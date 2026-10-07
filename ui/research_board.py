"""Panel listing what there is to work out: what is known, what is in hand, and a way to choose what comes next."""

from dataclasses import dataclass

import pygame

from graphics.font import LINE_HEIGHT, BitmapFont
from graphics.palette import PALETTE
from graphics.ui_art import band_hue
from simulation.work.research import CLOSED, IN_HAND, KNOWN, OPEN, SubjectDefinition
from simulation.world import SimulationWorld
from ui.button import HEIGHT as BUTTON_HEIGHT
from ui.button import Button
from ui.panel import draw_panel

PANEL_WIDTH = 300
PADDING = 5
# Tight enough for every subject the game comes with to fit above the minimap.
ROW_HEIGHT = LINE_HEIGHT * 2 + 1
STUDY_LABEL = "Estudiar"
STOP_LABEL = "Dejar"
NOBODY = "Nadie lleva el puesto de Estudio: hace falta una mesa de estudio y quien la ocupe."
SOMEBODY = "Lo estudia quien lleve el puesto de Estudio, en su turno."
KNOWN_TITLE = "Ya se sabe"
NOTHING_LEFT = "No queda nada por averiguar."
STATUS_COLOURS = {IN_HAND: "lamp", OPEN: "bone", CLOSED: "iron"}


def study_intent(subject_id: str | None) -> tuple[str, str | None]:
    return ("study", subject_id)


@dataclass(frozen=True)
class SubjectRow:
    """One subject as the board shows it."""

    subject_id: str
    title: str
    # What stands in its way or what it is for, in a few words.
    note: str
    status: str


def _note(world: SimulationWorld, subject: SubjectDefinition, status: str) -> str:
    subjects = world.registries.research.subjects
    if status == KNOWN:
        return "Ya se sabe"
    if status == CLOSED:
        missing = [subjects[each].name for each in subject.requires if not world.research.knows(world, each)]
        return f"Antes: {', '.join(missing)}"
    if subject.item is not None and subject.subject_id not in world.studies.supplied:
        item = world.registries.items.resolve(subject.item)
        units = f"{subject.count} de {item.name}" if subject.count > 1 else f"{item.article} {item.name}"
        return f"Pide {units}. {subject.text}"
    return subject.text


def subject_rows(world: SimulationWorld) -> list[SubjectRow]:
    """Every subject still to be worked out: the one in hand first, then what can be chosen, then what cannot yet."""
    order = {IN_HAND: 0, OPEN: 1, CLOSED: 2}
    rows = []
    for subject in world.research.subjects(world):
        status = world.research.status(world, subject)
        if status == KNOWN:
            continue
        done = round(world.research.fraction_done(world, subject) * 100)
        hours = max(1, round(subject.minutes / 60))
        title = f"{subject.name} ({hours} h)" if not done else f"{subject.name} ({done}%)"
        rows.append(SubjectRow(subject.subject_id, title, _note(world, subject, status), status))
    return sorted(rows, key=lambda row: order[row.status])


def known_lines(font: BitmapFont, world: SimulationWorld, width: int) -> list[str]:
    """What is known already, by name, in as many lines as it takes."""
    subjects = world.registries.research.subjects
    names = [subjects[each].name for each in world.studies.known if each in subjects]
    return font.wrap(f"{KNOWN_TITLE}: {', '.join(names)}", width) if names else []


def research_board_height(world: SimulationWorld, font: BitmapFont) -> int:
    known = len(known_lines(font, world, PANEL_WIDTH - PADDING * 2))
    return PADDING * 2 + LINE_HEIGHT + 2 + ROW_HEIGHT * len(subject_rows(world)) + LINE_HEIGHT * (known + 1) + 2


def study_buttons(font: BitmapFont, rect: pygame.Rect, world: SimulationWorld) -> list[Button]:
    """A button beside each subject that can be taken in hand, and one to put down the one that is."""
    buttons = []
    y = rect.y + PADDING + LINE_HEIGHT + 2
    for row in subject_rows(world):
        if row.status in (OPEN, IN_HAND):
            label = STUDY_LABEL if row.status == OPEN else STOP_LABEL
            intent = study_intent(row.subject_id if row.status == OPEN else None)
            button = Button.at(font, 0, y + (ROW_HEIGHT - BUTTON_HEIGHT) // 2, label, intent)
            button.rect.right = rect.right - PADDING
            buttons.append(button)
        y += ROW_HEIGHT
    return [button for button in buttons if button.rect.bottom <= rect.bottom - LINE_HEIGHT]


def _studying(world: SimulationWorld) -> bool:
    jobs = world.registries.jobs
    return any(
        (job := jobs.get(resident.job_id or "")) is not None and job.research for resident in world.residents.values()
    )


def draw_research_board(target: pygame.Surface, font: BitmapFont, rect: pygame.Rect, world: SimulationWorld) -> None:
    draw_panel(target, rect, band=PADDING + LINE_HEIGHT, band_color=band_hue("study"))
    x, y = rect.x + PADDING, rect.y + PADDING
    font.draw(target, "Estudio: lo que se sabe y lo que falta por saber", (x, y), PALETTE["paper"])
    y += LINE_HEIGHT + 2
    buttons = {button.rect.y: button for button in study_buttons(font, rect, world)}
    for row in subject_rows(world):
        if y + ROW_HEIGHT > rect.bottom - LINE_HEIGHT:
            break
        button = buttons.get(y + (ROW_HEIGHT - BUTTON_HEIGHT) // 2)
        width = (button.rect.left - 4 if button is not None else rect.right - PADDING) - x
        font.draw(target, font.truncate(row.title, width), (x, y), PALETTE[STATUS_COLOURS[row.status]])
        font.draw(target, font.truncate(row.note, width), (x, y + LINE_HEIGHT), PALETTE["stone" if row.status != CLOSED else "iron"])
        if button is not None:
            button.draw(target, font, active=row.status == IN_HAND)
        y += ROW_HEIGHT
    if not subject_rows(world):
        font.draw(target, NOTHING_LEFT, (x, y - LINE_HEIGHT), PALETTE["bone"])
    bottom = rect.bottom - PADDING - LINE_HEIGHT + 1
    for line in known_lines(font, world, rect.width - PADDING * 2):
        if y + LINE_HEIGHT > bottom:
            break
        font.draw(target, line, (x, y + 1), PALETTE["lichen"])
        y += LINE_HEIGHT
    hint = SOMEBODY if _studying(world) else NOBODY
    font.draw(target, font.truncate(hint, rect.width - PADDING * 2), (x, bottom), PALETTE["dust"])
