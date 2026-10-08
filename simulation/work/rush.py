"""Pushing a post (S52): a shift worked harder than it should be, at the player's word.

Whoever is pushed makes more for what is left of their shift, tires and frays faster, and every
unit they turn out may end badly: they are hurt, their tool breaks, or what they were making is
lost and some of what the post held with it. The more tired they are the likelier, and the
better at it, by the attribute the job goes by and their level at it, the less. Whatever goes
wrong ends the push, and they trust the player the less for it.

What a push does and what it risks is data. Nobody is pushed unless told: with nobody pushed no
dice are thrown here, and a settlement goes exactly as it would without any of it.
"""

import math
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from simulation.economy.ledger import SPOILED
from simulation.events.event import DomainEvent
from simulation.items.inventory import Inventory
from simulation.items.item import ItemInstance
from simulation.memory.memory import Memory
from simulation.residents.attributes import CONSTITUTION
from simulation.residents.needs import NEED_NAMES
from simulation.residents.resident import Resident
from simulation.work.job import JobDefinition
from world.interactable import Interactable

if TYPE_CHECKING:
    from simulation.world import SimulationWorld

# What can go wrong.
HURT, TOOL, SPOIL, BREAKDOWN = "hurt", "tool", "spoil", "breakdown"
MISHAPS = (HURT, TOOL, SPOIL, BREAKDOWN)
PUSH_EVENT = "work_pushed"
ACCIDENT_EVENT = "work_accident"
PUSH_IMPORTANCE = 20
ACCIDENT_IMPORTANCE = 45
ACCIDENT_MEMORY = 30.0
ACCIDENT_CAUSE = "apretar en el trabajo"
# What being hurt at work leaves somebody with at the least: nobody dies of having been pushed.
LEAST_HEALTH = 8.0
# The effect of an attribute on how likely a push is to end badly, among those of `data/attributes.json`.
MISHAP_EFFECT = "mishap"


@dataclass(frozen=True)
class Mishap:
    """One way a push can end badly."""

    weight: float = 1.0
    # What is told of it, with `{name}`, `{job}` and `{thing}`.
    text: str = ""
    # For being hurt: the kinds of injury there are to come by, each with how often and how bad.
    injuries: dict[str, tuple[float, tuple[int, int]]] = field(default_factory=dict)
    # For what is lost: the share of what there was of it, and how many units at the most.
    fraction: float = 0.0
    most: int = 0


@dataclass(frozen=True)
class RushSettings:
    # How many times as fast whoever is pushed works.
    pace: float = 1.0
    # What a minute of it adds to their needs, beside what the job does.
    per_minute: dict[str, float] = field(default_factory=dict)
    # The chance that a unit turned out pushed ends badly, for somebody rested, middling and new to it.
    risk: float = 0.0
    # For work that turns out no units: how many minutes of it count as one for what may go wrong.
    check_minutes: int = 30
    # How tired they have to be for it to be likelier, and how many times as likely worn right out.
    tired_from: float = 50.0
    tired_risk: float = 1.0
    # How much of the risk each level they have at the job past the first takes off.
    level_relief: float = 0.0
    # What an accident does to how far they trust the player, and to their spirits, and what they remember of it.
    trust: float = 0.0
    mood: float = 0.0
    memory: str = ""
    mishaps: dict[str, Mishap] = field(default_factory=dict)

    @property
    def enabled(self) -> bool:
        return self.pace > 1.0


def rush_settings_from_data(data: dict[str, Any]) -> RushSettings:
    defaults = RushSettings()
    per_minute = {str(need): float(delta) for need, delta in data.get("per_minute", {}).items()}
    if any(need not in NEED_NAMES for need in per_minute):
        raise ValueError("A push changes a need there is not")
    mishaps = {}
    for name, values in data.get("mishaps", {}).items():
        if name not in MISHAPS or not isinstance(values, dict):
            raise ValueError(f"A push can only end badly in one of {MISHAPS}, each with what it does: {name}")
        injuries = {}
        for kind, injury in values.get("injuries", {}).items():
            low, high = (int(value) for value in injury["harm"])
            if not 0 < low <= high or float(injury.get("weight", 1.0)) <= 0:
                raise ValueError(f"Being hurt at a push ({kind}) needs harm above nothing, and a weight above nothing")
            injuries[str(kind)] = (float(injury.get("weight", 1.0)), (low, high))
        mishap = Mishap(
            weight=float(values.get("weight", 1.0)),
            text=str(values.get("text", "")),
            injuries=injuries,
            fraction=float(values.get("fraction", 0.0)),
            most=int(values.get("most", 0)),
        )
        if mishap.weight <= 0 or not 0.0 <= mishap.fraction <= 1.0 or mishap.most < 0:
            raise ValueError(f"What goes wrong at a push ({name}) needs a weight above nothing, and a share from 0 to 1")
        if name == HURT and not injuries:
            raise ValueError("Being hurt at a push needs the injuries there are to come by")
        mishaps[str(name)] = mishap
    settings = RushSettings(
        pace=float(data.get("pace", defaults.pace)),
        per_minute=per_minute,
        risk=float(data.get("risk", defaults.risk)),
        check_minutes=int(data.get("check_minutes", defaults.check_minutes)),
        tired_from=float(data.get("tired_from", defaults.tired_from)),
        tired_risk=float(data.get("tired_risk", defaults.tired_risk)),
        level_relief=float(data.get("level_relief", defaults.level_relief)),
        trust=float(data.get("trust", defaults.trust)),
        mood=float(data.get("mood", defaults.mood)),
        memory=str(data.get("memory", defaults.memory)),
        mishaps=mishaps,
    )
    if settings.pace < 1.0 or not 0.0 <= settings.risk <= 1.0 or settings.check_minutes < 1:
        raise ValueError("A push makes work no slower, risks from nothing to everything, and is looked at every minute or more")
    if settings.tired_risk < 1.0 or not 0.0 <= settings.tired_from < 100.0 or not 0.0 <= settings.level_relief <= 1.0:
        raise ValueError("Being tired makes a push no safer, and a level takes off some of the risk or none")
    return settings


class RushSystem:
    def settings(self, world: "SimulationWorld") -> RushSettings:
        return world.registries.rush

    # ----- being pushed -----

    def pushed(self, world: "SimulationWorld", resident: Resident) -> bool:
        """Whether a resident is working a shift harder than it should be."""
        return world.clock.total_minutes < resident.pushing_until

    def pushable(self, world: "SimulationWorld", job: JobDefinition | None, resident: Resident | None = None) -> bool:
        """Whether there is anything about a job to push: something made, worked out or, for
        whoever holds it, come to at it. Work done outside the settlement is not."""
        if job is None or not job.rush or job.expedition is not None:
            return False
        if job.produces is not None or job.research:
            return True
        return resident is not None and bool(world.crafts.products(world, resident, job))

    def obstacle(self, world: "SimulationWorld", resident: Resident) -> str | None:
        """Why a resident cannot be told to push their post right now. None if they can."""
        job = world.work.job_of(world, resident)
        if not self.settings(world).enabled or job is None or resident.post_id not in world.interactables:
            return f"{resident.name} no tiene puesto en el que apretar"
        if not self.pushable(world, job, resident):
            return f"En ese puesto no hay nada que apretar: {job.name}"
        if resident.away or not world.health.is_fit_for_work(resident):
            return f"{resident.name} no está para apretar"
        if world.work.shift_minutes_left(world, resident, job) <= 0:
            return f"{resident.name} no está de turno"
        if self.pushed(world, resident):
            return f"{resident.name} ya va apretando"
        return None

    def push(self, world: "SimulationWorld", resident: Resident) -> str | None:
        """Have a resident push their post for what is left of their shift. Returns why they
        could not, if they could not."""
        error = self.obstacle(world, resident)
        if error is not None:
            return error
        job = world.work.job_of(world, resident)
        resident.pushing_until = world.clock.total_minutes + world.work.shift_minutes_left(world, resident, job)
        world.emit_event(
            DomainEvent(
                PUSH_EVENT,
                PUSH_IMPORTANCE,
                f"{resident.name} aprieta en su puesto: {job.name}",
                [resident.resident_id],
                data={"resident_id": resident.resident_id, "job": job.job_id, "until": resident.pushing_until},
            ),
            at=resident.tile,
        )
        return None

    def ease(self, resident: Resident) -> None:
        """Have a resident go back to working as anybody does."""
        resident.pushing_until = 0

    # ----- what it does -----

    def pace(self, world: "SimulationWorld", resident: Resident) -> float:
        """How many times as fast a resident works for being pushed: once, for whoever is not."""
        return self.settings(world).pace if self.pushed(world, resident) else 1.0

    def toll(self, world: "SimulationWorld", resident: Resident, per_minute: dict[str, float]) -> dict[str, float]:
        """What a minute at a job does to whoever does it, with what being pushed adds."""
        if not self.pushed(world, resident):
            return per_minute
        added = dict(per_minute)
        for need, delta in self.settings(world).per_minute.items():
            added[need] = added.get(need, 0.0) + delta
        return added

    # ----- what it risks -----

    def risk(self, world: "SimulationWorld", resident: Resident, job: JobDefinition) -> float:
        """The chance that the unit a pushed resident turns out next ends badly, from 0 to 1."""
        settings = self.settings(world)
        tired = max(0.0, resident.needs.tiredness - settings.tired_from) / (100.0 - settings.tired_from)
        risk = settings.risk * (1.0 + (settings.tired_risk - 1.0) * min(1.0, tired))
        if job.stat is not None:
            # Whoever has more of what the job goes by is surer at it.
            risk *= max(0.0, 2.0 - world.attributes.factor(world, resident, job.stat, MISHAP_EFFECT))
        risk *= max(0.0, 1.0 - settings.level_relief * (world.crafts.level(world, resident, job.job_id) - 1))
        return max(0.0, min(1.0, risk))

    def after_unit(self, world: "SimulationWorld", resident: Resident, job: JobDefinition, placed: Interactable) -> None:
        """A pushed resident has turned out a unit: it may have ended badly."""
        if not self.pushed(world, resident):
            return
        if world.rng.random() < self.risk(world, resident, job):
            self._go_wrong(world, resident, job, placed)

    def after_minute(self, world: "SimulationWorld", resident: Resident, job: JobDefinition, placed: Interactable) -> None:
        """A pushed resident has spent a minute at work that turns out no units: every so many
        of them count as one, for what may go wrong."""
        if not self.pushed(world, resident) or world.clock.total_minutes % self.settings(world).check_minutes:
            return
        if world.rng.random() < self.risk(world, resident, job):
            self._go_wrong(world, resident, job, placed)

    def _go_wrong(self, world: "SimulationWorld", resident: Resident, job: JobDefinition, placed: Interactable) -> None:
        settings = self.settings(world)
        tool = world.work.tool_of(world, resident, job)
        within_reach = {
            HURT: True,
            TOOL: tool is not None,
            SPOIL: bool(self._at_stake(world, resident, job, placed)),
            # The post itself may give out, where posts wear at all (S55).
            BREAKDOWN: world.wear.settings(world).enabled and not world.wear.broken(world, placed.object_id),
        }
        choices = [(name, mishap) for name, mishap in settings.mishaps.items() if within_reach.get(name)]
        if not choices:
            return
        mark = world.rng.random() * sum(mishap.weight for _, mishap in choices)
        for name, mishap in choices:
            mark -= mishap.weight
            if mark < 0:
                break
        self.ease(resident)
        thing, units = "", 0
        if name == TOOL and tool is not None:
            definition = world.registries.items.resolve(tool.definition_id)
            thing = f"{definition.article} {definition.name}"
            world.items.shatter(world, resident, tool)
        elif name == SPOIL:
            units = self._spoil(world, resident, job, placed, mishap)
        elif name == BREAKDOWN:
            world.wear.break_down(world, placed)
        text = mishap.text.replace("{name}", resident.name).replace("{job}", job.name).replace("{thing}", thing)
        room = world.room_at(resident.tile)
        world.emit_event(
            DomainEvent(
                ACCIDENT_EVENT,
                ACCIDENT_IMPORTANCE,
                text,
                [resident.resident_id],
                location_id=room.room_id if room is not None else None,
                data={"resident_id": resident.resident_id, "job": job.job_id, "mishap": name, "units": units},
            ),
            at=resident.tile,
        )
        # They were told to, and it turned out badly for them.
        world.politics.influence.judged(world, resident, settings.trust)
        resident.adjust_mood(settings.mood)
        if settings.memory:
            world.memories.remember(
                resident.resident_id,
                Memory(settings.memory, ACCIDENT_MEMORY, -0.5, tags=["work", "accident"], timestamp=world.clock.total_minutes),
            )
        if name == HURT:
            self._hurt(world, resident, mishap)

    def _hurt(self, world: "SimulationWorld", resident: Resident, mishap: Mishap) -> None:
        mark = world.rng.random() * sum(weight for weight, _ in mishap.injuries.values())
        for kind, (weight, harm) in mishap.injuries.items():
            mark -= weight
            if mark < 0:
                break
        amount = float(world.rng.randint(*harm))
        # However bad, it leaves them alive: what is taken off is never all they have left.
        tough = max(0.1, 2.0 - world.attributes.factor(world, resident, CONSTITUTION, "toughness"))
        amount = min(amount, max(0.0, resident.health - LEAST_HEALTH) / tough)
        if amount > 0:
            world.health.hurt(world, resident, amount, kind, ACCIDENT_CAUSE)

    def _at_stake(
        self, world: "SimulationWorld", resident: Resident, job: JobDefinition, placed: Interactable
    ) -> list[tuple[Inventory, ItemInstance]]:
        """What of the settlement's a pushed resident has made and still has by them: in their
        hands, at their post, and where what is come to at the job is kept."""
        made = set(world.crafts.extra_items(world, resident))
        if job.produces is not None:
            made |= {job.produces.item, *job.produces.also}
        holders = [resident.inventory]
        if placed.object_id in world.containers:
            holders.append(world.containers[placed.object_id])
        kind = world.crafts.kind_of(world, job.job_id)
        kept = world.crafts.store(world, kind, placed) if kind is not None and job.produces is None else None
        if kept is not None and world.containers.get(kept) not in holders:
            holders.append(world.containers[kept])
        return [
            (inventory, item)
            for inventory in holders
            for item in inventory.items
            if item.owner_id is None and item.definition_id in made
        ]

    def _spoil(
        self, world: "SimulationWorld", resident: Resident, job: JobDefinition, placed: Interactable, mishap: Mishap
    ) -> int:
        """Lose what was being made, and a share of what there was of it by them. Returns how many units."""
        resident.work_progress = 0
        lost = 0
        for inventory, item in self._at_stake(world, resident, job, placed):
            left = mishap.most - lost if mishap.most else item.quantity
            gone = inventory.take_units(item.instance_id, min(left, max(1, math.ceil(item.quantity * mishap.fraction))))
            world.ledger.record(world, item.definition_id, -gone, SPOILED, by=resident.resident_id, at=placed.object_id)
            lost += gone
            if mishap.most and lost >= mishap.most:
                break
        return lost
