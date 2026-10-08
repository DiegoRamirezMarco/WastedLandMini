"""The settlement's books (S51): what comes in, what goes out, and how long what there is will last."""

import subprocess
import sys
import unittest
from dataclasses import replace
from pathlib import Path

from save.save_manager import SaveManager
from simulation.commands import DealWithMerchantCommand, ProposeObjectCommand, SetResearchCommand
from simulation.economy.fund_system import hand_over
from simulation.economy.ledger import (
    BOUGHT,
    BUILT,
    DRUNK,
    EATEN,
    HANDED,
    LOW_EVENT,
    MADE,
    OTHER,
    SOLD,
    STUDIED,
    LedgerState,
    ResourceSettings,
    resource_settings_from_data,
)
from simulation.economy.merchant import Merchant
from simulation.registries import builtin_registries
from simulation.residents.needs import Needs
from simulation.work import hauling
from simulation.world import SimulationWorld
from tests.worlds import no_store

ROOT = Path(__file__).resolve().parent.parent
MINUTES_PER_DAY = 24 * 60
RESOURCES = {"food": {"name": "Comida", "category": "food"}, "scrap": {"name": "Chatarra", "tag": "scrap"}}


def _keep_content(world: SimulationWorld) -> None:
    for resident in world.residents.values():
        resident.needs = Needs(hunger=0, thirst=0, tiredness=0, social=0, stress=0)


def _settled(seed: int = 7) -> SimulationWorld:
    """The settlement that comes ready made, with nobody wanting for anything and no grudges,
    and its books open."""
    world = SimulationWorld.demo_world(seed=seed)
    no_store(world)
    world.relationships.clear()
    _keep_content(world)
    world.ledger.tick(world)
    return world


def _run(world: SimulationWorld, minutes: int, until=None) -> bool:
    for _ in range(minutes):
        world.step(1)
        _keep_content(world)
        if until is not None and until():
            return True
    return False


def _written(world: SimulationWorld, resource: str, reason: str) -> float:
    """Everything written down of a resource for one reason, today and on the days kept."""
    days = [world.accounts.today, *world.accounts.days.values()]
    return sum(
        units for day in days for why, units in day.get(resource, {}).items() if why.partition(":")[0] == reason
    )


def _explained(world: SimulationWorld) -> bool:
    """Whether what was written today comes to how what there is has changed since the day began."""
    state = world.accounts
    opening, stock = state.held[state.day - 1], world.ledger.stock(world)
    return all(
        abs(stock[resource] - opening[resource] - sum(state.today.get(resource, {}).values())) < 1e-6
        for resource in stock
    )


def _unexplained(world: SimulationWorld) -> dict[tuple[int, str], float]:
    """What the count at the end of a day found that nothing written accounts for, on the days kept."""
    return {
        (day, resource): flows[OTHER]
        for day, written in world.accounts.days.items()
        for resource, flows in written.items()
        if OTHER in flows
    }


def _low_notices(world: SimulationWorld, name: str) -> int:
    return sum(1 for line in world.event_log if f"| {LOW_EVENT} |" in line and name in line)


class ResourceDataTests(unittest.TestCase):
    def test_what_a_settlement_counts_is_data(self) -> None:
        world = SimulationWorld.demo_world()
        self.assertEqual(list(world.registries.resources.resources), ["food", "water", "energy", "medicine", "scrap"])
        counted = {
            item_id: world.ledger.resources_of(world, world.registries.items.get(item_id))
            for item_id in ("canned_beans", "stew", "water", "fuel", "medicine", "scrap", "liquor", "hoe")
        }
        self.assertEqual(
            counted,
            {
                "canned_beans": ("food",), "stew": ("food",), "water": ("water",), "fuel": ("energy",),
                "medicine": ("medicine",), "scrap": ("scrap",), "liquor": (), "hoe": (),
            },
        )
        # Another is one more entry in the data, and nothing in the code names any of them.
        more = resource_settings_from_data({"resources": {**RESOURCES, "drink": {"name": "Bebida", "category": "drink"}}})
        world.registries = replace(world.registries, resources=more)
        self.assertEqual(world.ledger.resources_of(world, world.registries.items.get("liquor")), ("drink",))
        self.assertEqual(list(world.ledger.stock(world)), ["food", "scrap", "drink"])

    def test_data_that_makes_no_sense_is_refused(self) -> None:
        for bad in (
            {"resources": {"food": {"name": "Comida"}}},
            {"resources": {"food": {"category": "food"}}},
            {"resources": RESOURCES, "window_days": 0},
            {"resources": RESOURCES, "window_days": 5, "kept_days": 3},
            {"resources": RESOURCES, "low_days": -1},
        ):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                resource_settings_from_data(bad)

    def test_the_books_need_no_pygame(self) -> None:
        check = (
            "import sys; import simulation.economy.ledger, save.save_manager; "
            "from simulation.world import SimulationWorld; world = SimulationWorld.demo_world(); "
            "world.step(1500); world.ledger.report(world); sys.exit(1 if 'pygame' in sys.modules else 0)"
        )
        done = subprocess.run([sys.executable, "-c", check], cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(done.returncode, 0, done.stderr)


class StockTests(unittest.TestCase):
    def test_what_is_the_settlements_is_what_is_nobodys_wherever_it_is(self) -> None:
        world = SimulationWorld.demo_world()
        before = world.ledger.stock(world)
        in_stores = sum(
            item.quantity
            for inventory in world.containers.values()
            for item in inventory.items
            if item.owner_id is None and world.registries.items.resolve(item.definition_id).category == "food"
        )
        self.assertEqual(before["food"], in_stores)
        # What is somebody's own is not the settlement's, wherever it is kept.
        world.stock(world.containers["pantry_1"], "canned_beans", 3, "marta")
        self.assertEqual(world.ledger.stock(world)["food"], before["food"])
        # What somebody is carrying that is nobody's still is, and so is what waits at the gate.
        world.stock(world.residents["raul"].inventory, "canned_beans", 2, None)
        world.at_gate["medicine"] = 4
        after = world.ledger.stock(world)
        self.assertEqual((after["food"], after["medicine"]), (before["food"] + 2, before["medicine"] + 4))


class EntryTests(unittest.TestCase):
    def test_what_the_garden_makes_comes_in_and_a_meal_goes_out(self) -> None:
        world = SimulationWorld.demo_world(seed=7)
        world.step(MINUTES_PER_DAY)
        first = world.accounts.days[1]
        self.assertGreater(first["food"][f"{MADE}:farmer"], 0)
        self.assertLess(first["food"][EATEN], 0)
        self.assertLess(first["water"][DRUNK], 0)
        # What the kitchen cooks is food made of food: as much goes into the pot as comes out of it.
        self.assertEqual(first["food"]["used:cook"], -first["food"][f"{MADE}:cook"])
        self.assertEqual(world.ledger.reason_name(world, f"{MADE}:farmer"), "Huerto")
        self.assertEqual(world.ledger.reason_name(world, "used:cook"), "Cocina: lo que gasta")
        self.assertEqual(world.ledger.reason_name(world, "found:cook"), "Traído de fuera")
        self.assertEqual(world.ledger.reason_name(world, EATEN), "Comido")

    def test_what_counts_as_no_resource_is_not_written_down(self) -> None:
        world = _settled()
        world.ledger.record(world, "liquor", 3, MADE)
        world.ledger.record(world, "canned_beans", 0, MADE)
        self.assertEqual((world.accounts.today, list(world.ledger.recent)), ({}, []))
        world.ledger.record(world, "canned_beans", 2, MADE, "cook", "marta", "cooking_pot")
        self.assertEqual(world.accounts.today, {"food": {"made:cook": 2.0}})
        entry = world.ledger.recent[-1]
        self.assertEqual((entry.definition_id, entry.units, entry.by, entry.at), ("canned_beans", 2, "marta", "cooking_pot"))

    def test_carrying_a_thing_about_changes_nothing(self) -> None:
        world = SimulationWorld.demo_world()
        raul = world.residents["raul"]
        world.containers["pantry_2"].items.clear()
        world.stock(raul.inventory, "vegetables", 6, None)
        world.ledger.tick(world)
        before = world.ledger.stock(world)
        rule = world.registries.jobs["farmer"].produces
        done = hauling.exchange(world, raul, rule, world.interactables["pantry_2"])
        self.assertIn("lleva 6", done or "")
        self.assertEqual(world.containers["pantry_2"].count("vegetables"), 6)
        self.assertEqual(world.ledger.stock(world), before)
        self.assertEqual(world.accounts.today, {})

    def test_a_thing_that_changes_hands_comes_in_or_goes_out(self) -> None:
        world = _settled()
        marta = world.residents["marta"]
        shelf = next(
            inventory for inventory in world.containers.values() if inventory.stack_of("canned_beans", None) is not None
        )
        hand_over(world, shelf, shelf.stack_of("canned_beans", None), marta.inventory, "marta", SOLD)
        self.assertEqual(world.accounts.today["food"], {SOLD: -1.0})
        # Handed back, it is the settlement's again. Moved as what it already was, nothing is written.
        self.assertTrue(world.fund.take_in(world, marta.inventory, marta.inventory.stack_of("canned_beans", "marta"), marta.tile))
        self.assertEqual(world.accounts.today["food"], {SOLD: -1.0, HANDED: 1.0})
        hand_over(world, shelf, shelf.stack_of("canned_beans", None), world.containers["pantry_1"], None)
        self.assertEqual(world.accounts.today["food"], {SOLD: -1.0, HANDED: 1.0})
        self.assertTrue(_explained(world))

    def test_a_deal_with_a_caravan_is_written_as_it_is_struck(self) -> None:
        world = _settled()
        world.merchant = Merchant("caravan", world.clock.total_minutes + 300, {"medicine": 2}, 30.0)
        before = world.ledger.stock(world)
        result = world.apply_command(DealWithMerchantCommand(sell={"canned_beans": 2}, buy={"medicine": 1}))
        self.assertTrue(result.ok, result.message)
        self.assertEqual(world.accounts.today, {"food": {SOLD: -2.0}, "medicine": {BOUGHT: 1.0}})
        after = world.ledger.stock(world)
        # What was bought waits at the gate to be carried in, and is the settlement's from then on.
        self.assertEqual((after["food"], after["medicine"]), (before["food"] - 2, before["medicine"] + 1))
        self.assertTrue(_explained(world))

    def test_what_a_site_takes_goes_out_as_it_is_carried_to_it(self) -> None:
        world = _settled()
        spot = next(
            (x, y)
            for y in range(1, world.tile_map.height - 2)
            for x in range(1, world.tile_map.width - 2)
            if world.urbanism.object_error(world, "bed", (x, y)) is None
        )
        site_id = world.apply_command(ProposeObjectCommand("bed", spot, "marta")).entity_id
        self.assertTrue(_run(world, 2 * MINUTES_PER_DAY, lambda: site_id not in world.sites), "the bed never stood")
        self.assertEqual(_written(world, "scrap", BUILT), -2)
        self.assertEqual(_unexplained(world), {})
        self.assertTrue(_explained(world))

    def test_what_is_studied_and_used_up_goes_out(self) -> None:
        world = _settled()
        world.staffing.assign(world, world.residents["lucia"], "water_carrier")
        spot = next(
            (x, y)
            for y in range(1, world.tile_map.height - 2)
            for x in range(1, world.tile_map.width - 2)
            if world.urbanism.object_error(world, "study_desk", (x, y)) is None
        )
        world.urbanism.place_object(world, "study_desk", spot)
        self.assertTrue(world.staffing.assign(world, world.residents["nuria"], "researcher"))
        world.apply_command(SetResearchCommand("dosage"))
        self.assertTrue(_run(world, MINUTES_PER_DAY, lambda: "dosage" in world.studies.supplied), "never brought")
        self.assertEqual(_written(world, "medicine", STUDIED), -2)
        self.assertEqual(_unexplained(world), {})
        self.assertTrue(_explained(world))


class DayTests(unittest.TestCase):
    def test_a_week_leaves_nothing_unaccounted_for(self) -> None:
        for seed in (7, 11, 23):
            with self.subTest(seed=seed):
                world = SimulationWorld.demo_world(seed=seed)
                world.step(7 * MINUTES_PER_DAY)
                state = world.accounts
                self.assertEqual(sorted(state.days), [1, 2, 3, 4, 5, 6, 7])
                self.assertEqual(_unexplained(world), {})
                for day in sorted(state.days)[1:]:
                    for resource, count in state.held[day].items():
                        written = sum(state.days[day].get(resource, {}).values())
                        self.assertEqual(count - state.held[day - 1][resource], written, (day, resource))
                self.assertTrue(_explained(world))

    def test_what_nothing_wrote_down_is_entered_as_such(self) -> None:
        world = SimulationWorld.demo_world(seed=7)
        world.step(60)
        tank = world.containers["water_tank"]
        tank.take_units(tank.stack_of("water", None).instance_id, 5)
        world.step(MINUTES_PER_DAY)
        first = world.accounts.days[1]
        self.assertEqual(first["water"][OTHER], -5)
        self.assertEqual(_unexplained(world), {(1, "water"): -5})
        # The count is the truth: with what was entered, the books come to it.
        held = world.accounts.held
        self.assertEqual(held[1]["water"] - held[0]["water"], sum(first["water"].values()))

    def test_only_the_last_days_are_kept(self) -> None:
        world = SimulationWorld.demo_world(seed=7)
        world.step(9 * MINUTES_PER_DAY)
        kept = world.registries.resources.kept_days
        self.assertEqual(sorted(world.accounts.days), list(range(9 - kept + 1, 10)))
        self.assertEqual(sorted(world.accounts.held), list(range(9 - kept + 1, 10)))

    def test_the_pace_is_that_of_the_last_days_and_says_how_long_it_will_last(self) -> None:
        world = SimulationWorld.demo_world()
        stock = world.ledger.stock(world)["food"]
        world.accounts = LedgerState(
            day=5,
            days={
                1: {"food": {EATEN: -100.0}},
                2: {"food": {f"{MADE}:farmer": 10.0, EATEN: -40.0}},
                3: {"food": {f"{MADE}:farmer": 20.0, EATEN: -50.0}},
                4: {"food": {f"{MADE}:farmer": 30.0, EATEN: -60.0, "found": 3.0}},
            },
        )
        food = world.ledger.line(world, "food")
        self.assertTrue(food.known and not food.tentative)
        self.assertEqual((food.coming, food.going, food.net), (21.0, 50.0, -29.0))
        self.assertAlmostEqual(food.days_left, stock / 29.0)
        self.assertEqual(food.low, food.days_left < world.registries.resources.low_days)
        self.assertEqual(food.by_reason, ((f"{MADE}:farmer", 20.0), ("found", 1.0), (EATEN, -50.0)))
        # What is not going down has no days left to count, and what nothing is written of says nothing.
        world.accounts.days[4]["food"][f"{MADE}:farmer"] = 300.0
        self.assertIsNone(world.ledger.line(world, "food").days_left)
        water = world.ledger.line(world, "water")
        self.assertEqual((water.coming, water.going, water.days_left, water.low), (0.0, 0.0, None, False))

    def test_before_a_day_has_closed_the_pace_is_told_from_the_hours_there_are(self) -> None:
        world = SimulationWorld.demo_world(seed=7)
        world.step(3 * 60)
        self.assertFalse(world.ledger.line(world, "food").known)
        world.step(5 * 60)
        food = world.ledger.line(world, "food")
        self.assertTrue(food.known and food.tentative)
        written = world.accounts.today["food"]
        elapsed = world.clock.total_minutes - world.accounts.opened_at
        self.assertAlmostEqual(food.coming, sum(units for units in written.values() if units > 0) * MINUTES_PER_DAY / elapsed)
        world.step(MINUTES_PER_DAY)
        self.assertFalse(world.ledger.line(world, "food").tentative)

    def test_what_is_running_low_is_said_once_a_day(self) -> None:
        world = SimulationWorld.demo_world(seed=7)
        world.step(1)
        self.assertEqual(_low_notices(world, "agua"), 0)
        # As if a whole day's water had gone the day before: what there is will not last two.
        world.accounts.days[0] = {"water": {DRUNK: -500.0}}
        self.assertTrue(world.ledger.line(world, "water").low)
        world.step(60)
        self.assertEqual(_low_notices(world, "agua"), 1)
        world.step(8 * 60)
        self.assertEqual(_low_notices(world, "agua"), 1)
        world.step(MINUTES_PER_DAY)
        self.assertEqual(_low_notices(world, "agua"), 2)
        events = [event for event in world.events.drain() if event.event_type == LOW_EVENT]
        self.assertEqual(events[0].data["resource"], "water")
        self.assertIn("menos de un día", events[0].text)


class DeterminismTests(unittest.TestCase):
    def test_the_books_move_no_dice_and_decide_nothing(self) -> None:
        registries = builtin_registries()
        # With no store in either: a store goes by what the resources are, and that is not what is asked here.
        written = no_store(SimulationWorld.demo_world(seed=11))
        unwritten = no_store(
            SimulationWorld.demo_world(seed=11, registries=replace(registries, resources=ResourceSettings()))
        )
        for world in (written, unwritten):
            world.step(3 * MINUTES_PER_DAY)
        self.assertEqual(unwritten.accounts, LedgerState())
        self.assertTrue(written.accounts.days)
        self.assertEqual(written.rng.get_state(), unwritten.rng.get_state())
        self.assertEqual(written.event_rng.get_state(), unwritten.event_rng.get_state())
        happened = [line for line in written.event_log if f"| {LOW_EVENT} |" not in line]
        self.assertEqual(happened, unwritten.event_log)
        self.assertEqual(
            {name: (each.x, each.y, vars(each.needs), each.mood) for name, each in written.residents.items()},
            {name: (each.x, each.y, vars(each.needs), each.mood) for name, each in unwritten.residents.items()},
        )


class LedgerSaveTests(unittest.TestCase):
    def setUp(self) -> None:
        self.manager = SaveManager()

    def test_what_is_written_is_saved_and_goes_on_the_same(self) -> None:
        world = SimulationWorld.demo_world(seed=7)
        world.step(2 * MINUTES_PER_DAY + 400)
        data = self.manager.to_data(world)
        self.assertEqual(data["version"], self.manager.CURRENT_VERSION)
        self.assertEqual(sorted(data["ledger"]["days"]), ["1", "2"])
        loaded = self.manager.from_data(data)
        self.assertEqual(loaded.accounts, world.accounts)
        self.assertEqual(self.manager.to_data(loaded), data)
        for each in (world, loaded):
            each.step(MINUTES_PER_DAY)
        self.assertEqual(self.manager.to_data(loaded), self.manager.to_data(world))
        self.assertEqual(_unexplained(loaded), {})

    def test_a_save_from_before_has_nothing_written_and_opens_its_books_as_it_goes_on(self) -> None:
        world = SimulationWorld.demo_world(seed=7)
        world.step(MINUTES_PER_DAY + 300)
        data = self.manager.to_data(world)
        del data["ledger"]
        data["version"] = 38
        loaded = self.manager.from_data(data)
        self.assertEqual(loaded.accounts, LedgerState())
        self.assertFalse(loaded.ledger.line(loaded, "food").known)
        loaded.step(1)
        self.assertEqual(loaded.accounts.day, loaded.clock.day)
        self.assertEqual(loaded.accounts.held[loaded.clock.day - 1], world.ledger.stock(world))
        loaded.step(MINUTES_PER_DAY)
        self.assertEqual(_unexplained(loaded), {})


if __name__ == "__main__":
    unittest.main()
