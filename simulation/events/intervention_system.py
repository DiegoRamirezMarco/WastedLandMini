"""Crises the player can weigh in on.

A resident whose grievance boils over stops to stew, and a decision opens. The player may
give advice; advice only shifts the scores of what the resident might do. The resident then
picks for themselves, or picks alone once the window closes.
"""

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from simulation.ai.decision_system import advice_influence
from simulation.events.crisis import Crisis
from simulation.events.decision import Decision, DecisionDefinition, DecisionOption
from simulation.events.event import DomainEvent
from simulation.memory.memory import Memory
from simulation.residents.activity import Activity
from simulation.residents.resident import Resident
from simulation.social.social_system import SocialSystem, tension

if TYPE_CHECKING:
    from simulation.world import SimulationWorld

GRIEVANCE = "grievance"
BRAWL = "brawl"
JOB_OFFER = "job_offer"
CONFESSION = "confession"
BREAKUP = "breakup"
BROOD_ACTION = "brood"
# Resentment below this is not a grievance worth a crisis, however stressed the resident is.
MIN_RESENTMENT = 30.0
# Nobody stops to stew over a grudge while this hungry or tired: the body comes first.
MAX_BODILY_NEED = 70.0
SCORE_NOISE = 0.03
MAX_IMPORTANCE = 69
ADVICE_STRENGTH = 1.0
# After someone has been asked about a vacant job, nobody else is asked about it for this long.
JOB_ASK_INTERVAL_MINUTES = 360


def anger(world: "SimulationWorld", resident: Resident, target: Resident) -> float:
    """How close a resident is to boiling over at someone, from 0 to 100."""
    resentment = world.relationship(resident.resident_id, target.resident_id).resentment
    value = (
        0.6 * resentment
        + 0.3 * resident.needs.stress
        + 0.2 * (resident.personality.aggression - 50.0)
    )
    return max(0.0, min(100.0, value))


def escalation_chance(world: "SimulationWorld", resident: Resident, target: Resident) -> float:
    """Probability that a resident who has just argued with someone squares up to them.

    Bad blood, a temper and rashness push towards it; fear of the other and empathy hold back.
    """
    personality = resident.personality
    fear = world.relationship(resident.resident_id, target.resident_id).fear
    chance = (
        0.03
        + 0.25 * tension(world, resident, target)
        + 0.25 * max(0.0, (personality.aggression - 50.0) / 50.0)
        + 0.15 * max(0.0, (personality.impulsiveness - 50.0) / 50.0)
        - 0.3 * fear / 100.0
        - 0.2 * personality.empathy / 100.0
    )
    return max(0.0, min(0.6, chance))


def score_inputs(world: "SimulationWorld", resident: Resident, target: Resident | None, anger_value: float) -> dict[str, float]:
    """The inputs an outcome's score can weigh, each from 0 to 1."""
    personality = resident.personality
    inputs = {
        "bias": 1.0,
        "anger": anger_value / 100.0,
        "aggression": personality.aggression / 100.0,
        "impulsiveness": personality.impulsiveness / 100.0,
        "empathy": personality.empathy / 100.0,
        "courage": personality.courage / 100.0,
        "sociability": personality.sociability / 100.0,
        "greed": personality.greed / 100.0,
        "stress": resident.needs.stress / 100.0,
        "affection": 0.5,
        "resentment": 0.0,
        "fear": 0.0,
        "attraction": 0.0,
        "health": resident.health / 100.0,
        "vacancy": 0.0,
        "idle": 0.0,
    }
    if target is not None:
        feelings = world.relationship(resident.resident_id, target.resident_id)
        inputs["affection"] = (feelings.affection + 100.0) / 200.0
        inputs["resentment"] = feelings.resentment / 100.0
        inputs["fear"] = feelings.fear / 100.0
        inputs["attraction"] = feelings.attraction / 100.0
    return inputs


@dataclass
class InterventionSystem:
    social: SocialSystem = field(default_factory=SocialSystem)

    def maybe_open(self, world: "SimulationWorld", resident: Resident) -> Activity | None:
        """Open a crisis if this resident has a grievance that has boiled over.

        Returns the activity of waiting for advice, or None if there is no crisis.
        """
        definition = world.registries.decisions.get(GRIEVANCE)
        if definition is None or self.pending_for(world, resident.resident_id) is not None:
            return None
        if self._cooling_down(world, definition, resident):
            return None
        if max(resident.needs.hunger, resident.needs.tiredness) > MAX_BODILY_NEED:
            return None
        target = self._grievance_target(world, resident)
        if target is None:
            return None
        anger_value = anger(world, resident, target)
        if anger_value < definition.anger_threshold:
            return None
        return self._open(world, resident, target, definition, anger_value)

    def maybe_brawl(self, world: "SimulationWorld", resident: Resident, target: Resident) -> Activity | None:
        """After an argument, maybe have `resident` square up to `target`.

        A fight can do lasting harm, so it never starts outright: a decision opens first and the
        player may step in. Returns the activity of waiting for that, or None.
        """
        definition = world.registries.decisions.get(BRAWL)
        if definition is None or self._cooling_down(world, definition, resident):
            return None
        if self.pending_for(world, resident.resident_id) or self.pending_for(world, target.resident_id):
            return None
        if world.rng.random() >= escalation_chance(world, resident, target):
            return None
        return self._open(world, resident, target, definition, anger(world, resident, target))

    def maybe_offer_job(self, world: "SimulationWorld", resident: Resident) -> Activity | None:
        """Put a job that has gone unfilled too long to this resident, if they are the one to ask.

        Changing jobs changes the settlement, so it opens a decision the player may weigh in on.
        Returns the activity of waiting for that, or None.
        """
        definition = world.registries.decisions.get(JOB_OFFER)
        if definition is None:
            return None
        if self.pending_for(world, resident.resident_id) is not None or self._cooling_down(world, definition, resident):
            return None
        if max(resident.needs.hunger, resident.needs.tiredness) > MAX_BODILY_NEED:
            return None
        now = world.clock.total_minutes
        # Someone looking for work does not wait to be asked: they look at what there is.
        opening = world.staffing.opening_for(world, resident)
        if opening is not None and not any(decision.job_id == opening for decision in world.decisions.values()):
            return self._open(world, resident, None, definition, 0.0, opening)
        for job_id in world.staffing.overdue(world):
            asked_at = world.crisis_cooldowns.get(self._job_key(job_id))
            if asked_at is not None and now - asked_at < JOB_ASK_INTERVAL_MINUTES:
                continue
            asked = next(
                (
                    candidate
                    for candidate in world.staffing.candidates(world, job_id)
                    if not self._cooling_down(world, definition, candidate)
                ),
                None,
            )
            if asked is resident:
                world.crisis_cooldowns[self._job_key(job_id)] = now
                return self._open(world, resident, None, definition, 0.0, job_id)
        return None

    def _job_key(self, job_id: str) -> str:
        """Key under which the last time a vacant job was put to someone is kept."""
        return f"{JOB_OFFER}@{job_id}"

    def maybe_romance(self, world: "SimulationWorld", resident: Resident) -> Activity | None:
        """Open a decision if a resident has something of the heart to make up their mind about.

        Saying what they feel to someone, or leaving a partner, changes two lives, so neither
        happens outright: the player may weigh in first. Returns the activity of waiting, or None.
        """
        if self.pending_for(world, resident.resident_id) is not None:
            return None
        if max(resident.needs.hunger, resident.needs.tiredness) > MAX_BODILY_NEED:
            return None
        for kind, find in (
            (BREAKUP, world.bonds.soured_partner),
            (CONFESSION, world.bonds.confession_target),
        ):
            definition = world.registries.decisions.get(kind)
            if definition is None or self._cooling_down(world, definition, resident):
                continue
            target = find(world, resident)
            if target is None or self.pending_for(world, target.resident_id) is not None:
                continue
            return self._open(world, resident, target, definition, anger(world, resident, target))
        return None

    def ask(self, world: "SimulationWorld", resident: Resident, kind: str) -> Decision | None:
        """Open a decision for a resident without stopping what they are doing.

        For someone who cannot stand and think it over where the player sees them, such as a
        resident outside the settlement. Returns the decision, or None if they have one open.
        """
        definition = world.registries.decisions.get(kind)
        if definition is None or self.pending_for(world, resident.resident_id) is not None:
            return None
        decision = self._decision(world, resident, None, definition, 0.0)
        world.decisions[decision.decision_id] = decision
        world.emit_event(
            DomainEvent(
                event_type=definition.event_type,
                importance=decision.crisis.urgency,
                text=self.fill(world, definition.text, resident, None),
                participants=[resident.resident_id],
            )
        )
        return decision

    def suggest_job(self, world: "SimulationWorld", resident_id: str, job_id: str, option_id: str) -> str | None:
        """The player puts it to a resident that they take up a job, with one of the usual advices.

        The resident decides on the spot, as they would at the end of any decision: the advice
        shifts the scores and they pick. Returns what they chose, or None if they cannot be asked:
        no such job or no free post for it, a decision already open, or asked too recently.
        """
        definition = world.registries.decisions.get(JOB_OFFER)
        resident = world.residents.get(resident_id)
        job = world.registries.jobs.get(job_id)
        if definition is None or resident is None or job is None or resident.job_id == job_id:
            return None
        if world.staffing.free_post(world, job) is None:
            return None
        if self.pending_for(world, resident_id) is not None or self._cooling_down(world, definition, resident):
            return None
        decision = self._decision(world, resident, None, definition, 0.0, job_id)
        return self._settle(world, decision, option_id, waiting=False)

    def _cooldown_key(self, kind: str, resident_id: str) -> str:
        return resident_id if kind == GRIEVANCE else f"{kind}:{resident_id}"

    def _cooling_down(self, world: "SimulationWorld", definition: DecisionDefinition, resident: Resident) -> bool:
        last = world.crisis_cooldowns.get(self._cooldown_key(definition.kind, resident.resident_id))
        return last is not None and world.clock.total_minutes - last < definition.cooldown_minutes

    def _decision(
        self,
        world: "SimulationWorld",
        resident: Resident,
        target: Resident | None,
        definition: DecisionDefinition,
        anger_value: float,
        job_id: str | None = None,
    ) -> Decision:
        """A decision for `resident` about `target`, or about taking up a job. It is not open yet."""
        world.decision_count += 1
        importance = min(
            MAX_IMPORTANCE, definition.importance + round((anger_value - definition.anger_threshold) / 2)
        )
        decision = Decision(
            decision_id=f"decision_{world.decision_count}",
            resident_id=resident.resident_id,
            prompt=self.fill(world, definition.prompt, resident, target, job_id),
            options=[
                DecisionOption(
                    option.option_id, self.fill(world, option.text, resident, target, job_id), dict(option.influence)
                )
                for option in definition.options
            ],
            related_event_type=definition.event_type,
            kind=definition.kind,
            deadline=world.clock.total_minutes + definition.window_minutes,
            crisis=Crisis(
                resident.resident_id,
                target.resident_id if target is not None else None,
                anger_value,
                importance,
                intent="",
            ),
            job_id=job_id,
        )
        decision.crisis.intent = self.leaning(world, decision)
        return decision

    def _open(
        self,
        world: "SimulationWorld",
        resident: Resident,
        target: Resident | None,
        definition: DecisionDefinition,
        anger_value: float,
        job_id: str | None = None,
    ) -> Activity:
        """Open a decision for `resident` and have them wait for advice."""
        decision = self._decision(world, resident, target, definition, anger_value, job_id)
        world.decisions[decision.decision_id] = decision
        resident.current_action = BROOD_ACTION
        room = world.room_at(resident.tile)
        world.emit_event(
            DomainEvent(
                event_type=definition.event_type,
                importance=decision.crisis.urgency,
                text=self.fill(world, definition.text, resident, target, job_id),
                participants=[resident.resident_id],
                location_id=room.room_id if room is not None else None,
            ),
            at=resident.tile,
        )
        # A little longer than the window, so the decision is always settled before they move on.
        return Activity(BROOD_ACTION, minutes_left=definition.window_minutes + 5, using=True)

    def tick(self, world: "SimulationWorld") -> None:
        """Let residents whose window has closed decide without advice."""
        now = world.clock.total_minutes
        for decision in [d for d in world.decisions.values() if now >= d.deadline]:
            self.resolve(world, decision.decision_id, None)

    def pending_for(self, world: "SimulationWorld", resident_id: str) -> Decision | None:
        return next((d for d in world.decisions.values() if d.resident_id == resident_id), None)

    def cancel_for(self, world: "SimulationWorld", resident_id: str) -> None:
        """Drop a resident's open decision because events overtook it."""
        decision = self.pending_for(world, resident_id)
        if decision is not None:
            del world.decisions[decision.decision_id]
            world.crisis_cooldowns[self._cooldown_key(decision.kind, resident_id)] = world.clock.total_minutes

    def scores(
        self, world: "SimulationWorld", decision: Decision, option: DecisionOption | None
    ) -> dict[str, float]:
        """Score of each outcome for the deciding resident, with the given advice applied."""
        definition = world.registries.decisions[decision.kind]
        resident = world.residents[decision.resident_id]
        crisis = decision.crisis
        target = world.residents.get(crisis.target_id) if crisis and crisis.target_id else None
        inputs = score_inputs(world, resident, target, crisis.anger if crisis else 0.0)
        if decision.job_id is not None:
            inputs.update(world.staffing.decision_inputs(world, resident, decision.job_id))
        heed = advice_influence(resident, ADVICE_STRENGTH)
        scores: dict[str, float] = {}
        for outcome_id, outcome in definition.outcomes.items():
            score = sum(weight * inputs[name] for name, weight in outcome.score.items())
            if option is not None:
                score += option.influence.get(outcome_id, 0.0) * heed
            scores[outcome_id] = score
        return scores

    def leaning(self, world: "SimulationWorld", decision: Decision) -> str:
        """What the resident would most likely do if left alone."""
        scores = self.scores(world, decision, None)
        return max(scores, key=lambda outcome_id: scores[outcome_id])

    def resolve(self, world: "SimulationWorld", decision_id: str, option_id: str | None) -> str | None:
        """Close a decision: the resident weighs the advice and acts. Returns the outcome chosen."""
        decision = world.decisions.pop(decision_id, None)
        if decision is None:
            return None
        resident = world.residents.get(decision.resident_id)
        brooding = resident is not None and resident.activity is not None and resident.activity.action == BROOD_ACTION
        return self._settle(world, decision, option_id, waiting=brooding)

    def _settle(self, world: "SimulationWorld", decision: Decision, option_id: str | None, waiting: bool) -> str | None:
        """Have the resident weigh the advice, pick an outcome and act on it.

        `waiting` says whether they had stopped to think it over, and so go back to their day.
        """
        resident = world.residents.get(decision.resident_id)
        definition = world.registries.decisions.get(decision.kind)
        if resident is None or definition is None:
            return None
        crisis = decision.crisis
        target = world.residents.get(crisis.target_id) if crisis and crisis.target_id else None
        option = next((o for o in decision.options if o.option_id == option_id), None)

        scores = self.scores(world, decision, option)
        noisy = {outcome_id: score + world.rng.random() * SCORE_NOISE for outcome_id, score in scores.items()}
        chosen = definition.outcomes[max(noisy, key=lambda outcome_id: noisy[outcome_id])]

        resident.needs.apply(chosen.needs)
        if target is not None:
            feelings = world.relationship(resident.resident_id, target.resident_id)
            for feeling, delta in chosen.feelings.items():
                feelings.adjust(feeling, delta)
        room = world.room_at(resident.tile)
        location_id = room.room_id if room is not None else None
        if chosen.memory is not None:
            world.memories.remember(
                resident.resident_id,
                Memory(
                    text=self.fill(world, chosen.memory, resident, target, decision.job_id),
                    importance=float(crisis.urgency if crisis else definition.importance),
                    emotional_value=-0.3 if target is not None else 0.2,
                    people=[target.resident_id] if target is not None else [],
                    tags=["crisis", chosen.outcome_id],
                    timestamp=world.clock.total_minutes,
                    location_id=location_id,
                ),
            )
        if chosen.takes_job and decision.job_id is not None:
            world.staffing.assign(world, resident, decision.job_id)
        if chosen.expedition is not None:
            world.expeditions.choose(world, resident, chosen.expedition)
        # The answer is put into words before the gate is opened or shut, while the visitor still has a name.
        answer = self.fill(world, chosen.text, resident, target, decision.job_id)
        if chosen.gate is not None:
            world.happenings.answer_gate(world, chosen.gate)
        if chosen.raid is not None:
            world.happenings.answer_raid(world, resident, chosen.raid)
        if chosen.interaction is not None and target is not None:
            resident.activity = self.social.pursue(world, resident, target, chosen.interaction)
            resident.current_action = "walking"
        elif waiting:
            resident.activity = None
            resident.current_action = "idle"

        world.crisis_cooldowns[self._cooldown_key(decision.kind, resident.resident_id)] = world.clock.total_minutes
        advice = f"consejo: {option.text}" if option is not None else "sin consejo"
        world.emit_event(
            DomainEvent(
                event_type="crisis_resolved",
                importance=crisis.urgency if crisis else definition.importance,
                text=f"{answer} ({advice})",
                participants=[resident.resident_id],
                location_id=location_id,
            ),
            at=resident.tile,
        )
        return chosen.outcome_id

    def _grievance_target(self, world: "SimulationWorld", resident: Resident) -> Resident | None:
        """Whoever the resident resents most, if that is enough to be a grievance."""
        best: tuple[float, Resident] | None = None
        for other in world.residents.values():
            if other is resident:
                continue
            feelings = world.relationships.get((resident.resident_id, other.resident_id))
            resentment = feelings.resentment if feelings is not None else 0.0
            if resentment >= MIN_RESENTMENT and (best is None or resentment > best[0]):
                best = (resentment, other)
        return best[1] if best is not None else None

    def fill(
        self,
        world: "SimulationWorld",
        text: str,
        resident: Resident,
        target: Resident | None,
        job_id: str | None = None,
    ) -> str:
        """Put the names of who and what a decision is about into one of its texts."""
        job = world.registries.jobs.get(job_id or "")
        visitor = world.happenings.visitor(world)
        return (
            text.replace("{name}", resident.name)
            .replace("{target}", target.name if target else "nadie")
            .replace("{job}", job.name if job else "ninguno")
            .replace("{visitor}", visitor.name if visitor else "alguien")
        )
