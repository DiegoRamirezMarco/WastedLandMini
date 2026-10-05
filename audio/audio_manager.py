"""Plays sound effects in reaction to domain events, and music under them.

Never required: the game runs fine without sound.
"""

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
# Music stays under the sound effects, and one track gives way to the next over this long.
MUSIC_VOLUME = 0.45
MUSIC_FADE_MS = 1500


def load_sound_map(path: Path) -> dict[str, str]:
    """Read which sound each event type plays. A missing or broken file means no sounds."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    events = data.get("events", {}) if isinstance(data, dict) else {}
    return {str(event_type): str(sound) for event_type, sound in events.items()} if isinstance(events, dict) else {}


class AudioManager:
    def __init__(
        self,
        sounds_dir: Path,
        event_sounds: dict[str, str],
        music_dir: Path | None = None,
        tracks: Iterable[str] = (),
    ) -> None:
        self.event_sounds = dict(event_sounds)
        self.muted = False
        self.available = False
        # Name of the track that is playing, or would be if there were sound.
        self.track: str | None = None
        self._sounds: dict[str, pygame.mixer.Sound] = {}
        self._music: dict[str, pygame.mixer.Sound] = {}
        self._music_channel: pygame.mixer.Channel | None = None
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
        for name in sorted(set(tracks)) if music_dir is not None else []:
            try:
                self._music[name] = pygame.mixer.Sound(str(music_dir / f"{name}.wav"))
            except (pygame.error, OSError) as error:
                logger.warning("Music %s could not be loaded: %s", name, error)
        if self._music:
            # One channel is kept for the music, so that sound effects never cut it off.
            pygame.mixer.set_reserved(1)
            self._music_channel = pygame.mixer.Channel(0)
            self._music_channel.set_volume(MUSIC_VOLUME)

    def toggle_mute(self) -> bool:
        self.muted = not self.muted
        if self._music_channel is not None:
            self._music_channel.set_volume(0.0 if self.muted else MUSIC_VOLUME)
        return self.muted

    def set_music(self, name: str | None) -> bool:
        """Change to a track, fading the one before it out, or to silence. Returns whether anything changed."""
        if name == self.track:
            return False
        self.track = name
        channel = self._music_channel
        if channel is None:
            return True
        channel.fadeout(MUSIC_FADE_MS)
        track = self._music.get(name or "")
        if track is not None:
            # It waits its turn behind the fade, and then goes round and round.
            channel.queue(track) if channel.get_busy() else channel.play(track, loops=-1, fade_ms=MUSIC_FADE_MS)
        return True

    def keep_music_going(self) -> None:
        """Start the current track again if it has run out. A queued track plays once, so it needs this."""
        channel, track = self._music_channel, self._music.get(self.track or "")
        if channel is not None and track is not None and not channel.get_busy():
            channel.play(track, loops=-1)

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
