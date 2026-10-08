"""What gives a posed body weight: springs between where its clips have each bone and where it is.

A clip says where every bone is at each moment. Followed to the letter a body goes from pose to
pose like a machine, and from one clip to the next in no time at all. Here every bone is drawn
towards its place instead, loosely enough to arrive a little late and go a little past, the
further out on the body the looser. Nothing here is gameplay: it runs on real time, is never
saved, and knows no bone by name. How loose each bone is, is data.
"""

import random
from collections.abc import Hashable

from skeleton.plan import Keyframe, LifeSettings, SkeletonPlan, Spring


class Life:
    """What one body does with itself besides what it is given to do.

    It breathes, to a beat of its own. With nothing to do it does not stand stock still: it
    shifts its weight, and now and then does something small, a look about or a scratch. When
    is left to chance, and the chance is its own: nothing here is the simulation's, and none of
    it is saved.
    """

    def __init__(self, chance: random.Random) -> None:
        self._chance = chance
        # How far through a breath it is, and through shifting its weight, from 0 to 1. Nobody
        # starts in step with anybody else.
        self.breath = chance.random()
        self.stood = chance.random()
        # The small thing it is doing, how far through it, and seconds until the next one.
        self.fidget: str | None = None
        self.through = 0.0
        self._wait: float | None = None

    def update(self, settings: LifeSettings, seconds: float, at_ease: bool) -> None:
        """Let real time pass. `at_ease` is whether it has nothing to do and nothing in hand."""
        self.breath = (self.breath + seconds * settings.breath_rate) % 1.0
        if not at_ease or not settings.fidgets:
            # Busy: whatever small thing it was at is dropped, and the wait starts over when it is free.
            self.fidget, self._wait = None, None
            if at_ease:
                self.stood = (self.stood + seconds * settings.stand_rate) % 1.0
            return
        if self._wait is None:
            self._wait = self._chance.uniform(*settings.every)
        if self.fidget is not None:
            self.through += seconds * settings.fidget_rate
            if self.through >= 1.0:
                self.fidget, self._wait = None, self._chance.uniform(*settings.every)
            return
        self.stood = (self.stood + seconds * settings.stand_rate) % 1.0
        self._wait -= seconds
        if self._wait <= 0.0:
            self.fidget, self.through = self._chance.choice(settings.fidgets), 0.0

    def idling(self, settings: LifeSettings) -> tuple[str, float] | None:
        """The clip a body with nothing to do is in right now, and how far through it. None if
        it is to stand as its own clip has it."""
        if self.fidget is not None:
            return (self.fidget, self.through)
        return (settings.stand, self.stood) if settings.stand is not None else None


class Motion:
    """Where the bones of one body are right now, on their way to where its clips have them.

    It is told where they should be with `follow`, as often as the body is shown, and says where
    they are with `keyframe`. Sides are those of a body facing the unmirrored way: turning round
    is none of its business, and does not unsettle it.
    """

    def __init__(self) -> None:
        # For each bone: how far it is turned, how fast that is changing, how long it looks and
        # how fast that is changing.
        self._bones: dict[str, list[float]] = {}
        # Where the whole body is from where it stands at rest, and how fast it is moving.
        self._root = [0.0, 0.0, 0.0, 0.0]
        # What the body was last told it was doing, and time owed that did not fill a step yet.
        self._doing: Hashable = None
        self._lag = 0.0
        self.started = False
        # Where it was last told to be, and whether it has got there and stopped: if so, being
        # told the same again costs nothing.
        self._aimed: Keyframe | None = None
        self.settled = False

    def snap(self, plan: SkeletonPlan, target: Keyframe, doing: Hashable = None) -> None:
        """Put every bone exactly where a pose has it, at a standstill."""
        self._bones = {name: [angle, 0.0, scale, 0.0] for name, (angle, scale) in plan.every_bone(target).items()}
        self._root = [target.root[0], 0.0, target.root[1], 0.0]
        self._doing, self._lag, self.started = doing, 0.0, True
        self._aimed, self.settled = target, True

    def follow(self, plan: SkeletonPlan, target: Keyframe, seconds: float, doing: Hashable = None) -> None:
        """Let `seconds` pass with every bone drawn towards where a pose has it.

        `doing` is whatever tells one thing the body does from another. When it changes the body
        is given a jolt, which is what settling into something new looks like. The first time,
        the body is simply put where the pose has it.
        """
        if not self.started:
            self.snap(plan, target, doing)
            return
        settings = plan.motion
        same = doing == self._doing and target == self._aimed
        if same and self.settled:
            return
        self._aimed, self.settled = target, False
        if doing != self._doing:
            self._doing = doing
            self._root[1] += settings.jolt_root[0]
            self._root[3] += settings.jolt_root[1]
            for name, (turning, growing) in settings.jolt_bones.items():
                state = self._bones.get(name)
                if state is not None:
                    state[1] += turning
                    state[3] += growing
        self._lag = min(self._lag + seconds, settings.step * settings.max_steps)
        if self._lag < settings.step:
            return
        aims = plan.every_bone(target)
        while self._lag >= settings.step:
            self._step(plan, aims, target.root, settings.step)
            self._lag -= settings.step
        if same and self.at_rest() and self._there(aims, target.root):
            # As good as there: it is put there, and need not be moved again until it is told otherwise.
            self.snap(plan, target, doing)

    def _there(self, aims: dict[str, tuple[float, float]], root: tuple[float, float], within: float = 1e-3) -> bool:
        """Whether every bone is where it was going."""
        if abs(self._root[0] - root[0]) > within or abs(self._root[2] - root[1]) > within:
            return False
        return all(
            abs(state[0] - aims[name][0]) < within and abs(state[2] - aims[name][1]) < within
            for name, state in self._bones.items()
            if name in aims
        )

    def _step(self, plan: SkeletonPlan, aims: dict[str, tuple[float, float]], root: tuple[float, float], step: float) -> None:
        settings = plan.motion
        self._spring(self._root, 0, root[0], settings.root, step)
        self._spring(self._root, 2, root[1], settings.root, step)
        bones, springs, loose = self._bones, settings.springs, settings.spring
        # Bones are listed from the root outwards: the one a bone hangs from has always moved first.
        for name, hangs_from in plan.hangs_from.items():
            state = bones.get(name)
            if state is None:
                state = bones[name] = [aims[name][0], 0.0, aims[name][1], 0.0]
            spring = springs.get(name, loose)
            angle, scale = aims[name]
            if spring.drag and hangs_from is not None:
                # Left behind by as much as what it hangs from is swinging.
                angle -= spring.drag * bones[hangs_from][1]
            self._spring(state, 0, angle, spring, step)
            self._spring(state, 2, scale, spring, step)

    @staticmethod
    def _spring(state: list[float], at: int, aim: float, spring: Spring, step: float) -> None:
        """Move one number and its speed forward a step, drawn towards where it should be."""
        kept, gained, turned, slowed = spring.stepped(step)
        off, speed = state[at] - aim, state[at + 1]
        state[at] = aim + kept * off + gained * speed
        state[at + 1] = turned * off + slowed * speed

    def keyframe(self) -> Keyframe:
        """Where every bone is right now, as a pose."""
        return Keyframe(
            (self._root[0], self._root[2]), {name: (state[0], state[2]) for name, state in self._bones.items()}
        )

    def at_rest(self, within: float = 1e-3) -> bool:
        """Whether nothing of the body is moving any more."""
        return (
            abs(self._root[1]) < within
            and abs(self._root[3]) < within
            and all(abs(state[1]) < within and abs(state[3]) < within for state in self._bones.values())
        )
