"""Builds a resident's face from stacked layers, or from custom PNGs when a pack provides them."""

from collections import Counter

import pygame

from graphics.assets import AssetStore
from graphics.palette import PALETTE

FACE_SIZE = (64, 64)
# Size of a face when it stands for a resident on a map seen from afar.
MARKER_SIZE = (16, 16)
EXPRESSIONS = ("neutral", "angry", "sad", "happy")
DEFAULT_EXPRESSION = "neutral"
# Bottom layer first. `{id}` layers belong to one resident, `{expression}` layers are shared.
LAYERS = (
    "faces/base/{id}.png",
    "faces/mouth/{expression}.png",
    "faces/eyes/{expression}.png",
    "faces/brows/{expression}.png",
    "faces/hair/{id}.png",
)


def _reduced(face: pygame.Surface, size: tuple[int, int]) -> pygame.Surface:
    """Shrink a face by a whole number, keeping its exact colours, and outline what is left of it."""
    block_width, block_height = face.get_width() // size[0], face.get_height() // size[1]
    small = pygame.Surface(size, pygame.SRCALPHA)
    for y in range(size[1]):
        for x in range(size[0]):
            # Each pixel takes the colour that fills most of the block it replaces.
            block = Counter(
                tuple(face.get_at((x * block_width + dx, y * block_height + dy)))
                for dy in range(block_height)
                for dx in range(block_width)
            )
            color = block.most_common(1)[0][0]
            if color[3]:
                small.set_at((x, y), color)
    # The outline of the full-size face is too thin to survive, so it is drawn again.
    outlined = small.copy()
    for y in range(size[1]):
        for x in range(size[0]):
            if small.get_at((x, y))[3]:
                continue
            beside = ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1))
            if any(small.get_rect().collidepoint(point) and small.get_at(point)[3] for point in beside):
                outlined.set_at((x, y), PALETTE["ink"])
    return outlined


class FaceRenderer:
    def __init__(self, assets: AssetStore, custom: AssetStore | None = None) -> None:
        self._assets = assets
        self._custom = custom
        self._cache: dict[tuple[str, str], pygame.Surface] = {}
        self._markers: dict[tuple[str, str], pygame.Surface] = {}

    def face(self, face_id: str, expression: str = DEFAULT_EXPRESSION) -> pygame.Surface:
        """Return the 64×64 face of `face_id` showing `expression`."""
        if expression not in EXPRESSIONS:
            expression = DEFAULT_EXPRESSION
        key = (face_id, expression)
        if key not in self._cache:
            self._cache[key] = self._custom_face(face_id, expression) or self._layered_face(face_id, expression)
        return self._cache[key]

    def marker(self, face_id: str, expression: str = DEFAULT_EXPRESSION) -> pygame.Surface:
        """Return the same face at `MARKER_SIZE`, small enough to mark a resident on the map."""
        if expression not in EXPRESSIONS:
            expression = DEFAULT_EXPRESSION
        key = (face_id, expression)
        if key not in self._markers:
            self._markers[key] = _reduced(self.face(face_id, expression), MARKER_SIZE)
        return self._markers[key]

    def _layered_face(self, face_id: str, expression: str) -> pygame.Surface:
        face = pygame.Surface(FACE_SIZE, pygame.SRCALPHA)
        for layer in LAYERS:
            path = layer.replace("{id}", face_id).replace("{expression}", expression)
            face.blit(self._assets.image(path, size=FACE_SIZE), (0, 0))
        return face

    def _custom_face(self, face_id: str, expression: str) -> pygame.Surface | None:
        """A custom face for this expression, else the pack's neutral or only image, else None."""
        if self._custom is None:
            return None
        folder = f"faces/{face_id}"
        available = self._custom.files(folder)
        for name in (f"{expression}.png", f"{DEFAULT_EXPRESSION}.png"):
            if name in available:
                return self._custom.image(f"{folder}/{name}", size=FACE_SIZE)
        if len(available) == 1:
            return self._custom.image(f"{folder}/{available[0]}", size=FACE_SIZE)
        return None
