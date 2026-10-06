import json
import subprocess
import sys
import unittest
from pathlib import Path

from save.save_manager import SaveManager
from simulation.commands import ChooseOptionCommand, PlaceObjectCommand
from simulation.items.custom_content import validate_item_data
from simulation.registries import DATA_DIR, BuiltInRegistries
from simulation.residents.activity import Activity
from simulation.residents.needs import Needs
from simulation.residents.personality import Personality
from simulation.residents.resident import Resident
from simulation.health.injury import Injury
from simulation.items.item_system import USE_ITEM_ACTION
from simulation.substances.substance import Habit, substance_from_data, substance_settings_from_data
from simulation.substances.substance_system import HABIT, TEMPTED
from simulation.tastes.taste import PEOPLE, Taste
from simulation.work.work_system import WORK_ACTION
from simulation.world import SimulationWorld

ROOT = Path(__file__).resolve().parent.parent
MINUTES_PER_DAY = 24 * 60
# Out in the open, where whoever stands near sees and nothing is under a roof.
OPEN_GROUND = (20, 12)
# Inside the dormitory, and just outside its wall.
IN_THE_DORMITORY = (6, 5)
OUTSIDE_THE_DORMITORY = (6, 8)
FAR_AWAY = (30, 15)


def _content(world: SimulationWorld, *resident_ids: str) -> None:
    for resident_id in resident_ids or world.residents:
        world.residents[resident_id].needs = Needs(hunger=0, tiredness=0, social=0, stress=0)


def _few(seed: int = 7) -> SimulationWorld:
    """Marta, Raúl and Lucía alone, content, with no jobs, no grudges and nothing put by."""
    world = SimulationWorld.demo_world(seed=seed)
    for extra in [resident_id for resident_id in world.residents if resident_id not in ("marta", "raul", "lucia")]:
        del world.residents[extra]
    world.relationships.clear()
    for resident in world.residents.values():
        resident.job_id = resident.post_id = None
        resident.inventory.items.clear()
        resident.personality = Personality()
    for container_id in ("cooking_pot", "crate_dorm", "crate_1"):
        world.containers[container_id].items.clear()
    _content(world)
    return world


def _place(world: SimulationWorld, resident_id: str, tile: tuple[int, int]) -> Resident:
    resident = world.residents[resident_id]
    resident.x, resident.y = tile
    resident.activity = Activity("wander", minutes_left=600, using=True)
    return resident


def _take(world: SimulationWorld, resident: Resident, item_id: str) -> None:
    """Have a resident take something, as they would on finishing with it."""
    world.items.take_in(world, resident, world.registries.items.get(item_id))


def _put_on_duty(world: SimulationWorld, resident_id: str, minutes: int = 600) -> Resident:
    resident = world.residents[resident_id]
    post = world.interactables[resident.post_id]
    passable = world.passable()
    resident.x, resident.y = next(
        (post.x + dx, post.y + dy)
        for dx, dy in ((0, 1), (0, -1), (-1, 0), (1, 0), (2, 0))
        if passable((post.x + dx, post.y + dy))
    )
    resident.activity = Activity(WORK_ACTION, resident.post_id, minutes_left=minutes, using=True)
    resident.current_action = WORK_ACTION
    return resident


def _types(world: SimulationWorld) -> list[str]:
    return [line.split(" | ")[1] for line in world.event_log]


def _dependents(world: SimulationWorld, item_id: str) -> list[str]:
    return [
        resident.resident_id
        for resident in world.residents.values()
        if item_id in resident.habits and resident.habits[item_id].dependent
    ]


class EffectTests(unittest.TestCase):
    def setUp(self) -> None:
        self.world = _few()
        self.raul = _place(self.world, "raul", OPEN_GROUND)
        for name in ("marta", "lucia"):
            _place(self.world, name, FAR_AWAY)
        self.substances = self.world.substances

    def test_the_game_comes_with_one_for_each_way_of_taking_them(self) -> None:
        items = self.world.registries.items
        routes = {item_id: items.get(item_id).substance.route for item_id in items.ids() if items.get(item_id).substance}
        self.assertEqual(
            routes,
            {"liquor": "swallowed", "cigarette": "smoked", "sedative": "swallowed", "powder": "sniffed", "syringe": "injected"},
        )
        self.assertEqual(set(routes.values()), set(self.world.registries.substances.routes))
        self.assertIsNone(items.get("canned_beans").substance)

    def test_the_good_it_does_lasts_while_it_lasts(self) -> None:
        self.raul.needs.stress = 60
        _take(self.world, self.raul, "liquor")
        self.assertEqual(self.raul.needs.stress, 48, "what it does on the spot")
        self.assertTrue(self.substances.is_under(self.world, self.raul, "liquor"))
        self.assertFalse(self.substances.is_under(self.world, self.raul, "powder"))
        self.assertEqual(self.substances.work_pace(self.world, self.raul), 0.85)
        self.assertTrue(any("Raúl se toma un aguardiente" in line for line in self.world.event_log))
        before = self.raul.needs.stress
        self.world.step(60)
        self.assertLess(self.raul.needs.stress, before - 1.0, "and minute by minute after")
        self.world.step(61)
        self.assertFalse(self.substances.is_under(self.world, self.raul))
        self.assertEqual(self.substances.work_pace(self.world, self.raul), 1.0)

    def test_what_comes_after_is_its_own_harm(self) -> None:
        _take(self.world, self.raul, "powder")
        self.assertEqual(self.substances.work_pace(self.world, self.raul), 1.25, "it has them work faster")
        self.world.step(181)
        self.raul.needs.stress, self.raul.needs.tiredness = 0, 0
        self.world.step(120)
        self.assertGreater(self.raul.needs.stress, 8, "and pay for it afterwards")
        self.assertGreater(self.raul.needs.tiredness, 10)
        self.assertEqual(len(self.raul.under), 1, "it is still on them, coming down")
        self.world.step(121)
        self.assertEqual(self.raul.under, [])

    def test_too_much_of_one_harms_and_can_kill(self) -> None:
        _take(self.world, self.raul, "liquor")
        self.assertEqual(self.raul.health, 100.0)
        _take(self.world, self.raul, "liquor")
        self.assertEqual([(injury.kind, injury.severity) for injury in self.raul.injuries], [("intoxication", 6.0)])
        _take(self.world, self.raul, "syringe")
        self.assertEqual(self.raul.health, 90.0, "some harm whoever takes them at all")
        self.raul.injuries.append(Injury("cut", 65.0))
        _take(self.world, self.raul, "syringe")
        self.assertNotIn("raul", self.world.residents)
        self.assertEqual(self.world.deaths[-1].resident_id, "raul")

    def test_someone_under_a_needle_notices_nothing(self) -> None:
        self.assertTrue(self.world.is_aware(self.raul))
        _take(self.world, self.raul, "syringe")
        self.assertFalse(self.world.is_aware(self.raul))
        self.world.step(241)
        self.assertTrue(self.world.is_aware(self.raul))

    def test_nobody_but_the_rash_takes_more_of_what_they_are_already_under(self) -> None:
        liquor = self.world.registries.items.get("liquor")
        self.assertEqual(self.substances.wish(self.world, self.raul, liquor), 0.0)
        _take(self.world, self.raul, "liquor")
        self.assertIsNone(self.substances.wish(self.world, self.raul, liquor))
        self.raul.personality.impulsiveness = 80
        self.assertEqual(self.substances.wish(self.world, self.raul, liquor), 0.0)


class SeenTests(unittest.TestCase):
    def setUp(self) -> None:
        self.world = _few()
        self.raul, self.marta, self.lucia = (self.world.residents[name] for name in ("raul", "marta", "lucia"))

    def _taste(self, resident: Resident, taste_id: str, leaning: float) -> None:
        self.world.tastes.profile(self.world, resident).of(PEOPLE)[taste_id] = Taste(leaning=leaning)

    def test_two_who_watch_the_same_drunk_feel_differently_about_them(self) -> None:
        _place(self.world, "raul", OPEN_GROUND)
        _place(self.world, "marta", (21, 12))
        _place(self.world, "lucia", (19, 12))
        self._taste(self.marta, "drunks", -80)
        self._taste(self.lucia, "drunks", 80)
        _take(self.world, self.raul, "liquor")
        self.assertLess(self.world.relationship("marta", "raul").affection, 0)
        self.assertGreater(self.world.relationship("lucia", "raul").affection, 0)
        self.assertIn("substance_seen", _types(self.world))
        facts = [fact.text for fact in self.world.knowledge.facts.values()]
        self.assertIn("Raúl había bebido de más", facts)
        self.assertTrue(all(self.world.knowledge.knows(name, fact_id) for name in ("marta", "lucia") for fact_id in self.world.knowledge.facts))

    def test_someone_who_minds_neither_way_and_someone_who_is_not_there(self) -> None:
        _place(self.world, "raul", OPEN_GROUND)
        _place(self.world, "marta", (21, 12))
        _place(self.world, "lucia", FAR_AWAY)
        self._taste(self.marta, "drunks", 0)
        self._taste(self.lucia, "drunks", -80)
        _take(self.world, self.raul, "liquor")
        self.assertEqual(self.world.relationship("marta", "raul").affection, 0)
        self.assertEqual(self.world.relationships.get(("lucia", "raul")), None, "she saw nothing")

    def test_smoke_indoors_is_minded_by_those_in_the_room_and_by_nobody_outside_it(self) -> None:
        for resident in (self.marta, self.lucia):
            self._taste(resident, "smokers", -80)
        _place(self.world, "raul", IN_THE_DORMITORY)
        _place(self.world, "marta", (4, 5))
        _place(self.world, "lucia", OUTSIDE_THE_DORMITORY)
        self.assertTrue(self.world.under_roof(self.raul.tile) and not self.world.under_roof(self.lucia.tile))
        _take(self.world, self.raul, "cigarette")
        self.assertLess(self.world.relationship("marta", "raul").affection, 0)
        lucia = self.world.relationships.get(("lucia", "raul"))
        self.assertTrue(lucia is None or lucia.affection == 0)

        outdoors = _few()
        for name in ("marta", "lucia"):
            outdoors.tastes.profile(outdoors, outdoors.residents[name]).of(PEOPLE)["smokers"] = Taste(leaning=-80)
            _place(outdoors, name, (21, 12))
        _take(outdoors, _place(outdoors, "raul", OPEN_GROUND), "cigarette")
        self.assertEqual(outdoors.relationships.get(("marta", "raul")), None, "in the open it bothers nobody")


class DependenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.world = _few()
        self.raul = _place(self.world, "raul", OPEN_GROUND)
        for name in ("marta", "lucia"):
            _place(self.world, name, FAR_AWAY)
        self.substances = self.world.substances
        self.settings = self.world.registries.substances

    def _a_night_at_the_bar(self, seed: int) -> list[str]:
        world = SimulationWorld.demo_world(seed=seed)
        for _ in range(12):
            for resident in list(world.residents.values()):
                _take(world, resident, "liquor")
                resident.injuries.clear()
            world.clock.advance_minutes(180)
        return _dependents(world, "liquor")

    def test_the_same_drink_leaves_one_dependent_and_another_not_and_the_same_seed_the_same_ones(self) -> None:
        first = self._a_night_at_the_bar(5)
        self.assertTrue(0 < len(first) < 9, first)
        self.assertEqual(self._a_night_at_the_bar(5), first)
        self.assertNotEqual(self._a_night_at_the_bar(6), first)

    def test_the_more_of_a_habit_the_likelier_and_it_is_said_when_it_comes(self) -> None:
        self.raul.habits["cigarette"] = Habit(uses=40)
        for _ in range(40):
            _take(self.world, self.raul, "cigarette")
        self.assertTrue(self.raul.habits["cigarette"].dependent)
        self.assertEqual(_types(self.world).count("dependence_began"), 1)
        self.assertTrue(any("Raúl ya no sabe pasar sin un cigarro liado" in line for line in self.world.event_log))

    def test_whoever_depends_on_something_wants_it_and_is_the_worse_for_going_without(self) -> None:
        cigarette = self.world.registries.items.get("cigarette")
        now = self.world.clock.total_minutes
        self.raul.habits["cigarette"] = Habit(uses=9, dependent=True, last_taken=now)
        self.assertFalse(self.substances.craves(self.world, self.raul, "cigarette"), "they have just had one")
        self.assertEqual(self.substances.work_pace(self.world, self.raul), 1.0)
        self.raul.habits["cigarette"].last_taken = now - 481
        self.assertTrue(self.substances.craves(self.world, self.raul, "cigarette"))
        self.assertEqual(self.substances.wish(self.world, self.raul, cigarette), self.settings.craving_wish)
        self.assertEqual(self.substances.work_pace(self.world, self.raul), self.settings.withdrawal_pace)
        self.assertEqual(self.world.trade.want(self.world, self.raul, cigarette, 400), 1.25, "at any price")
        self.world.step(60)
        self.assertGreater(self.raul.needs.stress, 2.0)
        self.assertEqual(self.raul.habits["cigarette"].without, 60.0)

    def test_someone_dependent_goes_after_what_they_have_by_them(self) -> None:
        now = self.world.clock.total_minutes
        self.raul.habits["cigarette"] = Habit(uses=9, dependent=True, last_taken=now - 600, allowed_until=now + 600)
        self.raul.activity = None
        self.world.stock(self.raul.inventory, "cigarette", 2, "raul")
        for _ in range(30):
            self.world.step(1)
            self.raul.needs = Needs(hunger=0, tiredness=0, social=0, stress=0)
            if "substance_taken" in _types(self.world):
                break
        self.assertIn("substance_taken", _types(self.world))
        self.assertEqual(self.raul.inventory.count("cigarette"), 1, "and it is used up")
        self.assertEqual(self.raul.habits["cigarette"].uses, 10)

    def test_long_enough_without_it_passes_and_sooner_under_a_medic(self) -> None:
        now = self.world.clock.total_minutes
        passes = self.settings.passes_after_minutes
        self.raul.habits["cigarette"] = Habit(uses=9, dependent=True, last_taken=now - 600, without=passes - 2)
        self.world.step(1)
        self.assertTrue(self.raul.habits["cigarette"].dependent)
        self.world.step(1)
        habit = self.raul.habits["cigarette"]
        self.assertEqual((habit.dependent, habit.recovered), (False, True))
        self.assertEqual(_types(self.world).count("dependence_passed"), 1)
        self.assertEqual(self.substances.work_pace(self.world, self.raul), 1.0)

        world = SimulationWorld.demo_world()
        _content(world)
        vera, paco = _put_on_duty(world, "vera"), world.residents["paco"]
        bed = world.interactables["clinic_bed_1"]
        paco.x, paco.y = bed.x, bed.y
        paco.activity = Activity("rest", "clinic_bed_1", minutes_left=600, using=True)
        paco.habits["liquor"] = Habit(uses=9, dependent=True, last_taken=world.clock.total_minutes - 2000)
        world.clock.hour = 10
        world.step(10)
        self.assertTrue(world.work.on_duty(world, vera))
        self.assertEqual(paco.habits["liquor"].without, 10 * self.settings.care_factor)
        self.assertEqual(paco.activity.target_id, "clinic_bed_1", "well as he is, he stays to be seen through it")
        clinic = world.definition_of(bed).use
        self.assertGreater(world.substances.care_wish(world, paco, clinic), 0)
        self.assertEqual(world.substances.care_wish(world, vera, clinic), 0, "she is going without nothing")
        days = world.registries.economy.idle_days
        paco.last_worked = world.clock.total_minutes - (days + 1) * MINUTES_PER_DAY
        world.step(1)
        self.assertTrue(world.trade.supplied(world, paco), "nobody lying in care is held to have stopped working")
        vera.job_id, vera.activity = None, None
        world.step(2)
        self.assertNotEqual(getattr(paco.activity, "target_id", None), "clinic_bed_1", "with nobody to see him through it he gets up")


class SayTests(unittest.TestCase):
    """Starting on something that hooks, going back to it, and now and then a habit."""

    def setUp(self) -> None:
        self.world = _few()
        self.raul = self.world.residents["raul"]
        self.raul.x, self.raul.y = OPEN_GROUND
        for name in ("marta", "lucia"):
            _place(self.world, name, FAR_AWAY)
        self.cigarette = self.world.registries.items.get("cigarette")

    def _reach_for_it(self, limit: int = 20) -> None:
        """Let Raúl, who has one on him and nerves enough to want it, get as far as he gets."""
        for _ in range(limit):
            self.raul.needs = Needs(hunger=0, tiredness=0, social=0, stress=70)
            uses = [c for c in self.world.items.candidates(self.world, self.raul) if c.name == USE_ITEM_ACTION]
            if uses and (self.raul.activity is None or self.raul.activity.action != USE_ITEM_ACTION):
                self.raul.activity = self.world.items.plan(self.world, self.raul, uses[0])
            self.world.step(1)
            if self.world.decisions or "substance_taken" in _types(self.world):
                return

    def test_the_first_time_with_something_that_hooks_they_stop_and_the_player_may_talk_them_out_of_it(self) -> None:
        self.world.stock(self.raul.inventory, "cigarette", 1, "raul")
        self.raul.personality = Personality(impulsiveness=20, courage=80)
        self._reach_for_it()
        decision = next(iter(self.world.decisions.values()))
        self.assertEqual((decision.kind, decision.resident_id), (TEMPTED, "raul"))
        self.assertIn("un cigarro liado", decision.prompt)
        self.assertEqual(self.raul.tempted_by, "cigarette")
        self.assertNotIn("substance_taken", _types(self.world))
        self.assertIsNone(self.world.substances.wish(self.world, self.raul, self.cigarette), "not while they think it over")
        self.assertEqual(self.world.apply_command(ChooseOptionCommand(decision.decision_id, "discourage")), "resist")
        self.assertIsNone(self.raul.tempted_by)
        self._reach_for_it()
        self.assertEqual((self.world.decisions, self.raul.inventory.count("cigarette")), ({}, 1))
        self.assertNotIn("substance_taken", _types(self.world))
        self.world.step(self.world.registries.substances.resist_minutes)
        self._reach_for_it()
        self.assertEqual(len(self.world.decisions), 1, "it is put to them again when the resolve wears off")

    def test_left_to_themselves_the_rash_go_ahead(self) -> None:
        self.world.stock(self.raul.inventory, "cigarette", 1, "raul")
        self.raul.personality = Personality(impulsiveness=95, courage=10)
        self._reach_for_it()
        decision = next(iter(self.world.decisions.values()))
        self.assertEqual(self.world.apply_command(ChooseOptionCommand(decision.decision_id, "neutral")), "take")
        self._reach_for_it()
        self.assertIn("substance_taken", _types(self.world))
        self.assertEqual(self.raul.inventory.count("cigarette"), 0)

    def test_a_drink_like_any_other_asks_nobody(self) -> None:
        liquor = self.world.registries.items.get("liquor")
        self.assertTrue(self.world.substances.may_take(self.world, self.raul, liquor))
        self.assertEqual(self.world.decisions, {})

    def test_going_back_to_it_after_days_without_is_asked_and_a_habit_only_now_and_then(self) -> None:
        now = self.world.clock.total_minutes
        may_take = lambda: self.world.substances.may_take(self.world, self.raul, self.cigarette)
        self.raul.habits["cigarette"] = Habit(uses=30, recovered=True, last_taken=now - 3 * MINUTES_PER_DAY)
        self.assertFalse(may_take())
        relapse = next(iter(self.world.decisions.values()))
        self.assertEqual(relapse.kind, TEMPTED)
        self.world.interventions.resolve(self.world, relapse.decision_id, "discourage")

        self.raul.habits["cigarette"] = Habit(uses=30, dependent=True, last_taken=now - 600)
        self.assertFalse(may_take())
        habit = next(iter(self.world.decisions.values()))
        self.assertEqual(habit.kind, HABIT)
        self.world.interventions.resolve(self.world, habit.decision_id, "neutral")
        self.raul.habits["cigarette"].allowed_until = self.raul.habits["cigarette"].resisting_until = 0
        self.assertTrue(may_take(), "not asked again for days: it is their habit, and they go on")
        self.assertEqual(self.world.decisions, {})
        self.world.step(3 * MINUTES_PER_DAY + 1)
        self.raul.habits["cigarette"].last_taken = self.world.clock.total_minutes - 600
        self.assertFalse(may_take())


class MadeHereTests(unittest.TestCase):
    def test_whoever_keeps_the_bar_makes_what_it_serves_out_of_water(self) -> None:
        world = SimulationWorld.demo_world()
        world.relationships.clear()
        bar, tank = world.containers["bar"], world.containers["water_tank"]
        self.assertEqual(bar.count("liquor"), 12)
        bar.items.clear()
        water = tank.count("water")
        world.clock.hour = 18
        for _ in range(4 * 60):
            world.step(1)
            _content(world)
        self.assertGreaterEqual(bar.count("liquor"), 3)
        self.assertLess(tank.count("water"), water)

    def test_a_drink_at_the_bar_is_one_of_what_it_holds_and_is_on_whoever_has_it(self) -> None:
        world = SimulationWorld.demo_world()
        world.relationships.clear()
        _content(world)
        _put_on_duty(world, "lucia")
        ines = world.residents["ines"]
        ines.credits = 10.0
        ines.activity = world.activities.routine._use(world, ines, world.interactables["bar"])
        for _ in range(120):
            world.step(1)
            _content(world, *[name for name in world.residents if name != "ines"])
            if "substance_taken" in _types(world):
                break
        self.assertEqual(world.containers["bar"].count("liquor"), 11)
        self.assertTrue(world.substances.is_under(world, ines, "liquor"))
        self.assertEqual(ines.credits, 8.0)

    def test_a_laboratory_has_to_be_worked_out_and_makes_the_rest_in_turn(self) -> None:
        world = SimulationWorld.demo_world()
        world.relationships.clear()
        self.assertFalse(world.research.knows(world, "chemistry"))
        self.assertIn("lab_bench", world.registries.research.subjects["chemistry"].objects)
        self.assertFalse(world.apply_command(PlaceObjectCommand("lab_bench", (14, 11))).ok)
        bench = world.urbanism.place_object(world, "lab_bench", (14, 11)).entity_id
        paco = world.residents["paco"]
        self.assertTrue(world.staffing.assign(world, paco, "chemist"))
        _put_on_duty(world, "paco", minutes=400)
        for _ in range(380):
            world.step(1)
            _content(world)
        made = {item.definition_id: item.quantity for item in world.containers[bench].items}
        self.assertEqual(made, {"cigarette": 1, "sedative": 1, "powder": 1, "syringe": 1})
        self.assertIsNotNone(world.definition_of(world.interactables[bench]).use.sells)
        self.assertEqual(world.fund.till(world), "shop_counter", "the shop is still where the fund is kept")


class SubstanceDataAndSaveTests(unittest.TestCase):
    def setUp(self) -> None:
        self.manager = SaveManager()

    def test_a_substance_a_pack_brings_works_with_no_code_of_its_own(self) -> None:
        registries = BuiltInRegistries.load(DATA_DIR)
        data = {
            "id": "moon_tea", "name": "té de luna", "article": "un", "category": "vice", "base_value": 5,
            "effects": {"stress": -5},
            "substance": {"route": "swallowed", "minutes": 60, "work_pace": 0.5, "dependence": 1.0, "sign": "high"},
        }
        validate_item_data(data, "moon_tea", None)
        registries.items.load_mapping(data)
        registries.validate()
        world = SimulationWorld.demo_world(registries=registries)
        raul = world.residents["raul"]
        _take(world, raul, "moon_tea")
        self.assertEqual(world.substances.work_pace(world, raul), 0.5)
        self.assertTrue(raul.habits["moon_tea"].dependent)
        self.assertTrue(any("Raúl se toma un té de luna" in line for line in world.event_log))

    def test_a_substance_that_makes_no_sense_is_refused(self) -> None:
        with self.assertRaisesRegex(ValueError, "needs a route"):
            substance_from_data("x", {"minutes": 10})
        with self.assertRaisesRegex(ValueError, "must last a minute"):
            substance_from_data("x", {"route": "smoked"})
        with self.assertRaisesRegex(ValueError, "impossible chance"):
            substance_from_data("x", {"route": "smoked", "minutes": 5, "dependence": 2})
        with self.assertRaisesRegex(ValueError, "map needs to numbers"):
            substance_from_data("x", {"route": "smoked", "minutes": 5, "per_minute": {"stress": "a lot"}})
        with self.assertRaisesRegex(ValueError, "needs a route"):
            validate_item_data({"id": "x", "name": "X", "article": "un", "category": "vice", "substance": {}}, "x", None)
        with self.assertRaisesRegex(ValueError, "chance from 0 to 1"):
            substance_settings_from_data({"max_chance": 3})

    def test_what_someone_is_under_and_their_habits_survive_saving(self) -> None:
        world = SimulationWorld.demo_world(seed=5)
        raul = world.residents["raul"]
        _take(world, raul, "liquor")
        raul.habits["ghost_weed"] = Habit(uses=4, dependent=True, last_taken=7, without=12.5, recovered=True)
        raul.tempted_by = "cigarette"
        loaded = self.manager.from_data(json.loads(json.dumps(self.manager.to_data(world))))
        again = loaded.residents["raul"]
        self.assertEqual((again.under, again.habits, again.tempted_by), (raul.under, raul.habits, "cigarette"))
        self.assertEqual(self.manager.to_data(loaded), self.manager.to_data(world))
        loaded.step(MINUTES_PER_DAY)
        self.assertIsNone(loaded.residents["raul"].tempted_by, "nothing was waiting on it")
        self.assertIn("ghost_weed", loaded.residents["raul"].habits, "a habit of something that is gone is kept")

    def test_in_a_save_from_before_nobody_is_under_anything_and_the_bar_is_stocked(self) -> None:
        world = SimulationWorld.demo_world(seed=5)
        world.step(MINUTES_PER_DAY)
        data = self.manager.to_data(world)
        data["version"] = 27
        del data["containers"]["bar"]
        for resident in data["residents"]:
            del resident["under"], resident["habits"], resident["tempted_by"]
        loaded = self.manager.from_data(json.loads(json.dumps(data)))
        self.assertTrue(all(not r.under and not r.habits and r.tempted_by is None for r in loaded.residents.values()))
        self.assertEqual(loaded.containers["bar"].count("liquor"), 12)
        pantry = sum(item.quantity for item in world.containers["pantry_1"].items)
        self.assertEqual(sum(item.quantity for item in loaded.containers["pantry_1"].items), pantry, "nothing else is restocked")
        loaded.step(MINUTES_PER_DAY)

    def test_ten_weeks_do_not_leave_the_whole_settlement_dependent(self) -> None:
        for seed in (3, 5, 11):
            world = SimulationWorld.demo_world(seed=seed)
            world.step(70 * MINUTES_PER_DAY)
            dependents = [r.resident_id for r in world.residents.values() if any(h.dependent for h in r.habits.values())]
            self.assertLess(len(dependents), len(world.residents) / 2, (seed, dependents))
            self.assertEqual(world.deaths, [], seed)
            self.assertNotIn("no_food", _types(world), seed)

    def test_substances_need_no_pygame(self) -> None:
        check = (
            "import sys; import simulation.world, save.save_manager; "
            "import simulation.substances.substance, simulation.substances.substance_system; "
            "from simulation.world import SimulationWorld; SimulationWorld.demo_world().step(600); "
            "sys.exit(1 if 'pygame' in sys.modules else 0)"
        )
        done = subprocess.run([sys.executable, "-c", check], cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(done.returncode, 0, done.stderr)


if __name__ == "__main__":
    unittest.main()
