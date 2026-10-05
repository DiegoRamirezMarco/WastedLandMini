"""Panel listing the settlement's posts: who holds each, which stand empty, and a way to propose one."""

from dataclasses import dataclass

import pygame

from graphics.font import LINE_HEIGHT, BitmapFont
from graphics.palette import PALETTE
from simulation.world import SimulationWorld
from ui.button import HEIGHT as BUTTON_HEIGHT
from ui.button import Button
from ui.labels import describe_holders, describe_shifts, describe_vacancy
from ui.panel import draw_panel

PANEL_WIDTH = 250
PADDING = 5
ROW_HEIGHT = LINE_HEIGHT * 2 + 3
SUGGEST_LABEL = "Proponer"
NOBODY_SELECTED = "Elige a alguien para proponerle un puesto."


def suggest_intent(job_id: str) -> tuple[str, str]:
    return ("suggest", job_id)


@dataclass(frozen=True)
class PostRow:
    """One job as the board shows it."""

    job_id: str
    title: str
    holders: str
    vacant: bool
    # Whether the selected resident could be asked to take it: a free post, and not theirs already.
    can_suggest: bool


def post_rows(world: SimulationWorld, selected_id: str | None) -> list[PostRow]:
    """The jobs that have a post on this map, the ones the settlement misses most first."""
    selected = world.residents.get(selected_id or "")
    stations = {placed.kind for placed in world.interactables.values()}
    jobs = [job for job in world.registries.jobs.values() if job.station in stations]
    rows = []
    for job in sorted(jobs, key=lambda job: -job.priority):
        vacancy = describe_vacancy(world, job.job_id)
        holders = describe_holders(world, job.job_id)
        rows.append(
            PostRow(
                job_id=job.job_id,
                title=f"{job.name} ({describe_shifts(job)})",
                holders=f"{holders} · {vacancy}" if vacancy is not None else holders,
                vacant=vacancy is not None,
                can_suggest=selected is not None
                and selected.job_id != job.job_id
                and world.staffing.free_post(world, job) is not None,
            )
        )
    return rows


def job_board_height(world: SimulationWorld) -> int:
    return PADDING * 2 + LINE_HEIGHT + 2 + ROW_HEIGHT * len(post_rows(world, None)) + LINE_HEIGHT


def suggest_buttons(
    font: BitmapFont, rect: pygame.Rect, world: SimulationWorld, selected_id: str | None
) -> list[Button]:
    """A button beside each job the selected resident could be asked to take."""
    buttons = []
    y = rect.y + PADDING + LINE_HEIGHT + 2
    for row in post_rows(world, selected_id):
        if row.can_suggest:
            button = Button.at(font, 0, y + (ROW_HEIGHT - BUTTON_HEIGHT) // 2, SUGGEST_LABEL, suggest_intent(row.job_id))
            button.rect.right = rect.right - PADDING
            buttons.append(button)
        y += ROW_HEIGHT
    return buttons


def draw_job_board(
    target: pygame.Surface,
    font: BitmapFont,
    rect: pygame.Rect,
    world: SimulationWorld,
    selected_id: str | None,
) -> None:
    draw_panel(target, rect)
    x, y = rect.x + PADDING, rect.y + PADDING
    font.draw(target, "Puestos", (x, y), PALETTE["paper"])
    y += LINE_HEIGHT + 2
    buttons = {button.intent: button for button in suggest_buttons(font, rect, world, selected_id)}
    for row in post_rows(world, selected_id):
        button = buttons.get(suggest_intent(row.job_id))
        width = (button.rect.left - 4 if button is not None else rect.right - PADDING) - x
        font.draw(target, font.truncate(row.title, width), (x, y), PALETTE["ember" if row.vacant else "bone"])
        holders = font.truncate(row.holders, width)
        font.draw(target, holders, (x, y + LINE_HEIGHT), PALETTE["lamp" if row.vacant else "stone"])
        if button is not None:
            button.draw(target, font)
        y += ROW_HEIGHT
    selected = world.residents.get(selected_id or "")
    hint = NOBODY_SELECTED if selected is None else f"Proponer un puesto a {selected.name}: decide por su cuenta."
    font.draw(target, font.truncate(hint, rect.width - PADDING * 2), (x, y), PALETTE["dust"])
