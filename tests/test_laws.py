import unittest
from dataclasses import replace

from simulation.events.event import DomainEvent
from simulation.politics.law import EFFECTS, law_definition_from_data, law_settings_from_data
from simulation.politics.proposal import ENACT_LAW
from simulation.politics.records import ACCEPTED
from simulation.registries import BuiltInRegistries
from simulation.residents.activity import ATTEND_ACTION, RETIRE_ACTION, Activity
from simulation.residents.needs import Needs
from simulation.work.work_system import minutes_left_in_shift
from simulation.world import SimulationWorld

SERIOUS = (
    "curfew", "rest_day", "long_hours", "short_hours", "low_wages", "high_wages", "tax", "rationing",
    "common_property", "dry_law", "substance_ban", "closed_gate", "free_meals", "pregnancy_rest",
)
ABSURD = (
    "silent_siesta", "radio_hour", "salute", "banned_food", "daily_round", "leader_birthday", "no_fire", "lights_out",
)


def _settled(seed: int = 7) -> SimulationWorld:
    """The ready-made settlement with nothing felt by anyone for anyone, and nobody in need."""
    world = SimulationWorld.demo_world(seed=seed)
    world.relationships.clear()
    for resident in world.residents.values():
        resident.needs = Needs(hunger=0, tiredness=0, social=0, stress=0)
    return world


def _governed(kind: str = "strong_mayor", seed: int = 7) -> SimulationWorld:
    world = _settled(seed)
    world.registries = replace(world.registries, politics=replace(world.registries.politics, election_hours=1))
    world.politics.leadership.establish(world, kind)
    return world


def _types(world: SimulationWorld) -> list[str]:
    return [line.split(" | ")[1] for line in world.event_log]


def _broken(world: SimulationWorld) -> list[tuple[str, str]]:
    """Who has been seen to break which law, in the order it was seen."""
    return [
        (event.data["resident_id"], event.data["law"])
        for event in world.history
        if event.event_type == "law_broken"
    ]


def _held(world: SimulationWorld, resident_id: str):
    return world.politics.legitimacy.profile(world, world.residents[resident_id])


def _obeys(world: SimulationWorld, *resident_ids: str) -> None:
    """Have residents do as the government says whatever it says: loyal, trusting and afraid."""
    for resident_id in resident_ids:
        profile = _held(world, resident_id)
        profile.loyalty, profile.trust, profile.fear, profile.fearfulness = 100.0, 100.0, 100.0, 100.0


def _defies(world: SimulationWorld, *resident_ids: str) -> None:
    """Have residents owe the government nothing, under one nobody thinks legitimate."""
    world.government.measures["legitimacy"] = 0.0
    for resident_id in resident_ids:
        profile = _held(world, resident_id)
        profile.loyalty, profile.trust, profile.fear, profile.authoritarian_tolerance = 0.0, 0.0, 0.0, 0.0


def _steady(world: SimulationWorld) -> SimulationWorld:
    """The same world with the bar for keeping a law standing in the same place every day."""
    world.registries = replace(world.registries, laws=replace(world.registries.laws, keep_jitter=0.0))
    return world


def _at(world: SimulationWorld, hour: int, minute: int = 0) -> None:
    world.clock.hour, world.clock.minute = hour, minute


def _awake_at(world: SimulationWorld, resident_id: str, tile: tuple[int, int]) -> None:
    resident = world.residents[resident_id]
    resident.x, resident.y = tile
    resident.activity = Activity("wander", minutes_left=600, using=True)


def _put_away(world: SimulationWorld, *but: str) -> None:
    """Have everybody but those named be out of the way: asleep in the graveyard's far corner."""
    for index, resident in enumerate(world.residents.values()):
        if resident.resident_id in but:
            continue
        resident.x, resident.y = 54 + index % 4, 27 + index // 4
        resident.activity = Activity("sleep_rough", minutes_left=6000, using=True)


def _free(world: SimulationWorld, resident_id: str) -> None:
    world.residents[resident_id].activity = None
    world.residents[resident_id].job_id = None
    world.residents[resident_id].post_id = None


class LawDataTests(unittest.TestCase):
    def test_the_laws_there_are_to_begin_with_serious_and_absurd(self) -> None:
        laws = SimulationWorld.demo_world().registries.laws.laws
        self.assertEqual(set(laws), {*SERIOUS, *ABSURD})
        for law_id in SERIOUS:
            self.assertFalse(laws[law_id].absurd, law_id)
        for law_id in ABSURD:
            self.assertTrue(laws[law_id].absurd, law_id)
            self.assertTrue(laws[law_id].whim, law_id)
            self.assertTrue(laws[law_id].whim_opinion, law_id)

    def test_a_law_is_never_only_words(self) -> None:
        laws = SimulationWorld.demo_world().registries.laws.laws
        done = set()
        for law in laws.values():
            for degree in law.degrees:
                self.assertTrue(degree.effects, law.law_id)
                self.assertTrue(set(degree.effects) <= set(EFFECTS), law.law_id)
                done |= set(degree.effects)
        self.assertEqual(done, set(EFFECTS), "and there is a law for everything a law can do")

    def test_a_law_goes_from_mild_to_harsh(self) -> None:
        laws = SimulationWorld.demo_world().registries.laws.laws
        curfew = laws["curfew"]
        self.assertEqual(len(curfew.degrees), 3)
        weights = [degree.weight for degree in curfew.degrees]
        self.assertEqual(weights, sorted(weights))
        self.assertEqual([degree.effects["meals"] for degree in laws["rationing"].degrees], [3, 2, 1])

    def test_a_law_that_makes_no_sense_is_refused(self) -> None:
        sound = {"name": "Ley", "text": "algo", "degrees": [{"name": "así", "effects": {"closes": ["bar"]}}]}
        law_definition_from_data("one", sound)
        for wrong in (
            {"name": "Ley", "text": "algo"},
            {**sound, "degrees": []},
            {**sound, "degrees": [{"name": "nada", "effects": {}}]},
            {**sound, "degrees": [{"name": "magia", "effects": {"summons_rain": True}}]},
            {**sound, "degrees": [{"name": "horas", "effects": {"curfew": [22, 30]}}]},
            {**sound, "degrees": [{"name": "todo", "effects": {"tax": 1.0}}]},
            {**sound, "degrees": [{"name": "puerta", "effects": {"gate": "ajar"}}]},
            {**sound, "degrees": [{"name": "quién", "effects": {"excused": ["the lucky"]}}]},
            {**sound, "degrees": [{"name": "peso", "effects": {"closes": ["bar"]}, "weight": 0}]},
            {**sound, "degrees": [{"name": "veto", "effects": {"bans_item": True}}]},
            {**sound, "param": "hated_food"},
            {**sound, "param": "favourite_colour"},
            {**sound, "opinion": {"luck": 1}},
            {**sound, "whim_opinion": {"luck": 1}},
            {**sound, "motive": {"full_moon": True}},
            {**sound, "burden": 2},
        ):
            with self.assertRaises(ValueError, msg=wrong):
                law_definition_from_data("one", wrong)
        with self.assertRaises(ValueError):
            law_settings_from_data({"laws": {"one": {**sound, "excludes": ["two"]}}})

    def test_a_law_cannot_name_a_kind_of_object_there_is_not(self) -> None:
        registries = BuiltInRegistries.load()
        ghost = law_definition_from_data(
            "one", {"name": "Ley", "text": "algo", "degrees": [{"name": "así", "effects": {"closes": ["throne"]}}]}
        )
        registries.laws = replace(registries.laws, laws={**registries.laws.laws, "one": ghost})
        with self.assertRaises(ValueError):
            registries.validate()


class KeepingTests(unittest.TestCase):
    def test_keeping_a_law_goes_by_how_far_each_does_as_the_government_says(self) -> None:
        world = _steady(_governed())
        world.politics.laws.enact(world, "curfew", 1)
        laws = world.politics.laws
        world.government.measures["legitimacy"] = 0.0
        for resident_id in ("paco", "nuria"):
            profile = _held(world, resident_id)
            profile.loyalty, profile.trust, profile.fear = 0.0, 0.0, 0.0
        self.assertFalse(laws.keeps(world, world.residents["paco"], "curfew"))
        self.assertFalse(laws.keeps(world, world.residents["nuria"], "curfew"))
        _held(world, "paco").loyalty = 100.0
        self.assertTrue(laws.keeps(world, world.residents["paco"], "curfew"), "out of loyalty")
        _held(world, "nuria").fear, _held(world, "nuria").fearfulness = 100.0, 100.0
        self.assertTrue(laws.keeps(world, world.residents["nuria"], "curfew"), "or out of fear")
        self.assertGreater(_held(world, "nuria").fear, 50.0)

    def test_what_they_make_of_the_law_and_how_legitimate_the_government_is_count_too(self) -> None:
        world = _steady(_governed())
        world.politics.laws.enact(world, "dry_law")
        laws = world.politics.laws
        raul = world.residents["raul"]
        _defies(world, "raul")
        self.assertFalse(laws.keeps(world, raul, "dry_law"))
        world.government.measures["legitimacy"] = 100.0
        _held(world, "raul").trust, _held(world, "raul").loyalty = 100.0, 30.0
        legitimate = laws.keeps(world, raul, "dry_law")
        world.government.measures["legitimacy"] = 0.0
        self.assertTrue(legitimate and not laws.keeps(world, raul, "dry_law"), "the same man keeps what a government he holds to passes")
        # Somebody who is all for it keeps it with no government to speak of behind it.
        _held(world, "raul").authoritarian_tolerance, _held(world, "raul").justice_sensitivity = 100.0, 100.0
        raul.personality.sociability, raul.personality.empathy = 0.0, 100.0
        self.assertGreater(laws.regard(world, raul, "dry_law"), 0.3)
        self.assertTrue(laws.keeps(world, raul, "dry_law"))

    def test_a_law_that_is_a_burden_is_kept_by_fewer(self) -> None:
        world = _governed("direct_democracy")
        world.registries = replace(
            world.registries,
            laws=replace(
                world.registries.laws,
                keep_jitter=0.0,
                laws={
                    **world.registries.laws.laws,
                    "dry_law": replace(world.registries.laws.laws["dry_law"], burden=0.0, opinion={}, bias=0.0),
                },
            ),
        )
        world.politics.laws.enact(world, "dry_law")
        laws = world.politics.laws
        light = sum(laws.keeps(world, resident, "dry_law") for resident in world.residents.values())
        heavy_law = replace(world.registries.laws.laws["dry_law"], burden=1.0)
        world.registries = replace(
            world.registries, laws=replace(world.registries.laws, laws={**world.registries.laws.laws, "dry_law": heavy_law})
        )
        heavy = sum(laws.keeps(world, resident, "dry_law") for resident in world.residents.values())
        self.assertEqual(light, 9)
        self.assertLess(heavy, light)

    def test_it_is_the_same_answer_all_day_and_draws_on_no_randomness(self) -> None:
        world = _governed("direct_democracy")
        world.politics.laws.enact(world, "curfew", 1)
        laws = world.politics.laws
        state = world.rng.get_state()
        first = {resident_id: laws.keeps(world, resident, "curfew") for resident_id, resident in world.residents.items()}
        for _ in range(3):
            again = {resident_id: laws.keeps(world, resident, "curfew") for resident_id, resident in world.residents.items()}
            self.assertEqual(again, first)
        self.assertEqual(world.rng.get_state(), state)
        self.assertIn(True, first.values())
        self.assertIn(False, first.values(), "with nobody leading, some keep it and some do not")

    def test_whoever_leads_keeps_the_law_as_anybody_half_loyal_would(self) -> None:
        world = _governed()
        world.politics.laws.enact(world, "curfew", 1)
        leader = world.residents[world.government.leader]
        self.assertEqual(_held(world, leader.resident_id).loyalty, 0.0, "nobody is loyal to themselves")
        self.assertTrue(world.politics.laws.keeps(world, leader, "curfew"))


class CurfewTests(unittest.TestCase):
    def _night(self, kind: str = "strong_mayor") -> SimulationWorld:
        world = _governed(kind)
        world.politics.laws.enact(world, "curfew", 1)
        _at(world, 23)
        return world

    def test_whoever_keeps_it_gets_indoors_and_stays_there(self) -> None:
        world = self._night()
        _obeys(world, "paco")
        _put_away(world, "paco")
        _free(world, "paco")
        paco = world.residents["paco"]
        paco.x, paco.y = 20, 12
        self.assertFalse(world.under_roof(paco.tile))
        self.assertTrue(world.politics.laws.indoors(world, paco))
        planned = world.activities.routine.plan(world, paco)
        self.assertEqual(planned.action, RETIRE_ACTION)
        self.assertTrue(world.under_roof(planned.path[-1]))
        world.step(40)
        self.assertTrue(world.under_roof(paco.tile))
        for _ in range(12):
            world.step(20)
            # Once in, the only thing that takes him across open ground is the way to his bed.
            to_bed = paco.activity is not None and paco.activity.action == "sleep"
            self.assertTrue(world.under_roof(paco.tile) or to_bed, world.clock.label)
        self.assertEqual(_broken(world), [])

    def test_when_it_begins_whoever_keeps_it_and_is_strolling_in_the_open_stops(self) -> None:
        world = _governed()
        world.politics.laws.enact(world, "curfew", 1)
        _obeys(world, "paco")
        _defies(world, "sergio")
        for resident_id in ("paco", "sergio"):
            _awake_at(world, resident_id, (20, 12))
        world.residents["sergio"].x = 22
        _at(world, 22, 0)
        world.politics.laws.tick(world)
        self.assertIsNone(world.residents["paco"].activity)
        self.assertIsNotNone(world.residents["sergio"].activity)

    def test_by_day_it_asks_nothing_of_anybody(self) -> None:
        world = self._night()
        _obeys(world, "paco")
        _at(world, 12)
        self.assertFalse(world.politics.laws.indoors(world, world.residents["paco"]))

    def test_whoever_does_not_keep_it_is_out_and_is_seen_by_whoever_is_about(self) -> None:
        world = self._night()
        _defies(world, "sergio")
        _obeys(world, "tomas")
        _put_away(world, "sergio", "tomas")
        _awake_at(world, "sergio", (20, 12))
        _awake_at(world, "tomas", (21, 12))
        world.residents["tomas"].activity = Activity("work", "guard_post", minutes_left=600, using=True)
        self.assertFalse(world.politics.laws.keeps(world, world.residents["sergio"], "curfew"))
        world.politics.laws.tick(world)
        self.assertEqual(_broken(world), [("sergio", "curfew")], "the guard is out by right, and Sergio is not")
        fact = next(fact for fact in world.knowledge.facts.values() if fact.event_type == "law_broken")
        self.assertEqual(fact.subject_ids, ["sergio"])
        self.assertTrue(world.knowledge.knows("tomas", fact.fact_id))
        self.assertFalse(world.knowledge.knows("paco", fact.fact_id), "whoever was asleep knows nothing of it")
        feelings = world.relationship("tomas", "sergio")
        self.assertLess(feelings.trust, 0.0, "whoever keeps it thinks the less of him")
        self.assertGreater(feelings.resentment, 0.0)
        self.assertTrue(any("Sergio se saltó la ley" in memory.text for memory in world.memories.of("tomas")))
        world.clock.minute = 15
        world.politics.laws.tick(world)
        self.assertEqual(len(_broken(world)), 1, "once a day is all anybody is held to it")

    def test_with_nobody_about_to_see_nothing_comes_of_it(self) -> None:
        world = self._night()
        _defies(world, "sergio")
        _put_away(world, "sergio")
        _awake_at(world, "sergio", (20, 12))
        world.politics.laws.tick(world)
        self.assertEqual(_broken(world), [])
        self.assertEqual(world.knowledge.facts, {})

    def test_two_who_break_it_together_think_none_the_worse_of_each_other(self) -> None:
        world = self._night()
        _defies(world, "sergio", "raul")
        _put_away(world, "sergio", "raul")
        _awake_at(world, "sergio", (20, 12))
        _awake_at(world, "raul", (21, 12))
        world.politics.laws.tick(world)
        self.assertEqual({who for who, _law in _broken(world)}, {"sergio", "raul"})
        self.assertGreater(world.relationship("raul", "sergio").affection, 0.0)
        self.assertEqual(world.relationship("raul", "sergio").trust, 0.0)

    def test_a_leader_seen_to_break_their_own_law_loses_by_it(self) -> None:
        world = self._night()
        leader = world.government.leader
        _obeys(world, "paco")
        _put_away(world, leader, "paco")
        _awake_at(world, leader, (20, 12))
        _awake_at(world, "paco", (21, 12))
        world.residents["paco"].activity = Activity("work", "workbench", minutes_left=600, using=True)
        held, definition = world.government.laws["curfew"], world.registries.laws.laws["curfew"]
        legitimacy = world.government.measures["legitimacy"]
        loyalty = _held(world, "paco").loyalty
        self.assertTrue(world.politics.laws.breach(world, world.residents[leader], held, definition))
        self.assertLess(world.government.measures["legitimacy"], legitimacy)
        self.assertLess(_held(world, "paco").loyalty, loyalty)
        self.assertGreater(world.government.measures["corruption"], 0.0)

    def test_three_nights_under_it_see_it_kept_by_most_and_broken_by_whoever_owes_nothing(self) -> None:
        world = _governed()
        world.politics.laws.enact(world, "curfew", 2)
        _defies(world, "sergio", "raul")
        world.government.measures["legitimacy"] = 100.0
        _held(world, "sergio").fearfulness = 0.0
        world.step(60 * 24 * 3)
        out = {who for who, law in _broken(world) if law == "curfew"}
        self.assertTrue(out <= {"sergio", "raul"}, out)


class UseTests(unittest.TestCase):
    def test_under_a_dry_law_whoever_keeps_it_does_not_drink_and_whoever_does_not_is_seen_at_it(self) -> None:
        world = _governed()
        world.politics.laws.enact(world, "dry_law")
        _obeys(world, "paco", "lucia")
        _defies(world, "raul")
        laws = world.politics.laws
        bar = world.interactables["bar"]
        use = world.definition_of(bar).use
        self.assertTrue(laws.bars(world, world.residents["paco"], bar, use, False))
        self.assertFalse(laws.bars(world, world.residents["raul"], bar, use, False))
        for resident_id in ("paco", "raul"):
            world.residents[resident_id].needs.stress = 90.0
            world.residents[resident_id].needs.social = 90.0
            world.residents[resident_id].credits = 50.0
        world.residents["lucia"].activity = Activity("work", "bar", minutes_left=600, using=True)
        world.residents["lucia"].x, world.residents["lucia"].y = 48, 3
        _at(world, 19)
        names = {candidate.name for candidate in world.activities.routine.candidates(world, world.residents["paco"])}
        self.assertNotIn("drink", names)
        names = {candidate.name for candidate in world.activities.routine.candidates(world, world.residents["raul"])}
        self.assertIn("drink", names)
        world.step(60 * 4)
        drinkers = {who for who, law in _broken(world) if law == "dry_law"}
        self.assertEqual(drinkers, {"raul"})

    def test_the_fire_nobody_is_to_sit_at(self) -> None:
        world = _governed()
        world.politics.laws.enact(world, "no_fire")
        _obeys(world, "paco")
        fire = world.interactables["campfire"]
        use = world.definition_of(fire).use
        self.assertTrue(world.politics.laws.bars(world, world.residents["paco"], fire, use, False))
        bed = next(placed for placed in world.interactables.values() if placed.kind == "bed")
        self.assertFalse(world.politics.laws.bars(world, world.residents["paco"], bed, world.definition_of(bed).use, False))

    def test_rationing_counts_meals_and_whoever_keeps_it_stops_at_what_it_allows(self) -> None:
        world = _governed()
        world.politics.laws.enact(world, "rationing", 2)
        _obeys(world, "paco")
        _defies(world, "raul")
        laws = world.politics.laws
        pot = world.interactables["cooking_pot"]
        use = world.definition_of(pot).use
        paco, raul = world.residents["paco"], world.residents["raul"]
        self.assertFalse(laws.bars(world, paco, pot, use, False), "nobody has eaten yet")
        laws.used(world, paco, pot, use)
        self.assertEqual(laws.meals_today(world, paco), 1)
        self.assertTrue(laws.bars(world, paco, pot, use, False), "one meal a day is one meal a day")
        paco.needs.hunger = 90.0
        self.assertFalse(laws.bars(world, paco, pot, use, False), "starving, nobody keeps it")
        paco.needs.hunger = 0.0
        self.assertFalse(laws.bars(world, raul, pot, use, False))
        world.clock.day += 1
        self.assertEqual(laws.meals_today(world, paco), 0)
        self.assertFalse(laws.bars(world, paco, pot, use, False))

    def test_a_second_helping_is_seen_by_whoever_is_at_the_table(self) -> None:
        world = _governed()
        world.politics.laws.enact(world, "rationing", 2)
        _defies(world, "raul")
        _obeys(world, "paco")
        _put_away(world, "raul", "paco")
        _awake_at(world, "raul", (43, 5))
        _awake_at(world, "paco", (44, 5))
        laws = world.politics.laws
        pot = world.interactables["cooking_pot"]
        use = world.definition_of(pot).use
        laws.used(world, world.residents["raul"], pot, use)
        self.assertEqual(_broken(world), [])
        laws.used(world, world.residents["raul"], pot, use)
        self.assertEqual(_broken(world), [("raul", "rationing")])

    def test_two_days_on_one_meal_leave_whoever_keeps_it_hungrier(self) -> None:
        def hunger(rationed: bool) -> float:
            world = _governed()
            if rationed:
                world.politics.laws.enact(world, "rationing", 2)
            _obeys(world, *world.residents)
            world.step(60 * 24 * 2)
            return sum(resident.needs.hunger for resident in world.residents.values())

        self.assertGreater(hunger(True), hunger(False))

    def test_a_food_nobody_is_to_eat_is_passed_over_by_whoever_keeps_the_law(self) -> None:
        world = _governed()
        laws = world.politics.laws
        stew = world.registries.items.get("stew")
        beans = world.registries.items.get("canned_beans")
        world.politics.laws.enact(world, "banned_food", 0, {"item": "stew"})
        self.assertIn("nadie come", laws.describe(world, "banned_food", 0, {"item": "stew"}))
        self.assertIn(stew.name, laws.describe(world, "banned_food", 0, {"item": "stew"}))
        _obeys(world, "paco")
        _defies(world, "raul")
        paco, raul = world.residents["paco"], world.residents["raul"]
        self.assertFalse(laws.may_have(world, paco, stew))
        self.assertTrue(laws.may_have(world, paco, beans))
        self.assertTrue(laws.may_have(world, raul, stew))
        pot = world.containers["cooking_pot"]
        pot.items.clear()
        world.stock(pot, "stew", 5, None)
        paco.needs.hunger = 60.0
        self.assertIsNone(world.items.best_food(world, paco, "cooking_pot", "food"))
        world.stock(pot, "canned_beans", 5, None)
        self.assertEqual(world.items.best_food(world, paco, "cooking_pot", "food").definition_id, "canned_beans")
        paco.needs.hunger = 95.0
        self.assertTrue(laws.may_have(world, paco, stew), "starving, anybody eats what there is")

    def test_eating_it_all_the_same_is_seen(self) -> None:
        world = _governed()
        world.politics.laws.enact(world, "banned_food", 0, {"item": "stew"})
        _defies(world, "raul")
        _obeys(world, "paco")
        _put_away(world, "raul", "paco")
        _awake_at(world, "raul", (43, 5))
        _awake_at(world, "paco", (44, 5))
        world.items.take_in(world, world.residents["raul"], world.registries.items.get("canned_beans"))
        self.assertEqual(_broken(world), [])
        world.items.take_in(world, world.residents["raul"], world.registries.items.get("stew"))
        self.assertEqual(_broken(world), [("raul", "banned_food")])

    def test_a_ban_on_substances_goes_by_what_a_thing_is_tagged_as(self) -> None:
        world = _governed()
        world.politics.laws.enact(world, "substance_ban")
        _obeys(world, "paco")
        laws = world.politics.laws
        paco = world.residents["paco"]
        self.assertFalse(laws.may_have(world, paco, world.registries.items.get("cigarette")))
        self.assertTrue(laws.may_have(world, paco, world.registries.items.get("liquor")), "drink is another law's business")
        self.assertTrue(laws.may_have(world, paco, world.registries.items.get("stew")))
        world.stock(paco.inventory, "cigarette", 2, "paco")
        paco.needs.stress = 90.0
        used = [candidate for candidate in world.items.candidates(world, paco) if candidate.name == "use_item"]
        self.assertEqual(used, [])


class WorkAndMoneyTests(unittest.TestCase):
    def test_a_shift_is_longer_or_shorter_by_what_the_law_says(self) -> None:
        job = SimulationWorld.demo_world().registries.jobs["farmer"]
        self.assertEqual(job.shifts, ((8, 13), (15, 18)))
        self.assertEqual(minutes_left_in_shift(job, 12, 0), 60)
        self.assertEqual(minutes_left_in_shift(job, 18, 30), 0)
        self.assertEqual(minutes_left_in_shift(job, 18, 30, 120), 90)
        self.assertEqual(minutes_left_in_shift(job, 17, 0, -120), 0)
        self.assertEqual(minutes_left_in_shift(job, 15, 30, -120), 30)
        self.assertEqual(minutes_left_in_shift(job, 15, 30, -600), 30, "the day's last shift is never shorter than an hour")
        self.assertEqual(minutes_left_in_shift(job, 12, 0, -120), 60, "it is the end of the day that gives, not every shift")
        self.assertEqual(minutes_left_in_shift(job, 13, 30, 120), 0)
        night = replace(job, shifts=((22, 6),))
        self.assertEqual(minutes_left_in_shift(night, 23, 0), 7 * 60)
        self.assertEqual(minutes_left_in_shift(night, 5, 30), 30)
        self.assertEqual(minutes_left_in_shift(night, 6, 30), 0)
        self.assertEqual(minutes_left_in_shift(night, 6, 30, 60), 30, "and one that runs past midnight is longer at its end")

    def test_long_hours_keep_everybody_at_their_post_past_the_usual_time(self) -> None:
        world = _governed()
        raul = world.residents["raul"]
        job = world.registries.jobs["farmer"]
        raul.day_off = None
        _at(world, 18, 30)
        self.assertEqual(world.work.shift_minutes_left(world, raul, job), 0)
        world.politics.laws.enact(world, "long_hours", 1)
        self.assertEqual(world.work.shift_minutes_left(world, raul, job), 90)
        world.politics.laws.enact(world, "short_hours", 1)
        self.assertNotIn("long_hours", world.government.laws, "the one does away with the other")
        _at(world, 17)
        self.assertEqual(world.work.shift_minutes_left(world, raul, job), 0)

    def test_a_day_of_rest_by_law_is_a_day_off_for_everybody(self) -> None:
        world = _governed()
        raul = world.residents["raul"]
        raul.day_off = None
        world.clock.day = 7
        self.assertFalse(world.work.is_day_off(world, raul))
        world.politics.laws.enact(world, "rest_day")
        self.assertTrue(world.work.is_day_off(world, raul))
        self.assertTrue(all(world.work.is_day_off(world, resident) for resident in world.residents.values()))
        world.clock.day = 8
        self.assertFalse(world.work.is_day_off(world, raul))
        _at(world, 9)
        world.clock.day = 7
        self.assertEqual(world.work.shift_minutes_left(world, raul, world.registries.jobs["farmer"]), 0)

    def test_nobody_works_on_the_birthday_of_whoever_leads(self) -> None:
        world = _governed()
        leader = world.residents[world.government.leader]
        raul = world.residents["raul"]
        raul.day_off = None
        world.politics.laws.enact(world, "leader_birthday")
        born = world.family.birth_date(world, leader)
        days = 0
        while (world.family.today(world).month, world.family.today(world).day) != (born.month, born.day):
            world.clock.day += 1
            days += 1
            self.assertLess(days, 366)
        self.assertTrue(world.work.is_day_off(world, raul))
        world.clock.day += 1
        self.assertFalse(world.work.is_day_off(world, raul))
        world.clock.day -= 1
        world.government.leader = None
        self.assertFalse(world.work.is_day_off(world, raul), "with nobody leading there is no birthday to keep")

    def test_wages_are_what_the_law_makes_them_and_a_tax_stays_in_the_fund(self) -> None:
        def paid(*laws: tuple[str, int]) -> tuple[float, float]:
            world = _governed()
            for law_id, degree in laws:
                world.politics.laws.enact(world, law_id, degree)
            raul = world.residents["raul"]
            fund, pocket = world.trading.fund, raul.credits
            for _ in range(60):
                world.trade.pay_wage(world, raul, world.registries.jobs["farmer"])
            return round(raul.credits - pocket, 6), round(fund - world.trading.fund, 6)

        wage = SimulationWorld.demo_world().registries.economy.wage_per_hour
        self.assertEqual(paid(), (wage, wage))
        self.assertEqual(paid(("low_wages", 1)), (wage * 0.5, wage * 0.5))
        self.assertEqual(paid(("high_wages", 1)), (wage * 1.5, wage * 1.5))
        earned, left_fund = paid(("tax", 1))
        self.assertAlmostEqual(earned, wage * 0.8)
        self.assertAlmostEqual(left_fund, wage * 0.8, msg="what is not paid out never leaves the fund")
        self.assertAlmostEqual(paid(("high_wages", 1), ("tax", 1))[0], wage * 1.5 * 0.8)

    def test_a_meal_costs_nothing_where_the_law_says_so(self) -> None:
        world = _governed()
        paco = world.residents["paco"]
        use = world.definition_of(world.interactables["cooking_pot"]).use
        price = world.registries.economy.meal_price
        self.assertEqual(world.trade.cost(world, paco, use), price)
        world.politics.laws.enact(world, "free_meals")
        self.assertEqual(world.trade.cost(world, paco, use), 0.0)
        bar = world.definition_of(world.interactables["bar"]).use
        self.assertGreater(world.trade.cost(world, paco, bar), 0.0, "a drink is no meal out of the commons")

    def test_whoever_is_expecting_rests_and_is_kept_all_the_same(self) -> None:
        world = _governed()
        ines = world.residents["ines"]
        ines.day_off = None
        _at(world, 9)
        self.assertIsNotNone(world.work.candidate(world, ines))
        ines.expecting_with, ines.due_day = "tomas", world.clock.day + 100
        self.assertIsNotNone(world.work.candidate(world, ines), "with no law for it she works like anybody")
        world.politics.laws.enact(world, "pregnancy_rest")
        ines.last_worked = 0
        self.assertIsNone(world.work.candidate(world, ines))
        self.assertEqual(ines.last_worked, world.clock.total_minutes, "and nobody holds it against her")
        self.assertTrue(world.trade.supplied(world, ines))
        self.assertIsNotNone(world.work.candidate(world, world.residents["raul"]))

    def test_laws_about_coin_make_no_sense_under_barter(self) -> None:
        world = _governed("direct_democracy")
        world.trading.in_use = False
        for law_id in ("tax", "low_wages", "high_wages", "free_meals"):
            self.assertIsNotNone(world.politics.laws.obstacle(world, law_id), law_id)
            self.assertFalse(world.propose(ENACT_LAW, law=law_id).ok, law_id)
        self.assertIsNone(world.politics.laws.obstacle(world, "curfew"))


class EverybodyTests(unittest.TestCase):
    def test_what_is_kept_is_everybodys_under_common_property(self) -> None:
        world = _governed()
        crate = world.containers["crate_1"]
        mine = [item for item in crate.items if item.owner_id == "raul"]
        self.assertTrue(mine)
        hoe = next(item for item in world.residents["raul"].inventory.items if item.definition_id == "hoe")
        world.politics.laws.enact(world, "common_property")
        self.assertTrue(all(item.owner_id is None for item in mine))
        self.assertEqual(hoe.owner_id, "raul", "what somebody carries is still theirs")
        world.stock(crate, "canned_beans", 1, "paco")
        world.clock.day += 1
        _at(world, 0)
        world.politics.tick(world)
        self.assertFalse(any(item.owner_id == "paco" for item in crate.items), "and what is put away after is too, by the next day")

    def test_with_the_gate_closed_by_law_whoever_keeps_it_turns_people_away(self) -> None:
        world = _governed()
        tomas = world.residents["tomas"]
        tomas.personality.empathy, tomas.personality.sociability = 90.0, 80.0
        self.assertEqual(world.politics.laws.gate_shut(world, tomas), 0.0)
        definition = world.registries.decisions["stranger"]
        self.assertGreater(definition.outcomes["turn_away"].score["law"], 0.0)
        self.assertNotIn("law", definition.outcomes["let_in"].score)
        self.assertTrue(world.happenings.call_to_gate(world, tomas))
        decision = world.interventions.pending_for(world, "tomas")
        self.assertNotIn("law", decision.inputs)
        self.assertEqual(world.interventions.leaning(world, decision), "let_in")
        world.interventions.cancel_for(world, "tomas")
        world.at_the_gate, world.gate_party = None, []
        world.crisis_cooldowns.clear()
        world.politics.laws.enact(world, "closed_gate")
        _obeys(world, "tomas")
        self.assertEqual(world.politics.laws.gate_shut(world, tomas), 1.0)
        self.assertTrue(world.happenings.call_to_gate(world, tomas))
        decision = world.interventions.pending_for(world, "tomas")
        self.assertEqual(decision.inputs["law"], 1.0)
        self.assertEqual(world.interventions.leaning(world, decision), "turn_away")

    def test_letting_somebody_in_against_the_law_is_seen(self) -> None:
        world = _governed()
        world.politics.laws.enact(world, "closed_gate")
        _defies(world, "tomas")
        _obeys(world, "paco")
        _put_away(world, "tomas", "paco")
        gate = world.happenings.arrival_tile(world)
        _awake_at(world, "tomas", (gate[0] - 1, gate[1]))
        _awake_at(world, "paco", (gate[0] - 2, gate[1]))
        tomas = world.residents["tomas"]
        self.assertEqual(world.politics.laws.gate_shut(world, tomas), 0.0, "he does not keep it")
        self.assertTrue(world.happenings.call_to_gate(world, tomas))
        world.happenings.answer_gate(world, "let_in", tomas)
        self.assertEqual(len(world.residents), 10)
        self.assertEqual(_broken(world), [("tomas", "closed_gate")])

    def test_at_the_hour_of_the_radio_whoever_keeps_it_goes_and_whoever_is_missing_is_seen_to_be(self) -> None:
        world = _governed()
        world.politics.laws.enact(world, "radio_hour")
        _obeys(world, *world.residents)
        _defies(world, "sergio")
        world.government.measures["legitimacy"] = 100.0
        for resident_id in world.residents:
            _free(world, resident_id)
        radio = world.interactables["radio_set"]
        reach = world.registries.laws.attend_reach
        _at(world, 19, 59)
        world.step(1)
        self.assertIsNotNone(world.politics.laws.attendance(world, world.residents["paco"]))
        self.assertIsNone(world.politics.laws.attendance(world, world.residents["sergio"]))
        world.step(58)
        near = {
            resident_id
            for resident_id, resident in world.residents.items()
            if abs(resident.x - radio.x) + abs(resident.y - radio.y) <= reach
        }
        self.assertGreaterEqual(len(near), 6, "most of them make it there within the hour")
        self.assertTrue(any(resident.activity and resident.activity.action == ATTEND_ACTION for resident in world.residents.values()))
        world.step(2)
        missing = {who for who, law in _broken(world) if law == "radio_hour"}
        self.assertIn("sergio", missing)
        self.assertTrue(missing.isdisjoint(near))
        fact = next(fact for fact in world.knowledge.facts.values() if fact.event_type == "law_broken")
        self.assertTrue(any(world.knowledge.knows(resident_id, fact.fact_id) for resident_id in near))
        world.step(120)
        self.assertFalse(any(resident.activity and resident.activity.action == ATTEND_ACTION for resident in world.residents.values()))

    def test_at_any_other_hour_it_asks_nothing(self) -> None:
        world = _governed()
        world.politics.laws.enact(world, "radio_hour")
        _obeys(world, "paco")
        _at(world, 12)
        self.assertIsNone(world.politics.laws.attendance(world, world.residents["paco"]))
        self.assertEqual(world.politics.laws.pull(world, world.residents["paco"], world.interactables["radio_set"]), 0.0)
        _at(world, 20)
        self.assertGreater(world.politics.laws.pull(world, world.residents["paco"], world.interactables["radio_set"]), 0.0)

    def test_whoever_leads_is_greeted_once_a_day_by_whoever_comes_across_them_and_keeps_the_law(self) -> None:
        world = _governed()
        leader = world.government.leader
        world.politics.laws.enact(world, "salute")
        _defies(world, "sergio")
        world.government.measures["legitimacy"] = 100.0
        _obeys(world, "paco", leader)
        _put_away(world, leader, "paco", "sergio")
        _awake_at(world, leader, (20, 12))
        _awake_at(world, "paco", (21, 12))
        _awake_at(world, "sergio", (20, 13))
        _at(world, 12, 1)
        world.politics.laws.tick(world)
        self.assertEqual(_types(world).count("saluted"), 1)
        self.assertEqual(_broken(world), [("sergio", "salute")])
        self.assertLess(world.relationship(leader, "sergio").trust, 0.0, "whoever leads saw who did not")
        world.clock.minute = 2
        world.politics.laws.tick(world)
        self.assertEqual(_types(world).count("saluted"), 1, "once a day")
        self.assertEqual(len(_broken(world)), 1)

    def test_during_the_silence_whoever_keeps_it_talks_to_nobody(self) -> None:
        world = _governed()
        world.politics.laws.enact(world, "silent_siesta")
        _obeys(world, "paco")
        _defies(world, "raul")
        _put_away(world, "paco", "raul", "nuria")
        for resident_id, tile in (("paco", (20, 12)), ("raul", (22, 12)), ("nuria", (21, 13))):
            _awake_at(world, resident_id, tile)
            world.residents[resident_id].needs.social = 90.0
        world.residents["paco"].activity = None
        world.residents["raul"].activity = None
        _at(world, 14, 30)
        routine = world.activities.routine
        self.assertFalse(any(each.partner_id for each in routine.candidates(world, world.residents["paco"])))
        self.assertTrue(any(each.partner_id for each in routine.candidates(world, world.residents["raul"])))
        _at(world, 17)
        self.assertTrue(any(each.partner_id for each in routine.candidates(world, world.residents["paco"])))

    def test_talking_through_it_is_seen_by_whoever_else_is_there(self) -> None:
        world = _governed()
        world.politics.laws.enact(world, "silent_siesta")
        _defies(world, "raul", "nuria")
        _obeys(world, "paco")
        _put_away(world, "paco", "raul", "nuria")
        _awake_at(world, "paco", (20, 13))
        _awake_at(world, "raul", (20, 12))
        _awake_at(world, "nuria", (21, 12))
        world.residents["raul"].activity = Activity("chat", minutes_left=30, using=True, partner_id="nuria")
        world.residents["nuria"].activity = Activity("chat", minutes_left=30, using=True, partner_id="raul")
        _at(world, 14, 5)
        world.politics.laws.tick(world)
        self.assertEqual({who for who, _law in _broken(world)}, {"raul", "nuria"})
        self.assertLess(world.relationship("paco", "raul").trust, 0.0)

    def test_lamps_give_no_light_at_night_where_the_law_puts_them_out(self) -> None:
        world = _governed()
        lamp = world.interactables["lamp_cantina"]
        fire = world.interactables["campfire"]
        _at(world, 23)
        self.assertTrue(world.has_power())
        self.assertGreater(world.light_of(lamp), 0)

        def lit() -> int:
            return sum(
                world.is_lit((x, y)) for x in range(world.tile_map.width) for y in range(world.tile_map.height)
            )

        before = lit()
        world.politics.laws.enact(world, "lights_out")
        self.assertEqual(world.light_of(lamp), 0)
        self.assertLess(lit(), before, "and the settlement is the darker for it")
        self.assertGreater(world.light_of(fire), 0, "a fire is no lamp")
        _at(world, 12)
        self.assertGreater(world.light_of(lamp), 0, "and by day there is nothing to put out")

    def test_what_a_law_has_somebody_doing_is_said_for_what_it_is(self) -> None:
        from simulation.residents.activity import LEAVE_ACTION
        from ui.labels import describe_action

        world = _governed()
        paco = world.residents["paco"]
        said = set()
        for action in (RETIRE_ACTION, ATTEND_ACTION, LEAVE_ACTION):
            paco.activity = Activity(action, None, [(1, 1)], 10)
            said.add(describe_action(world, paco))
        self.assertEqual(len(said), 3)
        self.assertNotIn("pasea", said)

    def test_a_law_about_a_thing_there_is_not_cannot_be_had(self) -> None:
        world = SimulationWorld.new_settlement()
        self.assertIsNotNone(world.politics.laws.obstacle(world, "radio_hour"))
        self.assertIsNotNone(world.politics.laws.obstacle(world, "salute"), "nor one about a leader with nobody leading")
        self.assertIsNotNone(world.politics.laws.obstacle(world, "no_such_law"))


class PoliticsOfLawsTests(unittest.TestCase):
    def test_a_harsh_law_makes_the_place_more_authoritarian_and_a_nonsense_costs_legitimacy(self) -> None:
        world = _governed()
        measures = world.government.measures
        authoritarian, legitimacy = measures["authoritarianism"], measures["legitimacy"]
        world.politics.laws.enact(world, "curfew", 0)
        mild = measures["authoritarianism"]
        self.assertGreater(mild, authoritarian)
        self.assertEqual(measures["legitimacy"], legitimacy)
        world.politics.laws.enact(world, "curfew", 2)
        self.assertGreater(measures["authoritarianism"], mild, "and the harsher, the more")
        self.assertEqual(world.government.laws["curfew"].degree, 2)
        world.politics.laws.repeal(world, "curfew")
        self.assertAlmostEqual(measures["authoritarianism"], authoritarian)
        world.politics.laws.enact(world, "salute")
        self.assertLess(measures["legitimacy"], legitimacy)
        self.assertEqual(_types(world).count("law_enacted"), 3)
        self.assertEqual(_types(world).count("law_repealed"), 1)

    def test_a_government_that_is_expected_to_abuse_loses_less_by_a_nonsense(self) -> None:
        lost = {}
        for kind in ("strong_mayor", "personalist_rule"):
            world = _governed(kind)
            world.government.measures["legitimacy"] = 80.0
            world.politics.laws.enact(world, "salute")
            lost[kind] = 80.0 - world.government.measures["legitimacy"]
        self.assertGreater(lost["strong_mayor"], lost["personalist_rule"])

    def test_a_day_under_a_law_somebody_is_against_is_held_against_the_government(self) -> None:
        world = _governed()
        world.politics.laws.enact(world, "tax", 2)
        laws = world.politics.laws
        raul = world.residents["raul"]
        self.assertLess(laws.regard(world, raul, "tax", 2), 0.0)
        resentment, trust = _held(world, "raul").resentment, _held(world, "raul").trust
        for _ in range(5):
            laws.tick_day(world)
        self.assertGreater(_held(world, "raul").resentment, resentment)
        self.assertLess(_held(world, "raul").trust, trust)
        other = _governed()
        other.politics.laws.enact(other, "rest_day")
        self.assertGreater(other.politics.laws.regard(other, other.residents["raul"], "rest_day"), 0.0)
        before = _held(other, "raul").trust
        other.politics.laws.tick_day(other)
        self.assertGreater(_held(other, "raul").trust, before)
        self.assertEqual(_held(other, "raul").resentment, 0.0)

    def test_a_law_the_player_was_behind_is_held_to_their_account_day_by_day(self) -> None:
        world = _governed()
        self.assertTrue(world.propose(ENACT_LAW, law="rest_day").ok)
        self.assertEqual(world.government.decided[-1].status, ACCEPTED)
        self.assertTrue(world.government.laws["rest_day"].pushed)
        raul = world.residents["raul"]
        standing = world.politics.influence.standing(world, raul)
        before = standing.trust
        world.politics.laws.tick_day(world)
        self.assertGreater(standing.trust, before)
        other = _governed()
        other.politics.laws.enact(other, "rest_day")
        other.politics.laws.tick_day(other)
        self.assertEqual(other.player_standing, {}, "one they had nothing to do with is none of their business")

    def test_whoever_leads_an_authoritarian_place_passes_what_takes_their_fancy(self) -> None:
        # Where the data leaves laws to the residents: in the game's own they are the player's.
        world = _governed("personalist_rule")
        world.registries = replace(
            world.registries, proposals=replace(world.registries.proposals, decrees=(), residents_raise=(ENACT_LAW,))
        )
        leader = world.residents[world.government.leader]
        self.assertGreaterEqual(world.government.measures["authoritarianism"], world.registries.laws.whim_from)
        leader.personality.sociability, leader.personality.aggression = 0.0, 100.0
        leader.personality.greed, leader.personality.empathy = 100.0, 0.0
        _held(world, leader.resident_id).political_interest = 100.0
        raised = []
        for _ in range(60):
            world.clock.day += 1
            _at(world, 8)
            world.government.raised_on.clear()
            world.politics.voting.tick(world)
            for proposal in list(world.government.proposals.values()):
                raised.append(proposal)
                world.politics.voting.decide(world, proposal)
        whims = [proposal for proposal in raised if world.registries.laws.laws[proposal.law or ""].whim]
        self.assertTrue(whims, "sooner or later")
        self.assertTrue(all(proposal.by == leader.resident_id for proposal in whims))
        self.assertTrue(any(world.registries.laws.laws[law_id].absurd for law_id in world.government.laws))

    def test_nobody_has_whims_where_nobody_is_put_up_with_having_them(self) -> None:
        world = _governed("strong_mayor")
        leader = world.residents[world.government.leader]
        self.assertLess(world.government.measures["authoritarianism"], world.registries.laws.whim_from)
        leader.personality.sociability, leader.personality.aggression = 0.0, 100.0
        for _ in range(60):
            world.clock.day += 1
            _at(world, 8)
            world.government.raised_on.clear()
            world.politics.voting.tick(world)
        absurd = [proposal for proposal in world.government.proposals.values() if world.registries.laws.laws[proposal.law or ""].absurd]
        self.assertEqual(absurd, [])

    def test_a_leader_bans_the_food_they_cannot_stand(self) -> None:
        from simulation.tastes.taste import Taste

        world = _governed("personalist_rule")
        leader = world.residents[world.government.leader]
        voting = world.politics.voting
        law = world.registries.laws.laws["banned_food"]
        self.assertIsNone(voting._names_for(world, leader, law), "with nothing they loathe there is nothing to ban")
        world.tastes.profile(world, leader).items["vegetables"] = Taste(leaning=-95.0)
        self.assertEqual(voting._names_for(world, leader, law), {"item": "vegetables"})
        params = {"item": "vegetables"}
        self.assertGreater(world.politics.laws.regard(world, leader, "banned_food", 0, params), 0.0)
        fond = world.residents["paco"]
        world.tastes.profile(world, fond).items["vegetables"] = Taste(leaning=95.0)
        self.assertLess(world.politics.laws.regard(world, fond, "banned_food", 0, params), 0.0, "whoever likes it is against")

    def test_somebody_who_knows_of_trouble_at_night_wants_a_curfew(self) -> None:
        world = _governed("direct_democracy")
        voting = world.politics.voting
        vera = world.residents["vera"]
        law = world.registries.laws.laws["curfew"]
        self.assertFalse(voting._moved(world, vera, law, 1.0))
        _at(world, 23)
        for index, resident in enumerate(world.residents.values()):
            resident.x, resident.y = 39 + index % 3, 11 + index // 3
            resident.activity = Activity("wander", minutes_left=600, using=True)
        world.emit_event(
            DomainEvent("theft_committed", 60, "Sergio le quita algo a Nuria", ["sergio"]),
            at=world.residents["sergio"].tile,
            fact_text="Sergio le robó a Nuria",
            subjects=["sergio", "nuria"],
        )
        self.assertTrue(voting._moved(world, vera, law, 1.0))
        by_day = _governed("direct_democracy")
        _at(by_day, 12)
        for index, resident in enumerate(by_day.residents.values()):
            resident.x, resident.y = 39 + index % 3, 11 + index // 3
            resident.activity = Activity("wander", minutes_left=600, using=True)
        by_day.emit_event(
            DomainEvent("theft_committed", 60, "Sergio le quita algo a Nuria", ["sergio"]),
            at=by_day.residents["sergio"].tile,
            fact_text="Sergio le robó a Nuria",
            subjects=["sergio", "nuria"],
        )
        self.assertFalse(by_day.politics.voting._moved(by_day, by_day.residents["vera"], law, 1.0), "what happens by day is no reason")

    def test_a_week_under_laws_changes_what_people_are_seen_to_do(self) -> None:
        def drinks_and_nights_out(*laws: tuple[str, int]) -> tuple[int, int]:
            world = SimulationWorld.demo_world(seed=3)
            world.politics.leadership.establish(world, "strong_mayor")
            for law_id, degree in laws:
                world.politics.laws.enact(world, law_id, degree)
            for resident_id in world.residents:
                _obeys(world, resident_id)
            drinks = out = 0
            for _ in range(7 * 24 * 4):
                world.step(15)
                hour = world.clock.hour
                if hour >= 22 or hour < 6:
                    # Out in the open with nowhere to be: strolling, or stood talking.
                    out += sum(
                        1
                        for resident in world.residents.values()
                        if not resident.away
                        and not world.under_roof(resident.tile)
                        and resident.activity is not None
                        and (resident.activity.action == "wander" or resident.activity.partner_id is not None)
                    )
            drinks = sum(1 for line in world.event_log if "toma algo en la cantina" in line)
            return drinks, out

        free_drinks, free_nights = drinks_and_nights_out()
        dry_drinks, kept_nights = drinks_and_nights_out(("dry_law", 0), ("curfew", 1))
        self.assertGreater(free_drinks, 0)
        self.assertEqual(dry_drinks, 0)
        self.assertGreater(free_nights, 0)
        self.assertLess(kept_nights, free_nights / 4)


if __name__ == "__main__":
    unittest.main()
