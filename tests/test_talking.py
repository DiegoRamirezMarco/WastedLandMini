import os
import tempfile
import unittest
from pathlib import Path

import pygame

from graphics.poses import builtin_poses
from simulation.commands import SetMannerCommand
from simulation.residents.activity import Activity
from simulation.residents.manner import TALK, WALK
from skeleton.plan import IDLE_CLIP, builtin_plan
from ui.talk_bubble import TURN_MINUTES

CLIPS = ("talk_calm", "talk_hands", "talk_shy", "listen", "laugh", "wave")


class TalkingClipsTests(unittest.TestCase):
    def test_every_clip_of_talking_moves_a_body_from_the_side_and_can_be_shown_from_the_front(self) -> None:
        plan = builtin_plan()
        for clip in CLIPS:
            at_rest = plan.pose("right")
            poses = [plan.pose("right", clip, moment / 8) for moment in range(8)]
            self.assertTrue(any(pose != poses[0] for pose in poses), f"{clip} does not move")
            self.assertTrue(any(pose["hand_right"] != at_rest["hand_right"] or pose["head"] != at_rest["head"] for pose in poses), clip)
            self.assertEqual(set(plan.pose("down", clip, 0.3)), set(at_rest))
        # Whoever waves has a hand up by their head, and whoever listens has theirs down.
        wave = plan.pose("right", "wave", 0.25)
        self.assertLess(wave["hand_right"][1], wave["chest"][1])
        listen = plan.pose("right", "listen", 0.25)
        self.assertGreater(listen["hand_right"][1], listen["chest"][1])

    def test_how_a_talk_is_shown_is_data(self) -> None:
        talk = builtin_poses().talk
        self.assertEqual((talk.listen.clip, talk.laugh.clip, talk.greet.clip), ("listen", "laugh", "wave"))
        self.assertIn("joke", talk.laugh_at)
        self.assertIn("hug", talk.silent)
        self.assertGreater(talk.greet_minutes, 0)


class TalkingTests(unittest.TestCase):
    """Two who have something to say to each other, in the real game without a window."""

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

    def meet(self, action: str = "chat", minutes_ago: int = 0) -> None:
        """Have Raúl bring something up with Lucía, so long ago."""
        began = self.world.clock.total_minutes - minutes_ago
        raul, lucia = self.raul, self.lucia
        raul.x, raul.y, raul.trail, raul.facing = 20, 14, [], "right"
        lucia.x, lucia.y, lucia.trail, lucia.facing = 21, 14, [], "left"
        raul.activity = Activity(action, partner_id="lucia", minutes_left=600, using=True, began_at=began, brought=True)
        lucia.activity = Activity(action, partner_id="raul", minutes_left=600, using=True, began_at=began, brought=False)

    def test_there_is_a_way_of_speaking_for_each_nature_until_one_is_chosen(self) -> None:
        world, manners = self.world, self.world.registries.manners
        kind = manners.kind_for(TALK)
        self.assertEqual({manner.manner_id for manner in manners.of_kind(kind.kind_id)}, {"talk_calm", "talk_hands", "talk_shy"})
        nature = lambda **parts: {"sociability": 50.0, "impulsiveness": 50.0, **parts}
        for name in ("raul", "lucia", "tomas", "ines"):
            self.assertEqual(manners.default(name, TALK, nature(sociability=55.0, impulsiveness=82.0)).manner_id, "talk_hands")
            self.assertEqual(manners.default(name, TALK, nature(sociability=20.0)).manner_id, "talk_shy")
        # In the middle of everything it is anybody's guess, and the same guess every time.
        middling = {manners.default(name, TALK, nature()).manner_id for name in map(str, range(40))}
        self.assertEqual(middling, {"talk_calm", "talk_hands", "talk_shy"})
        self.assertEqual(manners.default("raul", TALK, nature()), manners.default("raul", TALK, nature()))
        # Manners that lean no way are whose they were, whatever anybody's nature.
        self.assertEqual(manners.default("raul", WALK, nature(sociability=0.0)), manners.default("raul", WALK))
        # Theirs is by their nature, and then whatever is chosen for them.
        raul = self.raul
        raul.personality.sociability, raul.personality.impulsiveness = 10.0, 50.0
        self.assertEqual(world.manner_of(raul, TALK).manner_id, "talk_shy")
        self.assertTrue(world.apply_command(SetMannerCommand("raul", TALK, "talk_hands")))
        self.assertEqual(world.manner_of(raul, TALK).manner_id, "talk_hands")

    def test_whoever_brought_it_up_greets_then_they_speak_by_turns_and_the_other_listens(self) -> None:
        view, world = self.view, self.world
        self.meet(minutes_ago=0)
        self.assertEqual(view._bearing(self.raul)[0], "wave")
        self.assertEqual(view._bearing(self.lucia)[0], "listen")
        own = {name: world.manner_of(world.residents[name], TALK).clip for name in ("raul", "lucia")}
        # Past the greeting, in the first turn it is whoever brought it up who speaks.
        self.meet(minutes_ago=TURN_MINUTES * 2 + 1)
        self.assertTrue(view._speaking(self.raul))
        self.assertFalse(view._speaking(self.lucia))
        self.assertEqual((view._bearing(self.raul)[0], view._bearing(self.lucia)[0]), (own["raul"], "listen"))
        self.assertGreater(view._bearing(self.raul)[1], 0.0)
        self.meet(minutes_ago=TURN_MINUTES * 3 + 1)
        self.assertEqual((view._bearing(self.raul)[0], view._bearing(self.lucia)[0]), ("listen", own["lucia"]))
        # Whoever speaks moves their mouth, and whoever listens does not.
        mouths = {name: set() for name in ("raul", "lucia")}
        for tick in range(40):
            view.time = tick / 60
            for name in mouths:
                mouths[name].add(view._look_of(world.residents[name]).mouth)
        self.assertEqual(mouths["lucia"], {0, 1, 2})
        self.assertEqual(mouths["raul"], {0})

    def test_what_is_told_to_make_somebody_laugh_makes_them_laugh(self) -> None:
        self.meet("joke", minutes_ago=TURN_MINUTES * 2 + 1)
        self.assertEqual(self.view._bearing(self.lucia)[0], "laugh")
        self.assertNotIn(self.view._bearing(self.raul)[0], ("laugh", "listen", IDLE_CLIP))

    def test_what_two_do_that_is_not_talk_is_not_shown_as_talk(self) -> None:
        self.meet("hug", minutes_ago=TURN_MINUTES * 2 + 1)
        self.assertEqual(self.view._bearing(self.raul), (IDLE_CLIP, 0.0, None))
        self.raul.activity = None
        self.assertEqual(self.view._bearing(self.raul), (IDLE_CLIP, 0.0, None))
        self.assertFalse(self.view._speaking(self.raul))

    def test_sitting_they_talk_with_their_hands_on_the_body_that_sits(self) -> None:
        view = self.view
        self.meet(minutes_ago=TURN_MINUTES * 2 + 1)
        view._seat_of = lambda resident: ("sit_stool", 0.2)
        clip, rate, overlay = view._bearing(self.raul)
        self.assertEqual((clip, overlay), ("sit_stool", self.world.manner_of(self.raul, TALK).clip))
        self.assertEqual(rate, self.world.manner_of(self.raul, TALK).rate)
        self.assertEqual(view._bearing(self.lucia)[2], "listen")

    def test_they_are_seen_at_it_on_the_window_and_on_the_screen_they_are_drawn_on(self) -> None:
        view, game = self.view, self.game
        self.meet(minutes_ago=TURN_MINUTES * 2 + 1)
        view.centre_on((20.5, 14))
        hands = set()
        for _ in range(50):
            view.update(1 / 60)
            view.render()
            game.present()
            skeleton = next(entry[2] for entry in view._doll_draws if entry[1] is view.doll_shown["raul"])
            hands.add(round(skeleton.joints["hand_right"].y - skeleton.joints["chest"].y, 1))
        self.assertGreater(max(hands) - min(hands), 1.0, "his hand goes up and down as he speaks")
        studio = game.doll_editor
        studio.open("raul")
        self.assertEqual(studio._own_clip("talk_calm"), self.world.manner_of(self.raul, TALK).clip)
        studio.clip = "talk_calm"
        self.assertEqual({studio._look().mouth for studio.time in (tick / 60 for tick in range(40))}, {0, 1, 2})


if __name__ == "__main__":
    unittest.main()
