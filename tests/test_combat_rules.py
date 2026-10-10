import copy
import json
import unittest

from simulation.rng import SimulationRNG
from simulation.combat.encounter import FIGHT, PAY, RUN, aftermath, decide_alone, hero, meet, payable, price, raider, raiders
from simulation.combat.model import DATA_PATH, combat_from_data, load_combat
from simulation.combat.rules import (
    CRIT_READY,
    DODGED,
    DOWN,
    ENDED,
    FLED,
    FLEE_FAILED,
    FLOORED,
    HEALED,
    HIT,
    LOST,
    REELED,
    SEVERED,
    SHOVED,
    BLED,
    BOTH,
    EMPTY,
    GUN,
    HAND,
    HELD,
    THROWN_OFF,
    WON,
    Fight,
    bleeding,
    can_strike,
    foe_crit_chance,
    foe_sever_chance,
    gone,
    of_leg,
    sever_chance,
    sever_odds,
    severable,
    stumps,
    crit_times,
    dodge_chance,
    interval,
    power,
    steadiness,
    walk_speed,
)

EVEN = {"strength": 5, "constitution": 5, "dexterity": 5, "mind": 5, "senses": 5}


def _with(**changed: float) -> dict[str, float]:
    return {**EVEN, **changed}


class DataTests(unittest.TestCase):
    def setUp(self) -> None:
        self.data = load_combat()
        self.raw = json.loads(DATA_PATH.read_text(encoding="utf-8"))

    def test_each_kind_of_weapon_goes_by_its_own_two_attributes(self) -> None:
        kinds = {kind_id: set(kind.scales_with) for kind_id, kind in self.data.kinds.items()}
        self.assertEqual(
            kinds,
            {"melee": {"strength", "dexterity"}, "ranged": {"dexterity", "senses"}, "energy": {"senses", "mind"}},
        )
        for weapon in self.data.weapons.values():
            self.assertLessEqual(set(weapon.scales), kinds[weapon.kind], weapon.weapon_id)
            self.assertAlmostEqual(sum(weapon.scales.values()), 1.0, places=5, msg=weapon.weapon_id)
        # Which of the two, and how much of each, depends on the weapon.
        self.assertGreater(self.data.weapons["baton"].scales["strength"], self.data.weapons["baton"].scales["dexterity"])
        self.assertGreater(self.data.weapons["rusty_knife"].scales["dexterity"], self.data.weapons["rusty_knife"].scales["strength"])

    def test_a_weapon_that_goes_by_what_its_kind_does_not_is_rejected(self) -> None:
        bad = copy.deepcopy(self.raw)
        bad["weapons"]["baton"]["scales"] = {"mind": 1.0}
        with self.assertRaisesRegex(ValueError, "goes by something"):
            combat_from_data(bad)
        bad = copy.deepcopy(self.raw)
        bad["weapons"]["baton"]["kind"] = "thrown"
        with self.assertRaisesRegex(ValueError, "kind there is not"):
            combat_from_data(bad)
        bad = copy.deepcopy(self.raw)
        bad["raiders"]["thug"]["weapons"] = ["spoon"]
        with self.assertRaisesRegex(ValueError, "weapons there are"):
            combat_from_data(bad)
        bad = copy.deepcopy(self.raw)
        bad["tuning"]["no_such_figure"] = 1
        with self.assertRaisesRegex(ValueError, "nothing goes by"):
            combat_from_data(bad)

    def test_there_is_a_zone_for_each_of_the_five_and_they_get_worse(self) -> None:
        zones = list(self.data.zones.values())
        self.assertEqual([zone.zone_id for zone in zones], ["forest", "ruins", "summit", "plant", "crater"])
        for nearer, further in zip(zones, zones[1:]):
            self.assertGreaterEqual(further.levels[0], nearer.levels[0])
            self.assertGreaterEqual(further.levels[1], nearer.levels[1])
            self.assertGreaterEqual(further.most, nearer.most)


class ScalingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.data = load_combat()
        self.tuning = self.data.tuning

    def _power(self, weapon_id: str, **attributes: float) -> float:
        return power(hero(self.data, "X", _with(**attributes), weapon_id), self.tuning)

    def test_in_the_middle_of_everything_a_weapon_does_its_own_harm(self) -> None:
        for weapon_id in self.data.weapons:
            self.assertAlmostEqual(self._power(weapon_id), 1.0, places=6)

    def test_close_quarters_go_by_strength_and_dexterity_by_the_weapon(self) -> None:
        self.assertGreater(self._power("baton", strength=9), self._power("baton", dexterity=9))
        self.assertGreater(self._power("rusty_knife", dexterity=9), self._power("rusty_knife", strength=9))
        self.assertAlmostEqual(self._power("sledge", dexterity=10), 1.0, places=6, msg="a maul is all arm")
        self.assertAlmostEqual(self._power("baton", mind=10, senses=10), 1.0, places=6)

    def test_at_a_distance_goes_by_dexterity_and_senses_and_energy_by_senses_and_mind(self) -> None:
        self.assertGreater(self._power("rifle", senses=9), self._power("rifle", dexterity=9))
        self.assertGreater(self._power("rifle", dexterity=9), 1.0)
        self.assertAlmostEqual(self._power("rifle", strength=10, mind=10), 1.0, places=6)
        self.assertGreater(self._power("laser", mind=9), self._power("laser", senses=9))
        self.assertGreater(self._power("laser", senses=9), 1.0)
        self.assertAlmostEqual(self._power("laser", strength=10, dexterity=10), 1.0, places=6)

    def test_a_point_is_worth_what_the_tuning_says_and_nothing_does_no_harm(self) -> None:
        self.assertAlmostEqual(self._power("sledge", strength=6), 1.0 + self.tuning.damage_per_point, places=6)
        self.assertEqual(self._power("sledge", strength=1), max(self.tuning.least_damage, 1.0 - 4 * self.tuning.damage_per_point))

    def test_quick_hands_strike_sooner_and_quick_feet_get_out_of_the_way(self) -> None:
        slow, quick = hero(self.data, "X", _with(dexterity=2), "baton"), hero(self.data, "X", _with(dexterity=9), "baton")
        self.assertLess(interval(quick, self.tuning), interval(slow, self.tuning))
        self.assertAlmostEqual(interval(hero(self.data, "X", EVEN, "baton"), self.tuning), self.data.weapons["baton"].seconds)
        self.assertGreater(dodge_chance(quick, self.tuning), dodge_chance(slow, self.tuning))
        self.assertEqual(dodge_chance(hero(self.data, "X", _with(dexterity=1), "baton"), self.tuning), 0.0)
        self.assertLessEqual(dodge_chance(hero(self.data, "X", _with(dexterity=50), "baton"), self.tuning), self.tuning.most_dodge)


class FightTests(unittest.TestCase):
    def setUp(self) -> None:
        self.data = load_combat()

    def _fight(self, seed: int = 3, foes: int = 2, medkits: int = 0, weapon: str = "baton", **attributes: float) -> Fight:
        rng = SimulationRNG(seed)
        band = [raider(self.data, self.data.raiders["thug"], 1, rng) for _ in range(foes)]
        return Fight(self.data, hero(self.data, "Sergio", _with(**attributes), weapon), band, rng, medkits)

    def test_left_alone_it_goes_to_its_end(self) -> None:
        for seed in range(30):
            fight = self._fight(seed)
            self.assertIn(fight.resolve(), (WON, LOST, FLED))
            self.assertLess(fight.seconds, 120.0)
            self.assertEqual(fight.outcome == WON, not fight.standing())
            self.assertEqual(fight.outcome == LOST, fight.hero.down)

    def test_the_same_seed_and_the_same_presses_are_the_same_fight(self) -> None:
        def told(seed: int, press: bool) -> list:
            fight = self._fight(seed)
            events = []
            for tick in range(400):
                if press and tick == 10:
                    # Whoever they would not have picked themselves.
                    fight.choose(next(index for index in fight.standing() if index != fight.target()))
                events += [(event.kind, event.by, event.to, round(event.amount, 6)) for event in fight.update(0.1)]
            return events

        self.assertEqual(told(5, False), told(5, False))
        self.assertNotEqual(told(5, False), told(6, False))
        self.assertNotEqual(told(5, False), told(5, True))

    def test_everybody_strikes_at_once_each_at_their_own_pace(self) -> None:
        fight = self._fight(foes=3)
        events = []
        for _ in range(60):
            events += fight.update(0.1)
        strikers = {event.by for event in events if event.kind in (HIT, DODGED)}
        self.assertEqual(strikers, {0, 1, 2, 3})
        self.assertTrue(all(event.to == 0 for event in events if event.by != 0 and event.kind in (HIT, DODGED)))

    def test_several_raiders_get_in_one_anothers_way(self) -> None:
        alone, three = self._fight(foes=1), self._fight(foes=3)
        self.assertAlmostEqual(three._pace(three.foes[0]) / interval(three.foes[0], self.data.tuning), 1.0 + 2 * self.data.tuning.many_slower)
        self.assertAlmostEqual(alone._pace(alone.foes[0]), interval(alone.foes[0], self.data.tuning))
        self.assertAlmostEqual(three._pace(three.hero), interval(three.hero, self.data.tuning), msg="the hero is as quick as ever")

    def test_untold_they_hit_whoever_is_nearest_going_down_and_told_whoever_they_are_told(self) -> None:
        fight = self._fight(foes=3)
        fight.foes[2].health = 5.0
        self.assertEqual(fight.target(), 2)
        self.assertTrue(fight.choose(0))
        self.assertEqual(fight.target(), 0)
        hits = []
        while fight.foes[0].health > 0 and fight.outcome is None:
            hits += [event.to for event in fight.update(0.1) if event.by == 0 and event.kind in (HIT, DODGED)]
        self.assertEqual(set(hits), {1}, "every blow at whoever was said, until they are down")
        self.assertEqual(fight.target(), 2, "and then back to whoever they would pick")
        self.assertFalse(fight.choose(0), "nobody is told to hit the fallen")
        self.assertTrue(fight.choose(None))

    def test_the_measure_of_a_telling_blow_fills_with_blows_and_with_time(self) -> None:
        fight = self._fight(foes=1)
        fight.foes[0].health = fight.foes[0].max_health = 100000.0
        fight.hero.health = fight.hero.max_health = 100000.0
        self.assertFalse(fight.land_crit(0.0), "not before it is full")
        events = []
        while not fight.crit_ready:
            before = fight.crit
            events += fight.update(0.1)
            self.assertGreaterEqual(fight.crit, before)
        self.assertEqual([event.kind for event in events].count(CRIT_READY), 1)
        self.assertLess(fight.seconds, 1.0 / self.data.tuning.crit_per_second, "blows fill it sooner than time alone")
        # Full, it waits for as long as nobody stops the mark, and is said once.
        waiting = fight.update(5.0)
        self.assertNotIn(CRIT_READY, [event.kind for event in waiting])
        self.assertTrue(fight.crit_ready)

    def test_a_telling_blow_lands_at_once_tells_by_how_near_the_middle_and_is_never_dodged(self) -> None:
        tuning = self.data.tuning
        self.assertEqual(crit_times(tuning, 0.0)[0], 3.0)
        self.assertEqual(crit_times(tuning, -0.05)[0], 3.0)
        self.assertEqual(crit_times(tuning, 0.2)[0], 2.0)
        self.assertEqual(crit_times(tuning, 0.9)[0], 1.25)
        self.assertEqual(crit_times(tuning, 7.0)[0], 1.25)
        for seed in range(12):
            fight = self._fight(seed, foes=1)
            fight.foes[0].attributes["dexterity"] = 10.0
            fight.foes[0].health = fight.foes[0].max_health = 100000.0
            fight.hero.health = fight.hero.max_health = 100000.0
            fight.crit = 1.0
            # Right up to them, as a blow with what is in the hand has to be.
            fight.foes[0].at = fight.hero.at + self.data.tuning.reach
            self.assertTrue(fight.land_crit(0.0))
            self.assertEqual(fight.crit, 0.0)
            told = [event for event in fight.update(0.05) if event.by == 0 and event.kind == HIT]
            self.assertEqual([(event.kind, event.times, event.said) for event in told], [(HIT, 3.0, "¡PERFECTO!")])
            low, high = fight.hero.weapon.damage
            worth = power(fight.hero, tuning)
            self.assertTrue(low * worth * 3 - 1e-6 <= told[0].amount <= high * worth * 3 + 1e-6)
            self.assertLess(fight.crit, tuning.crit_per_hit, "a telling blow does not fill the next")

    def test_a_medkit_mends_and_they_see_to_themselves_when_badly_off(self) -> None:
        fight = self._fight(medkits=1)
        self.assertFalse(fight.heal(), "no use to somebody who is whole")
        fight.hero.health = 50.0
        self.assertTrue(fight.heal())
        self.assertEqual((fight.hero.health, fight.medkits), (50.0 + self.data.tuning.medkit, 0))
        self.assertFalse(fight.heal(), "there are no more")
        fight = self._fight(medkits=2)
        fight.hero.health = 20.0
        kinds = []
        for _ in range(40):
            kinds += [event.kind for event in fight.update(0.1)]
            if HEALED in kinds:
                break
        self.assertIn(HEALED, kinds)
        self.assertEqual(fight.medkits, 1)

    def test_running_for_it_may_not_come_off_and_costs_them_if_it_does_not(self) -> None:
        tuning = self.data.tuning
        fight = self._fight(foes=3)
        self.assertAlmostEqual(fight.flee_chance(), tuning.flee - 2 * tuning.flee_per_foe)
        self.assertAlmostEqual(fight.flee_chance(before=True), tuning.flee - 2 * tuning.flee_per_foe + tuning.flee_before)
        self.assertGreater(self._fight(foes=1, dexterity=9).flee_chance(), self._fight(foes=1, dexterity=2).flee_chance())
        self.assertTrue(0.05 <= self._fight(foes=3, dexterity=1).flee_chance() <= self._fight(foes=1, dexterity=99).flee_chance() <= 0.95)
        got_away = stumbled = 0
        for seed in range(200):
            fight = self._fight(seed, foes=1)
            wait = fight.hero.wait
            if fight.flee():
                got_away += 1
                self.assertEqual(fight.outcome, FLED)
                self.assertFalse(fight.flee(), "it is over")
            else:
                stumbled += 1
                self.assertIsNone(fight.outcome)
                self.assertAlmostEqual(fight.hero.wait, wait + tuning.flee_stumble_seconds)
                self.assertIn(FLEE_FAILED, [event.kind for event in fight.update(0.0)])
        self.assertTrue(70 < got_away < 130, got_away)
        self.assertEqual(got_away + stumbled, 200)

    def test_watched_they_stand_and_fight_and_unwatched_they_run_when_all_is_lost(self) -> None:
        fled = 0
        for seed in range(40):
            watched = self._fight(seed, foes=3)
            watched.hero.health = 10.0
            while watched.outcome is None:
                watched.update(0.5)
            self.assertEqual(watched.outcome, LOST, "whoever watches says when to run")
            alone = self._fight(seed, foes=3)
            alone.hero.health = 10.0
            fled += alone.resolve() == FLED
        self.assertGreater(fled, 5)

    def test_it_ends_when_the_last_raider_or_the_hero_goes_down(self) -> None:
        fight = self._fight(foes=2, strength=10)
        for foe in fight.foes:
            foe.health = 1.0
            foe.attributes["dexterity"] = 1.0
        events = []
        while fight.outcome is None:
            events += fight.update(0.1)
        self.assertEqual(fight.outcome, WON)
        self.assertEqual([event.kind for event in events].count(DOWN), 2)
        self.assertEqual((events[-1].kind, events[-1].said), (ENDED, WON))
        self.assertEqual(fight.update(5.0), [], "nothing more happens")
        self.assertFalse(fight.heal() or fight.land_crit(0.0) or fight.flee())


class GroundTests(unittest.TestCase):
    """There is ground between them: a weapon for the hand has to be carried right up to whoever it is used on."""

    def setUp(self) -> None:
        self.data = load_combat()
        self.tuning = self.data.tuning

    def _fight(self, seed: int = 3, weapon: str = "baton", gun: str | None = None, sort: str = "thug", level: int = 1, foes: int = 1, **attributes: float) -> Fight:
        rng = SimulationRNG(seed)
        band = [raider(self.data, self.data.raiders[sort], level, rng) for _ in range(foes)]
        return Fight(self.data, hero(self.data, "Sergio", _with(**attributes), weapon, gun_id=gun), band, rng)

    def test_they_come_on_one_another_with_ground_between(self) -> None:
        fight = self._fight(foes=3)
        low, high = self.tuning.start_gap
        self.assertEqual(fight.hero.at, 0.0)
        self.assertTrue(low <= fight.foes[0].at <= high)
        self.assertEqual([round(foe.at - fight.foes[0].at, 6) for foe in fight.foes], [0.0, self.tuning.rank_gap, 2 * self.tuning.rank_gap])
        self.assertFalse(fight.in_reach(fight.hero, fight.foes[0]))
        self.assertIsNone(fight.weapon_for(fight.hero, fight.foes[0]), "nothing to hit them with from here")

    def test_at_close_quarters_nobody_is_struck_until_they_are_right_up_to_one_another(self) -> None:
        fight = self._fight()
        events, struck_at = [], None
        while struck_at is None and fight.seconds < 20:
            before = fight.gap(fight.hero, fight.foes[0])
            told = fight.update(0.05)
            events += told
            if any(event.kind in (HIT, DODGED) for event in told):
                struck_at = before
            else:
                self.assertLessEqual(fight.gap(fight.hero, fight.foes[0]), before + 1e-9, "they only close")
        self.assertIsNotNone(struck_at)
        self.assertLessEqual(struck_at, self.tuning.reach + walk_speed(fight.hero, self.tuning) * 0.11)
        self.assertGreater(fight.seconds, 1.0, "it takes them a moment to get there")
        self.assertGreaterEqual(fight.gap(fight.hero, fight.foes[0]), self.tuning.reach - 1e-6, "and they stop right up to them, not on them")

    def test_quick_feet_close_sooner(self) -> None:
        self.assertGreater(walk_speed(hero(self.data, "X", _with(dexterity=9), "baton"), self.tuning), walk_speed(hero(self.data, "X", _with(dexterity=2), "baton"), self.tuning))
        self.assertAlmostEqual(walk_speed(hero(self.data, "X", EVEN, "baton"), self.tuning), self.tuning.walk)

    def test_what_is_fired_is_fired_from_where_they_stand(self) -> None:
        fight = self._fight(weapon="rifle", sort="gunner", level=2)
        fight.hero.health = fight.hero.max_health = 100000.0
        fight.foes[0].health = fight.foes[0].max_health = 100000.0
        events = []
        for _ in range(120):
            before = fight.gap(fight.hero, fight.foes[0])
            events += fight.update(0.05)
            self.assertGreaterEqual(fight.gap(fight.hero, fight.foes[0]), before - 1e-9, "nobody with something to fire walks up to anybody")
        self.assertTrue(any(event.by == 0 for event in events if event.kind in (HIT, DODGED)))
        self.assertTrue(any(event.by == 1 for event in events if event.kind in (HIT, DODGED)))
        self.assertTrue(all(event.weapon for event in events if event.kind in (HIT, DODGED, REELED, FLOORED)))
        self.assertGreaterEqual(fight.gap(fight.hero, fight.foes[0]), self.tuning.start_gap[0])

    def test_with_both_they_fire_while_there_is_ground_between_and_strike_once_there_is_none(self) -> None:
        fight = self._fight(gun="pipe_pistol")
        fight.foes[0].health = fight.foes[0].max_health = 100000.0
        fight.hero.health = fight.hero.max_health = 100000.0
        fight.hero.rounds = 1000
        used = []
        shoved = 0
        for _ in range(400):
            at = fight.hero.at
            for event in fight.update(0.05):
                if event.by == 0 and event.kind in (HIT, DODGED):
                    used.append((event.weapon, fight.in_reach(fight.hero, fight.foes[0])))
                shoved += event.by == 0 and event.kind == SHOVED
            self.assertLessEqual(fight.hero.at, at + 1e-9, "they stand their ground and let them come")
        weapons = [weapon for weapon, _ in used]
        self.assertEqual(weapons[0], "pipe_pistol", "they open with what they fire")
        self.assertIn("baton", weapons)
        self.assertGreater(shoved, 3, "and with somebody on top of them they shove, to get room to fire")
        first = weapons.index("baton")
        self.assertTrue(all(weapon == "pipe_pistol" for weapon in weapons[:first]))
        # A blow that sends them back gives room for another shot.
        self.assertEqual(fight.weapon_for(fight.hero, fight.foes[0]).weapon_id, "baton" if fight.in_reach(fight.hero, fight.foes[0]) else "pipe_pistol")

    def test_only_something_to_fire_is_carried_besides_and_only_besides_a_weapon_for_the_hand(self) -> None:
        with self.assertRaisesRegex(ValueError, "something to fire"):
            hero(self.data, "X", EVEN, "baton", gun_id="rusty_knife")
        with self.assertRaisesRegex(ValueError, "something to fire"):
            hero(self.data, "X", EVEN, "rifle", gun_id="pipe_pistol")
        both = hero(self.data, "X", EVEN, "baton", gun_id="arc_thrower")
        self.assertEqual((both.weapon.weapon_id, both.gun.weapon_id), ("baton", "arc_thrower"))
        self.assertGreater(power(hero(self.data, "X", _with(senses=9), "baton", gun_id="rifle"), self.tuning, self.data.weapons["rifle"]), 1.0)

    def test_a_hard_blow_makes_them_reel_and_a_harder_one_puts_them_on_the_ground(self) -> None:
        reeled = floored = 0
        for seed in range(60):
            fight = self._fight(seed, weapon="sledge", strength=10)
            foe = fight.foes[0]
            foe.attributes["dexterity"] = 1.0
            foe.at = self.tuning.reach
            foe.health = foe.max_health = 70.0
            fight.hero.wait = 0.0
            at, wait = foe.at, foe.wait
            told = [event for event in fight.update(0.05) if event.by == 0]
            kinds = [event.kind for event in told]
            self.assertEqual(kinds[0], HIT)
            hit = told[0]
            landed = hit.amount / foe.max_health / steadiness(foe, self.tuning)
            if landed >= self.tuning.floors_at:
                floored += 1
                self.assertIn(FLOORED, kinds)
                self.assertGreater(foe.floored, 0.0)
                self.assertAlmostEqual(foe.at, at + self.tuning.floored_push)
            elif landed >= self.tuning.reels_at:
                reeled += 1
                self.assertIn(REELED, kinds)
                self.assertGreater(foe.at, at, "sent back a little, and already on their way in again")
                self.assertLessEqual(foe.at, at + self.tuning.reel_push + 1e-9)
                self.assertGreater(foe.wait, wait)
            else:
                self.assertNotIn(REELED, kinds)
        self.assertGreater(floored, 10)
        self.assertGreater(reeled, 0)

    def test_on_the_ground_they_do_nothing_and_get_out_of_the_way_of_nothing(self) -> None:
        fight = self._fight(weapon="fists")
        foe = fight.foes[0]
        foe.attributes["dexterity"] = 10.0
        foe.at, foe.health, foe.max_health = self.tuning.reach, 100000.0, 100000.0
        fight.hero.health = fight.hero.max_health = 100000.0
        foe.floored = 3.0
        events = []
        for _ in range(40):
            events += fight.update(0.05)
        self.assertFalse([event for event in events if event.by == 1], "whoever is down strikes nobody")
        self.assertFalse([event for event in events if event.kind == DODGED and event.to == 1])
        self.assertTrue([event for event in events if event.kind == HIT and event.to == 1])
        self.assertAlmostEqual(foe.floored, 1.0, places=5)
        for _ in range(60):
            events += fight.update(0.05)
        self.assertEqual(foe.floored, 0.0)
        self.assertTrue([event for event in events if event.by == 1], "and up again they are at it again")

    def test_a_telling_blow_at_close_quarters_floors_whoever_it_lands_on(self) -> None:
        fight = self._fight(weapon="fists")
        foe = fight.foes[0]
        foe.at, foe.health, foe.max_health = self.tuning.reach, 100000.0, 100000.0
        fight.crit = 1.0
        fight.land_crit(0.2)
        kinds = [event.kind for event in fight.update(0.05) if event.by == 0]
        self.assertEqual(kinds, [HIT, FLOORED])
        self.assertGreater(steadiness(hero(self.data, "X", _with(constitution=9), "fists"), self.tuning), 1.0)

    def test_the_hero_can_be_put_on_the_ground_too(self) -> None:
        down = 0
        for seed in range(40):
            fight = self._fight(seed, weapon="fists", sort="thug", level=5, foes=2, constitution=2)
            for foe in fight.foes:
                foe.health = foe.max_health = 100000.0
            events = []
            for _ in range(600):
                # Kept on their feet for as long as it takes: it is the falling that is looked at.
                fight.hero.health = fight.hero.max_health
                events += fight.update(0.05)
            down += any(event.kind == FLOORED and event.to == 0 for event in events)
        self.assertGreater(down, 5)


class ShovingTests(unittest.TestCase):
    """Right up to somebody, they can be shoved: next to no harm, but they go back and may go down."""

    def setUp(self) -> None:
        self.data = load_combat()
        self.tuning = self.data.tuning

    def _fight(self, seed: int = 3, weapon: str = "baton", gun: str | None = None, level: int = 1, **attributes: float) -> Fight:
        rng = SimulationRNG(seed)
        fight = Fight(self.data, hero(self.data, "Sergio", _with(**attributes), weapon, gun_id=gun), [raider(self.data, self.data.raiders["thug"], level, rng)], rng)
        for fighter in fight.fighters:
            fighter.health = fighter.max_health = 100000.0
        return fight

    def _close(self, fight: Fight) -> None:
        fight.foes[0].at = fight.hero.at + self.tuning.reach
        fight.foes[0].wait = 99.0

    def test_nobody_is_shoved_from_where_they_cannot_be_reached(self) -> None:
        fight = self._fight()
        self.assertFalse(fight.can_shove())
        self.assertFalse(fight.shove())
        self._close(fight)
        self.assertTrue(fight.can_shove())

    def test_a_shove_sends_them_back_does_next_to_no_harm_and_has_to_be_got_over(self) -> None:
        went_down = 0
        for seed in range(80):
            fight = self._fight(seed)
            self._close(fight)
            foe = fight.foes[0]
            at, health = foe.at, foe.health
            self.assertTrue(fight.shove())
            told = [event for event in fight.update(0.05) if event.by == 0]
            kinds = [event.kind for event in told]
            self.assertEqual(kinds[0], SHOVED)
            self.assertIn(kinds[1], (REELED, FLOORED))
            self.assertEqual(len(kinds), 2, "a shove is all they do with that turn")
            if kinds[1] == FLOORED:
                self.assertAlmostEqual(foe.at - at, self.tuning.shove_push, places=5)
            else:
                # Sent as far, and already on their way back in.
                self.assertTrue(self.tuning.shove_push - 0.3 < foe.at - at <= self.tuning.shove_push + 1e-9)
            self.assertTrue(1.0 <= health - foe.health <= 3.0)
            self.assertFalse(fight.in_reach(fight.hero, foe))
            went_down += kinds[1] == FLOORED
            self.assertFalse(fight.can_shove(), "not again at once")
            self.assertEqual(fight.hero.shove_wait, self.tuning.shove_rest)
        self.assertTrue(8 < went_down < 50, went_down)

    def test_a_strong_arm_shoves_further_and_floors_oftener_and_a_firm_stance_is_floored_less(self) -> None:
        strong, weak = self._fight(strength=10), self._fight(strength=2)
        for fight in (strong, weak):
            fight.foes[0].attributes["constitution"] = 5.0
        self.assertGreater(strong.shove_floors(strong.hero, strong.foes[0]), weak.shove_floors(weak.hero, weak.foes[0]))
        firm = self._fight()
        firm.foes[0].attributes["constitution"] = 10.0
        slight = self._fight()
        slight.foes[0].attributes["constitution"] = 1.0
        self.assertLess(firm.shove_floors(firm.hero, firm.foes[0]), slight.shove_floors(slight.hero, slight.foes[0]))
        slight.foes[0].lost.append("leg_left")
        self.assertEqual(slight.shove_floors(slight.hero, slight.foes[0]), 1.0, "on one leg anybody goes over")
        sent = []
        for fight in (strong, weak):
            self._close(fight)
            at = fight.foes[0].at
            fight.shove()
            fight.update(0.05)
            sent.append(fight.foes[0].at - at)
        self.assertGreater(sent[0], sent[1] + 0.8, "five points of strength either way is a pace and a half")

    def test_raiders_shove_too_now_and_then(self) -> None:
        shoved = floored = 0
        for seed in range(30):
            fight = self._fight(seed, weapon="fists")
            for _ in range(600):
                for event in fight.update(0.05):
                    shoved += event.kind == SHOVED and event.by == 1
                    floored += event.kind == FLOORED and event.to == 0 and not event.weapon
        self.assertGreater(shoved, 20)
        self.assertGreater(floored, 3, "and the hero goes down of it like anybody")

    def test_with_only_a_weapon_for_the_hand_they_shove_only_when_told(self) -> None:
        fight = self._fight()
        events = []
        for _ in range(400):
            events += fight.update(0.05)
        self.assertFalse([event for event in events if event.kind == SHOVED and event.by == 0])


class SeveringTests(unittest.TestCase):
    """A telling blow may take a part off: an arm or a leg, and a head only with the blow that kills."""

    def setUp(self) -> None:
        self.data = load_combat()
        self.tuning = self.data.tuning

    def _blow(self, seed: int, weapon: str, off: float, health: float = 100000.0):
        rng = SimulationRNG(seed)
        fight = Fight(self.data, hero(self.data, "Sergio", EVEN, weapon), [raider(self.data, self.data.raiders["thug"], 1, rng)], rng)
        foe = fight.foes[0]
        foe.health, foe.max_health = health, 100000.0
        foe.at, foe.wait = self.tuning.reach, 99.0
        fight.hero.health = fight.hero.max_health = 100000.0
        fight.crit = 1.0
        self.assertTrue(fight.land_crit(off))
        return fight, [event for event in fight.update(0.05) if event.by == 0]

    def test_how_likely_goes_by_the_weapon_and_by_how_well_the_mark_was_stopped(self) -> None:
        weapons, tuning = self.data.weapons, self.tuning
        self.assertEqual(sever_chance(tuning, weapons["fists"], 3.0), 0.0, "nobody takes an arm off with bare hands")
        self.assertGreater(sever_chance(tuning, weapons["rusty_knife"], 3.0), sever_chance(tuning, weapons["baton"], 3.0))
        self.assertGreater(sever_chance(tuning, weapons["rusty_knife"], 3.0), sever_chance(tuning, weapons["rusty_knife"], 2.0))
        self.assertEqual(sever_chance(tuning, weapons["laser"], 1.25), 0.0, "a blow that only grazed takes nothing off")
        self.assertEqual(sever_chance(tuning, weapons["laser"], 1.0), 0.0)

    def test_a_telling_blow_takes_off_an_arm_or_a_leg_and_never_a_head_from_the_living(self) -> None:
        parts: dict[str, int] = {}
        plain = 0
        for seed in range(300):
            fight, told = self._blow(seed, "rusty_knife", 0.0)
            kinds = [event.kind for event in told]
            foe = fight.foes[0]
            if SEVERED in kinds:
                part = next(event.said for event in told if event.kind == SEVERED)
                parts[part] = parts.get(part, 0) + 1
                self.assertEqual(foe.lost, [part])
                self.assertEqual(kinds.index(HIT), 0)
                if of_leg(part, self.tuning):
                    self.assertIn(FLOORED, kinds, "a leg gone is a fall, wherever it was cut")
                    self.assertGreater(foe.floored, 0.0)
            else:
                plain += 1
                self.assertEqual(foe.lost, [])
                self.assertIn(FLOORED, kinds, "a telling blow that takes nothing off still floors")
        every = {part for limb in (*self.tuning.arms, *self.tuning.legs) for part in limb}
        self.assertEqual(set(parts), every, "through any joint a limb bends at")
        self.assertEqual(len(every), 12)
        self.assertFalse(set(parts) & set(self.tuning.deadly))

        def count(*words: str) -> int:
            return sum(times for part, times in parts.items() if part.split("_")[0] in words)

        # The smaller the part, the oftener: hands and feet before forearms and shins, and those before whole limbs.
        self.assertGreater(count("hand", "foot"), count("forearm", "shin") * 1.3, parts)
        self.assertGreater(count("forearm", "shin"), count("arm", "leg") * 1.3, parts)
        self.assertGreater(count("hand", "foot"), sum(parts.values()) * 0.45, parts)
        self.assertTrue(0.6 < sum(parts.values()) / 300 < 0.9, parts)
        self.assertGreater(plain, 30)

    def test_a_head_comes_off_only_with_the_blow_that_kills(self) -> None:
        heads = 0
        ways = []
        for seed in range(200):
            fight, told = self._blow(seed, "rusty_knife", 0.0, health=3.0)
            foe = fight.foes[0]
            self.assertTrue(foe.down)
            severed = [event.said for event in told if event.kind == SEVERED]
            self.assertLessEqual(set(severed), set(self.tuning.deadly))
            self.assertLessEqual(len(severed), 1)
            heads += bool(severed)
            ways += severed
            kinds = [event.kind for event in told]
            self.assertEqual(kinds[-2:], [DOWN, ENDED])
        self.assertTrue(110 < heads < 180, heads)
        self.assertEqual(set(ways), {self.tuning.head, "torso"}, "a head off, or cut in two")
        self.assertGreater(ways.count(self.tuning.head), ways.count("torso") * 1.8, "and a head far sooner")

    def test_the_smaller_the_part_the_likelier_it_is_the_one_that_comes_off(self) -> None:
        tuning = self.tuning
        self.assertLess(sever_odds("arm_left", tuning), sever_odds("forearm_left", tuning))
        self.assertLess(sever_odds("forearm_left", tuning), sever_odds("hand_left", tuning))
        self.assertEqual(sever_odds("hand_left", tuning), sever_odds("foot_right", tuning))
        self.assertEqual(sever_odds("arm_right", tuning), sever_odds("leg_left", tuning))
        self.assertGreater(sever_odds("head", tuning), sever_odds("torso", tuning))
        self.assertEqual(sever_odds("tail", tuning), 1.0)
        raw = json.loads(DATA_PATH.read_text(encoding="utf-8"))
        raw["tuning"]["sever_odds"] = [1, 5]
        short = combat_from_data(raw).tuning
        self.assertEqual(sever_odds("hand_left", short), 5.0, "past the last that is written, as the last")
        raw["tuning"]["sever_odds"] = [1, 0]
        with self.assertRaisesRegex(ValueError, "more than nothing"):
            combat_from_data(raw)
        del raw["tuning"]["sever_odds"], raw["tuning"]["deadly_odds"]
        self.assertEqual(combat_from_data(raw).tuning.sever_odds, (1.0, 2.0, 4.0))

    def test_a_limb_comes_off_at_any_joint_still_on_them(self) -> None:
        tuning = self.tuning
        who = hero(self.data, "X", EVEN, "fists")
        self.assertEqual(len(severable(who, tuning)), 12)
        self.assertEqual(stumps(who, tuning), [])
        who.lost.append("forearm_left")
        left = severable(who, tuning)
        self.assertIn("arm_left", left, "it can still be cut nearer the trunk")
        self.assertNotIn("forearm_left", left)
        self.assertNotIn("hand_left", left, "what went with it is not there to cut")
        self.assertEqual(gone(who, tuning.arms), 1, "an arm cut anywhere is an arm of no use")
        self.assertEqual(stumps(who, tuning), ["forearm_left"])
        who.lost.append("arm_left")
        self.assertEqual(stumps(who, tuning), ["arm_left"], "open where it was cut nearest the trunk, and only there")
        self.assertAlmostEqual(bleeding(who, tuning), tuning.bleed)
        self.assertEqual(gone(who, tuning.arms), 1)
        self.assertFalse(any(part.endswith("_left") and "arm" in part or part == "hand_left" for part in severable(who, tuning)))
        who.lost += ["foot_right", "hand_right"]
        self.assertEqual(stumps(who, tuning), ["arm_left", "hand_right", "foot_right"])
        self.assertAlmostEqual(bleeding(who, tuning), 3 * tuning.bleed)
        self.assertFalse(can_strike(who, tuning), "a hand gone is as an arm gone")
        self.assertTrue(of_leg("foot_right", tuning) and of_leg("shin_left", tuning) and not of_leg("hand_left", tuning))
        self.assertEqual(dodge_chance(who, tuning), 0.0, "and a foot as a leg")

    def test_a_limb_written_as_one_part_comes_off_whole_or_not_at_all(self) -> None:
        raw = json.loads(DATA_PATH.read_text(encoding="utf-8"))
        raw["tuning"]["arms"] = ["arm_left", "arm_right"]
        raw["tuning"]["legs"] = [["leg_left"], ["leg_right", "shin_right"]]
        tuning = combat_from_data(raw).tuning
        self.assertEqual(tuning.arms, (("arm_left",), ("arm_right",)))
        who = hero(self.data, "X", EVEN, "fists")
        self.assertEqual(severable(who, tuning), ["arm_left", "arm_right", "leg_left", "leg_right", "shin_right"])

    def test_a_plain_blow_takes_nothing_off(self) -> None:
        for seed in range(40):
            rng = SimulationRNG(seed)
            fight = Fight(self.data, hero(self.data, "Sergio", _with(strength=10), "sledge"), [raider(self.data, self.data.raiders["thug"], 1, rng)], rng)
            fight.foes[0].at = self.tuning.reach
            events = []
            while fight.outcome is None and fight.seconds < 60:
                events += fight.update(0.1)
            self.assertFalse([event for event in events if event.kind == SEVERED])

    def test_whoever_has_lost_a_part_bleeds_a_little_every_second_until_it_is_the_end_of_them(self) -> None:
        rng = SimulationRNG(1)
        fight = Fight(self.data, hero(self.data, "Sergio", EVEN, "fists"), [raider(self.data, self.data.raiders["thug"], 1, rng)], rng)
        foe = fight.foes[0]
        fight.hero.health = fight.hero.max_health = 100000.0
        fight.hero.at = -500.0
        foe.health = 30.0
        foe.lost.append("arm_left")
        self.assertEqual(bleeding(foe, self.tuning), self.tuning.bleed)
        events = fight.update(5.0)
        self.assertAlmostEqual(foe.health, 30.0 - 5 * self.tuning.bleed, places=4)
        bled = [event for event in events if event.kind == BLED]
        self.assertTrue(3 <= len(bled) <= 12, "said now and then, not every instant")
        self.assertAlmostEqual(sum(event.amount for event in bled), 5 * self.tuning.bleed, delta=1.0)
        foe.lost.append("leg_right")
        self.assertEqual(bleeding(foe, self.tuning), 2 * self.tuning.bleed, "twice as fast with two gone")
        events = fight.update(30.0)
        self.assertTrue(foe.down)
        self.assertEqual(fight.outcome, WON, "bled out, they are as beaten as by any blow")
        self.assertIn(DOWN, [event.kind for event in events])
        self.assertEqual(bleeding(foe, self.tuning), 0.0)

    def test_a_medkit_stops_what_bleeds(self) -> None:
        rng = SimulationRNG(1)
        fight = Fight(self.data, hero(self.data, "Sergio", EVEN, "fists"), [raider(self.data, self.data.raiders["thug"], 1, rng)], rng, medkits=1)
        who = fight.hero
        who.lost.append("arm_left")
        self.assertGreater(bleeding(who, self.tuning), 0.0)
        self.assertTrue(fight.heal(), "worth it even to somebody who is whole otherwise")
        self.assertEqual(bleeding(who, self.tuning), 0.0)

    def test_what_is_gone_is_missed(self) -> None:
        tuning = self.tuning
        whole, armless, lame = (hero(self.data, "X", EVEN, "baton") for _ in range(3))
        armless.lost.append("arm_left")
        lame.lost.append("leg_left")
        self.assertAlmostEqual(interval(armless, tuning) / interval(whole, tuning), 1.0 + tuning.arm_slower)
        self.assertAlmostEqual(walk_speed(lame, tuning) / walk_speed(whole, tuning), tuning.leg_slower)
        self.assertEqual(dodge_chance(lame, tuning), 0.0)
        self.assertGreater(dodge_chance(whole, tuning), 0.0)
        self.assertTrue(can_strike(armless, tuning))
        armless.lost.append("arm_right")
        self.assertFalse(can_strike(armless, tuning))
        lame.lost.append("leg_right")
        self.assertEqual(walk_speed(lame, tuning), 0.0)

    def test_with_no_arm_they_strike_nobody_and_with_no_leg_they_do_not_get_up(self) -> None:
        rng = SimulationRNG(2)
        fight = Fight(self.data, hero(self.data, "Sergio", EVEN, "fists"), [raider(self.data, self.data.raiders["thug"], 1, rng) for _ in range(2)], rng)
        for fighter in fight.fighters:
            fighter.health = fighter.max_health = 100000.0
            fighter.staunched = True
        armless, legless = fight.foes
        armless.lost += ["arm_left", "arm_right"]
        legless.lost += ["leg_left", "leg_right"]
        for foe in fight.foes:
            foe.staunched = True
        start = legless.at
        events = []
        for _ in range(300):
            events += fight.update(0.05)
        self.assertFalse([event for event in events if event.by in (1, 2) and event.kind in (HIT, DODGED, SHOVED)])
        self.assertEqual(legless.at, start)
        self.assertGreater(legless.floored, 0.0)
        self.assertEqual(fight.standing(), [0, 1], "they are still there to be finished")


class TheirTellingBlowsTests(unittest.TestCase):
    """Theirs land telling blows too, and take parts off ours: less often, and the oftener the
    stronger they are for how firm ours stands."""

    def setUp(self) -> None:
        self.data = load_combat()
        self.tuning = self.data.tuning

    def _pair(self, strength: float, constitution: float, sort: str = "thug"):
        foe = raider(self.data, self.data.raiders[sort], 3, SimulationRNG(1))
        foe.attributes["strength"] = strength
        return foe, hero(self.data, "Sergio", _with(constitution=constitution), "baton")

    def test_the_stronger_they_are_for_how_firm_ours_stands_the_oftener(self) -> None:
        tuning = self.tuning
        even = foe_crit_chance(*self._pair(5, 5), tuning)
        self.assertAlmostEqual(even, tuning.foe_crit)
        self.assertGreater(foe_crit_chance(*self._pair(9, 5), tuning), even)
        self.assertGreater(foe_crit_chance(*self._pair(5, 2), tuning), even)
        self.assertLess(foe_crit_chance(*self._pair(5, 9), tuning), even)
        self.assertEqual(foe_crit_chance(*self._pair(1, 10), tuning), 0.0)
        self.assertEqual(foe_crit_chance(*self._pair(99, 1), tuning), tuning.most_foe_crit)
        self.assertAlmostEqual(foe_crit_chance(*self._pair(8, 5), tuning) - even, 3 * tuning.foe_crit_per_point)

    def test_theirs_take_parts_off_less_often_than_ours_with_the_same_weapon(self) -> None:
        tuning, knife = self.tuning, self.data.weapons["rusty_knife"]
        foe, ours = self._pair(5, 5)
        self.assertAlmostEqual(foe_sever_chance(foe, ours, tuning, knife, 3.0), sever_chance(tuning, knife, 3.0) * tuning.foe_severs)
        strong, _ = self._pair(10, 5)
        self.assertGreater(foe_sever_chance(strong, ours, tuning, knife, 3.0), foe_sever_chance(foe, ours, tuning, knife, 3.0))
        weak, firm = self._pair(2, 10)
        self.assertLess(foe_sever_chance(weak, firm, tuning, knife, 3.0), foe_sever_chance(foe, ours, tuning, knife, 3.0))
        self.assertEqual(foe_sever_chance(strong, ours, tuning, self.data.weapons["fists"], 3.0), 0.0)
        self.assertLessEqual(foe_sever_chance(*self._pair(99, 1), tuning, knife, 3.0), 1.0)

    def _watch(self, sort: str, level: int, constitution: float, fights: int = 60, seconds: float = 40.0) -> tuple[int, int, int, int]:
        """How many blows of theirs landed, how many of those were telling ones, how many
        parts they took off ours, and how many heads."""
        blows = telling = parts = heads = 0
        for seed in range(fights):
            rng = SimulationRNG(seed)
            fight = Fight(self.data, hero(self.data, "Sergio", _with(constitution=constitution), "fists"), [raider(self.data, self.data.raiders[sort], level, rng)], rng)
            fight.foes[0].health = fight.foes[0].max_health = 100000.0
            fight.foes[0].at = self.tuning.reach
            fight.hero.health = fight.hero.max_health = 400.0
            while fight.outcome is None and fight.seconds < seconds:
                for event in fight.update(0.25):
                    blows += event.kind == HIT and event.by == 1
                    telling += event.kind == HIT and event.by == 1 and event.times > 1.0
                    if event.kind == SEVERED and event.to == 0:
                        parts += 1
                        heads += event.said == self.tuning.head
            self.assertLessEqual(len(set(fight.hero.lost)), 5)
        return blows, telling, parts, heads

    def test_ours_lose_parts_to_them_and_bleed_and_see_to_it(self) -> None:
        blows, telling, parts, heads = self._watch("cutter", 5, 3)
        self.assertGreater(telling, 20)
        self.assertLess(telling / blows, self.tuning.most_foe_crit + 0.05)
        self.assertGreater(parts, 5, "a knife in a strong hand takes parts off ours")
        firm = self._watch("cutter", 1, 10)
        self.assertLess(firm[1] / max(1, firm[0]), telling / blows, "and far fewer off somebody who stands firm before a weak one")
        thug = self._watch("thug", 1, 5)
        self.assertEqual(thug[2], 0, "bare hands take nothing off")

    def test_a_part_gone_is_seen_to_with_a_medkit_by_themselves(self) -> None:
        rng = SimulationRNG(4)
        fight = Fight(self.data, hero(self.data, "Sergio", EVEN, "fists"), [raider(self.data, self.data.raiders["thug"], 1, rng)], rng, medkits=1)
        fight.foes[0].health = fight.foes[0].max_health = 100000.0
        fight.foes[0].at = self.tuning.reach
        fight.hero.lost.append("arm_left")
        kinds = []
        for _ in range(60):
            kinds += [event.kind for event in fight.update(0.1)]
        self.assertIn(HEALED, kinds)
        self.assertEqual(bleeding(fight.hero, self.tuning), 0.0)
        self.assertEqual(fight.medkits, 0)

    def test_what_they_took_off_is_what_ours_comes_back_without(self) -> None:
        rng = SimulationRNG(2)
        fight = Fight(self.data, hero(self.data, "Sergio", EVEN, "sledge"), [raider(self.data, self.data.raiders["thug"], 1, rng)], rng)
        fight.hero.lost.append("leg_left")
        fight.hero.staunched = True
        fight.foes[0].health = 1.0
        fight.foes[0].at = self.tuning.reach
        fight.foes[0].attributes["dexterity"] = 1.0
        fight.hero.floored = 0.0
        fight.hero.wait = 0.0
        while fight.outcome is None and fight.seconds < 30:
            fight.update(0.1)
        after = aftermath(self.data, fight, rng)
        if after.outcome == WON:
            self.assertEqual(after.lost, ["leg_left"])
            self.assertIn("Vuelve sin una pierna", after.told("Sergio"))
        maimed = Fight(self.data, hero(self.data, "Sergio", EVEN, "fists"), [raider(self.data, self.data.raiders["thug"], 1, rng)], rng)
        maimed.hero.lost += ["hand_right", "foot_left", "shin_left"]
        maimed.foes[0].health = 0.0
        maimed.outcome = WON
        told = aftermath(self.data, maimed, rng)
        self.assertEqual(told.lost, ["hand_right", "shin_left"])
        self.assertIn("Vuelve sin una mano ni media pierna.", told.told("Sergio"))
        halved = Fight(self.data, hero(self.data, "Sergio", EVEN, "fists"), [raider(self.data, self.data.raiders["thug"], 1, rng)], rng)
        halved.hero.lost.append("torso")
        halved.hero.health = 0.0
        halved.outcome = LOST
        self.assertTrue(aftermath(self.data, halved, rng).died, "nor in two")
        self.assertIn("partido en dos", aftermath(self.data, halved, rng).told("Sergio"))
        beheaded = Fight(self.data, hero(self.data, "Sergio", EVEN, "fists"), [raider(self.data, self.data.raiders["thug"], 1, rng)], rng)
        beheaded.hero.lost.append(self.tuning.head)
        beheaded.hero.health = 0.0
        beheaded.outcome = LOST
        for seed in range(20):
            gone = aftermath(self.data, beheaded, SimulationRNG(seed))
            self.assertTrue(gone.died, "nobody comes back without a head")
            self.assertIn("sin cabeza", gone.told("Sergio"))

    def test_on_one_leg_nobody_runs_far(self) -> None:
        rng = SimulationRNG(1)
        fight = Fight(self.data, hero(self.data, "Sergio", EVEN, "fists"), [raider(self.data, self.data.raiders["thug"], 1, rng)], rng)
        whole = fight.flee_chance()
        fight.hero.lost.append("leg_left")
        self.assertAlmostEqual(fight.flee_chance(), whole * self.tuning.leg_slower)


class BeastTests(unittest.TestCase):
    """Something that is no raider: stronger, with claws that cut, and nothing to be paid."""

    def setUp(self) -> None:
        self.data = load_combat()

    def test_it_is_stronger_tougher_and_has_claws_that_take_parts_off(self) -> None:
        kinds = self.data.raiders
        beast, thug = kinds["monster"], kinds["thug"]
        self.assertTrue(beast.beast)
        self.assertEqual(beast.weapons, ("claws",))
        claws = self.data.weapons["claws"]
        self.assertEqual((claws.kind, claws.severs), ("melee", 1.0))
        self.assertGreater(claws.damage[0], self.data.weapons["rusty_knife"].damage[0], "more harm than a knife")
        self.assertGreater(beast.size, 1.0)

        def mean(kind, what) -> float:
            return sum(what(raider(self.data, kind, 3, SimulationRNG(seed))) for seed in range(200)) / 200

        self.assertGreater(mean(beast, lambda foe: foe.attributes["strength"]), mean(thug, lambda foe: foe.attributes["strength"]) + 1)
        self.assertGreater(mean(beast, lambda foe: foe.max_health), mean(thug, lambda foe: foe.max_health) * 1.3)
        self.assertTrue(raider(self.data, beast, 3, SimulationRNG(1)).beast)
        self.assertFalse(raider(self.data, thug, 3, SimulationRNG(1)).beast)

    def test_it_is_a_danger_to_the_limbs_of_whoever_meets_it(self) -> None:
        maimed = with_knife = 0
        for seed in range(150):
            for sort in ("monster", "cutter"):
                rng = SimulationRNG(seed)
                fight = Fight(self.data, hero(self.data, "Sergio", EVEN, "baton"), [raider(self.data, self.data.raiders[sort], 3, rng)], rng, medkits=2)
                fight.resolve()
                lost = bool(fight.hero.lost)
                maimed += lost and sort == "monster"
                with_knife += lost and sort == "cutter"
        self.assertGreater(maimed, 15, maimed)
        self.assertGreater(maimed, with_knife, "more of a danger than somebody with a knife")

    def test_a_beast_is_met_where_the_zone_has_it_or_where_it_is_asked_for(self) -> None:
        sorts = {foe.kind for seed in range(300) for foe in raiders(self.data, "forest", SimulationRNG(seed))}
        self.assertNotIn("monster", sorts, "not at the gate")
        sorts = {foe.kind for seed in range(300) for foe in raiders(self.data, "crater", SimulationRNG(seed))}
        self.assertIn("monster", sorts)
        asked = raiders(self.data, "forest", SimulationRNG(1), "monster", 2, 4)
        self.assertEqual([(foe.kind, foe.level) for foe in asked], [("monster", 4), ("monster", 4)])
        only_sort = raiders(self.data, "forest", SimulationRNG(1), "monster")
        self.assertEqual({(foe.kind, foe.level) for foe in only_sort}, {("monster", 1)}, "as many and of the level the zone has")

    def test_nothing_is_handed_to_a_beast_and_what_is_taken_from_it_is_a_piece_of_it(self) -> None:
        rng = SimulationRNG(3)
        band = raiders(self.data, "summit", rng, "monster", 1)
        self.assertFalse(payable(band))
        self.assertTrue(payable(raiders(self.data, "forest", SimulationRNG(1), "thug")))
        paid = meet(self.data, hero(self.data, "Sergio", EVEN, "baton"), "summit", SimulationRNG(8), choice=PAY, carried=50)
        fight = Fight(self.data, hero(self.data, "Sergio", EVEN, "baton"), band, rng)
        self.assertEqual(decide_alone(fight, 0.05, 50, self.data), RUN, "the timid run from it: there is no paying it")
        fight.foes[0].health = 0.0
        fight.outcome = WON
        after = aftermath(self.data, fight, rng)
        self.assertEqual(after.loot, {self.data.tuning.beast_loot: 1})
        self.assertGreater(after.experience, 0)
        del paid


class RoundsTests(unittest.TestCase):
    """What is fired can be fired so many times in a fight, and the player says what the hero
    fights with of what they carry."""

    def setUp(self) -> None:
        self.data = load_combat()
        self.tuning = self.data.tuning

    def _fight(self, seed: int = 3, weapon: str = "baton", gun: str | None = "pipe_pistol", sort: str = "thug", level: int = 1, rounds: int | None = None) -> Fight:
        rng = SimulationRNG(seed)
        fight = Fight(self.data, hero(self.data, "Sergio", EVEN, weapon, gun_id=gun, rounds=rounds), [raider(self.data, self.data.raiders[sort], level, rng)], rng)
        for fighter in fight.fighters:
            fighter.health = fighter.max_health = 100000.0
        return fight

    def _used(self, fight: Fight, seconds: float, by: int = 0) -> list[str]:
        used = []
        for _ in range(round(seconds / 0.05)):
            used += [event.weapon for event in fight.update(0.05) if event.by == by and event.kind in (HIT, DODGED)]
        return used

    def test_what_is_fired_holds_so_many_rounds_and_nothing_else_holds_any(self) -> None:
        weapons = self.data.weapons
        self.assertEqual({weapon_id: weapon.ammo for weapon_id, weapon in weapons.items() if weapon.ammo}, {"pipe_pistol": 6, "rifle": 5, "arc_thrower": 8, "laser": 6})
        self.assertTrue(all(weapon.ammo > 0 for weapon in weapons.values() if weapon.kind != "melee"))
        raw = json.loads(DATA_PATH.read_text(encoding="utf-8"))
        raw["weapons"]["baton"]["ammo"] = 3
        with self.assertRaisesRegex(ValueError, "fired so many times"):
            combat_from_data(raw)
        del raw["weapons"]["baton"]["ammo"], raw["weapons"]["rifle"]["ammo"]
        self.assertEqual(combat_from_data(raw).weapons["rifle"].ammo, 0, "left out, it needs none")

    def test_they_set_out_with_what_it_holds_unless_it_is_said(self) -> None:
        self.assertEqual(hero(self.data, "X", EVEN, "baton", gun_id="pipe_pistol").rounds, 6)
        self.assertEqual(hero(self.data, "X", EVEN, "rifle").rounds, 5)
        self.assertEqual(hero(self.data, "X", EVEN, "baton").rounds, 0)
        self.assertEqual(hero(self.data, "X", EVEN, "baton", gun_id="pipe_pistol", rounds=2).rounds, 2)
        self.assertEqual(hero(self.data, "X", EVEN, "baton", gun_id="pipe_pistol", rounds=-4).rounds, 0)
        gunner = raider(self.data, self.data.raiders["gunner"], 2, SimulationRNG(1))
        self.assertEqual(gunner.rounds, gunner.weapon.ammo)
        self.assertGreater(gunner.rounds, 0)

    def test_every_shot_uses_one_and_with_none_left_they_go_in_with_what_is_in_the_hand(self) -> None:
        fight = self._fight(rounds=3)
        fight.foes[0].wait = 9999.0
        fight.foes[0].at = fight.hero.at + 30.0
        events = []
        for _ in range(300):
            events += fight.update(0.05)
        shots = [event.weapon for event in events if event.by == 0 and event.kind in (HIT, DODGED)]
        self.assertEqual(shots[:3], ["pipe_pistol"] * 3, "hit or not, a shot is a shot")
        self.assertNotIn("pipe_pistol", shots[3:])
        empty = [event for event in events if event.kind == EMPTY]
        self.assertEqual([(event.by, event.weapon) for event in empty], [(0, "pipe_pistol")], "said once")
        self.assertEqual(fight.hero.rounds, 0)
        self.assertLess(fight.gap(fight.hero, fight.foes[0]), 30.0, "and then they go for them")
        fight.foes[0].at = fight.hero.at + self.tuning.reach
        fight.foes[0].floored = 0.0
        self.assertEqual(fight.weapon_for(fight.hero, fight.foes[0]).weapon_id, "baton")

    def test_with_only_something_to_fire_and_that_empty_it_is_bare_hands(self) -> None:
        fight = self._fight(weapon="rifle", gun=None, rounds=1)
        fight.foes[0].wait = 9999.0
        used = self._used(fight, 25.0)
        self.assertEqual(used[0], "rifle")
        self.assertEqual(set(used[1:]), {"fists"})
        self.assertTrue(fight.in_reach(fight.hero, fight.foes[0]), "they had to walk up to them")

    def test_theirs_run_out_too_and_come_on_with_their_hands(self) -> None:
        fight = self._fight(weapon="fists", gun=None, sort="gunner", level=2)
        fight.hero.wait = 9999.0
        fight.hero.at = fight.foes[0].at - 30.0
        holds = fight.foes[0].weapon.ammo
        fired = fight.foes[0].weapon.weapon_id
        used = []
        emptied = 0
        for _ in range(3000):
            fight.hero.wait = 9999.0
            fight.hero.floored = 0.0
            for event in fight.update(0.05):
                used += [event.weapon] if event.by == 1 and event.kind in (HIT, DODGED) else []
                emptied += event.kind == EMPTY and event.by == 1
        self.assertEqual(used[:holds], [fired] * holds)
        self.assertEqual(emptied, 1)
        self.assertGreater(len(used), holds)
        self.assertEqual(set(used[holds:]), {"fists"})

    def test_the_player_says_what_they_fight_with_of_what_they_carry(self) -> None:
        fight = self._fight()
        self.assertEqual((fight.stance, fight.stances()), (BOTH, [BOTH, HAND, GUN]))
        self.assertFalse(fight.set_stance("teeth"))
        self.assertEqual([fight.next_stance() for _ in range(3)], [HAND, GUN, BOTH])
        only = self._fight(gun=None)
        self.assertEqual(only.stances(), [BOTH])
        self.assertFalse(only.set_stance(GUN))
        self.assertEqual(only.next_stance(), BOTH)

    def test_with_the_hand_alone_nothing_is_fired_and_no_round_is_used(self) -> None:
        fight = self._fight()
        self.assertTrue(fight.set_stance(HAND))
        fight.foes[0].wait = 9999.0
        fight.foes[0].at = fight.hero.at + 12.0
        self.assertIsNone(fight.weapon_for(fight.hero, fight.foes[0]))
        events = []
        for _ in range(400):
            events += fight.update(0.05)
        used = {event.weapon for event in events if event.by == 0 and event.kind in (HIT, DODGED)}
        self.assertLessEqual(used, {"baton", "fists"}, "the baton, and fists on whoever it sent down")
        self.assertIn("baton", used)
        self.assertEqual(fight.hero.rounds, 6)
        self.assertFalse(any(event.by == 0 and event.kind == SHOVED for event in events), "nor do they shove for room to fire")

    def test_with_what_is_fired_alone_they_fire_right_up_to_them_while_it_lasts(self) -> None:
        fight = self._fight(rounds=4)
        self.assertTrue(fight.set_stance(GUN))
        fight.foes[0].wait = 9999.0
        fight.foes[0].at = fight.hero.at + self.tuning.reach
        fight.hero.shove_wait = 9999.0
        self.assertEqual(fight.weapon_for(fight.hero, fight.foes[0]).weapon_id, "pipe_pistol")
        used = []
        for _ in range(500):
            fight.foes[0].at = fight.hero.at + self.tuning.reach
            fight.foes[0].floored = 0.0
            fight.hero.shove_wait = 9999.0
            used += [event.weapon for event in fight.update(0.05) if event.by == 0 and event.kind in (HIT, DODGED)]
        self.assertEqual(used[:4], ["pipe_pistol"] * 4)
        self.assertEqual(set(used[4:]), {"baton"}, "and with none left, what is in the hand")


class PoundingTests(unittest.TestCase):
    """Somebody on the ground is got down on and pounded where they lie, until they throw
    whoever is on them off: a die and their strength each."""

    def setUp(self) -> None:
        self.data = load_combat()
        self.tuning = self.data.tuning

    def _fight(self, seed: int = 3, weapon: str = "baton", sort: str = "thug", level: int = 1, **attributes: float) -> Fight:
        rng = SimulationRNG(seed)
        fight = Fight(self.data, hero(self.data, "Sergio", _with(**attributes), weapon), [raider(self.data, self.data.raiders[sort], level, rng)], rng)
        for fighter in fight.fighters:
            fighter.health = fighter.max_health = 100000.0
        fight.foes[0].at = fight.hero.at + self.tuning.reach
        return fight

    def test_only_somebody_on_the_ground_and_right_up_to_them_is_got_down_on(self) -> None:
        fight = self._fight()
        ours, theirs = fight.hero, fight.foes[0]
        self.assertFalse(fight.can_pound(ours, theirs), "they are on their feet")
        theirs.floored = 1.0
        self.assertTrue(fight.can_pound(ours, theirs))
        theirs.at += 1.0
        self.assertFalse(fight.can_pound(ours, theirs), "there is ground between")
        theirs.at -= 1.0
        ours.floored = 0.5
        self.assertFalse(fight.can_pound(ours, theirs), "nobody on the ground gets on anybody")
        ours.floored = 0.0
        ours.lost += ["hand_left", "forearm_right"]
        self.assertFalse(fight.can_pound(ours, theirs), "nor anybody with no arm of any use")
        ours.lost.clear()
        ours.lost += ["foot_left", "leg_right"]
        self.assertFalse(fight.can_pound(ours, theirs))
        ours.lost.clear()
        theirs.health = 0.0
        self.assertFalse(fight.can_pound(ours, theirs), "nor on anybody who is done for")

    def test_whoever_throws_the_more_with_their_strength_wins_and_the_top_face_always_does(self) -> None:
        fight = self._fight()
        edge = self.tuning.pound_edge
        self.assertGreater(edge, 0, "whoever is on top has their weight on them")
        self.assertTrue(fight.throws_off(5, 5 + edge, 4, 5))
        self.assertFalse(fight.throws_off(4, 5 + edge, 4, 5), "the same is not more")
        self.assertFalse(fight.throws_off(4, 5, 3, 5), "nor is more that is not more than their weight")
        self.assertFalse(fight.throws_off(5, 2, 1, 9))
        self.assertTrue(fight.throws_off(self.tuning.pound_die, 1, 6, 10), "however strong whoever is on them")
        self.assertFalse(fight.throws_off(self.tuning.pound_die - 1, 1, 1, 10))

    def test_fists_come_down_fast_on_them_and_they_stay_down_until_they_throw_them_off(self) -> None:
        fight = self._fight(strength=10)
        foe = fight.foes[0]
        foe.attributes["strength"] = 1.0
        foe.floored = 0.3
        fight.hero.wait = 0.0
        events = []
        seconds = 0.0
        while not any(event.kind == THROWN_OFF for event in events) and seconds < 120.0:
            self.assertTrue(foe.floored > 0.0 or seconds == 0.0)
            events += fight.update(0.05)
            seconds += 0.05
            if fight.pins:
                self.assertEqual(fight.pins, {0: 1})
        blows = [event for event in events if event.kind in (HIT, DODGED) and event.by == 0]
        held = [event for event in events if event.kind == HELD]
        thrown = [event for event in events if event.kind == THROWN_OFF]
        self.assertEqual({event.weapon for event in blows}, {"fists"}, "whatever they carry")
        self.assertTrue(all(event.kind == HIT for event in blows), "nobody on the ground gets out of the way")
        self.assertEqual(len(blows), len(held) + 1, "a throw of the dice after every blow")
        self.assertGreater(seconds, self.tuning.floored_seconds, "held down past when they would have been up")
        self.assertLess(seconds / len(blows), interval(fight.hero, self.tuning, self.data.weapons["fists"]), "faster than standing")
        self.assertEqual(len(thrown), 1)
        self.assertEqual((thrown[0].by, thrown[0].to), (1, 0))
        die = str(self.tuning.pound_die)
        self.assertTrue(thrown[0].said.startswith(f"{die}+1 contra "), thrown[0].said)
        self.assertTrue(all(not event.said.startswith(die) and "+1 contra " in event.said and event.said.endswith("+10") for event in held))
        self.assertEqual(foe.floored, 0.0, "up at once")
        self.assertEqual(fight.pins, {})
        self.assertGreater(fight.gap(fight.hero, foe), self.tuning.reach, "and whoever was on them is sent back")
        self.assertGreater(fight.hero.wait, self.tuning.reel_seconds * 0.5)

    def test_a_weak_one_does_not_hold_a_strong_one_for_long(self) -> None:
        def blows_to_get_off(mine: float, theirs: float) -> float:
            total = 0
            for seed in range(40):
                fight = self._fight(seed=seed, strength=theirs)
                foe = fight.foes[0]
                foe.attributes["strength"] = mine
                foe.floored = 0.3
                fight.hero.wait = 0.0
                for _ in range(4000):
                    kinds = [event.kind for event in fight.update(0.05)]
                    total += kinds.count(HIT)
                    if THROWN_OFF in kinds:
                        break
            return total / 40

        self.assertLess(blows_to_get_off(9, 3), blows_to_get_off(5, 5))
        self.assertLess(blows_to_get_off(5, 5), blows_to_get_off(2, 9))
        self.assertLess(blows_to_get_off(1, 10), 12, "the top face gets anybody off in the end")

    def test_fists_fill_less_of_the_telling_blow_than_a_blow_does(self) -> None:
        fight = self._fight(strength=10)
        fight.foes[0].attributes["strength"] = 1.0
        fight.foes[0].floored = 0.3
        fight.hero.wait = 0.0
        fight.crit = 0.0
        fight.update(self.tuning.pound_down + 0.05)
        self.assertAlmostEqual(
            fight.crit, self.tuning.crit_per_hit * self.tuning.pound_crit + self.tuning.crit_per_second * (self.tuning.pound_down + 0.05)
        )

    def test_they_get_down_on_them_at_once_whatever_they_were_about(self) -> None:
        tuning = self.tuning
        fight = self._fight(strength=10)
        foe = fight.foes[0]
        foe.attributes["strength"] = 1.0
        # They have just struck, and it put them on the ground: their next blow is a long way off.
        fight.hero.wait = 1.4
        fight._floor(0, 1, 12.0, "baton")
        foe.at = fight.hero.at + tuning.reach
        events = fight.update(0.05)
        self.assertEqual(fight.pins, {0: 1}, "on them before a fist has come down")
        self.assertFalse(any(event.kind == HIT for event in events))
        self.assertLessEqual(fight.hero.wait, tuning.pound_down)
        blows = 0
        for _ in range(round(tuning.floored_seconds / 0.05)):
            blows += sum(event.kind == HIT and event.by == 0 for event in fight.update(0.05))
            if not fight.pins:
                break
            self.assertGreater(foe.floored, 0.0)
        self.assertGreaterEqual(blows, 1)
        first = self._fight(strength=10)
        first.foes[0].floored = 1.0
        first.hero.wait = 1.4
        kinds = []
        for _ in range(round((tuning.pound_down + 0.1) / 0.05)):
            kinds += [event.kind for event in first.update(0.05)]
        self.assertIn(HIT, kinds, "and the first comes down as soon as they are down")

    def test_as_strong_as_one_another_it_goes_on_for_a_few_blows(self) -> None:
        blows = thrown = 0
        for seed in range(60):
            fight = self._fight(seed=seed)
            fight.foes[0].attributes["strength"] = 5.0
            fight.foes[0].floored = 0.5
            for _ in range(2000):
                kinds = [event.kind for event in fight.update(0.05)]
                blows += kinds.count(HIT)
                if THROWN_OFF in kinds:
                    thrown += 1
                    break
        self.assertEqual(thrown, 60)
        self.assertGreater(blows / thrown, 2.5)
        self.assertLess(blows / thrown, 6.0)

    def test_a_telling_blow_on_somebody_on_the_ground_is_struck_with_what_is_in_the_hand(self) -> None:
        fight = self._fight(weapon="rusty_knife", strength=10)
        foe = fight.foes[0]
        foe.attributes["strength"] = 1.0
        foe.floored = 5.0
        fight.crit = 1.0
        self.assertTrue(fight.land_crit(0.0))
        events = fight.update(0.05)
        hit = next(event for event in events if event.kind == HIT)
        self.assertEqual((hit.weapon, hit.times), ("rusty_knife", self.tuning.crit_marks[0][1]))

    def test_theirs_get_down_on_ours_too(self) -> None:
        events = []
        for seed in range(8):
            fight = self._fight(seed=seed, strength=1)
            foe = fight.foes[0]
            foe.attributes["strength"] = 10.0
            foe.weapon = self.data.weapons["baton"]
            foe.shove_wait = 9999.0
            fight.hero.floored = 0.3
            foe.wait = 0.0
            for _ in range(200):
                told = fight.update(0.05)
                events += told
                if any(event.kind == THROWN_OFF for event in told):
                    break
        blows = [event for event in events if event.kind == HIT and event.by == 1]
        self.assertGreater(len(blows), 16)
        self.assertEqual({event.weapon for event in blows if event.times == 1.0}, {"fists"})
        self.assertTrue(any(event.kind == HELD and (event.by, event.to) == (1, 0) for event in events))
        self.assertFalse(any(event.by == 0 and event.kind in (HIT, DODGED) for event in events), "ours does nothing from under them")

    def test_a_beast_claws_at_whoever_it_is_on_and_no_faster_than_it_claws(self) -> None:
        fight = self._fight(sort="monster", level=3, strength=1)
        beast = fight.foes[0]
        beast.attributes["strength"] = 10.0
        beast.shove_wait = 9999.0
        fight.hero.floored = 0.3
        beast.wait = 0.0
        events = []
        for _ in range(200):
            beast.shove_wait = 9999.0
            events += fight.update(0.05)
            if any(event.kind == THROWN_OFF for event in events):
                break
        blows = [event for event in events if event.kind == HIT and event.by == 1]
        self.assertEqual({event.weapon for event in blows}, {"claws"})
        self.assertAlmostEqual(fight.pound_pace(beast), interval(beast, self.tuning, beast.weapon))
        self.assertGreater(fight.pound_pace(beast), fight.pound_pace(fight.hero))

    def test_somebody_with_no_leg_who_throws_them_off_is_still_on_the_ground(self) -> None:
        fight = self._fight(strength=1)
        foe = fight.foes[0]
        foe.attributes["strength"] = 10.0
        foe.lost += ["leg_left", "shin_right"]
        foe.staunched = True
        fight.hero.wait = 0.0
        kinds = []
        for _ in range(400):
            kinds += [event.kind for event in fight.update(0.05)]
            self.assertGreater(foe.floored, 0.0 if THROWN_OFF not in kinds else -1.0)
        self.assertIn(THROWN_OFF, kinds)
        self.assertGreater(kinds.count(THROWN_OFF), 1, "and they are got down on again")
        fight.update(0.05)
        self.assertGreater(foe.floored, 0.0)


class EncounterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.data = load_combat()

    def test_raiders_are_of_the_levels_and_the_number_their_zone_has(self) -> None:
        for zone_id, zone in self.data.zones.items():
            counts, levels, kinds = set(), set(), set()
            for seed in range(300):
                band = raiders(self.data, zone_id, SimulationRNG(seed))
                counts.add(len(band))
                levels |= {foe.level for foe in band}
                kinds |= {foe.kind for foe in band}
                for foe in band:
                    self.assertTrue(all(1 <= value <= 10 for value in foe.attributes.values()))
                    self.assertEqual(foe.health, foe.max_health)
                    self.assertFalse(foe.hero)
            self.assertEqual(counts, set(range(1, zone.most + 1)), zone_id)
            self.assertEqual(levels, set(range(zone.levels[0], zone.levels[1] + 1)), zone_id)
            self.assertEqual(kinds, {kind.kind_id for kind in self.data.raiders.values() if kind.from_level <= zone.levels[1]}, zone_id)

    def test_a_raider_has_what_their_sort_and_their_level_give_them(self) -> None:
        thug, sparks = self.data.raiders["thug"], self.data.raiders["sparks"]

        def mean(kind, level: int, what) -> float:
            return sum(what(raider(self.data, kind, level, SimulationRNG(seed))) for seed in range(200)) / 200

        self.assertGreater(mean(thug, 5, lambda foe: foe.max_health), mean(thug, 1, lambda foe: foe.max_health) + 30)
        self.assertGreater(mean(thug, 3, lambda foe: foe.attributes["strength"]), mean(thug, 3, lambda foe: foe.attributes["mind"]) + 1)
        self.assertGreater(mean(sparks, 4, lambda foe: foe.attributes["mind"]), mean(sparks, 4, lambda foe: foe.attributes["strength"]) + 1)
        carried = {raider(self.data, thug, 1, SimulationRNG(seed)).weapon.weapon_id for seed in range(50)}
        self.assertEqual(carried, {"fists"}, "at the first level, bare hands")
        later = {raider(self.data, thug, 5, SimulationRNG(seed)).weapon.weapon_id for seed in range(80)}
        self.assertEqual(later, {"baton", "sledge"})
        self.assertEqual({raider(self.data, sparks, 4, SimulationRNG(seed)).weapon.kind for seed in range(20)}, {"energy"})

    def test_what_is_left_of_it(self) -> None:
        won = lost = dead = maimed = kits = 0
        for seed in range(600):
            rng = SimulationRNG(seed)
            who = hero(self.data, "Sergio", EVEN, "baton")
            fight = Fight(self.data, who, raiders(self.data, "summit", rng), rng)
            fight.resolve()
            after = aftermath(self.data, fight, rng)
            self.assertEqual(after.outcome, fight.outcome)
            self.assertTrue(after.told("Sergio"))
            if fight.outcome == WON:
                won += 1
                if not all(foe.beast for foe in fight.foes):
                    self.assertGreater(after.loot[self.data.tuning.scrap], 0)
                tuning = self.data.tuning
                self.assertLessEqual(set(after.loot), {tuning.scrap, tuning.kit, tuning.beast_loot, *self.data.weapons})
                kits += after.loot.get(tuning.kit, 0)
                self.assertEqual(after.experience, self.data.tuning.experience_per_level * sum(foe.level for foe in fight.foes))
                self.assertFalse(after.robbed or after.died)
                self.assertEqual(after.health, who.health, "what they lost in it is lost")
            elif fight.outcome == LOST:
                lost += 1
                self.assertTrue(after.robbed)
                self.assertEqual(after.loot, {})
                dead += after.died
                maimed += after.maimed is not None
                self.assertFalse(after.died and after.maimed)
                if after.maimed is not None:
                    self.assertEqual(after.lost, [after.maimed], "what was taken of them is what they are without")
            else:
                self.assertFalse(after.robbed or after.loot)
        self.assertGreater(won, 50)
        self.assertGreater(lost, 50)
        self.assertGreater(kits, won * 0.2, "now and then one of them had something to mend with on them")
        self.assertTrue(0.04 < dead / lost < 0.25, dead / lost)
        self.assertTrue(0.06 < maimed / lost < 0.32, maimed / lost)

    def test_before_a_blow_is_struck_they_can_be_paid_or_run_from(self) -> None:
        who = hero(self.data, "Sergio", EVEN, "baton")
        paid = meet(self.data, who, "ruins", SimulationRNG(4), choice=PAY, carried=10)
        self.assertEqual((paid.outcome, paid.health), (PAY, 100.0))
        self.assertIn(paid.paid, (2, 4))
        broke = meet(self.data, hero(self.data, "Sergio", EVEN, "baton"), "ruins", SimulationRNG(4), choice=PAY, carried=0)
        self.assertNotEqual(broke.outcome, PAY, "with nothing to pay with, it is a fight")
        ran = [meet(self.data, hero(self.data, "S", EVEN, "baton"), "forest", SimulationRNG(seed), choice=RUN).outcome for seed in range(80)]
        self.assertGreater(ran.count(FLED), 45, "likelier before a blow is struck than in the thick of it")
        self.assertLess(ran.count(FLED), 80, "and never certain")
        self.assertEqual(price(self.data, raiders(self.data, "forest", SimulationRNG(1))), self.data.tuning.pay_per_raider)

    def test_left_to_decide_the_brave_fight_and_the_timid_pay_or_run(self) -> None:
        rng = SimulationRNG(2)
        band = [raider(self.data, self.data.raiders["thug"], 1, rng) for _ in range(2)]
        fight = Fight(self.data, hero(self.data, "Sergio", EVEN, "baton"), band, rng)
        self.assertEqual(decide_alone(fight, 0.9, 10, self.data), FIGHT)
        self.assertEqual(decide_alone(fight, 0.1, 10, self.data), PAY)
        self.assertEqual(decide_alone(fight, 0.1, 0, self.data), RUN)
        same = [meet(self.data, hero(self.data, "S", EVEN, "baton"), "plant", SimulationRNG(9)).told("S") for _ in range(2)]
        self.assertEqual(same[0], same[1])


if __name__ == "__main__":
    unittest.main()
