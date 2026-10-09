"""Taking things apart for what they are made of.

What lies about the settlement and is good for nothing else, a rusted car or a heap of tyres,
can be taken apart by a resident who is told to: it is a task of theirs until it is done, and
then the thing is gone and what came out of it is in their hands. And the player can break up
an item for scrap: what is nobody's at once, and what is somebody's only if they agree to it.
"""

from dataclasses import dataclass
from typing import TYPE_CHECKING

from simulation.ai.navigation import path_beside
from simulation.ai.utility_ai import ScoredAction
from simulation.economy.ledger import SALVAGED, USED
from simulation.events.event import DomainEvent
from simulation.items.inventory import Inventory
from simulation.items.item import ItemInstance
from simulation.memory.memory import Memory
from simulation.residents.activity import Activity
from simulation.residents.resident import Resident
from simulation.work.hauling import containers_of_kind
from world.interactable import Interactable, SalvageRule
from world.pathfinding import manhattan
from world.urbanism import UrbanismResult

if TYPE_CHECKING:
    from simulation.world import SimulationWorld

SALVAGE_ACTION = "salvage"
# What the owner of a thing makes up their mind about when the player would have it broken up.
SCRAP_PROPOSAL = "scrap_proposal"
# The property of an item that says how many units of scrap one of it comes to.
SCRAP_PROPERTY = "scrap"
ORDERED_IMPORTANCE = 20
SALVAGED_IMPORTANCE = 30
SCRAPPED_IMPORTANCE = 20
SCRAP_MEMORY = 30.0
ADVICE = "encourage"


@dataclass
class Salvage:
    """Something a resident has been told to take apart, and how far along they are with it."""

    object_id: str
    resident_id: str
    # Minutes of work done so far.
    progress: float = 0.0


class SalvageSystem:
    # ----- what can be taken apart -----

    def rule_of(self, world: "SimulationWorld", placed: Interactable) -> SalvageRule | None:
        definition = world.registries.interactables.find(placed.kind)
        rule = definition.salvage if definition is not None else None
        return rule if rule is not None and world.registries.items.find(rule.item) is not None else None

    def available(self, world: "SimulationWorld", tag: str | None = None) -> list[Interactable]:
        """What there is about that could be taken apart and nobody has been told to yet, in
        map order. With `tag`, only what gives something that carries it."""
        found = []
        for object_id, placed in world.interactables.items():
            rule = self.rule_of(world, placed)
            if rule is None or object_id in world.salvage:
                continue
            if tag is not None and tag not in world.registries.items.resolve(rule.item).tags:
                continue
            found.append(placed)
        return found

    def of(self, world: "SimulationWorld", resident: Resident) -> list[Salvage]:
        """What a resident has been told to take apart and is still there."""
        return [
            job
            for job in world.salvage.values()
            if job.resident_id == resident.resident_id and job.object_id in world.interactables
        ]

    # ----- being told to -----

    def order(self, world: "SimulationWorld", resident_id: str, object_id: str) -> UrbanismResult:
        """Tell a resident to take something apart. It is theirs to do from then on, as their
        work, until it is done. Told again to somebody else, it is that one's."""
        resident = world.residents.get(resident_id)
        placed = world.interactables.get(object_id)
        if resident is None:
            return UrbanismResult(False, "No hay a quién decírselo")
        if resident.away:
            return UrbanismResult(False, f"{resident.name} está fuera del asentamiento")
        if placed is None:
            return UrbanismResult(False, "Eso ya no está")
        rule = self.rule_of(world, placed)
        if rule is None:
            return UrbanismResult(False, "De eso no se saca nada")
        if not world.health.is_fit_for_work(resident):
            return UrbanismResult(False, f"{resident.name} no está para eso")
        if world.containers.get(object_id) is not None and world.containers[object_id].items:
            return UrbanismResult(False, "Hay que vaciarlo antes")
        definition = world.definition_of(placed)
        before = world.salvage.get(object_id)
        world.salvage[object_id] = Salvage(object_id, resident_id, before.progress if before is not None else 0.0)
        if before is not None and before.resident_id != resident_id:
            other = world.residents.get(before.resident_id)
            if other is not None and other.activity is not None and other.activity.target_id == object_id:
                other.activity = None
                other.current_action = "idle"
        text = f"{resident.name} va a desguazar {definition.article} {definition.name}"
        world.emit_event(
            DomainEvent(
                "salvage_ordered", ORDERED_IMPORTANCE, text, [resident_id], data={"object_id": object_id}
            ),
            at=(placed.x, placed.y),
        )
        return UrbanismResult(True, text, object_id)

    def cancel(self, world: "SimulationWorld", object_id: str) -> bool:
        """Have nobody take a thing apart after all. Returns whether somebody was going to."""
        job = world.salvage.pop(object_id, None)
        if job is None:
            return False
        resident = world.residents.get(job.resident_id)
        if resident is not None and resident.activity is not None and resident.activity.action == SALVAGE_ACTION:
            if resident.activity.target_id == object_id:
                resident.activity = None
                resident.current_action = "idle"
        return True

    # ----- doing it -----

    def task(self, world: "SimulationWorld", resident: Resident, score: float) -> ScoredAction | None:
        """The nearest thing a resident has been told to take apart, as something to do next."""
        mine = self.of(world, resident)
        if not mine:
            return None

        def distance(job: Salvage) -> tuple[int, str]:
            placed = world.interactables[job.object_id]
            return manhattan(resident.tile, (placed.x, placed.y)), job.object_id

        return ScoredAction(SALVAGE_ACTION, score, min(mine, key=distance).object_id)

    def plan(self, world: "SimulationWorld", resident: Resident, candidate: ScoredAction) -> Activity | None:
        placed = world.interactables.get(candidate.target_id or "")
        path = path_beside(world, resident, placed) if placed is not None else None
        if path is None:
            return None
        return Activity(SALVAGE_ACTION, placed.object_id, path, world.registries.construction.stint_minutes)

    def tick(self, world: "SimulationWorld", resident: Resident, activity: Activity) -> None:
        """Spend one minute taking something apart."""
        job = world.salvage.get(activity.target_id or "")
        placed = world.interactables.get(activity.target_id or "")
        rule = self.rule_of(world, placed) if placed is not None else None
        if job is None or placed is None or rule is None or job.resident_id != resident.resident_id:
            self._leave(resident)
            return
        if not world.construction.free_to_build(world, resident):
            self._leave(resident)
            return
        definition = world.definition_of(placed)
        if not activity.using:
            activity.using = True
            resident.current_action = SALVAGE_ACTION
            room = world.room_at(resident.tile)
            world.emit_event(
                DomainEvent(
                    "salvage_started",
                    5,
                    f"{resident.name} se pone a desguazar {definition.article} {definition.name}",
                    [resident.resident_id],
                    location_id=room.room_id if room is not None else None,
                    data={"object_id": placed.object_id},
                )
            )
        resident.needs.apply(world.registries.construction.per_minute)
        # Taking a thing apart for the settlement is work like any other.
        world.trade.pay_wage(world, resident, world.work.job_of(world, resident))
        job.progress += world.health.work_pace(world, resident) * world.work.mood_pace(resident)
        activity.minutes_left -= 1
        if job.progress >= rule.minutes:
            self._finish(world, resident, placed, rule)
        elif activity.minutes_left <= 0:
            self._leave(resident)

    def _finish(self, world: "SimulationWorld", resident: Resident, placed: Interactable, rule: SalvageRule) -> None:
        definition = world.definition_of(placed)
        item = world.registries.items.resolve(rule.item)
        tiles = set(placed.footprint(definition))
        del world.interactables[placed.object_id]
        world.containers.pop(placed.object_id, None)
        world.salvage.pop(placed.object_id, None)
        world.urbanism.invalidate_routes(world, tiles, target_ids={placed.object_id})
        world.stock(resident.inventory, rule.item, rule.units, None)
        world.ledger.record(world, rule.item, rule.units, SALVAGED, by=resident.resident_id)
        # Something nobody knows may have been inside (S59).
        world.finds.maybe(world, "salvage", resident)
        self._leave(resident)
        world.emit_event(
            DomainEvent(
                "object_salvaged",
                SALVAGED_IMPORTANCE,
                f"{resident.name} desguaza {definition.article} {definition.name}: saca {rule.units} de {item.name}",
                [resident.resident_id],
                data={
                    "object_id": placed.object_id, "kind": placed.kind, "tile": [placed.x, placed.y],
                    "item_id": rule.item, "units": rule.units,
                },
            ),
            at=(placed.x, placed.y),
        )

    def _leave(self, resident: Resident) -> None:
        resident.activity = None
        resident.current_action = "idle"

    # ----- breaking an item up -----

    def scrap_units(self, world: "SimulationWorld", item: ItemInstance) -> int:
        """Units of scrap an item comes to, all of it together. None for what is good for nothing broken up."""
        definition = world.registries.items.resolve(item.definition_id)
        return int(definition.properties.get(SCRAP_PROPERTY, 0.0)) * item.quantity

    def _holder(self, world: "SimulationWorld", instance_id: str) -> tuple[Inventory, str | None, Resident | None] | None:
        """Where an item is: the inventory, and the container or the resident it belongs to."""
        for object_id, inventory in world.containers.items():
            if inventory.find(instance_id) is not None:
                return inventory, object_id, None
        for resident in world.residents.values():
            if resident.inventory.find(instance_id) is not None:
                return resident.inventory, None, resident
        return None

    def scrap_item(self, world: "SimulationWorld", item_id: str, option_id: str | None = ADVICE) -> UrbanismResult:
        """The player has an item broken up for scrap. What is nobody's is broken up there and
        then. What is somebody's is put to them, and they say whether they will have it."""
        scrap = world.registries.items.find(world.registries.construction.scrap_item)
        found = self._holder(world, item_id)
        if found is None or scrap is None:
            return UrbanismResult(False, "Eso ya no está")
        inventory, container_id, carrier = found
        item = inventory.find(item_id)
        definition = world.registries.items.resolve(item.definition_id)
        thing = f"{definition.article} {definition.name}"
        units = self.scrap_units(world, item)
        if units <= 0 or item.definition_id == scrap.item_id:
            return UrbanismResult(False, f"De eso no sale chatarra: {definition.name}")
        owner = world.residents.get(item.owner_id or "")
        if item.owner_id is None:
            if carrier is not None or item.meant_for is not None:
                return UrbanismResult(False, "Eso va de camino a alguna parte")
        elif owner is None or owner.away:
            return UrbanismResult(False, "Su dueño no está para preguntárselo")
        else:
            if SCRAP_PROPOSAL not in world.registries.decisions:
                return UrbanismResult(False, "No hay manera de pedírselo")
            asked = world.interventions.asking_obstacle(world, owner, SCRAP_PROPOSAL)
            if asked == "deciding":
                return UrbanismResult(False, f"{owner.name} tiene otra cosa en la cabeza")
            if asked is not None:
                return UrbanismResult(False, f"{owner.name} ya ha dicho que no: vuelve a intentarlo más tarde")
            worth = world.items.personal_value(world, owner, definition, item)
            inputs = {"bargain": max(0.0, 1.0 - worth / 100.0)}
            outcome = world.interventions.put_to(world, owner, SCRAP_PROPOSAL, thing, inputs, option_id)
            if outcome is None or not outcome.agrees:
                return UrbanismResult(False, f"{owner.name} no quiere que se desguace {thing}")
            world.memories.remember(
                owner.resident_id,
                Memory(
                    f"Di {thing} para chatarra.", SCRAP_MEMORY, -0.2, [], ["salvage"], world.clock.total_minutes
                ),
            )
        inventory.remove(item_id)
        if item.owner_id is None:
            world.ledger.record(world, item.definition_id, -item.quantity, USED)
        where = self._store(world, scrap.item_id, container_id, carrier)
        if where is not None:
            world.stock(world.containers[where], scrap.item_id, units, None)
            world.ledger.record(world, scrap.item_id, units, SALVAGED, at=where)
        tile = None
        if container_id is not None and container_id in world.interactables:
            tile = (world.interactables[container_id].x, world.interactables[container_id].y)
        elif carrier is not None:
            tile = carrier.tile
        text = f"Se desguaza {thing}: salen {units} de {scrap.name}"
        world.emit_event(
            DomainEvent(
                "item_scrapped",
                SCRAPPED_IMPORTANCE,
                text,
                [owner.resident_id] if owner is not None else [],
                data={"item_id": item.definition_id, "units": units, "into": where},
            ),
            at=tile,
        )
        return UrbanismResult(True, text, where)

    def _store(
        self, world: "SimulationWorld", scrap_id: str, container_id: str | None, carrier: Resident | None
    ) -> str | None:
        """Where the scrap of something broken up is left: where the settlement keeps scrap, the
        nearest such place, and failing that where the thing was or the nearest container."""
        near = carrier.tile if carrier is not None else None
        if container_id is not None and container_id in world.interactables:
            near = (world.interactables[container_id].x, world.interactables[container_id].y)
        tags = world.registries.items.resolve(scrap_id).tags
        kinds = [rule.to for rule in world.registries.expeditions.deliveries if rule.tag is not None and rule.tag in tags]
        places = [object_id for kind in kinds for object_id, _inventory in containers_of_kind(world, kind)]
        if places and near is not None:
            return min(
                places,
                key=lambda each: (manhattan(near, (world.interactables[each].x, world.interactables[each].y)), each),
            )
        if places:
            return places[0]
        if container_id is not None:
            return container_id
        return world.nearest_container(near) if near is not None else None
