"""Draws what an inventory holds: a compact row of icons, or a list with names and owners."""

import pygame

from graphics.font import LINE_HEIGHT, BitmapFont
from graphics.item_icons import ICON_SIZE, ItemIcons
from graphics.palette import PALETTE
from simulation.items.inventory import Inventory
from simulation.world import SimulationWorld
from ui.labels import condition_of, price_label, selling_use
from ui.panel import draw_panel

ROW_HEIGHT = ICON_SIZE[1] + 2
PADDING = 5
PANEL_WIDTH = 184
EMPTY_TEXT = "No lleva nada"
# The mark at the end of a row that breaks the item up for scrap, and how wide it is.
SCRAP_MARK = "desg."
SCRAP_WIDTH = 30
# Condition from which a thing is shown as sound, and from which as merely worn.
SOUND_CONDITION = 50.0
WORN_CONDITION = 20.0


def condition_color(condition: float) -> str:
    """Palette name for the state of a thing: sound, worn, or all but gone."""
    if condition >= SOUND_CONDITION:
        return "lichen"
    return "lamp" if condition >= WORN_CONDITION else "ember"


def draw_condition(target: pygame.Surface, position: tuple[int, int], condition: float) -> None:
    """A thin bar under an icon at `position` for how much use a thing has left in it."""
    bar = pygame.Rect(position[0] + 1, position[1] + ICON_SIZE[1], ICON_SIZE[0] - 2, 2)
    pygame.draw.rect(target, PALETTE["shadow"], bar)
    filled = round(bar.width * condition / 100.0)
    if filled:
        pygame.draw.rect(target, PALETTE[condition_color(condition)], (bar.x, bar.y, filled, bar.height))


def draw_item_row(
    target: pygame.Surface,
    font: BitmapFont,
    icons: ItemIcons,
    position: tuple[int, int],
    world: SimulationWorld,
    inventory: Inventory,
    holder_id: str,
    width: int,
) -> None:
    """One line of icons with counts. Things that belong to someone else are counted in red,
    and a thing that wears out has a bar under it for the state it is in."""
    x, y = position
    if not inventory.items:
        font.draw(target, EMPTY_TEXT, (x, y + 3), PALETTE["stone"])
        return
    for item in inventory.items:
        count = f"x{item.quantity}"
        needed = ICON_SIZE[0] + 2 + font.width(count) + 6
        if x + needed > position[0] + width:
            font.draw(target, "...", (x, y + 3), PALETTE["stone"])
            return
        target.blit(icons.icon(item.definition_id), (x, y))
        condition = condition_of(world, item)
        if condition is not None:
            draw_condition(target, (x, y), condition)
        stolen = item.owner_id not in (None, holder_id)
        font.draw(target, count, (x + ICON_SIZE[0] + 2, y + 3), PALETTE["ember" if stolen else "bone"])
        x += needed


def container_panel_height(inventory: Inventory) -> int:
    return PADDING * 2 + LINE_HEIGHT + 2 + ROW_HEIGHT * max(1, len(inventory.items))


def container_item_hitboxes(
    position: tuple[int, int], world: SimulationWorld, container_id: str, width: int = PANEL_WIDTH
) -> list[tuple[pygame.Rect, str]]:
    """Rows occupied by the items in a container, paired with their stable definition IDs."""
    inventory = world.containers.get(container_id)
    if inventory is None:
        return []
    x, y = position[0] + PADDING, position[1] + PADDING + LINE_HEIGHT + 2
    return [
        (pygame.Rect(x, y + index * ROW_HEIGHT, width - PADDING * 2, ROW_HEIGHT), item.definition_id)
        for index, item in enumerate(inventory.items)
    ]


def container_scrap_hitboxes(
    position: tuple[int, int], world: SimulationWorld, container_id: str, width: int = PANEL_WIDTH
) -> list[tuple[pygame.Rect, str]]:
    """Where each item that can be broken up for scrap is clicked to do it, paired with the
    item's own ID: at the right end of its row. Nothing on a counter is: that is for sale."""
    inventory = world.containers.get(container_id)
    if inventory is None or selling_use(world, container_id) is not None:
        return []
    right = position[0] + width - PADDING
    top = position[1] + PADDING + LINE_HEIGHT + 2
    return [
        (pygame.Rect(right - SCRAP_WIDTH, top + index * ROW_HEIGHT + 1, SCRAP_WIDTH, ROW_HEIGHT - 2), item.instance_id)
        for index, item in enumerate(inventory.items)
        if world.salvaging.scrap_units(world, item) > 0
    ]


def draw_container_panel(
    target: pygame.Surface,
    font: BitmapFont,
    icons: ItemIcons,
    position: tuple[int, int],
    world: SimulationWorld,
    container_id: str,
    width: int = PANEL_WIDTH,
) -> pygame.Rect:
    """Panel listing everything in a container: whose it is, or what it costs on a shop's counter."""
    inventory = world.containers[container_id]
    rect = pygame.Rect(position, (width, container_panel_height(inventory)))
    draw_panel(target, rect)
    x, y = rect.x + PADDING, rect.y + PADDING
    placed = world.interactables.get(container_id)
    title = world.definition_of(placed).name.capitalize() if placed is not None else container_id
    selling = selling_use(world, container_id)
    if selling is not None:
        attended = selling.staffed_by is None or world.work.is_staffed(world, selling.staffed_by)
        title = f"{title} · {'en venta' if attended else 'nadie atiende'}"
    font.draw(target, title, (x, y), PALETTE["paper"])
    y += LINE_HEIGHT + 2
    if not inventory.items:
        font.draw(target, "Vacía", (x, y + 3), PALETTE["stone"])
    scrap = dict((item_id, mark) for mark, item_id in container_scrap_hitboxes(position, world, container_id, width))
    for item in inventory.items:
        definition = world.registries.items.resolve(item.definition_id)
        target.blit(icons.icon(item.definition_id), (x, y))
        condition = condition_of(world, item)
        if condition is not None:
            draw_condition(target, (x, y), condition)
        text = f"{definition.name} x{item.quantity}"
        room = rect.width - PADDING * 2 - ICON_SIZE[0] - 4
        price = price_label(world, container_id, item) if selling is not None and item.owner_id is None else None
        if price is not None:
            font.draw(target, price, (rect.right - PADDING - font.width(price), y + 3), PALETTE["lamp"])
            room -= font.width(price) + 4
        else:
            owner = world.residents.get(item.owner_id or "")
            text += f" (de {owner.name})" if owner is not None else " (de todos)"
        mark = scrap.get(item.instance_id)
        if mark is not None:
            draw_panel(target, mark, fill="shadow", border="copper")
            font.draw(target, SCRAP_MARK, (mark.centerx - font.width(SCRAP_MARK) // 2, mark.y + 1), PALETTE["sand"])
            room -= SCRAP_WIDTH + 3
        font.draw(target, font.truncate(text, room), (x + ICON_SIZE[0] + 4, y + 3), PALETTE["bone"])
        y += ROW_HEIGHT
    return rect
