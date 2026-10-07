"""The game's own pictures, drawn by code: thick dark lines and flat colour, at the resolution of the window.

This is the one hand everything the game draws for itself is drawn in (P41): furniture, buildings,
the ground, what is carried, and whoever nobody has drawn. Like the illustrations it stands in
for, it is free of the style contract. A picture is drawn larger than it will be shown and
brought down to size, which is what smooths its edges.
"""

import math
from collections.abc import Sequence

import pygame

from graphics.palette import Color
from graphics.ui_art import darker, lighter

Point = tuple[float, float]

# How many times over a picture is drawn before it is brought down to its size.
DETAIL = 3
LINE: Color = (30, 22, 20)
WOOD: Color = (156, 96, 60)
PALE_WOOD: Color = (198, 150, 100)
METAL: Color = (126, 136, 144)
DARK_METAL: Color = (78, 84, 92)
RUST: Color = (160, 86, 52)
STONE: Color = (150, 146, 138)
SOIL: Color = (112, 82, 60)
SHEET: Color = (236, 229, 212)
PAPER: Color = (251, 247, 238)
BLUE: Color = (62, 112, 150)
GREEN: Color = (104, 152, 84)
RED: Color = (200, 64, 54)
YELLOW: Color = (238, 190, 70)
ORANGE: Color = (232, 128, 54)
GLASS: Color = (150, 204, 214)
CANVAS: Color = (224, 212, 184)
RUBBER: Color = (58, 56, 60)


class Sheet:
    """A picture being drawn. Everything is given in units, whatever size it ends up."""

    def __init__(self, size: tuple[int, int], unit: float, line: float = 3.4, detail: int = DETAIL) -> None:
        self.size = size
        self.surface = pygame.Surface((max(1, size[0]) * detail, max(1, size[1]) * detail), pygame.SRCALPHA)
        # One unit, on the picture as it is drawn.
        self.unit = unit * detail
        self.line = max(2, round(line * self.unit))

    def _rect(self, x: float, y: float, width: float, height: float) -> pygame.Rect:
        unit = self.unit
        return pygame.Rect(round(x * unit), round(y * unit), max(1, round(width * unit)), max(1, round(height * unit)))

    def _points(self, points: Sequence[Point]) -> list[Point]:
        return [(x * self.unit, y * self.unit) for x, y in points]

    def box(
        self, x: float, y: float, width: float, height: float, color: Color, radius: float = 0.0, outline: bool = True
    ) -> None:
        """A filled box with a dark line round it."""
        rect, rounding = self._rect(x, y, width, height), round(radius * self.unit)
        pygame.draw.rect(self.surface, color, rect, border_radius=rounding)
        if outline:
            pygame.draw.rect(self.surface, LINE, rect, self.line, border_radius=rounding)

    def shade(
        self, x: float, y: float, width: float, height: float, color: Color, alpha: int = 255, radius: float = 0.0
    ) -> None:
        """A patch of colour with no line round it, laid over what is there."""
        rect = self._rect(x, y, width, height)
        if alpha >= 255:
            pygame.draw.rect(self.surface, color, rect, border_radius=round(radius * self.unit))
            return
        patch = pygame.Surface(rect.size, pygame.SRCALPHA)
        pygame.draw.rect(patch, (*color, alpha), patch.get_rect(), border_radius=round(radius * self.unit))
        self.surface.blit(patch, rect)

    def oval(
        self, x: float, y: float, width: float, height: float, color: Color, alpha: int = 255, outline: bool = False
    ) -> None:
        rect = self._rect(x, y, width, height)
        if alpha >= 255:
            pygame.draw.ellipse(self.surface, color, rect)
        else:
            patch = pygame.Surface(rect.size, pygame.SRCALPHA)
            pygame.draw.ellipse(patch, (*color, alpha), patch.get_rect())
            self.surface.blit(patch, rect)
        if outline:
            pygame.draw.ellipse(self.surface, LINE, rect, self.line)

    def poly(self, points: Sequence[Point], color: Color, outline: bool = True) -> None:
        scaled = self._points(points)
        pygame.draw.polygon(self.surface, color, scaled)
        if outline:
            self._trace([*scaled, scaled[0]], LINE, self.line)

    def stroke(self, points: Sequence[Point], color: Color = LINE, width: float = 2.0) -> None:
        """A line through some points, with round ends and corners."""
        self._trace(self._points(points), color, max(1, round(width * self.unit)))

    def _trace(self, scaled: Sequence[Point], color: Color, thick: int) -> None:
        pygame.draw.lines(self.surface, color, False, list(scaled), thick)
        for point in scaled:
            pygame.draw.circle(self.surface, color, point, thick / 2)

    def arc(
        self, x: float, y: float, radius: float, start: float, end: float, color: Color = LINE, width: float = 2.0
    ) -> None:
        """Part of a ring between two angles, in degrees clockwise from the right."""
        steps = max(4, int(abs(end - start) / 12))
        points = [
            (x + radius * math.cos(math.radians(angle)), y + radius * math.sin(math.radians(angle)))
            for angle in (start + (end - start) * step / steps for step in range(steps + 1))
        ]
        self.stroke(points, color, width)

    def block(
        self,
        x: float,
        y: float,
        width: float,
        deep: float,
        height: float,
        color: Color,
        radius: float = 3.0,
        top: Color | None = None,
    ) -> None:
        """A box seen from its front and a little from above: its top, `deep` down the picture, over its front."""
        self.box(x, y + deep - 0.01, width, height, color, radius)
        self.shade(x + 2.6, y + deep + height * 0.62, width - 5.2, height * 0.3, darker(color, 0.16), 255, 2)
        self.box(x, y, width, deep, top if top is not None else lighter(color, 0.2), radius)
        self.shade(x + 3, y + 2.6, width - 6, min(3.4, deep / 3), lighter(top if top is not None else color, 0.42), 255, 1.5)

    def ground_shade(self, x: float, y: float, width: float, height: float, alpha: int = 70) -> None:
        """The shade a thing throws on the ground it stands on."""
        self.oval(x, y, width, height, (0, 0, 0), alpha)

    def finished(self) -> pygame.Surface:
        return pygame.transform.smoothscale(self.surface, (max(1, self.size[0]), max(1, self.size[1])))
