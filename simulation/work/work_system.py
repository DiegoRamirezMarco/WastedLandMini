"""Jobs: residents go to their post during their shift, and the post does its work while staffed."""

import math
from typing import TYPE_CHECKING

from simulation.ai.navigation import path_beside
from simulation.ai.utility_ai import ScoredAction
from simulation.events.event import DomainEvent
from simulation.items.item import ItemInstance
from simulation.residents.activity import Activity
from simulation.residents.needs import BODILY_NEEDS, URGENT_NEED
from simulation.residents.resident import Resident
from simulation.work import hauling
from simulation.work.job import INTO_STATION, JobDefinition
from world.interactable import Interactable

if TYPE_CHECKING:
    from simulation.world import SimulationWorld

WORK_ACTION = "work"
# Carrying what the job makes or needs between the post and a container.
HAUL_ACTION = "haul"
WORK_ACTIONS = (WORK_ACTION, HAUL_ACTION)
# Going to work beats idling and mild wants, and gives way to a real need.
WORK_SCORE = 0.6
# With a need this high a resident sees to it before starting or going back to work.
PRESSING_NEED = 80.0
# Someone about to leave the settlement for hours sees to a need long before it gets that far.
SETTING_OUT_NEED = 50.0
WORK_EVENT_IMPORTANCE = 5
# Time spent loading or unloading at the end of a haul.
HAUL_MINUTES = 2
MINUTES_PER_DAY = 24 * 60
# How far ahead someone who keeps watch stays up for what they know is coming, and how long after.
WATCH_AHEAD_MINUTES = 8 * 60
WATCH_AFTER_MINUTES = 60
WATCH_NOTICE = "watch:"
LOW_MOOD_WORK_FLOOR = 0.75


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

    def is_day_off(self, world: "SimulationWorld", resident: Resident) -> bool:
        """Whether today is the day of the week this resident does not work."""
        if resident.day_off is None:
            return False
        return (world.clock.day - 1) % world.registries.economy.week_days == resident.day_off

    def shift_minutes_left(self, world: "SimulationWorld", resident: Resident, job: JobDefinition) -> int:
        """Minutes this resident still has to work right now. 0 off shift and on their day off.

        Someone whose job is to keep watch, and who knows what they watch for is on its way, is on
        duty until it has come and gone, shift or no shift.
        """
        shift = 0 if self.is_day_off(world, resident) else minutes_left_in_shift(job, world.clock.hour, world.clock.minute)
        if job.watch_for is None:
            return shift
        coming = world.happenings.expected(world, resident, job.watch_for, within=WATCH_AHEAD_MINUTES)
        if coming is None:
            return shift
        return max(shift, coming.at + WATCH_AFTER_MINUTES - world.clock.total_minutes)

    def tool_of(self, world: "SimulationWorld", resident: Resident, job: JobDefinition) -> ItemInstance | None:
        """The working tool for this job that a resident has on them, if the job uses one."""
        if job.tool is None:
            return None
        for item in resident.inventory.items:
            if not item.broken and job.tool.tag in world.registries.items.resolve(item.definition_id).tags:
                return item
        return None

    def candidate(self, world: "SimulationWorld", resident: Resident) -> ScoredAction | None:
        """Going to work, or on an errand for it, if the resident has a post and no need is pressing.

        Work is for the shift. Handing in what they still carry is also done once it is over.
        """
        job = self.job_of(world, resident)
        if job is None or resident.post_id not in world.interactables:
            return None
        leaving = job.expedition is not None and resident.last_expedition_day != world.clock.day
        pressing = SETTING_OUT_NEED if leaving else PRESSING_NEED
        if any(getattr(resident.needs, need) >= pressing for need in BODILY_NEEDS):
            return None
        if not world.health.is_fit_for_work(resident):
            return None
        if job.outdoors and world.happenings.is_stormy(world):
            # Work in the open waits for the weather, and so does whoever does it.
            return None
        remaining = self.shift_minutes_left(world, resident, job)
        if job.produces is not None:
            errand = hauling.errand(world, resident, job.produces, remaining)
            if errand is not None:
                return ScoredAction(HAUL_ACTION, WORK_SCORE, errand)
        if job.expedition is not None:
            # What was brought back from outside is put away before anything else.
            errand = world.expeditions.errand(world, resident)
            if errand is not None:
                return ScoredAction(HAUL_ACTION, WORK_SCORE, errand)
        radio_id = None
        if leaving and remaining > 0:
            # Nobody who is about to go out there leaves without hearing what the radio has to say.
            radio_id = world.happenings.radio_to_check(world, resident)
        elif job.watch_for is not None and not self.is_day_off(world, resident):
            # Whoever keeps watch hears the evening's bulletin before turning in, in case it is a night to stay up.
            radio_id = world.happenings.radio_to_check(world, resident, evening=True)
        if radio_id is not None:
            return ScoredAction(world.definition_of(world.interactables[radio_id]).use.action, WORK_SCORE, radio_id)
        if remaining <= 0:
            return None
        return ScoredAction(WORK_ACTION, WORK_SCORE, resident.post_id)

    def plan(
        self, world: "SimulationWorld", resident: Resident, candidate: ScoredAction | None = None
    ) -> Activity | None:
        """The walk to the post, or to the container an errand leads to."""
        hauling_to = candidate.target_id if candidate is not None and candidate.name == HAUL_ACTION else None
        placed = world.interactables.get(hauling_to or resident.post_id or "")
        path = path_beside(world, resident, placed) if placed is not None else None
        if path is None:
            return None
        if hauling_to is not None:
            return Activity(HAUL_ACTION, hauling_to, path, HAUL_MINUTES)
        return Activity(WORK_ACTION, resident.post_id, path)

    def tick(self, world: "SimulationWorld", resident: Resident, activity: Activity) -> None:
        """Spend one minute of a shift at the post."""
        job = self.job_of(world, resident)
        placed = world.interactables.get(activity.target_id or "")
        if job is None or placed is None or (job.outdoors and world.happenings.is_stormy(world)):
            self._leave(resident)
            return
        remaining = activity.minutes_left if activity.using else self.shift_minutes_left(world, resident, job)
        if world.expeditions.can_set_out(world, resident, job, remaining) and not world.expeditions.stays_in(
            world, resident, job
        ):
            # This job is done out there: the post is only where they leave from, as soon as they can.
            world.expeditions.set_out(world, resident, job)
            return
        if not activity.using:
            if remaining <= 0:
                self._leave(resident)
                return
            activity.using = True
            activity.minutes_left = remaining
            resident.current_action = WORK_ACTION
            self._face(resident, placed)
            room = world.room_at(resident.tile)
            self._say_if_watching(world, resident, job)
            world.emit_event(
                DomainEvent(
                    "work_started",
                    WORK_EVENT_IMPORTANCE,
                    f"{resident.name} {job.text if job.expedition is None else 'se queda al cuidado del carro'}",
                    [resident.resident_id],
                    location_id=room.room_id if room is not None else None,
                )
            )
        resident.needs.apply(job.per_minute)
        world.trade.pay_wage(world, resident, job)
        activity.minutes_left -= 1
        if job.produces is not None and not self._produce(world, resident, job, placed, activity.minutes_left):
            # Hands full, or nothing left to work with: off on an errand.
            self._leave(resident)
            return
        if activity.minutes_left <= 0 or any(getattr(resident.needs, need) >= URGENT_NEED for need in BODILY_NEEDS):
            self._leave(resident)

    def haul_tick(self, world: "SimulationWorld", resident: Resident, activity: Activity) -> None:
        """Spend one minute at the container a worker has carried things to, or come to fetch them from."""
        job = self.job_of(world, resident)
        placed = world.interactables.get(activity.target_id or "")
        if job is None or placed is None:
            self._leave(resident)
            return
        if not activity.using:
            done = hauling.exchange(world, resident, job.produces, placed) if job.produces is not None else None
            if done is None and job.expedition is not None:
                done = world.expeditions.unload(world, resident, placed)
            if done is None:
                self._leave(resident)
                return
            activity.using = True
            resident.current_action = HAUL_ACTION
            self._face(resident, placed)
            room = world.room_at(resident.tile)
            world.emit_event(
                DomainEvent(
                    "goods_hauled",
                    WORK_EVENT_IMPORTANCE,
                    f"{resident.name} {done}",
                    [resident.resident_id],
                    location_id=room.room_id if room is not None else None,
                )
            )
        world.trade.pay_wage(world, resident, job)
        activity.minutes_left -= 1
        if activity.minutes_left <= 0:
            self._leave(resident)

    def _say_if_watching(self, world: "SimulationWorld", resident: Resident, job: JobDefinition) -> None:
        """Say, once a night, that someone is at their post out of hours because of what they know is coming."""
        if job.watch_for is None or minutes_left_in_shift(job, world.clock.hour, world.clock.minute) > 0:
            return
        key = f"{WATCH_NOTICE}{resident.resident_id}"
        if world.notices.get(key) == world.clock.day:
            return
        world.notices[key] = world.clock.day
        world.emit_event(
            DomainEvent(
                "night_watch",
                WORK_EVENT_IMPORTANCE + 20,
                f"{resident.name} se queda de guardia esta noche por lo que anuncia la radio",
                [resident.resident_id],
            ),
            at=resident.tile,
        )

    def _leave(self, resident: Resident) -> None:
        resident.activity = None
        resident.current_action = "idle"

    def _face(self, resident: Resident, placed: Interactable) -> None:
        dx, dy = placed.x - resident.x, placed.y - resident.y
        if dx or dy:
            resident.facing = ("right" if dx > 0 else "left") if abs(dx) > abs(dy) else ("down" if dy > 0 else "up")

    def _produce(
        self, world: "SimulationWorld", resident: Resident, job: JobDefinition, placed: Interactable, shift_left: int
    ) -> bool:
        """One minute's work towards the next unit. False if the worker has to leave the post to go on.

        What is made stays in the post, or in the worker's hands until they carry it where it goes.
        Raw material is taken from what the worker has fetched.
        """
        rule = job.produces
        if rule.into == INTO_STATION:
            target = world.containers.get(placed.object_id)
            full = target is None or target.count(rule.item) >= rule.max_stock
        else:
            target = resident.inventory
            full = hauling.carried(resident, rule.item) >= rule.carry
        if target is None:
            return True
        if full:
            return hauling.errand(world, resident, rule, shift_left) is None
        tool = self.tool_of(world, resident, job)
        speed = job.tool.speed if job.tool is not None and tool is not None else 1.0
        # Short of an arm the work still gets done, in more minutes.
        speed *= world.health.work_pace(world, resident)
        speed *= self._mood_pace(resident)
        needed = math.ceil(rule.every_minutes / speed)
        resident.work_progress = min(resident.work_progress + 1, needed)
        if resident.work_progress < needed:
            return True
        if rule.source is not None:
            material = hauling.raw_carried(world, resident, rule)
            if material is None:
                return hauling.errand(world, resident, rule, shift_left) is None
            resident.inventory.take_unit(material.instance_id)
        world.stock(target, rule.item, 1, None)
        resident.work_progress = 0
        if tool is not None:
            world.items.wear(world, resident, tool)
        return True

    def _mood_pace(self, resident: Resident) -> float:
        """Low spirits make productive work drag; good spirits do not make it superhuman."""
        if resident.mood >= 50.0:
            return 1.0
        return max(LOW_MOOD_WORK_FLOOR, 0.75 + 0.25 * resident.mood / 50.0)
