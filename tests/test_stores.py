"""Room for things (S53): the store what is everybody's is kept in, the places it is taken
from, and what happens when there is no room left."""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from save.save_manager import SaveManager
from simulation.commands import ProposeObjectCommand
from simulation.economy.stores import FULL_EVENT, NO_LIMIT
from simulation.items.inventory import Inventory
from simulation.registries import DATA_DIR, BuiltInRegistries
from simulation.residents.attributes import Attributes
from simulation.residents.needs import Needs
from simulation.work import hauling
from simulation.work.hauling import containers_of_kind
from simulation.world import SimulationWorld
from tests.worlds import no_store
from world.interactable import Interactable

ROOT = Path(__file__).resolve().parent.parent
MINUTES_PER_DAY = 24 * 60
STORE = "warehouse"
RESOURCES = ("food", "water", "energy", "medicine", "scrap")


def _keep_content(world: SimulationWorld) -> None:
    for resident in world.residents.values():
        resident.needs = Needs(hunger=0, thirst=0, tiredness=0, social=0, stress=0)


def _settled(seed: int = 7, hour: int = 8) -> SimulationWorld:
    """The settlement that comes ready made, store and all, with everyone content."""
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


def _everywhere(world: SimulationWorld, item_id: str) -> int:
    return sum(inventory.count(item_id) for inventory in world.containers.values())


def _fill(world: SimulationWorld, resource_id: str, item_id: str) -> None:
    """Put as much of a thing in the store as it has room left for."""
    world.stores.tick(world)
    world.stock(world.containers[STORE], item_id, world.stores.room(world)[resource_id], None)


def _registries_with(change) -> BuiltInRegistries:
    with tempfile.TemporaryDirectory() as folder:
        root = Path(folder)
        for path in DATA_DIR.rglob("*.json"):
            target = root / path.relative_to(DATA_DIR)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
        data = json.loads((root / "interactables.json").read_text(encoding="utf-8"))
        change(data)
        (root / "interactables.json").write_text(json.dumps(data), encoding="utf-8")
        return BuiltInRegistries.load(root)


class DataTests(unittest.TestCase):
    def test_what_a_store_holds_and_what_is_kept_at_hand_are_data(self) -> None:
        world = SimulationWorld.demo_world()
        kinds = world.registries.interactables
        store = kinds.get(STORE)
        self.assertEqual(set(store.store), set(RESOURCES))
        self.assertTrue(store.container and store.build is not None)
        self.assertEqual((store.width, store.height), (4, 3), "as big as a small building")
        self.assertEqual(kinds.get("pantry").outlet, {"food": 4})
        self.assertEqual(kinds.get("water_tank").outlet, {"water": 20})
        self.assertEqual(set(kinds.get("crate").outlet.values()), {0}, "a crate keeps none of it")
        self.assertIsNone(kinds.get("cooking_pot").outlet, "what is cooked stays in the pot")
        self.assertEqual(world.stores.capacity(world), store.store)

        def bigger(data) -> None:
            data[STORE]["store"]["food"] = 250

        self.assertEqual(_registries_with(bigger).interactables.get(STORE).store["food"], 250)

    def test_a_store_of_something_there_is_not_is_refused(self) -> None:
        def unknown(data) -> None:
            data[STORE]["store"]["gold"] = 5

        def not_a_container(data) -> None:
            data["table"]["outlet"] = {"food": 2}

        def both(data) -> None:
            data[STORE]["outlet"] = {"food": 2}

        def negative(data) -> None:
            data["pantry"]["outlet"] = {"food": -1}

        for change in (unknown, not_a_container, both, negative):
            with self.subTest(change=change.__name__), self.assertRaises(ValueError):
                _registries_with(change)

    def test_stores_need_no_pygame(self) -> None:
        check = (
            "import sys; import simulation.economy.stores; from simulation.world import SimulationWorld; "
            "world = SimulationWorld.demo_world(); world.step(180); assert world.stores.held(world)['water'] > 0; "
            "sys.exit(1 if 'pygame' in sys.modules else 0)"
        )
        done = subprocess.run([sys.executable, "-c", check], cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(done.returncode, 0, done.stderr)


class KeepingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.world = _settled()
        self.store = self.world.containers[STORE]

    def test_what_stands_free_goes_to_the_store_but_for_a_little_kept_at_hand(self) -> None:
        world = self.world
        before = world.ledger.stock(world)
        beans = _everywhere(world, "canned_beans")
        self.assertEqual(self.store.items, [])
        world.stores.tick(world)
        self.assertEqual(world.ledger.stock(world), before, "nothing is made or lost by it")
        self.assertEqual(_everywhere(world, "canned_beans"), beans)
        self.assertEqual(world.containers["pantry_1"].count("canned_beans"), 4)
        self.assertEqual(world.containers["pantry_2"].count("canned_beans"), 4)
        self.assertEqual(world.containers["water_tank"].count("water"), 20)
        self.assertEqual(world.containers["generator"].count("fuel"), 4)
        self.assertEqual(world.containers["medicine_cabinet"].count("medicine"), 2)
        # The well keeps as much at hand as the tank does (S55).
        self.assertEqual(world.containers["well"].count("water"), 20)
        self.assertEqual(self.store.count("water"), before["water"] - 40)
        held = world.stores.held(world)
        self.assertEqual(held["water"], before["water"] - 40)
        self.assertGreater(held["food"], 0)
        again = SaveManager().to_data(world)
        world.stores.tick(world)
        self.assertEqual(SaveManager().to_data(world), again, "and once it is put away nothing more moves")

    def test_what_is_taken_comes_back_from_the_store(self) -> None:
        world = self.world
        world.stores.tick(world)
        pantry, in_store = world.containers["pantry_1"], self.store.count("canned_beans")
        pantry.take_units(pantry.stack_of("canned_beans", None).instance_id, 3)
        world.stores.tick(world)
        self.assertEqual(pantry.count("canned_beans"), 4)
        self.assertEqual(self.store.count("canned_beans"), in_store - 3)

    def test_a_little_of_each_kind_of_thing_is_kept_at_hand(self) -> None:
        world = self.world
        world.stock(self.store, "vegetables", 30, None)
        world.stores.tick(world)
        for pantry_id in ("pantry_1", "pantry_2"):
            pantry = world.containers[pantry_id]
            self.assertEqual((pantry.count("canned_beans"), pantry.count("vegetables")), (4, 4))
        self.assertEqual(self.store.count("vegetables"), 30 - 8)

    def test_what_is_somebodys_stays_where_they_put_it(self) -> None:
        world = self.world
        pantry = world.containers["pantry_1"]
        world.stock(pantry, "canned_beans", 9, "marta")
        world.stores.tick(world)
        self.assertEqual(pantry.stack_of("canned_beans", "marta").quantity, 9)
        self.assertIsNone(self.store.stack_of("canned_beans", "marta"))

    def test_a_crate_keeps_none_of_it_and_everything_else(self) -> None:
        world = self.world
        crate = world.containers["crate_workshop"]
        world.stock(crate, "canned_beans", 5, None)
        world.stock(crate, "fuel", 3, None)
        knife = crate.count("rusty_knife")
        self.assertGreater(knife, 0)
        before = self.store.count("canned_beans")
        world.stores.tick(world)
        self.assertEqual((crate.count("canned_beans"), crate.count("fuel")), (0, 0))
        self.assertEqual(crate.count("rusty_knife"), knife, "which is nothing the settlement lives on")
        self.assertGreaterEqual(self.store.count("canned_beans"), before + 5)

    def test_what_is_cooked_stays_in_the_pot(self) -> None:
        world = self.world
        stew = world.containers["cooking_pot"].count("stew")
        self.assertGreater(stew, 0)
        world.stores.tick(world)
        self.assertEqual(world.containers["cooking_pot"].count("stew"), stew)
        self.assertEqual(self.store.count("stew"), 0)

    def test_a_second_store_holds_what_the_first_has_no_room_for(self) -> None:
        world = self.world
        world.interactables["second"] = Interactable("second", STORE, 0, 0)
        world.containers["second"] = Inventory()
        one = world.registries.interactables.get(STORE).store
        self.assertEqual(world.stores.capacity(world), {name: units * 2 for name, units in one.items()})
        world.stock(world.containers["pantry_1"], "vegetables", one["food"] + 30, None)
        world.stores.tick(world)
        food = lambda inventory: sum(  # noqa: E731
            item.quantity for item in inventory.items if world.registries.items.resolve(item.definition_id).category == "food"
        )
        self.assertLessEqual(food(self.store), one["food"])
        self.assertGreater(food(self.store), one["food"] - 10, "the first is as good as full")
        self.assertGreater(food(world.containers["second"]), 20)
        self.assertEqual(world.stores.full_of(world), [])

    def test_the_books_say_how_much_room_there_is(self) -> None:
        world = self.world
        world.stores.tick(world)
        lines = {line.resource_id: line for line in world.ledger.report(world)}
        capacity = world.registries.interactables.get(STORE).store
        for resource_id in RESOURCES:
            line = lines[resource_id]
            self.assertEqual((line.capacity, line.full), (capacity[resource_id], False))
            self.assertEqual(line.stored, world.stores.held(world)[resource_id])
            self.assertLessEqual(line.stored, line.stock)


class FullTests(unittest.TestCase):
    def setUp(self) -> None:
        self.world = _settled()
        self.store = self.world.containers[STORE]

    def test_with_the_store_full_nothing_more_is_grown_and_it_is_said_once_a_day(self) -> None:
        world = self.world
        world.residents["marta"].job_id = None
        _fill(world, "food", "vegetables")
        capacity = world.stores.capacity(world)["food"]
        self.assertEqual(world.stores.held(world)["food"], capacity)
        self.assertEqual(world.stores.full_of(world), ["food"])
        pantry = world.containers["pantry_1"]
        self.assertEqual(world.stores.room_at(world, pantry, "vegetables"), 4 - pantry.count("vegetables"))
        grown = _everywhere(world, "vegetables")
        _run(world, 5 * 60)
        self.assertEqual(world.stores.held(world)["food"], capacity, "not a unit more than it holds")
        # What it takes to have a little at hand in each pantry, and what each has in their hands.
        self.assertLessEqual(_everywhere(world, "vegetables"), grown + 8)
        for farmer_id in ("raul", "ines"):
            self.assertLessEqual(hauling.carried(world.residents[farmer_id], "vegetables"), 6)
        said = [line for line in world.event_log if f"| {FULL_EVENT} |" in line]
        self.assertEqual(len(said), 1)
        self.assertIn("No cabe más comida en el almacén: hace falta otro", said[0])
        line = world.ledger.line(world, "food")
        self.assertEqual((line.capacity, line.full, line.stored), (capacity, True, capacity))

    def test_with_room_again_they_go_back_to_it(self) -> None:
        world = self.world
        world.residents["marta"].job_id = None
        _fill(world, "food", "vegetables")
        _run(world, 3 * 60)
        before = _everywhere(world, "vegetables")
        stack = self.store.stack_of("vegetables", None)
        self.store.take_units(stack.instance_id, 40)
        _run(world, 4 * 60)
        self.assertGreater(_everywhere(world, "vegetables"), before - 40 + 6)

    def test_water_is_drawn_until_the_store_is_full_and_no_longer(self) -> None:
        world = _settled(hour=7)
        self.store = world.containers[STORE]
        _fill(world, "water", "water")
        capacity = world.stores.capacity(world)["water"]
        tank = world.containers["water_tank"]
        lucia = world.residents["lucia"]
        self.assertTrue(world.staffing.assign(world, lucia, "water_carrier"))
        self.assertLessEqual(world.stores.room_at(world, tank, "water"), 0)
        before = world.ledger.stock(world)["water"]
        _run(world, 2 * 60)
        self.assertEqual(world.ledger.stock(world)["water"], before, "there is nowhere to put any")
        stack = self.store.stack_of("water", None)
        self.store.take_units(stack.instance_id, 50)
        _run(world, 3 * 60)
        self.assertGreater(world.ledger.stock(world)["water"], before - 50)
        self.assertLessEqual(world.stores.held(world)["water"], capacity)

    def test_another_store_makes_room(self) -> None:
        world = self.world
        _fill(world, "food", "vegetables")
        self.assertEqual(world.stores.full_of(world), ["food"])
        world.interactables["second"] = Interactable("second", STORE, 0, 0)
        world.containers["second"] = Inventory()
        self.assertEqual(world.stores.full_of(world), [])
        self.assertGreater(world.stores.room_at(world, world.containers["pantry_1"], "vegetables"), 50)
        self.assertFalse(world.ledger.line(world, "food").full)

    def test_one_is_built_as_anything_is(self) -> None:
        world = self.world
        spot = next(
            (x, y)
            for y in range(1, world.tile_map.height - 4)
            for x in range(1, world.tile_map.width - 5)
            if world.urbanism.object_error(world, STORE, (x, y)) is None
        )
        result = world.apply_command(ProposeObjectCommand(STORE, spot, "marta"))
        self.assertTrue(result.ok)
        site = world.sites[result.entity_id]
        self.assertEqual((site.what, len(site.tiles)), (STORE, 12))


class WithoutTests(unittest.TestCase):
    def test_a_settlement_with_no_store_goes_on_as_it_did(self) -> None:
        world = no_store(_settled())
        self.assertFalse(world.stores.stands(world))
        self.assertEqual((world.stores.capacity(world), world.stores.full_of(world)), ({}, []))
        beans = world.containers["pantry_1"].count("canned_beans")
        water = world.containers["water_tank"].count("water")
        world.stores.tick(world)
        self.assertEqual(world.containers["pantry_1"].count("canned_beans"), beans)
        self.assertEqual(world.containers["water_tank"].count("water"), water)
        self.assertEqual(world.stores.room_at(world, world.containers["pantry_1"], "vegetables"), NO_LIMIT)
        self.assertFalse(world.stores.feeds(world, "pantry"))
        self.assertEqual(containers_of_kind(world, "pantry", stores=True), containers_of_kind(world, "pantry"))
        line = world.ledger.line(world, "food")
        self.assertEqual((line.capacity, line.full, line.stored), (None, False, None))
        world.step(MINUTES_PER_DAY)
        self.assertFalse(any(f"| {FULL_EVENT} |" in line for line in world.event_log))

    def test_a_save_of_the_ready_made_settlement_from_before_gains_its_store(self) -> None:
        manager = SaveManager()
        data = manager.to_data(no_store(SimulationWorld.demo_world(seed=11)))
        self.assertNotIn(STORE, [each["id"] for each in data["interactables"]])
        data["version"] = 41
        for room in data["rooms"]:
            if room["id"] == "storehouse":
                room["name"] = "almacén"
        loaded = manager.from_data(data)
        self.assertTrue(loaded.stores.stands(loaded))
        there = SimulationWorld.demo_world().interactables[STORE]
        self.assertEqual((loaded.interactables[STORE].x, loaded.interactables[STORE].y), (there.x, there.y))
        self.assertEqual(loaded.rooms["storehouse"].name, "despensa", "two things are not called the same")
        water = loaded.ledger.stock(loaded)["water"]
        loaded.step(1)
        self.assertEqual(loaded.ledger.stock(loaded)["water"], water)
        self.assertGreater(loaded.stores.held(loaded)["water"], 100, "what there was is kept in it at once")

    def test_it_gains_nothing_else_and_not_the_store_where_something_stands(self) -> None:
        manager = SaveManager()
        world = no_store(SimulationWorld.demo_world(seed=11))
        there = SimulationWorld.demo_world().interactables[STORE]
        # The player took a crate down, built on the ground the store would take, and named the building.
        del world.interactables["crate_1"]
        del world.containers["crate_1"]
        world.interactables["mine"] = Interactable("mine", "table", there.x + 1, there.y + 1)
        world.rooms["storehouse"].name = "la alacena"
        data = manager.to_data(world)
        data["version"] = 41
        loaded = manager.from_data(data)
        self.assertFalse(loaded.stores.stands(loaded))
        self.assertNotIn("crate_1", loaded.interactables, "what was taken down stays down")
        self.assertEqual(loaded.rooms["storehouse"].name, "la alacena")

    def test_a_save_with_a_store_goes_on_the_same_and_one_of_now_with_none_has_none(self) -> None:
        manager = SaveManager()
        world = SimulationWorld.demo_world(seed=11)
        world.step(6 * 60)
        data = manager.to_data(world)
        loaded = manager.from_data(data)
        self.assertEqual(loaded.stores.held(loaded), world.stores.held(world))
        for each in (world, loaded):
            each.step(6 * 60)
        self.assertEqual(manager.to_data(loaded), manager.to_data(world))
        # Whoever has taken theirs down, or never built one, is not given one on loading.
        without = manager.to_data(no_store(SimulationWorld.demo_world(seed=11)))
        again = manager.from_data(without)
        self.assertFalse(again.stores.stands(again))
        again.step(60)
        self.assertGreater(again.containers["water_tank"].count("water"), 100)


class ThroughTests(unittest.TestCase):
    """What was done at a pantry, a tank or a cabinet is still done there, and reaches the store."""

    def setUp(self) -> None:
        self.world = _settled()
        self.store = self.world.containers[STORE]
        self.world.stores.tick(self.world)

    def test_the_cook_fetches_what_goes_in_the_pot_from_the_store(self) -> None:
        world = self.world
        world.stock(self.store, "vegetables", 30, None)
        marta = world.residents["marta"]
        rule = world.registries.jobs["cook"].produces
        self.assertEqual(hauling.fetch_source(world, rule), STORE)
        placed = world.interactables[STORE]
        marta.inventory.items.clear()
        done = hauling.exchange(world, marta, rule, placed)
        self.assertIn("coge", done or "")
        self.assertGreaterEqual(sum(item.quantity for item in marta.inventory.items), 4)

    def test_a_day_of_the_kitchen_and_the_garden_goes_round(self) -> None:
        world = self.world
        stew = lambda: world.containers["cooking_pot"].count("stew")  # noqa: E731
        made = 0
        last = stew()
        for _ in range(MINUTES_PER_DAY):
            world.step(1)
            _keep_content(world)
            made += max(0, stew() - last)
            last = stew()
        self.assertGreater(_everywhere(world, "vegetables"), 20, "the garden went on growing")
        self.assertGreater(made, 0, "and the cook on cooking")
        self.assertGreater(self.store.count("vegetables"), 0)

    def test_the_generator_and_the_cabinet_are_kept_up_with_nobody_carrying(self) -> None:
        world = self.world
        for job_id in ("mechanic", "medic"):
            rule = world.registries.jobs[job_id].supplies
            worker = next(each for each in world.residents.values() if each.job_id == job_id)
            self.assertIsNone(hauling.supply_errand(world, worker, rule, 240), job_id)
        generator = world.containers["generator"]
        generator.take_units(generator.stack_of("fuel", None).instance_id, 4)
        self.assertFalse(world.has_power())
        world.step(1)
        self.assertTrue(world.has_power())
        self.assertEqual(generator.count("fuel"), 4)

    def test_what_they_already_carry_for_it_is_still_taken_there(self) -> None:
        world = self.world
        paco = world.residents["paco"]
        rule = world.registries.jobs["mechanic"].supplies
        generator = world.containers["generator"]
        generator.take_units(generator.stack_of("fuel", None).instance_id, 2)
        world.stock(paco.inventory, "fuel", 3, None)
        self.assertEqual(hauling.supply_errand(world, paco, rule, 240), "generator")

    def test_whoever_is_in_care_is_given_what_is_kept_in_the_store(self) -> None:
        world = self.world
        found = [object_id for object_id, _ in containers_of_kind(world, "medicine_cabinet", stores=True)]
        self.assertEqual(found, ["medicine_cabinet", STORE])
        self.assertEqual(containers_of_kind(world, "cooking_pot", stores=True), containers_of_kind(world, "cooking_pot"))

    def test_raiders_take_from_the_store_what_they_took_from_the_pantries_and_no_more(self) -> None:
        world = self.world
        raid = world.registries.world_events.events["raid"]
        self.assertIn("pantry", raid.containers)
        self.assertNotIn("water_tank", raid.containers)
        water, beans = self.store.count("water"), self.store.count("canned_beans")
        self.assertGreater(beans, 8)
        world.happenings._loot(world, raid)  # noqa: SLF001
        self.assertEqual(self.store.count("water"), water, "they never got to the tank")
        self.assertEqual(self.store.count("canned_beans"), beans - int(beans * raid.fraction))
        self.assertEqual(self.store.count("fuel"), world.stores.held(world)["energy"])

    def test_vermin_get_at_what_is_kept_in_the_store(self) -> None:
        world = self.world
        vermin = world.registries.world_events.events["vermin"]
        beans = self.store.count("canned_beans")
        water = self.store.count("water")
        world.happenings._spoil(world, vermin)  # noqa: SLF001
        self.assertEqual(self.store.count("canned_beans"), beans - int(beans * vermin.fraction))
        self.assertEqual(self.store.count("water"), water)

    def test_a_week_with_the_store_leaves_nothing_unexplained_in_the_books(self) -> None:
        for seed in (7, 23):
            with self.subTest(seed=seed):
                world = SimulationWorld.demo_world(seed=seed)
                world.step(7 * MINUTES_PER_DAY)
                unexplained = {
                    (day, resource_id): flows["other"]
                    for day, resources in world.accounts.days.items()
                    for resource_id, flows in resources.items()
                    if abs(flows.get("other", 0.0)) > 1e-9
                }
                self.assertEqual(unexplained, {})
                self.assertLessEqual(world.stores.held(world)["food"], world.stores.capacity(world)["food"])


if __name__ == "__main__":
    unittest.main()
