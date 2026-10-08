"""Better things (S54): whatever stands has a level, and a level is a rarity.

A post, a store, a bed and a generator start out common and can be made better four times
over: uncommon, rare, epic, legendary. Each makes the thing do what it does that much better:
a post is worked faster, a store holds more, a bed rests better, a generator gives more. The
sixth, mythic, is never made here: it is found.

Making a thing better is a site on what already stands, with what it takes carried to it and
worked on, as anything is built (S16), once that rarity has been studied (S17). The thing is
not used meanwhile. What the rarities are, what each takes and how much better it is are data.
"""

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from simulation.events.event import DomainEvent
from simulation.residents.resident import Resident
from world.build import UPGRADE_SITE, BuildRule, BuildSite
from world.interactable import Interactable

if TYPE_CHECKING:
    from simulation.world import SimulationWorld

UPGRADED_EVENT = "object_upgraded"
UPGRADED_IMPORTANCE = 35
BED_NEED = "tiredness"
NOT_THAT = "Eso no se puede mejorar"
NOBODY_KEEPS = "Nadie lleva eso ni hay quien arregle las cosas: no hay a quién proponérselo"
IN_HAND = "Ya hay una obra en ello"


@dataclass(frozen=True)
class Rarity:
    """One step of how rare, and so how good, a thing is."""

    rarity_id: str
    name: str
    # The colour it is known by, wherever things are shown.
    color: tuple[int, int, int] = (236, 229, 212)
    # By how much whatever has it does what it does better than a common one.
    better: float = 1.0
    # The subject that has to be known before a thing can be made this rare. None for what
    # takes no studying.
    study: str | None = None
    # Whether a thing can be made this rare here at all. What cannot is only ever found.
    built: bool = True


@dataclass(frozen=True)
class RaritySettings:
    # The rarities there are, the commonest first: a thing of level 1 has the first.
    tiers: tuple[Rarity, ...] = (Rarity("common", "Común"),)
    # What making a thing one level better takes for the first, by the tag of the items that
    # will do, and in minutes of work. The next takes twice that, and so on.
    cost: dict[str, int] = field(default_factory=dict)
    minutes: int = 0
    # Kinds of object that can be made better besides what is a post, a store or a bed.
    kinds: tuple[str, ...] = ()
    # How often a thing brought from outside is of each rarity, as weights in the order of
    # `tiers`, and by how much every weight past the first is multiplied for whoever went on
    # at something worth a risk (S64). With no weights everything found is common.
    found: tuple[float, ...] = ()
    risk_factor: float = 1.0

    def of(self, level: int) -> Rarity:
        """The rarity a level is. Past either end, the nearest there is."""
        return self.tiers[max(1, min(len(self.tiers), level)) - 1]

    @property
    def highest(self) -> int:
        return len(self.tiers)


def rarity_settings_from_data(data: dict[str, Any]) -> RaritySettings:
    tiers = []
    for rarity_id, values in data.get("tiers", {}).items():
        if not isinstance(values, dict) or "name" not in values:
            raise ValueError(f"Rarity {rarity_id} needs a name")
        color = values.get("color", (236, 229, 212))
        rarity = Rarity(
            rarity_id=str(rarity_id),
            name=str(values["name"]),
            color=(int(color[0]), int(color[1]), int(color[2])),
            better=float(values.get("better", 1.0)),
            study=str(values["study"]) if values.get("study") else None,
            built=bool(values.get("built", True)),
        )
        if rarity.better <= 0 or not all(0 <= part <= 255 for part in rarity.color):
            raise ValueError(f"Rarity {rarity_id} is better by a factor above zero, and has a colour of three parts")
        tiers.append(rarity)
    if not tiers:
        return RaritySettings()
    if any(later.better < earlier.better for earlier, later in zip(tiers, tiers[1:])):
        raise ValueError("Rarities go from the commonest to the rarest: each is at least as good as the one before")
    upgrade = data.get("upgrade", {})
    found = data.get("found", {})
    weights = found.get("weights", {})
    unknown = sorted(set(weights) - {each.rarity_id for each in tiers})
    if unknown:
        raise ValueError(f"What is found is of rarities there are not: {unknown}")
    settings = RaritySettings(
        tiers=tuple(tiers),
        cost={str(tag): int(units) for tag, units in upgrade.get("cost", {}).items()},
        minutes=int(upgrade.get("minutes", 0)),
        kinds=tuple(str(kind) for kind in upgrade.get("kinds", [])),
        found=tuple(float(weights.get(each.rarity_id, 0.0)) for each in tiers) if weights else (),
        risk_factor=float(found.get("risk_factor", 1.0)),
    )
    if any(weight < 0 for weight in settings.found) or settings.risk_factor <= 0:
        raise ValueError("How often a rarity is found is a weight of nothing or more, and a risk multiplies it by more than nothing")
    if settings.minutes < 0 or any(units < 0 for units in settings.cost.values()):
        raise ValueError("Making a thing better takes no less than nothing")
    return settings


class UpgradeSystem:
    def settings(self, world: "SimulationWorld") -> RaritySettings:
        return world.registries.rarities

    # ----- how good a thing is -----

    def rarity(self, world: "SimulationWorld", placed: Interactable | None) -> Rarity:
        """How rare a thing that stands is. Common for what is not there."""
        return self.settings(world).of(placed.level if placed is not None else 1)

    def better(self, world: "SimulationWorld", object_id: str | None) -> float:
        """By how much a thing that stands does what it does better than a common one."""
        return self.rarity(world, world.interactables.get(object_id or "")).better

    def can_be_bettered(self, world: "SimulationWorld", placed: Interactable) -> bool:
        """Whether a thing is of a kind that has levels: a post of some job, a store, a bed,
        or a kind the data names."""
        definition = world.definition_of(placed)
        if definition.store is not None or placed.kind in self.settings(world).kinds:
            return True
        if any(job.works_at(placed.kind) for job in world.registries.jobs.values()):
            return True
        use = definition.use
        return use is not None and use.unaware and use.per_minute.get(BED_NEED, 0.0) < 0

    # ----- making it better -----

    def keeper(self, world: "SimulationWorld", object_id: str) -> Resident | None:
        """Who making a thing better is put to (P60): whoever has it as their post, or else
        holds the job it is a post of; for what stands in somebody's house, whoever the
        house is of; and for what is nobody's, whoever mends what breaks down. None with
        none of them here."""
        placed = world.interactables.get(object_id)
        if placed is None:
            return None
        holder = world.staffing.holder(world, object_id)
        if holder is not None and not holder.away:
            return holder
        job = world.staffing.job_at(world, object_id)
        room = world.housing.room_of(world, placed)
        owners = world.housing.owners(world, room.room_id) if room is not None else []
        candidates = [
            *(world.staffing.workers(world, job.job_id) if job is not None else []),
            *(world.residents[owner_id] for owner_id in owners),
        ]
        here = next((resident for resident in candidates if not resident.away), None)
        return here if here is not None else world.residents.get(world.wear.mender(world) or "")

    def site_of(self, world: "SimulationWorld", object_id: str) -> BuildSite | None:
        """The site at which a thing is being made better, while it is."""
        return next(
            (site for site in world.sites.values() if site.kind == UPGRADE_SITE and site.what == object_id), None
        )

    def in_hand(self, world: "SimulationWorld", object_id: str | None) -> bool:
        """Whether a thing is not to be used right now: it is being made better, or it has
        broken down and waits to be mended (S55)."""
        if object_id is None:
            return False
        if world.wear.broken(world, object_id):
            return True
        return bool(world.sites) and self.site_of(world, object_id) is not None

    def next(self, world: "SimulationWorld", placed: Interactable) -> Rarity | None:
        """The rarity a thing would have if it were made better once more. None at the top."""
        settings = self.settings(world)
        return settings.of(placed.level + 1) if placed.level < settings.highest else None

    def obstacle(self, world: "SimulationWorld", object_id: str) -> str | None:
        """Why a thing cannot be made better right now. None if it can."""
        placed = world.interactables.get(object_id)
        if placed is None or not self.can_be_bettered(world, placed):
            return NOT_THAT
        coming = self.next(world, placed)
        if coming is None or not coming.built:
            return "Mejor que eso no se hace aquí: solo se encuentra"
        if self.site_of(world, object_id) is not None or world.wear.broken(world, object_id):
            return IN_HAND if not world.wear.broken(world, object_id) else "Antes hay que arreglarlo"
        subject = world.registries.research.subjects.get(coming.study or "")
        if subject is not None and not world.research.knows(world, subject.subject_id):
            return f"Antes hay que estudiarlo: {subject.name}"
        return None

    def rule(self, world: "SimulationWorld", object_id: str) -> BuildRule | None:
        """What making a thing one level better takes: the more the better it already is. None
        for what has no level above the one it has."""
        placed = world.interactables.get(object_id)
        if placed is None or self.next(world, placed) is None:
            return None
        settings = self.settings(world)
        return BuildRule(
            {tag: units * placed.level for tag, units in settings.cost.items()}, settings.minutes * placed.level
        )

    def thing(self, world: "SimulationWorld", object_id: str) -> str | None:
        """What the work is called in a sentence: the thing, and how rare it will be."""
        placed = world.interactables.get(object_id)
        coming = self.next(world, placed) if placed is not None else None
        if placed is None or coming is None:
            return None
        definition = world.definition_of(placed)
        return f"mejorar {definition.article} {definition.name} ({coming.name.lower()})"

    def finish(self, world: "SimulationWorld", site: BuildSite) -> str:
        """The work on a thing is done: it is one level better from now on."""
        placed = world.interactables[site.what]
        placed.level = min(self.settings(world).highest, placed.level + 1)
        rarity = self.rarity(world, placed)
        definition = world.definition_of(placed)
        named = f"{definition.article} {definition.name}"
        world.emit_event(
            DomainEvent(
                UPGRADED_EVENT,
                UPGRADED_IMPORTANCE,
                f"{named[0].upper()}{named[1:]} es ahora de calidad: {rarity.name.lower()}",
                data={"object_id": placed.object_id, "kind": placed.kind, "level": placed.level, "rarity": rarity.rarity_id},
            ),
            at=(placed.x, placed.y),
        )
        return placed.object_id

    def found_level(self, world: "SimulationWorld", dice, risked: bool = False) -> int:
        """How rare one thing brought from outside is, drawn with `dice`: seldom anything but
        common, and the oftener for a risk taken."""
        settings = self.settings(world)
        weights = [
            weight * (settings.risk_factor if risked and index else 1.0) for index, weight in enumerate(settings.found)
        ]
        total = sum(weights)
        if total <= 0:
            return 1
        mark = dice.random() * total
        for index, weight in enumerate(weights):
            mark -= weight
            if mark < 0:
                return index + 1
        return 1

