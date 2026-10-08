"""Current (S55): what a generator gives, what each thing draws, and what stops without it.

Some kinds of thing run on current: lamps, the radio, the workshop, the laboratory, the tank
with its pump. Each draws so much and a generator gives so much, as data, while it has fuel.
With no current a thing stops: a lamp gives no light, nobody can work at the post.

Each such thing is switched on or off by the player. When more is asked for than there is,
whatever was switched on last goes off, and it is said. The generator burns its fuel by what
is drawn and for how long: a lamp through the night, a post while somebody works at it.
"""

from dataclasses import dataclass
from typing import TYPE_CHECKING

from simulation.economy.ledger import BURNT
from simulation.events.event import DomainEvent
from simulation.items.inventory import Inventory
from world.interactable import Interactable

if TYPE_CHECKING:
    from simulation.world import SimulationWorld

FAILED_EVENT = "power_failed"
SHED_EVENT = "power_shed"
SWITCHED_EVENT = "power_switched"
POWER_EVENT_IMPORTANCE = 25
SWITCH_IMPORTANCE = 10
POWER_OUT_NOTICE = "power_out"


@dataclass(frozen=True)
class PowerResult:
    ok: bool
    message: str


class PowerSystem:
    # ----- what there is and what is asked for -----

    def generators(self, world: "SimulationWorld") -> list[tuple[Interactable, Inventory]]:
        """Whatever gives current, in map order, with what it holds."""
        return [
            (placed, world.containers[object_id])
            for object_id, placed in world.interactables.items()
            if world.definition_of(placed).gives > 0 and object_id in world.containers
        ]

    def fuel(self, world: "SimulationWorld") -> int:
        """Units of fuel in what gives current."""
        item_id = world.registries.power.fuel
        return sum(inventory.count(item_id) for _placed, inventory in self.generators(world))

    def supply(self, world: "SimulationWorld") -> int:
        """How much current there is: what every generator that has fuel gives, the more for
        having been made better (S54). None with no fuel anywhere."""
        item_id = world.registries.power.fuel
        return sum(
            round(world.definition_of(placed).gives * world.upgrades.better(world, placed.object_id))
            for placed, inventory in self.generators(world)
            if inventory.count(item_id) > 0
        )

    def draws(self, world: "SimulationWorld", placed: Interactable | None) -> int:
        """How much current a thing draws when it is on. Nothing for most things."""
        return world.definition_of(placed).draws if placed is not None else 0

    def drawing(self, world: "SimulationWorld") -> list[Interactable]:
        """Everything that runs on current and is switched on, in map order."""
        return [placed for placed in world.interactables.values() if placed.on and self.draws(world, placed) > 0]

    def demand(self, world: "SimulationWorld") -> int:
        return sum(self.draws(world, placed) for placed in self.drawing(world))

    def enough(self, world: "SimulationWorld") -> bool:
        """Whether there is current, and enough of it for everything that is switched on."""
        return 0 < self.demand(world) <= self.supply(world)

    def powered(self, world: "SimulationWorld", object_id: str | None) -> bool:
        """Whether a thing has what it needs to run: it draws nothing, or it is switched on and
        there is current for it."""
        placed = world.interactables.get(object_id or "")
        if self.draws(world, placed) <= 0:
            return True
        return placed.on and self.enough(world)

    def stopped(self, world: "SimulationWorld", object_id: str | None) -> bool:
        """Whether a thing that runs on current is standing idle for want of it."""
        return not self.powered(world, object_id)

    # ----- what the player does -----

    def switch(self, world: "SimulationWorld", object_id: str, on: bool) -> PowerResult:
        """Switch a thing that runs on current on or off. Switched on with no current to spare,
        it goes off again at once, as whatever was switched on last does."""
        placed = world.interactables.get(object_id)
        if placed is None or self.draws(world, placed) <= 0:
            return PowerResult(False, "Eso no va con corriente")
        definition = world.definition_of(placed)
        named = f"{definition.article} {definition.name}"
        if placed.on == on:
            return PowerResult(True, f"{named[0].upper()}{named[1:]} ya estaba así")
        placed.on = on
        if on:
            placed.switched_at = world.clock.total_minutes
        text = f"Se {'enciende' if on else 'apaga'} {named}"
        world.emit_event(
            DomainEvent(SWITCHED_EVENT, SWITCH_IMPORTANCE, text, data={"object_id": object_id, "on": on}),
            at=(placed.x, placed.y),
        )
        if on and self.fuel(world) > 0 and self.demand(world) > self.supply(world):
            self._shed(world)
            if not placed.on:
                return PowerResult(False, f"No hay corriente para {named}: se apaga")
        return PowerResult(True, text)

    # ----- every minute -----

    def tick(self, world: "SimulationWorld") -> None:
        """Keep what is asked for within what there is, and burn fuel for what is running."""
        generators = self.generators(world)
        if not generators:
            # A settlement with no generator has no current to run out of.
            return
        settings = world.registries.power
        if self.fuel(world) <= 0:
            if world.notices.get(POWER_OUT_NOTICE) != world.clock.day and self._night_begins(world):
                world.notices[POWER_OUT_NOTICE] = world.clock.day
                world.emit_event(DomainEvent(FAILED_EVENT, POWER_EVENT_IMPORTANCE, "El generador se queda sin combustible"))
            return
        if self.demand(world) > self.supply(world):
            self._shed(world)
        if settings.fuel_lasts <= 0:
            return
        world.power_burnt += self._running(world) / settings.fuel_lasts
        while world.power_burnt >= 1.0 - 1e-9:
            world.power_burnt = max(0.0, world.power_burnt - 1.0)
            if not self._burn(world):
                world.power_burnt = 0.0
                break

    def _night_begins(self, world: "SimulationWorld") -> bool:
        hours = world.registries.event_settings.get("perception", {}).get("dark_hours")
        return bool(hours) and world.clock.minute == 0 and world.clock.hour == int(hours[0])

    def _running(self, world: "SimulationWorld") -> float:
        """How much is being drawn this minute by what is running: a light, counted for the
        whole night as night begins; a post while somebody is at it; anything else while it is
        used."""
        hours = world.registries.event_settings.get("perception", {}).get("dark_hours")
        night = ((int(hours[1]) - int(hours[0])) % 24) * 60 if hours else 0
        drawn = 0.0
        at_post = {
            resident.post_id for resident in world.residents.values() if world.work.on_duty(world, resident)
        }
        for placed in self.drawing(world):
            definition = world.definition_of(placed)
            if definition.light > 0 and definition.use is None and not any(
                job.works_at(placed.kind) for job in world.registries.jobs.values()
            ):
                # What only gives light burns for the night it is about to light.
                drawn += definition.draws * night if self._night_begins(world) else 0.0
            elif definition.chill < 1.0 or placed.object_id in at_post or world.users_of(placed.object_id) > 0:
                # What chills runs for as long as it is on (S65).
                drawn += definition.draws
        return drawn

    def _burn(self, world: "SimulationWorld") -> bool:
        """Use up one unit of fuel, from the first generator that has any."""
        item_id = world.registries.power.fuel
        for _placed, inventory in self.generators(world):
            stack = inventory.stack_of(item_id, None)
            if stack is not None:
                inventory.take_unit(stack.instance_id)
                world.ledger.record(world, item_id, -1, BURNT)
                return True
        return False

    def _shed(self, world: "SimulationWorld") -> None:
        """Switch off whatever was switched on last, and the one before it, until what is left
        asks for no more than there is."""
        supply = self.supply(world)
        latest_first = sorted(
            enumerate(self.drawing(world)), key=lambda entry: (-entry[1].switched_at, -entry[0])
        )
        for _order, placed in latest_first:
            if self.demand(world) <= supply:
                return
            placed.on = False
            definition = world.definition_of(placed)
            world.emit_event(
                DomainEvent(
                    SHED_EVENT,
                    POWER_EVENT_IMPORTANCE,
                    f"No hay corriente para todo: se apaga {definition.article} {definition.name}",
                    data={"object_id": placed.object_id, "supply": supply},
                ),
                at=(placed.x, placed.y),
            )
