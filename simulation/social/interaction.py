from dataclasses import dataclass, field
from typing import Any

from simulation.social.relationship import FEELINGS


@dataclass(frozen=True)
class InteractionDefinition:
    """A kind of face-to-face exchange between two residents, such as a chat or an argument."""

    interaction_id: str
    hostile: bool
    minutes: tuple[int, int]
    importance: int
    text: str
    memory: str
    tension_importance: int = 0
    per_minute: dict[str, float] = field(default_factory=dict)
    relationship: dict[str, float] = field(default_factory=dict)
    dialogue: str | None = None
    emotional_value: float = 0.0
    tags: tuple[str, ...] = ()
    # Past-tense summary. An exchange with one becomes a fact that others can see and repeat.
    fact: str | None = None
    # Whether anything one of the two stole from the other is handed back afterwards.
    returns_stolen: bool = False
    # Range of harm each side does the other, for an exchange that comes to blows.
    damage: tuple[int, int] | None = None
    # What the exchange is to a romance: `confession`, `tryst`, `breakup` or `proposal`. None for any other.
    romance: str | None = None
    # What is said of somebody who is at it, with `{other}` where the other one goes. None
    # for one that is told like any other talk, or any other quarrel.
    doing: str | None = None
    # The taste it is liked or loathed by, as a tag of `data/tastes.json`, where it is done
    # for the sake of it: cards, a dance. What comes of it goes by how each of them takes it.
    pastime: str | None = None
    # The use both go on to once it is over, each for themselves: `drink`, for having asked
    # somebody for one. Whoever was asked goes only if they care to.
    then_use: str | None = None


ROMANCE_KINDS = ("confession", "tryst", "breakup", "proposal")


def interaction_definition_from_data(interaction_id: str, data: dict[str, Any]) -> InteractionDefinition:
    missing = {"minutes", "importance", "text", "memory"} - data.keys()
    if missing:
        raise ValueError(f"Missing fields in interaction {interaction_id}: {sorted(missing)}")
    relationship = {str(feeling): float(delta) for feeling, delta in data.get("relationship", {}).items()}
    unknown = relationship.keys() - set(FEELINGS)
    if unknown:
        raise ValueError(f"Interaction {interaction_id} changes unknown feelings: {sorted(unknown)}")
    damage = None
    if "damage" in data:
        low, high = (int(value) for value in data["damage"])
        if not 0 <= low <= high:
            raise ValueError(f"Interaction {interaction_id} has an invalid damage range")
        damage = (low, high)
    romance = str(data["romance"]) if "romance" in data else None
    if romance is not None and romance not in ROMANCE_KINDS:
        raise ValueError(f"Interaction {interaction_id} is an unknown kind of romance: {romance}")
    shortest, longest = (int(value) for value in data["minutes"])
    if not 1 <= shortest <= longest:
        raise ValueError(f"Interaction {interaction_id} has an invalid minutes range")
    return InteractionDefinition(
        interaction_id=interaction_id,
        hostile=bool(data.get("hostile", False)),
        minutes=(shortest, longest),
        importance=int(data["importance"]),
        text=str(data["text"]),
        memory=str(data["memory"]),
        tension_importance=int(data.get("tension_importance", 0)),
        per_minute={str(need): float(delta) for need, delta in data.get("per_minute", {}).items()},
        relationship=relationship,
        dialogue=str(data["dialogue"]) if "dialogue" in data else None,
        emotional_value=float(data.get("emotional_value", 0.0)),
        tags=tuple(str(tag) for tag in data.get("tags", [])),
        fact=str(data["fact"]) if "fact" in data else None,
        returns_stolen=bool(data.get("returns_stolen", False)),
        damage=damage,
        romance=romance,
        doing=str(data["doing"]) if data.get("doing") else None,
        pastime=str(data["pastime"]) if data.get("pastime") else None,
        then_use=str(data["then_use"]) if data.get("then_use") else None,
    )
