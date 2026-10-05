from dataclasses import dataclass

Tile = tuple[int, int]


@dataclass(frozen=True)
class TerrainDefinition:
    terrain_id: str
    walkable: bool = True
    # Blocks line of sight.
    opaque: bool = False


@dataclass
class TileMap:
    """Grid of terrain IDs, indexed as `tiles[y][x]`."""

    width: int
    height: int
    tiles: list[list[str]]

    def in_bounds(self, tile: Tile) -> bool:
        return 0 <= tile[0] < self.width and 0 <= tile[1] < self.height

    def terrain_at(self, tile: Tile) -> str:
        return self.tiles[tile[1]][tile[0]]
