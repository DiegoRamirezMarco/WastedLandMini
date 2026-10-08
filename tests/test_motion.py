import itertools
import json
import math
import random
import unittest
from dataclasses import replace
from types import SimpleNamespace

from graphics.poses import builtin_poses
from skeleton.character import Character
from skeleton.motion import Life, Motion
from skeleton.plan import PLAN_PATH, FACINGS, Keyframe, MotionSettings, Spring, added, builtin_plan, plan_from_data


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
        # Risen further than its legs go, it is not lifted off its feet: it is as high as they let it.
        leapt = self.plan.place("doll_right", Keyframe((0.0, -3.0), {}))
        self.assertAlmostEqual(leapt["foot_right"][1], self.ground, 6)
        self.assertAlmostEqual(leapt["foot_left"][1], self.ground, 6)
        self.assertAlmostEqual(self._leg(leapt), self._leg(self.rest) * stretch, 6)
        self.assertLess(leapt["pelvis"][1], risen["pelvis"][1], "which is higher than it stood")
        self.assertGreater(leapt["pelvis"][1], self.rest["pelvis"][1] - 3.0 + 1.0, "and a good deal short of where the pose had it")
        # To leave the ground a pose has to lift its feet: then they go up with the body, all the way.
        tucked = {
            f"{bone}_{side}": (math.radians(turn), 1.0)
            for side in ("left", "right")
            for bone, turn in (("thigh", 50), ("shin", -60))
        }
        jumped = self.plan.place("doll_right", Keyframe((0.0, -3.0), tucked))
        standing = self.plan.place("doll_right", Keyframe((0.0, 0.0), tucked))
        for side in ("left", "right"):
            self.assertAlmostEqual(jumped[f"foot_{side}"][1], standing[f"foot_{side}"][1] - 3.0, 6, side)
        self.assertAlmostEqual(jumped["pelvis"][1], self.rest["pelvis"][1] - 3.0, 6)
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
        still, risen = self.plan.place("right", Keyframe()), self.plan.place("right", Keyframe((0.5, -1.0), {}))
        self.assertAlmostEqual(risen["foot_right"][1], still["foot_right"][1] - 1.0, 6)
        self.assertAlmostEqual(risen["head"][0], still["head"][0] + 0.5, 6)
        # They have no legs that bend to let them down: a pose that would have them under the
        # ground leaves them standing on it, whole.
        sunk = self.plan.place("right", Keyframe((0.5, 3.0), {}))
        for joint in ("foot_right", "head"):
            self.assertAlmostEqual(sunk[joint][1], still[joint][1], 6)
            self.assertAlmostEqual(sunk[joint][0], still[joint][0] + 0.5, 6)
        for clip in self.plan.clips:
            for phase in (0.0, 0.3, 0.6, 0.8):
                lowest = max(y for _, y in self.plan.pose("right", clip, phase).values())
                self.assertLessEqual(lowest, max(y for _, y in still.values()) + 1e-6, (clip, phase))
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


class SolesTests(unittest.TestCase):
    """Feet that stand flat on the ground, whatever their clip and their springs would turn them to."""

    def setUp(self) -> None:
        self.plan = builtin_plan()
        self.ground = self.plan.rests["doll"]["foot_right"][1]
        self.long = self.plan.length("doll", "foot_right")

    def _sole(self, pose: dict, side: str) -> tuple[float, float, float]:
        """How far a foot is off the ground, and how far its toe is ahead of its heel and under it."""
        heel, toe = pose[f"foot_{side}"], pose[f"toe_{side}"]
        return (self.ground - heel[1], toe[0] - heel[0], toe[1] - heel[1])

    def test_a_sole_on_the_ground_or_near_it_is_flat_to_it_all_the_way_round_a_stride(self) -> None:
        footing = self.plan.footing
        self.assertGreater(footing.level, 0.0)
        self.assertGreater(footing.hold, 0.0)
        turned = 0
        for clip in ("walk", "walk_shuffle", "walk_swagger", "work", "hoe", "weed", "hammer", "argue", "fight", "eat", "stand"):
            for step in range(24):
                phase = step / 24
                bones = self.plan.every_bone(self.plan.turned("doll", clip, phase))
                pose = self.plan.pose("doll_right", clip, phase)
                for side in ("left", "right"):
                    high, ahead, under = self._sole(pose, side)
                    turned += abs(bones[f"foot_{side}"][0]) > 0.2
                    if high <= footing.level:
                        self.assertAlmostEqual(under, 0.0, 6, f"{clip} {phase:.2f} {side}: the sole is level")
                        self.assertAlmostEqual(ahead, self.long, 6, f"{clip} {phase:.2f} {side}: and points ahead")
                    self.assertGreaterEqual(high, -1e-6, "and no foot is under the ground")
        self.assertGreater(turned, 20, "though the clips turn their feet a good deal, heel and toe")
        # Facing the other way it is the same in a mirror.
        left = self.plan.pose("doll_left", "walk", 0.3)
        self.assertAlmostEqual(left["toe_left"][1], left["foot_left"][1], 6)
        self.assertLess(left["toe_left"][0], left["foot_left"][0])

    def test_a_foot_held_well_up_is_as_its_clip_has_it(self) -> None:
        footing = self.plan.footing
        kicked = max(
            (self.plan.pose("doll_right", "fight_kick", step / 40) for step in range(40)),
            key=lambda pose: max(self._sole(pose, side)[0] for side in ("left", "right")),
        )
        side = max(("left", "right"), key=lambda each: self._sole(kicked, each)[0])
        high, ahead, under = self._sole(kicked, side)
        self.assertGreater(high, footing.level * 2, "a kick takes the foot well off the ground")
        self.assertLess(under, -0.3)
        other = "left" if side == "right" else "right"
        self.assertAlmostEqual(self._sole(kicked, other)[2], 0.0, 6, "while the one they stand on is flat")
        # Between the two heights a foot comes level little by little, and not at a stroke.
        full = abs(math.cos(math.radians(50))) * self.long
        seen = []
        for step in range(90):
            bend = step * 0.03
            bones = {"foot_right": (math.radians(-40), 1.0), "thigh_right": (bend, 1.0), "shin_right": (bend * 0.5, 1.0)}
            high, _, under = self._sole(self.plan.place("doll_right", Keyframe((0.0, 0.0), bones)), "right")
            seen.append((high, abs(under)))
        self.assertGreater(max(high for high, _ in seen), footing.level * 2)
        between = [slope for high, slope in seen if footing.level < high < footing.level * 2]
        self.assertGreater(len(between), 3)
        for high, slope in seen:
            if high <= footing.level:
                self.assertAlmostEqual(slope, 0.0, 6, msg=f"at {high:.2f} it is level")
            elif high >= footing.level * 2:
                self.assertAlmostEqual(slope, full, 6, msg=f"at {high:.2f} it is all the clip's")
            else:
                self.assertTrue(0.0 < slope < full, (high, slope))
        self.assertEqual(between, sorted(between), "the higher, the more it is as the clip has it")

    def test_a_foot_that_is_on_the_ground_is_on_it_and_not_a_hair_above(self) -> None:
        footing = self.plan.footing
        # A leg that has not quite settled, as on its springs: its foot a little off where it stands.
        for bend in (0.0, 0.05, 0.1):
            bones = {"thigh_right": (bend, 1.0), "shin_right": (-bend * 0.5, 1.0)}
            pose = self.plan.place("doll_right", Keyframe((0.0, 0.4), bones))
            lift = self.ground - self.plan.place("doll_right", Keyframe((0.0, 0.0), bones))["foot_right"][1]
            self.assertLess(lift, footing.hold)
            self.assertAlmostEqual(pose["foot_right"][1], self.ground, 6, f"bent by {bend}")
        # A body lively on its springs, walking: whichever foot is down is down.
        body = Character(self.plan)
        body.lively = True
        seen = []
        for frame in range(180):
            body.stand(0, 0, "doll_right", "walk", frame / 60 % 1.0)
            body.update(1 / 60)
            pose = body.local_pose()
            lows = sorted(self._sole(pose, side) for side in ("left", "right"))
            seen.append(lows[0][0])
            for high, ahead, under in lows:
                if high <= footing.level:
                    self.assertAlmostEqual(under, 0.0, 6, f"frame {frame}")
        self.assertLess(sum(1 for high in seen if high > 0.05), len(seen) * 0.35, "one foot or the other is on the ground")

    def test_a_foot_that_kneels_lies_flat_the_way_it_points_and_the_small_bodies_are_left_alone(self) -> None:
        curled = self.plan.pose("doll_right", builtin_poses().rough.asleep.clip)
        for side in ("left", "right"):
            high, ahead, under = self._sole(curled, side)
            self.assertAlmostEqual(under, 0.0, 6, "level")
            self.assertLess(ahead, 0.0, "and behind them, where a kneeling foot points")
        # Only the views whose legs stand are levelled: the game's own small bodies roll their feet as they did.
        rolled = [
            abs(pose["toe_left"][1] - pose["foot_left"][1])
            for pose in (self.plan.pose("right", "walk", step / 16) for step in range(16))
        ]
        self.assertGreater(max(rolled), 0.3)

    def test_how_near_the_ground_is_data_and_data_that_cannot_be_is_refused(self) -> None:
        data = json.loads(PLAN_PATH.read_text(encoding="utf-8"))
        bare = plan_from_data({**data, "footing": {key: value for key, value in data["footing"].items() if key not in ("hold", "level")}})
        self.assertEqual((bare.footing.hold, bare.footing.level), (0.0, 0.0))
        rolled = bare.pose("doll_right", "walk", 0.0)
        self.assertGreater(abs(rolled["toe_left"][1] - rolled["foot_left"][1]), 0.5, "with no level given, feet turn as before")
        for wrong in ({"hold": -0.1}, {"hold": 5.0}, {"level": -1.0}):
            with self.assertRaises(ValueError, msg=wrong):
                plan_from_data({**data, "footing": {**data["footing"], **wrong}})


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


class GestureTests(unittest.TestCase):
    """Something done once over whatever else a body is doing: no window, no pictures."""

    def setUp(self) -> None:
        self.plan = builtin_plan()
        self.rate = 2.0

    def _walker(self, lively: bool = True) -> Character:
        body = Character(self.plan)
        body.lively = lively
        body.stand(0, 0, "doll_right", "walk", 0.3)
        return body

    def test_a_gesture_moves_the_bones_its_clip_names_and_leaves_the_rest_to_what_was_going_on(self) -> None:
        body = self._walker()
        walking = self.plan.turned("doll", "walk", 0.3).bones
        self.assertIn("pocket", self.plan.once)
        body.gesture("pocket", self.rate)
        self.assertEqual(body.gesturing, "pocket")
        body.update(0.3 / self.rate)
        aim = body.aim().bones
        reaching = self.plan.sample("pocket", "doll", 0.3).bones
        self.assertEqual(set(reaching), {"neck", "skull", "upper_arm_right", "forearm_right"})
        for bone, turned in reaching.items():
            self.assertEqual(aim[bone], turned, bone)
        self.assertLess(aim["upper_arm_right"][0], 0.0, "the hand goes back to the hip")
        for bone in ("thigh_left", "thigh_right", "upper_arm_left", "spine"):
            self.assertEqual(aim.get(bone), walking.get(bone), f"{bone} goes on walking")

    def test_it_is_done_once_at_its_own_pace_and_then_the_body_is_as_it_was(self) -> None:
        body = self._walker()
        body.gesture("pocket", self.rate)
        body.update(0.4)
        self.assertEqual(body.gesturing, "pocket")
        # Another asked for meanwhile waits for nothing: the one under way is finished, and that is all.
        body.gesture("fidget_shrug", self.rate)
        self.assertEqual(body.gesturing, "pocket")
        body.update(0.11)
        self.assertIsNone(body.gesturing, "half a second at two turns a second")
        self.assertEqual(body.aim().bones, self.plan.turned("doll", "walk", 0.3).bones)
        # With the game going faster its gestures go faster, as its springs do.
        body.pace = 4.0
        body.gesture("pocket", self.rate)
        body.update(0.13)
        self.assertIsNone(body.gesturing)
        body.gesture("pocket", 0.0)
        self.assertIsNone(body.gesturing, "a gesture that takes for ever is none")

    def test_only_a_body_shown_moving_smoothly_makes_gestures(self) -> None:
        kept = self._walker(lively=False)
        kept.gesture("pocket", self.rate)
        self.assertIsNone(kept.gesturing, "one kept as a picture for each frame of its clip has none")
        self.assertEqual(kept.aim().bones, self.plan.turned("doll", "walk", 0.3).bones)
        body = self._walker()
        body.gesture("pocket", self.rate)
        body.lively = False
        body.update(0.1)
        self.assertIsNone(body.gesturing, "and one that stops being shown so lets go of it")


class LifeTests(unittest.TestCase):
    """A body shown moving breathes, and with nothing to do it shifts its weight and fidgets."""

    FRAME = 1 / 60

    def setUp(self) -> None:
        self.plan = builtin_plan()
        self.settings = self.plan.life

    def test_what_a_body_at_rest_does_is_data(self) -> None:
        settings = self.settings
        self.assertIn(settings.breath, self.plan.clips)
        self.assertIn(settings.stand, self.plan.clips)
        self.assertGreaterEqual(len(settings.fidgets), 3)
        for clip in settings.fidgets:
            self.assertIn(clip, self.plan.once, f"{clip} is done once")
            first, last = self.plan.sample(clip, "side", 0.0), self.plan.sample(clip, "side", 1.0)
            self.assertEqual((first.bones, last.bones), ({}, {}), f"{clip} starts and ends standing")
        self.assertNotIn(settings.stand, self.plan.once)
        self.assertNotIn(settings.breath, self.plan.once)
        self.assertEqual(self.plan.frames("idle", "side"), 1, "standing still is still one pose, to measure by")
        self.assertLess(settings.every[0], settings.every[1])
        data = {
            "root": "a",
            "joints": {"a": {}, "b": {}},
            "bones": {"ab": ["a", "b"]},
            "views": {view: {"rest": {"a": [0, -2], "b": [0, 0]}} for view in ("front", "side")},
            "orders": {"front": [], "side": [], "back": []},
            "clips": {"idle": {}, "sigh": {"side": [{}, {"ab": 5}]}, "nod": {"once": True, "side": [{}, {"ab": 9}, {}]}},
        }
        made = plan_from_data({**data, "life": {"breath": {"clip": "sigh", "rate": 0.5}, "fidgets": {"clips": ["nod"], "every": [2, 3]}}})
        self.assertEqual((made.life.breath, made.life.breath_rate, made.life.stand, made.life.fidgets), ("sigh", 0.5, None, ("nod",)))
        self.assertEqual(plan_from_data(data).life.fidgets, ())
        for life in (
            {"breath": {"clip": "yawn"}},
            {"fidgets": {"clips": ["nod", "wave"]}},
            {"fidgets": {"clips": ["nod"], "every": [5, 2]}},
            {"fidgets": {"clips": ["nod"], "rate": 0}},
        ):
            with self.assertRaises(ValueError, msg=life):
                plan_from_data({**data, "life": life})

    def test_everybody_breathes_to_a_beat_of_their_own(self) -> None:
        one, other, again = Life(random.Random("a")), Life(random.Random("b")), Life(random.Random("a"))
        self.assertNotEqual(one.breath, other.breath)
        self.assertEqual(one.breath, again.breath, "the same chance gives the same life")
        before = one.breath
        one.update(self.settings, 1.0, False)
        self.assertAlmostEqual(one.breath, (before + self.settings.breath_rate) % 1.0)
        self.assertIsNone(one.fidget)

    def test_with_nothing_to_do_it_shifts_its_weight_and_now_and_then_does_something_small(self) -> None:
        settings, life = self.settings, Life(random.Random(3))
        seen = []
        for _ in range(round(120 / self.FRAME)):
            life.update(settings, self.FRAME, True)
            seen.append(life.idling(settings))
        self.assertEqual(seen[0][0], settings.stand)
        runs = [(clip, len(list(frames))) for clip, frames in itertools.groupby(clip for clip, _ in seen)]
        done = [clip for clip, _ in runs if clip != settings.stand]
        self.assertGreaterEqual(len(done), 4, "in two minutes it has fidgeted a few times")
        self.assertLessEqual(set(done), set(settings.fidgets))
        self.assertGreater(len(set(done)), 1, "and not always the same way")
        for clip, frames in runs[1:-1]:
            if clip == settings.stand:
                self.assertGreaterEqual(frames, settings.every[0] / self.FRAME - 2, "it stands a while between two")
                self.assertLessEqual(frames, settings.every[1] / self.FRAME + 2)
            else:
                self.assertAlmostEqual(frames, 1 / settings.fidget_rate / self.FRAME, delta=2, msg="each is done once through")
        through = [phase for clip, phase in seen if clip == done[0]][: round(1 / settings.fidget_rate / self.FRAME) - 2]
        self.assertEqual(through, sorted(through))
        self.assertLess(through[0], 0.05)
        self.assertGreater(through[-1], 0.9)
        stood = [phase for clip, phase in seen[:200] if clip == settings.stand]
        self.assertNotEqual(stood[0], stood[-1], "standing, its weight is on the move")

    def test_busy_it_does_not_fidget_and_drops_what_it_was_at(self) -> None:
        settings, life = self.settings, Life(random.Random(5))
        while life.fidget is None:
            life.update(settings, self.FRAME, True)
        life.update(settings, self.FRAME, False)
        self.assertIsNone(life.fidget, "given something to do, it leaves off")
        for _ in range(round(90 / self.FRAME)):
            life.update(settings, self.FRAME, False)
            self.assertIsNone(life.fidget)
        # Free again, it waits as long as ever before the next.
        for _ in range(round((settings.every[0] - 1) / self.FRAME)):
            life.update(settings, self.FRAME, True)
            self.assertIsNone(life.fidget)

    def test_its_chance_is_its_own_and_the_same_seed_gives_the_same_life(self) -> None:
        state = random.getstate()
        lives = [Life(random.Random(11)), Life(random.Random(11))]
        told = [[], []]
        for _ in range(round(60 / self.FRAME)):
            for life, heard in zip(lives, told):
                life.update(self.settings, self.FRAME, True)
                heard.append(life.idling(self.settings))
        self.assertEqual(told[0], told[1])
        self.assertEqual(random.getstate(), state, "nobody else's chance was touched")

    def test_a_body_with_a_life_breathes_whatever_it_is_doing_and_one_without_does_not(self) -> None:
        heights = []
        for life in (Life(random.Random(1)), None):
            body = Character(self.plan)
            body.lively, body.life = True, life
            body.stand(0, 0, "doll_right", "work", 0.0)
            chest = []
            for _ in range(round(4 / self.FRAME)):
                body.update(self.FRAME)
                chest.append(body.local_pose()["shoulder_right"][1])
            heights.append(max(chest) - min(chest))
        self.assertGreater(heights[0], 0.1, "its shoulders rise and fall")
        self.assertAlmostEqual(heights[1], 0.0, 6)
        # A body that is not lively is posed to the letter, life or no life.
        body = Character(self.plan)
        body.life = Life(random.Random(1))
        body.stand(0, 0, "doll_right", "work", 0.0)
        body.update(1.0)
        self.assertEqual(body.local_pose(), self.plan.pose("doll_right", "work", 0.0))

    def test_at_ease_it_stands_as_its_life_has_it_and_with_something_in_hand_as_its_clip_does(self) -> None:
        body = Character(self.plan)
        body.lively, body.life = True, Life(random.Random(2))
        body.life.fidget, body.life.through = "fidget_stretch", 0.5
        body.stand(0, 0, "doll_right", "idle", 0.0)
        hanging = self.plan.pose("doll_right")["hand_right"][1]
        body.at_ease = False
        self.assertFalse(body.idle)
        self.assertAlmostEqual(body.plan.place("doll_right", body.aim())["hand_right"][1], hanging, delta=1.0)
        body.at_ease = True
        self.assertTrue(body.idle)
        self.assertLess(body.plan.place("doll_right", body.aim())["hand_right"][1], hanging - 6.0, "its arms are up over its head")
        # Carrying, or walking, it is not idle whatever whoever shows it says.
        body.stand(0, 0, "doll_right", "idle", 0.0, "carry")
        self.assertFalse(body.idle)
        body.stand(0, 0, "doll_right", "walk", 0.2)
        self.assertFalse(body.idle)
        # Fidgeting is not taking up something else: the body is given no jolt for it.
        body.stand(0, 0, "doll_right", "idle", 0.0)
        body.life.fidget = None
        body.update(self.FRAME)
        body.local_pose()
        low = body.local_pose()["pelvis"][1]
        body.life.fidget, body.life.through = "fidget_shrug", 0.0
        sunk = 0.0
        for _ in range(12):
            body.update(0.0)
            body._owed = self.FRAME
            sunk = max(sunk, body.local_pose()["pelvis"][1] - low)
        self.assertLess(sunk, 0.2)

    def test_the_stage_gives_every_resident_a_life_of_their_own(self) -> None:
        from scenes.body_stage import BodyStage

        def stage() -> BodyStage:
            return BodyStage(SimpleNamespace(plan=self.plan), seed=4)

        def resident(name: str) -> SimpleNamespace:
            return SimpleNamespace(resident_id=name, lost_limbs=[], x=3.0, y=4.0, facing="down")

        first, second = stage(), stage()
        ana, luis = first.character(resident("ana")), first.character(resident("luis"))
        self.assertIsNotNone(ana.life)
        self.assertNotEqual(ana.life.breath, luis.life.breath)
        self.assertIs(first.character(resident("ana")), ana)
        self.assertEqual(second.character(resident("ana")).life.breath, ana.life.breath, "the same stage gives the same lives")
        self.assertFalse(ana.lively, "until it is shown as a doll it is posed to the letter")


if __name__ == "__main__":
    unittest.main()
