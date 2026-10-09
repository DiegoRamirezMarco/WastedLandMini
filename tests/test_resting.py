"""How lying on the ground is shown: curled up there, with lying down and getting up seen when they are."""

import math
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import pygame

from graphics.assets import ASSETS_DIR, AssetStore
from graphics.body_renderer import BodyRenderer
from graphics.poses import builtin_poses, poses_from_data
from scenes.body_stage import UNSEEN_SECONDS, BodyStage
from simulation.family.family_system import SLEEP_ROUGH_ACTION
from simulation.residents.activity import Activity
from simulation.world import SimulationWorld
from skeleton.plan import builtin_plan


class LyingClipsTests(unittest.TestCase):
    """Runs the body plan alone."""

    def setUp(self) -> None:
        self.plan = builtin_plan()
        self.rough = builtin_poses().rough

    def test_lying_down_and_getting_up_are_done_once_and_meet_lying_curled(self) -> None:
        rough = self.rough
        self.assertLessEqual({rough.down.clip, rough.up.clip}, self.plan.once)
        self.assertNotIn(rough.asleep.clip, self.plan.once)
        curled = self.plan.sample(rough.asleep.clip, "doll", 0.0)
        for clip, phase in ((rough.down.clip, 1.0), (rough.up.clip, 0.0)):
            there = self.plan.sample(clip, "doll", phase)
            self.assertEqual(there.bones.keys(), curled.bones.keys(), clip)
            for bone, (angle, long) in curled.bones.items():
                self.assertAlmostEqual(there.bones[bone][0], angle, 6, f"{clip} {bone}")
                self.assertAlmostEqual(there.bones[bone][1], long, 6, f"{clip} {bone}")
            self.assertAlmostEqual(math.dist(there.root, curled.root), 0.0, 6)
        # Both begin and end standing, as anybody stands.
        standing = self.plan.pose("doll_right")
        for clip, phase in ((rough.down.clip, 0.0), (rough.up.clip, 1.0)):
            pose = self.plan.pose("doll_right", clip, phase)
            for joint, point in standing.items():
                self.assertAlmostEqual(math.dist(pose[joint], point), 0.0, 6, f"{clip} {joint}")

    def test_curled_up_the_whole_body_is_low_on_the_ground_and_none_of_it_under(self) -> None:
        standing = self.plan.pose("doll_right")
        # Everything is from the spot between the feet: the ground is at nought, and up is less.
        tall = -min(y for _, y in standing.values())
        for facing in ("doll_right", "doll_left"):
            curled = self.plan.pose(facing, self.rough.asleep.clip)
            highest, lowest = min(y for _, y in curled.values()), max(y for _, y in curled.values())
            self.assertLessEqual(lowest, 1e-6, "no joint is under the ground")
            self.assertGreater(lowest, -2.5, "and it lies on it, not over it")
            self.assertLess(-highest, tall * 0.4, "it is well under half as high as it stands")
            across = max(x for x, _ in curled.values()) - min(x for x, _ in curled.values())
            self.assertGreater(across, -highest, "and longer than it is high")
            self.assertLess(abs(curled["head"][1] - curled["pelvis"][1]), 2.5, "head and hips are level")
        # All the way down and all the way up nothing goes under the ground either, whoever's body it is.
        for clip in (self.rough.down.clip, self.rough.up.clip, self.rough.asleep.clip):
            for step in range(21):
                pose = self.plan.pose("doll_right", clip, step / 20)
                self.assertLessEqual(max(y for _, y in pose.values()), 1e-6, (clip, step))
        # Facing the other way it is the same in a mirror: the head is at the other end.
        right, left = (self.plan.pose(facing, self.rough.asleep.clip) for facing in ("doll_right", "doll_left"))
        self.assertAlmostEqual(right["head"][0], -left["head"][0], 6)
        self.assertGreater(right["head"][0], right["pelvis"][0])

    def test_all_three_have_to_be_said_or_nothing_is_made_of_it(self) -> None:
        self.assertIsNone(poses_from_data({}).rough)
        for wrong in ({"down": {"clip": "lie_down"}}, "curled", {"down": {}, "asleep": {}, "up": {"rate": 0}}):
            with self.assertRaises(ValueError, msg=wrong):
                poses_from_data({"sleep_rough": wrong})
        for doing in (self.rough.down, self.rough.asleep, self.rough.up):
            self.assertIn(doing.clip, self.plan.clips)


class SeenToLieDownTests(unittest.TestCase):
    """The stage alone: what has been seen to begin, and what was found already so."""

    def setUp(self) -> None:
        pygame.init()
        pygame.display.set_mode((8, 8))
        self.addCleanup(pygame.quit)
        self.world = SimulationWorld.demo_world()
        self.stage = BodyStage(BodyRenderer(AssetStore(ASSETS_DIR), builtin_plan()))

    def _pass(self, seconds: float, frame: float = 1 / 60) -> None:
        for _ in range(round(seconds / frame)):
            self.stage.update(frame, self.world)

    def test_somebody_found_lying_has_lain_for_ever_and_somebody_seen_to_lie_down_since_then(self) -> None:
        stage = self.stage
        self.assertEqual(stage.rest("raul", True), (True, math.inf), "found asleep: nobody saw him lie down")
        self.assertEqual(stage.rest("ines", False), (False, math.inf))
        self._pass(0.2)
        self.assertEqual(stage.rest("raul", True), (True, math.inf))
        # She lies down in sight: it is counted from then.
        lying, seconds = stage.rest("ines", True)
        self.assertEqual((lying, seconds), (True, 0.0))
        self._pass(0.25)
        self.assertAlmostEqual(stage.rest("ines", True)[1], 0.25, 6)
        self._pass(0.25)
        self.assertAlmostEqual(stage.rest("ines", True)[1], 0.5, 6)
        # And gets up in sight.
        self.assertEqual(stage.rest("ines", False), (False, 0.0))
        self._pass(0.1)
        self.assertAlmostEqual(stage.rest("ines", False)[1], 0.1, 6)

    def test_what_nobody_was_looking_at_was_not_seen_to_begin(self) -> None:
        stage = self.stage
        stage.rest("ines", False)
        self._pass(UNSEEN_SECONDS + 0.2)
        self.assertEqual(stage.rest("ines", True), (True, math.inf), "off the screen she lay down unseen")
        # Looked at every frame, a change is seen however long she has been in sight.
        for _ in range(90):
            self.stage.update(1 / 60, self.world)
            stage.rest("ines", True)
        self.assertEqual(stage.rest("ines", False), (False, 0.0))

    def test_with_the_game_going_faster_so_does_lying_down(self) -> None:
        stage = self.stage
        stage.rest("ines", False)
        stage.rest("ines", True)
        self.world.clock.speed = 4
        self._pass(0.25)
        self.assertAlmostEqual(stage.rest("ines", True)[1], 1.0, 6)


class SleepingOnTheGroundTests(unittest.TestCase):
    """Runs the real game without a window, with folders of its own for drawings and content."""

    def setUp(self) -> None:
        for variable in ("SDL_VIDEODRIVER", "SDL_AUDIODRIVER"):
            self.addCleanup(self._restore_driver, variable, os.environ.get(variable))
            os.environ[variable] = "dummy"
        from game.game import Game

        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        (self.root / "illustrations").mkdir()
        (self.root / "custom").mkdir()
        self.game = Game(
            illustrations_dir=self.root / "illustrations",
            voices_dir=None,
            custom_content_dir=self.root / "custom",
            save_path=self.root / "save.json",
            start_in_menu=False,
        )
        self.addCleanup(pygame.quit)
        self.view, self.world = self.game.global_view, self.game.world
        # Time in the game stands still all the same: only the scene is let go on.
        self.world.clock.paused = False
        self.raul = self.world.residents["raul"]
        self.raul.x, self.raul.y, self.raul.trail, self.raul.facing, self.raul.activity = 20, 14, [], "right", None
        self.view.centre_on((20.5, 13.5))
        self.view.following = None
        self.rough = self.view.poses.rough

    @staticmethod
    def _restore_driver(variable: str, previous: str | None) -> None:
        if previous is None:
            os.environ.pop(variable, None)
        else:
            os.environ[variable] = previous

    def _frames(self, seconds: float) -> None:
        for _ in range(round(seconds * 60)):
            self.view.update(1 / 60)
            self.view.render()
            self.game.present()

    def _asleep(self) -> None:
        self.raul.activity = Activity(SLEEP_ROUGH_ACTION, minutes_left=400, using=True)

    def _doll_draw(self):
        return next((entry for entry in self.view._doll_draws if entry[1] is self.view.doll_shown.get("raul")), None)

    def test_on_the_window_they_are_seen_to_lie_down_curl_up_and_get_up_again(self) -> None:
        view, body = self.view, None
        self._frames(0.2)
        body = view.bodies.characters["raul"]
        self.assertEqual(body.clip, "idle")
        standing = view.hitboxes["raul"].copy()
        self._asleep()
        self._frames(0.2)
        self.assertEqual(body.clip, self.rough.down.clip)
        self.assertGreater(body.phase, 0.05)
        self.assertLess(body.phase, 0.5)
        self.assertFalse(body.idle, "nobody fidgets on the way down")
        self._frames(1.0 / self.rough.down.rate)
        self.assertEqual(body.clip, self.rough.asleep.clip)
        # Lying there the whole of them is shown, low on the ground, and no blanket over them.
        draw = self._doll_draw()
        self.assertIsNotNone(draw[2], "a body laid over its skeleton, not a head on a pillow")
        self.assertEqual(view._rough, [], "there is no blanket")
        left, top, right, bottom = draw[2].bounds()
        self.assertGreater(right - left, bottom - top)
        lying = view.hitboxes["raul"]
        self.assertLess(lying.height, standing.height * 0.75, "what is picked is as low as they lie")
        self.assertEqual(view._status_icon(self.raul, resting=True), "sleep")
        self.assertEqual(view._held, [])
        # Waking where they lie, they get up; then they stand as before.
        self.raul.activity = None
        self._frames(0.2)
        self.assertEqual(body.clip, self.rough.up.clip)
        self._frames(1.0 / self.rough.up.rate)
        self.assertEqual(body.clip, "idle")
        self.assertEqual(view.hitboxes["raul"].height, standing.height)

    def test_found_asleep_they_are_already_curled_up_and_walking_off_they_are_simply_up(self) -> None:
        view = self.view
        self._asleep()
        self._frames(0.1)
        body = view.bodies.characters["raul"]
        self.assertEqual(body.clip, self.rough.asleep.clip, "nobody saw them lie down")
        # They wake and walk off at once: there is no getting up to wait for.
        self.raul.activity = None
        self.raul.trail = [(self.raul.x - 1, self.raul.y), self.raul.tile]
        view.tick_progress = 0.5
        self._frames(0.1)
        self.assertEqual(body.clip, self.world.manner_of(self.raul, "walk").clip)
        self.assertIsNone(view._rough_pose(self.raul, 0.5))

    def test_the_small_bodies_shown_without_a_window_keep_their_blanket(self) -> None:
        view = self.view
        self._asleep()
        # As on a canvas alone: nobody is a doll.
        with mock.patch.object(type(view), "windowed", new_callable=mock.PropertyMock, return_value=False):
            view.render()
            self.assertIsNone(view._doll_for(self.raul))
            self.assertEqual(view._doll_draws, [])
        self.assertIn("raul", view.hitboxes)
        body = view.bodies.characters.get("raul")
        self.assertNotIn(body.clip if body is not None else "idle", (self.rough.down.clip, self.rough.asleep.clip))


if __name__ == "__main__":
    unittest.main()
