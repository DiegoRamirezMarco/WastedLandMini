from collections.abc import Mapping
from dataclasses import dataclass

NEED_NAMES = ("hunger", "thirst", "tiredness", "social", "stress", "boredom")
# Wanting to be entertained (S62), and how fast it sets in, a minute awake.
BOREDOM = "boredom"
BOREDOM_PACE = 0.06
# Where it stands for whoever has never been asked: in a new settlement, and in a save
# from before there was such a thing.
BOREDOM_START = 15.0
# Needs of the body. Only these can cut short what a resident is doing or keep them from work.
BODILY_NEEDS = ("hunger", "thirst", "tiredness")
# A bodily need this high cuts short whatever long thing a resident is doing: hunger wakes you up.
URGENT_NEED = 85.0
# Whoever keeps to a bed to mend gets up for less: they may be there for days, and are in no
# state to wait until it hurts.
MENDING_NEED = 75.0


def _clamp(value: float) -> float:
    return max(0.0, min(100.0, value))


@dataclass
class Needs:
    hunger: float = 15.0
    thirst: float = 12.0
    tiredness: float = 10.0
    social: float = 20.0
    stress: float = 10.0
    # Wanting to be entertained (S62): time and work raise it, pastimes, things and company lower it.
    boredom: float = BOREDOM_START

    def step(self, minutes: int, resting: bool = False) -> None:
        """Let needs grow with time. Asleep, the body and the wish for company run at half pace,
        and nobody is bored."""
        pace = 0.5 if resting else 1.0
        self.hunger = _clamp(self.hunger + 0.08 * pace * minutes)
        self.thirst = _clamp(self.thirst + 0.03 * pace * minutes)
        self.tiredness = _clamp(self.tiredness + 0.07 * minutes)
        self.social = _clamp(self.social + 0.05 * pace * minutes)
        if not resting:
            self.boredom = _clamp(self.boredom + BOREDOM_PACE * minutes)

    def apply(self, effects: Mapping[str, float]) -> None:
        """Add `effects` to the needs they name. Names that are not needs are ignored."""
        for need, delta in effects.items():
            if need in NEED_NAMES:
                setattr(self, need, _clamp(getattr(self, need) + delta))
