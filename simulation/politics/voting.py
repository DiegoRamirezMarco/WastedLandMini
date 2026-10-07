"""Proposals and votes: what is put to the settlement, who decides it, and how each of them votes.

The player proposes and the settlement decides. A proposal goes into the process of the
government in force: whoever may propose has to make it theirs, it is talked over, and those
who approve decide it, each by their own mind. Only if it passes does anything follow.
Residents who may propose raise things of their own when they have a reason to.

No vote is a roll: how each resident votes is worked out from what they hold, what they stand
to gain or lose, what they feel for who it is about and for who put it, what they know, their
loyalty, their fear, what they remember and what the player said to them.
"""

from collections.abc import Iterator, Mapping
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from simulation.memory.memory import Memory
from simulation.politics import opinion
from simulation.politics.government import (
    COUNCIL,
    LEADER,
    NOBODY,
    OPEN,
    VOTED_WAYS,
    PoliticsResult,
)
from simulation.politics.influence import CONTRARY, IGNORED, SOFTENED, TAKEN
from simulation.politics.law import LawDefinition
from simulation.politics.political_event import PoliticalEvent
from simulation.politics.proposal import (
    ADOPT_CURRENCY,
    CALL_ELECTION,
    CHANGE_GOVERNMENT,
    ENACT_LAW,
    EXPEL,
    REPEAL_LAW,
    RETURN_TO_BARTER,
)
from simulation.politics.records import (
    ABSTAIN,
    ACCEPTED,
    CHANGED,
    DROPPED,
    NO,
    PASSED,
    PLAYER,
    REJECTED,
    VETOED,
    YES,
    Ballot,
    Proposal,
)
from simulation.residents.resident import Resident
from simulation.rng import SimulationRNG
from simulation.social.relationship import FEELINGS

if TYPE_CHECKING:
    from simulation.world import SimulationWorld

RAISED_IMPORTANCE = 55
DROPPED_IMPORTANCE = 40
LOBBIED_IMPORTANCE = 30
VOTE_IMPORTANCE = 55
DECIDED_IMPORTANCE = 65
VOTE_MEMORY = 30.0
PROPOSAL_MEMORY = 50.0
EXPELLED_MEMORY = 90.0
# How somebody remembers a thing of theirs that was turned down, before what it was.
TURNED_DOWN = "No salió adelante lo que propuse: "
# The hour of the day at which whoever has something to put to the others thinks of doing so.
STIR_HOUR = 8
# What stands for or against, as the player says it to a resident.
FOR, AGAINST = "for", "against"
STANCES = (FOR, AGAINST)
# How much the evidence against somebody can come to, however much is known of them, and how
# much what is remembered can.
MOST_EVIDENCE = 3.0
MOST_MEMORY = 1.0
# What is felt for somebody from which it is taken to heart when they are thrown out.
CLOSE_AFFECTION = 40.0
# How much more than the law itself a whim has to appeal to whoever leads for them to pass it.
WHIM_WISH = 0.2
OUTCOMES = {
    ACCEPTED: ("proposal_accepted", "Sale adelante"),
    CHANGED: ("proposal_changed", "Sale adelante, rebajada"),
    REJECTED: ("proposal_rejected", "No sale adelante"),
    VETOED: ("proposal_vetoed", "Quien manda se niega"),
    DROPPED: ("proposal_dropped", "Se queda en nada"),
}


@dataclass(frozen=True)
class Idea:
    """Something a resident might put to the others, and how much they want it."""

    wish: float
    kind: str
    law: str | None = None
    degree: int = 0
    target: str | None = None
    government: str | None = None
    params: dict[str, str] = field(default_factory=dict)


class Voting:
    # ----- who has a say -----

    def _group(self, world: "SimulationWorld", who: str) -> list[Resident]:
        """The residents a government means by one of its words, as far as they are here:
        whoever leads, the council, or every adult. With nobody in the seat it names, the say
        falls to the council, and failing that to everybody."""
        leadership = world.politics.leadership
        state = world.government
        present = leadership.present(world)
        if who == NOBODY:
            return []
        if who == LEADER:
            leader = next((resident for resident in present if resident.resident_id == state.leader), None)
            if leader is not None:
                return [leader]
            who = COUNCIL
        if who == COUNCIL:
            sitting = [resident for resident in present if resident.resident_id in state.council]
            if sitting:
                return sitting
        return present

    def proposers(self, world: "SimulationWorld") -> list[Resident]:
        """Whoever may lay a proposal before the settlement, under the government in force."""
        definition = world.politics.leadership.definition(world)
        return self._group(world, definition.proposes) if definition is not None else []

    def may_propose(self, world: "SimulationWorld", resident: Resident) -> bool:
        return any(each is resident for each in self.proposers(world))

    def deciders(self, world: "SimulationWorld") -> list[Resident]:
        """Whoever decides a proposal, under the government in force."""
        definition = world.politics.leadership.definition(world)
        return self._group(world, definition.approves) if definition is not None else []

    def pending(self, world: "SimulationWorld") -> list[Proposal]:
        return list(world.government.proposals.values())

    # ----- putting a proposal into words -----

    def matter(self, proposal: Proposal) -> str:
        """One name for what a proposal is about, to tell whether the same thing is being put again."""
        about = proposal.law or proposal.target or proposal.government or ""
        return f"{proposal.kind}:{about}"

    def worded(self, world: "SimulationWorld", proposal: Proposal, degree: int | None = None) -> str:
        settings = world.registries.proposals
        definition = settings.kinds[proposal.kind]
        laws = world.politics.laws
        law = laws.definition(world, proposal.law or "")
        degree = proposal.degree if degree is None else degree
        target = world.residents.get(proposal.target or "")
        record = world.kinship.get(proposal.target or "")
        government = world.registries.politics.governments.get(proposal.government or "")
        return (
            definition.text.replace(
                "{described}", laws.describe(world, law.law_id, degree, proposal.params) if law is not None else ""
            )
            .replace("{law}", law.name if law is not None else "")
            .replace("{text}", laws.said(world, law, proposal.params) if law is not None else "")
            .replace("{degree}", laws.degree(law, degree).name if law is not None else "")
            .replace("{target}", target.name if target else record.name if record else "alguien")
            .replace("{government}", government.name if government is not None else "")
            .replace("{currency}", proposal.params.get("name", "una moneda"))
        )

    # ----- raising one -----

    def obstacle(self, world: "SimulationWorld", proposal: Proposal) -> str | None:
        """Why a proposal cannot be put, or carried out, as things stand. None if it can."""
        state = world.government
        settings = world.registries.proposals
        definition = world.politics.leadership.definition(world)
        if state.kind is None or definition is None:
            return "Todavía no hay gobierno al que proponérselo"
        if proposal.kind not in settings.kinds:
            return "No hay tal cosa que proponer"
        laws = world.politics.laws
        if proposal.kind == ENACT_LAW:
            law = laws.definition(world, proposal.law or "")
            if law is None:
                return "No hay tal ley"
            if not 0 <= proposal.degree < len(law.degrees):
                return "Esa ley no llega tan lejos, ni se queda tan corta"
            held = state.laws.get(law.law_id)
            if held is not None and held.degree == proposal.degree and held.params == proposal.params:
                return "Esa ley ya rige"
            if law.param is not None:
                item = world.registries.items.find(proposal.params.get("item", ""))
                if item is None or item.category not in world.registries.economy.kept_categories:
                    return "Esa ley tiene que decir qué comida veta"
                if opinion.common_stock(world, item.category, but=item.item_id) <= 0:
                    return "No se puede vetar lo único que hay de comer"
            return laws.obstacle(world, law.law_id)
        if proposal.kind == REPEAL_LAW:
            return None if proposal.law in state.laws else "Esa ley no rige"
        if proposal.kind == CALL_ELECTION:
            voted = definition.leader_role is not None and any(way in VOTED_WAYS for way in definition.succession)
            if not voted and definition.council_seats <= 0:
                return "Con este gobierno no hay nada que votar"
            return "Ya se ha llamado a votar" if state.election_at is not None else None
        if proposal.kind == CHANGE_GOVERNMENT:
            if proposal.government not in world.registries.politics.governments:
                return "No hay tal manera de gobernarse"
            return "Ya se gobiernan así" if proposal.government == state.kind else None
        if proposal.kind == EXPEL:
            if proposal.target not in world.residents:
                return "No hay a quién echar"
            return "Ya le han echado" if proposal.target in world.leaving else None
        coin = world.fund.currency(world)
        if proposal.kind == ADOPT_CURRENCY:
            if not proposal.params.get("name"):
                return "Una moneda tiene que llamarse de alguna manera"
            return f"Ya se comercia con {coin.name}" if coin is not None else None
        if proposal.kind == RETURN_TO_BARTER:
            return "Ya se comercia por trueque" if coin is None else None
        return None

    def _waits(self, world: "SimulationWorld", proposal: Proposal) -> str | None:
        """Why a proposal has to wait, though it makes sense. None if it need not."""
        state = world.government
        settings = world.registries.proposals
        matter = self.matter(proposal)
        if any(self.matter(other) == matter for other in state.proposals.values()):
            return "Eso mismo está ya por decidir"
        if len(state.proposals) >= settings.pending_limit:
            return "Hay demasiadas cosas por decidir: que se decidan primero"
        settled = state.refused.get(matter)
        if settled is not None and world.clock.day < settled:
            return "Eso se decidió hace poco: no es momento de volver con ello"
        return None

    def _draft(
        self,
        world: "SimulationWorld",
        kind: str,
        by: str,
        law: str | None = None,
        degree: int | None = None,
        target: str | None = None,
        government: str | None = None,
        params: Mapping[str, str] | None = None,
    ) -> Proposal:
        """A proposal as it would be put, not yet laid before anybody."""
        definition = world.politics.leadership.definition(world)
        law_definition = world.politics.laws.definition(world, law or "")
        if degree is None:
            # Left unsaid, a law is proposed as written: at the middle of how far it can go.
            degree = len(law_definition.degrees) // 2 if law_definition is not None else 0
        proposal = Proposal(
            proposal_id="",
            kind=kind,
            by=by,
            law=law,
            degree=degree,
            target=target,
            government=government,
            params={str(key): str(value) for key, value in (params or {}).items()},
            raised_at=world.clock.total_minutes,
            open_ballot=definition is None or definition.ballot == OPEN,
        )
        if kind in world.registries.proposals.kinds:
            proposal.text = self.worded(world, proposal)
        return proposal

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
        """The player puts something to the settlement. Somebody who may propose has to make
        it theirs: whoever of them is most for it, if any of them is. Then it waits to be
        decided like any other. Nothing of it is done unless it passes."""
        proposal = self._draft(world, kind, PLAYER, law, degree, target, government, params)
        error = self.obstacle(world, proposal) or self._waits(world, proposal)
        if error is not None:
            return PoliticsResult(False, error)
        takers = [
            (self.mind(world, resident, proposal)[0], resident)
            for resident in self.proposers(world)
            if resident.resident_id != proposal.target
        ]
        wish, sponsor = max(takers, key=lambda each: (each[0], each[1].resident_id), default=(0.0, None))
        if sponsor is None or wish <= 0.0:
            return self._nobody_takes_it(world, proposal, sponsor)
        proposal.sponsor = sponsor.resident_id
        world.memories.remember(
            sponsor.resident_id,
            Memory(
                f"Hice mía una propuesta de quien nos aconseja: {proposal.text}.",
                PROPOSAL_MEMORY, 0.1, [], ["politics", "proposal", "player"], world.clock.total_minutes,
            ),
        )
        return self._lay(world, proposal, f"{sponsor.name} hace suya una propuesta: {proposal.text}")

    def _nobody_takes_it(self, world: "SimulationWorld", proposal: Proposal, asked: Resident | None) -> PoliticsResult:
        state = world.government
        state.refused[self.matter(proposal)] = world.clock.day + world.registries.proposals.again_days
        text = (
            f"{asked.name} no hace suya la propuesta: {proposal.text}"
            if asked is not None
            else f"No hay quien pueda hacer suya la propuesta: {proposal.text}"
        )
        world.emit_event(
            PoliticalEvent(
                "proposal_dropped",
                DROPPED_IMPORTANCE,
                text,
                [asked.resident_id] if asked is not None else [],
                data={"kind": proposal.kind, "by": proposal.by},
                government=state.kind,
            )
        )
        return PoliticsResult(False, text)

    def raise_as(
        self,
        world: "SimulationWorld",
        resident: Resident,
        kind: str,
        law: str | None = None,
        degree: int | None = None,
        target: str | None = None,
        government: str | None = None,
        params: Mapping[str, str] | None = None,
    ) -> PoliticsResult:
        """A resident lays something before the settlement, if the government lets them."""
        if not self.may_propose(world, resident):
            return PoliticsResult(False, f"{resident.name} no tiene a quién proponérselo")
        proposal = self._draft(world, kind, resident.resident_id, law, degree, target, government, params)
        error = self.obstacle(world, proposal) or self._waits(world, proposal)
        if error is not None:
            return PoliticsResult(False, error)
        world.government.raised_on[resident.resident_id] = world.clock.day
        world.memories.remember(
            resident.resident_id,
            Memory(
                f"Propuse {proposal.text}.", PROPOSAL_MEMORY, 0.1,
                [proposal.target] if proposal.target else [], ["politics", "proposal"], world.clock.total_minutes,
            ),
        )
        return self._lay(world, proposal, f"{resident.name} propone {proposal.text}")

    def _lay(self, world: "SimulationWorld", proposal: Proposal, text: str) -> PoliticsResult:
        """Lay a proposal before those who decide it, to be decided once it has been talked over."""
        state = world.government
        settings = world.registries.proposals
        definition = settings.kinds[proposal.kind]
        deciders = self.deciders(world)
        hours = settings.debate_hours
        if len(deciders) == 1:
            # One person making up their mind takes less than many talking it over.
            hours = min(hours, settings.leader_hours)
        if definition.debate_hours is not None:
            # What cannot be undone is given its time whoever decides it, so that there is a
            # chance to speak to them first.
            hours = definition.debate_hours
        state.proposal_count += 1
        proposal.proposal_id = f"proposal_{state.proposal_count}"
        proposal.decides_at = world.clock.total_minutes + hours * 60
        state.proposals[proposal.proposal_id] = proposal
        proposer = proposal.sponsor if proposal.by == PLAYER else proposal.by
        world.emit_event(
            PoliticalEvent(
                "proposal_raised",
                RAISED_IMPORTANCE,
                text,
                [each for each in (proposer, proposal.target) if each in world.residents],
                data={
                    "proposal": proposal.proposal_id, "kind": proposal.kind, "by": proposal.by,
                    "sponsor": proposal.sponsor, "law": proposal.law, "degree": proposal.degree,
                    "target": proposal.target, "government": proposal.government,
                    "decides_at": proposal.decides_at, "deciders": [each.resident_id for each in deciders],
                },
                government=state.kind,
            )
        )
        return PoliticsResult(True, text, proposal.proposal_id)

    # ----- what each resident makes of one -----

    def conviction(self, world: "SimulationWorld", voter: Resident, proposal: Proposal, degree: int | None = None) -> float:
        """What a resident makes of the thing itself: what they hold and what they stand to gain or lose."""
        laws = world.politics.laws
        degree = proposal.degree if degree is None else degree
        if proposal.kind == ENACT_LAW:
            return laws.regard(world, voter, proposal.law or "", degree, proposal.params)
        if proposal.kind == REPEAL_LAW:
            held = world.government.laws.get(proposal.law or "")
            if held is None:
                return 0.0
            return -laws.regard(world, voter, held.law_id, held.degree, held.params)
        definition = world.registries.proposals.kinds[proposal.kind]
        params = {**proposal.params, "government": proposal.government or ""}
        return opinion.weigh(world, voter, definition.opinion, params) + definition.bias

    def _about(self, world: "SimulationWorld", voter: Resident, target_id: str) -> float:
        """What a resident feels for whoever a proposal is about, as it weighs on throwing them out."""
        weights = world.registries.proposals.target
        if voter.resident_id == target_id:
            return weights.get("self", 0.0)
        total = 0.0
        feelings = world.relationships.get((voter.resident_id, target_id))
        if feelings is not None:
            total += sum(weights.get(name, 0.0) * getattr(feelings, name) / 100.0 for name in FEELINGS)
        if world.family.kin.close(world, voter.resident_id, target_id):
            total += weights.get("kin", 0.0)
        if voter.couple_with == target_id:
            total += weights.get("couple", 0.0)
        return total

    def known_misdeeds(self, world: "SimulationWorld", resident: Resident, target_id: str, since: int = 0) -> list[float]:
        """What a resident knows somebody to have done that counts against them: how much each
        thing weighs, by how sure they are of it. Only what they saw or were told."""
        misdeeds = world.registries.proposals.misdeeds
        facts = world.knowledge.facts
        weighed: list[float] = []
        for belief in world.knowledge.beliefs_of(resident.resident_id):
            fact = facts.get(belief.fact_id)
            if fact is None or fact.event_type not in misdeeds or fact.timestamp < since:
                continue
            if fact.subject_ids and fact.subject_ids[0] == target_id:
                weighed.append(belief.credibility * fact.importance / 50.0)
        return weighed

    def _remembered(self, world: "SimulationWorld", voter: Resident, person_id: str | None) -> float:
        """What a resident remembers of politics that has somebody in it: above nothing for good, below for bad."""
        if person_id is None or person_id == voter.resident_id:
            return 0.0
        total = sum(
            memory.emotional_value * memory.importance / 100.0
            for memory in world.memories.of(voter.resident_id)
            if "politics" in memory.tags and person_id in memory.people
        )
        return max(-MOST_MEMORY, min(MOST_MEMORY, total))

    def _margin(self, world: "SimulationWorld", voter: Resident) -> float:
        """How far from the middle a resident's mind has to be for them to vote one way or the
        other: the less politics is to them, the further."""
        interest = world.politics.legitimacy.profile(world, voter).political_interest
        return world.registries.proposals.margin * (1.5 - interest / 100.0)

    def stance(self, world: "SimulationWorld", resident: Resident, proposal: Proposal, degree: int | None = None) -> int:
        """Where a resident stands on a proposal: 1 for it, -1 against, 0 neither."""
        score = self.mind(world, resident, proposal, degree, alone=True)[0]
        margin = self._margin(world, resident)
        return 1 if score >= margin else -1 if score <= -margin else 0

    def mind(
        self,
        world: "SimulationWorld",
        voter: Resident,
        proposal: Proposal,
        degree: int | None = None,
        alone: bool = False,
    ) -> tuple[float, dict[str, float]]:
        """A resident's mind on a proposal, and the parts it is made of: above nothing for it.

        `alone` leaves out where whoever leads stands, which is how the leader's own stand is
        worked out.
        """
        settings = world.registries.proposals
        weights = settings.weights
        state = world.government
        parts: dict[str, float] = {"conviction": self.conviction(world, voter, proposal, degree)}
        if proposal.kind == EXPEL and proposal.target:
            parts["target"] = self._about(world, voter, proposal.target)
            if voter.resident_id != proposal.target:
                known = sum(self.known_misdeeds(world, voter, proposal.target))
                parts["evidence"] = weights["evidence"] * min(MOST_EVIDENCE, known)
        proposer = proposal.sponsor if proposal.by == PLAYER else proposal.by
        if proposal.by == PLAYER:
            influence = world.politics.influence
            trust = influence.standing(world, voter).trust
            parts["player"] = weights["player"] * (trust - 50.0) / 50.0 * influence.lean(world, voter)
        if proposer == voter.resident_id:
            parts["proposer"] = weights["proposer"]
        elif proposer is not None:
            feelings = world.relationships.get((voter.resident_id, proposer))
            if feelings is not None:
                regard = (feelings.affection + feelings.trust - feelings.resentment) / 100.0
                parts["proposer"] = weights["proposer"] * regard
        leader = world.residents.get(state.leader or "")
        if not alone and leader is not None and leader is not voter:
            stands = self.stance(world, leader, proposal, degree)
            if stands:
                politics = world.registries.politics
                profile = world.politics.legitimacy.profile(world, voter)
                loyalty = (profile.loyalty - politics.loyalty_base) / (100.0 - politics.loyalty_base)
                parts["loyalty"] = weights["loyalty"] * stands * loyalty
                parts["grudge"] = -weights["grudge"] * stands * profile.resentment / 100.0
                if proposal.open_ballot:
                    # A hand raised against whoever leads is seen by them.
                    dread = profile.fear / 100.0 * (0.5 + profile.fearfulness / 100.0)
                    parts["fear"] = weights["fear"] * stands * dread
        parts["memory"] = weights["memory"] * self._remembered(world, voter, proposer)
        push = proposal.lobbied.get(voter.resident_id)
        if push:
            parts["lobby"] = push
        return sum(parts.values()), parts

    def ballot(self, world: "SimulationWorld", voter: Resident, proposal: Proposal, degree: int | None = None) -> Ballot:
        """How a resident votes on a proposal, and the three things that weighed most in it."""
        score, parts = self.mind(world, voter, proposal, degree)
        margin = self._margin(world, voter)
        vote = YES if score >= margin else NO if score <= -margin else ABSTAIN
        sign = 1.0 if vote == YES else -1.0 if vote == NO else 0.0
        behind = sorted(
            (name for name, value in parts.items() if value and (sign == 0.0 or value * sign > 0)),
            key=lambda name: -abs(parts[name]),
        )
        return Ballot(voter.resident_id, vote, round(score, 3), behind[:3])

    def count(self, world: "SimulationWorld", proposal: Proposal, degree: int | None = None) -> list[Ballot]:
        """How those who decide a proposal would vote on it right now."""
        return [self.ballot(world, voter, proposal, degree) for voter in self.deciders(world)]

    def passes(self, world: "SimulationWorld", ballots: list[Ballot]) -> bool:
        """Whether a vote carries: the share the government asks for, of those who said yes or
        no. The word of whoever leads counts for as many votes as the government gives it."""
        definition = world.politics.leadership.definition(world)
        if definition is None:
            return False
        leader = world.government.leader
        yes = sum(definition.leader_weight if each.voter == leader else 1.0 for each in ballots if each.vote == YES)
        no = sum(definition.leader_weight if each.voter == leader else 1.0 for each in ballots if each.vote == NO)
        return yes > no and yes >= definition.approval * (yes + no)

    # ----- the player's word before a vote -----

    def lobby(self, world: "SimulationWorld", proposal_id: str, resident_id: str, stance: str) -> PoliticsResult:
        """The player speaks to one of those who will decide a proposal, for it or against it.

        Once for each resident and proposal. It weighs with them by how much they lean on the
        player, and they vote as they see fit: they may go along, come half way, take no notice,
        or do the opposite. Whoever is pushed against their own mind resists the more for it.
        """
        proposal = world.government.proposals.get(proposal_id)
        resident = world.residents.get(resident_id)
        if proposal is None:
            return PoliticsResult(False, "Eso ya no está por decidir")
        if stance not in STANCES:
            return PoliticsResult(False, "Solo se puede hablar a favor o en contra")
        if resident is None or not any(each is resident for each in self.deciders(world)):
            return PoliticsResult(False, "No es de quienes lo deciden")
        if resident_id in proposal.lobbied:
            return PoliticsResult(False, f"Ya se ha hablado de esto con {resident.name}")
        settings = world.registries.proposals
        influence = world.politics.influence
        sign = 1.0 if stance == FOR else -1.0
        before = self.ballot(world, resident, proposal)
        against_their_mind = before.vote == (NO if sign > 0 else YES)
        defies = against_their_mind and influence.defies(world, resident)
        if defies:
            push = -sign * settings.contrary * settings.lobby
        else:
            push = sign * settings.lobby * influence.lean(world, resident)
        if against_their_mind:
            influence.pushed(world, resident, min(1.0, abs(before.score)))
        proposal.lobbied[resident_id] = push
        if sign > 0:
            proposal.pushed = True
        world.tastes.advised(world, resident)
        after = self.ballot(world, resident, proposal)
        asked = YES if sign > 0 else NO
        if defies:
            took, said = CONTRARY, "le lleva la contraria a quien se lo dice"
        elif after.vote == asked:
            took, said = TAKEN, "lo ve así"
        elif after.vote != before.vote:
            took, said = SOFTENED, "se lo piensa, y ya no lo tiene tan claro"
        else:
            took, said = IGNORED, "no cambia de parecer"
        text = f"Se habla con {resident.name} sobre {proposal.text}: {said}"
        world.emit_event(
            PoliticalEvent(
                "proposal_lobbied",
                LOBBIED_IMPORTANCE,
                text,
                [resident_id],
                data={"proposal": proposal_id, "stance": stance, "took": took},
                government=world.government.kind,
            )
        )
        return PoliticsResult(took in (TAKEN, SOFTENED), text, took)

    # ----- time -----

    def tick(self, world: "SimulationWorld") -> None:
        """One minute: what has been talked over long enough is decided, and at the hour for
        it whoever has something to put to the others does."""
        state = world.government
        if state.kind is None:
            return
        now = world.clock.total_minutes
        for proposal in [each for each in state.proposals.values() if now >= each.decides_at]:
            self.decide(world, proposal)
        if world.clock.hour == STIR_HOUR and world.clock.minute == 0:
            self.stir(world)

    # ----- deciding -----

    def decide(self, world: "SimulationWorld", proposal: Proposal) -> str:
        """Have those who decide a proposal decide it, and carry it out if it passes.

        A law that does not carry as it was put is tried at each milder degree, and passes at
        the first that carries: changed. Where whoever leads may refuse what others approved
        and is against it, it is refused. Returns how it came out.
        """
        state = world.government
        definition = world.politics.leadership.definition(world)
        state.proposals.pop(proposal.proposal_id, None)
        deciders = self.deciders(world)
        if definition is None or not deciders or self.obstacle(world, proposal) is not None:
            return self._close(world, proposal, DROPPED, proposal.degree, [])
        ballots = self.count(world, proposal)
        status, degree = (ACCEPTED if self.passes(world, ballots) else REJECTED), proposal.degree
        if status == REJECTED and proposal.kind == ENACT_LAW:
            held = state.laws.get(proposal.law or "")
            floor = held.degree + 1 if held is not None and held.degree < proposal.degree else 0
            for milder in range(proposal.degree - 1, floor - 1, -1):
                milder_ballots = self.count(world, proposal, milder)
                if self.passes(world, milder_ballots):
                    status, degree, ballots = CHANGED, milder, milder_ballots
                    break
        leader = world.residents.get(state.leader or "")
        alone = len(deciders) == 1 and deciders[0] is leader
        if status in PASSED and definition.veto and leader is not None and not leader.away and not alone:
            if self.stance(world, leader, proposal, degree) < 0:
                status = VETOED
        return self._close(world, proposal, status, degree, ballots)

    def _close(self, world: "SimulationWorld", proposal: Proposal, status: str, degree: int, ballots: list[Ballot]) -> str:
        state = world.government
        settings = world.registries.proposals
        now = world.clock.total_minutes
        proposal.status, proposal.decided_at, proposal.ballots = status, now, ballots
        proposal.passed_degree = degree if status in PASSED else None
        state.decided.append(proposal)
        del state.decided[: -settings.history]
        if status in (REJECTED, VETOED):
            state.refused[self.matter(proposal)] = world.clock.day + settings.again_days
        elif status in PASSED and proposal.kind in (ENACT_LAW, REPEAL_LAW):
            # A law just passed is not put to be done away with the next day, nor one just
            # done away with put again: what was settled is left alone a little either way.
            undoing = REPEAL_LAW if proposal.kind == ENACT_LAW else ENACT_LAW
            state.refused[f"{undoing}:{proposal.law or ''}"] = world.clock.day + settings.undo_days
        text = self.worded(world, proposal, degree)
        yes, no, abstained = (
            [each.voter for each in ballots if each.vote == vote] for vote in (YES, NO, ABSTAIN)
        )
        if len(ballots) > 1:
            shown = {each.voter: each.vote for each in ballots} if proposal.open_ballot else {}
            world.emit_event(
                PoliticalEvent(
                    "vote_held",
                    VOTE_IMPORTANCE,
                    f"Se vota {text}: {len(yes)} a favor, {len(no)} en contra, {len(abstained)} no se pronuncian",
                    [each.voter for each in ballots],
                    data={
                        "proposal": proposal.proposal_id, "yes": len(yes), "no": len(no),
                        "abstain": len(abstained), "ballots": shown, "open": proposal.open_ballot,
                    },
                    government=state.kind,
                )
            )
        event_type, said = OUTCOMES[status]
        present = [resident.resident_id for resident in world.politics.leadership.present(world)]
        proposer = proposal.sponsor if proposal.by == PLAYER else proposal.by
        subjects = [each for each in (proposer, proposal.target) if each]
        world.emit_event(
            PoliticalEvent(
                event_type,
                DECIDED_IMPORTANCE if status != DROPPED else DROPPED_IMPORTANCE,
                f"{said}: {text}",
                present,
                data={
                    "proposal": proposal.proposal_id, "kind": proposal.kind, "status": status, "by": proposal.by,
                    "law": proposal.law, "degree": degree, "target": proposal.target,
                    "government": proposal.government,
                },
                government=state.kind,
            ),
            fact_text=f"se decidió sobre {text}: {said.lower()}" if status != DROPPED else None,
            subjects=subjects or present[:1],
        )
        if status == DROPPED:
            return status
        self._remember(world, proposal, text, status, ballots)
        aftermath = settings.aftermath
        legitimacy = world.politics.legitimacy
        if status == VETOED:
            legitimacy.shock(
                world,
                {"legitimacy": aftermath["veto_legitimacy"], "authoritarianism": aftermath["veto_authoritarianism"]},
            )
        elif len(ballots) > 1:
            # A thing decided by more than one, as the government says things are decided.
            legitimacy.shock(world, {"legitimacy": aftermath["heard_legitimacy"]})
        if status in PASSED:
            pushed = proposal.by == PLAYER or proposal.pushed
            if pushed:
                self._judge_player(world, proposal, degree)
            self._carry_out(world, proposal, degree, pushed, ballots)
        legitimacy.measure(world)
        return status

    def _remember(self, world: "SimulationWorld", proposal: Proposal, text: str, status: str, ballots: list[Ballot]) -> None:
        """Leave what a decision leaves in those who took part in it: how each voted, how it
        went for whoever put it, and for whoever it was about."""
        settings = world.registries.proposals
        aftermath = settings.aftermath
        now = world.clock.total_minutes
        passed = status in PASSED
        proposer_id = proposal.sponsor if proposal.by == PLAYER else proposal.by
        proposer = world.residents.get(proposer_id or "")
        target = world.residents.get(proposal.target or "")
        outside = ["player"] if proposal.by == PLAYER else []
        tags = ["politics", "vote", proposal.kind, *outside]
        own = ["politics", "proposal", proposal.kind, *outside]
        people = [each for each in (proposer_id, proposal.target) if each]
        for each in ballots:
            if each.vote == ABSTAIN or each.voter not in world.residents:
                continue
            said = "a favor de" if each.vote == YES else "en contra de"
            won = (each.vote == YES) == passed
            world.memories.remember(
                each.voter,
                Memory(
                    f"Voté {said} {text}.", VOTE_MEMORY, 0.1 if won else -0.1,
                    [person for person in people if person != each.voter], tags, now,
                ),
            )
        # Who voted how is known after a show of hands, and when one person decided alone.
        known = proposal.open_ballot or len(ballots) == 1
        for_it = [each.voter for each in ballots if each.vote == YES]
        against_it = [each.voter for each in ballots if each.vote == NO]
        if proposer is not None:
            profile = world.politics.legitimacy.profile(world, proposer)
            if passed:
                world.memories.remember(
                    proposer.resident_id,
                    Memory(f"Salió adelante lo que propuse: {text}.", PROPOSAL_MEMORY, 0.5, [], own, now),
                )
            else:
                blamed = [voter for voter in against_it if voter != proposer.resident_id] if known else []
                world.memories.remember(
                    proposer.resident_id,
                    Memory(f"{TURNED_DOWN}{text}.", PROPOSAL_MEMORY, -0.4, blamed, own, now),
                )
                profile.adjust("resentment", aftermath["refused_resentment"])
        if target is None or proposal.kind != EXPEL:
            return
        names = self._names(world, for_it)
        close = [
            resident
            for resident in world.politics.leadership.present(world)
            if resident is not target and self._close_to(world, resident, target)
        ]
        if passed:
            world.memories.remember(
                target.resident_id,
                Memory(
                    f"Me echaron del asentamiento: votaron por ello {names}." if known and for_it
                    else "Me echaron del asentamiento.",
                    EXPELLED_MEMORY, -1.0, for_it if known else [], tags, now,
                ),
            )
            for near in close:
                world.memories.remember(
                    near.resident_id,
                    Memory(
                        f"Echaron a {target.name}: votaron por ello {names}." if known and for_it
                        else f"Echaron a {target.name}.",
                        EXPELLED_MEMORY, -0.8, [target.resident_id, *(for_it if known else [])], tags, now,
                    ),
                )
                world.politics.legitimacy.profile(world, near).adjust("resentment", aftermath["close_resentment"])
        else:
            saved_by = self._names(world, against_it)
            world.memories.remember(
                target.resident_id,
                Memory(
                    f"Quisieron echarme del asentamiento, y {saved_by} votaron en contra." if known and against_it
                    else "Quisieron echarme del asentamiento.",
                    EXPELLED_MEMORY, -0.6, [*people, *(against_it if known else [])], tags, now,
                ),
            )
            if proposer is not None and proposer is not target:
                world.relationship(target.resident_id, proposer.resident_id).adjust(
                    "resentment", aftermath["voted_out_resentment"]
                )
        if not known:
            return
        for voter_id in for_it:
            if voter_id == target.resident_id:
                continue
            feelings = world.relationship(target.resident_id, voter_id)
            feelings.adjust("resentment", aftermath["voted_out_resentment"])
            feelings.adjust("trust", aftermath["voted_out_trust"])
            for near in close:
                if near.resident_id != voter_id:
                    world.relationship(near.resident_id, voter_id).adjust("resentment", aftermath["close_resentment"])
        for voter_id in against_it:
            if voter_id != target.resident_id:
                world.relationship(target.resident_id, voter_id).adjust("affection", aftermath["close_resentment"] / 2.0)

    def _close_to(self, world: "SimulationWorld", resident: Resident, other: Resident) -> bool:
        """Whether somebody is near enough to another to take to heart what is done to them."""
        if resident.couple_with == other.resident_id:
            return True
        if world.family.kin.close(world, resident.resident_id, other.resident_id):
            return True
        feelings = world.relationships.get((resident.resident_id, other.resident_id))
        return feelings is not None and feelings.affection >= CLOSE_AFFECTION

    def _names(self, world: "SimulationWorld", resident_ids: list[str]) -> str:
        names = [world.residents[each].name for each in resident_ids if each in world.residents]
        if len(names) <= 1:
            return "".join(names) or "nadie"
        return f"{', '.join(names[:-1])} y {names[-1]}"

    def _judge_player(self, world: "SimulationWorld", proposal: Proposal, degree: int) -> None:
        """Something the player was behind has been decided: each resident holds it to the
        player's account by how it turns out for them, and by nothing else."""
        outcome = world.registries.proposals.outcome
        for resident in world.residents.values():
            if not world.bonds.is_adult(world, resident):
                continue
            went = self.conviction(world, resident, proposal, degree)
            if proposal.kind == EXPEL and proposal.target:
                went += self._about(world, resident, proposal.target)
            world.politics.influence.judged(world, resident, outcome * max(-1.0, min(1.0, went)))

    def _carry_out(
        self, world: "SimulationWorld", proposal: Proposal, degree: int, pushed: bool, ballots: list[Ballot]
    ) -> None:
        """Do what a proposal that has passed says."""
        politics = world.politics
        proposer = proposal.sponsor if proposal.by == PLAYER else proposal.by
        if proposal.kind == ENACT_LAW and proposal.law:
            politics.laws.enact(world, proposal.law, degree, proposal.params, proposal.by, pushed)
        elif proposal.kind == REPEAL_LAW and proposal.law:
            politics.laws.repeal(world, proposal.law)
        elif proposal.kind == CALL_ELECTION:
            politics.leadership.recall(world)
        elif proposal.kind == CHANGE_GOVERNMENT and proposal.government:
            before = world.government.kind or ""
            wanted = {each.voter: proposal.government if each.vote == YES else before for each in ballots}
            # Too few to say how many wanted it: it is as legitimate as what it follows.
            politics.leadership.change_kind(
                world, proposal.government, wanted if len(wanted) >= world.registries.politics.founding_residents else None
            )
        elif proposal.kind == EXPEL:
            target = world.residents.get(proposal.target or "")
            if target is not None:
                politics.exile.banish(world, target, proposal.text, proposer)
        elif proposal.kind == ADOPT_CURRENCY:
            world.terms.adopt(world, proposal.params.get("name", ""), proposal.params.get("singular") or None)
        elif proposal.kind == RETURN_TO_BARTER:
            world.terms.revert(world)

    # ----- what residents put to the others unasked -----

    def stir(self, world: "SimulationWorld") -> PoliticsResult | None:
        """Have whoever of those who may propose wants something most put it to the others.

        One proposal a day at most, and none from somebody who raised one lately. Returns what
        came of it, or None if nobody had anything to put.
        """
        state = world.government
        settings = world.registries.proposals
        if state.kind is None or len(state.proposals) >= settings.pending_limit:
            return None
        best: tuple[float, str, Resident, Idea] | None = None
        for resident in self.proposers(world):
            raised = state.raised_on.get(resident.resident_id)
            if raised is not None and world.clock.day - raised < settings.rest_days:
                continue
            for idea in self.ideas(world, resident):
                # Between two wanted as much, whoever comes first by ID, so that it is always the same.
                ranked = (idea.wish, resident.resident_id, resident, idea)
                if best is None or (ranked[0], best[1]) > (best[0], ranked[1]):
                    best = ranked
        if best is None:
            return None
        _wish, _resident_id, resident, idea = best
        return self.raise_as(world, resident, idea.kind, idea.law, idea.degree, idea.target, idea.government, idea.params)

    def ideas(self, world: "SimulationWorld", resident: Resident) -> list[Idea]:
        """What a resident has reason to put to the others right now, and could."""
        found: list[Idea] = []
        since = world.clock.total_minutes - world.registries.proposals.sore_days * 24 * 60
        # What they put and saw turned down not long ago, they leave be: they remember it.
        lost = {
            memory.text
            for memory in world.memories.of(resident.resident_id)
            if "proposal" in memory.tags and memory.timestamp >= since and memory.text.startswith(TURNED_DOWN)
        }
        for idea in self._thought_of(world, resident):
            proposal = self._draft(
                world, idea.kind, resident.resident_id, idea.law, idea.degree, idea.target, idea.government, idea.params
            )
            if f"{TURNED_DOWN}{proposal.text}." in lost:
                continue
            if self.obstacle(world, proposal) is None and self._waits(world, proposal) is None:
                found.append(idea)
        return found

    def _thought_of(self, world: "SimulationWorld", resident: Resident) -> Iterator[Idea]:
        settings = world.registries.proposals
        state = world.government
        laws = world.politics.laws
        profile = world.politics.legitimacy.profile(world, resident)
        for law_id, law in world.registries.laws.laws.items():
            held = state.laws.get(law_id)
            if held is not None:
                regard = laws.regard(world, resident, law_id, held.degree, held.params)
                if regard <= settings.repeal_from:
                    yield Idea(-regard, REPEAL_LAW, law=law_id)
                continue
            params = self._names_for(world, resident, law)
            if params is None:
                continue
            degree = len(law.degrees) // 2
            regard = laws.regard(world, resident, law_id, degree, params)
            if law.motive is not None and regard >= settings.raise_from and self._moved(world, resident, law, regard):
                yield Idea(regard, ENACT_LAW, law=law_id, degree=degree, params=params)
            elif law.whim and self._whim(world, resident, law, params):
                yield Idea(opinion.weigh(world, resident, law.whim_opinion, params), ENACT_LAW, law_id, degree, params=params)
        definition = world.politics.leadership.definition(world)
        kinds = settings.kinds
        call = kinds.get(CALL_ELECTION)
        if call is not None and call.motive and state.leader not in (None, resident.resident_id):
            since = world.clock.day - state.term_began
            if (
                profile.loyalty <= call.motive.get("loyalty_below", 0.0)
                and profile.trust <= call.motive.get("trust_below", 0.0)
                and since >= call.motive.get("days_since_vote", 0.0)
            ):
                draft = self._draft(world, CALL_ELECTION, resident.resident_id)
                yield Idea(self.conviction(world, resident, draft), CALL_ELECTION)
        change = kinds.get(CHANGE_GOVERNMENT)
        if change is not None and change.motive and definition is not None:
            settled = world.clock.day - (state.chosen_on or world.clock.day)
            if profile.trust <= change.motive.get("trust_below", 0.0) and settled >= change.motive.get(
                "days_since_chosen", 0.0
            ):
                here = opinion.appeal_of(world, resident, state.kind)
                for government_id in world.registries.politics.governments:
                    gain = opinion.appeal_of(world, resident, government_id) - here
                    if government_id != state.kind and gain >= change.motive.get("appeal_above", 0.0):
                        yield Idea(gain, CHANGE_GOVERNMENT, government=government_id)
        expel = kinds.get(EXPEL)
        if expel is not None and expel.motive:
            since = world.clock.total_minutes - int(expel.motive.get("days", 0.0) * 24 * 60)
            for other in world.residents.values():
                feelings = world.relationships.get((resident.resident_id, other.resident_id))
                if other is resident or feelings is None:
                    continue
                if feelings.resentment < expel.motive.get("resentment_above", 0.0):
                    continue
                if len(self.known_misdeeds(world, resident, other.resident_id, since)) < expel.motive.get("misdeeds", 1.0):
                    continue
                draft = self._draft(world, EXPEL, resident.resident_id, target=other.resident_id)
                wish = self.mind(world, resident, draft, alone=True)[0]
                if wish >= settings.raise_from:
                    yield Idea(wish, EXPEL, target=other.resident_id)

    def _names_for(self, world: "SimulationWorld", resident: Resident, law: LawDefinition) -> dict[str, str] | None:
        """What a resident would have a law name, if it has to name something. None if they
        have nothing to name."""
        if law.param is None:
            return {}
        hated = world.tastes.favourites(world, resident).get("hated_food")
        return {"item": hated} if hated is not None else None

    def _moved(self, world: "SimulationWorld", resident: Resident, law: LawDefinition, regard: float) -> bool:
        """Whether a resident has the reason the law's data gives for wanting it, as far as they know."""
        (motive, value), = (law.motive or {"conviction": 0.0}).items()
        people = max(1, len(world.residents))
        if motive == "need_above":
            return getattr(resident.needs, str(value["need"]), 0.0) >= float(value["level"])
        if motive == "stock_below":
            return opinion.common_stock(world, str(value["category"])) / people < float(value["per_resident"])
        if motive in ("fund_below", "fund_above"):
            if world.fund.currency(world) is None:
                return False
            each = world.trading.fund / people
            return each < float(value) if motive == "fund_below" else each > float(value)
        if motive == "known_facts":
            since = world.clock.total_minutes - int(float(value.get("days", 7)) * 24 * 60)
            dark = world.registries.event_settings.get("perception", {}).get("dark_hours")
            known = 0
            for belief in world.knowledge.beliefs_of(resident.resident_id):
                fact = world.knowledge.facts.get(belief.fact_id)
                if fact is None or fact.event_type not in value.get("types", ()) or fact.timestamp < since:
                    continue
                hour = fact.timestamp // 60 % 24
                if value.get("night") and not (dark and _in_hours(hour, (int(dark[0]), int(dark[1])))):
                    continue
                known += 1
            return known >= int(value.get("count", 1))
        if motive == "conviction":
            return regard >= float(value)
        if motive == "stake":
            return opinion.value_of(world, resident, str(value)) > 0
        return False

    def _whim(self, world: "SimulationWorld", resident: Resident, law: LawDefinition, params: Mapping[str, str]) -> bool:
        """Whether whoever leads takes it into their head to pass a law for no better reason
        than liking it: the more authoritarian the settlement, the likelier, and always the
        same for the same day and law."""
        state = world.government
        settings = world.registries.laws
        if state.leader != resident.resident_id:
            return False
        beyond = state.measures["authoritarianism"] - settings.whim_from
        if beyond < 0 or opinion.weigh(world, resident, law.whim_opinion, params) < WHIM_WISH:
            return False
        chance = settings.whim_chance * beyond / max(1.0, 100.0 - settings.whim_from)
        return SimulationRNG.keyed(world.rng.seed, "whim", law.law_id, world.clock.day).random() < chance


def _in_hours(hour: int, window: tuple[int, int]) -> bool:
    start, end = window
    return start <= hour < end if start <= end else hour >= start or hour < end
