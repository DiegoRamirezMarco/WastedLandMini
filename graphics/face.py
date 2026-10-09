"""What a head has on it: eyes, brows, a mouth, a nose, ears and hair, each drawn by itself and
put on the head where it goes.

A head is drawn with nothing on it. Every piece of a face is a picture of its own, drawn as it is
seen from the front, and has a place on the head for each way the head is turned: from the
front, three quarters on, and from the side. Turned any way between those it is somewhere
between them. So one drawing of each piece does for a head that turns, where a head drawn whole
is only ever seen the way it was drawn.

Where a piece goes from the front is for whoever draws it to say. Where it goes turned is worked
out from that until they say otherwise: the head is taken for something round, and what is on it
goes round with it. That is a first guess and no more, there to be put right by hand.

Which pieces there are, how large their paper is and how each goes round is data, in
`data/face.json`.

A face moves (`FaceLook`): its eyes shut, its mouth opens, and its brows and its mouth say how
whoever wears it feels. All of that is worked out from the one drawing of each piece: an eye
is brought down to a line, a mouth is made taller, a brow leans, the ends of a mouth go up or
down. An eye shut and a mouth open may be drawn too, each on a paper of its own, and where one
has been it is that and not the rule. How far each thing goes is data as well (`moves`).
"""

import copy
import json
import logging
import math
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any

import pygame

from graphics.doll import HEAD_CANVAS, Doll, DollPart

try:
    import numpy as _np
except ImportError:  # Without numpy a head that is two at once is a little dark at its edge.
    _np = None

logger = logging.getLogger(__name__)

Point = tuple[float, float]
Size = tuple[int, int]

FACE_PATH = Path(__file__).resolve().parent.parent / "data" / "face.json"
FACE_FILE = "face.json"
# The way a head is seen that every other is worked out from.
FRONT = "front"
# What tells the two of a pair apart: the one on the side that is still seen when the head has
# turned right round to its side, and the one that has gone round the back by then.
NEAR, FAR = "near", "far"
# How a piece goes round with the head. Flat on it, and the narrower the more it is seen edge
# on; standing out of it, and as wide from any side; out at its edge, as ears are; whole, a
# share of the head's width forwards or back, as hair in front of it and behind it does; or
# not at all.
FLAT, SOLID, EDGE, SHIFT, STILL = "flat", "solid", "edge", "shift", "still"
TURNS = (FLAT, SOLID, EDGE, SHIFT, STILL)
# How much of itself a piece that is not seen in a view is shown at where it is being put in place.
GHOST_ALPHA = 70
# Where hair that comes over a head ends, from the ear: how much further forwards at the top of
# the head, and at the foot of it, in halves of the head's width with the head seen from its
# side. It leans as a hairline does, forwards at the crown and back at the nape.
OVER_AT_TOP, OVER_AT_FOOT = 0.22, -0.42
# How much further back than that line hair in front of a head opens when the head is seen
# from the front, in halves of the head's width: from there nothing of it opens, and the
# opening comes in as the head turns, to be on the line itself when it is seen from its side.
SLACK_IN_FRONT = 0.35
# How far in from its edge a piece is taken to be line and not yet the colour inside it, in
# halves of the head's width. Where a piece opens on another, that much of the one under it is
# not shown through the opening unless its edge there is the edge of the two together: so no
# line of either is left inside them, and the line round both is whole.
EDGE_KEPT = 0.14
# Pixels past the line that hair behind a head comes over it by, under the hair in front, so
# that no sliver of bare head is left between the two.
UNDERLAP = 3
# What a part that is laid under the whole doll is called after the bone it goes with.
UNDER = "~under"
# Between how far round and how far round, in degrees, a head goes from being seen from its
# side to being seen from behind: by degrees, the one fading as the other comes. All at once,
# half way between, its hair jumped from in front of it to over the back of it.
BEHIND_FROM, BEHIND_BY = 97.5, 127.5
# And how far round for an ear to be drawn the other way about, as the one on that side of a
# head is: by then it is nearer the edge of the head than the middle of it.
EAR_TURNED_FROM = 135.0
# Hundredths of its width a piece is brought to: one picture is kept for each.
WIDTH_STEP = 4
NARROWEST, WIDEST = 0.2, 2.0
CLEAR = (0, 0, 0, 0)
# What a paper that stands for a piece moved one way is for: an eye shut, a mouth open.
SHUT, OPEN = "shut", "open"
# Which end of a brow as it is drawn is the one nearer the nose: its right, since the one
# drawn is the one on the left of the paper. A brow that leans has that end up.
INNER_END = 1.0


@dataclass(frozen=True)
class FaceLook:
    """What a face is doing: how far its eyes are shut and its mouth is open, each in so many
    steps from not at all, and how whoever wears it feels. Nothing of it said, it is the face
    as it was drawn."""

    lids: int = 0
    mouth: int = 0
    mood: str = ""

    def __bool__(self) -> bool:
        return bool(self.lids or self.mouth or self.mood)


@dataclass(frozen=True)
class Shift:
    """How a piece is moved to say how somebody feels: how far it leans, in degrees, the end
    nearer the nose up; how far up it goes, as a share of how tall its paper is; and how far
    its ends are bent down, the same way, its middle going up a third as far."""

    tilt: float = 0.0
    lift: float = 0.0
    bend: float = 0.0


@dataclass(frozen=True)
class FaceMoves:
    """How a face moves by rule. By kind of piece, how wide and how tall it is at each step
    of shutting and of opening, against how it was drawn; by feeling and by kind of piece,
    how it is moved; and which kinds of piece the face of a body nobody has drawn has."""

    shut: dict[str, tuple[tuple[float, float], ...]] = field(default_factory=dict)
    open: dict[str, tuple[tuple[float, float], ...]] = field(default_factory=dict)
    moods: dict[str, dict[str, Shift]] = field(default_factory=dict)
    plain: tuple[str, ...] = ()
    # What each feeling is called, where it is offered to be looked at.
    mood_names: dict[str, str] = field(default_factory=dict)
    # What a piece shut all the way is by rule, in place of itself brought down to nothing:
    # a line as wide as it was drawn, the darkest colour it has, so thick and sagging so far
    # in its middle, both as shares of how tall its paper is. No line with no thickness.
    lid_thick: float = 0.0
    lid_sag: float = 0.0
    # Between how many and how many seconds a face blinks, each its own, and how long a
    # blink lasts. How many steps of opening and shutting a mouth goes through in a second
    # of speaking, and of chewing, which opens it no more than the first step.
    blink_every: tuple[float, float] = (0.0, 0.0)
    blink_lasts: float = 0.0
    talk_rate: float = 0.0
    chew_rate: float = 0.0

    def lids_at(self, seconds: float, own: float) -> int:
        """How far shut the eyes of a face are at a moment, by blinking: `own` is somewhere
        from nothing to one, and each face has its own, so that no two blink together."""
        steps = self.steps(SHUT)
        least, most = self.blink_every
        if not steps or self.blink_lasts <= 0 or least <= 0:
            return 0
        every = least + (most - least) * own
        into = (seconds + every * own) % every / self.blink_lasts
        if into >= 1.0:
            return 0
        # Shut in the middle of it, and on the way there and back before and after.
        return steps if 1 / 3 <= into < 2 / 3 else max(1, steps - 1)

    def mouth_at(self, seconds: float, own: float, chewing: bool = False) -> int:
        """How far open the mouth of a face is at a moment of speaking, or of chewing."""
        steps = min(1, self.steps(OPEN)) if chewing else self.steps(OPEN)
        rate = self.chew_rate if chewing else self.talk_rate
        if not steps or rate <= 0:
            return 0
        there_and_back = [*range(steps + 1), *range(steps - 1, 0, -1)]
        return there_and_back[int((seconds + own) * rate) % len(there_and_back)]

    def steps(self, which: str) -> int:
        """In how many steps a face shuts its eyes, or opens its mouth."""
        return max((len(steps) for steps in (self.shut if which == SHUT else self.open).values()), default=0)


@dataclass(frozen=True)
class Key:
    """Where a piece is on the head in one view: its middle on the head's paper, how wide it is
    against how it was drawn, whether it is seen at all, and whether it goes behind the head."""

    x: float
    y: float
    wide: float = 1.0
    shown: bool = True
    behind: bool = False

    def to_data(self) -> dict[str, Any]:
        return {"x": round(self.x, 2), "y": round(self.y, 2), "wide": round(self.wide, 3), "shown": self.shown, "behind": self.behind}


def key_from_data(data: Any) -> Key | None:
    if not isinstance(data, dict):
        return None
    try:
        return Key(
            float(data["x"]), float(data["y"]), min(WIDEST, max(NARROWEST, float(data.get("wide", 1.0)))),
            bool(data.get("shown", True)), bool(data.get("behind", False)),
        )
    except (KeyError, TypeError, ValueError):
        return None


@dataclass(frozen=True)
class Head:
    """How large the head a face goes on is, as it was drawn: its middle and how far out it goes
    to either side and up and down from there, in pixels of its paper."""

    x: float
    y: float
    across: float
    down: float


def head_of(drawing: pygame.Surface) -> Head:
    """The measure of a head as drawn. One nobody has drawn is taken to fill half its paper."""
    box = drawing.get_bounding_rect()
    if box.width < 4 or box.height < 4:
        width, height = drawing.get_size()
        return Head(width / 2, height / 2, width / 4, height / 4)
    return Head(box.centerx, box.centery, box.width / 2, box.height / 2)


@dataclass(frozen=True)
class FaceKind:
    """One kind of piece: an eye, a mouth."""

    kind_id: str
    name: str
    # How large its paper is, and how many times as large it is shown while it is drawn.
    paper: Size
    zoom: int = 1
    # Whether there are two of it, one the other seen in a mirror.
    paired: bool = False
    turn: str = FLAT
    # Where it starts out, from the middle of the head and in halves of its width and height:
    # across, towards the side that goes round the back, and down.
    at: Point = (0.0, 0.0)
    # How far out of the head it stands, in halves of the head's width. Less than nothing is
    # back from its middle. For a piece that goes whole, it is how far it has gone, forwards or
    # back, when the head is seen from its side.
    out: float = 0.0
    # The least of its width it is brought to when seen edge on. For a piece that goes whole,
    # how much of its width it has left when the head is seen from its side: all of it, at 1.
    narrowest: float = 0.5
    # How far round the head has to be, in degrees, for the far one of a pair to be seen no more.
    far_gone: float = 90.0
    # Whether its paper is laid over the head's own, their tops together and one in the middle
    # of the other, and starts out there. It may be larger than the head's: hair is.
    over_head: bool = False
    # Whether it starts out behind the head: hair at the back of it, and ears seen from the front.
    behind: bool = False
    # Whether, behind the head, it is behind the rest of the body too: hair down a back is, an ear is not.
    under_body: bool = False
    # A kind of piece behind which, on the head, this one comes over the head though it is
    # behind it: hair at the back of a head is seen on the head itself behind the ear, more of
    # it the further the head has turned. Nothing for a piece that stays behind the head.
    comes_over_behind: str = ""
    # A kind of piece that this one opens on, though it is in front of it: behind the line that
    # kind comes over the head as far as, this one is not there wherever that one is under
    # it, and that one is seen in its place. Hair in front of a head opens so on the hair
    # behind it: the two are one head of hair, with one line round the two of them and none
    # between them. Seen from the front nothing opens, and it opens by degrees as the head turns.
    opens_on: str = ""
    # A kind of piece that this one is another drawing of, and of that piece doing what: an
    # eye shut, a mouth open. It is no piece of its own, and has no place on the head: where
    # it has been drawn it is shown in place of the other when the other is doing that.
    stands_for: str = ""
    when: str = ""

    @property
    def instances(self) -> tuple[str, ...]:
        """What each of its pieces on a head is called: one, or the two of a pair. None for a
        paper that is another drawing of a piece."""
        if self.stands_for:
            return ()
        return (f"{self.kind_id}_{NEAR}", f"{self.kind_id}_{FAR}") if self.paired else (self.kind_id,)


@dataclass(frozen=True)
class LimbPlace:
    """Where on a trunk a kind of limb hangs: the part of the trunk it is beside, how much of
    that part's half width it is out by when the body faces the screen, and its joints, from
    the one it hangs by outwards, by what they are called without their side. `hangs_from` is
    the joint of the trunk it hangs from: how far ahead of that or behind it a limb is put, on
    a body seen from its side, is ahead or behind and not to one side, and goes round with the body.

    `clear_of` is a part of the limb itself, and `clear` how much of that part's half width
    further out the limb is when the body is seen from right in front or right behind: an
    arm hangs beside a trunk then, and not across the edge of it. It is no further out than
    it was at three quarters, and comes out from there to the front."""

    beside: str
    share: float
    joints: tuple[str, ...]
    hangs_from: str = ""
    clear_of: str = ""
    clear: float = 0.0


@dataclass(frozen=True)
class BodyTurn:
    """How a body is turned towards the screen (`graphics/volume.py`, `graphics/turn.py`)."""

    # The parts that are of the trunk, by their bone: drawn from the front, and wrapped round.
    trunk: tuple[str, ...]
    # Those of them that are one piece of rubber, from the lowest up: the first is gone along
    # backwards, from its far end to where the next begins. Nothing for a trunk of stiff parts.
    rubber: tuple[str, ...]
    # How far a trunk is from chest to back, as a share of how wide it is: what a doll has
    # until somebody says otherwise, and the least and the most it can be given.
    depth: float
    depths: tuple[float, float]
    limbs: dict[str, LimbPlace]
    # The nearest the front a body that is at something is ever turned, in degrees: its clips
    # are written for a body seen from its side. One that only stands is turned all the way.
    nearest: float = 0.0
    # Nearer the front than that, what a body does is seen less and less across the screen,
    # since it is done towards whoever looks: down to this share of it, seen from the front.
    least_swing: float = 1.0
    # The least of its length any part of a limb is seen at, however much it points at whoever
    # looks: it goes across the screen as much more than that share as it takes.
    least_long: float = 0.0
    # Joints that keep where they are from another, whatever the body does across the screen:
    # each with the joint it goes by. A head is one picture, drawn along the line from the
    # neck to its crown: that line brought in towards the middle of the trunk with the rest,
    # the head was seen to lean over to one side as the body came round to the front.
    stiff: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class FaceRules:
    # By ID, in the order they are laid on the head: the first is under the rest.
    kinds: dict[str, FaceKind]
    # How far round the head is in each view it has a place for, in degrees, from the front on.
    views: dict[str, float]
    view_names: dict[str, str]
    # How many turns between the front and the side a head is kept ready at.
    steps: int
    # How flat the face is: what is on the middle of it is this share of the way out a ball would have it.
    flat: float
    # How near the edge of the head, in halves of its width, the far edge of a flat piece may come.
    inside: float
    body: BodyTurn
    moves: FaceMoves = FaceMoves()

    def drawn_as(self, kind_id: str, when: str) -> FaceKind | None:
        """The paper that is another drawing of a kind of piece doing something, if there is one."""
        return next((kind for kind in self.kinds.values() if kind.stands_for == kind_id and kind.when == when), None)

    def kind_of(self, instance: str) -> FaceKind:
        return self.kinds[instance.removesuffix(f"_{NEAR}").removesuffix(f"_{FAR}")]

    @property
    def instances(self) -> list[str]:
        """Every piece a head has, in the order they are laid on it."""
        return [instance for kind in self.kinds.values() for instance in kind.instances]

    @property
    def side(self) -> float:
        """How far round a head seen from its side is."""
        return max(self.views.values())

    def stepped(self, yaw: float, behind: bool = False) -> int:
        """Which of the turns a head is kept ready at is nearest to one: from the front to its
        side, or on round to right behind it for whoever shows it from behind too."""
        return max(0, min(self.steps * (2 if behind else 1), round(abs(yaw) / self.side * self.steps)))

    def yaw_of(self, step: int) -> float:
        return step * self.side / self.steps


def rules_from_data(data: dict[str, Any]) -> FaceRules:
    kinds = {}
    for kind_id, values in data["kinds"].items():
        turn = str(values.get("turn", FLAT))
        if turn not in TURNS:
            raise ValueError(f"{kind_id} goes round with the head in a way there is not: {turn}")
        paper = (int(values["paper"][0]), int(values["paper"][1]))
        at = values.get("at", (0.0, 0.0))
        kinds[str(kind_id)] = FaceKind(
            str(kind_id), str(values.get("name", kind_id)), paper, max(1, int(values.get("zoom", 1))),
            bool(values.get("paired", False)), turn, (float(at[0]), float(at[1])), float(values.get("out", 0.0)),
            float(values.get("narrowest", 0.5)), float(values.get("far_gone", 90.0)), bool(values.get("over_head", False)),
            behind=bool(values.get("behind", False)), under_body=bool(values.get("under_body", False)),
            comes_over_behind=str(values.get("comes_over_behind", "")),
            opens_on=str(values.get("opens_on", "")),
            stands_for=str(values.get("stands_for", "")),
            when=str(values.get("when", "")),
        )
    for kind in kinds.values():
        for marker in (kind.comes_over_behind, kind.opens_on, kind.stands_for):
            if marker and marker not in kinds:
                raise ValueError(f"{kind.kind_id} goes by a kind of piece there is not: {marker}")
        if kind.stands_for and (kind.when not in (SHUT, OPEN) or kinds[kind.stands_for].paper != kind.paper):
            raise ValueError(f"{kind.kind_id} is no drawing of {kind.stands_for} shut or open on paper of its size")
    views = {str(view): float(yaw) for view, yaw in data["views"].items()}
    if views.get(FRONT) != 0.0 or len(set(views.values())) != len(views):
        raise ValueError("A face needs a view from the front, at no turn at all, and no two views at the same turn")
    views = dict(sorted(views.items(), key=lambda entry: entry[1]))
    names = {view: str(data.get("view_names", {}).get(view, view)) for view in views}
    body = data.get("body", {})
    depths = body.get("depths", (0.3, 1.0))
    turn = BodyTurn(
        tuple(map(str, body.get("trunk", ()))),
        tuple(map(str, body.get("rubber", ()))),
        float(body.get("depth", 0.6)),
        (float(depths[0]), float(depths[1])),
        {
            str(name): LimbPlace(
                str(limb["beside"]), float(limb.get("share", 1.0)), tuple(map(str, limb["joints"])), str(limb.get("hangs_from", "")),
                str(limb.get("clear_of", "")), float(limb.get("clear", 0.0)),
            )
            for name, limb in body.get("limbs", {}).items()
        },
        float(body.get("nearest", 0.0)),
        float(body.get("least_swing", 1.0)),
        float(body.get("least_long", 0.0)),
        tuple((str(by), str(joint)) for by, joint in body.get("stiff", ())),
    )
    return FaceRules(
        kinds, views, names, max(1, int(data.get("steps", 12))), float(data.get("flat", 0.75)),
        float(data.get("inside", 0.97)), turn, moves_from_data(data.get("moves", {}), kinds),
    )


def moves_from_data(data: dict[str, Any], kinds: dict[str, FaceKind]) -> FaceMoves:
    def steps(which: str) -> dict[str, tuple[tuple[float, float], ...]]:
        found = {}
        for kind_id, sizes in data.get(which, {}).items():
            if kind_id not in kinds:
                raise ValueError(f"A face moves a kind of piece there is not: {kind_id}")
            found[str(kind_id)] = tuple((max(0.05, float(wide)), max(0.05, float(tall))) for wide, tall in sizes)
        return found

    moods, names = {}, {}
    for mood, by_kind in data.get("moods", {}).items():
        moods[str(mood)] = {}
        names[str(mood)] = str(by_kind.get("name", mood))
        for kind_id, shift in by_kind.items():
            if kind_id == "name":
                continue
            if kind_id not in kinds:
                raise ValueError(f"A face moves a kind of piece there is not: {kind_id}")
            moods[str(mood)][str(kind_id)] = Shift(
                float(shift.get("tilt", 0.0)), float(shift.get("lift", 0.0)), float(shift.get("bend", 0.0))
            )
    plain = tuple(str(kind_id) for kind_id in data.get("plain", ()))
    for kind_id in plain:
        if kind_id not in kinds:
            raise ValueError(f"A plain face has a kind of piece there is not: {kind_id}")
    lid, blink, talk = data.get("lid", {}), data.get("blink", {}), data.get("talk", {})
    every = blink.get("every", (0.0, 0.0))
    return FaceMoves(
        steps(SHUT), steps(OPEN), moods, plain, names, float(lid.get("thick", 0.0)), float(lid.get("sag", 0.0)),
        (float(every[0]), float(every[1])), float(blink.get("lasts", 0.0)),
        float(talk.get("rate", 0.0)), float(talk.get("chew", 0.0)),
    )


def load_rules(path: Path = FACE_PATH) -> FaceRules:
    return rules_from_data(json.loads(path.read_text(encoding="utf-8")))


def face_path(body_id: str, kind_id: str) -> str:
    """Where below the illustrations folder the drawing of one kind of piece of somebody's face is kept."""
    return f"dolls/{body_id}/face_{kind_id}.png"


def face_file(body_id: str) -> str:
    """Where what says where each piece goes is kept."""
    return f"dolls/{body_id}/{FACE_FILE}"


def turned(rules: FaceRules, kind: FaceKind, front: Key, head: Head, yaw: float, half: float = 0.0) -> Key:
    """Where a piece put somewhere from the front goes when the head has turned `yaw` degrees
    towards the right of the screen, by taking the head for something round.

    `half` is half of how wide the piece is painted, in pixels, which is what keeps a flat one
    from going past the edge of the head.
    """
    if kind.turn == STILL or yaw == 0.0:
        return front
    if kind.turn == SHIFT:
        # Whole, and by degrees: forwards or back, and as much narrower as its kind is from the side.
        sine = math.sin(math.radians(yaw))
        wide = max(NARROWEST, front.wide * (1.0 - (1.0 - kind.narrowest) * sine))
        return replace(front, x=front.x + head.across * kind.out * sine, wide=wide)
    across = (front.x - head.x) / head.across
    down = (front.y - head.y) / head.down
    sine, cosine = math.sin(math.radians(yaw)), math.cos(math.radians(yaw))
    # The one of a pair that is on the side the head turns to goes round the back of it, and
    # comes into sight again at the other edge when the head is seen from as far behind.
    gone = kind.paired and across > 0 and kind.far_gone <= yaw <= 2.0 * rules.side - kind.far_gone
    if kind.turn == EDGE:
        x = head.x + head.across * (across * cosine + kind.out * sine)
        # Out at the edge it is behind the head. Once the head has turned, the one left is on the side of it.
        return replace(front, x=x, shown=front.shown and not gone, behind=yaw < kind.far_gone)
    deep = math.sqrt(max(0.0, 1.0 - min(1.0, across * across + down * down))) * rules.flat + kind.out
    x = head.x + head.across * (across * cosine + deep * sine)
    wide = front.wide
    if kind.turn == FLAT:
        level = math.sqrt(max(0.05, 1.0 - across * across))
        facing = (level * cosine - across * sine) / level
        wide = max(NARROWEST, front.wide * max(kind.narrowest, min(1.0, facing)))
        x = min(x, head.x + head.across * rules.inside - half * wide)
    return replace(front, x=x, wide=wide, shown=front.shown and not gone)


def _shrunk(mask: pygame.mask.Mask, by: int) -> pygame.mask.Mask:
    """A mask without whatever of it is within so many pixels of its edge, or of the edge of its room."""
    width, height = mask.get_size()
    outside = pygame.Mask((width + by * 2, height + by * 2), fill=True)
    outside.erase(mask, (by, by))
    wide = pygame.Mask(outside.get_size())
    for shift in range(-by, by + 1):
        wide.draw(outside, (shift, 0))
    grown = pygame.Mask(outside.get_size())
    for shift in range(-by, by + 1):
        grown.draw(wide, (0, shift))
    grown.invert()
    inner = pygame.Mask((width, height))
    inner.draw(grown, (-by, -by))
    return inner


class Face:
    """The pieces of one head: the drawing of each kind, and where each piece goes in each view."""

    def __init__(
        self, rules: FaceRules, drawings: dict[str, pygame.Surface] | None = None, keys: dict[str, dict[str, Key]] | None = None
    ) -> None:
        self.rules = rules
        # By kind. Every kind has its paper, drawn on or not.
        self.drawings: dict[str, pygame.Surface] = {}
        for kind in rules.kinds.values():
            kept = (drawings or {}).get(kind.kind_id)
            paper = pygame.Surface(kind.paper, pygame.SRCALPHA)
            if kept is not None:
                paper.blit(kept if kept.get_size() == kind.paper else pygame.transform.smoothscale(kept, kind.paper), (0, 0))
            self.drawings[kind.kind_id] = paper
        # By piece and by view: only where somebody has said. The rest is worked out.
        self.keys: dict[str, dict[str, Key]] = {piece: dict(views) for piece, views in (keys or {}).items()}
        self._sized: dict[tuple, pygame.Surface] = {}
        self._moved: dict[tuple, pygame.Surface] = {}
        self._painted: dict[str, pygame.Rect] = {}
        # How many times it has changed, drawing or place: whoever shows it elsewhere goes by this.
        self.revision = 0

    def touch(self) -> None:
        """Say that a drawing has changed: nothing made from the drawings is kept."""
        self._sized.clear()
        self._moved.clear()
        self._painted.clear()
        self.revision += 1

    def painted(self, kind_id: str) -> pygame.Rect:
        """The part of a kind's paper that has anything on it."""
        if kind_id not in self._painted:
            self._painted[kind_id] = self.drawings[kind_id].get_bounding_rect()
        return self._painted[kind_id]

    @property
    def drawn(self) -> bool:
        """Whether any piece has been drawn at all."""
        return any(self.painted(kind_id).width for kind_id in self.drawings)

    def doing(self, kind_id: str, look: "FaceLook | None") -> tuple:
        """What a kind of piece is to be shown as for a face that is doing something: which
        paper it is taken from, how wide and how tall against how that was drawn, and how it
        is moved to say how its wearer feels. Nothing at all for a piece that is as it was drawn."""
        if not look:
            return ()
        moves = self.rules.moves
        source, size, lid = kind_id, (1.0, 1.0), False
        for which, steps, step in ((SHUT, moves.shut.get(kind_id, ()), look.lids), (OPEN, moves.open.get(kind_id, ()), look.mouth)):
            if not steps or step <= 0:
                continue
            step = min(step, len(steps))
            other = self.rules.drawn_as(kind_id, which)
            if other is not None and step == len(steps) and self.painted(other.kind_id).width:
                # All the way there, and somebody has drawn it so: their drawing, and no rule.
                source = other.kind_id
            elif which == SHUT and step == len(steps) and moves.lid_thick > 0:
                lid = True
            else:
                size = steps[step - 1]
        shift = moves.moods.get(look.mood, {}).get(kind_id, Shift())
        if source == kind_id and size == (1.0, 1.0) and shift == Shift() and not lid:
            return ()
        return (source, size, shift, lid)

    def _done(self, doing: tuple) -> pygame.Surface:
        """A piece doing something: a picture whose middle is the middle of its paper, which
        it may be larger or smaller than."""
        if doing not in self._moved:
            source, (wide, tall), shift, lid = doing
            picture = self.drawings[source]
            box = self.painted(source)
            if lid and box.width > 2:
                moves = self.rules.moves
                picture = _lid(picture, box, moves.lid_thick * picture.get_height(), moves.lid_sag * picture.get_height())
                box = picture.get_bounding_rect()
            if shift.bend and box.width > 2:
                picture = _bent(picture, box, shift.bend * picture.get_height())
            if shift.tilt:
                picture = pygame.transform.rotozoom(picture, shift.tilt * INNER_END, 1.0)
            if shift.lift:
                picture = _lifted(picture, shift.lift * self.drawings[source].get_height())
            if (wide, tall) != (1.0, 1.0):
                size = (max(1, round(picture.get_width() * wide)), max(1, round(picture.get_height() * tall)))
                picture = pygame.transform.smoothscale(picture, size)
            self._moved[doing] = picture
        return self._moved[doing]

    def said(self, piece: str, view: str) -> bool:
        """Whether where a piece goes in a view is somebody's say, and not worked out."""
        return view in self.keys.get(piece, {})

    def _start(self, piece: str, head: Head, canvas: Size) -> Key:
        """Where a piece is from the front before anybody has put it anywhere."""
        kind = self.rules.kind_of(piece)
        if kind.over_head:
            return Key(canvas[0] / 2, kind.paper[1] / 2, behind=kind.behind)
        across = -kind.at[0] if piece.endswith(f"_{NEAR}") else kind.at[0]
        return Key(head.x + across * head.across, head.y + kind.at[1] * head.down, behind=kind.behind)

    def key(self, piece: str, view: str, head: Head, canvas: Size) -> Key:
        """Where a piece goes in a view: as somebody has said, or else as it works out from the front."""
        own = self.keys.get(piece, {})
        if view in own:
            return own[view]
        front = own.get(FRONT) or self._start(piece, head, canvas)
        if view == FRONT:
            return front
        kind = self.rules.kind_of(piece)
        return turned(self.rules, kind, front, head, self.rules.views[view], self.painted(kind.kind_id).width / 2)

    def set_key(self, piece: str, view: str, key: Key) -> None:
        self.keys.setdefault(piece, {})[view] = key
        self.revision += 1

    def forget_keys(self, view: str, piece: str | None = None) -> None:
        """Have where a piece goes in a view worked out again, or where every piece does."""
        for name, views in self.keys.items():
            if piece is None or name == piece:
                views.pop(view, None)
        self.revision += 1

    def at(self, piece: str, yaw: float, head: Head, canvas: Size) -> Key:
        """Where a piece goes on a head turned any way: between the two views nearest to it."""
        views = list(self.rules.views.items())
        yaw = max(views[0][1], min(views[-1][1], abs(yaw)))
        for (before, low), (after, high) in zip(views, views[1:]):
            if yaw <= high:
                break
        first, second = self.key(piece, before, head, canvas), self.key(piece, after, head, canvas)
        share = (yaw - low) / (high - low)
        nearer = first if share < 0.5 else second
        return Key(
            first.x + (second.x - first.x) * share, first.y + (second.y - first.y) * share,
            first.wide + (second.wide - first.wide) * share, nearer.shown, nearer.behind,
        )

    def _picture(self, piece: str, wide: float, other_way: bool = False, look: "FaceLook | None" = None) -> pygame.Surface:
        """A piece as wide as it is seen, and in a mirror if it is the far one of a pair: or
        if it is not, for one told to be the `other_way` about. With a `look`, it is doing
        whatever a face with that look has it do."""
        kind = self.rules.kind_of(piece)
        mirrored = (kind.paired and piece.endswith(f"_{FAR}")) != other_way
        hundredths = max(WIDTH_STEP, round(wide * 100 / WIDTH_STEP) * WIDTH_STEP)
        doing = self.doing(kind.kind_id, look)
        key = (kind.kind_id, mirrored, hundredths, doing)
        if key not in self._sized:
            picture = self._done(doing) if doing else self.drawings[kind.kind_id]
            if mirrored:
                picture = pygame.transform.flip(picture, True, False)
            if hundredths != 100:
                size = (max(1, round(picture.get_width() * hundredths / 100)), picture.get_height())
                picture = pygame.transform.smoothscale(picture, size)
            self._sized[key] = picture
        return self._sized[key]

    def laid(
        self, head_drawing: pygame.Surface, yaw: float, look: "FaceLook | None" = None
    ) -> list[tuple[str, Key, pygame.Surface, pygame.Rect]]:
        """Every piece that has been drawn as it goes on a head turned some way, the lowest
        first: what it is called, where it is, its picture, and where on the head's paper the
        painted part of that picture falls. With a `look`, each is doing what that has it do."""
        head, canvas = head_of(head_drawing), head_drawing.get_size()
        found = []
        for piece in self.rules.instances:
            kind = self.rules.kind_of(piece)
            if not self.painted(kind.kind_id).width:
                continue
            key = self.at(piece, yaw, head, canvas)
            picture = self._picture(piece, key.wide, look=look)
            corner = (round(key.x - picture.get_width() / 2), round(key.y - picture.get_height() / 2))
            found.append((piece, key, picture, picture.get_bounding_rect().move(corner)))
        return found

    def on_paper(self, kind_id: str, head: Head, canvas: Size) -> Head:
        """The measure of the head as it falls on the paper of a kind that is laid over it."""
        kind = self.rules.kinds[kind_id]
        return replace(head, x=head.x + (kind.paper[0] - canvas[0]) / 2) if kind.over_head else head

    def _under_body(self, piece: str, key: Key) -> bool:
        """Whether a piece, where it is, is behind the whole body and not only the head."""
        return key.behind and self.rules.kind_of(piece).under_body

    def backing(self, head_drawing: pygame.Surface, yaw: float) -> tuple[pygame.Surface, tuple[int, int]] | None:
        """What of a face is behind the whole body, turned some way: a picture, and where on the
        head's paper its corner goes, which may be off that paper. It is to be laid under the
        doll and moved as its head is. None if there is nothing of the kind."""
        under = [
            (picture, box) for piece, key, picture, box in self.laid(head_drawing, yaw)
            if key.shown and self._under_body(piece, key) and box.width
        ]
        if not under:
            return None
        room = under[0][1].unionall([box for _, box in under[1:]])
        back = pygame.Surface(room.size, pygame.SRCALPHA)
        for picture, box in under:
            painted = picture.get_bounding_rect()
            back.blit(picture, (box.x - room.x, box.y - room.y), painted)
        return back, room.topleft

    def fronting(
        self, head_drawing: pygame.Surface, yaw: float, look: "FaceLook | None" = None
    ) -> tuple[pygame.Surface, tuple[int, int]]:
        """A head with its face on it, turned some way, as it goes on a doll: a picture, and where
        on the head's paper its corner is. It is as large as what is on it, which may go past
        the paper: hair that has gone forwards does. What is behind the whole body is left out.
        With a `look`, the face is doing what that has it do."""
        paper = head_drawing.get_rect()
        boxes = [
            box for piece, key, _, box in self.laid(head_drawing, yaw, look)
            if key.shown and box.width and not self._under_body(piece, key)
        ]
        room = paper.unionall(boxes)
        return self.composed(head_drawing, yaw, backed=False, room=room, look=look), room.topleft

    def behind(self, head_drawing: pygame.Surface, yaw: float) -> tuple[pygame.Surface, tuple[int, int]]:
        """A head seen from behind, `yaw` degrees round from facing the screen and so more than
        from its side: a picture, and where on the head's paper its corner is.

        Nobody says where anything goes from behind: it follows from where it was put from the
        front. Hair at the back of the head is over it, and over the neck and the back under
        it, the other way about. Ears are on the head, one at either edge from right behind.
        Whatever else there is goes under the head, where it has gone round to: hair in front
        of the head the other way about, so that of it there is what stands above the head and
        to either side; and of a face nothing, unless a nose still stands out past the edge.
        A head with no hair is a head and its ears.
        """
        rules = self.rules
        head, canvas = head_of(head_drawing), head_drawing.get_size()
        yaw = max(rules.side, min(2.0 * rules.side, abs(yaw)))
        # How far round it is from being seen from right behind.
        away = 2.0 * rules.side - yaw
        under, over = [], []
        for piece in rules.instances:
            kind = rules.kind_of(piece)
            if not self.painted(kind.kind_id).width:
                continue
            front = self.keys.get(piece, {}).get(FRONT) or self._start(piece, head, canvas)
            if not front.shown:
                continue
            if kind.turn == SHIFT:
                # Whole, and the other way about: it goes forwards or back as it did seen as
                # far round from the front, since its edge is the same edge from either side.
                key = turned(rules, kind, replace(front, x=2.0 * head.x - front.x), head, away)
                picture = self._picture(piece, key.wide, other_way=True)
                (over if kind.behind else under).append((kind, key, picture))
                continue
            key = turned(rules, kind, front, head, yaw, self.painted(kind.kind_id).width / 2)
            if not key.shown:
                continue
            if kind.turn == EDGE:
                over.insert(0, (kind, key, self._picture(piece, key.wide, other_way=yaw >= EAR_TURNED_FROM)))
            else:
                under.append((kind, key, self._picture(piece, key.wide)))
        laid = []
        for group in (under, over):
            laid.append([(picture, (round(key.x - picture.get_width() / 2), round(key.y - picture.get_height() / 2))) for _, key, picture in group])
        boxes = [picture.get_bounding_rect().move(corner) for group in laid for picture, corner in group]
        room = head_drawing.get_rect().unionall([box for box in boxes if box.width])
        whole = pygame.Surface(room.size, pygame.SRCALPHA)
        for picture, corner in laid[0]:
            whole.blit(picture, (corner[0] - room.x, corner[1] - room.y))
        whole.blit(head_drawing, (-room.x, -room.y))
        for picture, corner in laid[1]:
            whole.blit(picture, (corner[0] - room.x, corner[1] - room.y))
        return whole, room.topleft

    def composed(
        self,
        head_drawing: pygame.Surface,
        yaw: float,
        ghosts: bool = False,
        backed: bool = True,
        room: pygame.Rect | None = None,
        look: "FaceLook | None" = None,
    ) -> pygame.Surface:
        """A head with its face on it, turned some way: one picture, as large as the head's paper.

        With `ghosts`, what is not seen in that turn is shown faintly, to be taken hold of.
        Without `backed`, what is behind the whole body is left out: that is `backing`. `room`
        is another part of the paper to show, or more than the paper, in place of all of it.
        With a `look`, the face is doing what that has it do.
        """
        room = room if room is not None else head_drawing.get_rect()
        whole = pygame.Surface(room.size, pygame.SRCALPHA)
        pieces = self.laid(head_drawing, yaw, look)

        def lay(behind: bool) -> None:
            for piece, key, picture, box in pieces:
                if key.behind != behind or not (key.shown or ghosts):
                    continue
                if not backed and self._under_body(piece, key):
                    continue
                corner = (round(key.x - picture.get_width() / 2) - room.x, round(key.y - picture.get_height() / 2) - room.y)
                if not key.shown:
                    picture = picture.copy()
                    picture.fill((255, 255, 255, GHOST_ALPHA), special_flags=pygame.BLEND_RGBA_MULT)
                opened = None if behind else self._opened(piece, key, picture, corner, head_drawing, pieces, yaw, room)
                if opened is not None:
                    picture, corner = opened, (0, 0)
                whole.blit(picture, corner)

        lay(behind=True)
        whole.blit(head_drawing, (-room.x, -room.y))
        self._come_over(whole, head_drawing, pieces, yaw, room)
        lay(behind=False)
        return whole

    def _opened(
        self,
        piece: str,
        key: Key,
        picture: pygame.Surface,
        corner: tuple[int, int],
        head_drawing: pygame.Surface,
        pieces: list[tuple[str, Key, pygame.Surface, pygame.Rect]],
        yaw: float,
        room: pygame.Rect,
    ) -> pygame.Surface | None:
        """A piece that opens on another, with what of it is open taken out: a picture as large
        as the part of the paper it is shown on. None if nothing of it opens.

        The two are to look one shape with one line round it. So behind the line the other
        kind comes over the head as far as, this piece is open:

        - wherever the other is under it and well inside its own edge: there the colour of the
          other is seen, and whatever line this piece had over it is gone
        - wherever the other is under it near its own edge, if that edge is the edge of the
          two together: there the line round the other is the line round both

        And it is left as it is wherever the other is under it near an edge that this piece
        goes on beyond: the line of the other would be a line inside the two of them. Nor is
        it open where the other is not under it: no hole shows what is behind the head, and
        where this piece is the outer one its own line is the line round both.
        """
        other = self.rules.kinds.get(self.rules.kind_of(piece).opens_on)
        if other is None or not other.comes_over_behind or not yaw:
            return None
        under = [
            (at, shown, box) for name, at, shown, box in pieces
            if self.rules.kind_of(name) is other and at.shown and at.behind and box.width
        ]
        if not under:
            return None
        kept = max(1, round(head_of(head_drawing).across * EDGE_KEPT))
        # Room for all of both, and to spare: the edge of the room is the edge of nothing.
        work = room.unionall([box for _, _, box in under]).inflate((kept + 3) * 2, (kept + 3) * 2)
        mine = pygame.Mask(work.size)
        mine.draw(pygame.mask.from_surface(picture), (corner[0] + room.x - work.x, corner[1] + room.y - work.y))
        beneath = pygame.Mask(work.size)
        for at, shown, _ in under:
            where = (round(at.x - shown.get_width() / 2) - work.x, round(at.y - shown.get_height() / 2) - work.y)
            beneath.draw(pygame.mask.from_surface(shown), where)
        both = mine.copy()
        both.draw(beneath, (0, 0))
        ends = self._hairline(other.comes_over_behind, head_drawing, yaw, SLACK_IN_FRONT)
        back = pygame.Surface(work.size, pygame.SRCALPHA)
        pygame.draw.polygon(back, (255, 255, 255, 255), [
            (-1, 0), (ends(work.y) - work.x, 0), (ends(work.bottom) - work.x, work.height), (-1, work.height),
        ])
        may_open = mine.overlap_mask(beneath, (0, 0)).overlap_mask(pygame.mask.from_surface(back), (0, 0))
        # How far in from the edge of the other, and of the two together, step by step.
        in_other, in_both = [beneath], [both]
        for _ in range(kept + 1):
            in_other.append(_shrunk(in_other[-1], 1))
            in_both.append(_shrunk(in_both[-1], 1))
        open_here = may_open.overlap_mask(in_other[kept], (0, 0))
        for depth in range(kept):
            # This near the edge of the other, and no further from the edge of both: it is the same edge.
            ring = in_other[depth].copy()
            ring.erase(in_other[depth + 1], (0, 0))
            outer = in_both[depth + 1].copy()
            outer.invert()
            open_here.draw(may_open.overlap_mask(ring, (0, 0)).overlap_mask(outer, (0, 0)), (0, 0))
        if not open_here.count():
            return None
        whole = pygame.Surface(room.size, pygame.SRCALPHA)
        whole.blit(picture, corner)
        gone = pygame.Mask(room.size)
        gone.draw(open_here, (work.x - room.x, work.y - room.y))
        whole.blit(gone.to_surface(setcolor=(255, 255, 255, 255), unsetcolor=CLEAR), (0, 0), special_flags=pygame.BLEND_RGBA_SUB)
        return whole

    def _hairline(self, marker: str, head_drawing: pygame.Surface, yaw: float, slack: float = 0.0):
        """The line on a turned head that hair behind it comes over the head as far as: how
        far across the head's paper it is at each height.

        It goes through the middle of whichever of a kind of piece is still seen, an ear, and
        leans as a hairline does, the more the further the head has turned. `slack` is how
        much further back it is with the head seen from the front, in halves of the head's
        width: that much less, by degrees, until from the side it is the line itself.
        """
        head, canvas = head_of(head_drawing), head_drawing.get_size()
        turned_by = math.sin(math.radians(min(abs(yaw), self.rules.side)))
        edge = self.at(self.rules.kinds[marker].instances[0], yaw, head, canvas).x - head.across * slack * (1.0 - turned_by)
        lean = head.across * turned_by
        top, foot = head.y - head.down, head.y + head.down

        def ends(y: float) -> float:
            share = (y - top) / (foot - top) if foot > top else 0.5
            return edge + lean * (OVER_AT_TOP + (OVER_AT_FOOT - OVER_AT_TOP) * share)

        return ends

    def _come_over(
        self,
        whole: pygame.Surface,
        head_drawing: pygame.Surface,
        pieces: list[tuple[str, Key, pygame.Surface, pygame.Rect]],
        yaw: float,
        room: pygame.Rect,
    ) -> None:
        """Lay over the head what is behind it but is seen on it as it turns: hair at the back
        of a head, on the part of the head that is behind its ear.

        Only on the head itself, and only as far forwards as the middle of the ear that is
        still seen: from the front that is the edge of the head, and nothing comes over; from
        the side it is the middle of it, and the back half of the head is hair. The line it
        ends along leans, the more the further the head has turned.
        """
        canvas = head_drawing.get_size()
        on_head: pygame.Surface | None = None
        for piece, key, picture, _ in pieces:
            marker = self.rules.kind_of(piece).comes_over_behind
            if not marker or not key.behind or not key.shown:
                continue
            if on_head is None:
                on_head = pygame.mask.from_surface(head_drawing).to_surface(setcolor=(255, 255, 255, 255), unsetcolor=CLEAR)
            ends = self._hairline(marker, head_drawing, yaw)
            # The head as far forwards as that line, and no further.
            shown = on_head.copy()
            width, height = canvas
            pygame.draw.polygon(
                shown, CLEAR,
                [(ends(0) + UNDERLAP, 0), (width + 1, 0), (width + 1, height), (ends(height) + UNDERLAP, height)],
            )
            over = pygame.Surface(canvas, pygame.SRCALPHA)
            over.blit(picture, (round(key.x - picture.get_width() / 2), round(key.y - picture.get_height() / 2)))
            over.blit(shown, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
            whole.blit(over, (-room.x, -room.y))

    def to_data(self) -> dict[str, Any]:
        return {"keys": {piece: {view: key.to_data() for view, key in views.items()} for piece, views in self.keys.items() if views}}


def _bent(picture: pygame.Surface, box: pygame.Rect, down: float) -> pygame.Surface:
    """A picture with the ends of what is painted on it brought down by so many pixels, and
    up by less than nothing: its middle goes the other way a third as far, so that it stays
    about where it was. Its own middle is where it was, on a picture that much taller."""
    reach = math.ceil(abs(down))
    width, height = picture.get_size()
    bent = pygame.Surface((width, height + 2 * reach), pygame.SRCALPHA)
    half = max(1.0, box.width / 2)
    for x in range(box.left, box.right):
        out = (x + 0.5 - box.centerx) / half
        bent.blit(picture, (x, reach + round(down * (out * out - 1 / 3))), (x, 0, 1, height))
    return bent


def _lid(picture: pygame.Surface, box: pygame.Rect, thick: float, sag: float) -> pygame.Surface:
    """An eye shut, by rule: a line where the eye was, as wide as it was painted and the
    darkest colour it has, so thick, and sagging so far in its middle."""
    darkest, least = (0, 0, 0), 766
    for x in range(box.left, box.right):
        for y in range(box.top, box.bottom):
            red, green, blue, alpha = picture.get_at((x, y))
            if alpha >= 200 and red + green + blue < least:
                darkest, least = (red, green, blue), red + green + blue
    shut = pygame.Surface(picture.get_size(), pygame.SRCALPHA)
    wide = max(2, round(thick))
    half = box.width / 2 - wide / 2
    points = []
    for step in range(13):
        out = step / 6 - 1.0
        points.append((box.centerx + out * half, box.centery + sag * (1.0 - out * out) - sag / 2))
    pygame.draw.lines(shut, darkest, False, points, wide)
    for point in points:
        pygame.draw.circle(shut, darkest, point, wide / 2)
    return shut


def _lifted(picture: pygame.Surface, up: float) -> pygame.Surface:
    """A picture with what is on it so many pixels further up: its own middle is where it
    was, on a picture that much taller."""
    reach = math.ceil(abs(up))
    lifted = pygame.Surface((picture.get_width(), picture.get_height() + 2 * reach), pygame.SRCALPHA)
    lifted.blit(picture, (0, reach - round(up)))
    return lifted


def plain_face(rules: FaceRules, head_drawing: pygame.Surface, example: Any) -> "Face":
    """The face of a body nobody has drawn: a plain piece of each kind a plain face has,
    made by `example` as the pieces a face is tried with are. It is the game's, as the figure
    it goes on is, until somebody draws their own."""
    face = Face(rules)
    head, canvas = head_of(head_drawing), head_drawing.get_size()
    at = (min(canvas[0] - 1, max(0, round(head.x))), min(canvas[1] - 1, max(0, round(head.y))))
    red, green, blue, alpha = head_drawing.get_at(at)
    skin = (red, green, blue) if alpha else (214, 170, 130)
    for kind_id in rules.moves.plain:
        kind = rules.kinds[kind_id]
        picture = example(kind_id, kind.paper, skin, face.on_paper(kind_id, head, canvas))
        if picture is not None:
            face.drawings[kind_id] = picture
    face.touch()
    return face


def keys_from_data(rules: FaceRules, data: Any) -> dict[str, dict[str, Key]]:
    """Where each piece goes, as it was kept. Whatever cannot be made out is left to be worked out."""
    found: dict[str, dict[str, Key]] = {}
    kept = data.get("keys") if isinstance(data, dict) else None
    if not isinstance(kept, dict):
        return found
    known = set(rules.instances)
    for piece, views in kept.items():
        if piece not in known or not isinstance(views, dict):
            continue
        for view, values in views.items():
            key = key_from_data(values)
            if view in rules.views and key is not None:
                found.setdefault(piece, {})[view] = key
    return found


class FaceStore:
    """The faces there are, by whose they are, read the first time each is asked for."""

    def __init__(self, root: Path | None, rules: FaceRules) -> None:
        self.root = root
        self.rules = rules
        self._faces: dict[str, Face] = {}

    def get(self, body_id: str) -> Face:
        """Somebody's face. Whoever has none yet has every paper blank."""
        if body_id not in self._faces:
            self._faces[body_id] = self._read(body_id)
        return self._faces[body_id]

    def _read(self, body_id: str) -> Face:
        if self.root is None:
            return Face(self.rules)
        drawings = {}
        for kind_id in self.rules.kinds:
            path = self.root / face_path(body_id, kind_id)
            if path.is_file():
                try:
                    drawings[kind_id] = pygame.image.load(str(path))
                except pygame.error as error:
                    logger.warning("A piece of a face could not be read: %s (%s)", path, error)
        keys: dict[str, dict[str, Key]] = {}
        path = self.root / face_file(body_id)
        if path.is_file():
            try:
                keys = keys_from_data(self.rules, json.loads(path.read_text(encoding="utf-8")))
            except (OSError, ValueError) as error:
                logger.warning("Where a face goes could not be read: %s (%s)", path, error)
        return Face(self.rules, drawings, keys)

    def save(self, body_id: str) -> bool:
        """Write somebody's face where it is looked for. Returns whether it worked."""
        if self.root is None or body_id not in self._faces:
            return False
        face = self._faces[body_id]
        try:
            for kind_id, drawing in face.drawings.items():
                path = self.root / face_path(body_id, kind_id)
                path.parent.mkdir(parents=True, exist_ok=True)
                pygame.image.save(drawing, str(path))
            (self.root / face_file(body_id)).write_text(json.dumps(face.to_data(), indent=2) + "\n", encoding="utf-8")
        except (OSError, pygame.error):
            return False
        return True

    def forget(self, body_id: str) -> None:
        self._faces.pop(body_id, None)


Placed = tuple[pygame.Surface, tuple[int, int]]


def with_head(doll: Doll, head: Placed, back: Placed | None = None) -> Doll:
    """A doll with another head on it, and the rest of it as it was: its body is not cut again,
    and its limbs are bent no more than once for all the heads it is given.

    `head` is a picture, and where on the head's paper its corner is: it may be larger than the
    paper. `back` is what goes with the head but behind the whole body, said the same way: it
    is laid under everything, and moved as the head is.
    """
    other = copy.copy(doll)
    of_head = {bone for bone, spec in doll.template.parts.items() if spec.canvas == HEAD_CANVAS}
    other.parts = {bone: part for bone, part in doll.parts.items() if bone not in of_head and UNDER not in bone}
    other.under, other.drawn = {}, dict(doll.drawn)
    whole = next((bone for bone in of_head if doll.template.parts[bone].whole), None)
    if whole is not None:
        spec = doll.template.parts[whole]
        for name, placed in ((whole, head), (f"{whole}{UNDER}", back)):
            if placed is None:
                continue
            picture, (left, top) = placed
            box = picture.get_bounding_rect()
            if not box.width:
                continue
            # It turns about the neck as the head does, wherever on its own picture that is.
            left, top = left + box.x, top + box.y
            other.parts[name] = DollPart(
                picture.subsurface(box).copy(), (spec.start[0] - left, spec.start[1] - top), (spec.end[0] - left, spec.end[1] - top)
            )
            other.drawn[name] = doll.drawn[whole]
            if name != whole:
                other.under[name] = whole
    other._sized, other._turned, other._standing = {}, {}, None
    return other


def faced(doll: Doll, face: "Face | None", head: pygame.Surface, yaw: float) -> Doll:
    """A doll with its face on, its head turned some way: the doll as it is if it has none.
    Round to three quarters from behind and further the head is seen from behind
    (`Face.behind`), and nothing of it is under the body. A little past its side it is still
    the head seen from its side. Between the two it is both, the one fading as the other comes."""
    if face is None or not face.drawn:
        return doll
    yaw = abs(yaw)
    if yaw >= BEHIND_BY:
        return with_head(doll, face.behind(head, yaw))
    if yaw <= BEHIND_FROM:
        return with_head(doll, face.fronting(head, yaw), face.backing(head, yaw))
    gone = (yaw - BEHIND_FROM) / (BEHIND_BY - BEHIND_FROM)
    back = face.backing(head, yaw)
    return with_head(
        doll, _dissolved(face.fronting(head, yaw), face.behind(head, yaw), gone),
        (_faded(back[0], 1.0 - gone), back[1]) if back is not None else None,
    )


def _faded(picture: pygame.Surface, share: float) -> pygame.Surface:
    """A picture that much of the way to being there at all."""
    faint = picture.copy()
    faint.fill((255, 255, 255, round(255 * max(0.0, min(1.0, share)))), special_flags=pygame.BLEND_RGBA_MULT)
    return faint


def _dissolved(one: Placed, other: Placed, share: float) -> Placed:
    """Two pictures of the same thing as one, the first giving way to the second by `share`:
    each with where on the paper its corner is, and the one made of them the same.

    Where both are, it is solid, and its colour part of the way from one to the other. Where
    only one is, it is as faint as that one has gone or has yet to come.
    """
    (first, at), (second, to) = one, other
    room = first.get_rect(topleft=at).union(second.get_rect(topleft=to))
    whole = pygame.Surface(room.size, pygame.SRCALPHA)
    # Added up, each as much as there is of it: colours times how solid, as pictures are laid.
    for picture, corner, much in ((first, at, 1.0 - share), (second, to, share)):
        layer = picture.convert_alpha() if picture.get_flags() & pygame.SRCALPHA == 0 else picture
        whole.blit(_faded(layer, much).premul_alpha(), (corner[0] - room.x, corner[1] - room.y), special_flags=pygame.BLEND_RGBA_ADD)
    return _straight(whole), room.topleft


def _straight(premultiplied: pygame.Surface) -> pygame.Surface:
    """A picture whose colours were each times how solid it is, with its colours as they are."""
    if _np is None:
        return premultiplied
    straight = premultiplied.copy()
    colours = pygame.surfarray.pixels3d(straight)
    solid = pygame.surfarray.array_alpha(straight).astype(_np.float32)
    colours[:] = _np.clip(colours.astype(_np.float32) * 255.0 / _np.maximum(solid, 1.0)[..., None], 0, 255).astype(_np.uint8)
    del colours
    return straight
