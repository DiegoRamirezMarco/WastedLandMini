"""Work paid in credits, and what they buy: goods over a counter, a drink, a repair."""

import math
from typing import TYPE_CHECKING

from simulation.ai.utility_ai import need_urgency
from simulation.events.event import DomainEvent
from simulation.items.inventory import Inventory
from simulation.items.item import WORN_CONDITION, ItemDefinition, ItemInstance
from simulation.items.item_system import FOOD_CATEGORY
from simulation.items.registry import UNKNOWN_CATEGORY
from simulation.residents.activity import Activity
from simulation.residents.needs import NEED_NAMES
from simulation.residents.resident import Resident
from simulation.work.job import JobDefinition
from world.interactable import UseDefinition

if TYPE_CHECKING:
    from simulation.world import SimulationWorld

REPAIR_APPEAL = 0.5
SHOP_APPEAL = 0.5
# How much a resident wants something they have no pressing use for, before its price is weighed.
BASE_DESIRE = 0.3
# Below this a thing is not worth the walk to the counter.
MIN_WANT = 0.25
MAX_WANT = 1.25
# Units of food of their own a resident keeps before they stop buying more.
STASH_SIZE = 2
# Fear of someone from which a resident wants something to defend themselves with.
ARM_FEAR = 30.0
PURCHASE_IMPORTANCE = 15
MINUTES_PER_HOUR = 60.0


class TradeSystem:
    # ----- earning -----

    def pay_wage(self, world: "SimulationWorld", resident: Resident, job: JobDefinition) -> None:
        """Credit a resident with one minute's wage."""
        wage = job.wage if job.wage is not None else world.registries.economy.wage_per_hour
        resident.credits += wage / MINUTES_PER_HOUR

    def pay(self, resident: Resident, price: float) -> bool:
        """Take a price out of a resident's credits. False, and nothing taken, if they are short."""
        if resident.credits < price:
            return False
        resident.credits -= price
        return True

    # ----- buying over a counter -----

    def price_of(self, world: "SimulationWorld", definition: ItemDefinition, in_stock: int) -> int:
        """What one unit costs. The fewer there are left, the dearer."""
        economy = world.registries.economy
        scarcity = 1.0 + economy.scarcity_markup / max(1, in_stock)
        return math.ceil(definition.base_value * economy.price_factor * scarcity)

    def want(self, world: "SimulationWorld", resident: Resident, definition: ItemDefinition, price: int) -> float:
        """How much a resident wants to buy something at a price, from 0 to `MAX_WANT`.

        A tool for their own job when they have none comes first. A weapon is wanted out of fear.
        Anything else is weighed by what it would do for them now against what it costs.
        """
        if definition.category == UNKNOWN_CATEGORY or price <= 0:
            return 0.0
        job = world.work.job_of(world, resident)
        if job is not None and job.tool is not None and job.tool.tag in definition.tags:
            return 0.0 if self._carries_tagged(world, resident, job.tool.tag) else MAX_WANT
        if definition.properties.get("damage", 0.0) > 1.0:
            if world.health.weapon_of(world, resident)[0] > 1.0:
                return 0.0
            fear = max(
                (
                    feelings.fear
                    for (source_id, target_id), feelings in world.relationships.items()
                    if source_id == resident.resident_id and target_id in world.residents
                ),
                default=0.0,
            )
            return min(MAX_WANT, fear / 100.0 * 1.5) if fear >= ARM_FEAR else 0.0
        relief = sum(
            need_urgency(resident, need)
            for need, delta in world.items.use_effects(world, resident, definition).items()
            if delta < 0 and need in NEED_NAMES
        )
        owned = self._owned_units(world, resident, definition.item_id)
        if relief <= 0 and not definition.effects:
            return 0.0
        if owned >= (STASH_SIZE if definition.category == FOOD_CATEGORY else 1):
            return 0.0
        bargain = world.items.personal_value(world, resident, definition) / price
        return min(MAX_WANT, bargain * (BASE_DESIRE + relief))

    def best_buy(
        self, world: "SimulationWorld", resident: Resident, container_id: str
    ) -> tuple[ItemInstance, int, float] | None:
        """What a resident would buy from a counter right now: the item, its price and how much they want it."""
        container = world.containers.get(container_id)
        if container is None:
            return None
        best: tuple[ItemInstance, int, float] | None = None
        for item in container.items:
            if item.owner_id is not None or item.broken:
                continue
            definition = world.registries.items.resolve(item.definition_id)
            price = self.price_of(world, definition, container.count(item.definition_id))
            if price > resident.credits:
                continue
            want = self.want(world, resident, definition, price)
            if want >= MIN_WANT and (best is None or want > best[2]):
                best = (item, price, want)
        return best

    def shop_score(self, world: "SimulationWorld", resident: Resident, container_id: str) -> float | None:
        """How much a resident wants to go to a counter and buy something. None if nothing tempts them."""
        choice = self.best_buy(world, resident, container_id)
        return choice[2] * SHOP_APPEAL if choice is not None else None

    def buy(self, world: "SimulationWorld", resident: Resident, container_id: str) -> str | None:
        """Buy the thing a resident wants most from a counter. Returns its definition ID, or None."""
        choice = self.best_buy(world, resident, container_id)
        if choice is None:
            return None
        item, price, _ = choice
        container = world.containers[container_id]
        if not self.pay(resident, price):
            return None
        if item.quantity > 1:
            item.quantity -= 1
            world.stock(resident.inventory, item.definition_id, 1, resident.resident_id)
        else:
            container.remove(item.instance_id)
            item.owner_id = resident.resident_id
            resident.inventory.add(item)
        definition = world.registries.items.resolve(item.definition_id)
        room = world.room_at(resident.tile)
        world.emit_event(
            DomainEvent(
                "item_bought",
                PURCHASE_IMPORTANCE,
                f"{resident.name} compra {definition.article} {definition.name} por {price} vales",
                [resident.resident_id],
                location_id=room.room_id if room is not None else None,
            ),
            at=resident.tile,
        )
        return item.definition_id

    def _carries_tagged(self, world: "SimulationWorld", resident: Resident, tag: str) -> bool:
        return any(tag in world.registries.items.resolve(item.definition_id).tags for item in resident.inventory.items)

    def _owned_units(self, world: "SimulationWorld", resident: Resident, definition_id: str) -> int:
        """How many of something a resident already has, on them or put away."""
        inventories = [resident.inventory, *world.containers.values()]
        return sum(
            item.quantity
            for inventory in inventories
            for item in inventory.items
            if item.definition_id == definition_id and item.owner_id == resident.resident_id
        )

    # ----- repairs -----

    def worn_item(self, world: "SimulationWorld", resident: Resident) -> ItemInstance | None:
        """The most worn thing of their own a resident has on them that is worth repairing."""
        worn = [
            item
            for item in resident.inventory.items
            if item.owner_id == resident.resident_id
            and item.condition < WORN_CONDITION
            and world.registries.items.resolve(item.definition_id).properties.get("wear", 0.0) > 0
        ]
        return min(worn, key=lambda item: (item.condition, item.instance_id), default=None)

    def repair_score(self, world: "SimulationWorld", resident: Resident, use: UseDefinition) -> float | None:
        """How much a resident wants something of theirs repaired. None if nothing needs it, or if
        there is nothing to repair it with."""
        item = self.worn_item(world, resident)
        if item is None or (use.material is not None and self.repair_material(world, use) is None):
            return None
        return REPAIR_APPEAL * (1.0 - max(0.0, item.condition) / 100.0)

    def repair_material(self, world: "SimulationWorld", use: UseDefinition) -> tuple[Inventory, ItemInstance] | None:
        """A unit of what a repair is made with, and where it is, if the settlement has any."""
        for object_id, inventory in world.containers.items():
            placed = world.interactables.get(object_id)
            if placed is None or placed.kind != use.material_from:
                continue
            for item in inventory.items:
                if item.owner_id is None and use.material in world.registries.items.resolve(item.definition_id).tags:
                    return (inventory, item)
        return None

    def take_repair_material(self, world: "SimulationWorld", use: UseDefinition) -> bool:
        """Use up what one repair takes. True if the repair needs nothing, or there was some."""
        if use.material is None:
            return True
        material = self.repair_material(world, use)
        if material is None:
            return False
        material[0].take_unit(material[1].instance_id)
        return True

    def repair_minute(self, world: "SimulationWorld", activity: Activity, use: UseDefinition) -> bool:
        """Mend the thing being repaired for one minute. True once there is no more to be done.

        The work is the repairer's, so it stops when they leave their post.
        """
        item = world.items.find_item(world, activity.item_id or "")
        if item is None or (use.staffed_by is not None and not world.work.is_staffed(world, use.staffed_by)):
            return True
        item.condition = min(100.0, max(0.0, item.condition) + use.repairs)
        return item.condition >= 100.0
