"""Grid pathfinding. Domain-only: tiles in, tiles out."""

import heapq
from collections.abc import Callable, Sequence

from world.map import Tile

Point = tuple[float, float]

# The tiles beside one: what it takes to stand next to something. Fixed order, so that equally
# good choices are always resolved the same way.
NEIGHBOURS: tuple[Tile, ...] = ((0, -1), (1, 0), (0, 1), (-1, 0))
DIAGONALS: tuple[Tile, ...] = ((1, -1), (1, 1), (-1, 1), (-1, -1))
# What a step costs while a way is looked for, in whole numbers so that two ways of the same
# length never differ by a rounding. Seventeen twelfths is the diagonal of a tile, near enough.
STRAIGHT_COST = 12
DIAGONAL_COST = 17


def manhattan(a: Tile, b: Tile) -> int:
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def tile_of(point: Point) -> Tile:
    """The tile a point is on."""
    return (int((point[0] + 0.5) // 1), int((point[1] + 0.5) // 1))


def line(start: Tile, goal: Tile) -> list[Tile]:
    """The tiles stepped on going straight from `start` to `goal`, at whatever angle that is.

    `start` is left out and `goal` is the last. Each is beside the one before it, sideways or
    diagonally, and none is further than half a tile from the straight line itself.
    """
    dx, dy = goal[0] - start[0], goal[1] - start[1]
    steps = max(abs(dx), abs(dy))
    return [
        (start[0] + (2 * step * dx + steps) // (2 * steps), start[1] + (2 * step * dy + steps) // (2 * steps))
        for step in range(1, steps + 1)
    ]


def sight(start: Tile, goal: Tile, passable: Callable[[Tile], bool]) -> bool:
    """Whether the straight line from `start` to `goal` can be walked: nothing on it, and no corner cut."""
    x, y = start
    for tile in line(start, goal):
        if not passable(tile):
            return False
        if tile[0] != x and tile[1] != y and not (passable((tile[0], y)) and passable((x, tile[1]))):
            return False
        x, y = tile
    return True


def find_path(start: Tile, goal: Tile, passable: Callable[[Tile], bool]) -> list[Tile] | None:
    """Return a short way from `start` to `goal`, or None if there is none.

    It goes straight for as long as nothing is in the way, at any angle, and turns only to get
    round what is: every stretch of it is a `line`. Between two obstacles that touch at a corner
    there is no way through. The path excludes `start` and includes `goal`. `passable` decides
    every tile entered, including the goal, and must reject tiles outside the map.
    """
    if start == goal:
        return []
    known: dict[Tile, bool] = {}

    def free(tile: Tile) -> bool:
        if tile not in known:
            known[tile] = passable(tile)
        return known[tile]

    if sight(start, goal, free):
        return line(start, goal)
    came_from: dict[Tile, Tile] = {}
    cost = {start: 0}
    counter = 0
    frontier: list[tuple[int, int, Tile]] = [(_distance(start, goal), counter, start)]
    while frontier:
        _, _, current = heapq.heappop(frontier)
        if current == goal:
            way = [current]
            while way[-1] in came_from:
                way.append(came_from[way[-1]])
            return _straightened(start, way[-2::-1], free)
        for dx, dy in NEIGHBOURS + DIAGONALS:
            neighbour = (current[0] + dx, current[1] + dy)
            new_cost = cost[current] + (DIAGONAL_COST if dx and dy else STRAIGHT_COST)
            if new_cost >= cost.get(neighbour, new_cost + 1) or not free(neighbour):
                continue
            if dx and dy and not (free((neighbour[0], current[1])) and free((current[0], neighbour[1]))):
                continue
            cost[neighbour] = new_cost
            came_from[neighbour] = current
            counter += 1
            heapq.heappush(frontier, (new_cost + _distance(neighbour, goal), counter, neighbour))
    return None


def reach(start: Tile, steps: int, passable: Callable[[Tile], bool]) -> dict[Tile, int]:
    """The tiles that can be walked to from `start` in no more than so many steps, nearest first.

    Each comes with how many steps it takes. `start` is not among them, and need not be passable.
    """
    found = {start: 0}
    edge = [start]
    for count in range(1, steps + 1):
        further: list[Tile] = []
        for current in edge:
            for dx, dy in NEIGHBOURS + DIAGONALS:
                neighbour = (current[0] + dx, current[1] + dy)
                if neighbour in found or not passable(neighbour):
                    continue
                if dx and dy and not (passable((neighbour[0], current[1])) and passable((current[0], neighbour[1]))):
                    continue
                found[neighbour] = count
                further.append(neighbour)
        edge = further
    del found[start]
    return found


def straight_ahead(start: Tile, path: Sequence[Tile]) -> list[Point]:
    """Where a walk along `path` from `start` runs until it first turns: a point for each tile of that stretch.

    The points are on the straight line the stretch was laid along, so the last is the middle of
    its tile and the others may be up to half a tile off the middle of theirs. For a path with
    no stretch to it, it is its first tile.
    """
    reach = 0
    for count, tile in enumerate(path, start=1):
        if max(abs(tile[0] - start[0]), abs(tile[1] - start[1])) != count:
            # It has turned back on itself: nothing further on is straight ahead.
            break
        if line(start, tile) == list(path[:count]):
            reach = count
    if reach == 0:
        return [(float(tile[0]), float(tile[1])) for tile in path[:1]]
    dx, dy = path[reach - 1][0] - start[0], path[reach - 1][1] - start[1]
    return [(start[0] + step * dx / reach, start[1] + step * dy / reach) for step in range(1, reach + 1)]


def _distance(a: Tile, b: Tile) -> int:
    """What it costs to get from one tile to another with nothing in the way."""
    across, along = sorted((abs(a[0] - b[0]), abs(a[1] - b[1])))
    return STRAIGHT_COST * along + (DIAGONAL_COST - STRAIGHT_COST) * across


def _straightened(start: Tile, way: list[Tile], passable: Callable[[Tile], bool]) -> list[Tile]:
    """The same way with its corners cut wherever there is nothing to go round."""
    path: list[Tile] = []
    anchor, index = start, 0
    while index < len(way):
        reach = index
        if sight(anchor, way[-1], passable):
            reach = len(way) - 1
        else:
            while reach + 1 < len(way) and sight(anchor, way[reach + 1], passable):
                reach += 1
        path.extend(line(anchor, way[reach]))
        anchor, index = way[reach], reach + 1
    return path
