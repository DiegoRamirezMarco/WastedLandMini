"""Panel listing the settlement's posts: who holds each, which stand empty, what whoever is
selected would make of each, and the ways of putting them to one, proposing it, or pushing theirs."""

from dataclasses import dataclass

import pygame

from graphics.font import LINE_HEIGHT, BitmapFont
from graphics.palette import PALETTE
from graphics.ui_art import band_hue
from simulation.ai.affect import LEAVE_JOB, PUSH, TAKE_JOB, TASK
from simulation.work.work_system import Expected
from simulation.world import SimulationWorld
from ui.button import HEIGHT as BUTTON_HEIGHT
from ui.button import Button
from ui.labels import describe_holders, describe_obstacle, describe_shifts, describe_vacancy
from ui.panel import draw_panel

PANEL_WIDTH = 250
PADDING = 5
# Tight enough for every post to fit above the minimap.
ROW_HEIGHT = LINE_HEIGHT * 2 + 1
SUGGEST_LABEL = "Proponer"
PUT_LABEL = "Poner"
PUSH_LABEL = "Apretar"
LEAVE_LABEL = "Quitar"
PUSHED = "va apretando"
NOBODY_SELECTED = "Elige a alguien para darle un puesto."
SELECTED_HINT = "Poner: lo hace. Proponer: lo decide."
# From how much faster or slower than a plain pair of hands it is worth saying so in colour.
GOOD_PACE, POOR_PACE = 1.05, 0.95
PUSH_POST_INTENT = ("push_post",)
LEAVE_POST_INTENT = ("leave_post",)
# What telling it is, as the simulation knows it.
PUT_KIND, PUSH_KIND, LEAVE_KIND = f"{TASK}:{TAKE_JOB}", f"{TASK}:{PUSH}", f"{TASK}:{LEAVE_JOB}"


def suggest_intent(job_id: str) -> tuple[str, str]:
    return ("suggest", job_id)


def put_intent(job_id: str) -> tuple[str, str]:
    return ("put", job_id)


@dataclass(frozen=True)
class PostRow:
    """One job as the board shows it."""

    job_id: str
    title: str
    holders: str
    vacant: bool
    # Whether the selected resident could be asked to take it, and if not, why, in a few words.
    can_suggest: bool
    obstacle: str = ""
    # What the selected resident would make of it, in a few letters, and whether that is more
    # or less than a plain pair of hands: 1, -1, or 0 for much the same.
    would_make: str = ""
    standing: int = 0
    # Whether they can be put to it there and then, which is an order.
    can_put: bool = False
    # Whether it is theirs already; and then whether they can be told to push it or to leave
    # it, and whether they are pushing it now.
    own: bool = False
    can_push: bool = False
    can_leave: bool = False
    pushed: bool = False


def describe_expected(expected: Expected) -> str:
    """What somebody would make of a post, in a few letters: how many times as fast as a plain
    pair of hands, and how many units a day where it makes any."""
    pace = f"x{expected.pace:.1f}".replace(".", ",")
    return pace if expected.per_day is None else f"{pace} · {round(expected.per_day)}/día"


def post_rows(world: SimulationWorld, selected_id: str | None) -> list[PostRow]:
    """The jobs that have a post on this map, the ones the settlement misses most first."""
    selected = world.residents.get(selected_id or "")
    stations = {placed.kind for placed in world.interactables.values()}
    jobs = [job for job in world.registries.jobs.values() if any(kind in stations for kind in job.stations)]
    options = {option.kind: option for option in world.affect_options(selected.resident_id)} if selected else {}
    free = {target for target, _name in options[PUT_KIND].targets} if PUT_KIND in options else set()
    rows = []
    for job in sorted(jobs, key=lambda job: -job.priority):
        vacancy = describe_vacancy(world, job.job_id)
        holders = describe_holders(world, job.job_id)
        code = world.interventions.suggestion_obstacle(world, selected.resident_id, job.job_id) if selected else None
        expected = world.work.expected(world, selected, job) if selected is not None and not selected.away else None
        own = selected is not None and selected.job_id == job.job_id
        rows.append(
            PostRow(
                job_id=job.job_id,
                title=f"{job.name} ({describe_shifts(job)})",
                holders=f"{holders} · {vacancy}" if vacancy is not None else holders,
                vacant=vacancy is not None,
                can_suggest=selected is not None and code is None,
                obstacle=describe_obstacle(code),
                would_make=describe_expected(expected) if expected is not None else "",
                standing=0 if expected is None else (expected.pace >= GOOD_PACE) - (expected.pace <= POOR_PACE),
                can_put=job.job_id in free,
                own=own,
                can_push=own and PUSH_KIND in options,
                can_leave=own and LEAVE_KIND in options,
                pushed=own and world.rush.pushed(world, selected),
            )
        )
    return rows


def job_board_height(world: SimulationWorld) -> int:
    return PADDING * 2 + LINE_HEIGHT + 2 + ROW_HEIGHT * len(post_rows(world, None)) + LINE_HEIGHT


def board_buttons(
    font: BitmapFont, rect: pygame.Rect, world: SimulationWorld, selected_id: str | None
) -> list[Button]:
    """The buttons of the board, on the second line of each post, from its right: for a post
    that is the selected resident's, pushing it and leaving it; for any other, putting them to
    it, which is an order, and proposing it, which they answer."""
    buttons = []
    y = rect.y + PADDING + LINE_HEIGHT + 2
    for row in post_rows(world, selected_id):
        if row.own:
            wanted = [(LEAVE_LABEL, LEAVE_POST_INTENT, row.can_leave), (PUSH_LABEL, PUSH_POST_INTENT, row.can_push)]
        else:
            wanted = [
                (SUGGEST_LABEL, suggest_intent(row.job_id), row.can_suggest),
                (PUT_LABEL, put_intent(row.job_id), row.can_put),
            ]
        right = rect.right - PADDING
        for label, intent, offered in wanted:
            if not offered:
                continue
            button = Button.at(font, 0, y + LINE_HEIGHT + (LINE_HEIGHT - BUTTON_HEIGHT) // 2, label, intent)
            button.rect.right = right
            right = button.rect.left - 2
            buttons.append(button)
        y += ROW_HEIGHT
    return buttons


def suggest_buttons(
    font: BitmapFont, rect: pygame.Rect, world: SimulationWorld, selected_id: str | None
) -> list[Button]:
    """A button beside each job the selected resident could be asked to take."""
    return [
        button
        for button in board_buttons(font, rect, world, selected_id)
        if isinstance(button.intent, tuple) and button.intent[0] == "suggest"
    ]


def draw_job_board(
    target: pygame.Surface,
    font: BitmapFont,
    rect: pygame.Rect,
    world: SimulationWorld,
    selected_id: str | None,
) -> None:
    draw_panel(target, rect, band=PADDING + LINE_HEIGHT, band_color=band_hue("work"))
    x, y = rect.x + PADDING, rect.y + PADDING
    font.draw(target, "Puestos", (x, y), PALETTE["paper"])
    y += LINE_HEIGHT + 2
    buttons = board_buttons(font, rect, world, selected_id)
    right = rect.right - PADDING
    for row in post_rows(world, selected_id):
        second = y + LINE_HEIGHT
        mine = [button for button in buttons if y <= button.rect.centery < y + ROW_HEIGHT]
        # First line: the post, and at its end what whoever is selected would make of it.
        made = row.would_make
        made_left = right - font.width(made) if made else right
        if made:
            font.draw(target, made, (made_left, y), PALETTE[("bone", "lichen", "ember")[row.standing]])
        title = font.truncate(row.title, made_left - 4 - x)
        font.draw(target, title, (x, y), PALETTE["ember" if row.vacant else "bone"])
        # Second line: who holds it, and at its end what can be done about it.
        edge = min((button.rect.left for button in mine), default=right)
        note = PUSHED if row.pushed else (row.obstacle if not mine and not row.own else "")
        if note:
            note = font.truncate(note, rect.width // 2)
            edge -= font.width(note) + (2 if mine else 0)
            font.draw(target, note, (edge, second), PALETTE["ember" if row.pushed else "iron"])
        holders = font.truncate(row.holders, edge - 4 - x)
        font.draw(target, holders, (x, second), PALETTE["lamp" if row.vacant else "stone"])
        for button in mine:
            button.draw(target, font)
        y += ROW_HEIGHT
    selected = world.residents.get(selected_id or "")
    hint = NOBODY_SELECTED if selected is None else SELECTED_HINT
    font.draw(target, font.truncate(hint, rect.width - PADDING * 2), (x, y), PALETTE["dust"])
