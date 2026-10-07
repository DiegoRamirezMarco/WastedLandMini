import os
import tempfile
import unittest
from pathlib import Path

import pygame

from graphics import ui_art
from graphics.illustrations import Illustrations
from graphics.palette import PALETTE
from graphics.screen_layers import ScreenLayers
from graphics.ui_skin import ICONS_DIR, SMALLEST_DRESSED, WindowSkin
from ui.panel import draw_bar, draw_button, draw_panel, set_skin

CANVAS = (200, 120)
SCALE = 2


class UiSkinTests(unittest.TestCase):
    """What is drawn of the interface at the resolution of the window, without a window."""

    def setUp(self) -> None:
        previous = os.environ.get("SDL_VIDEODRIVER")
        os.environ["SDL_VIDEODRIVER"] = "dummy"
        self.addCleanup(lambda: os.environ.pop("SDL_VIDEODRIVER") if previous is None else os.environ.update(SDL_VIDEODRIVER=previous))
        pygame.init()
        pygame.display.set_mode((16, 16))
        self.addCleanup(pygame.quit)
        self.addCleanup(set_skin, None)
        self.layers = ScreenLayers(SCALE)
        self.canvas = pygame.Surface(CANVAS, pygame.SRCALPHA)
        self.canvas.fill(PALETTE["ink"])
        self.skin = WindowSkin(self.canvas, self.layers)
        set_skin(self.skin)

    def _window(self) -> pygame.Surface:
        window = pygame.Surface((CANVAS[0] * SCALE, CANVAS[1] * SCALE))
        self.layers.compose(window, self.canvas)
        return window

    def test_with_no_window_under_the_canvas_everything_is_drawn_flat_on_it(self) -> None:
        plain = pygame.Surface(CANVAS)
        skin = WindowSkin(plain, self.layers)
        self.assertFalse(skin.usable)
        set_skin(skin)
        draw_panel(plain, pygame.Rect(10, 10, 80, 40))
        draw_button(plain, pygame.Rect(100, 10, 40, 13), active=True)
        draw_bar(plain, pygame.Rect(100, 40, 50, 5), 0.5, "ember")
        self.assertEqual(plain.get_at((50, 30))[:3], PALETTE["ink"])
        self.assertEqual(plain.get_at((10, 10))[:3], PALETTE["iron"])
        self.assertEqual(plain.get_at((120, 16))[:3], PALETTE["lamp"])
        self.assertEqual(plain.get_at((105, 42))[:3], PALETTE["ember"])
        self.assertEqual(plain.get_at((145, 42))[:3], PALETTE["shadow"])
        self.assertFalse(self.layers.active, "nothing was put on the window")

    def test_a_panel_leaves_the_canvas_clear_for_a_picture_of_the_window(self) -> None:
        rect = pygame.Rect(10, 10, 80, 40)
        draw_panel(self.canvas, rect, band=12)
        self.assertEqual(self.canvas.get_at(rect.center).a, 0)
        self.assertEqual(self.canvas.get_at((5, 5))[:3], PALETTE["ink"], "and nothing round it is touched")
        window = self._window()
        middle = window.get_at((rect.centerx * SCALE, rect.centery * SCALE))[:3]
        band = window.get_at((rect.centerx * SCALE, (rect.y + 6) * SCALE))[:3]
        self.assertNotEqual(middle, PALETTE["ink"])
        self.assertNotEqual(band, middle, "its heading stands on a band of another colour")
        # What is drawn on the canvas afterwards is in front of it.
        self.canvas.set_at(rect.center, PALETTE["glow"])
        self.assertEqual(self._window().get_at((rect.centerx * SCALE, rect.centery * SCALE))[:3], PALETTE["glow"])

    def test_buttons_and_bars_are_dressed_too_and_a_bar_shows_its_share(self) -> None:
        button, bar = pygame.Rect(20, 20, 50, 13), pygame.Rect(20, 60, 100, 6)
        draw_button(self.canvas, button)
        draw_bar(self.canvas, bar, 0.5, "ember")
        self.assertEqual(self.canvas.get_at(button.center).a, 0)
        self.assertEqual(self.canvas.get_at(bar.center).a, 0)
        window = self._window()
        filled = window.get_at(((bar.x + 20) * SCALE, bar.centery * SCALE))
        empty = window.get_at(((bar.x + 80) * SCALE, bar.centery * SCALE))
        self.assertGreater(filled.r, empty.r + 60)

    def test_what_is_too_small_or_drawn_elsewhere_is_left_flat(self) -> None:
        small = pygame.Rect(10, 10, SMALLEST_DRESSED[0] - 1, SMALLEST_DRESSED[1] - 1)
        draw_panel(self.canvas, small)
        self.assertEqual(self.canvas.get_at(small.center)[:3], PALETTE["ink"])
        other = pygame.Surface(CANVAS, pygame.SRCALPHA)
        draw_panel(other, pygame.Rect(10, 10, 80, 40))
        self.assertEqual(other.get_at((50, 30))[:3], PALETTE["ink"])
        # Nor is anything that the canvas is not letting be drawn in whole.
        self.canvas.set_clip(pygame.Rect(0, 0, 50, 50))
        cut = pygame.Rect(30, 30, 60, 40)
        draw_panel(self.canvas, cut)
        self.canvas.set_clip(None)
        self.assertEqual(self.canvas.get_at((40, 40))[:3], PALETTE["ink"])
        self.assertFalse(self.layers.active)

    def test_the_large_parts_of_the_screen_wear_the_plate(self) -> None:
        part = pygame.Rect(0, 0, 200, 26)
        self.skin.parts = {tuple(part)}
        draw_panel(self.canvas, part, border="ink")
        window = self._window()
        self.assertEqual(self.canvas.get_at(part.center).a, 0)
        self.assertNotEqual(window.get_at((200, 26))[:3], PALETTE["ink"])

    def test_every_icon_is_drawn_at_any_size_alone_and_on_its_tile(self) -> None:
        self.assertEqual(set(ui_art.GLYPHS), set(ui_art.HUES))
        for name in ui_art.GLYPHS:
            for size in (22, 36):
                alone, tile = ui_art.icon(name, size), ui_art.tile(name, size)
                self.assertEqual((alone.get_size(), tile.get_size()), ((size, size), (size, size)))
                self.assertGreater(pygame.mask.from_surface(alone).count(), size * size // 8, name)
                self.assertEqual(tile.get_at((size // 2, size // 2)).a, 255, name)
                self.assertEqual(tile.get_at((0, 0)).a, 0, f"{name}: its corners are rounded off")
        self.assertIsNot(self.skin.tile("people", 36), self.skin.tile("people", 36, lit=True))
        self.assertIs(self.skin.tile("people", 36), self.skin.tile("people", 36), "made once and kept")

    def test_a_picture_in_the_folder_takes_the_place_of_an_icon(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            icons = Path(folder) / ICONS_DIR
            icons.mkdir(parents=True)
            own = pygame.Surface((64, 64), pygame.SRCALPHA)
            own.fill((10, 200, 30, 255))
            pygame.image.save(own, str(icons / "people.png"))
            skin = WindowSkin(self.canvas, self.layers, Illustrations(Path(folder)))
            # Brought smoothly to the size it is shown at, which may shift a colour by a hair.
            shown = skin.tile("people", 36).get_at((18, 18))
            self.assertLess(max(abs(shown.r - 10), abs(shown.g - 200), abs(shown.b - 30)), 5)
            self.assertEqual(skin.icon("people", 22).get_size(), (22, 22))
            self.assertLess(skin.tile("work", 36).get_at((18, 18)).g, 255, "the rest are the game's own")
            self.assertNotEqual(skin.tile("work", 36).get_at((0, 0)).a, 255)


if __name__ == "__main__":
    unittest.main()
