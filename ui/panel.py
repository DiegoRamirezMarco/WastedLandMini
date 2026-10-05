"""Flat rectangular backing for HUD elements."""

import pygame

from graphics.palette import PALETTE


def draw_panel(
    target: pygame.Surface, rect: pygame.Rect, fill: str = "ink", border: str = "iron"
) -> None:
    pygame.draw.rect(target, PALETTE[fill], rect)
    pygame.draw.rect(target, PALETTE[border], rect, 1)
