"""A fight out there, on screen (P80): seen from the side where the walk was, everybody
striking by themselves, with the measure of a telling blow to fill and a mark to stop.

Nothing here decides anything of the fight: it belongs to the simulation, which is asked to
let it go on and told what the player presses, and what it says happened is what is shown.
Over it nothing is written but numbers: a telling blow is seen slowly, a part coming off
more slowly and from nearer, whoever is on the ground sees stars, and when the last one
falls that is said large.
"""

import math
import random
from dataclasses import dataclass

import pygame

from graphics.font import BitmapFont
from scenes.fight_look import BLOOD, BRUISE, BURN, Body, Look
from simulation.combat.model import MELEE, Fighter
from simulation.combat.raid_system import CRIT, FLEE, HANDS_OFF, HEAL, SHOVE, STANCE, TARGET
from simulation.combat.rules import (
    BLED,
    BOTH,
    DODGED,
    DOWN,
    FLEE_FAILED,
    FLOORED,
    GUN,
    HAND,
    HEALED,
    HELD,
    HIT,
    LOST,
    REELED,
    SEVERED,
    SHOVED,
    THROWN_OFF,
    WON,
    Event,
    Fight,
    bleeding,
)
from simulation.commands import FightActCommand, FightOnCommand, WatchFightCommand
from simulation.world import SimulationWorld

Color = tuple[int, int, int]

CHOOSING, FIGHTING, AIMING, OVER = "choosing", "fighting", "aiming", "over"
INK: Color = (26, 22, 20)
PAPER: Color = (242, 236, 220)
BONE: Color = (217, 210, 192)
DUST: Color = (163, 156, 143)
LAMP: Color = (227, 178, 60)
GLOW: Color = (245, 224, 138)
EMBER: Color = (217, 90, 69)
RED: Color = (163, 50, 47)
GORE: Color = (150, 16, 20)
LICHEN: Color = (163, 176, 106)
HERO_COLOR: Color = (60, 106, 132)
RAIDER_COLORS: dict[str, Color] = {
    "thug": (150, 70, 56), "cutter": (136, 96, 60), "gunner": (112, 104, 78), "sparks": (116, 80, 132),
    "monster": (52, 78, 60),
}
# How many pixels a pace of the fight is, as a share of how tall somebody stands: right up
# to one another, they all but touch.
PACE = 0.27
# Seconds a blow is seen coming before it lands and going back after, and numbers hang in the air.
WIND_UP, FOLLOW, WORDS = 0.22, 0.3, 1.1
# How far into whoever is struck the hand goes, in pixels: a blow that stops short is no blow.
INTO = 10.0
SHOVE_CLIP, SHOVE_SECONDS = "fight_kick", 0.36
POUND_CLIP, POUND_OUT, POUND_NEAR, POUND_SETTLE = "pound", 0.8, 14.0, 0.16
PANEL_TALL = 92
GRAVITY = 1500.0
MOST_POOLS = 90
# What comes out of where a part was: beats a second, drops a second between and with each,
# how fast, how wide in turns, and for how long out of whoever it was the end of.
JET_BEATS, JET_TRICKLE, JET_RATE = 1.7, 10.0, 130.0
JET_SLOW, JET_FAST, JET_SPREAD, JET_AFTER = 70.0, 330.0, 0.035, 2.6
STARS, STAR_RING, STAR_FLAT, STAR_OVER, STAR_SIZE, STAR_TURNS = 4, 30.0, 0.32, 34.0, 8.0, 0.8
# A part coming off: seconds of the player's own time (and for a head), how much of its pace
# time keeps, how near, how long to get there and back, and the bars that close on it.
SLOW_SECONDS, SLOW_HEAD_SECONDS, SLOW_PACE = 1.6, 2.3, 0.14
ZOOM, ZOOM_IN, ZOOM_OUT, BARS = 1.9, 0.16, 0.4, 56
CRIT_SECONDS, CRIT_ZOOM, CRIT_SHAKE = 0.9, 1.3, 0.5
KO, KO_SECONDS, KO_LANDS, KO_FROM, KO_SLOW, KO_SCALE = "KO", 1.6, 0.16, 2.6, 1.1, 22
# How long after it is over it goes on being looked at, and how long a press that came to
# nothing shows that it did.
AFTER_SECONDS, FAILED_SECONDS = 1.2, 0.6
SMALL, MIDDLE, LARGE = 2, 3, 5


@dataclass
class Word:
    text: str
    x: float
    y: float
    color: Color
    age: float = 0.0
    big: bool = False


@dataclass
class Shot:
    start: tuple[float, float]
    end: tuple[float, float]
    color: Color
    age: float = 0.0


@dataclass
class Drop:
    x: float
    y: float
    vx: float
    vy: float
    size: float
    lands: float


class FightArena:
    def __init__(
        self, world: SimulationWorld, look: Look, font: BitmapFont, size: tuple[int, int], resident_id: str, zone_id: str,
        gone_by: float = 0.0,
    ) -> None:
        self.world = world
        self.look = look
        self.font = font
        self.resident_id = resident_id
        self.zone_id = zone_id
        self.gone_by = gone_by
        self.screen = pygame.Surface(size)
        fight: Fight | None = world.apply_command(WatchFightCommand(resident_id))
        if fight is None:
            raise ValueError(f"{resident_id} has no fight on their hands")
        self.fight = fight
        self.data = world.registries.combat
        # With more than one thing to fight with, it is asked which before a blow is struck.
        self.state = CHOOSING if len(fight.stances()) > 1 else FIGHTING
        self.time = 0.0
        self.clock = 0.0
        self.ended_at: float | None = None
        self.aiming = 0.0
        self.words: list[Word] = []
        self.shots: list[Shot] = []
        self.drops: list[Drop] = []
        self.pools: list[tuple[float, float, float]] = []
        self.struck_at: dict[int, tuple[float, str]] = {}
        self.walked: dict[int, float] = {}
        self._at: dict[int, float] = {}
        self.shoved_at: dict[int, float] = {}
        self._drip: dict[int, float] = {}
        self.cut_at: dict[int, float] = {}
        self._last_down = 0
        self.pounds: dict[int, int] = {}
        self._lean: dict[int, float] = {}
        self._on: dict[int, float] = {}
        self.failed_at = -9.0
        self.shake = 0.0
        self.gore = 1.0
        self.slow_motion = True
        self.slow_age = self.slow_for = 0.0
        self.zoom_to = ZOOM
        self.focus = 0
        self.eye = (size[0] / 2, size[1] / 2)
        self._view = (self.screen.get_rect(), 1.0)
        self.ko_at: float | None = None
        self._ko_pictures: dict[Color, pygame.Surface] = {}
        self.scatter = random.Random(0)
        self.bodies: list[Body] = [look.body("hero", HERO_COLOR, hero=True)]
        self.bodies += [look.body(foe.kind, RAIDER_COLORS.get(foe.kind, (140, 80, 60))) for foe in fight.foes]
        for part in fight.hero.lost:
            # What they were already without, they stand there without.
            self.bodies[0].sever(part, 1.0, 0.0)
        self.bodies[0].pieces.clear()
        self.middle = self._span()
        self.buttons: dict[str, pygame.Rect] = {}
        self._place(0.0)

    # ----- where everything is -----

    @property
    def done(self) -> bool:
        """Whether there is nothing more of it to see."""
        return self.ended_at is not None and not self.slowing and self.time - self.ended_at >= KO_SECONDS + AFTER_SECONDS

    @property
    def ground(self) -> int:
        return self.look.ground(self.screen.get_size()) - PANEL_TALL // 3

    def tall(self, index: int = 0) -> float:
        fighter = self.fight.fighters[index] if 0 <= index < len(self.fight.fighters) else None
        kind = self.data.raiders.get(fighter.kind) if fighter is not None else None
        return self.screen.get_height() * self.look.figure * (kind.size if kind is not None else 1.0)

    @property
    def pace(self) -> float:
        return self.tall() * PACE

    def _span(self) -> float:
        ats = [fighter.at for fighter in self.fight.fighters if not fighter.down] or [0.0]
        return (min(ats) + max(ats)) / 2

    def spot(self, index: int) -> tuple[float, float]:
        wide = self.screen.get_width()
        x = wide / 2 + (self.fight.fighters[index].at - self.middle) * self.pace
        return (min(wide - 50.0, max(50.0, x)), float(self.ground))

    def box(self, index: int) -> pygame.Rect:
        x, y = self.spot(index)
        tall = self.tall(index)
        return pygame.Rect(round(x - tall * 0.3), round(y - tall), round(tall * 0.6), round(tall))

    def mark(self) -> float:
        turns = self.aiming * self.data.tuning.crit_sweeps_per_second
        return 1.0 - 2.0 * abs((turns % 2.0) - 1.0)

    def _faces_left(self, index: int) -> bool:
        fighters = self.fight.fighters
        if index == 0:
            target = self.fight.target()
            return target is not None and fighters[target + 1].at < fighters[0].at
        return fighters[0].at <= fighters[index].at

    def _victim(self, index: int) -> Fighter | None:
        fight = self.fight
        if index != 0:
            return fight.hero
        target = fight.target()
        return fight.foes[target] if target is not None else None

    def _place(self, seconds: float) -> None:
        """Say where every body stands this frame and what it is doing."""
        fight = self.fight
        live = self.state in (FIGHTING, AIMING)
        self.middle += (self._span() - self.middle) * min(1.0, seconds * 3.0)
        for index, fighter in enumerate(fight.fighters):
            body = self.bodies[index]
            moved = abs(fighter.at - self._at.get(index, fighter.at))
            self._at[index] = fighter.at
            x, y = self.spot(index)
            left = self._faces_left(index)
            way = -1.0 if left else 1.0
            clip, phase, exact = "idle", self.clock * 0.5 + index * 0.3, False
            victim = self._victim(index)
            using = fight.weapon_for(fighter, victim) if victim is not None and not fighter.down else None
            body.holding = (using or fighter.weapon).weapon_id
            when, weapon_id = self.struck_at.get(index, (-9.0, ""))
            since = self.clock - when
            under = fight.pins.get(index) if live and self.look.has_clip(POUND_CLIP) else None
            over = 0.0
            if under is not None:
                lies = self.bodies[under].chest()[0]
                way = 1.0 if lies >= x else -1.0
                left = way < 0.0
                over = lies - way * body.reach(POUND_CLIP)[1] * POUND_OUT - x
            lean = self._lean.get(index, 0.0)
            lean += (over - lean) * min(1.0, seconds * POUND_NEAR)
            self._lean[index] = lean
            x += lean
            blow = None
            if since < FOLLOW and weapon_id in self.data.weapons:
                weapon = self.data.weapons[weapon_id]
                peak, _ = body.reach(weapon.clip)
                blow = (weapon, peak + (0.999 - peak) * since / FOLLOW, 1.0 - since / FOLLOW)
            elif using is not None and fighter.wait < WIND_UP and fighter.floored <= 0.0 and live:
                peak, _ = body.reach(using.clip)
                coming = 1.0 - max(0.0, fighter.wait) / WIND_UP
                blow = (using, peak * coming, coming)
            shoving = self.clock - self.shoved_at.get(index, -9.0)
            if under is not None:
                # Down on them: a fist comes down with every blow, one and then the other.
                blow = None
                pace = max(0.05, fight.pound_pace(fighter))
                coming = 1.0 - min(1.0, max(0.0, fighter.wait) / pace)
                clip, phase = POUND_CLIP, ((self.pounds.get(index, 0) + coming) * 0.5) % 1.0
                exact = self.clock - self._on.get(index, self.clock) >= POUND_SETTLE
                body.holding = fighter.weapon.weapon_id if fighter.beast else ""
            elif shoving < SHOVE_SECONDS:
                blow = None
                clip, phase, exact = SHOVE_CLIP, shoving / SHOVE_SECONDS, True
            if blow is not None and victim is not None:
                weapon, phase, near = blow
                clip, exact = weapon.clip, True
                body.holding = weapon.weapon_id
                if weapon.kind == MELEE:
                    _, out = body.reach(weapon.clip)
                    short = abs(self.spot(fight.fighters.index(victim))[0] - x) - out + INTO
                    x += way * max(0.0, short) * near
            elif moved > 1e-4 and fighter.floored <= 0.0 and seconds > 0.0:
                self.walked[index] = self.walked.get(index, 0.0) + moved / 2.0
                clip, phase = "walk", self.walked[index]
            if fighter.floored <= 0.0 and not fighter.down and body.lying:
                body.got_up()
            elif fighter.floored > 0.0 and not fighter.down:
                body.hold_down(fighter.floored)
            body.stand(x, y, self.tall(index), left, clip, phase, exact)

    # ----- what is pressed -----

    def _act(self, act: str, value: float | str | None = None) -> bool:
        return bool(self.world.apply_command(FightActCommand(self.resident_id, act, value)))

    def key(self, key: int) -> bool:
        """Take a key. Says whether it was one of the fight's."""
        if self.state == OVER:
            return False
        if key == pygame.K_TAB:
            self._act(STANCE)
        elif self.state == CHOOSING:
            if key not in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE, pygame.K_1):
                return False
            self.state = FIGHTING
        elif key == pygame.K_SPACE:
            self.press_crit()
        elif key == pygame.K_q:
            self._act(HEAL)
        elif key == pygame.K_h:
            self._act(FLEE)
        elif key == pygame.K_e:
            self._act(SHOVE)
        elif key == pygame.K_a:
            self._act(HANDS_OFF, 0.0 if self.fight.hands_off else 1.0)
        elif key in (pygame.K_1, pygame.K_2, pygame.K_3):
            self._act(TARGET, key - pygame.K_1)
        else:
            return False
        return True

    def click(self, position: tuple[int, int]) -> bool:
        """Take a press at a place of its own picture. Says whether it was on anything."""
        for name, rect in self.buttons.items():
            if rect.collidepoint(position):
                self._button(name)
                return True
        if self.state in (FIGHTING, AIMING):
            for index in self.fight.standing():
                if self.box(index + 1).collidepoint(position):
                    self._act(TARGET, index)
                    return True
            if self.state == AIMING:
                self.press_crit()
                return True
        return False

    def _button(self, name: str) -> None:
        if name == "fight":
            self.state = FIGHTING
        elif name == "crit":
            self.press_crit()
        elif name == "heal":
            self._act(HEAL)
        elif name == "flee":
            self._act(FLEE)
        elif name == "shove":
            self._act(SHOVE)
        elif name == "stance":
            self._act(STANCE)
        elif name in (BOTH, HAND, GUN):
            self._act(STANCE, name)

    def press_crit(self) -> None:
        """The measure is full: start the mark going. Or it is going: stop it where it is."""
        if self.state == FIGHTING and self.fight.crit_ready:
            self.state, self.aiming = AIMING, 0.0
        elif self.state == AIMING:
            self._act(CRIT, self.mark())
            self.state = FIGHTING

    # ----- time -----

    @property
    def slowing(self) -> bool:
        return self.slow_age < self.slow_for

    @property
    def cinema(self) -> bool:
        return self.slowing and self.zoom_to >= ZOOM

    def near(self) -> float:
        if self.slow_age >= self.slow_for:
            return 0.0
        share = min(1.0, self.slow_age / ZOOM_IN, (self.slow_for - self.slow_age) / ZOOM_OUT)
        return share * share * (3.0 - 2.0 * share)

    def _slow(self, index: int, seconds: float, zoom: float = ZOOM) -> None:
        if not self.slow_motion:
            return
        if self.slowing:
            self.slow_for = max(self.slow_for, self.slow_age + seconds)
            self.zoom_to = max(self.zoom_to, zoom)
        else:
            self.slow_age, self.slow_for, self.zoom_to = 0.0, seconds, zoom
            self.eye = self._looked_at(index)
        self.focus = index

    def _looked_at(self, index: int) -> tuple[float, float]:
        body = self.bodies[index]
        x, y = body.middle()
        piece = body.pieces[-1] if body.pieces else None
        joints = list(piece.skeleton.joints.values()) if piece is not None else []
        if joints:
            detail = body.detail
            far_x = sum(joint.x for joint in joints) / len(joints) * detail
            far_y = (sum(joint.y for joint in joints) / len(joints) + body.low) * detail
            x, y = x + (far_x - x) * 0.4, y + (far_y - y) * 0.4
        return (x, y)

    def view(self) -> tuple[pygame.Rect, float]:
        wide, high = self.screen.get_size()
        zoom = 1.0 + (self.zoom_to - 1.0) * self.near()
        seen = pygame.Rect(0, 0, round(wide / zoom), round(high / zoom))
        seen.center = (round(self.eye[0]), round(self.eye[1]))
        return (seen.clamp(self.screen.get_rect()), zoom)

    def _seen(self, point: tuple[float, float]) -> tuple[float, float]:
        seen, zoom = self._view
        return ((point[0] - seen.x) * zoom, (point[1] - seen.y) * zoom) if zoom > 1.0 else point

    def update(self, seconds: float) -> None:
        self.time += seconds
        self.slow_age += seconds
        slowed = 1.0 - (1.0 - SLOW_PACE) * self.near()
        if self.slowing:
            goal = self._looked_at(self.focus)
            share = min(1.0, seconds * 6.0)
            self.eye = (self.eye[0] + (goal[0] - self.eye[0]) * share, self.eye[1] + (goal[1] - self.eye[1]) * share)
        seconds *= slowed
        for word in self.words:
            word.age += seconds
        for shot in self.shots:
            shot.age += seconds
        self.words = [word for word in self.words if word.age < WORDS]
        self.shots = [shot for shot in self.shots if shot.age < 0.14]
        self.shake = max(0.0, self.shake - seconds * 3.0)
        self._fall(seconds)
        pace = 1.0
        tuning = self.data.tuning
        if self.state == AIMING:
            self.aiming += seconds
            pace = tuning.aiming_time
            if self.aiming * tuning.crit_sweeps_per_second >= tuning.crit_sweeps:
                self.press_crit()
        if self.state in (FIGHTING, AIMING):
            # The fight is the simulation's: it is asked to let it go on, and says what happened.
            for event in self.world.apply_command(FightOnCommand(self.resident_id, seconds * pace)):
                self._show(event)
            if self.fight.outcome is not None:
                self.state = OVER
                self.ended_at = self.time
                if self.fight.outcome in (WON, LOST):
                    self.ko_at = self.time
                    self.shake = max(self.shake, CRIT_SHAKE)
                    self._slow(0 if self.fight.outcome == LOST else self._last_down, KO_SLOW, CRIT_ZOOM)
                else:
                    self.ended_at = self.time - KO_SECONDS
        self.clock += seconds * pace
        on = set(self.fight.pins) if self.state in (FIGHTING, AIMING) else set()
        self._on = {index: self._on.get(index, self.clock) for index in on}
        self._place(seconds * pace)
        for index, body in enumerate(self.bodies):
            body.update(seconds * pace)
            self._jets(index, body, seconds * pace)

    def _jets(self, index: int, body: Body, seconds: float) -> None:
        """Blood comes in jets out of where a part was, for as long as they bleed."""
        fighter = self.fight.fighters[index]
        fresh = self.clock - self.cut_at.get(index, -99.0) < JET_AFTER
        live = self.state in (FIGHTING, AIMING)
        bleeds = bleeding(fighter, self.data.tuning) > 0.0 if live else not fighter.staunched and fresh
        if index not in self.cut_at or self.gore <= 0.0 or not (bleeds or (fighter.down and fresh)):
            return
        luck = self.scatter
        beat = max(0.0, math.sin((self.clock * JET_BEATS + index * 0.37) * math.tau)) ** 3
        for at, (x, y, out_x, out_y) in enumerate(body.stumps()):
            key = index * 16 + at
            self._drip[key] = self._drip.get(key, 0.0) + seconds * (JET_TRICKLE + JET_RATE * beat) * self.gore
            while self._drip[key] >= 1.0:
                self._drip[key] -= 1.0
                turn = luck.uniform(-JET_SPREAD, JET_SPREAD) * math.tau
                speed = (JET_SLOW + (JET_FAST - JET_SLOW) * beat) * luck.uniform(0.75, 1.1)
                way_x = out_x * math.cos(turn) - out_y * math.sin(turn)
                way_y = out_x * math.sin(turn) + out_y * math.cos(turn)
                self.drops.append(Drop(x, y, way_x * speed, way_y * speed, luck.uniform(2.0, 4.2), max(y + 4.0, self.ground + luck.uniform(2, 22))))

    def _fall(self, seconds: float) -> None:
        flying = []
        for drop in self.drops:
            drop.vy += GRAVITY * seconds
            drop.x += drop.vx * seconds
            drop.y += drop.vy * seconds
            if drop.y >= drop.lands:
                self.pools.append((drop.x, drop.lands, drop.size))
            else:
                flying.append(drop)
        self.drops = flying
        del self.pools[:-MOST_POOLS]

    def _spurt(self, index: int, way: float, amount: float, much: float) -> None:
        x, y = self.bodies[index].spot(0.62)
        luck = self.scatter
        for _ in range(int(min(60, (2 + amount * 0.45) * much * self.gore))):
            speed = luck.uniform(120, 420)
            self.drops.append(
                Drop(x, y, way * speed * luck.uniform(0.3, 1.0), -luck.uniform(60, 380), luck.uniform(2.0, 5.5), self.ground + luck.uniform(2, 22))
            )

    def _say(self, text: str, index: int, color: Color, big: bool = False) -> None:
        x, y = self.spot(index)
        self.words.append(Word(text, x + self.scatter.uniform(-18, 18), y - self.tall(index) - 70, color, big=big))

    def _show(self, event: Event) -> None:
        fighters = self.fight.fighters
        weapon = self.data.weapons.get(event.weapon)
        way = 1.0 if fighters[event.to].at >= fighters[event.by].at else -1.0
        if event.kind in (HIT, DODGED) and weapon is not None:
            self.struck_at[event.by] = (self.clock, weapon.weapon_id)
            if weapon.kind != MELEE:
                start = self.bodies[event.by].hand() or self.bodies[event.by].spot(0.62)
                end = self.bodies[event.to].spot(0.62)
                color = (120, 230, 255) if weapon.kind == "energy" else GLOW
                self.shots.append(Shot((start[0], start[1]), (end[0], end[1] if event.kind == HIT else end[1] - 70), color))
        if event.kind == HIT and weapon is not None:
            telling = event.times > 1.0
            victim = self.bodies[event.to]
            if victim.lying and fighters[event.to].floored > 0.0 and weapon.kind == MELEE:
                victim.pounded(event.amount)
            else:
                victim.struck(way, event.amount)
            blunt = weapon.kind == MELEE and "knife" not in weapon.clip
            kind = BURN if weapon.kind == "energy" else BRUISE if blunt else BLOOD
            if self.gore > 0.0 or kind == BRUISE:
                victim.mark(kind)
            if (event.amount >= 9 or telling) and self.gore > 0.0:
                victim.mark(BLOOD if kind != BURN else BURN)
            self._spurt(event.to, way, event.amount, 0.35 if blunt else 0.5 if kind == BURN else 1.0)
            self._say(f"-{event.amount:.0f}", event.to, GLOW if telling else (EMBER if event.to == 0 else PAPER), big=telling)
            if telling:
                self.shake = max(self.shake, CRIT_SHAKE)
                self._slow(event.to, CRIT_SECONDS, CRIT_ZOOM)
        elif event.kind == HELD:
            self.pounds[event.by] = self.pounds.get(event.by, 0) + 1
        elif event.kind == THROWN_OFF:
            self.pounds[event.to] = self.pounds.get(event.to, 0) + 1
            self.bodies[event.to].struck(way, 9.0, reeling=True)
        elif event.kind == SHOVED:
            self.shoved_at[event.by] = self.clock
            self.bodies[event.to].struck(way, 6.0, reeling=True)
            self.bodies[event.to].mark(BRUISE)
        elif event.kind == SEVERED:
            self.bodies[event.to].sever(event.said, way, 12.0)
            self.cut_at[event.to] = self.clock
            self._spurt(event.to, way, 40.0, 2.0)
            self.bodies[event.to].mark(BLOOD)
            self.shake = 1.0
            self._slow(event.to, SLOW_HEAD_SECONDS if event.said in self.data.tuning.deadly else SLOW_SECONDS)
        elif event.kind == BLED:
            if event.amount >= 1.0:
                self._say(f"-{event.amount:.0f}", event.to, GORE)
        elif event.kind == REELED:
            self.bodies[event.to].struck(way, event.amount, reeling=True)
            self.shake = max(self.shake, 0.4)
        elif event.kind == FLOORED:
            self.bodies[event.to].floor(way, event.amount, self.data.tuning.floored_seconds)
            self._spurt(event.to, way, event.amount, 0.8)
            self.shake = max(self.shake, 0.5)
        elif event.kind == DOWN:
            self._last_down = event.to
            self.bodies[event.to].fall(way, 14.0)
            self._spurt(event.to, way, 18.0, 1.0)
        elif event.kind == HEALED:
            self._say(f"+{event.amount:.0f}", 0, LICHEN, big=True)
        elif event.kind == FLEE_FAILED:
            self.failed_at = self.time

    # ----- drawing -----

    def _text(self, text: str, position: tuple[float, float], color: Color, scale: int = MIDDLE, centre: bool = False) -> pygame.Rect:
        shade = self.font.render(text, INK, scale)
        picture = self.font.render(text, color, scale)
        rect = picture.get_rect()
        if centre:
            rect.center = (round(position[0]), round(position[1]))
        else:
            rect.topleft = (round(position[0]), round(position[1]))
        for dx, dy in ((scale, scale), (-scale, 0), (scale, 0), (0, -scale)):
            self.screen.blit(shade, rect.move(dx, dy))
        self.screen.blit(picture, rect)
        return rect

    def _bar(self, rect: pygame.Rect, share: float, color: Color) -> None:
        pygame.draw.rect(self.screen, INK, rect.inflate(4, 4), border_radius=4)
        pygame.draw.rect(self.screen, (46, 42, 43), rect, border_radius=3)
        fill = rect.copy()
        fill.width = round(rect.width * min(1.0, max(0.0, share)))
        if fill.width > 0:
            pygame.draw.rect(self.screen, color, fill, border_radius=3)

    def _button_at(self, name: str, label: str, rect: pygame.Rect, lit: bool = False, dim: bool = False, bad: bool = False) -> None:
        self.buttons[name] = rect
        pygame.draw.rect(self.screen, INK, rect.inflate(6, 6), border_radius=8)
        pygame.draw.rect(self.screen, RED if bad else LAMP if lit else (74, 69, 69), rect, border_radius=6)
        label = self.font.truncate(label, (rect.width - 10) // SMALL)
        picture = self.font.render(label, DUST if dim else (INK if lit else PAPER), SMALL)
        self.screen.blit(picture, picture.get_rect(center=rect.center))

    def _way(self, stance: str) -> str:
        hero = self.fight.hero
        if stance == HAND:
            return hero.weapon.name.capitalize()
        if stance == GUN and hero.gun is not None:
            return hero.gun.name.capitalize()
        return "Las dos" if hero.gun is not None else hero.weapon.name.capitalize()

    def _rounds(self) -> str:
        fired = self.fight.fired(self.fight.hero)
        if fired is None or fired.ammo <= 0:
            return ""
        rounds = self.fight.hero.rounds
        return "sin balas" if rounds <= 0 else "1 bala" if rounds == 1 else f"{rounds} balas"

    def _over_head(self, index: int, fighter: Fighter) -> None:
        if fighter.down:
            return
        x, y = self.spot(index)
        lift = 0 if index < 2 else 46 * ((index - 1) % 3)
        x, top = self._seen((x + self._aside(index), y - self.tall(index) - 26 - lift))
        bar = pygame.Rect(round(x) - 50, round(top), 100, 10)
        share = fighter.health / fighter.max_health
        self._bar(bar, share, LICHEN if share > 0.5 else LAMP if share > 0.25 else RED)
        self._text(f"{fighter.name} Nv{fighter.level}", (x, top - 16), PAPER, SMALL, centre=True)

    def _aside(self, index: int) -> float:
        """How far to one side what is said over somebody goes: right up to one another, the
        hero's is moved away from the raiders' and theirs away from the hero's."""
        fight = self.fight
        near = [foe for foe in fight.foes if not foe.down and fight.gap(fight.hero, foe) < 3.4]
        if index == 0:
            return 0.0 if not near else (-70.0 if near[0].at >= fight.hero.at else 70.0)
        foe = fight.fighters[index]
        if foe not in near:
            return 0.0
        return 70.0 if foe.at >= fight.hero.at else -70.0

    def _stars(self, index: int) -> None:
        fighter = self.fight.fighters[index]
        if fighter.down or fighter.floored <= 0.0 or self.state not in (FIGHTING, AIMING):
            return
        head = self.bodies[index].head()
        if head is None:
            return
        grown = self.tall(index) / 200.0
        for star in range(STARS):
            turn = (self.clock * STAR_TURNS + star / STARS) * math.tau
            x = head[0] + math.cos(turn) * STAR_RING * grown
            y = head[1] - STAR_OVER * grown + math.sin(turn) * STAR_RING * STAR_FLAT * grown
            size = STAR_SIZE * grown * (1.0 + 0.3 * math.sin(turn))
            spin = self.clock * 3.0 + star
            points = [
                (x + math.sin(spin + tip * math.pi / 5) * size * (1.0 if tip % 2 == 0 else 0.45), y - math.cos(spin + tip * math.pi / 5) * size * (1.0 if tip % 2 == 0 else 0.45))
                for tip in range(10)
            ]
            pygame.draw.polygon(self.screen, GLOW, points)
            pygame.draw.polygon(self.screen, INK, points, 2)

    def draw(self) -> pygame.Surface:
        """Draw the fight as it stands, and hand back the picture of it."""
        screen, fight = self.screen, self.fight
        wide, high = screen.get_size()
        self.buttons = {}
        jolt = (round(self.scatter.uniform(-6, 6) * self.shake), round(self.scatter.uniform(-4, 4) * self.shake))
        screen.blit(self.look.backdrop(self.zone_id, (wide, high), self.gone_by), jolt)
        for x, y, size in self.pools:
            pool = pygame.Rect(0, 0, round(size * 3.2), max(2, round(size * 0.9)))
            pool.center = (round(x), round(y))
            pygame.draw.ellipse(screen, GORE, pool)
        for shot in self.shots:
            pygame.draw.line(screen, INK, shot.start, shot.end, 7)
            pygame.draw.line(screen, shot.color, shot.start, shot.end, 3)
        order = sorted(
            range(len(fight.fighters)),
            key=lambda index: (not fight.fighters[index].down, fight.fighters[index].floored <= 0.0, -index),
        )
        for index in order:
            x, y = self.spot(index)
            if not fight.fighters[index].down:
                shade = pygame.Surface((round(self.tall(index) * 0.5), 18), pygame.SRCALPHA)
                pygame.draw.ellipse(shade, (0, 0, 0, 80), shade.get_rect())
                screen.blit(shade, shade.get_rect(center=(round(x), round(y) + 2)))
            self.bodies[index].draw(screen)
        for body in self.bodies:
            body.draw_pieces(screen)
        for drop in self.drops:
            size = max(1, round(drop.size))
            tail = (round(drop.x - drop.vx * 0.022), round(drop.y - drop.vy * 0.022))
            pygame.draw.line(screen, GORE, tail, (round(drop.x), round(drop.y)), size)
            pygame.draw.circle(screen, GORE, (round(drop.x), round(drop.y)), size)
        for index in range(len(fight.fighters)):
            self._stars(index)
        self.look.front(screen, self.zone_id, self.gone_by)
        self._view = self.view()
        seen, zoom = self._view
        close, cinema = self.near(), self.cinema
        if zoom > 1.0:
            pygame.transform.smoothscale(screen.subsurface(seen).copy(), (wide, high), screen)
        for index, fighter in enumerate(fight.fighters):
            if not cinema:
                self._over_head(index, fighter)
        if self.state in (FIGHTING, AIMING) and not self.slowing:
            target = fight.target()
            if target is not None:
                x, y = self.spot(target + 1)
                tip = y - self.tall(target + 1) - 52 + 4 * math.sin(self.time * 6)
                color = GLOW if fight.chosen == target else PAPER
                pygame.draw.polygon(screen, INK, [(x - 13, tip - 17), (x + 13, tip - 17), (x, tip + 3)])
                pygame.draw.polygon(screen, color, [(x - 9, tip - 14), (x + 9, tip - 14), (x, tip - 1)])
        row = 0
        for word in self.words:
            rise = 46 * (word.age / WORDS)
            at = self._seen((word.x, word.y - rise))
            if zoom > 1.0:
                top = (BARS * close if cinema else 0.0) + 30.0
                at = (min(wide - 120.0, max(120.0, at[0])), max(at[1], top + row * 44.0) if at[1] < top else at[1])
                row += at[1] <= top + row * 44.0
            self._text(word.text, at, word.color, LARGE if word.big else MIDDLE, centre=True)
        self._panel()
        if close > 0.0 and cinema:
            screen.fill(INK, (0, 0, wide, round(BARS * close)))
            low = round((PANEL_TALL + 6) * close)
            screen.fill(INK, (0, high - low, wide, low))
        self._ko()
        if self.state == AIMING:
            self._aim()
        elif self.state == CHOOSING:
            self._choosing()
        return screen

    def _ko(self) -> None:
        if self.ko_at is None or self.time - self.ko_at >= KO_SECONDS:
            return
        age = self.time - self.ko_at
        color = GLOW if self.fight.outcome == WON else EMBER
        if color not in self._ko_pictures:
            face = self.font.render(KO, color, KO_SCALE)
            edge = self.font.render(KO, INK, KO_SCALE)
            picture = pygame.Surface((face.get_width() + 28, face.get_height() + 28), pygame.SRCALPHA)
            for step in range(16):
                picture.blit(edge, (14 + round(7 * math.cos(step * math.tau / 16)), 14 + round(7 * math.sin(step * math.tau / 16))))
            picture.blit(edge, (21, 23))
            picture.blit(face, (14, 14))
            self._ko_pictures[color] = picture
        picture = self._ko_pictures[color]
        coming = max(0.0, 1.0 - age / KO_LANDS)
        size = 1.0 + (KO_FROM - 1.0) * coming * coming
        if size > 1.01:
            picture = pygame.transform.smoothscale(picture, (round(picture.get_width() * size), round(picture.get_height() * size)))
        left = KO_SECONDS - age
        if left < 0.25:
            picture = picture.copy()
            picture.set_alpha(round(255 * left / 0.25))
        wide, high = self.screen.get_size()
        self.screen.blit(picture, picture.get_rect(center=(wide // 2, round(high * 0.3))))

    def _panel(self) -> None:
        screen, fight = self.screen, self.fight
        wide, high = screen.get_size()
        panel = pygame.Rect(0, high - PANEL_TALL, wide, PANEL_TALL)
        veil = pygame.Surface(panel.size, pygame.SRCALPHA)
        veil.fill((20, 18, 18, 215))
        screen.blit(veil, panel)
        if self.state not in (FIGHTING, AIMING):
            return
        ready = fight.crit_ready
        top, row = panel.y + 10, panel.y + 40
        meter = pygame.Rect(18, row + 6, 230, 24)
        pulse = 0.5 + 0.5 * math.sin(self.time * 10)
        self._bar(meter, fight.crit, GLOW if ready and pulse > 0.5 else LAMP)
        self._text("CRÍTICO: ESPACIO" if ready else "CRÍTICO", (18, top), GLOW if ready else BONE, SMALL)
        if ready:
            self.buttons["crit"] = meter.inflate(8, 30)
        choice = len(fight.stances()) > 1
        rounds = self._rounds()
        said = "ARMA (Tab)" if choice else "ARMA"
        self._text(f"{said} · {rounds}" if rounds else said, (266, top), EMBER if rounds == "sin balas" else BONE, SMALL)
        self._button_at("stance", self._way(fight.stance), pygame.Rect(264, row, 200, 38), dim=not choice)
        self._button_at("shove", "Empujar (E)", pygame.Rect(478, row, 140, 38), lit=fight.can_shove(), dim=not fight.can_shove())
        self._button_at("heal", f"Cura x{fight.medkits} (Q)", pygame.Rect(632, row, 140, 38), dim=fight.medkits <= 0)
        failed = self.time - self.failed_at < FAILED_SECONDS
        self._button_at("flee", f"Huir (H) {fight.flee_chance() * 100:.0f}%", pygame.Rect(786, row, 150, 38), bad=failed)
        self._text("Pelea solo" if fight.hands_off else "Clic: a quién", (950, top), LICHEN if fight.hands_off else DUST, SMALL)
        self._text("A: vuelves tú" if fight.hands_off else "A: pelea solo", (950, row + 8), DUST, SMALL)

    def _aim(self) -> None:
        screen = self.screen
        wide = screen.get_width()
        bar = pygame.Rect(wide // 2 - 300, 130, 600, 44)
        pygame.draw.rect(screen, INK, bar.inflate(12, 12), border_radius=10)
        pygame.draw.rect(screen, RED, bar, border_radius=6)
        marks = self.data.tuning.crit_marks
        for (reach, _, _), color in reversed(list(zip(marks[:-1], (LICHEN, LAMP)))):
            zone = pygame.Rect(0, bar.y, round(bar.width * reach), bar.height)
            zone.centerx = bar.centerx
            pygame.draw.rect(screen, color, zone)
        x = bar.centerx + round(self.mark() * bar.width / 2)
        pygame.draw.rect(screen, INK, (x - 6, bar.y - 12, 12, bar.height + 24), border_radius=4)
        pygame.draw.rect(screen, PAPER, (x - 3, bar.y - 9, 6, bar.height + 18), border_radius=3)
        self._text("¡Párala en el centro!  ESPACIO o clic", (wide // 2, bar.y - 30), GLOW, SMALL, centre=True)

    def _choosing(self) -> None:
        """Before a blow is struck: what they fight with, of what they carry."""
        screen, fight = self.screen, self.fight
        wide = screen.get_width()
        box = pygame.Rect(wide // 2 - 400, 150, 800, 190)
        veil = pygame.Surface(box.size, pygame.SRCALPHA)
        veil.fill((20, 18, 18, 235))
        screen.blit(veil, box)
        pygame.draw.rect(screen, LAMP, box, 3, border_radius=8)
        self._text("¿Con qué lucho?", (box.centerx, box.y + 30), PAPER, MIDDLE, centre=True)
        rounds = self._rounds()
        for at, way in enumerate((HAND, GUN, BOTH)):
            label = self._way(way) if way != GUN or not rounds else f"{self._way(way)} · {rounds}"
            self._button_at(way, label, pygame.Rect(box.x + 25 + at * 255, box.y + 62, 240, 40), lit=fight.stance == way)
        self._button_at("fight", "Luchar (Intro)", pygame.Rect(box.centerx - 130, box.y + 124, 260, 42), lit=True)
