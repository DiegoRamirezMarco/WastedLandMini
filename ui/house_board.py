"""Panel on the building being looked at from inside: what it is called and for, what it is like
to live in, whether its door is locked, and whose it is."""

import pygame

from graphics.font import LINE_HEIGHT, BitmapFont
from graphics.palette import PALETTE, Color
from simulation.world import SimulationWorld
from ui.button import HEIGHT as BUTTON_HEIGHT
from ui.button import Button
from ui.panel import draw_bar, draw_panel

PANEL_WIDTH = 186
PADDING = 6
# The band its title sits on, and the room under it.
BAND = LINE_HEIGHT + PADDING + 1
ROW = BUTTON_HEIGHT + 2
OWNER_COLUMNS = 2
NAME_LABEL = "Nombre"
USE_LABEL = "Uso"
NO_USE = "sin decir"
LOCK_LABEL = "Echar llave"
UNLOCK_LABEL = "Quitar llave"
LOCKED = "Puerta: con llave"
OPEN = "Puerta: abierta"
EVERYBODYS = "Es de todos: entra quien quiera."
OWNERS_TITLE = "De quién es"
NOBODY_HERE = "No vive nadie en el asentamiento."
HOMELESS_NOTE = "* sin casa: duerme al raso"
NAMING_HINT = "Intro: vale · Esc: dejarlo"
NAME_LENGTH = 24
CARET = "_"
# What a building is like, in the order it is shown, with the colour of each.
MEASURES = (
    ("comfort", "Comodidad", "lichen"),
    ("warmth", "Calor", "ember"),
    ("light", "Luz", "lamp"),
    ("beauty", "Belleza", "plum"),
)
BAR_HEIGHT = 6
BAR_LABEL = 62
RENAME_INTENT = ("house_rename",)
USE_INTENT = ("house_use",)
LOCK_INTENT = ("house_lock",)


def owner_intent(resident_id: str) -> tuple[str, str]:
    return ("house_owner", resident_id)


def next_use(world: SimulationWorld, room_id: str) -> str:
    """The use that comes after the one a building has, going round them: nothing said comes last."""
    uses = [*world.registries.housing.uses, ""]
    current = world.homes.uses.get(room_id, "")
    return uses[(uses.index(current) + 1) % len(uses)] if current in uses else uses[0]


def beds_in(world: SimulationWorld, room_id: str) -> int:
    """How many there are to sleep in, in a building."""
    room = world.rooms[room_id]
    return sum(
        1
        for placed in world.interactables.values()
        if room.contains((placed.x, placed.y))
        and (use := world.definition_of(placed).use) is not None
        and use.unaware
        and use.per_minute.get("tiredness", 0.0) < 0
    )


def homeless(world: SimulationWorld) -> set[str]:
    """Whoever has no house of their own, nor lives in that of somebody of theirs."""
    housing = world.housing
    housed = set()
    for room_id in world.homes.owners:
        room = world.rooms.get(room_id)
        if room is None:
            continue
        housed.update(resident_id for resident_id, resident in world.residents.items() if housing.lives_in(world, resident, room))
    return set(world.residents) - housed


def _owners_top(naming: bool) -> int:
    top = BAND + 3 + ROW * 2 + (LINE_HEIGHT if naming else 0) + 2
    top += len(MEASURES) * LINE_HEIGHT + 4
    return top + ROW + LINE_HEIGHT + 2


def house_board_height(world: SimulationWorld, naming: bool = False) -> int:
    rows = max(1, -(-len(world.residents) // OWNER_COLUMNS))
    return _owners_top(naming) + LINE_HEIGHT + 2 + rows * ROW + LINE_HEIGHT + PADDING


def house_buttons(font: BitmapFont, rect: pygame.Rect, world: SimulationWorld, room_id: str, naming: bool = False) -> list[Button]:
    """What can be pressed on the board: to name the building, say what it is for, lock it, and say who has it."""
    x, right = rect.x + PADDING, rect.right - PADDING
    y = rect.y + BAND + 3
    rename = Button.at(font, 0, y, NAME_LABEL, RENAME_INTENT)
    rename.rect.right = right
    y += ROW + (LINE_HEIGHT if naming else 0)
    use = Button.at(font, 0, y, USE_LABEL, USE_INTENT)
    use.rect.right = right
    buttons = [rename, use]
    y += ROW + 2 + len(MEASURES) * LINE_HEIGHT + 4
    if world.housing.owners(world, room_id):
        locked = room_id in world.homes.locked
        lock = Button.at(font, 0, y, UNLOCK_LABEL if locked else LOCK_LABEL, LOCK_INTENT)
        lock.rect.right = right
        buttons.append(lock)
    y = rect.y + _owners_top(naming) + LINE_HEIGHT + 2
    column = (rect.width - PADDING * 2) // OWNER_COLUMNS
    without = homeless(world)
    for index, (resident_id, resident) in enumerate(world.residents.items()):
        left = x + (index % OWNER_COLUMNS) * column
        top = y + (index // OWNER_COLUMNS) * ROW
        mark = " *" if resident_id in without else ""
        label = font.truncate(resident.name, column - 12 - font.width(mark)) + mark
        buttons.append(Button(pygame.Rect(left, top, column - 2, BUTTON_HEIGHT), label, owner_intent(resident_id)))
    return [button for button in buttons if button.rect.bottom <= rect.bottom - PADDING]


def draw_house_board(
    target: pygame.Surface,
    font: BitmapFont,
    rect: pygame.Rect,
    world: SimulationWorld,
    room_id: str,
    naming: str | None = None,
    band_color: Color | None = None,
) -> None:
    """Draw the board of a building. `naming` is the name being written for it, while one is."""
    room = world.rooms[room_id]
    housing = world.housing
    draw_panel(target, rect, band=BAND, band_color=band_color)
    x, width = rect.x + PADDING, rect.width - PADDING * 2
    writing = naming is not None
    buttons = {button.intent: button for button in house_buttons(font, rect, world, room_id, writing)}
    title = (naming + CARET) if writing else room.name.capitalize()
    font.draw(target, font.truncate(title, width), (x, rect.y + PADDING - 1), PALETTE["glow" if writing else "paper"])

    y = rect.y + BAND + 3
    owners = housing.owners(world, room_id)
    beds = beds_in(world, room_id)
    font.draw(target, f"Camas: {beds} · viven {len(owners)}", (x, y + 1), PALETTE["bone" if len(owners) <= beds else "ember"])
    y += ROW
    if writing:
        font.draw(target, NAMING_HINT, (x, y), PALETTE["dust"])
        y += LINE_HEIGHT
    use = housing.use_of(world, room_id) or NO_USE
    font.draw(target, font.truncate(f"{USE_LABEL}: {use}", width - font.width(USE_LABEL) - 14), (x, y + 1), PALETTE["bone"])
    y += ROW + 2

    qualities = housing.qualities(world, room)
    for measure, label, color in MEASURES:
        font.draw(target, label, (x, y), PALETTE["bone"])
        draw_bar(target, pygame.Rect(x + BAR_LABEL, y + 3, width - BAR_LABEL, BAR_HEIGHT), qualities[measure] / 100.0, color)
        y += LINE_HEIGHT
    y += 4

    if owners:
        locked = housing.locked(world, room)
        font.draw(target, LOCKED if locked else OPEN, (x, y + 1), PALETTE["lamp" if locked else "bone"])
    else:
        for index, line in enumerate(font.wrap(EVERYBODYS, width)[:2]):
            font.draw(target, line, (x, y + 1 + index * LINE_HEIGHT), PALETTE["dust"])

    y = rect.y + _owners_top(writing)
    font.draw(target, OWNERS_TITLE, (x, y), PALETTE["lamp"])
    if not world.residents:
        font.draw(target, NOBODY_HERE, (x, y + LINE_HEIGHT + 2), PALETTE["dust"])
    for intent, button in buttons.items():
        active = isinstance(intent, tuple) and intent[0] == "house_owner" and intent[1] in owners
        button.draw(target, font, active=active or (intent == RENAME_INTENT and writing))
    if homeless(world):
        note = rect.bottom - PADDING - LINE_HEIGHT + 2
        font.draw(target, font.truncate(HOMELESS_NOTE, width), (x, note), PALETTE["ember"])
