"""Settlement tilesets: ground, floors, shack walls and the perimeter fence, and the roofs."""

import random
from collections.abc import Callable
from functools import partial

import pygame

from graphics.tileset import (
    ROOF_CELLS,
    ROOF_SHEET,
    ROOF_SHEET_SIZE,
    SETTLEMENT_CELLS,
    SETTLEMENT_SHEET,
    SETTLEMENT_SHEET_SIZE,
    Cell,
)
from settings import TILE_SIZE
from tools.art.grid import dots, fill, overlay, paint

T = TILE_SIZE


def _blank(color: str | None = None) -> pygame.Surface:
    surface = pygame.Surface((T, T), pygame.SRCALPHA)
    if color is not None:
        fill(surface, color, (0, 0, T, T))
    return surface


def _scatter(count: int, seed: int, margin: int = 0) -> list[tuple[int, int]]:
    rng = random.Random(seed)
    return [(rng.randrange(margin, T - margin), rng.randrange(margin, T - margin)) for _ in range(count)]


def _dirt() -> pygame.Surface:
    surface = _blank("earth")
    dots(surface, "earth_dark", _scatter(9, seed=11))
    return surface


def _dirt_pebbles() -> pygame.Surface:
    surface = _dirt()
    for x, y in ((3, 4), (10, 9), (6, 12)):
        fill(surface, "dust", (x, y, 2, 1))
        fill(surface, "earth_dark", (x, y + 1, 2, 1))
    return surface


def _grass(blades: int, seed: int, tips: bool) -> pygame.Surface:
    surface = _dirt()
    for x, y in _scatter(blades, seed=seed, margin=1):
        dots(surface, "moss", [(x, y + 1)])
        dots(surface, "olive", [(x, y)])
        if tips and (x + y) % 3 == 0:
            dots(surface, "lichen", [(x, y - 1)])
    return surface


def _gate() -> pygame.Surface:
    surface = _dirt()
    for x in (4, 10):
        for y in range(0, T, 4):
            fill(surface, "earth_dark", (x, y, 2, 3))
    return surface


def _soil() -> pygame.Surface:
    surface = _blank("earth_dark")
    for y in (2, 6, 10, 14):
        fill(surface, "rust_dark", (0, y, T, 2))
        dots(surface, "earth", [(x, y - 1) for x in range((y * 3) % 5, T, 5)])
    return surface


def _floor_wood() -> pygame.Surface:
    surface = _blank("rust")
    for y, joint, shine in ((3, 10, 2), (7, 4, 9), (11, 13, 5), (15, 7, 12)):
        fill(surface, "rust_dark", (0, y, T, 1))
        fill(surface, "rust_dark", (joint, y - 3, 1, 3))
        fill(surface, "copper", (shine, y - 3, 3, 1))
    return surface


def _floor_concrete() -> pygame.Surface:
    surface = _blank("iron")
    dots(surface, "shadow", _scatter(7, seed=1))
    dots(surface, "stone", _scatter(4, seed=2))
    fill(surface, "shadow", (0, T - 1, T, 1))
    fill(surface, "shadow", (T - 1, 0, 1, T))
    return surface


def _floor_cracked() -> pygame.Surface:
    surface = _floor_concrete()
    crack = [(4, 2), (5, 3), (5, 4), (6, 5), (7, 5), (8, 6), (8, 7), (9, 8), (10, 9), (10, 10), (11, 11)]
    dots(surface, "shadow", crack)
    dots(surface, "ink", [(5, 4), (8, 6), (10, 9)])
    dots(surface, "shadow", [(9, 5), (10, 4), (7, 8), (6, 9)])
    return surface


def _floor_stained() -> pygame.Surface:
    surface = _floor_concrete()
    fill(surface, "moss_dark", (5, 6, 6, 4))
    fill(surface, "moss_dark", (6, 5, 4, 6))
    dots(surface, "moss", [(7, 7), (8, 8), (9, 7)])
    dots(surface, "moss_dark", [(4, 8), (11, 7), (8, 11)])
    return surface


def _wall_top() -> pygame.Surface:
    surface = _blank("rust_dark")
    dots(surface, "ink", _scatter(8, seed=3))
    return surface


def _wall_face() -> pygame.Surface:
    surface = _blank("copper")
    fill(surface, "sand", (0, 0, T, 1))
    for x in (3, 7, 11, 15):
        fill(surface, "rust", (x, 1, 1, 12))
    dots(surface, "rust_dark", [(1, 2), (5, 2), (9, 2), (13, 2), (1, 11), (5, 11), (9, 11), (13, 11)])
    fill(surface, "rust", (0, 13, T, 2))
    fill(surface, "rust_dark", (0, 15, T, 1))
    return surface


def _wall_face_window() -> pygame.Surface:
    surface = _wall_face()
    fill(surface, "rust_dark", (4, 3, 8, 7))
    fill(surface, "deep", (5, 4, 6, 5))
    dots(surface, "mist", [(6, 5), (7, 5), (6, 6)])
    return surface


def _wall_face_sign() -> pygame.Surface:
    surface = _wall_face()
    fill(surface, "ink", (4, 3, 8, 8))
    fill(surface, "lamp", (5, 4, 6, 6))
    for offset in range(6):
        dots(surface, "ink", [(5 + offset, 9 - offset)])
        if offset >= 3:
            dots(surface, "ink", [(5 + offset - 3, 9 - offset), (5 + offset, 12 - offset)])
    return surface


def _door() -> pygame.Surface:
    surface = _wall_face()
    fill(surface, "ink", (1, 0, 14, 16))
    fill(surface, "steel", (2, 1, 12, 15))
    fill(surface, "teal", (2, 1, 12, 1))
    fill(surface, "deep", (2, 8, 12, 1))
    fill(surface, "ink", (5, 3, 6, 3))
    fill(surface, "mist", (6, 4, 4, 1))
    fill(surface, "lamp", (11, 10, 2, 2))
    fill(surface, "deep", (2, 15, 12, 1))
    return surface


def _fence_top() -> pygame.Surface:
    surface = _blank()
    fill(surface, "iron", (5, 0, 6, T))
    fill(surface, "stone", (5, 0, 1, T))
    fill(surface, "shadow", (10, 0, 1, T))
    for y in range(3, T, 4):
        fill(surface, "shadow", (6, y, 4, 1))
    return surface


def _fence_face() -> pygame.Surface:
    surface = _blank("stone")
    for x in range(2, T, 4):
        fill(surface, "iron", (x, 1, 2, 14))
    fill(surface, "dust", (0, 0, T, 1))
    fill(surface, "shadow", (0, 15, T, 1))
    dots(surface, "shadow", [(x, 3) for x in range(0, T, 4)])
    return surface


def _fence_face_rusty() -> pygame.Surface:
    surface = _fence_face()
    fill(surface, "rust", (3, 6, 4, 5))
    fill(surface, "rust", (10, 9, 3, 4))
    dots(surface, "copper", [(4, 7), (5, 8), (11, 10)])
    dots(surface, "rust_dark", [(3, 10), (6, 6), (12, 12), (8, 4)])
    return surface


PAINTERS: dict[str, Callable[[], pygame.Surface]] = {
    "dirt": _dirt,
    "dirt_pebbles": _dirt_pebbles,
    "grass": lambda: _grass(blades=7, seed=21, tips=False),
    "grass_tuft": lambda: _grass(blades=16, seed=22, tips=True),
    "gate": _gate,
    "soil": _soil,
    "floor_wood": _floor_wood,
    "floor_concrete": _floor_concrete,
    "floor_cracked": _floor_cracked,
    "floor_stained": _floor_stained,
    "wall_top": _wall_top,
    "wall_face": _wall_face,
    "wall_face_window": _wall_face_window,
    "wall_face_sign": _wall_face_sign,
    "door": _door,
    "fence_top": _fence_top,
    "fence_face": _fence_face,
    "fence_face_rusty": _fence_face_rusty,
}


ROOF_LEGEND = {
    "s": "stone", "d": "dust", "i": "iron", "k": "shadow", "r": "rust", "c": "copper", "t": "steel", "m": "teal",
}

# Corrugated tin seen from above, at half size: each character is a block of 2×2 pixels.
ROOF_TIN = [
    "sdsisdsi",
    "sdsisdsi",
    "sdsisdsi",
    "sdsisdsi",
    "sdsisdsi",
    "sdsisdsi",
    "sdsisdsi",
    "iiiiiiii",
]

ROOFS = {
    "roof": ROOF_TIN,
    "roof_rusty": overlay(
        ROOF_TIN, {1: "....rr..", 2: "...rcrr.", 3: "....rr..", 5: ".r......", 6: "rr......"}
    ),
    # A sheet of something else nailed over a hole.
    "roof_patched": overlay(ROOF_TIN, {2: ".kkkkk..", 3: ".tmttk..", 4: ".tmttk..", 5: ".tmttk.."}),
    # The lower edge, and the shadow it throws on the wall under it.
    "roof_eave": overlay(ROOF_TIN, {6: "dddddddd", 7: "kkkkkkkk"}),
}


def _roof(name: str) -> pygame.Surface:
    return pygame.transform.scale(paint(ROOFS[name], ROOF_LEGEND), (T, T))


ROOF_PAINTERS: dict[str, Callable[[], pygame.Surface]] = {name: partial(_roof, name) for name in ROOFS}


def _sheet(
    painters: dict[str, Callable[[], pygame.Surface]], cells: dict[str, Cell], size: tuple[int, int]
) -> pygame.Surface:
    if painters.keys() != cells.keys():
        mismatched = sorted(painters.keys() ^ cells.keys())
        raise ValueError(f"Tile painters and sheet cells name different tiles: {mismatched}")
    sheet = pygame.Surface(size, pygame.SRCALPHA)
    for name, (column, row) in cells.items():
        sheet.blit(painters[name](), (column * T, row * T))
    return sheet


def build() -> dict[str, pygame.Surface]:
    return {
        SETTLEMENT_SHEET: _sheet(PAINTERS, SETTLEMENT_CELLS, SETTLEMENT_SHEET_SIZE),
        ROOF_SHEET: _sheet(ROOF_PAINTERS, ROOF_CELLS, ROOF_SHEET_SIZE),
    }
