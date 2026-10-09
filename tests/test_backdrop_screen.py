import os
import tempfile
import unittest
from pathlib import Path

import pygame

from graphics.backdrop import backdrop_path
from scenes.backdrop_editor import NOTHING_DRAWN, OTHERS_OFF, SAVED_TEXT, rolled
from scenes.object_editor import FILL_TOOL
from settings import SCALE
from simulation.world import SimulationWorld

SKY = (150, 60, 90)
INK = (40, 30, 60)


def _send_out(world: SimulationWorld, resident_id: str = "sergio"):
    out = world.residents[resident_id]
    for _ in range(240):
        if out.away:
            return out
        world.step(1)
    raise AssertionError("the scavenger never set out")


def _bytes(picture: pygame.Surface) -> bytes:
    return pygame.image.tobytes(picture, "RGBA")


class RollingTests(unittest.TestCase):
    def test_what_goes_off_one_end_of_a_rolled_picture_comes_in_at_the_other(self) -> None:
        pygame.init()
        self.addCleanup(pygame.quit)
        picture = pygame.Surface((8, 2), pygame.SRCALPHA)
        picture.set_at((7, 0), (255, 0, 0, 255))
        picture.set_at((0, 1), (0, 255, 0, 255))
        once = rolled(picture, 2)
        self.assertEqual(tuple(once.get_at((1, 0))), (255, 0, 0, 255))
        self.assertEqual(tuple(once.get_at((2, 1))), (0, 255, 0, 255))
        self.assertEqual(pygame.mask.from_surface(once).count(), 2, "nothing is lost and nothing made")
        self.assertEqual(_bytes(rolled(once, -2)), _bytes(picture))
        self.assertEqual(_bytes(rolled(picture, 8)), _bytes(picture))


class _Shell(unittest.TestCase):
    """The real game shell without a window, with somebody out of the settlement and watched."""

    illustrated = True

    def setUp(self) -> None:
        for variable in ("SDL_VIDEODRIVER", "SDL_AUDIODRIVER"):
            self.addCleanup(self._restore_driver, variable, os.environ.get(variable))
            os.environ[variable] = "dummy"
        from game.game import Game

        self.folder = None
        if self.illustrated:
            keep = tempfile.TemporaryDirectory()
            self.addCleanup(keep.cleanup)
            self.folder = Path(keep.name) / "illustrations"
            self.folder.mkdir()
        self.game = Game(illustrations_dir=self.folder, voices_dir=None, start_in_menu=False)
        self.addCleanup(pygame.quit)
        self.view, self.world = self.game.global_view, self.game.world
        self.trips = self.view.expedition
        self.sergio = _send_out(self.world)
        self.world.events.drain()
        self.view.render()
        self.view.click(self.view.away_boxes["sergio"].center)
        self.view.render()

    @staticmethod
    def _restore_driver(variable: str, previous: str | None) -> None:
        if previous is None:
            os.environ.pop(variable, None)
        else:
            os.environ[variable] = previous

    def _open(self):
        self.view.click(self.trips.draw_button.rect.center)
        self.game.sync_scenes()
        return self.game.backdrop_editor

    def _at(self, editor, x: int, y: int) -> tuple[int, int]:
        """A place on the canvas over a pixel of the paper."""
        return (editor.area.x + x, editor.area.y + y)

    def _fill(self, editor, color, x: int = 10, y: int = 10) -> None:
        editor.color, editor.tool = color, FILL_TOOL
        editor.press(self._at(editor, x, y))
        editor.release()

    def _stroke(self, editor, color, start: tuple[int, int], end: tuple[int, int]) -> None:
        editor.color, editor.tool, editor.size = color, "brush", 6
        editor.press(self._at(editor, *start))
        editor.drag(self._at(editor, *end))
        editor.release()

    def _file(self, layer_id: str) -> Path:
        return self.folder / backdrop_path("ruins", layer_id)


class BackdropEditorTests(_Shell):
    def test_the_trip_has_a_way_to_where_what_goes_by_is_drawn(self) -> None:
        from game.game import BACKDROP_SCENE

        self.assertIn(self.trips.draw_button, self.trips.buttons())
        self.assertTrue(self.view.viewport.contains(self.trips.draw_button.rect))
        self.assertFalse(self.trips.draw_button.rect.colliderect(self.trips.leave_button.rect))
        editor = self._open()
        self.assertEqual(self.game.scene_name, BACKDROP_SCENE)
        self.assertIs(self.game.active_scene, editor)
        self.assertEqual((editor.zone, editor.resident_id, editor.closed), ("ruins", "sergio", False))
        self.assertEqual(editor._title(), "Dibujar el fondo: las ruinas")
        # Time stands still while it is open.
        minute = self.world.clock.total_minutes
        self.game.advance_simulation(5.0)
        self.assertEqual(self.world.clock.total_minutes, minute)
        # Escape goes back to whoever was being watched, and not out to the menu.
        self.game.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE, mod=0, unicode=""))
        self.game.sync_scenes()
        self.assertEqual((self.game.scene_name, self.view.outside), ("global", "sergio"))
        self.assertIsNone(self.view.requested_backdrop_editor)

    def test_there_is_a_paper_for_every_layer_and_the_first_is_in_hand(self) -> None:
        editor = self._open()
        plan = editor.plan
        self.assertEqual(list(editor.drawings), [layer.layer_id for layer in plan.layers])
        self.assertTrue(all(paper.get_size() == plan.paper for paper in editor.drawings.values()))
        self.assertTrue(all(paper.get_bounding_rect().width == 0 for paper in editor.drawings.values()), "nothing drawn yet")
        self.assertEqual(editor.layer, "sky")
        self.assertEqual(editor.area.size, plan.paper)
        self.assertEqual([button.label for button in editor.layer_buttons], [layer.name for layer in plan.layers])
        self.assertIn(plan.layer("sky").note, editor.notes[0])
        canvas = self.view.canvas.get_rect()
        self.assertTrue(all(canvas.contains(button.rect) for button in editor.buttons))
        self.assertTrue(canvas.contains(editor.area))
        rects = [button.rect for button in editor.buttons]
        self.assertEqual([rect.collidelistall(rects) for rect in rects], [[index] for index in range(len(rects))])
        self.assertTrue(all(not editor.area.colliderect(rect) for rect in rects))

    def test_the_guide_marks_where_feet_come_down_and_how_tall_somebody_is(self) -> None:
        editor = self._open()
        wide, tall = editor.plan.paper
        feet = round(editor.plan.ground * tall)
        for layer in editor.plan.layers:
            editor._apply(("layer", layer.layer_id))
            guide = editor.guide_picture
            self.assertEqual(guide.get_size(), editor.plan.paper)
            self.assertEqual({tuple(guide.get_at((x, feet)))[:3] for x in (3, wide // 2 + 40, wide - 3)}, {(217, 90, 69)})

    def test_what_is_painted_goes_on_the_layer_in_hand_and_no_other(self) -> None:
        editor = self._open()
        self._fill(editor, SKY)
        self.assertEqual(tuple(editor.drawings["sky"].get_at((200, 100))), (*SKY, 255))
        editor._apply(("layer", "middle"))
        self.assertEqual(editor.layer, "middle")
        self.assertIn(editor.plan.layer("middle").note, editor.notes[0])
        self._stroke(editor, INK, (100, 120), (140, 200))
        self.assertEqual(tuple(editor.drawings["middle"].get_at((100, 120))), (*INK, 255))
        self.assertEqual(tuple(editor.drawings["sky"].get_at((100, 120))), (*SKY, 255))
        self.assertEqual(editor.drawings["ground"].get_bounding_rect().width, 0)
        # Undone, the stroke is gone and the sky is as it was; undone again, the sky is, and it is in hand.
        editor.undo()
        self.assertEqual(editor.drawings["middle"].get_bounding_rect().width, 0)
        editor.undo()
        self.assertEqual((editor.layer, editor.drawings["sky"].get_bounding_rect().width), ("sky", 0))

    def test_the_paper_is_slid_sideways_to_draw_where_its_ends_meet(self) -> None:
        editor = self._open()
        wide = editor.plan.paper[0]
        self._stroke(editor, INK, (wide - 4, 50), (wide - 4, 60))
        editor._apply(("layer", "ground"))
        self._stroke(editor, SKY, (2, 280), (2, 290))
        before = {layer_id: _bytes(paper) for layer_id, paper in editor.drawings.items()}
        editor._apply(("roll", 1))
        slid = wide // 4
        self.assertEqual(tuple(editor.drawings["sky"].get_at((slid - 4, 55))), (*INK, 255), "what was at one end is in the middle")
        self.assertEqual(tuple(editor.drawings["ground"].get_at((slid + 2, 285))), (*SKY, 255), "and every layer goes with it")
        for _ in range(3):
            editor._apply(("roll", 1))
        self.assertEqual({layer_id: _bytes(paper) for layer_id, paper in editor.drawings.items()}, before, "all the way round")
        editor._apply(("roll", -1))
        editor.undo()
        self.assertEqual({layer_id: _bytes(paper) for layer_id, paper in editor.drawings.items()}, before)

    def test_the_game_has_a_picture_of_each_layer_to_start_from(self) -> None:
        editor = self._open()
        editor._apply(("layer", "ground"))
        editor._apply(("starter",))
        ground = editor.drawings["ground"]
        feet = round(editor.plan.ground * editor.plan.paper[1])
        self.assertEqual(ground.get_at((50, feet))[3], 255)
        self.assertEqual(ground.get_at((50, 20))[3], 0, "it lets what is behind show")
        editor.undo()
        self.assertEqual(editor.drawings["ground"].get_bounding_rect().width, 0)

    def test_saving_keeps_the_layers_that_have_anything_on_them(self) -> None:
        editor = self._open()
        editor.save()
        self.assertEqual(editor.notice, NOTHING_DRAWN)
        self.assertFalse(self._file("sky").parent.exists() and any(self._file("sky").parent.iterdir()))
        self._fill(editor, SKY)
        self.assertTrue(editor.save())
        self.assertEqual(editor.notice, SAVED_TEXT)
        self.assertTrue(self._file("sky").is_file())
        self.assertEqual([path.name for path in self._file("sky").parent.iterdir()], ["sky.png"])
        self.assertTrue(self.trips.backdrops.drawn("ruins"))
        # Opened again it is there to go on from, and wiped clean and saved it is the game's again.
        editor.closed = True
        self.game.sync_scenes()
        editor = self._open()
        self.assertEqual(tuple(editor.drawings["sky"].get_at((30, 30))), (*SKY, 255))
        editor._apply(("clear",))
        self.assertTrue(editor.save())
        self.assertFalse(self._file("sky").exists())
        self.assertFalse(self.trips.backdrops.drawn("ruins"))

    def test_what_is_drawn_is_what_goes_by_behind_whoever_is_out(self) -> None:
        stage = self.view.layers.on_screen(self.view.viewport)
        spot = (stage.x + 30, stage.y + 60)

        def sky() -> tuple:
            self.view.render()
            screen = pygame.Surface((self.view.canvas.get_width() * SCALE, self.view.canvas.get_height() * SCALE))
            self.game.present(screen)
            return tuple(screen.get_at(spot))[:3]

        self.world.clock.hour, self.world.clock.minute = 12, 0
        before = sky()
        self.assertNotEqual(before, SKY)
        editor = self._open()
        self._fill(editor, SKY)
        editor.save()
        editor.closed = True
        self.game.sync_scenes()
        self.assertEqual(self.view.outside, "sergio")
        self.assertEqual(sky(), SKY)
        # The layers nobody drew are still the ones the game has: there is ground under their feet.
        ground = next(strip for strip in self.trips.backdrops.strips("ruins", stage.height) if strip.layer.layer_id == "ground")
        self.assertGreater(ground.picture.get_bounding_rect().width, 0)

    def test_the_whole_of_it_goes_by_beside_the_paper_with_them_walking_in_it(self) -> None:
        editor = self._open()
        self.assertIsNotNone(self.view.walker("sergio"))
        self.assertIsNone(self.view.walker(None))

        def frame() -> bytes:
            editor.render()
            screen = pygame.Surface((self.view.canvas.get_width() * SCALE, self.view.canvas.get_height() * SCALE))
            self.game.present(screen)
            from scenes.object_editor import PREVIEW

            return pygame.image.tobytes(screen.subsurface(self.game.layers.on_screen(PREVIEW)), "RGB")

        first = frame()
        editor.update(0.5)
        self.assertNotEqual(frame(), first, "it moves")
        self._fill(editor, SKY)
        self.assertNotEqual(frame(), first)
        # With only the layer in hand on the paper it is drawn all the same.
        editor._apply(("others",))
        self.assertEqual((editor.others_on, editor.others_button.label), (False, OTHERS_OFF))
        frame()
        editor.resident_id = None
        frame()

    def test_only_country_there_is_can_be_drawn(self) -> None:
        editor = self.game.backdrop_editor
        editor.open("no_such_zone")
        self.assertTrue(editor.closed)
        self.assertFalse(editor.save())
        self.view.requested_backdrop_editor = ("no_such_zone", None)
        self.game.sync_scenes()
        self.assertEqual(self.game.scene_name, "global")


class NowhereToKeepDrawingsTests(_Shell):
    illustrated = False

    def test_with_nowhere_to_keep_drawings_there_is_no_way_to_draw_it(self) -> None:
        self.assertIsNone(self.game.backdrop_editor)
        self.assertNotIn(self.trips.draw_button, self.trips.buttons())
        self.view.click(self.trips.draw_button.rect.center)
        self.game.sync_scenes()
        self.assertEqual((self.game.scene_name, self.view.outside), ("global", "sergio"))


if __name__ == "__main__":
    unittest.main()
