"""Jobs: residents go to their post during their shift, and the post does its work while staffed."""

import math
from dataclasses import dataclass
from typing import TYPE_CHECKING

from simulation.ai.crowd import free_tile
from simulation.ai.navigation import path_beside
from simulation.ai.utility_ai import ScoredAction
from simulation.economy.ledger import MADE, USED
from simulation.events.event import DomainEvent
from simulation.items.item import ItemInstance
from simulation.residents.activity import Activity
from simulation.residents.attributes import CONSTITUTION, MIND
from simulation.residents.needs import BODILY_NEEDS, URGENT_NEED
from simulation.residents.resident import Resident
from simulation.work import hauling
from simulation.work.craft_system import tool_tag
from simulation.work.job import INTO_STATION, JobDefinition, SupplyRule
from simulation.work.research import JOB_PACE
from world.interactable import Interactable, UseDefinition
from world.pathfinding import find_path

if TYPE_CHECKING:
    from simulation.world import SimulationWorld

WORK_ACTION = "work"
# Carrying what the job makes or needs between the post and a container.
HAUL_ACTION = "haul"
# Going to the gate for what was bought there, to carry it in.
FETCH_ACTION = "fetch"
WORK_ACTIONS = (WORK_ACTION, HAUL_ACTION, FETCH_ACTION)
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
SHORTEST_SHIFT = 60
# How far ahead someone who keeps watch stays up for what they know is coming, and how long after.
WATCH_AHEAD_MINUTES = 8 * 60
WATCH_AFTER_MINUTES = 60
WATCH_NOTICE = "watch:"
LOW_MOOD_WORK_FLOOR = 0.75


@dataclass(frozen=True)
class Expected:
    """What somebody would make of a post."""

    # How many times as fast as a plain pair of hands: 1 for the same.
    pace: float
    # Units a day of what the job makes, where it makes something by the unit.
    per_day: float | None = None


def minutes_left_in_shift(job: JobDefinition, hour: int, minute: int, longer: int = 0) -> int:
    """Minutes until the current shift ends, or 0 outside every shift. Shifts may wrap past midnight.

    `longer` is how many minutes the working day goes on beyond its hours, or stops short of
    them if it is less than none: it is the last shift of the day that is longer or shorter
    for it, and never shorter than an hour.
    """
    now = hour * 60 + minute
    last = len(job.shifts) - 1
    for index, (start, end) in enumerate(job.shifts):
        length = (end - start) % 24 * 60
        if length <= 0:
            continue
        if longer and index == last:
            length = max(SHORTEST_SHIFT, min(MINUTES_PER_DAY, length + longer))
        since = (now - start * 60) % MINUTES_PER_DAY
        if since < length:
            return length - since
    return 0


class WorkSystem:
    def job_of(self, world: "SimulationWorld", resident: Resident) -> JobDefinition | None:
        return world.registries.jobs.get(resident.job_id or "")

    def supplies_of(self, world: "SimulationWorld", job: JobDefinition) -> SupplyRule | None:
        """What a worker sees to it that their post has: what the job says, or what is being studied calls for."""
        return job.supplies or world.research.supply_rule(world, job)

    def on_duty(self, world: "SimulationWorld", resident: Resident) -> bool:
        """True while a resident is at their post, working."""
        activity = resident.activity
        return activity is not None and activity.action == WORK_ACTION and activity.using

    def is_staffed(self, world: "SimulationWorld", job_id: str) -> bool:
        """Whether anyone with this job is at their post right now."""
        return any(
            resident.job_id == job_id and self.on_duty(world, resident) for resident in world.residents.values()
        )

    def open_to(self, world: "SimulationWorld", resident: Resident, use: UseDefinition) -> bool:
        """Whether a use that wants somebody at the post is open to a resident right now: someone
        is on duty there, or the post is their own and they can serve themselves at it."""
        if use.staffed_by is None or self.is_staffed(world, use.staffed_by):
            return True
        return use.repairs <= 0 and resident.job_id == use.staffed_by

    def sight_bonus(self, world: "SimulationWorld", resident: Resident) -> int:
        """Tiles further a resident sees for being on watch: what the job says, and one more
        for every two levels they have at it."""
        job = self.job_of(world, resident)
        if job is None or not job.sight_bonus or not self.on_duty(world, resident):
            return 0
        return job.sight_bonus + (world.crafts.level(world, resident, job.job_id) - 1) // 2

    def is_day_off(self, world: "SimulationWorld", resident: Resident) -> bool:
        """Whether today is a day this resident does not work: their own day of the week, or
        one the law gives everybody."""
        if world.politics.laws.day_off(world, resident):
            return True
        if resident.day_off is None:
            return False
        return (world.clock.day - 1) % world.registries.economy.week_days == resident.day_off

    def shift_minutes_left(self, world: "SimulationWorld", resident: Resident, job: JobDefinition) -> int:
        """Minutes this resident still has to work right now. 0 off shift and on their day off.

        Someone whose job is to keep watch, and who knows what they watch for is on its way, is on
        duty until it has come and gone, shift or no shift.
        """
        longer = world.politics.laws.shift_minutes(world)
        shift = (
            0
            if self.is_day_off(world, resident)
            else minutes_left_in_shift(job, world.clock.hour, world.clock.minute, longer)
        )
        if job.watch_for is None:
            return shift
        coming = world.happenings.expected(world, resident, job.watch_for, within=WATCH_AHEAD_MINUTES)
        if coming is None:
            return shift
        return max(shift, coming.at + WATCH_AFTER_MINUTES - world.clock.total_minutes)

    def tool_of(self, world: "SimulationWorld", resident: Resident, job: JobDefinition) -> ItemInstance | None:
        """The working tool for this job that a resident has on them: one of the kind the job
        uses, or one somebody made for it (S47). The one that makes the work go fastest."""
        best: tuple[float, ItemInstance] | None = None
        for item in resident.inventory.items:
            speed = self.tool_speed(world, job, item)
            if speed is not None and (best is None or speed > best[0]):
                best = (speed, item)
        return best[1] if best is not None else None

    def tool_speed(self, world: "SimulationWorld", job: JobDefinition, item: ItemInstance) -> float | None:
        """How many times as fast an item makes a job go. None for what is no tool for it, or is broken."""
        if item.broken:
            return None
        definition = world.registries.items.resolve(item.definition_id)
        # A rarer tool is that much faster (S64).
        better = world.items.better(world, item)
        if job.tool is not None and job.tool.tag in definition.tags:
            return job.tool.speed * better
        if tool_tag(job.job_id) in definition.tags:
            return max(1.0, definition.properties.get("speed", 1.0)) * better
        return None

    def candidate(self, world: "SimulationWorld", resident: Resident) -> ScoredAction | None:
        """Going to work, or on an errand for it, if the resident has a post and no need is pressing.

        Work is for the shift. Handing in what they still carry is also done once it is over.
        """
        job = self.job_of(world, resident)
        if job is None or resident.post_id not in world.interactables:
            return None
        if world.upgrades.in_hand(world, resident.post_id):
            # Nobody works at a post while it is being made better.
            return None
        if world.power.stopped(world, resident.post_id) and not world.staffing.fall_back(world, resident, job):
            # Nor at one that runs on current and has none, unless there is another of the
            # job's that needs none, which they take (S55).
            return None
        leaving = job.expedition is not None and resident.last_expedition_day != world.clock.day
        pressing = SETTING_OUT_NEED if leaving else PRESSING_NEED
        if world.activities.urgent_needs(world, resident, pressing):
            return None
        if not world.health.is_fit_for_work(resident):
            return None
        if world.politics.laws.excused(world, resident):
            # The law has them rest, and nobody is held to have stopped working for it.
            resident.last_worked = world.clock.total_minutes
            return None
        if job.outdoors and world.happenings.is_stormy(world):
            # Work in the open waits for the weather, and so does whoever does it.
            return None
        remaining = self.shift_minutes_left(world, resident, job)
        if job.produces is not None:
            errand = hauling.errand(world, resident, job.produces, remaining)
            if errand is not None:
                return ScoredAction(HAUL_ACTION, WORK_SCORE, errand)
        supplies = self.supplies_of(world, job)
        if supplies is not None:
            errand = hauling.supply_errand(world, resident, supplies, remaining)
            if errand is not None:
                return ScoredAction(HAUL_ACTION, WORK_SCORE, errand)
        if job.expedition is not None:
            # What was brought back from outside is put away before anything else.
            errand = world.expeditions.errand(world, resident)
            if errand is not None:
                return ScoredAction(HAUL_ACTION, WORK_SCORE, errand)
        # What was handed to them for the settlement, or bought for it, is carried to where it is kept.
        errand = world.fund.takings_errand(world, resident)
        if errand is not None:
            return ScoredAction(HAUL_ACTION, WORK_SCORE, errand)
        if world.fund.fetches_from_gate(world, resident):
            return ScoredAction(FETCH_ACTION, WORK_SCORE)
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
        if candidate is not None and candidate.name == FETCH_ACTION:
            spot = free_tile(world, world.happenings.arrival_tile(world), resident)
            way = find_path(resident.tile, spot, world.passable())
            return Activity(FETCH_ACTION, None, way, HAUL_MINUTES) if way is not None else None
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
        if world.upgrades.in_hand(world, placed.object_id) or world.power.stopped(world, placed.object_id):
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
        resident.needs.apply(self._toll(world, resident, job))
        world.attributes.practise(world, resident, job.stat, "work")
        world.crafts.worked(world, resident, job)
        world.trade.pay_wage(world, resident, job)
        activity.minutes_left -= 1
        if job.produces is not None and not self._produce(world, resident, job, placed, activity.minutes_left):
            # Hands full, or nothing left to work with: off on an errand.
            self._leave(resident)
            return
        if job.research:
            world.research.work(world, resident, placed)
            world.rush.after_minute(world, resident, job, placed)
        if job.produces is None and job.expedition is None:
            # A post that makes nothing of its own: what its worker has come to is made there.
            world.crafts.craft(world, resident, job, placed)
        supplies = self.supplies_of(world, job)
        if supplies is not None and self._called_away(world, resident, supplies, placed, activity.minutes_left):
            self._leave(resident)
            return
        if world.fund.fetches_from_gate(world, resident) and world.users_of(placed.object_id) == 0:
            # Something bought for the settlement waits at the gate, and nobody is being served.
            self._leave(resident)
            return
        if activity.minutes_left <= 0 or world.activities.urgent_needs(world, resident):
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
            supplies = self.supplies_of(world, job)
            if done is None and supplies is not None:
                done = hauling.supply_exchange(world, resident, supplies, placed)
            if done is None and job.expedition is not None:
                done = world.expeditions.unload(world, resident, placed)
            if done is None:
                done = world.fund.unload_takings(world, resident, placed)
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

    def fetch_tick(self, world: "SimulationWorld", resident: Resident, activity: Activity) -> None:
        """Spend one minute at the gate, loading up with what was bought there for the settlement."""
        job = self.job_of(world, resident)
        if not activity.using:
            done = world.fund.pick_up_at_gate(world, resident)
            if done is None:
                self._leave(resident)
                return
            activity.using = True
            resident.current_action = HAUL_ACTION
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
        if job is not None:
            world.trade.pay_wage(world, resident, job)
        activity.minutes_left -= 1
        if activity.minutes_left <= 0:
            self._leave(resident)

    def _toll(self, world: "SimulationWorld", resident: Resident, job: JobDefinition) -> dict[str, float]:
        """What a minute of the job does to whoever does it: it tires a strong constitution less."""
        tiring = job.per_minute.get("tiredness", 0.0)
        toll = job.per_minute
        if tiring > 0.0:
            spared = world.attributes.factor(world, resident, CONSTITUTION, "tiredness")
            toll = {**job.per_minute, "tiredness": tiring * max(0.0, 2.0 - spared)}
        # Pushed, it takes more out of them, whatever the job.
        return world.rush.toll(world, resident, toll)

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

    def _called_away(
        self, world: "SimulationWorld", resident: Resident, supplies: SupplyRule, placed: Interactable, shift_left: int
    ) -> bool:
        """Whether a worker should leave the post to fetch what they keep supplied. Nobody being served is left."""
        if world.users_of(placed.object_id) > 0:
            return False
        return hauling.supply_errand(world, resident, supplies, shift_left) is not None

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
        making = rule.item
        # What they have come to at the job, or been shown, is made in turn with what the job
        # gives anybody: whichever there is least of. A thing made of another needs it in hand.
        own = {
            product.item_id: product
            for product in world.crafts.products(world, resident, job)
            if product.ripe and (product.needs is None or resident.inventory.stack_of(product.needs, None) is not None)
        }
        if rule.into == INTO_STATION:
            target = world.containers.get(placed.object_id)
            if target is not None:
                # Of the things made here, the one there is least of.
                making = min((rule.item, *rule.also, *own), key=target.count)
            full = target is None or target.count(making) >= rule.max_stock
            # What is made here and kept in a store has no more room than the store has.
            full = full or world.stores.room_at(world, target, making) <= 0
        else:
            target = resident.inventory
            if own:
                making = min((rule.item, *own), key=lambda item_id: hauling.kept(world, resident, rule, item_id))
            full = hauling.carried_made(world, resident, rule) >= hauling.load(world, resident, rule)
        if target is None:
            return True
        if full:
            return hauling.errand(world, resident, rule, shift_left) is None
        how = own.get(making)
        tool = self.tool_of(world, resident, job)
        speed = self.pace(world, resident, job, tool)
        needed = math.ceil((how.every_minutes if how is not None else rule.every_minutes) / speed)
        resident.work_needed = needed
        resident.work_progress = min(resident.work_progress + 1, needed)
        if resident.work_progress < needed:
            return True
        if rule.source is not None:
            material = (
                resident.inventory.stack_of(how.needs, None)
                if how is not None and how.needs is not None
                else hauling.raw_carried(world, resident, rule)
            )
            if material is None:
                return hauling.errand(world, resident, rule, shift_left) is None
            resident.inventory.take_unit(material.instance_id)
            world.ledger.record(world, material.definition_id, -1, USED, job.job_id)
        units = how.batch if how is not None else 1
        # What a post makes is as rare as the post (S64).
        world.stock(target, making, units, None, placed.level)
        world.ledger.record(world, making, units, MADE, job.job_id, resident.resident_id, placed.object_id)
        resident.work_progress = 0
        if tool is not None:
            world.items.wear(world, resident, tool)
        world.rush.after_unit(world, resident, job, placed)
        return True

    def pace(
        self, world: "SimulationWorld", resident: Resident, job: JobDefinition, tool: ItemInstance | None = None
    ) -> float:
        """How many times as fast as a plain pair of hands a resident turns out what a job makes,
        with `tool` in them: what everything that tells on it comes to."""
        speed = self.tool_speed(world, job, tool) or 1.0 if tool is not None else 1.0
        if resident.job_id == job.job_id:
            # A post that has been made better is worked that much faster (S54), and one
            # kind of post may be slower than another of the same job (S55).
            speed *= world.upgrades.better(world, resident.post_id)
            post = world.interactables.get(resident.post_id or "")
            speed *= world.definition_of(post).post_pace if post is not None else 1.0
        # Short of an arm the work still gets done, in more minutes.
        speed *= world.health.work_pace(world, resident)
        speed *= self.mood_pace(resident)
        speed *= world.trade.unpaid_pace(world, resident)
        speed *= world.substances.work_pace(world, resident)
        speed *= world.politics.work_pace(world, resident)
        # Whoever has more of what the job goes by does it faster.
        speed *= world.attributes.work_pace(world, resident, job)
        # What has been worked out about a trade makes it go faster.
        speed *= world.research.factor(world, f"{JOB_PACE}{job.job_id}")
        # And so does every level whoever does it has at it.
        speed *= world.crafts.pace(world, resident, job)
        # And being pushed, for as long as it lasts: at the post that is theirs, and no other.
        if resident.job_id == job.job_id:
            speed *= world.rush.pace(world, resident)
        return speed

    def progress(self, world: "SimulationWorld", resident: Resident) -> float | None:
        """How far along whoever is at their post is with the next unit, or with what is being
        worked out, from 0 to 1. None for whoever is not at a post where anything is."""
        job = self.job_of(world, resident)
        if job is None or not self.on_duty(world, resident):
            return None
        if job.research:
            return world.research.progress_of(world)
        if resident.work_needed <= 0:
            return None
        return max(0.0, min(1.0, resident.work_progress / resident.work_needed))

    def expected(self, world: "SimulationWorld", resident: Resident, job: JobDefinition) -> "Expected":
        """What a resident would make of a job as they are today, whether or not it is theirs:
        how fast beside a plain pair of hands, and how many units a day where it makes any."""
        pace = self.pace(world, resident, job, self.tool_of(world, resident, job))
        if job.research:
            # What is worked out goes by the head, and by nothing that is made with the hands.
            pace = world.health.work_pace(world, resident) * self.mood_pace(resident)
            pace *= world.attributes.factor(world, resident, MIND, "study") * world.crafts.pace(world, resident, job)
            if resident.job_id == job.job_id:
                pace *= world.rush.pace(world, resident)
        per_day = None
        if job.produces is not None and pace > 0:
            shift = sum((end - start) % 24 * 60 for start, end in job.shifts)
            per_day = shift / math.ceil(job.produces.every_minutes / pace)
        return Expected(pace, per_day)

    def mood_pace(self, resident: Resident) -> float:
        """Low spirits make productive work drag; good spirits do not make it superhuman."""
        if resident.mood >= 50.0:
            return 1.0
        return max(LOW_MOOD_WORK_FLOOR, 0.75 + 0.25 * resident.mood / 50.0)
