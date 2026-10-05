"""Heads-up display of the global view: clock, speed and zoom buttons, event feed and the resident card."""

from collections.abc import Hashable, Iterable

import pygame

from graphics.font import BitmapFont
from graphics.item_icons import ItemIcons
from graphics.palette import PALETTE
from settings import SPEEDS
from simulation.events.event import DomainEvent
from simulation.world import SimulationWorld
from ui.button import Button
from ui.event_log import EventFeed
from ui.inventory_view import PANEL_WIDTH, container_panel_height, draw_container_panel
from ui.resident_card import CARD_WIDTH, card_height, draw_resident_card

HEADER_HEIGHT = 32
MARGIN = 6
BUTTONS_LEFT = 104
LOG_SIZE = (250, 168)

PAUSE_INTENT = ("pause",)
LOG_INTENT = ("log",)
ZOOM_OUT_INTENT = ("zoom", -1)
ZOOM_IN_INTENT = ("zoom", 1)
NOTICE_SECONDS = 3.0


def speed_intent(speed: int) -> tuple[str, int]:
    return ("speed", speed)


class Hud:
    def __init__(
        self, canvas: pygame.Surface, world: SimulationWorld, font: BitmapFont, icons: ItemIcons
    ) -> None:
        self.canvas = canvas
        self.world = world
        self.font = font
        self.icons = icons
        self.log_open = False
        # At most one of these is set: the resident or the container whose panel is showing.
        self.selected_id: str | None = None
        self.selected_container: str | None = None
        self._notice = ""
        self._notice_left = 0.0
        importance = world.registries.event_settings.get("importance", {})
        self.intervention_from = int(importance.get("noteworthy_max", 49)) + 1
        self.feed = EventFeed(
            noteworthy_from=int(importance.get("ambient_max", 29)) + 1,
            intervention_from=self.intervention_from,
        )

        self.pause_button = Button.at(font, BUTTONS_LEFT, 2, "II", PAUSE_INTENT)
        self.speed_buttons: list[Button] = []
        x = self.pause_button.rect.right + 4
        for speed in SPEEDS:
            button = Button.at(font, x, 2, f"x{speed}", speed_intent(speed))
            self.speed_buttons.append(button)
            x = button.rect.right + 2
        self.log_button = Button.at(font, 0, 2, "Registro", LOG_INTENT)
        self.log_button.rect.right = canvas.get_width() - MARGIN
        self.zoom_buttons = [
            Button.at(font, 0, 2, "-", ZOOM_OUT_INTENT),
            Button.at(font, 0, 2, "+", ZOOM_IN_INTENT),
        ]
        right = self.log_button.rect.left - 4
        for button in reversed(self.zoom_buttons):
            button.rect.right = right
            right = button.rect.left - 2
        self.hint_left = x + 8

    @property
    def buttons(self) -> list[Button]:
        return [self.pause_button, *self.speed_buttons, *self.zoom_buttons, self.log_button]

    def on_events(self, events: Iterable[DomainEvent]) -> None:
        self.feed.add(events)

    def notify(self, text: str) -> None:
        """Show a short message from the game itself, such as a save confirmation."""
        self._notice = text
        self._notice_left = NOTICE_SECONDS

    def update(self, dt: float) -> None:
        self._notice_left = max(0.0, self._notice_left - dt)

    def select_resident(self, resident_id: str | None) -> None:
        self.selected_id, self.selected_container = resident_id, None

    def select_container(self, container_id: str | None) -> None:
        self.selected_id, self.selected_container = None, container_id

    def click(self, position: tuple[int, int]) -> Hashable | None:
        """Return the intent of the button under `position`, if any."""
        return next((button.intent for button in self.buttons if button.contains(position)), None)

    def covers(self, position: tuple[int, int]) -> bool:
        """True if a HUD element is in front of the map at `position`."""
        if position[1] < HEADER_HEIGHT:
            return True
        panels = [self.card_rect(), self.container_rect()] + ([self.log_rect()] if self.log_open else [])
        return any(rect is not None and rect.collidepoint(position) for rect in panels)

    def log_rect(self) -> pygame.Rect:
        return pygame.Rect(
            self.canvas.get_width() - MARGIN - LOG_SIZE[0], HEADER_HEIGHT + MARGIN, *LOG_SIZE
        )

    def card_rect(self) -> pygame.Rect | None:
        if self.selected_id not in self.world.residents:
            return None
        height = card_height(self.world)
        return pygame.Rect(MARGIN, self.canvas.get_height() - MARGIN - height, CARD_WIDTH, height)

    def container_rect(self) -> pygame.Rect | None:
        inventory = self.world.containers.get(self.selected_container or "")
        if inventory is None:
            return None
        height = container_panel_height(inventory)
        return pygame.Rect(MARGIN, self.canvas.get_height() - MARGIN - height, PANEL_WIDTH, height)

    def render(self) -> None:
        clock = self.world.clock
        pygame.draw.rect(self.canvas, PALETTE["ink"], (0, 0, self.canvas.get_width(), HEADER_HEIGHT))
        self.font.draw(self.canvas, clock.label, (MARGIN, 3), PALETTE["paper"])
        self.pause_button.draw(self.canvas, self.font, active=clock.paused)
        for button, speed in zip(self.speed_buttons, SPEEDS):
            button.draw(self.canvas, self.font, active=clock.speed == speed and not clock.paused)
        for button in self.zoom_buttons:
            button.draw(self.canvas, self.font)
        self.log_button.draw(self.canvas, self.font, active=self.log_open)
        waiting = next(iter(self.world.decisions.values()), None)
        asker = self.world.residents.get(waiting.resident_id) if waiting is not None else None
        if self._notice_left > 0:
            self.font.draw(self.canvas, self._notice, (self.hint_left, 3), PALETTE["glow"])
        elif asker is not None:
            hint = f"! {asker.name} necesita consejo: TAB o clic"
            self.font.draw(self.canvas, hint, (self.hint_left, 3), PALETTE["lamp"])
        ticker_width = self.canvas.get_width() - MARGIN * 2
        self.feed.draw_ticker(self.canvas, self.font, (MARGIN, 18), ticker_width)

        if self.log_open:
            self.feed.draw_panel(self.canvas, self.font, self.log_rect())
        card = self.card_rect()
        if card is not None:
            resident = self.world.residents[self.selected_id]
            draw_resident_card(self.canvas, self.font, self.icons, card.topleft, self.world, resident)
        container = self.container_rect()
        if container is not None:
            draw_container_panel(
                self.canvas, self.font, self.icons, container.topleft, self.world, self.selected_container
            )
