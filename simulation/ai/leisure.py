"""Leisure: what a resident does for no reason but to pass the time, alone and with nothing.

A stroll, a sit, a doze, a tune. Each takes something off their nerves a minute at a time, more
or less of it by how much they like that sort of thing, which is a taste of theirs like any
other and shows the same way. What is done with somebody else is an exchange between the two
(`data/social.json`) and is not here, beyond what both have in common: the taste it goes by.
"""

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from simulation.events.event import DomainEvent
from simulation.residents.activity import Activity
from simulation.residents.needs import NEED_NAMES
from simulation.residents.resident import Resident
from simulation.tastes.settings import REACTIONS
from world.interactable import Interactable
from world.pathfinding import manhattan

if TYPE_CHECKING:
    from simulation.world import SimulationWorld

LEISURE_EVENT = "leisure_started"
LEISURE_IMPORTANCE = 6
DECLINED_EVENT = "leisure_declined"
DECLINED_IMPORTANCE = 12


@dataclass(frozen=True)
class Pastime:
    """One way of passing the time alone."""

    pastime_id: str
    # What it is called where it is offered, and what telling somebody to do it says.
    name: str
    label: str
    # What is told of whoever sets about it, with `{name}` where they go.
    text: str
    # What is said of somebody who is at it.
    doing: str
    minutes: tuple[int, int]
    per_minute: dict[str, float] = field(default_factory=dict)
    # The taste it is liked or loathed by, as a tag of `data/tastes.json`. None for one that is
    # the same to everybody.
    taste: str | None = None
    # Whether it is done walking about, sitting down or lying down. Otherwise, on their feet.
    strolls: bool = False
    sits: bool = False
    lies: bool = False
    icon: str | None = None


@dataclass(frozen=True)
class LeisureSettings:
    pastimes: dict[str, Pastime] = field(default_factory=dict)
    # How much of the good a pastime does comes of it, by how whoever is at it takes it.
    relief: dict[str, float] = field(default_factory=dict)
    # What is added to what is told of whoever sets about one, by how they take it.
    taken: dict[str, str] = field(default_factory=dict)
    # How fond of whoever asks somebody has to be, at the least, to go on somewhere with them.
    accept_affection: float = 0.0

    def relief_of(self, reaction: str) -> float:
        return self.relief.get(reaction, 1.0)


def leisure_settings_from_data(data: dict[str, Any]) -> LeisureSettings:
    pastimes = {}
    for pastime_id, values in data.get("alone", {}).items():
        missing = {"name", "label", "text", "doing", "minutes"} - set(values if isinstance(values, dict) else ())
        if missing:
            raise ValueError(f"Pastime {pastime_id} is missing {sorted(missing)}")
        shortest, longest = (int(value) for value in values["minutes"])
        if not 1 <= shortest <= longest:
            raise ValueError(f"Pastime {pastime_id} has an invalid minutes range")
        per_minute = {str(need): float(delta) for need, delta in values.get("per_minute", {}).items()}
        if any(need not in NEED_NAMES for need in per_minute):
            raise ValueError(f"Pastime {pastime_id} changes a need there is not")
        pastime = Pastime(
            pastime_id=str(pastime_id),
            name=str(values["name"]),
            label=str(values["label"]),
            text=str(values["text"]),
            doing=str(values["doing"]),
            minutes=(shortest, longest),
            per_minute=per_minute,
            taste=str(values["taste"]) if values.get("taste") else None,
            strolls=bool(values.get("strolls", False)),
            sits=bool(values.get("sits", False)),
            lies=bool(values.get("lies", False)),
            icon=str(values["icon"]) if values.get("icon") else None,
        )
        if sum((pastime.strolls, pastime.sits, pastime.lies)) > 1:
            raise ValueError(f"Pastime {pastime_id} is done one way: walking, sitting or lying")
        pastimes[pastime.pastime_id] = pastime
    relief = {str(reaction): float(share) for reaction, share in data.get("relief", {}).items()}
    taken = {str(reaction): str(text) for reaction, text in data.get("taken", {}).items()}
    unknown = sorted((relief.keys() | taken.keys()) - set(REACTIONS))
    if unknown:
        raise ValueError(f"Leisure is taken in ways there are not: {unknown}")
    if any(share < 0 for share in relief.values()):
        raise ValueError("A pastime does some good or none, never harm, however it is taken")
    return LeisureSettings(
        pastimes=pastimes,
        relief=relief,
        taken=taken,
        accept_affection=float(data.get("accept_affection", 0.0)),
    )


class LeisureSystem:
    def pastime_of(self, world: "SimulationWorld", activity: Activity | None) -> Pastime | None:
        """The pastime an activity is, if it is one."""
        if activity is None or activity.partner_id is not None or activity.target_id is not None:
            return None
        return world.registries.leisure.pastimes.get(activity.action)

    def plan(self, world: "SimulationWorld", resident: Resident, pastime_id: str) -> Activity | None:
        """Setting about a pastime, where they stand or from there. None if there is no such thing."""
        pastime = world.registries.leisure.pastimes.get(pastime_id)
        if pastime is None:
            return None
        minutes = world.rng.randint(*pastime.minutes)
        path = world.activities.routine.stroll(world, resident) if pastime.strolls else []
        return Activity(pastime.pastime_id, path=path, minutes_left=minutes)

    def tick(self, world: "SimulationWorld", resident: Resident, activity: Activity) -> None:
        """Spend one minute at a pastime: begin it, take what it gives, and leave it when it is
        over or the body asks for something."""
        pastime = self.pastime_of(world, activity)
        if pastime is None:
            resident.activity = None
            resident.current_action = "idle"
            return
        settings = world.registries.leisure
        if not activity.using:
            activity.using = True
            self._begin(world, resident, pastime)
        reaction = world.tastes.takes(world, resident, pastime.taste) if pastime.taste is not None else None
        share = settings.relief_of(reaction) if reaction is not None else 1.0
        # What it takes off them goes by how they like it. What it costs them does not.
        resident.needs.apply({need: delta * share if delta < 0 else delta for need, delta in pastime.per_minute.items()})
        activity.minutes_left -= 1
        if activity.minutes_left <= 0 or world.activities.urgent_needs(world, resident) or self.called_away(world, resident, activity):
            resident.activity = None
            resident.current_action = "idle"
            return
        if pastime.strolls and not activity.path:
            # Got to where they were going, they go on somewhere else.
            activity.path = world.activities.routine.stroll(world, resident)
        resident.current_action = "walking" if activity.path else pastime.pastime_id

    def called_away(self, world: "SimulationWorld", resident: Resident, activity: Activity) -> bool:
        """Whether what somebody took up to pass the time is over because work calls (S62):
        it was time on their hands, and their shift has begun. Not what they were told to do."""
        return not activity.ordered and world.work.candidate(world, resident) is not None

    def _begin(self, world: "SimulationWorld", resident: Resident, pastime: Pastime) -> None:
        settings = world.registries.leisure
        text = pastime.text.replace("{name}", resident.name)
        reaction = None
        if pastime.taste is not None:
            # How they take it tells on them, to the player and to whoever is there to see.
            reaction = world.tastes.pastime(world, resident, pastime.taste)
            text += settings.taken.get(reaction, "")
        room = world.room_at(resident.tile)
        world.emit_event(
            DomainEvent(
                LEISURE_EVENT,
                LEISURE_IMPORTANCE,
                text,
                [resident.resident_id],
                location_id=room.room_id if room is not None else None,
                data={"pastime": pastime.pastime_id, "reaction": reaction},
            ),
            at=resident.tile,
        )

    # ----- going on somewhere together -----

    def place_for(self, world: "SimulationWorld", resident: Resident, action: str) -> Interactable | None:
        """The nearest thing a resident could go and use that way right now, with room at it."""
        routine = world.activities.routine
        best = None
        for placed in world.interactables.values():
            use = world.definition_of(placed).use
            if use is None or use.action != action or world.users_of(placed.object_id) >= use.capacity:
                continue
            if not routine.open_for(world, resident, placed):
                continue
            key = (manhattan(resident.tile, (placed.x, placed.y)), placed.object_id)
            if best is None or key < best:
                best = key
        return world.interactables[best[1]] if best is not None else None

    def go_on(
        self, world: "SimulationWorld", resident: Resident, other: Resident, action: str, asked: bool
    ) -> Activity | None:
        """What a resident does once an exchange that leads somewhere is over: go there, each
        for themselves. Whoever was asked goes only if they care to, and it is said if they do not."""
        settings = world.registries.leisure
        if asked and world.relationship(resident.resident_id, other.resident_id).affection < settings.accept_affection:
            world.emit_event(
                DomainEvent(
                    DECLINED_EVENT,
                    DECLINED_IMPORTANCE,
                    f"{resident.name} no quiere ir con {other.name}",
                    [resident.resident_id, other.resident_id],
                ),
                at=resident.tile,
            )
            return None
        placed = self.place_for(world, resident, action)
        return world.activities.routine.use(world, resident, placed) if placed is not None else None
