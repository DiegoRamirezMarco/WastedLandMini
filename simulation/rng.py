import hashlib
import random
from collections.abc import Sequence
from typing import Any
from typing import TypeVar

T = TypeVar("T")


class SimulationRNG:
    def __init__(self, seed: int = 1) -> None:
        self.seed = seed
        self._rng = random.Random(seed)

    def random(self) -> float:
        return self._rng.random()

    def randint(self, a: int, b: int) -> int:
        return self._rng.randint(a, b)

    def choice(self, values: Sequence[T]) -> T:
        return self._rng.choice(values)

    def uniform(self, low: float, high: float) -> float:
        """A number anywhere between two, as likely one as another."""
        return self._rng.uniform(low, high)

    def choices(self, values: Sequence[T], weights: Sequence[float]) -> list[T]:
        """One of some things, each as likely as it weighs against the rest: in a list, as
        `random.choices` gives it."""
        return self._rng.choices(values, weights)

    def get_state(self) -> dict[str, Any]:
        return {"seed": self.seed, "state": self._rng.getstate()}

    def set_state(self, state: dict[str, Any]) -> None:
        self.seed = int(state.get("seed", 1))
        raw_state = state.get("state")
        if raw_state is None:
            self._rng.seed(self.seed)
            return
        self._rng.setstate(_tuplify(raw_state))

    @classmethod
    def keyed(cls, seed: int, *parts: object) -> "SimulationRNG":
        """A generator of its own for one question, always the same for the same seed and parts.

        For what has to come out the same whenever it is asked, and in whatever order: drawing
        from it moves no other generator on.
        """
        text = "\x1f".join([str(seed), *(str(part) for part in parts)])
        return cls(int.from_bytes(hashlib.sha256(text.encode("utf-8")).digest()[:8], "big"))

    @classmethod
    def from_state(cls, state: dict[str, Any]) -> "SimulationRNG":
        rng = cls(int(state.get("seed", 1)))
        rng.set_state(state)
        return rng


def _tuplify(value: Any) -> Any:
    if isinstance(value, list):
        return tuple(_tuplify(item) for item in value)
    return value
