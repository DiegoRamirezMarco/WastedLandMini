"""Finding a place to stand next to an object."""

from typing import TYPE_CHECKING

from simulation.residents.resident import Resident
from world.interactable import Interactable
from world.map import Tile
from world.pathfinding import NEIGHBOURS, find_path, manhattan

if TYPE_CHECKING:
    from simulation.world import SimulationWorld


def adjacent_spots(world: "SimulationWorld", resident: Resident, placed: Interactable) -> list[Tile]:
    """Free tiles next to the object, nearest first, avoiding ones others are heading to."""
    footprint = placed.footprint(world.definition_of(placed))
    walkable = world.passable()
    spots = {
        (x + dx, y + dy)
        for x, y in footprint
        for dx, dy in NEIGHBOURS
        if (x + dx, y + dy) not in footprint and walkable((x + dx, y + dy))
    }
    taken = {other.destination for other in world.residents.values() if other is not resident}
    return sorted(
        spots,
        key=lambda spot: (spot in taken, manhattan(resident.tile, spot), spot[1], spot[0]),
    )


def path_beside(world: "SimulationWorld", resident: Resident, placed: Interactable) -> list[Tile] | None:
    """Shortest walk to a tile next to the object, or None if it cannot be reached."""
    passable = world.passable()
    for spot in adjacent_spots(world, resident, placed):
        path = find_path(resident.tile, spot, passable)
        if path is not None:
            return path
    return None
