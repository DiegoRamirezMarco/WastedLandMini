"""Votes for a seat: who stands, what the player's word for one of them is worth, a count that
is made to come out somebody's way, and what a result leaves behind it.

Who stands goes by how much politics is to them, how readily they win people over, how well
they lead and how they are thought of. A result is kept, and remembered by those who took
part: whoever lost, whoever backed them, and whoever says there was cheating, with reason or
without.
"""

from collections import Counter
from typing import TYPE_CHECKING

from simulation.memory.memory import Memory
from simulation.politics.government import (
    COUNCIL,
    ELECTION,
    OPEN,
    VOTED_WAYS,
    GovernmentDefinition,
    PoliticsResult,
)
from simulation.politics.political_event import PoliticalEvent
from simulation.politics.records import LEADER_SEAT, ElectionRecord
from simulation.residents.resident import Resident

if TYPE_CHECKING:
    from simulation.world import SimulationWorld

# What whoever leads and stands to lose a vote makes up their mind about.
RIG = "rig_election"
RIGGED_IMPORTANCE = 70
CLAIMED_IMPORTANCE = 60
BACKED_IMPORTANCE = 30
VOTED_MEMORY = 35.0
LOST_MEMORY = 65.0
# How near a result has to be for whoever lost it to find it hard to believe, in votes.
CLOSE_RESULT = 1
# What a result that was near, and one that was not as it was cast, add to how sore a loser is.
CLOSE_SORENESS = 0.4
ROBBED_SORENESS = 0.5
# How far backing somebody against a resident's own choice pushes them.
BACKING_PUSH = 0.5


class Elections:
    # ----- who stands -----

    def will(self, world: "SimulationWorld", resident: Resident) -> float:
        """How much a resident wants a seat: above nothing for more than most."""
        weights = world.registries.politics.ways.get(ELECTION, {})
        sides = resident.personality
        interest = world.politics.legitimacy.profile(world, resident).political_interest
        leadership = world.politics.leadership
        liked = (
            leadership.felt_for(world, resident, "affection")
            + leadership.felt_for(world, resident, "trust")
            - leadership.felt_for(world, resident, "resentment")
        )
        return (
            weights.get("interest", 1.0) * (interest - 50.0)
            + weights.get("charisma", 0.4) * (sides.charisma - 50.0)
            + weights.get("leadership", 0.3) * (sides.leadership - 50.0)
            + weights.get("liked", 0.3) * liked
        )

    def candidates(
        self, world: "SimulationWorld", exclude: tuple[str, ...] | list[str] = (), at_least: int = 2
    ) -> list[Resident]:
        """Whoever puts themselves forward for a seat: those who want one enough, and whoever
        leads already. With fewer than it takes to have a choice, those who want it most.

        Where the data gives no mark to pass, everybody who is here stands.
        """
        state = world.government
        present = [
            resident
            for resident in world.politics.leadership.present(world)
            if resident.resident_id != state.resigned and resident.resident_id not in exclude
        ]
        mark = world.registries.politics.ways.get(ELECTION, {}).get("stand_from")
        if mark is None:
            return present
        wanting = {resident.resident_id: self.will(world, resident) for resident in present}
        standing = [
            resident
            for resident in present
            if resident.resident_id == state.leader or wanting[resident.resident_id] >= mark
        ]
        if len(standing) < min(at_least, len(present)):
            rest = sorted(
                (resident for resident in present if resident not in standing),
                key=lambda resident: (-wanting[resident.resident_id], resident.resident_id),
            )
            standing += rest[: min(at_least, len(present)) - len(standing)]
        return [resident for resident in present if resident in standing]

    # ----- the player's word for a candidate -----

    def back(self, world: "SimulationWorld", resident_id: str, candidate_id: str) -> PoliticsResult:
        """The player speaks to a resident for one of those who stand, before a vote that has
        been called. Once for each resident and vote. It weighs with them by how much they
        lean on the player, and they vote as they see fit."""
        state = world.government
        leadership = world.politics.leadership
        resident = world.residents.get(resident_id)
        candidate = world.residents.get(candidate_id)
        if state.election_at is None:
            return PoliticsResult(False, "No se ha llamado a votar")
        if resident is None or not any(each is resident for each in leadership.present(world)):
            return PoliticsResult(False, "No está para que se le hable de ello")
        standing = leadership.standing(world)
        if candidate is None or not any(each is candidate for each in standing):
            return PoliticsResult(False, "No se presenta")
        if resident_id in state.backing:
            return PoliticsResult(False, f"Ya se ha hablado de la votación con {resident.name}")
        settings = world.registries.proposals
        influence = world.politics.influence
        theirs = max(standing, key=lambda each: leadership.vote_score(world, resident, each))
        against_their_mind = theirs is not candidate
        defies = against_their_mind and influence.defies(world, resident)
        push = settings.backing * (-settings.contrary if defies else influence.lean(world, resident))
        if against_their_mind:
            influence.pushed(world, resident, BACKING_PUSH)
        state.backing[resident_id] = [candidate_id, push]
        world.tastes.advised(world, resident)
        now = max(standing, key=lambda each: leadership.vote_score(world, resident, each))
        took = "contrary" if defies else "taken" if now is candidate else "ignored"
        said = {
            "contrary": "le lleva la contraria a quien se lo dice",
            "taken": f"votará a {candidate.name}",
            "ignored": "no cambia de parecer",
        }[took]
        text = f"Se habla con {resident.name} de votar a {candidate.name}: {said}"
        world.emit_event(
            PoliticalEvent(
                "candidate_backed",
                BACKED_IMPORTANCE,
                text,
                [resident_id],
                data={"candidate": candidate_id, "took": took},
                government=state.kind,
            )
        )
        return PoliticsResult(took == "taken", text, took)

    # ----- a count made to come out somebody's way -----

    def voters(self, world: "SimulationWorld", way: str) -> list[Resident]:
        present = world.politics.leadership.present(world)
        if way == COUNCIL:
            return [resident for resident in present if resident.resident_id in world.government.council]
        return present

    def forecast(self, world: "SimulationWorld", way: str) -> tuple[Resident | None, dict[str, int]]:
        """Who would win a vote for the leader's seat held right now, and how many for each."""
        leadership = world.politics.leadership
        standing = leadership.standing(world)
        voters = self.voters(world, way)
        if not standing or not voters:
            return None, {}
        winner, _backers = leadership.elect(world, voters, standing, record=False)
        count = Counter(
            max(standing, key=lambda each: leadership.vote_score(world, voter, each)).resident_id for voter in voters
        )
        return winner, {each.resident_id: count[each.resident_id] for each in standing}

    def consider_rigging(self, world: "SimulationWorld", definition: GovernmentDefinition) -> bool:
        """Have whoever leads and stands to lose the vote that is coming think of seeing to
        the count. Only where votes are cast in secret: nobody miscounts a show of hands. It is
        theirs to decide and the player's to advise on. Returns whether it came to that."""
        state = world.government
        leader = world.residents.get(state.leader or "")
        way = next((way for way in definition.succession if way in VOTED_WAYS), None)
        if definition.ballot == OPEN or leader is None or leader.away or way is None:
            return False
        if RIG not in world.registries.decisions or world.interventions.asking_obstacle(world, leader, RIG):
            return False
        winner, tally = self.forecast(world, way)
        if winner is None or winner is leader or leader.resident_id not in tally:
            return False
        behind = (tally[winner.resident_id] - tally[leader.resident_id]) / max(1, sum(tally.values()))
        scruples = world.politics.legitimacy.profile(world, leader).justice_sensitivity / 100.0
        inputs = {"losing": min(1.0, 2.0 * behind), "scruples": scruples}
        return world.interventions.ask(world, leader, RIG, inputs=inputs) is not None

    def rig(self, world: "SimulationWorld", resident: Resident) -> None:
        """Whoever leads sees to it that the count of the vote that is coming comes out their
        way. Whoever sees them at it knows, and nobody else does."""
        state = world.government
        state.rigged_by = resident.resident_id
        world.politics.legitimacy.shock(world, {"corruption": world.registries.politics.rig_corruption})
        world.emit_event(
            PoliticalEvent(
                "election_rigged",
                RIGGED_IMPORTANCE,
                f"{resident.name} amaña el recuento de la votación",
                [resident.resident_id],
                government=state.kind,
            ),
            at=resident.tile,
            fact_text=f"{resident.name} amañó el recuento de una votación",
        )

    # ----- a result, and what it leaves -----

    def settle(
        self,
        world: "SimulationWorld",
        seat: str,
        way: str,
        standing: list[Resident],
        backed: dict[str, str],
        winner: Resident,
    ) -> Resident:
        """Give out the result of a vote, and keep it. Where whoever leads has seen to the
        count and would have lost, enough votes change hands in it for them to win. Returns
        whoever is given out as the winner."""
        state = world.government
        definition = world.politics.leadership.definition(world)
        open_ballot = definition is None or definition.ballot == OPEN
        count = Counter(backed.values())
        tally = {each.resident_id: count[each.resident_id] for each in standing}
        rigger = world.residents.get(state.rigged_by or "")
        rigged_by = None
        if seat == LEADER_SEAT and not open_ballot and rigger is not None and rigger is not winner:
            if any(each is rigger for each in standing):
                moved = (tally[winner.resident_id] - tally[rigger.resident_id]) // 2 + 1
                tally[rigger.resident_id] += moved
                tally[winner.resident_id] -= moved
                winner, rigged_by = rigger, rigger.resident_id
        state.elections.append(
            ElectionRecord(
                day=world.clock.day,
                at=world.clock.total_minutes,
                seat=seat,
                way=way,
                candidates=[each.resident_id for each in standing],
                tally=tally,
                winner=winner.resident_id,
                backed=dict(backed),
                open_ballot=open_ballot,
                rigged_by=rigged_by,
            )
        )
        del state.elections[: -world.registries.proposals.history]
        return winner

    def took_part(self, world: "SimulationWorld", record: ElectionRecord, incumbent_id: str | None) -> None:
        """What a vote for who leads leaves in those who took part: each remembers who they
        backed, whoever backed a loser trusts the government a little less, and a loser holds
        it against whoever won."""
        settings = world.registries.politics
        winner = world.residents.get(record.winner or "")
        if winner is None:
            return
        now = world.clock.total_minutes
        legitimacy = world.politics.legitimacy
        for voter_id, candidate_id in record.backed.items():
            candidate = world.residents.get(candidate_id)
            if voter_id not in world.residents or candidate is None or voter_id == candidate_id:
                continue
            # A count that was seen to is given out as the winner's: whoever backed the one
            # who had it taken from them is let down like anybody whose candidate lost.
            won = candidate_id == winner.resident_id
            how = "y ganó" if won else f"y ganó {winner.name}"
            world.memories.remember(
                voter_id,
                Memory(
                    f"Voté a {candidate.name} para mandar, {how}.", VOTED_MEMORY, 0.3 if won else -0.2,
                    [candidate_id, winner.resident_id], ["politics", "election"], now,
                ),
            )
            if not won:
                legitimacy.profile(world, world.residents[voter_id]).adjust("trust", settings.let_down_trust)
        for loser in self._losers(world, record, incumbent_id):
            profile = legitimacy.profile(world, loser)
            world.relationship(loser.resident_id, winner.resident_id).adjust(
                "resentment", settings.lost_resentment * (0.5 + profile.revengefulness / 100.0)
            )
            if loser.resident_id != incumbent_id:
                world.memories.remember(
                    loser.resident_id,
                    Memory(
                        f"Perdí la votación: manda {winner.name}.", LOST_MEMORY, -0.5,
                        [winner.resident_id], ["politics", "election"], now,
                    ),
                )

    def _losers(self, world: "SimulationWorld", record: ElectionRecord, incumbent_id: str | None) -> list[Resident]:
        """Whoever stood and lost with somebody behind them, and whoever led and lost the seat.
        Somebody nobody was behind has nothing to be sore about."""
        return [
            world.residents[loser_id]
            for loser_id in record.candidates
            if loser_id in world.residents
            and loser_id != record.winner
            and (record.tally.get(loser_id, 0) > 0 or loser_id == incumbent_id)
        ]

    def contested(self, world: "SimulationWorld", record: ElectionRecord, incumbent_id: str | None) -> None:
        """Have whoever lost a vote cast in secret and is sore enough say there was cheating,
        with reason or without. Nobody says it of a show of hands: everybody saw them."""
        settings = world.registries.politics
        winner = world.residents.get(record.winner or "")
        if winner is None or record.open_ballot:
            return
        true_count = Counter(record.backed.values())
        most = max(true_count.values(), default=0)
        for loser in self._losers(world, record, incumbent_id):
            loser_id = loser.resident_id
            profile = world.politics.legitimacy.profile(world, loser)
            soreness = profile.revengefulness / 100.0 + (50.0 - profile.trust) / 100.0
            if record.tally[winner.resident_id] - record.tally.get(loser_id, 0) <= CLOSE_RESULT:
                soreness += CLOSE_SORENESS
            if record.rigged_by is not None and true_count[loser_id] == most:
                # They had the votes, and know how many told them they would have theirs.
                soreness += ROBBED_SORENESS
            if soreness >= settings.claim_from:
                self._claim(world, record, loser, winner)

    def _claim(self, world: "SimulationWorld", record: ElectionRecord, loser: Resident, winner: Resident) -> None:
        """Have a loser say that there was cheating. Whoever hears it makes of it what they
        make of the loser and of the government, whether there was or not."""
        record.claimed_by.append(loser.resident_id)
        world.memories.remember(
            loser.resident_id,
            Memory(
                "Me robaron la votación.", LOST_MEMORY, -0.7, [winner.resident_id],
                ["politics", "election", "fraud"], world.clock.total_minutes,
            ),
        )
        world.emit_event(
            PoliticalEvent(
                "fraud_claimed",
                CLAIMED_IMPORTANCE,
                f"{loser.name} dice que en la votación hubo trampa",
                [loser.resident_id],
                data={"winner": winner.resident_id, "rigged": record.rigged_by is not None},
                government=world.government.kind,
            ),
            at=loser.tile,
            fact_text=f"{loser.name} dice que {winner.name} ganó la votación con trampa",
            subjects=[winner.resident_id, loser.resident_id],
        )
