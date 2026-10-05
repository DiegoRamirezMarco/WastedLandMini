"""One body in play: posed while it goes about its business, handed to physics when something hits it."""

import math
from collections.abc import Iterable
from dataclasses import dataclass
from enum import Enum

from skeleton import physics
from skeleton.plan import IDLE_CLIP, Point, SkeletonPlan
from skeleton.rig import Skeleton

# Seconds a body takes to steady itself after a blow that did not knock it down, and to get up after one that did.
STAGGER_SECONDS = 0.5
RISE_SECONDS = 0.7
# How firmly a staggering body is held to its pose at first, from 0 to 1. It ends fully held.
STAGGER_HOLD = 0.12


class Mode(Enum):
    # Posed by its clips. No physics runs at all.
    POSED = "posed"
    # Thrown off its pose by a blow and being drawn back to it.
    STAGGER = "stagger"
    # Limp: only gravity, bones and the ground have a say.
    RAGDOLL = "ragdoll"


@dataclass
class BodyPart:
    """A piece that has come off a body, with a skeleton of its own to fall and lie where it lands."""

    part_id: str
    skeleton: Skeleton

    def update(self, seconds: float) -> None:
        physics.advance(self.skeleton, seconds)

    @property
    def at_rest(self) -> bool:
        return self.skeleton.asleep


class Character:
    """A body, the parts it still has, and what moves it right now.

    Whoever shows it says where it stands and what it is doing with `stand`. While it is merely
    posed that is all there is to it, and `skeleton` is None. A blow, a fall or a lost part gives
    it a skeleton with every joint where the pose had it, and physics takes over from there.
    """

    def __init__(self, plan: SkeletonPlan, lost: Iterable[str] = ()) -> None:
        self.plan = plan
        # IDs of the parts that have come off, in the order they did.
        self.lost: list[str] = [part for part in lost if part in plan.parts]
        self.mode = Mode.POSED
        self.alive = True
        self.skeleton: Skeleton | None = None
        self.x = 0.0
        self.y = 0.0
        self.facing = "down"
        self.clip = IDLE_CLIP
        self.phase = 0.0
        self.overlay: str | None = None
        # Seconds left of the present stagger or of lying knocked down, and how long the stagger is.
        self._left = 0.0
        self._span = STAGGER_SECONDS

    @property
    def physical(self) -> bool:
        """Whether physics is moving it, rather than its clips alone."""
        return self.mode is not Mode.POSED

    @property
    def at_rest(self) -> bool:
        """Posed, or limp and lying still: nothing to work out for it this frame."""
        return self.skeleton is None or self.skeleton.asleep

    def has(self, part: str) -> bool:
        """Whether a part is still on the body. A part goes with whatever it hung from."""
        if part not in self.plan.parts:
            return False
        bone = self.plan.parts[part]
        return not any(bone in self.plan.bones_beyond(self.plan.parts[gone]) for gone in self.lost)

    def stand(
        self,
        x: float,
        y: float,
        facing: str,
        clip: str = IDLE_CLIP,
        phase: float = 0.0,
        overlay: str | None = None,
    ) -> None:
        """Say where the body's feet are, in map pixels, and what it is doing there."""
        self.x, self.y, self.facing = x, y, facing
        self.clip, self.phase, self.overlay = clip, phase, overlay

    def pose(self) -> dict[str, Point]:
        """Where its clips would have every joint right now, in map pixels."""
        local = self.plan.pose(self.facing, self.clip, self.phase, self.overlay)
        return {name: (self.x + x, self.y + y) for name, (x, y) in local.items()}

    def _embody(self) -> Skeleton:
        """Give it a skeleton standing exactly as it is posed, if it has none yet."""
        if self.skeleton is None:
            self.skeleton = Skeleton(self.plan, self.facing, self.lost)
            self.skeleton.set_pose(self.plan.pose(self.facing, self.clip, self.phase, self.overlay), self.x, self.y)
        return self.skeleton

    def _struck(self, joint: str | None) -> str:
        """The joint a blow lands on: the one named if the body still has it, or the root of the body."""
        return joint if joint is not None and joint in self._embody().joints else self.plan.root

    def hit(self, vx: float, vy: float, joint: str | None = None) -> None:
        """Strike one joint with a speed in pixels per second. The body staggers and steadies itself."""
        self._embody().push(self._struck(joint), vx, vy)
        if self.mode is Mode.POSED:
            self.mode = Mode.STAGGER
            self._span = self._left = STAGGER_SECONDS

    def knock_down(self, vx: float, vy: float, joint: str | None = None, seconds: float = 2.0) -> None:
        """Strike it hard enough to go limp. If it is alive it gets up after `seconds`."""
        self._embody().push(self._struck(joint), vx, vy)
        self.mode = Mode.RAGDOLL
        self._left = seconds

    def kill(self, vx: float = 0.0, vy: float = 0.0, joint: str | None = None) -> Skeleton:
        """Let it drop for good. Returns the skeleton, which is now nobody's to pose."""
        self.alive = False
        self.knock_down(vx, vy, joint)
        return self.skeleton

    def sever(self, part: str, vx: float = 0.0, vy: float = 0.0, spin: float = 0.0) -> BodyPart | None:
        """Take a part off the body and throw it with a speed and a spin. Returns it, to fall where it will.

        None if the body has no such part any more.
        """
        if not self.has(part):
            return None
        piece = self._embody().sever(self.plan.parts[part])
        if piece is None:
            return None
        self.lost.append(part)
        piece.push_all(vx, vy)
        piece.spin(spin)
        if self.mode is Mode.POSED:
            self.mode = Mode.STAGGER
            self._span = self._left = STAGGER_SECONDS
        return BodyPart(part, piece)

    def update(self, seconds: float) -> None:
        """Let real time pass. A posed body, or a limp one lying still, costs nothing."""
        skeleton = self.skeleton
        if skeleton is None:
            return
        if self.mode is Mode.RAGDOLL:
            physics.advance(skeleton, seconds)
            if self.alive:
                self._left -= seconds
                if self._left <= 0.0:
                    self.mode = Mode.STAGGER
                    self._span = self._left = RISE_SECONDS
                    skeleton.wake()
            return
        self._left -= seconds
        if self._left <= 0.0:
            # Back on its pose: the skeleton has nothing more to say.
            self.mode = Mode.POSED
            self.skeleton = None
            return
        # It may have walked on while it reeled: the ground is wherever its feet are now.
        skeleton.ground = self.y
        done = 1.0 - self._left / self._span
        hold = STAGGER_HOLD + (1.0 - STAGGER_HOLD) * math.pow(done, 3)
        physics.advance(skeleton, seconds, self.pose(), hold)
