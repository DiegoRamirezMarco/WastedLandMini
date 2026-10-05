from simulation.residents.resident import Resident


def advice_influence(resident: Resident, advice_strength: float) -> float:
    resistance = resident.personality.impulsiveness / 100.0
    return advice_strength * (1.0 - 0.5 * resistance)
