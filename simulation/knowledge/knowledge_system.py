"""How residents come to know things: by taking part, by seeing, or by being told."""

from collections.abc import Collection
from typing import TYPE_CHECKING

from simulation.events.event import DomainEvent
from simulation.knowledge.fact import (
    SOURCE_PARTICIPANT,
    SOURCE_TOLD,
    SOURCE_WITNESS,
    Belief,
    Fact,
)
from simulation.memory.memory import Memory
from simulation.residents.resident import Resident
from simulation.social.rumor import Rumor
from simulation.tastes.settings import RUMOR
from world.map import Tile
from world.visibility import line_of_sight, within_range

if TYPE_CHECKING:
    from simulation.world import SimulationWorld

DEFAULT_SIGHT_RANGE = 8
RUMOR_DECAY = 0.8
MIN_CREDIBILITY = 0.15
RUMOR_IMPORTANCE = 15
# Affection gap below which an onlooker does not take sides.
SIDE_MARGIN = 5.0
# Importance at which a reaction has its full written strength.
FULL_REACTION_IMPORTANCE = 50.0


def witnesses_of(world: "SimulationWorld", at: Tile, exclude: Collection[str] = ()) -> list[str]:
    """Residents who can see what happens at `at`: awake, close enough, nothing in the way.

    In the dark only what is near is seen, unless a fire or a lamp lights it.
    """
    perception = world.registries.event_settings.get("perception", {})
    sight_range = int(perception.get("sight_range", DEFAULT_SIGHT_RANGE))
    if world.is_dark() and not world.is_lit(at):
        sight_range = min(sight_range, int(perception.get("dark_sight_range", sight_range)))
    opaque = world.opaque()
    return [
        resident.resident_id
        for resident in world.residents.values()
        if resident.resident_id not in exclude
        and not resident.away
        and world.is_aware(resident)
        and within_range(resident.tile, at, sight_range + world.work.sight_bonus(world, resident))
        and line_of_sight(resident.tile, at, opaque)
    ]


def record_fact(
    world: "SimulationWorld",
    event: DomainEvent,
    text: str,
    subjects: Collection[str] | None = None,
    expires_at: int | None = None,
) -> Fact:
    """Record an event as a fact. Its participants and witnesses learn it at first hand.

    `subjects` are the people the fact is about, actor first. It defaults to the participants,
    but can include someone who was not there, such as the owner of something stolen.
    """
    fact = Fact(
        fact_id=world.knowledge.new_fact_id(),
        event_type=event.event_type,
        text=text,
        subject_ids=list(subjects or event.participants),
        importance=event.importance,
        timestamp=event.timestamp,
        location_id=event.location_id,
        expires_at=expires_at,
    )
    world.knowledge.add_fact(fact)
    for resident_id in event.participants:
        if resident_id in world.residents:
            learn(world, world.residents[resident_id], fact, 1.0, SOURCE_PARTICIPANT)
    for resident_id in event.witnesses:
        if resident_id in world.residents:
            learn(world, world.residents[resident_id], fact, 1.0, SOURCE_WITNESS)
    return fact


def learn(
    world: "SimulationWorld",
    resident: Resident,
    fact: Fact,
    credibility: float,
    source: str,
    told_by: str | None = None,
) -> bool:
    """Give a resident a belief about a fact. Returns True if it was news to them.

    Only news causes a reaction; hearing the same thing again just firms up the belief.
    """
    if credibility < MIN_CREDIBILITY:
        return False
    known = world.knowledge.belief(resident.resident_id, fact.fact_id)
    if known is not None:
        known.credibility = max(known.credibility, credibility)
        return False
    world.knowledge.set_belief(
        resident.resident_id,
        Belief(fact.fact_id, credibility, source, world.clock.total_minutes, told_by),
    )
    if source == SOURCE_PARTICIPANT:
        # Whoever a thing was done to by those who govern needs nobody to tell them.
        world.politics.learned(world, resident, fact, credibility)
        return True
    react(world, resident, fact, credibility)
    # What those who govern are known to have done tells on what is made of the government.
    world.politics.learned(world, resident, fact, credibility)
    teller = world.residents.get(told_by) if told_by else None
    text = f"{teller.name} me contó que {fact.text}." if teller is not None else f"Vi que {fact.text}."
    world.memories.remember(
        resident.resident_id,
        Memory(
            text=text,
            importance=fact.importance * credibility,
            emotional_value=-0.2,
            people=[*fact.subject_ids, *([told_by] if told_by else [])],
            tags=["heard" if source == SOURCE_TOLD else "witnessed"],
            timestamp=world.clock.total_minutes,
            location_id=fact.location_id if source == SOURCE_WITNESS else None,
        ),
    )
    return True


def react(world: "SimulationWorld", resident: Resident, fact: Fact, credibility: float) -> None:
    """Change how a resident feels about the people in a fact they have just learned.

    They blame whichever of the people involved they like less; with no favourite, both.
    """
    rule = world.registries.event_settings.get("reactions", {}).get(fact.event_type)
    if rule is None:
        return
    strength = credibility * fact.importance / FULL_REACTION_IMPORTANCE
    actor = fact.subject_ids[0] if fact.subject_ids else None
    if resident.resident_id in fact.subject_ids:
        # Someone the fact is about only reacts if it was done to them behind their back.
        if resident.resident_id != actor and "victim" in rule and actor in world.residents:
            resident.needs.apply(
                {need: delta * credibility for need, delta in rule.get("victim_needs", {}).items()}
            )
            # With a rival in it, the one who did the wrong is their own partner, not whoever acted.
            others = [subject for subject in fact.subject_ids[:2] if subject != resident.resident_id]
            wronged_by = resident.couple_with if "rival" in rule and resident.couple_with in others else actor
            feelings = world.relationship(resident.resident_id, wronged_by)
            for feeling, base in rule["victim"].items():
                feelings.adjust(feeling, float(base) * strength)
            for rival in (subject for subject in others if subject != wronged_by and "rival" in rule):
                if rival in world.residents:
                    for feeling, base in rule["rival"].items():
                        world.relationship(resident.resident_id, rival).adjust(feeling, float(base) * strength)
        return
    resident.needs.apply({need: delta * credibility for need, delta in rule.get("needs", {}).items()})
    mourn = rule.get("mourn")
    if mourn and fact.subject_ids:
        # The fact's last subject is who was lost; the fonder of them, the harder it hits.
        bond = world.relationships.get((resident.resident_id, fact.subject_ids[-1]))
        fondness = max(0.0, bond.affection) if bond is not None else 0.0
        grief = float(mourn.get("stress", 0.0)) + float(mourn.get("per_affection", 0.0)) * fondness
        resident.needs.apply({"stress": grief * credibility})
    # Only the first subjects did anything, where a rule says so: the rest had it done to them.
    doers = fact.subject_ids[: int(rule.get("blame_subjects", len(fact.subject_ids)))]
    involved = [subject for subject in doers if subject in world.residents]
    blamed = {subject: 1.0 for subject in involved}
    if rule.get("blame_target") == "actor":
        blamed = {actor: 1.0} if actor in world.residents else {}
    elif rule.get("blame_target") == "all":
        # Nobody takes a side: everyone in it is held to it in full.
        pass
    elif len(involved) == 2:
        first, second = involved
        lean = (
            world.relationship(resident.resident_id, first).affection
            - world.relationship(resident.resident_id, second).affection
        )
        if lean > SIDE_MARGIN:
            blamed = {second: 1.0}
        elif lean < -SIDE_MARGIN:
            blamed = {first: 1.0}
        else:
            blamed = {first: 0.5, second: 0.5}
    for subject, share in blamed.items():
        feelings = world.relationship(resident.resident_id, subject)
        for feeling, base in rule.get("blame", {}).items():
            feelings.adjust(feeling, float(base) * share * strength)


def share_rumor(world: "SimulationWorld", teller: Resident, listener: Resident) -> Rumor | None:
    """Maybe have `teller` pass on the most striking thing they know that `listener` does not."""
    reactions = world.registries.event_settings.get("reactions", {})
    facts = world.knowledge.facts

    def keeps_quiet(fact: Fact) -> bool:
        """Nobody volunteers their own misdeeds, except to a friend close enough to confide in,
        and never to anyone else the thing is about."""
        keepers = int(reactions.get(fact.event_type, {}).get("secret", 0))
        if teller.resident_id not in fact.subject_ids[:keepers]:
            return False
        return listener.resident_id in fact.subject_ids or not world.bonds.confides_in(world, teller, listener)

    def stale(fact: Fact) -> bool:
        """Word of something that was to come is not news once its hour has passed."""
        return fact.expires_at is not None and world.clock.total_minutes >= fact.expires_at

    news = [
        belief
        for belief in world.knowledge.beliefs_of(teller.resident_id)
        if not world.knowledge.knows(listener.resident_id, belief.fact_id)
        and not keeps_quiet(facts[belief.fact_id])
        and not stale(facts[belief.fact_id])
    ]
    if not news:
        return None
    if world.rng.random() >= 0.3 + teller.personality.sociability / 200.0:
        return None
    belief = max(
        news,
        key=lambda b: (facts[b.fact_id].importance * b.credibility, facts[b.fact_id].timestamp, b.fact_id),
    )
    fact = facts[belief.fact_id]
    trust = world.relationship(listener.resident_id, teller.resident_id).trust
    credibility = belief.credibility * RUMOR_DECAY * max(0.3, min(1.0, 0.75 + trust / 200.0))
    rumor = Rumor(fact.text, teller.resident_id, list(fact.subject_ids), credibility, fact.fact_id)
    if learn(world, listener, fact, credibility, SOURCE_TOLD, told_by=teller.resident_id):
        room = world.room_at(teller.tile)
        world.emit_event(
            DomainEvent(
                event_type="rumor_told",
                importance=RUMOR_IMPORTANCE,
                text=f"{teller.name} le cuenta a {listener.name} que {fact.text}",
                participants=[teller.resident_id, listener.resident_id],
                location_id=room.room_id if room is not None else None,
            )
        )
        # Whoever is fond of gossip is the fonder of whoever brings it, and the other way about.
        world.tastes.take_to(world, listener, teller, RUMOR)
    return rumor
