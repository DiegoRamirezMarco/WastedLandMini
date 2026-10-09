import math
import unittest
from dataclasses import replace

from graphics.doll import DOLL_FACINGS
from graphics.face import load_rules
from graphics.turn import turned_pose
from simulation.registries import builtin_registries
from skeleton.plan import FACINGS, builtin_plan

MOMENTS = 16


def bend(first: tuple[float, float], second: tuple[float, float]) -> float:
    """How far a part of a limb is turned from the part before it, in degrees."""
    cross = first[0] * second[1] - first[1] * second[0]
    return abs(math.degrees(math.atan2(cross, first[0] * second[0] + first[1] * second[1])))


def part(pose: dict, start: str, end: str) -> tuple[float, float]:
    return (pose[end][0] - pose[start][0], pose[end][1] - pose[start][1])


class WalkSeenFromTheFrontTests(unittest.TestCase):
    """A walk written to be seen from the side, on a body that faces the window or has its
    back to it: the ground is seen from above, and what is nearer is lower on the screen."""

    def setUp(self) -> None:
        self.plan = builtin_plan()
        self.rules = load_rules()
        self.turn = self.rules.body
        self.side = self.rules.side
        self.walks = [manner.clip for manner in builtin_registries().manners.of_kind("walk")]

    def shown(self, clip: str, moment: float, yaw: float, facing: str = "right", turn=None) -> dict:
        name = DOLL_FACINGS[facing]
        _, _, mirrored, swapped = FACINGS[name]
        pose = self.plan.pose(name, clip, moment)
        return turned_pose(turn or self.turn, {}, pose, yaw, self.side, mirrored, swapped)

    def test_from_its_side_and_three_quarters_on_a_body_walks_as_it_did(self) -> None:
        flat = replace(self.turn, tilt=0.0, sharpest=0.0)
        self.assertGreater(self.turn.tilt, 0.0)
        for clip in self.walks:
            for step in range(MOMENTS):
                for yaw in (self.side, self.side / 2, self.side * 1.5):
                    self.assertEqual(self.shown(clip, step / MOMENTS, yaw), self.shown(clip, step / MOMENTS, yaw, turn=flat), (clip, yaw))

    def test_seen_from_the_front_a_foot_put_forward_comes_down_the_screen_and_from_behind_goes_up_it(self) -> None:
        for facing in ("right", "left"):
            name = DOLL_FACINGS[facing]
            ahead = 1.0 if facing == "right" else -1.0
            for clip in self.walks:
                # How much further ahead one foot is than the other at each moment, as it is
                # seen from the side: and the two moments of the stride at its longest, each way.
                poses = [self.plan.pose(name, clip, step / MOMENTS) for step in range(MOMENTS)]
                strides = [(pose["foot_left"][0] - pose["foot_right"][0]) * ahead for pose in poses]
                for step in (strides.index(max(strides)), strides.index(min(strides))):
                    pose, apart = poses[step], strides[step]
                    self.assertGreater(abs(apart), 1.5, clip)
                    front, behind = self.shown(clip, step / MOMENTS, 0.0, facing), self.shown(clip, step / MOMENTS, 2 * self.side, facing)
                    lower = lambda shown: shown["foot_left"][1] - shown["foot_right"][1] - (pose["foot_left"][1] - pose["foot_right"][1])
                    self.assertGreater(lower(front) * apart, 0.0, (clip, facing, step))
                    self.assertLess(lower(behind) * apart, 0.0, (clip, facing, step))

    def test_its_feet_go_up_and_down_the_screen_as_it_walks_which_they_did_not(self) -> None:
        flat = replace(self.turn, tilt=0.0, sharpest=0.0)
        for clip in self.walks:
            def travel(turn) -> float:
                heights = [self.shown(clip, step / MOMENTS, 0.0, turn=turn)["foot_left"][1] for step in range(MOMENTS)]
                return max(heights) - min(heights)

            self.assertGreater(travel(self.turn), travel(flat) + 1.0, clip)

    def test_no_limb_is_folded_back_on_itself_or_brought_to_nothing(self) -> None:
        limbs = (("hip", "knee", "foot"), ("shoulder", "elbow", "hand"))
        for clip in [*self.walks, "idle"]:
            for step in range(MOMENTS):
                pose = self.plan.pose(DOLL_FACINGS["right"], clip, step / MOMENTS)
                for yaw in (0.0, self.side / 4, 2 * self.side - self.side / 4, 2 * self.side):
                    shown = self.shown(clip, step / MOMENTS, yaw)
                    for first, middle, last in limbs:
                        for which in ("_left", "_right"):
                            upper = part(shown, first + which, middle + which)
                            lower = part(shown, middle + which, last + which)
                            where = (clip, step, yaw, first + which)
                            self.assertLessEqual(bend(upper, lower), self.turn.sharpest + 0.01, where)
                            for shown_part, start, end in ((upper, first, middle), (lower, middle, last)):
                                long = math.hypot(*part(pose, start + which, end + which))
                                self.assertGreaterEqual(math.hypot(*shown_part), long * self.turn.least_long - 0.01, where)

    def test_a_hand_and_a_foot_are_laid_at_the_end_of_their_limb_as_they_were(self) -> None:
        flat = replace(self.turn, tilt=0.0, sharpest=0.0)
        for clip in self.walks:
            for step in range(MOMENTS):
                now, was = self.shown(clip, step / MOMENTS, 0.0), self.shown(clip, step / MOMENTS, 0.0, turn=flat)
                for start, end in (("foot_left", "toe_left"), ("hand_right", "fingertip_right")):
                    for one, other in zip(part(now, start, end), part(was, start, end)):
                        self.assertAlmostEqual(one, other, places=6)


if __name__ == "__main__":
    unittest.main()
