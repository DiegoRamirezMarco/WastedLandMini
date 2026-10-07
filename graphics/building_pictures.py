"""Buildings as the game draws them: a roof of sheet metal over a front of boards, and the inside with the roof off.

The same hand as the furniture (`graphics.cartoon`). A picture takes up what a building's picture
always has on the map: the room, the walls round it and a tile of headroom above. Everything is
measured in hundredths of a tile, from the top left corner of that.

A building somebody has drawn keeps their drawing. These are what the game shows of the rest.
"""

import random
from collections.abc import Sequence

import pygame

from graphics.cartoon import GLASS, LINE, PAPER, RUST, WOOD, Sheet
from graphics.palette import Color
from graphics.ui_art import darker, lighter, mix
from world.room import Room

# Tiles of the picture that are the front of the building, from its foot up: the wall with the door in it and the row before it.
FRONT_ROWS = 2
ROOFS: tuple[Color, ...] = ((126, 138, 150), (156, 100, 74), (116, 134, 112), (150, 142, 122))
FRONTS: tuple[Color, ...] = ((202, 116, 64), (208, 164, 90), (164, 150, 134), (186, 96, 78))
DOORS: tuple[Color, ...] = ((62, 132, 144), (88, 140, 96), (70, 104, 152))
AWNING: Color = (92, 156, 132)
FLOORS: dict[str, Color] = {"floor_wood": (176, 132, 94), "floor_concrete": (140, 138, 132)}
PLAIN_FLOOR: Color = (156, 136, 110)
INNER_WALL: Color = (150, 112, 84)


def _size(room: Room, cell: int) -> tuple[int, int]:
    return ((room.width + 2) * cell, (room.height + 3) * cell)


def _seed(room: Room) -> int:
    return sum(ord(letter) * (index + 1) for index, letter in enumerate(room.blueprint_id or room.room_id))


def closed(room: Room, cell: int, doors: Sequence[int]) -> pygame.Surface:
    """A building with its roof on. `doors` are the columns its doors are in, counted in tiles from its left edge."""
    # Not the simulation's randomness: the same dents every time, and nothing rides on them.
    chance = random.Random(_seed(room))
    sheet = Sheet(_size(room, cell), cell / 100.0, line=4.0)
    wide, tall = (room.width + 2) * 100.0, (room.height + 3) * 100.0
    front = tall - FRONT_ROWS * 100.0
    roof = ROOFS[_seed(room) % len(ROOFS)]
    boards = FRONTS[(_seed(room) // 3) % len(FRONTS)]
    door = DOORS[(_seed(room) // 7) % len(DOORS)]

    # The front, of boards standing side by side, with a skirting along its foot.
    sheet.box(4, front - 6, wide - 8, tall - front + 2, boards, 5)
    for x in range(30, int(wide) - 10, 25):
        sheet.stroke([(x, front + 8), (x, tall - 14)], darker(boards, 0.26), 1.8)
    sheet.shade(7, front + 26, wide - 14, 12, darker(boards, 0.12), 110)
    sheet.shade(7, tall - 24, wide - 14, 16, darker(boards, 0.34), 255, 3)
    doors = [column for column in doors if 0 <= column <= room.width + 1]
    for column in range(1, room.width + 1):
        left = column * 100.0
        if column in doors:
            sheet.box(left + 10, front + 46, 80, 146, door, 5)
            sheet.box(left + 24, front + 62, 52, 34, darker(GLASS, 0.3), 3)
            sheet.stroke([(left + 30, front + 90), (left + 44, front + 68)], lighter(GLASS, 0.5), 2.4)
            sheet.shade(left + 18, front + 106, 64, 74, darker(door, 0.16), 255, 3)
            sheet.oval(left + 70, front + 128, 10, 10, (236, 196, 90), 255, outline=True)
            # A striped awning over it.
            sheet.poly([(left - 6, front + 12), (left + 106, front + 12), (left + 112, front + 42), (left - 12, front + 42)], AWNING, outline=False)
            for index in range(5):
                if index % 2:
                    span = 124.0 / 5
                    sheet.poly(
                        [(left - 6 + index * 22.4, front + 12), (left - 6 + (index + 1) * 22.4, front + 12),
                         (left - 12 + (index + 1) * span, front + 42), (left - 12 + index * span, front + 42)],
                        PAPER,
                        outline=False,
                    )
            sheet.stroke([(left - 6, front + 12), (left + 106, front + 12), (left + 112, front + 42), (left - 12, front + 42), (left - 6, front + 12)], LINE, 3.6)
        elif column % 2 == 0 and column - 1 not in doors and column + 1 not in doors:
            sheet.box(left + 22, front + 70, 56, 46, (52, 64, 78), 4)
            sheet.stroke([(left + 50, front + 72), (left + 50, front + 114)], LINE, 2.6)
            sheet.stroke([(left + 28, front + 104), (left + 40, front + 78)], (120, 150, 170), 2.4)
            sheet.box(left + 16, front + 114, 68, 9, darker(boards, 0.3), 2)

    # The roof, seen from a little above: sheets of ridged metal, patched and rusting.
    sheet.box(0, 6, wide, front + 8, roof, 7)
    sheet.shade(4, 10, wide - 8, 12, lighter(roof, 0.3), 255, 5)
    for x in range(25, int(wide), 25):
        sheet.stroke([(x, 22), (x, front + 4)], darker(roof, 0.2), 1.6)
        sheet.stroke([(x + 3, 22), (x + 3, front + 4)], lighter(roof, 0.14), 1.0)
    for y in (front * 0.36, front * 0.7):
        sheet.stroke([(4, y), (wide - 4, y)], darker(roof, 0.36), 2.2)
    for _ in range(max(2, room.width * room.height // 5)):
        x, y = chance.uniform(20, wide - 110), chance.uniform(30, max(40.0, front - 80))
        if chance.random() < 0.5:
            sheet.box(x, y, chance.uniform(50, 90), chance.uniform(36, 58), mix(roof, RUST, 0.55), 3)
        else:
            sheet.oval(x, y, chance.uniform(40, 80), chance.uniform(20, 34), mix(roof, RUST, 0.7), 190)
    for x in range(40, int(wide) - 20, 110):
        sheet.oval(x, front - 10, 8, 8, darker(roof, 0.5))
    # The eave, and the shade under it.
    sheet.box(-2, front - 6, wide + 4, 18, darker(roof, 0.3), 4)
    sheet.shade(8, front + 12, wide - 16, 10, (0, 0, 0), 60)
    return sheet.finished()


def opened(room: Room, cell: int, doors: Sequence[int], floor_kind: str, foreground: bool) -> pygame.Surface:
    """A building with its roof off: the floor, the back wall and the sides, or with `foreground` the wall in front."""
    sheet = Sheet(_size(room, cell), cell / 100.0, line=4.0)
    wide, tall = (room.width + 2) * 100.0, (room.height + 3) * 100.0
    front = tall - 100.0
    boards = FRONTS[(_seed(room) // 3) % len(FRONTS)]
    if foreground:
        # What is left of the wall in front, cut low so that the room is seen over it.
        runs: list[tuple[float, float]] = []
        start = 0.0
        for column in sorted(set(doors)):
            if 0 < column <= room.width:
                runs.append((start, column * 100.0))
                start = (column + 1) * 100.0
        runs.append((start, wide))
        for left, right in runs:
            if right - left > 1:
                sheet.block(left + 2, front + 34, right - left - 4, 22, 40, boards, 4, darker(boards, 0.2))
        for column in doors:
            if 0 < column <= room.width:
                sheet.shade(column * 100.0 + 4, front + 60, 92, 34, darker(FLOORS.get(floor_kind, PLAIN_FLOOR), 0.3), 255, 3)
        return sheet.finished()

    chance = random.Random(_seed(room) + 1)
    floor = FLOORS.get(floor_kind, PLAIN_FLOOR)
    # The back wall, face on, a tile and a half tall.
    sheet.box(4, 50, wide - 8, 152, INNER_WALL, 4)
    for x in range(30, int(wide) - 10, 25):
        sheet.stroke([(x, 58), (x, 192)], darker(INNER_WALL, 0.26), 1.6)
    sheet.shade(8, 54, wide - 16, 12, darker(INNER_WALL, 0.4), 255, 3)
    sheet.shade(8, 184, wide - 16, 14, darker(INNER_WALL, 0.36), 255, 2)
    # The floor.
    sheet.box(96, 198, wide - 192, front - 196, floor, 0)
    if floor_kind == "floor_wood":
        for index, y in enumerate(range(225, int(front), 25)):
            sheet.stroke([(100, y), (wide - 100, y)], darker(floor, 0.16), 1.4)
            for x in range(100 + (index % 3) * 70, int(wide) - 100, 210):
                sheet.stroke([(x, y - 25), (x, y)], darker(floor, 0.16), 1.4)
    else:
        for _ in range(room.width * room.height * 2):
            x, y = chance.uniform(104, wide - 110), chance.uniform(204, front - 10)
            sheet.oval(x, y, chance.uniform(4, 9), chance.uniform(3, 6), darker(floor, 0.12))
    sheet.shade(98, 200, wide - 196, 20, (0, 0, 0), 50)
    # The walls at the sides, seen from above.
    for left in (4.0, wide - 100.0):
        sheet.box(left, 196, 96, tall - 200, darker(boards, 0.3), 3)
        sheet.shade(left + 6, 202, 20, tall - 212, lighter(boards, 0.06), 150, 3)
    return sheet.finished()
