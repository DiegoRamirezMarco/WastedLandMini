"""Domain rules for changing the settlement layout without depending on pygame."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from simulation.events.event import DomainEvent
from simulation.items.inventory import Inventory
from world.build import BUILDING_SITE, BuildRule, BuildSite, build_rule_from_data
from world.interactable import Interactable, InteractableDefinition
from world.map import Tile
from world.pathfinding import NEIGHBOURS
from world.room import Room

if TYPE_CHECKING:
    from simulation.world import SimulationWorld

BUILDING_EVENT_IMPORTANCE = 20
BUILDABLE_TERRAIN = {"dirt", "grass", "soil"}
SITE_IN_THE_WAY = "Ese espacio está marcado para una obra"
CUT_OFF = "Dejaría un rincón sin salida"


@dataclass(frozen=True)
class BuildingDefinition:
    blueprint_id: str
    name: str
    width: int
    height: int
    floor: str = "floor_wood"
    privacy: float = 0.4
    # What putting one up takes. None for a building that is simply put down.
    build: BuildRule | None = None


def building_definition_from_data(blueprint_id: str, data: dict[str, Any]) -> BuildingDefinition:
    missing = {"name", "width", "height"} - data.keys()
    if missing:
        raise ValueError(f"Missing fields in building {blueprint_id}: {sorted(missing)}")
    definition = BuildingDefinition(
        blueprint_id=blueprint_id,
        name=str(data["name"]),
        width=int(data["width"]),
        height=int(data["height"]),
        floor=str(data.get("floor", "floor_wood")),
        privacy=float(data.get("privacy", 0.4)),
        build=build_rule_from_data(f"building {blueprint_id}", data.get("build")),
    )
    if definition.width < 2 or definition.height < 2:
        raise ValueError(f"Building {blueprint_id} must be at least 2 by 2 tiles inside")
    if not 0.0 <= definition.privacy <= 1.0:
        raise ValueError(f"Building {blueprint_id} privacy must be between 0 and 1")
    return definition


@dataclass(frozen=True)
class UrbanismResult:
    ok: bool
    message: str
    entity_id: str | None = None


@dataclass
class UrbanismSystem:
    """Placement state and operations owned by the simulation world."""

    # Terrain hidden below each constructed building, needed to remove or move it later.
    underlays: dict[str, dict[Tile, str]] = field(default_factory=dict)
    next_object: int = 1
    next_building: int = 1

    def place_object(self, world: SimulationWorld, kind: str, tile: Tile) -> UrbanismResult:
        error = self.object_error(world, kind, tile)
        if error is not None:
            return UrbanismResult(False, error)
        object_id = self.raise_object(world, kind, tile)
        definition = world.registries.interactables.get(kind)
        self._announce(world, f"Se coloca {definition.article} {definition.name}", tile, object_id)
        return UrbanismResult(True, f"{definition.name.capitalize()} colocado", object_id)

    def raise_object(self, world: SimulationWorld, kind: str, tile: Tile) -> str:
        """Stand an object where it has already been settled that it can go. Returns its ID."""
        object_id = self._fresh_object_id(world, kind)
        placed = Interactable(object_id, kind, tile[0], tile[1])
        world.interactables[object_id] = placed
        definition = world.definition_of(placed)
        if definition.container:
            world.containers[object_id] = Inventory()
        self.invalidate_routes(world, set(placed.footprint(definition)))
        return object_id

    def move_object(self, world: SimulationWorld, object_id: str, tile: Tile) -> UrbanismResult:
        placed = world.interactables.get(object_id)
        if placed is None:
            return UrbanismResult(False, "Ese objeto ya no existe")
        error = self.move_object_error(world, object_id, tile)
        if error is not None:
            return UrbanismResult(False, error, object_id)
        placed.x, placed.y = tile
        self.invalidate_routes(
            world,
            set(placed.footprint(world.definition_of(placed))),
            target_ids={object_id},
        )
        self._announce(world, f"Se mueve {world.definition_of(placed).name}", tile, object_id)
        return UrbanismResult(True, "Objeto movido", object_id)

    def move_object_error(self, world: SimulationWorld, object_id: str, tile: Tile) -> str | None:
        """Why this object cannot go there, without moving it. None means it can."""
        placed = world.interactables.get(object_id)
        if placed is None:
            return "Ese objeto ya no existe"
        return self._object_busy_reason(world, object_id) or self.object_error(
            world, placed.kind, tile, ignore_object=object_id
        )

    def remove_object(self, world: SimulationWorld, object_id: str) -> UrbanismResult:
        placed = world.interactables.get(object_id)
        if placed is None:
            return UrbanismResult(False, "Ese objeto ya no existe")
        busy = self._object_busy_reason(world, object_id)
        if busy is not None:
            return UrbanismResult(False, busy, object_id)
        inventory = world.containers.get(object_id)
        if inventory is not None and inventory.items:
            return UrbanismResult(False, "Vacía el mueble antes de retirarlo", object_id)
        definition = world.definition_of(placed)
        del world.interactables[object_id]
        world.containers.pop(object_id, None)
        self.invalidate_routes(world, set(), target_ids={object_id})
        self._announce(world, f"Se retira {definition.name}", (placed.x, placed.y), object_id)
        return UrbanismResult(True, f"{definition.name.capitalize()} retirado")

    def object_error(
        self,
        world: SimulationWorld,
        kind: str,
        tile: Tile,
        ignore_object: str | None = None,
    ) -> str | None:
        definition = world.registries.interactables.find(kind)
        if definition is None:
            return "Ese tipo de objeto no está disponible"
        candidate = Interactable("preview", kind, tile[0], tile[1])
        footprint = set(candidate.footprint(definition))
        if not footprint or not all(world.tile_map.in_bounds(point) for point in footprint):
            return "No cabe dentro del mapa"
        if any(
            not world.registries.terrain[world.tile_map.terrain_at(point)].walkable
            for point in footprint
        ):
            return "Necesita suelo transitable"
        occupied = {
            point
            for placed in world.interactables.values()
            if placed.object_id != ignore_object
            for point in placed.footprint(world.definition_of(placed))
        }
        if footprint & occupied:
            return "Ese espacio ya está ocupado"
        if footprint & self._marked_out(world):
            return SITE_IN_THE_WAY
        if any(not resident.away and resident.tile in footprint for resident in world.residents.values()):
            return "Hay un residente en ese espacio"
        others = [placed for placed in world.interactables.values() if placed.object_id != ignore_object]
        open_after = self._walkable(world) - self._blocked(world, others)
        if definition.blocks:
            open_after -= footprint
        return self._access_error(world, open_after, others, list(world.rooms.values()), candidate=candidate)

    def place_building(
        self, world: SimulationWorld, blueprint_id: str, tile: Tile
    ) -> UrbanismResult:
        definition = world.registries.buildings.get(blueprint_id)
        if definition is None:
            return UrbanismResult(False, "Ese edificio no está disponible")
        error = self.building_error(world, definition.width, definition.height, tile)
        if error is not None:
            return UrbanismResult(False, error)
        room_id = self.raise_building(world, blueprint_id, tile)
        self._announce(world, f"Se construye {definition.name}", tile, room_id)
        return UrbanismResult(True, f"{definition.name.capitalize()} construido", room_id)

    def raise_building(self, world: SimulationWorld, blueprint_id: str, tile: Tile) -> str:
        """Stand a building where it has already been settled that it can go. Returns its room's ID."""
        definition = world.registries.buildings[blueprint_id]
        room_id = self._fresh_building_id(world, blueprint_id)
        room = Room(
            room_id,
            definition.name,
            definition.privacy,
            tile[0],
            tile[1],
            definition.width,
            definition.height,
            True,
            blueprint_id,
        )
        self._construct(world, room, definition.floor)
        self.invalidate_routes(world, set(self._building_tiles(room)))
        return room_id

    def move_building(self, world: SimulationWorld, room_id: str, tile: Tile) -> UrbanismResult:
        room = world.rooms.get(room_id)
        if room is None or not room.roofed:
            return UrbanismResult(False, "Ese edificio ya no existe")
        error = self.move_building_error(world, room_id, tile)
        if error is not None:
            return UrbanismResult(False, error, room_id)
        floor = self._floor_for(world, room)
        old_tiles = set(self._building_tiles(room))
        self._restore_underlay(world, room)
        room.x, room.y = tile
        self._construct(world, room, floor)
        self.invalidate_routes(world, old_tiles | set(self._building_tiles(room)))
        self._announce(world, f"Se traslada {room.name}", tile, room_id)
        return UrbanismResult(True, "Edificio movido", room_id)

    def move_building_error(self, world: SimulationWorld, room_id: str, tile: Tile) -> str | None:
        """Why this building cannot go there, without lifting it. None means it can."""
        room = world.rooms.get(room_id)
        if room is None or not room.roofed:
            return "Ese edificio ya no existe"
        return self._building_contents(world, room) or self.building_error(
            world, room.width, room.height, tile, ignore_room=room_id
        )

    def remove_building(self, world: SimulationWorld, room_id: str) -> UrbanismResult:
        room = world.rooms.get(room_id)
        if room is None or not room.roofed:
            return UrbanismResult(False, "Ese edificio ya no existe")
        blocked = self._building_contents(world, room)
        if blocked is not None:
            return UrbanismResult(False, blocked, room_id)
        self._restore_underlay(world, room)
        del world.rooms[room_id]
        self.invalidate_routes(world, set(self._building_tiles(room)))
        self._announce(world, f"Se derriba {room.name}", (room.x, room.y), room_id)
        return UrbanismResult(True, f"{room.name.capitalize()} retirado")

    def building_error(
        self,
        world: SimulationWorld,
        width: int,
        height: int,
        tile: Tile,
        ignore_room: str | None = None,
    ) -> str | None:
        preview = Room("preview", "", x=tile[0], y=tile[1], width=width, height=height, roofed=True)
        footprint = set(self._building_tiles(preview))
        if not footprint or not all(world.tile_map.in_bounds(point) for point in footprint):
            return "El edificio no cabe dentro del mapa"
        rooms = [room for room in world.rooms.values() if room.room_id != ignore_room]
        if any(footprint & set(self._building_tiles(room)) for room in rooms if room.roofed):
            return "Se solapa con otro edificio"
        occupied = {
            point
            for placed in world.interactables.values()
            for point in placed.footprint(world.definition_of(placed))
        }
        if footprint & occupied:
            return "Hay muebles u objetos en ese espacio"
        if footprint & self._marked_out(world):
            return SITE_IN_THE_WAY
        if any(not resident.away and resident.tile in footprint for resident in world.residents.values()):
            return "Hay un residente en ese espacio"
        # A building being moved stands on its own walls and floor; what counts is the ground below.
        ignored = world.rooms.get(ignore_room) if ignore_room is not None else None
        ground = self._ground_below(ignored) if ignored is not None else {}
        if any(
            ground.get(point, world.tile_map.terrain_at(point)) not in BUILDABLE_TERRAIN
            for point in footprint
        ):
            return "Solo se puede construir sobre terreno libre"
        walkable = self._walkable(world)
        if ignored is not None:
            # Lifted, it leaves behind the ground it stood on.
            walkable -= set(ground)
            walkable |= {point for point, terrain in ground.items() if world.registries.terrain[terrain].walkable}
        inside = {(x, y) for y in range(tile[1], tile[1] + height) for x in range(tile[0], tile[0] + width)}
        walkable = (walkable - footprint) | inside | {self._door_of(preview)}
        placed = list(world.interactables.values())
        return self._access_error(world, walkable - self._blocked(world, placed), placed, rooms, new_room=preview)

    def _construct(self, world: SimulationWorld, room: Room, floor: str) -> None:
        footprint = self._building_tiles(room)
        self.underlays[room.room_id] = {
            point: world.tile_map.terrain_at(point) for point in footprint
        }
        for x, y in footprint:
            border = x in (room.x - 1, room.x + room.width) or y in (
                room.y - 1,
                room.y + room.height,
            )
            world.tile_map.tiles[y][x] = "wall" if border else floor
        door = self._door_of(room)
        world.tile_map.tiles[door[1]][door[0]] = "door"
        world.rooms[room.room_id] = room

    @staticmethod
    def _door_of(room: Room) -> Tile:
        """Where a building put up here has its door: the middle of the wall at its front."""
        return (room.x + room.width // 2, room.y + room.height)

    # ----- keeping everything within reach -----

    @staticmethod
    def site_tiles(world: SimulationWorld, kind: str, what: str, tile: Tile) -> list[Tile]:
        """Every tile that an object or a building put at a tile would stand on, walls and all."""
        if kind == BUILDING_SITE:
            definition = world.registries.buildings[what]
            room = Room("site", "", x=tile[0], y=tile[1], width=definition.width, height=definition.height)
            return UrbanismSystem._building_tiles(room)
        return Interactable("site", what, tile[0], tile[1]).footprint(world.registries.interactables.get(what))

    @staticmethod
    def _marked_out(world: SimulationWorld) -> set[Tile]:
        """Every tile marked out for something that is being put up."""
        return {tile for site in world.sites.values() for tile in site.tiles}

    def within_reach(self, world: SimulationWorld) -> set[Tile]:
        """Every tile somebody could walk to from where people come in, as things stand:
        nowhere that is shut in, nor anything that stands in the way. Where nobody comes in
        anywhere, every tile that can be stood on."""
        open_ground = self._walkable(world) - self._blocked(world, list(world.interactables.values()))
        reached = self._reached(world, open_ground)
        return open_ground if reached is None else reached

    @staticmethod
    def _walkable(world: SimulationWorld) -> set[Tile]:
        """Every tile whose ground can be walked on, whatever stands on it. Not what a site has shut off."""
        terrain = world.registries.terrain
        shut = {tile for site in world.sites.values() if site.blocks for tile in site.tiles}
        return {
            (x, y)
            for y, row in enumerate(world.tile_map.tiles)
            for x, terrain_id in enumerate(row)
            if terrain_id in terrain and terrain[terrain_id].walkable and (x, y) not in shut
        }

    @staticmethod
    def _blocked(world: SimulationWorld, placed: list[Interactable]) -> set[Tile]:
        return {
            point
            for each in placed
            if world.definition_of(each).blocks
            for point in each.footprint(world.definition_of(each))
        }

    @staticmethod
    def _reached(world: SimulationWorld, open_ground: set[Tile]) -> set[Tile] | None:
        """Every tile that can be walked to from where people come in. None if they come in nowhere."""
        frontier = [tile for tile in world.entry_tiles() if tile in open_ground]
        if not frontier:
            return None
        reached = set(frontier)
        while frontier:
            x, y = frontier.pop()
            for dx, dy in NEIGHBOURS:
                step = (x + dx, y + dy)
                if step in open_ground and step not in reached:
                    reached.add(step)
                    frontier.append(step)
        return reached

    @staticmethod
    def _needs_access(world: SimulationWorld, definition: InteractableDefinition) -> bool:
        """Whether anyone ever has to get to an object of this kind: to use it, fill it or work at it."""
        return (
            definition.use is not None
            or definition.container
            or any(job.station == definition.kind for job in world.registries.jobs.values())
        )

    @staticmethod
    def _within_reach(placed: Interactable, definition: InteractableDefinition, reached: set[Tile]) -> bool:
        """Whether someone can get to where an object is used from: beside it, or on to it from beside."""
        footprint = set(placed.footprint(definition))
        if definition.use is not None and definition.use.position == "on":
            footprint = {(placed.x, placed.y)}
        return any((x + dx, y + dy) in reached for x, y in footprint for dx, dy in NEIGHBOURS)

    def _access_error(
        self,
        world: SimulationWorld,
        open_after: set[Tile],
        placed: list[Interactable],
        rooms: list[Room],
        candidate: Interactable | None = None,
        new_room: Room | None = None,
    ) -> str | None:
        """Why a change would leave something out of reach that is within reach now. None if it would not.

        `open_after` is the ground that could still be walked once the change is made, `placed` and
        `rooms` what would stand unchanged, and `candidate` or `new_room` what the change puts down.
        """
        before = self._reached(world, self._walkable(world) - self._blocked(world, list(world.interactables.values())))
        after = self._reached(world, open_after)
        if before is None or after is None:
            return None
        for each in placed:
            definition = world.definition_of(each)
            if (
                self._needs_access(world, definition)
                and self._within_reach(each, definition, before)
                and not self._within_reach(each, definition, after)
            ):
                return f"Dejaría sin paso: {definition.name}"
        for room in rooms:
            inside = {
                (x, y)
                for y in range(room.y, room.y + room.height)
                for x in range(room.x, room.x + room.width)
            }
            if room.roofed and inside & before and not inside & after:
                return f"Taparía la entrada: {room.name}"
        for site in world.sites.values():
            if self._beside(site, before) and not self._beside(site, after):
                return "Dejaría sin paso una obra"
        if candidate is not None:
            definition = world.definition_of(candidate)
            if self._needs_access(world, definition) and not self._within_reach(candidate, definition, after):
                return "No se podría llegar hasta ahí"
        if new_room is not None and self._door_of(new_room) not in after:
            return "La puerta quedaría tapada"
        # Ground that can be walked to now and could not be then: whoever stepped onto it, as off
        # the far side of a bed, would have no way back.
        taken = set(self._building_tiles(new_room)) if new_room is not None else set()
        if candidate is not None:
            taken |= set(candidate.footprint(world.definition_of(candidate)))
        if before - after - taken:
            return CUT_OFF
        return None

    @staticmethod
    def _beside(site: BuildSite, reached: set[Tile]) -> bool:
        """Whether someone can get next to a site, to bring things to it and to work on it."""
        return any((x + dx, y + dy) in reached for x, y in site.tiles for dx, dy in NEIGHBOURS)

    def _restore_underlay(self, world: SimulationWorld, room: Room) -> None:
        for point, terrain in self._ground_below(room).items():
            world.tile_map.tiles[point[1]][point[0]] = terrain
        self.underlays.pop(room.room_id, None)

    def _ground_below(self, room: Room) -> dict[Tile, str]:
        """The terrain a building hides. Buildings that came with the map are taken to stand on dirt."""
        underlay = self.underlays.get(room.room_id, {})
        return {point: underlay.get(point, "dirt") for point in self._building_tiles(room)}

    def _building_contents(self, world: SimulationWorld, room: Room) -> str | None:
        area = set(self._building_tiles(room))
        if any(
            set(placed.footprint(world.definition_of(placed))) & area
            for placed in world.interactables.values()
        ):
            return "Retira primero los muebles y objetos del edificio"
        if area & self._marked_out(world):
            return "Hay una obra dentro del edificio"
        if any(not resident.away and resident.tile in area for resident in world.residents.values()):
            return "No se puede editar mientras haya alguien dentro"
        return None

    def _object_busy_reason(self, world: SimulationWorld, object_id: str) -> str | None:
        for resident in world.residents.values():
            if resident.activity is not None and resident.activity.target_id == object_id:
                return "Ese objeto está siendo utilizado"
            if resident.post_id == object_id:
                return "Ese objeto es un puesto de trabajo asignado"
        return None

    @staticmethod
    def invalidate_routes(
        world: SimulationWorld,
        changed: set[Tile],
        target_ids: set[str] | None = None,
    ) -> None:
        """Stop plans made against geometry that no longer exists so they are replanned next tick."""
        targets = target_ids or set()
        for resident in world.residents.values():
            activity = resident.activity
            if activity is not None and (
                activity.target_id in targets or any(tile in changed for tile in activity.path)
            ):
                resident.activity = None
                resident.current_action = "idle"

    @staticmethod
    def _building_tiles(room: Room) -> list[Tile]:
        return [
            (x, y)
            for y in range(room.y - 1, room.y + room.height + 1)
            for x in range(room.x - 1, room.x + room.width + 1)
        ]

    @staticmethod
    def _floor_for(world: SimulationWorld, room: Room) -> str:
        definition = world.registries.buildings.get(room.blueprint_id or "")
        if definition is not None:
            return definition.floor
        counts: dict[str, int] = {}
        for y in range(room.y, room.y + room.height):
            for x in range(room.x, room.x + room.width):
                terrain = world.tile_map.terrain_at((x, y))
                counts[terrain] = counts.get(terrain, 0) + 1
        return max(counts, key=counts.get) if counts else "floor_wood"

    def _fresh_object_id(self, world: SimulationWorld, kind: str) -> str:
        while f"{kind}_{self.next_object}" in world.interactables:
            self.next_object += 1
        object_id = f"{kind}_{self.next_object}"
        self.next_object += 1
        return object_id

    def _fresh_building_id(self, world: SimulationWorld, blueprint_id: str) -> str:
        while f"{blueprint_id}_{self.next_building}" in world.rooms:
            self.next_building += 1
        room_id = f"{blueprint_id}_{self.next_building}"
        self.next_building += 1
        return room_id

    @staticmethod
    def _announce(world: SimulationWorld, text: str, tile: Tile, entity_id: str) -> None:
        world.emit_event(
            DomainEvent(
                "urbanism_changed",
                BUILDING_EVENT_IMPORTANCE,
                text,
                location_id=world.room_at(tile).room_id if world.room_at(tile) is not None else None,
                data={"entity_id": entity_id},
            ),
            at=tile,
        )
