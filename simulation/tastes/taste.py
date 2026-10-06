"""What a resident likes and loathes: the data, and nothing that works on it."""

from dataclasses import dataclass, field

LOWEST, HIGHEST = -100.0, 100.0
# The kinds of thing a taste can be for: a category of item, a taste tag, one item in particular,
# and something about other people or about what passes between two of them.
CATEGORY, TAG, ITEM, PEOPLE = "category", "tag", "item", "people"
KINDS = (CATEGORY, TAG, ITEM, PEOPLE)


def key_of(kind: str, name: str) -> str:
    """One name for a taste wherever it has to be told apart from the rest: `tag:sweet`."""
    return f"{kind}:{name}"


def parts_of(key: str) -> tuple[str, str]:
    kind, _, name = key.partition(":")
    return kind, name


@dataclass
class Taste:
    """How much one thing is liked, from -100 to 100.

    `leaning` is what they came with and never changes. `learned` is what living has added to
    it or taken from it since. The taste is the two together.
    """

    leaning: float = 0.0
    learned: float = 0.0

    @property
    def value(self) -> float:
        return max(LOWEST, min(HIGHEST, self.leaning + self.learned))


@dataclass
class TasteProfile:
    """The tastes one resident has so far. One they have not met has no entry yet."""

    categories: dict[str, Taste] = field(default_factory=dict)
    tags: dict[str, Taste] = field(default_factory=dict)
    items: dict[str, Taste] = field(default_factory=dict)
    people: dict[str, Taste] = field(default_factory=dict)

    def of(self, kind: str) -> dict[str, Taste]:
        if kind == CATEGORY:
            return self.categories
        if kind == TAG:
            return self.tags
        if kind == ITEM:
            return self.items
        if kind == PEOPLE:
            return self.people
        raise ValueError(f"Unknown kind of taste: {kind}")

    def find(self, kind: str, name: str) -> Taste | None:
        return self.of(kind).get(name)

    def keys(self) -> list[str]:
        return [key_of(kind, name) for kind in KINDS for name in self.of(kind)]
