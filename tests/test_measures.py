"""A doll's own measures: each part as long on the doll as on its paper, and its limbs joined on where they were put."""

import json
import math
import os
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

import pygame

from graphics.doll import (
    BODY_CANVAS,
    DOLL_VIEW,
    SHORTEST_PART,
    DollBuild,
    DollStore,
    build_from_data,
    build_path,
    doll_plan,
    doll_rest,
    load_template,
)
from graphics.doll_guide import reference
from graphics.illustrations import Illustrations
from settings import SCALE
from skeleton.plan import builtin_plan
from skeleton.rig import Skeleton


def _length(spec) -> float:
    return math.dist(spec.start, spec.end)


class DollBuildTests(unittest.TestCase):
    def setUp(self) -> None:
        pygame.init()
        self.addCleanup(pygame.quit)
        self.template = load_template()
        self.plan = builtin_plan()

    def test_with_no_measures_of_its_own_a_doll_is_the_template_and_nothing_is_drawn_out(self) -> None:
        build = DollBuild()
        self.assertIs(self.template.built(build), self.template)
        self.assertTrue(self.template.takes(build))
        plan = doll_plan(self.plan, self.template, build)
        for bone, spec in self.template.parts.items():
            if spec.rides:
                continue
            self.assertAlmostEqual(plan.length(DOLL_VIEW, bone), _length(spec) / self.template.unit, places=6, msg=bone)
        # The game's own body had a longer trunk than the paper, and drew the drawing out to fit.
        self.assertGreater(self.plan.length(DOLL_VIEW, "spine"), plan.length(DOLL_VIEW, "spine"))
        # Only the doll's own view is its own: seen as the game's bodies are, nothing has changed.
        self.assertEqual(plan.rests["side"], self.plan.rests["side"])
        self.assertEqual(plan.clips, self.plan.clips)

    def test_a_joint_moved_makes_its_part_longer_and_takes_along_what_hangs_from_it(self) -> None:
        unit = self.template.unit
        built = self.template.built(DollBuild(joints={"thigh.end": -1.5}))
        for side in ("_left", "_right"):
            thigh, shin, foot = (built.parts[f"{part}{side}"] for part in ("thigh", "shin", "foot"))
            before = [self.template.parts[f"{part}{side}"] for part in ("thigh", "shin", "foot")]
            self.assertAlmostEqual(_length(thigh), _length(before[0]) - 1.5 * unit)
            self.assertEqual(thigh.start, before[0].start, "the hip stays where it was")
            self.assertEqual(shin.start, thigh.end, "the limb is still in one piece")
            self.assertEqual(foot.start, shin.end)
            # What is below the knee is as long as it was, and that much higher on the paper.
            self.assertAlmostEqual(_length(shin), _length(before[1]))
            self.assertAlmostEqual(_length(foot), _length(before[2]))
            self.assertAlmostEqual(foot.end[1], before[2].end[1] - 1.5 * unit)
        # Both legs are one to the measures; an arm is not a leg.
        self.assertEqual(built.parts["upper_arm_left"], self.template.parts["upper_arm_left"])
        self.assertEqual(built.parts["spine"], self.template.parts["spine"])

    def test_where_a_limb_starts_moves_all_of_it(self) -> None:
        unit = self.template.unit
        built = self.template.built(DollBuild(joints={"upper_arm.start": -1.0}))
        for part in ("upper_arm_left", "forearm_left", "hand_left", "upper_arm_right"):
            now, before = built.parts[part], self.template.parts[part]
            self.assertAlmostEqual(now.start[1], before.start[1] - unit, msg=part)
            self.assertAlmostEqual(_length(now), _length(before), msg=part)
        plan = doll_plan(self.plan, built, DollBuild(joints={"upper_arm.start": -1.0}))
        self.assertEqual(plan.rests[DOLL_VIEW], doll_plan(self.plan, self.template, DollBuild()).rests[DOLL_VIEW])

    def test_the_trunk_is_measured_like_any_limb(self) -> None:
        unit = self.template.unit
        built = self.template.built(DollBuild(joints={"spine.end": -1.0, "hips.end": 1.0}))
        self.assertAlmostEqual(_length(built.parts["spine"]), _length(self.template.parts["spine"]) - unit)
        self.assertEqual(built.parts["neck"].start, built.parts["spine"].end)
        self.assertAlmostEqual(_length(built.parts["neck"]), _length(self.template.parts["neck"]))
        self.assertAlmostEqual(_length(built.parts["hips"]), _length(self.template.parts["hips"]) + unit)

    def test_someone_short_in_the_leg_stands_lower_and_still_on_the_ground(self) -> None:
        tall = doll_rest(self.plan, self.template, DollBuild())
        build = DollBuild(joints={"shin.end": -2.0, "thigh.end": -1.0})
        short = doll_rest(self.plan, self.template.built(build), build)
        base = self.plan.rests[DOLL_VIEW]
        for joint in ("foot_left", "foot_right", "toe_left", "toe_right"):
            for rest in (tall, short):
                self.assertAlmostEqual(rest[joint][1], base[joint][1], msg=joint)
                self.assertAlmostEqual(rest[joint][0], base[joint][0], msg=joint)
        for joint in ("pelvis", "chest", "head", "hand_left"):
            self.assertAlmostEqual(short[joint][1], tall[joint][1] + 3.0, msg=f"{joint} is three lower")
        # Above the legs nothing is otherwise: the same trunk on shorter legs.
        self.assertAlmostEqual(short["head"][1] - short["pelvis"][1], tall["head"][1] - tall["pelvis"][1])

    def test_a_limb_is_joined_on_where_it_was_put_and_a_head_where_it_sits(self) -> None:
        plain = doll_rest(self.plan, self.template, DollBuild())
        build = DollBuild(attach={"clavicle": (1.0, 0.5), "pelvis": (-0.5, -1.0)}, points={"skull.start": (1.0, -1.0)})
        built = self.template.built(build)
        moved = doll_rest(self.plan, built, build)

        def off(rest: dict, joint: str, other: str) -> tuple[float, float]:
            return (round(rest[joint][0] - rest[other][0], 6), round(rest[joint][1] - rest[other][1], 6))

        for side in ("_left", "_right"):
            before = off(plain, f"shoulder{side}", "chest")
            self.assertEqual(off(moved, f"shoulder{side}", "chest"), (before[0] + 1.0, before[1] + 0.5))
            before = off(plain, f"hip{side}", "pelvis")
            self.assertEqual(off(moved, f"hip{side}", "pelvis"), (round(before[0] - 0.5, 6), round(before[1] - 1.0, 6)))
            # An arm is as long as ever, wherever it hangs from.
            self.assertEqual(off(moved, f"hand{side}", f"shoulder{side}"), off(plain, f"hand{side}", f"shoulder{side}"))
        # The neck's place on the head's own paper went right and up: the head sits left and down of where it did.
        before, after = off(plain, "head", "neck"), off(moved, "head", "neck")
        self.assertEqual(after, (before[0] - 1.0, before[1] + 1.0))
        self.assertEqual(self.template.parts["skull"].end, built.parts["skull"].end, "the head itself has not moved on its paper")

    def test_measures_a_doll_cannot_have_are_refused(self) -> None:
        unit_length = _length(self.template.parts["shin_left"]) / self.template.unit
        refused = (
            DollBuild(joints={"shin.end": -(unit_length - SHORTEST_PART / 2)}),  # hardly a shin left
            DollBuild(joints={"shin.end": -unit_length - 1.0}),  # inside out
            DollBuild(joints={"neck.end": 2.0}),  # off the top of the paper
            DollBuild(joints={"hand.end": 14.0}),  # off the foot of the paper
            DollBuild(joints={"hips.end": 6.0}),  # so are these
            DollBuild(points={"skull.start": (10.0, 0.0)}),  # off the head's paper
            DollBuild(attach={"clavicle": (9.0, 0.0)}),  # an arm nowhere near the body
        )
        for build in refused:
            self.assertFalse(self.template.takes(build), build)
        accepted = (
            DollBuild(joints={"shin.end": -2.0, "thigh.end": -2.0}),
            DollBuild(joints={"shin.end": 2.0}),
            DollBuild(joints={"upper_arm.end": 1.5, "forearm.end": -1.0}),
            DollBuild(joints={"upper_arm.start": -1.0, "hand.end": 0.5}),
            DollBuild(attach={"clavicle": (1.0, 2.0), "pelvis": (0.0, -1.5)}, points={"skull.start": (-1.5, 1.0)}),
        )
        for build in accepted:
            self.assertTrue(self.template.takes(build), build)

    def test_every_joint_of_the_guide_can_be_taken_hold_of_once_a_side(self) -> None:
        build = DollBuild(joints={"forearm.end": -1.0})
        handles = self.template.handles(self.template.built(build))
        keys = [handle.key for handle in handles if handle.canvas == BODY_CANVAS]
        for key in ("upper_arm.start", "upper_arm.end", "forearm.end", "hand.end", "thigh.start", "thigh.end", "shin.end", "foot.end"):
            self.assertEqual(keys.count(key), 2, f"{key}: one on each side")
        for key in ("spine.start", "spine.end", "neck.end", "hips.end"):
            self.assertEqual(keys.count(key), 1, key)
        head = [handle for handle in handles if handle.canvas != BODY_CANVAS]
        self.assertEqual([(handle.key, handle.axis) for handle in head], [("skull.start", None)])
        wrists = [handle for handle in handles if handle.key == "forearm.end"]
        self.assertTrue(all(handle.point[1] == handle.origin[1] - self.template.unit for handle in wrists))
        self.assertTrue(all(handle.axis == (0.0, 1.0) for handle in wrists))

    def test_laid_over_its_own_body_no_part_of_a_doll_is_drawn_out(self) -> None:
        store = DollStore(None, self.template, self.plan)
        build = DollBuild(joints={"shin.end": -1.5, "upper_arm.end": 1.0, "spine.end": -0.5}, attach={"clavicle": (0.5, 0.5)})
        built = self.template.built(build)
        doll = store.made({name: reference(built, name) for name in self.template.canvases}, build)
        self.assertEqual(set(doll.parts), set(self.template.parts))
        skeleton = Skeleton(doll.plan, "doll_right")
        skeleton.set_pose(doll.plan.pose("doll_right", "walk", 0.3))
        for name, bone in skeleton.bones.items():
            if name in doll.drawn:
                self.assertAlmostEqual(bone.length, doll.drawn[name], places=6, msg=name)
        # Over the game's own body the same drawing would have had to be pulled to fit.
        self.assertNotAlmostEqual(Skeleton(self.plan, "doll_right").bones["spine"].length, doll.drawn["spine"])

    def test_measures_are_kept_as_they_were_and_what_cannot_be_read_is_left_out(self) -> None:
        build = DollBuild(joints={"shin.end": -1.25}, points={"skull.start": (0.5, -0.25)}, attach={"pelvis": (0.0, -1.0)})
        self.assertEqual(build_from_data(json.loads(json.dumps(build.to_data()))), build)
        self.assertEqual(build_from_data(None), DollBuild())
        self.assertEqual(build_from_data({"joints": "long", "points": {"a": [1]}, "attach": {"b": ["x", 2]}}), DollBuild())
        self.assertEqual(build_from_data({"joints": {"shin.end": 1, "odd": "two"}}), DollBuild(joints={"shin.end": 1.0}))

    def test_the_measures_a_new_doll_starts_from_are_data_and_a_doll_can_have_them(self) -> None:
        start = self.template.start
        self.assertTrue(self.template.takes(start))
        self.assertEqual(self.template.starting(), start)
        self.assertIsNot(self.template.starting(), start, "whoever is given them may change their own")
        # They are measures like any others: the template under them is what drawings without any are cut by.
        built = self.template.built(start)
        self.assertEqual(built.start, start)
        self.assertEqual(set(built.parts), set(self.template.parts))
        plan = doll_plan(self.plan, built, start)
        for bone, spec in built.parts.items():
            if spec.rides:
                continue
            self.assertAlmostEqual(plan.length(DOLL_VIEW, bone), _length(spec) / self.template.unit, places=6, msg=bone)
        # A template whose start no doll could have gives the plain one instead of a broken doll.
        broken = replace(self.template, start=DollBuild(joints={"shin.end": -40.0}))
        self.assertEqual(broken.starting(), DollBuild())

    def test_someone_not_drawn_yet_starts_from_those_and_an_old_drawing_is_left_as_it_was(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            store = DollStore(Illustrations(root), self.template, self.plan)
            self.assertEqual(store.build("new"), self.template.starting())
            # Drawn before there were measures, over the guide as the template has it.
            old = root / build_path("old")
            old.parent.mkdir(parents=True)
            pygame.image.save(reference(self.template, BODY_CANVAS), str(old.with_name("body.png")))
            self.assertEqual(store.build("old"), DollBuild())
            doll = store.get("old")
            self.assertEqual(doll.template.parts, self.template.parts)
            self.assertEqual(set(doll.parts), {bone for bone, spec in self.template.parts.items() if spec.canvas == BODY_CANVAS})
        self.assertEqual(DollStore(None, self.template, self.plan).build("anyone"), self.template.starting())

    def test_a_store_gives_each_doll_its_own_measures_and_the_template_s_when_they_are_no_good(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            store = DollStore(Illustrations(root), self.template, self.plan)
            for body_id, text in (
                ("ada", json.dumps({"joints": {"shin.end": -2.0}})),
                ("ben", "{ not json"),
                ("cal", json.dumps({"joints": {"shin.end": -40.0}})),
            ):
                path = root / build_path(body_id)
                path.parent.mkdir(parents=True)
                path.write_text(text, encoding="utf-8")
                pygame.image.save(reference(self.template, BODY_CANVAS), str(path.with_name("body.png")))
            with self.assertLogs("graphics.doll", level="WARNING"):
                self.assertEqual(store.build("ben"), DollBuild())
                ben = store.get("ben")
            self.assertEqual(store.build("cal"), DollBuild(), "legs inside out are no legs: cut as the template has it")
            self.assertEqual(store.build("ada"), DollBuild(joints={"shin.end": -2.0}))
            ada = store.get("ada")
            self.assertAlmostEqual(ada.plan.length(DOLL_VIEW, "shin_left"), 1.0)
            self.assertAlmostEqual(ben.plan.length(DOLL_VIEW, "shin_left"), 3.0)
            self.assertIsNot(ada.plan, ben.plan)


class MeasuringInTheEditorTests(unittest.TestCase):
    """Runs the real editor without a window, with a folder of its own to keep drawings in."""

    def setUp(self) -> None:
        for variable in ("SDL_VIDEODRIVER", "SDL_AUDIODRIVER"):
            self.addCleanup(self._restore_driver, variable, os.environ.get(variable))
            os.environ[variable] = "dummy"
        from game.game import Game

        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        (self.root / "illustrations").mkdir()
        (self.root / "custom").mkdir()
        self.game = Game(
            illustrations_dir=self.root / "illustrations",
            voices_dir=None,
            custom_content_dir=self.root / "custom",
            save_path=self.root / "save.json",
            start_in_menu=False,
        )
        self.addCleanup(pygame.quit)
        self.editor = self.game.doll_editor
        self.editor.open("paco")
        # Nobody has drawn Paco, so he has the measures every doll starts from.
        self.start = self.editor.base_template.starting()
        self.assertEqual(self.editor.build, self.start)
        # From here on he is measured from the plain template, whatever the game's start is.
        self.assertTrue(self.editor.set_build(DollBuild()))

    @staticmethod
    def _restore_driver(variable: str, previous: str | None) -> None:
        if previous is None:
            os.environ.pop(variable, None)
        else:
            os.environ[variable] = previous

    def _event(self, kind: int, position: tuple[float, float], **particulars) -> None:
        window = (round(position[0]) * SCALE, round(position[1]) * SCALE)
        self.editor.handle_event(pygame.event.Event(kind, pos=window, **particulars))

    def _click(self, position: tuple[float, float]) -> None:
        self._event(pygame.MOUSEBUTTONDOWN, position, button=1)
        self._event(pygame.MOUSEBUTTONUP, position, button=1)

    def _drag(self, start: tuple[float, float], end: tuple[float, float]) -> None:
        self._event(pygame.MOUSEBUTTONDOWN, start, button=1)
        self._event(pygame.MOUSEMOTION, end, rel=(0, 0), buttons=(1, 0, 0))
        self._event(pygame.MOUSEBUTTONUP, end, button=1)

    def _button(self, intent: tuple) -> tuple[int, int]:
        return next(button for button in self.editor.buttons if button.intent == intent).rect.center

    def _joint(self, key: str, canvas: str = BODY_CANVAS) -> tuple[float, float]:
        area = self.editor.areas[canvas]
        handle = next(handle for handle in self.editor.joint_handles(canvas) if handle.key == key)
        return (area.x + handle.point[0], area.y + handle.point[1])

    def _frame(self) -> None:
        self.editor.update(1 / 60)
        self.editor.render()
        self.game.present()

    def test_joints_are_only_taken_hold_of_with_the_measures_in_hand(self) -> None:
        ankle = self._joint("shin.end")
        self._drag(ankle, (ankle[0], ankle[1] - 16))
        self.assertEqual(self.editor.build, DollBuild(), "with the brush it is a stroke")
        self.assertGreater(pygame.mask.from_surface(self.editor.drawings[BODY_CANVAS]).count(), 0)
        self.editor.clear()

        self._click(self._button(("tool", "measure")))
        self._frame()
        self._drag(ankle, (ankle[0], ankle[1] - 16))
        self.assertEqual(self.editor.build.joints, {"shin.end": -1.0})
        self.assertFalse(pygame.mask.from_surface(self.editor.drawings[BODY_CANVAS]).count(), "and nothing is painted")
        # The guide, the figure under it and the body it is posed on have all followed.
        self.assertAlmostEqual(self.editor.doll_plan.length(DOLL_VIEW, "shin_right"), 2.0)
        self.assertIs(self.editor._preview.plan, self.editor.doll_plan)
        self.assertEqual(self._joint("shin.end"), (ankle[0], ankle[1] - 16))
        self._frame()

    def test_a_joint_goes_no_further_than_the_doll_can_have_it(self) -> None:
        self._click(self._button(("tool", "measure")))
        ankle = self._joint("shin.end")
        self._drag(ankle, (ankle[0], ankle[1] - 300))
        self.assertEqual(self.editor.build, DollBuild(), "pulled past the knee, it stays where it could last be")
        self._event(pygame.MOUSEBUTTONDOWN, ankle, button=1)
        self._event(pygame.MOUSEMOTION, (ankle[0], ankle[1] - 24), rel=(0, 0), buttons=(1, 0, 0))
        self._event(pygame.MOUSEMOTION, (ankle[0], ankle[1] - 300), rel=(0, 0), buttons=(1, 0, 0))
        self._event(pygame.MOUSEBUTTONUP, (ankle[0], ankle[1] - 300), button=1)
        self.assertEqual(self.editor.build.joints, {"shin.end": -1.5})
        # Sideways is no way for an ankle to go.
        ankle = self._joint("shin.end")
        self._drag(ankle, (ankle[0] + 40, ankle[1]))
        self.assertEqual(self.editor.build.joints, {"shin.end": -1.5})

    def test_shoulders_legs_and_head_are_moved_on_the_figure(self) -> None:
        self._click(self._button(("tool", "measure")))
        self._frame()
        spots = {name: spot for _, name, spot in self.editor.figure_handles()}
        self.assertEqual(set(spots), {"clavicle", "pelvis", "skull.start"})
        per_unit = self.editor._per_unit
        self._drag(spots["clavicle"], (spots["clavicle"][0] + per_unit, spots["clavicle"][1] + 2 * per_unit))
        self.assertEqual(self.editor.build.attach, {"clavicle": (1.0, 2.0)})
        moved = {name: spot for _, name, spot in self.editor.figure_handles()}
        self.assertAlmostEqual(moved["clavicle"][1], spots["clavicle"][1] + 2 * per_unit, delta=0.01)
        # A head moved up on the figure is its neck moved down on the head's own paper.
        neck = self._joint("skull.start", "head")
        self._drag(moved["skull.start"], (moved["skull.start"][0], moved["skull.start"][1] - per_unit))
        self.assertEqual(self.editor.build.points, {"skull.start": (0.0, 1.0)})
        self.assertEqual(self._joint("skull.start", "head"), (neck[0], neck[1] + self.editor.template.unit))
        # And the neck can be taken hold of there as well, and goes any way.
        neck = self._joint("skull.start", "head")
        self._drag(neck, (neck[0] - 8, neck[1] - 16))
        self.assertEqual(self.editor.build.points, {"skull.start": (-0.5, 0.0)})
        self._frame()

    def test_measures_are_saved_with_the_drawings_and_found_again(self) -> None:
        self._click(self._button(("tool", "measure")))
        knee = self._joint("thigh.end")
        self._drag(knee, (knee[0], knee[1] - 24))
        self.editor.mannequin()
        self.assertTrue(self.editor.save())
        kept = json.loads((self.root / "illustrations" / build_path("paco")).read_text(encoding="utf-8"))
        self.assertEqual(kept["joints"], {"thigh.end": -1.5})

        doll = self.game.dolls.get("paco")
        self.assertAlmostEqual(doll.plan.length(DOLL_VIEW, "thigh_left"), 1.5)
        self.assertAlmostEqual(doll.drawn["thigh_left"], 1.5)
        # Somebody not drawn yet has the measures to start from, and Paco is found again as he was left.
        self.editor.open("marta")
        self.assertEqual(self.editor.build, self.start)
        self.editor.open("paco")
        self.assertEqual(self.editor.build.joints, {"thigh.end": -1.5})
        # The measures to start from are a button away.
        self._click(self._button(("measures",)))
        self.assertEqual(self.editor.build, self.start)
        self.assertAlmostEqual(
            self.editor.doll_plan.length(DOLL_VIEW, "thigh_left"), 3.0 + self.start.joints.get("thigh.end", 0.0)
        )
        self._frame()


if __name__ == "__main__":
    unittest.main()
