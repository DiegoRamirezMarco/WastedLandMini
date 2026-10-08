"""Current (S55): what gives it, what draws it, the switches, and what stops without it."""

import subprocess
import sys
import unittest
from pathlib import Path

from save.save_manager import SaveManager
from simulation.commands import SwitchCommand
from simulation.economy.power import SHED_EVENT, SWITCHED_EVENT
from simulation.items.inventory import Inventory
from simulation.residents.attributes import Attributes
from simulation.residents.needs import Needs
from simulation.world import POWER_ITEM, SimulationWorld
from world.interactable import Interactable

ROOT = Path(__file__).resolve().parent.parent
MINUTES_PER_DAY = 24 * 60


def _keep_content(world: SimulationWorld) -> None:
    for resident in world.residents.values():
        resident.needs = Needs(hunger=0, thirst=0, tiredness=0, social=0, stress=0)


def _settled(seed: int = 7, hour: int = 7) -> SimulationWorld:
    world = SimulationWorld.demo_world(seed=seed)
    world.relationships.clear()
    world.clock.hour, world.clock.minute = hour, 0
    for resident in world.residents.values():
        resident.attributes = Attributes()
    _keep_content(world)
    return world


def _run(world: SimulationWorld, minutes: int, until=None) -> bool:
    for _ in range(minutes):
        world.step(1)
        _keep_content(world)
        if until is not None and until():
            return True
    return False


def _no_fuel(world: SimulationWorld) -> None:
    for inventory in world.containers.values():
        for item in [each for each in inventory.items if each.definition_id == POWER_ITEM]:
            inventory.remove(item.instance_id)


def _lamps(world: SimulationWorld) -> list[Interactable]:
    return [placed for placed in world.interactables.values() if placed.kind == "lamp"]


class SupplyTests(unittest.TestCase):
    def test_what_draws_and_what_gives_are_data(self) -> None:
        world = _settled()
        kinds = world.registries.interactables
        self.assertEqual(kinds.get("generator").gives, 16)
        self.assertEqual({kind: kinds.get(kind).draws for kind in ("lamp", "radio_set", "workbench", "lab_bench", "water_tank")},
                         {"lamp": 1, "radio_set": 1, "workbench": 2, "lab_bench": 2, "water_tank": 1})
        self.assertEqual((kinds.get("well").draws, kinds.get("pantry").draws, kinds.get("cooking_pot").draws), (0, 0, 0))
        self.assertEqual((world.registries.power.fuel, world.registries.power.fuel_lasts), (POWER_ITEM, 3780.0))

    def test_the_ready_made_settlement_has_current_for_what_it_has_and_a_little_over(self) -> None:
        world = _settled()
        self.assertEqual((world.power.supply(world), world.power.demand(world)), (16, 13))
        self.assertTrue(world.power.enough(world))
        self.assertTrue(all(placed.on for placed in world.interactables.values()))
        for object_id in ("workbench", "water_tank", "radio_set", "well", "pantry_1"):
            self.assertTrue(world.power.powered(world, object_id), object_id)

    def test_a_better_generator_gives_more(self) -> None:
        world = _settled()
        world.interactables["generator"].level = 3
        self.assertEqual(world.power.supply(world), round(16 * 1.3))

    def test_with_no_fuel_there_is_none_and_with_no_generator_nothing_that_draws_runs(self) -> None:
        world = _settled()
        _no_fuel(world)
        self.assertEqual(world.power.supply(world), 0)
        self.assertFalse(world.power.powered(world, "workbench"))
        self.assertTrue(world.power.powered(world, "well"), "which draws nothing")
        self.assertEqual(world.light_of(_lamps(world)[0]), 0)
        other = _settled()
        del other.interactables["generator"]
        del other.containers["generator"]
        other.step(5)
        self.assertFalse(other.power.powered(other, "water_tank"))
        self.assertFalse(other.has_power())

    def test_current_needs_no_pygame(self) -> None:
        check = (
            "import sys; import simulation.economy.power; from simulation.world import SimulationWorld; "
            "from simulation.commands import SwitchCommand; world = SimulationWorld.demo_world(); "
            "world.apply_command(SwitchCommand('workbench', False)); world.step(120); "
            "sys.exit(1 if 'pygame' in sys.modules else 0)"
        )
        done = subprocess.run([sys.executable, "-c", check], cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(done.returncode, 0, done.stderr)


class SwitchTests(unittest.TestCase):
    def setUp(self) -> None:
        self.world = _settled()

    def test_a_thing_is_switched_off_and_on_and_off_it_draws_nothing_and_stops(self) -> None:
        world = self.world
        lamp = _lamps(world)[0]
        lit = world.light_of(lamp)
        self.assertGreater(lit, 0)
        result = world.apply_command(SwitchCommand(lamp.object_id, False))
        self.assertTrue(result.ok)
        self.assertIn("Se apaga un farol", result.message)
        self.assertEqual((lamp.on, world.light_of(lamp), world.power.demand(world)), (False, 0, 12))
        self.assertFalse(world.power.powered(world, lamp.object_id))
        world.clock.advance_minutes(30)
        self.assertTrue(world.apply_command(SwitchCommand(lamp.object_id, True)).ok)
        self.assertEqual((lamp.on, lamp.switched_at, world.light_of(lamp)), (True, world.clock.total_minutes, lit))
        self.assertEqual(sum(f"| {SWITCHED_EVENT} |" in line for line in world.event_log), 2)

    def test_what_does_not_run_on_current_has_no_switch(self) -> None:
        for object_id in ("pantry_1", "well", "nothing"):
            result = self.world.apply_command(SwitchCommand(object_id, False))
            self.assertFalse(result.ok, object_id)
        self.assertTrue(self.world.interactables["pantry_1"].on)

    def test_when_more_is_asked_for_than_there_is_what_was_switched_on_last_goes_off(self) -> None:
        world = self.world
        lamps = _lamps(world)
        for lamp in lamps[:3]:
            world.apply_command(SwitchCommand(lamp.object_id, False))
        self.assertEqual(world.power.demand(world), 10)
        # Four more things that draw two each are put up, switched on as they stand: sixteen and two over.
        for index in range(4):
            world.interactables[f"bench_{index}"] = Interactable(f"bench_{index}", "lab_bench", 0, index)
            world.containers[f"bench_{index}"] = Inventory()
        self.assertEqual(world.power.demand(world), 18)
        world.clock.advance_minutes(10)
        first = world.apply_command(SwitchCommand(lamps[0].object_id, True))
        self.assertFalse(first.ok)
        self.assertIn("No hay corriente para un farol: se apaga", first.message)
        self.assertFalse(lamps[0].on, "it is what was switched on last")
        # There were two too many already: after it goes the last of the rest, by where it stands.
        self.assertEqual(world.power.demand(world), 16)
        self.assertFalse(world.interactables["bench_3"].on)
        self.assertTrue(world.interactables["bench_2"].on and world.interactables["workbench"].on)
        self.assertTrue(world.power.enough(world))
        self.assertTrue(any(f"| {SHED_EVENT} | No hay corriente para todo: se apaga" in line for line in world.event_log))

    def test_switches_and_what_has_been_burnt_are_saved_and_an_older_save_has_everything_on(self) -> None:
        manager = SaveManager()
        world = self.world
        lamp = _lamps(world)[0]
        world.apply_command(SwitchCommand(lamp.object_id, False))
        world.clock.advance_minutes(5)
        world.apply_command(SwitchCommand("workbench", False))
        world.apply_command(SwitchCommand("workbench", True))
        world.power_burnt = 0.4
        data = manager.to_data(world)
        loaded = manager.from_data(data)
        self.assertFalse(loaded.interactables[lamp.object_id].on)
        self.assertEqual(loaded.interactables["workbench"].switched_at, world.interactables["workbench"].switched_at)
        self.assertEqual(loaded.power_burnt, 0.4)
        for each in (world, loaded):
            each.step(6 * 60)
        self.assertEqual(manager.to_data(loaded), manager.to_data(world))
        for placed in data["interactables"]:
            del placed["on"], placed["switched_at"]
        del data["power_burnt"]
        data["version"] = 45
        older = manager.from_data(data)
        self.assertTrue(all(placed.on and placed.switched_at == 0 for placed in older.interactables.values()))
        self.assertEqual(older.power_burnt, 0.0)
        self.assertEqual(older.interactables["water_tank"].kind, "water_tank", "there is a generator: the tank is a tank")

    def test_in_an_older_save_with_no_generator_a_tank_is_a_well(self) -> None:
        manager = SaveManager()
        world = self.world
        del world.interactables["generator"]
        del world.containers["generator"]
        world.staffing.assign(world, world.residents["lucia"], "water_carrier", "water_tank")
        data = manager.to_data(world)
        data["version"] = 45
        older = manager.from_data(data)
        tank = older.interactables["water_tank"]
        self.assertEqual(tank.kind, "well")
        self.assertEqual(older.residents["lucia"].post_id, "water_tank", "it is the same thing, and still theirs")
        self.assertTrue(older.power.powered(older, "water_tank"))
        data["version"] = manager.CURRENT_VERSION
        self.assertEqual(manager.from_data(data).interactables["water_tank"].kind, "water_tank")


class StoppedTests(unittest.TestCase):
    def test_nobody_works_at_a_post_that_has_no_current(self) -> None:
        world = _settled(hour=10)
        paco = world.residents["paco"]
        self.assertTrue(_run(world, 120, lambda: world.work.on_duty(world, paco)))
        world.apply_command(SwitchCommand("workbench", False))
        world.step(1)
        self.assertFalse(world.work.on_duty(world, paco))
        self.assertIsNone(world.work.candidate(world, paco))
        self.assertEqual(paco.post_id, "workbench", "there is no other post of the workshop to go to")
        world.apply_command(SwitchCommand("workbench", True))
        self.assertTrue(_run(world, 120, lambda: world.work.on_duty(world, paco)))

    def test_whoever_draws_water_goes_to_the_well_when_the_tank_stops(self) -> None:
        world = _settled()
        lucia = world.residents["lucia"]
        world.staffing.assign(world, lucia, "water_carrier", "water_tank")
        self.assertTrue(_run(world, 120, lambda: world.work.on_duty(world, lucia)))
        self.assertEqual(lucia.activity.target_id, "water_tank")
        _no_fuel(world)
        before = world.ledger.stock(world)["water"]
        self.assertTrue(_run(world, 120, lambda: world.work.on_duty(world, lucia) and lucia.post_id == "well"), "never went")
        self.assertEqual((lucia.job_id, lucia.activity.target_id), ("water_carrier", "well"))
        _run(world, 3 * 60)
        self.assertGreater(world.ledger.stock(world)["water"], before, "and water is still drawn, by hand")

    def test_with_no_well_free_the_tank_stands_idle_and_water_is_still_drunk_from_it(self) -> None:
        world = _settled()
        lucia, nuria = world.residents["lucia"], world.residents["nuria"]
        world.staffing.assign(world, nuria, "water_carrier", "well")
        world.staffing.assign(world, lucia, "water_carrier", "water_tank")
        world.apply_command(SwitchCommand("water_tank", False))
        self.assertIsNone(world.work.candidate(world, lucia))
        self.assertEqual(lucia.post_id, "water_tank")
        ines = world.residents["ines"]
        ines.needs.thirst = 90.0
        world.put_down("ines", object_id="water_tank", do="use")
        world.step(1)
        self.assertEqual(ines.current_action, "drink_water", "what is in it is there to drink, pump or no pump")

    def test_a_radio_that_is_off_tells_nobody_anything(self) -> None:
        world = _settled(hour=9)
        sergio = world.residents["sergio"]
        world.apply_command(SwitchCommand("radio_set", False))
        world.put_down("sergio", object_id="radio_set", do="use")
        _run(world, 5)
        self.assertFalse(any(name.startswith("bulletin") and sergio.resident_id in name for name in world.notices))


class FuelTests(unittest.TestCase):
    def _alone(self, hour: int = 12) -> SimulationWorld:
        world = _settled(hour=hour)
        for resident_id in list(world.residents):
            del world.residents[resident_id]
        return world

    def test_nine_lamps_burn_a_unit_a_night_and_fewer_burn_less(self) -> None:
        burnt = {}
        for off in (0, 6):
            world = self._alone()
            for lamp in _lamps(world)[:off]:
                world.apply_command(SwitchCommand(lamp.object_id, False))
            fuel = world.ledger.stock(world)["energy"]
            world.step(6 * MINUTES_PER_DAY)
            burnt[off] = fuel - world.ledger.stock(world)["energy"]
        self.assertEqual(burnt[0], 6, "as it always was")
        self.assertEqual(burnt[6], 2, "three lamps of nine, six nights")

    def test_a_post_that_runs_on_current_burns_fuel_while_it_is_worked(self) -> None:
        world = _settled(hour=10)
        for resident_id in [each for each in world.residents if each != "paco"]:
            del world.residents[resident_id]
        for lamp in _lamps(world):
            world.apply_command(SwitchCommand(lamp.object_id, False))
        paco = world.residents["paco"]
        self.assertTrue(_run(world, 120, lambda: world.work.on_duty(world, paco)))
        before = world.power_burnt
        _run(world, 60)
        self.assertTrue(world.work.on_duty(world, paco))
        self.assertAlmostEqual(world.power_burnt - before, 60 * 2 / 3780.0, places=6)
        world.apply_command(SwitchCommand("workbench", False))
        before = world.power_burnt
        _run(world, 60)
        self.assertEqual(world.power_burnt, before, "with nothing running nothing is burnt")

    def test_when_it_runs_out_it_is_said_and_everything_that_draws_stops(self) -> None:
        world = self._alone(hour=21)
        _no_fuel(world)
        world.step(120)
        self.assertEqual(sum("power_failed | El generador se queda sin combustible" in line for line in world.event_log), 1)
        self.assertEqual(world.light_of(_lamps(world)[0]), 0)
        self.assertTrue(all(placed.on for placed in _lamps(world)), "they are still switched on, for when there is fuel")
        world.stock(world.containers["generator"], POWER_ITEM, 3, None)
        self.assertGreater(world.light_of(_lamps(world)[0]), 0)


if __name__ == "__main__":
    unittest.main()
