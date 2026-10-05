import json
import shutil
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from save.save_manager import SaveManager
from simulation.health.injury import Injury, injury_definition_from_data, limb_definition_from_data
from simulation.registries import DATA_DIR, BuiltInRegistries
from simulation.residents.activity import MOVE_TILES_PER_MINUTE, Activity
from simulation.residents.needs import Needs
from simulation.work.expedition import Expedition
from simulation.world import SimulationWorld

BAD_CUT = 30.0


def _world(chance: float | None = 1.0, seed: int = 7) -> SimulationWorld:
    """A quiet settlement. With `chance`, that is how likely a bad cut is to take a limb off."""
    world = SimulationWorld.demo_world(seed=seed)
    world.relationships.clear()
    for resident in world.residents.values():
        resident.needs = Needs(hunger=0, tiredness=0, social=0, stress=0)
    if chance is not None:
        injuries = dict(world.registries.injuries)
        injuries["cut"] = replace(injuries["cut"], severs_chance=chance)
        # The built-in definitions are shared: a world with other odds gets a registry of its own.
        world.registries = replace(world.registries, injuries=injuries)
    return world


class LimbLossTests(unittest.TestCase):
    def test_built_in_cuts_can_take_a_limb_and_every_limb_slows_something_down(self) -> None:
        registries = SimulationWorld.demo_world().registries
        cut = registries.injuries["cut"]
        self.assertIsNotNone(cut.severs_from)
        self.assertTrue(0.0 < cut.severs_chance < 1.0)
        self.assertIsNone(registries.injuries["bruise"].severs_from)
        self.assertEqual(len(registries.limbs), 4)
        for limb in registries.limbs.values():
            self.assertLess(min(limb.work_pace, limb.walk_pace), 1.0, limb.limb_id)

    def test_a_bad_cut_takes_a_limb_off_and_says_so(self) -> None:
        world = _world()
        raul, tomas = world.residents["raul"], world.residents["tomas"]
        self.assertTrue(world.health.hurt(world, raul, BAD_CUT, "cut", "una pelea con Tomás", tomas))
        self.assertEqual(len(raul.lost_limbs), 1)
        limb = world.registries.limbs[raul.lost_limbs[0]]
        event = world.history[-1]
        self.assertEqual(event.event_type, "limb_lost")
        self.assertEqual(event.participants, ["raul"])
        self.assertEqual(event.text, f"Raúl pierde {limb.name} en una pelea con Tomás")
        self.assertEqual(event.data["limb"], limb.limb_id)
        self.assertEqual(event.data["by"], "tomas")
        self.assertEqual(event.data["amount"], BAD_CUT)
        # The wound is there as well, and mends. The limb does not come back.
        self.assertEqual(raul.injuries, [Injury("cut", BAD_CUT)])
        world.step(30 * 24 * 60)
        self.assertEqual(world.residents["raul"].injuries, [])
        self.assertEqual(world.residents["raul"].lost_limbs, [limb.limb_id])

    def test_a_lesser_cut_or_a_blow_that_does_not_cut_takes_nothing(self) -> None:
        world = _world()
        raul = world.residents["raul"]
        state = world.rng.get_state()
        world.health.hurt(world, raul, world.registries.injuries["cut"].severs_from - 1, "cut", "una prueba")
        world.health.hurt(world, raul, BAD_CUT, "fracture", "una prueba")
        self.assertEqual(raul.lost_limbs, [])
        self.assertEqual([event.event_type for event in world.history[-2:]], ["injured", "injured"])
        self.assertEqual(world.history[-1].data, {"amount": BAD_CUT, "kind": "fracture", "by": None})
        self.assertEqual(world.rng.get_state(), state, "no dice are rolled unless a limb is at stake")

    def test_luck_decides_and_the_same_seed_decides_the_same(self) -> None:
        def losses(seed: int) -> list[str]:
            world = _world(chance=None, seed=seed)
            for resident in world.residents.values():
                world.health.hurt(world, resident, BAD_CUT, "cut", "una prueba")
            return [limb for resident in world.residents.values() for limb in resident.lost_limbs]

        self.assertEqual(losses(3), losses(3))
        self.assertTrue(0 < len(losses(3)) < len(SimulationWorld.demo_world().residents))

    def test_no_limb_is_lost_twice_and_none_is_left_to_lose_after_four(self) -> None:
        world = _world()
        raul = world.residents["raul"]
        for _ in range(6):
            raul.injuries.clear()
            world.health.hurt(world, raul, BAD_CUT, "cut", "una prueba")
        self.assertEqual(sorted(raul.lost_limbs), sorted(world.registries.limbs))
        self.assertEqual(world.history[-1].event_type, "injured")

    def test_those_who_saw_it_know_and_the_others_do_not(self) -> None:
        world = _world()
        raul, tomas, vera = (world.residents[name] for name in ("raul", "tomas", "vera"))
        (raul.x, raul.y), (tomas.x, tomas.y), (vera.x, vera.y) = (20, 14), (21, 14), (1, 1)
        world.health.hurt(world, raul, BAD_CUT, "cut", "una pelea con Tomás", tomas)
        fact = next(fact for fact in world.knowledge.facts.values() if fact.event_type == "limb_lost")
        self.assertIn("perdió", fact.text)
        self.assertTrue(world.knowledge.knows("raul", fact.fact_id))
        self.assertTrue(world.knowledge.knows("tomas", fact.fact_id))
        self.assertFalse(world.knowledge.knows("vera", fact.fact_id))

    def test_a_blow_that_kills_takes_no_limb_and_says_where_the_body_fell(self) -> None:
        world = _world()
        raul, tomas = world.residents["raul"], world.residents["tomas"]
        raul.lost_limbs = ["arm_left"]
        raul.injuries = [Injury("cut", 90)]
        self.assertFalse(world.health.hurt(world, raul, BAD_CUT, "cut", "una pelea con Tomás", tomas))
        death = world.history[-1]
        self.assertEqual(death.event_type, "death")
        self.assertEqual(
            death.data, {"resident_id": "raul", "tile": [raul.x, raul.y], "by": "tomas", "lost_limbs": ["arm_left"]}
        )

    def test_whoever_dies_beyond_the_fence_leaves_no_body_on_the_map(self) -> None:
        world = _world()
        sergio = world.residents["sergio"]
        sergio.expedition = Expedition(returns_at=world.clock.total_minutes + 60, finds=0, danger=0.0)
        world.health.die(world, sergio, "una prueba")
        self.assertIsNone(world.history[-1].data["tile"])


class LimbConsequenceTests(unittest.TestCase):
    def test_short_of_a_leg_a_resident_covers_half_the_ground(self) -> None:
        world = _world()
        raul = world.residents["raul"]
        self.assertEqual(world.health.walk_tiles(world, raul), MOVE_TILES_PER_MINUTE)
        raul.lost_limbs = ["leg_left"]
        self.assertEqual(world.health.walk_tiles(world, raul), 1)
        raul.lost_limbs = ["leg_left", "leg_right"]
        self.assertEqual(world.health.walk_tiles(world, raul), 1, "they still get there")
        start = raul.tile
        raul.activity = Activity("wander", path=[(start[0] + 1, start[1]), (start[0] + 2, start[1])], minutes_left=1)
        world.activities.tick(world, raul)
        self.assertEqual(raul.tile, (start[0] + 1, start[1]))
        self.assertEqual(len(raul.trail), 2)

    def test_short_of_an_arm_the_same_work_takes_longer(self) -> None:
        def minutes_to_grow(lost: list[str]) -> int:
            world = _world()
            raul = world.residents["raul"]
            raul.lost_limbs = lost
            job = world.work.job_of(world, raul)
            self.assertIsNone(job.produces.source, "the farmer needs nothing fetched to get on with it")
            plot = world.interactables[raul.post_id]
            holder = world.containers[plot.object_id] if job.produces.into == "station" else raul.inventory
            before = holder.count(job.produces.item)
            for minute in range(1, 600):
                world.work._produce(world, raul, job, plot, shift_left=600)
                if holder.count(job.produces.item) > before:
                    return minute
            raise AssertionError("nothing was grown")

        whole, one_armed = minutes_to_grow([]), minutes_to_grow(["arm_left"])
        self.assertGreater(one_armed, whole)
        self.assertAlmostEqual(one_armed / whole, 1 / 0.6, delta=0.2)
        world = _world()
        self.assertEqual(world.health.work_pace(world, world.residents["marta"]), 1.0)

    def test_a_week_goes_by_with_someone_maimed_and_the_settlement_holds(self) -> None:
        world = _world(chance=None)
        world.residents["raul"].lost_limbs = ["arm_right", "leg_left"]
        world.step(7 * 24 * 60)
        self.assertIn("raul", world.residents)
        self.assertLess(max(vars(world.residents["raul"].needs).values()), 100.0, "he still looks after himself")
        self.assertEqual(world.residents["raul"].lost_limbs, ["arm_right", "leg_left"])


class LimbDataTests(unittest.TestCase):
    def test_bad_limb_and_injury_data_is_refused(self) -> None:
        with self.assertRaises(ValueError):
            limb_definition_from_data("tail", {"work_pace": 0.5})
        with self.assertRaises(ValueError):
            limb_definition_from_data("tail", {"name": "la cola", "walk_pace": 0})
        with self.assertRaises(ValueError):
            injury_definition_from_data("bite", {"name": "un mordisco", "heal_per_day": 5, "severs_chance": 2})
        plain = injury_definition_from_data("bite", {"name": "un mordisco", "heal_per_day": 5})
        self.assertIsNone(plain.severs_from)

    def test_without_a_body_file_nobody_can_lose_anything(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            shutil.copytree(DATA_DIR, Path(tmp) / "data")
            (Path(tmp) / "data" / "body.json").unlink()
            registries = BuiltInRegistries.load(Path(tmp) / "data")
        self.assertEqual(registries.limbs, {})
        world = SimulationWorld.demo_world(registries=registries)
        world.health.hurt(world, world.residents["raul"], BAD_CUT, "cut", "una prueba")
        self.assertEqual(world.residents["raul"].lost_limbs, [])


class LimbSaveTests(unittest.TestCase):
    def setUp(self) -> None:
        self.manager = SaveManager()

    def test_lost_limbs_and_what_events_say_survive_saving(self) -> None:
        world = _world(chance=None)
        raul, tomas = world.residents["raul"], world.residents["tomas"]
        raul.lost_limbs = ["leg_right"]
        world.health.hurt(world, raul, 12, "bruise", "una pelea con Tomás", tomas)
        data = json.loads(json.dumps(self.manager.to_data(world)))
        self.assertEqual(data["version"], SaveManager.CURRENT_VERSION)
        loaded = self.manager.from_data(data)
        self.assertEqual(loaded.residents["raul"].lost_limbs, ["leg_right"])
        self.assertEqual(loaded.history[-1].data, {"amount": 12, "kind": "bruise", "by": "tomas"})
        self.assertEqual(self.manager.to_data(loaded), self.manager.to_data(world))
        world.step(24 * 60)
        loaded.step(24 * 60)
        self.assertEqual(self.manager.to_data(loaded), self.manager.to_data(world))

    def test_an_older_save_loads_with_everyone_whole(self) -> None:
        data = self.manager.to_data(_world(chance=None))
        data["version"] = 14
        for resident in data["residents"]:
            del resident["lost_limbs"]
        for event in data["history"]:
            event.pop("data", None)
        loaded = self.manager.from_data(json.loads(json.dumps(data)))
        self.assertTrue(all(resident.lost_limbs == [] for resident in loaded.residents.values()))
        self.assertTrue(all(event.data == {} for event in loaded.history))

    def test_a_limb_that_is_no_longer_defined_or_is_listed_twice_is_dropped(self) -> None:
        data = self.manager.to_data(_world(chance=None))
        data["residents"][0]["lost_limbs"] = ["tail", "arm_left", "arm_left"]
        data["residents"][1]["lost_limbs"] = "arm_left"
        loaded = self.manager.from_data(json.loads(json.dumps(data)))
        self.assertEqual(loaded.residents[data["residents"][0]["id"]].lost_limbs, ["arm_left"])
        self.assertEqual(loaded.residents[data["residents"][1]["id"]].lost_limbs, [])


if __name__ == "__main__":
    unittest.main()
