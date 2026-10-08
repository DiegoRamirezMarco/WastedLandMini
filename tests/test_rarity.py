"""Rarer things (S64): what is carried has a rarity too, which it keeps wherever it goes, and
which makes it do what it does better and be worth more."""

import unittest

from save.save_manager import SaveManager
from simulation.residents.activity import Activity
from simulation.residents.attributes import Attributes
from simulation.residents.needs import Needs
from simulation.rng import SimulationRNG
from simulation.work import hauling
from simulation.work.expedition import Expedition
from simulation.world import SimulationWorld
from tests.worlds import no_store

MINUTES_PER_DAY = 24 * 60


def _keep_content(world: SimulationWorld) -> None:
    for resident in world.residents.values():
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


def _stacks(world: SimulationWorld, item_id: str) -> dict[int, int]:
    """How many units of a thing there are in all, by how rare they are."""
    found: dict[int, int] = {}
    inventories = [*world.containers.values(), *(each.inventory for each in world.residents.values())]
    for inventory in inventories:
        for item in inventory.items:
            if item.definition_id == item_id and item.owner_id is None:
                found[item.level] = found.get(item.level, 0) + item.quantity
    return found


class KeptApartTests(unittest.TestCase):
    def test_things_of_one_kind_and_two_rarities_are_two_stacks(self) -> None:
        world = _settled()
        crate = world.containers["crate_dorm"]
        crate.items.clear()
        world.stock(crate, "hoe", 2, None)
        world.stock(crate, "hoe", 1, None, 3)
        world.stock(crate, "hoe", 4, None, 3)
        self.assertEqual(sorted((item.level, item.quantity) for item in crate.items), [(1, 2), (3, 5)])
        self.assertEqual(crate.count("hoe"), 7)
        self.assertEqual(crate.stack_of("hoe", None, 3).quantity, 5)
        self.assertIsNone(crate.stack_of("hoe", None, 2))
        self.assertIsNotNone(crate.stack_of("hoe", None))

    def test_what_a_better_post_makes_is_as_rare_as_the_post_and_stays_so_wherever_it_goes(self) -> None:
        world = _settled()
        world.residents["marta"].job_id = None
        world.interactables["crop_1"].level = 3
        before = _stacks(world, "vegetables")
        _run(world, 5 * 60)
        made = _stacks(world, "vegetables")
        self.assertGreater(made.get(3, 0), 3, "what Raúl grew at the bed that was made better")
        self.assertGreater(made.get(1, 0), before.get(1, 0), "what Inés grew at hers")
        store = world.containers["warehouse"]
        self.assertGreater(store.stack_of("vegetables", None, 3).quantity, 0, "carried to the pantry and put away as it was")
        self.assertEqual(set(made), {1, 3})
        self.assertEqual(world.ledger.stock(world)["food"], sum(sum(_stacks(world, each).values()) for each in ("vegetables", "canned_beans", "stew", "pizza_radioactiva") if world.registries.items.find(each)))

    def test_it_is_saved_and_a_save_from_before_has_everything_common(self) -> None:
        manager = SaveManager()
        world = _settled()
        world.stock(world.containers["crate_dorm"], "hoe", 1, None, 4)
        world.residents["sergio"].expedition = Expedition(world.clock.total_minutes + 60, 2, 0.0, risked=True)
        world.residents["sergio"].activity = Activity("expedition", minutes_left=60, using=True)
        data = manager.to_data(world)
        loaded = manager.from_data(data)
        self.assertEqual(loaded.containers["crate_dorm"].stack_of("hoe", None, 4).quantity, 1)
        self.assertTrue(loaded.residents["sergio"].expedition.risked)
        for items in data["containers"].values():
            for item in items:
                del item["level"]
        data["version"] = 43
        older = manager.from_data(data)
        self.assertEqual({item.level for inventory in older.containers.values() for item in inventory.items}, {1})


class BetterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.world = _settled()
        self.ines = self.world.residents["ines"]

    def test_rarer_food_fills_more_and_is_what_is_reached_for(self) -> None:
        world = no_store(_settled())
        ines = world.residents["ines"]
        pantry = world.containers["pantry_1"]
        pantry.items.clear()
        world.stock(pantry, "canned_beans", 5, None)
        world.stock(pantry, "canned_beans", 5, None, 4)
        self.assertEqual(world.items.best_food(world, ines, "pantry_1", "food").level, 4)
        self.assertEqual(world.items.take_meal(world, ines, "pantry_1", "food"), ("canned_beans", 4))
        beans = world.registries.items.resolve("canned_beans")
        relief = {}
        for level in (1, 4):
            ines.needs = Needs(hunger=90, thirst=0, tiredness=0, social=0, stress=0)
            world.items.take_in(world, ines, beans, world.registries.rarities.of(level).better)
            relief[level] = 90 - ines.needs.hunger
        self.assertAlmostEqual(relief[4], relief[1] * 1.5, places=3)

    def test_a_meal_off_the_shelf_does_good_by_how_rare_it_was(self) -> None:
        eaten = {}
        for level in (1, 5):
            world = no_store(_settled(hour=14))
            for other in [each for each in world.residents if each != "ines"]:
                del world.residents[other]
            pantry = world.containers["pantry_1"]
            pantry.items.clear()
            world.stock(pantry, "canned_beans", 3, None, level)
            ines = world.residents["ines"]
            ines.needs.hunger = 95.0
            world.put_down("ines", object_id="pantry_1")
            world.step(1)
            self.assertEqual((ines.current_action, ines.activity.item_level), ("eat", level))
            before = ines.needs.hunger
            world.step(25)
            eaten[level] = before - ines.needs.hunger
        self.assertGreater(eaten[5], eaten[1] * 1.5)

    def test_a_rarer_tool_is_faster_and_lasts_longer(self) -> None:
        world = self.world
        farmer = world.registries.jobs["farmer"]
        hoe = next(item for item in self.ines.inventory.items if item.definition_id == "hoe")
        plain = world.work.tool_speed(world, farmer, hoe)
        hoe.level = 3
        self.assertAlmostEqual(world.work.tool_speed(world, farmer, hoe), plain * 1.3)
        worn = {}
        for level in (1, 5):
            hoe.level, hoe.condition = level, 100.0
            world.items.wear(world, self.ines, hoe)
            worn[level] = 100.0 - hoe.condition
        self.assertGreater(worn[1], 0)
        self.assertAlmostEqual(worn[5], worn[1] / 1.75)

    def test_a_rarer_weapon_hits_harder(self) -> None:
        world = self.world
        tomas = world.residents["tomas"]
        baton = next(item for item in tomas.inventory.items if item.definition_id == "baton")
        plain = world.health.weapon_of(world, tomas)[0]
        baton.level = 6
        self.assertAlmostEqual(world.health.weapon_of(world, tomas)[0], plain * 2.0)

    def test_what_is_rarer_is_dearer_to_buy_and_worth_more(self) -> None:
        world = self.world
        counter = world.containers["shop_counter"]
        hoe = counter.stack_of("hoe", None)
        price = world.trade.price_for(world, counter, hoe)
        worth = world.trade.worth(world, self.ines, hoe)
        hoe.level = 4
        self.assertGreaterEqual(world.trade.price_for(world, counter, hoe), int(price * 1.5))
        self.assertAlmostEqual(world.trade.worth(world, self.ines, hoe), worth * 1.5)


class WhereFromTests(unittest.TestCase):
    def test_what_is_found_outside_is_seldom_rare_and_oftener_for_a_risk(self) -> None:
        world = _settled()
        settings = world.registries.rarities
        self.assertEqual(len(settings.found), len(settings.tiers))
        self.assertGreater(settings.found[0], sum(settings.found[1:]) * 4, "nearly all of it common")
        self.assertGreater(settings.found[1], settings.found[5] * 100, "and mythic hardly ever")
        counts = {}
        for risked in (False, True):
            dice = SimulationRNG(5)
            drawn = [world.upgrades.found_level(world, dice, risked) for _ in range(4000)]
            counts[risked] = sum(1 for level in drawn if level > 1)
            self.assertLessEqual(max(drawn), settings.highest)
        self.assertGreater(counts[False], 300)
        self.assertLess(counts[False], 900)
        self.assertGreater(counts[True], counts[False] * 2)

    def test_drawing_how_rare_a_find_is_moves_none_of_the_settlements_dice(self) -> None:
        from dataclasses import replace

        back = []
        for weighted in (True, False):
            world = _settled(seed=11)
            if not weighted:
                world.registries = replace(world.registries, rarities=replace(world.registries.rarities, found=()))
            sergio = world.residents["sergio"]
            for other in [each for each in world.residents if each != "sergio"]:
                del world.residents[other]
            sergio.inventory.items.clear()
            sergio.expedition = Expedition(world.clock.total_minutes + 3, 40, 0.0, risked=True)
            sergio.activity = Activity("expedition", minutes_left=3, using=True)
            world.step(4)
            self.assertIsNone(sergio.expedition)
            found: dict[str, int] = {}
            for item in sergio.inventory.items:
                found[item.definition_id] = found.get(item.definition_id, 0) + item.quantity
            back.append((world.rng.get_state(), found, {item.level for item in sergio.inventory.items}))
        (dice, found, levels), (plain_dice, plain_found, plain_levels) = back
        self.assertEqual(dice, plain_dice, "it is drawn with dice of its own")
        self.assertEqual(found, plain_found, "and what is found is the same things")
        self.assertEqual(plain_levels, {1})
        self.assertGreater(len(levels), 1)

    def test_what_is_left_at_a_place_is_told_by_the_kind_of_thing(self) -> None:
        world = no_store(_settled())
        sergio = world.residents["sergio"]
        sergio.inventory.items.clear()
        for level in (1, 2, 4):
            world.stock(sergio.inventory, "scrap", level, None, level)
        said = world.expeditions.unload(world, sergio, world.interactables["scrap_yard"])
        self.assertEqual(said, "deja chatarra (7) en un montón de chatarra")
        self.assertEqual(sorted(item.level for item in world.containers["scrap_yard"].items if item.level > 1), [2, 4])

    def test_whoever_goes_on_at_a_risk_is_marked_for_it(self) -> None:
        world = _settled()
        sergio = world.residents["sergio"]
        self.assertFalse(Expedition(0, 1, 0.0).risked)
        sergio.expedition = Expedition(world.clock.total_minutes + 5, 30, 0.0, risked=True)
        sergio.activity = Activity("expedition", minutes_left=5, using=True)
        _run(world, 30, lambda: sergio.expedition is None)
        self.assertIsNone(sergio.expedition)
        rare = sum(item.quantity for item in sergio.inventory.items if item.level > 1 and item.owner_id is None)
        self.assertGreater(rare, 3, "thirty things at three times the odds")

    def test_a_tool_mended_at_a_better_workshop_comes_away_rarer(self) -> None:
        world = _settled(hour=11)
        bench = world.interactables["workbench"]
        use = world.definition_of(bench).use
        ines = world.residents["ines"]
        hoe = next(item for item in ines.inventory.items if item.definition_id == "hoe")
        scrap = lambda: world.ledger.stock(world)["scrap"]  # noqa: E731
        paco = world.residents["paco"]
        self.assertTrue(_run(world, 120, lambda: world.work.on_duty(world, paco)), "nobody at the workshop")
        # Mended at a common workshop it is only mended. At a rare one it comes away a rarity
        # rarer each time, for a unit more of scrap, and no rarer than the workshop is.
        for bench_level, expected in ((1, 1), (3, 2), (3, 3), (3, 3)):
            bench.level = bench_level
            hoe.condition = 100.0 - use.repairs
            before, was = scrap(), hoe.level
            activity = Activity(use.action, "workbench", minutes_left=30, using=True, item_id=hoe.instance_id)
            self.assertTrue(world.trade.repair_minute(world, activity, use))
            self.assertEqual((hoe.level, hoe.condition), (expected, 100.0))
            self.assertEqual(before - scrap(), 1 if expected > was else 0)
        self.assertTrue(any("item_improved | Del taller sale" in line for line in world.event_log))


if __name__ == "__main__":
    unittest.main()
