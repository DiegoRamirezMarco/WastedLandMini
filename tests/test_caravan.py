import json
import unittest
from dataclasses import replace
from pathlib import Path

from save.save_manager import SaveManager
from simulation.ai.crowd import free_tile, spots_taken
from simulation.events.world_event import world_event_settings_from_data
from simulation.world import SimulationWorld

ROOT = Path(__file__).resolve().parent.parent
CARAVAN = "caravan"


def _events() -> dict:
    return json.loads((ROOT / "data" / "world_events.json").read_text(encoding="utf-8"))


def _morning(seed: int = 7) -> SimulationWorld:
    """The ready-made settlement on the morning a caravan comes."""
    world = SimulationWorld.demo_world(seed=seed)
    world.clock.day, world.clock.hour, world.clock.minute = 2, 9, 0
    return world


def _arrived(world: SimulationWorld) -> SimulationWorld:
    world.merchants.arrive(world, world.registries.world_events.events[CARAVAN])
    return world


def _with_caravan(world: SimulationWorld, **changes) -> SimulationWorld:
    """The same world with something about the caravan changed."""
    events = dict(world.registries.world_events.events)
    events[CARAVAN] = replace(events[CARAVAN], **changes)
    world.registries = replace(world.registries, world_events=replace(world.registries.world_events, events=events))
    return world


class CaravanStayTests(unittest.TestCase):
    def test_it_is_there_from_when_it_comes_until_night_falls(self) -> None:
        world = _arrived(_morning())
        definition = world.registries.world_events.events[CARAVAN]
        self.assertLessEqual(definition.hours[1], 12, "it comes in the morning")
        self.assertEqual(world.merchant.leaves_at, 24 * 60 + definition.leaves_hour * 60)
        world.step(11 * 60)
        self.assertIsNotNone(world.merchant, "eleven hours on it has not gone")
        world.step(60)
        self.assertIsNone(world.merchant)

    def test_one_that_names_no_hour_to_go_at_stops_for_as_long_as_it_says(self) -> None:
        world = _arrived(_with_caravan(_morning(), leaves_hour=None, minutes=(90, 90)))
        self.assertEqual(world.merchant.leaves_at, world.clock.total_minutes + 90)

    def test_one_that_comes_after_its_hour_to_go_does_not_stay_until_yesterday(self) -> None:
        world = _morning()
        world.clock.hour = 22
        _arrived(world)
        self.assertGreater(world.merchant.leaves_at, world.clock.total_minutes)

    def test_whoever_comes_is_somebody_by_name(self) -> None:
        world = _morning()
        definition = world.registries.world_events.events[CARAVAN]
        self.assertTrue(definition.keeper_id and definition.keeper_name)
        self.assertEqual(world.merchants.keepers(world), {definition.keeper_id: definition.keeper_name})
        _arrived(world)
        self.assertIn(definition.keeper_name, world.event_log[-1])
        self.assertNotIn(definition.keeper_id, world.residents, "and is nobody who lives there")

    def test_data_that_makes_no_sense_is_refused(self) -> None:
        data = _events()
        data["events"][CARAVAN]["leaves_hour"] = 9
        with self.assertRaises(ValueError):
            world_event_settings_from_data(data)
        data = _events()
        del data["events"][CARAVAN]["keeper"]["name"]
        with self.assertRaises(ValueError):
            world_event_settings_from_data(data)
        data = _events()
        del data["events"][CARAVAN]["keeper"], data["events"][CARAVAN]["cart"], data["events"][CARAVAN]["leaves_hour"]
        plain = world_event_settings_from_data(data).events[CARAVAN]
        self.assertEqual((plain.keeper_id, plain.cart, plain.leaves_hour), ("", None, None), "a pack may leave them out")


class CaravanPlaceTests(unittest.TestCase):
    def test_they_stand_beside_the_way_in_with_their_cart_and_on_nothing(self) -> None:
        world = _arrived(_morning())
        merchant = world.merchant
        cart = world.registries.interactables.get(world.registries.world_events.events[CARAVAN].cart)
        ways_in = world.entry_tiles()
        gate = world.happenings.arrival_tile(world)
        taken = world.merchants.spots(world)
        self.assertEqual(len(taken), 1 + cart.width)
        self.assertEqual({tile[1] for tile in taken}, {gate[1]}, "beside the way in, not in front of it")
        self.assertLessEqual(abs(merchant.tile[0] - gate[0]), 3)
        self.assertIn(merchant.cart[0], (merchant.tile[0] + 1, merchant.tile[0] - cart.width), "the cart is at their side")
        passable = world.passable()
        objects = {tile for placed in world.interactables.values() for tile in placed.footprint(world.definition_of(placed))}
        for tile in taken:
            room = world.room_at(tile)
            self.assertTrue(passable(tile), tile)
            self.assertNotIn(tile, ways_in)
            self.assertNotIn(tile, objects)
            self.assertFalse(room is not None and room.roofed, "they are out in the open, to be seen")

    def test_the_same_settlement_puts_them_in_the_same_place(self) -> None:
        places = {(_arrived(_morning(seed)).merchant.tile, _arrived(_morning(seed)).merchant.cart) for seed in (1, 2, 3)}
        self.assertEqual(len(places), 1, "where they stand goes by the map, not by chance")

    def test_with_no_cart_to_bring_they_stand_alone(self) -> None:
        world = _arrived(_with_caravan(_morning(), cart=None))
        self.assertIsNotNone(world.merchant.tile)
        self.assertIsNone(world.merchant.cart)
        self.assertEqual(world.merchants.spots(world), {world.merchant.tile})

    def test_nobody_plans_to_stop_where_they_or_their_cart_are(self) -> None:
        world = _arrived(_morning())
        taken = world.merchants.spots(world)
        self.assertTrue(taken <= spots_taken(world))
        for tile in taken:
            self.assertNotIn(free_tile(world, tile), taken)
        visitor = world.residents["ines"]
        plan = world.merchants.plan(world, visitor)
        self.assertIsNotNone(plan)
        end = plan.path[-1] if plan.path else visitor.tile
        self.assertNotIn(end, taken)
        self.assertLessEqual(max(abs(end[0] - world.merchant.tile[0]), abs(end[1] - world.merchant.tile[1])), 2)

    def test_once_they_are_gone_the_ground_is_anybodys_again(self) -> None:
        world = _arrived(_morning())
        self.assertTrue(world.merchants.spots(world))
        world.merchant = None
        self.assertEqual(world.merchants.spots(world), set())

    def test_the_cart_is_a_kind_of_thing_like_any_other(self) -> None:
        world = _morning()
        cart = world.registries.interactables.find(world.registries.world_events.events[CARAVAN].cart)
        self.assertIsNotNone(cart)
        self.assertEqual(cart.width, 2)


class CaravanSaveTests(unittest.TestCase):
    def setUp(self) -> None:
        self.manager = SaveManager()

    def test_where_they_stand_survives_saving(self) -> None:
        world = _arrived(_morning())
        loaded = self.manager.from_data(json.loads(json.dumps(self.manager.to_data(world))))
        self.assertEqual((loaded.merchant.tile, loaded.merchant.cart), (world.merchant.tile, world.merchant.cart))
        self.assertEqual(self.manager.to_data(loaded), self.manager.to_data(world))

    def test_a_save_from_before_they_were_anywhere_finds_them_a_place(self) -> None:
        world = _arrived(_morning())
        data = self.manager.to_data(world)
        del data["merchant"]["tile"], data["merchant"]["cart"]
        data["version"] = 32
        loaded = self.manager.from_data(json.loads(json.dumps(data)))
        self.assertEqual((loaded.merchant.tile, loaded.merchant.cart), (world.merchant.tile, world.merchant.cart))
        self.assertEqual(self.manager.to_data(loaded)["version"], self.manager.CURRENT_VERSION)

    def test_a_place_that_is_no_place_is_not_taken_from_a_save(self) -> None:
        world = _arrived(_morning())
        data = self.manager.to_data(world)
        data["merchant"]["tile"], data["merchant"]["cart"] = "here", [1, "two"]
        loaded = self.manager.from_data(json.loads(json.dumps(data)))
        self.assertEqual((loaded.merchant.tile, loaded.merchant.cart), (None, None))
        self.assertEqual(loaded.merchants.where(loaded), loaded.happenings.arrival_tile(loaded))


if __name__ == "__main__":
    unittest.main()
