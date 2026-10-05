from collections.abc import Mapping
from dataclasses import dataclass

NEED_NAMES = ("hunger", "thirst", "tiredness", "social", "stress")
# Needs of the body. Only these can cut short what a resident is doing or keep them from work.
BODILY_NEEDS = ("hunger", "thirst", "tiredness")
# A bodily need this high cuts short whatever long thing a resident is doing: hunger wakes you up.
URGENT_NEED = 85.0


def _clamp(value: float) -> float:
    return max(0.0, min(100.0, value))


@dataclass
class Needs:
    hunger: float = 15.0
    thirst: float = 12.0
    tiredness: float = 10.0
    social: float = 20.0
    stress: float = 10.0

    def step(self, minutes: int, resting: bool = False) -> None:
        """Let needs grow with time. Asleep, the body and the wish for company run at half pace."""
        pace = 0.5 if resting else 1.0
        self.hunger = _clamp(self.hunger + 0.08 * pace * minutes)
        self.thirst = _clamp(self.thirst + 0.03 * pace * minutes)
        self.tiredness = _clamp(self.tiredness + 0.07 * minutes)
        self.social = _clamp(self.social + 0.05 * pace * minutes)

    def apply(self, effects: Mapping[str, float]) -> None:
        """Add `effects` to the needs they name. Names that are not needs are ignored."""
        for need, delta in effects.items():
            if need in NEED_NAMES:
                setattr(self, need, _clamp(getattr(self, need) + delta))
