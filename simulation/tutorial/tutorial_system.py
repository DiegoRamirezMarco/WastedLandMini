"""Leads a new settlement through its opening, one step at a time.

It only ever looks at what the settlement has become: a step is done when the world says so,
however the player got there. The world outside leaves the settlement alone until the last step.
"""

from typing import TYPE_CHECKING

from simulation.events.event import DomainEvent
from simulation.tutorial.tutorial import (
    ACKNOWLEDGED,
    ANSWERED,
    BUILDING,
    DEED,
    ELAPSED,
    JOB,
    OBJECT,
    RESIDENTS,
    STRANGER_OPENING,
    Gift,
    TutorialState,
    TutorialStep,
)
from simulation.work.hauling import containers_of_kind

if TYPE_CHECKING:
    from simulation.residents.resident import Resident
    from simulation.world import SimulationWorld

STEP_DONE_EVENT = "tutorial_step_done"
FINISHED_EVENT = "tutorial_finished"
STEP_IMPORTANCE = 35
FINISHED_IMPORTANCE = 45
FINISHED_TEXT = "El asentamiento echa a andar por su cuenta"


class TutorialSystem:
    def start(self, world: "SimulationWorld") -> None:
        """Begin at the first step. With no steps defined, there is nothing to be led through."""
        steps = world.registries.tutorial.steps
        world.tutorial = TutorialState()
        if steps:
            self._begin(world, steps[0])

    def current(self, world: "SimulationWorld") -> TutorialStep | None:
        return world.registries.tutorial.step(world.tutorial.step_id)

    def progress(self, world: "SimulationWorld") -> tuple[int, int]:
        """Which step the settlement is on, counted from 1, and how many there are."""
        definition = world.registries.tutorial
        index = definition.index_of(world.tutorial.step_id)
        return ((index or 0) + 1, len(definition.steps))

    def acknowledge(self, world: "SimulationWorld") -> bool:
        """The player has read the step that only asks to be read. Returns whether one was waiting."""
        step = self.current(world)
        if step is None or step.goal.kind != ACKNOWLEDGED:
            return False
        world.tutorial.acknowledged = True
        return True

    def report(self, world: "SimulationWorld", deed: str) -> bool:
        """The player has done something the simulation cannot see for itself, such as a drawing.

        It counts only if the step in hand asks for it. Returns whether it did.
        """
        step = self.current(world)
        if step is None or step.goal.needed_deed != deed:
            return False
        if deed not in world.tutorial.deeds:
            world.tutorial.deeds.append(deed)
        return True

    def owed(self, world: "SimulationWorld") -> str | None:
        """What the player has yet to do with their own hands for the step in hand, once the
        settlement itself has what the step asks for. None if nothing, or if that comes first."""
        step = self.current(world)
        if step is None:
            return None
        deed = step.goal.needed_deed
        if deed is None or deed in world.tutorial.deeds or not self._stands(world, step):
            return None
        return deed

    def check(self, world: "SimulationWorld") -> None:
        """Move on from every step that is done. Run each minute and after anything the player does."""
        state = world.tutorial
        if not state.active:
            return
        # No more rounds than there are steps: each round either stops or leaves one behind.
        for _ in range(len(world.registries.tutorial.steps) + 1):
            step = self.current(world)
            if step is None:
                # A step the game no longer defines: the opening is over.
                state.step_id = None
                return
            self._open(world, step)
            if not self._met(world, step):
                return
            self._complete(world, step)

    # ----- what a step sets going -----

    def _open(self, world: "SimulationWorld", step: TutorialStep) -> None:
        state = world.tutorial
        if step.opening is None or state.opened:
            return
        if step.opening == STRANGER_OPENING:
            if not world.happenings.strangers_left(world):
                # Nobody is left to knock: there is nothing to wait for.
                state.opened = True
                return
            keeper = self._host(world)
            state.opened = keeper is not None and world.happenings.call_to_gate(world, keeper)

    @staticmethod
    def _host(world: "SimulationWorld") -> "Resident | None":
        """Whoever has been here longest among those who are in, awake and with nothing to decide."""
        return next(
            (
                resident
                for resident in world.residents.values()
                if not resident.away
                and world.is_aware(resident)
                and world.interventions.pending_for(world, resident.resident_id) is None
            ),
            None,
        )

    # ----- whether it is done -----

    def _met(self, world: "SimulationWorld", step: TutorialStep) -> bool:
        deed = step.goal.needed_deed
        return self._stands(world, step) and (deed is None or deed in world.tutorial.deeds)

    def _stands(self, world: "SimulationWorld", step: TutorialStep) -> bool:
        """Whether the settlement has become what the step asks for, whatever the player still owes it."""
        state, goal = world.tutorial, step.goal
        if goal.kind == DEED:
            return True
        if goal.kind == RESIDENTS:
            return len(world.residents) >= goal.count
        if goal.kind == BUILDING:
            built = [
                room
                for room in world.rooms.values()
                if room.roofed and (goal.target is None or room.blueprint_id == goal.target)
            ]
            return len(built) >= goal.count
        if goal.kind == OBJECT:
            placed = [
                each
                for each in world.interactables.values()
                if each.kind == goal.target and (not goal.indoors or world.under_roof((each.x, each.y)))
            ]
            return len(placed) >= goal.count
        if goal.kind == JOB:
            jobs = world.registries.jobs
            working = [
                resident
                for resident in world.residents.values()
                if resident.job_id in jobs and (goal.target is None or resident.job_id == goal.target)
            ]
            return len(working) >= goal.count
        if goal.kind == ELAPSED:
            return world.clock.total_minutes - state.since >= goal.minutes
        if goal.kind == ANSWERED:
            return state.opened and (step.opening != STRANGER_OPENING or not world.happenings.gate_is_busy(world))
        if goal.kind == ACKNOWLEDGED:
            return state.acknowledged
        return False

    # ----- moving on -----

    def _begin(self, world: "SimulationWorld", step: TutorialStep) -> None:
        state = world.tutorial
        state.step_id = step.step_id
        state.since = world.clock.total_minutes
        state.opened = False
        state.acknowledged = False
        state.deeds = []

    def _complete(self, world: "SimulationWorld", step: TutorialStep) -> None:
        state = world.tutorial
        for gift in step.gifts:
            self._give(world, gift)
        state.done.append(step.step_id)
        world.emit_event(
            DomainEvent(STEP_DONE_EVENT, STEP_IMPORTANCE, step.done or step.title, data={"step": step.step_id})
        )
        steps = world.registries.tutorial.steps
        index = world.registries.tutorial.index_of(step.step_id)
        following = steps[index + 1] if index is not None and index + 1 < len(steps) else None
        if following is not None:
            self._begin(world, following)
            return
        state.step_id = None
        world.emit_event(DomainEvent(FINISHED_EVENT, FINISHED_IMPORTANCE, FINISHED_TEXT))

    @staticmethod
    def _give(world: "SimulationWorld", gift: Gift) -> None:
        """Hand over what a step gives. Things the game no longer defines are left out."""
        if world.registries.items.find(gift.item) is None:
            return
        if gift.into is not None:
            holders = containers_of_kind(world, gift.into)
            if holders:
                world.stock(holders[0][1], gift.item, gift.count, None)
            return
        resident = next(iter(world.residents.values()), None)
        if resident is not None:
            world.stock(resident.inventory, gift.item, gift.count, resident.resident_id)
