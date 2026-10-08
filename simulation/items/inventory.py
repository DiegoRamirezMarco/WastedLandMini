from dataclasses import dataclass, field

from simulation.items.item import ItemInstance


@dataclass
class Inventory:
    """Items held in one place: on a resident or inside a container."""

    items: list[ItemInstance] = field(default_factory=list)

    def add(self, item: ItemInstance) -> None:
        self.items.append(item)

    def find(self, instance_id: str) -> ItemInstance | None:
        return next((item for item in self.items if item.instance_id == instance_id), None)

    def remove(self, instance_id: str) -> ItemInstance | None:
        for index, item in enumerate(self.items):
            if item.instance_id == instance_id:
                return self.items.pop(index)
        return None

    def stack_of(self, definition_id: str, owner_id: str | None, level: int | None = None) -> ItemInstance | None:
        """The stack of this kind of item belonging to this owner, if there is one here.

        What is being kept for somebody is never part of it. With `level`, only a stack of
        things that rare: without, the first there is, of whatever rarity.
        """
        return next(
            (
                item
                for item in self.items
                if item.definition_id == definition_id
                and item.owner_id == owner_id
                and item.meant_for is None
                and (level is None or item.level == level)
            ),
            None,
        )

    def take_unit(self, instance_id: str) -> bool:
        """Use up one unit of a stack. The stack disappears with its last unit."""
        item = self.find(instance_id)
        if item is None:
            return False
        item.quantity -= 1
        if item.quantity <= 0:
            self.items.remove(item)
        return True

    def take_units(self, instance_id: str, units: int) -> int:
        """Use up to `units` of a stack. Returns how many there were to take."""
        item = self.find(instance_id)
        taken = min(units, item.quantity) if item is not None else 0
        for _ in range(taken):
            self.take_unit(instance_id)
        return taken

    def count(self, definition_id: str) -> int:
        return sum(item.quantity for item in self.items if item.definition_id == definition_id)
