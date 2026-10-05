"""A whole building as one picture: its roof, its walls and its front, as seen from the open ground before it."""

import pygame

from graphics.assets import AssetStore
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
        name = f"{room.room_id}.png"
        if self._custom is not None and name in self._custom.files(CUSTOM_FOLDER):
            # A picture from a pack may be of any size: it is brought to the size of the building.
            picture = self._custom.image(f"{CUSTOM_FOLDER}/{name}")
            return picture if picture.get_size() == size else pygame.transform.scale(picture, size)
        return self._assets.image(building_path(room.room_id), size=size)
