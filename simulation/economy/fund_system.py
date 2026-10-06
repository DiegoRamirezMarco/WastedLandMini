"""The common fund: what the settlement holds as a whole, apart from what anybody owns.

In coin it is a figure. In things it is whatever lies in the settlement's containers and is
nobody's: the shop's shelves, the pantries, the scrap. Under barter that is all there is of it.
"""

from typing import TYPE_CHECKING

from simulation.items.inventory import Inventory
from simulation.items.item import ItemInstance
from simulation.economy.terms import Currency
from world.map import Tile

if TYPE_CHECKING:
    from simulation.world import SimulationWorld


class FundSystem:
    def currency(self, world: "SimulationWorld") -> Currency | None:
        """The currency the settlement trades with. None while it trades by barter."""
        return world.trading.currency if world.trading.in_use else None

    # ----- in coin -----

    def pay_in(self, world: "SimulationWorld", amount: float) -> None:
        """Put coin into the fund."""
        world.trading.fund += max(0.0, amount)

    def pay_out(self, world: "SimulationWorld", amount: float) -> float:
        """Take coin out of the fund, as far as it goes. Returns what was taken: it never goes below nothing."""
        taken = max(0.0, min(amount, world.trading.fund))
        world.trading.fund -= taken
        return taken

    # ----- in things -----

    def goods(self, world: "SimulationWorld") -> dict[str, int]:
        """Units of each kind of thing that are nobody's and in working order, wherever they are kept."""
        held: dict[str, int] = {}
        for inventory in world.containers.values():
            for item in inventory.items:
                if item.owner_id is None and not item.broken:
                    held[item.definition_id] = held.get(item.definition_id, 0) + item.quantity
        return held

    def take_goods(self, world: "SimulationWorld", definition_id: str, units: int) -> int:
        """Take units of something that is nobody's out of wherever it is kept. Returns how many there were."""
        left = units
        for inventory in world.containers.values():
            for item in list(inventory.items):
                if left <= 0:
                    return units
                if item.definition_id == definition_id and item.owner_id is None and not item.broken:
                    left -= inventory.take_units(item.instance_id, left)
        return units - left

    def counter(self, world: "SimulationWorld") -> str | None:
        """ID of the counter the settlement sells from, which is where its takings are kept. None if it has none."""
        for object_id in world.containers:
            placed = world.interactables.get(object_id)
            use = world.definition_of(placed).use if placed is not None else None
            if use is not None and use.sells:
                return object_id
        return None

    def store_for(self, world: "SimulationWorld", near: Tile) -> Inventory | None:
        """Where a thing that has just become the settlement's is put: on the counter, or else in the nearest container."""
        container_id = self.counter(world) or world.nearest_container(near)
        return world.containers.get(container_id or "")

    def take_in(self, world: "SimulationWorld", holder: Inventory, item: ItemInstance, near: Tile) -> bool:
        """Have one unit of a thing somebody holds become the settlement's. False if there is nowhere to keep it."""
        store = self.store_for(world, near)
        if store is None:
            return False
        hand_over(world, holder, item, store, None)
        return True


def hand_over(
    world: "SimulationWorld", holder: Inventory, item: ItemInstance, to: Inventory, owner_id: str | None
) -> ItemInstance:
    """Move one unit of a thing from one inventory to another, as `owner_id`'s. Returns it where it now is."""
    if item.quantity > 1:
        item.quantity -= 1
        return world.stock(to, item.definition_id, 1, owner_id)
    holder.remove(item.instance_id)
    item.owner_id = owner_id
    # Whoever made a present of it made it to somebody else.
    item.given_by = None
    to.add(item)
    return item
