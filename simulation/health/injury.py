from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class InjuryDefinition:
    """A kind of injury and how fast it mends, left alone or under a medic's care."""

    kind: str
    name: str
    heal_per_day: float
    treated_per_day: float


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
    return InjuryDefinition(kind, str(data["name"]), heal, treated)
