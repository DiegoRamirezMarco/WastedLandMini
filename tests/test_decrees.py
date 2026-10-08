"""What the player runs since S45: laws and what the settlement trades with, as the government
in force lets them be put, and the square people take to against a law they cannot abide."""

import json
import unittest
from dataclasses import replace

from save.save_manager import SaveManager
from simulation.commands import ProposeBarterCommand, ProposeCommand
from simulation.politics.government import politics_settings_from_data
from simulation.politics.law import law_settings_from_data
from simulation.politics.proposal import (
    DECREES,
    ENACT_LAW,
    RAISED_BY_RESIDENTS,
    REPEAL_LAW,
    proposal_settings_from_data,
)
from simulation.politics.records import ACCEPTED, PLAYER, REJECTED
from simulation.residents.activity import PROTEST_ACTION, Activity
from simulation.residents.needs import Needs
from simulation.world import SimulationWorld
from world.pathfinding import manhattan


def _settled(seed: int = 7) -> SimulationWorld:
    """The ready-made settlement with nothing felt by anyone for anyone, and nobody in need."""
    world = SimulationWorld.demo_world(seed=seed)
    world.relationships.clear()
    for resident in world.residents.values():
        resident.needs = Needs(hunger=0, tiredness=0, social=0, stress=0)
    return world


def _governed(kind: str, seed: int = 7) -> SimulationWorld:
    world = _settled(seed)
    world.politics.leadership.establish(world, kind)
    return world


def _types(world: SimulationWorld) -> list[str]:
    return [line.split(" | ")[1] for line in world.event_log]


def _held(world: SimulationWorld, resident_id: str):
    return world.politics.legitimacy.profile(world, world.residents[resident_id])


def _at(world: SimulationWorld, hour: int, minute: int = 0) -> None:
    world.clock.hour, world.clock.minute = hour, minute


def _hates(world: SimulationWorld, law_id: str, *resident_ids: str) -> None:
    """Have a law weigh on nothing but who somebody is, and these be the ones it weighs on."""
    laws = world.registries.laws
    law = replace(laws.laws[law_id], opinion={"individualism": -2.0}, bias=1.0)
    world.registries = replace(world.registries, laws=replace(laws, laws={**laws.laws, law_id: law}))
    for resident_id in world.residents:
        _held(world, resident_id).individualism = 100.0 if resident_id in resident_ids else 0.0


def _stand_in_the_square(world: SimulationWorld, law_id: str) -> list[str]:
    """Call today's protest and have whoever goes be standing there as it ends."""
    protests = world.politics.protests
    _at(world, protests.settings(world).hours[0])
    out = protests.call(world).get(law_id, [])
    centre = protests.square(world, (0, 0))
    for resident_id in out:
        resident = world.residents[resident_id]
        resident.x, resident.y = centre
        resident.activity = Activity(PROTEST_ACTION, minutes_left=60, item_id=law_id)
    protests.close(world)
    return out


class DataTests(unittest.TestCase):
    def test_laws_and_the_currency_are_the_players_and_elections_the_residents(self) -> None:
        settings = SimulationWorld.demo_world().registries.proposals
        self.assertEqual(set(settings.decrees), set(DECREES))
        self.assertEqual(set(settings.residents_raise), set(RAISED_BY_RESIDENTS))
        self.assertNotIn(ENACT_LAW, settings.residents_raise)

    def test_data_that_names_a_kind_there_is_not_is_refused(self) -> None:
        with self.assertRaises(ValueError):
            proposal_settings_from_data({"decrees": ["crown_somebody"]})
        with self.assertRaises(ValueError):
            proposal_settings_from_data({"residents_raise": ["riot"]})

    def test_every_government_says_how_freely_people_speak_out(self) -> None:
        governments = SimulationWorld.demo_world().registries.politics.governments
        self.assertEqual(governments["personalist_rule"].dissent, 0.0)
        self.assertEqual(governments["direct_democracy"].dissent, 1.0)
        self.assertLess(governments["military_leadership"].dissent, governments["strong_mayor"].dissent)
        with self.assertRaises(ValueError):
            politics_settings_from_data({"governments": {"odd": {"name": "Rara", "dissent": 1.5}}})

    def test_a_protest_is_data_and_makes_sense(self) -> None:
        settings = law_settings_from_data({"protest": {"hours": [10, 12], "from": 0.2, "reach": 5, "kind": "campfire"}})
        self.assertEqual((settings.protest.hours, settings.protest.start), ((10, 12), 0.2))
        self.assertEqual((settings.protest.reach, settings.protest.kind), (5, "campfire"))
        for wrong in ({"hours": [15, 12]}, {"tire_days": 0}, {"from": 0}, {"reach": -1}):
            with self.assertRaises(ValueError, msg=wrong):
                law_settings_from_data({"protest": wrong})

    def test_the_settlement_that_comes_ready_made_has_a_square(self) -> None:
        world = SimulationWorld.demo_world()
        kind = world.politics.protests.settings(world).kind
        squares = [placed for placed in world.interactables.values() if placed.kind == kind]
        self.assertEqual(len(squares), 1)
        self.assertFalse(world.definition_of(squares[0]).blocks, "people stand in it")
        self.assertIsNone(world.definition_of(squares[0]).build, "and one is simply put down")


class DecreeTests(unittest.TestCase):
    def test_where_one_person_decides_it_is_law_there_and_then(self) -> None:
        for kind in ("strong_mayor", "military_leadership", "personalist_rule"):
            world = _governed(kind)
            result = world.apply_command(ProposeCommand(ENACT_LAW, law="curfew", degree=2))
            self.assertTrue(result.ok, result.message)
            self.assertEqual(world.government.proposals, {}, kind)
            held = world.government.laws["curfew"]
            self.assertEqual((held.degree, held.by, held.imposed, held.pushed), (2, PLAYER, True, True))
            decided = world.government.decided[-1]
            self.assertEqual((decided.status, decided.imposed, decided.sponsor, decided.ballots), (ACCEPTED, True, None, []))
            self.assertNotIn("vote_held", _types(world), "nobody is asked")
            self.assertIn("law_enacted", _types(world))

    def test_whoever_leads_cannot_refuse_it_however_much_against_it_they_are(self) -> None:
        world = _governed("strong_mayor")
        leader = world.residents[world.government.leader]
        _hates(world, "curfew", leader.resident_id)
        self.assertLess(world.politics.laws.regard(world, leader, "curfew", 2), 0.0)
        self.assertTrue(world.apply_command(ProposeCommand(ENACT_LAW, law="curfew", degree=2)).ok)
        self.assertIn("curfew", world.government.laws)
        self.assertNotIn("proposal_vetoed", _types(world))

    def test_where_everybody_decides_everybody_has_their_vote(self) -> None:
        world = _governed("direct_democracy")
        result = world.apply_command(ProposeCommand(ENACT_LAW, law="curfew", degree=2))
        self.assertTrue(result.ok, result.message)
        proposal = world.government.proposals[result.detail]
        self.assertEqual((proposal.by, proposal.sponsor, proposal.imposed), (PLAYER, None, False))
        self.assertEqual(world.government.laws, {}, "nothing is done until it is voted")
        world.step(world.registries.proposals.debate_hours * 60 + 1)
        self.assertEqual(proposal.status, REJECTED)
        self.assertEqual(len(proposal.ballots), len(world.residents))
        self.assertEqual(world.government.laws, {}, "and turned down, nothing of it happens")
        self.assertIn("vote_held", _types(world))

    def test_a_law_they_vote_for_is_law_and_was_not_put_on_them(self) -> None:
        world = _governed("direct_democracy")
        self.assertTrue(world.apply_command(ProposeCommand(ENACT_LAW, law="rest_day")).ok)
        world.step(world.registries.proposals.debate_hours * 60 + 1)
        self.assertEqual(world.government.decided[-1].status, ACCEPTED)
        self.assertFalse(world.government.laws["rest_day"].imposed)

    def test_under_a_council_it_is_the_council_that_votes(self) -> None:
        world = _governed("council")
        result = world.apply_command(ProposeCommand(ENACT_LAW, law="rest_day"))
        self.assertTrue(result.ok, result.message)
        world.step(world.registries.proposals.debate_hours * 60 + 1)
        voters = {each.voter for each in world.government.decided[-1].ballots}
        self.assertEqual(voters, set(world.government.council))

    def test_with_the_seat_empty_it_falls_to_a_vote(self) -> None:
        world = _governed("strong_mayor")
        world.politics.leadership.resign(world, world.residents[world.government.leader])
        self.assertIsNone(world.government.leader)
        result = world.apply_command(ProposeCommand(ENACT_LAW, law="rest_day"))
        self.assertTrue(result.ok, result.message)
        self.assertIn(result.detail, world.government.proposals)
        self.assertEqual(world.government.laws, {})

    def test_what_was_decreed_can_be_undone_the_same_day(self) -> None:
        world = _governed("personalist_rule")
        self.assertTrue(world.apply_command(ProposeCommand(ENACT_LAW, law="tax", degree=2)).ok)
        self.assertTrue(world.apply_command(ProposeCommand(ENACT_LAW, law="tax", degree=0)).ok, "made milder")
        self.assertEqual(world.government.laws["tax"].degree, 0)
        self.assertTrue(world.apply_command(ProposeCommand(REPEAL_LAW, law="tax")).ok)
        self.assertEqual(world.government.laws, {})
        self.assertFalse(world.apply_command(ProposeCommand(REPEAL_LAW, law="tax")).ok, "it is no longer in force")

    def test_what_makes_no_sense_is_refused_whoever_governs(self) -> None:
        world = _governed("personalist_rule")
        self.assertFalse(world.apply_command(ProposeCommand(ENACT_LAW, law="no_such_law")).ok)
        self.assertFalse(world.apply_command(ProposeCommand(ENACT_LAW, law="curfew", degree=9)).ok)
        self.assertFalse(_settled().apply_command(ProposeCommand(ENACT_LAW, law="curfew")).ok, "no government yet")

    def test_how_the_settlement_trades_is_the_players_to_say_too(self) -> None:
        world = _governed("strong_mayor")
        self.assertTrue(world.trading.in_use)
        result = world.apply_command(ProposeBarterCommand())
        self.assertTrue(result.ok, result.message)
        self.assertFalse(world.trading.in_use, "under a mayor it is done")
        voted = _governed("direct_democracy")
        self.assertTrue(voted.apply_command(ProposeBarterCommand()).ok)
        self.assertTrue(voted.trading.in_use, "and under an assembly it waits for the vote")
        self.assertEqual(len(voted.government.proposals), 1)

    def test_a_decree_is_held_to_the_players_account_by_how_it_turns_out_for_each(self) -> None:
        world = _governed("strong_mayor")
        _hates(world, "curfew", "raul")
        self.assertTrue(world.apply_command(ProposeCommand(ENACT_LAW, law="curfew", degree=2)).ok)
        standing = world.politics.influence.standing
        self.assertLess(standing(world, world.residents["raul"]).trust, 50.0)
        self.assertGreater(standing(world, world.residents["vera"]).trust, 50.0)


class ResidentsTests(unittest.TestCase):
    def _hour_to_stir(self, world: SimulationWorld, days: int = 1) -> None:
        for _ in range(days):
            world.clock.day += 1
            _at(world, 8)
            world.politics.voting.tick(world)

    def test_nobody_puts_a_law_to_the_others_any_more(self) -> None:
        world = _governed("direct_democracy")
        resolve = world.registries.items.resolve
        for inventory in world.containers.values():
            inventory.items[:] = [item for item in inventory.items if resolve(item.definition_id).category != "food"]
        world.politics.laws.enact(world, "tax", 2)
        self._hour_to_stir(world, 10)
        raised = [*world.government.proposals.values(), *world.government.decided]
        self.assertEqual([each for each in raised if each.kind in DECREES], [])

    def test_whoever_leads_has_no_whims(self) -> None:
        world = _governed("personalist_rule")
        leader = world.residents[world.government.leader]
        leader.personality.sociability, leader.personality.aggression = 0.0, 100.0
        leader.personality.greed, leader.personality.empathy = 100.0, 0.0
        _held(world, leader.resident_id).political_interest = 100.0
        for _ in range(60):
            world.government.raised_on.clear()
            self._hour_to_stir(world)
        self.assertEqual(world.government.laws, {})

    def test_whoever_has_had_enough_of_how_things_are_traded_has_nobody_to_put_it_to(self) -> None:
        world = _governed("direct_democracy")
        raul = world.residents["raul"]
        before = _held(world, "raul").resentment
        result = world.terms.raised(world, raul, "barter")
        self.assertFalse(result.ok)
        self.assertEqual(world.government.proposals, {})
        self.assertGreater(_held(world, "raul").resentment, before)

    def test_they_still_call_for_a_vote_on_whoever_leads(self) -> None:
        world = _governed("direct_democracy")
        mayor = world.registries.politics.governments["strong_mayor"]
        made = replace(mayor, proposes="everyone", approves="everyone", votes="everyone")
        world.registries = replace(
            world.registries,
            politics=replace(
                world.registries.politics, governments={**world.registries.politics.governments, "strong_mayor": made}
            ),
        )
        world.politics.leadership.change_kind(world, "strong_mayor", None)
        leader = world.government.leader
        self.assertIsNotNone(leader)
        world.government.term_began = world.clock.day - 30
        for resident_id in world.residents:
            if resident_id != leader:
                profile = _held(world, resident_id)
                profile.loyalty, profile.trust, profile.resentment = 0.0, 0.0, 90.0
        self._hour_to_stir(world)
        self.assertEqual([each.kind for each in world.government.proposals.values()], ["call_election"])


class ProtestTests(unittest.TestCase):
    def _imposed(self, kind: str = "strong_mayor", *haters: str) -> SimulationWorld:
        world = _governed(kind)
        _hates(world, "curfew", *haters)
        self.assertTrue(world.apply_command(ProposeCommand(ENACT_LAW, law="curfew", degree=1)).ok)
        return world

    def test_whoever_cannot_abide_a_law_put_on_them_goes_out_against_it(self) -> None:
        world = self._imposed("strong_mayor", "raul", "ines")
        protests = world.politics.protests
        held = world.government.laws["curfew"]
        self.assertGreaterEqual(protests.grievance(world, world.residents["raul"], held), protests.settings(world).start)
        self.assertEqual(protests.grievance(world, world.residents["vera"], held), 0.0, "who is for it has none")
        _at(world, protests.settings(world).hours[0])
        self.assertEqual(protests.call(world), {"curfew": ["raul", "ines"]})
        self.assertIn("protest_called", _types(world))
        self.assertEqual(protests.out_today(world, "raul"), "curfew")
        self.assertIsNone(protests.out_today(world, "vera"))

    def test_they_leave_their_post_and_stand_in_the_square(self) -> None:
        world = self._imposed("strong_mayor", "raul", "ines")
        protests = world.politics.protests
        start, end = protests.settings(world).hours
        while not (world.clock.hour == start and world.clock.minute == 30):
            world.step(1)
        for resident_id in ("raul", "ines"):
            activity = world.residents[resident_id].activity
            self.assertIsNotNone(activity, resident_id)
            self.assertEqual((activity.action, activity.item_id), (PROTEST_ACTION, "curfew"))
        self.assertNotEqual(world.residents["vera"].activity.action if world.residents["vera"].activity else "", PROTEST_ACTION)
        while not (world.clock.hour == end and world.clock.minute == 0):
            world.step(1)
        centre = protests.square(world, (0, 0))
        placed = next(each for each in world.interactables.values() if each.kind == "plaza")
        self.assertEqual(centre, (placed.x, placed.y))
        held = next(event for event in world.history if event.event_type == "protest_held")
        self.assertEqual(sorted(held.data["who"]), ["ines", "raul"])
        self.assertEqual(world.government.protests["curfew"].days, 1)
        for resident_id in ("raul", "ines"):
            texts = [memory.text for memory in world.memories.of(resident_id)]
            self.assertTrue(any("Me planté en la plaza" in text for text in texts), resident_id)

    def test_whoever_stands_there_is_within_reach_of_the_square(self) -> None:
        world = self._imposed("strong_mayor", "raul", "ines")
        protests = world.politics.protests
        start = protests.settings(world).hours[0]
        while not (world.clock.hour == start + 1 and world.clock.minute == 30):
            world.step(1)
        centre = protests.square(world, (0, 0))
        for resident_id in ("raul", "ines"):
            resident = world.residents[resident_id]
            self.assertEqual(protests.protesting(world, resident), "curfew", resident_id)
            self.assertLessEqual(manhattan(resident.tile, centre), protests.settings(world).reach)

    def test_where_it_is_put_up_with_holding_costs_legitimacy_and_adds_to_unrest(self) -> None:
        world = self._imposed("strong_mayor", "raul", "ines", "paco")
        measures = world.government.measures
        self.assertLess(measures["authoritarianism"], world.politics.protests.settings(world).harsh_from)
        legitimacy, unrest = measures["legitimacy"], measures["unrest"]
        fear = _held(world, "raul").fear
        self.assertEqual(sorted(_stand_in_the_square(world, "curfew")), ["ines", "paco", "raul"])
        self.assertLess(measures["legitimacy"], legitimacy)
        self.assertGreater(measures["unrest"], unrest)
        self.assertEqual(_held(world, "raul").fear, fear, "nobody is leaned on")

    def test_where_the_settlement_is_harsh_they_are_leaned_on_instead(self) -> None:
        world = self._imposed("strong_mayor", "raul", "ines")
        measures = world.government.measures
        measures["authoritarianism"] = 90.0
        legitimacy, unrest = measures["legitimacy"], measures["unrest"]
        fear, resentment = _held(world, "raul").fear, _held(world, "raul").resentment
        _stand_in_the_square(world, "curfew")
        self.assertEqual((measures["legitimacy"], measures["unrest"]), (legitimacy, unrest))
        self.assertGreater(_held(world, "raul").fear, fear)
        self.assertGreater(_held(world, "raul").resentment, resentment)
        held = next(event for event in world.history if event.event_type == "protest_held")
        self.assertTrue(held.data["harsh"])

    def test_under_a_ruler_they_do_as_they_are_told_however_much_they_hate_it(self) -> None:
        world = self._imposed("personalist_rule", "raul", "ines", "paco")
        protests = world.politics.protests
        raul = world.residents["raul"]
        self.assertLess(world.politics.laws.regard(world, raul, "curfew", 1), -0.5)
        self.assertEqual(protests.grievance(world, raul, world.government.laws["curfew"]), 0.0)
        _at(world, protests.settings(world).hours[0])
        self.assertEqual(protests.call(world), {})

    def test_a_law_that_was_voted_brings_out_fewer_than_one_put_on_them(self) -> None:
        world = self._imposed("strong_mayor", "raul")
        protests = world.politics.protests
        raul = world.residents["raul"]
        held = world.government.laws["curfew"]
        imposed = protests.grievance(world, raul, held)
        held.imposed = False
        self.assertAlmostEqual(protests.grievance(world, raul, held), imposed / 2.0)

    def test_doing_away_with_the_law_is_taken_as_having_been_heard(self) -> None:
        world = self._imposed("strong_mayor", "raul", "ines")
        _stand_in_the_square(world, "curfew")
        _held(world, "raul").resentment = 40.0
        standing = world.politics.influence.standing(world, world.residents["raul"])
        trust, resentment = standing.trust, _held(world, "raul").resentment
        legitimacy = world.government.measures["legitimacy"]
        self.assertTrue(world.apply_command(ProposeCommand(REPEAL_LAW, law="curfew")).ok)
        self.assertNotIn("curfew", world.government.protests)
        self.assertIn("protest_won", _types(world))
        self.assertGreater(standing.trust, trust)
        self.assertLess(_held(world, "raul").resentment, resentment)
        self.assertGreater(world.government.measures["legitimacy"], legitimacy)
        texts = [memory.text for memory in world.memories.of("raul")]
        self.assertTrue(any(text.startswith("Quitaron la ley") for text in texts))

    def test_making_it_milder_is_heard_too_and_they_start_again_from_there(self) -> None:
        world = self._imposed("strong_mayor", "raul", "ines")
        _stand_in_the_square(world, "curfew")
        self.assertTrue(world.apply_command(ProposeCommand(ENACT_LAW, law="curfew", degree=0)).ok)
        self.assertIn("protest_won", _types(world))
        self.assertEqual(world.government.protests["curfew"].days, 0)
        texts = [memory.text for memory in world.memories.of("ines")]
        self.assertTrue(any(text.startswith("Rebajaron la ley") for text in texts))

    def test_a_law_done_away_with_that_nobody_was_out_against_is_no_victory(self) -> None:
        world = self._imposed("strong_mayor")
        self.assertTrue(world.apply_command(ProposeCommand(REPEAL_LAW, law="curfew")).ok)
        self.assertNotIn("protest_won", _types(world))

    def test_after_enough_days_of_it_for_nothing_they_give_it_up(self) -> None:
        world = self._imposed("strong_mayor", "raul")
        protests = world.politics.protests
        days = protests.settings(world).tire_days
        went = []
        for _ in range(days + 2):
            world.clock.day += 1
            went.append(_stand_in_the_square(world, "curfew"))
        self.assertEqual(went[0], ["raul"])
        self.assertEqual(went[-1], [], "and what they hold against it stays")
        self.assertLess(world.government.protests["curfew"].days, days + 1)

    def test_whoever_is_away_or_a_child_does_not_go(self) -> None:
        world = self._imposed("strong_mayor", "raul", "ines")
        world.residents["ines"].age = 8
        world.residents["ines"].born = None
        protests = world.politics.protests
        self.assertIsNone(protests.cause(world, world.residents["ines"]))
        self.assertIsNotNone(protests.cause(world, world.residents["raul"]))
        world.leaving["raul"] = world.clock.total_minutes + 60
        self.assertIsNone(protests.cause(world, world.residents["raul"]))

    def test_with_no_square_they_gather_where_newcomers_first_stand(self) -> None:
        world = self._imposed("strong_mayor", "raul")
        for object_id in [each.object_id for each in world.interactables.values() if each.kind == "plaza"]:
            del world.interactables[object_id]
        spawns = world.registries.maps[world.map_id].spawns
        self.assertEqual(world.politics.protests.square(world, (0, 0)), spawns[0])

    def test_nobody_is_out_where_no_law_is_in_force(self) -> None:
        world = _governed("strong_mayor")
        world.step(60 * 30)
        self.assertEqual(world.government.protests, {})
        self.assertNotIn("protest_called", _types(world))


class SaveTests(unittest.TestCase):
    def test_how_a_law_came_in_and_who_is_out_against_it_come_back(self) -> None:
        world = _governed("strong_mayor")
        _hates(world, "curfew", "raul", "ines")
        self.assertTrue(world.apply_command(ProposeCommand(ENACT_LAW, law="curfew", degree=1)).ok)
        _stand_in_the_square(world, "curfew")
        for resident in world.residents.values():
            resident.activity = None
        manager = SaveManager()
        saved = manager.to_data(world)
        self.assertEqual(saved["version"], manager.CURRENT_VERSION)
        loaded = manager.from_data(json.loads(json.dumps(saved)))
        self.assertTrue(loaded.government.laws["curfew"].imposed)
        self.assertEqual(loaded.government.protests, world.government.protests)
        self.assertEqual(loaded.government.decided, world.government.decided)

    def test_a_save_from_before_has_every_law_voted_and_nobody_out(self) -> None:
        world = _governed("strong_mayor")
        world.politics.laws.enact(world, "curfew", 1)
        saved = SaveManager().to_data(world)
        saved["version"] = 34
        saved["government"].pop("protests")
        for law in saved["government"]["laws"].values():
            law.pop("imposed")
        loaded = SaveManager().from_data(json.loads(json.dumps(saved)))
        self.assertFalse(loaded.government.laws["curfew"].imposed)
        self.assertEqual(loaded.government.protests, {})


if __name__ == "__main__":
    unittest.main()
