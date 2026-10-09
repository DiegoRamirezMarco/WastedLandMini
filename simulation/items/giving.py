"""A thing put into a resident's hands by the player (S59).

It comes out of what is everybody's, wherever that is kept: the stores, a crate, the shop's
counter. It is theirs from then on. How they take it goes by their tastes (S19), is seen
and said, and stays with them as something that happened.
"""

from dataclasses import dataclass
from typing import TYPE_CHECKING

from simulation.economy.ledger import GIVEN
from simulation.events.event import DomainEvent
from simulation.items.item import ItemDefinition
from simulation.items.registry import UNKNOWN_CATEGORY
from simulation.memory.memory import Memory
from simulation.residents.resident import Resident
from simulation.tastes.settings import DISLIKED, HANDED, HATED, LIKED, LOVED, NEUTRAL

if TYPE_CHECKING:
    from simulation.world import SimulationWorld

GIVEN_EVENT = "thing_given"
GIVEN_IMPORTANCE = 20
GIVEN_MEMORY = 30.0
# What they remember of it, and how it sits with them, by how they took it.
REMEMBERED = {
    HATED: ("Me dieron {thing}. Para eso, mejor nada.", -0.5),
    DISLIKED: ("Me dieron {thing}, que no me hace ninguna gracia.", -0.2),
    NEUTRAL: ("Me dieron {thing}.", 0.1),
    LIKED: ("Me dieron {thing}, y me gustó.", 0.4),
    LOVED: ("Me dieron {thing}: justo lo que quería.", 0.7),
}


@dataclass(frozen=True)
class GiveResult:
    ok: bool
    message: str
    # How it was taken, where it was given.
    reaction: str = ""


class GiveSystem:
    def givable(self, world: "SimulationWorld") -> dict[str, int]:
        """What there is to give: units of each thing that is everybody's and kept somewhere,
        by item ID."""
        found: dict[str, int] = {}
        for inventory in world.containers.values():
            for item in inventory.items:
                definition = world.registries.items.find(item.definition_id)
                if item.owner_id is None and definition is not None and definition.category != UNKNOWN_CATEGORY:
                    found[item.definition_id] = found.get(item.definition_id, 0) + item.quantity
        return found

    def obstacle(self, world: "SimulationWorld", resident_id: str, definition_id: str) -> str | None:
        """Why a thing cannot be given to somebody as things stand, or None if it can."""
        resident = world.residents.get(resident_id)
        if resident is None:
            return "No hay a quién dárselo"
        if resident.away:
            return f"{resident.name} no está en el asentamiento"
        definition = world.registries.items.find(definition_id)
        if definition is None or not self.givable(world).get(definition_id):
            return "De eso no hay nada que sea de todos"
        return None

    def give(self, world: "SimulationWorld", resident_id: str, definition_id: str) -> GiveResult:
        """Take a unit of a thing out of what is everybody's and put it in a resident's
        hands. Returns how they took it."""
        error = self.obstacle(world, resident_id, definition_id)
        if error is not None:
            return GiveResult(False, error)
        resident = world.residents[resident_id]
        definition = world.registries.items.resolve(definition_id)
        inventory, lot = next(
            (inventory, item)
            for inventory in world.containers.values()
            for item in inventory.items
            if item.definition_id == definition_id and item.owner_id is None
        )
        # It is as rare and as fresh in their hands as it was where it was kept.
        level, freshness = lot.level, lot.freshness
        inventory.take_units(lot.instance_id, 1)
        world.stock(resident.inventory, definition_id, 1, resident.resident_id, level, freshness)
        world.ledger.record(world, definition_id, -1, GIVEN, by=resident.resident_id)
        thing = f"{definition.article} {definition.name}"
        world.emit_event(
            DomainEvent(
                GIVEN_EVENT,
                GIVEN_IMPORTANCE,
                f"A {resident.name} se le da {thing}",
                [resident.resident_id],
                data={"resident_id": resident.resident_id, "item_id": definition_id},
            ),
            at=resident.tile,
        )
        reaction = world.tastes.react(world, resident, definition, HANDED)
        self._remember(world, resident, definition, reaction)
        return GiveResult(True, f"{resident.name} tiene ahora {thing}", reaction)

    def _remember(self, world: "SimulationWorld", resident: Resident, definition: ItemDefinition, reaction: str) -> None:
        text, value = REMEMBERED.get(reaction, REMEMBERED[NEUTRAL])
        world.memories.remember(
            resident.resident_id,
            Memory(
                text.replace("{thing}", f"{definition.article} {definition.name}"),
                GIVEN_MEMORY,
                value,
                [],
                ["gift"],
                world.clock.total_minutes,
            ),
        )
