"""What goes off (S65).

Some things keep only so long. Each kind loses so much of its freshness, of a hundred, in a
day, as data on it, and most lose none. A stack with none left has gone off: it is written
down as spoiled (S51), and what is left of it is compost.

What is put with a stack of the same thing is one stack with it if the two are about as
fresh, and as fresh as the two together; if not they are kept apart, so that it is the older
lot that goes off and is eaten first, and not all of it at once.

A thing that chills what is kept in it has it go off that much more slowly, while it has
current (S55): the refrigerated chest. What goes off is put in one by itself, ahead of the
store (S53).

Compost is kept until the player has it put on a bed of the garden, which is then worked
faster for some days.
"""

from dataclasses import dataclass
from typing import TYPE_CHECKING

from simulation.economy.ledger import SPOILED
from simulation.economy.spoil_settings import SpoilSettings
from simulation.events.event import DomainEvent
from simulation.items.inventory import Inventory
from simulation.items.item import ItemInstance
from world.interactable import Interactable
from world.map import Tile

if TYPE_CHECKING:
    from simulation.world import SimulationWorld

WENT_OFF_EVENT = "went_off"
DRESSED_EVENT = "bed_dressed"
WENT_OFF_IMPORTANCE = 30
DRESSED_IMPORTANCE = 20
FRESH = 100.0
# Less freshness than this is none: what is left of a sum of many small parts.
GONE = 1e-6
HOURS_PER_DAY = 24
MINUTES_PER_DAY = 24 * 60
NOT_A_BED = "Ahí no se echa abono"
ALREADY_DRESSED = "Ya tiene abono: aún le dura"


@dataclass(frozen=True)
class SpoilResult:
    ok: bool
    message: str


class SpoilSystem:
    def settings(self, world: "SimulationWorld") -> SpoilSettings:
        return world.registries.spoilage

    # ----- how fast -----

    def rate(self, world: "SimulationWorld", definition_id: str) -> float:
        """How much of its freshness, of a hundred, a kind of thing loses in a day. Nothing for what keeps."""
        definition = world.registries.items.find(definition_id)
        return definition.spoils if definition is not None else 0.0

    def goes_off(self, world: "SimulationWorld", definition_id: str) -> bool:
        return self.rate(world, definition_id) > 0

    def chills(self, world: "SimulationWorld", placed: Interactable | None) -> bool:
        """Whether a thing is keeping what is in it right now: it is of a kind that chills, it
        has current and it has not broken down."""
        if placed is None or world.definition_of(placed).chill >= 1.0:
            return False
        return world.power.powered(world, placed.object_id) and not world.wear.broken(world, placed.object_id)

    def factor(self, world: "SimulationWorld", container_id: str | None) -> float:
        """By how much what is kept in a place goes off more slowly than anywhere else: the
        chill of its kind, while it has current. One for anywhere else."""
        placed = world.interactables.get(container_id or "")
        return world.definition_of(placed).chill if self.chills(world, placed) else 1.0

    def days_left(self, world: "SimulationWorld", item: ItemInstance, container_id: str | None = None) -> float | None:
        """How many days a stack has before it goes off, kept where it is. None for what keeps."""
        rate = self.rate(world, item.definition_id) * self.factor(world, container_id)
        return item.freshness / rate if rate > 0 else None

    # ----- one stack or two -----

    def stack_for(
        self,
        world: "SimulationWorld",
        inventory: Inventory,
        definition_id: str,
        owner_id: str | None,
        level: int,
        freshness: float,
    ) -> ItemInstance | None:
        """The stack that so many units of a thing that goes off are put on: the one of the same
        thing, owner and rarity that is nearest to them in freshness, if it is near enough.
        None if they are to be a stack of their own."""
        apart = self.settings(world).apart
        near = [
            item
            for item in inventory.items
            if item.definition_id == definition_id
            and item.owner_id == owner_id
            and item.meant_for is None
            and item.level == level
            and abs(item.freshness - freshness) <= apart
        ]
        return min(near, key=lambda item: abs(item.freshness - freshness), default=None)

    def put_on(self, stack: ItemInstance, units: int, freshness: float) -> None:
        """So many units go on a stack, which is then as fresh as the two lots together."""
        total = stack.quantity + units
        if total > 0:
            stack.freshness = (stack.freshness * stack.quantity + freshness * units) / total
        stack.quantity = total

    # ----- every hour -----

    def tick(self, world: "SimulationWorld") -> None:
        """On the hour, whatever goes off is an hour further gone, and what has no freshness
        left has gone off."""
        if world.clock.minute != 0:
            return
        now = world.clock.total_minutes
        for object_id in [each for each, until in world.dressed.items() if until <= now or each not in world.interactables]:
            del world.dressed[object_id]
        gone: dict[str, int] = {}
        for container_id, inventory in world.containers.items():
            placed = world.interactables.get(container_id)
            tile = (placed.x, placed.y) if placed is not None else None
            self._age(world, inventory, self.factor(world, container_id), tile, gone)
        for resident in world.residents.values():
            if not resident.away:
                self._age(world, resident.inventory, 1.0, resident.tile, gone)
        if gone:
            items = world.registries.items
            said = ", ".join(f"{units} de {items.resolve(item_id).name}" for item_id, units in gone.items())
            world.emit_event(
                DomainEvent(WENT_OFF_EVENT, WENT_OFF_IMPORTANCE, f"Se echa a perder: {said}", data={"items": dict(gone)})
            )

    def _age(
        self, world: "SimulationWorld", inventory: Inventory, factor: float, tile: Tile | None, gone: dict[str, int]
    ) -> None:
        for item in list(inventory.items):
            rate = self.rate(world, item.definition_id)
            if rate <= 0:
                continue
            item.freshness = max(0.0, item.freshness - rate / HOURS_PER_DAY * factor)
            if item.freshness <= GONE:
                self._go_off(world, inventory, item, tile, gone)

    def _go_off(
        self, world: "SimulationWorld", inventory: Inventory, item: ItemInstance, tile: Tile | None, gone: dict[str, int]
    ) -> None:
        """A stack has gone off: it is no more, it is written down, and it is compost."""
        inventory.items.remove(item)
        gone[item.definition_id] = gone.get(item.definition_id, 0) + item.quantity
        if item.owner_id is None and item.meant_for is None:
            world.ledger.record(world, item.definition_id, -item.quantity, SPOILED)
        becomes = self.settings(world).becomes
        if becomes is None or world.registries.items.find(becomes) is None:
            return
        kept = self._heap(world, inventory, tile)
        if kept is not None:
            world.stock(kept, becomes, item.quantity, None)

    def _heap(self, world: "SimulationWorld", inventory: Inventory, tile: Tile | None) -> Inventory | None:
        """Where what has gone off is kept as compost: in the store, if one stands that is no
        chest; or else where it went off, if that is a place things are kept in; or else in
        the nearest such place."""
        for object_id, store in world.stores.inventories(world):
            if world.definition_of(world.interactables[object_id]).chill >= 1.0:
                return store
        if any(held is inventory for held in world.containers.values()):
            return inventory
        nearest = world.nearest_container(tile) if tile is not None else None
        return world.containers.get(nearest or "")

    # ----- compost -----

    def compost_held(self, world: "SimulationWorld") -> int:
        """How many units of compost the settlement has, wherever they are kept."""
        item_id = self.settings(world).compost
        if item_id is None:
            return 0
        return sum(
            item.quantity
            for inventory in world.containers.values()
            for item in inventory.items
            if item.definition_id == item_id and item.owner_id is None
        )

    def takes_compost(self, world: "SimulationWorld", placed: Interactable | None) -> bool:
        settings = self.settings(world)
        return placed is not None and settings.dresses and placed.kind in settings.compost_on

    def dressed_until(self, world: "SimulationWorld", object_id: str | None) -> int | None:
        """The game minute until which a thing has compost on it. None for one that has none."""
        until = world.dressed.get(object_id or "")
        return until if until is not None and until > world.clock.total_minutes else None

    def bed_factor(self, world: "SimulationWorld", object_id: str | None) -> float:
        """By how much a post is worked faster for the compost on it."""
        return self.settings(world).compost_factor if self.dressed_until(world, object_id) is not None else 1.0

    def obstacle(self, world: "SimulationWorld", object_id: str) -> str | None:
        """Why compost cannot be put on a thing right now. None if it can."""
        placed = world.interactables.get(object_id)
        if not self.takes_compost(world, placed):
            return NOT_A_BED
        if self.dressed_until(world, object_id) is not None:
            return ALREADY_DRESSED
        settings = self.settings(world)
        held = self.compost_held(world)
        if held < settings.compost_units:
            return f"Hace falta abono: {settings.compost_units}, y hay {held}"
        return None

    def dress(self, world: "SimulationWorld", object_id: str) -> SpoilResult:
        """Put compost on a bed, at the player's word: it is taken from wherever it is kept,
        and the bed is worked faster for some days."""
        error = self.obstacle(world, object_id)
        if error is not None:
            return SpoilResult(False, error)
        settings = self.settings(world)
        owed = settings.compost_units
        for inventory in world.containers.values():
            for item in list(inventory.items):
                if owed > 0 and item.definition_id == settings.compost and item.owner_id is None:
                    owed -= inventory.take_units(item.instance_id, owed)
        placed = world.interactables[object_id]
        world.dressed[object_id] = world.clock.total_minutes + settings.compost_days * MINUTES_PER_DAY
        definition = world.definition_of(placed)
        days = "un día" if settings.compost_days == 1 else f"{settings.compost_days} días"
        text = f"Se echa abono en {definition.article} {definition.name}: da más durante {days}"
        world.emit_event(
            DomainEvent(DRESSED_EVENT, DRESSED_IMPORTANCE, text, data={"object_id": object_id, "until": world.dressed[object_id]}),
            at=(placed.x, placed.y),
        )
        return SpoilResult(True, text)
