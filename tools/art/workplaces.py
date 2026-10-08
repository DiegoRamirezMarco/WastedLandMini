"""Objects of the settlement's premises: the cantina, the garden, the workshop, the shop and the gate."""

import random

import pygame

from graphics.palette import PALETTE
from tools.art.grid import dots, fill, paint
from tools.art.objects import BED


def _blank(width: int, height: int) -> pygame.Surface:
    return pygame.Surface((width, height), pygame.SRCALPHA)


def _box(surface: pygame.Surface, rect: tuple[int, int, int, int], color: str) -> None:
    """A filled rectangle with a one-pixel ink outline."""
    x, y, width, height = rect
    fill(surface, "ink", (x - 1, y - 1, width + 2, height + 2))
    fill(surface, color, rect)


def _cooking_pot() -> pygame.Surface:
    surface = _blank(16, 32)
    # Stove with a fire in its mouth.
    _box(surface, (2, 17, 12, 14), "iron")
    fill(surface, "stone", (1, 15, 14, 2))
    fill(surface, "shadow", (4, 21, 8, 7))
    fill(surface, "ember", (5, 23, 6, 4))
    fill(surface, "lamp", (6, 24, 4, 2))
    # Pot of stew on top.
    _box(surface, (4, 8, 8, 7), "stone")
    fill(surface, "dust", (3, 7, 10, 1))
    fill(surface, "sand", (5, 8, 6, 2))
    dots(surface, "ember", [(6, 8), (9, 9)])
    dots(surface, "ink", [(2, 10), (13, 10)])
    dots(surface, "dust", [(6, 4), (7, 2), (9, 3), (10, 5), (8, 0)])
    return surface


def _bar() -> pygame.Surface:
    surface = _blank(48, 16)
    _box(surface, (1, 5, 46, 10), "rust")
    fill(surface, "sand", (1, 5, 46, 2))
    fill(surface, "copper", (1, 7, 46, 1))
    fill(surface, "rust_dark", (1, 14, 46, 1))
    for x in range(8, 46, 8):
        fill(surface, "rust_dark", (x, 8, 1, 6))
    for x, color in ((6, "lichen"), (12, "mist"), (31, "ember"), (40, "lamp")):
        fill(surface, "ink", (x - 1, 0, 4, 5))
        fill(surface, color, (x, 1, 2, 4))
        dots(surface, "paper", [(x, 2)])
    fill(surface, "ink", (19, 1, 5, 4))
    fill(surface, "bone", (20, 2, 3, 3))
    return surface


def _crop_bed() -> pygame.Surface:
    surface = _blank(16, 16)
    _box(surface, (2, 8, 12, 6), "rust_dark")
    dots(surface, "earth_dark", [(3, 9), (6, 11), (9, 9), (12, 12), (5, 13), (10, 12)])
    for x in (4, 8, 12):
        fill(surface, "moss", (x, 5, 1, 4))
        fill(surface, "olive", (x - 1, 3, 3, 3))
        dots(surface, "lichen", [(x, 2), (x - 1, 3)])
    dots(surface, "ember", [(5, 6), (11, 5)])
    return surface


def _guard_post() -> pygame.Surface:
    surface = _blank(16, 32)
    # A sentry box: plank walls, an opening to look out of, a tin roof and a flag.
    _box(surface, (2, 7, 12, 24), "copper")
    for x in (5, 9):
        fill(surface, "rust", (x, 17, 1, 14))
    fill(surface, "shadow", (4, 9, 8, 8))
    fill(surface, "ink", (3, 17, 10, 1))
    _box(surface, (1, 4, 14, 3), "stone")
    fill(surface, "dust", (1, 4, 14, 1))
    fill(surface, "ink", (13, 0, 1, 4))
    fill(surface, "blood", (9, 0, 4, 2))
    return surface


def _workbench() -> pygame.Surface:
    surface = _blank(32, 16)
    for x in (3, 27):
        _box(surface, (x, 8, 2, 7), "iron")
    fill(surface, "shadow", (5, 11, 22, 2))
    _box(surface, (1, 4, 30, 4), "stone")
    fill(surface, "dust", (1, 4, 30, 1))
    fill(surface, "rust", (8, 2, 5, 2))
    fill(surface, "rust_dark", (10, 0, 1, 2))
    fill(surface, "dust", (17, 2, 6, 1))
    fill(surface, "iron", (25, 1, 4, 3))
    return surface


def _lab_bench() -> pygame.Surface:
    surface = _blank(32, 16)
    # A bench of planks on drums, with a flask over a burner, jars and a tray of what is made there.
    for x in (3, 26):
        _box(surface, (x, 9, 3, 6), "rust_dark")
    fill(surface, "shadow", (6, 12, 20, 2))
    _box(surface, (1, 5, 30, 4), "copper")
    fill(surface, "sand", (1, 5, 30, 1))
    fill(surface, "ink", (5, 0, 5, 5))
    fill(surface, "teal", (6, 2, 3, 3))
    fill(surface, "mist", (7, 1, 1, 1))
    dots(surface, "ember", [(6, 5), (8, 5)])
    fill(surface, "ink", (13, 1, 4, 4))
    fill(surface, "moss", (14, 2, 2, 2))
    fill(surface, "ink", (18, 2, 4, 3))
    fill(surface, "ochre", (19, 3, 2, 1))
    fill(surface, "ink", (24, 3, 6, 2))
    fill(surface, "paper", (25, 3, 4, 1))
    return surface


def _shop_counter() -> pygame.Surface:
    surface = _blank(32, 16)
    # A plank counter with a couple of tins and a pair of scales on it.
    _box(surface, (1, 6, 30, 9), "copper")
    fill(surface, "sand", (1, 6, 30, 2))
    fill(surface, "rust_dark", (1, 14, 30, 1))
    for x in (8, 16, 24):
        fill(surface, "rust", (x, 8, 1, 6))
    for x, color in ((4, "ember"), (10, "lichen")):
        fill(surface, "ink", (x - 1, 1, 5, 5))
        fill(surface, color, (x, 2, 3, 4))
        dots(surface, "paper", [(x + 1, 3)])
    fill(surface, "ink", (19, 1, 9, 1))
    fill(surface, "dust", (23, 2, 1, 4))
    for x in (19, 25):
        fill(surface, "ink", (x - 1, 3, 5, 2))
        fill(surface, "stone", (x, 3, 3, 1))
    return surface


def _shelf() -> pygame.Surface:
    surface = _blank(32, 32)
    # Bare shelving of salvaged planks: two boards for goods, and a closed base. What stands on the
    # boards is drawn by the game, from what the shop has in stock.
    _box(surface, (1, 1, 30, 30), "rust_dark")
    for x in (1, 29):
        fill(surface, "rust", (x, 1, 2, 30))
    fill(surface, "copper", (1, 1, 30, 1))
    for y in (10, 21):
        fill(surface, "sand", (3, y, 26, 1))
        fill(surface, "copper", (3, y + 1, 26, 1))
    fill(surface, "rust", (3, 23, 26, 7))
    for x in (11, 20):
        fill(surface, "rust_dark", (x, 23, 1, 7))
    dots(surface, "ink", [(7, 26), (16, 26), (25, 26)])
    return surface


def _handcart() -> pygame.Surface:
    surface = _blank(16, 16)
    # A cart knocked together from a crate and two wheels, with its handles sticking out.
    fill(surface, "ink", (0, 6, 4, 1))
    fill(surface, "ink", (0, 9, 4, 1))
    _box(surface, (4, 4, 10, 7), "copper")
    fill(surface, "sand", (4, 4, 10, 1))
    fill(surface, "rust", (4, 7, 10, 1))
    fill(surface, "rust_dark", (4, 10, 10, 1))
    for x in (5, 11):
        fill(surface, "ink", (x - 1, 10, 4, 5))
        fill(surface, "iron", (x, 11, 2, 3))
        dots(surface, "dust", [(x, 12)])
    return surface


def _caravan_cart() -> pygame.Surface:
    surface = _blank(32, 32)
    # A covered cart, loaded: the shaft it is pulled by, a patched awning over the goods, and two wheels.
    fill(surface, "ink", (0, 21, 5, 1))
    fill(surface, "rust", (0, 20, 4, 1))
    # The awning, rounded off at the top, with its hoops showing through.
    fill(surface, "ink", (7, 4, 20, 1))
    fill(surface, "ink", (5, 5, 24, 1))
    fill(surface, "ink", (4, 6, 26, 12))
    fill(surface, "bone", (7, 5, 20, 1))
    fill(surface, "bone", (5, 6, 24, 11))
    fill(surface, "paper", (7, 6, 20, 2))
    fill(surface, "dust", (5, 14, 24, 3))
    for x in (11, 17, 23):
        fill(surface, "dust", (x, 6, 1, 11))
    fill(surface, "sand", (18, 9, 4, 4))
    dots(surface, "rust", [(18, 9), (21, 12), (19, 11)])
    # What it carries, seen at the open back: a crate, a sack and a lamp hung from the hoop.
    fill(surface, "shadow", (24, 8, 5, 9))
    fill(surface, "copper", (25, 12, 4, 5))
    fill(surface, "sand", (25, 12, 4, 1))
    dots(surface, "lamp", [(26, 9), (26, 10)])
    dots(surface, "glow", [(27, 9)])
    # The bed of the cart.
    _box(surface, (4, 18, 25, 6), "copper")
    fill(surface, "sand", (4, 18, 25, 1))
    fill(surface, "rust", (4, 21, 25, 1))
    fill(surface, "rust_dark", (4, 23, 25, 1))
    for x in (10, 16, 22):
        fill(surface, "rust_dark", (x, 19, 1, 4))
    # A bucket and a bundle slung under it.
    fill(surface, "ink", (14, 24, 5, 4))
    fill(surface, "stone", (15, 25, 3, 2))
    for x in (5, 21):
        fill(surface, "ink", (x + 1, 22, 6, 1))
        fill(surface, "ink", (x, 23, 8, 8))
        fill(surface, "ink", (x + 1, 31, 6, 1))
        fill(surface, "iron", (x + 1, 24, 6, 6))
        fill(surface, "shadow", (x + 2, 25, 4, 4))
        fill(surface, "dust", (x + 3, 26, 2, 2))
        dots(surface, "stone", [(x + 1, 24), (x + 6, 24), (x + 1, 29), (x + 6, 29)])
    return surface


def _radio_set() -> pygame.Surface:
    surface = _blank(16, 32)
    # A big old receiver on a crate, with a wire for an aerial run up the wall.
    fill(surface, "ink", (11, 0, 1, 14))
    dots(surface, "dust", [(11, 0), (10, 1), (12, 1)])
    _box(surface, (2, 20, 12, 11), "rust")
    fill(surface, "copper", (2, 20, 12, 1))
    fill(surface, "rust_dark", (2, 25, 12, 1))
    _box(surface, (3, 11, 10, 9), "copper")
    fill(surface, "sand", (3, 11, 10, 1))
    fill(surface, "shadow", (4, 13, 5, 5))
    dots(surface, "rust_dark", [(5, 14), (7, 14), (5, 16), (7, 16)])
    fill(surface, "bone", (10, 13, 2, 2))
    dots(surface, "lamp", [(10, 17)])
    dots(surface, "ember", [(11, 17)])
    return surface


def _lamp() -> pygame.Surface:
    surface = _blank(16, 32)
    # A lantern hung from a post of scrap pipe.
    _box(surface, (7, 9, 2, 21), "iron")
    fill(surface, "stone", (7, 9, 1, 21))
    _box(surface, (5, 29, 6, 2), "iron")
    _box(surface, (4, 2, 8, 7), "shadow")
    fill(surface, "lamp", (5, 3, 6, 5))
    fill(surface, "glow", (6, 4, 4, 3))
    fill(surface, "ink", (7, 3, 1, 5))
    fill(surface, "iron", (3, 1, 10, 1))
    dots(surface, "ink", [(7, 0), (8, 0)])
    return surface


def _wreck() -> pygame.Surface:
    surface = _blank(48, 32)
    # A car stripped to the shell: no wheels, no glass, and more rust than paint.
    rng = random.Random(7)
    _box(surface, (2, 14, 44, 13), "rust")
    _box(surface, (10, 5, 24, 10), "rust")
    fill(surface, "copper", (2, 14, 44, 2))
    fill(surface, "copper", (10, 5, 24, 1))
    fill(surface, "rust_dark", (2, 25, 44, 2))
    # Empty windows, and the pillar between them.
    fill(surface, "ink", (12, 7, 20, 7))
    fill(surface, "shadow", (13, 8, 18, 5))
    fill(surface, "rust", (21, 7, 2, 7))
    # Wheel arches with nothing in them, sitting on bricks.
    for x in (6, 34):
        fill(surface, "ink", (x, 22, 8, 6))
        fill(surface, "shadow", (x + 1, 23, 6, 4))
        _box(surface, (x + 2, 27, 4, 3), "earth")
    # What paint is left, and holes eaten through the panels.
    for _ in range(9):
        x, y = rng.randrange(4, 42), rng.randrange(16, 23)
        fill(surface, "steel", (x, y, rng.randint(2, 4), 1))
    for _ in range(6):
        dots(surface, "rust_dark", [(rng.randrange(4, 44), rng.randrange(16, 24))])
    dots(surface, "bone", [(3, 17), (44, 17)])
    fill(surface, "ink", (0, 30, 48, 1))
    return surface


def _tyres() -> pygame.Surface:
    surface = _blank(16, 16)
    # Three tyres in a stack, seen a little from above.
    for y in (9, 5, 1):
        _box(surface, (3, y + 1, 10, 4), "shadow")
        fill(surface, "iron", (4, y + 1, 8, 1))
        fill(surface, "ink", (6, y + 2, 4, 1))
        dots(surface, "stone", [(4, y + 3), (8, y + 3), (11, y + 3)])
    return surface


def _junk() -> pygame.Surface:
    surface = _blank(16, 16)
    # Odds and ends nobody has found a use for yet: a bent pipe, a tin, a scrap of sheet.
    fill(surface, "ink", (2, 10, 9, 3))
    fill(surface, "iron", (3, 11, 7, 1))
    dots(surface, "stone", [(3, 11), (9, 11)])
    fill(surface, "ink", (9, 5, 5, 5))
    fill(surface, "rust", (10, 6, 3, 3))
    dots(surface, "copper", [(11, 6)])
    fill(surface, "ink", (4, 4, 4, 4))
    fill(surface, "dust", (5, 5, 2, 2))
    dots(surface, "rust_dark", [(12, 12), (2, 7), (7, 14)])
    return surface


def _barrel() -> pygame.Surface:
    """Three frames of a barrel with a fire burning in it."""
    flames = (
        [(6, 3), (7, 2), (8, 3), (9, 4)],
        [(7, 3), (8, 2), (9, 3), (6, 4)],
        [(6, 4), (7, 3), (8, 1), (9, 3)],
    )
    surface = _blank(48, 16)
    for frame, tips in enumerate(flames):
        left = frame * 16
        _box(surface, (left + 4, 7, 8, 8), "steel")
        for y in (9, 13):
            fill(surface, "deep", (left + 4, y, 8, 1))
        fill(surface, "ember", (left + 5, 4, 6, 3))
        fill(surface, "lamp", (left + 6, 5, 4, 2))
        dots(surface, "ember", [(left + x, y) for x, y in tips])
        dots(surface, "glow", [(left + 7, 5), (left + 8, 5)])
    return surface


def _scrap_pile() -> pygame.Surface:
    surface = _blank(32, 16)
    rng = random.Random(41)
    colors = ("iron", "stone", "rust", "shadow", "copper", "iron", "rust_dark")
    for x in range(1, 31):
        # A heap: tallest in the middle, ragged on top.
        height = max(2, 12 - abs(x - 15) * 2 // 3 + rng.randint(-2, 1))
        top = 15 - height
        dots(surface, "ink", [(x, top - 1)])
        for y in range(top, 15):
            dots(surface, rng.choice(colors), [(x, y)])
    fill(surface, "ink", (0, 15, 32, 1))
    dots(surface, "dust", [(9, 9), (16, 5), (22, 10)])
    return surface


def _water_tank() -> pygame.Surface:
    surface = _blank(32, 32)
    pygame.draw.ellipse(surface, PALETTE["ink"], (1, 1, 30, 30))
    pygame.draw.ellipse(surface, PALETTE["steel"], (2, 2, 28, 28))
    pygame.draw.ellipse(surface, PALETTE["deep"], (4, 4, 24, 24))
    pygame.draw.ellipse(surface, PALETTE["teal"], (5, 5, 22, 22))
    dots(surface, "mist", [(10, 10), (11, 10), (12, 11), (19, 18), (20, 18), (14, 21)])
    fill(surface, "ink", (13, 25, 6, 7))
    fill(surface, "rust", (14, 25, 4, 6))
    dots(surface, "copper", [(15, 26), (15, 28), (15, 30)])
    return surface


def _generator() -> pygame.Surface:
    surface = _blank(32, 16)
    _box(surface, (2, 5, 22, 9), "iron")
    fill(surface, "stone", (2, 5, 22, 1))
    fill(surface, "shadow", (4, 8, 9, 4))
    fill(surface, "rust", (15, 8, 7, 3))
    dots(surface, "lamp", [(6, 9), (8, 9), (19, 9)])
    dots(surface, "ember", [(20, 9)])
    fill(surface, "ink", (24, 7, 6, 1))
    fill(surface, "ink", (29, 7, 1, 6))
    fill(surface, "copper", (25, 8, 4, 4))
    for x in (5, 20):
        fill(surface, "ink", (x, 13, 5, 2))
        fill(surface, "rust_dark", (x + 1, 13, 3, 1))
    return surface


def _well() -> pygame.Surface:
    """A ring of stones with a beam over it and a bucket."""
    surface = _blank(16, 32)
    for x in (2, 12):
        fill(surface, "ink", (x - 1, 7, 4, 16))
        fill(surface, "rust", (x, 8, 2, 14))
    _box(surface, (1, 5, 14, 2), "rust_dark")
    fill(surface, "sand", (8, 7, 1, 8))
    _box(surface, (6, 14, 4, 3), "iron")
    pygame.draw.ellipse(surface, PALETTE["ink"], (0, 17, 16, 9))
    _box(surface, (1, 22, 14, 8), "stone")
    pygame.draw.ellipse(surface, PALETTE["dust"], (1, 18, 14, 7))
    pygame.draw.ellipse(surface, PALETTE["shadow"], (3, 19, 10, 5))
    dots(surface, "teal", [(6, 21), (7, 21), (8, 21)])
    dots(surface, "ink", [(5, 25), (10, 25), (7, 28), (12, 27)])
    return surface


def _refrigerated_chest() -> pygame.Surface:
    """A long white chest with a lid, the grille of its motor and a light."""
    surface = _blank(32, 16)
    _box(surface, (2, 6, 28, 9), "paper")
    fill(surface, "ink", (1, 3, 30, 1))
    fill(surface, "mist", (1, 4, 30, 2))
    fill(surface, "ink", (1, 6, 30, 1))
    fill(surface, "iron", (12, 7, 8, 1))
    fill(surface, "dust", (22, 9, 6, 4))
    dots(surface, "iron", [(23, 10), (25, 10), (27, 10), (23, 12), (25, 12), (27, 12)])
    dots(surface, "lichen", [(4, 9)])
    dots(surface, "teal", [(6, 9)])
    dots(surface, "mist", [(10, 10), (11, 11), (14, 10), (15, 12)])
    return surface


def _warehouse() -> pygame.Surface:
    """A shed of sheet metal, four tiles by three, seen from above and a little from its front."""
    surface = _blank(64, 48)
    # The roof, in sheets, with its ridge and a patch or two.
    _box(surface, (1, 1, 62, 30), "rust")
    for x in range(6, 62, 6):
        fill(surface, "rust_dark", (x, 1, 1, 30))
    fill(surface, "copper", (1, 14, 62, 2))
    fill(surface, "iron", (38, 20, 9, 6))
    fill(surface, "rust_dark", (10, 5, 8, 5))
    # The wall under it, with its two doors and what is painted over them.
    _box(surface, (1, 32, 62, 14), "steel")
    fill(surface, "stone", (1, 32, 62, 1))
    fill(surface, "rust_dark", (1, 44, 62, 2))
    fill(surface, "ink", (20, 35, 24, 11))
    fill(surface, "rust", (21, 36, 10, 10))
    fill(surface, "rust", (33, 36, 10, 10))
    fill(surface, "shadow", (31, 36, 2, 10))
    dots(surface, "lamp", [(30, 40), (34, 40)])
    fill(surface, "bone", (28, 33, 8, 2))
    for x in (7, 51):
        fill(surface, "ink", (x, 36, 6, 5))
        fill(surface, "deep", (x + 1, 37, 4, 3))
    return surface


def _clinic_bed() -> pygame.Surface:
    # The ordinary bed in hospital colours: a steel frame, white sheets and a red cross on the blanket.
    legend = {
        "o": "ink", "f": "stone", "k": "iron", "w": "bone", "p": "paper", "d": "dust",
        "b": "paper", "B": "bone", "D": "dust",
    }
    surface = paint(BED, legend)
    fill(surface, "blood", (7, 17, 2, 6))
    fill(surface, "blood", (5, 19, 6, 2))
    return surface


def _medicine_cabinet() -> pygame.Surface:
    surface = _blank(16, 32)
    for x in (3, 11):
        _box(surface, (x, 27, 2, 4), "iron")
    _box(surface, (2, 5, 12, 22), "bone")
    fill(surface, "paper", (2, 5, 12, 1))
    fill(surface, "dust", (8, 6, 1, 21))
    fill(surface, "blood", (7, 11, 2, 10))
    fill(surface, "blood", (3, 15, 10, 2))
    dots(surface, "iron", [(6, 23), (10, 23)])
    return surface


def _grave() -> pygame.Surface:
    surface = _blank(16, 16)
    # A mound of turned earth and a cross made of scrap.
    _box(surface, (3, 11, 10, 4), "earth_dark")
    dots(surface, "earth", [(5, 12), (9, 13), (11, 12)])
    _box(surface, (7, 2, 2, 10), "stone")
    _box(surface, (4, 5, 8, 2), "stone")
    fill(surface, "stone", (7, 5, 2, 2))
    dots(surface, "rust", [(5, 6), (10, 5), (8, 9)])
    return surface


def _study_desk() -> pygame.Surface:
    surface = _blank(16, 32)
    # A plank across two crates, with an open book on it and a stub of candle to read by.
    for x in (2, 11):
        _box(surface, (x, 24, 3, 7), "rust_dark")
    fill(surface, "shadow", (5, 26, 6, 3))
    _box(surface, (1, 20, 14, 4), "copper")
    fill(surface, "sand", (1, 20, 14, 1))
    fill(surface, "ink", (2, 15, 9, 5))
    fill(surface, "paper", (3, 16, 3, 3))
    fill(surface, "bone", (7, 16, 3, 3))
    dots(surface, "dust", [(4, 17), (8, 17), (8, 18)])
    fill(surface, "ink", (11, 14, 4, 6))
    fill(surface, "bone", (12, 15, 2, 5))
    dots(surface, "lamp", [(12, 12), (13, 13)])
    dots(surface, "ember", [(12, 13), (13, 14)])
    return surface


def build() -> dict[str, pygame.Surface]:
    painters = {
        "study_desk": _study_desk,
        "cooking_pot": _cooking_pot,
        "bar": _bar,
        "crop_bed": _crop_bed,
        "guard_post": _guard_post,
        "workbench": _workbench,
        "shop_counter": _shop_counter,
        "lab_bench": _lab_bench,
        "shelf": _shelf,
        "lamp": _lamp,
        "handcart": _handcart,
        "caravan_cart": _caravan_cart,
        "radio_set": _radio_set,
        "wreck": _wreck,
        "tyres": _tyres,
        "junk": _junk,
        "barrel": _barrel,
        "scrap_pile": _scrap_pile,
        "water_tank": _water_tank,
        "generator": _generator,
        "clinic_bed": _clinic_bed,
        "medicine_cabinet": _medicine_cabinet,
        "grave": _grave,
        "warehouse": _warehouse,
        "well": _well,
        "refrigerated_chest": _refrigerated_chest,
    }
    return {f"sprites/objects/{kind}.png": painter() for kind, painter in painters.items()}
