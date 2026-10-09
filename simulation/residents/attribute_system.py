"""Attributes at work (S46): what somebody has, what is left of it today, and how use raises it.

Whoever comes to live in the settlement has what the seed gives them, always the same for the
same settlement and person, unless they were made with something else: the first resident,
whose points the player shares out, and a child, who takes after whichever parents live here.
From then on what they do raises it, slowly and more slowly the higher it is. Age and injuries
take from what they can do today without touching what they have.
"""

from collections.abc import Mapping
from typing import TYPE_CHECKING

from simulation.events.event import DomainEvent
from simulation.residents.attributes import ATTRIBUTES, CHARISMA, OWN, AttributeSettings, Attributes
from simulation.residents.resident import Resident
from simulation.rng import SimulationRNG

if TYPE_CHECKING:
    from simulation.work.job import JobDefinition
    from simulation.world import SimulationWorld
    from world.interactable import Interactable

GREW_EVENT = "attribute_grew"
GREW_IMPORTANCE = 20


class AttributeSystem:
    def settings(self, world: "SimulationWorld") -> AttributeSettings:
        return world.registries.attributes

    # ----- what somebody has -----

    def of(self, world: "SimulationWorld", resident: Resident) -> Attributes:
        """A resident's attributes, made the first time they are asked for."""
        if resident.attributes is None:
            resident.attributes = self._born_with(world, resident)
        return resident.attributes

    def _born_with(self, world: "SimulationWorld", resident: Resident) -> Attributes:
        settings = self.settings(world)
        record = world.kinship.get(resident.resident_id)
        parents = [
            self.of(world, world.residents[parent_id])
            for parent_id in (record.parents if record is not None else [])
            if parent_id in world.residents and parent_id != resident.resident_id
        ]
        made = Attributes()
        for name in OWN:
            own = SimulationRNG.keyed(world.rng.seed, "attribute", resident.resident_id, name)
            value = settings.middle + (own.random() - own.random()) * settings.spread
            if parents:
                theirs = sum(getattr(parent, name) for parent in parents) / len(parents)
                value = settings.inherit * theirs + (1.0 - settings.inherit) * value
            setattr(made, name, round(settings.clamp(value), 1))
        return made

    def raw(self, world: "SimulationWorld", resident: Resident, name: str) -> float:
        """What a resident has of an attribute, whatever today leaves of it."""
        settings = self.settings(world)
        if name == CHARISMA:
            share = max(0.0, min(100.0, resident.personality.charisma)) / 100.0
            return settings.lowest + share * (settings.highest - settings.lowest)
        return getattr(self.of(world, resident), name)

    def value(self, world: "SimulationWorld", resident: Resident, name: str) -> float:
        """What a resident can bring to bear of an attribute today: less for the years on
        them, for the growing they still have to do, and for what they are hurt."""
        settings = self.settings(world)
        value = self.raw(world, resident, name)
        if name in settings.ages and resident.age > settings.age_from:
            value -= (resident.age - settings.age_from) * settings.age_per_year
        if name in settings.grows and resident.age < settings.grown_at:
            value *= settings.youth_floor + (1.0 - settings.youth_floor) * max(0, resident.age) / settings.grown_at
        if name in settings.injured and resident.injuries:
            value *= 1.0 - settings.injured_share * (100.0 - resident.health) / 100.0
        return settings.clamp(value)

    def level(self, world: "SimulationWorld", resident: Resident, name: str) -> int:
        """An attribute as it is shown: whole points of what they can bring to bear today."""
        return int(self.value(world, resident, name) + 1e-9)

    def levels(self, world: "SimulationWorld", resident: Resident) -> dict[str, int]:
        return {name: self.level(world, resident, name) for name in ATTRIBUTES}

    # ----- what it changes -----

    def factor(self, world: "SimulationWorld", resident: Resident, name: str, effect: str) -> float:
        """How many times as much of a thing somebody gets for an attribute: 1 in the middle."""
        settings = self.settings(world)
        each = settings.effects.get(effect, 0.0)
        if each == 0.0:
            return 1.0
        return max(0.1, 1.0 + (self.value(world, resident, name) - settings.middle) * each)

    def bonus(self, world: "SimulationWorld", resident: Resident, name: str, effect: str) -> int:
        """How many more of a thing somebody gets for an attribute, or fewer: none in the middle."""
        settings = self.settings(world)
        each = settings.effects.get(effect, 0.0)
        if each == 0.0:
            return 0
        return round((self.value(world, resident, name) - settings.middle) * each)

    def work_pace(self, world: "SimulationWorld", resident: Resident, job: "JobDefinition") -> float:
        """How fast a resident gets on with a job, for the attribute it goes by."""
        return self.factor(world, resident, job.stat, "work_pace") if job.stat is not None else 1.0

    # ----- being given some, and gaining some -----

    def give(self, world: "SimulationWorld", resident: Resident, values: Mapping[str, float], points: bool = False) -> None:
        """Have a resident be as they were made. What is left out is in the middle.

        With `points`, all six together come to no more than the first resident has to share
        out: what is over is taken from each by how far above the lowest it is.
        """
        settings = self.settings(world)
        made = {
            name: settings.clamp(float(values[name])) if name in values else settings.middle for name in ATTRIBUTES
        }
        if CHARISMA not in values:
            made[CHARISMA] = self.raw(world, resident, CHARISMA)
        over = sum(made.values()) - settings.founder_points
        above = sum(value - settings.lowest for value in made.values())
        if points and over > 0 and above > 0:
            made = {name: value - over * (value - settings.lowest) / above for name, value in made.items()}
        resident.attributes = Attributes(**{name: round(made[name], 2) for name in OWN})
        span = settings.highest - settings.lowest
        resident.personality.charisma = round((made[CHARISMA] - settings.lowest) / span * 100.0, 1)

    def practise(
        self,
        world: "SimulationWorld",
        resident: Resident,
        name: str | None,
        what: str,
        times: float = 1.0,
        cap: float | None = None,
    ) -> None:
        """Have a resident gain a little of an attribute by using it: the higher they are, the
        less each time, and with `cap` no further than that. It is said when it comes to a
        whole point more."""
        settings = self.settings(world)
        amount = settings.practice.get(what, 0.0) * times
        if name is None or amount <= 0.0:
            return
        before = self.raw(world, resident, name)
        room = (settings.highest - before) / max(0.1, settings.highest - settings.middle)
        after = settings.clamp(before + amount * max(0.0, room))
        if cap is not None:
            after = max(before, min(after, cap))
        if after == before:
            return
        if name == CHARISMA:
            span = settings.highest - settings.lowest
            resident.personality.charisma = (after - settings.lowest) / span * 100.0
        else:
            setattr(self.of(world, resident), name, after)
        if int(after + 1e-9) > int(before + 1e-9):
            definition = settings.attributes.get(name)
            called = definition.name.lower() if definition is not None else name
            world.emit_event(
                DomainEvent(
                    GREW_EVENT,
                    GREW_IMPORTANCE,
                    f"{resident.name} gana en {called}: {int(after + 1e-9)}",
                    [resident.resident_id],
                    data={"resident_id": resident.resident_id, "attribute": name, "level": int(after + 1e-9)},
                )
            )

    # ----- training (S57) -----

    def trains(self, world: "SimulationWorld", placed: "Interactable | None") -> str | None:
        """The attribute a thing is for practising. None for what is for nothing of the kind."""
        use = world.definition_of(placed).use if placed is not None else None
        return use.trains if use is not None and use.trains in ATTRIBUTES else None

    def train_cap(self, world: "SimulationWorld", placed: "Interactable") -> float:
        """How far a thing to train at takes an attribute: so far for a common one, and
        further for each rarity past it, up to the highest there is."""
        settings = self.settings(world)
        return settings.clamp(settings.train_cap + settings.train_per_level * (max(1, placed.level) - 1))

    def learns_at(self, world: "SimulationWorld", resident: Resident, placed: "Interactable | None") -> bool:
        """Whether a resident still has something to gain at a thing to train at."""
        name = self.trains(world, placed)
        return name is not None and self.raw(world, resident, name) < self.train_cap(world, placed) - 1e-9

    def train(self, world: "SimulationWorld", resident: Resident, placed: "Interactable") -> None:
        """A minute at a thing to train at: a little more of what it is for, as far as it goes."""
        self.practise(world, resident, self.trains(world, placed), "train", cap=self.train_cap(world, placed))

    def training(self, world: "SimulationWorld", resident: Resident) -> tuple[str, float] | None:
        """What a resident is training right now and how far along the next point of it they
        are, from 0 to 1. None for whoever is not at a thing to train at, and for whoever
        is at one for something else it offers (S60): a game of darts trains nothing."""
        activity = resident.activity
        if activity is None or not activity.using or activity.path:
            return None
        placed = world.interactables.get(activity.target_id or "")
        use = world.definition_of(placed).use_named(activity.action) if placed is not None else None
        if use is None or use.trains not in ATTRIBUTES:
            return None
        return use.trains, self.raw(world, resident, use.trains) % 1.0

    def tick_day(self, world: "SimulationWorld") -> None:
        """A day of leading tells on whoever leads."""
        leader = world.politics.leader(world)
        if leader is not None and not leader.away:
            self.practise(world, leader, CHARISMA, "lead")
