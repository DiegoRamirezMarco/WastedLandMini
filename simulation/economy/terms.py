"""How a settlement trades: by barter, a thing for a thing, or with a currency of its own making."""

from dataclasses import dataclass, field

NAME_LENGTH = 16


@dataclass
class Currency:
    """What a settlement counts its prices, its wages and its fund in. The player names it."""

    currency_id: str
    # What a sum of it is called, and what one of it is: `vales` and `vale`.
    name: str
    singular: str

    def amount(self, value: float) -> str:
        """A sum of it in words, in whole units, such as `1 vale` or `12 vales`."""
        whole = int(value)
        return f"{whole} {self.singular if whole == 1 else self.name}"


@dataclass
class TradingState:
    """How the settlement trades right now, and what it holds in coin as a whole."""

    # The currency the settlement has made, if it ever made one. It may not be the way it trades.
    currency: Currency | None = None
    # Whether things are paid for with it. Otherwise it is barter: a thing for a thing.
    in_use: bool = False
    # What the settlement holds of it as a whole, apart from what anybody owns.
    fund: float = 0.0
    # How many currencies have been made here, for their IDs.
    currency_count: int = 0
    # Day on which the residents were last asked how they would trade.
    asked_on: int | None = None
    # How many swaps each resident has had turned down at a counter since they last made
    # something of it, by resident ID.
    refusals: dict[str, int] = field(default_factory=dict)


@dataclass
class Debt:
    """Credit one resident has lent another, until it is paid back."""

    debtor_id: str
    creditor_id: str
    amount: float
    # Day on which it was lent.
    since: int
    # True once it has gone unpaid long enough to tell on what the lender thinks of them.
    overdue: bool = False


@dataclass(frozen=True)
class TradeResult:
    """Whether something the player set about came off, and what there is to say of it."""

    ok: bool
    message: str


def tidy_currency_name(name: str) -> str:
    """A currency's name as the settlement keeps it: no stray spaces, and short enough to show."""
    return " ".join(name.split())[:NAME_LENGTH].strip()


def singular_of(name: str) -> str:
    """What one of a currency is called when the player has not said: its name less a final `s`."""
    return name[:-1] if len(name) > 2 and name.endswith("s") else name
