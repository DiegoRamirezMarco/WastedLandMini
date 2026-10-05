"""Resident body sheets: 3 columns (idle, step A, step B) by 4 rows (down, left, right, up)."""

from dataclasses import dataclass

import pygame

from graphics.character_renderer import FACINGS, FRAME_SIZE, FRAMES_PER_FACING, SHEET_SIZE
from tools.art.grid import mirror, overlay, paint

# o outline, e eye, h/H hair, s/S skin, c/C shirt, p/P trousers, b boots. Capitals are shade.

HEAD = {
    "down": [
        "................",
        "....oooooooo....",
        "...ohhhhhhhho...",
        "..ohhhhhhhhhho..",
        "..ohhhhhhhhhho..",
        "..ohhhsssshhho..",
        "..ohssssssssho..",
        "..ohsessssesho..",
        "..ohsessssesho..",
        "..osssssssssso..",
        "...osssSSssso...",
        "....osssssso....",
        ".....oooooo.....",
    ],
    "up": [
        "................",
        "....oooooooo....",
        "...ohhhhhhhho...",
        "..ohhhhhhhhhho..",
        "..ohhhhhhhhhho..",
        "..ohhhhhhhhhho..",
        "..ohhhhhhhhhho..",
        "..ohhhhhhhhhho..",
        "..ohhhhhhhhhho..",
        "..oHhhhhhhhhHo..",
        "...oHHHHHHHHo...",
        "....osssssso....",
        ".....oooooo.....",
    ],
    "right": [
        "................",
        "....oooooooo....",
        "...ohhhhhhhho...",
        "..ohhhhhhhhhho..",
        "..ohhhhhhhhhho..",
        "..ohhhhhhhssso..",
        "..ohhhhhhsssso..",
        "..ohhhhhssseso..",
        "..ohhhhsssseso..",
        "..oHhhssssssso..",
        "...oHsssssSso...",
        "....osssssso....",
        ".....oooooo.....",
    ],
}

TORSO_FRONT = [
    "...occcccccco...",
    "..osccccccccso..",
    "..osccccccccso..",
    "..osCccccccCso..",
    "...oCCCCCCCCo...",
    "...oppppppppo...",
    "...oppppppppo...",
]
TORSO = {
    "down": TORSO_FRONT,
    "up": TORSO_FRONT,
    "right": [
        "....occcccco....",
        "....occCCcco....",
        "....occCCcco....",
        "....oCcsscCo....",
        "....oCCCCCCo....",
        "....oppppppo....",
        "....oppppppo....",
    ],
}

LEGS_FRONT_IDLE = [
    "...opppoopppo...",
    "...opPpoopPpo...",
    "...obbboobbbo...",
    "....ooo..ooo....",
]
LEGS_FRONT_STEP = [
    "...opppoopppo...",
    "...opPpoobbbo...",
    "...obbbo.ooo....",
    "....ooo.........",
]
LEGS_FRONT = [LEGS_FRONT_IDLE, LEGS_FRONT_STEP, mirror(LEGS_FRONT_STEP)]
LEGS = {
    "down": LEGS_FRONT,
    "up": LEGS_FRONT,
    "right": [
        [
            ".....oppppo.....",
            ".....opPppo.....",
            ".....obbbbbo....",
            "......ooooo.....",
        ],
        [
            "....oppoppo.....",
            "...oppo.oppo....",
            "...obbo.obbbo...",
            "....oo...ooo....",
        ],
        [
            ".....oppppo.....",
            "......oPpo......",
            "......obbbo.....",
            ".......ooo......",
        ],
    ],
}

# Rows drawn over the assembled frame, keyed by row index.
HAIR = {
    "short": {"down": {}, "up": {}, "right": {}},
    "long": {
        "down": {
            9: "..oh........ho..",
            10: "..oh........ho..",
            11: "..ohh......hho..",
            12: "..ohh......hho..",
            13: "..oHh......hHo..",
        },
        "up": {
            9: "..ohhhhhhhhhho..",
            10: "..ohhhhhhhhhho..",
            11: "..ohhHhhhhHhho..",
            12: "..ohhHhhhhHhho..",
            13: "..ohhHhhhhHhho..",
            14: "...hhHhhhhHhh...",
            15: "....HHHHHHHH....",
        },
        "right": {
            10: "..ohh...........",
            11: "..ohh...........",
            12: "..ohhh..........",
            13: "..oHh...........",
            14: "...oo...........",
        },
    },
    "bun": {
        "down": {0: "......oooo......", 1: ".....ohhhho....."},
        "up": {0: "......oooo......", 1: ".....ohhhho....."},
        "right": {
            3: ".o..............",
            4: "ohh.............",
            5: "ohh.............",
            6: ".o..............",
        },
    },
}


@dataclass(frozen=True)
class Look:
    hair_style: str
    hair: str
    hair_shade: str
    skin: str
    skin_shade: str
    shirt: str
    shirt_shade: str
    trousers: str
    trousers_shade: str
    boots: str

    def legend(self) -> dict[str, str]:
        return {
            "o": "ink", "e": "ink",
            "h": self.hair, "H": self.hair_shade,
            "s": self.skin, "S": self.skin_shade,
            "c": self.shirt, "C": self.shirt_shade,
            "p": self.trousers, "P": self.trousers_shade,
            "b": self.boots,
        }


LOOKS = {
    "marta": Look("long", "rust", "rust_dark", "skin_4", "skin_3", "teal", "steel", "iron", "shadow", "shadow"),
    "raul": Look("short", "shadow", "ink", "skin_3", "skin_2", "blood", "blood_dark", "stone", "iron", "rust_dark"),
    "lucia": Look("bun", "lamp", "ochre", "skin_4", "skin_3", "olive", "moss", "rust", "rust_dark", "shadow"),
    "tomas": Look("short", "dust", "stone", "skin_2", "skin_1", "moss", "moss_dark", "iron", "shadow", "rust_dark"),
    "ines": Look("bun", "rust_dark", "ink", "skin_3", "skin_2", "plum", "dusk", "stone", "iron", "shadow"),
    "vera": Look("long", "stone", "iron", "skin_4", "skin_3", "bone", "dust", "steel", "deep", "shadow"),
}


def _frame(look: Look, facing: str, step: int) -> pygame.Surface:
    side = "right" if facing == "left" else facing
    rows = overlay(HEAD[side] + TORSO[side] + LEGS[side][step], HAIR[look.hair_style][side])
    surface = paint(rows, look.legend())
    if surface.get_size() != FRAME_SIZE:
        raise ValueError(f"Frame is {surface.get_size()}, expected {FRAME_SIZE}")
    return pygame.transform.flip(surface, True, False) if facing == "left" else surface


def _sheet(look: Look) -> pygame.Surface:
    sheet = pygame.Surface(SHEET_SIZE, pygame.SRCALPHA)
    for row, facing in enumerate(FACINGS):
        for step in range(FRAMES_PER_FACING):
            sheet.blit(_frame(look, facing, step), (step * FRAME_SIZE[0], row * FRAME_SIZE[1]))
    return sheet


def build() -> dict[str, pygame.Surface]:
    return {f"sprites/residents/{body_id}.png": _sheet(look) for body_id, look in LOOKS.items()}
