"""Paper dolls: a body drawn once, cut apart where it bends, and moved by its skeleton.

A resident's body and head are drawn on two canvases of a fixed size, over a guide that marks where
each part goes and where it is jointed. The drawing is cut into those parts, and each part is laid
along its bone, turned as the bone turns. One drawing, seen from the side, does for every pose:
facing the other way it is the same drawing in a mirror.
"""

import json
import logging
import math
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any

import pygame

from graphics.illustrations import Illustrations
from graphics.palette import PALETTE
from skeleton.plan import PLAN_PATH, SIDES, SkeletonPlan, wrapped
from skeleton.rig import Skeleton

Point = tuple[float, float]
Color = tuple[int, int, int]

logger = logging.getLogger(__name__)

BODY_CANVAS = "body"
HEAD_CANVAS = "head"
# The measures of a doll are kept beside its drawings.
BUILD_FILE = "build.json"
# No part may be made shorter than this, in the skeleton's own measure, nor a limb be moved
# further than this from where the body plan joins it on.
SHORTEST_PART = 0.4
FURTHEST_ATTACHED = 5.0
# Parts are kept turned in this many steps of a full turn.
TURN_STEPS = 96
# The view of the skeleton that a doll is posed in, with its own build and order of drawing, and
# the way a doll faces for each side it can walk to.
DOLL_VIEW = "doll"
DOLL_FACINGS = {"right": "doll_right", "left": "doll_left"}
# Reaching this far, a half of the canvas is all of it.
FAR = 4096
# Parts on the far side of the body are tinted on the guide in one colour, the near side in another.
GUIDE_NEAR = PALETTE["sand"]
GUIDE_FAR = PALETTE["teal"]
GUIDE_MIDDLE = PALETTE["dust"]
GUIDE_JOINT = PALETTE["ember"]
# Pixels either side of a joint over which a limb is measured to see how wide it is drawn there.
JOINT_BAND = 2
# Pixels to one of the skeleton's at which a doll is laid out to see how much room it takes.
BOX_DETAIL = 4.0


def doll_path(body_id: str, canvas: str) -> str:
    """Where a resident's drawing of one canvas is kept, below the illustrations folder."""
    return f"dolls/{body_id}/{canvas}.png"


def build_path(body_id: str) -> str:
    """Where a resident's measures are kept, below the illustrations folder."""
    return f"dolls/{body_id}/{BUILD_FILE}"


def unsided(name: str) -> str:
    """The name of a bone or part without the side of the body it is on: both arms are one to the measures."""
    for side in SIDES:
        if name.endswith(side):
            return name[: -len(side)]
    return name


@dataclass
class DollBuild:
    """The measures of one doll: how its own are different from the template's.

    Someone drawn with short legs has short legs. The parts are as long as the guide was set for
    them, and a limb joins the trunk where it was put. Both sides of a body share their measures.
    """

    # How far each joint of the guide was moved along its part, in the skeleton's own measure, by
    # part and end: `shin.end` is the ankle.
    joints: dict[str, float] = field(default_factory=dict)
    # How far a joint that goes anywhere was moved, such as where a head sits on its neck.
    points: dict[str, Point] = field(default_factory=dict)
    # How far from where the body plan has them the bones that join a limb to the trunk end.
    attach: dict[str, Point] = field(default_factory=dict)

    def copy(self) -> "DollBuild":
        return DollBuild(dict(self.joints), dict(self.points), dict(self.attach))

    def to_data(self) -> dict[str, Any]:
        return {
            "joints": {key: round(value, 3) for key, value in self.joints.items()},
            "points": {key: [round(value[0], 3), round(value[1], 3)] for key, value in self.points.items()},
            "attach": {key: [round(value[0], 3), round(value[1], 3)] for key, value in self.attach.items()},
        }


def build_from_data(data: Any) -> DollBuild:
    """Measures as they were kept. Whatever of them cannot be read is left as the template has it."""
    build = DollBuild()
    if not isinstance(data, dict):
        return build
    for key, value in (data.get("joints") or {}).items() if isinstance(data.get("joints"), dict) else ():
        if isinstance(value, (int, float)):
            build.joints[str(key)] = float(value)
    for name, target in (("points", build.points), ("attach", build.attach)):
        kept = data.get(name)
        for key, value in kept.items() if isinstance(kept, dict) else ():
            if isinstance(value, (list, tuple)) and len(value) == 2 and all(isinstance(each, (int, float)) for each in value):
                target[str(key)] = (float(value[0]), float(value[1]))
    return build


@dataclass(frozen=True)
class JointHandle:
    """A joint of the guide that can be taken hold of to make a part longer or shorter."""

    # What the measures call it: a part and one of its ends.
    key: str
    canvas: str
    # Where it is on the canvas, and where the template has it.
    point: Point
    origin: Point
    # The way it may be moved. None for a joint that goes anywhere.
    axis: Point | None


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
    # The part is everything drawn on its canvas, such as a head with its hair.
    whole: bool = False
    # The part does not turn about its first joint against another: the trunk, which the rest hangs from.
    free_start: bool = False
    # Nor is it cut round at its second joint, though another part starts there: the shoulders of the
    # trunk are left as drawn, with the neck coming out of them.
    free_end: bool = False
    # What the part is on the example figure the guide shows: a sleeve, a shoe, a head.
    wears: str = ""

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
    # The measures a doll nobody has drawn yet starts from. The parts above say where the guide's
    # joints are before any measures: drawings made before there were measures are cut by those.
    start: DollBuild = field(default_factory=DollBuild)

    def starting(self) -> DollBuild:
        """The measures a new doll is given to begin with: the template's, if a doll can have them."""
        return self.start.copy() if self.takes(self.start) else DollBuild()

    def joint_keys(self) -> dict[tuple[str, Point], tuple[str, Point | None]]:
        """Every joint of the guide that can be moved, by canvas and place: what the measures call
        it, and the way it may go.

        A joint two parts share is the end of the first of them, and moves along it. A part that is
        everything on its canvas has one such joint, where it is joined on, which goes anywhere.
        """
        keys: dict[tuple[str, Point], tuple[str, Point | None]] = {}
        for bone, spec in self.parts.items():
            if not spec.whole:
                keys.setdefault((spec.canvas, spec.end), (f"{unsided(bone)}.end", _direction(spec)))
        for bone, spec in self.parts.items():
            axis = None if spec.whole else _direction(spec)
            keys.setdefault((spec.canvas, spec.start), (f"{unsided(bone)}.start", axis))
        return keys

    def built(self, build: DollBuild) -> "DollTemplate":
        """This template with its joints where a doll's measures have them."""
        if not build.joints and not build.points:
            return self
        # Where a limb starts is moved by itself, and takes the whole limb with it.
        moved: dict[tuple[str, Point], Point] = {}
        for place, (key, axis) in self.joint_keys().items():
            if not key.endswith(".start"):
                continue
            if axis is None:
                shift = build.points.get(key, (0.0, 0.0))
                moved[place] = (shift[0] * self.unit, shift[1] * self.unit)
            else:
                far = build.joints.get(key, 0.0) * self.unit
                moved[place] = (axis[0] * far, axis[1] * far)
        # Every other joint is the end of a part: moved, the part is that much longer or shorter,
        # and whatever hangs from it goes along as long as it was.
        waiting = [(bone, spec) for bone, spec in self.parts.items() if not spec.whole]
        while waiting:
            ready = [(bone, spec) for bone, spec in waiting if (spec.canvas, spec.start) in moved]
            if not ready:
                break
            for bone, spec in ready:
                way, begun = _direction(spec), moved[(spec.canvas, spec.start)]
                far = build.joints.get(f"{unsided(bone)}.end", 0.0) * self.unit
                moved.setdefault((spec.canvas, spec.end), (begun[0] + way[0] * far, begun[1] + way[1] * far))
            waiting = [entry for entry in waiting if entry not in ready]

        def at(canvas: str, point: Point) -> Point:
            shift = moved.get((canvas, point), (0.0, 0.0))
            return (point[0] + shift[0], point[1] + shift[1])

        parts = {
            bone: replace(spec, start=at(spec.canvas, spec.start), end=at(spec.canvas, spec.end))
            for bone, spec in self.parts.items()
        }
        return DollTemplate(self.unit, self.canvases, parts, self.start)

    def handles(self, built: "DollTemplate") -> list[JointHandle]:
        """The joints of a doll's guide that can be taken hold of, where its own measures have them."""
        found = []
        seen: set[tuple[str, Point]] = set()
        keys = self.joint_keys()
        for bone, spec in self.parts.items():
            for origin, point in ((spec.start, built.parts[bone].start), (spec.end, built.parts[bone].end)):
                place = (spec.canvas, origin)
                if place in keys and place not in seen:
                    seen.add(place)
                    key, axis = keys[place]
                    found.append(JointHandle(key, spec.canvas, point, origin, axis))
        return found

    def takes(self, build: DollBuild) -> bool:
        """Whether a doll can have these measures: every part still a part, every joint on its
        canvas, and nothing of a part over a part it does not meet."""
        built = self.built(build)
        for bone, spec in built.parts.items():
            width, height = self.canvases[spec.canvas]
            if not all(0 <= x <= width and 0 <= y <= height for x, y in (spec.start, spec.end)):
                return False
            if spec.whole:
                continue
            way = _direction(self.parts[bone])
            along = (spec.end[0] - spec.start[0]) * way[0] + (spec.end[1] - spec.start[1]) * way[1]
            if along < SHORTEST_PART * self.unit:
                return False
        own = {bone: pygame.mask.from_surface(built.region(bone)) for bone, spec in built.parts.items() if not spec.whole}
        for bone, region in own.items():
            spec = built.parts[bone]
            for other, other_region in own.items():
                if other <= bone or built.parts[other].canvas != spec.canvas:
                    continue
                if {spec.start, spec.end} & {built.parts[other].start, built.parts[other].end}:
                    continue
                # Two parts side by side may share the line between them, and no more.
                if region.overlap_area(other_region, (0, 0)) > 4 * self.unit:
                    return False
        return all(
            abs(shift[0]) <= FURTHEST_ATTACHED and abs(shift[1]) <= FURTHEST_ATTACHED for shift in build.attach.values()
        )

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

        A part takes what is drawn in its zone, up to each joint it turns about. There the drawing
        is cut straight across, and both parts that meet keep the same round end past the cut,
        centred on the joint and as wide as the limb was drawn there. However the joint bends, no
        corner of either sticks out and no gap opens.
        """
        spec = self.parts[bone]
        mask = self.region(bone)
        for joint, keep in self.cuts(spec):
            width = self._width_at(drawing, joint, keep, self.reach_at(spec, joint))
            if width > 0:
                pygame.draw.circle(mask, (255, 255, 255, 255), joint, width + 1)
        return mask

    def region(self, bone: str) -> pygame.Surface:
        """Where on its canvas a part is its own: its zone, as far as the joints it is cut at.

        White and solid there, clear elsewhere. Next to each other, the regions of a limb show where
        one part ends and the next begins.
        """
        spec = self.parts[bone]
        if spec.whole:
            return self.mask(bone)
        mask = pygame.Surface(self.canvases[spec.canvas], pygame.SRCALPHA)
        self._zone(mask, spec, (255, 255, 255, 255))
        for joint, keep in self.cuts(spec):
            # Everything on the far side of the cut is somebody else's.
            across = (-keep[1] * FAR, keep[0] * FAR)
            away = (-keep[0] * FAR, -keep[1] * FAR)
            pygame.draw.polygon(mask, (0, 0, 0, 0), [
                (joint[0] + across[0], joint[1] + across[1]),
                (joint[0] - across[0], joint[1] - across[1]),
                (joint[0] - across[0] + away[0], joint[1] - across[1] + away[1]),
                (joint[0] + across[0] + away[0], joint[1] + across[1] + away[1]),
            ])
        return mask

    def cuts(self, spec: PartSpec) -> list[tuple[Point, Point]]:
        """The joints a part is cut at, each with the side of the cut it keeps, as a direction."""
        if spec.whole:
            return []
        ends = ((spec.start, self._kept(spec, True)), (spec.end, self._kept(spec, False)))
        return [(joint, keep) for joint, keep in ends if keep]

    def sharing(self, spec: PartSpec, joint: Point) -> list[PartSpec]:
        """The other parts of the same canvas that have a joint at the same place."""
        return [
            other for other in self.parts.values()
            if other is not spec and other.canvas == spec.canvas and not other.whole and joint in (other.start, other.end)
        ]

    def reach_at(self, spec: PartSpec, joint: Point) -> float:
        """How far from a joint a limb is measured: no further than the narrowest zone that meets there."""
        return min([spec.reach, *(other.reach for other in self.sharing(spec, joint))])

    def _kept(self, spec: PartSpec, at_start: bool) -> Point | None:
        """Which side of the cut through one of its joints a part keeps, as a direction. None if it is not cut there."""
        joint = spec.start if at_start else spec.end
        own = _direction(spec)
        others = self.sharing(spec, joint)
        if not at_start:
            # At its far end a part is only cut if another goes on from there.
            starting = [other for other in others if other.start == joint]
            return (-own[0], -own[1]) if starting and not spec.free_end else None
        ending = [other for other in others if other.end == joint and not other.free_end]
        if ending:
            # It goes on from where another ends: the cut is square to that one, whichever way this one points.
            return _direction(ending[0])
        return None if spec.free_start else own

    def _width_at(self, drawing: pygame.Surface, joint: Point, keep: Point, reach: float) -> int:
        """Half the width of what is drawn along the cut through a joint, in pixels."""
        across = (-keep[1], keep[0])
        size = drawing.get_size()
        widest = 0
        for step in range(-JOINT_BAND, JOINT_BAND + 1):
            for offset in range(-int(reach), int(reach) + 1):
                x = round(joint[0] + keep[0] * step + across[0] * offset)
                y = round(joint[1] + keep[1] * step + across[1] * offset)
                if 0 <= x < size[0] and 0 <= y < size[1] and drawing.get_at((x, y))[3]:
                    widest = max(widest, abs(offset))
        return widest

    def _zone(self, target: pygame.Surface, spec: PartSpec, color: tuple[int, ...], width: int = 0) -> None:
        """Paint the zone of a part, or with `width` only its edge."""
        pygame.draw.polygon(target, color, spec.zone(), width)

    def _capsule(self, target: pygame.Surface, spec: PartSpec, color: tuple[int, ...]) -> None:
        """Paint the example of a part: a rounded strip from one joint to the next."""
        radius = round(spec.radius)
        pygame.draw.line(target, color, spec.start, spec.end, radius * 2 + 1)
        pygame.draw.circle(target, color, spec.start, radius)
        pygame.draw.circle(target, color, spec.end, radius)

    def guide(self, canvas: str) -> pygame.Surface:
        """What is shown under a canvas to draw over: every part in a zone of its own, the cuts
        between them, a dot at each joint, and a figure to take as a reference."""
        from graphics.doll_guide import build_guide

        return build_guide(self, canvas)

    def example(self, bone: str, color: Color, outline: Color | None = None) -> pygame.Surface:
        """The slim example of one part on a clear canvas, kept inside its zone.

        The trunk's stops at the shoulders, so that the neck shows between it and the head.
        """
        spec = self.parts[bone]
        surface = pygame.Surface(self.canvases[spec.canvas], pygame.SRCALPHA)
        edge = max(1, self.unit // 8) if outline is not None else 0
        if spec.whole:
            centre, radius = spec.end, round(spec.radius)
            if outline is not None:
                pygame.draw.circle(surface, outline, centre, radius)
            pygame.draw.circle(surface, color, centre, radius - edge)
            return surface
        if outline is not None:
            self._capsule(surface, spec, (*outline, 255))
        self._capsule(surface, replace(spec, radius=spec.radius - edge), (*color, 255))
        surface.blit(self.mask(bone), (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
        return surface

    def mannequin(self, colors: dict[str, Color], outline: Color = PALETTE["ink"]) -> dict[str, pygame.Surface]:
        """A plain figure filling every zone, in the colours given by bone: something to start a drawing from."""
        drawings = {name: pygame.Surface(size, pygame.SRCALPHA) for name, size in self.canvases.items()}
        for bone, spec in self.parts.items():
            drawings[spec.canvas].blit(self.example(bone, colors.get(bone, GUIDE_MIDDLE), outline), (0, 0))
            if spec.whole:
                # An eye, on the side it faces.
                radius = round(spec.radius)
                eye = (spec.end[0] + radius * 0.45, spec.end[1] - radius * 0.1)
                pygame.draw.circle(drawings[spec.canvas], outline, eye, max(2, radius // 8))
        return drawings


def _direction(spec: PartSpec) -> Point:
    """Which way a part runs on its canvas, from its first joint to its second."""
    dx, dy = spec.end[0] - spec.start[0], spec.end[1] - spec.start[1]
    length = math.hypot(dx, dy) or 1.0
    return (dx / length, dy / length)


def doll_rest(plan: SkeletonPlan, template: DollTemplate, build: DollBuild) -> dict[str, Point]:
    """Where the joints of a doll with its own measures stand at rest.

    Every bone that a part is drawn for is as long as the part is on its canvas and points the way
    it is drawn, so nothing has to be drawn out to fit. The bones between, which join a limb to
    the trunk, are as the body plan has them and moved by as much as the measures say. The whole
    is then stood back on the ground where the body plan's own stands.
    """
    base = plan.rests[DOLL_VIEW]
    placed = {plan.root: base[plan.root]}
    # Bones are listed from the root outwards, so a bone's start is always placed before it.
    for bone in plan.bones.values():
        (start_x, start_y), (end_x, end_y) = base[bone.start], base[bone.end]
        reach = (end_x - start_x, end_y - start_y)
        spec = template.parts.get(bone.name)
        if spec is not None:
            reach = ((spec.end[0] - spec.start[0]) / template.unit, (spec.end[1] - spec.start[1]) / template.unit)
        else:
            shift = build.attach.get(unsided(bone.name), (0.0, 0.0))
            reach = (reach[0] + shift[0], reach[1] + shift[1])
        placed[bone.end] = (placed[bone.start][0] + reach[0], placed[bone.start][1] + reach[1])
    lowest = max(y for _, y in base.values())
    feet = [joint for joint, (_, y) in base.items() if y >= lowest - 0.01]
    aside = sum(base[joint][0] - placed[joint][0] for joint in feet) / len(feet)
    down = lowest - max(placed[joint][1] for joint in feet)
    return {joint: (x + aside, y + down) for joint, (x, y) in placed.items()}


def doll_plan(plan: SkeletonPlan, template: DollTemplate, build: DollBuild) -> SkeletonPlan:
    """The body plan of one doll: the game's own, standing as that doll's measures have it."""
    return replace(plan, rests={**plan.rests, DOLL_VIEW: doll_rest(plan, template, build)})


def template_from_data(data: dict[str, Any]) -> DollTemplate:
    unit = int(data["unit"])
    canvases = {str(name): (int(size[0] * unit), int(size[1] * unit)) for name, size in data["canvases"].items()}
    parts = {}
    for bone, values in data["parts"].items():
        canvas = str(values["canvas"])
        if canvas not in canvases:
            raise ValueError(f"Doll part {bone} is drawn on unknown canvas: {canvas}")
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
            bool(values.get("whole", False)),
            bool(values.get("free_start", False)),
            bool(values.get("free_end", False)),
            str(values.get("wears", "")),
        )
    return DollTemplate(unit, canvases, parts, build_from_data(data.get("build")))


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

    def __init__(
        self, template: DollTemplate, drawings: dict[str, pygame.Surface], plan: SkeletonPlan | None = None
    ) -> None:
        self.unit = template.unit
        self.template = template
        # The body plan with this doll's own measures: whoever poses it goes by this one, and then
        # every part is as long on the doll as it was drawn. None for a doll laid over the game's own.
        self.plan = plan
        self.parts: dict[str, DollPart] = {}
        for bone, spec in template.parts.items():
            drawing = drawings.get(spec.canvas)
            if drawing is None:
                continue
            if drawing.get_size() != template.canvases[spec.canvas]:
                drawing = pygame.transform.smoothscale(drawing, template.canvases[spec.canvas])
            cut = drawing.convert_alpha() if pygame.display.get_surface() is not None else drawing.copy()
            # Whatever of the drawing falls outside the part's zone belongs to another part. It is made
            # clear and keeps its colour, so that no dark edge shows along a cut when the part is resized.
            keep = pygame.Surface(cut.get_size(), pygame.SRCALPHA)
            keep.fill((255, 255, 255, 0))
            keep.blit(template.cut_mask(bone, drawing), (0, 0), special_flags=pygame.BLEND_RGBA_MAX)
            cut.blit(keep, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
            box = cut.get_bounding_rect()
            if box.width == 0:
                continue
            self.parts[bone] = DollPart(
                cut.subsurface(box).copy(),
                (spec.start[0] - box.x, spec.start[1] - box.y),
                (spec.end[0] - box.x, spec.end[1] - box.y),
            )
        # How long each part is drawn, in the skeleton's own measure.
        self.drawn = {bone: math.dist(spec.start, spec.end) / template.unit for bone, spec in template.parts.items()}
        self._sized: dict[tuple, DollPart] = {}
        self._turned: dict[tuple, tuple[pygame.Surface, Point]] = {}
        self._standing: tuple[float, float, float, float] | None = None

    def standing(self, plan: SkeletonPlan) -> tuple[float, float, float, float]:
        """How far the doll reaches standing at rest, from the spot between its feet.

        Left, top, right and bottom in the skeleton's own measure, the same to either side so that
        it holds whichever way the doll faces. A doll is as tall as it was drawn, hair and hat and
        all, which is not the height of the game's own bodies.
        """
        if self._standing is None:
            facing = DOLL_FACINGS["right"]
            skeleton = Skeleton(plan, facing)
            skeleton.set_pose(plan.pose(facing))
            left, top, right, bottom = doll_box(self, plan, skeleton)
            half = max(-left, right)
            self._standing = (-half, top, half, bottom)
        return self._standing

    def _drawn_out(self, part: DollPart, stretch: int) -> DollPart:
        """A part made longer between its joints, to `stretch` hundredths of what was drawn.

        Only what lies between the two joints is drawn out. What goes past either joint stays as
        it was, so the round ends parts meet in stay round, and the part keeps its width.
        """
        axis = 1 if abs(part.end[1] - part.start[1]) >= abs(part.end[0] - part.start[0]) else 0
        size = part.image.get_size()
        low, high = sorted((part.start[axis], part.end[axis]))
        low, high = min(size[axis], max(0, round(low))), min(size[axis], max(0, round(high)))
        grown = round((high - low) * stretch / 100) - (high - low)
        if stretch == 100 or high <= low or grown <= -(high - low):
            return part

        def strip(first: int, last: int) -> pygame.Rect:
            return pygame.Rect(0, first, size[0], last - first) if axis else pygame.Rect(first, 0, last - first, size[1])

        longer = [size[0], size[1]]
        longer[axis] += grown
        image = pygame.Surface(longer, pygame.SRCALPHA)
        pieces = [(strip(0, low), 0, 0), (strip(low, high), low, grown), (strip(high, size[axis]), high + grown, 0)]
        for box, at, more in pieces:
            if box.width <= 0 or box.height <= 0:
                continue
            piece = part.image.subsurface(box)
            if more:
                piece = pygame.transform.smoothscale(piece, (box.width + more, box.height) if axis == 0 else (box.width, box.height + more))
            # Added to nothing, a piece is copied as it is, the colour of its clear pixels and all.
            image.blit(piece, (0, at) if axis else (at, 0), special_flags=pygame.BLEND_RGBA_ADD)
        middle = (low + high) / 2

        def moved(point: Point) -> Point:
            along = point[axis] + (grown if point[axis] > middle else 0)
            return (point[0], along) if axis else (along, point[1])

        return DollPart(image, moved(part.start), moved(part.end))

    def _sized_part(self, bone: str, mirrored: bool, detail: float, stretch: int) -> DollPart:
        """A part at the size it is shown, and in a mirror if the body faces the other way.

        `stretch` is how much longer than drawn its bone is, in hundredths.
        """
        key = (bone, mirrored, round(detail * 1000), stretch)
        if key not in self._sized:
            part = self._drawn_out(self.parts[bone], stretch)
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

    def placed(
        self, bone: str, mirrored: bool, detail: float, angle: float, length: float | None = None
    ) -> tuple[pygame.Surface, Point] | None:
        """A part turned to point along `angle`, and where on that picture its first joint is.

        `detail` is how many pixels of the target go to one of the skeleton's, and `length` how
        long the bone it is laid on is, if that is not the length it was drawn at. None if the
        drawing left that part empty.
        """
        if bone not in self.parts:
            return None
        stretch = round(100 * length / self.drawn[bone]) if length and self.drawn[bone] else 100
        part = self._sized_part(bone, mirrored, detail, stretch)
        drawn = math.atan2(part.end[0] - part.start[0], part.end[1] - part.start[1])
        steps = round(wrapped(angle - drawn) / math.tau * TURN_STEPS) % TURN_STEPS
        key = (bone, mirrored, round(detail * 1000), stretch, steps)
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

    def __init__(
        self, illustrations: Illustrations | None, template: DollTemplate, plan: SkeletonPlan | None = None
    ) -> None:
        self._illustrations = illustrations
        self.template = template
        # The game's body plan, which each doll gets with its own measures.
        self.plan = plan
        self._dolls: dict[str, Doll | None] = {}

    def build(self, body_id: str) -> DollBuild:
        """The measures of a body: its own if it has any that can be used.

        Someone nobody has drawn yet has the ones every doll starts from. A drawing kept without
        measures was made before there were any, over the guide as the template has it, and is
        left as it is.
        """
        root = self._illustrations.root if self._illustrations is not None else None
        if root is None:
            return self.template.starting()
        path = (root / build_path(body_id)).resolve()
        if not path.is_relative_to(root) or not path.is_file():
            return DollBuild() if self.drawings(body_id) else self.template.starting()
        try:
            build = build_from_data(json.loads(path.read_text(encoding="utf-8")))
        except (OSError, ValueError) as error:
            logger.warning("Measures could not be read: %s (%s)", path, error)
            return DollBuild()
        return build if self.template.takes(build) else DollBuild()

    def made(self, drawings: dict[str, pygame.Surface], build: DollBuild) -> Doll:
        """A doll cut from drawings by its own measures, with the body plan that goes with them."""
        template = self.template.built(build)
        plan = doll_plan(self.plan, template, build) if self.plan is not None else None
        return Doll(template, drawings, plan)

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
            self._dolls[body_id] = self.made(drawings, self.build(body_id)) if BODY_CANVAS in drawings else None
        return self._dolls[body_id]

    def forget(self, body_id: str) -> None:
        """Have a body's drawings read again, as after they have been changed."""
        self._dolls.pop(body_id, None)
        if self._illustrations is not None:
            for canvas in self.template.canvases:
                self._illustrations.forget(doll_path(body_id, canvas))


def doll_box(doll: Doll, plan: SkeletonPlan, skeleton: Skeleton) -> tuple[float, float, float, float]:
    """How far a doll laid over a skeleton reaches: left, top, right and bottom, in the skeleton's own measure."""
    left = top = math.inf
    right = bottom = -math.inf
    for name in plan.orders[DOLL_VIEW]:
        bone = skeleton.bones.get(skeleton.as_posed(name))
        placed = doll.placed(name, skeleton.mirrored, BOX_DETAIL, bone.angle, bone.length) if bone is not None else None
        if placed is None:
            continue
        image, joint = placed
        painted = image.get_bounding_rect()
        x = bone.a.x + 0.5 + (painted.x - joint[0]) / BOX_DETAIL
        y = bone.a.y + 0.5 + (painted.y - joint[1]) / BOX_DETAIL
        left, top = min(left, x), min(top, y)
        right, bottom = max(right, x + painted.width / BOX_DETAIL), max(bottom, y + painted.height / BOX_DETAIL)
    return (left, top, right, bottom) if left < right else (0.0, 0.0, 0.0, 0.0)


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
        # A limb may be longer on the skeleton than it was drawn: it is drawn out to fit.
        placed = doll.placed(name, skeleton.mirrored, detail, bone.angle, bone.length)
        if placed is None:
            continue
        image, joint = placed
        # A whole number of the skeleton's is the middle of one of its pixels.
        x = origin[0] + (bone.a.x + 0.5) * detail - joint[0]
        y = origin[1] + (bone.a.y + 0.5) * detail - joint[1]
        target.blit(image, (round(x), round(y)))
