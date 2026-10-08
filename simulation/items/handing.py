"""Things moved by the player's own hand: out of where they are and into somebody's hands, or
into something they are kept in (S51).

It is done whatever anybody makes of it. What is put in somebody's hands is theirs from then
on. Whoever it was taken from takes it ill, by how much it was worth to them, if they are
there to see it go: what happens out of their sight they know nothing of.
"""

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from simulation.events.event import DomainEvent
from simulation.items.inventory import Inventory
from simulation.items.item import ItemInstance
from simulation.knowledge.knowledge_system import witnesses_of
from simulation.memory.memory import Memory
from simulation.residents.resident import Resident
from world.map import Tile

if TYPE_CHECKING:
    from simulation.world import SimulationWorld

# Where a thing can be put: in somebody's hands, or in something things are kept in.
TO_RESIDENT, TO_CONTAINER = "resident", "container"
HANDED_EVENT = "item_handed"
TAKEN_EVENT = "item_taken"
HANDED_IMPORTANCE = 15
TAKEN_IMPORTANCE = 35
GONE = "Eso ya no está"
SAME_PLACE = "Ya está ahí"
NOWHERE = "Ahí no se puede dejar"


@dataclass(frozen=True)
class HandingSettings:
    # What whoever a thing is taken from is the worse for: the least and the most their nerves
    # go up and they come to resent whoever it was given to, and what it has to be worth to
    # them for it to be the most.
    stress: tuple[float, float] = (4.0, 22.0)
    resentment: tuple[float, float] = (4.0, 26.0)
    worth_most: float = 30.0


def handing_settings_from_data(data: dict[str, Any]) -> HandingSettings:
    defaults = HandingSettings()

    def pair(name: str, default: tuple[float, float]) -> tuple[float, float]:
        value = data.get(name, default)
        if not isinstance(value, (list, tuple)) or len(value) != 2 or float(value[0]) < 0 or float(value[1]) < float(value[0]):
            raise ValueError(f"'{name}' of a thing taken from somebody is the least and the most, neither below 0")
        return (float(value[0]), float(value[1]))

    settings = HandingSettings(
        stress=pair("stress", defaults.stress),
        resentment=pair("resentment", defaults.resentment),
        worth_most=float(data.get("worth_most", defaults.worth_most)),
    )
    if settings.worth_most <= 0:
        raise ValueError("What a thing has to be worth for its loss to be taken worst is above 0")
    return settings


@dataclass(frozen=True)
class HandingResult:
    ok: bool
    message: str
    # The item as it is where it was put, by its instance ID.
    item_id: str | None = None
    # Who took it ill, if anybody did.
    upset: str | None = None


@dataclass(frozen=True)
class _Held:
    """Where a thing is: in whose hands or in what, and where on the map that is."""

    item: ItemInstance
    inventory: Inventory
    resident: Resident | None
    container_id: str | None
    tile: Tile


class HandingSystem:
    def _find(self, world: "SimulationWorld", instance_id: str) -> _Held | None:
        for resident in world.residents.values():
            item = resident.inventory.find(instance_id)
            if item is not None:
                return _Held(item, resident.inventory, resident, None, resident.tile)
        for container_id, inventory in world.containers.items():
            item = inventory.find(instance_id)
            placed = world.interactables.get(container_id)
            if item is not None and placed is not None:
                return _Held(item, inventory, None, container_id, (placed.x, placed.y))
        return None

    def _named(self, world: "SimulationWorld", item: ItemInstance, units: int) -> str:
        definition = world.registries.items.resolve(item.definition_id)
        return f"{definition.article} {definition.name.lower()}" if units == 1 else f"{units} de {definition.name.lower()}"

    def error(self, world: "SimulationWorld", instance_id: str, to_kind: str, to_id: str) -> str | None:
        """Why a thing cannot be put there. None if it can."""
        held = self._find(world, instance_id)
        if held is None or (held.resident is not None and held.resident.away):
            return GONE
        if to_kind == TO_RESIDENT:
            receiver = world.residents.get(to_id)
            if receiver is None or receiver.away:
                return NOWHERE
            return SAME_PLACE if receiver is held.resident else None
        if to_kind == TO_CONTAINER:
            if to_id not in world.containers or to_id not in world.interactables:
                return NOWHERE
            return SAME_PLACE if to_id == held.container_id else None
        return NOWHERE

    def foresee(self, world: "SimulationWorld", instance_id: str, to_kind: str, to_id: str) -> str:
        """What putting a thing there would do, said before it is done."""
        error = self.error(world, instance_id, to_kind, to_id)
        if error is not None:
            return error
        held = self._find(world, instance_id)
        thing = self._named(world, held.item, held.item.quantity)
        if to_kind == TO_RESIDENT:
            receiver = world.residents[to_id]
            owner = world.residents.get(held.item.owner_id or "")
            if owner is not None and owner is not receiver:
                return f"{thing}: para {receiver.name}, y a {owner.name} le sentará mal"
            return f"{thing}: para {receiver.name}"
        placed = world.interactables[to_id]
        return f"{thing}: a guardar en {world.definition_of(placed).name.lower()}"

    def hand(
        self, world: "SimulationWorld", instance_id: str, to_kind: str, to_id: str, units: int | None = None
    ) -> HandingResult:
        """Put a thing in somebody's hands, or in something things are kept in: all there is
        of it in its stack, or only `units` of it. In somebody's hands it is theirs."""
        error = self.error(world, instance_id, to_kind, to_id)
        if error is not None:
            return HandingResult(False, error)
        held = self._find(world, instance_id)
        item = held.item
        count = item.quantity if units is None else max(1, min(int(units), item.quantity))
        owner = world.residents.get(item.owner_id or "")
        if count < item.quantity:
            # Part of a stack goes as a thing of its own, as worn as the rest of it.
            item.quantity -= count
            moved = world.new_item(item.definition_id, count, item.owner_id)
            moved.condition, moved.given_by, moved.meant_for = item.condition, item.given_by, item.meant_for
        else:
            held.inventory.remove(item.instance_id)
            moved = item
        thing = self._named(world, moved, count)
        if to_kind == TO_CONTAINER:
            world.containers[to_id].add(moved)
            placed = world.interactables[to_id]
            text = f"Se guarda {thing} en {world.definition_of(placed).name.lower()}"
            world.emit_event(
                DomainEvent(HANDED_EVENT, HANDED_IMPORTANCE, text, [], data={"item": moved.instance_id, "to": to_id}),
                at=(placed.x, placed.y),
            )
            return HandingResult(True, text, moved.instance_id)
        receiver = world.residents[to_id]
        upset = owner if owner is not None and owner is not receiver and self._sees(world, owner, held) else None
        definition = world.registries.items.resolve(moved.definition_id)
        worth = world.items.personal_value(world, owner, definition, moved) if upset else 0.0
        moved.owner_id, moved.meant_for = receiver.resident_id, None
        if owner is not receiver:
            # It was no present of anybody's: it was put there.
            moved.given_by = None
        receiver.inventory.add(moved)
        text = f"{receiver.name} se queda con {thing}"
        world.emit_event(
            DomainEvent(
                HANDED_EVENT, HANDED_IMPORTANCE, text, [receiver.resident_id], data={"item": moved.instance_id, "to": to_id}
            ),
            at=receiver.tile,
        )
        if upset is None:
            return HandingResult(True, text, moved.instance_id)
        self._take_ill(world, upset, receiver, thing, worth * count)
        return HandingResult(True, f"{text}. A {upset.name} le sienta mal", moved.instance_id, upset.resident_id)

    def _sees(self, world: "SimulationWorld", owner: Resident, held: _Held) -> bool:
        """Whether whoever a thing belongs to is there to see it go: it is taken out of their
        own hands while they are awake, or from somewhere they can see."""
        if owner.away or not world.is_aware(owner):
            return False
        return held.resident is owner or owner.resident_id in witnesses_of(world, held.tile)

    def _take_ill(self, world: "SimulationWorld", owner: Resident, receiver: Resident, thing: str, worth: float) -> None:
        """Have somebody be the worse for a thing of theirs having been given to another."""
        settings = world.registries.handing
        share = max(0.0, min(1.0, worth / settings.worth_most))
        stress = settings.stress[0] + (settings.stress[1] - settings.stress[0]) * share
        resentment = settings.resentment[0] + (settings.resentment[1] - settings.resentment[0]) * share
        owner.needs.apply({"stress": stress})
        world.relationship(owner.resident_id, receiver.resident_id).adjust("resentment", resentment)
        world.memories.remember(
            owner.resident_id,
            Memory(
                f"Me quitaron {thing} para dárselo a {receiver.name}.",
                TAKEN_IMPORTANCE,
                -0.6,
                [receiver.resident_id],
                ["taken"],
                world.clock.total_minutes,
            ),
        )
        world.emit_event(
            DomainEvent(
                TAKEN_EVENT,
                TAKEN_IMPORTANCE,
                f"A {owner.name} le quitan {thing} para dárselo a {receiver.name}, y le sienta mal",
                [owner.resident_id, receiver.resident_id],
                data={"stress": stress, "resentment": resentment},
            ),
            at=owner.tile,
        )
