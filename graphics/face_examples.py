"""A plain face to start from: one picture for each kind of piece, to draw over or to throw away.

It is here so that putting pieces in place can be tried before anything has been drawn, as the
plain figure is for a body. Nobody is meant to keep it.
"""

from collections.abc import Callable

import pygame

from graphics.cartoon import LINE
from graphics.doll import HEAD_CANVAS, DollTemplate
from graphics.face import Head
from graphics.palette import Color
from graphics.ui_art import darker

Size = tuple[int, int]

WHITE: Color = (244, 240, 230)
IRIS: Color = (70, 96, 120)
HAIR: Color = (92, 56, 36)
LIPS: Color = (150, 58, 52)
CLEAR = (0, 0, 0, 0)


def _eye(size: Size, skin: Color, head: Head) -> pygame.Surface:
    paper = pygame.Surface(size, pygame.SRCALPHA)
    box = paper.get_rect().inflate(-size[0] // 2, -size[1] // 3)
    pygame.draw.ellipse(paper, LINE, box.inflate(6, 6))
    pygame.draw.ellipse(paper, WHITE, box)
    pygame.draw.circle(paper, IRIS, box.center, box.height // 2 - 1)
    pygame.draw.circle(paper, LINE, box.center, max(2, box.height // 4))
    pygame.draw.circle(paper, WHITE, (box.centerx + 2, box.centery - 3), 2)
    return paper


def _eye_shut(size: Size, skin: Color, head: Head) -> pygame.Surface:
    paper = pygame.Surface(size, pygame.SRCALPHA)
    box = paper.get_rect().inflate(-size[0] // 2, -size[1] // 3)
    # A lid down over it: a line that sags, with the lashes at its ends.
    pygame.draw.arc(paper, LINE, box.inflate(6, 0).move(0, -box.height // 2), 3.5, 5.9, 4)
    return paper


def _mouth_open(size: Size, skin: Color, head: Head) -> pygame.Surface:
    paper = pygame.Surface(size, pygame.SRCALPHA)
    box = pygame.Rect(0, 0, size[0] * 3 // 10, size[1] * 3 // 5)
    box.center = (size[0] // 2, size[1] // 2)
    pygame.draw.ellipse(paper, LINE, box.inflate(6, 6))
    pygame.draw.ellipse(paper, darker(LIPS, 0.45), box)
    # A tongue at the foot of it.
    pygame.draw.ellipse(paper, LIPS, pygame.Rect(box.left + 2, box.centery + 1, box.width - 4, box.height // 2 - 1))
    return paper


def _brow(size: Size, skin: Color, head: Head) -> pygame.Surface:
    paper = pygame.Surface(size, pygame.SRCALPHA)
    left, right, middle = size[0] // 4, size[0] * 3 // 4, size[1] // 2
    # Level, a little higher in its middle: it says nothing until the face it is on feels something.
    points = [(left, middle + 1), (size[0] // 2, middle - 1), (right, middle + 1)]
    pygame.draw.lines(paper, HAIR, False, points, 6)
    for end in points:
        pygame.draw.circle(paper, HAIR, end, 3)
    return paper


def _mouth(size: Size, skin: Color, head: Head) -> pygame.Surface:
    paper = pygame.Surface(size, pygame.SRCALPHA)
    box = pygame.Rect(0, 0, size[0] * 2 // 5, size[1] // 2)
    box.center = (size[0] // 2, size[1] // 2 - box.height // 4)
    for color, grow in ((LINE, 3), (LIPS, 0)):
        pygame.draw.ellipse(paper, color, box.inflate(grow * 2, grow * 2))
    # Only the lower half of the oval is a smile.
    paper.fill(CLEAR, (0, 0, size[0], box.centery))
    pygame.draw.line(paper, LINE, (box.left - 3, box.centery), (box.right + 3, box.centery), 3)
    return paper


def _nose(size: Size, skin: Color, head: Head) -> pygame.Surface:
    paper = pygame.Surface(size, pygame.SRCALPHA)
    middle, top, bottom = size[0] // 2, size[1] // 4, size[1] * 3 // 4
    shape = [(middle - 3, top), (middle + 3, top), (middle + 8, bottom - 6), (middle + 4, bottom), (middle - 4, bottom), (middle - 8, bottom - 6)]
    pygame.draw.polygon(paper, darker(skin, 0.12), shape)
    pygame.draw.lines(paper, LINE, False, [shape[1], shape[2], shape[3], shape[4], shape[5]], 3)
    return paper


def _ear(size: Size, skin: Color, head: Head) -> pygame.Surface:
    paper = pygame.Surface(size, pygame.SRCALPHA)
    box = paper.get_rect().inflate(-size[0] // 2, -size[1] // 2)
    pygame.draw.ellipse(paper, LINE, box.inflate(6, 6))
    pygame.draw.ellipse(paper, skin, box)
    pygame.draw.arc(paper, darker(skin, 0.3), box.inflate(-8, -10), 0.6, 5.6, 2)
    return paper


def _hair_back(size: Size, skin: Color, head: Head) -> pygame.Surface:
    """The hair behind a head: more of it than there is head, and on down the back."""
    paper = pygame.Surface(size, pygame.SRCALPHA)
    mass = pygame.Rect(0, 0, round(head.across * 2.5), round(head.down * 2.3))
    mass.center = (round(head.x), round(head.y - head.down * 0.02))
    fall = pygame.Rect(mass.left + 4, mass.centery, mass.width - 8, round(head.down * 3.2))
    fall.bottom = min(fall.bottom, size[1] - 4)
    for color, grow in ((LINE, 3), (darker(HAIR, 0.22), 0)):
        pygame.draw.ellipse(paper, color, mass.inflate(grow * 2, grow * 2))
        pygame.draw.rect(paper, color, fall.inflate(grow * 2, grow * 2), border_radius=round(head.across * 0.6))
    # The line round the one is not wanted across the other.
    pygame.draw.ellipse(paper, darker(HAIR, 0.22), mass)
    return paper


def _hair(size: Size, skin: Color, head: Head) -> pygame.Surface:
    """The hair in front of a head: a fringe over the top of it, with the face left clear under it."""
    paper = pygame.Surface(size, pygame.SRCALPHA)
    cap = pygame.Rect(0, 0, round(head.across * 2.14), round(head.down * 1.3))
    cap.center = (round(head.x), round(head.y - head.down * 0.46))
    face = pygame.Rect(0, 0, round(head.across * 1.7), round(head.down * 1.9))
    face.center = (round(head.x), round(head.y + head.down * 0.36))
    for color, grow in ((LINE, 3), (HAIR, 0)):
        pygame.draw.ellipse(paper, color, cap.inflate(grow * 2, grow * 2))
    cut = pygame.Surface(size, pygame.SRCALPHA)
    pygame.draw.ellipse(cut, (255, 255, 255, 255), face)
    paper.blit(cut, (0, 0), special_flags=pygame.BLEND_RGBA_SUB)
    pygame.draw.ellipse(paper, LINE, face.inflate(6, 6), 3)
    # The line round the face is only wanted where there is hair beside it.
    keep = pygame.Surface(size, pygame.SRCALPHA)
    pygame.draw.ellipse(keep, (255, 255, 255, 255), cap.inflate(6, 6))
    paper.blit(keep, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
    return paper


EXAMPLES: dict[str, Callable[[Size, Color, Head], pygame.Surface]] = {
    "eye": _eye, "brow": _brow, "mouth": _mouth, "nose": _nose, "ear": _ear, "hair": _hair, "hair_back": _hair_back,
    "eye_shut": _eye_shut, "mouth_open": _mouth_open,
}


def plain_head(template: DollTemplate, skin: Color, line: int) -> pygame.Surface:
    """A head with nothing on it and no side to it: an egg on the head's paper, where the
    template has a head. It is what a face is put on until somebody draws their own."""
    paper = pygame.Surface(template.canvases[HEAD_CANVAS], pygame.SRCALPHA)
    spec = next((each for each in template.parts.values() if each.canvas == HEAD_CANVAS and each.whole), None)
    if spec is None:
        return paper
    box = pygame.Rect(0, 0, round(spec.radius * 1.72), round(spec.radius * 2.0))
    box.center = (round(spec.end[0]), round(spec.end[1]))
    pygame.draw.ellipse(paper, LINE, box.inflate(line * 2, line * 2))
    pygame.draw.ellipse(paper, skin, box)
    return paper


def skin_of(head_drawing: pygame.Surface, head: Head, fallback: Color = (214, 170, 130)) -> Color:
    """The colour a head is in its middle, which is taken for its skin."""
    at = (min(head_drawing.get_width() - 1, max(0, round(head.x))), min(head_drawing.get_height() - 1, max(0, round(head.y))))
    red, green, blue, alpha = head_drawing.get_at(at)
    return (red, green, blue) if alpha else fallback


def example(kind_id: str, size: Size, skin: Color, head: Head) -> pygame.Surface | None:
    """A plain picture of one kind of piece, on paper of a size. None for a kind there is none for."""
    draw = EXAMPLES.get(kind_id)
    return draw(size, skin, head) if draw is not None else None
