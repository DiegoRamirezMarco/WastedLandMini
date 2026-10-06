"""How much a resident likes a thing, and how they take it. Sums only: nothing here changes anything."""

from collections.abc import Callable
from dataclasses import dataclass

from simulation.items.item import ItemDefinition
from simulation.tastes.settings import DISLIKED, HATED, LIKED, LOVED, NEUTRAL, TasteSettings, side_of
from simulation.tastes.taste import CATEGORY, HIGHEST, ITEM, LOWEST, TAG, TasteProfile, key_of

__all__ = ["Moment", "felt", "liking", "reaction_to", "side_of"]


@dataclass(frozen=True)
class Moment:
    """What surrounds a thing when it is eaten, used or handed over."""

    # How pressing the needs it answers are, from 0 to 1.
    need: float = 0.0
    mood: float = 50.0
    # What is felt for whoever handed it over, from -100 to 100. Nothing if nobody did.
    fondness: float = 0.0


def liking(
    profile: TasteProfile,
    definition: ItemDefinition,
    settings: TasteSettings,
    counts: Callable[[str], bool] | None = None,
) -> float:
    """How much the tastes in a profile make of an item, from -100 to 100.

    Its taste tags and its category speak first. A taste for the item itself counts for more
    than they do without silencing them. Tastes the profile does not have say nothing, and with
    `counts` neither do those it turns down: that is how much someone else knows of them.
    """

    def value(kind: str, name: str) -> float | None:
        taste = profile.find(kind, name)
        if taste is None or (counts is not None and not counts(key_of(kind, name))):
            return None
        return taste.value

    by_tag = [found for tag in definition.preference_tags if (found := value(TAG, tag)) is not None]
    total = sum(by_tag) / len(by_tag) if by_tag else 0.0
    total += (value(CATEGORY, definition.category) or 0.0) * settings.category_weight
    own = value(ITEM, definition.item_id)
    if own:
        # The stronger the feeling for the item itself, the more it counts over the rest.
        weight = settings.item_weight * abs(own) / HIGHEST
        total = own * weight + total * (1.0 - weight)
    return max(LOWEST, min(HIGHEST, total))


def felt(liked: float, moment: Moment, settings: TasteSettings) -> float:
    """A liking as the moment colours it: hunger is the best sauce, and so is who it came from."""
    coloured = (
        liked
        + min(1.0, max(0.0, moment.need)) * settings.need_bonus
        + (moment.mood - 50.0) / 50.0 * settings.mood_bonus
        + moment.fondness / 100.0 * settings.fondness_bonus
    )
    return max(LOWEST, min(HIGHEST, coloured))


def reaction_to(score: float, settings: TasteSettings) -> str:
    """Which of the five reactions a liking comes to."""
    thresholds = settings.thresholds
    if score <= thresholds[HATED]:
        return HATED
    if score <= thresholds[DISLIKED]:
        return DISLIKED
    if score >= thresholds[LOVED]:
        return LOVED
    if score >= thresholds[LIKED]:
        return LIKED
    return NEUTRAL

