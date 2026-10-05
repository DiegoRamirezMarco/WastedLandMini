"""A picture of each roofed building of each map, put together from the tiles and given some height.

    python -m tools.art.buildings    list every building with the size its picture must have

The pictures are starter art like any other: one that exists is never overwritten, and a picture of
the same name under `custom_content/buildings/` takes its place in the game.
"""

import zlib

import pygame

from graphics.building_renderer import FACADE_ROWS, HEADROOM, building_path, building_size
from graphics.map_renderer import roof_names
from graphics.palette import PALETTE
from graphics.tileset import (
    CLOSE_ROOF_SHEET,
    ROOF_CELLS,
    SETTLEMENT_CELLS,
    SETTLEMENT_SHEET,
    Tileset,
)
from settings import TILE_SIZE
from simulation.registries import builtin_registries
from tools.art import tiles
from world.room import Room
from world.settlement import SettlementLayout

# The cloth over a door: its colour, striped with `bone`.
AWNINGS = ("teal", "blood", "olive", "plum", "ochre", "steel")
AWNING_HEIGHT = 7
AWNING_OVERHANG = 4
STRIPE = 4
# Height of the far slope of a roof, above its ridge.
FAR_SLOPE = 5


def _awning(surface: pygame.Surface, left: int, top: int, color: str) -> None:
    width = TILE_SIZE + AWNING_OVERHANG * 2
    pygame.draw.rect(surface, PALETTE["ink"], (left - 1, top - 1, width + 2, AWNING_HEIGHT + 2))
    for x in range(width):
        stripe = color if (x // STRIPE) % 2 == 0 else "bone"
        # Every other stripe hangs a pixel lower, which is what makes it cloth.
        height = AWNING_HEIGHT if (x // STRIPE) % 2 == 0 else AWNING_HEIGHT - 1
        surface.fill(PALETTE[stripe], (left + x, top, 1, height))
    surface.fill(PALETTE["shadow"], (left, top + AWNING_HEIGHT + 1, width, 1))


def _picture(layout: SettlementLayout, room: Room, ground: Tileset, roofing: Tileset) -> pygame.Surface:
    width, height = building_size(room)
    surface = pygame.Surface((width, height), pygame.SRCALPHA)
    seed = zlib.crc32(room.room_id.encode("utf-8"))
    facade_top = height - FACADE_ROWS * TILE_SIZE
    columns = room.width + 2
    front_row = room.y + room.height

    # The front: a course of planks, and under it the wall the map has, door and all.
    for column in range(columns):
        x = room.x - 1 + column
        left = column * TILE_SIZE
        surface.blit(ground.tile("wall_face"), (left, facade_top))
        terrain = layout.tile_map.terrain_at((x, front_row))
        if terrain == "door":
            name = "door"
        else:
            name = "wall_face_window" if x % 4 == 0 else "wall_face"
        surface.blit(ground.tile(name), (left, facade_top + TILE_SIZE))

    # The roof, from the top of the picture down to the eave over the front.
    names = roof_names(layout.tile_map, [room])
    rows = facade_top // TILE_SIZE
    for row in range(rows):
        for column in range(columns):
            # The headroom has no tile of the map under it: it takes after the row below.
            tile = (room.x - 1 + column, room.y - 1 + max(0, row - HEADROOM // TILE_SIZE))
            name = "roof_eave" if row == rows - 1 else names.get(tile, "roof")
            name = "roof" if name == "roof_eave" and row != rows - 1 else name
            surface.blit(roofing.tile(name), (column * TILE_SIZE, row * TILE_SIZE))
    # Its far slope is in shade, above a ridge that catches the light.
    for x in range(width):
        surface.fill(PALETTE["iron" if x % 4 == 3 else "stone"], (x, 1, 1, FAR_SLOPE))
    surface.fill(PALETTE["bone"], (0, FAR_SLOPE + 1, width, 1))
    surface.fill(PALETTE["shadow"], (0, FAR_SLOPE + 2, width, 1))
    # The shadow of the eave on the planks.
    surface.fill(PALETTE["ink"], (0, facade_top, width, 1))
    surface.fill(PALETTE["rust_dark"], (0, facade_top + 1, width, 2))

    # Something on the roof: a vent, or a plate over a hole.
    vent_x = 8 + seed % max(1, width - 24)
    vent_y = FAR_SLOPE + 8 + (seed // 7) % max(1, facade_top - FAR_SLOPE - 28)
    if seed % 2:
        pygame.draw.rect(surface, PALETTE["ink"], (vent_x, vent_y, 8, 7))
        pygame.draw.rect(surface, PALETTE["stone"], (vent_x + 1, vent_y + 1, 6, 5))
        surface.fill(PALETTE["shadow"], (vent_x + 2, vent_y + 2, 4, 1))
        surface.fill(PALETTE["shadow"], (vent_x + 2, vent_y + 4, 4, 1))
    else:
        pygame.draw.rect(surface, PALETTE["ink"], (vent_x, vent_y, 10, 8))
        pygame.draw.rect(surface, PALETTE["rust"], (vent_x + 1, vent_y + 1, 8, 6))
        for corner in ((vent_x + 2, vent_y + 2), (vent_x + 7, vent_y + 2), (vent_x + 2, vent_y + 5), (vent_x + 7, vent_y + 5)):
            surface.set_at(corner, PALETTE["copper"])

    # A cloth over every door, in a colour of the building's own.
    for column in range(columns):
        if layout.tile_map.terrain_at((room.x - 1 + column, front_row)) == "door":
            _awning(surface, column * TILE_SIZE - AWNING_OVERHANG, facade_top + TILE_SIZE - AWNING_HEIGHT - 1, AWNINGS[seed % len(AWNINGS)])

    # An outline down both sides and along the foot, so that it stands apart from the ground.
    surface.fill(PALETTE["ink"], (0, 0, width, 1))
    surface.fill(PALETTE["ink"], (0, 0, 1, height))
    surface.fill(PALETTE["ink"], (width - 1, 0, 1, height))
    surface.fill(PALETTE["ink"], (0, height - 1, width, 1))
    return surface


def buildings() -> list[tuple[SettlementLayout, Room]]:
    """Every roofed room of every built-in map."""
    return [
        (layout, room)
        for layout in builtin_registries().maps.values()
        for room in layout.rooms.values()
        if room.roofed
    ]


def build() -> dict[str, pygame.Surface]:
    sheets = tiles.build()
    ground = Tileset(sheets[SETTLEMENT_SHEET], SETTLEMENT_CELLS)
    roofing = Tileset(sheets[CLOSE_ROOF_SHEET], ROOF_CELLS)
    return {building_path(room.room_id): _picture(layout, room, ground, roofing) for layout, room in buildings()}


def main() -> None:
    print("Building        Picture size   Door, in pixels from its left edge")
    for layout, room in buildings():
        width, height = building_size(room)
        doors = [
            (x - room.x + 1) * TILE_SIZE
            for x in range(room.x - 1, room.x + room.width + 1)
            if layout.tile_map.terrain_at((x, room.y + room.height)) == "door"
        ]
        print(f"{room.room_id:<15} {width}x{height:<10} {', '.join(str(door) for door in doors) or 'none'}")


if __name__ == "__main__":
    main()
