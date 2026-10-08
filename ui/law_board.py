"""The laws of the settlement, on the government's panel (P51): each law there is, how far it
goes, and the buttons that put one in force, change it or do away with it.

Laws are the player's to run (S45). How one comes in is the government's, and the panel says
which it is: in force at once where one person decides, or put to a vote. What waits to be
voted, and who is out in the square against what, is listed above the laws.
"""

import pygame

from graphics.font import LINE_HEIGHT, BitmapFont
from graphics.palette import PALETTE
from simulation.politics.government import LEADER
from simulation.politics.law import LawDefinition
from simulation.politics.proposal import ENACT_LAW, REPEAL_LAW
from simulation.world import SimulationWorld
from ui.button import HEIGHT as BUTTON_HEIGHT
from ui.button import Button

PADDING = 6
ROW_HEIGHT = BUTTON_HEIGHT + 2
# The tabs of the government's panel: how they are governed, and the laws there are, in two lots.
KINDS_TAB, LAWS_TAB, ODD_TAB = "kinds", "laws", "odd"
TABS = ((KINDS_TAB, "Gobierno"), (LAWS_TAB, "Leyes"), (ODD_TAB, "Leyes raras"))
LAW_TABS = (LAWS_TAB, ODD_TAB)
NAME_WIDTH = 98
DEGREE_WIDTH = 92
ENACT_LABEL = "Decretar"
VOTE_LABEL = "A votar"
CHANGE_LABEL = "Cambiar"
REPEAL_LABEL = "Quitar"
NO_GOVERNMENT = "Sin gobierno no hay a quién ponerle leyes."
AT_ONCE = "Aquí decide una sola persona: lo que decretes rige al momento, les guste o no."
BY_VOTE = "Aquí se vota: lo que pongas se habla {hours} h y rige solo si sale adelante."


def tab_intent(tab: str) -> tuple[str, str]:
    return ("government_tab", tab)


def degree_intent(law_id: str, step: int) -> tuple[str, str, int]:
    return ("law_degree", law_id, step)


def item_intent(law_id: str) -> tuple[str, str]:
    return ("law_item", law_id)


def enact_intent(law_id: str) -> tuple[str, str]:
    return ("law_enact", law_id)


def repeal_intent(law_id: str) -> tuple[str, str]:
    return ("law_repeal", law_id)


def decided_at_once(world: SimulationWorld) -> bool:
    """Whether a law the player puts is in force there and then, under the government in force."""
    definition = world.politics.leadership.definition(world)
    return definition is not None and definition.approves == LEADER and world.government.leader in world.residents


def laws_of(world: SimulationWorld, tab: str) -> list[LawDefinition]:
    """The laws a tab lists: the serious ones, or the odd ones."""
    odd = tab == ODD_TAB
    return [law for law in world.registries.laws.laws.values() if law.absurd == odd]


def named_items(world: SimulationWorld) -> list[str]:
    """What a law that names a food may name: every food the settlement keeps in common."""
    kept = world.registries.economy.kept_categories
    items = world.registries.items
    return [item_id for item_id in items.ids() if items.get(item_id).category in kept]


def picked_degree(world: SimulationWorld, law: LawDefinition, degrees: dict[str, int]) -> int:
    """How far a law would go if it were put now: as picked on the panel, as it is in force,
    or at the middle of how far it can go."""
    held = world.government.laws.get(law.law_id)
    fallback = held.degree if held is not None else len(law.degrees) // 2
    return max(0, min(degrees.get(law.law_id, fallback), len(law.degrees) - 1))


def picked_params(world: SimulationWorld, law: LawDefinition, items: dict[str, str]) -> dict[str, str]:
    """What a law names, for one that names something: as picked, as in force, or the first there is."""
    if law.param is None:
        return {}
    held = world.government.laws.get(law.law_id)
    options = named_items(world)
    fallback = held.params.get("item") if held is not None else (options[0] if options else "")
    return {"item": items.get(law.law_id, fallback or "")}


def status_lines(font: BitmapFont, world: SimulationWorld, width: int) -> list[tuple[str, str]]:
    """How a law comes in here, what waits to be voted and who is out against what, as lines and their colour."""
    state = world.government
    if state.kind is None:
        return [(line, "dust") for line in font.wrap(NO_GOVERNMENT, width)]
    hours = world.registries.proposals.debate_hours
    how = AT_ONCE if decided_at_once(world) else BY_VOTE.format(hours=hours)
    lines = [(line, "sand") for line in font.wrap(how, width)]
    now = world.clock.total_minutes
    for proposal in state.proposals.values():
        if proposal.kind in (ENACT_LAW, REPEAL_LAW):
            left = max(1, -(-(proposal.decides_at - now) // 60))
            lines += [(line, "lamp") for line in font.wrap(f"Se vota en {left} h: {proposal.text}", width)]
    for record in state.protests.values():
        law = world.registries.laws.laws.get(record.law_id)
        if law is None or not record.who or record.last_day < world.clock.day - 1:
            continue
        people = "1 persona" if len(record.who) == 1 else f"{len(record.who)} personas"
        text = f"En la plaza contra {law.name}: {people}, día {max(1, record.days)}"
        lines += [(line, "ember") for line in font.wrap(text, width)]
    return lines


def laws_height(font: BitmapFont, world: SimulationWorld, tab: str, width: int) -> int:
    """How tall the part of the panel that lists laws is."""
    lines = len(status_lines(font, world, width))
    rows = len(laws_of(world, tab)) if world.government.kind is not None else 0
    return lines * LINE_HEIGHT + 4 + rows * ROW_HEIGHT + PADDING


def _columns(rect: pygame.Rect) -> tuple[int, int, int]:
    """Where the name of a law, how far it goes and its buttons start."""
    left = rect.x + PADDING
    return left, left + NAME_WIDTH, left + NAME_WIDTH + DEGREE_WIDTH + 26


def law_buttons(
    font: BitmapFont,
    rect: pygame.Rect,
    top: int,
    world: SimulationWorld,
    tab: str,
    degrees: dict[str, int],
    items: dict[str, str],
) -> list[Button]:
    """The buttons of every law listed, from `top` down: how far it goes, what it names, and
    putting it, changing it or doing away with it."""
    if world.government.kind is None:
        return []
    buttons: list[Button] = []
    _name_x, degree_x, action_x = _columns(rect)
    y = top + len(status_lines(font, world, rect.width - PADDING * 2)) * LINE_HEIGHT + 4
    at_once = decided_at_once(world)
    for law in laws_of(world, tab):
        if y + ROW_HEIGHT > rect.bottom - 2:
            break
        held = world.government.laws.get(law.law_id)
        degree = picked_degree(world, law, degrees)
        if len(law.degrees) > 1:
            buttons.append(Button.at(font, degree_x, y, "<", degree_intent(law.law_id, -1)))
            more = Button.at(font, 0, y, ">", degree_intent(law.law_id, 1))
            more.rect.right = action_x - 4
            buttons.append(more)
        elif law.param is not None:
            buttons.append(Button.at(font, degree_x, y, ">", item_intent(law.law_id)))
        x = action_x
        same = held is not None and held.degree == degree and held.params == picked_params(world, law, items)
        if not same:
            label = CHANGE_LABEL if held is not None else (ENACT_LABEL if at_once else VOTE_LABEL)
            put = Button.at(font, x, y, label, enact_intent(law.law_id))
            buttons.append(put)
            x = put.rect.right + 2
        if held is not None:
            buttons.append(Button.at(font, x, y, REPEAL_LABEL, repeal_intent(law.law_id)))
        y += ROW_HEIGHT
    return buttons


def draw_laws(
    target: pygame.Surface,
    font: BitmapFont,
    rect: pygame.Rect,
    top: int,
    world: SimulationWorld,
    tab: str,
    degrees: dict[str, int],
    items: dict[str, str],
) -> None:
    """The laws of a tab, from `top` down the panel: how one comes in, then each law on a line."""
    width = rect.width - PADDING * 2
    name_x, degree_x, action_x = _columns(rect)
    y = top
    for text, colour in status_lines(font, world, width):
        font.draw(target, text, (name_x, y), PALETTE[colour])
        y += LINE_HEIGHT
    y += 4
    if world.government.kind is None:
        return
    buttons = law_buttons(font, rect, top, world, tab, degrees, items)
    for law in laws_of(world, tab):
        if y + ROW_HEIGHT > rect.bottom - 2:
            break
        held = world.government.laws.get(law.law_id)
        font.draw(target, font.truncate(law.name, NAME_WIDTH - 4), (name_x, y + 1), PALETTE["glow" if held else "bone"])
        degree = law.degrees[picked_degree(world, law, degrees)]
        said = degree.name
        if law.param is not None:
            item = world.registries.items.find(picked_params(world, law, items).get("item", ""))
            said = item.name if item is not None else "nada"
        room = action_x - degree_x - 24
        label = font.truncate(said, room)
        font.draw(target, label, (degree_x + 12 + (room - font.width(label)) // 2, y + 1), PALETTE["sand" if held else "stone"])
        y += ROW_HEIGHT
    for button in buttons:
        button.draw(target, font)
