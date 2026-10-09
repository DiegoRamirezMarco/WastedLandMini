"""Leisure of their own accord (S62): wanting to be entertained is a need of its own."""

import json
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from save.save_manager import SaveManager
from simulation.ai.leisure import LEISURE_EVENT
from simulation.ai.routine_system import COMPANY_PULL, PASTIME_FROM, PASTIME_LIKING
from simulation.ai.utility_ai import BOREDOM_WEIGHT, need_urgency
from simulation.registries import builtin_registries
from simulation.residents.activity import Activity
from simulation.residents.needs import BOREDOM, BOREDOM_PACE, BOREDOM_START, NEED_NAMES, Needs
from simulation.residents.wishes import DO
from simulation.tastes.taste import TAG, Taste
from simulation.work.work_system import WORK_ACTIONS, WORK_SCORE
from simulation.world import SimulationWorld

ROOT = Path(__file__).resolve().parents[1]
MINUTES_PER_DAY = 24 * 60


def _types(world: SimulationWorld) -> list[str]:
    return [line.split(" | ")[1] for line in world.event_log]


def _idle(world: SimulationWorld, resident_id: str, boredom: float) -> object:
    """Somebody who wants for nothing but something to do, and holds no job."""
    resident = world.residents[resident_id]
    resident.needs = Needs(hunger=0, thirst=0, tiredness=0, social=0, stress=0, boredom=boredom)
    resident.job_id = resident.post_id = None
    resident.activity = None
    return resident


def _pastimes(world: SimulationWorld, resident) -> dict[str, float]:
    known = world.registries.leisure.pastimes
    return {
        each.name: each.score
        for each in world.activities.routine.candidates(world, resident)
        if each.name in known and each.target_id is None and each.partner_id is None
    }


class NeedTests(unittest.TestCase):
    def test_wanting_to_be_entertained_is_a_need_like_the_rest(self) -> None:
        self.assertIn(BOREDOM, NEED_NAMES)
        self.assertEqual(Needs().boredom, BOREDOM_START)
        needs = Needs(boredom=10.0)
        needs.apply({BOREDOM: -4.0})
        self.assertEqual(needs.boredom, 6.0)
        needs.apply({BOREDOM: -40.0})
        self.assertEqual(needs.boredom, 0.0)

    def test_it_sets_in_with_time_awake_and_not_asleep(self) -> None:
        needs = Needs(boredom=10.0)
        needs.step(60)
        self.assertAlmostEqual(needs.boredom, 10.0 + 60 * BOREDOM_PACE)
        asleep = Needs(boredom=10.0)
        asleep.step(60, resting=True)
        self.assertEqual(asleep.boredom, 10.0)
        long = Needs(boredom=10.0)
        long.step(10 * MINUTES_PER_DAY)
        self.assertEqual(long.boredom, 100.0)

    def test_bored_to_tears_is_still_less_than_work_is_worth(self) -> None:
        world = SimulationWorld.demo_world()
        marta = world.residents["marta"]
        marta.needs.boredom = 100.0
        self.assertEqual(need_urgency(marta, BOREDOM), BOREDOM_WEIGHT)
        self.assertLess(BOREDOM_WEIGHT, WORK_SCORE)
        marta.needs.boredom = 50.0
        self.assertAlmostEqual(need_urgency(marta, BOREDOM), BOREDOM_WEIGHT * 0.25)

    def test_it_weighs_on_their_spirits_a_little(self) -> None:
        world = SimulationWorld.demo_world()
        bored, content = world.residents["marta"], world.residents["vera"]
        for resident, boredom in ((bored, 100.0), (content, 0.0)):
            resident.needs = Needs(hunger=0, thirst=0, tiredness=0, social=0, stress=0, boredom=boredom)
            resident.mood = 60.0
            resident.injuries = []
            world.activities._settle_mood(resident)
        self.assertLess(bored.mood, content.mood)
        self.assertGreater(bored.mood, 59.0, "and no more than a little")

    def test_it_needs_no_pygame(self) -> None:
        code = (
            "import sys; from simulation.world import SimulationWorld; world = SimulationWorld.demo_world(); "
            "world.step(60 * 24); print('pygame' in sys.modules, max(r.needs.boredom for r in world.residents.values()) > 0)"
        )
        result = subprocess.run([sys.executable, "-c", code], cwd=ROOT, capture_output=True, text=True, check=True)
        self.assertEqual(result.stdout.strip().splitlines()[-1], "False True")


class DataTests(unittest.TestCase):
    def setUp(self) -> None:
        self.registries = builtin_registries()

    def test_every_pastime_passes_the_time(self) -> None:
        for pastime in self.registries.leisure.pastimes.values():
            self.assertLess(pastime.per_minute.get(BOREDOM, 0.0), 0.0, pastime.pastime_id)

    def test_company_entertains_and_a_quarrel_does_not(self) -> None:
        interactions = self.registries.interactions
        for interaction_id in ("chat", "joke", "cards", "stories", "dance"):
            self.assertLess(interactions.get(interaction_id).per_minute.get(BOREDOM, 0.0), 0.0, interaction_id)
        for interaction_id in ("argument", "fight", "insult", "breakup"):
            self.assertGreaterEqual(interactions.get(interaction_id).per_minute.get(BOREDOM, 0.0), 0.0, interaction_id)

    def test_work_bores_a_little(self) -> None:
        for job_id, job in self.registries.jobs.items():
            self.assertGreater(job.per_minute.get(BOREDOM, 0.0), 0.0, job_id)

    def test_things_entertain_and_drink_is_not_taken_to_for_want_of_something_to_do(self) -> None:
        kinds = self.registries.interactables
        self.assertLess(kinds.get("campfire").use.per_minute[BOREDOM], 0.0)
        self.assertLess(kinds.get("radio_set").use.per_minute[BOREDOM], 0.0)
        self.assertNotIn(BOREDOM, kinds.get("bar").use.per_minute)
        for kind in kinds.kinds():
            for use in kinds.get(kind).more:
                if use.trains is None:
                    self.assertLess(use.per_minute.get(BOREDOM, 0.0), 0.0, use.action)

    def test_what_is_found_to_pass_the_time_with_passes_it(self) -> None:
        finds = self.registries.finds.kinds
        for kind_id in ("found_trinket", "found_toy"):
            low, high = finds[kind_id].item["effects"][BOREDOM]
            self.assertLess(low, 0.0)
            self.assertLess(high, 0.0)


class OwnAccordTests(unittest.TestCase):
    def setUp(self) -> None:
        self.world = SimulationWorld.demo_world()
        self.world.clock.hour = 11

    def test_with_time_on_their_hands_and_bored_enough_they_weigh_every_pastime(self) -> None:
        world = self.world
        marta = _idle(world, "marta", PASTIME_FROM - 1)
        self.assertEqual(_pastimes(world, marta), {}, "not bored enough to bother")
        marta.needs.boredom = PASTIME_FROM + 20
        self.assertEqual(set(_pastimes(world, marta)), set(world.registries.leisure.pastimes))

    def test_bored_and_left_alone_they_pass_the_time_one_way_or_another(self) -> None:
        world = self.world
        marta = _idle(world, "marta", 90.0)
        marta.activity = world.activities.routine.plan(world, marta)
        action = marta.activity.action
        pastime = action in world.registries.leisure.pastimes
        thing = any(
            use.action == action and use.per_minute.get(BOREDOM, 0.0) < 0
            for kind in world.registries.interactables.kinds()
            for use in world.registries.interactables.get(kind).uses
        )
        self.assertTrue(pastime or thing or marta.activity.partner_id is not None, marta.activity)

    def test_with_nothing_else_there_it_is_a_pastime_they_take_up_and_it_passes_the_time(self) -> None:
        world = self.world
        marta = _idle(world, "marta", 90.0)
        for other in list(world.residents):
            if other != "marta":
                del world.residents[other]
        for object_id, placed in list(world.interactables.items()):
            if any(use.per_minute.get(BOREDOM, 0.0) < 0 for use in world.definition_of(placed).uses):
                del world.interactables[object_id]
        marta.activity = world.activities.routine.plan(world, marta)
        self.assertIn(marta.activity.action, world.registries.leisure.pastimes)
        for _ in range(15):
            world.step(1)
            marta.needs.hunger = marta.needs.thirst = 0.0
        self.assertLess(marta.needs.boredom, 90.0)
        self.assertIn(LEISURE_EVENT, _types(world))

    def test_they_take_to_what_they_like_before_what_they_loathe(self) -> None:
        world = self.world
        marta = _idle(world, "marta", 80.0)
        tags = world.tastes.profile(world, marta).tags
        tags["strolling"], tags["idling"] = Taste(leaning=80), Taste(leaning=-80)
        scored = _pastimes(world, marta)
        self.assertGreater(scored["stroll"], scored["sit"])
        tags["strolling"], tags["idling"] = Taste(leaning=-80), Taste(leaning=80)
        scored = _pastimes(world, marta)
        self.assertGreater(scored["sit"], scored["stroll"])

    def test_weighing_a_pastime_makes_no_taste_and_throws_none_of_the_settlements_dice(self) -> None:
        world = self.world
        marta = _idle(world, "marta", 80.0)
        tags = world.tastes.profile(world, marta).tags
        for pastime in world.registries.leisure.pastimes.values():
            tags.pop(pastime.taste, None)
        routine = world.activities.routine
        before = world.rng.get_state()
        scores = [routine._score_pastime(world, marta, pastime) for pastime in world.registries.leisure.pastimes.values()]
        self.assertTrue(all(score is not None and score > 0 for score in scores))
        self.assertEqual(world.rng.get_state(), before)
        self.assertFalse(any(pastime.taste in tags for pastime in world.registries.leisure.pastimes.values()))
        strolling = world.registries.leisure.pastimes["stroll"].taste
        self.assertEqual(
            world.tastes.inclination(world, marta, TAG, strolling), world.tastes.taste(world, marta, TAG, strolling).value
        )

    def test_nobody_naps_in_place_of_a_nights_sleep(self) -> None:
        """The rest there is in a pastime is not what it is taken up for."""
        world = self.world
        marta = _idle(world, "marta", 60.0)
        rested = _pastimes(world, marta)["nap"]
        marta.needs.tiredness = 95.0
        self.assertEqual(_pastimes(world, marta)["nap"], rested)

    def test_not_in_a_storm_nor_when_a_law_they_keep_has_them_indoors_or_quiet(self) -> None:
        world = self.world
        marta = _idle(world, "marta", 80.0)
        self.assertTrue(_pastimes(world, marta))
        with patch.object(type(world.happenings), "is_stormy", lambda _system, _world: True):
            self.assertEqual(_pastimes(world, marta), {})
        world.politics.laws.enact(world, "dry_law")
        self.assertTrue(_pastimes(world, marta), "a law that has nothing to say of it leaves it be")
        laws = type(world.politics.laws)
        with patch.object(laws, "indoors", lambda *_: True):
            self.assertEqual(_pastimes(world, marta), {})
        with patch.object(laws, "hushed", lambda *_: True):
            self.assertEqual(_pastimes(world, marta), {})

    def test_a_pastime_they_wish_for_is_weighed_bored_or_not(self) -> None:
        world = self.world
        marta = _idle(world, "marta", 0.0)
        self.assertEqual(_pastimes(world, marta), {})
        world.wishes.make(world, marta, DO, "stroll")
        scored = _pastimes(world, marta)
        self.assertEqual(set(scored), {"stroll"})
        self.assertAlmostEqual(scored["stroll"], world.registries.wishes.pull)
        marta.activity = world.activities.routine.plan(world, marta)
        self.assertEqual(marta.activity.action, "stroll", "and with nothing else to do, done")

    def test_nobody_leaves_their_post_for_it(self) -> None:
        """Bored to tears, and as fond of every pastime as anybody can be."""
        world = self.world
        self.assertLess(BOREDOM_WEIGHT * (1.0 + 100.0 / PASTIME_LIKING), WORK_SCORE)
        workers = [resident for resident in world.residents.values() if world.work.candidate(world, resident) is not None]
        self.assertTrue(workers)
        for worker in workers:
            worker.needs = Needs(hunger=0, thirst=0, tiredness=0, social=0, stress=0, boredom=100.0)
            tags = world.tastes.profile(world, worker).tags
            for pastime in world.registries.leisure.pastimes.values():
                tags[pastime.taste] = Taste(leaning=100)
            # What their work is right now: the post, an errand for it, or the radio for whoever keeps watch.
            work = world.work.candidate(world, worker)
            worker.activity = world.activities.routine.plan(world, worker)
            self.assertIn(worker.activity.action, (*WORK_ACTIONS, work.name), worker.name)

    def test_whoever_is_bored_is_the_readier_to_seek_company(self) -> None:
        world = self.world
        marta = _idle(world, "marta", 0.0)
        marta.needs.social = 50.0
        # Somebody who is staying where they are for a while, to go over to.
        world.residents["vera"].activity = Activity("wander", minutes_left=600, using=True)
        routine = world.activities.routine

        def talks() -> dict[str, float]:
            return {each.partner_id: each.score for each in routine.candidates(world, marta) if each.partner_id is not None}

        seeds = world.rng.get_state()
        content = talks()
        self.assertTrue(content)
        marta.needs.boredom = 100.0
        world.rng.set_state(seeds)
        bored = talks()
        self.assertEqual(set(bored), set(content))
        for partner_id, score in content.items():
            self.assertAlmostEqual(bored[partner_id] - score, COMPANY_PULL * BOREDOM_WEIGHT, msg=partner_id)

    def test_time_of_their_own_ends_when_their_shift_begins(self) -> None:
        """A pastime taken up unasked, and what a thing offers beside what it is for, are left
        when work calls. What they were told to do is not."""
        world = self.world
        worker = next(resident for resident in world.residents.values() if world.work.candidate(world, resident) is not None)
        worker.needs = Needs(hunger=0, thirst=0, tiredness=0, social=0, stress=40, boredom=80)
        worker.activity = Activity("sit", minutes_left=40, using=True)
        world.step(1)
        self.assertNotEqual(getattr(worker.activity, "action", None), "sit", "their shift is on")
        table = next(placed for placed in world.interactables.values() if placed.kind == "table")
        worker.needs = Needs(hunger=0, thirst=0, tiredness=0, social=0, stress=40, boredom=80)
        worker.activity = Activity("sit_table", table.object_id, minutes_left=40, using=True)
        world.step(1)
        self.assertNotEqual(getattr(worker.activity, "action", None), "sit_table")
        worker.needs = Needs(hunger=0, thirst=0, tiredness=0, social=0, stress=40, boredom=80)
        worker.activity = Activity("sit", minutes_left=40, using=True, ordered=True)
        world.step(1)
        self.assertEqual(worker.activity.action, "sit", "told to, they see it through")
        # Off shift, it is theirs to finish.
        idle = _idle(world, "marta", 80.0)
        idle.activity = Activity("sit", minutes_left=40, using=True)
        world.step(1)
        self.assertEqual(idle.activity.action, "sit")

    def test_a_thing_of_their_own_to_pass_the_time_with_is_wanted_for_it(self) -> None:
        world = self.world
        marta = _idle(world, "marta", 0.0)
        self.assertEqual(world.items._relief(marta, {BOREDOM: -20.0}), 0.0)
        marta.needs.boredom = 80.0
        self.assertAlmostEqual(world.items._relief(marta, {BOREDOM: -20.0}), BOREDOM_WEIGHT * 0.64)


class LongRunTests(unittest.TestCase):
    def test_ten_days_of_it_and_they_go_on_working_sleeping_and_eating(self) -> None:
        world = SimulationWorld.demo_world(seed=2)
        asleep = at_leisure = samples = 0
        boredom = 0.0
        pastimes = set(world.registries.leisure.pastimes)
        for _ in range(10 * 24):
            world.step(60)
            for resident in world.residents.values():
                samples += 1
                boredom += resident.needs.boredom
                activity = resident.activity
                asleep += activity is not None and activity.action == "sleep" and activity.using
                at_leisure += activity is not None and activity.action in pastimes
        self.assertEqual(world.deaths, [])
        self.assertNotIn("no_food", _types(world))
        self.assertGreater(asleep / samples, 0.22, "a night's sleep is still had")
        self.assertGreater(_types(world).count(LEISURE_EVENT), 5, "and pastimes are taken up unasked")
        self.assertGreater(at_leisure, 0)
        self.assertLess(boredom / samples, 60.0, "nobody is bored stiff the whole time")
        self.assertGreater(world.ledger.stock(world)["food"], 20)


class ScreenTests(unittest.TestCase):
    def test_every_need_has_its_bar_on_the_panel(self) -> None:
        from graphics.palette import PALETTE
        from ui.labels import NEED_LABELS
        from ui.resident_panel import NEED_COLORS

        self.assertEqual(set(NEED_LABELS), set(NEED_NAMES))
        self.assertEqual(set(NEED_COLORS), set(NEED_NAMES))
        self.assertEqual(NEED_LABELS[BOREDOM], "Tedio")
        self.assertIn(NEED_COLORS[BOREDOM], PALETTE)
        self.assertEqual(len(set(NEED_COLORS.values())), len(NEED_NAMES), "each its own colour")


class SaveTests(unittest.TestCase):
    def test_how_bored_somebody_is_is_saved(self) -> None:
        manager = SaveManager()
        world = SimulationWorld.demo_world()
        world.residents["marta"].needs.boredom = 73.5
        data = json.loads(json.dumps(manager.to_data(world)))
        self.assertEqual(manager.from_data(data).residents["marta"].needs.boredom, 73.5)

    def test_in_a_save_from_before_nobody_is_bored_yet(self) -> None:
        manager = SaveManager()
        world = SimulationWorld.demo_world()
        world.residents["marta"].needs.boredom = 73.5
        data = json.loads(json.dumps(manager.to_data(world)))
        for resident in data["residents"]:
            del resident["needs"]["boredom"]
        loaded = manager.from_data(data)
        self.assertEqual(loaded.residents["marta"].needs.boredom, BOREDOM_START)


if __name__ == "__main__":
    unittest.main()
