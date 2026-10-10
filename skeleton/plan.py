"""The body plan: which joints and bones a body has, how it stands and how it moves. All of it data.

Distances are in art pixels. A joint stands at `(x, y)` from the spot on the ground between the
feet: `x` grows to the right of the screen and `y` grows downwards, so everything above the ground
has a negative `y`. Whole numbers fall on the middle of a pixel.

An angle is how far a bone has turned from pointing straight down, anticlockwise as seen on screen:
a hanging arm at 90 degrees points to the right of the screen.
"""

import functools
import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

Point = tuple[float, float]

PLAN_PATH = Path(__file__).resolve().parent.parent / "data" / "skeleton.json"
# How a body is posed: seen from the front or from its right side.
VIEWS = ("front", "side")
# How a body is dressed. From behind it is posed as from the front and drawn with other art.
SKIN_VIEWS = ("front", "side", "back")
# For each way a body can face: the pose view, the skin view, whether the pose is mirrored, and
# whether its two sides change places as well. Turned to face the other way a body is mirrored,
# and seen from the side the limb that was nearer the viewer is then the further one.
FACINGS: dict[str, tuple[str, str, bool, bool]] = {
    "down": ("front", "front", False, False),
    "up": ("front", "back", True, False),
    "right": ("side", "side", False, False),
    "left": ("side", "side", True, True),
    # A paper doll is only ever seen from the side, with the build of its own that its drawing has.
    "doll_right": ("doll", "side", False, False),
    "doll_left": ("doll", "side", True, True),
}
SIDES = ("_left", "_right")
ROOT_KEY = "root"
# In a key of a clip: when in the clip it comes. In a clip: that it is done once and does not come round.
AT_KEY = "at"
ONCE_KEY = "once"
# In a clip: how something with a handle is held while it goes on.
GRIP_KEY = "grip"
# The places a body plan may name for the hand that holds and for the other one: the tip of its
# fingers, which is where a small thing sits, and its wrist.
HELD_ANCHORS = ("held_item", "held_wrist")
OTHER_ANCHORS = ("other_item", "other_wrist")
IDLE_CLIP = "idle"


def other_side(name: str) -> str:
    """The same joint, bone or part on the other side of the body. Names without a side are their own."""
    for side, opposite in (SIDES, SIDES[::-1]):
        if name.endswith(side):
            return name[: -len(side)] + opposite
    return name


def angle_of(dx: float, dy: float) -> float:
    """The angle of a direction, by the convention at the top of this module."""
    return math.atan2(dx, dy)


def wrapped(angle: float) -> float:
    """The same angle between minus half a turn and half a turn."""
    return (angle + math.pi) % math.tau - math.pi


@dataclass(frozen=True)
class JointSpec:
    name: str
    mass: float = 1.0
    # How far above the ground its middle comes to rest.
    radius: float = 1.0


@dataclass(frozen=True)
class BoneSpec:
    """A segment between two joints. `start` is the end nearer the root of the body."""

    name: str
    start: str
    end: str


@dataclass(frozen=True)
class LimitSpec:
    """How far a bone may turn against another, in degrees, seen from the side and from the front.

    From the side a positive angle is towards where the body faces. From the front it is away from
    the middle of the body for a bone that has a side, and to the right of the screen otherwise.
    """

    bone: str
    ref: str
    ref_reversed: bool
    ranges: dict[str, tuple[float, float]]


@dataclass(frozen=True)
class SkinSpec:
    """What is drawn over a bone: a sprite turned with it, or a strip of colour laid along it."""

    bone: str
    kind: str
    cell: str
    anchor: str = "middle"


@dataclass(frozen=True)
class Keyframe:
    root: Point = (0.0, 0.0)
    # Per bone, how far it is turned from its rest direction, in radians, and how long it looks.
    bones: dict[str, tuple[float, float]] = field(default_factory=dict)
    # When in its clip it comes, from 0 to 1. None for a key spaced evenly with the others.
    at: float | None = None


def added(frame: Keyframe, layer: Keyframe, share: float = 1.0) -> Keyframe:
    """One pose laid over another: every bone the second names is turned by as much more, and is
    as many times as long again, and the whole body is moved by as much. `share` is how much of
    the second is laid on, from none of it at 0."""
    bones = dict(frame.bones)
    for name, (angle, scale) in layer.bones.items():
        turned, long = bones.get(name, (0.0, 1.0))
        bones[name] = (turned + angle * share, long * (1.0 + (scale - 1.0) * share))
    return Keyframe((frame.root[0] + layer.root[0] * share, frame.root[1] + layer.root[1] * share), bones)


@dataclass(frozen=True)
class Grip:
    """How something with a handle is held while a clip goes on.

    In one hand, the handle comes out of the palm at an angle to the way the hand points. In
    both, it runs from the palm of the other hand through that of the hand that holds, which
    is the nearer to its far end: where the two hands go, the thing goes.
    """

    both: bool = False
    # How far along its handle, as a share of its length, the thing is held: by the one hand, or
    # by the other one of the two.
    at: float = 0.2
    # In one hand: how far the handle is turned from the way the hand points, in radians.
    turn: float = 0.0


@dataclass(frozen=True)
class Spring:
    """How a bone is drawn towards where its clip has it: `pull` is how hard, for how far off it
    is, and `hold` how much it is slowed, for how fast it is going."""

    pull: float = 400.0
    hold: float = 28.0
    # How far behind it is left by the swing of the bone it hangs from: seconds of that swing.
    drag: float = 0.0

    @classmethod
    def of(cls, speed: float, bounce: float = 0.0, drag: float = 0.0) -> "Spring":
        """A spring by how fast it gets there, and by how much it goes past and comes back: not
        at all at 0, and the nearer 1 the longer it goes on swinging."""
        return cls(speed * speed, 2.0 * (1.0 - bounce) * speed, drag)

    @functools.cache
    def stepped(self, step: float) -> tuple[float, float, float, float]:
        """What a step of so many seconds makes of how far off something is and how fast it is
        going: how much of each goes into how far off it is then, and into how fast it goes.

        This is what the spring does, worked out and not added up in small pieces, so a stiff
        spring is as steady as a loose one however long the step.
        """
        pull, half = self.pull, self.hold / 2.0
        if pull <= 0.0:
            return (1.0, step, 0.0, 1.0)
        swing = pull - half * half
        fade = math.exp(-half * step)
        if swing > 1e-9:
            # It goes past and comes back, less each time.
            rate = math.sqrt(swing)
            sine, cosine = math.sin(rate * step), math.cos(rate * step)
            return (
                fade * (cosine + half / rate * sine),
                fade * sine / rate,
                -fade * pull / rate * sine,
                fade * (cosine - half / rate * sine),
            )
        if swing > -1e-9:
            # It gets there as fast as can be without going past.
            return (fade * (1.0 + half * step), fade * step, -fade * pull * step, fade * (1.0 - half * step))
        # It creeps there.
        root = math.sqrt(-swing)
        slow, quick = -half + root, -half - root
        slower, quicker = math.exp(slow * step), math.exp(quick * step)
        both = (slower - quicker) / (slow - quick)
        return (
            (slow * quicker - quick * slower) / (slow - quick),
            both,
            -pull * both,
            (slow * slower - quick * quicker) / (slow - quick),
        )


@dataclass(frozen=True)
class Footing:
    """Which limbs a body stands on, and how they keep their feet on the ground.

    A clip moves the whole body with `root`: down as it takes a weight, up and forward as it
    lunges. A foot that the clip has on the ground stays where it was, and its leg bends or is
    drawn out to let the body go. One the clip has lifted goes with the body.
    """

    # The views a body is posed in this way.
    views: frozenset[str] = frozenset()
    # For each leg: the bone from the hip, and the one from the knee to the foot.
    legs: tuple[tuple[str, str], ...] = ()
    # How far off the ground a clip has to hold a foot for it to go wholly with the body.
    free: float = 1.0
    # How many times its length a leg may be drawn out before its foot leaves the ground.
    stretch: float = 1.12
    # How far off the ground a clip may hold a foot and it is still on it: a foot is not left
    # hanging a hair above the ground by a leg that has not quite settled.
    hold: float = 0.0
    # How far off the ground a foot is kept level, its sole flat to the ground whichever way
    # its clip turns it. Twice as far up it is wholly as its clip has it, as in a kick or a
    # jump. At 0 no foot is ever levelled.
    level: float = 0.0


@dataclass(frozen=True)
class LifeSettings:
    """What a body shown moving does besides what it is given to do, by the clips that show it."""

    # A clip laid over whatever else the body is doing, and how many turns of it a second.
    breath: str | None = None
    breath_rate: float = 0.25
    # The clip a body with nothing to do stands in, in place of standing stock still.
    stand: str | None = None
    stand_rate: float = 0.1
    # Clips done once, now and then, by a body with nothing to do: how many seconds go by
    # between one and the next, at the least and at the most, and how many turns of one a second.
    fidgets: tuple[str, ...] = ()
    every: Point = (8.0, 20.0)
    fidget_rate: float = 0.5


@dataclass(frozen=True)
class MotionSettings:
    """How loosely the bones of a body that is shown moving follow its clips."""

    # The spring of any bone that has none of its own, and that of the body as a whole.
    spring: Spring = Spring()
    root: Spring = Spring()
    springs: dict[str, Spring] = field(default_factory=dict)
    # The speed a body is given when it takes up something else: the whole of it in pixels a
    # second, and each bone in radians a second and in lengths of itself a second.
    jolt_root: Point = (0.0, 0.0)
    jolt_bones: dict[str, tuple[float, float]] = field(default_factory=dict)
    # Seconds to a step of the springs, and how many are caught up with after a stall.
    step: float = 1.0 / 60.0
    max_steps: int = 4


@dataclass(frozen=True)
class PhysicsSettings:
    # Pixels per second squared.
    gravity: float = 320.0
    # What is left of a joint's speed after each step.
    damping: float = 0.985
    # How much of its speed along the ground a joint loses on each step it lies there.
    friction: float = 0.5
    bounce: float = 0.15
    iterations: int = 4
    step: float = 1.0 / 60.0
    max_steps: int = 4
    limit_stiffness: float = 0.6
    # Pixels per second under which a body counts as lying still, and for how long before it sleeps.
    sleep_speed: float = 4.0
    sleep_after: float = 0.6
    # Seconds after which a limp body is left as it lies, however restless.
    rest_after: float = 6.0


@dataclass(frozen=True)
class SkeletonPlan:
    root: str
    joints: dict[str, JointSpec]
    bones: dict[str, BoneSpec]
    braces: tuple[tuple[str, str], ...]
    # The bone each part hangs from, by part ID. Cutting that bone loose takes the part off.
    parts: dict[str, str]
    limits: dict[str, LimitSpec]
    rests: dict[str, dict[str, Point]]
    # Bones from the furthest to the nearest, by skin view.
    orders: dict[str, tuple[str, ...]]
    skins: dict[str, SkinSpec]
    clips: dict[str, dict[str, tuple[Keyframe, ...]]]
    physics: PhysicsSettings = field(default_factory=PhysicsSettings)
    # Views that are another view with a rest of their own: they take its clips and its limits.
    likes: dict[str, str] = field(default_factory=dict)
    # Bones that turn as another does where a clip does not say otherwise: a hand with its forearm.
    follows: dict[str, str] = field(default_factory=dict)
    # Semantic places presentation may attach things to, kept in the body-plan data so callers do
    # not need to know any particular joint name.
    anchors: dict[str, str] = field(default_factory=dict)
    # The clips that are done once, from their first key to their last, and do not come round.
    once: frozenset[str] = frozenset()
    motion: MotionSettings = field(default_factory=MotionSettings)
    footing: Footing = field(default_factory=Footing)
    life: LifeSettings = field(default_factory=LifeSettings)
    # How something with a handle is held during a clip, for the clips in which something is.
    grips: dict[str, Grip] = field(default_factory=dict)
    # Per pose view and bone, how long it is and which way it points while the body stands at rest.
    _at_rest: dict[str, dict[str, tuple[float, float]]] = field(init=False, repr=False, compare=False)
    # The bone each bone hangs from, from the root outwards. None for one that hangs from the root.
    hangs_from: dict[str, str | None] = field(init=False, repr=False, compare=False)
    _beyond: dict[str, tuple[str, ...]] = field(init=False, repr=False, compare=False)
    _soles: dict[str, tuple[tuple[str, str, tuple[str, ...]], ...]] = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        ends = {bone.end: bone.name for bone in self.bones.values()}
        object.__setattr__(self, "hangs_from", {bone.name: ends.get(bone.start) for bone in self.bones.values()})
        # For each leg a body stands on: its foot, and every joint that hangs from that.
        beyond = {shin: tuple(self.bones[name].end for name in self.bones_beyond(shin)) for _, shin in self.footing.legs}
        object.__setattr__(self, "_beyond", beyond)
        # For each such leg: the bones that hang from its foot, each with every joint beyond it.
        soles = {
            shin: tuple(
                (bone.start, bone.end, tuple(self.bones[name].end for name in self.bones_beyond(bone.name)))
                for bone in self.bones.values()
                if bone.start == self.bones[shin].end
            )
            for _, shin in self.footing.legs
        }
        object.__setattr__(self, "_soles", soles)
        at_rest: dict[str, dict[str, tuple[float, float]]] = {}
        for view, rest in self.rests.items():
            at_rest[view] = {}
            for bone in self.bones.values():
                (start_x, start_y), (end_x, end_y) = rest[bone.start], rest[bone.end]
                length = math.hypot(end_x - start_x, end_y - start_y)
                at_rest[view][bone.name] = (length, angle_of(end_x - start_x, end_y - start_y) if length else 0.0)
        object.__setattr__(self, "_at_rest", at_rest)

    def length(self, view: str, bone: str) -> float:
        """How long a bone is, seen from one side."""
        return self._at_rest[view][bone][0]

    def rest_angle(self, view: str, bone: str) -> float:
        """Which way a bone points while the body stands at rest."""
        return self._at_rest[view][bone][1]

    def bones_beyond(self, bone: str) -> tuple[str, ...]:
        """A bone and every bone that hangs from it."""
        found = [bone]
        for name in found:
            found.extend(other.name for other in self.bones.values() if other.start == self.bones[name].end)
        return tuple(found)

    def anchor(self, name: str, facing: str, pose: dict[str, Point]) -> Point | None:
        """A semantic point in an already sampled pose, accounting for mirrored side views."""
        joint = self.anchors.get(name)
        if joint is None:
            return None
        if FACINGS[facing][3]:
            joint = other_side(joint)
        return pose.get(joint)

    def _palm(self, anchors: tuple[str, str], facing: str, pose: dict[str, Point]) -> tuple[Point, Point] | None:
        """The middle of a hand in a pose, and the way it points, as far as from wrist to fingertips."""
        tip, wrist = (self.anchor(name, facing, pose) for name in anchors)
        if tip is None or wrist is None:
            return None
        return ((tip[0] + wrist[0]) / 2.0, (tip[1] + wrist[1]) / 2.0), (tip[0] - wrist[0], tip[1] - wrist[1])

    def handle(self, clip: str, facing: str, pose: dict[str, Point]) -> tuple[Point, Point, float] | None:
        """Where a clip has something with a handle held, in a pose of it.

        Gives a point of the handle, the way the handle runs from there towards its far end, one
        pixel long, and how far along the handle that point is, as a share of its length. None
        if nothing is held by a handle in that clip, or the body plan does not say where the
        hands are.
        """
        grip = self.grips.get(clip)
        held = self._palm(HELD_ANCHORS, facing, pose) if grip is not None else None
        if grip is None or held is None:
            return None
        palm, pointing = held
        if grip.both:
            other = self._palm(OTHER_ANCHORS, facing, pose)
            if other is None:
                return None
            dx, dy = palm[0] - other[0][0], palm[1] - other[0][1]
            far = math.hypot(dx, dy)
            # With both hands on the same spot there is no saying which way it runs.
            return (other[0], (dx / far, dy / far), grip.at) if far > 1e-6 else None
        # Facing the other way, everything is in a mirror, and so is the turn of the handle.
        angle = angle_of(*pointing) + (-grip.turn if FACINGS[facing][2] else grip.turn)
        return (palm, (math.sin(angle), math.cos(angle)), grip.at)

    def frames(self, clip: str, view: str) -> int:
        return len(self._keyframes(clip, view))

    def like(self, view: str) -> str:
        """The view whose clips and limits a view goes by: itself, unless it is another with a rest of its own."""
        return self.likes.get(view, view)

    def _keyframes(self, clip: str, view: str) -> tuple[Keyframe, ...]:
        views = self.clips.get(clip) or self.clips.get(IDLE_CLIP) or {}
        return views.get(self.like(view)) or (Keyframe(),)

    def sample(self, clip: str, view: str, phase: float) -> Keyframe:
        """A clip part-way through, `phase` going from 0 to 1 over one turn of it.

        It goes through every key in a curve, as fast into each as out of it, and not in straight
        lines from one to the next. A clip that is done once stays as its first key before it
        starts and as its last when it is over, and sets off from each of those two at rest.
        """
        keyframes = self._keyframes(clip, view)
        count = len(keyframes)
        if count == 1:
            return keyframes[0]
        once = clip in self.once and clip in self.clips
        times = [frame.at for frame in keyframes]
        if times[0] is None:
            times = [index / (count - 1 if once else count) for index in range(count)]

        def at(index: int) -> float:
            """When a key comes, counting on through the turns before this one and after it."""
            return times[index % count] + index // count

        if once:
            phase = min(max(phase, times[0]), times[-1])
            before = max(index for index in range(count - 1) if times[index] <= phase)
        else:
            phase %= 1.0
            before = max((index for index in range(count) if times[index] <= phase), default=-1)
        after = before + 1
        span = at(after) - at(before)
        share = (phase - at(before)) / span if span > 0 else 0.0
        # How much of each key there is in the curve between two of them: the two themselves,
        # and the one either side, by which it leans the way it is going.
        weights = {
            before: 2 * share**3 - 3 * share**2 + 1,
            after: 3 * share**2 - 2 * share**3,
            before - 1: 0.0,
            after + 1: 0.0,
        }
        if not once or before > 0:
            lean = (share**3 - 2 * share**2 + share) * span / (at(after) - at(before - 1))
            weights[before - 1] -= lean
            weights[after] += lean
        if not once or after < count - 1:
            lean = (share**3 - share**2) * span / (at(after + 1) - at(before))
            weights[after + 1] += lean
            weights[before] -= lean
        used = [(keyframes[index % count], weight) for index, weight in weights.items() if weight]
        bones = {}
        for bone in set().union(*(frame.bones for frame, _ in used)):
            angle = scale = 0.0
            for frame, weight in used:
                turned, long = frame.bones.get(bone, (0.0, 1.0))
                angle += turned * weight
                scale += long * weight
            bones[bone] = (angle, scale)
        root = (sum(frame.root[0] * weight for frame, weight in used), sum(frame.root[1] * weight for frame, weight in used))
        return Keyframe(root, bones)

    def every_bone(self, frame: Keyframe) -> dict[str, tuple[float, float]]:
        """How far every bone is turned and how long it looks in a pose, the ones it does not
        name too: a bone that follows another turns as that one does, and any other is at rest."""
        turned, follows = frame.bones, self.follows
        return {name: turned.get(name) or (turned.get(follows.get(name, ""), (0.0, 1.0))[0], 1.0) for name in self.bones}

    def turned(self, view: str, clip: str = IDLE_CLIP, phase: float = 0.0, overlay: str | None = None) -> Keyframe:
        """How a clip part-way through has the bones of a body seen from one side.

        `overlay` names a second clip whose bones take the place of the first one's, such as arms
        held out to carry something while the legs go on walking.
        """
        frame = self.sample(clip, view, phase)
        if overlay is None:
            return frame
        bones = dict(frame.bones)
        bones.update(self.sample(overlay, view, phase).bones)
        return Keyframe(frame.root, bones)

    def pose(
        self, facing: str, clip: str = IDLE_CLIP, phase: float = 0.0, overlay: str | None = None
    ) -> dict[str, Point]:
        """Where every joint is, from the spot between the feet, for a body facing one way.

        `overlay` names a second clip whose bones take the place of the first one's, such as arms
        held out to carry something while the legs go on walking.
        """
        return self.place(facing, self.turned(FACINGS[facing][0], clip, phase, overlay))

    def place(self, facing: str, frame: Keyframe) -> dict[str, Point]:
        """Where every joint of a body facing one way is, from the spot between the feet, with
        its bones turned as a pose has them.

        A bone is turned from how it is at rest, and more is the same way round for every
        bone. So more is forwards for what hangs down at rest, as an arm does and a leg, and
        backwards for what points up, as the trunk does, the neck and the head: whoever bows
        has a trunk turned less than nothing.
        """
        view, _, mirrored, swapped = FACINGS[facing]
        turned = frame.bones
        rest = self.rests[view]
        root_x, root_y = rest[self.root]
        positions = {self.root: (root_x + frame.root[0], root_y + frame.root[1])}
        # Bones are listed from the root outwards, so a bone's start is always placed before it.
        at_rest = self._at_rest[view]
        whole = self.every_bone(frame)
        for bone in self.bones.values():
            angle, scale = whole[bone.name]
            length, rest_angle = at_rest[bone.name]
            angle += rest_angle
            reach = length * scale
            start_x, start_y = positions[bone.start]
            positions[bone.end] = (start_x + math.sin(angle) * reach, start_y + math.cos(angle) * reach)
        if view in self.footing.views:
            self._plant(positions, frame.root, rest)
            # However it lies, and however long its limbs, none of it is under the ground.
            sunk = max(y for _, y in positions.values())
        else:
            # A body that does not bend its legs to go down cannot go down: where a pose would
            # have any of it lower than it stands, it is the whole of it higher.
            sunk = max(y for _, y in positions.values()) - max(y for _, y in rest.values())
        if sunk > 0.0:
            positions = {name: (x, y - sunk) for name, (x, y) in positions.items()}
        if not mirrored:
            return positions
        return {(other_side(name) if swapped else name): (-x, y) for name, (x, y) in positions.items()}

    def _plant(self, positions: dict[str, Point], moved: Point, rest: dict[str, Point]) -> None:
        """Keep on the ground the feet a pose has there, though it moves the body they are under.

        `moved` is how far the pose has moved the whole body, feet and all. A foot that would be
        on the ground without that is put back where it would be, and the knee goes where it
        must, bending to the front. A leg too short to reach is drawn out, so far and no further.
        A foot the pose holds well off the ground is left to go with the body, and no foot is
        ever put under the ground. One that is on the ground is on it: not a hair above it.
        And a foot on the ground, or near it, has its sole level with it.

        A pose that lifts the body higher than its legs reach does not lift it off its feet:
        it is brought down until the feet it stands on are on the ground.
        """
        footing = self.footing
        feet = self._footfalls(positions, moved, rest)
        if footing.hold > 0.0:
            hang = max((self._hanging(positions, thigh, to) * (1.0 - lifted) for thigh, _, _, to, lifted in feet), default=0.0)
            if hang > 0.0:
                for joint, (x, y) in positions.items():
                    positions[joint] = (x, y + hang)
                feet = self._footfalls(positions, (moved[0], moved[1] + hang), rest)
        for thigh, shin, ground, (to_x, to_y), _ in feet:
            hip, knee, foot = self.bones[thigh].start, self.bones[thigh].end, self.bones[shin].end
            (hip_x, hip_y), (foot_x, foot_y) = positions[hip], positions[foot]
            if abs(to_x - foot_x) < 1e-9 and abs(to_y - foot_y) < 1e-9:
                self._level(positions, shin, ground)
                continue
            upper, lower = math.dist(positions[hip], positions[knee]), math.dist(positions[knee], positions[foot])
            reach_x, reach_y = to_x - hip_x, to_y - hip_y
            far = math.hypot(reach_x, reach_y)
            if upper <= 0.0 or lower <= 0.0 or far <= 0.0:
                continue
            drawn_out = min(max(far / (upper + lower), 1.0), footing.stretch)
            upper, lower = upper * drawn_out, lower * drawn_out
            if far > upper + lower:
                # Not even drawn out does it reach: the foot comes off the ground, as near as it gets.
                reach_x, reach_y = reach_x * (upper + lower) / far, reach_y * (upper + lower) / far
                far = upper + lower
            far = max(far, abs(upper - lower) + 1e-6)
            along = (upper * upper - lower * lower + far * far) / (2.0 * far)
            aside = math.sqrt(max(0.0, upper * upper - along * along))
            way_x, way_y = reach_x / far, reach_y / far
            positions[knee] = (hip_x + way_x * along + way_y * aside, hip_y + way_y * along - way_x * aside)
            shift = (hip_x + reach_x - foot_x, hip_y + reach_y - foot_y)
            for joint in self._beyond[shin]:
                x, y = positions[joint]
                positions[joint] = (x + shift[0], y + shift[1])
            self._level(positions, shin, ground)

    def _footfalls(
        self, positions: dict[str, Point], moved: Point, rest: dict[str, Point]
    ) -> list[tuple[str, str, float, Point, float]]:
        """For each leg a body stands on: its two bones, how high the ground is under its foot,
        where that foot is to go, and how much of that is the pose's own doing, from none of it
        for a foot on the ground to all of it for one held well off it."""
        footing = self.footing
        room = footing.free - footing.hold
        found = []
        for thigh, shin in footing.legs:
            foot_x, foot_y = positions[self.bones[shin].end]
            ground = rest[self.bones[shin].end][1]
            still_x, still_y = foot_x - moved[0], foot_y - moved[1]
            lifted = min(1.0, max(0.0, ground - still_y - footing.hold) / room) if room > 0 else 1.0
            lifted = lifted * lifted * (3.0 - 2.0 * lifted)
            to_x = still_x + (foot_x - still_x) * lifted
            if footing.hold > 0.0:
                # From the ground itself up to where the pose has it, and never under.
                to_y = min(ground, ground + (foot_y - ground) * lifted)
            else:
                to_y = min(ground, still_y + (foot_y - still_y) * lifted)
            found.append((thigh, shin, ground, (to_x, to_y), lifted))
        return found

    def _hanging(self, positions: dict[str, Point], thigh: str, to: Point) -> float:
        """How far a body would have to come down for a leg, drawn out as far as it goes, to
        reach where its foot is to be. Nothing for a leg that reaches, or that never would."""
        hip, knee = self.bones[thigh].start, self.bones[thigh].end
        shin = next(lower for upper, lower in self.footing.legs if upper == thigh)
        long = (math.dist(positions[hip], positions[knee]) + math.dist(positions[knee], positions[self.bones[shin].end])) * self.footing.stretch
        across, down = to[0] - positions[hip][0], to[1] - positions[hip][1]
        if math.hypot(across, down) <= long or abs(across) >= long:
            return 0.0
        return max(0.0, down - math.sqrt(long * long - across * across))

    def _level(self, positions: dict[str, Point], shin: str, ground: float) -> None:
        """Lay flat to the ground the sole of a foot that is on it or near it.

        Whatever hangs from the foot of a leg is turned about it until it lies along the
        ground, the way it already points: ahead for a foot that stands, behind for one that
        kneels. The nearer the ground the foot is, the more: on it, wholly; from as high as
        `level` up, less and less, and twice as high not at all.
        """
        reach = self.footing.level
        if reach <= 0.0:
            return
        for start, end, beyond in self._soles[shin]:
            (heel_x, heel_y), (toe_x, toe_y) = positions[start], positions[end]
            high = max(0.0, ground - heel_y)
            flat = 1.0 - min(1.0, max(0.0, high - reach) / reach)
            flat = flat * flat * (3.0 - 2.0 * flat)
            long = math.hypot(toe_x - heel_x, toe_y - heel_y)
            if flat <= 0.0 or long <= 0.0:
                continue
            turned = math.atan2(toe_y - heel_y, toe_x - heel_x)
            along = 0.0 if toe_x >= heel_x else math.pi
            turned += wrapped(along - turned) * flat
            shift = (heel_x + math.cos(turned) * long - toe_x, heel_y + math.sin(turned) * long - toe_y)
            for joint in beyond:
                x, y = positions[joint]
                positions[joint] = (x + shift[0], y + shift[1])


def _pair(value: Any, what: str) -> tuple[float, float]:
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        raise ValueError(f"Expected two numbers for {what}, got {value!r}")
    return (float(value[0]), float(value[1]))


def _keyframe(data: dict[str, Any], bones: dict[str, BoneSpec], where: str) -> Keyframe:
    turned = {}
    for bone, value in data.items():
        if bone in (ROOT_KEY, AT_KEY):
            continue
        if bone not in bones:
            raise ValueError(f"{where} moves unknown bone: {bone}")
        angle, scale = _pair(value, f"{where} {bone}") if isinstance(value, (list, tuple)) else (float(value), 1.0)
        turned[bone] = (math.radians(angle), scale)
    at = float(data[AT_KEY]) if AT_KEY in data else None
    return Keyframe(_pair(data.get(ROOT_KEY, (0, 0)), f"{where} root"), turned, at)


def _keyframes(frames: Any, bones: dict[str, BoneSpec], once: bool, where: str) -> tuple[Keyframe, ...]:
    """The keys of a clip from one side. Either none of them says when it comes, or they all do,
    each later than the one before."""
    keys = tuple(_keyframe(frame, bones, where) for frame in frames)
    times = [key.at for key in keys]
    if any(time is not None for time in times):
        last = 1.0 if once else 1.0 - 1e-9
        in_order = all(time is not None for time in times) and all(a < b for a, b in zip(times, times[1:]))
        if not in_order or times[0] < 0.0 or times[-1] > last:
            raise ValueError(f"{where}: every key must say when it comes, from 0 to 1 and each later than the last")
    return keys


def _grip(data: Any, where: str) -> Grip:
    """How a clip has something held by its handle: in one hand or in both, how far along, and turned how."""
    if not isinstance(data, dict):
        raise ValueError(f"{where}: a grip must say how a thing is held")
    hands, at = int(data.get("hands", 1)), float(data.get("at", 0.2))
    if hands not in (1, 2) or not 0.0 <= at <= 1.0:
        raise ValueError(f"{where}: a thing is held in one hand or two, at a share of its handle from 0 to 1")
    return Grip(hands == 2, at, math.radians(float(data.get("turn", 0.0))))


def _spring(value: Any, what: str) -> Spring:
    if not isinstance(value, dict):
        raise ValueError(f"Expected a spring for {what}, got {value!r}")
    speed, bounce = float(value.get("speed", 20.0)), float(value.get("bounce", 0.0))
    if speed <= 0.0 or not 0.0 <= bounce < 1.0:
        raise ValueError(f"The spring of {what} needs a speed above 0 and a bounce from 0 to under 1")
    return Spring.of(speed, bounce, float(value.get("drag", 0.0)))


def _footing(data: Any, bones: dict[str, BoneSpec], views: Any) -> Footing:
    if not isinstance(data, dict):
        return Footing()
    legs = tuple((str(thigh), str(shin)) for thigh, shin in data.get("legs", ()))
    for thigh, shin in legs:
        if thigh not in bones or shin not in bones or bones[shin].start != bones[thigh].end:
            raise ValueError(f"A leg to stand on is a bone and the one that hangs from it: {thigh}, {shin}")
    seen = frozenset(str(view) for view in data.get("views", ()))
    if not seen <= set(views):
        raise ValueError(f"Footing for unknown views: {sorted(seen - set(views))}")
    known = Footing()
    free, stretch = float(data.get("free", known.free)), float(data.get("stretch", known.stretch))
    if free < 0.0 or stretch < 1.0:
        raise ValueError("Footing needs a `free` of 0 or more and a `stretch` of 1 or more")
    hold, level = float(data.get("hold", known.hold)), float(data.get("level", known.level))
    if not 0.0 <= hold <= free or level < 0.0:
        raise ValueError("Footing needs a `hold` from 0 to its `free`, and a `level` of 0 or more")
    return Footing(seen, legs, free, stretch, hold, level)


def _life(data: Any, clips: Any) -> LifeSettings:
    if not isinstance(data, dict):
        return LifeSettings()
    breath, stand, fidgets = (data.get(key) or {} for key in ("breath", "stand", "fidgets"))
    known = LifeSettings()
    made = LifeSettings(
        breath.get("clip"), float(breath.get("rate", known.breath_rate)),
        stand.get("clip"), float(stand.get("rate", known.stand_rate)),
        tuple(str(clip) for clip in fidgets.get("clips", ())),
        _pair(fidgets.get("every", known.every), "life fidgets every"), float(fidgets.get("rate", known.fidget_rate)),
    )
    unknown = [clip for clip in (made.breath, made.stand, *made.fidgets) if clip is not None and clip not in clips]
    if unknown:
        raise ValueError(f"Life names unknown clips: {unknown}")
    if made.every[0] <= 0.0 or made.every[1] < made.every[0] or made.fidget_rate <= 0.0:
        raise ValueError("Life needs fidgets `every` so many seconds, from the least to the most, at a `rate` above 0")
    return made


def _motion(data: Any, bones: dict[str, BoneSpec]) -> MotionSettings:
    if not isinstance(data, dict):
        return MotionSettings()
    spring = _spring(data["spring"], "any bone") if "spring" in data else Spring()
    root = _spring(data["root"], "the whole body") if "root" in data else spring
    springs = {str(bone): _spring(value, bone) for bone, value in data.get("springs", {}).items()}
    jolt = data.get("jolt") or {}
    jolted = {
        str(bone): (math.radians(pair[0]), pair[1])
        for bone, pair in ((bone, _pair(value, f"jolt {bone}")) for bone, value in (jolt.get("bones") or {}).items())
    }
    if not set(springs) | set(jolted) <= bones.keys():
        raise ValueError(f"Springs for unknown bones: {sorted((set(springs) | set(jolted)) - bones.keys())}")
    known = MotionSettings()
    return MotionSettings(
        spring, root, springs, _pair(jolt.get(ROOT_KEY, (0, 0)), "jolt root"), jolted,
        float(data.get("step", known.step)), int(data.get("max_steps", known.max_steps)),
    )


def plan_from_data(data: dict[str, Any]) -> SkeletonPlan:
    joints = {
        str(name): JointSpec(str(name), float(values.get("mass", 1.0)), float(values.get("radius", 1.0)))
        for name, values in data["joints"].items()
    }
    root = str(data["root"])
    if root not in joints:
        raise ValueError(f"Skeleton root is not a joint: {root}")
    bones: dict[str, BoneSpec] = {}
    reached = {root}
    for name, ends in data["bones"].items():
        start, end = (str(joint) for joint in ends)
        if start not in joints or end not in joints:
            raise ValueError(f"Bone {name} joins unknown joints: {start}, {end}")
        if start not in reached or end in reached:
            raise ValueError(f"Bone {name} must start at a joint already joined to {root} and end at a new one")
        reached.add(end)
        bones[str(name)] = BoneSpec(str(name), start, end)
    if reached != joints.keys():
        raise ValueError(f"Joints that no bone reaches: {sorted(joints.keys() - reached)}")
    braces = tuple((str(a), str(b)) for a, b in data.get("braces", []))
    for pair in braces:
        if not set(pair) <= joints.keys():
            raise ValueError(f"Brace between unknown joints: {pair}")
    parts = {str(part): str(bone) for part, bone in data.get("parts", {}).items()}
    for part, bone in parts.items():
        if bone not in bones:
            raise ValueError(f"Part {part} hangs from unknown bone: {bone}")
    limits = {}
    for bone, values in data.get("limits", {}).items():
        ref = str(values["ref"])
        if bone not in bones or ref not in bones:
            raise ValueError(f"Limit on {bone} against {ref} names an unknown bone")
        ranges = {view: _pair(values[view], f"limit {bone} {view}") for view in VIEWS}
        limits[str(bone)] = LimitSpec(str(bone), ref, bool(values.get("ref_reversed", False)), ranges)
    rests, likes = {}, {}
    for view in (*VIEWS, *(str(name) for name in data["views"] if name not in VIEWS)):
        rest = {str(joint): _pair(point, f"{view} {joint}") for joint, point in data["views"][view]["rest"].items()}
        if rest.keys() != joints.keys():
            raise ValueError(f"The {view} view must place every joint: {sorted(rest.keys() ^ joints.keys())}")
        rests[view] = rest
        if view not in VIEWS:
            likes[view] = str(data["views"][view].get("like", ""))
            if likes[view] not in VIEWS:
                raise ValueError(f"The {view} view must be like one of {VIEWS}, not {likes[view]!r}")
    follows = {str(bone): str(other) for bone, other in data.get("follows", {}).items()}
    if not set(follows) | set(follows.values()) <= bones.keys():
        raise ValueError(f"Bones follow unknown bones: {follows}")
    anchors = {str(name): str(joint) for name, joint in data.get("anchors", {}).items()}
    if not set(anchors.values()) <= joints.keys():
        raise ValueError(f"Anchors name unknown joints: {anchors}")
    orders = {}
    for view in (*SKIN_VIEWS, *(str(name) for name in data["orders"] if name not in SKIN_VIEWS)):
        order = tuple(str(bone) for bone in data["orders"][view])
        if not set(order) <= bones.keys():
            raise ValueError(f"The {view} order names unknown bones: {sorted(set(order) - bones.keys())}")
        orders[view] = order
    skins = {}
    for bone, values in data.get("skins", {}).items():
        if bone not in bones:
            raise ValueError(f"Skin for unknown bone: {bone}")
        kind = "sprite" if "sprite" in values else "strip"
        skins[str(bone)] = SkinSpec(str(bone), kind, str(values[kind]), str(values.get("anchor", "middle")))
    once = frozenset(str(clip) for clip, views in data.get("clips", {}).items() if views.get(ONCE_KEY))
    clips = {
        str(clip): {
            view: _keyframes(views.get(view, [{}]), bones, clip in once, f"Clip {clip} ({view})") for view in VIEWS
        }
        for clip, views in data.get("clips", {}).items()
    }
    grips = {
        str(clip): _grip(views[GRIP_KEY], f"Clip {clip}")
        for clip, views in data.get("clips", {}).items()
        if GRIP_KEY in views
    }
    known = PhysicsSettings()
    physics = PhysicsSettings(
        **{name: type(getattr(known, name))(value) for name, value in data.get("physics", {}).items() if hasattr(known, name)}
    )
    return SkeletonPlan(
        root, joints, bones, braces, parts, limits, rests, orders, skins, clips,
        physics=physics, likes=likes, follows=follows, anchors=anchors,
        once=once, motion=_motion(data.get("motion"), bones), footing=_footing(data.get("footing"), bones, rests),
        life=_life(data.get("life"), clips), grips=grips,
    )


def load_plan(path: Path = PLAN_PATH) -> SkeletonPlan:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"Expected object in {path}")
    return plan_from_data(data)


@functools.cache
def builtin_plan() -> SkeletonPlan:
    """The game's own body plan, loaded once. It is read-only, so every body can share it."""
    return load_plan()
