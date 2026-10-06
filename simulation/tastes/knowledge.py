"""What has been found out of residents' tastes, and by whom. It is kept apart from the tastes themselves."""

from dataclasses import dataclass, field

from simulation.tastes.settings import KNOWN, SUSPECTED, UNKNOWN, TasteSettings, side_of

# Who the player is among those who find things out. No resident can have this ID.
PLAYER = "@player"


@dataclass
class TasteKnowledge:
    """How much each onlooker has seen of each taste of each resident.

    That a resident has a taste says nothing here: only what was seen to happen does. What is
    kept is how much has been seen and how it looked the last time, and never how strong the
    taste is. A taste may have moved since: nobody knows it has until they see it.
    """

    # By onlooker, then by whose taste it is, then by taste: how much of it has shown.
    seen: dict[str, dict[str, dict[str, float]]] = field(default_factory=dict)
    # The same way round: the reaction it looked like the last time it showed.
    seen_as: dict[str, dict[str, dict[str, str]]] = field(default_factory=dict)

    def observe(
        self,
        observer_id: str,
        subject_id: str,
        key: str,
        shows: float,
        settings: TasteSettings,
        showing: str | None = None,
    ) -> str | None:
        """Take note of something that showed a taste, and of how it looked: `showing`, a reaction.

        Returns what the taste has become to the onlooker, if that has changed. Seeing it go
        the other way from what they had seen puts them back to merely suspecting it, the new
        way, however sure they were.
        """
        if shows <= 0.0 or observer_id == subject_id:
            return None
        before = self.state(observer_id, subject_id, key, settings)
        tastes = self.seen.setdefault(observer_id, {}).setdefault(subject_id, {})
        looked = self.seen_as.setdefault(observer_id, {}).setdefault(subject_id, {})
        turned = (
            showing is not None
            and before != UNKNOWN
            and key in looked
            and side_of(looked[key]) != side_of(showing)
        )
        if showing is not None:
            looked[key] = showing
        if turned:
            tastes[key] = settings.suspected_at
            return SUSPECTED
        tastes[key] = tastes.get(key, 0.0) + shows
        after = self.state(observer_id, subject_id, key, settings)
        return after if after != before else None

    def looked(self, observer_id: str, subject_id: str, key: str) -> str | None:
        """The reaction a taste looked like the last time an onlooker saw it show, if it was noted."""
        return self.seen_as.get(observer_id, {}).get(subject_id, {}).get(key)

    def state(self, observer_id: str, subject_id: str, key: str, settings: TasteSettings) -> str:
        shown = self.seen.get(observer_id, {}).get(subject_id, {}).get(key, 0.0)
        if shown >= settings.known_at:
            return KNOWN
        return SUSPECTED if shown >= settings.suspected_at else UNKNOWN

    def keys(self, observer_id: str, subject_id: str) -> list[str]:
        """Every taste of a resident an onlooker has seen anything of, in the order it first showed."""
        return list(self.seen.get(observer_id, {}).get(subject_id, {}))
