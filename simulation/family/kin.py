"""Who is kin to whom, kept by stable IDs so that the dead and the absent stay in the tree.

What is kept is who somebody's parents are, by birth and by having taken them in, who they
are married to, and brothers and sisters whose parents nobody knows. The rest is worked out.
"""

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from simulation.world import SimulationWorld

SEXES = ("m", "f")
GENDERS = ("m", "f", "nb", "bi")
BOTH = "both"
DRAWN_TO = ("m", "f", BOTH)
# What kin are called, by what they are to somebody and the gender they go by.
WORDS = {
    "parent": {"m": "padre", "f": "madre"},
    "child": {"m": "hijo", "f": "hija"},
    "sibling": {"m": "hermano", "f": "hermana"},
    "grandparent": {"m": "abuelo", "f": "abuela"},
    "grandchild": {"m": "nieto", "f": "nieta"},
    "spouse": {"m": "marido", "f": "mujer"},
}
PLAIN = {
    "parent": "familia",
    "child": "criatura",
    "sibling": "familia",
    "grandparent": "familia",
    "grandchild": "familia",
    "spouse": "pareja",
}


@dataclass
class KinRecord:
    """One person in the settlement's families, living here, dead or never let in."""

    name: str
    gender: str = ""
    # Whose child they are by birth, and who took them in besides.
    parents: list[str] = field(default_factory=list)
    adoptive: list[str] = field(default_factory=list)
    # Brothers and sisters known as such without their parents being known.
    siblings: list[str] = field(default_factory=list)
    spouse: str | None = None


class Kinship:
    """Reads and writes of the settlement's kin records."""

    def record(self, world: "SimulationWorld", person_id: str, name: str = "", gender: str = "") -> KinRecord:
        """Somebody's record, made if they had none. What is given of them is filled in."""
        kin = world.kinship.setdefault(person_id, KinRecord(name or person_id, gender))
        kin.name, kin.gender = name or kin.name, gender or kin.gender
        return kin

    def parents_of(self, world: "SimulationWorld", person_id: str) -> list[str]:
        """Somebody's parents: those they were born to, then those who took them in."""
        kin = world.kinship.get(person_id)
        return [*kin.parents, *(each for each in kin.adoptive if each not in kin.parents)] if kin is not None else []

    def children_of(self, world: "SimulationWorld", person_id: str) -> list[str]:
        return [
            child_id for child_id, kin in world.kinship.items() if person_id in kin.parents or person_id in kin.adoptive
        ]

    def siblings_of(self, world: "SimulationWorld", person_id: str) -> list[str]:
        """Brothers and sisters: whoever shares a parent, and whoever is known as one."""
        kin = world.kinship.get(person_id)
        if kin is None:
            return []
        mine = set(self.parents_of(world, person_id))
        found = [other for other in kin.siblings if other != person_id]
        for other_id in world.kinship:
            if other_id != person_id and other_id not in found and mine & set(self.parents_of(world, other_id)):
                found.append(other_id)
        return found

    def spouse_of(self, world: "SimulationWorld", person_id: str) -> str | None:
        kin = world.kinship.get(person_id)
        return kin.spouse if kin is not None else None

    def tie(self, world: "SimulationWorld", person_id: str, other_id: str) -> str | None:
        """What `other_id` is to `person_id`, as close kin go: `parent`, `child`, `sibling`,
        `grandparent`, `grandchild` or `spouse`. None for anybody else."""
        if person_id == other_id:
            return None
        parents = self.parents_of(world, person_id)
        if other_id in parents:
            return "parent"
        if person_id in self.parents_of(world, other_id):
            return "child"
        if other_id in self.siblings_of(world, person_id):
            return "sibling"
        if any(other_id in self.parents_of(world, parent) for parent in parents):
            return "grandparent"
        if any(person_id in self.parents_of(world, parent) for parent in self.parents_of(world, other_id)):
            return "grandchild"
        return "spouse" if self.spouse_of(world, person_id) == other_id else None

    def close(self, world: "SimulationWorld", person_id: str, other_id: str) -> bool:
        """Whether two people are kin by blood or by having been taken in, close enough that
        there is never romance between them."""
        return self.tie(world, person_id, other_id) not in (None, "spouse")

    def word(self, world: "SimulationWorld", person_id: str, other_id: str) -> str:
        """What somebody calls one of their kin: `hermana`, `padre`, `hijo`."""
        tie = self.tie(world, person_id, other_id)
        other = world.kinship.get(other_id)
        if tie is None:
            return "conocido"
        return WORDS[tie].get(other.gender if other is not None else "", PLAIN[tie])

    def make_siblings(self, world: "SimulationWorld", one_id: str, other_id: str) -> None:
        for mine, theirs in ((one_id, other_id), (other_id, one_id)):
            kin = world.kinship.get(mine)
            if kin is not None and theirs not in kin.siblings:
                kin.siblings.append(theirs)

    def tree(self, world: "SimulationWorld", person_id: str) -> dict[str, list[tuple[str, str, bool]]]:
        """Somebody's family, for whoever draws it: for each kind of kin, the ID, the name and
        whether they live in the settlement, the dead and the absent included."""
        parents = self.parents_of(world, person_id)
        groups = {
            "grandparents": [each for parent in parents for each in self.parents_of(world, parent)],
            "parents": parents,
            "siblings": self.siblings_of(world, person_id),
            "spouse": [each for each in [self.spouse_of(world, person_id)] if each is not None],
            "children": self.children_of(world, person_id),
            "grandchildren": [
                each for child in self.children_of(world, person_id) for each in self.children_of(world, child)
            ],
        }
        return {
            tie: [
                (each, world.kinship[each].name if each in world.kinship else each, each in world.residents)
                for each in dict.fromkeys(people)
            ]
            for tie, people in groups.items()
        }
