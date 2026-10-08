"""A child under ten as it is seen: a head and a blanket.

It is on the back of whoever carries it, or in the bed, on the table or on the ground where it
was put down. The blanket is the game's, drawn in its own hand. The head is the child's own:
as somebody drew it, or else the face the game has for them.
"""

import pygame

from graphics.cartoon import Sheet
from graphics.palette import Color
from graphics.ui_art import darker

BLANKET: Color = (236, 214, 158)
# The blanket on a square of this many units a side, and how much taller than wide the whole bundle is.
UNITS = 20.0
TALL = 1.3
# How wide the head is, as a share of the bundle, and how far down the blanket starts.
HEAD_SHARE = 0.7
BLANKET_FROM = 0.34


def blanket(width: int, color: Color = BLANKET) -> pygame.Surface:
    """The blanket a child is wrapped in, with room over it for a head."""
    height = max(1, round(width * TALL))
    tall = UNITS * TALL
    sheet = Sheet((width, height), width / UNITS, line=1.9)
    top = tall * BLANKET_FROM
    sheet.ground_shade(2.0, tall - 4.2, 16.0, 3.6, 60)
    sheet.oval(1.6, top, 16.8, tall - top - 1.4, color, outline=True)
    # Where it is folded over, and tucked in.
    sheet.stroke([(4.6, top + 3.2), (10.0, top + 9.0), (15.4, top + 3.2)], darker(color, 0.34), 1.5)
    sheet.stroke([(10.0, top + 9.0), (10.0, tall - 4.4)], darker(color, 0.34), 1.2)
    sheet.oval(4.2, top + 1.2, 5.0, 3.2, (255, 255, 255), 70)
    return sheet.finished()


def bundle_picture(head: pygame.Surface | None, width: int, color: Color = BLANKET) -> pygame.Surface:
    """A child in its blanket, `width` pixels across: the blanket, and the head over the top of it."""
    picture = blanket(width, color)
    if head is None or head.get_width() <= 0 or head.get_height() <= 0:
        return picture
    across = max(1, round(width * HEAD_SHARE))
    down = max(1, round(across * head.get_height() / head.get_width()))
    small = pygame.transform.smoothscale(head, (across, down))
    # The head sits on the top of the blanket, its chin a little way into it.
    chin = round(picture.get_height() * (BLANKET_FROM + 0.12))
    picture.blit(small, ((width - across) // 2, max(0, chin - down)))
    return picture


def ground_blanket(width: int, height: int, color: Color = BLANKET) -> pygame.Surface:
    """The blanket over somebody asleep on the ground: a long heap, with whoever is under it
    making a rise in it, and room at one end for their head."""
    sheet = Sheet((width, height), width / UNITS, line=1.7)
    tall = UNITS * height / width
    sheet.ground_shade(1.0, tall - 3.4, 18.0, 3.2, 60)
    sheet.oval(4.4, tall * 0.26, 14.6, tall * 0.68, color, outline=True)
    sheet.stroke([(8.0, tall * 0.44), (12.0, tall * 0.62), (16.6, tall * 0.5)], darker(color, 0.34), 1.3)
    sheet.oval(7.0, tall * 0.34, 5.0, tall * 0.16, (255, 255, 255), 70)
    return sheet.finished()


def bundle_height(width: int) -> int:
    return max(1, round(width * TALL))

