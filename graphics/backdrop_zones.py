"""The game's own backdrops of the zones there are besides the ruins (S68): the forest at the
gate, the mountain top, the nuclear plant and the crater.

Drawn as the ruins are (`graphics.backdrop_pictures`), with what that has to draw with: a
layer at a time, at whatever size it is asked for, each meeting itself at its ends.
"""

import random

from graphics.backdrop_pictures import (
    BARK,
    CONCRETE,
    DRY,
    ROAD_BELOW,
    TALL,
    VERGE,
    Layer,
    Thing,
    _broken_top,
    _earth,
    _height_at,
    _round,
    _sky,
)
from graphics.cartoon import DARK_METAL, LINE, METAL, RUST, YELLOW, Sheet
from graphics.palette import Color
from graphics.ui_art import darker, lighter, mix

PINE: Color = (62, 92, 70)
PINE_FAR: Color = (112, 136, 122)
FOREST_HAZE: Color = (206, 208, 178)
MOSS: Color = (112, 124, 78)
FOREST_EARTH: Color = (132, 114, 84)
ROCK: Color = (134, 138, 146)
SNOW: Color = (236, 240, 244)
COLD_HAZE: Color = (208, 220, 230)
SICK_HIGH: Color = (126, 138, 104)
SICK_LOW: Color = (222, 214, 138)
SLAB: Color = (150, 148, 140)
GLOW: Color = (150, 232, 110)
ASH: Color = (62, 54, 58)
CHAR: Color = (34, 30, 34)
DUSK_HIGH: Color = (58, 40, 62)
DUSK_LOW: Color = (168, 92, 74)


# ----- the forest -----


def _forest_sky(sheet: Sheet, wide: float, chance: random.Random, ground: float) -> None:
    _sky(sheet, wide, chance, ground, (128, 160, 156), (228, 222, 178), haze=FOREST_HAZE, sun_at=(0.3, 58.0))


def _pine(sheet: Sheet, x: float, base: float, high: float, color: Color, outline: bool = True) -> None:
    """A pine: a trunk, and boughs in tiers that get narrower towards the top."""
    across = high * 0.42
    if outline:
        sheet.box(x - 1.6, base - high * 0.28, 3.2, high * 0.28, BARK, 0.6)
    tiers = 4
    for tier in range(tiers):
        low = base - high * (0.16 + 0.2 * tier)
        reach = across * (1.0 - tier * 0.2) / 2
        sheet.poly([(x - reach, low), (x, low - high * 0.34), (x + reach, low)], color, outline)


def _forest_far(sheet: Sheet, wide: float, chance: random.Random, ground: float) -> None:
    base = ground - 6
    things: list[Thing] = []
    x = 0.0
    while x < wide:
        high = chance.uniform(40, 86)
        color = mix(PINE_FAR, FOREST_HAZE, chance.uniform(0.1, 0.5))

        def tree(along: float, x=x, high=high, color=color) -> None:
            _pine(sheet, x + along, base, high, color, outline=False)

        things.append(tree)
        x += chance.uniform(9, 24)
    _round(things, wide)


def _bare_tree(sheet: Sheet, chance: random.Random, x: float, base: float, high: float) -> Thing:
    boughs = [(chance.uniform(0.4, 0.92), chance.choice((-1, 1)) * chance.uniform(9, 26), chance.uniform(8, 24)) for _ in range(6)]
    lean = chance.uniform(-5, 5)

    def tree(along: float) -> None:
        foot = x + along
        trunk = [(foot, base), (foot + lean * 0.5, base - high * 0.5), (foot + lean, base - high)]
        sheet.stroke(trunk, LINE, 6.4)
        sheet.stroke(trunk, BARK, 4.2)
        for share, reach, rise in boughs:
            start = (foot + lean * share, base - high * share)
            sheet.stroke([start, (start[0] + reach * 0.6, start[1] - rise * 0.4), (start[0] + reach, start[1] - rise)], BARK, 1.7)

    return tree


def _forest_middle(sheet: Sheet, wide: float, chance: random.Random, ground: float) -> None:
    base = ground - 9
    things: list[Thing] = []
    x = chance.uniform(4, 16)
    while x < wide - 6:
        kind = chance.random()
        if kind < 0.5:
            high = chance.uniform(70, 150)
            color = mix(PINE, MOSS, chance.uniform(0.0, 0.35))

            def pine(along: float, x=x, high=high, color=color) -> None:
                _pine(sheet, x + along, base, high, color)

            things.append(pine)
        elif kind < 0.82:
            things.append(_bare_tree(sheet, chance, x, base, chance.uniform(80, 150)))
        else:
            across = chance.uniform(10, 16)

            def stump(along: float, x=x, across=across) -> None:
                sheet.box(x + along - across / 2, base - 12, across, 12, BARK, 1.5)
                sheet.oval(x + along - across / 2, base - 15, across, 6, lighter(BARK, 0.3), 255, outline=True)

            things.append(stump)
        x += chance.uniform(16, 40)
    for _ in range(int(wide // 22)):
        bx, across, high = chance.uniform(0, wide), chance.uniform(18, 40), chance.uniform(8, 16)
        color = mix(MOSS, PINE, chance.uniform(0.1, 0.5))

        def bush(along: float, bx=bx, across=across, high=high, color=color) -> None:
            sheet.oval(bx + along, base - high * 0.7, across, high * 1.7, color, 255, outline=True)

        things.append(bush)
    _round(things, wide)


def _forest_ground(sheet: Sheet, wide: float, chance: random.Random, ground: float) -> None:
    _earth(sheet, wide, chance, ground, earth=FOREST_EARTH, dry=MOSS, stones=(126, 122, 110))
    # A path worn along it, where feet come down.
    sheet.shade(-2, ground - 6, wide + 4, ROAD_BELOW + 2, lighter(FOREST_EARTH, 0.14), 150, 6)


def _forest_front(sheet: Sheet, wide: float, chance: random.Random, ground: float) -> None:
    floor = TALL + 6
    things: list[Thing] = []
    slots = max(3, int(wide // 110))
    for slot in range(slots):
        x = (slot + chance.uniform(0.15, 0.75)) * wide / slots
        if slot % 3 == 0:
            long = chance.uniform(60, 90)

            def log(along: float, x=x, long=long) -> None:
                sheet.box(x + along, TALL - 20, long, 18, darker(BARK, 0.1), 8)
                sheet.oval(x + along + long - 9, TALL - 20, 12, 18, lighter(BARK, 0.25), 255, outline=True)

            things.append(log)
        else:
            fronds = [(chance.uniform(-22, 22), chance.uniform(16, 30)) for _ in range(8)]

            def fern(along: float, x=x, fronds=fronds) -> None:
                for lean, long in fronds:
                    tip = (x + along + lean, TALL - long)
                    sheet.stroke([(x + along, floor), ((x + along + tip[0]) / 2 + lean * 0.3, (floor + tip[1]) / 2), tip], darker(MOSS, 0.25), 2.0)

            things.append(fern)
    _round(things, wide)


# ----- the mountain top -----


def _summit_sky(sheet: Sheet, wide: float, chance: random.Random, ground: float) -> None:
    _sky(sheet, wide, chance, ground, (92, 138, 186), (214, 228, 236), SNOW, SNOW, COLD_HAZE, (0.2, 48.0))


def _peak(sheet: Sheet, x: float, base: float, across: float, high: float, rock: Color, outline: bool) -> None:
    """A peak with snow down from its top."""
    top = (x + across * 0.46, base - high)
    sheet.poly([(x, base), top, (x + across, base)], rock, outline)
    cap = 0.34
    left = (x + across * 0.46 * (1 - cap), base - high * (1 - cap))
    right = (x + across - (across * 0.54) * (1 - cap), base - high * (1 - cap))
    middle = ((left[0] + right[0]) / 2, left[1] + high * 0.07)
    sheet.poly([left, top, right, (middle[0] + across * 0.08, middle[1] - high * 0.05), middle], SNOW, False)
    if outline:
        sheet.stroke([(x, base), top, (x + across, base)], LINE, 1.1)


def _summit_far(sheet: Sheet, wide: float, chance: random.Random, ground: float) -> None:
    base = ground - 6
    things: list[Thing] = []
    x = -20.0
    while x < wide:
        across, high = chance.uniform(90, 170), chance.uniform(60, 130)
        rock = mix(ROCK, COLD_HAZE, chance.uniform(0.3, 0.6))

        def peak(along: float, x=x, across=across, high=high, rock=rock) -> None:
            _peak(sheet, x + along, base, across, high, rock, False)

        things.append(peak)
        x += across * chance.uniform(0.45, 0.8)
    _round(things, wide)


def _summit_middle(sheet: Sheet, wide: float, chance: random.Random, ground: float) -> None:
    base = ground - 9
    things: list[Thing] = []
    x = chance.uniform(0, 30)
    while x < wide - 20:
        kind = chance.random()
        if kind < 0.55:
            across, high = chance.uniform(50, 110), chance.uniform(36, 84)
            rock = mix(ROCK, (104, 100, 104), chance.uniform(0.0, 0.5))

            def crag(along: float, x=x, across=across, high=high, rock=rock) -> None:
                _peak(sheet, x + along, base, across, high, rock, True)

            things.append(crag)
            x += across * 0.8
        elif kind < 0.75:
            high = chance.uniform(96, 130)

            def mast(along: float, x=x, high=high) -> None:
                foot = x + along
                for side in (-9, 9):
                    sheet.stroke([(foot + side, base), (foot, base - high)], DARK_METAL, 1.6)
                for rung in range(1, 6):
                    reach = 9 * (1 - rung / 6)
                    sheet.stroke([(foot - reach, base - high * rung / 6), (foot + reach, base - high * rung / 6)], DARK_METAL, 1.1)
                sheet.oval(foot - 9, base - high * 0.86, 12, 12, METAL, 255, outline=True)

            things.append(mast)
            x += 30
        else:
            high = chance.uniform(40, 70)

            def pine(along: float, x=x, high=high) -> None:
                _pine(sheet, x + along, base, high, mix(PINE, SNOW, 0.2))

            things.append(pine)
            x += 24
        x += chance.uniform(6, 30)
    _round(things, wide)


def _summit_ground(sheet: Sheet, wide: float, chance: random.Random, ground: float) -> None:
    _earth(sheet, wide, chance, ground, earth=(140, 142, 148), dry=(170, 178, 170), stones=(110, 112, 120))
    things: list[Thing] = []
    for _ in range(int(wide // 30)):
        x, y = chance.uniform(0, wide), chance.uniform(ground - VERGE + 2, TALL - 8)
        across = chance.uniform(30, 80)

        def snow(along: float, x=x, y=y, across=across) -> None:
            sheet.oval(x + along, y, across, across * 0.16, SNOW, 235)

        things.append(snow)
    _round(things, wide)


def _summit_front(sheet: Sheet, wide: float, chance: random.Random, ground: float) -> None:
    things: list[Thing] = []
    slots = max(3, int(wide // 120))
    for slot in range(slots):
        x = (slot + chance.uniform(0.2, 0.7)) * wide / slots
        across, high = chance.uniform(40, 70), chance.uniform(20, 32)

        def boulder(along: float, x=x, across=across, high=high) -> None:
            sheet.oval(x + along, TALL - high, across, high * 2.2, darker(ROCK, 0.25), 255, outline=True)
            sheet.oval(x + along + across * 0.12, TALL - high - 1, across * 0.7, high * 0.6, SNOW, 240)

        things.append(boulder)
    _round(things, wide)


# ----- the nuclear plant -----


def _plant_sky(sheet: Sheet, wide: float, chance: random.Random, ground: float) -> None:
    _sky(sheet, wide, chance, ground, SICK_HIGH, SICK_LOW, (250, 244, 190), (232, 226, 170), (214, 208, 140), (0.6, 74.0))


def _cooling_tower(sheet: Sheet, x: float, base: float, across: float, high: float, color: Color, outline: bool) -> None:
    waist = across * 0.32
    shape = [
        (x, base), (x + waist * 0.55, base - high * 0.55), (x + waist * 0.4, base - high),
        (x + across - waist * 0.4, base - high), (x + across - waist * 0.55, base - high * 0.55), (x + across, base),
    ]
    sheet.poly(shape, color, outline)
    if outline:
        sheet.shade(x + across * 0.62, base - high * 0.96, across * 0.14, high * 0.94, darker(color, 0.14), 150)
        sheet.stroke([(x + waist * 0.4, base - high), (x + across - waist * 0.4, base - high)], darker(color, 0.4), 2.2)


def _plant_far(sheet: Sheet, wide: float, chance: random.Random, ground: float) -> None:
    base = ground - 6
    things: list[Thing] = []
    x = chance.uniform(0, 30)
    while x < wide - 20:
        color = mix((132, 134, 122), SICK_LOW, chance.uniform(0.1, 0.38))
        if chance.random() < 0.6:
            across, high = chance.uniform(46, 70), chance.uniform(70, 112)

            def tower(along: float, x=x, across=across, high=high, color=color) -> None:
                _cooling_tower(sheet, x + along, base, across, high, color, False)
                # What still rises from it.
                for puff in range(3):
                    sheet.oval(x + along + across * 0.2 + puff * 6, base - high - 14 - puff * 12, across * 0.6, 16, (236, 236, 214), 70)

            things.append(tower)
            x += across
        else:
            high = chance.uniform(90, 130)

            def stack(along: float, x=x, high=high, color=color) -> None:
                sheet.poly([(x + along, base), (x + along + 2, base - high), (x + along + 8, base - high), (x + along + 10, base)], color, False)

            things.append(stack)
            x += 14
        x += chance.uniform(10, 46)
    _round(things, wide)


def _plant_middle(sheet: Sheet, wide: float, chance: random.Random, ground: float) -> None:
    base = ground - 9
    things: list[Thing] = []
    x = chance.uniform(4, 20)
    while x < wide - 30:
        kind = chance.random()
        if kind < 0.4:
            across, high = chance.uniform(70, 110), chance.uniform(50, 76)
            wall = mix(SLAB, (170, 168, 150), chance.uniform(0, 0.5))
            top = _broken_top(chance, 0.0, across, base - high, high * 0.25)

            def hall(along: float, x=x, across=across, high=high, wall=wall, top=top) -> None:
                left = x + along
                # The dome of what it was built round, behind it.
                sheet.oval(left + across * 0.2, base - high - across * 0.22, across * 0.6, across * 0.5, darker(wall, 0.1), 255, outline=True)
                sheet.poly([(left, base), *((left + px, py) for px, py in top), (left + across, base)], wall)
                sheet.box(left + across * 0.4, base - 26, 16, 26, (52, 48, 46), 1.0)
                for stripe in range(int(across // 16)):
                    sheet.shade(left + 4 + stripe * 16, _height_at(top, 4 + stripe * 16) + 10, 8, 4, YELLOW if stripe % 2 else LINE)
                sheet.stroke([(left + 6, base - high * 0.5), (left + across - 6, base - high * 0.5)], RUST, 3.0)

            things.append(hall)
            x += across
        elif kind < 0.7:
            high = chance.uniform(100, 136)

            def pylon(along: float, x=x, high=high) -> None:
                foot = x + along + 12
                for side in (-12, 12):
                    sheet.stroke([(foot + side, base), (foot + side * 0.2, base - high)], DARK_METAL, 1.8)
                for rung in range(1, 7):
                    reach = 12 * (1 - rung / 7 * 0.8)
                    y = base - high * rung / 7
                    sheet.stroke([(foot - reach, y), (foot + reach, y)], DARK_METAL, 1.0)
                    sheet.stroke([(foot - reach, y), (foot + reach * 0.7, y - high / 7)], DARK_METAL, 0.8)
                for arm in (0.78, 0.92):
                    sheet.stroke([(foot - 24, base - high * arm), (foot + 24, base - high * arm)], DARK_METAL, 1.6)

            things.append(pylon)
            x += 30
        else:
            across = chance.uniform(40, 80)

            def fence(along: float, x=x, across=across) -> None:
                left = x + along
                for post in range(0, int(across) + 1, 13):
                    sheet.stroke([(left + post, base), (left + post, base - 30)], DARK_METAL, 1.6)
                for wire in (10, 20, 29):
                    sheet.stroke([(left, base - wire), (left + across, base - wire + 2)], DARK_METAL, 0.7)
                sheet.poly([(left + across * 0.4, base - 27), (left + across * 0.4 + 13, base - 27), (left + across * 0.4 + 6.5, base - 14)], YELLOW)

            things.append(fence)
            x += across
        x += chance.uniform(8, 26)
    _round(things, wide)


def _plant_ground(sheet: Sheet, wide: float, chance: random.Random, ground: float) -> None:
    _earth(sheet, wide, chance, ground, earth=(128, 124, 102), dry=(160, 158, 92), stones=(120, 118, 110))
    things: list[Thing] = []
    sheet.shade(-2, ground - 7, wide + 4, ROAD_BELOW + 7, SLAB)
    for edge in (ground - 7, ground + ROAD_BELOW):
        sheet.stroke([(-2, edge), (wide + 2, edge)], LINE, 1.1)
    for joint in range(int(wide // 40) + 1):
        x = joint * wide / (int(wide // 40) + 1)

        def seam(along: float, x=x) -> None:
            sheet.stroke([(x + along, ground - 7), (x + along - 4, ground + ROAD_BELOW)], darker(SLAB, 0.35), 0.9)

        things.append(seam)
    for stripe in range(int(wide // 18)):
        x = stripe * wide / int(wide // 18)
        if chance.random() < 0.3:
            continue

        def hazard(along: float, x=x) -> None:
            sheet.poly([(x + along, ground + 14), (x + along + 8, ground + 14), (x + along + 4, ground + 19), (x + along - 4, ground + 19)], YELLOW, False)

        things.append(hazard)
    _round(things, wide)


def _barrel(sheet: Sheet, x: float, top: float, tipped: bool) -> None:
    if tipped:
        sheet.box(x, top + 12, 40, 26, YELLOW, 6)
        sheet.oval(x + 32, top + 12, 12, 26, darker(YELLOW, 0.2), 255, outline=True)
        return
    sheet.box(x, top, 26, 44, YELLOW, 4)
    for band in (10, 30):
        sheet.stroke([(x, top + band), (x + 26, top + band)], darker(YELLOW, 0.4), 1.4)
    sheet.oval(x + 8, top + 14, 10, 10, LINE)


def _plant_front(sheet: Sheet, wide: float, chance: random.Random, ground: float) -> None:
    things: list[Thing] = []
    slots = max(3, int(wide // 110))
    for slot in range(slots):
        x = (slot + chance.uniform(0.15, 0.7)) * wide / slots
        tipped = chance.random() < 0.4
        if slot % 3 == 2:

            def pipe(along: float, x=x) -> None:
                sheet.box(x + along, TALL - 16, 90, 14, darker(METAL, 0.2), 7)
                sheet.box(x + along + 40, TALL - 19, 8, 20, darker(METAL, 0.35), 2)

            things.append(pipe)
        else:

            def barrel(along: float, x=x, tipped=tipped) -> None:
                _barrel(sheet, x + along, TALL - 30, tipped)
                sheet.oval(x + along - 8, TALL - 5, 46, 8, GLOW, 110)

            things.append(barrel)
    _round(things, wide)


# ----- the crater -----


def _crater_sky(sheet: Sheet, wide: float, chance: random.Random, ground: float) -> None:
    _sky(sheet, wide, chance, ground, DUSK_HIGH, DUSK_LOW, (236, 150, 110), (120, 70, 84), (132, 190, 104), (0.5, 96.0))
    # What comes up out of the hole lights the foot of the sky.
    for step, alpha in enumerate((26, 44, 70)):
        sheet.shade(-2, ground - 60 + step * 18, wide + 4, 22, GLOW, alpha)


def _crater_far(sheet: Sheet, wide: float, chance: random.Random, ground: float) -> None:
    base = ground - 6
    things: list[Thing] = []
    x = -10.0
    while x < wide:
        across, high = chance.uniform(60, 120), chance.uniform(24, 70)
        teeth = [(x + across * share, base - high * chance.uniform(0.55, 1.0)) for share in (0.15, 0.35, 0.5, 0.7, 0.88)]
        color = mix(ASH, DUSK_LOW, chance.uniform(0.1, 0.35))

        def rim(along: float, x=x, across=across, teeth=teeth, color=color) -> None:
            sheet.poly([(x + along, base), *((px + along, py) for px, py in teeth), (x + along + across, base)], color, False)

        things.append(rim)
        x += across * chance.uniform(0.5, 0.85)
    _round(things, wide)


def _crater_middle(sheet: Sheet, wide: float, chance: random.Random, ground: float) -> None:
    base = ground - 9
    things: list[Thing] = []
    x = chance.uniform(4, 24)
    while x < wide - 20:
        kind = chance.random()
        if kind < 0.4:
            high = chance.uniform(50, 110)
            bends = [(chance.uniform(-16, 16), chance.uniform(0.3, 0.6)), (chance.uniform(-30, 30), 1.0)]

            def girder(along: float, x=x, high=high, bends=bends) -> None:
                foot = x + along
                way = [(foot, base), *((foot + lean, base - high * share) for lean, share in bends)]
                sheet.stroke(way, LINE, 6.0)
                sheet.stroke(way, darker(RUST, 0.25), 3.8)
                sheet.stroke([way[-1], (way[-1][0] + 20, way[-1][1] + 8)], darker(RUST, 0.25), 2.6)

            things.append(girder)
            x += 26
        elif kind < 0.7:
            things.append(_bare_tree(sheet, chance, x, base, chance.uniform(50, 90)))
            x += 24
        else:
            across, high = chance.uniform(40, 80), chance.uniform(18, 40)
            top = _broken_top(chance, 0.0, across, base - high, high * 0.7)

            def slag(along: float, x=x, across=across, top=top) -> None:
                left = x + along
                sheet.poly([(left, base), *((left + px, py) for px, py in top), (left + across, base)], mix(ASH, CONCRETE, 0.3))
                sheet.oval(left + across * 0.2, base - 5, across * 0.6, 7, GLOW, 200)

            things.append(slag)
            x += across
        x += chance.uniform(8, 30)
    _round(things, wide)


def _crater_ground(sheet: Sheet, wide: float, chance: random.Random, ground: float) -> None:
    _earth(sheet, wide, chance, ground, earth=(74, 64, 66), dry=(96, 110, 70), stones=(52, 48, 52))
    things: list[Thing] = []
    for _ in range(int(wide // 26)):
        x, y = chance.uniform(0, wide), chance.uniform(ground - 4, TALL - 6)
        crack = [(x + step * chance.uniform(5, 11), y + step * chance.uniform(-2, 4)) for step in range(chance.randint(3, 6))]

        def glowing(along: float, crack=crack) -> None:
            way = [(px + along, py) for px, py in crack]
            sheet.stroke(way, darker(GLOW, 0.45), 2.0)
            sheet.stroke(way, GLOW, 0.8)

        things.append(glowing)
    for _ in range(int(wide // 70)):
        x, y, across = chance.uniform(0, wide), chance.uniform(ground + ROAD_BELOW, TALL - 14), chance.uniform(26, 50)

        def pool(along: float, x=x, y=y, across=across) -> None:
            sheet.oval(x + along, y, across, across * 0.24, darker(GLOW, 0.3), 255, outline=True)
            sheet.oval(x + along + across * 0.2, y + 1.5, across * 0.5, across * 0.08, lighter(GLOW, 0.4), 220)

        things.append(pool)
    _round(things, wide)


def _crater_front(sheet: Sheet, wide: float, chance: random.Random, ground: float) -> None:
    floor = TALL + 6
    things: list[Thing] = []
    slots = max(3, int(wide // 100))
    for slot in range(slots):
        x = (slot + chance.uniform(0.15, 0.7)) * wide / slots
        if slot % 2:
            shards = [(chance.uniform(-18, 18), chance.uniform(14, 30)) for _ in range(5)]

            def glass(along: float, x=x, shards=shards) -> None:
                for lean, long in shards:
                    foot = x + along + lean
                    sheet.poly([(foot - 4, floor), (foot + lean * 0.2, TALL - long), (foot + 5, floor)], darker(GLOW, 0.2))

            things.append(glass)
        else:
            across = chance.uniform(22, 34)

            def stump(along: float, x=x, across=across) -> None:
                sheet.poly([(x + along, floor), (x + along + 3, TALL - 30), (x + along + across * 0.5, TALL - 22), (x + along + across - 2, TALL - 34), (x + along + across, floor)], CHAR)

            things.append(stump)
    _round(things, wide)


# What the game draws of each layer of each of these zones, as `PICTURES` has the ruins.
ZONE_PICTURES: dict[str, dict[str, Layer]] = {
    "forest": {
        "sky": _forest_sky, "far": _forest_far, "middle": _forest_middle, "ground": _forest_ground, "front": _forest_front,
    },
    "summit": {
        "sky": _summit_sky, "far": _summit_far, "middle": _summit_middle, "ground": _summit_ground, "front": _summit_front,
    },
    "plant": {
        "sky": _plant_sky, "far": _plant_far, "middle": _plant_middle, "ground": _plant_ground, "front": _plant_front,
    },
    "crater": {
        "sky": _crater_sky, "far": _crater_far, "middle": _crater_middle, "ground": _crater_ground, "front": _crater_front,
    },
}
