"""Limbs of rubber: a strip of a drawing laid along a curve, in place of parts pinned at a joint.

A limb drawn in one line, such as an arm from the shoulder to the wrist, is bent as one piece. The
joints it has on the skeleton are not corners: the line down its middle rounds each of them off,
and the drawing follows that line, drawn out on the outside of a bend and gathered on the inside.
Both ends stay where the skeleton has them, pointing the way their bones do.

This needs numpy. Without it there are no limbs of rubber, and a doll is the jointed parts it was.
"""

import math
from collections import OrderedDict
from collections.abc import Hashable, Sequence
from dataclasses import dataclass
from typing import Any

import pygame

try:
    import numpy as np
except ImportError:  # No numpy: every limb stays in its parts.
    np = None

Point = tuple[float, float]

AVAILABLE = np is not None
# How many straight pieces the round of one joint is laid out in.
ROUND_PIECES = 16
# Pixels between the places a limb is looked at, along it and across it, to be put where it bends
# to. Nearer than seven tenths of one, no pixel of the picture is left with nothing on it.
STEP = 0.7
# Pixels left clear round a bent limb.
MARGIN = 2
# No limb is made wider or narrower than this for being shorter or longer than it was drawn.
WIDEST, NARROWEST = 1.6, 0.6
# On the inside of a bend nothing is put further in than this share of the way to its middle.
INMOST = 0.9
# A limb that would take more pixels than this is not bent: its joints are nowhere sensible.
LARGEST = 4_000_000


class Kept:
    """Pictures kept to be shown again. Once they take up too much, the longest unseen are let go."""

    def __init__(self, room: int) -> None:
        # Bytes of picture that may be kept.
        self.room = room
        self._held: OrderedDict[Hashable, tuple[Any, int]] = OrderedDict()
        self._taken = 0

    def __len__(self) -> int:
        return len(self._held)

    def get(self, key: Hashable) -> Any:
        held = self._held.get(key)
        if held is None:
            return None
        self._held.move_to_end(key)
        return held[0]

    def keep(self, key: Hashable, value: Any, size: int) -> Any:
        self._taken += size - self._held.pop(key, (None, 0))[1]
        self._held[key] = (value, size)
        while self._taken > self.room and len(self._held) > 1:
            _, (_, gone) = self._held.popitem(last=False)
            self._taken -= gone
        return value

    def clear(self) -> None:
        self._held.clear()
        self._taken = 0


class Allowance:
    """How much bending may be done in one frame, for whoever counts frames.

    Bending a limb to a shape it has not had yet takes a good deal longer than showing one that
    was kept. When many bodies take new shapes at once, as when the map is brought nearer, only
    so many are bent in a frame. The rest make do, for that frame, with the nearest shape they
    have had, so that no frame is kept waiting.
    """

    def __init__(self, a_frame: float = 4.0) -> None:
        # Milliseconds of bending to a frame, as near as it can be told beforehand.
        self.a_frame = a_frame
        self._left = a_frame

    def new_frame(self) -> None:
        self._left = self.a_frame

    def spend(self, detail: float) -> bool:
        """Whether one more limb may be bent in this frame, at so many pixels to one of the
        skeleton's. If it may, it is counted."""
        if self._left <= 0.0:
            return False
        self._left -= 0.3 + 0.026 * detail * detail
        return True


@dataclass(frozen=True)
class Strip:
    """A limb as it was drawn, as numbers, and where its joints are on it.

    Each pixel is its red, green and blue, each times how solid it is, and how solid it is from
    0 to 1. There is a clear pixel all round. The joints are in pixels of the picture, from the
    one nearest the trunk outwards, and lie in one line.
    """

    pixels: Any
    joints: tuple[Point, ...]


def read_strip(image: pygame.Surface, joints: Sequence[Point]) -> Strip:
    """A picture of a limb, ready to be bent."""
    width, height = image.get_size()
    pixels = np.zeros((width + 2, height + 2, 4), np.float32)
    solid = pygame.surfarray.array_alpha(image).astype(np.float32) / 255
    pixels[1:-1, 1:-1, :3] = pygame.surfarray.array3d(image) * solid[..., None]
    pixels[1:-1, 1:-1, 3] = solid
    return Strip(pixels, tuple(joints))


@dataclass(frozen=True)
class _Section:
    """The line down the middle of one part of a limb, in straight pieces from corner to corner.

    `along` is how far along the drawing each corner is, and `wide` how many times as wide as
    drawn the limb is there.
    """

    corners: Any
    along: Any
    wide: Any


def _between(start: Point, end: Point, share: float) -> Point:
    return (start[0] + (end[0] - start[0]) * share, start[1] + (end[1] - start[1]) * share)


def _curve(start: Point, corner: Point, end: Point, first: float, last: float) -> list[Point]:
    """Part of the round of a joint: a curve from `start` to `end` drawn towards the joint itself."""
    pieces = max(1, ROUND_PIECES // 2)
    found = []
    for index in range(pieces + 1):
        share = first + (last - first) * index / pieces
        rest = 1.0 - share
        found.append((
            rest * rest * start[0] + 2 * rest * share * corner[0] + share * share * end[0],
            rest * rest * start[1] + 2 * rest * share * corner[1] + share * share * end[1],
        ))
    return found


def _heading(start: Point, end: Point) -> Point:
    length = math.dist(start, end) or 1.0
    return ((end[0] - start[0]) / length, (end[1] - start[1]) / length)


def _lay(
    points: Sequence[Point],
    drawn: Sequence[float],
    rounding: float,
    volume: float,
    before: float,
    after: float,
    rest: Sequence[float] | None = None,
) -> list[_Section] | None:
    """The line down the middle of a limb whose joints are at `points`, a section to each part.

    `drawn` is how long each part is on the drawing, and `before` and `after` how far the drawing
    goes on past its first joint and past its last. `rest` is how long each part is when nothing
    squashes it or draws it out, if that is not as long as it was drawn. None for a limb with a
    part of no length.
    """
    count = len(points) - 1
    rounds: dict[int, tuple[Point, Point, Point]] = {}
    for joint in range(1, count):
        # A part with a joint at each end gives half of itself to the round of each.
        back = min(rounding / 2, 1.0 if joint == 1 else 0.5)
        ahead = min(rounding / 2, 1.0 if joint == count - 1 else 0.5)
        here = points[joint]
        rounds[joint] = (_between(here, points[joint - 1], back), here, _between(here, points[joint + 1], ahead))
    lines: list[list[Point]] = []
    for part in range(count):
        line = [points[0]] if part == 0 else _curve(*rounds[part], 0.5, 1.0)
        line += [points[count]] if part == count - 1 else _curve(*rounds[part + 1], 0.0, 0.5)
        line = [point for index, point in enumerate(line) if index == 0 or math.dist(point, line[index - 1]) > 1e-6]
        if len(line) < 2 or drawn[part] <= 0:
            return None
        lines.append(line)
    reaches = [[0.0] for _ in lines]
    for line, reach in zip(lines, reaches):
        for index in range(1, len(line)):
            reach.append(reach[-1] + math.dist(line[index - 1], line[index]))
    # Shorter than it is at rest, a part is that much wider, and the other way about.
    wides = [
        min(WIDEST, max(NARROWEST, (reach[-1] / long) ** -volume)) if volume and long > 0 else 1.0
        for reach, long in zip(reaches, rest if rest is not None else drawn)
    ]
    sections = []
    begun = 0.0
    for part, (line, reach) in enumerate(zip(lines, reaches)):
        along = [begun + far * drawn[part] / reach[-1] for far in reach]
        wide = [wides[part]] * len(line)
        if part > 0:
            wide[0] = (wides[part] + wides[part - 1]) / 2
        else:
            # The drawing goes on past the first joint, straight back the way the limb sets out.
            way, far = _heading(line[1], line[0]), (before + MARGIN) * wides[part]
            line = [(line[0][0] + way[0] * far, line[0][1] + way[1] * far), *line]
            along, wide = [-(before + MARGIN), *along], [wides[part], *wide]
        if part < count - 1:
            wide[-1] = (wides[part] + wides[part + 1]) / 2
        else:
            way, far = _heading(line[-2], line[-1]), (after + MARGIN) * wides[part]
            line = [*line, (line[-1][0] + way[0] * far, line[-1][1] + way[1] * far)]
            along, wide = [*along, along[-1] + after + MARGIN], [*wide, wides[part]]
        begun += drawn[part]
        sections.append(_Section(np.array(line, np.float64), np.array(along, np.float64), np.array(wide, np.float64)))
    return sections


def _spread(section: _Section, reach: float) -> tuple[Any, ...]:
    """Places all along a section, near enough to one another that nothing is left out between
    them even on the outside of a bend.

    For each: where it is, which way is to its side, how far along the drawing it is, how wide
    the limb is there, and how sharply the line is turning, to that side if more than nothing.
    """
    corners = section.corners
    piece = np.diff(corners, axis=0)
    long = np.hypot(piece[:, 0], piece[:, 1])
    far = np.concatenate(([0.0], np.cumsum(long)))
    heading = np.unwrap(np.arctan2(piece[:, 1], piece[:, 0]))
    # At a corner the line points halfway between the pieces that meet there, and turns by as
    # much as they differ over as far as they go on.
    facing = np.concatenate((heading[:1], (heading[:-1] + heading[1:]) / 2, heading[-1:]))
    turning = np.zeros(len(corners))
    turning[1:-1] = (heading[1:] - heading[:-1]) / ((long[:-1] + long[1:]) / 2)
    crowd = (1 + reach * section.wide * np.abs(turning)) / STEP
    filled = np.concatenate(([0.0], np.cumsum((crowd[:-1] + crowd[1:]) / 2 * long)))
    places = np.interp(np.linspace(0.0, filled[-1], max(2, math.ceil(filled[-1]) + 1)), filled, far)
    angle = np.interp(places, far, facing)
    return (
        np.interp(places, far, corners[:, 0]),
        np.interp(places, far, corners[:, 1]),
        -np.sin(angle),
        np.cos(angle),
        np.interp(places, far, section.along),
        np.interp(places, far, section.wide),
        np.interp(places, far, turning),
    )


def _colors(seen: Any) -> Any:
    """The colour of every pixel of a picture whose colours are each times how solid it is.

    What is clear right beside the picture is given the colour of the picture next to it. Turned
    or resized afterwards, its edge is then mixed with its own colour and not with black.
    """
    near = seen.copy()
    near[1:] += seen[:-1]
    near[:-1] += seen[1:]
    near[:, 1:] += seen[:, :-1]
    near[:, :-1] += seen[:, 1:]
    solid = seen[..., 3:]
    return np.where(
        solid > 0, seen[..., :3] / np.maximum(solid, 1e-6), near[..., :3] / np.maximum(near[..., 3:], 1e-6)
    )


def bent(
    strip: Strip,
    points: Sequence[Point],
    rounding: float = 1.0,
    volume: float = 0.0,
    fine: float = 1.0,
    rest: Sequence[float] | None = None,
) -> tuple[pygame.Surface, Point] | None:
    """A limb laid along its joints, and where on that picture the first of them is.

    `points` are the joints in pixels of the picture, wherever they are, and `fine` how many
    pixels of the strip go to one of those: a strip finer than the picture makes a smoother one.
    `rounding` is how much of the limb each bend takes up: none of it at 0, where a joint is a
    corner, and all of it at 2, where a limb of two parts is one curve. `volume` is how much
    wider a limb gets for being shorter than it is at rest: not at all at 0, enough to take up
    as much room as before at 1. `rest` is how long each of its parts is at rest, in pixels of
    the picture, if that is not as long as it was drawn. None if the limb cannot be laid out.
    """
    joints = strip.joints
    if len(points) != len(joints) or len(points) < 2:
        return None
    width, height = strip.pixels.shape[0] - 2, strip.pixels.shape[1] - 2
    way = _heading(joints[0], joints[-1])
    side = (-way[1], way[0])
    # Everything from here on is in pixels of the picture.
    drawn = [math.dist(joints[index], joints[index + 1]) / fine for index in range(len(joints) - 1)]
    corners = [((x - joints[0][0]) / fine, (y - joints[0][1]) / fine) for x in (0, width) for y in (0, height)]
    alongs = [x * way[0] + y * way[1] for x, y in corners]
    reach = max(abs(x * side[0] + y * side[1]) for x, y in corners)
    sections = _lay(
        points, drawn, rounding, volume, max(0.0, -min(alongs)), max(0.0, max(alongs) - sum(drawn)), rest
    )
    if sections is None:
        return None
    widest = max(float(section.wide.max()) for section in sections)
    room = reach * widest + MARGIN
    every = np.concatenate([section.corners for section in sections])
    left, top = math.floor(float(every[:, 0].min()) - room), math.floor(float(every[:, 1].min()) - room)
    size = (math.ceil(float(every[:, 0].max()) + room) - left, math.ceil(float(every[:, 1].max()) + room) - top)
    count = size[0] * size[1]
    if count > LARGEST:
        return None
    across = np.arange(-reach, reach + STEP, STEP / widest)
    # Where on the strip each place across the limb is, from the place along it: a clear pixel
    # comes before the first of the drawing, and whatever falls outside it is given one.
    over_x, over_y = side[0] * across * fine, side[1] * across * fine
    channels = np.arange(4)
    seen = np.zeros((count, 4))
    for section in sections:
        at_x, at_y, aside_x, aside_y, along, wide, turning = _spread(section, reach)
        # On the inside of a bend everything would cross over at its middle: it stops short of it.
        inmost = INMOST / np.maximum(np.abs(turning), 1e-9)
        aside = np.clip(
            across[None, :] * wide[:, None],
            np.where(turning < 0, -inmost, -np.inf)[:, None],
            np.where(turning > 0, inmost, np.inf)[:, None],
        )
        to_x = np.clip(((at_x - left)[:, None] + aside_x[:, None] * aside).astype(np.intp), 0, size[0] - 1)
        to_y = np.clip(((at_y - top)[:, None] + aside_y[:, None] * aside).astype(np.intp), 0, size[1] - 1)
        from_x = (joints[0][0] + 1 + way[0] * along * fine)[:, None] + over_x[None, :]
        from_y = (joints[0][1] + 1 + way[1] * along * fine)[:, None] + over_y[None, :]
        taken = strip.pixels[
            np.clip(from_x, 0, width + 1).astype(np.intp), np.clip(from_y, 0, height + 1).astype(np.intp)
        ]
        # A pixel is the middle of whatever lands on it, its four numbers side by side.
        where = (to_x * size[1] + to_y).ravel()
        landed = np.maximum(np.bincount(where, minlength=count), 1)
        each = (where[:, None] * 4 + channels).ravel()
        layer = np.bincount(each, weights=taken.reshape(-1), minlength=count * 4).reshape(count, 4) / landed[:, None]
        # A part further along the limb goes over the one before it.
        seen = layer + seen * (1 - layer[:, 3:4])
    seen = seen.reshape(size[0], size[1], 4)
    picture = pygame.Surface(size, pygame.SRCALPHA)
    pixels = pygame.surfarray.pixels3d(picture)
    pixels[:] = np.clip(_colors(seen) + 0.5, 0, 255).astype(np.uint8)
    del pixels
    pixels = pygame.surfarray.pixels_alpha(picture)
    pixels[:] = np.clip(seen[..., 3] * 255 + 0.5, 0, 255).astype(np.uint8)
    del pixels
    return picture, (points[0][0] - left, points[0][1] - top)
