"""Resident bodies in parts: per view a head, a trunk and the strips of colour laid along the limbs."""

from dataclasses import dataclass

import pygame

from graphics.body_renderer import SHEET_SIZE, SPRITE_CELLS, STRIP_CELLS, STRIP_SPACING, STRIP_TOP, VIEW_WIDTH
from skeleton.plan import SKIN_VIEWS
from tools.art.grid import overlay, paint

# o outline, e eye, h/H hair, s/S skin, c/C shirt, p/P trousers, b boots. Capitals are shade.

_BLANK = "................"

# A head sits on its bone at column 7 of row 8: the eyes.
HEAD = {
    "front": [
        _BLANK,
        _BLANK,
        _BLANK,
        _BLANK,
        ".....ooooo......",
        "....ohhhhho.....",
        "...ohhhhhhho....",
        "...ohsssssho....",
        "...osessseso....",
        "...ossssssso....",
        "....osssSso.....",
        ".....ooooo......",
        _BLANK,
        _BLANK,
        _BLANK,
        _BLANK,
    ],
    "side": [
        _BLANK,
        _BLANK,
        _BLANK,
        _BLANK,
        ".....ooooo......",
        "....ohhhhho.....",
        "...ohhhhhhho....",
        "...ohhhhssso....",
        "...ohhhsseso....",
        "...oHhssssso....",
        "....oHsssso.....",
        ".....ooooo......",
        _BLANK,
        _BLANK,
        _BLANK,
        _BLANK,
    ],
    "back": [
        _BLANK,
        _BLANK,
        _BLANK,
        _BLANK,
        ".....ooooo......",
        "....ohhhhho.....",
        "...ohhhhhhho....",
        "...ohhhhhhho....",
        "...ohhhhhhho....",
        "...oHhhhhhHo....",
        "....oHHHHHo.....",
        ".....ooooo......",
        _BLANK,
        _BLANK,
        _BLANK,
        _BLANK,
    ],
}

# A trunk sits on the spine at column 7 of row 6, half-way between the shoulders and the hips.
TORSO = {
    "front": [
        _BLANK,
        _BLANK,
        ".....ooooo......",
        "....occccco.....",
        "....occccco.....",
        "....occccco.....",
        "....oCcccCo.....",
        "....oCCCCCo.....",
        "....opppppo.....",
        "....opppppo.....",
        _BLANK,
        _BLANK,
    ],
    "side": [
        _BLANK,
        _BLANK,
        ".....ooooo......",
        "....occccco.....",
        "....oCcccco.....",
        "....oCcccco.....",
        "....oCCccco.....",
        "....oCCCCCo.....",
        "....opppppo.....",
        "....oPppppo.....",
        _BLANK,
        _BLANK,
    ],
}
TORSO["back"] = TORSO["front"]

# What is laid along each limb bone, from the end nearer the body, as wide as the limb is thick.
STRIPS = {
    "front": {"upper_arm": ["c", "c", "C"], "forearm": ["c", "s", "s"], "thigh": ["pp"] * 3, "shin": ["pp", "bb", "bb"]},
    "side": {"upper_arm": ["c", "c", "C"], "forearm": ["c", "s", "s"], "thigh": ["pp"] * 3, "shin": ["pp", "bb", "bb"]},
}
STRIPS["back"] = STRIPS["front"]

# Rows drawn over the head, keyed by row index.
HAIR = {
    "short": {"front": {}, "back": {}, "side": {}},
    "long": {
        "front": {
            9: "...ohsssssho....",
            10: "...ohsssSsho....",
            11: "...ohoooooho....",
            12: "...oho...oho....",
            13: "....o.....o.....",
        },
        "back": {
            10: "...ohhhhhhho....",
            11: "...ohhHhHhho....",
            12: "...ohhHhHhho....",
            13: "....oHHHHHo.....",
            14: ".....ooooo......",
        },
        "side": {
            10: "...ohh..........",
            11: "...ohho.........",
            12: "...ohho.........",
            13: "....oo..........",
        },
    },
    "bun": {
        "front": {2: "......ooo.......", 3: ".....ohhho......", 4: ".....ohhho......"},
        "back": {2: "......ooo.......", 3: ".....ohhho......", 4: ".....ohhho......"},
        "side": {
            5: ".oo.............",
            6: "ohho............",
            7: "ohho............",
            8: ".oo.............",
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
    "paco": Look("short", "iron", "shadow", "skin_3", "skin_2", "ochre", "rust", "deep", "shadow", "rust_dark"),
    "nuria": Look("bun", "shadow", "ink", "skin_2", "skin_1", "rose", "plum", "earth", "earth_dark", "shadow"),
    "sergio": Look("short", "copper", "rust", "skin_3", "skin_2", "steel", "deep", "earth", "earth_dark", "ink"),
    # Those who may come to the gate one day.
    "olga": Look("bun", "dust", "stone", "skin_3", "skin_2", "dusk", "ink", "iron", "shadow", "rust_dark"),
    "hugo": Look("short", "ochre", "rust", "skin_4", "skin_3", "ember", "blood", "steel", "deep", "shadow"),
    "carmen": Look("long", "ink", "shadow", "skin_2", "skin_1", "moss", "moss_dark", "rust", "rust_dark", "ink"),
    "bruno": Look("short", "bone", "dust", "skin_1", "rust_dark", "earth", "earth_dark", "stone", "iron", "shadow"),
}


def _sheet(look: Look) -> pygame.Surface:
    sheet = pygame.Surface(SHEET_SIZE, pygame.SRCALPHA)
    legend = look.legend()
    for column, view in enumerate(SKIN_VIEWS):
        left = column * VIEW_WIDTH
        head = paint(overlay(HEAD[view], HAIR[look.hair_style][view]), legend)
        for cell, rows in (("head", head), ("torso", paint(TORSO[view], legend))):
            if rows.get_size() != SPRITE_CELLS[cell].size:
                raise ValueError(f"The {view} {cell} is {rows.get_size()}, expected {SPRITE_CELLS[cell].size}")
            sheet.blit(rows, SPRITE_CELLS[cell].move(left, 0))
        for index, cell in enumerate(STRIP_CELLS):
            sheet.blit(paint(STRIPS[view][cell], legend), (left + index * STRIP_SPACING, STRIP_TOP))
    return sheet


def build() -> dict[str, pygame.Surface]:
    return {f"sprites/bodies/{body_id}.png": _sheet(look) for body_id, look in LOOKS.items()}
