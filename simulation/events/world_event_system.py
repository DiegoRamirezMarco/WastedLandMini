"""Things that happen to the settlement from outside: strangers, merchants, weather and vermin.

They are rolled once an hour with a random generator of their own, so that whether one happens
never changes what the residents would otherwise have done.
"""

from typing import TYPE_CHECKING

from simulation.ai.crowd import free_tile, spots_taken
from simulation.economy.ledger import ARRIVED, RAIDED, SPOILED
from simulation.events.event import DomainEvent
from simulation.items.inventory import Inventory
from simulation.knowledge.fact import SOURCE_PARTICIPANT
from simulation.knowledge.knowledge_system import learn
from simulation.events.world_event import (
    LET_FIRST,
    LET_IN,
    LET_SECOND,
    MERCHANT,
    RAID,
    SPOIL,
    STAND_GROUND,
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
# Two who come to the gate together: either of them may be let in without the other.
PAIR_DECISION = "strangers"
GATE_DECISIONS = (STRANGER_DECISION, PAIR_DECISION)
RAID_DECISION = "raid"
RAID_IMPORTANCE = 75
REPELLED_IMPORTANCE = 70
# Harm that standing up to raiders can do, and how much less likely it is for someone armed.
RAID_INJURY = (10, 25)
ARMED_FACTOR = 0.5
RAID_CAUSE = "plantar cara a unos merodeadores"
# From this hour a radio's bulletin counts as the evening one, for those who keep watch by night.
EVENING_HOUR = 20
EVENING_NOTICE = "evening:"
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
        world.merchants.tick(world)
        if world.at_the_gate is not None and not self._being_decided(world):
            # Nobody is left to answer: whoever was waiting gives up and goes.
            world.at_the_gate = None
            world.gate_party = []
        if world.under_raid is not None and not any(d.kind == RAID_DECISION for d in world.decisions.values()):
            # Nobody is left in their way.
            self.answer_raid(world, None, "")
        if world.tutorial.active:
            # A settlement still being led through its opening is left alone by the world outside.
            return
        settings = world.registries.world_events
        now = world.clock.total_minutes
        for upcoming in [each for each in world.upcoming if each.at <= now]:
            world.upcoming.remove(upcoming)
            definition = settings.events.get(upcoming.event_id)
            # What was on its way may come to nothing, if by now it cannot happen.
            if definition is not None and self._can_happen(world, definition):
                self._happen(world, definition, upcoming.fact_id)
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
        if not world.has_power():
            return
        world.notices[f"{BULLETIN_NOTICE}{listener.resident_id}"] = world.clock.day
        if world.clock.hour >= EVENING_HOUR:
            world.notices[f"{EVENING_NOTICE}{listener.resident_id}"] = world.clock.day
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

    def radio_to_check(self, world: "SimulationWorld", resident: Resident, evening: bool = False) -> str | None:
        """A radio set this resident has yet to listen to today, the nearest one. None if they have, or there is none.

        With `evening`, it is the evening's bulletin they have yet to hear, and only once it is on.
        """
        if not world.has_power():
            return None
        if evening and world.clock.hour < EVENING_HOUR:
            return None
        notice = EVENING_NOTICE if evening else BULLETIN_NOTICE
        if world.notices.get(f"{notice}{resident.resident_id}") == world.clock.day:
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
        """Whoever is waiting at the gate to be let in: the first of them, if they are two."""
        return next(
            (n for n in world.registries.world_events.newcomers if n.newcomer_id == world.at_the_gate), None
        )

    def visitors(self, world: "SimulationWorld") -> list[Newcomer]:
        """Everyone waiting at the gate together, the one who knocked first."""
        first = self.visitor(world)
        if first is None:
            return []
        known = {n.newcomer_id: n for n in world.registries.world_events.newcomers}
        others = [known[each] for each in world.gate_party if each in known and each != first.newcomer_id]
        return [first, *others]

    def _come_to_gate(self, world: "SimulationWorld", keeper: Resident, newcomer: Newcomer, alone: bool) -> bool:
        """Have somebody knock, with whoever comes with them unless they are to come alone, and
        put it to `keeper`. Returns whether it could be put to them."""
        companion = None if alone else world.family.companion(world, newcomer.newcomer_id)
        unseen = {each.newcomer_id for each in self._unseen(world)}
        together = companion in unseen and PAIR_DECISION in world.registries.decisions
        world.at_the_gate = newcomer.newcomer_id
        world.gate_party = [newcomer.newcomer_id, companion] if together else [newcomer.newcomer_id]
        kin = any(
            world.family.kin.close(world, each, resident_id)
            for each in world.gate_party
            for resident_id in world.residents
            if each in world.kinship or each in world.registries.family.people
        )
        inputs = {"kin": 1.0 if kin else 0.0, "room": 1.0 if self._free_beds(world) >= len(world.gate_party) else 0.0}
        if world.politics.laws.gate_shut(world, keeper):
            # A law says nobody comes in, and whoever answers keeps it.
            inputs["law"] = 1.0
        kind = PAIR_DECISION if together else STRANGER_DECISION
        if world.interventions.ask(world, keeper, kind, inputs=inputs) is None:
            world.at_the_gate, world.gate_party = None, []
            return False
        return True

    def answer_raid(self, world: "SimulationWorld", keeper: Resident | None, choice: str) -> None:
        """Carry out what whoever was on watch decided about the raiders. With nobody there, they help themselves."""
        definition = world.registries.world_events.events.get(world.under_raid or "")
        world.under_raid = None
        if definition is None:
            return
        if keeper is None or choice != STAND_GROUND:
            self._loot(world, definition)
            return
        room = world.room_at(keeper.tile)
        world.emit_event(
            DomainEvent(
                "raid_repelled",
                REPELLED_IMPORTANCE,
                f"{keeper.name} planta cara a unos merodeadores y los echa",
                [keeper.resident_id],
                location_id=room.room_id if room is not None else None,
            ),
            at=keeper.tile,
            fact_text=f"{keeper.name} echó a unos merodeadores",
        )
        armed = world.health.weapon_of(world, keeper)[0] > 1.0
        weapon = world.health.weapon_item(world, keeper)
        # A thing made to keep them at a distance (S47) makes it safer still.
        reach = world.registries.items.resolve(weapon.definition_id).properties.get("raid", 1.0) if weapon else 1.0
        if world.event_rng.random() < definition.danger * (ARMED_FACTOR if armed else 1.0) * min(1.0, max(0.0, reach)):
            world.health.hurt(world, keeper, world.event_rng.randint(*RAID_INJURY), "cut", RAID_CAUSE)

    def _loot(self, world: "SimulationWorld", definition: WorldEventDefinition) -> None:
        taken = 0
        reached = [inventory for kind in definition.containers for _, inventory in containers_of_kind(world, kind)]
        # What is kept in a store is theirs to take too, where the places they go through
        # are where it is taken from (S53): the food of a pantry, and not the water of a tank
        # they never got to.
        through = world.stores.kept_through(world, definition.containers)
        for inventory in reached:
            for item in list(inventory.items):
                if item.owner_id is None:
                    taken += self._carry_off(world, inventory, item, definition.fraction)
        for _, inventory in world.stores.inventories(world) if through else ():
            for item in list(inventory.items):
                if world.stores.resource_of(world, item) in through:
                    taken += self._carry_off(world, inventory, item, definition.fraction)
        said = f"se llevan {taken} cosas" if taken else "no encuentran nada que llevarse"
        tile = self.arrival_tile(world)
        world.emit_event(
            DomainEvent("raid", RAID_IMPORTANCE, f"{definition.text}: {said}"),
            at=tile,
            fact_text="unos merodeadores entraron de noche",
        )

    def _raid(self, world: "SimulationWorld", definition: WorldEventDefinition) -> None:
        keeper = self._keeper(world, definition)
        world.under_raid = definition.event_id
        if keeper is None or world.interventions.ask(world, keeper, RAID_DECISION) is None:
            self.answer_raid(world, None, "")

    def _keeper(self, world: "SimulationWorld", definition: WorldEventDefinition) -> Resident | None:
        """Whoever does the job an event asks for and is at their post, free to deal with it."""
        return next(
            (
                resident
                for resident in world.residents.values()
                if resident.job_id == definition.asks
                and world.work.on_duty(world, resident)
                and world.interventions.pending_for(world, resident.resident_id) is None
            ),
            None,
        )

    def anyone_home(self, world: "SimulationWorld") -> Resident | None:
        """Whoever has been here longest among those who are in, awake and with nothing to decide."""
        return next(
            (
                resident
                for resident in world.residents.values()
                if not resident.away
                and world.is_aware(resident)
                and world.interventions.pending_for(world, resident.resident_id) is None
            ),
            None,
        )

    def strangers_left(self, world: "SimulationWorld") -> bool:
        """Whether anybody could still come to the gate and be given an answer."""
        return bool(self._unseen(world)) and STRANGER_DECISION in world.registries.decisions

    def gate_is_busy(self, world: "SimulationWorld") -> bool:
        """Whether someone is at the gate, waiting for an answer."""
        return world.at_the_gate is not None or self._being_decided(world)

    def call_to_gate(self, world: "SimulationWorld", keeper: Resident) -> bool:
        """Bring a stranger to the gate for `keeper` to answer, whatever their job is.

        Returns whether one came: nobody does without a bed to spare, or while the gate is busy.
        """
        if self.gate_is_busy(world) or not self.strangers_left(world) or self._free_beds(world) <= 0:
            return False
        if world.interventions.pending_for(world, keeper.resident_id) is not None:
            return False
        return self._come_to_gate(world, keeper, world.event_rng.choice(self._unseen(world)), alone=True)

    def answer_gate(self, world: "SimulationWorld", choice: str, keeper: Resident | None = None) -> None:
        """Carry out what was decided about whoever is at the gate.

        Of two who came together either may be let in without the other, and there has to be a
        bed for each one who is. Whoever is let in while the other is not does not forget it.
        """
        waiting = self.visitors(world)
        world.at_the_gate, world.gate_party = None, []
        if not waiting:
            return
        wanted = {LET_IN: waiting, LET_FIRST: waiting[:1], LET_SECOND: waiting[-1:]}.get(choice, [])
        admitted: list[Resident] = []
        for newcomer in waiting:
            room = self._free_beds(world) > 0
            resident = self._settle_one(world, newcomer, admit=newcomer in wanted and room)
            if resident is not None:
                admitted.append(resident)
        if admitted and keeper is not None and keeper.resident_id in world.residents:
            world.politics.laws.gate_opened(world, keeper)
        for newcomer in waiting:
            if len(admitted) == 1 and newcomer.newcomer_id != admitted[0].resident_id:
                world.family.parted_at_gate(world, admitted[0], newcomer.newcomer_id, newcomer.name, keeper)

    def _settle_one(self, world: "SimulationWorld", newcomer: Newcomer, admit: bool) -> Resident | None:
        """Let one of those at the gate in to stay, or send them on their way for good."""
        world.newcomers_seen.append(newcomer.newcomer_id)
        if not admit:
            world.emit_event(
                DomainEvent("stranger_turned_away", TURNED_AWAY_IMPORTANCE, f"{newcomer.name} se aleja de la puerta")
            )
            return None
        x, y = self.arrival_tile(world)
        resident = Resident(
            newcomer.newcomer_id,
            newcomer.name,
            x=x,
            y=y,
            needs=Needs(**ARRIVAL_NEEDS),
            personality=Personality(**newcomer.personality),
            traits=list(newcomer.traits),
            age=newcomer.age,
            credits=world.registries.economy.starting_credits if world.fund.currency(world) is not None else 0.0,
            # They have the days anybody has to find something to do.
            last_worked=world.clock.total_minutes,
            # They came to stay, and mean to pull their weight.
            seeks_work=True,
        )
        world.residents[resident.resident_id] = resident
        world.family.welcome(world, resident)
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
        return resident

    # ----- whether and how -----

    def _being_decided(self, world: "SimulationWorld") -> bool:
        return any(decision.kind in GATE_DECISIONS for decision in world.decisions.values())

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
        if definition.kind == RAID:
            return world.under_raid is None and RAID_DECISION in world.registries.decisions
        if definition.kind == MERCHANT:
            # One at a time, and only where there is somewhere to leave what is bought from them.
            return world.merchant is None and bool(world.containers)
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

    def arrival_tile(self, world: "SimulationWorld") -> tuple[int, int]:
        layout = world.registries.maps.get(world.map_id)
        tiles = [*(layout.arrivals if layout is not None else []), *(layout.spawns if layout is not None else [])]
        passable = world.passable()
        ways_in = [tile for tile in tiles if passable(tile)]
        if not ways_in:
            return (0, 0)
        # The first way in that nobody stands on. With somebody on every one, as near to the first as there is room.
        taken = spots_taken(world)
        return next((tile for tile in ways_in if tile not in taken), free_tile(world, ways_in[0]))

    def _happen(self, world: "SimulationWorld", definition: WorldEventDefinition, heard: str | None = None) -> None:
        """Carry out an event. `heard` is the fact a radio gave of it beforehand, if one did."""
        if definition.kind == STRANGER:
            self._stranger(world, definition)
        elif definition.kind == STOCK:
            self._stock(world, definition)
        elif definition.kind == MERCHANT:
            world.merchants.arrive(world, definition, heard)
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
        elif definition.kind == RAID:
            self._raid(world, definition)

    def _stranger(self, world: "SimulationWorld", definition: WorldEventDefinition) -> None:
        newcomer = world.event_rng.choice(self._unseen(world))
        keeper = self._keeper(world, definition)
        if keeper is None and not any(resident.job_id == definition.asks for resident in world.residents.values()):
            # Nobody keeps the gate, as in a settlement of two or three: whoever is in goes to see who it is.
            keeper = self.anyone_home(world)
        if keeper is None:
            # They may try again another day: nobody has seen them.
            world.emit_event(
                DomainEvent(
                    "stranger_unanswered", UNANSWERED_IMPORTANCE, f"{newcomer.name} llama a la puerta y nadie abre"
                )
            )
            return
        self._come_to_gate(world, keeper, newcomer, alone=False)

    def _carry_off(self, world: "SimulationWorld", inventory: Inventory, item, fraction: float) -> int:
        """Have raiders take their share of a stack. Returns how many units went."""
        gone = inventory.take_units(item.instance_id, int(item.quantity * fraction))
        world.ledger.record(world, item.definition_id, -gone, RAIDED)
        return gone

    def _stock(self, world: "SimulationWorld", definition: WorldEventDefinition) -> None:
        container = containers_of_kind(world, definition.container or "")[0][1]
        left = self.draw_goods(world, definition)
        for item_id, units in left.items():
            world.stock(container, item_id, units, None)
            world.ledger.record(world, item_id, units, ARRIVED)
        goods = ", ".join(f"{world.registries.items.resolve(item_id).name} ({units})" for item_id, units in left.items())
        if goods:
            world.emit_event(DomainEvent("goods_left", STOCK_IMPORTANCE, f"{definition.text}: {goods}"))

    def draw_goods(self, world: "SimulationWorld", definition: WorldEventDefinition) -> dict[str, int]:
        """The things an event brings, drawn from its own list by weight: how many units of each."""
        items = [(item, weight) for item, weight in definition.items if world.registries.items.find(item) is not None]
        drawn: dict[str, int] = {}
        for _ in range(world.event_rng.randint(*definition.count) if items else 0):
            mark = world.event_rng.random() * sum(weight for _, weight in items)
            for item_id, weight in items:
                mark -= weight
                if mark < 0:
                    break
            drawn[item_id] = drawn.get(item_id, 0) + 1
        return drawn

    def _spoil(self, world: "SimulationWorld", definition: WorldEventDefinition) -> None:
        lost = 0
        for _, inventory in containers_of_kind(world, definition.container or "", stores=True):
            for item in list(inventory.items):
                category = world.registries.items.resolve(item.definition_id).category
                if item.owner_id is not None or category != definition.category:
                    continue
                gone = inventory.take_units(item.instance_id, int(item.quantity * definition.fraction))
                world.ledger.record(world, item.definition_id, -gone, SPOILED)
                lost += gone
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
