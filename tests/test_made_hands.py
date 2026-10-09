import os
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame

from graphics.doll import BODY_CANVAS, DOLL_FACINGS, Doll, doll_plan, draw_doll, load_template
from graphics.hand import HandChoice, HandPose, Hands, HandStore, choice_from_data, load_rules
from graphics.mannequin import figures, tones_of
from skeleton.plan import builtin_plan
from skeleton.rig import Skeleton

SKIN = (214, 170, 130)
RED = (200, 30, 30)


def painted(surface: pygame.Surface) -> int:
    return pygame.mask.from_surface(surface).count()


class HandTests(unittest.TestCase):
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

    def test_every_clip_has_a_way_of_holding_a_hand_and_the_rest_are_at_rest(self) -> None:
        rules = self.rules
        self.assertEqual(rules.pose_for("fight"), rules.poses["fist"])
        self.assertEqual(rules.pose_for("a clip nobody wrote"), rules.poses[rules.at_rest])
        self.assertEqual(rules.pose_for(None), rules.poses[rules.at_rest])

    def test_a_hand_is_less_shut_on_something_thicker(self) -> None:
        low, high = self.rules.held_thick
        thin, thick = self.rules.holding(low), self.rules.holding(high)
        self.assertGreater(thin.curl, thick.curl)
        self.assertEqual(self.rules.holding(high * 3), thick)

    def test_an_open_hand_reaches_further_than_a_fist(self) -> None:
        hands = Hands(self.rules, HandChoice(True))
        open_hand, _ = hands.picture("hand_right", 0.0, 1.6, False, 40.0, self.rules.poses["open"])
        fist, _ = hands.picture("hand_right", 0.0, 1.6, False, 40.0, self.rules.poses["fist"])
        self.assertGreater(open_hand.get_bounding_rect().height, fist.get_bounding_rect().height)

    def test_there_is_one_line_round_a_hand_and_none_where_a_finger_begins(self) -> None:
        hands = Hands(self.rules, HandChoice(True, color=SKIN))
        long = 1.6 * hands.size * 40.0
        for count in range(self.rules.finger_counts[0], self.rules.finger_counts[1] + 1):
            hands.choose(fingers=count)
            image, joint = hands.picture("hand_right", 0.0, 1.6, False, 40.0, HandPose(0.0, 0.0))
            # From the middle of the palm out along each finger, held straight, there is skin all the way.
            foot = self.rules.palm_from + self.rules.palm_long
            for index in range(count):
                x = round(joint[0] + (index - (count - 1) / 2) * self.rules.palm_wide / count * long)
                for step in range(20):
                    down = self.rules.palm_at + (foot + self.rules.finger_long * 0.4 - self.rules.palm_at) * step / 19
                    got = tuple(image.get_at((x, round(joint[1] + down * long))))
                    self.assertGreater(got[3], 245, (count, index, step))
                    for channel, wanted in zip(got[:3], SKIN):
                        self.assertAlmostEqual(channel, wanted, delta=6, msg=(count, index, step))

    def test_the_thumb_is_on_the_side_the_body_faces(self) -> None:
        hands = Hands(self.rules, HandChoice(True))
        def beyond(mirrored: bool) -> tuple[int, int]:
            """How far the hand reaches to the right of its wrist, and how far to the left."""
            image, joint = hands.picture("hand_right", 0.0, 1.6, mirrored, 40.0, self.rules.poses["open"])
            box, middle = image.get_bounding_rect(), round(joint[0])
            return box.right - middle, middle - box.left

        # The fingers fan to both sides alike: what reaches further one way is the thumb.
        ahead, behind = beyond(False)
        self.assertGreater(ahead, behind + 10)
        ahead, behind = beyond(True)
        self.assertGreater(behind, ahead + 10)

    def test_a_fist_has_its_fingers_and_its_thumb_over_the_palm(self) -> None:
        hands = Hands(self.rules, HandChoice(True))
        long = 1.6 * hands.size * 40.0
        # No wider than the palm and the line round it.
        half = round(long * (self.rules.palm_wide / 2 + self.rules.line)) + 3
        image, joint = hands.picture("hand_right", 0.0, 1.6, False, 40.0, self.rules.poses["fist"])
        box = image.get_bounding_rect()
        self.assertLess(box.right - round(joint[0]), half)
        self.assertLess(round(joint[0]) - box.left, half)
        # And lines inside it that an open hand has not: where each of them lies on the rest.
        open_hand, _ = hands.picture("hand_right", 0.0, 1.6, False, 40.0, self.rules.poses["open"])

        def lines_inside(picture: pygame.Surface) -> float:
            dark = pygame.mask.from_threshold(picture, (26, 20, 18, 255), (40, 40, 40, 255)).count()
            return dark / max(1, painted(picture))

        self.assertGreater(lines_inside(image), lines_inside(open_hand))

    def test_what_is_held_is_under_the_fingers_whatever_its_thickness(self) -> None:
        hands = Hands(self.rules, HandChoice(True, color=SKIN))
        wood = (120, 86, 52)
        long = 1.6 * hands.size * 40.0
        for thick in self.rules.held_thick:
            image, joint = hands.picture("hand_right", 0.0, 1.6, False, 40.0, self.rules.holding(thick), (thick, wood))
            woods = pygame.mask.from_threshold(image, (*wood, 255), (10, 10, 10, 255))
            # It shows to either side of the hand, and not across the middle of it.
            self.assertGreater(woods.count(), 20, thick)
            box = woods.get_bounding_rects()
            left = min(each.left for each in box)
            right = max(each.right for each in box)
            self.assertLess(left, joint[0] - long * self.rules.palm_wide)
            self.assertGreater(right, joint[0] + long * self.rules.palm_wide)
            row = round(sum(each.centery * each.width * each.height for each in box) / sum(each.width * each.height for each in box))
            for x in range(round(joint[0] - long * 0.2), round(joint[0] + long * 0.2)):
                self.assertFalse(woods.get_at((x, row)), (thick, x))

    def test_a_hand_hangs_from_its_wrist_whichever_way_it_runs(self) -> None:
        hands = Hands(self.rules, HandChoice(True))
        down, joint = hands.picture("hand_right", 0.0, 1.6, False, 40.0, self.rules.poses["open"])
        box = down.get_bounding_rect()
        # Straight down it is all but wholly below the wrist, and turned half round, above it.
        self.assertGreater(box.bottom - joint[1], (joint[1] - box.top) * 2)
        up, joint = hands.picture("hand_right", 3.14159, 1.6, False, 40.0, self.rules.poses["open"])
        box = up.get_bounding_rect()
        self.assertGreater(joint[1] - box.top, (box.bottom - joint[1]) * 2)

    def test_what_is_said_of_hands_changes_them(self) -> None:
        hands = Hands(self.rules, HandChoice(True))
        before, _ = hands.picture("hand_right", 0.0, 1.6, False, 40.0)
        hands.choose(color=RED, size=hands.size * 1.5, fingers=4)
        after, joint = hands.picture("hand_right", 0.0, 1.6, False, 40.0)
        self.assertGreater(after.get_bounding_rect().height, before.get_bounding_rect().height)
        palm = (round(joint[0]), round(joint[1] + 1.6 * hands.size * 40.0 * self.rules.palm_at))
        # Made finer and brought down smoothly, a colour comes out a shade off.
        for got, wanted in zip(tuple(after.get_at(palm))[:3], RED):
            self.assertAlmostEqual(got, wanted, delta=6)
        self.assertEqual(hands.fingers, 4)
        # No more fingers, and no larger, than a hand can be made with.
        hands.choose(fingers=40, size=99.0)
        self.assertEqual(hands.fingers, self.rules.finger_counts[1])
        self.assertEqual(hands.size, self.rules.sizes[1])

    def test_the_hand_of_the_far_side_is_darker(self) -> None:
        hands = Hands(self.rules, HandChoice(True, color=SKIN))
        near, joint = hands.picture("hand_right", 0.0, 1.6, False, 40.0)
        far, _ = hands.picture("hand_left", 0.0, 1.6, False, 40.0)
        palm = (round(joint[0]), round(joint[1] + 1.6 * hands.size * 40.0 * self.rules.palm_at))
        self.assertLess(sum(tuple(far.get_at(palm))[:3]), sum(tuple(near.get_at(palm))[:3]))

    def test_the_hand_of_the_far_side_is_the_other_hand_once_the_body_is_turned(self) -> None:
        hands = Hands(self.rules, HandChoice(True))
        # Open, so that the thumb tells one hand from the other: a fist is all but the same both ways.
        pose = self.rules.poses["open"]

        def both() -> tuple[pygame.Surface, pygame.Surface]:
            return tuple(hands.picture(name, 0.0, 1.6, False, 40.0, pose)[0] for name in ("hand_right", "hand_left"))

        def same(one: pygame.Surface, other: pygame.Surface) -> bool:
            return pygame.image.tobytes(one, "RGBA") == pygame.image.tobytes(other, "RGBA")

        near_side, far_side = both()
        # Left to itself, the far one has its thumb where the near one has.
        self.assertEqual(
            pygame.mask.from_surface(near_side).get_bounding_rects()[0], pygame.mask.from_surface(far_side).get_bounding_rects()[0]
        )
        # On a body it is the other hand however the body is turned, from its side too: it
        # does not change over as the body turns.
        for yaw in (0.0, 45.0, 90.0, 135.0, 180.0):
            hands.turned(yaw)
            self.assertTrue(hands.far_other, yaw)
        hands.turned(45.0)
        near_turned, far_turned = both()
        self.assertTrue(same(near_turned, near_side))
        self.assertFalse(same(far_turned, far_side))
        # It is that hand in a mirror, to within a pixel of how each was drawn.
        turned = pygame.mask.from_surface(far_turned)
        in_a_mirror = pygame.mask.from_surface(pygame.transform.flip(far_side, True, False))
        self.assertGreater(turned.overlap_area(in_a_mirror, (0, 0)), turned.count() * 0.97)
        self.assertLess(turned.overlap_area(pygame.mask.from_surface(far_side), (0, 0)), turned.count() * 0.97)
        hands.turned(None)
        self.assertTrue(same(both()[1], far_side))

    def test_the_near_hand_is_seen_from_its_back_and_shuts_behind_its_palm(self) -> None:
        hands = Hands(self.rules, HandChoice(True, color=SKIN))

        def lines(name: str, pose_id: str, **said: bool) -> int:
            """How much line there is to a hand: round it, between its fingers and on it."""
            image, _ = hands.picture(name, 0.0, 1.6, False, 40.0, self.rules.poses[pose_id], **said)
            return pygame.mask.from_threshold(image, (26, 20, 18, 255), (50, 50, 50, 255)).count()

        # Open, its back has the lines of a glove, which a palm has not: the rest is the same.
        self.assertGreater(lines("hand_right", "open"), lines("hand_right", "open", back=False) + 20)
        # Shut, a palm has its fingers and its thumb folded over it: a back has neither.
        self.assertGreater(lines("hand_right", "fist", back=False), lines("hand_right", "fist") + 100)
        # The far hand is seen from its palm, its fingers shut where they can be seen,
        # however the body is turned: and the near one from its back.
        for yaw in (None, 45.0, 0.0):
            hands.turned(yaw)
            self.assertEqual(lines("hand_left", "fist"), lines("hand_left", "fist", back=False), yaw)
            self.assertEqual(lines("hand_right", "fist"), lines("hand_right", "fist", back=True), yaw)
            self.assertGreater(lines("hand_left", "fist"), lines("hand_right", "fist") + 100, yaw)

    def test_the_line_round_a_hand_has_the_colour_and_the_thickness_picked_for_it(self) -> None:
        hands = Hands(self.rules, HandChoice(True, color=SKIN))

        def seen() -> tuple[pygame.Surface, int, int]:
            image, _ = hands.picture("hand_left", 0.0, 1.6, False, 40.0, self.rules.poses["open"])
            dark = red = 0
            for x in range(image.get_width()):
                for y in range(image.get_height()):
                    r, g, b, solid = image.get_at((x, y))
                    if solid > 200:
                        dark += r + g + b < 150
                        red += r > 150 and g < 80 and b < 80
            return image, dark, red

        usual, dark, red = seen()
        self.assertGreater(dark, 200)
        self.assertEqual(red, 0)
        hands.choose(line_color=RED)
        _, dark, red = seen()
        self.assertGreater(red, 200)
        self.assertLess(dark, 20)
        hands.choose(line=2.0)
        thicker, _, more = seen()
        self.assertGreater(more, red * 1.5)
        self.assertGreater(thicker.get_bounding_rect().width, usual.get_bounding_rect().width)
        # With none, it is what is inside the line and no more: and no thicker or thinner than can be.
        hands.choose(line=0.0)
        bare, dark, red = seen()
        self.assertLess(red, 20)
        self.assertLess(bare.get_bounding_rect().width, usual.get_bounding_rect().width)
        hands.choose(line=99.0)
        self.assertEqual(hands.bold, self.rules.lines[1])
        again = choice_from_data(hands.choice.to_data())
        self.assertEqual((again.line_color, again.line), (RED, 99.0))

    def test_a_hand_begins_as_wide_as_the_arm_it_is_joined_to(self) -> None:
        hands = Hands(self.rules, HandChoice(True, color=SKIN, line=0.0))

        def across_the_wrist() -> int:
            """How wide the hand is at its wrist."""
            image, joint = hands.picture("hand_right", 0.0, 1.6, False, 40.0, self.rules.poses["open"])
            row = round(joint[1])
            return sum(1 for x in range(image.get_width()) if image.get_at((x, row))[3] > 127)

        usual = across_the_wrist()
        hands.joins = 0.3
        thin = across_the_wrist()
        hands.joins = 0.6
        thick = across_the_wrist()
        self.assertLess(thin, usual)
        self.assertLess(thin, thick)
        # An arm 0.3 to either side is 24 pixels across here: the hand is that and a little
        # over where it begins, and has widened a little by the wrist.
        self.assertGreater(thin, 0.3 * 40.0 * 2)
        self.assertLess(thin, 0.3 * 40.0 * 2 * 1.9)

    def test_a_hand_takes_time_to_shut(self) -> None:
        hands = Hands(self.rules, HandChoice(True))
        hands.settle(self.rules.poses["open"])
        hands.settle(self.rules.poses["fist"], 0.02)
        partly = hands.held("hand_right").curl
        self.assertTrue(0.0 < partly < 1.0)
        hands.settle(self.rules.poses["fist"], 5.0)
        self.assertEqual(hands.held("hand_right").curl, 1.0)

    def test_a_doll_cut_without_its_hands_has_arms_that_end_at_the_wrist(self) -> None:
        whole = Doll(self.template, {BODY_CANVAS: self.body}, self.plan)
        bare = Doll(self.template, {BODY_CANVAS: self.body}, self.plan, self.rules.bones)
        self.assertIn("hand_right", whole.parts)
        self.assertNotIn("hand_right", bare.parts)
        self.assertEqual(bare.limbs["upper_arm_right"].bones, ("upper_arm_right", "forearm_right"))
        self.assertFalse(bare.limbs["upper_arm_right"].tipped)

    def test_made_hands_are_laid_on_a_doll_only_where_they_are_wanted(self) -> None:
        bare = Doll(self.template, {BODY_CANVAS: self.body}, self.plan, self.rules.bones)
        facing = DOLL_FACINGS["right"]
        skeleton = Skeleton(self.plan, facing)
        skeleton.set_pose(self.plan.pose(facing))

        def shown(hands: Hands | None) -> pygame.Surface:
            picture = pygame.Surface((400, 400), pygame.SRCALPHA)
            draw_doll(picture, bare, self.plan, skeleton, (200, 380), 12.0, hands=hands)
            return picture

        without = shown(None)
        self.assertEqual(painted(shown(Hands(self.rules, HandChoice(False)))), painted(without))
        with_hands = shown(Hands(self.rules, HandChoice(True, color=RED)))
        self.assertGreater(painted(with_hands), painted(without))
        reds = pygame.mask.from_threshold(with_hands, (*RED, 255), (12, 12, 12, 255)).count()
        self.assertGreater(reds, 20)

    def test_what_is_said_of_hands_is_kept_and_read_back(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            store = HandStore(Path(folder), self.rules)
            self.assertFalse(store.get("somebody").choice.made)
            store.get("somebody").choose(made=True, color=RED, size=1.4, fingers=4)
            self.assertTrue(store.save("somebody"))
            again = HandStore(Path(folder), self.rules).get("somebody")
            self.assertEqual(again.choice, HandChoice(True, RED, 1.4, 4))


if __name__ == "__main__":
    unittest.main()
