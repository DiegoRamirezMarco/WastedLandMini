import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any

from simulation.substances.substance import SubstanceDefinition

# A thing in worse condition than this is worth taking to be repaired.
WORN_CONDITION = 50.0
TASTE_TAG_PATTERN = re.compile(r"^[a-z0-9]+(_[a-z0-9]+)*$")
_BETWEEN_WORDS = re.compile(r"[\s\-]+")


def taste_tags(raw: Any) -> tuple[str, ...]:
    """Taste tags as they are kept: lower case, words joined by underscores, each of them once.

    There is no list they must come from. Raises ValueError for what cannot be made into one.
    """
    if isinstance(raw, str) or not isinstance(raw, Iterable):
        raise ValueError("'preference_tags' must be a list of strings")
    tidy: list[str] = []
    for tag in raw:
        if not isinstance(tag, str):
            raise ValueError("'preference_tags' must be a list of strings")
        tag = _BETWEEN_WORDS.sub("_", tag.strip().lower())
        if not TASTE_TAG_PATTERN.match(tag):
            raise ValueError(f"'{tag}' is not a taste tag: lowercase letters, digits and single underscores")
        if tag not in tidy:
            tidy.append(tag)
    return tuple(tidy)


@dataclass(frozen=True)
class ItemDefinition:
    item_id: str
    name: str
    article: str
    category: str
    base_value: int = 0
    description: str = ""
    tags: tuple[str, ...] = ()
    effects: dict[str, float] = field(default_factory=dict)
    # Other numbers about the item, such as `damage` for a weapon.
    properties: dict[str, float] = field(default_factory=dict)
    # What there is to like or loathe about it. `tags` are for rules and sorting, and never make a taste.
    preference_tags: tuple[str, ...] = ()
    # What taking it does beyond its effects on the spot, for an item that is a substance.
    substance: SubstanceDefinition | None = None


@dataclass
class ItemInstance:
    instance_id: str
    definition_id: str
    owner_id: str | None = None
    condition: float = 100.0
    quantity: int = 1
    # How rare it is, and so how good, from 1: the place of its rarity among those there
    # are (S64). Things of one kind and two rarities are two stacks.
    level: int = 1
    # ID of the resident who made a present of it to its owner, if anyone did.
    given_by: str | None = None
    # Who it is being kept for: the resident it was bought as a present for, or the settlement,
    # when it is something handed over or bought for the fund that is still on its way there.
    meant_for: str | None = None

    @property
    def broken(self) -> bool:
        """Worn right out. A broken thing does nothing until it is repaired."""
        return self.condition <= 0.0
