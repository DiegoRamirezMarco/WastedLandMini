"""Residents in each other's way: nobody steps onto a tile that somebody else is on."""

from collections.abc import Callable, Collection
from functools import cached_property
from typing import TYPE_CHECKING

from simulation.residents.resident import Resident
from world.map import Tile
from world.pathfinding import reach, tile_of

if TYPE_CHECKING:
    from simulation.world import SimulationWorld

# How near somebody on the move has to be for a way round them to be looked for. Further off,
# they will be somewhere else before they are reached.
NEAR_TILES = 2
# How far from where they were to stand a place is looked for when somebody is already there.
FREE_TILE_REACH = 6


def walking(resident: Resident) -> bool:
    """Whether a resident is on their way somewhere, as against standing where they are."""
    return resident.activity is not None and bool(resident.activity.path)


def spots_taken(world: "SimulationWorld", resident: Resident | None = None) -> set[Tile]:
    """Where the others stand or are on their way to stand: no place for a resident to plan to end up."""
    return {other.destination for other in world.residents.values() if other is not resident and not other.away}


def free_tile(world: "SimulationWorld", near: Tile, resident: Resident | None = None) -> Tile:
    """The tile nearest to one that nobody stands on or is heading for: the tile itself, if nobody is.

    For putting somebody on the map who was not on it. With nowhere free within reach it is the
    tile all the same.
    """
    taken = spots_taken(world, resident)
    if near not in taken:
        return near
    return next((tile for tile in reach(near, FREE_TILE_REACH, world.passable()) if tile not in taken), near)


class Crowd:
    """Everybody else on the map, as one resident finds them in the way during one minute.

    Whoever is out of the settlement is not in it, nor is whoever lies on something that nobody
    else walks onto.
    """

    def __init__(self, world: "SimulationWorld", resident: Resident) -> None:
        self.world = world
        self.resident = resident
        self._present = [other for other in world.residents.values() if other is not resident and not other.away]
        # Every tile anybody else is on or has walked over this minute, whatever the tile is.
        # Most steps are onto none of them, and then there is no more to find out.
        self._walked = {other.tile for other in self._present}
        for other in self._present:
            if len(other.trail) > 1:
                self._walked.update(map(tile_of, other.trail))

    @cached_property
    def open(self) -> Callable[[Tile], bool]:
        """Where can be walked with nobody about."""
        return self.world.passable()

    @cached_property
    def others(self) -> list[Resident]:
        """Whoever else is standing or walking on open ground."""
        return [other for other in self._present if self.open(other.tile)]

    @cached_property
    def at(self) -> dict[Tile, Resident]:
        """Who stands where. Of two on one tile, as an older save may have them, the first."""
        standing: dict[Tile, Resident] = {}
        for other in self.others:
            standing.setdefault(other.tile, other)
        return standing

    @cached_property
    def trodden(self) -> set[Tile]:
        """Every tile of open ground that somebody else is on or has walked over this minute."""
        return {tile for tile in self._walked if self.open(tile)}

    def free(self, origin: Tile, step: Tile) -> bool:
        """Whether a step can be taken this minute without walking into anybody, or between two people."""
        return self._clear(origin, step, self._walked) or self._clear(origin, step, self.trodden)

    @staticmethod
    def _clear(origin: Tile, step: Tile, tiles: set[Tile]) -> bool:
        if step in tiles:
            return False
        if step[0] != origin[0] and step[1] != origin[1]:
            return (step[0], origin[1]) not in tiles or (origin[0], step[1]) not in tiles
        return True

    def passable(self, also: Collection[Tile] = ()) -> Callable[[Tile], bool]:
        """A walkability test that counts people as in the way: for finding a way round them.

        Whoever stands still is in the way wherever they are, and whoever is walking only if
        they are near. Tiles in `also` count as walkable even if an object stands on them.
        """
        ground = self.world.passable(also) if also else self.open
        here = self.resident.tile
        blocked = {
            other.tile
            for other in self.others
            if not walking(other)
            or max(abs(other.x - here[0]), abs(other.y - here[1])) <= NEAR_TILES
        }
        return lambda tile: tile not in blocked and ground(tile)
