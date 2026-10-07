import json
import subprocess
import sys
import unittest
from dataclasses import replace
from pathlib import Path

from save.save_manager import SaveManager
from simulation.commands import ChooseOptionCommand, ProposeGovernmentCommand
from simulation.events.event import DomainEvent
from simulation.knowledge.fact import SOURCE_TOLD
from simulation.knowledge.knowledge_system import learn
from simulation.politics.government import LEANINGS, MEASURES, politics_settings_from_data
from simulation.politics.leadership import RESIGN
from simulation.politics.political_event import PoliticalEvent
from simulation.residents.activity import Activity
from simulation.work.expedition import Expedition
from simulation.residents.needs import Needs
from simulation.residents.resident import Resident
from simulation.world import SimulationWorld

ROOT = Path(__file__).resolve().parent.parent
KINDS = ("strong_mayor", "council", "direct_democracy", "military_leadership", "commune", "personalist_rule")


def _politics(world: SimulationWorld, **changes) -> SimulationWorld:
    """The same world with something about how politics goes changed."""
    world.registries = replace(world.registries, politics=replace(world.registries.politics, **changes))
    return world


def _settled(seed: int = 7) -> SimulationWorld:
    """The ready-made settlement with nothing felt by anyone for anyone, and nobody in need."""
    world = SimulationWorld.demo_world(seed=seed)
    world.relationships.clear()
    for resident in world.residents.values():
        resident.needs = Needs(hunger=0, tiredness=0, social=0, stress=0)
    return world


def _governed(kind: str, seed: int = 7, **changes) -> SimulationWorld:
    """The ready-made settlement under one kind of government, with votes that take an hour."""
    world = _politics(_settled(seed), election_hours=1, **changes)
    world.politics.leadership.establish(world, kind)
    return world


def _types(world: SimulationWorld) -> list[str]:
    return [line.split(" | ")[1] for line in world.event_log]


def _gathered(world: SimulationWorld) -> None:
    """Stand everybody together in the open, awake, where each sees the rest."""
    for index, resident in enumerate(world.residents.values()):
        resident.x, resident.y = 39 + index % 3, 11 + index // 3
        resident.activity = Activity("wander", minutes_left=600, using=True)


def _fights(world: SimulationWorld, starter: str, other: str, times: int = 1) -> None:
    """Have it seen by whoever is about that one resident starts a fight with another."""
    one, two = world.residents[starter], world.residents[other]
    for _ in range(times):
        world.emit_event(
            DomainEvent("fight_started", 60, f"{one.name} se lía a golpes con {two.name}", [starter, other]),
            at=one.tile,
            fact_text=f"{one.name} pegó a {two.name}",
        )


def _held(world: SimulationWorld, resident_id: str):
    return world.politics.legitimacy.profile(world, world.residents[resident_id])


def _midnight(world: SimulationWorld, days: int = 1) -> None:
    """Have that many days of politics begin, with nothing else happening in them."""
    for _ in range(days):
        world.clock.day += 1
        world.clock.hour, world.clock.minute = 0, 0
        world.politics.tick(world)


class GovernmentDataTests(unittest.TestCase):
    def test_the_six_kinds_to_begin_with_are_data_and_say_how_each_is_run(self) -> None:
        settings = SimulationWorld.demo_world().registries.politics
        self.assertEqual(tuple(settings.governments), KINDS)
        mayor, council, commune = (settings.governments[kind] for kind in ("strong_mayor", "council", "commune"))
        self.assertEqual((mayor.leader_role, mayor.proposes, mayor.approves, mayor.veto), ("mayor", "leader", "leader", True))
        self.assertEqual((mayor.term_days, mayor.succession), (56, ("election",)))
        self.assertEqual((council.leader_role, council.council_role, council.council_seats), (None, "councillor", 3))
        self.assertEqual((commune.votes, commune.approval, commune.succession), ("everyone", 0.75, ()))
        self.assertGreater(settings.governments["personalist_rule"].abuse_tolerance, mayor.abuse_tolerance)
        self.assertEqual(settings.roles["mayor"].called("f"), "alcaldesa")
        self.assertEqual(settings.roles["mayor"].called("nb"), "alcalde")

    def test_a_kind_that_makes_no_sense_is_refused(self) -> None:
        roles = {"mayor": {"name": "alcalde"}}
        sound = {"name": "Alcaldía", "leader_role": "mayor", "succession": ["election"]}
        politics_settings_from_data({"roles": roles, "governments": {"one": sound}})
        for wrong in (
            {**sound, "succession": ["lottery"]},
            {**sound, "succession": []},
            {"name": "Nadie", "succession": ["election"]},
            {**sound, "leader_role": "king"},
            {**sound, "council_seats": 3},
            {**sound, "approves": "the player"},
            {**sound, "appeal": {"luck": 1}},
            {**sound, "starts": {"happiness": 50}},
            {**sound, "abuse_tolerance": 140},
        ):
            with self.assertRaises(ValueError, msg=wrong):
                politics_settings_from_data({"roles": roles, "governments": {"one": wrong}})
        with self.assertRaises(ValueError):
            politics_settings_from_data({"profile": {"leanings": {"fearfulness": {"luck": 1}}}})
        with self.assertRaises(ValueError):
            politics_settings_from_data({"reactions": {"death": {"holds": {"hunger": 5}}}})

    def test_politics_needs_no_pygame(self) -> None:
        check = (
            "import sys; import simulation.world, save.save_manager; "
            "import simulation.politics.government, simulation.politics.leadership, simulation.politics.legitimacy; "
            "import simulation.politics.political_event, simulation.politics.politics_system; "
            "from simulation.world import SimulationWorld; SimulationWorld.demo_world().step(900); "
            "sys.exit(1 if 'pygame' in sys.modules else 0)"
        )
        done = subprocess.run([sys.executable, "-c", check], cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(done.returncode, 0, done.stderr)


class FoundingTests(unittest.TestCase):
    def _newcomer(self, world: SimulationWorld, resident_id: str, age: int = 30) -> Resident:
        resident = Resident(resident_id, resident_id.title(), x=10, y=10, age=age, last_worked=world.clock.total_minutes)
        world.residents[resident_id] = resident
        world.family.welcome(world, resident)
        return resident

    def test_two_have_no_government_and_a_third_has_them_choose_one(self) -> None:
        world = _politics(SimulationWorld.new_settlement(), choosing_hours=1)
        self._newcomer(world, "ana")
        self._newcomer(world, "blas")
        world.step(180)
        self.assertIsNone(world.government.kind)
        self.assertIsNone(world.government.choosing_until, "two simply get along")
        self.assertEqual(set(world.government.measures.values()), {0.0})
        self._newcomer(world, "cruz")
        world.step(1)
        self.assertIsNotNone(world.government.choosing_until)
        self.assertIsNone(world.government.kind, "they take their time over it")
        world.step(60)
        self.assertIn(world.government.kind, KINDS)
        self.assertEqual(_types(world).count("government_chosen"), 1)
        chosen = next(event for event in world.history if event.event_type == "government_chosen")
        self.assertIsInstance(chosen, PoliticalEvent)
        self.assertEqual(sorted(chosen.participants), ["ana", "blas", "cruz"])
        self.assertEqual(chosen.government, world.government.kind)

    def test_the_ready_made_settlement_chooses_on_its_first_day(self) -> None:
        world = SimulationWorld.demo_world()
        self.assertIsNone(world.government.kind)
        world.step(60 * 13)
        self.assertEqual(world.clock.day, 1)
        self.assertIn(world.government.kind, KINDS)
        kinds = _types(world)
        self.assertLess(kinds.index("government_choosing"), kinds.index("government_chosen"))
        self.assertGreater(world.government.measures["legitimacy"], 0)

    def test_the_same_settlement_always_chooses_the_same_and_another_may_not(self) -> None:
        def chosen(seed: int) -> tuple:
            world = SimulationWorld.demo_world(seed=seed)
            world.politics.leadership.settle_choosing(world)
            return world.government.kind, world.government.leader, tuple(world.government.council)

        self.assertEqual(chosen(7), chosen(7))
        self.assertGreater(len({chosen(seed)[0] for seed in range(1, 13)}), 2, "who lives there decides it")

    def test_each_chooses_by_what_they_hold(self) -> None:
        world = _settled()
        leadership = world.politics.leadership
        vera, paco = world.residents["vera"], world.residents["paco"]
        _held(world, "vera").collectivism, _held(world, "vera").individualism = 95.0, 5.0
        _held(world, "paco").authoritarian_tolerance, _held(world, "paco").fearfulness = 95.0, 90.0
        hers, his = leadership.appeal(world, vera), leadership.appeal(world, paco)
        self.assertEqual(max(hers, key=hers.get), "commune")
        self.assertEqual(max(his, key=his.get), "military_leadership")

    def test_the_player_puts_one_kind_to_everyone_once_and_it_only_weighs(self) -> None:
        world = _settled()
        self.assertFalse(world.apply_command(ProposeGovernmentCommand("commune")).ok, "nobody is choosing yet")
        world.politics.leadership.open_choosing(world)
        leadership, tomas = world.politics.leadership, world.residents["tomas"]
        before = leadership.appeal(world, tomas)
        self.assertFalse(world.apply_command(ProposeGovernmentCommand("empire")).ok)
        self.assertTrue(world.apply_command(ProposeGovernmentCommand("commune")).ok)
        self.assertIn("government_proposed", _types(world))
        self.assertFalse(world.apply_command(ProposeGovernmentCommand("council")).ok, "one proposal, and no more")
        after = leadership.appeal(world, tomas)
        self.assertGreater(after["commune"], before["commune"])
        self.assertEqual(after["council"], before["council"])
        self.assertNotEqual(max(after, key=after.get), "commune", "he is still against it, for all that")
        tomas.personality.impulsiveness = 100.0
        self.assertLess(leadership.appeal(world, tomas)["commune"], after["commune"], "some heed advice less")
        leadership.settle_choosing(world)
        self.assertFalse(world.apply_command(ProposeGovernmentCommand("council")).ok, "it is settled")

    def test_what_the_player_proposes_can_tip_it_and_cannot_cast_anyones_say(self) -> None:
        plain = _settled(seed=3)
        plain.politics.leadership.settle_choosing(plain)
        other = next(kind for kind in KINDS if kind != plain.government.kind)
        pushed = _politics(_settled(seed=3), proposal_weight=50.0)
        pushed.politics.leadership.open_choosing(pushed)
        pushed.apply_command(ProposeGovernmentCommand(other))
        pushed.politics.leadership.settle_choosing(pushed)
        self.assertEqual(pushed.government.kind, other)
        unheard = _politics(_settled(seed=3), proposal_weight=0.0)
        unheard.politics.leadership.open_choosing(unheard)
        unheard.apply_command(ProposeGovernmentCommand(other))
        unheard.politics.leadership.settle_choosing(unheard)
        self.assertEqual(unheard.government.kind, plain.government.kind)

    def test_only_adults_who_are_there_are_asked_and_fewer_than_three_later_undoes_nothing(self) -> None:
        world = _politics(_settled(), choosing_hours=0)
        world.residents["paco"].age = 12
        world.residents["nuria"].expedition = Expedition(10**9, 0, 0.0)
        world.step(1)
        world.step(1)
        chosen = next(event for event in world.history if event.event_type == "government_chosen")
        self.assertEqual(len(chosen.participants), 7)
        self.assertNotIn("paco", chosen.participants)
        self.assertNotIn("nuria", chosen.participants)
        kind = world.government.kind
        for resident_id in list(world.residents)[2:]:
            if resident_id != world.government.leader:
                del world.residents[resident_id]
        world.government.council = [each for each in world.government.council if each in world.residents]
        self.assertLess(len(world.residents), 4)
        world.politics.tick(world)
        self.assertEqual(world.government.kind, kind)

    def test_how_many_wanted_it_is_how_legitimate_it_starts_and_who_did_trusts_it_more(self) -> None:
        world = _settled()
        world.politics.leadership.settle_choosing(world)
        chosen = next(event for event in world.history if event.event_type == "government_chosen")
        behind = chosen.data["wanted"][world.government.kind]
        settings = world.registries.politics
        floor = settings.legitimacy_floor
        seat = sum(settings.seated.get(way, {}).get("legitimacy", 0.0) for way in ("election", "following", "strongest"))
        legitimacy = world.government.measures["legitimacy"]
        self.assertAlmostEqual(legitimacy, floor + (100 - floor) * behind / 9, delta=abs(seat) + 0.01)
        trust = sorted({profile.trust for profile in world.political_profiles.values()})
        self.assertEqual(trust, [settings.trust_start + settings.unbacked_trust, settings.trust_start + settings.backed_trust])


class ProfileTests(unittest.TestCase):
    def test_what_somebody_holds_comes_of_who_they_are(self) -> None:
        brave, timid = _settled(), _settled()
        brave.residents["tomas"].personality.courage = 95.0
        timid.residents["tomas"].personality.courage = 5.0
        self.assertLess(_held(brave, "tomas").fearfulness + 40, _held(timid, "tomas").fearfulness)
        kind, mean = _settled(), _settled()
        kind.residents["ines"].personality.empathy, mean.residents["ines"].personality.empathy = 95.0, 5.0
        self.assertGreater(_held(kind, "ines").justice_sensitivity, _held(mean, "ines").justice_sensitivity + 25)
        self.assertLess(_held(kind, "ines").revengefulness, _held(mean, "ines").revengefulness)

    def test_a_trait_tells_on_it_too(self) -> None:
        plain, wicked = _settled(), _settled()
        wicked.residents["ines"].traits = ["wicked"]
        self.assertAlmostEqual(
            _held(plain, "ines").justice_sensitivity - 25, _held(wicked, "ines").justice_sensitivity, delta=0.11
        )
        self.assertEqual(_held(plain, "ines").collectivism, _held(wicked, "ines").collectivism)

    def test_each_has_a_leaning_of_their_own_that_is_always_the_same(self) -> None:
        world = _settled()
        for resident in world.residents.values():
            resident.personality, resident.traits = replace(world.residents["marta"].personality), []
        leanings = {
            resident_id: tuple(getattr(_held(world, resident_id), leaning) for leaning in LEANINGS)
            for resident_id in world.residents
        }
        self.assertEqual(len(set(leanings.values())), 9, "nine alike in every way, and no two of a mind")
        again = _settled()
        for resident in again.residents.values():
            resident.personality, resident.traits = replace(again.residents["marta"].personality), []
        self.assertEqual(leanings["paco"], tuple(getattr(_held(again, "paco"), leaning) for leaning in LEANINGS))
        elsewhere = _settled(seed=8)
        for resident in elsewhere.residents.values():
            resident.personality, resident.traits = replace(elsewhere.residents["marta"].personality), []
        self.assertNotEqual(leanings["paco"], tuple(getattr(_held(elsewhere, "paco"), leaning) for leaning in LEANINGS))
        for values in leanings.values():
            self.assertTrue(all(0 <= value <= 100 for value in values))

    def test_it_is_kept_apart_from_the_resident_and_asking_draws_nothing(self) -> None:
        world = _settled()
        state = world.rng.get_state()
        profile = _held(world, "lucia")
        self.assertIs(world.political_profiles["lucia"], profile)
        self.assertFalse(any("politic" in name for name in vars(world.residents["lucia"])))
        self.assertEqual(world.rng.get_state(), state)


class SeatTests(unittest.TestCase):
    def test_each_kind_seats_who_it_says_and_whoever_leads_is_a_resident_with_a_role(self) -> None:
        seats = {}
        for kind in KINDS:
            world = _governed(kind)
            state = world.government
            leader = world.residents.get(state.leader or "")
            seats[kind] = (leader.roles if leader else None, len(state.council))
            for member in state.council:
                self.assertEqual(world.residents[member].roles, ["councillor"])
            if leader is not None:
                self.assertIsInstance(leader, Resident)
                self.assertIn(f"Me toca mandar: soy {world.politics.leadership.role_name(world, leader.roles[0], leader)}.",
                              [memory.text for memory in world.memories.of(leader.resident_id)])
        self.assertEqual(
            seats,
            {
                "strong_mayor": (["mayor"], 0),
                "council": (None, 3),
                "direct_democracy": (None, 0),
                "military_leadership": (["commander"], 0),
                "commune": (None, 0),
                "personalist_rule": (["ruler"], 0),
            },
        )

    def test_a_vote_goes_by_what_each_feels_for_who_stands_and_by_what_they_are_like(self) -> None:
        world = _settled()
        leadership = world.politics.leadership
        winner, backers = leadership.elect(world, leadership.present(world), leadership.present(world))
        self.assertEqual(winner.resident_id, "marta", "with nothing felt for anyone, whoever wins people over")
        for voter in world.residents:
            if voter != "paco":
                feelings = world.relationship(voter, "paco")
                feelings.affection, feelings.trust = 80.0, 70.0
        winner, backers = leadership.elect(world, leadership.present(world), leadership.present(world))
        self.assertEqual(winner.resident_id, "paco")
        # Whoever wants the seat enough to put themselves forward is for themselves (S27).
        keen = {
            resident_id
            for resident_id, resident in world.residents.items()
            if world.politics.elections.will(world, resident) >= 0
        }
        self.assertIn("paco", keen, "thought so much of, even he fancies it")
        self.assertEqual(backers, set(world.residents) - (keen - {"paco"}))
        self.assertIn("nuria", backers)
        world.relationship("nuria", "paco").resentment = 100.0
        world.relationship("nuria", "paco").affection = -50.0
        nuria = world.residents["nuria"]
        hers = max(leadership.present(world), key=lambda each: leadership.vote_score(world, nuria, each))
        self.assertNotEqual(hers.resident_id, "paco", "one may vote against who would do the rest good")

    def test_the_strongest_is_whoever_nobody_stands_up_to(self) -> None:
        world = _governed("military_leadership")
        self.assertEqual(world.government.leader, "tomas")
        other = _settled()
        for resident_id in other.residents:
            if resident_id != "paco":
                other.relationship(resident_id, "paco").fear = 90.0
        other.politics.leadership.establish(other, "military_leadership")
        self.assertEqual(other.government.leader, "paco", "being feared counts")


class SuccessionTests(unittest.TestCase):
    def test_a_mayor_who_resigns_is_followed_by_whoever_wins_the_vote_that_is_called(self) -> None:
        world = _governed("strong_mayor")
        first = world.residents[world.government.leader]
        self.assertTrue(world.politics.leadership.resign(world, first))
        self.assertEqual(first.roles, [])
        self.assertIsNone(world.government.leader)
        self.assertIsNotNone(world.government.election_at, "the seat stands empty until the vote")
        self.assertEqual(_types(world)[-2:], ["leader_resigned", "election_called"])
        world.step(61)
        second = world.residents[world.government.leader]
        self.assertIsNot(second, first, "whoever stepped down is not the one to follow themselves")
        self.assertEqual(second.roles, ["mayor"])
        self.assertIn("election_held", _types(world))
        self.assertIn("Dejé de ser alcaldesa.", [memory.text for memory in world.memories.of(first.resident_id)])
        self.assertFalse(world.politics.leadership.resign(world, first), "they hold nothing to step down from")

    def test_a_commander_who_resigns_is_followed_at_once_by_the_next_strongest(self) -> None:
        world = _governed("military_leadership")
        self.assertTrue(world.politics.leadership.resign(world, world.residents["tomas"]))
        self.assertNotIn(world.government.leader, (None, "tomas"))
        self.assertEqual(world.residents[world.government.leader].roles, ["commander"])
        self.assertIsNone(world.government.election_at)

    def test_a_ruler_is_followed_by_whoever_they_would_have_and_failing_that_by_who_has_a_following(self) -> None:
        world = _governed("personalist_rule")
        ruler, tomas = world.residents[world.government.leader], world.residents["tomas"]
        self.assertEqual(ruler.resident_id, "marta")
        self.assertIsNone(world.government.heir)
        _midnight(world)
        self.assertEqual(world.government.heir, "vera", "her sister: grown kin come before anybody else")
        name = world.politics.leadership._name_heir
        self.assertIsNone(name(world, tomas), "he has no kin, and thinks that much of nobody yet")
        feelings = world.relationship("tomas", "paco")
        feelings.affection, feelings.trust = 60.0, 40.0
        self.assertEqual(name(world, tomas), "paco")
        ruler.couple_with, world.residents["sergio"].couple_with = "sergio", ruler.resident_id
        _midnight(world)
        self.assertEqual(world.government.heir, "sergio", "a partner comes first")
        world.health.die(world, ruler, "una prueba")
        world.step(1)
        self.assertEqual(world.government.leader, "sergio")
        seated = [event for event in world.history if event.event_type == "leader_chosen"][-1]
        self.assertEqual(seated.data["way"], "heir")
        world.government.heir = None
        world.health.die(world, world.residents["sergio"], "una prueba")
        world.step(1)
        seated = [event for event in world.history if event.event_type == "leader_chosen"][-1]
        self.assertEqual(seated.data["way"], "following")
        self.assertEqual(world.residents[world.government.leader].roles, ["ruler"])

    def test_a_mayor_who_dies_leaves_a_settlement_that_goes_on_without_one_and_then_with(self) -> None:
        world = _governed("strong_mayor")
        mayor = world.residents[world.government.leader]
        stability = world.government.measures["stability"]
        world.health.die(world, mayor, "una prueba")
        world.step(30)
        self.assertIsNone(world.government.leader)
        self.assertEqual(world.government.kind, "strong_mayor")
        lost = next(event for event in world.history if event.event_type == "leader_lost")
        self.assertIsInstance(lost, PoliticalEvent)
        self.assertTrue(lost.data["died"])
        self.assertIn(mayor.name, lost.text)
        self.assertLess(world.government.measures["stability"], stability)
        self.assertEqual(len(world.residents), 8)
        world.step(60)
        self.assertIn(world.government.leader, world.residents)

    def test_with_nobody_to_take_it_the_seat_stands_empty_and_it_costs_until_somebody_does(self) -> None:
        world = _governed("military_leadership")
        for resident in world.residents.values():
            resident.expedition = Expedition(10**9, 0, 0.0) if resident.resident_id != "tomas" else None
        world.politics.leadership.resign(world, world.residents["tomas"])
        self.assertIsNone(world.government.leader)
        self.assertIn("leader_seat_empty", _types(world))
        legitimacy = world.government.measures["legitimacy"]
        _midnight(world, 3)
        self.assertIsNone(world.government.leader)
        self.assertEqual(_types(world).count("leader_seat_empty"), 1)
        self.assertAlmostEqual(
            world.government.measures["legitimacy"], legitimacy + 3 * world.registries.politics.vacancy_legitimacy
        )
        world.residents["raul"].expedition = None
        _midnight(world)
        self.assertEqual(world.government.leader, "raul")
        self.assertIsNone(world.government.vacant_since)

    def test_a_mayor_has_to_win_again_when_the_term_is_up_and_may_lose(self) -> None:
        kept, lost = _governed("strong_mayor"), _governed("strong_mayor")
        for world in (kept, lost):
            world.clock.day += 56
            self.assertEqual(world.government.leader, "marta")
        for voter in lost.residents:
            if voter not in ("marta", "vera"):
                _held(lost, voter).loyalty = 0.0
                lost.relationship(voter, "marta").resentment = 60.0
                lost.relationship(voter, "vera").affection = 60.0
        for world in (kept, lost):
            world.step(1)
            self.assertIn("election_called", _types(world))
            self.assertEqual(world.government.leader, "marta", "she leads until the vote is held")
            world.step(60)
        self.assertEqual(kept.government.leader, "marta")
        self.assertEqual(kept.government.term_began, kept.clock.day)
        self.assertTrue([e for e in kept.history if e.event_type == "election_held"][-1].data["kept"])
        self.assertEqual(lost.government.leader, "vera")
        self.assertEqual((lost.residents["marta"].roles, lost.residents["vera"].roles), ([], ["mayor"]))
        self.assertIn(
            "Perdí la votación: ahora manda Vera.", [memory.text for memory in lost.memories.of("marta")]
        )
        kept.step(120)
        self.assertEqual(_types(kept).count("election_called"), 1, "and not again until the next term is up")

    def test_a_seat_on_the_council_left_empty_is_voted_for_again(self) -> None:
        world = _governed("council")
        before = list(world.government.council)
        world.health.die(world, world.residents[before[0]], "una prueba")
        world.step(1)
        self.assertEqual(world.government.council, before[1:])
        world.step(61)
        self.assertEqual(len(world.government.council), 3)
        self.assertEqual(world.government.council[:2], before[1:])
        self.assertTrue(world.politics.leadership.resign(world, world.residents[before[1]]))
        self.assertEqual(world.residents[before[1]].roles, [])
        self.assertIn("council_seat_left", _types(world))

    def test_the_kind_of_government_can_change_in_the_middle_of_a_game(self) -> None:
        world = _governed("strong_mayor")
        world.government.measures.update({"corruption": 33.0, "legitimacy": 61.0, "stability": 70.0})
        self.assertTrue(world.politics.leadership.change_kind(world, "military_leadership"))
        state = world.government
        self.assertEqual((state.kind, state.leader), ("military_leadership", "tomas"))
        self.assertEqual((world.residents["marta"].roles, world.residents["tomas"].roles), ([], ["commander"]))
        self.assertEqual(state.measures["authoritarianism"], 75.0 + 4.0)
        self.assertEqual(state.measures["corruption"], 33.0)
        self.assertLess(state.measures["stability"], 70.0)
        self.assertIn("government_changed", _types(world))
        self.assertTrue(world.politics.leadership.change_kind(world, "council", {"marta": "council", "raul": "commune"}))
        self.assertEqual((state.leader, len(state.council)), (None, 3))
        self.assertEqual(world.residents["tomas"].roles, [r for r in ["councillor"] if "tomas" in state.council])
        self.assertFalse(world.politics.leadership.change_kind(world, "council"))
        self.assertFalse(world.politics.leadership.change_kind(world, "empire"))

    def test_loyalty_is_to_the_person_and_trust_in_the_government_stays(self) -> None:
        world = _governed("strong_mayor")
        legitimacy = world.politics.legitimacy
        for resident_id in world.residents:
            if resident_id != "marta":
                profile = _held(world, resident_id)
                profile.loyalty, profile.trust = 95.0, 80.0
        world.relationship("paco", "vera").affection = 80.0
        world.politics.leadership.resign(world, world.residents["marta"])
        world.step(61)
        new = world.residents[world.government.leader]
        seated = [event for event in world.history if event.event_type == "leader_chosen"][-1]
        self.assertEqual(seated.data["backers"], [], "a mayor is voted for in secret: nobody is told who was behind them")
        # Who was behind them is in what the world keeps of the vote, and nowhere else (S27).
        behind = {
            voter for voter, candidate in world.government.elections[-1].backed.items() if candidate == new.resident_id
        }
        backed = world.registries.politics.backed_loyalty
        for resident in world.residents.values():
            if resident is new:
                continue
            profile = _held(world, resident.resident_id)
            extra = backed if resident.resident_id in behind else 0.0
            self.assertAlmostEqual(profile.loyalty, min(100.0, legitimacy.ground(world, resident, new) + extra))
            self.assertLess(profile.loyalty, 95.0)
            if resident.resident_id != "marta":
                self.assertEqual(profile.trust, 80.0)


class LegitimacyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.world = _governed("strong_mayor")
        _gathered(self.world)
        self.measures = self.world.government.measures
        self.legitimacy = self.measures["legitimacy"]

    def test_a_settlement_can_be_brought_to_high_fear_with_low_loyalty_to_its_leader(self) -> None:
        for victim in ("paco", "lucia", "nuria", "ines", "sergio", "raul", "vera", "tomas"):
            _fights(self.world, "marta", victim, times=2)
        held = self.world.politics.legitimacy.measure(self.world)
        self.assertGreater(self.measures["fear"], 70)
        self.assertLess(held["loyalty"], 15)
        self.assertGreater(held["resentment"], 20)
        self.assertLess(self.measures["legitimacy"], self.legitimacy - 25)
        self.assertGreater(self.measures["authoritarianism"], 45)
        self.assertEqual(self.world.government.leader, "marta", "and she still leads")

    def test_the_same_done_by_someone_who_does_not_govern_is_no_matter_of_politics(self) -> None:
        before = (dict(self.measures), {each: vars(_held(self.world, each)).copy() for each in self.world.residents})
        _fights(self.world, "raul", "paco", times=3)
        self.world.politics.legitimacy.measure(self.world)
        after = (dict(self.measures), {each: vars(_held(self.world, each)) for each in self.world.residents})
        self.assertEqual(before, after)

    def test_only_whoever_saw_it_or_is_told_thinks_any_different(self) -> None:
        nuria = self.world.residents["nuria"]
        nuria.x, nuria.y = 5, 26
        before = vars(_held(self.world, "nuria")).copy()
        _fights(self.world, "marta", "paco")
        self.assertEqual(vars(_held(self.world, "nuria")), before, "the world knows, and she does not")
        self.assertGreater(_held(self.world, "lucia").fear, 0)
        fact = [fact for fact in self.world.knowledge.facts.values() if fact.event_type == "fight_started"][-1]
        learn(self.world, nuria, fact, 0.6, SOURCE_TOLD, told_by="lucia")
        self.assertGreater(_held(self.world, "nuria").fear, 0)
        self.assertLess(_held(self.world, "nuria").fear, _held(self.world, "lucia").fear, "hearsay counts for less")

    def test_it_tells_on_each_in_their_own_way(self) -> None:
        timid, bold = _held(self.world, "lucia"), _held(self.world, "ines")
        timid.fearfulness, bold.fearfulness = 95.0, 5.0
        timid.justice_sensitivity = bold.justice_sensitivity = 50.0
        timid.loyalty = bold.loyalty = 60.0
        fond = self.world.relationship("vera", "paco")
        fond.affection = 90.0
        self.world.relationship("sergio", "paco").resentment = 90.0
        for each in ("vera", "sergio", "paco"):
            profile = _held(self.world, each)
            profile.loyalty, profile.justice_sensitivity = 60.0, 50.0
        _fights(self.world, "marta", "paco")
        self.assertGreater(timid.fear, bold.fear * 2)
        self.assertEqual(timid.loyalty, bold.loyalty)
        lost = {each: 60.0 - _held(self.world, each).loyalty for each in ("vera", "sergio", "paco", "lucia")}
        self.assertGreater(lost["paco"], lost["vera"], "whoever it was done to takes it worst")
        self.assertGreater(lost["vera"], lost["lucia"], "then whoever cares for him")
        self.assertGreater(lost["lucia"], lost["sergio"], "and least of all whoever cannot stand him")

    def test_obeying_and_resenting_are_two_things(self) -> None:
        legitimacy = self.world.politics.legitimacy
        cowed, free = _held(self.world, "lucia"), _held(self.world, "ines")
        cowed.loyalty, cowed.fear, cowed.resentment, cowed.fearfulness = 0.0, 95.0, 90.0, 70.0
        free.loyalty, free.fear, free.resentment = 0.0, 0.0, 90.0
        self.assertGreater(legitimacy.obedience(self.world, self.world.residents["lucia"]), 60)
        self.assertLess(legitimacy.obedience(self.world, self.world.residents["ines"]), 30)
        self.assertEqual(cowed.resentment, free.resentment, "she does as she is told and hates it no less")
        loyal = _held(self.world, "vera")
        loyal.loyalty, loyal.fear, loyal.resentment = 100.0, 0.0, 0.0
        self.assertGreater(legitimacy.obedience(self.world, self.world.residents["vera"]), 45)

    def test_a_leader_seen_to_steal_costs_trust_and_more_where_less_is_put_up_with(self) -> None:
        def stolen(kind: str) -> tuple[float, float, float]:
            world = _governed(kind)
            _gathered(world)
            leader = world.government.leader
            world.government.measures["legitimacy"] = 80.0
            trust = _held(world, "lucia").trust
            world.emit_event(
                DomainEvent("theft_committed", 50, "Roba", [leader]), at=world.residents[leader].tile,
                fact_text="robó de la caja", subjects=[leader],
            )
            return 80.0 - world.government.measures["legitimacy"], world.government.measures["corruption"], trust - _held(world, "lucia").trust

        mayor, ruler = stolen("strong_mayor"), stolen("personalist_rule")
        self.assertGreater(mayor[0], ruler[0] * 2, "a ruler is expected to")
        self.assertGreater(ruler[0], 0)
        self.assertGreater(mayor[1], 3)
        self.assertGreater(mayor[2], 3)

    def test_a_councillor_seen_to_do_it_costs_the_government_and_not_loyalty_to_anybody(self) -> None:
        world = _governed("council")
        _gathered(world)
        member = world.government.council[0]
        victim = next(each for each in world.residents if each not in world.government.council)
        watcher = next(each for each in world.residents if each not in (member, victim))
        before = vars(_held(world, watcher)).copy()
        _fights(world, member, victim)
        after = vars(_held(world, watcher))
        self.assertEqual(after["loyalty"], before["loyalty"])
        self.assertGreater(after["fear"], before["fear"])
        self.assertLess(world.government.measures["legitimacy"], 100.0)

    def test_each_measure_moves_by_itself_from_day_to_day(self) -> None:
        for resident_id in self.world.residents:
            profile = _held(self.world, resident_id)
            profile.resentment, profile.fear, profile.loyalty, profile.trust = 80.0, 60.0, 10.0, 20.0
        self.measures.update({"corruption": 40.0, "legitimacy": 90.0, "unrest": 0.0, "stability": 50.0})
        _midnight(self.world)
        self.assertGreater(self.measures["unrest"], 15)
        self.assertLess(self.measures["unrest"], 80, "it comes to it a day at a time")
        self.assertLess(self.measures["public_support"], 25)
        self.assertGreater(self.measures["fear"], 50)
        self.assertEqual(self.measures["legitimacy"], 90.0, "legitimate, and with nobody behind it")
        self.assertLess(self.measures["corruption"], 40.0)
        self.assertLess(_held(self.world, "lucia").fear, 60.0, "fear fades")
        self.assertLess(_held(self.world, "lucia").resentment, 80.0)
        unrest = self.measures["unrest"]
        _midnight(self.world, 20)
        self.assertGreater(self.measures["unrest"], unrest)
        self.assertLess(self.measures["stability"], 50.0)
        self.assertEqual(set(self.measures), set(MEASURES))
        self.assertTrue(all(0 <= value <= 100 for value in self.measures.values()))

    def test_loyalty_comes_back_towards_what_is_felt_for_whoever_leads(self) -> None:
        legitimacy = self.world.politics.legitimacy
        lucia, marta = self.world.residents["lucia"], self.world.residents["marta"]
        feelings = self.world.relationship("lucia", "marta")
        feelings.affection, feelings.trust = 80.0, 60.0
        ground = legitimacy.ground(self.world, lucia, marta)
        self.assertGreater(ground, 70)
        _held(self.world, "lucia").loyalty = 10.0
        _midnight(self.world)
        once = _held(self.world, "lucia").loyalty
        self.assertTrue(10.0 < once < ground)
        _midnight(self.world, 120)
        self.assertAlmostEqual(_held(self.world, "lucia").loyalty, ground, delta=1.0)
        marta.personality.charisma = 0.0
        self.assertLess(legitimacy.ground(self.world, lucia, marta), ground)

    def test_people_do_better_under_a_good_leader_and_the_more_so_the_more_loyal(self) -> None:
        politics, marta, lucia = self.world.politics, self.world.residents["marta"], self.world.residents["lucia"]
        _held(self.world, "lucia").loyalty, _held(self.world, "ines").loyalty = 100.0, 20.0
        marta.personality.leadership = 100.0
        pace = self.world.registries.politics.leadership_pace
        self.assertAlmostEqual(politics.work_pace(self.world, lucia), 1.0 + pace)
        self.assertTrue(1.0 < politics.work_pace(self.world, self.world.residents["ines"]) < 1.0 + pace)
        self.assertEqual(politics.work_pace(self.world, marta), 1.0)
        marta.personality.leadership = 0.0
        self.assertAlmostEqual(politics.work_pace(self.world, lucia), 1.0 - pace)
        marta.expedition = Expedition(10**9, 0, 0.0)
        self.assertEqual(politics.work_pace(self.world, lucia), 1.0, "nobody is led by someone who is not there")
        self.assertEqual(SimulationWorld.demo_world().politics.work_pace(self.world, lucia), 1.0)
        commune = _governed("commune")
        self.assertEqual(commune.politics.work_pace(commune, commune.residents["lucia"]), 1.0)


class ResigningTests(unittest.TestCase):
    def setUp(self) -> None:
        self.world = _governed("strong_mayor")
        self.marta = self.world.residents["marta"]

    def _asked(self):
        return next((d for d in self.world.decisions.values() if d.kind == RESIGN), None)

    def test_a_leader_who_is_getting_on_well_does_not_think_of_it(self) -> None:
        _midnight(self.world)
        self.assertIsNone(self._asked())

    def test_a_worn_leader_thinks_of_stepping_down_and_the_player_has_a_say(self) -> None:
        self.marta.needs.stress = 95.0
        _midnight(self.world)
        decision = self._asked()
        self.assertEqual(decision.resident_id, "marta")
        self.assertIn("resign_stirring", _types(self.world))
        self.assertEqual(self.world.government.leader, "marta", "nothing happens until she makes up her mind")
        outcome = self.world.apply_command(ChooseOptionCommand(decision.decision_id, "encourage"))
        self.assertEqual(outcome, "resign")
        self.assertIsNone(self.world.government.leader)
        self.assertEqual(self.marta.roles, [])
        self.assertIn("leader_resigned", _types(self.world))

    def test_told_to_hold_on_with_people_behind_her_she_stays(self) -> None:
        self.marta.needs.stress = 86.0
        for resident_id in self.world.residents:
            profile = _held(self.world, resident_id)
            profile.loyalty, profile.trust = 90.0, 90.0
            self.world.relationship(resident_id, "marta").affection = 90.0
        _midnight(self.world)
        decision = self._asked()
        self.assertEqual(self.world.apply_command(ChooseOptionCommand(decision.decision_id, "discourage")), "stay")
        self.assertEqual(self.world.government.leader, "marta")
        _midnight(self.world)
        self.assertIsNone(self._asked(), "she is not asked again so soon")

    def test_a_leader_with_nobody_behind_them_thinks_of_it_too(self) -> None:
        for resident_id in self.world.residents:
            profile = _held(self.world, resident_id)
            profile.loyalty, profile.trust = 5.0, 10.0
            self.world.relationship(resident_id, "marta").resentment = 80.0
        _midnight(self.world)
        self.assertEqual(self._asked().resident_id, "marta")


class PoliticsSaveTests(unittest.TestCase):
    def test_the_government_and_what_everyone_holds_survive_saving(self) -> None:
        manager = SaveManager()
        world = _governed("personalist_rule")
        _gathered(world)
        _fights(world, world.government.leader, "paco")
        world.government.heir = "vera"
        world.politics.leadership.resign(world, world.residents[world.government.leader])
        council = _governed("council")
        for each in (world, council):
            loaded = manager.from_data(json.loads(json.dumps(manager.to_data(each))))
            self.assertEqual(manager.to_data(loaded), manager.to_data(each))
            self.assertEqual(vars(loaded.government), vars(each.government))
            self.assertEqual(loaded.political_profiles, each.political_profiles)
            self.assertEqual(
                {r.resident_id: r.roles for r in loaded.residents.values()},
                {r.resident_id: r.roles for r in each.residents.values()},
            )
        self.assertEqual(loaded.residents[council.government.council[0]].roles, ["councillor"])
        seated = next(event for event in loaded.history if event.event_type == "council_seated")
        self.assertIsInstance(seated, PoliticalEvent)
        self.assertEqual(seated.government, "council")
        plain = next(event for event in manager.from_data(manager.to_data(world)).history if event.event_type == "fight_started")
        self.assertNotIsInstance(plain, PoliticalEvent)

    def test_a_choice_being_made_survives_saving_with_what_was_proposed(self) -> None:
        manager = SaveManager()
        world = _settled()
        world.politics.leadership.open_choosing(world)
        world.apply_command(ProposeGovernmentCommand("council"))
        loaded = manager.from_data(json.loads(json.dumps(manager.to_data(world))))
        self.assertEqual((loaded.government.proposed, loaded.government.choosing_until), ("council", world.government.choosing_until))
        loaded.step(60 * 12 + 1)
        world.step(60 * 12 + 1)
        self.assertEqual(loaded.government.kind, world.government.kind)

    def test_a_save_from_before_has_everyone_in_the_middle_and_no_government_until_it_chooses_one(self) -> None:
        manager = SaveManager()
        world = _governed("strong_mayor")
        data = json.loads(json.dumps(manager.to_data(world)))
        data["version"] = 29
        del data["government"], data["political_profiles"]
        for resident in data["residents"]:
            del resident["roles"], resident["personality"]["charisma"], resident["personality"]["leadership"]
        old = _politics(manager.from_data(data), choosing_hours=1)
        for resident in old.residents.values():
            self.assertEqual((resident.personality.charisma, resident.personality.leadership), (50.0, 50.0))
            self.assertEqual(resident.roles, [])
        self.assertIsNone(old.government.kind)
        self.assertEqual(old.political_profiles, {})
        old.step(62)
        self.assertIn(old.government.kind, KINDS)
        self.assertEqual(manager.to_data(old)["version"], manager.CURRENT_VERSION)


if __name__ == "__main__":
    unittest.main()
