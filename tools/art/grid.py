"""Turn text grids into palette-coloured surfaces."""

from collections.abc import Mapping, Sequence

import pygame

from graphics.palette import PALETTE

TRANSPARENT = "."

Legend = Mapping[str, str]
Rect = tuple[int, int, int, int]


def paint(rows: Sequence[str], legend: Legend) -> pygame.Surface:
    """Paint one pixel per character. `legend` maps characters to palette names."""
    width = len(rows[0])
    surface = pygame.Surface((width, len(rows)), pygame.SRCALPHA)
    for y, row in enumerate(rows):
        if len(row) != width:
            raise ValueError(f"Row {y} is {len(row)} wide, expected {width}: {row!r}")
        for x, char in enumerate(row):
            if char != TRANSPARENT:
                surface.set_at((x, y), PALETTE[legend[char]])
    return surface


def overlay(base: Sequence[str], patches: Mapping[int, str]) -> list[str]:
    """Return `base` with each patch row drawn over the row of that index.

    A transparent character in a patch keeps what is underneath.
    """
    rows = list(base)
    for index, patch in patches.items():
        if len(patch) != len(rows[index]):
            raise ValueError(f"Patch for row {index} is {len(patch)} wide: {patch!r}")
        rows[index] = "".join(
            under if over == TRANSPARENT else over for under, over in zip(rows[index], patch)
        )
    return rows


def mirror(rows: Sequence[str]) -> list[str]:
    return [row[::-1] for row in rows]


def fill(surface: pygame.Surface, color: str, rect: Rect) -> None:
    surface.fill(PALETTE[color], rect)


def dots(surface: pygame.Surface, color: str, points: Sequence[tuple[int, int]]) -> None:
    for point in points:
        surface.set_at(point, PALETTE[color])
