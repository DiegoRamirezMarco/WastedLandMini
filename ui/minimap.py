"""The whole settlement in a corner of the screen: where everyone is, and what part is in view."""

from collections.abc import Mapping

import pygame

from graphics.palette import PALETTE
from ui.panel import draw_panel

# Canvas pixels a tile takes on the minimap.
TILE_PIXELS = 2
BORDER = 1
DOT_COLOR = "paper"
VIEW_COLOR = "glow"


def minimap_size(tiles: tuple[int, int]) -> tuple[int, int]:
    """Size of the panel for a map of that many tiles."""
    return (tiles[0] * TILE_PIXELS + BORDER * 2, tiles[1] * TILE_PIXELS + BORDER * 2)


def minimap_base(terrain: pygame.Surface, tiles: tuple[int, int]) -> pygame.Surface:
    """The map made small enough for the panel. Made once: the ground does not change."""
    return pygame.transform.scale(terrain, (tiles[0] * TILE_PIXELS, tiles[1] * TILE_PIXELS))


def tile_at(rect: pygame.Rect, position: tuple[int, int]) -> tuple[float, float]:
    """The map tile shown at a canvas position inside the minimap."""
    return (
        (position[0] - rect.x - BORDER) / TILE_PIXELS,
        (position[1] - rect.y - BORDER) / TILE_PIXELS,
    )


def draw_minimap(
    target: pygame.Surface,
    rect: pygame.Rect,
    base: pygame.Surface,
    view: pygame.Rect,
    dots: Mapping[tuple[float, float], str],
) -> None:
    """Draw the minimap: the ground, a dot per resident in the colour given, and the part in view.

    `dots` are keyed by position in tiles. `view` is in minimap pixels from the map's top-left corner.
    """
    draw_panel(target, rect)
    left, top = rect.x + BORDER, rect.y + BORDER
    target.blit(base, (left, top))
    for (x, y), color in dots.items():
        dot = (left + int(x * TILE_PIXELS), top + int(y * TILE_PIXELS), TILE_PIXELS, TILE_PIXELS)
        pygame.draw.rect(target, PALETTE[color], dot)
    frame = pygame.Rect(left + view.x, top + view.y, max(2, view.width), max(2, view.height))
    pygame.draw.rect(target, PALETTE[VIEW_COLOR], frame.clip(rect), 1)
