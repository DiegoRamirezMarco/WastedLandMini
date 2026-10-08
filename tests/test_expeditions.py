import json
import tempfile
import unittest
from pathlib import Path

from save.save_manager import SaveManager
from simulation.commands import ChooseOptionCommand
from simulation.knowledge.knowledge_system import witnesses_of
from simulation.registries import DATA_DIR, BuiltInRegistries
from simulation.residents.needs import Needs
from simulation.social.social_system import SocialSystem
from simulation.work.expedition import expedition_rule_from_data, expedition_settings_from_data
from simulation.work.expedition_system import EXPEDITION_ACTION, RISKY_FIND
from simulation.world import SimulationWorld
from tests.worlds import no_store

MINUTES_PER_DAY = 24 * 60
SCRAP_PILES = ("scrap_workshop", "scrap_yard")


def _types(world: SimulationWorld) -> list[str]:
    return [line.split(" | ")[1] for line in world.event_log]


def _keep_content(world: SimulationWorld) -> None:
    for resident in world.residents.values():
        resident.needs = Needs(hunger=0, tiredness=0, social=0, stress=0)


def _settled(seed: int = 7) -> SimulationWorld:
    world = SimulationWorld.demo_world(seed=seed)
    no_store(world)
    world.relationships.clear()
    _keep_content(world)
    return world


def _run(world: SimulationWorld, minutes: int) -> None:
    for _ in range(minutes):
        world.step(1)
        _keep_content(world)


def _send_out(world: SimulationWorld, limit: int = 120):
    """Let the morning go by until the scavenger has left, and return them."""
    sergio = world.residents["sergio"]
    for _ in range(limit):
        world.step(1)
        _keep_content(world)
        if sergio.away:
            return sergio
    raise AssertionError("the scavenger never set out")


def _scrap(world: SimulationWorld) -> int:
    return sum(world.containers[pile].count("scrap") for pile in SCRAP_PILES)


def _carried(resident) -> dict[str, int]:
    """How many of each kind of thing somebody carries that is nobody's, of whatever rarity (S64)."""
    carried: dict[str, int] = {}
    for item in resident.inventory.items:
        if item.owner_id is None:
            carried[item.definition_id] = carried.get(item.definition_id, 0) + item.quantity
    return carried


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


class SettingOutTests(unittest.TestCase):
    def setUp(self) -> None:
        self.world = _settled()
        self.sergio = self.world.residents["sergio"]

    def test_the_scavenger_leaves_from_the_cart_and_is_gone_for_hours(self) -> None:
        self.assertFalse(self.sergio.away)
        sergio = _send_out(self.world)
        self.assertEqual(sergio.activity.action, EXPEDITION_ACTION)
        self.assertEqual(_types(self.world).count("expedition_left"), 1)
        self.assertTrue(any("Sergio sale del asentamiento a rebuscar" in line for line in self.world.event_log))
        trip = sergio.expedition
        gone_for = trip.returns_at - self.world.clock.total_minutes
        self.assertTrue(239 <= gone_for <= 360, gone_for)
        self.assertTrue(3 <= trip.finds <= 6)
        _run(self.world, 200)
        self.assertTrue(sergio.away)

    def test_nobody_sets_out_hungry_or_twice_in_a_day_or_on_their_day_off(self) -> None:
        self.sergio.needs.hunger = 60
        self.assertIsNone(self.world.work.candidate(self.world, self.sergio), "breakfast first")
        self.sergio.needs.hunger = 0
        self.assertIsNotNone(self.world.work.candidate(self.world, self.sergio))
        sergio = _send_out(self.world)
        sergio.expedition.returns_at = self.world.clock.total_minutes + 5
        sergio.expedition.finds = 0
        sergio.expedition.find_at = None
        _run(self.world, 120)
        self.assertFalse(sergio.away)
        self.assertEqual(_types(self.world).count("expedition_left"), 1, "one trip a day")
        self.assertTrue(any("Sergio se queda al cuidado del carro" in line for line in self.world.event_log))
        self.world.clock.day = 6
        self.world.clock.hour, self.world.clock.minute = 9, 0
        self.assertTrue(self.world.work.is_day_off(self.world, sergio))
        self.assertIsNone(self.world.work.candidate(self.world, sergio))

    def test_whoever_is_out_there_sees_nobody_and_cannot_be_reached(self) -> None:
        sergio = _send_out(self.world)
        self.assertNotIn("sergio", witnesses_of(self.world, sergio.tile))
        raul = self.world.residents["raul"]
        raul.x, raul.y = sergio.x + 1, sergio.y
        raul.needs.social = 95
        self.assertNotIn("sergio", [c.partner_id for c in SocialSystem().candidates(self.world, raul)])
        raul.activity = SocialSystem().pursue(self.world, raul, sergio, "argument")
        self.world.step(5)
        self.assertEqual(sergio.activity.action, EXPEDITION_ACTION)
        self.assertNotIn("argument_started", _types(self.world))

    def test_out_there_they_are_paid_and_eat_as_they_go(self) -> None:
        sergio = _send_out(self.world)
        credits, sergio.needs.hunger = sergio.credits, 20.0
        raul = self.world.residents["raul"]
        raul.needs.hunger = 20.0
        self.world.step(60)
        self.assertAlmostEqual(sergio.credits - credits, self.world.registries.economy.wage_per_hour)
        self.assertAlmostEqual(sergio.needs.hunger - 20.0, (raul.needs.hunger - 20.0) / 2, places=2)


class ComingBackTests(unittest.TestCase):
    def setUp(self) -> None:
        self.world = _settled()
        self.sergio = _send_out(self.world)
        self.trip = self.sergio.expedition
        self.trip.find_at = None

    def _return(self, finds: int, danger: float = 0.0) -> None:
        self.trip.finds, self.trip.danger = finds, danger
        self.trip.returns_at = self.world.clock.total_minutes + 1
        self.world.step(1)

    def test_they_come_back_with_what_they_found_in_their_hands(self) -> None:
        self._return(finds=6)
        self.assertFalse(self.sergio.away)
        carried = _carried(self.sergio)
        self.assertEqual(sum(carried.values()), 6)
        known = {entry.item for entry in self.world.registries.expeditions.loot}
        self.assertLessEqual(set(carried), known)
        self.assertEqual(_types(self.world).count("expedition_returned"), 1)
        self.assertIn("Sergio vuelve de fuera con", self.world.event_log[-1])
        self.assertIn("expedition_returned", [event.event_type for event in self.world.history])

    def test_a_trip_can_come_back_empty_and_what_no_longer_exists_is_never_found(self) -> None:
        self._return(finds=0)
        self.assertEqual(_carried(self.sergio), {})
        self.assertIn("Sergio vuelve de fuera de vacío", self.world.event_log[-1])

        world = SimulationWorld.demo_world(registries=BuiltInRegistries.load())
        _keep_content(world)
        sergio = _send_out(world)
        sergio.expedition.find_at, sergio.expedition.finds = None, 40
        sergio.expedition.returns_at = world.clock.total_minutes + 1
        world.step(1)
        self.assertEqual(sum(_carried(sergio).values()), 40)
        self.assertNotIn("pizza_radioactiva", _carried(sergio), "that pack is not installed here")

    def test_the_commonest_things_out_there_turn_up_most(self) -> None:
        self._return(finds=200)
        carried = _carried(self.sergio)
        self.assertGreater(carried["scrap"], carried["canned_beans"])
        self.assertGreater(carried["canned_beans"], carried.get("old_radio", 0))

    def test_danger_is_what_decides_whether_they_come_back_hurt(self) -> None:
        self._return(finds=1, danger=1.0)
        self.assertLess(self.sergio.health, 100.0)
        self.assertIn("injured", _types(self.world))
        self.assertTrue(any("una salida fuera del asentamiento" in line for line in self.world.event_log))
        self.setUp()
        self._return(finds=1, danger=0.0)
        self.assertEqual(self.sergio.health, 100.0)

    def test_scrap_goes_to_a_scrap_pile_and_the_rest_to_the_shop_by_hand(self) -> None:
        self._return(finds=0)
        self.world.stock(self.sergio.inventory, "scrap", 3, None)
        self.world.stock(self.sergio.inventory, "canned_beans", 2, None)
        scrap, counter = _scrap(self.world), self.world.containers["shop_counter"]
        beans = counter.count("canned_beans")
        for _ in range(180):
            self.world.step(1)
            _keep_content(self.world)
            # Nothing reaches a container except out of his hands.
            in_hand = _carried(self.sergio)
            self.assertEqual(_scrap(self.world) + in_hand.get("scrap", 0), scrap + 3)
            self.assertEqual(counter.count("canned_beans") + in_hand.get("canned_beans", 0), beans + 2)
            if not in_hand:
                break
        self.assertEqual(_carried(self.sergio), {})
        self.assertEqual(_scrap(self.world), scrap + 3)
        self.assertEqual(counter.count("canned_beans"), beans + 2)
        hauls = [line for line in self.world.event_log if "goods_hauled" in line and "Sergio deja" in line]
        self.assertEqual(len(hauls), 2)
        self.assertIn("chatarra (3)", hauls[0])
        self.assertIn("judías en conserva (2)", hauls[1])


class RiskyFindTests(unittest.TestCase):
    def setUp(self) -> None:
        self.world = _settled()
        self.sergio = _send_out(self.world)
        self.trip = self.sergio.expedition
        now = self.world.clock.total_minutes
        self.trip.find_at, self.trip.returns_at, self.trip.finds, self.trip.danger = now + 1, now + 200, 4, 0.1
        self.world.step(2)
        self.decision = next(iter(self.world.decisions.values()))

    def test_it_is_put_to_the_player_without_bringing_them_home(self) -> None:
        self.assertEqual((self.decision.kind, self.decision.resident_id), (RISKY_FIND, "sergio"))
        self.assertIn("risky_find", _types(self.world))
        self.assertTrue(self.sergio.away)
        self.assertEqual(self.sergio.activity.action, EXPEDITION_ACTION)
        self.assertIsNone(self.trip.find_at, "it only comes up once a trip")

    def test_advice_decides_between_going_for_it_and_turning_back(self) -> None:
        returns_at = self.trip.returns_at
        self.assertEqual(self.world.apply_command(ChooseOptionCommand(self.decision.decision_id, "go")), "push_on")
        self.assertEqual(self.trip.finds, 8)
        self.assertAlmostEqual(self.trip.danger, 0.45)
        self.assertEqual(self.trip.returns_at, returns_at + 60)
        self.assertTrue(self.sergio.away, "deciding does not end the trip")

        self.setUp()
        now = self.world.clock.total_minutes
        outcome = self.world.apply_command(ChooseOptionCommand(self.decision.decision_id, "careful"))
        self.assertEqual(outcome, "turn_back")
        self.assertEqual((self.trip.finds, self.trip.returns_at), (2, now + 30))
        self.assertAlmostEqual(self.trip.danger, 0.1)

    def test_left_alone_the_bold_go_for_it_and_the_timid_do_not(self) -> None:
        self.assertEqual(self.world.interventions.resolve(self.world, self.decision.decision_id, None), "push_on")
        self.setUp()
        self.sergio.personality.courage = self.sergio.personality.greed = 10
        self.sergio.personality.impulsiveness = 10
        self.assertEqual(self.world.interventions.resolve(self.world, self.decision.decision_id, None), "turn_back")

    def test_they_do_not_come_back_until_they_have_made_up_their_mind(self) -> None:
        self.trip.returns_at = self.world.clock.total_minutes
        self.world.step(10)
        self.assertTrue(self.sergio.away)
        self.world.apply_command(ChooseOptionCommand(self.decision.decision_id, "careful"))
        self.trip.returns_at = self.world.clock.total_minutes
        self.world.step(1)
        self.assertFalse(self.sergio.away)
        self.assertEqual(self.world.decisions, {})


class RepairMaterialTests(unittest.TestCase):
    def setUp(self) -> None:
        self.world = _settled()
        self.raul = self.world.residents["raul"]
        self.raul.job_id = None
        self.hoe = self.raul.inventory.stack_of("hoe", "raul")
        self.hoe.condition = 20.0
        self.world.clock.hour = 10
        paco = self.world.residents["paco"]
        for _ in range(180):
            self.world.step(1)
            _keep_content(self.world)
            if self.world.work.on_duty(self.world, paco):
                break

    def _repairs(self) -> list[str]:
        candidates = self.world.activities.routine.candidates(self.world, self.raul)
        return [candidate.name for candidate in candidates if candidate.name == "repair"]

    def test_with_no_scrap_there_is_nothing_to_mend_with(self) -> None:
        self.assertEqual(self._repairs(), ["repair"])
        for pile in SCRAP_PILES:
            self.world.containers[pile].items.clear()
        self.assertEqual(self._repairs(), [])
        self.world.stock(self.world.containers["scrap_yard"], "scrap", 1, None)
        self.assertEqual(self._repairs(), ["repair"])

    def test_each_repair_uses_up_a_piece_of_scrap(self) -> None:
        before = _scrap(self.world)
        bench = self.world.interactables["workbench"]
        self.raul.activity = self.world.activities.routine._use(self.world, self.raul, bench)
        for _ in range(120):
            self.world.step(1)
            _keep_content(self.world)
            if self.hoe.condition >= 100.0:
                break
        self.assertEqual(self.hoe.condition, 100.0)
        self.assertEqual(_scrap(self.world), before - 1)


class ExpeditionDataAndSaveTests(unittest.TestCase):
    def setUp(self) -> None:
        self.manager = SaveManager()

    def test_impossible_rules_are_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "impossible"):
            expedition_rule_from_data("x", {"minutes": [300, 100]})
        with self.assertRaisesRegex(ValueError, "impossible"):
            expedition_rule_from_data("x", {"danger": 1.5})
        with self.assertRaisesRegex(ValueError, "positive"):
            expedition_settings_from_data({"loot": [{"item": "scrap", "weight": 0}]})
        self.assertEqual(expedition_settings_from_data({}).loot, ())

    def test_finds_and_repair_material_must_be_kept_in_containers(self) -> None:
        with self.assertRaisesRegex(ValueError, "delivered to guard_post"):
            _registries_with("expeditions.json", '"to": "shop_counter"', '"to": "guard_post"')
        with self.assertRaisesRegex(ValueError, "repair material"):
            _registries_with("interactables.json", '"material_from": "scrap_pile"', '"material_from": "guard_post"')
        with self.assertRaisesRegex(ValueError, "Unknown expedition choice"):
            _registries_with("decisions.json", '"expedition": "push_on"', '"expedition": "dig_in"')

    def test_saving_while_someone_is_out_there_continues_exactly_like_not_saving(self) -> None:
        original = SimulationWorld.demo_world(seed=5)
        while not original.residents["sergio"].away:
            original.step(1)
        original.step(30)
        loaded = self.manager.from_data(json.loads(json.dumps(self.manager.to_data(original))))
        self.assertEqual(self.manager.to_data(loaded), self.manager.to_data(original))
        self.assertTrue(loaded.residents["sergio"].away)
        self.assertEqual(loaded.residents["sergio"].expedition, original.residents["sergio"].expedition)
        original.step(2 * MINUTES_PER_DAY)
        loaded.step(2 * MINUTES_PER_DAY)
        self.assertEqual(self.manager.to_data(loaded), self.manager.to_data(original))

    def test_a_trip_and_being_out_there_are_only_kept_together(self) -> None:
        world = _settled()
        _send_out(world)
        data = self.manager.to_data(world)
        sergio = next(resident for resident in data["residents"] if resident["id"] == "sergio")
        sergio["activity"] = None
        loaded = self.manager.from_data(json.loads(json.dumps(data)))
        self.assertFalse(loaded.residents["sergio"].away)

        data = self.manager.to_data(world)
        next(resident for resident in data["residents"] if resident["id"] == "sergio")["expedition"] = None
        loaded = self.manager.from_data(json.loads(json.dumps(data)))
        self.assertIsNone(loaded.residents["sergio"].activity)
        loaded.step(MINUTES_PER_DAY)

    def test_an_older_save_gains_the_cart_and_scrap_to_mend_with(self) -> None:
        world = SimulationWorld.demo_world()
        data = self.manager.to_data(world)
        data["version"] = 10
        data["interactables"] = [placed for placed in data["interactables"] if placed["id"] != "handcart"]
        for pile in SCRAP_PILES:
            del data["containers"][pile]
        data["residents"] = [resident for resident in data["residents"] if resident["id"] != "sergio"]
        for resident in data["residents"]:
            del resident["expedition"], resident["last_expedition_day"]
        loaded = self.manager.from_data(json.loads(json.dumps(data)))
        self.assertIn("handcart", loaded.interactables)
        self.assertEqual(_scrap(loaded), 8)
        self.assertEqual({resident.away for resident in loaded.residents.values()}, {False})
        loaded.step(2 * MINUTES_PER_DAY)
        taken = loaded.staffing.workers(loaded, "scavenger")
        self.assertTrue(taken or "scavenger" in loaded.vacancies, "the new job is there for someone to take")


class BeyondTheFenceTests(unittest.TestCase):
    def test_a_week_of_trips_keeps_the_shop_stocked_and_the_workshop_in_scrap(self) -> None:
        world = SimulationWorld.demo_world(seed=3)
        counter = world.containers["shop_counter"]
        stocked = sum(item.quantity for item in counter.items)
        scrap = _scrap(world)
        away_minutes = 0
        for _ in range(7 * MINUTES_PER_DAY):
            world.step(1)
            away_minutes += world.residents["sergio"].away
            for resident in world.residents.values():
                for need in ("hunger", "tiredness", "social", "stress"):
                    self.assertLess(getattr(resident.needs, need), 100.0, (resident.name, need, world.clock.label))
        types = _types(world)
        self.assertGreaterEqual(types.count("expedition_returned"), 5)
        self.assertEqual(types.count("expedition_left"), types.count("expedition_returned"))
        self.assertGreater(away_minutes / 60, 20)
        bought = types.count("item_bought")
        self.assertGreater(bought, 5)
        self.assertGreater(sum(item.quantity for item in counter.items) + bought, stocked, "more came in than there was")
        repairs = sum("a arreglar" in line for line in world.event_log)
        self.assertGreaterEqual(repairs, 2)
        self.assertGreaterEqual(_scrap(world), scrap - repairs, "what the repairs used came out of the piles")
        self.assertTrue(any("Sergio deja chatarra" in line for line in world.event_log))
        # Whether anybody came to stay that week goes by what the week brought. Nobody was lost in it.
        self.assertGreaterEqual(len(world.residents), 9)
        self.assertEqual(world.deaths, [])


if __name__ == "__main__":
    unittest.main()
