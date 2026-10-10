import json
import unittest

from save.save_manager import SaveManager
from simulation.combat.raid_system import RAID_FOUGHT_EVENT, RAID_OVER_EVENT, RAIDERS_MET
from simulation.combat.rules import BOTH, GUN, WON
from simulation.commands import (
    ChooseOptionCommand,
    FightActCommand,
    FightOnCommand,
    LeaveFightCommand,
    PlanTripCommand,
    WatchFightCommand,
)
from simulation.health.injury import Injury
from simulation.registries import BuiltInRegistries
from simulation.residents.activity import Activity
from simulation.residents.needs import URGENT_NEED, Needs
from simulation.work.expedition import FIGHT, PAY, RUN, Raid
from simulation.world import SimulationWorld

SCAVENGER = "scavenger"


def _types(world: SimulationWorld, since: int = 0) -> list[str]:
    return [line.split(" | ")[1] for line in world.event_log[since:]]


def _content(world: SimulationWorld) -> None:
    for resident in world.residents.values():
        resident.needs = Needs(hunger=0, tiredness=0, social=0, stress=0)


def _settled(seed: int = 7) -> SimulationWorld:
    world = SimulationWorld.demo_world(seed=seed)
    world.relationships.clear()
    _content(world)
    return world


def _level(world: SimulationWorld, resident_id: str, level: int) -> None:
    resident = world.residents[resident_id]
    job = world.registries.jobs[resident.job_id]
    marks = world.registries.crafts.levels
    while world.crafts.level(world, resident, job.job_id) < level:
        world.crafts.worked(world, resident, job, max(1.0, marks[level - 1] - resident.trade.get(job.job_id, 0.0)))


def _out(world: SimulationWorld, raids_in: int | None = 5):
    """Send the scavenger out, with raiders in their way in so many minutes, or with none."""
    sergio = world.residents["sergio"]
    world.expeditions.set_out(world, sergio, world.registries.jobs[SCAVENGER])
    sergio.expedition.raids_at = [] if raids_in is None else [world.clock.total_minutes + raids_in]
    return sergio


def _met(world: SimulationWorld, foes: list[list], limit: int = 60):
    """Go on until the scavenger, who is out, has come on raiders, and say who those are."""
    sergio = world.residents["sergio"]
    for _ in range(limit):
        world.step(1)
        _content(world)
        if sergio.expedition is not None and sergio.expedition.raid is not None:
            sergio.expedition.raid.foes = [list(foe) for foe in foes]
            return sergio.expedition
    raise AssertionError("they never came on anybody")


def _advise(world: SimulationWorld, option: str) -> str | None:
    decision = world.interventions.pending_for(world, "sergio")
    return world.apply_command(ChooseOptionCommand(decision.decision_id, option))


def _until_over(world: SimulationWorld, limit: int = 200) -> None:
    for _ in range(limit):
        world.step(1)
        _content(world)
        sergio = world.residents.get("sergio")
        if sergio is None or sergio.expedition is None or sergio.expedition.raid is None:
            return
    raise AssertionError("it never came to an end")


class OnTheWayTests(unittest.TestCase):
    """Each zone a trip goes through may have raiders lying in wait, the likelier the further (S70)."""

    def test_the_further_the_zone_the_likelier_and_at_most_once_in_each(self) -> None:
        zones = self._zones()
        chances = [zone.chance for zone in zones]
        self.assertEqual(chances, sorted(chances))
        # By the fence nobody lies in wait: a settlement left to itself, which sends nobody
        # further, loses nobody to them. They are met from the next zone on.
        self.assertEqual(chances[0], 0.0)
        self.assertGreater(chances[1], 0.0)
        self.assertLess(chances[-1], 1.0)
        near = far = 0
        for seed in range(40):
            world = _settled(seed)
            _level(world, "sergio", 5)
            sergio = _out(world, None)
            near += len(world.raids.ahead(world, sergio, sergio.expedition))
            world = _settled(seed)
            _level(world, "sergio", 5)
            world.stock(next(iter(world.containers.values())), "water", 40, None)
            self.assertTrue(world.apply_command(PlanTripCommand("sergio", "crater", {"water": 14})).ok)
            sergio = world.residents["sergio"]
            world.expeditions.set_out(world, sergio, world.registries.jobs[SCAVENGER])
            trip = sergio.expedition
            ahead = trip.raids_at
            far += len(ahead)
            self.assertLessEqual(len(ahead), len(trip.route))
            self.assertEqual(ahead, sorted(ahead))
            self.assertTrue(all(trip.left_at < at < trip.turns_at for at in ahead), "on the way out")
            stages = [trip.stage_at((at - trip.left_at) / trip.out_minutes) for at in ahead]
            self.assertEqual(len(stages), len(set(stages)), "one zone, one band at most")
        self.assertEqual(near, 0, "left to themselves they keep to the forest, and meet nobody")
        self.assertGreater(far, 40, "a trip to the crater meets a band or two")

    def _zones(self):
        return list(BuiltInRegistries.load().combat.zones.values())

    def test_who_lies_in_wait_is_drawn_apart_and_is_the_same_whenever_it_is_asked(self) -> None:
        world = _settled()
        sergio = _out(world, None)
        before = world.rng.get_state()
        first = world.raids.ahead(world, sergio, sergio.expedition)
        self.assertEqual(world.raids.ahead(world, sergio, sergio.expedition), first)
        self.assertEqual(world.rng.get_state(), before, "it moves nothing else on")

    def test_whoever_has_turned_for_home_meets_nobody_new(self) -> None:
        world = _settled()
        sergio = _out(world, None)
        trip = sergio.expedition
        trip.raids_at = [trip.turns_at + 5]
        while world.clock.total_minutes < trip.turns_at + 10:
            world.step(1)
            _content(world)
        self.assertIsNone(trip.raid)
        self.assertEqual(trip.raids_at, [])


class MeetingTests(unittest.TestCase):
    """What to do about them is theirs to decide, and the player's to advise on."""

    def setUp(self) -> None:
        self.world = _settled()
        self.sergio = _out(self.world)
        self.since = len(self.world.event_log)

    def test_it_is_put_to_them_and_the_trip_stands_still_meanwhile(self) -> None:
        trip = _met(self.world, [["thug", 1]])
        self.assertIn(RAIDERS_MET, _types(self.world, self.since))
        decision = self.world.interventions.pending_for(self.world, "sergio")
        self.assertEqual(decision.kind, RAIDERS_MET)
        options = self.world.registries.decisions[RAIDERS_MET].options
        self.assertEqual([option.option_id for option in options], ["fight", "run", "pay", "neutral"])
        self.assertEqual((trip.raid.zone, trip.raid.due), ("forest", None))
        now = self.world.clock.total_minutes
        where, back = trip.distance(now), trip.returns_at
        for _ in range(10):
            self.world.step(1)
        later = self.world.clock.total_minutes
        self.assertAlmostEqual(trip.distance(later), where)
        self.assertEqual(trip.returns_at, back + 10, "all that was still to come is that much later")

    def test_told_to_pay_they_hand_over_what_they_carry_and_go_on(self) -> None:
        trip = _met(self.world, [["thug", 1]])
        trip.finds = 5
        cost = self.world.registries.combat.tuning.pay_per_raider
        self.world.registries.decisions[RAIDERS_MET].outcomes["pay"].score["bias"] = 9.0
        self.addCleanup(BuiltInRegistries.load)
        chosen = _advise(self.world, "pay")
        self.assertEqual(chosen, PAY)
        self.assertIsNone(trip.raid)
        self.assertEqual(trip.finds, 5 - cost)
        self.assertIn(RAID_OVER_EVENT, _types(self.world, self.since))
        self.assertTrue(self.sergio.away, "and they are still on their way")
        self.assertEqual(self.sergio.health, 100.0)

    def test_with_nothing_to_hand_over_paying_is_running(self) -> None:
        trip = _met(self.world, [["thug", 1]])
        trip.finds, trip.supplies = 0, {}
        self.world.raids.choose(self.world, self.sergio, PAY)
        over = [line for line in self.world.event_log[self.since:] if RAID_OVER_EVENT in line or RAID_FOUGHT_EVENT in line]
        self.assertEqual(len(over), 1)
        self.assertNotIn("dejan pasar", over[0])

    def test_nothing_is_handed_to_a_beast(self) -> None:
        trip = _met(self.world, [["monster", 3]])
        trip.finds = 50
        self.world.raids.choose(self.world, self.sergio, PAY)
        self.assertEqual(trip.finds, 50)

    def test_running_gets_them_home_or_into_the_fight(self) -> None:
        home = blows = 0
        for seed in range(24):
            world = _settled(seed)
            sergio = _out(world)
            trip = _met(world, [["thug", 1]])
            planned = trip.returns_at
            world.raids.choose(world, sergio, RUN)
            if trip.raid is None:
                home += 1
                self.assertLess(trip.returns_at, planned, "they turn round where they stand")
                self.assertEqual(trip.raids_at, [])
                self.assertEqual(sergio.health, 100.0)
            else:
                blows += 1
                self.assertIsNotNone(trip.raid.due, "caught, it comes to blows")
        self.assertGreater(home, 4)
        self.assertGreater(blows, 2)

    def test_if_the_question_is_dropped_they_do_as_they_are_and_do_not_stand_there_for_ever(self) -> None:
        trip = _met(self.world, [["thug", 1]])
        self.world.interventions.cancel_for(self.world, "sergio")
        self.assertIsNone(trip.raid.due)
        self.world.step(1)
        self.world.step(1)
        self.assertTrue(trip.raid is None or trip.raid.due is not None)
        _until_over(self.world)

    def test_left_alone_they_decide_by_themselves_when_the_time_to_advise_is_up(self) -> None:
        trip = _met(self.world, [["thug", 1]])
        window = self.world.registries.decisions[RAIDERS_MET].window_minutes
        for _ in range(window + 2):
            self.world.step(1)
        self.assertIsNone(self.world.interventions.pending_for(self.world, "sergio"))
        self.assertTrue(trip.raid is None or trip.raid.due is not None)


class FoughtAloneTests(unittest.TestCase):
    """Nobody watching, a fight waits a while and is then fought out by itself."""

    def _fight(self, foes: list[list], seed: int = 7, **ready):
        world = _settled(seed)
        for name, value in ready.items():
            world.attributes.give(world, world.residents["sergio"], {name: value})
        sergio = _out(world)
        trip = _met(world, foes)
        world.interventions.cancel_for(world, "sergio")
        world.raids.choose(world, sergio, FIGHT)
        return world, sergio, trip

    def test_it_waits_for_whoever_wants_to_see_it_and_then_goes_ahead(self) -> None:
        world, sergio, trip = self._fight([["thug", 1]])
        since = len(world.event_log)
        wait = world.registries.expeditions.raid_wait
        self.assertEqual(trip.raid.due, world.clock.total_minutes + wait)
        for _ in range(wait - 1):
            world.step(1)
        self.assertIsNotNone(trip.raid)
        self.assertEqual(sergio.health, 100.0)
        world.step(1)
        world.step(1)
        self.assertIsNone(sergio.expedition.raid if sergio.expedition else None)
        self.assertIn(RAID_OVER_EVENT, _types(world, since))

    def test_what_it_cost_them_is_an_injury_of_just_that_much(self) -> None:
        won = 0
        for seed in range(10):
            world, sergio, trip = self._fight([["thug", 1]], seed, strength=9, constitution=8)
            fight = world.raids.fight(world, sergio)
            fight.resolve()
            _until_over(world)
            if "sergio" not in world.residents or fight.outcome != WON:
                continue
            won += 1
            self.assertAlmostEqual(sergio.health, max(1.0, fight.hero.health), places=4, msg="the same fight, whoever asks for it")
            self.assertTrue(sergio.away, "and they go on from there with what they have left")
            carried = {item.definition_id for item in sergio.inventory.items}
            self.assertIn("scrap", carried, "what was taken from the fallen is on them")
        self.assertGreater(won, 5)

    def test_down_among_them_they_are_robbed_and_crawl_home_or_do_not_come_back(self) -> None:
        robbed = dead = 0
        for seed in range(12):
            world, sergio, trip = self._fight([["monster", 5], ["monster", 5], ["monster", 5]], seed)
            trip.finds, trip.supplies = 6, {"water": 3}
            planned = trip.returns_at
            since = len(world.event_log)
            _until_over(world)
            if "sergio" not in world.residents:
                dead += 1
                self.assertIn("death", _types(world, since))
                self.assertEqual(world.deaths[-1].resident_id, "sergio")
                continue
            if sergio.health >= 100.0 or trip.finds:
                continue
            robbed += 1
            self.assertEqual((trip.finds, trip.supplies), (0, {}))
            self.assertLess(trip.returns_at, planned + world.registries.expeditions.raid_wait + 60)
            self.assertGreaterEqual(sergio.health, 1.0, "alive, if only just")
            self.assertEqual(trip.raids_at, [])
        self.assertGreater(robbed + dead, 8, "three beasts are too many for anybody")
        self.assertGreater(dead, 0)

    def test_the_health_they_have_left_is_what_they_go_into_the_next_with(self) -> None:
        world, sergio, trip = self._fight([["cutter", 2]], 3, strength=9, constitution=9)
        _until_over(world)
        if "sergio" not in world.residents or not sergio.away:
            self.skipTest("this one did not go on")
        left = sergio.health
        self.assertLess(left, 100.0)
        trip.raid = Raid("forest", world.clock.total_minutes, [["thug", 1]])
        again = world.raids.fighter(world, sergio)
        self.assertAlmostEqual(again.health, left)
        self.assertLess(again.health, again.max_health, "nothing gives it back but what they carry to mend with")


class WhoFightsTests(unittest.TestCase):
    """Whoever goes into a fight goes in as they are, with what they carry."""

    def setUp(self) -> None:
        self.world = _settled()
        self.sergio = _out(self.world, None)
        self.data = self.world.registries.combat

    def test_they_are_as_capable_as_they_are_and_as_good_as_their_trade_has_made_them(self) -> None:
        world, sergio = self.world, self.sergio
        who = world.raids.fighter(world, sergio)
        self.assertEqual(set(who.attributes), set(self.data.attributes))
        for name in self.data.attributes:
            self.assertAlmostEqual(who.attributes[name], world.attributes.value(world, sergio, name))
        self.assertEqual((who.weapon.weapon_id, who.gun), (self.data.tuning.bare_hands, None))
        self.assertEqual(who.health, 100.0)
        _level(world, "sergio", 4)
        self.assertEqual(world.raids.fighter(world, sergio).level, 4)

    def test_they_fight_with_the_best_they_carry_for_the_hand_and_to_fire(self) -> None:
        world, sergio = self.world, self.sergio
        for item_id in ("rusty_knife", "baton", "pipe_pistol"):
            world.stock(sergio.inventory, item_id, 1, "sergio")
        who = world.raids.fighter(world, sergio)
        # The best is what does most harm in the time it takes: a knife, before a baton.
        self.assertEqual((who.weapon.weapon_id, who.gun.weapon_id, who.rounds), ("rusty_knife", "pipe_pistol", self.data.weapons["pipe_pistol"].ammo))
        next(item for item in sergio.inventory.items if item.definition_id == "rusty_knife").condition = 0.0
        self.assertEqual(world.raids.fighter(world, sergio).weapon.weapon_id, "baton", "nothing broken is fought with")
        for item in list(sergio.inventory.items):
            if item.definition_id != "pipe_pistol":
                sergio.inventory.items.remove(item)
        only = world.raids.fighter(world, sergio)
        self.assertEqual((only.weapon.weapon_id, only.gun), ("pipe_pistol", None), "with only something to fire, that is what is in the hand")
        carried = [weapon_id for weapon_id in self.data.weapons if weapon_id not in ("fists", "claws")]
        self.assertTrue(all(world.registries.items.find(weapon_id) is not None for weapon_id in carried), "every weapon is a thing of the game's")

    def test_what_they_were_already_without_they_go_in_without(self) -> None:
        world, sergio = self.world, self.sergio
        self.assertTrue(world.health.lose_limb(world, sergio, "hand_left"))
        who = world.raids.fighter(world, sergio)
        self.assertEqual(who.lost, ["hand_left"])
        self.assertTrue(who.staunched, "long since seen to")

    def test_medicine_is_what_they_mend_themselves_with_and_what_is_handed_over_goes_first(self) -> None:
        world, sergio = self.world, self.sergio
        self.assertEqual(world.raids.kits(world, sergio), [])
        self.assertTrue(world.expeditions.is_kit(world, "medicine"))
        self.assertFalse(world.expeditions.is_kit(world, "water"))
        sergio.expedition.supplies = {"water": 2, "medicine": 2}
        world.stock(sergio.inventory, "medicine", 1, "sergio")
        self.assertEqual(world.raids.kits(world, sergio), [("medicine", True), ("medicine", True), ("medicine", False)])
        sergio.expedition.raid = Raid("forest", world.clock.total_minutes, [["thug", 1]])
        self.assertEqual(world.raids.fight(world, sergio).medkits, 3)
        world.raids._use_kits(world, sergio, sergio.expedition, 2)
        self.assertEqual(sergio.expedition.supplies, {"water": 2})
        self.assertEqual(len(world.raids.kits(world, sergio)), 1)

    def test_medicine_can_be_handed_over_for_a_trip_and_comes_back_whole_if_it_is_not_used(self) -> None:
        world = _settled()
        _level(world, "sergio", 2)
        store = next(iter(world.containers.values()))
        world.stock(store, "water", 12, None)
        world.stock(store, "medicine", 3, None)
        self.assertIn("medicine", world.expeditions.on_hand(world))
        self.assertEqual(world.expeditions.worth(world, "medicine"), 0.0, "it gets nobody any further")
        result = world.apply_command(PlanTripCommand("sergio", "ruins", {"water": 4, "medicine": 2}))
        self.assertTrue(result.ok, result.message)
        sergio = _out(world, None)
        self.assertEqual(sergio.expedition.supplies.get("medicine"), 2)
        for _ in range(2000):
            world.step(1)
            _content(world)
            if not sergio.away:
                break
        self.assertFalse(sergio.away)
        carried = {item.definition_id: item.quantity for item in sergio.inventory.items if item.owner_id is None}
        self.assertEqual(carried.get("medicine"), 2)


class WatchedTests(unittest.TestCase):
    """A fight that has come to blows can be watched, and the player have a hand in it."""

    def setUp(self) -> None:
        self.world = _settled()
        self.sergio = _out(self.world)
        self.world.stock(self.sergio.inventory, "baton", 1, "sergio")
        self.world.stock(self.sergio.inventory, "pipe_pistol", 1, "sergio")
        self.trip = _met(self.world, [["thug", 1]])
        self.world.interventions.cancel_for(self.world, "sergio")

    def test_there_is_nothing_to_watch_until_it_has_come_to_blows(self) -> None:
        self.assertFalse(self.world.raids.waiting(self.world, "sergio"))
        self.assertIsNone(self.world.apply_command(WatchFightCommand("sergio")))
        self.assertIsNone(self.world.apply_command(WatchFightCommand("nobody")))
        self.assertEqual(self.world.apply_command(FightOnCommand("sergio", 1.0)), [])
        self.assertFalse(self.world.apply_command(FightActCommand("sergio", "heal")))

    def test_watched_it_goes_on_in_its_own_time_and_is_not_fought_out_meanwhile(self) -> None:
        world = self.world
        world.raids.choose(world, self.sergio, FIGHT)
        fight = world.apply_command(WatchFightCommand("sergio"))
        self.assertIsNotNone(fight)
        self.assertIs(world.apply_command(WatchFightCommand("sergio")), fight)
        self.assertEqual(fight.hero.name, "Sergio")
        self.assertEqual((fight.hero.weapon.weapon_id, fight.hero.gun.weapon_id), ("baton", "pipe_pistol"))
        for _ in range(world.registries.expeditions.raid_wait + 20):
            world.step(1)
        self.assertIsNotNone(self.trip.raid, "nobody fights it out behind whoever is watching")
        self.assertEqual(fight.seconds, 0.0, "nor does the settlement's time move it on")
        told = world.apply_command(FightOnCommand("sergio", 2.0))
        self.assertAlmostEqual(fight.seconds, 2.0, places=3)
        self.assertIsInstance(told, list)

    def test_the_player_has_a_hand_in_it(self) -> None:
        world = self.world
        world.raids.choose(world, self.sergio, FIGHT)
        fight = world.apply_command(WatchFightCommand("sergio"))
        self.assertEqual(fight.stance, BOTH)
        self.assertTrue(world.apply_command(FightActCommand("sergio", "stance", GUN)))
        self.assertEqual(fight.stance, GUN)
        self.assertFalse(world.apply_command(FightActCommand("sergio", "stance", "teeth")))
        self.assertFalse(world.apply_command(FightActCommand("sergio", "crit", 0.0)), "not before its measure is full")
        fight.crit = 1.0
        self.assertTrue(world.apply_command(FightActCommand("sergio", "crit", 0.0)))
        self.assertTrue(world.apply_command(FightActCommand("sergio", "hands_off", 1.0)))
        self.assertTrue(fight.hands_off)
        self.assertTrue(world.apply_command(FightActCommand("sergio", "target", 0)))
        self.assertFalse(world.apply_command(FightActCommand("sergio", "dance")))

    def test_played_to_its_end_what_is_left_of_it_is_the_settlements(self) -> None:
        world = self.world
        world.attributes.give(world, self.sergio, {"strength": 9, "constitution": 9})
        world.raids.choose(world, self.sergio, FIGHT)
        since = len(world.event_log)
        fight = world.apply_command(WatchFightCommand("sergio"))
        for _ in range(4000):
            world.apply_command(FightOnCommand("sergio", 0.05))
            if fight.outcome is not None:
                break
        self.assertIsNotNone(fight.outcome)
        self.assertNotIn("sergio", world.raids.live)
        self.assertIn(RAID_OVER_EVENT, _types(world, since))
        if "sergio" in world.residents:
            self.assertIsNone(self.sergio.expedition.raid)
            self.assertAlmostEqual(self.sergio.health, max(1.0, fight.hero.health), places=4)

    def test_walked_away_from_it_is_fought_out_from_where_it_stands(self) -> None:
        world = self.world
        world.raids.choose(world, self.sergio, FIGHT)
        fight = world.apply_command(WatchFightCommand("sergio"))
        world.apply_command(FightOnCommand("sergio", 1.0))
        self.assertIsNone(fight.outcome)
        world.apply_command(LeaveFightCommand("sergio"))
        self.assertIsNotNone(fight.outcome)
        self.assertEqual(world.raids.live, {})
        if "sergio" in world.residents:
            self.assertIsNone(self.sergio.expedition.raid)
        world.apply_command(LeaveFightCommand("sergio"))


class LimbTests(unittest.TestCase):
    """A limb can be lost at any joint, and whoever is without one is without all that was within it."""

    def setUp(self) -> None:
        self.world = _settled()
        self.sergio = self.world.residents["sergio"]
        self.health = self.world.health

    def test_every_part_a_fight_takes_off_is_one_somebody_can_be_without(self) -> None:
        registries = self.world.registries
        tuning = registries.combat.tuning
        parts = {part for limb in (*tuning.arms, *tuning.legs) for part in limb}
        self.assertEqual(parts, set(registries.limbs))
        self.assertEqual(registries.limbs["hand_left"].within, "forearm_left")
        self.assertEqual(registries.limbs["forearm_left"].within, "arm_left")
        self.assertIsNone(registries.limbs["arm_left"].within)
        self.assertGreater(registries.limbs["hand_left"].work_pace, registries.limbs["arm_left"].work_pace, "less is less of a loss")
        self.assertGreater(registries.limbs["foot_left"].walk_pace, registries.limbs["leg_left"].walk_pace)
        self.assertGreater(registries.limbs["hand_left"].odds, registries.limbs["arm_left"].odds)

    def test_lost_nearer_the_trunk_what_was_lost_further_out_is_no_longer_told_apart(self) -> None:
        world, sergio, health = self.world, self.sergio, self.health
        self.assertTrue(health.lose_limb(world, sergio, "hand_left"))
        self.assertFalse(health.lose_limb(world, sergio, "hand_left"))
        self.assertTrue(health.has_limb(world, sergio, "forearm_left"))
        whole = health.work_pace(world, sergio)
        self.assertTrue(health.lose_limb(world, sergio, "arm_left"))
        self.assertEqual(sergio.lost_limbs, ["arm_left"])
        self.assertFalse(health.has_limb(world, sergio, "hand_left"))
        self.assertFalse(health.lose_limb(world, sergio, "forearm_left"), "there is none to lose")
        self.assertLess(health.work_pace(world, sergio), whole)
        self.assertFalse(health.lose_limb(world, sergio, "tail"))

    def test_a_fight_leaves_just_what_it_cost_and_takes_off_just_what_it_took(self) -> None:
        world, sergio, health = self.world, self.sergio, self.health
        since = len(world.event_log)
        health.fought(world, sergio, 30.0, "cut", "toparse con saqueadores", ["foot_right"])
        self.assertAlmostEqual(sergio.health, 70.0)
        self.assertEqual(sergio.lost_limbs, ["foot_right"])
        self.assertIn("limb_lost", _types(world, since))
        health.fought(world, sergio, 500.0, "bruise", "toparse con saqueadores", [])
        self.assertAlmostEqual(sergio.health, 1.0, msg="it kills nobody by itself")
        self.assertIn("sergio", world.residents)

    def test_a_cut_on_the_map_takes_the_smaller_parts_sooner_and_nothing_twice(self) -> None:
        world, health = self.world, self.health
        cut = world.registries.injuries["cut"]
        taken: dict[str, int] = {}
        for _ in range(400):
            sergio = self.sergio
            sergio.lost_limbs.clear()
            limb = health._lose_limb(world, sergio, cut.severs_from + 50.0, cut)
            if limb is not None:
                taken[limb.limb_id.split("_")[0]] = taken.get(limb.limb_id.split("_")[0], 0) + 1
        self.assertGreater(taken["hand"] + taken["foot"], (taken["arm"] + taken["leg"]) * 2)
        sergio = self.sergio
        sergio.lost_limbs[:] = ["arm_left", "arm_right", "leg_left"]
        for _ in range(60):
            limb = health._lose_limb(world, sergio, cut.severs_from + 50.0, cut)
            if limb is not None:
                self.assertIn(limb.limb_id, ("leg_right", "shin_right", "foot_right"))
                sergio.lost_limbs[:] = ["arm_left", "arm_right", "leg_left"]


class HurtAtHomeTests(unittest.TestCase):
    """Somebody as badly hurt as a fight leaves them gets through it at home: nobody had
    come back that hurt before, and those who did wore themselves out or died of thirst."""

    def _hurt(self, severity: float = 75.0) -> tuple[SimulationWorld, object]:
        world = SimulationWorld.demo_world(seed=7)
        world.relationships.clear()
        raul = world.residents["raul"]
        raul.injuries = [Injury("cut", severity)]
        raul.job_id = None
        return world, raul

    def test_parched_and_starving_they_drink_and_eat_before_they_keep_to_a_bed(self) -> None:
        world, raul = self._hurt()
        raul.needs = Needs(hunger=96, thirst=96, tiredness=0, social=0, stress=0)
        rested = 0
        for _ in range(8 * 60):
            world.step(1)
            rested += raul.current_action == "rest"
        self.assertIn("raul", world.residents, "nobody dies of thirst for wanting a bed")
        # They go for it before it hurts, and back to bed between one time and the next.
        self.assertLess(raul.needs.thirst, URGENT_NEED)
        self.assertLess(raul.needs.hunger, URGENT_NEED)
        self.assertGreater(rested, 60, "and then they keep to it")
        self.assertNotIn("dehydration", [injury.kind for injury in raul.injuries])

    def test_worn_out_they_leave_the_bed_they_mend_in_for_one_to_sleep_in(self) -> None:
        world, raul = self._hurt(60.0)
        raul.needs = Needs(hunger=0, thirst=0, tiredness=70, social=0, stress=0)
        raul.x, raul.y = 27, 22
        raul.activity = Activity("rest", "clinic_bed_1", minutes_left=10_000, using=True)
        slept = mended = 0
        for _ in range(14 * 60):
            world.step(1)
            raul.needs.hunger = raul.needs.thirst = 0.0
            self.assertLess(raul.needs.tiredness, 100.0, world.clock.label)
            slept += raul.current_action == "sleep"
            mended += raul.activity is not None and raul.activity.action == "rest"
        self.assertGreater(slept, 120, "they went and slept, and did not lie there wearing themselves out")
        self.assertGreater(mended, 60, "and kept to the other bed besides")


class KeptTests(unittest.TestCase):
    """Raiders in the way of a trip are kept with it; the fight itself is not."""

    def test_raiders_in_the_way_come_back_as_they_were_and_end_as_they_would_have(self) -> None:
        world = _settled()
        sergio = _out(world)
        trip = _met(world, [["cutter", 2], ["thug", 1]])
        trip.raids_at = [trip.turns_at - 1]
        world.interventions.cancel_for(world, "sergio")
        world.raids.choose(world, sergio, FIGHT)
        manager = SaveManager()
        data = json.loads(json.dumps(manager.to_data(world)))
        again = manager.from_data(data)
        back = again.residents["sergio"].expedition
        self.assertEqual((back.raid.zone, back.raid.met_at, back.raid.foes, back.raid.due), (trip.raid.zone, trip.raid.met_at, trip.raid.foes, trip.raid.due))
        self.assertEqual(back.raids_at, trip.raids_at)
        ends = []
        for each in (world, again):
            fight = each.raids.fight(each, each.residents["sergio"])
            fight.resolve()
            ends.append((fight.outcome, round(fight.seconds, 3), round(fight.hero.health, 3)))
        self.assertEqual(ends[0], ends[1])

    def test_a_fight_being_watched_is_not_kept_and_starts_again(self) -> None:
        world = _settled()
        sergio = _out(world)
        _met(world, [["thug", 1]])
        world.interventions.cancel_for(world, "sergio")
        world.raids.choose(world, sergio, FIGHT)
        world.apply_command(WatchFightCommand("sergio"))
        world.apply_command(FightOnCommand("sergio", 1.5))
        again = SaveManager().from_data(json.loads(json.dumps(SaveManager().to_data(world))))
        self.assertEqual(again.raids.live, {})
        self.assertTrue(again.raids.waiting(again, "sergio"))
        self.assertEqual(again.apply_command(WatchFightCommand("sergio")).seconds, 0.0)

    def test_a_trip_from_before_there_were_raiders_has_none(self) -> None:
        world = _settled()
        _out(world, None)
        data = json.loads(json.dumps(SaveManager().to_data(world)))
        trip = next(each for each in data["residents"] if each["id"] == "sergio")["expedition"]
        del trip["raids_at"], trip["raid"]
        back = SaveManager().from_data(data).residents["sergio"].expedition
        self.assertEqual((back.raids_at, back.raid), ([], None))


if __name__ == "__main__":
    unittest.main()
