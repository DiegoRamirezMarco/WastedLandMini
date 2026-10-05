import math
import random
import sys
import unittest

from simulation.registries import builtin_registries
from skeleton import physics
from skeleton.character import RISE_SECONDS, STAGGER_SECONDS, Character, Mode
from skeleton.plan import FACINGS, builtin_plan, other_side, plan_from_data
from skeleton.rig import Skeleton

FRAME = 1 / 60


def _length(bone) -> float:
    return math.dist((bone.a.x, bone.a.y), (bone.b.x, bone.b.y))


def _turned(limit) -> float:
    """How far a limited bone is turned against the other one, in radians."""
    bone, ref = limit.bone, limit.ref
    rx, ry = ref.b.x - ref.a.x, ref.b.y - ref.a.y
    if limit.ref_reversed:
        rx, ry = -rx, -ry
    angle = math.atan2(bone.b.x - bone.a.x, bone.b.y - bone.a.y) - math.atan2(rx, ry)
    return (angle + math.pi) % math.tau - math.pi


def _settle(skeleton: Skeleton, seconds: float = 10.0) -> int:
    steps = 0
    for _ in range(int(seconds / FRAME)):
        steps += physics.advance(skeleton, FRAME)
    return steps


class PlanTests(unittest.TestCase):
    def setUp(self) -> None:
        self.plan = builtin_plan()

    def test_the_package_needs_neither_pygame_nor_the_simulation(self) -> None:
        import skeleton.character  # noqa: F401

        for module in ("skeleton.plan", "skeleton.rig", "skeleton.physics", "skeleton.character"):
            imported = set(vars(sys.modules[module]))
            self.assertFalse(imported & {"pygame", "simulation", "world", "scenes", "graphics"}, module)

    def test_every_joint_the_brief_asks_for_is_joined_to_the_body(self) -> None:
        joints = self.plan.joints.keys()
        for name in ("head", "neck", "chest", "pelvis"):
            self.assertIn(name, joints)
        for name in ("shoulder", "elbow", "hand", "knee", "foot"):
            for side in ("_left", "_right"):
                self.assertIn(name + side, joints)
        reached = {self.plan.root} | {bone.end for bone in self.plan.bones.values()}
        self.assertEqual(reached, set(joints))

    def test_every_limb_the_simulation_can_take_is_a_part_of_the_body(self) -> None:
        self.assertTrue(builtin_registries().limbs)
        self.assertLessEqual(builtin_registries().limbs.keys(), self.plan.parts.keys())

    def test_a_pose_keeps_every_bone_its_length_unless_a_clip_foreshortens_it(self) -> None:
        for facing, (view, _, _, _) in FACINGS.items():
            pose = self.plan.pose(facing, "walk", 0.3)
            frame = self.plan.sample("walk", view, 0.3)
            for bone in self.plan.bones.values():
                name = other_side(bone.name) if FACINGS[facing][3] else bone.name
                start, end = (other_side(j) if FACINGS[facing][3] else j for j in (bone.start, bone.end))
                scale = frame.bones.get(bone.name, (0.0, 1.0))[1]
                self.assertAlmostEqual(
                    math.dist(pose[start], pose[end]), self.plan.length(view, bone.name) * scale, 6, (facing, name)
                )

    def test_facing_left_is_facing_right_in_a_mirror_with_the_sides_swapped(self) -> None:
        right, left = self.plan.pose("right", "walk", 0.1), self.plan.pose("left", "walk", 0.1)
        for joint, (x, y) in right.items():
            self.assertAlmostEqual(left[other_side(joint)][0], -x, 6, joint)
            self.assertAlmostEqual(left[other_side(joint)][1], y, 6, joint)

    def test_seen_from_behind_a_body_keeps_its_left_on_its_left(self) -> None:
        front, back = self.plan.pose("down"), self.plan.pose("up")
        self.assertGreater(front["hand_left"][0], 0, "facing the viewer, its left is on the right of the screen")
        self.assertLess(back["hand_left"][0], 0)
        self.assertEqual(back["hand_left"], (-front["hand_left"][0], front["hand_left"][1]))

    def test_an_overlay_only_moves_the_bones_it_names(self) -> None:
        plain, carrying = self.plan.pose("right", "walk", 0.2), self.plan.pose("right", "walk", 0.2, "carry")
        self.assertNotEqual(plain["hand_right"], carrying["hand_right"])
        self.assertEqual(plain["foot_right"], carrying["foot_right"])

    def test_eating_lifts_the_held_item_anchor_towards_the_mouth(self) -> None:
        low = self.plan.pose("right", "eat", 0.0)
        bite = self.plan.pose("right", "eat", 0.5)
        mouth = self.plan.anchor("mouth", "right", bite)
        low_hand = self.plan.anchor("held_item", "right", low)
        bite_hand = self.plan.anchor("held_item", "right", bite)
        self.assertIsNotNone(mouth)
        self.assertIsNotNone(low_hand)
        self.assertIsNotNone(bite_hand)
        self.assertLess(math.dist(bite_hand, mouth), math.dist(low_hand, mouth))

    def test_semantic_anchors_follow_the_near_hand_when_the_body_is_mirrored(self) -> None:
        right = self.plan.pose("right", "eat", 0.5)
        left = self.plan.pose("left", "eat", 0.5)
        right_hand = self.plan.anchor("held_item", "right", right)
        left_hand = self.plan.anchor("held_item", "left", left)
        self.assertAlmostEqual(left_hand[0], -right_hand[0])
        self.assertAlmostEqual(left_hand[1], right_hand[1])

    def test_an_unknown_clip_stands_still_and_bad_data_is_refused(self) -> None:
        self.assertEqual(self.plan.pose("down", "moonwalk", 0.4), self.plan.pose("down"))
        data = {
            "root": "a",
            "joints": {"a": {}, "b": {}},
            "bones": {"ab": ["b", "a"]},
            "views": {view: {"rest": {"a": [0, 0], "b": [0, -1]}} for view in ("front", "side")},
            "orders": {view: [] for view in ("front", "side", "back")},
        }
        with self.assertRaises(ValueError):
            plan_from_data(data)


class SkeletonTests(unittest.TestCase):
    def setUp(self) -> None:
        self.plan = builtin_plan()

    def test_cutting_a_bone_takes_everything_beyond_it_and_nothing_else(self) -> None:
        body = Skeleton(self.plan, "down")
        upper_arm, forearm = body.bones["upper_arm_left"], body.bones["forearm_left"]
        before = set(body.bones)
        arm = body.sever("upper_arm_left")
        self.assertEqual(set(arm.bones), {"upper_arm_left", "forearm_left", "hand_left"})
        self.assertEqual(set(body.bones), before - {"upper_arm_left", "forearm_left", "hand_left"})
        # The very same bones and joints, not copies of them.
        self.assertIs(arm.bones["upper_arm_left"], upper_arm)
        self.assertIs(arm.bones["forearm_left"], forearm)
        self.assertIs(arm.joints["hand_left"], forearm.b)
        self.assertNotIn("hand_left", body.joints)
        # The shoulder stays on the body, and the arm keeps an end of its own where it was cut.
        self.assertIn("shoulder_left", body.joints)
        self.assertIsNot(arm.joints["shoulder_left"], body.joints["shoulder_left"])
        for skeleton in (body, arm):
            joints = {id(joint) for joint in skeleton.joints.values()}
            for held in (*skeleton.bones.values(), *skeleton.braces, *skeleton.spacers):
                self.assertLessEqual({id(held.a), id(held.b)}, joints, held.name)
            for limit in skeleton.limits:
                self.assertIn(limit.bone.name, skeleton.bones)
                self.assertIn(limit.ref.name, skeleton.bones)
        self.assertIsNone(body.sever("upper_arm_left"))

    def test_a_piece_falls_by_itself_while_the_body_stays_where_it_is(self) -> None:
        body = Skeleton(self.plan, "right")
        body.set_pose(self.plan.pose("right"), 50, 100)
        chest = (body.joints["chest"].x, body.joints["chest"].y)
        leg = body.sever("thigh_right")
        leg.ground = 140
        leg.spin(4.0)
        _settle(leg)
        self.assertTrue(leg.asleep)
        for joint in leg.joints.values():
            # On the ground, but for a toe that the ankle will not let lie quite flat.
            self.assertLessEqual(joint.y, 140 - joint.radius + 0.01)
            self.assertGreater(joint.y, 140 - joint.radius - 1.5)
        self.assertEqual((body.joints["chest"].x, body.joints["chest"].y), chest)

    def test_a_skeleton_can_be_built_already_short_of_parts(self) -> None:
        body = Skeleton(self.plan, "left", ["arm_right", "shin_left", "wings"])
        self.assertNotIn("forearm_right", body.bones)
        self.assertNotIn("shin_left", body.bones)
        self.assertIn("thigh_left", body.bones)


class PhysicsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.plan = builtin_plan()

    def _limp(self, facing: str, clip: str = "walk", phase: float = 0.3) -> Skeleton:
        character = Character(self.plan)
        character.stand(200, 100, facing, clip, phase)
        return character.kill()

    def test_a_limp_body_falls_to_the_ground_and_goes_to_sleep(self) -> None:
        for facing in FACINGS:
            body = self._limp(facing)
            top = body.bounds()[1]
            _settle(body)
            self.assertTrue(body.asleep, facing)
            self.assertGreater(body.bounds()[1], top + 5, f"{facing}: it should have gone down")
            for joint in body.joints.values():
                self.assertLessEqual(joint.y, 100 - joint.radius + 1e-6, (facing, joint.name))
            for bone in body.bones.values():
                self.assertAlmostEqual(_length(bone), bone.length, delta=1.5, msg=(facing, bone.name))

    def test_a_sleeping_body_takes_no_more_steps_until_something_wakes_it(self) -> None:
        body = self._limp("right")
        _settle(body)
        self.assertEqual(physics.advance(body, 1.0), 0)
        resting = [(joint.x, joint.y) for joint in body.joints.values()]
        body.push("head", 0, -120)
        self.assertGreater(physics.advance(body, FRAME * 3), 0)
        self.assertNotEqual(resting, [(joint.x, joint.y) for joint in body.joints.values()])

    def test_however_restless_a_body_is_left_alone_after_a_while(self) -> None:
        body = self._limp("down")
        steps = _settle(body, self.plan.physics.rest_after + 1.0)
        self.assertTrue(body.asleep)
        self.assertLessEqual(steps, round(self.plan.physics.rest_after / self.plan.physics.step) + 1)

    def test_a_long_stall_is_not_caught_up_with(self) -> None:
        body = self._limp("down")
        self.assertEqual(physics.advance(body, 5.0), self.plan.physics.max_steps)

    def test_a_blow_moves_the_joint_it_lands_on_and_the_bones_pass_it_on(self) -> None:
        body = self._limp("down", "idle")
        body.ground = 1e6
        start = {name: joint.x for name, joint in body.joints.items()}
        body.push("head", 200, 0)
        physics.step(body, self.plan.physics)
        moved = {name: joint.x - start[name] for name, joint in body.joints.items()}
        self.assertGreater(moved["head"], moved["foot_left"])
        for _ in range(20):
            physics.step(body, self.plan.physics)
        self.assertGreater(body.joints["chest"].x, start["chest"])

    def test_knees_and_elbows_do_not_bend_the_wrong_way(self) -> None:
        rng = random.Random(5)
        hinges = ("shin_left", "shin_right", "forearm_left", "forearm_right")
        for _ in range(25):
            body = self._limp(rng.choice(("left", "right")), "walk", rng.random())
            # Nothing to land on: only the joints themselves can stop a limb.
            body.ground = 1e6
            for name in rng.sample(sorted(body.joints), 3):
                body.push(name, rng.uniform(-60, 60), rng.uniform(-60, 60))
            for step in range(150):
                physics.step(body, self.plan.physics)
                # A limb may whip past its limit for an instant; it must not stay there.
                if step < 60:
                    continue
                for limit in body.limits:
                    if limit.bone.name in hinges:
                        over = max(limit.low - _turned(limit), _turned(limit) - limit.high)
                        self.assertLess(math.degrees(over), 20, limit.bone.name)

    def test_a_limb_never_folds_flat_on_itself(self) -> None:
        rng = random.Random(9)
        for _ in range(20):
            body = self._limp(rng.choice(sorted(FACINGS)), "walk", rng.random())
            body.push(rng.choice(sorted(body.joints)), rng.uniform(-200, 200), rng.uniform(-200, 50))
            _settle(body)
            for spacer in body.spacers:
                self.assertGreater(_length(spacer), spacer.length - 0.75, spacer.name)

    def test_the_same_blows_always_end_the_same_way(self) -> None:
        def run() -> list[tuple[float, float]]:
            body = self._limp("left")
            body.push("head", -90, -60)
            _settle(body)
            return [(joint.x, joint.y) for joint in body.joints.values()]

        self.assertEqual(run(), run())


class CharacterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.plan = builtin_plan()
        self.character = Character(self.plan)
        self.character.stand(100, 80, "right", "walk", 0.25)

    def test_a_body_going_about_its_business_has_no_skeleton_to_work_out(self) -> None:
        self.assertIs(self.character.mode, Mode.POSED)
        self.assertIsNone(self.character.skeleton)
        self.character.update(1.0)
        self.assertIsNone(self.character.skeleton)
        self.assertTrue(self.character.at_rest)
        self.assertFalse(self.character.physical)

    def test_a_blow_staggers_a_body_which_then_steadies_itself(self) -> None:
        self.character.hit(150, -60, "head")
        self.assertIs(self.character.mode, Mode.STAGGER)
        head = self.character.pose()["head"]
        self.character.update(FRAME * 4)
        thrown = self.character.skeleton.joints["head"]
        self.assertGreater(thrown.x, head[0] + 0.5)
        for _ in range(int(STAGGER_SECONDS / FRAME) + 2):
            self.character.update(FRAME)
        self.assertIs(self.character.mode, Mode.POSED)
        self.assertIsNone(self.character.skeleton)

    def test_someone_knocked_down_lies_there_and_then_gets_up(self) -> None:
        self.character.knock_down(120, -40, seconds=1.0)
        self.assertIs(self.character.mode, Mode.RAGDOLL)
        for _ in range(55):
            self.character.update(FRAME)
        self.assertIs(self.character.mode, Mode.RAGDOLL)
        self.assertGreater(self.character.skeleton.joints["head"].y, self.character.pose()["head"][1] + 5)
        for _ in range(8):
            self.character.update(FRAME)
        self.assertIs(self.character.mode, Mode.STAGGER)
        for _ in range(int(RISE_SECONDS / FRAME) + 2):
            self.character.update(FRAME)
        self.assertIs(self.character.mode, Mode.POSED)

    def test_the_dead_do_not_get_up(self) -> None:
        body = self.character.kill(60, -30)
        for _ in range(600):
            self.character.update(FRAME)
        self.assertIs(self.character.mode, Mode.RAGDOLL)
        self.assertFalse(self.character.alive)
        self.assertTrue(body.asleep and self.character.at_rest)

    def test_a_part_comes_off_as_a_body_of_its_own_and_is_gone_for_good(self) -> None:
        part = self.character.sever("arm_left", 80, -90, spin=5.0)
        self.assertEqual(part.part_id, "arm_left")
        self.assertEqual(set(part.skeleton.bones), {"upper_arm_left", "forearm_left", "hand_left"})
        self.assertNotIn("upper_arm_left", self.character.skeleton.bones)
        self.assertEqual(self.character.lost, ["arm_left"])
        self.assertFalse(self.character.has("arm_left"))
        self.assertFalse(self.character.has("forearm_left"), "it went with the arm")
        self.assertTrue(self.character.has("arm_right"))
        self.assertIsNone(self.character.sever("arm_left"))
        self.assertIsNone(self.character.sever("forearm_left"))
        self.assertIsNone(self.character.sever("tail"))
        for _ in range(600):
            part.update(FRAME)
            self.character.update(FRAME)
        self.assertTrue(part.at_rest)
        # The body steadied itself and still has no left arm, whichever way it turns.
        self.assertIs(self.character.mode, Mode.POSED)
        self.character.stand(100, 80, "down")
        self.character.hit(10, 0)
        self.assertNotIn("forearm_left", self.character.skeleton.bones)
        self.assertIn("forearm_right", self.character.skeleton.bones)

    def test_losing_one_part_leaves_the_rest_of_the_body_whole(self) -> None:
        whole = set(Skeleton(self.plan, "right").bones)
        self.character.sever("leg_right")
        self.character.sever("forearm_left")
        gone = {"thigh_right", "shin_right", "foot_right", "forearm_left", "hand_left"}
        self.assertEqual(set(self.character.skeleton.bones), whole - gone)

    def test_a_body_made_without_a_part_never_had_it(self) -> None:
        character = Character(self.plan, ["leg_left", "horn"])
        self.assertEqual(character.lost, ["leg_left"])
        self.assertNotIn("thigh_left", character.kill().bones)


if __name__ == "__main__":
    unittest.main()
