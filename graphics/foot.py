"""Feet that are made and not drawn, as hands are (`graphics/hand.py`): a boot out of a cartoon,
in a colour whoever draws the doll picks.

The doll is cut without the feet that were drawn on it and these are laid where they were, at
the end of each leg, turned as the bone of the foot is. That bone runs from the ankle to the
toes at the height of the ankle, well above the ground: so a foot is what hangs under it. It
is a boot: a shaft the leg goes into, cut straight across a little above the ankle, down to a
round heel, and forward along a flat sole to a round toe, with one line round the lot. It is
laid over the leg, as a hand is over its arm, and is wide enough to hide where the leg ends.

Tried and thrown out: a shaft with a round top, which was a ball on the end of the leg; and a
foot laid under the leg, which a doll with a foot drawn on the end of its leg hid all but the
sole of.

How far under the ankle the sole is goes with the leg and not with the size picked: a larger
foot is longer and thicker, and stands on the same ground. With the body turned towards
whoever looks, a foot points their way and shows shorter, down to a share of its length seen
from the front. How it is made is data, in `data/feet.json`.
"""

import json
import logging
import math
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

import pygame

from graphics.hand import FINER, JOIN_WIDER, KEPT_HANDS, LINE, SHADE_STEPS, TURN_STEPS, Look, _as_one, darker
from skeleton.rig import Bone

logger = logging.getLogger(__name__)

Color = tuple[int, int, int]
Point = tuple[float, float]

FEET_PATH = Path(__file__).resolve().parent.parent / "data" / "feet.json"
FEET_FILE = "feet.json"
# A foot is kept for each of this many lengths it may show at, from its side to the front.
SHOWN_STEPS = 12


@dataclass(frozen=True)
class FootRules:
    """How a foot is made. Everything but the colours and the sizes is a share of how long the
    bone of the foot is, from the ankle to the toes."""

    bones: tuple[str, ...]
    # What the name of the foot on the far side ends in, and how much darker that one is.
    far: str
    color: Color
    far_shade: float
    size: float
    sizes: tuple[float, float]
    # How far under the ankle the ground is.
    sole: float
    # The shaft the leg goes into: how far to either side of the ankle it goes, how far above
    # it, and how round its corners are.
    shaft_wide: float
    shaft_above: float
    shaft_round: float
    # The heel: how far behind the ankle its middle is, and how round it is.
    heel_back: float
    heel_radius: float
    # The toe: how far in front of the ankle its middle is, and how round it is.
    toe_at: float
    toe_radius: float
    line: float
    # How much of its length a foot shows seen from the front.
    front: float
    # How far round from facing the screen a body is, in degrees, when its near foot begins to
    # come round to point out to its own side, as feet do seen from the front. It comes round
    # by degrees, through pointing at whoever looks, when it is no length at all: turned the
    # other way all at once, it jumped. Further round than that both point the way the body faces.
    splay_to: float = 0.0
    # The part of a doll whose colour, at its far end, a foot has until one is picked for it.
    matches: str = ""
    # The least and the most times as thick as that the line round a foot may be made.
    lines: tuple[float, float] = (0.0, 2.5)
    # The joint of the skeleton that is an ankle: how high it is on a body at rest is how far
    # under it the sole of a foot is.
    matches_joint: str = ""


def rules_from_data(data: dict[str, Any]) -> FootRules:
    heel, toe, shaft = data["heel"], data["toe"], data["shaft"]
    red, green, blue = data.get("color", (214, 170, 130))
    sizes = data.get("sizes", (0.7, 1.5))
    return FootRules(
        tuple(map(str, data["bones"])), str(data.get("far", "_left")), (int(red), int(green), int(blue)),
        float(data.get("far_shade", 0.0)), float(data.get("size", 1.0)), (float(sizes[0]), float(sizes[1])),
        float(data["sole"]), float(shaft["wide"]), float(shaft.get("above", 0.15)), float(shaft.get("round", 0.1)),
        float(heel["back"]), float(heel["radius"]), float(toe["at"]), float(toe["radius"]),
        float(data.get("line", 0.08)), float(data.get("front", 0.5)), float(data.get("splay_to", 0.0)),
        str(data.get("matches", "")),
        (float(data.get("lines", (0.0, 2.5))[0]), float(data.get("lines", (0.0, 2.5))[1])),
        str(data.get("ankle", "")),
    )


def load_rules(path: Path = FEET_PATH) -> FootRules:
    return rules_from_data(json.loads(path.read_text(encoding="utf-8")))


@dataclass(frozen=True)
class FootChoice:
    """What whoever draws a doll has said of its feet: whether they are made, and not the ones
    drawn on it, their colour and how large they are, and the colour of the line round them
    and how many times as thick as usual it is."""

    made: bool = False
    color: Color | None = None
    size: float | None = None
    line_color: Color | None = None
    line: float | None = None

    def to_data(self) -> dict[str, Any]:
        return {
            "made": self.made, "color": list(self.color) if self.color else None, "size": self.size,
            "line_color": list(self.line_color) if self.line_color else None, "line": self.line,
        }


def choice_from_data(data: Any) -> FootChoice:
    if not isinstance(data, dict):
        return FootChoice()
    color, ink = data.get("color"), data.get("line_color")
    try:
        return FootChoice(
            bool(data.get("made", False)),
            (int(color[0]), int(color[1]), int(color[2])) if color else None,
            float(data["size"]) if data.get("size") is not None else None,
            (int(ink[0]), int(ink[1]), int(ink[2])) if ink else None,
            float(data["line"]) if data.get("line") is not None else None,
        )
    except (TypeError, ValueError, IndexError):
        return FootChoice()


def draw_foot(
    target: pygame.Surface,
    rules: FootRules,
    ankle: Point,
    long: float,
    angle: float,
    forwards: float,
    color: Color,
    size: float = 1.0,
    shown: float = 1.0,
    look: Look = Look(),
    sole: float | None = None,
) -> None:
    """Draw one foot on a surface, as large as it is told.

    `ankle` is where it hangs from and `long` how long its bone is, in pixels. `angle` is which
    way that bone runs, in radians from straight down and anticlockwise as bones are: a foot
    flat on the ground runs level. `forwards` is 1 for a body that faces right and -1 for one
    that faces left: which side of the bone the leg is on. `size` is how many times as long and
    as thick as the rules have it, and `shown` how much of its length is seen. `look` is how
    it is finished: its lines, and how wide the leg it is joined to is at the ankle, which is
    how wide its shaft is (`graphics/hand.py`). `sole` is how far under the ankle the ground
    is, as a share of `long`, where that is known from the body it is on and not the rules.
    """
    along = (math.sin(angle), math.cos(angle))
    up = (math.cos(angle) * forwards, -math.sin(angle) * forwards)

    def at(forward: float, above: float) -> Point:
        """A place on the foot: that far in front of the ankle, and that far above it."""
        return (ankle[0] + (along[0] * forward + up[0] * above) * long, ankle[1] + (along[1] * forward + up[1] * above) * long)

    line = look.line(rules.line, long)
    drop = rules.sole if sole is None else sole
    ground = -drop
    # Never rounder than there is room for between the ankle and the ground.
    heel = min(rules.heel_radius * size, drop * 0.6)
    toe = min(rules.toe_radius * size, drop * 0.6)
    back = -rules.heel_back * size * shown
    front = max(rules.toe_at * size * shown, back)
    wide, corner = rules.shaft_wide * size, rules.shaft_round * size
    if look.joins is not None:
        # Joined to a leg, its shaft is as wide as the leg is there.
        wide = max(corner + 0.02, look.joins * JOIN_WIDER)
    top = rules.shaft_above * size
    # Where the top of the foot leaves the shaft: at the front of it, or at the toe if that is nearer.
    leaves = min(wide, front)
    shapes = [
        # The shaft, from a little above the ankle down to the heel, cut straight across on top.
        ([at(corner - wide, top - corner), at(wide - corner, top - corner), at(wide - corner, ground + heel), at(corner - wide, ground + heel)], corner * long),
        (at(back, ground + heel), at(back, ground + heel), heel * long),
        (at(front, ground + toe), at(front, ground + toe), toe * long),
        # What is between them: flat under, and sloping down on top from the shaft to the toe.
        ([at(back, ground), at(front, ground), at(front, ground + toe * 2.0), at(leaves, ground + heel * 2.0), at(back, ground + heel * 2.0)], 0.0),
    ]
    _as_one(target, shapes, color, line, look.ink)


class Feet:
    """The feet of one doll, made at whatever size and turn they are asked for, and kept."""

    def __init__(self, rules: FootRules, choice: FootChoice = FootChoice()) -> None:
        self.rules = rules
        self.choice = choice
        self._kept: dict[tuple, tuple[pygame.Surface, Point]] = {}
        # How much of its length a foot shows, with the body turned as it is: and the near
        # one, which shows less than nothing of it when it points the other way.
        self.shown = 1.0
        self.near_shown = 1.0
        self.shade = 1.0
        # The colour of the leg they are on, where whoever has the doll has told it: theirs
        # until one is picked for them.
        self.natural: Color | None = None
        # How far to either side of the ankle that leg goes, and how far above the ground the
        # ankle of the body they are on is at rest, both in the skeleton's measure: a foot
        # begins that wide and stands that far under its ankle. None where nobody has said.
        self.joins: float | None = None
        self.stands: float | None = None

    @property
    def color(self) -> Color:
        return self.choice.color or self.natural or self.rules.color

    @property
    def ink(self) -> Color:
        """The colour of its line."""
        return self.choice.line_color or LINE

    @property
    def bold(self) -> float:
        """How many times as thick as the rules have it the line round it is."""
        low, high = self.rules.lines
        return max(low, min(high, self.choice.line if self.choice.line is not None else 1.0))

    @property
    def size(self) -> float:
        low, high = self.rules.sizes
        return max(low, min(high, self.choice.size if self.choice.size is not None else self.rules.size))

    def choose(self, **changes: Any) -> None:
        """Change what has been said of these feet."""
        self.choice = replace(self.choice, **changes)
        self._kept.clear()

    def turned(self, yaw: float | None, side: float = 90.0) -> None:
        """Say how far round from facing the screen the body they are on is, in degrees, where
        `side` is seen from its side: with None, seen from its side."""
        # The far one is in the shade of the body only as far as the body is seen from its side.
        self.shade = 1.0 if yaw is None else abs(math.sin(math.radians(yaw * 90.0 / side)))
        if yaw is None:
            self.shown = self.near_shown = 1.0
            return
        # From behind as from the front: it points away as it pointed at whoever looks.
        folded = min(abs(yaw), 2.0 * side - abs(yaw))

        def length(turn: float) -> float:
            round_by = math.radians(max(0.0, min(side, turn)) * 90.0 / side)
            return math.hypot(math.sin(round_by), self.rules.front * math.cos(round_by))

        self.shown = self.near_shown = length(folded)
        if folded < self.rules.splay_to:
            # From as long as the other at that turn, through nothing, to as long the other way.
            share = folded / self.rules.splay_to
            self.near_shown = -self.rules.front + (length(self.rules.splay_to) + self.rules.front) * share

    @property
    def splayed(self) -> bool:
        """Whether the near foot points out to its own side, and not the way the body faces."""
        return self.near_shown < 0.0

    def picture(
        self, name: str, angle: float, long: float, mirrored: bool, detail: float, shown: float | None = None, lined: bool = True
    ) -> tuple[pygame.Surface, Point]:
        """One foot as it is shown, and where on that picture its ankle is.

        `name` is which foot it is, by the doll's own name for its bone, `angle` which way that
        bone runs and `long` how long the bone is, in the skeleton's measure. `detail` is how
        many pixels go to one of the skeleton's.
        """
        far = name.endswith(self.rules.far)
        turn = round(angle / math.tau * TURN_STEPS) % TURN_STEPS
        seen = round(max(0.0, min(1.0, self.shown if shown is None else shown)) * SHOWN_STEPS)
        size = round(long * detail * 4) / 4
        joins = round(self.joins / long * 50) / 50 if self.joins and long > 0 else None
        sole = round(self.stands / long * 100) / 100 if self.stands and long > 0 else None
        look = Look(self.ink, self.bold, lined, joins)
        shade = round(self.shade * SHADE_STEPS) / SHADE_STEPS if far else 0.0
        key = (far, shade, mirrored, look, sole, turn, seen, size, self.color, self.size)
        if key not in self._kept:
            if len(self._kept) > KEPT_HANDS:
                self._kept.clear()
            self._kept[key] = self._made(far, mirrored, turn, seen, size, look, sole, shade)
        return self._kept[key]

    def _made(
        self, far: bool, mirrored: bool, turn: int, seen: int, size: float, look: Look = Look(), sole: float | None = None,
        shade: float = 1.0,
    ) -> tuple[pygame.Surface, Point]:
        rules = self.rules
        # Room for the foot whichever way it runs.
        far_down = max(rules.sole, sole or 0.0)
        far_out = max((rules.toe_at + rules.toe_radius) * self.size, (rules.shaft_wide + rules.shaft_above) * self.size, (look.joins or 0.0) * JOIN_WIDER)
        reach = size * (math.hypot(far_down, far_out) + rules.line * max(1.0, look.bold) + 0.1) + 4
        side = max(8, math.ceil(reach * 2))
        large = pygame.Surface((side * FINER, side * FINER), pygame.SRCALPHA)
        color = darker(self.color, rules.far_shade * shade) if far else self.color
        draw_foot(
            large, rules, (side * FINER / 2, side * FINER / 2), size * FINER, turn * math.tau / TURN_STEPS,
            -1.0 if mirrored else 1.0, color, self.size, seen / SHOWN_STEPS, look, sole,
        )
        return pygame.transform.smoothscale(large, (side, side)), (side / 2, side / 2)

    def laid(self, name: str, bone: Bone, mirrored: bool, detail: float, lined: bool = True) -> tuple[pygame.Surface, Point] | None:
        """A foot for whoever lays a doll over a skeleton: its picture on the bone that stands
        for it, and where on the picture the ankle is. None for a part that is no foot."""
        if not self.choice.made or name not in self.rules.bones:
            return None
        if name.endswith(self.rules.far):
            return self.picture(name, bone.angle, bone.length, mirrored, detail, lined=lined)
        if self.near_shown < 0.0:
            # Seen from the front the near foot is on the side the body does not face: it
            # points out that way, its bone in a mirror.
            return self.picture(name, -bone.angle, bone.length, not mirrored, detail, -self.near_shown, lined)
        return self.picture(name, bone.angle, bone.length, mirrored, detail, self.near_shown, lined)

    def line_of(self, name: str, bone: Bone, detail: float) -> float:
        """How thick the line round a foot is, in pixels."""
        return self.rules.line * bone.length * detail * self.bold

    def unlined(self, name: str, bone: Bone, mirrored: bool, detail: float) -> tuple[pygame.Surface, Point] | None:
        """The same foot with no line round it, for whoever joins it to its leg."""
        return self.laid(name, bone, mirrored, detail, lined=False)


class Made:
    """Whatever of a doll is made and not drawn, its hands and its feet alike, for whoever lays
    a doll over a skeleton: each is asked in turn for the part wanted."""

    def __init__(self, *kinds: Any) -> None:
        self.kinds = tuple(kind for kind in kinds if kind is not None)

    @property
    def bones(self) -> tuple[str, ...]:
        """The parts a doll is cut without, for these to be laid in their place."""
        return tuple(bone for kind in self.kinds if kind.choice.made for bone in kind.rules.bones)

    def laid(self, name: str, bone: Bone, mirrored: bool, detail: float) -> tuple[pygame.Surface, Point] | None:
        for kind in self.kinds:
            made = kind.laid(name, bone, mirrored, detail)
            if made is not None:
                return made
        return None

    def line_of(self, name: str, bone: Bone, detail: float) -> float:
        return max((kind.line_of(name, bone, detail) for kind in self.kinds if name in kind.rules.bones), default=2.0)

    def unlined(self, name: str, bone: Bone, mirrored: bool, detail: float) -> tuple[pygame.Surface, Point] | None:
        for kind in self.kinds:
            made = kind.unlined(name, bone, mirrored, detail)
            if made is not None:
                return made
        return None


def foot_file(body_id: str) -> str:
    return f"dolls/{body_id}/{FEET_FILE}"


class FootStore:
    """The feet of each doll there is, read the first time they are asked for."""

    def __init__(self, root: Path | None, rules: FootRules) -> None:
        self.root = root
        self.rules = rules
        self._feet: dict[str, Feet] = {}

    def get(self, body_id: str) -> Feet:
        if body_id not in self._feet:
            choice = FootChoice()
            path = self.root / foot_file(body_id) if self.root is not None else None
            if path is not None and path.is_file():
                try:
                    choice = choice_from_data(json.loads(path.read_text(encoding="utf-8")))
                except (OSError, ValueError) as error:
                    logger.warning("What was said of a doll's feet could not be read: %s (%s)", path, error)
            self._feet[body_id] = Feet(self.rules, choice)
        return self._feet[body_id]

    def forget(self, body_id: str) -> None:
        """Have what was said of a body's feet read again the next time it is asked for."""
        self._feet.pop(body_id, None)

    def save(self, body_id: str) -> bool:
        if self.root is None or body_id not in self._feet:
            return False
        try:
            path = self.root / foot_file(body_id)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(self._feet[body_id].choice.to_data(), indent=2) + "\n", encoding="utf-8")
        except OSError:
            return False
        return True
