"""Throwing somebody out: they walk to the gate and through it, and do not come back.

What depended on them is let go of as on a death, with no grave: their post, their bed, what
they kept in the settlement's containers. What they carry of their own goes with them. They
are still in the memories of those they left.
"""

from typing import TYPE_CHECKING

from simulation.politics.political_event import PoliticalEvent
from simulation.politics.records import Exile
from simulation.residents.activity import LEAVE_ACTION, Activity
from simulation.residents.resident import Resident
from world.pathfinding import find_path, manhattan

if TYPE_CHECKING:
    from simulation.world import SimulationWorld

EXPELLED_IMPORTANCE = 80
LEFT_IMPORTANCE = 70
# How long somebody thrown out has to be gone, in minutes, before they are simply put outside.
LEAVE_MINUTES = 240
# How long whoever was out there when they were thrown out is given once they are back.
BACK_MINUTES = 60
# How near the way out counts as being at it.
GATE_REACH = 1


class ExileSystem:
    def banish(self, world: "SimulationWorld", resident: Resident, why: str = "", by: str | None = None) -> None:
        """Have a resident thrown out for good: from now on they are on their way to the gate."""
        resident_id = resident.resident_id
        if resident_id in world.leaving:
            return
        now = world.clock.total_minutes
        world.leaving[resident_id] = now + LEAVE_MINUTES
        world.exiled.append(Exile(resident_id, resident.name, now, why))
        world.interventions.cancel_for(world, resident_id)
        if not resident.away:
            resident.activity = None
            resident.current_action = "idle"
        world.emit_event(
            PoliticalEvent(
                "resident_expelled",
                EXPELLED_IMPORTANCE,
                f"A {resident.name} le echan del asentamiento",
                [resident_id],
                data={"resident_id": resident_id, "by": by},
                government=world.government.kind,
            ),
            at=resident.tile,
            fact_text=f"a {resident.name} le echaron del asentamiento",
        )

    def tick(self, world: "SimulationWorld") -> None:
        """One minute: whoever has been thrown out keeps walking to the gate, and is gone once there."""
        if not world.leaving:
            return
        now = world.clock.total_minutes
        for resident_id, deadline in list(world.leaving.items()):
            resident = world.residents.get(resident_id)
            if resident is None:
                del world.leaving[resident_id]
                continue
            if resident.away:
                # Out there already: it is on coming back that they find out.
                world.leaving[resident_id] = max(deadline, now + BACK_MINUTES)
                continue
            gate = world.happenings.arrival_tile(world)
            if manhattan(resident.tile, gate) <= GATE_REACH or now >= deadline:
                self._depart(world, resident)
                continue
            activity = resident.activity
            if activity is not None and activity.action == LEAVE_ACTION and activity.path:
                continue
            path = find_path(resident.tile, gate, world.passable())
            if not path:
                self._depart(world, resident)
                continue
            resident.activity = Activity(LEAVE_ACTION, None, path, LEAVE_MINUTES)
            resident.current_action = "walking"

    def _depart(self, world: "SimulationWorld", resident: Resident) -> None:
        resident_id, name, tile = resident.resident_id, resident.name, resident.tile
        world.leaving.pop(resident_id, None)
        record = next((each for each in reversed(world.exiled) if each.resident_id == resident_id and not each.returned), None)
        if record is not None:
            # Who they were is kept, and when they will be heard of again.
            world.justice.left(world, resident, record)
        world.health.leave_behind(world, resident, takes_own=True)
        world.emit_event(
            PoliticalEvent(
                "resident_left",
                LEFT_IMPORTANCE,
                f"{name} cruza la puerta y no vuelve",
                data={"resident_id": resident_id, "tile": list(tile)},
                government=world.government.kind,
            ),
            at=tile,
            fact_text=f"{name} se fue del asentamiento para no volver",
            subjects=[resident_id],
        )
