"""The step of the opening a new settlement is on: what to do next, over the map and inside the editors."""

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
DRAW_INTENT = ("tutorial_draw",)
# What a step is about, when it is about a screen of its own.
CREATOR_FOCUS = "creator"
DOLL_FOCUS = "doll"
BUILDING_ART_FOCUS = "building_art"
# What the player does with their own hands that the opening waits for, by the names the editors give it.
COLOR_DEED, STROKE_DEED, FILL_DEED, UNDO_DEED = "color", "stroke", "fill", "undo"
PART_DEED = "part"
MEASURE_DEED = "measure"
RESIDENT_DRAWN_DEED = "save_resident"
BUILDING_DRAWN_DEED = "save_building"
OBJECT_DRAWN_PREFIX = "draw:"
CREATOR_LABEL = "Crear habitante"
ACKNOWLEDGE_LABEL = "Entendido"
DRAW_LABEL = "Dibujar"
OWED_DRAWING = "Ya está puesto. Falta dibujarlo."
BLINK_SECONDS = 0.5


def object_drawn_deed(kind: str) -> str:
    return f"{OBJECT_DRAWN_PREFIX}{kind}"


def owed_object(world: SimulationWorld) -> str | None:
    """Kind of the object that stands already and that the step in hand still wants drawn, if any."""
    owed = world.guide.owed(world)
    return owed.removeprefix(OBJECT_DRAWN_PREFIX) if owed is not None and owed.startswith(OBJECT_DRAWN_PREFIX) else None


def lit(seconds: float) -> bool:
    """The half of a blink in which whatever the opening points at stands out."""
    return seconds % (BLINK_SECONDS * 2) < BLINK_SECONDS


def tutorial_heading(world: SimulationWorld, step: TutorialStep) -> str:
    number, total = world.guide.progress(world)
    return f"{number}/{total} · {step.title}"


def tutorial_action(world: SimulationWorld, step: TutorialStep) -> tuple[str, Hashable] | None:
    """The button a step comes with over the map, as a label and an intent: only steps that are
    done on another screen, or by saying so, have one."""
    if step.focus == CREATOR_FOCUS:
        return (CREATOR_LABEL, CREATOR_INTENT)
    if step.focus in (DOLL_FOCUS, BUILDING_ART_FOCUS) or owed_object(world) is not None:
        return (DRAW_LABEL, DRAW_INTENT)
    if step.goal.kind == ACKNOWLEDGED:
        return (ACKNOWLEDGE_LABEL, ACKNOWLEDGE_INTENT)
    return None


def _lines(font: BitmapFont, world: SimulationWorld, step: TutorialStep, width: int) -> list[tuple[str, str]]:
    """The text of a step as lines and the colour of each, with what is still owed said last."""
    lines = [(line, "paper") for line in font.wrap(step.text, width)]
    if owed_object(world) is not None:
        lines += [(line, "glow") for line in font.wrap(OWED_DRAWING, width)]
    return lines


def tutorial_height(font: BitmapFont, world: SimulationWorld, width: int = PANEL_WIDTH) -> int:
    """How tall the panel has to be for the step the settlement is on. 0 with no step."""
    step = world.guide.current(world)
    if step is None:
        return 0
    lines = len(_lines(font, world, step, width - PADDING * 2))
    button = BUTTON_HEIGHT + 3 if tutorial_action(world, step) is not None else 0
    return PADDING * 2 + LINE_HEIGHT * (lines + 1) + 2 + button


def tutorial_button(font: BitmapFont, rect: pygame.Rect, world: SimulationWorld) -> Button | None:
    step = world.guide.current(world)
    action = tutorial_action(world, step) if step is not None else None
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
    for line, color in _lines(font, world, step, rect.width - PADDING * 2):
        font.draw(target, line, (x, y), PALETTE[color])
        y += LINE_HEIGHT
    button = tutorial_button(font, rect, world)
    if button is not None:
        button.draw(target, font, active=lit)


def lesson_for(world: SimulationWorld, focus: str | None = None, deed: str | None = None) -> TutorialStep | None:
    """The step in hand, if it is one for the editor that asks: the one a step is about, or the one
    where what the step still wants done is done."""
    step = world.guide.current(world)
    if step is None:
        return None
    if focus is not None and step.focus == focus:
        return step
    return step if deed is not None and step.goal.needed_deed == deed else None


def draw_lesson(target: pygame.Surface, font: BitmapFont, rect: pygame.Rect, world: SimulationWorld, step: TutorialStep) -> None:
    """Inside an editor, the step in hand where the editor's own notes go."""
    draw_panel(target, rect, border="lamp")
    x, y = rect.x + PADDING, rect.y + PADDING
    width = rect.width - PADDING * 2
    for line in font.wrap(tutorial_heading(world, step), width):
        font.draw(target, line, (x, y), PALETTE["lamp"])
        y += LINE_HEIGHT
    y += 2
    for line in font.wrap(step.text, width):
        if y + LINE_HEIGHT > rect.bottom - PADDING:
            break
        font.draw(target, line, (x, y), PALETTE["paper"])
        y += LINE_HEIGHT


def draw_hint(target: pygame.Surface, rect: pygame.Rect | None, seconds: float) -> None:
    """Make what a lesson is about stand out, on and off."""
    if rect is not None and lit(seconds):
        pygame.draw.rect(target, PALETTE["glow"], rect.inflate(4, 4), 1)
