"""Chooses what is heard of the settlement: the hour, the weather, and what is in view. It reads
the simulation and changes nothing."""

from collections.abc import Collection, Mapping

from audio.audio_manager import AmbienceRule
from audio.music import MusicSettings
from simulation.world import SimulationWorld


def at_night(world: SimulationWorld, hours: tuple[int, int]) -> bool:
    start, end = hours
    hour = world.clock.hour
    return start <= hour < end if start <= end else hour >= start or hour < end


def talking(world: SimulationWorld, in_view: Collection[str]) -> bool:
    """Whether anybody in view is in the middle of an exchange with somebody."""
    for resident_id in in_view:
        resident = world.residents.get(resident_id)
        activity = resident.activity if resident is not None else None
        if activity is not None and activity.using and activity.partner_id is not None:
            return True
    return False


def ambience_for(
    world: SimulationWorld,
    rules: Mapping[str, AmbienceRule],
    music: MusicSettings,
    kinds_in_view: Collection[str] = (),
    residents_in_view: Collection[str] = (),
) -> dict[str, float]:
    """How much of each piece of ambience there is to be heard right now, from 0 for none to 1.

    A storm drowns the day and the night out. Something that gives a sound of its own is heard
    while it is in view, and what runs on power only while there is some.
    """
    stormy = world.happenings.is_stormy(world)
    night = at_night(world, music.night_hours)
    heard: dict[str, float] = {}
    for name, rule in rules.items():
        if rule.when == "always":
            on = True
        elif rule.when == "storm":
            on = stormy
        elif rule.when == "day":
            on = not night and not stormy
        elif rule.when == "night":
            on = night and not stormy
        elif rule.when == "talk":
            on = talking(world, residents_in_view)
        else:
            on = rule.kind is not None and rule.kind in kinds_in_view
        if rule.powered and not world.has_power():
            on = False
        heard[name] = 1.0 if on else 0.0
    return heard


def actions_in_view(world: SimulationWorld, residents_in_view: Collection[str]) -> list[str]:
    """What those in view are in the middle of doing, as the names of what they do."""
    doing = []
    for resident_id in residents_in_view:
        resident = world.residents.get(resident_id)
        activity = resident.activity if resident is not None else None
        if resident is None or resident.away or activity is None or not activity.using:
            continue
        doing.append(activity.action)
    return doing
