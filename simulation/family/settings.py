from dataclasses import dataclass, field
from typing import Any

from simulation.family.kin import BOTH, DRAWN_TO, GENDERS, SEXES
from simulation.residents.personality import Personality

# Which end of a side of a way of being is the worse one.
HIGH, LOW = "high", "low"


@dataclass(frozen=True)
class PersonData:
    """What the game says of somebody it has by name: who they are, and who they are kin to."""

    sex: str
    gender: str
    drawn_to: str = BOTH
    siblings: tuple[str, ...] = ()
    parents: tuple[str, ...] = ()


@dataclass(frozen=True)
class ChildSettings:
    """How children come, how a bundle fares, and how fast it grows."""

    # The chance that a child comes of two going off alone together or marrying, the weeks it is
    # carried, and the age from which nobody carries one.
    chance: float = 0.15
    carried_weeks: int = 9
    fertile_until: int = 50
    # The weeks a child is a bundle for, and the age it has at the end of them.
    weeks: int = 12
    grown_at: int = 10
    # The names a child may be given, by sex, and whether who they are drawn to is left to chance.
    names: dict[str, tuple[str, ...]] = field(default_factory=dict)
    drawn_by_chance: bool = True
    # How far from the middle of its parents' a side of a child's way of being may fall, and the
    # chance of taking each trait of theirs.
    mix_spread: float = 15.0
    trait_chance: float = 0.5
    # For a child of two who are kin by blood: the sides of a way of being of which it takes the
    # worse of its parents' outright, and which end of each is the worse one, `high` or `low`.
    worse: dict[str, str] = field(
        default_factory=lambda: {
            "aggression": "high",
            "empathy": "low",
            "impulsiveness": "high",
            "sociability": "low",
            "greed": "high",
            "courage": "low",
        }
    )
    # How fast a bundle gets hungry, from how hungry it is fed, and what feeding it costs whoever does.
    hunger_per_minute: float = 0.3
    feed_from: float = 60.0
    feed_cost: dict[str, float] = field(default_factory=lambda: {"tiredness": 2.0, "stress": 1.0})
    # The harm a minute does a bundle put down somewhere, by where; the minutes after which being
    # left has doubled it; the harm of a minute unfed; and what it mends in a minute of being well.
    harm: dict[str, float] = field(default_factory=lambda: {"surface": 0.01, "ground": 0.02})
    left_scale: float = 240.0
    hunger_harm: float = 0.05
    mend_per_minute: float = 0.02
    # Minutes a bundle is left by parents who are there before somebody else is asked to take it
    # in, and the minutes between asking one resident and the next.
    neglect_minutes: int = 720
    ask_gap_minutes: int = 60
    # How well a bundle the player put down has to be for whoever sees to it to leave it there.
    taken_up_below: float = 50.0
    # Events that whoever sees them happen to a child is the worse for, and by how much.
    seen_events: tuple[str, ...] = ("work_started", "injured", "limb_lost", "substance_taken", "fight_started")
    seen_mood: float = 6.0
    seen_stress: float = 3.0


def _children(data: dict[str, Any]) -> ChildSettings:
    defaults = ChildSettings()
    bundle = data.get("bundle", {})
    seen = data.get("seen", {})
    inbred = data.get("inbred", {})
    settings = ChildSettings(
        chance=float(data.get("chance", defaults.chance)),
        carried_weeks=int(data.get("carried_weeks", defaults.carried_weeks)),
        fertile_until=int(data.get("fertile_until", defaults.fertile_until)),
        weeks=int(data.get("weeks", defaults.weeks)),
        grown_at=int(data.get("grown_at", defaults.grown_at)),
        names={str(sex): tuple(str(name) for name in names) for sex, names in data.get("names", {}).items()},
        drawn_by_chance=bool(data.get("drawn_by_chance", defaults.drawn_by_chance)),
        mix_spread=float(data.get("mix_spread", defaults.mix_spread)),
        trait_chance=float(data.get("trait_chance", defaults.trait_chance)),
        worse={str(side): str(end) for side, end in inbred.get("worse", defaults.worse).items()},
        hunger_per_minute=float(bundle.get("hunger_per_minute", defaults.hunger_per_minute)),
        feed_from=float(bundle.get("feed_from", defaults.feed_from)),
        feed_cost={str(need): float(delta) for need, delta in bundle.get("feed_cost", defaults.feed_cost).items()},
        harm={str(place): float(harm) for place, harm in bundle.get("harm", defaults.harm).items()},
        left_scale=float(bundle.get("left_scale", defaults.left_scale)),
        hunger_harm=float(bundle.get("hunger_harm", defaults.hunger_harm)),
        mend_per_minute=float(bundle.get("mend_per_minute", defaults.mend_per_minute)),
        neglect_minutes=int(bundle.get("neglect_minutes", defaults.neglect_minutes)),
        ask_gap_minutes=int(bundle.get("ask_gap_minutes", defaults.ask_gap_minutes)),
        taken_up_below=float(bundle.get("taken_up_below", defaults.taken_up_below)),
        seen_events=tuple(str(event) for event in seen.get("events", defaults.seen_events)),
        seen_mood=float(seen.get("mood", defaults.seen_mood)),
        seen_stress=float(seen.get("stress", defaults.seen_stress)),
    )
    if not 0.0 <= settings.chance <= 1.0 or not 0.0 <= settings.trait_chance <= 1.0:
        raise ValueError("The chance of a child, and of a child taking a trait, must be from 0 to 1")
    sides = set(vars(Personality()))
    if any(side not in sides or end not in (HIGH, LOW) for side, end in settings.worse.items()):
        raise ValueError(f"The worse end of a side of a way of being is `high` or `low`, of one of {sorted(sides)}")
    if min(settings.carried_weeks, settings.weeks, settings.grown_at) < 1 or settings.left_scale <= 0:
        raise ValueError("A child is carried and is a bundle for a week or more, and grows to an age of one or more")
    if min([settings.hunger_per_minute, settings.hunger_harm, *settings.harm.values()]) < 0:
        raise ValueError("A bundle cannot be the better for hunger or for being put down")
    return settings


@dataclass(frozen=True)
class FamilySettings:
    """How time tells on people, and how families come about."""

    # The year a settlement's first day is the first of January of.
    start_year: int = 2226
    # The age before which nobody dies of old age, the chance of it in a year at that age, and
    # the years after which that chance has doubled.
    old_age: int = 80
    old_age_chance: float = 0.05
    old_age_doubles: float = 5.0
    # What a minute asleep on the ground does, for want of a bed: less rest than a bed gives,
    # and nerves the worse for it. How tired somebody has to be to lie down like that.
    rough_per_minute: dict[str, float] = field(default_factory=lambda: {"tiredness": -0.12, "stress": 0.02})
    rough_from: float = 60.0
    rough_minutes: int = 480
    # Those the game has by name, by ID: residents of the settlement that comes ready made, and
    # whoever may come to the gate.
    people: dict[str, PersonData] = field(default_factory=dict)
    # Pairs who come to the gate together.
    arrive_together: tuple[tuple[str, str], ...] = ()
    # How well two have to get on, and how much each has to want it there and then, to go off
    # alone together without being a couple.
    casual_affection: float = 55.0
    casual_desire: float = 60.0
    # What somebody has to feel for their partner to think of marrying them, and what the one
    # asked has to feel to say yes.
    marry_affection: float = 55.0
    marry_trust: float = 20.0
    marry_accept_affection: float = 45.0
    # What is felt for close kin to begin with, in each direction.
    kin_affection: float = 40.0
    kin_trust: float = 30.0
    # Events that tell on whoever sees them happen to one of their own, and how much: nerves
    # for each point of the event's importance.
    kin_events: tuple[str, ...] = ("injured", "limb_lost", "fight_started", "theft_committed")
    kin_stress: float = 0.25
    # What having one of a pair turned away at the gate does to the one let in: what they feel
    # for whoever decided it, and their nerves.
    parted_feelings: dict[str, float] = field(default_factory=lambda: {"resentment": 35.0, "trust": -25.0})
    parted_stress: float = 25.0
    children: ChildSettings = field(default_factory=ChildSettings)


def _person(person_id: str, data: Any) -> PersonData:
    if not isinstance(data, dict) or data.get("sex") not in SEXES:
        raise ValueError(f"Family data for {person_id} needs a sex: one of {SEXES}")
    person = PersonData(
        sex=str(data["sex"]),
        gender=str(data.get("gender", data["sex"])),
        drawn_to=str(data.get("drawn_to", BOTH)),
        siblings=tuple(str(each) for each in data.get("siblings", [])),
        parents=tuple(str(each) for each in data.get("parents", [])),
    )
    if person.gender not in GENDERS or person.drawn_to not in DRAWN_TO:
        raise ValueError(f"Family data for {person_id} has an unknown gender, or is drawn to nobody known")
    return person


def family_settings_from_data(data: dict[str, Any]) -> FamilySettings:
    defaults = FamilySettings()
    old = data.get("old_age", {})
    rough = data.get("sleeping_rough", {})
    casual = data.get("casual", {})
    marriage = data.get("marriage", {})
    kin = data.get("kin", {})
    parted = data.get("parted_at_gate", {})
    settings = FamilySettings(
        start_year=int(data.get("start_year", defaults.start_year)),
        old_age=int(old.get("from", defaults.old_age)),
        old_age_chance=float(old.get("chance_per_year", defaults.old_age_chance)),
        old_age_doubles=float(old.get("doubles_every", defaults.old_age_doubles)),
        rough_per_minute={
            str(need): float(delta) for need, delta in rough.get("per_minute", defaults.rough_per_minute).items()
        },
        rough_from=float(rough.get("from", defaults.rough_from)),
        rough_minutes=int(rough.get("minutes", defaults.rough_minutes)),
        people={str(person_id): _person(str(person_id), values) for person_id, values in data.get("people", {}).items()},
        arrive_together=tuple((str(pair[0]), str(pair[1])) for pair in data.get("arrive_together", [])),
        casual_affection=float(casual.get("affection", defaults.casual_affection)),
        casual_desire=float(casual.get("desire", defaults.casual_desire)),
        marry_affection=float(marriage.get("affection", defaults.marry_affection)),
        marry_trust=float(marriage.get("trust", defaults.marry_trust)),
        marry_accept_affection=float(marriage.get("accept_affection", defaults.marry_accept_affection)),
        kin_affection=float(kin.get("affection", defaults.kin_affection)),
        kin_trust=float(kin.get("trust", defaults.kin_trust)),
        kin_events=tuple(str(event) for event in kin.get("events", defaults.kin_events)),
        kin_stress=float(kin.get("stress", defaults.kin_stress)),
        parted_feelings={
            str(feeling): float(delta) for feeling, delta in parted.get("feelings", defaults.parted_feelings).items()
        },
        parted_stress=float(parted.get("stress", defaults.parted_stress)),
        children=_children(data.get("children", {})),
    )
    if not 0.0 <= settings.old_age_chance <= 1.0 or settings.old_age_doubles <= 0 or settings.old_age < 1:
        raise ValueError("Old age needs an age to begin at, a chance from 0 to 1 and years for it to double in")
    if settings.rough_per_minute.get("tiredness", 0.0) >= 0 or settings.rough_minutes < 1:
        raise ValueError("Sleeping on the ground must rest somebody a little, for a minute or more")
    return settings
