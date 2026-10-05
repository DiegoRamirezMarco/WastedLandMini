"""What is drawn at the resolution of the window: under the canvas, where the canvas lets it show, and over it."""

from collections.abc import Callable

import pygame

from graphics.palette import PALETTE

Draw = Callable[[pygame.Surface], None]
TRANSPARENT = (0, 0, 0, 0)


class ScreenLayers:
    """Collects, each frame, the pictures that go straight on the window.

    Scenes go on drawing on the canvas in its own coordinates. Where an illustration belongs, they
    leave the canvas clear and say here what goes underneath.
    """

    def __init__(self, scale: int) -> None:
        # Window pixels to a canvas pixel.
        self.scale = scale
        self._under: list[Draw] = []

    def clear(self) -> None:
        self._under = []

    @property
    def active(self) -> bool:
        return bool(self._under)

    def on_screen(self, canvas_rect: pygame.Rect) -> pygame.Rect:
        """Where a part of the canvas falls on the window."""
        scale = self.scale
        return pygame.Rect(canvas_rect.x * scale, canvas_rect.y * scale, canvas_rect.width * scale, canvas_rect.height * scale)

    def under(self, draw: Draw) -> None:
        """Have something drawn on the window before the canvas goes over it."""
        self._under.append(draw)

    def picture_under(self, picture: pygame.Surface, canvas_rect: pygame.Rect) -> None:
        """Put a picture, already at the size it takes on the window, under a part of the canvas."""
        corner = self.on_screen(canvas_rect).topleft
        self._under.append(lambda screen: screen.blit(picture, corner))

    def compose(self, screen: pygame.Surface, canvas: pygame.Surface) -> None:
        """Put the frame together on the window."""
        if not self._under and not canvas.get_flags() & pygame.SRCALPHA:
            pygame.transform.scale(canvas, screen.get_size(), screen)
            return
        screen.fill(PALETTE["ink"])
        for draw in self._under:
            draw(screen)
        screen.blit(pygame.transform.scale(canvas, screen.get_size()), (0, 0))
