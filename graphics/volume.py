"""The trunk of a doll as something round, with its drawing wrapped about it.

A trunk is drawn once, as it is seen from the front. It is then taken for a solid: at every
height as wide as the drawing is there, and some share of that from chest to back. The drawing
is its skin, wrapped round it: what is drawn in the middle is on its chest, and what is drawn at
either edge is on its sides. Turned, the skin goes round with it, each pixel of it where that
part of the solid now is, and what comes into sight from behind is the same drawing in a mirror.

So one drawing does for the trunk seen from the front, three quarters on, from its side and
anywhere between, and nothing of it is pulled wide or pressed narrow by guess. Seen from the
front it is the drawing itself, untouched.

Two things a wrapped drawing cannot do by itself, and what is done about them:

- The line round a trunk is drawn at its edges, and an edge is not an edge once the trunk has
  turned. So the line is told from the drawing, row by row, and left out of the skin: what is
  inside it is what goes all the way round. It is put back round the trunk wherever its edge
  now is.
- A drawing made from the front says very little of the sides: they are its last few columns.
  Seen from its side a trunk is mostly side, so it is mostly those few columns, drawn out. A
  plain trunk bears that; one with a great deal drawn near its edges will show it. And a solid
  of this kind is the same from chest to back all the way up: it has no belly and no chest to
  show from the side. Neither is mended here: both want a second drawing.

This needs numpy. Without it a trunk is left as it was drawn, whichever way the body is turned.
"""

import copy
import itertools
import math
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

import pygame

from graphics import hose as rubber
from graphics.doll import BACKWARDS, Doll, DollLimb, DollPart, DollTemplate
from graphics.face import BodyTurn

try:
    import numpy as np
except ImportError:  # No numpy: every trunk stays as it was drawn.
    np = None

AVAILABLE = np is not None
# What tells one trunk of rubber from another made from the same doll.
_MARKS = itertools.count(1)

# How faint a pixel may be and still be of the drawing.
SOLID_FROM = 40
# A pixel no lighter than this, red, green and blue added up, is taken to be of a line.
DARKEST_FILL = 215
# How far in from the edge a line is looked for, in pixels: a row dark for further than that is
# not a row with a line at its edge, but a row that is all line, as the top of a shoulder is.
LINE_AT_MOST = 22
# The fewest rows, of those wide enough to tell, that must have a line at their edge for the
# drawing to be taken to have a line round it.
ROWS_WITH_LINE = 0.5
# The most of a row, from its middle to its edge, that is ever taken to be line.
LINE_OF_ROW = 0.3
# The fewest pixels of a row that are not line for its colour to be told from them, and the
# least share of the row they must be.
PLAIN_AT_LEAST = 3
PLAIN_SHARE = 0.4
# The least share of a drawing that is light enough not to be line, for its colour to be told
# from that alone.
LIGHT_AT_LEAST = 0.35
# How far round from the middle of the chest, in radians, a trunk is still its drawing, and by
# how far round it is nothing but the plain colour of each row.
CHEST_DRAWN_TO = math.radians(52.0)
SIDES_PLAIN_BY = math.radians(80.0)
# And by how far round nothing of a line that was drawn on it is left. A line near the edge
# of a chest is on a few columns of the drawing, which are most of a side: gone by degrees as
# the colour under it goes, it was a wide grey smear down the side of a trunk that had turned.
LINES_GONE_BY = math.radians(58.0)
# A pixel as light as this, red, green and blue added up, is none of a line: between that
# and the darkest that is not line, it is part of one.
NO_LINE_FROM = 340
# How many places across each pixel of a trunk that has gone round its drawing is looked at.
# Round a side, many pixels of the drawing go to one of what is seen: looked at in one place,
# a line drawn on a chest is there in one row and gone in the next.
ACROSS = 3


@dataclass(frozen=True)
class Solid:
    """The solid a trunk's drawing is wrapped round, by the rows of the paper from `top` down.

    `half` is how far out to either side of its middle it goes at each height, with its middle
    `axis` across the paper. `edge` is how much of each row, in from its edge, is the line
    round the drawing and not the drawing itself. `line` and `ink` are how thick that line is
    for the most part and its colour: nothing for a drawing with no line round it.

    It is one solid for all the parts of a trunk. Each part has a round end past the joint it
    turns about, which lies under the next part: wrapped round a solid of its own, that end
    went its own way and showed inside the trunk, with a line round it.
    """

    axis: float
    top: int
    half: Any
    edge: Any
    line: int = 0
    ink: tuple[int, int, int] = (0, 0, 0)
    # The colour each row is for the most part, its lines apart: what its sides and its back
    # are, where the drawing has nothing to say of them.
    fill: Any = None
    # Which rows have anything on them that is not line: one that is all line, as the line
    # along the top of a shoulder is, has no colour to go to, and goes round as it is.
    told: Any = None


def _measured(image: pygame.Surface, axis: float, top: int = 0) -> Solid | None:
    """The solid that a picture of a trunk is the skin of. None for a picture with nothing on it."""
    width, height = image.get_size()
    rgb = pygame.surfarray.array3d(image).astype(np.int64)
    alpha = pygame.surfarray.array_alpha(image)
    solid = alpha >= SOLID_FROM
    if not solid.any():
        return None
    columns = np.arange(width)[:, None]
    left = np.where(solid, columns, width).min(axis=0)
    right = np.where(solid, columns, -1).max(axis=0)
    drawn = right >= left
    half = np.maximum(np.where(drawn, np.maximum(axis - left, right + 1 - axis), 0.0), 0.0)
    # How far in from either edge each row goes on being dark: its line there.
    dark = solid & (rgb.sum(axis=2) <= DARKEST_FILL)
    rows = np.arange(height)
    runs = []
    for start, step in ((np.where(drawn, left, 0), 1), (np.where(drawn, right, 0), -1)):
        run, still = np.zeros(height, dtype=np.int64), drawn.copy()
        for far in range(LINE_AT_MOST + 1):
            still = still & dark[np.clip(start + step * far, 0, width - 1), rows]
            run += still
        runs.append(run)
    edge = np.maximum(*runs)
    lined = (edge > 0) & (edge <= LINE_AT_MOST)
    # A row that is all line has none at its edge to leave out: it is skin as it stands.
    edge = np.where(lined, edge, 0)
    telling = drawn & (right - left >= LINE_AT_MOST * 2)
    line, ink = 0, (0, 0, 0)
    if telling.any() and (lined & telling).sum() >= telling.sum() * ROWS_WITH_LINE:
        line = int(np.median(edge[lined & telling]))
        at = [(int(np.where(drawn, left, 0)[y]) + int(edge[y]) // 2, y) for y in np.nonzero(lined & telling)[0]]
        red, green, blue = (int(value) for value in np.median(np.array([rgb[x, y] for x, y in at]), axis=0))
        ink = (red, green, blue)
    else:
        edge = np.zeros(height, dtype=np.int64)
    # What colour each row is where it is not line: of all of it, if it is all line.
    fill = np.zeros((height, 3))
    plain = solid & ~dark
    rows = np.nonzero(drawn)[0]
    told = np.zeros(height, dtype=bool)
    # Which rows have anything on them that is not line: one that has not goes round as it is.
    not_all_line = np.zeros(height, dtype=bool)
    for y in rows:
        # A row that is mostly line, as one a belt is drawn across, has no colour of its own.
        not_all_line[y] = plain[:, y].sum() >= PLAIN_AT_LEAST
        told[y] = plain[:, y].sum() >= max(PLAIN_AT_LEAST, solid[:, y].sum() * PLAIN_SHARE)
        fill[y] = np.median(rgb[plain[:, y] if told[y] else solid[:, y], y], axis=0)
    if told.any():
        # It has that of the nearest row that has one: given its own, a line drawn across a
        # trunk was a dark smear down either side of it once the trunk had turned.
        with_one = np.nonzero(told)[0]
        for y in rows[~told[rows]]:
            fill[y] = fill[with_one[np.abs(with_one - y).argmin()]]
    return Solid(axis, top, half, edge.astype(np.float64), line, ink, fill, not_all_line)


# The solids of the trunks of the dolls last turned, by the pictures each was measured from:
# a doll is measured once, however many ways it is turned. The pictures are kept with it, so
# that no other picture is ever taken for one of them.
_SOLIDS: dict[tuple[int, ...], tuple[tuple[pygame.Surface, ...], "Solid | None"]] = {}
KEPT_SOLIDS = 64


def solid_of(doll: Doll, trunk: Sequence[str]) -> Solid | None:
    """The solid the trunk of a doll is wrapped round, out of all its parts as they lie on the
    paper they were drawn on. None for a doll with no trunk drawn, or without numpy."""
    if np is None:
        return None
    pictures = tuple(doll.parts[bone].image for bone in trunk if bone in doll.parts and bone in doll.template.parts)
    key = tuple(id(picture) for picture in pictures)
    kept = _SOLIDS.get(key)
    if kept is None:
        while len(_SOLIDS) >= KEPT_SOLIDS:
            _SOLIDS.pop(next(iter(_SOLIDS)))
        kept = _SOLIDS[key] = (pictures, _solid_of(doll, trunk))
    return kept[1]


def _solid_of(doll: Doll, trunk: Sequence[str]) -> Solid | None:
    placed = []
    for bone in trunk:
        part, spec = doll.parts.get(bone), doll.template.parts.get(bone)
        if part is not None and spec is not None:
            # Where on its paper the corner of the part's picture is.
            placed.append((part, round(spec.start[0] - part.start[0]), round(spec.start[1] - part.start[1])))
    if not placed:
        return None
    left = min(across for _, across, _ in placed)
    top = min(above for _, _, above in placed)
    right = max(across + part.image.get_width() for part, across, _ in placed)
    foot = max(above + part.image.get_height() for part, _, above in placed)
    # The trunk as it was drawn, all of a piece: its parts say the same where they lie over one another.
    whole = pygame.Surface((right - left, foot - top), pygame.SRCALPHA)
    for part, across, above in placed:
        whole.blit(part.image, (across - left, above - top))
    first, across, _ = placed[0]
    axis = across + (first.start[0] + first.end[0]) / 2.0
    solid = _measured(whole, axis - left, top)
    return None if solid is None else Solid(axis, top, solid.half, solid.edge, solid.line, solid.ink, solid.fill, solid.told)


def wrapped(
    part: DollPart, yaw: float, depth: float, side: float = 90.0, solid: Solid | None = None, corner: tuple[int, int] = (0, 0)
) -> DollPart:
    """A part of a trunk, drawn from the front, as it is seen with the body `yaw` degrees round
    from facing the screen, where `side` degrees is seen from its side.

    `depth` is how far it is from chest to back, as a share of how wide it is. `solid` is what
    it is wrapped round, with `corner` where on the paper the corner of the part's picture is:
    without one it is wrapped round a solid of its own, as wide as itself at every height.
    Seen from the front it is the part itself.
    """
    angle = math.radians(max(0.0, min(side, abs(yaw))) * 90.0 / side)
    if np is None or angle < 1e-6:
        return part
    image = part.image
    width, height = image.get_size()
    if solid is None:
        solid = _measured(image, (part.start[0] + part.end[0]) / 2.0)
        corner = (0, 0)
    if solid is None:
        return part
    # In single precision: it is a picture, and there is half as much of it to go through.
    rgb = pygame.surfarray.array3d(image).astype(np.float32)
    alpha = pygame.surfarray.array_alpha(image).astype(np.float32)
    axis = solid.axis - corner[0]
    theirs = np.clip(np.arange(height) + corner[1] - solid.top, 0, len(solid.half) - 1)
    half, lined, plain = (each[theirs].astype(np.float32) for each in (solid.half, solid.edge, solid.fill))
    # A drawing is as wide as a whole number of pixels at each height, and so is a step wider
    # or narrower than the row above. Each row is taken with its neighbours, so that an edge
    # that slants goes in or out by part of a pixel a row, which the edge below can show.
    evened = half.copy()
    evened[1:-1] = (half[:-2] + 2.0 * half[1:-1] + half[2:]) / 4.0
    between = np.zeros(len(half), dtype=bool)
    between[1:-1] = (half[:-2] > 0.5) & (half[1:-1] > 0.5) & (half[2:] > 0.5)
    half = np.where(between, evened, half)

    sine, cosine = math.sin(angle), math.cos(angle)
    # Seen that far round, a row that wide and that deep is this wide, and its middle has gone this far round.
    narrower = math.sqrt(cosine * cosine + depth * depth * sine * sine)
    gone = math.atan2(depth * sine, cosine)
    seen = half * narrower
    reach = int(math.ceil(float(seen.max()))) + 1
    out_width = reach * 2 + 1
    across = ((np.arange(out_width * ACROSS) + 0.5) / ACROSS - 0.5 - reach)[:, None].astype(np.float32)
    share = across / np.maximum(seen, 1e-6)[None, :]
    # How much of each pixel is of the trunk: all of it inside, none outside, and at its edge
    # the part that is. An edge that is there or is not has steps all the way down it.
    cover = np.clip((seen[None, :] - np.abs(across)) * ACROSS + 0.5, 0.0, 1.0) * (half[None, :] > 0.5)
    inside = cover > 0.0
    # Where on the skin each pixel now seen is: that far round the trunk, on its near half or,
    # in a mirror, its far one. The skin is the drawing inside its line: that is what goes all
    # the way round, and the line is put back at the edge afterwards.
    skin_half = np.maximum(half - np.minimum(lined, half * LINE_OF_ROW) - 1.0, 0.0)
    round_it = np.arcsin(np.clip(share, -1.0, 1.0)) - gone
    skin = skin_half[None, :] * np.sin(round_it)
    at = np.clip(axis + skin - 0.5, 0.0, width - 1.001)
    first = np.floor(at).astype(np.intp)
    blend = at - first
    rows = np.broadcast_to(np.arange(height)[None, :], first.shape)
    weighted = rgb * alpha[..., None]
    color = weighted[first, rows] * (1.0 - blend)[..., None] + weighted[first + 1, rows] * blend[..., None]
    opaque = alpha[first, rows] * (1.0 - blend) + alpha[first + 1, rows] * blend
    color = color / np.maximum(opaque, 1e-6)[..., None]
    # The drawing is of the chest. Of the sides and the back it has only its last few columns,
    # which drawn out across a side are streaks of whatever line ran near its edge. So the
    # further round from the middle of the chest, the more a row is its own plain colour, and
    # by the side it is nothing else: a trunk has a drawn chest, and plain sides and back.
    drawn_here = np.clip((SIDES_PLAIN_BY - np.abs(round_it)) / (SIDES_PLAIN_BY - CHEST_DRAWN_TO), 0.0, 1.0)
    # Only in the rows where this part goes out to the edge of the trunk. A part has a round
    # end past the joint it ends at, under the next part and narrower than it: given plain
    # sides out to the edge of the trunk, that end showed beside the part that is over it.
    columns = np.arange(width)[:, None]
    there = alpha >= SOLID_FROM
    own = np.where(there.any(axis=0), np.maximum(axis - np.where(there, columns, width).min(axis=0), np.where(there, columns, -1).max(axis=0) + 1 - axis), 0.0)
    to_the_edge = own >= solid.half[theirs] - np.maximum(lined, 2.0) - 2.0
    # What is line goes sooner than what is colour, and all at once: by how dark it is.
    lines_here = np.clip((LINES_GONE_BY - np.abs(round_it)) / (LINES_GONE_BY - CHEST_DRAWN_TO), 0.0, 1.0)
    of_line = np.clip((NO_LINE_FROM - color.sum(axis=2)) / (NO_LINE_FROM - DARKEST_FILL), 0.0, 1.0)
    drawn_here = drawn_here * (1.0 - of_line) + lines_here * of_line
    # A row that is all line has no colour to go to: it goes round as it was drawn.
    with_colour = solid.told[theirs] if solid.told is not None else np.ones(height, dtype=bool)
    drawn_here = np.where((to_the_edge & with_colour)[None, :], drawn_here, 1.0)
    color = color * drawn_here[..., None] + plain[None, :, :] * (1.0 - drawn_here)[..., None]
    opaque = opaque * drawn_here + 255.0 * (1.0 - drawn_here)
    if solid.line:
        # A line as thick as the drawing has it at that height, where its edge slants and is
        # thicker across: but never most of a row, a neck is not all line. Its inner edge too
        # is part of a pixel where it is part of one.
        thick = np.minimum(np.maximum(float(solid.line), lined), seen * LINE_OF_ROW)
        inked = np.clip((np.abs(across) - (seen - thick)[None, :]) * ACROSS + 0.5, 0.0, 1.0) * (inside & (opaque >= SOLID_FROM))
        color = color * (1.0 - inked)[..., None] + np.array(solid.ink, dtype=np.float32) * inked[..., None]
        opaque = opaque * (1.0 - inked) + 255.0 * inked
    opaque = opaque * cover
    # Each pixel is the middle of the places it was looked at in, their colours each times how solid.
    color = (color * opaque[..., None]).reshape(out_width, ACROSS, height, 3).mean(axis=1)
    opaque = opaque.reshape(out_width, ACROSS, height).mean(axis=1)
    color = color / np.maximum(opaque, 1e-6)[..., None]
    color = _beside(color, opaque)
    turned = pygame.Surface((out_width, height), pygame.SRCALPHA)
    pixels = pygame.surfarray.pixels3d(turned)
    pixels[:] = np.clip(color + 0.5, 0, 255).astype(np.uint8)
    del pixels
    clear = pygame.surfarray.pixels_alpha(turned)
    clear[:] = np.clip(opaque + 0.5, 0, 255).astype(np.uint8)
    del clear
    return DollPart(turned, (float(reach) + 0.5, part.start[1]), (float(reach) + 0.5, part.end[1]))


def _beside(color: Any, opaque: Any, far: int = 2) -> Any:
    """The colours of a picture with whatever is clear beside it given the colour of the
    picture next to it, `far` pixels out. Resized or turned afterwards, its edge is then mixed
    with its own colour and not with black: left black, the round end a part has under the
    next one was a dark hair of a line across the trunk, where its edge lay on it.
    """
    solid = (opaque > 0.5).astype(np.float32)
    known = color * solid[..., None]
    for _ in range(far):
        near, count = known.copy(), solid.copy()
        for axis, step in ((0, 1), (0, -1), (1, 1), (1, -1)):
            near += np.roll(known, step, axis=axis)
            count += np.roll(solid, step, axis=axis)
        found = (solid == 0) & (count > 0)
        known = np.where(found[..., None], near / np.maximum(count, 1.0)[..., None], known)
        solid = np.where(found, 1.0, solid).astype(np.float32)
    return np.where((opaque > 0.5)[..., None], color, known)


def _corner(doll: Doll, bone: str) -> tuple[int, int]:
    """Where on its paper the corner of the picture of one of a doll's parts is."""
    part, spec = doll.parts[bone], doll.template.parts[bone]
    return (round(spec.start[0] - part.start[0]), round(spec.start[1] - part.start[1]))


def _of_rubber(
    doll: Doll, turn: BodyTurn, solid: Solid | None, yaw: float, depth: float, side: float
) -> tuple[DollLimb, DollPart, tuple[int, int]] | None:
    """The trunk of a doll as one limb of rubber, turned as the body is: its hips and its trunk
    in one picture, with the joints they are bent at. With it, that picture as a part, and
    where on the paper its corner was before it was turned. None if it has not both of them
    drawn, or is not to be of rubber."""
    if len(turn.rubber) != 2 or not rubber.AVAILABLE or any(bone not in doll.parts for bone in turn.rubber):
        return None
    lower, upper = turn.rubber
    corners = {bone: _corner(doll, bone) for bone in turn.rubber}
    left = min(across for across, _ in corners.values())
    top = min(above for _, above in corners.values())
    right = max(corners[bone][0] + doll.parts[bone].image.get_width() for bone in turn.rubber)
    foot = max(corners[bone][1] + doll.parts[bone].image.get_height() for bone in turn.rubber)
    # The two as they were drawn, all of a piece: they say the same where one lies over the other.
    whole = pygame.Surface((right - left, foot - top), pygame.SRCALPHA)
    for bone in turn.rubber:
        whole.blit(doll.parts[bone].image, (corners[bone][0] - left, corners[bone][1] - top))
    specs = doll.template.parts
    # From the foot of the hips up to where the two meet, and on up to the top of the trunk.
    joints = [specs[lower].end, specs[lower].start, specs[upper].end]
    as_one = DollPart(whole, (joints[1][0] - left, joints[1][1] - top), (joints[2][0] - left, joints[2][1] - top))
    seen = wrapped(as_one, yaw, depth, side, solid, (left, top)) if solid is not None else as_one
    middle = seen.start[0]
    limb = DollLimb((f"{lower}{BACKWARDS}", upper), seen.image, tuple((middle, y - top) for _, y in joints), False, next(_MARKS))
    return limb, seen, (left, top)


def main_colour(image: pygame.Surface) -> tuple[int, int, int] | None:
    """The colour there is most of in a drawing, its lines apart: what a back nobody has drawn
    is. None for a drawing that is nothing but line, or nothing."""
    rgb = pygame.surfarray.array3d(image).astype(np.int64)
    solid = pygame.surfarray.array_alpha(image) >= SOLID_FROM
    plain = solid & (rgb.sum(axis=2) > DARKEST_FILL)
    if plain.sum() < solid.sum() * LIGHT_AT_LEAST:
        # Little of it is light enough not to be line: it is a dark thing, as dark skin is,
        # and not a thing that is mostly line. Its colour is the one there is most of in all of it.
        plain = solid
    if not plain.any():
        return None
    found = rgb[plain]
    # Colours a shade apart are one colour: sixteen to each of red, green and blue.
    near = (found[:, 0] >> 4) * 256 + (found[:, 1] >> 4) * 16 + (found[:, 2] >> 4)
    most = np.bincount(near).argmax()
    red, green, blue = (int(value) for value in np.median(found[near == most], axis=0))
    return (red, green, blue)


def plain_back(image: pygame.Surface, line: int, zones: Sequence[pygame.Surface] = ()) -> pygame.Surface:
    """A drawing of a trunk with nothing on it but the line round it: all of it the colour
    there is most of, and what is dark within `line` pixels of its edge left as it is. It is
    the back of a trunk nobody has drawn the back of.

    `zones` are parts of it that are each the colour there is most of in them, where that is
    not the colour of the whole: solid where each is, the later over the earlier. What is worn
    under the hips is its own colour from behind, and not that of the skin above it.
    """
    colour = main_colour(image)
    if colour is None:
        return image
    width, height = image.get_size()
    rgb = pygame.surfarray.array3d(image)
    alpha = pygame.surfarray.array_alpha(image)
    solid = alpha >= SOLID_FROM
    edge = np.zeros_like(solid)
    if line > 0:
        # Whatever is within so far of nothing, or of the edge of the picture.
        inside = np.zeros((width + 2, height + 2), dtype=bool)
        inside[1:-1, 1:-1] = solid
        for _ in range(line):
            inside[1:-1, 1:-1] &= inside[:-2, 1:-1] & inside[2:, 1:-1] & inside[1:-1, :-2] & inside[1:-1, 2:]
        edge = solid & ~inside[1:-1, 1:-1] & (rgb.astype(np.int64).sum(axis=2) <= DARKEST_FILL)
    plain = image.copy()
    pixels = pygame.surfarray.pixels3d(plain)
    pixels[solid & ~edge] = colour
    for zone in zones:
        only = image.copy()
        only.blit(zone, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
        its = main_colour(only)
        if its is not None:
            pixels[solid & ~edge & (pygame.surfarray.array_alpha(zone) > 0)] = its
    del pixels
    return plain


def back_of(doll: Doll, turn: BodyTurn) -> tuple[str, pygame.Surface] | None:
    """The back of the trunk of a doll as nobody has drawn it, on the paper its trunk is drawn
    on, and which paper that is: the trunk as it was drawn from the front, all the colour there
    is most of, with the line round it. None for a doll with no trunk, or without numpy."""
    template = doll.template
    bones = [bone for bone in turn.trunk if bone in doll.parts and bone in template.parts]
    canvas = template.parts[bones[0]].canvas if bones else None
    sheet = doll.sheets.get(canvas) if canvas is not None else None
    if sheet is None or np is None:
        return None
    theirs = pygame.Mask(sheet.get_size())
    for bone in bones:
        theirs.draw(pygame.mask.from_surface(template.cut_mask(bone, sheet)), (0, 0))
    only = sheet.copy()
    only.blit(theirs.to_surface(setcolor=(255, 255, 255, 255), unsetcolor=(255, 255, 255, 0)), (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
    solid = solid_of(doll, bones)
    box = only.get_bounding_rect()
    if not box.width:
        return canvas, only
    # Each part as far as it is its own, the further from the chest over the nearer. Only
    # where the trunk is: the rest of the paper is nothing, and a good deal of it.
    zones = [template.region(bone).subsurface(box) for bone in bones]
    behind = pygame.Surface(only.get_size(), pygame.SRCALPHA)
    behind.blit(plain_back(only.subsurface(box).copy(), solid.line + 2 if solid is not None and solid.line else 0, zones), box.topleft)
    return canvas, behind


# The parts of trunks seen from behind, by the doll each was cut for: a doll is cut again
# whenever its drawing changes, so what is kept for one is never out of date.
_BEHIND: dict[int, tuple[pygame.Surface | None, dict[str, DollPart]]] = {}
KEPT_BEHIND = 256


def _from_behind(doll: Doll, turn: BodyTurn, back: pygame.Surface | None) -> dict[str, DollPart]:
    """The parts of the trunk of a doll as they are seen from right behind it, each the other
    way about, as it is wrapped: its back, plain but for the line round it, with whatever has
    been drawn of its back over that. They are cut as the trunk itself was, all of a piece,
    and kept for the doll: the same pictures each time, so that what they are wrapped round
    is measured once."""
    kept = _BEHIND.get(doll._token)
    if kept is not None and kept[0] is back:
        return kept[1]
    parts: dict[str, DollPart] = {}
    plain = back_of(doll, turn)
    if plain is not None:
        canvas, behind = plain
        if back is not None and back.get_size() == behind.get_size():
            behind.blit(back, (0, 0))
        # Only its trunk is cut: nothing else is on that paper, and cutting is not quick.
        rest = tuple(bone for bone in doll.template.parts if bone not in turn.trunk)
        cut = Doll(doll.template, {canvas: behind}, doll.plan, rest)
        parts = {bone: _mirrored(cut.parts[bone]) for bone in turn.trunk if bone in cut.parts and bone in doll.parts}
    while len(_BEHIND) >= KEPT_BEHIND:
        _BEHIND.pop(next(iter(_BEHIND)))
    _BEHIND[doll._token] = (back, parts)
    return parts


def _mirrored(part: DollPart) -> DollPart:
    """A part the other way about, its joints with it."""
    width = part.image.get_width()
    return DollPart(pygame.transform.flip(part.image, True, False), (width - part.start[0], part.start[1]), (width - part.end[0], part.end[1]))


def turned_body(
    doll: Doll, turn: BodyTurn, yaw: float, depth: float, side: float = 90.0, back: pygame.Surface | None = None
) -> Doll:
    """A doll with its trunk turned and made of rubber, and the rest of it as it was: its
    limbs are not cut or bent again.

    Its hips and its trunk are one picture, bent along the bones of both as an arm is along its
    own: two stiff parts pinned where they meet came apart there as soon as they had turned,
    since the round end each had under the other was round no more.

    Further round than from its side, up to twice as far, it is seen from behind. What is
    wrapped round it then is its back: `back`, a drawing of it from right behind on the paper
    the trunk is drawn on, over a back that is plain but for the line round it. A trunk seen
    so far round from behind is one seen as far round from the front in a mirror, with its
    back for a chest: so that is how it is made.
    """
    if np is None or abs(yaw) <= side:
        return _turned(doll, turn, yaw, depth, side)
    behind = _from_behind(doll, turn, back)
    if not behind:
        return _turned(doll, turn, side, depth, side)
    other = copy.copy(doll)
    other.parts = {**doll.parts, **behind}
    other._sized, other._turned, other._standing = {}, {}, None
    seen = _turned(other, turn, max(0.0, 2.0 * side - abs(yaw)), depth, side)
    if seen is other:
        seen = copy.copy(other)
    seen.parts = {**seen.parts, **{bone: _mirrored(seen.parts[bone]) for bone in behind if bone in seen.parts}}
    limbs = dict(seen.limbs)
    for bone in turn.rubber:
        limb = limbs.get(bone)
        if limb is not None and limb.bones[0].endswith(BACKWARDS):
            width = limb.image.get_width()
            limbs[bone] = DollLimb(
                limb.bones, pygame.transform.flip(limb.image, True, False), tuple((width - x, y) for x, y in limb.joints), limb.tipped, next(_MARKS)
            )
    # The two parts of the trunk are one limb: both of its names go to the one picture.
    whole = next((limbs[bone] for bone in turn.rubber if bone in limbs and limbs[bone].bones[0].endswith(BACKWARDS)), None)
    if whole is not None:
        limbs.update({bone: whole for bone in turn.rubber})
    seen.limbs = limbs
    seen._sized, seen._turned, seen._standing = {}, {}, None
    return seen


def _turned(doll: Doll, turn: BodyTurn, yaw: float, depth: float, side: float = 90.0) -> Doll:
    """A doll with its trunk turned, no further round than from its side."""
    solid = solid_of(doll, turn.trunk) if abs(yaw) >= 1e-6 else None
    made = _of_rubber(doll, turn, solid, yaw, depth, side)
    limb = made[0] if made is not None else None
    if solid is None and limb is None:
        return doll
    other = copy.copy(doll)
    other.parts = dict(doll.parts)
    if solid is not None:
        for bone in turn.trunk:
            if bone not in doll.parts or bone not in doll.template.parts:
                continue
            part, corner = doll.parts[bone], _corner(doll, bone)
            if made is not None and bone in turn.rubber:
                # It is of the picture that was wrapped as one: the rows of that it was drawn
                # in. Each row is wrapped by itself, so they are the rows it would have been
                # wrapped to, and the trunk is gone round once and not once for each part too.
                _, seen, (_, top) = made
                rows = pygame.Rect(0, corner[1] - top, seen.image.get_width(), part.image.get_height()).clip(seen.image.get_rect())
                if rows.height == part.image.get_height():
                    other.parts[bone] = DollPart(seen.image.subsurface(rows).copy(), (seen.start[0], part.start[1]), (seen.start[0], part.end[1]))
                    continue
            other.parts[bone] = wrapped(part, yaw, depth, side, solid, corner)
    if limb is not None:
        other.limbs = {**doll.limbs, **{bone: limb for bone in turn.rubber}}
        other.drawn = {**doll.drawn, limb.bones[0]: doll.drawn[turn.rubber[0]]}
    other._sized, other._turned, other._standing = {}, {}, None
    return other


def half_width(doll: Doll, bone: str) -> float:
    """How far out to either side of its joints a part of a doll goes, in the skeleton's own measure."""
    part = doll.parts.get(bone)
    if part is None:
        return 0.0
    box = part.image.get_bounding_rect()
    axis = (part.start[0] + part.end[0]) / 2.0
    return max(0.0, axis - box.left, box.right - axis) / doll.unit


def fronted(template: DollTemplate, drawing: pygame.Surface, trunk: Sequence[str], depth: float) -> pygame.Surface:
    """A drawing of a body whose trunk is seen from its side, with that trunk made into one seen
    from the front: at every height the same to either side of its middle, and as much wider as
    a trunk is wider than it is deep. It is what the plain figure is turned into to be drawn
    over, since a trunk is to be drawn from the front. Wrapped and seen from its side again it
    is as wide as it was."""
    bones = [
        bone for bone in trunk
        if bone in template.parts and template.canvases[template.parts[bone].canvas] == drawing.get_size()
    ]
    if not bones or not 0.0 < depth < 1.0:
        return drawing
    theirs = pygame.Mask(drawing.get_size())
    for bone in bones:
        theirs.draw(pygame.mask.from_surface(template.cut_mask(bone, drawing)), (0, 0))
    only = drawing.copy()
    only.blit(theirs.to_surface(setcolor=(255, 255, 255, 255), unsetcolor=(255, 255, 255, 0)), (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
    box = only.get_bounding_rect()
    if not box.width:
        return drawing
    # Nothing is left where the trunk was, colour or all: its rows are added to nothing.
    rest = drawing.copy()
    rest.blit(theirs.to_surface(setcolor=(255, 255, 255, 255), unsetcolor=(0, 0, 0, 0)), (0, 0), special_flags=pygame.BLEND_RGBA_SUB)
    middle = template.parts[bones[0]].start[0]
    for y in range(box.top, box.bottom):
        row = only.subsurface((box.left, y, box.width, 1))
        span = row.get_bounding_rect()
        if not span.width:
            continue
        wide = max(1, round(span.width / depth))
        # Added to nothing, a row is copied as it is, the line at either end of it and all.
        rest.blit(
            pygame.transform.scale(row.subsurface(span), (wide, 1)), (round(middle - wide / 2), y),
            special_flags=pygame.BLEND_RGBA_ADD,
        )
    return rest
