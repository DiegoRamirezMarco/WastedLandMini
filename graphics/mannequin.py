"""The plain figure every doll starts from: an artist's, with no clothes and no face.

It is what the guide shows to be drawn over, pale, and what whoever nobody has drawn is shown
as, in a colour of their own. It says nothing about who anybody is, so that it does not get in
the way of what is drawn of them.

The figure is put together from what each part is said to be in the template (`shape`). It is a
drawing like any other and is cut like one: a limb in one piece, hand or foot and all, and the
trunk in one with the hips.
"""

import math
from dataclasses import dataclass

import pygame

from graphics.doll import DollTemplate, PartSpec
from graphics.palette import Color
from graphics.ui_art import mix
from skeleton.plan import SIDES

Point = tuple[float, float]
# A place along a part and how far the figure reaches there: a share of the part's length and,
# past either end, of its radius; then how far behind its bone and how far ahead, in radii.
Station = tuple[float, float, float, float]

SOLID = (255, 255, 255, 255)
CLEAR = (0, 0, 0, 0)
# How much of the line's colour is in the shade of a part, and in a part of the far side.
SHADE = 0.16
FAR = 0.24

# The parts that run on one into the next, by what each is.
PROFILES: dict[str, tuple[Station, ...]] = {
    "neck": ((0.0, -0.4, 1.0, 1.0), (1.0, 0.0, 0.94, 0.94), (1.0, 0.55, 0.6, 0.6)),
    "chest": (
        (0.0, 0.0, 0.62, 0.66), (0.3, 0.0, 0.8, 0.9), (0.62, 0.0, 0.93, 1.0), (0.9, 0.0, 0.92, 0.9),
        (1.0, 0.0, 0.8, 0.72), (1.0, 0.3, 0.36, 0.34),
    ),
    "pelvis": ((0.0, 0.0, 0.62, 0.66), (0.5, 0.0, 0.86, 0.8), (1.0, 0.0, 0.9, 0.8), (1.0, 0.3, 0.5, 0.44)),
    # What is under the hips, between the legs: as wide as the hips where it hangs from them,
    # and in to a round end.
    "briefs": ((0.0, 0.0, 0.9, 0.8), (0.5, 0.0, 0.84, 0.76), (1.0, 0.0, 0.62, 0.58), (1.0, 0.3, 0.3, 0.28)),
    "upper_arm": ((0.0, 0.0, 1.0, 1.0), (0.45, 0.0, 0.98, 0.94), (1.0, 0.0, 0.8, 0.8)),
    "forearm": ((0.0, 0.0, 0.8, 0.8), (0.28, 0.0, 0.84, 0.9), (1.0, 0.0, 0.6, 0.6)),
    "thigh": ((0.0, 0.0, 1.0, 1.0), (0.4, 0.0, 1.0, 0.98), (1.0, 0.0, 0.76, 0.76)),
    "shin": ((0.0, 0.0, 0.76, 0.76), (0.3, 0.0, 0.88, 0.74), (1.0, 0.0, 0.54, 0.54)),
}
# The round a limb begins with where it is joined on: half a circle over its first joint.
ROUND_TOP: tuple[Station, ...] = ((0.0, -0.96, 0.28, 0.28), (0.0, -0.75, 0.66, 0.66), (0.0, -0.4, 0.92, 0.92))
# A hand: a mitten, and a thumb on the side it faces, from one place along and across it to another.
HAND: tuple[Station, ...] = (
    (0.0, -0.2, 0.55, 0.55), (0.3, 0.0, 0.74, 0.8), (0.58, 0.0, 0.8, 0.82), (0.86, 0.0, 0.66, 0.6),
    (1.0, 0.0, 0.42, 0.36), (1.0, 0.2, 0.14, 0.12),
)
THUMB = ((0.26, 0.62), (0.6, 1.1), 0.27)
# A foot, corner by corner: how far along it, as a share of its length and then in radii, and how
# far under the ankle, in radii.
FOOT = (
    (0.0, -0.8, -0.2), (0.0, 0.8, -0.2), (0.75, 0.3, 0.62), (1.0, 0.55, 0.78), (1.0, 1.0, 1.08),
    (1.0, 0.96, 1.45), (0.0, -0.95, 1.45), (0.0, -1.06, 0.9), (0.0, -0.96, 0.2),
)
# A head seen from its side, looking right, corner by corner in radii from its middle: round
# behind and on top, flatter in front, with a chin.
HEAD = (
    (-0.1, -1.0), (0.42, -0.92), (0.78, -0.62), (0.9, -0.2), (0.84, 0.16), (0.82, 0.48), (0.7, 0.84),
    (0.42, 1.02), (0.04, 0.94), (-0.3, 0.66), (-0.62, 0.56), (-0.96, 0.22), (-1.04, -0.26),
    (-0.8, -0.74), (-0.46, -0.96),
)


@dataclass(frozen=True)
class Tones:
    """The colours a plain figure is made in: one of its own, and what shade and distance make of it."""

    fill: Color
    shade: Color
    far: Color
    far_shade: Color
    line: Color


def tones_of(color: Color, line: Color) -> Tones:
    """A figure of one colour with a line of another round it."""
    far = mix(color, line, FAR)
    return Tones(color, mix(color, line, SHADE), far, mix(far, line, SHADE), line)


def on_far_side(bone: str) -> bool:
    """Whether a part is on the side of the body turned away: the first of the two sides."""
    return bone.endswith(SIDES[0])


class _Frame:
    """A part as something to draw along: where it starts, which way it runs, and which way is across it."""

    def __init__(self, spec: PartSpec) -> None:
        dx, dy = spec.end[0] - spec.start[0], spec.end[1] - spec.start[1]
        self.length = math.hypot(dx, dy) or 1.0
        self.start, self.end, self.radius = spec.start, spec.end, spec.radius
        self.along = (dx / self.length, dy / self.length)
        # Across is the way the figure faces, to the right of the canvas; for a part lying along that way, down.
        across = (-self.along[1], self.along[0])
        if across[0] < -0.5 or (abs(across[0]) <= 0.5 and across[1] < 0):
            across = (-across[0], -across[1])
        self.across = across

    def at(self, along: float, across: float = 0.0) -> Point:
        """A point so many pixels along the part from its first joint, and so many to the side."""
        return (
            self.start[0] + self.along[0] * along + self.across[0] * across,
            self.start[1] + self.along[1] * along + self.across[1] * across,
        )

    def sides(self, station: Station) -> tuple[Point, Point]:
        """Where the figure's back and its front are at one place along the part."""
        share, beyond, behind, ahead = station
        along = share * self.length + beyond * self.radius
        return self.at(along, -behind * self.radius), self.at(along, ahead * self.radius)


def _smooth(points: list[Point], times: int = 2) -> list[Point]:
    """A closed outline with its corners cut, and cut again: straight runs turn into curves."""
    for _ in range(times):
        cut = []
        for index, (x, y) in enumerate(points):
            next_x, next_y = points[(index + 1) % len(points)]
            cut.append((x * 0.75 + next_x * 0.25, y * 0.75 + next_y * 0.25))
            cut.append((x * 0.25 + next_x * 0.75, y * 0.25 + next_y * 0.75))
        points = cut
    return points


def _run(blob: pygame.Surface, run: list[tuple[_Frame, tuple[Station, ...]]]) -> None:
    """Parts that go on one from the other, drawn as one shape from end to end."""
    sides = [frame.sides(station) for frame, profile in run for station in profile]
    outline = [back for back, _ in sides] + [front for _, front in reversed(sides)]
    pygame.draw.polygon(blob, SOLID, _smooth(outline))


def _plain(blob: pygame.Surface, frame: _Frame) -> None:
    """A part the figure has no shape for: a rounded strip from one joint to the next."""
    radius = max(1, round(frame.radius))
    pygame.draw.line(blob, SOLID, frame.start, frame.end, radius * 2 + 1)
    pygame.draw.circle(blob, SOLID, frame.start, radius)
    pygame.draw.circle(blob, SOLID, frame.end, radius)


def _hand(blob: pygame.Surface, frame: _Frame) -> None:
    _run(blob, [(frame, HAND)])
    (from_along, from_across), (to_along, to_across), wide = THUMB
    start = frame.at(from_along * frame.length, from_across * frame.radius)
    end = frame.at(to_along * frame.length, to_across * frame.radius)
    radius = max(2, round(wide * frame.radius))
    pygame.draw.line(blob, SOLID, start, end, radius * 2)
    pygame.draw.circle(blob, SOLID, start, radius)
    pygame.draw.circle(blob, SOLID, end, radius)


def _foot(blob: pygame.Surface, frame: _Frame) -> None:
    corners = [frame.at(share * frame.length + along * frame.radius, under * frame.radius) for share, along, under in FOOT]
    pygame.draw.polygon(blob, SOLID, _smooth(corners))


def _head(blob: pygame.Surface, spec: PartSpec) -> None:
    (x, y), radius = spec.end, spec.radius
    pygame.draw.polygon(blob, SOLID, _smooth([(x + across * radius, y + down * radius) for across, down in HEAD]))


ENDS = {"hand": _hand, "foot": _foot}


def _limb(blob: pygame.Surface, specs: list[PartSpec]) -> None:
    """A limb in one piece: the parts that bend as one shape, round where it is joined on, and
    its hand or its foot."""
    run = [(_Frame(spec), PROFILES[spec.shape]) for spec in specs if spec.shape in PROFILES]
    if run:
        run[0] = (run[0][0], ROUND_TOP + run[0][1])
        _run(blob, run)
    for spec in specs:
        if spec.shape in ENDS:
            ENDS[spec.shape](blob, _Frame(spec))
        elif spec.shape not in PROFILES:
            _plain(blob, _Frame(spec))


def _mass(blob: pygame.Surface, specs: list[PartSpec]) -> None:
    """Parts that stand on one joint: a chest and the hips under it are one shape, with a waist."""
    shaped = [(_Frame(spec), PROFILES[spec.shape]) for spec in specs if spec.shape in PROFILES]
    for spec in specs:
        if spec.shape not in PROFILES:
            _plain(blob, _Frame(spec))
    if len(shaped) == 2 and sum(one * other for one, other in zip(shaped[0][0].along, shaped[1][0].along)) < -0.9:
        # One runs up from the joint and the other down: from the far end of one to that of the other.
        (first, upper), (second, lower) = shaped
        _run(blob, [(second, lower[:0:-1]), (first, upper)])
        return
    for frame, profile in shaped:
        _run(blob, [(frame, profile)])


class _Sheet:
    """A canvas on which shapes are put down one over another, each with a line round it and a
    band of shade along its back and under it, as if light fell on it from ahead and above."""

    def __init__(self, size: tuple[int, int], line: int, depth: int, tones: Tones) -> None:
        self.size, self.depth, self.tones = size, depth, tones
        self.surface = pygame.Surface(size, pygame.SRCALPHA)
        self._reach = [
            (dx, dy) for dx in range(-line, line + 1) for dy in range(-line, line + 1) if dx * dx + dy * dy <= line * line
        ]

    def blob(self) -> pygame.Surface:
        return pygame.Surface(self.size, pygame.SRCALPHA)

    def stamp(self, blob: pygame.Surface, far: bool) -> None:
        """Put a shape down with its line and its shade: whatever it covers of what was there is gone."""
        tones = self.tones
        shape = pygame.mask.from_surface(blob)
        grown = pygame.Mask(self.size)
        for offset in self._reach:
            grown.draw(shape, offset)
        self.surface.blit(grown.to_surface(setcolor=(*tones.line, 255), unsetcolor=CLEAR), (0, 0))
        shape.to_surface(self.surface, setcolor=(*(tones.far_shade if far else tones.shade), 255), unsetcolor=None)
        lit = shape.overlap_mask(shape, (self.depth, -(self.depth // 2)))
        lit.to_surface(self.surface, setcolor=(*(tones.far if far else tones.fill), 255), unsetcolor=None)


def figure(template: DollTemplate, canvas: str, tones: Tones, line: int | None = None) -> pygame.Surface:
    """The plain figure on one canvas, in the colours given. `line` is how wide the line round it is."""
    size = template.canvases[canvas]
    line = line if line is not None else max(2, template.unit // 6)
    sheet = _Sheet(size, line, max(2, template.unit // 4), tones)
    mine = {bone: spec for bone, spec in template.parts.items() if spec.canvas == canvas}
    limbs = {limb[0]: limb for limb in template.hoses if set(limb) <= mine.keys()}
    in_limbs = {bone for limb in limbs.values() for bone in limb}
    drawn: set[str] = set()
    for bone, spec in mine.items():
        if bone in drawn:
            continue
        blob = sheet.blob()
        if spec.whole:
            _head(blob, spec)
            together = [bone]
        elif bone in limbs:
            together = list(limbs[bone])
            _limb(blob, [mine[part] for part in together])
        elif bone in in_limbs:
            continue
        else:
            together = [
                other for other, each in mine.items()
                if not each.whole and other not in in_limbs and each.start == spec.start
            ]
            _mass(blob, [mine[other] for other in together])
        drawn.update(together)
        sheet.stamp(blob, on_far_side(bone))
    # Nothing of it is left where no part would take it: it is what the game cuts out of it.
    taken = pygame.Mask(size)
    for bone in mine:
        taken.draw(pygame.mask.from_surface(template.cut_mask(bone, sheet.surface)), (0, 0))
    kept = taken.to_surface(setcolor=SOLID, unsetcolor=(255, 255, 255, 0))
    sheet.surface.blit(kept, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
    return sheet.surface


def figures(template: DollTemplate, tones: Tones, line: int | None = None) -> dict[str, pygame.Surface]:
    """The plain figure on every canvas: drawings to cut a doll from, or to start one's own from."""
    return {canvas: figure(template, canvas, tones, line) for canvas in template.canvases}
