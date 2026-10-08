"""The settlement's coin as it is shown: as somebody drew it, or else as the game does.

A currency is made by the player, who names it and draws it. Until it is drawn it wears the
game's own coin. A drawing is kept by the ID of its currency, so that one made after another is
drawn anew.
"""

import pygame

from graphics import ui_art
from graphics.illustrations import Illustrations
from graphics.palette import PALETTE

COINS_FOLDER = "coins"
# The paper a coin is drawn on. It is shown far smaller: in the bar, a few pixels across.
COIN_PAPER = (96, 96)
GLYPH = "coin"
RIM = (*PALETTE["ember"], 255)

Size = tuple[int, int]


def coin_path(currency_id: str) -> str:
    return f"{COINS_FOLDER}/{currency_id}.png"


class CoinArt:
    """Finds the drawing of a currency, and gives the editor what it draws over."""

    def __init__(self, illustrations: Illustrations | None) -> None:
        self.illustrations = illustrations if illustrations is not None and illustrations.root is not None else None
        self._made: dict[int, pygame.Surface] = {}

    @property
    def available(self) -> bool:
        """Whether there is anywhere to keep drawings."""
        return self.illustrations is not None

    def drawing(self, currency_id: str) -> pygame.Surface | None:
        """What somebody has drawn for a currency, at the size it is drawn at. None if nobody has."""
        if self.illustrations is None:
            return None
        return self.illustrations.fitted(coin_path(currency_id), COIN_PAPER)

    def shown(self, currency_id: str | None, side: int) -> pygame.Surface:
        """A currency's coin at a size in pixels: as it was drawn, or else the game's own."""
        if self.illustrations is not None and currency_id:
            own = self.illustrations.fitted(coin_path(currency_id), (side, side))
            if own is not None:
                return own
        if side not in self._made:
            self._made[side] = ui_art.icon(GLYPH, side)
        return self._made[side]

    def starter(self) -> pygame.Surface:
        """The game's own coin on the paper, to be drawn over."""
        return ui_art.icon(GLYPH, COIN_PAPER[0])

    def guide(self) -> pygame.Surface:
        """What is traced over: how much of the paper a coin fills, and the game's own as an example."""
        guide = self.starter()
        pygame.draw.circle(guide, RIM, (COIN_PAPER[0] // 2, COIN_PAPER[1] // 2), COIN_PAPER[0] // 2 - 4, 1)
        return guide

    def forget(self, currency_id: str) -> None:
        """Have a currency's drawing read again, as after it has been drawn anew."""
        if self.illustrations is not None:
            self.illustrations.forget(coin_path(currency_id))
