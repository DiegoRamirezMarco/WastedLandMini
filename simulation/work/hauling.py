"""Carrying: what a job makes or needs goes from one place to another in the worker's hands."""

from typing import TYPE_CHECKING

from simulation.items.inventory import Inventory
from simulation.items.item import ItemInstance
from simulation.residents.attributes import STRENGTH
from simulation.residents.resident import Resident
from simulation.work.job import INTO_STATION, ProduceRule, SupplyRule
from world.interactable import Interactable

if TYPE_CHECKING:
    from simulation.world import SimulationWorld

# A worker does not set out for raw material with less of their shift than this left.
MIN_FETCH_MINUTES = 30


def carried(resident: Resident, item_id: str) -> int:
    """Units of something a worker has on them that are nobody's in particular."""
    stack = resident.inventory.stack_of(item_id, None)
    return stack.quantity if stack is not None else 0


def made_items(world: "SimulationWorld", resident: Resident, rule: ProduceRule) -> tuple[str, ...]:
    """Everything a worker makes under a rule: what the job gives anybody, and what they have
    come to at it or been shown (S47)."""
    return (rule.item, *world.crafts.extra_items(world, resident))


def carried_made(world: "SimulationWorld", resident: Resident, rule: ProduceRule) -> int:
    """Units of what a worker makes that they have on them, nobody's in particular."""
    return sum(carried(resident, item_id) for item_id in made_items(world, resident, rule))


def room(world: "SimulationWorld", resident: Resident, rule: ProduceRule, inventory: Inventory) -> int:
    """How many more units of what a job makes a container takes: what the job makes and
    what anybody has come to at it share the room there is, so that a pantry holds as much of
    the garden as it did, of more kinds."""
    family = {rule.item, *world.crafts.family(world, resident.job_id)}
    return rule.max_stock - sum(inventory.count(item_id) for item_id in family)


def wanted_raw(world: "SimulationWorld", resident: Resident, rule: ProduceRule, inventory: Inventory) -> ItemInstance | None:
    """The stack in a container of the one thing something the worker makes is made of, when
    their post has less of that than of what the job gives anybody: what is fetched for it."""
    post = world.containers.get(resident.post_id or "")
    job = world.registries.jobs.get(resident.job_id or "")
    if post is None or job is None:
        return None
    best: tuple[int, ItemInstance] | None = None
    for product in world.crafts.products(world, resident, job):
        stack = inventory.stack_of(product.needs, None) if product.needs is not None and product.ripe else None
        have = post.count(product.item_id)
        if stack is not None and have < max(1, post.count(rule.item)) and (best is None or have < best[0]):
            best = (have, stack)
    return best[1] if best is not None else None


def kept(world: "SimulationWorld", resident: Resident, rule: ProduceRule, item_id: str) -> int:
    """Units of a thing where what the rule makes is taken, and on the worker on their way there."""
    stored = sum(inventory.count(item_id) for _, inventory in containers_of_kind(world, rule.into))
    return stored + carried(resident, item_id)


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


def delivery_target(world: "SimulationWorld", rule: ProduceRule, resident: Resident | None = None) -> str | None:
    """Where to take what was made: the emptiest container of the receiving kind that has room.
    With `resident`, room is what is left once everything their job makes is counted."""
    options = []
    for object_id, inventory in containers_of_kind(world, rule.into):
        left = room(world, resident, rule, inventory) if resident is not None else rule.max_stock - inventory.count(rule.item)
        if left > 0:
            options.append((rule.max_stock - left, object_id))
    return min(options)[1] if options else None


def fetch_source(world: "SimulationWorld", rule: ProduceRule) -> str | None:
    """Where to fetch raw material from: the container with the fullest stack of it."""
    best: tuple[int, str] | None = None
    for object_id, inventory in containers_of_kind(world, rule.source or ""):
        stack = _raw_stack(world, rule, inventory)
        if stack is not None and (best is None or stack.quantity > best[0]):
            best = (stack.quantity, object_id)
    return best[1] if best is not None else None


def load(world: "SimulationWorld", resident: Resident, rule: ProduceRule | SupplyRule) -> int:
    """How many units a resident carries in one trip of a job's: what the job says, and one
    or two more or fewer for how strong they are."""
    return max(1, rule.carry + world.attributes.bonus(world, resident, STRENGTH, "carry"))


def errand(world: "SimulationWorld", resident: Resident, rule: ProduceRule, shift_minutes_left: int) -> str | None:
    """The container a worker should walk to now, to hand in what they carry or to fetch raw material.

    What was made is handed in once the worker's hands are full, or when the shift is over. Raw
    material is fetched when they have none, while there is shift enough left to use it.
    """
    on_them = carried_made(world, resident, rule)
    if rule.into != INTO_STATION and on_them > 0 and (on_them >= load(world, resident, rule) or shift_minutes_left <= 0):
        target = delivery_target(world, rule, resident)
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


def _supply_source(world: "SimulationWorld", rule: SupplyRule) -> tuple[int, str] | None:
    """The fullest shared stack of what is supplied that lies anywhere but where it goes, and its container."""
    best: tuple[int, str] | None = None
    for object_id, inventory in world.containers.items():
        placed = world.interactables.get(object_id)
        stack = inventory.stack_of(rule.item, None)
        if placed is None or placed.kind == rule.into or stack is None:
            continue
        if best is None or stack.quantity > best[0]:
            best = (stack.quantity, object_id)
    return best


def supply_errand(world: "SimulationWorld", resident: Resident, rule: SupplyRule, shift_minutes_left: int) -> str | None:
    """The container a worker should walk to now, to keep what they look after supplied.

    What they carry is taken where it goes, shift or no shift. They go for more when a full load
    of it is lying somewhere, or at once, for whatever there is, when what they look after runs low.
    """
    receiving = [
        (inventory.count(rule.item), object_id)
        for object_id, inventory in containers_of_kind(world, rule.into)
        if inventory.count(rule.item) < rule.max_stock
    ]
    if not receiving:
        return None
    held, target = min(receiving)
    if carried(resident, rule.item) > 0:
        return target
    source = _supply_source(world, rule) if shift_minutes_left >= MIN_FETCH_MINUTES else None
    if source is None:
        return None
    return source[1] if held < rule.low or source[0] >= rule.carry else None


def supply_exchange(world: "SimulationWorld", resident: Resident, rule: SupplyRule, placed: Interactable) -> str | None:
    """Leave or pick up what is supplied at the container a worker has walked to. Returns what they did."""
    container = world.containers.get(placed.object_id)
    if container is None:
        return None
    definition = world.definition_of(placed)
    where = f"{definition.article} {definition.name}"
    name = world.registries.items.resolve(rule.item).name
    on_them = resident.inventory.stack_of(rule.item, None)
    if placed.kind == rule.into:
        units = min(on_them.quantity, rule.max_stock - container.count(rule.item)) if on_them is not None else 0
        if units <= 0:
            return None
        resident.inventory.take_units(on_them.instance_id, units)
        world.stock(container, rule.item, units, None)
        return f"lleva {units} de {name} a {where}"
    stack = container.stack_of(rule.item, None)
    if stack is None or on_them is not None:
        return None
    units = container.take_units(stack.instance_id, load(world, resident, rule))
    world.stock(resident.inventory, rule.item, units, None)
    return f"coge {units} de {name} de {where}"


def exchange(world: "SimulationWorld", resident: Resident, rule: ProduceRule, placed: Interactable) -> str | None:
    """Hand in or pick up at the container a worker has walked to.

    Returns what they did, as the rest of a sentence about them, or None if there was nothing to do.
    """
    container = world.containers.get(placed.object_id)
    if container is None:
        return None
    definition = world.definition_of(placed)
    where = f"{definition.article} {definition.name}"
    if placed.kind == rule.into:
        left = []
        for item_id in made_items(world, resident, rule):
            on_them = resident.inventory.stack_of(item_id, None)
            units = min(on_them.quantity, room(world, resident, rule, container)) if on_them is not None else 0
            if units <= 0:
                continue
            resident.inventory.take_units(on_them.instance_id, units)
            world.stock(container, item_id, units, None)
            left.append(f"{units} de {world.registries.items.resolve(item_id).name}")
        if left:
            return f"lleva {' y '.join(left)} a {where}"
        if rule.source is None or placed.kind != rule.source:
            return None
    if placed.kind == rule.source:
        # What something of their own is made of comes first, when there is some and it is wanted.
        stack = wanted_raw(world, resident, rule, container) or _raw_stack(world, rule, container)
        if stack is None:
            return None
        definition_id = stack.definition_id
        units = container.take_units(stack.instance_id, load(world, resident, rule))
        world.stock(resident.inventory, definition_id, units, None)
        return f"coge {units} de {world.registries.items.resolve(definition_id).name} de {where}"
    return None
