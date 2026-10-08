"""Panel for dressing the building being looked at from inside: what there is to put in it, as a
grid of pictures by kind, and what is in hand."""

from collections.abc import Callable
from dataclasses import dataclass

import pygame

from graphics.font import LINE_HEIGHT, BitmapFont
from graphics.palette import PALETTE, Color
from simulation.housing.decor import WALL
from simulation.housing.housing import QUALITIES
from simulation.work.construction import OBJECT_SITE
from simulation.world import SimulationWorld
from ui.button import HEIGHT as BUTTON_HEIGHT
from ui.button import Button
from ui.panel import draw_panel

PANEL_WIDTH = 186
PADDING = 6
BAND = LINE_HEIGHT + PADDING + 1
TITLE = "Decorar"
ORNAMENTS, FURNITURE, FLOORS, WALLS = "ornaments", "furniture", "floors", "walls"
TABS = ((ORNAMENTS, "Adorno"), (FURNITURE, "Mueble"), (FLOORS, "Suelo"), (WALLS, "Pared"))
COLUMNS = 4
TILE = 40
GAP = 2
# The side of the picture on a tile, with room left round it.
PICTURE = TILE - 8
ROWS = 6
REMOVE_LABEL = "Quitar"
DONE_LABEL = "Hecho"
AS_BUILT = "como estaba"
# The floor or the walls as the building was put up: the choice that takes the player's back.
AS_BUILT_ID = ""
REMOVE_INTENT = ("decor_remove",)
DONE_INTENT = ("decor_done",)
HINTS = {
    ORNAMENTS: "Elige uno y ponlo donde quieras: es gratis y al momento.",
    FURNITURE: "Un mueble se encarga: lo hace quien esté elegido, o quien viva aquí.",
    FLOORS: "El suelo cambia al momento.",
    WALLS: "Las paredes cambian al momento.",
}
REMOVING_HINT = "Pulsa un adorno para quitarlo. Los muebles se quitan en Urbanismo."
QUALITY_NAMES = {"comfort": "comodidad", "warmth": "calor", "light": "luz", "beauty": "belleza"}
FURNITURE_CATEGORY = "furniture"


@dataclass(frozen=True)
class DecorEntry:
    """One thing the board offers."""

    tab: str
    entry_id: str
    name: str
    # What there is to say of it under its name.
    note: str


def tab_intent(tab: str) -> tuple[str, str]:
    return ("decor_tab", tab)


def pick_intent(tab: str, entry_id: str) -> tuple[str, str, str]:
    return ("decor_pick", tab, entry_id)


def adds(world: SimulationWorld, kind: str) -> str:
    """What a thing adds to the building it is in, in words. Nothing if it adds nothing."""
    furnishing = world.registries.housing.furnishing.get(kind, {})
    return ", ".join(f"{amount:+.0f} {QUALITY_NAMES[quality]}" for quality in QUALITIES if (amount := furnishing.get(quality, 0.0)))


def _cost(world: SimulationWorld, kind: str) -> str:
    building = world.construction
    if not building.needs_building(world, OBJECT_SITE, kind):
        return "se pone al momento"
    rule = building.rule_for(world, OBJECT_SITE, kind)
    if rule is None:
        return ""
    items = world.registries.items
    parts = []
    for tag, units in rule.cost.items():
        material = next((items.get(item_id).name for item_id in items.ids() if tag in items.get(item_id).tags), tag)
        parts.append(f"{units} de {material}")
    if rule.minutes:
        parts.append(f"{rule.minutes} min")
    return ", ".join(parts)


def entries(world: SimulationWorld, tab: str) -> list[DecorEntry]:
    """What a tab of the board offers, in the order the data gives it."""
    decor = world.registries.decor
    if tab == ORNAMENTS:
        return [
            DecorEntry(tab, kind, definition.name, " · ".join(filter(None, ["en la pared" if definition.on == WALL else "en el suelo", adds(world, kind)])))
            for kind, definition in decor.ornaments.items()
        ]
    if tab == FURNITURE:
        kinds = world.registries.interactables
        return [
            DecorEntry(tab, kind, kinds.get(kind).name, " · ".join(filter(None, [_cost(world, kind), adds(world, kind)])))
            for kind in kinds.kinds()
            if kinds.get(kind).urbanism_category == FURNITURE_CATEGORY
            and world.construction.not_known(world, OBJECT_SITE, kind) is None
        ]
    names = decor.floors if tab == FLOORS else decor.walls
    return [
        DecorEntry(tab, AS_BUILT_ID, AS_BUILT, ""),
        *(DecorEntry(tab, entry_id, name, adds(world, entry_id)) for entry_id, name in names.items()),
    ]


def decor_board_height() -> int:
    return BAND + 3 + BUTTON_HEIGHT + 4 + ROWS * (TILE + GAP) + 2 + LINE_HEIGHT * 4 + 2 + BUTTON_HEIGHT + PADDING


def entry_cells(rect: pygame.Rect, world: SimulationWorld, tab: str) -> list[tuple[DecorEntry, pygame.Rect]]:
    """Where the tile of each thing on a tab is, for as many as there is room for."""
    left = rect.x + (rect.width - COLUMNS * (TILE + GAP) + GAP) // 2
    top = rect.y + BAND + 3 + BUTTON_HEIGHT + 4
    return [
        (entry, pygame.Rect(left + (index % COLUMNS) * (TILE + GAP), top + (index // COLUMNS) * (TILE + GAP), TILE, TILE))
        for index, entry in enumerate(entries(world, tab)[: COLUMNS * ROWS])
    ]


def decor_buttons(font: BitmapFont, rect: pygame.Rect) -> list[Button]:
    """The tabs across the top of the board, and under everything the way to take things away and the way out."""
    buttons = []
    x = rect.x + PADDING
    for tab, label in TABS:
        button = Button.at(font, x, rect.y + BAND + 3, label, tab_intent(tab))
        buttons.append(button)
        x = button.rect.right + 2
    foot = rect.bottom - PADDING - BUTTON_HEIGHT
    buttons.append(Button.at(font, rect.x + PADDING, foot, REMOVE_LABEL, REMOVE_INTENT))
    done = Button.at(font, 0, foot, DONE_LABEL, DONE_INTENT)
    done.rect.right = rect.right - PADDING
    buttons.append(done)
    return buttons


def decor_click(font: BitmapFont, rect: pygame.Rect, world: SimulationWorld, tab: str, position: tuple[int, int]):
    """What a press on the board asks for: a tab, a tool, or the thing on a tile. None for a press on nothing."""
    for button in decor_buttons(font, rect):
        if button.contains(position):
            return button.intent
    for entry, cell in entry_cells(rect, world, tab):
        if cell.collidepoint(position):
            return pick_intent(entry.tab, entry.entry_id)
    return None


def pointed_entry(rect: pygame.Rect, world: SimulationWorld, tab: str, position: tuple[int, int] | None) -> DecorEntry | None:
    if position is None:
        return None
    return next((entry for entry, cell in entry_cells(rect, world, tab) if cell.collidepoint(position)), None)


def draw_decor_board(
    target: pygame.Surface,
    font: BitmapFont,
    rect: pygame.Rect,
    world: SimulationWorld,
    tab: str,
    held: tuple[str, str] | None,
    removing: bool,
    pointer: tuple[int, int] | None,
    show: Callable[[DecorEntry, pygame.Rect], None],
    chosen: tuple[str, str] = ("", ""),
    band_color: Color | None = None,
) -> None:
    """Draw the board. `show` puts the picture of a thing on its tile; `held` is what is in hand,
    and `chosen` the floor and the walls the building has, which are lit on their tabs."""
    draw_panel(target, rect, band=BAND, band_color=band_color)
    x, width = rect.x + PADDING, rect.width - PADDING * 2
    font.draw(target, TITLE, (x, rect.y + PADDING - 1), PALETTE["paper"])
    for button in decor_buttons(font, rect):
        active = button.intent == tab_intent(tab) or (button.intent == REMOVE_INTENT and removing)
        button.draw(target, font, active=active)
    pointed = pointed_entry(rect, world, tab, pointer)
    lit = {FLOORS: chosen[0], WALLS: chosen[1]}
    for entry, cell in entry_cells(rect, world, tab):
        in_hand = held == (entry.tab, entry.entry_id) or (tab in lit and lit[tab] == entry.entry_id)
        border = "lamp" if in_hand else ("bone" if entry is pointed else "iron")
        draw_panel(target, cell, fill="shadow", border=border)
        show(entry, cell)
    y = rect.bottom - PADDING - BUTTON_HEIGHT - 2 - LINE_HEIGHT * 4
    named = pointed or next((entry for entry in entries(world, tab) if held == (entry.tab, entry.entry_id)), None)
    if removing and pointed is None:
        lines = font.wrap(REMOVING_HINT, width)
        color = "glow"
    elif named is not None:
        font.draw(target, font.truncate(named.name.capitalize(), width), (x, y), PALETTE["paper"])
        y += LINE_HEIGHT
        lines = font.wrap(named.note, width)[:3] if named.note else []
        color = "sand"
    else:
        lines = font.wrap(HINTS[tab], width)
        color = "dust"
    for line in lines[:4]:
        font.draw(target, line, (x, y), PALETTE[color])
        y += LINE_HEIGHT
