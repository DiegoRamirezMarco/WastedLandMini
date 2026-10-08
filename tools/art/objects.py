"""Settlement objects. One PNG per object kind, sized in whole tiles."""

import pygame

from tools.art.grid import paint

WOOD = {"o": "ink", "T": "sand", "t": "copper", "f": "rust", "k": "rust_dark"}

BED = [
    "................",
    ".oooooooooooooo.",
    ".offffffffffffo.",
    ".okkkkkkkkkkkko.",
    ".oooooooooooooo.",
    ".owwwwwwwwwwwwo.",
    ".owwppppppppwwo.",
    ".owppppppppppwo.",
    ".owppppppppppwo.",
    ".owwddddddddwwo.",
    ".owwwwwwwwwwwwo.",
    ".obbbbbbbbbbbbo.",
    ".oBBBBBBBBBBBBo.",
    ".oBBBBBBBBBBBBo.",
    ".oBBBBBBBBBBBBo.",
    ".oBBBBBBBBDDBBo.",
    ".oBBBBBBBDDBBBo.",
    ".oBBBBBBBBBBBBo.",
    ".oBBBBBBBBBBBBo.",
    ".oBBDDBBBBBBBBo.",
    ".oBBBDDBBBBBBBo.",
    ".oBBBBBBBBBBBBo.",
    ".oBBBBBBBBBBBBo.",
    ".oBBBBBBBBBBBBo.",
    ".oBBBBBBBBBBBBo.",
    ".oBBBBBBBBBBBBo.",
    ".oBBBBBBBBBBBBo.",
    ".oDDDDDDDDDDDDo.",
    ".oooooooooooooo.",
    ".offffffffffffo.",
    ".okkkkkkkkkkkko.",
    ".oooooooooooooo.",
]
BED_LEGEND = {
    **WOOD, "w": "bone", "p": "paper", "d": "dust", "b": "mist", "B": "teal", "D": "steel",
}

PANTRY = [
    ".oooooooooooooo.",
    ".oTTTTTTTTTTTTo.",
    ".otttttttttttto.",
    ".otttttttttttto.",
    ".offffffffffffo.",
    ".ofkkkkkkkkkkfo.",
    ".ofk55k55k55kfo.",
    ".ofk11k22k33kfo.",
    ".ofk11k22k33kfo.",
    ".ofk11k22k33kfo.",
    ".offffffffffffo.",
    ".ofkkkkkkkkkkfo.",
    ".ofk55k55kkkkfo.",
    ".ofk44k33k55kfo.",
    ".ofk44k33k22kfo.",
    ".ofk44k33k22kfo.",
    ".offffffffffffo.",
    ".ofkkkkkkkkkkfo.",
    ".ofkkkkkk55kkfo.",
    ".ofk2222k11kkfo.",
    ".ofk2222k11kkfo.",
    ".ofk2222k11kkfo.",
    ".offffffffffffo.",
    ".otttttkkttttto.",
    ".otttttkkttttto.",
    ".ottt3tkkt3ttto.",
    ".otttttkkttttto.",
    ".otttttkkttttto.",
    ".offffffffffffo.",
    ".okkkkkkkkkkkko.",
    ".oooooooooooooo.",
    "................",
]
PANTRY_LEGEND = {
    **WOOD, "1": "ember", "2": "lichen", "3": "lamp", "4": "mist", "5": "bone",
}

TABLE = [
    "................................",
    ".oooooooooooooooooooooooooooooo.",
    ".oTTTTTTTTTTTTTTTTTTTTTTTTTTTTo.",
    ".otttttttttttttttttttttttttttto.",
    ".otttttttttttttttttttttttttttto.",
    ".offffffffftttttttttfffffffffto.",
    ".otttttttttttttttttttttttttttto.",
    ".otttttttttttttttttttttttttttto.",
    ".otttttfffffffffttttttttfffffto.",
    ".otttttttttttttttttttttttttttto.",
    ".offffffffffffffffffffffffffffo.",
    ".okkkkkkkkkkkkkkkkkkkkkkkkkkkko.",
    ".oooooooooooooooooooooooooooooo.",
    "..oko......................oko..",
    "..oko......................oko..",
    "..ooo......................ooo..",
]

STOOL = [
    "................",
    "................",
    "................",
    "....oooooooo....",
    "...oTTTTTTTTo...",
    "...otttttttto...",
    "...otttttttto...",
    "...offffffffo...",
    "....oooooooo....",
    "....ok....ko....",
    "....ok....ko....",
    "....oo....oo....",
    "................",
    "................",
    "................",
    "................",
]

CRATE = [
    "................",
    ".oooooooooooooo.",
    ".oTTTTTTTTTTTTo.",
    ".otfttttttttfto.",
    ".ottfttttttftto.",
    ".otttfttttfttto.",
    ".ottttfttftttto.",
    ".otttttffttttto.",
    ".otttttffttttto.",
    ".ottttfttftttto.",
    ".otttfttttfttto.",
    ".ottfttttttftto.",
    ".otfttttttttfto.",
    ".offffffffffffo.",
    ".oooooooooooooo.",
    "................",
]

# The flames of each animation frame; the logs and stones below are the same in all of them.
CAMPFIRE_FLAMES = [
    [
        "................",
        ".......y........",
        "......yyy.......",
        "......yGy..e....",
        ".....eyGGy......",
        ".....eyGGye.....",
        "....eeyyGyee....",
        "....eeeyyeee....",
    ],
    [
        "................",
        "........y.......",
        ".......yy.......",
        "...e..yGyy......",
        ".....eyGGy......",
        "....eeyGGye.....",
        "....eeyGyyee....",
        "....eeeyyeee....",
    ],
    [
        "................",
        "................",
        ".......y....e...",
        "......yyy.......",
        "......yGye......",
        ".....eyGGye.....",
        "....eeyGGyee....",
        "....eeeyyeee....",
    ],
]
CAMPFIRE_BASE = [
    "...okeeeeeeko...",
    "..osskkeekksso..",
    "..osdkkkkkkdso..",
    "..osskkkkkksso..",
    "...ossddddsso...",
    "....oooooooo....",
    "................",
    "................",
]
CAMPFIRE_LEGEND = {
    "o": "ink", "y": "lamp", "G": "glow", "e": "ember", "k": "rust_dark", "s": "stone", "d": "dust",
}


def _strip(frames: list[pygame.Surface]) -> pygame.Surface:
    """Animation frames side by side, the layout the game expects for an animated object."""
    width, height = frames[0].get_size()
    strip = pygame.Surface((width * len(frames), height), pygame.SRCALPHA)
    for index, frame in enumerate(frames):
        strip.blit(frame, (index * width, 0))
    return strip


JUSTICE = {**WOOD, "s": "stone", "d": "dust", "b": "bone"}

STOCKS = [
    "................",
    "................",
    "................",
    ".oooooooooooooo.",
    ".oTTTTTTTTTTTTo.",
    ".ottoottttootto.",
    ".ottoottttootto.",
    ".offffffffffffo.",
    ".oooooooooooooo.",
    "...ok......ko...",
    "...ok......ko...",
    "...ok......ko...",
    "...ok......ko...",
    "..oooo....oooo..",
    "................",
    "................",
]


def _tall(marks: dict[tuple[int, int], str]) -> list[str]:
    """A grid a tile wide and two high from the pixels that are painted on it."""
    return ["".join(marks.get((x, y), ".") for x in range(16)) for y in range(32)]


def _gallows() -> list[str]:
    marks: dict[tuple[int, int], str] = {}
    for y in range(2, 27):
        marks.update({(3, y): "o", (4, y): "t", (5, y): "o"})
    for x in range(3, 13):
        marks.update({(x, 2): "o", (x, 3): "T", (x, 4): "o"})
    for step in range(4):
        marks[(6 + step, 9 - step)] = "k"
    for y in range(5, 11):
        marks[(11, y)] = "d"
    for spot in ((10, 11), (12, 11), (10, 12), (12, 12), (11, 13)):
        marks[spot] = "d"
    for x in range(1, 15):
        marks.update({(x, 26): "o", (x, 27): "T", (x, 28): "f", (x, 29): "o"})
    return _tall(marks)


def _guillotine() -> list[str]:
    marks: dict[tuple[int, int], str] = {}
    for y in range(3, 27):
        for x in (3, 11):
            marks.update({(x, y): "o", (x + 1, y): "t", (x + 2, y): "o"})
    for x in range(3, 14):
        marks.update({(x, 2): "o", (x, 3): "T", (x, 4): "o"})
    for x in range(6, 11):
        for y in range(6, 8 + (x - 6) // 2):
            marks[(x, y)] = "s"
        marks[(x, 5)] = "o"
    for x in range(6, 11):
        marks.update({(x, 21): "o", (x, 22): "t", (x, 23): "o"})
    marks.update({(8, 22): "o"})
    for x in range(1, 15):
        marks.update({(x, 26): "o", (x, 27): "T", (x, 28): "f", (x, 29): "o"})
    return _tall(marks)


def build() -> dict[str, pygame.Surface]:
    return {
        "sprites/objects/stocks.png": paint(STOCKS, JUSTICE),
        "sprites/objects/gallows.png": paint(_gallows(), JUSTICE),
        "sprites/objects/guillotine.png": paint(_guillotine(), JUSTICE),
        "sprites/objects/bed.png": paint(BED, BED_LEGEND),
        "sprites/objects/pantry.png": paint(PANTRY, PANTRY_LEGEND),
        "sprites/objects/table.png": paint(TABLE, WOOD),
        "sprites/objects/stool.png": paint(STOOL, WOOD),
        "sprites/objects/crate.png": paint(CRATE, WOOD),
        "sprites/objects/campfire.png": _strip(
            [paint(flames + CAMPFIRE_BASE, CAMPFIRE_LEGEND) for flames in CAMPFIRE_FLAMES]
        ),
    }
