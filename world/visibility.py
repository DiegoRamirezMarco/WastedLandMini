"""Line of sight on the tile grid. Domain-only: tiles in, booleans out."""

from collections.abc import Callable

from world.map import Tile


def line_tiles(start: Tile, end: Tile) -> list[Tile]:
    """Tiles on the straight line from `start` to `end`, both included (Bresenham)."""
    (x, y), (end_x, end_y) = start, end
    dx, dy = abs(end_x - x), -abs(end_y - y)
    step_x = 1 if x < end_x else -1
    step_y = 1 if y < end_y else -1
    error = dx + dy
    tiles = [(x, y)]
    while (x, y) != (end_x, end_y):
        doubled = 2 * error
        if doubled >= dy:
            error += dy
            x += step_x
        if doubled <= dx:
            error += dx
            y += step_y
        tiles.append((x, y))
    return tiles


def line_of_sight(start: Tile, end: Tile, opaque: Callable[[Tile], bool]) -> bool:
    """True if nothing opaque lies strictly between the two tiles."""
    return not any(opaque(tile) for tile in line_tiles(start, end)[1:-1])


def within_range(a: Tile, b: Tile, distance: int) -> bool:
    return max(abs(a[0] - b[0]), abs(a[1] - b[1])) <= distance
