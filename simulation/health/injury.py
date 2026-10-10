from dataclasses import dataclass
from typing import Any

from simulation.residents.needs import NEED_NAMES


@dataclass(frozen=True)
class InjuryDefinition:
    """A kind of injury and how fast it mends, left alone or under a medic's care."""

    kind: str
    name: str
    heal_per_day: float
    treated_per_day: float
    # A single injury of this kind at least this severe may take a limb off, with this chance.
    severs_from: float | None = None
    severs_chance: float = 0.0
    # The need that brings this on while it is at its worst, and how fast it then grows.
    from_need: str | None = None
    worsens_per_day: float = 0.0


@dataclass(frozen=True)
class LimbDefinition:
    """A limb that can be lost for good, and what going without it does to its owner."""

    limb_id: str
    # With its article, as it reads after a verb: "el brazo izquierdo".
    name: str
    # What is left of the pace of their work, and of their walk, from 0 to 1.
    work_pace: float = 1.0
    walk_pace: float = 1.0
    # The limb this one is the far end of, by ID: a hand is within a forearm, and that within
    # an arm. Whoever is without a limb is without everything within it. None for a whole one.
    within: str | None = None
    # How likely it is to be the one that is lost, against the others: the smaller, the likelier.
    odds: float = 1.0


@dataclass
class Injury:
    """One injury a resident carries. Its severity is the health it takes away while it lasts."""

    kind: str
    severity: float


@dataclass
class Death:
    """The settlement's record of someone who died."""

    resident_id: str
    name: str
    timestamp: int
    cause: str
    killer_id: str | None = None
    grave_id: str | None = None


def injury_definition_from_data(kind: str, data: dict[str, Any]) -> InjuryDefinition:
    missing = {"name", "heal_per_day"} - data.keys()
    if missing:
        raise ValueError(f"Missing fields in injury {kind}: {sorted(missing)}")
    heal = float(data["heal_per_day"])
    treated = float(data.get("treated_per_day", heal))
    if heal <= 0 or treated <= 0:
        raise ValueError(f"Injury {kind} must heal at a positive rate")
    severs_from = float(data["severs_from"]) if data.get("severs_from") is not None else None
    severs_chance = float(data.get("severs_chance", 0.0))
    if not 0.0 <= severs_chance <= 1.0:
        raise ValueError(f"Injury {kind} takes a limb off with a chance outside 0 to 1")
    from_need = str(data["from_need"]) if data.get("from_need") is not None else None
    worsens = float(data.get("worsens_per_day", 0.0))
    if from_need is not None and (from_need not in NEED_NAMES or worsens <= 0):
        raise ValueError(f"Injury {kind} must come of a need that exists and grow at a positive rate")
    return InjuryDefinition(kind, str(data["name"]), heal, treated, severs_from, severs_chance, from_need, worsens)


def limb_definition_from_data(limb_id: str, data: dict[str, Any]) -> LimbDefinition:
    if "name" not in data:
        raise ValueError(f"Missing fields in limb {limb_id}: ['name']")
    work_pace, walk_pace = float(data.get("work_pace", 1.0)), float(data.get("walk_pace", 1.0))
    if not (0.0 < work_pace <= 1.0 and 0.0 < walk_pace <= 1.0):
        raise ValueError(f"Limb {limb_id} must leave a pace above 0 and no more than 1")
    odds = float(data.get("odds", 1.0))
    if odds <= 0.0:
        raise ValueError(f"Limb {limb_id} is lost with some likelihood, however little")
    return LimbDefinition(limb_id, str(data["name"]), work_pace, walk_pace, str(data["within"]) if "within" in data else None, odds)
