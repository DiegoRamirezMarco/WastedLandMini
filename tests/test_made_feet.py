import math
import os
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame

from graphics.doll import BODY_CANVAS, DOLL_FACINGS, Doll, doll_plan, draw_doll, load_template
from graphics.foot import Feet, FootChoice, FootStore, Made, load_rules
from graphics.hand import HandChoice, Hands
from graphics.hand import load_rules as load_hand_rules
from graphics.mannequin import figures, tones_of
from skeleton.plan import builtin_plan
from skeleton.rig import Skeleton

SKIN = (214, 170, 130)
RED = (200, 30, 30)
LEVEL = math.pi / 2
LONG, DETAIL = 1.8, 40.0


class FootTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        pygame.init()
        pygame.display.set_mode((1, 1))
        cls.rules = load_rules()
        template = load_template()
        build = template.starting()
        cls.template = template.built(build)
        cls.plan = doll_plan(builtin_plan(), cls.template, build)
        cls.body = figures(cls.template, tones_of(SKIN, (30, 22, 20)), 5)[BODY_CANVAS]

    def test_a_foot_hangs_under_its_ankle_and_points_the_way_the_body_faces(self) -> None:
        feet = Feet(self.rules, FootChoice(True))
        long = LONG * DETAIL
        for mirrored, way in ((False, 1), (True, -1)):
            image, joint = feet.picture("foot_right", LEVEL * way, LONG, mirrored, DETAIL)
            box = image.get_bounding_rect()
            # Its sole is as far under the ankle as the rules have the ground, whichever way it faces.
            self.assertAlmostEqual(box.bottom - joint[1], long * (self.rules.sole + self.rules.line), delta=3)
            ahead, behind = (box.right - joint[0], joint[0] - box.left) if way > 0 else (joint[0] - box.left, box.right - joint[0])
            self.assertGreater(ahead, behind + long * 0.3)
            # And it covers its own ankle, where the leg ends.
            self.assertGreater(image.get_at((round(joint[0]), round(joint[1])))[3], 245)

    def test_a_larger_foot_stands_on_the_same_ground(self) -> None:
        feet = Feet(self.rules, FootChoice(True))
        small, joint = feet.picture("foot_right", LEVEL, LONG, False, DETAIL)
        feet.choose(size=self.rules.sizes[1])
        large, at = feet.picture("foot_right", LEVEL, LONG, False, DETAIL)
        self.assertGreater(large.get_bounding_rect().width, small.get_bounding_rect().width)
        self.assertAlmostEqual(large.get_bounding_rect().bottom - at[1], small.get_bounding_rect().bottom - joint[1], delta=1)
        feet.choose(size=99.0)
        self.assertEqual(feet.size, self.rules.sizes[1])

    def test_a_foot_shows_shorter_the_more_the_body_faces_the_screen(self) -> None:
        feet = Feet(self.rules, FootChoice(True))
        widths = []
        for yaw in (None, 45.0, 0.0):
            feet.turned(yaw)
            widths.append(feet.picture("foot_right", LEVEL, LONG, False, DETAIL)[0].get_bounding_rect().width)
        self.assertGreater(widths[0], widths[1])
        self.assertGreater(widths[1], widths[2])
        feet.turned(0.0)
        self.assertAlmostEqual(feet.shown, self.rules.front)
        feet.turned(90.0)
        self.assertAlmostEqual(feet.shown, 1.0)

    def test_seen_from_the_front_the_two_feet_point_out_to_either_side(self) -> None:
        feet = Feet(self.rules, FootChoice(True))
        facing = DOLL_FACINGS["right"]
        skeleton = Skeleton(self.plan, facing)
        skeleton.set_pose(self.plan.pose(facing))

        def ahead(name: str) -> float:
            """How much further a foot goes to the right of its ankle than to the left."""
            image, joint = feet.laid(name, skeleton.bones[name], skeleton.mirrored, DETAIL)
            box = image.get_bounding_rect()
            return (box.right - joint[0]) - (joint[0] - box.left)

        feet.turned(None)
        self.assertGreater(ahead("foot_right"), 10)
        self.assertGreater(ahead("foot_left"), 10)
        feet.turned(0.0)
        self.assertTrue(feet.splayed)
        self.assertLess(ahead("foot_right"), -5)
        self.assertGreater(ahead("foot_left"), 5)
        feet.turned(self.rules.splay_to + 10.0)
        self.assertFalse(feet.splayed)
        # The near one comes round by degrees, through pointing at whoever looks: from one
        # step of a turn to the next it is never far from where it was.
        before = None
        for step in range(0, 13):
            feet.turned(step * 7.5)
            now = ahead("foot_right")
            if before is not None:
                self.assertLess(abs(now - before), LONG * DETAIL * 0.45, step)
                self.assertGreaterEqual(now, before - 2, step)
            before = now
        # And from behind as from the front.
        feet.turned(180.0)
        self.assertTrue(feet.splayed)
        feet.turned(180.0 - self.rules.splay_to - 10.0)
        self.assertFalse(feet.splayed)

    def test_a_foot_stands_as_far_under_its_ankle_as_the_body_has_its_ankle_above_the_ground(self) -> None:
        feet = Feet(self.rules, FootChoice(True, line=0.0))
        for high in (1.2, 1.5, 2.0):
            feet.stands = high
            image, joint = feet.picture("foot_right", LEVEL, LONG, False, DETAIL)
            self.assertAlmostEqual(image.get_bounding_rect().bottom - joint[1], high * DETAIL, delta=1.5, msg=high)

    def test_the_shaft_of_a_foot_is_as_wide_as_the_leg_it_is_joined_to(self) -> None:
        feet = Feet(self.rules, FootChoice(True, line=0.0))

        def above_the_ankle() -> int:
            image, joint = feet.picture("foot_right", LEVEL, LONG, False, DETAIL)
            row = round(joint[1] - LONG * DETAIL * 0.08)
            return sum(1 for x in range(image.get_width()) if image.get_at((x, row))[3] > 127)

        feet.joins = 0.3
        self.assertAlmostEqual(above_the_ankle(), 0.3 * DETAIL * 2 * 1.08, delta=3)
        feet.joins = 0.8
        self.assertAlmostEqual(above_the_ankle(), 0.8 * DETAIL * 2 * 1.08, delta=3)

    def test_the_line_round_a_foot_has_the_colour_and_the_thickness_picked_for_it(self) -> None:
        feet = Feet(self.rules, FootChoice(True, color=SKIN, line_color=RED))

        def reds() -> int:
            image, _ = feet.picture("foot_right", LEVEL, LONG, False, DETAIL)
            found = 0
            for x in range(image.get_width()):
                for y in range(image.get_height()):
                    r, g, b, solid = image.get_at((x, y))
                    found += solid > 200 and r > 150 and g < 80 and b < 80
            return found

        usual = reds()
        self.assertGreater(usual, 100)
        feet.choose(line=2.0)
        self.assertGreater(reds(), usual * 1.5)
        feet.choose(line=0.0)
        self.assertLess(reds(), 10)

    def test_the_foot_of_the_far_side_is_darker_and_takes_the_colour_picked(self) -> None:
        feet = Feet(self.rules, FootChoice(True, color=RED))
        near, joint = feet.picture("foot_right", LEVEL, LONG, False, DETAIL)
        far, _ = feet.picture("foot_left", LEVEL, LONG, False, DETAIL)
        spot = (round(joint[0] + LONG * DETAIL * 0.4), round(joint[1] + LONG * DETAIL * self.rules.sole * 0.6))
        for got, wanted in zip(tuple(near.get_at(spot))[:3], RED):
            self.assertAlmostEqual(got, wanted, delta=6)
        self.assertLess(sum(tuple(far.get_at(spot))[:3]), sum(tuple(near.get_at(spot))[:3]))

    def test_made_feet_and_hands_are_laid_on_a_doll_cut_without_them(self) -> None:
        hands = Hands(load_hand_rules(), HandChoice(True))
        feet = Feet(self.rules, FootChoice(True, color=RED))
        made = Made(hands, feet)
        self.assertEqual(set(made.bones), {"hand_left", "hand_right", "foot_left", "foot_right"})
        self.assertEqual(Made(hands, Feet(self.rules)).bones, hands.rules.bones)
        bare = Doll(self.template, {BODY_CANVAS: self.body}, self.plan, made.bones)
        self.assertNotIn("foot_right", bare.parts)
        self.assertEqual(bare.limbs["thigh_right"].bones, ("thigh_right", "shin_right"))
        facing = DOLL_FACINGS["right"]
        skeleton = Skeleton(self.plan, facing)
        skeleton.set_pose(self.plan.pose(facing))

        def reds(with_what: Made | None) -> int:
            picture = pygame.Surface((400, 400), pygame.SRCALPHA)
            draw_doll(picture, bare, self.plan, skeleton, (200, 380), 12.0, hands=with_what)
            return pygame.mask.from_threshold(picture, (*RED, 255), (12, 12, 12, 255)).count()

        self.assertEqual(reds(None), 0)
        self.assertEqual(reds(Made(hands)), 0)
        self.assertGreater(reds(made), 100)

    def test_what_is_said_of_feet_is_kept_and_read_back(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            store = FootStore(Path(folder), self.rules)
            self.assertFalse(store.get("somebody").choice.made)
            store.get("somebody").choose(made=True, color=RED, size=1.2)
            self.assertTrue(store.save("somebody"))
            again = FootStore(Path(folder), self.rules).get("somebody")
            self.assertEqual(again.choice, FootChoice(True, RED, 1.2))


if __name__ == "__main__":
    unittest.main()
