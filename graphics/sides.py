"""The limbs of the far side taken from those of the near side, so that each is drawn once.

A doll has an arm and a leg on either side, each with a zone of its own on the paper. They are
laid out alike, the far ones a way off from the near ones. Whoever would rather not draw every
limb twice has what is in each zone of the near side put in the zone of the far side that
matches it, as it is or a shade darker, since what is further off is in the shade of the body.

A limb goes over whole, all of its zone at once: taken part by part it left behind whatever
lies past its first joint, where it meets the trunk.

It is the drawing itself that is changed: the doll is cut from it as from any other, and it is
kept as any other is.
"""

import pygame

import copy

from graphics.doll import Doll, DollLimb, DollPart, DollTemplate, shaded
from graphics.doll_guide import Piece, piece_zone, pieces

NEAR_SIDE, FAR_SIDE = "_right", "_left"
# How the far side comes by its limbs: drawn by hand, or taken from the near side, as they are or darker.
OWN, SAME, DARKER = "own", "same", "darker"
WAYS = (OWN, SAME, DARKER)
# How much darker.
SHADE = 0.16
SOLID = (255, 255, 255, 255)
CLEAR = (0, 0, 0, 0)


def limbs(template: DollTemplate, canvas: str) -> list[tuple[Piece, Piece]]:
    """The limbs of a canvas that are of the near side and have one like them on the far side,
    with that one: each a piece of the paper, part by part from the trunk outwards."""
    drawn = pieces(template, canvas)
    found = []
    for piece in drawn:
        if not piece or not all(bone.endswith(NEAR_SIDE) for bone in piece):
            continue
        other = tuple(bone.removesuffix(NEAR_SIDE) + FAR_SIDE for bone in piece)
        if other in drawn:
            found.append((piece, other))
    return found


def match_far_side(template: DollTemplate, canvas: str, drawing: pygame.Surface, shade: float = 0.0) -> bool:
    """Have every limb of the far side be what is drawn for the near side, on a drawing, in
    place. Whatever was in the zones of the far side is gone. Returns whether anything changed.

    `shade` is how much darker the far side is made, from not at all to black.
    """
    if drawing.get_size() != template.canvases[canvas]:
        return False
    pairs = limbs(template, canvas)
    before = drawing.copy()
    copies = []
    for near, far in pairs:
        # What of the drawing is this limb's own, to be put as far off as the other is.
        piece = drawing.copy()
        piece.blit(piece_zone(template, near).to_surface(setcolor=SOLID, unsetcolor=CLEAR), (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
        start, other = template.parts[near[0]].start, template.parts[far[0]].start
        copies.append((piece, piece.get_bounding_rect(), (round(other[0] - start[0]), round(other[1] - start[1]))))
    for _, far in pairs:
        drawing.blit(piece_zone(template, far).to_surface(setcolor=SOLID, unsetcolor=CLEAR), (0, 0), special_flags=pygame.BLEND_RGBA_SUB)
    level = round(255 * (1.0 - max(0.0, min(1.0, shade))))
    for piece, box, (dx, dy) in copies:
        if not box.width:
            continue
        cut = piece.subsurface(box).copy()
        if level < 255:
            cut.fill((level, level, level, 255), special_flags=pygame.BLEND_RGBA_MULT)
        # Added to nothing, it is copied as it is, edges and all.
        drawing.blit(cut, (box.x + dx, box.y + dy), special_flags=pygame.BLEND_RGBA_ADD)
    return pygame.image.tobytes(before, "RGBA") != pygame.image.tobytes(drawing, "RGBA")


def far_darker(doll: Doll, shade: float) -> Doll:
    """A doll with the limbs of its far side a shade darker, and the rest of it as it was.

    Kept darker in the drawing, the far side was in the shade of the body however the body
    was turned, and a body seen from the front had one arm darker than the other. So the
    drawing has both sides alike, and the shade is put on here, by whoever shows the doll, as
    much as the body is seen from its side.

    A limb of rubber is not another limb for being in the shade: it is told how dark it is,
    and whoever bends it darkens it after. Made another picture for every shade, it was bent
    again for every shade, and a body that turned as it walked was never done bending.
    """
    hundredths = round(max(0.0, min(1.0, shade)) * 100)
    if hundredths <= 0:
        return doll
    other = copy.copy(doll)
    other.parts = {
        bone: DollPart(shaded(part.image, hundredths), part.start, part.end) if bone.endswith(FAR_SIDE) else part
        for bone, part in doll.parts.items()
    }
    made: dict[int, DollLimb] = {}
    limbs = {}
    for bone, limb in doll.limbs.items():
        if not limb.bones[0].endswith(FAR_SIDE):
            limbs[bone] = limb
            continue
        if id(limb) not in made:
            made[id(limb)] = DollLimb(limb.bones, limb.image, limb.joints, limb.tipped, limb.mark, hundredths)
        limbs[bone] = made[id(limb)]
    other.limbs = limbs
    # Its parts are other pictures, and whatever was kept of them at a size is of no use: its
    # limbs are as they were read to be bent.
    other._sized, other._turned, other._standing = {}, {}, None
    return other
