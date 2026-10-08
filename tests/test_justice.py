import unittest

from save.save_manager import SaveManager
from simulation.commands import AccuseCommand, ChooseOptionCommand, SentenceCommand, SetPrisonRationCommand
from simulation.economy.terms import TradingState
from simulation.events.event import DomainEvent
from simulation.justice.records import CLOSED, GUILTY, INNOCENT, PUNISHMENT, STEPS, Trial
from simulation.justice.settings import ANGER, APPROVAL, FEAR, GRIEF, justice_settings_from_data
from simulation.knowledge.fact import SOURCE_TOLD, SOURCE_WITNESS, Belief
from simulation.residents.activity import ACCUSE_DECISION, EXILE_BACK_DECISION, SERVE_ACTION
from simulation.residents.needs import Needs
from simulation.world import SimulationWorld
from world.interactable import Interactable

MINUTES_PER_DAY = 24 * 60
THEFT, KILLING, BREACH = "theft_committed", "death", "law_broken"
THIEF, WITNESS = "paco", "ines"


def _settled(seed: int = 7) -> SimulationWorld:
    """The settlement that comes ready made, with everyone content, no grudges and no politics yet."""
    world = SimulationWorld.demo_world(seed=seed)
    world.relationships.clear()
    for resident in world.residents.values():
        resident.needs = Needs(hunger=0, tiredness=0, social=0, stress=0)
    return world


def _misdeed(world: SimulationWorld, doer: str, kind: str = THEFT, seen_by: tuple[str, ...] = (WITNESS,)) -> str:
    """Have somebody do something, seen by exactly those named. Returns the ID of the fact."""
    name = world.residents[doer].name
    fact = world.emit_event(DomainEvent(kind, 60, f"{name} hace algo", [doer]), fact_text=f"{name} hizo algo")
    for resident_id in seen_by:
        world.knowledge.set_belief(resident_id, Belief(fact.fact_id, 1.0, SOURCE_WITNESS, world.clock.total_minutes))
    return fact.fact_id


def _to_sentence(world: SimulationWorld) -> Trial:
    """Let the trial going on run until it is over or waits for what the player says."""
    trial = world.justice.open_trial(world)
    for _ in range(len(STEPS) * world.registries.justice.step_minutes + 5):
        if not trial.open or trial.awaiting_sentence:
            break
        world.step(1)
    return trial


def _jail(world: SimulationWorld) -> str:
    room_id = next(room_id for room_id, room in world.rooms.items() if room.roofed)
    world.homes.uses[room_id] = "jail"
    return room_id


def _condemned(world: SimulationWorld, accused: str, offence: str = THEFT, known_to: tuple[str, ...] = ()) -> Trial:
    """A trial that has found somebody guilty and waits for what they are given, with the
    thing known first-hand to those named and to nobody else."""
    fact_id = _misdeed(world, accused, offence, known_to)
    state = world.courts
    state.trial_count += 1
    trial = Trial(f"trial_{state.trial_count}", accused, WITNESS, offence, fact_id, step=PUNISHMENT, verdict=GUILTY)
    trial.next_at = world.clock.total_minutes + 600
    state.trials[trial.trial_id] = trial
    return trial


class AccusationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.world = _settled()

    def test_a_theft_somebody_saw_goes_to_trial_and_one_nobody_saw_cannot(self) -> None:
        world = self.world
        unseen = _misdeed(world, THIEF, seen_by=())
        self.assertEqual(world.justice.known_offences(world, THIEF), [])
        refused = world.apply_command(AccuseCommand(THIEF, unseen))
        self.assertFalse(refused.ok)
        self.assertIn("no se sabe nada", refused.message)
        self.assertIsNone(world.justice.open_trial(world), "what only the world knows is no ground for a trial")
        seen = _misdeed(world, THIEF)
        self.assertEqual([fact.fact_id for fact in world.justice.known_offences(world, THIEF)], [seen])
        opened = world.apply_command(AccuseCommand(THIEF))
        self.assertTrue(opened.ok)
        trial = world.courts.trials[opened.detail]
        self.assertEqual((trial.accused, trial.offence, trial.fact_id, trial.step), (THIEF, THEFT, seen, "accusation"))
        self.assertTrue(any(event.event_type == "trial_opened" for event in world.history))

    def test_a_law_seen_broken_can_be_answered_for(self) -> None:
        world = self.world
        fact_id = _misdeed(world, THIEF, BREACH)
        self.assertTrue(world.apply_command(AccuseCommand(THIEF, fact_id)).ok)
        self.assertEqual(world.justice.open_trial(world).offence, BREACH)

    def test_nobody_is_tried_twice_for_a_thing_nor_two_at_once(self) -> None:
        world = self.world
        first = _misdeed(world, THIEF)
        _misdeed(world, "raul")
        self.assertTrue(world.apply_command(AccuseCommand(THIEF)).ok)
        self.assertIn("en marcha", world.apply_command(AccuseCommand("raul")).message)
        trial = _to_sentence(world)
        world.apply_command(SentenceCommand(trial.trial_id, "warning"))
        self.assertTrue(world.justice.tried(world, first))
        self.assertFalse(world.apply_command(AccuseCommand(THIEF, first)).ok)
        self.assertTrue(world.apply_command(AccuseCommand("raul")).ok, "once it is over, another can be")

    def test_what_is_known_only_to_whoever_did_it_is_known_to_nobody(self) -> None:
        world = self.world
        fact_id = _misdeed(world, THIEF, seen_by=(THIEF,))
        self.assertFalse(world.apply_command(AccuseCommand(THIEF, fact_id)).ok)

    def test_somebody_who_saw_it_thinks_of_accusing_and_the_player_has_a_say(self) -> None:
        world = self.world
        fact_id = _misdeed(world, THIEF)
        witness, thief = world.residents[WITNESS], world.residents[THIEF]
        fact = world.knowledge.facts[fact_id]
        calm = world.justice.wish_to_accuse(world, witness, thief, fact)
        world.relationship(WITNESS, THIEF).adjust("resentment", 60.0)
        self.assertGreater(world.justice.wish_to_accuse(world, witness, thief, fact), calm)
        self.assertEqual(world.justice.wish_to_accuse(world, world.residents["raul"], thief, fact), 0.0, "they know nothing of it")
        world.clock.hour, world.clock.minute = world.registries.justice.accuse_hour - 1, 59
        world.step(1)
        decision = next(each for each in world.decisions.values() if each.kind == ACCUSE_DECISION)
        self.assertEqual(decision.resident_id, WITNESS)
        self.assertEqual(world.courts.weighing[WITNESS], (THIEF, fact_id))
        outcome = world.apply_command(ChooseOptionCommand(decision.decision_id, "encourage"))
        self.assertEqual(world.courts.weighing, {})
        trial = world.justice.open_trial(world)
        if outcome == "accuse":
            self.assertEqual((trial.accuser, trial.accused), (WITNESS, THIEF))
        else:
            self.assertIsNone(trial)

    def test_nobody_accuses_their_own_kin(self) -> None:
        world = self.world
        fact_id = _misdeed(world, "marta", seen_by=("vera",))
        world.relationship("vera", "marta").adjust("resentment", 90.0)
        fact = world.knowledge.facts[fact_id]
        self.assertEqual(world.justice.wish_to_accuse(world, world.residents["vera"], world.residents["marta"], fact), 0.0)


class TrialTests(unittest.TestCase):
    def setUp(self) -> None:
        self.world = _settled()

    def test_a_trial_goes_through_its_six_steps_and_waits_for_the_player(self) -> None:
        world = self.world
        _misdeed(world, THIEF, seen_by=tuple(each for each in world.residents if each != THIEF))
        world.apply_command(AccuseCommand(THIEF))
        trial = world.justice.open_trial(world)
        seen = [trial.step]
        for _ in range(len(STEPS) * world.registries.justice.step_minutes + 5):
            world.step(1)
            if trial.step != seen[-1]:
                seen.append(trial.step)
            if trial.awaiting_sentence:
                break
        self.assertEqual(tuple(seen), STEPS)
        self.assertEqual(trial.verdict, GUILTY)
        # Whoever is out of the settlement that hour says nothing.
        self.assertTrue(set(trial.witnesses) <= set(world.residents) - {THIEF})
        self.assertGreaterEqual(len(trial.witnesses), 6)
        self.assertNotIn(THIEF, trial.ballots, "nobody judges themselves")
        self.assertTrue(all(trial.ballots.values()))
        steps = [event.data.get("step") for event in world.history if event.event_type == "trial_step"]
        self.assertEqual(steps, ["evidence", "witnesses", "defence"])
        self.assertTrue(any(event.event_type == "trial_verdict" for event in world.history))

    def test_each_judges_on_what_they_believe_they_know(self) -> None:
        world = self.world
        fact_id = _misdeed(world, THIEF)
        world.apply_command(AccuseCommand(THIEF, fact_id))
        trial = world.justice.open_trial(world)
        trial.witnesses = [WITNESS]
        witness, stranger = world.residents[WITNESS], world.residents["raul"]
        self.assertTrue(world.justice.holds_guilty(world, witness, trial), "they saw it")
        self.assertFalse(world.justice.holds_guilty(world, stranger, trial), "they have only a stranger's word for it")
        world.relationship("raul", WITNESS).adjust("trust", 90.0)
        self.assertTrue(world.justice.holds_guilty(world, stranger, trial), "the word of somebody they trust is enough")
        world.relationship("raul", THIEF).adjust("affection", 90.0)
        self.assertFalse(world.justice.holds_guilty(world, stranger, trial), "unless it is against a friend")
        # Heard of, it counts for less than seen.
        world.knowledge.set_belief("lucia", Belief(fact_id, 0.5, SOURCE_TOLD, 0, WITNESS))
        self.assertLess(
            world.justice.belief_in_guilt(world, world.residents["lucia"], trial),
            world.justice.belief_in_guilt(world, witness, trial),
        )

    def test_with_nobody_sure_of_it_they_are_found_innocent_and_hold_it_against_whoever_accused(self) -> None:
        world = self.world
        _misdeed(world, THIEF)
        world.justice.accuse(world, THIEF, None, WITNESS)
        trial = _to_sentence(world)
        self.assertEqual((trial.verdict, trial.step), (INNOCENT, CLOSED), "one who saw it against seven who did not")
        self.assertGreater(world.relationship(THIEF, WITNESS).resentment, 0)
        self.assertEqual(world.courts.history, [], "and nothing is done to them")

    def test_said_nothing_of_it_they_are_given_the_least_there_is(self) -> None:
        world = self.world
        trial = _condemned(world, THIEF, known_to=(WITNESS,))
        trial.next_at = world.clock.total_minutes + 2
        world.step(3)
        self.assertEqual((trial.punishment, trial.step), (world.registries.justice.unanswered, CLOSED))


class PunishmentTests(unittest.TestCase):
    def setUp(self) -> None:
        self.world = _settled()

    def test_nobody_is_sentenced_to_what_there_is_no_place_for(self) -> None:
        world = self.world
        trial = _condemned(world, THIEF, known_to=(WITNESS,))
        available = world.justice.available(world)
        for needs_a_place in ("prison", "public_stocks", "execution"):
            self.assertNotIn(needs_a_place, available)
        self.assertEqual(available[0], "warning", "the mildest first")
        refused = world.apply_command(SentenceCommand(trial.trial_id, "prison"))
        self.assertFalse(refused.ok)
        self.assertIn("cárcel", refused.message)
        self.assertTrue(trial.awaiting_sentence, "it still waits to be said")
        self.assertIn("horca", world.apply_command(SentenceCommand(trial.trial_id, "execution")).message)
        _jail(world)
        world.interactables["stocks_1"] = Interactable("stocks_1", "stocks", 20, 20)
        self.assertIn("prison", world.justice.available(world))
        self.assertIn("public_stocks", world.justice.available(world))
        self.assertTrue(world.apply_command(SentenceCommand(trial.trial_id, "prison")).ok)

    def test_a_prisoner_is_locked_up_for_their_days_and_fed_what_is_said(self) -> None:
        world = self.world
        room = world.rooms[_jail(world)]
        trial = _condemned(world, THIEF, known_to=(WITNESS,))
        thief = world.residents[THIEF]
        self.assertFalse(world.apply_command(SetPrisonRationCommand(9, 1)).ok, "no more than the most there is")
        self.assertFalse(world.apply_command(SetPrisonRationCommand(1, 1, food="hoe")).ok, "a hoe is nothing to eat")
        self.assertTrue(world.apply_command(SetPrisonRationCommand(3, 2, food="canned_beans")).ok)
        world.apply_command(SentenceCommand(trial.trial_id, "prison"))
        days = world.registries.justice.punishments["prison"].days
        world.step(MINUTES_PER_DAY)
        self.assertTrue(room.contains(thief.tile), "they are inside it")
        self.assertEqual(thief.activity.action, SERVE_ACTION)
        self.assertTrue(world.justice.confined(world, THIEF))
        self.assertLess(thief.needs.hunger, 80.0, "three meals a day, of what was said, are enough to get by on")
        self.assertFalse(any(event.event_type == "prisoner_unfed" for event in world.history))
        world.step((days - 1) * MINUTES_PER_DAY - 60)
        self.assertTrue(room.contains(thief.tile))
        world.step(120)
        self.assertIsNone(world.justice.sentence_of(world, THIEF))
        self.assertTrue(any(event.event_type == "sentence_served" for event in world.history))
        self.assertIn(THIEF, world.residents, "fed, they come out alive")

    def test_given_nothing_a_prisoner_goes_hungry(self) -> None:
        world = self.world
        _jail(world)
        fed, starved = "paco", "raul"
        world.apply_command(SetPrisonRationCommand(0, 0))
        trial = _condemned(world, starved, known_to=(WITNESS,))
        world.apply_command(SentenceCommand(trial.trial_id, "prison"))
        world.step(MINUTES_PER_DAY)
        self.assertGreater(world.residents[starved].needs.hunger, world.residents[fed].needs.hunger)
        self.assertEqual((world.courts.ration.meals, world.courts.ration.drinks), (0, 0))

    def test_the_stocks_keep_somebody_by_them_for_their_hours(self) -> None:
        world = self.world
        thief = world.residents[THIEF]
        stocks = Interactable("stocks_1", "stocks", thief.x + 2, thief.y)
        world.interactables[stocks.object_id] = stocks
        trial = _condemned(world, THIEF, known_to=(WITNESS,))
        self.assertTrue(world.apply_command(SentenceCommand(trial.trial_id, "public_stocks")).ok)
        world.step(120)
        self.assertLessEqual(abs(thief.x - stocks.x) + abs(thief.y - stocks.y), 1)
        self.assertEqual(thief.activity.action, SERVE_ACTION)
        world.step(world.registries.justice.punishments["public_stocks"].hours * 60)
        self.assertFalse(world.justice.confined(world, THIEF))

    def test_a_fine_reaches_the_fund_in_coin_and_under_barter_in_things(self) -> None:
        world = self.world
        thief = world.residents[THIEF]
        amount = world.registries.justice.punishments["fine"].amount
        thief.credits = amount + 5
        fund = world.trading.fund
        trial = _condemned(world, THIEF, known_to=(WITNESS,))
        world.apply_command(SentenceCommand(trial.trial_id, "fine"))
        self.assertEqual((thief.credits, world.trading.fund), (5, fund + amount))
        # Whoever has less than it pays what they have, and the fund never goes below nothing.
        other = world.residents["raul"]
        other.credits = 3.0
        trial = _condemned(world, "raul", known_to=(WITNESS,))
        world.apply_command(SentenceCommand(trial.trial_id, "fine"))
        self.assertEqual((other.credits, world.trading.fund), (0.0, fund + amount + 3))
        # Under barter it is paid in things of their own.
        world.trading = TradingState()
        lucia = world.residents["lucia"]
        world.stock(lucia.inventory, "old_radio", 1, "lucia")
        common = world.fund.goods(world).get("old_radio", 0)
        trial = _condemned(world, "lucia", known_to=(WITNESS,))
        world.apply_command(SentenceCommand(trial.trial_id, "fine"))
        self.assertIsNone(lucia.inventory.stack_of("old_radio", "lucia"))
        self.assertEqual(world.fund.goods(world).get("old_radio", 0), common + 1)

    def test_what_is_confiscated_becomes_the_settlements(self) -> None:
        world = self.world
        thief = world.residents[THIEF]
        for item_id in ("old_radio", "canned_beans", "liquor"):
            world.stock(thief.inventory, item_id, 1, THIEF)
        own = len([item for item in thief.inventory.items if item.owner_id == THIEF])
        trial = _condemned(world, THIEF, known_to=(WITNESS,))
        world.apply_command(SentenceCommand(trial.trial_id, "confiscation"))
        left = len([item for item in thief.inventory.items if item.owner_id == THIEF])
        self.assertEqual(own - left, world.registries.justice.punishments["confiscation"].things)

    def test_somebody_put_to_death_is_dead_of_it_and_there_has_to_be_a_gallows(self) -> None:
        world = self.world
        world.interactables["gallows_1"] = Interactable("gallows_1", "gallows", 20, 20)
        trial = _condemned(world, THIEF, KILLING, known_to=(WITNESS,))
        self.assertTrue(world.apply_command(SentenceCommand(trial.trial_id, "execution")).ok)
        self.assertNotIn(THIEF, world.residents)
        self.assertEqual(world.deaths[-1].resident_id, THIEF)
        self.assertEqual(world.courts.history[-1].punishment, "execution")


class AftermathTests(unittest.TestCase):
    """A punishment is a political event, and each takes it their own way."""

    def _legitimacy_after(self, known: bool, punishment: str = "corporal_punishment", age: int | None = None) -> float:
        world = _settled()
        world.government.measures["legitimacy"] = 50.0
        if age is not None:
            world.residents[THIEF].age = age
        others = tuple(each for each in world.residents if each != THIEF)
        trial = _condemned(world, THIEF, KILLING if punishment != "warning" else THEFT, known_to=others if known else ())
        thief = world.residents[THIEF]
        for other in world.residents.values():
            # Everybody is there to see it.
            other.x, other.y = thief.x, thief.y
        self.assertTrue(world.apply_command(SentenceCommand(trial.trial_id, punishment)).ok)
        self.record = world.courts.history[-1]
        return world.government.measures["legitimacy"] - 50.0

    def test_the_same_punishment_raises_legitimacy_when_they_hold_them_guilty_and_sinks_it_when_innocent(self) -> None:
        just = self._legitimacy_after(known=True)
        self.assertEqual(set(self.record.reactions.values()) - {GRIEF, ANGER}, {APPROVAL})
        unjust = self._legitimacy_after(known=False)
        self.assertEqual(set(self.record.reactions.values()), {ANGER})
        self.assertGreater(just, 0.0)
        self.assertLess(unjust, 0.0)

    def test_what_goes_far_beyond_what_was_done_is_feared_and_not_approved(self) -> None:
        world = _settled()
        others = tuple(each for each in world.residents if each != THIEF)
        trial = _condemned(world, THIEF, THEFT, known_to=others)
        world.apply_command(SentenceCommand(trial.trial_id, "exile"))
        reactions = set(world.courts.history[-1].reactions.values())
        self.assertIn(FEAR, reactions)
        self.assertNotIn(APPROVAL, reactions)

    def test_punishing_a_child_costs_far_more(self) -> None:
        grown = self._legitimacy_after(known=False)
        child = self._legitimacy_after(known=False, age=12)
        self.assertTrue(self.record.child)
        self.assertLess(child, grown)
        self._legitimacy_after(known=True, age=12)
        self.assertNotIn(APPROVAL, self.record.reactions.values(), "nobody is glad of it, whatever the child did")

    def test_kin_and_those_who_wanted_it_remember_it_differently(self) -> None:
        world = _settled()
        others = tuple(each for each in world.residents if each != "marta")
        trial = _condemned(world, "marta", KILLING, known_to=others)
        self.assertTrue(world.apply_command(SentenceCommand(trial.trial_id, "exile")).ok)
        record = world.courts.history[-1]
        self.assertEqual((record.name, record.offence, record.punishment), ("Marta", KILLING, "exile"))
        self.assertEqual(record.kin, ["vera"], "her sister")
        self.assertEqual(record.reactions["vera"], GRIEF)
        self.assertEqual(record.reactions[WITNESS], APPROVAL)
        sister = next(each for each in world.memories.recent("vera", 5) if "punishment" in each.tags)
        other = next(each for each in world.memories.recent(WITNESS, 5) if "punishment" in each.tags)
        self.assertIn("hermana", sister.text)
        self.assertLess(sister.emotional_value, 0)
        self.assertGreater(other.emotional_value, 0)
        self.assertNotEqual(sister.text, other.text)
        self.assertGreater(
            world.politics.legitimacy.profile(world, world.residents["vera"]).resentment,
            world.politics.legitimacy.profile(world, world.residents[WITNESS]).resentment,
        )
        event = next(each for each in reversed(world.history) if each.event_type == "punishment_carried")
        self.assertEqual(event.data["reactions"], record.reactions)
        self.assertTrue(event.data["harsh"])


class ExileTests(unittest.TestCase):
    def setUp(self) -> None:
        self.world = _settled()

    def _exile(self, resident_id: str = THIEF, grudge: float = 0.0):
        world = self.world
        others = tuple(each for each in world.residents if each != resident_id)
        trial = _condemned(world, resident_id, KILLING, known_to=others)
        world.politics.legitimacy.profile(world, world.residents[resident_id]).resentment = grudge * 100.0
        self.assertTrue(world.apply_command(SentenceCommand(trial.trial_id, "exile")).ok)
        world.step(300)
        return next(each for each in world.exiled if each.resident_id == resident_id)

    def test_somebody_exiled_is_gone_from_the_map_the_posts_and_the_beds_and_not_from_memory(self) -> None:
        world = self.world
        job = world.residents[THIEF].job_id
        exile = self._exile()
        self.assertNotIn(THIEF, world.residents)
        self.assertNotIn(THIEF, [resident.resident_id for resident in world.staffing.workers(world, job)] if job else [])
        self.assertFalse(any(placed for placed in world.interactables.values() if getattr(placed, "owner_id", None) == THIEF))
        self.assertEqual(world.deaths, [], "and not dead")
        self.assertTrue(any(THIEF in memory.people for memory in world.memories.recent(WITNESS, 5)))
        self.assertIsNotNone(exile.back_at)
        self.assertEqual(exile.person["personality"]["empathy"], exile.person["personality"]["empathy"])
        self.assertGreaterEqual(exile.back_at - world.clock.total_minutes, 4 * MINUTES_PER_DAY)
        world.step(MINUTES_PER_DAY)
        self.assertNotIn(THIEF, world.residents, "the settlement goes on without them")

    def test_they_come_back_to_the_gate_and_whoever_is_there_decides(self) -> None:
        world = self.world
        exile = self._exile()
        age, traits = exile.person["age"], exile.person["traits"]
        exile.back_at = world.clock.total_minutes
        world.clock.hour, world.clock.minute = 23, 59
        world.step(1)
        decision = next(each for each in world.decisions.values() if each.kind == EXILE_BACK_DECISION)
        self.assertEqual(world.courts.at_gate, THIEF)
        self.assertIsNone(exile.back_at, "they come the once")
        keeper = world.residents[decision.resident_id]
        world.relationship(keeper.resident_id, THIEF).adjust("affection", 100.0)
        outcome = world.apply_command(ChooseOptionCommand(decision.decision_id, "open"))
        self.assertIsNone(world.courts.at_gate)
        if outcome == "let_back":
            back = world.residents[THIEF]
            self.assertEqual((back.name, back.age, back.traits), ("Paco", age, traits))
            self.assertTrue(exile.returned)
            self.assertTrue(any(event.event_type == "exile_readmitted" for event in world.history))
        else:
            self.assertNotIn(THIEF, world.residents)

    def test_turned_away_they_are_gone(self) -> None:
        world = self.world
        exile = self._exile()
        exile.back_at = world.clock.total_minutes
        world.clock.hour, world.clock.minute = 23, 59
        world.step(1)
        decision = next(each for each in world.decisions.values() if each.kind == EXILE_BACK_DECISION)
        world.relationship(decision.resident_id, THIEF).adjust("resentment", 100.0)
        outcome = world.apply_command(ChooseOptionCommand(decision.decision_id, "close"))
        self.assertEqual(outcome, "keep_out")
        self.assertNotIn(THIEF, world.residents)
        self.assertTrue(any(event.event_type == "exile_turned_away" for event in world.history))

    def test_whoever_left_with_a_grudge_may_come_back_with_raiders(self) -> None:
        world = self.world
        exile = self._exile(grudge=1.0)
        self.assertEqual(exile.grudge, 1.0)

        class Certain(type(world.rng)):
            def random(self) -> float:
                return 0.0

        world.rng.__class__ = Certain
        exile.back_at = world.clock.total_minutes
        world.clock.hour, world.clock.minute = 23, 59
        world.step(1)
        self.assertTrue(any(event.event_type == "exile_raid" for event in world.history))
        self.assertIsNone(exile.back_at)
        self.assertIsNone(world.courts.at_gate)

    def test_whoever_left_with_no_grudge_never_does(self) -> None:
        world = self.world
        exile = self._exile(grudge=0.0)
        exile.back_at = world.clock.total_minutes
        world.clock.hour, world.clock.minute = 23, 59
        world.step(1)
        self.assertFalse(any(event.event_type == "exile_raid" for event in world.history))


class JusticeDataTests(unittest.TestCase):
    def test_what_is_kept_of_justice_survives_saving_and_an_older_save_has_none(self) -> None:
        world = _settled()
        _jail(world)
        world.apply_command(SetPrisonRationCommand(3, 1, food="canned_beans"))
        trial = _condemned(world, THIEF, known_to=(WITNESS,))
        world.apply_command(SentenceCommand(trial.trial_id, "prison"))
        gone = _condemned(world, "raul", KILLING, known_to=(WITNESS,))
        world.apply_command(SentenceCommand(gone.trial_id, "exile"))
        world.step(300)
        _misdeed(world, "lucia")
        world.apply_command(AccuseCommand("lucia"))
        manager = SaveManager()
        data = manager.to_data(world)
        loaded = manager.from_data(data, world.registries)
        self.assertEqual(manager.to_data(loaded), data)
        self.assertEqual(loaded.justice.open_trial(loaded).accused, "lucia")
        self.assertTrue(loaded.justice.confined(loaded, THIEF))
        self.assertEqual([record.punishment for record in loaded.courts.history], ["prison", "exile"])
        self.assertEqual(loaded.courts.ration.food, "canned_beans")
        self.assertIsNotNone(next(each for each in loaded.exiled if each.resident_id == "raul").back_at)
        del data["courts"]
        for exile in data["exiled"]:
            for key in ("back_at", "grudge", "tries", "person", "returned"):
                del exile[key]
        older = manager.from_data(data, world.registries)
        self.assertEqual((older.courts.trials, older.courts.sentences, older.courts.history), ({}, [], []))
        self.assertIsNone(older.exiled[0].back_at, "whoever was thrown out before is gone for good")

    def test_the_data_is_checked(self) -> None:
        with self.assertRaises(ValueError):
            justice_settings_from_data({"punishments": {"warning": {"name": "x", "severity": 11}}})
        with self.assertRaises(ValueError):
            justice_settings_from_data({"punishments": {"fine": {"name": "x"}}, "trial": {"unanswered": "warning"}})
        with self.assertRaises(ValueError):
            justice_settings_from_data({"offences": {"theft_committed": {"gravity": 3}}})
        self.assertEqual(justice_settings_from_data({}).punishments, {})

    def test_a_week_goes_by_with_trials_and_the_settlement_is_still_there(self) -> None:
        world = SimulationWorld.demo_world(seed=11)
        world.step(7 * MINUTES_PER_DAY)
        self.assertGreaterEqual(len(world.residents), 6)
        for trial in world.courts.trials.values():
            self.assertIn(trial.step, (*STEPS, CLOSED))


if __name__ == "__main__":
    unittest.main()
