from dataclasses import dataclass


@dataclass
class PoliticalProfile:
    """What a resident holds about how a settlement should be run, and what they feel about
    how this one is. Kept apart from the resident, as their tastes are. Each from 0 to 100."""

    # Leanings: theirs from the start, and they do not change.
    authoritarian_tolerance: float = 50.0
    justice_sensitivity: float = 50.0
    collectivism: float = 50.0
    individualism: float = 50.0
    revengefulness: float = 50.0
    fearfulness: float = 50.0
    political_interest: float = 50.0
    # What they feel for whoever leads, which is for the person and goes with them.
    loyalty: float = 0.0
    # What they feel about the government, whoever is in it: how far they trust it, how much
    # they fear it and what they hold against it. Each by itself.
    trust: float = 50.0
    fear: float = 0.0
    resentment: float = 0.0

    def adjust(self, name: str, delta: float) -> None:
        setattr(self, name, max(0.0, min(100.0, getattr(self, name) + delta)))
