"""What each resident holds about the government, and what is measured of the settlement.

A resident's leanings come from their way of being, their traits and something of their own.
What they feel about whoever leads and about the government moves with what they see, are
told or believe that those who govern have done: nobody's opinion changes because the world
knows a thing. The settlement's measures follow from all of them, each by itself.
"""

from collections.abc import Mapping
from typing import TYPE_CHECKING

from simulation.knowledge.fact import Fact
from simulation.politics.government import LEANINGS, MEASURES, GovernmentState
from simulation.politics.profile import PoliticalProfile
from simulation.residents.resident import Resident
from simulation.rng import SimulationRNG

if TYPE_CHECKING:
    from simulation.world import SimulationWorld

# What a trait may give, in its data: so much more or less of a leaning.
TRAIT_POLITICS = "politics"
# The importance of a fact at which a political reaction is as its rule says.
FULL_REACTION_IMPORTANCE = 50.0
# How much less, or more, a thing done to somebody counts by what is felt for them.
CLOSENESS = (0.5, 1.5)


def _bounded(value: float) -> float:
    return max(0.0, min(100.0, value))


class Legitimacy:
    # ----- what a resident holds -----

    def profile(self, world: "SimulationWorld", resident: Resident) -> PoliticalProfile:
        """A resident's politics, made the first time they are asked for.

        Each leaning is what their way of being and their traits make it, and something of
        their own on top that is always the same for the same settlement and resident. Whoever
        comes to a settlement that has a leader starts from what they feel for them.
        """
        profile = world.political_profiles.get(resident.resident_id)
        if profile is not None:
            return profile
        settings = world.registries.politics
        profile = PoliticalProfile(trust=settings.trust_start)
        for leaning in LEANINGS:
            value = 50.0
            for side, weight in settings.leanings.get(leaning, {}).items():
                value += weight * (getattr(resident.personality, side) - 50.0)
            for trait_id in resident.traits:
                given = (world.registries.traits.find(trait_id) or {}).get(TRAIT_POLITICS, {})
                value += float(given.get(leaning, 0.0))
            own = SimulationRNG.keyed(world.rng.seed, "politics", resident.resident_id, leaning)
            value += (own.random() - own.random()) * settings.own_spread
            setattr(profile, leaning, _bounded(round(value, 1)))
        world.political_profiles[resident.resident_id] = profile
        leader = world.residents.get(world.government.leader or "")
        if leader is not None and leader is not resident:
            profile.loyalty = self.ground(world, resident, leader)
        return profile

    def ground(self, world: "SimulationWorld", resident: Resident, leader: Resident) -> float:
        """The loyalty a resident comes back to for a leader: what they feel for them as a
        person, and how readily the leader wins people over."""
        settings = world.registries.politics
        value = settings.loyalty_base + settings.loyalty_charisma * (leader.personality.charisma - 50.0)
        feelings = world.relationships.get((resident.resident_id, leader.resident_id))
        if feelings is not None:
            value += sum(weight * getattr(feelings, name) for name, weight in settings.loyalty_from.items())
        return _bounded(value)

    def obedience(self, world: "SimulationWorld", resident: Resident) -> float:
        """How far a resident does as the government says, from 0 to 100. It says nothing of
        what they hold against it: someone may obey out of fear and resent every day of it."""
        profile = self.profile(world, resident)
        total = 0.0
        for name, weight in world.registries.politics.obedience.items():
            value = getattr(profile, name)
            if name == "fear":
                # The same fear holds a fearful person more.
                value *= 0.5 + profile.fearfulness / 100.0
            total += weight * value
        return _bounded(total)

    # ----- what a change of government or of leader does -----

    def founded(self, world: "SimulationWorld", wanted: Mapping[str, str], chosen: str) -> None:
        """A kind of government has been chosen: whoever wanted it trusts it more for that, and
        whoever wanted another, less."""
        settings = world.registries.politics
        for resident_id, kind in wanted.items():
            resident = world.residents.get(resident_id)
            if resident is not None:
                self.profile(world, resident).adjust(
                    "trust", settings.backed_trust if kind == chosen else settings.unbacked_trust
                )

    def seated(self, world: "SimulationWorld", leader: Resident, way: str, backers: set[str]) -> None:
        """Somebody has come to lead: loyalty is to the person, so everyone starts again from
        what they feel for this one, and whoever backed them from a little more."""
        settings = world.registries.politics
        for resident in world.residents.values():
            if resident is leader:
                continue
            backed = settings.backed_loyalty if resident.resident_id in backers else 0.0
            self.profile(world, resident).loyalty = _bounded(self.ground(world, resident, leader) + backed)
        self.shock(world, settings.seated.get(way, {}))
        self.measure(world)

    # ----- what is seen, told or believed of those who govern -----

    def learned(self, world: "SimulationWorld", resident: Resident, fact: Fact, credibility: float) -> None:
        """A resident has just learned a fact: if whoever did it governs, it tells on what they
        hold, by who they are and who it was done to, and through them on the settlement."""
        settings = world.registries.politics
        state = world.government
        rule = settings.reactions.get(fact.event_type)
        if rule is None or state.kind is None or not fact.subject_ids:
            return
        actor = fact.subject_ids[0]
        if actor == resident.resident_id or not (actor == state.leader or actor in state.council):
            return
        strength = credibility * fact.importance / FULL_REACTION_IMPORTANCE
        weight = strength
        victim = fact.subject_ids[1] if len(fact.subject_ids) > 1 else None
        if victim == resident.resident_id:
            weight *= rule.victim
        elif victim is not None:
            feelings = world.relationships.get((resident.resident_id, victim))
            if feelings is not None:
                closeness = 1.0 + (feelings.affection - feelings.resentment) / 200.0
                weight *= max(CLOSENESS[0], min(CLOSENESS[1], closeness))
        profile = self.profile(world, resident)
        for held, delta in rule.holds.items():
            if held == "loyalty" and actor != state.leader:
                # Loyalty is to whoever leads, and this was somebody else in the government.
                continue
            leaning = settings.sways.get(held)
            sway = 0.5 + getattr(profile, leaning) / 100.0 if leaning is not None else 1.0
            profile.adjust(held, delta * weight * sway)
        definition = settings.governments.get(state.kind)
        others = max(1, len(self._adults(world)) - 1)
        for measure, delta in rule.measures.items():
            if measure == "legitimacy" and delta < 0 and definition is not None:
                # Some governments are expected to be like that.
                delta *= 1.0 - definition.abuse_tolerance / 100.0
            self._move(state, measure, delta * strength / others)

    # ----- the settlement's measures -----

    def shock(self, world: "SimulationWorld", changes: Mapping[str, float], scale: float = 1.0) -> None:
        """Move measures by what has just happened."""
        for measure, delta in changes.items():
            self._move(world.government, measure, delta * scale)

    def measure(self, world: "SimulationWorld") -> dict[str, float]:
        """Work out what follows straight from what the residents hold: public support and fear.

        Returns what they hold on average, for whatever else is worked out from it.
        """
        state = world.government
        adults = self._adults(world)
        leader = world.residents.get(state.leader or "")
        led = [resident for resident in adults if resident is not leader] or adults
        profiles = [self.profile(world, resident) for resident in led]
        if not profiles:
            return {"loyalty": 0.0, "trust": 0.0, "fear": 0.0, "resentment": 0.0}
        held = {
            name: sum(getattr(profile, name) for profile in profiles) / len(profiles)
            for name in ("loyalty", "trust", "fear", "resentment")
        }
        if state.kind is not None:
            support = (held["loyalty"] + held["trust"]) / 2.0 if leader is not None else held["trust"]
            state.measures["public_support"] = _bounded(support)
            state.measures["fear"] = _bounded(held["fear"])
        return held

    def tick_day(self, world: "SimulationWorld") -> None:
        """A day of politics: fear and grudges fade a little, loyalty comes back towards what
        is felt for whoever leads, and the measures move to where all of it puts them."""
        state = world.government
        if state.kind is None:
            return
        settings = world.registries.politics
        leader = world.residents.get(state.leader or "")
        for resident in world.residents.values():
            profile = self.profile(world, resident)
            profile.fear *= 1.0 - settings.fear_fade * (1.5 - profile.fearfulness / 100.0)
            profile.resentment *= 1.0 - settings.resentment_fade * (1.5 - profile.revengefulness / 100.0)
            if leader is not None and resident is not leader:
                profile.loyalty += (self.ground(world, resident, leader) - profile.loyalty) * settings.loyalty_drift
        held = self.measure(world)
        measures = state.measures
        definition = settings.governments.get(state.kind)
        empty = definition is not None and definition.leader_role is not None and state.leader is None
        if empty:
            self._move(state, "legitimacy", settings.vacancy_legitimacy)
        short = max(0.0, 50.0 - measures["public_support"]) * settings.unrest_from_support
        self._move(state, "unrest", (_bounded(held["resentment"] + short) - measures["unrest"]) * settings.unrest_drift)
        steady = (measures["legitimacy"] + measures["public_support"] + 100.0 - measures["unrest"]) / 3.0
        if empty:
            steady -= settings.vacancy_stability
        self._move(state, "stability", (_bounded(steady) - measures["stability"]) * settings.stability_drift)
        measures["corruption"] *= 1.0 - settings.corruption_fade

    def _adults(self, world: "SimulationWorld") -> list[Resident]:
        return [resident for resident in world.residents.values() if world.bonds.is_adult(world, resident)]

    def _move(self, state: GovernmentState, measure: str, delta: float) -> None:
        if measure in MEASURES:
            state.measures[measure] = _bounded(state.measures.get(measure, 0.0) + delta)
