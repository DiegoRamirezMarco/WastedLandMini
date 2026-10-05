"""Chooses the music for what is going on in the settlement. It reads the simulation and changes nothing."""

import json
from dataclasses import dataclass, field
from pathlib import Path

from simulation.world import SimulationWorld

# The moods the game knows how to tell apart, most pressing first.
TENSION = "tension"
STORM = "storm"
NIGHT = "night"
DAY = "day"
MOODS = (TENSION, STORM, NIGHT, DAY)
# A decision at least this urgent is worth changing the music for.
TENSE_URGENCY = 60


@dataclass(frozen=True)
class MusicSettings:
    """Which track plays for each mood, and the hours that count as night."""

    tracks: dict[str, str] = field(default_factory=dict)
    night_hours: tuple[int, int] = (21, 6)


def load_music_settings(path: Path) -> MusicSettings:
    """Read the music section of the audio file. A missing or broken file means no music."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return MusicSettings()
    music = data.get("music", {}) if isinstance(data, dict) else {}
    if not isinstance(music, dict):
        return MusicSettings()
    tracks = music.get("tracks", {})
    hours = music.get("night_hours", (21, 6))
    try:
        night = (int(hours[0]), int(hours[1]))
    except (TypeError, ValueError, IndexError):
        night = (21, 6)
    return MusicSettings(
        tracks={str(mood): str(track) for mood, track in tracks.items()} if isinstance(tracks, dict) else {},
        night_hours=night,
    )


def mood_of(world: SimulationWorld, settings: MusicSettings) -> str:
    """The mood of the settlement right now: trouble first, then the weather, then the hour."""
    for resident in world.residents.values():
        activity = resident.activity
        exchange = world.registries.interactions.get(activity.action) if activity and activity.using else None
        if exchange is not None and exchange.damage is not None:
            return TENSION
    if any(d.crisis is not None and d.crisis.urgency >= TENSE_URGENCY for d in world.decisions.values()):
        return TENSION
    if world.happenings.is_stormy(world):
        return STORM
    start, end = settings.night_hours
    hour = world.clock.hour
    at_night = start <= hour < end if start <= end else hour >= start or hour < end
    return NIGHT if at_night else DAY


def track_for(world: SimulationWorld, settings: MusicSettings) -> str | None:
    """Name of the track to play now, or None if the mood has none."""
    return settings.tracks.get(mood_of(world, settings))
