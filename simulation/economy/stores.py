"""Room for things (S53): the store that what the settlement lives on is kept in.

An `Almacén` is where what is everybody's is kept, and it holds so much of each resource. The
pantry, the tank, the cabinet, the heap of scrap and the generator are where it is taken from
and brought to: what stands free at one of them goes to the store, but for a little kept at
hand, and comes back as it is used. Nobody carries it between the two. A crate keeps none of
it: whatever of it is left in one goes to the store.

With the store full, what is made stays where it was made, and whoever makes it stops as they
do when their own place is full. It is said once a day. A settlement with no store at all goes
on as it always did.
"""

from typing import TYPE_CHECKING

from simulation.events.event import DomainEvent
from simulation.items.inventory import Inventory
from simulation.items.item import ItemInstance

if TYPE_CHECKING:
    from simulation.world import SimulationWorld

FULL_EVENT = "store_full"
FULL_IMPORTANCE = 35
FULL_NOTICE = "store_full:"
# What stands for there being no end to the room there is: no store, or nothing the store keeps.
NO_LIMIT = 10**9


class StoreSystem:
    def stores(self, world: "SimulationWorld") -> list[tuple[str, Inventory, dict[str, int]]]:
        """Every store that stands, in map order: its ID, what is in it, and how much of each
        resource it holds."""
        found = []
        for object_id, inventory in world.containers.items():
            placed = world.interactables.get(object_id)
            rule = world.definition_of(placed).store if placed is not None else None
            if rule is not None:
                # A store that has been made better holds that much more (S54).
                better = world.upgrades.better(world, object_id)
                found.append((object_id, inventory, {name: round(units * better) for name, units in rule.items()}))
        return found

    def stands(self, world: "SimulationWorld") -> bool:
        return bool(self.stores(world))

    def inventories(self, world: "SimulationWorld") -> list[tuple[str, Inventory]]:
        return [(object_id, inventory) for object_id, inventory, _rule in self.stores(world)]

    def capacity(self, world: "SimulationWorld") -> dict[str, int]:
        """How much of each resource the stores hold between them. Empty with no store."""
        room: dict[str, int] = {}
        for _object_id, _inventory, rule in self.stores(world):
            for resource_id, units in rule.items():
                room[resource_id] = room.get(resource_id, 0) + units
        return room

    def held(self, world: "SimulationWorld") -> dict[str, int]:
        """How much of each resource is in the stores right now."""
        held = {resource_id: 0 for resource_id in self.capacity(world)}
        for _object_id, inventory, _rule in self.stores(world):
            for item in inventory.items:
                resource_id = self._resource(world, item)
                if resource_id in held:
                    held[resource_id] += item.quantity
        return held

    def room(self, world: "SimulationWorld") -> dict[str, int]:
        """How much more of each resource the stores would take."""
        held = self.held(world)
        return {resource_id: max(0, units - held[resource_id]) for resource_id, units in self.capacity(world).items()}

    def room_at(self, world: "SimulationWorld", inventory: Inventory, definition_id: str) -> int:
        """How many more units of a thing a place it is brought to would take, by what the
        stores have room for: what it still lacks of what it keeps at hand, and what the stores
        would take off it. No limit where the place gives nothing to a store, or there is none."""
        keeps = self._keeps(world, inventory)
        definition = world.registries.items.find(definition_id)
        if keeps is None or definition is None:
            return NO_LIMIT
        capacity = self.capacity(world)
        for resource_id in world.ledger.resources_of(world, definition):
            if resource_id in keeps and resource_id in capacity:
                lacking = max(0, keeps[resource_id] - inventory.count(definition_id))
                return lacking + self.room(world)[resource_id]
        return NO_LIMIT

    def feeds(self, world: "SimulationWorld", kind: str, definition_id: str | None = None) -> bool:
        """Whether what is kept at a kind of place comes to it from the stores by itself: a
        store stands and that kind keeps something of theirs at hand. With `definition_id`,
        whether that thing does."""
        definition = world.registries.interactables.find(kind)
        keeps = definition.outlet if definition is not None else None
        capacity = self.capacity(world)
        if not keeps or not capacity:
            return False
        if definition_id is None:
            return any(resource_id in capacity for resource_id in keeps)
        item = world.registries.items.find(definition_id)
        counted = world.ledger.resources_of(world, item) if item is not None else ()
        return any(resource_id in keeps and resource_id in capacity for resource_id in counted)

    def kept_through(self, world: "SimulationWorld", kinds) -> set[str]:
        """The resources of the stores that are taken from through some kinds of place: what
        each of those keeps a little of at hand. Nothing with no store."""
        capacity = self.capacity(world)
        through: set[str] = set()
        for kind in kinds:
            definition = world.registries.interactables.find(kind)
            keeps = definition.outlet if definition is not None else None
            through.update(resource_id for resource_id, kept in (keeps or {}).items() if kept > 0 and resource_id in capacity)
        return through

    def resource_of(self, world: "SimulationWorld", item: ItemInstance) -> str | None:
        """The resource a stack counts as for a store, if it is everybody's and whole."""
        return self._resource(world, item)

    def full_of(self, world: "SimulationWorld") -> list[str]:
        """The resources the stores have no room left for."""
        return [resource_id for resource_id, units in self.room(world).items() if units <= 0]

    def tick(self, world: "SimulationWorld") -> None:
        """Each minute: what stands free at a place the store is taken from goes to the store,
        past what that place keeps at hand, and what it lacks of that comes back from it."""
        stores = self.stores(world)
        if not stores:
            return
        capacity = self.capacity(world)
        held = self.held(world)
        for object_id, inventory in world.containers.items():
            placed = world.interactables.get(object_id)
            keeps = world.definition_of(placed).outlet if placed is not None else None
            if keeps is None:
                continue
            at_hand: dict[str, int] = {}
            for item in list(inventory.items):
                resource_id = self._resource(world, item)
                if resource_id not in keeps or resource_id not in capacity:
                    continue
                over = item.quantity - keeps[resource_id]
                if over > 0:
                    held[resource_id] += self._put_away(world, stores, resource_id, inventory, item, over)
                at_hand[item.definition_id] = at_hand.get(item.definition_id, 0) + item.quantity
            for resource_id, kept in keeps.items():
                if kept > 0 and resource_id in capacity:
                    held[resource_id] -= self._bring_out(world, stores, resource_id, inventory, kept, at_hand)
        self._warn(world, capacity, held)

    def _put_away(
        self,
        world: "SimulationWorld",
        stores: list[tuple[str, Inventory, dict[str, int]]],
        resource_id: str,
        inventory: Inventory,
        item: ItemInstance,
        units: int,
    ) -> int:
        """Move up to so many units of a stack into the stores, the first with room first.
        Returns how many went."""
        moved = 0
        for _object_id, store, rule in stores:
            if moved >= units:
                break
            there = sum(each.quantity for each in store.items if self._resource(world, each) == resource_id)
            going = min(units - moved, rule.get(resource_id, 0) - there)
            if going <= 0:
                continue
            definition_id, level = item.definition_id, item.level
            going = inventory.take_units(item.instance_id, going)
            world.stock(store, definition_id, going, None, level)
            moved += going
        return moved

    def _bring_out(
        self,
        world: "SimulationWorld",
        stores: list[tuple[str, Inventory, dict[str, int]]],
        resource_id: str,
        inventory: Inventory,
        kept: int,
        at_hand: dict[str, int],
    ) -> int:
        """Bring back from the stores what a place lacks of what it keeps at hand: so many units
        of each kind of thing of that resource the stores have. Returns how many came."""
        moved = 0
        for _object_id, store, _rule in stores:
            for item in list(store.items):
                if self._resource(world, item) != resource_id:
                    continue
                lacking = kept - at_hand.get(item.definition_id, 0)
                if lacking <= 0:
                    continue
                definition_id, level = item.definition_id, item.level
                coming = store.take_units(item.instance_id, lacking)
                world.stock(inventory, definition_id, coming, None, level)
                at_hand[definition_id] = at_hand.get(definition_id, 0) + coming
                moved += coming
        return moved

    def _resource(self, world: "SimulationWorld", item: ItemInstance) -> str | None:
        """The resource a stack counts as, if it is everybody's and whole. What is somebody's,
        kept for somebody or broken is no part of what the settlement lives on."""
        if item.owner_id is not None or item.meant_for is not None or item.broken:
            return None
        definition = world.registries.items.find(item.definition_id)
        counted = world.ledger.resources_of(world, definition) if definition is not None else ()
        return counted[0] if counted else None

    def _keeps(self, world: "SimulationWorld", inventory: Inventory) -> dict[str, int] | None:
        """What a place keeps at hand of what the store holds, if it is one the store is taken
        from and a store stands."""
        if not self.stands(world):
            return None
        for object_id, held in world.containers.items():
            if held is inventory:
                placed = world.interactables.get(object_id)
                return world.definition_of(placed).outlet if placed is not None else None
        return None

    def _warn(self, world: "SimulationWorld", capacity: dict[str, int], held: dict[str, int]) -> None:
        """Say, once a day for each resource, that there is no room left for it."""
        resources = world.registries.resources.resources
        for resource_id, units in capacity.items():
            notice = f"{FULL_NOTICE}{resource_id}"
            if held[resource_id] < units or world.notices.get(notice) == world.clock.day:
                continue
            world.notices[notice] = world.clock.day
            name = resources[resource_id].name.lower() if resource_id in resources else resource_id
            world.emit_event(
                DomainEvent(
                    FULL_EVENT,
                    FULL_IMPORTANCE,
                    f"No cabe más {name} en el almacén: hace falta otro",
                    data={"resource": resource_id, "capacity": units},
                )
            )
