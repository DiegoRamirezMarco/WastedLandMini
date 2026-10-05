"""Draws resident bodies over their skeletons: a sprite or a strip of colour on each bone."""

import math
import weakref
from dataclasses import dataclass

import pygame

from graphics.assets import AssetStore
from graphics.palette import PALETTE
from skeleton.plan import FACINGS, SKIN_VIEWS, SkeletonPlan, wrapped
from skeleton.rig import Bone, Skeleton

# The space a body takes standing at rest, with its feet at the bottom centre.
FRAME_SIZE = (16, 24)
# A parts sheet: one column per skin view, each with a head, a trunk and the strips for the limbs.
VIEW_WIDTH = 16
SPRITE_CELLS = {"head": pygame.Rect(0, 0, VIEW_WIDTH, 16), "torso": pygame.Rect(0, 16, VIEW_WIDTH, 12)}
STRIP_TOP = 28
STRIP_SIZE = (3, 8)
STRIP_SPACING = 4
STRIP_CELLS = ("upper_arm", "forearm", "thigh", "shin")
SHEET_SIZE = (VIEW_WIDTH * len(SKIN_VIEWS), STRIP_TOP + STRIP_SIZE[1])
# The column of a sprite cell that falls on the middle of the body.
ANCHOR_COLUMN = 7
# The pixel of that space that the spot between the feet falls on.
FRAME_ORIGIN = (ANCHOR_COLUMN, FRAME_SIZE[1] - 2)
# A posed body is drawn once on a canvas this size and kept, with the spot between its feet here.
CANVAS_SIZE = (32, 32)
CANVAS_ORIGIN = (15, 28)
# Room left round a body that lies still when its picture is kept: a head may reach that far from its joint.
REST_MARGIN = 12
# Sprites turn in steps, so that a turned one can be kept.
TURN_STEPS = 16
OUTLINE = PALETTE["ink"]

Frame = tuple[pygame.Surface, tuple[int, int]]


def _nearest(value: float, mirrored: bool = False) -> int:
    """The pixel a position falls on. Halves always go the same way, unlike with `round`.

    For a mirrored body they go the other way, so that it is the exact mirror image of the unmirrored one.
    """
    return math.ceil(value - 0.5) if mirrored else math.floor(value + 0.5)


@dataclass(frozen=True)
class Sprite:
    image: pygame.Surface
    # The pixel of the image that sits on the bone.
    anchor: tuple[int, int]


@dataclass(frozen=True)
class Strip:
    # Colours from the end of the bone nearer the body to the far one.
    colors: tuple[tuple[int, int, int], ...]
    thickness: int


@dataclass
class BodySkin:
    """What one body wears, cut out of its parts sheet."""

    sprites: dict[tuple[str, str, bool], Sprite]
    strips: dict[tuple[str, str], Strip]


def _read_strip(sheet: pygame.Surface, area: pygame.Rect) -> Strip:
    thickness = sum(1 for x in range(area.width) if sheet.get_at((area.x + x, area.y))[3]) or 1
    colors = []
    for y in range(area.height):
        red, green, blue, alpha = sheet.get_at((area.x, area.y + y))
        if not alpha:
            break
        colors.append((red, green, blue))
    return Strip(tuple(colors) or (OUTLINE,), thickness)


def read_skin(sheet: pygame.Surface) -> BodySkin:
    sprites, strips = {}, {}
    for column, view in enumerate(SKIN_VIEWS):
        left = column * VIEW_WIDTH
        for cell, area in SPRITE_CELLS.items():
            image = sheet.subsurface(area.move(left, 0))
            anchor_y = area.height // 2
            sprites[(view, cell, False)] = Sprite(image, (ANCHOR_COLUMN, anchor_y))
            sprites[(view, cell, True)] = Sprite(
                pygame.transform.flip(image, True, False), (area.width - 1 - ANCHOR_COLUMN, anchor_y)
            )
        for index, cell in enumerate(STRIP_CELLS):
            strips[(view, cell)] = _read_strip(
                sheet, pygame.Rect(left + index * STRIP_SPACING, STRIP_TOP, *STRIP_SIZE)
            )
    return BodySkin(sprites, strips)


def _line(start: tuple[int, int], end: tuple[int, int]) -> list[tuple[int, int]]:
    """Every pixel from one point to another, in order."""
    (x, y), (end_x, end_y) = start, end
    dx, dy = abs(end_x - x), -abs(end_y - y)
    step_x, step_y = (1 if x < end_x else -1), (1 if y < end_y else -1)
    error = dx + dy
    points = [(x, y)]
    while (x, y) != (end_x, end_y):
        doubled = 2 * error
        if doubled >= dy:
            error += dy
            x += step_x
        if doubled <= dx:
            error += dx
            y += step_y
        points.append((x, y))
    return points


class BodyRenderer:
    def __init__(self, assets: AssetStore, plan: SkeletonPlan) -> None:
        self._assets = assets
        self.plan = plan
        self._skins: dict[str, BodySkin] = {}
        self._turned: dict[tuple[int, int], Sprite] = {}
        self._frames: dict[tuple, Frame] = {}
        # The picture of each skeleton that lies still, and the corner it is drawn from.
        self._settled: weakref.WeakKeyDictionary[Skeleton, Frame] = weakref.WeakKeyDictionary()

    def skin(self, body_id: str) -> BodySkin:
        """The parts of a body. A missing sheet yields placeholder parts."""
        if body_id not in self._skins:
            sheet = self._assets.image(f"sprites/bodies/{body_id}.png", size=SHEET_SIZE)
            self._skins[body_id] = read_skin(sheet)
        return self._skins[body_id]

    def head(self, body_id: str, facing: str = "down") -> pygame.Surface:
        """The head of a body by itself, as for someone lying under a blanket."""
        _, view, mirrored, _ = FACINGS[facing]
        return self.skin(body_id).sprites[(view, "head", mirrored)].image

    def frames(self, clip: str, facing: str) -> int:
        """How many pictures a clip is kept as, for a body facing one way."""
        keyframes = self.plan.frames(clip, FACINGS[facing][0])
        return 1 if keyframes == 1 else keyframes * 2

    def frame(
        self,
        body_id: str,
        facing: str,
        clip: str,
        index: int = 0,
        lost: tuple[str, ...] = (),
        overlay: str | None = None,
    ) -> Frame:
        """A posed body, and where on that picture the spot between its feet is. Drawn once and kept."""
        count = self.frames(clip, facing)
        index %= count
        key = (body_id, facing, clip, index, lost, overlay)
        if key not in self._frames:
            skeleton = Skeleton(self.plan, facing, lost)
            skeleton.set_pose(self.plan.pose(facing, clip, index / count, overlay))
            canvas = pygame.Surface(CANVAS_SIZE, pygame.SRCALPHA)
            self.draw(canvas, skeleton, body_id, CANVAS_ORIGIN)
            self._frames[key] = (canvas, CANVAS_ORIGIN)
        return self._frames[key]

    def is_settled(self, skeleton: Skeleton) -> bool:
        """Whether a skeleton is being drawn from a kept picture, having come to rest."""
        return skeleton in self._settled

    def draw_limp(
        self, target: pygame.Surface, skeleton: Skeleton, body_id: str, offset: tuple[int, int] = (0, 0)
    ) -> None:
        """Draw a skeleton that physics moves: joint by joint while it does, from one picture once it sleeps."""
        if not skeleton.asleep:
            self._settled.pop(skeleton, None)
            self.draw(target, skeleton, body_id, offset)
            return
        if skeleton not in self._settled:
            left, top, right, bottom = skeleton.bounds()
            corner = (math.floor(left) - REST_MARGIN, math.floor(top) - REST_MARGIN)
            size = (math.ceil(right - left) + REST_MARGIN * 2, math.ceil(bottom - top) + REST_MARGIN * 2)
            picture = pygame.Surface(size, pygame.SRCALPHA)
            self.draw(picture, skeleton, body_id, (-corner[0], -corner[1]))
            self._settled[skeleton] = (picture, corner)
        picture, corner = self._settled[skeleton]
        target.blit(picture, (corner[0] + offset[0], corner[1] + offset[1]))

    def draw(
        self, target: pygame.Surface, skeleton: Skeleton, body_id: str, offset: tuple[int, int] = (0, 0)
    ) -> None:
        """Draw a skeleton's bones from the furthest to the nearest, wherever its joints are now."""
        skin = self.skin(body_id)
        view, mirrored = skeleton.skin_view, skeleton.mirrored
        for name in self.plan.orders[view]:
            bone = skeleton.bones.get(skeleton.as_posed(name))
            spec = self.plan.skins.get(name)
            if bone is None or spec is None:
                continue
            if spec.kind == "strip":
                self._draw_strip(target, bone, skin.strips[(view, spec.cell)], offset, mirrored)
            else:
                self._draw_sprite(target, skeleton, bone, skin.sprites[(view, spec.cell, mirrored)], spec.anchor, offset)

    def _draw_strip(
        self, target: pygame.Surface, bone: Bone, strip: Strip, offset: tuple[int, int], mirrored: bool
    ) -> None:
        thickness = strip.thickness
        inset = (thickness - 1) / 2
        points = _line(
            (_nearest(bone.a.x - inset, mirrored) + offset[0], _nearest(bone.a.y - inset) + offset[1]),
            (_nearest(bone.b.x - inset, mirrored) + offset[0], _nearest(bone.b.y - inset) + offset[1]),
        )
        for x, y in points:
            target.fill(OUTLINE, (x - 1, y, thickness + 2, thickness))
            target.fill(OUTLINE, (x, y - 1, thickness, thickness + 2))
        colors = strip.colors
        for index, (x, y) in enumerate(points):
            target.fill(colors[index * len(colors) // len(points)], (x, y, thickness, thickness))

    def _draw_sprite(
        self,
        target: pygame.Surface,
        skeleton: Skeleton,
        bone: Bone,
        sprite: Sprite,
        anchor: str,
        offset: tuple[int, int],
    ) -> None:
        if anchor == "end":
            x, y = bone.b.x, bone.b.y
        elif anchor == "start":
            x, y = bone.a.x, bone.a.y
        else:
            x, y = (bone.a.x + bone.b.x) / 2, (bone.a.y + bone.b.y) / 2
        # The sprite is drawn as the bone points at rest; it turns by however far the bone has.
        rest = self.plan.rest_angle(skeleton.view, skeleton.as_posed(bone.name))
        turn = wrapped(bone.angle - (-rest if skeleton.mirrored else rest))
        steps = _nearest(turn / math.tau * TURN_STEPS) % TURN_STEPS
        if steps:
            sprite = self._turn(sprite, steps)
        left = _nearest(x, skeleton.mirrored) - sprite.anchor[0] + offset[0]
        target.blit(sprite.image, (left, _nearest(y) - sprite.anchor[1] + offset[1]))

    def _turn(self, sprite: Sprite, steps: int) -> Sprite:
        key = (id(sprite), steps)
        if key not in self._turned:
            # Turned about its anchor: on a square with the anchor in the very middle.
            width, height = sprite.image.get_size()
            reach = max(sprite.anchor[0], sprite.anchor[1], width - sprite.anchor[0], height - sprite.anchor[1])
            square = pygame.Surface((reach * 2 + 1, reach * 2 + 1), pygame.SRCALPHA)
            square.blit(sprite.image, (reach - sprite.anchor[0], reach - sprite.anchor[1]))
            image = pygame.transform.rotate(square, steps * 360 / TURN_STEPS)
            self._turned[key] = Sprite(image, (image.get_width() // 2, image.get_height() // 2))
        return self._turned[key]
