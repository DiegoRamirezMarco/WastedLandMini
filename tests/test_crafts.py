"""A trade and what it teaches (S47): levels of a job, the new things each brings, naming
them, making them, showing them to others and losing them."""

import json
import math
import subprocess
import sys
import unittest
from dataclasses import replace
from pathlib import Path

from save.save_manager import SaveManager
from simulation.commands import NameDiscoveryCommand
from simulation.economy.trade_system import MAX_WANT
from simulation.events.world_event import STAND_GROUND
from simulation.health.injury import Injury
from simulation.residents.activity import Activity
from simulation.residents.attributes import Attributes
from simulation.residents.needs import Needs
from simulation.residents.resident import Resident
from simulation.work import hauling
from simulation.work.craft import Discovery, article_for, craft_settings_from_data
from simulation.work.craft_system import (
    FOUND_EVENT,
    LEVEL_EVENT,
    LOST_EVENT,
    NAMED_EVENT,
    TAUGHT_EVENT,
    tool_tag,
)
from simulation.work.work_system import WORK_ACTION
from simulation.world import SimulationWorld

ROOT = Path(__file__).resolve().parent.parent
DATA = json.loads((ROOT / "data" / "crafts.json").read_text(encoding="utf-8"))


def _settled(seed: int = 7) -> SimulationWorld:
    """The ready-made settlement, content, with everybody in the middle of every attribute."""
    world = SimulationWorld.demo_world(seed=seed)
    world.relationships.clear()
    for resident in world.residents.values():
        resident.needs = Needs(hunger=0, tiredness=0, social=0, stress=0)
        resident.attributes = Attributes()
    return world


def _types(world: SimulationWorld) -> list[str]:
    return [line.split(" | ")[1] for line in world.event_log]


def _level_up(world: SimulationWorld, resident_id: str, level: int = 2) -> Discovery | None:
    """Give a resident the time at their job that a level takes, and return what they come to."""
    resident = world.residents[resident_id]
    job = world.registries.jobs[resident.job_id]
    marks = world.registries.crafts.levels
    world.crafts.worked(world, resident, job, marks[level - 1] - resident.trade.get(job.job_id, 0.0))
    waiting = [each for each in world.crafts.waiting(world) if each.by == resident_id and each.level == level]
    return waiting[-1] if waiting else None


def _learn(world: SimulationWorld, resident_id: str, name: str, **choices: str) -> Discovery:
    """Have a resident come to something at their job, named and picked."""
    discovery = _level_up(world, resident_id, world.crafts.level(world, world.residents[resident_id], world.residents[resident_id].job_id) + 1)
    result = world.apply_command(NameDiscoveryCommand(discovery.discovery_id, name, choices))
    assert result.ok, result.message
    return discovery


def _work(world: SimulationWorld, resident_id: str, minutes: int) -> Resident:
    """Have a resident spend minutes at their post, whatever the hour."""
    resident = world.residents[resident_id]
    for _ in range(minutes):
        if resident.activity is None or resident.activity.action != WORK_ACTION:
            resident.activity = Activity(WORK_ACTION, resident.post_id, [], 600, using=True)
        world.work.tick(world, resident, resident.activity)
        resident.needs = Needs(hunger=0, tiredness=0, social=0, stress=0)
    return resident


class DataTests(unittest.TestCase):
    def test_a_job_has_five_levels_and_eight_kinds_of_thing_are_taught(self) -> None:
        settings = SimulationWorld.demo_world().registries.crafts
        self.assertEqual(settings.top, 5)
        self.assertEqual(settings.levels[0], 0)
        self.assertEqual(
            set(settings.kinds), {"crop", "dish", "drink", "substance", "remedy", "tool", "weapon", "place"}
        )
        self.assertEqual(settings.jobs["farmer"], "crop")
        self.assertEqual(settings.jobs["scavenger"], "place")

    def test_every_job_that_teaches_is_a_job_and_the_rest_teach_nothing(self) -> None:
        world = SimulationWorld.demo_world()
        settings = world.registries.crafts
        self.assertLessEqual(set(settings.jobs), set(world.registries.jobs))
        for job_id in ("water_carrier", "shopkeeper", "researcher"):
            self.assertIsNone(world.crafts.kind_of(world, job_id), job_id)
        self.assertEqual(world.crafts.kind_of(world, "cook").kind_id, "dish")

    def test_a_crop_is_grown_four_ways(self) -> None:
        crop = SimulationWorld.demo_world().registries.crafts.kinds["crop"]
        grows = crop.choices["grows"].options
        self.assertEqual(list(grows), ["soil", "bush", "vine", "tree"])
        self.assertEqual(grows["soil"].ripens_days, 0)
        self.assertGreater(grows["tree"].ripens_days, grows["vine"].ripens_days)
        self.assertGreater(grows["tree"].batch, grows["soil"].batch)
        self.assertLess(grows["soil"].every_minutes, grows["bush"].every_minutes)

    def test_data_that_makes_no_sense_is_refused(self) -> None:
        crop = DATA["kinds"]["crop"]
        for wrong in (
            {"levels": [10, 20]},
            {"levels": [0, 50, 50]},
            {"jobs": {"farmer": "spell"}},
            {"teach_minutes": 0},
            {"kinds": {"crop": {**crop, "choices": {"grows": {"name": "x", "source": "the_moon"}}}}},
            {"kinds": {"crop": {**crop, "choices": {"grows": {"name": "x"}}}}},
            {"kinds": {"crop": {**crop, "item": {"tags": ["food"]}}}},
            {"kinds": {"crop": {**crop, "every_minutes": 0}}},
            {"kinds": {"crop": {**crop, "choices": {"grows": {"name": "x", "options": {"a": {"text": "no name"}}}}}}},
        ):
            with self.assertRaises(ValueError, msg=wrong):
                craft_settings_from_data({**DATA, **wrong})

    def test_a_name_goes_by_the_article_its_ending_tells(self) -> None:
        self.assertEqual(
            [article_for(name) for name in ("tomate", "lechuga", "patatas", "limones", "ajos", "")],
            ["un", "una", "unas", "unos", "unos", "un"],
        )

    def test_a_trade_needs_no_pygame(self) -> None:
        check = (
            "import sys; import simulation.work.craft_system, save.save_manager; "
            "from simulation.world import SimulationWorld; world = SimulationWorld.demo_world(); "
            "raul = world.residents['raul']; world.crafts.worked(world, raul, world.registries.jobs['farmer'], 9000); "
            "[world.name_discovery(d.discovery_id, 'cosa ' + d.discovery_id[-1]) for d in world.crafts.waiting(world)]; "
            "world.step(300); sys.exit(1 if 'pygame' in sys.modules else 0)"
        )
        done = subprocess.run([sys.executable, "-c", check], cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(done.returncode, 0, done.stderr)


class LevelTests(unittest.TestCase):
    def test_everybody_starts_at_the_first_level(self) -> None:
        world = _settled()
        raul = world.residents["raul"]
        self.assertEqual(world.crafts.level(world, raul, "farmer"), 1)
        self.assertEqual(world.crafts.level(world, raul, None), 1)
        self.assertEqual(world.crafts.progress(world, raul, "farmer"), 0.0)
        self.assertEqual(world.crafts.pace(world, raul, world.registries.jobs["farmer"]), 1.0)

    def test_a_minute_at_the_post_is_a_minute_of_the_trade(self) -> None:
        world = _settled()
        raul = _work(world, "raul", 120)
        self.assertEqual(raul.trade, {"farmer": 120.0})
        self.assertAlmostEqual(world.crafts.progress(world, raul, "farmer"), 120 / world.registries.crafts.levels[1])

    def test_time_at_a_job_comes_to_a_level_and_the_level_to_something_new(self) -> None:
        world = _settled()
        raul = world.residents["raul"]
        marks = world.registries.crafts.levels
        world.crafts.worked(world, raul, world.registries.jobs["farmer"], marks[1] - 1)
        self.assertEqual((world.crafts.level(world, raul, "farmer"), world.discoveries), (1, {}))
        world.crafts.worked(world, raul, world.registries.jobs["farmer"], 1)
        self.assertEqual(world.crafts.level(world, raul, "farmer"), 2)
        (discovery,) = world.crafts.waiting(world)
        self.assertEqual((discovery.kind, discovery.by, discovery.level, discovery.named), ("crop", "raul", 2, False))
        self.assertEqual(_types(world)[-2:], [LEVEL_EVENT, FOUND_EVENT])
        self.assertIn("Raúl llega al nivel 2 de huerto", world.event_log[-2])

    def test_each_level_brings_one_thing_and_there_are_four_to_come_to(self) -> None:
        world = _settled()
        raul = world.residents["raul"]
        world.crafts.worked(world, raul, world.registries.jobs["farmer"], 10 ** 6)
        self.assertEqual(world.crafts.level(world, raul, "farmer"), 5)
        self.assertEqual([each.level for each in world.crafts.waiting(world)], [2, 3, 4, 5])
        self.assertEqual(world.crafts.progress(world, raul, "farmer"), 1.0)
        world.crafts.worked(world, raul, world.registries.jobs["farmer"], 10 ** 6)
        self.assertEqual(len(world.discoveries), 4, "and past the top there is nothing more")

    def test_a_good_head_learns_a_trade_sooner(self) -> None:
        world = _settled()
        job = world.registries.jobs["farmer"]
        raul, ines = world.residents["raul"], world.residents["ines"]
        raul.attributes, ines.attributes = Attributes(mind=9.0), Attributes(mind=2.0)
        for farmer in (raul, ines):
            world.crafts.worked(world, farmer, job, 1000)
        self.assertGreater(raul.trade["farmer"], 1000.0)
        self.assertLess(ines.trade["farmer"], 1000.0)

    def test_every_level_makes_the_work_go_faster(self) -> None:
        def minutes_to_a_unit(level: int) -> int:
            world = _settled()
            raul = world.residents["raul"]
            raul.trade["farmer"] = float(world.registries.crafts.levels[level - 1])
            job, placed = world.registries.jobs["farmer"], world.interactables[raul.post_id]
            for minute in range(1, 200):
                world.work._produce(world, raul, job, placed, 300)
                if hauling.carried(raul, "vegetables") > 0:
                    return minute
            return 0

        self.assertGreater(minutes_to_a_unit(1), minutes_to_a_unit(3))
        self.assertGreater(minutes_to_a_unit(3), minutes_to_a_unit(5))

    def test_a_job_that_teaches_nothing_is_still_learned(self) -> None:
        world = _settled()
        nuria = world.residents["nuria"]
        self.assertEqual(nuria.job_id, "shopkeeper")
        world.crafts.worked(world, nuria, world.registries.jobs["shopkeeper"], 10 ** 6)
        self.assertEqual(world.crafts.level(world, nuria, "shopkeeper"), 5)
        self.assertEqual(world.discoveries, {})
        self.assertEqual(_types(world).count(LEVEL_EVENT), 4)

    def test_time_out_there_counts_for_whoever_works_out_there(self) -> None:
        world = _settled()
        sergio = world.residents["sergio"]
        world.expeditions.set_out(world, sergio, world.registries.jobs["scavenger"])
        for _ in range(30):
            world.expeditions.tick(world, sergio, sergio.activity)
        self.assertEqual(sergio.trade.get("scavenger"), 30.0)

    def test_whoever_keeps_watch_longer_sees_further(self) -> None:
        world = _settled()
        tomas = world.residents["tomas"]
        tomas.activity = Activity(WORK_ACTION, tomas.post_id, [], 60, using=True)
        usual = world.registries.jobs["guard"].sight_bonus
        self.assertEqual(world.work.sight_bonus(world, tomas), usual)
        tomas.trade["guard"] = float(world.registries.crafts.levels[4])
        self.assertEqual(world.work.sight_bonus(world, tomas), usual + 2)


class NamingTests(unittest.TestCase):
    def test_until_it_is_named_it_waits_and_nobody_makes_it(self) -> None:
        world = _settled()
        discovery = _level_up(world, "raul")
        raul = world.residents["raul"]
        self.assertEqual(world.crafts.waiting(world), [discovery])
        self.assertEqual(raul.makes, {})
        self.assertEqual(world.crafts.products(world, raul, world.registries.jobs["farmer"]), [])
        _work(world, "raul", 120)
        self.assertEqual(world.crafts.extra_items(world, raul), ())

    def test_the_player_says_what_it_is_called_and_how_it_grows(self) -> None:
        world = _settled()
        discovery = _level_up(world, "raul")
        result = world.apply_command(NameDiscoveryCommand(discovery.discovery_id, "  tomate  ", {"grows": "bush"}))
        self.assertTrue(result.ok, result.message)
        self.assertEqual((discovery.name, discovery.choices, discovery.item_id), ("tomate", {"grows": "bush"}, "crop_1"))
        item = world.registries.items.get("crop_1")
        self.assertEqual((item.name, item.article, item.category), ("tomate", "un", "food"))
        self.assertIn("crop", item.tags)
        self.assertLess(item.effects["hunger"], -20.0, "better than what anybody grows")
        self.assertEqual(world.crafts.waiting(world), [])
        self.assertEqual(world.residents["raul"].makes, {discovery.discovery_id: world.clock.day})
        self.assertEqual(_types(world)[-1], NAMED_EVENT)
        self.assertIn("Raúl aprende a cultivar tomate", world.event_log[-1])
        self.assertTrue(any("tomate" in memory.text for memory in world.memories.of("raul")))

    def test_what_is_left_unpicked_is_the_first_there_is_to_pick(self) -> None:
        world = _settled()
        discovery = _level_up(world, "raul")
        self.assertTrue(world.name_discovery(discovery.discovery_id, "ajos").ok)
        self.assertEqual(discovery.choices, {"grows": "soil"})
        self.assertEqual(world.registries.items.get(discovery.item_id).article, "unos")

    def test_a_thing_needs_a_name_of_its_own_and_a_pick_there_is(self) -> None:
        world = _settled()
        discovery = _level_up(world, "raul")
        name = world.name_discovery
        self.assertFalse(name("discovery_99", "tomate").ok)
        self.assertFalse(name(discovery.discovery_id, "   ").ok)
        self.assertFalse(name(discovery.discovery_id, "tomate", {"grows": "on_the_moon"}).ok)
        self.assertFalse(name(discovery.discovery_id, "Guiso caliente").ok, "the name of something there is already")
        self.assertFalse(discovery.named)
        self.assertTrue(name(discovery.discovery_id, "tomate").ok)
        self.assertFalse(name(discovery.discovery_id, "limón").ok, "it has a name already")
        other = _level_up(world, "ines")
        self.assertFalse(name(other.discovery_id, "TOMATE").ok)
        long_name = "x" * 60
        self.assertTrue(name(other.discovery_id, long_name).ok)
        self.assertEqual(len(other.name), world.registries.crafts.name_length)

    def test_what_it_is_like_is_the_games_to_say_and_always_the_same(self) -> None:
        def made(seed: int) -> dict:
            world = _settled(seed)
            return _learn(world, "raul", "tomate", grows="bush").item

        self.assertEqual(made(7), made(7))
        ranges = DATA["kinds"]["crop"]["item"]
        item = made(7)
        self.assertTrue(ranges["effects"]["hunger"][0] <= item["effects"]["hunger"] <= ranges["effects"]["hunger"][1])
        self.assertTrue(ranges["value"][0] <= item["base_value"] <= ranges["value"][1])
        self.assertTrue(set(item["preference_tags"]) <= set(DATA["flavours"]))
        self.assertEqual(len(item["preference_tags"]), 1)
        self.assertEqual(item["description"], "Cultivo de Raúl.")

    def test_what_is_come_to_at_a_higher_level_is_better(self) -> None:
        def hunger(level: int) -> float:
            world = _settled()
            world.discoveries["discovery_1"] = Discovery("discovery_1", "crop", "farmer", "raul", "Raúl", level)
            self.assertTrue(world.name_discovery("discovery_1", "tomate").ok)
            return world.registries.items.get("crop_1").effects["hunger"]

        self.assertLess(hunger(5), hunger(2))
        self.assertAlmostEqual(hunger(5), round(hunger(2) * (1 + 3 * DATA["better"]), 1))

    def test_the_item_is_this_settlements_and_no_other_gets_it(self) -> None:
        world = _settled()
        shared = world.registries.items
        _learn(world, "raul", "tomate")
        self.assertIsNot(world.registries.items, shared)
        self.assertIsNone(shared.find("crop_1"))
        self.assertIsNone(SimulationWorld.demo_world().registries.items.find("crop_1"))


class MakingTests(unittest.TestCase):
    def test_a_farmer_grows_what_they_came_to_in_turn_with_what_anybody_grows(self) -> None:
        world = _settled()
        discovery = _learn(world, "raul", "tomate", grows="bush")
        raul = world.residents["raul"]
        job, placed = world.registries.jobs["farmer"], world.interactables[raul.post_id]
        for _ in range(100):
            world.work._produce(world, raul, job, placed, 300)
        self.assertGreater(hauling.carried(raul, discovery.item_id), 0)
        self.assertEqual(hauling.carried(raul, discovery.item_id) % 2, 0, "a bush gives two at a time")
        self.assertEqual(
            hauling.carried_made(world, raul, job.produces),
            hauling.carried(raul, "vegetables") + hauling.carried(raul, discovery.item_id),
        )

    def test_a_pantry_holds_as_much_of_the_garden_as_it_did_of_more_kinds(self) -> None:
        world = _settled()
        tomato = _learn(world, "raul", "tomate")
        raul = world.residents["raul"]
        rule = world.registries.jobs["farmer"].produces
        pantry = world.containers["pantry_1"]
        pantry.items.clear()
        world.stock(pantry, "vegetables", rule.max_stock - 5, None)
        self.assertEqual(hauling.room(world, raul, rule, pantry), 5)
        world.stock(pantry, tomato.item_id, 5, None)
        self.assertEqual(hauling.room(world, raul, rule, pantry), 0)
        self.assertEqual(hauling.room(world, world.residents["ines"], rule, pantry), 0, "whoever does not grow it counts it too")
        world.stock(raul.inventory, tomato.item_id, 4, None)
        place = world.interactables["pantry_1"]
        self.assertIsNone(hauling.exchange(world, raul, rule, place), "a full pantry takes no more of either")

    def test_the_cook_fetches_what_their_own_dish_is_made_of(self) -> None:
        world = _settled()
        tomato = _learn(world, "raul", "tomate")
        dish = _learn(world, "marta", "pisto", **{"from": tomato.item_id})
        marta = world.residents["marta"]
        rule = world.registries.jobs["cook"].produces
        pantry, place = world.containers["pantry_1"], world.interactables["pantry_1"]
        pantry.items.clear()
        world.stock(pantry, "vegetables", 30, None)
        world.stock(pantry, tomato.item_id, 4, None)
        pot = world.containers[marta.post_id]
        pot.items.clear()
        world.stock(pot, "stew", 3, None)
        self.assertIsNotNone(hauling.exchange(world, marta, rule, place))
        self.assertEqual(hauling.carried(marta, tomato.item_id), 4, "though there is more of the rest")
        self.assertEqual(hauling.carried(marta, "vegetables"), 0)
        marta.inventory.items.clear()
        world.stock(pantry, tomato.item_id, 4, None)
        world.stock(pot, dish.item_id, 5, None)
        self.assertIsNotNone(hauling.exchange(world, marta, rule, place))
        self.assertGreater(hauling.carried(marta, "vegetables"), 0, "with pisto enough in the pot, it is the usual")

    def test_both_are_carried_to_the_pantry_and_eaten(self) -> None:
        world = _settled()
        discovery = _learn(world, "raul", "tomate", grows="soil")
        world.clock.hour = 8
        for _ in range(8 * 60):
            world.step(1)
        stored = sum(world.containers[pantry].count(discovery.item_id) for pantry in ("pantry_1", "pantry_2"))
        self.assertGreater(stored, 0)
        self.assertTrue(any("de tomate a una despensa" in line for line in world.event_log))

    def test_a_tree_gives_nothing_until_it_has_had_its_days(self) -> None:
        world = _settled()
        discovery = _learn(world, "raul", "limones", grows="tree")
        raul = world.residents["raul"]
        job = world.registries.jobs["farmer"]
        days = DATA["kinds"]["crop"]["choices"]["grows"]["options"]["tree"]["ripens_days"]
        (product,) = world.crafts.products(world, raul, job)
        self.assertEqual((product.ripe, product.batch), (False, 4))
        placed = world.interactables[raul.post_id]
        for _ in range(100):
            world.work._produce(world, raul, job, placed, 300)
        self.assertEqual(hauling.carried(raul, discovery.item_id), 0)
        self.assertGreater(hauling.carried(raul, "vegetables"), 0, "meanwhile they grow what anybody grows")
        world.clock.day += days
        self.assertTrue(world.crafts.products(world, raul, job)[0].ripe)

    def test_a_bed_is_grown_as_the_crop_its_farmer_learned_last_is(self) -> None:
        world = _settled()
        raul, ines = world.residents["raul"], world.residents["ines"]
        self.assertIsNone(world.crafts.grown_at(world, raul.post_id), "nothing but what anybody grows")
        _learn(world, "raul", "tomate", grows="bush")
        self.assertEqual(world.crafts.grown_at(world, raul.post_id), "bush")
        self.assertIsNone(world.crafts.grown_at(world, ines.post_id), "the bed beside it is another's")
        _learn(world, "raul", "limones", grows="tree")
        self.assertEqual(world.crafts.grown_at(world, raul.post_id), "tree")
        self.assertIsNone(world.crafts.grown_at(world, world.residents["marta"].post_id))
        world.health.die(world, raul, "una prueba")
        self.assertIsNone(world.crafts.grown_at(world, "crop_1"), "with nobody to tend it, it is a bed again")

    def test_a_dish_is_made_of_one_thing_and_only_with_that_in_hand(self) -> None:
        world = _settled()
        crop = _learn(world, "raul", "tomate")
        waiting = _level_up(world, "marta")
        made_of = [option.option_id for option in world.crafts.options(world, waiting)["from"]]
        self.assertIn(crop.item_id, made_of, "what was come to in the garden is there to cook with")
        self.assertIn("vegetables", made_of)
        self.assertNotIn("stew", made_of, "a dish is not made of another")
        self.assertTrue(world.name_discovery(waiting.discovery_id, "pisto", {"from": crop.item_id}).ok)
        dish = world.registries.items.get(waiting.item_id)
        self.assertIn("cooked", dish.tags)
        self.assertTrue(set(world.registries.items.get(crop.item_id).preference_tags[:1]) <= set(dish.preference_tags))
        marta = world.residents["marta"]
        job, pot = world.registries.jobs["cook"], world.interactables[marta.post_id]
        world.containers[pot.object_id].items.clear()
        world.stock(marta.inventory, "vegetables", 3, None)
        for _ in range(40):
            world.work._produce(world, marta, job, pot, 300)
        self.assertEqual(world.containers[pot.object_id].count(dish.item_id), 0, "with no tomato in hand there is no pisto")
        self.assertGreater(world.containers[pot.object_id].count("stew"), 0)
        world.stock(marta.inventory, crop.item_id, 2, None)
        for _ in range(40):
            world.work._produce(world, marta, job, pot, 300)
        self.assertGreater(world.containers[pot.object_id].count(dish.item_id), 0)
        self.assertLess(hauling.carried(marta, crop.item_id), 2, "and a tomato goes into each")

    def test_a_drink_is_strong_mild_or_no_drink_at_all(self) -> None:
        world = _settled()
        strong = _learn(world, "lucia", "orujo", made="distilled")
        tea = _learn(world, "lucia", "tila", made="infusion")
        items = world.registries.items
        self.assertEqual(items.get(strong.item_id).category, "drink")
        self.assertEqual(items.get(strong.item_id).substance.sign, "drunk")
        self.assertIn("alcohol", items.get(strong.item_id).tags)
        self.assertIsNone(items.get(tea.item_id).substance)
        self.assertLess(items.get(tea.item_id).effects["tiredness"], 0)
        lucia = world.residents["lucia"]
        job, bar = world.registries.jobs["bartender"], world.interactables[lucia.post_id]
        world.stock(lucia.inventory, "water", 6, None)
        for _ in range(120):
            world.work._produce(world, lucia, job, bar, 300)
        self.assertGreater(world.containers[bar.object_id].count(strong.item_id), 0)
        self.assertGreater(world.containers[bar.object_id].count(tea.item_id), 0)

    def test_a_substance_is_what_it_does_and_how_it_is_taken(self) -> None:
        world = _settled()
        paco = world.residents["paco"]
        bench = world.urbanism.place_object(world, "lab_bench", (14, 11)).entity_id
        self.assertTrue(world.staffing.assign(world, paco, "chemist"))
        self.assertEqual(paco.post_id, bench)
        waiting = _level_up(world, "paco")
        self.assertEqual(set(world.crafts.options(world, waiting)), {"does", "taken"})
        self.assertTrue(world.name_discovery(waiting.discovery_id, "humo azul", {"does": "lifts", "taken": "smoked"}).ok)
        substance = world.registries.items.get(waiting.item_id).substance
        self.assertEqual((substance.route, substance.sign), ("smoked", "smoke"))
        self.assertGreater(substance.work_pace, 1.0)
        self.assertGreater(substance.after_minutes, 0)
        self.assertEqual(world.registries.items.get(waiting.item_id).category, "vice")

    def test_a_remedy_is_made_at_the_clinic_and_kept_in_the_cabinet(self) -> None:
        world = _settled()
        remedy = _learn(world, "vera", "ungüento", cures="wounds")
        kind = world.registries.crafts.kinds["remedy"]
        vera = world.residents["vera"]
        cabinet = world.containers[vera.post_id]
        # A level makes the work go faster, and they are at the second.
        needed = math.ceil(kind.every_minutes / world.crafts.pace(world, vera, world.registries.jobs["medic"]))
        _work(world, "vera", needed - 1)
        self.assertEqual(cabinet.count(remedy.item_id), 0)
        _work(world, "vera", 1)
        self.assertEqual(cabinet.count(remedy.item_id), 1)
        self.assertIn("medicine", world.registries.items.get(remedy.item_id).tags)
        _work(world, "vera", kind.every_minutes * (kind.max_stock + 2))
        self.assertEqual(cabinet.count(remedy.item_id), kind.max_stock, "no more are made than are kept")

    def test_a_remedy_mends_what_it_is_for_faster_and_lasts_longer(self) -> None:
        def mended(with_remedy: bool) -> tuple[float, int]:
            world = _settled()
            remedy = _learn(world, "vera", "ungüento", cures="wounds")
            vera, paco = world.residents["vera"], world.residents["paco"]
            cabinet = world.containers[vera.post_id]
            cabinet.items.clear()
            world.stock(cabinet, remedy.item_id if with_remedy else "medicine", 1, None)
            vera.activity = Activity(WORK_ACTION, vera.post_id, [], 600, using=True)
            bed = next(placed for placed in world.interactables.values() if placed.kind == "clinic_bed")
            paco.x, paco.y = bed.x, bed.y
            paco.injuries = [Injury("fracture", 40.0)]
            paco.activity = Activity("rest", bed.object_id, [], 600, using=True)
            start = world.clock.total_minutes
            for _ in range(120):
                world.health.tick(world, paco)
            return paco.health, paco.dosed_until - start

        plain, better = mended(False), mended(True)
        self.assertGreater(better[0], plain[0])
        self.assertGreater(better[1], plain[1])

    def test_a_tool_is_made_for_a_job_and_makes_that_job_go_faster(self) -> None:
        world = _settled()
        waiting = _level_up(world, "paco")
        jobs = [option.option_id for option in world.crafts.options(world, waiting)["for"]]
        self.assertIn("cook", jobs)
        self.assertIn("researcher", jobs)
        self.assertNotIn("guard", jobs, "a job that makes nothing has no use for one")
        self.assertTrue(world.name_discovery(waiting.discovery_id, "cucharón", {"for": "cook"}).ok)
        tool = world.registries.items.get(waiting.item_id)
        self.assertIn(tool_tag("cook"), tool.tags)
        self.assertGreater(tool.properties["speed"], 1.0)
        marta, raul = world.residents["marta"], world.residents["raul"]
        cook, farmer = world.registries.jobs["cook"], world.registries.jobs["farmer"]
        self.assertIsNone(world.work.tool_of(world, marta, cook))
        self.assertEqual(world.trade.want(world, marta, tool, 5.0), MAX_WANT, "whoever it is for wants one")
        mine = world.stock(marta.inventory, tool.item_id, 1, "marta")
        self.assertIs(world.work.tool_of(world, marta, cook), mine)
        self.assertEqual(world.work.tool_speed(world, cook, mine), tool.properties["speed"])
        self.assertIsNone(world.work.tool_speed(world, farmer, mine), "and it is no use for another job")
        self.assertEqual(world.trade.want(world, marta, tool, 5.0), 0.0, "and one is enough")
        self.assertIsNotNone(world.work.tool_of(world, raul, farmer), "a hoe is still a hoe")

    def test_a_tool_is_made_at_the_workshop_and_left_at_the_shop(self) -> None:
        world = _settled()
        tool = _learn(world, "paco", "cucharón", **{"for": "cook"})
        kind = world.registries.crafts.kinds["tool"]
        _work(world, "paco", kind.every_minutes + 1)
        self.assertEqual(world.containers["shop_counter"].count(tool.item_id), 1)
        self.assertIn("thing_made", _types(world))

    def test_what_is_worn_stops_some_of_a_blow_and_wears_out(self) -> None:
        fight = SimulationWorld.demo_world().registries.interactions["fight"]

        def taken(armoured: bool) -> float:
            world = _settled()
            shield = _learn(world, "tomas", "escudo", type="armour")
            self.assertGreater(world.registries.items.get(shield.item_id).properties["armour"], 0.0)
            paco = world.residents["paco"]
            worn = world.stock(paco.inventory, shield.item_id, 1, "paco") if armoured else None
            world.health.fight_damage(world, paco, world.residents["raul"], fight)
            if worn is not None:
                self.assertLess(worn.condition, 100.0)
            return 100.0 - paco.health

        self.assertLess(taken(True), taken(False))

    def test_a_weapon_that_keeps_them_at_a_distance_makes_a_raid_safer(self) -> None:
        world = _settled()
        sling = _learn(world, "tomas", "honda", type="ranged")
        item = world.registries.items.get(sling.item_id)
        self.assertGreater(item.properties["damage"], 1.0)
        self.assertLess(item.properties["raid"], 1.0)
        club = _learn(world, "tomas", "garrote", type="melee")
        self.assertGreater(world.registries.items.get(club.item_id).properties["damage"], item.properties["damage"])
        # One that keeps them off altogether, to see it tell on what a raid costs.
        sure = replace(item, properties={**item.properties, "damage": 5.0, "raid": 0.0})
        world.registries.items.replace(sure)
        tomas = world.residents["tomas"]
        tomas.inventory.items.clear()
        world.stock(tomas.inventory, sure.item_id, 1, "tomas")
        raid_id = next(
            event_id for event_id, event in world.registries.world_events.events.items() if event.kind == "raid"
        )
        for _ in range(40):
            world.under_raid = raid_id
            world.happenings.answer_raid(world, tomas, STAND_GROUND)
        self.assertEqual(tomas.health, 100.0)

    def test_whoever_knows_of_a_place_goes_there_in_its_turn_for_what_it_gives(self) -> None:
        world = _settled()
        waiting = _level_up(world, "sergio")
        self.assertEqual(
            [option.option_id for option in world.crafts.options(world, waiting)["brings"]],
            ["food", "scrap", "fuel", "medicine"],
        )
        self.assertTrue(world.name_discovery(waiting.discovery_id, "El Vertedero", {"brings": "scrap"}).ok)
        self.assertIsNone(waiting.item_id, "a place is no thing")
        sergio = world.residents["sergio"]
        job = world.registries.jobs["scavenger"]
        trips = {}
        for day in (1, 2):
            world.clock.day = day
            sergio.expedition = None
            world.expeditions.set_out(world, sergio, job)
            trips[day] = sergio.expedition
        self.assertEqual(trips[1].fetch, "scrap")
        self.assertIsNone(trips[2].fetch, "and a day in between for wherever their feet take them")
        self.assertEqual((trips[1].place, trips[2].place), (waiting.discovery_id, None), "a trip says where it is bound")
        self.assertTrue(any("hacia El Vertedero" in line for line in world.event_log))


class TeachingTests(unittest.TestCase):
    def _side_by_side(self, world: SimulationWorld, one: str, other: str) -> None:
        first, second = world.residents[one], world.residents[other]
        second.x, second.y = first.x + 1, first.y
        first.activity = second.activity = None

    def _minutes(self, world: SimulationWorld, minutes: int) -> None:
        for _ in range(minutes):
            world.clock.advance_minutes(1)
            world.crafts.tick(world)

    def test_whoever_holds_the_same_job_learns_it_by_being_near_long_enough(self) -> None:
        world = _settled()
        tomato = _learn(world, "raul", "tomate")
        self._side_by_side(world, "raul", "ines")
        needed = world.registries.crafts.teach_minutes
        self._minutes(world, needed - 20)
        ines = world.residents["ines"]
        self.assertNotIn(tomato.discovery_id, ines.makes)
        self.assertGreater(ines.lessons[tomato.discovery_id], 0.0)
        self._minutes(world, 30)
        self.assertEqual(ines.makes, {tomato.discovery_id: world.clock.day})
        self.assertEqual(ines.lessons, {})
        self.assertEqual(_types(world)[-1], TAUGHT_EVENT)
        self.assertIn("Raúl enseña a Inés lo que sabe: tomate", world.event_log[-1])
        self.assertTrue(any("Raúl me enseñó" in memory.text for memory in world.memories.of("ines")))
        products = world.crafts.products(world, ines, world.registries.jobs["farmer"])
        self.assertEqual([product.item_id for product in products], [tomato.item_id])

    def test_nobody_learns_what_is_none_of_their_job_or_from_far_off(self) -> None:
        world = _settled()
        tomato = _learn(world, "raul", "tomate")
        self._side_by_side(world, "raul", "marta")
        ines = world.residents["ines"]
        ines.x, ines.y = world.residents["raul"].x + 20, world.residents["raul"].y
        self._minutes(world, world.registries.crafts.teach_minutes * 2)
        self.assertNotIn(tomato.discovery_id, world.residents["marta"].makes, "a cook is no farmer")
        self.assertNotIn(tomato.discovery_id, ines.makes, "and from across the settlement nothing is picked up")
        self.assertEqual(ines.lessons, {})

    def test_what_nobody_has_named_cannot_be_shown_to_anybody(self) -> None:
        world = _settled()
        _level_up(world, "raul")
        self._side_by_side(world, "raul", "ines")
        self._minutes(world, world.registries.crafts.teach_minutes * 2)
        self.assertEqual(world.residents["ines"].makes, {})

    def test_a_tree_shown_to_somebody_is_theirs_to_wait_for(self) -> None:
        world = _settled()
        lemon = _learn(world, "raul", "limones", grows="tree")
        world.clock.day += 30
        job = world.registries.jobs["farmer"]
        self.assertTrue(world.crafts.products(world, world.residents["raul"], job)[0].ripe)
        self._side_by_side(world, "raul", "ines")
        self._minutes(world, world.registries.crafts.teach_minutes + 10)
        ines = world.residents["ines"]
        self.assertIn(lemon.discovery_id, ines.makes)
        self.assertFalse(world.crafts.products(world, ines, job)[0].ripe)

    def test_what_only_one_knew_is_lost_with_them(self) -> None:
        world = _settled()
        tomato = _learn(world, "raul", "tomate")
        waiting = _level_up(world, "raul", 3)
        world.stock(world.containers["pantry_1"], tomato.item_id, 5, None)
        world.health.die(world, world.residents["raul"], "una prueba")
        self.assertIn(LOST_EVENT, _types(world))
        self.assertTrue(any("Con Raúl se pierde lo que sabía: tomate" in line for line in world.event_log))
        self.assertEqual(world.crafts.knowers(world, tomato.discovery_id), [])
        self.assertIsNotNone(world.registries.items.find(tomato.item_id), "the thing is still what it was")
        self.assertEqual(world.containers["pantry_1"].count(tomato.item_id), 5)
        self.assertNotIn(waiting.discovery_id, world.discoveries, "and what they had not named is forgotten")
        self.assertEqual(world.crafts.waiting(world), [])

    def test_what_somebody_else_knows_too_is_not_lost(self) -> None:
        world = _settled()
        tomato = _learn(world, "raul", "tomate")
        world.residents["ines"].makes[tomato.discovery_id] = world.clock.day
        world.health.die(world, world.residents["raul"], "una prueba")
        self.assertNotIn(LOST_EVENT, _types(world))
        self.assertEqual([each.resident_id for each in world.crafts.knowers(world, tomato.discovery_id)], ["ines"])


class SaveTests(unittest.TestCase):
    def test_what_was_come_to_and_who_knows_it_come_back(self) -> None:
        world = _settled()
        tomato = _learn(world, "raul", "tomate", grows="vine")
        waiting = _level_up(world, "ines")
        place = _learn(world, "sergio", "El Vertedero", brings="scrap")
        world.residents["ines"].lessons[tomato.discovery_id] = 120.0
        world.residents["paco"].dosed_with = "medicine"
        world.stock(world.containers["pantry_1"], tomato.item_id, 3, None)
        manager = SaveManager()
        saved = manager.to_data(world)
        self.assertEqual(saved["version"], manager.CURRENT_VERSION)
        loaded = manager.from_data(json.loads(json.dumps(saved)))
        self.assertEqual(loaded.discoveries, world.discoveries)
        self.assertEqual(loaded.discovery_count, world.discovery_count)
        for resident_id in ("raul", "ines", "sergio", "paco"):
            mine, theirs = loaded.residents[resident_id], world.residents[resident_id]
            self.assertEqual((mine.trade, mine.makes, mine.lessons, mine.dosed_with), (theirs.trade, theirs.makes, theirs.lessons, theirs.dosed_with))
        self.assertEqual(loaded.registries.items.get(tomato.item_id), world.registries.items.get(tomato.item_id))
        self.assertEqual(loaded.containers["pantry_1"].count(tomato.item_id), 3)
        self.assertEqual([each.discovery_id for each in loaded.crafts.waiting(loaded)], [waiting.discovery_id])
        self.assertIsNone(loaded.discoveries[place.discovery_id].item_id)
        again = _level_up(loaded, "marta")
        self.assertEqual(again.discovery_id, f"discovery_{world.discovery_count + 1}", "and the count goes on")

    def test_a_save_from_before_has_everybody_starting_their_job_anew(self) -> None:
        world = _settled()
        saved = SaveManager().to_data(world)
        saved["version"] = 36
        saved.pop("discoveries")
        saved.pop("discovery_count")
        for resident in saved["residents"]:
            for name in ("trade", "makes", "lessons", "dosed_with"):
                resident.pop(name)
        loaded = SaveManager().from_data(json.loads(json.dumps(saved)))
        raul = loaded.residents["raul"]
        self.assertEqual((raul.trade, raul.makes, raul.lessons, raul.dosed_with), ({}, {}, {}, None))
        self.assertEqual((loaded.discoveries, loaded.discovery_count), ({}, 0))
        self.assertEqual(loaded.crafts.level(loaded, raul, "farmer"), 1)

    def test_what_a_save_says_was_known_of_something_gone_is_forgotten(self) -> None:
        world = _settled()
        tomato = _learn(world, "raul", "tomate")
        saved = SaveManager().to_data(world)
        saved["discoveries"] = []
        loaded = SaveManager().from_data(json.loads(json.dumps(saved)))
        self.assertEqual(loaded.residents["raul"].makes, {})
        self.assertIsNone(loaded.registries.items.find(tomato.item_id))


if __name__ == "__main__":
    unittest.main()
