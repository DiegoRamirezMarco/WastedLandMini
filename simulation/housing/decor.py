"""What is put in a building only to be looked at, and what its floor and walls are made of (S42).

Furniture is built, as anything is: somebody is asked and does it. An ornament is not: it goes
where the player says at once and for nothing, on the floor or on the back wall, and comes away
the same. Nobody uses one and nobody walks into one; all it does is make the building what it
is to live in, which `HousingSystem.qualities` reads.

Where an ornament is goes by the building and not by the map, in cells of its inside from its
back left corner, so that it stays where it was put whatever becomes of the building outside.
"""

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from simulation.events.event import DomainEvent
from simulation.housing.housing import HousingResult, Ornament
from world.room import Room

if TYPE_CHECKING:
    from simulation.world import SimulationWorld

# How many cells of the inside of a building go to a tile of it on the map, each way.
CELLS = 2
FLOOR, WALL = "floor", "wall"
DECORATED_EVENT = "house_decorated"
DECORATED_IMPORTANCE = 5
Cell = tuple[int, int]


@dataclass(frozen=True)
class OrnamentDefinition:
    """A kind of thing to be looked at, as data."""

    kind: str
    name: str
    # Where it goes: on the floor or on the back wall.
    on: str = FLOOR
    # The cells it takes: across and, on the floor, towards the front.
    width: int = 1
    height: int = 1
    # Lies flat on the floor, so that anything else can stand on it.
    flat: bool = False


@dataclass(frozen=True)
class DecorSettings:
    """What there is to dress a building with, as data (`data/decor.json`)."""

    ornaments: dict[str, OrnamentDefinition] = field(default_factory=dict)
    # What a floor and a wall can be made of, by ID, with the name of each.
    floors: dict[str, str] = field(default_factory=dict)
    walls: dict[str, str] = field(default_factory=dict)


def decor_settings_from_data(data: dict[str, Any]) -> DecorSettings:
    ornaments = {}
    for kind, entry in data.get("ornaments", {}).items():
        on = str(entry.get("on", FLOOR))
        if on not in (FLOOR, WALL):
            raise ValueError(f"Ornament {kind} goes on neither the floor nor the wall: {on}")
        width, height = int(entry.get("width", 1)), int(entry.get("height", 1))
        if width < 1 or height < 1:
            raise ValueError(f"Ornament {kind} must take up at least a cell")
        ornaments[str(kind)] = OrnamentDefinition(
            str(kind),
            str(entry.get("name", kind)),
            on,
            width,
            # What hangs takes only a stretch of the wall.
            height if on == FLOOR else 1,
            bool(entry.get("flat", False)) and on == FLOOR,
        )
    return DecorSettings(
        ornaments,
        {str(floor_id): str(name) for floor_id, name in data.get("floors", {}).items()},
        {str(wall_id): str(name) for wall_id, name in data.get("walls", {}).items()},
    )


class DecorSystem:
    def settings(self, world: "SimulationWorld") -> DecorSettings:
        return world.registries.decor

    def size(self, room: Room) -> Cell:
        """How many cells the inside of a building is across and deep."""
        return (room.width * CELLS, room.height * CELLS)

    def furniture_cells(self, world: "SimulationWorld", room: Room) -> set[Cell]:
        """The cells of the inside that what stands in a building, or is being put up in it, takes."""
        taken: set[Cell] = set()
        for placed in world.interactables.values():
            if not room.contains((placed.x, placed.y)):
                continue
            definition = world.definition_of(placed)
            column, row = (placed.x - room.x) * CELLS, (placed.y - room.y) * CELLS
            taken.update((column + across, row + down) for across in range(definition.width) for down in range(definition.height))
        for site in world.sites.values():
            tiles = [tile for tile in (site.tiles or [(site.x, site.y)]) if room.contains(tile)]
            if tiles:
                column = (min(x for x, _ in tiles) - room.x) * CELLS
                row = (min(y for _, y in tiles) - room.y) * CELLS
                wide = max(x for x, _ in tiles) - min(x for x, _ in tiles) + 1
                deep = max(y for _, y in tiles) - min(y for _, y in tiles) + 1
                taken.update((column + across, row + down) for across in range(wide) for down in range(deep))
        return taken

    def cells(self, definition: OrnamentDefinition, x: int, y: int) -> set[Cell]:
        return {(x + across, y + down) for across in range(definition.width) for down in range(definition.height)}

    def ornaments(self, world: "SimulationWorld", room_id: str) -> list[Ornament]:
        """What has been put in a building to be looked at, of kinds there still are."""
        known = self.settings(world).ornaments
        return [ornament for ornament in world.homes.ornaments.get(room_id, []) if ornament.kind in known]

    def error(self, world: "SimulationWorld", room_id: str, kind: str, x: int, y: int) -> str | None:
        """Why an ornament cannot go there. None means it can."""
        room = world.rooms.get(room_id)
        definition = self.settings(world).ornaments.get(kind)
        if room is None or not room.roofed:
            return "No hay tal edificio"
        if definition is None:
            return "No hay tal adorno"
        columns, rows = self.size(room)
        if definition.on == WALL:
            y = 0
            rows = 1
        if x < 0 or y < 0 or x + definition.width > columns or y + definition.height > rows:
            return "Ahí no cabe"
        wanted = self.cells(definition, x, y)
        known = self.settings(world).ornaments
        for other in self.ornaments(world, room_id):
            theirs = known[other.kind]
            # What lies flat is only in the way of what else lies flat, and the wall is its own place.
            if other.on == definition.on and theirs.flat == definition.flat and wanted & self.cells(theirs, other.x, other.y):
                return f"Ahí ya hay {theirs.name}"
        if definition.on == FLOOR and not definition.flat and wanted & self.furniture_cells(world, room):
            return "Ahí hay un mueble"
        return None

    def place(self, world: "SimulationWorld", room_id: str, kind: str, x: int, y: int) -> HousingResult:
        """Put an ornament in a building, at once and for nothing."""
        error = self.error(world, room_id, kind, x, y)
        if error is not None:
            return HousingResult(False, error)
        definition = self.settings(world).ornaments[kind]
        homes = world.homes
        homes.ornament_count += 1
        ornament = Ornament(f"ornament_{homes.ornament_count}", kind, definition.on, x, y if definition.on == FLOOR else 0)
        homes.ornaments.setdefault(room_id, []).append(ornament)
        self._changed(world, room_id, f"Se pone {definition.name} en {world.rooms[room_id].name}")
        return HousingResult(True, f"Puesto: {definition.name}")

    def at(self, world: "SimulationWorld", room_id: str, on: str, cell: Cell) -> Ornament | None:
        """The ornament at a cell of the floor, or at a stretch of the wall: what stands before what lies under it."""
        known = self.settings(world).ornaments
        found = [
            ornament
            for ornament in self.ornaments(world, room_id)
            if ornament.on == on and (cell[0], cell[1] if on == FLOOR else 0) in self.cells(known[ornament.kind], ornament.x, ornament.y)
        ]
        found.sort(key=lambda ornament: known[ornament.kind].flat)
        return found[0] if found else None

    def remove(self, world: "SimulationWorld", room_id: str, ornament_id: str) -> HousingResult:
        """Take an ornament away."""
        kept = world.homes.ornaments.get(room_id, [])
        ornament = next((each for each in kept if each.ornament_id == ornament_id), None)
        if ornament is None:
            return HousingResult(False, "Ahí no hay ningún adorno")
        kept.remove(ornament)
        if not kept:
            world.homes.ornaments.pop(room_id, None)
        definition = self.settings(world).ornaments.get(ornament.kind)
        name = definition.name if definition is not None else ornament.kind
        room = world.rooms.get(room_id)
        self._changed(world, room_id, f"Se quita {name}" + (f" de {room.name}" if room is not None else ""))
        return HousingResult(True, f"Quitado: {name}")

    def surface(self, world: "SimulationWorld", room_id: str, floor: str | None = None, wall: str | None = None) -> HousingResult:
        """Say what the floor of a building is made of, its walls, or both. Nothing said of one puts it back as it was built."""
        room = world.rooms.get(room_id)
        if room is None or not room.roofed:
            return HousingResult(False, "No hay tal edificio")
        settings = self.settings(world)
        if floor and floor not in settings.floors:
            return HousingResult(False, "No hay tal suelo")
        if wall and wall not in settings.walls:
            return HousingResult(False, "No hay tal pared")
        said = []
        for chosen, kept, names in ((floor, world.homes.floors, settings.floors), (wall, world.homes.walls, settings.walls)):
            if chosen is None:
                continue
            if chosen:
                kept[room_id] = chosen
                said.append(names[chosen])
            else:
                kept.pop(room_id, None)
                said.append("como estaba")
        self._changed(world, room_id, f"Se cambia {room.name} por dentro")
        return HousingResult(True, ", ".join(said).capitalize() if said else "Queda como estaba")

    def floor_of(self, world: "SimulationWorld", room_id: str) -> str | None:
        """What the player has said the floor of a building is made of, if it is of a kind there still is."""
        floor = world.homes.floors.get(room_id)
        return floor if floor in self.settings(world).floors else None

    def wall_of(self, world: "SimulationWorld", room_id: str) -> str | None:
        wall = world.homes.walls.get(room_id)
        return wall if wall in self.settings(world).walls else None

    def _changed(self, world: "SimulationWorld", room_id: str, text: str) -> None:
        world.emit_event(DomainEvent(DECORATED_EVENT, DECORATED_IMPORTANCE, text, data={"room": room_id}))
