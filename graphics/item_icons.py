"""Finds the icon of an item: built-in art first, then a content pack's own icon."""

import pygame

from graphics.assets import AssetStore, make_placeholder

ICON_SIZE = (16, 16)
# Folders of `custom_content/` in which a pack may bring an `icon.png`.
PACK_FOLDERS = ("items", "foods")


def builtin_icon_path(item_id: str) -> str:
    return f"sprites/items/{item_id}.png"


class ItemIcons:
    def __init__(self, assets: AssetStore, custom: AssetStore | None = None) -> None:
        self._assets = assets
        self._custom = custom
        self._cache: dict[str, pygame.Surface] = {}

    def icon(self, item_id: str) -> pygame.Surface:
        """Return the 16×16 icon of an item, or the placeholder if it has none."""
        if item_id not in self._cache:
            self._cache[item_id] = self._find(item_id)
        return self._cache[item_id]

    def _find(self, item_id: str) -> pygame.Surface:
        if f"{item_id}.png" in self._assets.files("sprites/items"):
            return self._assets.image(builtin_icon_path(item_id), size=ICON_SIZE)
        if self._custom is not None:
            for folder in PACK_FOLDERS:
                if "icon.png" in self._custom.files(f"{folder}/{item_id}"):
                    # Pack authors draw icons at any size; they are brought down to ours.
                    icon = self._custom.image(f"{folder}/{item_id}/icon.png")
                    return icon if icon.get_size() == ICON_SIZE else pygame.transform.scale(icon, ICON_SIZE)
        return make_placeholder(ICON_SIZE)
