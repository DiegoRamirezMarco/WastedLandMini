import json
import unittest
from dataclasses import replace

from save.save_manager import SaveManager
from simulation.commands import ChooseOptionCommand, FoundResidentCommand, SetIdentityCommand
from simulation.events.world_event_system import PAIR_DECISION, STRANGER_DECISION
from simulation.events.event import DomainEvent
from simulation.family.calendar import DAYS_PER_YEAR, Date, date_of, years_between
from simulation.family.children import BED, CARRIED, GROUND, TAKE_IN, Bundle
from simulation.family.kin import KinRecord
from simulation.residents.personality import Personality
from simulation.rng import SimulationRNG
from simulation.work.work_system import WORK_ACTION
from simulation.family.family_system import KIN_TOGETHER, SLEEP_ROUGH_ACTION
from simulation.knowledge.fact import SOURCE_TOLD
from simulation.knowledge.knowledge_system import learn
from simulation.family.settings import family_settings_from_data
from simulation.residents.activity import Activity
from simulation.residents.needs import Needs
from simulation.residents.resident import Resident
from simulation.world import SimulationWorld
from tests.worlds import no_store

MINUTES_PER_DAY = 24 * 60


def _content(world: SimulationWorld, *resident_ids: str) -> None:
    for resident_id in resident_ids or world.residents:
        world.residents[resident_id].needs = Needs(hunger=0, tiredness=0, social=0, stress=0)


def _settled(seed: int = 7) -> SimulationWorld:
    world = SimulationWorld.demo_world(seed=seed)
    no_store(world)
    world.relationships.clear()
    _content(world)
    return world


def _types(world: SimulationWorld) -> list[str]:
    return [line.split(" | ")[1] for line in world.event_log]


def _midnight(world: SimulationWorld, days: int = 1) -> None:
    """Have that many days begin, one after another, with nothing else happening in them."""
    for _ in range(days):
        world.clock.day += 1
        world.clock.hour, world.clock.minute = 0, 0
        world.family.tick(world)


class _Certain(SimulationRNG):
    """A generator of world events for which whatever can happen does, at the first chance."""

    def random(self) -> float:
        return 0.0


def _apart(world: SimulationWorld, one: str, other: str) -> tuple[Resident, Resident]:
    """Stand two residents side by side in the open, awake, with everybody else far away."""
    for index, resident in enumerate(world.residents.values()):
        resident.x, resident.y = 3 + index, 26
        resident.activity = Activity("wander", minutes_left=600, using=True)
    a, b = world.residents[one], world.residents[other]
    (a.x, a.y), (b.x, b.y) = (40, 12), (41, 12)
    return a, b


def _fond(world: SimulationWorld, one: str, other: str, affection: float = 70.0, attraction: float = 0.0) -> None:
    for a, b in ((one, other), (other, one)):
        feelings = world.relationship(a, b)
        feelings.affection, feelings.trust, feelings.attraction = affection, 40.0, attraction


def _strangers(world: SimulationWorld, *seen: str) -> Resident:
    """Have whoever has not been seen come to the gate at the next hour, with the guard at it."""
    world.event_rng = _Certain(1)
    world.clock.day, world.clock.hour, world.clock.minute = 2, 12, 0
    world.happened = {other: 2 for other in world.registries.world_events.events if other != "stranger"}
    world.newcomers_seen = list(seen)
    tomas = world.residents["tomas"]
    post = world.interactables[tomas.post_id]
    tomas.x, tomas.y = post.x, post.y - 1
    tomas.activity = Activity(WORK_ACTION, tomas.post_id, minutes_left=600, using=True)
    tomas.current_action = WORK_ACTION
    world.step(60)
    return tomas


def _children(world: SimulationWorld, **changes) -> SimulationWorld:
    """The same world with something about how children come or fare changed."""
    family = world.registries.family
    world.registries = replace(world.registries, family=replace(family, children=replace(family.children, **changes)))
    return world


def _born(world: SimulationWorld, mother_id: str = "ines", father_id: str | None = "tomas") -> Bundle:
    """A child of these two, born this minute."""
    mother = world.residents[mother_id]
    mother.expecting_with = father_id
    return world.children.give_birth(world, mother)


class CalendarTests(unittest.TestCase):
    def test_the_date_follows_from_the_day_through_months_and_years(self) -> None:
        dates = {day: date_of(day, 2226) for day in (1, 31, 32, 59, 60, 365, 366, 365 * 2 + 60)}
        self.assertEqual(dates[1], Date(2226, 1, 1))
        self.assertEqual((dates[31], dates[32]), (Date(2226, 1, 31), Date(2226, 2, 1)))
        self.assertEqual((dates[59], dates[60]), (Date(2226, 2, 28), Date(2226, 3, 1)), "no leap years")
        self.assertEqual((dates[365], dates[366]), (Date(2226, 12, 31), Date(2227, 1, 1)))
        self.assertEqual(dates[365 * 2 + 60].label, "1 de marzo de 2228")
        self.assertEqual(date_of(0, 2226), Date(2225, 12, 31), "before it began, it counts backwards")
        self.assertEqual(date_of(1 - 41 * 365, 2226).year, 2185)

    def test_a_settlement_begins_on_the_first_of_january_of_2226(self) -> None:
        world = SimulationWorld.demo_world()
        self.assertEqual(world.family.today(world).label, "1 de enero de 2226")
        world.clock.day = 400
        self.assertEqual(world.family.today(world), Date(2227, 2, 4))

    def test_bad_family_data_is_rejected(self) -> None:
        self.assertEqual(family_settings_from_data({}).start_year, 2226)
        with self.assertRaisesRegex(ValueError, "Old age"):
            family_settings_from_data({"old_age": {"chance_per_year": 2}})
        with self.assertRaisesRegex(ValueError, "Sleeping on the ground"):
            family_settings_from_data({"sleeping_rough": {"per_minute": {"tiredness": 0.1}}})


class AgeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.world = _settled()
        self.marta = self.world.residents["marta"]

    def test_everyone_has_a_date_of_birth_that_makes_them_the_age_they_are(self) -> None:
        birthdays = set()
        for resident in self.world.residents.values():
            born = self.world.family.born(self.world, resident)
            self.assertEqual(years_between(born, self.world.clock.day), resident.age, resident.name)
            birthdays.add(self.world.family.birth_date(self.world, resident).label.rsplit(" de ", 1)[0])
        self.assertGreater(len(birthdays), 6, "they were not all born on the same day of the year")
        self.assertEqual(self.world.family.birth_date(self.world, self.marta).year, 2226 - 42)

    def test_a_birthday_comes_round_by_itself_and_is_said(self) -> None:
        self.marta.born = self.world.clock.day + 2 - 41 * DAYS_PER_YEAR
        self.marta.age = 40
        _midnight(self.world)
        self.assertEqual((self.marta.age, _types(self.world).count("birthday")), (40, 0))
        _midnight(self.world)
        self.assertEqual(self.marta.age, 41)
        self.assertTrue(any("Marta cumple 41 años" in line for line in self.world.event_log))
        _midnight(self.world, DAYS_PER_YEAR - 1)
        self.assertEqual(self.marta.age, 41)
        _midnight(self.world)
        self.assertEqual(self.marta.age, 42, "and a year later, on the same day")

    def test_nobody_dies_of_old_age_before_eighty_and_someone_old_enough_does_and_is_buried(self) -> None:
        chance = self.world.family.old_age_chance
        self.assertEqual((chance(self.world, 30), chance(self.world, 79)), (0.0, 0.0))
        self.assertAlmostEqual(chance(self.world, 80), 0.05 / DAYS_PER_YEAR)
        self.assertAlmostEqual(chance(self.world, 85), 0.10 / DAYS_PER_YEAR)
        self.assertEqual(chance(self.world, 140), 1.0 / DAYS_PER_YEAR)
        vera = self.world.residents["vera"]
        vera.age, vera.born = 96, None
        before = len(self.world.residents)
        _midnight(self.world, 4 * DAYS_PER_YEAR)
        self.assertNotIn("vera", self.world.residents)
        self.assertEqual(len(self.world.residents), before - 1, "and nobody else")
        death = self.world.deaths[-1]
        self.assertEqual((death.resident_id, death.cause), ("vera", "la vejez"))
        self.assertIn(death.grave_id, self.world.interactables)
        self.assertTrue(all(resident.age < 80 for resident in self.world.residents.values()))

    def test_the_same_seed_has_the_old_die_on_the_same_day(self) -> None:
        days = []
        for _ in range(2):
            world = _settled(seed=4)
            world.residents["vera"].age = 99
            while "vera" in world.residents:
                _midnight(world)
            days.append(world.clock.day)
        self.assertEqual(days[0], days[1])

    def test_dates_of_birth_are_saved_and_a_save_from_before_has_everyone_the_age_they_were(self) -> None:
        manager = SaveManager()
        born = self.world.family.born(self.world, self.marta)
        data = manager.to_data(self.world)
        loaded = manager.from_data(json.loads(json.dumps(data)))
        self.assertEqual(loaded.residents["marta"].born, born)
        for resident in data["residents"]:
            del resident["born"]
        older = manager.from_data(json.loads(json.dumps(data)))
        self.assertIsNone(older.residents["marta"].born)
        self.assertEqual(older.family.born(older, older.residents["marta"]), born)
        _midnight(older, 10)
        self.assertEqual(older.residents["marta"].age, 41)


class IdentityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.world = _settled()

    def test_those_the_game_has_by_name_are_who_it_says_they_are(self) -> None:
        who = {r.resident_id: (r.sex, r.gender, r.drawn_to) for r in self.world.residents.values()}
        self.assertEqual(who["marta"], ("f", "f", "m"))
        self.assertEqual(who["tomas"], ("m", "m", "f"))
        self.assertEqual(who["lucia"], ("f", "f", "both"))
        self.assertTrue(all(sex in ("m", "f") for sex, _, _ in who.values()))

    def test_a_first_resident_is_who_the_player_says_and_what_is_left_out_follows_from_them(self) -> None:
        world = SimulationWorld.new_settlement()
        identity = {"sex": "f", "gender": "nb", "drawn_to": "f"}
        ada = world.residents[world.apply_command(FoundResidentCommand("Ada", 30, {"libido": 80}, [], identity=identity))]
        self.assertEqual((ada.sex, ada.gender, ada.drawn_to, ada.personality.libido), ("f", "nb", "f", 80.0))
        sexes = set()
        for _ in range(2):
            other = SimulationWorld.new_settlement()
            eva = other.residents[other.apply_command(FoundResidentCommand("Eva", 30, {}, [], identity={"gender": "zz"}))]
            sexes.add(eva.sex)
            self.assertEqual((eva.gender, eva.drawn_to), (eva.sex, "both"))
        self.assertEqual(len(sexes), 1, "the same every time for the same person")

    def test_the_player_can_say_who_somebody_is_and_nonsense_is_refused(self) -> None:
        self.assertTrue(self.world.apply_command(SetIdentityCommand("raul", "m", "bi", "m")))
        raul = self.world.residents["raul"]
        self.assertEqual((raul.sex, raul.gender, raul.drawn_to), ("m", "bi", "m"))
        self.assertEqual(self.world.kinship["raul"].gender, "bi")
        self.assertFalse(self.world.apply_command(SetIdentityCommand("raul", "x", "m", "both")))
        self.assertFalse(self.world.apply_command(SetIdentityCommand("nobody", "m", "m", "both")))

    def test_libido_is_theirs_and_the_moment_counts(self) -> None:
        raul = self.world.residents["raul"]
        raul.personality.libido, raul.mood = 80.0, 60.0
        desire = self.world.family.desire
        self.assertEqual(desire(self.world, raul), 80.0)
        raul.needs.stress = 75
        self.assertEqual(desire(self.world, raul), 40.0)
        raul.needs.stress, raul.needs.tiredness = 0, 100
        self.assertEqual(desire(self.world, raul), 40.0)
        raul.needs.tiredness, raul.mood = 0, 10.0
        self.assertLess(desire(self.world, raul), 80.0)
        raul.mood, raul.age = 60.0, 17
        self.assertEqual(desire(self.world, raul), 0.0, "it counts for nothing in anyone who is not an adult")
        self.assertEqual(raul.personality.libido, 80.0)


class DrawnToTests(unittest.TestCase):
    def setUp(self) -> None:
        self.world = _settled()
        self.tomas, self.ines = _apart(self.world, "tomas", "ines")
        _fond(self.world, "tomas", "ines", affection=60, attraction=60)
        self.bonds, self.family = self.world.bonds, self.world.family

    def test_it_goes_by_the_others_sex_and_not_by_their_gender(self) -> None:
        self.assertGreater(self.bonds.attraction_rate(self.world, self.tomas, self.ines), 0)
        self.ines.gender = "m"
        self.assertGreater(self.bonds.attraction_rate(self.world, self.tomas, self.ines), 0, "gender decides nothing of it")
        self.tomas.drawn_to = "m"
        self.assertEqual(self.bonds.attraction_rate(self.world, self.tomas, self.ines), 0.0)
        self.assertGreater(self.bonds.attraction_rate(self.world, self.ines, self.tomas), 0, "each way by itself")

    def test_nobody_courts_or_becomes_a_couple_with_someone_they_are_not_drawn_to(self) -> None:
        self.assertIs(self.bonds.confession_target(self.world, self.tomas), self.ines)
        self.tomas.drawn_to = "m"
        self.assertIsNone(self.bonds.confession_target(self.world, self.tomas))
        confession = self.world.registries.interactions["confession"]
        self.bonds.resolve(self.world, self.ines, self.tomas, confession)
        self.assertIsNone(self.ines.couple_with, "however she feels, he is not drawn to her")
        self.assertIn("confession_rejected", _types(self.world))
        self.tomas.drawn_to = "both"
        self.bonds.resolve(self.world, self.ines, self.tomas, confession)
        self.assertEqual((self.ines.couple_with, self.tomas.couple_with), ("tomas", "ines"))

    def test_nothing_of_it_with_anyone_under_age_and_being_kin_keeps_nobody_apart(self) -> None:
        self.assertTrue(self.family.may_court(self.world, self.tomas, self.ines))
        self.ines.age, self.ines.personality.libido = 17, 100.0
        self.assertFalse(self.family.may_court(self.world, self.tomas, self.ines))
        self.assertFalse(self.family.may_court(self.world, self.ines, self.tomas))
        self.assertEqual(self.bonds.attraction_rate(self.world, self.tomas, self.ines), 0.0)
        self.ines.age = 33
        marta, vera = self.world.residents["marta"], self.world.residents["vera"]
        marta.drawn_to = vera.drawn_to = "f"
        self.assertTrue(self.family.kin.close(self.world, "marta", "vera"))
        self.assertTrue(self.family.may_court(self.world, vera, marta), "being sisters does not stop them")
        self.family.kin.make_siblings(self.world, "tomas", "ines")
        self.assertGreater(self.bonds.attraction_rate(self.world, self.tomas, self.ines), 0)
        self.assertIs(self.bonds.confession_target(self.world, self.tomas), self.ines)


class KinTogetherTests(unittest.TestCase):
    """Nothing keeps close kin apart, and whoever comes to know of it thinks the worse of both."""

    def setUp(self) -> None:
        self.world = _settled()
        self.marta, self.vera = _apart(self.world, "marta", "vera")
        self.marta.drawn_to = self.vera.drawn_to = "f"
        _fond(self.world, "marta", "vera", affection=70, attraction=90)
        self.raul, self.nuria = self.world.residents["raul"], self.world.residents["nuria"]
        self.family = self.world.family

    def _facts(self) -> list:
        return [fact for fact in self.world.knowledge.facts.values() if fact.event_type == KIN_TOGETHER]

    def _feels(self, one: str, other: str) -> tuple[float, float, float]:
        feelings = self.world.relationship(one, other)
        return (feelings.affection, feelings.trust, feelings.resentment)

    def test_whoever_sees_two_sisters_become_a_couple_thinks_the_worse_of_both(self) -> None:
        self.raul.x, self.raul.y = 40, 13
        self.world.relationship("raul", "marta").affection = 50.0
        confession = self.world.registries.interactions["confession"]
        self.world.bonds.resolve(self.world, self.marta, self.vera, confession)
        self.assertEqual((self.marta.couple_with, self.vera.couple_with), ("vera", "marta"))
        self.assertIn(KIN_TOGETHER, _types(self.world))
        self.assertEqual(self._facts()[0].text, "Marta anda con Vera, su hermana")
        of_marta, of_vera = self._feels("raul", "marta"), self._feels("raul", "vera")
        self.assertLess(of_marta[0], 50.0 - 20)
        self.assertLess(of_vera[0], -20, "he takes no side: it is held against the two of them alike")
        self.assertAlmostEqual(50.0 - of_marta[0], 0.0 - of_vera[0])
        self.assertGreater(of_vera[2], 10)
        self.assertLess(of_vera[1], -10)
        self.assertEqual(self._feels("marta", "vera")[0], 70.0, "nothing changes between the two of them")
        self.assertIsNone(self.world.relationships.get(("nuria", "vera")), "whoever was not there knows nothing of it")

    def test_whoever_is_told_of_it_thinks_the_worse_of_them_too_and_the_two_keep_it_to_themselves(self) -> None:
        fact = self.family.kin_together(self.world, self.marta, self.vera)
        self.assertIsNone(self.world.knowledge.belief("nuria", fact.fact_id))
        learn(self.world, self.nuria, fact, 0.8, SOURCE_TOLD, told_by="raul")
        self.assertLess(self._feels("nuria", "marta")[0], -15)
        self.assertGreater(self._feels("nuria", "vera")[2], 8)
        self.assertEqual(self.world.registries.event_settings["reactions"][KIN_TOGETHER]["secret"], 2)

    def test_there_is_one_fact_of_it_however_often_they_are_come_across(self) -> None:
        self.assertIsNone(self.family.kin_together(self.world, self.raul, self.nuria), "they are no kin")
        first = self.family.kin_together(self.world, self.marta, self.vera)
        self.assertIs(self.family.kin_together(self.world, self.vera, self.marta), first)
        self.assertEqual(len(self._facts()), 1)
        self.assertEqual(_types(self.world).count(KIN_TOGETHER), 1)
        self.assertIsNone(self.world.relationships.get(("raul", "vera")), "nobody was about")
        self.raul.x, self.raul.y = 40, 13
        self.world.bonds.seen(self.world, self.marta, self.vera)
        seen_once = self._feels("raul", "vera")
        self.assertLess(seen_once[0], -20)
        self.world.bonds.seen(self.world, self.marta, self.vera)
        self.assertEqual(self._feels("raul", "vera"), seen_once, "it is news only once")
        self.assertEqual(len(self._facts()), 1)

    def test_a_child_of_two_who_are_kin_by_blood_takes_the_worse_of_each_side_and_every_flaw(self) -> None:
        world = _children(_settled(), trait_chance=0.0)
        tomas, ines = world.residents["tomas"], world.residents["ines"]
        world.family.kin.make_siblings(world, "tomas", "ines")
        tomas.personality = Personality(aggression=80, empathy=20, courage=90, greed=10, libido=30)
        ines.personality = Personality(aggression=30, empathy=60, courage=40, greed=70, libido=70)
        tomas.traits, ines.traits = ["rogue"], ["music_lover", "dim"]
        child = _born(world)
        sides = child.personality
        self.assertEqual((sides.aggression, sides.empathy, sides.courage, sides.greed), (80, 20, 40, 70))
        self.assertEqual((sides.impulsiveness, sides.sociability), (50.0, 50.0))
        spread = world.registries.family.children.mix_spread
        self.assertTrue(50 - spread <= sides.libido <= 50 + spread, "what has no worse end is mixed as in anyone")
        self.assertEqual(child.traits, ["dim", "rogue"], "the flaws of both for certain, and nothing else by chance")
        self.assertTrue(world.children.inbred(world, child.child_id))
        self.assertTrue(world.history[-1].data["of_kin"])

    def test_a_child_of_two_taken_in_by_the_same_person_is_like_any_other(self) -> None:
        world = _children(_settled(), trait_chance=0.0)
        tomas, ines = world.residents["tomas"], world.residents["ines"]
        for each in ("tomas", "ines"):
            world.family.kin.record(world, each).adoptive.append("vera")
        self.assertTrue(world.family.kin.close(world, "tomas", "ines"))
        self.assertFalse(world.family.kin.blood(world, "tomas", "ines"))
        self.assertIsNotNone(world.family.kin_together(world, tomas, ines), "it is ill seen all the same")
        tomas.personality, ines.personality = Personality(courage=90), Personality(courage=10)
        tomas.traits, ines.traits = ["rogue"], ["dim"]
        child = _born(world)
        spread = world.registries.family.children.mix_spread
        self.assertTrue(50 - spread <= child.personality.courage <= 50 + spread)
        self.assertEqual(child.traits, [])
        self.assertFalse(world.children.inbred(world, child.child_id))
        self.assertFalse(world.children.inbred(world, _born(_settled()).child_id))

    def test_who_is_kin_by_blood_is_worked_out_from_who_was_born_to_whom(self) -> None:
        kin = self.family.kin
        self.assertTrue(kin.blood(self.world, "marta", "vera"))
        for child in ("lucia", "paco"):
            kin.record(self.world, child).parents.extend(["marta", "raul"])
        kin.record(self.world, "sergio").parents.append("lucia")
        related = {other: kin.blood(self.world, "lucia", other) for other in ("marta", "paco", "sergio", "tomas")}
        self.assertEqual(related, {"marta": True, "paco": True, "sergio": True, "tomas": False})
        self.assertTrue(kin.blood(self.world, "sergio", "raul"), "a grandfather")
        self.assertFalse(kin.blood(self.world, "lucia", "lucia"))

    def test_the_worse_end_of_a_side_has_to_be_one_of_a_side_there_is(self) -> None:
        for worse in ({"luck": "high"}, {"courage": "middling"}):
            with self.assertRaises(ValueError):
                family_settings_from_data({"children": {"inbred": {"worse": worse}}})
        settings = family_settings_from_data({"children": {"inbred": {"worse": {"libido": "high"}}}})
        self.assertEqual(settings.children.worse, {"libido": "high"})


class CasualTests(unittest.TestCase):
    """Two adults need not be a couple to go off alone together."""

    def setUp(self) -> None:
        self.world = _settled()
        self.raul, self.nuria = _apart(self.world, "raul", "nuria")
        _fond(self.world, "raul", "nuria")
        for resident in (self.raul, self.nuria):
            resident.personality.libido, resident.mood, resident.activity = 90.0, 60.0, None
        self.world.clock.hour = 22
        self.tryst = self.world.registries.interactions["tryst"]

    def _seeks(self) -> list[str]:
        return [c.partner_id for c in self.world.bonds.candidates(self.world, self.raul)]

    def test_two_who_get_on_very_well_and_both_want_it_go_off_alone(self) -> None:
        self.assertEqual(self._seeks(), ["nuria"])
        self.assertTrue(self.world.bonds.may_begin(self.world, self.raul, self.nuria, self.tryst))
        self.assertIsNone(self.raul.couple_with, "and are no couple for it")

    def test_two_with_a_low_libido_do_not_nor_two_who_do_not_get_on_that_well(self) -> None:
        self.raul.personality.libido = 30.0
        self.assertEqual(self._seeks(), [])
        self.raul.personality.libido, self.nuria.personality.libido = 90.0, 30.0
        self.assertEqual(self._seeks(), ["nuria"], "he cannot know until he asks")
        self.assertFalse(self.world.bonds.may_begin(self.world, self.raul, self.nuria, self.tryst))
        self.assertEqual(self._seeks(), [], "he takes no for an answer tonight")
        self.setUp()
        _fond(self.world, "raul", "nuria", affection=30)
        self.assertEqual(self._seeks(), [])

    def test_nor_two_of_whom_one_is_not_drawn_to_the_other(self) -> None:
        self.nuria.drawn_to = "f"
        self.assertFalse(self.world.bonds.may_begin(self.world, self.raul, self.nuria, self.tryst))
        self.setUp()
        self.raul.drawn_to = "m"
        self.assertEqual(self._seeks(), [])

    def test_nerves_get_in_the_way(self) -> None:
        self.raul.needs.stress = 90
        self.assertEqual(self._seeks(), [])


class MarriageTests(unittest.TestCase):
    def setUp(self) -> None:
        self.world = _settled()
        self.tomas, self.ines = _apart(self.world, "tomas", "ines")
        _fond(self.world, "tomas", "ines", affection=70, attraction=60)
        self.tomas.couple_with, self.ines.couple_with = "ines", "tomas"
        self.proposal = self.world.registries.interactions["proposal"]

    def test_a_couple_that_is_doing_well_thinks_of_marrying_and_the_player_has_a_say(self) -> None:
        self.assertIs(self.world.bonds.proposal_target(self.world, self.tomas), self.ines)
        self.tomas.activity = self.world.interventions.maybe_romance(self.world, self.tomas)
        decision = next(iter(self.world.decisions.values()))
        self.assertEqual((decision.kind, decision.resident_id), ("proposal", "tomas"))
        self.assertIn("Inés", decision.prompt)
        self.assertEqual(self.world.apply_command(ChooseOptionCommand(decision.decision_id, "encourage")), "propose")

    def test_asked_and_willing_they_are_married_and_it_is_kin_like_any_other(self) -> None:
        self.world.bonds.resolve(self.world, self.tomas, self.ines, self.proposal)
        self.assertTrue(self.world.bonds.are_married(self.world, self.tomas, self.ines))
        self.assertTrue(any("Tomás e Inés se casan" in line for line in self.world.event_log))
        self.assertEqual(self.world.family.kin.tree(self.world, "ines")["spouse"], [("tomas", "Tomás", True)])
        self.assertEqual(self.world.family.kin.word(self.world, "ines", "tomas"), "marido")
        self.assertIsNone(self.world.bonds.proposal_target(self.world, self.tomas), "nobody marries twice over")
        self.world.bonds.part(self.world, self.tomas, self.ines)
        self.assertFalse(self.world.bonds.are_married(self.world, self.tomas, self.ines))
        self.assertEqual(self.world.family.kin.tree(self.world, "ines")["spouse"], [])

    def test_asked_and_not_willing_they_are_not(self) -> None:
        self.world.relationship("ines", "tomas").affection = 20
        self.world.bonds.resolve(self.world, self.tomas, self.ines, self.proposal)
        self.assertFalse(self.world.bonds.are_married(self.world, self.tomas, self.ines))
        self.assertIn("proposal_rejected", _types(self.world))
        self.assertEqual(self.tomas.couple_with, "ines", "they are a couple still")

    def test_a_couple_at_odds_does_not_think_of_it(self) -> None:
        self.world.relationship("tomas", "ines").resentment = 40
        self.assertIsNone(self.world.bonds.proposal_target(self.world, self.tomas))
        self.tomas.couple_with = self.ines.couple_with = None
        self.assertIsNone(self.world.bonds.proposal_target(self.world, self.tomas))


class KinTests(unittest.TestCase):
    def setUp(self) -> None:
        self.world = _settled()
        self.kin = self.world.family.kin

    def test_brothers_and_sisters_and_the_rest_are_worked_out_from_who_the_parents_are(self) -> None:
        for child in ("lucia", "paco"):
            self.kin.record(self.world, child).parents.extend(["marta", "raul"])
        self.kin.record(self.world, "sergio").parents.append("lucia")
        self.assertEqual(self.kin.parents_of(self.world, "lucia"), ["marta", "raul"])
        self.assertEqual(self.kin.children_of(self.world, "marta"), ["lucia", "paco"])
        self.assertEqual(self.kin.siblings_of(self.world, "lucia"), ["paco"])
        ties = {other: self.kin.tie(self.world, "lucia", other) for other in ("marta", "paco", "sergio", "tomas")}
        self.assertEqual(ties, {"marta": "parent", "paco": "sibling", "sergio": "child", "tomas": None})
        self.assertEqual(self.kin.tie(self.world, "sergio", "raul"), "grandparent")
        self.assertEqual(self.kin.tie(self.world, "raul", "sergio"), "grandchild")
        words = [self.kin.word(self.world, "lucia", other) for other in ("marta", "raul", "paco", "sergio")]
        self.assertEqual(words, ["madre", "padre", "hermano", "hijo"])
        self.assertTrue(self.kin.close(self.world, "sergio", "marta"))
        self.assertFalse(self.kin.close(self.world, "sergio", "tomas"))

    def test_whoever_takes_a_child_in_is_its_parent_beside_those_it_was_born_to(self) -> None:
        record = self.kin.record(self.world, "lucia")
        record.parents.append("marta")
        record.adoptive.append("ines")
        self.assertEqual(self.kin.parents_of(self.world, "lucia"), ["marta", "ines"])
        self.assertEqual(self.kin.tie(self.world, "ines", "lucia"), "child")
        self.assertEqual([each[0] for each in self.kin.tree(self.world, "lucia")["parents"]], ["marta", "ines"])
        self.kin.record(self.world, "sergio").adoptive.append("ines")
        self.assertEqual(self.kin.siblings_of(self.world, "sergio"), ["lucia"], "kin like any other")

    def test_what_is_felt_for_kin_starts_from_being_kin_each_way_by_itself(self) -> None:
        world = SimulationWorld.demo_world()
        settings = world.registries.family
        for one, other in (("marta", "vera"), ("vera", "marta")):
            feelings = world.relationship(one, other)
            self.assertEqual((feelings.affection, feelings.trust), (settings.kin_affection, settings.kin_trust))
        self.assertEqual(world.family.kin.word(world, "marta", "vera"), "hermana")
        self.assertIsNone(world.relationships.get(("marta", "nuria")))

    def test_someone_whose_sister_is_hurt_takes_it_worse_than_someone_to_whom_she_is_nobody(self) -> None:
        marta, vera = _apart(self.world, "marta", "vera")
        raul = self.world.residents["raul"]
        raul.x, raul.y = 40, 13
        self.world.health.hurt(self.world, vera, 12.0, "cut", "una prueba")
        self.assertGreater(marta.needs.stress, raul.needs.stress + 5)

    def test_the_tree_is_the_same_after_saving_with_a_dead_grandparent_still_in_it(self) -> None:
        self.kin.record(self.world, "nuria").parents.append("vera")
        self.kin.record(self.world, "lucia").parents.append("nuria")
        self.world.health.die(self.world, self.world.residents["vera"], "una prueba")
        tree = self.kin.tree(self.world, "lucia")
        self.assertEqual(tree["grandparents"], [("vera", "Vera", False)])
        self.assertEqual(tree["parents"], [("nuria", "Nuria", True)])
        manager = SaveManager()
        loaded = manager.from_data(json.loads(json.dumps(manager.to_data(self.world))))
        self.assertEqual(loaded.family.kin.tree(loaded, "lucia"), tree)
        self.assertEqual(loaded.kinship, self.world.kinship)

    def test_who_everyone_is_survives_saving_and_a_save_from_before_has_them_drawn_to_both_and_kin_to_nobody(self) -> None:
        manager = SaveManager()
        self.world.residents["raul"].personality.libido = 85.0
        self.world.apply_command(SetIdentityCommand("raul", "m", "nb", "m"))
        data = manager.to_data(self.world)
        loaded = manager.from_data(json.loads(json.dumps(data)))
        raul = loaded.residents["raul"]
        self.assertEqual((raul.sex, raul.gender, raul.drawn_to, raul.personality.libido), ("m", "nb", "m", 85.0))
        self.assertTrue(loaded.family.kin.close(loaded, "marta", "vera"))

        data["version"] = 28
        del data["kinship"], data["gate_party"]
        for resident in data["residents"]:
            del resident["sex"], resident["gender"], resident["drawn_to"], resident["born"]
            del resident["personality"]["libido"]
        data["residents"][0]["id"] = "zoe"
        older = manager.from_data(json.loads(json.dumps(data)))
        self.assertEqual({r.drawn_to for r in older.residents.values()}, {"both"})
        self.assertEqual((older.residents["raul"].sex, older.residents["raul"].gender), ("m", "m"), "as the game has him")
        self.assertIn(older.residents["zoe"].sex, ("m", "f"))
        self.assertEqual(older.residents["zoe"].gender, older.residents["zoe"].sex)
        self.assertFalse(older.family.kin.close(older, "vera", "zoe"))
        self.assertEqual({r.personality.libido for r in older.residents.values()}, {50.0})
        self.assertEqual(older.residents["raul"].age, 38)
        older.step(MINUTES_PER_DAY)


class FamilyAtTheGateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.world = _settled()
        self.tomas = _strangers(self.world, "olga", "bruno")

    def _decision(self):
        return next(iter(self.world.decisions.values()))

    def test_two_who_come_together_are_put_to_the_guard_together(self) -> None:
        decision = self._decision()
        self.assertEqual((decision.kind, decision.resident_id), (PAIR_DECISION, "tomas"))
        self.assertIn("Hugo", decision.prompt)
        self.assertIn("Carmen", decision.prompt)
        self.assertEqual([option.text for option in decision.options][1:3], ["Solo Hugo", "Solo Carmen"])
        self.assertEqual(self.world.gate_party, ["hugo", "carmen"])
        self.assertEqual(decision.inputs, {"kin": 0.0, "room": 1.0})

    def test_let_in_together_they_live_here_as_the_brother_and_sister_they_are(self) -> None:
        self.assertEqual(self.world.apply_command(ChooseOptionCommand(self._decision().decision_id, "open")), "let_in")
        hugo, carmen = self.world.residents["hugo"], self.world.residents["carmen"]
        self.assertEqual((hugo.sex, carmen.sex, hugo.traits, carmen.traits), ("m", "f", ["kleptomaniac", "swindler"], ["wicked", "brute"]))
        self.assertEqual(self.world.family.kin.word(self.world, "hugo", "carmen"), "hermana")
        self.assertEqual(self.world.relationship("carmen", "hugo").affection, self.world.registries.family.kin_affection)
        self.assertNotIn("family_parted", _types(self.world))
        self.assertEqual((self.world.at_the_gate, self.world.gate_party), (None, []))

    def test_one_may_be_let_in_and_the_other_not_and_whoever_is_in_does_not_forget_it(self) -> None:
        self.world.happenings.answer_gate(self.world, "let_first", self.tomas)
        self.assertIn("hugo", self.world.residents)
        self.assertNotIn("carmen", self.world.residents)
        self.assertTrue({"hugo", "carmen"} <= set(self.world.newcomers_seen), "she is gone for good")
        hugo = self.world.residents["hugo"]
        self.assertIn("Me dejaron pasar y a Carmen, mi hermana, no.", [m.text for m in self.world.memories.of("hugo")])
        self.assertGreaterEqual(self.world.relationship("hugo", "tomas").resentment, 30)
        self.assertLess(self.world.relationship("hugo", "tomas").trust, 0)
        self.assertGreater(hugo.needs.stress, 40)
        self.assertTrue(any("Hugo entra y Carmen, hermana de Hugo, se queda fuera" in line for line in self.world.event_log))
        self.assertEqual(self.world.family.kin.tree(self.world, "hugo")["siblings"], [("carmen", "Carmen", False)])
        self.assertTrue(any("y a Carmen no" in m.text for m in self.world.memories.of("tomas")))

    def test_the_player_can_ask_for_only_one_of_them_and_the_guard_decides(self) -> None:
        self.tomas.personality = Personality(empathy=70, aggression=30, greed=30)
        self.assertEqual(self.world.apply_command(ChooseOptionCommand(self._decision().decision_id, "second")), "let_second")
        self.assertEqual(("carmen" in self.world.residents, "hugo" in self.world.residents), (True, False))
        self.assertIn("family_parted", _types(self.world))

    def test_with_one_bed_to_spare_only_one_of_them_can_stay(self) -> None:
        beds = [o for o, placed in self.world.interactables.items() if placed.kind == "bed"]
        for object_id in beds[len(self.world.residents) + 1 :]:
            del self.world.interactables[object_id]
        self.world.happenings.answer_gate(self.world, "let_in", self.tomas)
        self.assertEqual(("hugo" in self.world.residents, "carmen" in self.world.residents), (True, False))
        self.assertIn("family_parted", _types(self.world))

    def test_turned_away_together_nobody_is_parted_from_anybody(self) -> None:
        self.assertEqual(self.world.apply_command(ChooseOptionCommand(self._decision().decision_id, "close")), "turn_away")
        self.assertNotIn("hugo", self.world.residents)
        self.assertNotIn("family_parted", _types(self.world))

    def test_someone_who_has_kin_inside_is_known_for_it_at_the_gate(self) -> None:
        world = _settled()
        _strangers(world, "olga", "hugo", "carmen")
        decision = next(iter(world.decisions.values()))
        self.assertEqual((decision.kind, world.at_the_gate), (STRANGER_DECISION, "bruno"))
        self.assertEqual(decision.inputs["kin"], 1.0, "he is Paco's brother")
        other = _settled()
        _strangers(other, "bruno", "hugo", "carmen")
        self.assertEqual(next(iter(other.decisions.values())).inputs["kin"], 0.0)

    def test_two_waiting_at_the_gate_are_still_two_after_saving(self) -> None:
        manager = SaveManager()
        loaded = manager.from_data(json.loads(json.dumps(manager.to_data(self.world))))
        self.assertEqual((loaded.at_the_gate, loaded.gate_party), ("hugo", ["hugo", "carmen"]))
        self.assertEqual(manager.to_data(loaded), manager.to_data(self.world))


class ConceptionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.world = _children(_settled(), chance=1.0)
        self.tomas, self.ines = self.world.residents["tomas"], self.world.residents["ines"]
        self.children = self.world.children

    def test_sex_decides_who_can_have_a_child_and_gender_decides_nothing_of_it(self) -> None:
        marta, vera = self.world.residents["marta"], self.world.residents["vera"]
        self.assertFalse(self.children.together(self.world, marta, vera), "two who are f by sex")
        self.assertFalse(self.children.together(self.world, self.tomas, self.world.residents["raul"]))
        self.ines.gender, self.tomas.gender = "m", "nb"
        self.assertTrue(self.children.together(self.world, self.tomas, self.ines))
        self.assertEqual((self.ines.expecting_with, self.tomas.expecting_with), ("tomas", None), "whoever is f carries it")
        self.assertFalse(self.children.together(self.world, self.tomas, self.ines), "one at a time")

    def test_it_is_a_matter_of_chance_and_never_with_anyone_under_age_or_past_it(self) -> None:
        never = _children(_settled(), chance=0.0)
        self.assertFalse(never.children.together(never, never.residents["tomas"], never.residents["ines"]))
        self.ines.age = 17
        self.assertFalse(self.children.together(self.world, self.tomas, self.ines))
        self.ines.age = 55
        self.assertFalse(self.children.together(self.world, self.tomas, self.ines))

    def test_a_child_is_born_nine_weeks_after_it_was_conceived_to_the_two_whose_child_it_is(self) -> None:
        self.assertTrue(self.children.together(self.world, self.ines, self.tomas))
        self.assertEqual(self.ines.due_day, self.world.clock.day + 63)
        self.assertIn("child_conceived", _types(self.world))
        _midnight(self.world, 62)
        self.assertEqual(self.world.bundles, {})
        _midnight(self.world)
        bundle = next(iter(self.world.bundles.values()))
        self.assertEqual(self.world.family.kin.parents_of(self.world, bundle.child_id), ["ines", "tomas"])
        self.assertEqual((bundle.born, bundle.carried_by, bundle.place), (self.world.clock.day, "ines", CARRIED))
        self.assertIsNone(self.ines.expecting_with)
        self.assertTrue(any(f"Inés da a luz a {bundle.name}" in line for line in self.world.event_log))
        self.assertNotIn(bundle.child_id, self.world.residents, "it is no resident yet")

    def test_a_second_child_is_brother_or_sister_to_the_first(self) -> None:
        first, second = _born(self.world), _born(self.world)
        self.assertNotEqual((first.child_id, first.name), (second.child_id, second.name))
        self.assertEqual(self.world.family.kin.siblings_of(self.world, first.child_id), [second.child_id])
        self.assertEqual(self.world.family.kin.tie(self.world, "tomas", second.child_id), "child")

    def test_the_same_seed_gives_the_same_births(self) -> None:
        born = []
        for _ in range(2):
            world = _settled(seed=9)
            child = _born(world)
            born.append((child.child_id, child.sex, child.drawn_to, vars(child.personality), child.traits))
        self.assertEqual(born[0], born[1])

    def test_a_child_takes_its_way_of_being_and_its_traits_from_its_parents_and_not_their_tastes(self) -> None:
        world = _children(_settled(), trait_chance=1.0)
        tomas, ines = world.residents["tomas"], world.residents["ines"]
        tomas.personality, ines.personality = Personality(courage=90, greed=10), Personality(courage=70, greed=30)
        tomas.traits, ines.traits = ["rogue"], ["music_lover", "dim"]
        world.tastes.liking(world, ines, world.registries.items.get("stew"))
        child = _born(world)
        spread = world.registries.family.children.mix_spread
        self.assertTrue(80 - spread <= child.personality.courage <= min(100, 80 + spread))
        self.assertTrue(20 - spread <= child.personality.greed <= 20 + spread)
        self.assertEqual(child.traits, ["music_lover", "dim"], "no more than anybody has")
        self.assertNotIn(child.child_id, world.taste_profiles)
        alone = _born(_children(_settled(), trait_chance=0.0), father_id=None)
        self.assertEqual(alone.traits, [])


class BundleTests(unittest.TestCase):
    def setUp(self) -> None:
        self.world = _settled()
        self.ines = self.world.residents["ines"]
        self.bundle = _born(self.world)

    def test_a_bundle_is_carried_about_and_never_walks(self) -> None:
        places = set()
        for _ in range(MINUTES_PER_DAY):
            self.world.step(1)
            self.assertNotIn(self.bundle.child_id, self.world.residents)
            places.add(self.bundle.place)
            if self.bundle.place == CARRIED:
                self.assertEqual(self.bundle.tile, self.ines.tile)
        self.assertEqual(places, {CARRIED, BED}, "on her back by day, beside her by night")
        self.assertEqual(self.bundle.health, 100.0)

    def test_whoever_sees_to_it_feeds_it_and_is_the_more_tired_for_it(self) -> None:
        self.ines.needs = Needs(hunger=0, tiredness=0, social=0, stress=0)
        self.bundle.hunger = 59.9
        self.world.children.tick(self.world)
        self.assertEqual(self.bundle.hunger, 0.0)
        self.assertEqual((self.ines.needs.tiredness, self.ines.needs.stress), (2.0, 1.0))

    def test_with_its_mother_away_the_other_parent_sees_to_it(self) -> None:
        self.ines.expedition = object()
        self.world.children.tick(self.world)
        self.assertEqual(self.bundle.carried_by, "tomas")
        self.world.residents["tomas"].expedition = object()
        self.world.children.tick(self.world)
        self.assertEqual((self.bundle.carried_by, self.bundle.place), (None, BED), "put down in a bed that is free")

    def test_a_bundle_left_on_the_ground_is_worse_off_than_one_in_a_bed(self) -> None:
        other = _born(self.world)
        for parent in ("ines", "tomas"):
            self.world.residents[parent].expedition = object()
        self.world.children.tick(self.world)
        self.bundle.place, other.place = GROUND, BED
        for _ in range(300):
            self.world.children.tick(self.world)
        self.assertLess(self.bundle.health, other.health - 5)
        self.assertLess(self.bundle.health, 100.0)
        early = 100.0 - self.bundle.health
        for _ in range(300):
            self.world.children.tick(self.world)
        self.assertGreater(100.0 - early - self.bundle.health, early, "the more so the longer it is left")
        self.assertEqual(self.world.decisions, {}, "its parents are only away")

    def test_a_bundle_whose_parents_die_is_taken_in_by_someone_and_lives(self) -> None:
        for parent in ("ines", "tomas"):
            self.world.health.die(self.world, self.world.residents[parent], "una prueba")
        self.world.step(2)
        decision = next(d for d in self.world.decisions.values() if d.kind == TAKE_IN)
        self.assertIn(self.bundle.name, decision.prompt)
        self.assertIn("child_alone", _types(self.world))
        taker = self.world.residents[decision.resident_id]
        taker.personality = Personality(empathy=90)
        self.assertEqual(self.world.apply_command(ChooseOptionCommand(decision.decision_id, "encourage")), "take_in")
        self.world.step(2)
        self.assertEqual(self.bundle.carried_by, taker.resident_id)
        tree = self.world.family.kin.tree(self.world, self.bundle.child_id)
        self.assertEqual([each[0] for each in tree["parents"]], ["ines", "tomas", taker.resident_id])
        self.assertEqual(self.world.family.kin.tie(self.world, taker.resident_id, self.bundle.child_id), "child")
        self.assertIn("child_taken_in", _types(self.world))
        self.world.step(MINUTES_PER_DAY)
        self.assertIn(self.bundle.child_id, self.world.bundles)

    def test_taken_in_by_nobody_it_dies_and_never_without_the_player_having_had_a_say(self) -> None:
        for parent in ("ines", "tomas"):
            self.world.health.die(self.world, self.world.residents[parent], "una prueba")
        for resident in self.world.residents.values():
            resident.personality = Personality(empathy=0, greed=100)
        asked = set()
        for _ in range(3 * MINUTES_PER_DAY):
            self.world.step(1)
            _content(self.world)
            for decision in [d for d in self.world.decisions.values() if d.kind == TAKE_IN]:
                self.assertIn(self.bundle.child_id, self.world.bundles, "nobody is asked about a child who is dead")
                asked.add(decision.resident_id)
                self.world.apply_command(ChooseOptionCommand(decision.decision_id, "neutral"))
            if self.bundle.child_id not in self.world.bundles:
                break
        self.assertNotIn(self.bundle.child_id, self.world.bundles)
        self.assertGreaterEqual(len(asked), 2, "more than one of them was asked")
        self.assertIn("child_died", _types(self.world))
        self.assertEqual(self.world.deaths[-1].resident_id, self.bundle.child_id)
        self.assertIn(self.bundle.child_id, self.world.kinship, "it stays in the tree")

    def test_a_bundle_and_a_child_on_the_way_survive_saving(self) -> None:
        manager = SaveManager()
        self.world.residents["nuria"].expecting_with, self.world.residents["nuria"].due_day = "raul", 40
        self.bundle.hunger, self.bundle.health, self.bundle.refused = 12.5, 80.0, ["paco"]
        loaded = manager.from_data(json.loads(json.dumps(manager.to_data(self.world))))
        self.assertEqual(loaded.bundles, self.world.bundles)
        self.assertEqual((loaded.residents["nuria"].expecting_with, loaded.residents["nuria"].due_day), ("raul", 40))
        self.assertEqual(manager.to_data(loaded), manager.to_data(self.world))
        data = manager.to_data(self.world)
        data["version"] = 28
        del data["bundles"], data["kinship"]
        older = manager.from_data(json.loads(json.dumps(data)))
        self.assertEqual((older.bundles, older.kinship.get(self.bundle.child_id)), ({}, None))


class GrowingUpTests(unittest.TestCase):
    def setUp(self) -> None:
        self.world = _settled()
        self.bundle = _born(self.world)

    def test_a_childs_age_goes_week_by_week_to_ten_and_year_by_year_after(self) -> None:
        ages = []
        for _ in range(11):
            _midnight(self.world, 7)
            ages.append(self.world.children.age_of(self.world, self.bundle))
        self.assertEqual(ages, [0, 1, 2, 3, 4, 5, 5, 6, 7, 8, 9])
        self.assertIn(self.bundle.child_id, self.world.bundles)
        _midnight(self.world, 7)
        child = self.world.residents[self.bundle.child_id]
        self.assertNotIn(child.resident_id, self.world.bundles)
        self.assertEqual((child.age, child.sex, child.personality), (10, self.bundle.sex, self.bundle.personality))
        self.assertTrue(any(f"{child.name} tiene ya diez años" in line for line in self.world.event_log))
        self.assertEqual(self.world.family.kin.tie(self.world, "ines", child.resident_id), "child")
        self.assertGreater(self.world.relationship(child.resident_id, "ines").affection, 0, "kin from the first day")
        _midnight(self.world, DAYS_PER_YEAR - 1)
        self.assertEqual(child.age, 10)
        _midnight(self.world)
        self.assertEqual(child.age, 11, "a year after, on their birthday")
        self.assertTrue(any(f"{child.name} cumple 11 años" in line for line in self.world.event_log))

    def _grown(self) -> Resident:
        _midnight(self.world, 12 * 7)
        return self.world.residents[self.bundle.child_id]

    def test_from_ten_a_child_can_be_given_a_post_and_is_kept_out_of_romance(self) -> None:
        child = self._grown()
        self.assertTrue(self.world.staffing.assign(self.world, child, "farmer"))
        self.assertEqual(child.job_id, "farmer")
        child.personality.libido = 100.0
        raul = self.world.residents["raul"]
        self.assertFalse(self.world.family.may_court(self.world, raul, child))
        self.assertFalse(self.world.family.may_court(self.world, child, raul))
        self.assertEqual(self.world.family.desire(self.world, child), 0.0)
        self.assertFalse(self.world.children.together(self.world, child, raul))

    def test_nobody_under_age_has_to_earn_their_keep(self) -> None:
        child = self._grown()
        child.last_worked = self.world.clock.total_minutes - 10 * MINUTES_PER_DAY
        self.assertTrue(self.world.trade.supplied(self.world, child))
        raul = self.world.residents["raul"]
        raul.last_worked = child.last_worked
        self.assertFalse(self.world.trade.supplied(self.world, raul))

    def test_a_child_at_work_is_taken_worse_by_whoever_sees_it_than_an_adult_at_the_same_post(self) -> None:
        child = self._grown()
        raul, nuria = _apart(self.world, "raul", "nuria")
        child.x, child.y = 40, 13
        child.activity = Activity("wander", minutes_left=600, using=True)
        for resident in (raul, nuria):
            resident.mood, resident.needs.stress = 60.0, 0.0
        self.world.emit_event(DomainEvent("work_started", 5, "Nuria se pone a trabajar", ["nuria"]))
        self.assertEqual((raul.mood, raul.needs.stress), (60.0, 0.0))
        self.world.emit_event(DomainEvent("work_started", 5, "La criatura se pone a trabajar", [child.resident_id]))
        settings = self.world.registries.family.children
        self.assertEqual((raul.mood, raul.needs.stress), (60.0 - settings.seen_mood, settings.seen_stress))
        self.assertEqual(nuria.mood, 60.0 - settings.seen_mood)
        self.assertEqual(self.world.residents["marta"].mood, self.world.residents["vera"].mood, "who saw nothing")

    def test_a_settlement_that_puts_a_child_to_work_is_lower_in_mood(self) -> None:
        moods = {}
        for at_work in (True, False):
            # A week is short for this: over fourteen seeds it holds in twelve, and this is one,
            # in the settlement as it was when they were counted, with no store (S53).
            world = no_store(SimulationWorld.demo_world(seed=2))
            child = Resident("alba", "Alba", age=10, x=42, y=14)
            world.residents["alba"] = child
            world.family.welcome(world, child)
            if at_work:
                self.assertTrue(world.staffing.assign(world, child, "farmer"))
            # Mood comes back in a few hours, so it is looked at all through the days and not at the end.
            seen = []
            for _ in range(5 * 24):
                world.step(60)
                grown = [r for r in world.residents.values() if r.age >= 18]
                seen.append(sum(r.mood for r in grown) / len(grown))
            moods[at_work] = sum(seen) / len(seen)
        # With mood low a settlement quarrels the sooner (S15). How often it does in one week
        # goes more by chance than by this, so it is the mood that is looked at here.
        self.assertLess(moods[True], moods[False] - 0.5)


class SleepingRoughTests(unittest.TestCase):
    def _night(self, with_beds: bool) -> tuple[SimulationWorld, Resident]:
        world = _settled()
        for extra in [resident_id for resident_id in world.residents if resident_id != "marta"]:
            del world.residents[extra]
        if not with_beds:
            for object_id in [o for o, placed in world.interactables.items() if placed.kind == "bed"]:
                del world.interactables[object_id]
        marta = world.residents["marta"]
        marta.needs.tiredness = 90
        world.clock.hour = 23
        return world, marta

    def test_whoever_has_no_bed_curls_up_on_the_ground_and_wakes_less_rested(self) -> None:
        rough_world, rough = self._night(with_beds=False)
        bed_world, abed = self._night(with_beds=True)
        for world, resident in ((rough_world, rough), (bed_world, abed)):
            for _ in range(240):
                world.step(1)
                resident.needs.hunger = resident.needs.thirst = 0
        self.assertEqual(rough.current_action, SLEEP_ROUGH_ACTION)
        self.assertFalse(rough_world.is_aware(rough))
        self.assertEqual(abed.current_action, "sleep")
        self.assertLess(rough.needs.tiredness, 90, "it is some rest")
        self.assertGreater(rough.needs.tiredness, abed.needs.tiredness + 10, "and less than a bed gives")
        self.assertGreater(rough.needs.stress, abed.needs.stress)
        self.assertEqual(_types(rough_world).count("slept_rough"), 1)
        self.assertNotIn("slept_rough", _types(bed_world))

    def test_nobody_lies_down_on_the_ground_for_being_a_little_tired(self) -> None:
        world, marta = self._night(with_beds=False)
        marta.needs.tiredness = 40
        self.assertIsNone(world.family.rough_candidate(world, marta, bed_to_be_had=False))
        marta.needs.tiredness = 90
        self.assertIsNone(world.family.rough_candidate(world, marta, bed_to_be_had=True))
        self.assertIsNotNone(world.family.rough_candidate(world, marta, bed_to_be_had=False))


if __name__ == "__main__":
    unittest.main()
