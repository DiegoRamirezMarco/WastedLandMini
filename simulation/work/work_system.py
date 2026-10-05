"""Jobs: residents go to their post during their shift, and the post does its work while staffed."""

from typing import TYPE_CHECKING

from simulation.ai.navigation import path_beside
from simulation.ai.utility_ai import ScoredAction
from simulation.events.event import DomainEvent
from simulation.items.inventory import Inventory
from simulation.items.item import ItemInstance
from simulation.residents.activity import Activity
from simulation.residents.needs import BODILY_NEEDS, URGENT_NEED
from simulation.residents.resident import Resident
from simulation.work.job import INTO_STATION, JobDefinition, ProduceRule
from world.interactable import Interactable

if TYPE_CHECKING:
    from simulation.world import SimulationWorld

WORK_ACTION = "work"
# Going to work beats idling and mild wants, and gives way to a real need.
WORK_SCORE = 0.6
# With a need this high a resident sees to it before starting or going back to work.
PRESSING_NEED = 80.0
WORK_EVENT_IMPORTANCE = 5
MINUTES_PER_DAY = 24 * 60


def minutes_left_in_shift(job: JobDefinition, hour: int, minute: int) -> int:
    """Minutes until the current shift ends, or 0 outside every shift. Shifts may wrap past midnight."""
    now = hour * 60 + minute
    for start, end in job.shifts:
        begins, ends = start * 60, end * 60
        if begins <= ends:
            if begins <= now < ends:
                return ends - now
        elif now >= begins or now < ends:
            return (ends - now) % MINUTES_PER_DAY
    return 0


class WorkSystem:
    def job_of(self, world: "SimulationWorld", resident: Resident) -> JobDefinition | None:
        return world.registries.jobs.get(resident.job_id or "")

    def on_duty(self, world: "SimulationWorld", resident: Resident) -> bool:
        """True while a resident is at their post, working."""
        activity = resident.activity
        return activity is not None and activity.action == WORK_ACTION and activity.using

    def is_staffed(self, world: "SimulationWorld", job_id: str) -> bool:
        """Whether anyone with this job is at their post right now."""
        return any(
            resident.job_id == job_id and self.on_duty(world, resident) for resident in world.residents.values()
        )

    def sight_bonus(self, world: "SimulationWorld", resident: Resident) -> int:
        job = self.job_of(world, resident)
        return job.sight_bonus if job is not None and self.on_duty(world, resident) else 0

    def candidate(self, world: "SimulationWorld", resident: Resident) -> ScoredAction | None:
        """Going to work, if the resident has a post, it is their shift, and no need is pressing."""
        job = self.job_of(world, resident)
        if job is None or resident.post_id not in world.interactables:
            return None
        if minutes_left_in_shift(job, world.clock.hour, world.clock.minute) <= 0:
            return None
        if any(getattr(resident.needs, need) >= PRESSING_NEED for need in BODILY_NEEDS):
            return None
        if not world.health.is_fit_for_work(resident):
            return None
        return ScoredAction(WORK_ACTION, WORK_SCORE, resident.post_id)

    def plan(self, world: "SimulationWorld", resident: Resident) -> Activity | None:
        placed = world.interactables.get(resident.post_id or "")
        path = path_beside(world, resident, placed) if placed is not None else None
        if path is None:
            return None
        return Activity(WORK_ACTION, resident.post_id, path)

    def tick(self, world: "SimulationWorld", resident: Resident, activity: Activity) -> None:
        """Spend one minute of a shift at the post."""
        job = self.job_of(world, resident)
        placed = world.interactables.get(activity.target_id or "")
        if job is None or placed is None:
            self._leave(resident)
            return
        if not activity.using:
            remaining = minutes_left_in_shift(job, world.clock.hour, world.clock.minute)
            if remaining <= 0:
                self._leave(resident)
                return
            activity.using = True
            activity.minutes_left = remaining
            resident.current_action = WORK_ACTION
            self._face(resident, placed)
            room = world.room_at(resident.tile)
            world.emit_event(
                DomainEvent(
                    "work_started",
                    WORK_EVENT_IMPORTANCE,
                    f"{resident.name} {job.text}",
                    [resident.resident_id],
                    location_id=room.room_id if room is not None else None,
                )
            )
        resident.needs.apply(job.per_minute)
        if job.produces is not None:
            self._produce(world, resident, job.produces, placed)
        activity.minutes_left -= 1
        if activity.minutes_left <= 0 or any(getattr(resident.needs, need) >= URGENT_NEED for need in BODILY_NEEDS):
            self._leave(resident)

    def _leave(self, resident: Resident) -> None:
        resident.activity = None
        resident.current_action = "idle"

    def _face(self, resident: Resident, placed: Interactable) -> None:
        dx, dy = placed.x - resident.x, placed.y - resident.y
        if dx or dy:
            resident.facing = ("right" if dx > 0 else "left") if abs(dx) > abs(dy) else ("down" if dy > 0 else "up")

    def _containers_of_kind(self, world: "SimulationWorld", kind: str) -> list[tuple[str, Inventory]]:
        return [
            (object_id, inventory)
            for object_id, inventory in world.containers.items()
            if object_id in world.interactables and world.interactables[object_id].kind == kind
        ]

    def _raw_material(self, world: "SimulationWorld", rule: ProduceRule) -> tuple[Inventory, ItemInstance] | None:
        """The fullest shared stack of something the rule can be made from."""
        best: tuple[Inventory, ItemInstance] | None = None
        for _, inventory in self._containers_of_kind(world, rule.source or ""):
            for item in inventory.items:
                definition = world.registries.items.resolve(item.definition_id)
                if item.owner_id is not None or definition.category != rule.source_category:
                    continue
                if rule.skip_tag is not None and rule.skip_tag in definition.tags:
                    continue
                if best is None or item.quantity > best[1].quantity:
                    best = (inventory, item)
        return best

    def _produce(self, world: "SimulationWorld", resident: Resident, rule: ProduceRule, placed: Interactable) -> None:
        resident.work_progress += 1
        if resident.work_progress < rule.every_minutes:
            return
        if rule.into == INTO_STATION:
            target = world.containers.get(placed.object_id)
        else:
            # Share the output between the containers of that kind, emptiest first.
            options = self._containers_of_kind(world, rule.into)
            target = min(options, key=lambda option: (option[1].count(rule.item), option[0]))[1] if options else None
        if target is None or target.count(rule.item) >= rule.max_stock:
            return
        if rule.source is not None:
            material = self._raw_material(world, rule)
            if material is None:
                return
            material[0].take_unit(material[1].instance_id)
        world.stock(target, rule.item, 1, None)
        resident.work_progress = 0
