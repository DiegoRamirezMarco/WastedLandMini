"""Who holds which post: taking up a job, and noticing the jobs nobody is doing."""

import math

from typing import TYPE_CHECKING

from simulation.events.event import DomainEvent
from simulation.residents.resident import Resident
from simulation.work.job import JobDefinition
from simulation.work.work_system import WORK_ACTIONS

if TYPE_CHECKING:
    from simulation.world import SimulationWorld

JOB_CHANGE_IMPORTANCE = 40
VACANCY_IMPORTANCE = 35
# Hours without anyone after which a vacancy weighs as much as it ever will on whoever is asked.
PRESSING_VACANCY_HOURS = 72.0
VACANCY_NOTICE = "vacant:"


class StaffingSystem:
    def workers(self, world: "SimulationWorld", job_id: str) -> list[Resident]:
        return [resident for resident in world.residents.values() if resident.job_id == job_id]

    def free_post(self, world: "SimulationWorld", job: JobDefinition) -> str | None:
        """An object this job is worked at that is nobody's post yet, in map order."""
        taken = {resident.post_id for resident in world.residents.values()}
        return next(
            (
                object_id
                for object_id, placed in world.interactables.items()
                if job.works_at(placed.kind) and object_id not in taken
            ),
            None,
        )

    def needed(self, world: "SimulationWorld", job: JobDefinition) -> int:
        """How many people a job takes right now: what its data says, and for one that feeds or
        waters the settlement, more as more people live in it."""
        if job.per_residents <= 0:
            return job.needed
        return max(job.needed, math.ceil(len(world.residents) / job.per_residents))

    def is_short(self, world: "SimulationWorld", job: JobDefinition) -> bool:
        """Whether a job has fewer people than it takes and a post standing free for another.
        Whoever a law has resting does not count: somebody has to see to what they did."""
        at_it = [
            resident for resident in self.workers(world, job.job_id) if not world.politics.laws.excused(world, resident)
        ]
        return len(at_it) < self.needed(world, job) and self.free_post(world, job) is not None

    def holder(self, world: "SimulationWorld", post_id: str) -> Resident | None:
        """Whoever has an object as their post, if anybody has."""
        return next((resident for resident in world.residents.values() if resident.post_id == post_id), None)

    def job_at(self, world: "SimulationWorld", post_id: str) -> JobDefinition | None:
        """The job an object is a post of, if it is one."""
        placed = world.interactables.get(post_id)
        if placed is None:
            return None
        return next((job for job in world.registries.jobs.values() if job.works_at(placed.kind)), None)

    def assign(
        self, world: "SimulationWorld", resident: Resident, job_id: str, post_id: str | None = None
    ) -> bool:
        """Give a resident a job and a free post for it, in place of any they had. False if
        there is none. With `post_id` it is that post and no other, which may be another of
        the job they have."""
        job = world.registries.jobs.get(job_id)
        if job is not None and post_id is not None:
            fits = self.job_at(world, post_id) is job and self.holder(world, post_id) is None
            post_id = post_id if fits else None
        elif job is not None and resident.job_id != job_id:
            post_id = self.free_post(world, job)
        if job is None or post_id is None:
            return False
        previous = world.registries.jobs.get(resident.job_id or "")
        self._leave_post(world, resident)
        if previous is job:
            # Another post of the job they had: nothing else changes, and nothing is said.
            resident.post_id = post_id
            return True
        resident.job_id, resident.post_id, resident.work_progress = job_id, post_id, 0
        resident.seeks_work = False
        text = f"{resident.name} se hace cargo de un puesto: {job.name}"
        if previous is not None:
            text = f"{resident.name} cambia de puesto: de {previous.name} a {job.name}"
        self._say_changed(world, resident, text)
        return True

    def fall_back(self, world: "SimulationWorld", resident: Resident, job: JobDefinition) -> bool:
        """Have somebody whose post stands idle for want of current take another post of
        their job that is not, if one stands free: whoever draws water goes to the well when
        the tank stops (S55). Says whether they have one they can work at now."""
        taken = {each.post_id for each in world.residents.values()}
        for object_id, placed in world.interactables.items():
            if job.works_at(placed.kind) and object_id not in taken and world.power.powered(world, object_id):
                return self.assign(world, resident, job.job_id, object_id)
        return False

    def swap(self, world: "SimulationWorld", one: Resident, other: Resident) -> bool:
        """Have two residents change posts: each takes the job and the post the other had.
        Whoever changes with somebody who had none is left with none. False if there is
        nothing to change."""
        if one is other or (one.post_id is None and other.post_id is None):
            return False
        jobs = world.registries.jobs
        before = {each.resident_id: (each.job_id, each.post_id) for each in (one, other)}
        for each in (one, other):
            self._leave_post(world, each)
        for each, given in ((one, other), (other, one)):
            had, (job_id, post_id) = jobs.get(each.job_id or ""), before[given.resident_id]
            now = jobs.get(job_id or "")
            if now is had:
                each.post_id = post_id
                continue
            each.job_id, each.post_id, each.work_progress = job_id, post_id, 0
            if now is None:
                text = f"{each.name} deja su puesto: {had.name}"
            elif had is None:
                each.seeks_work = False
                text = f"{each.name} se hace cargo de un puesto: {now.name}"
            else:
                text = f"{each.name} cambia de puesto: de {had.name} a {now.name}"
            self._say_changed(world, each, text)
        return True

    def _leave_post(self, world: "SimulationWorld", resident: Resident) -> None:
        """Have a resident stop working at the post they have, for being about to have another."""
        if resident.activity is not None and resident.activity.action in WORK_ACTIONS:
            resident.activity = None
            resident.current_action = "idle"
        self._put_down(world, resident)
        # A push is of the post they had: it does not go with them to another.
        world.rush.ease(resident)

    def _say_changed(self, world: "SimulationWorld", resident: Resident, text: str) -> None:
        room = world.room_at(resident.tile)
        world.emit_event(
            DomainEvent(
                "job_changed",
                JOB_CHANGE_IMPORTANCE,
                text,
                [resident.resident_id],
                location_id=room.room_id if room is not None else None,
            ),
            at=resident.tile,
        )

    def tick(self, world: "SimulationWorld") -> None:
        """Once an hour, keep track of the jobs that are short of people and give notice of them."""
        if world.clock.minute != 0:
            return
        now = world.clock.total_minutes
        notice_minutes = world.registries.economy.vacancy_notice_hours * 60
        for job_id, job in world.registries.jobs.items():
            key = f"{VACANCY_NOTICE}{job_id}"
            if not self.is_short(world, job):
                world.vacancies.pop(job_id, None)
                world.notices.pop(key, None)
                continue
            since = world.vacancies.setdefault(job_id, now)
            if now - since >= notice_minutes and key not in world.notices:
                world.notices[key] = world.clock.day
                world.emit_event(
                    DomainEvent("post_vacant", VACANCY_IMPORTANCE, f"Nadie se ocupa de un puesto: {job.name}")
                )

    def overdue(self, world: "SimulationWorld") -> list[str]:
        """Jobs that have been short of people long enough to do something about, most missed first."""
        now = world.clock.total_minutes
        notice_minutes = world.registries.economy.vacancy_notice_hours * 60
        jobs = world.registries.jobs
        late = [
            job_id
            for job_id, since in world.vacancies.items()
            if job_id in jobs and now - since >= notice_minutes and self.is_short(world, jobs[job_id])
        ]
        return sorted(late, key=lambda job_id: (-jobs[job_id].priority, job_id))

    def opening_for(self, world: "SimulationWorld", resident: Resident) -> str | None:
        """The job someone looking for work would think of taking: the one most missed that has a free post."""
        if not resident.seeks_work or resident.job_id in world.registries.jobs:
            return None
        if not world.health.is_fit_for_work(resident):
            return None
        free = [job for job in world.registries.jobs.values() if self.free_post(world, job) is not None]
        if not free:
            return None
        return max(free, key=lambda job: (self.is_short(world, job), job.priority)).job_id

    def candidates(self, world: "SimulationWorld", job_id: str) -> list[Resident]:
        """Residents who could reasonably be asked to take a job, the most obvious choice first.

        Those with no job come first, then those whose own job has people to spare, then those
        whose job matters less than this one. Nobody is asked to leave a job that matters as much.
        """
        job = world.registries.jobs[job_id]
        ranked: list[tuple[int, int, int, Resident]] = []
        for index, resident in enumerate(world.residents.values()):
            if resident.job_id == job_id or not world.health.is_fit_for_work(resident):
                continue
            current = world.registries.jobs.get(resident.job_id or "")
            if current is None:
                ranked.append((0, 0, index, resident))
            elif len(self.workers(world, current.job_id)) > self.needed(world, current):
                ranked.append((1, current.priority, index, resident))
            elif current.priority < job.priority:
                ranked.append((2, current.priority, index, resident))
        return [entry[3] for entry in sorted(ranked, key=lambda entry: entry[:3])]

    def decision_inputs(self, world: "SimulationWorld", resident: Resident, job_id: str) -> dict[str, float]:
        """What a resident weighs about taking a job, each from 0 to 1."""
        since = world.vacancies.get(job_id)
        hours = (world.clock.total_minutes - since) / 60.0 if since is not None else 0.0
        return {
            "vacancy": max(0.0, min(1.0, hours / PRESSING_VACANCY_HOURS)),
            "idle": 0.0 if resident.job_id in world.registries.jobs else 1.0,
        }

    def _put_down(self, world: "SimulationWorld", resident: Resident) -> None:
        """Leave what was being carried for the old job in the nearest container."""
        nearest = world.nearest_container(resident.tile)
        if nearest is None:
            return
        for item in [item for item in resident.inventory.items if item.owner_id is None]:
            resident.inventory.remove(item.instance_id)
            world.containers[nearest].add(item)
