"""Substances as data, and what they leave in whoever takes them.

A substance is an item like any other with a `substance` entry: how it is taken, the good it
does while it lasts, the harm of its own, and what it looks like to others. A pack brings one
with no code of its own.
"""

from dataclasses import dataclass, field
from typing import Any

# What a resident may decide about something they are about to take.
TAKE = "take"
RESIST = "resist"
SUBSTANCE_CHOICES = (TAKE, RESIST)


@dataclass(frozen=True)
class SubstanceDefinition:
    """What taking an item does beyond what it does to needs on the spot."""

    # How it is taken: one of the routes in `data/substances.json`.
    route: str
    # How long it lasts, and what it does to needs each minute and to the pace of work meanwhile.
    minutes: int
    per_minute: dict[str, float] = field(default_factory=dict)
    work_pace: float = 1.0
    # Whether whoever is under it notices nothing around them.
    unaware: bool = False
    # What comes after it wears off: for how long, and what it does to needs each minute.
    after_minutes: int = 0
    after_per_minute: dict[str, float] = field(default_factory=dict)
    # The harm to health of taking it at all, and of taking it on top of itself.
    toll: float = 0.0
    harm: float = 0.0
    # The chance, the first time, that taking it brings dependence. It grows with the habit.
    dependence: float = 0.0
    # Minutes after which somebody who depends on it wants more.
    craving_minutes: int = 1440
    # What it looks like on whoever took it, which is what tastes in people go by.
    sign: str = ""


@dataclass(frozen=True)
class SubstanceSettings:
    """How substances work in general. What each one does is in its own item."""

    # The ways there are of taking one, and how each is said of whoever does: "se fuma".
    routes: dict[str, str] = field(default_factory=dict)
    # What each sign is called when someone is seen with it on them: "había bebido de más".
    signs: dict[str, str] = field(default_factory=dict)
    # The route whose sign reaches everyone under the same roof, and nobody outside it.
    fills_the_room: str = "smoked"
    # How much likelier each time already taken makes dependence, and the likeliest it gets.
    habit_growth: float = 0.15
    max_chance: float = 0.6
    # Minutes without it after which dependence passes, and how much faster under a medic's care.
    passes_after_minutes: int = 7200
    care_factor: float = 3.0
    # What going without does to whoever depends on something: needs each minute, and work.
    withdrawal_per_minute: dict[str, float] = field(default_factory=dict)
    withdrawal_pace: float = 0.8
    # How much somebody who depends on a thing and has gone without wants it, beside any need.
    craving_wish: float = 0.8
    # Impulsiveness from which somebody takes more of what they are already under.
    impulse_from: float = 60.0
    # The chance of dependence from which a first time is something the player has a say in.
    hooks_from: float = 0.08
    # Minutes without it after which going back to it is a relapse.
    relapse_minutes: int = 2880
    # How long a yes lasts, how long a no does, and what a no costs in nerves.
    allowed_minutes: int = 180
    resist_minutes: int = 360
    resist_stress: float = 8.0
    # The kind of injury too much of something is.
    overdose_kind: str = "intoxication"


@dataclass
class Intake:
    """Something a resident has taken and is still under, or coming down from."""

    item_id: str
    # Game minute at which it wears off, and at which what comes after it is over.
    until: int
    after_until: int = 0
    sign: str = ""
    unaware: bool = False


@dataclass
class Habit:
    """What a resident's history with one substance is."""

    uses: int = 0
    last_taken: int = 0
    dependent: bool = False
    # Minutes gone without since they wanted it and had none, which is what dependence passes with.
    without: float = 0.0
    # Whether they depended on it once and got over it.
    recovered: bool = False
    # Game minutes until which they have made up their mind to take it, or not to.
    allowed_until: int = 0
    resisting_until: int = 0


def _needs(data: Any, where: str) -> dict[str, float]:
    if not isinstance(data, dict) or not all(
        isinstance(value, (int, float)) and not isinstance(value, bool) for value in data.values()
    ):
        raise ValueError(f"{where} must map needs to numbers")
    return {str(need): float(delta) for need, delta in data.items()}


def substance_from_data(where: str, data: Any) -> SubstanceDefinition:
    """Read an item's `substance` entry. Raises ValueError for one that makes no sense."""
    if not isinstance(data, dict) or not isinstance(data.get("route"), str):
        raise ValueError(f"The substance of {where} needs a route: how it is taken")
    after = data.get("after", {})
    if not isinstance(after, dict):
        raise ValueError(f"What comes after the substance of {where} must be an object")
    definition = SubstanceDefinition(
        route=data["route"],
        minutes=int(data.get("minutes", 0)),
        per_minute=_needs(data.get("per_minute", {}), f"What the substance of {where} does each minute"),
        work_pace=float(data.get("work_pace", 1.0)),
        unaware=bool(data.get("unaware", False)),
        after_minutes=int(after.get("minutes", 0)),
        after_per_minute=_needs(after.get("per_minute", {}), f"What comes after the substance of {where}"),
        toll=float(data.get("toll", 0.0)),
        harm=float(data.get("harm", 0.0)),
        dependence=float(data.get("dependence", 0.0)),
        craving_minutes=int(data.get("craving_minutes", 1440)),
        sign=str(data.get("sign", "")),
    )
    if definition.minutes < 1 or definition.after_minutes < 0 or definition.craving_minutes < 1:
        raise ValueError(f"The substance of {where} must last a minute or more, and be wanted again after one or more")
    if not 0.0 <= definition.dependence <= 1.0 or definition.work_pace <= 0 or min(definition.toll, definition.harm) < 0:
        raise ValueError(f"The substance of {where} has an impossible chance of dependence, pace of work or harm")
    return definition


def substance_settings_from_data(data: dict[str, Any]) -> SubstanceSettings:
    defaults = SubstanceSettings()
    withdrawal = data.get("withdrawal", {})
    settings = SubstanceSettings(
        routes={str(route): str(said) for route, said in data.get("routes", {}).items()},
        signs={str(sign): str(said) for sign, said in data.get("signs", {}).items()},
        fills_the_room=str(data.get("fills_the_room", defaults.fills_the_room)),
        habit_growth=float(data.get("habit_growth", defaults.habit_growth)),
        max_chance=float(data.get("max_chance", defaults.max_chance)),
        passes_after_minutes=int(data.get("passes_after_minutes", defaults.passes_after_minutes)),
        care_factor=float(data.get("care_factor", defaults.care_factor)),
        withdrawal_per_minute=_needs(withdrawal.get("per_minute", {}), "What going without does each minute"),
        withdrawal_pace=float(withdrawal.get("work_pace", defaults.withdrawal_pace)),
        craving_wish=float(data.get("craving_wish", defaults.craving_wish)),
        impulse_from=float(data.get("impulse_from", defaults.impulse_from)),
        hooks_from=float(data.get("hooks_from", defaults.hooks_from)),
        relapse_minutes=int(data.get("relapse_minutes", defaults.relapse_minutes)),
        allowed_minutes=int(data.get("allowed_minutes", defaults.allowed_minutes)),
        resist_minutes=int(data.get("resist_minutes", defaults.resist_minutes)),
        resist_stress=float(data.get("resist_stress", defaults.resist_stress)),
        overdose_kind=str(data.get("overdose_kind", defaults.overdose_kind)),
    )
    if not 0.0 <= settings.max_chance <= 1.0 or settings.habit_growth < 0 or settings.care_factor < 1:
        raise ValueError("Substances need a chance from 0 to 1, a habit that does not shrink and care that does not slow")
    if settings.passes_after_minutes < 1 or settings.withdrawal_pace <= 0:
        raise ValueError("Dependence must take a minute or more to pass, and going without must leave some pace of work")
    return settings
