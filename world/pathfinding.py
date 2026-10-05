"""Grid pathfinding. Domain-only: tiles in, tiles out."""

import heapq
from collections.abc import Callable

from world.map import Tile

# Fixed order so that equally short paths are always resolved the same way.
NEIGHBOURS: tuple[Tile, ...] = ((0, -1), (1, 0), (0, 1), (-1, 0))


def manhattan(a: Tile, b: Tile) -> int:
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def find_path(start: Tile, goal: Tile, passable: Callable[[Tile], bool]) -> list[Tile] | None:
    """Return the shortest 4-way path from `start` to `goal`, or None if there is none.

    The path excludes `start` and includes `goal`. `passable` decides every tile entered,
    including the goal, and must reject tiles outside the map.
    """
    if start == goal:
        return []
    came_from: dict[Tile, Tile] = {}
    cost = {start: 0}
    counter = 0
    frontier: list[tuple[int, int, Tile]] = [(manhattan(start, goal), counter, start)]
    while frontier:
        _, _, current = heapq.heappop(frontier)
        if current == goal:
            path = [current]
            while path[-1] in came_from:
                path.append(came_from[path[-1]])
            return path[-2::-1]
        for dx, dy in NEIGHBOURS:
            neighbour = (current[0] + dx, current[1] + dy)
            new_cost = cost[current] + 1
            if new_cost >= cost.get(neighbour, new_cost + 1) or not passable(neighbour):
                continue
            cost[neighbour] = new_cost
            came_from[neighbour] = current
            counter += 1
            heapq.heappush(frontier, (new_cost + manhattan(neighbour, goal), counter, neighbour))
    return None
