"""What the drawing screens share beyond a brush: shapes laid down in one go, and a field of colour to pick any from.

Nothing here knows which screen it is on. A screen says where on its paper the mouse is, and puts
what comes of it on whichever drawing is in hand.
"""

import colorsys
import math

import pygame

from graphics.palette import PALETTE

Point = tuple[int, int]
Color = tuple[int, int, int]

LINE_TOOL, BOX_TOOL, OVAL_TOOL, POLYGON_TOOL = "line", "box", "oval", "polygon"
SHAPE_LABELS = {LINE_TOOL: "Recta", BOX_TOOL: "Cuadro", OVAL_TOOL: "Círculo", POLYGON_TOOL: "Polígono"}
FILLED_LABEL, HOLLOW_LABEL = "Forma: rellena", "Forma: hueca"
POLYGON_NOTICE = "Clic en cada esquina. Clic derecho, Enter o la primera esquina lo cierran"
# Pixels of the drawing within which a click on the first corner of a polygon closes it.
CLOSE_WITHIN = 7
# How wide the strip of greys beside the colours is, and how light the field is at its top and bottom.
GREY_STRIP = 12
LIGHTEST, DARKEST = 0.93, 0.1
# The lower half of the field is the same colours with less of them in.
MUTED = 0.4
CLEAR = (0, 0, 0, 0)


def _box(first: Point, second: Point) -> pygame.Rect:
    left, top = min(first[0], second[0]), min(first[1], second[1])
    return pygame.Rect(left, top, abs(second[0] - first[0]) + 1, abs(second[1] - first[1]) + 1)


def paint_shape(
    surface: pygame.Surface, tool: str, points: list[Point], color: Color, size: int, filled: bool, closed: bool = True
) -> None:
    """Lay a shape down on a drawing. `size` is how thick its line is, and all of it when it is not filled.

    A polygon that is not `closed` yet is drawn as the line it is so far.
    """
    if len(points) < 2:
        return
    paint = (*color, 255)
    width = max(1, size)
    first, last = points[0], points[-1]
    if tool == LINE_TOOL:
        pygame.draw.line(surface, paint, first, last, width)
        for end in (first, last):
            pygame.draw.circle(surface, paint, end, max(1, width // 2))
    elif tool == BOX_TOOL:
        pygame.draw.rect(surface, paint, _box(first, last), 0 if filled else min(width, max(1, min(_box(first, last).size) // 2)))
    elif tool == OVAL_TOOL:
        box = _box(first, last)
        if filled or min(box.size) <= width * 2:
            pygame.draw.ellipse(surface, paint, box)
        else:
            # A ring is the oval with a smaller one taken out of it, so that its line has no gaps.
            ring = pygame.Surface(box.size, pygame.SRCALPHA)
            pygame.draw.ellipse(ring, paint, ring.get_rect())
            pygame.draw.ellipse(ring, CLEAR, ring.get_rect().inflate(-width * 2, -width * 2))
            surface.blit(ring, box)
    elif tool == POLYGON_TOOL:
        if closed and filled and len(points) >= 3:
            pygame.draw.polygon(surface, paint, points)
        if len(points) >= 2:
            pygame.draw.lines(surface, paint, closed and len(points) >= 3, points, width)
            for corner in points:
                pygame.draw.circle(surface, paint, corner, max(1, width // 2))


class ShapeDraft:
    """A shape being laid down: where it began, and where the mouse has it now."""

    def __init__(self, tool: str, where: str, at: Point) -> None:
        self.tool = tool
        # Which drawing it is on, for a screen with more than one.
        self.where = where
        self.points: list[Point] = [at, at]

    def move(self, at: Point) -> None:
        """Take the end still in hand to where the mouse is."""
        self.points[-1] = at

    def corner(self, at: Point) -> bool:
        """Fix a corner of a polygon and go on to the next. Returns whether that closed it."""
        if len(self.points) >= 4 and math.dist(at, self.points[0]) <= CLOSE_WITHIN:
            return True
        self.points[-1] = at
        self.points.append(at)
        return False

    @property
    def fixed(self) -> list[Point]:
        """The corners of a polygon that have been put down, without the one still in hand."""
        return self.points[:-1]

    @property
    def drawn(self) -> bool:
        """Whether it has any size: a press and release in one place is not a shape."""
        return self.points[0] != self.points[-1]

    def paint(self, surface: pygame.Surface, color: Color, size: int, filled: bool, closed: bool = True) -> None:
        points = self.fixed if self.tool == POLYGON_TOOL and closed else self.points
        paint_shape(surface, self.tool, points, color, size, filled, closed)

    def shown_on(self, drawing: pygame.Surface, color: Color, size: int, filled: bool) -> pygame.Surface:
        """The drawing as it would be with the shape as it stands, to be seen while it is made."""
        picture = drawing.copy()
        self.paint(picture, color, size, filled, closed=self.tool != POLYGON_TOOL)
        return picture


class ColorField:
    """A field of every colour to pick one from: around the colours from left to right, lighter
    above and darker below, with them full in the upper half and muted in the lower, and greys beside."""

    def __init__(self, rect: pygame.Rect) -> None:
        self.rect = rect
        self.picture = pygame.Surface(rect.size)
        wide, tall = rect.width - GREY_STRIP, rect.height
        half = tall // 2
        for x in range(rect.width):
            for y in range(tall):
                self.picture.set_at((x, y), self._color(x, y, wide, tall, half))

    @staticmethod
    def _color(x: int, y: int, wide: int, tall: int, half: int) -> Color:
        if x >= wide:
            grey = round(255 * (1.0 - y / max(1, tall - 1)))
            return (grey, grey, grey)
        row, rows, strength = (y, half, 1.0) if y < half else (y - half, tall - half, MUTED)
        light = LIGHTEST + (DARKEST - LIGHTEST) * row / max(1, rows - 1)
        red, green, blue = colorsys.hls_to_rgb(x / max(1, wide), light, strength)
        return (round(red * 255), round(green * 255), round(blue * 255))

    def contains(self, position: Point) -> bool:
        return self.rect.collidepoint(position)

    def color_at(self, position: Point) -> Color:
        """The colour under a place on the screen, the nearest of the field's if it is just off it."""
        x = min(self.rect.width - 1, max(0, position[0] - self.rect.x))
        y = min(self.rect.height - 1, max(0, position[1] - self.rect.y))
        return tuple(self.picture.get_at((x, y)))[:3]

    def draw(self, target: pygame.Surface) -> None:
        target.blit(self.picture, self.rect)
        pygame.draw.rect(target, PALETTE["stone"], self.rect.inflate(2, 2), 1)


def draw_chosen(target: pygame.Surface, rect: pygame.Rect, color: Color) -> None:
    """Show the colour in hand, which may be none of the ready ones."""
    pygame.draw.rect(target, color, rect)
    pygame.draw.rect(target, PALETTE["paper"], rect, 1)
