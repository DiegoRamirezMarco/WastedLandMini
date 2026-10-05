from dataclasses import dataclass, field


@dataclass
class Rumor:
    """A fact as one resident passes it to another: less certain than seeing it."""

    text: str
    origin_id: str
    subject_ids: list[str] = field(default_factory=list)
    credibility: float = 0.5
    fact_id: str = ""
