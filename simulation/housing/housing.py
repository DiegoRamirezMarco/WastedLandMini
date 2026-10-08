"""Whose a building is, and what follows from it (S41).

The player says who a building belongs to. One that belongs to nobody is the settlement's, and
anybody goes into it. One that is somebody's is theirs: they sleep there, whoever they would
have in may come in, and anybody else who does is trespassing. Whoever has no house sleeps in
the open.

It is who may go in for a thing that a house changes, not whose the thing is: what is the
settlement's stays the settlement's wherever it is kept, since in a settlement of one shack
that shack is the store as well.

None of it applies while a new settlement is still in its opening: then nothing is anybody's.
"""

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from simulation.events.event import DomainEvent
from simulation.residents.resident import Resident
from world.interactable import Interactable, UseDefinition
from world.room import Room

if TYPE_CHECKING:
    from simulation.world import SimulationWorld

TRESPASS_EVENT = "trespass"
HOUSED_EVENT = "house_given"
NAMED_EVENT = "building_named"
LOCKED_EVENT = "house_locked"
QUALITIES = ("comfort", "warmth", "light", "beauty")


@dataclass(frozen=True)
class HousingSettings:
    """How houses work, as data (`data/housing.json`)."""

    # How well somebody who lives in a house has to think of another to have them in.
    welcome_affection: float = 35.0
    # How pressing a need has to be for somebody to go into a house that is not theirs for it.
    desperate: dict[str, float] = field(default_factory=lambda: {"hunger": 85.0, "thirst": 85.0})
    trespass_importance: int = 35
    housed_importance: int = 30
    # What each kind of object adds to each quality of the building it stands in, from 0 to 100 in all.
    furnishing: dict[str, dict[str, float]] = field(default_factory=dict)
    # How much better somebody rests in a bed of their own for each point of comfort, and how
    # much a house good to look at lifts the mood of whoever lives in it each day, at the most.
    rest_per_comfort: float = 0.002
    mood_per_day: float = 4.0
    # The uses a building can be said to be for.
    uses: dict[str, str] = field(default_factory=dict)


def housing_settings_from_data(data: dict[str, Any]) -> HousingSettings:
    defaults = HousingSettings()
    furnishing = {
        str(kind): {str(quality): float(amount) for quality, amount in values.items()}
        for kind, values in data.get("furnishing", {}).items()
    }
    for kind, values in furnishing.items():
        if any(quality not in QUALITIES for quality in values):
            raise ValueError(f"Furnishing {kind} adds to a quality there is not: one of {QUALITIES}")
    settings = HousingSettings(
        welcome_affection=float(data.get("welcome_affection", defaults.welcome_affection)),
        desperate={str(need): float(level) for need, level in data.get("desperate", defaults.desperate).items()},
        trespass_importance=int(data.get("trespass_importance", defaults.trespass_importance)),
        housed_importance=int(data.get("housed_importance", defaults.housed_importance)),
        furnishing=furnishing,
        rest_per_comfort=float(data.get("rest_per_comfort", defaults.rest_per_comfort)),
        mood_per_day=float(data.get("mood_per_day", defaults.mood_per_day)),
        uses={str(use_id): str(name) for use_id, name in data.get("uses", {}).items()},
    )
    if settings.rest_per_comfort < 0 or settings.mood_per_day < 0:
        raise ValueError("A house good to live in must not make anybody rest or feel the worse")
    return settings


@dataclass
class Ornament:
    """Something put in a building only to be looked at: on its floor or on its back wall (S42).

    Where it is goes by the building, not by the map: in cells of its inside from its back left
    corner, across and towards the front for what is on the floor, and across for what hangs.
    """

    ornament_id: str
    kind: str
    # `floor` or `wall`.
    on: str
    x: int
    y: int


@dataclass
class HousingState:
    """Whose each building is. Everything here is saved."""

    # The residents each building belongs to, by room ID. One that is missing is the settlement's.
    owners: dict[str, list[str]] = field(default_factory=dict)
    # The name the player has given a building, and what they have said it is for, by room ID.
    names: dict[str, str] = field(default_factory=dict)
    uses: dict[str, str] = field(default_factory=dict)
    # Whether houses have been given out for the first time: at the end of the opening of a new
    # settlement, or from the start in one that comes ready made.
    began: bool = False
    # The buildings whose door is locked, by room ID: only whoever lives in one goes into it.
    locked: list[str] = field(default_factory=list)
    # The day each resident who lives somewhere last had their mood lifted or lowered by it.
    lifted_on: int = 0
    # What has been put in each building to be looked at, and what its floor and walls are, by room ID.
    ornaments: dict[str, list[Ornament]] = field(default_factory=dict)
    floors: dict[str, str] = field(default_factory=dict)
    walls: dict[str, str] = field(default_factory=dict)
    ornament_count: int = 0


@dataclass(frozen=True)
class HousingResult:
    ok: bool
    message: str


class HousingSystem:
    def settings(self, world: "SimulationWorld") -> HousingSettings:
        return world.registries.housing

    def applies(self, world: "SimulationWorld") -> bool:
        """Whether anything is anybody's yet: not while a new settlement is in its opening."""
        return not world.tutorial.active

    # ----- whose it is -----

    def owners(self, world: "SimulationWorld", room_id: str) -> list[str]:
        """Who a building belongs to, of those who still live in the settlement. Nobody for the settlement's own."""
        return [owner for owner in world.homes.owners.get(room_id, []) if owner in world.residents]

    def homes_of(self, world: "SimulationWorld", resident_id: str) -> list[str]:
        """The buildings that are a resident's, by room ID."""
        return [room_id for room_id in world.homes.owners if room_id in world.rooms and resident_id in self.owners(world, room_id)]

    def room_of(self, world: "SimulationWorld", placed: Interactable) -> Room | None:
        """The building an object stands in. None for one that stands in the open."""
        room = world.room_at((placed.x, placed.y))
        return room if room is not None and room.roofed else None

    def lives_in(self, world: "SimulationWorld", resident: Resident, room: Room) -> bool:
        """Whether a building is home to somebody: it is theirs, or their partner's, or their mother's or father's."""
        owners = self.owners(world, room.room_id)
        if resident.resident_id in owners:
            return True
        kin = world.family.kin
        parents = kin.parents_of(world, resident.resident_id)
        with_them = (resident.couple_with, kin.spouse_of(world, resident.resident_id))
        return any(owner in with_them or owner in parents for owner in owners)

    def welcome(self, world: "SimulationWorld", resident: Resident, room: Room) -> bool:
        """Whether somebody may go into a building: it is nobody's, or theirs, or whoever lives
        there thinks well enough of them. With its door locked, only whoever lives there."""
        owners = self.owners(world, room.room_id)
        if not owners or not self.applies(world) or self.lives_in(world, resident, room):
            return True
        if self.locked(world, room):
            return False
        wanted = self.settings(world).welcome_affection
        return any(
            (feelings := world.relationships.get((owner, resident.resident_id))) is not None
            and feelings.affection >= wanted
            for owner in owners
        )

    def locked(self, world: "SimulationWorld", room: Room) -> bool:
        """Whether the door of a building is locked: one that is somebody's, and that the player has said is."""
        return room.room_id in world.homes.locked and bool(self.owners(world, room.room_id))

    # ----- what somebody may use -----

    @staticmethod
    def _is_bed(use: UseDefinition) -> bool:
        return use.unaware and use.per_minute.get("tiredness", 0.0) < 0

    def _at_work(self, world: "SimulationWorld", resident: Resident, placed: Interactable) -> bool:
        job = world.registries.jobs.get(resident.job_id or "")
        return job is not None and job.works_at(placed.kind)

    def may_use(self, world: "SimulationWorld", resident: Resident, placed: Interactable, use: UseDefinition) -> bool:
        """Whether a thing is somebody's to use, by whose building it stands in.

        A bed under a roof is for whoever lives in that building, and so nobody's in a building
        that is the settlement's: whoever has no house sleeps in the open. Anything else in a
        house is for whoever is welcome in it. Whoever works at a thing may always get to it.
        """
        room = self.room_of(world, placed)
        if room is None or not self.applies(world) or self._at_work(world, resident, placed):
            return True
        if self._is_bed(use):
            return bool(self.owners(world, room.room_id)) and self.lives_in(world, resident, room)
        return self.welcome(world, resident, room)

    def pressed(self, world: "SimulationWorld", resident: Resident, placed: Interactable, use: UseDefinition) -> bool:
        """Whether somebody who may not use a thing would go in for it all the same: a need of
        theirs that it sees to has got that bad, it is no bed, and the door is not locked."""
        room = self.room_of(world, placed)
        if room is None or self._is_bed(use) or self.locked(world, room):
            return False
        return any(
            use.per_minute.get(need, 0.0) < 0 or use.consumes is not None and need == "hunger"
            for need, level in self.settings(world).desperate.items()
            if getattr(resident.needs, need, 0.0) >= level
        )

    def used(self, world: "SimulationWorld", resident: Resident, placed: Interactable) -> None:
        """Somebody has started to use a thing: if it is in a house they had no business in, they
        have gone in unasked, which whoever sees it knows and whoever lives there holds against them."""
        room = self.room_of(world, placed)
        if room is None or not self.applies(world) or self._at_work(world, resident, placed):
            return
        owners = self.owners(world, room.room_id)
        if not owners or self.welcome(world, resident, room):
            return
        world.emit_event(
            DomainEvent(
                TRESPASS_EVENT,
                self.settings(world).trespass_importance,
                f"{resident.name} se mete en {room.name} sin que nadie le haya dicho que pase",
                [resident.resident_id, *owners],
                data={"room": room.room_id, "object": placed.object_id},
            ),
            at=resident.tile,
            fact_text=f"{resident.name} se metió en {room.name} sin permiso",
        )

    # ----- the player's say -----

    def give(self, world: "SimulationWorld", room_id: str, owners: list[str]) -> HousingResult:
        """Say who a building belongs to. Nobody makes it the settlement's again."""
        room = world.rooms.get(room_id)
        if room is None or not room.roofed:
            return HousingResult(False, "No hay tal edificio")
        chosen = [owner for owner in dict.fromkeys(owners) if owner in world.residents]
        if len(chosen) != len(set(owners)):
            return HousingResult(False, "No vive aquí alguien de quien se dice")
        before = self.owners(world, room_id)
        if chosen:
            world.homes.owners[room_id] = chosen
        else:
            world.homes.owners.pop(room_id, None)
            # What is everybody's has no door to lock.
            if room_id in world.homes.locked:
                world.homes.locked.remove(room_id)
        world.homes.began = True
        if set(chosen) == set(before):
            return HousingResult(True, f"{room.name.capitalize()} queda como estaba")
        names = ", ".join(world.residents[owner].name for owner in chosen)
        text = f"{room.name.capitalize()} es de {names}" if chosen else f"{room.name.capitalize()} vuelve a ser de todos"
        world.emit_event(
            DomainEvent(
                HOUSED_EVENT,
                self.settings(world).housed_importance,
                text,
                [*chosen, *(owner for owner in before if owner not in chosen)],
                data={"room": room_id, "owners": list(chosen), "before": list(before)},
            )
        )
        return HousingResult(True, text)

    def lock(self, world: "SimulationWorld", room_id: str, locked: bool) -> HousingResult:
        """Lock the door of a building that is somebody's, or leave it open again."""
        room = world.rooms.get(room_id)
        if room is None or not room.roofed:
            return HousingResult(False, "No hay tal edificio")
        if locked and not self.owners(world, room_id):
            return HousingResult(False, "Lo que es de todos no se cierra con llave")
        was = room_id in world.homes.locked
        if locked and not was:
            world.homes.locked.append(room_id)
        elif not locked and was:
            world.homes.locked.remove(room_id)
        text = f"{room.name.capitalize()} queda cerrada con llave" if locked else f"{room.name.capitalize()} queda abierta"
        if locked != was:
            world.emit_event(
                DomainEvent(LOCKED_EVENT, 10, text, self.owners(world, room_id), data={"room": room_id, "locked": locked})
            )
        return HousingResult(True, text)

    def name(self, world: "SimulationWorld", room_id: str, name: str | None = None, use: str | None = None) -> HousingResult:
        """Give a building a name of its own, say what it is for, or both."""
        room = world.rooms.get(room_id)
        if room is None:
            return HousingResult(False, "No hay tal edificio")
        if use is not None:
            if use and use not in self.settings(world).uses:
                return HousingResult(False, "No hay tal uso para un edificio")
            if use:
                world.homes.uses[room_id] = use
            else:
                world.homes.uses.pop(room_id, None)
        if name is not None:
            name = " ".join(name.split())
            if not name:
                return HousingResult(False, "Un edificio ha de llamarse de alguna manera")
            room.name = name
            world.homes.names[room_id] = name
        world.emit_event(DomainEvent(NAMED_EVENT, 10, f"El edificio se llama ahora {room.name}", data={"room": room_id}))
        return HousingResult(True, f"Se llama {room.name}")

    def use_of(self, world: "SimulationWorld", room_id: str) -> str:
        """What a building has been said to be for, in words. Nothing if nobody has said."""
        return self.settings(world).uses.get(world.homes.uses.get(room_id, ""), "")

    # ----- what happens without anybody saying -----

    def settle(self, world: "SimulationWorld") -> None:
        """Give everybody who has no house one of the buildings with beds to spare, in the order
        they are in: what a settlement that was already running had in practice, and what whoever
        founded one has made by the time its opening is over. The player changes it from there."""
        world.homes.began = True
        housed = {owner for room_id in world.homes.owners for owner in self.owners(world, room_id)}
        waiting = [resident_id for resident_id in world.residents if resident_id not in housed]
        for room in world.rooms.values():
            if not room.roofed or not waiting:
                continue
            beds = sum(
                1
                for placed in world.interactables.values()
                if room.contains((placed.x, placed.y))
                and (use := world.definition_of(placed).use) is not None
                and self._is_bed(use)
            )
            room_for = beds - len(self.owners(world, room.room_id))
            if room_for <= 0:
                continue
            taken, waiting = waiting[:room_for], waiting[room_for:]
            world.homes.owners[room.room_id] = [*self.owners(world, room.room_id), *taken]

    def tick(self, world: "SimulationWorld") -> None:
        """One minute: houses are given out for the first time when a new settlement's opening is
        over, and once a day a house lifts the mood of whoever lives in it, or does not."""
        if not world.homes.began and self.applies(world):
            self.settle(world)
        if world.clock.hour == 0 and world.clock.minute == 0 and world.homes.lifted_on != world.clock.day:
            world.homes.lifted_on = world.clock.day
            most = self.settings(world).mood_per_day
            for room_id in list(world.homes.owners):
                room = world.rooms.get(room_id)
                if room is None:
                    continue
                beauty = self.qualities(world, room)["beauty"]
                for owner in self.owners(world, room_id):
                    # A house with nothing in it to look at neither lifts nor lowers.
                    world.residents[owner].adjust_mood(most * beauty / 100.0)

    # ----- what a building is like -----

    def qualities(self, world: "SimulationWorld", room: Room) -> dict[str, float]:
        """How comfortable, warm, light and good to look at a building is, each from 0 to 100, from what stands in it."""
        furnishing = self.settings(world).furnishing
        totals = {quality: 0.0 for quality in QUALITIES}
        counted: dict[tuple[str, str], int] = {}
        for placed in world.interactables.values():
            if not room.contains((placed.x, placed.y)):
                continue
            for quality, amount in furnishing.get(placed.kind, {}).items():
                # A second of the same thing adds half of what the first did, a third a third.
                times = counted[(placed.kind, quality)] = counted.get((placed.kind, quality), 0) + 1
                totals[quality] += amount / times
        for ornament in world.homes.ornaments.get(room.room_id, []):
            for quality, amount in furnishing.get(ornament.kind, {}).items():
                times = counted[(ornament.kind, quality)] = counted.get((ornament.kind, quality), 0) + 1
                totals[quality] += amount / times
        # What its floor and its walls are made of, where the player has said.
        for surface in (world.homes.floors.get(room.room_id), world.homes.walls.get(room.room_id)):
            for quality, amount in furnishing.get(surface or "", {}).items():
                totals[quality] += amount
        return {quality: max(0.0, min(100.0, value)) for quality, value in totals.items()}

    def rest_factor(self, world: "SimulationWorld", resident: Resident, placed: Interactable) -> float:
        """By how much somebody rests better in a bed in their own house than in any other, for how comfortable it is."""
        room = self.room_of(world, placed)
        if room is None or not self.applies(world) or not self.lives_in(world, resident, room):
            return 1.0
        return 1.0 + self.settings(world).rest_per_comfort * self.qualities(world, room)["comfort"]
