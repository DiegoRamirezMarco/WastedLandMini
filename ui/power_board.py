"""The board of current (P60): what gives it, what draws it, and a switch to each thing that
runs on it.

It reads the simulation and changes nothing: a switch pressed is an intent for the scene.
"""

from dataclasses import dataclass

import pygame

from graphics.font import LINE_HEIGHT, BitmapFont
from graphics.palette import PALETTE
from graphics.ui_art import band_hue
from simulation.world import SimulationWorld
from ui.button import HEIGHT as BUTTON_HEIGHT
from ui.button import Button
from ui.panel import draw_panel

PANEL_WIDTH = 380
PADDING = 5
ROW_HEIGHT = BUTTON_HEIGHT + 2
POWER_INTENT = ("power",)
TITLE = "Corriente: lo que da el generador y lo que se le pide"
NO_GENERATOR = "No hay generador: nada que vaya con corriente funciona."
NO_FUEL = "El generador no tiene combustible: todo está parado."
NOTHING_DRAWS = "No hay nada que vaya con corriente."
FOOTER = "Si no hay para todo, se apaga lo último que se encendió."
ON_LABEL, OFF_LABEL = "Encender", "Apagar"
# How a thing that runs on current stands, and what is said of each.
RUNNING, SWITCHED_OFF, STARVED = "running", "off", "starved"
STATE_WORDS = {RUNNING: ("Encendido", "lichen"), SWITCHED_OFF: ("Apagado", "stone"), STARVED: ("Sin corriente", "ember")}
OUTSIDE = "fuera"
BESIDE = "junto a {name}"
# How many tiles from a building a thing in the open is still said to be beside it.
NEAR_TILES = 6


def switch_intent(object_id: str, on: bool) -> tuple[str, str, bool]:
    return ("switch", object_id, on)


@dataclass(frozen=True)
class PowerRow:
    """One thing that runs on current, as the board lists it."""

    object_id: str
    name: str
    draws: int
    state: str
    on: bool


def power_state(world: SimulationWorld, object_id: str, enough: bool | None = None) -> str | None:
    """How a thing that runs on current stands: running, switched off, or on with no current
    for it. None for what draws none. `enough` is whether there is current for everything
    that is on, where whoever asks has worked it out already."""
    placed = world.interactables.get(object_id)
    if placed is None or world.power.draws(world, placed) <= 0:
        return None
    if not placed.on:
        return SWITCHED_OFF
    if enough is None:
        enough = world.power.enough(world)
    return RUNNING if enough else STARVED


def where(world: SimulationWorld, object_id: str) -> str:
    """The name of the place a thing stands in, or of the one it stands beside in the open."""
    placed = world.interactables.get(object_id)
    if placed is None:
        return OUTSIDE
    room = world.room_at((placed.x, placed.y))
    if room is not None:
        return room.name

    def away(each) -> int:
        across = max(each.x - placed.x, 0, placed.x - (each.x + each.width - 1))
        down = max(each.y - placed.y, 0, placed.y - (each.y + each.height - 1))
        return across + down

    nearest = min(world.rooms.values(), key=lambda each: (away(each), each.room_id), default=None)
    if nearest is None or away(nearest) > NEAR_TILES:
        return OUTSIDE
    return BESIDE.format(name=nearest.name)


def power_rows(world: SimulationWorld) -> list[PowerRow]:
    """Everything that runs on current, in map order."""
    enough = world.power.enough(world)
    rows = []
    for object_id, placed in world.interactables.items():
        draws = world.power.draws(world, placed)
        if draws <= 0:
            continue
        name = f"{world.definition_of(placed).name.capitalize()} ({where(world, object_id)})"
        rows.append(PowerRow(object_id, name, draws, power_state(world, object_id, enough) or SWITCHED_OFF, placed.on))
    return rows


def summary(world: SimulationWorld) -> tuple[str, str]:
    """What there is and what is asked for, in a line, and the colour it is said in."""
    power = world.power
    if not power.generators(world):
        return NO_GENERATOR, "ember"
    fuel = power.fuel(world)
    if fuel <= 0:
        return NO_FUEL, "ember"
    supply, demand = power.supply(world), power.demand(world)
    return f"Da {supply} · se piden {demand} · combustible: {fuel}", "paper" if demand <= supply else "ember"


def power_board_height(world: SimulationWorld) -> int:
    rows = max(1, len(power_rows(world)))
    return PADDING * 2 + LINE_HEIGHT * 3 + 4 + ROW_HEIGHT * rows


def _rows_top(rect: pygame.Rect) -> int:
    return rect.y + PADDING + LINE_HEIGHT * 2 + 4


def power_buttons(font: BitmapFont, rect: pygame.Rect, world: SimulationWorld) -> list[Button]:
    """A switch at the end of the row of each thing that runs on current."""
    buttons = []
    y = _rows_top(rect)
    for row in power_rows(world):
        button = Button.at(font, 0, y + 1, OFF_LABEL if row.on else ON_LABEL, switch_intent(row.object_id, not row.on))
        button.rect.right = rect.right - PADDING
        buttons.append(button)
        y += ROW_HEIGHT
    return [button for button in buttons if button.rect.bottom <= rect.bottom - PADDING - LINE_HEIGHT]


def draw_power_board(target: pygame.Surface, font: BitmapFont, rect: pygame.Rect, world: SimulationWorld) -> None:
    draw_panel(target, rect, band=PADDING + LINE_HEIGHT, band_color=band_hue("energy"))
    x, y = rect.x + PADDING, rect.y + PADDING
    width = rect.width - PADDING * 2
    font.draw(target, font.truncate(TITLE, width), (x, y), PALETTE["paper"])
    y += LINE_HEIGHT + 2
    text, color = summary(world)
    font.draw(target, font.truncate(text, width), (x, y), PALETTE[color])
    y = _rows_top(rect)
    rows = power_rows(world)
    buttons = {button.intent[1]: button for button in power_buttons(font, rect, world)}
    if not rows:
        font.draw(target, NOTHING_DRAWS, (x, y + 2), PALETTE["stone"])
    for row in rows:
        button = buttons.get(row.object_id)
        if button is None:
            break
        word, color = STATE_WORDS[row.state]
        said = f"gasta {row.draws} · {word}"
        right = button.rect.left - 6
        font.draw(target, said, (right - font.width(said), y + 2), PALETTE[color])
        room = right - font.width(said) - 6 - x
        font.draw(target, font.truncate(row.name, room), (x, y + 2), PALETTE["bone" if row.on else "stone"])
        # A switch that is pressed in is one that is on.
        button.draw(target, font, active=False)
        y += ROW_HEIGHT
    font.draw(target, font.truncate(FOOTER, width), (x, rect.bottom - PADDING - LINE_HEIGHT + 1), PALETTE["dust"])
