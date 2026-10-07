"""Plays sound in reaction to what happens: effects for events, for what is being done in view
and for the player's own clicks, ambience that goes round under them, and music under it all.

Never required: the game runs fine without sound. Every sound is a file with a name, and one
of the same name in the folder for the player's own sounds is played in place of the game's.
"""

import json
import logging
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path

import pygame

from simulation.events.event import DomainEvent

logger = logging.getLogger(__name__)

SAMPLE_RATE = 22050
# Real milliseconds that must pass between two sounds, so fast-forward does not become a racket.
MIN_GAP_MS = 150
# The same for the player's own clicks, which come one at a time anyway.
INTERFACE_GAP_MS = 40
# Music stays under the sound effects, and one track gives way to the next over this long.
MUSIC_VOLUME = 0.45
MUSIC_FADE_MS = 1500
# How fast ambience comes up and dies away, as a share of all the way in a second.
AMBIENCE_RATE = 0.8
# The folder ambience is kept in, beside the effects.
AMBIENCE_FOLDER = "ambience"
# What a sound file may be.
SOUND_SUFFIXES = (".wav", ".ogg")
# Where the player's own sounds go: any file here with the name of one of the game's is played instead.
SOUNDS_DIR = Path(__file__).resolve().parent.parent / "sounds"


@dataclass(frozen=True)
class ActionSound:
    """A sound that goes with something being done in view, for as long as it is: how often."""

    sound: str
    every_ms: int = 600


@dataclass(frozen=True)
class AmbienceRule:
    """When a piece of ambience is heard, and how loud at most.

    `when` is `always`, `day`, `night`, `storm`, `talk` (people talking in view) or `near`
    (something of a `kind` in view).
    """

    when: str = "always"
    volume: float = 0.3
    kind: str | None = None
    # Whether it is only heard while the settlement has power, as what runs on it is.
    powered: bool = False


@dataclass(frozen=True)
class SoundSettings:
    """What sounds, and when: everything in the audio file but the music."""

    events: dict[str, str] = field(default_factory=dict)
    interface: dict[str, str] = field(default_factory=dict)
    actions: dict[str, ActionSound] = field(default_factory=dict)
    ambience: dict[str, AmbienceRule] = field(default_factory=dict)
    volumes: dict[str, float] = field(default_factory=dict)

    def names(self) -> set[str]:
        """Every effect any of it asks for."""
        return {*self.events.values(), *self.interface.values(), *(each.sound for each in self.actions.values())}


WHENS = ("always", "day", "night", "storm", "talk", "near")
DEFAULT_VOLUMES = {"effects": 1.0, "actions": 0.4, "interface": 0.6, "ambience": 1.0}


def _section(data: object, name: str) -> dict:
    section = data.get(name, {}) if isinstance(data, dict) else {}
    return section if isinstance(section, dict) else {}


def load_sound_map(path: Path) -> dict[str, str]:
    """Read which sound each event type plays. A missing or broken file means no sounds."""
    return load_sound_settings(path).events


def load_sound_settings(path: Path) -> SoundSettings:
    """Read everything that sounds from the audio file. A missing or broken file means silence,
    and so does any part of it that makes no sense."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return SoundSettings()
    actions = {}
    for action, rule in _section(data, "actions").items():
        try:
            actions[str(action)] = ActionSound(str(rule["sound"]), max(50, int(rule.get("every_ms", 600))))
        except (TypeError, KeyError, ValueError):
            continue
    ambience = {}
    for name, rule in _section(data, "ambience").items():
        try:
            when = str(rule.get("when", "always"))
            if when not in WHENS:
                continue
            kind = str(rule["kind"]) if rule.get("kind") else None
            ambience[str(name)] = AmbienceRule(
                when, max(0.0, min(1.0, float(rule.get("volume", 0.3)))), kind, bool(rule.get("powered", False))
            )
        except (TypeError, AttributeError, ValueError):
            continue
    volumes = dict(DEFAULT_VOLUMES)
    for name, level in _section(data, "volumes").items():
        try:
            volumes[str(name)] = max(0.0, min(1.0, float(level)))
        except (TypeError, ValueError):
            continue
    return SoundSettings(
        events={str(event_type): str(sound) for event_type, sound in _section(data, "events").items()},
        interface={str(name): str(sound) for name, sound in _section(data, "interface").items()},
        actions=actions,
        ambience=ambience,
        volumes=volumes,
    )


def find_sound(name: str, folders: Sequence[Path]) -> Path | None:
    """The file for a sound: the first there is, looking in each folder in turn."""
    for folder in folders:
        for suffix in SOUND_SUFFIXES:
            path = folder / f"{name}{suffix}"
            if path.is_file():
                return path
    return None


class AudioManager:
    def __init__(
        self,
        sounds_dir: Path,
        event_sounds: Mapping[str, str] | SoundSettings,
        music_dir: Path | None = None,
        tracks: Iterable[str] = (),
        own_dir: Path | None = None,
    ) -> None:
        settings = event_sounds if isinstance(event_sounds, SoundSettings) else SoundSettings(events=dict(event_sounds))
        self.settings = settings
        self.event_sounds = dict(settings.events)
        self.volumes = {**DEFAULT_VOLUMES, **settings.volumes}
        self.muted = False
        self.available = False
        # Name of the track that is playing, or would be if there were sound.
        self.track: str | None = None
        # How loud each piece of ambience is right now, and how loud it is on its way to being.
        self.ambience_levels: dict[str, float] = {name: 0.0 for name in settings.ambience}
        self._ambience_wanted: dict[str, float] = dict(self.ambience_levels)
        # Which of the sounds on offer came from the player's own folder.
        self.own: set[str] = set()
        self._sounds: dict[str, pygame.mixer.Sound] = {}
        self._music: dict[str, pygame.mixer.Sound] = {}
        self._ambience: dict[str, pygame.mixer.Sound] = {}
        self._ambience_channels: dict[str, pygame.mixer.Channel] = {}
        self._music_channel: pygame.mixer.Channel | None = None
        self._last_played_at = -MIN_GAP_MS
        self._last_click_at = -INTERFACE_GAP_MS
        # Real milliseconds until each sound that goes with something being done may come again.
        self._action_wait: dict[str, float] = {}
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init(frequency=SAMPLE_RATE, size=-16, channels=1, buffer=512)
            self.available = True
        except pygame.error as error:
            logger.warning("Sound is off: %s", error)
            return
        # The player's own come first: a file there is played in place of the game's.
        folders = [folder for folder in (own_dir, sounds_dir) if folder is not None]
        for name in sorted(settings.names()):
            sound = self._load(name, folders)
            if sound is not None:
                self._sounds[name] = sound
        for name in sorted(settings.ambience):
            sound = self._load(name, [folder / AMBIENCE_FOLDER for folder in folders])
            if sound is not None:
                self._ambience[name] = sound
        for name in sorted(set(tracks)) if music_dir is not None else []:
            try:
                self._music[name] = pygame.mixer.Sound(str(music_dir / f"{name}.wav"))
            except (pygame.error, OSError) as error:
                logger.warning("Music %s could not be loaded: %s", name, error)
        # A channel is kept for the music and one for each piece of ambience, so that sound
        # effects never cut them off.
        reserved = (1 if self._music else 0) + len(self._ambience)
        if reserved:
            pygame.mixer.set_num_channels(max(pygame.mixer.get_num_channels(), reserved + 8))
            pygame.mixer.set_reserved(reserved)
        index = 0
        if self._music:
            self._music_channel = pygame.mixer.Channel(index)
            self._music_channel.set_volume(MUSIC_VOLUME)
            index += 1
        for name in self._ambience:
            self._ambience_channels[name] = pygame.mixer.Channel(index)
            index += 1

    def _load(self, name: str, folders: Sequence[Path]) -> pygame.mixer.Sound | None:
        path = find_sound(name, folders)
        if path is None:
            logger.warning("Sound %s could not be found", name)
            return None
        try:
            sound = pygame.mixer.Sound(str(path))
        except (pygame.error, OSError) as error:
            logger.warning("Sound %s could not be loaded: %s", name, error)
            return None
        if len(folders) > 1 and path.parent == folders[0]:
            self.own.add(name)
        return sound

    def toggle_mute(self) -> bool:
        self.muted = not self.muted
        if self._music_channel is not None:
            self._music_channel.set_volume(0.0 if self.muted else MUSIC_VOLUME)
        self._set_ambience_volumes()
        return self.muted

    # ----- music -----

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

    # ----- effects -----

    def play(self, name: str, volume: float | None = None) -> bool:
        """Play a sound by name. Returns whether it actually played."""
        sound = self._sounds.get(name)
        now = pygame.time.get_ticks()
        if sound is None or self.muted or now - self._last_played_at < MIN_GAP_MS:
            return False
        sound.set_volume(self.volumes["effects"] if volume is None else volume)
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

    def interface(self, what: str) -> str | None:
        """Sound something the player did with their own hand: a `click`, a panel that opens or
        shuts, somebody selected, an order given or something refused. Returns the sound it is,
        played or not, or None for something that has none."""
        name = self.settings.interface.get(what)
        sound = self._sounds.get(name or "")
        now = pygame.time.get_ticks()
        if name is None:
            return None
        if sound is not None and not self.muted and now - self._last_click_at >= INTERFACE_GAP_MS:
            sound.set_volume(self.volumes["interface"])
            sound.play()
            self._last_click_at = now
        return name

    def on_actions(self, actions: Iterable[str], dt: float) -> list[str]:
        """Sound what is being done in view: each thing with a sound of its own is heard again
        every so often for as long as somebody is at it. Returns the sounds that came due."""
        elapsed = dt * 1000.0
        for sound in list(self._action_wait):
            self._action_wait[sound] -= elapsed
        due: list[str] = []
        for action in dict.fromkeys(actions):
            rule = self.settings.actions.get(action)
            if rule is None or self._action_wait.get(rule.sound, 0.0) > 0.0:
                continue
            self._action_wait[rule.sound] = float(rule.every_ms)
            due.append(rule.sound)
            sound = self._sounds.get(rule.sound)
            if sound is not None and not self.muted:
                sound.set_volume(self.volumes["actions"])
                sound.play()
        return due

    # ----- ambience -----

    def set_ambience(self, wanted: Mapping[str, float]) -> None:
        """Say how much of each piece of ambience there is to be heard, from 0 to 1 of how
        loud it gets. It comes up and dies away by itself: see `update`."""
        for name in self._ambience_wanted:
            rule = self.settings.ambience[name]
            self._ambience_wanted[name] = max(0.0, min(1.0, float(wanted.get(name, 0.0)))) * rule.volume

    def update(self, dt: float) -> None:
        """Let real time pass: ambience moves towards how loud it is wanted."""
        step = AMBIENCE_RATE * dt
        for name, wanted in self._ambience_wanted.items():
            level = self.ambience_levels[name]
            self.ambience_levels[name] = min(wanted, level + step) if wanted > level else max(wanted, level - step)
        self._set_ambience_volumes()

    def _set_ambience_volumes(self) -> None:
        for name, channel in self._ambience_channels.items():
            level = 0.0 if self.muted else self.ambience_levels[name] * self.volumes["ambience"]
            if level > 0.0 and not channel.get_busy():
                channel.play(self._ambience[name], loops=-1)
            elif level <= 0.0 and channel.get_busy():
                channel.stop()
            channel.set_volume(level)
