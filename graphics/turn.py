"""A body turned towards the screen: where its limbs go when its trunk has gone round.

A doll's trunk is drawn from the front and wrapped round something solid (`graphics/volume.py`),
so it can be seen from any way round between the front and its side. Its arms and legs are of
rubber and round, look the same from anywhere, and are moved by clips that know only a body
seen from its side. So a limb is never looked at from further round. It is moved whole:

- its shoulder or its hip is on the side of the trunk, and goes round with it: seen from the
  side the two of a pair are one behind the other, and seen from the front they are as far
  apart as the trunk is wide there
- how far ahead of the trunk or behind it a limb hangs, which whoever draws a doll says for a
  body seen from its side, goes round too: seen from the front it is no more across the
  screen than a nose is, and both of a pair are the same way out from the middle of the trunk
- nothing of a limb is made longer or shorter, and none is laid in another order: it is the
  limb it was, somewhere else

That is right for a body standing, whichever way it is turned, and for one that is at
something as near the front as three quarters. Nearer than that, what its clips have it do
across the screen is done more and more towards whoever looks, and is seen less across: every
joint is brought in towards the middle of the trunk, or towards where its limb begins, down to
a share of the way seen from the front. So a leg that swings ahead is shorter and not out to
one side, and a limb is as much thicker as its rubber makes it for being shorter. Whoever
shows a body may still keep one that is at something from turning nearer than three quarters
(`body_yaw`).

How far out on the trunk the limbs are is data (`body` in `data/face.json`).
"""

import math
from collections.abc import Callable, Hashable

from graphics.doll import Doll
from graphics.face import BodyTurn
from graphics.volume import half_width
from skeleton.plan import SIDES

Point = tuple[float, float]

# The side of the body that is nearer when it is seen from its side.
NEAR_SIDE = "_right"
# The joint the trunk and the head are brought in towards, nearer the front than three quarters.
AXIS = "pelvis"
# What how much further out a limb stands, seen from the front, is kept under: the name of its
# first joint and this.
CLEAR = "~clear"


def body_yaw(turn: BodyTurn, yaw: float, standing: bool = False) -> float:
    """How far round a body is shown when its head is `yaw` degrees round: the same if it only
    stands, and never nearer the front than its clips can bear if it is at something."""
    return abs(yaw) if standing else min(max(abs(yaw), turn.nearest), 180.0 - turn.nearest)


def limbs_apart(turn: BodyTurn, doll: Doll) -> dict[str, float]:
    """How far to its own side each limb of a doll is when the doll faces the screen, in the
    skeleton's own measure, by what each of its joints is called without its side: as far out
    as the part of the trunk it hangs beside is wide, or some share of that."""
    apart = {}
    for limb in turn.limbs.values():
        far = half_width(doll, limb.beside) * limb.share
        apart.update({joint: far for joint in limb.joints})
        # And how much further out than that it stands, from right in front or right behind.
        apart[f"{limb.joints[0]}{CLEAR}"] = half_width(doll, limb.clear_of) * limb.clear if limb.clear_of else 0.0
    return apart


def turned_pose(
    turn: BodyTurn,
    apart: dict[str, float],
    pose: dict[str, Point],
    yaw: float,
    side: float,
    mirrored: bool = False,
    swapped: bool = False,
) -> dict[str, Point]:
    """A pose as it is shown with the body `yaw` degrees round from facing the screen, where
    `side` degrees is seen from its side. `apart` is how far to its side each limb is from the front.

    `mirrored` and `swapped` are how the body faces, as the skeleton has them: one that faces
    left is the other in a mirror, and may call its sides by each other's names.
    """
    # As far round as right behind: there its limbs have changed sides, as limbs seen from
    # behind have, and what it does is towards whoever looks again, the other way.
    angle = math.radians(max(0.0, min(2.0 * side, abs(yaw))) * 90.0 / side)
    sine, cosine = math.sin(angle), math.cos(angle)
    # How much of what is done across the screen is still seen across it: all of it down to
    # three quarters, and less and less from there to the front, or to right behind.
    whole_from = math.sin(math.radians(max(0.0, min(side, turn.nearest)) * 90.0 / side))
    swing = 1.0 if sine >= whole_from or whole_from <= 0.0 else turn.least_swing + (1.0 - turn.least_swing) * sine / whole_from
    # How far it is from three quarters towards right in front or right behind: none of the
    # way at three quarters and beyond, all of it there.
    fronted = (1.0 - swing) / (1.0 - turn.least_swing) if turn.least_swing < 1.0 else 0.0
    # In a mirror the near side is on the other hand, unless the names went over with it.
    hand = (-1.0 if mirrored else 1.0) * (-1.0 if swapped else 1.0)
    shown = dict(pose)
    if swing < 1.0 and AXIS in pose:
        # The trunk and the head lean towards whoever looks, and so lean less across.
        of_limbs = {f"{joint}{which}" for limb in turn.limbs.values() for joint in limb.joints for which in SIDES}
        middle = pose[AXIS][0]
        for joint, (x, y) in pose.items():
            if joint not in of_limbs:
                shown[joint] = (middle + (x - middle) * swing, y)
        for by, joint in turn.stiff:
            if by in pose and joint in pose:
                shown[joint] = (shown[by][0] + pose[joint][0] - pose[by][0], pose[joint][1])
    for limb in turn.limbs.values():
        for which in SIDES:
            first = f"{limb.joints[0]}{which}"
            if first not in pose:
                continue
            # Ahead of the trunk or behind it, which is across the screen only from the side.
            hangs = limb.hangs_from if limb.hangs_from in pose else None
            ahead = pose[first][0] - pose[hangs][0] if hangs is not None else 0.0
            out = apart.get(limb.joints[0], 0.0) + apart.get(f"{limb.joints[0]}{CLEAR}", 0.0) * fronted
            to_its_side = out * (-1.0 if which == NEAR_SIDE else 1.0) * hand
            begins = (shown[hangs][0] if hangs is not None else pose[first][0]) + ahead * sine + to_its_side * cosine
            before, at = pose[first], begins
            shown[first] = (begins, pose[first][1])
            for joint in limb.joints[1:]:
                if f"{joint}{which}" not in pose:
                    continue
                x, y = pose[f"{joint}{which}"]
                across, down = x - before[0], y - before[1]
                share = swing
                least = math.hypot(across, down) * turn.least_long
                if swing < 1.0 and across and (across * share) ** 2 + down * down < least * least:
                    # Seen all but end on, it would be no length at all: it is as much
                    # across the screen as leaves it the least it may be.
                    share = min(1.0, math.sqrt(max(0.0, least * least - down * down)) / abs(across))
                at += across * share
                shown[f"{joint}{which}"] = (at, y)
                before = (x, y)
    return shown


class Turned:
    """Dolls as each is turned, for whoever shows many at once and may keep no frame waiting.

    Turning a doll a way it has not been turned yet is not quick: its trunk is wrapped round
    again, and its head put together again. One doll beside a paper bears that. Thirty that
    all turn in the same frame do not: so only so many are turned a new way in a frame, and
    the rest are shown, for that frame, the nearest way they have been turned already. A doll
    that has not been turned any way yet is turned whatever is left: there is nothing else to
    show of it.
    """

    def __init__(self, a_frame: int = 2) -> None:
        # How many dolls may be turned a new way in one frame.
        self.a_frame = a_frame
        self._left = a_frame
        self._kept: dict[Hashable, dict[float, Doll]] = {}

    def new_frame(self) -> None:
        self._left = self.a_frame

    @property
    def spent(self) -> bool:
        """Whether no more may be turned a new way in this frame."""
        return self._left <= 0

    def take(self) -> None:
        """Count something else that is not quick as one doll turned a new way in this frame."""
        self._left -= 1

    def forget(self, who: Hashable) -> None:
        """Let go of every way one doll was turned: its drawing has changed."""
        self._kept.pop(who, None)

    def seen(self, who: Hashable, yaw: float, make: Callable[[float], Doll]) -> Doll:
        """One doll turned `yaw` degrees, or as near that as it has been turned if no more
        may be turned in this frame. `make` turns it: it is asked at most once for each way."""
        ways = self._kept.setdefault(who, {})
        if yaw in ways:
            return ways[yaw]
        if ways and self._left <= 0:
            return ways[min(ways, key=lambda other: abs(other - yaw))]
        self._left -= 1
        ways[yaw] = make(yaw)
        return ways[yaw]
