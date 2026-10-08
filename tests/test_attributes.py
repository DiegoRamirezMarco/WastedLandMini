"""Strength, constitution, dexterity, mind, senses and charisma (S46): what somebody is born
with, what each is good for, and how use raises it."""

import json
import subprocess
import sys
import unittest
from dataclasses import replace
from pathlib import Path

from save.save_manager import SaveManager
from simulation.commands import FoundResidentCommand
from simulation.health.injury import Injury
from simulation.knowledge.knowledge_system import witnesses_of
from simulation.residents.activity import Activity
from simulation.residents.attribute_system import GREW_EVENT
from simulation.residents.attributes import (
    ATTRIBUTES,
    CHARISMA,
    CONSTITUTION,
    DEXTERITY,
    EFFECTS,
    MIND,
    OWN,
    SENSES,
    STRENGTH,
    Attributes,
    attribute_settings_from_data,
)
from simulation.residents.needs import Needs
from simulation.residents.resident import Resident
from simulation.work import hauling
from simulation.work.job import job_definition_from_data
from simulation.work.work_system import WORK_ACTION
from simulation.world import SimulationWorld

ROOT = Path(__file__).resolve().parent.parent
DATA = json.loads((ROOT / "data" / "attributes.json").read_text(encoding="utf-8"))


def _settled(seed: int = 7) -> SimulationWorld:
    world = SimulationWorld.demo_world(seed=seed)
    world.relationships.clear()
    for resident in world.residents.values():
        resident.needs = Needs(hunger=0, tiredness=0, social=0, stress=0)
    return world


def _with(world: SimulationWorld, resident_id: str, **values: float) -> Resident:
    """Have a resident be so much of each attribute named, and as they were of the rest."""
    resident = world.residents[resident_id]
    had = world.attributes.of(world, resident)
    resident.attributes = replace(had, **{name: float(value) for name, value in values.items()})
    return resident


def _stranger(world: SimulationWorld, resident_id: str = "ada") -> Resident:
    resident = Resident(resident_id, resident_id.capitalize(), x=20, y=14)
    world.residents[resident_id] = resident
    return resident


class DataTests(unittest.TestCase):
    def test_there_are_six_each_with_a_name_and_three_letters(self) -> None:
        settings = SimulationWorld.demo_world().registries.attributes
        self.assertEqual(tuple(settings.attributes), ATTRIBUTES)
        names = [settings.attributes[name].name for name in ATTRIBUTES]
        self.assertEqual(names, ["Fuerza", "Constitución", "Destreza", "Mente", "Sentidos", "Carisma"])
        self.assertTrue(all(len(settings.attributes[name].short) == 3 for name in ATTRIBUTES))
        self.assertEqual((settings.lowest, settings.middle, settings.highest), (1.0, 5.0, 10.0))

    def test_what_each_is_good_for_is_data(self) -> None:
        settings = SimulationWorld.demo_world().registries.attributes
        self.assertEqual(set(settings.effects), set(EFFECTS))
        self.assertTrue(all(value > 0 for value in settings.effects.values()))

    def test_data_that_makes_no_sense_is_refused(self) -> None:
        for wrong in (
            {"effects": {"flying": 1.0}},
            {"practice": {"sleeping": 1.0}},
            {"practice": {"work": -1.0}},
            {"lowest": 6},
            {"inherit": 1.5},
            {"founder_points": 3},
            {"age": {"of": ["luck"]}},
            {"attributes": {**DATA["attributes"], "luck": {"name": "Suerte"}}},
            {"attributes": {name: values for name, values in DATA["attributes"].items() if name != "mind"}},
        ):
            with self.assertRaises(ValueError, msg=wrong):
                attribute_settings_from_data({**DATA, **wrong})

    def test_every_job_goes_by_one_of_them(self) -> None:
        jobs = SimulationWorld.demo_world().registries.jobs
        self.assertTrue(all(job.stat in ATTRIBUTES for job in jobs.values()), {j: jobs[j].stat for j in jobs})
        self.assertEqual((jobs["farmer"].stat, jobs["researcher"].stat, jobs["guard"].stat), (STRENGTH, MIND, SENSES))
        with self.assertRaises(ValueError):
            job_definition_from_data("odd", {"name": "Raro", "station": "bar", "shifts": [[8, 9]], "text": "x", "stat": "luck"})

    def test_attributes_need_no_pygame(self) -> None:
        check = (
            "import sys; import simulation.residents.attribute_system, save.save_manager; "
            "from simulation.world import SimulationWorld; world = SimulationWorld.demo_world(); world.step(120); "
            "sys.exit(1 if 'pygame' in sys.modules else 0)"
        )
        done = subprocess.run([sys.executable, "-c", check], cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(done.returncode, 0, done.stderr)


class BornWithTests(unittest.TestCase):
    def test_whoever_comes_has_what_the_seed_gives_them_always_the_same(self) -> None:
        world = _settled()
        ada = _stranger(world)
        self.assertIsNone(ada.attributes, "nothing is made until it is asked for")
        made = world.attributes.of(world, ada)
        settings = world.registries.attributes
        self.assertTrue(all(settings.lowest <= getattr(made, name) <= settings.highest for name in OWN))
        again = _settled()
        self.assertEqual(again.attributes.of(again, _stranger(again)), made)
        other = _settled(seed=8)
        self.assertNotEqual(other.attributes.of(other, _stranger(other)), made)
        self.assertNotEqual(world.attributes.of(world, _stranger(world, "bea")), made)

    def test_people_are_not_all_alike(self) -> None:
        world = _settled()
        values = [
            getattr(world.attributes.of(world, _stranger(world, f"one_{index}")), name)
            for index in range(40)
            for name in OWN
        ]
        self.assertLess(min(values), 3.5)
        self.assertGreater(max(values), 6.5)
        self.assertAlmostEqual(sum(values) / len(values), 5.0, delta=0.5)

    def test_the_nine_who_come_ready_made_are_as_the_game_says(self) -> None:
        world = SimulationWorld.demo_world()
        levels = world.attributes.levels
        self.assertEqual(levels(world, world.residents["tomas"])[STRENGTH], 7)
        self.assertEqual(levels(world, world.residents["vera"])[MIND], 8)
        self.assertEqual(levels(world, world.residents["paco"])[MIND], 3)
        self.assertEqual(set(levels(world, world.residents["marta"])), set(ATTRIBUTES))

    def test_charisma_is_the_side_of_their_way_of_being_that_goes_by_that_name(self) -> None:
        world = _settled()
        marta = world.residents["marta"]
        marta.personality.charisma = 100.0
        self.assertEqual(world.attributes.raw(world, marta, CHARISMA), 10.0)
        marta.personality.charisma = 0.0
        self.assertEqual(world.attributes.raw(world, marta, CHARISMA), 1.0)
        self.assertFalse(hasattr(marta.attributes, CHARISMA), "there is one of it, not two")

    def test_the_first_resident_is_as_the_player_made_them(self) -> None:
        world = SimulationWorld.new_settlement()
        given = {STRENGTH: 8, CONSTITUTION: 6, DEXTERITY: 4, MIND: 5, SENSES: 3, CHARISMA: 7}
        resident_id = world.apply_command(FoundResidentCommand("Ada", 30, attributes=given))
        ada = world.residents[resident_id]
        self.assertEqual(world.attributes.levels(world, ada), given)
        self.assertAlmostEqual(ada.personality.charisma, (7 - 1) / 9 * 100, places=1)

    def test_all_six_come_to_no_more_than_there_are_points_for(self) -> None:
        world = SimulationWorld.new_settlement()
        points = world.registries.attributes.founder_points
        resident_id = world.apply_command(FoundResidentCommand("Ada", 30, attributes={name: 10 for name in ATTRIBUTES}))
        ada = world.residents[resident_id]
        total = sum(world.attributes.raw(world, ada, name) for name in ATTRIBUTES)
        self.assertAlmostEqual(total, points, delta=0.1)
        lopsided = SimulationWorld.new_settlement()
        resident_id = lopsided.apply_command(FoundResidentCommand("Bea", 30, attributes={STRENGTH: 10, MIND: 1}))
        bea = lopsided.residents[resident_id]
        self.assertEqual(lopsided.attributes.raw(lopsided, bea, STRENGTH), 10.0, "within the points nothing is touched")
        self.assertEqual(lopsided.attributes.raw(lopsided, bea, MIND), 1.0)
        self.assertEqual(lopsided.attributes.raw(lopsided, bea, SENSES), 5.0, "and what is left out is in the middle")

    def test_made_with_nothing_said_they_have_what_the_seed_gives(self) -> None:
        world = SimulationWorld.new_settlement()
        resident_id = world.apply_command(FoundResidentCommand("Ada", 30))
        self.assertIsNone(world.residents[resident_id].attributes)
        self.assertEqual(set(world.attributes.levels(world, world.residents[resident_id])), set(ATTRIBUTES))

    def test_a_child_takes_after_whichever_parents_live_here(self) -> None:
        world = _settled()
        _with(world, "tomas", strength=10, mind=10)
        _with(world, "ines", strength=10, mind=10)
        child = _stranger(world, "nino")
        world.family.kin.record(world, "nino", "Nino", "m").parents = ["tomas", "ines"]
        orphan = _stranger(world, "nina")
        theirs, alone = world.attributes.of(world, child), world.attributes.of(world, orphan)
        self.assertGreaterEqual(theirs.strength, 7.0)
        self.assertGreaterEqual(theirs.mind, 7.0)
        inherit = world.registries.attributes.inherit
        own = (theirs.strength - inherit * 10.0) / (1.0 - inherit)
        self.assertTrue(1.0 <= own <= 10.0, "the rest is their own")
        self.assertNotEqual(theirs, alone)


class TodayTests(unittest.TestCase):
    def test_the_years_take_from_the_body_and_not_from_the_head(self) -> None:
        world = _settled()
        vera = _with(world, "vera", strength=6, mind=8)
        settings = world.registries.attributes
        vera.age = settings.age_from
        self.assertEqual(world.attributes.value(world, vera, STRENGTH), 6.0)
        vera.age = settings.age_from + 25
        self.assertAlmostEqual(world.attributes.value(world, vera, STRENGTH), 6.0 - 25 * settings.age_per_year)
        self.assertEqual(world.attributes.value(world, vera, MIND), 8.0)
        self.assertEqual(world.attributes.raw(world, vera, STRENGTH), 6.0, "what they have is untouched")

    def test_a_child_has_not_all_their_strength_yet(self) -> None:
        world = _settled()
        ines = _with(world, "ines", strength=8, dexterity=8)
        ines.age = 8
        self.assertLess(world.attributes.value(world, ines, STRENGTH), 8.0)
        self.assertEqual(world.attributes.value(world, ines, DEXTERITY), 8.0)
        ines.age = world.registries.attributes.grown_at
        self.assertEqual(world.attributes.value(world, ines, STRENGTH), 8.0)

    def test_whoever_is_hurt_can_do_less_until_they_mend(self) -> None:
        world = _settled()
        raul = _with(world, "raul", strength=8, mind=6)
        raul.injuries = [Injury("fracture", 50.0)]
        self.assertAlmostEqual(world.attributes.value(world, raul, STRENGTH), 8.0 * 0.75)
        self.assertEqual(world.attributes.value(world, raul, MIND), 6.0)
        raul.injuries = []
        self.assertEqual(world.attributes.value(world, raul, STRENGTH), 8.0)

    def test_nothing_falls_below_the_lowest(self) -> None:
        world = _settled()
        paco = _with(world, "paco", strength=1)
        paco.age = 90
        self.assertEqual(world.attributes.value(world, paco, STRENGTH), 1.0)
        self.assertEqual(world.attributes.level(world, paco, STRENGTH), 1)


class WhatItChangesTests(unittest.TestCase):
    def _minutes_to_a_unit(self, strength: float) -> int:
        world = _settled()
        raul = _with(world, "raul", strength=strength)
        job = world.registries.jobs["farmer"]
        placed = world.interactables[raul.post_id]
        raul.work_progress = 0
        for minute in range(1, 200):
            world.work._produce(world, raul, job, placed, 300)
            if hauling.carried(raul, job.produces.item) > 0:
                return minute
        return 0

    def test_whoever_has_more_of_what_the_job_goes_by_does_it_faster(self) -> None:
        weak, middling, strong = (self._minutes_to_a_unit(strength) for strength in (2, 5, 9))
        self.assertGreater(weak, middling)
        self.assertGreater(middling, strong)
        world = _settled()
        raul = _with(world, "raul", strength=5, mind=10)
        self.assertEqual(world.attributes.work_pace(world, raul, world.registries.jobs["farmer"]), 1.0)
        self.assertGreater(world.attributes.work_pace(world, raul, world.registries.jobs["researcher"]), 1.0)

    def test_a_strong_arm_deals_more_and_quick_feet_take_less(self) -> None:
        fight = SimulationWorld.demo_world().registries.interactions["fight"]

        def dealt(strength: float, dexterity: float) -> float:
            world = _settled()
            _with(world, "raul", strength=strength)
            victim = _with(world, "paco", dexterity=dexterity, constitution=5)
            world.health.fight_damage(world, victim, world.residents["raul"], fight)
            return sum(injury.severity for injury in victim.injuries)

        self.assertGreater(dealt(9, 5), dealt(5, 5))
        self.assertGreater(dealt(5, 5), dealt(2, 5))
        self.assertGreater(dealt(5, 2), dealt(5, 9))

    def test_the_same_blow_comes_out_worse_in_a_weak_constitution(self) -> None:
        def left(constitution: float) -> float:
            world = _settled()
            paco = _with(world, "paco", constitution=constitution)
            world.health.hurt(world, paco, 20.0, "bruise", "una caída")
            return paco.health

        self.assertGreater(left(9), left(5))
        self.assertGreater(left(5), left(2))
        self.assertEqual(left(5), 80.0)

    def test_a_strong_constitution_mends_sooner(self) -> None:
        def after_a_day(constitution: float) -> float:
            world = _settled()
            paco = _with(world, "paco", constitution=constitution)
            paco.injuries = [Injury("fracture", 40.0)]
            for _ in range(24 * 60):
                world.health.tick(world, paco)
            return paco.health

        self.assertGreater(after_a_day(9), after_a_day(5))
        self.assertGreater(after_a_day(5), after_a_day(2))

    def test_work_tires_a_strong_constitution_less(self) -> None:
        world = _settled()
        job = world.registries.jobs["farmer"]
        usual = job.per_minute["tiredness"]
        self.assertEqual(world.work._toll(world, _with(world, "raul", constitution=5), job)["tiredness"], usual)
        self.assertLess(world.work._toll(world, _with(world, "raul", constitution=9), job)["tiredness"], usual)
        self.assertGreater(world.work._toll(world, _with(world, "raul", constitution=2), job)["tiredness"], usual)
        cook = world.registries.jobs["cook"]
        self.assertIs(world.work._toll(world, world.residents["marta"], cook), cook.per_minute, "what does not tire is left be")

    def test_the_strong_carry_more_in_one_trip(self) -> None:
        world = _settled()
        rule = world.registries.jobs["farmer"].produces
        self.assertEqual(hauling.load(world, _with(world, "raul", strength=5), rule), rule.carry)
        self.assertGreater(hauling.load(world, _with(world, "raul", strength=9), rule), rule.carry)
        self.assertLess(hauling.load(world, _with(world, "raul", strength=1), rule), rule.carry)
        self.assertGreaterEqual(hauling.load(world, _with(world, "raul", strength=1), replace(rule, carry=1)), 1)

    def test_a_good_head_works_things_out_sooner(self) -> None:
        def progress(mind: float) -> float:
            world = _settled()
            vera = _with(world, "vera", mind=mind)
            subject = next(iter(world.registries.research.subjects.values()))
            world.studies.known = [each for each in world.studies.known if each != subject.subject_id]
            world.studies.subject_id = subject.subject_id
            world.studies.supplied.append(subject.subject_id)
            world.studies.progress[subject.subject_id] = 0.0
            desk = next(iter(world.interactables.values()))
            world.research.work(world, vera, desk)
            return world.studies.progress.get(subject.subject_id, 0.0)

        self.assertGreater(progress(9), progress(5))
        self.assertGreater(progress(5), progress(2))

    def test_sharp_senses_see_further(self) -> None:
        world = _settled()
        world.clock.hour = 12
        for resident in world.residents.values():
            resident.x, resident.y, resident.activity = 2, 30, None
        nuria = world.residents["nuria"]
        nuria.x, nuria.y = 40, 11
        far = (40 + 9, 11)
        _with(world, "nuria", senses=5)
        self.assertNotIn("nuria", witnesses_of(world, far))
        _with(world, "nuria", senses=10)
        self.assertIn("nuria", witnesses_of(world, far))
        near = (40 + 7, 11)
        _with(world, "nuria", senses=1)
        self.assertNotIn("nuria", witnesses_of(world, near))
        _with(world, "nuria", senses=5)
        self.assertIn("nuria", witnesses_of(world, near))

    def test_sharp_senses_bring_more_back_and_bring_it_back_safer(self) -> None:
        def trip(senses: float):
            world = _settled()
            sergio = _with(world, "sergio", senses=senses)
            world.expeditions.set_out(world, sergio, world.registries.jobs["scavenger"])
            return sergio.expedition

        dull, sharp = trip(1), trip(10)
        self.assertGreater(sharp.finds, dull.finds)
        self.assertLess(sharp.danger, dull.danger)


class PracticeTests(unittest.TestCase):
    def test_a_day_at_the_post_raises_what_the_job_goes_by(self) -> None:
        world = _settled()
        raul = _with(world, "raul", strength=5, mind=5)
        raul.activity = Activity(WORK_ACTION, raul.post_id, [], 480, using=True)
        for _ in range(240):
            world.work.tick(world, raul, raul.activity)
            if raul.activity is None:
                raul.activity = Activity(WORK_ACTION, raul.post_id, [], 480, using=True)
        self.assertGreater(raul.attributes.strength, 5.0)
        self.assertEqual(raul.attributes.mind, 5.0, "and nothing else")

    def test_the_higher_it_is_the_slower_it_comes(self) -> None:
        world = _settled()

        def gained(start: float) -> float:
            raul = _with(world, "raul", strength=start)
            world.attributes.practise(world, raul, STRENGTH, "work", times=1000)
            return raul.attributes.strength - start

        self.assertGreater(gained(2), gained(5))
        self.assertGreater(gained(5), gained(8))
        self.assertEqual(gained(10), 0.0, "and there is no going past the highest")

    def test_a_whole_point_more_is_said(self) -> None:
        world = _settled()
        raul = _with(world, "raul", strength=5.99)
        world.attributes.practise(world, raul, STRENGTH, "work", times=200)
        lines = [line for line in world.event_log if GREW_EVENT in line]
        self.assertEqual(len(lines), 1)
        self.assertIn("Raúl gana en fuerza: 6", lines[0])
        world.attributes.practise(world, raul, STRENGTH, "work", times=1)
        self.assertEqual(len([line for line in world.event_log if GREW_EVENT in line]), 1, "and only then")

    def test_a_fight_hardens_both_and_coming_through_an_injury_hardens_too(self) -> None:
        world = _settled()
        raul = _with(world, "raul", strength=5)
        paco = _with(world, "paco", dexterity=5, constitution=5)
        world.health.fight_damage(world, paco, raul, world.registries.interactions["fight"])
        self.assertGreater(raul.attributes.strength, 5.0)
        self.assertGreater(paco.attributes.dexterity, 5.0)
        self.assertGreater(paco.attributes.constitution, 5.0)

    def test_leading_tells_on_whoever_leads(self) -> None:
        world = _settled()
        world.politics.leadership.establish(world, "strong_mayor")
        leader = world.residents[world.government.leader]
        other = next(resident for resident in world.residents.values() if resident is not leader)
        before, theirs = leader.personality.charisma, other.personality.charisma
        world.attributes.tick_day(world)
        self.assertGreater(leader.personality.charisma, before)
        self.assertEqual(other.personality.charisma, theirs)

    def test_what_nothing_raises_stays_where_it_was(self) -> None:
        world = _settled()
        raul = _with(world, "raul", strength=5)
        world.attributes.practise(world, raul, None, "work")
        world.attributes.practise(world, raul, STRENGTH, "juggling")
        self.assertEqual(raul.attributes.strength, 5.0)


class SaveTests(unittest.TestCase):
    def test_what_each_is_capable_of_comes_back_as_it_was(self) -> None:
        world = _settled()
        _with(world, "raul", strength=7.35, senses=2.5)
        ada = _stranger(world)
        manager = SaveManager()
        saved = manager.to_data(world)
        self.assertEqual(saved["version"], manager.CURRENT_VERSION)
        loaded = manager.from_data(json.loads(json.dumps(saved)))
        self.assertEqual(loaded.residents["raul"].attributes, world.residents["raul"].attributes)
        self.assertIsNone(loaded.residents["ada"].attributes, "whoever was never asked still has not been")
        self.assertEqual(loaded.attributes.of(loaded, loaded.residents["ada"]), world.attributes.of(world, ada))

    def test_in_a_save_from_before_everybody_has_what_the_seed_gives_them(self) -> None:
        world = _settled()
        saved = SaveManager().to_data(world)
        saved["version"] = 35
        for resident in saved["residents"]:
            resident.pop("attributes")
        loaded = SaveManager().from_data(json.loads(json.dumps(saved)))
        again = SaveManager().from_data(json.loads(json.dumps(saved)))
        self.assertIsNone(loaded.residents["raul"].attributes)
        levels = loaded.attributes.levels(loaded, loaded.residents["raul"])
        self.assertEqual(levels, again.attributes.levels(again, again.residents["raul"]))
        self.assertTrue(all(1 <= level <= 10 for level in levels.values()))

    def test_what_was_saved_out_of_bounds_is_brought_back_in(self) -> None:
        world = _settled()
        saved = SaveManager().to_data(world)
        saved["residents"][0]["attributes"] = {"strength": 99, "mind": -4}
        loaded = SaveManager().from_data(json.loads(json.dumps(saved)))
        first = next(iter(loaded.residents.values()))
        self.assertEqual(first.attributes, Attributes(strength=10.0, mind=1.0))


if __name__ == "__main__":
    unittest.main()
