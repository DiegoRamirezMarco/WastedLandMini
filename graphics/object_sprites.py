"""Sprites for furniture and other objects placed on the map, with custom overrides."""

import logging

import pygame

from graphics.assets import AssetStore
from settings import TILE_SIZE
from world.interactable import InteractableDefinition

logger = logging.getLogger(__name__)

CUSTOM_FOLDER = "objects"
CUSTOM_FILE = "sprite.png"


def builtin_object_path(kind: str) -> str:
    return f"sprites/objects/{kind}.png"


def custom_object_path(kind: str) -> str:
    return f"{CUSTOM_FOLDER}/{kind}/{CUSTOM_FILE}"


class ObjectSprites:
    """Resolve object art, preferring a valid sprite supplied by its content pack."""

    def __init__(self, assets: AssetStore, custom: AssetStore | None = None) -> None:
        self.assets = assets
        self.custom = custom
        self._sheets: dict[tuple[str, int, int], pygame.Surface] = {}

    def sheet(self, definition: InteractableDefinition) -> pygame.Surface:
        key = (definition.kind, definition.width, definition.height)
        if key not in self._sheets:
            self._sheets[key] = self._load(definition)
        return self._sheets[key]

    def frames(self, definition: InteractableDefinition) -> int:
        """Animation frames laid side by side in the resolved sheet."""
        frame_width = definition.width * TILE_SIZE
        return max(1, self.sheet(definition).get_width() // frame_width)

    def _load(self, definition: InteractableDefinition) -> pygame.Surface:
        frame = (definition.width * TILE_SIZE, definition.height * TILE_SIZE)
        if self.custom is not None and CUSTOM_FILE in self.custom.files(
            f"{CUSTOM_FOLDER}/{definition.kind}"
        ):
            picture = self.custom.optional_image(custom_object_path(definition.kind))
            if (
                picture is not None
                and picture.get_width() % frame[0] == 0
                and picture.get_height() >= frame[1]
            ):
                return picture
            logger.warning(
                "Custom object sprite %s must be a multiple of %s pixels wide and at least %s high",
                definition.kind,
                frame[0],
                frame[1],
            )
        return self.assets.image(builtin_object_path(definition.kind))
