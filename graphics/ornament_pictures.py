"""What is put in a building only to be looked at, as the game draws it (P40).

What goes on the floor is drawn as furniture is, to stand in its cells: `Stage` and all. What
hangs is drawn face on, as the back wall it hangs on is, as wide as the cells it takes and as
tall as it is, and it says how far down the wall its top goes. Everything is measured in
hundredths of the width of a cell.

A kind the game has no picture of, such as a pack may bring, is shown as a plain box.
"""

from collections.abc import Callable

import pygame

from graphics.cartoon import (
    BLUE,
    CANVAS,
    DARK_METAL,
    GLASS,
    GREEN,
    LINE,
    METAL,
    PALE_WOOD,
    PAPER,
    RED,
    WOOD,
    YELLOW,
    Sheet,
)
from graphics.object_pictures import DEPTH, ObjectPicture, Stage
from graphics.ui_art import darker, lighter

Cells = tuple[int, int]
POT = (190, 104, 66)
LEAF = (86, 146, 78)


def rug(cells: Cells, cell: int, depth: int) -> ObjectPicture:
    """A woven rug with a border and a fringe at each end."""
    return _rug(cells, cell, depth, RED, YELLOW)


def mat(cells: Cells, cell: int, depth: int) -> ObjectPicture:
    """A small mat of plaited straw."""
    return _rug(cells, cell, depth, (186, 160, 96), (120, 96, 60))


def _rug(cells: Cells, cell: int, depth: int, color, trim) -> ObjectPicture:
    stage = Stage(cells, 0, cell, depth)
    s = stage.under
    width, top, tall = stage.width, stage.back, stage.front - stage.back
    for x in range(10, int(width) - 6, 9):
        # The fringe, which shows at the far end and at the near one.
        s.stroke([(x, top + 4), (x, top + 9)], darker(trim, 0.2), 1.6)
        s.stroke([(x, top + tall - 9), (x, top + tall - 4)], darker(trim, 0.2), 1.6)
    s.box(6, top + 8, width - 12, tall - 16, color, 5)
    s.shade(13, top + 14, width - 26, tall - 28, lighter(color, 0.14), 255, 3)
    s.stroke(
        [(18, top + 19), (width - 18, top + 19), (width - 18, top + tall - 19), (18, top + tall - 19), (18, top + 19)],
        trim,
        2.6,
    )
    middle = top + tall / 2
    s.poly(
        [(width / 2 - 16, middle), (width / 2, middle - tall * 0.16), (width / 2 + 16, middle), (width / 2, middle + tall * 0.16)],
        trim,
        outline=False,
    )
    return stage.picture()


def plant(cells: Cells, cell: int, depth: int) -> ObjectPicture:
    """Something green in a clay pot."""
    stage = Stage(cells, 86, cell, depth)
    s = stage.under
    stage.shadow(24, 52, 60)
    floor = stage.front - 12
    for x, y, wide, tall in ((18, floor - 92, 34, 44), (50, floor - 100, 34, 46), (30, floor - 122, 38, 52), (12, floor - 62, 30, 30), (58, floor - 64, 30, 30)):
        s.oval(x, y, wide, tall, LEAF, outline=True)
        s.oval(x + wide * 0.22, y + tall * 0.16, wide * 0.3, tall * 0.34, lighter(LEAF, 0.3))
    s.stroke([(50, floor - 34), (50, floor - 78)], darker(LEAF, 0.4), 2.4)
    s.poly([(33, floor - 32), (67, floor - 32), (61, floor), (39, floor)], POT)
    s.box(30, floor - 38, 40, 10, lighter(POT, 0.16), 3)
    s.shade(38, floor - 24, 6, 18, lighter(POT, 0.3), 255, 2)
    return stage.picture()


def chair(cells: Cells, cell: int, depth: int) -> ObjectPicture:
    """A chair with a back to it, facing the room."""
    stage = Stage(cells, 62, cell, depth)
    s = stage.under
    stage.shadow(20, 60, 60)
    floor = stage.front - 12
    deep = (stage.front - stage.back) * 0.4
    top = floor - 30 - deep
    s.box(24, top - 54, 52, 60, WOOD, 6)
    s.shade(28, top - 50, 44, 5, lighter(WOOD, 0.24), 255, 2)
    for x in (39, 50, 61):
        s.stroke([(x, top - 42), (x, top)], darker(WOOD, 0.3), 1.8)
    for x in (26, 65):
        s.box(x, top + deep + 6, 9, 24, darker(WOOD, 0.24), 2)
    s.block(21, top, 58, deep, 8, WOOD, 6, PALE_WOOD)
    return stage.picture()


def bedside_table(cells: Cells, cell: int, depth: int) -> ObjectPicture:
    """A small cupboard with a drawer, and a candle on it."""
    stage = Stage(cells, 52, cell, depth)
    s = stage.under
    stage.shadow(14, 72, 60)
    body = stage.solid(18, 64, 42, WOOD, margin=8, share=0.7, top=PALE_WOOD)
    s.box(25, body.face + 7, 50, 14, lighter(WOOD, 0.1), 2)
    s.oval(47, body.face + 11, 6, 6, YELLOW, outline=True)
    s.box(25, body.face + 24, 50, 12, darker(WOOD, 0.14), 2)
    # The candle and its light.
    middle = body.top + body.deep / 2
    s.oval(38, middle - 40, 26, 30, YELLOW, 70)
    s.box(44, middle - 22, 12, 22, PAPER, 2)
    s.poly([(45, middle - 22), (50, middle - 38), (55, middle - 22)], YELLOW)
    return stage.picture()


def floor_lamp(cells: Cells, cell: int, depth: int) -> ObjectPicture:
    """A lamp on a tall foot, with a shade of cloth."""
    stage = Stage(cells, 130, cell, depth)
    s = stage.under
    stage.shadow(28, 44, 60)
    floor = stage.front - 14
    top = max(6.0, floor - 172)
    s.oval(16, top - 4, 68, 74, YELLOW, 60)
    s.box(36, floor - 8, 28, 8, DARK_METAL, 3)
    s.box(45, top + 44, 10, floor - top - 50, DARK_METAL, 2)
    s.shade(47, top + 50, 3, floor - top - 62, lighter(DARK_METAL, 0.3), 255, 1)
    s.poly([(36, top + 6), (64, top + 6), (74, top + 46), (26, top + 46)], CANVAS)
    s.shade(40, top + 12, 8, 28, lighter(CANVAS, 0.5), 255, 3)
    s.stroke([(27, top + 46), (73, top + 46)], darker(CANVAS, 0.35), 2.2)
    return stage.picture()


def _plain(cells: Cells, cell: int, depth: int) -> ObjectPicture:
    stage = Stage(cells, 40, cell, depth)
    stage.shadow()
    stage.solid(12, stage.width - 24, 34, CANVAS)
    return stage.picture()


# ----- what hangs -----


def picture(sheet: Sheet, width: float, tall: float) -> None:
    """A landscape in a frame."""
    sheet.box(10, 6, width - 20, tall - 12, WOOD, 4)
    sheet.box(18, 14, width - 36, tall - 28, GLASS, 2)
    sheet.oval(width - 44, 20, 14, 14, YELLOW)
    sheet.poly([(19, tall - 15), (19, tall - 34), (40, tall - 46), (62, tall - 30), (width - 19, tall - 40), (width - 19, tall - 15)], GREEN, outline=False)
    sheet.stroke([(18, 14), (width - 18, 14), (width - 18, tall - 14), (18, tall - 14), (18, 14)], LINE, 2.4)


def window(sheet: Sheet, width: float, tall: float) -> None:
    """A window of four panes, with the day outside and a sill under it."""
    sheet.box(10, 6, width - 20, tall - 20, PALE_WOOD, 4)
    sheet.shade(20, 16, width - 40, tall - 40, GLASS, 255, 2)
    sheet.shade(20, 16, width - 40, (tall - 40) * 0.42, lighter(GLASS, 0.35), 255, 2)
    for start in (34.0, width * 0.56):
        sheet.stroke([(start, tall - 34), (start + 20, 24)], lighter(GLASS, 0.75), 3.2)
    sheet.stroke([(20, 16), (width - 20, 16), (width - 20, tall - 24), (20, tall - 24), (20, 16)], LINE, 2.6)
    sheet.stroke([(width / 2, 16), (width / 2, tall - 24)], LINE, 2.6)
    sheet.stroke([(20, tall / 2 - 4), (width - 20, tall / 2 - 4)], LINE, 2.6)
    sheet.box(4, tall - 16, width - 8, 12, lighter(PALE_WOOD, 0.14), 3)


def curtain(sheet: Sheet, width: float, tall: float) -> None:
    """A length of cloth on a rail, drawn to one side."""
    cloth = (176, 84, 92)
    sheet.poly(
        [(14, 12), (width - 14, 12), (width - 20, tall * 0.5), (width - 12, tall - 8), (22, tall - 8), (30, tall * 0.5)],
        cloth,
    )
    for x in (34.0, 50.0, 66.0):
        sheet.stroke([(x, 20), (x + (4 if x < 50 else -4), tall - 16)], darker(cloth, 0.24), 2.0)
    sheet.shade(22, 18, 8, tall * 0.4, lighter(cloth, 0.24), 255, 3)
    sheet.stroke([(6, 10), (width - 6, 10)], DARK_METAL, 4.2)
    for x in (6.0, width - 6.0):
        sheet.oval(x - 5, 5, 10, 10, METAL, outline=True)


def wall_shelf(sheet: Sheet, width: float, tall: float) -> None:
    """A board on two brackets, with a few things kept on it."""
    board = tall - 26
    for x in (30.0, width - 38.0):
        sheet.poly([(x, board + 8), (x + 8, board + 8), (x + 8, tall - 4)], DARK_METAL)
    sheet.box(8, board, width - 16, 10, PALE_WOOD, 3)
    # A row of books, a jar and a tin.
    x = 22.0
    for color, wide, high in ((RED, 10, 34), (BLUE, 12, 40), (GREEN, 9, 30), (YELLOW, 11, 36)):
        sheet.box(x, board - high, wide, high, color, 1.5)
        x += wide
    sheet.box(width * 0.52, board - 30, 22, 30, GLASS, 5)
    sheet.box(width * 0.52 + 3, board - 36, 16, 8, METAL, 2)
    sheet.box(width - 54, board - 22, 26, 22, METAL, 3)
    sheet.shade(width - 50, board - 18, 5, 14, lighter(METAL, 0.4), 255, 2)


def wall_lamp(sheet: Sheet, width: float, tall: float) -> None:
    """A lamp on an arm out of the wall."""
    sheet.oval(8, 0, width - 16, tall - 6, YELLOW, 64)
    sheet.box(40, tall - 26, 20, 20, DARK_METAL, 4)
    sheet.stroke([(50, tall - 22), (50, tall - 38)], DARK_METAL, 4.0)
    sheet.poly([(34, 12), (66, 12), (74, tall - 34), (26, tall - 34)], YELLOW)
    sheet.shade(40, 17, 8, tall - 56, lighter(YELLOW, 0.55), 255, 3)


def clock(sheet: Sheet, width: float, tall: float) -> None:
    """A round clock in a wooden rim."""
    side = min(width - 28, tall - 8)
    left, top = (width - side) / 2, (tall - side) / 2
    sheet.oval(left, top, side, side, WOOD, outline=True)
    sheet.oval(left + 7, top + 7, side - 14, side - 14, PAPER, outline=True)
    centre = (width / 2, tall / 2)
    for x, y in ((0, -1), (1, 0), (0, 1), (-1, 0)):
        reach = side / 2 - 12
        sheet.stroke([(centre[0] + x * reach, centre[1] + y * reach), (centre[0] + x * (reach - 4), centre[1] + y * (reach - 4))], LINE, 1.8)
    sheet.stroke([centre, (centre[0], centre[1] - side * 0.27)], LINE, 2.6)
    sheet.stroke([centre, (centre[0] + side * 0.18, centre[1] + side * 0.08)], LINE, 2.6)
    sheet.oval(centre[0] - 3, centre[1] - 3, 6, 6, RED)


def _plain_hanging(sheet: Sheet, width: float, tall: float) -> None:
    sheet.box(12, 8, width - 24, tall - 16, CANVAS, 4)


FloorPainter = Callable[[Cells, int, int], ObjectPicture]
WallPainter = Callable[[Sheet, float, float], None]

FLOOR_PAINTERS: dict[str, FloorPainter] = {
    "rug": rug,
    "mat": mat,
    "plant": plant,
    "chair": chair,
    "bedside_table": bedside_table,
    "floor_lamp": floor_lamp,
}
# What hangs: who draws each, how tall it is, and how far down the wall its top goes.
WALL_PAINTERS: dict[str, tuple[WallPainter, float, float]] = {
    "picture": (picture, 80, 62),
    "window": (window, 118, 44),
    "curtain": (curtain, 150, 34),
    "wall_shelf": (wall_shelf, 74, 70),
    "wall_lamp": (wall_lamp, 76, 52),
    "clock": (clock, 64, 50),
}
PLAIN_HANGING: tuple[WallPainter, float, float] = (_plain_hanging, 70, 60)


class OrnamentPictures:
    """Makes the game's picture of each kind of ornament at the size it is asked for, once, and keeps it."""

    def __init__(self) -> None:
        self._floor: dict[tuple, ObjectPicture] = {}
        self._wall: dict[tuple, tuple[pygame.Surface, int]] = {}

    def has(self, kind: str) -> bool:
        return kind in FLOOR_PAINTERS or kind in WALL_PAINTERS

    def on_floor(self, kind: str, cells: Cells, cell: int, depth: int) -> ObjectPicture:
        """An ornament that goes on the floor, for cells that wide and that deep."""
        key = (kind, cells, cell, depth)
        if key not in self._floor:
            self._floor[key] = FLOOR_PAINTERS.get(kind, _plain)(cells, cell, depth)
        return self._floor[key]

    def on_wall(self, kind: str, wide: int, cell: int) -> tuple[pygame.Surface, int]:
        """An ornament that hangs, for cells that wide: its picture, and how far down the wall its top goes."""
        key = (kind, wide, cell)
        if key not in self._wall:
            painter, tall, top = WALL_PAINTERS.get(kind, PLAIN_HANGING)
            unit = cell / 100.0
            sheet = Sheet((wide * cell, round(tall * unit)), unit)
            painter(sheet, wide * 100.0, tall)
            self._wall[key] = (sheet.finished(), round(top * unit))
        return self._wall[key]

    def whole(self, kind: str, on_wall: bool, cells: Cells, size: int) -> pygame.Surface:
        """An ornament in one piece, to fit a square of a catalogue."""
        cell = max(8, size // max(cells[0], 1))
        drawn = self.on_wall(kind, cells[0], cell)[0] if on_wall else self.on_floor(kind, cells, cell, max(1, round(cell * DEPTH))).under
        scale = min(1.0, size / drawn.get_width(), size / drawn.get_height())
        if scale < 1.0:
            drawn = pygame.transform.smoothscale(drawn, (max(1, round(drawn.get_width() * scale)), max(1, round(drawn.get_height() * scale))))
        return drawn
