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
BROOD_ACTION = "brood"
# Resentment below this is not a grievance worth a crisis, however stressed the resident is.
MIN_RESENTMENT = 30.0
# Nobody stops to stew over a grudge while this hungry or tired: the body comes first.
MAX_BODILY_NEED = 70.0
SCORE_NOISE = 0.03
MAX_IMPORTANCE = 69
ADVICE_STRENGTH = 1.0


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
        "health": resident.health / 100.0,
    }
    if target is not None:
        feelings = world.relationship(resident.resident_id, target.resident_id)
        inputs["affection"] = (feelings.affection + 100.0) / 200.0
        inputs["resentment"] = feelings.resentment / 100.0
        inputs["fear"] = feelings.fear / 100.0
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

    def _cooldown_key(self, kind: str, resident_id: str) -> str:
        return resident_id if kind == GRIEVANCE else f"{kind}:{resident_id}"

    def _cooling_down(self, world: "SimulationWorld", definition: DecisionDefinition, resident: Resident) -> bool:
        last = world.crisis_cooldowns.get(self._cooldown_key(definition.kind, resident.resident_id))
        return last is not None and world.clock.total_minutes - last < definition.cooldown_minutes

    def _open(
        self,
        world: "SimulationWorld",
        resident: Resident,
        target: Resident,
        definition: DecisionDefinition,
        anger_value: float,
    ) -> Activity:
        """Open a decision for `resident` about `target` and have them wait for advice."""
        world.decision_count += 1
        importance = min(
            MAX_IMPORTANCE, definition.importance + round((anger_value - definition.anger_threshold) / 2)
        )
        decision = Decision(
            decision_id=f"decision_{world.decision_count}",
            resident_id=resident.resident_id,
            prompt=definition.prompt.replace("{target}", target.name),
            options=[
                DecisionOption(option.option_id, option.text.replace("{target}", target.name), dict(option.influence))
                for option in definition.options
            ],
            related_event_type=definition.event_type,
            kind=definition.kind,
            deadline=world.clock.total_minutes + definition.window_minutes,
            crisis=Crisis(resident.resident_id, target.resident_id, anger_value, importance, intent=""),
        )
        decision.crisis.intent = self.leaning(world, decision)
        world.decisions[decision.decision_id] = decision
        resident.current_action = BROOD_ACTION
        room = world.room_at(resident.tile)
        world.emit_event(
            DomainEvent(
                event_type=definition.event_type,
                importance=importance,
                text=self._fill(definition.text, resident, target),
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
        if chosen.memory is not None and target is not None:
            world.memories.remember(
                resident.resident_id,
                Memory(
                    text=chosen.memory.replace("{target}", target.name),
                    importance=float(crisis.urgency if crisis else definition.importance),
                    emotional_value=-0.3,
                    people=[target.resident_id],
                    tags=["crisis", chosen.outcome_id],
                    timestamp=world.clock.total_minutes,
                    location_id=location_id,
                ),
            )
        if chosen.interaction is not None and target is not None:
            resident.activity = self.social.pursue(world, resident, target, chosen.interaction)
            resident.current_action = "walking"
        else:
            resident.activity = None
            resident.current_action = "idle"

        world.crisis_cooldowns[self._cooldown_key(decision.kind, resident.resident_id)] = world.clock.total_minutes
        advice = f"consejo: {option.text}" if option is not None else "sin consejo"
        world.emit_event(
            DomainEvent(
                event_type="crisis_resolved",
                importance=crisis.urgency if crisis else definition.importance,
                text=f"{self._fill(chosen.text, resident, target)} ({advice})",
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

    def _fill(self, text: str, resident: Resident, target: Resident | None) -> str:
        return text.replace("{name}", resident.name).replace("{target}", target.name if target else "nadie")
