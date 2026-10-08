"""Finds the icon of an item: a content pack may add one or replace built-in art."""

import math

import pygame

from graphics import item_pictures
from graphics.assets import AssetStore, make_placeholder

ICON_SIZE = (16, 16)
# How many colours of a thing are kept for what flies off it, and from how fine a grid over its picture.
CRUMB_COLORS = 6
CRUMB_GRID = 8
# Red, green and blue together under this is too dark to be anything but an outline.
DARKEST_CRUMB = 150
# How many bites can be seen gone from a thing.
BITES = 4
# A bite is this large across, as a share of the longer side of the thing, and is made of this
# many rounds side by side, as teeth leave it.
BITE_ACROSS = 0.34
TEETH = 3
# The edge of a thing is looked for on a copy of it no larger than this, however large it was drawn.
SEARCHED = 48
# Folders of `custom_content/` in which a pack may bring an `icon.png`. The last is where the
# pictures of what residents have come to at their jobs are kept (P54): it is no pack.
PACK_FOLDERS = ("items", "foods", "made")
# A thing held by its handle is kept turned in this many steps of a full turn, and so many
# pictures of it are kept before the oldest are let go.
GRIP_TURNS = 240
GRIPS_KEPT = 720
# The game's own pictures are painted again, larger, for a hand that shows them larger than
# they were made: by whole times their size, up to this many.
LARGEST_PAINTED = 4


def builtin_icon_path(item_id: str) -> str:
    return f"sprites/items/{item_id}.png"


class ItemIcons:
    def __init__(self, assets: AssetStore, custom: AssetStore | None = None) -> None:
        self._assets = assets
        self._custom = custom
        self._cache: dict[str, pygame.Surface] = {}
        self._small: dict[str, pygame.Surface] = {}
        self._pictures: dict[str, pygame.Surface] = {}
        self._eaten: dict[tuple[str, int], pygame.Surface] = {}
        self._held: dict[tuple[str, int, int, bool], pygame.Surface] = {}
        self._colors: dict[str, list[tuple[int, int, int]]] = {}
        self._shown: dict[tuple[str, int], pygame.Surface] = {}
        self._gripped: dict[tuple, tuple[pygame.Surface, tuple[float, float]]] = {}
        self._painted_large: dict[tuple[str, int], pygame.Surface] = {}
        # Whether the game's own items are shown as it draws them for the window (P41), in place of
        # their small icons, wherever a picture as large as it was made is asked for.
        self.painted = False

    def icon(self, item_id: str) -> pygame.Surface:
        """Return the 16×16 icon of an item, or the placeholder if it has none."""
        if item_id not in self._cache:
            self._cache[item_id] = self._find(item_id)
        return self._cache[item_id]

    def small(self, item_id: str) -> pygame.Surface:
        """The icon at half size, for things seen on the map: in someone's hands or on a shelf."""
        if item_id not in self._small:
            half = (ICON_SIZE[0] // 2, ICON_SIZE[1] // 2)
            self._small[item_id] = pygame.transform.scale(self.icon(item_id), half)
        return self._small[item_id]

    def picture(self, item_id: str) -> pygame.Surface:
        """The picture of an item at the size it was made: a pack's as large as it was drawn, the game's own 16×16."""
        if item_id not in self._pictures:
            found = self._find_picture(item_id)
            picture = pygame.Surface(found.get_size(), pygame.SRCALPHA)
            picture.blit(found, (0, 0))
            self._pictures[item_id] = picture
        return self._pictures[item_id]

    def shown(self, item_id: str, size: int) -> pygame.Surface:
        """The picture of an item brought to `size` pixels a side, for where it is shown on the window."""
        key = (item_id, size)
        if key not in self._shown:
            picture = self.picture(item_id)
            fits = picture.get_size() == (size, size)
            small = max(picture.get_size()) < size
            # A small picture made larger keeps its hard edges; a large one is brought down smoothly.
            resize = pygame.transform.scale if small else pygame.transform.smoothscale
            self._shown[key] = picture if fits else resize(picture, (size, size))
        return self._shown[key]

    def held(self, item_id: str, size: int, bites: int = 0, mirrored: bool = False) -> pygame.Surface:
        """An item as it is seen in someone's hand: what was drawn of it and none of the empty
        paper round it, `size` pixels along its longer side, with so many bites gone from it.

        A picture larger than that is brought down smoothly, so that what was drawn can be made
        out; a smaller one is made larger by whole pixels, and keeps the hard edges it was made
        with wherever that comes out even. `mirrored` is for whoever faces left.
        """
        size = max(1, size)
        bites = min(max(bites, 0), BITES)
        key = (item_id, size, bites, mirrored)
        if key not in self._held:
            drawn = self._bitten(item_id, bites)
            width, height = drawn.get_size()
            longer = max(width, height)
            fitted = (max(1, round(width * size / longer)), max(1, round(height * size / longer)))
            if longer < size:
                times = -(-size // longer)
                drawn = pygame.transform.scale(drawn, (width * times, height * times))
            held = drawn if drawn.get_size() == fitted else pygame.transform.smoothscale(drawn, fitted)
            self._held[key] = pygame.transform.flip(held, True, False) if mirrored else held
        return self._held[key]

    def gripped(
        self,
        item_id: str,
        start: tuple[float, float],
        end: tuple[float, float],
        long: float,
        way: tuple[float, float],
        at: float = 0.0,
        mirrored: bool = False,
    ) -> tuple[pygame.Surface, tuple[float, float]]:
        """An item as it is seen held by its handle, and where on that picture it is held.

        `start` and `end` are the two ends of its handle on its picture, in hundredths of its
        side, the one it is held by first. It is shown with that handle `long` pixels from end
        to end and running `way`, a direction on the screen, and the point given back is the one
        `at` that share of the way along the handle. `mirrored` is for whoever faces left: the
        thing is the other way round in their hands.
        """
        angle = math.atan2(-way[1], way[0])
        step = round(angle / math.tau * GRIP_TURNS) % GRIP_TURNS
        key = (item_id, start, end, max(1, round(long)), step, round(at * 100), mirrored)
        kept = self._gripped.get(key)
        if kept is not None:
            return kept
        handle = math.dist(start, end) / 100.0
        picture = self._to_grip(item_id, key[3] / handle if handle > 0 else 1.0)
        width, height = picture.get_size()
        first = (start[0] * width / 100.0, start[1] * height / 100.0)
        last = (end[0] * width / 100.0, end[1] * height / 100.0)
        if mirrored:
            picture = pygame.transform.flip(picture, True, False)
            first, last = (width - first[0], first[1]), (width - last[0], last[1])
        drawn = math.dist(first, last) or 1.0
        scale = key[3] / drawn
        # Turned from the way its handle runs on its picture to the way it is to run.
        turn = step * math.tau / GRIP_TURNS - math.atan2(-(last[1] - first[1]), last[0] - first[0])
        turned = pygame.transform.rotozoom(picture, math.degrees(turn), scale)
        held = (first[0] + (last[0] - first[0]) * at - width / 2.0, first[1] + (last[1] - first[1]) * at - height / 2.0)
        cos, sin = math.cos(turn), math.sin(turn)
        point = (
            turned.get_width() / 2.0 + (held[0] * cos + held[1] * sin) * scale,
            turned.get_height() / 2.0 + (-held[0] * sin + held[1] * cos) * scale,
        )
        if len(self._gripped) >= GRIPS_KEPT:
            for old in list(self._gripped)[: GRIPS_KEPT // 4]:
                del self._gripped[old]
        self._gripped[key] = (turned, point)
        return self._gripped[key]

    def _to_grip(self, item_id: str, side: float) -> pygame.Surface:
        """The picture of an item to be turned in a hand, where its whole side would be `side`
        pixels: the game's own painted as large as that takes, any other as it was made."""
        picture = self.picture(item_id)
        times = min(LARGEST_PAINTED, math.ceil(side / max(picture.get_size())))
        own = self._custom is None or not any("icon.png" in self._custom.files(f"{folder}/{item_id}") for folder in PACK_FOLDERS)
        if times <= 1 or not (own and self.painted and item_pictures.painted(item_id)):
            return picture
        key = (item_id, times)
        if key not in self._painted_large:
            self._painted_large[key] = item_pictures.picture(item_id, item_pictures.MADE_AT * times)
        return self._painted_large[key]

    def _bitten(self, item_id: str, bites: int) -> pygame.Surface:
        """What is drawn of an item, as large as it was made, with so many bites gone from it.

        Each bite is taken where what is left comes nearest the upper corner at its back, which is
        the one at the mouth of whoever faces right: so a meal is eaten into from there.
        """
        key = (item_id, bites)
        if key not in self._eaten:
            if bites == 0:
                picture = self.picture(item_id)
                drawn = picture.get_bounding_rect()
                self._eaten[key] = picture.subsurface(drawn).copy() if drawn.width and drawn.height else picture
            else:
                self._eaten[key] = self._bite(self._bitten(item_id, bites - 1))
        return self._eaten[key]

    @staticmethod
    def _bite(whole: pygame.Surface) -> pygame.Surface:
        width, height = whole.get_size()
        longer = max(width, height)
        # Small pictures are bitten at a finer grain than they were made, or a bite is a few squares.
        times = max(1, -(-SEARCHED // longer))
        bitten = pygame.transform.scale(whole, (width * times, height * times)) if times > 1 else whole.copy()
        width, height, longer = width * times, height * times, longer * times
        coarse = max(1, longer // SEARCHED)
        left = pygame.mask.from_surface(bitten).scale((max(1, width // coarse), max(1, height // coarse)))
        solid = [(x, y) for x in range(left.get_size()[0]) for y in range(left.get_size()[1]) if left.get_at((x, y))]
        if not solid:
            return bitten
        nearest = min(solid, key=lambda point: (point[0] * point[0] + point[1] * point[1], point))
        at = ((nearest[0] + 0.5) * coarse, (nearest[1] + 0.5) * coarse)
        middle = left.centroid()
        into = math.atan2((middle[1] + 0.5) * coarse - at[1], (middle[0] + 0.5) * coarse - at[0])
        reach = BITE_ACROSS * longer / 2.0
        for tooth in range(TEETH):
            # The rounds stand in a row across the way in, the middle one deepest.
            aside = (tooth - (TEETH - 1) / 2.0) * reach * 0.8
            deep = reach * (0.35 if tooth == TEETH // 2 else 0.1)
            centre = (
                at[0] + math.cos(into) * deep - math.sin(into) * aside,
                at[1] + math.sin(into) * deep + math.cos(into) * aside,
            )
            pygame.draw.circle(bitten, (0, 0, 0, 0), (round(centre[0]), round(centre[1])), max(1, round(reach * 0.62)))
        return bitten

    def crumb_colors(self, item_id: str) -> list[tuple[int, int, int]]:
        """A few of the colours an item is drawn in, the commonest first, for the crumbs that fly off it."""
        if item_id not in self._colors:
            picture = self.picture(item_id)
            width, height = picture.get_size()
            counts: dict[tuple[int, int, int], int] = {}
            for column in range(CRUMB_GRID):
                for row in range(CRUMB_GRID):
                    pixel = picture.get_at((column * width // CRUMB_GRID, row * height // CRUMB_GRID))
                    # Not the dark line round it: a crumb is a piece of what is inside.
                    if pixel[3] > 200 and sum(pixel[:3]) > DARKEST_CRUMB:
                        counts[tuple(pixel)[:3]] = counts.get(tuple(pixel)[:3], 0) + 1
            ranked = sorted(counts, key=lambda color: (-counts[color], color))
            self._colors[item_id] = ranked[:CRUMB_COLORS] or [(200, 180, 140)]
        return self._colors[item_id]

    def forget(self, item_id: str) -> None:
        """Reload an icon after the in-game item editor has saved it."""
        self._cache.pop(item_id, None)
        self._small.pop(item_id, None)
        self._pictures.pop(item_id, None)
        self._colors.pop(item_id, None)
        for kept in (self._eaten, self._held, self._shown, self._gripped, self._painted_large):
            for key in [key for key in kept if key[0] == item_id]:
                del kept[key]
        if self._custom is not None:
            for folder in PACK_FOLDERS:
                self._custom.forget(f"{folder}/{item_id}/icon.png")

    def _find_picture(self, item_id: str) -> pygame.Surface:
        if self._custom is not None:
            for folder in PACK_FOLDERS:
                if "icon.png" in self._custom.files(f"{folder}/{item_id}"):
                    return self._custom.image(f"{folder}/{item_id}/icon.png")
        if self.painted and item_pictures.painted(item_id):
            return item_pictures.picture(item_id)
        return self.icon(item_id)

    def _find(self, item_id: str) -> pygame.Surface:
        if self._custom is not None:
            for folder in PACK_FOLDERS:
                if "icon.png" in self._custom.files(f"{folder}/{item_id}"):
                    # Pack authors draw icons at any size; they are brought down to ours.
                    icon = self._custom.image(f"{folder}/{item_id}/icon.png")
                    return icon if icon.get_size() == ICON_SIZE else pygame.transform.scale(icon, ICON_SIZE)
        if f"{item_id}.png" in self._assets.files("sprites/items"):
            return self._assets.image(builtin_icon_path(item_id), size=ICON_SIZE)
        return make_placeholder(ICON_SIZE)
