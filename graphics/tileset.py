"""Named tiles cut from a tileset sheet."""

from collections.abc import Mapping

import pygame

from graphics.assets import make_placeholder
from settings import TILE_SIZE

Cell = tuple[int, int]

SETTLEMENT_SHEET = "sprites/tiles/settlement.png"
SETTLEMENT_SHEET_SIZE = (8 * TILE_SIZE, 3 * TILE_SIZE)

# Column and row of each tile inside the settlement sheet.
SETTLEMENT_CELLS: dict[str, Cell] = {
    "dirt": (0, 0),
    "dirt_pebbles": (1, 0),
    "grass": (2, 0),
    "grass_tuft": (3, 0),
    "gate": (4, 0),
    "soil": (5, 0),
    "floor_wood": (0, 1),
    "floor_concrete": (1, 1),
    "floor_cracked": (2, 1),
    "floor_stained": (3, 1),
    "wall_top": (0, 2),
    "wall_face": (1, 2),
    "wall_face_window": (2, 2),
    "wall_face_sign": (3, 2),
    "door": (4, 2),
    "fence_top": (5, 2),
    "fence_face": (6, 2),
    "fence_face_rusty": (7, 2),
}

ROOF_SHEET = "sprites/tiles/roofs.png"
ROOF_SHEET_SIZE = (4 * TILE_SIZE, TILE_SIZE)

# Roofs are only seen from afar, at half size: their art is drawn in blocks of 2×2 pixels.
ROOF_CELLS: dict[str, Cell] = {
    "roof": (0, 0),
    "roof_rusty": (1, 0),
    "roof_patched": (2, 0),
    "roof_eave": (3, 0),
}


class Tileset:
    def __init__(self, sheet: pygame.Surface, cells: Mapping[str, Cell]) -> None:
        self._tiles = {
            name: sheet.subsurface((column * TILE_SIZE, row * TILE_SIZE, TILE_SIZE, TILE_SIZE))
            for name, (column, row) in cells.items()
        }
        self._placeholder = make_placeholder((TILE_SIZE, TILE_SIZE))

    def tile(self, name: str) -> pygame.Surface:
        """Return the named tile, or a placeholder if the sheet has no such tile."""
        return self._tiles.get(name, self._placeholder)
