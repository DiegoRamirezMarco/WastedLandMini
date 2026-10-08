"""What politics keeps a record of: laws in force, proposals, votes, elections, what the player
is to each resident, and whoever was thrown out. Plain state, saved by stable IDs."""

from dataclasses import dataclass, field

# Who a proposal is by, when it is the player's.
PLAYER = "@player"
YES, NO, ABSTAIN = "yes", "no", "abstain"
VOTES = (YES, NO, ABSTAIN)
# Where a proposal stands: waiting to be decided, passed as it was put, passed at a milder
# degree, turned down, refused by whoever leads after it had passed, or taken up by nobody.
PENDING, ACCEPTED, CHANGED, REJECTED, VETOED, DROPPED = (
    "pending", "accepted", "changed", "rejected", "vetoed", "dropped",
)
STATUSES = (PENDING, ACCEPTED, CHANGED, REJECTED, VETOED, DROPPED)
PASSED = (ACCEPTED, CHANGED)
# The seat a vote is for.
LEADER_SEAT, COUNCIL_SEAT = "leader", "council"


@dataclass
class LawInForce:
    """A law the settlement has, at the degree it was passed at."""

    law_id: str
    degree: int = 0
    # What it names, when it names something: the `item` nobody is to eat.
    params: dict[str, str] = field(default_factory=dict)
    # The day it was passed, and who proposed it: a resident's ID, or the player's.
    since: int = 0
    by: str | None = None
    # Whether the player put it forward or spoke up for it.
    pushed: bool = False


@dataclass
class Ballot:
    """How one resident voted on a proposal, and why: what weighed most, strongest first."""

    voter: str
    vote: str
    score: float = 0.0
    reasons: list[str] = field(default_factory=list)


@dataclass
class Proposal:
    """Something put to the settlement to decide, by a resident or by the player."""

    proposal_id: str
    kind: str
    # Who put it: a resident's ID, or the player's. And the resident who made it theirs, when
    # it was the player's: nobody outside the settlement lays anything before it.
    by: str = PLAYER
    sponsor: str | None = None
    # What it is about: a law and the degree of it, a resident, a kind of government.
    law: str | None = None
    degree: int = 0
    target: str | None = None
    government: str | None = None
    params: dict[str, str] = field(default_factory=dict)
    # What it says, put into words when it was raised.
    text: str = ""
    raised_at: int = 0
    decides_at: int = 0
    # What the player's word added for or against it with each resident they spoke to.
    lobbied: dict[str, float] = field(default_factory=dict)
    # Whether the player spoke up for it with anybody.
    pushed: bool = False
    status: str = PENDING
    decided_at: int | None = None
    # The degree it passed at, when it passed, and how each of those who decided it voted.
    passed_degree: int | None = None
    ballots: list[Ballot] = field(default_factory=list)
    # Whether it was voted by a show of hands, so that who voted how is known.
    open_ballot: bool = True


@dataclass
class ElectionRecord:
    """A vote for a seat, as it came out."""

    day: int
    at: int
    seat: str = LEADER_SEAT
    way: str = "election"
    candidates: list[str] = field(default_factory=list)
    # Votes for each candidate as they were given out. Under `rigged` they are not as cast.
    tally: dict[str, int] = field(default_factory=dict)
    winner: str | None = None
    # Who each voter backed. Known to all after a show of hands, and only to the world otherwise.
    backed: dict[str, str] = field(default_factory=dict)
    open_ballot: bool = True
    # Who had the count come out their way, if anybody did, and who said afterwards that somebody had.
    rigged_by: str | None = None
    claimed_by: list[str] = field(default_factory=list)


@dataclass
class PlayerStanding:
    """What the player is to one resident. Trust moves only with how what the player was
    behind turned out for them. Resistance comes of being pushed against their own mind, and
    wears off."""

    trust: float = 50.0
    resistance: float = 0.0


@dataclass
class Exile:
    """Somebody thrown out for good: gone from the map, the posts and the beds, and not dead."""

    resident_id: str
    name: str
    at: int = 0
    why: str = ""
    # The game minute at which they are heard of again, at the gate or with raiders. None once
    # they have been, or if they never are.
    back_at: int | None = None
    # What they held against the government as they left, from 0 to 1, and how many times
    # they have come to the gate and found nobody.
    grudge: float = 0.0
    tries: int = 0
    # Who they were, for them to be the same if they are let back in.
    person: dict = field(default_factory=dict)
    # Whether they were let back in, and so are no longer out.
    returned: bool = False
