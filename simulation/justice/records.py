"""What the settlement keeps of its trials and punishments. Plain state, saved by stable IDs."""

from dataclasses import dataclass, field

# The six steps of a trial, in order, and where one that is over stands.
ACCUSATION, EVIDENCE, WITNESSES, DEFENCE, VERDICT, PUNISHMENT = (
    "accusation", "evidence", "witnesses", "defence", "verdict", "punishment",
)
STEPS = (ACCUSATION, EVIDENCE, WITNESSES, DEFENCE, VERDICT, PUNISHMENT)
CLOSED = "closed"
GUILTY, INNOCENT = "guilty", "innocent"


@dataclass
class Trial:
    """Somebody tried for something that is known of them, from the accusation to the punishment."""

    trial_id: str
    accused: str
    # Who accused them: a resident's ID, or the player's.
    accuser: str
    # The kind of thing it is, and the fact it rests on.
    offence: str
    fact_id: str
    opened_at: int = 0
    # The step it has reached, and the game minute at which it goes on to the next.
    step: str = ACCUSATION
    next_at: int = 0
    # Who spoke to having seen it, and how each of those who judged held the accused: guilty or not.
    witnesses: list[str] = field(default_factory=list)
    ballots: dict[str, bool] = field(default_factory=dict)
    verdict: str | None = None
    # What they were given, once the player has said.
    punishment: str | None = None
    closed_at: int | None = None

    @property
    def open(self) -> bool:
        return self.step != CLOSED

    @property
    def awaiting_sentence(self) -> bool:
        """Whether they have been found guilty and it waits to be said what they are given."""
        return self.step == PUNISHMENT and self.verdict == GUILTY and self.punishment is None


@dataclass
class Sentence:
    """A punishment that goes on for a time: locked up, in the stocks, or working for everybody."""

    resident_id: str
    punishment: str
    trial_id: str
    # The game minute at which it is over.
    until: int
    # Where it is served: the ID of the building or of the object. None for one served anywhere.
    place_id: str | None = None
    # The day on which it was last said that there was nothing to give them.
    unfed_on: int = 0


@dataclass
class PunishmentRecord:
    """A punishment carried out: who, for what, to what, who was there and how each took it."""

    resident_id: str
    name: str
    offence: str
    punishment: str
    at: int
    trial_id: str = ""
    # Who saw it, or for one not done in public who was there to hear of it, and which of
    # them were kin of the condemned or friends of theirs.
    present: list[str] = field(default_factory=list)
    kin: list[str] = field(default_factory=list)
    friends: list[str] = field(default_factory=list)
    # How each took it, by resident ID.
    reactions: dict[str, str] = field(default_factory=dict)
    # Whether they were under age.
    child: bool = False


@dataclass
class Ration:
    """What a prisoner is given each day: how many meals and of what, how many drinks and of
    what. An item left unsaid is whatever of the kind the settlement has most of."""

    meals: int = 3
    drinks: int = 2
    food: str = ""
    drink: str = ""


@dataclass
class JusticeState:
    """The trials there have been, the sentences being served and what has been carried out."""

    trials: dict[str, Trial] = field(default_factory=dict)
    trial_count: int = 0
    sentences: list[Sentence] = field(default_factory=list)
    history: list[PunishmentRecord] = field(default_factory=list)
    # What prisoners are given. None until the player says, when it is what the data says.
    ration: Ration | None = None
    # Who is making up their mind whether to accuse somebody, and of what: the accused and the fact.
    weighing: dict[str, tuple[str, str]] = field(default_factory=dict)
    # Whoever was exiled and is at the gate asking to come back, by their ID.
    at_gate: str | None = None
