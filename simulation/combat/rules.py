"""A fight out there: everybody strikes by themselves, each at their own pace, and now and then
there is a telling blow for whoever is watching to land.

One of the settlement's against one to three raiders, all of them at it at once, along a
line. Whoever fights at close quarters has to get right up to whoever they hit; whoever
fires does so from where they stand. Somebody with both a weapon for the hand and one to
fire uses each as it serves: they fire while there is ground between, and strike once there
is none. A hard blow makes whoever takes it reel, and a harder one puts them on the ground
for a while.

Right up to somebody, they can be shoved: it does next to no harm and sends them back, and
may put them on the ground. A telling blow may take a part off whoever it lands on: an arm
or a leg, and a head only with the blow that kills. Whoever has lost a part bleeds, a little
every second, and is the worse at whatever that part was for.

Left alone it goes to its end by itself: whoever was sent out picks who to hit, patches
themselves up when they are badly off, and runs for it when there is nothing else left.
Whoever watches can say who is hit, stop the mark of a telling blow, shove, hand over a
medkit or call the run.

No pygame here. Time is whatever seconds `update` is handed, and luck the `SimulationRNG`
the fight was made with: the same seed and the same presses are the same fight.
"""

from dataclasses import dataclass, field

from simulation.rng import SimulationRNG
from simulation.combat.model import MELEE, CombatData, Fighter, Tuning, Weapon

WON, LOST, FLED = "won", "lost", "fled"
# What can happen in a fight, for whoever shows it.
HIT, DODGED, DOWN, CRIT_READY, HEALED, FLEE_FAILED, ENDED = "hit", "dodged", "down", "crit_ready", "healed", "flee_failed", "ended"
# A blow that made whoever took it reel, and one that put them on the ground.
REELED, FLOORED = "reeled", "floored"
# A shove, a part taken off (`said` is which), and what was lost of bleeding since it was last said.
SHOVED, SEVERED, BLED = "shoved", "severed", "bled"
# What they fire is empty; somebody on the ground is held there under blows (`said` is the
# two throws); and they throw whoever was on them off.
EMPTY, HELD, THROWN_OFF = "empty", "held", "thrown_off"
# What the hero fights with, of what they carry: only what is in the hand, only what is
# fired, or each as it serves.
HAND, GUN, BOTH = "hand", "gun", "both"


@dataclass(frozen=True)
class Event:
    kind: str
    # Whoever did it and whoever it was done to, as they stand in the fight: 0 is the hero.
    by: int = 0
    to: int = 0
    amount: float = 0.0
    # How many times over a telling blow told, and what is said of it. One and nothing for a plain blow.
    times: float = 1.0
    said: str = ""
    # The weapon it was done with, by ID, for a blow.
    weapon: str = ""


def score(fighter: Fighter, weapon: Weapon, tuning: Tuning) -> float:
    """What somebody is worth with a weapon: their attributes, each by how much the weapon goes by it."""
    shares = sum(weapon.scales.values())
    return sum(fighter.attribute(name, tuning.middle) * share for name, share in weapon.scales.items()) / shares


def power(fighter: Fighter, tuning: Tuning, weapon: Weapon | None = None) -> float:
    """How many times its own harm a weapon does in these hands: the one in their hand, unless another is said."""
    weapon = weapon or fighter.weapon
    return max(tuning.least_damage, 1.0 + tuning.damage_per_point * (score(fighter, weapon, tuning) - tuning.middle))


def gone(fighter: Fighter, limbs: tuple[tuple[str, ...], ...]) -> int:
    """How many of some limbs are of no use to somebody: with any part of one lost, it is none."""
    return sum(1 for limb in limbs if any(part in fighter.lost for part in limb))


def severable(fighter: Fighter, tuning: Tuning) -> list[str]:
    """The parts of their limbs that can still come off them: each limb can be cut through at
    any joint that is still on them, which is every one nearer the trunk than where it was
    last cut."""
    left = []
    for limb in (*tuning.arms, *tuning.legs):
        for part in limb:
            if part in fighter.lost:
                break
            left.append(part)
    return left


def sever_odds(part: str, tuning: Tuning) -> float:
    """How likely a part is to be the one that comes off, against the others that could: by
    how far out along its limb it is, the further the likelier, since less has to be cut
    through. Past the last that is written, as the last."""
    for limb in (*tuning.arms, *tuning.legs):
        if part in limb:
            return tuning.sever_odds[min(limb.index(part), len(tuning.sever_odds) - 1)]
    if part in tuning.deadly:
        return tuning.deadly_odds[min(tuning.deadly.index(part), len(tuning.deadly_odds) - 1)]
    return 1.0


def stumps(fighter: Fighter, tuning: Tuning) -> list[str]:
    """Where they are open: for each limb the part lost nearest the trunk, since whatever was
    lost further out went with it, and whatever else has come off."""
    found = [next(part for part in limb if part in fighter.lost) for limb in (*tuning.arms, *tuning.legs) if gone(fighter, (limb,))]
    return found + [part for part in tuning.deadly if part in fighter.lost]


def of_leg(part: str, tuning: Tuning) -> bool:
    """Whether a part is one of a leg."""
    return any(part in limb for limb in tuning.legs)


def interval(fighter: Fighter, tuning: Tuning, weapon: Weapon | None = None) -> float:
    """Seconds from one blow of theirs to the next: quick hands are quicker, and an arm gone is slower."""
    quick = 1.0 + tuning.speed_per_point * (fighter.attribute("dexterity", tuning.middle) - tuning.middle)
    slower = 1.0 + tuning.arm_slower * gone(fighter, tuning.arms)
    return (weapon or fighter.weapon).seconds / max(0.4, quick) * slower


def dodge_chance(fighter: Fighter, tuning: Tuning) -> float:
    """How likely they are to get out of the way of a blow. Nobody does on one leg."""
    if gone(fighter, tuning.legs):
        return 0.0
    chance = tuning.dodge + tuning.dodge_per_point * (fighter.attribute("dexterity", tuning.middle) - tuning.middle)
    return min(tuning.most_dodge, max(0.0, chance))


def walk_speed(fighter: Fighter, tuning: Tuning) -> float:
    """Paces a second somebody closes with whoever they are after: less for each leg gone, and none with none."""
    legs = gone(fighter, tuning.legs)
    if legs >= len(tuning.legs):
        return 0.0
    speed = max(0.5, tuning.walk + tuning.walk_per_point * (fighter.attribute("dexterity", tuning.middle) - tuning.middle))
    return speed * tuning.leg_slower**legs


def steadiness(fighter: Fighter, tuning: Tuning) -> float:
    """How many times as hard as anybody they are to knock off their feet: a strong constitution stands firmer."""
    return max(0.5, 1.0 + tuning.steady_per_point * (fighter.attribute("constitution", tuning.middle) - tuning.middle))


def can_strike(fighter: Fighter, tuning: Tuning) -> bool:
    """Whether they have an arm left to strike with."""
    return gone(fighter, tuning.arms) < len(tuning.arms)


def bleeding(fighter: Fighter, tuning: Tuning) -> float:
    """What somebody loses a second to the parts they have lost, until it is seen to."""
    return 0.0 if fighter.staunched or fighter.down else tuning.bleed * len(stumps(fighter, tuning))


def crit_times(tuning: Tuning, off: float) -> tuple[float, str]:
    """How many times over a telling blow tells for a mark stopped that far off the middle,
    from 0 at it to 1 at either end, and what is said of it."""
    off = min(1.0, abs(off))
    for reach, times, said in tuning.crit_marks:
        if off <= reach:
            return times, said
    return tuning.crit_marks[-1][1], tuning.crit_marks[-1][2]


def sever_chance(tuning: Tuning, weapon: Weapon, times: float) -> float:
    """How likely a telling blow with a weapon is to take a part off, for how many times over it tells."""
    for at_least, chance in tuning.crit_severs:
        if times >= at_least:
            return chance * weapon.severs
    return 0.0


def edge(attacker: Fighter, victim: Fighter, tuning: Tuning) -> float:
    """How much stronger somebody is than whoever they strike stands firm: points of strength
    over points of constitution."""
    return attacker.attribute("strength", tuning.middle) - victim.attribute("constitution", tuning.middle)


def foe_crit_chance(attacker: Fighter, victim: Fighter, tuning: Tuning) -> float:
    """How likely a blow of somebody who is not the hero is to be a telling one: the likelier
    the stronger they are for how firm whoever takes it stands."""
    chance = tuning.foe_crit + tuning.foe_crit_per_point * edge(attacker, victim, tuning)
    return min(tuning.most_foe_crit, max(0.0, chance))


def foe_sever_chance(attacker: Fighter, victim: Fighter, tuning: Tuning, weapon: Weapon, times: float) -> float:
    """How likely a telling blow of somebody who is not the hero is to take a part off: less
    than one of the hero's with the same weapon, and the likelier the stronger they are for
    how firm whoever takes it stands."""
    stronger = max(0.0, 1.0 + tuning.foe_sever_per_point * edge(attacker, victim, tuning))
    return min(1.0, sever_chance(tuning, weapon, times) * tuning.foe_severs * stronger)


@dataclass
class Fight:
    """One fight, as it stands. `fighters[0]` is the hero and the rest are against them."""

    data: CombatData
    hero: Fighter
    foes: list[Fighter]
    rng: SimulationRNG
    medkits: int = 0
    # Whether nobody is watching: then they also run for it by themselves when all is lost.
    hands_off: bool = False
    outcome: str | None = None
    # How full the measure of a telling blow is, from 0 to 1.
    crit: float = 0.0
    # Who the player said to hit, by where they stand among the foes. None for whoever they pick.
    chosen: int | None = None
    seconds: float = 0.0
    _crit_told: bool = False
    _telling: tuple[float, str] | None = None
    # Whether the player has said to shove whoever is in front of them, the next thing they do.
    _shove_asked: bool = False
    # What each has bled since it was last said, by where they stand in the fight, and who to
    # put it down to if it is the end of them.
    _bled: dict[int, float] = field(default_factory=dict)
    _bled_by: dict[int, int] = field(default_factory=dict)
    # What the hero fights with, of what they carry.
    stance: str = BOTH
    # Who is on top of whom, pounding them where they lie: by where each stands in the fight.
    pins: dict[int, int] = field(default_factory=dict)
    events: list[Event] = field(default_factory=list)

    def __post_init__(self) -> None:
        tuning = self.tuning
        # They come on one another with ground between: the hero at one end of it and the
        # raiders at the other, a little apart from one another.
        self.hero.at = 0.0
        gap = self.rng.uniform(*tuning.start_gap)
        for index, foe in enumerate(self.foes):
            foe.at = gap + index * tuning.rank_gap
        for fighter in self.fighters:
            weapon = self._first(fighter)
            opening = self.data.kinds[weapon.kind].opening
            fighter.wait = self._pace(fighter, weapon) * opening * self.rng.uniform(0.8, 1.2)
        if not self.foes:
            self.outcome = WON
        if self.hero.gun is None:
            self.stance = BOTH

    @property
    def tuning(self) -> Tuning:
        return self.data.tuning

    @property
    def fighters(self) -> list[Fighter]:
        return [self.hero, *self.foes]

    def standing(self) -> list[int]:
        """Which of the foes are still alive, by where they stand among them."""
        return [index for index, foe in enumerate(self.foes) if not foe.down]

    def _first(self, fighter: Fighter) -> Weapon:
        """What somebody opens with: what they fire, if they carry anything to fire."""
        return fighter.gun if fighter.gun is not None else fighter.weapon

    def _pace(self, fighter: Fighter, weapon: Weapon | None = None) -> float:
        """Seconds between two blows of somebody, as things stand: raiders who are several get
        in one another's way."""
        seconds = interval(fighter, self.tuning, weapon)
        if fighter.hero:
            return seconds
        return seconds * (1.0 + self.tuning.many_slower * max(0, len(self.standing()) - 1))

    # ----- where everybody is -----

    def gap(self, one: Fighter, other: Fighter) -> float:
        """How much ground there is between two of them, in paces."""
        return abs(one.at - other.at)

    def in_reach(self, one: Fighter, other: Fighter) -> bool:
        """Whether one can strike the other with what is in their hand: they are right up to them."""
        return self.gap(one, other) <= self.tuning.reach + 1e-6

    def weapon_for(self, fighter: Fighter, victim: Fighter) -> Weapon | None:
        """What somebody uses on somebody else from where they stand: what is in their hand if
        they are right up to them or it is fired, or else what they carry to fire. None with
        only a weapon for the hand and ground still between, and for whoever has no arm left."""
        if not can_strike(fighter, self.tuning):
            return None
        fired = self.fired(fighter)
        loaded = fired if fired is not None and (fired.ammo <= 0 or fighter.rounds > 0) else None
        # What is in the hand for close quarters: with only something to fire and that
        # empty, bare hands.
        hand = fighter.weapon if fighter.weapon.kind == MELEE else self.data.weapons[self.tuning.bare_hands]
        stance = self.stance if fighter.hero and fighter.gun is not None else BOTH
        if stance == GUN and loaded is not None:
            return loaded
        if stance == HAND:
            loaded = None
        if fighter.weapon.kind != MELEE and loaded is not None:
            return loaded
        if self.in_reach(fighter, victim):
            return hand
        return loaded

    def fired(self, fighter: Fighter) -> Weapon | None:
        """What somebody fires, if they carry anything to fire."""
        if fighter.gun is not None:
            return fighter.gun
        return fighter.weapon if fighter.weapon.kind != MELEE else None

    def stances(self) -> list[str]:
        """The ways the hero can fight with what they carry: one, unless they carry both a
        weapon for the hand and something to fire."""
        return [BOTH, HAND, GUN] if self.hero.gun is not None else [BOTH]

    def set_stance(self, stance: str) -> bool:
        """The player says what the hero fights with. Says whether they carry it."""
        if stance not in self.stances():
            return False
        self.stance = stance
        return True

    def next_stance(self) -> str:
        """Go on to the next way of fighting there is, and say which it is."""
        ways = self.stances()
        self.stance = ways[(ways.index(self.stance) + 1) % len(ways)] if self.stance in ways else ways[0]
        return self.stance

    def _spend(self, index: int, fighter: Fighter, weapon: Weapon) -> None:
        """Use up a round of what was just fired, and say so when it was the last."""
        if weapon.ammo <= 0:
            return
        fighter.rounds = max(0, fighter.rounds - 1)
        if fighter.rounds == 0:
            self.events.append(Event(EMPTY, index, index, weapon=weapon.weapon_id))

    # ----- somebody on the ground -----

    def can_pound(self, fighter: Fighter, victim: Fighter) -> bool:
        """Whether somebody can get down on somebody else and pound them where they lie: the
        other is on the ground and right up to them, and they are on their feet with a hand free."""
        tuning = self.tuning
        if victim.floored <= 0.0 or victim.down or fighter.floored > 0.0 or not can_strike(fighter, tuning):
            return False
        return self.in_reach(fighter, victim) and gone(fighter, tuning.legs) < len(tuning.legs)

    def pound_weapon(self, fighter: Fighter, telling: tuple[float, str] | None = None) -> Weapon:
        """What somebody brings down on whoever they are on top of: their fists, but for a
        beast, which has its claws for hands, and for a telling blow, which is struck with
        what they carry in the hand."""
        if fighter.beast or (telling is not None and fighter.weapon.kind == MELEE):
            return fighter.weapon
        return self.data.weapons[self.tuning.bare_hands]

    def pound_pace(self, fighter: Fighter) -> float:
        """Seconds between two blows of somebody on top of somebody else: fists come down
        fast, and claws as fast as claws ever do."""
        tuning = self.tuning
        if fighter.beast:
            return self._pace(fighter, fighter.weapon)
        return tuning.pound_seconds * (1.0 + tuning.arm_slower * gone(fighter, tuning.arms))

    def throws_off(self, under: int, mine: int, over: int, theirs: int) -> bool:
        """Whether whoever is under gets whoever is on them off, with what each threw and the
        strength of each: they have to throw the more, over the weight that is on them, and
        the top face of the die always does."""
        return under >= self.tuning.pound_die or under + mine > over + theirs + self.tuning.pound_edge

    def _get_on(self, by: int, to: int, at_once: bool = False) -> None:
        """Somebody gets down on whoever is on the ground: it takes them a moment, whatever
        they were about, and whoever is under is going nowhere meanwhile."""
        if self.pins.get(by) == to:
            return
        fighters = self.fighters
        self.pins[by] = to
        if not at_once:
            fighters[by].wait = self.tuning.pound_down
        self._hold(fighters[by], fighters[to])

    def _hold(self, attacker: Fighter, victim: Fighter) -> None:
        """Keep whoever is under on the ground until the next blow has come down on them."""
        victim.floored = max(victim.floored, max(0.0, attacker.wait) + self.pound_pace(attacker) + 0.2)

    def _pound(self, by: int, to: int, telling: tuple[float, str] | None = None) -> None:
        """A blow comes down on whoever is on the ground, and then they see whether they can
        throw whoever is on them off: a die and their strength each."""
        fighters = self.fighters
        attacker, victim = fighters[by], fighters[to]
        tuning = self.tuning
        self.pins[by] = to
        filled = self.crit
        self._strike(by, to, self.pound_weapon(attacker, telling), telling)
        if telling is None and self.crit > filled:
            # Fists come down fast: each fills less of the telling blow than a blow does.
            self.crit = filled + (self.crit - filled) * tuning.pound_crit
        if victim.down or self.outcome is not None:
            self.pins.pop(by, None)
            return
        under = self.rng.randint(1, tuning.pound_die)
        over = self.rng.randint(1, tuning.pound_die)
        mine, theirs = round(victim.attribute("strength", tuning.middle)), round(attacker.attribute("strength", tuning.middle))
        said = f"{under}+{mine} contra {over}+{theirs}"
        if self.throws_off(under, mine, over, theirs):
            self.pins.pop(by, None)
            # Off them, and up, if they have a leg to get up on.
            victim.floored = 0.0
            self._push(attacker, victim, tuning.pound_push)
            attacker.wait += tuning.reel_seconds
            self.events.append(Event(THROWN_OFF, to, by, said=said))
        else:
            self._hold(attacker, victim)
            self.events.append(Event(HELD, by, to, said=said))

    def target(self) -> int | None:
        """Who the hero hits next: whoever the player said, if they still stand, or else
        whoever they pick themselves, which is whoever is nearest going down."""
        up = self.standing()
        if not up:
            return None
        if self.chosen in up:
            return self.chosen
        return min(up, key=lambda index: (self.foes[index].health, index))

    def choose(self, index: int | None) -> bool:
        """The player says who is to be hit. Says whether there is such a one standing."""
        if index is not None and index not in self.standing():
            return False
        self.chosen = index
        return True

    # ----- what the player can do -----

    @property
    def crit_ready(self) -> bool:
        return self.crit >= 1.0 and self.outcome is None

    def land_crit(self, off: float) -> bool:
        """The player stops the mark of a telling blow, that far off the middle of its bar:
        the hero's next blow comes at once, and tells that many times over."""
        if not self.crit_ready:
            return False
        self._telling = crit_times(self.tuning, off)
        self.crit, self._crit_told = 0.0, False
        self.hero.wait = 0.0
        return True

    def heal(self) -> bool:
        """A medkit, if there is one and it is any use: it mends, and stops what bleeds."""
        hero = self.hero
        whole = hero.health >= hero.max_health and bleeding(hero, self.tuning) <= 0.0
        if self.outcome is not None or self.medkits <= 0 or whole:
            return False
        self.medkits -= 1
        before = hero.health
        hero.health = min(hero.max_health, hero.health + self.tuning.medkit)
        hero.staunched = True
        self.events.append(Event(HEALED, amount=hero.health - before))
        return True

    def can_shove(self) -> bool:
        """Whether the hero could shove whoever they are after right now: they are right up
        to them, on their feet, and have their breath back from the last."""
        target = self.target()
        hero = self.hero
        if self.outcome is not None or target is None or hero.floored > 0.0 or hero.shove_wait > 0.0:
            return False
        return self.in_reach(hero, self.foes[target]) and can_strike(hero, self.tuning)

    def shove(self) -> bool:
        """The player says to shove whoever is in front of them: it is the next thing they do."""
        if not self.can_shove():
            return False
        self._shove_asked = True
        self.hero.wait = 0.0
        return True

    def flee_chance(self, before: bool = False) -> float:
        """How likely the hero is to get away: quick feet help, and each raider is one more to slip."""
        tuning = self.tuning
        chance = tuning.flee + tuning.flee_per_point * (self.hero.attribute("dexterity", tuning.middle) - tuning.middle)
        chance -= tuning.flee_per_foe * max(0, len(self.standing()) - 1)
        chance += tuning.flee_before if before else 0.0
        # Nobody runs far on one leg.
        return min(0.95, max(0.05, chance)) * tuning.leg_slower ** gone(self.hero, tuning.legs)

    def flee(self, before: bool = False) -> bool:
        """Run for it. It may not come off: then they have turned their back for nothing."""
        if self.outcome is not None:
            return False
        if self.rng.random() < self.flee_chance(before):
            self._end(FLED)
            return True
        self.hero.wait += self.tuning.flee_stumble_seconds
        self.events.append(Event(FLEE_FAILED))
        return False

    # ----- blows -----

    def _end(self, outcome: str) -> None:
        self.outcome = outcome
        self.events.append(Event(ENDED, said=outcome))

    def _push(self, victim: Fighter, attacker: Fighter, paces: float) -> None:
        """Send somebody back from whoever struck them."""
        away = 1.0 if victim.at >= attacker.at else -1.0
        victim.at += away * paces

    def _floor(self, by: int, to: int, amount: float, weapon_id: str = "", push: float | None = None) -> None:
        fighters = self.fighters
        victim = fighters[to]
        victim.floored = max(victim.floored, self.tuning.floored_seconds)
        self._push(victim, fighters[by], self.tuning.floored_push if push is None else push)
        self.events.append(Event(FLOORED, by, to, amount, weapon=weapon_id))

    def _sever(self, by: int, to: int, weapon: Weapon, times: float, killed: bool) -> bool:
        """See whether a telling blow takes a part off whoever it landed on, and take it: a
        limb, through any joint it still has. A head comes off only with the blow that kills,
        or they are cut in two by it, and a limb only with one that does not. Says whether a
        part came off."""
        tuning = self.tuning
        attacker, victim = self.fighters[by], self.fighters[to]
        chance = sever_chance(tuning, weapon, times) if attacker.hero else foe_sever_chance(attacker, victim, tuning, weapon, times)
        if self.rng.random() >= chance:
            return False
        left = [part for part in tuning.deadly if part not in victim.lost] if killed else severable(victim, tuning)
        if not left:
            return False
        # The smaller the part, the likelier it is the one: a hand sooner than a whole arm.
        part = self.rng.choices(left, [sever_odds(each, tuning) for each in left])[0]
        if part in victim.lost:
            return False
        victim.lost.append(part)
        victim.staunched = False
        self._bled_by[to] = by
        self.events.append(Event(SEVERED, by, to, times=times, said=part, weapon=weapon.weapon_id))
        return True

    def _strike(self, by: int, to: int, weapon: Weapon, telling: tuple[float, str] | None = None) -> None:
        fighters = self.fighters
        attacker, victim = fighters[by], fighters[to]
        tuning = self.tuning
        if telling is None and victim.floored <= 0.0 and self.rng.random() < dodge_chance(victim, tuning):
            # A telling blow is never got out of the way of, and nobody on the ground gets out of the way of anything.
            self.events.append(Event(DODGED, by, to, weapon=weapon.weapon_id))
            return
        times, said = telling or (1.0, "")
        amount = self.rng.uniform(*weapon.damage) * power(attacker, tuning, weapon) * times
        victim.health = max(0.0, victim.health - amount)
        self.events.append(Event(HIT, by, to, amount, times, said, weapon.weapon_id))
        if attacker.hero and telling is None:
            self.crit = min(1.0, self.crit + tuning.crit_per_hit)
        if victim.down:
            if telling is not None:
                self._sever(by, to, weapon, times, killed=True)
            self.events.append(Event(DOWN, by, to, weapon=weapon.weapon_id))
            return
        # A telling blow may take a part off: a leg gone is a fall, whatever else.
        if telling is not None and self._sever(by, to, weapon, times, killed=False):
            if of_leg(victim.lost[-1], tuning):
                self._floor(by, to, amount, weapon.weapon_id)
            else:
                victim.wait += tuning.reel_seconds
                self.events.append(Event(REELED, by, to, amount, weapon=weapon.weapon_id))
            return
        # How hard it landed for somebody of their size: what makes them reel, or go down.
        landed = amount / victim.max_health / steadiness(victim, tuning)
        heavy = weapon.kind == MELEE
        if victim.floored > 0.0:
            return
        # What is fired goes through somebody more than it throws them: it takes more of it to floor them.
        floors_at = tuning.floors_at * (1.0 if heavy else tuning.shot_floors)
        if landed >= floors_at or (times >= tuning.crit_floors and heavy):
            self._floor(by, to, amount, weapon.weapon_id)
        elif landed >= tuning.reels_at or times > 1.0:
            victim.wait += tuning.reel_seconds
            if heavy:
                self._push(victim, attacker, tuning.reel_push)
            self.events.append(Event(REELED, by, to, amount, weapon=weapon.weapon_id))

    def shove_floors(self, attacker: Fighter, victim: Fighter) -> float:
        """How likely a shove is to put somebody on the ground: strength against how firm they stand."""
        tuning = self.tuning
        edge = attacker.attribute("strength", tuning.middle) - victim.attribute("constitution", tuning.middle)
        chance = tuning.shove_floors + tuning.shove_floors_per_point * edge
        # On one leg anybody goes over.
        return 1.0 if gone(victim, tuning.legs) else min(0.9, max(0.05, chance))

    def _shove(self, by: int, to: int) -> None:
        """Shove somebody who is right up to them: next to no harm, but they go back, late with
        their next blow, and may go down."""
        fighters = self.fighters
        attacker, victim = fighters[by], fighters[to]
        tuning = self.tuning
        attacker.shove_wait = tuning.shove_rest
        attacker.wait += tuning.shove_seconds
        amount = self.rng.uniform(*tuning.shove_damage)
        victim.health = max(1.0, victim.health - amount)
        far = max(0.5, tuning.shove_push + tuning.shove_push_per_point * (attacker.attribute("strength", tuning.middle) - tuning.middle))
        self.events.append(Event(SHOVED, by, to, amount))
        if victim.floored <= 0.0 and self.rng.random() < self.shove_floors(attacker, victim):
            self._floor(by, to, amount, push=far)
            return
        self._push(victim, attacker, far)
        victim.wait += tuning.reel_seconds
        self.events.append(Event(REELED, by, to, amount))

    def _close(self, fighter: Fighter, victim: Fighter, seconds: float) -> None:
        """Walk up to somebody, and stop right up to them."""
        way = 1.0 if victim.at > fighter.at else -1.0
        step = min(walk_speed(fighter, self.tuning) * seconds, max(0.0, self.gap(fighter, victim) - self.tuning.reach))
        fighter.at += way * step

    def _hero_acts(self, seconds: float) -> None:
        tuning, hero = self.tuning, self.hero
        to = self.target()
        if to is None:
            return
        victim = self.foes[to]
        weapon = self.weapon_for(hero, victim)
        if weapon is None:
            # Nothing to fire and ground between: they go for them, readying the blow as they go.
            self._shove_asked = False
            self._close(hero, victim, seconds)
            hero.wait = max(0.0, hero.wait - seconds)
            return
        pounding = weapon.kind == MELEE and self.can_pound(hero, victim)
        if not pounding:
            self.pins.pop(0, None)
        else:
            # A telling blow that is ready comes down at once, from wherever they are.
            self._get_on(0, to + 1, at_once=self._telling is not None)
        hero.wait -= seconds
        while hero.wait <= 0.0 and self.outcome is None and not victim.down:
            badly_off = hero.health / hero.max_health
            hurt = badly_off < tuning.heals_below or bleeding(hero, tuning) > 0.0
            if self._telling is None and hurt and self.medkits > 0:
                # They see to themselves before they go on, and to whatever bleeds: it costs them half a blow.
                self.heal()
                hero.wait += self._pace(hero, weapon) * 0.5
                continue
            if self._telling is None and self.hands_off and badly_off < tuning.flees_below:
                # Nothing left but to run: got away or not, that was their turn.
                self.flee()
                hero.wait = max(hero.wait, 0.05)
                return
            # They shove if they are told to; and by themselves, with something to fire and
            # somebody on top of them, to get room to fire it.
            fires = self.stance != HAND and hero.gun is not None and (hero.gun.ammo <= 0 or hero.rounds > 0)
            crowded = fires and self._telling is None and victim.floored <= 0.0
            if (self._shove_asked or crowded) and self.in_reach(hero, victim) and hero.shove_wait <= 0.0:
                self._shove_asked = False
                self._shove(0, to + 1)
                return
            self._shove_asked = False
            telling, self._telling = self._telling, None
            if pounding and self.can_pound(hero, victim):
                # Down on them with their fists, for as long as they can be held there.
                self._pound(0, to + 1, telling)
                hero.wait += self.pound_pace(hero)
                continue
            self._strike(0, to + 1, weapon, telling)
            self._spend(0, hero, weapon)
            hero.wait += self._pace(hero, weapon)

    def _foe_acts(self, index: int, foe: Fighter, seconds: float) -> None:
        tuning = self.tuning
        weapon = self.weapon_for(foe, self.hero)
        if weapon is None:
            if can_strike(foe, tuning):
                self._close(foe, self.hero, seconds)
                foe.wait = max(0.0, foe.wait - seconds)
            return
        pounding = weapon.kind == MELEE and self.can_pound(foe, self.hero)
        if not pounding:
            self.pins.pop(index, None)
        else:
            self._get_on(index, 0)
        foe.wait -= seconds
        while foe.wait <= 0.0 and self.outcome is None and not self.hero.down and foe.floored <= 0.0:
            on_them = pounding and self.can_pound(foe, self.hero)
            shoves = weapon.kind == MELEE and foe.shove_wait <= 0.0 and self.hero.floored <= 0.0
            if shoves and self.rng.random() < tuning.raider_shoves:
                self._shove(index, 0)
                return
            # Now and then one of theirs is a telling blow too: the likelier the stronger they
            # are for how firm the hero stands.
            telling = None
            if self.rng.random() < foe_crit_chance(foe, self.hero, tuning):
                perfect = self.rng.random() < tuning.foe_perfect
                telling = (tuning.crit_marks[0][1], "¡Brutal!") if perfect else (tuning.crit_marks[1][1], "¡Crítico!")
            if on_them:
                # Down on the hero where they lie, for as long as they can be held there.
                self._pound(index, 0, telling)
                foe.wait += self.pound_pace(foe)
                continue
            self._strike(index, 0, weapon, telling)
            self._spend(index, foe, weapon)
            foe.wait += self._pace(foe, weapon)

    def _bleed(self, index: int, fighter: Fighter, seconds: float) -> None:
        """Take from somebody what the parts they have lost cost them, and say so now and then."""
        losing = bleeding(fighter, self.tuning)
        if losing <= 0.0:
            return
        lost = min(fighter.health, losing * seconds)
        fighter.health -= lost
        self._bled[index] = self._bled.get(index, 0.0) + lost
        if self._bled[index] >= 1.0 or fighter.down:
            self.events.append(Event(BLED, self._bled_by.get(index, 0), index, self._bled.pop(index)))
        if fighter.down:
            self.events.append(Event(DOWN, self._bled_by.get(index, 0), index))

    def update(self, seconds: float) -> list[Event]:
        """Let time pass. Returns what happened in it, in order, and forgets it."""
        step = 0.05
        left = max(0.0, seconds)
        tuning = self.tuning
        while left > 1e-9 and self.outcome is None:
            took = min(step, left)
            left -= took
            self.seconds += took
            self.crit = min(1.0, self.crit + tuning.crit_per_second * took)
            for index, fighter in enumerate(self.fighters):
                if fighter.down or self.outcome is not None:
                    continue
                fighter.shove_wait = max(0.0, fighter.shove_wait - took)
                self._bleed(index, fighter, took)
                legless = gone(fighter, tuning.legs) >= len(tuning.legs)
                if fighter.down:
                    pass
                elif fighter.floored > 0.0 or legless:
                    # On the ground: nothing to be done until they are up again, and with no
                    # leg to stand on they are not getting up. Whoever was on somebody is off them.
                    self.pins.pop(index, None)
                    fighter.floored = max(0.0, fighter.floored - took) if not legless else max(fighter.floored, 0.1)
                elif fighter.hero:
                    self._hero_acts(took)
                else:
                    self._foe_acts(index, fighter, took)
                if self.hero.down:
                    self._end(LOST)
                elif not self.standing():
                    self._end(WON)
            # Nobody is on top of anybody who is up again or done for, and nobody who is done for is.
            fighters = self.fighters
            for by, to in list(self.pins.items()):
                if fighters[by].down or fighters[by].floored > 0.0 or fighters[to].down or fighters[to].floored <= 0.0:
                    del self.pins[by]
            if self.crit >= 1.0 and not self._crit_told and self.outcome is None:
                # Full, by a blow or by waiting: said once, and it waits to be landed.
                self._crit_told = True
                self.events.append(Event(CRIT_READY))
        told, self.events = self.events, []
        return told

    def resolve(self, limit: float = 600.0) -> str:
        """Go to the end of it with nobody watching. Returns how it ended."""
        self.hands_off = True
        while self.outcome is None and self.seconds < limit:
            self.update(1.0)
        if self.outcome is None:
            # Nobody is left standing there for ten minutes: they part.
            self._end(FLED)
        self.events = []
        return self.outcome
