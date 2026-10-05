import json
import unittest

from save.save_manager import SaveManager
from simulation.events.world_event import Upcoming
from simulation.residents.activity import Activity
from simulation.residents.needs import Needs
from simulation.social.social_system import argument_chance
from simulation.work.work_system import WORK_ACTION
from simulation.world import POWER_ITEM, SimulationWorld


def _settled(seed: int = 7) -> SimulationWorld:
    world = SimulationWorld.demo_world(seed=seed)
    world.relationships.clear()
    for resident in world.residents.values():
        resident.needs = Needs(hunger=0, thirst=0, tiredness=0, social=0, stress=0)
    return world


def _on_duty(world: SimulationWorld, resident_id: str, minutes: int = 120):
    resident = world.residents[resident_id]
    post = world.interactables[resident.post_id]
    resident.x, resident.y = post.x, post.y - 1
    resident.activity = Activity(WORK_ACTION, resident.post_id, minutes_left=minutes, using=True)
    resident.current_action = WORK_ACTION
    return resident


class WaterTests(unittest.TestCase):
    def test_thirst_grows_and_water_from_the_tank_slakes_it(self) -> None:
        world = _settled()
        raul = world.residents["raul"]
        tank = world.containers["water_tank"]
        before = tank.count("water")
        raul.needs.thirst = 90
        raul.x, raul.y = 53, 15

        activity = world.activities.routine.plan(world, raul)
        self.assertEqual((activity.action, activity.target_id), ("drink_water", "water_tank"))
        raul.activity = activity
        for _ in range(30):
            world.step(1)
            if raul.activity is None:
                break

        self.assertLess(raul.needs.thirst, 50)
        self.assertEqual(tank.count("water"), before - 1)

    def test_no_water_is_reported_separately_from_no_food(self) -> None:
        world = _settled()
        for object_id, inventory in world.containers.items():
            if world.interactables[object_id].kind == "water_tank":
                inventory.items.clear()
        raul = world.residents["raul"]
        self.assertIsNone(world.items.take_food(world, raul, "water_tank", "water"))
        event_types = [line.split(" | ")[1] for line in world.event_log]
        self.assertIn("no_water", event_types)
        self.assertNotIn("no_food", event_types)


class PowerTests(unittest.TestCase):
    def test_powered_lamps_and_radio_depend_on_generator_fuel(self) -> None:
        world = _settled()
        world.clock.hour = 23
        self.assertTrue(world.has_power())
        self.assertTrue(world.is_lit((26, 34)), "the gate lamp has power")

        world.containers["generator"].items.clear()
        self.assertFalse(world.has_power())
        self.assertFalse(world.is_lit((26, 34)), "a lamp without the generator is dark")
        self.assertTrue(world.is_lit((19, 13)), "firelight still works")

        upcoming = Upcoming("raid", world.clock.total_minutes + 60)
        world.upcoming.append(upcoming)
        world.happenings.hear_radio(world, world.residents["tomas"])
        self.assertIsNone(upcoming.fact_id)
        world.stock(world.containers["generator"], POWER_ITEM, 1, None)
        world.happenings.hear_radio(world, world.residents["tomas"])
        self.assertIsNotNone(upcoming.fact_id)

    def test_the_generator_burns_one_fuel_when_night_starts(self) -> None:
        world = _settled()
        world.clock.hour, world.clock.minute = 21, 59
        before = world.power_units()
        world.step(1)
        self.assertEqual(world.power_units(), before - 1)


class MoodTests(unittest.TestCase):
    def test_low_mood_makes_arguments_likelier(self) -> None:
        world = _settled()
        a, b = world.residents["marta"], world.residents["lucia"]
        a.mood = b.mood = 50
        ordinary = argument_chance(world, a, b)
        a.mood = b.mood = 5
        self.assertGreater(argument_chance(world, a, b), ordinary)

    def test_low_mood_slows_productive_work(self) -> None:
        high = _settled()
        low = _settled()
        for world, mood in ((high, 50), (low, 20)):
            world.clock.hour = 8
            farmer = _on_duty(world, "raul", minutes=60)
            farmer.mood = mood
            farmer.inventory.items = [item for item in farmer.inventory.items if item.owner_id is not None]
            for _ in range(22):
                world.step(1)
                farmer.needs = Needs(hunger=0, thirst=0, tiredness=0, social=0, stress=0)
        self.assertGreater(high.residents["raul"].inventory.count("vegetables"), 0)
        self.assertEqual(low.residents["raul"].inventory.count("vegetables"), 0)


class SustenanceSaveTests(unittest.TestCase):
    def test_thirst_mood_water_and_power_round_trip_and_old_saves_get_defaults(self) -> None:
        manager = SaveManager()
        world = _settled()
        world.residents["marta"].needs.thirst = 44
        world.residents["marta"].mood = 23
        loaded = manager.from_data(json.loads(json.dumps(manager.to_data(world))))
        self.assertEqual(manager.to_data(loaded), manager.to_data(world))

        data = manager.to_data(world)
        data["version"] = 15
        data["interactables"] = [placed for placed in data["interactables"] if placed["id"] not in ("water_tank", "generator")]
        data["containers"].pop("water_tank")
        data["containers"].pop("generator")
        for resident in data["residents"]:
            resident["needs"].pop("thirst", None)
            resident.pop("mood", None)
        older = manager.from_data(json.loads(json.dumps(data)))
        self.assertIn("water_tank", older.containers)
        self.assertIn("generator", older.containers)
        self.assertGreater(older.containers["water_tank"].count("water"), 0)
        self.assertGreater(older.power_units(), 0)
        self.assertTrue(all(resident.needs.thirst == 12.0 and resident.mood == 50.0 for resident in older.residents.values()))


if __name__ == "__main__":
    unittest.main()
