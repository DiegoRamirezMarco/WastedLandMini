"""What time and kin do to people: dates of birth, birthdays and growing old; who somebody
is, who they are drawn to and who they are kin to; and where they sleep."""

import zlib

from typing import TYPE_CHECKING

from simulation.ai.utility_ai import ScoredAction, need_urgency
from simulation.events.event import DomainEvent
from simulation.family.calendar import DAYS_PER_YEAR, Date, date_of, day_of_year_for, years_between
from simulation.family.kin import BOTH, DRAWN_TO, GENDERS, SEXES, Kinship
from simulation.memory.memory import Memory
from simulation.residents.activity import Activity
from simulation.residents.resident import Resident
from simulation.social.relationship import Relationship

if TYPE_CHECKING:
    from simulation.world import SimulationWorld

# Lying down on the ground to sleep, for want of a bed.
SLEEP_ROUGH_ACTION = "sleep_rough"
BIRTHDAY_IMPORTANCE = 20
ROUGH_IMPORTANCE = 15
OLD_AGE_CAUSE = "la vejez"
# How much less than a bed the ground is wanted, tiredness for tiredness.
ROUGH_APPEAL = 0.8
PARTED_IMPORTANCE = 60
PARTED_MEMORY = 80.0


class FamilySystem:
    kin = Kinship()

    # ----- who somebody is -----

    def welcome(self, world: "SimulationWorld", resident: Resident) -> None:
        """Have the settlement know who somebody is as they come to live in it.

        Whoever the game has by name is who it says they are, unless they were made otherwise.
        Anybody else with no sex given has one that follows from their ID, always the same.
        Their kin among those the game has by name are put on record, and what is felt for close
        kin starts from being kin.
        """
        person = world.registries.family.people.get(resident.resident_id)
        if resident.sex not in SEXES:
            if person is not None:
                resident.sex, resident.gender, resident.drawn_to = person.sex, person.gender, person.drawn_to
            else:
                resident.sex = SEXES[zlib.crc32(resident.resident_id.encode("utf-8")) % 2]
        if resident.gender not in GENDERS:
            resident.gender = resident.sex
        if resident.drawn_to not in DRAWN_TO:
            resident.drawn_to = BOTH
        self.born(world, resident)
        mine = self.kin.record(world, resident.resident_id, resident.name, resident.gender)
        if person is not None:
            for other_id in person.siblings:
                self._known(world, other_id)
                self.kin.make_siblings(world, resident.resident_id, other_id)
            for parent_id in person.parents:
                self._known(world, parent_id)
                if parent_id not in mine.parents:
                    mine.parents.append(parent_id)
        for other in world.residents.values():
            if other is not resident and self.kin.close(world, resident.resident_id, other.resident_id):
                self.bind(world, resident, other)

    def _known(self, world: "SimulationWorld", person_id: str) -> None:
        """Put somebody on record who may not live here: by the name the game has for them, if any."""
        living = world.residents.get(person_id)
        newcomer = next((n for n in world.registries.world_events.newcomers if n.newcomer_id == person_id), None)
        dead = next((death for death in world.deaths if death.resident_id == person_id), None)
        name = living.name if living else newcomer.name if newcomer else dead.name if dead else ""
        person = world.registries.family.people.get(person_id)
        self.kin.record(world, person_id, name, living.gender if living else person.gender if person else "")

    def set_identity(self, world: "SimulationWorld", resident_id: str, sex: str, gender: str, drawn_to: str) -> bool:
        """Say who a resident is. Returns whether there is such a resident and it made sense."""
        resident = world.residents.get(resident_id)
        if resident is None or sex not in SEXES or gender not in GENDERS or drawn_to not in DRAWN_TO:
            return False
        resident.sex, resident.gender, resident.drawn_to = sex, gender, drawn_to
        self.kin.record(world, resident_id, resident.name, gender)
        return True

    def from_before(self, world: "SimulationWorld", resident: Resident) -> None:
        """Somebody out of a save from before anybody had a sex or a gender: they are who the game
        says they are, or who their ID makes them, and drawn to both so that nothing that was
        going on stops. Nobody is kin to anybody."""
        person = world.registries.family.people.get(resident.resident_id)
        resident.sex = person.sex if person is not None else SEXES[zlib.crc32(resident.resident_id.encode("utf-8")) % 2]
        resident.gender = person.gender if person is not None else resident.sex
        resident.drawn_to = BOTH
        self.kin.record(world, resident.resident_id, resident.name, resident.gender)

    def drawn(self, resident: Resident, other: Resident) -> bool:
        """Whether one resident is drawn to people of the other's sex. It does not go by gender."""
        return resident.drawn_to == BOTH or resident.drawn_to == other.sex

    def may_court(self, world: "SimulationWorld", resident: Resident, other: Resident) -> bool:
        """Whether there can be anything between one resident and another, as far as the first
        goes: both are adults, the first is drawn to the other, and they are not close kin."""
        return (
            world.bonds.is_adult(world, resident)
            and world.bonds.is_adult(world, other)
            and self.drawn(resident, other)
            and not self.kin.close(world, resident.resident_id, other.resident_id)
        )

    def desire(self, world: "SimulationWorld", resident: Resident) -> float:
        """How much a resident's libido counts for right now, from 0 to 100: it is theirs and
        does not change, and nerves, low spirits, tiredness and a hurt body all take from it.
        It counts for nothing in anyone who is not an adult."""
        if not world.bonds.is_adult(world, resident):
            return 0.0
        needs = resident.needs
        spirits = min(1.0, 0.5 + resident.mood / 100.0)
        moment = (1.0 - needs.stress / 150.0) * (1.0 - needs.tiredness / 200.0) * spirits * resident.health / 100.0
        return max(0.0, min(100.0, resident.personality.libido * moment))

    def casual(self, world: "SimulationWorld", resident: Resident, feelings: Relationship) -> bool:
        """Whether a resident would go off alone with someone they are no couple with: they get
        on very well with them, and want it enough there and then."""
        settings = world.registries.family
        return feelings.affection >= settings.casual_affection and self.desire(world, resident) >= settings.casual_desire

    def bind(self, world: "SimulationWorld", resident: Resident, other: Resident) -> None:
        """Have what two close kin feel for each other start from being kin, each way by itself."""
        settings = world.registries.family
        for one, another in ((resident, other), (other, resident)):
            feelings = world.relationship(one.resident_id, another.resident_id)
            feelings.affection = max(feelings.affection, settings.kin_affection)
            feelings.trust = max(feelings.trust, settings.kin_trust)

    def witnessed(self, world: "SimulationWorld", event: DomainEvent) -> None:
        """Have what is seen to happen to one of their own tell on whoever sees it."""
        settings = world.registries.family
        if event.event_type not in settings.kin_events or not event.witnesses or not world.kinship:
            return
        for witness_id in event.witnesses:
            witness = world.residents.get(witness_id)
            if witness is not None and any(self.kin.close(world, witness_id, each) for each in event.participants):
                witness.needs.apply({"stress": event.importance * settings.kin_stress})

    # ----- kin at the gate -----

    def companion(self, world: "SimulationWorld", newcomer_id: str) -> str | None:
        """Whoever comes to the gate with somebody, if they do not come alone."""
        for one, other in world.registries.family.arrive_together:
            if newcomer_id in (one, other):
                return other if newcomer_id == one else one
        return None

    def parted_at_gate(
        self, world: "SimulationWorld", admitted: Resident, left_id: str, left_name: str, keeper: Resident | None
    ) -> None:
        """One of two who came together was let in and the other was not: whoever is in does not forget it."""
        settings = world.registries.family
        self._known(world, left_id)
        word = self.kin.word(world, admitted.resident_id, left_id)
        now = world.clock.total_minutes
        admitted.needs.apply({"stress": settings.parted_stress})
        admitted.adjust_mood(-settings.parted_stress)
        people = [keeper.resident_id] if keeper is not None else []
        world.memories.remember(
            admitted.resident_id,
            Memory(f"Me dejaron pasar y a {left_name}, mi {word}, no.", PARTED_MEMORY, -0.9, people, ["family", "gate"], now),
        )
        if keeper is not None:
            feelings = world.relationship(admitted.resident_id, keeper.resident_id)
            for feeling, delta in settings.parted_feelings.items():
                feelings.adjust(feeling, delta)
            world.memories.remember(
                keeper.resident_id,
                Memory(
                    f"Dejé pasar a {admitted.name} y a {left_name} no.", PARTED_MEMORY / 2, -0.3,
                    [admitted.resident_id], ["gate"], now,
                ),
            )
        who = keeper.name if keeper is not None else "Nadie"
        world.emit_event(
            DomainEvent(
                "family_parted",
                PARTED_IMPORTANCE,
                f"{admitted.name} entra y {left_name}, {word} de {admitted.name}, se queda fuera",
                [admitted.resident_id, *people],
                data={"left": left_id},
            ),
            at=admitted.tile,
            fact_text=f"{who} dejó fuera a {left_name}, {word} de {admitted.name}",
            subjects=[*people, admitted.resident_id],
        )

    # ----- the date -----

    def today(self, world: "SimulationWorld") -> Date:
        """The date the settlement is on."""
        return date_of(world.clock.day, world.registries.family.start_year)

    def birth_date(self, world: "SimulationWorld", resident: Resident) -> Date:
        """The date somebody was born on."""
        return date_of(self.born(world, resident), world.registries.family.start_year)

    def born(self, world: "SimulationWorld", resident: Resident) -> int:
        """The day somebody was born, counted as the settlement's days are. Whoever came with
        nothing but an age is given the day that makes them that age."""
        if resident.born is None:
            # Their last birthday was at most a year ago: how long ago goes by who they are.
            since = (world.clock.day - 1 - day_of_year_for(resident.resident_id)) % DAYS_PER_YEAR
            resident.born = world.clock.day - resident.age * DAYS_PER_YEAR - since
        return resident.born

    # ----- a day going by -----

    def tick(self, world: "SimulationWorld") -> None:
        """At the start of each day, have everybody be the age they are, and the old run their chance."""
        if world.clock.hour != 0 or world.clock.minute != 0:
            return
        world.children.tick_day(world)
        settings = world.registries.family
        for resident in list(world.residents.values()):
            age = years_between(self.born(world, resident), world.clock.day)
            if age > resident.age:
                resident.age = age
                world.emit_event(
                    DomainEvent(
                        "birthday",
                        BIRTHDAY_IMPORTANCE,
                        f"{resident.name} cumple {age} años",
                        [resident.resident_id],
                        data={"age": age},
                    ),
                    at=resident.tile if not resident.away else None,
                )
            if resident.age >= settings.old_age and world.rng.random() < self.old_age_chance(world, resident.age):
                world.health.die(world, resident, OLD_AGE_CAUSE)

    def old_age_chance(self, world: "SimulationWorld", age: int) -> float:
        """The chance that somebody of an age dies of it on any one day. None before it begins."""
        settings = world.registries.family
        if age < settings.old_age:
            return 0.0
        yearly = settings.old_age_chance * 2.0 ** ((age - settings.old_age) / settings.old_age_doubles)
        return min(1.0, yearly) / DAYS_PER_YEAR

    # ----- sleeping on the ground -----

    def rough_candidate(self, world: "SimulationWorld", resident: Resident, bed_to_be_had: bool) -> ScoredAction | None:
        """Lying down where they are, for somebody tired enough with no bed to go to."""
        settings = world.registries.family
        if bed_to_be_had or resident.needs.tiredness < settings.rough_from:
            return None
        return ScoredAction(SLEEP_ROUGH_ACTION, need_urgency(resident, "tiredness") * ROUGH_APPEAL)

    def plan_rough(self, world: "SimulationWorld", resident: Resident) -> Activity:
        return Activity(SLEEP_ROUGH_ACTION, None, [], world.registries.family.rough_minutes)

    def rough_tick(self, world: "SimulationWorld", resident: Resident, activity: Activity) -> None:
        """One minute asleep on the ground: some rest, and the worse for it."""
        if not activity.using:
            activity.using = True
            resident.current_action = SLEEP_ROUGH_ACTION
            room = world.room_at(resident.tile)
            world.emit_event(
                DomainEvent(
                    "slept_rough",
                    ROUGH_IMPORTANCE,
                    f"{resident.name} se acurruca en el suelo: no hay cama para dormir",
                    [resident.resident_id],
                    location_id=room.room_id if room is not None else None,
                )
            )
        resident.needs.apply(world.registries.family.rough_per_minute)
        activity.minutes_left -= 1
        rested = resident.needs.tiredness <= 0.0
        if rested or activity.minutes_left <= 0 or world.activities.urgent_needs(world, resident, ignoring=("tiredness",)):
            resident.activity = None
            resident.current_action = "idle"
