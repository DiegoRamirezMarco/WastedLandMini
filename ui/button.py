"""Clickable text button. It reports an intent; what the intent does is up to the scene."""

from collections.abc import Hashable
from dataclasses import dataclass

import pygame

from graphics.font import CELL_SIZE, BitmapFont
from graphics.palette import PALETTE

PADDING_X = 4
HEIGHT = CELL_SIZE[1] + 2


@dataclass
class Button:
    rect: pygame.Rect
    label: str
    intent: Hashable

    @classmethod
    def at(cls, font: BitmapFont, x: int, y: int, label: str, intent: Hashable) -> "Button":
        return cls(pygame.Rect(x, y, font.width(label) + PADDING_X * 2, HEIGHT), label, intent)

    def contains(self, position: tuple[int, int]) -> bool:
        return self.rect.collidepoint(position)

    def draw(self, target: pygame.Surface, font: BitmapFont, active: bool = False) -> None:
        pygame.draw.rect(target, PALETTE["lamp" if active else "shadow"], self.rect)
        pygame.draw.rect(target, PALETTE["iron"], self.rect, 1)
        color = PALETTE["ink" if active else "bone"]
        font.draw(target, self.label, (self.rect.x + PADDING_X, self.rect.y + (self.rect.height - CELL_SIZE[1]) // 2), color)
