import math
import os
import tempfile
import unittest
from pathlib import Path

import pygame

from graphics.doll import BODY_CANVAS, DOLL_FACINGS, HEAD_CANVAS, Doll, DollStore, doll_path, draw_doll, load_template
from graphics.illustrations import Illustrations
from graphics.palette import PALETTE
from scenes.hud import DRAW_INTENT
from settings import SCALE, SCREEN_HEIGHT, SCREEN_WIDTH
from simulation.health.injury import Injury
from skeleton.plan import builtin_plan
from skeleton.rig import Skeleton

RED, BLUE = (220, 30, 30), (30, 60, 220)


def _painted(surface: pygame.Surface) -> int:
    return pygame.mask.from_surface(surface).count()


class DollTemplateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.plan = builtin_plan()
        self.template = load_template()

    def test_the_doll_lengthens_its_torso_and_arms_but_not_its_legs(self) -> None:
        unit = self.template.unit
        self.assertEqual(set(self.template.canvases), {BODY_CANVAS, HEAD_CANVAS})
        self.assertEqual(self.plan.like("doll"), "side", "a doll is posed by the clips of a body seen from the side")
        stretched = {}
        for bone, spec in self.template.parts.items():
            self.assertIn(bone, self.plan.bones)
            longer = self.plan.length("doll", bone) / (math.dist(spec.start, spec.end) / unit)
            if abs(longer - 1.0) > 1e-6:
                stretched[bone] = round(longer, 3)
        # The longer torso gives the figure adult proportions. Arms still gain a little reach, but
        # legs keep their drawn length so trousers and shoes are not pulled apart.
        self.assertEqual(
            set(stretched),
            {"spine", *{f"{part}_{side}" for part in ("upper_arm", "forearm") for side in ("left", "right")}},
        )
        for bone, longer in stretched.items():
            limits = (1.3, 1.4) if bone == "spine" else (1.1, 1.3)
            self.assertTrue(limits[0] <= longer <= limits[1], (bone, longer))
            if bone.endswith("_left"):
                self.assertEqual(longer, stretched[bone.replace("_left", "_right")], bone)
        for part in ("thigh", "shin"):
            for side in ("left", "right"):
                bone = f"{part}_{side}"
                drawn = math.dist(self.template.parts[bone].start, self.template.parts[bone].end) / unit
                self.assertAlmostEqual(self.plan.length("doll", bone), drawn)
        self.assertEqual(set(self.template.parts), set(self.plan.orders["doll"]), "every part has its turn to be drawn")

    def test_hands_feet_and_hips_are_parts_of_their_own(self) -> None:
        parts = self.template.parts
        for side in ("left", "right"):
            self.assertEqual(parts[f"hand_{side}"].start, parts[f"forearm_{side}"].end, "a hand starts at the wrist")
            self.assertEqual(parts[f"foot_{side}"].start, parts[f"shin_{side}"].end, "a foot starts at the ankle")
            foot = parts[f"foot_{side}"]
            self.assertGreater(foot.end[0] - foot.start[0], abs(foot.end[1] - foot.start[1]), "and points forwards")
        self.assertEqual(parts["hips"].start, parts["spine"].start, "the hips hang from where the trunk stands")
        self.assertGreater(parts["hips"].end[1], parts["hips"].start[1])
        # A hand turns with its forearm. A planted foot stays level, while the other one flexes
        # with the stride instead of looking snapped away from its ankle.
        swung = self.plan.pose("doll_right", "fight", 0.3)
        still = self.plan.pose("doll_right")
        hand = lambda pose: (pose["fingertip_right"][0] - pose["hand_right"][0], pose["fingertip_right"][1] - pose["hand_right"][1])
        foot_of = lambda pose: (pose["toe_right"][0] - pose["foot_right"][0], pose["toe_right"][1] - pose["foot_right"][1])
        self.assertNotAlmostEqual(hand(swung)[0], hand(still)[0], 1)
        walking = self.plan.pose("doll_right", "walk", 0.0)
        self.assertNotEqual(walking["foot_right"], still["foot_right"])
        left_foot = lambda pose: (pose["toe_left"][0] - pose["foot_left"][0], pose["toe_left"][1] - pose["foot_left"][1])
        self.assertAlmostEqual(foot_of(walking)[1], foot_of(still)[1], 5, "the planted foot is level")
        self.assertGreater(abs(left_foot(walking)[1]), 0.5, "the lifted foot flexes with the leg")

    def test_the_near_arm_hangs_from_further_back_and_the_near_leg_goes_over_the_body(self) -> None:
        rest = self.plan.rests["doll"]
        self.assertLess(rest["shoulder_right"][0], rest["chest"][0], "facing right, the arm of the near side is nearer the back")
        self.assertGreater(rest["shoulder_left"][0], rest["chest"][0], "and the far one nearer the chest")
        # The legs leave the hips as the arms leave the shoulders: the near one behind, the far one in front.
        for side in ("left", "right"):
            self.assertEqual(rest[f"hip_{side}"][0], rest[f"shoulder_{side}"][0], side)
            self.assertEqual(rest[f"foot_{side}"][0], rest[f"hip_{side}"][0], f"the {side} leg hangs straight")
        order = self.plan.orders["doll"]
        self.assertLess(order.index("thigh_left"), order.index("spine"))
        self.assertLess(order.index("hips"), order.index("thigh_right"), "the near leg is drawn over the hips")
        self.assertLess(order.index("spine"), order.index("thigh_right"))
        # It starts low in the hips: well below the waist, so that its top does not show up in the belly,
        # and no lower than the hips may be drawn, so that it does not hang loose under them.
        hips = self.template.parts["hips"]
        drawn_to = (math.dist(hips.start, hips.end) + hips.ends[1]) / self.template.unit
        for side in ("left", "right"):
            below_waist = rest[f"hip_{side}"][1] - rest["pelvis"][1]
            self.assertGreater(below_waist, drawn_to * 0.75, side)
            self.assertLess(below_waist, drawn_to, side)

    def test_zones_only_overlap_where_two_parts_are_jointed(self) -> None:
        masks = {bone: pygame.mask.from_surface(self.template.mask(bone)) for bone, spec in self.template.parts.items() if not spec.whole}
        for bone, mask in masks.items():
            width, height = self.template.canvases[BODY_CANVAS]
            self.assertEqual(mask.get_bounding_rects()[0].clip(pygame.Rect(0, 0, width, height)), mask.get_bounding_rects()[0], bone)
            for other, other_mask in masks.items():
                ends = lambda name: {self.plan.bones[name].start, self.plan.bones[name].end}
                jointed = bool(ends(bone) & ends(other))
                if bone < other and not jointed:
                    self.assertEqual(mask.overlap_area(other_mask, (0, 0)), 0, (bone, other))
            lower = [other for other in masks if self.plan.bones[bone].end == self.plan.bones[other].start]
            for other in lower:
                self.assertGreater(mask.overlap_area(masks[other], (0, 0)), 0, f"{bone} and {other} must overlap at their joint")

    def test_every_zone_leaves_room_round_the_example_to_draw_a_stouter_or_odder_body(self) -> None:
        for bone, spec in self.template.parts.items():
            if spec.whole:
                # A head has its whole canvas, and its example leaves room all round for hair or a hat.
                width, height = self.template.canvases[spec.canvas]
                self.assertGreater(min(spec.end[0], width - spec.end[0], spec.end[1]), spec.radius * 1.7, bone)
                continue
            self.assertGreaterEqual(spec.reach, spec.radius * 1.9, f"{bone} can be drawn about twice as wide")
            zone = pygame.mask.from_surface(self.template.mask(bone))
            example = pygame.mask.from_surface(self.template.example(bone, RED))
            self.assertEqual(example.overlap_area(zone, (0, 0)), example.count(), f"the example of {bone} is inside its zone")
            self.assertGreater(zone.count(), example.count() * 1.8, bone)

    def test_there_is_a_neck_between_the_shoulders_and_the_head(self) -> None:
        neck, trunk = self.template.parts["neck"], self.template.parts["spine"]
        self.assertEqual(neck.start, trunk.end, "it comes out of the trunk where the shoulders are")
        self.assertLess(neck.radius, trunk.radius / 2, "and is a good deal thinner")
        # The trunk's example stops just above the shoulders, so the neck's shows over it.
        top_of_trunk = pygame.mask.from_surface(self.template.example("spine", RED)).get_bounding_rects()[0].top
        top_of_neck = pygame.mask.from_surface(self.template.example("neck", BLUE)).get_bounding_rects()[0].top
        self.assertGreater(top_of_trunk - top_of_neck, self.template.unit)
        # Put together, the head clears the shoulders by the length of the neck: there is skin to see between them.
        doll = Doll(self.template, self.template.mannequin({**{bone: RED for bone in self.template.parts}, "neck": BLUE}))
        skeleton = Skeleton(self.plan, "doll_right")
        skeleton.set_pose(self.plan.pose("doll_right"))
        picture = pygame.Surface((400, 500), pygame.SRCALPHA)
        detail = float(self.template.unit)
        draw_doll(picture, doll, self.plan, skeleton, (200, 460), detail)
        showing = pygame.mask.from_threshold(picture, (*BLUE, 255), (30, 30, 30, 255))
        self.assertGreater(showing.count(), 200, "the neck is in sight")
        box = showing.get_bounding_rects()[0]
        chest_y = 460 + (skeleton.joints["chest"].y + 0.5) * detail
        self.assertLess(box.top, chest_y - detail, "and rises well above the shoulders")
        self.assertLess(box.width, trunk.radius * 2)

    def test_the_guide_marks_every_zone_and_the_mannequin_fills_them_all(self) -> None:
        for canvas, size in self.template.canvases.items():
            guide = self.template.guide(canvas)
            self.assertEqual(guide.get_size(), size)
            self.assertGreater(_painted(guide), size[0] * size[1] // 6)
        figure = self.template.mannequin({bone: RED for bone in self.template.parts})
        doll = Doll(self.template, figure)
        self.assertEqual(set(doll.parts), set(self.template.parts))


class DollCuttingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.plan = builtin_plan()
        self.template = load_template()
        self.body = pygame.Surface(self.template.canvases[BODY_CANVAS], pygame.SRCALPHA)
        self.head = pygame.Surface(self.template.canvases[HEAD_CANVAS], pygame.SRCALPHA)

    def _doll(self) -> Doll:
        return Doll(self.template, {BODY_CANVAS: self.body, HEAD_CANVAS: self.head})

    def test_what_is_drawn_in_a_zone_goes_with_that_part_and_no_other(self) -> None:
        forearm, thigh = self.template.parts["forearm_right"], self.template.parts["thigh_left"]
        # Away from the joints, where two parts overlap on purpose.
        along = lambda spec, part: (spec.start[0] + (spec.end[0] - spec.start[0]) * part, spec.start[1] + (spec.end[1] - spec.start[1]) * part)
        pygame.draw.circle(self.body, RED, along(forearm, 0.8), 6)
        pygame.draw.circle(self.body, BLUE, along(thigh, 0.25), 6)
        # A scribble where no zone is belongs to nothing.
        pygame.draw.circle(self.body, RED, (self.body.get_width() // 2, self.body.get_height() - 4), 3)
        doll = self._doll()
        self.assertEqual(set(doll.parts), {"forearm_right", "thigh_left"})
        colours = lambda part: {tuple(part.image.get_at((x, y)))[:3] for x in range(part.image.get_width()) for y in range(part.image.get_height()) if part.image.get_at((x, y))[3]}
        self.assertEqual(colours(doll.parts["forearm_right"]), {RED})
        self.assertEqual(colours(doll.parts["thigh_left"]), {BLUE})

    def test_a_body_drawn_well_outside_the_example_is_still_cut_into_its_parts(self) -> None:
        trunk, arm = self.template.parts["spine"], self.template.parts["upper_arm_right"]
        # A belly out to the edge of the trunk's zone, and an arm twice as thick as the example.
        belly = (trunk.start[0] + trunk.reach - 6, trunk.start[1] - 10)
        thick = (arm.start[0] - arm.reach + 6, (arm.start[1] + arm.end[1]) / 2 - 8)
        self.assertGreater(belly[0] - trunk.start[0], trunk.radius * 1.5)
        pygame.draw.circle(self.body, RED, belly, 5)
        pygame.draw.circle(self.body, BLUE, thick, 5)
        doll = self._doll()
        self.assertEqual(set(doll.parts), {"spine", "upper_arm_right"})
        self.assertEqual(_painted(doll.parts["spine"].image), _painted(doll.parts["upper_arm_right"].image))
        # It moves with its part: laid out at any angle, the belly is still there, whole.
        image, _ = doll.placed("spine", False, self.template.unit, 2.0)
        self.assertAlmostEqual(_painted(image), _painted(doll.parts["spine"].image), delta=30)

    def test_parts_that_meet_at_a_joint_end_in_the_same_round_so_no_corner_sticks_out_when_it_bends(self) -> None:
        upper, fore = self.template.parts["upper_arm_right"], self.template.parts["forearm_right"]
        # An arm drawn as one thick bar, straight through the elbow, as anyone would draw it.
        half = 22
        bar = pygame.Rect(upper.start[0] - half, upper.start[1] - 10, half * 2, fore.end[1] - upper.start[1] + 20)
        pygame.draw.rect(self.body, RED, bar)
        doll = self._doll()
        elbow = fore.start

        def has(part_name: str, at: tuple[float, float]) -> bool:
            """Whether a part kept the pixel of the drawing at a place on the canvas."""
            part, spec = doll.parts[part_name], self.template.parts[part_name]
            x, y = round(at[0] - spec.start[0] + part.start[0]), round(at[1] - spec.start[1] + part.start[1])
            return part.image.get_rect().collidepoint(x, y) and part.image.get_at((x, y))[3] > 0

        past = half * 0.85
        # Past the elbow the upper arm keeps what is within the arm's width of the joint, and not the corners beyond.
        self.assertTrue(has("upper_arm_right", (elbow[0], elbow[1] + past)))
        self.assertFalse(has("upper_arm_right", (elbow[0] + past, elbow[1] + past)))
        self.assertFalse(has("upper_arm_right", (elbow[0], elbow[1] + half * 1.5)))
        # The forearm does the same on its side of the joint, so the two ends are one circle.
        self.assertTrue(has("forearm_right", (elbow[0], elbow[1] - past)))
        self.assertFalse(has("forearm_right", (elbow[0] - past, elbow[1] - past)))
        # Between its joints each part is whole, corner to corner, and the hand end is left as drawn.
        self.assertTrue(has("upper_arm_right", (elbow[0] + half - 2, elbow[1] - 20)))
        self.assertTrue(has("forearm_right", (fore.end[0] + half - 2, fore.end[1] + 8)))
        # The same at the shoulder, where the arm turns against the trunk.
        self.assertFalse(has("upper_arm_right", (upper.start[0] + past, upper.start[1] - past)))
        # Bent double, nothing of the arm reaches further from the elbow than the arm is wide.
        skeleton = Skeleton(self.plan, "doll_right", ["arm_left", "leg_left", "leg_right"])
        pose = self.plan.pose("doll_right")
        skeleton.set_pose(pose)
        joints = skeleton.joints
        upper_long, fore_long = skeleton.bones["upper_arm_right"].length, skeleton.bones["forearm_right"].length
        joints["elbow_right"].x, joints["elbow_right"].y = joints["shoulder_right"].x, joints["shoulder_right"].y + upper_long
        joints["hand_right"].x, joints["hand_right"].y = joints["elbow_right"].x + fore_long, joints["elbow_right"].y
        joints["fingertip_right"].x, joints["fingertip_right"].y = joints["hand_right"].x + 1.6, joints["hand_right"].y
        picture = pygame.Surface((300, 300), pygame.SRCALPHA)
        detail = float(self.template.unit)
        draw_doll(picture, doll, self.plan, skeleton, (150, 290), detail)
        at_elbow = (150 + (joints["elbow_right"].x + 0.5) * detail, 290 + (joints["elbow_right"].y + 0.5) * detail)
        outer_corner = (round(at_elbow[0] - past), round(at_elbow[1] + past))
        self.assertEqual(picture.get_at(outer_corner)[3], 0, "the outside of the bend is round")
        self.assertGreater(picture.get_at((round(at_elbow[0]), round(at_elbow[1])))[3], 0)

    def test_a_limb_longer_than_it_was_drawn_grows_between_its_joints_and_keeps_its_round_ends(self) -> None:
        fore = self.template.parts["forearm_right"]
        half = 22
        pygame.draw.rect(self.body, RED, pygame.Rect(fore.start[0] - half, fore.start[1] - 40, half * 2, fore.end[1] - fore.start[1] + 80))
        doll = self._doll()
        detail = float(self.template.unit)
        drawn, _ = doll.placed("forearm_right", False, detail, 0.0)
        longer, joint = doll.placed("forearm_right", False, detail, 0.0, doll.drawn["forearm_right"] * 1.25)
        grown = round((fore.end[1] - fore.start[1]) * 0.25)
        self.assertEqual(longer.get_width(), drawn.get_width(), "it is no wider")
        self.assertEqual(longer.get_height(), drawn.get_height() + grown)
        # Above the elbow it is the same round end, pixel for pixel; below the wrist, the same again.
        above = round(joint[1])
        for surface in (drawn, longer):
            self.assertEqual(surface.get_at((round(joint[0]), 2))[3], 255)
        rows = lambda surface, first, last: [surface.get_at((x, y))[3] for y in range(first, last) for x in range(surface.get_width())]
        self.assertEqual(rows(longer, 0, above), rows(drawn, 0, above))
        tail = drawn.get_height() - round(joint[1]) - (fore.end[1] - fore.start[1])
        self.assertEqual(rows(longer, longer.get_height() - int(tail), longer.get_height()), rows(drawn, drawn.get_height() - int(tail), drawn.get_height()))

    def test_no_dark_edge_shows_where_a_drawing_is_cut(self) -> None:
        upper, fore = self.template.parts["upper_arm_right"], self.template.parts["forearm_right"]
        half = 22
        pygame.draw.rect(self.body, RED, pygame.Rect(upper.start[0] - half, upper.start[1], half * 2, fore.end[1] - upper.start[1]))
        doll = self._doll()
        # Much smaller than drawn, every pixel along the cut is a blend of red with what was cut away.
        image, _ = doll.placed("forearm_right", False, 3.0, 0.3, doll.drawn["forearm_right"] * 1.2)
        seen = [tuple(image.get_at((x, y))) for x in range(image.get_width()) for y in range(image.get_height())]
        for red, green, blue, alpha in seen:
            if alpha > 24:
                self.assertTrue(all(abs(got - want) <= 12 for got, want in zip((red, green, blue), RED)), (red, green, blue, alpha))

    def test_what_is_drawn_across_a_joint_goes_with_both_parts(self) -> None:
        elbow = self.template.parts["forearm_right"].start
        pygame.draw.circle(self.body, RED, elbow, 5)
        self.assertEqual(set(self._doll().parts), {"upper_arm_right", "forearm_right"})

    def test_everything_on_the_head_canvas_is_the_head_hair_and_all(self) -> None:
        self.head.fill(BLUE)
        doll = self._doll()
        self.assertEqual(doll.parts["skull"].image.get_size(), self.head.get_size())

    def test_a_part_turns_about_its_first_joint_the_way_its_bone_points(self) -> None:
        spec = self.template.parts["forearm_right"]
        # Only the far end of the forearm is drawn: a hand, to be found again once it is laid out.
        pygame.draw.circle(self.body, RED, spec.end, 8)
        doll = self._doll()
        detail = 8.0
        reach = doll.drawn["forearm_right"] * detail
        for angle in (0.0, math.pi / 2, math.pi, -math.pi / 2, 0.6):
            image, joint = doll.placed("forearm_right", False, detail, angle)
            hand = pygame.mask.from_surface(image).centroid()
            self.assertAlmostEqual(hand[0] - joint[0], math.sin(angle) * reach, delta=3.5, msg=angle)
            self.assertAlmostEqual(hand[1] - joint[1], math.cos(angle) * reach, delta=3.5, msg=angle)
            self.assertIs(doll.placed("forearm_right", False, detail, angle)[0], image, "a turned part is kept")
        self.assertIsNone(doll.placed("thigh_left", False, detail, 0.0), "nothing was drawn there")

    def test_facing_the_other_way_the_doll_is_the_same_drawing_in_a_mirror(self) -> None:
        figure = self.template.mannequin({bone: RED for bone in self.template.parts})
        # Something on one side only, to tell the two ways apart.
        foot = self.template.parts["foot_right"]
        pygame.draw.circle(figure[BODY_CANVAS], BLUE, (foot.end[0] + 6, foot.end[1] + 6), 8)
        doll = Doll(self.template, figure)
        pictures = {}
        for facing in ("right", "left"):
            skeleton = Skeleton(self.plan, DOLL_FACINGS[facing])
            skeleton.set_pose(self.plan.pose(DOLL_FACINGS[facing], "walk", 0.2))
            picture = pygame.Surface((400, 400), pygame.SRCALPHA)
            draw_doll(picture, doll, self.plan, skeleton, (200, 300), 10.0)
            pictures[facing] = picture
        right, left = pictures["right"].get_bounding_rect(), pictures["left"].get_bounding_rect()
        self.assertAlmostEqual(right.right - 200, 200 - left.left, delta=12)
        self.assertAlmostEqual(right.top, left.top, delta=2)
        self.assertGreater(right.height, 150)
        blue = lambda picture: pygame.mask.from_threshold(picture, (*BLUE, 255), (40, 40, 40, 255)).centroid()[0]
        self.assertGreater(blue(pictures["right"]), 200, "the toe points the way it faces")
        self.assertLess(blue(pictures["left"]), 200)

    def test_a_doll_short_of_a_limb_is_drawn_without_it(self) -> None:
        doll = Doll(self.template, self.template.mannequin({bone: RED for bone in self.template.parts}))
        counts = []
        for lost in ((), ("arm_right",), ("arm_right", "leg_left")):
            skeleton = Skeleton(self.plan, "doll_right", lost)
            skeleton.set_pose(self.plan.pose("doll_right", "fight", 0.3))
            picture = pygame.Surface((400, 400), pygame.SRCALPHA)
            draw_doll(picture, doll, self.plan, skeleton, (200, 300), 10.0)
            counts.append(_painted(picture))
        self.assertGreater(counts[0], counts[1])
        self.assertGreater(counts[1], counts[2])

    def test_a_store_cuts_a_doll_once_from_what_is_on_disk_and_only_if_the_body_was_drawn(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            figure = self.template.mannequin({bone: RED for bone in self.template.parts})
            for body_id, canvases in (("raul", (BODY_CANVAS, HEAD_CANVAS)), ("marta", (HEAD_CANVAS,))):
                for canvas in canvases:
                    path = root / doll_path(body_id, canvas)
                    path.parent.mkdir(parents=True, exist_ok=True)
                    pygame.image.save(figure[canvas], str(path))
            # A drawing made elsewhere at another size is brought to the size of its canvas.
            large = root / doll_path("paco", BODY_CANVAS)
            large.parent.mkdir(parents=True)
            pygame.image.save(pygame.transform.scale(figure[BODY_CANVAS], (512, 704)), str(large))
            store = DollStore(Illustrations(root), self.template)
            raul = store.get("raul")
            self.assertEqual(set(raul.parts), set(self.template.parts))
            self.assertIs(store.get("raul"), raul)
            self.assertIsNone(store.get("marta"), "a head alone is not a body")
            self.assertIsNone(store.get("lucia"))
            self.assertEqual(set(store.get("paco").parts), set(self.template.parts) - {"skull"})
            store.forget("raul")
            self.assertIsNot(store.get("raul"), raul)
        self.assertIsNone(DollStore(None, self.template).get("raul"))


class DollEditorTests(unittest.TestCase):
    """The real game shell, without a window, with an empty folder to keep drawings in."""

    def setUp(self) -> None:
        for variable in ("SDL_VIDEODRIVER", "SDL_AUDIODRIVER"):
            self.addCleanup(self._restore, variable, os.environ.get(variable))
            os.environ[variable] = "dummy"
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name) / "illustrations"
        self.root.mkdir()
        from game.game import Game

        self.game = Game(illustrations_dir=self.root, voices_dir=None, start_in_menu=False)
        self.addCleanup(pygame.quit)
        self.window = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))

    @staticmethod
    def _restore(variable: str, previous: str | None) -> None:
        if previous is None:
            os.environ.pop(variable, None)
        else:
            os.environ[variable] = previous

    def _show(self) -> pygame.Surface:
        with self.assertNoLogs("graphics.assets", level="WARNING"):
            self.game.active_scene.render()
        self.game.present(self.window)
        return self.window

    def _event(self, kind: int, position: tuple[int, int], **more) -> None:
        window = (position[0] * SCALE + 1, position[1] * SCALE + 1)
        self.game.active_scene.handle_event(pygame.event.Event(kind, pos=window, **more))

    def _click(self, position: tuple[int, int]) -> None:
        self._event(pygame.MOUSEBUTTONDOWN, position, button=1)
        self._event(pygame.MOUSEBUTTONUP, position, button=1)

    def _open(self, resident_id: str):
        view = self.game.global_view
        view.hud.select_resident(resident_id)
        draw = next(button for button in view.hud.menu if button.intent == DRAW_INTENT)
        self._click(draw.rect.center)
        self.game.sync_scenes()
        self.assertEqual(self.game.scene_name, "editor")
        return self.game.doll_editor

    def _button(self, editor, intent: tuple):
        return next(button for button in editor.buttons if button.intent == intent)

    def test_the_menu_opens_the_editor_on_whoever_is_selected_and_time_stops(self) -> None:
        editor = self._open("lucia")
        self.assertEqual(editor.resident_id, "lucia")
        minute = self.game.world.clock.total_minutes
        self.game.advance_simulation(5.0)
        self.assertEqual(self.game.world.clock.total_minutes, minute)
        self._show()
        # Escape leaves the drawing, not the game.
        self.game.handle_key(pygame.K_ESCAPE)
        editor.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE, mod=0))
        self.game.sync_scenes()
        self.assertEqual(self.game.scene_name, "global")
        self.assertTrue(self.game.running)
        # With nobody selected, F2 opens it on the first resident there is.
        self.game.global_view.hud.select_resident(None)
        self.game.global_view.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_F2))
        self.game.sync_scenes()
        self.assertEqual(self.game.doll_editor.resident_id, next(iter(self.game.world.residents)))

    def test_strokes_paint_the_canvas_under_the_mouse_and_can_be_undone(self) -> None:
        editor = self._open("raul")
        body, head = editor.areas[BODY_CANVAS], editor.areas[HEAD_CANVAS]
        self.assertEqual(_painted(editor.drawings[BODY_CANVAS]), 0)
        ember = next(rect for rect, color in editor.swatches if color == PALETTE["ember"])
        self._click(ember.center)
        self.assertEqual(editor.color, PALETTE["ember"])
        self._event(pygame.MOUSEBUTTONDOWN, (body.x + 40, body.y + 60), button=1)
        self._event(pygame.MOUSEMOTION, (body.x + 120, body.y + 60), rel=(0, 0), buttons=(1, 0, 0))
        self._event(pygame.MOUSEBUTTONUP, (body.x + 120, body.y + 60), button=1)
        drawing = editor.drawings[BODY_CANVAS]
        self.assertEqual(tuple(drawing.get_at((80, 60)))[:3], PALETTE["ember"], "the stroke runs between the two points")
        self.assertEqual(_painted(editor.drawings[HEAD_CANVAS]), 0)
        stroke = _painted(drawing)
        # A thicker brush, on the other canvas.
        self._click(editor.brush_buttons[-1][0].center)
        self._click((head.x + 80, head.y + 80))
        self.assertGreater(_painted(editor.drawings[HEAD_CANVAS]), 100)
        # The rubber takes paint off, and the bucket pours it in.
        self._click(self._button(editor, ("tool", "eraser")).rect.center)
        self._click((body.x + 80, body.y + 60))
        self.assertLess(_painted(editor.drawings[BODY_CANVAS]), stroke)
        self._click(self._button(editor, ("tool", "fill")).rect.center)
        self._click(next(rect for rect, color in editor.swatches if color == PALETTE["teal"]).center)
        self._click((body.x + 5, body.y + 5))
        self.assertEqual(tuple(editor.drawings[BODY_CANVAS].get_at((200, 300)))[:3], PALETTE["teal"])
        # Each of those can be taken back, with the button or with the keys.
        self._click(self._button(editor, ("undo",)).rect.center)
        self.assertEqual(editor.drawings[BODY_CANVAS].get_at((200, 300))[3], 0)
        editor.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_z, mod=pygame.KMOD_CTRL))
        self.assertEqual(_painted(editor.drawings[BODY_CANVAS]), stroke)
        self._click(self._button(editor, ("clear",)).rect.center)
        self.assertEqual(_painted(editor.drawings[BODY_CANVAS]) + _painted(editor.drawings[HEAD_CANVAS]), 0)
        self._show()

    def test_the_guide_goes_under_over_or_away_and_the_drawing_shows_at_twice_its_size(self) -> None:
        editor = self._open("raul")
        body = editor.areas[BODY_CANVAS]
        spot = ((body.x + 160) * SCALE, (body.y + 80) * SCALE)
        with_guide = tuple(self._show().get_at(spot))[:3]
        self._click(editor.guide_button.rect.center)
        self._click(editor.guide_button.rect.center)
        self.assertEqual(editor.guide, "off")
        self.assertNotEqual(tuple(self._show().get_at(spot))[:3], with_guide, "under the trunk the guide was tinting the paper")
        editor.color = RED
        editor.press((body.x + 160, body.y + 80))
        editor.release()
        self.assertEqual(tuple(self._show().get_at(spot))[:3], RED)
        self.assertEqual(self.game.canvas.get_at((body.x + 160, body.y + 80))[3], 0, "the canvas is clear over the drawing")

    def test_a_saved_drawing_is_cut_into_a_doll_that_walks_the_map_and_gives_them_a_face(self) -> None:
        game, view = self.game, self.game.global_view
        raul = game.world.residents["raul"]
        self.assertIsNone(game.dolls.get("raul"))
        self.assertIsNone(game.faces.portrait("raul", "neutral", (64, 64)))
        pixel_face = game.faces.face("raul", "neutral").copy()
        editor = self._open("raul")
        self._click(editor.mannequin_button.rect.center)
        self.assertGreater(_painted(editor.drawings[BODY_CANVAS]), 5000)
        self._click(self._button(editor, ("save",)).rect.center)
        for canvas, size in editor.template.canvases.items():
            saved = pygame.image.load(str(self.root / doll_path("raul", canvas)))
            self.assertEqual(saved.get_size(), size)
        self.assertIn("Guardado", editor.notice)
        self._click(self._button(editor, ("close",)).rect.center)
        game.sync_scenes()
        self.assertEqual(game.scene_name, "global")

        doll = game.dolls.get("raul")
        self.assertEqual(set(doll.parts), set(editor.template.parts))
        raul.x, raul.y, raul.trail, raul.activity, raul.facing = 20, 14, [], None, "down"
        view.centre_on((20, 14))
        window = self._show()
        self.assertEqual([entry[1] for entry in view._doll_draws], [doll])
        self.assertTrue(game.layers.active)
        self.assertEqual(game.canvas.get_at(view.viewport.center)[3], 0, "the map is on the window, under the canvas")
        # He is there, at the size of the window: his trunk is not the colour of the ground.
        hitbox = view.hitboxes["raul"]
        chest = (hitbox.centerx * SCALE, (hitbox.bottom - 11) * SCALE)
        self.assertNotEqual(tuple(window.get_at(chest))[:3], tuple(window.get_at((chest[0] + 80, chest[1])))[:3])
        # What is picked with the mouse, and what his name goes over, is the doll as tall as it was drawn.
        column = [tuple(window.get_at((hitbox.centerx * SCALE, y)))[:3] for y in range((hitbox.top - 8) * SCALE, (hitbox.top + 3) * SCALE)]
        skin = column[-1]
        self.assertNotEqual(skin, tuple(window.get_at((chest[0] + 80, chest[1])))[:3], "just below its top is his head")
        self.assertNotIn(skin, column[: 7 * SCALE], "and above it only his name")
        # It stands by its own measures, which are those of the paper: nothing is drawn out to fit the game's body.
        self.assertIsNot(doll.plan, view.bodies.plan)
        self.assertIs(view.bodies.characters["raul"].plan, doll.plan)
        left, high, right, low = doll.standing(doll.plan)
        crown = doll.plan.rests["doll"]["head"][1] + 0.5 - editor.template.parts["skull"].radius / editor.template.unit
        for bone in ("spine", "thigh_left", "upper_arm_right"):
            self.assertAlmostEqual(doll.plan.length("doll", bone), doll.drawn[bone], msg=f"{bone} is as long as it was drawn")
        self.assertAlmostEqual(high, crown, delta=0.5, msg="the plain head of the mannequin, and no hair")
        self.assertEqual(-left, right)
        self.assertAlmostEqual(low, 0.0, delta=1.0)
        # Seen from the side, he keeps facing the way he last walked across.
        self.assertEqual(view.bodies.characters["raul"].facing, "doll_right")
        raul.trail = [(21, 14), (20, 14)]
        self._show()
        self.assertEqual(view.bodies.characters["raul"].facing, "doll_left")
        raul.trail, raul.facing = [], "up"
        self._show()
        self.assertEqual(view.bodies.characters["raul"].facing, "doll_left")
        # The head he was drawn is his face from now on. Nobody else has changed.
        self.assertIsNotNone(game.faces.portrait("raul", "neutral", (64, 64)))
        self.assertNotEqual(pygame.image.tobytes(game.faces.face("raul", "neutral"), "RGBA"), pygame.image.tobytes(pixel_face, "RGBA"))
        self.assertIsNone(game.dolls.get("marta"))
        # Opened again, the editor starts from what was saved.
        self.assertGreater(_painted(self._open("raul").drawings[BODY_CANVAS]), 5000)

    def test_a_doll_reels_falls_loses_limbs_and_sleeps_like_any_other_body(self) -> None:
        game, view, world = self.game, self.game.global_view, self.game.world
        for name in ("raul", "lucia"):
            editor = self._open(name)
            editor.mannequin()
            editor.save()
            editor.closed = True
            game.sync_scenes()
        raul, lucia, tomas = (world.residents[name] for name in ("raul", "lucia", "tomas"))
        for index, resident in enumerate((raul, lucia, tomas)):
            resident.x, resident.y, resident.trail, resident.activity = 20 + index, 14, [], None
        view.centre_on((21, 14))
        self._show()
        self.assertEqual(len(view._doll_draws), 2, "Tomás has not been drawn: he is the game's own pixel art")
        world.health.hurt(world, raul, 22, "fracture", "una prueba", tomas)
        lucia.injuries = [Injury("cut", 99)]
        world.health.hurt(world, lucia, 5, "bruise", "una prueba", tomas)
        view.on_events(world.events.drain())
        for _ in range(30):
            view.update(1 / 60)
            self._show()
        skeletons = [entry[2] for entry in view._doll_draws]
        self.assertIn(view.bodies.characters["raul"].skeleton, skeletons, "knocked down, the doll follows his skeleton")
        self.assertIn(view.bodies.remains[0].skeleton, skeletons, "and hers lies where she fell")
        # In bed, only the head of a doll shows.
        bed = world.interactables["bed_1"]
        from simulation.residents.activity import Activity

        raul.x, raul.y, raul.activity = bed.x, bed.y, Activity("sleep", "bed_1", using=True)
        view.centre_on((bed.x, bed.y))
        view.roofs_on = False
        self._show()
        lying = [entry for entry in view._doll_draws if entry[2] is None]
        self.assertEqual(len(lying), 1)
        self.assertIsNotNone(lying[0][3])


class NoDrawingsFolderTests(unittest.TestCase):
    def test_without_a_folder_to_keep_drawings_in_there_is_no_editor(self) -> None:
        previous = {variable: os.environ.get(variable) for variable in ("SDL_VIDEODRIVER", "SDL_AUDIODRIVER")}
        os.environ.update(SDL_VIDEODRIVER="dummy", SDL_AUDIODRIVER="dummy")
        self.addCleanup(lambda: [os.environ.pop(k) if v is None else os.environ.__setitem__(k, v) for k, v in previous.items()])
        from game.game import Game

        game = Game(illustrations_dir=None, voices_dir=None, start_in_menu=False)
        self.addCleanup(pygame.quit)
        view = game.global_view
        self.assertIsNone(game.doll_editor)
        self.assertNotIn(DRAW_INTENT, [button.intent for button in view.hud.menu])
        view.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_F2))
        game.sync_scenes()
        self.assertEqual(game.scene_name, "global")
        view.render()
        self.assertEqual(view._doll_draws, [])


if __name__ == "__main__":
    unittest.main()
