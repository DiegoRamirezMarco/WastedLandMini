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


def build() -> dict[str, pygame.Surface]:
    return {
        "sprites/objects/bed.png": paint(BED, BED_LEGEND),
        "sprites/objects/pantry.png": paint(PANTRY, PANTRY_LEGEND),
        "sprites/objects/table.png": paint(TABLE, WOOD),
        "sprites/objects/stool.png": paint(STOOL, WOOD),
        "sprites/objects/crate.png": paint(CRATE, WOOD),
        "sprites/objects/campfire.png": _strip(
            [paint(flames + CAMPFIRE_BASE, CAMPFIRE_LEGEND) for flames in CAMPFIRE_FLAMES]
        ),
    }
