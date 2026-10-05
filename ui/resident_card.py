"""Card with one resident's state: what they are doing, their needs and how they feel about others."""

import pygame

from graphics.font import LINE_HEIGHT, BitmapFont
from graphics.item_icons import ICON_SIZE, ItemIcons
from graphics.palette import PALETTE
from simulation.residents.needs import NEED_NAMES
from simulation.residents.resident import Resident
from simulation.world import SimulationWorld
from ui.inventory_view import ROW_HEIGHT, draw_item_row
from ui.labels import (
    FEELING_LABELS,
    NEED_LABELS,
    affordable_goods,
    describe_action,
    describe_bond,
    describe_credits,
    describe_injuries,
    describe_job,
    has_shop,
)
from ui.panel import draw_panel

CARD_WIDTH = 184
PADDING = 5
BAR_LEFT = 44
BAR_WIDTH = 100
BAR_ROW = 10
NEED_COLORS = {"hunger": "sand", "tiredness": "teal", "social": "rose", "stress": "ember"}
HEALTH_LABEL = "Salud"
HEALTH_COLOR = "lichen"
MAX_RELATIONSHIPS = 4
AFFORDS_LABEL = "Le llega para"
AFFORDS_NOTHING = "No le llega para nada de la tienda"


def card_height(world: SimulationWorld) -> int:
    others = min(max(len(world.residents) - 1, 0), MAX_RELATIONSHIPS)
    rows = LINE_HEIGHT * 4 + 2 + BAR_ROW * (len(NEED_NAMES) + 1) + 2 + LINE_HEIGHT * others + ROW_HEIGHT
    # Where there is a shop, one more row for what their credits would buy there.
    return PADDING * 2 + rows + (ROW_HEIGHT if has_shop(world) else 0)


def draw_resident_card(
    target: pygame.Surface,
    font: BitmapFont,
    icons: ItemIcons,
    position: tuple[int, int],
    world: SimulationWorld,
    resident: Resident,
) -> pygame.Rect:
    rect = pygame.Rect(position, (CARD_WIDTH, card_height(world)))
    draw_panel(target, rect)
    x, y = rect.x + PADDING, rect.y + PADDING
    inner = CARD_WIDTH - PADDING * 2

    font.draw(target, resident.name, (x, y), PALETTE["paper"])
    credits = describe_credits(resident)
    font.draw(target, credits, (rect.right - PADDING - font.width(credits), y), PALETTE["lamp"])
    y += LINE_HEIGHT
    action = font.truncate(describe_action(world, resident), inner)
    font.draw(target, action, (x, y), PALETTE["dust"])
    y += LINE_HEIGHT
    font.draw(target, font.truncate(describe_job(world, resident), inner), (x, y), PALETTE["stone"])
    y += LINE_HEIGHT + 2

    bars = [(HEALTH_LABEL, resident.health, HEALTH_COLOR)] + [
        (NEED_LABELS[need], getattr(resident.needs, need), NEED_COLORS[need]) for need in NEED_NAMES
    ]
    for label, value, color in bars:
        font.draw(target, label, (x, y - 1), PALETTE["bone"])
        bar = pygame.Rect(rect.x + PADDING + BAR_LEFT, y + 3, BAR_WIDTH, 5)
        pygame.draw.rect(target, PALETTE["shadow"], bar)
        filled = round(BAR_WIDTH * value / 100.0)
        if filled:
            pygame.draw.rect(target, PALETTE[color], (bar.x, bar.y, filled, bar.height))
        number = str(round(value))
        font.draw(target, number, (rect.right - PADDING - font.width(number), y - 1), PALETTE["dust"])
        y += BAR_ROW
    y += 2

    # Their partner comes first, so that there is always room for them.
    others = sorted(
        (other for other in world.residents.values() if other is not resident),
        key=lambda other: other.resident_id != resident.couple_with,
    )
    for other in others[:MAX_RELATIONSHIPS]:
        feelings = world.relationships.get((resident.resident_id, other.resident_id))
        parts = [
            f"{label} {round(getattr(feelings, feeling)) if feelings is not None else 0}"
            for feeling, label in FEELING_LABELS.items()
        ]
        line = font.truncate(f"{other.name}{describe_bond(world, resident, other)}: " + "  ".join(parts), inner)
        font.draw(target, line, (x, y), PALETTE["bone"])
        y += LINE_HEIGHT

    draw_item_row(target, font, icons, (x, y), world, resident.inventory, resident.resident_id, inner)
    y += ROW_HEIGHT
    if has_shop(world):
        _draw_affordable(target, font, icons, (x, y), world, resident, inner)
        y += ROW_HEIGHT

    if resident.injuries:
        # While someone is hurt, what ails them matters more than what is on their mind.
        font.draw(target, font.truncate(describe_injuries(world, resident), inner), (x, y), PALETTE["ember"])
        return rect
    memories = world.memories.recent(resident.resident_id, 1)
    latest = f"Recuerda: {memories[-1].text}" if memories else "Sin recuerdos todavía"
    font.draw(target, font.truncate(latest, inner), (x, y), PALETTE["stone"])
    return rect


def _draw_affordable(
    target: pygame.Surface,
    font: BitmapFont,
    icons: ItemIcons,
    position: tuple[int, int],
    world: SimulationWorld,
    resident: Resident,
    width: int,
) -> None:
    """One line with the icons of what a resident's credits would buy at the shop right now."""
    x, y = position
    goods = affordable_goods(world, resident)
    if not goods:
        font.draw(target, font.truncate(AFFORDS_NOTHING, width), (x, y + 3), PALETTE["stone"])
        return
    font.draw(target, AFFORDS_LABEL, (x, y + 3), PALETTE["stone"])
    left = x + font.width(AFFORDS_LABEL) + 6
    for definition_id in goods:
        if left + ICON_SIZE[0] > x + width:
            break
        target.blit(icons.icon(definition_id), (left, y))
        left += ICON_SIZE[0] + 2
