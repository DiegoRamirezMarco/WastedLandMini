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
}
SIDES = ("_left", "_right")
ROOT_KEY = "root"
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
    # Per pose view and bone, how long it is and which way it points while the body stands at rest.
    _at_rest: dict[str, dict[str, tuple[float, float]]] = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
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

    def frames(self, clip: str, view: str) -> int:
        return len(self._keyframes(clip, view))

    def _keyframes(self, clip: str, view: str) -> tuple[Keyframe, ...]:
        views = self.clips.get(clip) or self.clips.get(IDLE_CLIP) or {}
        return views.get(view) or (Keyframe(),)

    def sample(self, clip: str, view: str, phase: float) -> Keyframe:
        """A clip part-way through, `phase` going from 0 to 1 over one turn of it."""
        keyframes = self._keyframes(clip, view)
        if len(keyframes) == 1:
            return keyframes[0]
        position = (phase % 1.0) * len(keyframes)
        index = int(position) % len(keyframes)
        before, after = keyframes[index], keyframes[(index + 1) % len(keyframes)]
        blend = position - int(position)
        bones = {}
        for bone in before.bones.keys() | after.bones.keys():
            (angle_a, scale_a), (angle_b, scale_b) = before.bones.get(bone, (0.0, 1.0)), after.bones.get(bone, (0.0, 1.0))
            bones[bone] = (angle_a + (angle_b - angle_a) * blend, scale_a + (scale_b - scale_a) * blend)
        root = (
            before.root[0] + (after.root[0] - before.root[0]) * blend,
            before.root[1] + (after.root[1] - before.root[1]) * blend,
        )
        return Keyframe(root, bones)

    def pose(
        self, facing: str, clip: str = IDLE_CLIP, phase: float = 0.0, overlay: str | None = None
    ) -> dict[str, Point]:
        """Where every joint is, from the spot between the feet, for a body facing one way.

        `overlay` names a second clip whose bones take the place of the first one's, such as arms
        held out to carry something while the legs go on walking.
        """
        view, _, mirrored, swapped = FACINGS[facing]
        frame = self.sample(clip, view, phase)
        turned = dict(frame.bones)
        if overlay is not None:
            turned.update(self.sample(overlay, view, phase).bones)
        rest = self.rests[view]
        root_x, root_y = rest[self.root]
        positions = {self.root: (root_x + frame.root[0], root_y + frame.root[1])}
        # Bones are listed from the root outwards, so a bone's start is always placed before it.
        at_rest = self._at_rest[view]
        for bone in self.bones.values():
            angle, scale = turned.get(bone.name, (0.0, 1.0))
            length, rest_angle = at_rest[bone.name]
            angle += rest_angle
            reach = length * scale
            start_x, start_y = positions[bone.start]
            positions[bone.end] = (start_x + math.sin(angle) * reach, start_y + math.cos(angle) * reach)
        if not mirrored:
            return positions
        return {(other_side(name) if swapped else name): (-x, y) for name, (x, y) in positions.items()}


def _pair(value: Any, what: str) -> tuple[float, float]:
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        raise ValueError(f"Expected two numbers for {what}, got {value!r}")
    return (float(value[0]), float(value[1]))


def _keyframe(data: dict[str, Any], bones: dict[str, BoneSpec], where: str) -> Keyframe:
    turned = {}
    for bone, value in data.items():
        if bone == ROOT_KEY:
            continue
        if bone not in bones:
            raise ValueError(f"{where} moves unknown bone: {bone}")
        angle, scale = _pair(value, f"{where} {bone}") if isinstance(value, (list, tuple)) else (float(value), 1.0)
        turned[bone] = (math.radians(angle), scale)
    return Keyframe(_pair(data.get(ROOT_KEY, (0, 0)), f"{where} root"), turned)


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
    rests = {}
    for view in VIEWS:
        rest = {str(joint): _pair(point, f"{view} {joint}") for joint, point in data["views"][view]["rest"].items()}
        if rest.keys() != joints.keys():
            raise ValueError(f"The {view} view must place every joint: {sorted(rest.keys() ^ joints.keys())}")
        rests[view] = rest
    orders = {}
    for view in SKIN_VIEWS:
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
    clips = {
        str(clip): {
            view: tuple(_keyframe(frame, bones, f"Clip {clip} ({view})") for frame in views.get(view, [{}]))
            for view in VIEWS
        }
        for clip, views in data.get("clips", {}).items()
    }
    known = PhysicsSettings()
    physics = PhysicsSettings(
        **{name: type(getattr(known, name))(value) for name, value in data.get("physics", {}).items() if hasattr(known, name)}
    )
    return SkeletonPlan(root, joints, bones, braces, parts, limits, rests, orders, skins, clips, physics)


def load_plan(path: Path = PLAN_PATH) -> SkeletonPlan:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"Expected object in {path}")
    return plan_from_data(data)


@functools.cache
def builtin_plan() -> SkeletonPlan:
    """The game's own body plan, loaded once. It is read-only, so every body can share it."""
    return load_plan()
