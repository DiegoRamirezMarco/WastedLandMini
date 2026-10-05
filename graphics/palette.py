"""Shared colour palette. Every sprite and UI colour comes from here."""

from pathlib import Path

Color = tuple[int, int, int]

PALETTE_NAME = "Wasteland Minis"
GPL_PATH = Path(__file__).resolve().parent.parent / "assets" / "palette.gpl"

PALETTE: dict[str, Color] = {
    # Neutrals
    "ink": (26, 22, 20),
    "shadow": (46, 42, 43),
    "iron": (74, 69, 69),
    "stone": (111, 106, 100),
    "dust": (163, 156, 143),
    "bone": (217, 210, 192),
    "paper": (242, 236, 220),
    # Rust and wood
    "rust_dark": (59, 36, 32),
    "rust": (107, 58, 42),
    "copper": (163, 90, 52),
    "sand": (209, 139, 79),
    # Earth
    "earth_dark": (94, 78, 64),
    "earth": (122, 102, 82),
    # Skin
    "skin_1": (92, 58, 46),
    "skin_2": (143, 90, 66),
    "skin_3": (198, 138, 99),
    "skin_4": (232, 185, 143),
    # Greens
    "moss_dark": (42, 51, 38),
    "moss": (70, 85, 58),
    "olive": (111, 128, 72),
    "lichen": (163, 176, 106),
    # Blues
    "deep": (31, 47, 58),
    "steel": (50, 80, 94),
    "teal": (79, 127, 138),
    "mist": (140, 188, 184),
    # Reds
    "blood_dark": (90, 30, 34),
    "blood": (163, 50, 47),
    "ember": (217, 90, 69),
    # Yellows
    "ochre": (176, 122, 30),
    "lamp": (227, 178, 60),
    "glow": (245, 224, 138),
    # Purples
    "dusk": (58, 42, 68),
    "plum": (110, 74, 122),
    "rose": (201, 135, 159),
}


def to_gpl() -> str:
    """Return the palette as a GIMP palette file, readable by most sprite editors."""
    lines = ["GIMP Palette", f"Name: {PALETTE_NAME}", "Columns: 8", "#"]
    lines += [f"{r:3d} {g:3d} {b:3d}\t{name}" for name, (r, g, b) in PALETTE.items()]
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    GPL_PATH.write_text(to_gpl(), encoding="utf-8", newline="\n")
    print(f"Wrote {GPL_PATH}")
