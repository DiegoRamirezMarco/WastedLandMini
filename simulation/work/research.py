"""Research: the player says what is to be worked out, and whoever holds the post for it works
it out on their shift. What is known opens up things to build and makes other things go better."""

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from simulation.residents.attributes import MIND
from simulation.events.event import DomainEvent
from simulation.residents.resident import Resident
from simulation.work.job import JobDefinition, SupplyRule
from world.build import BUILDING_SITE
from world.interactable import Interactable

if TYPE_CHECKING:
    from simulation.world import SimulationWorld

# What knowing a subject may make go better. Each is a factor on a figure of the simulation.
BUILD_PACE = "build_pace"  # work done on a site in a minute
EXPEDITION_DANGER = "expedition_danger"  # the chance of coming back hurt from a trip outside
EXPEDITION_FINDS = "expedition_finds"  # how much a trip outside brings back
DOSE_MINUTES = "dose_minutes"  # how long a dose given in care goes on working
JOB_PACE = "pace:"  # followed by a job ID: what that job turns out
EFFECTS = (BUILD_PACE, EXPEDITION_DANGER, EXPEDITION_FINDS, DOSE_MINUTES)

# How a subject stands.
KNOWN = "known"
IN_HAND = "in_hand"
OPEN = "open"
CLOSED = "closed"

CHOSEN_EVENT = "research_chosen"
FINISHED_EVENT = "research_finished"
WAITING_EVENT = "research_waiting"
CHOSEN_IMPORTANCE = 20
WAITING_IMPORTANCE = 30
FINISHED_IMPORTANCE = 45
IDLE_NOTICE = "study:idle"
ITEM_NOTICE = "study:item"
NOT_KNOWN = "Eso todavía no se sabe hacer. Hay que averiguar: {subject}"


@dataclass(frozen=True)
class SubjectDefinition:
    """Something that can be worked out: what it takes, and what knowing it does."""

    subject_id: str
    name: str
    text: str = ""
    # Minutes of somebody's shift at the post.
    minutes: int = 60
    # Subjects that have to be known first.
    requires: tuple[str, ...] = ()
    # Item that is studied and used up doing it, and how many of it.
    item: str | None = None
    count: int = 1
    # Object kinds and blueprints that nobody knows how to put up until this is known.
    objects: tuple[str, ...] = ()
    buildings: tuple[str, ...] = ()
    # What goes better for knowing it: a factor for each of EFFECTS, or for a job's pace.
    effects: dict[str, float] = field(default_factory=dict)


@dataclass(frozen=True)
class ResearchSettings:
    subjects: dict[str, SubjectDefinition] = field(default_factory=dict)


@dataclass
class ResearchState:
    """What a settlement knows, and what it is working out."""

    # The subject in hand, if one has been chosen.
    subject_id: str | None = None
    # Subjects worked out, oldest first.
    known: list[str] = field(default_factory=list)
    # Minutes of work done on each subject that is not known yet.
    progress: dict[str, float] = field(default_factory=dict)
    # Subjects whose item has already been handed over and used up.
    supplied: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ResearchResult:
    ok: bool
    message: str


def subject_definition_from_data(subject_id: str, data: dict[str, Any]) -> SubjectDefinition:
    if not isinstance(data, dict) or "name" not in data:
        raise ValueError(f"Research subject {subject_id} needs a name")
    needs = data.get("needs")
    if needs is not None and (not isinstance(needs, dict) or "item" not in needs):
        raise ValueError(f"Research subject {subject_id} must say which item it needs")
    opens = data.get("opens", {})
    subject = SubjectDefinition(
        subject_id=subject_id,
        name=str(data["name"]),
        text=str(data.get("text", "")),
        minutes=int(data.get("minutes", 60)),
        requires=tuple(str(each) for each in data.get("requires", [])),
        item=str(needs["item"]) if needs is not None else None,
        count=int(needs.get("count", 1)) if needs is not None else 1,
        objects=tuple(str(kind) for kind in opens.get("objects", [])),
        buildings=tuple(str(blueprint) for blueprint in opens.get("buildings", [])),
        effects={str(name): float(factor) for name, factor in data.get("effects", {}).items()},
    )
    if subject.minutes < 1 or subject.count < 1:
        raise ValueError(f"Research subject {subject_id} must take a minute and an item or more")
    if any(factor <= 0 for factor in subject.effects.values()):
        raise ValueError(f"Research subject {subject_id} has an effect that is not a factor above zero")
    return subject


def research_settings_from_data(data: dict[str, Any]) -> ResearchSettings:
    subjects = {
        str(subject_id): subject_definition_from_data(str(subject_id), values)
        for subject_id, values in data.get("subjects", {}).items()
    }
    for subject in subjects.values():
        unknown = [each for each in subject.requires if each not in subjects]
        if unknown:
            raise ValueError(f"Research subject {subject.subject_id} requires unknown subjects: {unknown}")
    # Nothing may wait, however far back, for itself.
    settled: set[str] = set()
    while len(settled) < len(subjects):
        ready = [each for each in subjects.values() if each.subject_id not in settled and set(each.requires) <= settled]
        if not ready:
            raise ValueError(f"Research subjects require each other in a circle: {sorted(set(subjects) - settled)}")
        settled.update(each.subject_id for each in ready)
    return ResearchSettings(subjects)


class ResearchSystem:
    # ----- what there is to know -----

    def subjects(self, world: "SimulationWorld") -> list[SubjectDefinition]:
        return list(world.registries.research.subjects.values())

    def in_hand(self, world: "SimulationWorld") -> SubjectDefinition | None:
        return world.registries.research.subjects.get(world.studies.subject_id or "")

    def knows(self, world: "SimulationWorld", subject_id: str) -> bool:
        return subject_id in world.studies.known

    def status(self, world: "SimulationWorld", subject: SubjectDefinition) -> str:
        """How a subject stands: known, in hand, open to be chosen, or closed for want of another."""
        if self.knows(world, subject.subject_id):
            return KNOWN
        if world.studies.subject_id == subject.subject_id:
            return IN_HAND
        return OPEN if all(self.knows(world, each) for each in subject.requires) else CLOSED

    def fraction_done(self, world: "SimulationWorld", subject: SubjectDefinition) -> float:
        if self.knows(world, subject.subject_id):
            return 1.0
        return max(0.0, min(1.0, world.studies.progress.get(subject.subject_id, 0.0) / subject.minutes))

    def lock_on(self, world: "SimulationWorld", kind: str, what: str) -> SubjectDefinition | None:
        """The subject that has to be known before an object kind or a blueprint can be put up, if it is not."""
        for subject in world.registries.research.subjects.values():
            opened = subject.buildings if kind == BUILDING_SITE else subject.objects
            if what in opened and not self.knows(world, subject.subject_id):
                return subject
        return None

    def factor(self, world: "SimulationWorld", effect: str) -> float:
        """By how much what is known multiplies a figure of the simulation. 1 for nothing known that touches it."""
        subjects = world.registries.research.subjects
        factor = 1.0
        for subject_id in world.studies.known:
            subject = subjects.get(subject_id)
            if subject is not None:
                factor *= subject.effects.get(effect, 1.0)
        return factor

    # ----- what the player does -----

    def obstacle(self, world: "SimulationWorld", subject_id: str) -> str | None:
        """Why a subject cannot be taken in hand. None if it can."""
        subjects = world.registries.research.subjects
        subject = subjects.get(subject_id)
        if subject is None:
            return "Eso no es algo que se pueda averiguar"
        if self.knows(world, subject_id):
            return f"Eso ya se sabe: {subject.name}"
        missing = [subjects[each].name for each in subject.requires if not self.knows(world, each)]
        if missing:
            return f"Antes hay que averiguar: {', '.join(missing)}"
        return None

    def choose(self, world: "SimulationWorld", subject_id: str | None) -> ResearchResult:
        """Say what is to be worked out next, or with None that nothing is. What was done on another is kept."""
        state = world.studies
        if subject_id is None:
            state.subject_id = None
            return ResearchResult(True, "No se estudia nada")
        error = self.obstacle(world, subject_id)
        if error is not None:
            return ResearchResult(False, error)
        subject = world.registries.research.subjects[subject_id]
        if state.subject_id != subject_id:
            state.subject_id = subject_id
            world.notices.pop(IDLE_NOTICE, None)
            world.notices.pop(ITEM_NOTICE, None)
            world.emit_event(
                DomainEvent(
                    CHOSEN_EVENT, CHOSEN_IMPORTANCE, f"Se empieza a estudiar: {subject.name}", data={"subject": subject_id}
                )
            )
        return ResearchResult(True, f"Se estudia: {subject.name}")

    def grant_what_stands(self, world: "SimulationWorld") -> None:
        """Have a settlement know how to put up what it already has standing, and all that takes knowing."""
        subjects = world.registries.research.subjects
        kinds = {placed.kind for placed in world.interactables.values()}
        blueprints = {room.blueprint_id for room in world.rooms.values()}
        pending = [
            subject.subject_id
            for subject in subjects.values()
            if kinds & set(subject.objects) or blueprints & set(subject.buildings)
        ]
        while pending:
            subject_id = pending.pop()
            if subject_id in world.studies.known or subject_id not in subjects:
                continue
            world.studies.known.append(subject_id)
            pending.extend(subjects[subject_id].requires)
        # Told in the order the game lists them, whatever order they were come upon in.
        world.studies.known.sort(key=list(subjects).index)

    # ----- what whoever holds the post does -----

    def supply_rule(self, world: "SimulationWorld", job: JobDefinition) -> SupplyRule | None:
        """What a job that studies has to have brought to its post for the subject in hand, if anything still."""
        subject = self.in_hand(world)
        if not job.research or subject is None or subject.item is None:
            return None
        if subject.subject_id in world.studies.supplied:
            return None
        return SupplyRule(subject.item, job.station, low=subject.count, carry=subject.count, max_stock=subject.count)

    def work(self, world: "SimulationWorld", resident: Resident, placed: Interactable) -> None:
        """One minute of somebody's shift at a post where things are worked out."""
        subject = self.in_hand(world)
        if subject is None or not self._has_material(world, subject, placed.kind):
            return
        state = world.studies
        pace = world.health.work_pace(world, resident) * world.work.mood_pace(resident)
        pace *= world.attributes.factor(world, resident, MIND, "study")
        job = world.work.job_of(world, resident)
        if job is not None:
            pace *= world.crafts.pace(world, resident, job)
        state.progress[subject.subject_id] = state.progress.get(subject.subject_id, 0.0) + pace
        if state.progress[subject.subject_id] >= subject.minutes:
            self._finish(world, subject, resident)

    def tick(self, world: "SimulationWorld") -> None:
        """Once an hour, give notice once a day of a post where nothing can be got on with."""
        if world.clock.minute != 0 or not world.registries.research.subjects:
            return
        jobs = world.registries.jobs
        if not any(
            (job := jobs.get(resident.job_id or "")) is not None and job.research for resident in world.residents.values()
        ):
            # With nobody to study there is nobody to be kept waiting.
            return
        subject = self.in_hand(world)
        if subject is None:
            if any(self.status(world, each) == OPEN for each in self.subjects(world)):
                self._notice(world, IDLE_NOTICE, "En el estudio no hay nada entre manos: falta elegir qué averiguar")
            return
        if subject.item is None or subject.subject_id in world.studies.supplied:
            return
        # What is somebody's own is not there for the taking, and counts for nothing.
        to_be_had = sum(
            item.quantity
            for inventory in [*world.containers.values(), *(each.inventory for each in world.residents.values())]
            for item in inventory.items
            if item.definition_id == subject.item and item.owner_id is None
        )
        if to_be_had < subject.count:
            item = world.registries.items.resolve(subject.item)
            self._notice(world, ITEM_NOTICE, f"El estudio espera {item.article} {item.name}: {subject.name}")

    def _notice(self, world: "SimulationWorld", key: str, text: str) -> None:
        if world.notices.get(key) == world.clock.day:
            return
        world.notices[key] = world.clock.day
        world.emit_event(DomainEvent(WAITING_EVENT, WAITING_IMPORTANCE, text))

    def _has_material(self, world: "SimulationWorld", subject: SubjectDefinition, station: str) -> bool:
        """Whether a subject has had the item it studies. Once every unit is at the posts it is used up."""
        state = world.studies
        if subject.item is None or subject.subject_id in state.supplied:
            return True
        desks = [
            world.containers[object_id]
            for object_id, placed in world.interactables.items()
            if placed.kind == station and object_id in world.containers
        ]
        stacks = [stack for desk in desks if (stack := desk.stack_of(subject.item, None)) is not None]
        if sum(stack.quantity for stack in stacks) < subject.count:
            return False
        wanted = subject.count
        for desk in desks:
            stack = desk.stack_of(subject.item, None)
            if stack is not None and wanted > 0:
                wanted -= desk.take_units(stack.instance_id, wanted)
        state.supplied.append(subject.subject_id)
        return True

    def _finish(self, world: "SimulationWorld", subject: SubjectDefinition, by: Resident) -> None:
        state = world.studies
        state.known.append(subject.subject_id)
        state.progress.pop(subject.subject_id, None)
        if subject.subject_id in state.supplied:
            state.supplied.remove(subject.subject_id)
        state.subject_id = None
        by.adjust_mood(4.0)
        room = world.room_at(by.tile)
        world.emit_event(
            DomainEvent(
                FINISHED_EVENT,
                FINISHED_IMPORTANCE,
                f"{by.name} ha averiguado algo: {subject.name}",
                [by.resident_id],
                location_id=room.room_id if room is not None else None,
                data={"subject": subject.subject_id},
            ),
            at=by.tile,
        )
