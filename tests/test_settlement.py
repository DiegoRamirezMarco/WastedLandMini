import unittest

from save.save_manager import SaveManager
from simulation.ai.activity_system import MOVE_TILES_PER_MINUTE
from simulation.ai.routine_system import RoutineSystem, in_hours
from simulation.registries import builtin_registries
from simulation.residents.activity import Activity
from simulation.residents.needs import NEED_NAMES, Needs
from simulation.world import SimulationWorld
from world.pathfinding import find_path, manhattan

MINUTES_PER_DAY = 24 * 60


def _grid_passable(rows: list[str]):
    return lambda tile: 0 <= tile[1] < len(rows) and 0 <= tile[0] < len(rows[0]) and rows[tile[1]][tile[0]] == "."


class PathfindingTests(unittest.TestCase):
    def test_path_goes_around_a_wall_by_the_shortest_route(self) -> None:
        rows = [
            ".....",
            ".###.",
            ".....",
        ]
        path = find_path((0, 2), (4, 0), _grid_passable(rows))
        self.assertIsNotNone(path)
        self.assertEqual(len(path), manhattan((0, 2), (4, 0)))
        self.assertEqual(path[-1], (4, 0))
        self.assertNotIn((2, 1), path)

    def test_steps_are_adjacent_and_exclude_the_start(self) -> None:
        path = find_path((0, 0), (3, 2), _grid_passable(["....", "....", "...."]))
        previous = (0, 0)
        for step in path:
            self.assertEqual(manhattan(previous, step), 1)
            previous = step

    def test_unreachable_goal_has_no_path(self) -> None:
        self.assertIsNone(find_path((0, 0), (2, 0), _grid_passable([".#."])))

    def test_start_equal_to_goal_is_an_empty_path(self) -> None:
        self.assertEqual(find_path((1, 0), (1, 0), _grid_passable(["..."])), [])


class SettlementMapTests(unittest.TestCase):
    def test_every_usable_object_can_be_reached_from_every_spawn(self) -> None:
        world = SimulationWorld.demo_world()
        routine = RoutineSystem()
        usable = [placed for placed in world.interactables.values() if world.definition_of(placed).use]
        self.assertGreaterEqual(len(usable), 3)
        for resident in world.residents.values():
            for placed in usable:
                self.assertIsNotNone(routine._use(world, resident, placed), placed.object_id)

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
                self.assertEqual(resident.trail[-1], resident.tile)
                for previous, step in zip(resident.trail, resident.trail[1:]):
                    self.assertEqual(manhattan(previous, step), 1)
                    self.assertTrue(walkable(step) or step in beds, step)

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
