from dataclasses import dataclass, field


@dataclass
class Memory:
    """Something one resident remembers. `timestamp` is game minutes since day 1, 00:00."""

    text: str
    importance: float
    emotional_value: float
    people: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    timestamp: int = 0
    location_id: str | None = None
