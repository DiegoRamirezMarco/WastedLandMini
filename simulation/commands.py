from dataclasses import dataclass
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
