"""Trials and punishments as data (`data/punishments.json`): what somebody can be tried for, the
scale of punishments and what each needs, and the numbers a trial and its aftermath go by."""

from dataclasses import dataclass, field
from typing import Any

# How each of those who see or hear of a punishment may take it.
APPROVAL, FEAR, ANGER, GRIEF, INDIFFERENCE = "approval", "fear", "anger", "grief", "indifference"
REACTIONS = (APPROVAL, FEAR, ANGER, GRIEF, INDIFFERENCE)


@dataclass(frozen=True)
class OffenceDefinition:
    """Something somebody can be tried for: the kind of event it is, and how grave."""

    event_type: str
    name: str
    # From 1 to 10, as the severity of a punishment is: what answers it without going beyond it.
    gravity: int = 1


@dataclass(frozen=True)
class PunishmentDefinition:
    punishment_id: str
    name: str
    # From 1, a word, to 10, a life.
    severity: int = 1
    # What is said of whoever is given it: "va a la cárcel".
    said: str = ""
    # The use a building has to have for it to be carried out, and the kinds of object any one
    # of which has to stand in the settlement. Nobody is sentenced to what there is no place for.
    building: str | None = None
    objects: tuple[str, ...] = ()
    # Whether it is done where everybody can see, and whether it is one of the harsh ones.
    public: bool = False
    harsh: bool = False
    # How much of it there is, by what it is: coin, things, days, hours, or harm to health.
    amount: float = 0.0
    things: int = 0
    days: int = 0
    hours: int = 0
    harm: float = 0.0
    # What whoever dies of it is said to have died of.
    cause: str = ""


@dataclass(frozen=True)
class JusticeSettings:
    offences: dict[str, OffenceDefinition] = field(default_factory=dict)
    punishments: dict[str, PunishmentDefinition] = field(default_factory=dict)
    # Minutes between one step of a trial and the next, the hours the player has to say what
    # the punishment is, and what it is when they say nothing.
    step_minutes: int = 60
    sentence_hours: int = 24
    unanswered: str = "warning"
    # What somebody has to make of it to hold the accused guilty, and how much each thing counts.
    guilty_from: float = 0.5
    weights: dict[str, float] = field(
        default_factory=lambda: {
            "saw": 1.0, "told": 0.8, "testimony": 0.6, "resentment": 0.3, "affection": -0.3, "kin": -0.4, "accuser": 0.1,
        }
    )
    # When in the day somebody who knows of something thinks of accusing, how sure of it they
    # have to be, how many days old it may be, and what it has to come to with them.
    accuse_hour: int = 12
    accuse_sure_from: float = 0.6
    accuse_within_days: int = 6
    accuse_from: float = 0.45
    accuse_weights: dict[str, float] = field(
        default_factory=lambda: {"gravity": 0.05, "resentment": 0.6, "affection": -0.6, "justice": 0.3}
    )
    # What a prisoner is given each day until the player says otherwise, and the most of either.
    meals: int = 3
    drinks: int = 2
    food: str = ""
    drink: str = ""
    most_rations: int = 4
    # How a punishment is taken: the affection from which somebody is a friend, by how much
    # it has to go beyond what was done to be feared, the severity under which nobody much
    # minds, what each way of taking it does to whoever takes it so and to the settlement's
    # measures for each point of severity, what a harsh one does, how much more a child's
    # counts, and how much of it reaches whoever only hears of it.
    friend_from: float = 40.0
    harsher_by: int = 3
    indifferent_below: int = 2
    felt: dict[str, dict[str, float]] = field(default_factory=dict)
    measures: dict[str, dict[str, float]] = field(default_factory=dict)
    harsh: dict[str, float] = field(default_factory=dict)
    child_factor: float = 3.0
    heard_share: float = 0.5
    # After how many days somebody exiled is heard of again, the chance that it is with raiders
    # for one who left with all the grudge there is, and how many days running they try the gate.
    return_days: tuple[int, int] = (5, 12)
    raid_chance: float = 0.5
    return_tries: int = 3


def _numbers(data: Any, where: str) -> dict[str, float]:
    if not isinstance(data, dict):
        raise ValueError(f"{where} must be an object of numbers")
    return {str(key): float(value) for key, value in data.items()}


def _punishment(punishment_id: str, data: Any) -> PunishmentDefinition:
    if not isinstance(data, dict) or "name" not in data:
        raise ValueError(f"Punishment {punishment_id} needs a name")
    definition = PunishmentDefinition(
        punishment_id=punishment_id,
        name=str(data["name"]),
        severity=int(data.get("severity", 1)),
        said=str(data.get("said", "")),
        building=str(data["building"]) if data.get("building") else None,
        objects=tuple(str(kind) for kind in data.get("objects", [])),
        public=bool(data.get("public", False)),
        harsh=bool(data.get("harsh", False)),
        amount=float(data.get("amount", 0.0)),
        things=int(data.get("things", 0)),
        days=int(data.get("days", 0)),
        hours=int(data.get("hours", 0)),
        harm=float(data.get("harm", 0.0)),
        cause=str(data.get("cause", "")),
    )
    if not 1 <= definition.severity <= 10:
        raise ValueError(f"The severity of punishment {punishment_id} must be from 1 to 10")
    if min(definition.amount, definition.things, definition.days, definition.hours, definition.harm) < 0:
        raise ValueError(f"Punishment {punishment_id} cannot be less than nothing of anything")
    return definition


def justice_settings_from_data(data: dict[str, Any]) -> JusticeSettings:
    defaults = JusticeSettings()
    trial, accusing, prison = data.get("trial", {}), data.get("accusing", {}), data.get("prison", {})
    reactions, back = data.get("reactions", {}), data.get("exile_return", {})
    offences = {}
    for event_type, values in data.get("offences", {}).items():
        if not isinstance(values, dict) or "name" not in values:
            raise ValueError(f"Offence {event_type} needs a name")
        gravity = int(values.get("gravity", 1))
        if not 1 <= gravity <= 10:
            raise ValueError(f"The gravity of offence {event_type} must be from 1 to 10")
        offences[str(event_type)] = OffenceDefinition(str(event_type), str(values["name"]), gravity)
    punishments = {str(key): _punishment(str(key), values) for key, values in data.get("punishments", {}).items()}
    days = back.get("days", defaults.return_days)
    felt = {
        str(reaction): _numbers(reactions.get(reaction, {}), f"What {reaction} does to whoever feels it")
        for reaction in REACTIONS
        if reaction in reactions
    }
    measures = {
        str(reaction): _numbers(values, f"What {reaction} does to the settlement")
        for reaction, values in reactions.get("measures", {}).items()
    }
    unknown = sorted(set(measures) - set(REACTIONS))
    if unknown:
        raise ValueError(f"A punishment is taken in one of {REACTIONS}, not {unknown}")
    settings = JusticeSettings(
        offences=offences,
        punishments=punishments,
        step_minutes=int(trial.get("step_minutes", defaults.step_minutes)),
        sentence_hours=int(trial.get("sentence_hours", defaults.sentence_hours)),
        unanswered=str(trial.get("unanswered", defaults.unanswered)),
        guilty_from=float(trial.get("guilty_from", defaults.guilty_from)),
        weights={**defaults.weights, **_numbers(trial.get("weights", {}), "The weights of a verdict")},
        accuse_hour=int(accusing.get("hour", defaults.accuse_hour)),
        accuse_sure_from=float(accusing.get("sure_from", defaults.accuse_sure_from)),
        accuse_within_days=int(accusing.get("within_days", defaults.accuse_within_days)),
        accuse_from=float(accusing.get("from", defaults.accuse_from)),
        accuse_weights={**defaults.accuse_weights, **_numbers(accusing.get("weights", {}), "The weights of accusing")},
        meals=int(prison.get("meals", defaults.meals)),
        drinks=int(prison.get("drinks", defaults.drinks)),
        food=str(prison.get("food", defaults.food)),
        drink=str(prison.get("drink", defaults.drink)),
        most_rations=int(prison.get("most", defaults.most_rations)),
        friend_from=float(reactions.get("friend_from", defaults.friend_from)),
        harsher_by=int(reactions.get("harsher_by", defaults.harsher_by)),
        indifferent_below=int(reactions.get("indifferent_below", defaults.indifferent_below)),
        felt=felt,
        measures=measures,
        harsh=_numbers(reactions.get("harsh", {}), "What a harsh punishment does"),
        child_factor=float(reactions.get("child_factor", defaults.child_factor)),
        heard_share=float(reactions.get("heard_share", defaults.heard_share)),
        return_days=(int(days[0]), int(days[1])),
        raid_chance=float(back.get("raid_chance", defaults.raid_chance)),
        return_tries=int(back.get("tries", defaults.return_tries)),
    )
    if settings.punishments and settings.unanswered not in settings.punishments:
        raise ValueError(f"What is given when nothing is said must be a punishment there is: {settings.unanswered}")
    if settings.step_minutes < 1 or settings.sentence_hours < 1 or not 0 <= settings.accuse_hour < 24:
        raise ValueError("A trial takes a minute or more a step, and an hour or more to be sentenced")
    if settings.return_days[0] < 1 or settings.return_days[1] < settings.return_days[0]:
        raise ValueError("Somebody exiled is heard of again after a day or more, the first figure no more than the second")
    if not 0.0 <= settings.raid_chance <= 1.0 or min(settings.meals, settings.drinks) < 0 or settings.most_rations < 1:
        raise ValueError("The chance of raiders is from 0 to 1, and a prisoner is given no less than nothing")
    return settings
