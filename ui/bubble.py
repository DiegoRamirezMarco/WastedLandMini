"""Bubbles: a small one over a resident for what they are doing, and a comic one for what someone says."""

import pygame

from graphics.font import LINE_HEIGHT, BitmapFont
from graphics.palette import PALETTE

PADDING = 6
# How far the tail of a speech bubble reaches towards whoever is speaking.
TAIL = 7
# A bubble over a resident: room for an 8×8 icon with a pixel to spare all round, and its tail below.
MARK_SIZE = (12, 12)
MARK_TAIL = 2


def _rounded(target: pygame.Surface, rect: pygame.Rect, fill: str, border: str) -> None:
    """A box with its four corner pixels cut off, outlined."""
    pygame.draw.rect(target, PALETTE[border], rect.inflate(-2, 0))
    pygame.draw.rect(target, PALETTE[border], rect.inflate(0, -2))
    pygame.draw.rect(target, PALETTE[fill], rect.inflate(-2, -2))


def draw_mark(target: pygame.Surface, icon: pygame.Surface, top_centre: tuple[int, int]) -> pygame.Rect:
    """Draw an icon in a small bubble whose tail points down at `top_centre`'s column. Returns the bubble."""
    rect = pygame.Rect(top_centre[0] - MARK_SIZE[0] // 2, top_centre[1], *MARK_SIZE)
    _rounded(target, rect, "paper", "ink")
    target.fill(PALETTE["ink"], (rect.centerx - 1, rect.bottom, 2, 1))
    target.fill(PALETTE["paper"], (rect.centerx - 1, rect.bottom - 1, 2, 1))
    target.fill(PALETTE["ink"], (rect.centerx - 1, rect.bottom + 1, 1, MARK_TAIL - 1))
    target.blit(icon, (rect.x + (rect.width - icon.get_width()) // 2, rect.y + (rect.height - icon.get_height()) // 2))
    return rect


def draw_speech(
    target: pygame.Surface, font: BitmapFont, rect: pygame.Rect, text: str, towards: int = -1, shout: bool = False
) -> None:
    """Draw what someone says in a comic bubble filling `rect`.

    The tail comes out of the left side for `towards` below zero and out of the right otherwise.
    A shout is written larger where there is room for it.
    """
    _rounded(target, rect, "paper", "ink")
    y = rect.y + rect.height // 3
    x = rect.left if towards < 0 else rect.right - 1
    step = -1 if towards < 0 else 1
    for reach in range(TAIL):
        # A wedge that narrows as it leaves the bubble.
        height = TAIL - reach
        column = x + step * (reach + 1)
        target.fill(PALETTE["paper"], (column, y, 1, height))
        target.fill(PALETTE["ink"], (column, y - 1, 1, 1))
        target.fill(PALETTE["ink"], (column, y + height, 1, 1))
    target.fill(PALETTE["paper"], (x, y, 1, TAIL))

    width = rect.width - PADDING * 2
    scale = 2 if shout and len(font.wrap(text, width // 2)) * LINE_HEIGHT * 2 <= rect.height - PADDING * 2 else 1
    lines = font.wrap(text, width // scale)
    line_height = LINE_HEIGHT * scale
    top = rect.y + max(PADDING, (rect.height - len(lines) * line_height) // 2)
    for line in lines:
        if top + line_height > rect.bottom - 2:
            break
        left = rect.x + (rect.width - font.width(line) * scale) // 2
        font.draw(target, line, (left, top), PALETTE["ink"], scale=scale)
        top += line_height
