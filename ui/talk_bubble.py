"""What is seen over somebody who is talking (P62): the picture of the thing they talk of, the
face of whoever it is about, or the words where it is neither.

It reads the simulation and changes nothing.
"""

import pygame

from graphics.face_renderer import MARKER_SIZE, FaceRenderer
from graphics.font import ELLIPSIS, LINE_HEIGHT, BitmapFont
from graphics.item_icons import ICON_SIZE, ItemIcons
from graphics.palette import PALETTE
from simulation.residents.resident import Resident
from simulation.social.talk import Shown
from simulation.world import SimulationWorld
from ui.panel import draw_item

# The two of a talk take turns to speak, this many game minutes each, whoever brought it up first.
TURN_MINUTES = 4
PADDING = 2
# How far the tail reaches down towards whoever speaks.
TAIL = 3
# The most room the words of a bubble take, and the most lines of them.
TEXT_WIDTH = 92
TEXT_LINES = 3


def bubble_of(world: SimulationWorld, resident: Resident) -> Shown | None:
    """What is over a resident right now: a phrase of their own whenever one comes out, and
    otherwise what the talk is about, while it is their turn to speak."""
    said = world.talk.saying(world, resident)
    if said:
        return Shown(text=said)
    shown = world.talk.shown(world, resident)
    activity = resident.activity
    if shown is None or activity is None:
        return None
    turn = ((world.clock.total_minutes - activity.began_at) // TURN_MINUTES) % 2
    return shown if (turn == 0) == activity.brought else None


def said_aloud(shown: Shown | None) -> str:
    """What of a bubble is words, and so can be said out loud. A picture says nothing."""
    return shown.text if shown is not None else ""


def bubble_lines(font: BitmapFont, text: str) -> list[str]:
    """The words of a bubble as the lines they are written in, cut short where there are too many."""
    lines = font.wrap(text, TEXT_WIDTH)
    if len(lines) > TEXT_LINES:
        lines = lines[:TEXT_LINES]
        lines[-1] = font.truncate(lines[-1] + ELLIPSIS, TEXT_WIDTH)
    return lines


def bubble_size(font: BitmapFont, shown: Shown) -> tuple[int, int]:
    """How large the bubble for it is, without its tail."""
    if shown.item_id is not None:
        return ICON_SIZE[0] + PADDING * 2 + 2, ICON_SIZE[1] + PADDING * 2 + 2
    if shown.face_id is not None:
        return MARKER_SIZE[0] + PADDING * 2 + 2, MARKER_SIZE[1] + PADDING * 2 + 2
    lines = bubble_lines(font, shown.text)
    width = max((font.width(line) for line in lines), default=0)
    return width + PADDING * 2 + 4, len(lines) * LINE_HEIGHT + PADDING * 2


def _rounded(target: pygame.Surface, rect: pygame.Rect) -> None:
    """A box of paper with its four corner pixels cut off, outlined."""
    pygame.draw.rect(target, PALETTE["ink"], rect.inflate(-2, 0))
    pygame.draw.rect(target, PALETTE["ink"], rect.inflate(0, -2))
    pygame.draw.rect(target, PALETTE["paper"], rect.inflate(-2, -2))


def draw_talk_bubble(
    target: pygame.Surface,
    font: BitmapFont,
    icons: ItemIcons,
    faces: FaceRenderer,
    shown: Shown,
    top_centre: tuple[int, int],
    within: pygame.Rect | None = None,
) -> pygame.Rect:
    """Draw a bubble whose tail points down at `top_centre`'s column, its top at that height.
    `within` is where it has to stay: it slides along sooner than leave it. Returns the bubble."""
    width, height = bubble_size(font, shown)
    rect = pygame.Rect(top_centre[0] - width // 2, top_centre[1], width, height)
    if within is not None:
        rect.x = max(within.left, min(within.right - width, rect.x))
    _rounded(target, rect)
    # The tail stays over whoever speaks, wherever the bubble had to slide to.
    tail_x = max(rect.left + 2, min(rect.right - 4, top_centre[0] - 1))
    target.fill(PALETTE["paper"], (tail_x, rect.bottom - 1, 2, 1))
    for reach in range(TAIL):
        target.fill(PALETTE["ink"], (tail_x, rect.bottom + reach, 2 if reach < TAIL - 1 else 1, 1))
    target.fill(PALETTE["paper"], (tail_x, rect.bottom, 1, max(0, TAIL - 2)))
    inside = rect.inflate(-PADDING * 2 - 2, -PADDING * 2 - 2)
    if shown.item_id is not None:
        draw_item(target, icons, shown.item_id, pygame.Rect(inside.topleft, ICON_SIZE))
    elif shown.face_id is not None:
        target.blit(faces.marker(shown.face_id), inside.topleft)
    else:
        y = rect.y + PADDING
        for line in bubble_lines(font, shown.text):
            font.draw(target, line, (rect.centerx - font.width(line) // 2, y), PALETTE["ink"])
            y += LINE_HEIGHT
    return rect
