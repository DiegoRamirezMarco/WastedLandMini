"""Panel with what the player can tell a resident they have stopped: first what kind of thing,
then what, then who or what it is about."""

from dataclasses import dataclass
from collections.abc import Hashable

import pygame

from graphics.font import LINE_HEIGHT, BitmapFont
from graphics.palette import PALETTE
from simulation.ai.affect import GROUPS, INCITE, NEED, TASK, WITH, WORDS, AffectOption
from simulation.world import SimulationWorld
from ui.panel import draw_panel

PANEL_WIDTH = 230
PADDING = 5
ROW_HEIGHT = LINE_HEIGHT + 3
AFFECT_LABEL = "Afectar"
GROUP_TITLES = {
    NEED: "Que atienda una necesidad",
    WITH: "Que vaya con alguien",
    INCITE: "Incitarle",
    TASK: "Que se ponga a algo",
    WORDS: "Unas palabras",
}
BACK_LABEL = "< Volver"
CLOSE_LABEL = "Nada, que siga"
NOTHING_TO_SAY = "No está para que se le diga nada."
HINT = "Lo que le digas, lo hará."
# Opens the panel for whoever is selected, or shuts it and lets them go.
AFFECT_INTENT = ("affect_open",)
BACK_INTENT = ("affect_back",)
CLOSE_INTENT = ("affect_close",)


def group_intent(group: str) -> tuple[str, str]:
    return ("affect_group", group)


def order_intent(kind: str) -> tuple[str, str]:
    return ("affect", kind)


def target_intent(kind: str, target_id: str) -> tuple[str, str, str]:
    return ("affect_target", kind, target_id)


@dataclass(frozen=True)
class AffectRow:
    """One line of the panel: something to click, with what clicking it means."""

    rect: pygame.Rect
    text: str
    intent: Hashable

    def contains(self, position: tuple[int, int]) -> bool:
        return self.rect.collidepoint(position)


def _lines(
    world: SimulationWorld, resident_id: str, group: str | None, kind: str | None
) -> tuple[str, list[tuple[str, Hashable]]]:
    """The heading of the panel as it stands and its lines, each with what clicking it means."""
    options: list[AffectOption] = world.affect_options(resident_id)
    resident = world.residents.get(resident_id)
    name = resident.name if resident is not None else ""
    chosen = next((option for option in options if option.kind == kind), None)
    if chosen is not None and chosen.targets:
        lines = [(chosen.said(target_id), target_intent(chosen.kind, target_id)) for target_id, _name in chosen.targets]
        return f"{name}: {GROUP_TITLES[chosen.group].lower()}", [*lines, (BACK_LABEL, BACK_INTENT)]
    if group is not None:
        lines = [
            (option.label.replace("{target}", "...") if option.targets else option.label, order_intent(option.kind))
            for option in options
            if option.group == group
        ]
        return f"{name}: {GROUP_TITLES[group].lower()}", [*lines, (BACK_LABEL, BACK_INTENT)]
    groups = [group for group in GROUPS if any(option.group == group for option in options)]
    lines = [(f"{GROUP_TITLES[each]} >", group_intent(each)) for each in groups]
    return f"{AFFECT_LABEL} a {name}", [*lines, (CLOSE_LABEL, CLOSE_INTENT)]


def affect_board_height(world: SimulationWorld, resident_id: str, group: str | None, kind: str | None) -> int:
    _title, lines = _lines(world, resident_id, group, kind)
    return PADDING * 2 + LINE_HEIGHT + 3 + ROW_HEIGHT * len(lines) + LINE_HEIGHT + 2


def affect_rows(
    rect: pygame.Rect, world: SimulationWorld, resident_id: str, group: str | None, kind: str | None
) -> list[AffectRow]:
    """Every line of the panel that can be clicked, where it is drawn."""
    _title, lines = _lines(world, resident_id, group, kind)
    top = rect.y + PADDING + LINE_HEIGHT + 3
    return [
        AffectRow(pygame.Rect(rect.x + PADDING, top + index * ROW_HEIGHT, rect.width - PADDING * 2, ROW_HEIGHT - 1), text, intent)
        for index, (text, intent) in enumerate(lines)
        if top + (index + 1) * ROW_HEIGHT <= rect.bottom - LINE_HEIGHT
    ]


def draw_affect_board(
    target: pygame.Surface,
    font: BitmapFont,
    rect: pygame.Rect,
    world: SimulationWorld,
    resident_id: str,
    group: str | None,
    kind: str | None,
    pointer: tuple[int, int] | None = None,
) -> None:
    draw_panel(target, rect)
    title, _lines_ = _lines(world, resident_id, group, kind)
    x, y = rect.x + PADDING, rect.y + PADDING
    font.draw(target, font.truncate(title, rect.width - PADDING * 2), (x, y), PALETTE["paper"])
    rows = affect_rows(rect, world, resident_id, group, kind)
    for row in rows:
        under = pointer is not None and row.contains(pointer)
        way_out = row.intent in (BACK_INTENT, CLOSE_INTENT)
        draw_panel(target, row.rect, fill="shadow", border="lamp" if under else "iron")
        color = "glow" if under else ("dust" if way_out else "bone")
        font.draw(target, font.truncate(row.text, row.rect.width - 6), (row.rect.x + 3, row.rect.y + 1), PALETTE[color])
    hint = HINT if len(rows) > 1 else NOTHING_TO_SAY
    font.draw(target, font.truncate(hint, rect.width - PADDING * 2), (x, rect.bottom - PADDING - LINE_HEIGHT + 1), PALETTE["dust"])
