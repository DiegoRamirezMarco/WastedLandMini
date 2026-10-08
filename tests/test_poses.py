"""How work is shown: the clip of each job with its tool and without, and things held by their handle."""

import json
import math
import tempfile
import unittest
from pathlib import Path

import pygame

from graphics import item_pictures
from graphics.assets import ASSETS_DIR, AssetStore
from graphics.item_icons import ItemIcons
from graphics.poses import PLAIN_WORK, POSES_PATH, builtin_poses, poses_from_data
from simulation.registries import builtin_registries
from skeleton.plan import FACINGS, Grip, builtin_plan, plan_from_data

RED, BLUE = (200, 30, 30), (30, 60, 200)


class GripTests(unittest.TestCase):
    """Runs the body plan alone: no window, no pictures."""

    def setUp(self) -> None:
        self.plan = builtin_plan()

    def _palm(self, pose: dict, side: str) -> tuple[float, float]:
        wrist, tip = pose[f"hand_{side}"], pose[f"fingertip_{side}"]
        return ((wrist[0] + tip[0]) / 2, (wrist[1] + tip[1]) / 2)

    def test_a_clip_says_how_a_thing_with_a_handle_is_held_in_it(self) -> None:
        grips = self.plan.grips
        self.assertTrue(grips["hoe"].both, "a hoe is worked with both hands")
        self.assertFalse(grips["hammer"].both)
        self.assertGreater(grips["hammer"].turn, 0.0)
        for clip in ("idle", "walk", "work", "weed", "eat"):
            self.assertNotIn(clip, grips)
            self.assertIsNone(self.plan.handle(clip, "right", self.plan.pose("right", clip, 0.3)))
        # The places of the hands are the body plan's to name: no caller knows a joint.
        self.assertLessEqual({"held_item", "held_wrist", "other_item", "other_wrist"}, set(self.plan.anchors))

    def test_in_both_hands_a_handle_runs_from_the_palm_of_one_through_that_of_the_other(self) -> None:
        for phase in (0.0, 0.3, 0.55, 0.77):
            pose = self.plan.pose("doll_right", "hoe", phase)
            point, way, at = self.plan.handle("hoe", "doll_right", pose)
            near, far = self._palm(pose, "right"), self._palm(pose, "left")
            self.assertAlmostEqual(math.dist(point, far), 0.0, 6, "it is held by the hand of the far side, near its end")
            self.assertAlmostEqual(math.hypot(*way), 1.0, 6)
            reach = math.dist(near, far)
            self.assertGreater(reach, 2.5, "the hands are well apart, or there is no saying which way it runs")
            self.assertAlmostEqual(point[0] + way[0] * reach, near[0], 6)
            self.assertAlmostEqual(point[1] + way[1] * reach, near[1], 6)
            self.assertEqual(at, self.plan.grips["hoe"].at)
        # Raised it points up, and brought down it points ahead and into the ground.
        raised = self.plan.handle("hoe", "doll_right", self.plan.pose("doll_right", "hoe", 0.6))[1]
        struck = self.plan.handle("hoe", "doll_right", self.plan.pose("doll_right", "hoe", 0.0))[1]
        self.assertLess(raised[1], -0.8)
        self.assertGreater(struck[0], 0.4)
        self.assertGreater(struck[1], 0.4)

    def test_in_one_hand_it_is_turned_from_the_way_the_hand_points_and_mirrored_with_the_body(self) -> None:
        for phase in (0.0, 0.25, 0.4):
            pose = self.plan.pose("doll_right", "hammer", phase)
            point, way, _ = self.plan.handle("hammer", "doll_right", pose)
            wrist, tip = pose["hand_right"], pose["fingertip_right"]
            self.assertAlmostEqual(math.dist(point, self._palm(pose, "right")), 0.0, 6)
            pointing = math.atan2(tip[0] - wrist[0], tip[1] - wrist[1])
            turned = math.atan2(way[0], way[1]) - pointing
            self.assertAlmostEqual((turned + math.pi) % math.tau - math.pi, self.plan.grips["hammer"].turn, 6)
            # Facing the other way everything is in a mirror, the hammer too.
            other = self.plan.pose("doll_left", "hammer", phase)
            mirrored = self.plan.handle("hammer", "doll_left", other)
            self.assertTrue(FACINGS["doll_left"][2])
            self.assertAlmostEqual(mirrored[0][0], -point[0], 6)
            self.assertAlmostEqual(mirrored[0][1], point[1], 6)
            self.assertAlmostEqual(mirrored[1][0], -way[0], 6)
            self.assertAlmostEqual(mirrored[1][1], way[1], 6)

    def test_a_grip_that_cannot_be_is_refused_and_a_plan_without_hands_holds_nothing(self) -> None:
        data = json.loads((POSES_PATH.parent / "skeleton.json").read_text(encoding="utf-8"))
        for wrong in ({"hands": 3}, {"hands": 2, "at": 1.5}, "both"):
            clips = {**data["clips"], "hoe": {**data["clips"]["hoe"], "grip": wrong}}
            with self.assertRaises(ValueError):
                plan_from_data({**data, "clips": clips})
        bare = plan_from_data({**data, "anchors": {"mouth": "head"}})
        self.assertEqual(bare.grips["hoe"], Grip(True, 0.2))
        self.assertIsNone(bare.handle("hoe", "right", bare.pose("right", "hoe", 0.0)))


class PosesDataTests(unittest.TestCase):
    def setUp(self) -> None:
        self.poses = builtin_poses()
        self.plan = builtin_plan()
        self.registries = builtin_registries()

    def test_every_job_and_clip_and_thing_it_names_is_one_there_is(self) -> None:
        poses = self.poses
        shown = [poses.work, poses.build, *(each for job in poses.jobs.values() for each in (job.bare, job.tool) if each)]
        for doing in shown:
            self.assertIn(doing.clip, self.plan.clips)
            self.assertGreater(doing.rate, 0.0)
        for job_id, job in poses.jobs.items():
            self.assertIn(job_id, self.registries.jobs)
            if job.tool is not None:
                self.assertIsNotNone(self.registries.jobs[job_id].tool, f"{job_id} has a look with a tool and no tool")
        for thing in poses.handles:
            known = self.registries.items.find(thing) is not None
            self.assertTrue(known or item_pictures.painted(thing), f"{thing} has a handle and no picture")
        self.assertEqual(poses.work.clip, PLAIN_WORK)
        # What is done on taking something up or handing it over is done once, with one arm.
        self.assertIn(poses.pocket.clip, self.plan.once)
        self.assertGreater(poses.pocket.rate, 0.0)

    def test_work_is_shown_by_its_job_and_by_whether_its_tool_is_in_hand(self) -> None:
        poses = self.poses
        farming = poses.jobs["farmer"]
        self.assertIs(poses.working("farmer", True), farming.tool)
        self.assertIs(poses.working("farmer", False), farming.bare)
        self.assertNotEqual(farming.tool.clip, farming.bare.clip)
        self.assertIn(farming.tool.clip, self.plan.grips, "the tool is held by its handle in the clip of working with it")
        self.assertNotIn(farming.bare.clip, self.plan.grips)
        # A job with no look of its own is plain work, tool or no tool.
        for job_id in ("cook", None, "no such job"):
            self.assertIs(poses.working(job_id, True), poses.work)
            self.assertIs(poses.working(job_id, False), poses.work)
        # What builders are seen with is nobody's: it is no item.
        self.assertIsNotNone(poses.build.prop)
        self.assertIsNone(self.registries.items.find(poses.build.prop))
        self.assertIn(poses.build.prop, poses.handles)
        self.assertIn(poses.build.clip, self.plan.grips)

    def test_what_is_not_said_is_plain_and_what_cannot_be_is_refused(self) -> None:
        self.assertIsNone(poses_from_data({}).pocket, "where nothing is said of it, nothing is made of it")
        empty = poses_from_data({})
        self.assertEqual((empty.work.clip, empty.work.rate, empty.build.clip, empty.jobs, empty.handles), (PLAIN_WORK, 1.0, PLAIN_WORK, {}, {}))
        made = poses_from_data({"work": {"clip": "work", "rate": 2}, "jobs": {"farmer": {"tool": {"clip": "hoe"}}}})
        self.assertEqual((made.jobs["farmer"].bare.clip, made.jobs["farmer"].tool.clip, made.jobs["farmer"].tool.rate), ("work", "hoe", 2.0))
        for wrong in (
            {"work": {"rate": 0}},
            {"build": "hammer"},
            {"handles": {"hoe": {"from": [1, 1], "to": [1, 1], "long": 3}}},
            {"handles": {"hoe": {"from": [1, 1], "to": [9, 9], "long": 0}}},
            {"handles": {"hoe": {"from": [1], "to": [9, 9], "long": 3}}},
        ):
            with self.assertRaises(ValueError, msg=wrong):
                poses_from_data(wrong)


class GrippedPictureTests(unittest.TestCase):
    """A thing turned in the hand: pictures of the tests' own, in a folder of their own."""

    def setUp(self) -> None:
        pygame.init()
        pygame.display.set_mode((8, 8))
        self.addCleanup(pygame.quit)
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.custom = Path(self._tmp.name)
        # A stick drawn from the bottom left corner to the top right, red where it is held and blue at its far end.
        picture = pygame.Surface((64, 64), pygame.SRCALPHA)
        pygame.draw.line(picture, RED, (8, 56), (32, 32), 5)
        pygame.draw.line(picture, BLUE, (32, 32), (56, 8), 5)
        folder = self.custom / "items" / "stick"
        folder.mkdir(parents=True)
        pygame.image.save(picture, str(folder / "icon.png"))
        self.icons = ItemIcons(AssetStore(ASSETS_DIR), AssetStore(self.custom))
        self.ends = ((12.5, 87.5), (87.5, 12.5))

    def _middle(self, picture: pygame.Surface, color: tuple[int, int, int]) -> tuple[float, float]:
        return pygame.mask.from_threshold(picture, (*color, 255), (60, 60, 60, 255)).centroid()

    def test_it_is_as_long_as_it_is_told_and_runs_the_way_it_is_told(self) -> None:
        for way in ((1.0, 0.0), (0.0, 1.0), (0.0, -1.0), (-0.6, 0.8)):
            picture, point = self.icons.gripped("stick", *self.ends, 80.0, way)
            red, blue = self._middle(picture, RED), self._middle(picture, BLUE)
            # The end it is held by is where it is said to be, and the far end is that way from it.
            self.assertLess(math.dist(point, red), 24, way)
            along = ((blue[0] - point[0]) * way[0] + (blue[1] - point[1]) * way[1], (blue[0] - point[0]) * -way[1] + (blue[1] - point[1]) * way[0])
            self.assertAlmostEqual(along[0], 60.0, delta=6, msg=f"three quarters of the way along, running {way}")
            self.assertAlmostEqual(along[1], 0.0, delta=4, msg=way)
        short, _ = self.icons.gripped("stick", *self.ends, 30.0, (1.0, 0.0))
        self.assertLess(short.get_width(), 50)

    def test_the_point_it_is_held_at_is_wherever_along_the_handle_the_hand_is(self) -> None:
        end, point = self.icons.gripped("stick", *self.ends, 80.0, (1.0, 0.0))
        middle, held = self.icons.gripped("stick", *self.ends, 80.0, (1.0, 0.0), at=0.5)
        self.assertAlmostEqual(held[0] - point[0], 40.0, delta=1.5)
        self.assertAlmostEqual(held[1], point[1], delta=1.5)
        self.assertLess(math.dist(held, self._middle(middle, RED)), 24)
        self.assertLess(math.dist(held, self._middle(middle, BLUE)), 24)

    def test_whoever_faces_left_holds_it_the_other_way_round_and_pictures_are_kept(self) -> None:
        right, point = self.icons.gripped("stick", *self.ends, 80.0, (0.8, 0.6))
        left, other = self.icons.gripped("stick", *self.ends, 80.0, (-0.8, 0.6), mirrored=True)
        self.assertEqual(left.get_size(), right.get_size())
        self.assertAlmostEqual(other[0], left.get_width() - point[0], delta=1.0)
        for color in (RED, BLUE):
            here, there = self._middle(right, color), self._middle(left, color)
            self.assertAlmostEqual(there[0], left.get_width() - here[0], delta=2.0)
            self.assertAlmostEqual(there[1], here[1], delta=2.0)
        self.assertIs(self.icons.gripped("stick", *self.ends, 80.0, (0.8, 0.6))[0], right)
        # Drawn again in the item editor, it is turned from the new picture.
        self.icons.forget("stick")
        self.assertIsNot(self.icons.gripped("stick", *self.ends, 80.0, (0.8, 0.6))[0], right)

    def test_the_game_s_own_picture_is_painted_larger_for_a_hand_that_shows_it_large(self) -> None:
        icons = ItemIcons(AssetStore(ASSETS_DIR))
        icons.painted = True
        handle = builtin_poses().handles["hammer"]
        small, _ = icons.gripped("hammer", handle.start, handle.end, 20.0, (0.0, -1.0))
        large, _ = icons.gripped("hammer", handle.start, handle.end, 300.0, (0.0, -1.0))
        self.assertLess(small.get_height(), 60)
        self.assertGreater(large.get_height(), 300)
        self.assertEqual(set(icons._painted_large), {("hammer", 4)})


if __name__ == "__main__":
    unittest.main()
