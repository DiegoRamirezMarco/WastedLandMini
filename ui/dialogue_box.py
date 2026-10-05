"""Box with a line of dialogue or narration, wrapped to fit."""

import pygame

from graphics.font import LINE_HEIGHT, BitmapFont
from graphics.palette import PALETTE
from ui.panel import draw_panel

PADDING = 8


def draw_dialogue_box(
    target: pygame.Surface, font: BitmapFont, rect: pygame.Rect, text: str, speaker: str | None = None
) -> None:
    """Draw `text` in a box. With a speaker, their name is shown first in a brighter colour."""
    draw_panel(target, rect, fill="shadow")
    x, y = rect.x + PADDING, rect.y + PADDING
    if speaker is not None:
        font.draw(target, speaker, (x, y), PALETTE["glow"])
        y += LINE_HEIGHT + 1
    for line in font.wrap(text, rect.width - PADDING * 2):
        if y + LINE_HEIGHT > rect.bottom:
            break
        font.draw(target, line, (x, y), PALETTE["paper"])
        y += LINE_HEIGHT
