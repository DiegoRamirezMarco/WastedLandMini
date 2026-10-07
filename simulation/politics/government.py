"""Kinds of government as data, and the government a settlement has as state.

Every kind is one definition: who may propose, who approves, who votes, how much the leader's
word weighs, how long a term lasts, how the next leader comes to be and how much abuse of
power is put up with. No kind has code of its own.
"""

from dataclasses import dataclass, field
from typing import Any

from simulation.residents.personality import Personality

# What is measured of a settlement that has a government, each from 0 to 100 and by itself.
MEASURES = ("legitimacy", "public_support", "fear", "unrest", "stability", "authoritarianism", "corruption")
# What a resident holds, and does not change: where their politics come from.
LEANINGS = (
    "authoritarian_tolerance",
    "justice_sensitivity",
    "collectivism",
    "individualism",
    "revengefulness",
    "fearfulness",
    "political_interest",
)
# What a resident feels about whoever leads and about the government, which does change.
HOLDS = ("loyalty", "trust", "fear", "resentment")
# Ways the next leader comes to be: voted for by everyone, voted for by the council, whoever
# is strongest, whoever the last one named, and whoever has the most behind them.
ELECTION, COUNCIL, STRONGEST, HEIR, FOLLOWING = "election", "council", "strongest", "heir", "following"
WAYS = (ELECTION, COUNCIL, STRONGEST, HEIR, FOLLOWING)
# Ways that take a vote, and so time to hold.
VOTED_WAYS = (ELECTION, COUNCIL)
LEADER, EVERYONE, NOBODY = "leader", "everyone", "nobody"
WHO = (LEADER, COUNCIL, EVERYONE, NOBODY)


@dataclass(frozen=True)
class PoliticsResult:
    """Whether something the player put to the settlement went ahead, and what there is to say of it."""

    ok: bool
    message: str


@dataclass(frozen=True)
class GovernmentDefinition:
    """One kind of government."""

    government_id: str
    name: str
    # The role whoever leads holds, and the one of those who sit on the council. None where
    # there is no such thing.
    leader_role: str | None = None
    council_role: str | None = None
    council_seats: int = 0
    # Who may propose, who approves, and who votes: `leader`, `council`, `everyone` or `nobody`.
    proposes: str = EVERYONE
    approves: str = EVERYONE
    votes: str = EVERYONE
    # The share of those who approve that it takes, how many votes the leader's word is worth,
    # and whether the leader may refuse what was approved.
    approval: float = 0.5
    leader_weight: float = 1.0
    veto: bool = False
    # Days a term lasts. 0 where nobody is ever put to a vote again.
    term_days: int = 0
    # The ways the next leader comes to be, tried in this order.
    succession: tuple[str, ...] = ()
    # How much abuse of power is put up with, from 0 to 100.
    abuse_tolerance: float = 50.0
    # Measures a settlement starts with under it.
    starts: dict[str, float] = field(default_factory=dict)
    # What draws a resident to it: how much each of their leanings counts for or against.
    appeal: dict[str, float] = field(default_factory=dict)


@dataclass(frozen=True)
class RoleDefinition:
    """A role a resident may hold, and what whoever holds it is called by the gender they go by."""

    role_id: str
    name: str
    names: dict[str, str] = field(default_factory=dict)

    def called(self, gender: str) -> str:
        return self.names.get(gender, self.name)


@dataclass(frozen=True)
class PoliticalReaction:
    """What learning that whoever governs did a thing does to somebody, and to the settlement."""

    # Changes to what the resident holds, before who they are is counted in.
    holds: dict[str, float] = field(default_factory=dict)
    # Changes to the settlement's measures if everybody came to know of it.
    measures: dict[str, float] = field(default_factory=dict)
    # How many times over it counts with whoever it was done to.
    victim: float = 2.0


@dataclass(frozen=True)
class PoliticsSettings:
    governments: dict[str, GovernmentDefinition] = field(default_factory=dict)
    roles: dict[str, RoleDefinition] = field(default_factory=dict)
    # How many have to live in a settlement for it to choose a government, the hours it takes
    # them to settle on one, and the hours it takes to hold a vote for a seat left empty.
    founding_residents: int = 3
    choosing_hours: int = 12
    election_hours: int = 24
    # How much the player's proposal adds to a kind's appeal, for someone who heeds advice.
    proposal_weight: float = 0.6
    # Where each leaning comes from: for each, how much every side of a way of being moves it
    # from the middle. How far a leaning of their own may fall from that, either way.
    leanings: dict[str, dict[str, float]] = field(default_factory=dict)
    own_spread: float = 25.0
    # Trust in the government to begin with, and what having wanted the kind that was chosen,
    # or another, adds to it.
    trust_start: float = 50.0
    backed_trust: float = 10.0
    unbacked_trust: float = -10.0
    # Loyalty to whoever leads: where it starts, how much what is felt for them and their
    # charisma add, what having backed them adds, and how fast it comes back to that each day.
    loyalty_base: float = 35.0
    loyalty_from: dict[str, float] = field(
        default_factory=lambda: {"affection": 0.3, "trust": 0.3, "resentment": -0.3, "fear": -0.1}
    )
    loyalty_charisma: float = 0.4
    backed_loyalty: float = 15.0
    loyalty_drift: float = 0.05
    # The share of fear and of resentment that goes each day, in someone in the middle.
    fear_fade: float = 0.03
    resentment_fade: float = 0.02
    # Which leaning makes each thing held move more: from half as much to half as much again.
    sways: dict[str, str] = field(
        default_factory=lambda: {
            "fear": "fearfulness",
            "resentment": "revengefulness",
            "trust": "justice_sensitivity",
            "loyalty": "justice_sensitivity",
        }
    )
    # How much of each thing held, and of each leaning, goes into doing as the government says.
    obedience: dict[str, float] = field(
        default_factory=lambda: {"loyalty": 0.4, "fear": 0.5, "trust": 0.2, "authoritarian_tolerance": 0.2}
    )
    # What counts in each way of coming to lead.
    ways: dict[str, dict[str, float]] = field(default_factory=dict)
    # What a leader coming to the seat by each way does to the measures.
    seated: dict[str, dict[str, float]] = field(default_factory=dict)
    # Legitimacy a government has with nobody having wanted it, what losing or changing a
    # leader does to stability, and what a day with the seat empty costs.
    legitimacy_floor: float = 30.0
    change_stability: float = -10.0
    lost_stability: float = -15.0
    vacancy_legitimacy: float = -2.0
    vacancy_stability: float = 20.0
    # How fast unrest and stability come to where things put them, each day; how much low
    # support adds to unrest; and the share of corruption that is forgotten each day.
    unrest_drift: float = 0.25
    unrest_from_support: float = 0.5
    stability_drift: float = 0.2
    corruption_fade: float = 0.01
    # What learning of a thing done by whoever governs does, by the kind of event.
    reactions: dict[str, PoliticalReaction] = field(default_factory=dict)
    # How much faster or slower everybody works under a leader at either end of leadership,
    # for someone wholly loyal to them.
    leadership_pace: float = 0.06
    # How worn a leader has to be, or how little support there has to be, to think of resigning.
    resign_stress: float = 85.0
    resign_support: float = 25.0


@dataclass
class GovernmentState:
    """The government a settlement has. None of it until one is chosen."""

    kind: str | None = None
    leader: str | None = None
    council: list[str] = field(default_factory=list)
    measures: dict[str, float] = field(default_factory=lambda: {measure: 0.0 for measure in MEASURES})
    # The day it was chosen, and the day the term that is running began.
    chosen_on: int | None = None
    term_began: int = 0
    # Game minute at which the residents settle on a kind, while they are making up their
    # minds, and the kind the player has put to them all.
    choosing_until: int | None = None
    proposed: str | None = None
    # Game minute at which a vote that has been called is held.
    election_at: int | None = None
    # Game minute since which the leader's seat stands empty.
    vacant_since: int | None = None
    # Whoever the leader would have follow them, and whoever has just stepped down.
    heir: str | None = None
    resigned: str | None = None


def _numbers(data: Any, where: str) -> dict[str, float]:
    if not isinstance(data, dict):
        raise ValueError(f"{where} must be an object of numbers")
    return {str(key): float(value) for key, value in data.items()}


def _government(government_id: str, data: Any, roles: dict[str, RoleDefinition]) -> GovernmentDefinition:
    if not isinstance(data, dict) or "name" not in data:
        raise ValueError(f"Government {government_id} needs a name")
    definition = GovernmentDefinition(
        government_id=government_id,
        name=str(data["name"]),
        leader_role=str(data["leader_role"]) if data.get("leader_role") else None,
        council_role=str(data["council_role"]) if data.get("council_role") else None,
        council_seats=int(data.get("council_seats", 0)),
        proposes=str(data.get("proposes", EVERYONE)),
        approves=str(data.get("approves", EVERYONE)),
        votes=str(data.get("votes", EVERYONE)),
        approval=float(data.get("approval", 0.5)),
        leader_weight=float(data.get("leader_weight", 1.0)),
        veto=bool(data.get("veto", False)),
        term_days=int(data.get("term_days", 0)),
        succession=tuple(str(way) for way in data.get("succession", [])),
        abuse_tolerance=float(data.get("abuse_tolerance", 50.0)),
        starts=_numbers(data.get("starts", {}), f"What government {government_id} starts with"),
        appeal=_numbers(data.get("appeal", {}), f"The appeal of government {government_id}"),
    )
    for who in (definition.proposes, definition.approves, definition.votes):
        if who not in WHO:
            raise ValueError(f"Government {government_id} leaves something to {who}: it must be one of {WHO}")
    if any(way not in WAYS for way in definition.succession):
        raise ValueError(f"Government {government_id} has an unknown way of succession: one of {WAYS}")
    if (definition.leader_role is None) != (not definition.succession):
        raise ValueError(f"Government {government_id} needs a way of succession if it has a leader, and none if not")
    if definition.council_seats < 0 or (definition.council_seats > 0) != (definition.council_role is not None):
        raise ValueError(f"Government {government_id} needs a role for its council if it has seats, and none if not")
    for role in (definition.leader_role, definition.council_role):
        if role is not None and role not in roles:
            raise ValueError(f"Government {government_id} names a role nobody has defined: {role}")
    if any(measure not in MEASURES for measure in definition.starts):
        raise ValueError(f"Government {government_id} starts with an unknown measure: one of {MEASURES}")
    if any(leaning not in LEANINGS for leaning in definition.appeal):
        raise ValueError(f"Government {government_id} appeals to an unknown leaning: one of {LEANINGS}")
    if not 0.0 <= definition.abuse_tolerance <= 100.0 or not 0.0 < definition.approval <= 1.0:
        raise ValueError(f"Government {government_id} has a tolerance outside 0 to 100, or an approval outside 0 to 1")
    if definition.term_days < 0:
        raise ValueError(f"Government {government_id} has a term of less than no days")
    return definition


def politics_settings_from_data(data: dict[str, Any]) -> PoliticsSettings:
    defaults = PoliticsSettings()
    roles = {
        str(role_id): RoleDefinition(
            str(role_id),
            str(values["name"]),
            {str(gender): str(name) for gender, name in values.get("names", {}).items()},
        )
        for role_id, values in data.get("roles", {}).items()
    }
    profile = data.get("profile", {})
    loyalty = data.get("loyalty", {})
    measures = data.get("measures", {})
    sides = set(vars(Personality()))
    leanings = {
        str(leaning): _numbers(weights, f"Where {leaning} comes from")
        for leaning, weights in profile.get("leanings", {}).items()
    }
    for leaning, weights in leanings.items():
        if leaning not in LEANINGS or any(side not in sides for side in weights):
            raise ValueError(f"The leaning {leaning} must be one of {LEANINGS}, from sides of a way of being")
    reactions = {
        str(event_type): PoliticalReaction(
            holds=_numbers(rule.get("holds", {}), f"The political reaction to {event_type}"),
            measures=_numbers(rule.get("measures", {}), f"The political reaction to {event_type}"),
            victim=float(rule.get("victim", 2.0)),
        )
        for event_type, rule in data.get("reactions", {}).items()
    }
    for event_type, rule in reactions.items():
        if any(held not in HOLDS for held in rule.holds) or any(measure not in MEASURES for measure in rule.measures):
            raise ValueError(f"The political reaction to {event_type} changes something nobody holds or measures")
    ways = {str(way): _numbers(weights, f"The way {way}") for way, weights in data.get("ways", {}).items()}
    seated = {str(way): _numbers(change, f"Being seated by {way}") for way, change in data.get("seated", {}).items()}
    if any(way not in WAYS for way in (*ways, *seated)):
        raise ValueError(f"A way of coming to lead must be one of {WAYS}")
    settings = PoliticsSettings(
        governments={
            str(government_id): _government(str(government_id), values, roles)
            for government_id, values in data.get("governments", {}).items()
        },
        roles=roles,
        founding_residents=int(data.get("founding_residents", defaults.founding_residents)),
        choosing_hours=int(data.get("choosing_hours", defaults.choosing_hours)),
        election_hours=int(data.get("election_hours", defaults.election_hours)),
        proposal_weight=float(data.get("proposal_weight", defaults.proposal_weight)),
        leanings=leanings,
        own_spread=float(profile.get("own_spread", defaults.own_spread)),
        trust_start=float(profile.get("trust_start", defaults.trust_start)),
        backed_trust=float(profile.get("backed_trust", defaults.backed_trust)),
        unbacked_trust=float(profile.get("unbacked_trust", defaults.unbacked_trust)),
        loyalty_base=float(loyalty.get("base", defaults.loyalty_base)),
        loyalty_from=_numbers(loyalty.get("from", defaults.loyalty_from), "Where loyalty comes from"),
        loyalty_charisma=float(loyalty.get("charisma", defaults.loyalty_charisma)),
        backed_loyalty=float(loyalty.get("backed", defaults.backed_loyalty)),
        loyalty_drift=float(loyalty.get("drift", defaults.loyalty_drift)),
        fear_fade=float(profile.get("fear_fade", defaults.fear_fade)),
        resentment_fade=float(profile.get("resentment_fade", defaults.resentment_fade)),
        sways={str(held): str(leaning) for held, leaning in profile.get("sways", defaults.sways).items()},
        obedience=_numbers(profile.get("obedience", defaults.obedience), "What goes into obeying"),
        ways=ways,
        seated=seated,
        legitimacy_floor=float(measures.get("legitimacy_floor", defaults.legitimacy_floor)),
        change_stability=float(measures.get("change_stability", defaults.change_stability)),
        lost_stability=float(measures.get("lost_stability", defaults.lost_stability)),
        vacancy_legitimacy=float(measures.get("vacancy_legitimacy", defaults.vacancy_legitimacy)),
        vacancy_stability=float(measures.get("vacancy_stability", defaults.vacancy_stability)),
        unrest_drift=float(measures.get("unrest_drift", defaults.unrest_drift)),
        unrest_from_support=float(measures.get("unrest_from_support", defaults.unrest_from_support)),
        stability_drift=float(measures.get("stability_drift", defaults.stability_drift)),
        corruption_fade=float(measures.get("corruption_fade", defaults.corruption_fade)),
        reactions=reactions,
        leadership_pace=float(data.get("leadership_pace", defaults.leadership_pace)),
        resign_stress=float(data.get("resign_stress", defaults.resign_stress)),
        resign_support=float(data.get("resign_support", defaults.resign_support)),
    )
    if settings.founding_residents < 1 or settings.choosing_hours < 0 or settings.election_hours < 0:
        raise ValueError("A government takes one resident or more, and no less than no time to choose or to vote")
    if any(held not in HOLDS or leaning not in LEANINGS for held, leaning in settings.sways.items()):
        raise ValueError(f"What sways a thing held must be one of {LEANINGS}, for one of {HOLDS}")
    if any(name not in (*HOLDS, *LEANINGS) for name in settings.obedience):
        raise ValueError("Obeying comes of what a resident holds and of their leanings, and of nothing else")
    for drift in (settings.loyalty_drift, settings.unrest_drift, settings.stability_drift):
        if not 0.0 <= drift <= 1.0:
            raise ValueError("What comes back to its place each day does so by a share from 0 to 1")
    return settings
