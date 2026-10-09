"""The country a trip goes through, seen from the side: layers that go by each at its own pace.

A backdrop is so many layers on one paper, from the sky at the back to what passes in front
of whoever walks. Each goes by at a share of the pace of the ground, and each meets itself at
its ends, so that it goes round for as long as there is walking to do. Which layers there are
is data, in `data/backdrops.json`; the layers of a zone are what somebody has drawn of them
(P69), and where nobody has, the game's own (`graphics.backdrop_pictures`).

None of it is the simulation's: which zone a trip goes through is, and that is all that is
asked of it.
"""

import functools
import json
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pygame

from graphics.illustrations import Illustrations

Size = tuple[int, int]

BACKDROPS_PATH = Path(__file__).resolve().parent.parent / "data" / "backdrops.json"
BACKDROPS_FOLDER = "backdrops"
# The art of a zone that names none, or one the game has no picture of.
PLAIN_ART = "plain"
# What draws a layer of the game's own, of one kind of art, at a size.
Painter = Callable[[str, str, Size, "BackdropPlan"], pygame.Surface]


def backdrop_path(zone_id: str, layer_id: str) -> str:
    return f"{BACKDROPS_FOLDER}/{zone_id}/{layer_id}.png"


@dataclass(frozen=True)
class BackdropLayer:
    layer_id: str
    name: str
    # How much of the way the ground goes this layer goes: nothing for what stands still, more
    # than all of it for what is nearer than whoever walks.
    pace: float
    # Whether it passes in front of whoever walks.
    front: bool = False
    # What goes in it, said to whoever draws it.
    note: str = ""


@dataclass(frozen=True)
class BackdropPlan:
    """How every backdrop is laid out: the paper its layers are drawn on, and what is where on it."""

    paper: Size
    # How far down the paper the ground is that feet are on, and how much of its height
    # somebody standing there takes, both as shares of it.
    ground: float
    figure: float
    layers: tuple[BackdropLayer, ...]
    # The game's own art of each zone, by zone ID.
    art: dict[str, str]

    def layer(self, layer_id: str) -> BackdropLayer | None:
        return next((layer for layer in self.layers if layer.layer_id == layer_id), None)

    def art_of(self, zone_id: str) -> str:
        return self.art.get(zone_id, PLAIN_ART)


def backdrops_from_data(data: dict[str, Any]) -> BackdropPlan:
    wide, tall = (int(value) for value in data.get("paper", (400, 310)))
    ground, figure = float(data.get("ground", 0.8)), float(data.get("figure", 0.24))
    if wide < 16 or tall < 16:
        raise ValueError("The paper of a backdrop is too small to draw on")
    if not 0.0 < figure < ground < 1.0:
        raise ValueError("A backdrop needs ground to stand on, below whoever stands on it and above the foot of the paper")
    layers = []
    for entry in data.get("layers", []):
        layer = BackdropLayer(
            str(entry["id"]),
            str(entry.get("name", entry["id"])),
            float(entry.get("pace", 1.0)),
            bool(entry.get("front", False)),
            str(entry.get("note", "")),
        )
        if layer.pace < 0.0:
            raise ValueError(f"Layer {layer.layer_id} of the backdrops goes backwards")
        layers.append(layer)
    if not layers:
        raise ValueError("A backdrop needs at least one layer")
    if len({layer.layer_id for layer in layers}) != len(layers):
        raise ValueError("Two layers of the backdrops have the same ID")
    art = {
        str(zone_id): str(entry.get("art", PLAIN_ART)) if isinstance(entry, dict) else PLAIN_ART
        for zone_id, entry in dict(data.get("zones", {})).items()
    }
    return BackdropPlan((wide, tall), ground, figure, tuple(layers), art)


def load_backdrops(path: Path = BACKDROPS_PATH) -> BackdropPlan:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"Expected object in {path}")
    return backdrops_from_data(data)


@functools.cache
def builtin_backdrops() -> BackdropPlan:
    """The game's own, loaded once. It is read-only."""
    return load_backdrops()


@dataclass(frozen=True)
class Strip:
    """A layer as it is shown: the rows of it that have anything in them, and how wide it is
    before it comes round again."""

    layer: BackdropLayer
    picture: pygame.Surface
    # How far down the place it is shown in its first row is.
    top: int


def _for_showing(picture: pygame.Surface) -> pygame.Surface:
    """A picture as fast to show as it can be made, where there is a window to show it on: one
    with nothing clear in it, as a sky is, is shown without asking what is behind it."""
    if not (pygame.display.get_init() and pygame.display.get_surface() is not None):
        return picture
    solid = pygame.mask.from_surface(picture, 254).count() == picture.get_width() * picture.get_height()
    return picture.convert() if solid else picture.convert_alpha()


class BackdropStore:
    """Finds the layers of a zone: what somebody has drawn of each, or else the game's own."""

    def __init__(self, illustrations: Illustrations | None, plan: BackdropPlan | None = None, painter: Painter | None = None) -> None:
        self.illustrations = illustrations if illustrations is not None and illustrations.root is not None else None
        self.plan = plan if plan is not None else builtin_backdrops()
        if painter is None:
            from graphics.backdrop_pictures import painted

            painter = painted
        self._painter = painter
        self._strips: dict[tuple[str, int], list[Strip]] = {}

    @property
    def available(self) -> bool:
        """Whether there is anywhere to keep drawings."""
        return self.illustrations is not None

    def drawing(self, zone_id: str, layer_id: str) -> pygame.Surface | None:
        """What somebody has drawn of a layer of a zone, on the paper. None if nobody has."""
        if self.illustrations is None:
            return None
        return self.illustrations.fitted(backdrop_path(zone_id, layer_id), self.plan.paper)

    def drawn(self, zone_id: str) -> bool:
        """Whether anybody has drawn anything of a zone."""
        return any(self.drawing(zone_id, layer.layer_id) is not None for layer in self.plan.layers)

    def starter(self, zone_id: str, layer_id: str) -> pygame.Surface:
        """The game's own picture of a layer on the paper, to be drawn over."""
        return self._painter(self.plan.art_of(zone_id), layer_id, self.plan.paper, self.plan)

    def size_for(self, height: int) -> Size:
        """How large the paper is shown where it has so many pixels of height to fill."""
        wide, tall = self.plan.paper
        return (max(1, round(wide * height / tall)), max(1, height))

    def strips(self, zone_id: str, height: int) -> list[Strip]:
        """The layers of a zone at the size that fills a height, from the back to the front."""
        key = (zone_id, height)
        if key not in self._strips:
            if len(self._strips) >= 4:
                # They are large, and one zone at one size is all that is ever on show.
                self._strips.clear()
            self._strips[key] = [self._strip(zone_id, layer, self.size_for(height)) for layer in self.plan.layers]
        return self._strips[key]

    def _strip(self, zone_id: str, layer: BackdropLayer, size: Size) -> Strip:
        own = self.drawing(zone_id, layer.layer_id)
        if own is not None:
            picture = pygame.transform.smoothscale(own, size)
        else:
            # Where nobody has drawn it the game draws it at the size it is shown, and not on the paper.
            picture = self._painter(self.plan.art_of(zone_id), layer.layer_id, size, self.plan)
        rows = picture.get_bounding_rect()
        if rows.height <= 0:
            return Strip(layer, pygame.Surface((size[0], 1), pygame.SRCALPHA), 0)
        band = pygame.Rect(0, rows.y, size[0], rows.height)
        return Strip(layer, _for_showing(picture.subsurface(band).copy()), rows.y)

    def forget(self, zone_id: str) -> None:
        """Have a zone's drawings read again, as after they have been drawn anew."""
        for key in [key for key in self._strips if key[0] == zone_id]:
            del self._strips[key]
        if self.illustrations is not None:
            for layer in self.plan.layers:
                self.illustrations.forget(backdrop_path(zone_id, layer.layer_id))


def draw_strips(
    target: pygame.Surface, strips: list[Strip], area: pygame.Rect, travelled: float, front: bool
) -> None:
    """Show the layers that are behind whoever walks, or the ones in front, over a part of a
    picture. `travelled` is how far the ground has gone by, in pixels: each layer has gone by
    its own share of that, and comes round again as often as it takes to fill the place."""
    before = target.get_clip()
    target.set_clip(area.clip(before))
    for strip in strips:
        if strip.layer.front != front:
            continue
        wide = strip.picture.get_width()
        x = area.x - int(travelled * strip.layer.pace) % wide
        while x < area.right:
            target.blit(strip.picture, (x, area.y + strip.top))
            x += wide
    target.set_clip(before)
