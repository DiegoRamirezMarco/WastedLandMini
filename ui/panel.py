"""Backing for HUD elements: panels, the backs of buttons and bars.

Each is drawn flat on whatever it is asked for on. Where the game has a skin, the skin is offered
it first, and may dress it in something finer.
"""

from typing import Protocol

import pygame

from graphics.palette import PALETTE, Color


class Skin(Protocol):
    """What dresses the interface in place of flat colour. Each says whether it did."""

    def panel(
        self, target: pygame.Surface, rect: pygame.Rect, fill: str, border: str, band: int, band_color: Color | None
    ) -> bool: ...

    def button(self, target: pygame.Surface, rect: pygame.Rect, active: bool) -> bool: ...

    def bar(self, target: pygame.Surface, rect: pygame.Rect, share: float, color: str) -> bool: ...


_skin: Skin | None = None


def set_skin(skin: Skin | None) -> None:
    """Have panels, buttons and bars offered to a skin before they are drawn flat. None takes it off."""
    global _skin
    _skin = skin


def draw_panel(
    target: pygame.Surface,
    rect: pygame.Rect,
    fill: str = "ink",
    border: str = "iron",
    band: int = 0,
    band_color: Color | None = None,
) -> None:
    """A panel. `band` is how tall a band across its top is, for a heading, where the skin draws one."""
    if _skin is not None and _skin.panel(target, rect, fill, border, band, band_color):
        return
    pygame.draw.rect(target, PALETTE[fill], rect)
    pygame.draw.rect(target, PALETTE[border], rect, 1)


def draw_button(target: pygame.Surface, rect: pygame.Rect, active: bool = False) -> None:
    """The back of a button, lit while what it stands for is on."""
    if _skin is not None and _skin.button(target, rect, active):
        return
    pygame.draw.rect(target, PALETTE["lamp" if active else "shadow"], rect)
    pygame.draw.rect(target, PALETTE["iron"], rect, 1)


def draw_bar(target: pygame.Surface, rect: pygame.Rect, share: float, color: str) -> None:
    """A measure from nothing to full: that share of the bar, from 0 to 1, in a colour of the palette."""
    share = max(0.0, min(1.0, share))
    if _skin is not None and _skin.bar(target, rect, share, color):
        return
    pygame.draw.rect(target, PALETTE["shadow"], rect)
    filled = round(rect.width * share)
    if filled:
        pygame.draw.rect(target, PALETTE[color], (rect.x, rect.y, filled, rect.height))
