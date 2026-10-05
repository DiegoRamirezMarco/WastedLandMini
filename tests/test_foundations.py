import tempfile
import unittest
from pathlib import Path

from save.save_manager import SaveManager
from simulation.commands import AdvanceTimeCommand, SetPausedCommand, SetSpeedCommand
from simulation.headless import run_headless
from simulation.registries import BuiltInRegistries
from simulation.world import SimulationWorld


class FoundationTests(unittest.TestCase):
    def test_builtin_data_loads_through_registries(self) -> None:
        registries = BuiltInRegistries.load()
        self.assertEqual(registries.items.get("canned_beans").category, "food")
        self.assertGreater(registries.personalities.get("hotheaded").aggression, 70)
        self.assertEqual(registries.traits.get("music_lover")["tags"], ["music"])

    def test_commands_advance_pause_and_speed_simulation_time(self) -> None:
        world = SimulationWorld.demo_world()
        world.apply_command(SetSpeedCommand(3))
        world.apply_command(AdvanceTimeCommand())
        self.assertEqual(world.clock.minute, 3)

        world.apply_command(SetPausedCommand(True))
        world.apply_command(AdvanceTimeCommand(minutes=10))
        self.assertEqual(world.clock.minute, 3)

    def test_headless_runner_is_deterministic_for_same_seed(self) -> None:
        first = run_headless(days=1, seed=42)
        second = run_headless(days=1, seed=42)
        self.assertEqual(first, second)
        self.assertGreater(len(first), 0)

    def test_versioned_save_load_round_trip_is_equal(self) -> None:
        manager = SaveManager()
        world = SimulationWorld.demo_world(seed=99)
        world.apply_command(AdvanceTimeCommand(minutes=720))

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "save.json"
            manager.save(world, path)
            loaded = manager.load(path)

        self.assertEqual(manager.to_data(loaded), manager.to_data(world))


if __name__ == "__main__":
    unittest.main()
