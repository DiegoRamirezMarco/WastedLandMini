"""Politics: who is in charge of the settlement, what it decides, and what its people make of it.

The player is nobody in the settlement, and runs three things in it all the same (S45): its
laws, its punishments and what it trades with. How a law of theirs comes into force is the
government's: at once where one person decides, by a vote where more do. Who leads, how
people vote and what they make of it are the residents' own.
"""

from collections.abc import Mapping
from typing import TYPE_CHECKING

from simulation.knowledge.fact import Fact
from simulation.politics.election import Elections
from simulation.politics.exile import ExileSystem
from simulation.politics.government import PoliticsResult
from simulation.politics.influence import Influence
from simulation.politics.law_system import Laws
from simulation.politics.leadership import Leadership
from simulation.politics.legitimacy import Legitimacy
from simulation.politics.protest import Protests
from simulation.politics.voting import Voting
from simulation.residents.resident import Resident

if TYPE_CHECKING:
    from simulation.world import SimulationWorld


class PoliticsSystem:
    leadership = Leadership()
    legitimacy = Legitimacy()
    laws = Laws()
    voting = Voting()
    elections = Elections()
    influence = Influence()
    exile = ExileSystem()
    protests = Protests()

    def tick(self, world: "SimulationWorld") -> None:
        """One minute of politics, and at the start of each day what a day does."""
        self.leadership.tick(world)
        self.voting.tick(world)
        self.laws.tick(world)
        self.exile.tick(world)
        self.protests.tick(world)
        if world.clock.hour == 0 and world.clock.minute == 0:
            self.influence.tick_day(world)
            if world.government.kind is not None:
                self.legitimacy.tick_day(world)
                self.leadership.tick_day(world)
                self.laws.tick_day(world)

    def propose_government(self, world: "SimulationWorld", government_id: str) -> PoliticsResult:
        """The player's one proposal of a kind of government, while the settlement chooses."""
        return self.leadership.propose(world, government_id)

    def choose_government(self, world: "SimulationWorld", government_id: str) -> PoliticsResult:
        """The player says how the settlement is governed, and it is."""
        return self.leadership.choose(world, government_id)

    def propose(
        self,
        world: "SimulationWorld",
        kind: str,
        law: str | None = None,
        degree: int | None = None,
        target: str | None = None,
        government: str | None = None,
        params: Mapping[str, str] | None = None,
    ) -> PoliticsResult:
        """The player puts something to the settlement, for those who decide to decide."""
        return self.voting.propose(world, kind, law, degree, target, government, params)

    def lobby(self, world: "SimulationWorld", proposal_id: str, resident_id: str, stance: str) -> PoliticsResult:
        """The player speaks to one of those who will decide a proposal, for it or against it."""
        return self.voting.lobby(world, proposal_id, resident_id, stance)

    def back_candidate(self, world: "SimulationWorld", resident_id: str, candidate_id: str) -> PoliticsResult:
        """The player speaks to a resident for one of those who stand in the vote that has been called."""
        return self.elections.back(world, resident_id, candidate_id)

    def learned(self, world: "SimulationWorld", resident: Resident, fact: Fact, credibility: float) -> None:
        """A resident has just learned a fact: what it does to their politics, if anything."""
        self.legitimacy.learned(world, resident, fact, credibility)

    def leader(self, world: "SimulationWorld") -> Resident | None:
        """Whoever leads the settlement, if anybody does and they are alive."""
        return world.residents.get(world.government.leader or "")

    def work_pace(self, world: "SimulationWorld", resident: Resident) -> float:
        """How much faster or slower a resident works for who leads them: a good leader gets
        more out of people and a poor one less, and more so out of whoever is loyal to them."""
        leader = self.leader(world)
        if leader is None or leader is resident or leader.away:
            return 1.0
        pace = world.registries.politics.leadership_pace
        if pace == 0.0 or leader.personality.leadership == 50.0:
            return 1.0
        loyalty = self.legitimacy.profile(world, resident).loyalty / 100.0
        return 1.0 + (leader.personality.leadership - 50.0) / 50.0 * pace * loyalty
