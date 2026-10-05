"""Draws what an inventory holds: a compact row of icons, or a list with names and owners."""

import pygame

from graphics.font import LINE_HEIGHT, BitmapFont
from graphics.item_icons import ICON_SIZE, ItemIcons
from graphics.palette import PALETTE
from simulation.items.inventory import Inventory
from simulation.world import SimulationWorld
from ui.panel import draw_panel

ROW_HEIGHT = ICON_SIZE[1] + 2
PADDING = 5
PANEL_WIDTH = 184
EMPTY_TEXT = "No lleva nada"


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
    """One line of icons with counts. Things that belong to someone else are counted in red."""
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
        stolen = item.owner_id not in (None, holder_id)
        font.draw(target, count, (x + ICON_SIZE[0] + 2, y + 3), PALETTE["ember" if stolen else "bone"])
        x += needed


def container_panel_height(inventory: Inventory) -> int:
    return PADDING * 2 + LINE_HEIGHT + 2 + ROW_HEIGHT * max(1, len(inventory.items))


def draw_container_panel(
    target: pygame.Surface,
    font: BitmapFont,
    icons: ItemIcons,
    position: tuple[int, int],
    world: SimulationWorld,
    container_id: str,
) -> pygame.Rect:
    """Panel listing everything in a container, with whose it is."""
    inventory = world.containers[container_id]
    rect = pygame.Rect(position, (PANEL_WIDTH, container_panel_height(inventory)))
    draw_panel(target, rect)
    x, y = rect.x + PADDING, rect.y + PADDING
    placed = world.interactables.get(container_id)
    title = world.definition_of(placed).name.capitalize() if placed is not None else container_id
    font.draw(target, title, (x, y), PALETTE["paper"])
    y += LINE_HEIGHT + 2
    if not inventory.items:
        font.draw(target, "Vacía", (x, y + 3), PALETTE["stone"])
    for item in inventory.items:
        definition = world.registries.items.resolve(item.definition_id)
        owner = world.residents.get(item.owner_id or "")
        whose = f"de {owner.name}" if owner is not None else "de todos"
        target.blit(icons.icon(item.definition_id), (x, y))
        line = font.truncate(f"{definition.name} x{item.quantity} ({whose})", rect.width - PADDING * 2 - ICON_SIZE[0] - 4)
        font.draw(target, line, (x + ICON_SIZE[0] + 4, y + 3), PALETTE["bone"])
        y += ROW_HEIGHT
    return rect
