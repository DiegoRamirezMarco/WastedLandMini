"""16×16 icons for items: the built-in ones, and the two example content packs."""

import pygame

from graphics.item_icons import ICON_SIZE, builtin_icon_path
from tools.art.grid import paint

CANNED_BEANS = [
    "................",
    "....oooooooo....",
    "...oddddddddo...",
    "...osssssssso...",
    "...oooooooooo...",
    "...oeeeeeeeeo...",
    "...oeeppppeeo...",
    "...oepkppkpeo...",
    "...oeppkpppeo...",
    "...oepppkppeo...",
    "...oeeppppeeo...",
    "...oeeeeeeeeo...",
    "...oooooooooo...",
    "...osssssssso...",
    "....oooooooo....",
    "................",
]
CANNED_BEANS_LEGEND = {"o": "ink", "d": "dust", "s": "stone", "e": "ember", "p": "paper", "k": "rust"}

OLD_RADIO = [
    "................",
    "..........o.....",
    ".........o......",
    "........o.......",
    ".oooooooooooooo.",
    ".otttttttttttto.",
    ".otkkkkktdddtto.",
    ".otkfkfktdidtto.",
    ".otkkkkktdddtto.",
    ".otkfkfktttttto.",
    ".otkkkkktyttyto.",
    ".otttttttttttto.",
    ".oooooooooooooo.",
    "..oo........oo..",
    "................",
    "................",
]
OLD_RADIO_LEGEND = {"o": "ink", "t": "copper", "k": "rust_dark", "f": "rust", "d": "bone", "i": "ink", "y": "lamp"}

PIZZA = [
    "................",
    "..oooooooooooo..",
    ".occcccccccccco.",
    ".oyyyyyyyyyyyyo.",
    "..oyylyyyylyyo..",
    "..oyyyyeyyyyyo..",
    "...oyyyyyylyo...",
    "...oylyyyyyyo...",
    "....oyyyeyyo....",
    "....oyyyyyyo....",
    ".....oylyyo.....",
    ".....oyyyyo.....",
    "......oyyo......",
    "......oyyo......",
    ".......oo.......",
    "................",
]
PIZZA_LEGEND = {"o": "ink", "c": "sand", "y": "lamp", "l": "lichen", "e": "ember"}

PLUSH = [
    "................",
    "..ooo......ooo..",
    ".obbbo....obbbo.",
    ".obpbooooooobpbo",
    ".obbbbbbbbbbbbo.",
    "..obbbbbbbbbbo..",
    "..obbebbbbebbo..",
    "..obbebbbbebbo..",
    "..obbbbppbbbbo..",
    "..obbbpkkpbbbo..",
    "..obbbppppbbbo..",
    "...obbbkkbbbo...",
    "....obbbbbbo....",
    ".....oooooo.....",
    "................",
    "................",
]
PLUSH_LEGEND = {"o": "ink", "b": "copper", "p": "bone", "e": "ember", "k": "ink"}


VEGETABLES = [
    "................",
    "..........ll....",
    ".........lgl.l..",
    "........lgglgl..",
    ".........ggggl..",
    "........oooog...",
    ".......oeeeeo...",
    "......oeeseeo...",
    ".....oeeeeeo....",
    "....oeeseeo.....",
    "...oeeeeeo......",
    "..oeeseeo.......",
    "..oeeeeo........",
    "..oeeoo.........",
    "...oo...........",
    "................",
]
VEGETABLES_LEGEND = {"l": "lichen", "g": "olive", "o": "ink", "e": "ember", "s": "sand"}

STEW = [
    "................",
    "......d...d.....",
    ".....d...d......",
    "......d...d.....",
    "................",
    ".oooooooooooooo.",
    ".osssssssssssso.",
    "..oeekeesekeeo..",
    "..obbbbbbbbbbo..",
    "..obbbbbbbbbbo..",
    "...obbbbbbbbo...",
    "....obbbbbbo....",
    ".....oooooo.....",
    "................",
    "................",
    "................",
]
STEW_LEGEND = {"d": "dust", "o": "ink", "s": "stone", "e": "ember", "k": "rust", "b": "bone"}


BATON = [
    "................",
    "............oo..",
    "...........otto.",
    "..........ottto.",
    ".........ottto..",
    "........ottto...",
    ".......ottto....",
    "......ottto.....",
    ".....ottto......",
    "....okkko.......",
    "...okkko........",
    "..okkko.........",
    "..okko..........",
    "...oo...........",
    "................",
    "................",
]
BATON_LEGEND = {"o": "ink", "t": "rust", "k": "shadow"}

RUSTY_KNIFE = [
    "................",
    "............oo..",
    "...........odo..",
    "..........oddo..",
    ".........oddo...",
    "........oddo....",
    ".......oddo.....",
    "......oddo......",
    ".....osdo.......",
    "....ooso........",
    "...okko.........",
    "..okko..........",
    "..oko...........",
    "...o............",
    "................",
    "................",
]
RUSTY_KNIFE_LEGEND = {"o": "ink", "d": "dust", "s": "stone", "k": "rust"}


def _checked(surface: pygame.Surface, name: str) -> pygame.Surface:
    if surface.get_size() != ICON_SIZE:
        raise ValueError(f"Icon {name} is {surface.get_size()}, expected {ICON_SIZE}")
    return surface


def build() -> dict[str, pygame.Surface]:
    """Icons that live under `assets/`."""
    return {
        builtin_icon_path("canned_beans"): _checked(paint(CANNED_BEANS, CANNED_BEANS_LEGEND), "canned_beans"),
        builtin_icon_path("old_radio"): _checked(paint(OLD_RADIO, OLD_RADIO_LEGEND), "old_radio"),
        builtin_icon_path("vegetables"): _checked(paint(VEGETABLES, VEGETABLES_LEGEND), "vegetables"),
        builtin_icon_path("stew"): _checked(paint(STEW, STEW_LEGEND), "stew"),
        builtin_icon_path("baton"): _checked(paint(BATON, BATON_LEGEND), "baton"),
        builtin_icon_path("rusty_knife"): _checked(paint(RUSTY_KNIFE, RUSTY_KNIFE_LEGEND), "rusty_knife"),
    }


def build_custom() -> dict[str, pygame.Surface]:
    """Icons for the example packs, as paths under `custom_content/`."""
    return {
        "foods/pizza_radioactiva/icon.png": _checked(paint(PIZZA, PIZZA_LEGEND), "pizza_radioactiva"),
        "items/peluche_maligno/icon.png": _checked(paint(PLUSH, PLUSH_LEGEND), "peluche_maligno"),
    }
