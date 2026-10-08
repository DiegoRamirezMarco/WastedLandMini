"""What is seen over a thing that stands idle (P60): broken down, switched off, or on with no
current for it. And a small stone at its foot in the colour of how rare it is.

It reads the simulation and changes nothing.
"""

import pygame

from graphics.palette import PALETTE
from simulation.world import SimulationWorld
from ui.bubble import MARK_SIZE, MARK_TAIL, draw_mark
from ui.power_board import STARVED, SWITCHED_OFF, power_state

BROKEN, OFF, NO_CURRENT = "broken", "off", "no_current"
GLYPH_SIZE = (8, 8)
GEM = 5
# What is drawn in the bubble of each mark, a pixel to a letter.
_BOLT = (
    "....##..",
    "...##...",
    "..##....",
    ".#####..",
    "...##...",
    "..##....",
    ".##.....",
    ".#......",
)
_BANG = (
    "...##...",
    "...##...",
    "...##...",
    "...##...",
    "...##...",
    "........",
    "...##...",
    "...##...",
)
_SLASH = tuple("".join("#" if column == 7 - row else "." for column in range(8)) for row in range(8))
_glyphs: dict[str, pygame.Surface] = {}


def _stamp(rows: tuple[str, ...], color: str, onto: pygame.Surface | None = None) -> pygame.Surface:
    picture = onto if onto is not None else pygame.Surface(GLYPH_SIZE, pygame.SRCALPHA)
    for y, row in enumerate(rows):
        for x, letter in enumerate(row):
            if letter == "#":
                picture.set_at((x, y), PALETTE[color])
    return picture


def glyph(mark: str) -> pygame.Surface:
    """The small picture of a mark, made once."""
    if mark not in _glyphs:
        if mark == BROKEN:
            _glyphs[mark] = _stamp(_BANG, "ember")
        elif mark == OFF:
            _glyphs[mark] = _stamp(_BOLT, "stone")
        else:
            _glyphs[mark] = _stamp(_SLASH, "ember", _stamp(_BOLT, "ochre"))
    return _glyphs[mark]


def marks_of(world: SimulationWorld) -> dict[str, str]:
    """The mark over each thing that stands idle, by its ID: what has broken down, what is
    switched off, and what is on with no current for it."""
    enough = world.power.enough(world)
    marks: dict[str, str] = {}
    for object_id, placed in world.interactables.items():
        if placed.condition <= 0.0:
            marks[object_id] = BROKEN
            continue
        state = power_state(world, object_id, enough)
        if state == SWITCHED_OFF:
            marks[object_id] = OFF
        elif state == STARVED:
            marks[object_id] = NO_CURRENT
    return marks


def draw_object_mark(target: pygame.Surface, box: pygame.Rect, mark: str) -> pygame.Rect:
    """A mark in a bubble over where a thing is drawn. Returns the bubble."""
    top = (box.centerx, box.top - MARK_SIZE[1] - MARK_TAIL)
    return draw_mark(target, glyph(mark), top)


def draw_gem(target: pygame.Surface, box: pygame.Rect, color: tuple[int, int, int]) -> pygame.Rect:
    """A small stone at the foot of where a thing is drawn, in the colour of its rarity."""
    centre = (box.right - GEM // 2 - 1, box.bottom - GEM // 2 - 1)
    half = GEM // 2
    points = [(centre[0], centre[1] - half), (centre[0] + half, centre[1]), (centre[0], centre[1] + half), (centre[0] - half, centre[1])]
    outline = [(centre[0], centre[1] - half - 1), (centre[0] + half + 1, centre[1]), (centre[0], centre[1] + half + 1), (centre[0] - half - 1, centre[1])]
    pygame.draw.polygon(target, PALETTE["ink"], outline)
    pygame.draw.polygon(target, color, points)
    return pygame.Rect(centre[0] - half - 1, centre[1] - half - 1, GEM + 2, GEM + 2)
