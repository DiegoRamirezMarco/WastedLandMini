"""What is traced over when a resident is drawn: every piece in a zone of its own, marked where
it bends, and under it all a plain figure to take as a reference.

A piece is what moves in one: a limb from where it is joined on to its fingers or its toes, and
the trunk with the hips and the neck. The figure is pale and says nothing of who is being drawn.
It is only ever a guide: nothing of it ends up in anybody's drawing unless they trace it.
"""

import math

import pygame

from graphics.doll import DollTemplate
from graphics.mannequin import SOLID, Tones, figure, tones_of
from graphics.palette import PALETTE, Color
from graphics.ui_art import mix

Point = tuple[float, float]
Piece = tuple[str, ...]

INK = PALETTE["ink"]
# Pieces on the near side of the body are tinted in one colour, on the far side in another, and
# what is in the middle in a third.
GUIDE_NEAR = PALETTE["sand"]
GUIDE_FAR = PALETTE["teal"]
GUIDE_MIDDLE = PALETTE["stone"]
GUIDE_JOINT = PALETTE["ember"]
# The figure of the guide is a little lighter than the paper it lies on, with a soft line round it.
GUIDE_TONES: Tones = tones_of((238, 231, 214), (134, 114, 96))
# How solid the zone of a piece and the line round it are, out of 255.
ZONE_FILL = 30
ZONE_LINE = 200
# Where a piece bends it is crossed by dots this long, this far apart, this much darker than its tint.
DOTS = (2, 3)
DOTS_DARKER = 0.25
# How much of the ink is in what is written on a piece, the rest being its tint.
NAME_DARKER = 0.55
# What is written on the guide about no piece in particular.
NOTE_INK: Color = mix(GUIDE_MIDDLE, INK, NAME_DARKER)


def side_tint(bone: str) -> Color:
    """The colour of a part on the guide: one for the near side of the body, one for the far, one for the middle."""
    return GUIDE_NEAR if bone.endswith("_right") else (GUIDE_FAR if bone.endswith("_left") else GUIDE_MIDDLE)


def name_ink(bone: str) -> Color:
    """The colour a part is named in on the guide: that of its side, dark enough to be read."""
    return mix(side_tint(bone), INK, NAME_DARKER)


def reference(template: DollTemplate, canvas: str) -> pygame.Surface:
    """The figure of the guide on one canvas: a drawing like any other, and cut like one."""
    return figure(template, canvas, GUIDE_TONES)


def pieces(template: DollTemplate, canvas: str) -> list[Piece]:
    """What a canvas is drawn in, piece by piece: each limb whole, and whatever else is joined together."""
    mine = [bone for bone, spec in template.parts.items() if spec.canvas == canvas and not spec.whole]
    limbs = [tuple(part for part in limb if part in mine) for limb in template.hoses]
    found: list[Piece] = [limb for limb in limbs if limb]
    loose = [bone for bone in mine if not any(bone in limb for limb in found)]

    def joints(bone: str) -> set[Point]:
        return {template.parts[bone].start, template.parts[bone].end}

    while loose:
        group = [loose.pop(0)]
        grown = True
        while grown:
            near = [bone for bone in loose if any(joints(bone) & joints(other) for other in group)]
            grown = bool(near)
            group += near
            loose = [bone for bone in loose if bone not in near]
        found.append(tuple(group))
    return found


def piece_zone(template: DollTemplate, piece: Piece) -> pygame.mask.Mask:
    """Everywhere a piece may be drawn: what is each part's own, and the round a limb begins with."""
    size = template.canvases[template.parts[piece[0]].canvas]
    zone = pygame.Mask(size)
    seams = pygame.Surface(size, pygame.SRCALPHA)
    for bone in piece:
        spec = template.parts[bone]
        zone.draw(pygame.mask.from_surface(template.region(bone)), (0, 0))
        for joint, keep in template.cuts(spec):
            reach = template.reach_at(spec, joint)
            if template.sharing(spec, joint):
                # Neither of two parts has the very line they are cut apart along: the piece does.
                across = (-keep[1] * reach, keep[0] * reach)
                pygame.draw.line(
                    seams, SOLID, (joint[0] - across[0], joint[1] - across[1]), (joint[0] + across[0], joint[1] + across[1]), 3
                )
                continue
            # Where nothing else begins, as at a shoulder, the game rounds the end off by itself:
            # what is drawn past the joint is kept as far as that round goes.
            dome = pygame.Surface(size, pygame.SRCALPHA)
            pygame.draw.circle(dome, SOLID, joint, reach)
            dome.blit(template.mask(bone), (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
            zone.draw(pygame.mask.from_surface(dome), (0, 0))
    zone.draw(pygame.mask.from_surface(seams), (0, 0))
    return zone


def piece_zones(template: DollTemplate, canvas: str) -> dict[Piece, pygame.mask.Mask]:
    """Every piece of a canvas with its zone."""
    return {piece: piece_zone(template, piece) for piece in pieces(template, canvas)}


def piece_spots(
    template: DollTemplate, canvas: str, zones: dict[Piece, pygame.mask.Mask] | None = None
) -> dict[Piece, pygame.Rect]:
    """Where each piece of a canvas is, as the box round its zone, for whoever names the sides of
    the body. `zones` are those of the pieces, if they have been worked out already."""
    spots = {}
    for piece, zone in (zones if zones is not None else piece_zones(template, canvas)).items():
        boxes = zone.get_bounding_rects()
        if boxes:
            spots[piece] = boxes[0].unionall(boxes[1:])
    return spots


def _dots(target: pygame.Surface, color: tuple[int, ...], start: Point, end: Point) -> None:
    dx, dy = end[0] - start[0], end[1] - start[1]
    length = math.hypot(dx, dy)
    if length <= 0:
        return
    step, covered = sum(DOTS), 0.0
    while covered < length:
        stop = min(length, covered + DOTS[0])
        pygame.draw.line(
            target,
            color,
            (start[0] + dx * covered / length, start[1] + dy * covered / length),
            (start[0] + dx * stop / length, start[1] + dy * stop / length),
        )
        covered += step


def cuts(template: DollTemplate, canvas: str, among: Piece | None = None) -> list[tuple[Point, Point]]:
    """Every line a drawing on this canvas is cut along, once each, as its two ends: where it bends.

    With `among`, only those of the parts of one piece.
    """
    lines: dict[tuple[int, int, int, int], tuple[Point, Point]] = {}
    for bone, spec in template.parts.items():
        if spec.canvas != canvas or spec.whole or (among is not None and bone not in among):
            continue
        for joint, keep in template.cuts(spec):
            reach = template.reach_at(spec, joint)
            across = (-keep[1], keep[0])
            ends = (
                (joint[0] - across[0] * reach, joint[1] - across[1] * reach),
                (joint[0] + across[0] * reach, joint[1] + across[1] * reach),
            )
            first, second = sorted(ends)
            # Both parts that meet at a joint are cut along the same line there; the longer one is drawn.
            key = (round(joint[0]), round(joint[1]), round(abs(across[0]) * 10), round(abs(across[1]) * 10))
            known = lines.get(key)
            if known is None or math.dist(*known) < math.dist(first, second):
                lines[key] = (first, second)
    return list(lines.values())


def build_guide(
    template: DollTemplate,
    canvas: str,
    zones: dict[Piece, pygame.mask.Mask] | None = None,
    figure: pygame.Surface | None = None,
) -> pygame.Surface:
    """What is shown under a canvas to draw over.

    Each piece has a zone of its own, lightly tinted by the side of the body it is on, with a thin
    line round all of it and not round each of its parts. The plain figure lies in the middle of
    it. Where a piece bends it is crossed by a line of dots, and every joint has a small ring.
    `zones` are those of the pieces, if they have been worked out already. `figure` is the
    figure to lie in it, where it is not the plain one as it comes.
    """
    size = template.canvases[canvas]
    guide = pygame.Surface(size, pygame.SRCALPHA)
    zones = zones if zones is not None else piece_zones(template, canvas)
    for piece, zone in zones.items():
        zone.to_surface(guide, setcolor=(*side_tint(piece[0]), ZONE_FILL), unsetcolor=None)
    guide.blit(figure if figure is not None else reference(template, canvas), (0, 0))
    marks = pygame.Surface(size, pygame.SRCALPHA)
    for piece, zone in zones.items():
        tint = side_tint(piece[0])
        for start, end in cuts(template, canvas, piece):
            _dots(marks, (*mix(tint, INK, DOTS_DARKER), 255), start, end)
        for part in zone.connected_components():
            edge = part.outline()
            if len(edge) > 2:
                pygame.draw.lines(marks, (*tint, ZONE_LINE), True, edge)
    guide.blit(marks, (0, 0))
    radius = max(2, template.unit // 5)
    for spec in template.parts.values():
        if spec.canvas != canvas:
            continue
        for joint in (spec.start,) if spec.whole else (spec.start, spec.end):
            at = (round(joint[0]), round(joint[1]))
            pygame.draw.circle(guide, (*PALETTE["paper"], 255), at, radius)
            pygame.draw.circle(guide, (*GUIDE_JOINT, 255), at, radius, 1)
            guide.set_at(at, (*GUIDE_JOINT, 255))
    return guide


def label_spots(template: DollTemplate, canvas: str) -> dict[str, pygame.Rect]:
    """Where each part of a canvas is, as the box round its zone, for whoever names the parts on the guide."""
    spots = {}
    for bone, spec in template.parts.items():
        if spec.canvas == canvas and not spec.whole:
            boxes = pygame.mask.from_surface(template.region(bone)).get_bounding_rects()
            if boxes:
                spots[bone] = boxes[0].unionall(boxes[1:])
    return spots
