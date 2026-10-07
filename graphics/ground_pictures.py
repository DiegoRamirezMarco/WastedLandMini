"""The ground of a whole map as the game draws it: earth, grass, tilled soil, and the fence round it all.

The same hand as the furniture (`graphics.cartoon`), in one picture for the whole map, which goes
under everything that stands on it. A ground somebody has made a picture of keeps theirs.

Everything is measured in hundredths of a tile.
"""

import random

import pygame

from graphics.cartoon import DARK_METAL, LINE, METAL, RUST, SOIL, STONE, WOOD, Sheet
from graphics.palette import Color
from graphics.ui_art import darker, lighter, mix
from world.map import Tile, TileMap

EARTH: Color = (158, 132, 100)
GRASS: Color = (118, 146, 86)
# What is under a roof or a wall is never seen: a building's own picture is over it.
COVERED: Color = (70, 58, 50)
BUILT = ("wall", "door", "floor_wood", "floor_concrete")
# A picture this large is drawn only twice over before it is brought down to size.
DETAIL = 2


def _is(tile_map: TileMap, tile: Tile, terrain: str) -> bool:
    return tile_map.in_bounds(tile) and tile_map.terrain_at(tile) == terrain


def ground(tile_map: TileMap, cell: int, seed: int = 0) -> pygame.Surface:
    """The ground of a map, `cell` pixels to a tile."""
    # Not the simulation's randomness: the same stones every time, and nothing rides on them.
    chance = random.Random(seed)
    width, height = tile_map.width, tile_map.height
    sheet = Sheet((width * cell, height * cell), cell / 100.0, line=4.0, detail=DETAIL)
    sheet.shade(0, 0, width * 100, height * 100, EARTH)
    # The earth is not all one colour.
    for _ in range(width * height // 3):
        x, y = chance.uniform(0, width * 100), chance.uniform(0, height * 100)
        tint = (0, 0, 0) if chance.random() < 0.5 else (255, 240, 210)
        sheet.oval(x - 90, y - 50, chance.uniform(120, 260), chance.uniform(70, 150), tint, 12)

    tiles = [(x, y, tile_map.terrain_at((x, y))) for y in range(height) for x in range(width)]
    # Grass first, each tile a little larger than itself, so that patches of it run together with soft edges.
    # Each patch is a little out of true, so that a row of them is not a row of squares.
    patches = [
        (x * 100 + chance.uniform(-8, 8), y * 100 + chance.uniform(-8, 8), chance.uniform(118, 138))
        for x, y, terrain in tiles
        if terrain == "grass"
    ]
    for left, top, side in patches:
        sheet.shade(left - 16, top - 14, side + 8, side + 6, mix(GRASS, EARTH, 0.55), 255, 44)
    for left, top, side in patches:
        sheet.shade(left - 10, top - 10, side - 4, side - 6, darker(GRASS, 0.1), 255, 40)
    for left, top, side in patches:
        sheet.shade(left - 8, top - 12, side - 8, side - 12, GRASS, 255, 38)
    for x, y, terrain in tiles:
        left, top = x * 100.0, y * 100.0
        if terrain == "grass":
            for _ in range(3):
                tx, ty = left + chance.uniform(10, 86), top + chance.uniform(22, 92)
                blade = lighter(GRASS, 0.24) if chance.random() < 0.5 else darker(GRASS, 0.3)
                sheet.stroke([(tx - 6, ty - 14), (tx, ty), (tx + 2, ty - 18)], blade, 2.6)
                sheet.stroke([(tx, ty), (tx + 8, ty - 12)], blade, 2.6)
        elif terrain == "dirt":
            if chance.random() < 0.16:
                px, py = left + chance.uniform(14, 70), top + chance.uniform(20, 76)
                sheet.oval(px, py, chance.uniform(10, 20), chance.uniform(7, 12), STONE, 255, outline=True)
            if chance.random() < 0.12:
                cx, cy = left + chance.uniform(10, 60), top + chance.uniform(20, 80)
                sheet.stroke([(cx, cy), (cx + 14, cy + 4), (cx + 24, cy - 2)], darker(EARTH, 0.22), 1.8)
            if chance.random() < 0.08:
                tx, ty = left + chance.uniform(20, 80), top + chance.uniform(40, 90)
                sheet.stroke([(tx - 5, ty - 12), (tx, ty), (tx + 4, ty - 14)], darker(GRASS, 0.1), 2.4)
        elif terrain == "soil":
            sheet.shade(left - 1, top - 1, 102, 102, SOIL)
            for row in (22, 54, 86):
                sheet.stroke([(left + 4, top + row), (left + 96, top + row)], darker(SOIL, 0.3), 4)
                sheet.stroke([(left + 4, top + row - 9), (left + 96, top + row - 9)], lighter(SOIL, 0.14), 2.4)
        elif terrain in BUILT:
            sheet.shade(left - 1, top - 1, 102, 102, COVERED)
        elif terrain == "gate":
            sheet.shade(left - 1, top + 10, 102, 80, darker(EARTH, 0.14), 255, 20)
            for share in (0.3, 0.62):
                sheet.stroke([(left + 6, top + 100 * share), (left + 94, top + 100 * share + 6)], darker(EARTH, 0.26), 2)

    # The fence, over the ground: sheets of metal seen from the front where it runs across, and from above where it runs down.
    for x, y, terrain in tiles:
        if terrain != "fence":
            continue
        left, top = x * 100.0, y * 100.0
        across = _is(tile_map, (x - 1, y), "fence") or _is(tile_map, (x + 1, y), "fence") or _is(tile_map, (x - 1, y), "gate") or _is(tile_map, (x + 1, y), "gate")
        down = _is(tile_map, (x, y - 1), "fence") or _is(tile_map, (x, y + 1), "fence")
        if down and not across:
            sheet.box(left + 34, top - 4, 32, 108, darker(METAL, 0.2), 3)
            sheet.shade(left + 39, top, 9, 100, lighter(METAL, 0.2), 255, 3)
            continue
        panel = mix(METAL, RUST, chance.choice((0.0, 0.25, 0.6)))
        sheet.box(left - 2, top + 16, 104, 74, panel, 3)
        for ridge in range(12, 100, 22):
            sheet.stroke([(left + ridge, top + 22), (left + ridge, top + 84)], darker(panel, 0.22), 2)
        sheet.shade(left, top + 19, 100, 7, lighter(panel, 0.3), 255, 2)
        if chance.random() < 0.4:
            sheet.oval(left + chance.uniform(10, 60), top + chance.uniform(40, 62), chance.uniform(18, 34), 14, mix(panel, RUST, 0.8), 200)
        if down:
            sheet.box(left + 34, top - 4, 32, 36, darker(METAL, 0.2), 3)
    # Posts where the fence turns or ends, and at either side of the way in.
    for x, y, terrain in tiles:
        if terrain != "fence":
            continue
        left, top = x * 100.0, y * 100.0
        beside_gate = _is(tile_map, (x - 1, y), "gate") or _is(tile_map, (x + 1, y), "gate")
        corner = (
            (_is(tile_map, (x - 1, y), "fence") or _is(tile_map, (x + 1, y), "fence"))
            and (_is(tile_map, (x, y - 1), "fence") or _is(tile_map, (x, y + 1), "fence"))
        )
        if beside_gate or corner or x % 5 == 0:
            post = WOOD if beside_gate else DARK_METAL
            sheet.box(left + 36, top - 2, 28, 96, post, 4)
            sheet.shade(left + 41, top + 3, 7, 84, lighter(post, 0.26), 255, 3)
            sheet.box(left + 30, top - 8, 40, 14, darker(post, 0.1), 4)
    sheet.stroke([(0, 0), (width * 100, 0)], LINE, 0.1)
    return sheet.finished()
