import tempfile
import unittest
from pathlib import Path

from save.save_manager import SaveManager
from simulation.commands import ChooseOptionCommand
from simulation.events.intervention_system import BROOD_ACTION, anger
from simulation.registries import DATA_DIR, BuiltInRegistries
from simulation.residents.activity import Activity
from simulation.residents.needs import Needs
from simulation.residents.personality import Personality
from simulation.social.social_system import SocialSystem
from simulation.world import SimulationWorld

MINUTES_PER_DAY = 24 * 60


def _open_crisis(world: SimulationWorld):
    """Run until a decision is open and return it."""
    for _ in range(MINUTES_PER_DAY):
        if world.decisions:
            return next(iter(world.decisions.values()))
        world.step(1)
    raise AssertionError("no crisis opened")


def _types(world: SimulationWorld) -> list[str]:
    return [event.event_type for event in world.history]


def _world_with(personality: Personality) -> SimulationWorld:
    """The demo opening, with Raúl given another personality but the same grudge and anger."""
    world = SimulationWorld.demo_world()
    raul = world.residents["raul"]
    raul.personality = personality
    world.relationship("raul", "marta").resentment = 80
    raul.needs.stress = 80
    return world


LEVEL_HEADED = Personality(aggression=20, impulsiveness=20, empathy=50)
HOTHEAD = Personality(aggression=95, impulsiveness=95, empathy=10)


class CrisisOpeningTests(unittest.TestCase):
    def setUp(self) -> None:
        self.world = SimulationWorld.demo_world()
        self.raul = self.world.residents["raul"]

    def test_the_demo_opens_with_raul_asking_for_advice_about_marta(self) -> None:
        decision = _open_crisis(self.world)
        self.assertEqual((decision.resident_id, decision.crisis.target_id), ("raul", "marta"))
        self.assertIn("Marta", decision.prompt)
        self.assertEqual([option.option_id for option in decision.options], ["calm", "talk", "neutral", "provoke"])
        self.assertIn("Habla con Marta", [option.text for option in decision.options])
        self.assertEqual(self.raul.current_action, BROOD_ACTION)
        opened = self.world.history[-1]
        self.assertEqual(opened.event_type, "crisis_opened")
        self.assertGreaterEqual(opened.importance, 50)
        self.assertEqual(opened.participants, ["raul"])
        self.assertGreater(decision.deadline, self.world.clock.total_minutes)

    def test_anger_needs_a_real_grudge_and_grows_with_stress_and_temper(self) -> None:
        marta = self.world.residents["marta"]
        base = anger(self.world, self.raul, marta)
        self.raul.needs.stress = 90
        stressed = anger(self.world, self.raul, marta)
        self.assertGreater(stressed, base)
        self.raul.personality.aggression = 100
        self.assertGreater(anger(self.world, self.raul, marta), stressed)

        lucia = self.world.residents["lucia"]
        lucia.needs.stress = 100
        self.world.relationship("lucia", "marta").resentment = 20
        self.assertIsNone(self.world.interventions.maybe_open(self.world, lucia))

    def test_a_resident_waiting_for_advice_is_left_alone_and_does_not_wander_off(self) -> None:
        _open_crisis(self.world)
        where = self.raul.tile
        marta = self.world.residents["marta"]
        marta.needs.social = 100
        partners = [c.partner_id for c in SocialSystem().candidates(self.world, marta)]
        self.assertNotIn("raul", partners)
        self.world.step(30)
        self.assertEqual((self.raul.tile, self.raul.current_action), (where, BROOD_ACTION))

    def test_there_is_at_most_one_crisis_per_resident_per_day(self) -> None:
        decision = _open_crisis(self.world)
        opened_at = self.world.clock.total_minutes
        self.world.apply_command(ChooseOptionCommand(decision.decision_id, "provoke"))
        for _ in range(MINUTES_PER_DAY - 1):
            self.world.step(1)
            for pending in self.world.decisions.values():
                # They may still square up to someone after an argument; that is another kind of decision.
                self.assertFalse(pending.resident_id == "raul" and pending.kind == "grievance")
        self.assertEqual(self.world.crisis_cooldowns["raul"], opened_at)


class AdviceTests(unittest.TestCase):
    def test_advice_moves_scores_and_impulsive_residents_heed_it_less(self) -> None:
        shifts = {}
        for label, personality in (("calm", LEVEL_HEADED), ("rash", HOTHEAD)):
            world = _world_with(personality)
            decision = _open_crisis(world)
            system = world.interventions
            provoke = next(option for option in decision.options if option.option_id == "provoke")
            alone, advised = system.scores(world, decision, None), system.scores(world, decision, provoke)
            self.assertGreater(advised["confront"], alone["confront"])
            self.assertLess(advised["cool_off"], alone["cool_off"])
            self.assertEqual(advised["talk_it_out"], alone["talk_it_out"])
            shifts[label] = advised["confront"] - alone["confront"]
        self.assertGreater(shifts["calm"], shifts["rash"])

    def test_the_same_advice_ends_differently_for_different_personalities(self) -> None:
        outcomes = {}
        for label, personality in (("calm", LEVEL_HEADED), ("rash", HOTHEAD)):
            world = _world_with(personality)
            decision = _open_crisis(world)
            outcomes[label] = world.interventions.resolve(world, decision.decision_id, "calm")
        self.assertEqual(outcomes, {"calm": "cool_off", "rash": "confront"})

    def test_what_they_lean_towards_is_known_before_any_advice(self) -> None:
        world = _world_with(HOTHEAD)
        self.assertEqual(_open_crisis(world).crisis.intent, "confront")

    def test_unknown_advice_counts_as_none_and_a_closed_decision_ignores_advice(self) -> None:
        world = SimulationWorld.demo_world()
        decision = _open_crisis(world)
        world.apply_command(ChooseOptionCommand(decision.decision_id, "no_such_option"))
        self.assertIn("sin consejo", world.history[-1].text)
        events = len(world.history)
        world.apply_command(ChooseOptionCommand(decision.decision_id, "calm"))
        self.assertEqual(len(world.history), events)


class OutcomeTests(unittest.TestCase):
    def test_egged_on_raul_confronts_marta_and_the_argument_runs_to_its_end(self) -> None:
        world = SimulationWorld.demo_world()
        decision = _open_crisis(world)
        before = world.relationship("marta", "raul").resentment, world.relationship("raul", "marta").resentment
        world.apply_command(ChooseOptionCommand(decision.decision_id, "provoke"))

        raul, marta = world.residents["raul"], world.residents["marta"]
        self.assertEqual((raul.activity.partner_id, raul.activity.intent), ("marta", "argument"))
        self.assertIn("Dale, dale", world.history[-1].text)
        for _ in range(180):
            world.step(1)
            if "argument_started" in _types(world):
                break
        argument = world.history[-1]
        self.assertEqual(argument.event_type, "argument_started")
        self.assertEqual(set(argument.participants), {"raul", "marta"})
        self.assertGreaterEqual(argument.importance, 50)
        self.assertEqual((raul.current_action, marta.current_action), ("argument", "argument"))

        world.step(20)
        self.assertNotEqual(raul.current_action, "argument")
        after = world.relationship("marta", "raul").resentment, world.relationship("raul", "marta").resentment
        self.assertGreater(after[0], before[0])
        self.assertGreater(after[1], before[1])
        # A settlement of nine sets about choosing a government in its first minute, which is another matter.
        kinds = [kind for kind in _types(world) if kind != "government_choosing"]
        self.assertEqual(kinds[:3], ["crisis_opened", "crisis_resolved", "argument_started"])
        self.assertIn("Discutí con Marta.", [memory.text for memory in world.memories.of("raul")])
        self.assertTrue(any(fact.event_type == "argument_started" for fact in world.knowledge.facts.values()))

    def test_talking_it_out_eases_the_grudge_on_both_sides(self) -> None:
        world = SimulationWorld.demo_world()
        decision = _open_crisis(world)
        before = world.relationship("marta", "raul").resentment, world.relationship("raul", "marta").resentment
        self.assertEqual(world.interventions.resolve(world, decision.decision_id, "talk"), "talk_it_out")
        world.step(240)
        self.assertIn("heart_to_heart_started", _types(world))
        self.assertLess(world.relationship("marta", "raul").resentment, before[0])
        self.assertLess(world.relationship("raul", "marta").resentment, before[1])

    def test_cooling_off_lowers_stress_and_leaves_a_memory_but_no_exchange(self) -> None:
        world = _world_with(LEVEL_HEADED)
        decision = _open_crisis(world)
        raul = world.residents["raul"]
        stress, resentment = raul.needs.stress, world.relationship("raul", "marta").resentment
        self.assertEqual(world.interventions.resolve(world, decision.decision_id, "calm"), "cool_off")
        self.assertLess(raul.needs.stress, stress)
        self.assertLess(world.relationship("raul", "marta").resentment, resentment)
        self.assertIsNone(raul.activity)
        self.assertEqual(world.memories.of("raul")[-1].text, "Me tragué el enfado con Marta.")
        self.assertIn("Relájate", world.history[-1].text)

    def test_left_alone_the_resident_decides_when_the_window_closes_and_not_before(self) -> None:
        world = SimulationWorld.demo_world()
        decision = _open_crisis(world)
        world.step(decision.deadline - world.clock.total_minutes - 1)
        self.assertIn(decision.decision_id, world.decisions)
        world.step(1)
        self.assertNotIn(decision.decision_id, world.decisions)
        resolved = world.history[-1]
        self.assertEqual(resolved.event_type, "crisis_resolved")
        self.assertIn("sin consejo", resolved.text)
        self.assertNotEqual(world.residents["raul"].current_action, BROOD_ACTION)

    def test_a_confrontation_wakes_its_target(self) -> None:
        world = SimulationWorld.demo_world()
        decision = _open_crisis(world)
        marta = world.residents["marta"]
        marta.x, marta.y = 3, 3
        marta.activity = Activity("sleep", "bed_1", minutes_left=600, using=True)
        marta.needs = Needs(hunger=0, tiredness=100, social=0, stress=0)
        self.assertFalse(world.is_aware(marta))
        world.apply_command(ChooseOptionCommand(decision.decision_id, "provoke"))
        world.step(120)
        self.assertIn("argument_started", _types(world))

    def test_being_confronted_overtakes_ones_own_crisis(self) -> None:
        world = SimulationWorld.demo_world()
        decision = _open_crisis(world)
        marta, raul = world.residents["marta"], world.residents["raul"]
        marta.activity = world.interventions.social.pursue(world, marta, raul, "argument")
        world.step(120)
        self.assertNotIn(decision.decision_id, world.decisions)
        self.assertNotIn("crisis_resolved", _types(world))
        self.assertIn("argument_started", _types(world))


class InterventionSaveTests(unittest.TestCase):
    def setUp(self) -> None:
        self.manager = SaveManager()

    def test_a_pending_decision_survives_saving_and_advice_after_loading_plays_out_the_same(self) -> None:
        original = SimulationWorld.demo_world()
        decision = _open_crisis(original)
        original.step(10)
        loaded = self.manager.from_data(self.manager.to_data(original))
        self.assertEqual(self.manager.to_data(loaded), self.manager.to_data(original))
        self.assertEqual(loaded.decisions[decision.decision_id].options, decision.options)
        for world in (original, loaded):
            world.apply_command(ChooseOptionCommand(decision.decision_id, "provoke"))
            world.step(2 * MINUTES_PER_DAY)
        self.assertEqual(self.manager.to_data(loaded), self.manager.to_data(original))
        self.assertEqual([e.text for e in loaded.history], [e.text for e in original.history])

    def test_the_same_advice_at_the_same_time_gives_the_same_history(self) -> None:
        histories = []
        for _ in range(2):
            world = SimulationWorld.demo_world(seed=5)
            for _ in range(3 * MINUTES_PER_DAY):
                world.step(1)
                for decision in list(world.decisions.values()):
                    world.apply_command(ChooseOptionCommand(decision.decision_id, "talk"))
            histories.append([(event.timestamp, event.text) for event in world.history])
        self.assertEqual(histories[0], histories[1])
        self.assertTrue(histories[0])

    def test_version_3_save_without_decisions_or_knowledge_loads(self) -> None:
        world = SimulationWorld.demo_world()
        world.step(600)
        data = self.manager.to_data(world)
        data["version"] = 3
        for key in ("decisions", "decision_count", "crisis_cooldowns", "history", "facts", "beliefs"):
            del data[key]
        for resident in data["residents"]:
            if resident["activity"] is not None:
                resident["activity"].pop("intent", None)
        loaded = self.manager.from_data(data)
        self.assertEqual((loaded.decisions, loaded.history, loaded.knowledge.facts), ({}, [], {}))
        loaded.step(MINUTES_PER_DAY)

    def test_a_decision_of_a_removed_kind_or_resident_is_dropped_on_load(self) -> None:
        world = SimulationWorld.demo_world()
        _open_crisis(world)
        data = self.manager.to_data(world)
        data["decisions"][0]["kind"] = "duel"
        loaded = self.manager.from_data(data)
        self.assertEqual(loaded.decisions, {})
        loaded.step(MINUTES_PER_DAY)


class DecisionDataTests(unittest.TestCase):
    def test_a_decision_that_names_an_unknown_interaction_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "data"
            (root / "maps").mkdir(parents=True)
            for path in DATA_DIR.rglob("*.json"):
                text = path.read_text(encoding="utf-8")
                if path.name == "decisions.json":
                    text = text.replace('"interaction": "argument"', '"interaction": "duel"')
                (root / path.relative_to(DATA_DIR)).write_text(text, encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "unknown interaction: duel"):
                BuiltInRegistries.load(root)


class LongRunTests(unittest.TestCase):
    """Regression: an unattended feud once spiralled until a need sat at its maximum."""

    def _run(self, seed: int, advice: str | None, days: int = 14) -> SimulationWorld:
        world = SimulationWorld.demo_world(seed=seed)
        for _ in range(days * MINUTES_PER_DAY):
            world.step(1)
            for resident in world.residents.values():
                for need in ("hunger", "tiredness", "social", "stress"):
                    self.assertLess(getattr(resident.needs, need), 100.0, (seed, advice, resident.name, need))
            if advice is not None:
                for decision in list(world.decisions.values()):
                    world.apply_command(ChooseOptionCommand(decision.decision_id, advice))
        return world

    def test_two_weeks_never_pin_a_need_whatever_the_player_does(self) -> None:
        for seed, advice in ((7, None), (99, None), (42, "provoke")):
            self._run(seed, advice)

    def test_calming_advice_leaves_less_conflict_than_egging_on(self) -> None:
        calm, provoked = self._run(7, "calm"), self._run(7, "provoke")
        arguments = lambda world: sum(event.event_type == "argument_started" for event in world.history)
        self.assertLess(arguments(calm), arguments(provoked))
        self.assertLess(
            calm.relationship("raul", "marta").resentment, provoked.relationship("raul", "marta").resentment
        )


if __name__ == "__main__":
    unittest.main()
