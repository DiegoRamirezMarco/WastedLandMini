import os
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame

from graphics.doll import BODY_CANVAS, DOLL_FACINGS, Doll, doll_plan, draw_doll, load_template
from graphics.foot import Feet, FootChoice, Made
from graphics.foot import load_rules as load_foot_rules
from graphics.hand import HandChoice, Hands
from graphics.hand import load_rules as load_hand_rules
from graphics.joined import colour_at, cut_short, half_width_at, joined
from graphics.mannequin import figures, tones_of
from skeleton.plan import builtin_plan
from skeleton.rig import Skeleton

SKIN = (214, 170, 130)
LINE = (30, 22, 20)
BLUE = (60, 90, 200)


def dark(surface: pygame.Surface, box: pygame.Rect) -> int:
    """How many pixels of a part of a picture are of a line: solid, and dark."""
    found = 0
    for x in range(box.left, box.right):
        for y in range(box.top, box.bottom):
            red, green, blue, solid = surface.get_at((x, y))
            found += solid > 200 and red + green + blue < 150
    return found


class JoinedTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        pygame.init()
        pygame.display.set_mode((1, 1))

    def made(self) -> tuple[pygame.Surface, pygame.Surface]:
        """A round thing with a line round it, and the same without."""
        lined = pygame.Surface((80, 80), pygame.SRCALPHA)
        pygame.draw.circle(lined, LINE, (40, 40), 30)
        pygame.draw.circle(lined, SKIN, (40, 40), 26)
        unlined = pygame.Surface((80, 80), pygame.SRCALPHA)
        pygame.draw.circle(unlined, SKIN, (40, 40), 26)
        return lined, unlined

    def test_its_line_is_gone_where_the_limb_comes_into_it_and_nowhere_else(self) -> None:
        lined, unlined = self.made()
        # A limb twenty wide that comes down into the top of it, and stops at its middle.
        limb = pygame.Surface((20, 60), pygame.SRCALPHA)
        limb.fill(BLUE)
        one = joined(lined, unlined, (100.0, 100.0), [(limb, 130.0, 80.0)], 4.0)
        top, foot = pygame.Rect(34, 8, 12, 8), pygame.Rect(34, 64, 12, 8)
        self.assertGreater(dark(lined, top), 30)
        self.assertEqual(dark(one, top), 0)
        self.assertEqual(dark(one, foot), dark(lined, foot))
        # To either side of where the limb comes in, its line is whole.
        for side in (pygame.Rect(8, 34, 8, 12), pygame.Rect(64, 34, 8, 12)):
            self.assertEqual(dark(one, side), dark(lined, side))
        # And nothing of it is anywhere it was not.
        self.assertEqual(pygame.mask.from_surface(one).count(), pygame.mask.from_surface(one).overlap_area(pygame.mask.from_surface(lined), (0, 0)))
        # The first picture is left as it was, to be joined to a limb somewhere else.
        self.assertGreater(dark(lined, top), 30)

    def test_its_line_stays_where_its_edge_runs_along_the_edge_of_the_limb(self) -> None:
        lined, unlined = self.made()
        # A limb as wide as the thing itself: its edge and the thing's are the one edge.
        limb = pygame.Surface((60, 60), pygame.SRCALPHA)
        limb.fill(BLUE)
        one = joined(lined, unlined, (100.0, 100.0), [(limb, 110.0, 80.0)], 4.0)
        for side in (pygame.Rect(8, 30, 6, 8), pygame.Rect(66, 30, 6, 8)):
            self.assertEqual(dark(one, side), dark(lined, side))
        self.assertEqual(dark(one, pygame.Rect(34, 8, 12, 8)), 0)

    def test_with_no_limb_under_it_it_is_as_it_was(self) -> None:
        lined, unlined = self.made()
        self.assertIs(joined(lined, unlined, (100.0, 100.0), []), lined)
        limb = pygame.Surface((20, 20), pygame.SRCALPHA)
        limb.fill(BLUE)
        self.assertIs(joined(lined, unlined, (100.0, 100.0), [(limb, 400.0, 400.0)]), lined)

    def test_the_colour_of_a_drawing_round_a_spot_is_told_with_its_lines_apart(self) -> None:
        drawing = pygame.Surface((40, 40), pygame.SRCALPHA)
        drawing.fill(BLUE, pygame.Rect(5, 5, 30, 30))
        pygame.draw.rect(drawing, LINE, pygame.Rect(5, 5, 30, 30), 4)
        self.assertEqual(colour_at(drawing, (20.0, 20.0), 12), BLUE)
        self.assertIsNone(colour_at(drawing, (6.0, 6.0), 1))
        self.assertIsNone(colour_at(pygame.Surface((40, 40), pygame.SRCALPHA), (20.0, 20.0), 12))

    def test_a_made_hand_and_a_made_foot_have_no_line_across_the_limb_they_are_on(self) -> None:
        template = load_template()
        build = template.starting()
        template = template.built(build)
        plan = doll_plan(builtin_plan(), template, build)
        body = figures(template, tones_of(SKIN, LINE), 5)[BODY_CANVAS]
        made = Made(Hands(load_hand_rules(), HandChoice(True, color=SKIN)), Feet(load_foot_rules(), FootChoice(True, color=SKIN)))
        bare = Doll(template, {BODY_CANVAS: body}, plan, made.bones)
        facing = DOLL_FACINGS["right"]
        skeleton = Skeleton(plan, facing)
        skeleton.set_pose(plan.pose(facing))
        detail = 24.0
        picture = pygame.Surface((700, 900), pygame.SRCALPHA)
        draw_doll(picture, bare, plan, skeleton, (350, 860), detail, hands=made)
        for name in ("hand_right", "foot_right"):
            bone = skeleton.bones[name]
            joint = (round(350 + (bone.a.x + 0.5) * detail), round(860 + (bone.a.y + 0.5) * detail))
            # Round where the two meet, in the middle of the limb, there is skin and no line.
            for across in range(-3, 4):
                for down in range(-3, 4):
                    got = tuple(picture.get_at((joint[0] + across, joint[1] + down)))
                    self.assertGreater(sum(got[:3]), 300, (name, across, down, got))
            # Its line is there for all that, wherever it is not over the limb.
            lined, where = made.laid(name, bone, skeleton.mirrored, detail)
            self.assertGreater(dark(lined, lined.get_rect()), 200, name)


    def test_how_wide_a_limb_is_where_it_ends_is_told_from_its_drawing(self) -> None:
        limb = pygame.Surface((60, 120), pygame.SRCALPHA)
        pygame.draw.rect(limb, BLUE, pygame.Rect(20, 0, 20, 120))
        self.assertAlmostEqual(half_width_at(limb, (30.0, 10.0), (30.0, 100.0)), 10.0, delta=1.0)
        self.assertEqual(half_width_at(pygame.Surface((60, 120), pygame.SRCALPHA), (30.0, 10.0), (30.0, 100.0)), 0.0)

    def test_a_limb_cut_short_has_nothing_of_what_was_drawn_on_the_end_of_it(self) -> None:
        # A leg twenty wide, with a foot drawn on the end of it: out to one side, from a
        # little above the ankle down.
        limb = pygame.Surface((90, 140), pygame.SRCALPHA)
        pygame.draw.rect(limb, BLUE, pygame.Rect(20, 0, 20, 110))
        pygame.draw.rect(limb, BLUE, pygame.Rect(20, 92, 60, 40))
        short = cut_short(limb, (30.0, 10.0), (30.0, 100.0), 2.0)
        box = short.get_bounding_rect()
        # No wider than a leg, and a round end no further past the ankle than the leg is wide.
        self.assertLess(box.width, 28)
        self.assertLess(box.bottom, 100 + 14)
        self.assertGreater(box.bottom, 100 + 6)
        # The leg itself is as it was, well above the ankle.
        for y in (5, 40, 60):
            self.assertEqual(tuple(short.get_at((30, y))), tuple(limb.get_at((30, y))))
            self.assertEqual(tuple(short.get_at((22, y))), tuple(limb.get_at((22, y))))
        self.assertEqual(limb.get_bounding_rect().width, 60)

    def test_a_doll_cut_without_a_hand_or_a_foot_has_no_more_of_them_than_a_round_end(self) -> None:
        template = load_template()
        build = template.starting()
        template = template.built(build)
        plan = doll_plan(builtin_plan(), template, build)
        body = figures(template, tones_of(SKIN, LINE), 5)[BODY_CANVAS]
        whole = Doll(template, {BODY_CANVAS: body}, plan)
        bare = Doll(template, {BODY_CANVAS: body}, plan, ("hand_right", "foot_right"))
        for bone in ("forearm_right", "shin_right"):
            part = bare.parts[bone]
            wide = half_width_at(whole.parts[bone].image, whole.parts[bone].start, whole.parts[bone].end, 0.38)
            box = part.image.get_bounding_rect()
            self.assertLess(box.bottom, part.end[1] + wide * 1.2 + 2, bone)
            limb = bare.limbs[bone]
            self.assertLess(limb.image.get_bounding_rect().bottom, limb.joints[-1][1] + wide * 1.2 + 2, bone)
        # The other side, which has its hand and its foot, is as it was drawn.
        self.assertEqual(bare.limbs["forearm_left"].image.get_size(), whole.limbs["forearm_left"].image.get_size())


if __name__ == "__main__":
    unittest.main()
