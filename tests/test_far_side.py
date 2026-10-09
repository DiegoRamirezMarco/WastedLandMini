import os
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame

from graphics.doll import BODY_CANVAS, Doll, load_template
from graphics.mannequin import figures, tones_of
from graphics.sides import SHADE, limbs, match_far_side

SKIN = (214, 170, 130)
GREEN = (40, 200, 60, 255)
BLUE = (40, 60, 200, 255)


def count(surface: pygame.Surface, color: tuple[int, ...]) -> int:
    return pygame.mask.from_threshold(surface, color, (1, 1, 1, 255)).count()


class SidesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        pygame.init()
        pygame.display.set_mode((1, 1))
        template = load_template()
        cls.template = template.built(template.starting())
        cls.plain = figures(cls.template, tones_of(SKIN, (30, 22, 20)), 5)[BODY_CANVAS]

    def middle(self, bone: str) -> tuple[int, int]:
        spec = self.template.parts[bone]
        return (round((spec.start[0] + spec.end[0]) / 2), round((spec.start[1] + spec.end[1]) / 2))

    def test_an_arm_and_a_leg_each_have_one_like_them_on_the_far_side(self) -> None:
        pairs = dict(limbs(self.template, BODY_CANVAS))
        self.assertEqual(
            pairs,
            {
                ("upper_arm_right", "forearm_right", "hand_right"): ("upper_arm_left", "forearm_left", "hand_left"),
                ("thigh_right", "shin_right", "foot_right"): ("thigh_left", "shin_left", "foot_left"),
            },
        )

    def test_what_is_drawn_for_the_near_side_is_put_on_the_far_side(self) -> None:
        drawing = self.plain.copy()
        pygame.draw.circle(drawing, GREEN, self.middle("forearm_right"), 6)
        pygame.draw.circle(drawing, BLUE, self.middle("shin_left"), 6)
        near_before = count(drawing, GREEN)
        self.assertTrue(match_far_side(self.template, BODY_CANVAS, drawing))
        # The mark on the near arm is on both arms now, and what was on the far leg is gone.
        self.assertEqual(count(drawing, GREEN), near_before * 2)
        self.assertEqual(tuple(drawing.get_at(self.middle("forearm_left"))), GREEN)
        self.assertEqual(count(drawing, BLUE), 0)
        # Done again, there is nothing left to do.
        self.assertFalse(match_far_side(self.template, BODY_CANVAS, drawing))

    def test_the_two_sides_are_cut_into_the_same_parts(self) -> None:
        drawing = self.plain.copy()
        pygame.draw.circle(drawing, GREEN, self.middle("thigh_right"), 8)
        match_far_side(self.template, BODY_CANVAS, drawing)
        doll = Doll(self.template, {BODY_CANVAS: drawing})
        for part in ("upper_arm", "forearm", "hand", "thigh", "shin", "foot"):
            near, far = doll.parts[f"{part}_right"].image, doll.parts[f"{part}_left"].image
            # The far side is a whole number of pixels off, and its zones are not: a part may be
            # cut a row or two sooner or later, and no more.
            self.assertAlmostEqual(near.get_width(), far.get_width(), delta=3, msg=part)
            self.assertAlmostEqual(near.get_height(), far.get_height(), delta=3, msg=part)
            solid = pygame.mask.from_surface(near).count()
            self.assertAlmostEqual(pygame.mask.from_surface(far).count(), solid, delta=solid * 0.06, msg=part)

    def test_the_trunk_and_the_near_side_are_left_as_they_were(self) -> None:
        drawing = self.plain.copy()
        match_far_side(self.template, BODY_CANVAS, drawing, SHADE)
        for part in ("spine", "hips", "upper_arm_right", "foot_right"):
            before = Doll(self.template, {BODY_CANVAS: self.plain}).parts[part].image
            after = Doll(self.template, {BODY_CANVAS: drawing}).parts[part].image
            # As they are seen: what is clear has no colour to be the same or not.
            seen = []
            for image in (before, after):
                on_white = pygame.Surface(image.get_size())
                on_white.fill((255, 255, 255))
                on_white.blit(image, (0, 0))
                seen.append(pygame.image.tobytes(on_white, "RGB"))
            self.assertEqual(seen[0], seen[1], part)

    def test_a_limb_goes_over_whole_past_where_it_meets_the_trunk(self) -> None:
        drawing = self.plain.copy()
        # A mark at the very top of the near arm, above its shoulder.
        top = self.template.parts["upper_arm_right"].start
        above = (round(top[0]), round(top[1]) - 10)
        self.assertTrue(drawing.get_at(above)[3], "the plain arm does not reach above its shoulder")
        drawing.set_at(above, GREEN)
        match_far_side(self.template, BODY_CANVAS, drawing)
        # It is there twice now: where it was put, and as far off as the other arm is, to a pixel.
        self.assertEqual(count(drawing, GREEN), 2)
        far = self.template.parts["upper_arm_left"].start
        there = pygame.Rect(0, 0, 3, 3)
        there.center = (round(far[0]), round(far[1]) - 10)
        self.assertEqual(count(drawing.subsurface(there), GREEN), 1)

    def test_the_far_side_can_be_made_darker(self) -> None:
        same, darker = self.plain.copy(), self.plain.copy()
        match_far_side(self.template, BODY_CANVAS, same)
        match_far_side(self.template, BODY_CANVAS, darker, SHADE)
        spot = self.middle("thigh_left")
        self.assertEqual(tuple(same.get_at(spot)), tuple(same.get_at(self.middle("thigh_right"))))
        self.assertLess(sum(tuple(darker.get_at(spot))[:3]), sum(tuple(same.get_at(spot))[:3]))
        self.assertEqual(darker.get_at(spot)[3], 255)


    def test_the_far_side_is_put_in_the_shade_by_whoever_shows_the_doll(self) -> None:
        from graphics.sides import far_darker

        doll = Doll(self.template, {BODY_CANVAS: self.plain})
        self.assertIs(far_darker(doll, 0.0), doll)
        dark = far_darker(doll, 0.2)

        def light(image: pygame.Surface) -> int:
            box = image.get_bounding_rect()
            return sum(tuple(image.get_at(box.center))[:3])

        for bone in ("upper_arm_left", "thigh_left"):
            self.assertLess(light(dark.parts[bone].image), light(doll.parts[bone].image), bone)
            # Its limb of rubber is the limb it was, told how dark it is: it is bent once,
            # in the shade or out of it, and darkened after.
            self.assertIs(dark.limbs[bone].image, doll.limbs[bone].image)
            self.assertEqual(dark.limbs[bone].mark, doll.limbs[bone].mark)
            self.assertEqual((dark.limbs[bone].shade, doll.limbs[bone].shade), (20, 0))
        for bone in ("upper_arm_right", "thigh_right", "spine"):
            self.assertIs(dark.parts[bone], doll.parts[bone], bone)
        # The doll it was made from is as it was.
        self.assertEqual(light(doll.parts["upper_arm_left"].image), light(Doll(self.template, {BODY_CANVAS: self.plain}).parts["upper_arm_left"].image))


if __name__ == "__main__":
    unittest.main()
