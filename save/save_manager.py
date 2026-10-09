import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

from simulation.clock import SimulationClock
from simulation.economy.ledger import LedgerState
from simulation.economy.merchant import Merchant
from simulation.housing.housing import HousingState, Ornament
from simulation.economy.terms import Currency, Debt, TradingState
from simulation.justice.records import CLOSED, STEPS, JusticeState, PunishmentRecord, Ration, Sentence, Trial
from simulation.events.crisis import Crisis
from simulation.events.decision import Decision, DecisionOption
from simulation.events.event import DomainEvent
from simulation.events.world_event import MERCHANT, Upcoming, Weather
from simulation.events.world_event_system import GATE_DECISIONS, RAID_DECISION
from simulation.family.children import PLACES, Bundle
from simulation.family.kin import KinRecord
from simulation.health.injury import Death, Injury
from simulation.items.inventory import Inventory
from simulation.items.item import ItemInstance
from simulation.items.theft import TheftAttempt
from simulation.knowledge.fact import Belief, Fact
from simulation.memory.memory import Memory
from simulation.registries import DEFAULT_MAP_ID, BuiltInRegistries, builtin_registries
from simulation.residents.activity import Activity, Order
from simulation.residents.needs import Needs
from simulation.politics.government import MEASURES
from simulation.politics.political_event import PoliticalEvent
from simulation.politics.profile import PoliticalProfile
from simulation.politics.records import (
    LEADER_SEAT,
    PENDING,
    PLAYER,
    STATUSES,
    VOTES,
    Ballot,
    ElectionRecord,
    Exile,
    LawInForce,
    ProtestRecord,
    PlayerStanding,
    Proposal,
)
from simulation.residents.attributes import OWN, Attributes
from simulation.work.craft import Discovery
from simulation.residents.personality import Personality
from simulation.residents.resident import FACINGS, Resident
from simulation.rng import SimulationRNG
from simulation.social.relationship import Relationship
from simulation.social.talk import ASK_KINDS, Ask, VocabularyState, Word
from simulation.substances.substance import Habit, Intake
from simulation.tastes.settings import REACTIONS
from simulation.tastes.taste import KINDS, Taste, TasteProfile
from simulation.work.expedition import Expedition
from simulation.work.expedition_system import EXPEDITION_ACTION
from simulation.tutorial.tutorial import TutorialState
from simulation.work.research import ResearchState
from simulation.work.salvage import Salvage
from simulation.world import SimulationWorld
from world.build import BuildSite
from world.interactable import Interactable
from world.map import TileMap
from world.room import Room

# Version 1 stored resident positions in pixels and had no map, facing or activities.
# Version 3 added memories and conversation partners; older saves simply have none.
# Version 4 added facts, beliefs, pending decisions and history, all empty by default.
# Version 5 added items. Older saves had endless food, so they get the map's starting stock.
FIRST_ITEM_VERSION = 5
# Version 6 added jobs and a larger settlement. Older saves take the map's current buildings.
FIRST_JOB_VERSION = 6
# Version 7 added injuries and the record of the dead, both empty by default.
# Version 8 added credits, days off, vacancies and a shop. Older saves start with the usual pocket
# money, and gain the objects the map has been given since.
FIRST_ECONOMY_VERSION = 8
# Version 9 only marks a change to the built-in map: the shop got its shelves, and the settlement
# its lamps and its scrap. A save older than the last such change gains the objects the map has
# been given since.
# Version 10 added ages, couples and degrees of friendship. Older saves load with everyone single.
# Version 11 added trips outside and the cart they leave from, and made the scrap piles hold scrap.
# Version 12 added what happens from outside: weather, the gate, and beds for whoever is let in.
# Version 13 added events that are on their way, and the settlement's radio to hear of them.
# Version 14 added raids. A save from before simply has never had one.
# Version 15 added lost limbs, none by default, and the particulars of events, empty by default.
# Version 16 added thirst, mood, water and generator fuel.
# Version 17 stores changes made in urbanism mode: terrain, rooms and construction underlays.
# Version 18 added where a new settlement is in its opening. Older saves are simply past it.
# Version 19 added tastes, what has been found out of them, and who made a present of an item.
# Older saves have none: tastes are made as things are met, as in a settlement just begun.
# Version 20 added tastes in people and how each taste looked the last time it showed. A save from
# before has no tastes in people yet, and what was known of the rest is shown as it stands.
# Version 21 added each resident's manners: how they walk, eat and fight. Whoever has none
# chosen, as in any older save, goes by the ones that are theirs by default.
# Version 22 added how long somebody on a walk has been held up by whoever is in their way. A
# save from before has nobody held up, and may have two people on one tile: they walk apart.
# Version 23 added medicine, kept in the clinic's cabinet, and the dose each resident is under. A
# save from before has nobody under one, finds its cabinet stocked as the map stocks it, and has
# the furniture of the south house moved to where nobody is walled in by it.
# Version 24 added building: the sites that are being worked on. A save from before has none,
# and what stands in it stands as it did.
# Version 25 added what the settlement knows and what it is working out. A save from before
# knows how to make whatever it has standing, and is working nothing out.
FIRST_RESEARCH_VERSION = 25
# Version 26 added the common fund, how the settlement trades, whoever has stopped by to trade,
# and credit as something that can be stolen. A save from before trades with the credits it
# had, and its fund starts with what a currency just taken up would have put in it.
FIRST_FUND_VERSION = 26
# Version 27 added when each resident last worked and how long they have gone unpaid, what is
# owed between residents, what waits at the gate to be carried in, who an item is being kept
# for, and how many swaps each resident has had turned down. In a save from before everybody
# has just worked, nobody owes anything and nothing waits.
FIRST_UPKEEP_VERSION = 27
# Version 28 added what each resident is under and their history with each substance, and made
# the bar hold what it serves. In a save from before nobody is under anything, and the bar starts
# with what the map puts in it.
# Version 29 added dates of birth, sex, gender, who each resident is drawn to, libido and kin.
# In a save from before everyone is the age they were, is who the game says or their ID makes
# them, is drawn to both, and is kin to nobody.
FIRST_FAMILY_VERSION = 29
# Version 30 added charisma and leadership, the roles a resident holds, the government the
# settlement has and what each resident holds about it. In a save from before everyone is in
# the middle for both, nobody holds a role and there is no government yet: one is chosen.
# Version 31 added the laws in force, how many times each resident has eaten out of the commons
# today, proposals waiting and decided, the votes for a seat there have been, what the player
# is to each resident, and whoever has been thrown out. In a save from before there are no
# laws, nothing is waiting, nobody has been thrown out, and the player is in the middle for
# trust with everybody.
# Version 32 added what somebody has been told to take apart, and the one thing a trip outside
# is for when it is for one thing. In a save from before nobody has been told to take anything
# apart, and every trip is for whatever turns up.
# Version 35 added whether a law was put in force with nobody asked, and who is out in the
# square against which (S45). In a save from before every law was voted and nobody is out.
# Version 36 added each resident's attributes (S46). In a save from before everybody has what
# the settlement's seed gives them, the first time it is asked.
# Version 37 added what residents have come to at their jobs, the time each has at each job,
# what each knows how to make and is learning, and what they were last dosed with (S47). In a
# save from before everybody starts their job anew and nothing has been come to.
LAST_MAP_CHANGE_VERSION = 16
# Version 42 marks another change to the built-in map: the settlement that comes ready made
# got its store (S53). A save from before gains it, where nothing stands on its ground, and
# nothing else: whatever the player has since taken down stays down. The building its food is
# taken from, which the map called by the name the store now has, is called as the map calls
# it now if nobody has given it another.
# Version 45 marks one more: it got a well, where water is drawn with no current (S55).
MAP_GAINS: dict[int, tuple[str, ...]] = {42: ("warehouse",), 45: ("well",)}
MAP_RENAMES: dict[int, dict[str, str]] = {42: {"storehouse": "almacén"}}
# Version 46 added current (S55): what stands is switched on or off, and a tank needs some.
FIRST_CURRENT_VERSION = 46
TANK_KIND, WELL_KIND = "water_tank", "well"
# A save older than this gives the containers it never had what the map starts them with.
LAST_STOCK_CHANGE_VERSION = 28
FIRST_MEDICINE_VERSION = 23
# Objects of a built-in map that were moved after saves had been made with them: where each
# stood, and where it stands now. A save from before has them moved if they are still there.
MOVED_ON_THE_MAP: dict[str, dict[str, tuple[tuple[int, int], tuple[int, int]]]] = {
    DEFAULT_MAP_ID: {
        "crate_south": ((8, 24), (7, 27)),
        "bed_6": ((7, 24), (8, 24)),
        "bed_10": ((7, 26), (8, 26)),
    }
}
FIRST_URBANISM_VERSION = 17
FIRST_TILE_VERSION = 2


class SaveManager:
    CURRENT_VERSION = 50

    def save(self, world: SimulationWorld, path: Path) -> None:
        path.write_text(json.dumps(self.to_data(world), ensure_ascii=False, indent=2), encoding="utf-8")

    def load(self, path: Path, registries: BuiltInRegistries | None = None) -> SimulationWorld:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError(f"Expected object save file: {path}")
        return self.from_data(data, registries)

    def to_data(self, world: SimulationWorld) -> dict[str, Any]:
        return {
            "version": self.CURRENT_VERSION,
            "clock": vars(world.clock),
            "rng": world.rng.get_state(),
            "event_rng": world.event_rng.get_state(),
            "happened": dict(world.happened),
            "weather": vars(world.weather) if world.weather is not None else None,
            "upcoming": [vars(upcoming) for upcoming in world.upcoming],
            "at_the_gate": world.at_the_gate,
            "under_raid": world.under_raid,
            "trading": {
                "currency": vars(world.trading.currency) if world.trading.currency is not None else None,
                "in_use": world.trading.in_use,
                "fund": world.trading.fund,
                "currency_count": world.trading.currency_count,
                "asked_on": world.trading.asked_on,
                "refusals": dict(world.trading.refusals),
                "asked_about": world.trading.asked_about,
                "answers": dict(world.trading.answers),
            },
            "debts": [vars(debt) for debt in world.debts],
            "at_gate": dict(world.at_gate),
            "housing": {
                # Only whoever still lives here owns anything, and only what is still standing.
                "owners": {
                    room_id: owners
                    for room_id in world.homes.owners
                    if room_id in world.rooms and (owners := world.housing.owners(world, room_id))
                },
                "names": {room_id: name for room_id, name in world.homes.names.items() if room_id in world.rooms},
                "uses": {room_id: use for room_id, use in world.homes.uses.items() if room_id in world.rooms},
                "began": world.homes.began,
                "locked": [
                    room_id for room_id in world.homes.locked if room_id in world.rooms and world.housing.owners(world, room_id)
                ],
                "lifted_on": world.homes.lifted_on,
                "ornaments": {
                    room_id: [vars(ornament) for ornament in ornaments]
                    for room_id, ornaments in world.homes.ornaments.items()
                    if room_id in world.rooms and ornaments
                },
                "floors": {room_id: floor for room_id, floor in world.homes.floors.items() if room_id in world.rooms},
                "walls": {room_id: wall for room_id, wall in world.homes.walls.items() if room_id in world.rooms},
                "ornament_count": world.homes.ornament_count,
            },
            "merchant": (
                {
                    "event_id": world.merchant.event_id,
                    "leaves_at": world.merchant.leaves_at,
                    "goods": dict(world.merchant.goods),
                    "purse": world.merchant.purse,
                    "fact_id": world.merchant.fact_id,
                    "tile": list(world.merchant.tile) if world.merchant.tile is not None else None,
                    "cart": list(world.merchant.cart) if world.merchant.cart is not None else None,
                }
                if world.merchant is not None
                else None
            ),
            "newcomers_seen": list(world.newcomers_seen),
            "gate_party": list(world.gate_party),
            "kinship": {person_id: vars(kin) for person_id, kin in world.kinship.items()},
            "government": asdict(world.government),
            "political_profiles": {
                resident_id: vars(profile) for resident_id, profile in world.political_profiles.items()
            },
            "player_standing": {
                resident_id: vars(standing) for resident_id, standing in world.player_standing.items()
            },
            "leaving": dict(world.leaving),
            "exiled": [vars(exile) for exile in world.exiled],
            "courts": {
                "trials": [vars(trial) for trial in world.courts.trials.values()],
                "trial_count": world.courts.trial_count,
                "sentences": [vars(sentence) for sentence in world.courts.sentences],
                "history": [vars(record) for record in world.courts.history],
                "ration": vars(world.courts.ration) if world.courts.ration is not None else None,
                "weighing": {resident_id: list(about) for resident_id, about in world.courts.weighing.items()},
                "at_gate": world.courts.at_gate,
            },
            "bundles": [
                {**{key: value for key, value in vars(bundle).items() if key != "personality"}, "personality": vars(bundle.personality)}
                for bundle in world.bundles.values()
            ],
            "map_id": world.map_id,
            "terrain": [list(row) for row in world.tile_map.tiles],
            "rooms": [
                {
                    "id": room.room_id,
                    "name": room.name,
                    "privacy": room.privacy,
                    "x": room.x,
                    "y": room.y,
                    "width": room.width,
                    "height": room.height,
                    "roofed": room.roofed,
                    "blueprint_id": room.blueprint_id,
                }
                for room in world.rooms.values()
            ],
            "urbanism": {
                "next_object": world.urbanism.next_object,
                "next_building": world.urbanism.next_building,
                "underlays": {
                    room_id: [
                        {"x": tile[0], "y": tile[1], "terrain": terrain}
                        for tile, terrain in underlay.items()
                    ]
                    for room_id, underlay in world.urbanism.underlays.items()
                },
            },
            "interactables": [
                {
                    "id": placed.object_id,
                    "kind": placed.kind,
                    "x": placed.x,
                    "y": placed.y,
                    "level": placed.level,
                    "on": placed.on,
                    "switched_at": placed.switched_at,
                    "condition": placed.condition,
                }
                for placed in world.interactables.values()
            ],
            "sites": [
                {
                    "id": site.site_id,
                    "kind": site.kind,
                    "what": site.what,
                    "x": site.x,
                    "y": site.y,
                    "in_charge": site.in_charge,
                    "delivered": dict(site.delivered),
                    "progress": site.progress,
                    "started_at": site.started_at,
                }
                for site in world.sites.values()
            ],
            "site_count": world.site_count,
            "salvage": [vars(job) for job in world.salvage.values()],
            "discoveries": [asdict(discovery) for discovery in world.discoveries.values()],
            "discovery_count": world.discovery_count,
            "ledger": {
                "day": world.accounts.day,
                "opened_at": world.accounts.opened_at,
                "today": {resource: dict(flows) for resource, flows in world.accounts.today.items()},
                "days": {
                    str(day): {resource: dict(flows) for resource, flows in written.items()}
                    for day, written in world.accounts.days.items()
                },
                "held": {str(day): dict(count) for day, count in world.accounts.held.items()},
            },
            "research": {
                "subject": world.studies.subject_id,
                "known": list(world.studies.known),
                "progress": dict(world.studies.progress),
                "supplied": list(world.studies.supplied),
            },
            "residents": [
                {
                    "id": resident.resident_id,
                    "name": resident.name,
                    "x": resident.x,
                    "y": resident.y,
                    "facing": resident.facing,
                    "needs": vars(resident.needs),
                    "personality": vars(resident.personality),
                    "attributes": vars(resident.attributes) if resident.attributes is not None else None,
                    "mood": resident.mood,
                    "current_action": resident.current_action,
                    "activity": _activity_to_data(resident.activity),
                    "doing": _order_to_data(resident.doing),
                    "orders": [_order_to_data(order) for order in resident.orders],
                    "free_will": resident.free_will,
                    "traits": list(resident.traits),
                    "manners": dict(resident.manners),
                    "job_id": resident.job_id,
                    "post_id": resident.post_id,
                    "work_progress": resident.work_progress,
                    "day_off": resident.day_off,
                    "credits": resident.credits,
                    "last_worked": resident.last_worked,
                    "unpaid_on": resident.unpaid_on,
                    "unpaid_days": resident.unpaid_days,
                    "under": [vars(intake) for intake in resident.under],
                    "habits": {item_id: vars(habit) for item_id, habit in resident.habits.items()},
                    "tempted_by": resident.tempted_by,
                    "age": resident.age,
                    "born": resident.born,
                    "sex": resident.sex,
                    "gender": resident.gender,
                    "drawn_to": resident.drawn_to,
                    "expecting_with": resident.expecting_with,
                    "due_day": resident.due_day,
                    "roles": list(resident.roles),
                    "couple_with": resident.couple_with,
                    "expedition": vars(resident.expedition) if resident.expedition is not None else None,
                    "last_expedition_day": resident.last_expedition_day,
                    "seeks_work": resident.seeks_work,
                    "injuries": [vars(injury) for injury in resident.injuries],
                    "dosed_until": resident.dosed_until,
                    "dosed_with": resident.dosed_with,
                    "trade": dict(resident.trade),
                    "pushing_until": resident.pushing_until,
                    "makes": dict(resident.makes),
                    "lessons": dict(resident.lessons),
                    "lost_limbs": list(resident.lost_limbs),
                    "inventory": _inventory_to_data(resident.inventory),
                }
                for resident in world.residents.values()
            ],
            "relationships": [
                {
                    "source_id": relationship.source_id,
                    "target_id": relationship.target_id,
                    "affection": relationship.affection,
                    "trust": relationship.trust,
                    "attraction": relationship.attraction,
                    "fear": relationship.fear,
                    "resentment": relationship.resentment,
                    "last_argued": relationship.last_argued,
                    "bond": relationship.bond,
                    "last_together": relationship.last_together,
                }
                for relationship in world.relationships.values()
            ],
            "memories": {
                resident_id: [vars(memory) for memory in world.memories.of(resident_id)]
                for resident_id in world.memories.resident_ids()
            },
            "containers": {
                object_id: _inventory_to_data(inventory) for object_id, inventory in world.containers.items()
            },
            "item_count": world.item_count,
            "thefts": [vars(attempt) for attempt in world.thefts],
            "theft_cooldowns": dict(world.theft_cooldowns),
            "notices": dict(world.notices),
            "power_burnt": world.power_burnt,
            "dressed": dict(world.dressed),
            "words": _words_to_data(world.words),
            "vacancies": dict(world.vacancies),
            "deaths": [vars(death) for death in world.deaths],
            "decisions": [_decision_to_data(decision) for decision in world.decisions.values()],
            "decision_count": world.decision_count,
            "crisis_cooldowns": dict(world.crisis_cooldowns),
            "history": [vars(event) for event in world.history],
            "facts": [vars(fact) for fact in world.knowledge.facts.values()],
            "beliefs": {
                resident_id: [vars(belief) for belief in world.knowledge.beliefs_of(resident_id)]
                for resident_id in world.knowledge.resident_ids()
            },
            "event_log": list(world.event_log),
            "tastes": {
                resident_id: {
                    kind: {name: {"leaning": taste.leaning, "learned": taste.learned} for name, taste in profile.of(kind).items()}
                    for kind in KINDS
                }
                for resident_id, profile in world.taste_profiles.items()
            },
            "taste_knowledge": {
                observer_id: {subject_id: dict(tastes) for subject_id, tastes in subjects.items()}
                for observer_id, subjects in world.taste_knowledge.seen.items()
            },
            "taste_seen_as": {
                observer_id: {subject_id: dict(tastes) for subject_id, tastes in subjects.items()}
                for observer_id, subjects in world.taste_knowledge.seen_as.items()
            },
            "tutorial": {
                "step": world.tutorial.step_id,
                "since": world.tutorial.since,
                "opened": world.tutorial.opened,
                "acknowledged": world.tutorial.acknowledged,
                "deeds": list(world.tutorial.deeds),
                "done": list(world.tutorial.done),
            },
        }

    def from_data(
        self, data: dict[str, Any], registries: BuiltInRegistries | None = None
    ) -> SimulationWorld:
        version = int(data.get("version", 0))
        if version > self.CURRENT_VERSION:
            raise ValueError(f"Unsupported save version: {version}")

        clock_data = _object_or_empty(data.get("clock"))
        rng_data = _object_or_empty(data.get("rng"))
        world = SimulationWorld(
            clock=SimulationClock(
                day=int(clock_data.get("day", 1)),
                hour=int(clock_data.get("hour", 8)),
                minute=int(clock_data.get("minute", 0)),
                fixed_tick_minutes=int(clock_data.get("fixed_tick_minutes", 1)),
                paused=bool(clock_data.get("paused", False)),
                speed=int(clock_data.get("speed", 1)),
            ),
            rng=SimulationRNG.from_state(rng_data),
            registries=registries or builtin_registries(),
        )
        self._restore_map(world, data, version)
        self._restore_discoveries(world, data)

        residents = data.get("residents", [])
        if not isinstance(residents, list):
            raise ValueError("Save field residents must be a list")
        spawns = world.registries.maps[world.map_id].spawns or [(0, 0)]
        pocket_money = world.registries.economy.starting_credits if version < FIRST_ECONOMY_VERSION else 0.0
        for index, resident_data in enumerate(residents):
            if not isinstance(resident_data, dict):
                raise ValueError("Resident save entry must be an object")
            needs_data = _object_or_empty(resident_data.get("needs"))
            personality_data = _object_or_empty(resident_data.get("personality"))
            resident_id = str(resident_data["id"])
            tile = (int(resident_data.get("x", 0)), int(resident_data.get("y", 0)))
            activity = _activity_from_data(resident_data.get("activity"))
            if version < FIRST_TILE_VERSION or not self._can_stand(world, tile):
                # Off the map, or where the map has since put a wall: back to a spawn point.
                tile = spawns[index % len(spawns)]
                activity = None
            facing = str(resident_data.get("facing", "down"))
            if activity is not None and activity.target_id not in (None, *world.interactables, *world.sites):
                activity = None
            if activity is not None and not all(self._can_stand(world, step) for step in activity.path):
                activity = None
            day_off = resident_data.get("day_off")
            trip = resident_data.get("expedition")
            if not isinstance(trip, dict) or activity is None or activity.action != EXPEDITION_ACTION:
                # Being out there and the trip itself go together: one without the other is dropped.
                trip = None
                activity = None if activity is not None and activity.action == EXPEDITION_ACTION else activity
            resident = Resident(
                resident_id=resident_id,
                name=str(resident_data.get("name", resident_id)),
                x=tile[0],
                y=tile[1],
                needs=Needs(
                    hunger=float(needs_data.get("hunger", 15.0)),
                    thirst=float(needs_data.get("thirst", 12.0)),
                    tiredness=float(needs_data.get("tiredness", 10.0)),
                    social=float(needs_data.get("social", 20.0)),
                    stress=float(needs_data.get("stress", 10.0)),
                ),
                personality=Personality(
                    aggression=float(personality_data.get("aggression", 50.0)),
                    empathy=float(personality_data.get("empathy", 50.0)),
                    impulsiveness=float(personality_data.get("impulsiveness", 50.0)),
                    sociability=float(personality_data.get("sociability", 50.0)),
                    greed=float(personality_data.get("greed", 50.0)),
                    courage=float(personality_data.get("courage", 50.0)),
                    libido=float(personality_data.get("libido", 50.0)),
                    charisma=float(personality_data.get("charisma", 50.0)),
                    leadership=float(personality_data.get("leadership", 50.0)),
                ),
                attributes=_attributes_from_data(world, resident_data.get("attributes")),
                mood=float(resident_data.get("mood", 50.0)),
                current_action=str(resident_data.get("current_action", "idle")),
                facing=facing if facing in FACINGS else "down",
                activity=activity,
                # What they were at for having been told goes with being at it: one without the other is dropped.
                doing=_order_from_data(resident_data.get("doing")) if activity is not None and activity.ordered else None,
                orders=[
                    order
                    for order in map(_order_from_data, _list_or_empty(resident_data.get("orders")))
                    if order is not None
                ],
                # In a save from before, everybody does as they like.
                free_will=bool(resident_data.get("free_will", True)),
                traits=[str(trait) for trait in resident_data.get("traits", [])],
                # A manner that is no longer defined is forgotten: they go by their own by default.
                manners=world.registries.manners.tidy(_object_or_empty(resident_data.get("manners"))),
                job_id=_text_or_none(resident_data.get("job_id")),
                post_id=_text_or_none(resident_data.get("post_id")),
                work_progress=int(resident_data.get("work_progress", 0)),
                day_off=int(day_off) if day_off is not None else None,
                credits=float(resident_data.get("credits", pocket_money)),
                # In a save from before, everybody has just worked.
                last_worked=int(resident_data.get("last_worked", world.clock.total_minutes)),
                unpaid_on=int(resident_data.get("unpaid_on", 0)),
                unpaid_days=max(0, int(resident_data.get("unpaid_days", 0))),
                under=[
                    Intake(
                        item_id=str(intake["item_id"]),
                        until=int(intake.get("until", 0)),
                        after_until=int(intake.get("after_until", 0)),
                        sign=str(intake.get("sign", "")),
                        unaware=bool(intake.get("unaware", False)),
                    )
                    for intake in _list_or_empty(resident_data.get("under"))
                    if isinstance(intake, dict) and "item_id" in intake
                ],
                # A habit is kept whatever it is of: one of something no content brings any longer
                # does nothing, and is there if it comes back.
                habits={
                    str(item_id): Habit(
                        uses=max(0, int(habit.get("uses", 0))),
                        last_taken=int(habit.get("last_taken", 0)),
                        dependent=bool(habit.get("dependent", False)),
                        without=max(0.0, float(habit.get("without", 0.0))),
                        recovered=bool(habit.get("recovered", False)),
                        allowed_until=int(habit.get("allowed_until", 0)),
                        resisting_until=int(habit.get("resisting_until", 0)),
                    )
                    for item_id, habit in _object_or_empty(resident_data.get("habits")).items()
                    if isinstance(habit, dict)
                },
                tempted_by=_text_or_none(resident_data.get("tempted_by")),
                age=int(resident_data.get("age", 30)),
                # In a save from before, the day that makes them the age they were is worked out when it is asked for.
                born=int(resident_data["born"]) if resident_data.get("born") is not None else None,
                sex=str(resident_data.get("sex", "")),
                gender=str(resident_data.get("gender", "")),
                drawn_to=str(resident_data.get("drawn_to", "both")),
                expecting_with=_text_or_none(resident_data.get("expecting_with")),
                due_day=int(resident_data.get("due_day", 0)),
                roles=[str(role) for role in _list_or_empty(resident_data.get("roles"))],
                couple_with=_text_or_none(resident_data.get("couple_with")),
                expedition=Expedition(
                    returns_at=int(trip.get("returns_at", 0)),
                    finds=int(trip.get("finds", 0)),
                    danger=float(trip.get("danger", 0.0)),
                    find_at=int(trip["find_at"]) if trip.get("find_at") is not None else None,
                    fetch=_text_or_none(trip.get("fetch")),
                    risked=bool(trip.get("risked", False)),
                )
                if trip is not None
                else None,
                last_expedition_day=int(resident_data.get("last_expedition_day", 0)),
                seeks_work=bool(resident_data.get("seeks_work", False)),
                injuries=[
                    Injury(str(injury.get("kind", "bruise")), float(injury.get("severity", 0.0)))
                    for injury in resident_data.get("injuries", [])
                    if isinstance(injury, dict)
                ],
                dosed_until=int(resident_data.get("dosed_until", 0)),
                dosed_with=_text_or_none(resident_data.get("dosed_with")),
                pushing_until=max(0, int(resident_data.get("pushing_until", 0))),
                trade={
                    str(job_id): max(0.0, float(minutes))
                    for job_id, minutes in _object_or_empty(resident_data.get("trade")).items()
                },
                # What was come to and is no longer on record is forgotten.
                makes={
                    str(discovery_id): int(day)
                    for discovery_id, day in _object_or_empty(resident_data.get("makes")).items()
                    if discovery_id in world.discoveries
                },
                lessons={
                    str(discovery_id): max(0.0, float(minutes))
                    for discovery_id, minutes in _object_or_empty(resident_data.get("lessons")).items()
                    if discovery_id in world.discoveries
                },
                # A limb that is no longer defined is simply not missed.
                lost_limbs=[
                    str(limb)
                    for limb in dict.fromkeys(_list_or_empty(resident_data.get("lost_limbs")))
                    if limb in world.registries.limbs
                ],
                inventory=_inventory_from_data(resident_data.get("inventory")),
            )
            world.residents[resident.resident_id] = resident

        for resident in world.residents.values():
            if not self._partner_is_valid(world, resident):
                resident.activity = None
            # A couple is only kept if both are there and each names the other.
            other = world.residents.get(resident.couple_with or "")
            if other is None or other.couple_with != resident.resident_id:
                resident.couple_with = None

        relationships = data.get("relationships", [])
        if isinstance(relationships, list):
            for relationship_data in relationships:
                if not isinstance(relationship_data, dict):
                    raise ValueError("Relationship save entry must be an object")
                relationship = Relationship(
                    source_id=str(relationship_data["source_id"]),
                    target_id=str(relationship_data["target_id"]),
                    affection=float(relationship_data.get("affection", 0.0)),
                    trust=float(relationship_data.get("trust", 0.0)),
                    attraction=float(relationship_data.get("attraction", 0.0)),
                    fear=float(relationship_data.get("fear", 0.0)),
                    resentment=float(relationship_data.get("resentment", 0.0)),
                    last_argued=(
                        int(relationship_data["last_argued"])
                        if relationship_data.get("last_argued") is not None
                        else None
                    ),
                    bond=str(relationship_data.get("bond", "")),
                    last_together=(
                        int(relationship_data["last_together"])
                        if relationship_data.get("last_together") is not None
                        else None
                    ),
                )
                world.relationships[(relationship.source_id, relationship.target_id)] = relationship

        for resident_id, memories in _object_or_empty(data.get("memories")).items():
            for memory_data in memories if isinstance(memories, list) else []:
                if isinstance(memory_data, dict):
                    world.memories.remember(str(resident_id), _memory_from_data(memory_data))

        self._restore_kin(world, data, version)
        self._restore_politics(world, data)
        # Only what is still there can be taken apart, and only by somebody who still lives here.
        for saved in _list_or_empty(data.get("salvage")):
            if not isinstance(saved, dict):
                continue
            object_id, resident_id = str(saved.get("object_id", "")), str(saved.get("resident_id", ""))
            if object_id in world.interactables and resident_id in world.residents:
                world.salvage[object_id] = Salvage(object_id, resident_id, max(0.0, float(saved.get("progress", 0.0))))
        self._restore_items(world, data, version)
        deaths = data.get("deaths", [])
        world.deaths = [
            Death(
                resident_id=str(death.get("resident_id", "")),
                name=str(death.get("name", "")),
                timestamp=int(death.get("timestamp", 0)),
                cause=str(death.get("cause", "")),
                killer_id=_text_or_none(death.get("killer_id")),
                grave_id=_text_or_none(death.get("grave_id")),
            )
            for death in (deaths if isinstance(deaths, list) else [])
            if isinstance(death, dict)
        ]
        self._restore_knowledge(world, data)
        self._restore_decisions(world, data)
        self._restore_happenings(world, data, rng_data)
        self._restore_trading(world, data, version)

        event_log = data.get("event_log", [])
        world.event_log = [str(line) for line in event_log] if isinstance(event_log, list) else []
        self._restore_tutorial(world, data)
        self._restore_tastes(world, data)
        self._restore_research(world, data, version)
        self._restore_housing(world, data)
        self._restore_ledger(world, data)
        return world

    def _restore_ledger(self, world: SimulationWorld, data: dict[str, Any]) -> None:
        """Put back what was written down of what comes in and goes out. A save from before has
        nothing written: its books are opened the first minute it goes on."""
        saved = _object_or_empty(data.get("ledger"))

        def flows(written: Any) -> dict[str, dict[str, float]]:
            return {
                str(resource): {str(why): float(units) for why, units in _object_or_empty(by_why).items()}
                for resource, by_why in _object_or_empty(written).items()
            }

        def by_day(written: Any) -> dict[int, Any]:
            return {int(day): each for day, each in _object_or_empty(written).items() if str(day).lstrip("-").isdigit()}

        world.accounts = LedgerState(
            day=int(saved.get("day", 0)),
            opened_at=int(saved.get("opened_at", 0)),
            today=flows(saved.get("today")),
            days={day: flows(written) for day, written in by_day(saved.get("days")).items()},
            held={
                day: {str(resource): int(units) for resource, units in _object_or_empty(count).items()}
                for day, count in by_day(saved.get("held")).items()
            },
        )

    def _restore_discoveries(self, world: SimulationWorld, data: dict[str, Any]) -> None:
        """Put back what residents have come to at their jobs, and the items that were made of
        it, before anything that may be one of them is. A save from before has none."""
        for saved in _list_or_empty(data.get("discoveries")):
            # What was found (S59) is one of the kinds there are to find, and the rest one a job teaches.
            found = isinstance(saved, dict) and bool(saved.get("source"))
            kinds = world.registries.finds.kinds if found else world.registries.crafts.kinds
            if not isinstance(saved, dict) or "discovery_id" not in saved or saved.get("kind") not in kinds:
                # A kind of thing that is no longer defined cannot be made, and is forgotten.
                continue
            discovery = Discovery(
                discovery_id=str(saved["discovery_id"]),
                kind=str(saved["kind"]),
                job_id=str(saved.get("job_id", "")),
                by=str(saved.get("by", "")),
                by_name=str(saved.get("by_name", "")),
                level=int(saved.get("level", 2)),
                day=int(saved.get("day", 0)),
                name=str(saved.get("name", "")),
                choices={str(key): str(value) for key, value in _object_or_empty(saved.get("choices")).items()},
                item_id=_text_or_none(saved.get("item_id")),
                item=dict(_object_or_empty(saved.get("item"))),
                source=str(saved.get("source") or ""),
                units=max(0, int(saved["units"])) if isinstance(saved.get("units"), int) else 0,
                owner=_text_or_none(saved.get("owner")),
            )
            world.discoveries[discovery.discovery_id] = discovery
        world.discovery_count = max(int(data.get("discovery_count", 0)), len(world.discoveries))
        world.crafts.restore(world)

    def _restore_politics(self, world: SimulationWorld, data: dict[str, Any]) -> None:
        """Put back the government and what each resident holds about it. A save from before
        has neither: the settlement chooses a government as one that has just grown to it does."""
        saved = _object_or_empty(data.get("government"))
        state = world.government
        state.kind = _text_or_none(saved.get("kind"))
        state.leader = _text_or_none(saved.get("leader"))
        state.council = [str(member) for member in _list_or_empty(saved.get("council"))]
        for measure, value in _object_or_empty(saved.get("measures")).items():
            if measure in MEASURES:
                state.measures[measure] = float(value)
        state.chosen_on = int(saved["chosen_on"]) if saved.get("chosen_on") is not None else None
        state.term_began = int(saved.get("term_began", 0))
        for moment in ("choosing_until", "election_at", "vacant_since"):
            setattr(state, moment, int(saved[moment]) if saved.get(moment) is not None else None)
        state.proposed = _text_or_none(saved.get("proposed"))
        state.heir = _text_or_none(saved.get("heir"))
        state.resigned = _text_or_none(saved.get("resigned"))
        held = vars(PoliticalProfile())
        for resident_id, values in _object_or_empty(data.get("political_profiles")).items():
            if isinstance(values, dict):
                world.political_profiles[str(resident_id)] = PoliticalProfile(
                    **{name: float(values.get(name, default)) for name, default in held.items()}
                )
        # A law that is no longer defined is no longer in force.
        state.laws = {
            str(law_id): LawInForce(
                law_id=str(law_id),
                degree=max(0, int(law.get("degree", 0))),
                params={str(key): str(value) for key, value in _object_or_empty(law.get("params")).items()},
                since=int(law.get("since", 0)),
                by=_text_or_none(law.get("by")),
                pushed=bool(law.get("pushed", False)),
                imposed=bool(law.get("imposed", False)),
            )
            for law_id, law in _object_or_empty(saved.get("laws")).items()
            if isinstance(law, dict) and law_id in world.registries.laws.laws
        }
        # Nobody is out against a law that is no longer in force.
        state.protests = {
            str(law_id): ProtestRecord(
                law_id=str(law_id),
                days=max(0, int(record.get("days", 0))),
                last_day=int(record.get("last_day", 0)),
                who=[str(each) for each in _list_or_empty(record.get("who")) if each in world.residents],
            )
            for law_id, record in _object_or_empty(saved.get("protests")).items()
            if isinstance(record, dict) and law_id in state.laws
        }
        state.meals = {
            str(resident_id): [int(eaten[0]), int(eaten[1])]
            for resident_id, eaten in _object_or_empty(saved.get("meals")).items()
            if isinstance(eaten, list) and len(eaten) == 2
        }
        kinds = world.registries.proposals.kinds
        # A proposal of a kind that is no longer defined cannot be decided, and is forgotten.
        waiting = [
            _proposal_from_data(proposal)
            for proposal in _object_or_empty(saved.get("proposals")).values()
            if isinstance(proposal, dict) and proposal.get("kind") in kinds
        ]
        state.proposals = {proposal.proposal_id: proposal for proposal in waiting if proposal.status == PENDING}
        state.decided = [
            _proposal_from_data(proposal)
            for proposal in _list_or_empty(saved.get("decided"))
            if isinstance(proposal, dict) and proposal.get("kind") in kinds
        ]
        state.proposal_count = max(0, int(saved.get("proposal_count", 0)))
        state.refused = {str(matter): int(day) for matter, day in _object_or_empty(saved.get("refused")).items()}
        state.raised_on = {
            str(resident_id): int(day) for resident_id, day in _object_or_empty(saved.get("raised_on")).items()
        }
        state.elections = [
            _election_from_data(election)
            for election in _list_or_empty(saved.get("elections"))
            if isinstance(election, dict)
        ]
        state.recall = bool(saved.get("recall", False))
        state.rigged_by = _text_or_none(saved.get("rigged_by"))
        state.rig_asked = bool(saved.get("rig_asked", False))
        state.backing = {
            str(resident_id): [str(spoken[0]), float(spoken[1])]
            for resident_id, spoken in _object_or_empty(saved.get("backing")).items()
            if isinstance(spoken, list) and len(spoken) == 2
        }
        for resident_id, values in _object_or_empty(data.get("player_standing")).items():
            if isinstance(values, dict):
                world.player_standing[str(resident_id)] = PlayerStanding(
                    trust=float(values.get("trust", 50.0)), resistance=float(values.get("resistance", 0.0))
                )
        # Only somebody who is still here can be on their way out.
        world.leaving = {
            str(resident_id): int(by)
            for resident_id, by in _object_or_empty(data.get("leaving")).items()
            if resident_id in world.residents
        }
        world.exiled = [
            Exile(
                resident_id=str(exile.get("resident_id", "")),
                name=str(exile.get("name", "")),
                at=int(exile.get("at", 0)),
                why=str(exile.get("why", "")),
                # Somebody thrown out before anybody could come back is gone for good.
                back_at=int(exile["back_at"]) if exile.get("back_at") is not None else None,
                grudge=float(exile.get("grudge", 0.0)),
                tries=int(exile.get("tries", 0)),
                person=dict(_object_or_empty(exile.get("person"))),
                returned=bool(exile.get("returned", False)),
            )
            for exile in _list_or_empty(data.get("exiled"))
            if isinstance(exile, dict)
        ]
        self._restore_courts(world, _object_or_empty(data.get("courts")))

    def _restore_courts(self, world: SimulationWorld, saved: dict[str, Any]) -> None:
        """Put back the trials, the sentences being served and what has been carried out. A
        save from before there were any has none."""
        courts = JusticeState()
        punishments = world.registries.justice.punishments
        for values in _list_or_empty(saved.get("trials")):
            if not isinstance(values, dict) or not values.get("trial_id"):
                continue
            step = str(values.get("step", CLOSED))
            trial = Trial(
                trial_id=str(values["trial_id"]),
                accused=str(values.get("accused", "")),
                accuser=str(values.get("accuser", "")),
                offence=str(values.get("offence", "")),
                fact_id=str(values.get("fact_id", "")),
                opened_at=int(values.get("opened_at", 0)),
                step=step if step in (*STEPS, CLOSED) else CLOSED,
                next_at=int(values.get("next_at", 0)),
                witnesses=[str(each) for each in _list_or_empty(values.get("witnesses"))],
                ballots={str(key): bool(value) for key, value in _object_or_empty(values.get("ballots")).items()},
                verdict=str(values["verdict"]) if values.get("verdict") else None,
                punishment=str(values["punishment"]) if values.get("punishment") else None,
                closed_at=int(values["closed_at"]) if values.get("closed_at") is not None else None,
            )
            if trial.open and trial.accused not in world.residents:
                # Nobody is tried who is no longer here.
                trial.step = CLOSED
            courts.trials[trial.trial_id] = trial
        courts.trial_count = max(int(saved.get("trial_count", 0)), len(courts.trials))
        for values in _list_or_empty(saved.get("sentences")):
            if isinstance(values, dict) and values.get("resident_id") in world.residents and values.get("punishment") in punishments:
                place = values.get("place_id")
                courts.sentences.append(
                    Sentence(
                        resident_id=str(values["resident_id"]),
                        punishment=str(values["punishment"]),
                        trial_id=str(values.get("trial_id", "")),
                        until=int(values.get("until", 0)),
                        place_id=str(place) if place else None,
                        unfed_on=int(values.get("unfed_on", 0)),
                    )
                )
        for values in _list_or_empty(saved.get("history")):
            if isinstance(values, dict) and values.get("resident_id"):
                courts.history.append(
                    PunishmentRecord(
                        resident_id=str(values["resident_id"]),
                        name=str(values.get("name", "")),
                        offence=str(values.get("offence", "")),
                        punishment=str(values.get("punishment", "")),
                        at=int(values.get("at", 0)),
                        trial_id=str(values.get("trial_id", "")),
                        present=[str(each) for each in _list_or_empty(values.get("present"))],
                        kin=[str(each) for each in _list_or_empty(values.get("kin"))],
                        friends=[str(each) for each in _list_or_empty(values.get("friends"))],
                        reactions={str(key): str(value) for key, value in _object_or_empty(values.get("reactions")).items()},
                        child=bool(values.get("child", False)),
                    )
                )
        ration = saved.get("ration")
        if isinstance(ration, dict):
            courts.ration = Ration(
                meals=max(0, int(ration.get("meals", 0))),
                drinks=max(0, int(ration.get("drinks", 0))),
                food=str(ration.get("food", "")),
                drink=str(ration.get("drink", "")),
            )
        for resident_id, about in _object_or_empty(saved.get("weighing")).items():
            if resident_id in world.residents and isinstance(about, list) and len(about) == 2:
                courts.weighing[str(resident_id)] = (str(about[0]), str(about[1]))
        at_gate = saved.get("at_gate")
        courts.at_gate = str(at_gate) if at_gate else None
        world.courts = courts

    def _restore_kin(self, world: SimulationWorld, data: dict[str, Any], version: int) -> None:
        """Put back who is kin to whom. In a save from before, nobody is, and everyone is who
        the game says they are or their ID makes them."""
        if version < FIRST_FAMILY_VERSION:
            for resident in world.residents.values():
                world.family.from_before(world, resident)
            return
        for person_id, saved in _object_or_empty(data.get("kinship")).items():
            if not isinstance(saved, dict):
                continue
            world.kinship[str(person_id)] = KinRecord(
                name=str(saved.get("name", person_id)),
                gender=str(saved.get("gender", "")),
                parents=[str(each) for each in _list_or_empty(saved.get("parents"))],
                adoptive=[str(each) for each in _list_or_empty(saved.get("adoptive"))],
                siblings=[str(each) for each in _list_or_empty(saved.get("siblings"))],
                spouse=_text_or_none(saved.get("spouse")),
            )
        sides = vars(Personality())
        for saved in _list_or_empty(data.get("bundles")):
            if not isinstance(saved, dict) or "child_id" not in saved:
                continue
            place = str(saved.get("place", "ground"))
            carrier = _text_or_none(saved.get("carried_by"))
            keeper = _text_or_none(saved.get("keeper"))
            bundle = Bundle(
                child_id=str(saved["child_id"]),
                name=str(saved.get("name", saved["child_id"])),
                sex=str(saved.get("sex", "f")),
                gender=str(saved.get("gender", saved.get("sex", "f"))),
                drawn_to=str(saved.get("drawn_to", "both")),
                born=int(saved.get("born", world.clock.day)),
                personality=Personality(
                    **{
                        side: float(value)
                        for side, value in _object_or_empty(saved.get("personality")).items()
                        if side in sides
                    }
                ),
                # A trait that is no longer defined is dropped, as it is for anybody.
                traits=[str(trait) for trait in _list_or_empty(saved.get("traits")) if world.registries.traits.find(str(trait))],
                carried_by=carrier if carrier in world.residents else None,
                place=place if place in PLACES else "ground",
                x=int(saved.get("x", 0)),
                y=int(saved.get("y", 0)),
                hunger=float(saved.get("hunger", 0.0)),
                health=float(saved.get("health", 100.0)),
                left=int(saved.get("left", 0)),
                refused=[str(each) for each in _list_or_empty(saved.get("refused"))],
                asking=_text_or_none(saved.get("asking")),
                asked_at=int(saved.get("asked_at", 0)),
                keeper=keeper if keeper in world.residents else None,
                set_down=bool(saved.get("set_down", False)),
            )
            world.bundles[bundle.child_id] = bundle

    def _restore_research(self, world: SimulationWorld, data: dict[str, Any], version: int) -> None:
        """Put back what is known and what is being worked out. A subject that is gone is forgotten."""
        subjects = world.registries.research.subjects
        if version < FIRST_RESEARCH_VERSION:
            world.research.grant_what_stands(world)
            return
        saved = _object_or_empty(data.get("research"))
        known = [str(each) for each in dict.fromkeys(_list_or_empty(saved.get("known"))) if each in subjects]
        in_hand = _text_or_none(saved.get("subject"))
        world.studies = ResearchState(
            subject_id=in_hand if in_hand in subjects and in_hand not in known else None,
            known=known,
            progress={
                str(subject_id): max(0.0, float(minutes))
                for subject_id, minutes in _object_or_empty(saved.get("progress")).items()
                if subject_id in subjects
                and subject_id not in known
                and isinstance(minutes, (int, float))
                and not isinstance(minutes, bool)
            },
            supplied=[str(each) for each in _list_or_empty(saved.get("supplied")) if each in subjects and each not in known],
        )

    def _restore_tastes(self, world: SimulationWorld, data: dict[str, Any]) -> None:
        """Tastes are kept whatever they are for: one for a tag or an item that no content brings
        any longer does nothing, and is there if the content comes back."""
        for resident_id, kinds in _object_or_empty(data.get("tastes")).items():
            profile = TasteProfile()
            for kind in KINDS:
                for name, taste in _object_or_empty(_object_or_empty(kinds).get(kind)).items():
                    if isinstance(taste, dict):
                        profile.of(kind)[str(name)] = Taste(
                            leaning=float(taste.get("leaning", 0.0)), learned=float(taste.get("learned", 0.0))
                        )
            world.taste_profiles[str(resident_id)] = profile
        for observer_id, subjects in _object_or_empty(data.get("taste_knowledge")).items():
            for subject_id, tastes in _object_or_empty(subjects).items():
                seen = {
                    str(key): float(shown)
                    for key, shown in _object_or_empty(tastes).items()
                    if isinstance(shown, (int, float)) and not isinstance(shown, bool)
                }
                world.taste_knowledge.seen.setdefault(str(observer_id), {})[str(subject_id)] = seen
        for observer_id, subjects in _object_or_empty(data.get("taste_seen_as")).items():
            for subject_id, tastes in _object_or_empty(subjects).items():
                looked = {str(key): str(reaction) for key, reaction in _object_or_empty(tastes).items() if reaction in REACTIONS}
                world.taste_knowledge.seen_as.setdefault(str(observer_id), {})[str(subject_id)] = looked

    def _restore_tutorial(self, world: SimulationWorld, data: dict[str, Any]) -> None:
        """Put a settlement back where it was in its opening. One saved at a step that is gone is past it."""
        saved = _object_or_empty(data.get("tutorial"))
        step_id = _text_or_none(saved.get("step"))
        known = world.registries.tutorial
        world.tutorial = TutorialState(
            step_id=step_id if known.step(step_id) is not None else None,
            since=int(saved.get("since", 0)),
            opened=bool(saved.get("opened", False)),
            acknowledged=bool(saved.get("acknowledged", False)),
            deeds=[str(deed) for deed in _list_or_empty(saved.get("deeds"))],
            done=[str(done) for done in _list_or_empty(saved.get("done"))],
        )

    def _restore_items(self, world: SimulationWorld, data: dict[str, Any], version: int) -> None:
        """Put saved items back. An item of a kind no longer defined is kept as an inert placeholder."""
        if version < FIRST_ITEM_VERSION:
            world.stock_from_layout()
            return
        saved_containers = _object_or_empty(data.get("containers"))
        for object_id, saved in saved_containers.items():
            inventory = _inventory_from_data(saved)
            if object_id in world.containers:
                world.containers[object_id] = inventory
                continue
            # The container is gone: things go back to their owners, and shared things are lost.
            for item in inventory.items:
                owner = world.residents.get(item.owner_id or "")
                if owner is not None:
                    owner.inventory.add(item)
        everything = [*world.containers.values(), *(resident.inventory for resident in world.residents.values())]
        highest = max(
            (_item_number(item.instance_id) for inventory in everything for item in inventory.items), default=0
        )
        world.item_count = max(int(data.get("item_count", 0)), highest)
        if version < LAST_STOCK_CHANGE_VERSION:
            # Containers the map has gained since start with what the map puts in them.
            for entry in world.registries.maps[world.map_id].stock:
                container = world.containers.get(entry.container)
                if entry.container in saved_containers or container is None:
                    continue
                if world.registries.items.find(entry.item) is not None:
                    world.stock(container, entry.item, entry.count, entry.owner)
        thefts = data.get("thefts", [])
        world.thefts = [
            TheftAttempt(
                thief_id=str(attempt.get("thief_id", "")),
                victim_id=str(attempt.get("victim_id", "")),
                item_instance_id=str(attempt.get("item_instance_id", "")),
                discovered=bool(attempt.get("discovered", False)),
                container_id=str(attempt.get("container_id", "")),
                fact_id=str(attempt.get("fact_id", "")),
                noticed=bool(attempt.get("noticed", False)),
                returned=bool(attempt.get("returned", False)),
                amount=max(0.0, float(attempt.get("amount", 0.0))),
            )
            for attempt in (thefts if isinstance(thefts, list) else [])
            if isinstance(attempt, dict)
        ]
        world.theft_cooldowns = {
            str(resident_id): int(minute)
            for resident_id, minute in _object_or_empty(data.get("theft_cooldowns")).items()
        }
        world.notices = {str(name): int(day) for name, day in _object_or_empty(data.get("notices")).items()}
        burnt = data.get("power_burnt", 0.0)
        world.power_burnt = min(1.0, max(0.0, float(burnt))) if isinstance(burnt, (int, float)) else 0.0
        # The beds that have compost on them, and until when. None in a save from before (S65).
        world.dressed = {
            str(object_id): int(until)
            for object_id, until in _object_or_empty(data.get("dressed")).items()
            if isinstance(until, int) and not isinstance(until, bool)
        }
        # The words the player has given. None in a save from before (S58).
        world.words = _words_from_data(data.get("words"))
        world.vacancies = {
            str(job_id): int(minute)
            for job_id, minute in _object_or_empty(data.get("vacancies")).items()
            if job_id in world.registries.jobs
        }

    def _restore_trading(self, world: SimulationWorld, data: dict[str, Any], version: int) -> None:
        """Put back how the settlement trades, its fund, and whoever had stopped by to trade."""
        if version < FIRST_FUND_VERSION:
            world.terms.settle_on_credits(world)
            return
        saved = _object_or_empty(data.get("trading"))
        currency = saved.get("currency")
        asked_on = saved.get("asked_on")
        made = (
            Currency(
                currency_id=str(currency.get("currency_id", "")),
                name=str(currency.get("name", "")),
                singular=str(currency.get("singular", currency.get("name", ""))),
            )
            if isinstance(currency, dict) and currency.get("currency_id") and currency.get("name")
            else None
        )
        world.trading = TradingState(
            currency=made,
            # A settlement trades with a currency only while it has one.
            in_use=bool(saved.get("in_use", False)) and made is not None,
            fund=max(0.0, float(saved.get("fund", 0.0))),
            currency_count=max(0, int(saved.get("currency_count", 0))),
            asked_on=int(asked_on) if asked_on is not None else None,
            refusals={
                str(resident_id): int(times)
                for resident_id, times in _object_or_empty(saved.get("refusals")).items()
                if resident_id in world.residents and isinstance(times, int) and not isinstance(times, bool)
            },
            asked_about=str(saved.get("asked_about", "")),
            answers={
                str(resident_id): bool(said)
                for resident_id, said in _object_or_empty(saved.get("answers")).items()
                if resident_id in world.residents
            },
        )
        # What is owed to or by somebody who is gone is owed no longer.
        world.debts = [
            Debt(
                debtor_id=str(debt["debtor_id"]),
                creditor_id=str(debt["creditor_id"]),
                amount=max(0.0, float(debt.get("amount", 0.0))),
                since=int(debt.get("since", 0)),
                overdue=bool(debt.get("overdue", False)),
            )
            for debt in _list_or_empty(data.get("debts"))
            if isinstance(debt, dict)
            and debt.get("debtor_id") in world.residents
            and debt.get("creditor_id") in world.residents
        ]
        world.at_gate = {
            str(item_id): int(units)
            for item_id, units in _object_or_empty(data.get("at_gate")).items()
            if isinstance(units, int)
            and not isinstance(units, bool)
            and units > 0
            and world.registries.items.find(str(item_id)) is not None
        }
        visitor = data.get("merchant")
        events = world.registries.world_events.events
        # Whoever came with an event the game no longer has, or that is no longer a merchant, has gone.
        if isinstance(visitor, dict) and getattr(events.get(visitor.get("event_id")), "kind", None) == MERCHANT:
            world.merchant = Merchant(
                event_id=str(visitor["event_id"]),
                leaves_at=int(visitor.get("leaves_at", 0)),
                goods={
                    str(item_id): int(units)
                    for item_id, units in _object_or_empty(visitor.get("goods")).items()
                    if isinstance(units, int)
                    and not isinstance(units, bool)
                    and units > 0
                    and world.registries.items.find(str(item_id)) is not None
                },
                purse=max(0.0, float(visitor.get("purse", 0.0))),
                # Word of them that nobody remembers is as good as never given.
                fact_id=visitor.get("fact_id") if visitor.get("fact_id") in world.knowledge.facts else None,
            )
            # Where they stand and where their cart is. A save from before they were anywhere has
            # them found a place now.
            tile, cart = _tile_or_none(visitor.get("tile")), _tile_or_none(visitor.get("cart"))
            if "tile" not in visitor:
                tile, cart = world.merchants.stand(world, events[world.merchant.event_id])
            world.merchant.tile, world.merchant.cart = tile, cart

    def _restore_housing(self, world: SimulationWorld, data: dict[str, Any]) -> None:
        """Put back whose each building is and what has been put in it to be looked at."""
        world.homes = HousingState()
        saved = data.get("housing")
        if not isinstance(saved, dict):
            # A save from before buildings were anybody's: everybody has the house they were
            # sleeping in, unless the settlement is still in its opening, when nothing is.
            if not world.tutorial.active:
                world.housing.settle(world)
            return
        homes = world.homes
        # Only a building that is still there belongs to anybody, and only to whoever still lives here.
        homes.owners = {
            str(room_id): [str(owner) for owner in owners if str(owner) in world.residents]
            for room_id, owners in _object_or_empty(saved.get("owners")).items()
            if str(room_id) in world.rooms and isinstance(owners, list)
        }
        homes.owners = {room_id: owners for room_id, owners in homes.owners.items() if owners}
        homes.names = {str(k): str(v) for k, v in _object_or_empty(saved.get("names")).items() if str(k) in world.rooms}
        uses = world.registries.housing.uses
        homes.uses = {
            str(k): str(v) for k, v in _object_or_empty(saved.get("uses")).items() if str(k) in world.rooms and str(v) in uses
        }
        homes.began = bool(saved.get("began", False))
        homes.locked = [str(room_id) for room_id in saved.get("locked", []) if str(room_id) in homes.owners]
        homes.lifted_on = int(saved.get("lifted_on", 0))
        homes.floors = {str(k): str(v) for k, v in _object_or_empty(saved.get("floors")).items() if str(k) in world.rooms}
        homes.walls = {str(k): str(v) for k, v in _object_or_empty(saved.get("walls")).items() if str(k) in world.rooms}
        homes.ornament_count = max(0, int(saved.get("ornament_count", 0)))
        homes.ornaments = {}
        for room_id, ornaments in _object_or_empty(saved.get("ornaments")).items():
            if str(room_id) not in world.rooms or not isinstance(ornaments, list):
                continue
            kept = [
                Ornament(str(each["ornament_id"]), str(each["kind"]), str(each.get("on", "floor")), int(each.get("x", 0)), int(each.get("y", 0)))
                for each in ornaments
                if isinstance(each, dict) and "ornament_id" in each and "kind" in each
            ]
            if kept:
                homes.ornaments[str(room_id)] = kept

    def _restore_happenings(self, world: SimulationWorld, data: dict[str, Any], rng_data: dict[str, Any]) -> None:
        """Put back the weather, the gate and what has already happened from outside."""
        saved_rng = data.get("event_rng")
        if isinstance(saved_rng, dict):
            world.event_rng = SimulationRNG.from_state(saved_rng)
        else:
            # A save from before world events draws its own from the seed it was started with.
            world.event_rng = SimulationRNG(int(rng_data.get("seed", 1)) * 7919 + 13)
        events = world.registries.world_events
        world.happened = {
            str(event_id): int(day)
            for event_id, day in _object_or_empty(data.get("happened")).items()
            if event_id in events.events
        }
        weather = data.get("weather")
        if isinstance(weather, dict) and weather.get("event_id") in events.events:
            world.weather = Weather(str(weather["event_id"]), int(weather.get("until", 0)))
        upcoming = data.get("upcoming", [])
        world.upcoming = [
            Upcoming(
                str(entry["event_id"]),
                int(entry.get("at", 0)),
                # Word of it that nobody remembers any more is as good as never given.
                entry.get("fact_id") if entry.get("fact_id") in world.knowledge.facts else None,
            )
            for entry in (upcoming if isinstance(upcoming, list) else [])
            if isinstance(entry, dict) and entry.get("event_id") in events.events
        ]
        seen = data.get("newcomers_seen", [])
        world.newcomers_seen = [str(newcomer_id) for newcomer_id in seen] if isinstance(seen, list) else []
        waiting = _text_or_none(data.get("at_the_gate"))
        known = {newcomer.newcomer_id for newcomer in events.newcomers}
        # Whoever waits at the gate does so only while someone is deciding about them.
        deciding = any(decision.kind in GATE_DECISIONS for decision in world.decisions.values())
        world.at_the_gate = waiting if waiting in known and deciding else None
        party = [str(each) for each in _list_or_empty(data.get("gate_party")) if each in known]
        world.gate_party = party if world.at_the_gate is not None else []
        raid = _text_or_none(data.get("under_raid"))
        # Raiders are only at the gate while someone is deciding what to do about them.
        facing = any(decision.kind == RAID_DECISION for decision in world.decisions.values())
        world.under_raid = raid if raid in events.events and facing else None

    def _restore_decisions(self, world: SimulationWorld, data: dict[str, Any]) -> None:
        world.decision_count = int(data.get("decision_count", 0))
        world.crisis_cooldowns = {
            str(resident_id): int(minute)
            for resident_id, minute in _object_or_empty(data.get("crisis_cooldowns")).items()
        }
        history = data.get("history", [])
        world.history = [
            _event_from_data(event) for event in (history if isinstance(history, list) else []) if isinstance(event, dict)
        ]
        decisions = data.get("decisions", [])
        for saved in decisions if isinstance(decisions, list) else []:
            # A decision is only kept if its resident, its kind and the job it is about still exist.
            if (
                isinstance(saved, dict)
                and saved.get("resident_id") in world.residents
                and saved.get("kind") in world.registries.decisions
                and saved.get("job_id") in (None, *world.registries.jobs)
            ):
                decision = _decision_from_data(saved)
                world.decisions[decision.decision_id] = decision

    def _restore_knowledge(self, world: SimulationWorld, data: dict[str, Any]) -> None:
        facts = data.get("facts", [])
        for fact_data in facts if isinstance(facts, list) else []:
            if isinstance(fact_data, dict) and "fact_id" in fact_data:
                location_id = fact_data.get("location_id")
                world.knowledge.add_fact(
                    Fact(
                        fact_id=str(fact_data["fact_id"]),
                        event_type=str(fact_data.get("event_type", "")),
                        text=str(fact_data.get("text", "")),
                        subject_ids=[str(subject) for subject in fact_data.get("subject_ids", [])],
                        importance=int(fact_data.get("importance", 0)),
                        timestamp=int(fact_data.get("timestamp", 0)),
                        location_id=str(location_id) if location_id is not None else None,
                        expires_at=int(fact_data["expires_at"]) if fact_data.get("expires_at") is not None else None,
                    )
                )
        for resident_id, beliefs in _object_or_empty(data.get("beliefs")).items():
            for belief_data in beliefs if isinstance(beliefs, list) else []:
                # A belief about a fact that is gone would be a dangling ID, so it is dropped.
                if not isinstance(belief_data, dict) or belief_data.get("fact_id") not in world.knowledge.facts:
                    continue
                told_by = belief_data.get("told_by")
                world.knowledge.set_belief(
                    str(resident_id),
                    Belief(
                        fact_id=str(belief_data["fact_id"]),
                        credibility=float(belief_data.get("credibility", 1.0)),
                        source=str(belief_data.get("source", "told")),
                        learned_at=int(belief_data.get("learned_at", 0)),
                        told_by=str(told_by) if told_by is not None else None,
                    ),
                )

    def _partner_is_valid(self, world: SimulationWorld, resident: Resident) -> bool:
        """A saved conversation is only kept if both sides and its definition still exist."""
        activity = resident.activity
        if activity is None or activity.partner_id is None:
            return True
        partner = world.residents.get(activity.partner_id)
        if partner is None:
            return False
        if not activity.using:
            return True
        return (
            activity.action in world.registries.interactions
            and partner.activity is not None
            and partner.activity.partner_id == resident.resident_id
            and partner.activity.action == activity.action
        )

    def _can_stand(self, world: SimulationWorld, tile: tuple[int, int]) -> bool:
        """Whether a tile is on the map and its terrain can be walked on."""
        if not world.tile_map.in_bounds(tile):
            return False
        terrain = world.registries.terrain.get(world.tile_map.terrain_at(tile))
        return terrain is not None and terrain.walkable

    def _restore_map(self, world: SimulationWorld, data: dict[str, Any], version: int) -> None:
        """Load the saved map, falling back to the default one if it no longer exists."""
        map_id = str(data.get("map_id", DEFAULT_MAP_ID))
        world.load_layout(map_id if map_id in world.registries.maps else DEFAULT_MAP_ID)
        if map_id == world.map_id and version >= FIRST_URBANISM_VERSION:
            self._restore_urbanism(world, data)
        saved = data.get("interactables")
        if map_id != world.map_id or not isinstance(saved, list) or version < FIRST_JOB_VERSION:
            return
        containers_before = world.containers
        from_map = world.interactables
        # Objects whose kind is no longer defined are dropped instead of breaking the save.
        world.interactables = {
            str(placed["id"]): Interactable(
                str(placed["id"]),
                str(placed["kind"]),
                int(placed["x"]),
                int(placed["y"]),
                # How good it is. In a save from before everything is common (S54).
                max(1, min(world.registries.rarities.highest, _level_of(placed))),
                # Whether it is switched on. In a save from before everything is (S55).
                bool(placed.get("on", True)),
                max(0, _level_of({"level": placed.get("switched_at", 0)}) if placed.get("switched_at") else 0),
                # How much is left in it. In a save from before everything is whole (S55).
                _condition_of(placed),
            )
            for placed in saved
            if isinstance(placed, dict) and world.registries.interactables.find(str(placed.get("kind")))
        }
        if version < LAST_MAP_CHANGE_VERSION:
            # What the map has gained since is added, wherever the save has nothing standing.
            taken = {(placed.x, placed.y) for placed in world.interactables.values()}
            for object_id, placed in from_map.items():
                if object_id not in world.interactables and (placed.x, placed.y) not in taken:
                    world.interactables[object_id] = placed
        if version < FIRST_MEDICINE_VERSION:
            self._move_what_the_map_moved(world)
        self._gain_from_the_map(world, from_map, version)
        if version < FIRST_CURRENT_VERSION and not any(
            world.definition_of(placed).gives for placed in world.interactables.values()
        ):
            # A tank runs on current now. Where there is nothing to give it any, it is a
            # well from here on, which is the same post worked by hand (S55).
            for placed in world.interactables.values():
                if placed.kind == TANK_KIND and world.registries.interactables.find(WELL_KIND) is not None:
                    placed.kind = WELL_KIND
        world.containers = {
            object_id: containers_before.get(object_id, Inventory())
            for object_id, placed in world.interactables.items()
            if world.definition_of(placed).container
        }
        self._restore_sites(world, data)

    def _gain_from_the_map(self, world: SimulationWorld, from_map: dict[str, Interactable], version: int) -> None:
        """Give a save from before a change to the map the things that change added, each
        where the map has it, if all the ground it takes is still bare and nobody has built
        over it. And call a building as the map calls it now, if it still has its old name."""
        covered = {
            tile for placed in world.interactables.values() for tile in placed.footprint(world.definition_of(placed))
        }
        terrain = world.registries.terrain
        for since, object_ids in MAP_GAINS.items():
            for object_id in object_ids if version < since else ():
                placed = from_map.get(object_id)
                if placed is None or object_id in world.interactables:
                    continue
                ground = placed.footprint(world.definition_of(placed))
                bare = all(
                    world.tile_map.in_bounds(tile)
                    and tile not in covered
                    and world.room_at(tile) is None
                    and terrain[world.tile_map.terrain_at(tile)].walkable
                    for tile in ground
                )
                if bare:
                    world.interactables[object_id] = placed
                    covered.update(ground)
        layout = world.registries.maps.get(world.map_id)
        named = {room_id: room.name for room_id, room in layout.rooms.items()} if layout is not None else {}
        for since, renamed in MAP_RENAMES.items():
            for room_id, was in renamed.items() if version < since else ():
                room = world.rooms.get(room_id)
                if room is not None and room.name == was and room_id in named:
                    room.name = named[room_id]

    def _restore_sites(self, world: SimulationWorld, data: dict[str, Any]) -> None:
        """Put back what was being built. A site for something no longer defined, or that no
        longer fits on the map, is dropped along with what had been brought to it."""
        world.site_count = max(0, int(data.get("site_count", 0)))
        for saved in _list_or_empty(data.get("sites")):
            if not isinstance(saved, dict) or "id" not in saved:
                continue
            site = BuildSite(
                site_id=str(saved["id"]),
                kind=str(saved.get("kind", "")),
                what=str(saved.get("what", "")),
                x=int(saved.get("x", 0)),
                y=int(saved.get("y", 0)),
                in_charge=_text_or_none(saved.get("in_charge")),
                delivered={
                    str(item_id): int(units)
                    for item_id, units in _object_or_empty(saved.get("delivered")).items()
                    if isinstance(units, int) and not isinstance(units, bool) and units > 0
                },
                progress=max(0.0, float(saved.get("progress", 0.0))),
                started_at=int(saved.get("started_at", 0)),
            )
            if world.construction.measure(world, site) and all(world.tile_map.in_bounds(tile) for tile in site.tiles):
                world.sites[site.site_id] = site

    def _move_what_the_map_moved(self, world: SimulationWorld) -> None:
        """Put objects an older save has where the map used to have them where the map has them now.

        Only what still stands exactly where it did is moved, and only onto ground nothing else is on:
        whatever the player has rearranged since is left as they left it.
        """
        pending = dict(MOVED_ON_THE_MAP.get(world.map_id, {}))
        progress = True
        # One may be standing where another is going, so they are gone over until none can move.
        while pending and progress:
            progress = False
            for object_id, (old, new) in list(pending.items()):
                placed = world.interactables.get(object_id)
                if placed is None or (placed.x, placed.y) != old:
                    del pending[object_id]
                    continue
                definition = world.definition_of(placed)
                moved = Interactable(object_id, placed.kind, new[0], new[1])
                others = {
                    tile
                    for other in world.interactables.values()
                    if other.object_id != object_id
                    for tile in other.footprint(world.definition_of(other))
                }
                if any(tile in others or not self._can_stand(world, tile) for tile in moved.footprint(definition)):
                    continue
                world.interactables[object_id] = moved
                del pending[object_id]
                progress = True

    def _restore_urbanism(self, world: SimulationWorld, data: dict[str, Any]) -> None:
        """Restore an edited map, ignoring malformed optional layout entries safely."""
        terrain = data.get("terrain")
        if (
            isinstance(terrain, list)
            and len(terrain) == world.tile_map.height
            and all(isinstance(row, list) and len(row) == world.tile_map.width for row in terrain)
        ):
            known = world.registries.terrain
            if all(isinstance(cell, str) and cell in known for row in terrain for cell in row):
                world.tile_map = TileMap(
                    world.tile_map.width,
                    world.tile_map.height,
                    [[str(cell) for cell in row] for row in terrain],
                )

        rooms = data.get("rooms")
        if isinstance(rooms, list):
            restored: dict[str, Room] = {}
            for saved in rooms:
                if not isinstance(saved, dict) or "id" not in saved:
                    continue
                room = Room(
                    room_id=str(saved["id"]),
                    name=str(saved.get("name", saved["id"])),
                    privacy=float(saved.get("privacy", 0.0)),
                    x=int(saved.get("x", 0)),
                    y=int(saved.get("y", 0)),
                    width=int(saved.get("width", 0)),
                    height=int(saved.get("height", 0)),
                    roofed=bool(saved.get("roofed", False)),
                    blueprint_id=_text_or_none(saved.get("blueprint_id")),
                )
                corners = (
                    (room.x, room.y),
                    (room.x + room.width - 1, room.y + room.height - 1),
                )
                if room.width > 0 and room.height > 0 and all(
                    world.tile_map.in_bounds(corner) for corner in corners
                ):
                    restored[room.room_id] = room
            world.rooms = restored

        urbanism = _object_or_empty(data.get("urbanism"))
        world.urbanism.next_object = max(1, int(urbanism.get("next_object", 1)))
        world.urbanism.next_building = max(1, int(urbanism.get("next_building", 1)))
        underlays = _object_or_empty(urbanism.get("underlays"))
        world.urbanism.underlays = {}
        for room_id, entries in underlays.items():
            if room_id not in world.rooms or not isinstance(entries, list):
                continue
            restored_underlay: dict[tuple[int, int], str] = {}
            for entry in entries:
                if not isinstance(entry, dict):
                    continue
                tile = (int(entry.get("x", -1)), int(entry.get("y", -1)))
                terrain_id = str(entry.get("terrain", ""))
                if world.tile_map.in_bounds(tile) and terrain_id in world.registries.terrain:
                    restored_underlay[tile] = terrain_id
            world.urbanism.underlays[str(room_id)] = restored_underlay


def _activity_to_data(activity: Activity | None) -> dict[str, Any] | None:
    if activity is None:
        return None
    return {
        "action": activity.action,
        "target_id": activity.target_id,
        "path": [list(tile) for tile in activity.path],
        "minutes_left": activity.minutes_left,
        "using": activity.using,
        "partner_id": activity.partner_id,
        "intent": activity.intent,
        "item_id": activity.item_id,
        "item_level": activity.item_level,
        "held_up": activity.held_up,
        "ordered": activity.ordered,
        "about": activity.about,
        "about_text": activity.about_text,
        "brought": activity.brought,
        "began_at": activity.began_at,
    }


def _words_to_data(words: VocabularyState) -> dict[str, Any]:
    return {
        "lists": {list_id: [vars(word) for word in given] for list_id, given in words.lists.items()},
        "phrases": {resident_id: dict(mine) for resident_id, mine in words.phrases.items()},
        "nicknames": {resident_id: dict(mine) for resident_id, mine in words.nicknames.items()},
        "asks": [vars(ask) for ask in words.asks],
        "ask_count": words.ask_count,
        "told": {resident_id: list(told) for resident_id, told in words.told.items()},
    }


def _words_from_data(data: Any) -> VocabularyState:
    """The words the player has given, out of a save. Whatever of it is not as it should be
    is left out, and a save from before there were any gives none."""
    words = VocabularyState()
    if not isinstance(data, dict):
        return words
    for list_id, given in _object_or_empty(data.get("lists")).items():
        for word in given if isinstance(given, list) else []:
            if isinstance(word, dict) and isinstance(word.get("word_id"), str) and isinstance(word.get("text"), str):
                by, day = word.get("by"), word.get("day", 0)
                words.lists.setdefault(str(list_id), []).append(
                    Word(
                        word["word_id"],
                        word["text"],
                        str(by) if by is not None else None,
                        int(day) if isinstance(day, int) and not isinstance(day, bool) else 0,
                    )
                )
    for name, kept in (("phrases", words.phrases), ("nicknames", words.nicknames)):
        for resident_id, mine in _object_or_empty(data.get(name)).items():
            if isinstance(mine, dict):
                kept[str(resident_id)] = {str(key): str(text) for key, text in mine.items() if isinstance(text, str)}
    for ask in data.get("asks", []) if isinstance(data.get("asks"), list) else []:
        if isinstance(ask, dict) and ask.get("kind") in ASK_KINDS and all(
            isinstance(ask.get(key), str) for key in ("ask_id", "resident_id", "what")
        ):
            since = ask.get("since", 0)
            words.asks.append(
                Ask(
                    ask["ask_id"],
                    ask["resident_id"],
                    ask["kind"],
                    ask["what"],
                    int(since) if isinstance(since, int) and not isinstance(since, bool) else 0,
                )
            )
    count = data.get("ask_count", 0)
    words.ask_count = max(len(words.asks), int(count) if isinstance(count, int) and not isinstance(count, bool) else 0)
    for resident_id, told in _object_or_empty(data.get("told")).items():
        if isinstance(told, list) and len(told) == 2 and all(isinstance(each, str) for each in told):
            words.told[str(resident_id)] = (told[0], told[1])
    return words


def _activity_from_data(data: Any) -> Activity | None:
    if not isinstance(data, dict) or "action" not in data:
        return None
    target_id = data.get("target_id")
    partner_id = data.get("partner_id")
    intent = data.get("intent")
    item_id = data.get("item_id")
    return Activity(
        action=str(data["action"]),
        target_id=str(target_id) if target_id is not None else None,
        path=[(int(tile[0]), int(tile[1])) for tile in data.get("path", [])],
        minutes_left=int(data.get("minutes_left", 0)),
        using=bool(data.get("using", False)),
        partner_id=str(partner_id) if partner_id is not None else None,
        intent=str(intent) if intent is not None else None,
        item_id=str(item_id) if item_id is not None else None,
        item_level=max(1, _level_of({"level": data.get("item_level", 1)})),
        held_up=int(data.get("held_up", 0)),
        ordered=bool(data.get("ordered", False)),
        about=str(data.get("about", "")),
        about_text=str(data.get("about_text", "")),
        brought=bool(data.get("brought", False)),
        began_at=int(data.get("began_at", 0)),
    )


def _order_to_data(order: Order | None) -> dict[str, Any] | None:
    return {"kind": order.kind, "target_id": order.target_id} if order is not None else None


def _order_from_data(data: Any) -> Order | None:
    if not isinstance(data, dict) or "kind" not in data:
        return None
    target_id = data.get("target_id")
    return Order(str(data["kind"]), str(target_id) if target_id is not None else None)


def _inventory_to_data(inventory: Inventory) -> list[dict[str, Any]]:
    return [
        {
            "id": item.instance_id,
            "definition_id": item.definition_id,
            "owner_id": item.owner_id,
            "condition": item.condition,
            "quantity": item.quantity,
            "level": item.level,
            "freshness": item.freshness,
            "given_by": item.given_by,
            "meant_for": item.meant_for,
        }
        for item in inventory.items
    ]


def _inventory_from_data(data: Any) -> Inventory:
    inventory = Inventory()
    for item in data if isinstance(data, list) else []:
        if not isinstance(item, dict) or "id" not in item or "definition_id" not in item:
            continue
        owner_id = item.get("owner_id")
        inventory.add(
            ItemInstance(
                instance_id=str(item["id"]),
                definition_id=str(item["definition_id"]),
                owner_id=str(owner_id) if owner_id is not None else None,
                condition=float(item.get("condition", 100.0)),
                quantity=max(1, int(item.get("quantity", 1))),
                # How rare it is. In a save from before everything is common (S64).
                level=max(1, _level_of(item)),
                # How fresh it is. In a save from before everything is quite fresh (S65).
                freshness=_condition_of({"condition": item.get("freshness", 100.0)}),
                given_by=_text_or_none(item.get("given_by")),
                meant_for=_text_or_none(item.get("meant_for")),
            )
        )
    return inventory


def _item_number(instance_id: str) -> int:
    """The counter part of an ID such as `item_12`, or 0 for any other form."""
    number = instance_id.rpartition("_")[2]
    return int(number) if number.isdigit() else 0


def _decision_to_data(decision: Decision) -> dict[str, Any]:
    return {
        "decision_id": decision.decision_id,
        "resident_id": decision.resident_id,
        "prompt": decision.prompt,
        "options": [
            {"id": option.option_id, "text": option.text, "influence": dict(option.influence)}
            for option in decision.options
        ],
        "related_event_type": decision.related_event_type,
        "kind": decision.kind,
        "deadline": decision.deadline,
        "crisis": vars(decision.crisis) if decision.crisis is not None else None,
        "job_id": decision.job_id,
        "subject": decision.subject,
        "inputs": dict(decision.inputs),
    }


def _decision_from_data(data: dict[str, Any]) -> Decision:
    crisis = data.get("crisis")
    return Decision(
        decision_id=str(data["decision_id"]),
        resident_id=str(data["resident_id"]),
        prompt=str(data.get("prompt", "")),
        options=[
            DecisionOption(
                str(option["id"]),
                str(option.get("text", "")),
                {str(outcome): float(weight) for outcome, weight in option.get("influence", {}).items()},
            )
            for option in data.get("options", [])
        ],
        related_event_type=str(data.get("related_event_type", "")),
        kind=str(data.get("kind", "")),
        deadline=int(data.get("deadline", 0)),
        crisis=Crisis(
            source_id=str(crisis.get("source_id", data["resident_id"])),
            target_id=str(crisis["target_id"]) if crisis.get("target_id") is not None else None,
            anger=float(crisis.get("anger", 0.0)),
            urgency=int(crisis.get("urgency", 0)),
            intent=str(crisis.get("intent", "")),
        )
        if isinstance(crisis, dict)
        else None,
        job_id=_text_or_none(data.get("job_id")),
        subject=_text_or_none(data.get("subject")),
        inputs={
            str(name): float(value)
            for name, value in _object_or_empty(data.get("inputs")).items()
            if isinstance(value, (int, float)) and not isinstance(value, bool)
        },
    )


def _event_from_data(data: dict[str, Any]) -> DomainEvent:
    location_id = data.get("location_id")
    event = DomainEvent(
        event_type=str(data.get("event_type", "")),
        importance=int(data.get("importance", 0)),
        text=str(data.get("text", "")),
        participants=[str(person) for person in data.get("participants", [])],
        witnesses=[str(person) for person in data.get("witnesses", [])],
        location_id=str(location_id) if location_id is not None else None,
        timestamp=int(data.get("timestamp", 0)),
        data=dict(_object_or_empty(data.get("data"))),
    )
    if "government" in data:
        # A political event says under which government it happened, and stays one.
        return PoliticalEvent(**vars(event), government=_text_or_none(data.get("government")))
    return event


def _attributes_from_data(world: SimulationWorld, data: Any) -> Attributes | None:
    """What a resident is capable of, as it was saved. None for somebody out of a save from
    before, or who was never asked: the seed gives them theirs when they are."""
    if not isinstance(data, dict):
        return None
    settings = world.registries.attributes
    return Attributes(**{name: settings.clamp(float(data.get(name, settings.middle))) for name in OWN})


def _proposal_from_data(data: dict[str, Any]) -> Proposal:
    status = str(data.get("status", PENDING))
    passed = data.get("passed_degree")
    decided = data.get("decided_at")
    return Proposal(
        proposal_id=str(data.get("proposal_id", "")),
        kind=str(data["kind"]),
        by=str(data.get("by", PLAYER)),
        sponsor=_text_or_none(data.get("sponsor")),
        law=_text_or_none(data.get("law")),
        degree=max(0, int(data.get("degree", 0))),
        target=_text_or_none(data.get("target")),
        government=_text_or_none(data.get("government")),
        params={str(key): str(value) for key, value in _object_or_empty(data.get("params")).items()},
        text=str(data.get("text", "")),
        raised_at=int(data.get("raised_at", 0)),
        decides_at=int(data.get("decides_at", 0)),
        lobbied={str(key): float(value) for key, value in _object_or_empty(data.get("lobbied")).items()},
        pushed=bool(data.get("pushed", False)),
        status=status if status in STATUSES else PENDING,
        decided_at=int(decided) if decided is not None else None,
        passed_degree=int(passed) if passed is not None else None,
        ballots=[
            Ballot(
                voter=str(ballot.get("voter", "")),
                vote=str(ballot.get("vote", "")),
                score=float(ballot.get("score", 0.0)),
                reasons=[str(reason) for reason in _list_or_empty(ballot.get("reasons"))],
            )
            for ballot in _list_or_empty(data.get("ballots"))
            if isinstance(ballot, dict) and ballot.get("vote") in VOTES
        ],
        open_ballot=bool(data.get("open_ballot", True)),
        imposed=bool(data.get("imposed", False)),
    )


def _election_from_data(data: dict[str, Any]) -> ElectionRecord:
    return ElectionRecord(
        day=int(data.get("day", 0)),
        at=int(data.get("at", 0)),
        seat=str(data.get("seat", LEADER_SEAT)),
        way=str(data.get("way", "election")),
        candidates=[str(candidate) for candidate in _list_or_empty(data.get("candidates"))],
        tally={str(candidate): int(votes) for candidate, votes in _object_or_empty(data.get("tally")).items()},
        winner=_text_or_none(data.get("winner")),
        backed={str(voter): str(candidate) for voter, candidate in _object_or_empty(data.get("backed")).items()},
        open_ballot=bool(data.get("open_ballot", True)),
        rigged_by=_text_or_none(data.get("rigged_by")),
        claimed_by=[str(loser) for loser in _list_or_empty(data.get("claimed_by"))],
    )


def _memory_from_data(data: dict[str, Any]) -> Memory:
    location_id = data.get("location_id")
    return Memory(
        text=str(data.get("text", "")),
        importance=float(data.get("importance", 0.0)),
        emotional_value=float(data.get("emotional_value", 0.0)),
        people=[str(person) for person in data.get("people", [])],
        tags=[str(tag) for tag in data.get("tags", [])],
        timestamp=int(data.get("timestamp", 0)),
        location_id=str(location_id) if location_id is not None else None,
    )


def _condition_of(saved: dict[str, Any]) -> float:
    """How much is left in a thing that was saved, of a hundred. Whole where it was not said."""
    condition = saved.get("condition", 100.0)
    if isinstance(condition, bool) or not isinstance(condition, (int, float)):
        return 100.0
    return min(100.0, max(0.0, float(condition)))


def _level_of(saved: dict[str, Any]) -> int:
    """How good a thing that was saved is. Common in a save from before things had levels."""
    level = saved.get("level", 1)
    return level if isinstance(level, int) and not isinstance(level, bool) else 1


def _text_or_none(value: Any) -> str | None:
    return str(value) if value is not None else None


def _object_or_empty(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _tile_or_none(value: Any) -> tuple[int, int] | None:
    """A tile as it was saved: two whole numbers. None for anything else."""
    if isinstance(value, list) and len(value) == 2 and all(isinstance(each, int) and not isinstance(each, bool) for each in value):
        return (value[0], value[1])
    return None


def _list_or_empty(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []
