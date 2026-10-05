"""Draws resident bodies from their sprite sheets."""

import pygame

from graphics.assets import AssetStore

FRAME_SIZE = (16, 24)
FACINGS = ("down", "left", "right", "up")
FRAMES_PER_FACING = 3
SHEET_SIZE = (FRAME_SIZE[0] * FRAMES_PER_FACING, FRAME_SIZE[1] * len(FACINGS))


class CharacterRenderer:
    def __init__(self, assets: AssetStore) -> None:
        self._assets = assets

    def frame(self, body_id: str, facing: str = "down", step: int = 0) -> pygame.Surface:
        """Return one frame of a body sheet. A missing sheet yields a placeholder frame."""
        sheet = self._assets.image(f"sprites/residents/{body_id}.png", size=SHEET_SIZE)
        width, height = FRAME_SIZE
        column = step % FRAMES_PER_FACING
        return sheet.subsurface((column * width, FACINGS.index(facing) * height, width, height))

    def draw(
        self,
        target: pygame.Surface,
        body_id: str,
        feet: tuple[int, int],
        facing: str = "down",
        step: int = 0,
    ) -> None:
        """Draw a body with the bottom centre of its frame at `feet`."""
        width, height = FRAME_SIZE
        target.blit(self.frame(body_id, facing, step), (feet[0] - width // 2, feet[1] - height))
