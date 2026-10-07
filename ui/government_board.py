"""Panel on how the settlement is governed: its kind, who holds its seats, how things stand, the
laws in force, and the kinds there are to choose from."""

from dataclasses import dataclass

import pygame

from graphics.font import LINE_HEIGHT, BitmapFont
from graphics.palette import PALETTE, Color
from simulation.politics.government import COUNCIL, EVERYONE, LEADER, NOBODY, SECRET, GovernmentDefinition
from simulation.world import SimulationWorld
from ui.button import HEIGHT as BUTTON_HEIGHT
from ui.button import Button
from ui.panel import draw_bar, draw_panel

PANEL_WIDTH = 330
PADDING = 6
# The band its title sits on, and the room under it.
BAND = LINE_HEIGHT + PADDING + 1
ROW_HEIGHT = LINE_HEIGHT * 2 + 2
TITLE = "Gobierno"
CHOOSE_LABEL = "Elegir"
CONFIRM_LABEL = "Confirmar"
IN_FORCE = "En vigor"
KINDS_TITLE = "Maneras de gobernarse"
TOO_FEW = "Sin gobierno. Aún son pocos para tener que gobernarse: hacen falta {count}."
CHOOSING = "Sin gobierno. Lo están hablando: si no eliges tú, lo deciden ellos en {hours} h."
NO_LAWS = "Ninguna ley en vigor."
FOUNDING_HINT = "Lo que elijas nace con la legitimidad de cuantos lo querían."
CHANGING_HINT = "Cambiarlo sacude el asentamiento: baja la estabilidad y quien mandaba deja el puesto."
# The measures of a settlement, in the order they are shown, with the colour of each.
MEASURES = (
    ("legitimacy", "Legitimidad", "lichen"),
    ("public_support", "Apoyo", "mist"),
    ("stability", "Estabilidad", "lamp"),
    ("fear", "Miedo", "plum"),
    ("unrest", "Malestar", "ember"),
    ("authoritarianism", "Mano dura", "copper"),
    ("corruption", "Corrupción", "ochre"),
)
BAR_COLUMNS = 2
BAR_HEIGHT = 6
BAR_LABEL = 62
# How the next to lead comes to it, by the first way a kind of government goes by.
WAYS = {
    "election": "se elige entre todos",
    "council": "lo nombra el consejo",
    "strongest": "manda quien más puede",
    "heir": "deja dicho quién le sigue",
    "following": "manda a quien sigue la gente",
}


def choose_intent(government_id: str) -> tuple[str, str]:
    return ("choose_government", government_id)


def describe_kind(world: SimulationWorld, definition: GovernmentDefinition) -> str:
    """How a kind of government works, in a line, from what its data says."""
    roles = world.registries.politics.roles
    parts = []
    if definition.approves == LEADER and definition.leader_role in roles:
        parts.append(f"Decide quien sea {roles[definition.leader_role].name}")
    elif definition.approves == COUNCIL:
        parts.append(f"Decide un consejo de {definition.council_seats}")
    elif definition.approves == EVERYONE:
        share = round(definition.approval * 100)
        parts.append("Deciden todos" if share <= 50 else f"Deciden todos, con el {share}% a favor")
    if definition.succession:
        parts.append(WAYS.get(definition.succession[0], definition.succession[0]))
    if definition.votes != NOBODY:
        parts.append("voto secreto" if definition.ballot == SECRET else "a mano alzada")
    if definition.term_days:
        parts.append(f"cada {definition.term_days} días")
    return " · ".join(parts)


def status_lines(world: SimulationWorld) -> list[tuple[str, str]]:
    """How the settlement is governed right now and who holds its seats, as lines and the colour of each."""
    state, settings = world.government, world.registries.politics
    definition = world.politics.leadership.definition(world)
    if definition is None:
        if state.choosing_until is None:
            return [(TOO_FEW.format(count=settings.founding_residents), "dust")]
        hours = max(1, -(-(state.choosing_until - world.clock.total_minutes) // 60))
        return [(CHOOSING.format(hours=hours), "lamp")]
    lines = [(f"{definition.name}, desde el día {state.chosen_on}", "paper")]
    leadership = world.politics.leadership
    if definition.leader_role is not None:
        leader = world.politics.leader(world)
        role = leadership.role_name(world, definition.leader_role, leader)
        if leader is not None:
            lines.append((f"{role.capitalize()}: {leader.name}", "bone"))
        else:
            lines.append((f"Nadie ocupa el puesto de {role}", "ember"))
    if definition.council_role is not None:
        names = [world.residents[member].name for member in state.council if member in world.residents]
        empty = definition.council_seats - len(names)
        seats = ", ".join(names) if names else "nadie"
        lines.append((f"Consejo: {seats}" + (f" ({empty} sin ocupar)" if empty > 0 else ""), "bone"))
    if state.election_at is not None:
        hours = max(1, -(-(state.election_at - world.clock.total_minutes) // 60))
        lines.append((f"Hay votación convocada: en {hours} h", "lamp"))
    return lines


def law_lines(font: BitmapFont, world: SimulationWorld, width: int) -> list[str]:
    """The laws in force, by name, in as many lines as it takes."""
    names = []
    for law_id in world.government.laws:
        definition = world.politics.laws.definition(world, law_id)
        names.append(definition.name if definition is not None else law_id)
    return font.wrap(f"Leyes en vigor: {', '.join(names)}", width) if names else [NO_LAWS]


@dataclass(frozen=True)
class Parts:
    """Where each part of the board starts, from the top of it down."""

    status: int
    bars: int
    laws: int
    kinds: int
    hint: int
    bottom: int


def _parts(font: BitmapFont, world: SimulationWorld) -> Parts:
    width = PANEL_WIDTH - PADDING * 2
    status = BAND + 3
    lines = sum(len(font.wrap(text, width)) for text, _ in status_lines(world))
    bars = status + lines * LINE_HEIGHT + 3
    governed = world.government.kind is not None
    rows = -(-len(MEASURES) // BAR_COLUMNS) if governed else 0
    laws = bars + rows * LINE_HEIGHT + (3 if governed else 0)
    kinds = laws + (len(law_lines(font, world, width)) * LINE_HEIGHT + 4 if governed else 0)
    hint = kinds + LINE_HEIGHT + 1 + ROW_HEIGHT * len(world.registries.politics.governments) + 2
    return Parts(status, bars, laws, kinds, hint, hint + LINE_HEIGHT * 2 + PADDING)


def government_board_height(font: BitmapFont, world: SimulationWorld) -> int:
    return _parts(font, world).bottom


def can_choose(world: SimulationWorld) -> bool:
    """Whether there is anything for the player to choose: a settlement choosing, or one with a government."""
    state = world.government
    return state.kind is not None or state.choosing_until is not None


def choose_buttons(font: BitmapFont, rect: pygame.Rect, world: SimulationWorld, armed: str | None) -> list[Button]:
    """A button beside each kind the settlement could be given. The one in hand asks to be pressed again."""
    if not can_choose(world):
        return []
    buttons = []
    parts = _parts(font, world)
    y = rect.y + parts.kinds + LINE_HEIGHT + 1
    for government_id in world.registries.politics.governments:
        if government_id != world.government.kind:
            label = CONFIRM_LABEL if government_id == armed else CHOOSE_LABEL
            button = Button.at(font, 0, y + (ROW_HEIGHT - BUTTON_HEIGHT) // 2, label, choose_intent(government_id))
            button.rect.right = rect.right - PADDING
            buttons.append(button)
        y += ROW_HEIGHT
    return [button for button in buttons if button.rect.bottom <= rect.bottom - PADDING]


def draw_government_board(
    target: pygame.Surface,
    font: BitmapFont,
    rect: pygame.Rect,
    world: SimulationWorld,
    armed: str | None = None,
    band_color: Color | None = None,
) -> None:
    draw_panel(target, rect, band=BAND, band_color=band_color)
    x, width = rect.x + PADDING, rect.width - PADDING * 2
    font.draw(target, TITLE, (x, rect.y + PADDING - 1), PALETTE["paper"])
    parts = _parts(font, world)
    floor = rect.bottom - PADDING

    y = rect.y + parts.status
    for text, color in status_lines(world):
        for line in font.wrap(text, width):
            font.draw(target, line, (x, y), PALETTE[color])
            y += LINE_HEIGHT

    state = world.government
    if state.kind is not None:
        column = width // BAR_COLUMNS
        for index, (measure, label, color) in enumerate(MEASURES):
            left = x + (index % BAR_COLUMNS) * column
            top = rect.y + parts.bars + (index // BAR_COLUMNS) * LINE_HEIGHT
            font.draw(target, label, (left, top), PALETTE["bone"])
            track = pygame.Rect(left + BAR_LABEL, top + 3, column - BAR_LABEL - 8, BAR_HEIGHT)
            draw_bar(target, track, state.measures.get(measure, 0.0) / 100.0, color)
        y = rect.y + parts.laws
        for line in law_lines(font, world, width):
            font.draw(target, line, (x, y), PALETTE["sand"])
            y += LINE_HEIGHT

    y = rect.y + parts.kinds
    font.draw(target, KINDS_TITLE, (x, y), PALETTE["lamp"])
    y += LINE_HEIGHT + 1
    buttons = {button.intent: button for button in choose_buttons(font, rect, world, armed)}
    for government_id, definition in world.registries.politics.governments.items():
        if y + ROW_HEIGHT > floor:
            break
        current = government_id == state.kind
        button = buttons.get(choose_intent(government_id))
        mark_width = font.width(IN_FORCE) if current else 0
        right = button.rect.left - 4 if button is not None else rect.right - PADDING - mark_width - (4 if current else 0)
        font.draw(target, font.truncate(definition.name, right - x), (x, y), PALETTE["glow" if current else "paper"])
        note = font.truncate(describe_kind(world, definition), right - x)
        font.draw(target, note, (x, y + LINE_HEIGHT), PALETTE["dust" if current else "stone"])
        if button is not None:
            button.draw(target, font, active=government_id == armed)
        elif current:
            font.draw(target, IN_FORCE, (rect.right - PADDING - mark_width, y + LINE_HEIGHT // 2), PALETTE["lamp"])
        y += ROW_HEIGHT

    if can_choose(world) and rect.y + parts.hint + LINE_HEIGHT <= floor:
        hint = CHANGING_HINT if state.kind is not None else FOUNDING_HINT
        y = rect.y + parts.hint
        for line in font.wrap(hint, width)[:2]:
            if y + LINE_HEIGHT > rect.bottom - 2:
                break
            font.draw(target, line, (x, y), PALETTE["glow" if armed is not None else "dust"])
            y += LINE_HEIGHT
