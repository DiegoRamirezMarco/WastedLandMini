from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

from simulation.economy.terms import TradeResult
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

    def set_research(self, subject_id: str | None) -> ResearchResult:
        ...

    def propose_currency(self, name: str, singular: str | None, option_id: str) -> TradeResult:
        ...

    def propose_barter(self, option_id: str) -> TradeResult:
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
    ) -> str | None:
        ...

    def set_manner(self, resident_id: str, kind_id: str, manner_id: str) -> bool:
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

    def apply(self, world: CommandTarget) -> str | None:
        """Returns the ID of whoever now lives there, or None if the settlement would not have them."""
        return world.found_resident(self.name, self.age, self.personality, self.traits, self.manners)


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
