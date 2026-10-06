"""Finding a place to stand next to an object."""

from collections.abc import Callable
from typing import TYPE_CHECKING

from simulation.ai.crowd import spots_taken
from simulation.residents.resident import Resident
from world.interactable import Interactable
from world.map import Tile
from world.pathfinding import NEIGHBOURS, find_path, manhattan

if TYPE_CHECKING:
    from simulation.world import SimulationWorld


def adjacent_spots(world: "SimulationWorld", resident: Resident, placed: Interactable) -> list[Tile]:
    """Free tiles next to the object, nearest first. One that somebody else stands on or is heading to is not free."""
    footprint = placed.footprint(world.definition_of(placed))
    walkable = world.passable()
    spots = {
        (x + dx, y + dy)
        for x, y in footprint
        for dx, dy in NEIGHBOURS
        if (x + dx, y + dy) not in footprint and walkable((x + dx, y + dy))
    }
    return sorted(
        spots - spots_taken(world, resident),
        key=lambda spot: (manhattan(resident.tile, spot), spot[1], spot[0]),
    )


def path_beside(
    world: "SimulationWorld",
    resident: Resident,
    placed: Interactable,
    passable: Callable[[Tile], bool] | None = None,
) -> list[Tile] | None:
    """A short walk to a tile next to the object, or None if it cannot be reached.

    `passable` says where can be walked, for a walk that has to go round more than the map itself.
    """
    passable = passable or world.passable()
    for spot in adjacent_spots(world, resident, placed):
        path = find_path(resident.tile, spot, passable)
        if path is not None:
            return path
    return None
