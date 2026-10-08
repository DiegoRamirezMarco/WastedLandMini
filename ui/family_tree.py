"""The families of the whole settlement laid out as trees, one beside another.

Laying it out reads who is kin to whom and nothing else, and is told nothing of how it is drawn.
Each family is a block of rows, one to a generation, with parents over their children and
partners side by side; whoever is kin to nobody here comes after them, in rows of their own.
"""

from collections import defaultdict
from dataclasses import dataclass

from simulation.world import SimulationWorld

# What there is to say of somebody on the tree, by where they are.
HERE, CARRIED, DEAD, ELSEWHERE = "here", "carried", "dead", "elsewhere"
# What ties two people on it.
PARENT, ADOPTIVE, SPOUSE, COUPLE, SIBLING = "parent", "adoptive", "spouse", "couple", "sibling"
# How many columns a band of families is wide before the next goes under it, and the room left
# between two partners' families and between one family and the next.
BAND_COLUMNS = 14
GAP = 0.5
BLOCK_GAP = 1.0


@dataclass(frozen=True)
class Person:
    """Somebody on the tree: who they are, where they are, and their age if they live here."""

    person_id: str
    name: str
    state: str
    age: int | None = None


@dataclass(frozen=True)
class Tie:
    """What one person on the tree is to another. For a parent, `one` is the parent."""

    kind: str
    one: str
    other: str


@dataclass(frozen=True)
class Tree:
    """Everybody on it, where each goes in columns and rows, and what ties them."""

    people: dict[str, Person]
    places: dict[str, tuple[float, float]]
    ties: list[Tie]
    # How many columns and rows it takes in all.
    size: tuple[float, float]
    # Whoever is kin to nobody on it.
    alone: list[str]


def _people(world: SimulationWorld) -> dict[str, Person]:
    """Everybody the settlement has on record: who lives here, the children still carried, the
    dead, and the kin of any of them who never lived here."""
    dead = {death.resident_id: death.name for death in world.deaths}
    people: dict[str, Person] = {}
    for resident_id, resident in world.residents.items():
        people[resident_id] = Person(resident_id, resident.name, HERE, resident.age)
    for child_id, bundle in world.bundles.items():
        people[child_id] = Person(child_id, bundle.name, CARRIED, world.children.age_of(world, bundle))
    for person_id, record in world.kinship.items():
        if person_id not in people:
            people[person_id] = Person(person_id, record.name, DEAD if person_id in dead else ELSEWHERE)
    return people


def _ties(world: SimulationWorld, people: dict[str, Person]) -> list[Tie]:
    ties: list[Tie] = []
    seen: set[tuple[str, frozenset[str]]] = set()

    def add(kind: str, one: str, other: str) -> None:
        # Two who are married are not also tied as a couple, and no tie is put down twice.
        key = ("partners" if kind in (SPOUSE, COUPLE) else kind, frozenset((one, other)))
        if one in people and other in people and one != other and key not in seen:
            seen.add(key)
            ties.append(Tie(kind, one, other))

    for person_id in sorted(world.kinship):
        record = world.kinship[person_id]
        for parent in record.parents:
            add(PARENT, parent, person_id)
        for parent in record.adoptive:
            if parent not in record.parents:
                add(ADOPTIVE, parent, person_id)
        if record.spouse is not None:
            add(SPOUSE, person_id, record.spouse)
    for resident_id in sorted(world.residents):
        partner = world.residents[resident_id].couple_with
        if partner is not None:
            add(COUPLE, resident_id, partner)
    for person_id in sorted(world.kinship):
        mine = set(world.family.kin.parents_of(world, person_id))
        for other in world.kinship[person_id].siblings:
            # Brothers and sisters whose parents are on it are tied through them.
            if not mine & set(world.family.kin.parents_of(world, other)):
                add(SIBLING, person_id, other)
    return ties


def _families(people: dict[str, Person], ties: list[Tie]) -> list[list[str]]:
    """Who goes with whom: everybody tied to one another, family by family, the largest first."""
    beside: dict[str, set[str]] = defaultdict(set)
    for tie in ties:
        beside[tie.one].add(tie.other)
        beside[tie.other].add(tie.one)
    families, seen = [], set()
    for person_id in sorted(people):
        if person_id in seen:
            continue
        family, waiting = [], [person_id]
        seen.add(person_id)
        while waiting:
            current = waiting.pop()
            family.append(current)
            for other in sorted(beside[current]):
                if other not in seen:
                    seen.add(other)
                    waiting.append(other)
        families.append(sorted(family))
    return sorted(families, key=lambda family: (-len(family), family[0]))


def _generations(family: list[str], ties: list[Tie]) -> dict[str, int]:
    """The row each of a family is on: a parent one over their children, partners and brothers
    and sisters on the same. Where the ties cannot all be kept, the first reached is."""
    steps: dict[str, list[tuple[str, int]]] = defaultdict(list)
    for tie in ties:
        down = 1 if tie.kind in (PARENT, ADOPTIVE) else 0
        steps[tie.one].append((tie.other, down))
        steps[tie.other].append((tie.one, -down))
    rows = {family[0]: 0}
    waiting = [family[0]]
    while waiting:
        current = waiting.pop(0)
        for other, step in steps[current]:
            if other not in rows:
                rows[other] = rows[current] + step
                waiting.append(other)
    top = min(rows.values())
    return {person_id: row - top for person_id, row in rows.items()}


def _lay_family(family: list[str], ties: list[Tie]) -> dict[str, tuple[float, float]]:
    """Where each of a family goes, from its own top left corner: children under the middle of
    their parents where there is room, and nobody on top of anybody."""
    inside = [tie for tie in ties if tie.one in family and tie.other in family]
    rows = _generations(family, inside)
    children: dict[str, list[str]] = defaultdict(list)
    partners: dict[str, list[str]] = defaultdict(list)
    has_parent: set[str] = set()
    for tie in inside:
        if tie.kind in (PARENT, ADOPTIVE):
            children[tie.one].append(tie.other)
            has_parent.add(tie.other)
        elif tie.kind in (SPOUSE, COUPLE):
            partners[tie.one].append(tie.other)
            partners[tie.other].append(tie.one)
    # Whoever has a child with somebody stands beside them, partners or not.
    for child in family:
        parents = [tie.one for tie in inside if tie.kind in (PARENT, ADOPTIVE) and tie.other == child]
        for one in parents:
            for other in parents:
                if one != other and other not in partners[one]:
                    partners[one].append(other)
    places: dict[str, tuple[float, float]] = {}
    free: dict[int, float] = defaultdict(float)
    placing: set[str] = set()

    def place(person_id: str) -> None:
        if person_id in places or person_id in placing:
            return
        row = rows[person_id]
        unit = [person_id] + [
            other for other in partners[person_id] if other not in places and other not in placing and rows[other] == row
        ]
        placing.update(unit)
        young = sorted({child for member in unit for child in children[member] if rows[child] == row + 1})
        for child in young:
            place(child)
        under = [places[child][0] for child in young if child in places]
        middle = sum(under) / len(under) if under else free[row] + (len(unit) - 1) / 2
        left = max(free[row], middle - (len(unit) - 1) / 2)
        for index, member in enumerate(unit):
            places[member] = (left + index, float(row))
        free[row] = left + len(unit) + GAP
        placing.difference_update(unit)

    # From the top down, with brothers and sisters known as such kept together.
    order = sorted(family, key=lambda person_id: (person_id in has_parent, rows[person_id], person_id))
    for person_id in order:
        place(person_id)
    left = min(x for x, _ in places.values())
    return {person_id: (x - left, row) for person_id, (x, row) in places.items()}


def family_tree(world: SimulationWorld) -> Tree:
    """The families of everybody the settlement has on record, laid out side by side in bands."""
    people = _people(world)
    ties = _ties(world, people)
    families = _families(people, ties)
    places: dict[str, tuple[float, float]] = {}
    alone = [family[0] for family in families if len(family) == 1]
    x = y = band = widest = 0.0

    def put(block: dict[str, tuple[float, float]], gap: float = BLOCK_GAP) -> None:
        nonlocal x, y, band, widest
        width = max(column for column, _ in block.values()) + 1
        height = max(row for _, row in block.values()) + 1
        if x > 0 and x + width > BAND_COLUMNS:
            x, y, band = 0.0, y + band + GAP, 0.0
        for person_id, (column, row) in block.items():
            places[person_id] = (x + column, y + row)
        x += width + gap
        band = max(band, height)
        widest = max(widest, x - gap)

    for family in families:
        if len(family) > 1:
            put(_lay_family(family, ties))
    if alone and places:
        # Whoever is kin to nobody starts a band of their own, under the families.
        x, y, band = 0.0, y + band + GAP, 0.0
    for person_id in alone:
        put({person_id: (0.0, 0.0)}, gap=0.0)
    size = (max(widest, 1.0), y + max(band, 1.0)) if places else (0.0, 0.0)
    return Tree(people, places, ties, size, alone)
