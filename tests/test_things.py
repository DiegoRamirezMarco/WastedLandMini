import json
import logging
import tempfile
import unittest
from pathlib import Path

from save.save_manager import SaveManager
from simulation.events.event import DomainEvent
from simulation.items.custom_content import load_custom_items, validate_item_data
from simulation.items.inventory import Inventory
from simulation.items.item import ItemDefinition, ItemInstance
from simulation.items.item_system import (
    STEAL_ACTION,
    THEFT_COOLDOWN_MINUTES,
    USE_ITEM_ACTION,
    ItemSystem,
)
from simulation.items.registry import UNKNOWN_CATEGORY, ItemRegistry
from simulation.knowledge.knowledge_system import share_rumor
from simulation.registries import DATA_DIR, BuiltInRegistries, builtin_registries
from simulation.residents.activity import Activity
from simulation.residents.needs import Needs
from simulation.world import SimulationWorld

MINUTES_PER_DAY = 24 * 60
VALID = {"id": "x", "name": "X", "article": "un", "category": "gift"}


def _quieten(world: SimulationWorld) -> SimulationWorld:
    """Leave only Marta, Raúl and Lucía, with no jobs, no feelings, no needs and no cooked food about."""
    for extra in [rid for rid in world.residents if rid not in ("marta", "raul", "lucia")]:
        del world.residents[extra]
    world.relationships.clear()
    for resident in world.residents.values():
        resident.needs = Needs(hunger=0, tiredness=0, social=0, stress=0)
        resident.job_id = resident.post_id = None
    if "cooking_pot" in world.containers:
        world.containers["cooking_pot"].items.clear()
    return world


def _calm_world(seed: int = 7) -> SimulationWorld:
    """The demo settlement with nobody hungry, tired, lonely or angry, and nobody up to anything."""
    return _quieten(SimulationWorld.demo_world(seed=seed))


def _calm_world_with(registries: BuiltInRegistries) -> SimulationWorld:
    world = _quieten(SimulationWorld.demo_world(registries=registries))
    for resident in world.residents.values():
        resident.inventory.items.clear()
    return world


def _place(world: SimulationWorld, resident_id: str, tile: tuple[int, int]) -> None:
    world.residents[resident_id].x, world.residents[resident_id].y = tile


def _types(world: SimulationWorld) -> list[str]:
    return [line.split(" | ")[1] for line in world.event_log]


def _radio(world: SimulationWorld) -> ItemInstance:
    return world.containers["crate_dorm"].items[0]


def _let_raul_steal_the_radio(world: SimulationWorld, watcher_inside: bool = False) -> None:
    """Raúl resents Marta and takes her radio from the dormitory crate."""
    world.relationship("raul", "marta").resentment = 60
    _place(world, "raul", (8, 5))
    _place(world, "marta", (30, 14))
    _place(world, "lucia", (8, 6) if watcher_inside else (30, 15))
    if watcher_inside:
        # Plan the theft before anyone is looking; Lucía walks in while it happens.
        _place(world, "lucia", (30, 15))
        world.step(1)
        _place(world, "lucia", (8, 6))
    world.residents["lucia"].activity = Activity("wander", minutes_left=60, using=True)
    world.residents["marta"].activity = Activity("wander", minutes_left=60, using=True)
    for _ in range(30):
        world.step(1)
        if world.thefts:
            return
    raise AssertionError("no theft happened")


class InventoryTests(unittest.TestCase):
    def test_a_stack_shrinks_one_unit_at_a_time_and_goes_when_empty(self) -> None:
        inventory = Inventory([ItemInstance("item_1", "canned_beans", quantity=2)])
        self.assertEqual(inventory.count("canned_beans"), 2)
        self.assertTrue(inventory.take_unit("item_1"))
        self.assertEqual(inventory.count("canned_beans"), 1)
        self.assertTrue(inventory.take_unit("item_1"))
        self.assertEqual(inventory.items, [])
        self.assertFalse(inventory.take_unit("item_1"))

    def test_stacks_are_kept_apart_by_owner(self) -> None:
        world = _calm_world()
        pantry = world.containers["pantry_1"]
        shared = pantry.count("canned_beans")
        world.stock(pantry, "canned_beans", 3, None)
        world.stock(pantry, "canned_beans", 2, "raul")
        self.assertEqual(pantry.count("canned_beans"), shared + 5)
        self.assertEqual(pantry.stack_of("canned_beans", "raul").quantity, 2)
        self.assertEqual(pantry.stack_of("canned_beans", None).quantity, shared + 3)

    def test_new_items_get_fresh_stable_ids(self) -> None:
        world = _calm_world()
        ids = {item.instance_id for inventory in world.containers.values() for item in inventory.items}
        fresh = world.new_item("canned_beans")
        self.assertNotIn(fresh.instance_id, ids)


class CustomContentTests(unittest.TestCase):
    def setUp(self) -> None:
        logging.disable(logging.WARNING)
        self.addCleanup(logging.disable, logging.NOTSET)
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)

    def _pack(self, folder: str, name: str, content: object) -> None:
        path = self.root / folder / name
        path.mkdir(parents=True, exist_ok=True)
        text = content if isinstance(content, str) else json.dumps(content)
        (path / "data.json").write_text(text, encoding="utf-8")

    def test_valid_packs_load_through_the_same_registry_as_built_in_items(self) -> None:
        registry = ItemRegistry()
        registry.load_collection_json_file(DATA_DIR / "items.json")
        self._pack("items", "lucky_coin", {**VALID, "id": "lucky_coin", "from_the_future": True})
        self._pack("foods", "broth", {**VALID, "id": "broth", "category": "food", "effects": {"hunger": -40}})
        self.assertEqual(sorted(load_custom_items(registry, self.root)), ["broth", "lucky_coin"])
        self.assertEqual(registry.get("broth").effects, {"hunger": -40.0})
        self.assertIsInstance(registry.get("lucky_coin"), type(registry.get("canned_beans")))

    def test_malformed_packs_are_skipped_without_stopping_the_game(self) -> None:
        bad = {
            "Bad-Id": {**VALID, "id": "Bad-Id"},
            "wrong_folder": {**VALID, "id": "something_else"},
            "no_name": {"id": "no_name", "article": "un", "category": "gift"},
            "negative": {**VALID, "id": "negative", "base_value": -5},
            "bool_value": {**VALID, "id": "bool_value", "base_value": True},
            "bad_tags": {**VALID, "id": "bad_tags", "tags": "shiny"},
            "bad_effects": {**VALID, "id": "bad_effects", "effects": {"hunger": "lots"}},
            "a_list": [1, 2, 3],
            "not_json": "{ this is not json",
            "canned_beans": {**VALID, "id": "canned_beans"},
        }
        for name, content in bad.items():
            self._pack("items", name, content)
        self._pack("foods", "not_food", {**VALID, "id": "not_food"})
        self._pack("items", "huge", {**VALID, "id": "huge", "description": "x" * 70_000})
        (self.root / "items" / "empty_folder").mkdir()
        self._pack("items", "fine", {**VALID, "id": "fine"})

        registry = ItemRegistry()
        registry.load_collection_json_file(DATA_DIR / "items.json")
        self.assertEqual(load_custom_items(registry, self.root), ["fine"])
        self.assertEqual(registry.get("canned_beans").category, "food", "a pack must not replace a built-in item")

    def test_validation_names_what_is_wrong(self) -> None:
        with self.assertRaisesRegex(ValueError, "folder name"):
            validate_item_data(VALID, "y", None)
        with self.assertRaisesRegex(ValueError, "category"):
            validate_item_data(VALID, "x", "food")
        validate_item_data(VALID, "x", None)

    def test_a_missing_pack_folder_is_not_an_error(self) -> None:
        self.assertEqual(load_custom_items(ItemRegistry(), self.root / "nowhere"), [])

    def test_the_bundled_examples_are_loaded_and_used(self) -> None:
        items = builtin_registries().items
        self.assertEqual(items.get("pizza_radioactiva").category, "food")
        self.assertIn("custom", items.get("peluche_maligno").tags)
        world = SimulationWorld.demo_world()
        world.step(2 * MINUTES_PER_DAY)
        self.assertTrue(any("pizza radiactiva" in line for line in world.event_log))


class FoodTests(unittest.TestCase):
    def setUp(self) -> None:
        self.world = _calm_world()
        self.marta = self.world.residents["marta"]
        self.pantry = self.world.containers["pantry_1"]

    def test_a_meal_takes_one_unit_off_the_shelf_and_lowers_hunger_by_its_effect(self) -> None:
        self.world.containers["pantry_2"].items.clear()
        before = self.pantry.count("canned_beans")
        self.marta.needs.hunger = 80
        for _ in range(240):
            self.world.step(1)
            if self.marta.current_action == "eat":
                break
        self.assertEqual(self.pantry.count("canned_beans"), before - 1)
        hunger = self.marta.needs.hunger
        self.world.step(20)
        self.assertLess(self.marta.needs.hunger, hunger - 20)

    def test_the_tastier_food_is_taken_first(self) -> None:
        self.marta.needs.hunger = 80
        best = self.world.items.best_food(self.world, self.marta, "pantry_2", "food")
        self.assertEqual(best.definition_id, "pizza_radioactiva")

    def test_someone_elses_stash_is_not_food_for_the_taking(self) -> None:
        self.assertIsNone(self.world.items.best_food(self.world, self.marta, "crate_1", "food"))
        raul = self.world.residents["raul"]
        self.assertEqual(self.world.items.best_food(self.world, raul, "crate_1", "food").owner_id, "raul")

    def test_an_empty_pantry_is_not_worth_the_walk(self) -> None:
        for container in self.world.containers.values():
            container.items.clear()
        self.marta.needs.hunger = 95
        self.assertNotEqual(self.world.activities.routine.plan(self.world, self.marta).action, "eat")

    def test_arriving_to_bare_shelves_is_reported_once_a_day(self) -> None:
        self.marta.needs.hunger = 95
        activity = self.world.activities.routine.plan(self.world, self.marta)
        self.assertEqual(activity.action, "eat")
        for container in self.world.containers.values():
            container.items.clear()
        self.marta.activity = activity
        self.world.step(60)
        self.assertEqual(_types(self.world).count("no_food"), 1)
        self.assertNotEqual(self.marta.current_action, "eat")
        self.assertGreater(self.marta.needs.hunger, 95)

    def test_a_map_can_have_supplies_delivered_every_morning(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "data"
            (root / "maps").mkdir(parents=True)
            for path in DATA_DIR.rglob("*.json"):
                text = path.read_text(encoding="utf-8")
                if path.name == "settlement.json":
                    supplies = (
                        '"supplies": [{"container": "pantry_1", "item": "canned_beans", "count": 8, "hour": 7},'
                        ' {"container": "pantry_2", "item": "canned_beans", "count": 7, "hour": 7}],\n  "spawns": ['
                    )
                    text = text.replace('"spawns": [', supplies)
                (root / path.relative_to(DATA_DIR)).write_text(text, encoding="utf-8")
            world = _quieten(SimulationWorld.demo_world(registries=BuiltInRegistries.load(root)))
        for container in world.containers.values():
            container.items.clear()
        world.step(23 * 60)
        self.assertEqual((world.clock.hour, world.clock.minute), (7, 0))
        self.assertEqual(_types(world).count("supplies_arrived"), 2)
        delivered = world.containers["pantry_1"].count("canned_beans") + world.containers["pantry_2"].count("canned_beans")
        self.assertEqual(delivered, 15)

    def test_a_cooked_meal_is_worth_a_longer_walk_than_a_tin(self) -> None:
        self.world.stock(self.world.containers["cooking_pot"], "stew", 3, None)
        self.world.containers["pantry_2"].items.clear()
        self.marta.needs.hunger = 80
        _place(self.world, "marta", (35, 9))
        activity = self.world.activities.routine.plan(self.world, self.marta)
        self.assertEqual((activity.action, activity.target_id), ("eat", "cooking_pot"))

    def test_a_week_of_meals_never_runs_the_settlement_out_of_food(self) -> None:
        world = SimulationWorld.demo_world(seed=3)
        world.step(7 * MINUTES_PER_DAY)
        self.assertNotIn("no_food", _types(world))
        self.assertGreater(sum(c.count("canned_beans") for c in world.containers.values()), 0)


class BelongingsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.world = _calm_world()
        self.items: ItemSystem = self.world.items
        self.lucia = self.world.residents["lucia"]

    def test_a_trait_makes_fitting_things_worth_more(self) -> None:
        radio = self.world.registries.items.get("old_radio")
        marta, raul = self.world.residents["marta"], self.world.residents["raul"]
        self.assertGreater(self.items.personal_value(self.world, marta, radio), self.items.personal_value(self.world, raul, radio))
        self.assertEqual(self.items.personal_value(self.world, raul, radio), radio.base_value)

    def test_a_favourite_food_also_lifts_the_mood(self) -> None:
        sweet = ItemDefinition("cake", "tarta", "una", "food", tags=("sweet",), effects={"hunger": -20})
        plain = self.items.use_effects(self.world, self.world.residents["raul"], sweet)
        loved = self.items.use_effects(self.world, self.lucia, sweet)
        self.assertNotIn("stress", plain)
        self.assertLess(loved["stress"], 0)

    def test_a_stressed_resident_turns_to_something_they_carry_and_keeps_it(self) -> None:
        self.lucia.needs.stress = 90
        # Without a fire to sit by, a radio to listen to or a comforting pizza, the toy is what she has.
        self.world.interactables.pop("campfire")
        self.world.interactables.pop("radio_set")
        self.world.containers["pantry_2"].items.clear()
        self.world.step(1)
        self.assertEqual(self.lucia.activity.action, USE_ITEM_ACTION)
        self.world.step(12)
        self.assertLess(self.lucia.needs.stress, 90)
        self.assertEqual(self.lucia.inventory.count("peluche_maligno"), 1)

    def test_eating_from_ones_own_stash_uses_it_up(self) -> None:
        raul = self.world.residents["raul"]
        for container_id in ("pantry_1", "pantry_2"):
            self.world.containers[container_id].items.clear()
        raul.needs.hunger = 90
        self.world.step(1)
        self.assertEqual((raul.activity.action, raul.activity.target_id), (USE_ITEM_ACTION, "crate_1"))
        while raul.activity is not None and raul.activity.action == USE_ITEM_ACTION:
            self.world.step(1)
        self.assertEqual(self.world.containers["crate_1"].count("canned_beans"), 1)
        self.assertLess(raul.needs.hunger, 75)

    def test_nobody_uses_what_is_not_theirs(self) -> None:
        raul = self.world.residents["raul"]
        raul.needs.stress = 95
        used = [c for c in self.items.candidates(self.world, raul) if c.name == USE_ITEM_ACTION]
        self.assertEqual(used, [])


class GiftAndTradeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.world = _calm_world()
        self.items: ItemSystem = self.world.items
        self.lucia, self.marta = self.world.residents["lucia"], self.world.residents["marta"]
        self.chat = self.world.registries.interactions["chat"]

    def _chat_until(self, giver, receiver, happened) -> None:
        for _ in range(200):
            self.items.after_exchange(self.world, giver, receiver, self.chat)
            if happened():
                return
        raise AssertionError("nothing changed hands")

    def test_a_gift_changes_owner_and_warms_the_one_who_receives_it(self) -> None:
        self.world.relationship("lucia", "marta").affection = 60
        before = self.world.relationship("marta", "lucia").affection
        self._chat_until(self.lucia, self.marta, lambda: self.marta.inventory.items)
        gift = self.marta.inventory.items[0]
        self.assertEqual((gift.definition_id, gift.owner_id), ("peluche_maligno", "marta"))
        self.assertEqual(self.lucia.inventory.items, [])
        self.assertGreater(self.world.relationship("marta", "lucia").affection, before)
        self.assertIn("gift_given", _types(self.world))
        self.assertIn("me regaló", self.world.memories.of("marta")[-1].text)
        self.assertIn("Le regalé", self.world.memories.of("lucia")[-1].text)

    def test_no_gift_without_fondness_and_none_from_the_grasping(self) -> None:
        for _ in range(200):
            self.items.after_exchange(self.world, self.lucia, self.marta, self.chat)
        self.assertEqual(self.marta.inventory.items, [])
        self.world.relationship("lucia", "marta").affection = 90
        self.lucia.personality.greed = 90
        for _ in range(200):
            self.items.after_exchange(self.world, self.lucia, self.marta, self.chat)
        self.assertEqual(self.marta.inventory.items, [])

    def test_a_swap_happens_only_when_one_gains_and_the_other_does_not_lose(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            pack = Path(tmp) / "items" / "silver_ring"
            pack.mkdir(parents=True)
            ring = {"id": "silver_ring", "name": "anillo de plata", "article": "un", "category": "gift", "base_value": 40}
            (pack / "data.json").write_text(json.dumps(ring), encoding="utf-8")
            world = _calm_world_with(BuiltInRegistries.load(DATA_DIR, custom_dir=tmp))
        items, marta, lucia = world.items, world.residents["marta"], world.residents["lucia"]
        radio = world.containers["crate_dorm"].remove(_radio(world).instance_id)
        radio.owner_id = "lucia"
        lucia.inventory.add(radio)
        ring_item = world.new_item("silver_ring", owner_id="marta")
        marta.inventory.add(ring_item)

        # Marta loves music: the radio is worth 52 to her and the ring 40. To Lucía the ring is worth more.
        offer = items.propose_trade(world, marta, lucia)
        self.assertEqual((offer.offered_instance_ids, offer.requested_instance_ids), ([ring_item.instance_id], [radio.instance_id]))

        items.after_exchange(world, marta, lucia, world.registries.interactions["chat"])
        self.assertEqual([(i.definition_id, i.owner_id) for i in marta.inventory.items], [("old_radio", "marta")])
        self.assertEqual([(i.definition_id, i.owner_id) for i in lucia.inventory.items], [("silver_ring", "lucia")])
        self.assertIn("trade_made", _types(world))

    def test_no_swap_that_would_leave_someone_worse_off(self) -> None:
        radio = self.world.containers["crate_dorm"].remove(_radio(self.world).instance_id)
        radio.owner_id = "lucia"
        self.lucia.inventory.items.clear()
        self.lucia.inventory.add(radio)
        self.marta.inventory.add(self.world.new_item("canned_beans", owner_id="marta"))
        self.assertIsNone(self.items.propose_trade(self.world, self.marta, self.lucia))


class TheftTests(unittest.TestCase):
    def setUp(self) -> None:
        self.world = _calm_world()
        self.items: ItemSystem = self.world.items
        self.raul, self.marta = self.world.residents["raul"], self.world.residents["marta"]
        self.radio_definition = self.world.registries.items.get("old_radio")

    def test_a_grudge_and_greed_tempt_and_empathy_holds_back(self) -> None:
        tempt = lambda: self.items.temptation(self.world, self.raul, self.marta, self.radio_definition)
        self.assertEqual(tempt(), 0.0)
        self.world.relationship("raul", "marta").resentment = 60
        grudge = tempt()
        self.assertGreater(grudge, 0.0)
        self.raul.personality.greed = 90
        self.assertGreater(tempt(), grudge)
        self.raul.personality.empathy = 100
        self.assertLess(tempt(), self.items.temptation(self.world, self.raul, self.marta, self.radio_definition) + 1)
        self.raul.personality.greed = 50
        self.assertLess(tempt(), grudge)

    def test_nobody_steals_while_someone_is_watching_the_spot(self) -> None:
        self.world.relationship("raul", "marta").resentment = 60
        _place(self.world, "raul", (8, 5))
        steals = lambda: [c for c in self.items.candidates(self.world, self.raul) if c.name == STEAL_ACTION]
        _place(self.world, "lucia", (30, 15))
        _place(self.world, "marta", (30, 14))
        self.assertEqual([c.item_id for c in steals()], [_radio(self.world).instance_id])
        _place(self.world, "lucia", (8, 6))
        self.assertEqual(steals(), [])

    def test_the_thing_changes_hands_but_not_owner_and_the_thief_lies_low(self) -> None:
        radio = _radio(self.world)
        _let_raul_steal_the_radio(self.world)
        self.assertEqual(self.world.containers["crate_dorm"].items, [])
        self.assertIs(self.raul.inventory.find(radio.instance_id), radio)
        self.assertEqual(radio.owner_id, "marta")
        attempt = self.world.thefts[0]
        self.assertEqual((attempt.thief_id, attempt.victim_id, attempt.container_id), ("raul", "marta", "crate_dorm"))
        self.assertFalse(attempt.discovered)
        self.assertIn("theft_committed", _types(self.world))

        fact = self.world.knowledge.facts[attempt.fact_id]
        self.assertEqual(fact.subject_ids, ["raul", "marta"])
        self.assertTrue(self.world.knowledge.knows("raul", fact.fact_id))
        self.assertFalse(self.world.knowledge.knows("marta", fact.fact_id))
        steals = [c for c in self.items.candidates(self.world, self.raul) if c.name == STEAL_ACTION]
        self.assertEqual(steals, [], "no second theft the same day")
        self.assertEqual(self.world.theft_cooldowns["raul"] + THEFT_COOLDOWN_MINUTES > self.world.clock.total_minutes, True)

    def test_the_thief_never_volunteers_what_they_did(self) -> None:
        _let_raul_steal_the_radio(self.world)
        for _ in range(200):
            self.assertIsNone(share_rumor(self.world, self.raul, self.world.residents["lucia"]))

    def test_an_undiscovered_theft_leaves_the_victim_none_the_wiser_about_who(self) -> None:
        _let_raul_steal_the_radio(self.world)
        self.assertEqual(self.world.relationships.get(("marta", "raul")), None)
        self.marta.activity = None
        _place(self.world, "marta", (8, 5))
        self.world.step(1)
        attempt = self.world.thefts[0]
        self.assertTrue(attempt.noticed)
        self.assertIn("theft_noticed", _types(self.world))
        self.assertGreater(self.marta.needs.stress, 0)
        self.assertIn("Eché en falta una radio vieja.", [m.text for m in self.world.memories.of("marta")])
        feelings = self.world.relationships.get(("marta", "raul"))
        self.assertTrue(feelings is None or feelings.resentment == 0)
        self.world.step(30)
        self.assertEqual(_types(self.world).count("theft_noticed"), 1)

    def test_a_discovered_theft_turns_the_victim_against_the_thief(self) -> None:
        _let_raul_steal_the_radio(self.world)
        attempt = self.world.thefts[0]
        fact = self.world.knowledge.facts[attempt.fact_id]
        lucia = self.world.residents["lucia"]
        from simulation.knowledge.fact import SOURCE_WITNESS
        from simulation.knowledge.knowledge_system import learn

        learn(self.world, lucia, fact, 1.0, SOURCE_WITNESS)
        self.assertGreater(self.world.relationship("lucia", "raul").resentment, 0)
        self.assertEqual(self.world.relationship("lucia", "marta").resentment, 0, "the victim is not blamed")

        self.assertEqual(self.world.relationship("marta", "raul").resentment, 0)
        for _ in range(200):
            if share_rumor(self.world, lucia, self.marta) is not None:
                break
        told = self.world.knowledge.belief("marta", fact.fact_id)
        self.assertEqual(told.told_by, "lucia")
        feelings = self.world.relationship("marta", "raul")
        self.assertGreater(feelings.resentment, 10)
        self.assertLess(feelings.trust, -10)
        self.assertGreater(feelings.resentment, self.world.relationship("lucia", "raul").resentment)

    def test_a_theft_seen_by_its_victim_is_discovered_on_the_spot(self) -> None:
        self.world.relationship("raul", "marta").resentment = 60
        _place(self.world, "raul", (8, 4))
        _place(self.world, "lucia", (30, 15))
        _place(self.world, "marta", (30, 14))
        self.world.step(1)
        self.assertEqual(self.raul.activity.action, STEAL_ACTION)
        _place(self.world, "marta", (8, 6))
        self.marta.activity = Activity("wander", minutes_left=60, using=True)
        self.world.step(10)
        attempt = self.world.thefts[0]
        self.assertTrue(attempt.discovered)
        self.assertGreater(self.world.relationship("marta", "raul").resentment, 15)
        self.assertGreater(self.marta.needs.stress, 0)

    def test_making_peace_brings_the_stolen_thing_back(self) -> None:
        radio = _radio(self.world)
        _let_raul_steal_the_radio(self.world)
        heart_to_heart = self.world.registries.interactions["heart_to_heart"]
        self.items.after_exchange(self.world, self.raul, self.marta, heart_to_heart)
        self.assertIs(self.marta.inventory.find(radio.instance_id), radio)
        self.assertIsNone(self.raul.inventory.find(radio.instance_id))
        attempt = self.world.thefts[0]
        self.assertTrue(attempt.returned and attempt.discovered)
        self.assertIn("item_returned", _types(self.world))
        self.assertTrue(self.world.knowledge.knows("marta", attempt.fact_id))
        self.assertEqual(self.world.relationship("marta", "raul").resentment, 0, "no fresh anger over what was given back")
        self.marta.activity = None
        _place(self.world, "marta", (8, 5))
        self.world.step(1)
        self.assertNotIn("theft_noticed", _types(self.world))

    def test_an_ordinary_chat_returns_nothing(self) -> None:
        _let_raul_steal_the_radio(self.world)
        self.items.after_exchange(self.world, self.raul, self.marta, self.world.registries.interactions["chat"])
        self.assertFalse(self.world.thefts[0].returned)


class ItemSaveTests(unittest.TestCase):
    def setUp(self) -> None:
        logging.disable(logging.WARNING)
        self.addCleanup(logging.disable, logging.NOTSET)
        self.manager = SaveManager()

    def test_items_thefts_and_traits_survive_saving_and_the_run_stays_identical(self) -> None:
        original = SimulationWorld.demo_world(seed=7)
        original.step(2 * MINUTES_PER_DAY)
        self.assertTrue(original.thefts)
        loaded = self.manager.from_data(json.loads(json.dumps(self.manager.to_data(original))))
        self.assertEqual(self.manager.to_data(loaded), self.manager.to_data(original))
        self.assertEqual(loaded.residents["marta"].traits, ["music_lover"])
        original.step(3 * MINUTES_PER_DAY)
        loaded.step(3 * MINUTES_PER_DAY)
        self.assertEqual(self.manager.to_data(loaded), self.manager.to_data(original))

    def test_a_save_that_references_removed_custom_content_still_loads(self) -> None:
        world = SimulationWorld.demo_world()
        self.assertEqual(world.containers["pantry_2"].count("pizza_radioactiva"), 3)
        self.assertEqual(world.residents["lucia"].inventory.count("peluche_maligno"), 1)
        data = json.loads(json.dumps(self.manager.to_data(world)))

        without_packs = BuiltInRegistries.load(DATA_DIR)
        self.assertIsNone(without_packs.items.find("pizza_radioactiva"))
        loaded = self.manager.from_data(data, without_packs)
        pizza = loaded.containers["pantry_2"].stack_of("pizza_radioactiva", None)
        self.assertEqual(pizza.quantity, 3)
        placeholder = loaded.registries.items.resolve("pizza_radioactiva")
        self.assertEqual((placeholder.category, placeholder.effects), (UNKNOWN_CATEGORY, {}))
        self.assertEqual(loaded.residents["lucia"].inventory.count("peluche_maligno"), 1)

        loaded.step(2 * MINUTES_PER_DAY)
        self.assertEqual(loaded.containers["pantry_2"].count("pizza_radioactiva"), 3, "nobody eats what they cannot recognise")
        self.assertEqual(loaded.residents["lucia"].inventory.count("peluche_maligno"), 1)

        restored = self.manager.from_data(json.loads(json.dumps(self.manager.to_data(loaded))))
        self.assertEqual(restored.registries.items.resolve("pizza_radioactiva").category, "food")
        self.assertEqual(restored.containers["pantry_2"].count("pizza_radioactiva"), 3)

    def test_a_save_from_before_items_gets_the_maps_starting_stock(self) -> None:
        world = SimulationWorld.demo_world()
        data = self.manager.to_data(world)
        data["version"] = 4
        for key in ("containers", "item_count", "thefts", "theft_cooldowns", "notices"):
            del data[key]
        for resident in data["residents"]:
            del resident["inventory"]
            del resident["traits"]
        loaded = self.manager.from_data(data)
        self.assertGreater(loaded.containers["pantry_1"].count("canned_beans"), 0)
        self.assertEqual(loaded.residents["marta"].traits, [])
        loaded.step(MINUTES_PER_DAY)
        self.assertNotIn("no_food", _types(loaded))

    def test_things_in_a_container_that_is_gone_return_to_their_owner(self) -> None:
        world = SimulationWorld.demo_world()
        data = self.manager.to_data(world)
        data["interactables"] = [placed for placed in data["interactables"] if placed["id"] != "crate_dorm"]
        loaded = self.manager.from_data(data)
        self.assertNotIn("crate_dorm", loaded.containers)
        self.assertEqual(loaded.residents["marta"].inventory.count("old_radio"), 1)
        fresh = loaded.new_item("canned_beans")
        everything = [i.instance_id for c in loaded.containers.values() for i in c.items]
        self.assertNotIn(fresh.instance_id, everything)
        loaded.step(MINUTES_PER_DAY)


class MapDataTests(unittest.TestCase):
    def test_stock_in_something_that_is_not_a_container_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "data"
            (root / "maps").mkdir(parents=True)
            for path in DATA_DIR.rglob("*.json"):
                text = path.read_text(encoding="utf-8")
                if path.name == "settlement.json":
                    text = text.replace('{"container": "pantry_2", "item": "pizza', '{"container": "table", "item": "pizza')
                (root / path.relative_to(DATA_DIR)).write_text(text, encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "not a container"):
                BuiltInRegistries.load(root)


if __name__ == "__main__":
    unittest.main()
