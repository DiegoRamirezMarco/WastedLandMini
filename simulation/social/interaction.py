from dataclasses import dataclass, field
from typing import Any

from simulation.residents.needs import NEED_NAMES
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
    # The same of whoever it is being done to, where it is something done to somebody (S63).
    doing_other: str | None = None
    # The taste it is liked or loathed by, as a tag of `data/tastes.json`, where it is done
    # for the sake of it: cards, a dance. What comes of it goes by how each of them takes it.
    pastime: str | None = None
    # The use both go on to once it is over, each for themselves: `drink`, for having asked
    # somebody for one. Whoever was asked goes only if they care to.
    then_use: str | None = None
    # Whether it is about something (S58): whoever starts it brings a subject up, and how
    # the other takes it tells on what they feel for them.
    subject: bool = False
    # For something that is done to somebody (S63), beside what both come to feel: what
    # whoever it was done to comes to feel for whoever did it, and what whoever did it for
    # them; what it does to the spirits and the needs of each; and what else it does, by
    # the name of each deed.
    towards_doer: dict[str, float] = field(default_factory=dict)
    towards_other: dict[str, float] = field(default_factory=dict)
    doer_mood: float = 0.0
    other_mood: float = 0.0
    doer_needs: dict[str, float] = field(default_factory=dict)
    other_needs: dict[str, float] = field(default_factory=dict)
    deeds: tuple[str, ...] = ()
    # What whoever it was done to remembers of it and how it sits with them, where that is
    # not what whoever did it remembers.
    memory_other: str | None = None
    value_other: float | None = None
    # Whether whoever was asked goes on to what it leads to whether they care to or not.
    insists: bool = False


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
    sides = {
        name: {str(key): float(delta) for key, delta in data.get(name, {}).items()}
        for name in ("towards_doer", "towards_other", "doer_needs", "other_needs")
    }
    if (sides["towards_doer"].keys() | sides["towards_other"].keys()) - set(FEELINGS):
        raise ValueError(f"Interaction {interaction_id} has somebody come to feel what there is not")
    if (sides["doer_needs"].keys() | sides["other_needs"].keys()) - set(NEED_NAMES):
        raise ValueError(f"Interaction {interaction_id} changes a need there is not")
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
        doing_other=str(data["doing_other"]) if data.get("doing_other") else None,
        pastime=str(data["pastime"]) if data.get("pastime") else None,
        then_use=str(data["then_use"]) if data.get("then_use") else None,
        subject=bool(data.get("subject", False)),
        towards_doer=sides["towards_doer"],
        towards_other=sides["towards_other"],
        doer_mood=float(data.get("doer_mood", 0.0)),
        other_mood=float(data.get("other_mood", 0.0)),
        doer_needs=sides["doer_needs"],
        other_needs=sides["other_needs"],
        deeds=tuple(str(deed) for deed in data.get("deeds", [])),
        memory_other=str(data["memory_other"]) if data.get("memory_other") else None,
        value_other=float(data["value_other"]) if "value_other" in data else None,
        insists=bool(data.get("insists", False)),
    )
