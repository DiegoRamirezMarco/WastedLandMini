import json
import tempfile
import unittest
from pathlib import Path

from save.save_manager import SaveManager
from simulation.commands import ChooseOptionCommand
from simulation.events.world_event import Weather, world_event_settings_from_data
from simulation.events.world_event_system import STRANGER_DECISION
from simulation.registries import DATA_DIR, BuiltInRegistries
from simulation.residents.activity import Activity
from simulation.residents.needs import Needs
from simulation.rng import SimulationRNG
from simulation.work.hauling import carried
from simulation.work.work_system import WORK_ACTION
from simulation.world import SimulationWorld

MINUTES_PER_DAY = 24 * 60
PANTRIES = ("pantry_1", "pantry_2")


class _Certain(SimulationRNG):
    """A generator of world events for which whatever can happen does, at the first chance."""

    def random(self) -> float:
        return 0.0


def _types(world: SimulationWorld) -> list[str]:
    return [line.split(" | ")[1] for line in world.event_log]


def _keep_content(world: SimulationWorld) -> None:
    for resident in world.residents.values():
        resident.needs = Needs(hunger=0, tiredness=0, social=0, stress=resident.needs.stress)


def _settled(seed: int = 7) -> SimulationWorld:
    world = SimulationWorld.demo_world(seed=seed)
    world.relationships.clear()
    for resident in world.residents.values():
        resident.needs = Needs(hunger=0, tiredness=0, social=0, stress=0)
    return world


def _only(world: SimulationWorld, event_id: str, day: int = 2, hour: int = 12) -> None:
    """Make one world event certain at the next hour that it can happen, and the others impossible."""
    world.event_rng = _Certain(1)
    world.clock.day, world.clock.hour, world.clock.minute = day, hour, 0
    world.happened = {other: day for other in world.registries.world_events.events if other != event_id}


def _on_duty(world: SimulationWorld, resident_id: str) -> None:
    resident = world.residents[resident_id]
    post = world.interactables[resident.post_id]
    resident.x, resident.y = post.x, post.y - 1
    resident.activity = Activity(WORK_ACTION, resident.post_id, minutes_left=600, using=True)
    resident.current_action = WORK_ACTION


def _registries_with(file_name: str, old: str, new: str) -> BuiltInRegistries:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "data"
        (root / "maps").mkdir(parents=True)
        for path in DATA_DIR.rglob("*.json"):
            text = path.read_text(encoding="utf-8")
            if path.name == file_name:
                assert old in text, old
                text = text.replace(old, new)
            (root / path.relative_to(DATA_DIR)).write_text(text, encoding="utf-8")
        return BuiltInRegistries.load(root)


class WhenThingsHappenTests(unittest.TestCase):
    def test_nothing_happens_to_a_settlement_on_its_first_day(self) -> None:
        world = _settled()
        world.event_rng = _Certain(1)
        world.step(15 * 60)
        self.assertEqual(world.happened, {})
        self.assertIsNone(world.weather)
        world.step(MINUTES_PER_DAY)
        self.assertTrue(world.happened)

    def test_an_event_keeps_to_its_hours_and_does_not_come_again_too_soon(self) -> None:
        world = _settled()
        _only(world, "vermin", hour=7)
        world.step(60)
        self.assertNotIn("food_spoiled", _types(world), "only by night")
        world.clock.day, world.clock.hour = 3, 1
        world.step(60)
        self.assertEqual(_types(world).count("food_spoiled"), 1)
        self.assertEqual(world.happened["vermin"], 3)
        world.clock.day, world.clock.hour = 5, 1
        world.step(60)
        self.assertEqual(_types(world).count("food_spoiled"), 1, "six days must pass")
        world.clock.day, world.clock.hour = 9, 1
        world.step(60)
        self.assertEqual(_types(world).count("food_spoiled"), 2)

    def test_what_happens_from_outside_does_not_change_what_residents_would_have_done(self) -> None:
        quiet, eventful = SimulationWorld.demo_world(seed=4), SimulationWorld.demo_world(seed=4)
        quiet.event_rng, eventful.event_rng = SimulationRNG(1), SimulationRNG(99)
        for world in (quiet, eventful):
            world.step(20 * 60)
        self.assertEqual(quiet.event_log, eventful.event_log)
        self.assertEqual(quiet.rng.get_state(), eventful.rng.get_state())

    def test_the_same_seed_brings_the_same_events(self) -> None:
        logs = []
        for _ in range(2):
            world = SimulationWorld.demo_world(seed=5)
            world.step(6 * MINUTES_PER_DAY)
            logs.append(world.event_log)
        self.assertEqual(logs[0], logs[1])


class StrangerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.world = _settled()
        self.tomas = self.world.residents["tomas"]
        _only(self.world, "stranger")
        _on_duty(self.world, "tomas")

    def _arrive(self):
        self.world.step(60)
        return next((d for d in self.world.decisions.values() if d.kind == STRANGER_DECISION), None)

    def test_a_stranger_at_the_gate_is_the_guards_to_answer_and_the_players_to_advise(self) -> None:
        decision = self._arrive()
        self.assertEqual(decision.resident_id, "tomas")
        visitor = self.world.happenings.visitor(self.world)
        self.assertIn(visitor.name, decision.prompt)
        self.assertIn("stranger_at_gate", _types(self.world))
        self.assertNotIn(visitor.newcomer_id, self.world.residents)
        self.assertTrue(self.world.work.on_duty(self.world, self.tomas), "he goes on keeping the gate")
        self.world.step(30)
        self.assertEqual(len(self.world.decisions), 1, "one stranger at a time")

    def test_let_in_they_become_a_resident_with_nothing_but_what_they_stand_in(self) -> None:
        decision = self._arrive()
        visitor = self.world.happenings.visitor(self.world)
        before = len(self.world.residents)
        self.assertEqual(self.world.apply_command(ChooseOptionCommand(decision.decision_id, "open")), "let_in")
        self.assertEqual(len(self.world.residents), before + 1)
        newcomer = self.world.residents[visitor.newcomer_id]
        self.assertEqual((newcomer.name, newcomer.age), (visitor.name, visitor.age))
        self.assertIsNone(newcomer.job_id)
        self.assertTrue(newcomer.seeks_work)
        self.assertEqual(newcomer.inventory.items, [])
        self.assertTrue(self.world.passable()(newcomer.tile))
        self.assertIsNone(self.world.at_the_gate)
        self.assertIn("newcomer_joined", _types(self.world))
        self.assertTrue(any(f"Tomás abre la puerta a {visitor.name}" in line for line in self.world.event_log))
        self.assertIn(visitor.newcomer_id, self.world.newcomers_seen)
        # They settle in like anyone: they eat, they sleep, and nothing breaks.
        actions = set()
        self.world.event_rng = SimulationRNG(1)
        for _ in range(3 * MINUTES_PER_DAY):
            self.world.step(1)
            actions.add(newcomer.current_action)
        self.assertLessEqual({"eat", "sleep"}, actions)
        # And they look for something to do without being asked: the garden always has room.
        self.assertEqual(newcomer.job_id, "farmer")
        self.assertFalse(newcomer.seeks_work)
        self.assertTrue(any(f"{visitor.name} se hace cargo de un puesto: Huerto" in line for line in self.world.event_log))

    def test_turned_away_they_are_gone_for_good(self) -> None:
        decision = self._arrive()
        visitor = self.world.happenings.visitor(self.world)
        before = len(self.world.residents)
        self.assertEqual(self.world.apply_command(ChooseOptionCommand(decision.decision_id, "close")), "turn_away")
        self.assertEqual(len(self.world.residents), before)
        self.assertIn("stranger_turned_away", _types(self.world))
        self.assertTrue(any("siga su camino" in line and visitor.name in line for line in self.world.event_log))
        self.world.clock.day = 20
        self.world.happened.pop("stranger")
        for _ in range(4):
            later = self._arrive()
            if later is None:
                break
            self.assertNotEqual(self.world.happenings.visitor(self.world).newcomer_id, visitor.newcomer_id)
            self.world.apply_command(ChooseOptionCommand(later.decision_id, "close"))
            self.world.happened.pop("stranger")
            self.world.clock.hour = 12

    def test_left_alone_a_gruff_guard_shuts_the_gate_and_a_kind_one_opens_it(self) -> None:
        self.assertEqual(self.world.interventions.resolve(self.world, self._arrive().decision_id, None), "turn_away")
        self.setUp()
        self.tomas.personality.empathy, self.tomas.personality.aggression = 90, 10
        self.assertEqual(self.world.interventions.resolve(self.world, self._arrive().decision_id, None), "let_in")

    def test_nobody_comes_while_the_guard_is_off_and_with_no_guard_they_find_the_gate_shut(self) -> None:
        self.tomas.activity = Activity("wander", minutes_left=600, using=True)
        self.assertIsNone(self._arrive())
        self.assertNotIn("stranger_unanswered", _types(self.world))
        self.tomas.job_id = self.tomas.post_id = None
        self.assertIsNone(self._arrive())
        self.assertEqual(_types(self.world).count("stranger_unanswered"), 1)
        self.assertEqual(self.world.newcomers_seen, [], "they may try again another day")

    def test_nobody_comes_when_there_is_no_bed_for_them(self) -> None:
        beds = [oid for oid, placed in self.world.interactables.items() if placed.kind == "bed"]
        for bed_id in beds[len(self.world.residents):]:
            del self.world.interactables[bed_id]
        self.assertIsNone(self._arrive())
        self.assertNotIn("stranger_at_gate", _types(self.world))

    def test_if_whoever_was_deciding_is_gone_the_stranger_gives_up(self) -> None:
        self._arrive()
        self.assertIsNotNone(self.world.at_the_gate)
        self.world.health.die(self.world, self.tomas, "una prueba")
        self.world.step(1)
        self.assertIsNone(self.world.at_the_gate)
        self.assertEqual(self.world.newcomers_seen, [])


class CaravanAndVerminTests(unittest.TestCase):
    def test_a_caravan_leaves_goods_on_the_shop_counter(self) -> None:
        world = _settled()
        _only(world, "caravan", hour=4)
        counter = world.containers["shop_counter"]
        before = sum(item.quantity for item in counter.items)
        world.step(60)
        self.assertEqual([upcoming.event_id for upcoming in world.upcoming], ["caravan"], "it is on its way first")
        world.step(5 * 60)
        added = sum(item.quantity for item in counter.items) - before
        self.assertTrue(3 <= added <= 6, added)
        self.assertEqual(_types(world).count("caravan_passed"), 1)
        self.assertIn("Pasa una caravana y deja género en la tienda:", world.event_log[-1])

    def test_vermin_eat_a_share_of_what_is_in_the_pantries_and_leave_private_stores_alone(self) -> None:
        world = _settled()
        for pantry in PANTRIES:
            world.containers[pantry].items.clear()
        world.stock(world.containers["pantry_1"], "vegetables", 20, None)
        world.stock(world.containers["pantry_2"], "canned_beans", 10, "raul")
        _only(world, "vermin", hour=2)
        for resident in world.residents.values():
            resident.activity = Activity("wander", minutes_left=600, using=True)
        world.step(60)
        self.assertEqual(world.containers["pantry_1"].count("vegetables"), 16)
        self.assertEqual(world.containers["pantry_2"].count("canned_beans"), 10)
        self.assertIn("se pierden 4 raciones", world.event_log[-1])

    def test_with_nothing_to_spoil_nothing_is_said(self) -> None:
        world = _settled()
        for pantry in PANTRIES:
            world.containers[pantry].items.clear()
        _only(world, "vermin", hour=2)
        for resident in world.residents.values():
            resident.activity = Activity("wander", minutes_left=600, using=True)
        world.step(60)
        self.assertNotIn("food_spoiled", _types(world))


class StormTests(unittest.TestCase):
    def setUp(self) -> None:
        self.world = _settled()
        self.world.clock.day = 2
        self.world.happened = {event_id: 2 for event_id in self.world.registries.world_events.events}
        self.raul = self.world.residents["raul"]

    def _storm(self, minutes: int = 120) -> None:
        self.world.weather = Weather("dust_storm", self.world.clock.total_minutes + minutes)

    def test_a_storm_comes_and_passes_and_both_are_said(self) -> None:
        _only(self.world, "dust_storm", hour=5)
        self.world.step(60)
        self.assertFalse(self.world.happenings.is_stormy(self.world), "it gives six hours' warning")
        self.world.step(6 * 60)
        self.assertTrue(self.world.happenings.is_stormy(self.world))
        lasts = self.world.weather.until - self.world.clock.total_minutes
        self.assertTrue(150 <= lasts <= 300, lasts)
        self.assertTrue(any("Se levanta una tormenta de polvo" in line for line in self.world.event_log))
        self.world.event_rng = SimulationRNG(1)
        self.world.step(lasts + 1)
        self.assertFalse(self.world.happenings.is_stormy(self.world))
        self.assertTrue(any("Amaina la tormenta de polvo" in line for line in self.world.event_log))

    def test_nothing_grows_in_a_storm_and_the_cook_carries_on(self) -> None:
        self.world.clock.hour = 11
        _on_duty(self.world, "raul")
        _on_duty(self.world, "marta")
        self.world.stock(self.world.residents["marta"].inventory, "vegetables", 6, None)
        self.world.containers["cooking_pot"].items.clear()
        self._storm(90)
        for _ in range(60):
            self.world.step(1)
            _keep_content(self.world)
        self.assertEqual(carried(self.raul, "vegetables"), 0)
        self.assertGreaterEqual(self.world.containers["cooking_pot"].count("stew"), 3)
        for _ in range(60):
            self.world.step(1)
            _keep_content(self.world)
        self.assertGreater(carried(self.raul, "vegetables"), 0, "once it passes the garden yields again")

    def test_nobody_sets_out_into_a_storm(self) -> None:
        sergio = self.world.residents["sergio"]
        self.world.clock.hour = 8
        self._storm(100)
        for _ in range(90):
            self.world.step(1)
            _keep_content(self.world)
        self.assertFalse(sergio.away)
        self.assertTrue(self.world.under_roof(sergio.tile), "he waits it out in the dry")
        for _ in range(120):
            self.world.step(1)
            _keep_content(self.world)
        self.assertTrue(sergio.away)

    def test_a_storm_wears_on_whoever_is_out_in_it_and_not_on_those_under_a_roof(self) -> None:
        indoors = self.world.residents["marta"]
        for resident, tile in ((self.raul, (20, 18)), (indoors, (5, 5))):
            resident.x, resident.y = tile
            resident.activity = Activity("wander", minutes_left=600, using=True)
        self._storm(200)
        self.world.step(100)
        self.assertAlmostEqual(self.raul.needs.stress, 3.0, places=1)
        self.assertEqual(indoors.needs.stress, 0.0)


class WorldEventDataAndSaveTests(unittest.TestCase):
    def setUp(self) -> None:
        self.manager = SaveManager()

    def test_bad_definitions_are_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "unknown kind"):
            world_event_settings_from_data({"events": {"x": {"kind": "meteor"}}})
        with self.assertRaisesRegex(ValueError, "hours within one day"):
            world_event_settings_from_data({"events": {"x": {"kind": "weather", "hours": [20, 6]}}})
        with self.assertRaisesRegex(ValueError, "share an id"):
            world_event_settings_from_data({"newcomers": [{"id": "a"}, {"id": "a"}]})
        with self.assertRaisesRegex(ValueError, "unknown job to answer the gate"):
            _registries_with("world_events.json", '"asks": "guard"', '"asks": "doorman"')
        with self.assertRaisesRegex(ValueError, "not a container kind"):
            _registries_with("world_events.json", '"container": "pantry"', '"container": "guard_post"')
        with self.assertRaisesRegex(ValueError, "unknown personality traits"):
            _registries_with("world_events.json", '"empathy": 70', '"charm": 70')
        with self.assertRaisesRegex(ValueError, "Unknown gate choice"):
            _registries_with("decisions.json", '"gate": "let_in"', '"gate": "ajar"')

    def test_every_newcomer_has_a_bed_waiting_only_while_there_is_one_and_a_name_of_their_own(self) -> None:
        world = SimulationWorld.demo_world()
        newcomers = world.registries.world_events.newcomers
        self.assertGreaterEqual(len(newcomers), 3)
        self.assertFalse({newcomer.newcomer_id for newcomer in newcomers} & world.residents.keys())
        self.assertTrue(all(newcomer.age >= 18 for newcomer in newcomers))
        self.assertGreater(world.happenings._free_beds(world), 0)

    def test_saving_with_a_stranger_at_the_gate_and_a_storm_on_continues_exactly_like_not_saving(self) -> None:
        original = _settled(seed=5)
        _only(original, "stranger")
        original.event_rng = SimulationRNG(11)
        original.happened.pop("dust_storm")
        _on_duty(original, "tomas")
        original.at_the_gate = "olga"
        original.interventions.ask(original, original.residents["tomas"], STRANGER_DECISION)
        original.weather = Weather("dust_storm", original.clock.total_minutes + 200)
        original.step(10)
        loaded = self.manager.from_data(json.loads(json.dumps(self.manager.to_data(original))))
        self.assertEqual(self.manager.to_data(loaded), self.manager.to_data(original))
        self.assertEqual((loaded.at_the_gate, loaded.weather), ("olga", original.weather))
        self.assertEqual(loaded.event_rng.get_state(), original.event_rng.get_state())
        original.step(3 * MINUTES_PER_DAY)
        loaded.step(3 * MINUTES_PER_DAY)
        self.assertEqual(self.manager.to_data(loaded), self.manager.to_data(original))

    def test_an_older_save_has_had_nothing_happen_to_it_and_gains_the_beds(self) -> None:
        world = SimulationWorld.demo_world(seed=9)
        data = self.manager.to_data(world)
        data["version"] = 11
        for key in ("event_rng", "happened", "weather", "at_the_gate", "newcomers_seen"):
            del data[key]
        data["interactables"] = [placed for placed in data["interactables"] if placed["id"] not in ("bed_10", "bed_11")]
        loaded = self.manager.from_data(json.loads(json.dumps(data)))
        self.assertEqual((loaded.happened, loaded.weather, loaded.at_the_gate, loaded.newcomers_seen), ({}, None, None, []))
        self.assertEqual(loaded.event_rng.get_state(), world.event_rng.get_state())
        self.assertIn("bed_11", loaded.interactables)
        loaded.step(3 * MINUTES_PER_DAY)

    def test_a_stranger_is_only_at_the_gate_while_someone_is_deciding(self) -> None:
        world = _settled()
        world.at_the_gate = "olga"
        data = self.manager.to_data(world)
        self.assertIsNone(self.manager.from_data(json.loads(json.dumps(data))).at_the_gate)
        data["weather"] = {"event_id": "blizzard", "until": 99999}
        self.assertIsNone(self.manager.from_data(json.loads(json.dumps(data))).weather)


class EventfulWeeksTests(unittest.TestCase):
    def test_three_weeks_of_whatever_comes_and_an_open_gate_leave_the_settlement_standing(self) -> None:
        world = SimulationWorld.demo_world(seed=5)
        started = len(world.residents)
        for _ in range(21 * MINUTES_PER_DAY):
            world.step(1)
            for decision in list(world.decisions.values()):
                if decision.kind == STRANGER_DECISION:
                    world.apply_command(ChooseOptionCommand(decision.decision_id, "open"))
            for resident in world.residents.values():
                for need in ("hunger", "tiredness", "social", "stress"):
                    self.assertLess(getattr(resident.needs, need), 100.0, (resident.name, need, world.clock.label))
        types = _types(world)
        self.assertIn("caravan_passed", types)
        self.assertIn("weather_changed", types)
        self.assertIn("newcomer_joined", types)
        self.assertGreater(len(world.residents), started)
        beds = sum(1 for placed in world.interactables.values() if placed.kind == "bed")
        self.assertLessEqual(len(world.residents), beds, "never more people than beds")
        newcomers = [resident for resident in world.residents.values() if resident.resident_id in world.newcomers_seen]
        self.assertTrue(newcomers)
        self.assertNotIn("no_food", types)


if __name__ == "__main__":
    unittest.main()
