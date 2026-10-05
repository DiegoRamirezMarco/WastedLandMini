"""Plays sound effects in reaction to domain events. Never required: the game runs fine without sound."""

import json
import logging
from collections.abc import Iterable
from pathlib import Path

import pygame

from simulation.events.event import DomainEvent

logger = logging.getLogger(__name__)

SAMPLE_RATE = 22050
# Real milliseconds that must pass between two sounds, so fast-forward does not become a racket.
MIN_GAP_MS = 150


def load_sound_map(path: Path) -> dict[str, str]:
    """Read which sound each event type plays. A missing or broken file means no sounds."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    events = data.get("events", {}) if isinstance(data, dict) else {}
    return {str(event_type): str(sound) for event_type, sound in events.items()} if isinstance(events, dict) else {}


class AudioManager:
    def __init__(self, sounds_dir: Path, event_sounds: dict[str, str]) -> None:
        self.event_sounds = dict(event_sounds)
        self.muted = False
        self.available = False
        self._sounds: dict[str, pygame.mixer.Sound] = {}
        self._last_played_at = -MIN_GAP_MS
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init(frequency=SAMPLE_RATE, size=-16, channels=1, buffer=512)
            self.available = True
        except pygame.error as error:
            logger.warning("Sound is off: %s", error)
            return
        for name in sorted(set(self.event_sounds.values())):
            try:
                self._sounds[name] = pygame.mixer.Sound(str(sounds_dir / f"{name}.wav"))
            except (pygame.error, OSError) as error:
                logger.warning("Sound %s could not be loaded: %s", name, error)

    def toggle_mute(self) -> bool:
        self.muted = not self.muted
        return self.muted

    def play(self, name: str) -> bool:
        """Play a sound by name. Returns whether it actually played."""
        sound = self._sounds.get(name)
        now = pygame.time.get_ticks()
        if sound is None or self.muted or now - self._last_played_at < MIN_GAP_MS:
            return False
        sound.play()
        self._last_played_at = now
        return True

    def sound_for(self, events: Iterable[DomainEvent]) -> str | None:
        """The sound of the most important of these events that has one."""
        with_sound = [event for event in events if event.event_type in self.event_sounds]
        if not with_sound:
            return None
        return self.event_sounds[max(with_sound, key=lambda event: event.importance).event_type]

    def on_events(self, events: Iterable[DomainEvent]) -> str | None:
        """React to what the simulation emitted. Returns the sound chosen, played or not."""
        name = self.sound_for(events)
        if name is not None:
            self.play(name)
        return name
