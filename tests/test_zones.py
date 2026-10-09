import json
import unittest

from save.save_manager import SaveManager
from simulation.commands import CancelTripCommand, ChooseOptionCommand, PlanTripCommand, RenameZoneCommand
from simulation.residents.needs import Needs
from simulation.rng import SimulationRNG
from simulation.work.expedition import Expedition, expedition_settings_from_data
from simulation.work.expedition_system import ZONE_FOUND_EVENT
from simulation.world import SimulationWorld

LINE = ["forest", "ruins", "summit", "plant", "crater"]
SCAVENGER = "scavenger"


def _types(world: SimulationWorld) -> list[str]:
    return [line.split(" | ")[1] for line in world.event_log]


def _content(world: SimulationWorld) -> None:
    for resident in world.residents.values():
        resident.needs = Needs(hunger=0, tiredness=0, social=0, stress=0)


def _settled(seed: int = 7) -> SimulationWorld:
    world = SimulationWorld.demo_world(seed=seed)
    world.relationships.clear()
    _content(world)
    return world


def _level(world: SimulationWorld, resident_id: str, level: int) -> None:
    """Give a resident the time at their job that a level takes."""
    resident = world.residents[resident_id]
    job = world.registries.jobs[resident.job_id]
    marks = world.registries.crafts.levels
    # A poor head takes longer over it: as long as it takes.
    while world.crafts.level(world, resident, job.job_id) < level:
        world.crafts.worked(world, resident, job, max(1.0, marks[level - 1] - resident.trade.get(job.job_id, 0.0)))


def _send_out(world: SimulationWorld, limit: int = 240):
    sergio = world.residents["sergio"]
    for _ in range(limit):
        world.step(1)
        _content(world)
        if sergio.away:
            return sergio
    raise AssertionError("the scavenger never set out")


def _carried(resident) -> dict[str, int]:
    carried: dict[str, int] = {}
    for item in resident.inventory.items:
        if item.owner_id is None:
            carried[item.definition_id] = carried.get(item.definition_id, 0) + item.quantity
    return carried


def _common(world: SimulationWorld, item_id: str) -> int:
    return world.giving.givable(world).get(item_id, 0)


class TheLineTests(unittest.TestCase):
    """The country out there lies in a line, each zone past the one before (S68)."""

    def setUp(self) -> None:
        self.world = _settled()
        self.trips = self.world.expeditions
        self.settings = self.world.registries.expeditions
        self.sergio = self.world.residents["sergio"]

    def test_five_zones_one_past_the_other_each_further_and_worse(self) -> None:
        line = self.settings.line
        self.assertEqual([zone.zone_id for zone in line], LINE)
        self.assertEqual(
            [zone.name for zone in line],
            ["el bosque", "las ruinas de ciudad", "la cima de la montaña", "la central nuclear", "el cráter nuclear"],
        )
        first = line[0]
        self.assertEqual((first.minutes, first.supplies, first.danger, first.more), (0, 0.0, 0.0, 0))
        self.assertEqual(first.loot, (), "at the gate there is what there is anywhere")
        for nearer, further in zip(line, line[1:]):
            self.assertGreater(further.minutes, nearer.minutes)
            self.assertGreater(further.supplies, nearer.supplies)
            self.assertGreater(further.danger, nearer.danger)
            self.assertGreater(further.rare, nearer.rare)
            self.assertGreater(further.finds, nearer.finds)
            self.assertGreaterEqual(further.raiders[0], nearer.raiders[0])
            self.assertGreater(further.raiders[1], nearer.raiders[1] - 1)
            self.assertTrue(further.loot, "past the gate each has its own")
        known = set(self.world.registries.items.ids())
        self.assertTrue(all(entry.item in known for zone in line for entry in zone.loot))
        self.assertEqual([self.trips.needs(self.world, zone) for zone in line], [0, 2, 5, 9, 14])
        self.assertEqual([zone.zone_id for zone in self.trips.route_to(self.world, line[2])], LINE[:3])

    def test_what_makes_no_zone_is_rejected(self) -> None:
        for bad, said in (
            ({"minutes": -5}, "takes time"),
            ({"raiders": [3, 1]}, "raiders"),
            ({"raiders": [0, 1]}, "raiders"),
            ({"loot": [{"item": "scrap", "weight": 0}]}, "weight"),
        ):
            with self.assertRaisesRegex(ValueError, said):
                expedition_settings_from_data({"zones": {"x": bad}})
        with self.assertRaisesRegex(ValueError, "provision"):
            expedition_settings_from_data({"provisions": [{"tag": "food", "category": "food"}]})
        with self.assertRaisesRegex(ValueError, "provision"):
            expedition_settings_from_data({"provisions": [{"tag": "food", "worth": 0}]})
        apart = expedition_settings_from_data({"zones": {"a": {}, "b": {"apart": True}, "c": {}}})
        self.assertEqual([zone.zone_id for zone in apart.line], ["a", "c"])

    def test_only_the_first_is_known_until_somebody_goes_up_a_level(self) -> None:
        world, trips = self.world, self.trips
        self.assertEqual([zone.zone_id for zone in trips.found(world)], ["forest"])
        self.assertEqual([zone.zone_id for zone in trips.reach(world, self.sergio)], ["forest"])
        self.assertEqual(trips.reach(world, world.residents["marta"]), [], "nobody whose job is not done out there")
        _level(world, "sergio", 2)
        self.assertEqual(_types(world).count(ZONE_FOUND_EVENT), 1)
        said = next(line for line in world.event_log if ZONE_FOUND_EVENT in line)
        self.assertIn("¡Sergio ha encontrado una nueva zona!", said)
        self.assertIn("las ruinas de ciudad", said)
        self.assertEqual((world.zones["ruins"].by, world.zones["ruins"].name), ("sergio", ""))
        self.assertEqual([zone.zone_id for zone in trips.reach(world, self.sergio)], ["forest", "ruins"])
        self.assertFalse(world.crafts.waiting(world), "it is no thing to be made: it waits on nobody")
        _level(world, "sergio", 5)
        self.assertEqual([zone.zone_id for zone in trips.found(world)], LINE)
        self.assertEqual(_types(world).count(ZONE_FOUND_EVENT), 4)

    def test_a_zone_is_found_once_and_each_goes_as_far_as_their_own_level(self) -> None:
        world, trips = self.world, self.trips
        _level(world, "sergio", 3)
        paco = world.residents["paco"]
        paco.job_id, paco.post_id = SCAVENGER, self.sergio.post_id
        self.assertEqual([zone.zone_id for zone in trips.reach(world, paco)], ["forest"], "knowing of it is not knowing the way")
        _level(world, "paco", 2)
        self.assertEqual(_types(world).count(ZONE_FOUND_EVENT), 2, "what is known is not found again")
        self.assertEqual(world.zones["ruins"].by, "sergio")
        self.assertEqual([zone.zone_id for zone in trips.reach(world, paco)], ["forest", "ruins"])
        # Whoever found it gone, it is still known, and still as far as it was.
        del world.residents["sergio"]
        self.assertEqual([zone.zone_id for zone in trips.found(world)], LINE[:3])

    def test_a_zone_is_called_what_the_player_says(self) -> None:
        world, trips = self.world, self.trips
        ruins = self.settings.zone("ruins")
        self.assertFalse(world.apply_command(RenameZoneCommand("ruins", "Villaescombro")).ok, "nobody knows of it yet")
        _level(world, "sergio", 2)
        result = world.apply_command(RenameZoneCommand("ruins", "  Villa   Escombro  "))
        self.assertTrue(result.ok)
        self.assertEqual(trips.name_of(world, ruins), "Villa Escombro")
        self.assertIn("zone_named", _types(world))
        self.assertTrue(world.apply_command(RenameZoneCommand("forest", "El Pinar")).ok, "the first can be named too")
        self.assertEqual(trips.name_of(world, self.settings.zone("forest")), "El Pinar")
        world.apply_command(RenameZoneCommand("ruins", ""))
        self.assertEqual(trips.name_of(world, ruins), "las ruinas de ciudad", "with no name it is the game's again")
        self.assertFalse(world.apply_command(RenameZoneCommand("nowhere", "X")).ok)


class ProvisionsTests(unittest.TestCase):
    """Going further takes what is handed over at setting out: it fills the way like a bar (S68)."""

    def setUp(self) -> None:
        self.world = _settled()
        self.trips = self.world.expeditions
        self.sergio = self.world.residents["sergio"]
        _level(self.world, "sergio", 3)

    def test_food_and_water_are_what_gets_somebody_further(self) -> None:
        world, trips = self.world, self.trips
        there = trips.on_hand(world)
        self.assertGreater(there.get("water", 0), 10)
        self.assertGreater(there.get("canned_beans", 0), 10)
        self.assertNotIn("scrap", there)
        self.assertEqual((trips.worth(world, "water"), trips.worth(world, "stew"), trips.worth(world, "scrap")), (1.0, 1.0, 0.0))
        self.assertEqual(trips.worth_of(world, {"water": 2, "canned_beans": 3, "scrap": 9}), 5.0)

    def test_the_way_fills_as_things_are_handed_over(self) -> None:
        world, trips = self.world, self.trips
        got = [trips.gets_to(world, self.sergio, {"water": units}).zone_id for units in range(7)]
        self.assertEqual(got, ["forest", "forest", "ruins", "ruins", "ruins", "summit", "summit"])
        self.assertEqual(trips.gets_to(world, self.sergio, {"water": 99}).zone_id, "summit", "no further than they know the way")

    def test_what_is_handed_over_leaves_the_stores_at_once(self) -> None:
        world = self.world
        water, beans = _common(world, "water"), _common(world, "canned_beans")
        result = world.apply_command(PlanTripCommand("sergio", "ruins", {"water": 1, "canned_beans": 1}))
        self.assertTrue(result.ok, result.message)
        self.assertIn("las ruinas de ciudad", result.message)
        self.assertEqual((_common(world, "water"), _common(world, "canned_beans")), (water - 1, beans - 1))
        self.assertEqual((self.sergio.outing.zone, self.sergio.outing.supplies), ("ruins", {"water": 1, "canned_beans": 1}))
        self.assertEqual(_carried(self.sergio), {}, "it is not in their pockets to be put away")
        self.assertIn("trip_planned", _types(world))

    def test_a_trip_that_cannot_be_is_not_made_ready(self) -> None:
        world = self.world
        water = _common(world, "water")
        for resident_id, zone_id, supplies, said in (
            ("nobody", "ruins", {"water": 2}, "No hay a quién"),
            ("marta", "forest", {}, "oficio de salir"),
            ("sergio", "plant", {"water": 20}, "no sabe llegar"),
            ("sergio", "nowhere", {}, "no sabe llegar"),
            ("sergio", "ruins", {"water": 1}, "no llega"),
            ("sergio", "ruins", {"scrap": 5}, "No hay tanto"),
            ("sergio", "ruins", {"water": 100000}, "No hay tanto"),
        ):
            result = world.apply_command(PlanTripCommand(resident_id, zone_id, supplies))
            self.assertFalse(result.ok, (resident_id, zone_id))
            self.assertIn(said, result.message)
        self.assertEqual(_common(world, "water"), water)
        self.assertIsNone(self.sergio.outing)

    def test_made_ready_again_only_the_difference_changes_hands(self) -> None:
        world = self.world
        water = _common(world, "water")
        world.apply_command(PlanTripCommand("sergio", "ruins", {"water": 4}))
        self.assertTrue(world.apply_command(PlanTripCommand("sergio", "summit", {"water": 6})).ok)
        self.assertEqual(_common(world, "water"), water - 6)
        self.assertTrue(world.apply_command(PlanTripCommand("sergio", "ruins", {"water": 2})).ok)
        self.assertEqual(self.sergio.outing.supplies, {"water": 2})
        self.assertEqual(_carried(self.sergio), {"water": 4}, "what is over is theirs to carry back")
        # One that cannot be leaves the one there was as it was.
        self.assertFalse(world.apply_command(PlanTripCommand("sergio", "summit", {"water": 3})).ok)
        self.assertEqual((self.sergio.outing.zone, self.sergio.outing.supplies), ("ruins", {"water": 2}))

    def test_undone_what_was_handed_over_is_carried_back_to_where_it_is_kept(self) -> None:
        world = self.world
        water = _common(world, "water")
        self.assertFalse(world.apply_command(CancelTripCommand("sergio")).ok)
        world.apply_command(PlanTripCommand("sergio", "ruins", {"water": 3}))
        self.assertTrue(world.apply_command(CancelTripCommand("sergio")).ok)
        self.assertIsNone(self.sergio.outing)
        self.assertEqual(_carried(self.sergio), {"water": 3})
        for _ in range(400):
            world.step(1)
            _content(world)
            if not _carried(self.sergio).get("water") and self.sergio.away:
                break
        self.assertNotIn("water", _carried(self.sergio), "it is put away before they set out")
        self.assertGreaterEqual(_common(world, "water"), water - 3 - 40, "and is back with the rest, less what was drunk meanwhile")


class FarTripTests(unittest.TestCase):
    """A trip made ready goes through every zone on the way, and takes and risks more for it."""

    def setUp(self) -> None:
        self.world = _settled()
        self.trips = self.world.expeditions
        self.sergio = self.world.residents["sergio"]
        self.job = self.world.registries.jobs[SCAVENGER]
        _level(self.world, "sergio", 5)

    def _out(self, zone_id: str, units: int) -> Expedition:
        result = self.world.apply_command(PlanTripCommand("sergio", zone_id, {"water": units}))
        self.assertTrue(result.ok, result.message)
        self.trips.set_out(self.world, self.sergio, self.job)
        return self.sergio.expedition

    def test_left_to_themselves_they_keep_to_the_first_zone(self) -> None:
        self.trips.set_out(self.world, self.sergio, self.job)
        trip = self.sergio.expedition
        self.assertEqual((trip.zone, trip.route, trip.stages, trip.supplies), ("forest", [], [], {}))
        self.assertTrue(240 <= trip.returns_at - trip.left_at <= 360)
        self.assertEqual(trip.zone_at(trip.left_at + 10), "forest")
        self.assertEqual(trip.furthest(), "forest")
        self.assertTrue(any("Sergio sale del asentamiento a rebuscar" in line for line in self.world.event_log))

    def test_it_goes_through_every_zone_on_the_way_and_takes_as_long(self) -> None:
        trip = self._out("summit", 5)
        self.assertIsNone(self.sergio.outing, "made ready for one trip")
        self.assertEqual((trip.zone, trip.route, trip.supplies), ("summit", LINE[:3], {"water": 5}))
        long = trip.returns_at - trip.left_at
        self.assertTrue(240 + 330 <= long <= 360 + 330, long)
        self.assertEqual(trip.out_minutes, long // 2)
        self.assertEqual(len(trip.stages), 3)
        self.assertEqual(trip.stages, sorted(trip.stages))
        self.assertEqual(trip.stages[-1], 1.0)
        seen = [trip.zone_at(minute) for minute in range(trip.left_at, trip.returns_at + 1)]
        order = [zone for index, zone in enumerate(seen) if index == 0 or seen[index - 1] != zone]
        self.assertEqual(order, ["forest", "ruins", "summit", "ruins", "forest"], "out through each, and home through each")
        self.assertEqual(self.trips.zone_now(self.world, trip).zone_id, "forest")
        self.assertEqual(self.trips.zone_of(self.world, trip).zone_id, "summit")
        self.assertTrue(any("Sergio sale del asentamiento hacia la cima de la montaña" in line for line in self.world.event_log))
        left = next(line for line in self.world.event_log if "expedition_left" in line)
        self.assertIn("Sergio", left)

    def test_the_further_the_likelier_to_come_back_hurt(self) -> None:
        near = self._out("forest", 0).danger
        self.sergio.expedition = None
        far = self._out("crater", 14).danger
        zones = self.world.registries.expeditions.line
        self.assertGreater(far, near)
        self.assertAlmostEqual(far / near, (self.job.expedition.danger + sum(zone.danger for zone in zones)) / self.job.expedition.danger, places=5)

    def test_getting_there_uses_up_everything_that_was_handed_over(self) -> None:
        trip = self._out("ruins", 4)
        trip.find_at, trip.danger = None, 0.0
        while self.sergio.away:
            self.world.step(1)
            _content(self.world)
        self.assertEqual(trip.got_to(), 1.0)
        self.assertNotIn("water", _carried(self.sergio))
        table = {entry.item for entry in self.world.registries.expeditions.zone("ruins").loot}
        self.assertTrue(_carried(self.sergio))
        self.assertLessEqual(set(_carried(self.sergio)), table, "what there is where they got to")

    def test_turning_back_sooner_brings_home_what_was_not_used(self) -> None:
        trip = self._out("summit", 10)
        trip.danger = 0.0
        # Come on something a quarter of the way out, and told to leave it.
        quarter = trip.left_at + trip.out_minutes // 4
        trip.find_at = quarter
        while not self.world.decisions:
            self.world.step(1)
            _content(self.world)
        now = self.world.clock.total_minutes
        decision = next(iter(self.world.decisions.values()))
        self.assertEqual(self.world.apply_command(ChooseOptionCommand(decision.decision_id, "careful")), "turn_back")
        self.assertAlmostEqual(trip.got_to(), 0.25, delta=0.02)
        self.assertEqual(trip.returns_at, now + (now - trip.left_at), "the way home is as long as the way there was")
        self.assertEqual(trip.furthest(), "forest")
        self.assertAlmostEqual(trip.distance(now), trip.got_to(), places=5)
        self.assertEqual(trip.distance(trip.returns_at), 0.0)
        while self.sergio.away:
            self.world.step(1)
            _content(self.world)
        found = next(line for line in reversed(self.world.event_log) if "expedition_returned" in line)
        brought = _carried(self.sergio).get("water", 0)
        self.assertTrue(7 <= brought <= 7 + 3, (brought, found))
        self.assertGreaterEqual(brought - found.count("agua limpia") * 3, 4, "three quarters of the way was not gone")

    def test_far_from_home_what_is_come_on_may_be_anywhere_along_the_way(self) -> None:
        shares = set()
        for seed in range(1, 40):
            world = _settled(seed)
            _level(world, "sergio", 3)
            sergio = world.residents["sergio"]
            self.assertTrue(world.apply_command(PlanTripCommand("sergio", "summit", {"water": 5})).ok)
            world.expeditions.set_out(world, sergio, world.registries.jobs[SCAVENGER])
            trip = sergio.expedition
            if trip.find_at is not None:
                share = (trip.find_at - trip.left_at) / trip.out_minutes
                self.assertTrue(0.39 <= share <= 1.01, share)
                shares.add(round(share, 1))
        self.assertGreater(len(shares), 3)

    def test_further_out_things_are_rarer_and_what_nobody_knows_likelier(self) -> None:
        world = self.world

        def rare(likelier: float) -> int:
            dice = SimulationRNG.keyed(1, "test", likelier)
            return sum(world.upgrades.found_level(world, dice, False, likelier) > 1 for _ in range(3000))

        self.assertGreater(rare(5.0), rare(1.0) * 2)
        plain = SimulationRNG.keyed(1, "test", 1.0)
        self.assertEqual(rare(1.0), sum(world.upgrades.found_level(world, plain) > 1 for _ in range(3000)), "at the gate, as it was")

        def unknown(likelier: float) -> int:
            found = 0
            for minute in range(600):
                fresh = _settled()
                fresh.clock.minute = minute % 60
                fresh.clock.hour = minute // 60
                found += fresh.finds.maybe(fresh, "expedition", fresh.residents["sergio"], likelier=likelier) is not None
            return found

        self.assertGreater(unknown(3.5), unknown(1.0) * 2)

    def test_a_trip_made_ready_for_where_they_can_no_longer_get_to_is_a_trip_to_the_gate(self) -> None:
        self.world.apply_command(PlanTripCommand("sergio", "crater", {"water": 14}))
        del self.world.zones["crater"]
        self.trips.set_out(self.world, self.sergio, self.job)
        trip = self.sergio.expedition
        self.assertEqual((trip.zone, trip.supplies), ("forest", {}))
        self.assertEqual(_carried(self.sergio), {"water": 14})


class ZonesSaveTests(unittest.TestCase):
    def setUp(self) -> None:
        self.manager = SaveManager()

    def test_zones_trips_and_what_was_made_ready_are_saved(self) -> None:
        world = _settled()
        _level(world, "sergio", 3)
        world.apply_command(RenameZoneCommand("ruins", "Villaescombro"))
        world.apply_command(PlanTripCommand("sergio", "summit", {"water": 5}))
        loaded = self.manager.from_data(json.loads(json.dumps(self.manager.to_data(world))))
        self.assertEqual(self.manager.to_data(loaded), self.manager.to_data(world))
        self.assertEqual(loaded.zones["ruins"].name, "Villaescombro")
        self.assertEqual(loaded.residents["sergio"].outing, world.residents["sergio"].outing)
        for each in (world, loaded):
            each.expeditions.set_out(each, each.residents["sergio"], each.registries.jobs[SCAVENGER])
        again = self.manager.from_data(json.loads(json.dumps(self.manager.to_data(world))))
        self.assertEqual(again.residents["sergio"].expedition, world.residents["sergio"].expedition)
        self.assertEqual(again.residents["sergio"].expedition.route, LINE[:3])
        world.step(3 * 24 * 60)
        loaded.step(3 * 24 * 60)
        self.assertEqual(self.manager.to_data(loaded), self.manager.to_data(world))

    def test_a_save_from_before_knows_as_far_as_whoever_goes_out_furthest(self) -> None:
        world = _settled()
        world.residents["sergio"].trade[SCAVENGER] = float(world.registries.crafts.levels[2])
        data = self.manager.to_data(world)
        del data["zones"]
        for resident in data["residents"]:
            del resident["outing"]
        loaded = self.manager.from_data(json.loads(json.dumps(data)))
        self.assertEqual([zone.zone_id for zone in loaded.expeditions.found(loaded)], LINE[:3])
        self.assertEqual([zone.zone_id for zone in loaded.expeditions.reach(loaded, loaded.residents["sergio"])], LINE[:3])
        self.assertIsNone(loaded.residents["sergio"].outing)
        fresh = self.manager.from_data(json.loads(json.dumps({**self.manager.to_data(_settled()), "zones": None})))
        self.assertEqual([zone.zone_id for zone in fresh.expeditions.found(fresh)], ["forest"])


if __name__ == "__main__":
    unittest.main()
