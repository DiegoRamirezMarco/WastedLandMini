from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

from simulation.ai.affect import AffectResult
from simulation.economy.terms import TradeResult
from simulation.housing.housing import HousingResult
from simulation.justice.justice_system import JusticeResult
from simulation.politics.government import PoliticsResult
from simulation.work.craft import CraftResult
from simulation.work.research import ResearchResult
from world.map import Tile
from world.urbanism import UrbanismResult
from typing import Protocol


class CommandTarget(Protocol):
    def step(self, minutes: int | None = None) -> None:
        ...

    def set_paused(self, paused: bool) -> None:
        ...

    def set_speed(self, speed: int) -> None:
        ...

    def choose_option(self, decision_id: str, option_id: str) -> str | None:
        ...

    def suggest_job(self, resident_id: str, job_id: str, option_id: str) -> str | None:
        ...

    def place_object(self, kind: str, tile: Tile) -> UrbanismResult:
        ...

    def move_object(self, object_id: str, tile: Tile) -> UrbanismResult:
        ...

    def remove_object(self, object_id: str) -> UrbanismResult:
        ...

    def place_building(self, blueprint_id: str, tile: Tile) -> UrbanismResult:
        ...

    def move_building(self, room_id: str, tile: Tile) -> UrbanismResult:
        ...

    def remove_building(self, room_id: str) -> UrbanismResult:
        ...

    def propose_object(self, kind: str, tile: Tile, resident_id: str, option_id: str) -> UrbanismResult:
        ...

    def propose_building(self, blueprint_id: str, tile: Tile, resident_id: str, option_id: str) -> UrbanismResult:
        ...

    def cancel_site(self, site_id: str) -> UrbanismResult:
        ...

    def order_salvage(self, resident_id: str, object_id: str) -> UrbanismResult:
        ...

    def hold_resident(self, resident_id: str) -> AffectResult:
        ...

    def release_resident(self, resident_id: str) -> bool:
        ...

    def affect_resident(self, resident_id: str, kind: str, target_id: str | None) -> AffectResult:
        ...

    def scrap_item(self, item_id: str, option_id: str) -> UrbanismResult:
        ...

    def set_research(self, subject_id: str | None) -> ResearchResult:
        ...

    def propose_currency(self, name: str, singular: str | None, option_id: str) -> TradeResult:
        ...

    def propose_barter(self, option_id: str) -> TradeResult:
        ...

    def rename_currency(self, name: str, singular: str | None) -> TradeResult:
        ...

    def deal_with_merchant(self, sell: Mapping[str, int], buy: Mapping[str, int]) -> TradeResult:
        ...

    def propose_sale(self, resident_id: str, item_id: str, for_item: str | None, option_id: str) -> TradeResult:
        ...

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
        ...

    def set_identity(self, resident_id: str, sex: str, gender: str, drawn_to: str) -> bool:
        ...

    def propose_government(self, government_id: str) -> PoliticsResult:
        ...

    def choose_government(self, government_id: str) -> PoliticsResult:
        ...

    def give_house(self, room_id: str, owners: list[str]) -> HousingResult:
        ...

    def name_building(self, room_id: str, name: str | None = None, use: str | None = None) -> HousingResult:
        ...

    def lock_house(self, room_id: str, locked: bool) -> HousingResult:
        ...

    def decorate(self, room_id: str, kind: str, x: int, y: int) -> HousingResult:
        ...

    def undecorate(self, room_id: str, ornament_id: str) -> HousingResult:
        ...

    def surface_building(self, room_id: str, floor: str | None = None, wall: str | None = None) -> HousingResult:
        ...

    def propose(
        self,
        kind: str,
        law: str | None = None,
        degree: int | None = None,
        target: str | None = None,
        government: str | None = None,
        params: Mapping[str, str] | None = None,
    ) -> PoliticsResult:
        ...

    def lobby(self, proposal_id: str, resident_id: str, stance: str) -> PoliticsResult:
        ...

    def back_candidate(self, resident_id: str, candidate_id: str) -> PoliticsResult:
        ...

    def set_manner(self, resident_id: str, kind_id: str, manner_id: str) -> bool:
        ...

    def name_discovery(self, discovery_id: str, name: str, choices: Mapping[str, str] | None = None) -> CraftResult:
        ...

    def accuse(self, accused_id: str, fact_id: str | None = None) -> JusticeResult:
        ...

    def sentence(self, trial_id: str, punishment_id: str) -> JusticeResult:
        ...

    def set_prison_ration(self, meals: int, drinks: int, food: str = "", drink: str = "") -> JusticeResult:
        ...

    def acknowledge_tutorial(self) -> bool:
        ...

    def report_deed(self, deed: str) -> bool:
        ...


class SimulationCommand(Protocol):
    def apply(self, world: CommandTarget) -> object:
        ...


@dataclass(frozen=True)
class AdvanceTimeCommand:
    minutes: int | None = None

    def apply(self, world: CommandTarget) -> None:
        world.step(self.minutes)


@dataclass(frozen=True)
class SetPausedCommand:
    paused: bool

    def apply(self, world: CommandTarget) -> None:
        world.set_paused(self.paused)


@dataclass(frozen=True)
class SetSpeedCommand:
    speed: int

    def apply(self, world: CommandTarget) -> None:
        world.set_speed(self.speed)


@dataclass(frozen=True)
class ChooseOptionCommand:
    """The player's advice on an open decision."""

    decision_id: str
    option_id: str

    def apply(self, world: CommandTarget) -> str | None:
        """Returns the ID of what the resident decided to do, or None if the decision was closed."""
        return world.choose_option(self.decision_id, self.option_id)


@dataclass(frozen=True)
class SuggestJobCommand:
    """The player's suggestion that a resident take up a job that has a free post."""

    resident_id: str
    job_id: str
    # The advice it is given with, one of the options of the job offer decision.
    option_id: str = "encourage"

    def apply(self, world: CommandTarget) -> str | None:
        """Returns the ID of what the resident decided, or None if they could not be asked."""
        return world.suggest_job(self.resident_id, self.job_id, self.option_id)


@dataclass(frozen=True)
class PlaceObjectCommand:
    """Put an object down at once. Only one that takes nothing to build can be."""

    kind: str
    tile: Tile

    def apply(self, world: CommandTarget) -> UrbanismResult:
        return world.place_object(self.kind, self.tile)


@dataclass(frozen=True)
class MoveObjectCommand:
    object_id: str
    tile: Tile

    def apply(self, world: CommandTarget) -> UrbanismResult:
        return world.move_object(self.object_id, self.tile)


@dataclass(frozen=True)
class RemoveObjectCommand:
    object_id: str

    def apply(self, world: CommandTarget) -> UrbanismResult:
        return world.remove_object(self.object_id)


@dataclass(frozen=True)
class PlaceBuildingCommand:
    """Put a building down at once. Only one that takes nothing to build can be."""

    blueprint_id: str
    tile: Tile

    def apply(self, world: CommandTarget) -> UrbanismResult:
        return world.place_building(self.blueprint_id, self.tile)


@dataclass(frozen=True)
class MoveBuildingCommand:
    room_id: str
    tile: Tile

    def apply(self, world: CommandTarget) -> UrbanismResult:
        return world.move_building(self.room_id, self.tile)


@dataclass(frozen=True)
class RemoveBuildingCommand:
    room_id: str

    def apply(self, world: CommandTarget) -> UrbanismResult:
        return world.remove_building(self.room_id)


@dataclass(frozen=True)
class ProposeObjectCommand:
    """The player's proposal to a resident that they put an object up somewhere.

    They agree or they do not. If they do, the ground is marked out and the result names the site.
    """

    kind: str
    tile: Tile
    resident_id: str
    # The advice it is given with, one of the options of the building proposal decision.
    option_id: str = "encourage"

    def apply(self, world: CommandTarget) -> UrbanismResult:
        return world.propose_object(self.kind, self.tile, self.resident_id, self.option_id)


@dataclass(frozen=True)
class ProposeBuildingCommand:
    """The player's proposal to a resident that they put a building up somewhere."""

    blueprint_id: str
    tile: Tile
    resident_id: str
    option_id: str = "encourage"

    def apply(self, world: CommandTarget) -> UrbanismResult:
        return world.propose_building(self.blueprint_id, self.tile, self.resident_id, self.option_id)


@dataclass(frozen=True)
class CancelSiteCommand:
    """Give up something that is being built. What had been brought to it is put away."""

    site_id: str

    def apply(self, world: CommandTarget) -> UrbanismResult:
        return world.cancel_site(self.site_id)


@dataclass(frozen=True)
class HoldResidentCommand:
    """The player stops a resident: they leave off what they were doing and stand there
    listening for a while, to be told something. With nothing said they go about their day."""

    resident_id: str

    def apply(self, world: CommandTarget) -> AffectResult:
        return world.hold_resident(self.resident_id)


@dataclass(frozen=True)
class ReleaseResidentCommand:
    """The player lets a resident they had stopped go, with nothing said."""

    resident_id: str

    def apply(self, world: CommandTarget) -> bool:
        return world.release_resident(self.resident_id)


@dataclass(frozen=True)
class AffectCommand:
    """The player tells a resident to do something. It is the one place where what the player
    says is an order: the resident does it, as far as it can be done.

    `kind` is one of what the world offers for that resident right now, such as `need:eat`,
    `with:talk`, `incite:strike`, `task:salvage` or `words:calm`, and `target_id` who or what it
    is about where it is about somebody or something.
    """

    resident_id: str
    kind: str
    target_id: str | None = None

    def apply(self, world: CommandTarget) -> AffectResult:
        return world.affect_resident(self.resident_id, self.kind, self.target_id)


@dataclass(frozen=True)
class SalvageCommand:
    """The player tells a resident to take apart something that is lying about: a rusted car, a
    heap of tyres. It is that resident's task until it is done, and what comes out of it goes
    to the site they see to, if it waits for it, or to where such things are kept."""

    resident_id: str
    object_id: str

    def apply(self, world: CommandTarget) -> UrbanismResult:
        return world.order_salvage(self.resident_id, self.object_id)


@dataclass(frozen=True)
class ScrapItemCommand:
    """The player has an item broken up for scrap.

    What is nobody's and kept in a container is broken up there and then: it is one of the
    things the player does with their own hands. What is somebody's is put to them, with the
    advice given, and it is theirs to say.
    """

    # The item, by its instance ID.
    item_id: str
    option_id: str = "encourage"

    def apply(self, world: CommandTarget) -> UrbanismResult:
        return world.scrap_item(self.item_id, self.option_id)


@dataclass(frozen=True)
class SetResearchCommand:
    """The player's say on what is to be worked out next. None for nothing at all.

    It is theirs to say: whoever holds the post works on whatever has been chosen. What was done
    on a subject that is left for another is kept.
    """

    subject_id: str | None

    def apply(self, world: CommandTarget) -> ResearchResult:
        return world.set_research(self.subject_id)


@dataclass(frozen=True)
class ProposeCurrencyCommand:
    """The player's proposal that the settlement trade with a currency they have made and named.

    It is the residents who settle it, each for themselves, with the advice it is put with. If
    more are for it than against, prices, wages and the fund are counted in it from then on.
    Where there is a government it is decided as anything is: it becomes a proposal, and the
    result says whether one was laid before those who decide.
    """

    name: str
    # What one of it is called. Left out, it is the name less a final `s`.
    singular: str | None = None
    # The advice it is put with, one of the options of the currency proposal decision.
    option_id: str = "encourage"

    def apply(self, world: CommandTarget) -> TradeResult:
        return world.propose_currency(self.name, self.singular, self.option_id)


@dataclass(frozen=True)
class ProposeBarterCommand:
    """The player's proposal that the settlement go back to trading a thing for a thing."""

    option_id: str = "encourage"

    def apply(self, world: CommandTarget) -> TradeResult:
        return world.propose_barter(self.option_id)


@dataclass(frozen=True)
class ProposeGovernmentCommand:
    """The player's one proposal of a kind of government, while the settlement is choosing one.
    It weighs with each resident as advice does, and they settle it among themselves."""

    government_id: str

    def apply(self, world: CommandTarget) -> PoliticsResult:
        return world.propose_government(self.government_id)


@dataclass(frozen=True)
class GiveHouseCommand:
    """The player says who a building belongs to (S41). With nobody, it is the settlement's again.

    It is theirs from then on: they sleep there, whoever they would have in may come in, and
    what is kept in it is none of the settlement's.
    """

    room_id: str
    owners: tuple[str, ...] = ()

    def apply(self, world: CommandTarget) -> HousingResult:
        return world.give_house(self.room_id, list(self.owners))


@dataclass(frozen=True)
class DecorateCommand:
    """The player puts an ornament in a building (S42): at once and for nothing.

    Where it goes is in cells of the inside of the building from its back left corner: a
    cell of the floor, or a stretch of the back wall.
    """

    room_id: str
    kind: str
    x: int
    y: int = 0

    def apply(self, world: CommandTarget) -> HousingResult:
        return world.decorate(self.room_id, self.kind, self.x, self.y)


@dataclass(frozen=True)
class UndecorateCommand:
    """The player takes an ornament out of a building."""

    room_id: str
    ornament_id: str

    def apply(self, world: CommandTarget) -> HousingResult:
        return world.undecorate(self.room_id, self.ornament_id)


@dataclass(frozen=True)
class SurfaceCommand:
    """The player says what the floor of a building is made of, its walls, or both (S42).

    Nothing said of one, as an empty ID, puts it back as the building was put up.
    """

    room_id: str
    floor: str | None = None
    wall: str | None = None

    def apply(self, world: CommandTarget) -> HousingResult:
        return world.surface_building(self.room_id, self.floor, self.wall)


@dataclass(frozen=True)
class LockHouseCommand:
    """The player locks the door of a building that is somebody's, or leaves it open again (S41).

    Locked, nobody but whoever lives there goes in, however well they are thought of.
    """

    room_id: str
    locked: bool = True

    def apply(self, world: CommandTarget) -> HousingResult:
        return world.lock_house(self.room_id, self.locked)


@dataclass(frozen=True)
class NameBuildingCommand:
    """The player gives a building a name of its own, says what it is for, or both (S41)."""

    room_id: str
    name: str | None = None
    use: str | None = None

    def apply(self, world: CommandTarget) -> HousingResult:
        return world.name_building(self.room_id, self.name, self.use)


@dataclass(frozen=True)
class ChooseGovernmentCommand:
    """The player says how the settlement is governed, and it is (S38): while it is choosing a
    kind, or in place of the one it has. How many would have had it is how legitimate it starts.
    """

    government_id: str

    def apply(self, world: CommandTarget) -> PoliticsResult:
        return world.choose_government(self.government_id)


@dataclass(frozen=True)
class ProposeCommand:
    """Something the player puts to the settlement: a law, doing away with one, a vote for who
    leads, another kind of government, throwing somebody out, or another way of trading.

    Somebody who may propose under the government in force has to make it theirs, and then
    those who decide, decide. Nothing of it is done unless it passes. The result says whether
    it was laid before them, and its `detail` is the ID of the proposal.
    """

    # One of the kinds in `data/proposals.json`.
    kind: str
    # The law it is about and how far it goes, counted from 0 for the mildest. Left out, a law
    # is proposed at the middle of how far it can go.
    law: str | None = None
    degree: int | None = None
    # The resident it is about, and the kind of government.
    target: str | None = None
    government: str | None = None
    # What else it names: the `item` a law is to ban, the `name` and `singular` of a currency.
    params: Mapping[str, str] = field(default_factory=dict)

    def apply(self, world: CommandTarget) -> PoliticsResult:
        return world.propose(self.kind, self.law, self.degree, self.target, self.government, self.params)


@dataclass(frozen=True)
class LobbyCommand:
    """The player speaks to one of those who will decide a proposal, for it or against it.

    Once for each resident and proposal. They vote as they see fit: the result's `detail` says
    whether they went along (`taken`), came half way (`softened`), took no notice (`ignored`)
    or did the opposite (`contrary`).
    """

    proposal_id: str
    resident_id: str
    # `for` or `against`.
    stance: str = "for"

    def apply(self, world: CommandTarget) -> PoliticsResult:
        return world.lobby(self.proposal_id, self.resident_id, self.stance)


@dataclass(frozen=True)
class BackCandidateCommand:
    """The player speaks to a resident for one of those who stand in the vote that has been
    called. Once for each resident and vote, and they vote as they see fit."""

    resident_id: str
    candidate_id: str

    def apply(self, world: CommandTarget) -> PoliticsResult:
        return world.back_candidate(self.resident_id, self.candidate_id)


@dataclass(frozen=True)
class RenameCurrencyCommand:
    """The player's name for the currency the settlement has, when it took one up of its own
    accord under the plain name such a thing goes by. What anybody holds of it is the same."""

    name: str
    singular: str | None = None

    def apply(self, world: CommandTarget) -> TradeResult:
        return world.rename_currency(self.name, self.singular)


@dataclass(frozen=True)
class DealWithMerchantCommand:
    """What the player sells to whoever has stopped to trade, and buys from them, in one go.

    It is the one thing the player does with their own hands. Only what is nobody's can be sold
    this way. Each is units by item ID: with a currency the difference comes out of the fund or
    goes into it, and under barter what is given has to be worth what is taken.
    """

    sell: Mapping[str, int] = field(default_factory=dict)
    buy: Mapping[str, int] = field(default_factory=dict)

    def apply(self, world: CommandTarget) -> TradeResult:
        return world.deal_with_merchant(self.sell, self.buy)


@dataclass(frozen=True)
class ProposeSaleCommand:
    """The player's proposal to a resident that they sell a thing of their own to a merchant.

    They agree or they do not, by what it is worth to them. What it fetches is theirs: coin, or
    under barter the thing of the merchant's that `for_item` names.
    """

    resident_id: str
    # The item of theirs, by its instance ID.
    item_id: str
    for_item: str | None = None
    option_id: str = "encourage"

    def apply(self, world: CommandTarget) -> TradeResult:
        return world.propose_sale(self.resident_id, self.item_id, self.for_item, self.option_id)


@dataclass(frozen=True)
class FoundResidentCommand:
    """The player's first resident, as they made them. Only a settlement with nobody in it takes one."""

    name: str
    age: int = 30
    personality: Mapping[str, float] = field(default_factory=dict)
    traits: Sequence[str] = ()
    # Their way of doing each kind of thing, by kind. A kind left out goes by their own by default.
    manners: Mapping[str, str] = field(default_factory=dict)
    # Their `sex` (`m` or `f`), their `gender` (`m`, `f`, `nb` or `bi`) and who they are `drawn_to`
    # (`m`, `f` or `both`). What is left out follows from who they are.
    identity: Mapping[str, str] = field(default_factory=dict)
    # Their strength, constitution, dexterity, mind, senses and charisma, from 1 to 10 (S46).
    # What is left out is in the middle, and all six come to no more than there are points for.
    # None for what the seed gives them, as it gives anybody.
    attributes: Mapping[str, float] | None = None

    def apply(self, world: CommandTarget) -> str | None:
        """Returns the ID of whoever now lives there, or None if the settlement would not have them."""
        return world.found_resident(
            self.name, self.age, self.personality, self.traits, self.manners, self.identity, self.attributes
        )


@dataclass(frozen=True)
class SetIdentityCommand:
    """The player's say on a resident's sex, their gender and who they are drawn to: for someone
    out of a save from before there was any of it, whom the game could only guess at."""

    resident_id: str
    sex: str
    gender: str
    drawn_to: str = "both"

    def apply(self, world: CommandTarget) -> bool:
        """Returns whether they are now so: there must be such a resident, and it must make sense."""
        return world.set_identity(self.resident_id, self.sex, self.gender, self.drawn_to)


@dataclass(frozen=True)
class NameDiscoveryCommand:
    """What the player says something a resident has come to at their job is (S47): what it
    is called, and what is picked of it out of what its kind lets be picked, by choice ID.

    What it is like otherwise is the game's to work out. Left unpicked, a choice is the first
    there is. Drawing it is done on the window, and is no business of the simulation's.
    """

    discovery_id: str
    name: str
    choices: Mapping[str, str] = field(default_factory=dict)

    def apply(self, world: CommandTarget) -> CraftResult:
        return world.name_discovery(self.discovery_id, self.name, self.choices)


@dataclass(frozen=True)
class AccuseCommand:
    """The player's accusation: that a resident be tried for something known of them.

    It is refused for what nobody in the settlement saw or was told of. Left out, the thing is
    the latest that is known of them. Whether they are guilty is for those who decide to say.
    """

    accused_id: str
    # The fact it rests on, by its ID.
    fact_id: str | None = None

    def apply(self, world: CommandTarget) -> JusticeResult:
        return world.accuse(self.accused_id, self.fact_id)


@dataclass(frozen=True)
class SentenceCommand:
    """What the player says somebody found guilty is given. Only what the settlement has a
    place for can be: no prison without a jail, nor stocks, gallows or guillotine without one."""

    trial_id: str
    punishment_id: str

    def apply(self, world: CommandTarget) -> JusticeResult:
        return world.sentence(self.trial_id, self.punishment_id)


@dataclass(frozen=True)
class SetPrisonRationCommand:
    """How much a prisoner is given to eat and to drink each day, and of what, by item ID. An
    item left out is whatever of the kind the settlement has most of."""

    meals: int
    drinks: int
    food: str = ""
    drink: str = ""

    def apply(self, world: CommandTarget) -> JusticeResult:
        return world.set_prison_ration(self.meals, self.drinks, self.food, self.drink)


@dataclass(frozen=True)
class SetMannerCommand:
    """The player's say on how a resident walks, eats or fights. It changes how it looks and nothing else."""

    resident_id: str
    kind_id: str
    manner_id: str

    def apply(self, world: CommandTarget) -> bool:
        """Returns whether they now have it: it must be a manner of that kind, and they must live there."""
        return world.set_manner(self.resident_id, self.kind_id, self.manner_id)


@dataclass(frozen=True)
class AcknowledgeTutorialCommand:
    """The player has read the step of the opening that only asks to be read."""

    def apply(self, world: CommandTarget) -> bool:
        return world.acknowledge_tutorial()


@dataclass(frozen=True)
class ReportDeedCommand:
    """The player has done something with their own hands that the opening may be waiting for.

    What it was is a name and nothing more to the simulation: drawing is not its business.
    """

    deed: str

    def apply(self, world: CommandTarget) -> bool:
        """Returns whether the step in hand was waiting for it."""
        return world.report_deed(self.deed)
