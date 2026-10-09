import json
import os
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame

from graphics.doll import BODY_CANVAS, DOLL_FACINGS, HEAD_CANVAS, DollStore, build_path, doll_path, load_template
from graphics.figure import BACK_DRAWING, DEPTH_KEY, FAR_KEY, FRONT_DRAWN, SIDE_DRAWN, TRUNK_KEY, Figures
from graphics.illustrations import Illustrations
from graphics.mannequin import figures, tones_of
from graphics.volume import fronted
from skeleton.plan import builtin_plan
from skeleton.rig import Skeleton

SKIN = (214, 170, 130)
LINE = (30, 22, 20)
RED = (200, 30, 30)
GREEN = (40, 200, 60, 255)


def greens(image: pygame.Surface) -> int:
    return sum(
        1 for x in range(image.get_width()) for y in range(image.get_height())
        if image.get_at((x, y))[3] > 100 and image.get_at((x, y))[1] > image.get_at((x, y))[0] + 25
    )


class FiguresTests(unittest.TestCase):
    def setUp(self) -> None:
        pygame.init()
        pygame.display.set_mode((1, 1))
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.base = load_template()
        self.template = self.base.built(self.base.starting())
        self.plain = figures(self.template, tones_of(SKIN, LINE), 5)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def keep(self, body_id: str, drawings: dict[str, pygame.Surface], **extras) -> None:
        for canvas, drawing in drawings.items():
            path = self.root / doll_path(body_id, canvas)
            path.parent.mkdir(parents=True, exist_ok=True)
            pygame.image.save(drawing, str(path))
        measures = self.root / build_path(body_id)
        measures.write_text(json.dumps({**self.base.starting().to_data(), **extras}), encoding="utf-8")

    def cast(self) -> Figures:
        dolls = DollStore(Illustrations(self.root), self.base, builtin_plan())
        return Figures(dolls, self.root)

    def width(self, doll, bone: str = "spine") -> int:
        return doll.parts[bone].image.get_bounding_rect().width

    def test_a_body_drawn_before_there_was_turning_is_its_drawing_from_its_side(self) -> None:
        self.keep("old", self.plain)
        cast = self.cast()
        self.assertEqual(cast.said("old").drawn, SIDE_DRAWN)
        doll = cast.dolls.get("old")
        side = cast.shown("old", doll)
        self.assertIs(side.doll, doll)
        self.assertEqual(side.yaw, cast.side)
        self.assertIsNone(side.made)
        # Seen from the front its trunk is made into one seen from the front: wider, and the
        # same to either side of its middle. Nobody has drawn it again.
        cast.new_frame()
        front = cast.shown("old", doll, 0.0)
        self.assertIsNot(front.doll, doll)
        self.assertGreater(self.width(front.doll), self.width(doll) * 1.3)
        part = front.doll.parts["spine"]
        box = part.image.get_bounding_rect()
        self.assertAlmostEqual(part.start[0] - box.left, box.right - part.start[0], delta=3)
        # Its limbs are the ones it was cut with, and its drawing on disk is as it was.
        self.assertIs(front.doll.limbs["thigh_right"].image, cast._again(doll, True, (), cast.said("old").depth).limbs["thigh_right"].image)
        kept = pygame.image.load(str(self.root / doll_path("old", BODY_CANVAS)))
        self.assertEqual(pygame.image.tobytes(kept, "RGBA"), pygame.image.tobytes(self.plain[BODY_CANVAS], "RGBA"))
        # And from behind it is as wide as from the front.
        cast.new_frame()
        self.assertAlmostEqual(self.width(cast.shown("old", doll, 180.0).doll), self.width(front.doll), delta=2)

    def test_a_body_drawn_from_the_front_is_wrapped_round_from_its_side_too(self) -> None:
        turn = self.cast().rules.body
        drawn = dict(self.plain)
        drawn[BODY_CANVAS] = fronted(self.template, self.plain[BODY_CANVAS], turn.trunk, 0.5)
        self.keep("new", drawn, **{TRUNK_KEY: FRONT_DRAWN, DEPTH_KEY: 0.5, FAR_KEY: "darker"})
        cast = self.cast()
        said = cast.said("new")
        self.assertEqual((said.drawn, said.depth, said.far_side), (FRONT_DRAWN, 0.5, "darker"))
        doll = cast.dolls.get("new")
        front = cast.shown("new", doll, 0.0)
        self.assertEqual(self.width(front.doll), self.width(doll))
        cast.new_frame()
        side = cast.shown("new", doll)
        self.assertIsNot(side.doll, doll)
        self.assertAlmostEqual(self.width(side.doll), self.width(doll) * 0.5, delta=4)
        # Its far side is in the shade seen from its side, and out of it seen from the front.
        self.assertEqual((side.doll.limbs["thigh_left"].shade > 0, front.doll.limbs["thigh_left"].shade), (True, 0))

    def test_the_back_of_a_trunk_that_was_drawn_is_what_is_seen_from_behind(self) -> None:
        turn = self.cast().rules.body
        drawn = dict(self.plain)
        drawn[BODY_CANVAS] = fronted(self.template, self.plain[BODY_CANVAS], turn.trunk, turn.depth)
        back = pygame.Surface(drawn[BODY_CANVAS].get_size(), pygame.SRCALPHA)
        spec = self.template.parts["spine"]
        pygame.draw.circle(back, GREEN, (round(spec.start[0]), round((spec.start[1] + spec.end[1]) / 2)), 6)
        self.keep("new", {**drawn, BACK_DRAWING: back}, **{TRUNK_KEY: FRONT_DRAWN})
        cast = self.cast()
        doll = cast.dolls.get("new")
        self.assertEqual(greens(cast.shown("new", doll, 0.0).doll.parts["spine"].image), 0)
        cast.new_frame()
        self.assertGreater(greens(cast.shown("new", doll, 180.0).doll.parts["spine"].image), 40)

    def test_hands_and_feet_that_are_made_are_laid_on_a_body_cut_without_them(self) -> None:
        self.keep("old", self.plain)
        cast = self.cast()
        cast.hands.get("old").choose(made=True, color=RED)
        cast.feet.get("old").choose(made=True, color=RED)
        doll = cast.dolls.get("old")
        self.assertIn("hand_right", doll.parts)
        shown = cast.shown("old", doll)
        self.assertNotIn("hand_right", shown.doll.parts)
        self.assertNotIn("foot_left", shown.doll.parts)
        self.assertEqual(set(shown.made.bones), {"hand_left", "hand_right", "foot_left", "foot_right"})
        # They are told how wide the limb each is on is, and how high the ankles stand.
        self.assertGreater(cast.hands.get("old").joins, 0.0)
        self.assertAlmostEqual(cast.feet.get("old").stands, 1.5, delta=0.3)
        plan = doll.plan
        facing = DOLL_FACINGS["right"]
        skeleton = Skeleton(plan, facing)
        skeleton.set_pose(cast.posed(shown, plan.pose(facing), facing))
        picture = pygame.Surface((400, 440), pygame.SRCALPHA)
        cast.draw(picture, shown, plan, skeleton, (200, 420), 12.0)
        self.assertGreater(pygame.mask.from_threshold(picture, (*RED, 255), (12, 12, 12, 255)).count(), 150)
        # The same body with what it wears on is cut without them all the same.
        again = cast.dolls.tailor.dress(shown.doll, [])
        self.assertEqual(again.without, shown.doll.without)
        self.assertNotIn("hand_right", again.parts)

    def test_only_so_many_bodies_are_turned_anew_in_a_frame(self) -> None:
        self.keep("old", self.plain)
        cast = self.cast()
        doll = cast.dolls.get("old")
        front = cast.shown("old", doll, 0.0)
        cast.new_frame()
        quarter = cast.shown("old", doll, 45.0)
        self.assertIsNot(quarter.doll, front.doll)
        # No more in this frame: it is shown the nearest way it has been turned.
        self.assertIs(cast.shown("old", doll, 30.0).doll, quarter.doll)
        cast.new_frame()
        self.assertIsNot(cast.shown("old", doll, 30.0).doll, quarter.doll)
        # What it was turned to is kept from one frame to the next.
        cast.new_frame()
        self.assertIs(cast.shown("old", doll, 0.0).doll, front.doll)

    def test_a_body_whose_trunk_has_yet_to_be_made_waits_its_turn_seen_from_its_side(self) -> None:
        for name in ("one", "other"):
            self.keep(name, self.plain)
        cast = self.cast()
        one, other = cast.dolls.get("one"), cast.dolls.get("other")
        self.assertIsNot(cast.shown("one", one, 0.0).doll, one)
        # Enough has been made in this frame: the other is its drawing, from its side.
        waiting = cast.shown("other", other, 0.0)
        self.assertIs(waiting.doll, other)
        self.assertEqual(waiting.yaw, cast.side)
        cast.new_frame()
        turned = cast.shown("other", other, 0.0)
        self.assertIsNot(turned.doll, other)
        self.assertEqual(turned.yaw, 0.0)

    def test_on_a_map_a_body_is_kept_turned_in_coarser_steps(self) -> None:
        self.keep("old", self.plain)
        cast = self.cast()
        doll = cast.dolls.get("old")
        self.assertEqual(cast.shown("old", doll, 30.0, 22.5).yaw, 22.5)
        cast.new_frame()
        self.assertEqual(cast.shown("old", doll, 35.0, 22.5).yaw, 45.0)
        cast.new_frame()
        self.assertEqual(cast.shown("old", doll, 200.0, 22.5).yaw, 180.0)
        self.assertEqual(cast.shown("old", doll, 95.0, 22.5).yaw, cast.side)

    def test_a_head_with_its_face_drawn_on_it_has_none_on_the_back_of_it(self) -> None:
        drawn = dict(self.plain)
        head = drawn[HEAD_CANVAS] = drawn[HEAD_CANVAS].copy()
        box = head.get_bounding_rect()
        # An eye, where one drawn from the side has it.
        pygame.draw.circle(head, GREEN, (box.centerx + box.width // 5, box.centery), 5)
        self.keep("old", drawn)
        cast = self.cast()
        doll = cast.dolls.get("old")
        self.assertGreater(greens(cast.shown("old", doll, 0.0).doll.parts["skull"].image), 30)
        cast.new_frame()
        behind = cast.shown("old", doll, 180.0).doll.parts["skull"].image
        self.assertEqual(greens(behind), 0)
        # It is as large as it was, with the line round it.
        self.assertAlmostEqual(pygame.mask.from_surface(behind).count(), pygame.mask.from_surface(doll.parts["skull"].image).count(), delta=40)

    def test_a_pose_goes_round_with_the_body_and_is_as_it_was_from_its_side(self) -> None:
        self.keep("old", self.plain)
        cast = self.cast()
        doll = cast.dolls.get("old")
        facing = DOLL_FACINGS["right"]
        pose = doll.plan.pose(facing, "walk", 0.3)
        self.assertIs(cast.posed(cast.shown("old", doll), pose, facing), pose)
        cast.new_frame()
        front = cast.posed(cast.shown("old", doll, 0.0), pose, facing)
        self.assertGreater(front["shoulder_left"][0], front["chest"][0])
        self.assertLess(front["shoulder_right"][0], front["chest"][0])
        self.assertEqual(front["shoulder_left"][1], pose["shoulder_left"][1])

    def test_somebody_nobody_has_drawn_is_turned_as_one_drawn_from_its_side(self) -> None:
        cast = self.cast()
        doll = cast.dolls.stand_in("nobody", lambda template: figures(template, tones_of(SKIN, LINE), 5))
        self.assertIs(cast.shown(None, doll).doll, doll)
        cast.new_frame()
        self.assertGreater(self.width(cast.shown(None, doll, 0.0).doll), self.width(doll) * 1.3)
        self.assertEqual(cast.said("nobody").drawn, SIDE_DRAWN)
        self.assertIn(HEAD_CANVAS, doll.sheets)


if __name__ == "__main__":
    unittest.main()
