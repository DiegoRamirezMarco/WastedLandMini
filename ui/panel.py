"""Flat rectangular backing for HUD elements."""

from collections.abc import Callable

import pygame

from graphics.palette import PALETTE

Skin = Callable[[pygame.Surface, pygame.Rect], bool]
# What dresses a panel in place of a flat fill, when the game has a skin for it. It says whether it did.
_skin: Skin | None = None


def set_skin(skin: Skin | None) -> None:
    """Have panels offered to a skin before they are drawn flat. None takes it off."""
    global _skin
    _skin = skin


def draw_panel(
    target: pygame.Surface, rect: pygame.Rect, fill: str = "ink", border: str = "iron"
) -> None:
    if _skin is not None and _skin(target, rect):
        return
    pygame.draw.rect(target, PALETTE[fill], rect)
    pygame.draw.rect(target, PALETTE[border], rect, 1)
