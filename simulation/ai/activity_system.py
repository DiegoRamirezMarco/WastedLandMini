"""Advances residents through their activities one game minute at a time."""

from collections.abc import Collection
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from simulation.ai.crowd import Crowd, spots_taken, walking
from simulation.ai.navigation import path_beside
from simulation.ai.routine_system import RoutineSystem
from simulation.events.event import DomainEvent
from simulation.health.health_system import RECOVERED_HEALTH
from simulation.items.item_system import ITEM_ACTIONS
from simulation.residents.activity import MOVE_TILES_PER_MINUTE, SHELTER_ACTION, WANDER_ACTION, Activity
from simulation.residents.needs import BODILY_NEEDS, URGENT_NEED
from simulation.residents.resident import Resident
from simulation.social.social_system import SocialSystem
from simulation.work.construction import BUILD_ACTION, CARRY_ACTION
from simulation.work.expedition_system import EXPEDITION_ACTION
from simulation.work.work_system import HAUL_ACTION, WORK_ACTION
from world.interactable import UseDefinition
from world.map import Tile
from world.pathfinding import Point, find_path, reach, straight_ahead

if TYPE_CHECKING:
    from simulation.world import SimulationWorld

ROUTINE_EVENT_IMPORTANCE = 5
MOOD_DRIFT = 0.002
# Minutes somebody waits for whoever is passing in front of them before looking for a way round.
WAIT_MINUTES = 1
# Minutes with no way on and no way round after which they give up, and walk a little way off
# for a while so as not to be in the way themselves.
PATIENCE_MINUTES = 2
BACK_OFF_TILES = 3
BACK_OFF_MINUTES = (2, 6)
# How far somebody with nothing to keep them where they stand will go to be out of the way.
ASIDE_TILES = 4


def facing_towards(origin: Tile, target: Tile) -> str | None:
    dx, dy = target[0] - origin[0], target[1] - origin[1]
    if dx == 0 and dy == 0:
        return None
    # Going diagonally they are seen from the side.
    if abs(dx) >= abs(dy):
        return "right" if dx > 0 else "left"
    return "down" if dy > 0 else "up"


def _within(point: Point, tile: Tile) -> bool:
    """Whether a point is on a tile: no further than half a tile from the middle of it."""
    return abs(point[0] - tile[0]) <= 0.5 and abs(point[1] - tile[1]) <= 0.5


@dataclass
class ActivitySystem:
    routine: RoutineSystem = field(default_factory=RoutineSystem)
    social: SocialSystem = field(default_factory=SocialSystem)

    def begin_minute(self, world: "SimulationWorld") -> None:
        """Start everybody's trail again before anybody moves: what is on one after this was walked this minute."""
        for resident in world.residents.values():
            self._begin_trail(resident)

    def _begin_trail(self, resident: Resident) -> None:
        # The trail goes on from where the last one left them, which is the middle of their tile
        # unless they are part-way along a stretch that is not in line with it.
        last = resident.trail[-1] if resident.trail else resident.tile
        resident.trail = [last if _within(last, resident.tile) else resident.tile]

    def tick(self, world: "SimulationWorld", resident: Resident) -> None:
        self._begin_trail(resident)
        self._act(world, resident)
        if len(resident.trail) == 1:
            # They walked no further. Left off the middle of their tile, they step onto it;
            # moved somewhere else outright, they are simply there.
            if resident.trail[0] != resident.tile and _within(resident.trail[0], resident.tile):
                resident.trail.append(resident.tile)
            else:
                resident.trail = [resident.tile]

    def _act(self, world: "SimulationWorld", resident: Resident) -> None:
        # Asleep, the body runs slow. So it does for someone out there, who eats as they go from what they took.
        resident.needs.step(1, resting=resident.away or not world.is_aware(resident))
        self._settle_mood(resident)
        world.health.tick(world, resident)
        if resident.resident_id not in world.residents:
            # Going without took them.
            return
        for need in self.unanswerable(world, resident):
            world.items.report_nothing_for(world, resident, need)
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
            self._walk(world, resident, world.health.walk_tiles(world, resident))
            if resident.activity is not activity:
                # With no way through, they gave it up.
                return
            if activity.intent is not None:
                # Chasing someone counts against the time they will keep at it.
                activity.minutes_left -= 1
                if activity.minutes_left <= 0 or self.urgent_needs(world, resident):
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
        if activity.action == BUILD_ACTION:
            world.construction.build_tick(world, resident, activity)
            return
        if activity.action == CARRY_ACTION:
            world.construction.carry_tick(world, resident, activity)
            return
        use = self._use_of(world, activity)
        if not activity.using:
            if not self._begin(world, resident, activity, use):
                resident.activity = None
                resident.current_action = "idle"
                return
            activity.using = True
        self._spend_minute(world, resident, activity, use)

    def _walk(self, world: "SimulationWorld", resident: Resident, tiles: int = MOVE_TILES_PER_MINUTE) -> None:
        crowd = Crowd(world, resident)
        moved = False
        for _ in range(tiles):
            activity = resident.activity
            if not activity.path or not self._way_clear(world, resident, activity, crowd):
                break
            # It may be another walk by now, or a stroll for having given this one up.
            activity = resident.activity
            moved = True
            if not resident.ahead or not _within(resident.ahead[0], activity.path[0]):
                # A new stretch, or a way that is not the one they were on.
                resident.ahead = straight_ahead(resident.tile, activity.path)
            step = activity.path.pop(0)
            resident.facing = facing_towards(resident.tile, step) or resident.facing
            resident.x, resident.y = step
            resident.trail.append(resident.ahead.pop(0))
        activity = resident.activity
        activity.held_up = activity.held_up + 1 if activity.path and not moved else 0
        resident.current_action = "walking"

    def _way_clear(self, world: "SimulationWorld", resident: Resident, activity: Activity, crowd: Crowd) -> bool:
        """Whether the next step of a walk can be taken this minute.

        With somebody in the way it may come to be a step somewhere else: round them, to another
        place that does as well, or off to one side for having given up.
        """
        step = activity.path[0]
        if crowd.free(resident.tile, step):
            return True
        other = crowd.at.get(step)
        passing = other is None or (walking(other) and other.activity.path[0] != resident.tile)
        if passing and activity.held_up < WAIT_MINUTES:
            # Whoever it is will be gone in a moment.
            return False
        path = self._way_round(world, resident, activity, crowd)
        if path is None and other is not None and self._make_room(world, resident, activity, other):
            # They are asked to step aside, and do.
            return False
        if path is None and activity.held_up >= PATIENCE_MINUTES:
            self._back_off(world, resident, crowd)
            path = resident.activity.path
        elif path is not None:
            activity.path, resident.ahead = path, []
        return bool(path) and crowd.free(resident.tile, path[0])

    def _way_round(
        self, world: "SimulationWorld", resident: Resident, activity: Activity, crowd: Crowd
    ) -> list[Tile] | None:
        """Another walk to what a resident is after, round whoever is in the way. None if there is none.

        To where they were going, if nobody has stopped there. If somebody has, to another place
        that does as well: beside the same person, or beside the same thing. Out for a stroll,
        where they are does as well as anywhere.
        """
        goal = activity.path[-1]
        holder = crowd.at.get(goal)
        if holder is None or walking(holder):
            return find_path(resident.tile, goal, crowd.passable(() if crowd.open(goal) else (goal,)))
        if activity.partner_id is not None:
            partner = world.residents.get(activity.partner_id)
            planned = self.social.approach(world, resident, partner, crowd.passable()) if partner is not None else None
            return planned.path if planned is not None else None
        placed = world.interactables.get(activity.target_id or "")
        if placed is not None:
            return path_beside(world, resident, placed, crowd.passable())
        site = world.sites.get(activity.target_id or "")
        if site is not None:
            return world.construction.path_to(world, resident, site, crowd.passable())
        return [] if activity.action == WANDER_ACTION else None

    def _make_room(self, world: "SimulationWorld", resident: Resident, activity: Activity, other: Resident) -> bool:
        """Have whoever stands in a resident's way step aside, if nothing keeps them where they are.

        Somebody strolling about or waiting out the weather moves, to the nearest place that is
        not on the way of whoever wants to get by, and goes on with what they were at: under a
        roof still, if they were sheltering. Somebody at work, at table, in bed or in talk stays.
        False if they stay.
        """
        theirs = other.activity
        if theirs is not None and (
            theirs.path
            or theirs.partner_id is not None
            or theirs.target_id is not None
            or theirs.action not in (WANDER_ACTION, SHELTER_ACTION)
        ):
            return False
        passable = Crowd(world, other).passable()
        keep_clear = {resident.tile, *activity.path} | spots_taken(world, other)
        dry = theirs is not None and theirs.action == SHELTER_ACTION
        spot = next(
            (
                tile
                for tile in reach(other.tile, ASIDE_TILES, passable)
                if tile not in keep_clear and (not dry or world.under_roof(tile))
            ),
            None,
        )
        path = find_path(other.tile, spot, passable) if spot is not None else None
        if not path:
            return False
        if theirs is None:
            other.activity = Activity(WANDER_ACTION, path=path, minutes_left=world.rng.randint(*BACK_OFF_MINUTES))
        else:
            # Once there they settle down to it again.
            theirs.path, theirs.using = path, False
        other.ahead = []
        return True

    def _back_off(self, world: "SimulationWorld", resident: Resident, crowd: Crowd) -> None:
        """Give up what a resident was on their way to, and have them walk a little way off if there is anywhere to."""
        passable = crowd.passable()
        taken = spots_taken(world, resident)
        near = {tile: steps for tile, steps in reach(resident.tile, BACK_OFF_TILES, passable).items() if tile not in taken}
        path: list[Tile] = []
        if near:
            furthest = max(near.values())
            goal = world.rng.choice([tile for tile, steps in near.items() if steps == furthest])
            path = find_path(resident.tile, goal, passable) or []
        resident.activity = Activity(WANDER_ACTION, path=path, minutes_left=world.rng.randint(*BACK_OFF_MINUTES))
        resident.ahead = []

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
        if not world.trade.can_afford(world, resident, use):
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
        world.trade.charge(world, resident, use)
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
                event_type="meal_started" if activity.action == "eat" else "activity_started",
                importance=ROUTINE_EVENT_IMPORTANCE,
                text=f"{resident.name} {text}",
                participants=[resident.resident_id],
                location_id=room.room_id if room is not None else None,
                data={"action": activity.action, "item_id": activity.item_id},
            )
        )
        return True

    def urgent_needs(
        self, world: "SimulationWorld", resident: Resident, level: float = URGENT_NEED, ignoring: Collection[str] = ()
    ) -> list[str]:
        """Needs of the body high enough to come before whatever a resident is doing.

        One that nothing can be done about does not count: with no water anywhere, thirst keeps
        nobody from their bed or their post. It takes its toll on their health instead.
        """
        return [
            need
            for need in BODILY_NEEDS
            if need not in ignoring
            and getattr(resident.needs, need) >= level
            and self.routine.can_relieve(world, resident, need)
        ]

    def unanswerable(self, world: "SimulationWorld", resident: Resident) -> list[str]:
        """Needs of the body that are urgent and that nothing in the settlement can answer."""
        if resident.away:
            return []
        return [
            need
            for need in BODILY_NEEDS
            if getattr(resident.needs, need) >= URGENT_NEED and not self.routine.can_relieve(world, resident, need)
        ]

    def _spend_minute(
        self, world: "SimulationWorld", resident: Resident, activity: Activity, use: UseDefinition | None
    ) -> None:
        activity.minutes_left -= 1
        relieved = False
        if use is not None:
            resident.needs.apply(use.per_minute)
            lowered = [use.until] if use.until else [need for need, delta in use.per_minute.items() if delta < 0]
            relieved = bool(lowered) and all(getattr(resident.needs, need, 0.0) <= 0.0 for need in lowered)
            if (use.per_minute or use.heals) and self.urgent_needs(world, resident, ignoring=use.per_minute):
                relieved = True
            if use.heals and resident.health >= RECOVERED_HEALTH:
                relieved = True
            if use.repairs > 0 and world.trade.repair_minute(world, activity, use):
                relieved = True
        if activity.minutes_left > 0 and not relieved:
            return
        if use is not None and activity.item_id is not None and not use.sells and use.repairs <= 0:
            item = world.registries.items.resolve(activity.item_id)
            world.items.take_in(world, resident, item)
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
