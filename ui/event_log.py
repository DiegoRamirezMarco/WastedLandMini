"""Recent domain events as text: one line for the latest, a panel for the history."""

from collections import deque
from collections.abc import Iterable

import pygame

from graphics.font import LINE_HEIGHT, BitmapFont
from graphics.palette import PALETTE, Color
from simulation.events.event import DomainEvent
from ui.labels import format_time
from ui.panel import draw_panel

HISTORY = 200
PADDING = 5


class EventFeed:
    def __init__(self, noteworthy_from: int, intervention_from: int) -> None:
        self._events: deque[DomainEvent] = deque(maxlen=HISTORY)
        self._noteworthy_from = noteworthy_from
        self._intervention_from = intervention_from

    def add(self, events: Iterable[DomainEvent]) -> None:
        self._events.extend(events)

    def latest(self) -> DomainEvent | None:
        return self._events[-1] if self._events else None

    def recent(self, count: int) -> list[DomainEvent]:
        return list(self._events)[-count:]

    def color(self, event: DomainEvent) -> Color:
        """Events that matter more stand out more."""
        if event.importance >= self._intervention_from:
            return PALETTE["ember"]
        if event.importance >= self._noteworthy_from:
            return PALETTE["lamp"]
        return PALETTE["dust"]

    def draw_ticker(
        self, target: pygame.Surface, font: BitmapFont, position: tuple[int, int], width: int
    ) -> None:
        event = self.latest()
        if event is None:
            return
        line = font.truncate(f"{format_time(event.timestamp)}  {event.text}", width)
        font.draw(target, line, position, self.color(event))

    def draw_panel(self, target: pygame.Surface, font: BitmapFont, rect: pygame.Rect, title: str = "Registro") -> None:
        draw_panel(target, rect)
        x, y = rect.x + PADDING, rect.y + PADDING
        font.draw(target, title, (x, y), PALETTE["paper"])
        y += LINE_HEIGHT + 2
        events = self.recent((rect.bottom - PADDING - y) // LINE_HEIGHT)
        if not events:
            font.draw(target, "Todavía no ha pasado nada.", (x, y), PALETTE["stone"])
        for event in events:
            line = f"{format_time(event.timestamp, with_day=True)}  {event.text}"
            font.draw(target, font.truncate(line, rect.width - PADDING * 2), (x, y), self.color(event))
            y += LINE_HEIGHT
