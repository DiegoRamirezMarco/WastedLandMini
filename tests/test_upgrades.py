"""Better things (S54): what stands has a level, which is a rarity, and is made better as a
site on it, once that rarity has been studied."""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from save.save_manager import SaveManager
from simulation.commands import ProposeUpgradeCommand
from simulation.registries import DATA_DIR, BuiltInRegistries
from simulation.residents.attributes import Attributes
from simulation.residents.needs import Needs
from simulation.work.upgrades import IN_HAND, NOT_THAT, UPGRADED_EVENT
from simulation.world import SimulationWorld
from world.build import UPGRADE_SITE

ROOT = Path(__file__).resolve().parent.parent
MINUTES_PER_DAY = 24 * 60
STUDIES = ("fine_work", "skilled_work", "master_work", "great_work")


def _keep_content(world: SimulationWorld) -> None:
    for resident in world.residents.values():
        resident.needs = Needs(hunger=0, thirst=0, tiredness=0, social=0, stress=0)


def _settled(seed: int = 7, hour: int = 8, known: int = 1) -> SimulationWorld:
    """The settlement that comes ready made, with everyone content, and so many of the
    rarities studied already."""
    world = SimulationWorld.demo_world(seed=seed)
    world.relationships.clear()
    world.clock.hour, world.clock.minute = hour, 0
    for resident in world.residents.values():
        resident.attributes = Attributes()
    world.studies.known.extend(STUDIES[:known])
    _keep_content(world)
    return world


def _run(world: SimulationWorld, minutes: int, until=None) -> bool:
    for _ in range(minutes):
        world.step(1)
        _keep_content(world)
        if until is not None and until():
            return True
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


class RarityTests(unittest.TestCase):
    def test_the_rarities_are_data_from_the_commonest_to_what_is_only_found(self) -> None:
        settings = SimulationWorld.demo_world().registries.rarities
        self.assertEqual(
            [each.name for each in settings.tiers], ["Común", "Poco común", "Raro", "Épico", "Legendario", "Mítico"]
        )
        self.assertEqual([each.built for each in settings.tiers], [True] * 5 + [False])
        self.assertEqual([each.study for each in settings.tiers], [None, *STUDIES, None])
        betters = [each.better for each in settings.tiers]
        self.assertEqual(betters[0], 1.0)
        self.assertEqual(betters, sorted(betters))
        self.assertEqual(len({each.color for each in settings.tiers}), 6, "each has a colour of its own")
        self.assertEqual((settings.of(1).rarity_id, settings.of(6).rarity_id, settings.of(99).rarity_id), ("common", "mythic", "mythic"))

        def gentler(data) -> None:
            data["tiers"]["rare"]["better"] = 1.2
            data["upgrade"]["cost"] = {"scrap": 1}

        changed = _registries_with("rarities.json", gentler).rarities
        self.assertEqual((changed.of(3).better, changed.cost), (1.2, {"scrap": 1}))

    def test_rarities_that_make_no_sense_are_refused(self) -> None:
        def unknown_study(data) -> None:
            data["tiers"]["rare"]["study"] = "alchemy"

        def out_of_order(data) -> None:
            data["tiers"]["rare"]["better"] = 1.01

        def unknown_kind(data) -> None:
            data["upgrade"]["kinds"] = ["throne"]

        for change in (unknown_study, out_of_order, unknown_kind):
            with self.subTest(change=change.__name__), self.assertRaises(ValueError):
                _registries_with("rarities.json", change)

    def test_a_post_a_store_a_bed_and_the_generator_have_levels_and_nothing_else_has(self) -> None:
        world = _settled()
        can = lambda object_id: world.upgrades.can_be_bettered(world, world.interactables[object_id])  # noqa: E731
        for object_id in ("crop_1", "cooking_pot", "water_tank", "workbench", "warehouse", "bed_1", "generator"):
            self.assertTrue(can(object_id), object_id)
        for object_id in ("table", "crate_1", "pantry_1", "lamp_shop", "stool_1", "wreck_yard"):
            self.assertFalse(can(object_id), object_id)
            self.assertEqual(world.upgrades.obstacle(world, object_id), NOT_THAT)
        self.assertTrue(all(placed.level == 1 for placed in world.interactables.values()), "everything starts common")

    def test_making_things_better_needs_no_pygame(self) -> None:
        check = (
            "import sys; import simulation.work.upgrades; from simulation.world import SimulationWorld; "
            "from simulation.commands import ProposeUpgradeCommand; world = SimulationWorld.demo_world(); "
            "world.studies.known.append('fine_work'); world.apply_command(ProposeUpgradeCommand('warehouse', 'marta')); "
            "world.step(240); sys.exit(1 if 'pygame' in sys.modules else 0)"
        )
        done = subprocess.run([sys.executable, "-c", check], cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(done.returncode, 0, done.stderr)


class MakingBetterTests(unittest.TestCase):
    def test_a_rarity_has_to_have_been_studied_first(self) -> None:
        world = _settled(known=0)
        self.assertEqual(world.upgrades.obstacle(world, "crop_1"), "Antes hay que estudiarlo: Buen oficio")
        result = world.apply_command(ProposeUpgradeCommand("crop_1", "marta"))
        self.assertFalse(result.ok)
        self.assertIn("Buen oficio", result.message)
        self.assertEqual(world.sites, {})
        world.studies.known.append("fine_work")
        self.assertIsNone(world.upgrades.obstacle(world, "crop_1"))
        world.interactables["crop_1"].level = 2
        self.assertEqual(world.upgrades.obstacle(world, "crop_1"), "Antes hay que estudiarlo: Oficio fino")

    def test_each_level_takes_more_than_the_last(self) -> None:
        world = _settled(known=4)
        crop = world.interactables["crop_1"]
        first = world.upgrades.rule(world, "crop_1")
        self.assertEqual((first.cost, first.minutes), ({"scrap": 3}, 180))
        crop.level = 3
        third = world.upgrades.rule(world, "crop_1")
        self.assertEqual((third.cost, third.minutes), ({"scrap": 9}, 540))
        self.assertEqual(world.upgrades.thing(world, "crop_1"), "mejorar un bancal (épico)")

    def test_what_is_mythic_is_never_made_here(self) -> None:
        world = _settled(known=4)
        crop = world.interactables["crop_1"]
        crop.level = 5
        self.assertEqual(world.upgrades.rarity(world, crop).rarity_id, "legendary")
        self.assertIn("solo se encuentra", world.upgrades.obstacle(world, "crop_1"))
        self.assertFalse(world.apply_command(ProposeUpgradeCommand("crop_1", "marta")).ok)
        crop.level = 6
        self.assertEqual(world.upgrades.rarity(world, crop).name, "Mítico")
        self.assertIsNone(world.upgrades.rule(world, "crop_1"))
        self.assertFalse(world.apply_command(ProposeUpgradeCommand("crop_1", "marta")).ok)

    def test_it_is_put_to_somebody_carried_to_and_worked_on_like_anything_built(self) -> None:
        world = _settled()
        scrap = lambda: world.ledger.stock(world)["scrap"]  # noqa: E731
        before = scrap()
        result = world.apply_command(ProposeUpgradeCommand("warehouse", "marta"))
        self.assertTrue(result.ok, result.message)
        site = world.sites[result.entity_id]
        store = world.interactables["warehouse"]
        self.assertEqual((site.kind, site.what, site.in_charge), (UPGRADE_SITE, "warehouse", "marta"))
        self.assertEqual((site.x, site.y, len(site.tiles)), (store.x, store.y, 12))
        self.assertEqual(world.upgrades.obstacle(world, "warehouse"), IN_HAND)
        self.assertFalse(world.apply_command(ProposeUpgradeCommand("warehouse", "raul")).ok, "one at a time")
        self.assertTrue(_run(world, MINUTES_PER_DAY, lambda: not world.sites), "it was never done")
        self.assertEqual(store.level, 2)
        self.assertEqual(world.upgrades.rarity(world, store).name, "Poco común")
        self.assertEqual(scrap(), before - 3)
        log = "\n".join(world.event_log)
        self.assertIn("site_laid | Se marca el sitio de una obra: mejorar un almacén (poco común)", log)
        self.assertIn(f"{UPGRADED_EVENT} | Un almacén es ahora de calidad: poco común", log)
        self.assertIn("site_finished | Obra terminada: mejorar un almacén (poco común)", log)
        self.assertTrue(any("Saqué adelante una obra" in memory.text for memory in world.memories.of("marta")))

    def test_what_is_being_made_better_is_not_used_meanwhile(self) -> None:
        world = _settled()
        raul = world.residents["raul"]
        self.assertTrue(_run(world, 120, lambda: world.work.on_duty(world, raul)))
        self.assertTrue(world.apply_command(ProposeUpgradeCommand("crop_1", "marta")).ok)
        world.step(1)
        self.assertFalse(world.work.on_duty(world, raul), "nobody works at a post that is being seen to")
        self.assertIsNone(world.work.candidate(world, raul))
        self.assertTrue(world.apply_command(ProposeUpgradeCommand("bed_1", "ines")).ok)
        ines = world.residents["ines"]
        self.assertFalse(world.activities.routine.open_for(world, ines, world.interactables["bed_1"]))
        self.assertTrue(world.activities.routine.open_for(world, ines, world.interactables["bed_7"]))
        # A store goes on holding what it holds.
        self.assertTrue(world.apply_command(ProposeUpgradeCommand("warehouse", "paco")).ok)
        water = world.stores.held(world)["water"]
        world.step(5)
        self.assertGreater(water, 0)
        self.assertGreaterEqual(world.stores.held(world)["water"], water - 5)

    def test_if_the_thing_goes_the_work_is_given_up_and_what_was_brought_comes_back(self) -> None:
        world = _settled()
        scrap = world.ledger.stock(world)["scrap"]
        site_id = world.apply_command(ProposeUpgradeCommand("bed_2", "marta")).entity_id
        self.assertTrue(_run(world, 6 * 60, lambda: site_id in world.sites and world.sites[site_id].delivered), "nothing was brought")
        del world.interactables["bed_2"]
        _run(world, 5)
        self.assertNotIn(site_id, world.sites)
        self.assertEqual(world.ledger.stock(world)["scrap"], scrap)


class BetterTests(unittest.TestCase):
    def test_a_better_post_is_worked_faster(self) -> None:
        world = _settled()
        raul, ines = world.residents["raul"], world.residents["ines"]
        farmer, cook = world.registries.jobs["farmer"], world.registries.jobs["cook"]
        plain = world.work.pace(world, raul, farmer)
        world.interactables["crop_1"].level = 3
        self.assertAlmostEqual(world.work.pace(world, raul, farmer), plain * 1.3)
        self.assertAlmostEqual(world.work.pace(world, ines, farmer), plain, msg="hers is another post")
        self.assertAlmostEqual(world.work.pace(world, raul, cook), world.work.pace(world, ines, cook), msg="not his job")
        self.assertAlmostEqual(world.work.expected(world, raul, farmer).pace, world.work.expected(world, ines, farmer).pace * 1.3)

    def test_a_better_store_holds_more(self) -> None:
        world = _settled()
        plain = world.stores.capacity(world)
        world.interactables["warehouse"].level = 5
        self.assertEqual(world.stores.capacity(world), {name: round(units * 1.75) for name, units in plain.items()})
        self.assertEqual(world.ledger.line(world, "food").capacity, round(plain["food"] * 1.75))

    def test_a_better_bed_rests_better(self) -> None:
        rested = {}
        for level in (1, 4):
            world = _settled(hour=23)
            for other in [each for each in world.residents if each != "ines"]:
                del world.residents[other]
            world.interactables["bed_1"].level = level
            ines = world.residents["ines"]
            ines.needs.tiredness = 90.0
            world.put_down("ines", object_id="bed_1")
            world.step(1)
            self.assertEqual(ines.current_action, "sleep")
            before = ines.needs.tiredness
            world.step(60)
            rested[level] = before - ines.needs.tiredness
        self.assertGreater(rested[4], rested[1] * 1.3)

    def test_a_better_generator_gives_more_current(self) -> None:
        world = _settled()
        plain = world.power.supply(world)
        self.assertGreater(plain, 0)
        world.interactables["generator"].level = 5
        self.assertEqual(world.power.supply(world), round(plain * 1.75))


class SavedTests(unittest.TestCase):
    def test_levels_and_a_work_in_hand_are_saved_and_go_on_the_same(self) -> None:
        manager = SaveManager()
        world = _settled()
        world.interactables["crop_3"].level = 4
        site_id = world.apply_command(ProposeUpgradeCommand("warehouse", "marta")).entity_id
        world.step(30)
        data = manager.to_data(world)
        loaded = manager.from_data(data)
        self.assertEqual(loaded.interactables["crop_3"].level, 4)
        self.assertEqual((loaded.sites[site_id].kind, len(loaded.sites[site_id].tiles)), (UPGRADE_SITE, 12))
        for each in (world, loaded):
            each.step(8 * 60)
        self.assertEqual(manager.to_data(loaded), manager.to_data(world))
        self.assertEqual(loaded.interactables["warehouse"].level, 2)

    def test_in_a_save_from_before_everything_is_common(self) -> None:
        manager = SaveManager()
        world = _settled()
        world.interactables["crop_3"].level = 4
        data = manager.to_data(world)
        for placed in data["interactables"]:
            del placed["level"]
        data["version"] = 42
        loaded = manager.from_data(data)
        self.assertTrue(all(placed.level == 1 for placed in loaded.interactables.values()))
        data = manager.to_data(world)
        next(each for each in data["interactables"] if each["id"] == "crop_3")["level"] = 40
        self.assertEqual(manager.from_data(data).interactables["crop_3"].level, 6, "no better than the best there is")


if __name__ == "__main__":
    unittest.main()
