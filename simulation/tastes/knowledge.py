"""What has been found out of residents' tastes, and by whom. It is kept apart from the tastes themselves."""

from dataclasses import dataclass, field

from simulation.tastes.settings import KNOWN, SUSPECTED, UNKNOWN, TasteSettings

# Who the player is among those who find things out. No resident can have this ID.
PLAYER = "@player"


@dataclass
class TasteKnowledge:
    """How much each onlooker has seen of each taste of each resident.

    That a resident has a taste says nothing here: only what was seen to happen does. What is
    kept is how much has been seen, and never how strong the taste is.
    """

    # By onlooker, then by whose taste it is, then by taste: how much of it has shown.
    seen: dict[str, dict[str, dict[str, float]]] = field(default_factory=dict)

    def observe(self, observer_id: str, subject_id: str, key: str, shows: float, settings: TasteSettings) -> str | None:
        """Take note of something that showed a taste. Returns what it has become, if it has changed."""
        if shows <= 0.0 or observer_id == subject_id:
            return None
        before = self.state(observer_id, subject_id, key, settings)
        tastes = self.seen.setdefault(observer_id, {}).setdefault(subject_id, {})
        tastes[key] = tastes.get(key, 0.0) + shows
        after = self.state(observer_id, subject_id, key, settings)
        return after if after != before else None

    def state(self, observer_id: str, subject_id: str, key: str, settings: TasteSettings) -> str:
        shown = self.seen.get(observer_id, {}).get(subject_id, {}).get(key, 0.0)
        if shown >= settings.known_at:
            return KNOWN
        return SUSPECTED if shown >= settings.suspected_at else UNKNOWN

    def keys(self, observer_id: str, subject_id: str) -> list[str]:
        """Every taste of a resident an onlooker has seen anything of, in the order it first showed."""
        return list(self.seen.get(observer_id, {}).get(subject_id, {}))
