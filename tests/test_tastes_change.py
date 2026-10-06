"""Tastes in people, and how what is lived through moves a taste."""

import json
import tempfile
import unittest
from pathlib import Path

from save.save_manager import SaveManager
from simulation.items.item import ItemDefinition
from simulation.registries import DATA_DIR, BuiltInRegistries
from simulation.residents.needs import Needs
from simulation.residents.resident import Resident
from simulation.tastes.knowledge import PLAYER, TasteKnowledge
from simulation.tastes.settings import (
    ADVICE,
    DISLIKED,
    EATEN,
    GIVEN,
    HATED,
    KNOWN,
    LIKED,
    LOVED,
    RUMOR,
    SUSPECTED,
    UNKNOWN,
    TasteSettings,
    taste_settings_from_data,
)
from simulation.tastes.taste import CATEGORY, ITEM, PEOPLE, TAG, Taste
from simulation.tastes.taste_system import FOUND_OUT_EVENT
from simulation.world import SimulationWorld

MINUTES_PER_DAY = 24 * 60
CAKE = {
    "id": "cake",
    "name": "tarta",
    "article": "una",
    "category": "food",
    "base_value": 20,
    "tags": ["food", "custom"],
    "preference_tags": ["sweet"],
    "effects": {"hunger": -20},
}
# Something that always turns on whoever eats it.
OYSTERS = {
    "id": "ostras",
    "name": "ostras pasadas",
    "article": "unas",
    "category": "food",
    "base_value": 12,
    "tags": ["food", "custom"],
    "preference_tags": ["seafood", "salty"],
    "effects": {"hunger": -30},
    "properties": {"sickens": 1.0},
}
BEER = {
    "id": "beer",
    "name": "cerveza",
    "article": "una",
    "category": "food",
    "tags": ["food", "custom"],
    "preference_tags": ["alcoholic"],
    "effects": {"hunger": -5},
}


def _registries(*packs: dict) -> BuiltInRegistries:
    """The game's own data and these packs, and nothing of what happens to be in the content folder."""
    with tempfile.TemporaryDirectory() as tmp:
        for pack in packs:
            folder = Path(tmp) / "items" / pack["id"]
            folder.mkdir(parents=True)
            (folder / "data.json").write_text(json.dumps(pack), encoding="utf-8")
        return BuiltInRegistries.load(DATA_DIR, custom_dir=tmp)


def _world(*packs: dict, seed: int = 7, keep: tuple[str, ...] = ("marta", "raul", "lucia", "tomas")) -> SimulationWorld:
    """A few residents with nothing on their minds, no feelings for one another and nothing in their pockets."""
    world = SimulationWorld.demo_world(seed=seed, registries=_registries(*packs))
    for extra in [rid for rid in world.residents if rid not in keep]:
        del world.residents[extra]
    world.relationships.clear()
    for resident in world.residents.values():
        resident.needs = Needs(hunger=0, tiredness=0, social=0, stress=0)
        resident.inventory.items.clear()
        resident.mood = 50.0
    return world


def _set(world: SimulationWorld, resident: Resident, kind: str, name: str, value: float) -> Taste:
    taste = world.tastes.profile(world, resident).of(kind)[name] = Taste(leaning=value)
    return taste


def _plain(world: SimulationWorld, resident: Resident, definition: ItemDefinition) -> None:
    """Leave a resident with nothing to go by but the taste tags of a thing."""
    _set(world, resident, CATEGORY, definition.category, 0)
    _set(world, resident, ITEM, definition.item_id, 0)


class LearningTests(unittest.TestCase):
    def setUp(self) -> None:
        self.world = _world(CAKE, BEER)
        self.tastes, self.settings = self.world.tastes, self.world.registries.tastes
        self.marta, self.raul, self.lucia = (self.world.residents[name] for name in ("marta", "raul", "lucia"))
        self.cake = self.world.registries.items.get("cake")
        for resident in (self.marta, self.raul, self.lucia):
            _plain(self.world, resident, self.cake)

    def test_something_good_adds_to_what_is_learned_and_something_bad_takes_from_it(self) -> None:
        taste = _set(self.world, self.raul, TAG, "spicy", -30)
        moved = self.tastes.learn(self.world, self.raul, TAG, "spicy", 1.0, 0.5)
        self.assertEqual((moved, taste.learned, taste.leaning, taste.value), (30.0, 30.0, -30, 0.0))
        moved = self.tastes.learn(self.world, self.raul, TAG, "spicy", -1.0, 1.0)
        self.assertEqual((moved, taste.learned, taste.leaning, taste.value), (-60.0, -30.0, -30, -60.0))

    def test_it_moves_by_how_much_the_thing_mattered(self) -> None:
        taste = _set(self.world, self.raul, TAG, "spicy", 0)
        trivial = abs(self.tastes.learn(self.world, self.raul, TAG, "spicy", -1.0, 0.02))
        grave = abs(self.tastes.learn(self.world, self.raul, TAG, "spicy", -1.0, 1.0))
        self.assertLess(trivial, 2.0)
        self.assertGreater(grave, 40.0)
        self.assertEqual(self.tastes.learn(self.world, self.raul, TAG, "spicy", -1.0, 0.0), 0.0)
        self.assertEqual(self.tastes.learn(self.world, self.raul, TAG, "spicy", 0.0, 1.0), 0.0)
        self.assertEqual(taste.leaning, 0)

    def test_what_is_learned_never_takes_a_taste_past_the_ends_of_the_scale(self) -> None:
        taste = _set(self.world, self.raul, TAG, "spicy", 80)
        for _ in range(5):
            self.tastes.learn(self.world, self.raul, TAG, "spicy", 1.0, 1.0)
        self.assertEqual((taste.leaning, taste.learned, taste.value), (80, 20.0, 100.0))
        for _ in range(8):
            self.tastes.learn(self.world, self.raul, TAG, "spicy", -1.0, 1.0)
        self.assertEqual((taste.leaning, taste.learned, taste.value), (80, -180.0, -100.0))

    def test_a_taste_can_be_learned_for_something_they_had_no_feeling_about(self) -> None:
        profile = self.tastes.profile(self.world, self.raul)
        profile.items.pop("cake")
        self.tastes.learn(self.world, self.raul, TAG, "never_met", -1.0, 0.5)
        self.assertEqual(profile.tags["never_met"].learned, -30.0)
        self.assertNotEqual(profile.tags["never_met"].leaning, 0.0, "the leaning they would have had is theirs all the same")

    def test_the_first_time_of_a_taste_leaves_a_small_mark_and_having_it_again_adds_less_each_time(self) -> None:
        self.assertEqual(self.tastes.react(self.world, self.lucia, self.cake, EATEN), LOVED)
        sweet = self.tastes.profile(self.world, self.lucia).tags["sweet"]
        # Her trait gave her the taste: this was not her first time of it.
        self.assertAlmostEqual(sweet.learned, self.settings.exposure)
        _set(self.world, self.raul, CATEGORY, "food", 0)
        raul = self.tastes.profile(self.world, self.raul)
        raul.tags.pop("sweet", None)
        reaction = self.tastes.react(self.world, self.raul, self.cake, EATEN)
        fresh = raul.tags["sweet"]
        if reaction in (LIKED, LOVED, DISLIKED, HATED):
            self.assertGreater(abs(fresh.learned), self.settings.exposure)
            self.assertLess(abs(fresh.learned), 5.0, "a small mark")
        else:
            self.assertEqual(fresh.learned, 0.0, "taken as any other, it leaves nothing")

        steps = []
        for _ in range(200):
            before = sweet.learned
            self.tastes.react(self.world, self.lucia, self.cake, EATEN)
            steps.append(sweet.learned - before)
        self.assertGreater(steps[0], steps[20])
        self.assertGreater(steps[20], steps[100])
        self.assertLessEqual(sweet.learned, self.settings.exposure_cap + 0.01)
        self.assertGreater(sweet.learned, self.settings.exposure_cap * 0.9)
        self.assertEqual(sweet.leaning, 80)

    def test_what_is_taken_badly_is_liked_the_less_for_having_it_again(self) -> None:
        sweet = _set(self.world, self.raul, TAG, "sweet", -70)
        for _ in range(30):
            self.assertEqual(self.tastes.react(self.world, self.raul, self.cake, EATEN), HATED)
        self.assertLess(sweet.learned, -5.0)
        self.assertGreaterEqual(sweet.learned, -self.settings.exposure_cap - 0.01)

    def test_what_makes_a_habit_goes_faster_and_farther(self) -> None:
        beer = self.world.registries.items.get("beer")
        _plain(self.world, self.raul, beer)
        liking = _set(self.world, self.raul, TAG, "alcoholic", 40)
        _set(self.world, self.raul, TAG, "sweet", 40)
        self.tastes.react(self.world, self.raul, beer, EATEN)
        self.tastes.react(self.world, self.raul, self.cake, EATEN)
        sweet = self.tastes.profile(self.world, self.raul).tags["sweet"]
        self.assertGreater(liking.learned, sweet.learned * 2)
        for _ in range(300):
            self.tastes.react(self.world, self.raul, beer, EATEN)
        self.assertGreater(liking.learned, self.settings.exposure_cap * 2)
        self.assertEqual(liking.leaning, 40)

    def test_something_of_whoever_gave_it_stays_with_the_thing(self) -> None:
        self.world.relationship("raul", "lucia").affection = 90
        self.world.relationship("marta", "lucia").affection = -90
        _set(self.world, self.raul, TAG, "sweet", 0)
        _set(self.world, self.marta, TAG, "sweet", 0)
        self.tastes.react(self.world, self.raul, self.cake, GIVEN, self.lucia)
        self.tastes.react(self.world, self.marta, self.cake, GIVEN, self.lucia)
        self.assertGreater(self.tastes.profile(self.world, self.raul).items["cake"].learned, 5.0)
        self.assertLess(self.tastes.profile(self.world, self.marta).items["cake"].learned, -5.0)
        # Eaten with nobody to thank for it, the thing itself is not learned about.
        before = self.tastes.profile(self.world, self.lucia).items["cake"].learned
        self.tastes.react(self.world, self.lucia, self.cake, EATEN)
        self.assertEqual(self.tastes.profile(self.world, self.lucia).items["cake"].learned, before)


class SicknessTests(unittest.TestCase):
    def setUp(self) -> None:
        self.world = _world(OYSTERS, CAKE)
        self.items, self.tastes = self.world.items, self.world.tastes
        self.raul = self.world.residents["raul"]
        self.oysters = self.world.registries.items.get("ostras")
        _plain(self.world, self.raul, self.oysters)
        self.seafood = _set(self.world, self.raul, TAG, "seafood", 40)
        self.salty = _set(self.world, self.raul, TAG, "salty", 40)

    def test_someone_taken_ill_by_a_meal_turns_against_it_and_remembers_why(self) -> None:
        self.assertGreater(self.tastes.liking(self.world, self.raul, self.oysters), 30)
        self.items.take_in(self.world, self.raul, self.oysters)

        self.assertLess(self.raul.health, 100.0)
        self.assertEqual([injury.kind for injury in self.raul.injuries], ["sickness"])
        self.assertIn("Raúl sale con una intoxicación de comer unas ostras pasadas", "\n".join(self.world.event_log))
        own = self.tastes.profile(self.world, self.raul).items["ostras"]
        self.assertLess(own.learned, -10.0)
        self.assertLess(self.seafood.learned, -5.0)
        self.assertGreater(self.seafood.learned, own.learned, "what it tasted of is blamed less than the thing")
        self.assertEqual((self.seafood.leaning, self.salty.leaning), (40, 40))
        self.assertLess(self.tastes.liking(self.world, self.raul, self.oysters), 30)
        memory = self.world.memories.of("raul")[-1]
        self.assertEqual(memory.text, "Enfermé después de comer unas ostras pasadas.")
        self.assertIn("sickness", memory.tags)
        self.assertLess(memory.emotional_value, 0)

    def test_the_worse_it_was_the_more_it_counts(self) -> None:
        mild, grave = _world(OYSTERS), _world(OYSTERS)
        learned = []
        for world, harm in ((mild, 5.0), (grave, 30.0)):
            raul = world.residents["raul"]
            world.tastes.sickened(world, raul, world.registries.items.get("ostras"), harm)
            learned.append(world.tastes.profile(world, raul).items["ostras"].learned)
            self.assertGreater(world.memories.of("raul")[-1].importance, 19.0)
        self.assertLess(learned[1], learned[0] * 3)
        self.assertLess(learned[0], 0.0)
        self.assertGreater(mild.memories.of("raul")[-1].importance, 0)
        self.assertGreater(grave.memories.of("raul")[-1].importance, mild.memories.of("raul")[-1].importance)

    def test_having_been_ill_of_it_they_stop_choosing_it(self) -> None:
        pantry = self.world.containers["pantry_1"]
        pantry.items.clear()
        self.world.stock(pantry, "ostras", 3, None)
        self.world.stock(pantry, "canned_beans", 3, None)
        for tag in ("tinned",):
            _set(self.world, self.raul, TAG, tag, 40)
        _set(self.world, self.raul, ITEM, "canned_beans", 0)
        self.raul.needs.hunger = 80
        self.assertEqual(self.items.best_food(self.world, self.raul, "pantry_1", "food").definition_id, "ostras")
        for _ in range(2):
            self.items.take_in(self.world, self.raul, self.oysters)
            self.raul.injuries.clear()
        self.raul.needs.hunger = 80
        self.assertEqual(self.items.best_food(self.world, self.raul, "pantry_1", "food").definition_id, "canned_beans")

    def test_what_moved_a_taste_is_remembered_and_the_memory_does_not_move_it_again(self) -> None:
        self.items.take_in(self.world, self.raul, self.oysters)
        after = {key: (taste.leaning, taste.learned) for key, taste in self.tastes.profile(self.world, self.raul).tags.items()}
        own = self.tastes.profile(self.world, self.raul).items["ostras"].learned
        memories = len(self.world.memories.of("raul"))
        for container in self.world.containers.values():
            container.items.clear()
        self.world.step(3 * MINUTES_PER_DAY)
        self.assertEqual(self.tastes.profile(self.world, self.raul).items["ostras"].learned, own)
        for tag in ("seafood", "salty"):
            self.assertEqual((self.tastes.profile(self.world, self.raul).tags[tag].leaning, self.tastes.profile(self.world, self.raul).tags[tag].learned), after[tag])
        self.assertEqual([memory.text for memory in self.world.memories.of("raul")].count("Enfermé después de comer unas ostras pasadas."), 1)
        self.assertGreaterEqual(len(self.world.memories.of("raul")), memories)

    def test_what_does_not_turn_on_anyone_draws_nothing_and_harms_nobody(self) -> None:
        cake = self.world.registries.items.get("cake")
        before = self.world.rng.get_state()
        self.items.take_in(self.world, self.raul, cake)
        self.assertEqual(self.world.rng.get_state(), before)
        self.assertEqual(self.raul.health, 100.0)
        self.assertEqual(self.raul.needs.hunger, 0)

    def test_someone_it_kills_learns_nothing_and_nothing_breaks(self) -> None:
        from simulation.health.injury import Injury

        self.raul.injuries.append(Injury("cut", 97.0))
        self.items.take_in(self.world, self.raul, self.oysters)
        self.assertNotIn("raul", self.world.residents)
        self.assertEqual(self.world.deaths[-1].cause, "comer unas ostras pasadas")
        self.world.step(60)

    def test_a_chance_of_it_that_is_no_chance_is_refused(self) -> None:
        for wrong in (1.5, -0.2):
            with self.assertRaisesRegex(ValueError, "ostras"):
                _registries({**OYSTERS, "properties": {"sickens": wrong}})


class DoubtTests(unittest.TestCase):
    def setUp(self) -> None:
        self.world = _world(CAKE)
        self.tastes, self.settings = self.world.tastes, self.world.registries.tastes
        self.raul, self.lucia = self.world.residents["raul"], self.world.residents["lucia"]
        self.cake = self.world.registries.items.get("cake")
        _plain(self.world, self.raul, self.cake)
        self.sweet = _set(self.world, self.raul, TAG, "sweet", 80)
        self.raul.x, self.raul.y = 20, 14
        self.lucia.x, self.lucia.y = 21, 14
        for _ in range(3):
            self.tastes.react(self.world, self.raul, self.cake, EATEN)

    def _found(self, observer: str = PLAYER) -> dict[str, tuple[str, str]]:
        return {key: (state, looks) for key, state, looks in self.tastes.found_out(self.world, self.raul, observer)}

    def test_a_taste_that_moves_is_still_known_as_it_was_until_it_is_seen_to_have(self) -> None:
        self.assertEqual(self._found()["tag:sweet"], (KNOWN, LOVED))
        self.tastes.learn(self.world, self.raul, TAG, "sweet", -1.0, 1.0)
        self.tastes.learn(self.world, self.raul, TAG, "sweet", -1.0, 1.0)
        self.assertLess(self.sweet.value, -20)
        self.assertEqual(self._found()["tag:sweet"], (KNOWN, LOVED), "nobody has seen anything yet")
        self.assertEqual(self._found("lucia")["tag:sweet"], (KNOWN, LOVED))

    def test_seen_to_go_the_other_way_it_is_back_to_being_suspected_the_new_way(self) -> None:
        for _ in range(2):
            self.tastes.learn(self.world, self.raul, TAG, "sweet", -1.0, 1.0)
        before = len(self.world.event_log)
        self.tastes.react(self.world, self.raul, self.cake, EATEN)
        self.assertEqual(self._found()["tag:sweet"], (SUSPECTED, DISLIKED))
        self.assertEqual(self._found()["item:cake"], (SUSPECTED, DISLIKED))
        self.assertEqual(self._found("lucia")["tag:sweet"], (SUSPECTED, DISLIKED))
        told = [line for line in self.world.event_log[before:] if FOUND_OUT_EVENT in line]
        self.assertIn("Raúl parece evitar lo dulce", "\n".join(told))
        # And from there it is found out again as anything is.
        for _ in range(5):
            self.tastes.react(self.world, self.raul, self.cake, EATEN)
        self.assertEqual(self._found()["tag:sweet"][0], KNOWN)
        self.assertIn(self._found()["tag:sweet"][1], (DISLIKED, HATED))

    def test_a_taste_that_only_grows_stronger_is_not_put_in_doubt(self) -> None:
        self.sweet.leaning = 30
        world = self.world
        knowledge = world.taste_knowledge
        knowledge.seen[PLAYER]["raul"]["tag:sweet"] = 5.0
        knowledge.seen_as[PLAYER]["raul"]["tag:sweet"] = LIKED
        self.tastes.learn(world, self.raul, TAG, "sweet", 1.0, 1.0)
        self.tastes.react(world, self.raul, self.cake, EATEN)
        self.assertEqual(self._found()["tag:sweet"], (KNOWN, LOVED))

    def test_what_is_seen_is_kept_apart_from_what_is_so(self) -> None:
        knowledge, settings = TasteKnowledge(), TasteSettings()
        self.assertEqual(knowledge.observe(PLAYER, "raul", "tag:sweet", 3.0, settings, LOVED), KNOWN)
        self.assertEqual(knowledge.looked(PLAYER, "raul", "tag:sweet"), LOVED)
        self.assertIsNone(knowledge.observe(PLAYER, "raul", "tag:sweet", 1.0, settings, LIKED), "the same way, a little less")
        self.assertEqual(knowledge.looked(PLAYER, "raul", "tag:sweet"), LIKED)
        self.assertEqual(knowledge.observe(PLAYER, "raul", "tag:sweet", 1.0, settings, HATED), SUSPECTED)
        self.assertEqual(knowledge.state(PLAYER, "raul", "tag:sweet", settings), SUSPECTED)
        self.assertEqual(knowledge.looked(PLAYER, "raul", "tag:sweet"), HATED)
        # Something that has never shown cannot be contradicted.
        self.assertIsNone(knowledge.observe(PLAYER, "raul", "tag:sour", 0.4, settings, DISLIKED))
        self.assertEqual(knowledge.state(PLAYER, "raul", "tag:sour", settings), UNKNOWN)
        self.assertIsNone(knowledge.looked(PLAYER, "lucia", "tag:sweet"))


class PeopleTests(unittest.TestCase):
    def setUp(self) -> None:
        self.world = _world()
        self.tastes, self.settings = self.world.tastes, self.world.registries.tastes
        self.marta, self.raul, self.lucia, self.tomas = (
            self.world.residents[name] for name in ("marta", "raul", "lucia", "tomas")
        )

    def _feels(self, source: Resident, target: Resident, feeling: str = "affection") -> float:
        return getattr(self.world.relationship(source.resident_id, target.resident_id), feeling)

    def test_the_game_knows_what_there_is_to_like_in_people_as_data(self) -> None:
        self.assertEqual(
            set(self.settings.people),
            {"confident", "aggressive", "generous", "lively", "authority", "gossip", "being_told"},
        )
        self.assertEqual(self.settings.people["lively"].feeling, "attraction")
        self.assertEqual(self.settings.people["gossip"].when, (RUMOR,))
        self.assertEqual(self.tastes.label(self.world, "people:aggressive"), "la gente agresiva")
        for wrong in (
            {"people": {"x": {"who": {"charm": [0, 50]}}}},
            {"people": {"x": {"who": {"courage": [0, 50]}, "feeling": "envy"}}},
            {"people": {"x": {"when": ["dinner"]}}},
            {"people": {"x": {"name": "nadie"}}},
            {"learning": {"sickness_harm": [9, 3]}},
            {"learning": {"habits": {"alcoholic": 0}}},
        ):
            with self.assertRaises(ValueError, msg=wrong):
                taste_settings_from_data(wrong)

    def test_two_people_take_the_same_person_differently_and_it_goes_one_way_only(self) -> None:
        self.assertGreaterEqual(self.tomas.personality.courage, 65, "Tomás is sure of himself")
        _set(self.world, self.marta, PEOPLE, "confident", 90)
        _set(self.world, self.raul, PEOPLE, "confident", -90)
        for resident in (self.marta, self.raul):
            # Nothing else about him to go by.
            for other in ("aggressive", "generous", "lively", "authority"):
                _set(self.world, resident, PEOPLE, other, 0)
            for _ in range(5):
                self.tastes.take_to(self.world, resident, self.tomas)
        self.assertGreater(self._feels(self.marta, self.tomas), 5.0)
        self.assertLess(self._feels(self.raul, self.tomas), -5.0)
        self.assertEqual(self._feels(self.tomas, self.marta), 0.0)
        self.assertEqual(self._feels(self.tomas, self.raul), 0.0)

    def test_a_taste_in_people_is_made_the_first_time_it_comes_into_it_and_only_then(self) -> None:
        self.assertEqual(self.tastes.profile(self.world, self.lucia).people, {})
        self.tastes.take_to(self.world, self.lucia, self.tomas)
        made = self.tastes.profile(self.world, self.lucia).people
        self.assertIn("confident", made)
        self.assertIn("authority", made, "he keeps the watch")
        self.assertNotIn("gossip", made)
        self.assertNotIn("being_told", made)
        self.assertNotIn("generous", made, "he is not open-handed enough for that to come into it")
        again = _world()
        again.tastes.take_to(again, again.residents["lucia"], again.residents["tomas"])
        self.assertEqual(again.tastes.profile(again, again.residents["lucia"]).people, made)
        self.assertNotEqual(
            self.tastes.profile(self.world, self.lucia).people["confident"].leaning,
            self.tastes.taste(self.world, self.raul, PEOPLE, "confident").leaning,
        )

    def test_each_taste_moves_the_feeling_it_is_about(self) -> None:
        _set(self.world, self.lucia, PEOPLE, "confident", 0)
        _set(self.world, self.lucia, PEOPLE, "authority", -100)
        for other in ("aggressive", "generous", "lively"):
            _set(self.world, self.lucia, PEOPLE, other, 0)
        self.tastes.take_to(self.world, self.lucia, self.tomas)
        self.assertLess(self._feels(self.lucia, self.tomas, "trust"), 0.0)
        self.assertEqual(self._feels(self.lucia, self.tomas), 0.0)
        # Without the post, there is nothing to distrust him for.
        self.tomas.job_id = None
        before = self._feels(self.lucia, self.tomas, "trust")
        self.tastes.take_to(self.world, self.lucia, self.tomas)
        self.assertEqual(self._feels(self.lucia, self.tomas, "trust"), before)

    def test_gossip_is_welcome_to_some_and_not_to_others_and_only_gossip(self) -> None:
        _set(self.world, self.marta, PEOPLE, "gossip", 90)
        _set(self.world, self.raul, PEOPLE, "gossip", -90)
        for resident in (self.marta, self.raul):
            self.tastes.take_to(self.world, resident, self.lucia, RUMOR)
        self.assertGreater(self._feels(self.marta, self.lucia), 1.0)
        self.assertLess(self._feels(self.raul, self.lucia), -1.0)
        feeling = self._feels(self.marta, self.lucia)
        for other in ("confident", "aggressive", "generous", "lively", "authority"):
            _set(self.world, self.marta, PEOPLE, other, 0)
        self.tastes.take_to(self.world, self.marta, self.lucia)
        self.assertEqual(self._feels(self.marta, self.lucia), feeling)

    def test_a_rumour_told_in_the_settlement_goes_through_it(self) -> None:
        from simulation.events.event import DomainEvent
        from simulation.knowledge.knowledge_system import share_rumor

        self.world.emit_event(
            DomainEvent("argument_started", 40, "Tomás discutió con Lucía", ["tomas", "lucia"]),
            fact_text="Tomás discutió con Lucía",
        )
        _set(self.world, self.raul, PEOPLE, "gossip", -100)
        before = self._feels(self.raul, self.tomas)
        told = None
        for _ in range(60):
            told = share_rumor(self.world, self.tomas, self.raul)
            if told is not None:
                break
        self.assertIsNotNone(told)
        self.assertLess(self._feels(self.raul, self.tomas), before)

    def test_being_told_what_to_do_counts_for_more_with_some_than_with_others(self) -> None:
        self.assertAlmostEqual(self.tastes.heed(self.world, self.lucia), 1.0 + self.tastes.profile(self.world, self.lucia).people["being_told"].value / 100.0 * self.settings.advice_weight)
        _set(self.world, self.raul, PEOPLE, "being_told", -100)
        _set(self.world, self.marta, PEOPLE, "being_told", 100)
        _set(self.world, self.lucia, PEOPLE, "being_told", 0)
        self.assertAlmostEqual(self.tastes.heed(self.world, self.raul), 1.0 - self.settings.advice_weight)
        self.assertAlmostEqual(self.tastes.heed(self.world, self.marta), 1.0 + self.settings.advice_weight)
        self.assertEqual(self.tastes.heed(self.world, self.lucia), 1.0)

    def test_advice_weighs_less_with_whoever_cannot_stand_being_given_it(self) -> None:
        def pull(value: float) -> float:
            world = _world()
            raul, marta = world.residents["raul"], world.residents["marta"]
            world.relationship("raul", "marta").resentment = 90
            world.relationship("marta", "raul").resentment = 90
            _set(world, raul, PEOPLE, "being_told", value)
            decision = None
            for _ in range(300):
                activity = world.interventions.maybe_brawl(world, raul, marta)
                if activity is not None:
                    raul.activity = activity
                    decision = world.interventions.pending_for(world, "raul")
                    break
            self.assertIsNotNone(decision)
            option = next(option for option in decision.options if option.option_id == "separate")
            alone = world.interventions.scores(world, decision, None)
            advised = world.interventions.scores(world, decision, option)
            return max(advised[outcome] - alone[outcome] for outcome in alone)

        self.assertGreater(pull(100), pull(0))
        self.assertGreater(pull(0), pull(-100))
        self.assertGreater(pull(-100), 0.0, "it still counts for something")

    def test_tastes_in_people_are_found_out_as_any_other_from_what_passes_between_them(self) -> None:
        _set(self.world, self.marta, PEOPLE, "confident", 90)
        key = "people:confident"
        knowledge = self.world.taste_knowledge
        self.assertEqual(knowledge.state(PLAYER, "marta", key, self.settings), UNKNOWN)
        seen = []
        for _ in range(8):
            self.tastes.take_to(self.world, self.marta, self.tomas)
            seen.append(knowledge.state(PLAYER, "marta", key, self.settings))
        self.assertEqual(seen[0], UNKNOWN)
        self.assertIn(SUSPECTED, seen)
        self.assertEqual(seen[-1], KNOWN)
        self.assertEqual(knowledge.state("tomas", "marta", key, self.settings), KNOWN)
        self.assertEqual(knowledge.state("raul", "marta", key, self.settings), UNKNOWN)
        found = dict((taste, (state, looks)) for taste, state, looks in self.tastes.found_out(self.world, self.marta))
        self.assertEqual(found[key], (KNOWN, LOVED))
        self.assertIn("Marta adora la gente segura de sí misma", "\n".join(self.world.event_log))

    def test_being_given_advice_shows_how_it_is_taken(self) -> None:
        _set(self.world, self.raul, PEOPLE, "being_told", -90)
        for _ in range(8):
            self.tastes.advised(self.world, self.raul)
        self.assertEqual(self.world.taste_knowledge.state(PLAYER, "raul", "people:being_told", self.settings), KNOWN)
        self.assertIn("Raúl detesta que le digan lo que tiene que hacer", "\n".join(self.world.event_log))


class SavedChangesTests(unittest.TestCase):
    def test_tastes_in_people_what_was_learned_and_how_things_looked_are_kept(self) -> None:
        manager = SaveManager()
        world = _world(CAKE)
        raul, tomas = world.residents["raul"], world.residents["tomas"]
        cake = world.registries.items.get("cake")
        for _ in range(4):
            world.tastes.react(world, raul, cake, EATEN)
            world.tastes.take_to(world, raul, tomas)
        world.tastes.learn(world, raul, TAG, "sweet", -1.0, 0.7)
        self.assertTrue(world.taste_profiles["raul"].people)
        self.assertTrue(world.taste_knowledge.seen_as[PLAYER]["raul"])

        loaded = manager.from_data(json.loads(json.dumps(manager.to_data(world))), world.registries)

        self.assertEqual(manager.to_data(loaded)["version"], manager.CURRENT_VERSION)
        self.assertEqual(loaded.taste_profiles, world.taste_profiles)
        self.assertEqual(loaded.taste_knowledge, world.taste_knowledge)
        self.assertEqual(loaded.tastes.found_out(loaded, loaded.residents["raul"]), world.tastes.found_out(world, raul))
        self.assertEqual(manager.to_data(loaded), manager.to_data(world))

    def test_a_save_from_before_tastes_in_people_loads_and_shows_what_was_known_as_it_stands(self) -> None:
        manager = SaveManager()
        world = _world(CAKE)
        raul = world.residents["raul"]
        _set(world, raul, TAG, "sweet", 80)
        _plain(world, raul, world.registries.items.get("cake"))
        for _ in range(3):
            world.tastes.react(world, raul, world.registries.items.get("cake"), EATEN)
        data = json.loads(json.dumps(manager.to_data(world)))
        data["version"] = 19
        del data["taste_seen_as"]
        for profile in data["tastes"].values():
            profile.pop("people", None)
        old = manager.from_data(data, world.registries)
        self.assertEqual(old.taste_profiles["raul"].people, {})
        self.assertEqual(old.taste_knowledge.seen_as, {})
        found = {key: (state, looks) for key, state, looks in old.tastes.found_out(old, old.residents["raul"])}
        self.assertEqual(found["tag:sweet"], (KNOWN, LOVED))
        old.step(MINUTES_PER_DAY)

    def test_damaged_records_of_how_things_looked_are_left_out(self) -> None:
        manager = SaveManager()
        world = _world()
        data = manager.to_data(world)
        data["taste_seen_as"] = {"@player": {"marta": {"tag:sweet": "adored", "tag:sour": "hated"}, "raul": 3}, "lucia": []}
        loaded = manager.from_data(json.loads(json.dumps(data)), world.registries)
        self.assertEqual(loaded.taste_knowledge.seen_as["@player"]["marta"], {"tag:sour": "hated"})


class LongRunTests(unittest.TestCase):
    def test_ten_weeks_pass_without_anyones_tastes_all_running_to_one_end(self) -> None:
        for seed in (3, 7, 19):
            world = SimulationWorld.demo_world(seed=seed, registries=_registries())
            world.step(70 * MINUTES_PER_DAY)
            cap = world.registries.tastes.exposure_cap + world.registries.tastes.learning * world.registries.tastes.first_mark
            for resident_id, profile in world.taste_profiles.items():
                values = [taste.value for taste in profile.tags.values()]
                if len(values) < 3:
                    continue
                self.assertFalse(all(value >= 60 for value in values), (seed, resident_id, values))
                self.assertFalse(all(value <= -60 for value in values), (seed, resident_id, values))
                for tag, taste in profile.tags.items():
                    self.assertLessEqual(abs(taste.learned), cap + 0.01, (seed, resident_id, tag))
                for taste in profile.people.values():
                    self.assertEqual(taste.learned, 0.0)
            self.assertTrue(any(profile.people for profile in world.taste_profiles.values()), seed)


if __name__ == "__main__":
    unittest.main()
