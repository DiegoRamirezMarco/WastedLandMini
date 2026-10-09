import math
import os
import unittest
from dataclasses import replace

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame

from graphics import volume
from graphics.doll import BODY_CANVAS, DOLL_FACINGS, Doll, doll_plan, load_template
from graphics.face import load_rules
from graphics.mannequin import figures, tones_of
from graphics import doll as doll_module
from graphics.turn import body_yaw, limbs_apart, turned_pose
from graphics.volume import fronted, half_width, solid_of, turned_body, wrapped
from skeleton.plan import FACINGS, builtin_plan
from skeleton.rig import Skeleton

SKIN = (214, 170, 130)
LINE = (30, 22, 20)
GREEN = (40, 200, 60, 255)


def painted(surface: pygame.Surface) -> int:
    return pygame.mask.from_surface(surface).count()


@unittest.skipUnless(volume.AVAILABLE, "a trunk is only wrapped with numpy")
class VolumeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        pygame.init()
        pygame.display.set_mode((1, 1))
        cls.rules = load_rules()
        cls.turn = cls.rules.body
        template = load_template()
        build = template.starting()
        cls.template = template.built(build)
        cls.plan = doll_plan(builtin_plan(), cls.template, build)
        cls.plain = figures(cls.template, tones_of(SKIN, LINE), 5)[BODY_CANVAS]
        cls.front = fronted(cls.template, cls.plain, cls.turn.trunk, cls.turn.depth)
        cls.doll = Doll(cls.template, {BODY_CANVAS: cls.front}, cls.plan)

    def width_of(self, doll: Doll, bone: str = "spine") -> int:
        return doll.parts[bone].image.get_bounding_rect().width

    def test_the_figure_to_draw_over_has_its_trunk_seen_from_the_front(self) -> None:
        side = Doll(self.template, {BODY_CANVAS: self.plain}, self.plan)
        # As much wider as a trunk is wider than deep, the same to either side, and no taller.
        self.assertAlmostEqual(self.width_of(self.doll) * self.turn.depth, self.width_of(side), delta=4)
        self.assertEqual(self.front.get_bounding_rect().height, self.plain.get_bounding_rect().height)
        part = self.doll.parts["spine"]
        box, middle = part.image.get_bounding_rect(), part.start[0]
        self.assertAlmostEqual(middle - box.left, box.right - middle, delta=2)
        # It is the colour it was, and nothing else of the figure has moved.
        self.assertEqual(tuple(self.front.get_at((round(self.template.parts["spine"].start[0]), round(self.template.parts["spine"].end[1]) + 30)))[:3], SKIN)
        for bone in ("upper_arm_right", "thigh_left", "foot_right"):
            self.assertEqual(side.parts[bone].image.get_size(), self.doll.parts[bone].image.get_size(), bone)

    def test_seen_from_the_front_a_trunk_is_the_drawing_itself(self) -> None:
        front = turned_body(self.doll, self.turn, 0.0, self.turn.depth)
        for bone in self.turn.trunk:
            self.assertIs(front.parts[bone], self.doll.parts[bone], bone)
        self.assertIs(wrapped(self.doll.parts["spine"], 0.0, self.turn.depth), self.doll.parts["spine"])

    def test_the_further_round_the_narrower_down_to_as_deep_as_it_is(self) -> None:
        widths = [self.width_of(turned_body(self.doll, self.turn, yaw, self.turn.depth)) for yaw in (0.0, 30.0, 60.0, 90.0)]
        self.assertEqual(widths, sorted(widths, reverse=True))
        self.assertGreater(widths[0], widths[-1])
        self.assertAlmostEqual(widths[-1], widths[0] * self.turn.depth, delta=4)
        # A deeper trunk is wider from the side, and no wider from the front.
        deep = self.width_of(turned_body(self.doll, self.turn, 90.0, 0.9))
        self.assertGreater(deep, widths[-1])
        # And it is no taller or shorter for having turned, nor are its joints anywhere else on it.
        turned = turned_body(self.doll, self.turn, 60.0, self.turn.depth).parts["spine"]
        before = self.doll.parts["spine"]
        self.assertEqual(turned.image.get_height(), before.image.get_height())
        self.assertEqual((turned.start[1], turned.end[1]), (before.start[1], before.end[1]))
        box = turned.image.get_bounding_rect()
        self.assertAlmostEqual(turned.start[0] - box.left, box.right - turned.start[0], delta=2)

    def test_what_is_drawn_on_the_chest_goes_round_to_the_front_edge(self) -> None:
        drawing = self.front.copy()
        spec = self.template.parts["spine"]
        chest = (round(spec.start[0]), round((spec.start[1] + spec.end[1]) / 2))
        pygame.draw.circle(drawing, GREEN, chest, 5)
        doll = Doll(self.template, {BODY_CANVAS: drawing}, self.plan)

        def mark(yaw: float) -> tuple[float, float] | None:
            part = turned_body(doll, self.turn, yaw, self.turn.depth).parts["spine"]
            # Edge on it is a sliver, part of each pixel it is in: greener than it is red, which
            # skin is not, and not green outright.
            found = pygame.Mask(part.image.get_size())
            for x in range(part.image.get_width()):
                for y in range(part.image.get_height()):
                    red, green, _, alpha = part.image.get_at((x, y))
                    if alpha > 100 and green > red + 25:
                        found.set_at((x, y))
            if not found.count():
                return None
            box, whole = found.get_bounding_rects()[0], part.image.get_bounding_rect()
            # How far across the trunk it is, from its back edge at 0 to its front edge at 1.
            return ((box.centerx - whole.left) / whole.width, box.width)

        middle, quarter, most, side = mark(0.0), mark(45.0), mark(70.0), mark(90.0)
        self.assertAlmostEqual(middle[0], 0.5, delta=0.05)
        self.assertGreater(quarter[0], middle[0] + 0.1)
        # Further round it is nearer the front edge and more edge on: there is less of it to see.
        self.assertGreater(most[0], quarter[0])
        self.assertLess(most[1], middle[1])
        # From the side it is on the very edge, under the line round the trunk or all but.
        self.assertTrue(side is None or side[0] > most[0])

    def test_the_line_round_a_trunk_is_round_it_however_it_is_turned(self) -> None:
        solid = solid_of(self.doll, self.turn.trunk)
        self.assertGreater(solid.line, 2)
        self.assertLess(sum(solid.ink), 150)
        for yaw in (30.0, 60.0, 90.0):
            part = turned_body(self.doll, self.turn, yaw, self.turn.depth).parts["spine"]
            row = part.image.get_height() // 2
            seen = [tuple(part.image.get_at((x, row))) for x in range(part.image.get_width())]
            seen = [color for color in seen if color[3] > 200]
            dark = [sum(color[:3]) < 150 for color in seen]
            # Line at either edge, and none between: the line it was drawn with has not come inside.
            self.assertTrue(dark[0] and dark[-1], yaw)
            runs = sum(1 for before, after in zip(dark, dark[1:]) if after and not before) + (1 if dark[0] else 0)
            self.assertEqual(runs, 2, (yaw, dark))

    def test_the_parts_of_a_trunk_go_round_as_one(self) -> None:
        # Laid over a skeleton, a trunk that has turned has no more of an edge inside it than one that has not.
        from graphics.doll import draw_doll
        from skeleton.rig import Skeleton

        facing = DOLL_FACINGS["right"]
        skeleton = Skeleton(self.plan, facing)
        skeleton.set_pose(self.plan.pose(facing))

        def lines_down_the_middle(yaw: float) -> int:
            """How many lines are crossed going down the middle of the trunk, laid over a skeleton."""
            turned = turned_body(self.doll, self.turn, yaw, self.turn.depth)
            only_trunk = Doll(self.template, {BODY_CANVAS: self.front}, self.plan)
            only_trunk.parts = {bone: turned.parts[bone] for bone in self.turn.trunk}
            only_trunk.limbs = {}
            picture = pygame.Surface((400, 400), pygame.SRCALPHA)
            draw_doll(picture, only_trunk, self.plan, skeleton, (200, 380), 16.0)
            box = picture.get_bounding_rect()
            column = [tuple(picture.get_at((box.centerx, y))) for y in range(box.top, box.bottom)]
            dark = [sum(color[:3]) < 150 for color in column if color[3] > 200]
            return sum(1 for before, after in zip(dark, dark[1:]) if after and not before) + (1 if dark[0] else 0)

        drawn = lines_down_the_middle(0.0)
        self.assertGreaterEqual(drawn, 2)
        for yaw in (30.0, 60.0):
            self.assertEqual(lines_down_the_middle(yaw), drawn, yaw)

    def test_a_trunk_is_of_rubber_and_does_not_come_apart_where_it_bends(self) -> None:
        from graphics.doll import BACKWARDS, draw_doll
        from skeleton.rig import Skeleton

        facing = DOLL_FACINGS["right"]
        for yaw in (0.0, 45.0, 90.0):
            turned = turned_body(self.doll, self.turn, yaw, self.turn.depth)
            limb = turned.limbs["spine"]
            self.assertIs(turned.limbs["hips"], limb)
            self.assertEqual(limb.bones, (f"hips{BACKWARDS}", "spine"))
            # Its joints are one over another, the foot of the hips lowest.
            self.assertEqual(len({x for x, _ in limb.joints}), 1)
            self.assertEqual(sorted((y for _, y in limb.joints), reverse=True), [y for _, y in limb.joints])
            # The arms and legs it had are the ones it has.
            self.assertIs(turned.limbs["upper_arm_right"], self.doll.limbs["upper_arm_right"])
            # Bent hard at the hips, as a blow bends it, the trunk alone is still all of a piece.
            only = Doll(self.template, {BODY_CANVAS: self.front}, self.plan)
            only.parts = {bone: turned.parts[bone] for bone in self.turn.rubber}
            only.limbs = {bone: limb for bone in self.turn.rubber}
            only.drawn = turned.drawn
            pose = dict(self.plan.pose(facing, "hammer", 0.0))
            skeleton = Skeleton(self.plan, facing)
            skeleton.set_pose(pose)
            self.assertGreater(abs(skeleton.bones["spine"].angle - math.pi), 0.2, "the clip does not bend the trunk")
            picture = pygame.Surface((500, 500), pygame.SRCALPHA)
            draw_doll(picture, only, self.plan, skeleton, (250, 460), 16.0)
            pieces = [box for box in pygame.mask.from_surface(picture).get_bounding_rects() if box.width * box.height > 30]
            self.assertEqual(len(pieces), 1, yaw)
            # And its hips and its trunk are both in it: it is as tall as the two of them.
            tall = (self.doll.drawn["hips"] + self.doll.drawn["spine"]) * 16.0
            self.assertGreater(pieces[0].height, tall * 0.85, yaw)

    def test_two_trunks_of_rubber_are_not_taken_for_each_other(self) -> None:
        one = turned_body(self.doll, self.turn, 30.0, self.turn.depth).limbs["spine"]
        other = turned_body(self.doll, self.turn, 60.0, self.turn.depth).limbs["spine"]
        self.assertEqual(one.bones, other.bones)
        self.assertNotEqual(one.mark, other.mark)
        self.assertNotEqual(one.image.get_size(), other.image.get_size())

    def test_limbs_hang_beside_the_trunk_they_are_of(self) -> None:
        apart = limbs_apart(self.turn, self.doll)
        self.assertEqual(apart["shoulder"], apart["hand"])
        self.assertGreater(apart["shoulder"], apart["hip"])
        self.assertLess(apart["shoulder"], half_width(self.doll, "spine"))
        # A wider trunk has its arms further out.
        wide = Doll(self.template, {BODY_CANVAS: fronted(self.template, self.plain, self.turn.trunk, 0.4)}, self.plan)
        self.assertGreater(limbs_apart(self.turn, wide)["shoulder"], apart["shoulder"])

    def test_limbs_are_moved_whole_and_only_as_far_as_the_body_has_turned(self) -> None:
        side = self.rules.side
        apart = limbs_apart(self.turn, self.doll)
        pose = self.plan.pose(DOLL_FACINGS["right"], "walk", 0.3)
        from_side = turned_pose(self.turn, apart, pose, side, side)
        for joint, (x, y) in pose.items():
            self.assertAlmostEqual(from_side[joint][0], x, msg=joint)
        front = turned_pose(self.turn, apart, pose, 0.0, side)
        # From the front its shoulders are the same way out from the middle of its chest, one
        # to either side, wherever ahead of the chest or behind it each was put for a body
        # seen from its side: and so are its hips from the middle of them.
        self.assertNotAlmostEqual(pose["shoulder_left"][0] - pose["chest"][0], -(pose["shoulder_right"][0] - pose["chest"][0]), places=2)
        # And they stand that much clear of the trunk, which they do not from three quarters on:
        # an arm hangs beside a trunk seen from the front, and not across the edge of it.
        shoulders, hips = apart["shoulder"] + apart["shoulder~clear"], apart["hip"] + apart["hip~clear"]
        self.assertGreater(apart["shoulder~clear"], 0.0)
        self.assertAlmostEqual(front["shoulder_left"][0] - front["chest"][0], shoulders)
        self.assertAlmostEqual(front["shoulder_right"][0] - front["chest"][0], -shoulders)
        self.assertAlmostEqual(front["hip_left"][0] - front["pelvis"][0], hips)
        self.assertAlmostEqual(front["hip_right"][0] - front["pelvis"][0], -hips)
        # Half way round, half way: no further out than from the front, no nearer than from the side.
        quarter = turned_pose(self.turn, apart, pose, 45.0, side)
        self.assertLess(quarter["shoulder_left"][0] - quarter["chest"][0], apart["shoulder"])
        self.assertGreater(quarter["shoulder_left"][0], quarter["shoulder_right"][0])
        # As far round as three quarters nothing of it but where its limbs begin has moved:
        # its trunk is where it was, and every bone of a limb as long and pointing as it did.
        limbs = [bone for bone in self.plan.bones.values() if bone.start.endswith(("_left", "_right"))]
        for joint in ("pelvis", "chest", "neck", "head"):
            self.assertEqual(quarter[joint], pose[joint], joint)
        for bone in limbs:
            was = (pose[bone.end][0] - pose[bone.start][0], pose[bone.end][1] - pose[bone.start][1])
            now = (quarter[bone.end][0] - quarter[bone.start][0], quarter[bone.end][1] - quarter[bone.start][1])
            self.assertLess(math.dist(was, now), 1e-9, bone.name)

    def test_nearer_the_front_what_a_body_does_is_seen_less_across_the_screen(self) -> None:
        side, least = self.rules.side, self.turn.least_swing
        self.assertTrue(0.0 < least < 1.0)
        apart = limbs_apart(self.turn, self.doll)
        pose = self.plan.pose(DOLL_FACINGS["right"], "walk", 0.3)
        front = turned_pose(self.turn, apart, pose, 0.0, side)
        # Seen from the front its trunk leans that much less across, about its hips, and each
        # bone of a limb goes that much less across and as far up or down as it did.
        self.assertEqual(front["pelvis"], pose["pelvis"])
        self.assertAlmostEqual(front["neck"][0] - front["pelvis"][0], (pose["neck"][0] - pose["pelvis"][0]) * least)
        # Its head goes with its neck, and is no more aslant than it was: it is one picture.
        self.assertAlmostEqual(front["head"][0] - front["neck"][0], pose["head"][0] - pose["neck"][0])
        self.assertEqual(front["head"][1], pose["head"][1])
        limbs = [bone for bone in self.plan.bones.values() if bone.start.endswith(("_left", "_right"))]
        narrowed = 0
        # That is with the ground seen from its side. Seen from above, what a limb does
        # towards whoever looks goes down the screen too (P76, `tests/test_front_walk.py`).
        level = turned_pose(replace(self.turn, tilt=0.0, sharpest=0.0), apart, pose, 0.0, side)
        for bone in limbs:
            was = (pose[bone.end][0] - pose[bone.start][0], pose[bone.end][1] - pose[bone.start][1])
            now = (level[bone.end][0] - level[bone.start][0], level[bone.end][1] - level[bone.start][1])
            self.assertAlmostEqual(now[1], was[1], msg=bone.name)
            # That much less across, or as much as leaves it the least of its length it may be seen at.
            self.assertGreaterEqual(abs(now[0]) + 1e-9, abs(was[0]) * least, bone.name)
            self.assertLessEqual(abs(now[0]), abs(was[0]) + 1e-9, bone.name)
            self.assertGreaterEqual(math.hypot(*now) + 1e-6, math.hypot(*was) * self.turn.least_long, bone.name)
            narrowed += abs(abs(now[0]) - abs(was[0]) * least) < 1e-9
        self.assertGreater(narrowed, len(limbs) // 2)
        # Between there and three quarters, between the two.
        between = turned_pose(self.turn, apart, pose, self.turn.nearest / 2, side)
        knee = lambda shown: abs(shown["knee_left"][0] - shown["hip_left"][0])
        self.assertTrue(knee(front) < knee(between) < knee(pose))

    def test_facing_left_it_is_the_same_body_in_a_mirror(self) -> None:
        side = self.rules.side
        apart = limbs_apart(self.turn, self.doll)
        right = self.plan.pose(DOLL_FACINGS["right"], "walk", 0.3)
        left = self.plan.pose(DOLL_FACINGS["left"], "walk", 0.3)
        _, _, mirrored, swapped = FACINGS[DOLL_FACINGS["left"]]
        seen_right = turned_pose(self.turn, apart, right, 30.0, side)
        seen_left = turned_pose(self.turn, apart, left, 30.0, side, mirrored, swapped)
        self.assertEqual(
            sorted((round(-x, 4), round(y, 4)) for x, y in seen_left.values()),
            sorted((round(x, 4), round(y, 4)) for x, y in seen_right.values()),
        )

    def test_a_body_that_is_at_something_is_never_turned_right_round_to_the_front(self) -> None:
        self.assertGreater(self.turn.nearest, 0.0)
        self.assertEqual(body_yaw(self.turn, 0.0), self.turn.nearest)
        self.assertEqual(body_yaw(self.turn, 0.0, standing=True), 0.0)
        self.assertEqual(body_yaw(self.turn, -70.0), 70.0)


    def test_seen_from_behind_a_trunk_has_a_plain_back_with_its_line_round_it(self) -> None:
        drawing = self.front.copy()
        spec = self.template.parts["spine"]
        chest = (round(spec.start[0]), round((spec.start[1] + spec.end[1]) / 2))
        pygame.draw.circle(drawing, GREEN, chest, 6)
        doll = Doll(self.template, {BODY_CANVAS: drawing}, self.plan)

        def greens(image: pygame.Surface) -> int:
            return sum(
                1 for x in range(image.get_width()) for y in range(image.get_height())
                if image.get_at((x, y))[3] > 100 and image.get_at((x, y))[1] > image.get_at((x, y))[0] + 25
            )

        front = turned_body(doll, self.turn, 0.0, self.turn.depth).parts["spine"]
        behind = turned_body(doll, self.turn, 180.0, self.turn.depth).parts["spine"]
        self.assertGreater(greens(front.image), 50)
        self.assertEqual(greens(behind.image), 0)
        # It is as large as from the front, the colour there is most of, and still has its line.
        self.assertEqual(behind.image.get_bounding_rect().size, front.image.get_bounding_rect().size)
        self.assertEqual(tuple(behind.image.get_at((round(behind.start[0]), round((behind.start[1] + behind.end[1]) / 2))))[:3], SKIN)
        self.assertEqual(volume.main_colour(drawing), SKIN)
        box = behind.image.get_bounding_rect()
        edge = tuple(behind.image.get_at((box.left + 2, box.centery)))
        self.assertLess(sum(edge[:3]), 200)
        # Part of the way round from behind it is as wide as it is as far round from the front.
        self.assertAlmostEqual(
            self.width_of(turned_body(doll, self.turn, 135.0, self.turn.depth)), self.width_of(turned_body(doll, self.turn, 45.0, self.turn.depth)), delta=2
        )
        self.assertEqual(greens(turned_body(doll, self.turn, 135.0, self.turn.depth).parts["spine"].image), 0)

    def test_a_back_that_is_drawn_is_what_is_seen_from_behind(self) -> None:
        back = pygame.Surface(self.front.get_size(), pygame.SRCALPHA)
        spec = self.template.parts["spine"]
        # A mark to one side of the middle of the back, as it is seen from behind.
        mark = (round(spec.start[0]) + 14, round((spec.start[1] + spec.end[1]) / 2))
        pygame.draw.circle(back, GREEN, mark, 5)

        def where(yaw: float) -> float | None:
            """How far across the trunk the mark is, from its left edge at 0 to its right at 1."""
            part = turned_body(self.doll, self.turn, yaw, self.turn.depth, back=back).parts["spine"]
            found = pygame.Mask(part.image.get_size())
            for x in range(part.image.get_width()):
                for y in range(part.image.get_height()):
                    red, green, _, alpha = part.image.get_at((x, y))
                    if alpha > 100 and green > red + 25:
                        found.set_at((x, y))
            if not found.count():
                return None
            whole = part.image.get_bounding_rect()
            return (found.get_bounding_rects()[0].centerx - whole.left) / whole.width

        self.assertIsNone(where(0.0))
        self.assertIsNone(where(60.0))
        behind = where(180.0)
        # From right behind it is where it was drawn, to the right of the middle.
        self.assertGreater(behind, 0.55)
        # A body that faces right and is seen from behind has turned its back to the left: the mark goes that way.
        self.assertLess(where(135.0), behind)

    def test_seen_from_behind_the_limbs_have_changed_sides(self) -> None:
        side = self.rules.side
        apart = limbs_apart(self.turn, self.doll)
        pose = self.plan.pose(DOLL_FACINGS["right"])
        front = turned_pose(self.turn, apart, pose, 0.0, side)
        behind = turned_pose(self.turn, apart, pose, 2 * side, side)
        for joint, hangs in (("shoulder", "chest"), ("hip", "pelvis")):
            for which in ("_left", "_right"):
                ahead = front[f"{joint}{which}"][0] - front[hangs][0]
                self.assertAlmostEqual(behind[f"{joint}{which}"][0] - behind[hangs][0], -ahead, msg=f"{joint}{which}")
        # And the body is no nearer its side than it was told, either way round.
        self.assertEqual(body_yaw(self.turn, 170.0), 180.0 - self.turn.nearest)
        self.assertEqual(body_yaw(self.turn, 170.0, standing=True), 170.0)


    def test_the_piece_under_the_hips_rides_on_them_and_is_laid_between_the_legs(self) -> None:
        spec = self.template.parts["briefs"]
        self.assertEqual(spec.rides, "hips")
        self.assertEqual(spec.start, self.template.parts["hips"].end)
        self.assertIn("briefs", self.turn.trunk)
        # Its zone is under that of the hips and above those of the legs, and is nobody else's.
        foot = max(y for _, y in spec.zone())
        self.assertLess(foot, min(y for _, y in self.template.parts["thigh_right"].zone()))
        self.assertLess(foot, min(y for _, y in self.template.parts["thigh_left"].zone()))
        drawing = self.front.copy()
        middle = (round(spec.start[0]), round((spec.start[1] + spec.end[1]) / 2 + 4))
        pygame.draw.circle(drawing, GREEN, middle, 5)
        doll = Doll(self.template, {BODY_CANVAS: drawing}, self.plan)

        def greens(image: pygame.Surface) -> int:
            return sum(
                1 for x in range(image.get_width()) for y in range(image.get_height())
                if image.get_at((x, y))[3] > 100 and image.get_at((x, y))[1] > image.get_at((x, y))[0] + 25
            )

        self.assertGreater(greens(doll.parts["briefs"].image), 50)
        facing = DOLL_FACINGS["right"]
        skeleton = Skeleton(self.plan, facing)
        skeleton.set_pose(self.plan.pose(facing))
        laid = list(doll_module._laid(doll, self.plan, skeleton, 16.0))
        # The hips keep a round end past the joint they end at, as every part does, and the mark
        # is under that too: the piece itself is laid after them, and is the last with it on.
        marked = [index for index, (image, _, _) in enumerate(laid) if greens(image)][-1:]
        self.assertEqual(len(marked), 1)
        # It hangs from where the hips end: the mark is just under that joint.
        image, x, y = laid[marked[0]]
        self.assertEqual(image.get_size(), doll.placed("briefs", False, 16.0, skeleton.bones["hips"].angle)[0].get_size())
        groin = skeleton.bones["hips"].b
        box = image.get_bounding_rect()
        self.assertAlmostEqual(x + box.centerx, (groin.x + 0.5) * 16.0, delta=4)
        self.assertLess(abs(y + box.centery - (groin.y + 0.5) * 16.0), 30)
        # After the far leg and before the near one, which is over it.
        legs = {name: next(i for i, (picture, _, _) in enumerate(laid) if picture is doll.hosed(name, False, 16.0, [doll_module._bone_of(skeleton, part) for part in doll.limbs[name].bones])[0][0]) for name in ("thigh_left", "thigh_right")}
        self.assertTrue(legs["thigh_left"] < marked[0] < legs["thigh_right"])
        # From behind it is the colour there is most of in it, whatever the rest of the back is.
        worn = self.front.copy()
        blue = pygame.Surface(worn.get_size(), pygame.SRCALPHA)
        blue.fill((60, 90, 200, 255))
        blue.blit(self.template.region("briefs"), (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
        blue.blit(pygame.mask.from_surface(worn).to_surface(setcolor=(255, 255, 255, 255), unsetcolor=(0, 0, 0, 0)), (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
        worn.blit(blue, (0, 0))
        behind = turned_body(Doll(self.template, {BODY_CANVAS: worn}, self.plan), self.turn, 180.0, self.turn.depth)
        its = behind.parts["briefs"]
        self.assertEqual(tuple(its.image.get_at((round(its.start[0]), round((its.start[1] + its.end[1]) / 2))))[:3], (60, 90, 200))
        chest = behind.parts["spine"]
        self.assertEqual(tuple(chest.image.get_at((round(chest.start[0]), round((chest.start[1] + chest.end[1]) / 2))))[:3], SKIN)
        # It goes round with the trunk, and from behind it is plain like the rest of the back.
        self.assertLess(self.width_of(turned_body(doll, self.turn, 90.0, self.turn.depth), "briefs"), self.width_of(doll, "briefs"))
        self.assertEqual(greens(turned_body(doll, self.turn, 180.0, self.turn.depth).parts["briefs"].image), 0)

    def test_a_drawing_on_the_paper_as_it_was_is_put_where_its_parts_go_now(self) -> None:
        was = next(former for former in self.template.formers if former.canvases[BODY_CANVAS] == (400, 384))
        build = self.template.starting()
        old = pygame.Surface(was.canvases[BODY_CANVAS], pygame.SRCALPHA)
        thigh = was.built(build).parts["thigh_right"]
        spot = (round(thigh.start[0]), round((thigh.start[1] + thigh.end[1]) / 2))
        pygame.draw.circle(old, GREEN, spot, 6)
        trunk = was.built(build).parts["spine"]
        chest = (round(trunk.start[0]), round((trunk.start[1] + trunk.end[1]) / 2))
        pygame.draw.circle(old, (200, 30, 30, 255), chest, 6)
        base = load_template()
        new = base.adopted(BODY_CANVAS, old, build)
        self.assertEqual(new.get_size(), base.canvases[BODY_CANVAS])
        # The leg has gone down with its zone, by as much as the paper is taller: the trunk has not moved.
        now = self.template.parts["thigh_right"]
        down = round(now.start[1] - thigh.start[1])
        self.assertGreater(down, 10)
        self.assertEqual(tuple(new.get_at((spot[0], spot[1] + down))), GREEN)
        self.assertEqual(new.get_at(spot)[3], 0)
        self.assertEqual(tuple(new.get_at(chest))[:3], (200, 30, 30))
        # And nothing of it is in the zone of the piece there was not.
        doll = Doll(self.template, {BODY_CANVAS: new}, self.plan)
        self.assertNotIn("briefs", doll.parts)


    def test_only_so_many_of_a_crowd_are_turned_a_new_way_in_a_frame(self) -> None:
        from graphics.turn import Turned

        made = []

        def make(yaw: float) -> Doll:
            made.append(yaw)
            return turned_body(self.doll, self.turn, yaw, self.turn.depth)

        turned = Turned(a_frame=1)
        # One that has not been turned any way is turned, whatever is left of the frame.
        first = turned.seen("one", 90.0, make)
        other = turned.seen("other", 90.0, make)
        self.assertEqual(made, [90.0, 90.0])
        self.assertIsNot(first, other)
        # No more in this frame: it is shown the nearest way it has been turned.
        self.assertIs(turned.seen("one", 45.0, make), first)
        self.assertEqual(len(made), 2)
        turned.new_frame()
        quarter = turned.seen("one", 45.0, make)
        self.assertIsNot(quarter, first)
        self.assertIs(turned.seen("one", 30.0, make), quarter)
        self.assertIs(turned.seen("one", 80.0, make), first)
        self.assertEqual(made, [90.0, 90.0, 45.0])
        # What it has been turned to is kept, frame after frame, until it is told to forget it.
        turned.new_frame()
        self.assertIs(turned.seen("one", 45.0, make), quarter)
        self.assertEqual(len(made), 3)
        turned.forget("one")
        self.assertIsNot(turned.seen("one", 45.0, make), quarter)


    def test_the_colour_of_a_dark_body_is_told_though_it_is_as_dark_as_a_line(self) -> None:
        dark = (101, 49, 31)
        body = pygame.Surface((80, 80), pygame.SRCALPHA)
        pygame.draw.rect(body, (*dark, 255), pygame.Rect(10, 10, 60, 60))
        pygame.draw.rect(body, (*LINE, 255), pygame.Rect(10, 10, 60, 60), 4)
        self.assertEqual(volume.main_colour(body), dark)
        pygame.draw.rect(body, (*SKIN, 255), pygame.Rect(20, 20, 10, 10))
        self.assertEqual(volume.main_colour(body), dark)
        self.assertEqual(tuple(volume.plain_back(body, 6).get_at((25, 25)))[:3], dark)


if __name__ == "__main__":
    unittest.main()
