"""What is found that nobody knows (S59): a thing brought back from outside, left by a
caravan, come upon while taking something apart, or in the pockets of whoever comes to stay.

The game settles what it is, out of the kinds of `data/finds.json`, and what it does. The
player says what it is called and draws it, and no more. Until then it waits, as what is come
to at a job does (S47), and it is the same machinery that makes an item of it: a kind here is
written as a kind there, with nothing to pick.

Whether one turns up, which and how many come of a die of their own: nothing here throws
the settlement's.
"""

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from simulation.economy.ledger import FOUND
from simulation.events.event import DomainEvent
from simulation.residents.resident import Resident
from simulation.rng import SimulationRNG
from simulation.work.craft import Discovery, KindDefinition, kind_from_data

if TYPE_CHECKING:
    from simulation.world import SimulationWorld

FOUND_EVENT = "discovery_made"
FOUND_IMPORTANCE = 60
BROUGHT_EVENT = "find_brought"
BROUGHT_IMPORTANCE = 30


@dataclass(frozen=True)
class FindSource:
    """Somewhere a thing nobody knows may come from."""

    source_id: str
    # How likely one is to turn up each time something comes that way, and how many of it.
    chance: float = 0.0
    units: tuple[int, int] = (1, 1)
    # What is said when it turns up, and what is said of the thing ever after: `{name}` is
    # whoever found it.
    found: str = "{name} da con algo que nadie conoce"
    told: str = "Lo encontró {name}."
    # Whether whoever found it keeps it, and not the settlement.
    keeps: bool = False


@dataclass(frozen=True)
class FindSettings:
    # The kinds of thing there are to find, written as the kinds a job teaches, and how often
    # each turns up beside the others.
    kinds: dict[str, KindDefinition] = field(default_factory=dict)
    weights: dict[str, float] = field(default_factory=dict)
    sources: dict[str, FindSource] = field(default_factory=dict)
    # How many may wait to be named before no more turn up.
    most_waiting: int = 2
    # Who is said to have found what nobody in particular did.
    nobody: str = "alguien"

    @property
    def enabled(self) -> bool:
        return bool(self.kinds) and bool(self.sources)


def find_settings_from_data(data: dict[str, Any]) -> FindSettings:
    defaults = FindSettings()
    kinds, weights = {}, {}
    for kind_id, values in data.get("kinds", {}).items():
        kind = kind_from_data(str(kind_id), {key: value for key, value in values.items() if key != "weight"})
        if kind.item is None or kind.choices:
            raise ValueError(f"A kind of thing to find is an item with nothing to pick: {kind_id}")
        kinds[kind.kind_id] = kind
        weights[kind.kind_id] = float(values.get("weight", 1.0))
        if weights[kind.kind_id] <= 0:
            raise ValueError(f"A kind of thing to find turns up sometimes: {kind_id}")
    sources = {}
    for source_id, values in data.get("sources", {}).items():
        if not isinstance(values, dict):
            raise ValueError(f"Where things are found needs a chance and how many: {source_id}")
        low, high = (int(each) for each in values.get("units", (1, 1)))
        source = FindSource(
            source_id=str(source_id),
            chance=float(values.get("chance", 0.0)),
            units=(low, high),
            found=str(values.get("found", FindSource.found)),
            told=str(values.get("told", FindSource.told)),
            keeps=bool(values.get("keeps", False)),
        )
        if not 0.0 <= source.chance <= 1.0 or not 1 <= low <= high:
            raise ValueError(f"Something is found a time in so many, one of it or more: {source_id}")
        sources[source.source_id] = source
    settings = FindSettings(
        kinds=kinds,
        weights=weights,
        sources=sources,
        most_waiting=int(data.get("most_waiting", defaults.most_waiting)),
        nobody=str(data.get("nobody", defaults.nobody)),
    )
    if settings.most_waiting < 0:
        raise ValueError("No fewer than no finds wait to be named")
    return settings


class FindSystem:
    def settings(self, world: "SimulationWorld") -> FindSettings:
        return world.registries.finds

    def waiting(self, world: "SimulationWorld") -> list[Discovery]:
        """What has been found that the player has not named yet, oldest first."""
        return [discovery for discovery in world.discoveries.values() if discovery.source and not discovery.named]

    def maybe(
        self, world: "SimulationWorld", source_id: str, by: Resident | None = None, by_name: str = ""
    ) -> Discovery | None:
        """Something has come into the settlement one of the ways things do: now and then
        there is something among it that nobody knows. `by` is whoever found it, where
        anybody did, and `by_name` who is said to have where nobody of the settlement did."""
        settings = self.settings(world)
        source = settings.sources.get(source_id)
        if source is None or not settings.enabled or len(self.waiting(world)) >= settings.most_waiting:
            return None
        who = by.resident_id if by is not None else ""
        dice = SimulationRNG.keyed(world.rng.seed, "find", source_id, who, world.clock.total_minutes)
        if dice.random() >= source.chance:
            return None
        return self.find(world, source_id, by, by_name, dice)

    def find(
        self,
        world: "SimulationWorld",
        source_id: str,
        by: Resident | None = None,
        by_name: str = "",
        dice: SimulationRNG | None = None,
        kind_id: str | None = None,
    ) -> Discovery | None:
        """Have something nobody knows turn up, for certain: which kind and how many come of
        the die, unless the kind is said. It waits to be named, and is said to have turned up."""
        settings = self.settings(world)
        source = settings.sources.get(source_id)
        if source is None or not settings.kinds or (kind_id is not None and kind_id not in settings.kinds):
            return None
        who = by.resident_id if by is not None else ""
        if dice is None:
            dice = SimulationRNG.keyed(world.rng.seed, "find", source_id, who, world.clock.total_minutes, "sure")
        if kind_id is None:
            mark = dice.random() * sum(settings.weights.values())
            for kind_id, weight in settings.weights.items():
                mark -= weight
                if mark < 0:
                    break
        name = by.name if by is not None else (by_name or settings.nobody)
        world.discovery_count += 1
        discovery = Discovery(
            discovery_id=f"discovery_{world.discovery_count}",
            kind=str(kind_id),
            job_id="",
            by=who,
            by_name=name,
            day=world.clock.day,
            source=source_id,
            units=dice.randint(*source.units),
            owner=who if source.keeps and who else None,
        )
        world.discoveries[discovery.discovery_id] = discovery
        world.emit_event(
            DomainEvent(
                FOUND_EVENT,
                FOUND_IMPORTANCE,
                f"{source.found.replace('{name}', name)}: falta decir qué es",
                [who] if who else [],
                data={
                    "discovery": discovery.discovery_id, "resident_id": who, "kind": discovery.kind,
                    "source": source_id, "units": discovery.units,
                },
            ),
            at=by.tile if by is not None and not by.away else None,
        )
        return discovery

    def told(self, world: "SimulationWorld", discovery: Discovery) -> str:
        """What is said of a thing that was found, ever after: where it came from."""
        source = self.settings(world).sources.get(discovery.source)
        return (source.told if source is not None else FindSource.told).replace("{name}", discovery.by_name)

    def named(self, world: "SimulationWorld", discovery: Discovery) -> None:
        """What was found has been named and is an item like any other: what there was of it
        is whoever found it's own, if it was theirs to keep and they are still here, and
        otherwise waits at the gate to be carried in, as the settlement's."""
        item_id, units = discovery.item_id, discovery.units
        if item_id is None or units <= 0:
            return
        keeper = world.residents.get(discovery.owner or "")
        if keeper is not None:
            world.stock(keeper.inventory, item_id, units, keeper.resident_id)
        else:
            world.at_gate[item_id] = world.at_gate.get(item_id, 0) + units
            world.ledger.record(world, item_id, units, FOUND, by=discovery.by or None)
        discovery.units = 0
        thing = world.registries.items.resolve(item_id)
        whose = f"de {keeper.name}" if keeper is not None else "de todos, y espera en la puerta"
        world.emit_event(
            DomainEvent(
                BROUGHT_EVENT,
                BROUGHT_IMPORTANCE,
                f"Hay {thing.name} ({units}): es {whose}",
                [keeper.resident_id] if keeper is not None else [],
                data={"discovery": discovery.discovery_id, "item": item_id, "units": units, "owner": discovery.owner},
            )
        )
