"""What an object that shows off a container's contents, such as a shop's shelf, has on it."""

from simulation.world import SimulationWorld
from world.interactable import Interactable

# Size at which goods are drawn on a shelf: half an item icon.
GOODS_SIZE = (8, 8)
# Top-left corner of each place for one of the goods on a shelf sprite, board by board.
SLOTS = ((3, 2), (12, 2), (21, 2), (3, 13), (12, 13), (21, 13))


def displayed_goods(world: SimulationWorld, placed: Interactable) -> list[str]:
    """Item definition IDs to draw on a display object, one per slot it has filled.

    The stock of the containers it stands for, in the same room, is spread over every display
    there: one of each thing in turn, so that a little of everything shows, and the shelves
    empty as the stock runs down.
    """
    shown = world.definition_of(placed).display_of
    if shown is None:
        return []
    room = world.room_at((placed.x, placed.y))
    left = [
        [item.definition_id, item.quantity]
        for object_id, inventory in world.containers.items()
        if (holder := world.interactables.get(object_id)) is not None
        and holder.kind == shown
        and world.room_at((holder.x, holder.y)) is room
        for item in inventory.items
        if item.owner_id is None
    ]
    units: list[str] = []
    while any(quantity > 0 for _, quantity in left):
        for entry in left:
            if entry[1] > 0:
                units.append(entry[0])
                entry[1] -= 1
    displays = [
        other.object_id
        for other in world.interactables.values()
        if other.kind == placed.kind and world.room_at((other.x, other.y)) is room
    ]
    first = displays.index(placed.object_id) * len(SLOTS)
    return units[first : first + len(SLOTS)]
