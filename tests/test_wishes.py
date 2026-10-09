"""Wishes (S61): small things a resident comes to want, met or let go."""

import json
import subprocess
import sys
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from save.save_manager import SaveManager
from simulation.ai.utility_ai import ScoredAction
from simulation.commands import GiveCommand
from simulation.registries import builtin_registries
from simulation.residents.activity import Activity
from simulation.residents.needs import Needs
from simulation.residents.wishes import (
    DO,
    EAT,
    HAVE,
    KINDS,
    LAPSED_EVENT,
    MET_EVENT,
    WISH_EVENT,
    WITH,
    WishSettings,
    wish_settings_from_data,
)
from simulation.tastes.taste import Taste
from simulation.world import SimulationWorld

ROOT = Path(__file__).resolve().parents[1]
MINUTES_PER_DAY = 24 * 60
HERE, BESIDE = (20, 18), (21, 18)


def _types(world: SimulationWorld) -> list[str]:
    return [line.split(" | ")[1] for line in world.event_log]


def _settings(world: SimulationWorld, **changes: object) -> None:
    world.registries = replace(world.registries, wishes=replace(world.registries.wishes, **changes))


def _calm(world: SimulationWorld) -> SimulationWorld:
    """Nobody wants for anything of the body, holds a job or does anything of their own."""
    for resident in world.residents.values():
        resident.needs = Needs(hunger=0, thirst=0, tiredness=0, social=0, stress=0)
        resident.job_id = resident.post_id = None
        resident.activity = Activity("wander", minutes_left=6000, using=True)
    return world


def _likes(world: SimulationWorld, resident, item_id: str, liking: float) -> None:
    """Have a resident make of a thing what a test needs them to."""
    definition = world.registries.items.resolve(item_id)
    profile = world.tastes.profile(world, resident)
    profile.categories[definition.category] = Taste(leaning=0)
    profile.items[item_id] = Taste(leaning=0)
    for tag in definition.preference_tags:
        profile.tags[tag] = Taste(leaning=liking)


class DataTests(unittest.TestCase):
    def test_what_is_wished_for_and_what_it_is_worth_are_data(self) -> None:
        wishes = builtin_registries().wishes
        self.assertTrue(wishes.enabled)
        self.assertEqual(set(wishes.kinds), set(KINDS), "to eat or drink, to be with, to have and to do")
        self.assertGreater(wishes.met_mood, 0)
        self.assertLess(wishes.lapsed_mood, 0)
        self.assertGreater(wishes.met_value, 0)
        self.assertLess(wishes.lapsed_value, 0)
        for kind in wishes.kinds.values():
            for told in (kind.text, kind.got, kind.lost):
                self.assertTrue("{what}" in told and "{name}" in told, told)
            for remembered in (kind.met, kind.lapsed):
                self.assertIn("{what}", remembered)
        self.assertEqual(wishes.kinds[EAT].categories, ("food", "drink"))
        self.assertTrue(wishes.kinds[HAVE].categories, "what is wished for to keep is of some categories and not of others")
        self.assertFalse(set(wishes.kinds[HAVE].categories) & set(wishes.kinds[EAT].categories))

    def test_data_that_makes_no_sense_is_refused(self) -> None:
        good = {"chance": 0.1, "kinds": {"eat": {"text": "A {name} se le antoja {what}", "categories": ["food"]}}}
        self.assertTrue(wish_settings_from_data(good).enabled)
        self.assertFalse(wish_settings_from_data({}).enabled)
        for bad in (
            {**good, "kinds": {"fly": {"text": "x"}}},
            {**good, "kinds": {"eat": {}}},
            {**good, "kinds": {"eat": {"text": "x"}}},
            {**good, "kinds": {"have": {"text": "x"}}},
            {**good, "kinds": {"eat": {"text": "x", "weight": 0, "categories": ["food"]}}},
            {**good, "chance": 2},
            {**good, "lasts_hours": 0},
            {**good, "hours": [22, 8]},
        ):
            with self.assertRaises(ValueError, msg=str(bad)):
                wish_settings_from_data(bad)

    def test_it_needs_no_pygame(self) -> None:
        code = (
            "import sys; from simulation.world import SimulationWorld; world = SimulationWorld.demo_world(); "
            "world.wishes.make(world, world.residents['marta'], 'do', 'stroll'); world.step(60 * 24 * 2); "
            "print('pygame' in sys.modules)"
        )
        result = subprocess.run([sys.executable, "-c", code], cwd=ROOT, capture_output=True, text=True, check=True)
        self.assertEqual(result.stdout.strip().splitlines()[-1], "False")


class ComingToWantTests(unittest.TestCase):
    def setUp(self) -> None:
        self.world = _calm(SimulationWorld.demo_world())
        self.marta = self.world.residents["marta"]

    def test_what_they_could_want_is_out_of_what_they_know_and_like(self) -> None:
        world, marta = self.world, self.marta
        world.relationships.clear()
        for definition in world.talk.known_items(world, marta):
            _likes(world, marta, definition.item_id, -80)
        options = world.wishes.options(world, marta)
        self.assertEqual({kind for kind, _what in options}, {DO}, "with nothing liked and nobody dear, something to do")
        self.assertIn((DO, "stroll"), options)
        self.assertIn((DO, "wash"), options, "and what there is to do with the things that stand there")
        self.assertNotIn((DO, "train"), options)
        with patch.object(type(world.housing), "may_use", lambda _housing, _world, _who, _placed, use: use.action != "wash"):
            self.assertNotIn((DO, "wash"), world.wishes.options(world, marta), "not with what is not theirs to use")
            self.assertIn((DO, "stroll"), world.wishes.options(world, marta))
        _likes(world, marta, "stew", 80)
        self.assertIn((EAT, "stew"), world.wishes.options(world, marta))
        _likes(world, marta, "old_radio", 80)
        self.assertIn((HAVE, "old_radio"), world.wishes.options(world, marta))
        world.stock(marta.inventory, "old_radio", 1, "marta")
        self.assertNotIn((HAVE, "old_radio"), world.wishes.options(world, marta), "she has one")
        # Scrap, medicine and water are for using up: nobody wishes they had some to keep.
        for item_id in ("scrap", "medicine", "water"):
            _likes(world, marta, item_id, 80)
        self.assertIn("scrap", [definition.item_id for definition in world.talk.known_items(world, marta)])
        wished = {what for kind, what in world.wishes.options(world, marta) if kind in (EAT, HAVE)}
        self.assertFalse(wished & {"scrap", "medicine", "water"})
        world.relationship("marta", "vera").affection = 60
        world.relationship("marta", "raul").affection = 5
        people = [what for kind, what in world.wishes.options(world, marta) if kind == WITH]
        self.assertEqual(people, ["vera"])

    def test_nobody_wishes_for_what_a_law_they_keep_forbids_them_or_what_they_have_sworn_off(self) -> None:
        world, marta = self.world, self.marta
        for item_id in ("liquor", "old_radio"):
            _likes(world, marta, item_id, 80)
        things = lambda: {what for kind, what in world.wishes.options(world, marta) if kind in (EAT, HAVE)}  # noqa: E731
        self.assertTrue({"liquor", "old_radio"} <= things())
        with patch.object(type(world.politics.laws), "may_have", lambda _laws, _world, _who, definition: definition.item_id != "liquor"):
            self.assertNotIn("liquor", things())
            self.assertIn("old_radio", things())
        with patch.object(type(world.substances), "wish", lambda _system, _world, _who, definition: None if definition.item_id == "liquor" else 0.0):
            self.assertNotIn("liquor", things())

    def test_now_and_then_by_day_somebody_comes_to_want_something(self) -> None:
        world = self.world
        _settings(world, chance=1.0)
        world.clock.hour, world.clock.minute = 3, 0
        world.wishes.tick(world)
        self.assertEqual(world.wishes_of, {}, "not in the small hours")
        world.clock.hour = 10
        world.wishes.tick(world)
        self.assertEqual(set(world.wishes_of), set(world.residents), "one each")
        wish = world.wishes_of["marta"]
        self.assertIn(wish.kind, KINDS)
        self.assertEqual(wish.until - wish.since, world.registries.wishes.lasts_hours * 60)
        self.assertEqual(_types(world).count(WISH_EVENT), len(world.residents))
        self.assertTrue(world.wishes.said(world, wish).count("Marta") >= 1)
        before = dict(world.wishes_of)
        world.clock.hour = 11
        world.wishes.tick(world)
        self.assertEqual(world.wishes_of, before, "nobody wants two things at once")

    def test_wishing_throws_none_of_the_settlements_dice(self) -> None:
        world = self.world
        _settings(world, chance=1.0)
        world.clock.hour, world.clock.minute = 10, 0
        before = (world.rng.get_state(), world.event_rng.get_state())
        world.wishes.tick(world)
        self.assertTrue(world.wishes_of)
        self.assertEqual((world.rng.get_state(), world.event_rng.get_state()), before)

    def test_nobody_wishes_where_there_is_no_chance_of_it(self) -> None:
        world = self.world
        _settings(world, chance=0.0)
        world.clock.hour, world.clock.minute = 10, 0
        world.wishes.tick(world)
        self.assertEqual(world.wishes_of, {})


class MetTests(unittest.TestCase):
    def setUp(self) -> None:
        self.world = _calm(SimulationWorld.demo_world())
        _settings(self.world, chance=0.0001)
        self.marta = self.world.residents["marta"]
        self.marta.mood = 50.0

    def _ended(self, event: str) -> None:
        self.world.wishes.tick(self.world)
        self.assertNotIn("marta", self.world.wishes_of)
        self.assertIn(event, _types(self.world))

    def test_a_thing_wished_for_is_had_by_being_given_it(self) -> None:
        world, marta = self.world, self.marta
        wish = world.wishes.make(world, marta, HAVE, "old_radio")
        self.assertEqual(world.wishes.said(world, wish), "Marta querría tener una radio vieja")
        world.wishes.tick(world)
        self.assertIn("marta", world.wishes_of)
        self.assertTrue(world.apply_command(GiveCommand("marta", "old_radio")).ok)
        self.assertNotIn("marta", world.wishes_of, "handed the very thing, it is met there and then")
        self.assertIn(MET_EVENT, _types(world))
        self.assertIn("Marta ya tiene una radio vieja, como quería", world.event_log[-1])
        memory = world.memories.recent("marta", 1)[-1]
        self.assertIn("radio vieja", memory.text)
        self.assertGreater(memory.emotional_value, 0)

    def test_what_a_wish_met_does_to_their_spirits(self) -> None:
        world, marta = self.world, self.marta
        world.wishes.make(world, marta, HAVE, "old_radio")
        world.stock(marta.inventory, "old_radio", 1, "marta")
        self._ended(MET_EVENT)
        self.assertEqual(marta.mood, 50.0 + world.registries.wishes.met_mood, "come by any other way, it is met as well")

    def test_handed_something_else_they_go_on_wanting(self) -> None:
        world, marta = self.world, self.marta
        world.wishes.make(world, marta, HAVE, "old_radio")
        self.assertTrue(world.apply_command(GiveCommand("marta", "hoe")).ok)
        world.wishes.tick(world)
        self.assertEqual(world.wishes_of["marta"].what, "old_radio")

    def test_something_to_eat_is_had_by_being_handed_it_too(self) -> None:
        world, marta = self.world, self.marta
        world.wishes.make(world, marta, EAT, "stew")
        self.assertTrue(world.apply_command(GiveCommand("marta", "stew")).ok)
        self.assertNotIn("marta", world.wishes_of)
        self.assertIn("Marta se da el gusto de un guiso caliente", world.event_log[-1])

    def test_whoever_wants_something_to_eat_takes_that_where_there_is_some(self) -> None:
        world, marta = self.world, self.marta
        marta.needs.hunger = 70.0
        pantry = world.containers["pantry_1"]
        for item_id in ("stew", "canned_beans", "vegetables"):
            world.stock(pantry, item_id, 2, None)
        usual = world.items.best_food(world, marta, "pantry_1", "food").definition_id
        other = next(item_id for item_id in ("stew", "canned_beans", "vegetables") if item_id != usual)
        world.wishes.make(world, marta, EAT, other)
        self.assertEqual(world.items.best_food(world, marta, "pantry_1", "food").definition_id, other)
        world.wishes.make(world, marta, EAT, "liquor")
        self.assertEqual(
            world.items.best_food(world, marta, "pantry_1", "food").definition_id, usual, "where there is none, what she would have had"
        )

    def test_let_go_unmet_it_is_remembered_the_other_way(self) -> None:
        world, marta = self.world, self.marta
        wish = world.wishes.make(world, marta, HAVE, "old_radio")
        world.clock.advance_minutes(wish.until - wish.since - 1)
        world.wishes.tick(world)
        self.assertIn("marta", world.wishes_of)
        world.clock.advance_minutes(1)
        self._ended(LAPSED_EVENT)
        self.assertIn("Marta se queda sin una radio vieja", world.event_log[-1])
        self.assertEqual(marta.mood, 50.0 + world.registries.wishes.lapsed_mood)
        memory = world.memories.recent("marta", 1)[-1]
        self.assertLess(memory.emotional_value, 0)
        self.assertIn("radio vieja", memory.text)

    def test_a_while_with_somebody_is_had_by_talking_to_them_and_not_by_quarrelling(self) -> None:
        world, marta = self.world, self.marta
        vera = world.residents["vera"]
        world.wishes.make(world, marta, WITH, "vera")
        marta.activity = Activity("argument", partner_id="vera", using=True, minutes_left=10)
        world.wishes.tick(world)
        self.assertIn("marta", world.wishes_of, "a quarrel is not what she wanted")
        marta.activity = Activity("chat", partner_id="raul", using=True, minutes_left=10)
        world.wishes.tick(world)
        self.assertIn("marta", world.wishes_of, "nor is somebody else")
        marta.activity = Activity("chat", partner_id="vera", using=True, minutes_left=10)
        self._ended(MET_EVENT)
        self.assertEqual(world.memories.recent("marta", 1)[-1].people, ["vera"])
        del vera

    def test_something_to_do_is_had_by_doing_it(self) -> None:
        world, marta = self.world, self.marta
        wish = world.wishes.make(world, marta, DO, "wash")
        self.assertEqual(world.wishes.said(world, wish), "A Marta le apetece lavarse")
        marta.activity = Activity("wash", "water_tank", minutes_left=5)
        world.wishes.tick(world)
        self.assertIn("marta", world.wishes_of, "on her way is not at it")
        marta.activity.using = True
        self._ended(MET_EVENT)

    def test_something_to_eat_is_had_by_eating_that_and_nothing_else(self) -> None:
        world, marta = self.world, self.marta
        wish = world.wishes.make(world, marta, EAT, "stew")
        self.assertEqual(world.wishes.said(world, wish), "Marta tiene antojo de un guiso caliente")
        marta.activity = Activity("eat", "pantry_1", minutes_left=10, using=True, item_id="canned_beans")
        world.wishes.tick(world)
        self.assertIn("marta", world.wishes_of)
        marta.activity = Activity("eat", "cooking_pot", minutes_left=10, using=True, item_id="stew")
        self._ended(MET_EVENT)

    def test_whoever_they_wanted_to_be_with_going_lets_it_go(self) -> None:
        world, marta = self.world, self.marta
        world.wishes.make(world, marta, WITH, "vera")
        del world.residents["vera"]
        self._ended(LAPSED_EVENT)

    def test_they_are_the_readier_to_do_what_would_meet_it(self) -> None:
        world, marta = self.world, self.marta
        pull = world.registries.wishes.pull
        talk = ScoredAction("talk", 1.0, partner_id="vera")
        wash = ScoredAction("wash", 1.0, "water_tank")
        pot = ScoredAction("eat", 1.0, "cooking_pot")
        self.assertEqual(world.wishes.pull(world, marta, talk), 0.0, "wanting nothing, nothing pulls")
        world.wishes.make(world, marta, WITH, "vera")
        self.assertEqual(world.wishes.pull(world, marta, talk), pull)
        self.assertEqual(world.wishes.pull(world, marta, ScoredAction("talk", 1.0, partner_id="raul")), 0.0)
        world.wishes.make(world, marta, DO, "wash")
        self.assertEqual(world.wishes.pull(world, marta, wash), pull)
        self.assertEqual(world.wishes.pull(world, marta, talk), 0.0)
        world.wishes.make(world, marta, EAT, "stew")
        for container in world.containers.values():
            container.items[:] = [item for item in container.items if item.definition_id != "stew"]
        self.assertEqual(world.wishes.pull(world, marta, pot), 0.0, "there is none there")
        world.stock(world.containers["cooking_pot"], "stew", 1, None)
        self.assertEqual(world.wishes.pull(world, marta, pot), pull, "to eat where there is some")
        self.assertEqual(world.wishes.pull(world, marta, ScoredAction("work", 1.0, "cooking_pot")), 0.0, "and not there for anything else")
        self.assertEqual(world.wishes.pull(world, marta, ScoredAction("eat", 1.0, "pantry_1")), 0.0)
        # And it tells in what she sets about, left to herself.
        world.wishes.make(world, marta, DO, "wash")
        marta.needs.stress = 30.0
        scored = {each.name: each.score for each in world.activities.routine.candidates(world, marta) if each.target_id == "water_tank"}
        self.assertIn("wash", scored)

    def test_a_wish_waits_for_the_law_and_for_the_weather(self) -> None:
        """What they want can wait: it does not keep them out after the hour a law they keep
        has them indoors, nor out in a storm."""
        world, marta = self.world, self.marta
        marta.activity = None
        world.wishes.make(world, marta, WITH, "vera")
        routine = world.activities.routine

        def talk() -> float:
            return next(each.score for each in routine.candidates(world, marta) if each.partner_id == "vera")

        seeds = world.rng.get_state()
        plain = talk()
        world.rng.set_state(seeds)
        with patch.object(type(world.happenings), "is_stormy", lambda _system, _world: True):
            stormy = talk()
        self.assertAlmostEqual(plain - stormy, world.registries.wishes.pull)
        world.politics.laws.enact(world, "curfew", 2)
        laws = type(world.politics.laws)
        with patch.object(laws, "indoors", lambda *_: True), patch.object(laws, "under_same_roof", lambda *_: True):
            world.rng.set_state(seeds)
            kept_in = talk()
        self.assertAlmostEqual(plain - kept_in, world.registries.wishes.pull)

    def test_left_to_themselves_some_wishes_are_met_and_some_are_not(self) -> None:
        world = SimulationWorld.demo_world(seed=4)
        _settings(world, chance=0.2)
        world.step(5 * MINUTES_PER_DAY)
        types = _types(world)
        self.assertGreater(types.count(WISH_EVENT), 10)
        self.assertGreater(types.count(MET_EVENT), 0, "they see to some themselves")
        self.assertGreater(types.count(LAPSED_EVENT), 0)
        self.assertEqual(world.deaths, [])


class SaveTests(unittest.TestCase):
    def test_what_is_wanted_is_saved_and_goes_on_the_same(self) -> None:
        manager = SaveManager()
        world = SimulationWorld.demo_world(seed=5)
        _settings(world, chance=0.3)
        world.step(MINUTES_PER_DAY)
        self.assertTrue(world.wishes_of)
        data = manager.to_data(world)
        self.assertGreaterEqual(data["version"], 51)
        loaded = manager.from_data(json.loads(json.dumps(data)), world.registries)
        self.assertEqual(loaded.wishes_of, world.wishes_of)
        for each in (world, loaded):
            each.step(MINUTES_PER_DAY)
        self.assertEqual(manager.to_data(loaded), manager.to_data(world))

    def test_in_a_save_from_before_nobody_wants_anything(self) -> None:
        manager = SaveManager()
        world = SimulationWorld.demo_world()
        world.wishes.make(world, world.residents["marta"], DO, "stroll")
        data = manager.to_data(world)
        old = json.loads(json.dumps(data))
        del old["wishes"]
        old["version"] = 50
        self.assertEqual(manager.from_data(old).wishes_of, {})
        broken = json.loads(json.dumps(data))
        broken["wishes"] += [
            {"resident_id": "nobody", "kind": "do", "what": "stroll", "since": 0, "until": 9},
            {"resident_id": "raul", "kind": "fly", "what": "x", "since": 0, "until": 9},
            {"resident_id": "ines", "kind": "do", "what": "stroll", "since": "now", "until": 9},
            7,
        ]
        self.assertEqual(set(manager.from_data(broken).wishes_of), {"marta"})
        self.assertIsInstance(WishSettings().kinds, dict)


if __name__ == "__main__":
    unittest.main()
