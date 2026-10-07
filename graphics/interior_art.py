"""Furniture as it is seen from inside a building: from its front, and a little from above.

The art there was is drawn for the map, from straight above. Seen from inside, the same thing
shows its front: a bed its headboard, the top of its mattress and the board at its foot. What is
here is drawn by code at the resolution of the window, in thick dark lines and flat colour, as
the dolls and the player's own drawings are. Like them it is free of the style contract.

So far there is the bed, as a try of how furniture is to look in there (P39).
"""

from collections.abc import Callable
from dataclasses import dataclass

import pygame

from graphics.palette import Color
from graphics.ui_art import darker, lighter

# How many times over a picture is drawn before it is brought down to its size, which smooths its edges.
DETAIL = 3
LINE: Color = (30, 22, 20)
WOOD: Color = (156, 96, 60)
SHEET: Color = (236, 229, 212)
PILLOW: Color = (251, 247, 238)
BLANKET: Color = (62, 112, 150)


@dataclass(frozen=True)
class InsidePicture:
    """A thing as it is seen from inside, in pixels of the window."""

    # What of it is under whoever is in it, and what of it is over them: a bed, and its blanket.
    under: pygame.Surface
    over: pygame.Surface | None
    # How far it stands above the back edge of the floor it takes up.
    rise: int


Painter = Callable[[int, int], InsidePicture]


class _Sheet:
    """A picture being drawn larger than it will be shown, in thick lines."""

    def __init__(self, size: tuple[int, int], unit: float) -> None:
        self.surface = pygame.Surface((size[0] * DETAIL, size[1] * DETAIL), pygame.SRCALPHA)
        # A hundredth of the width of a cell, on the picture as it is drawn.
        self.unit = unit * DETAIL
        self.line = max(2, round(3.4 * self.unit))

    def _rect(self, x: float, y: float, width: float, height: float) -> pygame.Rect:
        unit = self.unit
        return pygame.Rect(round(x * unit), round(y * unit), round(width * unit), round(height * unit))

    def box(self, x: float, y: float, width: float, height: float, color: Color, radius: float = 0.0, outline: bool = True) -> None:
        """A filled shape with a dark line round it."""
        rect, rounding = self._rect(x, y, width, height), round(radius * self.unit)
        pygame.draw.rect(self.surface, color, rect, border_radius=rounding)
        if outline:
            pygame.draw.rect(self.surface, LINE, rect, self.line, border_radius=rounding)

    def shade(self, x: float, y: float, width: float, height: float, color: Color, alpha: int = 255, radius: float = 0.0) -> None:
        """A patch of colour with no line round it, laid over what is there."""
        rect = self._rect(x, y, width, height)
        patch = pygame.Surface(rect.size, pygame.SRCALPHA)
        pygame.draw.rect(patch, (*color, alpha), patch.get_rect(), border_radius=round(radius * self.unit))
        self.surface.blit(patch, rect)

    def stroke(self, points: list[tuple[float, float]], color: Color = LINE, width: float = 2.0) -> None:
        unit = self.unit
        scaled = [(x * unit, y * unit) for x, y in points]
        thick = max(1, round(width * unit))
        pygame.draw.lines(self.surface, color, False, scaled, thick)
        for point in scaled:
            pygame.draw.circle(self.surface, color, point, thick / 2)

    def oval(self, x: float, y: float, width: float, height: float, color: Color, alpha: int) -> None:
        rect = self._rect(x, y, width, height)
        patch = pygame.Surface(rect.size, pygame.SRCALPHA)
        pygame.draw.ellipse(patch, (*color, alpha), patch.get_rect())
        self.surface.blit(patch, rect)

    def finished(self) -> pygame.Surface:
        width, height = self.surface.get_size()
        return pygame.transform.smoothscale(self.surface, (width // DETAIL, height // DETAIL))


def bed(cell: int, depth: int) -> InsidePicture:
    """A bed one cell wide and two deep, its head to the back wall.

    Everything is measured in hundredths of the width of a cell. `depth` is how deep a cell
    looks, which is what makes the top of the mattress as long as it is.
    """
    unit = cell / 100.0
    rise = round(40 * unit)
    deep = 2 * depth / unit
    # Down the picture: the back edge of the floor it takes up, where the mattress ends at the
    # board at its foot, and the front edge of that floor.
    back, front = 40.0, 40.0 + deep
    foot = front - 30.0
    size = (cell, rise + 2 * depth)
    under, over = _Sheet(size, unit), _Sheet(size, unit)

    # On the floor, the shade it throws.
    under.oval(2, front - 13, 96, 15, (0, 0, 0), 70)
    # The headboard, face on, between its two posts.
    under.box(9, 5, 82, back + 12, WOOD, 7)
    under.shade(12, 8, 76, 5, lighter(WOOD, 0.22), 255, 3)
    for x in (30, 50, 70):
        under.stroke([(x, 12), (x, back + 6)], darker(WOOD, 0.28), 1.6)
    for x in (4, 86):
        under.box(x, 1, 10, back + 18, darker(WOOD, 0.12), 4)
        under.shade(x + 2, 4, 3, back + 10, lighter(WOOD, 0.2), 255, 1.5)
    # The frame, seen from above, and the mattress in it.
    under.box(7, back + 2, 86, foot - back + 4, darker(WOOD, 0.06), 5)
    under.box(11, back + 5, 78, foot - back - 2, SHEET, 5)
    under.shade(13, back + 7, 74, 5, lighter(SHEET, 0.5), 255, 2.5)
    # The pillow, with the hollow a head leaves in it.
    under.box(19, back + 8, 62, 25, PILLOW, 10)
    under.shade(24, back + 24, 52, 6, darker(PILLOW, 0.14), 255, 3)
    under.oval(35, back + 13, 30, 13, darker(PILLOW, 0.1), 255)

    # The blanket, turned down at the top, over whoever lies there.
    top = back + 38
    over.box(9, top, 82, foot - top + 7, BLANKET, 6)
    # It falls away to one side, which is in a little shade.
    over.shade(72, top + 13, 16.5, foot - top - 9, darker(BLANKET, 0.2), 255, 4)
    over.shade(11.5, top + 13, 5, foot - top - 9, lighter(BLANKET, 0.12), 255, 2.5)
    over.box(9, top, 82, 13, lighter(BLANKET, 0.34), 5)
    over.shade(12, top + 2.4, 76, 3.2, lighter(BLANKET, 0.62), 255, 1.6)
    # Where it lies over a body, in a few folds.
    middle = (top + 13 + foot) / 2
    over.stroke([(26, top + 22), (33, middle - 4), (30, foot - 6)], darker(BLANKET, 0.42), 2.2)
    over.stroke([(58, top + 20), (52, middle + 2), (60, foot - 4)], darker(BLANKET, 0.42), 2.2)
    over.stroke([(74, top + 26), (71, middle + 6)], darker(BLANKET, 0.42), 2.0)
    over.stroke([(40, top + 19), (44, top + 30)], lighter(BLANKET, 0.3), 1.8)
    # The board at its foot, face on, and the feet it stands on.
    for x in (8, 81):
        over.box(x, front - 9, 11, 9, darker(WOOD, 0.3), 2)
    over.box(6, foot - 2, 88, 26, WOOD, 6)
    over.shade(9.5, foot + 1, 81, 4.5, lighter(WOOD, 0.24), 255, 2.2)
    over.shade(9.5, foot + 16, 81, 5, darker(WOOD, 0.2), 255, 2.2)
    for x in (34, 66):
        over.stroke([(x, foot + 3), (x, foot + 20)], darker(WOOD, 0.3), 1.6)
    return InsidePicture(under.finished(), over.finished(), rise)


# What there is a picture of from inside, by kind of object.
PAINTERS: dict[str, Painter] = {"bed": bed}
