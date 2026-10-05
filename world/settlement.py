from dataclasses import dataclass, field
from typing import Any

from world.interactable import Interactable
from world.map import Tile, TileMap
from world.room import Room


@dataclass(frozen=True)
class StockEntry:
    """Items inside a container when a new settlement starts."""

    container: str
    item: str
    count: int = 1
    owner: str | None = None


@dataclass(frozen=True)
class SupplyRule:
    """Items that arrive in a container every day at a given hour."""

    container: str
    item: str
    count: int
    hour: int = 7


@dataclass
class SettlementLayout:
    """A map as authored: terrain, rooms, the objects placed on it and where residents start."""

    map_id: str
    tile_map: TileMap
    rooms: dict[str, Room]
    interactables: dict[str, Interactable]
    spawns: list[Tile]
    stock: list[StockEntry] = field(default_factory=list)
    supplies: list[SupplyRule] = field(default_factory=list)
    # Plots where the dead are buried, in the order they are used.
    graves: list[Tile] = field(default_factory=list)


def layout_from_data(data: dict[str, Any], source: str = "<data>") -> SettlementLayout:
    missing = {"id", "legend", "rows"} - data.keys()
    if missing:
        raise ValueError(f"Missing fields in map {source}: {sorted(missing)}")
    legend = {str(char): str(terrain_id) for char, terrain_id in data["legend"].items()}
    rows = [str(row) for row in data["rows"]]
    if not rows:
        raise ValueError(f"Map {source} has no rows")
    width = len(rows[0])
    tiles: list[list[str]] = []
    for y, row in enumerate(rows):
        if len(row) != width:
            raise ValueError(f"Map {source} row {y} is {len(row)} wide, expected {width}")
        unknown = set(row) - legend.keys()
        if unknown:
            raise ValueError(f"Map {source} row {y} uses characters not in the legend: {sorted(unknown)}")
        tiles.append([legend[char] for char in row])

    rooms = {
        str(room["id"]): Room(
            room_id=str(room["id"]),
            name=str(room.get("name", room["id"])),
            privacy=float(room.get("privacy", 0.0)),
            x=int(room["x"]),
            y=int(room["y"]),
            width=int(room["width"]),
            height=int(room["height"]),
            roofed=bool(room.get("roofed", False)),
        )
        for room in data.get("rooms", [])
    }
    interactables: dict[str, Interactable] = {}
    for placed in data.get("objects", []):
        object_id = str(placed["id"])
        if object_id in interactables:
            raise ValueError(f"Duplicate object id in map {source}: {object_id}")
        interactables[object_id] = Interactable(
            object_id, str(placed["kind"]), int(placed["x"]), int(placed["y"])
        )
    spawns = [(int(spawn[0]), int(spawn[1])) for spawn in data.get("spawns", [])]
    return SettlementLayout(
        map_id=str(data["id"]),
        tile_map=TileMap(width=width, height=len(tiles), tiles=tiles),
        rooms=rooms,
        interactables=interactables,
        spawns=spawns,
        stock=[
            StockEntry(
                str(entry["container"]),
                str(entry["item"]),
                int(entry.get("count", 1)),
                str(entry["owner"]) if entry.get("owner") is not None else None,
            )
            for entry in data.get("stock", [])
        ],
        supplies=[
            SupplyRule(str(rule["container"]), str(rule["item"]), int(rule["count"]), int(rule.get("hour", 7)))
            for rule in data.get("supplies", [])
        ],
        graves=[(int(plot[0]), int(plot[1])) for plot in data.get("graves", [])],
    )
