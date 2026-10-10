import os
import tempfile
import unittest
from pathlib import Path

import pygame

from graphics.hand import load_rules as load_hand_rules
from graphics.poses import PLAIN_WORK, builtin_poses
from simulation.registries import builtin_registries
from simulation.residents.activity import Activity
from skeleton.plan import builtin_plan

LOOKS = {
    "cook": "stir", "bartender": "wipe", "guard": "watch", "medic": "bandage", "mechanic": "wrench",
    "shopkeeper": "counter", "scavenger": "rummage", "water_carrier": "pump", "researcher": "write", "chemist": "mix",
}


class JobLooksTests(unittest.TestCase):
    """Every job has a way of working of its own (P79): as data, and on the map of the real game."""

    def test_every_job_there_is_has_a_look_of_its_own(self) -> None:
        poses, jobs = builtin_poses(), builtin_registries().jobs
        self.assertEqual(set(poses.jobs), set(jobs), "no job is left to the work of bare hands")
        seen = {job_id: poses.working(job_id, False).clip for job_id in jobs}
        self.assertEqual({job_id: clip for job_id, clip in seen.items() if job_id in LOOKS}, LOOKS)
        self.assertNotIn(PLAIN_WORK, seen.values())
        self.assertEqual(len(set(seen.values())), len(seen), "no two jobs look the same")
        # Whoever has no job, or one there is none of, works as anybody does with bare hands.
        self.assertEqual(poses.working(None, False).clip, PLAIN_WORK)
        self.assertEqual(poses.working("juggler", True).clip, PLAIN_WORK)

    def test_each_of_those_clips_moves_a_body_and_has_a_way_to_hold_the_hands(self) -> None:
        plan, hands = builtin_plan(), load_hand_rules()
        at_rest = plan.pose("right")
        for clip in LOOKS.values():
            poses = [plan.pose("right", clip, moment / 8) for moment in range(8)]
            self.assertTrue(any(pose != poses[0] for pose in poses), f"{clip} does not move")
            self.assertTrue(all(pose["hand_right"] != at_rest["hand_right"] for pose in poses[:6]), f"{clip} is done with the hands")
            self.assertEqual(set(plan.pose("down", clip, 0.3)), set(at_rest))
            self.assertIn(clip, hands.clips)
        # Whoever rummages is bent well over, and whoever keeps a watch stands straight.
        bent = lambda clip: plan.pose("right", clip, 0.0)["neck"][0] - plan.pose("right", clip, 0.0)["pelvis"][0]
        self.assertGreater(bent("rummage"), bent("watch") + 1.5)


class JobsOnTheMapTests(unittest.TestCase):
    def setUp(self) -> None:
        for variable in ("SDL_VIDEODRIVER", "SDL_AUDIODRIVER"):
            self.addCleanup(self._restore, variable, os.environ.get(variable))
            os.environ[variable] = "dummy"
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        root = Path(self._tmp.name) / "illustrations"
        root.mkdir()
        self.addCleanup(pygame.quit)
        from game.game import Game

        self.game = Game(illustrations_dir=root, voices_dir=None, start_in_menu=False)
        self.view, self.world = self.game.global_view, self.game.world
        self.raul = self.world.residents["raul"]

    @staticmethod
    def _restore(variable: str, previous: str | None) -> None:
        if previous is None:
            os.environ.pop(variable, None)
        else:
            os.environ[variable] = previous

    def test_at_their_post_each_is_seen_at_the_work_of_their_job(self) -> None:
        view, raul = self.view, self.raul
        raul.x, raul.y, raul.trail = 20, 14, []
        for job_id, clip in LOOKS.items():
            raul.job_id = job_id
            raul.activity = Activity("work", minutes_left=60, using=True)
            self.assertEqual(view._bearing(raul), (clip, view.poses.jobs[job_id].bare.rate, None), job_id)
        # And they are seen at it on the window: their hands are not where they hang.
        raul.job_id = "water_carrier"
        view.centre_on((20, 14))
        heights = set()
        for _ in range(50):
            raul.activity = Activity("work", minutes_left=60, using=True)
            view.update(1 / 60)
            view.render()
            self.game.present()
            skeleton = next(entry[2] for entry in view._doll_draws if entry[1] is view.doll_shown["raul"])
            heights.add(round(skeleton.joints["hand_right"].y - skeleton.joints["chest"].y, 1))
        self.assertGreater(max(heights) - min(heights), 1.5, "the handle goes up and down")

    def test_the_screen_they_are_drawn_on_shows_them_at_their_own_work(self) -> None:
        studio, raul = self.game.doll_editor, self.raul
        raul.job_id = "cook"
        studio.open("raul")
        self.assertEqual(studio._own_clip("hammer"), "stir")
        raul.job_id = None
        self.assertEqual(studio._own_clip("hammer"), "hammer")


if __name__ == "__main__":
    unittest.main()
