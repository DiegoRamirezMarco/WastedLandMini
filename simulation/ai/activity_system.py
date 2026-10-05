"""Advances residents through their activities one game minute at a time."""

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from simulation.ai.routine_system import RoutineSystem
from simulation.events.event import DomainEvent
from simulation.health.health_system import RECOVERED_HEALTH
from simulation.items.item_system import ITEM_ACTIONS
from simulation.residents.activity import MOVE_TILES_PER_MINUTE, SHELTER_ACTION, Activity
from simulation.residents.needs import BODILY_NEEDS, URGENT_NEED
from simulation.residents.resident import Resident
from simulation.social.social_system import SocialSystem
from simulation.work.expedition_system import EXPEDITION_ACTION
from simulation.work.work_system import HAUL_ACTION, WORK_ACTION
from world.interactable import UseDefinition
from world.map import Tile

if TYPE_CHECKING:
    from simulation.world import SimulationWorld

ROUTINE_EVENT_IMPORTANCE = 5
MOOD_DRIFT = 0.002


def facing_towards(origin: Tile, target: Tile) -> str | None:
    dx, dy = target[0] - origin[0], target[1] - origin[1]
    if dx == 0 and dy == 0:
        return None
    if abs(dx) > abs(dy):
        return "right" if dx > 0 else "left"
    return "down" if dy > 0 else "up"


@dataclass
class ActivitySystem:
    routine: RoutineSystem = field(default_factory=RoutineSystem)
    social: SocialSystem = field(default_factory=SocialSystem)

    def tick(self, world: "SimulationWorld", resident: Resident) -> None:
        # Asleep, the body runs slow. So it does for someone out there, who eats as they go from what they took.
        resident.needs.step(1, resting=resident.away or not world.is_aware(resident))
        self._settle_mood(resident)
        world.health.tick(world, resident)
        resident.trail = [resident.tile]
        if resident.activity is None:
            world.items.notice_missing(world, resident)
            crisis = (
                world.interventions.maybe_open(world, resident)
                or world.interventions.maybe_offer_job(world, resident)
                or world.interventions.maybe_romance(world, resident)
            )
            resident.activity = crisis or self.routine.plan(world, resident)
        activity = resident.activity
        if activity.action == SHELTER_ACTION and not world.happenings.is_stormy(world):
            # It has passed: there is nothing left to shelter from.
            resident.activity = None
            resident.current_action = "idle"
            return

        if activity.path:
            self._walk(resident, activity, world.health.walk_tiles(world, resident))
            if activity.intent is not None:
                # Chasing someone counts against the time they will keep at it.
                activity.minutes_left -= 1
                if activity.minutes_left <= 0 or self._has_urgent_need(resident, ignoring={}):
                    resident.activity = None
                    resident.current_action = "idle"
            return
        if activity.partner_id is not None:
            self.social.tick(world, resident, activity)
            return
        if activity.action in ITEM_ACTIONS:
            world.items.tick(world, resident, activity)
            return
        if activity.action == WORK_ACTION:
            world.work.tick(world, resident, activity)
            return
        if activity.action == HAUL_ACTION:
            world.work.haul_tick(world, resident, activity)
            return
        if activity.action == EXPEDITION_ACTION:
            world.expeditions.tick(world, resident, activity)
            return
        use = self._use_of(world, activity)
        if not activity.using:
            if not self._begin(world, resident, activity, use):
                resident.activity = None
                resident.current_action = "idle"
                return
            activity.using = True
        self._spend_minute(world, resident, activity, use)

    def _walk(self, resident: Resident, activity: Activity, tiles: int = MOVE_TILES_PER_MINUTE) -> None:
        for _ in range(tiles):
            if not activity.path:
                break
            step = activity.path.pop(0)
            resident.facing = facing_towards(resident.tile, step) or resident.facing
            resident.x, resident.y = step
            resident.trail.append(step)
        resident.current_action = "walking"

    def _use_of(self, world: "SimulationWorld", activity: Activity) -> UseDefinition | None:
        placed = world.interactables.get(activity.target_id) if activity.target_id else None
        return world.definition_of(placed).use if placed is not None else None

    def _begin(
        self, world: "SimulationWorld", resident: Resident, activity: Activity, use: UseDefinition | None
    ) -> bool:
        """Start the use the resident walked over for. False if it turns out to be impossible."""
        if use is None or activity.target_id is None:
            resident.current_action = SHELTER_ACTION if activity.action == SHELTER_ACTION else "idle"
            return True
        if use.staffed_by is not None and not world.work.is_staffed(world, use.staffed_by):
            return False
        if use.price > resident.credits:
            return False
        if use.sells:
            # Paid for and handed over at once; the event of it is the purchase itself.
            activity.item_id = world.trade.buy(world, resident, activity.target_id)
            if activity.item_id is None:
                return False
        elif use.repairs > 0:
            worn = world.trade.worn_item(world, resident)
            if worn is None or not world.trade.take_repair_material(world, use):
                return False
            activity.item_id = worn.instance_id
        elif use.consumes is not None:
            # What they eat is taken off the shelf now, so two residents never eat the same unit.
            activity.item_id = world.items.take_food(world, resident, activity.target_id, use.consumes)
            if activity.item_id is None:
                return False
        elif use.item_id is not None:
            activity.item_id = use.item_id
        world.trade.pay(resident, use.price)
        if use.radio:
            world.happenings.hear_radio(world, resident)
        placed = world.interactables[activity.target_id]
        resident.current_action = activity.action
        resident.facing = facing_towards(resident.tile, (placed.x, placed.y)) or "down"
        if use.sells:
            return True
        text = use.text
        if activity.item_id is not None:
            item = world.items.definition_for(world, activity.item_id)
            text = text.replace("{item}", f"{item.article} {item.name}")
        room = world.room_at(resident.tile)
        world.emit_event(
            DomainEvent(
                event_type="activity_started",
                importance=ROUTINE_EVENT_IMPORTANCE,
                text=f"{resident.name} {text}",
                participants=[resident.resident_id],
                location_id=room.room_id if room is not None else None,
            )
        )
        return True

    def _has_urgent_need(self, resident: Resident, ignoring: dict[str, float]) -> bool:
        return any(getattr(resident.needs, need) >= URGENT_NEED for need in BODILY_NEEDS if need not in ignoring)

    def _spend_minute(
        self, world: "SimulationWorld", resident: Resident, activity: Activity, use: UseDefinition | None
    ) -> None:
        activity.minutes_left -= 1
        relieved = False
        if use is not None:
            resident.needs.apply(use.per_minute)
            lowered = [use.until] if use.until else [need for need, delta in use.per_minute.items() if delta < 0]
            relieved = bool(lowered) and all(getattr(resident.needs, need, 0.0) <= 0.0 for need in lowered)
            if (use.per_minute or use.heals) and self._has_urgent_need(resident, ignoring=use.per_minute):
                relieved = True
            if use.heals and resident.health >= RECOVERED_HEALTH:
                relieved = True
            if use.repairs > 0 and world.trade.repair_minute(world, activity, use):
                relieved = True
        if activity.minutes_left > 0 and not relieved:
            return
        if use is not None and activity.item_id is not None and not use.sells and use.repairs <= 0:
            item = world.registries.items.resolve(activity.item_id)
            resident.needs.apply(world.items.use_effects(world, resident, item))
        resident.activity = None
        resident.current_action = "idle"

    def _settle_mood(self, resident: Resident) -> None:
        """Let mood drift towards how life currently feels, without becoming another urgent need."""
        needs = resident.needs
        strain = (
            needs.hunger * 0.16
            + needs.thirst * 0.2
            + needs.tiredness * 0.12
            + needs.social * 0.08
            + needs.stress * 0.24
            + max(0.0, 100.0 - resident.health) * 0.2
        )
        target = max(0.0, min(100.0, 72.0 - strain))
        resident.adjust_mood((target - resident.mood) * MOOD_DRIFT)
