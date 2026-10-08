"""What is talked of (S58): subjects, how they are taken, and the words the player gives."""

import json
import subprocess
import sys
import unittest
from dataclasses import replace
from pathlib import Path

from save.save_manager import SaveManager
from simulation.commands import (
    AddWordCommand,
    AnswerAskCommand,
    DismissAskCommand,
    SetNicknameCommand,
    SetPhraseCommand,
    TalkAboutCommand,
)
from simulation.events.event import DomainEvent
from simulation.family.family_system import SLEEP_ROUGH_ACTION
from simulation.registries import DATA_DIR, builtin_registries
from simulation.residents.activity import Activity
from simulation.residents.needs import Needs
from simulation.residents.resident import Resident
from simulation.rng import SimulationRNG
from simulation.social.social_system import SocialSystem
from simulation.social.talk import (
    ASK_NICKNAME,
    ASK_PHRASE,
    ASK_SUBJECT,
    ASK_WORD,
    ASKED_EVENT,
    FACT,
    ITEM,
    PERSON,
    TAKEN_EVENT,
    WORD,
    Ask,
    Shown,
    slug,
    subject_of,
)
from simulation.social.talk_settings import TalkSettings, talk_settings_from_data
from simulation.tastes.knowledge import PLAYER
from simulation.tastes.settings import DISLIKED, HATED, KNOWN, LIKED, LOVED, NEUTRAL, SUSPECTED
from simulation.tastes.taste import TAG, Taste, key_of
from simulation.world import SimulationWorld

ROOT = Path(__file__).resolve().parents[1]
MINUTES_PER_DAY = 24 * 60
# Two tiles of open ground side by side, out of sight of the dormitory.
HERE, BESIDE = (20, 18), (21, 18)
INDOORS = (5, 5)
ZOPENCO = "insults.zopenco"


def _stand(resident: Resident, tile: tuple[int, int]) -> None:
    """Put a resident on a tile with nothing on their mind, and keep them there."""
    resident.x, resident.y = tile
    resident.needs = Needs(hunger=0, tiredness=0, social=0, stress=0)
    resident.activity = Activity("wander", minutes_left=6000, using=True)


def _quiet_world(seed: int = 7) -> SimulationWorld:
    """The demo settlement with no feelings between anyone, nothing kept anywhere and
    everybody shut indoors, awake: there is nothing to talk of but what a test gives."""
    world = SimulationWorld.demo_world(seed=seed)
    world.relationships.clear()
    for inventory in world.containers.values():
        inventory.items.clear()
    for resident in world.residents.values():
        resident.job_id = resident.post_id = None
        resident.inventory.items.clear()
        _stand(resident, INDOORS)
    return world


def _settings(world: SimulationWorld, **changes: object) -> None:
    world.registries = replace(world.registries, talk=replace(world.registries.talk, **changes))


def _side_by_side(world: SimulationWorld, a_id: str, b_id: str) -> tuple[Resident, Resident]:
    a, b = world.residents[a_id], world.residents[b_id]
    _stand(a, HERE)
    _stand(b, BESIDE)
    return a, b


def _likes(world: SimulationWorld, resident: Resident, word_id: str, liking: float) -> None:
    """Give a resident the taste for a word that a test needs them to have."""
    world.tastes.profile(world, resident).tags[world.talk.tag_of(word_id)] = Taste(leaning=liking)


def _chat(world: SimulationWorld, a: Resident, b: Resident, exchange: str = "chat", limit: int = 200) -> Activity:
    """Have `a` start a talk with `b` and let it run its course. Returns what `a` was at
    while it lasted."""
    a.activity = SocialSystem().pursue(world, a, b, exchange)
    seen = None
    for _ in range(limit):
        world.step(1)
        for resident in world.residents.values():
            resident.needs = Needs(hunger=0, tiredness=0, social=0, stress=0)
        in_it = a.activity is not None and a.activity.action == exchange and a.activity.using
        if in_it:
            seen = a.activity
        talking = any(
            each.activity is not None and each.activity.action == exchange and each.activity.using for each in (a, b)
        )
        if seen is not None and not talking:
            return seen
    raise AssertionError("the talk never ran its course")


def _types(world: SimulationWorld) -> list[str]:
    return [line.split(" | ")[1] for line in world.event_log]


class DataTests(unittest.TestCase):
    def test_what_talk_is_made_of_is_data(self) -> None:
        registries = builtin_registries()
        talk = registries.talk
        self.assertTrue(talk.enabled)
        self.assertEqual(
            set(talk.lists), {"insults", "compliments", "foods", "cravings", "places", "dangers", "subjects", "gossip"}
        )
        self.assertEqual(set(talk.phrases), {"greeting", "catchphrase", "glad", "low", "angry"})
        self.assertIn(talk.new_subjects, talk.lists)
        self.assertTrue(all(each.ask and each.patterns for each in talk.lists.values()))
        self.assertTrue(registries.interactions["chat"].subject)
        self.assertTrue(registries.interactions["stories"].subject)
        self.assertFalse(registries.interactions["argument"].subject)
        # A subject that is disliked takes the good of the talk away and one that is liked adds to it.
        self.assertEqual(talk.relish[DISLIKED], 0.0)
        self.assertLess(talk.taken[DISLIKED]["affection"], 0.0)
        self.assertGreater(talk.taken[LIKED]["affection"], 0.0)
        self.assertNotIn(NEUTRAL, talk.taken)

    def test_the_lists_come_empty_for_the_words_are_the_players(self) -> None:
        data = json.loads((DATA_DIR / "talk.json").read_text(encoding="utf-8"))
        self.assertTrue(all(each["words"] == [] for each in data["lists"].values()))
        world = _quiet_world()
        self.assertEqual(world.talk.all_words(world), [])

    def test_data_that_makes_no_sense_is_refused(self) -> None:
        good = {"lists": {"subjects": {"name": "Temas"}}}
        self.assertEqual(talk_settings_from_data(good).new_subjects, "subjects")
        for bad in (
            {"lists": {"subjects": {}}},
            {"phrases": {"greeting": {}}},
            {"phrases": {"greeting": {"name": "Saludo", "when": "never"}}},
            {**good, "taken": {"furious": {"affection": -1}}},
            {**good, "taken": {"hated": {"hunger": -1}}},
            {**good, "relish": {"furious": 0}},
            {**good, "new_subjects": "nowhere"},
            {**good, "asks": {"chance": 2}},
            {**good, "longest": 0},
        ):
            with self.assertRaises(ValueError, msg=str(bad)):
                talk_settings_from_data(bad)

    def test_a_settlement_without_the_data_talks_as_it_always_did(self) -> None:
        world = _quiet_world()
        world.registries = replace(world.registries, talk=TalkSettings())
        a, b = _side_by_side(world, "marta", "raul")
        was = _chat(world, a, b)
        self.assertEqual((was.about, was.brought), ("", False))
        started = next(line for line in world.event_log if "| chat_started |" in line)
        self.assertIn(' — Marta: "', started)
        self.assertNotIn(TAKEN_EVENT, _types(world))

    def test_it_needs_no_pygame(self) -> None:
        code = (
            "import sys; from simulation.world import SimulationWorld; "
            "from simulation.commands import AddWordCommand; world = SimulationWorld.demo_world(); "
            "world.apply_command(AddWordCommand('insults', 'zopenco')); world.step(60 * 24 * 3); "
            "print('pygame' in sys.modules)"
        )
        result = subprocess.run([sys.executable, "-c", code], cwd=ROOT, capture_output=True, text=True, check=True)
        self.assertEqual(result.stdout.strip().splitlines()[-1], "False")


class WordTests(unittest.TestCase):
    def setUp(self) -> None:
        self.world = _quiet_world()

    def test_a_word_goes_into_its_list_and_is_something_to_talk_of(self) -> None:
        world = self.world
        result = world.apply_command(AddWordCommand("insults", "  Zopenco  "))
        self.assertTrue(result.ok, result.message)
        (definition, word), = world.talk.all_words(world)
        self.assertEqual((definition.list_id, word.word_id, word.text), ("insults", ZOPENCO, "Zopenco"))
        self.assertTrue(world.talk.valid(world, subject_of(WORD, ZOPENCO)))
        self.assertIn(subject_of(WORD, ZOPENCO), world.talk.vocabulary(world, world.residents["marta"]))
        self.assertIn("word_given", _types(world))

    def test_the_same_word_is_not_put_twice_however_it_is_written(self) -> None:
        world = self.world
        self.assertEqual(slug("  ¡El Viejo  MADRID! "), "el_viejo_madrid")
        self.assertTrue(world.add_word("places", "el Viejo Madrid").ok)
        self.assertFalse(world.add_word("places", "El viejo madrid!").ok)
        # The same word is another thing in another list.
        self.assertTrue(world.add_word("dangers", "el Viejo Madrid").ok)
        self.assertEqual(len(world.talk.all_words(world)), 2)

    def test_a_word_that_cannot_be_kept_is_refused(self) -> None:
        world = self.world
        longest = world.registries.talk.longest
        for list_id, text in (("nowhere", "algo"), ("insults", ""), ("insults", "   "), ("insults", "¡¡!!"), ("insults", "x" * (longest + 1))):
            self.assertFalse(world.add_word(list_id, text).ok, (list_id, text))
        self.assertTrue(world.add_word("insults", "x" * longest).ok)
        self.assertEqual(len(world.talk.all_words(world)), 1)

    def test_a_list_can_come_with_words_of_its_own(self) -> None:
        world = self.world
        subjects = world.registries.talk.lists["subjects"]
        _settings(world, lists={**world.registries.talk.lists, "subjects": replace(subjects, words=("el tiempo",))})
        self.assertEqual([word.word_id for word in world.talk.words(world, "subjects")], ["subjects.el_tiempo"])
        self.assertFalse(world.add_word("subjects", "El Tiempo").ok)

    def test_each_has_phrases_of_their_own_and_they_can_be_taken_back(self) -> None:
        world = self.world
        self.assertTrue(world.apply_command(SetPhraseCommand("marta", "greeting", " ¡Buenas! ")).ok)
        self.assertEqual(world.talk.phrase(world, "marta", "greeting"), "¡Buenas!")
        self.assertEqual(world.talk.phrase(world, "raul", "greeting"), "")
        self.assertFalse(world.set_phrase("marta", "motto", "algo").ok)
        self.assertFalse(world.set_phrase("nobody", "greeting", "algo").ok)
        self.assertFalse(world.set_phrase("marta", "greeting", "x" * 200).ok)
        self.assertTrue(world.set_phrase("marta", "greeting", "").ok)
        self.assertEqual(world.talk.phrase(world, "marta", "greeting"), "")

    def test_what_one_calls_another_is_theirs_and_goes_one_way(self) -> None:
        world = self.world
        self.assertTrue(world.apply_command(SetNicknameCommand("marta", "raul", "el Rulas")).ok)
        self.assertEqual(world.talk.nickname(world, "marta", "raul"), "el Rulas")
        self.assertEqual(world.talk.nickname(world, "raul", "marta"), "Marta")
        self.assertEqual(world.talk.nickname(world, "ines", "raul"), "Raúl")
        self.assertEqual(world.talk.label(world, subject_of(PERSON, "raul"), "marta"), "el Rulas")
        self.assertFalse(world.set_nickname("marta", "marta", "yo").ok)
        self.assertFalse(world.set_nickname("marta", "nobody", "x").ok)
        self.assertTrue(world.set_nickname("marta", "raul", "").ok)
        self.assertEqual(world.talk.nickname(world, "marta", "raul"), "Raúl")


class SubjectTests(unittest.TestCase):
    def setUp(self) -> None:
        self.world = _quiet_world()
        self.marta, self.raul = _side_by_side(self.world, "marta", "raul")
        self.world.add_word("insults", "zopenco")
        self.world.add_word("places", "el Viejo Madrid")

    def _picks(self, minutes: int = 300) -> list[str]:
        found = []
        for _ in range(minutes):
            self.world.clock.advance_minutes(1)
            picked = self.world.talk.pick(self.world, self.marta, self.raul)
            found.append(picked[0] if picked is not None else "")
        return found

    def test_somebody_brings_up_what_they_like(self) -> None:
        world = self.world
        _likes(world, self.marta, ZOPENCO, 80)
        _likes(world, self.marta, "places.el_viejo_madrid", -80)
        self.assertEqual(set(self._picks()), {subject_of(WORD, ZOPENCO)})

    def test_with_nothing_they_care_for_any_word_will_do_and_with_no_words_nothing(self) -> None:
        world = self.world
        for word_id in (ZOPENCO, "places.el_viejo_madrid"):
            _likes(world, self.marta, word_id, 0)
        self.assertEqual(
            set(self._picks()), {subject_of(WORD, ZOPENCO), subject_of(WORD, "places.el_viejo_madrid")}
        )
        world.words.lists.clear()
        self.assertEqual(set(self._picks(50)), {""})

    def test_they_talk_of_the_things_they_know_of_and_of_nobody_elses(self) -> None:
        world = self.world
        crate = world.containers["crate_dorm"]
        world.stock(crate, "stew", 2, None)
        world.stock(crate, "liquor", 1, "raul")
        world.stock(self.marta.inventory, "hoe", 1, "marta")
        self.assertEqual([each.item_id for each in world.talk.known_items(world, self.marta)], ["hoe", "stew"])
        self.assertEqual([each.item_id for each in world.talk.known_items(world, self.raul)], ["liquor", "stew"])
        for word_id in (ZOPENCO, "places.el_viejo_madrid"):
            _likes(world, self.marta, word_id, -80)
        # What they make of the stew is what they would come to it with: they never had any.
        before = world.tastes.profile(world, self.marta).keys()
        fancy = world.tastes.fancy(world, self.marta, world.registries.items.resolve("stew"))
        self.assertEqual(world.tastes.profile(world, self.marta).keys(), before, "guessing makes no taste")
        world.tastes.meet(world, self.marta, world.registries.items.resolve("stew"))
        self.assertAlmostEqual(world.tastes.liking(world, self.marta, world.registries.items.resolve("stew")), fancy)

    def test_they_talk_of_whoever_they_feel_strongly_about_but_not_to_their_face(self) -> None:
        world = self.world
        for word_id in (ZOPENCO, "places.el_viejo_madrid"):
            _likes(world, self.marta, word_id, -80)
        world.relationship("marta", "ines").resentment = 60
        world.relationship("marta", "raul").affection = 90
        self.assertEqual(set(self._picks(60)), {subject_of(PERSON, "ines")})
        self.assertEqual(
            world.talk.sentence(world, self.marta, subject_of(PERSON, "ines"), SimulationRNG.keyed(1, "x")).count("Inés"), 1
        )

    def test_what_they_have_seen_the_other_dislike_they_bring_up_less(self) -> None:
        world = self.world
        other = "places.el_viejo_madrid"
        _likes(world, self.marta, ZOPENCO, 60)
        _likes(world, self.marta, other, 60)
        plain = self._picks(400)
        self.assertGreater(plain.count(subject_of(WORD, ZOPENCO)), 120)
        settings = world.registries.tastes
        world.taste_knowledge.observe(
            "marta", "raul", key_of(TAG, world.talk.tag_of(ZOPENCO)), settings.known_at, settings, HATED
        )
        minded = self._picks(400)
        self.assertLess(minded.count(subject_of(WORD, ZOPENCO)), minded.count(subject_of(WORD, other)) / 2)
        # What the player has seen is not what Marta has.
        world.taste_knowledge.observe(
            PLAYER, "raul", key_of(TAG, world.talk.tag_of(other)), settings.known_at, settings, HATED
        )
        again = self._picks(400)
        self.assertLess(again.count(subject_of(WORD, ZOPENCO)), again.count(subject_of(WORD, other)) / 2)

    def test_news_the_other_has_not_heard_is_a_subject_and_is_told_by_being_it(self) -> None:
        world = self.world
        _settings(world, news_chance=1.0)
        fact = world.emit_event(DomainEvent("found", 40, "Marta encuentra algo", ["marta"]), fact_text="Marta encontró un tesoro")
        self.assertFalse(world.knowledge.knows("raul", fact.fact_id))
        was = _chat(world, self.marta, self.raul)
        self.assertEqual((was.about, was.brought), (subject_of(FACT, fact.fact_id), True))
        self.assertEqual(was.about_text, "lo de que Marta encontró un tesoro")
        self.assertTrue(world.knowledge.knows("raul", fact.fact_id))
        self.assertIn("rumor_told", _types(world))
        # Once he has heard it, it is no news to bring him.
        self.assertNotEqual(world.talk.pick(world, self.marta, self.raul)[0], subject_of(FACT, fact.fact_id))

    def test_news_is_not_always_what_is_brought_up(self) -> None:
        world = self.world
        _settings(world, news_chance=-1.0)
        _likes(world, self.marta, ZOPENCO, 80)
        fact = world.emit_event(DomainEvent("found", 40, "Marta encuentra algo", ["marta"]), fact_text="Marta encontró un tesoro")
        self.assertNotIn(subject_of(FACT, fact.fact_id), self._picks(100))

    def test_picking_a_subject_throws_none_of_the_settlements_dice(self) -> None:
        world = self.world
        _likes(world, self.marta, ZOPENCO, 80)
        world.stock(world.containers["crate_dorm"], "stew", 2, None)
        before = (world.rng.get_state(), world.event_rng.get_state())
        self._picks(50)
        world.talk.reaction(world, self.raul, subject_of(ITEM, "stew"))
        world.talk.taken(world, self.raul, self.marta, subject_of(WORD, ZOPENCO))
        self.assertEqual((world.rng.get_state(), world.event_rng.get_state()), before)

    def test_giving_words_throws_none_of_the_settlements_dice(self) -> None:
        plain, worded = SimulationWorld.demo_world(seed=11), SimulationWorld.demo_world(seed=11)
        worded.add_word("subjects", "el tiempo")
        worded.set_phrase("marta", "greeting", "¡Buenas!")
        worded.set_nickname("marta", "raul", "el Rulas")
        self.assertEqual(plain.rng.get_state(), worded.rng.get_state())
        self.assertEqual(plain.event_rng.get_state(), worded.event_rng.get_state())


class TakenTests(unittest.TestCase):
    """How whoever listens takes a subject tells on what they feel for whoever brought it up."""

    def _after(self, liking: float | None) -> tuple[SimulationWorld, Activity]:
        world = _quiet_world()
        marta, raul = _side_by_side(world, "marta", "raul")
        if liking is None:
            world.registries = replace(world.registries, talk=TalkSettings())
        else:
            world.add_word("insults", "zopenco")
            _likes(world, raul, ZOPENCO, liking)
            _likes(world, marta, ZOPENCO, 0)
            world.words.told["marta"] = ("raul", subject_of(WORD, ZOPENCO))
        return world, _chat(world, marta, raul)

    def test_the_chat_is_about_it_for_both_and_one_of_them_brought_it(self) -> None:
        world = _quiet_world()
        marta, raul = _side_by_side(world, "marta", "raul")
        world.add_word("insults", "zopenco")
        world.words.told["marta"] = ("raul", subject_of(WORD, ZOPENCO))
        marta.activity = SocialSystem().pursue(world, marta, raul, "chat")
        world.step(1)
        self.assertEqual(marta.activity.about, subject_of(WORD, ZOPENCO))
        self.assertEqual(raul.activity.about, marta.activity.about)
        self.assertEqual(raul.activity.about_text, marta.activity.about_text)
        self.assertEqual((marta.activity.brought, raul.activity.brought), (True, False))
        self.assertEqual(marta.activity.began_at, world.clock.total_minutes)
        self.assertEqual(world.talk.about(world, raul), (marta.activity.about, marta.activity.about_text))
        started = next(line for line in world.event_log if "| chat_started |" in line)
        self.assertIn(f"Marta y Raúl charlan sobre {marta.activity.about_text}", started)
        self.assertNotIn(" — ", started, "nobody is quoted any more")
        self.assertEqual(world.words.told, {}, "what was told is brought up once")

    def test_a_subject_they_dislike_lowers_it_and_one_they_like_raises_it(self) -> None:
        felt = {}
        for name, liking in (("none", None), (HATED, -90), (DISLIKED, -40), (NEUTRAL, 0), (LIKED, 40), (LOVED, 90)):
            world, _was = self._after(liking)
            felt[name] = world.relationship("raul", "marta")
        self.assertLess(felt[HATED].affection, felt[DISLIKED].affection)
        self.assertLess(felt[DISLIKED].affection, 0.0, "it was at nothing, and is lower")
        self.assertGreater(felt[NEUTRAL].affection, 0.0)
        self.assertLess(felt[NEUTRAL].affection, felt[LIKED].affection)
        self.assertLess(felt[LIKED].affection, felt[LOVED].affection)
        self.assertGreater(felt[HATED].resentment, 0.0)
        self.assertEqual(felt[LIKED].resentment, 0.0)
        # A subject they have nothing against leaves the talk what a talk has always been.
        for feeling in ("affection", "trust", "resentment", "attraction", "fear"):
            self.assertAlmostEqual(getattr(felt[NEUTRAL], feeling), getattr(felt["none"], feeling), msg=feeling)

    def test_whoever_brought_it_up_feels_as_after_any_talk(self) -> None:
        plain, _was = self._after(None)
        hated, _was = self._after(-90)
        for feeling in ("affection", "trust", "resentment"):
            self.assertAlmostEqual(
                getattr(hated.relationship("marta", "raul"), feeling), getattr(plain.relationship("marta", "raul"), feeling)
            )

    def test_how_it_was_taken_is_said_and_a_subject_taken_as_it_comes_is_not(self) -> None:
        world, _was = self._after(-90)
        line = next(line for line in world.event_log if f"| {TAKEN_EVENT} |" in line)
        self.assertIn('Raúl no soporta que Marta le hable sobre "zopenco"', line)
        world, _was = self._after(0)
        self.assertNotIn(TAKEN_EVENT, _types(world))

    def test_somebody_is_taken_by_whether_the_two_stand_the_same_way_on_them(self) -> None:
        world = _quiet_world()
        raul, marta = world.residents["raul"], world.residents["marta"]
        ines = subject_of(PERSON, "ines")
        sore = world.registries.talk.sore_from
        self.assertEqual(world.talk.reaction(world, raul, ines, marta), NEUTRAL)
        feelings = world.relationship("raul", "ines")
        # Marta speaks well of her, or stands nowhere: it goes by what he feels for her.
        for hers in (0, 50):
            world.relationship("marta", "ines").affection = hers
            for his, taken in ((sore, LIKED), (sore * 2, LOVED), (-sore, DISLIKED), (-sore * 2, HATED), (sore - 1, NEUTRAL)):
                feelings.affection, feelings.resentment = max(0, his), max(0, -his)
                self.assertEqual(world.talk.reaction(world, raul, ines, marta), taken, (hers, his))
        # She speaks ill of her: whoever cannot stand her either is glad to hear it.
        world.relationship("marta", "ines").affection = 0
        world.relationship("marta", "ines").resentment = 50
        for his, taken in ((sore, DISLIKED), (sore * 2, HATED), (-sore, LIKED), (-sore * 2, LOVED), (0, NEUTRAL)):
            feelings.affection, feelings.resentment = max(0, his), max(0, -his)
            self.assertEqual(world.talk.reaction(world, raul, ines, marta), taken, his)
        # Mixed feelings come to none, and nobody minds being talked of to their face.
        feelings.affection, feelings.resentment = 80, 75
        self.assertEqual(world.talk.reaction(world, raul, ines, marta), NEUTRAL)
        self.assertEqual(world.talk.reaction(world, raul, subject_of(PERSON, "raul"), marta), NEUTRAL)
        self.assertEqual(world.talk.reaction(world, raul, subject_of(PERSON, "nobody"), marta), NEUTRAL)

    def test_a_thing_is_taken_by_the_taste_they_would_have_for_it(self) -> None:
        world = _quiet_world()
        raul = world.residents["raul"]
        stew = world.registries.items.resolve("stew")
        profile = world.tastes.profile(world, raul)
        profile.categories[stew.category] = Taste(leaning=0)
        for tag in stew.preference_tags:
            profile.tags[tag] = Taste(leaning=-90)
        profile.items[stew.item_id] = Taste(leaning=0)
        self.assertEqual(world.talk.reaction(world, raul, subject_of(ITEM, "stew")), HATED)
        for tag in stew.preference_tags:
            profile.tags[tag] = Taste(leaning=90)
        self.assertEqual(world.talk.reaction(world, raul, subject_of(ITEM, "stew")), LOVED)
        self.assertEqual(world.talk.reaction(world, raul, subject_of(ITEM, "no_such_thing")), NEUTRAL)

    def test_a_word_is_a_taste_like_any_other_and_is_found_out_by_being_talked_of(self) -> None:
        world = _quiet_world()
        marta, raul = _side_by_side(world, "marta", "raul")
        world.add_word("insults", "zopenco")
        _likes(world, raul, ZOPENCO, -90)
        key = key_of(TAG, world.talk.tag_of(ZOPENCO))
        self.assertEqual(world.tastes.found_out(world, raul), [])
        shows = world.registries.talk.shows
        suspected = world.registries.tastes.suspected_at
        for _ in range(int(suspected / shows + 0.999)):
            world.talk.taken(world, raul, marta, subject_of(WORD, ZOPENCO))
        self.assertEqual(world.tastes.found_out(world, raul), [(key, SUSPECTED, DISLIKED)])
        self.assertEqual(world.tastes.found_out(world, raul, "marta"), [(key, SUSPECTED, DISLIKED)], "she was there")
        self.assertEqual(world.tastes.found_out(world, raul, "ines"), [])
        self.assertEqual(world.tastes.label(world, key), '"zopenco"')
        for _ in range(int(world.registries.tastes.known_at / shows + 0.999)):
            world.talk.taken(world, raul, marta, subject_of(WORD, ZOPENCO))
        self.assertEqual(world.tastes.found_out(world, raul), [(key, KNOWN, HATED)])
        found = [line for line in world.event_log if "| taste_found_out |" in line]
        self.assertTrue(any('"zopenco"' in line for line in found), found)

    def test_what_whoever_brought_it_up_makes_of_it_shows_too(self) -> None:
        world = _quiet_world()
        marta, raul = _side_by_side(world, "marta", "raul")
        world.add_word("insults", "zopenco")
        _likes(world, marta, ZOPENCO, 90)
        _likes(world, raul, ZOPENCO, 0)
        key = key_of(TAG, world.talk.tag_of(ZOPENCO))
        for _ in range(2):
            world.talk.brought_up(world, marta, raul, subject_of(WORD, ZOPENCO))
        self.assertEqual(world.tastes.found_out(world, marta, "raul"), [(key, SUSPECTED, LIKED)])


class ToldTests(unittest.TestCase):
    def setUp(self) -> None:
        self.world = _quiet_world()
        self.marta, self.raul = _side_by_side(self.world, "marta", "raul")
        self.world.add_word("insults", "zopenco")

    def test_told_what_to_talk_about_they_go_and_bring_it_up(self) -> None:
        world = self.world
        self.marta.activity = None
        result = world.apply_command(TalkAboutCommand("marta", "raul", subject_of(WORD, ZOPENCO)))
        self.assertTrue(result.ok, result.message)
        self.assertIn('"zopenco"', result.message)
        self.assertEqual(world.words.told, {"marta": ("raul", subject_of(WORD, ZOPENCO))})
        self.assertEqual(self.marta.activity.partner_id, "raul")
        seen = None
        for _ in range(200):
            world.step(1)
            if self.marta.activity is not None and self.marta.activity.about:
                seen = self.marta.activity.about
                break
        self.assertEqual(seen, subject_of(WORD, ZOPENCO))

    def test_a_subject_can_be_made_up_on_the_spot_and_joins_a_list(self) -> None:
        world = self.world
        result = world.apply_command(TalkAboutCommand("marta", "raul", text="el fin del mundo"))
        self.assertTrue(result.ok, result.message)
        new = "subjects.el_fin_del_mundo"
        self.assertEqual(world.words.told["marta"], ("raul", subject_of(WORD, new)))
        self.assertEqual(world.talk.find_word(world, new)[1].by, "marta")
        # One that is there already is used as it is, and one for another list goes there.
        self.assertTrue(world.talk_about("ines", "raul", text="El fin del mundo").ok)
        self.assertEqual(len(world.talk.words(world, "subjects")), 1)
        self.assertTrue(world.talk_about("ines", "raul", text="los perros", list_id="dangers").ok)
        self.assertEqual(world.words.told["ines"], ("raul", subject_of(WORD, "dangers.los_perros")))

    def test_what_cannot_be_talked_of_is_refused(self) -> None:
        world = self.world
        for arguments in (
            ("marta", "marta", subject_of(WORD, ZOPENCO)),
            ("marta", "nobody", subject_of(WORD, ZOPENCO)),
            ("marta", "raul", subject_of(WORD, "insults.no_such_word")),
            ("marta", "raul", subject_of(ITEM, "no_such_thing")),
            ("marta", "raul", "nonsense"),
            ("marta", "raul", None),
        ):
            self.assertFalse(world.talk_about(*arguments).ok, arguments)
        self.assertEqual(world.words.told, {})

    def test_told_while_they_cannot_go_it_keeps_for_the_next_time_they_talk(self) -> None:
        world = self.world
        _settings(world, order="")
        result = world.talk_about("marta", "raul", subject_of(WORD, ZOPENCO))
        self.assertTrue(result.ok)
        self.assertIn("la próxima vez", result.message)
        # With somebody else it is not brought up, and it keeps.
        ines = world.residents["ines"]
        _likes(world, self.marta, ZOPENCO, -90)
        world.add_word("places", "el Viejo Madrid")
        _likes(world, self.marta, "places.el_viejo_madrid", 90)
        self.assertEqual(world.talk.pick(world, self.marta, ines)[0], subject_of(WORD, "places.el_viejo_madrid"))
        self.assertIn("marta", world.words.told)
        self.assertEqual(world.talk.pick(world, self.marta, self.raul)[0], subject_of(WORD, ZOPENCO))
        self.assertEqual(world.words.told, {})


class AskTests(unittest.TestCase):
    def setUp(self) -> None:
        self.world = _quiet_world()
        _settings(self.world, ask_chance=1.0)

    def _to_the_hour(self) -> None:
        world = self.world
        hour = world.registries.talk.ask_hour
        while not (world.clock.hour == hour and world.clock.minute == 0):
            world.clock.advance_minutes(1)
        world.talk.tick(world)

    def test_residents_ask_for_words_at_their_hour_and_only_so_many_wait(self) -> None:
        world = self.world
        world.talk.tick(world)
        self.assertEqual(world.words.asks, [])
        self._to_the_hour()
        asks = world.words.asks
        self.assertEqual(len(asks), world.registries.talk.most_asks)
        self.assertEqual(len({ask.resident_id for ask in asks}), len(asks), "one each")
        self.assertEqual(len({ask.ask_id for ask in asks}), len(asks))
        self.assertTrue(all(ask.kind in (ASK_WORD, ASK_PHRASE) for ask in asks), "nobody feels anything for anybody yet")
        self.assertEqual(_types(world).count(ASKED_EVENT), len(asks))
        self.assertTrue(all(world.talk.question(world, ask) for ask in asks))

    def test_asking_throws_none_of_the_settlements_dice(self) -> None:
        world = self.world
        before = world.rng.get_state()
        self._to_the_hour()
        self.assertTrue(world.words.asks)
        self.assertEqual(world.rng.get_state(), before)

    def test_nobody_asks_where_the_chance_is_none(self) -> None:
        _settings(self.world, ask_chance=0.0)
        self._to_the_hour()
        self.assertEqual(self.world.words.asks, [])

    def test_what_waits_too_long_is_let_go(self) -> None:
        world = self.world
        self._to_the_hour()
        self.assertTrue(world.words.asks)
        _settings(world, ask_chance=0.0)
        lapse = world.registries.talk.lapse_hours
        for _ in range(lapse - 1):
            world.clock.advance_minutes(60)
            world.talk.tick(world)
        self.assertTrue(world.words.asks)
        world.clock.advance_minutes(60)
        world.talk.tick(world)
        self.assertEqual(world.words.asks, [])

    def _ask(self, kind: str, what: str, resident_id: str = "marta") -> Ask:
        ask = Ask(f"ask_{len(self.world.words.asks) + 1}", resident_id, kind, what, self.world.clock.total_minutes)
        self.world.words.asks.append(ask)
        return ask

    def test_a_word_asked_for_goes_into_the_list_as_theirs(self) -> None:
        world = self.world
        ask = self._ask(ASK_WORD, "insults")
        self.assertEqual(world.talk.question(world, ask), world.registries.talk.lists["insults"].ask)
        self.assertFalse(world.apply_command(AnswerAskCommand(ask.ask_id, "")).ok)
        self.assertEqual(world.words.asks, [ask], "it goes on waiting")
        self.assertTrue(world.apply_command(AnswerAskCommand(ask.ask_id, "zopenco")).ok)
        self.assertEqual(world.words.asks, [])
        self.assertEqual(world.talk.find_word(world, ZOPENCO)[1].by, "marta")
        self.assertFalse(world.apply_command(AnswerAskCommand(ask.ask_id, "memo")).ok, "nobody is asking any more")

    def test_a_phrase_and_a_name_asked_for_are_theirs(self) -> None:
        world = self.world
        phrase, name = self._ask(ASK_PHRASE, "catchphrase"), self._ask(ASK_NICKNAME, "raul")
        self.assertEqual(world.talk.question(world, name), "¿Cómo llamo a Raúl?")
        self.assertFalse(world.answer_ask(phrase.ask_id, "  ").ok)
        self.assertFalse(world.answer_ask(name.ask_id, "").ok)
        self.assertTrue(world.answer_ask(phrase.ask_id, "¡Cáspita!").ok)
        self.assertTrue(world.answer_ask(name.ask_id, "el Rulas").ok)
        self.assertEqual(world.talk.phrase(world, "marta", "catchphrase"), "¡Cáspita!")
        self.assertEqual(world.talk.nickname(world, "marta", "raul"), "el Rulas")
        self.assertEqual(world.words.asks, [])

    def test_asked_what_to_talk_about_the_answer_is_a_subject_or_a_new_one(self) -> None:
        world = self.world
        world.add_word("insults", "zopenco")
        ask = self._ask(ASK_SUBJECT, "raul")
        self.assertEqual(world.talk.question(world, ask), "¿De qué hablo con Raúl?")
        self.assertFalse(world.answer_ask(ask.ask_id).ok)
        self.assertTrue(world.apply_command(AnswerAskCommand(ask.ask_id, subject=subject_of(WORD, ZOPENCO))).ok)
        self.assertEqual(world.words.told["marta"], ("raul", subject_of(WORD, ZOPENCO)))
        again = self._ask(ASK_SUBJECT, "raul", "ines")
        self.assertTrue(world.answer_ask(again.ask_id, text="las nubes", list_id="subjects").ok)
        self.assertEqual(world.words.told["ines"], ("raul", subject_of(WORD, "subjects.las_nubes")))

    def test_an_ask_can_be_left_unanswered(self) -> None:
        world = self.world
        ask = self._ask(ASK_WORD, "insults")
        self.assertTrue(world.apply_command(DismissAskCommand(ask.ask_id)).ok)
        self.assertEqual(world.words.asks, [])
        self.assertFalse(world.dismiss_ask(ask.ask_id).ok)

    def test_they_come_to_wonder_what_to_talk_about_with_somebody_they_like(self) -> None:
        world = self.world
        talk = world.registries.talk
        for phrase_id in talk.phrases:
            world.set_phrase("marta", phrase_id, "algo")
        _settings(world, lists={})
        world.relationship("marta", "raul").affection = talk.subject_from
        world.relationship("marta", "ines").resentment = talk.nickname_from
        wanted = set()
        for day in range(40):
            dice = SimulationRNG.keyed(world.rng.seed, "ask", "marta", day)
            wanted.add(world.talk._wants(world, world.residents["marta"], dice))
        self.assertEqual(wanted, {(ASK_SUBJECT, "raul"), (ASK_NICKNAME, "ines")})
        world.set_nickname("marta", "ines", "la Sargento")
        self.assertEqual(
            {world.talk._wants(world, world.residents["marta"], SimulationRNG.keyed(1, "x", day)) for day in range(10)},
            {(ASK_SUBJECT, "raul")},
        )


class SayingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.world = _quiet_world()
        self.marta, self.raul = _side_by_side(self.world, "marta", "raul")
        _settings(self.world, say_chance=1.0)

    def _talking(self) -> None:
        world = self.world
        world.add_word("insults", "zopenco")
        world.words.told["marta"] = ("raul", subject_of(WORD, ZOPENCO))
        self.marta.activity = SocialSystem().pursue(world, self.marta, self.raul, "chat")
        world.step(1)
        self.assertTrue(self.marta.activity.using)

    def test_whoever_has_none_says_nothing_of_their_own(self) -> None:
        self._talking()
        self.assertEqual(self.world.talk.saying(self.world, self.marta), "")

    def test_they_greet_as_a_talk_begins(self) -> None:
        world = self.world
        world.set_phrase("marta", "greeting", "¡Buenas!")
        self.assertEqual(world.talk.saying(world, self.marta), "", "there is nobody to greet")
        self._talking()
        self.assertEqual(world.talk.saying(world, self.marta), "¡Buenas!")
        self.assertEqual(world.talk.shown(world, self.marta), Shown(text="¡Buenas!"))
        self.assertEqual(world.talk.saying(world, self.raul), "")
        self.marta.activity.began_at -= world.registries.talk.greet_minutes
        self.assertEqual(world.talk.saying(world, self.marta), "")

    def test_what_comes_out_goes_by_how_they_are(self) -> None:
        world = self.world
        talk = world.registries.talk
        for phrase_id in ("catchphrase", "glad", "low", "angry"):
            world.set_phrase("marta", phrase_id, phrase_id)
        while world.clock.total_minutes % talk.alone_every:
            world.clock.advance_minutes(1)
        self.marta.mood = 50
        self.assertEqual(world.talk.saying(world, self.marta), "catchphrase")
        self.marta.mood = talk.glad_from
        self.assertEqual(world.talk.saying(world, self.marta), "glad")
        self.marta.mood = talk.low_below - 1
        self.assertEqual(world.talk.saying(world, self.marta), "low")
        self.marta.needs.stress = talk.angry_from
        self.assertEqual(world.talk.saying(world, self.marta), "angry")
        # It is seen for a moment, and then not until the next time.
        world.clock.advance_minutes(talk.say_minutes)
        self.assertEqual(world.talk.saying(world, self.marta), "")

    def test_it_does_not_come_out_every_time_and_never_from_somebody_asleep(self) -> None:
        world = self.world
        _settings(world, say_chance=0.3)
        talk = world.registries.talk
        world.set_phrase("marta", "catchphrase", "¡Cáspita!")
        said = 0
        for _ in range(200):
            world.clock.advance_minutes(talk.alone_every)
            said += bool(world.talk.saying(world, self.marta))
        self.assertTrue(30 < said < 90, said)
        _settings(world, say_chance=1.0)
        self.assertEqual(world.talk.saying(world, self.marta), "¡Cáspita!")
        self.marta.activity = Activity(SLEEP_ROUGH_ACTION, minutes_left=60, using=True)
        self.assertFalse(world.is_aware(self.marta))
        self.assertEqual(world.talk.saying(world, self.marta), "")

    def test_what_is_seen_over_them_is_the_thing_the_face_or_the_words(self) -> None:
        world = self.world
        self.assertIsNone(world.talk.shown(world, self.marta), "nobody is talking")
        self._talking()
        self.assertEqual(world.talk.shown(world, self.marta), Shown(text=self.marta.activity.about_text))
        self.assertEqual(world.talk.shown(world, self.raul), Shown(text=self.marta.activity.about_text))
        for activity in (self.marta.activity, self.raul.activity):
            activity.about = subject_of(ITEM, "stew")
        self.assertEqual(world.talk.shown(world, self.raul), Shown(item_id="stew"))
        for activity in (self.marta.activity, self.raul.activity):
            activity.about = subject_of(PERSON, "ines")
        self.assertEqual(world.talk.shown(world, self.marta), Shown(face_id="ines"))
        fact = world.emit_event(DomainEvent("found", 40, "Inés encuentra algo", ["ines"]), fact_text="Inés encontró un tesoro")
        self.marta.activity.about = subject_of(FACT, fact.fact_id)
        self.assertEqual(world.talk.shown(world, self.marta), Shown(face_id="ines"), "the face of whoever it is about")


class SaveTests(unittest.TestCase):
    def test_the_words_and_what_a_talk_is_about_are_saved_and_go_on_the_same(self) -> None:
        manager = SaveManager()
        world = SimulationWorld.demo_world(seed=5)
        world.add_word("insults", "zopenco")
        world.add_word("gossip", "el tendero se tiñe el pelo")
        world.set_phrase("marta", "greeting", "¡Buenas!")
        world.set_nickname("marta", "raul", "el Rulas")
        world.words.told["ines"] = ("raul", subject_of(WORD, ZOPENCO))
        world.words.asks.append(Ask("ask_9", "marta", ASK_WORD, "places", 30))
        world.words.ask_count = 9
        for _ in range(3 * MINUTES_PER_DAY):
            world.step(1)
            if any(each.activity is not None and each.activity.about for each in world.residents.values()):
                break
        talking = [each for each in world.residents.values() if each.activity is not None and each.activity.about]
        self.assertTrue(talking)
        data = manager.to_data(world)
        self.assertEqual(data["version"], manager.CURRENT_VERSION)
        self.assertGreaterEqual(manager.CURRENT_VERSION, 49)
        loaded = manager.from_data(json.loads(json.dumps(data)))
        self.assertEqual(loaded.words, world.words)
        for resident in talking:
            mine, theirs = resident.activity, loaded.residents[resident.resident_id].activity
            self.assertEqual(
                (theirs.about, theirs.about_text, theirs.brought, theirs.began_at),
                (mine.about, mine.about_text, mine.brought, mine.began_at),
            )
        for each in (world, loaded):
            each.step(2 * MINUTES_PER_DAY)
        self.assertEqual(manager.to_data(loaded), manager.to_data(world))

    def test_a_save_from_before_has_no_words_and_one_that_is_damaged_keeps_what_it_can(self) -> None:
        manager = SaveManager()
        world = SimulationWorld.demo_world()
        world.add_word("insults", "zopenco")
        world.step(MINUTES_PER_DAY)
        data = manager.to_data(world)
        del data["words"]
        data["version"] = 48
        for resident in data["residents"]:
            for key in ("about", "about_text", "brought", "began_at"):
                (resident.get("activity") or {}).pop(key, None)
        loaded = manager.from_data(data)
        self.assertEqual(loaded.words.lists, {})
        self.assertEqual(loaded.words.asks, [])
        loaded.step(MINUTES_PER_DAY)
        broken = manager.to_data(world)
        broken["words"] = {
            "lists": {"insults": [{"word_id": ZOPENCO, "text": "zopenco", "day": "soon"}, {"text": "memo"}, "x"], "odd": 3},
            "phrases": {"marta": {"greeting": "¡Buenas!", "glad": 7}, "raul": "x"},
            "nicknames": [],
            "asks": [{"ask_id": "ask_1", "resident_id": "marta", "kind": "favour", "what": "x"}, {"ask_id": "ask_2"}, 5],
            "ask_count": "many",
            "told": {"marta": ["raul"], "ines": ["raul", subject_of(WORD, ZOPENCO)]},
        }
        loaded = manager.from_data(broken)
        self.assertEqual([(word.word_id, word.day) for word in loaded.words.lists["insults"]], [(ZOPENCO, 0)])
        self.assertEqual(loaded.words.phrases, {"marta": {"greeting": "¡Buenas!"}})
        self.assertEqual((loaded.words.nicknames, loaded.words.asks, loaded.words.ask_count), ({}, [], 0))
        self.assertEqual(loaded.words.told, {"ines": ("raul", subject_of(WORD, ZOPENCO))})


if __name__ == "__main__":
    unittest.main()
