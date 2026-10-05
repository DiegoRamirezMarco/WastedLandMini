"""Objects of the settlement's premises: the cantina, the garden, the workshop and the gate."""

import random

import pygame

from graphics.palette import PALETTE
from tools.art.grid import dots, fill, paint
from tools.art.objects import BED


def _blank(width: int, height: int) -> pygame.Surface:
    return pygame.Surface((width, height), pygame.SRCALPHA)


def _box(surface: pygame.Surface, rect: tuple[int, int, int, int], color: str) -> None:
    """A filled rectangle with a one-pixel ink outline."""
    x, y, width, height = rect
    fill(surface, "ink", (x - 1, y - 1, width + 2, height + 2))
    fill(surface, color, rect)


def _cooking_pot() -> pygame.Surface:
    surface = _blank(16, 32)
    # Stove with a fire in its mouth.
    _box(surface, (2, 17, 12, 14), "iron")
    fill(surface, "stone", (1, 15, 14, 2))
    fill(surface, "shadow", (4, 21, 8, 7))
    fill(surface, "ember", (5, 23, 6, 4))
    fill(surface, "lamp", (6, 24, 4, 2))
    # Pot of stew on top.
    _box(surface, (4, 8, 8, 7), "stone")
    fill(surface, "dust", (3, 7, 10, 1))
    fill(surface, "sand", (5, 8, 6, 2))
    dots(surface, "ember", [(6, 8), (9, 9)])
    dots(surface, "ink", [(2, 10), (13, 10)])
    dots(surface, "dust", [(6, 4), (7, 2), (9, 3), (10, 5), (8, 0)])
    return surface


def _bar() -> pygame.Surface:
    surface = _blank(48, 16)
    _box(surface, (1, 5, 46, 10), "rust")
    fill(surface, "sand", (1, 5, 46, 2))
    fill(surface, "copper", (1, 7, 46, 1))
    fill(surface, "rust_dark", (1, 14, 46, 1))
    for x in range(8, 46, 8):
        fill(surface, "rust_dark", (x, 8, 1, 6))
    for x, color in ((6, "lichen"), (12, "mist"), (31, "ember"), (40, "lamp")):
        fill(surface, "ink", (x - 1, 0, 4, 5))
        fill(surface, color, (x, 1, 2, 4))
        dots(surface, "paper", [(x, 2)])
    fill(surface, "ink", (19, 1, 5, 4))
    fill(surface, "bone", (20, 2, 3, 3))
    return surface


def _crop_bed() -> pygame.Surface:
    surface = _blank(16, 16)
    _box(surface, (2, 8, 12, 6), "rust_dark")
    dots(surface, "earth_dark", [(3, 9), (6, 11), (9, 9), (12, 12), (5, 13), (10, 12)])
    for x in (4, 8, 12):
        fill(surface, "moss", (x, 5, 1, 4))
        fill(surface, "olive", (x - 1, 3, 3, 3))
        dots(surface, "lichen", [(x, 2), (x - 1, 3)])
    dots(surface, "ember", [(5, 6), (11, 5)])
    return surface


def _guard_post() -> pygame.Surface:
    surface = _blank(16, 32)
    # A sentry box: plank walls, an opening to look out of, a tin roof and a flag.
    _box(surface, (2, 7, 12, 24), "copper")
    for x in (5, 9):
        fill(surface, "rust", (x, 17, 1, 14))
    fill(surface, "shadow", (4, 9, 8, 8))
    fill(surface, "ink", (3, 17, 10, 1))
    _box(surface, (1, 4, 14, 3), "stone")
    fill(surface, "dust", (1, 4, 14, 1))
    fill(surface, "ink", (13, 0, 1, 4))
    fill(surface, "blood", (9, 0, 4, 2))
    return surface


def _workbench() -> pygame.Surface:
    surface = _blank(32, 16)
    for x in (3, 27):
        _box(surface, (x, 8, 2, 7), "iron")
    fill(surface, "shadow", (5, 11, 22, 2))
    _box(surface, (1, 4, 30, 4), "stone")
    fill(surface, "dust", (1, 4, 30, 1))
    fill(surface, "rust", (8, 2, 5, 2))
    fill(surface, "rust_dark", (10, 0, 1, 2))
    fill(surface, "dust", (17, 2, 6, 1))
    fill(surface, "iron", (25, 1, 4, 3))
    return surface


def _barrel() -> pygame.Surface:
    """Three frames of a barrel with a fire burning in it."""
    flames = (
        [(6, 3), (7, 2), (8, 3), (9, 4)],
        [(7, 3), (8, 2), (9, 3), (6, 4)],
        [(6, 4), (7, 3), (8, 1), (9, 3)],
    )
    surface = _blank(48, 16)
    for frame, tips in enumerate(flames):
        left = frame * 16
        _box(surface, (left + 4, 7, 8, 8), "steel")
        for y in (9, 13):
            fill(surface, "deep", (left + 4, y, 8, 1))
        fill(surface, "ember", (left + 5, 4, 6, 3))
        fill(surface, "lamp", (left + 6, 5, 4, 2))
        dots(surface, "ember", [(left + x, y) for x, y in tips])
        dots(surface, "glow", [(left + 7, 5), (left + 8, 5)])
    return surface


def _scrap_pile() -> pygame.Surface:
    surface = _blank(32, 16)
    rng = random.Random(41)
    colors = ("iron", "stone", "rust", "shadow", "copper", "iron", "rust_dark")
    for x in range(1, 31):
        # A heap: tallest in the middle, ragged on top.
        height = max(2, 12 - abs(x - 15) * 2 // 3 + rng.randint(-2, 1))
        top = 15 - height
        dots(surface, "ink", [(x, top - 1)])
        for y in range(top, 15):
            dots(surface, rng.choice(colors), [(x, y)])
    fill(surface, "ink", (0, 15, 32, 1))
    dots(surface, "dust", [(9, 9), (16, 5), (22, 10)])
    return surface


def _water_tank() -> pygame.Surface:
    surface = _blank(32, 32)
    pygame.draw.ellipse(surface, PALETTE["ink"], (1, 1, 30, 30))
    pygame.draw.ellipse(surface, PALETTE["steel"], (2, 2, 28, 28))
    pygame.draw.ellipse(surface, PALETTE["deep"], (4, 4, 24, 24))
    pygame.draw.ellipse(surface, PALETTE["teal"], (5, 5, 22, 22))
    dots(surface, "mist", [(10, 10), (11, 10), (12, 11), (19, 18), (20, 18), (14, 21)])
    fill(surface, "ink", (13, 25, 6, 7))
    fill(surface, "rust", (14, 25, 4, 6))
    dots(surface, "copper", [(15, 26), (15, 28), (15, 30)])
    return surface


def _clinic_bed() -> pygame.Surface:
    # The ordinary bed in hospital colours: a steel frame, white sheets and a red cross on the blanket.
    legend = {
        "o": "ink", "f": "stone", "k": "iron", "w": "bone", "p": "paper", "d": "dust",
        "b": "paper", "B": "bone", "D": "dust",
    }
    surface = paint(BED, legend)
    fill(surface, "blood", (7, 17, 2, 6))
    fill(surface, "blood", (5, 19, 6, 2))
    return surface


def _medicine_cabinet() -> pygame.Surface:
    surface = _blank(16, 32)
    for x in (3, 11):
        _box(surface, (x, 27, 2, 4), "iron")
    _box(surface, (2, 5, 12, 22), "bone")
    fill(surface, "paper", (2, 5, 12, 1))
    fill(surface, "dust", (8, 6, 1, 21))
    fill(surface, "blood", (7, 11, 2, 10))
    fill(surface, "blood", (3, 15, 10, 2))
    dots(surface, "iron", [(6, 23), (10, 23)])
    return surface


def _grave() -> pygame.Surface:
    surface = _blank(16, 16)
    # A mound of turned earth and a cross made of scrap.
    _box(surface, (3, 11, 10, 4), "earth_dark")
    dots(surface, "earth", [(5, 12), (9, 13), (11, 12)])
    _box(surface, (7, 2, 2, 10), "stone")
    _box(surface, (4, 5, 8, 2), "stone")
    fill(surface, "stone", (7, 5, 2, 2))
    dots(surface, "rust", [(5, 6), (10, 5), (8, 9)])
    return surface


def build() -> dict[str, pygame.Surface]:
    painters = {
        "cooking_pot": _cooking_pot,
        "bar": _bar,
        "crop_bed": _crop_bed,
        "guard_post": _guard_post,
        "workbench": _workbench,
        "barrel": _barrel,
        "scrap_pile": _scrap_pile,
        "water_tank": _water_tank,
        "clinic_bed": _clinic_bed,
        "medicine_cabinet": _medicine_cabinet,
        "grave": _grave,
    }
    return {f"sprites/objects/{kind}.png": painter() for kind, painter in painters.items()}
