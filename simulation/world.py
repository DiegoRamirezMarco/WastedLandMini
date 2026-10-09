from collections.abc import Callable, Collection, Mapping, Sequence
from dataclasses import dataclass, field, replace

from simulation.ai.activity_system import ActivitySystem
from simulation.ai.affect import AffectOption, AffectResult, AffectSystem, QueuedOrder
from simulation.ai.leisure import LeisureSystem
from simulation.ai.placing import Placement, PlaceResult, PlacingSystem
from simulation.clock import SimulationClock
from simulation.commands import SimulationCommand
from simulation.events.decision import Decision
from simulation.events.event import DomainEvent, euphonic
from simulation.events.event_manager import EventManager
from simulation.economy.fund_system import FundSystem
from simulation.economy.power import PowerResult, PowerSystem
from simulation.economy.spoilage import FRESH, SpoilResult, SpoilSystem
from simulation.economy.stores import StoreSystem
from simulation.economy.ledger import LedgerState, LedgerSystem
from simulation.economy.lending import LendingSystem
from simulation.economy.merchant import Merchant, MerchantSystem
from simulation.economy.terms import Debt, TradeResult, TradingState
from simulation.economy.terms_system import TermsSystem
from simulation.economy.trade_system import TradeSystem
from simulation.events.intervention_system import InterventionSystem
from simulation.events.world_event import Upcoming, Weather
from simulation.events.world_event_system import WorldEventSystem
from simulation.family.children import Bundle, ChildSystem
from simulation.family.family_system import SLEEP_ROUGH_ACTION, FamilySystem
from simulation.family.kin import KinRecord
from simulation.health.health_system import HealthSystem
from simulation.health.injury import Death
from simulation.items.inventory import Inventory
from simulation.items.item import ItemInstance
from simulation.items.giving import GiveResult, GiveSystem
from simulation.items.item_system import ItemSystem
from simulation.items.theft import TheftAttempt
from simulation.knowledge.fact import Fact, KnowledgeStore
from simulation.knowledge.knowledge_system import record_fact, witnesses_of
from simulation.memory.memory_system import MemorySystem
from simulation.justice.justice_system import JusticeResult, JusticeSystem
from simulation.justice.records import JusticeState
from simulation.politics.government import GovernmentState, PoliticsResult
from simulation.politics.politics_system import PoliticsSystem
from simulation.politics.profile import PoliticalProfile
from simulation.politics.records import Exile, PlayerStanding
from simulation.registries import DEFAULT_MAP_ID, BuiltInRegistries, builtin_registries
from simulation.residents.attribute_system import AttributeSystem
from simulation.residents.founding import found_resident
from simulation.residents.manner import MannerDefinition
from simulation.residents.attributes import Attributes
from simulation.residents.personality import Personality
from simulation.residents.resident import Resident
from simulation.residents.wishes import Wish, WishSystem
from simulation.rng import SimulationRNG
from simulation.social.bonds import BondSystem
from simulation.substances.substance_system import SubstanceSystem
from simulation.social.relationship import Relationship
from simulation.social.talk import TalkResult, TalkSystem, VocabularyState
from simulation.tastes.knowledge import TasteKnowledge
from simulation.tastes.taste import TasteProfile
from simulation.tastes.taste_system import TasteSystem
from simulation.housing.decor import DecorSystem
from simulation.housing.housing import HousingResult, HousingState, HousingSystem
from simulation.tutorial.tutorial import TutorialState
from simulation.tutorial.tutorial_system import TutorialSystem
from simulation.work.craft import CraftResult, Discovery
from simulation.work.craft_system import CraftSystem
from simulation.work.finds import FindSystem
from simulation.work.construction import ConstructionSystem
from simulation.work.upgrades import NOBODY_KEEPS, UpgradeSystem
from simulation.work.wear import WearSystem
from simulation.work.expedition_system import ExpeditionSystem
from simulation.work.research import ResearchResult, ResearchState, ResearchSystem
from simulation.work.rush import RushSystem
from simulation.work.salvage import Salvage, SalvageSystem
from simulation.work.staffing import StaffingSystem
from simulation.work.work_system import WORK_ACTION, WorkSystem
from world.build import BUILDING_SITE, OBJECT_SITE, UPGRADE_SITE, BuildSite
from world.interactable import Interactable, InteractableDefinition
from world.map import Tile, TileMap
from world.pathfinding import manhattan
from world.visibility import line_of_sight, within_range
from world.room import Room
from world.urbanism import UrbanismResult, UrbanismSystem

POWER_ITEM = "fuel"


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
    attributes: AttributeSystem = field(default_factory=AttributeSystem)
    crafts: CraftSystem = field(default_factory=CraftSystem)
    # What each resident wants right now, if anything, by resident ID (S61).
    wishes: WishSystem = field(default_factory=WishSystem)
    wishes_of: dict[str, Wish] = field(default_factory=dict)
    # What turns up that nobody knows, and things put in somebody's hands by the player (S59).
    finds: FindSystem = field(default_factory=FindSystem)
    giving: GiveSystem = field(default_factory=GiveSystem)
    # What residents have come to at their jobs, by discovery ID: named by the player, or waiting to be.
    discoveries: dict[str, Discovery] = field(default_factory=dict)
    discovery_count: int = 0
    interventions: InterventionSystem = field(default_factory=InterventionSystem)
    affect: AffectSystem = field(default_factory=AffectSystem)
    placing: PlacingSystem = field(default_factory=PlacingSystem)
    leisure: LeisureSystem = field(default_factory=LeisureSystem)
    # Open chances for the player to advise a resident, by decision ID.
    decisions: dict[str, Decision] = field(default_factory=dict)
    decision_count: int = 0
    # Game minute of each resident's last crisis.
    crisis_cooldowns: dict[str, int] = field(default_factory=dict)
    # Every noteworthy event so far, oldest first.
    history: list[DomainEvent] = field(default_factory=list)
    items: ItemSystem = field(default_factory=ItemSystem)
    work: WorkSystem = field(default_factory=WorkSystem)
    rush: RushSystem = field(default_factory=RushSystem)
    staffing: StaffingSystem = field(default_factory=StaffingSystem)
    trade: TradeSystem = field(default_factory=TradeSystem)
    fund: FundSystem = field(default_factory=FundSystem)
    terms: TermsSystem = field(default_factory=TermsSystem)
    merchants: MerchantSystem = field(default_factory=MerchantSystem)
    # How the settlement trades, and what it holds in coin as a whole. A new one trades by barter.
    trading: TradingState = field(default_factory=TradingState)
    # What comes into what the settlement lives on and what goes out of it, as it is written down.
    ledger: LedgerSystem = field(default_factory=LedgerSystem)
    # The stores what is everybody's is kept in, and the places it is taken from (S53).
    stores: StoreSystem = field(default_factory=StoreSystem)
    # Current: what gives it, what draws it and what stops without it (S55). And the part of
    # a unit of fuel that has been burnt since the last whole one.
    power: PowerSystem = field(default_factory=PowerSystem)
    power_burnt: float = 0.0
    # What goes off, and what is left of it (S65). And the beds that have compost on them,
    # each with the game minute it lasts until.
    spoilage: SpoilSystem = field(default_factory=SpoilSystem)
    dressed: dict[str, int] = field(default_factory=dict)
    accounts: LedgerState = field(default_factory=LedgerState)
    # Whoever has stopped by the gate to trade, while they are there.
    merchant: Merchant | None = None
    lending: LendingSystem = field(default_factory=LendingSystem)
    substances: SubstanceSystem = field(default_factory=SubstanceSystem)
    family: FamilySystem = field(default_factory=FamilySystem)
    children: ChildSystem = field(default_factory=ChildSystem)
    politics: PoliticsSystem = field(default_factory=PoliticsSystem)
    justice: JusticeSystem = field(default_factory=JusticeSystem)
    # The government the settlement has: none until it has grown enough to choose one.
    government: GovernmentState = field(default_factory=GovernmentState)
    # What each resident holds about how the settlement is run, by resident ID. Kept apart from the resident.
    political_profiles: dict[str, PoliticalProfile] = field(default_factory=dict)
    # What the player is to each resident, by resident ID: how far they trust them, and how
    # much they resist being pushed.
    player_standing: dict[str, PlayerStanding] = field(default_factory=dict)
    # Whoever has been thrown out and is on their way to the gate: the game minute by which
    # they are gone, by resident ID. And everyone who has been thrown out, oldest first.
    leaving: dict[str, int] = field(default_factory=dict)
    exiled: list[Exile] = field(default_factory=list)
    # The trials there have been, the sentences being served and the punishments carried out.
    courts: JusticeState = field(default_factory=JusticeState)
    # Children under ten, by ID: carried and seen to by somebody until they walk.
    bundles: dict[str, Bundle] = field(default_factory=dict)
    # What residents have lent one another and not had back yet.
    debts: list[Debt] = field(default_factory=list)
    # Units of what was bought for the settlement that wait at the gate to be carried in, by item ID.
    at_gate: dict[str, int] = field(default_factory=dict)
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
    # Everyone waiting at the gate together, when they are more than one.
    gate_party: list[str] = field(default_factory=list)
    # Who is kin to whom, by person ID: the living, the dead and those who never came in.
    kinship: dict[str, KinRecord] = field(default_factory=dict)
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
    urbanism: UrbanismSystem = field(default_factory=UrbanismSystem)
    construction: ConstructionSystem = field(default_factory=ConstructionSystem)
    # How good what stands is, and the making of it better (S54).
    upgrades: UpgradeSystem = field(default_factory=UpgradeSystem)
    # Posts that wear, break down and are mended (S55).
    wear: WearSystem = field(default_factory=WearSystem)
    # Ground marked out for what somebody has agreed to put up, by site ID.
    sites: dict[str, BuildSite] = field(default_factory=dict)
    site_count: int = 0
    salvaging: SalvageSystem = field(default_factory=SalvageSystem)
    # What somebody has been told to take apart, by the ID of the object.
    salvage: dict[str, Salvage] = field(default_factory=dict)
    research: ResearchSystem = field(default_factory=ResearchSystem)
    # What the settlement knows, and what it is working out.
    studies: ResearchState = field(default_factory=ResearchState)
    tastes: TasteSystem = field(default_factory=TasteSystem)
    # What is talked of, and the words the player has given for it: the lists, each
    # resident's phrases, what one calls another, and what they are waiting to be told (S58).
    talk: TalkSystem = field(default_factory=TalkSystem)
    words: VocabularyState = field(default_factory=VocabularyState)
    # What each resident likes and loathes, by resident ID. Kept apart from the resident.
    taste_profiles: dict[str, TasteProfile] = field(default_factory=dict)
    # What the player and each resident have found out of anyone's tastes.
    taste_knowledge: TasteKnowledge = field(default_factory=TasteKnowledge)
    guide: TutorialSystem = field(default_factory=TutorialSystem)
    # Where a new settlement is in its opening. One that is past it, or never had one, has no step.
    tutorial: TutorialState = field(default_factory=TutorialState)
    # Whose each building is, and what has been put in it to be looked at.
    housing: HousingSystem = field(default_factory=HousingSystem)
    homes: HousingState = field(default_factory=HousingState)
    decor: DecorSystem = field(default_factory=DecorSystem)

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
        # Before anything else happens this minute: a day that has ended is counted as it ended.
        self.ledger.tick(self)
        self.stores.tick(self)
        self.power.tick(self)
        self.spoilage.tick(self)
        self.interventions.tick(self)
        self.items.tick_world(self)
        self.staffing.tick(self)
        self.construction.tick(self)
        self.wear.tick(self)
        self.research.tick(self)
        self.crafts.tick(self)
        self.happenings.tick(self)
        self.lending.tick(self)
        self.family.tick(self)
        self.politics.tick(self)
        if self.clock.hour == 0 and self.clock.minute == 0:
            self.attributes.tick_day(self)
        self.justice.tick(self)
        self.talk.tick(self)
        self.wishes.tick(self)
        self.housing.tick(self)
        self.activities.begin_minute(self)
        for resident in list(self.residents.values()):
            # Someone may die during this very minute.
            if resident.resident_id in self.residents:
                self.activities.tick(self, resident)
        # Once everybody has moved: a bundle is wherever whoever carries it has got to.
        self.children.tick(self)
        self.guide.check(self)

    def apply_command(self, command: SimulationCommand) -> object:
        result = command.apply(self)
        # What the player has just done may be what the opening was waiting for, even with time stopped.
        self.guide.check(self)
        return result

    def set_paused(self, paused: bool) -> None:
        self.clock.paused = paused

    def choose_option(self, decision_id: str, option_id: str) -> str | None:
        """Give the player's advice on an open decision. The resident then decides."""
        return self.interventions.resolve(self, decision_id, option_id)

    def suggest_job(self, resident_id: str, job_id: str, option_id: str) -> str | None:
        """Put it to a resident that they take up a job. They weigh it and decide for themselves."""
        return self.interventions.suggest_job(self, resident_id, job_id, option_id)

    def place_object(self, kind: str, tile: Tile) -> UrbanismResult:
        """Put an object down at once, which only what takes nothing to build can be."""
        return self.construction.place(self, OBJECT_SITE, kind, tile)

    def move_object(self, object_id: str, tile: Tile) -> UrbanismResult:
        return self.urbanism.move_object(self, object_id, tile)

    def remove_object(self, object_id: str) -> UrbanismResult:
        return self.urbanism.remove_object(self, object_id)

    def place_building(self, blueprint_id: str, tile: Tile) -> UrbanismResult:
        """Put a building down at once, which only what takes nothing to build can be."""
        return self.construction.place(self, BUILDING_SITE, blueprint_id, tile)

    def propose_object(self, kind: str, tile: Tile, resident_id: str, option_id: str) -> UrbanismResult:
        """Put it to a resident that they put an object up. They weigh it and decide for themselves."""
        return self.construction.propose(self, OBJECT_SITE, kind, tile, resident_id, option_id)

    def propose_upgrade(self, object_id: str, resident_id: str | None, option_id: str) -> UrbanismResult:
        """Put it to a resident that they make something that stands better. They weigh it
        and decide for themselves, as with anything that is built. With nobody named it
        is put to whoever keeps the thing (P60)."""
        placed = self.interactables.get(object_id)
        if resident_id is None:
            error = self.upgrades.obstacle(self, object_id)
            keeper = self.upgrades.keeper(self, object_id)
            if error is not None or keeper is None:
                return UrbanismResult(False, error or NOBODY_KEEPS)
            resident_id = keeper.resident_id
        tile = (placed.x, placed.y) if placed is not None else (0, 0)
        return self.construction.propose(self, UPGRADE_SITE, object_id, tile, resident_id, option_id)

    def propose_building(self, blueprint_id: str, tile: Tile, resident_id: str, option_id: str) -> UrbanismResult:
        """Put it to a resident that they put a building up. They weigh it and decide for themselves."""
        return self.construction.propose(self, BUILDING_SITE, blueprint_id, tile, resident_id, option_id)

    def cancel_site(self, site_id: str) -> UrbanismResult:
        return self.construction.cancel(self, site_id)

    def hold_resident(self, resident_id: str) -> AffectResult:
        """Stop a resident, who stands and listens for what the player has to say."""
        return self.affect.hold(self, resident_id)

    def release_resident(self, resident_id: str) -> bool:
        """Let a resident who was stopped go about their day with nothing said."""
        return self.affect.release(self, resident_id)

    def affect_options(self, resident_id: str) -> list[AffectOption]:
        """What a resident can be told right now."""
        return self.affect.options(self, resident_id)

    def affect_resident(self, resident_id: str, kind: str, target_id: str | None) -> AffectResult:
        """Tell a resident to do something. It is an order: they do it, as far as it can be
        done, at once or when what they were told before it is done."""
        return self.affect.order(self, resident_id, kind, target_id)

    def placements(
        self,
        resident_id: str,
        object_id: str | None = None,
        other_id: str | None = None,
        site_id: str | None = None,
        tile: Tile | None = None,
    ) -> list[Placement]:
        """What would come of putting a resident down on a thing, on somebody, on a site or
        on a tile, the likeliest first. It changes nothing."""
        return self.placing.options(
            self, resident_id, object_id=object_id, other_id=other_id, site_id=site_id, tile=tile
        )

    def put_down(
        self,
        resident_id: str,
        object_id: str | None = None,
        other_id: str | None = None,
        site_id: str | None = None,
        tile: Tile | None = None,
        do: str | None = None,
    ) -> PlaceResult:
        """Take a resident up and put them down somewhere else. They are there at once, and
        set about what they were put down on, as an order."""
        return self.placing.put(
            self, resident_id, object_id=object_id, other_id=other_id, site_id=site_id, tile=tile, do=do
        )

    def bundle_placements(
        self, child_id: str, other_id: str | None = None, object_id: str | None = None, tile: Tile | None = None
    ) -> list[Placement]:
        """What would come of putting a child's bundle down on somebody, on a thing or on a tile."""
        return self.placing.bundle_options(self, child_id, other_id=other_id, object_id=object_id, tile=tile)

    def put_bundle(
        self, child_id: str, other_id: str | None = None, object_id: str | None = None, tile: Tile | None = None
    ) -> PlaceResult:
        """Put a child's bundle in the arms of somebody, or lay it down where it stays."""
        return self.placing.put_bundle(self, child_id, other_id=other_id, object_id=object_id, tile=tile)

    def affect_people(self, resident_id: str) -> tuple[tuple[str, str], ...]:
        """Everybody a resident could be told to do something with right now, the nearest first."""
        return self.affect.people(self, resident_id)

    def affect_with(self, resident_id: str, other_id: str) -> list[AffectOption]:
        """What a resident can be told to do with one person, by what they feel for them."""
        return self.affect.with_whom(self, resident_id, other_id)

    def orders_of(self, resident_id: str) -> list[QueuedOrder]:
        """What a resident has been told to do and has not done, what they are at first."""
        return self.affect.queue(self, resident_id)

    def cancel_order(self, resident_id: str, index: int) -> AffectResult:
        """Take back one of the things a resident has been told to do, counted as `orders_of` gives them."""
        return self.affect.cancel(self, resident_id, index)

    def switch(self, object_id: str, on: bool) -> PowerResult:
        """Switch something that runs on current on or off."""
        return self.power.switch(self, object_id, on)

    def compost(self, object_id: str) -> SpoilResult:
        """Put compost on a bed of the garden, which gives more for some days (S65)."""
        return self.spoilage.dress(self, object_id)

    def add_word(self, list_id: str, text: str) -> TalkResult:
        """Put a word in one of the settlement's lists (S58)."""
        return self.talk.add_word(self, list_id, text)

    def set_phrase(self, resident_id: str, phrase_id: str, text: str) -> TalkResult:
        """Give a resident one of their own phrases, or with nothing take it back."""
        return self.talk.set_phrase(self, resident_id, phrase_id, text)

    def set_nickname(self, resident_id: str, other_id: str, text: str) -> TalkResult:
        """Say what one resident calls another, or with nothing that it is their name."""
        return self.talk.set_nickname(self, resident_id, other_id, text)

    def answer_ask(self, ask_id: str, text: str = "", subject: str | None = None, list_id: str | None = None) -> TalkResult:
        """Give a resident the word, the phrase, the name or the subject they asked for."""
        return self.talk.answer(self, ask_id, text, subject, list_id)

    def dismiss_ask(self, ask_id: str) -> TalkResult:
        """Leave what a resident asked for unanswered."""
        return self.talk.dismiss(self, ask_id)

    def talk_about(
        self, resident_id: str, other_id: str, subject: str | None = None, text: str = "", list_id: str | None = None
    ) -> TalkResult:
        """Tell a resident what to talk about with somebody: a subject there is, or a new word."""
        return self.talk.talk_about(self, resident_id, other_id, subject, text, list_id)

    def set_free_will(self, resident_id: str, free: bool) -> AffectResult:
        """Say whether a resident does anything of their own accord, or only what they are told."""
        return self.affect.set_will(self, resident_id, free)

    def order_salvage(self, resident_id: str, object_id: str) -> UrbanismResult:
        """Tell a resident to take something apart for what it is made of. It is their task until it is done."""
        return self.salvaging.order(self, resident_id, object_id)

    def scrap_item(self, item_id: str, option_id: str) -> UrbanismResult:
        """Have an item broken up for scrap: at once if it is nobody's, and if its owner agrees otherwise."""
        return self.salvaging.scrap_item(self, item_id, option_id)

    def set_research(self, subject_id: str | None) -> ResearchResult:
        """Say what is to be worked out next. Whoever holds the post for it works on that."""
        return self.research.choose(self, subject_id)

    def propose_currency(self, name: str, singular: str | None, option_id: str) -> TradeResult:
        """Put it to the residents that they trade with a currency the player has made. They settle it."""
        return self.terms.propose_currency(self, name, singular, option_id)

    def propose_barter(self, option_id: str) -> TradeResult:
        """Put it to the residents that they go back to trading a thing for a thing. They settle it."""
        return self.terms.propose_barter(self, option_id)

    def rename_currency(self, name: str, singular: str | None) -> TradeResult:
        """Give the currency the settlement has the name the player wants for it."""
        return self.terms.rename(self, name, singular)

    def deal_with_merchant(self, sell: Mapping[str, int], buy: Mapping[str, int]) -> TradeResult:
        """Sell whoever has stopped to trade what belongs to nobody, and buy from them, out of the fund and into it."""
        return self.merchants.deal(self, sell, buy)

    def propose_sale(self, resident_id: str, item_id: str, for_item: str | None, option_id: str) -> TradeResult:
        """Put it to a resident that they sell a thing of their own to whoever has stopped to trade."""
        return self.merchants.propose_sale(self, resident_id, item_id, for_item, option_id)

    def move_building(self, room_id: str, tile: Tile) -> UrbanismResult:
        return self.urbanism.move_building(self, room_id, tile)

    def remove_building(self, room_id: str) -> UrbanismResult:
        return self.urbanism.remove_building(self, room_id)

    def found_resident(
        self,
        name: str,
        age: int,
        personality: Mapping[str, float],
        traits: Sequence[str],
        manners: Mapping[str, str] | None = None,
        identity: Mapping[str, str] | None = None,
        attributes: Mapping[str, float] | None = None,
    ) -> str | None:
        """Take in the player's first resident. Returns their ID, or None if there is already someone."""
        resident = found_resident(self, name, age, personality, traits, manners, identity, attributes)
        return resident.resident_id if resident is not None else None

    def give(self, resident_id: str, definition_id: str) -> GiveResult:
        """Put in a resident's hands a unit of a thing that is everybody's (S59)."""
        return self.giving.give(self, resident_id, definition_id)

    def name_discovery(self, discovery_id: str, name: str, choices: Mapping[str, str] | None = None) -> CraftResult:
        """Say what something a resident has come to at their job is called, and what is picked of it."""
        return self.crafts.name(self, discovery_id, name, choices)

    def accuse(self, accused_id: str, fact_id: str | None = None) -> JusticeResult:
        """Have a resident tried for something that is known of them. Those who decide judge."""
        return self.justice.accuse(self, accused_id, fact_id)

    def sentence(self, trial_id: str, punishment_id: str) -> JusticeResult:
        """Say what somebody found guilty is given, out of what the settlement has a place for."""
        return self.justice.sentence(self, trial_id, punishment_id)

    def set_prison_ration(self, meals: int, drinks: int, food: str = "", drink: str = "") -> JusticeResult:
        """Say how much a prisoner is given to eat and to drink each day, and of what."""
        return self.justice.set_ration(self, meals, drinks, food, drink)

    def propose_government(self, government_id: str) -> PoliticsResult:
        """Put a kind of government to everyone, while the settlement is choosing one. They settle it."""
        return self.politics.propose_government(self, government_id)

    def choose_government(self, government_id: str) -> PoliticsResult:
        """Give the settlement a kind of government, while it is choosing one or in place of the one it has."""
        return self.politics.choose_government(self, government_id)

    def propose(
        self,
        kind: str,
        law: str | None = None,
        degree: int | None = None,
        target: str | None = None,
        government: str | None = None,
        params: Mapping[str, str] | None = None,
    ) -> PoliticsResult:
        """Put something to the settlement. Whoever may propose has to make it theirs, and
        those who decide, decide: nothing of it is done unless it passes."""
        return self.politics.propose(self, kind, law, degree, target, government, params)

    def lobby(self, proposal_id: str, resident_id: str, stance: str) -> PoliticsResult:
        """Speak to one of those who will decide a proposal, for it or against it. They vote as they see fit."""
        return self.politics.lobby(self, proposal_id, resident_id, stance)

    def back_candidate(self, resident_id: str, candidate_id: str) -> PoliticsResult:
        """Speak to a resident for one of those who stand in the vote that has been called."""
        return self.politics.back_candidate(self, resident_id, candidate_id)

    def set_identity(self, resident_id: str, sex: str, gender: str, drawn_to: str) -> bool:
        """Say what a resident's sex and gender are and who they are drawn to."""
        return self.family.set_identity(self, resident_id, sex, gender, drawn_to)

    def manner_of(self, resident: Resident, kind_id: str) -> MannerDefinition | None:
        """How a resident does one kind of thing: as was chosen for them, or else in their own way."""
        return self.registries.manners.of(resident.resident_id, resident.manners, kind_id)

    def set_manner(self, resident_id: str, kind_id: str, manner_id: str) -> bool:
        """Give a resident a manner for its kind. Returns whether there was such a resident and such a manner."""
        resident = self.residents.get(resident_id)
        manner = self.registries.manners.manners.get(manner_id)
        if resident is None or manner is None or manner.kind != kind_id:
            return False
        resident.manners[kind_id] = manner_id
        return True

    def give_house(self, room_id: str, owners: list[str]) -> HousingResult:
        """Say who a building belongs to. Nobody makes it the settlement's."""
        return self.housing.give(self, room_id, owners)

    def decorate(self, room_id: str, kind: str, x: int, y: int) -> HousingResult:
        """Put an ornament in a building, at a cell of its floor or a stretch of its back wall."""
        return self.decor.place(self, room_id, kind, x, y)

    def undecorate(self, room_id: str, ornament_id: str) -> HousingResult:
        return self.decor.remove(self, room_id, ornament_id)

    def surface_building(self, room_id: str, floor: str | None = None, wall: str | None = None) -> HousingResult:
        """Say what the floor of a building is made of, its walls, or both."""
        return self.decor.surface(self, room_id, floor, wall)

    def lock_house(self, room_id: str, locked: bool) -> HousingResult:
        """Lock the door of a building that is somebody's, or leave it open again."""
        return self.housing.lock(self, room_id, locked)

    def name_building(self, room_id: str, name: str | None = None, use: str | None = None) -> HousingResult:
        """Give a building a name of its own, say what it is for, or both."""
        return self.housing.name(self, room_id, name, use)

    def acknowledge_tutorial(self) -> bool:
        return self.guide.acknowledge(self)

    def report_deed(self, deed: str) -> bool:
        return self.guide.report(self, deed)

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
            self.family.witnessed(self, event)
        self.children.seen(self, event)
        if fact_text is not None:
            fact = record_fact(self, event, euphonic(fact_text), subjects, expires_at)
        importance = self.registries.event_settings.get("importance", {})
        if event.importance > int(importance.get("ambient_max", 29)):
            self.history.append(event)
        self.events.emit(event)
        self.event_log.append(f"{self.clock.label} | {event.event_type} | {event.text}")
        return fact

    def new_item(
        self,
        definition_id: str,
        quantity: int = 1,
        owner_id: str | None = None,
        level: int = 1,
        freshness: float = FRESH,
    ) -> ItemInstance:
        """Create an item with a fresh stable ID, as rare as `level` says and, for what goes
        off, as fresh as `freshness` says. It is not placed anywhere yet."""
        self.item_count += 1
        return ItemInstance(
            f"item_{self.item_count}", definition_id, owner_id, quantity=quantity, level=level, freshness=freshness
        )

    def stock(
        self,
        inventory: Inventory,
        definition_id: str,
        count: int,
        owner_id: str | None,
        level: int = 1,
        freshness: float | None = None,
    ) -> ItemInstance:
        """Put `count` units in an inventory, on top of a matching stack if there is one:
        one of the same rarity, which is common unless `level` says otherwise (S64).

        What goes off (S65) comes as fresh as `freshness` says, and quite fresh if it says
        nothing. It goes on a stack that is about as fresh, which is then as fresh as the
        two together, or else is a stack of its own."""
        if self.spoilage.goes_off(self, definition_id):
            coming = FRESH if freshness is None else freshness
            stack = self.spoilage.stack_for(self, inventory, definition_id, owner_id, level, coming)
            if stack is not None:
                self.spoilage.put_on(stack, count, coming)
                return stack
            item = self.new_item(definition_id, count, owner_id, level, coming)
            inventory.add(item)
            return item
        stack = inventory.stack_of(definition_id, owner_id, level)
        if stack is not None:
            stack.quantity += count
            return stack
        item = self.new_item(definition_id, count, owner_id, level)
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
        # Layout definitions are shared by worlds; live urbanism must never mutate the registry.
        self.tile_map = TileMap(
            layout.tile_map.width,
            layout.tile_map.height,
            [list(row) for row in layout.tile_map.tiles],
        )
        self.rooms = {room_id: replace(room) for room_id, room in layout.rooms.items()}
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

    def entry_tiles(self) -> list[Tile]:
        """Where people come in and first stand: what everything in the settlement has to be reachable from."""
        layout = self.registries.maps.get(self.map_id)
        return [*layout.arrivals, *layout.spawns] if layout is not None else []

    def room_at(self, tile: Tile) -> Room | None:
        return next((room for room in self.rooms.values() if room.contains(tile)), None)

    def is_aware(self, resident: Resident) -> bool:
        """False while a resident is using something that shuts the world out, such as a bed,
        or is under something that does."""
        if resident.under and self.substances.out_of_it(self, resident):
            return False
        activity = resident.activity
        if activity is not None and activity.using and activity.action == SLEEP_ROUGH_ACTION:
            return False
        if activity is None or not activity.using or activity.target_id is None:
            return True
        placed = self.interactables.get(activity.target_id)
        use = self.definition_of(placed).use_for(activity.action) if placed is not None else None
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
        powered = self.power.enough(self)
        for placed in self.interactables.values():
            reach = self.light_of(placed, powered)
            if reach <= 0:
                continue
            source = (placed.x, placed.y)
            if within_range(source, tile, reach) and line_of_sight(source, tile, opaque):
                return True
        return False

    def light_of(self, placed: Interactable, powered: bool | None = None) -> int:
        """How many tiles round it an object lights right now. A lamp gives none while the
        power is out, and nothing does that a law has put out for the night."""
        if self.definition_of(placed).draws > 0:
            # What runs on current gives no light without it, nor switched off (S55).
            if not placed.on or not (self.power.enough(self) if powered is None else powered):
                return 0
        if self.government.laws and self.politics.laws.dark(self, placed):
            return 0
        return self.definition_of(placed).light

    def power_units(self) -> int:
        """Fuel units in generators that can keep lamps and the radio alive."""
        return self.power.fuel(self)

    def has_power(self) -> bool:
        """Whether there is fuel for what gives current. Whether a thing has current is `power.powered`."""
        return self.power_units() > 0

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

        Tiles in `also` count as walkable even if an object stands on them. Ground marked out
        for something that will be in the way once it is up is kept off meanwhile.
        """
        blocked = {
            tile
            for placed in self.interactables.values()
            if self.definition_of(placed).blocks
            for tile in placed.footprint(self.definition_of(placed))
        } - set(also)
        blocked.update(tile for site in self.sites.values() if site.blocks for tile in site.tiles)
        terrain = self.registries.terrain
        tile_map = self.tile_map

        def is_passable(tile: Tile) -> bool:
            if not tile_map.in_bounds(tile) or tile in blocked:
                return False
            definition = terrain.get(tile_map.terrain_at(tile))
            return definition is not None and definition.walkable

        return is_passable

    @classmethod
    def new_settlement(cls, seed: int = 7, registries: BuiltInRegistries | None = None) -> "SimulationWorld":
        """An empty plot with nobody on it, and the opening that leads the player through settling it."""
        world = cls(
            rng=SimulationRNG(seed),
            event_rng=SimulationRNG(seed * 7919 + 13),
            registries=registries or builtin_registries(),
        )
        map_id = world.registries.tutorial.map_id
        world.load_layout(map_id if map_id in world.registries.maps else DEFAULT_MAP_ID)
        world.stock_from_layout()
        world.guide.start(world)
        return world

    @classmethod
    def demo_world(cls, seed: int = 7, registries: BuiltInRegistries | None = None) -> "SimulationWorld":
        world = cls(
            rng=SimulationRNG(seed),
            event_rng=SimulationRNG(seed * 7919 + 13),
            registries=registries or builtin_registries(),
        )
        world.load_layout(DEFAULT_MAP_ID)
        world.stock_from_layout()
        # A settlement that is already running knows how to make what it has.
        world.research.grant_what_stands(world)
        residents = [
            Resident("marta", "Marta", personality=Personality(empathy=75, sociability=65, charisma=68, leadership=58), traits=["music_lover"]),
            Resident("raul", "Raúl", personality=Personality(aggression=72, impulsiveness=68, charisma=42, leadership=55)),
            Resident("lucia", "Lucía", personality=Personality(empathy=60, greed=25, charisma=55, leadership=45), traits=["sweet_tooth"]),
            Resident("tomas", "Tomás", personality=Personality(courage=75, sociability=35, aggression=55, charisma=45, leadership=70)),
            Resident("ines", "Inés", personality=Personality(empathy=65, sociability=60, greed=40, charisma=60, leadership=50)),
            Resident("vera", "Vera", personality=Personality(empathy=80, sociability=55, courage=60, charisma=62, leadership=64)),
            Resident("paco", "Paco", personality=Personality(empathy=45, sociability=45, impulsiveness=40, charisma=40, leadership=35), traits=["dim"]),
            Resident("nuria", "Nuria", personality=Personality(empathy=55, sociability=70, greed=65, charisma=70, leadership=40)),
            Resident(
                "sergio",
                "Sergio",
                personality=Personality(courage=70, greed=60, impulsiveness=55, charisma=55, leadership=52),
                traits=["rogue"],
            ),
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
        # What each is capable of: strength, constitution, dexterity, mind and senses.
        capable = {
            "marta": (4, 6, 6, 6, 5), "raul": (7, 6, 4, 4, 5), "lucia": (3, 5, 6, 5, 6), "tomas": (7, 7, 5, 4, 6),
            "ines": (5, 6, 6, 5, 5), "vera": (4, 5, 6, 8, 6), "paco": (6, 6, 6, 3, 4), "nuria": (4, 4, 5, 7, 6),
            "sergio": (5, 5, 7, 5, 7),
        }
        for resident in residents:
            resident.attributes = Attributes(*(float(value) for value in capable[resident.resident_id]))
            resident.age = ages[resident.resident_id]
            job_id, post_id, day_off = posts[resident.resident_id]
            resident.credits = world.registries.economy.starting_credits
            if job_id in world.registries.jobs and post_id in world.interactables:
                resident.job_id, resident.post_id, resident.day_off = job_id, post_id, day_off
        spawns = world.registries.maps[world.map_id].spawns
        for index, resident in enumerate(residents):
            resident.x, resident.y = spawns[index % len(spawns)]
            world.residents[resident.resident_id] = resident
        for resident in residents:
            world.family.welcome(world, resident)
        # A settlement that is already running trades with the credits it has always had.
        world.terms.settle_on_credits(world)
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
        # A settlement that is already running has its houses given out: everybody has the
        # one they sleep in. The player changes it from there.
        world.housing.settle(world)
        return world
