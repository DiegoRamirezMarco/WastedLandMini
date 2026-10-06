import json
from pathlib import Path
from typing import Any

from simulation.clock import SimulationClock
from simulation.events.crisis import Crisis
from simulation.events.decision import Decision, DecisionOption
from simulation.events.event import DomainEvent
from simulation.events.world_event import Upcoming, Weather
from simulation.events.world_event_system import RAID_DECISION, STRANGER_DECISION
from simulation.health.injury import Death, Injury
from simulation.items.inventory import Inventory
from simulation.items.item import ItemInstance
from simulation.items.theft import TheftAttempt
from simulation.knowledge.fact import Belief, Fact
from simulation.memory.memory import Memory
from simulation.registries import DEFAULT_MAP_ID, BuiltInRegistries, builtin_registries
from simulation.residents.activity import Activity
from simulation.residents.needs import Needs
from simulation.residents.personality import Personality
from simulation.residents.resident import FACINGS, Resident
from simulation.rng import SimulationRNG
from simulation.social.relationship import Relationship
from simulation.tastes.settings import REACTIONS
from simulation.tastes.taste import KINDS, Taste, TasteProfile
from simulation.work.expedition import Expedition
from simulation.work.expedition_system import EXPEDITION_ACTION
from simulation.tutorial.tutorial import TutorialState
from simulation.world import SimulationWorld
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
LAST_MAP_CHANGE_VERSION = 16
FIRST_URBANISM_VERSION = 17
FIRST_TILE_VERSION = 2


class SaveManager:
    CURRENT_VERSION = 21

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
            "newcomers_seen": list(world.newcomers_seen),
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
                {"id": placed.object_id, "kind": placed.kind, "x": placed.x, "y": placed.y}
                for placed in world.interactables.values()
            ],
            "residents": [
                {
                    "id": resident.resident_id,
                    "name": resident.name,
                    "x": resident.x,
                    "y": resident.y,
                    "facing": resident.facing,
                    "needs": vars(resident.needs),
                    "personality": vars(resident.personality),
                    "mood": resident.mood,
                    "current_action": resident.current_action,
                    "activity": _activity_to_data(resident.activity),
                    "traits": list(resident.traits),
                    "manners": dict(resident.manners),
                    "job_id": resident.job_id,
                    "post_id": resident.post_id,
                    "work_progress": resident.work_progress,
                    "day_off": resident.day_off,
                    "credits": resident.credits,
                    "age": resident.age,
                    "couple_with": resident.couple_with,
                    "expedition": vars(resident.expedition) if resident.expedition is not None else None,
                    "last_expedition_day": resident.last_expedition_day,
                    "seeks_work": resident.seeks_work,
                    "injuries": [vars(injury) for injury in resident.injuries],
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
            if activity is not None and activity.target_id not in (None, *world.interactables):
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
                ),
                mood=float(resident_data.get("mood", 50.0)),
                current_action=str(resident_data.get("current_action", "idle")),
                facing=facing if facing in FACINGS else "down",
                activity=activity,
                traits=[str(trait) for trait in resident_data.get("traits", [])],
                # A manner that is no longer defined is forgotten: they go by their own by default.
                manners=world.registries.manners.tidy(_object_or_empty(resident_data.get("manners"))),
                job_id=_text_or_none(resident_data.get("job_id")),
                post_id=_text_or_none(resident_data.get("post_id")),
                work_progress=int(resident_data.get("work_progress", 0)),
                day_off=int(day_off) if day_off is not None else None,
                credits=float(resident_data.get("credits", pocket_money)),
                age=int(resident_data.get("age", 30)),
                couple_with=_text_or_none(resident_data.get("couple_with")),
                expedition=Expedition(
                    returns_at=int(trip.get("returns_at", 0)),
                    finds=int(trip.get("finds", 0)),
                    danger=float(trip.get("danger", 0.0)),
                    find_at=int(trip["find_at"]) if trip.get("find_at") is not None else None,
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

        event_log = data.get("event_log", [])
        world.event_log = [str(line) for line in event_log] if isinstance(event_log, list) else []
        self._restore_tutorial(world, data)
        self._restore_tastes(world, data)
        return world

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
        if version < LAST_MAP_CHANGE_VERSION:
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
            )
            for attempt in (thefts if isinstance(thefts, list) else [])
            if isinstance(attempt, dict)
        ]
        world.theft_cooldowns = {
            str(resident_id): int(minute)
            for resident_id, minute in _object_or_empty(data.get("theft_cooldowns")).items()
        }
        world.notices = {str(name): int(day) for name, day in _object_or_empty(data.get("notices")).items()}
        world.vacancies = {
            str(job_id): int(minute)
            for job_id, minute in _object_or_empty(data.get("vacancies")).items()
            if job_id in world.registries.jobs
        }

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
        deciding = any(decision.kind == STRANGER_DECISION for decision in world.decisions.values())
        world.at_the_gate = waiting if waiting in known and deciding else None
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
                str(placed["id"]), str(placed["kind"]), int(placed["x"]), int(placed["y"])
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
        world.containers = {
            object_id: containers_before.get(object_id, Inventory())
            for object_id, placed in world.interactables.items()
            if world.definition_of(placed).container
        }

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
    }


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
    )


def _inventory_to_data(inventory: Inventory) -> list[dict[str, Any]]:
    return [
        {
            "id": item.instance_id,
            "definition_id": item.definition_id,
            "owner_id": item.owner_id,
            "condition": item.condition,
            "quantity": item.quantity,
            "given_by": item.given_by,
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
                given_by=_text_or_none(item.get("given_by")),
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
    )


def _event_from_data(data: dict[str, Any]) -> DomainEvent:
    location_id = data.get("location_id")
    return DomainEvent(
        event_type=str(data.get("event_type", "")),
        importance=int(data.get("importance", 0)),
        text=str(data.get("text", "")),
        participants=[str(person) for person in data.get("participants", [])],
        witnesses=[str(person) for person in data.get("witnesses", [])],
        location_id=str(location_id) if location_id is not None else None,
        timestamp=int(data.get("timestamp", 0)),
        data=dict(_object_or_empty(data.get("data"))),
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


def _text_or_none(value: Any) -> str | None:
    return str(value) if value is not None else None


def _object_or_empty(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _list_or_empty(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []
