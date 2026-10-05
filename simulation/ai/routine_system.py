"""Chooses what a resident does next by scoring the things they could do."""

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from simulation.ai.navigation import adjacent_spots
from simulation.ai.utility_ai import DISTANCE_COST, ScoredAction, need_urgency, ranked
from simulation.items.item_system import ITEM_ACTIONS, ItemSystem
from simulation.residents.activity import SHELTER_ACTION, WANDER_ACTION, Activity
from simulation.residents.needs import NEED_NAMES
from simulation.residents.resident import Resident
from simulation.social.bonds import TRYST, TRYST_ACTION
from simulation.social.social_system import SocialSystem
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
        for placed in world.interactables.values():
            use = world.definition_of(placed).use
            if use is None or world.users_of(placed.object_id) >= use.capacity:
                continue
            if use.staffed_by is not None and not world.work.is_staffed(world, use.staffed_by):
                continue
            score = self._score_use(world, resident, placed, use)
            if score is not None:
                scored.append(ScoredAction(use.action, score + self._noise(world), placed.object_id))
        for talk in self.social.candidates(world, resident):
            scored.append(ScoredAction(talk.name, talk.score + self._noise(world), partner_id=talk.partner_id))
        for tryst in world.bonds.candidates(world, resident):
            scored.append(ScoredAction(tryst.name, tryst.score + self._noise(world), partner_id=tryst.partner_id))
        for handle in self.items.candidates(world, resident):
            scored.append(
                ScoredAction(handle.name, handle.score + self._noise(world), handle.target_id, item_id=handle.item_id)
            )
        work = world.work.candidate(world, resident)
        if work is not None:
            scored.append(ScoredAction(work.name, work.score + self._noise(world), work.target_id))
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
            if (use := world.definition_of(placed).use) is not None
        )

    def _offers(
        self, world: "SimulationWorld", resident: Resident, placed: Interactable, use: UseDefinition, need: str
    ) -> bool:
        """Whether a use would lower a need, as things stand: open, within their means and not empty."""
        if use.staffed_by is not None and not world.work.is_staffed(world, use.staffed_by):
            return False
        if use.price > resident.credits:
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
            elif candidate.name == SHELTER_ACTION:
                activity = self._shelter(world, resident)
            elif candidate.target_id is None:
                return self._wander(world, resident)
            else:
                activity = self._use(world, resident, world.interactables[candidate.target_id])
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
        if use.price > resident.credits:
            return None
        if use.sells or use.repairs > 0:
            want = (
                world.trade.shop_score(world, resident, placed.object_id)
                if use.sells
                else world.trade.repair_score(world, resident, use)
            )
            return want - distance_cost if want is not None else None
        if use.heals:
            care = world.health.care_score(resident)
            return care - DISTANCE_COST * manhattan(resident.tile, (placed.x, placed.y)) if care > 0 else None
        relief = dict(use.per_minute)
        item_id = use.item_id
        if use.consumes is not None:
            food = self.items.best_food(world, resident, placed.object_id, use.consumes)
            if food is None:
                return None
            item_id = food.definition_id
        quality = 1.0
        if item_id is not None:
            item = world.registries.items.resolve(item_id)
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
        score *= quality
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

    def _use(self, world: "SimulationWorld", resident: Resident, placed: Interactable) -> Activity | None:
        definition = world.definition_of(placed)
        use = definition.use
        if use is None:
            return None
        if use.position == "on":
            spots = [(placed.x, placed.y)]
            passable = world.passable(also=spots)
        else:
            spots = adjacent_spots(world, resident, placed)
            passable = world.passable()
        for spot in spots:
            path = find_path(resident.tile, spot, passable)
            if path is not None:
                return Activity(use.action, placed.object_id, path, use.minutes)
        return None

    def _shelter(self, world: "SimulationWorld", resident: Resident) -> Activity | None:
        """A walk to the nearest free spot under a roof, to wait there for the weather to pass."""
        passable = world.passable()
        taken = {other.destination for other in world.residents.values() if other is not resident}
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
        # Nobody who is in the dry strolls out into a storm.
        indoors_only = world.happenings.is_stormy(world) and world.under_roof(resident.tile)
        for _ in range(WANDER_ATTEMPTS):
            target = (
                resident.x + world.rng.randint(-WANDER_RANGE, WANDER_RANGE),
                resident.y + world.rng.randint(-WANDER_RANGE, WANDER_RANGE),
            )
            if not passable(target) or (indoors_only and not world.under_roof(target)):
                continue
            path = find_path(resident.tile, target, passable)
            if path is not None:
                return Activity(WANDER_ACTION, None, path, minutes)
        return Activity(WANDER_ACTION, None, [], minutes)
