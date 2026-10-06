"""Freehand building drawings, kept as aligned parts and assembled for presentation.

The four files of a building all use the same canvas.  That makes the contract easy to
understand and easy to mod: a part can be transparent everywhere except where it belongs, and
the game can exchange the roof for the inside without having to guess offsets from an image.
"""

from collections.abc import Iterable

import pygame

from graphics.building_renderer import FACADE_ROWS, BuildingRenderer, building_size
from graphics.illustrations import Illustrations
from graphics.palette import PALETTE
from settings import TILE_SIZE
from world.map import TileMap
from world.room import Room

INSIDE_PART = "inside"
WALLS_PART = "walls"
ROOF_PART = "roof"
DOOR_PART = "door"
BUILDING_PARTS = (INSIDE_PART, WALLS_PART, ROOF_PART, DOOR_PART)
PART_LABELS = {
    INSIDE_PART: "Interior",
    WALLS_PART: "Muros",
    ROOF_PART: "Tejado",
    DOOR_PART: "Puerta",
}
# At the default map zoom the window has two pixels for every pixel of the old map art.  Keeping
# drawings at that detail means they are shown as made, just like dolls and other illustrations.
BUILDING_DETAIL = 2


def building_part_path(room_id: str, part: str) -> str:
    """Path of one freehand part below the illustrations folder."""
    if part not in BUILDING_PARTS:
        raise ValueError(f"Unknown building part: {part}")
    return f"buildings/{room_id}/{part}.png"


def legacy_building_path(room_id: str) -> str:
    """Path used by the older, one-piece illustrated buildings."""
    return f"buildings/{room_id}.png"


def building_canvas_size(room: Room) -> tuple[int, int]:
    width, height = building_size(room)
    return (width * BUILDING_DETAIL, height * BUILDING_DETAIL)


def door_columns(tile_map: TileMap, room: Room) -> tuple[int, ...]:
    """Door columns on the shared canvas, counted in tiles from its left edge."""
    front_y = room.y + room.height
    return tuple(
        x - room.x + 1
        for x in range(room.x - 1, room.x + room.width + 1)
        if tile_map.in_bounds((x, front_y)) and tile_map.terrain_at((x, front_y)) == "door"
    )


def _blank(size: tuple[int, int]) -> pygame.Surface:
    return pygame.Surface(size, pygame.SRCALPHA)


def _only(source: pygame.Surface, rects: Iterable[pygame.Rect]) -> pygame.Surface:
    result = _blank(source.get_size())
    for rect in rects:
        result.blit(source, rect, rect)
    return result


class BuildingArtStore:
    """Loads freehand building parts and assembles closed and open views on demand."""

    def __init__(
        self,
        illustrations: Illustrations | None,
        fallback: BuildingRenderer,
        tile_map: TileMap,
    ) -> None:
        self.illustrations = illustrations
        self.fallback = fallback
        self.tile_map = tile_map
        self._closed: dict[str, pygame.Surface | None] = {}
        self._open: dict[tuple[str, str], pygame.Surface | None] = {}

    def drawings(self, room: Room) -> dict[str, pygame.Surface]:
        """Parts actually saved for a room, at the room's canonical canvas size."""
        if self.illustrations is None:
            return {}
        size = building_canvas_size(room)
        found = {
            part: self.illustrations.fitted(building_part_path(room.room_id, part), size)
            for part in BUILDING_PARTS
        }
        return {part: picture for part, picture in found.items() if picture is not None}

    def has_parts(self, room: Room) -> bool:
        return bool(self.drawings(room))

    def closed(self, room: Room) -> pygame.Surface | None:
        """The roof-on picture, or None when this building has no illustration of its own."""
        if room.room_id not in self._closed:
            self._closed[room.room_id] = self._make_closed(room)
        return self._closed[room.room_id]

    def opened(self, room: Room, foreground: bool) -> pygame.Surface | None:
        """Drawn parts shown with the roof off.

        The inside goes below furniture and residents.  Walls and the door go above them, so the
        front of the building can hide feet without the roof hiding the room.
        """
        key = (room.room_id, "foreground" if foreground else "background")
        if key not in self._open:
            drawings = self.drawings(room)
            names = (WALLS_PART, DOOR_PART) if foreground else (INSIDE_PART,)
            chosen = [drawings[name] for name in names if name in drawings]
            self._open[key] = self._combine(chosen, building_canvas_size(room)) if chosen else None
        return self._open[key]

    def starter(self, room: Room, part: str) -> pygame.Surface:
        """The game's current art separated into one part, as a starting point for the editor."""
        size = building_canvas_size(room)
        old = self.fallback.picture(room)
        old = old if old.get_size() == size else pygame.transform.scale(old, size)
        tile = TILE_SIZE * BUILDING_DETAIL
        facade_top = size[1] - FACADE_ROWS * tile
        doors = set(door_columns(self.tile_map, room))
        if part == ROOF_PART:
            return _only(old, (pygame.Rect(0, 0, size[0], facade_top),))
        if part == WALLS_PART:
            rects = [
                pygame.Rect(column * tile, facade_top, tile, size[1] - facade_top)
                for column in range(room.width + 2)
                if column not in doors
            ]
            return _only(old, rects)
        if part == DOOR_PART:
            rects = [pygame.Rect(column * tile, facade_top, tile, size[1] - facade_top) for column in doors]
            return _only(old, rects)
        # The old standing picture has no inside.  The map's floor remains the fallback in play.
        return _blank(size)

    def zones(self, room: Room, part: str) -> list[tuple[str, pygame.Rect]]:
        """The stretches of the canvas one part is drawn in, each by what it is.

        `floor`, `roof` and `door` are a part each. The walls are the one at the `back`, a `side`
        each way and the `front`, with a `gap` left in it for every door.
        """
        size = building_canvas_size(room)
        tile = TILE_SIZE * BUILDING_DETAIL
        facade_top = size[1] - FACADE_ROWS * tile
        doors = [
            pygame.Rect(column * tile, facade_top, tile, FACADE_ROWS * tile)
            for column in door_columns(self.tile_map, room)
        ]
        if part == INSIDE_PART:
            return [("floor", pygame.Rect(tile, tile * 2, room.width * tile, room.height * tile))]
        if part == ROOF_PART:
            return [("roof", pygame.Rect(0, 0, size[0], facade_top))]
        if part == DOOR_PART:
            return [("door", door) for door in doors]
        if part == WALLS_PART:
            # Back, sides and front as they sit on the map.  The broad front facade may be drawn
            # over the last two rows, matching the old standing buildings.
            return [
                ("back", pygame.Rect(0, tile, size[0], tile)),
                ("side", pygame.Rect(0, tile, tile, (room.height + 2) * tile)),
                ("side", pygame.Rect(size[0] - tile, tile, tile, (room.height + 2) * tile)),
                ("front", pygame.Rect(0, facade_top, size[0], FACADE_ROWS * tile)),
                *(("gap", door) for door in doors),
            ]
        return []

    def example(self, room: Room, part: str) -> pygame.Surface:
        """Something to go by when drawing a part: the game's own art of it, or for the inside,
        which the game has none of, a floor of boards."""
        if part != INSIDE_PART:
            return self.starter(room, part)
        example = _blank(building_canvas_size(room))
        board = TILE_SIZE * BUILDING_DETAIL // 2
        for _, floor in self.zones(room, part):
            pygame.draw.rect(example, PALETTE["copper"], floor)
            for row, y in enumerate(range(floor.top, floor.bottom, board)):
                pygame.draw.line(example, PALETTE["rust_dark"], (floor.left, y), (floor.right - 1, y), BUILDING_DETAIL)
                # Boards end at a different place in each row, as laid boards do.
                for x in range(floor.left + (row % 3 + 1) * board * 2, floor.right, board * 7):
                    pygame.draw.line(example, PALETTE["rust_dark"], (x, y), (x, min(floor.bottom, y + board) - 1), BUILDING_DETAIL)
            pygame.draw.rect(example, PALETTE["rust_dark"], floor, BUILDING_DETAIL)
        return example

    def guide(self, room: Room, part: str) -> pygame.Surface:
        """What is traced over for one part: its zones, tinted and edged, with an example of it under them."""
        size = building_canvas_size(room)
        guide = _blank(size)
        tile = TILE_SIZE * BUILDING_DETAIL
        strong = (*PALETTE["teal"], 210)
        faint = (*PALETTE["teal"], 45)
        joint = (*PALETTE["ember"], 230)
        zones = self.zones(room, part)
        for name, rect in zones:
            if name != "gap":
                pygame.draw.rect(guide, faint, rect)
        for name, rect in zones:
            if name == "gap":
                pygame.draw.rect(guide, (0, 0, 0, 0), rect)
        guide.blit(self.example(room, part), (0, 0))
        for name, rect in zones:
            pygame.draw.rect(guide, joint if name == "gap" else strong, rect, max(1, BUILDING_DETAIL))
        if part == ROOF_PART:
            # The eave: under it the front of the building shows.
            eave = size[1] - FACADE_ROWS * tile - 1
            pygame.draw.line(guide, joint, (0, eave), (size[0] - 1, eave), BUILDING_DETAIL)
        return guide

    def forget(self, room_id: str) -> None:
        self._closed.pop(room_id, None)
        for key in [key for key in self._open if key[0] == room_id]:
            del self._open[key]
        if self.illustrations is not None:
            self.illustrations.forget(legacy_building_path(room_id))
            for part in BUILDING_PARTS:
                self.illustrations.forget(building_part_path(room_id, part))

    def _make_closed(self, room: Room) -> pygame.Surface | None:
        if self.illustrations is None:
            return None
        size = building_canvas_size(room)
        legacy = self.illustrations.fitted(legacy_building_path(room.room_id), size)
        drawings = self.drawings(room)
        if not drawings:
            return legacy
        layers = []
        # A missing part falls back independently.  Saving a clear part is therefore meaningful:
        # it removes that part without making the rest of the building lose its safe fallback.
        for part in (INSIDE_PART, WALLS_PART, DOOR_PART, ROOF_PART):
            layers.append(drawings[part] if part in drawings else self.starter(room, part))
        return self._combine(layers, size)

    @staticmethod
    def _combine(layers: Iterable[pygame.Surface], size: tuple[int, int]) -> pygame.Surface:
        result = _blank(size)
        for layer in layers:
            result.blit(layer, (0, 0))
        return result
