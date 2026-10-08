"""The interface as it is drawn at the resolution of the window: frames, buttons, bars and icons.

All of it is made by code, smooth and in whatever colours it takes: like the illustrations it is
shown with, it is free of the style contract. Every size here is in pixels of the window.
"""

import math
import random
from collections.abc import Callable, Sequence
from dataclasses import dataclass

import pygame

from graphics.palette import PALETTE, Color

Point = tuple[float, float]
Size = tuple[int, int]

# How many times over a shape is drawn before it is brought down to its size, which is what smooths its edges.
FRAME_DETAIL = 2
ICON_DETAIL = 4
# The side of the square an icon is laid out on, whatever size it ends up.
UNITS = 48.0
WHITE: Color = (255, 255, 255)
BLACK: Color = (0, 0, 0)
CREAM: Color = (252, 246, 230)
CLEAR = (255, 255, 255, 0)
GRAIN_TILE = 96


def mix(one: Color, other: Color, share: float) -> Color:
    """A colour that far from one towards the other."""
    return tuple(round(a + (b - a) * share) for a, b in zip(one, other))  # type: ignore[return-value]


def lighter(color: Color, share: float) -> Color:
    return mix(color, WHITE, share)


def darker(color: Color, share: float) -> Color:
    return mix(color, BLACK, share)


def _gradient(size: Size, top: Color, bottom: Color) -> pygame.Surface:
    column = pygame.Surface((1, size[1]), pygame.SRCALPHA)
    last = max(1, size[1] - 1)
    for y in range(size[1]):
        column.set_at((0, y), (*mix(top, bottom, y / last), 255))
    return pygame.transform.scale(column, size)


def _rounded(surface: pygame.Surface, radius: int) -> pygame.Surface:
    """Cut the corners off a picture, keeping its colours up to the very edge."""
    mask = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
    mask.fill(CLEAR)
    pygame.draw.rect(mask, (255, 255, 255, 255), mask.get_rect(), border_radius=max(0, radius))
    surface.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
    return surface


def _plate(size: Size, top: Color, bottom: Color, radius: int) -> pygame.Surface:
    return _rounded(_gradient((max(1, size[0]), max(1, size[1])), top, bottom), radius)


def _veil(size: Size, color: Color, alpha: int) -> pygame.Surface:
    veil = pygame.Surface(size, pygame.SRCALPHA)
    veil.fill((*color, alpha))
    return veil


_grain: pygame.Surface | None = None


def _grained(surface: pygame.Surface) -> None:
    """A little unevenness over a face, so that it is not one flat sheet of colour."""
    global _grain
    if _grain is None:
        # Not the simulation's randomness: the same speckle every time, and nothing rides on it.
        chance = random.Random(7)
        _grain = pygame.Surface((GRAIN_TILE, GRAIN_TILE), pygame.SRCALPHA)
        for y in range(GRAIN_TILE):
            for x in range(GRAIN_TILE):
                shade = chance.random()
                _grain.set_at((x, y), (*(WHITE if shade > 0.5 else BLACK), int(abs(shade - 0.5) * 22)))
    for y in range(0, surface.get_height(), GRAIN_TILE):
        for x in range(0, surface.get_width(), GRAIN_TILE):
            surface.blit(_grain, (x, y))


@dataclass(frozen=True)
class FrameStyle:
    """How a panel looks: the colour of its face, the line round it, and what it wears."""

    fill: Color
    trim: Color
    radius: int = 6
    # A band across its top, for a heading, and how tall it is.
    band: Color | None = None
    band_height: int = 0
    # Rivets in its corners, as on a plate of metal.
    rivets: bool = False
    # How far a soft shadow spreads round it. The picture is that much larger on every side.
    shadow: int = 0


def frame(size: Size, style: FrameStyle) -> pygame.Surface:
    """A panel of a size. With a shadow, the picture is larger than the panel by it on every side."""
    k = FRAME_DETAIL
    width, height = max(8, size[0]) * k, max(8, size[1]) * k
    radius = min(style.radius, size[0] // 2, size[1] // 2) * k
    picture = _plate((width, height), darker(style.fill, 0.7), darker(style.fill, 0.8), radius)
    line = 2 * k
    trim = _plate(
        (width - 2 * k, height - 2 * k), lighter(style.trim, 0.22), darker(style.trim, 0.3), radius - k
    )
    picture.blit(trim, (k, k))
    inner = (width - 2 * k - 2 * line, height - 2 * k - 2 * line)
    face_radius = max(0, radius - k - line)
    face = _gradient((max(1, inner[0]), max(1, inner[1])), lighter(style.fill, 0.08), darker(style.fill, 0.2))
    if style.band is not None and style.band_height:
        band_height = min(inner[1], style.band_height * k)
        face.blit(_gradient((inner[0], band_height), lighter(style.band, 0.12), darker(style.band, 0.22)), (0, 0))
        face.blit(_veil((inner[0], k), BLACK, 130), (0, band_height))
        face.blit(_veil((inner[0], k), WHITE, 22), (0, band_height + k))
    _grained(face)
    # Light catches the top of the face, and the line round it throws a shadow on it.
    face.blit(_veil((inner[0], k), WHITE, 34), (0, k))
    pygame.draw.rect(face, (0, 0, 0, 255), face.get_rect(), k)
    face.blit(_veil((inner[0], k), BLACK, 60), (0, inner[1] - 2 * k))
    _rounded(face, face_radius)
    picture.blit(face, (k + line, k + line))
    if style.rivets:
        reach = 7 * k
        for x in (reach, width - reach):
            for y in (reach, height - reach):
                pygame.draw.circle(picture, darker(style.fill, 0.75), (x, y + k // 2), 3 * k)
                pygame.draw.circle(picture, darker(style.trim, 0.1), (x, y), 2.4 * k)
                pygame.draw.circle(picture, lighter(style.trim, 0.55), (x - 0.6 * k, y - 0.7 * k), 0.9 * k)
    picture = pygame.transform.smoothscale(picture, (width // k, height // k))
    if not style.shadow:
        return picture
    spread = style.shadow
    whole = pygame.Surface((picture.get_width() + spread * 2, picture.get_height() + spread * 2), pygame.SRCALPHA)
    cast = pygame.Rect(spread, spread + spread // 3, *picture.get_size())
    pygame.draw.rect(whole, (0, 0, 0, 150), cast, border_radius=style.radius)
    whole = pygame.transform.gaussian_blur(whole, max(1, spread // 2))
    whole.blit(picture, (spread, spread))
    return whole


def pill(size: Size, fill: Color, trim: Color, radius: int = 6, pressed: bool = False) -> pygame.Surface:
    """The back of a button: raised, or pressed in."""
    k = FRAME_DETAIL
    width, height = max(4, size[0]) * k, max(4, size[1]) * k
    radius = min(radius, size[0] // 2, size[1] // 2) * k
    picture = _plate((width, height), darker(fill, 0.72), darker(fill, 0.8), radius)
    picture.blit(_plate((width - 2 * k, height - 2 * k), lighter(trim, 0.2), darker(trim, 0.3), radius - k), (k, k))
    top, bottom = (darker(fill, 0.12), lighter(fill, 0.1)) if pressed else (lighter(fill, 0.2), darker(fill, 0.2))
    inner = (width - 4 * k, height - 4 * k)
    face = _gradient((max(1, inner[0]), max(1, inner[1])), top, bottom)
    if not pressed:
        # A gloss over its upper half.
        face.blit(_veil((inner[0], inner[1] // 2), WHITE, 26), (0, 0))
        face.blit(_veil((inner[0], k), WHITE, 60), (0, 0))
    else:
        face.blit(_veil((inner[0], k * 2), BLACK, 60), (0, 0))
    picture.blit(_rounded(face, max(0, radius - 2 * k)), (2 * k, 2 * k))
    return pygame.transform.smoothscale(picture, (width // k, height // k))


def bar(size: Size, share: float, color: Color) -> pygame.Surface:
    """A measure from nothing to full, as a rounded track with that share of it filled."""
    k = FRAME_DETAIL
    width, height = max(4, size[0]) * k, max(4, size[1]) * k
    radius = height // 2
    track = PALETTE["ink"]
    picture = _plate((width, height), darker(track, 0.45), lighter(track, 0.12), radius)
    inner = (width - 2 * k, height - 2 * k)
    filled = round(inner[0] * max(0.0, min(1.0, share)))
    if filled > 0:
        # Never so short that its round ends do not fit.
        filled = max(filled, min(inner[0], inner[1]))
        fill = _gradient((filled, inner[1]), lighter(color, 0.16), darker(color, 0.2))
        fill.blit(_veil((filled, max(1, inner[1] // 3)), WHITE, 56), (0, k // 2))
        picture.blit(_rounded(fill, inner[1] // 2), (k, k))
    return pygame.transform.smoothscale(picture, (width // k, height // k))


class Pen:
    """Draws an icon on a square of `UNITS` a side, whatever size the picture under it is."""

    def __init__(self, surface: pygame.Surface, main: Color, cut: Color, soft: Color, light: Color) -> None:
        self.surface = surface
        self.k = surface.get_width() / UNITS
        # The colour of the thing, of what is cut into it, of what stands behind it and of what shines on it.
        self.main, self.cut, self.soft, self.light = main, cut, soft, light

    def _at(self, point: Point) -> Point:
        return point[0] * self.k, point[1] * self.k

    def circle(self, x: float, y: float, radius: float, color: Color | None = None) -> None:
        pygame.draw.circle(self.surface, color or self.main, self._at((x, y)), radius * self.k)

    def hole(self, x: float, y: float, radius: float) -> None:
        """Take a round piece out of whatever has been drawn."""
        pygame.draw.circle(self.surface, (0, 0, 0, 0), self._at((x, y)), radius * self.k)

    def box(
        self,
        x: float,
        y: float,
        width: float,
        height: float,
        radius: float = 0.0,
        color: Color | None = None,
        top_only: bool = False,
    ) -> None:
        k = self.k
        rect = pygame.Rect(round(x * k), round(y * k), round(width * k), round(height * k))
        rounding = round(radius * k)
        if top_only:
            pygame.draw.rect(
                self.surface, color or self.main, rect, border_top_left_radius=rounding, border_top_right_radius=rounding
            )
        else:
            pygame.draw.rect(self.surface, color or self.main, rect, border_radius=rounding)

    def poly(self, points: Sequence[Point], color: Color | None = None) -> None:
        pygame.draw.polygon(self.surface, color or self.main, [self._at(point) for point in points])

    def line(self, points: Sequence[Point], width: float, color: Color | None = None) -> None:
        """A thick line through some points, with round ends and round corners."""
        color = color or self.main
        half = width / 2
        for start, end in zip(points, points[1:]):
            dx, dy = end[0] - start[0], end[1] - start[1]
            length = math.hypot(dx, dy) or 1.0
            nx, ny = -dy / length * half, dx / length * half
            self.poly(
                [(start[0] + nx, start[1] + ny), (end[0] + nx, end[1] + ny), (end[0] - nx, end[1] - ny), (start[0] - nx, start[1] - ny)],
                color,
            )
        for point in points:
            self.circle(point[0], point[1], half, color)

    def arc(
        self, x: float, y: float, radius: float, start: float, end: float, width: float, color: Color | None = None
    ) -> None:
        """Part of a ring, between two angles in degrees, measured clockwise from the right."""
        steps = max(6, int(abs(end - start) / 8))
        points = [
            (x + radius * math.cos(math.radians(angle)), y + radius * math.sin(math.radians(angle)))
            for angle in (start + (end - start) * step / steps for step in range(steps + 1))
        ]
        self.line(points, width, color)

    def turned(
        self, x: float, y: float, width: float, height: float, degrees: float, color: Color | None = None
    ) -> None:
        """A box about its middle, turned clockwise."""
        cos, sin = math.cos(math.radians(degrees)), math.sin(math.radians(degrees))
        corners = [(-width / 2, -height / 2), (width / 2, -height / 2), (width / 2, height / 2), (-width / 2, height / 2)]
        self.poly([(x + dx * cos - dy * sin, y + dx * sin + dy * cos) for dx, dy in corners], color)


Glyph = Callable[[Pen], None]


def _people(p: Pen) -> None:
    for x in (9.5, 38.5):
        p.circle(x, 20, 5.2, p.soft)
        p.box(x - 7.5, 27.5, 15, 15, 6.5, p.soft, top_only=True)
    p.circle(24, 15.5, 9.6, p.cut)
    p.box(8.5, 26.5, 31, 16, 11.5, p.cut, top_only=True)
    p.circle(24, 15.5, 7.4)
    p.box(11, 29, 26, 13.5, 9.5, top_only=True)


def _hammer(p: Pen) -> None:
    p.turned(21, 29, 5.5, 31, 45)
    p.turned(32.5, 17.5, 25, 12.5, 45, p.cut)
    p.turned(32.5, 17.5, 22, 9.5, 45)
    p.turned(29.3, 14.3, 2.2, 9.5, 45, p.soft)


def _book(p: Pen) -> None:
    p.poly([(4.5, 11.5), (22.5, 15), (22.5, 40), (4.5, 36.5)])
    p.poly([(43.5, 11.5), (25.5, 15), (25.5, 40), (43.5, 36.5)])
    p.box(22.5, 15, 3, 25, 0, p.soft)
    for y in (20.5, 26, 31.5):
        p.line([(8.5, y - 1.7), (18.5, y + 0.2)], 2.2, p.cut)
        p.line([(39.5, y - 1.7), (29.5, y + 0.2)], 2.2, p.cut)


def _crate(p: Pen) -> None:
    p.box(7, 16, 34, 27, 3)
    p.line([(12, 22.5), (36, 38.5)], 3.2, p.cut)
    p.line([(36, 22.5), (12, 38.5)], 3.2, p.cut)
    p.box(7, 16, 34, 4, 0, p.soft)
    p.box(4.5, 8.5, 39, 9, 2.5)
    for x in (9, 39):
        p.circle(x, 13, 1.5, p.cut)


def _hall(p: Pen) -> None:
    p.poly([(24, 4.5), (44.5, 16.5), (3.5, 16.5)])
    p.circle(24, 12, 2.4, p.cut)
    p.box(6, 18.5, 36, 4)
    for x in (8.5, 17.5, 26, 35):
        p.box(x, 24.5, 4.6, 12.5, 1)
    p.box(6, 38.5, 36, 3.2)
    p.box(3, 42.2, 42, 3.2, 1)


def _bell(p: Pen) -> None:
    p.circle(24, 7.2, 3.2)
    p.circle(24, 20.5, 11.5)
    p.box(12.5, 20.5, 23, 12)
    p.poly([(12.5, 28), (35.5, 28), (42, 37), (6, 37)])
    p.box(6, 35.5, 36, 3.4, 1.7)
    p.circle(24, 42.2, 3.6)
    p.arc(24, 20.5, 7.5, 200, 250, 2.2, p.light)


def _map(p: Pen) -> None:
    p.poly([(4.5, 13.5), (17, 9), (31, 13.5), (43.5, 9), (43.5, 36), (31, 40.5), (17, 36), (4.5, 40.5)])
    p.poly([(17, 9), (31, 13.5), (31, 40.5), (17, 36)], p.soft)
    p.circle(24, 20.5, 6, p.cut)
    p.poly([(18.6, 23.2), (29.4, 23.2), (24, 33)], p.cut)
    p.circle(24, 20.5, 2.4, p.light)


def _disk(p: Pen) -> None:
    p.poly([(7.5, 10), (10, 7.5), (33.5, 7.5), (40.5, 14.5), (40.5, 38), (38, 40.5), (10, 40.5), (7.5, 38)])
    p.box(14.5, 7.5, 16, 11.5, 0, p.cut)
    p.box(24, 9.5, 4.2, 7.5, 0, p.light)
    p.box(12.5, 24.5, 23, 16, 1.5, p.cut)
    p.line([(16, 30), (32, 30)], 1.8, p.light)
    p.line([(16, 35), (32, 35)], 1.8, p.light)


def _town(p: Pen) -> None:
    p.box(20.5, 7.5, 12.5, 36)
    p.box(34.5, 25, 10, 18.5, 0, p.soft)
    p.poly([(2, 24.5), (11.5, 14), (21, 24.5)])
    p.box(5, 24, 13, 19.5)
    for y in (11.5, 18.5, 25.5):
        p.box(22.8, y, 3, 4.2, 0, p.cut)
        p.box(27.6, y, 3, 4.2, 0, p.cut)
    p.box(9.5, 33, 4.2, 10.5, 0, p.cut)
    p.box(37.5, 29.5, 4.2, 4.2, 0, p.cut)
    p.box(1.5, 42.5, 45, 2.6, 1)


def _pencil(p: Pen) -> None:
    p.turned(28, 20, 9.5, 27, 45)
    p.turned(33.3, 14.7, 9.5, 2.4, 45, p.cut)
    p.turned(36.5, 11.5, 9.5, 4.2, 45, p.soft)
    p.poly([(21.8, 32.9), (15.1, 26.2), (9.5, 38.5)], p.soft)
    p.poly([(9.5, 38.5), (13.6, 36.6), (11.4, 34.4)], p.cut)


def _house(p: Pen) -> None:
    p.box(32.5, 8.5, 5.5, 11)
    p.poly([(24, 5.5), (45.5, 24.5), (2.5, 24.5)])
    p.box(9, 24, 30, 19)
    p.box(20.5, 30.5, 7, 12.5, 1, p.cut)
    p.box(12, 28.5, 5.6, 5.6, 0, p.cut)
    p.box(30.4, 28.5, 5.6, 5.6, 0, p.cut)


def _mic(p: Pen) -> None:
    p.box(17.5, 4.5, 13, 24, 6.5)
    for y in (11.5, 16, 20.5):
        p.line([(21, y), (27, y)], 1.6, p.cut)
    p.arc(24, 21.5, 12, 0, 180, 3.2)
    p.line([(24, 33.5), (24, 41)], 3.2)
    p.line([(16.5, 42), (31.5, 42)], 3.4)


def _sun(p: Pen) -> None:
    for step in range(8):
        angle = math.radians(step * 45)
        cos, sin = math.cos(angle), math.sin(angle)
        p.line([(24 + 15.5 * cos, 24 + 15.5 * sin), (24 + 20.5 * cos, 24 + 20.5 * sin)], 4.6)
    p.circle(24, 24, 10.5)
    p.circle(21, 21, 3.6, p.light)


def _moon(p: Pen) -> None:
    p.circle(22, 24, 18)
    p.hole(31, 18.5, 15)
    p.circle(13.5, 28, 2.6, p.soft)
    p.circle(19, 36, 1.8, p.soft)


def _apple(p: Pen) -> None:
    p.line([(24, 17), (26.5, 7.5)], 3.4, PALETTE["rust"])
    p.turned(33.5, 10.5, 12, 6, -28, PALETTE["olive"])
    p.circle(16.5, 26, 11)
    p.circle(31.5, 26, 11)
    p.circle(18.5, 32, 11)
    p.circle(29.5, 32, 11)
    p.circle(13.5, 22.5, 3.2, p.light)


def _drop(p: Pen) -> None:
    p.poly([(24, 3.5), (37.5, 26.5), (10.5, 26.5)])
    p.circle(24, 29.5, 14.2)
    p.arc(24, 29.5, 9, 110, 170, 3, p.light)


def _bolt(p: Pen) -> None:
    p.poly([(29.5, 3), (9.5, 27.5), (21.5, 27.5), (17, 45), (38.5, 19), (26, 19)])
    p.poly([(27.5, 8), (15.5, 24), (19.5, 24)], p.light)


def _cross(p: Pen) -> None:
    p.box(5.5, 5.5, 37, 37, 9)
    p.box(19.5, 12, 9, 24, 1.5, p.cut)
    p.box(12, 19.5, 24, 9, 1.5, p.cut)


def _gear(p: Pen) -> None:
    for step in range(8):
        angle = step * 45
        p.turned(24 + 16 * math.cos(math.radians(angle)), 24 + 16 * math.sin(math.radians(angle)), 9, 9, angle)
    p.circle(24, 24, 14.5)
    p.circle(24, 24, 10.5, p.soft)
    p.hole(24, 24, 5.4)


def _lock(p: Pen) -> None:
    p.arc(24, 21, 9.5, 180, 360, 5.5, p.soft)
    p.box(8, 20, 32, 24, 5)
    p.circle(24, 29.5, 4, p.cut)
    p.box(22.2, 30, 3.6, 8.5, 1, p.cut)


def _coin(p: Pen) -> None:
    p.circle(24, 24, 19.5)
    p.circle(24, 24, 15, p.soft)
    p.circle(24, 24, 12.5)
    p.box(21.2, 15.5, 5.6, 17, 1.5, p.cut)
    p.arc(24, 24, 16.8, 195, 255, 2.4, p.light)


def _purse(p: Pen) -> None:
    p.poly([(15.5, 4.5), (32.5, 4.5), (29, 13.5), (19, 13.5)])
    p.circle(24, 29.5, 15)
    p.box(10, 30, 28, 14.5, 7)
    p.box(16.5, 12, 15, 4, 2, p.cut)
    p.circle(24, 30, 7.2, p.cut)
    p.circle(24, 30, 4.8, p.light)


def _kin(p: Pen) -> None:
    p.line([(24, 15), (24, 26)], 3.2, p.soft)
    p.line([(11.5, 26), (36.5, 26)], 3.2, p.soft)
    p.line([(11.5, 26), (11.5, 31)], 3.2, p.soft)
    p.line([(36.5, 26), (36.5, 31)], 3.2, p.soft)
    p.circle(24, 11.5, 7.6)
    p.circle(11.5, 36, 7.6)
    p.circle(36.5, 36, 7.6)
    p.circle(21.5, 9, 2.2, p.light)


GLYPHS: dict[str, Glyph] = {
    "people": _people,
    "work": _hammer,
    "study": _book,
    "stores": _crate,
    "government": _hall,
    "events": _bell,
    "map": _map,
    "save": _disk,
    "urbanism": _town,
    "draw": _pencil,
    "buildings": _house,
    "voice": _mic,
    "sun": _sun,
    "moon": _moon,
    "food": _apple,
    "water": _drop,
    "energy": _bolt,
    "medicine": _cross,
    "scrap": _gear,
    "lock": _lock,
    "coin": _coin,
    "fund": _purse,
    "family": _kin,
}
# The colour each icon is, where it stands alone or on a tile of its own.
HUES: dict[str, Color] = {
    "people": (226, 104, 74),
    "work": (222, 158, 48),
    "study": (58, 150, 172),
    "stores": (176, 104, 58),
    "government": (146, 98, 170),
    "events": (214, 84, 96),
    "map": (112, 160, 78),
    "save": (76, 118, 176),
    "urbanism": (226, 134, 62),
    "draw": (212, 104, 148),
    "buildings": (72, 162, 132),
    "voice": (88, 176, 196),
    "sun": (246, 196, 62),
    "moon": (168, 208, 222),
    "food": (224, 84, 66),
    "water": (84, 172, 214),
    "energy": (248, 206, 70),
    "medicine": (246, 240, 226),
    "scrap": (188, 172, 150),
    "lock": (226, 186, 84),
    "coin": (240, 190, 70),
    "fund": (206, 156, 62),
    "family": (198, 112, 132),
}
# What is cut into an icon that stands alone, where it is not simply dark.
CUTS: dict[str, Color] = {"medicine": (206, 58, 54)}


def band_hue(name: str) -> Color:
    """The colour of the band over a panel that an entry of the menu opens: its icon's, dark enough to read on."""
    return darker(HUES[name], 0.34)


def icon(name: str, size: int) -> pygame.Surface:
    """An icon standing alone, in its own colour with a dark line round it."""
    k = ICON_DETAIL
    hue = HUES[name]
    side = size * k
    # Room is left all round for the line.
    margin = max(k, round(side * 0.07))
    drawn = pygame.Surface((side - margin * 2, side - margin * 2), pygame.SRCALPHA)
    cut = CUTS.get(name, darker(hue, 0.72))
    GLYPHS[name](Pen(drawn, hue, cut, darker(hue, 0.28), lighter(hue, 0.6)))
    shape = pygame.mask.from_surface(drawn, 96).to_surface(setcolor=(*darker(hue, 0.82), 255), unsetcolor=(0, 0, 0, 0))
    picture = pygame.Surface((side, side), pygame.SRCALPHA)
    for step in range(16):
        angle = math.radians(step * 22.5)
        picture.blit(shape, (margin + round(margin * math.cos(angle)), margin + round(margin * math.sin(angle))))
    picture.blit(drawn, (margin, margin))
    return pygame.transform.smoothscale(picture, (size, size))


def tile(name: str, size: int, lit: bool = False) -> pygame.Surface:
    """An icon in pale on a rounded tile of its own colour, as an entry of a menu wears it."""
    k = ICON_DETAIL
    hue = lighter(HUES[name], 0.12) if lit else HUES[name]
    side = size * k
    radius = round(side * 0.24)
    picture = _plate((side, side), darker(hue, 0.74), darker(hue, 0.8), radius)
    edge = max(k, round(side * 0.035))
    inner = side - edge * 2
    face = _gradient((inner, inner), lighter(hue, 0.26), darker(hue, 0.2))
    # A gloss over its upper half.
    gloss = pygame.Surface((inner, inner), pygame.SRCALPHA)
    pygame.draw.ellipse(gloss, (255, 255, 255, 34), (-inner // 4, -inner // 2, inner * 3 // 2, inner))
    face.blit(gloss, (0, 0))
    picture.blit(_rounded(face, radius - edge), (edge, edge))
    glyph_side = round(side * 0.7)
    corner = (side - glyph_side) // 2
    shade = pygame.Surface((glyph_side, glyph_side), pygame.SRCALPHA)
    dark = darker(hue, 0.6)
    GLYPHS[name](Pen(shade, dark, dark, dark, dark))
    picture.blit(shade, (corner, corner + max(1, round(side * 0.035))))
    drawn = pygame.Surface((glyph_side, glyph_side), pygame.SRCALPHA)
    GLYPHS[name](Pen(drawn, CREAM, darker(hue, 0.42), mix(CREAM, hue, 0.5), WHITE))
    picture.blit(drawn, (corner, corner))
    return pygame.transform.smoothscale(picture, (size, size))
