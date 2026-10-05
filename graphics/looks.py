"""Which of the game's own looks someone is drawn with when they have no art under their own ID."""

import zlib
from collections.abc import Callable

from graphics.assets import AssetStore

BODIES_FOLDER = "sprites/bodies"


class Looks:
    def __init__(self, assets: AssetStore, chosen: Callable[[str], str | None] | None = None) -> None:
        # The looks there are: every body the game comes with, by ID. Faces go by the same IDs.
        self.known = [name.removesuffix(".png") for name in assets.files(BODIES_FOLDER)]
        # Asked for the look someone was given, if they were given one.
        self.chosen = chosen

    def of(self, body_id: str) -> str:
        """The look to draw someone with: the one they were given, else their own, else one that
        is always the same for the same ID, so that nobody is ever a placeholder."""
        given = self.chosen(body_id) if self.chosen is not None else None
        if given in self.known:
            return given
        if body_id in self.known or not self.known:
            return body_id
        return self.known[zlib.crc32(body_id.encode("utf-8")) % len(self.known)]
