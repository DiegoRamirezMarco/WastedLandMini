"""The well (S55): a second kind of post for drawing water, worked by hand and slower."""

import json
import tempfile
import unittest
from pathlib import Path

from save.save_manager import SaveManager
from simulation.ai.placing import POST, SWAP
from simulation.registries import DATA_DIR, BuiltInRegistries
from simulation.residents.attributes import Attributes
from simulation.residents.needs import Needs
from simulation.world import SimulationWorld

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


class WellTests(unittest.TestCase):
    def test_a_job_may_have_more_than_one_kind_of_post(self) -> None:
        world = _settled()
        job = world.registries.jobs["water_carrier"]
        self.assertEqual(job.stations, ("water_tank", "well"))
        self.assertTrue(job.works_at("well") and job.works_at("water_tank"))
        self.assertFalse(job.works_at("pantry"))
        self.assertEqual(world.registries.jobs["farmer"].stations, ("crop_bed",))
        self.assertIs(world.staffing.job_at(world, "well"), job)
        self.assertIs(world.staffing.job_at(world, "water_tank"), job)

    def test_a_post_of_a_kind_there_is_not_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            for path in DATA_DIR.rglob("*.json"):
                target = root / path.relative_to(DATA_DIR)
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
            data = json.loads((root / "jobs.json").read_text(encoding="utf-8"))
            data["water_carrier"]["also_at"] = ["spring"]
            (root / "jobs.json").write_text(json.dumps(data), encoding="utf-8")
            with self.assertRaises(ValueError):
                BuiltInRegistries.load(root)

    def test_two_can_draw_water_one_at_the_tank_and_one_at_the_well(self) -> None:
        world = _settled()
        lucia, nuria = world.residents["lucia"], world.residents["nuria"]
        self.assertTrue(world.staffing.assign(world, lucia, "water_carrier"))
        self.assertTrue(world.staffing.assign(world, nuria, "water_carrier"))
        self.assertEqual({lucia.post_id, nuria.post_id}, {"water_tank", "well"})
        self.assertFalse(world.staffing.assign(world, world.residents["paco"], "water_carrier"), "there are no more posts")
        before = world.ledger.stock(world)["water"]
        self.assertTrue(_run(world, 180, lambda: all(world.work.on_duty(world, each) for each in (lucia, nuria))))
        _run(world, 4 * 60)
        self.assertGreater(world.ledger.stock(world)["water"], before + 8)

    def test_a_well_is_drawn_from_more_slowly_than_a_tank(self) -> None:
        world = _settled()
        lucia, nuria = world.residents["lucia"], world.residents["nuria"]
        job = world.registries.jobs["water_carrier"]
        world.staffing.assign(world, lucia, "water_carrier", "water_tank")
        world.staffing.assign(world, nuria, "water_carrier", "well")
        self.assertEqual(world.registries.interactables.get("well").post_pace, 0.6)
        self.assertAlmostEqual(world.work.pace(world, nuria, job), world.work.pace(world, lucia, job) * 0.6)

    def test_what_is_drawn_at_the_well_is_drunk_there_and_kept_in_the_store(self) -> None:
        world = _settled()
        nuria = world.residents["nuria"]
        well = world.containers["well"]
        world.staffing.assign(world, nuria, "water_carrier", "well")
        world.step(1)
        self.assertEqual(well.count("water"), 20, "a little is kept at hand there, as at the tank")
        store = world.containers["warehouse"]
        in_store = store.count("water")
        self.assertTrue(_run(world, 180, lambda: world.work.on_duty(world, nuria)))
        _run(world, 4 * 60)
        self.assertGreater(store.count("water"), in_store)
        ines = world.residents["ines"]
        ines.needs.thirst = 90.0
        self.assertEqual(world.placements("ines", object_id="well")[0].kind, SWAP, "a post first, as the tank is, and Nuria has it")
        world.put_down("ines", object_id="well", do="use")
        world.step(1)
        self.assertEqual(ines.current_action, "drink_water")

    def test_it_is_a_post_like_any_other(self) -> None:
        world = _settled()
        well = world.interactables["well"]
        self.assertTrue(world.upgrades.can_be_bettered(world, well))
        found = world.placements("paco", object_id="well")
        self.assertEqual((found[0].kind, found[0].job_id), (POST, "water_carrier"))
        self.assertIsNotNone(world.registries.interactables.get("well").build)

    def test_a_new_settlement_is_asked_for_a_well_and_not_a_tank(self) -> None:
        tutorial = json.loads((DATA_DIR / "tutorial.json").read_text(encoding="utf-8"))
        steps = tutorial["steps"] if isinstance(tutorial, dict) and "steps" in tutorial else tutorial
        water = next(step for step in steps if step.get("id") == "water")
        self.assertEqual(water["goal"]["target"], "well")
        self.assertEqual([gift["into"] for gift in water["gifts"]], ["well"])
        self.assertIn("pozo", water["text"])

    def test_a_save_of_the_ready_made_settlement_from_before_gains_its_well(self) -> None:
        manager = SaveManager()
        world = SimulationWorld.demo_world(seed=11)
        del world.interactables["well"]
        del world.containers["well"]
        data = manager.to_data(world)
        data["version"] = 44
        loaded = manager.from_data(data)
        self.assertEqual(loaded.interactables["well"].kind, "well")
        self.assertIn("well", loaded.containers)
        data["version"] = manager.CURRENT_VERSION
        self.assertNotIn("well", manager.from_data(data).interactables, "whoever took theirs down keeps it down")


if __name__ == "__main__":
    unittest.main()
