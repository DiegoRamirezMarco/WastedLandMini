"""Things to train at (S57): weights, a chess table, a target, a skipping rope, a dummy and a log."""

import pygame

from graphics.palette import PALETTE
from tools.art.grid import dots, fill


def _blank(width: int, height: int) -> pygame.Surface:
    return pygame.Surface((width, height), pygame.SRCALPHA)


def _box(surface: pygame.Surface, rect: tuple[int, int, int, int], color: str) -> None:
    """A filled rectangle with a one-pixel ink outline."""
    x, y, width, height = rect
    fill(surface, "ink", (x - 1, y - 1, width + 2, height + 2))
    fill(surface, color, rect)


def _disc(surface: pygame.Surface, centre: tuple[int, int], radius: int, color: str) -> None:
    """A filled circle with a one-pixel ink outline."""
    pygame.draw.circle(surface, PALETTE["ink"], centre, radius + 1)
    pygame.draw.circle(surface, PALETTE[color], centre, radius)


def _weights() -> pygame.Surface:
    """A bar with discs at each end on a low rack, and a dumbbell on the ground."""
    surface = _blank(16, 32)
    for x in (4, 10):
        _box(surface, (x, 20, 2, 9), "iron")
    fill(surface, "ink", (0, 17, 16, 3))
    fill(surface, "stone", (1, 18, 14, 1))
    for x in (1, 13):
        _box(surface, (x, 13, 2, 11), "iron")
    for x in (3, 11):
        _box(surface, (x, 15, 2, 7), "ember")
    fill(surface, "ink", (5, 28, 6, 3))
    fill(surface, "stone", (6, 29, 4, 1))
    for x in (4, 10):
        _box(surface, (x, 27, 2, 4), "iron")
    return surface


def _chess_table() -> pygame.Surface:
    """A small table with a board on it and a few pieces."""
    surface = _blank(16, 32)
    for x in (2, 12):
        _box(surface, (x, 24, 2, 6), "rust_dark")
    _box(surface, (1, 17, 14, 6), "rust")
    fill(surface, "copper", (1, 17, 14, 1))
    for row in range(3):
        for column in range(5):
            color = "paper" if (row + column) % 2 else "shadow"
            fill(surface, color, (3 + column * 2, 18 + row, 2, 1))
    for x, color in ((4, "paper"), (9, "ink"), (12, "paper")):
        fill(surface, "ink", (x - 1, 13, 3, 5))
        fill(surface, color if color != "ink" else "iron", (x, 14, 1, 3))
    return surface


def _target() -> pygame.Surface:
    """A round target on three legs, with an arrow in it."""
    surface = _blank(16, 32)
    for step in range(9):
        dots(surface, "ink", [(6 - step // 2, 22 + step), (10 + step // 2, 22 + step)])
        dots(surface, "rust", [(7 - step // 2, 22 + step), (9 + step // 2, 22 + step)])
    fill(surface, "ink", (7, 20, 3, 10))
    fill(surface, "rust_dark", (8, 20, 1, 9))
    _disc(surface, (8, 13), 6, "paper")
    pygame.draw.circle(surface, PALETTE["ember"], (8, 13), 5)
    pygame.draw.circle(surface, PALETTE["paper"], (8, 13), 3)
    pygame.draw.circle(surface, PALETTE["ember"], (8, 13), 1)
    dots(surface, "lamp", [(8, 13)])
    dots(surface, "ink", [(10, 11), (11, 10), (12, 9), (13, 8)])
    dots(surface, "lichen", [(14, 7), (13, 7), (14, 8)])
    return surface


def _skipping_rope() -> pygame.Surface:
    """A post with a rope hung on it by its middle, over a mat."""
    surface = _blank(16, 32)
    _box(surface, (1, 27, 14, 3), "teal")
    fill(surface, "mist", (2, 27, 12, 1))
    _box(surface, (7, 7, 2, 21), "rust")
    dots(surface, "ink", [(9, 9), (10, 9), (11, 9)])
    left = [(10, 10), (9, 12), (8, 14), (7, 16), (6, 18), (6, 20), (6, 22)]
    right = [(11, 10), (12, 12), (13, 14), (13, 16), (12, 18), (12, 20), (12, 22)]
    for point in left + right:
        dots(surface, "ink", [(point[0] - 1, point[1]), (point[0] + 1, point[1])])
    dots(surface, "sand", left + right)
    for x in (5, 11):
        _box(surface, (x, 23, 2, 4), "ember")
    return surface


def _dummy() -> pygame.Surface:
    """A sack of straw on a pole with arms of stick and a face painted on it."""
    surface = _blank(16, 32)
    _box(surface, (7, 22, 2, 8), "rust")
    fill(surface, "ink", (4, 30, 8, 2))
    fill(surface, "rust_dark", (5, 30, 6, 1))
    fill(surface, "ink", (0, 15, 16, 3))
    fill(surface, "sand", (1, 16, 14, 1))
    _box(surface, (4, 14, 8, 9), "plum")
    dots(surface, "lamp", [(8, 16), (8, 19)])
    _disc(surface, (8, 8), 4, "bone")
    dots(surface, "ink", [(6, 7), (10, 7)])
    dots(surface, "rose", [(5, 9), (11, 9)])
    dots(surface, "ember", [(6, 10), (7, 11), (8, 11), (9, 11), (10, 10)])
    dots(surface, "lamp", [(6, 2), (8, 1), (10, 2)])
    return surface


def _training_log() -> pygame.Surface:
    """A thick log stood on end with a rag tied round it where heads meet it."""
    surface = _blank(16, 32)
    _box(surface, (4, 9, 8, 21), "rust")
    dots(surface, "rust_dark", [(6, 13), (6, 21), (6, 24), (9, 20), (9, 23), (10, 27), (7, 27)])
    pygame.draw.ellipse(surface, PALETTE["ink"], (3, 6, 10, 6))
    pygame.draw.ellipse(surface, PALETTE["sand"], (4, 7, 8, 4))
    dots(surface, "copper", [(7, 9), (8, 9)])
    fill(surface, "ink", (3, 14, 10, 5))
    fill(surface, "ember", (4, 15, 8, 3))
    dots(surface, "blood_dark", [(7, 16), (8, 16)])
    dots(surface, "ember", [(13, 15), (14, 14), (14, 17)])
    dots(surface, "lamp", [(1, 11), (0, 11), (2, 11), (1, 10), (1, 12), (14, 9), (13, 9), (15, 9), (14, 8), (14, 10)])
    return surface


def build() -> dict[str, pygame.Surface]:
    painters = {
        "weights": _weights,
        "chess_table": _chess_table,
        "target": _target,
        "skipping_rope": _skipping_rope,
        "dummy": _dummy,
        "training_log": _training_log,
    }
    return {f"sprites/objects/{kind}.png": painter() for kind, painter in painters.items()}
