"""Where the settlement's coin is drawn: one picture, shown wherever something is counted in it."""

from collections.abc import Callable
from pathlib import Path

import pygame

from graphics.coin_art import COIN_PAPER, CoinArt, coin_path
from graphics.font import BitmapFont
from graphics.palette import PALETTE
from graphics.screen_layers import ScreenLayers
from scenes.object_editor import DRAWING_AT, PREVIEW, ObjectEditor
from simulation.world import SimulationWorld

SAVED_TEXT = "Guardado: así es ya la moneda"
PREVIEW_HEADING = "Así se ve en la barra y en el panel"
# The sizes it is shown at beside the paper, in pixels of the window: in a panel, and in the bar.
SHOWN_AT = (48, 22)
# Canvas pixels to one of the paper's.
ZOOM = 3
LEGEND = ((None, "El círculo es lo que llena una moneda. Debajo, la del juego como ejemplo"),)
NOTES_TEXT = (
    "Es la moneda del asentamiento: se ve junto al fondo en la barra de arriba, en su panel y donde se cobra o se paga.",
    "Se enseña muy pequeña. Formas grandes y pocos colores se leen mejor que un dibujo fino.",
    "Lo que quede sin pintar deja ver lo de detrás: no hace falta que sea redonda.",
    "Arte de partida pone la del juego sobre el papel. Ctrl+Z deshace, Esc vuelve sin guardar.",
)


class CoinEditor(ObjectEditor):
    """Draw the coin of a currency. Simulation time stands still while it is open."""

    def __init__(
        self,
        canvas: pygame.Surface,
        world: SimulationWorld,
        font: BitmapFont,
        layers: ScreenLayers,
        root: Path,
        coins: CoinArt,
        on_saved: Callable[[str], None] | None = None,
    ) -> None:
        # It draws as an object is drawn, on a paper of its own and with nothing of the opening in it.
        super().__init__(canvas, world, font, layers, root, None, on_saved)  # type: ignore[arg-type]
        self.coins = coins
        self.legend = LEGEND
        self.preview_heading = PREVIEW_HEADING
        self.notes = NOTES_TEXT

    def open(self, currency_id: str | None) -> None:
        """Start drawing the coin of a currency, from what has been drawn of it so far."""
        made = self.world.trading.currency
        self.kind = currency_id if made is not None and made.currency_id == currency_id else None
        self.closed = self.kind is None
        self.notice = ""
        self._undo = []
        self._stroke = None
        self._draft = None
        if self.kind is None:
            return
        self.zoom = ZOOM
        self.area = pygame.Rect(DRAWING_AT, (COIN_PAPER[0] * self.zoom, COIN_PAPER[1] * self.zoom))
        self.drawing = pygame.Surface(COIN_PAPER, pygame.SRCALPHA)
        kept = self.coins.drawing(self.kind)
        if kept is not None:
            self.drawing.blit(kept, (0, 0))
        self.guide_picture = self.coins.guide()

    def starter(self) -> None:
        """Put the game's own coin on the paper, to be drawn over."""
        if self.kind is not None:
            self._remember()
            self.drawing = self.coins.starter()

    def save(self) -> bool:
        """Write the drawing where the game looks for it. Returns whether it worked."""
        if self.kind is None:
            return False
        try:
            path = self.root / coin_path(self.kind)
            path.parent.mkdir(parents=True, exist_ok=True)
            pygame.image.save(self.drawing, str(path))
        except (OSError, pygame.error):
            self.notice = "No se pudo guardar"
            return False
        self.coins.forget(self.kind)
        if self.on_saved is not None:
            self.on_saved(self.kind)
        self.notice = SAVED_TEXT
        return True

    def _title(self) -> str:
        made = self.world.trading.currency
        return f"Dibujar la moneda: {made.name}" if made is not None else "Dibujar la moneda"

    def _lesson(self):
        return None

    def _show_preview(self, screen: pygame.Surface) -> None:
        """The coin on the dark of a panel, at the sizes the window shows it."""
        place = self.layers.on_screen(PREVIEW)
        screen.fill(PALETTE["shadow"], place)
        x = place.x + 24
        for side in SHOWN_AT:
            picture = pygame.transform.smoothscale(self.drawing, (side, side))
            screen.blit(picture, (x, place.centery - side // 2))
            x += side + 32
