"""The way of somebody who is out of the settlement: a line from it to where they are bound,
their face on it as far along as they are, and what there is to say of it under that."""

import pygame

from graphics.font import LINE_HEIGHT, BitmapFont
from graphics.palette import PALETTE
from ui.panel import draw_panel

PADDING = 6
# How thick the line of the way is, and how far the posts at its ends stand over and under it.
WAY = 2
POST = 3
# How far from the face the mark of which way they go is, and how long it is.
ARROW_GAP = 3
ARROW = 4


def trip_bar_height(font: BitmapFont, width: int, face_height: int, lines: tuple[str, ...]) -> int:
    """How tall the bar is for what there is to say in it."""
    said = sum(len(font.wrap(line, width - PADDING * 2)) for line in lines if line)
    return PADDING + face_height + POST + WAY + POST + 1 + LINE_HEIGHT * (1 + said) + PADDING - 2


def way_ends(rect: pygame.Rect, face_width: int) -> tuple[int, int]:
    """Where along the bar the way begins and ends: the face is whole at either, and so is
    the mark of which way they go beside it."""
    room = PADDING + face_width // 2 + ARROW_GAP + ARROW
    return (rect.x + room, rect.right - room)


def face_spot(rect: pygame.Rect, face: pygame.Surface, share: float) -> pygame.Rect:
    """Where the face goes for somebody that far from the settlement, from 0 at it to 1 at the far end."""
    left, right = way_ends(rect, face.get_width())
    at = left + round(min(1.0, max(0.0, share)) * (right - left))
    return face.get_rect(midtop=(at, rect.y + PADDING))


def draw_trip_bar(
    target: pygame.Surface,
    font: BitmapFont,
    rect: pygame.Rect,
    face: pygame.Surface,
    share: float,
    heading_back: bool,
    stopped: bool,
    ends: tuple[str, str],
    lines: tuple[str, ...],
    marks: tuple[float, ...] = (),
) -> pygame.Rect:
    """Draw the way and whoever is on it. Returns where their face was put. `marks` are how
    far along it one stretch of country gives way to the next, from 0 to 1."""
    draw_panel(target, rect)
    left, right = way_ends(rect, face.get_width())
    spot = face_spot(rect, face, share)
    y = spot.bottom + POST
    pygame.draw.rect(target, PALETTE["iron"], (left, y, right - left, WAY))
    # What is lit is the way home: all there is of it to walk still, or to walk again.
    pygame.draw.rect(target, PALETTE["lamp"], (left, y, spot.centerx - left, WAY))
    for end in (left, right):
        pygame.draw.rect(target, PALETTE["bone"], (end - 1, y - POST, 2, POST * 2 + WAY))
    for mark in marks:
        pygame.draw.rect(target, PALETTE["dust"], (left + round(mark * (right - left)), y - 1, 1, WAY + 2))
    target.blit(face, spot)
    if not stopped:
        # A mark beside the face, pointing the way they go.
        way = -1 if heading_back else 1
        tip = (spot.centerx + way * (face.get_width() // 2 + ARROW_GAP + ARROW), spot.centery)
        back = tip[0] - way * ARROW
        pygame.draw.polygon(target, PALETTE["glow"], [tip, (back, tip[1] - ARROW), (back, tip[1] + ARROW)])
    top = y + WAY + POST + 1
    font.draw(target, ends[0], (rect.x + PADDING, top), PALETTE["dust"])
    font.draw(target, ends[1], (rect.right - PADDING - font.width(ends[1]), top), PALETTE["dust"])
    top += LINE_HEIGHT
    for index, line in enumerate(line for line in lines if line):
        for part in font.wrap(line, rect.width - PADDING * 2):
            color = PALETTE["paper" if index == 0 else "bone"]
            font.draw(target, part, (rect.centerx - font.width(part) // 2, top), color)
            top += LINE_HEIGHT
    return spot
