"""Limbs of rubber: a strip of a drawing laid along a curve, in place of parts pinned at a joint.

A limb drawn in one line, such as an arm from the shoulder to the wrist, is bent as one piece. The
joints it has on the skeleton are not corners: the line down its middle rounds each of them off,
and the drawing follows that line, drawn out on the outside of a bend and gathered on the inside.
Both ends stay where the skeleton has them, pointing the way their bones do.

What hangs from the far end of a limb, a hand or a foot, is not bent: a shoe is no hose, and
laid along a curve it comes out of shape. It keeps its shape and turns about the joint it hangs
from, whichever way it was drawn pointing. Only a narrow band either side of that joint gives,
turning a little more the further along it is, so that the limb goes into it with no cut.

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
# Of the band that gives where a hand or a foot hangs from a limb, the share that is on the hand
# or the foot itself, against what is on the limb: most of it is on the limb.
GIVE_PAST = 1 / 3
# Pixels by which the part of a limb that bends goes on under the picture of its hand or foot.
OVERLAP = 2.0
# A drawing no finer than this, against the picture it is bent into, is looked at four times to
# a pixel where it is turned whole, so that no pixel of the picture is left out.
COARSE = 1.5

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
class Tip:
    """What hangs from the far end of a limb and keeps its shape: a hand, a foot.

    It is everything on the drawing past the joint it hangs from, at places all over it: where
    each is from that joint, how far past the joint, and what is drawn there.
    """

    # Which way it was drawn pointing, how long it is, and how far back up the limb the joint
    # gives, all in pixels of the drawing.
    way: Point
    long: float
    give: float
    at_x: Any
    at_y: Any
    past: Any
    taken: Any
    # How far from the joint the furthest of it is.
    reach: float


@dataclass(frozen=True)
class Strip:
    """A limb as it was drawn, as numbers, and where its joints are on it.

    Each pixel is its red, green and blue, each times how solid it is, and how solid it is from
    0 to 1. There is a clear pixel all round. The joints are those of the parts that bend, in
    pixels of the picture, from the one nearest the trunk outwards, and lie in one line.
    """

    pixels: Any
    joints: tuple[Point, ...]
    # Pixels of this picture to one of the picture a limb is bent into.
    fine: float
    rounding: float
    # How long each part is, how far the picture goes on before the first joint and after the
    # last, and how far to either side of the line through its joints it is painted.
    drawn: tuple[float, ...]
    before: float
    after: float
    reach: float
    tip: Tip | None = None


def read_strip(
    image: pygame.Surface, joints: Sequence[Point], rounding: float = 1.0, fine: float = 1.0, give: float | None = None
) -> Strip | None:
    """A picture of a limb, ready to be bent. None if its joints leave it a part of no length.

    With `give`, the last two joints are those of a hand or a foot that hangs from the limb and
    keeps its shape, and `give` is how much of its own length the limb gives, back from where
    it hangs, to go into it without a cut.
    """
    width, height = image.get_size()
    pixels = np.zeros((width + 2, height + 2, 4), np.float32)
    solid = pygame.surfarray.array_alpha(image).astype(np.float32) / 255
    pixels[1:-1, 1:-1, :3] = pygame.surfarray.array3d(image) * solid[..., None]
    pixels[1:-1, 1:-1, 3] = solid
    joints = tuple(joints)
    hangs = give is not None and len(joints) > 2
    bends = joints[:-1] if hangs else joints
    drawn = tuple(math.dist(start, end) for start, end in zip(bends, bends[1:]))
    if len(bends) < 2 or min(drawn) <= 0:
        return None
    way = _heading(bends[0], bends[-1])
    side = (-way[1], way[0])
    painted_x, painted_y = np.nonzero(solid > 0)
    along = (painted_x + 0.5 - bends[0][0]) * way[0] + (painted_y + 0.5 - bends[0][1]) * way[1]
    aside = (painted_x + 0.5 - bends[0][0]) * side[0] + (painted_y + 0.5 - bends[0][1]) * side[1]
    long = sum(drawn)
    # Past the joint a hand or a foot hangs from, everything is the hand's or the foot's.
    own = along <= long if hangs else np.ones(len(along), bool)
    if not own.any():
        return None
    before = max(0.0, float(-along[own].min()))
    after = 0.0 if hangs else max(0.0, float(along.max()) - long)
    reach = float(np.abs(aside[own]).max()) + 1.0
    tip = None
    if hangs and (~own).any():
        end, far = bends[-1], joints[-1]
        every = [(0.5, 0.5)] if fine >= COARSE else [(0.25, 0.25), (0.75, 0.25), (0.25, 0.75), (0.75, 0.75)]
        at_x = np.concatenate([painted_x[~own] + x - end[0] for x, _ in every])
        at_y = np.concatenate([painted_y[~own] + y - end[1] for _, y in every])
        taken = np.concatenate([pixels[painted_x[~own] + 1, painted_y[~own] + 1]] * len(every))
        tip = Tip(
            _heading(end, far), math.dist(end, far), give * math.dist(end, far),
            at_x, at_y, at_x * way[0] + at_y * way[1], taken, float(np.hypot(at_x, at_y).max()),
        )
    return Strip(pixels, bends, fine, rounding, drawn, before, after, reach, tip)


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
    open_end: bool = True,
    straight: float = 0.0,
) -> list[_Section] | None:
    """The line down the middle of a limb whose joints are at `points`, a section to each part.

    `drawn` is how long each part is on the drawing, and `before` and `after` how far the drawing
    goes on past its first joint and past its last. `rest` is how long each part is when nothing
    squashes it or draws it out, if that is not as long as it was drawn. With no `open_end`
    something hangs from the last joint: the line stops there, the last `straight` of it is
    left straight, and the limb is as wide there as it was drawn, whatever it is further up.
    None for a limb with a part of no length.
    """
    count = len(points) - 1
    rounds: dict[int, tuple[Point, Point, Point]] = {}
    for joint in range(1, count):
        # A part with a joint at each end gives half of itself to the round of each.
        back = min(rounding / 2, 1.0 if joint == 1 else 0.5)
        ahead = min(rounding / 2, 1.0 if joint == count - 1 else 0.5)
        here = points[joint]
        if not open_end and joint == count - 1:
            long = math.dist(here, points[joint + 1])
            ahead = min(ahead, max(0.0, 1.0 - straight / long)) if long > 0 else 0.0
        rounds[joint] = (_between(here, points[joint - 1], back), here, _between(here, points[joint + 1], ahead))
    # Where along each round the joint itself comes: half-way if it takes as much of the part
    # before as of the part after, and nearer the shorter side if not. On a limb held straight
    # that is exactly where the joint is, so what is drawn at an elbow stays at the elbow.
    joined = {}
    for joint, (start, here, end) in rounds.items():
        before_it, after_it = math.sqrt(math.dist(start, here)), math.sqrt(math.dist(here, end))
        joined[joint] = before_it / (before_it + after_it) if before_it + after_it > 0 else 0.5
    lines: list[list[Point]] = []
    for part in range(count):
        line = [points[0]] if part == 0 else _curve(*rounds[part], joined[part], 1.0)
        line += [points[count]] if part == count - 1 else _curve(*rounds[part + 1], 0.0, joined[part + 1])
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
        elif open_end:
            way, far = _heading(line[-2], line[-1]), (after + MARGIN) * wides[part]
            line = [*line, (line[-1][0] + way[0] * far, line[-1][1] + way[1] * far)]
            along, wide = [*along, along[-1] + after + MARGIN], [*wide, wides[part]]
        else:
            wide[-1] = 1.0
        begun += drawn[part]
        sections.append(_Section(np.array(line, np.float64), np.array(along, np.float64), np.array(wide, np.float64)))
    return sections


def _spread(section: _Section, reach: float, crowded: float = 1.0) -> tuple[Any, ...]:
    """Places all along a section, near enough to one another that nothing is left out between
    them even on the outside of a bend. `crowded` has them that many times nearer still.

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
    crowd = (1 + reach * section.wide * np.abs(turning)) * crowded / STEP
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


def _given(past: Any, give: float) -> Any:
    """How much of the turn of a hand or a foot each place takes, by how far past the joint it is:
    none of it well back up the limb, all of it a little way into the hand, and smoothly between."""
    share = np.clip((past + give) / (give * (1 + GIVE_PAST)), 0.0, 1.0) if give > 0 else (past > 0).astype(float)
    return share * share * (3 - 2 * share)


def _laid(to_x: Any, to_y: Any, taken: Any, left: int, top: int, size: tuple[int, int]) -> Any:
    """A layer of a picture: at each of its pixels, the middle of whatever lands there."""
    count = size[0] * size[1]
    where = (
        np.clip((to_x - left).astype(np.intp), 0, size[0] - 1) * size[1]
        + np.clip((to_y - top).astype(np.intp), 0, size[1] - 1)
    ).ravel()
    landed = np.maximum(np.bincount(where, minlength=count), 1)
    each = (where[:, None] * 4 + np.arange(4)).ravel()
    return np.bincount(each, weights=taken.reshape(-1), minlength=count * 4).reshape(count, 4) / landed[:, None]


def _picture(seen: Any, size: tuple[int, int]) -> pygame.Surface:
    """A picture out of its pixels, their colours each times how solid they are."""
    seen = seen.reshape(size[0], size[1], 4)
    picture = pygame.Surface(size, pygame.SRCALPHA)
    pixels = pygame.surfarray.pixels3d(picture)
    pixels[:] = np.clip(_colors(seen) + 0.5, 0, 255).astype(np.uint8)
    del pixels
    pixels = pygame.surfarray.pixels_alpha(picture)
    pixels[:] = np.clip(seen[..., 3] * 255 + 0.5, 0, 255).astype(np.uint8)
    del pixels
    return picture


def bent(
    strip: Strip, points: Sequence[Point], volume: float = 0.0, rest: Sequence[float] | None = None
) -> tuple[pygame.Surface, Point] | None:
    """The part of a limb that bends, laid along its joints, and where on that picture the first
    of them is.

    `points` are those joints in pixels of the picture, wherever they are. `volume` is how much
    wider a limb gets for being shorter than it is at rest: not at all at 0, enough to take up
    as much room as before at 1. `rest` is how long each of its parts is at rest, in pixels of
    the picture, if that is not as long as it was drawn. If a hand or a foot hangs from the limb
    this stops short of it, where the joint begins to give: `tipped` is the rest of it. None if
    the limb cannot be laid out.
    """
    joints, fine, tip = strip.joints, strip.fine, strip.tip
    if len(points) != len(joints):
        return None
    width, height = strip.pixels.shape[0] - 2, strip.pixels.shape[1] - 2
    way = _heading(joints[0], joints[-1])
    side = (-way[1], way[0])
    # Everything from here on is in pixels of the picture, but for what is said to be the strip's.
    drawn = [long / fine for long in strip.drawn]
    reach = strip.reach / fine
    give = tip.give / fine if tip is not None else 0.0
    sections = _lay(points, drawn, strip.rounding, volume, strip.before / fine, strip.after / fine, rest, tip is None, give)
    if sections is None:
        return None
    widest = max(float(section.wide.max()) for section in sections)
    room = reach * widest + MARGIN
    every = np.concatenate([section.corners for section in sections])
    left, top = math.floor(float(every[:, 0].min()) - room), math.floor(float(every[:, 1].min()) - room)
    size = (math.ceil(float(every[:, 0].max()) + room) - left, math.ceil(float(every[:, 1].max()) + room) - top)
    if size[0] * size[1] > LARGEST:
        return None
    across = np.arange(-reach, reach + STEP, STEP / widest)
    # Where on the strip each place across the limb is, from the place along it: a clear pixel
    # comes before the first of the drawing, and whatever falls outside it is given one.
    over_x, over_y = side[0] * across * fine, side[1] * across * fine
    seen = np.zeros((size[0] * size[1], 4))
    for section in sections:
        at_x, at_y, aside_x, aside_y, along, wide, turning = _spread(section, reach)
        if tip is not None:
            # It goes a little way into what the other picture shows, where the joint has barely
            # begun to give and the two are alike: laid one over the other, no line shows between.
            mine = along <= sum(drawn) - give + min(give, OVERLAP)
            at_x, at_y, aside_x, aside_y, along, wide, turning = (
                each[mine] for each in (at_x, at_y, aside_x, aside_y, along, wide, turning)
            )
            if not len(along):
                continue
        # On the inside of a bend everything would cross over at its middle: it stops short of it.
        inmost = INMOST / np.maximum(np.abs(turning), 1e-9)
        aside = np.clip(
            across[None, :] * wide[:, None],
            np.where(turning < 0, -inmost, -np.inf)[:, None],
            np.where(turning > 0, inmost, np.inf)[:, None],
        )
        from_x = (joints[0][0] + 1 + way[0] * along * fine)[:, None] + over_x[None, :]
        from_y = (joints[0][1] + 1 + way[1] * along * fine)[:, None] + over_y[None, :]
        taken = strip.pixels[
            np.clip(from_x, 0, width + 1).astype(np.intp), np.clip(from_y, 0, height + 1).astype(np.intp)
        ]
        layer = _laid(at_x[:, None] + aside_x[:, None] * aside, at_y[:, None] + aside_y[:, None] * aside, taken, left, top, size)
        # A part further along the limb goes over the one before it.
        seen = layer + seen * (1 - layer[:, 3:4])
    return _picture(seen, size), (points[0][0] - left, points[0][1] - top)


def tipped(strip: Strip, lean: float, drawn_out: float = 1.0) -> tuple[pygame.Surface, Point] | None:
    """The hand or the foot at the end of a limb, with the end of the limb that gives to it, and
    where on that picture the joint it hangs from is.

    It is as it was drawn, the limb pointing the way it does on the drawing, but for how it is
    turned: `lean` is how far it points from the way the end of the limb does, in radians, as
    the hands of a clock go on the screen. On the drawing it may already be turned so, as a foot
    is. `drawn_out` is how many times as long as it was drawn it is. Up to the joint the limb
    turns a little further the nearer it comes, and so does the hand a little way in: no cut.
    None for a limb nothing hangs from.
    """
    tip, fine = strip.tip, strip.fine
    if tip is None:
        return None
    joints = strip.joints
    width, height = strip.pixels.shape[0] - 2, strip.pixels.shape[1] - 2
    way = _heading(joints[0], joints[-1])
    side = (-way[1], way[0])
    angle = lambda heading: math.atan2(heading[1], heading[0])
    turn = (lean - (angle(tip.way) - angle(way)) + math.pi) % math.tau - math.pi
    reach, give, long = strip.reach / fine, tip.give / fine, sum(strip.drawn)
    around = math.ceil(max(tip.reach / fine * max(1.0, drawn_out), math.hypot(give, reach)) + MARGIN)
    size = (around * 2, around * 2)
    seen = np.zeros((size[0] * size[1], 4))
    if give > 0:
        # The end of the limb, as far back as it gives: the nearer the joint, the further it
        # turns about it. Its outside is drawn out by that, and is looked at the more closely.
        crowded = 1 + reach * abs(turn) * 1.5 / (give * (1 + GIVE_PAST))
        past = np.linspace(-give, 0.0, max(2, math.ceil(give * crowded / STEP) + 1))
        across = np.arange(-reach, reach + STEP, STEP)
        given = (_given(past * fine, tip.give) * turn)[:, None]
        off_x = way[0] * past[:, None] + side[0] * across[None, :]
        off_y = way[1] * past[:, None] + side[1] * across[None, :]
        from_x = (joints[0][0] + 1 + way[0] * (long + past * fine))[:, None] + side[0] * across[None, :] * fine
        from_y = (joints[0][1] + 1 + way[1] * (long + past * fine))[:, None] + side[1] * across[None, :] * fine
        taken = strip.pixels[
            np.clip(from_x, 0, width + 1).astype(np.intp), np.clip(from_y, 0, height + 1).astype(np.intp)
        ]
        seen = _laid(
            off_x * np.cos(given) - off_y * np.sin(given), off_x * np.sin(given) + off_y * np.cos(given),
            taken, -around, -around, size,
        )
    # The hand or the foot, whole. What lies along it is drawn out with it.
    off_x, off_y = tip.at_x / fine, tip.at_y / fine
    longer = np.maximum(off_x * tip.way[0] + off_y * tip.way[1], 0.0) * (drawn_out - 1.0)
    off_x, off_y = off_x + longer * tip.way[0], off_y + longer * tip.way[1]
    given = _given(tip.past, tip.give) * turn
    layer = _laid(
        off_x * np.cos(given) - off_y * np.sin(given), off_x * np.sin(given) + off_y * np.cos(given),
        tip.taken, -around, -around, size,
    )
    seen = layer + seen * (1 - layer[:, 3:4])
    return _picture(seen, size), (float(around), float(around))
