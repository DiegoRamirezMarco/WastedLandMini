"""Image loading with a visible placeholder for anything missing or invalid."""

import logging
from pathlib import Path

import pygame

from settings import TILE_SIZE

logger = logging.getLogger(__name__)

Size = tuple[int, int]

ASSETS_DIR = Path(__file__).resolve().parent.parent / "assets"

# Deliberately outside the palette so a placeholder can never be mistaken for art.
PLACEHOLDER_COLORS = ((255, 0, 255), (0, 0, 0))
PLACEHOLDER_CELL = TILE_SIZE // 2


def make_placeholder(size: Size) -> pygame.Surface:
    surface = pygame.Surface(size, pygame.SRCALPHA)
    for y in range(0, size[1], PLACEHOLDER_CELL):
        for x in range(0, size[0], PLACEHOLDER_CELL):
            color = PLACEHOLDER_COLORS[(x // PLACEHOLDER_CELL + y // PLACEHOLDER_CELL) % 2]
            surface.fill(color, (x, y, PLACEHOLDER_CELL, PLACEHOLDER_CELL))
    return surface


class AssetStore:
    """Loads and caches PNGs below one root directory.

    Use one store per root (`assets/`, `custom_content/`). Loading never raises: a missing,
    unreadable, wrongly sized or out-of-root file yields a placeholder and a logged warning.
    """

    def __init__(self, root: Path) -> None:
        self._root = root.resolve()
        self._cache: dict[tuple[str, Size | None], pygame.Surface] = {}

    def image(self, relative_path: str, size: Size | None = None) -> pygame.Surface:
        """Return the image at `relative_path`. Pass `size` to enforce exact pixel dimensions."""
        key = (relative_path, size)
        if key not in self._cache:
            self._cache[key] = self._load(relative_path, size)
        return self._cache[key]

    def files(self, relative_dir: str) -> list[str]:
        """Names of the PNG files directly inside a folder of this store. Empty if there is none."""
        path = (self._root / relative_dir).resolve()
        if not path.is_relative_to(self._root) or not path.is_dir():
            return []
        return sorted(child.name for child in path.iterdir() if child.is_file() and child.suffix.lower() == ".png")

    def forget(self, relative_path: str) -> None:
        """Discard cached variants of one asset after an in-game editor overwrites it."""
        for key in [key for key in self._cache if key[0] == relative_path]:
            self._cache.pop(key, None)

    def optional_image(self, relative_path: str) -> pygame.Surface | None:
        """Load an unconstrained image, returning None instead of a placeholder when it is invalid."""
        path = (self._root / relative_path).resolve()
        if not path.is_relative_to(self._root) or not path.is_file():
            return None
        try:
            surface = pygame.image.load(str(path))
        except (pygame.error, OSError) as error:
            logger.warning("Asset could not be loaded: %s (%s)", relative_path, error)
            return None
        if pygame.display.get_init() and pygame.display.get_surface() is not None:
            surface = surface.convert_alpha()
        return surface

    def _load(self, relative_path: str, size: Size | None) -> pygame.Surface:
        fallback_size = size or (TILE_SIZE, TILE_SIZE)
        path = (self._root / relative_path).resolve()
        if not path.is_relative_to(self._root):
            logger.warning("Asset path escapes %s: %s", self._root, relative_path)
            return make_placeholder(fallback_size)
        try:
            surface = pygame.image.load(str(path))
        except (pygame.error, OSError) as error:
            logger.warning("Asset could not be loaded: %s (%s)", relative_path, error)
            return make_placeholder(fallback_size)
        if size is not None and surface.get_size() != size:
            logger.warning(
                "Asset %s is %s, expected %s", relative_path, surface.get_size(), size
            )
            return make_placeholder(fallback_size)
        if pygame.display.get_init() and pygame.display.get_surface() is not None:
            surface = surface.convert_alpha()
        return surface
