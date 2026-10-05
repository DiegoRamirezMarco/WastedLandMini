import logging
import os
import tempfile
import unittest
from pathlib import Path

import pygame

from graphics.assets import ASSETS_DIR, AssetStore
from graphics.face_renderer import FACE_SIZE, FaceRenderer
from graphics.illustrations import Illustrations, nine_slice
from graphics.screen_layers import ScreenLayers
from settings import SCALE, SCREEN_HEIGHT, SCREEN_WIDTH, TILE_SIZE
from simulation.commands import AdvanceTimeCommand

GROUND = (150, 110, 70)
SHOP = (40, 160, 200)
FACE = (200, 60, 120)
SKIN = (60, 20, 90)


def _is(color: tuple[int, ...], expected: tuple[int, int, int]) -> bool:
    """Whether a colour is the expected one, give or take what smooth scaling rounds off."""
    return all(abs(channel - wanted) <= 4 for channel, wanted in zip(color[:3], expected))


def _picture(root: Path, relative: str, color: tuple[int, int, int], size: tuple[int, int] = (300, 200)) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    surface = pygame.Surface(size)
    surface.fill(color)
    pygame.image.save(surface, str(path))


class IllustrationsTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name) / "illustrations"
        self.root.mkdir()

    def test_a_picture_is_found_as_made_and_brought_to_any_size(self) -> None:
        _picture(self.root, "map/settlement.png", GROUND, (300, 200))
        pictures = Illustrations(self.root)
        self.assertEqual(pictures.find("map/settlement.png").get_size(), (300, 200))
        fitted = pictures.fitted("map/settlement.png", (64, 48))
        self.assertEqual(fitted.get_size(), (64, 48))
        self.assertTrue(_is(tuple(fitted.get_at((10, 10))), GROUND))
        self.assertIs(pictures.fitted("map/settlement.png", (64, 48)), fitted)
        self.assertEqual(pictures.names("map"), ["settlement.png"])

    def test_what_is_missing_broken_or_outside_the_folder_is_simply_not_there(self) -> None:
        logging.disable(logging.WARNING)
        self.addCleanup(logging.disable, logging.NOTSET)
        _picture(self.root.parent, "outside.png", GROUND)
        (self.root / "broken.png").write_bytes(b"not a picture")
        pictures = Illustrations(self.root)
        self.assertIsNone(pictures.find("nothing.png"))
        self.assertIsNone(pictures.find("broken.png"))
        self.assertIsNone(pictures.find("../outside.png"))
        self.assertIsNone(pictures.fitted("nothing.png", (10, 10)))
        self.assertEqual(pictures.names("../"), [])
        for nowhere in (None, self.root / "no_such_folder"):
            empty = Illustrations(nowhere)
            self.assertIsNone(empty.root)
            self.assertIsNone(empty.find("map/settlement.png"))
            self.assertEqual(empty.names("map"), [])

    def test_a_skin_keeps_its_border_and_stretches_its_middle(self) -> None:
        source = pygame.Surface((80, 80))
        source.fill(SKIN)
        pygame.draw.rect(source, (255, 255, 255), source.get_rect(), 10)
        panel = nine_slice(source, (400, 60), 12)
        self.assertEqual(panel.get_size(), (400, 60))
        self.assertEqual(tuple(panel.get_at((2, 2)))[:3], (255, 255, 255))
        self.assertEqual(tuple(panel.get_at((397, 57)))[:3], (255, 255, 255))
        self.assertTrue(_is(tuple(panel.get_at((200, 30))), SKIN))
        self.assertEqual(nine_slice(source, (10, 6), 12).get_size(), (10, 6))

    def test_an_illustrated_face_takes_the_place_of_the_layered_one_at_every_size(self) -> None:
        _picture(self.root, "faces/raul/angry.png", FACE, (512, 512))
        _picture(self.root, "faces/marta/neutral.png", GROUND, (512, 512))
        _picture(self.root, "faces/marta/sad.png", SHOP, (512, 512))
        faces = FaceRenderer(AssetStore(ASSETS_DIR), None, Illustrations(self.root))
        # The only picture there is of him does for every expression.
        for expression in ("angry", "neutral", "happy"):
            self.assertTrue(_is(tuple(faces.face("raul", expression).get_at((5, 5))), FACE))
        self.assertEqual(faces.face("raul", "angry").get_size(), FACE_SIZE)
        self.assertEqual(faces.portrait("raul", "angry", (256, 256)).get_size(), (256, 256))
        # With several, the one for the expression, or else the neutral one.
        self.assertTrue(_is(tuple(faces.portrait("marta", "sad", (64, 64)).get_at((5, 5))), SHOP))
        self.assertTrue(_is(tuple(faces.portrait("marta", "angry", (64, 64)).get_at((5, 5))), GROUND))
        self.assertIsNone(faces.portrait("lucia", "neutral", (64, 64)))
        self.assertNotEqual(tuple(faces.face("lucia", "neutral").get_at((32, 40)))[:3], FACE)
        self.assertIsNone(FaceRenderer(AssetStore(ASSETS_DIR)).portrait("raul", "angry", (64, 64)))

    def test_with_nothing_to_show_through_the_window_is_the_canvas_made_larger(self) -> None:
        layers = ScreenLayers(2)
        canvas = pygame.Surface((8, 6))
        canvas.fill((10, 200, 30))
        window = pygame.Surface((16, 12))
        self.assertFalse(layers.active)
        layers.compose(window, canvas)
        self.assertEqual(tuple(window.get_at((15, 11)))[:3], (10, 200, 30))
        self.assertEqual(layers.on_screen(pygame.Rect(1, 2, 3, 4)), pygame.Rect(2, 4, 6, 8))


class IllustratedGameTests(unittest.TestCase):
    """The real game shell, without a window, with pictures of flat colour standing in for illustrations."""

    def setUp(self) -> None:
        for variable in ("SDL_VIDEODRIVER", "SDL_AUDIODRIVER"):
            previous = os.environ.get(variable)
            self.addCleanup(self._restore, variable, previous)
            os.environ[variable] = "dummy"
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name) / "illustrations"
        self.root.mkdir()
        self.addCleanup(pygame.quit)
        self.window = None

    @staticmethod
    def _restore(variable: str, previous: str | None) -> None:
        if previous is None:
            os.environ.pop(variable, None)
        else:
            os.environ[variable] = previous

    def _game(self):
        from game.game import Game

        game = Game(illustrations_dir=self.root, voices_dir=None)
        self.window = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
        return game

    def _shown(self, game) -> pygame.Surface:
        with self.assertNoLogs("graphics.assets", level="WARNING"):
            game.active_scene.render()
        game.present(self.window)
        return self.window

    def _on_window(self, view, tile: tuple[float, float]) -> tuple[int, int]:
        x, y = view._canvas_point(tile[0] * TILE_SIZE, tile[1] * TILE_SIZE)
        return (x * SCALE, y * SCALE)

    def test_an_illustrated_ground_shows_under_the_map_at_the_resolution_of_the_window(self) -> None:
        _picture(self.root, "map/settlement.png", GROUND, (1536, 1024))
        game = self._game()
        view = game.global_view
        open_ground = (20.5, 20.5)
        self.assertEqual(game.world.tile_map.terrain_at((20, 20)), "dirt")
        view.centre_on(open_ground)
        window = self._shown(game)
        spot = self._on_window(view, open_ground)
        self.assertTrue(_is(tuple(window.get_at(spot)), GROUND))
        # The canvas is left clear over the map, and what stands on the ground is still drawn.
        self.assertEqual(game.canvas.get_at(view.viewport.center)[3], 0)
        view.centre_on((4, 20))
        window = self._shown(game)
        self.assertNotEqual(tuple(window.get_at(self._on_window(view, (0.5, 20.5))))[:3], GROUND)
        # Round the map everything is as it was: the bar is drawn on the canvas.
        self.assertEqual(game.canvas.get_at((300, 5))[3], 255)
        # It grows with the zoom like the rest of the map.
        for zoom in range(4):
            view.set_zoom(zoom)
            view.centre_on(open_ground)
            window = self._shown(game)
            self.assertTrue(_is(tuple(window.get_at(self._on_window(view, open_ground))), GROUND), zoom)

    def test_night_and_storms_darken_the_illustrated_ground_too(self) -> None:
        _picture(self.root, "map/settlement.png", GROUND, (1536, 1024))
        game = self._game()
        view, world = game.global_view, game.world
        far_from_any_light = (36.5, 12.5)
        view.centre_on(far_from_any_light)
        by_day = tuple(self._shown(game).get_at(self._on_window(view, far_from_any_light)))[:3]
        self.assertEqual(by_day, GROUND)
        world.clock.hour = 2
        by_night = tuple(self._shown(game).get_at(self._on_window(view, far_from_any_light)))[:3]
        self.assertLess(sum(by_night), sum(by_day) * 0.7)

    def test_a_drawn_building_stands_on_the_window_until_it_is_looked_into(self) -> None:
        _picture(self.root, "map/settlement.png", GROUND, (1536, 1024))
        _picture(self.root, "buildings/shop.png", SHOP, (1536, 1024))
        game = self._game()
        view, world = game.global_view, game.world
        shop, dormitory = world.rooms["shop"], world.rooms["dormitory"]
        # A spot under its roof, away from the sign with its name.
        inside = (shop.x + 1.5, shop.y + 0.5)
        view.centre_on(inside)
        window = self._shown(game)
        self.assertTrue(_is(tuple(window.get_at(self._on_window(view, inside))), SHOP))
        roof = (shop.x - 0.5, shop.y - 1.5)
        self.assertTrue(_is(tuple(window.get_at(self._on_window(view, roof))), SHOP), "it rises above its back wall")
        # A building nobody has drawn keeps the game's own picture.
        other = (dormitory.x + dormitory.width / 2, dormitory.y + dormitory.height / 2)
        view.centre_on(other)
        self.assertNotIn(tuple(self._shown(game).get_at(self._on_window(view, other)))[:3], (SHOP, GROUND))
        # Looked into, it is gone and the floor shows.
        view.centre_on(inside)
        view.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_t))
        window = self._shown(game)
        self.assertNotIn(tuple(window.get_at(self._on_window(view, inside)))[:3], (SHOP, GROUND))

    def test_the_large_parts_of_the_screen_wear_the_skin_and_keep_their_text(self) -> None:
        _picture(self.root, "ui/panel.png", SKIN, (512, 512))
        game = self._game()
        view = game.global_view
        layout = view.hud.layout
        window = self._shown(game)
        for part in (layout.top, layout.sidebar, layout.panel, layout.dock):
            corner = (part.right - 3, part.bottom - 3)
            self.assertEqual(game.canvas.get_at(corner)[3], 0, part)
            self.assertTrue(_is(tuple(window.get_at((corner[0] * SCALE, corner[1] * SCALE))), SKIN), part)
        # What is written on them is still there, on the canvas.
        painted = sum(
            1 for x in range(layout.panel.x, layout.panel.right) for y in range(layout.panel.y, layout.panel.y + 20)
            if game.canvas.get_at((x, y))[3]
        )
        self.assertGreater(painted, 40)
        # The map has no skin: without a drawn ground it is the game's own, on the canvas.
        self.assertEqual(game.canvas.get_at(layout.map.center)[3], 255)

    def test_illustrated_faces_are_shown_large_in_the_panel_and_in_the_dock(self) -> None:
        _picture(self.root, "faces/raul/angry.png", FACE, (1024, 1024))
        game = self._game()
        view, world = game.global_view, game.world
        view.hud.select_resident("raul")
        window = self._shown(game)
        panel = view.hud.layout.panel
        in_panel = ((panel.x + 30) * SCALE, (panel.y + 30) * SCALE)
        self.assertTrue(_is(tuple(window.get_at(in_panel)), FACE))
        # He boils over in the first minutes: the dock then shows him large.
        world.apply_command(AdvanceTimeCommand(minutes=8))
        view.on_events(world.events.drain())
        decision = next(decision for decision in world.decisions.values() if decision.resident_id == "raul")
        game.open_interaction(decision.decision_id)
        window = self._shown(game)
        dock = view.hud.layout.dock
        in_dock = ((dock.x + 40) * SCALE, (dock.y + 40) * SCALE)
        self.assertTrue(_is(tuple(window.get_at(in_dock)), FACE))
        # His name is still on its plate, drawn over the picture.
        plate_row = [tuple(window.get_at(((dock.x + x) * SCALE, (dock.bottom - 12) * SCALE)))[:3] for x in range(40, 100)]
        self.assertTrue(any(color != FACE for color in plate_row))

    def test_a_folder_with_nothing_in_it_changes_nothing(self) -> None:
        game = self._game()
        window = self._shown(game)
        self.assertFalse(game.layers.active)
        for spot in ((10, 10), (400, 200), (700, 400)):
            self.assertEqual(tuple(window.get_at((spot[0] * SCALE, spot[1] * SCALE)))[:3], tuple(game.canvas.get_at(spot))[:3])


if __name__ == "__main__":
    unittest.main()
