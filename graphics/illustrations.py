"""Pictures made outside the game, shown at the resolution of the window rather than of the canvas.

They live in a folder of their own, `illustrations/`, and are free of the style contract: any size,
any colours. Whatever is missing there, the game draws as it always has.
"""

import logging
from pathlib import Path

import pygame

logger = logging.getLogger(__name__)

Size = tuple[int, int]

ILLUSTRATIONS_DIR = Path(__file__).resolve().parent.parent / "illustrations"
# How much of each side of a panel skin is its border, which keeps its shape when the panel is stretched.
SKIN_BORDER = 8


class Illustrations:
    def __init__(self, root: Path | None) -> None:
        self.root = root.resolve() if root is not None and root.is_dir() else None
        self._pictures: dict[str, pygame.Surface | None] = {}
        self._fitted: dict[tuple[str, Size], pygame.Surface] = {}

    def find(self, relative_path: str) -> pygame.Surface | None:
        """The picture at a path below the folder, as it was made. None if there is none that can be read."""
        if relative_path not in self._pictures:
            self._pictures[relative_path] = self._load(relative_path)
        return self._pictures[relative_path]

    def fitted(self, relative_path: str, size: Size) -> pygame.Surface | None:
        """The same picture brought smoothly to a size, and kept at it."""
        key = (relative_path, size)
        if key not in self._fitted:
            picture = self.find(relative_path)
            if picture is None:
                return None
            self._fitted[key] = picture if picture.get_size() == size else pygame.transform.smoothscale(picture, size)
        return self._fitted[key]

    def names(self, relative_dir: str) -> list[str]:
        """Names of the PNG files directly inside a folder. Empty if there is none."""
        if self.root is None:
            return []
        path = (self.root / relative_dir).resolve()
        if not path.is_relative_to(self.root) or not path.is_dir():
            return []
        return sorted(child.name for child in path.iterdir() if child.is_file() and child.suffix.lower() == ".png")

    def _load(self, relative_path: str) -> pygame.Surface | None:
        if self.root is None:
            return None
        path = (self.root / relative_path).resolve()
        if not path.is_relative_to(self.root) or not path.is_file():
            return None
        try:
            picture = pygame.image.load(str(path))
        except (pygame.error, OSError) as error:
            logger.warning("Illustration could not be loaded: %s (%s)", relative_path, error)
            return None
        if pygame.display.get_init() and pygame.display.get_surface() is not None:
            picture = picture.convert_alpha()
        return picture


def nine_slice(source: pygame.Surface, size: Size, border: int) -> pygame.Surface:
    """A panel of any size out of one picture: its corners as they are, its edges and middle stretched.

    `border` is how wide the picture's border is drawn on the panel, in pixels.
    """
    width, height = source.get_size()
    cut_x, cut_y = width // SKIN_BORDER, height // SKIN_BORDER
    border = min(border, size[0] // 2, size[1] // 2)
    from_x, from_y = (0, cut_x, width - cut_x, width), (0, cut_y, height - cut_y, height)
    to_x, to_y = (0, border, size[0] - border, size[0]), (0, border, size[1] - border, size[1])
    panel = pygame.Surface(size, pygame.SRCALPHA)
    for row in range(3):
        for column in range(3):
            piece = source.subsurface(
                (from_x[column], from_y[row], from_x[column + 1] - from_x[column], from_y[row + 1] - from_y[row])
            )
            place = (to_x[column + 1] - to_x[column], to_y[row + 1] - to_y[row])
            if place[0] > 0 and place[1] > 0:
                panel.blit(pygame.transform.smoothscale(piece, place), (to_x[column], to_y[row]))
    return panel
