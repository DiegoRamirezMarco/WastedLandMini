"""Which of the game's own looks someone is drawn with until somebody draws them."""

import zlib

from graphics.assets import AssetStore

BODIES_FOLDER = "sprites/bodies"


class Looks:
    def __init__(self, assets: AssetStore) -> None:
        # The looks there are: every body the game comes with, by ID. Faces go by the same IDs.
        self.known = [name.removesuffix(".png") for name in assets.files(BODIES_FOLDER)]

    def of(self, body_id: str) -> str:
        """The look to draw someone with: their own, or else one of the game's that is always the
        same for the same ID, so that nobody is a placeholder while they wait to be drawn."""
        if body_id in self.known or not self.known:
            return body_id
        return self.known[zlib.crc32(body_id.encode("utf-8")) % len(self.known)]
