"""Chooses what a resident does next by scoring the things they could do."""

from dataclasses import dataclass, field, replace
from typing import TYPE_CHECKING

from simulation.ai.crowd import spots_taken
from simulation.ai.navigation import adjacent_spots, seat_at
from simulation.ai.utility_ai import DISTANCE_COST, ScoredAction, need_urgency, ranked
from simulation.economy.merchant import VISIT_ACTION
from simulation.family.family_system import SLEEP_ROUGH_ACTION
from simulation.items.item_system import ITEM_ACTIONS, ItemSystem
from simulation.residents.activity import (
    ATTEND_ACTION,
    PROTEST_ACTION,
    RETIRE_ACTION,
    SHELTER_ACTION,
    WANDER_ACTION,
    Activity,
)
from simulation.residents.manner import SIT
from simulation.residents.needs import NEED_NAMES
from simulation.residents.resident import Resident
from simulation.social.bonds import TRYST, TRYST_ACTION
from simulation.social.social_system import SocialSystem
from simulation.work.construction import BUILD_ACTIONS
from simulation.work.work_system import WORK_ACTIONS
from world.interactable import Interactable, UseDefinition
from world.map import Tile
from world.pathfinding import find_path, manhattan

if TYPE_CHECKING:
    from simulation.world import SimulationWorld

WANDER_SCORE = 0.1
WANDER_RANGE = 12
WANDER_ATTEMPTS = 8
WANDER_MINUTES = (5, 30)
SCORE_NOISE = 0.05
# What a thing offers beside what it is for appeals a little less than what a thing is for,
# and than a thing of their own that is to hand (S60).
EXTRA_USE_APPEAL = 0.75
PREFERRED_HOURS_BONUS = 2.0
OFF_HOURS_PENALTY = 0.2
# Need level from which the off-hours penalty starts to fade.
DESPERATE_FROM = 70.0
# Total need relief of an ordinary meal, against which other food is judged.
PLAIN_MEAL_RELIEF = 25.0
# Hunger above which going to bed starts to lose its appeal.
SUPPER_HUNGER = 40.0
# Hunger beyond that at which bed has no appeal left at all.
SUPPER_RANGE = 30.0
# Getting under a roof in bad weather comes before anything that is not work or a real need.
SHELTER_SCORE = 0.5
SHELTER_MINUTES = 90
# Getting indoors when a law they keep says so comes before anything that can wait.
RETIRE_SCORE = 0.45
RETIRE_MINUTES = 30


def in_hours(hour: int, window: tuple[int, int]) -> bool:
    """True if `hour` is inside `window`, which may wrap past midnight (e.g. 22 to 7)."""
    start, end = window
    return start <= hour < end if start <= end else hour >= start or hour < end


@dataclass
class RoutineSystem:
    social: SocialSystem = field(default_factory=SocialSystem)
    items: ItemSystem = field(default_factory=ItemSystem)

    def candidates(self, world: "SimulationWorld", resident: Resident) -> list[ScoredAction]:
        """Score everything the resident could do next: use an object, talk, handle an item, or wander."""
        scored: list[ScoredAction] = []
        bed_to_be_had = False
        # What the laws they keep ask of them right now: to be indoors, to keep quiet.
        laws = world.politics.laws
        governed = bool(world.government.laws)
        indoors = governed and laws.indoors(world, resident)
        hushed = governed and laws.hushed(world, resident)
        for placed in world.interactables.values():
            # Everything there is to do with it, each for what it is worth to them now (S60).
            definition = world.definition_of(placed)
            for use in definition.uses:
                if world.users_of(placed.object_id) >= use.capacity:
                    continue
                if not world.work.open_to(world, resident, use) or world.upgrades.in_hand(world, placed.object_id):
                    # Nor is anything used while it is being made better (S54).
                    continue
                # What stands in somebody's house is theirs to use, and whoever they would have in.
                # Anybody else goes in for it only when they have to.
                housing = world.housing
                if not housing.may_use(world, resident, placed, use) and not housing.pressed(world, resident, placed, use):
                    continue
                bed_to_be_had = bed_to_be_had or (use.unaware and use.per_minute.get("tiredness", 0.0) < 0)
                if governed and laws.bars(world, resident, placed, use, indoors):
                    continue
                score = self._score_use(world, resident, placed, use)
                if score is not None:
                    pull = laws.pull(world, resident, placed) if governed else 0.0
                    if use is definition.use:
                        grain = self._noise(world)
                    else:
                        # What a thing offers beside what it is for appeals a little less, and is
                        # weighed for that and no more: the grain of chance the rest is weighed
                        # with is thrown as it always was, so that a settlement goes as it went
                        # until somebody takes one up.
                        score, grain = score * EXTRA_USE_APPEAL, 0.0
                    scored.append(ScoredAction(use.action, score + pull + grain, placed.object_id))
        for talk in () if hushed else self.social.candidates(world, resident):
            if indoors and not laws.under_same_roof(world, resident, world.residents[talk.partner_id].tile):
                continue
            scored.append(ScoredAction(talk.name, talk.score + self._noise(world), partner_id=talk.partner_id))
        for tryst in () if hushed or indoors else world.bonds.candidates(world, resident):
            scored.append(ScoredAction(tryst.name, tryst.score + self._noise(world), partner_id=tryst.partner_id))
        for handle in self.items.candidates(world, resident):
            scored.append(
                ScoredAction(handle.name, handle.score + self._noise(world), handle.target_id, item_id=handle.item_id)
            )
        work = world.work.candidate(world, resident)
        if work is not None:
            scored.append(ScoredAction(work.name, work.score + self._noise(world), work.target_id))
        rough = world.family.rough_candidate(world, resident, bed_to_be_had)
        if rough is not None:
            scored.append(ScoredAction(rough.name, rough.score + self._noise(world)))
        visit = world.merchants.candidate(world, resident)
        if visit is not None:
            scored.append(ScoredAction(visit.name, visit.score + self._noise(world)))
        build = None if indoors else world.construction.candidate(world, resident, busy=work is not None)
        if build is not None:
            scored.append(ScoredAction(build.name, build.score + self._noise(world), build.target_id))
        if indoors and not world.under_roof(resident.tile):
            scored.append(ScoredAction(RETIRE_ACTION, RETIRE_SCORE + self._noise(world)))
        attend = laws.attendance(world, resident) if governed else None
        if attend is not None:
            scored.append(ScoredAction(attend.name, attend.score + self._noise(world), attend.target_id))
        protest = world.politics.protests.candidate(world, resident) if governed else None
        if protest is not None:
            scored.append(ScoredAction(protest.name, protest.score + self._noise(world), item_id=protest.item_id))
        if world.happenings.is_stormy(world) and not world.under_roof(resident.tile):
            # The worse their nerves, the sooner they get out of it.
            wish = SHELTER_SCORE + 0.5 * need_urgency(resident, "stress")
            scored.append(ScoredAction(SHELTER_ACTION, wish + self._noise(world)))
        scored.append(ScoredAction(WANDER_ACTION, WANDER_SCORE + self._noise(world)))
        return scored

    def can_relieve(self, world: "SimulationWorld", resident: Resident, need: str) -> bool:
        """Whether there is anything a resident could do about a need: something they carry, or somewhere to go."""
        for item in resident.inventory.items:
            definition = world.registries.items.resolve(item.definition_id)
            if not item.broken and self.items.use_effects(world, resident, definition).get(need, 0.0) < 0:
                return True
        return any(
            self._offers(world, resident, placed, use, need)
            for placed in world.interactables.values()
            for use in world.definition_of(placed).uses
        )

    def relieves(self, world: "SimulationWorld", resident: Resident, placed: Interactable, need: str) -> bool:
        """Whether using an object would lower a need of a resident's, as things stand."""
        use = world.definition_of(placed).use
        return use is not None and self._offers(world, resident, placed, use, need)

    def use(
        self, world: "SimulationWorld", resident: Resident, placed: Interactable, action: str | None = None
    ) -> Activity | None:
        """The walk to an object and the use of it: what it is mainly for, or the one of its
        uses that goes by `action`. None if there is no getting to it."""
        return self._use(world, resident, placed, action)

    def stroll(self, world: "SimulationWorld", resident: Resident) -> list[Tile]:
        """The way to somewhere near, picked at random, for whoever is out for a walk."""
        return self._wander(world, resident).path

    def open_for(
        self, world: "SimulationWorld", resident: Resident, placed: Interactable, action: str | None = None
    ) -> bool:
        """Whether a resident could use an object as things stand: open, theirs to use, within
        their means and, where it serves something, not empty. For what it is mainly for, or
        for the one of its uses that goes by `action`."""
        use = world.definition_of(placed).use_for(action)
        if use is None or not world.work.open_to(world, resident, use):
            return False
        if world.upgrades.in_hand(world, placed.object_id):
            return False
        if not world.housing.may_use(world, resident, placed, use) and not world.housing.pressed(world, resident, placed, use):
            return False
        if not world.trade.can_afford(world, resident, use, placed.object_id):
            return False
        return use.consumes is None or self.items.best_food(world, resident, placed.object_id, use.consumes) is not None

    def _offers(
        self, world: "SimulationWorld", resident: Resident, placed: Interactable, use: UseDefinition, need: str
    ) -> bool:
        """Whether a use would lower a need, as things stand: open, within their means and not empty."""
        if not world.work.open_to(world, resident, use):
            return False
        if not world.housing.may_use(world, resident, placed, use) and not world.housing.pressed(world, resident, placed, use):
            return False
        if not world.trade.can_afford(world, resident, use, placed.object_id):
            return False
        if use.per_minute.get(need, 0.0) < 0:
            return True
        item_id = use.item_id
        if use.consumes is not None:
            food = self.items.best_food(world, resident, placed.object_id, use.consumes)
            if food is None:
                return False
            item_id = food.definition_id
        if item_id is None:
            return False
        item = world.registries.items.resolve(item_id)
        return self.items.use_effects(world, resident, item).get(need, 0.0) < 0

    def plan(self, world: "SimulationWorld", resident: Resident) -> Activity:
        """Return the best activity the resident can actually reach."""
        for candidate in ranked(self.candidates(world, resident)):
            if candidate.name == TRYST_ACTION:
                activity = self.social.pursue(world, resident, world.residents[candidate.partner_id], TRYST)
            elif candidate.partner_id is not None:
                activity = self.social.approach(world, resident, world.residents[candidate.partner_id])
            elif candidate.name in ITEM_ACTIONS:
                activity = self.items.plan(world, resident, candidate)
            elif candidate.name in WORK_ACTIONS:
                activity = world.work.plan(world, resident, candidate)
            elif candidate.name in BUILD_ACTIONS:
                activity = world.construction.plan(world, resident, candidate)
            elif candidate.name == SHELTER_ACTION:
                activity = self._shelter(world, resident)
            elif candidate.name == RETIRE_ACTION:
                roof = self._shelter(world, resident)
                activity = replace(roof, action=RETIRE_ACTION, minutes_left=RETIRE_MINUTES) if roof is not None else None
            elif candidate.name == ATTEND_ACTION:
                activity = world.politics.laws.plan_attend(world, resident, candidate)
            elif candidate.name == PROTEST_ACTION:
                activity = world.politics.protests.plan(world, resident, candidate)
            elif candidate.name == VISIT_ACTION:
                activity = world.merchants.plan(world, resident)
            elif candidate.name == SLEEP_ROUGH_ACTION:
                return world.family.plan_rough(world, resident)
            elif candidate.target_id is None:
                return self._wander(world, resident)
            else:
                activity = self._use(world, resident, world.interactables[candidate.target_id], candidate.name)
            if activity is not None:
                return activity
        return self._wander(world, resident)

    def _noise(self, world: "SimulationWorld") -> float:
        return world.rng.random() * SCORE_NOISE

    def _score_use(
        self, world: "SimulationWorld", resident: Resident, placed: Interactable, use: UseDefinition
    ) -> float | None:
        """How much the resident wants this use right now. None if it has nothing to offer them."""
        distance_cost = DISTANCE_COST * manhattan(resident.tile, (placed.x, placed.y))
        if not world.trade.can_afford(world, resident, use, placed.object_id):
            return None
        if use.sells or use.repairs > 0:
            want = (
                world.trade.shop_score(world, resident, placed.object_id)
                if use.sells
                else world.trade.repair_score(world, resident, use)
            )
            return want - distance_cost if want is not None else None
        if use.heals:
            care = max(world.health.care_score(resident), world.substances.care_wish(world, resident, use))
            return care - DISTANCE_COST * manhattan(resident.tile, (placed.x, placed.y)) if care > 0 else None
        relief = dict(use.per_minute)
        item_id = use.item_id
        if use.consumes is not None:
            food = self.items.best_food(world, resident, placed.object_id, use.consumes)
            if food is None:
                return None
            item_id = food.definition_id
        quality = 1.0
        wish = 0.0
        if item_id is not None:
            item = world.registries.items.resolve(item_id)
            wish = world.substances.wish(world, resident, item)
            if wish is None:
                return None
            effects = self.items.use_effects(world, resident, item)
            for need, delta in effects.items():
                relief[need] = relief.get(need, 0.0) + delta
            if use.consumes is not None:
                # A proper meal is worth a longer walk than a cold tin.
                strength = sum(-delta for delta in effects.values() if delta < 0) / PLAIN_MEAL_RELIEF
                quality = 0.75 + 0.25 * min(2.0, strength)
        score = sum(
            need_urgency(resident, need)
            for need, delta in relief.items()
            if delta < 0 and need in NEED_NAMES
        )
        score = score * quality + wish
        if use.unaware:
            # Nobody settles down to sleep on an empty stomach: the hungrier, the less bed appeals.
            score *= 1.0 - min(1.0, max(0.0, resident.needs.hunger - SUPPER_HUNGER) / SUPPER_RANGE)
        if use.preferred_hours is not None:
            if in_hours(world.clock.hour, use.preferred_hours):
                score *= PREFERRED_HOURS_BONUS
            else:
                # The wrong time of day matters less and less as the need becomes desperate.
                worst = max((getattr(resident.needs, need) for need in relief if need in NEED_NAMES), default=0.0)
                desperation = min(1.0, max(0.0, (worst - DESPERATE_FROM) / (100.0 - DESPERATE_FROM)))
                score *= OFF_HOURS_PENALTY + (1.0 - OFF_HOURS_PENALTY) * desperation
        return score - DISTANCE_COST * manhattan(resident.tile, (placed.x, placed.y))

    def _use(
        self, world: "SimulationWorld", resident: Resident, placed: Interactable, action: str | None = None
    ) -> Activity | None:
        definition = world.definition_of(placed)
        use = definition.use_for(action)
        if use is None:
            return None
        if use.position == "on":
            spots = [(placed.x, placed.y)]
            passable = world.passable(also=spots)
        else:
            spots = adjacent_spots(world, resident, placed)
            if world.registries.manners.during(SIT, use.action) is not None:
                # What is done sitting down is done from a seat, if one stands free beside it:
                # the nearest of those, before the nearest patch of ground.
                spots.sort(key=lambda spot: seat_at(world, spot) is None)
            passable = world.passable()
        for spot in spots:
            path = find_path(resident.tile, spot, passable)
            if path is not None:
                return Activity(use.action, placed.object_id, path, use.minutes)
        return None

    def _shelter(self, world: "SimulationWorld", resident: Resident) -> Activity | None:
        """A walk to the nearest free spot under a roof, to wait there for the weather to pass."""
        passable = world.passable()
        taken = spots_taken(world, resident)
        rooms = sorted(
            (room for room in world.rooms.values() if room.roofed),
            key=lambda room: (
                manhattan(resident.tile, (room.x + room.width // 2, room.y + room.height // 2)), room.room_id
            ),
        )
        for room in rooms:
            spots = sorted(
                (
                    (x, y)
                    for x in range(room.x, room.x + room.width)
                    for y in range(room.y, room.y + room.height)
                    if passable((x, y)) and (x, y) not in taken
                ),
                key=lambda spot: (manhattan(resident.tile, spot), spot),
            )
            for spot in spots[:3]:
                path = find_path(resident.tile, spot, passable)
                if path is not None:
                    return Activity(SHELTER_ACTION, None, path, SHELTER_MINUTES)
        return None

    def _wander(self, world: "SimulationWorld", resident: Resident) -> Activity:
        minutes = world.rng.randint(*WANDER_MINUTES)
        passable = world.passable()
        taken = spots_taken(world, resident)
        # Nobody who is in the dry strolls out into a storm, nor out of doors against a law they
        # keep: whoever keeps a curfew stays under the roof they are under.
        curfew = bool(world.government.laws) and world.politics.laws.indoors(world, resident)
        indoors_only = (curfew or world.happenings.is_stormy(world)) and world.under_roof(resident.tile)
        same_roof = curfew and indoors_only
        for _ in range(WANDER_ATTEMPTS):
            target = (
                resident.x + world.rng.randint(-WANDER_RANGE, WANDER_RANGE),
                resident.y + world.rng.randint(-WANDER_RANGE, WANDER_RANGE),
            )
            if not passable(target) or target in taken or (indoors_only and not world.under_roof(target)):
                continue
            if same_roof and not world.politics.laws.under_same_roof(world, resident, target):
                continue
            path = find_path(resident.tile, target, passable)
            if path is not None:
                return Activity(WANDER_ACTION, None, path, minutes)
        return Activity(WANDER_ACTION, None, [], minutes)
