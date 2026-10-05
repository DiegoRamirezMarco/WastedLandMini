"""Paper dolls: a body drawn once, cut apart where it bends, and moved by its skeleton.

A resident's body and head are drawn on two canvases of a fixed size, over a guide that marks where
each part goes and where it is jointed. The drawing is cut into those parts, and each part is laid
along its bone, turned as the bone turns. One drawing, seen from the side, does for every pose:
facing the other way it is the same drawing in a mirror.
"""

import json
import math
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

import pygame

from graphics.illustrations import Illustrations
from graphics.palette import PALETTE
from skeleton.plan import PLAN_PATH, SkeletonPlan, wrapped
from skeleton.rig import Skeleton

Point = tuple[float, float]
Color = tuple[int, int, int]

BODY_CANVAS = "body"
HEAD_CANVAS = "head"
# Parts are kept turned in this many steps of a full turn.
TURN_STEPS = 96
# The view of the skeleton that a doll is posed in, and its order of drawing.
DOLL_VIEW = "side"
# Parts on the far side of the body are tinted on the guide in one colour, the near side in another.
GUIDE_NEAR = PALETTE["sand"]
GUIDE_FAR = PALETTE["teal"]
GUIDE_MIDDLE = PALETTE["dust"]
GUIDE_JOINT = PALETTE["ember"]
# Pixels either side of a joint over which a limb is measured to see how wide it is drawn there.
JOINT_BAND = 2
# How solid the inside of a zone is on the guide, out of 255, and how thick its edge.
ZONE_FILL = 60
ZONE_EDGE = 2


def doll_path(body_id: str, canvas: str) -> str:
    """Where a resident's drawing of one canvas is kept, below the illustrations folder."""
    return f"dolls/{body_id}/{canvas}.png"


@dataclass(frozen=True)
class PartSpec:
    """Where one part is drawn on its canvas, along a line from one joint to the next.

    The example is the slim figure the guide shows. The zone is how far the part may be drawn: a
    good deal wider and longer, so that a body can be made stout, or any odd shape, and still be
    cut into its parts.
    """

    bone: str
    canvas: str
    start: Point
    end: Point
    # Half the width of the example.
    radius: float
    # Half the width of the zone, and how far it goes beyond the first joint and beyond the second.
    reach: float = 0.0
    ends: tuple[float, float] = (0.0, 0.0)
    # A rounder end to the example, for a hand or a foot: its offset from the far joint and its radius.
    cap: tuple[float, float, float] | None = None
    # The radius of the zone round that end, where it needs more room than the rest of the zone gives.
    cap_reach: float = 0.0
    # The part is everything drawn on its canvas, such as a head with its hair.
    whole: bool = False
    # The part does not turn about its first joint against another: the trunk, which the rest hangs from.
    free_start: bool = False

    def zone(self) -> list[Point]:
        """The corners of the zone: a box along the part, wider than it and reaching past both joints."""
        dx, dy = self.end[0] - self.start[0], self.end[1] - self.start[1]
        length = math.hypot(dx, dy) or 1.0
        along, across = (dx / length, dy / length), (-dy / length, dx / length)
        near = (self.start[0] - along[0] * self.ends[0], self.start[1] - along[1] * self.ends[0])
        far = (self.end[0] + along[0] * self.ends[1], self.end[1] + along[1] * self.ends[1])
        side = (across[0] * self.reach, across[1] * self.reach)
        return [
            (near[0] + side[0], near[1] + side[1]),
            (far[0] + side[0], far[1] + side[1]),
            (far[0] - side[0], far[1] - side[1]),
            (near[0] - side[0], near[1] - side[1]),
        ]


@dataclass(frozen=True)
class DollTemplate:
    # Pixels of a drawing to one pixel of the skeleton's own measure.
    unit: int
    # Size in pixels of each canvas.
    canvases: dict[str, tuple[int, int]]
    parts: dict[str, PartSpec]

    def mask(self, bone: str) -> pygame.Surface:
        """The zone of a part on its canvas: white and solid where the part is, clear elsewhere."""
        spec = self.parts[bone]
        mask = pygame.Surface(self.canvases[spec.canvas], pygame.SRCALPHA)
        if spec.whole:
            mask.fill((255, 255, 255, 255))
            return mask
        self._zone(mask, spec, (255, 255, 255, 255))
        return mask

    def cut_mask(self, bone: str, drawing: pygame.Surface) -> pygame.Surface:
        """What of a drawing goes with a part: white and solid there, clear elsewhere.

        Between its two joints a part takes all of its zone. Past a joint it turns about, it only
        takes a round end centred on that joint, as wide as the limb was drawn there. Two parts
        that meet at a joint so end in the same circle, and however the joint bends no corner of
        either sticks out.
        """
        spec = self.parts[bone]
        if spec.whole:
            return self.mask(bone)
        mask = pygame.Surface(self.canvases[spec.canvas], pygame.SRCALPHA)
        solid = (255, 255, 255, 255)
        followed = any(
            other is not spec and other.canvas == spec.canvas and other.start == spec.end for other in self.parts.values()
        )
        shaft = replace(
            spec,
            ends=(spec.ends[0] if spec.free_start else 0.0, 0.0 if followed else spec.ends[1]),
            cap_reach=0.0 if followed else spec.cap_reach,
        )
        self._zone(mask, shaft, solid)
        joints = ([] if spec.free_start else [spec.start]) + ([spec.end] if followed else [])
        for joint in joints:
            width = self._width_at(drawing, spec, joint)
            if width > 0:
                pygame.draw.circle(mask, solid, joint, width + 1)
        return mask

    def _width_at(self, drawing: pygame.Surface, spec: PartSpec, joint: Point) -> int:
        """Half the width of what is drawn across a part at one of its joints, in pixels."""
        dx, dy = spec.end[0] - spec.start[0], spec.end[1] - spec.start[1]
        length = math.hypot(dx, dy) or 1.0
        along, across = (dx / length, dy / length), (-dy / length, dx / length)
        size = drawing.get_size()
        widest = 0
        for step in range(-JOINT_BAND, JOINT_BAND + 1):
            for offset in range(-int(spec.reach), int(spec.reach) + 1):
                x = round(joint[0] + along[0] * step + across[0] * offset)
                y = round(joint[1] + along[1] * step + across[1] * offset)
                if 0 <= x < size[0] and 0 <= y < size[1] and drawing.get_at((x, y))[3]:
                    widest = max(widest, abs(offset))
        return widest

    def _zone(self, target: pygame.Surface, spec: PartSpec, color: tuple[int, ...], width: int = 0) -> None:
        """Paint the zone of a part, or with `width` only its edge."""
        pygame.draw.polygon(target, color, spec.zone(), width)
        if spec.cap is not None and spec.cap_reach > 0:
            centre = (spec.end[0] + spec.cap[0], spec.end[1] + spec.cap[1])
            pygame.draw.circle(target, color, centre, round(spec.cap_reach), width)

    def _capsule(self, target: pygame.Surface, spec: PartSpec, color: tuple[int, ...]) -> None:
        """Paint the example of a part: a rounded strip from one joint to the next."""
        radius = round(spec.radius)
        pygame.draw.line(target, color, spec.start, spec.end, radius * 2 + 1)
        pygame.draw.circle(target, color, spec.start, radius)
        pygame.draw.circle(target, color, spec.end, radius)
        if spec.cap is not None:
            pygame.draw.circle(target, color, (spec.end[0] + spec.cap[0], spec.end[1] + spec.cap[1]), round(spec.cap[2]))

    def guide(self, canvas: str) -> pygame.Surface:
        """What is shown under a canvas to draw over.

        For every part, a slim example of it, the frame of the zone it may be drawn in, faintly
        filled, and a dot at each joint.
        """
        guide = pygame.Surface(self.canvases[canvas], pygame.SRCALPHA)
        mine = [(bone, spec) for bone, spec in self.parts.items() if spec.canvas == canvas]
        tints = {
            bone: GUIDE_NEAR if bone.endswith("_right") else (GUIDE_FAR if bone.endswith("_left") else GUIDE_MIDDLE)
            for bone, _ in mine
        }
        for bone, spec in mine:
            if not spec.whole:
                self._zone(guide, spec, (*tints[bone], ZONE_FILL))
        for bone, spec in mine:
            if not spec.whole:
                self._zone(guide, spec, (*tints[bone], 255), ZONE_EDGE)
        for bone, spec in mine:
            if spec.whole:
                pygame.draw.circle(guide, (*tints[bone], 255), spec.end, round(spec.radius))
                continue
            self._capsule(guide, spec, (*tints[bone], 255))
        for spec in self.parts.values():
            if spec.canvas == canvas:
                for joint in (spec.start, spec.end):
                    pygame.draw.circle(guide, GUIDE_JOINT, joint, max(2, self.unit // 5))
        return guide

    def mannequin(self, colors: dict[str, Color], outline: Color = PALETTE["ink"]) -> dict[str, pygame.Surface]:
        """A plain figure filling every zone, in the colours given by bone: something to start a drawing from."""
        drawings = {name: pygame.Surface(size, pygame.SRCALPHA) for name, size in self.canvases.items()}
        edge = max(1, self.unit // 8)
        for bone, spec in self.parts.items():
            surface = drawings[spec.canvas]
            color = colors.get(bone, GUIDE_MIDDLE)
            if spec.whole:
                centre, radius = spec.end, round(spec.radius)
                pygame.draw.circle(surface, outline, centre, radius + edge)
                pygame.draw.circle(surface, color, centre, radius)
                # An eye, on the side it faces.
                pygame.draw.circle(surface, outline, (centre[0] + radius * 0.45, centre[1] - radius * 0.1), max(2, radius // 8))
                continue
            self._capsule(surface, spec, (*outline, 255))
            inner = (spec.cap[0], spec.cap[1], spec.cap[2] - edge) if spec.cap is not None else None
            thin = PartSpec(spec.bone, spec.canvas, spec.start, spec.end, spec.radius - edge, cap=inner)
            self._capsule(surface, thin, (*color, 255))
        return drawings


def template_from_data(data: dict[str, Any]) -> DollTemplate:
    unit = int(data["unit"])
    canvases = {str(name): (int(size[0] * unit), int(size[1] * unit)) for name, size in data["canvases"].items()}
    parts = {}
    for bone, values in data["parts"].items():
        canvas = str(values["canvas"])
        if canvas not in canvases:
            raise ValueError(f"Doll part {bone} is drawn on unknown canvas: {canvas}")
        cap = values.get("cap")
        radius = float(values["radius"])
        ends = values.get("ends", (radius, radius))
        parts[str(bone)] = PartSpec(
            str(bone),
            canvas,
            (values["from"][0] * unit, values["from"][1] * unit),
            (values["to"][0] * unit, values["to"][1] * unit),
            radius * unit,
            # Without a reach of its own, a part may be drawn no wider than its example.
            float(values.get("reach", radius)) * unit,
            (float(ends[0]) * unit, float(ends[1]) * unit),
            (cap[0] * unit, cap[1] * unit, cap[2] * unit) if cap is not None else None,
            float(values.get("cap_reach", 0.0)) * unit,
            bool(values.get("whole", False)),
            bool(values.get("free_start", False)),
        )
    return DollTemplate(unit, canvases, parts)


def load_template(path: Path = PLAN_PATH) -> DollTemplate:
    return template_from_data(json.loads(path.read_text(encoding="utf-8"))["doll"])


@dataclass(frozen=True)
class DollPart:
    """One part cut out of a drawing: its picture, and where on it the part is jointed."""

    image: pygame.Surface
    start: Point
    end: Point


class Doll:
    """A drawing cut into its parts, ready to be laid over a skeleton."""

    def __init__(self, template: DollTemplate, drawings: dict[str, pygame.Surface]) -> None:
        self.unit = template.unit
        self.parts: dict[str, DollPart] = {}
        for bone, spec in template.parts.items():
            drawing = drawings.get(spec.canvas)
            if drawing is None:
                continue
            if drawing.get_size() != template.canvases[spec.canvas]:
                drawing = pygame.transform.smoothscale(drawing, template.canvases[spec.canvas])
            cut = drawing.convert_alpha() if pygame.display.get_surface() is not None else drawing.copy()
            # Whatever of the drawing falls outside the part's zone belongs to another part.
            cut.blit(template.cut_mask(bone, drawing), (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
            box = cut.get_bounding_rect()
            if box.width == 0:
                continue
            self.parts[bone] = DollPart(
                cut.subsurface(box).copy(),
                (spec.start[0] - box.x, spec.start[1] - box.y),
                (spec.end[0] - box.x, spec.end[1] - box.y),
            )
        self._sized: dict[tuple[str, bool, int], DollPart] = {}
        self._turned: dict[tuple[str, bool, int, int], tuple[pygame.Surface, Point]] = {}

    def _sized_part(self, bone: str, mirrored: bool, detail: float) -> DollPart:
        """A part at the size it is shown, and in a mirror if the body faces the other way."""
        key = (bone, mirrored, round(detail * 1000))
        if key not in self._sized:
            part = self.parts[bone]
            factor = detail / self.unit
            size = (max(1, round(part.image.get_width() * factor)), max(1, round(part.image.get_height() * factor)))
            image = pygame.transform.smoothscale(part.image, size)
            start = (part.start[0] * factor, part.start[1] * factor)
            end = (part.end[0] * factor, part.end[1] * factor)
            if mirrored:
                image = pygame.transform.flip(image, True, False)
                start, end = (size[0] - start[0], start[1]), (size[0] - end[0], end[1])
            self._sized[key] = DollPart(image, start, end)
        return self._sized[key]

    def placed(self, bone: str, mirrored: bool, detail: float, angle: float) -> tuple[pygame.Surface, Point] | None:
        """A part turned to point along `angle`, and where on that picture its first joint is.

        `detail` is how many pixels of the target go to one of the skeleton's. None if the drawing
        left that part empty.
        """
        if bone not in self.parts:
            return None
        part = self._sized_part(bone, mirrored, detail)
        drawn = math.atan2(part.end[0] - part.start[0], part.end[1] - part.start[1])
        steps = round(wrapped(angle - drawn) / math.tau * TURN_STEPS) % TURN_STEPS
        key = (bone, mirrored, round(detail * 1000), steps)
        if key not in self._turned:
            turn = steps * math.tau / TURN_STEPS
            image = pygame.transform.rotozoom(part.image, math.degrees(turn), 1.0) if steps else part.image
            # Where the joint went: it turned about the middle of the picture, and the picture grew to fit.
            from_middle = (part.start[0] - part.image.get_width() / 2, part.start[1] - part.image.get_height() / 2)
            sine, cosine = math.sin(turn), math.cos(turn)
            joint = (
                image.get_width() / 2 + from_middle[0] * cosine + from_middle[1] * sine,
                image.get_height() / 2 - from_middle[0] * sine + from_middle[1] * cosine,
            )
            self._turned[key] = (image, joint)
        return self._turned[key]


class DollStore:
    """The dolls there are drawings for, cut the first time each is asked for."""

    def __init__(self, illustrations: Illustrations | None, template: DollTemplate) -> None:
        self._illustrations = illustrations
        self.template = template
        self._dolls: dict[str, Doll | None] = {}

    def drawings(self, body_id: str) -> dict[str, pygame.Surface]:
        """The drawings kept for a body, by canvas. Empty if nobody has drawn it."""
        if self._illustrations is None:
            return {}
        found = {canvas: self._illustrations.find(doll_path(body_id, canvas)) for canvas in self.template.canvases}
        return {canvas: picture for canvas, picture in found.items() if picture is not None}

    def get(self, body_id: str) -> Doll | None:
        """The doll of a body. None unless its body has been drawn."""
        if body_id not in self._dolls:
            drawings = self.drawings(body_id)
            self._dolls[body_id] = Doll(self.template, drawings) if BODY_CANVAS in drawings else None
        return self._dolls[body_id]

    def forget(self, body_id: str) -> None:
        """Have a body's drawings read again, as after they have been changed."""
        self._dolls.pop(body_id, None)
        if self._illustrations is not None:
            for canvas in self.template.canvases:
                self._illustrations.forget(doll_path(body_id, canvas))


def draw_doll(
    target: pygame.Surface,
    doll: Doll,
    plan: SkeletonPlan,
    skeleton: Skeleton,
    origin: Point,
    detail: float,
) -> None:
    """Lay a doll's parts over a skeleton, the furthest first.

    `origin` is where on the target the skeleton's own (0, 0) falls, and `detail` how many pixels
    of the target go to one of the skeleton's.
    """
    for name in plan.orders[DOLL_VIEW]:
        bone = skeleton.bones.get(skeleton.as_posed(name))
        if bone is None:
            continue
        placed = doll.placed(name, skeleton.mirrored, detail, bone.angle)
        if placed is None:
            continue
        image, joint = placed
        # A whole number of the skeleton's is the middle of one of its pixels.
        x = origin[0] + (bone.a.x + 0.5) * detail - joint[0]
        y = origin[1] + (bone.a.y + 0.5) * detail - joint[1]
        target.blit(image, (round(x), round(y)))
