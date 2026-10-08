"""Every kind of furniture and object as the game draws it: from its front, and a little from above.

One picture does for the map and for the inside of a building. The only thing that differs is
how deep a cell of the ground looks: as deep as it is wide out on the map, and less inside,
where the floor is seen from lower down. A painter is given both and draws to fit.

Everything is measured in hundredths of the width of a cell. Down the picture, `back` is the far
edge of the ground the thing takes up and `front` the near one; whatever is above `back` stands
up over the ground behind it.
"""

from collections.abc import Callable
from dataclasses import dataclass, field

import pygame

from graphics.cartoon import (
    BLUE,
    CANVAS,
    DARK_METAL,
    GLASS,
    GREEN,
    LINE,
    METAL,
    ORANGE,
    PALE_WOOD,
    PAPER,
    RED,
    RUBBER,
    RUST,
    SHEET,
    SOIL,
    STONE,
    WOOD,
    YELLOW,
    Sheet,
)
from graphics.palette import Color
from graphics.ui_art import darker, lighter, mix

# How deep a cell of the ground looks in these pictures, as a share of its width: the floor is
# seen from a little above, so less deep than wide. It is the same on the map and inside a
# building, so that one picture does for both.
DEPTH = 0.62


@dataclass(frozen=True)
class ObjectPicture:
    """A thing as the game draws it, in pixels of wherever it is shown."""

    # What of it is under whoever is in it, and what of it is over them: a bed, and its blanket.
    under: pygame.Surface
    over: pygame.Surface | None
    # How far it stands above the far edge of the ground it takes up.
    rise: int
    # Where what it shows off goes, from its top left corner, and how large each is shown.
    slots: tuple[tuple[int, int], ...] = ()
    slot_size: int = 0
    # Where the neck of whoever lies in it is, from its top left corner. None for what nobody lies in.
    neck: tuple[float, float] | None = None


@dataclass
class Solid:
    """A box standing on the ground, as it was drawn: where its top starts, its front, and its foot."""

    x: float
    width: float
    top: float
    face: float
    floor: float

    @property
    def deep(self) -> float:
        return self.face - self.top

    @property
    def tall(self) -> float:
        return self.floor - self.face


@dataclass
class Stage:
    """The ground a thing takes up, and the room above it, to draw it in."""

    cells: tuple[int, int]
    rise: float
    cell: int
    depth: int
    under: Sheet = field(init=False)
    _over: Sheet | None = field(init=False, default=None)
    slots: list[tuple[float, float]] = field(init=False, default_factory=list)
    slot_size: float = field(init=False, default=0.0)
    neck: tuple[float, float] | None = field(init=False, default=None)

    def __post_init__(self) -> None:
        self.unit = self.cell / 100.0
        # How many units of the picture a cell of the ground is deep.
        self.deep = 100.0 * self.depth / self.cell
        self.rise_px = round(self.rise * self.unit)
        self.size = (self.cells[0] * self.cell, self.rise_px + self.cells[1] * self.depth)
        self.under = Sheet(self.size, self.unit)
        self.back = float(self.rise)
        self.front = self.back + self.cells[1] * self.deep
        self.width = self.cells[0] * 100.0

    @property
    def over(self) -> Sheet:
        if self._over is None:
            self._over = Sheet(self.size, self.unit)
        return self._over

    @property
    def middle(self) -> float:
        """Half way down the ground it takes up."""
        return (self.back + self.front) / 2

    def solid(
        self,
        x: float,
        width: float,
        height: float,
        color: Color,
        margin: float = 5.0,
        share: float = 1.0,
        top: Color | None = None,
        radius: float = 3.0,
        sheet: Sheet | None = None,
    ) -> Solid:
        """A box that stands on the ground, taking up `share` of its depth, from its near edge back."""
        floor = self.front - margin
        deep = max(4.0, (self.front - self.back - margin * 2) * share)
        start = floor - height - deep
        (sheet or self.under).block(x, start, width, deep, height, color, radius, top)
        return Solid(x, width, start, start + deep, floor)

    def shadow(self, x: float | None = None, width: float | None = None, alpha: int = 70) -> None:
        left = 2.0 if x is None else x
        self.under.ground_shade(left, self.front - 15, (self.width - 4.0) if width is None else width, 16, alpha)

    def picture(self) -> ObjectPicture:
        unit = self.unit
        return ObjectPicture(
            self.under.finished(),
            self._over.finished() if self._over is not None else None,
            self.rise_px,
            tuple((round(x * unit), round(y * unit)) for x, y in self.slots),
            round(self.slot_size * unit),
            (self.neck[0] * unit, self.neck[1] * unit) if self.neck is not None else None,
        )


def _flame(sheet: Sheet, x: float, foot: float, size: float, frame: int) -> None:
    """A fire, leaning a different way at each of its three turns."""
    lean = (-0.12, 0.05, 0.14)[frame % 3] * size
    tall = (1.0, 1.14, 0.92)[frame % 3] * size
    sheet.poly(
        [(x - size * 0.42, foot), (x - size * 0.5, foot - tall * 0.42), (x - size * 0.14 + lean, foot - tall * 0.62),
         (x + lean * 1.6, foot - tall), (x + size * 0.2 + lean, foot - tall * 0.56), (x + size * 0.5, foot - tall * 0.36),
         (x + size * 0.4, foot)],
        ORANGE,
    )
    sheet.poly(
        [(x - size * 0.2, foot), (x - size * 0.22, foot - tall * 0.3), (x + lean, foot - tall * 0.6),
         (x + size * 0.24, foot - tall * 0.26), (x + size * 0.2, foot)],
        YELLOW,
        outline=False,
    )


def _planks(sheet: Sheet, solid: Solid, color: Color, every: float = 16.0) -> None:
    """The boards a wooden front is made of, as lines across it."""
    y = solid.face + every
    while y < solid.floor - 6:
        sheet.stroke([(solid.x + 4, y), (solid.x + solid.width - 4, y)], darker(color, 0.3), 1.5)
        y += every


def bed(cell: int, depth: int, frame: int = 0) -> ObjectPicture:
    """A bed one cell wide and two deep, its head to the back."""
    return _bed(cell, depth, WOOD, SHEET, BLUE, None)


def clinic_bed(cell: int, depth: int, frame: int = 0) -> ObjectPicture:
    """A sick bed: a frame of tube, white all over, with a cross on it."""
    return _bed(cell, depth, (200, 206, 208), PAPER, (150, 198, 176), RED)


def _bed(cell: int, depth: int, frame_color: Color, sheet_color: Color, blanket: Color, cross: Color | None) -> ObjectPicture:
    stage = Stage((1, 2), 40, cell, depth)
    under, over = stage.under, stage.over
    back, front = stage.back, stage.front
    foot = front - 30.0
    stage.shadow()
    stage.neck = (50.0, back + 39.0)
    # The headboard, face on, between its two posts.
    under.box(9, 5, 82, back + 12, frame_color, 7)
    under.shade(12, 8, 76, 5, lighter(frame_color, 0.22), 255, 3)
    for x in (30, 50, 70):
        under.stroke([(x, 12), (x, back + 6)], darker(frame_color, 0.28), 1.6)
    if cross is not None:
        under.shade(45, 13, 10, 24, cross, 255, 2)
        under.shade(38, 20, 24, 10, cross, 255, 2)
    for x in (4, 86):
        under.box(x, 1, 10, back + 18, darker(frame_color, 0.12), 4)
        under.shade(x + 2, 4, 3, back + 10, lighter(frame_color, 0.2), 255, 1.5)
    # The frame, seen from above, and the mattress in it.
    under.box(7, back + 2, 86, foot - back + 4, darker(frame_color, 0.06), 5)
    under.box(11, back + 5, 78, foot - back - 2, sheet_color, 5)
    under.shade(13, back + 7, 74, 5, lighter(sheet_color, 0.5), 255, 2.5)
    # The pillow, with the hollow a head leaves in it.
    under.box(19, back + 8, 62, 25, PAPER, 10)
    under.shade(24, back + 24, 52, 6, darker(PAPER, 0.14), 255, 3)
    under.oval(35, back + 13, 30, 13, darker(PAPER, 0.1))
    # The blanket, turned down at the top, over whoever lies there.
    top = back + 38
    over.box(9, top, 82, foot - top + 7, blanket, 6)
    over.shade(72, top + 13, 16.5, foot - top - 9, darker(blanket, 0.2), 255, 4)
    over.shade(11.5, top + 13, 5, foot - top - 9, lighter(blanket, 0.12), 255, 2.5)
    over.box(9, top, 82, 13, lighter(blanket, 0.34), 5)
    over.shade(12, top + 2.4, 76, 3.2, lighter(blanket, 0.62), 255, 1.6)
    middle = (top + 13 + foot) / 2
    over.stroke([(26, top + 22), (33, middle - 4), (30, foot - 6)], darker(blanket, 0.42), 2.2)
    over.stroke([(58, top + 20), (52, middle + 2), (60, foot - 4)], darker(blanket, 0.42), 2.2)
    over.stroke([(74, top + 26), (71, middle + 6)], darker(blanket, 0.42), 2.0)
    # The board at its foot, face on, and the feet it stands on.
    for x in (8, 81):
        over.box(x, front - 9, 11, 9, darker(frame_color, 0.3), 2)
    over.box(6, foot - 2, 88, 26, frame_color, 6)
    over.shade(9.5, foot + 1, 81, 4.5, lighter(frame_color, 0.24), 255, 2.2)
    over.shade(9.5, foot + 16, 81, 5, darker(frame_color, 0.2), 255, 2.2)
    for x in (34, 66):
        over.stroke([(x, foot + 3), (x, foot + 20)], darker(frame_color, 0.3), 1.6)
    return stage.picture()


def pantry(cell: int, depth: int, frame: int = 0) -> ObjectPicture:
    """A cupboard for food: jars on an open shelf over two doors."""
    stage = Stage((1, 1), 80, cell, depth)
    s = stage.under
    stage.shadow()
    body = stage.solid(8, 84, 96, WOOD, share=0.55)
    s.box(14, body.face + 6, 72, 36, darker(WOOD, 0.55), 2)
    s.stroke([(15, body.face + 25), (85, body.face + 25)], PALE_WOOD, 2.4)
    for x, color in ((19, RED), (32, YELLOW), (45, GREEN), (60, PAPER), (72, ORANGE)):
        s.box(x, body.face + 11, 10, 13, color, 2)
    for x, color in ((24, GREEN), (40, RED), (56, YELLOW), (70, BLUE)):
        s.box(x, body.face + 28, 10, 12, color, 2)
    for x in (14, 51):
        s.box(x, body.face + 48, 35, 42, lighter(WOOD, 0.1), 3)
        s.stroke([(x + 5, body.face + 54), (x + 30, body.face + 54)], lighter(WOOD, 0.34), 1.6)
    s.oval(43, body.face + 66, 5, 5, LINE)
    s.oval(53, body.face + 66, 5, 5, LINE)
    return stage.picture()


def campfire(cell: int, depth: int, frame: int = 0) -> ObjectPicture:
    """A fire on the ground, in a ring of stones."""
    stage = Stage((1, 1), 34, cell, depth)
    s = stage.under
    middle, reach = stage.middle, (stage.front - stage.back) * 0.36
    s.oval(14, middle - reach, 72, reach * 2, (40, 30, 26), 150)
    for x, y in ((14, 0.1), (26, -0.7), (50, -0.95), (74, -0.7), (86, 0.1), (72, 0.8), (50, 1.0), (28, 0.8)):
        s.oval(x - 9, middle + y * reach - 6, 18, 12, STONE, 255, outline=True)
    s.stroke([(30, middle + 6), (70, middle - 8)], darker(WOOD, 0.3), 9)
    s.stroke([(30, middle + 6), (70, middle - 8)], WOOD, 5)
    s.stroke([(32, middle - 8), (70, middle + 7)], darker(WOOD, 0.3), 9)
    s.stroke([(32, middle - 8), (70, middle + 7)], PALE_WOOD, 5)
    _flame(s, 50, middle + 4, 34, frame)
    return stage.picture()


def table(cell: int, depth: int, frame: int = 0) -> ObjectPicture:
    stage = Stage((2, 1), 42, cell, depth)
    s = stage.under
    stage.shadow(6, 188)
    floor, slab = stage.front - 5, 10.0
    deep = stage.front - stage.back - 10
    top = floor - 46 - deep
    for x in (10, 178):
        s.box(x, top + deep + slab - 1, 12, 46 - slab + 1, darker(WOOD, 0.2), 2)
    s.block(4, top, 192, deep, slab, WOOD, 4, PALE_WOOD)
    for x in (52, 100, 148):
        s.stroke([(x, top + 4), (x, top + deep - 4)], darker(PALE_WOOD, 0.22), 1.5)
    return stage.picture()


def stool(cell: int, depth: int, frame: int = 0) -> ObjectPicture:
    stage = Stage((1, 1), 12, cell, depth)
    s = stage.under
    stage.shadow(20, 60, 60)
    floor = stage.front - 12
    deep = (stage.front - stage.back) * 0.42
    top = floor - 30 - deep
    for x in (27, 64):
        s.box(x, top + deep + 6, 9, 24, darker(WOOD, 0.24), 2)
    s.block(21, top, 58, deep, 8, WOOD, 7, PALE_WOOD)
    return stage.picture()


def crate(cell: int, depth: int, frame: int = 0) -> ObjectPicture:
    """A box of boards with its lid on, for keeping things in."""
    stage = Stage((1, 1), 48, cell, depth)
    s = stage.under
    stage.shadow()
    body = stage.solid(10, 80, 50, PALE_WOOD, margin=6)
    _planks(s, body, PALE_WOOD, 16)
    for x in (10, 80):
        s.box(x, body.face, 10, body.tall, darker(PALE_WOOD, 0.2), 2)
    s.stroke([(50, body.top + 4), (50, body.face - 4)], darker(PALE_WOOD, 0.3), 1.6)
    s.box(40, body.face + 15, 20, 15, DARK_METAL, 3)
    s.oval(47, body.face + 20, 6, 6, YELLOW)
    return stage.picture()


def study_desk(cell: int, depth: int, frame: int = 0) -> ObjectPicture:
    """A desk with a book open on it and a light to read by."""
    stage = Stage((1, 1), 60, cell, depth)
    s = stage.under
    stage.shadow()
    body = stage.solid(7, 86, 44, WOOD, top=PALE_WOOD)
    s.box(14, body.face + 8, 72, 16, lighter(WOOD, 0.1), 2)
    s.oval(47, body.face + 13, 6, 6, LINE)
    s.box(14, body.face + 26, 30, 16, darker(WOOD, 0.45), 2)
    deep = body.deep
    s.poly([(18, body.top + deep * 0.28), (44, body.top + deep * 0.2), (44, body.top + deep * 0.82), (18, body.top + deep * 0.9)], PAPER)
    s.poly([(44, body.top + deep * 0.2), (68, body.top + deep * 0.28), (68, body.top + deep * 0.9), (44, body.top + deep * 0.82)], SHEET)
    for step in (0.4, 0.55, 0.7):
        s.stroke([(23, body.top + deep * step), (39, body.top + deep * (step - 0.04))], darker(PAPER, 0.4), 1.3)
    s.box(76, body.top + deep * 0.3 - 20, 9, 24, PAPER, 3)
    _flame(s, 80.5, body.top + deep * 0.3 - 20, 12, frame)
    return stage.picture()


def cooking_pot(cell: int, depth: int, frame: int = 0) -> ObjectPicture:
    """A stove with a fire in its mouth and a pot of stew on top."""
    stage = Stage((1, 1), 78, cell, depth)
    s = stage.under
    stage.shadow()
    stove = stage.solid(10, 80, 52, DARK_METAL, share=0.8)
    s.box(26, stove.face + 14, 48, 28, (36, 26, 24), 5)
    s.shade(31, stove.face + 26, 38, 13, ORANGE, 255, 4)
    s.shade(38, stove.face + 31, 24, 8, YELLOW, 255, 3)
    for x in (18, 78):
        s.oval(x, stove.face + 5, 5, 5, METAL)
    deep = stove.deep
    pot_top = stove.top + deep * 0.5 - 30
    s.box(22, pot_top + 9, 56, 28, METAL, 9)
    s.shade(27, pot_top + 28, 46, 6, darker(METAL, 0.2), 255, 3)
    s.oval(22, pot_top, 56, 18, darker(METAL, 0.15), 255, outline=True)
    s.oval(28, pot_top + 3.5, 44, 11, (150, 96, 52))
    s.oval(36, pot_top + 6, 8, 5, ORANGE)
    s.oval(52, pot_top + 5, 7, 4, GREEN)
    for x, sway in ((38, 4), (56, -4)):
        s.stroke([(x, pot_top - 4), (x + sway, pot_top - 14), (x - sway, pot_top - 24)], (236, 236, 230), 2.4)
    return stage.picture()


def bar(cell: int, depth: int, frame: int = 0) -> ObjectPicture:
    """The counter of the cantina, three cells long, with what it serves on it."""
    stage = Stage((3, 1), 62, cell, depth)
    s = stage.under
    stage.shadow(4, 292)
    body = stage.solid(4, 292, 54, WOOD, top=PALE_WOOD)
    for x in (12, 106, 200):
        s.box(x, body.face + 9, 86, 36, darker(WOOD, 0.14), 3)
        s.stroke([(x + 6, body.face + 15), (x + 80, body.face + 15)], lighter(WOOD, 0.2), 1.6)
    foot = body.top + body.deep * 0.6
    for x, color in ((34, GREEN), (58, RUST), (236, BLUE), (258, GREEN)):
        s.box(x, foot - 30, 13, 30, color, 4)
        s.box(x + 3.5, foot - 42, 6, 14, color, 2)
        s.shade(x + 2.6, foot - 16, 7.8, 8, PAPER, 255, 1)
    s.box(136, foot - 20, 20, 20, PAPER, 4)
    s.arc(158, foot - 10, 6, -70, 70, LINE, 3)
    s.oval(138, foot - 23, 16, 7, (232, 190, 110), 255, outline=True)
    return stage.picture()


def workbench(cell: int, depth: int, frame: int = 0) -> ObjectPicture:
    """A heavy bench for mending and making, with tools left on it."""
    stage = Stage((2, 1), 46, cell, depth)
    s = stage.under
    stage.shadow(5, 190)
    floor, slab = stage.front - 5, 13.0
    deep = stage.front - stage.back - 10
    top = floor - 48 - deep
    for x in (9, 175):
        s.box(x, top + deep + slab - 1, 16, 48 - slab + 1, darker(WOOD, 0.26), 2)
    s.box(22, floor - 18, 156, 9, darker(WOOD, 0.14), 2)
    s.block(4, top, 192, deep, slab, PALE_WOOD, 3)
    # A vice at one end, a hammer and a saw.
    s.block(150, top + deep * 0.25 - 14, 30, deep * 0.4, 14, DARK_METAL, 2)
    s.stroke([(40, top + deep * 0.72), (76, top + deep * 0.36)], WOOD, 5)
    s.box(68, top + deep * 0.36 - 8, 20, 11, METAL, 2)
    s.poly([(98, top + deep * 0.3), (140, top + deep * 0.46), (140, top + deep * 0.66), (98, top + deep * 0.5)], (190, 196, 200))
    s.box(88, top + deep * 0.28, 12, deep * 0.26, WOOD, 3)
    return stage.picture()


def shop_counter(cell: int, depth: int, frame: int = 0) -> ObjectPicture:
    """The counter of the shop, with its till and a few things set out."""
    stage = Stage((2, 1), 50, cell, depth)
    s = stage.under
    stage.shadow(5, 190)
    body = stage.solid(5, 190, 52, WOOD, top=PALE_WOOD)
    for index, x in enumerate(range(11, 188, 22)):
        s.shade(x, body.face + 6, 22, 40, (220, 212, 190) if index % 2 else (86, 150, 132), 255)
    s.stroke([(11, body.face + 6), (189, body.face + 6), (189, body.face + 46), (11, body.face + 46), (11, body.face + 6)], LINE, 2.6)
    foot = body.top + body.deep * 0.62
    s.box(134, foot - 30, 42, 30, DARK_METAL, 4)
    s.box(139, foot - 26, 32, 10, (200, 226, 190), 2)
    s.box(128, foot - 6, 54, 8, darker(DARK_METAL, 0.2), 2)
    for x, color in ((26, RED), (44, YELLOW), (64, GREEN)):
        s.box(x, foot - 16, 13, 16, color, 3)
        s.oval(x, foot - 20, 13, 7, lighter(color, 0.3), 255, outline=True)
    return stage.picture()


def shelf(cell: int, depth: int, frame: int = 0) -> ObjectPicture:
    """Shelves two cells long, with room on two boards for what the shop has."""
    stage = Stage((2, 1), 108, cell, depth)
    s = stage.under
    stage.shadow(5, 190)
    body = stage.solid(5, 190, 122, WOOD, share=0.42)
    s.box(12, body.face + 7, 176, 108, darker(WOOD, 0.58), 2)
    boards = (body.face + 54, body.face + 108)
    for y in boards:
        s.box(12, y, 176, 8, PALE_WOOD, 1)
    stage.slot_size = 34.0
    for y in boards:
        for x in (26, 83, 140):
            stage.slots.append((x, y - stage.slot_size - 1))
    return stage.picture()


def barrel(cell: int, depth: int, frame: int = 0) -> ObjectPicture:
    """An oil drum with a fire lit in it."""
    stage = Stage((1, 1), 70, cell, depth)
    s = stage.under
    stage.shadow(14, 72)
    floor = stage.front - 8
    top = floor - 62
    s.box(20, top, 60, 62, RUST, 9)
    s.shade(24, top + 10, 9, 44, lighter(RUST, 0.2), 255, 4)
    s.shade(66, top + 10, 10, 44, darker(RUST, 0.22), 255, 4)
    for y in (top + 18, top + 42):
        s.stroke([(21, y), (79, y)], darker(RUST, 0.45), 2.6)
    s.oval(20, top - 9, 60, 20, (40, 28, 24), 255, outline=True)
    s.oval(28, top - 5, 44, 12, ORANGE)
    _flame(s, 50, top + 2, 32, frame)
    return stage.picture()


def scrap_pile(cell: int, depth: int, frame: int = 0) -> ObjectPicture:
    """A heap of metal, for mending and building with."""
    stage = Stage((2, 1), 34, cell, depth)
    s = stage.under
    stage.shadow(6, 188)
    floor = stage.front - 6
    s.poly([(10, floor), (34, floor - 34), (76, floor - 50), (118, floor - 58), (158, floor - 40), (190, floor), ], darker(METAL, 0.3))
    s.poly([(24, floor - 6), (58, floor - 44), (92, floor - 22), (70, floor - 2)], RUST)
    s.poly([(96, floor - 4), (112, floor - 52), (150, floor - 34), (140, floor - 2)], METAL)
    s.poly([(140, floor - 4), (166, floor - 30), (184, floor - 4)], DARK_METAL)
    s.stroke([(44, floor - 30), (100, floor - 60)], darker(METAL, 0.1), 6)
    s.stroke([(44, floor - 30), (100, floor - 60)], lighter(METAL, 0.3), 2)
    s.oval(64, floor - 24, 26, 20, STONE, 255, outline=True)
    s.oval(72, floor - 18, 10, 8, darker(METAL, 0.5))
    s.box(118, floor - 26, 22, 9, YELLOW, 2)
    for x, y in ((34, floor - 12), (158, floor - 14), (108, floor - 12)):
        s.oval(x, y, 6, 6, lighter(METAL, 0.4))
    return stage.picture()


def water_tank(cell: int, depth: int, frame: int = 0) -> ObjectPicture:
    """A tank two cells each way, up on legs, with a tap."""
    stage = Stage((2, 2), 66, cell, depth)
    s = stage.under
    tank: Color = (104, 150, 172)
    stage.shadow(8, 184, 80)
    floor = stage.front - 8
    for x in (26, 162):
        s.box(x, floor - 34, 12, 34, DARK_METAL, 2)
    s.stroke([(32, floor - 8), (168, floor - 26)], DARK_METAL, 4)
    top = floor - 34 - (stage.front - stage.back) * 0.5 - 70
    tall = floor - 28 - top
    s.box(16, top + 16, 168, tall - 16, tank, 22)
    s.shade(26, top + 30, 16, tall - 44, lighter(tank, 0.24), 255, 8)
    s.shade(158, top + 30, 18, tall - 44, darker(tank, 0.2), 255, 8)
    for y in (top + tall * 0.42, top + tall * 0.74):
        s.stroke([(17, y), (183, y)], darker(tank, 0.4), 2.6)
    s.oval(16, top, 168, 36, lighter(tank, 0.2), 255, outline=True)
    s.oval(84, top + 9, 32, 14, darker(tank, 0.3), 255, outline=True)
    s.box(94, floor - 46, 14, 24, METAL, 3)
    s.box(84, floor - 48, 34, 8, RED, 3)
    s.poly([(101, floor - 18), (107, floor - 6), (101, floor - 1), (95, floor - 6)], (120, 196, 226))
    return stage.picture()


def generator(cell: int, depth: int, frame: int = 0) -> ObjectPicture:
    """An engine that makes light out of fuel."""
    stage = Stage((2, 1), 112, cell, depth)
    s = stage.under
    casing: Color = (196, 162, 62)
    stage.shadow(6, 188)
    body = stage.solid(8, 184, 56, casing, share=0.8, radius=6)
    s.box(18, body.face + 10, 66, 34, (40, 40, 44), 4)
    for y in (body.face + 17, body.face + 25, body.face + 33):
        s.stroke([(24, y), (78, y)], METAL, 2.2)
    s.box(98, body.face + 10, 80, 34, darker(casing, 0.16), 4)
    for x, color in ((110, GREEN), (128, YELLOW), (146, RED)):
        s.oval(x, body.face + 18, 9, 9, color, 255, outline=True)
    s.shade(108, body.face + 33, 58, 5, DARK_METAL, 255, 2)
    pipe = body.top + body.deep * 0.4
    s.stroke([(150, pipe), (150, pipe - 40), (170, pipe - 52)], LINE, 13)
    s.stroke([(150, pipe), (150, pipe - 40), (170, pipe - 52)], DARK_METAL, 8)
    s.oval(162, pipe - 70, 16, 12, (120, 120, 120), 150)
    s.oval(170, pipe - 84, 12, 10, (120, 120, 120), 110)
    s.box(40, body.top + body.deep * 0.3 - 8, 44, 12, darker(casing, 0.3), 4)
    return stage.picture()


def medicine_cabinet(cell: int, depth: int, frame: int = 0) -> ObjectPicture:
    """A white cupboard with glass in its doors and a cross on it."""
    stage = Stage((1, 1), 78, cell, depth)
    s = stage.under
    white: Color = (234, 234, 226)
    stage.shadow()
    body = stage.solid(12, 76, 94, white, share=0.5)
    for x in (18, 51):
        s.box(x, body.face + 8, 31, 44, GLASS, 3)
        s.stroke([(x + 5, body.face + 40), (x + 14, body.face + 14)], lighter(GLASS, 0.6), 2.4)
        for y, color in ((body.face + 26, RED), (body.face + 44, BLUE)):
            s.shade(x + 5, y - 9, 8, 9, color, 255, 1.5)
            s.shade(x + 16, y - 7, 8, 7, PAPER, 255, 1.5)
            s.stroke([(x + 2, y), (x + 29, y)], darker(white, 0.3), 1.6)
    s.box(18, body.face + 58, 64, 28, darker(white, 0.08), 3)
    s.shade(45, body.face + 62, 10, 20, RED, 255, 1.5)
    s.shade(40, body.face + 67, 20, 10, RED, 255, 1.5)
    return stage.picture()


def lamp(cell: int, depth: int, frame: int = 0) -> ObjectPicture:
    """A lantern on a post."""
    stage = Stage((1, 1), 150, cell, depth)
    s = stage.under
    stage.shadow(26, 48, 60)
    floor = stage.front - (stage.front - stage.back) * 0.3
    top = max(6.0, floor - 190)
    s.oval(22, top - 8, 56, 60, YELLOW, 70)
    s.box(36, floor - 12, 28, 12, DARK_METAL, 3)
    s.box(45, top + 40, 10, floor - top - 48, DARK_METAL, 2)
    s.shade(47, top + 44, 3, floor - top - 56, lighter(DARK_METAL, 0.3), 255, 1)
    s.box(33, top + 8, 34, 34, YELLOW, 4)
    s.shade(38, top + 13, 10, 24, lighter(YELLOW, 0.5), 255, 3)
    s.stroke([(50, top + 9), (50, top + 41)], LINE, 2.4)
    s.poly([(28, top + 10), (50, top - 2), (72, top + 10)], DARK_METAL)
    s.box(31, top + 40, 38, 6, DARK_METAL, 2)
    return stage.picture()


def handcart(cell: int, depth: int, frame: int = 0) -> ObjectPicture:
    """A cart knocked together from a crate and two wheels, for going out with."""
    stage = Stage((1, 1), 30, cell, depth)
    s = stage.under
    stage.shadow()
    floor = stage.front - 6
    deep = (stage.front - stage.back) * 0.5
    top = floor - 16 - 30 - deep
    s.stroke([(30, top + deep * 0.5), (4, top + deep * 0.5 - 14)], LINE, 7)
    s.stroke([(30, top + deep * 0.5), (4, top + deep * 0.5 - 14)], WOOD, 3.6)
    s.block(24, top, 70, deep, 30, RUST, 3, darker(RUST, 0.5))
    s.stroke([(28, top + deep + 12), (90, top + deep + 12)], darker(RUST, 0.4), 2)
    for x in (30, 68):
        s.oval(x, floor - 26, 26, 26, RUBBER, 255, outline=True)
        s.oval(x + 8, floor - 18, 10, 10, METAL)
    return stage.picture()


def radio_set(cell: int, depth: int, frame: int = 0) -> ObjectPicture:
    """The settlement's radio: a big old receiver on a crate, with its aerial up."""
    stage = Stage((1, 1), 124, cell, depth)
    s = stage.under
    stage.shadow()
    base = stage.solid(12, 76, 34, PALE_WOOD, share=0.7)
    _planks(s, base, PALE_WOOD, 12)
    deep = base.deep * 0.7
    top = base.top + base.deep * 0.2 - 40
    s.stroke([(78, top + 4), (86, top - 62)], LINE, 3.4)
    s.oval(82, top - 68, 8, 8, RED, 255, outline=True)
    s.block(18, top, 64, deep, 40, RUST, 5)
    s.box(24, top + deep + 7, 30, 26, (44, 36, 34), 3)
    for y in (top + deep + 13, top + deep + 20, top + deep + 27):
        s.stroke([(28, y), (50, y)], (120, 100, 90), 1.8)
    s.oval(60, top + deep + 8, 15, 15, YELLOW, 255, outline=True)
    s.stroke([(67.5, top + deep + 15.5), (72, top + deep + 11)], LINE, 2)
    s.oval(62, top + deep + 27, 6, 6, GREEN)
    s.oval(70, top + deep + 27, 6, 6, RED)
    return stage.picture()


def lab_bench(cell: int, depth: int, frame: int = 0) -> ObjectPicture:
    """A bench of metal with flasks on it and something on the boil."""
    stage = Stage((2, 1), 62, cell, depth)
    s = stage.under
    stage.shadow(5, 190)
    body = stage.solid(5, 190, 48, METAL, top=(206, 212, 214))
    s.box(14, body.face + 9, 80, 30, darker(METAL, 0.22), 3)
    s.box(106, body.face + 9, 80, 30, darker(METAL, 0.22), 3)
    for x in (48, 140):
        s.oval(x, body.face + 20, 7, 7, LINE)
    foot = body.top + body.deep * 0.6
    for x, color, size in ((30, GREEN, 1.0), (62, (150, 110, 190), 0.8), (160, (110, 190, 220), 0.9)):
        wide, tall = 30 * size, 36 * size
        s.poly([(x + wide * 0.36, foot - tall), (x + wide * 0.64, foot - tall), (x + wide * 0.64, foot - tall * 0.56),
                (x + wide, foot), (x, foot), (x + wide * 0.36, foot - tall * 0.56)], (228, 240, 240))
        s.poly([(x + wide * 0.2, foot - tall * 0.3), (x + wide * 0.8, foot - tall * 0.3), (x + wide, foot), (x, foot)], color, outline=False)
        s.stroke([(x + wide * 0.36, foot - tall), (x + wide * 0.64, foot - tall)], LINE, 2.6)
    s.box(100, foot - 12, 30, 12, DARK_METAL, 3)
    _flame(s, 115, foot - 12, 18, frame)
    return stage.picture()


def crop_bed(cell: int, depth: int, frame: int = 0) -> ObjectPicture:
    """A bed of earth edged with boards, with something coming up in it."""
    stage = Stage((1, 1), 30, cell, depth)
    s = stage.under
    floor = stage.front - 4
    deep = stage.front - stage.back - 8
    top = floor - 9 - deep
    s.block(4, top, 92, deep, 9, PALE_WOOD, 3, SOIL)
    for share in (0.3, 0.62):
        s.stroke([(10, top + deep * share), (90, top + deep * share)], darker(SOIL, 0.3), 2.2)
    for index, (x, share) in enumerate(((22, 0.34), (50, 0.26), (78, 0.36), (34, 0.74), (66, 0.7))):
        foot = top + deep * share
        tall = 20 + (index % 3) * 4
        leaf = lighter(GREEN, 0.16 + 0.1 * (index % 2))
        s.stroke([(x, foot), (x, foot - tall)], darker(GREEN, 0.1), 3.4)
        s.oval(x - 15, foot - tall * 1.0, 16, 11, leaf, 255, outline=True)
        s.oval(x - 1, foot - tall * 1.25, 16, 11, lighter(leaf, 0.14), 255, outline=True)
    return stage.picture()


def guard_post(cell: int, depth: int, frame: int = 0) -> ObjectPicture:
    """A sentry box by the gate, with a striped board across it."""
    stage = Stage((1, 1), 128, cell, depth)
    s = stage.under
    olive: Color = (116, 128, 96)
    stage.shadow()
    body = stage.solid(16, 68, 112, olive, share=0.6)
    s.box(27, body.face + 12, 46, 34, (36, 40, 44), 3)
    s.stroke([(31, body.face + 40), (44, body.face + 16)], (90, 110, 120), 2.4)
    for index, x in enumerate(range(16, 84, 17)):
        s.shade(x, body.face + 56, 17, 14, YELLOW if index % 2 == 0 else (40, 36, 34), 255)
    s.stroke([(16, body.face + 56), (84, body.face + 56)], LINE, 2.6)
    s.stroke([(16, body.face + 70), (84, body.face + 70)], LINE, 2.6)
    s.block(8, body.top - 10, 84, body.deep + 4, 10, RUST, 3)
    return stage.picture()


def grave(cell: int, depth: int, frame: int = 0) -> ObjectPicture:
    """A mound of earth with a cross of two boards at its head."""
    stage = Stage((1, 1), 46, cell, depth)
    s = stage.under
    reach = stage.front - stage.back
    s.oval(14, stage.back + reach * 0.3, 72, reach * 0.62, SOIL, 255, outline=True)
    s.oval(22, stage.back + reach * 0.36, 44, reach * 0.3, lighter(SOIL, 0.16))
    for x, y in ((30, 0.66), (52, 0.74), (66, 0.6)):
        s.oval(x, stage.back + reach * y, 8, 5, darker(SOIL, 0.3))
    foot = stage.back + reach * 0.36
    s.box(45, foot - 62, 10, 62, PALE_WOOD, 2)
    s.box(30, foot - 48, 40, 10, PALE_WOOD, 2)
    return stage.picture()


def wreck(cell: int, depth: int, frame: int = 0) -> ObjectPicture:
    """What is left of a car, three cells long, seen from its side and rusted through."""
    stage = Stage((3, 2), 12, cell, depth)
    s = stage.under
    paint: Color = (156, 88, 60)
    stage.shadow(6, 288, 85)
    floor = stage.front - 10
    # One wheel is still on it. Where the other was, it sits on a block.
    s.box(206, floor - 20, 44, 20, STONE, 3)
    s.oval(40, floor - 44, 46, 46, RUBBER, 255, outline=True)
    s.oval(54, floor - 30, 18, 18, DARK_METAL, 255, outline=True)
    body = [
        (8, floor - 16), (8, floor - 42), (20, floor - 52), (74, floor - 56), (104, floor - 92), (196, floor - 92),
        (228, floor - 58), (284, floor - 54), (292, floor - 40), (292, floor - 16),
    ]
    s.poly(body, paint)
    # A little of its top is seen: the roof and the bonnet catch the light.
    s.poly([(106, floor - 90), (194, floor - 90), (188, floor - 82), (112, floor - 82)], lighter(paint, 0.24), outline=False)
    s.poly([(22, floor - 50), (74, floor - 54), (70, floor - 47), (26, floor - 44)], lighter(paint, 0.2), outline=False)
    s.shade(10, floor - 26, 280, 9, darker(paint, 0.2), 255, 3)
    s.poly([(110, floor - 84), (146, floor - 84), (146, floor - 58), (90, floor - 58)], (56, 66, 74))
    s.poly([(154, floor - 84), (192, floor - 84), (216, floor - 58), (154, floor - 58)], (56, 66, 74))
    s.stroke([(100, floor - 62), (118, floor - 80)], (120, 140, 150), 2.2)
    s.stroke([(150, floor - 56), (150, floor - 18)], darker(paint, 0.5), 2)
    s.stroke([(86, floor - 56), (86, floor - 18)], darker(paint, 0.5), 2)
    s.oval(30, floor - 52, 60, 44, (40, 30, 28))
    s.oval(40, floor - 44, 46, 46, RUBBER, 255, outline=True)
    s.oval(54, floor - 30, 18, 18, DARK_METAL, 255, outline=True)
    s.oval(202, floor - 52, 56, 40, (40, 30, 28))
    for x, y, wide in ((112, floor - 44, 30), (236, floor - 46, 34), (22, floor - 40, 22), (170, floor - 36, 26)):
        s.oval(x, y, wide, 11, darker(paint, 0.4))
    s.box(8, floor - 44, 12, 12, YELLOW, 3)
    s.box(280, floor - 48, 12, 12, darker(RED, 0.2), 3)
    return stage.picture()


def tyres(cell: int, depth: int, frame: int = 0) -> ObjectPicture:
    """Old tyres, stacked."""
    stage = Stage((1, 1), 30, cell, depth)
    s = stage.under
    stage.shadow(10, 80)
    floor = stage.front - 6
    for step in range(3):
        y = floor - 34 - step * 17
        s.box(12, y + 11, 76, 20, RUBBER, 9)
        s.oval(12, y, 76, 26, lighter(RUBBER, 0.14), 255, outline=True)
        s.oval(32, y + 6, 36, 13, (26, 24, 26), 255, outline=True)
        for x in (20, 50, 78):
            s.stroke([(x, y + 22), (x + 2, y + 30)], lighter(RUBBER, 0.3), 1.8)
    return stage.picture()


def junk(cell: int, depth: int, frame: int = 0) -> ObjectPicture:
    """Loose rubbish underfoot: a tin, a board, a broken bottle."""
    stage = Stage((1, 1), 14, cell, depth)
    s = stage.under
    middle, reach = stage.middle, stage.front - stage.back
    s.poly([(12, middle + reach * 0.14), (56, middle - reach * 0.2), (62, middle - reach * 0.08), (18, middle + reach * 0.26)], PALE_WOOD)
    s.box(60, middle + reach * 0.04, 20, 22, METAL, 4)
    s.oval(60, middle + reach * 0.04 - 5, 20, 10, lighter(METAL, 0.3), 255, outline=True)
    s.poly([(30, middle + reach * 0.34), (38, middle + reach * 0.16), (48, middle + reach * 0.22), (46, middle + reach * 0.4)], GREEN)
    for x, y in ((20, -0.3), (78, -0.26), (44, -0.34)):
        s.oval(x, middle + reach * y, 7, 6, DARK_METAL, 255, outline=True)
    return stage.picture()


def caravan_cart(cell: int, depth: int, frame: int = 0) -> ObjectPicture:
    """The covered cart of whoever comes to trade."""
    stage = Stage((2, 1), 104, cell, depth)
    s = stage.under
    stage.shadow(6, 188, 80)
    floor = stage.front - 6
    deep = (stage.front - stage.back) * 0.5
    top = floor - 26 - 24 - deep
    s.stroke([(24, top + deep + 8), (2, top + deep + 22)], LINE, 8)
    s.stroke([(24, top + deep + 8), (2, top + deep + 22)], WOOD, 4)
    for x in (30, 134):
        s.oval(x, floor - 40, 40, 40, darker(WOOD, 0.3), 255, outline=True)
        s.oval(x + 13, floor - 27, 14, 14, METAL, 255, outline=True)
        for dx, dy in ((20, 4), (20, 36), (4, 20), (36, 20)):
            s.stroke([(x + 20, floor - 20), (x + dx, floor - 40 + dy)], LINE, 1.8)
    s.block(18, top, 168, deep, 24, WOOD, 4, darker(WOOD, 0.4))
    for x in (60, 102, 144):
        s.stroke([(x, top + deep + 3), (x, top + deep + 21)], darker(WOOD, 0.34), 1.6)
    # The awning over it, on its hoops, patched.
    s.box(22, top - 70, 160, 70 + deep * 0.5, CANVAS, 30)
    s.shade(30, top - 62, 144, 10, lighter(CANVAS, 0.5), 255, 5)
    for x in (62, 102, 142):
        s.stroke([(x, top - 66), (x, top + deep * 0.5 - 4)], darker(CANVAS, 0.3), 2)
    s.box(108, top - 44, 26, 22, (206, 150, 96), 3)
    for x, y in ((112, top - 40), (126, top - 28)):
        s.stroke([(x, y), (x + 4, y + 4)], LINE, 1.6)
    s.box(150, top - 34, 22, 34 + deep * 0.3, (56, 44, 40), 4)
    s.box(154, top - 14, 14, 14 + deep * 0.3, PALE_WOOD, 2)
    s.oval(156, top - 30, 10, 12, YELLOW, 255, outline=True)
    return stage.picture()


Painter = Callable[[int, int, int], ObjectPicture]

# The picture the game draws of each kind of object, by kind.
def stocks(cell: int, depth: int, frame: int = 0) -> ObjectPicture:
    """A board with three holes in it between two posts, for a head and two hands."""
    stage = Stage((1, 1), 60, cell, depth)
    s = stage.under
    stage.shadow(8, 84, 60)
    floor = stage.front - (stage.front - stage.back) * 0.3
    top = max(6.0, floor - 88)
    for x in (14, 76):
        s.box(x, top + 4, 10, floor - top - 4, WOOD, 2)
    s.box(6, top + 14, 88, 32, PALE_WOOD, 4)
    s.stroke([(9, top + 30), (91, top + 30)], LINE, 1.8)
    s.oval(40, top + 20, 20, 20, darker(WOOD, 0.55), 255, outline=True)
    for x in (16, 70):
        s.oval(x, top + 23, 14, 14, darker(WOOD, 0.55), 255, outline=True)
    return stage.picture()


def gallows(cell: int, depth: int, frame: int = 0) -> ObjectPicture:
    """A post with an arm to it and a rope hanging from the arm, on a low stand."""
    stage = Stage((1, 1), 170, cell, depth)
    s = stage.under
    stage.shadow(4, 92, 60)
    floor = stage.front - (stage.front - stage.back) * 0.3
    top = max(6.0, floor - 210)
    s.box(6, floor - 16, 88, 16, WOOD, 3)
    s.shade(10, floor - 13, 80, 4, lighter(WOOD, 0.3), 255, 2)
    s.box(18, top + 6, 12, floor - top - 20, PALE_WOOD, 2)
    s.box(14, top, 70, 12, PALE_WOOD, 3)
    s.stroke([(30, top + 46), (56, top + 12)], darker(WOOD, 0.3), 5.0)
    s.stroke([(72, top + 12), (72, top + 62)], CANVAS, 3.0)
    s.oval(63, top + 60, 18, 24, CANVAS, 0, outline=True)
    return stage.picture()


def guillotine(cell: int, depth: int, frame: int = 0) -> ObjectPicture:
    """Two tall posts with a slanted blade up between them, and a board with a hole at their foot."""
    stage = Stage((1, 1), 180, cell, depth)
    s = stage.under
    stage.shadow(4, 92, 60)
    floor = stage.front - (stage.front - stage.back) * 0.3
    top = max(6.0, floor - 220)
    s.box(6, floor - 14, 88, 14, WOOD, 3)
    for x in (22, 68):
        s.box(x, top + 8, 10, floor - top - 20, PALE_WOOD, 2)
    s.box(18, top, 64, 12, PALE_WOOD, 3)
    s.poly([(32, top + 22), (68, top + 22), (68, top + 58), (32, top + 40)], METAL)
    s.stroke([(34, top + 41), (67, top + 57)], lighter(METAL, 0.5), 2.0)
    s.box(32, top + 14, 36, 9, DARK_METAL, 2)
    s.box(26, floor - 50, 48, 34, WOOD, 3)
    s.oval(41, floor - 42, 18, 18, darker(WOOD, 0.55), 255, outline=True)
    return stage.picture()


PAINTERS: dict[str, Painter] = {
    "bed": bed,
    "pantry": pantry,
    "campfire": campfire,
    "table": table,
    "stool": stool,
    "crate": crate,
    "study_desk": study_desk,
    "cooking_pot": cooking_pot,
    "bar": bar,
    "workbench": workbench,
    "shop_counter": shop_counter,
    "shelf": shelf,
    "barrel": barrel,
    "scrap_pile": scrap_pile,
    "water_tank": water_tank,
    "generator": generator,
    "clinic_bed": clinic_bed,
    "medicine_cabinet": medicine_cabinet,
    "lamp": lamp,
    "handcart": handcart,
    "radio_set": radio_set,
    "lab_bench": lab_bench,
    "crop_bed": crop_bed,
    "guard_post": guard_post,
    "grave": grave,
    "wreck": wreck,
    "tyres": tyres,
    "junk": junk,
    "caravan_cart": caravan_cart,
    "stocks": stocks,
    "gallows": gallows,
    "guillotine": guillotine,
}
# The ground each is drawn for, in cells: a kind whose data says otherwise keeps the art there was.
FOOTPRINTS: dict[str, tuple[int, int]] = {
    "bed": (1, 2), "clinic_bed": (1, 2), "table": (2, 1), "bar": (3, 1), "workbench": (2, 1), "shop_counter": (2, 1),
    "shelf": (2, 1), "scrap_pile": (2, 1), "water_tank": (2, 2), "generator": (2, 1), "lab_bench": (2, 1),
    "wreck": (3, 2), "caravan_cart": (2, 1),
}
# How many turns the picture of a kind goes through, for what burns.
FRAMES: dict[str, int] = {"campfire": 3, "barrel": 3, "study_desk": 3, "lab_bench": 3}


def footprint(kind: str) -> tuple[int, int]:
    return FOOTPRINTS.get(kind, (1, 1))


class ObjectPictures:
    """Makes the game's picture of each kind of object at the size it is asked for, once, and keeps it."""

    def __init__(self) -> None:
        self._kept: dict[tuple[str, int, int, int], ObjectPicture] = {}

    def has(self, kind: str, width: int, height: int) -> bool:
        """Whether there is a picture of a kind, for something that takes up that much ground."""
        return kind in PAINTERS and footprint(kind) == (width, height)

    def frames(self, kind: str) -> int:
        return FRAMES.get(kind, 1)

    def at(self, kind: str, cell: int, frame: int = 0) -> ObjectPicture:
        """A kind of object for cells that wide, as deep as they look from where it is seen."""
        return self.picture(kind, cell, max(1, round(cell * DEPTH)), frame)

    def whole(self, kind: str, cell: int) -> pygame.Surface:
        """A kind of object in one piece, as for a catalogue: what is over it laid on what is under."""
        picture = self.at(kind, cell)
        if picture.over is None:
            return picture.under
        whole = picture.under.copy()
        whole.blit(picture.over, (0, 0))
        return whole

    def picture(self, kind: str, cell: int, depth: int, frame: int = 0) -> ObjectPicture:
        """A kind of object for cells that wide and that deep, at one turn of its picture."""
        key = (kind, cell, depth, frame % self.frames(kind))
        if key not in self._kept:
            self._kept[key] = PAINTERS[kind](cell, depth, key[3])
        return self._kept[key]
