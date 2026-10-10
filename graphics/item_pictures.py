"""What is carried and kept, as the game draws it: one picture for each of the items it comes with.

The same hand as the furniture (`graphics.cartoon`): thick dark lines and flat colour, drawn at
whatever size it is asked for. An item a pack brings, or one the player has drawn in the item
editor, keeps its own picture: these are only what the game shows where nobody has made one.

Everything is measured in hundredths of the side of the picture.
"""

from collections.abc import Callable

import pygame

from graphics.cartoon import (
    BLUE,
    DARK_METAL,
    GLASS,
    GREEN,
    LINE,
    METAL,
    ORANGE,
    PALE_WOOD,
    PAPER,
    RED,
    RUST,
    WOOD,
    YELLOW,
    Sheet,
)
from graphics.ui_art import darker, lighter

Painter = Callable[[Sheet], None]


def _canned_beans(s: Sheet) -> None:
    s.box(24, 26, 52, 56, METAL, 6)
    s.box(24, 40, 52, 26, RED, 0)
    s.oval(40, 46, 20, 14, (236, 200, 150), 255, outline=True)
    s.oval(24, 16, 52, 22, lighter(METAL, 0.3), 255, outline=True)
    s.oval(33, 21, 34, 12, darker(METAL, 0.1), 255, outline=True)
    s.shade(29, 70, 8, 8, lighter(METAL, 0.4), 255, 3)


def _old_radio(s: Sheet) -> None:
    s.stroke([(70, 30), (84, 6)], LINE, 3.4)
    s.oval(80, 2, 9, 9, RED, 255, outline=True)
    s.box(12, 28, 76, 56, RUST, 8)
    s.box(19, 36, 34, 40, (44, 36, 34), 4)
    for y in (45, 55, 65):
        s.stroke([(24, y), (48, y)], (130, 108, 96), 2.4)
    s.oval(59, 37, 22, 22, YELLOW, 255, outline=True)
    s.stroke([(70, 48), (76, 41)], LINE, 2.6)
    s.oval(60, 66, 8, 8, GREEN)
    s.oval(72, 66, 8, 8, RED)


def _vegetables(s: Sheet) -> None:
    s.poly([(30, 44), (52, 44), (44, 90)], ORANGE)
    for y in (56, 68):
        s.stroke([(34, y), (42, y)], darker(ORANGE, 0.3), 2)
    s.poly([(36, 46), (30, 20), (42, 34), (46, 14), (50, 34), (58, 22), (50, 46)], GREEN)
    s.oval(52, 50, 38, 36, RED, 255, outline=True)
    s.oval(60, 56, 10, 8, lighter(RED, 0.4))
    s.poly([(66, 52), (70, 42), (76, 52)], GREEN)


def _stew(s: Sheet) -> None:
    for x, sway in ((38, 5), (58, -5)):
        s.stroke([(x, 34), (x + sway, 22), (x - sway, 10)], (236, 236, 230), 3)
    s.poly([(10, 46), (90, 46), (76, 84), (24, 84)], PALE_WOOD)
    s.oval(10, 34, 80, 26, lighter(PALE_WOOD, 0.2), 255, outline=True)
    s.oval(18, 38, 64, 17, (150, 92, 50))
    s.oval(30, 42, 12, 8, ORANGE)
    s.oval(52, 41, 10, 7, GREEN)
    s.oval(64, 45, 9, 6, (236, 200, 150))
    s.shade(28, 70, 44, 6, darker(PALE_WOOD, 0.2), 255, 3)


def _water(s: Sheet) -> None:
    s.box(40, 6, 20, 14, BLUE, 3)
    s.box(26, 18, 48, 72, GLASS, 14)
    s.shade(30, 44, 40, 42, (104, 176, 214), 255, 10)
    s.stroke([(27, 44), (73, 44)], darker(BLUE, 0.1), 2)
    s.shade(33, 26, 7, 50, PAPER, 150, 3)


def _fuel(s: Sheet) -> None:
    s.box(16, 26, 64, 64, RED, 8)
    s.poly([(16, 26), (40, 10), (58, 10), (58, 26)], RED)
    s.box(60, 12, 16, 12, DARK_METAL, 3)
    s.box(26, 16, 22, 8, (60, 30, 28), 3)
    s.shade(21, 34, 8, 48, lighter(RED, 0.3), 255, 3)
    s.poly([(48, 44), (58, 62), (48, 76), (38, 62)], YELLOW)
    s.stroke([(30, 40), (66, 40)], darker(RED, 0.4), 2.4)


def _medicine(s: Sheet) -> None:
    s.box(14, 28, 72, 58, PAPER, 9)
    s.box(36, 16, 28, 16, darker(PAPER, 0.16), 5)
    s.shade(44, 40, 12, 36, RED, 255, 2)
    s.shade(32, 52, 36, 12, RED, 255, 2)
    s.shade(19, 76, 62, 6, darker(PAPER, 0.14), 255, 3)


def _baton(s: Sheet) -> None:
    s.stroke([(22, 80), (78, 22)], LINE, 19)
    s.stroke([(22, 80), (78, 22)], WOOD, 12)
    s.stroke([(30, 66), (70, 26)], lighter(WOOD, 0.3), 3)
    s.stroke([(18, 84), (34, 68)], LINE, 22)
    s.stroke([(18, 84), (34, 68)], darker(WOOD, 0.4), 15)


def _rusty_knife(s: Sheet) -> None:
    s.poly([(44, 52), (86, 12), (90, 22), (56, 62)], (196, 190, 180))
    s.oval(64, 30, 10, 8, RUST)
    s.oval(74, 22, 6, 5, RUST)
    s.stroke([(36, 52), (60, 70)], LINE, 9)
    s.stroke([(36, 52), (60, 70)], METAL, 4)
    s.stroke([(16, 86), (44, 58)], LINE, 19)
    s.stroke([(16, 86), (44, 58)], WOOD, 12)


def _sledge(s: Sheet) -> None:
    s.stroke([(16, 88), (66, 30)], LINE, 15)
    s.stroke([(16, 88), (66, 30)], WOOD, 9)
    s.poly([(48, 22), (72, 6), (92, 30), (68, 46)], METAL)
    s.stroke([(58, 20), (72, 12)], lighter(METAL, 0.4), 3)


def _pipe_pistol(s: Sheet) -> None:
    # A length of pipe on a block of wood: what somebody made to fire once and again.
    s.stroke([(18, 40), (84, 40)], LINE, 17)
    s.stroke([(18, 40), (84, 40)], METAL, 10)
    s.stroke([(24, 37), (78, 37)], lighter(METAL, 0.4), 2.4)
    s.poly([(20, 46), (46, 46), (40, 86), (18, 82)], WOOD)
    s.stroke([(46, 50), (56, 60), (46, 62)], LINE, 4)
    s.oval(84, 40, 4, 4, LINE)


def _rifle(s: Sheet) -> None:
    s.poly([(6, 70), (34, 52), (44, 62), (16, 90)], WOOD)
    s.stroke([(34, 56), (94, 12)], LINE, 12)
    s.stroke([(34, 56), (94, 12)], METAL, 6)
    s.stroke([(40, 60), (62, 44)], LINE, 15)
    s.stroke([(40, 60), (62, 44)], darker(WOOD, 0.2), 9)
    s.stroke([(44, 64), (52, 72), (58, 62)], LINE, 4)


def _arc_thrower(s: Sheet) -> None:
    spark = (120, 230, 255)
    s.poly([(14, 52), (58, 36), (64, 56), (22, 74)], (70, 96, 116))
    s.poly([(20, 70), (40, 62), (38, 92), (22, 92)], darker(WOOD, 0.3))
    s.stroke([(58, 44), (84, 30)], LINE, 9)
    s.stroke([(58, 44), (84, 30)], METAL, 4)
    s.stroke([(60, 52), (88, 46)], LINE, 9)
    s.stroke([(60, 52), (88, 46)], METAL, 4)
    s.stroke([(84, 30), (92, 34), (86, 40), (94, 42), (88, 46)], spark, 3.4)
    s.oval(34, 54, 6, 5, spark)


def _laser(s: Sheet) -> None:
    beam = (120, 230, 255)
    s.poly([(8, 66), (30, 52), (38, 64), (14, 84)], (84, 88, 100))
    s.stroke([(30, 56), (88, 16)], LINE, 16)
    s.stroke([(30, 56), (88, 16)], (84, 88, 100), 10)
    s.stroke([(40, 46), (78, 20)], beam, 3)
    s.oval(90, 14, 6, 6, beam)
    s.stroke([(46, 58), (52, 70), (60, 60)], LINE, 4)


def _beast_claw(s: Sheet) -> None:
    bone = (226, 218, 196)
    s.poly([(20, 84), (36, 40), (62, 14), (86, 10), (66, 32), (52, 62), (40, 90)], bone)
    s.stroke([(40, 50), (66, 22)], lighter(bone, 0.5), 3)
    s.oval(30, 84, 13, 9, (150, 16, 20))


def _hoe(s: Sheet) -> None:
    s.stroke([(16, 88), (72, 20)], LINE, 13)
    s.stroke([(16, 88), (72, 20)], PALE_WOOD, 7)
    s.poly([(62, 16), (88, 12), (92, 40), (80, 44), (76, 28), (66, 28)], METAL)
    s.stroke([(82, 18), (86, 36)], lighter(METAL, 0.4), 2.4)


def _hammer(s: Sheet) -> None:
    s.stroke([(22, 86), (60, 36)], LINE, 13)
    s.stroke([(22, 86), (60, 36)], WOOD, 7)
    s.poly([(85, 36), (74, 50), (43, 26), (54, 12)], DARK_METAL)
    s.stroke([(56, 18), (79, 36)], lighter(DARK_METAL, 0.35), 2.4)


def _scrap(s: Sheet) -> None:
    s.poly([(10, 82), (30, 40), (62, 30), (90, 62), (86, 84)], darker(METAL, 0.3))
    s.poly([(20, 80), (40, 44), (62, 62), (50, 82)], RUST)
    s.poly([(56, 80), (66, 38), (86, 66), (82, 82)], METAL)
    s.oval(34, 22, 30, 30, METAL, 255, outline=True)
    s.oval(44, 32, 10, 10, (40, 34, 34))
    for x, y in ((30, 70), (72, 72)):
        s.oval(x, y, 8, 8, lighter(METAL, 0.4), 255, outline=True)


def _compost(s: Sheet) -> None:
    earth = (112, 82, 58)
    s.poly([(8, 86), (24, 56), (46, 42), (72, 52), (92, 86)], earth)
    s.poly([(22, 86), (36, 64), (56, 60), (70, 86)], darker(earth, 0.22), outline=False)
    for x, y in ((28, 72), (60, 74), (76, 66), (44, 52)):
        s.oval(x, y, 7, 7, lighter(earth, 0.35))
    s.stroke([(50, 44), (50, 24)], GREEN, 4)
    s.oval(34, 12, 18, 14, GREEN, 255, outline=True)
    s.oval(50, 8, 18, 14, GREEN, 255, outline=True)


def _liquor(s: Sheet) -> None:
    s.box(42, 6, 16, 26, GREEN, 4)
    s.box(40, 4, 20, 9, (196, 150, 90), 3)
    s.poly([(42, 30), (58, 30), (72, 46), (72, 92), (28, 92), (28, 46)], GREEN)
    s.box(33, 56, 34, 24, PAPER, 3)
    s.stroke([(38, 64), (62, 64)], LINE, 2.2)
    s.stroke([(40, 72), (60, 72)], RED, 2.6)
    s.shade(32, 48, 6, 38, lighter(GREEN, 0.4), 255, 3)


def _cigarette(s: Sheet) -> None:
    s.stroke([(16, 70), (70, 40)], LINE, 17)
    s.stroke([(16, 70), (58, 47)], PAPER, 10)
    s.stroke([(16, 70), (30, 62)], (220, 150, 80), 10)
    s.stroke([(58, 47), (70, 40)], ORANGE, 10)
    s.stroke([(76, 34), (70, 22), (80, 12)], (220, 220, 214), 3.4)
    s.stroke([(86, 30), (82, 20)], (220, 220, 214), 3)


def _sedative(s: Sheet) -> None:
    s.box(26, 30, 48, 60, (206, 150, 70), 10)
    s.box(30, 12, 40, 20, PAPER, 5)
    s.box(31, 50, 38, 24, PAPER, 3)
    for x, y in ((38, 58), (50, 58), (44, 66), (58, 66)):
        s.oval(x, y, 6, 5, BLUE)
    s.shade(30, 36, 6, 48, lighter((206, 150, 70), 0.4), 255, 3)


def _powder(s: Sheet) -> None:
    s.poly([(18, 34), (82, 34), (88, 86), (12, 86)], PAPER)
    s.poly([(18, 34), (50, 16), (82, 34), (50, 46)], darker(PAPER, 0.1))
    s.oval(30, 54, 40, 22, (240, 240, 244), 255, outline=True)
    s.stroke([(24, 82), (76, 82)], darker(PAPER, 0.2), 2.4)


def _syringe(s: Sheet) -> None:
    s.stroke([(74, 26), (92, 8)], LINE, 4)
    s.stroke([(28, 72), (74, 26)], LINE, 24)
    s.stroke([(28, 72), (74, 26)], GLASS, 16)
    s.stroke([(30, 70), (52, 48)], (150, 196, 120), 16)
    for share in (0.3, 0.5, 0.7):
        x, y = 28 + 46 * share, 72 - 46 * share
        s.stroke([(x - 4, y - 4), (x + 1, y + 1)], LINE, 2)
    s.stroke([(10, 90), (28, 72)], LINE, 9)
    s.stroke([(10, 90), (28, 72)], METAL, 4)
    s.stroke([(4, 84), (16, 96)], LINE, 9)


PAINTERS: dict[str, Painter] = {
    "canned_beans": _canned_beans,
    "old_radio": _old_radio,
    "vegetables": _vegetables,
    "stew": _stew,
    "water": _water,
    "fuel": _fuel,
    "medicine": _medicine,
    "baton": _baton,
    "rusty_knife": _rusty_knife,
    "sledge": _sledge,
    "pipe_pistol": _pipe_pistol,
    "rifle": _rifle,
    "arc_thrower": _arc_thrower,
    "laser": _laser,
    "beast_claw": _beast_claw,
    "hoe": _hoe,
    # No item of anybody's: what is seen in the hand of whoever builds.
    "hammer": _hammer,
    "scrap": _scrap,
    "compost": _compost,
    "liquor": _liquor,
    "cigarette": _cigarette,
    "sedative": _sedative,
    "powder": _powder,
    "syringe": _syringe,
}
# The size the game's own pictures are made at where nobody says another: large enough to be
# shown in a hand, on a shelf or in a panel without being made larger.
MADE_AT = 96


def painted(item_id: str) -> bool:
    """Whether the game draws a picture of an item itself."""
    return item_id in PAINTERS


def picture(item_id: str, size: int = MADE_AT) -> pygame.Surface:
    """The game's picture of one of its own items, `size` pixels a side."""
    sheet = Sheet((size, size), size / 100.0, line=4.2)
    PAINTERS[item_id](sheet)
    return sheet.finished()
