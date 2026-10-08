"""Posts that wear and break down, and are mended (S55)."""

import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from save.save_manager import SaveManager
from simulation.commands import AffectCommand, ProposeUpgradeCommand
from simulation.registries import DATA_DIR, BuiltInRegistries
from simulation.residents.attributes import Attributes
from simulation.residents.needs import Needs
from simulation.work.rush import BREAKDOWN
from simulation.work.wear import BROKE_EVENT, MENDED_EVENT, NOT_BROKEN
from simulation.world import SimulationWorld
from world.build import REPAIR_SITE

MINUTES_PER_DAY = 24 * 60


def _keep_content(world: SimulationWorld, *spared: str) -> None:
    for resident_id, resident in world.residents.items():
        if resident_id not in spared:
            resident.needs = Needs(hunger=0, thirst=0, tiredness=0, social=0, stress=0)


def _settled(seed: int = 7, hour: int = 8) -> SimulationWorld:
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


def _count(world: SimulationWorld, event_type: str) -> int:
    return sum(f"| {event_type} |" in line for line in world.event_log)


class WearingTests(unittest.TestCase):
    def test_how_a_post_wears_and_what_mending_takes_are_data(self) -> None:
        world = _settled()
        wear = world.registries.wear
        self.assertEqual((wear.per_hour, wear.pushed, wear.cost, wear.minutes, wear.job), (0.25, 2.0, {"scrap": 2}, 120, "mechanic"))
        self.assertIn(BREAKDOWN, world.registries.rush.mishaps)
        self.assertTrue(all(placed.condition == 100.0 for placed in world.interactables.values()))
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            for path in DATA_DIR.rglob("*.json"):
                target = root / path.relative_to(DATA_DIR)
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
            data = json.loads((root / "work.json").read_text(encoding="utf-8"))
            data["wear"]["job"] = "tinker"
            (root / "work.json").write_text(json.dumps(data), encoding="utf-8")
            with self.assertRaises(ValueError):
                BuiltInRegistries.load(root)

    def test_a_post_is_the_worse_for_every_hour_it_is_worked_and_no_other_is(self) -> None:
        world = _settled()
        raul = world.residents["raul"]
        self.assertTrue(_run(world, 120, lambda: world.work.on_duty(world, raul)))
        crop = world.interactables["crop_1"]
        before = crop.condition
        _run(world, 60)
        self.assertTrue(world.work.on_duty(world, raul))
        self.assertAlmostEqual(before - crop.condition, 0.25, places=6)
        self.assertEqual(world.interactables["crop_2"].condition, 100.0, "which nobody works")
        self.assertEqual(world.interactables["bed_1"].condition, 100.0, "nor does a bed wear")
        self.assertTrue(world.wear.wears(world, crop))
        self.assertFalse(world.wear.wears(world, world.interactables["bed_1"]))

    def test_pushed_it_wears_twice_as_fast(self) -> None:
        world = _settled()
        ines = world.residents["ines"]
        self.assertTrue(_run(world, 120, lambda: world.work.on_duty(world, ines)))
        self.assertTrue(world.apply_command(AffectCommand("ines", "task:push")).ok)
        # No push ends badly here: only how fast the post wears is looked at.
        world.registries = replace(world.registries, rush=replace(world.registries.rush, risk=0.0))
        crop = world.interactables["crop_5"]
        before = crop.condition
        for _ in range(60):
            world.step(1)
            _keep_content(world)
        self.assertTrue(world.rush.pushed(world, ines))
        self.assertAlmostEqual(before - crop.condition, 0.5, places=6)

    def test_with_no_wear_in_the_data_nothing_wears(self) -> None:
        world = _settled()
        world.registries = replace(world.registries, wear=replace(world.registries.wear, per_hour=0.0))
        _run(world, 6 * 60)
        self.assertTrue(all(placed.condition == 100.0 for placed in world.interactables.values()))


class BreakingDownTests(unittest.TestCase):
    def setUp(self) -> None:
        self.world = _settled()
        self.raul, self.paco = self.world.residents["raul"], self.world.residents["paco"]
        self.crop = self.world.interactables["crop_1"]

    def _wear_out(self) -> None:
        self.assertTrue(_run(self.world, 120, lambda: self.world.work.on_duty(self.world, self.raul)))
        self.crop.condition = 0.004
        self.world.step(1)

    def test_worn_out_it_breaks_down_and_nobody_works_at_it(self) -> None:
        world = self.world
        self._wear_out()
        self.assertEqual(self.crop.condition, 0.0)
        self.assertTrue(world.wear.broken(world, "crop_1"))
        self.assertFalse(world.work.on_duty(world, self.raul))
        self.assertIsNone(world.work.candidate(world, self.raul))
        self.assertEqual(_count(world, BROKE_EVENT), 1)
        self.assertIn("Se avería un bancal: hay que arreglarlo", "\n".join(world.event_log))
        site = world.wear.site_of(world, "crop_1")
        self.assertEqual((site.kind, site.in_charge, site.tiles), (REPAIR_SITE, "paco", [(self.crop.x, self.crop.y)]))
        self.assertEqual(world.construction.thing(world, site.kind, site.what), "arreglar un bancal")
        rule = world.construction.rule_of(world, site)
        self.assertEqual((rule.cost, rule.minutes, rule.job), ({"scrap": 2}, 120, "mechanic"))

    def test_the_mechanic_mends_it_with_scrap_and_it_is_as_good_as_new(self) -> None:
        world = self.world
        scrap = world.ledger.stock(world)["scrap"]
        self._wear_out()
        self.assertTrue(_run(world, MINUTES_PER_DAY, lambda: not world.wear.broken(world, "crop_1")), "never mended")
        self.assertEqual(world.sites, {})
        self.assertGreater(self.crop.condition, 99.0)
        self.assertEqual(world.ledger.stock(world)["scrap"], scrap - 2)
        self.assertEqual(_count(world, MENDED_EVENT), 1)
        self.assertIn("site_finished | Obra terminada: arreglar un bancal", "\n".join(world.event_log))
        self.assertTrue(_run(world, MINUTES_PER_DAY, lambda: world.work.on_duty(world, self.raul)), "and it is worked again")

    def test_what_has_broken_down_is_not_used_either(self) -> None:
        world = self.world
        pot = world.interactables["cooking_pot"]
        ines = world.residents["ines"]
        self.assertTrue(world.activities.routine.open_for(world, ines, pot))
        world.wear.break_down(world, pot)
        self.assertFalse(world.activities.routine.open_for(world, ines, pot))
        self.assertEqual(world.upgrades.obstacle(world, "cooking_pot"), "Antes hay que arreglarlo")
        world.studies.known.append("fine_work")
        self.assertFalse(world.apply_command(ProposeUpgradeCommand("cooking_pot", "marta")).ok)
        self.assertEqual(world.wear.obstacle(world, "crop_2"), NOT_BROKEN)

    def test_with_nobody_to_mend_it_it_waits_and_is_theirs_when_somebody_is(self) -> None:
        world = self.world
        self.paco.job_id = self.paco.post_id = None
        world.wear.break_down(world, self.crop)
        site = world.wear.site_of(world, "crop_1")
        self.assertIsNone(site.in_charge)
        _run(world, 4 * 60)
        self.assertTrue(world.wear.broken(world, "crop_1"), "nobody else mends what the mechanic mends")
        self.assertTrue(world.staffing.assign(world, world.residents["nuria"], "mechanic"))
        _run(world, 61)
        self.assertEqual(site.in_charge, "nuria")
        self.assertTrue(_run(world, MINUTES_PER_DAY, lambda: not world.wear.broken(world, "crop_1")))

    def test_a_push_that_goes_wrong_may_break_the_post(self) -> None:
        world = self.world
        rush = world.registries.rush
        only = {BREAKDOWN: rush.mishaps[BREAKDOWN]}
        world.registries = replace(world.registries, rush=replace(rush, risk=1.0, tired_risk=1.0, mishaps=only))
        ines = world.residents["ines"]
        self.assertTrue(_run(world, 120, lambda: world.work.on_duty(world, ines)))
        self.assertTrue(world.apply_command(AffectCommand("ines", "task:push")).ok)
        self.assertTrue(_run(world, 4 * 60, lambda: world.wear.broken(world, "crop_5")), "it never gave out")
        self.assertFalse(world.rush.pushed(world, ines), "whatever goes wrong ends the push")
        log = "\n".join(world.event_log)
        self.assertIn("work_accident | El puesto de Inés se avería de tanto apretar: Huerto", log)
        self.assertIn(f"{BROKE_EVENT} | Se avería un bancal", log)
        self.assertIsNotNone(world.wear.site_of(world, "crop_5"))

    def test_how_worn_a_post_is_and_the_mending_of_it_are_saved(self) -> None:
        manager = SaveManager()
        world = self.world
        world.interactables["crop_3"].condition = 37.5
        world.wear.break_down(world, self.crop)
        world.step(20)
        data = manager.to_data(world)
        loaded = manager.from_data(data)
        self.assertEqual(loaded.interactables["crop_3"].condition, 37.5)
        self.assertTrue(loaded.wear.broken(loaded, "crop_1"))
        self.assertEqual(loaded.wear.site_of(loaded, "crop_1").in_charge, "paco")
        for each in (world, loaded):
            each.step(8 * 60)
        self.assertEqual(manager.to_data(loaded), manager.to_data(world))
        for placed in data["interactables"]:
            del placed["condition"]
        data["sites"] = []
        data["version"] = 46
        older = manager.from_data(data)
        self.assertTrue(all(placed.condition == 100.0 for placed in older.interactables.values()))


if __name__ == "__main__":
    unittest.main()
