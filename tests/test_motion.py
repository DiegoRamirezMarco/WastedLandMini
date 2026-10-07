import math
import unittest
from dataclasses import replace

from skeleton.character import Character
from skeleton.motion import Motion
from skeleton.plan import FACINGS, Keyframe, MotionSettings, Spring, added, builtin_plan, plan_from_data


def _still(plan, clip: str = "idle", phase: float = 0.0) -> Keyframe:
    return plan.turned("side", clip, phase)


class ClipSamplingTests(unittest.TestCase):
    """A clip goes from key to key in a curve, and may say when each key comes."""

    def setUp(self) -> None:
        self.plan = builtin_plan()

    def _plan(self, frames: list[dict], **more) -> object:
        data = {
            "root": "a",
            "joints": {"a": {}, "b": {}, "c": {}},
            "bones": {"ab": ["a", "b"], "bc": ["b", "c"]},
            "views": {view: {"rest": {"a": [0, -4], "b": [0, -2], "c": [0, 0]}} for view in ("front", "side")},
            "orders": {"front": [], "side": [], "back": []},
            "clips": {"idle": {}, "swing": {"side": frames, "front": frames, **more}},
        }
        return plan_from_data(data)

    def test_a_clip_passes_through_its_keys_and_does_not_turn_a_corner_at_them(self) -> None:
        plan = self._plan([{"ab": 0}, {"ab": 40}, {"ab": 0}, {"ab": -40}])
        angle = lambda phase: math.degrees(plan.sample("swing", "side", phase).bones["ab"][0])
        for index, want in enumerate((0, 40, 0, -40)):
            self.assertAlmostEqual(angle(index / 4), want, 6)
        self.assertAlmostEqual(angle(1.0), 0.0, 6, "it comes round to where it began")
        # Going into a key and coming out of it, it is moving at the same speed: no corner.
        tiny = 1e-4
        for key in (0.0, 0.25, 0.5, 0.75):
            before = (angle(key) - angle(key - tiny)) / tiny
            after = (angle(key + tiny) - angle(key)) / tiny
            self.assertAlmostEqual(before, after, delta=abs(before) * 0.01 + 0.5, msg=key)
        # At the top of the swing it has stopped, where a straight line would still be going.
        self.assertAlmostEqual((angle(0.25 + tiny) - angle(0.25)) / tiny, 0.0, delta=0.5)
        self.assertGreater(angle(0.125), 20.0, "and half-way there it is more than half-way up")

    def test_a_key_can_say_when_it_comes(self) -> None:
        plan = self._plan([{"at": 0, "ab": 0}, {"at": 0.7, "ab": 0}, {"at": 0.8, "ab": 60}, {"at": 0.9, "ab": 0}])
        angle = lambda phase: math.degrees(plan.sample("swing", "side", phase).bones["ab"][0])
        self.assertAlmostEqual(angle(0.8), 60, 6)
        self.assertAlmostEqual(angle(0.7), 0, 6)
        self.assertLess(abs(angle(0.35)), 12, "held back for most of the clip")
        self.assertGreater(angle(0.76), 25, "and let go all at once")
        for frames in (
            [{"at": 0, "ab": 0}, {"ab": 5}],
            [{"at": 0.5, "ab": 0}, {"at": 0.2, "ab": 5}],
            [{"at": 0, "ab": 0}, {"at": 1.2, "ab": 5}],
        ):
            with self.assertRaises(ValueError, msg=frames):
                self._plan(frames)

    def test_a_clip_done_once_starts_and_ends_at_rest_and_does_not_come_round(self) -> None:
        plan = self._plan([{}, {"ab": 50}, {}], once=True)
        angle = lambda phase: math.degrees(plan.sample("swing", "side", phase).bones.get("ab", (0.0, 1.0))[0])
        self.assertIn("swing", plan.once)
        self.assertAlmostEqual(angle(0.0), 0, 6)
        self.assertAlmostEqual(angle(0.5), 50, 6)
        self.assertAlmostEqual(angle(1.0), 0, 6)
        self.assertAlmostEqual(angle(1.7), 0, 6, "past its end it stays as it ended")
        self.assertAlmostEqual(angle(-0.3), 0, 6)
        self.assertAlmostEqual(angle(0.001), 0, delta=0.05, msg="it sets off gently")

    def test_a_pose_is_its_bones_turned_and_then_put_in_place(self) -> None:
        for facing, (view, _, _, _) in FACINGS.items():
            turned = self.plan.turned(view, "walk", 0.3, "carry")
            self.assertEqual(self.plan.place(facing, turned), self.plan.pose(facing, "walk", 0.3, "carry"), facing)
        whole = self.plan.every_bone(self.plan.turned("side", "carry", 0.0))
        self.assertEqual(set(whole), set(self.plan.bones))
        for hand, arm in self.plan.follows.items():
            self.assertEqual(whole[hand][0], whole[arm][0], "a hand turns as its forearm does")

    def test_one_pose_laid_over_another_adds_its_turns_and_its_way(self) -> None:
        base = Keyframe((1.0, 2.0), {"spine": (0.2, 1.0), "skull": (0.1, 1.1)})
        layer = Keyframe((0.0, -0.5), {"spine": (0.1, 1.2)})
        both = added(base, layer)
        self.assertEqual(both.root, (1.0, 1.5))
        self.assertAlmostEqual(both.bones["spine"][0], 0.3)
        self.assertAlmostEqual(both.bones["spine"][1], 1.2)
        self.assertEqual(both.bones["skull"], (0.1, 1.1))
        half = added(base, layer, 0.5)
        self.assertAlmostEqual(half.bones["spine"][0], 0.25)
        self.assertAlmostEqual(half.bones["spine"][1], 1.1)
        self.assertEqual(half.root, (1.0, 1.75))


class FootingTests(unittest.TestCase):
    """A foot that is on the ground stays on it while the body above it sinks, rises and lunges."""

    def setUp(self) -> None:
        self.plan = builtin_plan()
        self.rest = self.plan.pose("doll_right")
        self.ground = self.rest["foot_right"][1]

    def _leg(self, pose: dict) -> float:
        return math.dist(pose["hip_right"], pose["knee_right"]) + math.dist(pose["knee_right"], pose["foot_right"])

    def test_the_body_sinks_over_its_feet_and_the_knees_give_to_the_front(self) -> None:
        sunk = self.plan.place("doll_right", Keyframe((0.0, 1.2), {}))
        self.assertAlmostEqual(sunk["pelvis"][1], self.rest["pelvis"][1] + 1.2, 6)
        for side in ("left", "right"):
            for joint in (f"foot_{side}", f"toe_{side}"):
                self.assertAlmostEqual(sunk[joint][0], self.rest[joint][0], 6, joint)
                self.assertAlmostEqual(sunk[joint][1], self.rest[joint][1], 6, joint)
            self.assertGreater(sunk[f"knee_{side}"][0], self.rest[f"knee_{side}"][0] + 1.0, "the knee goes forward")
        self.assertAlmostEqual(self._leg(sunk), self._leg(self.rest), 6, "and the leg is as long as it was")
        # Facing the other way it is the same in a mirror.
        left = self.plan.place("doll_left", Keyframe((0.0, 1.2), {}))
        self.assertAlmostEqual(left["knee_left"][0], -sunk["knee_right"][0], 6)
        self.assertAlmostEqual(left["foot_left"][1], self.ground, 6)

    def test_the_body_rises_and_lunges_and_its_legs_are_drawn_out_so_far_and_no_further(self) -> None:
        stretch = self.plan.footing.stretch
        risen = self.plan.place("doll_right", Keyframe((0.0, -0.5), {}))
        self.assertAlmostEqual(risen["foot_right"][1], self.ground, 6, "the foot is still down")
        self.assertGreater(self._leg(risen), self._leg(self.rest) + 0.4)
        self.assertLessEqual(self._leg(risen), self._leg(self.rest) * stretch + 1e-6)
        leapt = self.plan.place("doll_right", Keyframe((0.0, -3.0), {}))
        self.assertLess(leapt["foot_right"][1], self.ground - 1.0, "risen too far, the feet leave the ground")
        self.assertAlmostEqual(self._leg(leapt), self._leg(self.rest) * stretch, 6)
        lunged = self.plan.place("doll_right", Keyframe((1.5, 0.6), {}))
        self.assertAlmostEqual(lunged["pelvis"][0], self.rest["pelvis"][0] + 1.5, 6)
        self.assertAlmostEqual(lunged["foot_right"][0], self.rest["foot_right"][0], 6, "the body goes forward over its feet")
        self.assertAlmostEqual(lunged["foot_right"][1], self.ground, 6)

    def test_a_lifted_foot_goes_with_the_body_and_no_foot_goes_under_the_ground(self) -> None:
        lifted = {"thigh_left": (math.radians(50), 1.0), "shin_left": (math.radians(-60), 1.0)}
        still = self.plan.place("doll_right", Keyframe((0.0, 0.0), lifted))
        sunk = self.plan.place("doll_right", Keyframe((0.0, 0.8), lifted))
        self.assertLess(still["foot_left"][1], self.ground - 1.5, "it is well off the ground")
        self.assertAlmostEqual(sunk["foot_left"][1], still["foot_left"][1] + 0.8, 6, "and goes down with the body")
        self.assertAlmostEqual(sunk["foot_right"][1], self.ground, 6, "while the other stays where it stands")
        long = self.plan.place("doll_right", Keyframe((0.0, 0.0), {"shin_right": (0.0, 1.3)}))
        self.assertAlmostEqual(long["foot_right"][1], self.ground, 6, "a leg too long for where it stands bends")

    def test_the_small_bodies_of_the_game_bob_whole_and_which_legs_stand_is_data(self) -> None:
        self.assertEqual(self.plan.footing.views, frozenset({"doll"}))
        self.assertEqual(set(self.plan.footing.legs), {("thigh_left", "shin_left"), ("thigh_right", "shin_right")})
        still, sunk = self.plan.place("right", Keyframe()), self.plan.place("right", Keyframe((0.0, 1.0), {}))
        self.assertAlmostEqual(sunk["foot_right"][1], still["foot_right"][1] + 1.0, 6)
        data = {
            "root": "a",
            "joints": {"a": {}, "b": {}, "c": {}},
            "bones": {"ab": ["a", "b"], "bc": ["b", "c"]},
            "views": {view: {"rest": {"a": [0, -4], "b": [0, -2], "c": [0, 0]}} for view in ("front", "side")},
            "orders": {"front": [], "side": [], "back": []},
        }
        made = plan_from_data({**data, "footing": {"views": ["side"], "legs": [["ab", "bc"]], "stretch": 1.5}})
        self.assertAlmostEqual(made.place("right", Keyframe((0.0, 1.0), {}))["c"][1], 0.0, 6)
        self.assertEqual(plan_from_data(data).footing.legs, ())
        for footing in (
            {"views": ["nowhere"], "legs": [["ab", "bc"]]},
            {"views": ["side"], "legs": [["bc", "ab"]]},
            {"views": ["side"], "legs": [["ab", "zz"]]},
            {"views": ["side"], "legs": [["ab", "bc"]], "stretch": 0.5},
        ):
            with self.assertRaises(ValueError, msg=footing):
                plan_from_data({**data, "footing": footing})


class MotionTests(unittest.TestCase):
    """Bones are drawn towards where a clip has them, and get there late and go a little past."""

    def setUp(self) -> None:
        self.plan = builtin_plan()

    def _run(self, motion: Motion, plan, target: Keyframe, seconds: float, frame: float = 1 / 60, doing=None) -> list[Keyframe]:
        seen = []
        for _ in range(round(seconds / frame)):
            motion.follow(plan, target, frame, doing)
            seen.append(motion.keyframe())
        return seen

    def test_the_first_time_a_body_is_simply_where_its_pose_has_it(self) -> None:
        motion = Motion()
        self.assertFalse(motion.started)
        target = self.plan.turned("side", "walk", 0.1)
        motion.follow(self.plan, target, 1 / 60)
        self.assertTrue(motion.started)
        self.assertEqual(motion.keyframe().root, target.root)
        self.assertEqual(motion.keyframe().bones, self.plan.every_bone(target))
        self.assertTrue(motion.at_rest())

    def test_a_bone_gets_where_it_is_going_late_and_goes_a_little_past(self) -> None:
        plan = replace(self.plan, motion=MotionSettings(spring=Spring.of(16.0, 0.6), root=Spring.of(16.0, 0.6)))
        motion = Motion()
        motion.snap(plan, _still(plan))
        raised = Keyframe((0.0, -2.0), {"upper_arm_right": (1.0, 1.0)})
        seen = self._run(motion, plan, raised, 2.0)
        arm = [frame.bones["upper_arm_right"][0] for frame in seen]
        self.assertLess(arm[1], 0.2, "it does not jump there")
        self.assertGreater(max(arm), 1.03, "it goes past")
        self.assertLess(max(arm), 1.6)
        self.assertAlmostEqual(arm[-1], 1.0, 3, "and settles where it was going")
        self.assertAlmostEqual(seen[-1].root[1], -2.0, 3)
        self.assertTrue(motion.at_rest(0.01))
        # A bone the pose does not name stays as it was, and one that follows another goes with it.
        self.assertAlmostEqual(seen[-1].bones["thigh_left"][0], 0.0, 6)

    def test_a_stiff_bone_keeps_up_and_a_loose_one_trails(self) -> None:
        stiff, loose = Spring.of(60.0, 0.0), Spring.of(8.0, 0.3)
        plan = replace(
            self.plan, motion=MotionSettings(spring=stiff, root=stiff, springs={"forearm_right": loose})
        )
        motion = Motion()
        motion.snap(plan, _still(plan))
        target = Keyframe((0.0, 0.0), {"upper_arm_right": (1.0, 1.0), "forearm_right": (1.0, 1.0)})
        soon = self._run(motion, plan, target, 0.1)[-1]
        self.assertGreater(soon.bones["upper_arm_right"][0], 0.85)
        self.assertLess(soon.bones["forearm_right"][0], 0.4)

    def test_it_is_the_same_however_many_frames_a_second_it_is_shown_at(self) -> None:
        target = Keyframe((0.0, -1.0), {"spine": (0.3, 1.1), "skull": (0.5, 1.0)})
        ends = []
        for frame in (1 / 30, 1 / 60, 1 / 120):
            motion = Motion()
            motion.snap(self.plan, _still(self.plan))
            ends.append(self._run(motion, self.plan, target, 0.5, frame)[-1])
        for other in ends[1:]:
            self.assertAlmostEqual(other.bones["skull"][0], ends[0].bones["skull"][0], 2)
            self.assertAlmostEqual(other.root[1], ends[0].root[1], 2)
        # A long stall is not caught up with: the body does not leap.
        motion = Motion()
        motion.snap(self.plan, _still(self.plan))
        motion.follow(self.plan, target, 30.0)
        self.assertLess(motion.keyframe().bones["skull"][0], 0.5)

    def test_taking_up_something_else_gives_the_body_a_jolt(self) -> None:
        loose = Spring.of(16.0, 0.5)
        settings = MotionSettings(spring=loose, root=loose, jolt_root=(0.0, 30.0), jolt_bones={"spine": (0.0, -1.0)})
        plan = replace(self.plan, motion=settings)
        still = _still(plan)
        calm, jolted = Motion(), Motion()
        for motion in (calm, jolted):
            motion.snap(plan, still, "idle")
        self._run(calm, plan, still, 0.1, doing="idle")
        seen = self._run(jolted, plan, still, 0.1, doing="work")
        self.assertTrue(calm.at_rest())
        self.assertGreater(max(frame.root[1] for frame in seen), 0.5, "it sinks")
        self.assertLess(min(frame.bones["spine"][1] for frame in seen), 0.98, "and is squashed")
        self._run(jolted, plan, still, 3.0, doing="work")
        self.assertTrue(jolted.at_rest(0.01), "and comes back to where it was")
        self.assertAlmostEqual(jolted.keyframe().root[1], 0.0, 2)

    def test_what_trails_is_left_behind_by_what_it_hangs_from(self) -> None:
        self.assertIsNone(self.plan.hangs_from["spine"])
        self.assertEqual(self.plan.hangs_from["forearm_right"], "upper_arm_right")
        self.assertEqual(self.plan.hangs_from["skull"], "neck")
        stiff = Spring.of(40.0, 0.0)
        plan = replace(self.plan, motion=MotionSettings(spring=stiff, root=stiff, springs={"forearm_right": Spring.of(40.0, 0.0, 0.08)}))
        dragged, plain = Motion(), Motion()
        dragged.snap(plan, _still(plan))
        plain.snap(replace(plan, motion=MotionSettings(spring=stiff, root=stiff)), _still(plan))
        target = Keyframe((0.0, 0.0), {"upper_arm_right": (1.0, 1.0), "forearm_right": (1.0, 1.0)})
        behind = self._run(dragged, plan, target, 0.05)[-1].bones["forearm_right"][0]
        along = self._run(plain, replace(plan, motion=MotionSettings(spring=stiff, root=stiff)), target, 0.05)[-1].bones["forearm_right"][0]
        self.assertLess(behind, along)

    def test_springs_are_data_and_bad_ones_are_refused(self) -> None:
        motion = self.plan.motion
        self.assertGreater(motion.spring.pull, 0)
        self.assertTrue(motion.springs, "some bones are looser than the rest")
        self.assertLessEqual(set(motion.springs), set(self.plan.bones))
        self.assertLess(motion.springs["hand_right"].pull, motion.springs["thigh_right"].pull, "a hand is looser than a leg")
        spring = Spring.of(10.0, 0.0)
        self.assertAlmostEqual(spring.pull, 100.0)
        self.assertAlmostEqual(spring.hold, 20.0, msg="with no bounce it gets there without going past")
        self.assertAlmostEqual(Spring.of(10.0, 0.5).hold, 10.0)
        # However stiff a spring and however long the step, it never flies off.
        for spring in (Spring.of(200.0, 0.0), Spring.of(200.0, 0.9), Spring(400.0, 90.0), Spring.of(3.0, 0.2)):
            off, speed = 1.0, 0.0
            for _ in range(600):
                kept, gained, turned, slowed = spring.stepped(1 / 30)
                off, speed = kept * off + gained * speed, turned * off + slowed * speed
                self.assertLess(abs(off), 1.0 + 1e-9)
            self.assertAlmostEqual(off, 0.0, 3)
        data = {
            "root": "a",
            "joints": {"a": {}, "b": {}},
            "bones": {"ab": ["a", "b"]},
            "views": {view: {"rest": {"a": [0, -2], "b": [0, 0]}} for view in ("front", "side")},
            "orders": {"front": [], "side": [], "back": []},
        }
        made = plan_from_data({**data, "motion": {"spring": {"speed": 10, "bounce": 0.5}, "springs": {"ab": {"speed": 5}}, "jolt": {"root": [0, 9], "bones": {"ab": [90, -1]}}}})
        self.assertAlmostEqual(made.motion.spring.hold, 10.0)
        self.assertEqual(made.motion.root, made.motion.spring, "the whole body goes by the spring of any bone unless it has its own")
        self.assertAlmostEqual(made.motion.springs["ab"].pull, 25.0)
        self.assertEqual(made.motion.jolt_root, (0.0, 9.0))
        self.assertAlmostEqual(made.motion.jolt_bones["ab"][0], math.pi / 2)
        for motion in (
            {"spring": {"speed": 0}},
            {"spring": {"speed": 10, "bounce": 1}},
            {"springs": {"nothing": {"speed": 5}}},
            {"jolt": {"bones": {"nothing": [1, 1]}}},
        ):
            with self.assertRaises(ValueError, msg=motion):
                plan_from_data({**data, "motion": motion})


class LivelyCharacterTests(unittest.TestCase):
    """A body shown as a doll moves by its springs. Any other is posed exactly as its clip says."""

    def setUp(self) -> None:
        self.plan = builtin_plan()

    def test_a_body_that_is_not_lively_is_posed_to_the_letter(self) -> None:
        body = Character(self.plan)
        body.stand(50, 80, "doll_right", "walk", 0.3)
        body.update(1 / 60)
        exact = self.plan.pose("doll_right", "walk", 0.3)
        self.assertEqual(body.local_pose(), exact)
        self.assertEqual(body.pose()["head"], (50 + exact["head"][0], 80 + exact["head"][1]))

    def test_a_lively_body_trails_its_clip_and_catches_up(self) -> None:
        body = Character(self.plan)
        body.lively = True
        body.stand(0, 0, "doll_right", "idle", 0.0)
        body.update(1 / 60)
        self.assertEqual(body.local_pose(), self.plan.pose("doll_right"))
        body.stand(0, 0, "doll_right", "carry", 0.0)
        body.update(1 / 60)
        held_out = self.plan.pose("doll_right", "carry")
        hand = lambda pose: pose["hand_right"]
        self.assertGreater(math.dist(hand(body.local_pose()), hand(held_out)), 1.0, "the arms are not there yet")
        nearest = math.inf
        for _ in range(240):
            body.update(1 / 60)
            nearest = min(nearest, math.dist(hand(body.local_pose()), hand(held_out)))
        self.assertLess(math.dist(hand(body.local_pose()), hand(held_out)), 0.05, "and then they are")
        self.assertEqual(body.local_pose(), held_out, "to the letter, once they have stopped")
        # Asked twice in one frame it is in one place, and with no time gone by it stays there.
        body.stand(0, 0, "doll_right", "idle", 0.0)
        body.update(1 / 60)
        once = body.local_pose()
        self.assertEqual(body.local_pose(), once)
        body.update(0.0)
        self.assertEqual(body.local_pose(), once)

    def test_a_body_nobody_looked_at_is_where_its_clips_have_it_when_it_is_seen_again(self) -> None:
        body = Character(self.plan)
        body.lively = True
        body.stand(0, 0, "doll_right", "idle", 0.0)
        body.update(1 / 60)
        body.local_pose()
        body.stand(0, 0, "doll_right", "carry", 0.0)
        for _ in range(120):
            body.update(1 / 60)
        self.assertEqual(body.local_pose(), self.plan.pose("doll_right", "carry"), "it does not swing there from where it was left")

    def test_turning_round_is_at_once_and_mirrors_what_it_was_doing(self) -> None:
        body = Character(self.plan)
        body.lively = True
        body.stand(0, 0, "doll_right", "idle", 0.0)
        body.update(1 / 60)
        body.stand(0, 0, "doll_right", "carry", 0.0)
        for _ in range(4):
            body.update(1 / 60)
            body.local_pose()
        right = body.local_pose()
        body.stand(0, 0, "doll_left", "carry", 0.0)
        left = body.local_pose()
        # The near hand is the other one now, and where the first was in a mirror.
        self.assertAlmostEqual(left["hand_left"][0], -right["hand_right"][0], 6)
        self.assertAlmostEqual(left["hand_left"][1], right["hand_right"][1], 6)

    def test_struck_it_falls_from_where_it_is_seen_and_not_from_where_its_clip_has_it(self) -> None:
        body = Character(self.plan)
        body.lively = True
        body.stand(0, 0, "doll_right", "idle", 0.0)
        body.update(1 / 60)
        body.stand(0, 0, "doll_right", "carry", 0.0)
        body.update(1 / 60)
        seen = body.pose()
        body.knock_down(40.0, -20.0)
        for joint, (x, y) in seen.items():
            if joint == self.plan.root:
                continue
            self.assertAlmostEqual(body.skeleton.joints[joint].x, x, 6, joint)
            self.assertAlmostEqual(body.skeleton.joints[joint].y, y, 6, joint)

    def test_faster_time_makes_the_springs_faster_too(self) -> None:
        slow, fast = Character(self.plan), Character(self.plan)
        for body, pace in ((slow, 1.0), (fast, 3.0)):
            body.lively, body.pace = True, pace
            body.stand(0, 0, "doll_right", "idle", 0.0)
            body.update(1 / 60)
            body.local_pose()
            body.stand(0, 0, "doll_right", "carry", 0.0)
            for _ in range(3):
                body.update(1 / 60)
                body.local_pose()
        held_out = self.plan.pose("doll_right", "carry")["hand_right"]
        self.assertLess(math.dist(fast.local_pose()["hand_right"], held_out), math.dist(slow.local_pose()["hand_right"], held_out))


if __name__ == "__main__":
    unittest.main()
