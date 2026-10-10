import json
import os
import tempfile
import unittest
from pathlib import Path

import pygame

from graphics.doll import DOLL_FACINGS, build_path, doll_path, load_template
from graphics.face import load_rules
from graphics.figure import LIMBS_KEY
from graphics.mannequin import figures, tones_of
from graphics.turn import limb_keys_from_data, limb_keys_to_data, limb_names, limbs_moved, turned_pose
from scenes.doll_page import MEASURE_TOOL, NUDGE
from scenes.studio import FACE_TAB
from settings import SCALE, SCREEN_HEIGHT, SCREEN_WIDTH
from skeleton.plan import FACINGS, builtin_plan

SKIN = (214, 170, 130)
LINE = (30, 22, 20)
ARM = ("shoulder", "elbow", "hand", "fingertip")


def other_side(joint: str) -> str:
    """What a joint of one side is called on the other."""
    if joint.endswith("_right"):
        return joint[: -len("_right")] + "_left"
    if joint.endswith("_left"):
        return joint[: -len("_left")] + "_right"
    return joint


class LimbsPutInPlaceTests(unittest.TestCase):
    """Where a limb was put by hand, in each view, and what is made of it on a body turned any way."""

    def setUp(self) -> None:
        self.rules = load_rules()
        self.turn, self.views, self.side = self.rules.body, self.rules.views, self.rules.side
        self.plan = builtin_plan()

    def test_each_limb_is_one_by_itself_and_what_is_kept_of_it_is_read_again(self) -> None:
        self.assertEqual(set(limb_names(self.turn)), {"arm_left", "arm_right", "leg_left", "leg_right"})
        keys = {"front": {"arm_right": (0.5, -0.25)}, "profile": {"leg_left": (-1.0, 0.0), "arm_left": (0.0, 0.0)}}
        kept = limb_keys_to_data(keys)
        self.assertEqual(kept, {"front": {"arm_right": [0.5, -0.25]}, "profile": {"leg_left": [-1.0, 0.0]}})
        self.assertEqual(limb_keys_from_data(json.loads(json.dumps(kept)), self.turn, self.views), {
            "front": {"arm_right": (0.5, -0.25)}, "profile": {"leg_left": (-1.0, 0.0)},
        })
        # Whatever cannot be read, or is of a view or a limb there is not, is left out.
        odd = {"front": {"tail": [1, 1], "arm_left": "far"}, "above": {"arm_left": [1, 1]}, "profile": 3}
        self.assertEqual(limb_keys_from_data(odd, self.turn, self.views), {})
        self.assertEqual(limb_keys_from_data(None, self.turn, self.views), {})

    def test_between_two_views_a_limb_is_between_where_it_was_put_in_each(self) -> None:
        keys = {"front": {"arm_right": (2.0, 0.0)}, "three_quarter": {"arm_right": (1.0, 1.0)}}

        def moved(yaw: float) -> dict:
            return limbs_moved(keys, self.views, yaw, self.side)

        self.assertEqual(moved(0.0), {"arm_right": (2.0, 0.0)})
        self.assertEqual(moved(self.views["three_quarter"]), {"arm_right": (1.0, 1.0)})
        half = moved(self.views["three_quarter"] / 2)["arm_right"]
        self.assertAlmostEqual(half[0], 1.5)
        self.assertAlmostEqual(half[1], 0.5)
        # Nobody put it anywhere from the side: there it is where it goes by rule.
        self.assertEqual(moved(self.side), {})
        # From behind it is as it is as far round from the front, the other way across.
        self.assertEqual(moved(2 * self.side), {"arm_right": (-2.0, 0.0)})
        self.assertEqual(limbs_moved({}, self.views, 30.0, self.side), {})

    def test_the_whole_limb_goes_and_no_other_part_of_the_body(self) -> None:
        pose = self.plan.pose(DOLL_FACINGS["right"], "walk", 0.3)
        for yaw in (self.side, 45.0, 0.0):
            plain = turned_pose(self.turn, {}, pose, yaw, self.side)
            moved = turned_pose(self.turn, {}, pose, yaw, self.side, moved={"arm_right": (1.5, -0.5)})
            for joint, (x, y) in plain.items():
                if joint in {f"{part}_right" for part in ARM}:
                    self.assertAlmostEqual(moved[joint][0], x + 1.5)
                    self.assertAlmostEqual(moved[joint][1], y - 0.5)
                else:
                    self.assertEqual(moved[joint], (x, y), joint)
        # From its side, with nothing put anywhere, a body is as it was.
        self.assertEqual(turned_pose(self.turn, {}, pose, self.side, self.side, moved={}), pose)

    def test_facing_left_it_is_the_same_body_in_a_mirror_limb_for_limb(self) -> None:
        moved = {"arm_right": (1.5, -0.5), "leg_left": (-0.75, 0.25)}
        right = self.plan.pose(DOLL_FACINGS["right"], "walk", 0.3)
        left = self.plan.pose(DOLL_FACINGS["left"], "walk", 0.3)
        _, _, mirrored, swapped = FACINGS[DOLL_FACINGS["left"]]
        for yaw in (self.side, 30.0, 0.0):
            seen_right = turned_pose(self.turn, {}, right, yaw, self.side, moved=moved)
            seen_left = turned_pose(self.turn, {}, left, yaw, self.side, mirrored, swapped, moved)
            # What is drawn on the near arm of one is drawn on the near arm of the other: the
            # joints a body in a mirror calls by the names of the other side.
            for joint, (x, y) in seen_right.items():
                self.assertAlmostEqual(seen_left[other_side(joint)][0], -x, places=6, msg=(yaw, joint))
                self.assertAlmostEqual(seen_left[other_side(joint)][1], y, places=6, msg=(yaw, joint))


class PlacingInTheGameTests(unittest.TestCase):
    """Limbs and pieces of a face put in place on the screen residents are drawn on, in the real game."""

    def setUp(self) -> None:
        for variable in ("SDL_VIDEODRIVER", "SDL_AUDIODRIVER"):
            self.addCleanup(self._restore, variable, os.environ.get(variable))
            os.environ[variable] = "dummy"
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name) / "illustrations"
        self.root.mkdir()
        self.addCleanup(pygame.quit)
        self.window = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
        base = load_template()
        plain = figures(base.built(base.starting()), tones_of(SKIN, LINE), 5)
        for canvas, drawing in plain.items():
            path = self.root / doll_path("raul", canvas)
            path.parent.mkdir(parents=True, exist_ok=True)
            pygame.image.save(drawing, str(path))
        (self.root / build_path("raul")).write_text(json.dumps(base.starting().to_data()), encoding="utf-8")
        from game.game import Game

        self.game = Game(illustrations_dir=self.root, voices_dir=None, start_in_menu=False)
        self.studio = self.game.doll_editor
        self.studio.open("raul")
        self.game.scene_name = "editor"
        self.frame()

    @staticmethod
    def _restore(variable: str, previous: str | None) -> None:
        if previous is None:
            os.environ.pop(variable, None)
        else:
            os.environ[variable] = previous

    def frame(self) -> None:
        self.game.active_scene.update(1 / 60)
        self.game.active_scene.render()
        self.game.present(self.window)

    def mouse(self, kind: int, position: tuple[float, float], **more) -> None:
        at = (round(position[0]) * SCALE + 1, round(position[1]) * SCALE + 1)
        self.game.active_scene.handle_event(pygame.event.Event(kind, pos=at, **more))

    def press(self, intent: tuple) -> None:
        at = next(button for button in self.studio.buttons if button.intent == intent).rect.center
        self.mouse(pygame.MOUSEBUTTONDOWN, at, button=1)
        self.mouse(pygame.MOUSEBUTTONUP, at, button=1)

    def key(self, key: int, mod: int = 0) -> None:
        self.game.active_scene.handle_event(pygame.event.Event(pygame.KEYDOWN, key=key, mod=mod, unicode=""))

    def spot(self, limb: str) -> tuple[float, float]:
        return next(spot for _, name, spot in self.studio.body.figure_handles() if name == limb)

    def pull(self, limb: str, by: tuple[int, int]) -> None:
        start = self.spot(limb)
        end = (round(start[0]) + by[0], round(start[1]) + by[1])
        self.mouse(pygame.MOUSEBUTTONDOWN, start, button=1)
        self.mouse(pygame.MOUSEMOTION, end, buttons=(1, 0, 0), rel=by)
        self.mouse(pygame.MOUSEBUTTONUP, end, button=1)

    def test_a_limb_is_put_in_place_by_itself_in_each_view_and_kept(self) -> None:
        studio, body = self.studio, self.studio.body
        rules = studio.faces.rules
        self.press(("tool", MEASURE_TOOL))
        self.frame()
        # Measured, it is seen from its side to begin with, and there is a tile for each view.
        self.assertEqual(body.measure_view, "profile")
        self.assertTrue(studio.placing)
        for view in rules.views:
            self.assertTrue(any(button.intent == ("view", view) for button in studio.buttons), view)
        self.assertFalse(any(button.intent[0] == "clip" for button in studio.buttons), "it stands still while it is measured")
        per_unit = body._per_unit
        far_arm = self.spot("arm_left")
        self.pull("arm_right", (round(per_unit), 0))
        self.assertEqual(body.limb_keys, {"profile": {"arm_right": (round(round(per_unit) / per_unit, 2), 0.0)}})
        self.assertEqual(self.spot("arm_left"), far_arm, "the other arm is where it was")
        self.assertEqual(body.chosen_limb, "arm_right")
        # From the front it is another say: what was said from the side is no part of it.
        self.press(("view", "front"))
        self.frame()
        self.assertEqual(body.measure_view, "front")
        self.assertFalse(any(kind == "point" for kind, _, _ in body.figure_handles()), "a head is moved from the side alone")
        before = self.spot("leg_left")
        self.pull("leg_left", (6, -3))
        self.assertEqual(set(body.limb_keys), {"profile", "front"})
        self.assertEqual(set(body.limb_keys["front"]), {"leg_left"})
        now = self.spot("leg_left")
        self.assertAlmostEqual(now[0] - before[0], 6, delta=0.2)
        self.assertAlmostEqual(now[1] - before[1], -3, delta=0.2)
        # The keys move the one in hand a little at a time, and further with Shift held.
        was = body.limb_keys["front"]["leg_left"]
        self.key(pygame.K_RIGHT)
        self.key(pygame.K_DOWN, pygame.KMOD_SHIFT)
        moved = body.limb_keys["front"]["leg_left"]
        self.assertAlmostEqual(moved[0], was[0] + NUDGE, places=2)
        self.assertAlmostEqual(moved[1], was[1] + NUDGE * 5, places=2)
        self.frame()
        # Kept, it is what the settlement shows of them.
        self.press(("save",))
        kept = json.loads((self.root / build_path("raul")).read_text(encoding="utf-8"))
        self.assertEqual(set(kept[LIMBS_KEY]), {"profile", "front"})
        cast = self.game.figures
        self.assertEqual(cast.said("raul").limbs["front"]["leg_left"], moved)
        doll = self.game.dolls.get("raul")
        shown = cast.shown("raul", doll)
        self.assertEqual(set(shown.moved), {"arm_right"})
        pose = doll.plan.pose(DOLL_FACINGS["right"])
        self.assertNotEqual(cast.posed(shown, pose, DOLL_FACINGS["right"])["hand_right"], pose["hand_right"])
        for now, was in zip(cast.posed(shown, pose, DOLL_FACINGS["right"])["hand_left"], pose["hand_left"]):
            self.assertAlmostEqual(now, was, places=9)
        # And one tile puts back the one in hand in the view in hand, or all of them.
        self.press(("limbs_auto",))
        self.assertNotIn("front", body.limb_keys)
        self.assertIn("profile", body.limb_keys)
        self.press(("view", "profile"))
        self.frame()
        corner = (body.preview_rect.x + 4, body.preview_rect.bottom - 4)
        self.mouse(pygame.MOUSEBUTTONDOWN, corner, button=1)
        self.mouse(pygame.MOUSEBUTTONUP, corner, button=1)
        self.assertIsNone(body.chosen_limb)
        self.press(("limbs_auto",))
        self.assertEqual(body.limb_keys, {})

    def test_each_piece_of_a_face_goes_by_itself_and_the_keys_move_it_a_little(self) -> None:
        studio, face = self.studio, self.studio.face
        self.press(("tab", FACE_TAB))
        self.press(("mannequin",))
        self.assertTrue(studio.arranging and studio.placing)
        self.assertFalse(face.symmetric)
        # The same tiles for the views as limbs have.
        self.press(("view", "front"))
        self.frame()
        self.assertEqual(face.view, "front")
        near, far = face._key("eye_near"), face._key("eye_far")
        at = (face.stage.x + round(near.x * face.stage_zoom), face.stage.y + round(near.y * face.stage_zoom))
        self.mouse(pygame.MOUSEBUTTONDOWN, at, button=1)
        self.mouse(pygame.MOUSEBUTTONUP, at, button=1)
        self.assertEqual(face.chosen, "eye_near")
        self.key(pygame.K_LEFT)
        self.key(pygame.K_UP, pygame.KMOD_SHIFT)
        moved = face._key("eye_near")
        self.assertAlmostEqual(moved.x, near.x - 0.5)
        self.assertAlmostEqual(moved.y, near.y - 2.0)
        self.assertEqual(face._key("eye_far"), far, "the other eye is where it was")
        self.press(("view", "profile"))
        self.frame()
        self.assertEqual(face.view, "profile")


if __name__ == "__main__":
    unittest.main()
