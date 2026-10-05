"""A body made of joints held together by bones, which can be cut apart while it is in use."""

import math
from collections.abc import Iterable

from skeleton.plan import FACINGS, Point, SkeletonPlan, other_side


class Joint:
    """A point of the body. It remembers where it was a step ago, which is what gives it speed."""

    __slots__ = ("name", "x", "y", "px", "py", "inv_mass", "radius")

    def __init__(self, name: str, x: float, y: float, mass: float = 1.0, radius: float = 1.0) -> None:
        self.name = name
        self.x = x
        self.y = y
        self.px = x
        self.py = y
        self.inv_mass = 1.0 / mass if mass > 0 else 0.0
        self.radius = radius

    def copy(self) -> "Joint":
        twin = Joint(self.name, self.x, self.y, 1.0, self.radius)
        twin.px, twin.py, twin.inv_mass = self.px, self.py, self.inv_mass
        return twin


class Bone:
    """Keeps two joints a fixed distance apart. `a` is the end nearer the root of the body."""

    __slots__ = ("name", "a", "b", "length")

    def __init__(self, name: str, a: Joint, b: Joint, length: float) -> None:
        self.name = name
        self.a = a
        self.b = b
        self.length = length

    @property
    def angle(self) -> float:
        """Which way it points now, turning anticlockwise on screen from straight down."""
        return math.atan2(self.b.x - self.a.x, self.b.y - self.a.y)


class Limit:
    """Keeps a bone from turning further against another than a joint of flesh would let it."""

    __slots__ = ("bone", "ref", "ref_reversed", "low", "high")

    def __init__(self, bone: Bone, ref: Bone, ref_reversed: bool, low: float, high: float) -> None:
        self.bone = bone
        self.ref = ref
        self.ref_reversed = ref_reversed
        self.low = low
        self.high = high


class Skeleton:
    """The joints, bones and limits of one body, or of one piece that has come off it.

    It is built for one way of facing, since a body seen from the side is not as wide as from the
    front. `ground` is the height its joints cannot fall below.
    """

    def __init__(self, plan: SkeletonPlan, facing: str = "down", missing: Iterable[str] = ()) -> None:
        self.plan = plan
        self.facing = facing
        self.view, self.skin_view, self.mirrored, self.swapped = FACINGS[facing]
        self.ground = 0.0
        # Whether it lies still and is left alone, and for how long it has barely moved.
        self.asleep = False
        self.still_for = 0.0
        # How long physics has had it since it last woke.
        self.limp_for = 0.0
        # Time owed to it that did not fill a whole step yet.
        self.lag = 0.0
        rest = self._named(plan.rests[self.view])
        self.joints: dict[str, Joint] = {
            name: Joint(name, rest[name][0], rest[name][1], spec.mass, spec.radius)
            for name, spec in plan.joints.items()
        }
        self.bones: dict[str, Bone] = {
            name: Bone(name, self.joints[spec.start], self.joints[spec.end], self._rest_length(name))
            for name, spec in plan.bones.items()
        }
        # Unseen struts that keep the trunk in shape.
        self.braces: list[Bone] = [
            Bone(f"{a}~{b}", self.joints[a], self.joints[b], math.dist(rest[a], rest[b])) for a, b in plan.braces
        ]
        self.limits: list[Limit] = [self._limit(name) for name in plan.limits]
        # Pairs of joints that may come no nearer than a distance: what keeps a limb from folding
        # flat on itself where it lies, which a limit on its angle alone cannot tell from straight.
        self.spacers: list[Bone] = [spacer for spacer in map(self._spacer, self.limits) if spacer is not None]
        for part in missing:
            if part in plan.parts:
                self.sever(plan.parts[part])

    def _named(self, positions: dict[str, Point]) -> dict[str, Point]:
        """Positions given for a body facing the unmirrored way, as this body has them."""
        if not self.mirrored:
            return positions
        return {self.as_posed(name): (-x, y) for name, (x, y) in positions.items()}

    def as_posed(self, name: str) -> str:
        """The joint or bone of the plan that one of this body's stands in for, facing as it does."""
        return other_side(name) if self.swapped else name

    def _rest_length(self, bone: str) -> float:
        return self.plan.length(self.view, self.as_posed(bone))

    def _limit(self, name: str) -> Limit:
        spec = self.plan.limits[name]
        like = self.plan.like(self.view)
        low, high = (math.radians(degrees) for degrees in spec.ranges[like])
        # Limits are written for a body facing right, or for its left side when seen from the front.
        forwards = not self.mirrored
        if like == "front" and name.endswith("_right"):
            forwards = not forwards
        if not forwards:
            low, high = -high, -low
        return Limit(self.bones[name], self.bones[spec.ref], spec.ref_reversed, low, high)

    def _spacer(self, limit: Limit) -> Bone | None:
        bone, ref = limit.bone, limit.ref
        near, far = (ref.a, ref.b) if limit.ref_reversed else (ref.b, ref.a)
        bend = max(abs(limit.low), abs(limit.high))
        if near is not bone.a or bend >= math.pi:
            return None
        # The two bones and the gap between their far ends make a triangle.
        gap = math.sqrt(max(0.0, ref.length**2 + bone.length**2 + 2 * ref.length * bone.length * math.cos(bend)))
        return Bone(f"{far.name}|{bone.b.name}", far, bone.b, gap)

    def set_pose(self, pose: dict[str, Point], x: float = 0.0, y: float = 0.0) -> None:
        """Put the joints where a pose has them, around a spot on the ground, and bring them to a stop."""
        self.ground = y
        for name, joint in self.joints.items():
            if name in pose:
                joint.x = joint.px = x + pose[name][0]
                joint.y = joint.py = y + pose[name][1]
        self.wake()

    def push(self, joint: str, vx: float, vy: float) -> None:
        """Add speed to one joint, in pixels per second. The bones pass it on to the rest."""
        target = self.joints.get(joint)
        if target is not None:
            step = self.plan.physics.step
            target.px -= vx * step
            target.py -= vy * step
            self.wake()

    def push_all(self, vx: float, vy: float) -> None:
        """Add the same speed to every joint, as when the whole body was already moving."""
        step = self.plan.physics.step
        for joint in self.joints.values():
            joint.px -= vx * step
            joint.py -= vy * step
        self.wake()

    def spin(self, rate: float) -> None:
        """Set it turning about its middle, in radians per second: what makes a thrown limb tumble."""
        joints = list(self.joints.values())
        middle_x = sum(joint.x for joint in joints) / len(joints)
        middle_y = sum(joint.y for joint in joints) / len(joints)
        step = self.plan.physics.step
        for joint in joints:
            joint.px += (joint.y - middle_y) * rate * step
            joint.py -= (joint.x - middle_x) * rate * step
        self.wake()

    def wake(self) -> None:
        self.asleep = False
        self.still_for = 0.0
        self.limp_for = 0.0

    def sever(self, bone: str) -> "Skeleton | None":
        """Cut a bone loose from the joint it starts at. Returns the piece that comes off.

        The bone and everything that hangs from it leave this skeleton for one of their own, with
        the same joints and bones they had: nothing is copied but the joint that was cut through.
        None if this skeleton has no such bone.
        """
        cut = self.bones.get(bone)
        if cut is None:
            return None
        end = cut.a.copy()
        cut.a = end
        # Everything still joined to the cut end goes with it.
        loose = {id(end): end}
        grew = True
        while grew:
            grew = False
            for other in self.bones.values():
                if (id(other.a) in loose) != (id(other.b) in loose):
                    loose[id(other.a)] = other.a
                    loose[id(other.b)] = other.b
                    grew = True

        piece = Skeleton.__new__(Skeleton)
        piece.plan, piece.facing = self.plan, self.facing
        piece.view, piece.skin_view = self.view, self.skin_view
        piece.mirrored, piece.swapped = self.mirrored, self.swapped
        piece.ground, piece.asleep, piece.still_for, piece.limp_for, piece.lag = self.ground, False, 0.0, 0.0, 0.0
        piece.joints = {joint.name: joint for joint in loose.values()}
        piece.bones = {name: other for name, other in self.bones.items() if id(other.a) in loose}
        self.bones = {name: other for name, other in self.bones.items() if id(other.a) not in loose}
        self.joints = {name: joint for name, joint in self.joints.items() if id(joint) not in loose}
        # A strut or a limit between the two pieces holds nothing any more.
        piece.braces = [brace for brace in self.braces if id(brace.a) in loose and id(brace.b) in loose]
        self.braces = [brace for brace in self.braces if id(brace.a) not in loose and id(brace.b) not in loose]
        piece.spacers = [spacer for spacer in self.spacers if id(spacer.a) in loose and id(spacer.b) in loose]
        self.spacers = [spacer for spacer in self.spacers if id(spacer.a) not in loose and id(spacer.b) not in loose]
        piece.limits = [limit for limit in self.limits if limit.bone.name in piece.bones and limit.ref.name in piece.bones]
        self.limits = [limit for limit in self.limits if limit.bone.name in self.bones and limit.ref.name in self.bones]
        self.wake()
        return piece

    def bounds(self) -> tuple[float, float, float, float]:
        """Left, top, right and bottom of the joints."""
        xs = [joint.x for joint in self.joints.values()]
        ys = [joint.y for joint in self.joints.values()]
        return (min(xs), min(ys), max(xs), max(ys))
