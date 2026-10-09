"""Armour drawn once over the plain figure and laid over any body (P66), and the screen it is drawn in."""

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import pygame

from graphics import tailor
from graphics.doll import (
    BODY_CANVAS,
    HEAD_CANVAS,
    DollBuild,
    DollStore,
    Garment,
    _grown,
    doll_path,
    draw_doll,
    garment_file,
    garment_path,
    load_template,
    template_from_data,
)
from graphics.doll_guide import piece_zone, reference
from graphics.illustrations import Illustrations
from graphics.mannequin import figures, tones_of
from graphics.tailor import Tailor
from scenes.hud import DRAW_INTENT
from settings import SCALE, SCREEN_HEIGHT, SCREEN_WIDTH
from skeleton.plan import PLAN_PATH, builtin_plan
from skeleton.rig import Skeleton

SKIN, STEEL, RUST, MARK = (214, 168, 130), (40, 60, 220), (220, 40, 40), (30, 220, 60)
# What is painted in the fitting room: a colour nobody is shown in until somebody draws them.
PAINT = (250, 30, 240)
THICK = 6


def _painted(surface: pygame.Surface) -> pygame.mask.Mask:
    return pygame.mask.from_surface(surface)


def _of_color(surface: pygame.Surface, color: tuple[int, int, int]) -> pygame.mask.Mask:
    return pygame.mask.from_threshold(surface, (*color, 255), (40, 40, 40, 255))


def _box(mask: pygame.mask.Mask) -> pygame.Rect:
    boxes = mask.get_bounding_rects()
    return boxes[0].unionall(boxes[1:]) if boxes else pygame.Rect(0, 0, 0, 0)


@unittest.skipUnless(tailor.AVAILABLE, "laying a piece over a body needs numpy")
class TailorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.base = load_template()
        self.start = self.base.starting()
        # The paper a piece is drawn on: the figure with the measures every doll starts from.
        self.paper = self.base.built(self.start)
        self.tailor = Tailor(self.base)

    def _figure(self, build: DollBuild | None = None) -> dict[str, pygame.Surface]:
        """The plain figure as somebody's drawings, with their measures."""
        return figures(self.base.built(build or self.start), tones_of(SKIN, SKIN))

    def _own(self, bone: str, template=None) -> pygame.mask.Mask:
        return piece_zone(template or self.paper, (bone,))

    def _shell(self, slot: str, color=STEEL, thick: int = THICK) -> Garment:
        """A piece that covers every part of its slot on the figure, and goes a little past its skin."""
        sheets = {}
        for bone in self.paper.worn_on(slot):
            canvas = self.paper.parts[bone].canvas
            sheet = sheets.setdefault(canvas, pygame.Surface(self.paper.canvases[canvas], pygame.SRCALPHA))
            figure = _painted(reference(self.paper, canvas)).overlap_mask(self._own(bone), (0, 0))
            _grown(figure, thick).overlap_mask(self._own(bone), (0, 0)).to_surface(sheet, setcolor=(*color, 255), unsetcolor=None)
        return Garment(slot, slot, sheets, self.start)

    def _fitted(self, garment: Garment, drawings: dict[str, pygame.Surface], build: DollBuild | None = None):
        template = self.base.built(build or self.start)
        return self.tailor.fitted(garment, self.tailor.bodies(template, drawings))

    def _reshaped(self, by: int) -> dict[str, pygame.Surface]:
        """The figure made stouter by so many pixels all round, or thinner by as many if fewer than none."""
        drawings = self._figure()
        shape = _painted(drawings[BODY_CANVAS])
        if by > 0:
            _grown(shape, by).to_surface(drawings[BODY_CANVAS], setcolor=(*SKIN, 255), unsetcolor=None)
        else:
            clear = pygame.Mask(shape.get_size(), fill=True)
            clear.erase(shape, (0, 0))
            _grown(clear, -by).to_surface(drawings[BODY_CANVAS], setcolor=(0, 0, 0, 0), unsetcolor=None)
        return drawings

    def test_where_things_are_worn_is_data_and_names_parts_of_either_side(self) -> None:
        slots = {slot.slot_id: slot for slot in self.base.wear}
        self.assertLessEqual({"mask", "helmet", "torso", "legs", "shoulders"}, set(slots))
        self.assertLess(list(slots).index("mask"), list(slots).index("helmet"), "a helmet goes over a mask")
        self.assertEqual(self.base.worn_on("shoulders"), ["upper_arm_left", "upper_arm_right"])
        self.assertEqual(self.base.worn_on("helmet"), ["skull"])
        self.assertEqual(self.base.worn_on("no such place"), [])
        data = json.loads(PLAN_PATH.read_text(encoding="utf-8"))["doll"]
        data["wear"] = {"tail": {"name": "Cola", "parts": ["tail"]}}
        with self.assertRaises(ValueError):
            template_from_data(data)

    def test_on_the_figure_it_was_drawn_over_a_piece_is_as_it_was_drawn(self) -> None:
        garment = self._shell("torso")
        figure = {canvas: reference(self.paper, canvas) for canvas in self.paper.canvases}
        laid = self._fitted(garment, figure)[BODY_CANVAS]
        drawn, now = _painted(garment.drawings[BODY_CANVAS]), _painted(laid)
        apart = drawn.count() + now.count() - 2 * drawn.overlap_area(now, (0, 0))
        self.assertLess(apart, drawn.count() * 0.03, "but for the pixels along its edge")
        self.assertGreater(_of_color(laid, STEEL).count(), drawn.count() * 0.9, "and of the colour it was painted")

    def test_on_a_stout_body_no_skin_shows_beside_a_piece_and_on_a_thin_one_it_does_not_float(self) -> None:
        garment = self._shell("torso")
        spine = self.paper.parts["spine"]
        middle = round((spine.start[1] + spine.end[1]) / 2)
        wide = {}
        for name, by in (("stout", 12), ("as drawn", 0), ("thin", -6)):
            drawings = self._reshaped(by) if by else self._figure()
            laid = _painted(self._fitted(garment, drawings)[BODY_CANVAS])
            trunk = _painted(drawings[BODY_CANVAS]).overlap_mask(self._own("spine"), (0, 0))
            bare = trunk.count() - trunk.overlap_area(laid, (0, 0))
            self.assertLess(bare, trunk.count() * 0.02, f"{name}: the trunk is under the piece")
            row = pygame.Mask(laid.get_size())
            row.draw(pygame.Mask((laid.get_size()[0], 1), fill=True), (0, middle))
            body_wide = _box(trunk.overlap_mask(row, (0, 0))).width
            wide[name] = _box(laid.overlap_mask(row, (0, 0))).width
            # Past the skin it is about as thick as it was drawn, never several times that.
            self.assertGreater(wide[name], body_wide, name)
            self.assertLess(wide[name], body_wide + 4 * THICK, f"{name}: it lies close to the skin")
        self.assertGreater(wide["stout"], wide["as drawn"] + 12)
        self.assertLess(wide["thin"], wide["as drawn"] - 6)

    def test_on_a_body_drawn_as_a_stick_each_leg_wears_its_own_trouser_leg_and_no_other(self) -> None:
        drawings = self._figure()
        body = drawings[BODY_CANVAS]
        body.fill((0, 0, 0, 0))
        legs = {}
        for side in ("left", "right"):
            thigh, shin = self.paper.parts[f"thigh_{side}"], self.paper.parts[f"shin_{side}"]
            pygame.draw.line(body, (*SKIN, 255), thigh.start, shin.end, 3)
            legs[side] = thigh.start[0]
        laid = _painted(self._fitted(self._shell("legs"), drawings)[BODY_CANVAS])
        for side, middle in legs.items():
            zone = self._own(f"thigh_{side}")
            zone.draw(self._own(f"shin_{side}"), (0, 0))
            box = _box(laid.overlap_mask(zone, (0, 0)))
            self.assertGreater(box.height, 60, f"the {side} leg is in its trouser leg")
            # A thin leg has a thin trouser leg, close about it, and nothing of the other one's
            # beside it: seen from the figure's paper that one is not far off.
            self.assertLess(box.width, 3 + 4 * THICK, side)
            self.assertAlmostEqual(box.centerx, middle, delta=3)

    def test_longer_legs_make_longer_trousers_with_the_hem_as_far_down_the_shin(self) -> None:
        garment = self._shell("legs")
        shin = self.paper.parts["shin_right"]
        at = 0.8
        hem = shin.start[1] + (shin.end[1] - shin.start[1]) * at
        pygame.draw.line(garment.drawings[BODY_CANVAS], (*MARK, 255), (shin.start[0] - 12, hem), (shin.start[0] + 12, hem), 3)
        build = self.start.copy()
        build.joints["shin.end"] = build.joints.get("shin.end", 0.0) + 1.5
        build.joints["thigh.end"] = build.joints.get("thigh.end", 0.0) + 1.0
        self.assertTrue(self.base.takes(build))
        longer = self.base.built(build).parts["shin_right"]
        self.assertGreater(longer.end[1] - longer.start[1], shin.end[1] - shin.start[1] + 20)
        laid = self._fitted(garment, self._figure(build), build)[BODY_CANVAS]
        mark = _box(_of_color(laid, MARK))
        self.assertGreater(mark.width, 10, "the hem is still there")
        self.assertAlmostEqual(mark.centery, longer.start[1] + (longer.end[1] - longer.start[1]) * at, delta=3)
        # And the trousers go from the top of the leg to the ankle, as they did.
        thigh = self.base.built(build).parts["thigh_right"]
        legs = _box(_painted(laid).overlap_mask(self._own("shin_right", self.base.built(build)), (0, 0)))
        self.assertAlmostEqual(legs.bottom, longer.end[1], delta=3)
        self.assertLess(_box(_painted(laid)).top, thigh.start[1])

    def test_nothing_of_a_piece_is_laid_where_its_slot_has_no_part(self) -> None:
        garment = self._shell("torso")
        # Somebody painted on an arm too, with the piece for the trunk in hand.
        arm = self.paper.parts["upper_arm_right"]
        pygame.draw.circle(garment.drawings[BODY_CANVAS], (*RUST, 255), arm.start, 14)
        laid = _painted(self._fitted(garment, self._reshaped(8))[BODY_CANVAS])
        may = pygame.Mask(laid.get_size())
        for bone in self.paper.worn_on("torso"):
            may.draw(self._own(bone), (0, 0))
        self.assertGreater(laid.count(), 1000)
        self.assertEqual(laid.count(), laid.overlap_area(may, (0, 0)))

    def test_where_nothing_of_a_part_is_drawn_nothing_is_worn_on_it(self) -> None:
        drawings = self._figure()
        for bone in self.paper.parts:
            if "arm" in bone or "hand" in bone:
                _painted(self.paper.mask(bone)).to_surface(drawings[BODY_CANVAS], setcolor=(0, 0, 0, 0), unsetcolor=None)
        laid = self._fitted(self._shell("shoulders"), drawings)
        self.assertEqual(_painted(laid[BODY_CANVAS]).count(), 0, "no arms, no pauldrons")
        # And a body with no head drawn at all has nowhere to wear a helmet.
        del drawings[HEAD_CANVAS]
        self.assertEqual(self._fitted(self._shell("helmet"), drawings), {})

    def test_a_helmet_goes_to_a_head_of_any_size_wherever_it_is_on_its_paper(self) -> None:
        garment = self._shell("helmet")
        size = self.paper.canvases[HEAD_CANVAS]
        drawings = self._figure()
        head = pygame.Surface(size, pygame.SRCALPHA)
        centre, radius = (size[0] - 40, 44), 26
        pygame.draw.circle(head, (*SKIN, 255), centre, radius)
        drawings[HEAD_CANVAS] = head
        laid = _painted(self._fitted(garment, drawings)[HEAD_CANVAS])
        box = _box(laid)
        self.assertAlmostEqual(box.centerx, centre[0], delta=4)
        self.assertAlmostEqual(box.centery, centre[1], delta=4)
        self.assertGreater(box.width, radius * 2, "it goes over the head")
        self.assertLess(box.width, radius * 2 + 4 * THICK, "and no further past it than it was drawn")
        skull = _painted(head)
        self.assertLess(skull.count() - skull.overlap_area(laid, (0, 0)), skull.count() * 0.02)
        self.assertLess(box.width, _box(_painted(garment.drawings[HEAD_CANVAS])).width * 0.7, "smaller than on the figure")

    def test_a_mask_is_under_the_helmet_and_both_over_the_head(self) -> None:
        skull = self.paper.parts["skull"]
        size = self.paper.canvases[HEAD_CANVAS]
        mask = Garment("mask", "mask", {HEAD_CANVAS: pygame.Surface(size, pygame.SRCALPHA)}, self.start)
        helmet = Garment("helmet", "helmet", {HEAD_CANVAS: pygame.Surface(size, pygame.SRCALPHA)}, self.start)
        pygame.draw.circle(mask.drawings[HEAD_CANVAS], (*RUST, 255), skull.end, 24)
        pygame.draw.circle(helmet.drawings[HEAD_CANVAS], (*STEEL, 255), skull.end, 12)
        drawings = self._figure()
        before = drawings[HEAD_CANVAS].copy()
        for order in ((mask, helmet), (helmet, mask)):
            dressed = self.tailor.dressed(self.paper, drawings, order)[HEAD_CANVAS]
            self.assertEqual(tuple(dressed.get_at((round(skull.end[0]), round(skull.end[1]))))[:3], STEEL)
            self.assertEqual(tuple(dressed.get_at((round(skull.end[0]) + 18, round(skull.end[1]))))[:3], RUST)
        self.assertEqual(pygame.image.tobytes(drawings[HEAD_CANVAS], "RGBA"), pygame.image.tobytes(before, "RGBA"))
        self.assertIs(self.tailor.dressed(self.paper, drawings, [])[HEAD_CANVAS], drawings[HEAD_CANVAS])

    def test_a_doll_with_pieces_on_bends_and_turns_as_it_did(self) -> None:
        plan = builtin_plan()
        store = DollStore(None, self.base, plan)
        bare = store.made(self._figure(), self.start)
        worn = self.tailor.dress(bare, [self._shell("torso"), self._shell("shoulders", RUST), self._shell("legs", MARK)])
        self.assertEqual(set(worn.parts), set(bare.parts))
        self.assertEqual(set(worn.limbs), set(bare.limbs))
        for facing in ("doll_right", "doll_left"):
            skeleton = Skeleton(worn.plan, facing)
            skeleton.set_pose(worn.plan.pose(facing, "walk", 0.25))
            picture = pygame.Surface((400, 500), pygame.SRCALPHA)
            draw_doll(picture, worn, worn.plan, skeleton, (200, 460), 12.0)
            for color in (STEEL, RUST, MARK):
                self.assertGreater(_of_color(picture, color).count(), 300, (facing, color))
        self.assertEqual(worn.standing(worn.plan)[3], bare.standing(bare.plan)[3], "it stands on the same ground")

    def test_without_numpy_nobody_is_seen_to_wear_anything(self) -> None:
        drawings = self._figure()
        with mock.patch.object(tailor, "AVAILABLE", False):
            dressed = self.tailor.dressed(self.paper, drawings, [self._shell("torso")])
        self.assertEqual(dressed, drawings)
        self.assertIs(dressed[BODY_CANVAS], drawings[BODY_CANVAS])


@unittest.skipUnless(tailor.AVAILABLE, "laying a piece over a body needs numpy")
class WardrobeTests(unittest.TestCase):
    """Pieces kept in the illustrations folder, and the dolls cut with them on."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        self.base = load_template()
        self.start = self.base.starting()
        self.paper = self.base.built(self.start)
        for name in ("ana", "blas"):
            for canvas, drawing in figures(self.paper, tones_of(SKIN, SKIN)).items():
                path = self.root / doll_path(name, canvas)
                path.parent.mkdir(parents=True, exist_ok=True)
                pygame.image.save(drawing, str(path))
        self._keep("plate", "torso", STEEL)
        self.store = DollStore(Illustrations(self.root), self.base, builtin_plan())

    def _keep(self, garment_id: str, slot: str, color: tuple[int, int, int], build: DollBuild | None = None) -> None:
        sheet = pygame.Surface(self.paper.canvases[BODY_CANVAS], pygame.SRCALPHA)
        spine = self.paper.parts["spine"]
        pygame.draw.circle(sheet, (*color, 255), ((spine.start[0] + spine.end[0]) / 2, (spine.start[1] + spine.end[1]) / 2), 30)
        path = self.root / garment_path(garment_id, BODY_CANVAS)
        path.parent.mkdir(parents=True, exist_ok=True)
        pygame.image.save(sheet, str(path))
        data = {"slot": slot, "build": (build or self.start).to_data()}
        (self.root / garment_file(garment_id)).write_text(json.dumps(data), encoding="utf-8")

    def test_a_piece_is_read_with_its_slot_and_the_measures_it_was_drawn_over(self) -> None:
        plate = self.store.garment("plate")
        self.assertEqual((plate.garment_id, plate.slot), ("plate", "torso"))
        self.assertEqual(plate.build.to_data(), self.start.to_data())
        self.assertEqual(set(plate.drawings), {BODY_CANVAS})
        self.assertIsNone(self.store.garment("nothing"))
        self._keep("odd", "tail", RUST)
        self.assertIsNone(self.store.garment("odd"), "a piece for a slot there is not is nobody's to wear")
        self.assertIsNone(DollStore(None, self.base).garment("plate"), "nor is there any with nowhere to keep them")

    def test_a_doll_is_cut_with_its_pieces_on_once_and_again_when_one_is_drawn_anew(self) -> None:
        ana = self.store.get("ana")
        worn = self.store.dressed(ana, ("plate",))
        self.assertIsNot(worn, ana)
        self.assertIs(self.store.dressed(ana, ["plate"]), worn, "kept, however it is asked for")
        self.assertGreater(_of_color(worn.sheets[BODY_CANVAS], STEEL).count(), 1000)
        self.assertEqual(_of_color(ana.sheets[BODY_CANVAS], STEEL).count(), 0, "their own drawing is as it was")
        self.assertIs(self.store.dressed(ana, ()), ana)
        self.assertIs(self.store.dressed(ana, ("nothing",)), ana)
        self.assertIsNone(self.store.dressed(None, ("plate",)))
        self._keep("plate", "torso", RUST)
        self.store.forget_garment("plate")
        again = self.store.dressed(ana, ("plate",))
        self.assertIsNot(again, worn)
        self.assertGreater(_of_color(again.sheets[BODY_CANVAS], RUST).count(), 1000)
        # And when they are drawn anew themselves.
        self.store.forget("ana")
        self.assertIsNot(self.store.dressed(self.store.get("ana"), ("plate",)), again)

    def test_whoever_counts_frames_has_one_cut_in_each(self) -> None:
        ana, blas = self.store.get("ana"), self.store.get("blas")
        self.assertIsNot(self.store.dressed(ana, ("plate",), in_turn=True), ana)
        self.assertIs(self.store.dressed(blas, ("plate",), in_turn=True), blas, "seen as they were until their turn")
        self.assertIsNot(self.store.dressed(ana, ("plate",), in_turn=True), ana, "one that is kept is shown at once")
        self.store.new_frame()
        self.assertIsNot(self.store.dressed(blas, ("plate",), in_turn=True), blas)


@unittest.skipUnless(tailor.AVAILABLE, "laying a piece over a body needs numpy")
class FittingRoomTests(unittest.TestCase):
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

    def _stroke(self, start: tuple[int, int], end: tuple[int, int]) -> None:
        self._event(pygame.MOUSEBUTTONDOWN, start, button=1)
        self._event(pygame.MOUSEMOTION, end, buttons=(1, 0, 0), rel=(0, 0))
        self._event(pygame.MOUSEBUTTONUP, end, button=1)

    def _press(self, intent: tuple) -> None:
        editor = self.game.active_scene
        self._click(next(button for button in editor.buttons if button.intent == intent).rect.center)

    def _open(self, resident_id: str):
        view = self.game.global_view
        view.hud.select_resident(resident_id)
        self._click(next(button for button in view.hud.menu if button.intent == DRAW_INTENT).rect.center)
        self.game.sync_scenes()
        self._press(("fitting",))
        self.game.sync_scenes()
        self.assertEqual(self.game.scene_name, "garment_editor")
        return self.game.garment_editor

    def _on(self, editor, canvas: str, point: tuple[float, float]) -> tuple[int, int]:
        area = editor.areas[canvas]
        return (round(area.x + point[0]), round(area.y + point[1]))

    def _paint_shoulder(self, editor) -> None:
        self._press(("slot", "shoulders"))
        arm = editor.template.parts["upper_arm_right"]
        editor.size, editor.color = 18, PAINT
        for down in (0, 14, 28):
            self._stroke(
                self._on(editor, BODY_CANVAS, (arm.start[0] - 20, arm.start[1] + down)),
                self._on(editor, BODY_CANVAS, (arm.start[0] + 20, arm.start[1] + down)),
            )

    def test_the_fitting_room_is_a_step_from_the_drawing_and_goes_back_to_it_as_it_was_left(self) -> None:
        self.game.global_view.hud.select_resident("marta")
        view = self.game.global_view
        self._click(next(button for button in view.hud.menu if button.intent == DRAW_INTENT).rect.center)
        self.game.sync_scenes()
        doll_editor = self.game.doll_editor
        trunk = doll_editor.template.parts["spine"]
        self._stroke(self._on(doll_editor, BODY_CANVAS, trunk.start), self._on(doll_editor, BODY_CANVAS, trunk.end))
        drawn = _painted(doll_editor.drawings[BODY_CANVAS]).count()
        self.assertGreater(drawn, 0)
        self._press(("fitting",))
        self.game.sync_scenes()
        editor = self.game.active_scene
        self.assertIs(editor, self.game.garment_editor)
        self.assertEqual(editor.resident_id, "marta", "tried on whoever was being drawn")
        self.assertEqual({button.intent[1] for button in editor.buttons if button.intent[0] == "slot"}, set(editor.worn))
        self.assertFalse(any(button.intent in (("mannequin",), ("measures",), ("fitting",)) for button in editor.buttons))
        frozen = self.game.world.clock.total_minutes
        self.game.advance_simulation(5.0)
        self.assertEqual(self.game.world.clock.total_minutes, frozen, "time stands still there too")
        self._show()
        self.game.handle_key(pygame.K_ESCAPE)
        self.game.active_scene.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE, mod=0))
        self.game.sync_scenes()
        self.assertEqual(self.game.scene_name, "editor")
        self.assertEqual(_painted(self.game.doll_editor.drawings[BODY_CANVAS]).count(), drawn, "the drawing is as it was left")
        self.assertFalse((self.root / "garments").exists(), "and nothing was kept that was not saved")

    def test_a_piece_is_painted_only_where_it_is_worn_and_seen_on_whoever_it_is_tried_on(self) -> None:
        editor = self._open("marta")
        self.assertEqual(_of_color(editor._preview.sheets[BODY_CANVAS], PAINT).count(), 0)
        self._paint_shoulder(editor)
        painted = _painted(editor.drawings[BODY_CANVAS])
        self.assertGreater(painted.count(), 800)
        # A stroke down a leg, with the pauldrons in hand, leaves nothing.
        shin = editor.template.parts["shin_right"]
        self._stroke(self._on(editor, BODY_CANVAS, shin.start), self._on(editor, BODY_CANVAS, shin.end))
        self._click(self._on(editor, HEAD_CANVAS, editor.template.parts["skull"].end))
        self.assertEqual(_painted(editor.drawings[BODY_CANVAS]).count(), painted.count())
        self.assertEqual(_painted(editor.drawings[HEAD_CANVAS]).count(), 0)
        self.assertEqual(painted.count(), painted.overlap_area(editor.allowed(BODY_CANVAS), (0, 0)))
        # Beside the paper it is on them: on their own doll, cut with the piece.
        self.assertGreater(_of_color(editor._preview.sheets[BODY_CANVAS], PAINT).count(), 200)
        self.assertIn("upper_arm_right", editor._preview.parts)
        window = self._show()
        place = editor.layers.on_screen(pygame.Rect(604, 272, 192, 170))
        self.assertGreater(_of_color(window.subsurface(place), PAINT).count(), 50, "and is seen on the figure that moves")
        # Undone, stroke by stroke, it is off them again.
        while editor._undo:
            editor.undo()
        self.assertEqual(_painted(editor.drawings[BODY_CANVAS]).count(), 0)
        self.assertEqual(_of_color(editor._preview.sheets[BODY_CANVAS], PAINT).count(), 0)

    def test_stepping_tries_the_same_piece_on_the_next_resident(self) -> None:
        editor = self._open("marta")
        self._paint_shoulder(editor)
        before = pygame.image.tobytes(editor.drawings[BODY_CANVAS], "RGBA")
        first = editor._preview
        self._press(("step", 1))
        self.assertNotEqual(editor.resident_id, "marta")
        self.assertIsNot(editor._preview, first)
        self.assertGreater(_of_color(editor._preview.sheets[BODY_CANVAS], PAINT).count(), 200)
        self.assertEqual(pygame.image.tobytes(editor.drawings[BODY_CANVAS], "RGBA"), before, "the drawing is the same")
        self._press(("step", -1))
        self.assertEqual(editor.resident_id, "marta")

    def test_the_far_side_wears_what_was_painted_for_the_near_one(self) -> None:
        editor = self._open("marta")
        self._paint_shoulder(editor)
        near = piece_zone(editor.template, ("upper_arm_right",))
        far = piece_zone(editor.template, ("upper_arm_left",))
        painted = _painted(editor.drawings[BODY_CANVAS])
        self.assertEqual(painted.overlap_area(far, (0, 0)), 0)
        self._press(("mirror",))
        painted = _painted(editor.drawings[BODY_CANVAS])
        self.assertEqual(painted.overlap_area(far, (0, 0)), painted.overlap_area(near, (0, 0)))
        editor.undo()
        self.assertEqual(_painted(editor.drawings[BODY_CANVAS]).overlap_area(far, (0, 0)), 0)

    def test_saved_pieces_are_kept_and_shown_on_everybody_on_the_map_while_the_switch_is_on(self) -> None:
        editor = self._open("marta")
        view = self.game.global_view
        bare = view._doll_of("marta")
        self._paint_shoulder(editor)
        self.assertEqual(view.trying_on, ())
        self._press(("on_map",))
        self.assertTrue(editor.on_map)
        self.assertTrue((self.root / garment_path("shoulders", BODY_CANVAS)).is_file(), "showing them keeps them first")
        kept = json.loads((self.root / garment_file("shoulders")).read_text(encoding="utf-8"))
        self.assertEqual(kept["slot"], "shoulders")
        self.assertEqual(kept["build"], editor.build.to_data())
        self.assertFalse((self.root / garment_file("helmet")).exists(), "a piece with nothing painted is not kept")
        self.assertEqual(view.trying_on, editor.worn)
        self.game.present(self.window)
        worn = view._doll_of("marta")
        self.assertIsNot(worn, bare)
        self.assertGreater(_of_color(worn.sheets[BODY_CANVAS], PAINT).count(), 200)
        # It is how they are shown and no more: nothing of it is in what is saved of the settlement.
        self.assertNotIn("shoulders", json.dumps(self.game.saves.to_data(self.game.world)))
        # Opened again, the piece is there to go on with. Cleared and saved, it is gone.
        self._press(("close",))
        self.game.sync_scenes()
        self._press(("fitting",))
        self.game.sync_scenes()
        editor = self.game.garment_editor
        self._press(("slot", "shoulders"))
        self.assertGreater(_painted(editor.drawings[BODY_CANVAS]).count(), 800)
        self._press(("clear",))
        self._press(("save",))
        self.assertFalse((self.root / garment_file("shoulders")).exists())
        self.assertFalse((self.root / garment_path("shoulders", BODY_CANVAS)).exists())
        self.game.present(self.window)
        self.assertEqual(_of_color(view._doll_of("marta").sheets[BODY_CANVAS], PAINT).count(), 0)
        self._press(("on_map",))
        self.assertEqual(view.trying_on, ())


if __name__ == "__main__":
    unittest.main()
