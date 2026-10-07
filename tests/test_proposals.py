import json
import subprocess
import sys
import unittest
from dataclasses import replace
from pathlib import Path

from save.save_manager import SaveManager
from simulation.commands import (
    BackCandidateCommand,
    ChooseOptionCommand,
    LobbyCommand,
    ProposeBarterCommand,
    ProposeCommand,
)
from simulation.events.event import DomainEvent
from simulation.politics.election import RIG
from simulation.politics.government import EVERYONE, OPEN, SECRET
from simulation.politics.influence import CONTRARY, IGNORED, SOFTENED, TAKEN
from simulation.politics.proposal import (
    ADOPT_CURRENCY,
    CALL_ELECTION,
    CHANGE_GOVERNMENT,
    ENACT_LAW,
    EXPEL,
    KINDS,
    REASONS,
    REPEAL_LAW,
    RETURN_TO_BARTER,
    proposal_settings_from_data,
)
from simulation.politics.records import (
    ABSTAIN,
    ACCEPTED,
    CHANGED,
    NO,
    PLAYER,
    REJECTED,
    VETOED,
    YES,
    Proposal,
)
from simulation.residents.activity import Activity
from simulation.residents.needs import Needs
from simulation.world import SimulationWorld

ROOT = Path(__file__).resolve().parent.parent


def _politics(world: SimulationWorld, **changes) -> SimulationWorld:
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


def _assembly(leader: bool = True, ballot: str = OPEN, veto: bool = False, seed: int = 7) -> SimulationWorld:
    """A settlement led by a mayor where everybody proposes and everybody decides: a kind of
    government made for the test, to see what whoever leads does to a vote of all."""
    world = _settled(seed)
    mayor = world.registries.politics.governments["strong_mayor"]
    made = replace(mayor, proposes=EVERYONE, approves=EVERYONE, votes=EVERYONE, ballot=ballot, veto=veto)
    _politics(world, election_hours=1, governments={**world.registries.politics.governments, "strong_mayor": made})
    world.politics.leadership.establish(world, "strong_mayor")
    if not leader:
        world.politics.leadership.resign(world, world.residents[world.government.leader])
        world.government.election_at = None
    return world


def _types(world: SimulationWorld) -> list[str]:
    return [line.split(" | ")[1] for line in world.event_log]


def _held(world: SimulationWorld, resident_id: str):
    return world.politics.legitimacy.profile(world, world.residents[resident_id])


def _waiting(world: SimulationWorld) -> Proposal:
    return next(iter(world.government.proposals.values()))


def _ballots(world: SimulationWorld, proposal: Proposal) -> dict[str, str]:
    return {each.voter: each.vote for each in world.politics.voting.count(world, proposal)}


def _reasons(world: SimulationWorld, proposal: Proposal, voter: str) -> list[str]:
    return world.politics.voting.ballot(world, world.residents[voter], proposal).reasons


def _decide(world: SimulationWorld) -> Proposal:
    """Have what is waiting decided now, and return it."""
    proposal = _waiting(world)
    world.politics.voting.decide(world, proposal)
    return proposal


def _gathered(world: SimulationWorld) -> None:
    """Stand everybody together in the open, awake, where each sees the rest."""
    for index, resident in enumerate(world.residents.values()):
        resident.x, resident.y = 39 + index % 3, 11 + index // 3
        resident.activity = Activity("wander", minutes_left=600, using=True)


def _memories(world: SimulationWorld, resident_id: str) -> list[str]:
    return [memory.text for memory in world.memories.of(resident_id)]


def _steals(world: SimulationWorld, thief: str, victim: str) -> None:
    """Have it seen by whoever is about that one resident takes what is another's."""
    one, other = world.residents[thief], world.residents[victim]
    world.emit_event(
        DomainEvent("theft_committed", 60, f"{one.name} le quita algo a {other.name}", [thief]),
        at=one.tile,
        fact_text=f"{one.name} le robó a {other.name}",
        subjects=[thief, victim],
    )


class ProposalDataTests(unittest.TestCase):
    def test_what_can_be_proposed_is_data(self) -> None:
        settings = SimulationWorld.demo_world().registries.proposals
        self.assertEqual(set(settings.kinds), set(KINDS))
        self.assertGreater(settings.kinds[EXPEL].debate_hours, settings.debate_hours, "throwing somebody out is talked over longer")
        self.assertLess(settings.target["affection"], 0, "whoever is fond of somebody is against throwing them out")

    def test_a_kind_that_makes_no_sense_is_refused(self) -> None:
        sound = {"name": "una expulsión", "text": "echar a {target}"}
        proposal_settings_from_data({"kinds": {"expel": sound}})
        for wrong in (
            {"kinds": {"coronation": sound}},
            {"kinds": {"expel": {"name": "sin texto"}}},
            {"kinds": {"expel": {**sound, "opinion": {"luck": 1}}}},
            {"kinds": {"expel": {**sound, "motive": {"moon_phase": 1}}}},
            {"kinds": {"expel": {**sound, "debate_hours": -1}}},
            {"target": {"hunger": 1}},
            {"margin": -1},
            {"influence": {"resistance_fade": 2}},
        ):
            with self.assertRaises(ValueError, msg=wrong):
                proposal_settings_from_data(wrong)

    def test_proposals_and_votes_need_no_pygame(self) -> None:
        check = (
            "import sys; import simulation.world, save.save_manager; "
            "import simulation.politics.voting, simulation.politics.election, simulation.politics.exile; "
            "import simulation.politics.influence, simulation.politics.law_system, simulation.politics.opinion; "
            "from simulation.world import SimulationWorld; world = SimulationWorld.demo_world(); world.step(900); "
            "world.propose('enact_law', law='rest_day'); world.step(900); "
            "sys.exit(1 if 'pygame' in sys.modules else 0)"
        )
        done = subprocess.run([sys.executable, "-c", check], cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(done.returncode, 0, done.stderr)


class WhoDecidesTests(unittest.TestCase):
    def test_nothing_is_proposed_where_there_is_no_government(self) -> None:
        world = _settled()
        result = world.apply_command(ProposeCommand(ENACT_LAW, law="rest_day"))
        self.assertFalse(result.ok)
        self.assertEqual(world.government.proposals, {})

    def test_each_government_says_who_proposes_and_who_decides(self) -> None:
        voting = SimulationWorld.demo_world().politics.voting
        mayor = _governed("strong_mayor")
        self.assertEqual([each.resident_id for each in voting.deciders(mayor)], [mayor.government.leader])
        self.assertEqual([each.resident_id for each in voting.proposers(mayor)], [mayor.government.leader])
        council = _governed("council")
        self.assertEqual({each.resident_id for each in voting.deciders(council)}, set(council.government.council))
        assembly = _governed("direct_democracy")
        self.assertEqual(len(voting.deciders(assembly)), 9)
        self.assertTrue(all(voting.may_propose(assembly, resident) for resident in assembly.residents.values()))

    def test_a_seat_that_stands_empty_leaves_the_say_to_everybody(self) -> None:
        world = _governed("strong_mayor")
        world.politics.leadership.resign(world, world.residents[world.government.leader])
        self.assertEqual(len(world.politics.voting.deciders(world)), 9)

    def test_whoever_is_away_has_no_say(self) -> None:
        from simulation.work.expedition import Expedition

        world = _governed("direct_democracy")
        world.residents["sergio"].expedition = Expedition(returns_at=10**9, finds=0, danger=0.0)
        self.assertNotIn("sergio", [each.resident_id for each in world.politics.voting.deciders(world)])

    def test_under_a_mayor_the_mayor_makes_it_theirs_and_decides_alone_and_sooner(self) -> None:
        world = _governed("strong_mayor")
        leader = world.government.leader
        result = world.apply_command(ProposeCommand(ENACT_LAW, law="rest_day"))
        self.assertTrue(result.ok, result.message)
        proposal = world.government.proposals[result.detail]
        self.assertEqual((proposal.by, proposal.sponsor), (PLAYER, leader))
        settings = world.registries.proposals
        self.assertEqual(proposal.decides_at - proposal.raised_at, settings.leader_hours * 60)
        self.assertNotIn("rest_day", world.government.laws, "nothing is done until it is decided")
        world.step(settings.leader_hours * 60 + 1)
        self.assertEqual(world.government.proposals, {})
        self.assertIn("rest_day", world.government.laws)
        self.assertEqual(world.government.decided[-1].status, ACCEPTED)
        self.assertEqual([each.voter for each in world.government.decided[-1].ballots], [leader])
        self.assertNotIn("vote_held", _types(world), "one person making up their mind is no vote")

    def test_throwing_somebody_out_is_given_its_day_even_when_one_person_decides(self) -> None:
        world = _governed("strong_mayor")
        leader = world.government.leader
        target = next(resident_id for resident_id in world.residents if resident_id != leader)
        world.relationship(leader, target).resentment = 100.0
        _held(world, leader).revengefulness = 100.0
        world.residents[leader].personality.empathy = 0.0
        result = world.apply_command(ProposeCommand(EXPEL, target=target))
        self.assertTrue(result.ok, result.message)
        proposal = world.government.proposals[result.detail]
        settings = world.registries.proposals
        self.assertEqual(proposal.decides_at - proposal.raised_at, settings.kinds[EXPEL].debate_hours * 60)
        self.assertGreater(settings.kinds[EXPEL].debate_hours, settings.leader_hours)
        world.step(settings.leader_hours * 60 + 1)
        self.assertIn(target, world.residents)
        self.assertNotIn(target, world.leaving, "there is still time to speak to whoever decides")
        self.assertEqual(world.lobby(proposal.proposal_id, leader, "against").detail != "", True)

    def test_what_nobody_who_may_propose_wants_goes_no_further(self) -> None:
        world = _governed("strong_mayor")
        result = world.apply_command(ProposeCommand(ENACT_LAW, law="salute"))
        self.assertFalse(result.ok)
        self.assertEqual(world.government.proposals, {})
        self.assertIn("proposal_dropped", _types(world))
        again = world.apply_command(ProposeCommand(ENACT_LAW, law="salute"))
        self.assertFalse(again.ok, "and it is not to be put again the same day")
        self.assertEqual(_types(world).count("proposal_dropped"), 1)

    def test_what_makes_no_sense_cannot_be_put(self) -> None:
        world = _governed("direct_democracy")
        for command in (
            ProposeCommand(ENACT_LAW, law="no_such_law"),
            ProposeCommand(ENACT_LAW, law="curfew", degree=9),
            ProposeCommand(REPEAL_LAW, law="curfew"),
            ProposeCommand(EXPEL, target="nobody"),
            ProposeCommand(CHANGE_GOVERNMENT, government="direct_democracy"),
            ProposeCommand(CHANGE_GOVERNMENT, government="monarchy"),
            ProposeCommand(CALL_ELECTION),
            ProposeCommand(ENACT_LAW, law="banned_food"),
            ProposeCommand(ENACT_LAW, law="banned_food", params={"item": "scrap"}),
            ProposeCommand(ENACT_LAW, law="salute"),
            ProposeCommand(ADOPT_CURRENCY, params={"name": "chapas"}),
            ProposeCommand("coronation"),
        ):
            self.assertFalse(world.apply_command(command).ok, command)
        self.assertEqual(world.government.proposals, {})
        self.assertNotIn("proposal_raised", _types(world))


class VoteTests(unittest.TestCase):
    def test_the_same_proposal_is_voted_for_by_one_and_against_by_another_each_for_what_they_are(self) -> None:
        world = _governed("direct_democracy")
        _held(world, "lucia").collectivism, _held(world, "lucia").justice_sensitivity = 90.0, 80.0
        _held(world, "tomas").collectivism, _held(world, "tomas").individualism = 10.0, 90.0
        world.residents["tomas"].personality.greed = 85.0
        self.assertTrue(world.propose(ENACT_LAW, law="rationing").ok)
        proposal = _waiting(world)
        votes = _ballots(world, proposal)
        self.assertEqual((votes["lucia"], votes["tomas"]), (YES, NO))
        self.assertEqual(_reasons(world, proposal, "lucia")[0], "conviction")
        self.assertEqual(_reasons(world, proposal, "tomas")[0], "conviction")
        # It is who they are that does it: with Tomás's mind on what is everybody's, he is for it.
        _held(world, "tomas").collectivism, _held(world, "tomas").individualism = 90.0, 10.0
        world.residents["tomas"].personality.greed = 15.0
        self.assertEqual(_ballots(world, proposal)["tomas"], YES)

    def test_how_hungry_somebody_is_weighs_on_rationing(self) -> None:
        world = _governed("direct_democracy")
        self.assertTrue(world.propose(ENACT_LAW, law="rationing").ok)
        proposal = _waiting(world)
        voting = world.politics.voting
        before = voting.mind(world, world.residents["paco"], proposal)[0]
        world.residents["paco"].needs.hunger = 90.0
        self.assertLess(voting.mind(world, world.residents["paco"], proposal)[0], before)

    def test_a_vote_is_never_a_roll(self) -> None:
        world = _governed("direct_democracy")
        self.assertTrue(world.propose(ENACT_LAW, law="curfew").ok)
        proposal = _waiting(world)
        first = [(each.voter, each.vote, each.score) for each in world.politics.voting.count(world, proposal)]
        state = world.rng.get_state()
        for _ in range(5):
            again = [(each.voter, each.vote, each.score) for each in world.politics.voting.count(world, proposal)]
            self.assertEqual(again, first)
        self.assertEqual(world.rng.get_state(), state, "and it draws on no randomness at all")

    def test_whoever_cares_little_for_politics_keeps_out_of_what_is_near_the_middle(self) -> None:
        world = _governed("direct_democracy")
        self.assertTrue(world.propose(ENACT_LAW, law="curfew").ok)
        proposal = _waiting(world)
        voting = world.politics.voting
        nuria = world.residents["nuria"]
        score = voting.mind(world, nuria, proposal)[0]
        self.assertLess(score, 0)
        _held(world, "nuria").political_interest = 100.0
        self.assertEqual(voting.ballot(world, nuria, proposal).vote, NO)
        _held(world, "nuria").political_interest = 0.0
        self.assertEqual(voting.ballot(world, nuria, proposal).vote, ABSTAIN)

    def test_somebody_votes_down_what_would_do_them_good_because_they_hate_whoever_leads(self) -> None:
        world = _assembly()
        leader = world.government.leader
        self.assertTrue(world.propose(ENACT_LAW, law="rest_day").ok)
        proposal = _waiting(world)
        voting = world.politics.voting
        self.assertEqual(voting.stance(world, world.residents[leader], proposal), 1, "whoever leads is for it")
        raul = world.residents["raul"]
        self.assertGreater(voting.conviction(world, raul, proposal), 0, "and it would do Raúl good")
        self.assertEqual(voting.ballot(world, raul, proposal).vote, YES)
        _held(world, "raul").resentment, _held(world, "raul").loyalty = 100.0, 0.0
        world.registries = replace(
            world.registries,
            proposals=replace(world.registries.proposals, weights={**world.registries.proposals.weights, "grudge": 2.0}),
        )
        ballot = voting.ballot(world, raul, proposal)
        self.assertEqual(ballot.vote, NO)
        self.assertEqual(ballot.reasons[0], "grudge")
        self.assertIn("grudge", REASONS)

    def test_loyalty_carries_somebody_along_with_whoever_leads(self) -> None:
        world = _assembly()
        self.assertTrue(world.propose(ENACT_LAW, law="rest_day").ok)
        proposal = _waiting(world)
        voting = world.politics.voting
        ines = world.residents["ines"]
        _held(world, "ines").loyalty = 35.0
        plain = voting.mind(world, ines, proposal)[0]
        _held(world, "ines").loyalty = 100.0
        self.assertGreater(voting.mind(world, ines, proposal)[0], plain)
        self.assertIn("loyalty", voting.mind(world, ines, proposal)[1])

    def test_fear_bends_a_show_of_hands_and_not_a_vote_cast_in_secret(self) -> None:
        for ballot, bends in ((OPEN, True), (SECRET, False)):
            world = _assembly(ballot=ballot)
            self.assertTrue(world.propose(ENACT_LAW, law="rest_day").ok)
            proposal = _waiting(world)
            self.assertEqual(proposal.open_ballot, ballot == OPEN)
            voting = world.politics.voting
            paco = world.residents["paco"]
            calm = voting.mind(world, paco, proposal)[0]
            _held(world, "paco").fear, _held(world, "paco").fearfulness = 90.0, 90.0
            parts = voting.mind(world, paco, proposal)[1]
            self.assertEqual("fear" in parts, bends, ballot)
            self.assertEqual(voting.mind(world, paco, proposal)[0] > calm, bends, ballot)

    def test_what_is_felt_for_whoever_put_it_weighs_on_it(self) -> None:
        world = _governed("direct_democracy")
        world.politics.voting.raise_as(world, world.residents["vera"], ENACT_LAW, law="curfew")
        proposal = _waiting(world)
        voting = world.politics.voting
        paco = world.residents["paco"]
        plain = voting.mind(world, paco, proposal)[0]
        world.relationship("paco", "vera").affection, world.relationship("paco", "vera").trust = 80.0, 80.0
        fond = voting.mind(world, paco, proposal)[0]
        world.relationship("paco", "vera").affection, world.relationship("paco", "vera").trust = -60.0, -60.0
        world.relationship("paco", "vera").resentment = 80.0
        sour = voting.mind(world, paco, proposal)[0]
        self.assertGreater(fond, plain)
        self.assertLess(sour, plain)
        self.assertEqual(voting.ballot(world, paco, proposal).reasons[0], "proposer")

    def test_what_is_remembered_of_politics_weighs_on_later_votes(self) -> None:
        from simulation.memory.memory import Memory

        world = _governed("direct_democracy")
        world.politics.voting.raise_as(world, world.residents["vera"], ENACT_LAW, law="curfew")
        proposal = _waiting(world)
        voting = world.politics.voting
        paco = world.residents["paco"]
        plain = voting.mind(world, paco, proposal)[0]
        world.memories.remember("paco", Memory("Vera votó por echar a mi amigo.", 90.0, -1.0, ["vera"], ["politics"], 0))
        mind, parts = voting.mind(world, paco, proposal)
        self.assertLess(mind, plain)
        self.assertLess(parts["memory"], 0)
        # What has nothing to do with politics, or with her, is no part of it.
        other = _governed("direct_democracy")
        other.politics.voting.raise_as(other, other.residents["vera"], ENACT_LAW, law="curfew")
        other.memories.remember("paco", Memory("Charlé un rato con Vera.", 90.0, -1.0, ["vera"], ["talk"], 0))
        self.assertEqual(other.politics.voting.mind(other, other.residents["paco"], _waiting(other))[0], plain)

    def test_it_takes_the_share_the_government_asks_for(self) -> None:
        world = _governed("commune")
        self.assertEqual(world.politics.leadership.definition(world).approval, 0.75)
        voting = world.politics.voting
        from simulation.politics.records import Ballot

        def carried(yes: int, no: int, abstain: int = 0) -> bool:
            names = list(world.residents)
            ballots = [Ballot(names[index], YES) for index in range(yes)]
            ballots += [Ballot(names[yes + index], NO) for index in range(no)]
            ballots += [Ballot(names[yes + no + index], ABSTAIN) for index in range(abstain)]
            return voting.passes(world, ballots)

        self.assertTrue(carried(6, 2, 1), "three in four of those who said yes or no")
        self.assertFalse(carried(5, 2, 2))
        self.assertFalse(carried(0, 0, 9), "with nobody for it, nothing carries")
        assembly = _governed("direct_democracy")
        self.assertTrue(assembly.politics.voting.passes(assembly, [Ballot("marta", YES), Ballot("raul", ABSTAIN)]))
        self.assertFalse(assembly.politics.voting.passes(assembly, [Ballot("marta", YES), Ballot("raul", NO)]))


class DecidingTests(unittest.TestCase):
    def test_a_proposal_of_the_players_that_is_turned_down_does_nothing(self) -> None:
        world = _governed("direct_democracy")
        result = world.apply_command(ProposeCommand(ENACT_LAW, law="curfew"))
        self.assertTrue(result.ok, result.message)
        proposal = world.government.proposals[result.detail]
        sponsor = proposal.sponsor
        self.assertIn(sponsor, world.residents, "somebody made it theirs")
        world.step(world.registries.proposals.debate_hours * 60 + 1)
        self.assertEqual(proposal.status, REJECTED)
        self.assertEqual(world.government.laws, {}, "and nothing of it happens")
        self.assertEqual(world.government.proposals, {})
        types = _types(world)
        self.assertIn("vote_held", types)
        self.assertIn("proposal_rejected", types)
        self.assertNotIn("law_enacted", types)
        self.assertEqual(world.government.measures["authoritarianism"], 10.0)
        again = world.apply_command(ProposeCommand(ENACT_LAW, law="curfew"))
        self.assertFalse(again.ok, "what was just turned down is left alone for a while")
        world.clock.day += world.registries.proposals.again_days
        self.assertTrue(world.apply_command(ProposeCommand(ENACT_LAW, law="curfew")).ok)

    def test_what_is_put_waits_to_be_talked_over(self) -> None:
        world = _governed("direct_democracy")
        self.assertTrue(world.propose(ENACT_LAW, law="rest_day").ok)
        hours = world.registries.proposals.debate_hours
        world.step(hours * 60 - 1)
        self.assertEqual(len(world.government.proposals), 1)
        self.assertEqual(world.government.laws, {})
        world.step(2)
        self.assertIn("rest_day", world.government.laws)
        self.assertGreater(world.registries.proposals.kinds[EXPEL].debate_hours, hours)

    def test_the_same_thing_is_not_put_twice_and_only_so_much_waits_at_once(self) -> None:
        world = _governed("direct_democracy")
        self.assertTrue(world.propose(ENACT_LAW, law="rest_day").ok)
        self.assertFalse(world.propose(ENACT_LAW, law="rest_day").ok)
        world.registries = replace(world.registries, proposals=replace(world.registries.proposals, pending_limit=1))
        self.assertFalse(world.propose(ENACT_LAW, law="pregnancy_rest").ok)

    def test_a_law_that_does_not_carry_as_it_was_put_passes_milder(self) -> None:
        world = _governed("direct_democracy")
        voting = world.politics.voting
        # Everybody holds with sharing out what there is, and everybody is starving.
        for resident_id, resident in world.residents.items():
            profile = _held(world, resident_id)
            profile.collectivism, profile.justice_sensitivity, profile.individualism = 100.0, 100.0, 0.0
            profile.political_interest = 80.0
            resident.personality.greed = 50.0
            resident.needs.hunger = 100.0
        self.assertTrue(voting.raise_as(world, world.residents["vera"], ENACT_LAW, law="rationing", degree=2).ok)
        proposal = _waiting(world)
        as_put = voting.passes(world, voting.count(world, proposal, 2))
        mildest = voting.passes(world, voting.count(world, proposal, 0))
        self.assertFalse(as_put)
        self.assertTrue(mildest, "the fewer it weighs on, the fewer are against it")
        _decide(world)
        self.assertEqual(proposal.status, CHANGED)
        held = world.government.laws["rationing"]
        self.assertLess(held.degree, 2)
        self.assertEqual(proposal.passed_degree, held.degree)
        self.assertIn("proposal_changed", _types(world))

    def test_whoever_leads_and_has_a_veto_refuses_what_the_rest_approved(self) -> None:
        world = _assembly(veto=True)
        leader = world.residents[world.government.leader]
        legitimacy = world.government.measures["legitimacy"]
        self.assertTrue(world.propose(ENACT_LAW, law="rest_day").ok)
        proposal = _waiting(world)
        self.assertTrue(world.politics.voting.passes(world, world.politics.voting.count(world, proposal)))
        # Whoever leads would not have anybody rest.
        leader.personality.greed = 100.0
        _held(world, leader.resident_id).collectivism = 0.0
        world.registries = replace(
            world.registries,
            laws=replace(
                world.registries.laws,
                laws={
                    **world.registries.laws.laws,
                    "rest_day": replace(world.registries.laws.laws["rest_day"], opinion={"leads": -2.0, "works": 0.5}),
                },
            ),
        )
        self.assertEqual(world.politics.voting.stance(world, leader, proposal), -1)
        _decide(world)
        self.assertEqual(proposal.status, VETOED)
        self.assertEqual(world.government.laws, {})
        self.assertIn("proposal_vetoed", _types(world))
        self.assertLess(world.government.measures["legitimacy"], legitimacy)
        without = _assembly(veto=False)
        self.assertTrue(without.propose(ENACT_LAW, law="rest_day").ok)
        self.assertEqual(_decide(without).status, ACCEPTED)

    def test_a_law_in_force_can_be_done_away_with_the_same_way(self) -> None:
        world = _governed("direct_democracy")
        world.politics.laws.enact(world, "tax", 2)
        before = world.government.measures["authoritarianism"]
        self.assertTrue(world.propose(REPEAL_LAW, law="tax").ok)
        proposal = _decide(world)
        self.assertEqual(proposal.status, ACCEPTED)
        self.assertEqual(world.government.laws, {})
        self.assertIn("law_repealed", _types(world))
        self.assertLess(world.government.measures["authoritarianism"], before)

    def test_another_kind_of_government_is_put_and_decided(self) -> None:
        world = _governed("direct_democracy")
        for resident_id in world.residents:
            _held(world, resident_id).collectivism = 95.0
            _held(world, resident_id).individualism = 5.0
            _held(world, resident_id).authoritarian_tolerance = 20.0
        self.assertTrue(world.propose(CHANGE_GOVERNMENT, government="commune").ok)
        proposal = _waiting(world)
        self.assertEqual(_reasons(world, proposal, "paco")[0], "conviction")
        _decide(world)
        self.assertEqual(proposal.status, ACCEPTED)
        self.assertEqual(world.government.kind, "commune")
        self.assertIn("government_changed", _types(world))
        self.assertGreater(world.government.measures["legitimacy"], 50.0, "as legitimate as how many were for it")

    def test_how_the_settlement_trades_is_decided_by_whoever_governs(self) -> None:
        world = _governed("strong_mayor")
        leader = world.residents[world.government.leader]
        self.assertTrue(world.trading.in_use)
        result = world.apply_command(ProposeBarterCommand())
        self.assertFalse(result.ok, "whoever leads is not for it")
        self.assertTrue(world.trading.in_use)
        _held(world, leader.resident_id).collectivism = 100.0
        leader.credits = 0.0
        leader.personality.greed = 0.0
        world.clock.day += world.registries.proposals.again_days
        result = world.apply_command(ProposeBarterCommand())
        self.assertTrue(result.ok, result.message)
        self.assertTrue(world.trading.in_use, "it waits to be decided like anything else")
        self.assertEqual(_waiting(world).kind, RETURN_TO_BARTER)
        _decide(world)
        self.assertFalse(world.trading.in_use, "and it is the mayor's say, whatever the rest would have")
        self.assertIn("trade_terms_changed", _types(world))

    def test_with_no_government_everybody_still_answers_for_themselves(self) -> None:
        world = _settled()
        self.assertIsNone(world.government.kind)
        world.apply_command(ProposeBarterCommand())
        self.assertEqual(world.government.proposals, {})
        self.assertTrue({"trade_terms_changed", "trade_terms_kept"} & set(_types(world)))


class MemoryTests(unittest.TestCase):
    def test_those_who_took_part_remember_how_they_voted(self) -> None:
        world = _governed("direct_democracy")
        self.assertTrue(world.propose(ENACT_LAW, law="rest_day").ok)
        proposal = _decide(world)
        for ballot in proposal.ballots:
            said = "a favor de" if ballot.vote == YES else "en contra de"
            remembered = [memory for memory in world.memories.of(ballot.voter) if "vote" in memory.tags]
            if ballot.vote == ABSTAIN:
                self.assertEqual(remembered, [])
                continue
            self.assertEqual(len(remembered), 1, ballot.voter)
            self.assertIn(f"Voté {said}", remembered[0].text)
            self.assertIn("politics", remembered[0].tags)
            self.assertIn("player", remembered[0].tags, "and that it came from outside")
        self.assertTrue(any("Hice mía una propuesta" in text for text in _memories(world, proposal.sponsor)))

    def test_whoever_put_it_remembers_how_it_went_and_who_was_against(self) -> None:
        world = _governed("direct_democracy")
        vera = world.residents["vera"]
        self.assertTrue(world.politics.voting.raise_as(world, vera, ENACT_LAW, law="curfew").ok)
        self.assertIn("Propuse", " ".join(_memories(world, "vera")))
        resentment = _held(world, "vera").resentment
        proposal = _decide(world)
        self.assertEqual(proposal.status, REJECTED)
        lost = next(memory for memory in world.memories.of("vera") if "No salió adelante" in memory.text)
        against = {ballot.voter for ballot in proposal.ballots if ballot.vote == NO}
        self.assertEqual(set(lost.people), against, "after a show of hands she knows who")
        self.assertGreater(_held(world, "vera").resentment, resentment)

    def test_a_vote_cast_in_secret_leaves_nobody_knowing_who_voted_how(self) -> None:
        world = _governed("council")
        self.assertEqual(world.politics.leadership.definition(world).ballot, SECRET)
        member = world.residents[world.government.council[0]]
        for other in world.government.council[1:]:
            # The rest of the council like their evenings at the bar, and being told nothing.
            _held(world, other).authoritarian_tolerance = 0.0
            world.residents[other].personality.sociability = 100.0
        self.assertTrue(world.politics.voting.raise_as(world, member, ENACT_LAW, law="dry_law").ok)
        proposal = _decide(world)
        self.assertEqual(proposal.status, REJECTED)
        lost = next(memory for memory in world.memories.of(member.resident_id) if "No salió adelante" in memory.text)
        self.assertEqual(lost.people, [])
        held = next(event for event in world.history if event.event_type == "vote_held")
        self.assertEqual(held.data["ballots"], {})
        self.assertEqual(held.data["no"], len([each for each in proposal.ballots if each.vote == NO]))
        shown = _governed("direct_democracy")
        self.assertTrue(shown.propose(ENACT_LAW, law="rest_day").ok)
        _decide(shown)
        held = next(event for event in shown.history if event.event_type == "vote_held")
        self.assertEqual(len(held.data["ballots"]), 9)

    def test_whoever_was_not_there_comes_to_hear_of_it(self) -> None:
        from simulation.knowledge.knowledge_system import share_rumor
        from simulation.work.expedition import Expedition

        world = _governed("direct_democracy")
        sergio = world.residents["sergio"]
        sergio.expedition = Expedition(returns_at=10**9, finds=0, danger=0.0)
        self.assertTrue(world.propose(ENACT_LAW, law="rest_day").ok)
        _decide(world)
        fact = next(fact for fact in world.knowledge.facts.values() if fact.event_type == "proposal_accepted")
        self.assertTrue(world.knowledge.knows("vera", fact.fact_id))
        self.assertFalse(world.knowledge.knows("sergio", fact.fact_id), "nobody knows a thing because the world does")
        sergio.expedition = None
        world.residents["vera"].personality.sociability = 100.0
        for _ in range(200):
            if world.knowledge.knows("sergio", fact.fact_id):
                break
            share_rumor(world, world.residents["vera"], sergio)
        self.assertTrue(world.knowledge.knows("sergio", fact.fact_id))


class InfluenceTests(unittest.TestCase):
    def _put(self, law: str = "curfew") -> tuple[SimulationWorld, Proposal]:
        world = _governed("direct_democracy")
        self.assertTrue(world.propose(ENACT_LAW, law=law).ok)
        return world, _waiting(world)

    def test_the_player_speaks_to_whoever_decides_once_and_cannot_vote_for_them(self) -> None:
        world, proposal = self._put()
        self.assertEqual(_ballots(world, proposal)["raul"], ABSTAIN)
        result = world.apply_command(LobbyCommand(proposal.proposal_id, "raul", "for"))
        self.assertTrue(result.ok, result.message)
        self.assertEqual(result.detail, TAKEN)
        self.assertEqual(_ballots(world, proposal)["raul"], YES)
        self.assertIn("lobby", _reasons(world, proposal, "raul"))
        self.assertFalse(world.apply_command(LobbyCommand(proposal.proposal_id, "raul", "for")).ok, "once is all")
        self.assertFalse(world.apply_command(LobbyCommand(proposal.proposal_id, "nobody", "for")).ok)
        self.assertFalse(world.apply_command(LobbyCommand("proposal_99", "paco", "for")).ok)
        self.assertFalse(world.apply_command(LobbyCommand(proposal.proposal_id, "paco", "loudly")).ok)
        self.assertIn("proposal_lobbied", _types(world))

    def test_whoever_is_set_against_it_is_not_talked_round(self) -> None:
        world, proposal = self._put()
        self.assertEqual(_ballots(world, proposal)["sergio"], NO)
        result = world.apply_command(LobbyCommand(proposal.proposal_id, "sergio", "for"))
        self.assertIn(result.detail, (SOFTENED, IGNORED))
        self.assertNotEqual(_ballots(world, proposal)["sergio"], YES)

    def test_only_those_who_decide_can_be_spoken_to(self) -> None:
        world = _governed("strong_mayor")
        self.assertTrue(world.propose(ENACT_LAW, law="rest_day").ok)
        proposal = _waiting(world)
        leader = world.government.leader
        other = next(resident_id for resident_id in world.residents if resident_id != leader)
        self.assertFalse(world.lobby(proposal.proposal_id, other, "for").ok)
        self.assertNotEqual(world.lobby(proposal.proposal_id, leader, "against").detail, "")

    def test_being_pushed_against_their_own_mind_makes_somebody_resist_and_in_the_end_do_the_opposite(self) -> None:
        world, proposal = self._put()
        influence = world.politics.influence
        sergio = world.residents["sergio"]
        raul = world.residents["raul"]
        lean = influence.lean(world, sergio)
        world.lobby(proposal.proposal_id, "sergio", "for")
        world.lobby(proposal.proposal_id, "raul", "for")
        self.assertGreater(influence.standing(world, sergio).resistance, 0.0)
        self.assertEqual(influence.standing(world, raul).resistance, 0.0, "whoever had no mind against it was not pushed")
        self.assertLess(influence.lean(world, sergio), lean, "and leans on the player the less for it")
        # Pushed over and over, there comes a day they do the contrary.
        other = _governed("direct_democracy")
        self.assertTrue(other.propose(ENACT_LAW, law="curfew").ok)
        again = _waiting(other)
        stubborn = other.residents["sergio"]
        other.politics.influence.standing(other, stubborn).resistance = other.registries.proposals.defiance
        before = other.politics.voting.mind(other, stubborn, again)[0]
        result = other.lobby(again.proposal_id, "sergio", "for")
        self.assertEqual(result.detail, CONTRARY)
        self.assertFalse(result.ok)
        self.assertLess(other.politics.voting.mind(other, stubborn, again)[0], before)

    def test_resistance_wears_off_with_the_days(self) -> None:
        world = _governed("direct_democracy")
        standing = world.politics.influence.standing(world, world.residents["paco"])
        standing.resistance = 40.0
        world.clock.day += 1
        world.clock.hour, world.clock.minute = 0, 0
        world.politics.tick(world)
        self.assertLess(standing.resistance, 40.0)
        self.assertGreater(standing.resistance, 30.0)

    def test_trust_in_the_player_moves_only_with_how_it_turned_out_for_each(self) -> None:
        world, proposal = self._put("rationing")
        influence = world.politics.influence
        for resident_id in ("raul", "paco"):
            world.lobby(proposal.proposal_id, resident_id, "for")
        self.assertTrue(all(standing.trust == 50.0 for standing in world.player_standing.values()), "talking moves no trust")
        for resident_id in world.residents:
            _held(world, resident_id).collectivism = 95.0
        _held(world, "tomas").collectivism, _held(world, "tomas").individualism = 0.0, 100.0
        world.residents["tomas"].personality.greed = 100.0
        _decide(world)
        self.assertIn(proposal.status, (ACCEPTED, CHANGED))
        self.assertGreater(influence.standing(world, world.residents["lucia"]).trust, 50.0, "it suits her")
        self.assertLess(influence.standing(world, world.residents["tomas"]).trust, 50.0, "and not him")
        # What is turned down does nothing, and so nobody holds it to the player's account.
        other, lost = self._put("curfew")
        _decide(other)
        self.assertEqual(lost.status, REJECTED)
        self.assertTrue(all(standing.trust == 50.0 for standing in other.player_standing.values()))

    def test_a_proposal_of_the_players_weighs_more_with_whoever_trusts_them(self) -> None:
        world, proposal = self._put()
        voting = world.politics.voting
        paco = world.residents["paco"]
        plain = voting.mind(world, paco, proposal)[0]
        world.politics.influence.standing(world, paco).trust = 100.0
        trusting, parts = voting.mind(world, paco, proposal)
        self.assertGreater(trusting, plain)
        self.assertGreater(parts["player"], 0)
        world.politics.influence.standing(world, paco).trust = 0.0
        self.assertLess(voting.mind(world, paco, proposal)[0], plain)

    def test_what_the_player_is_to_somebody_tells_on_any_advice_they_give_them(self) -> None:
        world = _governed("strong_mayor")
        leader = world.residents[world.government.leader]
        decision = world.interventions.ask(world, leader, "resign", inputs={"support": 0.5})
        option = next(each for each in decision.options if each.option_id == "encourage")
        plain = world.interventions.scores(world, decision, option)["resign"]
        world.politics.influence.standing(world, leader).trust = 100.0
        trusted = world.interventions.scores(world, decision, option)["resign"]
        world.politics.influence.standing(world, leader).resistance = 90.0
        resisted = world.interventions.scores(world, decision, option)["resign"]
        self.assertGreater(trusted, plain)
        self.assertLess(resisted, plain)
        self.assertEqual(world.interventions.scores(world, decision, None)["resign"], world.interventions.scores(world, decision, None)["resign"])


class ResidentsProposeTests(unittest.TestCase):
    def _hour_to_stir(self, world: SimulationWorld, days: int = 1) -> None:
        """Have the hour at which people put things to the others come round, that many days running."""
        for _ in range(days):
            world.clock.day += 1
            world.clock.hour, world.clock.minute = 8, 0
            world.politics.voting.tick(world)

    def _empty_the_larder(self, world: SimulationWorld) -> None:
        resolve = world.registries.items.resolve
        for inventory in world.containers.values():
            inventory.items[:] = [item for item in inventory.items if resolve(item.definition_id).category != "food"]

    def test_with_the_larder_low_somebody_who_holds_with_it_puts_rationing_to_the_rest(self) -> None:
        world = _governed("direct_democracy")
        self._hour_to_stir(world)
        self.assertEqual(world.government.proposals, {}, "with enough to eat nobody thinks of it")
        self._empty_the_larder(world)
        self._hour_to_stir(world)
        proposal = _waiting(world)
        self.assertEqual((proposal.kind, proposal.law), (ENACT_LAW, "rationing"))
        self.assertIn(proposal.by, world.residents)
        self.assertIsNone(proposal.sponsor, "it is theirs: nobody has to make it so")
        proposer = world.residents[proposal.by]
        self.assertGreaterEqual(
            world.politics.laws.regard(world, proposer, "rationing", proposal.degree), world.registries.proposals.raise_from
        )
        self.assertIn("proposal_raised", _types(world))
        self.assertTrue(any("Propuse" in text for text in _memories(world, proposal.by)))

    def test_whoever_has_just_put_something_lets_others_have_their_turn(self) -> None:
        world = _governed("direct_democracy")
        self._empty_the_larder(world)
        self._hour_to_stir(world)
        first = _waiting(world).by
        _decide(world)
        world.government.refused.clear()
        world.government.laws.clear()
        self._hour_to_stir(world)
        if world.government.proposals:
            self.assertNotEqual(_waiting(world).by, first)

    def test_under_a_mayor_only_the_mayor_puts_anything(self) -> None:
        world = _governed("strong_mayor")
        leader = world.government.leader
        self._empty_the_larder(world)
        for resident_id in world.residents:
            _held(world, resident_id).collectivism = 100.0
            _held(world, resident_id).justice_sensitivity = 100.0
        self._hour_to_stir(world)
        self.assertEqual([proposal.by for proposal in world.government.proposals.values()], [leader])
        other = world.residents[next(resident_id for resident_id in world.residents if resident_id != leader)]
        self.assertFalse(world.politics.voting.raise_as(world, other, ENACT_LAW, law="rest_day").ok)

    def test_somebody_wronged_by_a_thief_they_resent_puts_it_that_they_be_thrown_out(self) -> None:
        world = _governed("direct_democracy")
        _gathered(world)
        voting = world.politics.voting
        self.assertEqual(voting.ideas(world, world.residents["nuria"]), [])
        world.relationship("nuria", "sergio").resentment = 90.0
        _steals(world, "sergio", "nuria")
        self.assertEqual(
            [idea for idea in voting.ideas(world, world.residents["nuria"]) if idea.kind == EXPEL], [],
            "once is not enough to want somebody gone for good",
        )
        _steals(world, "sergio", "nuria")
        _steals(world, "sergio", "paco")
        world.relationship("nuria", "sergio").resentment = 20.0
        self.assertEqual(
            [idea for idea in voting.ideas(world, world.residents["nuria"]) if idea.kind == EXPEL], [],
            "and knowing it is not enough: it takes having it in for them",
        )
        world.relationship("nuria", "sergio").resentment = 90.0
        ideas = [idea for idea in voting.ideas(world, world.residents["nuria"]) if idea.kind == EXPEL]
        self.assertEqual([idea.target for idea in ideas], ["sergio"])
        self._hour_to_stir(world)
        proposal = _waiting(world)
        self.assertEqual((proposal.kind, proposal.by, proposal.target), (EXPEL, "nuria", "sergio"))

    def test_nobody_puts_out_somebody_for_what_they_never_knew_of(self) -> None:
        world = _governed("direct_democracy")
        # The theft happens with nobody about to see it.
        for index, resident in enumerate(world.residents.values()):
            resident.x, resident.y = 5 + 6 * index, 20
        world.residents["sergio"].x, world.residents["sergio"].y = 55, 30
        _steals(world, "sergio", "nuria")
        world.relationship("nuria", "sergio").resentment = 90.0
        self.assertEqual(world.politics.voting.known_misdeeds(world, world.residents["nuria"], "sergio"), [])
        self.assertEqual([idea for idea in world.politics.voting.ideas(world, world.residents["nuria"]) if idea.kind == EXPEL], [])

    def test_a_leader_nobody_is_behind_has_a_vote_called_on_them(self) -> None:
        world = _assembly()
        leader = world.government.leader
        world.government.term_began = world.clock.day - 30
        for resident_id in world.residents:
            _held(world, resident_id).loyalty, _held(world, resident_id).trust = 5.0, 20.0
            _held(world, resident_id).resentment = 60.0
        self._hour_to_stir(world)
        proposal = _waiting(world)
        self.assertEqual(proposal.kind, CALL_ELECTION)
        self.assertNotEqual(proposal.by, leader)

    def test_whoever_cannot_stand_how_things_are_run_puts_another_way_to_the_rest(self) -> None:
        world = _governed("direct_democracy")
        world.government.chosen_on = world.clock.day - 40
        vera = world.residents["vera"]
        _held(world, "vera").trust = 10.0
        _held(world, "vera").collectivism, _held(world, "vera").individualism = 100.0, 0.0
        _held(world, "vera").authoritarian_tolerance = 0.0
        ideas = [idea for idea in world.politics.voting.ideas(world, vera) if idea.kind == CHANGE_GOVERNMENT]
        self.assertIn("commune", [idea.government for idea in ideas])
        _held(world, "vera").trust = 60.0
        self.assertEqual([idea for idea in world.politics.voting.ideas(world, vera) if idea.kind == CHANGE_GOVERNMENT], [])

    def test_a_law_somebody_cannot_abide_is_put_to_be_done_away_with(self) -> None:
        world = _governed("direct_democracy")
        world.politics.laws.enact(world, "tax", 2)
        self._hour_to_stir(world)
        proposal = _waiting(world)
        self.assertEqual((proposal.kind, proposal.law), (REPEAL_LAW, "tax"))

    def test_whoever_had_something_turned_down_leaves_it_be_for_weeks(self) -> None:
        world = _governed("direct_democracy")
        voting = world.politics.voting
        ines = world.residents["ines"]
        _held(world, "ines").collectivism, _held(world, "ines").individualism = 100.0, 0.0
        ines.personality.greed = 0.0

        def hers() -> list[str]:
            return [idea.law for idea in voting.ideas(world, ines) if idea.kind == ENACT_LAW]

        self.assertIn("common_property", hers())
        self.assertTrue(voting.raise_as(world, ines, ENACT_LAW, law="common_property").ok)
        self.assertEqual(_decide(world).status, REJECTED)
        world.clock.day += world.registries.proposals.again_days + 1
        self.assertNotIn("common_property", hers(), "she remembers how it went")
        world.clock.day += world.registries.proposals.sore_days
        self.assertIn("common_property", hers())

    def test_a_law_just_passed_is_not_put_to_be_done_away_with_the_next_day(self) -> None:
        world = _governed("direct_democracy")
        self.assertTrue(world.propose(ENACT_LAW, law="rest_day").ok)
        self.assertEqual(_decide(world).status, ACCEPTED)
        self.assertFalse(world.propose(REPEAL_LAW, law="rest_day").ok)
        world.clock.day += world.registries.proposals.again_days
        self.assertNotIn("decidió hace poco", world.propose(REPEAL_LAW, law="rest_day").message)

    def test_whoever_may_not_propose_has_nobody_to_put_their_grumble_to(self) -> None:
        world = _governed("strong_mayor")
        leader = world.government.leader
        other = world.residents[next(resident_id for resident_id in world.residents if resident_id != leader)]
        before = _held(world, other.resident_id).resentment
        result = world.terms.raised(world, other, "barter")
        self.assertFalse(result.ok)
        self.assertEqual(world.government.proposals, {})
        self.assertGreater(_held(world, other.resident_id).resentment, before)


class ExpelTests(unittest.TestCase):
    def _voted_out(self, kind: str = "direct_democracy") -> tuple[SimulationWorld, Proposal]:
        """Sergio, known by all to be a thief and liked by nobody but Lucía, put to be thrown out."""
        world = _governed(kind)
        _gathered(world)
        _steals(world, "sergio", "nuria")
        for resident_id in world.residents:
            if resident_id not in ("sergio", "lucia"):
                world.relationship(resident_id, "sergio").resentment = 80.0
        world.relationship("lucia", "sergio").affection = 90.0
        world.relationship("lucia", "sergio").trust = 60.0
        self.assertTrue(world.politics.voting.raise_as(world, world.residents["nuria"], EXPEL, target="sergio").ok)
        return world, _waiting(world)

    def test_each_votes_on_throwing_somebody_out_by_what_they_feel_for_them_and_know_of_them(self) -> None:
        world, proposal = self._voted_out()
        votes = _ballots(world, proposal)
        self.assertEqual(votes["sergio"], NO, "nobody votes themselves out")
        self.assertEqual(votes["lucia"], NO)
        self.assertEqual(_reasons(world, proposal, "lucia")[0], "target")
        self.assertEqual(votes["paco"], YES)
        self.assertEqual(set(_reasons(world, proposal, "paco")[:2]), {"target", "evidence"})
        # What Paco knows is part of it: had he never seen it, he would have less against him.
        unseen = world.politics.voting.mind(world, world.residents["paco"], proposal)[1]
        self.assertGreater(unseen["evidence"], 0)

    def test_whoever_is_thrown_out_walks_to_the_gate_and_is_gone_for_good(self) -> None:
        world, proposal = self._voted_out()
        sergio = world.residents["sergio"]
        post, job = sergio.post_id, sergio.job_id
        world.stock(world.containers["crate_1"], "canned_beans", 3, "sergio")
        self.assertEqual(_decide(world).status, ACCEPTED)
        self.assertIn("sergio", world.residents, "they are not gone on the spot")
        self.assertIn("sergio", world.leaving)
        self.assertIn("resident_expelled", _types(world))
        world.step(120)
        self.assertNotIn("sergio", world.residents)
        self.assertNotIn("sergio", world.leaving)
        self.assertIn("resident_left", _types(world))
        self.assertEqual([exile.resident_id for exile in world.exiled], ["sergio"])
        self.assertEqual(world.deaths, [], "nobody died")
        self.assertFalse(any(placed.kind == "grave" for placed in world.interactables.values()))
        self.assertFalse(any(each.post_id == post and each.job_id == job for each in world.residents.values()))
        self.assertFalse(
            any(item.owner_id == "sergio" for inventory in world.containers.values() for item in inventory.items),
            "what they kept is nobody's now",
        )
        self.assertIn("sergio", world.kinship, "and who they were is not forgotten")
        self.assertTrue(any("Sergio" in text for text in _memories(world, "lucia")))
        world.step(60 * 24)
        self.assertNotIn("sergio", world.residents)

    def test_the_settlement_goes_on_without_them(self) -> None:
        world, _proposal = self._voted_out()
        _decide(world)
        world.step(60 * 24 * 3)
        self.assertEqual(len(world.residents), 8)
        self.assertNotIn("sergio", [each.voter for each in world.politics.voting.count(world, Proposal("x", ENACT_LAW, law="rest_day"))])

    def test_after_a_show_of_hands_they_and_those_near_them_know_who_did_it(self) -> None:
        world, proposal = self._voted_out()
        _decide(world)
        for_it = [ballot.voter for ballot in proposal.ballots if ballot.vote == YES]
        self.assertIn("paco", for_it)
        remembered = next(memory for memory in world.memories.of("sergio") if "Me echaron" in memory.text)
        self.assertEqual(set(remembered.people), set(for_it))
        self.assertGreater(world.relationship("sergio", "paco").resentment, 0.0)
        self.assertLess(world.relationship("sergio", "paco").trust, 0.0)
        # Lucía, who cared for him, holds it against those who voted for it and against the government.
        hers = next(memory for memory in world.memories.of("lucia") if "Echaron a Sergio" in memory.text)
        self.assertIn("paco", hers.people)
        self.assertGreater(world.relationship("lucia", "paco").resentment, 0.0)
        self.assertGreater(_held(world, "lucia").resentment, 0.0)
        self.assertEqual(world.relationship("vera", "paco").resentment, 0.0, "whoever was not close to him holds nothing")

    def test_whoever_they_wanted_out_and_stays_remembers_who_stood_by_them(self) -> None:
        world, proposal = self._voted_out()
        for resident_id in world.residents:
            if resident_id not in ("sergio", "nuria"):
                world.relationship(resident_id, "sergio").resentment = 0.0
                world.relationship(resident_id, "sergio").affection = 70.0
        _decide(world)
        self.assertEqual(proposal.status, REJECTED)
        self.assertIn("sergio", world.residents)
        self.assertNotIn("sergio", world.leaving)
        remembered = next(memory for memory in world.memories.of("sergio") if "Quisieron echarme" in memory.text)
        self.assertIn("nuria", remembered.people)
        self.assertGreater(world.relationship("sergio", "nuria").resentment, 0.0)
        self.assertGreater(world.relationship("sergio", "lucia").affection, 0.0)

    def test_a_leader_who_is_thrown_out_is_followed_like_one_who_dies(self) -> None:
        world = _assembly()
        leader = world.residents[world.government.leader]
        world.politics.exile.banish(world, leader, "porque sí")
        world.step(180)
        self.assertNotIn(leader.resident_id, world.residents)
        self.assertIn("leader_lost", _types(world))
        world.step(120)
        self.assertNotEqual(world.government.leader, leader.resident_id)
        self.assertIsNotNone(world.government.leader)

    def test_the_player_can_put_it_and_it_is_theirs_to_answer_for(self) -> None:
        world = _governed("direct_democracy")
        _gathered(world)
        _steals(world, "sergio", "nuria")
        for resident_id in world.residents:
            if resident_id != "sergio":
                world.relationship(resident_id, "sergio").resentment = 80.0
        world.relationship("lucia", "sergio").resentment = 0.0
        world.relationship("lucia", "sergio").affection = 90.0
        result = world.apply_command(ProposeCommand(EXPEL, target="sergio"))
        self.assertTrue(result.ok, result.message)
        proposal = world.government.proposals[result.detail]
        self.assertNotEqual(proposal.sponsor, "sergio")
        _decide(world)
        self.assertEqual(proposal.status, ACCEPTED)
        influence = world.politics.influence
        self.assertLess(influence.standing(world, world.residents["lucia"]).trust, 50.0)
        self.assertGreater(influence.standing(world, world.residents["nuria"]).trust, 50.0)


class ElectionTests(unittest.TestCase):
    def test_not_everybody_stands_and_whoever_leads_does(self) -> None:
        world = _governed("strong_mayor")
        leadership = world.politics.leadership
        standing = [resident.resident_id for resident in leadership.standing(world)]
        self.assertIn(world.government.leader, standing)
        self.assertLess(len(standing), len(world.residents))
        self.assertGreaterEqual(len(standing), 2)
        self.assertNotIn("paco", standing, "politics is nothing to him")
        _held(world, "paco").political_interest = 100.0
        self.assertIn("paco", [resident.resident_id for resident in leadership.standing(world)])
        # With nobody who wants it, the two who mind least stand all the same.
        for resident_id in world.residents:
            _held(world, resident_id).political_interest = 0.0
        world.government.leader = None
        self.assertEqual(len(leadership.standing(world)), 2)

    def test_a_vote_that_is_called_has_whoever_leads_win_again_or_go(self) -> None:
        world = _governed("strong_mayor")
        leader = world.government.leader
        for resident_id in world.residents:
            if resident_id not in (leader, "vera"):
                world.relationship(resident_id, "vera").affection = 80.0
                world.relationship(resident_id, "vera").trust = 80.0
        self.assertTrue(world.politics.leadership.recall(world))
        self.assertFalse(world.politics.leadership.recall(world), "one at a time")
        world.step(61)
        self.assertEqual(world.government.leader, "vera")
        self.assertIn("mayor", world.residents["vera"].roles)
        self.assertNotIn("mayor", world.residents[leader].roles)
        record = world.government.elections[-1]
        self.assertEqual((record.winner, record.seat), ("vera", "leader"))
        self.assertGreater(record.tally["vera"], record.tally[leader])
        self.assertEqual(sum(record.tally.values()), len(record.backed))

    def test_the_result_of_an_election_is_kept_and_is_still_there_after_saving_and_loading(self) -> None:
        world = _governed("strong_mayor")
        world.politics.leadership.recall(world)
        world.step(61)
        record = world.government.elections[-1]
        winner = world.government.leader
        self.assertEqual(record.winner, winner)
        loaded = SaveManager().from_data(json.loads(json.dumps(SaveManager().to_data(world))))
        self.assertEqual(loaded.government.leader, winner)
        self.assertEqual(loaded.government.elections, world.government.elections)
        self.assertIn("mayor", loaded.residents[winner].roles)
        loaded.step(60 * 24)
        self.assertEqual(loaded.government.leader, winner)

    def test_those_who_took_part_in_an_election_remember_it(self) -> None:
        world = _governed("strong_mayor")
        leader = world.government.leader
        for resident_id in world.residents:
            if resident_id not in (leader, "vera"):
                world.relationship(resident_id, "vera").affection = 80.0
                world.relationship(resident_id, "vera").trust = 80.0
        world.relationship("paco", "vera").affection = -80.0
        world.relationship("paco", leader).affection = 80.0
        trust = _held(world, "paco").trust
        world.politics.leadership.recall(world)
        world.step(61)
        record = world.government.elections[-1]
        self.assertEqual(record.backed["paco"], leader)
        self.assertTrue(any("Voté a Vera para mandar, y ganó" in text for text in _memories(world, "lucia")))
        let_down = next(memory for memory in world.memories.of("paco") if "election" in memory.tags)
        self.assertIn("y ganó Vera", let_down.text)
        self.assertLess(let_down.emotional_value, 0)
        self.assertLess(_held(world, "paco").trust, trust, "whoever backed a loser trusts it all a little less")
        self.assertTrue(any("Perdí la votación" in text for text in _memories(world, leader)))
        self.assertGreater(world.relationship(leader, "vera").resentment, 0.0, "a loser holds it against whoever won")

    def test_the_player_puts_an_election_and_those_who_decide_decide_it(self) -> None:
        world = _assembly()
        for resident_id in world.residents:
            _held(world, resident_id).loyalty, _held(world, resident_id).trust = 0.0, 10.0
            _held(world, resident_id).resentment = 70.0
        result = world.apply_command(ProposeCommand(CALL_ELECTION))
        self.assertTrue(result.ok, result.message)
        self.assertIsNone(world.government.election_at, "nothing is called until it is decided")
        proposal = _decide(world)
        self.assertEqual(proposal.status, ACCEPTED)
        self.assertIsNotNone(world.government.election_at)
        self.assertTrue(world.government.recall)
        self.assertEqual(_ballots(world, proposal)[world.government.leader], NO, "whoever leads is against it")
        world.step(61)
        self.assertIn("election_held", _types(world))
        self.assertFalse(world.government.recall)

    def test_the_player_speaks_for_a_candidate_once_and_they_vote_as_they_see_fit(self) -> None:
        world = _governed("strong_mayor")
        leader = world.government.leader
        self.assertFalse(world.apply_command(BackCandidateCommand("paco", "vera")).ok, "no vote has been called")
        world.politics.leadership.recall(world)
        leadership = world.politics.leadership
        paco = world.residents["paco"]
        standing = leadership.standing(world)

        def choice() -> str:
            return max(standing, key=lambda each: leadership.vote_score(world, paco, each)).resident_id

        self.assertEqual(choice(), leader)
        # Paco thinks the world of whoever it is that advises them.
        world.politics.influence.standing(world, paco).trust = 100.0
        self.assertFalse(world.back_candidate("paco", "paco").ok, "he does not stand")
        result = world.apply_command(BackCandidateCommand("paco", "vera"))
        self.assertTrue(result.ok, result.message)
        self.assertEqual(choice(), "vera")
        self.assertFalse(world.back_candidate("paco", "ines").ok, "once is all")
        self.assertGreater(world.politics.influence.standing(world, paco).resistance, 0.0, "it was not what he had in mind")
        world.step(61)
        self.assertEqual(world.government.elections[-1].backed["paco"], "vera")
        self.assertEqual(world.government.backing, {}, "and what was said is done with once the vote is held")


class FraudTests(unittest.TestCase):
    def _losing(self, ballot: str = SECRET) -> SimulationWorld:
        """A mayor nobody is behind, with a vote called that Vera is going to win."""
        world = _settled()
        mayor = world.registries.politics.governments["strong_mayor"]
        _politics(
            world,
            election_hours=2,
            governments={**world.registries.politics.governments, "strong_mayor": replace(mayor, ballot=ballot)},
        )
        world.politics.leadership.establish(world, "strong_mayor")
        leader = world.government.leader
        for resident_id in world.residents:
            if resident_id not in (leader, "vera"):
                world.relationship(resident_id, "vera").affection = 80.0
                world.relationship(resident_id, "vera").trust = 80.0
        world.politics.leadership.recall(world)
        return world

    def _asked(self, world: SimulationWorld):
        return next((decision for decision in world.decisions.values() if decision.kind == RIG), None)

    def test_a_leader_about_to_lose_a_secret_vote_thinks_of_seeing_to_the_count(self) -> None:
        world = self._losing()
        leader = world.government.leader
        world.step(30)
        self.assertIsNone(self._asked(world), "not until the vote is near")
        world.step(31)
        decision = self._asked(world)
        self.assertIsNotNone(decision)
        self.assertEqual(decision.resident_id, leader)
        self.assertIn("rigging_stirring", _types(world))

    def test_nobody_miscounts_a_show_of_hands_and_nobody_rigs_what_they_are_winning(self) -> None:
        world = self._losing(OPEN)
        world.step(119)
        self.assertIsNone(self._asked(world))
        winning = _governed("strong_mayor")
        winning.politics.leadership.recall(winning)
        winning.step(59)
        self.assertIsNone(self._asked(winning))

    def test_a_count_that_is_seen_to_comes_out_for_whoever_saw_to_it(self) -> None:
        world = self._losing()
        leader = world.government.leader
        _held(world, leader).justice_sensitivity = 0.0
        world.residents[leader].personality.greed = 100.0
        world.step(61)
        self.assertEqual(world.apply_command(ChooseOptionCommand(self._asked(world).decision_id, "encourage")), "rig")
        self.assertEqual(world.government.rigged_by, leader)
        self.assertIn("election_rigged", _types(world))
        corruption = world.government.measures["corruption"]
        self.assertGreater(corruption, 0.0)
        world.step(60)
        self.assertEqual(world.government.leader, leader, "they go on leading")
        record = world.government.elections[-1]
        self.assertEqual((record.winner, record.rigged_by), (leader, leader))
        self.assertGreater(record.tally[leader], record.tally["vera"], "as it was given out")
        cast = list(record.backed.values())
        self.assertGreater(cast.count("vera"), cast.count(leader), "and not as it was cast")
        self.assertEqual(sum(record.tally.values()), len(cast), "no vote is made up: they change hands")
        self.assertIsNone(world.government.rigged_by)
        held = next(event for event in world.history if event.event_type == "election_held")
        self.assertEqual(held.data["backers"], [], "nobody is told who voted for whom")

    def test_advised_against_it_or_with_scruples_they_let_the_votes_say_what_they_say(self) -> None:
        world = self._losing()
        leader = world.government.leader
        _held(world, leader).justice_sensitivity = 100.0
        world.step(61)
        self.assertEqual(world.apply_command(ChooseOptionCommand(self._asked(world).decision_id, "discourage")), "accept")
        world.step(60)
        self.assertEqual(world.government.leader, "vera")
        self.assertIsNone(world.government.elections[-1].rigged_by)
        self.assertNotIn("election_rigged", _types(world))

    def test_left_to_make_up_their_mind_they_do_it_by_the_time_of_the_vote(self) -> None:
        world = self._losing()
        leader = world.government.leader
        _held(world, leader).justice_sensitivity = 0.0
        world.residents[leader].personality.greed = 100.0
        world.residents[leader].personality.courage = 100.0
        world.step(121)
        self.assertIsNone(self._asked(world))
        self.assertEqual(world.government.elections[-1].rigged_by, leader)
        self.assertEqual(world.government.leader, leader)

    def test_only_whoever_sees_it_done_knows_and_it_costs_the_government_dear_with_them(self) -> None:
        world = self._losing()
        leader = world.government.leader
        _gathered(world)
        world.residents["paco"].x, world.residents["paco"].y = 5, 30
        world.residents["paco"].activity = Activity("wander", minutes_left=600, using=True)
        trust = {resident_id: _held(world, resident_id).trust for resident_id in world.residents}
        legitimacy = world.government.measures["legitimacy"]
        world.politics.elections.rig(world, world.residents[leader])
        fact = next(fact for fact in world.knowledge.facts.values() if fact.event_type == "election_rigged")
        self.assertTrue(world.knowledge.knows("lucia", fact.fact_id))
        self.assertFalse(world.knowledge.knows("paco", fact.fact_id))
        self.assertLess(_held(world, "lucia").trust, trust["lucia"])
        self.assertEqual(_held(world, "paco").trust, trust["paco"])
        self.assertLess(world.government.measures["legitimacy"], legitimacy)
        self.assertGreater(world.relationship("lucia", leader).resentment, 0.0)

    def test_a_sore_loser_says_there_was_cheating_whether_there_was_or_not(self) -> None:
        for rigged in (True, False):
            world = self._losing()
            leader = world.government.leader
            _gathered(world)
            if rigged:
                world.government.rigged_by = leader
                loser = "vera"
            else:
                loser = leader
            _held(world, loser).revengefulness, _held(world, loser).trust = 100.0, 10.0
            world.government.rig_asked = True
            legitimacy = world.government.measures["legitimacy"]
            world.step(121)
            record = world.government.elections[-1]
            self.assertEqual(record.rigged_by is not None, rigged)
            self.assertEqual(record.claimed_by, [loser], rigged)
            self.assertIn("fraud_claimed", _types(world))
            self.assertTrue(any("Me robaron la votación" in text for text in _memories(world, loser)))
            self.assertLess(world.government.measures["legitimacy"], legitimacy + 8.0, "whoever hears it thinks the less of the result")
            fact = next(fact for fact in world.knowledge.facts.values() if fact.event_type == "fraud_claimed")
            self.assertEqual(fact.subject_ids[0], record.winner)

    def test_a_loser_with_no_grudge_takes_it(self) -> None:
        world = self._losing()
        leader = world.government.leader
        _held(world, leader).revengefulness, _held(world, leader).trust = 0.0, 90.0
        world.government.rig_asked = True
        world.step(121)
        self.assertEqual(world.government.elections[-1].claimed_by, [])
        self.assertNotIn("fraud_claimed", _types(world))


class SaveTests(unittest.TestCase):
    def test_everything_politics_keeps_comes_back_as_it_was(self) -> None:
        world = _governed("direct_democracy")
        _gathered(world)
        world.politics.laws.enact(world, "banned_food", 0, {"item": "vegetables"}, "vera", True)
        self.assertTrue(world.propose(ENACT_LAW, law="curfew").ok)
        proposal = _waiting(world)
        world.lobby(proposal.proposal_id, "sergio", "for")
        self.assertTrue(world.propose(ENACT_LAW, law="rest_day").ok)
        world.politics.voting.decide(world, world.government.proposals["proposal_2"])
        world.politics.exile.banish(world, world.residents["paco"], "por pesado")
        world.government.meals["raul"] = [world.clock.day, 2]
        world.government.backing["raul"] = ["vera", 3.5]
        saved = SaveManager().to_data(world)
        self.assertEqual(saved["version"], 31)
        loaded = SaveManager().from_data(json.loads(json.dumps(saved)))
        self.assertEqual(loaded.government, world.government)
        self.assertEqual(loaded.player_standing, world.player_standing)
        self.assertEqual(loaded.leaving, world.leaving)
        self.assertEqual(loaded.exiled, world.exiled)
        self.assertEqual(SaveManager().to_data(loaded), saved)
        # And it goes on from there the same.
        for each in (world, loaded):
            each.step(60 * 13)
        self.assertEqual(loaded.government.decided[-1].status, world.government.decided[-1].status)
        self.assertEqual(loaded.government.decided[-1].ballots, world.government.decided[-1].ballots)
        self.assertNotIn("paco", loaded.residents)

    def test_a_save_from_before_has_no_laws_nothing_waiting_and_nobody_thrown_out(self) -> None:
        world = _governed("strong_mayor")
        data = SaveManager().to_data(world)
        data["version"] = 30
        for added in ("player_standing", "leaving", "exiled"):
            del data[added]
        for added in (
            "laws", "meals", "proposals", "decided", "proposal_count", "refused", "raised_on", "elections",
            "recall", "rigged_by", "rig_asked", "backing",
        ):
            del data["government"][added]
        loaded = SaveManager().from_data(json.loads(json.dumps(data)))
        state = loaded.government
        self.assertEqual((state.kind, state.leader), (world.government.kind, world.government.leader))
        self.assertEqual((state.laws, state.proposals, state.decided, state.elections), ({}, {}, [], []))
        self.assertEqual((loaded.player_standing, loaded.leaving, loaded.exiled), ({}, {}, []))
        self.assertEqual(loaded.politics.influence.factor(loaded, loaded.residents["paco"]), 1.0)
        loaded.step(60 * 24)
        self.assertTrue(loaded.propose(ENACT_LAW, law="rest_day").ok)

    def test_what_is_no_longer_defined_is_dropped_on_loading(self) -> None:
        world = _governed("direct_democracy")
        world.politics.laws.enact(world, "curfew", 1)
        self.assertTrue(world.propose(ENACT_LAW, law="rest_day").ok)
        data = json.loads(json.dumps(SaveManager().to_data(world)))
        data["government"]["laws"]["fashion_police"] = {"law_id": "fashion_police", "degree": 0}
        data["government"]["proposals"]["proposal_9"] = {"proposal_id": "proposal_9", "kind": "coronation"}
        data["leaving"]["somebody_gone"] = 5
        loaded = SaveManager().from_data(data)
        self.assertEqual(set(loaded.government.laws), {"curfew"})
        self.assertEqual(set(loaded.government.proposals), {"proposal_1"})
        self.assertEqual(loaded.leaving, {})


class HeadlessTests(unittest.TestCase):
    def test_a_settlement_runs_two_weeks_under_each_government_putting_things_and_deciding_them(self) -> None:
        for kind in ("strong_mayor", "council", "direct_democracy", "military_leadership", "commune", "personalist_rule"):
            world = SimulationWorld.demo_world(seed=11)
            world.politics.leadership.establish(world, kind)
            world.propose(ENACT_LAW, law="rest_day")
            world.propose(ENACT_LAW, law="curfew", degree=2)
            world.step(60 * 24 * 14)
            state = world.government
            self.assertEqual(state.kind, kind)
            self.assertTrue(all(proposal.status != "pending" for proposal in state.decided), kind)
            self.assertLessEqual(len(state.proposals), world.registries.proposals.pending_limit, kind)
            for measure, value in state.measures.items():
                self.assertTrue(0.0 <= value <= 100.0, (kind, measure, value))
            SaveManager().from_data(json.loads(json.dumps(SaveManager().to_data(world))))

    def test_the_same_seed_decides_the_same_things(self) -> None:
        def run() -> list[str]:
            world = SimulationWorld.demo_world(seed=5)
            world.step(60 * 13)
            world.propose(ENACT_LAW, law="rest_day")
            world.step(60 * 24 * 6)
            return [line for line in world.event_log if "proposal" in line or "law_" in line or "vote" in line]

        self.assertEqual(run(), run())


if __name__ == "__main__":
    unittest.main()
