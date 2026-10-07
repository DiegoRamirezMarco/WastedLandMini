"""What the player is to each resident, as a layer of its own.

The player is nobody in the settlement, and still each resident has something to make of
them: how far they trust them, how much they resist being pushed, and so how much they lean
on what the player says. Trust moves only with how what the player was behind turned out for
that resident. Resistance comes of being pushed against their own mind, and wears off.
"""

from typing import TYPE_CHECKING

from simulation.ai.decision_system import advice_influence
from simulation.politics.records import PlayerStanding
from simulation.residents.resident import Resident

if TYPE_CHECKING:
    from simulation.world import SimulationWorld

# What a resident did with what the player said to them before a vote: went along with it,
# came half way, took no notice, or did the opposite.
TAKEN, SOFTENED, IGNORED, CONTRARY = "taken", "softened", "ignored", "contrary"
TAKES = (TAKEN, SOFTENED, IGNORED, CONTRARY)


def _bounded(value: float) -> float:
    return max(0.0, min(100.0, value))


class Influence:
    def standing(self, world: "SimulationWorld", resident: Resident) -> PlayerStanding:
        """What the player is to a resident, made the first time it is asked for: in the middle
        for trust, and with nothing to resist yet."""
        standing = world.player_standing.get(resident.resident_id)
        if standing is None:
            standing = world.player_standing[resident.resident_id] = PlayerStanding()
        return standing

    def factor(self, world: "SimulationWorld", resident: Resident) -> float:
        """How much more or less the player's word counts with a resident for what the player
        is to them: 1 for somebody in the middle for trust who has nothing to resist."""
        standing = world.player_standing.get(resident.resident_id)
        if standing is None:
            return 1.0
        return (0.5 + standing.trust / 100.0) * (1.0 - standing.resistance / 100.0)

    def lean(self, world: "SimulationWorld", resident: Resident) -> float:
        """How much a resident leans on what the player says, from 0 for not at all: by how
        they take advice, their taste for being told what to do, and what the player is to them."""
        return advice_influence(resident, 1.0) * world.tastes.heed(world, resident) * self.factor(world, resident)

    def defies(self, world: "SimulationWorld", resident: Resident) -> bool:
        """Whether a resident has been pushed enough to do the opposite of what they are told."""
        return self.standing(world, resident).resistance >= world.registries.proposals.defiance

    def pushed(self, world: "SimulationWorld", resident: Resident, how_far: float) -> None:
        """A resident has been pushed against their own mind, that far from it."""
        standing = self.standing(world, resident)
        standing.resistance = _bounded(standing.resistance + world.registries.proposals.against * (1.0 + how_far))

    def judged(self, world: "SimulationWorld", resident: Resident, went: float) -> None:
        """Something the player was behind has turned out well for a resident, or badly: `went`
        is how well, above nothing, or how badly, below it."""
        standing = self.standing(world, resident)
        standing.trust = _bounded(standing.trust + went)

    def tick_day(self, world: "SimulationWorld") -> None:
        """A day without being pushed: resistance wears off a little."""
        fade = world.registries.proposals.resistance_fade
        for standing in world.player_standing.values():
            standing.resistance *= 1.0 - fade
