import math
import os
import tempfile
import unittest
from pathlib import Path

import pygame

from graphics.doll import BODY_CANVAS, HEAD_CANVAS, Doll, DollStore, doll_path, draw_doll, load_template
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

    def test_every_part_is_a_bone_drawn_as_long_as_the_skeleton_has_it(self) -> None:
        unit = self.template.unit
        self.assertEqual(set(self.template.canvases), {BODY_CANVAS, HEAD_CANVAS})
        for bone, spec in self.template.parts.items():
            self.assertIn(bone, self.plan.bones)
            # One scale then fits every part: a drawing is never stretched along a bone.
            self.assertAlmostEqual(math.dist(spec.start, spec.end) / unit, self.plan.length("side", bone), 5, bone)
        self.assertLessEqual(set(self.template.parts), set(self.plan.orders["side"]), "every part has its turn to be drawn")

    def test_zones_only_overlap_where_two_parts_are_jointed(self) -> None:
        masks = {bone: pygame.mask.from_surface(self.template.mask(bone)) for bone, spec in self.template.parts.items() if not spec.whole}
        for bone, mask in masks.items():
            width, height = self.template.canvases[BODY_CANVAS]
            self.assertEqual(mask.get_bounding_rects()[0].clip(pygame.Rect(0, 0, width, height)), mask.get_bounding_rects()[0], bone)
            for other, other_mask in masks.items():
                jointed = self.plan.bones[bone].end == self.plan.bones[other].start or self.plan.bones[other].end == self.plan.bones[bone].start
                if bone < other and not jointed:
                    self.assertEqual(mask.overlap_area(other_mask, (0, 0)), 0, (bone, other))
            lower = [other for other in masks if self.plan.bones[bone].end == self.plan.bones[other].start]
            for other in lower:
                self.assertGreater(mask.overlap_area(masks[other], (0, 0)), 0, f"{bone} and {other} must overlap at their joint")

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
        reach = self.plan.length("side", "forearm_right") * detail
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
        shin = self.template.parts["shin_right"]
        pygame.draw.circle(figure[BODY_CANVAS], BLUE, (shin.end[0] + shin.cap[0] + 10, shin.end[1]), 8)
        doll = Doll(self.template, figure)
        pictures = {}
        for facing in ("right", "left"):
            skeleton = Skeleton(self.plan, facing)
            skeleton.set_pose(self.plan.pose(facing, "walk", 0.2))
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
            skeleton = Skeleton(self.plan, "right", lost)
            skeleton.set_pose(self.plan.pose("right", "fight", 0.3))
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

        self.game = Game(illustrations_dir=self.root)
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
        spot = ((body.x + 128) * SCALE, (body.y + 100) * SCALE)
        with_guide = tuple(self._show().get_at(spot))[:3]
        self._click(editor.guide_button.rect.center)
        self._click(editor.guide_button.rect.center)
        self.assertEqual(editor.guide, "off")
        self.assertNotEqual(tuple(self._show().get_at(spot))[:3], with_guide, "under the trunk the guide was tinting the paper")
        editor.color = RED
        editor.press((body.x + 128, body.y + 100))
        editor.release()
        self.assertEqual(tuple(self._show().get_at(spot))[:3], RED)
        self.assertEqual(self.game.canvas.get_at((body.x + 128, body.y + 100))[3], 0, "the canvas is clear over the drawing")

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
        # Seen from the side, he keeps facing the way he last walked across.
        self.assertEqual(view.bodies.characters["raul"].facing, "right")
        raul.trail = [(21, 14), (20, 14)]
        self._show()
        self.assertEqual(view.bodies.characters["raul"].facing, "left")
        raul.trail, raul.facing = [], "up"
        self._show()
        self.assertEqual(view.bodies.characters["raul"].facing, "left")
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

        game = Game(illustrations_dir=None)
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
