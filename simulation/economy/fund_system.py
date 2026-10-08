"""The common fund: what the settlement holds as a whole, apart from what anybody owns.

In coin it is a figure. In things it is whatever lies in the settlement's containers and is
nobody's: the shop's shelves, the pantries, the scrap. Under barter that is all there is of it.
What becomes the settlement's away from where it is kept is carried there in somebody's hands.
"""

import math
from typing import TYPE_CHECKING

from simulation.economy.ledger import HANDED, TAKEN
from simulation.economy.terms import Currency
from simulation.items.inventory import Inventory
from simulation.items.item import ItemInstance
from simulation.items.theft import FUND_VICTIM
from simulation.residents.resident import Resident
from world.interactable import Interactable
from world.map import Tile

if TYPE_CHECKING:
    from simulation.world import SimulationWorld

# Who a thing is kept for while it is the settlement's and still on its way to where that is kept.
COMMON = FUND_VICTIM
# Units somebody carries in from the gate at once.
FETCH_LOAD = 6


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

    def take_goods(
        self, world: "SimulationWorld", definition_id: str, units: int, unit_price: int = 0, reason: str = TAKEN
    ) -> tuple[int, int]:
        """Take units of something that is nobody's out of wherever it is kept.

        Returns how many there were and what they fetch at `unit_price` each: a worn one fetches
        less. `reason` is why they leave, for the settlement's books.
        """
        left, fetched = units, 0
        for inventory in world.containers.values():
            for item in list(inventory.items):
                if left <= 0:
                    break
                if item.definition_id == definition_id and item.owner_id is None and not item.broken:
                    share = world.items.condition_share(world, item)
                    taken = inventory.take_units(item.instance_id, left)
                    left -= taken
                    fetched += taken * math.floor(unit_price * share)
        world.ledger.record(world, definition_id, -(units - left), reason)
        return (units - left, fetched)

    def worth_of_goods(self, world: "SimulationWorld", definition_id: str, units: int, unit_price: int) -> int:
        """What that many units of something that is nobody's would fetch, taken as `take_goods` takes them."""
        left, fetched = units, 0
        for inventory in world.containers.values():
            for item in inventory.items:
                if left > 0 and item.definition_id == definition_id and item.owner_id is None and not item.broken:
                    taken = min(left, item.quantity)
                    left -= taken
                    fetched += taken * math.floor(unit_price * world.items.condition_share(world, item))
        return fetched

    def till(self, world: "SimulationWorld") -> str | None:
        """ID of where the settlement keeps its takings: the counter it sells from, or with no
        counter the first container of the kind a fund is kept in. None if it has neither."""
        box: str | None = None
        # The one that has been there longest, if there are several.
        for object_id in world.containers:
            placed = world.interactables.get(object_id)
            if placed is None:
                continue
            use = world.definition_of(placed).use
            if use is not None and use.sells:
                return object_id
            if box is None and placed.kind == world.registries.economy.strongbox_kind:
                box = object_id
        return box

    def keeps_till(self, world: "SimulationWorld", resident: Resident) -> bool:
        """Whether it falls to a resident to see to the till: it is their job to keep that counter.
        A fund kept in a box is everybody's to look at."""
        placed = world.interactables.get(self.till(world) or "")
        if placed is None:
            return False
        use = world.definition_of(placed).use
        return use is None or use.staffed_by is None or use.staffed_by == resident.job_id

    def store_for(self, world: "SimulationWorld", near: Tile) -> Inventory | None:
        """Where a thing that has just become the settlement's is put: at the till, or else in the nearest container."""
        container_id = self.till(world) or world.nearest_container(near)
        return world.containers.get(container_id or "")

    def take_in(
        self,
        world: "SimulationWorld",
        holder: Inventory,
        item: ItemInstance,
        near: Tile,
        into: Inventory | None = None,
        carrier: Resident | None = None,
    ) -> bool:
        """Have one unit of a thing somebody holds become the settlement's.

        Handed to `carrier`, whoever is serving, it is theirs to carry to the till. Handed over
        at a container nobody serves at, it stays there. Otherwise it goes straight where the
        fund is kept. False if there is nowhere to keep it.
        """
        if carrier is not None:
            self._hand(world, holder, item, carrier)
            return True
        store = into if into is not None else self.store_for(world, near)
        if store is None:
            return False
        hand_over(world, holder, item, store, None)
        return True

    def _hand(self, world: "SimulationWorld", holder: Inventory, item: ItemInstance, carrier: Resident) -> None:
        """Give one unit of a thing to whoever is to carry it to the till, as the settlement's."""
        was = item.owner_id
        if item.quantity > 1:
            item.quantity -= 1
            item = world.new_item(item.definition_id, 1, None, item.level, item.freshness)
        else:
            holder.remove(item.instance_id)
            item.owner_id, item.given_by = None, None
        item.meant_for = COMMON
        carrier.inventory.add(item)
        if was is not None:
            world.ledger.record(world, item.definition_id, 1, HANDED, by=carrier.resident_id)

    # ----- carrying it to where it is kept -----

    def takings_on(self, resident: Resident) -> list[ItemInstance]:
        """What a resident carries that is the settlement's and on its way to the till."""
        return [item for item in resident.inventory.items if item.meant_for == COMMON]

    def takings_errand(self, world: "SimulationWorld", resident: Resident) -> str | None:
        """The container a resident should walk to with the takings they carry, if they carry any."""
        if not self.takings_on(resident):
            return None
        return self.till(world) or world.nearest_container(resident.tile)

    def unload_takings(self, world: "SimulationWorld", resident: Resident, placed: Interactable) -> str | None:
        """Leave in a container the takings a resident carries. Returns what was done, or None."""
        container = world.containers.get(placed.object_id)
        takings = self.takings_on(resident)
        if container is None or not takings:
            return None
        left = []
        for item in takings:
            resident.inventory.remove(item.instance_id)
            item.meant_for = None
            container.add(item)
            left.append(f"{world.registries.items.resolve(item.definition_id).name} ({item.quantity})")
        definition = world.definition_of(placed)
        return f"deja {', '.join(left)} en {definition.article} {definition.name}"

    def fetches_from_gate(self, world: "SimulationWorld", resident: Resident) -> bool:
        """Whether a resident should go to the gate for what was bought there: something waits,
        it is their job to keep the till, and their hands are free of takings."""
        if not world.at_gate or self.takings_on(resident):
            return False
        placed = world.interactables.get(self.till(world) or "")
        use = world.definition_of(placed).use if placed is not None else None
        return use is not None and use.staffed_by is not None and use.staffed_by == resident.job_id

    def someone_fetches(self, world: "SimulationWorld") -> bool:
        """Whether anybody holds the job that brings in from the gate what was bought there."""
        placed = world.interactables.get(self.till(world) or "")
        use = world.definition_of(placed).use if placed is not None else None
        if use is None or use.staffed_by is None:
            return False
        return any(resident.job_id == use.staffed_by for resident in world.residents.values())

    def pick_up_at_gate(self, world: "SimulationWorld", resident: Resident) -> str | None:
        """Load a resident with what waits at the gate, as far as their hands go. Returns what was done, or None."""
        room, picked = FETCH_LOAD, []
        for item_id in list(world.at_gate):
            units = min(room, world.at_gate[item_id])
            if units <= 0 or world.registries.items.find(item_id) is None:
                continue
            world.at_gate[item_id] -= units
            if world.at_gate[item_id] <= 0:
                del world.at_gate[item_id]
            room -= units
            item = world.new_item(item_id, units, None)
            item.meant_for = COMMON
            resident.inventory.add(item)
            picked.append(f"{world.registries.items.resolve(item_id).name} ({units})")
        return f"recoge {', '.join(picked)} en la puerta" if picked else None


def hand_over(
    world: "SimulationWorld",
    holder: Inventory,
    item: ItemInstance,
    to: Inventory,
    owner_id: str | None,
    reason: str | None = None,
) -> ItemInstance:
    """Move one unit of a thing from one inventory to another, as `owner_id`'s. Returns it where it now is.

    What becomes the settlement's, or stops being it, is written down in its books: `reason`
    says why, where it is something other than being handed in or taken.
    """
    was = item.owner_id
    if item.quantity > 1:
        item.quantity -= 1
        moved = world.stock(to, item.definition_id, 1, owner_id, item.level, item.freshness)
    else:
        holder.remove(item.instance_id)
        item.owner_id = owner_id
        # Whoever made a present of it made it to somebody else, and it is kept for nobody now.
        item.given_by = None
        item.meant_for = None
        to.add(item)
        moved = item
    if was is None and owner_id is not None:
        world.ledger.record(world, moved.definition_id, -1, reason or TAKEN)
    elif was is not None and owner_id is None:
        world.ledger.record(world, moved.definition_id, 1, reason or HANDED)
    return moved
