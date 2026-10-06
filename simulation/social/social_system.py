"""Conversations and arguments between two residents standing next to each other."""

from collections.abc import Callable
from typing import TYPE_CHECKING

from simulation.ai.crowd import spots_taken
from simulation.ai.utility_ai import DISTANCE_COST, ScoredAction, need_urgency
from simulation.events.event import DomainEvent
from simulation.knowledge.knowledge_system import share_rumor
from simulation.memory.memory import Memory
from simulation.residents.activity import MOVE_TILES_PER_MINUTE, SHELTER_ACTION, WANDER_ACTION, Activity
from simulation.residents.resident import Resident
from simulation.social.bonds import AFFAIR_EVENT, AFFAIR_IMPORTANCE, TRYST
from simulation.social.interaction import InteractionDefinition
from simulation.social.relationship import SIGNED_FEELINGS, Relationship
from simulation.work.work_system import WORK_ACTION
from world.map import Tile
from world.pathfinding import NEIGHBOURS, find_path, manhattan

if TYPE_CHECKING:
    from simulation.world import SimulationWorld

# Action of a resident who is walking over to talk to someone.
TALK_ACTION = "talk"
CHAT_ID = "chat"
ARGUMENT_ID = "argument"

TALK_APPEAL = 1.2
CONFRONT_WEIGHT = 0.3
ARRIVAL_SLACK_TILES = 2
# How long someone set on an exchange keeps after their partner before giving up.
PURSUIT_MINUTES = 120
# Extra importance of an argument someone went out of their way to start.
CONFRONTATION_IMPORTANCE = 15
# After an argument a resident does not seek the other out for this long, unless a crisis drives them.
ARGUMENT_COOLDOWN_MINUTES = 360
LOW_MOOD_ARGUMENT_WEIGHT = 0.2


def _clamp(value: float, lowest: float, highest: float) -> float:
    return max(lowest, min(highest, value))


def tension(world: "SimulationWorld", a: Resident, b: Resident) -> float:
    """Shared resentment between two residents, from 0 to 1."""
    there = world.relationship(a.resident_id, b.resident_id).resentment
    back = world.relationship(b.resident_id, a.resident_id).resentment
    return (there + back) / 200.0


def argument_chance(world: "SimulationWorld", a: Resident, b: Resident) -> float:
    """Probability that a meeting between two residents turns into an argument."""
    temper = (a.personality.aggression + b.personality.aggression) / 200.0 - 0.5
    worst_need = max(
        getattr(resident.needs, need) for resident in (a, b) for need in ("hunger", "tiredness", "stress")
    )
    strain = max(0.0, worst_need / 100.0 - 0.6)
    warmth = (
        world.relationship(a.resident_id, b.resident_id).affection
        + world.relationship(b.resident_id, a.resident_id).affection
    ) / 200.0
    low_mood = max(0.0, (50.0 - min(a.mood, b.mood)) / 50.0)
    chance = (
        0.06
        + 0.5 * tension(world, a, b)
        + 0.15 * temper
        + 0.2 * strain
        + LOW_MOOD_ARGUMENT_WEIGHT * low_mood
        - 0.1 * warmth
    )
    return _clamp(chance, 0.02, 0.9)


def feeling_changes(
    definition: InteractionDefinition,
    resident: Resident,
    partner: Resident,
    feelings: Relationship,
    attraction_rate: float = 0.0,
) -> dict[str, float]:
    """How `resident`'s feelings about `partner` change. Depends on both personalities,
    so the two sides of one exchange come out different. Affection, trust and attraction grow
    more slowly the higher they already are, and attraction only grows at `attraction_rate`:
    not at all where there is nothing to grow from."""
    mine, theirs = resident.personality, partner.personality
    if definition.hostile:
        other = 0.5 + theirs.aggression / 100.0
        own = {"resentment": 1.5 - mine.empathy / 100.0, "fear": 1.5 - mine.courage / 100.0}
    else:
        other = 0.5 + theirs.empathy / 100.0
        own = {"affection": 0.5 + mine.sociability / 100.0, "resentment": 0.5 + mine.empathy / 100.0}
    changes: dict[str, float] = {}
    for feeling, base in definition.relationship.items():
        delta = base * other * own.get(feeling, 1.0)
        if feeling == "attraction" and base > 0:
            delta = base * attraction_rate
        if delta > 0 and feeling in (*SIGNED_FEELINGS, "attraction"):
            delta *= max(0.0, 1.0 - getattr(feelings, feeling) / 100.0)
        changes[feeling] = delta
    return changes


class SocialSystem:
    def candidates(self, world: "SimulationWorld", resident: Resident) -> list[ScoredAction]:
        """Score walking over to each resident who can be talked to right now."""
        scored: list[ScoredAction] = []
        for partner in world.residents.values():
            if partner is resident or not self._can_be_approached(world, partner, resident):
                continue
            distance = manhattan(resident.tile, partner.tile)
            stays = partner.activity.minutes_left if partner.activity is not None else 0
            if stays * MOVE_TILES_PER_MINUTE < distance + ARRIVAL_SLACK_TILES:
                continue
            feelings = world.relationship(resident.resident_id, partner.resident_id)
            if (
                feelings.last_argued is not None
                and world.clock.total_minutes - feelings.last_argued < ARGUMENT_COOLDOWN_MINUTES
            ):
                continue
            affinity = _clamp(
                1.0 + (feelings.affection - feelings.resentment - feelings.fear) / 100.0, 0.2, 1.8
            )
            confront = (feelings.resentment / 100.0) * (resident.personality.aggression / 100.0)
            score = (
                need_urgency(resident, "social") * affinity * TALK_APPEAL
                + confront * CONFRONT_WEIGHT
                - DISTANCE_COST * distance
            )
            scored.append(ScoredAction(TALK_ACTION, score, partner_id=partner.resident_id))
        return scored

    def approach(
        self,
        world: "SimulationWorld",
        resident: Resident,
        partner: Resident,
        passable: Callable[[Tile], bool] | None = None,
    ) -> Activity | None:
        """Plan a walk to a free tile next to `partner`: one nobody else stands on or is heading to.

        `passable` says where can be walked, for a walk that has to go round more than the map itself.
        """
        passable = passable or world.passable()
        ground = world.passable()
        taken = spots_taken(world, resident)
        spots = sorted(
            (
                (partner.x + dx, partner.y + dy)
                for dx, dy in NEIGHBOURS
                if ground((partner.x + dx, partner.y + dy)) and (partner.x + dx, partner.y + dy) not in taken
            ),
            # Standing beside the partner comes first: two people on the same row face each other.
            key=lambda spot: (
                spot[1] != partner.y,
                manhattan(resident.tile, spot),
                spot[1],
                spot[0],
            ),
        )
        for spot in spots:
            path = find_path(resident.tile, spot, passable)
            if path is not None:
                return Activity(TALK_ACTION, path=path, partner_id=partner.resident_id)
        return None

    def pursue(
        self, world: "SimulationWorld", resident: Resident, partner: Resident, interaction_id: str
    ) -> Activity:
        """Set out to have one particular exchange with `partner`, whatever they are doing."""
        planned = self.approach(world, resident, partner)
        return Activity(
            TALK_ACTION,
            path=planned.path if planned is not None else [],
            minutes_left=PURSUIT_MINUTES,
            partner_id=partner.resident_id,
            intent=interaction_id,
        )

    def tick(self, world: "SimulationWorld", resident: Resident, activity: Activity) -> None:
        """Spend one minute of a meeting: start it on arrival, end it when time is up."""
        if not activity.using:
            started = self._begin(world, resident, activity)
            if started is None:
                if activity.intent is None or not self._keep_pursuing(world, resident, activity):
                    resident.activity = None
                    resident.current_action = "idle"
                return
            activity = started
        definition = world.registries.interactions[activity.action]
        resident.needs.apply(definition.per_minute)
        partner = world.residents.get(activity.partner_id or "")
        if definition.romance == TRYST and partner is not None:
            # Two people off alone can still be come across.
            world.bonds.seen(world, resident, partner)
        activity.minutes_left -= 1
        if activity.minutes_left <= 0:
            self._conclude(world, resident, activity, definition)

    def _can_be_approached(self, world: "SimulationWorld", partner: Resident, by: Resident) -> bool:
        for other in world.residents.values():
            if other is partner or other is by or other.activity is None:
                continue
            if other.activity.partner_id == partner.resident_id:
                return False
        activity = partner.activity
        if activity is None:
            return True
        if activity.partner_id is not None or not activity.using:
            return False
        if activity.action == WORK_ACTION:
            job = world.work.job_of(world, partner)
            return job is not None and job.interruptible
        if activity.target_id is None:
            # Strolling, or waiting out the weather: either way, free to talk.
            return activity.action in (WANDER_ACTION, SHELTER_ACTION)
        placed = world.interactables.get(activity.target_id)
        use = world.definition_of(placed).use if placed is not None else None
        return use is not None and use.interruptible

    def _in_exchange(self, resident: Resident) -> bool:
        activity = resident.activity
        return activity is not None and activity.using and activity.partner_id is not None

    def _keep_pursuing(self, world: "SimulationWorld", resident: Resident, activity: Activity) -> bool:
        """Follow a partner who moved or is busy. False once it is time to give up."""
        partner = world.residents.get(activity.partner_id or "")
        activity.minutes_left -= 1
        if partner is None or activity.minutes_left <= 0:
            return False
        planned = self.approach(world, resident, partner)
        if planned is None:
            return False
        activity.path = planned.path
        resident.current_action = "walking" if planned.path else "idle"
        return True

    def _begin(self, world: "SimulationWorld", resident: Resident, approach: Activity) -> Activity | None:
        """Start the exchange for both residents. Returns `resident`'s new activity."""
        partner = world.residents.get(approach.partner_id or "")
        if partner is None or partner.away or manhattan(resident.tile, partner.tile) != 1:
            return None
        if approach.intent is not None:
            # A resident with their mind made up interrupts anything but another exchange.
            definition = world.registries.interactions.get(approach.intent)
            if definition is None or self._in_exchange(partner):
                return None
            if definition.romance is not None and not world.bonds.may_begin(world, resident, partner, definition):
                if world.relationship(resident.resident_id, partner.resident_id).last_together == world.clock.total_minutes:
                    # Turned down: there is nothing to wait around for.
                    approach.minutes_left = 0
                return None
        else:
            if not self._can_be_approached(world, partner, resident):
                return None
            hostile = world.rng.random() < argument_chance(world, resident, partner)
            definition = world.registries.interactions[ARGUMENT_ID if hostile else CHAT_ID]
        minutes = world.rng.randint(*definition.minutes)
        order = list(world.residents)
        partner_already_ticked = order.index(partner.resident_id) < order.index(resident.resident_id)

        for one, other in ((resident, partner), (partner, resident)):
            one.activity = Activity(
                definition.interaction_id,
                minutes_left=minutes,
                using=True,
                partner_id=other.resident_id,
                # Whoever came for this exchange keeps it as their intent, so its end is theirs to settle.
                intent=approach.intent if one is resident else None,
            )
            one.current_action = definition.interaction_id
            dx, dy = other.x - one.x, other.y - one.y
            one.facing = ("right" if dx > 0 else "left") if dx else ("down" if dy > 0 else "up")
        if partner_already_ticked:
            # The partner has had this minute already; give them their share of it.
            partner.needs.apply(definition.per_minute)
            partner.activity.minutes_left -= 1

        # Whatever the partner was stewing over is overtaken by this.
        world.interventions.cancel_for(world, partner.resident_id)
        self._announce(world, resident, partner, definition, sought=approach.intent is not None)
        return resident.activity

    def _announce(
        self,
        world: "SimulationWorld",
        resident: Resident,
        partner: Resident,
        definition: InteractionDefinition,
        sought: bool = False,
    ) -> None:
        speaker, listener = resident, partner
        if definition.hostile and self._heat(world, partner, resident) > self._heat(world, resident, partner):
            speaker, listener = partner, resident
        text = definition.text.replace("{a}", speaker.name).replace("{b}", listener.name)
        lines = world.registries.dialogue.get(definition.dialogue or "", [])
        if lines:
            text = f'{text} — {speaker.name}: "{world.rng.choice(lines)}"'
        room = world.room_at(resident.tile)
        importance = definition.importance + round(
            definition.tension_importance * tension(world, resident, partner)
        )
        if sought and definition.hostile:
            importance += CONFRONTATION_IMPORTANCE
        event_type, subjects = f"{definition.interaction_id}_started", None
        betrayed = world.bonds.betrayed_by(world, speaker, listener) if definition.romance == TRYST else []
        if betrayed:
            # Behind someone's back it is another thing, and it is also about whoever is not there.
            event_type, subjects = AFFAIR_EVENT, [speaker.resident_id, listener.resident_id, *betrayed]
            importance += AFFAIR_IMPORTANCE
        world.emit_event(
            DomainEvent(
                event_type=event_type,
                importance=importance,
                text=text,
                participants=[speaker.resident_id, listener.resident_id],
                location_id=room.room_id if room is not None else None,
            ),
            at=resident.tile,
            fact_text=(
                definition.fact.replace("{a}", speaker.name).replace("{b}", listener.name)
                if definition.fact is not None
                else None
            ),
            subjects=subjects,
        )

    def _heat(self, world: "SimulationWorld", resident: Resident, towards: Resident) -> float:
        feelings = world.relationship(resident.resident_id, towards.resident_id)
        return resident.personality.aggression + feelings.resentment

    def _conclude(
        self,
        world: "SimulationWorld",
        resident: Resident,
        activity: Activity,
        definition: InteractionDefinition,
    ) -> None:
        """Apply this resident's side of the exchange: their feelings and their memory of it."""
        partner = world.residents.get(activity.partner_id or "")
        if partner is not None:
            feelings = world.relationship(resident.resident_id, partner.resident_id)
            drawn = world.bonds.attraction_rate(world, resident, partner)
            for feeling, delta in feeling_changes(definition, resident, partner, feelings, drawn).items():
                feelings.adjust(feeling, delta)
            if definition.hostile:
                feelings.last_argued = world.clock.total_minutes
            world.bonds.update_friendship(world, resident, partner)
            if definition.romance is not None and activity.intent == definition.interaction_id:
                world.bonds.resolve(world, resident, partner, definition)
            room = world.room_at(resident.tile)
            world.memories.remember(
                resident.resident_id,
                Memory(
                    text=definition.memory.replace("{other}", partner.name),
                    importance=float(definition.importance),
                    emotional_value=definition.emotional_value,
                    people=[partner.resident_id],
                    tags=list(definition.tags),
                    timestamp=world.clock.total_minutes,
                    location_id=room.room_id if room is not None else None,
                ),
            )
            resident.adjust_mood(definition.emotional_value * 8.0)
            if not definition.hostile:
                share_rumor(world, resident, partner)
                world.items.after_exchange(world, resident, partner, definition)
                world.tastes.take_to(world, resident, partner)
                world.tastes.after_exchange(world, resident, partner)
        resident.activity = None
        resident.current_action = "idle"
        if partner is None or not definition.hostile:
            return
        if definition.damage is not None:
            # This resident's side of a fight: what the other did to them.
            world.health.fight_damage(world, resident, partner, definition)
        else:
            resident.activity = world.interventions.maybe_brawl(world, resident, partner)
