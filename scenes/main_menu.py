"""The first screen: go on with a settlement, or start one. It asks; the game shell does."""

from dataclasses import dataclass

import pygame

from graphics.font import LINE_HEIGHT, BitmapFont
from graphics.palette import PALETTE
from graphics.screen_layers import ScreenLayers
from scenes.scene import canvas_position
from ui.panel import draw_panel

CONTINUE, NEW_GAME, DEMO, QUIT = "continue", "new", "demo", "quit"
TITLE = "WASTELAND MINIS"
TITLE_SCALE = 4
SUBTITLE = "Un asentamiento en el yermo, y la gente que lo levanta"
ENTRY_SIZE = (220, 24)
ENTRY_GAP = 6
ENTRIES_TOP = 190
RESUME_LABEL = "Volver a la partida"
NO_SAVE_NOTE = "No hay partida guardada"
RESUME_NOTE = "La partida en curso sigue donde la dejaste"
NEW_NOTE = "Un solar vacío, y un tutorial que lo llena paso a paso"
DEMO_NOTE = "Un asentamiento ya en marcha, con nueve habitantes"
QUIT_NOTE = "Lo que no se haya guardado con F5 se pierde"
OVERWRITE_NOTE = "Hay una partida en curso sin guardar: pulsa otra vez para dejarla"
HINT = "Flechas y Enter, o el ratón"


@dataclass(frozen=True)
class Entry:
    choice: str
    label: str
    note: str
    enabled: bool = True


class MainMenu:
    def __init__(self, canvas: pygame.Surface, font: BitmapFont, layers: ScreenLayers | None = None) -> None:
        self.canvas = canvas
        self.font = font
        self.layers = layers
        # What the player asked for. The game shell picks it up.
        self.requested: str | None = None
        # Whether a settlement is being played, and what the saved one is, in a few words. Set by the shell.
        self.in_session = False
        self.saved: str | None = None
        self.selected = 0
        self.notice = ""
        # A choice that would throw the settlement being played away is asked for twice.
        self._confirming: str | None = None

    def open(self, in_session: bool, saved: str | None, notice: str = "") -> None:
        self.in_session, self.saved, self.notice = in_session, saved, notice
        self.requested, self._confirming = None, None
        self.selected = next((index for index, entry in enumerate(self.entries) if entry.enabled), 0)

    @property
    def entries(self) -> list[Entry]:
        if self.in_session:
            first = Entry(CONTINUE, RESUME_LABEL, RESUME_NOTE)
        else:
            first = Entry(CONTINUE, "Continuar", self.saved or NO_SAVE_NOTE, enabled=self.saved is not None)
        return [
            first,
            Entry(NEW_GAME, "Partida nueva", NEW_NOTE),
            Entry(DEMO, "Asentamiento de ejemplo", DEMO_NOTE),
            Entry(QUIT, "Salir", QUIT_NOTE),
        ]

    def entry_rects(self) -> list[pygame.Rect]:
        left = (self.canvas.get_width() - ENTRY_SIZE[0]) // 2
        return [
            pygame.Rect(left, ENTRIES_TOP + index * (ENTRY_SIZE[1] + ENTRY_GAP), *ENTRY_SIZE)
            for index in range(len(self.entries))
        ]

    def choose(self, choice: str) -> None:
        """Ask for one of the entries, as a click or Enter on it does."""
        entry = next((each for each in self.entries if each.choice == choice), None)
        if entry is None or not entry.enabled:
            return
        if self.in_session and choice in (NEW_GAME, DEMO) and self._confirming != choice:
            self._confirming, self.notice = choice, OVERWRITE_NOTE
            return
        self.requested = choice

    def _move(self, by: int) -> None:
        entries = self.entries
        for _ in entries:
            self.selected = (self.selected + by) % len(entries)
            if entries[self.selected].enabled:
                break
        self._confirming, self.notice = None, ""

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_UP, pygame.K_w):
                self._move(-1)
            elif event.key in (pygame.K_DOWN, pygame.K_s):
                self._move(1)
            elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
                self.choose(self.entries[self.selected].choice)
            elif event.key == pygame.K_ESCAPE and self.in_session:
                self.requested = CONTINUE
        elif event.type == pygame.MOUSEMOTION:
            self._hover(canvas_position(event.pos))
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            position = canvas_position(event.pos)
            self._hover(position)
            for entry, rect in zip(self.entries, self.entry_rects()):
                if rect.collidepoint(position):
                    self.choose(entry.choice)

    def _hover(self, position: tuple[int, int]) -> None:
        for index, (entry, rect) in enumerate(zip(self.entries, self.entry_rects())):
            if rect.collidepoint(position) and entry.enabled and index != self.selected:
                self.selected = index
                self._confirming, self.notice = None, ""

    def update(self, dt: float) -> None:
        pass

    def render(self) -> None:
        if self.layers is not None:
            self.layers.clear()
        self.canvas.fill(PALETTE["ink"])
        width = self.canvas.get_width()
        title = self.font.render(TITLE, PALETTE["lamp"], TITLE_SCALE)
        self.canvas.blit(title, ((width - title.get_width()) // 2, 78))
        rule = pygame.Rect(0, 0, title.get_width(), 2)
        rule.midtop = (width // 2, 78 + title.get_height() + 6)
        pygame.draw.rect(self.canvas, PALETTE["rust"], rule)
        self.font.draw(
            self.canvas, SUBTITLE, ((width - self.font.width(SUBTITLE)) // 2, rule.bottom + 8), PALETTE["bone"]
        )

        entries, rects = self.entries, self.entry_rects()
        for index, (entry, rect) in enumerate(zip(entries, rects)):
            chosen = index == self.selected and entry.enabled
            draw_panel(self.canvas, rect, fill="shadow" if chosen else "ink", border="lamp" if chosen else "iron")
            color = PALETTE["paper" if chosen else "bone"] if entry.enabled else PALETTE["stone"]
            label = self.font.render(entry.label, color, 2 if chosen else 1)
            self.canvas.blit(label, label.get_rect(center=rect.center))

        # Under the entries, what the one in hand means, or what the game has to say.
        note = self.notice or entries[self.selected].note
        y = rects[-1].bottom + 14
        for line in self.font.wrap(note, 420):
            self.font.draw(self.canvas, line, ((width - self.font.width(line)) // 2, y), PALETTE["glow" if self.notice else "sand"])
            y += LINE_HEIGHT
        self.font.draw(
            self.canvas,
            HINT,
            ((width - self.font.width(HINT)) // 2, self.canvas.get_height() - LINE_HEIGHT - 8),
            PALETTE["dust"],
        )
