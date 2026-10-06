"""What residents like and loathe, how they take things for it, and how it is found out."""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from save.save_manager import SaveManager
from simulation.items.custom_content import validate_item_data
from simulation.items.item import ItemDefinition, taste_tags
from simulation.registries import DATA_DIR, BuiltInRegistries
from simulation.residents.needs import Needs
from simulation.residents.resident import Resident
from simulation.rng import SimulationRNG
from simulation.tastes.knowledge import PLAYER, TasteKnowledge
from simulation.tastes.leaning import leaning_for
from simulation.tastes.reaction import Moment, felt, liking, reaction_to
from simulation.tastes.settings import (
    DISLIKED,
    EATEN,
    GIVEN,
    HATED,
    KNOWN,
    LIKED,
    LOVED,
    NEUTRAL,
    REACTIONS,
    SUSPECTED,
    UNKNOWN,
    USED,
    TasteSettings,
    taste_settings_from_data,
)
from simulation.tastes.taste import CATEGORY, ITEM, TAG, Taste, TasteProfile, key_of
from simulation.tastes.taste_system import FOUND_OUT_EVENT, MENTION_EVENT, REACTION_EVENT, REFUSAL_EVENT
from simulation.world import SimulationWorld

ROOT = Path(__file__).resolve().parent.parent
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
# Something a pack brings with tastes the game has never had.
ALGAE = {
    "id": "sopa_algas",
    "name": "sopa de algas fosforescentes",
    "article": "una",
    "category": "food",
    "base_value": 14,
    "tags": ["food", "custom"],
    "preference_tags": ["salty", "seafood", "radioactive", "slimy"],
    "effects": {"hunger": -30},
}


def _registries(*packs: dict) -> BuiltInRegistries:
    """The game's own data and these packs, and nothing of what happens to be in the content folder."""
    with tempfile.TemporaryDirectory() as tmp:
        for pack in packs:
            folder = Path(tmp) / "items" / pack["id"]
            folder.mkdir(parents=True)
            (folder / "data.json").write_text(json.dumps(pack), encoding="utf-8")
        return BuiltInRegistries.load(DATA_DIR, custom_dir=tmp)


def _world(*packs: dict, seed: int = 7) -> SimulationWorld:
    """Marta, Raúl and Lucía with nothing on their minds, no feelings for one another and nothing in their pockets."""
    world = SimulationWorld.demo_world(seed=seed, registries=_registries(*packs))
    for extra in [rid for rid in world.residents if rid not in ("marta", "raul", "lucia")]:
        del world.residents[extra]
    world.relationships.clear()
    for resident in world.residents.values():
        resident.needs = Needs(hunger=0, tiredness=0, social=0, stress=0)
        resident.job_id = resident.post_id = None
        resident.inventory.items.clear()
        resident.mood = 50.0
    return world


def _types(world: SimulationWorld) -> list[str]:
    return [line.split(" | ")[1] for line in world.event_log]


def _set(world: SimulationWorld, resident: Resident, kind: str, name: str, value: float) -> None:
    world.tastes.profile(world, resident).of(kind)[name] = Taste(leaning=value)


class TasteTagTests(unittest.TestCase):
    def test_taste_tags_are_put_in_one_form_and_counted_once(self) -> None:
        self.assertEqual(taste_tags(["Sweet", " very spicy ", "old-world", "sweet"]), ("sweet", "very_spicy", "old_world"))
        self.assertEqual(taste_tags([]), ())
        for wrong in ([""], ["  "], [3], "sweet", ["a__b"], ["_a"], ["what?"], None):
            with self.assertRaises(ValueError, msg=wrong):
                taste_tags(wrong)

    def test_a_pack_with_tags_that_cannot_be_tastes_is_turned_down_like_any_other_bad_data(self) -> None:
        validate_item_data(CAKE, "cake", None)
        validate_item_data({**CAKE, "preference_tags": ["Very Sweet"]}, "cake", None)
        for wrong in ([""], [1], "sweet"):
            with self.assertRaisesRegex(ValueError, "preference_tags|taste tag"):
                validate_item_data({**CAKE, "preference_tags": wrong}, "cake", None)

    def test_the_games_own_items_and_a_packs_are_read_the_same_way(self) -> None:
        registries = _registries({**CAKE, "preference_tags": ["Sweet", "sweet", "home made"]})
        self.assertEqual(registries.items.get("cake").preference_tags, ("sweet", "home_made"))
        self.assertEqual(registries.items.get("stew").preference_tags, ("hot", "homemade"))
        self.assertEqual(registries.items.get("water").preference_tags, ())
        # What a pack lays over one of the game's own keeps the tastes it does not speak of.
        patched = _registries({"id": "stew", "name": "potaje"})
        self.assertEqual(patched.items.get("stew").preference_tags, ("hot", "homemade"))

    def test_a_trait_gives_its_taste_as_data_and_bad_data_is_refused(self) -> None:
        registries = _registries()
        self.assertEqual(registries.traits.get("sweet_tooth")["tastes"], {"sweet": 80})
        for wrong in ({"Sweet": 80}, {"sweet": 300}, {"sweet": "a lot"}, ["sweet"]):
            registries.traits.get("sweet_tooth")["tastes"] = wrong
            with self.assertRaisesRegex(ValueError, "sweet_tooth"):
                registries.validate()


class LeaningTests(unittest.TestCase):
    def setUp(self) -> None:
        self.settings = TasteSettings()

    def test_the_same_settlement_resident_and_tag_always_give_the_same_leaning(self) -> None:
        first = leaning_for(7, "marta", TAG, "slimy", self.settings)
        self.assertEqual(first, leaning_for(7, "marta", TAG, "slimy", self.settings))
        self.assertTrue(-100.0 <= first <= 100.0)
        self.assertNotEqual(first, leaning_for(8, "marta", TAG, "slimy", self.settings), "another settlement, another Marta")
        self.assertNotEqual(first, leaning_for(7, "marta", TAG, "sweet", self.settings))

    def test_two_residents_may_well_lean_opposite_ways(self) -> None:
        names = ("marta", "raul", "lucia", "tomas", "ines", "vera", "paco", "nuria", "sergio")
        leanings = [leaning_for(7, name, TAG, "slimy", self.settings) for name in names]
        self.assertEqual(len(set(leanings)), len(names))
        self.assertLess(min(leanings), -20.0)
        self.assertGreater(max(leanings), 20.0)

    def test_most_leanings_are_mild_a_category_milder_and_one_item_is_seldom_anything_at_all(self) -> None:
        tags = [leaning_for(7, f"r{n}", TAG, "slimy", self.settings) for n in range(400)]
        mild = sum(1 for leaning in tags if abs(leaning) < 60.0)
        self.assertGreater(mild, 280)
        self.assertLess(mild, 400)
        self.assertLess(abs(sum(tags) / len(tags)), 10.0, "as many one way as the other")
        categories = [leaning_for(7, f"r{n}", CATEGORY, "food", self.settings) for n in range(400)]
        self.assertLessEqual(max(abs(leaning) for leaning in categories), 50.0)
        items = [leaning_for(7, f"r{n}", ITEM, "stew", self.settings) for n in range(400)]
        quirks = [leaning for leaning in items if leaning is not None]
        self.assertTrue(20 < len(quirks) < 110)
        self.assertTrue(all(60.0 <= abs(quirk) <= 100.0 for quirk in quirks))
        self.assertTrue(any(quirk > 0 for quirk in quirks) and any(quirk < 0 for quirk in quirks))

    def test_a_generator_for_one_question_moves_no_other_on(self) -> None:
        world = _world(ALGAE)
        before = world.rng.get_state()
        marta = world.residents["marta"]
        world.tastes.meet(world, marta, world.registries.items.get("sopa_algas"))
        self.assertEqual(world.rng.get_state(), before)
        self.assertEqual(SimulationRNG.keyed(7, "a", 1).random(), SimulationRNG.keyed(7, "a", 1).random())
        self.assertNotEqual(SimulationRNG.keyed(7, "a", 1).random(), SimulationRNG.keyed(7, "a", 2).random())
        self.assertNotEqual(SimulationRNG.keyed(7, "ab", "c").random(), SimulationRNG.keyed(7, "a", "bc").random())


class LikingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.settings = taste_settings_from_data(json.loads((DATA_DIR / "tastes.json").read_text(encoding="utf-8")))
        self.cake = ItemDefinition("cake", "tarta", "una", "food", preference_tags=("sweet",))
        self.jelly = ItemDefinition("gelatina_mutante", "gelatina mutante", "una", "food", preference_tags=("sweet", "slimy"))

    def test_a_taste_for_a_tag_is_a_liking_for_what_carries_it_and_a_distaste_a_loathing(self) -> None:
        fond, averse, blank = TasteProfile(), TasteProfile(), TasteProfile()
        fond.tags["sweet"] = Taste(leaning=80)
        averse.tags["sweet"] = Taste(leaning=-70)
        self.assertEqual(liking(fond, self.cake, self.settings), 80)
        self.assertEqual(liking(averse, self.cake, self.settings), -70)
        self.assertEqual(liking(blank, self.cake, self.settings), 0)
        self.assertEqual(reaction_to(liking(fond, self.cake, self.settings), self.settings), LOVED)
        self.assertEqual(reaction_to(liking(averse, self.cake, self.settings), self.settings), HATED)
        self.assertEqual(reaction_to(liking(blank, self.cake, self.settings), self.settings), NEUTRAL)

    def test_tags_are_weighed_together_and_a_category_counts_for_less(self) -> None:
        profile = TasteProfile()
        profile.tags["sweet"] = Taste(leaning=70)
        profile.tags["slimy"] = Taste(leaning=-35)
        self.assertAlmostEqual(liking(profile, self.jelly, self.settings), 17.5)
        profile.categories["food"] = Taste(leaning=40)
        self.assertAlmostEqual(liking(profile, self.jelly, self.settings), 17.5 + 40 * self.settings.category_weight)

    def test_one_item_can_be_loved_over_tags_that_are_loathed_without_silencing_them(self) -> None:
        profile = TasteProfile()
        profile.tags["slimy"] = Taste(leaning=-80)
        profile.tags["sweet"] = Taste(leaning=-80)
        self.assertEqual(reaction_to(liking(profile, self.jelly, self.settings), self.settings), HATED)
        profile.items["gelatina_mutante"] = Taste(leaning=100)
        loved = liking(profile, self.jelly, self.settings)
        self.assertGreater(loved, 20.0)
        self.assertLess(loved, 100.0, "the tags still have their say")
        self.assertEqual(reaction_to(loved, self.settings), LIKED)
        profile.tags["slimy"] = profile.tags["sweet"] = Taste(leaning=0)
        self.assertEqual(reaction_to(liking(profile, self.jelly, self.settings), self.settings), LOVED)

    def test_what_is_learned_is_added_to_the_leaning_and_kept_apart_from_it(self) -> None:
        taste = Taste(leaning=-35, learned=20)
        self.assertEqual((taste.leaning, taste.learned, taste.value), (-35, 20, -15))
        self.assertEqual(Taste(leaning=90, learned=50).value, 100)
        self.assertEqual(Taste(leaning=-90, learned=-50).value, -100)

    def test_the_moment_colours_a_liking(self) -> None:
        plain = felt(10.0, Moment(), self.settings)
        self.assertEqual(plain, 10.0)
        self.assertGreater(felt(10.0, Moment(need=1.0), self.settings), plain, "hunger is the best sauce")
        self.assertGreater(felt(10.0, Moment(mood=90.0), self.settings), plain)
        self.assertLess(felt(10.0, Moment(mood=10.0), self.settings), plain)
        self.assertGreater(felt(10.0, Moment(fondness=80.0), self.settings), plain)
        self.assertLess(felt(10.0, Moment(fondness=-80.0), self.settings), plain)
        self.assertEqual(felt(95.0, Moment(need=1.0, mood=100.0, fondness=100.0), self.settings), 100.0)

    def test_the_five_reactions_are_in_order_and_the_rules_are_checked(self) -> None:
        seen = [reaction_to(score, self.settings) for score in (-100, -60, -59, -20, -19, 0, 19, 20, 59, 60, 100)]
        self.assertEqual(seen, [HATED, HATED, DISLIKED, DISLIKED, NEUTRAL, NEUTRAL, NEUTRAL, LIKED, LIKED, LOVED, LOVED])
        self.assertEqual(set(self.settings.effects), set(REACTIONS))
        for wrong in (
            {"thresholds": {"liked": -5}},
            {"thresholds": {"adored": 90}},
            {"effects": {"adored": {}}},
            {"weights": {"item": 1.5}},
            {"found_out": {"suspected": 4, "known": 3}},
        ):
            with self.assertRaises(ValueError, msg=wrong):
                taste_settings_from_data(wrong)


class MeetingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.world = _world(ALGAE, CAKE)
        self.tastes = self.world.tastes
        self.marta, self.raul, self.lucia = (self.world.residents[name] for name in ("marta", "raul", "lucia"))
        self.algae = self.world.registries.items.get("sopa_algas")

    def test_a_profile_starts_with_what_traits_give_and_nothing_else(self) -> None:
        self.assertEqual(self.tastes.profile(self.world, self.raul).keys(), [])
        self.assertEqual(self.tastes.profile(self.world, self.lucia).keys(), ["tag:sweet"])
        self.assertEqual(self.tastes.profile(self.world, self.lucia).tags["sweet"].value, 80)
        self.assertEqual(self.tastes.profile(self.world, self.marta).tags["music"].value, 70)
        self.assertIs(self.tastes.profile(self.world, self.marta), self.world.taste_profiles["marta"])
        self.assertFalse(hasattr(self.marta, "tastes"), "kept apart from the resident")

    def test_a_taste_is_made_on_meeting_a_new_tag_and_kept(self) -> None:
        self.assertIsNone(self.tastes.profile(self.world, self.marta).find(TAG, "slimy"))
        self.assertEqual(self.tastes.liking(self.world, self.marta, self.algae), 0, "asking how they like it makes nothing")
        self.assertIsNone(self.tastes.profile(self.world, self.marta).find(TAG, "slimy"))

        self.tastes.react(self.world, self.marta, self.algae, EATEN)

        profile = self.tastes.profile(self.world, self.marta)
        for tag in ("salty", "seafood", "radioactive", "slimy"):
            taste = profile.find(TAG, tag)
            self.assertIsNotNone(taste, tag)
            self.assertEqual(taste.leaning, leaning_for(7, "marta", TAG, tag, self.world.registries.tastes))
            self.assertLess(abs(taste.learned), 5.0, "the first time leaves a small mark at the most")
        self.assertIsNotNone(profile.find(CATEGORY, "food"))
        slimy = profile.tags["slimy"]
        self.tastes.react(self.world, self.marta, self.algae, EATEN)
        self.assertIs(profile.tags["slimy"], slimy)

    def test_a_tag_the_game_works_by_makes_no_taste(self) -> None:
        self.assertEqual(self.algae.tags, ("food", "custom"))
        self.tastes.react(self.world, self.marta, self.algae, EATEN)
        profile = self.tastes.profile(self.world, self.marta)
        self.assertNotIn("custom", profile.tags)
        self.assertNotIn("food", profile.tags)
        plain = ItemDefinition("ration", "ración", "una", "food", tags=("food", "quest_item", "sweet"))
        self.tastes.react(self.world, self.lucia, plain, EATEN)
        self.assertEqual(sorted(self.tastes.profile(self.world, self.lucia).tags), ["sweet"], "only what her trait gave her")
        self.assertEqual(self.tastes.liking(self.world, self.lucia, plain), self.tastes.profile(self.world, self.lucia).categories["food"].value * self.world.registries.tastes.category_weight)

    def test_a_packs_new_taste_tags_work_with_no_code_of_their_own(self) -> None:
        reactions = {}
        for seed in range(1, 13):
            world = _world(ALGAE, seed=seed)
            for resident in world.residents.values():
                reactions[(seed, resident.resident_id)] = world.tastes.react(
                    world, resident, world.registries.items.get("sopa_algas"), EATEN
                )
                self.assertIn("radioactive", world.tastes.profile(world, resident).tags)
        self.assertGreater(len(set(reactions.values())), 2, "people take it differently")
        again = _world(ALGAE, seed=5)
        marta = again.residents["marta"]
        self.assertEqual(again.tastes.react(again, marta, again.registries.items.get("sopa_algas"), EATEN), reactions[(5, "marta")])

    def test_what_is_no_longer_defined_makes_no_taste(self) -> None:
        gone = self.world.registries.items.resolve("something_removed")
        self.assertEqual(self.tastes.react(self.world, self.marta, gone, EATEN), NEUTRAL)
        self.assertEqual(self.tastes.profile(self.world, self.marta).keys(), ["tag:music"])


class ReactionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.world = _world(CAKE)
        self.tastes = self.world.tastes
        self.marta, self.raul, self.lucia = (self.world.residents[name] for name in ("marta", "raul", "lucia"))
        self.cake = self.world.registries.items.get("cake")
        for resident in (self.marta, self.raul, self.lucia):
            # Nothing but the sweetness of it to go by.
            _set(self.world, resident, CATEGORY, "food", 0)
            _set(self.world, resident, ITEM, "cake", 0)
        _set(self.world, self.raul, TAG, "sweet", -80)
        _set(self.world, self.marta, TAG, "sweet", 0)

    def test_the_same_meal_is_taken_differently_and_it_shows_in_the_mood(self) -> None:
        self.assertEqual(self.tastes.react(self.world, self.lucia, self.cake, EATEN), LOVED)
        self.assertEqual(self.tastes.react(self.world, self.raul, self.cake, EATEN), HATED)
        self.assertEqual(self.tastes.react(self.world, self.marta, self.cake, EATEN), NEUTRAL)
        self.assertGreater(self.lucia.mood, 50.0)
        self.assertLess(self.raul.mood, 50.0)
        self.assertEqual(self.marta.mood, 50.0)
        lines = [line for line in self.world.event_log if REACTION_EVENT in line]
        self.assertEqual(len(lines), 2, "nothing is said of taking a thing as any other")
        self.assertIn("Lucía come una tarta con verdadero deleite", lines[0])
        self.assertIn("Raúl come una tarta con asco", lines[1])
        event = [event for event in self.world.events.pending if event.event_type == REACTION_EVENT][0]
        self.assertEqual(event.data, {"resident_id": "lucia", "item_id": "cake", "reaction": LOVED, "how": EATEN, "giver_id": None})

    def test_a_meal_to_their_taste_eases_them_and_one_that_is_not_weighs_on_them(self) -> None:
        items = self.world.items
        self.assertLess(items.use_effects(self.world, self.lucia, self.cake)["stress"], 0)
        self.assertGreater(items.use_effects(self.world, self.raul, self.cake)["stress"], 0)
        self.assertNotIn("stress", items.use_effects(self.world, self.marta, self.cake))
        self.assertEqual(items.use_effects(self.world, self.lucia, self.cake)["hunger"], -20)

    def test_among_what_answers_their_hunger_they_take_what_they_like(self) -> None:
        pantry = self.world.containers["pantry_1"]
        pantry.items.clear()
        self.world.stock(pantry, "cake", 2, None)
        self.world.stock(pantry, "canned_beans", 2, None)
        for resident in (self.lucia, self.raul):
            resident.needs.hunger = 80
            for tag in ("salty", "tinned"):
                _set(self.world, resident, TAG, tag, 0)
            _set(self.world, resident, ITEM, "canned_beans", 0)
        food = self.world.items.best_food
        self.assertEqual(food(self.world, self.lucia, "pantry_1", "food").definition_id, "cake")
        self.assertEqual(food(self.world, self.raul, "pantry_1", "food").definition_id, "canned_beans")

    def test_hunger_and_who_it_comes_from_can_tip_a_reaction(self) -> None:
        _set(self.world, self.marta, TAG, "sweet", 10)
        self.assertEqual(self.tastes.react(self.world, self.marta, self.cake, EATEN), NEUTRAL)
        self.marta.needs.hunger = 100
        self.assertEqual(self.tastes.react(self.world, self.marta, self.cake, EATEN), LIKED)
        self.marta.needs.hunger = 0
        self.world.relationship("marta", "lucia").affection = 90
        self.assertEqual(self.tastes.react(self.world, self.marta, self.cake, GIVEN, self.lucia), LIKED)

    def test_how_a_present_is_taken_is_what_it_does_to_what_is_felt_for_the_giver(self) -> None:
        self.tastes.react(self.world, self.lucia, self.cake, GIVEN, self.marta)
        self.tastes.react(self.world, self.raul, self.cake, GIVEN, self.marta)
        warm, cold = self.world.relationship("lucia", "marta"), self.world.relationship("raul", "marta")
        self.assertGreater(warm.affection, 8.0)
        self.assertGreater(warm.trust, 0.0)
        self.assertLess(cold.affection, 0.0)
        self.assertLess(cold.trust, 0.0)
        self.assertEqual(self.world.relationship("marta", "lucia").affection, 0.0, "one way only")
        self.assertIn("Raúl recibe una tarta de Marta con mala cara", "\n".join(self.world.event_log))

    def test_a_thing_used_is_taken_by_taste_too(self) -> None:
        radio = self.world.registries.items.get("old_radio")
        _set(self.world, self.marta, CATEGORY, "tool", 0)
        _set(self.world, self.marta, ITEM, "old_radio", 0)
        self.assertEqual(self.tastes.react(self.world, self.marta, radio, USED), LOVED)
        self.assertIn("Marta disfruta de lo lindo con una radio vieja", "\n".join(self.world.event_log))

    def test_nothing_is_made_of_what_has_nothing_to_like_about_it(self) -> None:
        water = self.world.registries.items.get("water")
        _set(self.world, self.marta, ITEM, "water", 0)
        before = len(self.world.event_log)
        self.assertEqual(self.tastes.react(self.world, self.marta, water, "drunk"), NEUTRAL)
        self.assertEqual(len(self.world.event_log), before)
        self.assertEqual(self.tastes.found_out(self.world, self.marta), [("tag:music", KNOWN, LOVED)])
        self.assertEqual(self.world.taste_knowledge.keys(PLAYER, "marta"), ["tag:music"])


class WorthTests(unittest.TestCase):
    def setUp(self) -> None:
        self.world = _world(CAKE)
        self.items, self.tastes = self.world.items, self.world.tastes
        self.marta, self.raul, self.lucia = (self.world.residents[name] for name in ("marta", "raul", "lucia"))
        self.cake = self.world.registries.items.get("cake")
        self.radio = self.world.registries.items.get("old_radio")
        # Plenty of everything, so that how few there are counts for next to nothing.
        self.world.stock(self.world.containers["pantry_1"], "cake", 300, None)
        self.world.stock(self.world.containers["pantry_1"], "old_radio", 300, None)

    def test_a_thing_is_worth_its_base_value_to_whoever_makes_nothing_of_it(self) -> None:
        self.assertAlmostEqual(self.items.personal_value(self.world, self.raul, self.cake), self.cake.base_value, delta=0.1)

    def test_a_liking_makes_it_worth_more_and_a_loathing_less(self) -> None:
        plain = self.items.personal_value(self.world, self.raul, self.cake)
        self.assertGreater(self.items.personal_value(self.world, self.lucia, self.cake), plain * 1.3)
        _set(self.world, self.raul, TAG, "sweet", -80)
        self.assertLess(self.items.personal_value(self.world, self.raul, self.cake), plain * 0.7)
        self.assertGreater(
            self.items.personal_value(self.world, self.marta, self.radio),
            self.items.personal_value(self.world, self.raul, self.radio),
        )

    def test_a_pressing_need_it_answers_makes_it_worth_more(self) -> None:
        full = self.items.personal_value(self.world, self.raul, self.cake)
        self.raul.needs.hunger = 95
        self.assertGreater(self.items.personal_value(self.world, self.raul, self.cake), full * 1.3)
        self.assertAlmostEqual(self.items.personal_value(self.world, self.raul, self.radio), self.radio.base_value, delta=0.2)

    def test_the_fewer_there_are_the_more_one_is_worth(self) -> None:
        ring = ItemDefinition("ring", "anillo", "un", "gift", base_value=40)
        self.assertAlmostEqual(self.items.personal_value(self.world, self.raul, ring), 40 * (1 + self.world.registries.tastes.worth_scarcity))
        self.assertGreater(
            self.items.personal_value(self.world, self.raul, ring), 40 * 1.2, "the only one there is, or none at all"
        )

    def test_what_someone_dear_gave_is_worth_more_to_whoever_was_given_it(self) -> None:
        keepsake = self.world.new_item("old_radio", owner_id="raul")
        keepsake.given_by = "lucia"
        plain = self.items.personal_value(self.world, self.raul, self.radio, keepsake)
        self.world.relationship("raul", "lucia").affection = 80
        dear = self.items.personal_value(self.world, self.raul, self.radio, keepsake)
        self.assertGreater(dear, plain * 1.3)
        self.assertAlmostEqual(self.items.personal_value(self.world, self.raul, self.radio), plain)
        self.world.relationship("raul", "lucia").affection = -80
        self.assertAlmostEqual(self.items.personal_value(self.world, self.raul, self.radio, keepsake), plain)

    def test_a_favourite_is_worth_more_than_its_base_value_and_is_the_last_thing_traded(self) -> None:
        self.assertEqual(self.tastes.favourites(self.world, self.lucia)["favorite_food"], "cake")
        self.assertGreater(self.items.personal_value(self.world, self.lucia, self.cake), self.cake.base_value)
        # Raúl has a sweet tooth of his own and something worth as much as a cake to offer for one.
        _set(self.world, self.raul, TAG, "sweet", 50)
        for item_id in ("fair", "trinket"):
            self.world.registries.items.register(ItemDefinition(item_id, item_id, "un", "gift", base_value=20))
            self.world.stock(self.world.containers["pantry_1"], item_id, 300, None)
        _set(self.world, self.raul, ITEM, "trinket", 60)
        self.raul.inventory.add(self.world.new_item("fair", owner_id="raul"))
        for owner in (self.lucia, self.marta):
            owner.inventory.add(self.world.new_item("cake", owner_id=owner.resident_id))
        # Marta makes nothing of cake and loses nothing by the swap. Lucía will not part with hers.
        self.assertIsNotNone(self.items.propose_trade(self.world, self.raul, self.marta))
        self.assertIsNone(self.items.propose_trade(self.world, self.raul, self.lucia))
        # With something else he wants as much, that is what she lets go.
        self.lucia.inventory.add(self.world.new_item("trinket", owner_id="lucia"))
        offer = self.items.propose_trade(self.world, self.raul, self.lucia)
        self.assertEqual([self.lucia.inventory.find(i).definition_id for i in offer.requested_instance_ids], ["trinket"])

    def test_favourites_are_read_off_the_tastes_there_are_and_say_nothing_where_nothing_stands_out(self) -> None:
        nothing = {"favorite_food": None, "hated_food": None, "favorite_item": None, "hated_item": None}
        self.assertEqual(self.tastes.favourites(self.world, self.raul), nothing)
        _set(self.world, self.raul, TAG, "sweet", -90)
        _set(self.world, self.raul, TAG, "hot", 50)
        _set(self.world, self.raul, ITEM, "hoe", -100)
        self.assertEqual(
            self.tastes.favourites(self.world, self.raul),
            {"favorite_food": "stew", "hated_food": "cake", "favorite_item": None, "hated_item": "hoe"},
        )
        self.assertEqual(self.tastes.favourites(self.world, self.marta)["favorite_item"], "old_radio")


class FindingOutTests(unittest.TestCase):
    def setUp(self) -> None:
        self.world = _world(CAKE, ALGAE)
        self.tastes, self.settings = self.world.tastes, self.world.registries.tastes
        self.marta, self.raul, self.lucia = (self.world.residents[name] for name in ("marta", "raul", "lucia"))
        self.cake = self.world.registries.items.get("cake")
        _set(self.world, self.raul, TAG, "sweet", -80)
        for resident in (self.raul, self.lucia):
            _set(self.world, resident, CATEGORY, "food", 0)
            _set(self.world, resident, ITEM, "cake", 0)

    def _state(self, resident: Resident, key: str, observer: str = PLAYER) -> str:
        return self.world.taste_knowledge.state(observer, resident.resident_id, key, self.settings)

    def test_that_a_taste_is_there_does_not_make_it_known(self) -> None:
        self.assertEqual(self.tastes.profile(self.world, self.raul).tags["sweet"].value, -80)
        self.assertEqual(self._state(self.raul, "tag:sweet"), UNKNOWN)
        self.assertEqual(self.tastes.found_out(self.world, self.raul), [])
        self.tastes.liking(self.world, self.raul, self.cake)
        self.items_value = self.world.items.personal_value(self.world, self.raul, self.cake)
        self.assertEqual(self.tastes.found_out(self.world, self.raul), [], "nor does weighing things up by it")

    def test_a_taste_is_found_out_step_by_step_from_what_is_seen(self) -> None:
        seen = []
        for _ in range(3):
            self.tastes.react(self.world, self.raul, self.cake, EATEN)
            seen.append(self._state(self.raul, "tag:sweet"))
        self.assertEqual(seen, [SUSPECTED, SUSPECTED, KNOWN])
        found = [line for line in self.world.event_log if FOUND_OUT_EVENT in line]
        self.assertIn("Raúl parece evitar lo dulce", found[0] + found[1])
        self.assertIn("Raúl detesta lo dulce", found[-1] + found[-2])
        self.assertEqual(
            sorted(self.tastes.found_out(self.world, self.raul)),
            [("item:cake", KNOWN, HATED), ("tag:sweet", KNOWN, HATED)],
        )

    def test_while_it_is_only_suspected_it_is_seen_which_way_it_goes_and_not_how_far(self) -> None:
        self.tastes.react(self.world, self.raul, self.cake, EATEN)
        self.assertEqual(sorted(self.tastes.found_out(self.world, self.raul)), [("item:cake", SUSPECTED, DISLIKED), ("tag:sweet", SUSPECTED, DISLIKED)])
        event = [event for event in self.world.events.pending if event.event_type == FOUND_OUT_EVENT][0]
        self.assertEqual(event.data, {"resident_id": "raul", "taste": "item:cake", "state": SUSPECTED, "leaning": DISLIKED})

    def test_nowhere_in_what_is_found_out_is_there_a_number(self) -> None:
        for _ in range(4):
            for resident in (self.raul, self.lucia, self.marta):
                self.tastes.react(self.world, resident, self.cake, EATEN)
                self.tastes.react(self.world, resident, self.world.registries.items.get("sopa_algas"), EATEN)
        for resident in (self.raul, self.lucia, self.marta):
            for entry in self.tastes.found_out(self.world, resident):
                self.assertTrue(all(isinstance(part, str) for part in entry), entry)
        events = [event for event in self.world.events.pending if event.event_type in (FOUND_OUT_EVENT, REACTION_EVENT)]
        self.assertTrue(events)
        for event in events:
            self.assertFalse(any(isinstance(value, (int, float)) for value in event.data.values()), event.data)
            self.assertFalse(any(character.isdigit() for character in event.text), event.text)

    def test_a_trait_is_there_for_anyone_to_see_and_so_is_the_taste_that_comes_of_it(self) -> None:
        self.assertEqual(self.tastes.found_out(self.world, self.lucia), [("tag:sweet", KNOWN, LOVED)])
        self.assertEqual(self._state(self.lucia, "tag:sweet", observer="raul"), UNKNOWN, "to the player, who sees her traits")

    def test_a_taste_that_was_outweighed_stays_out_of_sight(self) -> None:
        jelly = ItemDefinition("jelly", "gelatina", "una", "food", preference_tags=("sweet", "slimy"))
        _set(self.world, self.lucia, TAG, "slimy", -30)
        _set(self.world, self.lucia, ITEM, "jelly", 0)
        for _ in range(8):
            self.assertEqual(self.tastes.react(self.world, self.lucia, jelly, EATEN), LIKED)
        self.assertEqual(self._state(self.lucia, "tag:slimy"), UNKNOWN)
        self.assertEqual(self._state(self.lucia, "item:jelly"), KNOWN)
        slime = ItemDefinition("slime", "baba", "una", "food", preference_tags=("slimy",))
        _set(self.world, self.lucia, ITEM, "slime", 0)
        self.tastes.react(self.world, self.lucia, slime, EATEN)
        self.tastes.react(self.world, self.lucia, slime, EATEN)
        self.assertEqual(self._state(self.lucia, "tag:slimy"), SUSPECTED)

    def test_whoever_is_there_finds_out_too_and_nobody_else(self) -> None:
        self.raul.x, self.raul.y = 20, 14
        self.lucia.x, self.lucia.y = 21, 14
        self.marta.x, self.marta.y = 8, 5
        for _ in range(3):
            self.tastes.react(self.world, self.raul, self.cake, EATEN)
        self.assertEqual(self._state(self.raul, "tag:sweet", observer="lucia"), KNOWN)
        self.assertEqual(self._state(self.raul, "tag:sweet", observer="marta"), UNKNOWN)
        self.assertEqual(self._state(self.raul, "tag:sweet", observer="raul"), UNKNOWN, "nobody finds themselves out")

    def test_what_is_known_is_kept_apart_from_what_is_so(self) -> None:
        knowledge = TasteKnowledge()
        self.assertEqual(knowledge.observe(PLAYER, "raul", "tag:sweet", 1.0, self.settings), SUSPECTED)
        self.assertIsNone(knowledge.observe(PLAYER, "raul", "tag:sweet", 1.0, self.settings))
        self.assertEqual(knowledge.observe(PLAYER, "raul", "tag:sweet", 1.0, self.settings), KNOWN)
        self.assertIsNone(knowledge.observe(PLAYER, "raul", "tag:sweet", 0.0, self.settings))
        self.assertEqual(knowledge.seen, {PLAYER: {"raul": {"tag:sweet": 3.0}}})
        self.assertEqual(knowledge.state(PLAYER, "lucia", "tag:sweet", self.settings), UNKNOWN)
        # The taste changing hands in the profile changes nothing of what has been seen of it.
        self.tastes.react(self.world, self.raul, self.cake, EATEN)
        before = dict(self.world.taste_knowledge.seen[PLAYER]["raul"])
        self.tastes.profile(self.world, self.raul).tags["sweet"].learned = 150
        self.assertEqual(self.world.taste_knowledge.seen[PLAYER]["raul"], before)


class BetweenPeopleTests(unittest.TestCase):
    def setUp(self) -> None:
        self.world = _world(CAKE)
        self.items, self.tastes = self.world.items, self.world.tastes
        self.marta, self.raul, self.lucia = (self.world.residents[name] for name in ("marta", "raul", "lucia"))
        self.chat = self.world.registries.interactions["chat"]
        for resident in (self.marta, self.raul, self.lucia):
            _set(self.world, resident, CATEGORY, "food", 0)
            _set(self.world, resident, CATEGORY, "gift", 0)
            _set(self.world, resident, ITEM, "cake", 0)

    def _gift(self, giver: Resident, receiver: Resident) -> str:
        self.world.relationship(giver.resident_id, receiver.resident_id).affection = 60
        for _ in range(300):
            self.items.after_exchange(self.world, giver, receiver, self.chat)
            if receiver.inventory.items:
                return receiver.inventory.items[0].definition_id
        raise AssertionError("nothing was given")

    def test_a_giver_chooses_by_what_they_have_seen_of_the_other_and_not_by_what_is_so(self) -> None:
        ring = ItemDefinition("ring", "anillo", "un", "gift", base_value=22)
        self.world.registries.items.register(ring)
        _set(self.world, self.lucia, ITEM, "ring", 0)
        for item_id in ("cake", "ring"):
            self.marta.inventory.add(self.world.new_item(item_id, owner_id="marta"))
        # Lucía loves sweet things, but Marta has never seen it: she gives what is worth most.
        self.assertGreater(self.tastes.liking(self.world, self.lucia, self.world.registries.items.get("cake")), 60)
        self.assertEqual(self.tastes.believed_liking(self.world, self.marta, self.lucia, self.world.registries.items.get("cake")), 0)
        self.assertEqual(self._gift(self.marta, self.lucia), "ring")

    def test_having_seen_it_they_give_what_the_other_likes(self) -> None:
        ring = ItemDefinition("ring", "anillo", "un", "gift", base_value=22)
        self.world.registries.items.register(ring)
        _set(self.world, self.lucia, ITEM, "ring", 0)
        for item_id in ("cake", "ring"):
            self.marta.inventory.add(self.world.new_item(item_id, owner_id="marta"))
        self.world.taste_knowledge.observe("marta", "lucia", "tag:sweet", 1.0, self.world.registries.tastes)
        self.assertGreater(self.tastes.believed_liking(self.world, self.marta, self.lucia, self.world.registries.items.get("cake")), 60)
        self.assertEqual(self._gift(self.marta, self.lucia), "cake")
        given = self.lucia.inventory.items[0]
        self.assertEqual((given.owner_id, given.given_by), ("lucia", "marta"))
        self.assertGreater(self.world.relationship("lucia", "marta").affection, 8.0)
        self.assertIn(REACTION_EVENT, _types(self.world))
        self.assertEqual(self.world.taste_knowledge.state("marta", "lucia", "item:cake", self.world.registries.tastes), SUSPECTED)

    def test_a_present_that_is_loathed_is_no_help_to_the_giver(self) -> None:
        _set(self.world, self.raul, TAG, "sweet", -90)
        self.marta.inventory.add(self.world.new_item("cake", owner_id="marta"))
        self.assertEqual(self._gift(self.marta, self.raul), "cake")
        self.assertLess(self.world.relationship("raul", "marta").affection, 0.0)

    def test_a_swap_turned_down_over_a_taste_is_said_once_a_day_and_shows_it(self) -> None:
        # Marta would give a ring for the radio, and the ring is worth more on paper. Raúl cannot stand it.
        self.world.registries.items.register(ItemDefinition("ring", "anillo", "un", "gift", base_value=40))
        self.marta.inventory.add(self.world.new_item("ring", owner_id="marta"))
        self.raul.inventory.add(self.world.new_item("old_radio", owner_id="raul"))
        _set(self.world, self.raul, ITEM, "ring", -90)
        _set(self.world, self.raul, CATEGORY, "tool", 0)
        self.assertIsNone(self.items.propose_trade(self.world, self.marta, self.raul))
        for _ in range(5):
            self.items.after_exchange(self.world, self.marta, self.raul, self.chat)
        self.assertEqual(_types(self.world).count(REFUSAL_EVENT), 1)
        self.assertIn("Raúl no quiere un anillo de Marta", "\n".join(self.world.event_log))
        self.assertEqual(self.world.taste_knowledge.state(PLAYER, "raul", "item:ring", self.world.registries.tastes), SUSPECTED)
        self.assertEqual(self.world.taste_knowledge.state("marta", "raul", "item:ring", self.world.registries.tastes), SUSPECTED)
        self.world.clock.advance_minutes(MINUTES_PER_DAY)
        self.items.after_exchange(self.world, self.marta, self.raul, self.chat)
        self.assertEqual(_types(self.world).count(REFUSAL_EVENT), 2)
        # With nothing against the ring, it is simply a swap.
        _set(self.world, self.raul, ITEM, "ring", 0)
        self.items.after_exchange(self.world, self.marta, self.raul, self.chat)
        self.assertIn("trade_made", _types(self.world))
        self.assertEqual(_types(self.world).count(REFUSAL_EVENT), 2)

    def test_now_and_then_someone_speaks_of_a_taste_of_theirs_and_it_shows(self) -> None:
        spoken = 0
        for minute in range(400):
            self.world.clock.advance_minutes(1)
            spoken += self.tastes.after_exchange(self.world, self.lucia, self.raul)
        share = spoken / 400
        self.assertTrue(0.04 < share < 0.18, share)
        self.assertIn("Lucía le cuenta a Raúl que adora lo dulce", [line.split(" | ")[2] for line in self.world.event_log if MENTION_EVENT in line])
        self.assertEqual(self.world.taste_knowledge.state("raul", "lucia", "tag:sweet", self.world.registries.tastes), KNOWN)
        # Someone with nothing they feel strongly about has nothing to say.
        self.tastes.profile(self.world, self.raul).tags.clear()
        self.assertEqual(sum(self.tastes.after_exchange(self.world, self.raul, self.lucia) for _ in range(50)), 0)

    def test_speaking_of_it_draws_nothing_from_what_the_rest_runs_on(self) -> None:
        before = self.world.rng.get_state()
        for _ in range(50):
            self.world.clock.advance_minutes(1)
            self.tastes.after_exchange(self.world, self.lucia, self.raul)
        self.assertEqual(self.world.rng.get_state(), before)


class SavedTastesTests(unittest.TestCase):
    def _round_trip(self, world: SimulationWorld, registries: BuiltInRegistries | None = None) -> SimulationWorld:
        manager = SaveManager()
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "save.json"
            manager.save(world, path)
            return manager.load(path, registries or world.registries)

    def test_tastes_made_on_the_way_and_what_was_found_out_are_kept(self) -> None:
        world = _world(ALGAE)
        marta, lucia = world.residents["marta"], world.residents["lucia"]
        algae = world.registries.items.get("sopa_algas")
        for _ in range(3):
            world.tastes.react(world, marta, algae, EATEN)
        world.tastes.profile(world, marta).tags["slimy"].learned = -12.5
        gift = world.new_item("old_radio", owner_id="lucia")
        gift.given_by = "marta"
        lucia.inventory.add(gift)

        loaded = self._round_trip(world)

        self.assertEqual(loaded.taste_profiles["marta"], world.taste_profiles["marta"])
        self.assertEqual(loaded.taste_profiles["marta"].tags["slimy"].learned, -12.5)
        self.assertEqual(loaded.taste_knowledge, world.taste_knowledge)
        self.assertEqual(loaded.tastes.found_out(loaded, loaded.residents["marta"]), world.tastes.found_out(world, marta))
        self.assertEqual(loaded.residents["lucia"].inventory.items[0].given_by, "marta")
        self.assertEqual(SaveManager().to_data(loaded), SaveManager().to_data(world))
        # And the next taste is made as it would have been.
        cake = ItemDefinition("cake", "tarta", "una", "food", preference_tags=("crunchy",))
        for one in (world, loaded):
            one.tastes.meet(one, one.residents["raul"], cake)
        self.assertEqual(loaded.taste_profiles["raul"], world.taste_profiles["raul"])

    def test_a_save_made_with_a_pack_loads_without_it_and_keeps_its_tastes(self) -> None:
        world = _world(ALGAE)
        marta = world.residents["marta"]
        for _ in range(3):
            world.tastes.react(world, marta, world.registries.items.get("sopa_algas"), EATEN)
        marta.inventory.add(world.new_item("sopa_algas", owner_id="marta"))
        slimy = world.taste_profiles["marta"].tags["slimy"].leaning

        without = self._round_trip(world, _registries())

        self.assertIsNone(without.registries.items.find("sopa_algas"))
        self.assertEqual(without.taste_profiles["marta"].tags["slimy"].leaning, slimy)
        self.assertIn("radioactive", without.taste_profiles["marta"].tags)
        self.assertEqual(without.taste_profiles["marta"].items.keys(), world.taste_profiles["marta"].items.keys())
        without.step(MINUTES_PER_DAY)
        self.assertTrue(without.tastes.found_out(without, without.residents["marta"]))
        self.assertTrue(without.tastes.favourites(without, without.residents["marta"]))
        # And it is there when the pack comes back.
        back = self._round_trip(without, _registries(ALGAE))
        self.assertEqual(back.taste_profiles["marta"].tags["slimy"].leaning, slimy)

    def test_a_save_from_before_loads_with_no_tastes_but_what_traits_give(self) -> None:
        manager = SaveManager()
        world = _world()
        data = manager.to_data(world)
        data["version"] = 18
        del data["tastes"], data["taste_knowledge"]
        for resident in data["residents"]:
            for item in resident["inventory"]:
                del item["given_by"]
        old = manager.from_data(json.loads(json.dumps(data)), world.registries)
        self.assertEqual(old.taste_profiles, {})
        self.assertEqual(old.tastes.profile(old, old.residents["lucia"]).keys(), ["tag:sweet"])
        self.assertEqual(old.tastes.profile(old, old.residents["raul"]).keys(), [])
        old.step(MINUTES_PER_DAY)

    def test_damaged_tastes_in_a_save_are_left_out(self) -> None:
        manager = SaveManager()
        world = _world()
        data = manager.to_data(world)
        data["tastes"] = {"marta": {"tag": {"sweet": "a lot", "sour": {"leaning": 30}}, "item": 4}, "raul": 7}
        data["taste_knowledge"] = {"@player": {"marta": {"tag:sweet": "x", "tag:sour": 2}, "raul": 3}, "lucia": []}
        loaded = manager.from_data(json.loads(json.dumps(data)), world.registries)
        self.assertEqual(loaded.taste_profiles["marta"].tags, {"sour": Taste(leaning=30.0)})
        self.assertEqual(loaded.taste_profiles["raul"], TasteProfile())
        self.assertEqual(loaded.taste_knowledge.seen["@player"]["marta"], {"tag:sour": 2.0})


class SettlementTests(unittest.TestCase):
    def test_over_four_weeks_a_taste_of_everyone_comes_to_be_known_through_what_happened(self) -> None:
        world = SimulationWorld.demo_world(seed=7, registries=_registries())
        # Nobody has shown anything yet: what is known is what their traits say.
        self.assertEqual(sum(len(world.tastes.found_out(world, resident)) for resident in world.residents.values()), 2)
        everyone = dict(world.residents)
        world.step(28 * MINUTES_PER_DAY)
        self.assertEqual(world.deaths, [])
        for resident_id, resident in everyone.items():
            known = [key for key, state, _ in world.tastes.found_out(world, resident) if state == KNOWN]
            learned = [key for key in known if key not in ("tag:music", "tag:sweet")]
            self.assertTrue(learned, resident_id)
        types = _types(world)
        self.assertIn(REACTION_EVENT, types)
        self.assertIn(FOUND_OUT_EVENT, types)
        reactions = {event.data["reaction"] for event in world.history if event.event_type == REACTION_EVENT}
        self.assertFalse(reactions, "what is taken to taste is not history")

    def test_the_same_seed_gives_the_same_tastes_and_another_seed_others(self) -> None:
        def tastes_after(seed: int) -> dict:
            world = SimulationWorld.demo_world(seed=seed, registries=_registries())
            world.step(2 * MINUTES_PER_DAY)
            return SaveManager().to_data(world)["tastes"]

        first = tastes_after(11)
        self.assertEqual(first, tastes_after(11))
        self.assertNotEqual(first, tastes_after(12))
        self.assertGreater(len(first), 5)

    def test_tastes_need_no_pygame(self) -> None:
        check = (
            "import sys; import simulation.world, save.save_manager; "
            "import simulation.tastes.taste_system, simulation.tastes.knowledge, simulation.tastes.reaction, "
            "simulation.tastes.leaning, simulation.tastes.settings, simulation.tastes.taste; "
            "from simulation.world import SimulationWorld; SimulationWorld.demo_world().step(600); "
            "sys.exit(1 if 'pygame' in sys.modules else 0)"
        )
        done = subprocess.run([sys.executable, "-c", check], cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(done.returncode, 0, done.stderr)


if __name__ == "__main__":
    unittest.main()
