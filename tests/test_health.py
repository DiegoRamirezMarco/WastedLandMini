import json
import unittest
from collections import Counter

from save.save_manager import SaveManager
from simulation.commands import ChooseOptionCommand
from simulation.events.intervention_system import BRAWL, BROOD_ACTION, escalation_chance
from simulation.health.health_system import RECOVERED_HEALTH, UNFIT_HEALTH
from simulation.health.injury import Injury
from simulation.items.custom_content import validate_item_data
from simulation.knowledge.knowledge_system import share_rumor
from simulation.residents.activity import Activity
from simulation.residents.needs import Needs
from simulation.residents.personality import Personality
from simulation.work.work_system import WORK_ACTION
from simulation.world import SimulationWorld

MINUTES_PER_DAY = 24 * 60
HOTHEAD = Personality(aggression=95, impulsiveness=95, empathy=10, courage=80)
GENTLE = Personality(aggression=15, impulsiveness=20, empathy=85)


def _settled(seed: int = 7) -> SimulationWorld:
    world = SimulationWorld.demo_world(seed=seed)
    world.relationships.clear()
    for resident in world.residents.values():
        resident.needs = Needs(hunger=0, tiredness=0, social=0, stress=0)
    return world


def _keep_content(world: SimulationWorld) -> None:
    for resident in world.residents.values():
        resident.needs = Needs(hunger=0, tiredness=0, social=0, stress=0)


def _types(world: SimulationWorld) -> list[str]:
    return [event.event_type for event in world.history]


def _brawl(world: SimulationWorld, resident_id: str = "raul", target_id: str = "marta"):
    """Have one resident square up to another, as after an argument, and return the decision."""
    resident, target = world.residents[resident_id], world.residents[target_id]
    world.relationship(resident_id, target_id).resentment = 90
    world.relationship(target_id, resident_id).resentment = 90
    for _ in range(200):
        activity = world.interventions.maybe_brawl(world, resident, target)
        if activity is not None:
            resident.activity = activity
            return world.interventions.pending_for(world, resident_id)
    raise AssertionError("no brawl was brewing")


def _run_fight(world: SimulationWorld, limit: int = 240) -> None:
    """Advance until a fight has started and finished."""
    started = False
    for _ in range(limit):
        world.step(1)
        fighting = any(resident.current_action == "fight" for resident in world.residents.values())
        started = started or fighting
        if started and not fighting:
            return
    raise AssertionError("the fight never happened" if not started else "the fight never ended")


class HealthTests(unittest.TestCase):
    def setUp(self) -> None:
        self.world = _settled()
        self.raul = self.world.residents["raul"]

    def test_health_is_what_injuries_leave(self) -> None:
        self.assertEqual(self.raul.health, 100.0)
        self.raul.injuries = [Injury("bruise", 20), Injury("cut", 15)]
        self.assertEqual(self.raul.health, 65.0)
        self.raul.injuries.append(Injury("fracture", 500))
        self.assertEqual(self.raul.health, 0.0)

    def _health_after(self, hours: int, in_clinic: bool, medic_on_duty: bool) -> float:
        world = _settled()
        raul, vera = world.residents["raul"], world.residents["vera"]
        raul.injuries = [Injury("cut", 40)]
        raul.job_id = None
        if in_clinic:
            raul.x, raul.y = 27, 22
            raul.activity = Activity("rest", "clinic_bed_1", minutes_left=10_000, using=True)
        else:
            raul.activity = Activity("wander", minutes_left=10_000, using=True)
        if medic_on_duty:
            vera.activity = Activity(WORK_ACTION, "medicine_cabinet", minutes_left=10_000, using=True)
        else:
            vera.job_id = None
        for _ in range(hours * 60):
            world.step(1)
            _keep_content(world)
        return raul.health

    def test_wounds_mend_alone_faster_lying_down_and_fastest_with_a_medic(self) -> None:
        on_foot = self._health_after(12, in_clinic=False, medic_on_duty=False)
        lying = self._health_after(12, in_clinic=True, medic_on_duty=False)
        treated = self._health_after(12, in_clinic=True, medic_on_duty=True)
        self.assertGreater(on_foot, 60.0)
        self.assertGreater(lying, on_foot + 1)
        self.assertGreater(treated, lying + 3)

    def test_the_hurt_go_to_the_clinic_and_get_up_when_they_are_better(self) -> None:
        self.raul.job_id = None
        self.raul.injuries = [Injury("bruise", 45)]
        activity = self.world.activities.routine.plan(self.world, self.raul)
        self.assertEqual(activity.action, "rest")
        self.assertEqual(self.world.interactables[activity.target_id].kind, "clinic_bed")
        self.raul.activity = activity
        for _ in range(4 * MINUTES_PER_DAY):
            self.world.step(1)
            _keep_content(self.world)
            if self.raul.health >= RECOVERED_HEALTH and self.raul.current_action != "rest":
                break
        self.assertGreaterEqual(self.raul.health, RECOVERED_HEALTH)
        self.assertNotEqual(self.raul.current_action, "rest")

    def test_a_scratch_is_not_worth_a_bed(self) -> None:
        self.raul.job_id = None
        self.raul.injuries = [Injury("bruise", 8)]
        self.assertNotEqual(self.world.activities.routine.plan(self.world, self.raul).action, "rest")

    def test_someone_badly_hurt_does_not_go_to_work(self) -> None:
        self.world.clock.hour = 9
        self.assertIsNotNone(self.world.work.candidate(self.world, self.raul))
        self.raul.injuries = [Injury("fracture", 100 - UNFIT_HEALTH + 5)]
        self.assertIsNone(self.world.work.candidate(self.world, self.raul))

    def test_a_patient_gets_up_to_eat(self) -> None:
        self.raul.injuries = [Injury("fracture", 60)]
        self.raul.x, self.raul.y = 27, 22
        self.raul.activity = Activity("rest", "clinic_bed_1", minutes_left=600, using=True)
        self.raul.needs.hunger = 90
        self.world.step(1)
        self.assertFalse(self.raul.activity is not None and self.raul.activity.action == "rest")


class WeaponTests(unittest.TestCase):
    def setUp(self) -> None:
        self.world = _settled()
        self.health = self.world.health
        self.fight = self.world.registries.interactions["fight"]

    def test_the_guard_carries_a_truncheon_and_a_knife_lies_in_the_workshop(self) -> None:
        self.assertEqual(self.health.weapon_of(self.world, self.world.residents["tomas"])[0], 1.4)
        self.assertEqual(self.health.weapon_of(self.world, self.world.residents["raul"]), (1.0, ()))
        self.assertEqual(self.world.containers["crate_workshop"].count("rusty_knife"), 1)

    def test_a_weapon_and_a_temper_make_blows_land_harder(self) -> None:
        def total(attacker_id: str) -> float:
            world = _settled()
            victim, attacker = world.residents["ines"], world.residents[attacker_id]
            for _ in range(3):
                world.health.fight_damage(world, victim, attacker, world.registries.interactions["fight"])
            return 100.0 - victim.health

        self.assertGreater(total("tomas"), total("lucia"))

    def test_a_blade_cuts_and_fists_bruise(self) -> None:
        victim, attacker = self.world.residents["ines"], self.world.residents["raul"]
        self.health.fight_damage(self.world, victim, attacker, self.fight)
        self.assertEqual(victim.injuries[-1].kind, "bruise")
        self.world.stock(attacker.inventory, "rusty_knife", 1, "raul")
        self.health.fight_damage(self.world, victim, attacker, self.fight)
        self.assertEqual(victim.injuries[-1].kind, "cut")
        self.assertIn("injured", _types(self.world))

    def test_an_injury_of_an_unknown_kind_becomes_a_bruise(self) -> None:
        raul = self.world.residents["raul"]
        self.assertTrue(self.health.hurt(self.world, raul, 5, "frostbite", "el frío"))
        self.assertEqual(raul.injuries[-1].kind, "bruise")

    def test_pack_items_may_carry_numeric_properties_only(self) -> None:
        good = {"id": "pipe", "name": "tubería", "article": "una", "category": "tool", "properties": {"damage": 1.5}}
        validate_item_data(good, "pipe", None)
        with self.assertRaisesRegex(ValueError, "properties"):
            validate_item_data({**good, "properties": {"damage": "lots"}}, "pipe", None)


class BrawlTests(unittest.TestCase):
    def setUp(self) -> None:
        self.world = _settled()
        self.raul, self.marta = self.world.residents["raul"], self.world.residents["marta"]
        for resident in self.world.residents.values():
            resident.job_id = None

    def test_bad_blood_and_temper_bring_it_on_and_fear_and_kindness_hold_it_back(self) -> None:
        self.assertEqual(escalation_chance(self.world, self.marta, self.raul), 0.0)
        calm = escalation_chance(self.world, self.raul, self.marta)
        self.world.relationship("raul", "marta").resentment = 80
        self.world.relationship("marta", "raul").resentment = 80
        tense = escalation_chance(self.world, self.raul, self.marta)
        self.assertGreater(tense, calm)
        self.world.relationship("raul", "marta").fear = 80
        self.assertLess(escalation_chance(self.world, self.raul, self.marta), tense)
        self.raul.personality = HOTHEAD
        self.assertLessEqual(escalation_chance(self.world, self.raul, self.marta), 0.6)

    def test_squaring_up_opens_a_short_decision_before_anything_happens(self) -> None:
        decision = _brawl(self.world)
        self.assertEqual((decision.kind, decision.resident_id, decision.crisis.target_id), (BRAWL, "raul", "marta"))
        self.assertEqual([o.option_id for o in decision.options], ["separate", "talk", "neutral", "provoke"])
        self.assertEqual(decision.deadline - self.world.clock.total_minutes, 20)
        self.assertEqual(self.raul.current_action, BROOD_ACTION)
        brewing = self.world.history[-1]
        self.assertEqual(brewing.event_type, "fight_brewing")
        self.assertGreaterEqual(brewing.importance, 60)
        self.assertNotIn("fight_started", _types(self.world))
        self.assertIsNone(self.world.interventions.maybe_brawl(self.world, self.marta, self.raul), "one at a time")

    def test_stepping_in_stops_it(self) -> None:
        decision = _brawl(self.world)
        outcome = self.world.apply_command(ChooseOptionCommand(decision.decision_id, "separate"))
        self.assertEqual(outcome, "walk_away")
        self.world.step(120)
        self.assertNotIn("fight_started", _types(self.world))
        self.assertEqual((self.raul.health, self.marta.health), (100.0, 100.0))
        self.assertIn("Estuve a punto de pegar a Marta.", [m.text for m in self.world.memories.of("raul")])

    def test_egged_on_they_fight_and_both_come_out_hurt_and_afraid(self) -> None:
        decision = _brawl(self.world)
        fear_before = self.world.relationship("marta", "raul").fear
        self.assertEqual(self.world.apply_command(ChooseOptionCommand(decision.decision_id, "provoke")), "fight")
        self.assertEqual((self.raul.activity.partner_id, self.raul.activity.intent), ("marta", "fight"))
        _run_fight(self.world)

        started = next(event for event in self.world.history if event.event_type == "fight_started")
        self.assertEqual(set(started.participants), {"raul", "marta"})
        self.assertGreaterEqual(started.importance, 60)
        self.assertLess(self.raul.health, 100.0)
        self.assertLess(self.marta.health, 100.0)
        self.assertGreater(self.world.relationship("marta", "raul").fear, fear_before)
        self.assertEqual(_types(self.world).count("injured"), 2)
        self.assertTrue(any("se peleó con" in fact.text for fact in self.world.knowledge.facts.values()))
        self.assertIn("Me peleé con Raúl.", [m.text for m in self.world.memories.of("marta")])

    def test_left_alone_the_hothead_swings_and_the_gentle_one_walks_away(self) -> None:
        outcomes = {}
        for label, personality in (("hothead", HOTHEAD), ("gentle", GENTLE)):
            world = _settled()
            world.residents["raul"].personality = personality
            decision = _brawl(world)
            world.step(decision.deadline - world.clock.total_minutes)
            self.assertNotIn(decision.decision_id, world.decisions)
            resolved = [event for event in world.history if event.event_type == "crisis_resolved"][-1]
            outcomes[label] = "fight" if "se lanza" in resolved.text else "walk_away"
        self.assertEqual(outcomes, {"hothead": "fight", "gentle": "walk_away"})

    def test_the_same_word_stops_one_and_not_another(self) -> None:
        outcomes = {}
        for label, personality in (("hothead", HOTHEAD), ("gentle", GENTLE)):
            world = _settled()
            world.residents["raul"].personality = personality
            decision = _brawl(world)
            outcomes[label] = world.apply_command(ChooseOptionCommand(decision.decision_id, "talk"))
        self.assertEqual(outcomes, {"hothead": "fight", "gentle": "walk_away"})

    def test_no_fight_ever_starts_without_a_chance_to_step_in(self) -> None:
        # A fortnight in which a fight sends somebody to the clinic: one seed in twelve has none.
        world = SimulationWorld.demo_world(seed=9)
        for _ in range(14 * MINUTES_PER_DAY):
            world.step(1)
            for decision in list(world.decisions.values()):
                world.apply_command(ChooseOptionCommand(decision.decision_id, "provoke"))
        kinds = Counter(_types(world))
        self.assertGreater(kinds["fight_started"], 0)
        self.assertLessEqual(kinds["fight_started"], kinds["fight_brewing"])
        self.assertTrue(any("se tumba en la enfermería" in line for line in world.event_log))


class DeathTests(unittest.TestCase):
    def setUp(self) -> None:
        self.world = _settled()
        self.raul, self.lucia = self.world.residents["raul"], self.world.residents["lucia"]
        self.fight = self.world.registries.interactions["fight"]
        for resident in self.world.residents.values():
            resident.job_id = None if resident is not self.lucia else resident.job_id
            resident.x, resident.y = 3, 3
        # Lucía and Raúl are out in the plaza; Marta watches from close by.
        self.lucia.x, self.lucia.y = 20, 14
        self.raul.x, self.raul.y = 21, 14
        self.world.residents["marta"].x, self.world.residents["marta"].y = 23, 14
        self.world.relationship("marta", "lucia").affection = 80
        self.world.relationship("ines", "lucia").affection = 80
        self.lucia.injuries = [Injury("cut", 97)]

    def _kill(self) -> None:
        self.raul.activity = Activity("fight", minutes_left=3, using=True, partner_id="lucia")
        self.world.decisions.clear()
        self.assertFalse(self.world.health.fight_damage(self.world, self.lucia, self.raul, self.fight))

    def test_the_dead_are_gone_recorded_and_buried(self) -> None:
        self._kill()
        self.assertNotIn("lucia", self.world.residents)
        death = self.world.deaths[0]
        self.assertEqual((death.resident_id, death.name, death.killer_id), ("lucia", "Lucía", "raul"))
        grave = self.world.interactables[death.grave_id]
        self.assertEqual(grave.kind, "grave")
        self.assertEqual(self.world.room_at((grave.x, grave.y)).room_id, "graveyard")
        event = self.world.history[-1]
        self.assertEqual((event.event_type, event.importance), ("death", 95))
        self.assertIn("Lucía ha muerto", event.text)
        self.assertIsNone(self.raul.activity, "the survivor is no longer fighting anyone")

    def test_what_they_owned_is_everyones_and_their_post_stands_empty(self) -> None:
        toy = self.lucia.inventory.items[0]
        self.lucia.activity = Activity(WORK_ACTION, "bar", minutes_left=60, using=True)
        self.assertTrue(self.world.work.is_staffed(self.world, "bartender"))
        self._kill()
        self.assertIsNone(toy.owner_id)
        self.assertTrue(any(inventory.find(toy.instance_id) for inventory in self.world.containers.values()))
        self.assertFalse(self.world.work.is_staffed(self.world, "bartender"))
        self.world.clock.hour = 19
        drinks = [c for c in self.world.activities.routine.candidates(self.world, self.raul) if c.name == "drink"]
        self.assertEqual(drinks, [], "nobody serves at the bar any more")

    def test_decisions_about_the_dead_are_dropped(self) -> None:
        marta = self.world.residents["marta"]
        self.world.relationship("marta", "lucia").resentment = 90
        self.world.relationship("lucia", "marta").resentment = 90
        for _ in range(200):
            activity = self.world.interventions.maybe_brawl(self.world, marta, self.lucia)
            if activity is not None:
                break
        self.assertTrue(self.world.decisions)
        self.raul.activity = Activity("fight", minutes_left=3, using=True, partner_id="lucia")
        self.world.health.fight_damage(self.world, self.lucia, self.raul, self.fight)
        self.assertEqual(self.world.decisions, {})

    def test_those_who_see_it_turn_on_the_killer_and_grieve_by_how_fond_they_were(self) -> None:
        marta, tomas = self.world.residents["marta"], self.world.residents["tomas"]
        tomas.x, tomas.y = 23, 15
        self._kill()
        fact = list(self.world.knowledge.facts.values())[-1]
        self.assertEqual(fact.subject_ids, ["raul", "lucia"])
        for witness in (marta, tomas):
            self.assertTrue(self.world.knowledge.knows(witness.resident_id, fact.fact_id))
            feelings = self.world.relationship(witness.resident_id, "raul")
            self.assertGreater(feelings.resentment, 20)
            self.assertGreater(feelings.fear, 10)
        self.assertGreater(marta.needs.stress, tomas.needs.stress, "Marta was fond of her")

    def test_those_elsewhere_carry_on_until_someone_tells_them(self) -> None:
        ines = self.world.residents["ines"]
        self._kill()
        fact = list(self.world.knowledge.facts.values())[-1]
        self.assertFalse(self.world.knowledge.knows("ines", fact.fact_id))
        self.assertEqual((ines.needs.stress, self.world.relationships.get(("ines", "raul"))), (0, None))
        for _ in range(200):
            if share_rumor(self.world, self.world.residents["marta"], ines) is not None:
                break
        self.assertTrue(self.world.knowledge.knows("ines", fact.fact_id))
        self.assertGreater(ines.needs.stress, 10)
        self.assertGreater(self.world.relationship("ines", "raul").resentment, 10)

    def test_life_goes_on_without_them(self) -> None:
        self._kill()
        for resident_id, (job, _) in {"marta": ("cook", ""), "raul": ("farmer", ""), "ines": ("farmer", "")}.items():
            self.world.residents[resident_id].job_id = job
        living = len(self.world.residents)
        self.world.step(5 * MINUTES_PER_DAY)
        self.assertEqual(len(self.world.residents), living)
        self.assertEqual(len(self.world.deaths), 1)


class HealthSaveTests(unittest.TestCase):
    def setUp(self) -> None:
        self.manager = SaveManager()

    def test_injuries_graves_and_the_dead_survive_saving(self) -> None:
        world = _settled()
        raul, lucia = world.residents["raul"], world.residents["lucia"]
        lucia.injuries = [Injury("cut", 99)]
        raul.injuries = [Injury("bruise", 12.5)]
        world.health.fight_damage(world, lucia, raul, world.registries.interactions["fight"])
        self.assertEqual(len(world.deaths), 1)
        loaded = self.manager.from_data(json.loads(json.dumps(self.manager.to_data(world))))
        self.assertEqual(self.manager.to_data(loaded), self.manager.to_data(world))
        self.assertEqual(loaded.deaths[0].name, "Lucía")
        self.assertIn(loaded.deaths[0].grave_id, loaded.interactables)
        self.assertEqual(loaded.residents["raul"].injuries, [Injury("bruise", 12.5)])
        world.step(2 * MINUTES_PER_DAY)
        loaded.step(2 * MINUTES_PER_DAY)
        self.assertEqual(self.manager.to_data(loaded), self.manager.to_data(world))

    def test_a_decision_to_fight_survives_saving_and_plays_out_the_same(self) -> None:
        original = _settled()
        decision = _brawl(original)
        loaded = self.manager.from_data(json.loads(json.dumps(self.manager.to_data(original))))
        self.assertEqual(loaded.decisions[decision.decision_id].kind, BRAWL)
        for world in (original, loaded):
            world.apply_command(ChooseOptionCommand(decision.decision_id, "provoke"))
            world.step(MINUTES_PER_DAY)
        self.assertEqual(self.manager.to_data(loaded), self.manager.to_data(original))

    def test_a_save_from_before_health_loads_with_everyone_unhurt(self) -> None:
        world = SimulationWorld.demo_world()
        data = self.manager.to_data(world)
        data["version"] = 6
        del data["deaths"]
        for resident in data["residents"]:
            del resident["injuries"]
        loaded = self.manager.from_data(data)
        self.assertEqual([r.health for r in loaded.residents.values()], [100.0] * len(loaded.residents))
        self.assertEqual(loaded.deaths, [])
        loaded.step(MINUTES_PER_DAY)


class ConsequencesInTheSettlementTests(unittest.TestCase):
    def test_with_a_calming_voice_three_weeks_pass_without_a_blow(self) -> None:
        world = SimulationWorld.demo_world(seed=7)
        for _ in range(21 * MINUTES_PER_DAY):
            world.step(1)
            for decision in list(world.decisions.values()):
                option = "separate" if decision.kind == BRAWL else "calm"
                world.apply_command(ChooseOptionCommand(decision.decision_id, option))
        self.assertNotIn("fight_started", _types(world))
        self.assertEqual(world.deaths, [])
        # A trip outside may still leave its mark on someone: nobody inside laid a hand on anybody.
        hurts = [event for event in world.history if event.event_type in ("injured", "limb_lost")]
        self.assertEqual([event.data["by"] for event in hurts if event.data.get("by") is not None], [])

    def test_egging_everyone_on_fills_the_clinic_but_needs_stay_in_hand(self) -> None:
        world = SimulationWorld.demo_world(seed=99)
        lowest = 100.0
        for _ in range(21 * MINUTES_PER_DAY):
            world.step(1)
            for decision in list(world.decisions.values()):
                world.apply_command(ChooseOptionCommand(decision.decision_id, "provoke"))
            for resident in world.residents.values():
                lowest = min(lowest, resident.health)
                for need in ("hunger", "tiredness", "social", "stress"):
                    self.assertLess(getattr(resident.needs, need), 100.0, (resident.name, need, world.clock.label))
        self.assertLess(lowest, 90.0)
        self.assertGreater(_types(world).count("fight_started"), 2)


if __name__ == "__main__":
    unittest.main()
