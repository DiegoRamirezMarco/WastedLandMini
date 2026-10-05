"""A whole building as one picture: its roof, its walls and its front, as seen from the open ground before it."""

import pygame

from graphics.assets import AssetStore
from graphics.palette import PALETTE
from settings import TILE_SIZE
from world.room import Room

# How far the picture of a building rises above the wall at its back, which is what gives it height.
HEADROOM = TILE_SIZE
# Rows of tiles its front takes up, counted from the wall with the door in it upwards.
FACADE_ROWS = 2
# A picture of the same building in a content pack takes the place of the game's own.
CUSTOM_FOLDER = "buildings"


def building_path(room_id: str) -> str:
    return f"sprites/buildings/{room_id}.png"


def building_size(room: Room) -> tuple[int, int]:
    """The size of a building's picture: the room, the walls round it, and the headroom."""
    return ((room.width + 2) * TILE_SIZE, (room.height + 2) * TILE_SIZE + HEADROOM)


def building_area(room: Room) -> pygame.Rect:
    """Where on the map a building's picture goes, in map pixels. Its foot is the foot of the front wall."""
    width, height = building_size(room)
    return pygame.Rect((room.x - 1) * TILE_SIZE, (room.y + room.height + 1) * TILE_SIZE - height, width, height)


class BuildingRenderer:
    def __init__(self, assets: AssetStore, custom: AssetStore | None = None) -> None:
        self._assets = assets
        self._custom = custom
        self._pictures: dict[str, pygame.Surface] = {}

    def picture(self, room: Room) -> pygame.Surface:
        """The picture of a building with its roof on. A missing one yields a placeholder of the right size."""
        if room.room_id not in self._pictures:
            self._pictures[room.room_id] = self._load(room)
        return self._pictures[room.room_id]

    def _load(self, room: Room) -> pygame.Surface:
        size = building_size(room)
        names = [f"{room.room_id}.png"]
        if room.blueprint_id is not None:
            names.append(f"{room.blueprint_id}.png")
        if self._custom is not None:
            paths = [f"{CUSTOM_FOLDER}/{name}" for name in names]
            if room.blueprint_id is not None:
                paths.insert(0, f"{CUSTOM_FOLDER}/{room.blueprint_id}/sprite.png")
            for path in paths:
                picture = self._custom.optional_image(path)
                if picture is not None:
                    return picture if picture.get_size() == size else pygame.transform.scale(picture, size)
        for name in names:
            picture = self._assets.optional_image(f"sprites/buildings/{name}")
            if picture is not None:
                return picture if picture.get_size() == size else pygame.transform.scale(picture, size)
        # Authored map rooms keep the long-standing visible placeholder contract. Urbanism
        # buildings have a blueprint ID and get a usable procedural starter instead.
        return procedural_building(room) if room.blueprint_id is not None else self._assets.image(
            building_path(room.room_id), size=size
        )


def procedural_building(room: Room) -> pygame.Surface:
    """Readable fallback art for a newly constructed building without a supplied drawing."""
    size = building_size(room)
    surface = pygame.Surface(size, pygame.SRCALPHA)
    facade_top = size[1] - FACADE_ROWS * TILE_SIZE
    roof = pygame.Rect(0, TILE_SIZE // 2, size[0], max(TILE_SIZE, facade_top - TILE_SIZE // 2))
    pygame.draw.rect(surface, PALETTE["rust_dark"], roof)
    pygame.draw.polygon(
        surface,
        PALETTE["rust"],
        ((0, roof.y + TILE_SIZE), (size[0] - 1, roof.y), (size[0] - 1, roof.bottom), (0, roof.bottom)),
    )
    pygame.draw.line(surface, PALETTE["copper"], (0, roof.bottom - 1), (size[0] - 1, roof.bottom - 1), 2)
    pygame.draw.rect(surface, PALETTE["earth_dark"], (0, facade_top, size[0], size[1] - facade_top))
    pygame.draw.rect(surface, PALETTE["stone"], (0, facade_top, size[0], TILE_SIZE // 3))
    door_x = (room.width // 2 + 1) * TILE_SIZE
    pygame.draw.rect(
        surface,
        PALETTE["rust_dark"],
        (door_x, facade_top + TILE_SIZE // 2, TILE_SIZE, size[1] - facade_top - TILE_SIZE // 2),
    )
    for column in range(1, room.width + 1, 2):
        if column == room.width // 2 + 1:
            continue
        pygame.draw.rect(
            surface,
            PALETTE["deep"],
            (column * TILE_SIZE + 4, facade_top + 6, TILE_SIZE - 8, TILE_SIZE - 7),
        )
    pygame.draw.rect(surface, PALETTE["ink"], surface.get_rect(), 1)
    return surface
