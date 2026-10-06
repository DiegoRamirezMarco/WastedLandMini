from dataclasses import dataclass, field
from typing import Any

from simulation.events.crisis import Crisis
from simulation.events.world_event import GATE_CHOICES, RAID_CHOICES
from simulation.residents.needs import NEED_NAMES
from simulation.social.relationship import FEELINGS
from simulation.work.expedition import EXPEDITION_CHOICES

# What an outcome's score may depend on. Each is scaled to run from 0 to 1.
SCORE_INPUTS = (
    "bias", "anger", "aggression", "impulsiveness", "empathy", "courage", "sociability", "greed",
    "stress", "affection", "resentment", "fear", "attraction", "health", "vacancy", "idle",
    "mood", "burden", "effort", "short",
)


@dataclass(frozen=True)
class DecisionOption:
    """Advice the player can give. `influence` adds to the score of the outcomes it names."""

    option_id: str
    text: str
    influence: dict[str, float] = field(default_factory=dict)


@dataclass
class Decision:
    """An open chance for the player to advise a resident before they act."""

    decision_id: str
    resident_id: str
    prompt: str
    options: list[DecisionOption]
    related_event_type: str
    kind: str = ""
    # Game minute at which the resident stops waiting and decides alone.
    deadline: int = 0
    crisis: Crisis | None = None
    # Job the decision is about, when it is about taking up a post.
    job_id: str | None = None
    # What the decision is about, as it is named in a sentence, when it is about a thing.
    subject: str | None = None
    # Particulars of what is being decided that weigh on it, each from 0 to 1, by score input.
    inputs: dict[str, float] = field(default_factory=dict)


@dataclass(frozen=True)
class OutcomeDefinition:
    """One thing the resident may end up doing. `score` weighs the inputs in SCORE_INPUTS."""

    outcome_id: str
    score: dict[str, float]
    text: str
    interaction: str | None = None
    needs: dict[str, float] = field(default_factory=dict)
    feelings: dict[str, float] = field(default_factory=dict)
    memory: str | None = None
    # Whether choosing this means taking up the job the decision is about.
    takes_job: bool = False
    # What choosing this does to the trip outside the resident is on: `push_on` or `turn_back`.
    expedition: str | None = None
    # What choosing this does about the stranger at the gate: `let_in` or `turn_away`.
    gate: str | None = None
    # What choosing this does about raiders: `stand_ground` or `give_way`.
    raid: str | None = None
    # Whether choosing this means taking on the piece of building the decision is about.
    builds: bool = False


@dataclass(frozen=True)
class DecisionDefinition:
    kind: str
    event_type: str
    window_minutes: int
    cooldown_minutes: int
    anger_threshold: float
    importance: int
    text: str
    prompt: str
    outcomes: dict[str, OutcomeDefinition]
    options: tuple[DecisionOption, ...]


def decision_definition_from_data(kind: str, data: dict[str, Any]) -> DecisionDefinition:
    missing = {"event_type", "text", "prompt", "outcomes", "options"} - data.keys()
    if missing:
        raise ValueError(f"Missing fields in decision {kind}: {sorted(missing)}")
    outcomes = {
        str(outcome_id): _outcome_from_data(kind, str(outcome_id), values)
        for outcome_id, values in data["outcomes"].items()
    }
    if not outcomes:
        raise ValueError(f"Decision {kind} has no outcomes")
    options = []
    for option in data["options"]:
        influence = {str(outcome): float(weight) for outcome, weight in option.get("influence", {}).items()}
        unknown = influence.keys() - outcomes.keys()
        if unknown:
            raise ValueError(f"Option {option['id']} of decision {kind} names unknown outcomes: {sorted(unknown)}")
        options.append(DecisionOption(str(option["id"]), str(option["text"]), influence))
    return DecisionDefinition(
        kind=kind,
        event_type=str(data["event_type"]),
        window_minutes=int(data.get("window_minutes", 60)),
        cooldown_minutes=int(data.get("cooldown_minutes", 1440)),
        anger_threshold=float(data.get("anger_threshold", 50.0)),
        importance=int(data.get("importance", 50)),
        text=str(data["text"]),
        prompt=str(data["prompt"]),
        outcomes=outcomes,
        options=tuple(options),
    )


def _outcome_from_data(kind: str, outcome_id: str, data: dict[str, Any]) -> OutcomeDefinition:
    where = f"outcome {outcome_id} of decision {kind}"
    if "text" not in data:
        raise ValueError(f"Missing text in {where}")
    score = {str(name): float(weight) for name, weight in data.get("score", {}).items()}
    feelings = {str(name): float(delta) for name, delta in data.get("feelings", {}).items()}
    needs = {str(name): float(delta) for name, delta in data.get("needs", {}).items()}
    for label, names, allowed in (
        ("score inputs", score, SCORE_INPUTS), ("feelings", feelings, FEELINGS), ("needs", needs, NEED_NAMES)
    ):
        unknown = names.keys() - set(allowed)
        if unknown:
            raise ValueError(f"Unknown {label} in {where}: {sorted(unknown)}")
    expedition = str(data["expedition"]) if "expedition" in data else None
    if expedition is not None and expedition not in EXPEDITION_CHOICES:
        raise ValueError(f"Unknown expedition choice in {where}: {expedition}")
    gate = str(data["gate"]) if "gate" in data else None
    if gate is not None and gate not in GATE_CHOICES:
        raise ValueError(f"Unknown gate choice in {where}: {gate}")
    raid = str(data["raid"]) if "raid" in data else None
    if raid is not None and raid not in RAID_CHOICES:
        raise ValueError(f"Unknown raid choice in {where}: {raid}")
    return OutcomeDefinition(
        outcome_id=outcome_id,
        score=score,
        text=str(data["text"]),
        interaction=str(data["interaction"]) if "interaction" in data else None,
        needs=needs,
        feelings=feelings,
        memory=str(data["memory"]) if "memory" in data else None,
        takes_job=bool(data.get("takes_job", False)),
        expedition=expedition,
        gate=gate,
        raid=raid,
        builds=bool(data.get("builds", False)),
    )
