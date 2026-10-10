import os
import tempfile
import unittest
from pathlib import Path

import pygame

from graphics.face import SHUT
from graphics.hand import load_rules as load_hand_rules
from graphics.poses import builtin_poses
from simulation.registries import builtin_registries
from simulation.residents.activity import Activity
from simulation.residents.manner import ARGUE
from skeleton.plan import IDLE_CLIP, builtin_plan

CLIPS = ("hug", "kiss", "flirt", "point", "cower", "shove", "stagger", "comfort", "cry", "bow", "dance", "sing", "cards", "chess")


class DealingDataTests(unittest.TestCase):
    """What two do together that is not talk, and what is done alone with a look of its own: as data."""

    def test_every_clip_moves_a_body_from_the_side_and_can_be_shown_from_the_front(self) -> None:
        plan = builtin_plan()
        at_rest = plan.pose("right")
        for clip in CLIPS:
            poses = [plan.pose("right", clip, moment / 8) for moment in range(8)]
            self.assertTrue(any(pose != poses[0] for pose in poses), f"{clip} does not move")
            self.assertTrue(any(pose["hand_right"] != at_rest["hand_right"] or pose["head"] != at_rest["head"] for pose in poses), clip)
            self.assertEqual(set(plan.pose("down", clip, 0.3)), set(at_rest))
        # Whoever hugs has both hands out in front of them, and whoever cowers has theirs over their head.
        hug = plan.pose("right", "hug", 0.0)
        self.assertGreater(min(hug["hand_left"][0], hug["hand_right"][0]), hug["chest"][0] + 2.0)
        cower = plan.pose("right", "cower", 0.0)
        self.assertLess(max(cower["hand_left"][1], cower["hand_right"][1]), cower["chest"][1])
        # Whoever is shoved goes back as whoever shoves comes on.
        self.assertGreater(plan.pose("right", "shove", 0.25)["pelvis"][0], at_rest["pelvis"][0] + 0.8)
        self.assertLess(plan.pose("right", "stagger", 0.3)["pelvis"][0], at_rest["pelvis"][0] - 0.8)

    def test_whatever_is_shown_is_something_there_is_with_a_clip_and_a_way_to_hold_the_hands(self) -> None:
        poses, plan, hands = builtin_poses(), builtin_plan(), load_hand_rules()
        interactions = builtin_registries().interactions
        used = set()
        for action, together in poses.together.items():
            self.assertIn(action, interactions, action)
            self.assertTrue(together.doer is not None or together.other is not None, action)
            used.update(role.clip for role in (together.doer, together.other) if role is not None)
        used.update(showing.clip for showing in poses.alone.values())
        self.assertEqual(used, set(CLIPS))
        for clip in used:
            self.assertIn(clip, plan.clips)
            self.assertIn(clip, hands.clips, "hands that are made are held some way at it")
        # What has a look of its own is not left out of talk for having none.
        self.assertFalse(set(poses.talk.silent) & set(poses.together))
        self.assertTrue(poses.together["kiss"].doer.eyes_shut and poses.together["kiss"].other.eyes_shut)
        self.assertTrue(poses.alone["sing"].mouth_goes)
        self.assertGreater(poses.together["hug"].near, 0.0)
        self.assertEqual(poses.together["dance"].near, 0.0)


class DealingTests(unittest.TestCase):
    """Two at something together on the map of the real game, without a window."""

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
        self.raul, self.lucia = self.world.residents["raul"], self.world.residents["lucia"]

    @staticmethod
    def _restore(variable: str, previous: str | None) -> None:
        if previous is None:
            os.environ.pop(variable, None)
        else:
            os.environ[variable] = previous

    def meet(self, action: str) -> None:
        """Have Raúl come to Lucía for something, a while ago."""
        began = self.world.clock.total_minutes - 30
        raul, lucia = self.raul, self.lucia
        raul.x, raul.y, raul.trail, raul.facing = 20, 14, [], "right"
        lucia.x, lucia.y, lucia.trail, lucia.facing = 21, 14, [], "left"
        raul.activity = Activity(action, partner_id="lucia", minutes_left=600, using=True, began_at=began, intent=action)
        lucia.activity = Activity(action, partner_id="raul", minutes_left=600, using=True, began_at=began)

    def clips(self) -> tuple[str, str]:
        return self.view._bearing(self.raul)[0], self.view._bearing(self.lucia)[0]

    def test_each_of_two_is_shown_at_their_own_part_of_it(self) -> None:
        view, world = self.view, self.world
        for action, (does, other) in {
            "hug": ("hug", "hug"), "kiss": ("kiss", "kiss"), "shove": ("shove", "stagger"), "cow": ("point", "cower"),
            "hear_out": ("comfort", "cry"), "dance": ("dance", "dance"), "tell_off": ("point", "cower"),
        }.items():
            self.meet(action)
            self.assertTrue(view._began_it(self.raul) and not view._began_it(self.lucia))
            self.assertEqual(self.clips(), (does, other), action)
            self.assertEqual(view._bearing(self.raul)[1], view.poses.together[action].doer.rate)
        # Whoever has no part of their own in it speaks or listens, as at any talk: or has
        # words in their own way, if it is that kind of thing.
        self.meet("flirt")
        self.assertEqual(self.clips()[0], "flirt")
        self.assertIn(self.clips()[1], ("listen", world.manner_of(self.lucia, "talk").clip))
        self.meet("belittle")
        self.assertEqual(self.clips(), (world.manner_of(self.raul, ARGUE).clip, "cower"))
        self.meet("insult")
        self.assertEqual(self.clips(), (world.manner_of(self.raul, ARGUE).clip, world.manner_of(self.lucia, ARGUE).clip))
        # What has no look of its own yet is as it was.
        self.meet("pamper")
        self.assertEqual(self.clips(), (IDLE_CLIP, IDLE_CLIP))

    def test_what_is_done_with_the_arms_round_somebody_is_done_from_nearer(self) -> None:
        view = self.view
        self.meet("chat")
        self.assertEqual((view.sway(self.raul), view.sway(self.lucia)), (0.0, 0.0))
        self.meet("hug")
        near = view.poses.together["hug"].near
        self.assertEqual((view.sway(self.raul), view.sway(self.lucia)), (near, -near))
        # One above the other, they stay where they are: they are seen from their side.
        self.lucia.x, self.lucia.y = 20, 15
        self.assertEqual(view.sway(self.raul), 0.0)
        # And nobody is drawn towards somebody who is still on their way.
        self.meet("hug")
        self.lucia.trail = [(22, 14), (21, 14)]
        self.assertEqual(view.sway(self.raul), 0.0)

    def test_their_faces_do_what_goes_with_it(self) -> None:
        view, moves = self.view, self.game.figures.rules.moves
        self.meet("kiss")
        for resident in (self.raul, self.lucia):
            looks = {view._look_of(resident) for view.time in (tick / 60 for tick in range(120))}
            self.assertEqual({look.lids for look in looks}, {moves.steps(SHUT)}, "their eyes are shut all the while")
            self.assertEqual({look.mouth for look in looks}, {0})
        self.meet("hear_out")
        self.assertEqual(view._look_of(self.lucia).lids, moves.steps(SHUT))
        self.assertNotEqual({view._look_of(self.raul).lids for view.time in (tick / 60 for tick in range(60))}, {moves.steps(SHUT)})

    def test_alone_they_dance_and_sing_and_sat_down_to_it_they_do_it_on_the_body_that_sits(self) -> None:
        view, raul = self.view, self.raul
        raul.x, raul.y, raul.trail = 20, 14, []
        raul.activity = Activity("dance_alone", minutes_left=60, using=True)
        self.assertEqual(view._bearing(raul), ("dance", view.poses.alone["dance_alone"].rate, None))
        raul.activity = Activity("sing", minutes_left=60, using=True)
        clip, rate, overlay = view._bearing(raul)
        seat = view._seat_of(raul)
        self.assertEqual((clip, overlay) if seat is not None else (clip, overlay), (seat[0], "sing") if seat is not None else ("sing", None))
        self.assertEqual(rate, view.poses.alone["sing"].rate)
        mouths = {view._look_of(raul).mouth for view.time in (tick / 60 for tick in range(40))}
        self.assertEqual(mouths, {0, 1, 2}, "whoever sings has their mouth going")
        view._seat_of = lambda resident: ("sit_stool", 0.2)
        raul.activity = Activity("play_chess", minutes_left=60, using=True)
        self.assertEqual(view._bearing(raul), ("sit_stool", view.poses.alone["play_chess"].rate, "chess"))

    def test_they_are_seen_at_it_on_the_window(self) -> None:
        view, game = self.view, self.game
        self.meet("hug")
        view.centre_on((20.5, 14))
        gaps = []
        for _ in range(30):
            view.update(1 / 60)
            view.render()
            game.present()
            hands = {}
            for name in ("raul", "lucia"):
                skeleton = next(entry[2] for entry in view._doll_draws if entry[1] is view.doll_shown[name])
                hands[name] = skeleton.joints["pelvis"].x
            gaps.append(abs(hands["lucia"] - hands["raul"]))
        # A tile apart where they stand, and a good deal less than that as they are shown.
        from settings import TILE_SIZE

        self.assertLess(gaps[-1], TILE_SIZE * 0.6)


if __name__ == "__main__":
    unittest.main()
