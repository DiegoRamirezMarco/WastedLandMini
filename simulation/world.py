from collections.abc import Callable, Collection
from dataclasses import dataclass, field, replace

from simulation.ai.activity_system import ActivitySystem
from simulation.clock import SimulationClock
from simulation.commands import SimulationCommand
from simulation.events.decision import Decision
from simulation.events.event import DomainEvent, euphonic
from simulation.events.event_manager import EventManager
from simulation.economy.trade_system import TradeSystem
from simulation.events.intervention_system import InterventionSystem
from simulation.events.world_event import Upcoming, Weather
from simulation.events.world_event_system import WorldEventSystem
from simulation.health.health_system import HealthSystem
from simulation.health.injury import Death
from simulation.items.inventory import Inventory
from simulation.items.item import ItemInstance
from simulation.items.item_system import ItemSystem
from simulation.items.theft import TheftAttempt
from simulation.knowledge.fact import Fact, KnowledgeStore
from simulation.knowledge.knowledge_system import record_fact, witnesses_of
from simulation.memory.memory_system import MemorySystem
from simulation.registries import DEFAULT_MAP_ID, BuiltInRegistries, builtin_registries
from simulation.residents.personality import Personality
from simulation.residents.resident import Resident
from simulation.rng import SimulationRNG
from simulation.social.bonds import BondSystem
from simulation.social.relationship import Relationship
from simulation.work.expedition_system import ExpeditionSystem
from simulation.work.staffing import StaffingSystem
from simulation.work.work_system import WORK_ACTION, WorkSystem
from world.interactable import Interactable, InteractableDefinition
from world.map import Tile, TileMap
from world.pathfinding import manhattan
from world.visibility import line_of_sight, within_range
from world.room import Room

POWER_ITEM = "fuel"
POWERED_LIGHTS = {"lamp"}
GENERATOR_KIND = "generator"
POWER_OUT_NOTICE = "power_out"
POWER_EVENT_IMPORTANCE = 25


@dataclass
class SimulationWorld:
    residents: dict[str, Resident] = field(default_factory=dict)
    relationships: dict[tuple[str, str], Relationship] = field(default_factory=dict)
    clock: SimulationClock = field(default_factory=SimulationClock)
    rng: SimulationRNG = field(default_factory=lambda: SimulationRNG(7))
    events: EventManager = field(default_factory=EventManager)
    memories: MemorySystem = field(default_factory=MemorySystem)
    knowledge: KnowledgeStore = field(default_factory=KnowledgeStore)
    event_log: list[str] = field(default_factory=list)
    registries: BuiltInRegistries = field(default_factory=BuiltInRegistries)
    map_id: str = ""
    tile_map: TileMap = field(default_factory=lambda: TileMap(0, 0, []))
    rooms: dict[str, Room] = field(default_factory=dict)
    interactables: dict[str, Interactable] = field(default_factory=dict)
    activities: ActivitySystem = field(default_factory=ActivitySystem)
    interventions: InterventionSystem = field(default_factory=InterventionSystem)
    # Open chances for the player to advise a resident, by decision ID.
    decisions: dict[str, Decision] = field(default_factory=dict)
    decision_count: int = 0
    # Game minute of each resident's last crisis.
    crisis_cooldowns: dict[str, int] = field(default_factory=dict)
    # Every noteworthy event so far, oldest first.
    history: list[DomainEvent] = field(default_factory=list)
    items: ItemSystem = field(default_factory=ItemSystem)
    work: WorkSystem = field(default_factory=WorkSystem)
    staffing: StaffingSystem = field(default_factory=StaffingSystem)
    trade: TradeSystem = field(default_factory=TradeSystem)
    bonds: BondSystem = field(default_factory=BondSystem)
    expeditions: ExpeditionSystem = field(default_factory=ExpeditionSystem)
    happenings: WorldEventSystem = field(default_factory=WorldEventSystem)
    # Randomness of what happens to the settlement from outside, kept apart from everything else's.
    event_rng: SimulationRNG = field(default_factory=lambda: SimulationRNG(7007))
    # Day on which each world event last happened, by event ID.
    happened: dict[str, int] = field(default_factory=dict)
    weather: Weather | None = None
    # World events that are on their way, soonest first as they were settled.
    upcoming: list[Upcoming] = field(default_factory=list)
    # ID of the newcomer waiting at the gate for an answer, and of everyone who has come before.
    at_the_gate: str | None = None
    # ID of the raid that is at the gate while whoever is on watch makes up their mind.
    under_raid: str | None = None
    newcomers_seen: list[str] = field(default_factory=list)
    health: HealthSystem = field(default_factory=HealthSystem)
    # Game minute since which each job has been short of people, by job ID.
    vacancies: dict[str, int] = field(default_factory=dict)
    # Everyone who has died, oldest first.
    deaths: list[Death] = field(default_factory=list)
    # Contents of each container object, by object ID.
    containers: dict[str, Inventory] = field(default_factory=dict)
    item_count: int = 0
    thefts: list[TheftAttempt] = field(default_factory=list)
    # Game minute of each resident's last theft.
    theft_cooldowns: dict[str, int] = field(default_factory=dict)
    # Day on which each once-a-day notice was last given.
    notices: dict[str, int] = field(default_factory=dict)

    def step(self, minutes: int | None = None) -> None:
        if self.clock.paused:
            return
        elapsed = minutes if minutes is not None else self.clock.fixed_tick_minutes * self.clock.speed
        if elapsed < 0:
            raise ValueError("minutes must be non-negative")
        for _ in range(elapsed):
            self._tick()

    def _tick(self) -> None:
        self.clock.advance_minutes(1)
        self._power_tick()
        self.interventions.tick(self)
        self.items.tick_world(self)
        self.staffing.tick(self)
        self.happenings.tick(self)
        for resident in list(self.residents.values()):
            # Someone may die during this very minute.
            if resident.resident_id in self.residents:
                self.activities.tick(self, resident)

    def apply_command(self, command: SimulationCommand) -> object:
        return command.apply(self)

    def set_paused(self, paused: bool) -> None:
        self.clock.paused = paused

    def choose_option(self, decision_id: str, option_id: str) -> str | None:
        """Give the player's advice on an open decision. The resident then decides."""
        return self.interventions.resolve(self, decision_id, option_id)

    def suggest_job(self, resident_id: str, job_id: str, option_id: str) -> str | None:
        """Put it to a resident that they take up a job. They weigh it and decide for themselves."""
        return self.interventions.suggest_job(self, resident_id, job_id, option_id)

    def set_speed(self, speed: int) -> None:
        if speed < 1:
            raise ValueError("speed must be at least 1")
        self.clock.speed = speed

    def emit_event(
        self,
        event: DomainEvent,
        at: Tile | None = None,
        fact_text: str | None = None,
        subjects: Collection[str] | None = None,
        expires_at: int | None = None,
    ) -> Fact | None:
        """Announce an event. With `at`, whoever can see that tile witnesses it.
        With `fact_text`, it is recorded as a fact about `subjects` (by default the participants)
        that those present know and can pass on, until `expires_at` if it is news of something to
        come. Returns that fact, if one was recorded."""
        event.timestamp = self.clock.total_minutes
        event.text = euphonic(event.text)
        fact = None
        if at is not None:
            event.witnesses = witnesses_of(self, at, exclude=event.participants)
        if fact_text is not None:
            fact = record_fact(self, event, euphonic(fact_text), subjects, expires_at)
        importance = self.registries.event_settings.get("importance", {})
        if event.importance > int(importance.get("ambient_max", 29)):
            self.history.append(event)
        self.events.emit(event)
        self.event_log.append(f"{self.clock.label} | {event.event_type} | {event.text}")
        return fact

    def new_item(self, definition_id: str, quantity: int = 1, owner_id: str | None = None) -> ItemInstance:
        """Create an item with a fresh stable ID. It is not placed anywhere yet."""
        self.item_count += 1
        return ItemInstance(f"item_{self.item_count}", definition_id, owner_id, quantity=quantity)

    def stock(self, inventory: Inventory, definition_id: str, count: int, owner_id: str | None) -> ItemInstance:
        """Put `count` units in an inventory, on top of a matching stack if there is one."""
        stack = inventory.stack_of(definition_id, owner_id)
        if stack is not None:
            stack.quantity += count
            return stack
        item = self.new_item(definition_id, count, owner_id)
        inventory.add(item)
        return item

    def stock_from_layout(self) -> None:
        """Fill containers as the map says a new settlement starts. Items no longer defined are left out."""
        for entry in self.registries.maps[self.map_id].stock:
            container = self.containers.get(entry.container)
            if container is not None and self.registries.items.find(entry.item) is not None:
                self.stock(container, entry.item, entry.count, entry.owner)

    def relationship(self, source_id: str, target_id: str) -> Relationship:
        key = (source_id, target_id)
        if key not in self.relationships:
            self.relationships[key] = Relationship(source_id, target_id)
        return self.relationships[key]

    def load_layout(self, map_id: str) -> None:
        """Take terrain, rooms and placed objects from a registered map."""
        layout = self.registries.maps[map_id]
        self.map_id = layout.map_id
        self.tile_map = layout.tile_map
        self.rooms = dict(layout.rooms)
        self.interactables = {
            object_id: replace(placed) for object_id, placed in layout.interactables.items()
        }
        self.containers = {
            object_id: Inventory()
            for object_id, placed in self.interactables.items()
            if self.definition_of(placed).container
        }

    def definition_of(self, placed: Interactable) -> InteractableDefinition:
        return self.registries.interactables.get(placed.kind)

    def users_of(self, object_id: str) -> int:
        """How many residents are using this object or on their way to it. Whoever works it does not count."""
        return sum(
            1
            for resident in self.residents.values()
            if resident.activity is not None
            and resident.activity.target_id == object_id
            and resident.activity.action != WORK_ACTION
        )

    def nearest_container(self, tile: Tile) -> str | None:
        """ID of the container closest to a tile, if the settlement has any."""
        placed = [self.interactables[object_id] for object_id in self.containers if object_id in self.interactables]
        if not placed:
            return None
        return min(placed, key=lambda p: (manhattan(tile, (p.x, p.y)), p.object_id)).object_id

    def room_at(self, tile: Tile) -> Room | None:
        return next((room for room in self.rooms.values() if room.contains(tile)), None)

    def is_aware(self, resident: Resident) -> bool:
        """False while a resident is using something that shuts the world out, such as a bed."""
        activity = resident.activity
        if activity is None or not activity.using or activity.target_id is None:
            return True
        placed = self.interactables.get(activity.target_id)
        use = self.definition_of(placed).use if placed is not None else None
        return use is None or not use.unaware

    def is_dark(self) -> bool:
        """Whether it is night enough that only what is close or lit can be seen."""
        hours = self.registries.event_settings.get("perception", {}).get("dark_hours")
        if not hours:
            return False
        start, end = int(hours[0]), int(hours[1])
        hour = self.clock.hour
        return start <= hour < end if start <= end else hour >= start or hour < end

    def is_lit(self, tile: Tile) -> bool:
        """Whether a tile is within reach of something that gives light, with nothing in between."""
        opaque = self.opaque()
        powered = self.has_power()
        for placed in self.interactables.values():
            definition = self.definition_of(placed)
            if definition.light <= 0:
                continue
            if placed.kind in POWERED_LIGHTS and not powered:
                continue
            source = (placed.x, placed.y)
            if within_range(source, tile, definition.light) and line_of_sight(source, tile, opaque):
                return True
        return False

    def power_units(self) -> int:
        """Fuel units in generators that can keep lamps and the radio alive."""
        return sum(
            inventory.count(POWER_ITEM)
            for object_id, inventory in self.containers.items()
            if object_id in self.interactables and self.interactables[object_id].kind == GENERATOR_KIND
        )

    def has_power(self) -> bool:
        return self.power_units() > 0

    def _power_tick(self) -> None:
        """Burn one fuel when the lamps come on for the night."""
        hours = self.registries.event_settings.get("perception", {}).get("dark_hours")
        dark_start = int(hours[0]) if hours else None
        if self.clock.minute != 0 or self.clock.hour != dark_start:
            return
        generator = next(
            (
                inventory
                for object_id, inventory in self.containers.items()
                if object_id in self.interactables and self.interactables[object_id].kind == GENERATOR_KIND
            ),
            None,
        )
        stack = generator.stack_of(POWER_ITEM, None) if generator is not None else None
        if stack is None:
            if self.notices.get(POWER_OUT_NOTICE) != self.clock.day:
                self.notices[POWER_OUT_NOTICE] = self.clock.day
                self.emit_event(DomainEvent("power_failed", POWER_EVENT_IMPORTANCE, "El generador se queda sin combustible"))
            return
        generator.take_unit(stack.instance_id)

    def under_roof(self, tile: Tile) -> bool:
        room = self.room_at(tile)
        return room is not None and room.roofed

    def opaque(self) -> Callable[[Tile], bool]:
        """Return a test for tiles that block line of sight. Outside the map counts as opaque."""
        terrain = self.registries.terrain
        tile_map = self.tile_map

        def is_opaque(tile: Tile) -> bool:
            if not tile_map.in_bounds(tile):
                return True
            definition = terrain.get(tile_map.terrain_at(tile))
            return definition is not None and definition.opaque

        return is_opaque

    def passable(self, also: Collection[Tile] = ()) -> Callable[[Tile], bool]:
        """Return a walkability test for the current map and objects.

        Tiles in `also` count as walkable even if an object stands on them.
        """
        blocked = {
            tile
            for placed in self.interactables.values()
            if self.definition_of(placed).blocks
            for tile in placed.footprint(self.definition_of(placed))
        } - set(also)
        terrain = self.registries.terrain
        tile_map = self.tile_map

        def is_passable(tile: Tile) -> bool:
            if not tile_map.in_bounds(tile) or tile in blocked:
                return False
            definition = terrain.get(tile_map.terrain_at(tile))
            return definition is not None and definition.walkable

        return is_passable

    @classmethod
    def demo_world(cls, seed: int = 7, registries: BuiltInRegistries | None = None) -> "SimulationWorld":
        world = cls(
            rng=SimulationRNG(seed),
            event_rng=SimulationRNG(seed * 7919 + 13),
            registries=registries or builtin_registries(),
        )
        world.load_layout(DEFAULT_MAP_ID)
        world.stock_from_layout()
        residents = [
            Resident("marta", "Marta", personality=Personality(empathy=75, sociability=65), traits=["music_lover"]),
            Resident("raul", "Raúl", personality=Personality(aggression=72, impulsiveness=68)),
            Resident("lucia", "Lucía", personality=Personality(empathy=60, greed=25), traits=["sweet_tooth"]),
            Resident("tomas", "Tomás", personality=Personality(courage=75, sociability=35, aggression=55)),
            Resident("ines", "Inés", personality=Personality(empathy=65, sociability=60, greed=40)),
            Resident("vera", "Vera", personality=Personality(empathy=80, sociability=55, courage=60)),
            Resident("paco", "Paco", personality=Personality(empathy=45, sociability=45, impulsiveness=40)),
            Resident("nuria", "Nuria", personality=Personality(empathy=55, sociability=70, greed=65)),
            Resident("sergio", "Sergio", personality=Personality(courage=70, greed=60, impulsiveness=55)),
        ]
        # Who works where, and the day of the week each has off. Marta cooks what Raúl and Inés
        # grow, which is where their quarrel comes from.
        posts = {
            "marta": ("cook", "cooking_pot", 6),
            "raul": ("farmer", "crop_1", 3),
            "lucia": ("bartender", "bar", 1),
            "tomas": ("guard", "guard_post", 2),
            "ines": ("farmer", "crop_5", 5),
            "vera": ("medic", "medicine_cabinet", 4),
            "paco": ("mechanic", "workbench", 2),
            "nuria": ("shopkeeper", "shop_counter", 4),
            "sergio": ("scavenger", "handcart", 5),
        }
        ages = {
            "marta": 41, "raul": 38, "lucia": 27, "tomas": 45, "ines": 33, "vera": 52, "paco": 36, "nuria": 29,
            "sergio": 31,
        }
        for resident in residents:
            resident.age = ages[resident.resident_id]
            job_id, post_id, day_off = posts[resident.resident_id]
            resident.credits = world.registries.economy.starting_credits
            if job_id in world.registries.jobs and post_id in world.interactables:
                resident.job_id, resident.post_id, resident.day_off = job_id, post_id, day_off
        spawns = world.registries.maps[world.map_id].spawns
        for index, resident in enumerate(residents):
            resident.x, resident.y = spawns[index % len(spawns)]
            world.residents[resident.resident_id] = resident
        # The opening situation: Marta and Raúl are at odds over the provisions, and it is getting to him.
        world.relationship("marta", "raul").resentment = 35
        world.relationship("raul", "marta").affection = 15
        world.relationship("raul", "marta").resentment = 50
        world.residents["raul"].needs.stress = 45
        # Tomás and Inés share the south house and get on. There is something more there, unsaid.
        for one, other in (("tomas", "ines"), ("ines", "tomas")):
            world.relationship(one, other).affection = 30
            world.relationship(one, other).attraction = 38
        # Belongings: Marta's radio and Raúl's stash sit in crates; Lucía carries her toy.
        for container_id, item_id, count, owner_id in (
            ("crate_dorm", "old_radio", 1, "marta"),
            ("crate_1", "canned_beans", 2, "raul"),
        ):
            if container_id in world.containers and world.registries.items.find(item_id) is not None:
                world.stock(world.containers[container_id], item_id, count, owner_id)
        if world.registries.items.find("peluche_maligno") is not None:
            world.stock(world.residents["lucia"].inventory, "peluche_maligno", 1, "lucia")
        if world.registries.items.find("baton") is not None:
            # The guard carries a truncheon. It makes him dangerous in a fight.
            world.stock(world.residents["tomas"].inventory, "baton", 1, "tomas")
        if world.registries.items.find("hoe") is not None:
            # Each of the two who work the garden has a hoe of their own.
            for farmer_id in ("raul", "ines"):
                world.stock(world.residents[farmer_id].inventory, "hoe", 1, farmer_id)
        return world
