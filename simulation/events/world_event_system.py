"""Things that happen to the settlement from outside: strangers, caravans, weather and vermin.

They are rolled once an hour with a random generator of their own, so that whether one happens
never changes what the residents would otherwise have done.
"""

from typing import TYPE_CHECKING

from simulation.events.event import DomainEvent
from simulation.knowledge.fact import SOURCE_PARTICIPANT
from simulation.knowledge.knowledge_system import learn
from simulation.events.world_event import (
    LET_IN,
    SPOIL,
    STOCK,
    STRANGER,
    WEATHER,
    Newcomer,
    Upcoming,
    Weather,
    WorldEventDefinition,
)
from simulation.residents.needs import Needs
from simulation.residents.personality import Personality
from simulation.residents.resident import Resident
from simulation.work.hauling import containers_of_kind

if TYPE_CHECKING:
    from simulation.world import SimulationWorld

STRANGER_DECISION = "stranger"
BED_USE_ACTION = "sleep"
ARRIVAL_IMPORTANCE = 60
TURNED_AWAY_IMPORTANCE = 40
UNANSWERED_IMPORTANCE = 35
STOCK_IMPORTANCE = 30
WEATHER_IMPORTANCE = 45
SPOIL_IMPORTANCE = 45
BULLETIN_IMPORTANCE = 35
CAUGHT_OUT_IMPORTANCE = 45
# Tag of an item that is a radio, and the notice kept of who has listened to one today.
RADIO_TAG = "radio"
BULLETIN_NOTICE = "bulletin:"
# How someone who has been walking the wasteland arrives.
ARRIVAL_NEEDS = {"hunger": 60.0, "tiredness": 55.0, "social": 40.0, "stress": 30.0}


class WorldEventSystem:
    def tick(self, world: "SimulationWorld") -> None:
        """Let the weather pass and act, then once an hour see whether anything new happens."""
        self._weather(world)
        if world.at_the_gate is not None and not self._being_decided(world):
            # Nobody is left to answer: whoever was waiting gives up and goes.
            world.at_the_gate = None
        settings = world.registries.world_events
        now = world.clock.total_minutes
        for upcoming in [each for each in world.upcoming if each.at <= now]:
            world.upcoming.remove(upcoming)
            definition = settings.events.get(upcoming.event_id)
            # What was on its way may come to nothing, if by now it cannot happen.
            if definition is not None and self._can_happen(world, definition):
                self._happen(world, definition)
        if world.clock.minute != 0 or world.clock.day <= settings.quiet_days:
            return
        for event_id, definition in settings.events.items():
            # An event that gives warning is settled that much earlier than the hours it keeps to.
            start, end = (hour - definition.lead_hours for hour in definition.hours)
            if not start <= world.clock.hour < end or not self._can_happen(world, definition):
                continue
            last = world.happened.get(event_id)
            if last is not None and world.clock.day - last < definition.cooldown_days:
                continue
            if any(upcoming.event_id == event_id for upcoming in world.upcoming):
                continue
            if world.event_rng.random() < definition.chance_per_day / (end - start):
                world.happened[event_id] = world.clock.day
                if definition.lead_hours:
                    world.upcoming.append(Upcoming(event_id, now + definition.lead_hours * 60))
                else:
                    self._happen(world, definition)

    # ----- the radio -----

    def hear_radio(self, world: "SimulationWorld", listener: Resident) -> None:
        """Give a resident who is listening to a radio word of whatever is on its way.

        The first to hear a bulletin makes it a fact, which those around hear too and anyone who
        knows it can pass on. Nobody knows what is coming just because it is.
        """
        world.notices[f"{BULLETIN_NOTICE}{listener.resident_id}"] = world.clock.day
        for upcoming in world.upcoming:
            definition = world.registries.world_events.events.get(upcoming.event_id)
            if definition is None or not definition.forecast:
                continue
            fact = world.knowledge.facts.get(upcoming.fact_id or "")
            if fact is not None:
                learn(world, listener, fact, 1.0, SOURCE_PARTICIPANT)
                continue
            hour = upcoming.at // 60 % 24
            word = f"anuncian {definition.forecast} para las {hour}"
            room = world.room_at(listener.tile)
            recorded = world.emit_event(
                DomainEvent(
                    "radio_bulletin",
                    BULLETIN_IMPORTANCE,
                    f"{listener.name} oye en la radio que {word}",
                    [listener.resident_id],
                    location_id=room.room_id if room is not None else None,
                ),
                at=listener.tile,
                fact_text=f"en la radio {word}",
                expires_at=upcoming.at,
            )
            upcoming.fact_id = recorded.fact_id if recorded is not None else None

    def expected(self, world: "SimulationWorld", resident: Resident, kind: str, within: int) -> Upcoming | None:
        """An event of a kind that this resident knows is coming in the next `within` minutes, if any."""
        now = world.clock.total_minutes
        for upcoming in world.upcoming:
            definition = world.registries.world_events.events.get(upcoming.event_id)
            if definition is None or definition.kind != kind or upcoming.at - now > within:
                continue
            if upcoming.fact_id is not None and world.knowledge.knows(resident.resident_id, upcoming.fact_id):
                return upcoming
        return None

    def radio_to_check(self, world: "SimulationWorld", resident: Resident) -> str | None:
        """A radio set this resident has yet to listen to today, the nearest one. None if they have, or there is none."""
        if world.notices.get(f"{BULLETIN_NOTICE}{resident.resident_id}") == world.clock.day:
            return None
        sets = [
            placed
            for placed in world.interactables.values()
            if (use := world.definition_of(placed).use) is not None and use.radio
        ]
        if not sets:
            return None
        return min(sets, key=lambda p: (abs(p.x - resident.x) + abs(p.y - resident.y), p.object_id)).object_id

    def weather_now(self, world: "SimulationWorld") -> WorldEventDefinition | None:
        """The weather the settlement is under, if any that the game still knows."""
        if world.weather is None:
            return None
        return world.registries.world_events.events.get(world.weather.event_id)

    def is_stormy(self, world: "SimulationWorld") -> bool:
        """Whether the weather is bad enough to keep people from work out of doors."""
        return self.weather_now(world) is not None

    def visitor(self, world: "SimulationWorld") -> Newcomer | None:
        """Whoever is waiting at the gate to be let in."""
        return next(
            (n for n in world.registries.world_events.newcomers if n.newcomer_id == world.at_the_gate), None
        )

    def answer_gate(self, world: "SimulationWorld", choice: str) -> None:
        """Carry out what was decided about the stranger at the gate."""
        newcomer = self.visitor(world)
        world.at_the_gate = None
        if newcomer is None:
            return
        world.newcomers_seen.append(newcomer.newcomer_id)
        if choice != LET_IN:
            world.emit_event(
                DomainEvent("stranger_turned_away", TURNED_AWAY_IMPORTANCE, f"{newcomer.name} se aleja de la puerta")
            )
            return
        x, y = self._arrival_tile(world)
        resident = Resident(
            newcomer.newcomer_id,
            newcomer.name,
            x=x,
            y=y,
            needs=Needs(**ARRIVAL_NEEDS),
            personality=Personality(**newcomer.personality),
            traits=list(newcomer.traits),
            age=newcomer.age,
            credits=world.registries.economy.starting_credits,
            # They came to stay, and mean to pull their weight.
            seeks_work=True,
        )
        world.residents[resident.resident_id] = resident
        room = world.room_at(resident.tile)
        world.emit_event(
            DomainEvent(
                "newcomer_joined",
                ARRIVAL_IMPORTANCE,
                f"{newcomer.name} entra en el asentamiento para quedarse",
                [resident.resident_id],
                location_id=room.room_id if room is not None else None,
            ),
            at=resident.tile,
            fact_text=f"{newcomer.name} llegó al asentamiento",
        )

    # ----- whether and how -----

    def _being_decided(self, world: "SimulationWorld") -> bool:
        return any(decision.kind == STRANGER_DECISION for decision in world.decisions.values())

    def _can_happen(self, world: "SimulationWorld", definition: WorldEventDefinition) -> bool:
        if definition.kind == STRANGER:
            # Strangers come while the gate is kept. With nobody whose job it is, they come and find it shut.
            keepers = [resident for resident in world.residents.values() if resident.job_id == definition.asks]
            return (
                world.at_the_gate is None
                and bool(self._unseen(world))
                and self._free_beds(world) > 0
                and STRANGER_DECISION in world.registries.decisions
                and (not keepers or any(world.work.on_duty(world, keeper) for keeper in keepers))
            )
        if definition.kind == WEATHER:
            return world.weather is None
        return bool(containers_of_kind(world, definition.container or ""))

    def _unseen(self, world: "SimulationWorld") -> list[Newcomer]:
        """Newcomers who have never come to the gate, and are not living here under the same name."""
        return [
            newcomer
            for newcomer in world.registries.world_events.newcomers
            if newcomer.newcomer_id not in world.newcomers_seen and newcomer.newcomer_id not in world.residents
        ]

    def _free_beds(self, world: "SimulationWorld") -> int:
        beds = sum(
            1
            for placed in world.interactables.values()
            if (use := world.definition_of(placed).use) is not None and use.action == BED_USE_ACTION
        )
        return beds - len(world.residents)

    def _arrival_tile(self, world: "SimulationWorld") -> tuple[int, int]:
        layout = world.registries.maps.get(world.map_id)
        tiles = [*(layout.arrivals if layout is not None else []), *(layout.spawns if layout is not None else [])]
        passable = world.passable()
        return next((tile for tile in tiles if passable(tile)), (0, 0))

    def _happen(self, world: "SimulationWorld", definition: WorldEventDefinition) -> None:
        if definition.kind == STRANGER:
            self._stranger(world, definition)
        elif definition.kind == STOCK:
            self._stock(world, definition)
        elif definition.kind == WEATHER:
            minutes = world.event_rng.randint(*definition.minutes)
            world.weather = Weather(definition.event_id, world.clock.total_minutes + minutes)
            world.emit_event(DomainEvent("weather_changed", WEATHER_IMPORTANCE, definition.text))
            for resident in world.residents.values():
                if resident.expedition is not None and definition.danger:
                    # Out there with no roof to get under, it is another matter.
                    resident.expedition.danger = min(1.0, resident.expedition.danger + definition.danger)
                    world.emit_event(
                        DomainEvent(
                            "caught_out",
                            CAUGHT_OUT_IMPORTANCE,
                            f"A {resident.name} le pilla fuera: {definition.name}",
                            [resident.resident_id],
                        )
                    )
        elif definition.kind == SPOIL:
            self._spoil(world, definition)

    def _stranger(self, world: "SimulationWorld", definition: WorldEventDefinition) -> None:
        newcomer = world.event_rng.choice(self._unseen(world))
        keeper = next(
            (
                resident
                for resident in world.residents.values()
                if resident.job_id == definition.asks
                and world.work.on_duty(world, resident)
                and world.interventions.pending_for(world, resident.resident_id) is None
            ),
            None,
        )
        if keeper is None:
            # They may try again another day: nobody has seen them.
            world.emit_event(
                DomainEvent(
                    "stranger_unanswered", UNANSWERED_IMPORTANCE, f"{newcomer.name} llama a la puerta y nadie abre"
                )
            )
            return
        world.at_the_gate = newcomer.newcomer_id
        world.interventions.ask(world, keeper, STRANGER_DECISION)

    def _stock(self, world: "SimulationWorld", definition: WorldEventDefinition) -> None:
        container = containers_of_kind(world, definition.container or "")[0][1]
        items = [(item, weight) for item, weight in definition.items if world.registries.items.find(item) is not None]
        left: dict[str, int] = {}
        for _ in range(world.event_rng.randint(*definition.count) if items else 0):
            mark = world.event_rng.random() * sum(weight for _, weight in items)
            for item_id, weight in items:
                mark -= weight
                if mark < 0:
                    break
            left[item_id] = left.get(item_id, 0) + 1
        for item_id, units in left.items():
            world.stock(container, item_id, units, None)
        goods = ", ".join(f"{world.registries.items.resolve(item_id).name} ({units})" for item_id, units in left.items())
        if goods:
            world.emit_event(DomainEvent("caravan_passed", STOCK_IMPORTANCE, f"{definition.text}: {goods}"))

    def _spoil(self, world: "SimulationWorld", definition: WorldEventDefinition) -> None:
        lost = 0
        for _, inventory in containers_of_kind(world, definition.container or ""):
            for item in list(inventory.items):
                category = world.registries.items.resolve(item.definition_id).category
                if item.owner_id is not None or category != definition.category:
                    continue
                lost += inventory.take_units(item.instance_id, int(item.quantity * definition.fraction))
        if lost:
            world.emit_event(
                DomainEvent("food_spoiled", SPOIL_IMPORTANCE, f"{definition.text}: se pierden {lost} raciones")
            )

    def _weather(self, world: "SimulationWorld") -> None:
        if world.weather is None:
            return
        definition = self.weather_now(world)
        if definition is None or world.clock.total_minutes >= world.weather.until:
            world.weather = None
            if definition is not None and definition.end_text:
                world.emit_event(DomainEvent("weather_changed", WEATHER_IMPORTANCE - 15, definition.end_text))
            return
        if definition.stress_per_minute:
            for resident in world.residents.values():
                room = world.room_at(resident.tile)
                if not resident.away and (room is None or not room.roofed):
                    resident.needs.apply({"stress": definition.stress_per_minute})
