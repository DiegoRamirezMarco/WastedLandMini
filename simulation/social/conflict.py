from dataclasses import dataclass


@dataclass
class ConflictState:
    source_id: str
    target_id: str
    intensity: int = 0
    reason: str = ""

    def escalate(self, amount: int = 1) -> None:
        self.intensity = max(0, min(100, self.intensity + amount))
