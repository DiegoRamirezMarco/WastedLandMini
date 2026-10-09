"""Armour cut to whoever wears it: a piece drawn once over the plain figure, laid over any body.

A piece is drawn on a doll's own paper, over the plain figure with the measures every doll starts
from. What matters of each pixel of it is not where on the paper it is but where on the body: how
far along its part, from one joint to the next, and how far from the skin. Put on somebody, it is
laid out anew on their paper by that. It is as long as their part is. Over the skin it is as wide
as they are, and past the skin it is about as thick as it was drawn: a little thinner on a thin
body and thicker on a stout one, and less where their body leaves it no room in the part's zone.

A head is everything drawn on its paper and has no joints to go by. A piece on it goes by the way
from the middle of the head instead, and by how far out the head reaches that way.

What comes of it is a drawing like any other, laid over the body's own and cut with it into one
doll: it bends, turns and grows as the body does, at no cost of its own. Where nothing of a part
is drawn there is nothing to wear a piece on, and none of it is seen there.

This needs numpy. Without it nobody is seen to wear anything.
"""

import json
import math
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

import pygame

from graphics.doll import Doll, DollBuild, DollTemplate, Garment, PartSpec
from graphics.doll_guide import piece_zone, reference

try:
    import numpy as np
except ImportError:  # No numpy: a doll is as it was drawn.
    np = None

AVAILABLE = np is not None
# How far along a part its width is evened out over, either way, as a share of the template's unit:
# a piece goes by the shape of a body and not by every stroke of its outline.
EVEN = 0.4
# A part is taken to be at least this wide, in pixels, however thin it was drawn.
THINNEST_PART = 2.0
# Past the skin a piece is as thick as it was drawn, times how many times as wide as the figure's
# their part is, to this power: not at all at 0, all the way at 1. And never more or less than
# these shares of the thickness it was drawn with, however odd their body or little the room.
FOLLOWS = 0.5
THICKEST, THINNEST = 1.6, 0.15
# A head is looked at in this many steps of a full turn, and how far out it reaches is evened out
# over this many of them either way: a helmet goes by the head and not by every lock of its hair.
ROUND_STEPS = 72
ROUND_EVEN = 4
# The places within each pixel of a piece laid out anew that the drawing is looked at, so that a
# line of it made smaller is thinner and not gone.
WITHIN = ((0.25, 0.25), (0.75, 0.25), (0.25, 0.75), (0.75, 0.75))
# Pixels round where a piece was painted within which it is looked at.
BESIDE = 2.0
# Two parts run on in one line if the ways they point are this much alike, or this much opposed.
IN_LINE = 0.999


def _solid(surface: pygame.Surface) -> Any:
    """How solid each pixel of a picture is, from 0 to 1."""
    try:
        seen = pygame.surfarray.pixels_alpha(surface)
    except ValueError:  # A picture with nothing clear in it.
        seen = pygame.surfarray.array_alpha(surface)
    solid = seen.astype(np.float32) / 255
    del seen
    return solid


def _pixels(surface: pygame.Surface, own: Any) -> Any:
    """What of a picture is in a place, as numbers, with a clear pixel all round: red, green and
    blue each times how solid the pixel is, and how solid it is."""
    width, height = surface.get_size()
    solid = _solid(surface) * own
    pixels = np.zeros((width + 2, height + 2, 4), np.float32)
    pixels[1:-1, 1:-1, :3] = pygame.surfarray.array3d(surface) * solid[..., None]
    pixels[1:-1, 1:-1, 3] = solid
    return pixels


def _taken(pixels: Any, x: Any, y: Any) -> Any:
    """What a picture has at places on it, mixed from the four pixels round each. Nothing off it."""
    width, height = pixels.shape[0] - 2, pixels.shape[1] - 2
    # A pixel's middle is half-way across it, and the picture begins one pixel in.
    x, y = x + 0.5, y + 0.5
    off = (x < 0) | (x > width + 1) | (y < 0) | (y > height + 1)
    x, y = np.clip(x, 0, width + 1 - 1e-6), np.clip(y, 0, height + 1 - 1e-6)
    left, top = np.floor(x).astype(np.intp), np.floor(y).astype(np.intp)
    across, down = (x - left)[..., None].astype(np.float32), (y - top)[..., None].astype(np.float32)
    taken = (pixels[left, top] * (1 - across) + pixels[left + 1, top] * across) * (1 - down) + (
        pixels[left, top + 1] * (1 - across) + pixels[left + 1, top + 1] * across
    ) * down
    taken[off] = 0.0
    return taken


def _painted_box(pixels: Any) -> tuple[float, float, float, float] | None:
    """The box round what is painted of a picture, and a little more. None if nothing is."""
    xs, ys = np.nonzero(pixels[1:-1, 1:-1, 3] > 0)
    if not len(xs):
        return None
    return (xs.min() - BESIDE, ys.min() - BESIDE, xs.max() + 1 + BESIDE, ys.max() + 1 + BESIDE)


def _picture(seen: Any) -> pygame.Surface:
    """A picture out of its pixels, their colours each times how solid they are."""
    picture = pygame.Surface(seen.shape[:2], pygame.SRCALPHA)
    solid = seen[..., 3:]
    colors = np.where(solid > 0, seen[..., :3] / np.maximum(solid, 1e-6), 0.0)
    pixels = pygame.surfarray.pixels3d(picture)
    pixels[:] = np.clip(colors + 0.5, 0, 255).astype(np.uint8)
    del pixels
    pixels = pygame.surfarray.pixels_alpha(picture)
    pixels[:] = np.clip(seen[..., 3] * 255 + 0.5, 0, 255).astype(np.uint8)
    del pixels
    return picture


def _filled(values: Any, around: bool = False) -> Any:
    """Numbers in a row with those that are missing taken from the ones either side. `around`
    says the row goes round and meets itself. None if every one of them is missing."""
    known = np.nonzero(np.isfinite(values))[0]
    if not len(known):
        return None
    places = np.arange(len(values))
    if around:
        return np.interp(places, known, values[known], period=len(values))
    return np.interp(places, known, values[known])


def _evened(values: Any, by: int, around: bool = False, most: bool = False) -> Any:
    """Numbers in a row, each made the middle of those within `by` of it either way, or with
    `most` the largest of them."""
    if by < 1:
        return values
    if around:
        padded = np.concatenate((values[-by:], values, values[:by]))
    else:
        padded = np.concatenate((np.full(by, values[0]), values, np.full(by, values[-1])))
    if most:
        return np.max([padded[shift : shift + len(values)] for shift in range(2 * by + 1)], axis=0)
    return np.convolve(padded, np.ones(2 * by + 1) / (2 * by + 1), mode="valid")


def _thick(wide: Any, was_wide: Any, room: Any, past: Any) -> Any:
    """How many times as thick as it was drawn a piece is past the skin: by how wide the body is
    there against the figure, and no more than there is room for."""
    follows = (np.maximum(wide, 1e-6) / np.maximum(was_wide, 1e-6)) ** FOLLOWS
    fits = np.maximum(room, 0.0) / np.maximum(past, 1e-6)
    return np.clip(np.minimum(np.minimum(follows, THICKEST), fits), THINNEST, None)


class _Frame:
    """A part as something to measure along: where it starts, which way it runs, which way is
    across it, and how long it is."""

    def __init__(self, spec: PartSpec, beyond: int) -> None:
        dx, dy = spec.end[0] - spec.start[0], spec.end[1] - spec.start[1]
        self.long = math.hypot(dx, dy) or 1.0
        self.start = spec.start
        self.along = (dx / self.long, dy / self.long)
        self.across = (-self.along[1], self.along[0])
        # How far to either side its zone goes, and how far past its first joint and its second.
        self.reach, self.ends = spec.reach, spec.ends
        # The first place along it that is looked at, and how many pixels from there: all of the
        # part and `beyond` past either end, where what it runs on from is.
        self.first = math.floor(-spec.ends[0]) - 1 - beyond
        self.count = math.ceil(self.long + spec.ends[1]) + 2 + beyond - self.first

    def of(self, x: Any, y: Any) -> tuple[Any, Any]:
        """How far along the part and how far across it places on its paper are."""
        x, y = x - self.start[0], y - self.start[1]
        return x * self.along[0] + y * self.along[1], x * self.across[0] + y * self.across[1]

    def at(self, along: Any, across: Any) -> tuple[Any, Any]:
        """Where on its paper is so far along the part and so far across it."""
        return (
            self.start[0] + self.along[0] * along + self.across[0] * across,
            self.start[1] + self.along[1] * along + self.across[1] * across,
        )

    def places(self) -> Any:
        """How far along the part the middle of each of the pixels looked at is."""
        return self.first + 0.5 + np.arange(self.count)

    def sides(self, painted: Any) -> tuple[Any, Any]:
        """How far to either side of the part what is painted goes, pixel by pixel along it:
        nothing where there is none."""
        xs, ys = np.nonzero(painted)
        along, across = self.of(xs + 0.5, ys + 0.5)
        steps = np.floor(along).astype(np.intp) - self.first
        within = (steps >= 0) & (steps < self.count)
        low, high = np.full(self.count, np.inf), np.full(self.count, -np.inf)
        np.minimum.at(low, steps[within], across[within])
        np.maximum.at(high, steps[within], across[within])
        return low, high


@dataclass(frozen=True)
class _Skin:
    """Where the skin of a part is: how far to either side of it the body goes, all along it."""

    low: Any
    high: Any


class _Sheet:
    """One paper with something painted on it, as something to measure: somebody's body, or the
    plain figure a piece was drawn over."""

    def __init__(self, template: DollTemplate, canvas: str, solid: Any) -> None:
        self.template, self.canvas = template, canvas
        self.solid = solid
        self.painted = solid > 0
        self.even = max(1, round(template.unit * EVEN))
        self._own: dict[str, Any] = {}
        self._near: dict[tuple[str, ...], Any] = {}
        self._frames: dict[str, _Frame] = {}
        self._skins: dict[str, _Skin | None] = {}
        self._round: tuple[_Round | None] | None = None

    def own(self, bone: str) -> Any:
        """What of the paper is a part's own: where a piece on it may be."""
        if bone not in self._own:
            zone = piece_zone(self.template, (bone,)).to_surface(setcolor=(255, 255, 255, 255), unsetcolor=(0, 0, 0, 0))
            self._own[bone] = _solid(zone) > 0
        return self._own[bone]

    def frame(self, bone: str) -> _Frame:
        if bone not in self._frames:
            self._frames[bone] = _Frame(self.template.parts[bone], self.even)
        return self._frames[bone]

    def line(self, bone: str) -> tuple[str, ...]:
        """A part and those it runs on from or into in one line, as a thigh and its shin do."""
        parts = self.template.parts
        found, waiting = [bone], [bone]
        while waiting:
            spec = parts[waiting.pop()]
            way = self.frame(spec.bone).along
            for other, each in parts.items():
                if other in found or each.whole or each.canvas != spec.canvas:
                    continue
                onward = self.frame(other).along
                if {spec.start, spec.end} & {each.start, each.end} and abs(way[0] * onward[0] + way[1] * onward[1]) > IN_LINE:
                    found.append(other)
                    waiting.append(other)
        return tuple(sorted(found))

    def near(self, bone: str) -> Any:
        """What of the paper is the part's or that of the parts it is in line with."""
        line = self.line(bone)
        if line not in self._near:
            near = self.own(line[0]).copy()
            for other in line[1:]:
                near |= self.own(other)
            self._near[line] = near
        return self._near[line]

    def skin(self, bone: str) -> _Skin | None:
        """The skin of a part of the body, evened out. None if nothing of the part is drawn.

        It is measured a little past either end too, on whatever the part runs on from, so that
        two parts that meet at a joint have the same skin there.
        """
        if bone not in self._skins:
            found = None
            if (self.own(bone) & self.painted).any():
                low, high = self.frame(bone).sides(self.near(bone) & self.painted)
                # As far out as it goes anywhere near: where a part ends in a round, or has a
                # dent in it, a piece goes straight on over it.
                low = _evened(-_evened(-_filled(low), self.even, most=True), self.even)
                high = _evened(_evened(_filled(high), self.even, most=True), self.even)
                # However thin, it has some width for a piece to be as wide as.
                narrow = np.maximum(THINNEST_PART - (high - low), 0.0) / 2
                found = _Skin(low - narrow, high + narrow)
            self._skins[bone] = found
        return self._skins[bone]

    def round(self) -> "_Round | None":
        """All that is painted on the paper as something to measure round. None if nothing is."""
        if self._round is None:
            self._round = (_round(self.solid),)
        return self._round[0]


def _past(frame: _Frame, painted: Any, skin: _Skin, even: int) -> tuple[Any, Any]:
    """How far past the skin of the figure a piece goes to either side, all along a part: the
    most of it anywhere near, so that it is given room for all of it."""
    low, high = frame.sides(painted)
    under = np.where(np.isfinite(low), np.maximum(skin.low - low, 0.0), 0.0)
    over = np.where(np.isfinite(high), np.maximum(high - skin.high, 0.0), 0.0)
    return _evened(under, even, most=True), _evened(over, even, most=True)


def _lay_part(seen: Any, pixels: Any, drawn: _Sheet, worn: _Sheet, bone: str) -> None:
    """Lay what a piece has on one part of the figure over that part of somebody's body.

    `pixels` are the piece's, `drawn` the paper it was drawn on with the figure under it, and
    `worn` the paper of whoever wears it. What comes of it is put into `seen`, over what is there.
    """
    was_skin, skin = drawn.skin(bone), worn.skin(bone)
    box = _painted_box(pixels)
    if was_skin is None or skin is None or box is None:
        return
    was, now = drawn.frame(bone), worn.frame(bone)
    painted = pixels[1:-1, 1:-1, 3] > 0
    under, over = _past(was, drawn.near(bone) & painted, was_skin, drawn.even)
    was_at, now_at = was.places(), now.places()

    def across_there(along: Any, there: Any, across: Any) -> tuple[Any, Any, Any]:
        """How far across the part on the paper it was drawn on what is so far across theirs
        comes from, and how far to either side of theirs the piece goes there."""
        low, high = np.interp(along, now_at, skin.low), np.interp(along, now_at, skin.high)
        was_low, was_high = np.interp(there, was_at, was_skin.low), np.interp(there, was_at, was_skin.high)
        wide, was_wide = high - low, was_high - was_low
        below, above = np.interp(there, was_at, under), np.interp(there, was_at, over)
        thick_low, thick_high = _thick(wide, was_wide, now.reach + low, below), _thick(wide, was_wide, now.reach - high, above)
        aside = np.where(
            across > high,
            was_high + (across - high) / thick_high,
            np.where(across < low, was_low - (low - across) / thick_low, was_low + (across - low) * was_wide / np.maximum(wide, 1e-6)),
        )
        return aside, low - below * thick_low, high + above * thick_high

    # Past a joint, where a part ends in a round, it is as much longer as it is wider there: a
    # round stays a round. And no longer than the zone of the part has room for.
    xs, ys = np.nonzero(drawn.own(bone) & painted)
    reach = was.of(xs + 0.5, ys + 0.5)[0] if len(xs) else np.zeros(1)
    grown = []
    for joint, there, room, goes in ((0.0, 0.0, now.ends[0], -reach.min()), (now.long, was.long, now.ends[1], reach.max() - was.long)):
        _, low, high = across_there(joint, there, 0.0)
        was_wide = np.interp(there, was_at, was_skin.high + over) - np.interp(there, was_at, was_skin.low - under)
        wider = float(high - low) / max(float(was_wide), 1e-6)
        grown.append(max(min(wider, room / goes) if goes > 0 else wider, 1e-3))

    def from_where(x: Any, y: Any) -> tuple[Any, Any]:
        """Where on the paper the piece was drawn on what is at places on theirs comes from."""
        along, across = now.of(x, y)
        there = np.where(
            along < 0,
            along / grown[0],
            np.where(along > now.long, was.long + (along - now.long) / grown[1], along * was.long / now.long),
        )
        return was.at(there, across_there(along, there, across)[0])

    xs, ys = np.nonzero(worn.own(bone))
    # Only where something of the piece comes to is it worth looking closely.
    x, y = from_where(xs + 0.5, ys + 0.5)
    near = (x >= box[0]) & (x <= box[2]) & (y >= box[1]) & (y <= box[3])
    xs, ys = xs[near], ys[near]
    if not len(xs):
        return
    # A part wears what was painted on that part of the figure and on no other: on a body much
    # thinner than the figure, what is beside the part on its paper comes from far across the
    # other one, where another part may be.
    was_own = drawn.own(bone)
    width, height = was_own.shape
    laid = np.zeros((len(xs), 4), np.float32)
    for within_x, within_y in WITHIN:
        x, y = from_where(xs + within_x, ys + within_y)
        taken = _taken(pixels, x, y)
        column, row = np.floor(x).astype(np.intp), np.floor(y).astype(np.intp)
        on_paper = (column >= 0) & (column < width) & (row >= 0) & (row < height)
        taken[~(on_paper & was_own[np.clip(column, 0, width - 1), np.clip(row, 0, height - 1)])] = 0.0
        laid += taken
    laid /= len(WITHIN)
    # Before its first joint a part keeps only a round as wide as it is there, once it is cut:
    # whatever of the piece went past that would be left behind, or go with another part.
    along, across = now.of(xs + 0.5, ys + 0.5)
    _, low, high = across_there(0.0, 0.0, 0.0)
    laid[(along < 0) & (np.hypot(along, across) > max(-float(low), float(high)) + 1.0)] = 0.0
    seen[xs, ys] = laid + seen[xs, ys] * (1 - laid[:, 3:])


@dataclass(frozen=True)
class _Round:
    """A head, or whatever else is everything on its paper, as something to measure round: its
    middle, and how far out from there it reaches each way."""

    middle: tuple[float, float]
    reach: Any


def _ways(x: Any, y: Any, middle: tuple[float, float]) -> tuple[Any, Any]:
    """Which way from a middle places are, in steps of a full turn, and how far."""
    x, y = x - middle[0], y - middle[1]
    return (np.arctan2(y, x) + math.pi) / math.tau * ROUND_STEPS, np.hypot(x, y)


def _furthest(painted: Any, middle: tuple[float, float]) -> Any:
    """How far from a middle what is painted goes, each way: nothing where there is none."""
    xs, ys = np.nonzero(painted)
    way, far = _ways(xs + 0.5, ys + 0.5, middle)
    furthest = np.full(ROUND_STEPS, -np.inf)
    np.maximum.at(furthest, np.floor(way).astype(np.intp) % ROUND_STEPS, far)
    return np.where(np.isfinite(furthest), furthest, np.nan)


def _round(solid: Any) -> _Round | None:
    """A painted shape as something to measure round. None if nothing is painted."""
    xs, ys = np.nonzero(solid > 0)
    if not len(xs):
        return None
    middle = (float(xs.mean()) + 0.5, float(ys.mean()) + 0.5)
    reach = _filled(_furthest(solid > 0, middle), around=True)
    # As far out as it goes anywhere near that way, so that a helmet covers hair that stands up.
    reach = _evened(_evened(reach, ROUND_EVEN // 2, around=True, most=True), ROUND_EVEN, around=True)
    return _Round(middle, np.maximum(reach, THINNEST_PART))


def _to_edge(size: tuple[int, int], middle: tuple[float, float]) -> Any:
    """How far it is from a middle to the edge of its paper, each way."""
    angle = (np.arange(ROUND_STEPS) + 0.5) / ROUND_STEPS * math.tau - math.pi
    east, south = np.cos(angle), np.sin(angle)
    with np.errstate(divide="ignore", invalid="ignore"):
        across = np.where(east > 0, (size[0] - middle[0]) / east, np.where(east < 0, -middle[0] / east, np.inf))
        down = np.where(south > 0, (size[1] - middle[1]) / south, np.where(south < 0, -middle[1] / south, np.inf))
    return np.minimum(across, down)


def _each_way(values: Any, way: Any) -> Any:
    """What a row that goes round has at any place round it, between the two steps either side."""
    way = way - 0.5
    before = np.floor(way).astype(np.intp)
    share = way - before
    return values[before % ROUND_STEPS] * (1 - share) + values[(before + 1) % ROUND_STEPS] * share


def _lay_whole(seen: Any, pixels: Any, drawn: _Sheet, worn: _Sheet) -> None:
    """Lay a piece drawn over the head of the figure over somebody's head, whatever shape it is."""
    was, now = drawn.round(), worn.round()
    box = _painted_box(pixels)
    if was is None or now is None or box is None:
        return
    size = worn.solid.shape
    past = np.nan_to_num(_furthest(pixels[1:-1, 1:-1, 3] > 0, was.middle), nan=0.0)
    past = _evened(np.maximum(past - was.reach, 0.0), ROUND_EVEN, around=True, most=True)
    # Past the head it is about as thick as it was drawn, if their paper leaves it the room.
    thick = _thick(now.reach, was.reach, _to_edge(size, now.middle) - now.reach, past)

    def from_where(x: Any, y: Any) -> tuple[Any, Any]:
        way, far = _ways(x, y, now.middle)
        reach, was_reach = _each_way(now.reach, way), _each_way(was.reach, way)
        there = np.where(far > reach, was_reach + (far - reach) / _each_way(thick, way), far * was_reach / reach)
        turn = way / ROUND_STEPS * math.tau - math.pi
        return was.middle[0] + np.cos(turn) * there, was.middle[1] + np.sin(turn) * there

    xs, ys = np.indices(size)
    x, y = from_where(xs + 0.5, ys + 0.5)
    near = (x >= box[0]) & (x <= box[2]) & (y >= box[1]) & (y <= box[3])
    xs, ys = xs[near], ys[near]
    if not len(xs):
        return
    laid = np.zeros((len(xs), 4), np.float32)
    for within_x, within_y in WITHIN:
        laid += _taken(pixels, *from_where(xs + within_x, ys + within_y))
    laid /= len(WITHIN)
    seen[xs, ys] = laid + seen[xs, ys] * (1 - laid[:, 3:])


class Tailor:
    """Lays pieces drawn over the plain figure over anybody's body."""

    def __init__(self, base: DollTemplate) -> None:
        # The template every doll starts from: a piece says by its measures how the figure it
        # was drawn over stood on it.
        self.base = base
        self._figures: dict[tuple[str, str], _Sheet] = {}

    def _figure(self, build: DollBuild, canvas: str) -> _Sheet:
        """The paper a piece was drawn on, with the plain figure that was under it."""
        key = (canvas, json.dumps(build.to_data(), sort_keys=True))
        if key not in self._figures:
            template = self.base.built(build)
            self._figures[key] = _Sheet(template, canvas, _solid(reference(template, canvas)))
        return self._figures[key]

    def bodies(self, template: DollTemplate, drawings: dict[str, pygame.Surface]) -> dict[str, _Sheet]:
        """Somebody's drawings as something to lay pieces over: measured once, for all they wear."""
        return {canvas: _Sheet(template, canvas, _solid(drawing)) for canvas, drawing in drawings.items()} if AVAILABLE else {}

    def fitted(self, garment: Garment, bodies: dict[str, _Sheet]) -> dict[str, pygame.Surface]:
        """A piece laid out for somebody: its drawings on their paper, by canvas. Nothing for a
        canvas they have no drawing on, or that the piece has nothing on."""
        found: dict[str, pygame.Surface] = {}
        for canvas, worn in bodies.items():
            piece = garment.drawings.get(canvas)
            template = worn.template
            bones = [
                bone for bone in template.worn_on(garment.slot)
                if bone in self.base.parts and template.parts[bone].canvas == canvas
            ]
            if piece is None or not bones or piece.get_size() != template.canvases[canvas]:
                continue
            drawn = self._figure(garment.build, canvas)
            # Whatever of it is painted where the slot has no part is nobody's to wear.
            may = np.zeros(worn.solid.shape, bool)
            for bone in bones:
                may |= True if template.parts[bone].whole else drawn.own(bone)
            pixels = _pixels(piece, may)
            seen = np.zeros((*worn.solid.shape, 4), np.float32)
            for bone in bones:
                if template.parts[bone].whole:
                    _lay_whole(seen, pixels, drawn, worn)
                else:
                    _lay_part(seen, pixels, drawn, worn, bone)
            found[canvas] = _picture(seen)
        return found

    def dressed(
        self, template: DollTemplate, drawings: dict[str, pygame.Surface], garments: Sequence[Garment]
    ) -> dict[str, pygame.Surface]:
        """Somebody's drawings with pieces on: each laid over their body, and over the pieces
        that go under it. The drawings they came with are left as they were."""
        order = [slot.slot_id for slot in self.base.wear]
        worn = sorted((piece for piece in garments if piece.slot in order), key=lambda piece: order.index(piece.slot))
        sheets = dict(drawings)
        # Every piece goes by the body, and not by what else is worn over it.
        bodies = self.bodies(template, drawings)
        for garment in worn:
            for canvas, laid in self.fitted(garment, bodies).items():
                if sheets[canvas] is drawings[canvas]:
                    sheets[canvas] = drawings[canvas].copy()
                sheets[canvas].blit(laid, (0, 0))
        return sheets

    def dress(self, doll: Doll, garments: Sequence[Garment]) -> Doll:
        """A doll with pieces on: cut from its own drawings with theirs over them."""
        return Doll(doll.template, self.dressed(doll.template, doll.sheets, garments), doll.plan)
