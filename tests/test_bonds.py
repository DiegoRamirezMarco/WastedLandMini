import json
import unittest

from save.save_manager import SaveManager
from simulation.commands import ChooseOptionCommand
from simulation.events.event import euphonic
from simulation.events.intervention_system import BREAKUP, CONFESSION
from simulation.knowledge.fact import SOURCE_TOLD
from simulation.knowledge.knowledge_system import learn, share_rumor
from simulation.residents.activity import Activity
from simulation.residents.needs import Needs
from simulation.residents.resident import Resident
from simulation.social.bonds import AFFAIR_EVENT, TRYST, TRYST_ACTION, bond_settings_from_data, spark
from simulation.social.social_system import SocialSystem, feeling_changes
from simulation.tastes.taste import Taste
from simulation.world import SimulationWorld

MINUTES_PER_DAY = 24 * 60
# Two tiles of open ground side by side, out of sight of the dormitory.
HERE, BESIDE, NEARBY = (20, 18), (21, 18), (23, 19)
INDOORS = (5, 5)


def _types(world: SimulationWorld) -> list[str]:
    return [line.split(" | ")[1] for line in world.event_log]


def _stand(resident: Resident, tile: tuple[int, int]) -> None:
    """Put a resident on a tile with nothing on their mind, and keep them there."""
    resident.x, resident.y = tile
    resident.needs = Needs(hunger=0, tiredness=0, social=0, stress=0)
    resident.activity = Activity("wander", minutes_left=6000, using=True)


def _quiet_world() -> SimulationWorld:
    """The demo settlement with no feelings between anyone and everybody shut indoors, awake."""
    world = SimulationWorld.demo_world()
    world.relationships.clear()
    for resident in world.residents.values():
        resident.job_id = resident.post_id = None
        _stand(resident, INDOORS)
    return world


def _feel(world: SimulationWorld, source_id: str, target_id: str, **feelings: float) -> None:
    for feeling, value in feelings.items():
        setattr(world.relationship(source_id, target_id), feeling, value)


def _couple(world: SimulationWorld, a_id: str, b_id: str) -> None:
    world.residents[a_id].couple_with, world.residents[b_id].couple_with = b_id, a_id
    for one, other in ((a_id, b_id), (b_id, a_id)):
        _feel(world, one, other, affection=50, trust=40, attraction=60)


def _side_by_side(world: SimulationWorld, a_id: str, b_id: str) -> tuple[Resident, Resident]:
    a, b = world.residents[a_id], world.residents[b_id]
    _stand(a, HERE)
    _stand(b, BESIDE)
    return a, b


def _seek(world: SimulationWorld, a: Resident, b: Resident, exchange: str) -> None:
    a.activity = SocialSystem().pursue(world, a, b, exchange)


def _run_exchange(world: SimulationWorld, a: Resident, exchange: str, limit: int = 200) -> bool:
    """Let time pass until `a` has had the exchange and is done with it. False if it never started."""
    started = False
    for _ in range(limit):
        world.step(1)
        for resident in world.residents.values():
            resident.needs = Needs(hunger=0, tiredness=0, social=0, stress=resident.needs.stress)
        in_it = a.activity is not None and a.activity.action == exchange and a.activity.using
        started = started or in_it
        if started and not in_it:
            return True
        if not started and a.activity is None:
            return False
    return started


class FriendshipTests(unittest.TestCase):
    def setUp(self) -> None:
        self.world = _quiet_world()
        self.marta, self.raul = self.world.residents["marta"], self.world.residents["raul"]

    def _tier(self, source_id: str, target_id: str) -> str | None:
        tier = self.world.bonds.tier(self.world, self.world.relationship(source_id, target_id))
        return tier.tier_id if tier is not None else None

    def test_friendship_has_degrees_and_runs_one_way(self) -> None:
        self.assertIsNone(self._tier("marta", "raul"))
        _feel(self.world, "marta", "raul", affection=35, trust=12)
        self.assertEqual(self._tier("marta", "raul"), "friend")
        _feel(self.world, "marta", "raul", affection=70, trust=35)
        self.assertEqual(self._tier("marta", "raul"), "close_friend")
        _feel(self.world, "marta", "raul", affection=70, trust=5)
        self.assertIsNone(self._tier("marta", "raul"), "fondness without trust is not friendship")
        self.assertIsNone(self._tier("raul", "marta"), "what he feels is another matter")

    def test_growing_into_a_friendship_or_out_of_it_is_said_once(self) -> None:
        _feel(self.world, "marta", "raul", affection=35, trust=12)
        for _ in range(3):
            self.world.bonds.update_friendship(self.world, self.marta, self.raul)
        self.assertEqual(_types(self.world).count("friendship_changed"), 1)
        self.assertIn("Marta siente ya por Raúl una amistad", self.world.event_log[-1])
        self.assertEqual(self.world.relationship("marta", "raul").bond, "friend")
        self.assertEqual(self.world.relationship("raul", "marta").bond, "")
        _feel(self.world, "marta", "raul", affection=10)
        self.world.bonds.update_friendship(self.world, self.marta, self.raul)
        self.assertIn("Marta ya no siente por Raúl una amistad", self.world.event_log[-1])
        self.assertEqual(self.world.relationship("marta", "raul").bond, "")

    def test_a_chat_can_tip_two_people_into_friendship(self) -> None:
        a, b = _side_by_side(self.world, "marta", "raul")
        for one, other in (("marta", "raul"), ("raul", "marta")):
            _feel(self.world, one, other, affection=29.5, trust=12)
        _seek(self.world, a, b, "chat")
        self.assertTrue(_run_exchange(self.world, a, "chat"))
        self.assertEqual(self.world.relationship("marta", "raul").bond, "friend")
        self.assertIn("friendship_changed", _types(self.world))

    def test_tiers_must_be_listed_from_the_least_and_romance_is_for_adults(self) -> None:
        with self.assertRaisesRegex(ValueError, "least to the closest"):
            bond_settings_from_data(
                {"friendship": [{"id": "close", "affection": 60}, {"id": "friend", "affection": 30}]}
            )
        with self.assertRaisesRegex(ValueError, "adults"):
            bond_settings_from_data({"adult_age": 16})
        self.assertEqual(bond_settings_from_data({}).adult_age, 18)


class AttractionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.world = _quiet_world()
        self.tomas, self.ines = self.world.residents["tomas"], self.world.residents["ines"]
        self.chat = self.world.registries.interactions["chat"]

    def test_a_spark_is_fixed_by_who_the_two_are_and_many_pairs_have_none(self) -> None:
        ids = list(self.world.residents)
        sparks = {(a, b): spark(a, b) for a in ids for b in ids if a != b}
        self.assertEqual(sparks, {(a, b): spark(a, b) for a in ids for b in ids if a != b})
        self.assertTrue(all(0.0 <= value <= 1.0 for value in sparks.values()))
        self.assertTrue(any(value == 0.0 for value in sparks.values()))
        self.assertTrue(any(value > 0.3 for value in sparks.values()))
        self.assertTrue(any(sparks[(a, b)] != sparks[(b, a)] for a, b in sparks))

    def test_attraction_only_grows_where_there_is_something_to_grow_from(self) -> None:
        feelings = self.world.relationship("tomas", "ines")
        self.assertNotIn(0.0, [feeling_changes(self.chat, self.tomas, self.ines, feelings)["affection"]])
        self.assertEqual(feeling_changes(self.chat, self.tomas, self.ines, feelings)["attraction"], 0.0)
        grown = feeling_changes(self.chat, self.tomas, self.ines, feelings, attraction_rate=0.5)["attraction"]
        self.assertGreater(grown, 0.0)
        feelings.attraction = 80
        self.assertLess(feeling_changes(self.chat, self.tomas, self.ines, feelings, 0.5)["attraction"], grown)
        argument = self.world.registries.interactions["argument"]
        self.assertLess(feeling_changes(argument, self.tomas, self.ines, feelings, 0.5)["attraction"], 0.0)

    def test_what_is_already_felt_keeps_growing_and_a_partner_slows_it_for_anyone_else(self) -> None:
        rate = self.world.bonds.attraction_rate
        _feel(self.world, "tomas", "ines", attraction=40)
        self.assertGreaterEqual(rate(self.world, self.tomas, self.ines), 0.4)
        free = rate(self.world, self.tomas, self.ines)
        self.tomas.couple_with = "vera"
        self.assertAlmostEqual(rate(self.world, self.tomas, self.ines), free * 0.3)
        self.tomas.couple_with = "ines"
        self.assertEqual(rate(self.world, self.tomas, self.ines), free)

    def test_there_is_no_romance_with_or_for_anyone_who_is_not_an_adult(self) -> None:
        _couple(self.world, "tomas", "ines")
        self.ines.age = 17
        self.world.clock.hour = 22
        self.assertEqual(self.world.bonds.attraction_rate(self.world, self.tomas, self.ines), 0.0)
        self.assertEqual(self.world.bonds.attraction_rate(self.world, self.ines, self.tomas), 0.0)
        self.assertEqual(self.world.bonds.candidates(self.world, self.tomas), [])
        self.assertEqual(self.world.bonds.candidates(self.world, self.ines), [])
        self.tomas.couple_with = self.ines.couple_with = None
        self.assertIsNone(self.world.bonds.confession_target(self.world, self.tomas))
        self.assertIsNone(self.world.bonds.confession_target(self.world, self.ines))
        a, b = _side_by_side(self.world, "tomas", "ines")
        self.assertFalse(self.world.bonds.may_begin(self.world, a, b, self.world.registries.interactions[TRYST]))


class ConfessionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.world = _quiet_world()
        self.tomas, self.ines = _side_by_side(self.world, "tomas", "ines")
        _feel(self.world, "tomas", "ines", attraction=50, affection=40)

    def _open(self):
        self.tomas.activity = self.world.interventions.maybe_romance(self.world, self.tomas)
        return next(iter(self.world.decisions.values()), None)

    def test_it_takes_both_attraction_and_fondness_and_two_people_who_are_free(self) -> None:
        target = self.world.bonds.confession_target
        self.assertIs(target(self.world, self.tomas), self.ines)
        self.assertIsNone(target(self.world, self.ines), "she has not got that far")
        _feel(self.world, "tomas", "ines", affection=20)
        self.assertIsNone(target(self.world, self.tomas))
        _feel(self.world, "tomas", "ines", affection=40)
        self.ines.couple_with = "raul"
        self.assertIsNone(target(self.world, self.tomas))

    def test_saying_it_is_a_decision_the_player_can_weigh_in_on(self) -> None:
        self.tomas.personality.courage = 5
        self.tomas.personality.impulsiveness = 20
        decision = self._open()
        self.assertEqual((decision.kind, decision.resident_id, decision.crisis.target_id), (CONFESSION, "tomas", "ines"))
        self.assertIn("Inés", decision.prompt)
        self.assertIn("feelings_stirring", _types(self.world))
        self.assertEqual(self.world.interventions.resolve(self.world, decision.decision_id, None), "keep_quiet")
        self.assertIsNone(self.tomas.activity)
        self.assertIsNone(self._open(), "not again so soon")

        self.setUp()
        self.tomas.personality.courage = 5
        self.tomas.personality.impulsiveness = 20
        decision = self._open()
        outcome = self.world.apply_command(ChooseOptionCommand(decision.decision_id, "encourage"))
        self.assertEqual(outcome, "confess")
        self.assertEqual((self.tomas.activity.partner_id, self.tomas.activity.intent), ("ines", "confession"))

    def test_they_are_a_couple_only_if_the_one_told_feels_the_same(self) -> None:
        _seek(self.world, self.tomas, self.ines, "confession")
        self.assertTrue(_run_exchange(self.world, self.tomas, "confession"))
        self.assertEqual((self.tomas.couple_with, self.ines.couple_with), (None, None))
        self.assertIn("confession_rejected", _types(self.world))
        self.assertTrue(any("Inés no siente lo mismo por Tomás" in line for line in self.world.event_log))
        self.assertLess(self.world.relationship("tomas", "ines").attraction, 50)
        self.assertGreater(self.tomas.needs.stress, 10)

        self.setUp()
        _feel(self.world, "ines", "tomas", attraction=40, affection=30)
        _seek(self.world, self.tomas, self.ines, "confession")
        self.assertTrue(_run_exchange(self.world, self.tomas, "confession"))
        self.assertEqual((self.tomas.couple_with, self.ines.couple_with), ("ines", "tomas"))
        self.assertEqual(_types(self.world).count("couple_formed"), 1)
        self.assertTrue(any("Tomás e Inés están juntos" in line for line in self.world.event_log))
        for resident_id in ("tomas", "ines"):
            self.assertTrue(any("estamos juntos" in m.text for m in self.world.memories.of(resident_id)))

    def test_names_are_joined_as_spanish_joins_them(self) -> None:
        self.assertEqual(euphonic("Tomás y Inés charlan"), "Tomás e Inés charlan")
        self.assertEqual(euphonic("Inés y Tomás charlan"), "Inés y Tomás charlan")
        self.assertEqual(euphonic("hoy Inés no trabaja"), "hoy Inés no trabaja")


class TimeAloneTests(unittest.TestCase):
    def setUp(self) -> None:
        self.world = _quiet_world()
        self.world.clock.hour = 22
        self.tomas, self.ines = _side_by_side(self.world, "tomas", "ines")
        _couple(self.world, "tomas", "ines")

    def _wants(self, resident: Resident) -> list[str]:
        return [c.partner_id for c in self.world.bonds.candidates(self.world, resident) if c.name == TRYST_ACTION]

    def test_a_couple_seek_each_other_out_at_night_and_not_every_night(self) -> None:
        self.assertEqual(self._wants(self.tomas), ["ines"])
        self.world.clock.hour = 12
        self.assertEqual(self._wants(self.tomas), [])
        self.world.clock.hour = 22
        self.world.relationship("tomas", "ines").last_together = self.world.clock.total_minutes - 60
        self.assertEqual(self._wants(self.tomas), [])
        self.world.relationship("tomas", "ines").last_together = None
        self.tomas.needs.tiredness = 90
        self.assertEqual(self._wants(self.tomas), [], "not when dead on their feet")

    def test_two_who_are_free_say_what_they_feel_before_anything_else(self) -> None:
        self.tomas.couple_with = self.ines.couple_with = None
        self.assertEqual(self._wants(self.tomas), [])

    def test_it_happens_only_if_both_want_it(self) -> None:
        _feel(self.world, "ines", "tomas", attraction=10)
        _seek(self.world, self.tomas, self.ines, TRYST)
        self.assertFalse(_run_exchange(self.world, self.tomas, TRYST, limit=10))
        self.assertNotIn("tryst_started", _types(self.world))
        self.assertIsNone(self.tomas.activity, "he takes no for an answer")
        self.assertEqual(self._wants(self.tomas), [], "and does not ask again tonight")

    def test_they_wait_for_a_moment_when_nobody_is_looking(self) -> None:
        _stand(self.world.residents["raul"], NEARBY)
        _seek(self.world, self.tomas, self.ines, TRYST)
        self.world.step(5)
        self.assertNotIn("tryst_started", _types(self.world))
        _stand(self.world.residents["raul"], INDOORS)
        self.assertTrue(_run_exchange(self.world, self.tomas, TRYST))
        self.assertEqual(_types(self.world).count("tryst_started"), 1)
        self.assertTrue(any("Tomás e Inés se pierden un rato a solas" in line for line in self.world.event_log))

    def test_only_the_two_know_of_it_unless_someone_comes_across_them(self) -> None:
        _seek(self.world, self.tomas, self.ines, TRYST)
        self.world.step(3)
        self.assertEqual(self.tomas.activity.action, TRYST)
        fact = next(f for f in self.world.knowledge.facts.values() if f.event_type == "tryst_started")
        knowers = [rid for rid in self.world.residents if self.world.knowledge.knows(rid, fact.fact_id)]
        self.assertEqual(sorted(knowers), ["ines", "tomas"])
        _stand(self.world.residents["lucia"], NEARBY)
        self.world.step(1)
        self.assertTrue(self.world.knowledge.knows("lucia", fact.fact_id))
        self.assertFalse(self.world.knowledge.knows("raul", fact.fact_id))
        before = self.world.relationship("tomas", "ines").affection
        self.assertTrue(_run_exchange(self.world, self.tomas, TRYST))
        self.assertGreater(self.world.relationship("tomas", "ines").affection, before)
        self.assertTrue(any("a solas con Inés" in m.text for m in self.world.memories.of("tomas")))


class JealousyAndSecretsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.world = _quiet_world()
        self.world.clock.hour = 22
        self.tomas, self.ines = _side_by_side(self.world, "tomas", "ines")
        self.vera, self.lucia = self.world.residents["vera"], self.world.residents["lucia"]
        # Tomás is with Vera, and drawn to Inés, who is drawn to him.
        _couple(self.world, "tomas", "vera")
        _feel(self.world, "tomas", "ines", attraction=70, affection=40)
        _feel(self.world, "ines", "tomas", attraction=70, affection=40)
        self.tomas.personality.empathy = 30

    def _affair(self):
        _seek(self.world, self.tomas, self.ines, TRYST)
        self.assertTrue(_run_exchange(self.world, self.tomas, TRYST))
        return next(f for f in self.world.knowledge.facts.values() if f.event_type == AFFAIR_EVENT)

    def test_only_the_heartless_and_the_smitten_go_behind_a_partners_back(self) -> None:
        def wants() -> list[str]:
            return sorted(c.partner_id for c in self.world.bonds.candidates(self.world, self.tomas))

        self.assertEqual(wants(), ["ines", "vera"])
        self.tomas.personality.empathy = 75
        self.assertEqual(wants(), ["vera"])
        self.tomas.personality.empathy = 30
        _feel(self.world, "tomas", "ines", attraction=50)
        self.assertEqual(wants(), ["vera"])

    def test_behind_a_partners_back_it_is_an_affair_and_a_secret(self) -> None:
        fact = self._affair()
        self.assertEqual(fact.subject_ids, ["tomas", "ines", "vera"])
        self.assertNotIn("tryst_started", _types(self.world))
        self.assertFalse(self.world.knowledge.knows("vera", fact.fact_id))
        self.assertEqual(self.world.relationship("vera", "tomas").resentment, 0)
        # Neither of the two tells just anyone, however chatty.
        self.tomas.personality.sociability = self.ines.personality.sociability = 100
        for _ in range(40):
            self.assertIsNone(share_rumor(self.world, self.tomas, self.lucia))
            self.assertIsNone(share_rumor(self.world, self.ines, self.lucia))
        self.assertFalse(self.world.knowledge.knows("lucia", fact.fact_id))

    def test_a_secret_is_told_to_a_close_friend_and_never_to_whoever_it_was_kept_from(self) -> None:
        fact = self._affair()
        self.ines.personality.sociability = self.tomas.personality.sociability = 100
        _feel(self.world, "ines", "lucia", affection=70, trust=40)
        _feel(self.world, "tomas", "vera", affection=80, trust=60)
        self.assertTrue(self.world.bonds.confides_in(self.world, self.ines, self.lucia))
        told = any(share_rumor(self.world, self.ines, self.lucia) is not None for _ in range(40))
        self.assertTrue(told)
        self.assertTrue(self.world.knowledge.knows("lucia", fact.fact_id))
        for _ in range(40):
            share_rumor(self.world, self.tomas, self.vera)
        self.assertFalse(self.world.knowledge.knows("vera", fact.fact_id), "he does not confess it to her")

    def test_whoever_learns_their_partner_was_with_another_turns_on_both(self) -> None:
        fact = self._affair()
        paco = self.world.residents["paco"]
        self.assertTrue(learn(self.world, paco, fact, 1.0, SOURCE_TOLD, told_by="lucia"))
        self.assertGreater(self.world.relationship("paco", "tomas").resentment, 0)
        self.assertEqual(self.world.relationship("paco", "vera").resentment, 0, "it was done to her, not by her")

        calm = self.vera.needs.stress
        self.assertTrue(learn(self.world, self.vera, fact, 1.0, SOURCE_TOLD, told_by="paco"))
        betrayed, rival = self.world.relationship("vera", "tomas"), self.world.relationship("vera", "ines")
        self.assertGreaterEqual(betrayed.resentment, 45)
        self.assertLess(betrayed.trust, 0)
        self.assertGreaterEqual(rival.resentment, 25)
        self.assertGreater(betrayed.resentment, rival.resentment)
        self.assertGreater(self.vera.needs.stress, calm + 15)
        self.assertFalse(learn(self.world, self.vera, fact, 1.0, SOURCE_TOLD, told_by="lucia"), "old news")
        self.assertIs(self.world.bonds.soured_partner(self.world, self.vera), self.tomas)

    def test_it_is_the_partner_who_did_the_wrong_even_when_the_other_made_the_first_move(self) -> None:
        _seek(self.world, self.ines, self.tomas, TRYST)
        self.assertTrue(_run_exchange(self.world, self.ines, TRYST))
        fact = next(f for f in self.world.knowledge.facts.values() if f.event_type == AFFAIR_EVENT)
        self.assertEqual(fact.subject_ids, ["ines", "tomas", "vera"])
        learn(self.world, self.vera, fact, 1.0, SOURCE_TOLD, told_by="paco")
        self.assertGreater(
            self.world.relationship("vera", "tomas").resentment, self.world.relationship("vera", "ines").resentment
        )


class BreakupTests(unittest.TestCase):
    def setUp(self) -> None:
        self.world = _quiet_world()
        self.tomas, self.vera = _side_by_side(self.world, "tomas", "vera")
        _couple(self.world, "tomas", "vera")
        _feel(self.world, "vera", "tomas", resentment=60, affection=10, trust=-20)
        # Someone who makes nothing of being told what to do, so that advice weighs what it weighs.
        self.world.tastes.profile(self.world, self.vera).people["being_told"] = Taste()

    def _open(self):
        self.vera.activity = self.world.interventions.maybe_romance(self.world, self.vera)
        return next(iter(self.world.decisions.values()), None)

    def test_a_couple_that_gets_on_has_nothing_to_decide(self) -> None:
        _feel(self.world, "vera", "tomas", resentment=10)
        self.assertIsNone(self.world.bonds.soured_partner(self.world, self.vera))
        self.assertIsNone(self._open())

    def test_leaving_is_a_decision_and_advice_can_send_it_either_way(self) -> None:
        decision = self._open()
        self.assertEqual((decision.kind, decision.resident_id, decision.crisis.target_id), (BREAKUP, "vera", "tomas"))
        self.assertIn("couple_in_trouble", _types(self.world))
        self.assertEqual([option.option_id for option in decision.options], ["leave", "talk", "neutral", "stay"])
        outcome = self.world.apply_command(ChooseOptionCommand(decision.decision_id, "talk"))
        self.assertEqual(outcome, "talk_it_out")
        self.assertEqual(self.vera.activity.intent, "heart_to_heart")
        self.assertTrue(_run_exchange(self.world, self.vera, "heart_to_heart"))
        self.assertEqual((self.vera.couple_with, self.tomas.couple_with), ("tomas", "vera"))
        self.assertLess(self.world.relationship("vera", "tomas").resentment, 60)

        self.setUp()
        decision = self._open()
        self.assertEqual(self.world.apply_command(ChooseOptionCommand(decision.decision_id, "leave")), "break_up")
        self.assertEqual(self.vera.activity.intent, "breakup")
        self.assertEqual(self.vera.couple_with, "tomas", "not until she has told him")
        self.assertTrue(_run_exchange(self.world, self.vera, "breakup"))
        self.assertEqual((self.vera.couple_with, self.tomas.couple_with), (None, None))
        self.assertEqual(_types(self.world).count("couple_broke_up"), 1)
        self.assertTrue(any("Vera y Tomás ya no están juntos" in line for line in self.world.event_log))
        self.assertTrue(any("rompió conmigo" in m.text for m in self.world.memories.of("tomas")))
        self.assertGreater(self.tomas.needs.stress, self.vera.needs.stress)

    def test_the_same_trouble_ends_differently_for_different_people(self) -> None:
        self.vera.personality.empathy = 90
        _feel(self.world, "vera", "tomas", affection=60)
        forgiving = self.world.interventions.resolve(self.world, self._open().decision_id, None)
        self.setUp()
        self.vera.personality.empathy = 10
        self.vera.personality.impulsiveness = 90
        _feel(self.world, "vera", "tomas", affection=-30, resentment=90)
        bitter = self.world.interventions.resolve(self.world, self._open().decision_id, None)
        self.assertEqual((forgiving, bitter), ("talk_it_out", "break_up"))

    def test_a_death_leaves_the_one_who_stays_on_their_own(self) -> None:
        self.world.health.die(self.world, self.tomas, "una prueba")
        self.assertIsNone(self.vera.couple_with)
        self.world.step(60)


def _smitten_world(seed: int = 3) -> SimulationWorld:
    """The demo settlement with Tomás and Inés already past the point of saying nothing."""
    world = SimulationWorld.demo_world(seed=seed)
    for one, other in (("tomas", "ines"), ("ines", "tomas")):
        _feel(world, one, other, attraction=55, affection=45)
    return world


def _run_until_couple(world: SimulationWorld, limit: int = 6 * MINUTES_PER_DAY) -> None:
    for _ in range(limit):
        world.step(1)
        if world.residents["tomas"].couple_with == "ines":
            return
    raise AssertionError("Tomás and Inés never got together")


class BondsSaveAndWeekTests(unittest.TestCase):
    def setUp(self) -> None:
        self.manager = SaveManager()

    def test_the_settlement_grows_a_couple_by_itself_and_every_step_can_be_seen(self) -> None:
        world = _smitten_world()
        _run_until_couple(world)
        world.step(4 * MINUTES_PER_DAY)
        types = _types(world)
        self.assertIn("couple_formed", types)
        self.assertLess(types.index("feelings_stirring"), types.index("confession_started"))
        self.assertLess(types.index("confession_started"), types.index("couple_formed"))
        self.assertLess(types.index("couple_formed"), types.index("tryst_started"))
        tomas, ines = world.residents["tomas"], world.residents["ines"]
        self.assertEqual((tomas.couple_with, ines.couple_with), ("ines", "tomas"))
        for fact in world.knowledge.facts.values():
            if fact.event_type != "tryst_started":
                continue
            for resident_id in world.residents:
                belief = world.knowledge.belief(resident_id, fact.fact_id)
                if belief is not None and resident_id not in fact.subject_ids:
                    self.assertIn(belief.source, ("witness", "told"), "nobody just knows")
        for resident in world.residents.values():
            for need in ("hunger", "tiredness", "social", "stress"):
                self.assertLess(getattr(resident.needs, need), 100.0, (resident.name, need))

    def test_saving_a_settlement_with_a_couple_continues_exactly_like_not_saving(self) -> None:
        original = _smitten_world()
        _run_until_couple(original)
        original.step(MINUTES_PER_DAY)
        self.assertEqual(original.residents["ines"].couple_with, "tomas")
        loaded = self.manager.from_data(json.loads(json.dumps(self.manager.to_data(original))))
        self.assertEqual(self.manager.to_data(loaded), self.manager.to_data(original))
        self.assertEqual(loaded.residents["tomas"].couple_with, "ines")
        self.assertEqual(loaded.residents["tomas"].age, 45)
        self.assertEqual(
            loaded.relationship("tomas", "ines").last_together, original.relationship("tomas", "ines").last_together
        )
        original.step(2 * MINUTES_PER_DAY)
        loaded.step(2 * MINUTES_PER_DAY)
        self.assertEqual(self.manager.to_data(loaded), self.manager.to_data(original))

    def test_an_older_save_loads_with_everyone_single_and_half_a_couple_is_no_couple(self) -> None:
        world = SimulationWorld.demo_world()
        _couple(world, "tomas", "ines")
        data = self.manager.to_data(world)
        data["version"] = 9
        for resident in data["residents"]:
            del resident["age"], resident["couple_with"]
        for relationship in data["relationships"]:
            del relationship["bond"], relationship["last_together"]
        loaded = self.manager.from_data(json.loads(json.dumps(data)))
        self.assertEqual({r.couple_with for r in loaded.residents.values()}, {None})
        self.assertEqual({r.age for r in loaded.residents.values()}, {30})
        self.assertEqual(loaded.relationship("tomas", "ines").bond, "")
        loaded.step(MINUTES_PER_DAY)

        data = self.manager.to_data(world)
        next(r for r in data["residents"] if r["id"] == "ines")["couple_with"] = None
        self.assertIsNone(self.manager.from_data(data).residents["tomas"].couple_with)
        data = self.manager.to_data(world)
        data["residents"] = [r for r in data["residents"] if r["id"] != "ines"]
        self.assertIsNone(self.manager.from_data(data).residents["tomas"].couple_with)


if __name__ == "__main__":
    unittest.main()
