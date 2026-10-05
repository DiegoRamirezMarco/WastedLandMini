import logging
import tempfile
import unittest
from pathlib import Path

import pygame

import settings
from graphics.assets import PLACEHOLDER_COLORS, AssetStore
from graphics.palette import GPL_PATH, PALETTE, to_gpl


class AssetStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name) / "assets"
        self.root.mkdir()
        self.store = AssetStore(self.root)
        logging.disable(logging.WARNING)
        self.addCleanup(logging.disable, logging.NOTSET)

    def _write_png(self, path: Path, size: tuple[int, int]) -> None:
        surface = pygame.Surface(size, pygame.SRCALPHA)
        surface.fill(PALETTE["lamp"])
        pygame.image.save(surface, str(path))

    def _assert_placeholder(self, surface: pygame.Surface, size: tuple[int, int]) -> None:
        self.assertEqual(surface.get_size(), size)
        self.assertEqual(tuple(surface.get_at((0, 0)))[:3], PLACEHOLDER_COLORS[0])

    def test_valid_png_loads_and_is_cached(self) -> None:
        self._write_png(self.root / "icon.png", (16, 16))
        surface = self.store.image("icon.png", size=(16, 16))
        self.assertEqual(tuple(surface.get_at((0, 0)))[:3], PALETTE["lamp"])
        self.assertIs(self.store.image("icon.png", size=(16, 16)), surface)

    def test_missing_png_gives_tile_sized_placeholder(self) -> None:
        tile = (settings.TILE_SIZE, settings.TILE_SIZE)
        self._assert_placeholder(self.store.image("nope.png"), tile)

    def test_missing_png_placeholder_uses_requested_size(self) -> None:
        self._assert_placeholder(self.store.image("faces/nope.png", size=(64, 64)), (64, 64))

    def test_corrupt_png_gives_placeholder(self) -> None:
        (self.root / "broken.png").write_bytes(b"not a png")
        self._assert_placeholder(self.store.image("broken.png", size=(16, 16)), (16, 16))
        self.assertIsNone(self.store.optional_image("broken.png"))

    def test_an_optional_image_is_none_when_missing_and_the_surface_when_present(self) -> None:
        self.assertIsNone(self.store.optional_image("missing.png"))
        self._write_png(self.root / "optional.png", (27, 19))
        self.assertEqual(self.store.optional_image("optional.png").get_size(), (27, 19))

    def test_wrong_size_gives_placeholder(self) -> None:
        self._write_png(self.root / "big.png", (32, 32))
        self._assert_placeholder(self.store.image("big.png", size=(16, 16)), (16, 16))

    def test_path_outside_root_gives_placeholder(self) -> None:
        self._write_png(self.root.parent / "outside.png", (16, 16))
        self._assert_placeholder(self.store.image("../outside.png", size=(16, 16)), (16, 16))


class StyleContractTests(unittest.TestCase):
    def test_window_is_an_integer_multiple_of_the_canvas(self) -> None:
        self.assertIsInstance(settings.SCALE, int)
        self.assertEqual(settings.SCREEN_WIDTH, settings.INTERNAL_WIDTH * settings.SCALE)
        self.assertEqual(settings.SCREEN_HEIGHT, settings.INTERNAL_HEIGHT * settings.SCALE)

    def test_canvas_width_fits_whole_tiles(self) -> None:
        self.assertEqual(settings.INTERNAL_WIDTH % settings.TILE_SIZE, 0)

    def test_exported_palette_matches_code(self) -> None:
        self.assertEqual(GPL_PATH.read_text(encoding="utf-8"), to_gpl())


if __name__ == "__main__":
    unittest.main()
