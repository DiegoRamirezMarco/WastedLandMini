"""The panel down the right of the screen: one resident in full, or everybody at a glance."""

import pygame

from graphics.assets import AssetStore
from graphics.face_renderer import FACE_SIZE, MARKER_SIZE, FaceRenderer
from graphics.font import LINE_HEIGHT, BitmapFont
from graphics.icons import ICON_SIZE as MARK_SIZE
from graphics.icons import icon_path
from graphics.item_icons import ICON_SIZE, ItemIcons
from graphics.palette import PALETTE
from graphics.screen_layers import ScreenLayers
from simulation.residents.needs import NEED_NAMES
from simulation.residents.resident import Resident
from simulation.tastes.settings import DISLIKED, HATED, LIKED, LOVED
from simulation.world import SimulationWorld
from ui.dock import draw_face
from ui.inventory_view import draw_condition
from ui.labels import (
    NEED_LABELS,
    affordable_goods,
    condition_of,
    describe_action,
    describe_credits,
    describe_injuries,
    describe_job,
    expression_of,
    has_shop,
    relationship_rows,
    taste_debug_rows,
    taste_rows,
    trait_names,
)
from ui.panel import draw_panel

PADDING = 6
BAR_LEFT = 44
BAR_ROW = 10
NEED_COLORS = {"hunger": "sand", "thirst": "teal", "tiredness": "dust", "social": "rose", "stress": "ember"}
HEALTH_LABEL = "Salud"
HEALTH_COLOR = "lichen"
MOOD_LABEL = "Ánimo"
MOOD_COLOR = "lamp"
# Health above the needs and mood below them.
OTHER_BARS = 2
MAX_RELATIONSHIPS = 5
RELATIONSHIP_ROW = MARKER_SIZE[1] + 2
# The inventory as a grid: an icon at twice its size, how many, and its name underneath.
ITEM_SCALE = 2
ITEM_COLUMNS = 3
ITEM_CELL_HEIGHT = ICON_SIZE[1] * ITEM_SCALE + LINE_HEIGHT + 4
MAX_ITEM_ROWS = 2
ROSTER_ROW = MARKER_SIZE[1] + 3
TRAITS_TITLE = "Rasgos"
RELATIONSHIPS_TITLE = "Relaciones"
INVENTORY_TITLE = "Inventario"
EMPTY_TEXT = "No lleva nada"
AFFORDS_LABEL = "Le llega para"
AFFORDS_NOTHING = "No le llega para nada de la tienda"
ROSTER_TITLE = "Asentamiento"
# The lower part of the panel shows one of two things: how they live, or what they like.
LIFE_TAB, TASTES_TAB = "life", "tastes"
TASTES_TITLE = "Gustos"
TAB_LABELS = {LIFE_TAB: "Gustos", TASTES_TAB: "Volver"}
TAB_WIDTH = 40
TASTE_ROW = LINE_HEIGHT + 2
TASTE_ICONS = {LOVED: "relish", LIKED: "relish", DISLIKED: "disgust", HATED: "disgust"}
TASTE_COLORS = {LOVED: "lichen", LIKED: "lichen", DISLIKED: "ember", HATED: "ember"}
# Beside it, on how they live, the way to where their manners are chosen.
MANNERS_LABEL = "Maneras"
MANNERS_WIDTH = 46
# A switch on the tastes for looking at the figures the game keeps to itself. Not for play.
DEBUG_LABEL = "Debug"
DEBUG_WIDTH = 34
DEBUG_TITLE = "Gustos: valores"
DEBUG_HEADINGS = ("base", "apr.", "total")
DEBUG_COLUMN = 26


def _title(target: pygame.Surface, font: BitmapFont, text: str, x: int, y: int, width: int) -> int:
    """A heading with a rule under it. Returns where what follows starts."""
    font.draw(target, text, (x, y), PALETTE["paper"])
    target.fill(PALETTE["iron"], (x, y + LINE_HEIGHT, width, 1))
    return y + LINE_HEIGHT + 3


def roster_rows(panel: pygame.Rect, world: SimulationWorld) -> list[tuple[pygame.Rect, str]]:
    """Where each resident is listed when nobody is selected, to be picked there with a click."""
    top = panel.y + PADDING + LINE_HEIGHT + 3
    rows = []
    for resident_id in world.residents:
        row = pygame.Rect(panel.x + PADDING, top, panel.width - PADDING * 2, ROSTER_ROW)
        if row.bottom > panel.bottom - PADDING:
            break
        rows.append((row, resident_id))
        top += ROSTER_ROW
    return rows


def draw_roster(
    target: pygame.Surface, font: BitmapFont, faces: FaceRenderer, panel: pygame.Rect, world: SimulationWorld
) -> None:
    """Everybody in the settlement: a face, a name and what they are doing."""
    draw_panel(target, panel)
    inner = panel.width - PADDING * 2
    _title(target, font, f"{ROSTER_TITLE} · {len(world.residents)}", panel.x + PADDING, panel.y + PADDING, inner)
    for row, resident_id in roster_rows(panel, world):
        resident = world.residents[resident_id]
        target.blit(faces.marker(resident_id, expression_of(world, resident)), row.topleft)
        left = row.x + MARKER_SIZE[0] + 4
        font.draw(target, resident.name, (left, row.y + 2), PALETTE["bone"])
        doing = "fuera" if resident.away else describe_action(world, resident)
        left += font.width(resident.name) + 6
        font.draw(target, font.truncate(doing, row.right - left), (left, row.y + 2), PALETTE["stone"])


def tab_hitbox(panel: pygame.Rect) -> pygame.Rect:
    """Where the panel is switched between how a resident lives and what they like: at the right
    end of the first heading under their bars."""
    top = panel.y + PADDING + FACE_SIZE[1] + 6 + BAR_ROW * (len(NEED_NAMES) + OTHER_BARS) + 4
    return pygame.Rect(panel.right - PADDING - TAB_WIDTH, top - 1, TAB_WIDTH, LINE_HEIGHT)


def manners_hitbox(panel: pygame.Rect) -> pygame.Rect:
    """Where a resident's way of walking, eating and fighting is asked for: beside the way to their tastes."""
    tab = tab_hitbox(panel)
    return pygame.Rect(tab.left - MANNERS_WIDTH - 3, tab.y, MANNERS_WIDTH, tab.height)


def debug_hitbox(panel: pygame.Rect) -> pygame.Rect:
    """Where the figures behind the tastes are switched on and off: beside the way back."""
    tab = tab_hitbox(panel)
    return pygame.Rect(tab.left - DEBUG_WIDTH - 3, tab.y, DEBUG_WIDTH, tab.height)


def _draw_taste_figures(
    target: pygame.Surface,
    font: BitmapFont,
    panel: pygame.Rect,
    position: tuple[int, int],
    world: SimulationWorld,
    resident: Resident,
) -> None:
    """Every taste a resident has with its figures: the leaning, what was learned, and the two together."""
    x, y = position
    right = panel.right - PADDING
    # From the right: how sure the player is, then the three figures.
    columns = [right - 8 - DEBUG_COLUMN * (len(DEBUG_HEADINGS) - index) for index in range(len(DEBUG_HEADINGS))]
    for column, heading in zip(columns, DEBUG_HEADINGS):
        font.draw(target, heading, (column + DEBUG_COLUMN - font.width(heading), y), PALETTE["dust"])
    y += TASTE_ROW
    rows = taste_debug_rows(world, resident)
    room = (panel.bottom - PADDING - y) // TASTE_ROW
    left_out = max(0, len(rows) - (room - 1)) if len(rows) > room else 0
    for label, leaning, learned, value, reaction, sure in rows[: len(rows) - left_out]:
        font.draw(target, font.truncate(label, columns[0] - x - 2), (x, y), PALETTE["bone"])
        figures = ("" if leaning is None else f"{leaning:+d}", "" if learned is None else f"{learned:+d}", f"{value:+d}")
        colors = ("stone", "stone", TASTE_COLORS.get(reaction, "paper"))
        for column, figure, color in zip(columns, figures, colors):
            font.draw(target, figure, (column + DEBUG_COLUMN - font.width(figure), y), PALETTE[color])
        font.draw(target, sure, (right - font.width(sure), y), PALETTE["teal"])
        y += TASTE_ROW
    if left_out:
        font.draw(target, f"y {left_out} más", (x, y), PALETTE["stone"])
    elif not rows:
        font.draw(target, "Todavía no tiene ninguno", (x, y), PALETTE["stone"])


def _draw_tab(target: pygame.Surface, font: BitmapFont, panel: pygame.Rect, tab: str) -> None:
    rect = tab_hitbox(panel)
    draw_panel(target, rect, fill="shadow", border="lamp")
    label = TAB_LABELS[tab]
    font.draw(target, label, (rect.centerx - font.width(label) // 2, rect.y), PALETTE["glow"])


def _draw_tastes(
    target: pygame.Surface,
    font: BitmapFont,
    assets: AssetStore,
    panel: pygame.Rect,
    position: tuple[int, int],
    world: SimulationWorld,
    resident: Resident,
    debug: bool = False,
) -> None:
    """What the player has found out of what a resident likes, one taste to a line. With `debug`,
    every taste they have and the figures behind it instead."""
    x, y = position
    inner = panel.width - PADDING * 2
    y = _title(target, font, DEBUG_TITLE if debug else TASTES_TITLE, x, y, inner - TAB_WIDTH - DEBUG_WIDTH - 6)
    switch = debug_hitbox(panel)
    draw_panel(target, switch, fill="lamp" if debug else "shadow", border="iron")
    font.draw(
        target,
        DEBUG_LABEL,
        (switch.centerx - font.width(DEBUG_LABEL) // 2, switch.y),
        PALETTE["ink" if debug else "stone"],
    )
    if debug:
        _draw_taste_figures(target, font, panel, (x, y), world, resident)
        return
    rows = taste_rows(world, resident)
    room = (panel.bottom - PADDING - y) // TASTE_ROW
    if len(rows) > room:
        left_out = len(rows) - (room - 1)
        rows = rows[: room - 1] + [(f"y {left_out} más", "", None)]
    for label, words, leaning in rows:
        icon = TASTE_ICONS.get(leaning or "")
        if icon is not None:
            # The marks are drawn for a bubble of paper, so they are given a scrap of it here.
            target.fill(PALETTE["paper"], (x, y, MARK_SIZE[0] + 2, MARK_SIZE[1] + 1))
            target.blit(assets.image(icon_path(icon), size=MARK_SIZE), (x + 1, y))
        left = x + MARK_SIZE[0] + 5
        said = font.width(words)
        font.draw(target, font.truncate(label, inner - (left - x) - said - 6), (left, y), PALETTE["bone" if leaning else "stone"])
        font.draw(target, words, (panel.right - PADDING - said, y), PALETTE[TASTE_COLORS.get(leaning or "", "dust")])
        y += TASTE_ROW


def relationship_hitboxes(panel: pygame.Rect, world: SimulationWorld, resident: Resident) -> list[tuple[pygame.Rect, str]]:
    """Where each of the people a resident cares about is listed, to be picked there with a click."""
    top = _relationships_top(panel, world, resident)
    return [
        (pygame.Rect(panel.x + PADDING, top + index * RELATIONSHIP_ROW, panel.width - PADDING * 2, RELATIONSHIP_ROW), other.resident_id)
        for index, (other, _, _, _) in enumerate(relationship_rows(world, resident, MAX_RELATIONSHIPS))
    ]


def inventory_hitboxes(panel: pygame.Rect, world: SimulationWorld, resident: Resident) -> list[tuple[pygame.Rect, str]]:
    """The visible inventory cells and the stable item definition shown in each one."""
    top = _relationships_top(panel, world, resident)
    top += len(relationship_rows(world, resident, MAX_RELATIONSHIPS)) * RELATIONSHIP_ROW + 4
    top += LINE_HEIGHT + 3
    left = panel.x + PADDING
    width = panel.width - PADDING * 2
    cell = width // ITEM_COLUMNS
    shown = resident.inventory.items[: ITEM_COLUMNS * MAX_ITEM_ROWS]
    return [
        (
            pygame.Rect(
                left + (index % ITEM_COLUMNS) * cell,
                top + (index // ITEM_COLUMNS) * ITEM_CELL_HEIGHT,
                cell - 2,
                ITEM_CELL_HEIGHT - 2,
            ),
            item.definition_id,
        )
        for index, item in enumerate(shown)
    ]


def _relationships_top(panel: pygame.Rect, world: SimulationWorld, resident: Resident) -> int:
    top = panel.y + PADDING + FACE_SIZE[1] + 6 + BAR_ROW * (len(NEED_NAMES) + OTHER_BARS) + 4
    if resident.traits:
        top += LINE_HEIGHT + 3 + LINE_HEIGHT + 6
    return top + LINE_HEIGHT + 3


def draw_resident_panel(
    target: pygame.Surface,
    font: BitmapFont,
    icons: ItemIcons,
    faces: FaceRenderer,
    assets: AssetStore,
    panel: pygame.Rect,
    world: SimulationWorld,
    resident: Resident,
    layers: ScreenLayers | None = None,
    tab: str = LIFE_TAB,
    debug: bool = False,
) -> None:
    draw_panel(target, panel)
    x, y = panel.x + PADDING, panel.y + PADDING
    inner = panel.width - PADDING * 2

    # Their face, and beside it who they are and what they are about.
    portrait = pygame.Rect(x, y, *FACE_SIZE)
    draw_face(target, faces, portrait, resident.resident_id, expression_of(world, resident), layers)
    pygame.draw.rect(target, PALETTE["stone"], portrait, 1)
    beside = portrait.right + 6
    room = panel.right - PADDING - beside
    font.draw(target, resident.name, (beside, y), PALETTE["paper"], scale=2)
    lines = [
        (describe_credits(resident), "lamp"),
        (describe_action(world, resident), "dust"),
        (describe_job(world, resident), "stone"),
    ]
    line_y = y + LINE_HEIGHT * 2 + 2
    for text, color in lines:
        for line in font.wrap(text, room)[:2]:
            if line_y + LINE_HEIGHT > portrait.bottom + 2:
                break
            font.draw(target, line, (beside, line_y), PALETTE[color])
            line_y += LINE_HEIGHT
    y = portrait.bottom + 6

    # Health and mood are better full; the needs between them are better empty.
    bars = [(HEALTH_LABEL, resident.health, HEALTH_COLOR)] + [
        (NEED_LABELS[need], getattr(resident.needs, need), NEED_COLORS[need]) for need in NEED_NAMES
    ] + [(MOOD_LABEL, resident.mood, MOOD_COLOR)]
    bar_width = inner - BAR_LEFT - 22
    for label, value, color in bars:
        font.draw(target, label, (x, y - 1), PALETTE["bone"])
        bar = pygame.Rect(x + BAR_LEFT, y + 3, bar_width, 5)
        pygame.draw.rect(target, PALETTE["shadow"], bar)
        filled = round(bar_width * value / 100.0)
        if filled:
            pygame.draw.rect(target, PALETTE[color], (bar.x, bar.y, filled, bar.height))
        number = str(round(value))
        font.draw(target, number, (panel.right - PADDING - font.width(number), y - 1), PALETTE["dust"])
        y += BAR_ROW
    y += 4

    if tab == TASTES_TAB:
        _draw_tastes(target, font, assets, panel, (x, y), world, resident, debug)
        _draw_tab(target, font, panel, tab)
        return
    traits = trait_names(world, resident)
    if traits:
        y = _title(target, font, TRAITS_TITLE, x, y, inner)
        left = x
        for name in traits:
            chip = pygame.Rect(left, y, font.width(name) + 8, LINE_HEIGHT + 1)
            if chip.right > panel.right - PADDING:
                break
            draw_panel(target, chip, fill="shadow", border="iron")
            font.draw(target, name, (chip.x + 4, chip.y + 1), PALETTE["bone"])
            left = chip.right + 3
        y += LINE_HEIGHT + 6

    y = _title(target, font, RELATIONSHIPS_TITLE, x, y, inner)
    _draw_tab(target, font, panel, tab)
    manners = manners_hitbox(panel)
    draw_panel(target, manners, fill="shadow", border="lamp")
    font.draw(target, MANNERS_LABEL, (manners.centerx - font.width(MANNERS_LABEL) // 2, manners.y), PALETTE["glow"])
    for other, score, label, icon in relationship_rows(world, resident, MAX_RELATIONSHIPS):
        target.blit(faces.marker(other.resident_id), (x, y))
        left = x + MARKER_SIZE[0] + 3
        if icon is not None:
            target.blit(assets.image(icon_path(icon), size=MARK_SIZE), (left, y + 4))
        left += MARK_SIZE[0] + 3
        font.draw(target, other.name, (left, y + 2), PALETTE["bone"])
        figure = f"{score:+d}" if score else "0"
        color = "lichen" if score > 0 else ("ember" if score < 0 else "stone")
        font.draw(target, figure, (x + 92 - font.width(figure), y + 2), PALETTE[color])
        font.draw(target, font.truncate(label, panel.right - PADDING - (x + 98)), (x + 98, y + 2), PALETTE["dust"])
        y += RELATIONSHIP_ROW
    y += 4

    y = _title(target, font, INVENTORY_TITLE, x, y, inner)
    y = _draw_item_grid(target, font, icons, (x, y), inner, world, resident)
    if has_shop(world):
        _draw_affordable(target, font, icons, (x, y), world, resident, inner)
        y += ICON_SIZE[1] + 2

    if resident.injuries or resident.lost_limbs:
        # While someone is hurt, what ails them matters more than what is on their mind.
        last, color = describe_injuries(world, resident), "ember"
    else:
        memories = world.memories.recent(resident.resident_id, 1)
        last, color = (f"Recuerda: {memories[-1].text}" if memories else "Sin recuerdos todavía"), "stone"
    for line in font.wrap(last, inner):
        if y + LINE_HEIGHT > panel.bottom - 2:
            break
        font.draw(target, line, (x, y), PALETTE[color])
        y += LINE_HEIGHT


def _draw_item_grid(
    target: pygame.Surface,
    font: BitmapFont,
    icons: ItemIcons,
    position: tuple[int, int],
    width: int,
    world: SimulationWorld,
    resident: Resident,
) -> int:
    """What a resident carries, a few to a row. Returns where what follows starts."""
    x, y = position
    items = resident.inventory.items
    if not items:
        font.draw(target, EMPTY_TEXT, (x, y), PALETTE["stone"])
        return y + LINE_HEIGHT + 4
    cell = width // ITEM_COLUMNS
    size = (ICON_SIZE[0] * ITEM_SCALE, ICON_SIZE[1] * ITEM_SCALE)
    shown = items[: ITEM_COLUMNS * MAX_ITEM_ROWS]
    for index, item in enumerate(shown):
        left = x + (index % ITEM_COLUMNS) * cell
        top = y + (index // ITEM_COLUMNS) * ITEM_CELL_HEIGHT
        box = pygame.Rect(left, top, cell - 2, ITEM_CELL_HEIGHT - 2)
        draw_panel(target, box, fill="shadow", border="iron")
        corner = (box.centerx - size[0] // 2, box.y + 1)
        target.blit(pygame.transform.scale(icons.icon(item.definition_id), size), corner)
        condition = condition_of(world, item)
        if condition is not None:
            draw_condition(target, (box.centerx - ICON_SIZE[0] // 2, corner[1] + size[1] - ICON_SIZE[1] - 1), condition)
        count = str(item.quantity)
        # Things that belong to someone else are counted in red.
        stolen = item.owner_id not in (None, resident.resident_id)
        font.draw(target, count, (box.right - 3 - font.width(count), box.y + 1), PALETTE["ember" if stolen else "paper"])
        name = font.truncate(world.registries.items.resolve(item.definition_id).name, box.width - 4)
        font.draw(target, name, (box.centerx - font.width(name) // 2, box.bottom - LINE_HEIGHT), PALETTE["bone"])
    rows = -(-len(shown) // ITEM_COLUMNS)
    return y + rows * ITEM_CELL_HEIGHT + 2


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
