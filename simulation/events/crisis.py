from dataclasses import dataclass


@dataclass
class Crisis:
    source_id: str
    target_id: str | None
    anger: float
    urgency: int
    intent: str
