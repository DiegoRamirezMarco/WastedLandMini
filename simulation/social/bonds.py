"""Friendship, attraction and couples: what grows between residents over time, and what ends it.

Everything here is between adults, and nothing happens to anyone who does not want it: a couple
forms only if the one asked feels the same, and two residents only go off alone together if both
are drawn to each other. What they do alone is told as an event and no more than that.
"""

import zlib
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from simulation.ai.utility_ai import DISTANCE_COST, ScoredAction
from simulation.events.event import DomainEvent
from simulation.knowledge.fact import SOURCE_WITNESS, Fact
from simulation.knowledge.knowledge_system import learn, witnesses_of
from simulation.memory.memory import Memory
from simulation.residents.resident import Resident
from simulation.social.interaction import InteractionDefinition
from simulation.social.relationship import Relationship
from world.pathfinding import manhattan

if TYPE_CHECKING:
    from simulation.world import SimulationWorld

# What an exchange can be to a romance, as named in `data/social.json`.
CONFESSION = "confession"
TRYST = "tryst"
BREAKUP = "breakup"
# Action of a resident on their way to be alone with someone.
TRYST_ACTION = "tryst"
TRYST_APPEAL = 0.7
AFFAIR_EVENT = "affair"
# Extra importance of two residents going off alone when it is behind someone's back.
AFFAIR_IMPORTANCE = 15
FRIENDSHIP_IMPORTANCE = 25
COUPLE_IMPORTANCE = 60
REJECTION_IMPORTANCE = 45
BREAKUP_IMPORTANCE = 65
# Nobody thinks of romance, or of ending one, with a bodily need this high.
MAX_BODILY_NEED = 70.0


@dataclass(frozen=True)
class FriendshipTier:
    """A degree of friendship, and what one resident must feel for another to hold them in it."""

    tier_id: str
    name: str
    affection: float
    trust: float


@dataclass(frozen=True)
class BondSettings:
    """The settlement's rules about friendship and romance."""

    adult_age: int = 18
    # Degrees of friendship, the least first.
    friendship: tuple[FriendshipTier, ...] = ()
    # Attraction and affection from which a resident may say what they feel.
    confess_attraction: float = 45.0
    confess_affection: float = 35.0
    # What the one told must feel in turn to say yes.
    accept_attraction: float = 35.0
    accept_affection: float = 25.0
    # Attraction from which two residents go off alone, and the hours they do it in.
    tryst_attraction: float = 40.0
    tryst_hours: tuple[int, int] = (21, 6)
    tryst_cooldown_minutes: int = 1440
    # Attraction it takes to go behind a partner's back, and the empathy that stops it.
    affair_attraction: float = 60.0
    affair_max_empathy: float = 60.0
    # How much slower attraction to anyone else grows in someone who has a partner.
    taken_attraction_factor: float = 0.3
    # Resentment of a partner from which a resident thinks of leaving them.
    breakup_resentment: float = 45.0


def bond_settings_from_data(data: dict[str, Any]) -> BondSettings:
    defaults = BondSettings()
    tiers = tuple(
        FriendshipTier(
            str(tier["id"]), str(tier.get("name", tier["id"])), float(tier["affection"]), float(tier.get("trust", 0.0))
        )
        for tier in data.get("friendship", [])
    )
    if list(tiers) != sorted(tiers, key=lambda tier: tier.affection):
        raise ValueError("Friendship tiers must be listed from the least to the closest")
    romance = data.get("romance", {})
    hours = romance.get("tryst_hours", defaults.tryst_hours)
    settings = BondSettings(
        adult_age=int(data.get("adult_age", defaults.adult_age)),
        friendship=tiers,
        confess_attraction=float(romance.get("confess_attraction", defaults.confess_attraction)),
        confess_affection=float(romance.get("confess_affection", defaults.confess_affection)),
        accept_attraction=float(romance.get("accept_attraction", defaults.accept_attraction)),
        accept_affection=float(romance.get("accept_affection", defaults.accept_affection)),
        tryst_attraction=float(romance.get("tryst_attraction", defaults.tryst_attraction)),
        tryst_hours=(int(hours[0]), int(hours[1])),
        tryst_cooldown_minutes=int(romance.get("tryst_cooldown_minutes", defaults.tryst_cooldown_minutes)),
        affair_attraction=float(romance.get("affair_attraction", defaults.affair_attraction)),
        affair_max_empathy=float(romance.get("affair_max_empathy", defaults.affair_max_empathy)),
        taken_attraction_factor=float(romance.get("taken_attraction_factor", defaults.taken_attraction_factor)),
        breakup_resentment=float(romance.get("breakup_resentment", defaults.breakup_resentment)),
    )
    if settings.adult_age < 18:
        raise ValueError("Romance is for adults: adult_age cannot be under 18")
    return settings


def spark(source_id: str, target_id: str) -> float:
    """How much one resident is drawn to another by nature, from 0 to 1.

    It is fixed by who the two are, is not the same in both directions, and for half of all
    pairs it is nothing at all.
    """
    value = zlib.crc32(f"{source_id}>{target_id}".encode()) / 0xFFFFFFFF
    return max(0.0, value * 2.0 - 1.0)


def _in_hours(hour: int, window: tuple[int, int]) -> bool:
    start, end = window
    return start <= hour < end if start <= end else hour >= start or hour < end


class BondSystem:
    def settings(self, world: "SimulationWorld") -> BondSettings:
        return world.registries.bonds

    def is_adult(self, world: "SimulationWorld", resident: Resident) -> bool:
        return resident.age >= self.settings(world).adult_age

    def are_couple(self, a: Resident, b: Resident) -> bool:
        return a.couple_with == b.resident_id and b.couple_with == a.resident_id

    # ----- friendship -----

    def tier(self, world: "SimulationWorld", feelings: Relationship) -> FriendshipTier | None:
        """The closest degree of friendship these feelings amount to, if any."""
        held = None
        for tier in self.settings(world).friendship:
            if feelings.affection >= tier.affection and feelings.trust >= tier.trust:
                held = tier
        return held

    def confides_in(self, world: "SimulationWorld", resident: Resident, other: Resident) -> bool:
        """Whether `resident` holds `other` close enough to tell them a secret."""
        tiers = self.settings(world).friendship
        feelings = world.relationships.get((resident.resident_id, other.resident_id))
        return bool(tiers) and feelings is not None and self.tier(world, feelings) == tiers[-1]

    def update_friendship(self, world: "SimulationWorld", resident: Resident, other: Resident) -> None:
        """Say so when what `resident` feels for `other` has grown into friendship, or out of it."""
        feelings = world.relationship(resident.resident_id, other.resident_id)
        tiers = self.settings(world).friendship
        tier = self.tier(world, feelings)
        held = tier.tier_id if tier is not None else ""
        if held == feelings.bond:
            return
        order = ["", *(each.tier_id for each in tiers)]
        grew = order.index(held) > (order.index(feelings.bond) if feelings.bond in order else 0)
        previous = next((each for each in tiers if each.tier_id == feelings.bond), None)
        feelings.bond = held
        if grew and tier is not None:
            text = f"{resident.name} siente ya por {other.name} una {tier.name}"
        elif previous is not None:
            text = f"{resident.name} ya no siente por {other.name} una {previous.name}"
        else:
            return
        world.emit_event(
            DomainEvent("friendship_changed", FRIENDSHIP_IMPORTANCE, text, [resident.resident_id, other.resident_id])
        )

    # ----- attraction -----

    def attraction_rate(self, world: "SimulationWorld", resident: Resident, other: Resident) -> float:
        """How fast a friendly exchange draws `resident` towards `other`, as a multiple of its base.

        It takes a spark, or an attraction that is there already, and both being adults. Someone
        who has a partner is slower to be drawn to anyone else.
        """
        if not (self.is_adult(world, resident) and self.is_adult(world, other)):
            return 0.0
        feelings = world.relationships.get((resident.resident_id, other.resident_id))
        felt = feelings.attraction / 100.0 if feelings is not None else 0.0
        rate = max(spark(resident.resident_id, other.resident_id), felt)
        taken = resident.couple_with is not None and resident.couple_with != other.resident_id
        return rate * (self.settings(world).taken_attraction_factor if taken else 1.0)

    # ----- what a resident may be making up their mind about -----

    def confession_target(self, world: "SimulationWorld", resident: Resident) -> Resident | None:
        """Whoever a single resident is drawn to enough to think of telling them, if anyone."""
        settings = self.settings(world)
        if resident.couple_with is not None or not self.is_adult(world, resident):
            return None
        best: tuple[float, Resident] | None = None
        for other in world.residents.values():
            feelings = world.relationships.get((resident.resident_id, other.resident_id))
            if other is resident or feelings is None or other.couple_with is not None:
                continue
            if not self.is_adult(world, other):
                continue
            if feelings.attraction < settings.confess_attraction or feelings.affection < settings.confess_affection:
                continue
            if best is None or feelings.attraction > best[0]:
                best = (feelings.attraction, other)
        return best[1] if best is not None else None

    def soured_partner(self, world: "SimulationWorld", resident: Resident) -> Resident | None:
        """A resident's partner, if things between them have got bad enough to think of leaving."""
        partner = world.residents.get(resident.couple_with or "")
        if partner is None:
            return None
        feelings = world.relationship(resident.resident_id, partner.resident_id)
        return partner if feelings.resentment >= self.settings(world).breakup_resentment else None

    # ----- going off alone together -----

    def candidates(self, world: "SimulationWorld", resident: Resident) -> list[ScoredAction]:
        """Score seeking someone out to be alone with them, at the hours for it."""
        settings = self.settings(world)
        if not self.is_adult(world, resident) or not _in_hours(world.clock.hour, settings.tryst_hours):
            return []
        if max(resident.needs.hunger, resident.needs.tiredness) > MAX_BODILY_NEED:
            return []
        scored: list[ScoredAction] = []
        for other in world.residents.values():
            feelings = world.relationships.get((resident.resident_id, other.resident_id))
            if other is resident or other.away or feelings is None:
                continue
            if not self._would_seek(world, resident, other, feelings):
                continue
            if other.activity is not None and other.activity.partner_id is not None:
                continue
            score = TRYST_APPEAL * feelings.attraction / 100.0 - DISTANCE_COST * manhattan(resident.tile, other.tile)
            scored.append(ScoredAction(TRYST_ACTION, score, partner_id=other.resident_id))
        return scored

    def _would_seek(
        self, world: "SimulationWorld", resident: Resident, other: Resident, feelings: Relationship
    ) -> bool:
        """Whether `resident` would go looking for `other` tonight: their partner, or someone behind a partner's back."""
        settings = self.settings(world)
        if not self.is_adult(world, other):
            return False
        last = feelings.last_together
        if last is not None and world.clock.total_minutes - last < settings.tryst_cooldown_minutes:
            return False
        if self.are_couple(resident, other):
            return feelings.attraction >= settings.tryst_attraction
        # Anyone else only when one of the two has a partner: singles say what they feel first.
        if resident.couple_with is None and other.couple_with is None:
            return False
        if resident.couple_with is not None and resident.personality.empathy >= settings.affair_max_empathy:
            return False
        return feelings.attraction >= settings.affair_attraction

    def may_begin(
        self, world: "SimulationWorld", resident: Resident, other: Resident, definition: InteractionDefinition
    ) -> bool:
        """Whether an exchange that is part of a romance can start, now that `resident` has reached `other`.

        Going off alone takes the other wanting to as well, and nobody about to see them leave.
        """
        if definition.romance != TRYST:
            return True
        now = world.clock.total_minutes
        mine = world.relationship(resident.resident_id, other.resident_id)
        theirs = world.relationship(other.resident_id, resident.resident_id)
        willing = (
            self.is_adult(world, resident)
            and self.is_adult(world, other)
            and theirs.attraction >= self.settings(world).tryst_attraction
            and max(other.needs.hunger, other.needs.tiredness) <= MAX_BODILY_NEED
        )
        if not willing:
            # They take no for an answer, and do not ask again tonight.
            mine.last_together = now
            return False
        if witnesses_of(world, resident.tile, exclude=[resident.resident_id, other.resident_id]):
            return False
        mine.last_together = theirs.last_together = now
        return True

    def betrayed_by(self, world: "SimulationWorld", a: Resident, b: Resident) -> list[str]:
        """Partners of either of two residents who are not the other one: who it is behind the back of."""
        return [
            partner_id
            for one, other in ((a, b), (b, a))
            if (partner_id := one.couple_with) is not None
            and partner_id != other.resident_id
            and partner_id in world.residents
        ]

    def seen(self, world: "SimulationWorld", resident: Resident, other: Resident) -> None:
        """Let whoever comes across two residents alone together learn of it."""
        fact = self._latest_fact(world, resident, other)
        if fact is None:
            return
        for witness_id in witnesses_of(world, resident.tile, exclude=[resident.resident_id, other.resident_id]):
            learn(world, world.residents[witness_id], fact, 1.0, SOURCE_WITNESS)

    def _latest_fact(self, world: "SimulationWorld", a: Resident, b: Resident) -> Fact | None:
        pair = {a.resident_id, b.resident_id}
        return next(
            (
                fact
                for fact in reversed(list(world.knowledge.facts.values()))
                if fact.event_type in (AFFAIR_EVENT, f"{TRYST}_started") and set(fact.subject_ids[:2]) == pair
            ),
            None,
        )

    # ----- how a confession or a breakup ends -----

    def resolve(
        self, world: "SimulationWorld", initiator: Resident, other: Resident, definition: InteractionDefinition
    ) -> None:
        """Settle what the one who started a confession or a breakup came for."""
        if definition.romance == CONFESSION:
            self._answer(world, initiator, other)
        elif definition.romance == BREAKUP and self.are_couple(initiator, other):
            self.part(world, initiator, other)
            self._remember(world, initiator, other, f"Rompí con {other.name}.", -0.5)
            self._remember(world, other, initiator, f"{initiator.name} rompió conmigo.", -0.9)
            other.needs.apply({"stress": 20.0})
            initiator.needs.apply({"stress": 8.0})
            self._announce(
                world, "couple_broke_up", BREAKUP_IMPORTANCE, initiator, other,
                f"{initiator.name} y {other.name} ya no están juntos",
                f"{initiator.name} rompió con {other.name}",
            )

    def part(self, world: "SimulationWorld", a: Resident, b: Resident) -> None:
        """End a couple. What they feel for each other is theirs to get over."""
        a.couple_with = b.couple_with = None

    def _answer(self, world: "SimulationWorld", asker: Resident, asked: Resident) -> None:
        settings = self.settings(world)
        theirs = world.relationship(asked.resident_id, asker.resident_id)
        mine = world.relationship(asker.resident_id, asked.resident_id)
        free = asker.couple_with is None and asked.couple_with is None
        adults = self.is_adult(world, asker) and self.is_adult(world, asked)
        feels_the_same = (
            theirs.attraction >= settings.accept_attraction and theirs.affection >= settings.accept_affection
        )
        if free and adults and feels_the_same:
            asker.couple_with, asked.couple_with = asked.resident_id, asker.resident_id
            for one, other in ((asker, asked), (asked, asker)):
                one.needs.apply({"stress": -15.0})
                self._remember(world, one, other, f"{other.name} y yo estamos juntos.", 0.9)
            self._announce(
                world, "couple_formed", COUPLE_IMPORTANCE, asker, asked,
                f"{asker.name} y {asked.name} están juntos",
                f"{asker.name} y {asked.name} están juntos",
            )
            return
        asker.needs.apply({"stress": 15.0})
        mine.adjust("attraction", -10.0)
        mine.adjust("affection", -5.0)
        theirs.adjust("affection", -2.0)
        self._remember(world, asker, asked, f"Le dije a {asked.name} lo que sentía y no siente lo mismo.", -0.8)
        self._remember(world, asked, asker, f"{asker.name} me dijo lo que sentía. No siento lo mismo.", -0.2)
        world.emit_event(
            DomainEvent(
                "confession_rejected",
                REJECTION_IMPORTANCE,
                f"{asked.name} no siente lo mismo por {asker.name}",
                [asker.resident_id, asked.resident_id],
            ),
            at=asker.tile,
        )

    def _announce(
        self, world: "SimulationWorld", event_type: str, importance: int, a: Resident, b: Resident, text: str, fact: str
    ) -> None:
        room = world.room_at(a.tile)
        world.emit_event(
            DomainEvent(
                event_type,
                importance,
                text,
                [a.resident_id, b.resident_id],
                location_id=room.room_id if room is not None else None,
            ),
            at=a.tile,
            fact_text=fact,
        )

    def _remember(
        self, world: "SimulationWorld", resident: Resident, other: Resident, text: str, emotional_value: float
    ) -> None:
        world.memories.remember(
            resident.resident_id,
            Memory(text, 60.0, emotional_value, [other.resident_id], ["romance"], world.clock.total_minutes),
        )
