"""Close-up faces as 64×64 layers: a base and hair per resident, shared eyes, brows and mouths."""

import pygame

from graphics.face_renderer import EXPRESSIONS, FACE_SIZE
from graphics.palette import PALETTE
from tools.art.residents import LOOKS, Look

Point = tuple[int, int]

CENTRE_X = FACE_SIZE[0] // 2
EYE_Y = 32
EYE_OFFSET = 9
BROW_Y = 25
MOUTH_Y = 44


def _layer() -> pygame.Surface:
    return pygame.Surface(FACE_SIZE, pygame.SRCALPHA)


def _ellipse(surface: pygame.Surface, color: str, rect: tuple[int, int, int, int]) -> None:
    pygame.draw.ellipse(surface, PALETTE[color], rect)


def _rect(surface: pygame.Surface, color: str, rect: tuple[int, int, int, int]) -> None:
    surface.fill(PALETTE[color], rect)


def _pixels(surface: pygame.Surface, color: str, points: list[Point]) -> None:
    for point in points:
        surface.set_at(point, PALETTE[color])


def _mirrored(points: list[Point]) -> list[Point]:
    """Points plus their mirror image across the middle of the face."""
    return points + [(FACE_SIZE[0] - 1 - x, y) for x, y in points]


def _line(start: Point, end: Point, thickness: int = 1) -> list[Point]:
    """Pixels of a straight line, `thickness` pixels tall."""
    (x0, y0), (x1, y1) = start, end
    steps = max(abs(x1 - x0), abs(y1 - y0), 1)
    points = []
    for step in range(steps + 1):
        x = round(x0 + (x1 - x0) * step / steps)
        y = round(y0 + (y1 - y0) * step / steps)
        points += [(x, y + extra) for extra in range(thickness)]
    return points


def _base(look: Look) -> pygame.Surface:
    surface = _layer()
    # Shoulders and neck.
    _ellipse(surface, "ink", (2, 50, 60, 36))
    _ellipse(surface, look.shirt, (3, 51, 58, 34))
    _ellipse(surface, look.shirt_shade, (3, 58, 58, 34))
    _rect(surface, "ink", (24, 44, 16, 12))
    _rect(surface, look.skin_shade, (25, 44, 14, 11))
    # Ears.
    for x in (8, 50):
        _ellipse(surface, "ink", (x, 27, 6, 11))
        _ellipse(surface, look.skin_shade, (x + 1, 28, 4, 9))
    # Head: an outline, a shaded rim to the right and below, and the lit face.
    _ellipse(surface, "ink", (11, 7, 42, 46))
    _ellipse(surface, look.skin_shade, (12, 8, 40, 44))
    _ellipse(surface, look.skin, (12, 8, 37, 41))
    # Nose.
    _pixels(surface, look.skin_shade, [(32, 34), (32, 35), (32, 36), (33, 37), (32, 38), (31, 38), (30, 38)])
    return surface


def _hair(look: Look) -> pygame.Surface:
    surface = _layer()
    style = look.hair_style
    if style == "long":
        # Curtains down both sides, behind the cap drawn next.
        for x in (7, 46):
            _rect(surface, "ink", (x, 20, 11, 39))
            _rect(surface, look.hair, (x + 1, 20, 9, 38))
            _rect(surface, look.hair_shade, (x + 1 if x < 32 else x + 7, 24, 3, 34))
    if style == "bun":
        _ellipse(surface, "ink", (24, 0, 16, 13))
        _ellipse(surface, look.hair, (25, 1, 14, 11))
        _ellipse(surface, look.hair_shade, (29, 5, 10, 7))
    # Cap of hair over the top of the head, cut off in a fringe.
    cap = _layer()
    _ellipse(cap, "ink", (9, 4, 46, 40))
    _ellipse(cap, look.hair, (10, 5, 44, 38))
    _ellipse(cap, look.hair_shade, (26, 5, 28, 30))
    _ellipse(cap, look.hair, (10, 5, 40, 30))
    fringe = 21 if style == "short" else 23
    surface.blit(cap, (0, 0), (0, 0, FACE_SIZE[0], fringe))
    _rect(surface, "ink", (13, fringe, 38, 1))
    # Sideburns.
    for x in (11, 49):
        _rect(surface, "ink", (x, fringe, 4, 8))
        _rect(surface, look.hair, (x + 1, fringe, 2, 7))
    return surface


def _eyes(expression: str) -> pygame.Surface:
    surface = _layer()
    for side in (-1, 1):
        x = CENTRE_X + side * EYE_OFFSET - (1 if side > 0 else 0)
        if expression == "happy":
            # Closed, curved upwards.
            arc = [(x - 4, EYE_Y + 1), (x - 3, EYE_Y), (x - 2, EYE_Y - 1), (x - 1, EYE_Y - 1), (x, EYE_Y - 1),
                   (x + 1, EYE_Y - 1), (x + 2, EYE_Y), (x + 3, EYE_Y + 1)]
            _pixels(surface, "ink", arc + [(px, py + 1) for px, py in arc[2:6]])
            continue
        _rect(surface, "ink", (x - 5, EYE_Y - 3, 10, 7))
        _rect(surface, "paper", (x - 4, EYE_Y - 2, 8, 5))
        _rect(surface, "ink", (x - 2, EYE_Y - 2, 4, 5))
        _pixels(surface, "paper", [(x - 1, EYE_Y - 1)])
        if expression == "angry":
            # The lid comes down towards the nose.
            inner = x - side * 4
            _pixels(surface, "ink", _line((inner, EYE_Y), (x + side * 4, EYE_Y - 2), thickness=1)
                    + _line((inner, EYE_Y - 1), (x + side * 1, EYE_Y - 2)))
        elif expression == "sad":
            # The lid droops at the outer corner.
            outer = x + side * 4
            _pixels(surface, "ink", _line((outer, EYE_Y), (x - side * 4, EYE_Y - 2))
                    + _line((outer, EYE_Y - 1), (x - side * 1, EYE_Y - 2)))
    return surface


def _brows(expression: str) -> pygame.Surface:
    surface = _layer()
    # Left brow from its outer end to its inner end; the right one is its mirror image.
    slopes = {"neutral": (0, 0), "angry": (-2, 3), "sad": (2, -2), "happy": (-1, -2)}
    outer, inner = slopes[expression]
    brow = _line((CENTRE_X - 15, BROW_Y + outer), (CENTRE_X - 5, BROW_Y + inner), thickness=2)
    _pixels(surface, "ink", _mirrored(brow))
    return surface


def _mouth(expression: str) -> pygame.Surface:
    surface = _layer()
    if expression == "neutral":
        _rect(surface, "ink", (CENTRE_X - 6, MOUTH_Y, 12, 2))
    elif expression == "happy":
        smile = _line((CENTRE_X - 8, MOUTH_Y - 2), (CENTRE_X - 4, MOUTH_Y + 2), thickness=2)
        _pixels(surface, "ink", _mirrored(smile))
        _rect(surface, "ink", (CENTRE_X - 4, MOUTH_Y + 2, 8, 2))
    elif expression == "sad":
        frown = _line((CENTRE_X - 7, MOUTH_Y + 3), (CENTRE_X - 3, MOUTH_Y), thickness=2)
        _pixels(surface, "ink", _mirrored(frown))
        _rect(surface, "ink", (CENTRE_X - 3, MOUTH_Y, 6, 2))
    else:
        # Angry: teeth bared in a downturned mouth.
        _rect(surface, "ink", (CENTRE_X - 8, MOUTH_Y - 2, 16, 7))
        _rect(surface, "paper", (CENTRE_X - 7, MOUTH_Y - 1, 14, 2))
        _rect(surface, "blood_dark", (CENTRE_X - 7, MOUTH_Y + 2, 14, 2))
        _pixels(surface, "ink", [(x, MOUTH_Y - 1) for x in range(CENTRE_X - 4, CENTRE_X + 6, 3)]
                + [(x, MOUTH_Y) for x in range(CENTRE_X - 4, CENTRE_X + 6, 3)])
        _pixels(surface, "ink", _mirrored([(CENTRE_X - 9, MOUTH_Y + 3), (CENTRE_X - 9, MOUTH_Y + 4)]))
    return surface


def build() -> dict[str, pygame.Surface]:
    art: dict[str, pygame.Surface] = {}
    for face_id, look in LOOKS.items():
        art[f"faces/base/{face_id}.png"] = _base(look)
        art[f"faces/hair/{face_id}.png"] = _hair(look)
    for expression in EXPRESSIONS:
        art[f"faces/eyes/{expression}.png"] = _eyes(expression)
        art[f"faces/brows/{expression}.png"] = _brows(expression)
        art[f"faces/mouth/{expression}.png"] = _mouth(expression)
    return art
