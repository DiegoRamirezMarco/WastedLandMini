from dataclasses import dataclass, field

SOURCE_PARTICIPANT = "participant"
SOURCE_WITNESS = "witness"
SOURCE_TOLD = "told"


@dataclass
class Fact:
    """Something that happened in the settlement. The world records it; residents may not know it."""

    fact_id: str
    event_type: str
    text: str
    subject_ids: list[str] = field(default_factory=list)
    importance: int = 0
    timestamp: int = 0
    location_id: str | None = None


@dataclass
class Belief:
    """One resident's knowledge of a fact: how they learned it and how sure they are."""

    fact_id: str
    credibility: float
    source: str
    learned_at: int = 0
    told_by: str | None = None


class KnowledgeStore:
    """All facts, and for each resident the facts they know about."""

    def __init__(self) -> None:
        self.facts: dict[str, Fact] = {}
        self._beliefs: dict[str, dict[str, Belief]] = {}

    def new_fact_id(self) -> str:
        number = len(self.facts) + 1
        while f"fact_{number}" in self.facts:
            number += 1
        return f"fact_{number}"

    def add_fact(self, fact: Fact) -> None:
        self.facts[fact.fact_id] = fact

    def belief(self, resident_id: str, fact_id: str) -> Belief | None:
        return self._beliefs.get(resident_id, {}).get(fact_id)

    def knows(self, resident_id: str, fact_id: str) -> bool:
        return self.belief(resident_id, fact_id) is not None

    def beliefs_of(self, resident_id: str) -> list[Belief]:
        return list(self._beliefs.get(resident_id, {}).values())

    def set_belief(self, resident_id: str, belief: Belief) -> None:
        self._beliefs.setdefault(resident_id, {})[belief.fact_id] = belief

    def resident_ids(self) -> list[str]:
        return list(self._beliefs)
