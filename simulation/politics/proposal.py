"""What can be put to a settlement to decide, as data, and how deciding goes.

A kind of proposal says what weighs for or against it with each resident and what brings one
of them to raise it unasked. No kind has code of its own beyond what it does once passed.
"""

from dataclasses import dataclass, field
from typing import Any

from simulation.politics import opinion
from simulation.social.relationship import FEELINGS

ENACT_LAW, REPEAL_LAW = "enact_law", "repeal_law"
CALL_ELECTION, CHANGE_GOVERNMENT = "call_election", "change_government"
EXPEL = "expel"
ADOPT_CURRENCY, RETURN_TO_BARTER = "adopt_currency", "return_to_barter"
# What a proposal may be. Each does one thing when it passes, and nothing if it does not.
KINDS = (ENACT_LAW, REPEAL_LAW, CALL_ELECTION, CHANGE_GOVERNMENT, EXPEL, ADOPT_CURRENCY, RETURN_TO_BARTER)
# What may bring a resident to raise each kind unasked.
MOTIVES = {
    CALL_ELECTION: ("loyalty_below", "trust_below", "days_since_vote"),
    CHANGE_GOVERNMENT: ("appeal_above", "trust_below", "days_since_chosen"),
    EXPEL: ("resentment_above", "misdeeds", "days"),
}
# What is felt for whoever a proposal is about that may weigh on it, beside being their kin,
# their partner, or the very one.
ABOUT = (*FEELINGS, "kin", "couple", "self")
# The parts a resident's mind on a proposal is made of, for whoever reads a vote back: what
# they hold and stand to lose, what they feel for who it is about and for who put it, what
# they know that person to have done, loyalty to whoever leads and a grudge against the
# government, fear, what they remember, and what the player said to them.
REASONS = (
    "conviction", "target", "evidence", "proposer", "player", "loyalty", "grudge", "fear", "memory", "lobby",
)


@dataclass(frozen=True)
class ProposalDefinition:
    kind: str
    name: str
    # What it says, with `{described}` for a law at its degree, or `{law}`, `{text}` and `{degree}`
    # for the parts of that, and `{target}`, `{government}` and `{currency}`.
    text: str
    opinion: dict[str, float] = field(default_factory=dict)
    bias: float = 0.0
    # Hours it is talked over before it is decided. None for the usual.
    debate_hours: int | None = None
    motive: dict[str, float] = field(default_factory=dict)


@dataclass(frozen=True)
class ProposalSettings:
    kinds: dict[str, ProposalDefinition] = field(default_factory=dict)
    # Hours a proposal is talked over before those who decide it do, and before whoever leads
    # does when it is theirs alone to decide.
    debate_hours: int = 12
    leader_hours: int = 6
    # How many may wait to be decided at once, the days a matter turned down is left alone, and
    # the days a resident who has raised one waits before raising another.
    pending_limit: int = 3
    again_days: int = 7
    # The days a law just passed is not put to be done away with, nor one just done away with put again.
    undo_days: int = 2
    rest_days: int = 5
    # The days a resident who had something of theirs turned down leaves that very thing be.
    sore_days: int = 28
    # What a resident has to make of a matter to raise it unasked, and of a law to ask for it gone.
    raise_from: float = 0.3
    repeal_from: float = -0.5
    # How far from the middle somebody's mind has to be for them to vote one way or the other,
    # for somebody in the middle for interest in politics.
    margin: float = 0.12
    # How many decided proposals and votes for a seat are kept.
    history: int = 40
    # How much each part of a mind on a proposal counts.
    weights: dict[str, float] = field(
        default_factory=lambda: {
            "proposer": 0.4, "player": 0.5, "loyalty": 0.5, "grudge": 0.5, "fear": 0.7, "memory": 0.4,
            "evidence": 0.5, "softened": 0.5,
        }
    )
    # What is felt for whoever a proposal is about, and how much each feeling counts.
    target: dict[str, float] = field(
        default_factory=lambda: {
            "affection": -1.0, "trust": -0.4, "resentment": 1.2, "fear": 0.4, "kin": -1.5, "couple": -2.0,
            "self": -5.0,
        }
    )
    # Facts that count against somebody when it is put that they be thrown out.
    misdeeds: tuple[str, ...] = ("theft_committed", "fight_started", "death", "election_rigged")
    # The player's word: how much it adds for somebody who leans on it wholly, what being
    # pushed against their own mind adds to their resistance, the resistance from which they
    # do the opposite and how much of the push that is, the share of resistance that wears off
    # each day, how much trust what the player was behind moves by how it turned out, and how
    # much the player's word for a candidate is worth in votes.
    lobby: float = 0.4
    against: float = 12.0
    defiance: float = 60.0
    contrary: float = 0.3
    resistance_fade: float = 0.05
    outcome: float = 12.0
    backing: float = 14.0
    # What comes of a decision: what whoever is thrown out, and those close to them, hold
    # against those who voted for it; what somebody whose proposal is turned down holds
    # against the government; what turning down what most were for costs in legitimacy; what
    # a veto costs; and what being heard, or never being, does.
    aftermath: dict[str, float] = field(
        default_factory=lambda: {
            "voted_out_resentment": 20.0, "voted_out_trust": -15.0, "close_resentment": 10.0,
            "refused_resentment": 4.0, "ignored_legitimacy": -3.0, "veto_legitimacy": -5.0,
            "veto_authoritarianism": 4.0, "heard_legitimacy": 1.0, "unheard_resentment": 2.0,
        }
    )


def _numbers(data: Any, where: str) -> dict[str, float]:
    if not isinstance(data, dict):
        raise ValueError(f"{where} must be an object of numbers")
    return {str(key): float(value) for key, value in data.items()}


def proposal_definition_from_data(kind: str, data: Any) -> ProposalDefinition:
    if kind not in KINDS:
        raise ValueError(f"Nothing is done by a proposal of kind {kind}: one of {KINDS}")
    if not isinstance(data, dict) or not {"name", "text"} <= data.keys():
        raise ValueError(f"Proposal {kind} needs a name and a text")
    weights = _numbers(data.get("opinion", {}), f"The opinion of proposal {kind}")
    opinion.check(weights, f"The opinion of proposal {kind}")
    motive = _numbers(data.get("motive", {}), f"The motive of proposal {kind}")
    unknown = sorted(set(motive) - set(MOTIVES.get(kind, ())))
    if unknown:
        raise ValueError(f"Proposal {kind} has a motive nothing can tell: {unknown}")
    hours = data.get("debate_hours")
    if hours is not None and int(hours) < 0:
        raise ValueError(f"Proposal {kind} is talked over for less than no time")
    return ProposalDefinition(
        kind=kind,
        name=str(data["name"]),
        text=str(data["text"]),
        opinion=weights,
        bias=float(data.get("bias", 0.0)),
        debate_hours=int(hours) if hours is not None else None,
        motive=motive,
    )


def proposal_settings_from_data(data: dict[str, Any]) -> ProposalSettings:
    defaults = ProposalSettings()
    influence = data.get("influence", {})
    target = {**defaults.target, **_numbers(data.get("target", {}), "What is felt for whoever a proposal is about")}
    if any(name not in ABOUT for name in target):
        raise ValueError(f"What is felt for whoever a proposal is about must be one of {ABOUT}")
    settings = ProposalSettings(
        kinds={
            str(kind): proposal_definition_from_data(str(kind), values)
            for kind, values in data.get("kinds", {}).items()
        },
        debate_hours=int(data.get("debate_hours", defaults.debate_hours)),
        leader_hours=int(data.get("leader_hours", defaults.leader_hours)),
        pending_limit=int(data.get("pending_limit", defaults.pending_limit)),
        again_days=int(data.get("again_days", defaults.again_days)),
        undo_days=int(data.get("undo_days", defaults.undo_days)),
        rest_days=int(data.get("rest_days", defaults.rest_days)),
        sore_days=int(data.get("sore_days", defaults.sore_days)),
        raise_from=float(data.get("raise_from", defaults.raise_from)),
        repeal_from=float(data.get("repeal_from", defaults.repeal_from)),
        margin=float(data.get("margin", defaults.margin)),
        history=int(data.get("history", defaults.history)),
        weights={**defaults.weights, **_numbers(data.get("weights", {}), "The weights of a vote")},
        target=target,
        misdeeds=tuple(str(event_type) for event_type in data.get("misdeeds", defaults.misdeeds)),
        lobby=float(influence.get("lobby", defaults.lobby)),
        against=float(influence.get("against", defaults.against)),
        defiance=float(influence.get("defiance", defaults.defiance)),
        contrary=float(influence.get("contrary", defaults.contrary)),
        resistance_fade=float(influence.get("resistance_fade", defaults.resistance_fade)),
        outcome=float(influence.get("outcome", defaults.outcome)),
        backing=float(influence.get("backing", defaults.backing)),
        aftermath={**defaults.aftermath, **_numbers(data.get("aftermath", {}), "What comes of a decision")},
    )
    if settings.debate_hours < 0 or settings.leader_hours < 0 or settings.pending_limit < 1 or settings.margin < 0:
        raise ValueError("A proposal is talked over for no less than no time, one at least may wait, and no margin is negative")
    if not 0.0 <= settings.resistance_fade <= 1.0 or settings.history < 1:
        raise ValueError("Resistance wears off by a share from 0 to 1, and at least one decision is kept")
    return settings
