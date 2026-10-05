from dataclasses import dataclass

from world.map import Tile


@dataclass
class Room:
    room_id: str
    name: str
    privacy: float = 0.0
    x: int = 0
    y: int = 0
    width: int = 0
    height: int = 0
    # A building with a roof over it, as opposed to a named stretch of open ground.
    roofed: bool = False
    # Stable data definition used to construct this room, if it was added in urbanism mode.
    blueprint_id: str | None = None

    def contains(self, tile: Tile) -> bool:
        return self.x <= tile[0] < self.x + self.width and self.y <= tile[1] < self.y + self.height
