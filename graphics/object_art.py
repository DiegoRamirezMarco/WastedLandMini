"""Furniture and loose objects as someone has drawn them: one picture a kind, for the window.

A drawing takes the place of the game's own sprite for every object of its kind. Whatever nobody
has drawn looks as it always has.
"""

import pygame

from graphics.illustrations import Illustrations
from graphics.object_sprites import ObjectSprites
from graphics.palette import PALETTE
from settings import TILE_SIZE
from world.interactable import InteractableDefinition

# Pixels of a drawing to a pixel of the map's own art: twice what the window shows at the default zoom.
OBJECT_DETAIL = 4
OBJECTS_FOLDER = "objects"
# How strongly the guide marks the ground an object stands on and the room it has to rise above it.
GROUND_FILL = (*PALETTE["ember"], 60)
ABOVE_FILL = (*PALETTE["steel"], 45)

Size = tuple[int, int]


def object_art_path(kind: str) -> str:
    return f"{OBJECTS_FOLDER}/{kind}.png"


class ObjectArtStore:
    """Finds the drawing of each kind of object, and gives the editor what it draws over."""

    def __init__(self, illustrations: Illustrations | None, sprites: ObjectSprites) -> None:
        self.illustrations = illustrations if illustrations is not None and illustrations.root is not None else None
        self.sprites = sprites

    @property
    def available(self) -> bool:
        """Whether there is anywhere to keep drawings."""
        return self.illustrations is not None

    def frame_size(self, definition: InteractableDefinition) -> Size:
        """The size of one object of a kind in pixels of the map's art: as wide as its tiles, as tall as its sprite."""
        return (definition.width * TILE_SIZE, self.sprites.sheet(definition).get_height())

    def canvas_size(self, definition: InteractableDefinition) -> Size:
        width, height = self.frame_size(definition)
        return (width * OBJECT_DETAIL, height * OBJECT_DETAIL)

    def drawing(self, definition: InteractableDefinition) -> pygame.Surface | None:
        """What someone has drawn for a kind, at the size it is drawn at. None if nobody has."""
        if self.illustrations is None:
            return None
        return self.illustrations.fitted(object_art_path(definition.kind), self.canvas_size(definition))

    def shown(self, definition: InteractableDefinition, size: Size) -> pygame.Surface | None:
        """The same drawing brought to the size it takes on the window, and kept at it."""
        if self.illustrations is None or size[0] <= 0 or size[1] <= 0:
            return None
        return self.illustrations.fitted(object_art_path(definition.kind), size)

    def starter(self, definition: InteractableDefinition) -> pygame.Surface:
        """The game's own sprite of a kind, enlarged with its hard edges, to be drawn over."""
        width, height = self.frame_size(definition)
        sheet = self.sprites.sheet(definition)
        frame = sheet.subsurface((0, 0, min(width, sheet.get_width()), height))
        starter = pygame.Surface(self.canvas_size(definition), pygame.SRCALPHA)
        starter.blit(pygame.transform.scale(frame, starter.get_size()), (0, 0))
        return starter

    def guide(self, definition: InteractableDefinition) -> pygame.Surface:
        """What is traced over: the tiles the object stands on, and the room it has above them."""
        size = self.canvas_size(definition)
        guide = pygame.Surface(size, pygame.SRCALPHA)
        tile = TILE_SIZE * OBJECT_DETAIL
        ground = pygame.Rect(0, size[1] - definition.height * tile, size[0], definition.height * tile)
        if ground.top > 0:
            guide.fill(ABOVE_FILL, pygame.Rect(0, 0, size[0], ground.top))
        guide.fill(GROUND_FILL, ground)
        for x in range(0, size[0] + 1, tile):
            pygame.draw.line(guide, PALETTE["ember"], (min(x, size[0] - 1), ground.top), (min(x, size[0] - 1), size[1] - 1))
        for y in range(ground.top, size[1] + 1, tile):
            pygame.draw.line(guide, PALETTE["ember"], (0, min(y, size[1] - 1)), (size[0] - 1, min(y, size[1] - 1)))
        pygame.draw.rect(guide, PALETTE["steel"], guide.get_rect(), 1)
        return guide

    def forget(self, kind: str) -> None:
        """Have a kind's drawing read again, as after it has been drawn anew."""
        if self.illustrations is not None:
            self.illustrations.forget(object_art_path(kind))
