"""Carrying: what a job makes or needs goes from one place to another in the worker's hands."""

from typing import TYPE_CHECKING

from simulation.items.inventory import Inventory
from simulation.items.item import ItemInstance
from simulation.residents.resident import Resident
from simulation.work.job import INTO_STATION, ProduceRule
from world.interactable import Interactable

if TYPE_CHECKING:
    from simulation.world import SimulationWorld

# A worker does not set out for raw material with less of their shift than this left.
MIN_FETCH_MINUTES = 30


def carried(resident: Resident, item_id: str) -> int:
    """Units of something a worker has on them that are nobody's in particular."""
    stack = resident.inventory.stack_of(item_id, None)
    return stack.quantity if stack is not None else 0


def containers_of_kind(world: "SimulationWorld", kind: str) -> list[tuple[str, Inventory]]:
    return [
        (object_id, inventory)
        for object_id, inventory in world.containers.items()
        if object_id in world.interactables and world.interactables[object_id].kind == kind
    ]


def _raw_stack(world: "SimulationWorld", rule: ProduceRule, inventory: Inventory) -> ItemInstance | None:
    """The fullest shared stack in an inventory of something the rule can be made from."""
    best: ItemInstance | None = None
    for item in inventory.items:
        definition = world.registries.items.resolve(item.definition_id)
        if item.owner_id is not None or definition.category != rule.source_category:
            continue
        if rule.skip_tag is not None and rule.skip_tag in definition.tags:
            continue
        if best is None or item.quantity > best.quantity:
            best = item
    return best


def raw_carried(world: "SimulationWorld", resident: Resident, rule: ProduceRule) -> ItemInstance | None:
    """Raw material the worker has on them, if any."""
    return _raw_stack(world, rule, resident.inventory)


def delivery_target(world: "SimulationWorld", rule: ProduceRule) -> str | None:
    """Where to take what was made: the emptiest container of the receiving kind that has room."""
    options = [
        (inventory.count(rule.item), object_id)
        for object_id, inventory in containers_of_kind(world, rule.into)
        if inventory.count(rule.item) < rule.max_stock
    ]
    return min(options)[1] if options else None


def fetch_source(world: "SimulationWorld", rule: ProduceRule) -> str | None:
    """Where to fetch raw material from: the container with the fullest stack of it."""
    best: tuple[int, str] | None = None
    for object_id, inventory in containers_of_kind(world, rule.source or ""):
        stack = _raw_stack(world, rule, inventory)
        if stack is not None and (best is None or stack.quantity > best[0]):
            best = (stack.quantity, object_id)
    return best[1] if best is not None else None


def errand(world: "SimulationWorld", resident: Resident, rule: ProduceRule, shift_minutes_left: int) -> str | None:
    """The container a worker should walk to now, to hand in what they carry or to fetch raw material.

    What was made is handed in once the worker's hands are full, or when the shift is over. Raw
    material is fetched when they have none, while there is shift enough left to use it.
    """
    on_them = carried(resident, rule.item)
    if rule.into != INTO_STATION and on_them > 0 and (on_them >= rule.carry or shift_minutes_left <= 0):
        target = delivery_target(world, rule)
        if target is not None:
            return target
    if rule.source is None or shift_minutes_left < MIN_FETCH_MINUTES:
        return None
    if raw_carried(world, resident, rule) is not None:
        return None
    if rule.into == INTO_STATION:
        post = world.containers.get(resident.post_id or "")
        if post is None or post.count(rule.item) >= rule.max_stock:
            return None
    return fetch_source(world, rule)


def exchange(world: "SimulationWorld", resident: Resident, rule: ProduceRule, placed: Interactable) -> str | None:
    """Hand in or pick up at the container a worker has walked to.

    Returns what they did, as the rest of a sentence about them, or None if there was nothing to do.
    """
    container = world.containers.get(placed.object_id)
    if container is None:
        return None
    definition = world.definition_of(placed)
    where = f"{definition.article} {definition.name}"
    on_them = resident.inventory.stack_of(rule.item, None)
    if placed.kind == rule.into and on_them is not None:
        units = min(on_them.quantity, rule.max_stock - container.count(rule.item))
        if units <= 0:
            return None
        resident.inventory.take_units(on_them.instance_id, units)
        world.stock(container, rule.item, units, None)
        return f"lleva {units} de {world.registries.items.resolve(rule.item).name} a {where}"
    if placed.kind == rule.source:
        stack = _raw_stack(world, rule, container)
        if stack is None:
            return None
        definition_id = stack.definition_id
        units = container.take_units(stack.instance_id, rule.carry)
        world.stock(resident.inventory, definition_id, units, None)
        return f"coge {units} de {world.registries.items.resolve(definition_id).name} de {where}"
    return None
