"""A track with a knob that is dragged along it. It reports a figure; what the figure is for is up to the scene."""

from dataclasses import dataclass

import pygame

from graphics.palette import PALETTE

KNOB_WIDTH = 6
# How far above and below the track a press still takes hold of it.
GRIP = 5


@dataclass
class Slider:
    rect: pygame.Rect
    low: float
    high: float

    def contains(self, position: tuple[int, int]) -> bool:
        return self.rect.inflate(KNOB_WIDTH, GRIP * 2).collidepoint(position)

    def value_at(self, x: int) -> float:
        """The figure the knob stands for at a canvas position, kept within the track."""
        share = (min(max(x, self.rect.left), self.rect.right) - self.rect.left) / max(1, self.rect.width)
        return self.low + (self.high - self.low) * share

    def knob_x(self, value: float) -> int:
        share = (min(max(value, self.low), self.high) - self.low) / ((self.high - self.low) or 1.0)
        return self.rect.left + round(self.rect.width * share)

    def draw(self, target: pygame.Surface, value: float, resting: float | None = None, active: bool = False) -> None:
        """Draw the track filled up to the knob. `resting` is where the knob does nothing, marked with a notch."""
        pygame.draw.rect(target, PALETTE["shadow"], self.rect)
        x = self.knob_x(value)
        start = self.knob_x(resting) if resting is not None else self.rect.left
        filled = pygame.Rect(min(start, x), self.rect.y, abs(x - start), self.rect.height)
        pygame.draw.rect(target, PALETTE["copper"], filled)
        pygame.draw.rect(target, PALETTE["iron"], self.rect, 1)
        if resting is not None:
            pygame.draw.line(target, PALETTE["dust"], (start, self.rect.top - 2), (start, self.rect.bottom + 1))
        knob = pygame.Rect(0, 0, KNOB_WIDTH, self.rect.height + 6)
        knob.center = (x, self.rect.centery)
        pygame.draw.rect(target, PALETTE["lamp" if active else "bone"], knob)
        pygame.draw.rect(target, PALETTE["ink"], knob, 1)
