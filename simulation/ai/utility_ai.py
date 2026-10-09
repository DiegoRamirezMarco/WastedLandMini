from dataclasses import dataclass

from simulation.residents.needs import BOREDOM
from simulation.residents.resident import Resident

# Score lost per tile of distance to whatever the action needs.
DISTANCE_COST = 0.003
# Wanting to be entertained weighs under half what a need of the body does: bored to tears is
# still less than work is worth, and nobody leaves their post for it (S62).
BOREDOM_WEIGHT = 0.45


@dataclass(frozen=True)
class ScoredAction:
    """A thing a resident could do next: use an object, talk to someone, or handle an item."""

    name: str
    score: float
    target_id: str | None = None
    partner_id: str | None = None
    item_id: str | None = None


def choose_best(actions: list[ScoredAction]) -> ScoredAction | None:
    return max(actions, key=lambda action: action.score, default=None)


def ranked(actions: list[ScoredAction]) -> list[ScoredAction]:
    """Best first. Equal scores keep the order they were given in."""
    return sorted(actions, key=lambda action: -action.score)


def need_urgency(resident: Resident, need: str) -> float:
    """How much a resident wants a need lowered, from 0 to about 1.5."""
    if need == BOREDOM:
        weight = BOREDOM_WEIGHT
    else:
        weight = 0.5 + resident.personality.sociability / 100.0 if need == "social" else 1.0
    return weight * (getattr(resident.needs, need) / 100.0) ** 2
