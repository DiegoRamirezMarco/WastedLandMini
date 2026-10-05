"""Card with one resident's state: what they are doing, their needs and how they feel about others."""

import pygame

from graphics.font import LINE_HEIGHT, BitmapFont
from graphics.item_icons import ItemIcons
from graphics.palette import PALETTE
from simulation.residents.needs import NEED_NAMES
from simulation.residents.resident import Resident
from simulation.world import SimulationWorld
from ui.inventory_view import ROW_HEIGHT, draw_item_row
from ui.labels import FEELING_LABELS, NEED_LABELS, describe_action, describe_injuries, describe_job
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


def card_height(world: SimulationWorld) -> int:
    others = min(max(len(world.residents) - 1, 0), MAX_RELATIONSHIPS)
    rows = LINE_HEIGHT * 4 + 2 + BAR_ROW * (len(NEED_NAMES) + 1) + 2 + LINE_HEIGHT * others + ROW_HEIGHT
    return PADDING * 2 + rows


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

    others = [other for other in world.residents.values() if other is not resident]
    for other in others[:MAX_RELATIONSHIPS]:
        feelings = world.relationships.get((resident.resident_id, other.resident_id))
        parts = [
            f"{label} {round(getattr(feelings, feeling)) if feelings is not None else 0}"
            for feeling, label in FEELING_LABELS.items()
        ]
        line = font.truncate(f"{other.name}: " + "  ".join(parts), inner)
        font.draw(target, line, (x, y), PALETTE["bone"])
        y += LINE_HEIGHT

    draw_item_row(target, font, icons, (x, y), world, resident.inventory, resident.resident_id, inner)
    y += ROW_HEIGHT

    if resident.injuries:
        # While someone is hurt, what ails them matters more than what is on their mind.
        font.draw(target, font.truncate(describe_injuries(world, resident), inner), (x, y), PALETTE["ember"])
        return rect
    memories = world.memories.recent(resident.resident_id, 1)
    latest = f"Recuerda: {memories[-1].text}" if memories else "Sin recuerdos todavía"
    font.draw(target, font.truncate(latest, inner), (x, y), PALETTE["stone"])
    return rect
