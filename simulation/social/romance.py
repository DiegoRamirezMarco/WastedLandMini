from dataclasses import dataclass


@dataclass
class RomanceIntent:
    source_id: str
    target_id: str
    confidence: float
    importance: int = 60
