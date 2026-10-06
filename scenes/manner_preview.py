"""Someone going through a manner on the spot, to see what it is like before it is theirs."""

import pygame

from graphics.doll import DOLL_FACINGS, Doll, DollStore, draw_doll
from graphics.doll_guide import reference
from graphics.item_icons import ItemIcons
from graphics.palette import PALETTE
from graphics.screen_layers import TRANSPARENT, ScreenLayers
from scenes.global_view import HELD_AHEAD, HELD_SIZE
from simulation.registries import BuiltInRegistries
from simulation.residents.manner import WALK, MannerDefinition
from skeleton.plan import SkeletonPlan
from skeleton.rig import Skeleton

# How many of the skeleton's pixels the place it is shown in is taken to be high: the body fills it by that.
PLACE_HEIGHT = 31.0
# How far above the bottom of the place the ground is, as a share of its height.
GROUND = 0.13
# Turns of the walking clip a second at one turn to the stride: slower than on the map, to be looked at.
WALK_RATE = 1.1
HAND_ANCHOR = "held_item"


class MannerPreview:
    """Shows a body doing something: a resident's own doll if they have been drawn, or else the
    figure every drawing starts from. Presentation only: it says nothing to the simulation."""

    def __init__(
        self,
        canvas: pygame.Surface,
        layers: ScreenLayers | None,
        plan: SkeletonPlan,
        dolls: DollStore,
        registries: BuiltInRegistries,
        icons: ItemIcons | None = None,
    ) -> None:
        self.canvas = canvas
        self.layers = layers
        self.plan = plan
        self.dolls = dolls
        self.registries = registries
        self.icons = icons
        self.time = 0.0
        self._example: Doll | None = None

    def update(self, seconds: float) -> None:
        self.time += seconds

    def example(self) -> Doll:
        """The figure of the guide, cut as a drawing would be."""
        if self._example is None:
            build = self.dolls.template.starting()
            built = self.dolls.template.built(build)
            self._example = self.dolls.made({name: reference(built, name) for name in built.canvases}, build)
        return self._example

    def doll_of(self, body_id: str | None) -> Doll:
        return (self.dolls.get(body_id) if body_id is not None else None) or self.example()

    def prop(self, manner: MannerDefinition) -> str | None:
        """Definition ID of something to put in the hand for a manner: the first item there is of the right sort."""
        kind = self.registries.manners.kinds.get(manner.kind)
        if kind is None or kind.prop_tag is None or self.icons is None:
            return None
        items = self.registries.items
        return next((item_id for item_id in items.ids() if kind.prop_tag in items.get(item_id).tags), None)

    def phase(self, manner: MannerDefinition) -> float:
        """How far through its clip the body is right now, in turns."""
        kind = self.registries.manners.kinds.get(manner.kind)
        walking = kind is not None and kind.occasion == WALK
        return self.time * manner.rate * (WALK_RATE if walking else 1.0)

    def picture(self, size: tuple[int, int], body_id: str | None, manner: MannerDefinition) -> pygame.Surface:
        """The body part-way through the manner, on a picture of its own with the ground under its feet."""
        picture = pygame.Surface(size, pygame.SRCALPHA)
        picture.fill(PALETTE["earth"])
        ground = round(size[1] * (1.0 - GROUND))
        pygame.draw.rect(picture, PALETTE["shadow"], (0, ground, size[0], size[1] - ground))
        doll = self.doll_of(body_id)
        plan = doll.plan or self.plan
        facing = DOLL_FACINGS["right"]
        pose = plan.pose(facing, manner.clip, self.phase(manner))
        skeleton = Skeleton(plan, facing)
        skeleton.set_pose(pose)
        detail = size[1] / PLACE_HEIGHT
        origin = (size[0] / 2 - detail * 2, float(ground))
        draw_doll(picture, doll, plan, skeleton, origin, detail)
        held = self.prop(manner)
        hand = plan.anchor(HAND_ANCHOR, facing, pose)
        if held is not None and hand is not None:
            thing = self.icons.held(held, max(3, round(HELD_SIZE * detail)))
            centre = (round(origin[0] + (hand[0] + HELD_AHEAD) * detail), round(origin[1] + hand[1] * detail))
            picture.blit(thing, thing.get_rect(center=centre))
        return picture

    def draw(self, rect: pygame.Rect, body_id: str | None, manner: MannerDefinition | None) -> None:
        """Show the body in a part of the canvas: at the window's own resolution where the canvas
        lets what is under it show, and on the canvas itself where it does not."""
        pygame.draw.rect(self.canvas, PALETTE["stone"], rect.inflate(2, 2), 1)
        if manner is None:
            self.canvas.fill(PALETTE["earth"], rect)
            return
        if self.layers is None or not self.canvas.get_flags() & pygame.SRCALPHA:
            fine = self.picture((rect.width * 2, rect.height * 2), body_id, manner)
            self.canvas.blit(pygame.transform.smoothscale(fine, rect.size), rect)
            return
        place = self.layers.on_screen(rect)
        self.canvas.fill(TRANSPARENT, rect)
        self.layers.picture_under(self.picture(place.size, body_id, manner), rect)
