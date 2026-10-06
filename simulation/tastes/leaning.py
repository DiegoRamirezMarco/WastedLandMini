"""The leaning a resident comes with for something they have never met."""

from simulation.rng import SimulationRNG
from simulation.tastes.settings import TasteSettings
from simulation.tastes.taste import CATEGORY, HIGHEST, ITEM


def leaning_for(seed: int, resident_id: str, kind: str, name: str, settings: TasteSettings) -> float | None:
    """What a resident makes of a thing before anything has happened to them over it.

    The same settlement, resident and thing always give the same answer, and asking draws
    nothing from the randomness the rest of the simulation runs on. Most leanings are mild and a
    few are strong. For one item in particular most people have none at all, which is None.
    """
    rng = SimulationRNG.keyed(seed, "taste", resident_id, kind, name)
    if kind == ITEM:
        if rng.random() >= settings.quirk_chance:
            return None
        low, high = settings.quirk_range
        strength = low + (high - low) * rng.random()
        return strength if rng.random() < 0.5 else -strength
    spread = (rng.random() - rng.random()) * HIGHEST
    return spread * settings.category_scale if kind == CATEGORY else spread
