from dataclasses import dataclass, field


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
