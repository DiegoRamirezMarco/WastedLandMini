"""Training (S57): things to train an attribute at, told to somebody by the player, as far as
the thing is good, at the cost of time and tiredness."""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from save.save_manager import SaveManager
from simulation.ai.affect import TASK, TRAIN
from simulation.commands import AffectCommand, PutDownCommand
from simulation.registries import DATA_DIR, BuiltInRegistries
from simulation.residents.activity import Activity
from simulation.residents.attribute_system import GREW_EVENT
from simulation.residents.attributes import ATTRIBUTES, Attributes
from simulation.residents.needs import Needs
from simulation.world import SimulationWorld
from world.interactable import Interactable

ROOT = Path(__file__).resolve().parent.parent
HOUR = 60
DAY = 24 * HOUR
GYM = "gym"
ORDER = f"{TASK}:{TRAIN}"
FOR = {
    "weights": "strength", "chess_table": "mind", "target": "senses", "skipping_rope": "dexterity",
    "dummy": "charisma", "training_log": "constitution",
}


def _settled(seed: int = 7, hour: int = 9) -> SimulationWorld:
    """The settlement that comes ready made, with everyone content and in the middle of everything."""
    world = SimulationWorld.demo_world(seed=seed)
    world.relationships.clear()
    world.clock.hour, world.clock.minute = hour, 0
    for resident in world.residents.values():
        resident.attributes = Attributes()
        resident.needs = Needs(hunger=0, thirst=0, tiredness=0, social=0, stress=0)
    return world


def _stand(world: SimulationWorld, kind: str, level: int = 1, object_id: str = GYM) -> Interactable:
    """Stand a thing to train at where a heap of junk was, out in the open."""
    junk = next(placed for placed in world.interactables.values() if placed.kind == "junk")
    del world.interactables[junk.object_id]
    world.interactables[object_id] = Interactable(object_id, kind, junk.x, junk.y, level)
    return world.interactables[object_id]


def _at_it(world: SimulationWorld, resident_id: str, minutes: int = 3 * HOUR) -> bool:
    """Let time go by until a resident is at a thing to train at."""
    for _ in range(minutes):
        if world.attributes.training(world, world.residents[resident_id]) is not None:
            return True
        world.step(1)
    return False


def _registries_with(file_name: str, change) -> BuiltInRegistries:
    with tempfile.TemporaryDirectory() as folder:
        root = Path(folder)
        for path in DATA_DIR.rglob("*.json"):
            target = root / path.relative_to(DATA_DIR)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
        data = json.loads((root / file_name).read_text(encoding="utf-8"))
        change(data)
        (root / file_name).write_text(json.dumps(data), encoding="utf-8")
        return BuiltInRegistries.load(root)


class DataTests(unittest.TestCase):
    def test_each_of_the_six_has_a_thing_to_train_it_at(self) -> None:
        world = SimulationWorld.demo_world()
        kinds = world.registries.interactables
        self.assertEqual(sorted(FOR.values()), sorted(ATTRIBUTES))
        for kind, attribute in FOR.items():
            definition = kinds.get(kind)
            self.assertEqual(definition.use.trains, attribute, kind)
            self.assertEqual((definition.use.label, definition.use.action), ("Entrenar", "train"))
            self.assertGreater(definition.use.per_minute["tiredness"], 0, "it tires")
            self.assertIsNotNone(definition.build, "it is something to build")
            self.assertIn(kind, world.registries.rarities.kinds, "and to make better")
        self.assertEqual(world.registries.attributes.practice["train"], 0.0003)
        self.assertEqual((world.registries.attributes.train_cap, world.registries.attributes.train_per_level), (6.0, 1.0))
        self.assertFalse(any(placed.kind in FOR for placed in world.interactables.values()), "none comes ready made")

    def test_data_that_makes_no_sense_is_refused(self) -> None:
        def luck(data) -> None:
            data["weights"]["use"]["trains"] = "luck"

        def backwards(data) -> None:
            data["training"]["per_level"] = -1

        def unlearning(data) -> None:
            data["practice"]["train"] = -0.1

        with self.assertRaises(ValueError):
            _registries_with("interactables.json", luck)
        for change in (backwards, unlearning):
            with self.assertRaises(ValueError):
                _registries_with("attributes.json", change)

    def test_it_needs_no_pygame(self) -> None:
        code = (
            "import sys; from simulation.world import SimulationWorld; "
            "from simulation.commands import AffectCommand; from world.interactable import Interactable; "
            "world = SimulationWorld.demo_world(); world.interactables['gym'] = Interactable('gym', 'weights', 30, 20); "
            "world.apply_command(AffectCommand('raul', 'task:train', 'gym')); world.step(240); "
            "print('pygame' in sys.modules)"
        )
        result = subprocess.run([sys.executable, "-c", code], cwd=ROOT, capture_output=True, text=True, check=True)
        self.assertEqual(result.stdout.strip().splitlines()[-1], "False")


class TrainingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.world = _settled()
        self.raul = self.world.residents["raul"]

    def _train(self, kind: str = "weights", level: int = 1) -> Interactable:
        placed = _stand(self.world, kind, level)
        result = self.world.apply_command(AffectCommand("raul", ORDER, GYM))
        self.assertTrue(result.ok, result.message)
        self.assertTrue(_at_it(self.world, "raul"), "never got to it")
        return placed

    def test_told_to_somebody_goes_and_trains_and_gains_a_little_of_what_the_thing_is_for(self) -> None:
        world, raul = self.world, self.raul
        self._train()
        self.assertEqual(world.attributes.training(world, raul)[0], "strength")
        self.assertEqual(world.users_of(GYM), 1)
        tired = raul.needs.tiredness
        world.step(HOUR)
        gained = raul.attributes.strength - 5.0
        self.assertAlmostEqual(gained, 60 * 0.0003, delta=0.004)
        self.assertEqual((raul.attributes.mind, raul.attributes.dexterity), (5.0, 5.0), "and of nothing else")
        self.assertAlmostEqual(raul.needs.tiredness - tired, 60 * (0.07 + 0.03), delta=0.3)
        self.assertAlmostEqual(world.attributes.training(world, raul)[1], gained % 1.0, places=6)
        # A session is two hours, and then they go about their day.
        world.step(HOUR + 5)
        self.assertIsNone(world.attributes.training(world, raul))

    def test_each_thing_trains_what_it_is_for_and_the_dummy_what_is_kept_with_how_they_are(self) -> None:
        world, raul = self.world, self.raul
        before = world.attributes.raw(world, raul, "charisma")
        self._train("dummy")
        world.step(HOUR)
        self.assertGreater(world.attributes.raw(world, raul, "charisma"), before)
        self.assertEqual(raul.attributes, Attributes(), "none of the five kept with them moved")

    def test_nobody_trains_unasked(self) -> None:
        world = self.world
        for index, kind in enumerate(FOR):
            _stand(world, kind, object_id=f"gym_{index}")
        gyms = {f"gym_{index}" for index in range(len(FOR))}
        passed = set()
        for _ in range(2 * DAY):
            world.step(1)
            # Whoever is at one of them is passing the time there (S60), which trains nothing.
            self.assertFalse(any(world.attributes.training(world, each) for each in world.residents.values()), world.clock.label)
            passed |= {
                each.activity.action for each in world.residents.values() if each.activity is not None and each.activity.target_id in gyms
            }
        self.assertNotIn("train", passed)

    def test_whoever_passes_the_time_at_one_of_them_trains_nothing(self) -> None:
        world, raul = self.world, self.raul
        target = _stand(world, "target", object_id="gym_target")
        self.assertIsNotNone(world.definition_of(target).use_named("darts"))
        aim = world.attributes.trains(world, target)
        before = world.attributes.raw(world, raul, aim)
        raul.activity = Activity("darts", target.object_id, minutes_left=20, using=True)
        self.assertIsNone(world.attributes.training(world, raul))
        for _ in range(10):
            world.step(1)
            raul.needs.hunger = raul.needs.thirst = 0.0
        self.assertEqual(raul.activity.action, "darts")
        self.assertEqual(world.attributes.raw(world, raul, aim), before)
        raul.activity = Activity("train", target.object_id, minutes_left=20, using=True)
        self.assertEqual(world.attributes.training(world, raul)[0], aim)

    def test_a_thing_takes_an_attribute_as_far_as_it_is_good_and_no_further(self) -> None:
        world, raul = self.world, self.raul
        caps = [world.attributes.train_cap(world, Interactable("x", "weights", 0, 0, level)) for level in range(1, 7)]
        self.assertEqual(caps, [6.0, 7.0, 8.0, 9.0, 10.0, 10.0])
        raul.attributes.strength = 5.9995
        world.events.drain()
        placed = self._train()
        for _ in range(30):
            if world.attributes.training(world, raul) is None:
                break
            world.step(1)
        self.assertIsNone(world.attributes.training(world, raul), "with nothing left to learn there they leave it")
        self.assertEqual(raul.attributes.strength, 6.0)
        grew = [event for event in world.events.drain() if event.event_type == GREW_EVENT]
        self.assertEqual([(event.data["attribute"], event.data["level"]) for event in grew], [("strength", 6)])
        # It has no more to teach them: told again, it is said why not, and it is no longer offered.
        result = world.apply_command(AffectCommand("raul", ORDER, GYM))
        self.assertFalse(result.ok)
        self.assertIn("ya no aprende más", result.message)
        self.assertNotIn(ORDER, [option.kind for option in world.affect_options("raul")])
        # Made better, it has.
        placed.level = 2
        self.assertTrue(world.attributes.learns_at(world, raul, placed))
        self.assertTrue(world.apply_command(AffectCommand("raul", ORDER, GYM)).ok)
        # And somebody who has less to begin with still has it all to gain at the common one.
        placed.level = 1
        self.assertTrue(world.attributes.learns_at(world, world.residents["ines"], placed))

    def test_it_is_offered_only_while_there_is_something_to_train_at(self) -> None:
        world = self.world
        self.assertNotIn(ORDER, [option.kind for option in world.affect_options("raul")])
        _stand(world, "target")
        option = next(option for option in world.affect_options("raul") if option.kind == ORDER)
        self.assertEqual([each for each, _said in option.targets], [GYM])
        self.assertIn("diana (sentidos), a ", option.targets[0][1])
        self.assertEqual(option.said(GYM).split(",")[0], "Que entrene en diana (sentidos)")
        # A thing that is used but trains nothing cannot be trained at.
        result = world.apply_command(AffectCommand("raul", ORDER, "pantry_1"))
        self.assertFalse(result.ok)

    def test_putting_somebody_down_on_it_has_them_train(self) -> None:
        world, raul = self.world, self.raul
        _stand(world, "skipping_rope")
        offered = world.placements("raul", object_id=GYM)
        self.assertTrue(offered, "nothing comes of putting them down there")
        self.assertEqual(offered[0].kind, "use")
        result = world.apply_command(PutDownCommand("raul", object_id=GYM))
        self.assertTrue(result.ok, result.message)
        self.assertTrue(_at_it(world, "raul", 10))
        world.step(30)
        self.assertGreater(raul.attributes.dexterity, 5.0)

    def test_a_need_of_the_body_that_cannot_wait_ends_it(self) -> None:
        world, raul = self.world, self.raul
        self._train()
        raul.needs.thirst = 99.0
        world.step(3)
        self.assertIsNone(world.attributes.training(world, raul))

    def test_one_at_a_time_at_each_thing(self) -> None:
        world = self.world
        self._train()
        result = world.apply_command(AffectCommand("ines", ORDER, GYM))
        self.assertFalse(result.ok, "somebody is at it already")

    def test_what_is_being_trained_is_saved_and_goes_on_the_same(self) -> None:
        manager = SaveManager()
        world = self.world
        self._train("training_log")
        world.step(20)
        loaded = manager.from_data(manager.to_data(world))
        self.assertEqual(loaded.attributes.training(loaded, loaded.residents["raul"])[0], "constitution")
        for each in (world, loaded):
            each.step(3 * HOUR)
        self.assertEqual(manager.to_data(loaded), manager.to_data(world))
        self.assertGreater(loaded.residents["raul"].attributes.constitution, 5.0)


if __name__ == "__main__":
    unittest.main()
