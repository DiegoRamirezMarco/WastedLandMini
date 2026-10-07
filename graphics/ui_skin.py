"""What dresses the interface at the resolution of the window.

Scenes go on asking for panels, buttons and bars on the canvas, in its own coordinates. Where the
window can show something finer under the canvas, this leaves the canvas clear there and puts a
picture underneath: one a file in `illustrations/ui/` gives, or else one made by code.
"""

from collections.abc import Hashable

import pygame

from graphics import ui_art
from graphics.illustrations import Illustrations, nine_slice
from graphics.palette import PALETTE, Color
from graphics.screen_layers import TRANSPARENT, ScreenLayers

# The picture that the large parts of the screen wear, if somebody has made one, and how wide its border is drawn.
SKIN_PATH = "ui/panel.png"
SKIN_BORDER_PIXELS = 20
# Where a picture that takes the place of one of the icons goes, by the name of the icon.
ICONS_DIR = "ui/icons"
# A panel smaller than this, on the canvas, is left flat: there is no room on it for a frame.
SMALLEST_DRESSED = (20, 12)
# How many pictures are kept made. Bars are kept apart: there is one for every length a bar has had,
# and letting go of them must not let go of the frames, which take far longer to make.
CACHE_LIMIT = 256
BAR_LIMIT = 512

BRASS: Color = (186, 136, 70)
# The plate the large parts of the screen are made of: the bar, the menu, the panel and the dock.
PLATE = ui_art.FrameStyle(fill=(31, 39, 47), trim=BRASS, radius=6, rivets=True)
# What the flat colours a panel is asked for in become on the window.
FILLS: dict[str, Color] = {
    "ink": ui_art.mix(PALETTE["ink"], PALETTE["deep"], 0.55),
    "shadow": ui_art.mix(PALETTE["shadow"], PALETTE["steel"], 0.4),
}
TRIMS: dict[str, Color] = {"iron": (94, 124, 134), "stone": (140, 146, 142)}
BAND: Color = (56, 104, 122)
BUTTON: Color = (62, 78, 92)
BUTTON_TRIM: Color = (126, 152, 162)
BUTTON_ON: Color = PALETTE["lamp"]
BUTTON_ON_TRIM: Color = PALETTE["glow"]
SHADOW = 8


class WindowSkin:
    def __init__(
        self, canvas: pygame.Surface, layers: ScreenLayers | None, illustrations: Illustrations | None = None
    ) -> None:
        self.canvas = canvas
        self.layers = layers
        self.illustrations = illustrations
        # The large parts of the screen, by where they are on the canvas.
        self.parts: set[tuple[int, int, int, int]] = set()
        # Where the pointer is, on the canvas, while whatever is being drawn lights up under it.
        self.pointer: tuple[int, int] | None = None
        self._source = illustrations.find(SKIN_PATH) if illustrations is not None else None
        self._pictures: dict[Hashable, pygame.Surface] = {}
        self._bars: dict[Hashable, pygame.Surface] = {}

    @property
    def usable(self) -> bool:
        """Whether there is a window under the canvas, and the canvas can be seen through."""
        return self.layers is not None and bool(self.canvas.get_flags() & pygame.SRCALPHA)

    def _reaches(self, target: pygame.Surface, rect: pygame.Rect) -> bool:
        """Whether a part of what is being drawn on can be cleared for a picture under it."""
        return target is self.canvas and self.usable and target.get_clip().contains(rect)

    def _kept(self, key: Hashable, make) -> pygame.Surface:
        if key not in self._pictures:
            if len(self._pictures) >= CACHE_LIMIT:
                self._pictures.clear()
            self._pictures[key] = make()
        return self._pictures[key]

    def _show(self, target: pygame.Surface, picture: pygame.Surface, rect: pygame.Rect, spread: int = 0) -> None:
        """Clear the canvas over a rectangle and put a picture under it, larger by `spread` all round."""
        target.fill(TRANSPARENT, rect)
        corner = self.layers.on_screen(rect).topleft
        place = (corner[0] - spread, corner[1] - spread)
        self.layers.under(lambda screen: screen.blit(picture, place))

    # ----- what `ui.panel` asks for -----

    def panel(
        self, target: pygame.Surface, rect: pygame.Rect, fill: str, border: str, band: int, band_color: Color | None
    ) -> bool:
        if not self._reaches(target, rect):
            return False
        size = self.layers.on_screen(rect).size
        if tuple(rect) in self.parts:
            if self._source is not None:
                skin = self._kept(("skin", size), lambda: nine_slice(self._source, size, SKIN_BORDER_PIXELS))
                self._show(target, skin, rect)
                return True
            style = PLATE
        elif rect.width < SMALLEST_DRESSED[0] or rect.height < SMALLEST_DRESSED[1]:
            return False
        else:
            style = ui_art.FrameStyle(
                fill=FILLS.get(fill, PALETTE[fill]),
                trim=TRIMS.get(border, PALETTE[border]),
                radius=5,
                band=(band_color or BAND) if band else None,
                band_height=band * self.layers.scale,
                shadow=SHADOW if band else 0,
            )
        self._show(target, self._kept((size, style), lambda: ui_art.frame(size, style)), rect, style.shadow)
        return True

    def button(self, target: pygame.Surface, rect: pygame.Rect, active: bool) -> bool:
        if not self._reaches(target, rect):
            return False
        size = self.layers.on_screen(rect).size
        hot = self.pointer is not None and rect.collidepoint(self.pointer)
        fill, trim = (BUTTON_ON, BUTTON_ON_TRIM) if active else (BUTTON, BUTTON_TRIM)
        if hot:
            fill = ui_art.lighter(fill, 0.16)
        self._show(target, self._kept(("button", size, fill, trim), lambda: ui_art.pill(size, fill, trim)), rect)
        return True

    def bar(self, target: pygame.Surface, rect: pygame.Rect, share: float, color: str) -> bool:
        if not self._reaches(target, rect):
            return False
        size = self.layers.on_screen(rect).size
        filled = round(size[0] * max(0.0, min(1.0, share)))
        key = (size, filled, color)
        if key not in self._bars:
            if len(self._bars) >= BAR_LIMIT:
                self._bars.clear()
            self._bars[key] = ui_art.bar(size, filled / size[0], PALETTE[color])
        self._show(target, self._bars[key], rect)
        return True

    def item(self, target: pygame.Surface, rect: pygame.Rect, icons, item_id: str) -> bool:
        if not self._reaches(target, rect):
            return False
        size = self.layers.on_screen(rect).size
        self._show(target, icons.shown(item_id, min(size)), rect)
        return True

    # ----- icons -----

    def tile(self, name: str, size: int, lit: bool = False) -> pygame.Surface:
        """The icon of an entry of the menu, on its tile, at a size of the window."""
        return self._own(name, size) or self._kept(("tile", name, size, lit), lambda: ui_art.tile(name, size, lit))

    def icon(self, name: str, size: int) -> pygame.Surface:
        """An icon standing alone, at a size of the window."""
        return self._own(name, size) or self._kept(("icon", name, size), lambda: ui_art.icon(name, size))

    def _own(self, name: str, size: int) -> pygame.Surface | None:
        if self.illustrations is None:
            return None
        return self.illustrations.fitted(f"{ICONS_DIR}/{name}.png", (size, size))

    def picture(self, target: pygame.Surface, picture: pygame.Surface, rect: pygame.Rect) -> bool:
        """Show a picture made for the window in a part of the canvas. Says whether it could."""
        if not self._reaches(target, rect):
            return False
        self._show(target, picture, rect)
        return True

    def plate(self, target: pygame.Surface, rect: pygame.Rect, fill: Color, trim: Color, radius: int = 8) -> bool:
        """A rounded plate with nothing on it, behind whatever stands out: an entry of the menu that is open."""
        if not self._reaches(target, rect):
            return False
        size = self.layers.on_screen(rect).size
        style = ui_art.FrameStyle(fill=fill, trim=trim, radius=radius)
        self._show(target, self._kept((size, style), lambda: ui_art.frame(size, style)), rect)
        return True
