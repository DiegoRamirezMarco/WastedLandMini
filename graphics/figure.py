"""Dolls as the game shows them: each turned whichever way it is asked for, with its face on and
whatever hands and feet it has that are made and not drawn.

A doll is cut from its drawings once (`graphics/doll.py`) and is what it is seen from its side.
Seen from anywhere else its trunk is wrapped round (`graphics/volume.py`), its head has its
face put on as that way round has it (`graphics/face.py`), its limbs go round with it
(`graphics/turn.py`), and its made hands and feet are told how it stands. Whoever shows a body
asks here for it turned so far, and is given what to lay over a skeleton and where its joints
then go.

A trunk is drawn from the front, to be wrapped. One drawn before there was any turning was
drawn from its side, and is told from the others by what is kept with its measures. Such a
body is not drawn again by anybody: seen from its side it is its drawing as it ever was, and
seen from anywhere else its trunk is made into one seen from the front by rule, as much wider
as a trunk is wider than deep. Its head, which has its face painted on it, is the same from
everywhere. It is as good as that until somebody draws it anew.

Turning a doll a way it has not been turned yet is not quick, and many may be asked for in
one frame: only so many are turned anew in a frame, and the rest are shown the nearest way
they have been turned (`Turned`).
"""

import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pygame

from graphics.doll import BODY_CANVAS, DOLL_FACINGS, HEAD_CANVAS, Doll, DollStore, draw_doll
from graphics.face import BEHIND_BY, BEHIND_FROM, Face, FaceLook, FaceRules, FaceStore, _dissolved, faced, plain_face, with_head
from graphics.face_examples import example
from graphics.face import load_rules as load_face_rules
from graphics.foot import Feet, FootRules, FootStore, Made
from graphics.foot import load_rules as load_foot_rules
from graphics.hand import HandPose, HandRules, HandStore
from graphics.hand import load_rules as load_hand_rules
from graphics.hose import Allowance
from graphics.joined import colour_at, half_width_at
from graphics.sides import DARKER, OWN, SHADE, WAYS, far_darker
from graphics.turn import LimbKeys, Turned, limb_keys_from_data, limbs_apart, limbs_moved, turned_pose
from graphics.volume import fronted, main_colour, plain_back, turned_body
from skeleton.plan import FACINGS, SkeletonPlan
from skeleton.rig import Skeleton

Point = tuple[float, float]

# What is kept with a body's measures besides them: how its trunk was drawn, how deep it is
# from chest to back as a share of its width, and how its far side comes by its limbs.
TRUNK_KEY, DEPTH_KEY, FAR_KEY = "trunk", "depth", "far_side"
# And where each of its limbs was put by hand, in each view (`graphics/turn.py`).
LIMBS_KEY = "limbs"
SIDE_DRAWN, FRONT_DRAWN = "side", "front"
# The drawing of the back of a trunk, kept beside those of a body's canvases.
BACK_DRAWING = "back"
# How far round the end of a limb its colour is looked for, in pixels of the drawing, for a
# hand or a foot that is made to be given.
MATCH_REACH = 7
# A head with its face drawn on it has none on the back of it. From behind it is all one
# colour, the one there is most of in so much of it from the top down, which is its hair if
# it has any: and what is dark within so much of its edge, as a share of how wide it is, is
# the line round it and is left.
HEAD_TOP = 0.34
HEAD_LINE = 0.035
# What is at the top of a head is its hair if so much of the whole head is that colour: less,
# and it is a tuft or a hat band, and the back of the head is the colour of the head.
HAIR_AT_LEAST = 0.2
# How many dolls may be turned a way they have not been turned yet in one frame.
TURNED_A_FRAME = 1
# In how many steps the far side goes from in the shade to out of it as a body turns.
SHADE_STEPS = 4


def _hair(head: pygame.Surface, colour: tuple[int, int, int] | None) -> tuple[int, int, int] | None:
    """The colour found at the top of a head, if enough of the head is that colour for it to
    be its hair: None if not, for the colour there is most of in all of it."""
    if colour is None:
        return None
    rgb = pygame.surfarray.array3d(head)
    solid = pygame.surfarray.array_alpha(head) >= 128
    # Colours a shade apart are one colour, as they are when the most of one is looked for.
    same = solid & ((rgb >> 4) == [value >> 4 for value in colour]).all(axis=2)
    return colour if solid.any() and same.sum() >= solid.sum() * HAIR_AT_LEAST else None


@dataclass(frozen=True)
class Said:
    """What has been said of a body besides its measures."""

    drawn: str = SIDE_DRAWN
    depth: float = 0.6
    far_side: str = OWN
    back: pygame.Surface | None = None
    # Where each of its limbs was put by hand, by view.
    limbs: LimbKeys = field(default_factory=dict)


@dataclass(frozen=True)
class Shown:
    """A doll turned some way, ready to be laid over a skeleton: the doll, whatever of it is
    made and not drawn, how far to its own side each of its limbs is from the front, and how
    far round it is, in degrees from facing whoever looks."""

    doll: Doll
    made: Made | None
    apart: dict[str, float]
    yaw: float
    # How far each of its limbs is from where it goes by rule, turned as it is.
    moved: dict[str, Point] = field(default_factory=dict)


class Figures:
    """Every doll the game shows, turned as it is asked for."""

    def __init__(
        self,
        dolls: DollStore,
        root: Path | None = None,
        face_rules: FaceRules | None = None,
        hand_rules: HandRules | None = None,
        foot_rules: FootRules | None = None,
    ) -> None:
        self.dolls = dolls
        self.rules = face_rules if face_rules is not None else load_face_rules()
        self.faces = FaceStore(root, self.rules)
        self.hands = HandStore(root, hand_rules if hand_rules is not None else load_hand_rules())
        self.feet = FootStore(root, foot_rules if foot_rules is not None else load_foot_rules())
        self._turned = Turned(TURNED_A_FRAME)
        self._said: dict[str, Said] = {}
        # Dolls cut again from the drawings of another: with a trunk made into one seen from
        # the front, or without the hands and feet that are made. By the doll each was cut from.
        self._cut: dict[tuple[int, bool, tuple[str, ...]], tuple[Doll, Doll]] = {}
        self._apart: dict[int, tuple[Doll, dict[str, float]]] = {}
        # The backs of heads that have their faces drawn on them, by the doll each is of.
        self._backs: dict[int, tuple[Doll, pygame.Surface]] = {}
        # The faces of bodies nobody has drawn, by whose each is, with the head it was made for.
        self._plain: dict[str, tuple[pygame.Surface, Face]] = {}
        # Dolls with their faces doing something, by the doll each is and what its face does.
        self._looks: dict[tuple, tuple[Doll, Doll]] = {}
        # Which doll the made hands and feet of each body were last told about.
        self._matched: dict[str, int] = {}

    @property
    def side(self) -> float:
        """How far round a body seen from its side is, in degrees."""
        return self.rules.side

    def new_frame(self) -> None:
        """Say that a frame has been shown: so many more dolls may be turned anew in the next."""
        self._turned.new_frame()

    def forget(self, body_id: str) -> None:
        """Have everything about a body read again, as after it has been drawn or changed."""
        self._said.pop(body_id, None)
        self._matched.pop(body_id, None)
        self._plain.pop(body_id, None)
        self.faces.forget(body_id)
        self.hands.forget(body_id)
        self.feet.forget(body_id)

    def changed(self, body_id: str) -> None:
        """Say that a body has been drawn anew by somebody who still has its face, its hands
        and its feet in hand: what is kept of how it was drawn is read again, and they are
        left as they are."""
        self._said.pop(body_id, None)
        self._matched.pop(body_id, None)

    def said(self, body_id: str | None) -> Said:
        """What has been said of a body besides its measures. Somebody with nothing kept, as
        one nobody has drawn, has a trunk seen from its side: the plain figure has."""
        if body_id is None:
            return Said(depth=self.rules.body.depth)
        if body_id not in self._said:
            kept = self.dolls.extras(body_id)
            turn = self.rules.body
            depth = kept.get(DEPTH_KEY)
            front = kept.get(TRUNK_KEY) == FRONT_DRAWN
            self._said[body_id] = Said(
                FRONT_DRAWN if front else SIDE_DRAWN,
                max(turn.depths[0], min(turn.depths[1], float(depth))) if isinstance(depth, (int, float)) else turn.depth,
                kept.get(FAR_KEY) if kept.get(FAR_KEY) in WAYS else OWN,
                self.dolls.extra_drawing(body_id, BACK_DRAWING) if front else None,
                limb_keys_from_data(kept.get(LIMBS_KEY), turn, self.rules.views),
            )
        return self._said[body_id]

    def made(self, body_id: str | None, doll: Doll) -> Made | None:
        """The hands and the feet of a body that are made and not drawn, told about the doll
        they go on: the colour and the width of the limb each is joined to, and how high its
        ankles stand. None for a body whose hands and feet are all drawn."""
        if body_id is None:
            return None
        hands, feet = self.hands.get(body_id), self.feet.get(body_id)
        if not hands.choice.made and not feet.choice.made:
            return None
        if self._matched.get(body_id) != doll._token:
            self._matched[body_id] = doll._token
            for kind in (hands, feet):
                part = doll.parts.get(kind.rules.matches)
                kind.natural = colour_at(part.image, part.end, MATCH_REACH) if part is not None else None
                wide = half_width_at(part.image, part.start, part.end) / doll.unit if part is not None else 0.0
                kind.joins = wide if wide > 0 else None
            ankle = doll.plan.pose(DOLL_FACINGS["right"]).get(feet.rules.matches_joint) if doll.plan is not None else None
            feet.stands = -ankle[1] if ankle is not None and ankle[1] < 0 else None
        return Made(hands, feet)

    def _is_cut(self, doll: Doll, front: bool, without: tuple[str, ...]) -> bool:
        """Whether a doll has been cut again that way already."""
        kept = self._cut.get((doll._token, front, tuple(sorted({*doll.without, *without}))))
        return kept is not None and kept[0] is doll

    def _again(self, doll: Doll, front: bool, without: tuple[str, ...], depth: float) -> Doll:
        """A doll cut again from the drawings of another: its trunk made into one seen from
        the front, if it is to be, and without the parts that are made instead."""
        without = tuple(sorted({*doll.without, *without}))
        if not front and without == tuple(sorted(doll.without)):
            return doll
        key = (doll._token, front, without)
        kept = self._cut.get(key)
        if kept is None or kept[0] is not doll:
            # Cutting a doll again is not quick: it counts as one turned a new way.
            self._turned.take()
            sheets = dict(doll.sheets)
            if front and BODY_CANVAS in sheets:
                sheets[BODY_CANVAS] = fronted(doll.template, sheets[BODY_CANVAS], self.rules.body.trunk, depth)
            if len(self._cut) > 256:
                self._cut.clear()
            kept = self._cut[key] = (doll, Doll(doll.template, sheets, doll.plan, without))
        return kept[1]

    def face_of(self, body_id: str | None, doll: Doll | None = None) -> Face | None:
        """The face of a body: its own, of pieces, if it has been drawn one. A body nobody
        has drawn at all, shown as `doll`, the figure the game draws of it, has a plain one
        that is the game's too. One drawn with its face on its head has no pieces."""
        if body_id is None:
            return None
        face = self.faces.get(body_id)
        if face.drawn or doll is None or not self.rules.moves.plain or self.dolls.get(body_id) is not None:
            return face
        head = doll.sheets.get(HEAD_CANVAS)
        if head is None:
            return face
        kept = self._plain.get(body_id)
        if kept is None or kept[0] is not head:
            kept = self._plain[body_id] = (head, plain_face(self.rules, head, example))
        return kept[1]

    def _looking(self, doll: Doll, face: Face, head: pygame.Surface, yaw: float, look: FaceLook) -> Doll:
        """A doll turned some way with its face doing something: the same body, and another head."""
        key = (id(doll), yaw, look, id(face), face.revision)
        kept = self._looks.get(key)
        if kept is None or kept[0] is not doll:
            if len(self._looks) > 384:
                self._looks.clear()
            kept = self._looks[key] = (doll, with_head(doll, face.fronting(head, yaw, look), face.backing(head, yaw)))
        return kept[1]

    def portrait(self, body_id: str, expression: str, size: tuple[int, int]) -> pygame.Surface | None:
        """The head of a body that has a face of pieces, seen from the front and feeling
        some way, brought to a size: for wherever a face is shown by itself. None for a body
        with no such face, whose head as it was drawn is all there is of it."""
        face = self.faces.get(body_id)
        head = self.dolls.drawings(body_id).get(HEAD_CANVAS) if face.drawn else None
        if head is None:
            return None
        look = FaceLook(mood=expression if expression in self.rules.moves.moods else "")
        boxes = [box for _, key, _, box in face.laid(head, 0.0, look) if key.shown and box.width]
        room = head.get_rect().unionall(boxes)
        # As large a square as takes all of it, the head in the middle across.
        side = max(room.width, room.height)
        room = pygame.Rect(room.centerx - side // 2, room.y - (side - room.height) // 2, side, side)
        whole = face.composed(head, 0.0, room=room, look=look)
        return whole if whole.get_size() == tuple(size) else pygame.transform.smoothscale(whole, size)

    def _behind(self, doll: Doll, head: pygame.Surface, yaw: float) -> Doll:
        """A doll whose face is drawn on its head, turned so far round: from behind its head is
        plain, the face fading as it goes round as one made of pieces does."""
        if yaw <= BEHIND_FROM:
            return doll
        kept = self._backs.get(doll._token)
        if kept is None or kept[0] is not doll:
            box = head.get_bounding_rect()
            if not box.width:
                return doll
            top = head.subsurface((box.x, box.y, box.width, max(1, round(box.height * HEAD_TOP))))
            try:
                plain = plain_back(head, max(1, round(box.width * HEAD_LINE)), (), _hair(head, main_colour(top)))
            except (pygame.error, ValueError, TypeError):
                plain = head
            if len(self._backs) > 256:
                self._backs.clear()
            kept = self._backs[doll._token] = (doll, plain)
        plain = kept[1]
        if yaw >= BEHIND_BY:
            return with_head(doll, (plain, (0, 0)))
        gone = (yaw - BEHIND_FROM) / (BEHIND_BY - BEHIND_FROM)
        return with_head(doll, _dissolved((head, (0, 0)), (plain, (0, 0)), gone))

    def shown(
        self,
        body_id: str | None,
        doll: Doll,
        yaw: float | None = None,
        step: float | None = None,
        look: FaceLook | None = None,
    ) -> Shown:
        """A doll turned `yaw` degrees round from facing whoever looks, as far as right behind
        at twice what its side is: from its side if it is not said. `doll` is the body as it
        was cut, with whatever it wears on, and `body_id` whose it is, if anybody's.

        `step` is in what steps of a turn it is kept turned, in degrees, where that is coarser
        than a head is: many are shown at once on a map, small, and each way one is turned is
        made once and kept.

        `look` is what its face is doing, if it has one of pieces and it is not seen from behind."""
        rules = self.rules
        if yaw is not None and step:
            yaw = max(0.0, min(2.0 * rules.side, round(abs(yaw) / step) * step))
        yaw = rules.side if yaw is None else rules.yaw_of(rules.stepped(yaw, behind=True))
        said = self.said(body_id)
        made = self.made(body_id, doll)
        without = made.bones if made is not None else ()
        # From its side, one drawn from its side is its drawing as it ever was.
        as_drawn = said.drawn == SIDE_DRAWN and abs(yaw - rules.side) < 1e-6
        if said.drawn == SIDE_DRAWN and not as_drawn and self._turned.spent and not self._is_cut(doll, True, without):
            # Its trunk has yet to be made into one seen from the front, and enough has been
            # made in this frame: until there is time it is its drawing, seen from its side.
            return self.shown(body_id, doll, look=look)
        base = self._again(doll, said.drawn == SIDE_DRAWN and not as_drawn, without, said.depth)

        face = self.face_of(body_id, doll)
        head = base.sheets.get(HEAD_CANVAS)

        def turn(to: float) -> Doll:
            seen = faced(base, face, head, to) if head is not None else base
            if head is not None and (face is None or not face.drawn):
                seen = self._behind(base, head, to)
            if said.drawn == SIDE_DRAWN and abs(to - rules.side) < 1e-6:
                return seen
            seen = turned_body(seen, rules.body, to, said.depth, rules.side, said.back)
            if said.far_side == DARKER:
                from_side = abs(math.sin(math.radians(to * 90.0 / rules.side)))
                seen = far_darker(seen, SHADE * round(from_side * SHADE_STEPS) / SHADE_STEPS)
            return seen

        who = (base._token, id(face), face.revision if face is not None else 0)
        turned = self._turned.seen(who, yaw, turn)
        if look and face is not None and head is not None and face.drawn and yaw <= BEHIND_FROM:
            turned = self._looking(turned, face, head, yaw, look)
        if made is not None:
            made_yaw = None if as_drawn else yaw
            for kind in made.kinds:
                if isinstance(kind, Feet):
                    kind.turned(made_yaw, rules.side)
                else:
                    kind.turned(made_yaw)
        if base._token not in self._apart or self._apart[base._token][0] is not base:
            if len(self._apart) > 256:
                self._apart.clear()
            self._apart[base._token] = (base, limbs_apart(rules.body, base))
        moved = limbs_moved(said.limbs, rules.views, yaw, rules.side) if said.limbs else {}
        return Shown(turned, made, self._apart[base._token][1], yaw, moved)

    def posed(self, shown: Shown, pose: dict[str, Point], facing: str) -> dict[str, Point]:
        """A pose as it is shown on a body turned as that one is: where its joints go across
        the screen. `facing` is the facing of the skeleton it is for."""
        if abs(shown.yaw - self.rules.side) < 1e-6 and not shown.moved:
            return pose
        _, _, mirrored, swapped = FACINGS[facing]
        return turned_pose(self.rules.body, shown.apart, pose, shown.yaw, self.rules.side, mirrored, swapped, shown.moved)

    def settle(self, body_id: str | None, clip: str | None, seconds: float | None = None) -> None:
        """Have the made hands of a body go towards the way they are held at a clip, by as
        much as the time gone by allows: at once, with no time given."""
        if body_id is None:
            return
        hands = self.hands.get(body_id)
        if hands.choice.made:
            hands.settle(hands.rules.pose_for(clip), seconds)

    def held(self, body_id: str | None, pose: HandPose | None) -> None:
        """Have the made hands of a body held one way, whatever it is at."""
        if body_id is not None and pose is not None and self.hands.get(body_id).choice.made:
            self.hands.get(body_id).settle(pose)

    def draw(
        self,
        target: pygame.Surface,
        shown: Shown,
        plan: SkeletonPlan,
        skeleton: Skeleton,
        origin: Point,
        detail: float,
        allowance: Allowance | None = None,
        grown: float = 1.0,
        foot: Point = (0.0, 0.0),
        **more: Any,
    ) -> None:
        """Draw a doll turned as it was asked for over a skeleton posed for it."""
        draw_doll(target, shown.doll, plan, skeleton, origin, detail, allowance, grown, foot, hands=shown.made, **more)
