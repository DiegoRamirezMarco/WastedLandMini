import math
import unittest

from save.save_manager import SaveManager
from simulation.ai.activity_system import MOVE_TILES_PER_MINUTE
from simulation.ai.routine_system import RoutineSystem, in_hours
from simulation.registries import builtin_registries
from simulation.residents.activity import Activity
from simulation.residents.needs import NEED_NAMES, Needs
from simulation.world import SimulationWorld
from world.pathfinding import find_path, line, manhattan, sight, straight_ahead

MINUTES_PER_DAY = 24 * 60


def _tile_of(point: tuple[float, float]) -> tuple[int, int]:
    """The tile a point of a trail is on."""
    return (math.floor(point[0] + 0.5), math.floor(point[1] + 0.5))


def _grid_passable(rows: list[str]):
    return lambda tile: 0 <= tile[1] < len(rows) and 0 <= tile[0] < len(rows[0]) and rows[tile[1]][tile[0]] == "."


class PathfindingTests(unittest.TestCase):
    def assertWalkable(self, start, path, passable) -> None:
        """Every step is onto a free tile beside the last one, and none squeezes past a corner."""
        previous = start
        for step in path:
            dx, dy = step[0] - previous[0], step[1] - previous[1]
            self.assertEqual(max(abs(dx), abs(dy)), 1, (previous, step))
            self.assertTrue(passable(step), step)
            if dx and dy:
                self.assertTrue(passable((step[0], previous[1])) and passable((previous[0], step[1])), (previous, step))
            previous = step

    def test_path_goes_around_a_wall_by_a_short_route(self) -> None:
        rows = [
            ".....",
            ".###.",
            ".....",
        ]
        passable = _grid_passable(rows)
        path = find_path((0, 2), (4, 0), passable)
        self.assertIsNotNone(path)
        self.assertEqual(len(path), manhattan((0, 2), (4, 0)), "the corner of the wall is gone round, not cut")
        self.assertEqual(path[-1], (4, 0))
        self.assertWalkable((0, 2), path, passable)

    def test_steps_are_adjacent_and_exclude_the_start(self) -> None:
        passable = _grid_passable(["....", "....", "...."])
        path = find_path((0, 0), (3, 2), passable)
        self.assertNotIn((0, 0), path)
        self.assertWalkable((0, 0), path, passable)

    def test_unreachable_goal_has_no_path(self) -> None:
        self.assertIsNone(find_path((0, 0), (2, 0), _grid_passable([".#."])))

    def test_start_equal_to_goal_is_an_empty_path(self) -> None:
        self.assertEqual(find_path((1, 0), (1, 0), _grid_passable(["..."])), [])

    def test_open_ground_is_crossed_in_a_straight_line_at_any_angle(self) -> None:
        passable = _grid_passable(["........"] * 6)
        for goal in ((7, 0), (0, 5), (5, 5), (7, 3), (2, 5), (7, 1)):
            path = find_path((0, 0), goal, passable)
            self.assertEqual(len(path), max(goal), "no further than going straight there")
            self.assertEqual(path, line((0, 0), goal))
            for x, y in path:
                # Never more than half a tile from the line itself.
                self.assertLessEqual(abs(x * goal[1] - y * goal[0]) / max(goal), 0.5, (goal, (x, y)))
            # And back again, the other way.
            back = find_path(goal, (0, 0), passable)
            self.assertEqual(len(back), max(goal))
            self.assertWalkable(goal, back, passable)

    def test_nobody_squeezes_between_two_things_that_touch_at_a_corner(self) -> None:
        rows = [
            ".#.",
            "#..",
            "...",
        ]
        self.assertIsNone(find_path((0, 0), (2, 2), _grid_passable(rows)))
        rows = [
            "..#.",
            ".#..",
            "....",
        ]
        passable = _grid_passable(rows)
        path = find_path((0, 0), (3, 0), passable)
        self.assertWalkable((0, 0), path, passable)
        self.assertEqual(path[-1], (3, 0))

    def test_a_way_round_turns_only_where_something_is_in_the_way(self) -> None:
        rows = [
            "..........",
            "..........",
            "....#.....",
            "....#.....",
            "....#.....",
            "..........",
        ]
        passable = _grid_passable(rows)
        path = find_path((0, 3), (9, 3), passable)
        self.assertWalkable((0, 3), path, passable)
        self.assertLess(len(path), manhattan((0, 3), (9, 3)) + 4, "shorter than going round it square")
        turns, start, rest = 0, (0, 3), list(path)
        while rest:
            stretch = straight_ahead(start, rest)
            start, rest, turns = rest[len(stretch) - 1], rest[len(stretch) :], turns + 1
        self.assertLessEqual(turns, 3)

    def test_what_is_straight_ahead_is_a_point_for_each_tile_of_the_stretch(self) -> None:
        path = line((2, 2), (9, 5)) + line((9, 5), (9, 8))
        stretch = straight_ahead((2, 2), path)
        self.assertEqual(len(stretch), 7)
        self.assertEqual(stretch[-1], (9.0, 5.0))
        for tile, (x, y) in zip(path, stretch):
            self.assertLessEqual(max(abs(x - tile[0]), abs(y - tile[1])), 0.5)
            # On the line from one end of the stretch to the other.
            self.assertAlmostEqual((x - 2) * 3, (y - 2) * 7)
        self.assertEqual(straight_ahead((0, 0), [(5, 5)]), [(5.0, 5.0)], "a jump is no stretch at all")
        self.assertEqual(straight_ahead((0, 0), []), [])


class SettlementMapTests(unittest.TestCase):
    def test_every_usable_object_can_be_reached_from_every_spawn(self) -> None:
        world = SimulationWorld.demo_world()
        routine = RoutineSystem()
        usable = [placed for placed in world.interactables.values() if world.definition_of(placed).use]
        self.assertGreaterEqual(len(usable), 3)
        for resident in world.residents.values():
            for placed in usable:
                self.assertIsNotNone(routine._use(world, resident, placed), placed.object_id)

    def test_nobody_who_gets_up_from_a_bed_can_end_up_walled_in(self) -> None:
        """Whoever lies on something steps off it onto any free tile beside it. From there the way out must be open.

        A row of beds once closed off a strip of floor in the south house: whoever got up on the
        wrong side could never leave it again.
        """
        world = SimulationWorld.demo_world()
        passable = world.passable()
        spawn = world.registries.maps[world.map_id].spawns[0]
        checked = 0
        for placed in world.interactables.values():
            definition = world.definition_of(placed)
            if definition.use is None or definition.use.position != "on":
                continue
            beside = [
                (x + dx, y + dy)
                for x, y in placed.footprint(definition)
                for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))
                if passable((x + dx, y + dy))
            ]
            self.assertTrue(beside, f"{placed.object_id} cannot be got off")
            for tile in beside:
                self.assertIsNotNone(find_path(tile, spawn, passable), f"{tile} beside {placed.object_id} is walled in")
                checked += 1
        self.assertGreater(checked, 20)

    def test_blocking_objects_cannot_be_walked_through(self) -> None:
        world = SimulationWorld.demo_world()
        passable = world.passable()
        pantry = world.interactables["pantry_1"]
        self.assertFalse(passable((pantry.x, pantry.y)))
        self.assertTrue(world.passable(also=[(pantry.x, pantry.y)])((pantry.x, pantry.y)))
        stool = world.interactables["stool_1"]
        self.assertTrue(passable((stool.x, stool.y)))

    def test_rooms_are_found_by_tile(self) -> None:
        world = SimulationWorld.demo_world()
        bed = world.interactables["bed_1"]
        self.assertEqual(world.room_at((bed.x, bed.y)).room_id, "dormitory")
        self.assertIsNone(world.room_at((1, 1)))


class RoutineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.world = SimulationWorld.demo_world()
        self.routine = RoutineSystem()
        self.marta = self.world.residents["marta"]

    def test_hungry_resident_goes_to_eat(self) -> None:
        self.marta.needs.hunger = 90
        activity = self.routine.plan(self.world, self.marta)
        self.assertEqual(activity.action, "eat")
        self.assertIn(self.world.interactables[activity.target_id].kind, ("pantry", "cooking_pot"))

    def test_content_resident_wanders(self) -> None:
        self.marta.needs = Needs(hunger=0, tiredness=0, social=0, stress=0)
        self.assertEqual(self.routine.plan(self.world, self.marta).action, "wander")

    def test_tired_resident_sleeps_at_night_but_not_by_day(self) -> None:
        self.marta.needs = Needs(hunger=0, tiredness=60, social=0, stress=0)
        self.world.clock.hour = 14
        self.assertNotEqual(self.routine.plan(self.world, self.marta).action, "sleep")
        self.world.clock.hour = 23
        self.assertEqual(self.routine.plan(self.world, self.marta).action, "sleep")

    def test_exhausted_resident_sleeps_even_by_day(self) -> None:
        self.marta.needs = Needs(hunger=0, tiredness=100, social=0, stress=0)
        self.world.clock.hour = 14
        self.assertEqual(self.routine.plan(self.world, self.marta).action, "sleep")

    def test_sleep_eases_stress_but_only_tiredness_decides_when_to_wake(self) -> None:
        world = SimulationWorld.demo_world()
        marta = world.residents["marta"]
        for resident in world.residents.values():
            resident.needs = Needs(hunger=0, tiredness=0, social=0, stress=0)
        marta.needs = Needs(hunger=0, tiredness=20, social=0, stress=90)
        marta.x, marta.y = 3, 3
        marta.activity = Activity("sleep", "bed_1", minutes_left=600, using=True)
        slept = 0
        while marta.activity is not None and marta.activity.action == "sleep":
            world.step(1)
            slept += 1
        self.assertLess(slept, 200, "stress kept them in bed long after they were rested")
        self.assertLess(marta.needs.stress, 90)
        self.assertEqual(marta.needs.tiredness, 0)

    def test_two_residents_never_share_a_bed(self) -> None:
        self.world.clock.hour = 23
        targets = []
        for resident in self.world.residents.values():
            resident.needs = Needs(hunger=0, tiredness=90, social=0, stress=0)
            resident.activity = self.routine.plan(self.world, resident)
            self.assertEqual(resident.activity.action, "sleep")
            targets.append(resident.activity.target_id)
        self.assertEqual(len(set(targets)), len(targets))

    def test_night_window_wraps_past_midnight(self) -> None:
        self.assertTrue(in_hours(23, (22, 7)))
        self.assertTrue(in_hours(3, (22, 7)))
        self.assertFalse(in_hours(7, (22, 7)))
        self.assertFalse(in_hours(12, (22, 7)))


class NeedsTests(unittest.TestCase):
    def test_effects_are_clamped_and_unknown_names_ignored(self) -> None:
        needs = Needs(hunger=10)
        needs.apply({"hunger": -25, "radiation": 5})
        self.assertEqual(needs.hunger, 0)
        self.assertFalse(hasattr(needs, "radiation"))

    def test_eating_lowers_hunger_by_the_item_effect(self) -> None:
        world = SimulationWorld.demo_world()
        marta = world.residents["marta"]
        marta.needs.hunger = 90
        for _ in range(4 * 60):
            world.step(1)
            if marta.current_action == "eat":
                break
        self.assertEqual(marta.current_action, "eat")
        before = marta.needs.hunger
        world.step(20)
        beans = builtin_registries().items.get("canned_beans")
        self.assertLess(marta.needs.hunger, before + beans.effects["hunger"] + 5)


class LifeInTheSettlementTests(unittest.TestCase):
    def test_residents_only_walk_between_adjacent_walkable_tiles(self) -> None:
        world = SimulationWorld.demo_world(seed=3)
        walkable = world.passable()
        # Beds of any kind are lain on, so their own tile is walked onto.
        beds = {
            (placed.x, placed.y)
            for placed in world.interactables.values()
            if (use := world.definition_of(placed).use) is not None and use.position == "on"
        }
        for _ in range(2 * MINUTES_PER_DAY):
            world.step(1)
            for resident in world.residents.values():
                self.assertLessEqual(len(resident.trail) - 1, MOVE_TILES_PER_MINUTE)
                # They may be part-way along a line that does not run through the middle of their tile.
                self.assertEqual(_tile_of(resident.trail[-1]), resident.tile)
                for previous, step in zip(resident.trail, resident.trail[1:]):
                    before, after = _tile_of(previous), _tile_of(step)
                    self.assertLessEqual(max(abs(after[0] - before[0]), abs(after[1] - before[1])), 1)
                    self.assertLess(math.dist(previous, step), 1.5)
                    self.assertTrue(walkable(after) or after in beds, step)
                    if after[0] != before[0] and after[1] != before[1]:
                        for corner in ((after[0], before[1]), (before[0], after[1])):
                            self.assertTrue(walkable(corner) or corner in beds, f"{before} to {after} cuts a corner")

    def test_a_walk_across_open_ground_is_seen_to_go_straight(self) -> None:
        world = SimulationWorld.demo_world(seed=3)
        passable = world.passable()
        marta = world.residents["marta"]
        # The longest slanting walk there is from where she stands with nothing in the way.
        goal = max(
            (
                (x, y)
                for x in range(world.tile_map.width)
                for y in range(world.tile_map.height)
                if abs(x - marta.x) > 2 * abs(y - marta.y) > 4 and sight(marta.tile, (x, y), passable)
            ),
            key=lambda tile: (abs(tile[0] - marta.x), tile),
        )
        start = marta.tile
        marta.activity = Activity("wander", path=find_path(start, goal, passable), minutes_left=5)
        walked = [(float(start[0]), float(start[1]))]
        while marta.tile != goal:
            world.activities.tick(world, marta)
            self.assertEqual(marta.trail[0], walked[-1], "each minute goes on from where the last one ended")
            self.assertEqual(_tile_of(marta.trail[-1]), marta.tile)
            walked.extend(marta.trail[1:])
        self.assertEqual(walked[-1], goal)
        rise = (goal[1] - start[1]) / (goal[0] - start[0])
        for x, y in walked:
            self.assertAlmostEqual(y, start[1] + (x - start[0]) * rise, msg="every point of it is on the one line")
        self.assertGreater(len({y for _, y in walked}), 3)

    def test_whoever_stops_part_way_along_a_line_steps_onto_their_tile(self) -> None:
        world = SimulationWorld.demo_world(seed=3)
        marta = world.residents["marta"]
        marta.needs = Needs(hunger=0, tiredness=0, social=0, stress=0)
        marta.trail = [(marta.x - 1.0, marta.y - 0.25), (marta.x + 0.0, marta.y + 0.5)]
        marta.activity = Activity("wander", minutes_left=5, using=True)
        world.activities.tick(world, marta)
        self.assertEqual(marta.trail, [(marta.x, marta.y + 0.5), marta.tile])
        world.activities.tick(world, marta)
        self.assertEqual(marta.trail, [marta.tile])
        # Put somewhere else outright, they do not slide there.
        marta.x += 6
        world.activities.tick(world, marta)
        self.assertEqual(marta.trail, [marta.tile])

    def test_a_week_passes_without_any_need_reaching_its_maximum(self) -> None:
        for seed in (7, 42):
            world = SimulationWorld.demo_world(seed=seed)
            self.assertGreaterEqual(len(world.residents), 3)
            used: set[str] = set()
            for _ in range(7 * MINUTES_PER_DAY):
                world.step(1)
                for resident in world.residents.values():
                    used.add(resident.current_action)
                    for need in NEED_NAMES:
                        self.assertLess(getattr(resident.needs, need), 100.0, (seed, resident.name, need))
            self.assertLessEqual({"eat", "sleep", "relax", "walking"}, used)

    def test_residents_sleep_mostly_at_night(self) -> None:
        world = SimulationWorld.demo_world(seed=7)
        night = day = 0
        for _ in range(7 * MINUTES_PER_DAY):
            world.step(1)
            asleep = sum(1 for resident in world.residents.values() if resident.current_action == "sleep")
            if in_hours(world.clock.hour, (22, 7)):
                night += asleep
            else:
                day += asleep
        self.assertGreater(night, 9 * day)
        self.assertGreater(night, 3 * 7 * 6 * 60)


class SettlementSaveTests(unittest.TestCase):
    def setUp(self) -> None:
        self.manager = SaveManager()

    def test_loading_mid_activity_continues_exactly_like_not_saving(self) -> None:
        original = SimulationWorld.demo_world(seed=11)
        original.step(900)
        self.assertTrue(any(resident.activity for resident in original.residents.values()))
        loaded = self.manager.from_data(self.manager.to_data(original))
        self.assertEqual(self.manager.to_data(loaded), self.manager.to_data(original))
        original.step(3 * MINUTES_PER_DAY)
        loaded.step(3 * MINUTES_PER_DAY)
        self.assertEqual(self.manager.to_data(loaded), self.manager.to_data(original))

    def test_version_1_save_with_pixel_positions_is_migrated_onto_the_map(self) -> None:
        old = {
            "version": 1,
            "clock": {"day": 3, "hour": 9, "minute": 30},
            "rng": {"seed": 5},
            "residents": [
                {"id": "marta", "name": "Marta", "x": 130.0, "y": 110.0, "needs": {"hunger": 40.0}},
                {"id": "raul", "name": "Raúl", "x": 260.0, "y": 165.0},
            ],
            "relationships": [{"source_id": "marta", "target_id": "raul", "resentment": 35.0}],
        }
        world = self.manager.from_data(old)
        walkable = world.passable()
        self.assertEqual(world.map_id, "settlement")
        self.assertEqual(world.clock.day, 3)
        self.assertEqual(world.residents["marta"].needs.hunger, 40.0)
        self.assertEqual(world.relationship("marta", "raul").resentment, 35.0)
        for resident in world.residents.values():
            self.assertTrue(walkable(resident.tile), resident.tile)
        world.step(MINUTES_PER_DAY)

    def test_save_from_a_removed_map_or_object_kind_still_loads(self) -> None:
        world = SimulationWorld.demo_world()
        world.residents["marta"].needs.tiredness = 100
        world.step(1)
        self.assertEqual(world.residents["marta"].activity.action, "sleep")
        data = self.manager.to_data(world)

        without_beds = dict(data)
        without_beds["interactables"] = [
            dict(placed, kind="hammock") if placed["kind"] == "bed" else placed
            for placed in data["interactables"]
        ]
        loaded = self.manager.from_data(without_beds)
        self.assertFalse(any(placed.kind == "hammock" for placed in loaded.interactables.values()))
        self.assertIsNone(loaded.residents["marta"].activity)
        loaded.step(MINUTES_PER_DAY)

        loaded = self.manager.from_data(dict(data, map_id="a_map_that_was_deleted"))
        self.assertEqual(loaded.map_id, "settlement")
        loaded.step(MINUTES_PER_DAY)


if __name__ == "__main__":
    unittest.main()
