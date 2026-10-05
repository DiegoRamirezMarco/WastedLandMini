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
    def from_state(cls, state: dict[str, Any]) -> "SimulationRNG":
        rng = cls(int(state.get("seed", 1)))
        rng.set_state(state)
        return rng


def _tuplify(value: Any) -> Any:
    if isinstance(value, list):
        return tuple(_tuplify(item) for item in value)
    return value
