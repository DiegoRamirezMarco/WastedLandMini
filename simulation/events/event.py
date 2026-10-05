import re
from dataclasses import dataclass, field

# In Spanish "y" becomes "e" before a word that starts with the sound of an i.
_Y_BEFORE_I = re.compile(r"\by (?=[IiÍí]|[Hh][iIíÍ])")


def euphonic(text: str) -> str:
    """Fix the conjunction in a text put together from names: `Tomás y Inés` reads `Tomás e Inés`."""
    return _Y_BEFORE_I.sub("e ", text)


@dataclass
class DomainEvent:
    event_type: str
    importance: int
    text: str
    participants: list[str] = field(default_factory=list)
    witnesses: list[str] = field(default_factory=list)
    location_id: str | None = None
    # Game minutes since day 1, 00:00. Set by the world when the event is emitted.
    timestamp: int = 0
