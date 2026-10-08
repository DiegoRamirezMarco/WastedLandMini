"""Children: conceived by chance, carried for weeks, born a bundle that somebody has to see to,
and a resident like any other from the day they are ten.

Until then a child is a head and a blanket: it goes nowhere by itself and does nothing. Whoever
looks after it carries it, feeds it and puts it down when they must, and anywhere but a bed it
is the worse for it. Its parents look after it first. With nobody to, someone else may take it
in, and the player is given a say before it is too late.
"""

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from simulation.ai.crowd import free_tile
from simulation.events.event import DomainEvent
from simulation.family.calendar import DAYS_PER_YEAR
from simulation.family.kin import BOTH, DRAWN_TO, SEXES
from simulation.family.settings import HIGH
from simulation.health.injury import Death
from simulation.knowledge.knowledge_system import witnesses_of
from simulation.memory.memory import Memory
from simulation.residents.founding import MAX_TRAITS, resident_id_for
from simulation.residents.personality import Personality
from simulation.residents.resident import Resident
from world.map import Tile

if TYPE_CHECKING:
    from simulation.family.settings import ChildSettings
    from simulation.world import SimulationWorld

TAKE_IN = "take_in"
# Where a bundle may be: on somebody's back, or put down in one of these.
CARRIED, BED, SURFACE, GROUND = "carried", "bed", "surface", "ground"
PLACES = (CARRIED, BED, SURFACE, GROUND)
BED_ACTION = "sleep"
CONCEIVED_IMPORTANCE = 35
BIRTH_IMPORTANCE = 70
GREW_IMPORTANCE = 50
TAKEN_IN_IMPORTANCE = 65
CHILD_DIED_IMPORTANCE = 90
HANDED_EVENT = "child_handed"
HANDED_IMPORTANCE = 20
SEEN_IMPORTANCE = 30
BIRTH_MEMORY = 85.0
NEGLECT_CAUSE = "el abandono"
# What marks a trait, in its data, as one nobody would wish on a child.
FLAW = "flaw"


@dataclass(frozen=True)
class Handed:
    ok: bool
    message: str


@dataclass
class Bundle:
    """A child under ten: carried, fed and put down by whoever looks after it."""

    child_id: str
    name: str
    sex: str
    gender: str
    drawn_to: str
    # The day it was born, counted as the settlement's days are.
    born: int
    personality: Personality = field(default_factory=Personality)
    traits: list[str] = field(default_factory=list)
    # Where it is: on whose back, or put down how, and on which tile.
    carried_by: str | None = None
    place: str = GROUND
    x: int = 0
    y: int = 0
    # From 0, fed, to 100; and from 100, well, down to 0, dead.
    hunger: float = 0.0
    health: float = 100.0
    # Minutes it has been without anybody seeing to it.
    left: int = 0
    # Who has been asked to take it in and said no, and who is making up their mind about it now.
    refused: list[str] = field(default_factory=list)
    asking: str | None = None
    # Game minute at which somebody was last asked.
    asked_at: int = 0
    # Whose arms the player has put it in, if anybody's: they see to it before its parents do,
    # while they are there and in a state to (S51).
    minded_by: str | None = None

    @property
    def tile(self) -> Tile:
        return (self.x, self.y)


class ChildSystem:
    def settings(self, world: "SimulationWorld") -> "ChildSettings":
        return world.registries.family.children

    def is_child(self, world: "SimulationWorld", resident: Resident) -> bool:
        """Whether a resident is under age: one of ten or more who walks, and is not yet grown."""
        return not world.bonds.is_adult(world, resident)

    def age_of(self, world: "SimulationWorld", bundle: Bundle) -> int:
        """How old a bundle is, in the years its weeks make it: a child's time runs fast."""
        settings = self.settings(world)
        days = max(0, world.clock.day - bundle.born)
        return min(settings.grown_at, days * settings.grown_at // (settings.weeks * 7))

    # ----- conceiving and carrying -----

    def together(self, world: "SimulationWorld", one: Resident, other: Resident) -> bool:
        """Two adults have gone off alone together, or married: a child may come of it.

        It takes one of them to be `m` by sex and the other `f`, and it is whoever is `f` that
        carries it. Whether it does is drawn from the settlement's own randomness. Returns
        whether one was conceived.
        """
        settings = self.settings(world)
        if {one.sex, other.sex} != set(SEXES):
            return False
        carrier, sire = (one, other) if one.sex == "f" else (other, one)
        adults = world.bonds.is_adult(world, one) and world.bonds.is_adult(world, other)
        if not adults or carrier.expecting_with is not None or carrier.age >= settings.fertile_until:
            return False
        if world.rng.random() >= settings.chance:
            return False
        carrier.expecting_with = sire.resident_id
        carrier.due_day = world.clock.day + settings.carried_weeks * 7
        world.emit_event(
            DomainEvent(
                "child_conceived",
                CONCEIVED_IMPORTANCE,
                f"{carrier.name} espera una criatura",
                [carrier.resident_id],
                data={"other": sire.resident_id, "due_day": carrier.due_day},
            )
        )
        return True

    def tick_day(self, world: "SimulationWorld") -> None:
        """At the start of a day: whoever is due gives birth, and whoever has turned ten walks."""
        for resident in list(world.residents.values()):
            if resident.expecting_with is not None and world.clock.day >= resident.due_day and not resident.away:
                self.give_birth(world, resident)
        for bundle in list(world.bundles.values()):
            if self.age_of(world, bundle) >= self.settings(world).grown_at:
                self._grow_up(world, bundle)

    def give_birth(self, world: "SimulationWorld", mother: Resident) -> Bundle:
        """Bring the child a resident carries into the world, as a bundle on their back."""
        settings = self.settings(world)
        father_id, mother.expecting_with, mother.due_day = mother.expecting_with, None, 0
        father = world.residents.get(father_id or "")
        of_kin = father_id is not None and world.family.kin.blood(world, mother.resident_id, father_id)
        sex = SEXES[world.rng.randint(0, 1)]
        taken = {*world.kinship, *(bundle.name for bundle in world.bundles.values())}
        names = [name for name in settings.names.get(sex, ()) if name not in {r.name for r in world.residents.values()}]
        names = [name for name in names if name not in taken] or [f"Criatura {len(world.kinship) + 1}"]
        name = world.rng.choice(names)
        child_id = resident_id_for(world, name)
        while child_id in world.kinship or child_id in world.bundles:
            child_id = f"{child_id}_"
        bundle = Bundle(
            child_id,
            name,
            sex,
            sex,
            DRAWN_TO[world.rng.randint(0, len(DRAWN_TO) - 1)] if settings.drawn_by_chance else BOTH,
            world.clock.day,
            self._mixed(world, mother, father, of_kin),
            self._inherited(world, mother, father, of_kin),
            carried_by=mother.resident_id,
            place=CARRIED,
            x=mother.x,
            y=mother.y,
        )
        world.bundles[child_id] = bundle
        record = world.family.kin.record(world, child_id, name, bundle.gender)
        record.parents = [each for each in (mother.resident_id, father_id) if each]
        for parent in (mother, father):
            if parent is None:
                continue
            world.family.kin.record(world, parent.resident_id, parent.name, parent.gender)
            parent.needs.apply({"stress": -10.0})
            world.memories.remember(
                parent.resident_id,
                Memory(f"Nació {name}.", BIRTH_MEMORY, 0.9, [child_id], ["family"], world.clock.total_minutes),
            )
        room = world.room_at(mother.tile)
        world.emit_event(
            DomainEvent(
                "child_born",
                BIRTH_IMPORTANCE,
                f"{mother.name} da a luz a {name}",
                [mother.resident_id],
                location_id=room.room_id if room is not None else None,
                data={"child_id": child_id, "parents": list(record.parents), "sex": sex, "of_kin": of_kin},
            ),
            at=mother.tile,
            fact_text=f"{mother.name} tuvo a {name}",
        )
        return bundle

    def inbred(self, world: "SimulationWorld", child_id: str) -> bool:
        """Whether somebody was born to two who are kin by blood."""
        record = world.kinship.get(child_id)
        return (
            record is not None
            and len(record.parents) >= 2
            and world.family.kin.blood(world, record.parents[0], record.parents[1])
        )

    def _mixed(
        self, world: "SimulationWorld", mother: Resident, father: Resident | None, of_kin: bool = False
    ) -> Personality:
        """A way of being of a child's own: each side near the middle of its parents', by chance.

        A child of two who are kin by blood takes the worse of the two outright, in every side
        that has a worse end.
        """
        settings = self.settings(world)
        worse = settings.worse if of_kin else {}
        sides = {}
        for side, hers in vars(mother.personality).items():
            his = getattr(father.personality, side) if father is not None else hers
            if side in worse:
                sides[side] = max(hers, his) if worse[side] == HIGH else min(hers, his)
                continue
            middle = (hers + his) / 2.0
            sides[side] = max(0.0, min(100.0, round(middle + (world.rng.random() * 2.0 - 1.0) * settings.mix_spread, 1)))
        return Personality(**sides)

    def _inherited(
        self, world: "SimulationWorld", mother: Resident, father: Resident | None, of_kin: bool = False
    ) -> list[str]:
        """The traits a child takes from its parents: each of theirs by chance, and no more than
        anybody has. A child of two who are kin by blood takes the flaws of both first, for certain."""
        chance = self.settings(world).trait_chance
        theirs = [trait for parent in (mother, father) if parent is not None for trait in parent.traits]
        traits: list[str] = []
        if of_kin:
            for trait in theirs:
                flaw = (world.registries.traits.find(trait) or {}).get(FLAW)
                if flaw and trait not in traits and len(traits) < MAX_TRAITS:
                    traits.append(trait)
        for trait in theirs:
            if trait not in traits and len(traits) < MAX_TRAITS and world.rng.random() < chance:
                traits.append(trait)
        return traits

    def _grow_up(self, world: "SimulationWorld", bundle: Bundle) -> Resident:
        """A child is ten: from now on a resident like any other, kept out of nothing but romance."""
        settings = self.settings(world)
        del world.bundles[bundle.child_id]
        x, y = free_tile(world, bundle.tile)
        child = Resident(
            bundle.child_id,
            bundle.name,
            x=x,
            y=y,
            personality=bundle.personality,
            traits=list(bundle.traits),
            age=settings.grown_at,
            # From ten they grow older as everybody does: their birthday is the day they turned ten.
            born=world.clock.day - settings.grown_at * DAYS_PER_YEAR,
            sex=bundle.sex,
            gender=bundle.gender,
            drawn_to=bundle.drawn_to,
            last_worked=world.clock.total_minutes,
        )
        world.residents[child.resident_id] = child
        world.family.welcome(world, child)
        world.emit_event(
            DomainEvent(
                "child_grew",
                GREW_IMPORTANCE,
                f"{child.name} tiene ya diez años y anda por su cuenta",
                [child.resident_id],
                data={"child_id": child.resident_id},
            ),
            at=child.tile,
        )
        return child

    # ----- seeing to a bundle -----

    def minder(self, world: "SimulationWorld", bundle: Bundle) -> Resident | None:
        """Whoever is seeing to a bundle right now: whoever the player put it in the arms of,
        or else the first of its parents, those it was born to before those who took it in.
        Whoever it is has to be here and in a state to."""
        handed = [bundle.minded_by] if bundle.minded_by is not None else []
        for minder_id in [*handed, *world.family.kin.parents_of(world, bundle.child_id)]:
            minder = world.residents.get(minder_id)
            if minder is not None and self.cannot_mind(world, minder) is None:
                return minder
        return None

    def cannot_mind(self, world: "SimulationWorld", resident: Resident) -> str | None:
        """Why a resident is in no state to see to a bundle right now. None if they are."""
        if resident.away:
            return f"{resident.name} está fuera del asentamiento"
        if not world.health.is_fit_for_work(resident) or world.substances.out_of_it(world, resident):
            return f"{resident.name} no está para cuidar de nadie"
        return None

    def hand(self, world: "SimulationWorld", child_id: str, resident_id: str) -> "Handed":
        """Put a bundle in the arms of a resident, whoever they are to it: they carry it and
        feed it from now on, as a parent would, while they are there and in a state to. It
        makes them nothing to it: with them gone, it is its parents' to see to again."""
        bundle = world.bundles.get(child_id)
        resident = world.residents.get(resident_id)
        if bundle is None or resident is None:
            return Handed(False, "Ya no está")
        error = self.cannot_mind(world, resident)
        if error is not None:
            return Handed(False, error)
        bundle.minded_by = resident_id
        self._keep(world, bundle, resident)
        text = f"{resident.name} coge en brazos a {bundle.name}"
        world.emit_event(
            DomainEvent(HANDED_EVENT, HANDED_IMPORTANCE, text, [resident_id], data={"child_id": child_id}),
            at=resident.tile,
        )
        return Handed(True, text)

    def carried_by(self, world: "SimulationWorld", resident: Resident) -> list[Bundle]:
        """The bundles a resident has on their back."""
        return [bundle for bundle in world.bundles.values() if bundle.carried_by == resident.resident_id]

    def tick(self, world: "SimulationWorld") -> None:
        """One minute of every bundle there is: carried or put down, fed or not, and what comes of it."""
        if not world.bundles:
            return
        settings = self.settings(world)
        for bundle in list(world.bundles.values()):
            minder = self.minder(world, bundle)
            bundle.hunger = min(100.0, bundle.hunger + settings.hunger_per_minute)
            if minder is not None:
                self._keep(world, bundle, minder)
            else:
                self._leave(world, bundle)
            harm = settings.harm.get(bundle.place, 0.0) * (1.0 + bundle.left / settings.left_scale)
            if bundle.hunger >= 100.0:
                harm += settings.hunger_harm
            if harm > 0:
                bundle.health = max(0.0, bundle.health - harm)
            elif bundle.health < 100.0:
                bundle.health = min(100.0, bundle.health + settings.mend_per_minute)
            if bundle.health <= 0.0 and bundle.asking is None:
                self._die(world, bundle)

    def _keep(self, world: "SimulationWorld", bundle: Bundle, minder: Resident) -> None:
        """Have whoever sees to a bundle carry it, lay it beside them when they sleep, and feed it."""
        bundle.left, bundle.refused, bundle.asking = 0, [], None
        bundle.x, bundle.y = minder.x, minder.y
        asleep = not world.is_aware(minder)
        placed = world.interactables.get(minder.activity.target_id or "") if minder.activity is not None else None
        in_bed = asleep and placed is not None and world.definition_of(placed).use is not None
        bundle.carried_by = None if asleep else minder.resident_id
        bundle.place = CARRIED if not asleep else BED if in_bed else GROUND
        settings = self.settings(world)
        if bundle.hunger >= settings.feed_from:
            bundle.hunger = 0.0
            minder.needs.apply(settings.feed_cost)

    def _leave(self, world: "SimulationWorld", bundle: Bundle) -> None:
        """Nobody is seeing to a bundle: it is put down, and if nobody will be, someone is asked to take it in."""
        if bundle.place == CARRIED:
            carrier = world.residents.get(bundle.carried_by or "")
            if carrier is not None:
                bundle.x, bundle.y = carrier.x, carrier.y
            bundle.carried_by = None
            bundle.place = self._put_down(world, bundle)
        bundle.left += 1
        settings = self.settings(world)
        parents = [p for p in world.family.kin.parents_of(world, bundle.child_id) if p in world.residents]
        if parents and bundle.left < settings.neglect_minutes:
            # Whoever looks after it is only away for now.
            return
        self._seek_someone(world, bundle)

    def _put_down(self, world: "SimulationWorld", bundle: Bundle) -> str:
        """Where a bundle is put when nobody can carry it: a bed that is free, or else a table or
        some such under a roof, or else the ground."""
        beds = sum(
            1
            for placed in world.interactables.values()
            if (use := world.definition_of(placed).use) is not None and use.action == BED_ACTION
        )
        if beds > len(world.residents):
            return BED
        return SURFACE if world.under_roof(bundle.tile) else GROUND

    def _seek_someone(self, world: "SimulationWorld", bundle: Bundle) -> None:
        """Put it to whoever is likeliest to take a bundle in, one at a time, with the player given a say."""
        if TAKE_IN not in world.registries.decisions:
            return
        if bundle.asking is not None:
            pending = world.interventions.pending_for(world, bundle.asking)
            if pending is not None and pending.kind == TAKE_IN:
                return
            bundle.asking = None
        now = world.clock.total_minutes
        if bundle.refused and now - bundle.asked_at < self.settings(world).ask_gap_minutes:
            return
        parents = world.family.kin.parents_of(world, bundle.child_id)
        candidates = []
        for resident in world.residents.values():
            if resident.resident_id in bundle.refused or resident.resident_id in parents:
                continue
            if resident.away or not world.bonds.is_adult(world, resident) or not world.is_aware(resident):
                continue
            if world.interventions.pending_for(world, resident.resident_id) is not None:
                continue
            kin = world.family.kin.close(world, resident.resident_id, bundle.child_id) or any(
                world.family.kin.close(world, resident.resident_id, parent) for parent in parents
            )
            fondness = max(
                (
                    feelings.affection
                    for parent in parents
                    if (feelings := world.relationships.get((resident.resident_id, parent))) is not None
                ),
                default=0.0,
            )
            candidates.append((kin, fondness + resident.personality.empathy, resident.resident_id, resident))
        if not candidates:
            return
        kin, fondness, _, chosen = max(candidates, key=lambda each: each[:3])
        inputs = {"kin": 1.0 if kin else 0.0, "affection": max(0.0, min(1.0, (fondness - chosen.personality.empathy + 100.0) / 200.0))}
        if world.interventions.ask(world, chosen, TAKE_IN, bundle.name, inputs) is not None:
            bundle.asking, bundle.asked_at = chosen.resident_id, now

    def decided(self, world: "SimulationWorld", resident: Resident, takes: bool) -> None:
        """Carry out what a resident decided about a bundle they were asked to take in."""
        bundle = next((each for each in world.bundles.values() if each.asking == resident.resident_id), None)
        if bundle is None:
            return
        bundle.asking = None
        if not takes:
            bundle.refused.append(resident.resident_id)
            return
        record = world.family.kin.record(world, bundle.child_id, bundle.name, bundle.gender)
        if resident.resident_id not in record.adoptive:
            record.adoptive.append(resident.resident_id)
        world.memories.remember(
            resident.resident_id,
            Memory(f"Me hice cargo de {bundle.name}.", BIRTH_MEMORY, 0.6, [bundle.child_id], ["family"], world.clock.total_minutes),
        )
        world.emit_event(
            DomainEvent(
                "child_taken_in",
                TAKEN_IN_IMPORTANCE,
                f"{resident.name} se hace cargo de {bundle.name}",
                [resident.resident_id],
                data={"child_id": bundle.child_id},
            ),
            at=resident.tile,
            fact_text=f"{resident.name} se hizo cargo de {bundle.name}",
        )

    def _die(self, world: "SimulationWorld", bundle: Bundle) -> None:
        """A bundle nobody looked after dies. It stays in the tree, and its own do not forget it."""
        del world.bundles[bundle.child_id]
        world.deaths.append(Death(bundle.child_id, bundle.name, world.clock.total_minutes, NEGLECT_CAUSE))
        for parent_id in world.family.kin.parents_of(world, bundle.child_id):
            parent = world.residents.get(parent_id)
            if parent is not None:
                parent.needs.apply({"stress": 40.0})
                parent.adjust_mood(-30.0)
                world.memories.remember(
                    parent_id,
                    Memory(f"{bundle.name} murió.", 100.0, -1.0, [bundle.child_id], ["family", "death"], world.clock.total_minutes),
                )
        world.emit_event(
            DomainEvent(
                "child_died",
                CHILD_DIED_IMPORTANCE,
                f"{bundle.name} muere sin nadie que se ocupe",
                data={"child_id": bundle.child_id},
            ),
            at=bundle.tile,
            fact_text=f"{bundle.name} murió sin nadie que se ocupara",
            subjects=[bundle.child_id],
        )

    # ----- what is made of a child's lot -----

    def seen(self, world: "SimulationWorld", event: DomainEvent) -> None:
        """Have whoever sees a child at work, hurt or under something be the worse for it, far
        more than for the same thing done by or to somebody grown."""
        settings = self.settings(world)
        if event.event_type not in settings.seen_events or not event.participants:
            return
        child = world.residents.get(event.participants[0])
        if child is None or not self.is_child(world, child) or child.away:
            return
        onlookers = event.witnesses or witnesses_of(world, child.tile, exclude=[child.resident_id])
        for witness_id in onlookers:
            witness = world.residents.get(witness_id)
            if witness is not None and not self.is_child(world, witness):
                witness.adjust_mood(-settings.seen_mood)
                witness.needs.apply({"stress": settings.seen_stress})
