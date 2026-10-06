"""Rows of buttons, one row to each kind of manner. It reports what was picked; whose it is is up to the scene."""

from collections.abc import Mapping

import pygame

from graphics.font import LINE_HEIGHT, BitmapFont
from graphics.palette import PALETTE
from simulation.residents.manner import MannerKind, MannerSettings
from ui.button import Button

ROW = 26
# Room for what a kind is called, to the left of the ways there are of it.
LABEL_WIDTH = 60
PICK = "manner"


def pick_intent(kind_id: str, manner_id: str) -> tuple[str, str, str]:
    return (PICK, kind_id, manner_id)


class MannerPicker:
    def __init__(self, font: BitmapFont, manners: MannerSettings, left: int, top: int, width: int) -> None:
        self.font = font
        self.manners = manners
        self.left = left
        self.width = width
        # A row to each kind that has ways to choose from: the kind, how far down it is, and its buttons.
        self.rows: list[tuple[MannerKind, int, list[Button]]] = []
        y = top
        for kind in manners.kinds.values():
            buttons, x = [], left + LABEL_WIDTH
            for manner in manners.of_kind(kind.kind_id):
                button = Button.at(font, x, y, manner.name, pick_intent(kind.kind_id, manner.manner_id))
                buttons.append(button)
                x = button.rect.right + 3
            if buttons:
                self.rows.append((kind, y, buttons))
                y += ROW
        self.bottom = y

    @property
    def buttons(self) -> list[Button]:
        return [button for _, _, buttons in self.rows for button in buttons]

    def picked(self, position: tuple[int, int]) -> tuple[str, str] | None:
        """The kind and the manner of the button at a position on the canvas, if there is one there."""
        intent = next((button.intent for button in self.buttons if button.contains(position)), None)
        return (intent[1], intent[2]) if intent is not None else None

    def draw(self, target: pygame.Surface, chosen: Mapping[str, str], shown: str | None = None) -> None:
        """Draw the rows with the manner in `chosen` lit in each, by kind. `shown` is the kind being tried out."""
        font = self.font
        for kind, y, buttons in self.rows:
            trying = kind.kind_id == shown
            if trying:
                font.draw(target, ">", (self.left - 8, y + 1), PALETTE["lamp"])
            font.draw(target, kind.name, (self.left, y + 1), PALETTE["lamp" if trying else "sand"])
            for button in buttons:
                button.draw(target, font, active=button.intent[2] == chosen.get(kind.kind_id))

    def describe(self, target: pygame.Surface, manner_id: str | None, top: int | None = None) -> None:
        """Say under the rows what a manner is like."""
        manner = self.manners.manners.get(manner_id or "")
        if manner is None:
            return
        y = self.bottom + 2 if top is None else top
        for line in self.font.wrap(f"{manner.name}: {manner.description}", self.width):
            self.font.draw(target, line, (self.left, y), PALETTE["bone"])
            y += LINE_HEIGHT
