"""What can happen to the settlement from outside, as data: who may turn up, and what may befall it."""

from dataclasses import dataclass, field
from typing import Any

# Kinds of world event the game knows how to carry out.
STRANGER = "stranger"
STOCK = "stock"
WEATHER = "weather"
SPOIL = "spoil"
KINDS = (STRANGER, STOCK, WEATHER, SPOIL)
# What whoever answers the gate can do about a stranger.
LET_IN = "let_in"
TURN_AWAY = "turn_away"
GATE_CHOICES = (LET_IN, TURN_AWAY)


@dataclass(frozen=True)
class Newcomer:
    """Someone who may come to the gate one day and ask to stay."""

    newcomer_id: str
    name: str
    age: int = 30
    personality: dict[str, float] = field(default_factory=dict)
    traits: tuple[str, ...] = ()


@dataclass(frozen=True)
class WorldEventDefinition:
    """One thing that can happen, how often, and what it does. Which fields matter depends on `kind`."""

    event_id: str
    kind: str
    # Chance of it happening on a day on which it can, spread over the hours it can happen in.
    chance_per_day: float
    hours: tuple[int, int] = (0, 24)
    # Days that must pass before it can happen again.
    cooldown_days: int = 1
    text: str = ""
    # stranger: the job whose worker on duty answers the gate.
    asks: str | None = None
    # stock: the kind of container that receives things, how many, and which, by weight.
    # spoil: the kind of container that loses them.
    container: str | None = None
    count: tuple[int, int] = (0, 0)
    items: tuple[tuple[str, float], ...] = ()
    # spoil: the category of item lost, and the share of each stack that goes.
    category: str | None = None
    fraction: float = 0.0
    # weather: how long it lasts, what it is called, what it does to nerves out of doors each
    # minute, and what is said when it passes.
    minutes: tuple[int, int] = (0, 0)
    name: str = ""
    stress_per_minute: float = 0.0
    end_text: str = ""
    # weather: how much likelier it makes whoever it catches outside the settlement to come back hurt.
    danger: float = 0.0
    # Hours between the event being on its way and its happening, in which a radio can give word of
    # it, and how the radio puts it: "anuncian ...". With no lead it comes unannounced.
    lead_hours: int = 0
    forecast: str = ""


@dataclass(frozen=True)
class WorldEventSettings:
    # Days at the start of a settlement in which nothing happens to it.
    quiet_days: int = 1
    newcomers: tuple[Newcomer, ...] = ()
    events: dict[str, WorldEventDefinition] = field(default_factory=dict)


@dataclass
class Upcoming:
    """A world event that is on its way and has not happened yet."""

    event_id: str
    # Game minute at which it happens.
    at: int
    # The fact a radio gave of it, once someone has heard it.
    fact_id: str | None = None


@dataclass
class Weather:
    """Weather the settlement is under right now. `event_id` names the event that brought it."""

    event_id: str
    # Game minute at which it passes.
    until: int


def _pair(values: Any, default: tuple[int, int]) -> tuple[int, int]:
    if values is None:
        return default
    low, high = (int(value) for value in values)
    return (low, high)


def world_event_settings_from_data(data: dict[str, Any]) -> WorldEventSettings:
    newcomers = tuple(
        Newcomer(
            newcomer_id=str(entry["id"]),
            name=str(entry.get("name", entry["id"])),
            age=int(entry.get("age", 30)),
            personality={str(name): float(value) for name, value in entry.get("personality", {}).items()},
            traits=tuple(str(trait) for trait in entry.get("traits", [])),
        )
        for entry in data.get("newcomers", [])
    )
    if len({newcomer.newcomer_id for newcomer in newcomers}) != len(newcomers):
        raise ValueError("Two newcomers share an id")
    events: dict[str, WorldEventDefinition] = {}
    for event_id, values in data.get("events", {}).items():
        kind = str(values.get("kind", ""))
        if kind not in KINDS:
            raise ValueError(f"World event {event_id} is of an unknown kind: {kind}")
        definition = WorldEventDefinition(
            event_id=str(event_id),
            kind=kind,
            chance_per_day=float(values.get("chance_per_day", 0.0)),
            hours=_pair(values.get("hours"), (0, 24)),
            cooldown_days=int(values.get("cooldown_days", 1)),
            text=str(values.get("text", "")),
            asks=str(values["asks"]) if "asks" in values else None,
            container=str(values["container"]) if "container" in values else None,
            count=_pair(values.get("count"), (0, 0)),
            items=tuple((str(entry["item"]), float(entry.get("weight", 1.0))) for entry in values.get("items", [])),
            category=str(values["category"]) if "category" in values else None,
            fraction=float(values.get("fraction", 0.0)),
            minutes=_pair(values.get("minutes"), (0, 0)),
            name=str(values.get("name", event_id)),
            stress_per_minute=float(values.get("stress_per_minute", 0.0)),
            end_text=str(values.get("end_text", "")),
            danger=float(values.get("danger", 0.0)),
            lead_hours=int(values.get("lead_hours", 0)),
            forecast=str(values.get("forecast", "")),
        )
        start, end = definition.hours
        if not (0.0 <= definition.chance_per_day <= 1.0 and 0 <= start < end <= 24):
            raise ValueError(f"World event {event_id} needs a chance from 0 to 1 and hours within one day")
        if not 0 <= definition.lead_hours <= start:
            raise ValueError(f"World event {event_id} cannot be on its way since before the day began")
        if not (0.0 <= definition.fraction <= 1.0 and all(weight > 0 for _, weight in definition.items)):
            raise ValueError(f"World event {event_id} has an impossible fraction or item weight")
        events[definition.event_id] = definition
    return WorldEventSettings(
        quiet_days=int(data.get("quiet_days", 1)), newcomers=newcomers, events=events
    )
