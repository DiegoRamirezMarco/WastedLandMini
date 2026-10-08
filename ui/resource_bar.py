"""What the settlement lives on, in the bar on top (P58): what there is of each thing, which way
it is going and by how much a day, how long it will last, and how spirits stand.

Nothing here decides anything. How each resource stands is asked of the settlement's books.
"""

from collections.abc import Callable
from dataclasses import dataclass

import pygame

from graphics.font import LINE_HEIGHT, BitmapFont
from graphics.palette import PALETTE
from simulation.economy.ledger import ResourceLine
from simulation.world import SimulationWorld
from ui.labels import COIN_ICON, lowest_spirits, settlement_counts, settlement_mood
from ui.panel import draw_bar, draw_panel

# The kinds of figure there are in the bar.
PEOPLE, RESOURCE, COIN, MOOD = "people", "resource", "coin", "mood"
PEOPLE_ICON, MOOD_ICON = "people", "mood"
# Room between one figure and the next, and between the parts of one.
GAP = 9
ICON_GAP = 3
ARROW = 5
ARROW_GAP = 3
DAYS_GAP = 4
MOOD_BAR = (24, 5)
# Past this many days nobody needs telling how long a thing will last.
FAR_DAYS = 30
# How much is said of each resource: everything, how long only of what is running low, or only what there is.
FULL, SHORT, BARE = 2, 1, 0
TIP_PADDING = 4
TIP_WIDTH = 190
GOOD_SPIRITS, FAIR_SPIRITS = 0.6, 0.35

PEOPLE_TIP = "Residentes, y camas que hay"
NOT_KNOWN = "Aún no hay bastante apuntado para saber cómo va"
TENTATIVE = "De las primeras horas: es aproximado"
NOTHING_LEFT = "No queda nada"
IN_STORE = "En el almacén: {kept}"
STORE_FULL = "Almacén lleno: {kept}. Hace falta otro"


@dataclass(frozen=True)
class Chip:
    """One figure of the bar: its icon, what it says, and where it is."""

    kind: str
    rect: pygame.Rect
    icon: str
    figure: str = ""
    # How it stands, for a resource the books keep.
    line: ResourceLine | None = None
    # Which way it is going, as -1, 0 or 1, by how much a day, and how many days are left: as said in the bar.
    way: int = 0
    pace: str = ""
    days: str = ""
    # From 0 to 1, for what is shown as a measure and not said: how spirits stand.
    share: float | None = None

    def contains(self, position: tuple[int, int]) -> bool:
        return self.rect.collidepoint(position)


def resource_words(line: ResourceLine, detail: int = FULL) -> tuple[int, str, str]:
    """Which way a resource is going, by how much a day, and how many days are left of it, in as
    few letters as say it. Nothing where the books have too little to go by."""
    if not line.known or detail == BARE:
        return (0, "", "")
    way = 0 if abs(line.net) < 0.5 else (1 if line.net > 0 else -1)
    pace = str(round(abs(line.net))) if way else ""
    days = ""
    if line.days_left is not None and line.days_left < FAR_DAYS and (detail == FULL or line.low):
        days = "<1d" if line.days_left < 1 else f"{int(line.days_left)}d"
    return (way, pace, days)


def _laid_out(font: BitmapFont, world: SimulationWorld, left: int, top: int, icon: int, detail: int) -> list[Chip]:
    lines = {line.icon: line for line in world.ledger.report(world)}
    chips: list[Chip] = []
    x = left

    def place(kind: str, name: str, figure: str, line: ResourceLine | None = None, share: float | None = None) -> None:
        nonlocal x
        way, pace, days = resource_words(line, detail) if line is not None else (0, "", "")
        width = icon + ICON_GAP + (MOOD_BAR[0] if share is not None else font.width(figure))
        if way:
            width += ARROW_GAP + ARROW + 2 + font.width(pace)
        if days:
            width += DAYS_GAP + font.width(days)
        chips.append(Chip(kind, pygame.Rect(x, top, width, icon), name, figure, line, way, pace, days, share))
        x += width + GAP

    for name, figure in settlement_counts(world):
        if name == PEOPLE_ICON:
            place(PEOPLE, name, figure)
        elif name == COIN_ICON:
            place(COIN, name, figure)
        else:
            place(RESOURCE, name, figure, lines.get(name))
    mood = settlement_mood(world)
    if mood is not None:
        place(MOOD, MOOD_ICON, "", share=mood / 100.0)
    return chips


def resource_chips(font: BitmapFont, world: SimulationWorld, left: int, right: int, top: int, icon: int) -> list[Chip]:
    """The figures of the bar from `left`, with as much said of each resource as there is room
    for before `right`: how long it will last is the first thing left out, of what is not
    running low, and which way it is going the next."""
    chips: list[Chip] = []
    for detail in (FULL, SHORT, BARE):
        chips = _laid_out(font, world, left, top, icon, detail)
        if not chips or chips[-1].rect.right <= right:
            break
    return chips


def _arrow(target: pygame.Surface, x: int, y: int, way: int, color) -> None:
    """A small arrowhead, up for what is gaining and down for what is going."""
    if way > 0:
        points = [(x, y + 6), (x + ARROW - 1, y + 6), (x + ARROW // 2, y + 2)]
    else:
        points = [(x, y + 3), (x + ARROW - 1, y + 3), (x + ARROW // 2, y + 7)]
    pygame.draw.polygon(target, color, points)


def spirits_color(share: float) -> str:
    return "lichen" if share >= GOOD_SPIRITS else "lamp" if share >= FAIR_SPIRITS else "ember"


def draw_chips(
    target: pygame.Surface,
    font: BitmapFont,
    chips: list[Chip],
    show_icon: Callable[[str, int], None],
    icon: int,
    lit: bool = False,
) -> None:
    """The figures of the bar. `show_icon` puts an icon at a place along it. What is running low
    is in red, and stands out for half of every blink."""
    for chip in chips:
        x, y = chip.rect.x, chip.rect.y
        show_icon(chip.icon, x)
        x += icon + ICON_GAP
        if chip.share is not None:
            bar = pygame.Rect(x, chip.rect.centery - MOOD_BAR[1] // 2 + 1, *MOOD_BAR)
            draw_bar(target, bar, chip.share, spirits_color(chip.share))
            continue
        low = chip.line is not None and chip.line.low
        font.draw(target, chip.figure, (x, y), PALETTE[("glow" if lit else "ember") if low else "bone"])
        x += font.width(chip.figure)
        if chip.way:
            x += ARROW_GAP
            going = "lichen" if chip.way > 0 else "ember"
            _arrow(target, x, y, chip.way, PALETTE[going])
            x += ARROW + 2
            # A reading taken from less than a whole day is said more quietly.
            said = "stone" if chip.line is not None and chip.line.tentative else going
            font.draw(target, chip.pace, (x, y), PALETTE[said])
            x += font.width(chip.pace)
        if chip.days:
            font.draw(target, chip.days, (x + DAYS_GAP, y), PALETTE["ember" if low else "lamp"])


# ----- what resting the pointer on one says -----


def _amount(units: float) -> str:
    """Units a day, with their sign: whole where there are many, and to a tenth where there are few."""
    if abs(units) >= 9.95:
        return f"{units:+.0f}"
    text = f"{units:+.1f}"
    return text[:-2] if text.endswith(".0") else text.replace(".", ",")


def _days(days: float) -> str:
    if days < 1:
        return "menos de un día"
    return "un día" if days < 2 else f"{int(days)} días"


def tip_lines(world: SimulationWorld, chip: Chip) -> list[tuple[str, str]]:
    """What resting the pointer on a figure of the bar says, as lines and the colour of each:
    for a resource, who makes it and what uses it up."""
    if chip.kind == PEOPLE:
        return [(PEOPLE_TIP, "paper")]
    if chip.kind == COIN:
        coin = world.fund.currency(world)
        held = coin.amount(world.trading.fund) if coin is not None else chip.figure
        return [(f"En el fondo: {held}", "paper")]
    if chip.kind == MOOD:
        mood, lowest = settlement_mood(world), lowest_spirits(world)
        lines = [(f"Ánimo del asentamiento: {round(mood or 0)} de 100", "paper")]
        if lowest is not None:
            lines.append((f"Quien peor está: {lowest.name}, {round(lowest.mood)}", "stone"))
        return lines
    line = chip.line
    if line is None:
        return [(chip.figure, "paper")]
    lines = [(f"{line.name}: {line.stock}", "paper")]
    if line.capacity is not None:
        # How much of it is in the store, of what the store holds (S53).
        kept = f"{line.stored or 0} de {line.capacity}"
        lines.append((STORE_FULL.format(kept=kept), "ember") if line.full else (IN_STORE.format(kept=kept), "stone"))
    if not line.known:
        return [*lines, (NOT_KNOWN, "stone")]
    for why, units in line.by_reason:
        lines.append((f"{_amount(units)} {world.ledger.reason_name(world, why)}", "lichen" if units > 0 else "sand"))
    lines.append((f"Al día: {_amount(line.net) if abs(line.net) >= 0.05 else '0'}", "paper"))
    if line.stock <= 0 and line.going > 0:
        lines.append((NOTHING_LEFT, "ember"))
    elif line.days_left is not None:
        lines.append((f"A este paso queda para {_days(line.days_left)}", "ember" if line.low else "lamp"))
    if line.tentative:
        lines.append((TENTATIVE, "stone"))
    return lines


def tip_rect(font: BitmapFont, chip: Chip, lines: list[tuple[str, str]], area: pygame.Rect) -> pygame.Rect:
    """Where what is said of a figure goes: under it, at the head of `area`, and whole inside it."""
    width = min(TIP_WIDTH, max(font.width(text) for text, _ in lines) + TIP_PADDING * 2)
    height = len(lines) * LINE_HEIGHT + TIP_PADDING * 2 - 2
    left = max(area.left + 2, min(chip.rect.x, area.right - width - 2))
    return pygame.Rect(left, area.top + 2, width, height)


def draw_tip(target: pygame.Surface, font: BitmapFont, rect: pygame.Rect, lines: list[tuple[str, str]]) -> None:
    draw_panel(target, rect, fill="shadow", border="copper")
    y = rect.y + TIP_PADDING - 1
    for text, color in lines:
        font.draw(target, font.truncate(text, rect.width - TIP_PADDING * 2), (rect.x + TIP_PADDING, y), PALETTE[color])
        y += LINE_HEIGHT
