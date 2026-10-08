"""What there is to say of a thing that stands (P60): how rare it is, whose post, how worn, whether
it has current, how full a store is, and what making it better takes.

It reads the simulation and changes nothing: what is pressed in it is an intent for the scene.
"""

from dataclasses import dataclass, field

import pygame

from graphics.font import LINE_HEIGHT, BitmapFont
from graphics.palette import PALETTE, Color
from simulation.world import SimulationWorld
from ui.button import HEIGHT as BUTTON_HEIGHT
from ui.button import Button
from ui.inventory_view import condition_color
from ui.labels import rarity_color
from ui.panel import draw_bar
from ui.power_board import OFF_LABEL, ON_LABEL, POWER_INTENT, RUNNING, STATE_WORDS, power_state, switch_intent
from world.build import BuildRule
from world.interactable import Interactable

PADDING = 5
BAR_SIZE = (58, 5)
BUTTON_GAP = 2
UPGRADE_LABEL = "Mejorar"
POWER_LABEL = "Corriente"
DRAW_LABEL = "Dibujar"
FREE_POST = "libre"
BROKEN_TEXT = "Averiado: no se puede usar"
NOBODY_MENDS = "Nadie lo arregla: hace falta quien lleve {job}"
MENDING = "Lo arregla {name}: {done}%"
BETTERING = "Mejora en obra, de {name}: {done}%"
NOBODY_AT_IT = "nadie"
TOP_RARITY = "No hay calidad por encima de esta"
NOBODY_TO_ASK = "No hay a quién proponérselo"
PUT_TO = "Se le propone a {name}"
NO_FUEL = "Sin combustible"
STORE_HEADING = "Lo que guarda"


def upgrade_intent(object_id: str) -> tuple[str, str]:
    return ("upgrade", object_id)


def redraw_intent(object_id: str) -> tuple[str, str]:
    return ("redraw", object_id)


@dataclass(frozen=True)
class Line:
    """A line of the panel: what it says and in what colour. With a share, a measure beside it."""

    text: str
    color: Color = PALETTE["bone"]
    share: float | None = None
    bar: str = "lichen"


@dataclass(frozen=True)
class ObjectView:
    """What is said of one thing, laid out: where it goes, each line with how far down it is,
    and what can be pressed."""

    object_id: str
    rect: pygame.Rect
    lines: list[tuple[Line, int]] = field(default_factory=list)
    buttons: list[Button] = field(default_factory=list)


def speaks(world: SimulationWorld, placed: Interactable) -> bool:
    """Whether there is anything to say of a thing beyond what it holds: it runs on current
    or gives it, it is a store, it wears, it can be made better, or it already is."""
    definition = world.definition_of(placed)
    if definition.draws > 0 or definition.gives > 0 or definition.store is not None or placed.level > 1:
        return True
    return world.upgrades.can_be_bettered(world, placed) or world.wear.wears(world, placed)


def rule_text(world: SimulationWorld, rule: BuildRule) -> str:
    """What a piece of work takes, in a few words."""
    items = world.registries.items
    parts = []
    for tag, units in rule.cost.items():
        material = next((items.get(item_id).name for item_id in items.ids() if tag in items.get(item_id).tags), tag)
        parts.append(f"{units} de {material}")
    if rule.minutes:
        hours = rule.minutes / 60
        parts.append(f"{hours:g} h de obra".replace(".", ","))
    return ", ".join(parts)


def _name_of(world: SimulationWorld, resident_id: str | None) -> str:
    resident = world.residents.get(resident_id or "")
    return resident.name if resident is not None else NOBODY_AT_IT


def _done(world: SimulationWorld, site) -> int:
    return round(world.construction.fraction_done(world, site) * 100)


def _post_lines(world: SimulationWorld, placed: Interactable) -> list[Line]:
    job = world.staffing.job_at(world, placed.object_id)
    if job is None:
        return []
    holder = world.staffing.holder(world, placed.object_id)
    lines = [Line(f"Puesto de {job.name}: {holder.name if holder is not None else FREE_POST}")]
    if not world.wear.wears(world, placed):
        return lines
    lines.append(Line("Estado", share=placed.condition / 100.0, bar=condition_color(placed.condition)))
    if world.wear.broken(world, placed.object_id):
        lines.append(Line(BROKEN_TEXT, PALETTE["ember"]))
        site = world.wear.site_of(world, placed.object_id)
        mender = world.residents.get(site.in_charge or "") if site is not None else None
        if mender is not None:
            lines.append(Line(MENDING.format(name=mender.name, done=_done(world, site)), PALETTE["lamp"]))
        else:
            needed = world.registries.jobs.get(world.wear.settings(world).job or "")
            lines.append(Line(NOBODY_MENDS.format(job=needed.name if needed is not None else "eso"), PALETTE["ember"]))
    return lines


def _current_lines(world: SimulationWorld, placed: Interactable) -> list[Line]:
    definition = world.definition_of(placed)
    lines = []
    state = power_state(world, placed.object_id)
    if state is not None:
        word, color = STATE_WORDS[state]
        lines.append(Line(f"Corriente: gasta {definition.draws}. {word}", PALETTE[color if state != RUNNING else "bone"]))
    if definition.gives > 0:
        fuel = world.containers[placed.object_id].count(world.registries.power.fuel) if placed.object_id in world.containers else 0
        gives = round(definition.gives * world.upgrades.better(world, placed.object_id))
        asked = world.power.demand(world)
        lines.append(Line(f"Da {gives} de corriente, se piden {asked}", PALETTE["bone" if asked <= gives else "ember"]))
        lines.append(Line(f"Combustible: {fuel}") if fuel > 0 else Line(NO_FUEL, PALETTE["ember"]))
    return lines


def _store_lines(world: SimulationWorld, placed: Interactable) -> list[Line]:
    found = next((entry for entry in world.stores.stores(world) if entry[0] == placed.object_id), None)
    if found is None:
        return []
    _object_id, inventory, rule = found
    names = world.registries.resources.resources
    lines = []
    for resource_id, room in rule.items():
        held = sum(item.quantity for item in inventory.items if world.stores.resource_of(world, item) == resource_id)
        name = names[resource_id].name if resource_id in names else resource_id
        share = held / room if room > 0 else 1.0
        bar = "ember" if held >= room else "lamp" if share >= 0.8 else "lichen"
        lines.append(Line(f"{name}: {held} de {room}", share=share, bar=bar))
    return lines


def _upgrade_lines(world: SimulationWorld, placed: Interactable) -> tuple[list[Line], bool]:
    """What is said of making a thing better, and whether it can be put to somebody now."""
    upgrades = world.upgrades
    if not upgrades.can_be_bettered(world, placed):
        return [], False
    site = upgrades.site_of(world, placed.object_id)
    if site is not None:
        text = BETTERING.format(name=_name_of(world, site.in_charge), done=_done(world, site))
        return [Line(text, PALETTE["lamp"])], False
    coming = upgrades.next(world, placed)
    if coming is None:
        return [Line(TOP_RARITY, PALETTE["stone"])], False
    error = upgrades.obstacle(world, placed.object_id)
    if error is not None:
        return [Line(error, PALETTE["stone"])], False
    rule = upgrades.rule(world, placed.object_id)
    lines = [Line(f"Mejorar a {coming.name.lower()}: {rule_text(world, rule) if rule is not None else ''}", coming.color)]
    keeper = upgrades.keeper(world, placed.object_id)
    if keeper is None:
        return [*lines, Line(NOBODY_TO_ASK, PALETTE["ember"])], False
    return [*lines, Line(PUT_TO.format(name=keeper.name), PALETTE["stone"])], True


def object_view(
    font: BitmapFont,
    world: SimulationWorld,
    object_id: str | None,
    corner: tuple[int, int],
    width: int,
    drawable: bool = False,
) -> ObjectView | None:
    """Everything the panel says of a thing, laid out from a corner at a width. None for what
    is not there, or has nothing to say."""
    placed = world.interactables.get(object_id or "")
    if placed is None or not speaks(world, placed):
        return None
    definition = world.definition_of(placed)
    rarity = world.upgrades.rarity(world, placed)
    said = [Line(definition.name.capitalize(), rarity.color), Line(f"Calidad: {rarity.name.lower()}", rarity.color)]
    said += _post_lines(world, placed) + _current_lines(world, placed) + _store_lines(world, placed)
    bettering, can_better = _upgrade_lines(world, placed)
    said += bettering

    inner = width - PADDING * 2
    lines: list[tuple[Line, int]] = []
    y = corner[1] + PADDING
    for line in said:
        room = inner - (BAR_SIZE[0] + 4 if line.share is not None else 0)
        for part in font.wrap(line.text, room) or [""]:
            lines.append((Line(part, line.color, line.share, line.bar), y))
            y += LINE_HEIGHT
    labels = []
    if can_better:
        labels.append((UPGRADE_LABEL, upgrade_intent(placed.object_id)))
    if definition.draws > 0:
        labels.append((OFF_LABEL if placed.on else ON_LABEL, switch_intent(placed.object_id, not placed.on)))
    if definition.draws > 0 or definition.gives > 0:
        labels.append((POWER_LABEL, POWER_INTENT))
    if drawable:
        labels.append((DRAW_LABEL, redraw_intent(placed.object_id)))
    buttons: list[Button] = []
    left = corner[0] + PADDING
    x, y = left, y + 2
    for label, intent in labels:
        button = Button.at(font, x, y, label, intent)
        if button.rect.right > corner[0] + width - PADDING and x > left:
            # No room left in the row: it starts another.
            x, y = left, y + BUTTON_HEIGHT + BUTTON_GAP
            button = Button.at(font, x, y, label, intent)
        buttons.append(button)
        x = button.rect.right + BUTTON_GAP
    if buttons:
        y += BUTTON_HEIGHT
    return ObjectView(placed.object_id, pygame.Rect(corner[0], corner[1], width, y + PADDING - corner[1]), lines, buttons)


def draw_object_view(target: pygame.Surface, font: BitmapFont, view: ObjectView) -> None:
    x = view.rect.x + PADDING
    for line, y in view.lines:
        font.draw(target, line.text, (x, y), line.color)
        if line.share is not None:
            bar = pygame.Rect(view.rect.right - PADDING - BAR_SIZE[0], y + (LINE_HEIGHT - BAR_SIZE[1]) // 2, *BAR_SIZE)
            draw_bar(target, bar, line.share, line.bar)
    for button in view.buttons:
        button.draw(target, font)
