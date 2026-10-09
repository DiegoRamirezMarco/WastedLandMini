"""Hands that are made and not drawn: a glove, in a colour whoever draws the doll picks.

A hand cut out of a drawing is one picture, and all it can do is turn. One made here can be
opened, shut, and shut just as far as what it holds is thick. So the doll is cut without the
hands that were drawn on it (`Doll(..., without=rules.bones)`), and these are laid where they
were, at the end of each arm, turned as the bone of the hand is.

A hand is drawn as a glove laid flat is, whichever way its arm points: a broad palm with round
corners, fat fingers side by side at the end of it, and a thumb at its side, the side the body
faces. There is one line round the whole of it and none round each finger: between two fingers
there is only the gap between them. Tried first and thrown out: a ball with thin fingers
coming out of one point, each with a line of its own, which was not a hand open and was not
one shut.

Open, its fingers are long and fan apart. As it shuts they come together and bend at the
knuckle towards whoever looks: so they grow short, are a knuckle and no more half way, and
past that lie back over the palm, with a finer line of their own. The thumb swings about where
it begins, from out at the side to across the fingers. Round something held, the fingers lie
across that instead, however thick it is. How it is made, how each way of holding
it is, and which of them goes with which clip is data, in `data/hands.json`.
"""

import json
import logging
import math
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

import pygame

from graphics.cartoon import LINE
from graphics.palette import Color
from graphics.ui_art import darker
from skeleton.rig import Bone

logger = logging.getLogger(__name__)

Point = tuple[float, float]

HANDS_PATH = Path(__file__).resolve().parent.parent / "data" / "hands.json"
HANDS_FILE = "hands.json"
# Times as fine as it is shown a hand is made, and brought down smoothly from.
FINER = 3
# How many ways round, and how many ways between open and shut, a hand is kept ready in.
TURN_STEPS = 96
CURL_STEPS = 20
SPREAD_STEPS = 4
THICK_STEPS = 8
# How far to either side of a hand what it holds is shown, in widths of the palm: the stand-in
# for a thing. And how thick it is, in the same, for each of the palms it is said to be thick.
HELD_REACH = 1.7
HELD_THICK = 0.2
KEPT_HANDS = 900
CLEAR = (0, 0, 0, 0)


@dataclass(frozen=True)
class HandPose:
    """A way of holding a hand: how far shut it is, from open to a fist, and how far apart its
    fingers are, from together to as far as they go."""

    curl: float = 0.0
    spread: float = 0.0
    name: str = ""

    def towards(self, other: "HandPose", share: float) -> "HandPose":
        share = max(0.0, min(1.0, share))
        return HandPose(self.curl + (other.curl - self.curl) * share, self.spread + (other.spread - self.spread) * share)


@dataclass(frozen=True)
class HandRules:
    # The bones of the doll that are its hands, and what the one on the far side ends in.
    bones: tuple[str, ...]
    far: str
    color: Color
    # How much darker the hand of the far side is.
    far_shade: float
    # How many times as long as the bone of the hand a hand is, and the least and most it can be made.
    size: float
    sizes: tuple[float, float]
    # Everything below is a share of how long the hand is, and angles are in degrees.
    # How far along it the palm begins, how wide and how long the palm is, and how round its
    # corners are, as a share of its width.
    palm_from: float
    palm_wide: float
    palm_long: float
    palm_round: float
    # How wide it is at the wrist, against how wide it is at the knuckles, and how round its
    # corners are at the knuckles: at the wrist it is as round as `palm_round` says.
    palm_wrist: float
    palm_knuckles: float
    fingers: int
    finger_counts: tuple[int, int]
    finger_long: float
    # How much of the room each finger has across the palm is left clear beside it, and how far
    # apart two neighbours lean when the fingers are spread.
    finger_gap: float
    finger_fan: float
    # How far a finger is bent at the knuckle in a fist, towards whoever looks: past a right
    # angle it lies back over the palm. And how much of its length shows of one that does.
    finger_folds: float
    finger_folded: float
    # How long each finger is against the longest, by how many there are, from the one
    # furthest from the thumb.
    finger_lengths: dict[int, tuple[float, ...]]
    thumb_long: float
    thumb_thick: float
    # Where the thumb begins, across the hand towards the way the body faces and along it;
    # which way it points from there when the hand is open and when it is a fist, from the way
    # the hand runs; between how far shut and how far shut the hand is it comes across; and
    # how much shorter it shows half way, when it is up off the palm to pass over the fingers.
    thumb_root: Point
    thumb_open: float
    thumb_shut: float
    thumb_swings: tuple[float, float]
    thumb_lifts: float
    line: float
    # How wide a line inside a hand is, against the one round it.
    inner_line: float
    poses: dict[str, HandPose]
    at_rest: str
    # The way of holding a hand that goes with each clip.
    clips: dict[str, str]
    # How thick what is held can be, in palms, and how much less shut the thickest has a hand.
    held_thick: tuple[float, float]
    held_opens: float
    # How fast a hand goes from one way of holding it to another: shares of the way a second.
    quick: float
    # How far round from facing the screen a body may be, in degrees, and still show the hand
    # of its far side as the other hand it is, its thumb on the other side. Past right behind,
    # it is so however the body is turned: the same hand seen from its side and the other from
    # anywhere else, it changed over as the body turned, all at once.
    far_other_to: float = 0.0
    # How long the lines on the back of a hand are, one between each two fingers, as a share of
    # how long the palm is: what tells its back from its palm when it is open.
    darts: float = 0.0
    # The least and the most times as thick as that the line round a hand may be made, and how
    # far back up the arm it is joined to a palm begins, under the end of it.
    lines: tuple[float, float] = (0.0, 2.5)
    palm_lap: float = 0.1
    # The part of a doll whose colour, at its far end, a hand has until one is picked for it.
    matches: str = ""

    @property
    def palm_at(self) -> float:
        """How far along the hand the middle of the palm is."""
        return self.palm_from + self.palm_long / 2.0

    def lengths(self, fingers: int) -> tuple[float, ...]:
        """How long each of so many fingers is against the longest."""
        return self.finger_lengths.get(fingers) or (1.0,) * fingers

    def pose_for(self, clip: str | None) -> HandPose:
        """How a hand is held in a clip: as the clip has it, or else at rest."""
        return self.poses[self.clips.get(clip or "", self.at_rest)]

    def holding(self, thick: float) -> HandPose:
        """A hand shut on something that thick, in palms: the thicker, the less shut."""
        low, high = self.held_thick
        share = max(0.0, min(1.0, (thick - low) / (high - low))) if high > low else 0.0
        grip = self.poses.get("grip", HandPose(0.8))
        return replace(grip, curl=grip.curl * (1.0 - self.held_opens * share))


def rules_from_data(data: dict[str, Any]) -> HandRules:
    fingers, thumb, palm, held = data["fingers"], data["thumb"], data["palm"], data.get("held", {})
    poses = {
        str(pose_id): HandPose(float(values.get("curl", 0.0)), float(values.get("spread", 0.0)), str(values.get("name", pose_id)))
        for pose_id, values in data["poses"].items()
    }
    at_rest = str(data.get("at_rest", next(iter(poses))))
    clips = {str(clip): str(pose) for clip, pose in data.get("clips", {}).items()}
    for pose in (at_rest, *clips.values()):
        if pose not in poses:
            raise ValueError(f"A hand is to be held a way there is not: {pose}")
    red, green, blue = data.get("color", (214, 170, 130))
    return HandRules(
        tuple(map(str, data["bones"])), str(data.get("far", "_left")), (int(red), int(green), int(blue)),
        float(data.get("far_shade", 0.0)), float(data.get("size", 1.0)),
        (float(data.get("sizes", (0.5, 2.0))[0]), float(data.get("sizes", (0.5, 2.0))[1])),
        float(palm["from"]), float(palm["wide"]), float(palm["long"]), float(palm.get("round", 0.3)),
        float(palm.get("wrist", 1.0)), float(palm.get("knuckles", 0.07)),
        int(fingers["count"]), (int(fingers.get("counts", (2, 4))[0]), int(fingers.get("counts", (2, 4))[1])),
        float(fingers["long"]), float(fingers.get("gap", 0.1)), float(fingers.get("fan", 12.0)),
        float(fingers.get("folds", 165.0)), float(fingers.get("folded", 0.6)),
        {int(count): tuple(float(share) for share in shares) for count, shares in fingers.get("lengths", {}).items()},
        float(thumb["long"]), float(thumb["thick"]), (float(thumb["root"][0]), float(thumb["root"][1])),
        float(thumb["open"]), float(thumb["shut"]),
        (float(thumb.get("swings", (0.0, 1.0))[0]), float(thumb.get("swings", (0.0, 1.0))[1])), float(thumb.get("lifts", 0.0)),
        float(data.get("line", 0.07)), float(data.get("inner_line", 1.0)), poses, at_rest, clips,
        (float(held.get("thick", (0.0, 1.0))[0]), float(held.get("thick", (0.0, 1.0))[1])), float(held.get("opens", 0.5)),
        float(data.get("quick", 9.0)), float(data.get("far_other_to", 0.0)), float(data.get("darts", 0.0)),
        (float(data.get("lines", (0.0, 2.5))[0]), float(data.get("lines", (0.0, 2.5))[1])), float(palm.get("lap", 0.1)),
        str(data.get("matches", "")),
    )


def load_rules(path: Path = HANDS_PATH) -> HandRules:
    return rules_from_data(json.loads(path.read_text(encoding="utf-8")))


@dataclass(frozen=True)
class HandChoice:
    """What whoever draws a doll has said of its hands: whether they are made, and not the ones
    drawn on it, their colour, how large they are and how many fingers they have beside the
    thumb, and the colour of the line round them and how many times as thick as usual it is."""

    made: bool = False
    color: Color | None = None
    size: float | None = None
    fingers: int | None = None
    line_color: Color | None = None
    line: float | None = None

    def to_data(self) -> dict[str, Any]:
        return {
            "made": self.made, "color": list(self.color) if self.color else None, "size": self.size, "fingers": self.fingers,
            "line_color": list(self.line_color) if self.line_color else None, "line": self.line,
        }


def choice_from_data(data: Any) -> HandChoice:
    if not isinstance(data, dict):
        return HandChoice()
    color, ink = data.get("color"), data.get("line_color")
    try:
        return HandChoice(
            bool(data.get("made", False)),
            (int(color[0]), int(color[1]), int(color[2])) if color else None,
            float(data["size"]) if data.get("size") is not None else None,
            int(data["fingers"]) if data.get("fingers") is not None else None,
            (int(ink[0]), int(ink[1]), int(ink[2])) if ink else None,
            float(data["line"]) if data.get("line") is not None else None,
        )
    except (TypeError, ValueError, IndexError):
        return HandChoice()


@dataclass(frozen=True)
class Look:
    """How a hand or a foot that is made is finished, apart from what it is doing.

    `ink` is the colour of its lines and `bold` how many times as thick as the rules have them
    they are: none round it at 0. Not `lined`, it has no line round it whatever `bold` is, only
    those inside it: what it is where it is joined to its limb (`graphics/joined.py`). `joins`
    is how far to either side of its joint the limb it is on goes there, as a share of how
    long this is: it begins that wide, and under the end of the limb, so that the two are one
    shape. With none it begins as wide as the rules have it.
    """

    ink: Color = LINE
    bold: float = 1.0
    lined: bool = True
    joins: float | None = None

    def line(self, rules_line: float, long: float) -> float:
        """How thick the line round it is, in pixels."""
        return max(1.0, rules_line * long * self.bold) if self.lined and self.bold > 0 else 0.0

    def inner(self, rules_line: float, long: float, share: float = 1.0) -> float:
        """How thick a line inside it is: no thinner than half of what the rules have, so
        that one with no line round it still has its fingers told apart."""
        return max(1.0, rules_line * long * share * max(self.bold, 0.5))


# How much wider than the limb it is on what is made begins: bent, a limb is a little wider
# than it was drawn, and none of it is to show beside what is over it.
JOIN_WIDER = 1.08
# How far a line may be made thinner or thicker with one press.
LINE_STEP = 0.25
# In how many steps the far side goes from in the shade to out of it as a body turns.
SHADE_STEPS = 4
# A palm joined to an arm widens in a curve: in so many straight pieces, as wide as it gets by
# this share of its length, and the more quickly at first the greater the swell.
PALM_PIECES = 8
PALM_WIDE_BY = 0.62
PALM_SWELL = 2.4


def _capsule(target: pygame.Surface, color: tuple[int, ...], start: Point, end: Point, radius: float) -> None:
    radius = max(1, round(radius))
    pygame.draw.line(target, color, start, end, radius * 2)
    pygame.draw.circle(target, color, start, radius)
    pygame.draw.circle(target, color, end, radius)


def _pad(target: pygame.Surface, color: tuple[int, ...], corners: list[Point], radius: float) -> None:
    """A shape with straight sides and corners as round as it is told: everything within
    `radius` of the corners given and of what lies between them."""
    pygame.draw.polygon(target, color, corners)
    for start, end in zip(corners, corners[1:] + corners[:1]):
        _capsule(target, color, start, end, radius)


def _as_one(target: pygame.Surface, shapes: list[tuple], fill: Color, line: float, ink: Color = LINE) -> None:
    """Draw several shapes as one thing: a dark line round all of them together, and none where
    one lies against another. Each is the two ends and the half width of a round-ended stroke,
    or the corners of a pad and how round they are."""
    for grown, color in ((line, (*ink, 255)), (0.0, (*fill, 255))):
        for shape in shapes:
            if len(shape) == 3:
                _capsule(target, color, shape[0], shape[1], shape[2] + grown)
            else:
                _pad(target, color, shape[0], shape[1] + grown)


def _over(
    target: pygame.Surface, shapes: list[tuple], fill: Color, line: float, cut: tuple[Point, Point] | None = None, ink: Color = LINE
) -> None:
    """Draw shapes as one thing over what is there already, and with `cut`, a place and a way,
    nothing of them behind that place: there they are one with what is under them."""
    layer = pygame.Surface(target.get_size(), pygame.SRCALPHA)
    _as_one(layer, shapes, fill, line, ink)
    if cut is not None:
        (x, y), (run_x, run_y) = cut
        far = float(sum(target.get_size()))
        sides = [(x - run_y * far * way, y + run_x * far * way) for way in (1.0, -1.0)]
        pygame.draw.polygon(layer, (0, 0, 0, 0), [*sides, *((side_x - run_x * far, side_y - run_y * far) for side_x, side_y in reversed(sides))])
    target.blit(layer, (0, 0))


def draw_hand(
    target: pygame.Surface,
    rules: HandRules,
    wrist: Point,
    long: float,
    angle: float,
    forwards: float,
    pose: HandPose,
    color: Color,
    fingers: int,
    stick: tuple[float, Color] | None = None,
    back: bool = False,
    look: Look = Look(),
) -> None:
    """Draw one hand on a surface, as large as it is told.

    `wrist` is where it hangs from and `long` how long it is, in pixels. `angle` is which way it
    runs from there, in radians from straight down and anticlockwise as bones are. `forwards`
    is 1 for a body that faces right and -1 for one that faces left: the side its thumb is on.
    `stick` is something held across the palm, how thick in palms and of what colour: the
    fingers are shut over it.

    `back` is whether it is seen from its back and not from its palm. Then its fingers shut
    away from whoever looks, behind the palm, and its thumb goes behind it too: a fist is the
    back of a hand with its knuckles along the end of it. What it holds is behind it. And it
    has a short line on it between each two fingers, as a glove has, which a palm has not.

    `look` is how it is finished: the colour and the thickness of its lines, and how wide the
    arm it is joined to is where it begins (`Look`).
    """
    along = (math.sin(angle), math.cos(angle))
    ahead = (math.cos(angle) * forwards, -math.sin(angle) * forwards)

    def at(across: float, down: float) -> Point:
        """A place on the hand: that far towards the way the body faces, and that far along it."""
        return (wrist[0] + (ahead[0] * across + along[0] * down) * long, wrist[1] + (ahead[1] * across + along[1] * down) * long)

    line = look.line(rules.line, long)
    curl, spread = max(0.0, min(1.0, pose.curl)), max(0.0, min(1.0, pose.spread))
    if stick is not None:
        curl = 1.0
    wide, top, foot = rules.palm_wide, rules.palm_from, rules.palm_from + rules.palm_long
    corner = rules.palm_knuckles
    broad = wide / 2 - corner
    if look.joins is None:
        # The palm: round at the wrist, where it is narrower, and all but square at the
        # knuckles, where the fingers begin as wide as it is.
        turn = min(rules.palm_round * wide, wide * rules.palm_wrist / 2, rules.palm_long / 2)
        narrow = wide * rules.palm_wrist / 2
        palm = [
            (at(turn - narrow, top + turn), at(narrow - turn, top + turn), turn * long),
            ([at(corner - narrow, top + turn), at(narrow - corner, top + turn), at(broad, foot - corner), at(-broad, foot - corner)], corner * long),
        ]
    else:
        # Joined to an arm, it begins as wide as the arm is there, a little way back up it and
        # under its end, and widens from that to the knuckles: quickly at first, as a hand does.
        narrow = max(corner + 0.01, min(wide / 2, look.joins * JOIN_WIDER)) - corner
        begins = top - rules.palm_lap
        high = foot - corner - begins
        right = [
            (narrow + (broad - narrow) * (1.0 - (1.0 - step / PALM_PIECES) ** PALM_SWELL), begins + corner + high * PALM_WIDE_BY * step / PALM_PIECES)
            for step in range(PALM_PIECES + 1)
        ] + [(broad, foot - corner)]
        palm = [([at(x, y) for x, y in right] + [at(-x, y) for x, y in reversed(right)], corner * long)]
    # The thumb swings about where it begins, inside the palm: out at the side when the hand
    # is open, and across the fingers when it is shut.
    root = rules.thumb_root
    begins, ends = rules.thumb_swings
    across = max(0.0, min(1.0, (curl - begins) / max(0.01, ends - begins)))
    across = across * across * (3.0 - 2.0 * across)
    pointing = math.radians(rules.thumb_open + (rules.thumb_shut - rules.thumb_open) * across)
    shown = rules.thumb_long * (1.0 - rules.thumb_lifts * math.sin(math.pi * across))
    thumb = (at(*root), at(root[0] + math.sin(pointing) * shown, root[1] + math.cos(pointing) * shown), rules.thumb_thick * long / 2.0)

    room = wide / fingers
    thick = room * (1.0 - rules.finger_gap) / 2.0
    lengths = rules.lengths(fingers)
    knuckles = [((index - (fingers - 1) / 2) * room, foot - thick * 0.7) for index in range(fingers)]
    # A finger bends at the knuckle towards whoever looks: so it is shorter the more it is
    # bent, a knuckle and no more at a right angle, and past that it lies back over the palm.
    bent = math.cos(math.radians(rules.finger_folds * curl))
    out, folded = [], []
    for index, (x, y) in enumerate(knuckles):
        if stick is not None and not back:
            continue
        reach = rules.finger_long * lengths[index] * bent
        if bent >= 0.0:
            lean = math.radians((index - (fingers - 1) / 2) * rules.finger_fan * spread)
            out.append((at(x, y), at(x + math.sin(lean) * reach, y + math.cos(lean) * reach), thick * long))
        else:
            folded.append((at(x, y), at(x, y + reach * rules.finger_folded), thick * long))
    inner = look.inner(rules.line, long, rules.inner_line)
    ink = look.ink
    # What is held has the line the rules have, whatever is said of the hand's.
    rim = max(1.0, rules.line * long) if look.lined else 0.0
    if stick is not None:
        half = max(0.02, stick[0] * wide * HELD_THICK / 2.0)
        lies = top + rules.palm_long * 0.62
        held = [(at(-wide * HELD_REACH, lies), at(wide * HELD_REACH, lies), half * long)]
    if back:
        # From its back, what is held is behind the hand, and so is whatever of its fingers
        # and its thumb is folded: of them there is only what reaches past the palm.
        if stick is not None:
            _as_one(target, held, stick[1], rim)
        _as_one(target, [*palm, thumb, *out, *folded], color, line, ink)
        # The lines of a glove, from between the knuckles back along the hand: longer the
        # more it is shut, as the back of a fist is drawn.
        dart = rules.palm_long * rules.darts * (1.0 + 0.5 * max(0.0, (curl - 0.45) / 0.55))
        if dart > 0.01:
            for (one, y), (other, _) in zip(knuckles, knuckles[1:]):
                seam = (one + other) / 2.0
                pygame.draw.line(target, (*ink, 255), at(seam, y + thick * 0.15), at(seam, y - dart), max(1, round(inner)))
        return
    if stick is not None:
        # What is held lies across the palm, and the fingers across that: from beyond it back
        # on to the palm, side by side, however thick it is.
        folded = [(at(x, lies + half + thick * 1.2), at(x, lies - half - thick * 0.7), thick * long) for x, _ in knuckles]
    # One line round the palm, the thumb and whatever fingers reach out of it.
    _as_one(target, [*palm, thumb, *out, *folded], color, line, ink)
    if stick is not None:
        _as_one(target, held, stick[1], rim)
    if folded:
        _over(target, folded, color, inner, ink=ink)
    # Where the thumb lies over the rest it has a line of its own, but not where it begins:
    # there it is one with the palm. Out at the side it has none but the one round the hand,
    # and the line comes from its tip as it comes across.
    heading = (thumb[1][0] - thumb[0][0], thumb[1][1] - thumb[0][1])
    length = math.hypot(*heading) or 1.0
    heading = (heading[0] / length, heading[1] / length)
    begun = thumb[2] * 0.8 + (1.0 - across) ** 2 * (length + thumb[2])
    _over(target, [thumb], color, inner, ((thumb[0][0] + heading[0] * begun, thumb[0][1] + heading[1] * begun), heading), ink)


class Hands:
    """The hands of one doll, made at whatever size and turn they are asked for, and kept."""

    def __init__(self, rules: HandRules, choice: HandChoice = HandChoice()) -> None:
        self.rules = rules
        self.choice = choice
        self._kept: dict[tuple, tuple[pygame.Surface, Point]] = {}
        # How each hand is held right now, by its bone, on the way to how it is to be held.
        self._held: dict[str, HandPose] = {}
        # Whether the hand of the far side is shown as the other hand, its thumb on the other side.
        self.far_other = False
        # The colour of the arm they are on, where whoever has the doll has told it: theirs
        # until one is picked for them.
        self.natural: Color | None = None
        # How much of the shade the hand of the far side is in, with the body turned as it is.
        self.shade = 1.0
        # And how far to either side of the wrist that arm goes, in the skeleton's measure: a
        # hand begins that wide. None where nobody has said, and a hand is as the rules have it.
        self.joins: float | None = None

    @property
    def color(self) -> Color:
        return self.choice.color or self.natural or self.rules.color

    @property
    def ink(self) -> Color:
        """The colour of its lines."""
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

    @property
    def fingers(self) -> int:
        low, high = self.rules.finger_counts
        return max(low, min(high, self.choice.fingers if self.choice.fingers is not None else self.rules.fingers))

    def choose(self, **changes: Any) -> None:
        """Change what has been said of these hands."""
        self.choice = replace(self.choice, **changes)
        self._kept.clear()

    def settle(self, pose: HandPose, seconds: float | None = None, bone: str | None = None) -> None:
        """Have a hand, or both, go towards a way of being held, by as much as the time gone by
        allows. With no time given they are held that way at once."""
        share = 1.0 if seconds is None else min(1.0, seconds * self.rules.quick)
        for name in (bone,) if bone is not None else self.rules.bones:
            self._held[name] = self._held.get(name, pose).towards(pose, share)

    def turned(self, yaw: float | None) -> None:
        """Say how far round from facing the screen the body they are on is, in degrees: with
        None, seen from its side."""
        # From as far round behind as from the front, it is the other hand as well.
        self.far_other = yaw is not None and min(abs(yaw), 180.0 - abs(yaw)) < self.rules.far_other_to
        # And it is in the shade of the body only as far as the body is seen from its side.
        self.shade = 1.0 if yaw is None else abs(math.sin(math.radians(yaw)))

    def held(self, bone: str) -> HandPose:
        return self._held.get(bone, self.rules.poses[self.rules.at_rest])

    def picture(
        self,
        name: str,
        angle: float,
        long: float,
        mirrored: bool,
        detail: float,
        pose: HandPose | None = None,
        stick: tuple[float, Color] | None = None,
        other: bool | None = None,
        back: bool | None = None,
        lined: bool = True,
    ) -> tuple[pygame.Surface, Point]:
        """One hand as it is shown, and where on that picture its wrist is.

        `name` is which hand it is, by the doll's own name for its bone, `angle` which way that
        bone runs and `long` how long the bone is, in the skeleton's measure. `detail` is how
        many pixels go to one of the skeleton's. `other` is whether the hand of the far side
        has its thumb on the other side: as the body is turned, if it is not said. `back` is
        whether it is seen from its back: if it is not said, the near one is and the far one
        never is, so that of the two it is always the far one whose fingers are seen shut.
        Tried and thrown out: the far one seen from its back too once the body had turned,
        which left a body at three quarters with two backs of hands and no fingers to see.
        """
        pose = pose if pose is not None else self.held(name)
        far = name.endswith(self.rules.far)
        if back is None:
            back = not far
        if far and (self.far_other if other is None else other):
            mirrored = not mirrored
        turn = round(angle / math.tau * TURN_STEPS) % TURN_STEPS
        curl = round(max(0.0, min(1.0, pose.curl)) * CURL_STEPS)
        spread = round(max(0.0, min(1.0, pose.spread)) * SPREAD_STEPS)
        thick = (round(stick[0] * THICK_STEPS), stick[1]) if stick is not None else None
        size = round(long * self.size * detail * 4) / 4
        joins = round(self.joins / (long * self.size) * 50) / 50 if self.joins and long > 0 else None
        look = Look(self.ink, self.bold, lined, joins)
        shade = round(self.shade * SHADE_STEPS) / SHADE_STEPS if far else 0.0
        key = (far, shade, mirrored, back, look, turn, curl, spread, thick, size, self.color, self.fingers)
        if key not in self._kept:
            if len(self._kept) > KEPT_HANDS:
                self._kept.clear()
            self._kept[key] = self._made(far, mirrored, turn, curl, spread, thick, size, back, look, shade)
        return self._kept[key]

    def _made(
        self, far: bool, mirrored: bool, turn: int, curl: int, spread: int, thick: tuple[int, Color] | None, size: float,
        back: bool = False, look: Look = Look(), shade: float = 1.0,
    ) -> tuple[pygame.Surface, Point]:
        rules = self.rules
        # Room for the hand whichever way it runs, and for what it holds across it.
        reach = size * (1.9 if thick is not None else 1.5) + 4
        side = max(8, math.ceil(reach * 2))
        large = pygame.Surface((side * FINER, side * FINER), pygame.SRCALPHA)
        color = darker(self.color, rules.far_shade * shade) if far else self.color
        draw_hand(
            large, rules, (side * FINER / 2, side * FINER / 2), size * FINER, turn * math.tau / TURN_STEPS,
            -1.0 if mirrored else 1.0, HandPose(curl / CURL_STEPS, spread / SPREAD_STEPS), color, self.fingers,
            (thick[0] / THICK_STEPS, thick[1]) if thick is not None else None, back, look,
        )
        return pygame.transform.smoothscale(large, (side, side)), (side / 2, side / 2)

    def laid(self, name: str, bone: Bone, mirrored: bool, detail: float) -> tuple[pygame.Surface, Point] | None:
        """A hand for whoever lays a doll over a skeleton: its picture on the bone that stands
        for it, and where on the picture the joint it hangs from is. None for a part that is no hand."""
        if not self.choice.made or name not in self.rules.bones:
            return None
        return self.picture(name, bone.angle, bone.length, mirrored, detail)

    def line_of(self, name: str, bone: Bone, detail: float) -> float:
        """How thick the line round a hand is, in pixels."""
        return self.rules.line * bone.length * self.size * detail * self.bold

    def unlined(self, name: str, bone: Bone, mirrored: bool, detail: float) -> tuple[pygame.Surface, Point] | None:
        """The same hand with no line round it, for whoever joins it to its arm."""
        if not self.choice.made or name not in self.rules.bones:
            return None
        return self.picture(name, bone.angle, bone.length, mirrored, detail, lined=False)


def hand_file(body_id: str) -> str:
    return f"dolls/{body_id}/{HANDS_FILE}"


class HandStore:
    """The hands of each doll there is, read the first time they are asked for."""

    def __init__(self, root: Path | None, rules: HandRules) -> None:
        self.root = root
        self.rules = rules
        self._hands: dict[str, Hands] = {}

    def get(self, body_id: str) -> Hands:
        if body_id not in self._hands:
            choice = HandChoice()
            path = self.root / hand_file(body_id) if self.root is not None else None
            if path is not None and path.is_file():
                try:
                    choice = choice_from_data(json.loads(path.read_text(encoding="utf-8")))
                except (OSError, ValueError) as error:
                    logger.warning("What was said of a doll's hands could not be read: %s (%s)", path, error)
            self._hands[body_id] = Hands(self.rules, choice)
        return self._hands[body_id]

    def forget(self, body_id: str) -> None:
        """Have what was said of a body's hands read again the next time it is asked for."""
        self._hands.pop(body_id, None)

    def save(self, body_id: str) -> bool:
        if self.root is None or body_id not in self._hands:
            return False
        try:
            path = self.root / hand_file(body_id)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(self._hands[body_id].choice.to_data(), indent=2) + "\n", encoding="utf-8")
        except OSError:
            return False
        return True
