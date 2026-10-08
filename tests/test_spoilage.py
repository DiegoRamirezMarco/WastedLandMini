"""What goes off (S65): how fast, what is left of it, the chest that keeps it longer, and
compost on a bed."""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from save.save_manager import SaveManager
from simulation.commands import CompostCommand, SwitchCommand
from simulation.economy.ledger import SPOILED
from simulation.economy.spoilage import ALREADY_DRESSED, DRESSED_EVENT, NOT_A_BED, WENT_OFF_EVENT
from simulation.items.custom_content import merged_item_data, validate_item_data
from simulation.items.inventory import Inventory
from simulation.registries import DATA_DIR, BuiltInRegistries
from simulation.work import hauling
from simulation.world import SimulationWorld
from tests.worlds import no_store
from world.interactable import Interactable

ROOT = Path(__file__).resolve().parent.parent
HOUR = 60
DAY = 24 * HOUR
CHEST = "chest"
STORE = "warehouse"


def _empty(seed: int = 7) -> SimulationWorld:
    """The settlement that comes ready made with nobody in it and nothing kept anywhere: what is
    put in a place stays there, but for what the store and time do with it."""
    world = SimulationWorld.demo_world(seed=seed)
    world.residents.clear()
    for inventory in world.containers.values():
        inventory.items.clear()
    world.clock.hour, world.clock.minute = 8, 0
    return world


def _with_chest(world: SimulationWorld) -> Inventory:
    """Stand a refrigerated chest in the open, with fuel in the generator for it."""
    world.interactables[CHEST] = Interactable(CHEST, "refrigerated_chest", 0, 0)
    world.containers[CHEST] = Inventory()
    world.stock(world.containers["generator"], "fuel", 4, None)
    return world.containers[CHEST]


def _stacks(inventory: Inventory, item_id: str) -> list[tuple[int, float]]:
    return [(item.quantity, round(item.freshness, 1)) for item in inventory.items if item.definition_id == item_id]


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
    def test_how_fast_a_thing_goes_off_is_data_on_it_and_most_keep(self) -> None:
        world = SimulationWorld.demo_world()
        items = world.registries.items
        self.assertEqual((items.get("vegetables").spoils, items.get("stew").spoils, items.get("medicine").spoils), (20, 34, 1))
        for kept in ("canned_beans", "water", "fuel", "scrap", "liquor", "hoe", "compost"):
            self.assertEqual(items.get(kept).spoils, 0, kept)
            self.assertFalse(world.spoilage.goes_off(world, kept))
        settings = world.registries.spoilage
        self.assertEqual((settings.becomes, settings.compost, settings.compost_on), ("compost", "compost", ("crop_bed",)))
        chest = world.registries.interactables.get("refrigerated_chest")
        self.assertEqual((chest.chill, chest.draws, chest.store, chest.container), (0.25, 1, {"food": 40}, True))
        self.assertIsNotNone(chest.build, "it is something to build")

    def test_data_that_makes_no_sense_is_refused(self) -> None:
        def negative(data) -> None:
            next(item for item in data if item["id"] == "stew")["spoils"] = -1

        def into_nothing(data) -> None:
            data["becomes"] = "ashes"

        def on_nothing(data) -> None:
            data["compost"]["on"] = ["flower_pot"]

        def no_days(data) -> None:
            data["compost"]["units"] = 0

        def chills_nothing(data) -> None:
            data["lamp"]["chill"] = 0.5

        def freezes_time(data) -> None:
            data["refrigerated_chest"]["chill"] = 0

        with self.assertRaises(ValueError):
            _registries_with("items.json", negative)
        for change in (into_nothing, on_nothing, no_days):
            with self.assertRaises(ValueError):
                _registries_with("spoilage.json", change)
        for change in (chills_nothing, freezes_time):
            with self.assertRaises(ValueError):
                _registries_with("interactables.json", change)

    def test_a_pack_that_changes_a_thing_leaves_how_fast_it_goes_off_unless_it_says(self) -> None:
        stew = SimulationWorld.demo_world().registries.items.get("stew")
        self.assertEqual(merged_item_data({"id": "stew", "name": "potaje"}, stew)["spoils"], 34)
        self.assertEqual(merged_item_data({"id": "stew", "spoils": 5}, stew)["spoils"], 5)
        validate_item_data({"id": "stew", "spoils": 0}, "stew", None, stew)
        for wrong in (-1, "soon"):
            with self.assertRaises(ValueError):
                validate_item_data({"id": "stew", "spoils": wrong}, "stew", None, stew)

    def test_a_settlement_with_no_such_data_has_nothing_go_off(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            for path in DATA_DIR.rglob("*.json"):
                if path.name == "spoilage.json":
                    continue
                target = root / path.relative_to(DATA_DIR)
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
            registries = BuiltInRegistries.load(root)
        self.assertIsNone(registries.spoilage.becomes)
        self.assertFalse(registries.spoilage.dresses)

    def test_it_needs_no_pygame(self) -> None:
        code = (
            "import sys; from simulation.world import SimulationWorld; "
            "from simulation.commands import CompostCommand; world = SimulationWorld.demo_world(); "
            "world.step(60 * 24 * 6); world.apply_command(CompostCommand('crop_1')); "
            "print('pygame' in sys.modules)"
        )
        result = subprocess.run([sys.executable, "-c", code], cwd=ROOT, capture_output=True, text=True, check=True)
        self.assertEqual(result.stdout.strip().splitlines()[-1], "False")


class GoingOffTests(unittest.TestCase):
    def setUp(self) -> None:
        self.world = no_store(_empty())
        self.crate = self.world.containers["crate_dorm"]

    def test_it_loses_its_freshness_by_the_hour_and_what_keeps_does_not(self) -> None:
        world = self.world
        greens = world.stock(self.crate, "vegetables", 6, None)
        tins = world.stock(self.crate, "canned_beans", 6, None)
        self.assertEqual((greens.freshness, tins.freshness), (100.0, 100.0))
        self.assertAlmostEqual(world.spoilage.days_left(world, greens), 5.0)
        self.assertIsNone(world.spoilage.days_left(world, tins))
        world.step(DAY)
        self.assertAlmostEqual(greens.freshness, 80.0)
        self.assertEqual(tins.freshness, 100.0)
        world.step(DAY * 2 + 12 * HOUR)
        self.assertAlmostEqual(greens.freshness, 30.0)
        self.assertAlmostEqual(world.spoilage.days_left(world, greens), 1.5)

    def test_with_none_left_it_has_gone_off_and_is_compost_and_it_is_said_and_written_down(self) -> None:
        world = self.world
        world.stock(self.crate, "stew", 4, None)
        world.stock(self.crate, "vegetables", 3, None)
        written = world.ledger.written
        world.events.drain()
        # A stew has a little under three days in it: seventy hours and a bit.
        world.step(70 * HOUR)
        self.assertEqual(self.crate.count("stew"), 4)
        world.step(HOUR)
        self.assertEqual((self.crate.count("stew"), self.crate.count("compost"), self.crate.count("vegetables")), (0, 4, 3))
        events = [event for event in world.events.drain() if event.event_type == WENT_OFF_EVENT]
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].data["items"], {"stew": 4})
        self.assertIn("4 de guiso caliente", events[0].text)
        entries = list(world.ledger.recent)[-(world.ledger.written - written):]
        self.assertEqual([(entry.definition_id, entry.units, entry.why) for entry in entries], [("stew", -4, SPOILED)])
        world.step(DAY * 2)
        self.assertEqual(self.crate.count("vegetables"), 3, "a day short of its five")
        world.step(HOUR)
        self.assertEqual((self.crate.count("vegetables"), self.crate.count("compost")), (0, 7))
        self.assertEqual(world.spoilage.compost_held(world), 7)
        self.assertEqual([item.freshness for item in self.crate.items], [100.0], "compost keeps")

    def test_what_is_somebodys_goes_off_too_and_is_no_loss_of_the_settlements(self) -> None:
        world = SimulationWorld.demo_world()
        no_store(world)
        marta = world.residents["marta"]
        for resident in list(world.residents.values()):
            if resident is not marta:
                del world.residents[resident.resident_id]
        for inventory in world.containers.values():
            inventory.items.clear()
        marta.inventory.items.clear()
        mine = world.stock(marta.inventory, "stew", 2, "marta")
        mine.freshness = 1.0
        written = world.ledger.written
        world.clock.minute = 59
        world.step(1)
        self.assertEqual(marta.inventory.count("stew"), 0)
        self.assertEqual(world.ledger.written, written, "it was never the settlement's")
        nearest = world.containers[world.nearest_container(marta.tile)]
        self.assertEqual(nearest.count("compost"), 2, "what is left is put in the nearest place things are kept in")

    def test_two_lots_about_as_fresh_are_one_stack_and_two_that_are_not_are_kept_apart(self) -> None:
        world = self.world
        world.stock(self.crate, "vegetables", 4, None)
        world.stock(self.crate, "vegetables", 4, None, freshness=90.0)
        self.assertEqual(_stacks(self.crate, "vegetables"), [(8, 95.0)], "as fresh as the two together")
        world.stock(self.crate, "vegetables", 2, None, freshness=40.0)
        self.assertEqual(_stacks(self.crate, "vegetables"), [(8, 95.0), (2, 40.0)])
        world.stock(self.crate, "vegetables", 2, None, freshness=50.0)
        self.assertEqual(_stacks(self.crate, "vegetables"), [(8, 95.0), (4, 45.0)], "it goes on the lot nearest to it")
        # What keeps is one stack however long it has been there.
        world.stock(self.crate, "canned_beans", 4, None)
        world.stock(self.crate, "canned_beans", 4, None, freshness=10.0)
        self.assertEqual(_stacks(self.crate, "canned_beans"), [(8, 100.0)])
        # And it is the older lot that goes off: not all of it at once.
        world.step(DAY * 3)
        self.assertEqual(_stacks(self.crate, "vegetables"), [(8, 35.0)])
        self.assertEqual(self.crate.count("compost"), 4)

    def test_of_two_lots_of_the_same_thing_the_older_is_eaten_first(self) -> None:
        world = SimulationWorld.demo_world()
        no_store(world)
        pantry = world.containers["pantry_1"]
        pantry.items.clear()
        fresh = world.stock(pantry, "stew", 3, None)
        old = world.stock(pantry, "stew", 3, None, freshness=20.0)
        self.assertIsNot(fresh, old)
        marta = world.residents["marta"]
        self.assertIs(world.items.best_food(world, marta, "pantry_1", "food"), old)
        self.assertEqual(world.items.take_meal(world, marta, "pantry_1", "food"), ("stew", 1))
        self.assertEqual((fresh.quantity, old.quantity), (3, 2))


class MovingTests(unittest.TestCase):
    def test_putting_a_thing_away_and_bringing_it_out_leaves_it_as_fresh_as_it_was(self) -> None:
        world = _empty()
        pantry, store = world.containers["pantry_1"], world.containers[STORE]
        other = world.containers["pantry_2"]
        world.stock(pantry, "vegetables", 14, None, freshness=55.0)
        world.step(1)
        self.assertEqual(_stacks(pantry, "vegetables"), [(4, 55.0)], "what a pantry keeps at hand")
        self.assertEqual(_stacks(other, "vegetables"), [(4, 55.0)], "and the other pantry has its own from the store")
        self.assertEqual(_stacks(store, "vegetables"), [(6, 55.0)])
        pantry.items.clear()
        world.step(1)
        self.assertEqual(_stacks(pantry, "vegetables"), [(4, 55.0)], "and it comes back as it went")
        self.assertEqual(_stacks(store, "vegetables"), [(2, 55.0)])

    def test_a_worker_who_carries_two_lots_of_what_they_make_counts_and_hands_in_both(self) -> None:
        world = SimulationWorld.demo_world()
        raul = world.residents["raul"]
        raul.inventory.items[:] = [item for item in raul.inventory.items if item.owner_id is not None]
        world.stock(raul.inventory, "vegetables", 2, None, freshness=40.0)
        world.stock(raul.inventory, "vegetables", 3, None)
        self.assertEqual(len(hauling.lots(raul.inventory, "vegetables")), 2)
        rule = world.registries.jobs["farmer"].produces
        self.assertEqual(hauling.carried(raul, "vegetables"), 5, "every lot of it, not only the first")
        self.assertEqual(hauling.carried_made(world, raul, rule), 5)
        pantry = world.containers["pantry_1"]
        pantry.items.clear()
        said = hauling.exchange(world, raul, rule, world.interactables["pantry_1"])
        self.assertIn("5 de", said or "")
        self.assertEqual(hauling.carried(raul, "vegetables"), 0)
        self.assertEqual(_stacks(pantry, "vegetables"), [(2, 40.0), (3, 100.0)])

    def test_compost_is_kept_in_the_store_when_there_is_one(self) -> None:
        world = _empty()
        pantry = world.containers["pantry_2"]
        greens = world.stock(pantry, "vegetables", 3, None)
        greens.freshness = 0.5
        world.clock.minute = 59
        world.step(1)
        self.assertEqual((pantry.count("compost"), world.containers[STORE].count("compost")), (0, 3))


class ChestTests(unittest.TestCase):
    def setUp(self) -> None:
        self.world = _empty()
        self.chest = _with_chest(self.world)
        self.store = self.world.containers[STORE]
        self.pantry = self.world.containers["pantry_1"]

    def test_what_goes_off_is_put_in_it_ahead_of_the_store_and_what_keeps_is_not(self) -> None:
        world = self.world
        self.assertTrue(world.spoilage.chills(world, world.interactables[CHEST]))
        world.stock(self.pantry, "vegetables", 20, None)
        world.stock(self.pantry, "canned_beans", 20, None)
        world.step(1)
        # Each of the two pantries keeps four of each at hand, and the rest is put away.
        self.assertEqual((self.chest.count("vegetables"), self.store.count("vegetables")), (12, 0))
        self.assertEqual((self.chest.count("canned_beans"), self.store.count("canned_beans")), (0, 12))
        self.assertEqual(world.stores.capacity(world)["food"], 140, "its room is room for food")
        # Full, what is over goes to the store as it always did.
        world.stock(self.pantry, "stew", 44, None)
        world.step(1)
        self.assertEqual((self.chest.count("vegetables"), self.chest.count("stew")), (12, 28), "as much as it holds")
        self.assertEqual(self.store.count("stew"), 44 - 28 - 4 - 4)

    def test_it_keeps_what_is_in_it_four_times_as_long(self) -> None:
        world = self.world
        # More than the pantries take out of it to keep at hand, so that some of it stays.
        cold = world.stock(self.chest, "vegetables", 20, None)
        warm = world.stock(world.containers["crate_dorm"], "stew", 5, "nobody_here")
        self.assertAlmostEqual(world.spoilage.days_left(world, cold, CHEST), 20.0)
        self.assertAlmostEqual(world.spoilage.factor(world, CHEST), 0.25)
        world.step(DAY)
        self.assertAlmostEqual(cold.freshness, 95.0)
        self.assertAlmostEqual(warm.freshness, 66.0)

    def test_with_no_current_it_keeps_nothing_and_takes_nothing(self) -> None:
        world = self.world
        cold = world.stock(self.chest, "vegetables", 20, None)
        self.assertTrue(world.apply_command(SwitchCommand(CHEST, False)).ok)
        self.assertFalse(world.spoilage.chills(world, world.interactables[CHEST]))
        self.assertEqual(world.spoilage.factor(world, CHEST), 1.0)
        world.stock(self.pantry, "stew", 16, None)
        world.step(1)
        self.assertEqual((self.chest.count("stew"), self.store.count("stew")), (0, 8))
        world.step(DAY - 1)
        self.assertAlmostEqual(cold.freshness, 80.0)
        # Switched on again, what goes off in the store is put in it on the hour.
        self.assertTrue(world.apply_command(SwitchCommand(CHEST, True)).ok)
        world.step(HOUR)
        self.assertEqual((self.chest.count("stew"), self.store.count("stew")), (8, 0))
        # And with no fuel it is as with it switched off.
        for inventory in world.containers.values():
            inventory.items[:] = [item for item in inventory.items if item.definition_id != "fuel"]
        self.assertFalse(world.spoilage.chills(world, world.interactables[CHEST]))

    def test_it_draws_current_for_as_long_as_it_is_on(self) -> None:
        world = self.world
        for placed in world.interactables.values():
            if placed.object_id != CHEST and world.definition_of(placed).draws:
                placed.on = False
        self.assertEqual(world.power.demand(world), 1)
        self.assertEqual(world.power._running(world), 1.0)
        world.interactables[CHEST].on = False
        self.assertEqual(world.power._running(world), 0.0)

    def test_what_comes_out_to_be_eaten_is_the_store_first_and_the_chest_after(self) -> None:
        world = self.world
        world.stock(self.chest, "stew", 6, None)
        world.stock(self.store, "stew", 3, None, freshness=70.0)
        world.step(1)
        self.assertEqual(_stacks(self.pantry, "stew"), [(3, 70.0), (1, 100.0)])
        # The other pantry had its four out of the chest, there being no more in the store.
        self.assertEqual((self.store.count("stew"), self.chest.count("stew")), (0, 1))


class CompostTests(unittest.TestCase):
    def setUp(self) -> None:
        self.world = SimulationWorld.demo_world()
        self.world.clock.hour, self.world.clock.minute = 8, 0
        self.store = self.world.containers[STORE]

    def test_it_is_put_on_a_bed_at_the_players_word_and_the_bed_gives_more_for_some_days(self) -> None:
        world, raul = self.world, self.world.residents["raul"]
        job = world.registries.jobs["farmer"]
        before = world.work.pace(world, raul, job)
        result = world.apply_command(CompostCommand("crop_1"))
        self.assertEqual((result.ok, result.message), (False, "Hace falta abono: 2, y hay 0"))
        world.stock(self.store, "compost", 5, None)
        world.events.drain()
        result = world.apply_command(CompostCommand("crop_1"))
        self.assertTrue(result.ok, result.message)
        self.assertEqual(self.store.count("compost"), 3)
        self.assertEqual(world.dressed["crop_1"], world.clock.total_minutes + 3 * DAY)
        self.assertAlmostEqual(world.work.pace(world, raul, job), before * 1.4)
        self.assertEqual(world.spoilage.bed_factor(world, "crop_5"), 1.0, "the bed beside it is as it was")
        event = next(event for event in world.events.drain() if event.event_type == DRESSED_EVENT)
        self.assertEqual(event.data["object_id"], "crop_1")
        # One dressing at a time, and only on what it is put on.
        self.assertEqual(world.apply_command(CompostCommand("crop_1")).message, ALREADY_DRESSED)
        self.assertEqual(world.apply_command(CompostCommand("workbench")).message, NOT_A_BED)
        self.assertEqual(self.store.count("compost"), 3)
        world.step(3 * DAY)
        self.assertNotIn("crop_1", world.dressed)
        self.assertAlmostEqual(world.spoilage.bed_factor(world, "crop_1"), 1.0)
        self.assertTrue(world.apply_command(CompostCommand("crop_1")).ok)

    def test_nobody_puts_it_on_unasked(self) -> None:
        world = self.world
        world.stock(self.store, "compost", 20, None)
        world.step(2 * DAY)
        self.assertEqual(world.spoilage.compost_held(world), 20)
        self.assertEqual(world.dressed, {})


class SavedTests(unittest.TestCase):
    def test_how_fresh_things_are_and_the_compost_on_a_bed_are_saved_and_go_on_the_same(self) -> None:
        manager = SaveManager()
        world = SimulationWorld.demo_world()
        world.stock(world.containers[STORE], "compost", 4, None)
        world.step(2 * DAY + 90)
        self.assertTrue(world.apply_command(CompostCommand("crop_2")).ok)
        loaded = manager.from_data(manager.to_data(world))
        self.assertEqual(loaded.dressed, world.dressed)
        fresh = lambda each: [  # noqa: E731
            round(item.freshness, 6) for inventory in each.containers.values() for item in inventory.items
        ]
        self.assertEqual(fresh(loaded), fresh(world))
        self.assertTrue(any(value < 100.0 for value in fresh(world)))
        for each in (world, loaded):
            each.step(DAY)
        self.assertEqual(manager.to_data(loaded), manager.to_data(world))

    def test_in_a_save_from_before_everything_is_fresh_and_no_bed_has_compost(self) -> None:
        manager = SaveManager()
        world = SimulationWorld.demo_world()
        world.step(DAY)
        world.dressed["crop_1"] = world.clock.total_minutes + DAY
        data = manager.to_data(world)
        del data["dressed"]
        for holder in [*data["containers"].values(), *(each["inventory"] for each in data["residents"])]:
            for item in holder:
                del item["freshness"]
        data["version"] = 47
        loaded = manager.from_data(data)
        self.assertEqual(loaded.dressed, {})
        self.assertTrue(
            all(item.freshness == 100.0 for inventory in loaded.containers.values() for item in inventory.items)
        )
        broken = manager.to_data(world)
        next(iter(broken["containers"].values())).append(
            {"id": "odd", "definition_id": "stew", "quantity": 1, "freshness": "rotten"}
        )
        broken["dressed"] = {"crop_1": "soon", "crop_2": 99}
        loaded = manager.from_data(broken)
        self.assertEqual(loaded.dressed, {"crop_2": 99})


if __name__ == "__main__":
    unittest.main()
