"""Draws a tile map's terrain. Chooses which tile shows each terrain; owns no map state."""

from collections.abc import Collection, Iterable, Mapping

import pygame

from graphics.tileset import Tileset
from settings import TILE_SIZE
from world.map import Tile, TileMap
from world.room import Room

# Terrain that stands up from the ground: seen from the front where it ends, from above elsewhere.
RAISED = {"wall": ("wall_top", "wall_face"), "fence": ("fence_top", "fence_face")}
# Terrain drawn over bare ground because its tiles have transparent parts.
OVER_DIRT = {"fence", "gate"}
# The tiles that are bare ground, which an illustration of the ground takes the place of.
GROUND_TILES = ("dirt", "dirt_pebbles", "grass", "grass_tuft")


def _scatter(x: int, y: int) -> int:
    """Stable pseudo-random number per tile, used to vary repeated tiles."""
    return ((x * 73856093) ^ (y * 19349663)) % 29


def _is(tile_map: TileMap, tile: Tile, terrain: str) -> bool:
    return tile_map.in_bounds(tile) and tile_map.terrain_at(tile) == terrain


def _shows_face(tile_map: TileMap, x: int, y: int, terrain: str) -> bool:
    if not _is(tile_map, (x, y + 1), terrain):
        return True
    # The end of a horizontal run with nothing behind it is a corner seen from the front.
    beside = _is(tile_map, (x - 1, y), terrain) or _is(tile_map, (x + 1, y), terrain)
    return beside and not _is(tile_map, (x, y - 1), terrain)


def tile_names(tile_map: TileMap, x: int, y: int) -> list[str]:
    """Tiles to draw at a position, bottom layer first."""
    terrain = tile_map.terrain_at((x, y))
    scatter = _scatter(x, y)
    layers = ["dirt"] if terrain in OVER_DIRT else []
    if terrain in RAISED:
        top, face = RAISED[terrain]
        if not _shows_face(tile_map, x, y, terrain):
            name = top
        elif terrain == "wall":
            name = "wall_face_window" if x % 4 == 0 else face
        else:
            name = "fence_face_rusty" if scatter < 9 else face
    elif terrain == "dirt":
        name = "dirt_pebbles" if scatter < 3 else "dirt"
    elif terrain == "grass":
        name = "grass_tuft" if scatter < 8 else "grass"
    elif terrain == "floor_concrete":
        name = {0: "floor_cracked", 1: "floor_stained"}.get(scatter, "floor_concrete")
    else:
        # Any other terrain uses the tile with the same name, or a placeholder if there is none.
        name = terrain
    return [*layers, name]


def render_terrain(tile_map: TileMap, tileset: Tileset, without: Collection[str] = ()) -> pygame.Surface:
    """The terrain of a whole map as one picture.

    With `without`, the tiles of those names are left out and the picture is clear where they
    were: what stands on the ground, to go over a ground drawn some other way.
    """
    size = (tile_map.width * TILE_SIZE, tile_map.height * TILE_SIZE)
    surface = pygame.Surface(size, pygame.SRCALPHA) if without else pygame.Surface(size)
    for y in range(tile_map.height):
        for x in range(tile_map.width):
            for name in tile_names(tile_map, x, y):
                if name not in without:
                    surface.blit(tileset.tile(name), (x * TILE_SIZE, y * TILE_SIZE))
    return surface


def roof_names(tile_map: TileMap, rooms: Iterable[Room]) -> dict[Tile, str]:
    """Roof tile over each position that a roofed room covers.

    A roof spans the room and the walls behind and beside it. The wall in front, the one with the
    door, stays in view below the eave.
    """
    names: dict[Tile, str] = {}
    for room in rooms:
        if not room.roofed:
            continue
        eave = room.y + room.height - 1
        for y in range(room.y - 1, eave + 1):
            for x in range(room.x - 1, room.x + room.width + 1):
                if not tile_map.in_bounds((x, y)):
                    continue
                scatter = _scatter(x, y)
                if y == eave:
                    names[(x, y)] = "roof_eave"
                elif scatter < 3:
                    names[(x, y)] = "roof_patched"
                else:
                    names[(x, y)] = "roof_rusty" if scatter < 9 else "roof"
    return names


def render_roofs(terrain: pygame.Surface, roofs: Mapping[Tile, str], tileset: Tileset) -> pygame.Surface:
    """A copy of the rendered terrain with the roofs on."""
    surface = terrain.copy()
    for (x, y), name in roofs.items():
        surface.blit(tileset.tile(name), (x * TILE_SIZE, y * TILE_SIZE))
    return surface
