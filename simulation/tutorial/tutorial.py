"""The opening of a new settlement: the steps the player is led through, as data.

A step says what to do, what counts as having done it, and what the settlement is given for it.
Nothing here knows how a step is shown: `focus` only names the part of the game it is about.
"""

from dataclasses import dataclass, field
from typing import Any

# What a step may wait for.
RESIDENTS = "residents"  # so many people living here
BUILDING = "building"  # so many roofed buildings, of one blueprint or of any
OBJECT = "object"  # so many objects of a kind, under a roof if `indoors`
JOB = "job"  # so many residents holding a job, one in particular or any
ELAPSED = "elapsed"  # so many game minutes since the step began
ANSWERED = "answered"  # whatever the step set going has been settled
ACKNOWLEDGED = "acknowledged"  # the player has said they have read it
DEED = "deed"  # the player has done something that only whoever shows the game can see, such as drawing
GOAL_KINDS = (RESIDENTS, BUILDING, OBJECT, JOB, ELAPSED, ANSWERED, ACKNOWLEDGED, DEED)

# What a step may set going when it begins.
STRANGER_OPENING = "stranger"
OPENINGS = (STRANGER_OPENING,)

# Who a gift may be handed to instead of being left in a container.
TO_RESIDENT = "resident"


@dataclass(frozen=True)
class Goal:
    kind: str
    # Object kind, blueprint ID or job ID the goal is about. None for any.
    target: str | None = None
    count: int = 1
    minutes: int = 0
    indoors: bool = False
    # Something the player has to have done besides, by the name whoever shows the game gives it.
    # A goal of the `deed` kind asks for nothing else, and names it as its target.
    deed: str | None = None

    @property
    def needed_deed(self) -> str | None:
        return self.target if self.kind == DEED else self.deed


@dataclass(frozen=True)
class Gift:
    """Something the settlement starts with, handed over when the step that calls for it is done."""

    item: str
    count: int = 1
    # Kind of container it is left in, as nobody's in particular.
    into: str | None = None
    # Or who it is given to, as their own: `resident` for whoever has been here longest.
    to: str | None = None


@dataclass(frozen=True)
class TutorialStep:
    step_id: str
    title: str
    text: str
    goal: Goal
    gifts: tuple[Gift, ...] = ()
    # What the step sets going when it begins, one of OPENINGS.
    opening: str | None = None
    # The part of the game the step is about, for whoever shows it to point at, and what in it.
    focus: str | None = None
    hint: str | None = None
    # What is said once it is done.
    done: str = ""


@dataclass(frozen=True)
class TutorialDefinition:
    # Map a new settlement starts on.
    map_id: str = ""
    steps: tuple[TutorialStep, ...] = ()

    def step(self, step_id: str | None) -> TutorialStep | None:
        return next((step for step in self.steps if step.step_id == step_id), None)

    def index_of(self, step_id: str | None) -> int | None:
        return next((index for index, step in enumerate(self.steps) if step.step_id == step_id), None)


@dataclass
class TutorialState:
    """Where a settlement is in its opening. With no step, it is not being led anywhere."""

    step_id: str | None = None
    # Game minute at which the step began.
    since: int = 0
    # Whether what the step sets going has been set going.
    opened: bool = False
    acknowledged: bool = False
    # What the player has done, of what the step in hand asks them to do.
    deeds: list[str] = field(default_factory=list)
    # Steps done so far, in order.
    done: list[str] = field(default_factory=list)

    @property
    def active(self) -> bool:
        return self.step_id is not None


def _goal_from_data(step_id: str, data: Any) -> Goal:
    if not isinstance(data, dict) or "type" not in data:
        raise ValueError(f"Tutorial step {step_id} needs a goal with a type")
    goal = Goal(
        kind=str(data["type"]),
        target=str(data["target"]) if data.get("target") is not None else None,
        count=int(data.get("count", 1)),
        minutes=int(data.get("minutes", 0)),
        indoors=bool(data.get("indoors", False)),
        deed=str(data["deed"]) if data.get("deed") is not None else None,
    )
    if goal.kind not in GOAL_KINDS:
        raise ValueError(f"Tutorial step {step_id} has an unknown kind of goal: {goal.kind}")
    if goal.count < 1 or goal.minutes < 0:
        raise ValueError(f"Tutorial step {step_id} asks for a count or a time that makes no sense")
    if goal.kind == OBJECT and goal.target is None:
        raise ValueError(f"Tutorial step {step_id} waits for an object without saying which kind")
    if goal.kind == DEED and goal.target is None:
        raise ValueError(f"Tutorial step {step_id} waits for the player to do something without saying what")
    return goal


def _gift_from_data(step_id: str, data: Any) -> Gift:
    if not isinstance(data, dict) or "item" not in data:
        raise ValueError(f"Tutorial step {step_id} has a gift without an item")
    gift = Gift(
        item=str(data["item"]),
        count=int(data.get("count", 1)),
        into=str(data["into"]) if data.get("into") is not None else None,
        to=str(data["to"]) if data.get("to") is not None else None,
    )
    if gift.count < 1:
        raise ValueError(f"Tutorial step {step_id} gives less than one of something")
    if (gift.into is None) == (gift.to is None):
        raise ValueError(f"Tutorial step {step_id} must say either what a gift goes into or who it goes to")
    if gift.to is not None and gift.to != TO_RESIDENT:
        raise ValueError(f"Tutorial step {step_id} gives something to nobody known: {gift.to}")
    return gift


def tutorial_definition_from_data(data: dict[str, Any]) -> TutorialDefinition:
    steps: list[TutorialStep] = []
    for entry in data.get("steps", []):
        if not isinstance(entry, dict) or not {"id", "title", "text", "goal"} <= entry.keys():
            raise ValueError("A tutorial step needs an id, a title, a text and a goal")
        step_id = str(entry["id"])
        if any(step.step_id == step_id for step in steps):
            raise ValueError(f"Duplicate tutorial step id: {step_id}")
        opening = str(entry["opening"]) if entry.get("opening") is not None else None
        if opening is not None and opening not in OPENINGS:
            raise ValueError(f"Tutorial step {step_id} sets going something unknown: {opening}")
        goal = _goal_from_data(step_id, entry["goal"])
        if goal.kind == ANSWERED and opening is None:
            raise ValueError(f"Tutorial step {step_id} waits for an answer to nothing")
        steps.append(
            TutorialStep(
                step_id=step_id,
                title=str(entry["title"]),
                text=str(entry["text"]),
                goal=goal,
                gifts=tuple(_gift_from_data(step_id, gift) for gift in entry.get("gifts", [])),
                opening=opening,
                focus=str(entry["focus"]) if entry.get("focus") is not None else None,
                hint=str(entry["hint"]) if entry.get("hint") is not None else None,
                done=str(entry.get("done", "")),
            )
        )
    return TutorialDefinition(map_id=str(data.get("map", "")), steps=tuple(steps))
