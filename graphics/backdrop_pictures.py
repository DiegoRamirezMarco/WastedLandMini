"""The game's own backdrops, drawn by code: what a trip goes through until somebody draws it.

The same hand as everything else the game draws for itself (`graphics.cartoon`), a layer at a
time and at whatever size it is asked for, so that it is as sharp on the window as on the
paper it is traced from. Every layer meets itself at its ends: whatever stands across one end
of it is drawn across the other too.

Everything is measured on a paper 310 tall, however wide: the one the built-in backdrops are
laid out on.
"""

import random
from collections.abc import Callable

import pygame

from graphics.backdrop import PLAIN_ART, BackdropPlan
from graphics.cartoon import DARK_METAL, LINE, METAL, RUBBER, RUST, STONE, Sheet
from graphics.palette import Color
from graphics.ui_art import darker, lighter, mix

Size = tuple[int, int]
# Something drawn on a layer, so far along it.
Thing = Callable[[float], None]

TALL = 310.0
# A picture this large is drawn only twice over before it is brought down to size.
DETAIL = 2
SKY_HIGH: Color = (112, 142, 158)
SKY_LOW: Color = (236, 208, 164)
SUN: Color = (252, 240, 204)
CLOUD: Color = (244, 226, 196)
HAZE: Color = (214, 194, 162)
FAR: Color = (124, 134, 144)
WALLS: tuple[Color, ...] = ((176, 154, 128), (160, 150, 138), (182, 142, 116), (150, 138, 122))
HOLE: Color = (56, 48, 48)
EARTH: Color = (158, 132, 100)
ROAD: Color = (106, 102, 100)
PAINT: Color = (220, 206, 156)
DRY: Color = (176, 156, 92)
BARK: Color = (84, 66, 56)
CONCRETE: Color = (132, 128, 122)
# How far above the line feet are on the ground begins, and how far below it the road ends.
VERGE = 14.0
ROAD_BELOW = 22.0


def _sheet(size: Size, line: float = 1.1) -> tuple[Sheet, float]:
    """Something to draw on at a size, and how wide it is in the measure everything is given in."""
    unit = size[1] / TALL
    return Sheet(size, unit, line=line, detail=DETAIL), size[0] / unit


def _round(things: list[Thing], wide: float) -> None:
    """Draw everything, and again a whole width to each side: what stands across an end of the
    layer is so across the other, and whatever is in front of something is in front of it there too."""
    for thing in things:
        for along in (-wide, 0.0, wide):
            thing(along)


def _sky(
    sheet: Sheet,
    wide: float,
    chance: random.Random,
    ground: float,
    high: Color = SKY_HIGH,
    low: Color = SKY_LOW,
    sun_color: Color = SUN,
    cloud_color: Color = CLOUD,
    haze: Color = HAZE,
    sun_at: tuple[float, float] = (0.72, 66.0),
) -> None:
    """A sky from one colour down to another, with a sun in its haze and long flat clouds."""
    horizon = ground - 8
    bands = 16
    for band in range(bands):
        share = (band / (bands - 1)) ** 1.5
        sheet.shade(-2, horizon * band / bands, wide + 4, horizon / bands + 1, mix(high, low, share))
    # Behind the ground it is all haze: nothing shows through a gap in what is drawn over it.
    sheet.shade(-2, horizon - 1, wide + 4, TALL - horizon + 3, low)
    things: list[Thing] = []
    sun_x, sun_y = wide * sun_at[0], sun_at[1]

    def sun(along: float) -> None:
        for reach, alpha in ((46, 26), (32, 40), (22, 70)):
            sheet.oval(sun_x + along - reach, sun_y - reach, reach * 2, reach * 2, sun_color, alpha)
        sheet.oval(sun_x + along - 13, sun_y - 13, 26, 26, sun_color)

    things.append(sun)
    for _ in range(7):
        x, y = chance.uniform(0, wide), chance.uniform(22, 150)
        long, thick = chance.uniform(60, 130), chance.uniform(7, 15)
        alpha = chance.randint(70, 130)

        def cloud(along: float, x=x, y=y, long=long, thick=thick, alpha=alpha) -> None:
            sheet.oval(x + along, y, long, thick, cloud_color, alpha)
            sheet.oval(x + along + long * 0.22, y - thick * 0.5, long * 0.5, thick, cloud_color, alpha)

        things.append(cloud)
    _round(things, wide)
    for step, alpha in enumerate((34, 52, 74)):
        sheet.shade(-2, horizon - 54 + step * 18, wide + 4, 20, haze, alpha)


def _broken_top(chance: random.Random, x: float, wide: float, top: float, drop: float) -> list[tuple[float, float]]:
    """The top of a wall that has come down in part, from its left end to its right: higher at one end."""
    steps = max(2, int(wide // 14))
    falls = chance.random() < 0.5
    points = []
    for step in range(steps + 1):
        share = step / steps
        fallen = drop * (share if falls else 1.0 - share) ** 1.3
        points.append((x + wide * share, top + fallen + (chance.uniform(-3, 5) if 0 < step < steps else 0.0)))
    # Stepped, as courses of block break, and not a slope.
    stepped = [points[0]]
    for before, after in zip(points, points[1:]):
        stepped.extend([(after[0], before[1]), after])
    return stepped


def _height_at(top: list[tuple[float, float]], x: float) -> float:
    """How far down the paper the top of a wall is at a place along it."""
    for (x0, y0), (x1, y1) in zip(top, top[1:]):
        if x0 <= x <= x1 and x1 > x0:
            return max(y0, y1)
    return top[-1][1]


def _ruins_far(sheet: Sheet, wide: float, chance: random.Random, ground: float) -> None:
    base = ground - 6
    things: list[Thing] = []
    x = chance.uniform(0, 12)
    while x < wide - 8:
        across, high = chance.uniform(14, 36), chance.uniform(34, 112)
        color = mix(FAR, HAZE, chance.uniform(0.1, 0.45))
        top = _broken_top(chance, 0.0, across, base - high, high * chance.uniform(0.1, 0.45))
        frame = chance.random() < 0.22
        lit = [
            (chance.uniform(2, across - 5), chance.uniform(high * 0.12, high * 0.85))
            for _ in range(int(across * high / 190))
        ]

        def tower(along: float, x=x, across=across, high=high, color=color, top=top, frame=frame, lit=lit) -> None:
            left = x + along
            if frame:
                # Only its frame is left standing: uprights and floors, and the sky between them.
                for upright in range(0, int(across) + 1, 7):
                    sheet.stroke([(left + upright, base), (left + upright, _height_at(top, upright) + 4)], color, 1.6)
                for floor in range(1, int(high // 13)):
                    sheet.stroke([(left, base - floor * 13), (left + across, base - floor * 13)], color, 1.2)
                return
            sheet.poly([(left, base), *((left + px, py) for px, py in top), (left + across, base)], color, outline=False)
            for px, up in lit:
                if base - up > _height_at(top, px) + 3:
                    sheet.shade(left + px, base - up, 3.0, 4.2, SKY_LOW, 120)

        things.append(tower)
        x += across + chance.uniform(0, 24)
    _round(things, wide)
    # Their feet are lost in the dust: over them only, so that whatever sky is behind shows between.
    standing = pygame.mask.from_surface(sheet.surface)
    for top, deep, alpha in ((base - 30, 16, 60), (base - 16, 18, 120)):
        band = pygame.Rect(0, round(top * sheet.unit), sheet.surface.get_width(), round(deep * sheet.unit))
        dust = standing.to_surface(setcolor=(*HAZE, alpha), unsetcolor=(0, 0, 0, 0))
        sheet.surface.blit(dust, band.topleft, band)


def _building(sheet: Sheet, chance: random.Random, x: float, base: float) -> tuple[Thing, float]:
    across, high = chance.uniform(58, 96), chance.uniform(74, 150)
    wall = mix(chance.choice(WALLS), HAZE, chance.uniform(0.0, 0.2))
    top = _broken_top(chance, 0.0, across, base - high, high * chance.uniform(0.25, 0.6))
    columns = max(2, int(across // 22))
    gap = across / columns
    windows = []
    for floor in range(int(high // 34) + 1):
        for column in range(columns):
            wx, wy = column * gap + gap * 0.26, base - 30 - floor * 34
            if floor == 0 and column == columns // 2:
                # The way in, with nothing in it.
                windows.append((wx, base - 31, gap * 0.48, 31.0, False))
            elif wy > _height_at(top, wx + gap * 0.24) + 7 and wy > _height_at(top, wx) + 7:
                windows.append((wx, wy, gap * 0.48, 19.0, chance.random() < 0.3))
    cracks = [
        [(start[0] + step * chance.uniform(-4, 6), start[1] + step * 9) for step in range(chance.randint(2, 4))]
        for start in ((chance.uniform(6, across - 6), base - chance.uniform(30, high * 0.6)) for _ in range(3))
    ]
    bars = [(chance.uniform(3, across - 3), chance.uniform(5, 13), chance.uniform(-3, 3)) for _ in range(4)]

    def building(along: float) -> None:
        left = x + along
        sheet.poly([(left, base), *((left + px, py) for px, py in top), (left + across, base)], wall)
        # Its far side is in shade.
        sheet.shade(left + across - 9, _height_at(top, across - 4) + 2, 8, base - _height_at(top, across - 4) - 2, darker(wall, 0.2), 150)
        for px, long, lean in bars:
            foot = _height_at(top, px)
            sheet.stroke([(left + px, foot + 1), (left + px + lean, foot - long)], RUST, 0.9)
        for wx, wy, wide_, tall_, boarded in windows:
            sheet.box(left + wx, wy, wide_, tall_, HOLE, 1.0)
            if boarded:
                for board in (0.3, 0.68):
                    sheet.stroke([(left + wx - 1, wy + tall_ * board), (left + wx + wide_ + 1, wy + tall_ * (board - 0.12))], BARK, 2.2)
        for crack in cracks:
            sheet.stroke([(left + px, min(base - 2, py)) for px, py in crack], darker(wall, 0.35), 0.7)

    return building, across


def _stub(sheet: Sheet, chance: random.Random, x: float, base: float) -> tuple[Thing, float]:
    """What is left of a wall, no higher than a head."""
    across, high = chance.uniform(22, 44), chance.uniform(16, 38)
    wall = mix(chance.choice(WALLS), HAZE, 0.1)
    top = _broken_top(chance, 0.0, across, base - high, high * 0.6)

    def stub(along: float) -> None:
        left = x + along
        sheet.poly([(left, base), *((left + px, py) for px, py in top), (left + across, base)], wall)
        sheet.oval(left - 6, base - 7, across + 12, 10, darker(wall, 0.12), 255, outline=True)

    return stub, across


def _lamp(sheet: Sheet, chance: random.Random, x: float, base: float) -> tuple[Thing, float]:
    lean, high = chance.uniform(-9, 9), chance.uniform(70, 96)

    def lamp(along: float) -> None:
        foot, head = (x + along + 6, base), (x + along + 6 + lean, base - high)
        sheet.stroke([foot, head], LINE, 4.2)
        sheet.stroke([foot, head], DARK_METAL, 2.2)
        arm = (head[0] + 15, head[1] + 3 + lean * 0.3)
        sheet.stroke([head, arm], LINE, 3.4)
        sheet.stroke([head, arm], DARK_METAL, 1.6)
        sheet.box(arm[0] - 5, arm[1], 9, 4, METAL, 1.2)

    return lamp, 22.0


def _dead_tree(sheet: Sheet, chance: random.Random, x: float, base: float) -> tuple[Thing, float]:
    high = chance.uniform(48, 78)
    boughs = [(chance.uniform(0.35, 0.9), chance.choice((-1, 1)) * chance.uniform(10, 24), chance.uniform(8, 22)) for _ in range(5)]

    def tree(along: float) -> None:
        foot = x + along + 14
        trunk = [(foot, base), (foot + 2, base - high * 0.5), (foot - 2, base - high)]
        sheet.stroke(trunk, LINE, 5.4)
        sheet.stroke(trunk, BARK, 3.2)
        for share, reach, rise in boughs:
            start = (foot + 1, base - high * share)
            sheet.stroke([start, (start[0] + reach * 0.6, start[1] - rise * 0.5), (start[0] + reach, start[1] - rise)], BARK, 1.6)

    return tree, 30.0


def _ruins_middle(sheet: Sheet, wide: float, chance: random.Random, ground: float) -> None:
    base = ground - 9
    things: list[Thing] = []
    small = (_stub, _lamp, _dead_tree)
    x = chance.uniform(4, 20)
    while x < wide - 30:
        thing, across = _building(sheet, chance, x, base)
        things.append(thing)
        x += across + chance.uniform(8, 20)
        if x < wide - 30:
            thing, across = chance.choice(small)(sheet, chance, x, base)
            things.append(thing)
            x += across + chance.uniform(6, 22)
    # Rubble at the feet of it all.
    for _ in range(int(wide // 26)):
        hx, across, high = chance.uniform(0, wide), chance.uniform(20, 46), chance.uniform(6, 14)
        color = mix(chance.choice(WALLS), CONCRETE, 0.5)

        def heap(along: float, hx=hx, across=across, high=high, color=color) -> None:
            sheet.oval(hx + along, base - high * 0.6, across, high * 1.6, color, 255, outline=True)

        things.append(heap)
    _round(things, wide)


def _earth(
    sheet: Sheet,
    wide: float,
    chance: random.Random,
    ground: float,
    road: bool = False,
    earth: Color = EARTH,
    dry: Color = DRY,
    stones: Color = STONE,
) -> None:
    """Bare ground of a colour, with stones and tufts on it, and a road along it if it has one."""
    top = ground - VERGE
    sheet.shade(-2, top, wide + 4, TALL - top + 2, earth)
    for band, share in enumerate((0.06, 0.12, 0.2)):
        # Darker towards whoever looks on.
        sheet.shade(-2, ground + ROAD_BELOW + band * 12, wide + 4, TALL, darker(earth, share))
    things: list[Thing] = []
    for _ in range(int(wide // 9)):
        x, y = chance.uniform(0, wide), chance.uniform(top + 2, TALL)
        tint = (0, 0, 0) if chance.random() < 0.5 else (255, 240, 210)
        across = chance.uniform(14, 40)

        def patch(along: float, x=x, y=y, tint=tint, across=across) -> None:
            sheet.oval(x + along, y, across, across * 0.3, tint, 16)

        things.append(patch)
    if road:
        _round(things, wide)
        things = []
        sheet.shade(-2, ground - 7, wide + 4, ROAD_BELOW + 7, ROAD)
        sheet.shade(-2, ground - 7, wide + 4, 5, lighter(ROAD, 0.12))
        for edge in (ground - 7, ground + ROAD_BELOW):
            sheet.stroke([(-2, edge), (wide + 2, edge)], LINE, 1.1)
        for _ in range(int(wide // 16)):
            x, y = chance.uniform(0, wide), chance.uniform(ground - 4, ground + ROAD_BELOW - 5)
            across = chance.uniform(16, 44)
            tint = lighter(ROAD, 0.16) if chance.random() < 0.6 else darker(ROAD, 0.2)

            def wear(along: float, x=x, y=y, across=across, tint=tint) -> None:
                sheet.oval(x + along, y, across, 5.5, tint, 110)

            things.append(wear)
        dashes = int(wide // 46)
        for dash in range(dashes):
            if chance.random() < 0.25:
                # Worn away.
                continue
            x, alpha = dash * wide / dashes + 6, chance.randint(110, 200)

            def paint(along: float, x=x, alpha=alpha) -> None:
                sheet.shade(x + along, ground + 9, 22, 3.2, PAINT, alpha, 1.0)

            things.append(paint)
        for _ in range(int(wide // 44)):
            x, y = chance.uniform(0, wide), chance.uniform(ground - 4, ground + ROAD_BELOW - 9)
            crack = [(x + step * chance.uniform(4, 9), y + step * chance.uniform(-1.5, 3.5)) for step in range(chance.randint(3, 5))]

            def cracked(along: float, crack=crack) -> None:
                sheet.stroke([(px + along, py) for px, py in crack], darker(ROAD, 0.45), 0.8)

            things.append(cracked)
    # The edge of it against what is behind: a line, and what has come to rest along it.
    sheet.stroke([(-2, top), (wide + 2, top)], LINE, 1.2)
    for _ in range(int(wide // 15)):
        x, across = chance.uniform(0, wide), chance.uniform(5, 13)
        color = mix(stones, earth, chance.uniform(0.1, 0.6))
        low = chance.random() < 0.55
        y = chance.uniform(ground + ROAD_BELOW + 4, TALL - 6) if low else top - across * 0.3

        def stone(along: float, x=x, y=y, across=across, color=color) -> None:
            sheet.oval(x + along, y, across, across * 0.62, color, 255, outline=True)

        things.append(stone)
    for _ in range(int(wide // 22)):
        x, y = chance.uniform(0, wide), chance.uniform(ground + ROAD_BELOW + 8, TALL - 2)
        blades = [(chance.uniform(-5, 5), chance.uniform(6, 12)) for _ in range(4)]

        def tuft(along: float, x=x, y=y, blades=blades) -> None:
            for lean, long in blades:
                sheet.stroke([(x + along, y), (x + along + lean, y - long)], dry, 0.9)

        things.append(tuft)
    _round(things, wide)


def _road(sheet: Sheet, wide: float, chance: random.Random, ground: float) -> None:
    _earth(sheet, wide, chance, ground, road=True)


def _ruins_front(sheet: Sheet, wide: float, chance: random.Random, ground: float) -> None:
    floor = TALL + 8
    low = ground + ROAD_BELOW
    things: list[Thing] = []
    slots = max(3, int(wide // 100))
    kinds = ["block", "bush", "tyre", "sign"]
    chance.shuffle(kinds)
    for slot in range(slots):
        x = (slot + chance.uniform(0.15, 0.7)) * wide / slots
        kind = kinds[slot % len(kinds)]
        if kind == "block":
            across, high = chance.uniform(34, 54), chance.uniform(22, 30)
            top = _broken_top(chance, 0.0, across, floor - high - (floor - TALL), high * 0.4)
            bars = [(chance.uniform(4, across - 4), chance.uniform(8, 16), chance.uniform(-5, 5)) for _ in range(3)]

            def block(along: float, x=x, across=across, top=top, bars=bars) -> None:
                left = x + along
                for px, long, lean in bars:
                    foot = _height_at(top, px)
                    sheet.stroke([(left + px, foot + 2), (left + px + lean, foot - long)], darker(RUST, 0.15), 1.3)
                sheet.poly([(left, floor), *((left + px, py) for px, py in top), (left + across, floor)], darker(CONCRETE, 0.22))
                sheet.shade(left + 3, top[0][1] + 5, across - 6, 4, darker(CONCRETE, 0.08), 170, 1.5)

            things.append(block)
        elif kind == "bush":
            twigs = [(chance.uniform(-20, 20), chance.uniform(18, 34)) for _ in range(9)]

            def bush(along: float, x=x, twigs=twigs) -> None:
                for lean, long in twigs:
                    start, end = (x + along, floor), (x + along + lean, floor - long - (floor - TALL))
                    sheet.stroke([start, ((start[0] + end[0]) / 2 + lean * 0.2, (start[1] + end[1]) / 2), end], darker(DRY, 0.42), 1.5)

            things.append(bush)
        elif kind == "tyre":

            def tyre(along: float, x=x) -> None:
                sheet.oval(x + along, TALL - 26, 46, 40, RUBBER, 255, outline=True)
                sheet.oval(x + along + 12, TALL - 17, 22, 20, darker(EARTH, 0.3), 255, outline=True)

            things.append(tyre)
        else:
            lean = chance.uniform(-12, 12)
            # No higher than the shins of whoever it passes in front of.
            head = low - chance.uniform(14, 24)

            def sign(along: float, x=x, lean=lean, head=head) -> None:
                foot, top = (x + along, floor), (x + along + lean, head)
                sheet.stroke([foot, top], LINE, 5.0)
                sheet.stroke([foot, top], darker(METAL, 0.3), 2.8)
                plate = [(top[0] - 15, top[1] - 4), (top[0] + 14, top[1] - 9 + lean * 0.2), (top[0] + 16, top[1] + 9), (top[0] - 13, top[1] + 13)]
                sheet.poly(plate, darker(RUST, 0.1))
                sheet.stroke([(plate[0][0] + 5, plate[0][1] + 6), (plate[1][0] - 5, plate[1][1] + 7)], darker(RUST, 0.45), 1.6)

            things.append(sign)
    _round(things, wide)


def _hills(sheet: Sheet, wide: float, chance: random.Random, ground: float) -> None:
    base = ground - 6
    things: list[Thing] = []
    for _ in range(max(3, int(wide // 80))):
        x, across, high = chance.uniform(0, wide), chance.uniform(110, 200), chance.uniform(24, 56)
        color = mix(FAR, HAZE, chance.uniform(0.3, 0.6))

        def hill(along: float, x=x, across=across, high=high, color=color) -> None:
            sheet.oval(x + along, base - high, across, high * 2, color)

        things.append(hill)
    _round(things, wide)


Layer = Callable[[Sheet, float, random.Random, float], None]

# What the game draws of each layer, by the art a zone has and the layer's ID. A layer it has
# nothing for is left clear.
PICTURES: dict[str, dict[str, Layer]] = {
    "ruins": {"sky": _sky, "far": _ruins_far, "middle": _ruins_middle, "ground": _road, "front": _ruins_front},
    PLAIN_ART: {"sky": _sky, "far": _hills, "ground": _earth},
}


def pictures() -> dict[str, dict[str, Layer]]:
    """Every kind of art the game has, with the zones past the ruins (`graphics.backdrop_zones`)."""
    if len(PICTURES) <= 2:
        from graphics.backdrop_zones import ZONE_PICTURES

        PICTURES.update(ZONE_PICTURES)
    return PICTURES


def painted(art: str, layer_id: str, size: Size, plan: BackdropPlan) -> pygame.Surface:
    """The game's own picture of a layer, of one kind of art, at a size."""
    known = pictures()
    art = art if art in known else PLAIN_ART
    draw = known[art].get(layer_id)
    if draw is None:
        return pygame.Surface(size, pygame.SRCALPHA)
    sheet, wide = _sheet(size)
    # Not the simulation's randomness: the same ruins every time, and nothing rides on them.
    draw(sheet, wide, random.Random(f"{art}:{layer_id}"), plan.ground * TALL)
    return sheet.finished()
