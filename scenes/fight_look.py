"""The bodies of a fight out there (P80): a doll over a skeleton that the game's physics can
take over, what a blow leaves on it, and what comes off it.

Whoever shows the fight says where each stands and what it is doing; a blow hands it to
physics for as long as it reels or lies. Nothing here decides anything of the fight.
"""

import math
import random
from dataclasses import dataclass

import pygame

from graphics import doll as doll_module
from graphics import mannequin
from graphics.backdrop import BackdropStore, draw_strips
from graphics.cartoon import LINE
from graphics.doll import DollStore
from skeleton.character import Character
from skeleton.plan import builtin_plan
from skeleton.rig import Skeleton

Color = tuple[int, int, int]

SKY: Color = (124, 150, 160)
GROUND: Color = (150, 128, 100)
INK: Color = (30, 22, 20)
# How tall a body is in its skeleton's own measure, as the game takes it to be.
BODY_TALL = 31.0
SKY: Color = (124, 150, 160)
GROUND: Color = (150, 128, 100)
INK: Color = (30, 22, 20)
# Speed a blow gives the joint it lands on, in the body's own measure a second: some for any
# blow and more the harder it was, and how much of it goes upwards. Far less than the game
# gives a blow on its map: here two bodies stand right up to one another, and one sent
# flying is one nobody is seen to hit.
BLOW_SPEED = 14.0
BLOW_SPEED_PER_DAMAGE = 0.9
BLOW_LIFT = 0.25
# How many times that a blow that makes them reel gives, one that floors them, and one that
# puts them down for good.
REEL_BLOW, FLOOR_BLOW, LAST_BLOW = 2.2, 3.4, 4.0
# How much of that a blow from above gives somebody lying under it, downwards.
POUND_DOWN = 0.8
# And how many times that a part that comes off is thrown with.
SEVER_BLOW = 5.0
# Where the hand that holds is, in what the game's body plan calls its points.
HAND_TIP, HAND_WRIST = "held_item", "held_wrist"
# And where the head is.
HEAD = "mouth"
# How much upwards what comes out of where a part was goes, in the body's own measure: it
# comes out away from the middle of them, and up.
JET_LIFT = 3.0
# What is seen in a hand, by weapon: how long it is in the body's own measure, how thick, its
# colour, and for what has a head at its far end, how big that is and its colour.
HELD: dict[str, tuple[float, float, Color, float, Color]] = {
    "baton": (9.0, 1.5, (104, 70, 44), 0.0, (0, 0, 0)),
    "rusty_knife": (5.0, 1.1, (168, 172, 176), 0.0, (0, 0, 0)),
    "sledge": (12.0, 1.3, (104, 70, 44), 3.4, (96, 98, 104)),
    "pipe_pistol": (4.5, 1.9, (62, 62, 68), 0.0, (0, 0, 0)),
    "rifle": (11.0, 1.5, (72, 56, 44), 0.0, (0, 0, 0)),
    "arc_thrower": (6.5, 2.1, (70, 96, 116), 1.6, (120, 230, 255)),
    "laser": (10.0, 1.7, (84, 88, 100), 1.4, (120, 230, 255)),
    "claws": (4.4, 1.0, (226, 218, 196), 0.0, (0, 0, 0)),
}
# What is held that is no one thing but several, fanned out from the hand: how many, and how
# far apart, in turns.
FANNED: dict[str, tuple[int, float]] = {"claws": (3, 0.07)}
# What a blow leaves on a body, by what it is: its colour, how see-through, and how big.
BRUISE, BLOOD, BURN = "bruise", "blood", "burn"
MARKS: dict[str, tuple[Color, int, tuple[float, float]]] = {
    BRUISE: ((74, 44, 96), 150, (1.4, 2.6)),
    BLOOD: ((150, 16, 20), 220, (0.9, 2.0)),
    BURN: ((34, 26, 24), 200, (1.2, 2.2)),
}
MOST_MARKS = 16


@dataclass
class Mark:
    """Something a blow left on somebody: by the joint it is nearest, so that it goes where the body goes."""

    kind: str
    joint: str
    dx: float
    dy: float
    radius: float


class Body:
    """Somebody's body on screen: a doll of the game's over a skeleton that its physics can
    take over, or a plain shape. Whoever shows the fight says where it stands and what it is
    doing; a blow hands it to physics for as long as it reels or lies."""

    def __init__(self, look: "Look", key: str, color: Color, hero: bool) -> None:
        self.look = look
        self.key = key
        self.color = color
        self.hero = hero
        self.marks: list[Mark] = []
        self.x = self.ground = 0.0
        self.tall = 100.0
        self.left = False
        self.lying = False
        # What they hold right now, by weapon ID, to be seen in their hand. Nothing for bare hands.
        self.holding = ""
        self.character = None
        self._posed = {}
        self._reach: dict[str, tuple[float, float]] = {}
        # The parts that have come off them, each a body of its own to fall and lie where it lands.
        self.pieces: list = []
        self.lost: list[str] = []
        game = look.game
        if game is not None:
            self.doll = look.doll(key, color, hero)
            self.plan = self.doll.plan if self.doll.plan is not None else game["plan"]
            self.character = game["character"](self.plan)
            self.character.lively = True
            self.low = self.doll.standing(self.plan)[3]

    @property
    def detail(self) -> float:
        return self.tall / BODY_TALL

    def stand(
        self, x: float, ground: float, tall: float, facing_left: bool, clip: str, phase: float, exact: bool = False
    ) -> None:
        """Say where their feet are on the screen and what they are doing there. `exact` has
        them just as the clip has them, with no give: a blow has to be where it is aimed."""
        self.x, self.ground, self.tall, self.left = x, ground, tall, facing_left
        if self.character is not None:
            facing = self.look.game["doll"].DOLL_FACINGS["left" if facing_left else "right"]
            detail = self.detail
            self.character.lively = not exact
            self.character.stand(x / detail, ground / detail - self.low, facing, clip, min(0.999, max(0.0, phase)) if exact else phase % 1.0)

    def reach(self, clip: str) -> tuple[float, float]:
        """How far through a clip the hand that strikes is furthest out in front, from 0 to 1,
        and how far out that is from the spot between their feet, in pixels of the screen."""
        if self.character is None:
            return (0.5, self.tall * 0.3)
        if clip not in self._reach:
            facing = self.look.game["doll"].DOLL_FACINGS["right"]
            best = (0.5, 0.0)
            for step in range(25):
                phase = step / 24 * 0.999
                hand = self.plan.anchor(HAND_TIP, facing, self.plan.pose(facing, clip, phase))
                if hand is not None and hand[0] > best[1]:
                    best = (phase, hand[0])
            self._reach[clip] = best
        phase, out = self._reach[clip]
        return (phase, out * self.detail)

    def update(self, seconds: float) -> None:
        if self.character is not None:
            self.character.update(seconds)
            for piece in self.pieces:
                piece.update(seconds)

    def sever(self, part: str, way: float, amount: float) -> None:
        """Take a part off them and throw it, away from whoever dealt the blow, turning as it goes."""
        self.lost.append(part)
        if self.character is None or not self.character.has(part):
            return
        luck = self.look.luck
        speed = (BLOW_SPEED + amount * BLOW_SPEED_PER_DAMAGE) * SEVER_BLOW * self.look.force
        spin = luck.uniform(3.0, 9.0) * luck.choice((-1.0, 1.0))
        piece = self.character.sever(part, way * speed * luck.uniform(0.6, 1.0), -speed * luck.uniform(0.5, 0.9), spin)
        if piece is not None:
            self.pieces.append(piece)

    def stumps(self) -> list[tuple[float, float, float, float]]:
        """Where on the screen each part came off them, and which way out of them that is: the
        joint each was cut through, if it is still on them, away from the middle of them and
        somewhat up."""
        if self.character is None:
            return [(self.x, self.ground - self.tall * (0.15 if self.lying else 0.7), 0.0, -1.0)] if self.lost else []
        skeleton = self._skeleton()
        joints = skeleton.joints
        if not joints:
            return []
        detail = self.detail
        middle_x = sum(joint.x for joint in joints.values()) / len(joints)
        middle_y = sum(joint.y for joint in joints.values()) / len(joints)
        found = []
        for part in self.lost:
            bone = self.plan.bones.get(self.plan.parts.get(part, ""))
            joint = joints.get(bone.start) if bone is not None else None
            if joint is None or bone.name in skeleton.bones:
                # Gone with something cut nearer the trunk, or never taken off this body.
                continue
            out_x, out_y = joint.x - middle_x, joint.y - middle_y - JET_LIFT
            far = math.hypot(out_x, out_y) or 1.0
            found.append((joint.x * detail, (joint.y + self.low) * detail, out_x / far, out_y / far))
        return found

    def head(self) -> tuple[float, float] | None:
        """Where on the screen their head is, if they have it."""
        if self.character is None:
            return (self.x, self.ground - self.tall * (0.14 if self.lying else 0.9)) if "head" not in self.lost else None
        skeleton = self._skeleton()
        pose = {name: (joint.x, joint.y) for name, joint in skeleton.joints.items()}
        head = self.plan.anchor(HEAD, self.character.facing, pose)
        return None if head is None else (head[0] * self.detail, (head[1] + self.low) * self.detail)

    def _blow(self, way: float, amount: float, harder: float = 1.0) -> tuple[float, float, str | None]:
        speed = (BLOW_SPEED + amount * BLOW_SPEED_PER_DAMAGE) * harder * self.look.force
        joints = self._joints()
        # A blow lands high: on one of the joints nearest the head.
        high = sorted(joints, key=lambda name: joints[name][1])[:4]
        return (way * speed, -speed * BLOW_LIFT, self.look.luck.choice(high) if high else None)

    def struck(self, way: float, amount: float, reeling: bool = False) -> None:
        """A blow that leaves them on their feet: they give under it, away from whoever dealt
        it, and more if it made them reel."""
        if self.character is not None and self.character.alive:
            vx, vy, joint = self._blow(way, amount, REEL_BLOW if reeling else 1.0)
            self.character.hit(vx, vy, joint)

    def _stilled(self) -> None:
        """Take from a body that was reeling whatever speed it had: it was being drawn back to
        where it stood, and what puts it down is the blow and nothing else."""
        skeleton = self.character.skeleton if self.character is not None else None
        if skeleton is not None and not self.lying:
            for joint in skeleton.joints.values():
                joint.px, joint.py = joint.x, joint.y

    def pounded(self, amount: float) -> None:
        """A blow from above on them where they lie: it drives them into the ground, and
        throws them nowhere."""
        if self.character is not None and self.character.alive:
            speed = (BLOW_SPEED + amount * BLOW_SPEED_PER_DAMAGE) * self.look.force
            joints = self._joints()
            luck = self.look.luck
            self.character.hit(luck.uniform(-0.25, 0.25) * speed, speed * POUND_DOWN, luck.choice(sorted(joints)) if joints else None)

    def floor(self, way: float, amount: float, seconds: float) -> None:
        """A blow that puts them on the ground, for so long."""
        self._stilled()
        self.lying = True
        if self.character is not None and self.character.alive:
            vx, vy, joint = self._blow(way, amount, FLOOR_BLOW)
            self.character.knock_down(vx, vy, joint, seconds)

    def fall(self, way: float, amount: float) -> None:
        """A blow that puts them down for good."""
        self._stilled()
        self.lying = True
        if self.character is not None and self.character.alive:
            vx, vy, joint = self._blow(way, amount, LAST_BLOW)
            self.character.kill(vx, vy, joint)

    def got_up(self) -> None:
        self.lying = False

    def chest(self) -> tuple[float, float]:
        """Where on the screen their chest is, however they stand or lie: half way from the
        middle of them to their head."""
        x, y = self.middle()
        if self.character is None:
            return (x, y)
        skeleton = self._skeleton()
        pose = {name: (joint.x, joint.y) for name, joint in skeleton.joints.items()}
        head = self.plan.anchor(HEAD, self.character.facing, pose)
        if head is None:
            return (x, y)
        return ((x + head[0] * self.detail) / 2, (y + (head[1] + self.low) * self.detail) / 2)

    def hold_down(self, seconds: float) -> None:
        """Keep them on the ground for that much longer: they are up when the fight says so,
        and no sooner."""
        if self.lying and self.character is not None and self.character.alive:
            self.character.knock_down(0.0, 0.0, None, seconds)

    def middle(self) -> tuple[float, float]:
        """Where on the screen the middle of them is, however they stand or lie."""
        joints = self._joints()
        if not joints:
            return (self.x, self.ground - self.tall * (0.1 if self.lying else 0.5))
        detail = self.detail
        return (
            sum(x for x, _ in joints.values()) / len(joints) * detail,
            (sum(y for _, y in joints.values()) / len(joints) + self.low) * detail,
        )

    def _skeleton(self):
        character = self.character
        if character.physical and character.skeleton is not None:
            return character.skeleton
        key = (character.facing, id(self.plan), tuple(character.lost))
        if key not in self._posed:
            self._posed = {key: self.look.game["skeleton"](self.plan, character.facing, character.lost)}
        skeleton = self._posed[key]
        skeleton.set_pose(character.local_pose(), character.x, character.y)
        return skeleton

    def _joints(self) -> dict[str, tuple[float, float]]:
        """Where every joint is right now, in the body's own measure."""
        if self.character is None:
            return {}
        return {name: (joint.x, joint.y) for name, joint in self._skeleton().joints.items()}

    def spot(self, share: float = 0.6) -> tuple[float, float]:
        """A place on the screen that far up them, from their feet at 0 to the top of their head at 1."""
        joints = self._joints()
        if not joints:
            return (self.x, self.ground - self.tall * share * (0.2 if self.lying else 1.0))
        detail = self.detail
        tops = sorted(joints.values(), key=lambda point: point[1])
        point = tops[min(len(tops) - 1, round((1.0 - share) * (len(tops) - 1)))]
        return (point[0] * detail, (point[1] + self.low) * detail)

    def mark(self, kind: str) -> None:
        """Leave on them what a blow leaves: a bruise, blood or a burn, somewhere on the upper half of them."""
        joints = self._joints()
        luck = self.look.luck
        low, high = MARKS[kind][2]
        if joints:
            names = sorted(joints, key=lambda name: joints[name][1])
            name = luck.choice(names[: max(1, len(names) * 2 // 3)])
        else:
            name = ""
        self.marks.append(Mark(kind, name, luck.uniform(-2.2, 2.2), luck.uniform(-2.0, 2.4), luck.uniform(low, high)))
        del self.marks[:-MOST_MARKS]

    def draw(self, target: pygame.Surface) -> None:
        if self.character is None:
            self._plain(target)
            return
        game = self.look.game
        skeleton = self._skeleton()
        detail = self.detail
        left, top, right, bottom = skeleton.bounds()
        margin = 14.0
        corner = ((left - margin) * detail, (top - margin + self.low) * detail)
        size = (max(8, round((right - left + margin * 2) * detail)), max(8, round((bottom - top + margin * 2) * detail)))
        picture = pygame.Surface(size, pygame.SRCALPHA)
        origin = (-corner[0], -corner[1] + self.low * detail)
        game["doll"].draw_doll(picture, self.doll, self.plan, skeleton, origin, detail)
        if self.marks:
            # What blows have left is laid over them and kept to them: nothing of it shows past their edge.
            stains = pygame.Surface(size, pygame.SRCALPHA)
            for mark in self.marks:
                joint = skeleton.joints.get(mark.joint)
                if joint is None:
                    continue
                color, alpha, _ = MARKS[mark.kind]
                centre = (origin[0] + (joint.x + mark.dx) * detail, origin[1] + (joint.y + mark.dy) * detail)
                wide = mark.radius * detail
                blot = pygame.Rect(0, 0, round(wide * 2.4), round(wide * 1.8))
                blot.center = (round(centre[0]), round(centre[1]))
                pygame.draw.ellipse(stains, (*color, alpha), blot)
                if mark.kind == BLOOD:
                    # It runs.
                    pygame.draw.line(stains, (*color, alpha), blot.center, (blot.centerx, blot.centery + round(wide * 2.6)), max(2, round(wide * 0.5)))
            stains.blit(picture, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
            picture.blit(stains, (0, 0))
        target.blit(picture, (round(corner[0]), round(corner[1])))
        self._held(target, skeleton)

    def draw_pieces(self, target: pygame.Surface) -> None:
        """What has come off them, wherever each has got to."""
        if self.character is None:
            return
        detail = self.detail
        for piece in self.pieces:
            if piece.skeleton.joints:
                self.look.game["doll"].draw_doll(target, self.doll, self.plan, piece.skeleton, (0.0, self.low * detail), detail)

    def hand(self) -> tuple[float, float] | None:
        """Where on the screen the hand that holds is right now."""
        if self.character is None:
            return None
        skeleton = self._skeleton()
        pose = {name: (joint.x, joint.y) for name, joint in skeleton.joints.items()}
        tip = self.plan.anchor(HAND_TIP, self.character.facing, pose)
        return None if tip is None else (tip[0] * self.detail, (tip[1] + self.low) * self.detail)

    def _held(self, target: pygame.Surface, skeleton) -> None:
        """What is in their hand, along the way the hand points."""
        shape = HELD.get(self.holding)
        if shape is None or self.lying:
            return
        long, thick, color, head, head_color = shape
        pose = {name: (joint.x, joint.y) for name, joint in skeleton.joints.items()}
        facing = self.character.facing
        tip, wrist = (self.plan.anchor(name, facing, pose) for name in (HAND_TIP, HAND_WRIST))
        if tip is None or wrist is None:
            return
        detail = self.detail
        way = pygame.Vector2(tip[0] - wrist[0], tip[1] - wrist[1])
        if way.length() < 1e-6:
            return
        way = way.normalize()
        start = pygame.Vector2(wrist[0], wrist[1] + self.low) * detail
        count, apart = FANNED.get(self.holding, (1, 0.0))
        for one in range(count):
            # Claws are three, spread from the hand; anything else is the one thing.
            turned = way.rotate((one - (count - 1) / 2) * apart * 360.0)
            end = start + turned * long * detail
            pygame.draw.line(target, INK, start, end, max(3, round((thick + 1.0) * detail)))
            pygame.draw.line(target, color, start, end, max(1, round(thick * detail)))
        end = start + way * long * detail
        if head > 0.0:
            pygame.draw.circle(target, INK, end, round((head + 0.5) * detail))
            pygame.draw.circle(target, head_color, end, round(head * detail))

    def _plain(self, target: pygame.Surface) -> None:
        x, y, tall = round(self.x), round(self.ground), self.tall
        wide = max(8, round(tall * 0.26))
        color = self.color
        if self.lying:
            body = pygame.Rect(x - round(tall * 0.36), y - wide, round(tall * 0.72), wide)
            pygame.draw.rect(target, color, body, border_radius=wide // 3)
            pygame.draw.rect(target, INK, body, 3, border_radius=wide // 3)
            head = (body.left - round(tall * 0.1) if self.left else body.right + round(tall * 0.1), y - wide // 2)
        else:
            body = pygame.Rect(x - wide // 2, y - round(tall * 0.72), wide, round(tall * 0.72))
            pygame.draw.rect(target, color, body, border_radius=wide // 3)
            pygame.draw.rect(target, INK, body, 3, border_radius=wide // 3)
            head = (x + (-4 if self.left else 4), y - round(tall * 0.86))
            arm = (x + (-wide if self.left else wide), y - round(tall * 0.5))
            pygame.draw.line(target, INK, (x, y - round(tall * 0.58)), arm, 7)
            pygame.draw.line(target, color, (x, y - round(tall * 0.58)), arm, 3)
        pygame.draw.circle(target, color, head, round(tall * 0.14))
        pygame.draw.circle(target, INK, head, round(tall * 0.14), 3)
        for index, mark in enumerate(self.marks):
            tint, _, _ = MARKS[mark.kind]
            at = (body.x + 4 + (index * 7) % max(1, body.width - 8), body.y + 6 + (index * 13) % max(1, body.height - 12))
            pygame.draw.circle(target, tint, at, max(2, round(mark.radius * 1.6)))


class Look:
    """What a fight is drawn with: the country of the zone it is in, standing still where the
    walk had got to, and a doll for each of those in it."""

    def __init__(self, dolls: DollStore | None, backdrops: BackdropStore, hero_doll: object | None = None) -> None:
        self.game = {
            "doll": doll_module,
            "mannequin": mannequin,
            "line": LINE,
            "character": Character,
            "skeleton": Skeleton,
            "plan": builtin_plan(),
        }
        self.backdrops = backdrops
        self.dolls = dolls if dolls is not None else DollStore(None, doll_module.load_template(), builtin_plan())
        # Whoever of the settlement is in it is drawn as they are on the walk there: the doll
        # the game has for them, if it has one.
        self.hero_doll = hero_doll
        # How many times as hard as it has it blows throw a body about.
        self.force = 1.0
        # Luck of its own, for what is only seen: looking on changes nothing of the fight.
        self.luck = random.Random(7)
        self._dolls: dict[str, object] = {}
        self._backdrops: dict[tuple, pygame.Surface] = {}

    @property
    def figure(self) -> float:
        """How tall somebody stands, as a share of the height of the place: as on the walk there."""
        return self.backdrops.plan.figure

    def has_clip(self, clip: str) -> bool:
        return clip in self.game["plan"].clips

    def body(self, key: str, color: Color, hero: bool = False) -> Body:
        """A body for somebody in the fight, of their own: two raiders of a sort do not share one."""
        return Body(self, key, color, hero)

    def doll(self, key: str, color: Color, hero: bool):
        if hero and self.hero_doll is not None:
            return self.hero_doll
        if key not in self._dolls:
            self._dolls[key] = self.dolls.stand_in(
                f"fight:{key}",
                lambda template: mannequin.figures(template, mannequin.tones_of(color, LINE), max(2, round(template.unit * 0.34))),
            )
        return self._dolls[key]

    def _layers(self, zone_id: str, size: tuple[int, int], gone_by: float, front: bool) -> pygame.Surface:
        key = (zone_id, size, round(gone_by), front)
        if key not in self._backdrops:
            if len(self._backdrops) > 6:
                self._backdrops.clear()
            whole = pygame.Surface(size, pygame.SRCALPHA)
            if not front:
                whole.fill(SKY)
            draw_strips(whole, self.backdrops.strips(zone_id, size[1]), whole.get_rect(), gone_by, front=front)
            self._backdrops[key] = whole
        return self._backdrops[key]

    def backdrop(self, zone_id: str, size: tuple[int, int], gone_by: float = 0.0) -> pygame.Surface:
        """The country of a zone, still, the size of the place it is shown in."""
        return self._layers(zone_id, size, gone_by, front=False)

    def front(self, target: pygame.Surface, zone_id: str, gone_by: float = 0.0) -> None:
        """What of a zone passes in front of whoever stands in it."""
        target.blit(self._layers(zone_id, target.get_size(), gone_by, front=True), (0, 0))

    def ground(self, size: tuple[int, int]) -> int:
        """How far down a place feet come down."""
        return round(size[1] * self.backdrops.plan.ground)
