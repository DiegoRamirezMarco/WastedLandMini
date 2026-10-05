"""The step of the opening a new settlement is on: what to do next, in a panel over the map."""

from collections.abc import Hashable

import pygame

from graphics.font import LINE_HEIGHT, BitmapFont
from graphics.palette import PALETTE
from simulation.tutorial.tutorial import ACKNOWLEDGED, TutorialStep
from simulation.world import SimulationWorld
from ui.button import HEIGHT as BUTTON_HEIGHT
from ui.button import Button
from ui.panel import draw_panel

PANEL_WIDTH = 272
PADDING = 5
CREATOR_INTENT = ("tutorial_creator",)
ACKNOWLEDGE_INTENT = ("tutorial_acknowledge",)
# What a step is about, when it is about the screen where the first resident is made.
CREATOR_FOCUS = "creator"
CREATOR_LABEL = "Crear habitante"
ACKNOWLEDGE_LABEL = "Entendido"


def tutorial_heading(world: SimulationWorld, step: TutorialStep) -> str:
    number, total = world.guide.progress(world)
    return f"{number}/{total} · {step.title}"


def tutorial_action(step: TutorialStep) -> tuple[str, Hashable] | None:
    """The button a step comes with, as a label and an intent: only steps the map cannot answer have one."""
    if step.focus == CREATOR_FOCUS:
        return (CREATOR_LABEL, CREATOR_INTENT)
    if step.goal.kind == ACKNOWLEDGED:
        return (ACKNOWLEDGE_LABEL, ACKNOWLEDGE_INTENT)
    return None


def tutorial_height(font: BitmapFont, world: SimulationWorld, width: int = PANEL_WIDTH) -> int:
    """How tall the panel has to be for the step the settlement is on. 0 with no step."""
    step = world.guide.current(world)
    if step is None:
        return 0
    lines = len(font.wrap(step.text, width - PADDING * 2))
    button = BUTTON_HEIGHT + 3 if tutorial_action(step) is not None else 0
    return PADDING * 2 + LINE_HEIGHT * (lines + 1) + 2 + button


def tutorial_button(font: BitmapFont, rect: pygame.Rect, world: SimulationWorld) -> Button | None:
    step = world.guide.current(world)
    action = tutorial_action(step) if step is not None else None
    if action is None:
        return None
    label, intent = action
    button = Button.at(font, 0, 0, label, intent)
    button.rect.bottomright = (rect.right - PADDING, rect.bottom - PADDING)
    return button


def draw_tutorial(target: pygame.Surface, font: BitmapFont, rect: pygame.Rect, world: SimulationWorld, lit: bool) -> None:
    """Draw the step in `rect`. `lit` is the half of a blink in which its button stands out."""
    step = world.guide.current(world)
    if step is None:
        return
    draw_panel(target, rect, border="lamp")
    x, y = rect.x + PADDING, rect.y + PADDING
    font.draw(target, font.truncate(tutorial_heading(world, step), rect.width - PADDING * 2), (x, y), PALETTE["lamp"])
    y += LINE_HEIGHT + 2
    for line in font.wrap(step.text, rect.width - PADDING * 2):
        font.draw(target, line, (x, y), PALETTE["paper"])
        y += LINE_HEIGHT
    button = tutorial_button(font, rect, world)
    if button is not None:
        button.draw(target, font, active=lit)
