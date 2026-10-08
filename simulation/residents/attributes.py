"""What a resident is capable of: strength, constitution, dexterity, mind, senses and charisma (S46).

Each goes from 1 to 10. Five are kept with the resident. Charisma is the side of their way of
being that already went by that name (S26), read on the same scale, so that there is one of it.
What each is good for is data: how much a point either side of the middle changes a thing.
"""

from dataclasses import dataclass, field
from typing import Any

STRENGTH, CONSTITUTION, DEXTERITY = "strength", "constitution", "dexterity"
MIND, SENSES, CHARISMA = "mind", "senses", "charisma"
ATTRIBUTES = (STRENGTH, CONSTITUTION, DEXTERITY, MIND, SENSES, CHARISMA)
# The ones kept with the resident. Charisma is kept with their way of being.
OWN = (STRENGTH, CONSTITUTION, DEXTERITY, MIND, SENSES)
# What a point of an attribute may change, each by so much either side of the middle.
#   work_pace: how fast a job is done by whoever has the attribute it goes by.
#   fight_strength: what is dealt in a fight, by strength. fight_dodge: what is taken, by dexterity.
#   toughness: how bad an injury comes out, by constitution. healing: how fast one mends.
#   tiredness: how much work tires. carry: units more or fewer in one trip, by strength.
#   study: how fast things are worked out, by mind. learning: how fast a trade is learned.
#   sight: tiles further or nearer that are seen, by senses.
#   finds: what a trip outside brings back. danger: how safe it is, by senses.
EFFECTS = (
    "work_pace", "fight_strength", "fight_dodge", "toughness", "healing", "tiredness", "carry", "study",
    "learning", "sight", "finds", "danger",
)
# What raises an attribute, each by so much a time: a minute at a post, a fight, an injury
# come through, a day of leading.
PRACTICES = ("work", "fight", "hurt", "lead")


@dataclass
class Attributes:
    strength: float = 5.0
    constitution: float = 5.0
    dexterity: float = 5.0
    mind: float = 5.0
    senses: float = 5.0


@dataclass(frozen=True)
class AttributeDefinition:
    attribute_id: str
    name: str
    # Three letters for where there is no room for the name.
    short: str
    text: str = ""


@dataclass(frozen=True)
class AttributeSettings:
    attributes: dict[str, AttributeDefinition] = field(default_factory=dict)
    lowest: float = 1.0
    highest: float = 10.0
    middle: float = 5.0
    # How far from the middle what somebody is born with may fall, either way.
    spread: float = 3.5
    # How many points the first resident has to share out among the six.
    founder_points: float = 33.0
    # How much of a child's attributes are the middle of its parents', the rest being its own.
    inherit: float = 0.6
    effects: dict[str, float] = field(default_factory=dict)
    practice: dict[str, float] = field(default_factory=dict)
    # The age from which the body gives a little each year, by how much, and in what.
    age_from: int = 50
    age_per_year: float = 0.08
    ages: tuple[str, ...] = (STRENGTH, CONSTITUTION, DEXTERITY, SENSES)
    # The age at which somebody has all of what they will have, the share of it a newborn has,
    # and what grows with them.
    grown_at: int = 16
    youth_floor: float = 0.4
    grows: tuple[str, ...] = (STRENGTH, CONSTITUTION)
    # What being hurt takes from, and the share of it gone in somebody at death's door.
    injured: tuple[str, ...] = (STRENGTH, DEXTERITY)
    injured_share: float = 0.5

    def clamp(self, value: float) -> float:
        return max(self.lowest, min(self.highest, value))


def _numbers(data: Any, allowed: tuple[str, ...], where: str) -> dict[str, float]:
    if not isinstance(data, dict):
        raise ValueError(f"{where} must be an object of numbers")
    unknown = sorted(set(data) - set(allowed))
    if unknown:
        raise ValueError(f"{where} names what nothing asks about: {unknown}")
    return {str(key): float(value) for key, value in data.items()}


def _named(data: Any, where: str) -> tuple[str, ...]:
    names = tuple(str(name) for name in data)
    unknown = sorted(set(names) - set(ATTRIBUTES))
    if unknown:
        raise ValueError(f"{where} names attributes there are not: {unknown}")
    return names


def attribute_settings_from_data(data: dict[str, Any]) -> AttributeSettings:
    defaults = AttributeSettings()
    given = data.get("attributes", {})
    unknown = sorted(set(given) - set(ATTRIBUTES))
    if unknown:
        raise ValueError(f"There are no such attributes: {unknown}. They are {ATTRIBUTES}")
    attributes = {}
    for attribute_id in ATTRIBUTES:
        values = given.get(attribute_id)
        if not isinstance(values, dict) or "name" not in values:
            raise ValueError(f"Attribute {attribute_id} needs a name")
        name = str(values["name"])
        attributes[attribute_id] = AttributeDefinition(
            attribute_id, name, str(values.get("short", name[:3].upper())), str(values.get("text", ""))
        )
    age = data.get("age", {})
    youth = data.get("youth", {})
    injury = data.get("injury", {})
    settings = AttributeSettings(
        attributes=attributes,
        lowest=float(data.get("lowest", defaults.lowest)),
        highest=float(data.get("highest", defaults.highest)),
        middle=float(data.get("middle", defaults.middle)),
        spread=float(data.get("spread", defaults.spread)),
        founder_points=float(data.get("founder_points", defaults.founder_points)),
        inherit=float(data.get("inherit", defaults.inherit)),
        effects=_numbers(data.get("effects", {}), EFFECTS, "What attributes do"),
        practice=_numbers(data.get("practice", {}), PRACTICES, "What raises an attribute"),
        age_from=int(age.get("from", defaults.age_from)),
        age_per_year=float(age.get("per_year", defaults.age_per_year)),
        ages=_named(age.get("of", defaults.ages), "What age takes from"),
        grown_at=int(youth.get("grown_at", defaults.grown_at)),
        youth_floor=float(youth.get("floor", defaults.youth_floor)),
        grows=_named(youth.get("of", defaults.grows), "What grows with a child"),
        injured=_named(injury.get("of", defaults.injured), "What being hurt takes from"),
        injured_share=float(injury.get("share", defaults.injured_share)),
    )
    if not settings.lowest <= settings.middle <= settings.highest or settings.lowest >= settings.highest:
        raise ValueError("Attributes go from a lowest to a highest, with the middle between them")
    if settings.spread < 0 or not 0.0 <= settings.inherit <= 1.0 or not 0.0 <= settings.injured_share <= 1.0:
        raise ValueError("Attributes spread by no less than nothing, and shares go from 0 to 1")
    if settings.founder_points < settings.lowest * len(ATTRIBUTES) or settings.grown_at < 1:
        raise ValueError("The first resident needs points for the lowest of everything, and a child grows up")
    if not 0.0 < settings.youth_floor <= 1.0 or any(value < 0 for value in settings.practice.values()):
        raise ValueError("A newborn has a share of what they will have, and practice takes nothing away")
    return settings
