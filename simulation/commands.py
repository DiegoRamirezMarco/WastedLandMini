from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

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

    def found_resident(
        self, name: str, age: int, personality: Mapping[str, float], traits: Sequence[str]
    ) -> str | None:
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
class FoundResidentCommand:
    """The player's first resident, as they made them. Only a settlement with nobody in it takes one."""

    name: str
    age: int = 30
    personality: Mapping[str, float] = field(default_factory=dict)
    traits: Sequence[str] = ()

    def apply(self, world: CommandTarget) -> str | None:
        """Returns the ID of whoever now lives there, or None if the settlement would not have them."""
        return world.found_resident(self.name, self.age, self.personality, self.traits)


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
