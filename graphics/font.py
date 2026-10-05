"""Proportional pixel font read from a sprite sheet."""

import pygame

from graphics.palette import Color

FONT_SHEET = "ui/font.png"
# Each glyph sits at the left of its cell: 2 rows for accents on capitals, 7 for the letter body,
# 2 for descenders.
CELL_SIZE = (6, 11)
SHEET_COLUMNS = 16
FONT_CHARS = (
    " !\"#$%&'()*+,-./0123456789:;<=>?@ABCDEFGHIJKLMNOPQRSTUVWXYZ[\\]^_`abcdefghijklmnopqrstuvwxyz{|}~"
    "ÁÉÍÓÚÜÑáéíóúüñ¿¡·—×"
)
# One extra cell after the last character holds the glyph shown for anything not in FONT_CHARS.
GLYPH_COUNT = len(FONT_CHARS) + 1
SHEET_SIZE = (SHEET_COLUMNS * CELL_SIZE[0], -(-GLYPH_COUNT // SHEET_COLUMNS) * CELL_SIZE[1])

SPACE_WIDTH = 3
LETTER_SPACING = 1
LINE_HEIGHT = CELL_SIZE[1] + 1
ELLIPSIS = "..."
CACHE_LIMIT = 512


class BitmapFont:
    def __init__(self, sheet: pygame.Surface) -> None:
        self._glyphs: list[tuple[pygame.mask.Mask, int]] = []
        width, height = CELL_SIZE
        for index in range(GLYPH_COUNT):
            cell = (index % SHEET_COLUMNS * width, index // SHEET_COLUMNS * height, width, height)
            mask = pygame.mask.from_surface(sheet.subsurface(cell))
            boxes = mask.get_bounding_rects()
            used = max((box.right for box in boxes), default=SPACE_WIDTH)
            self._glyphs.append((mask, used))
        self._cache: dict[tuple[str, Color, int], pygame.Surface] = {}

    def _glyph(self, char: str) -> tuple[pygame.mask.Mask, int]:
        index = FONT_CHARS.find(char)
        return self._glyphs[index if index >= 0 else GLYPH_COUNT - 1]

    def width(self, text: str) -> int:
        """Width of `text` in pixels at scale 1."""
        if not text:
            return 0
        return sum(self._glyph(char)[1] for char in text) + LETTER_SPACING * (len(text) - 1)

    def truncate(self, text: str, max_width: int) -> str:
        """Return `text`, shortened with an ellipsis if it is wider than `max_width`."""
        if self.width(text) <= max_width:
            return text
        while text and self.width(text + ELLIPSIS) > max_width:
            text = text[:-1]
        return text.rstrip() + ELLIPSIS

    def wrap(self, text: str, max_width: int) -> list[str]:
        """Split `text` into lines no wider than `max_width`, breaking between words."""
        lines: list[str] = []
        current = ""
        for word in text.split():
            candidate = f"{current} {word}" if current else word
            if current and self.width(candidate) > max_width:
                lines.append(current)
                current = word
            else:
                current = candidate
        return lines + [current] if current else lines

    def render(self, text: str, color: Color, scale: int = 1) -> pygame.Surface:
        """Return `text` drawn in `color`. `scale` must be a whole number."""
        key = (text, color, scale)
        cached = self._cache.get(key)
        if cached is not None:
            return cached
        surface = pygame.Surface((max(1, self.width(text)), CELL_SIZE[1]), pygame.SRCALPHA)
        x = 0
        for char in text:
            mask, width = self._glyph(char)
            mask.to_surface(surface, setcolor=color, unsetcolor=None, dest=(x, 0))
            x += width + LETTER_SPACING
        if scale != 1:
            surface = pygame.transform.scale(
                surface, (surface.get_width() * scale, surface.get_height() * scale)
            )
        if len(self._cache) >= CACHE_LIMIT:
            self._cache.clear()
        self._cache[key] = surface
        return surface

    def draw(
        self, target: pygame.Surface, text: str, position: tuple[int, int], color: Color, scale: int = 1
    ) -> None:
        target.blit(self.render(text, color, scale), position)
