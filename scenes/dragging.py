"""Picking things up with the mouse and putting them down (P27).

Somebody on the map is picked up by dragging them, and so is a child in its blanket. A thing
that stands on the map is picked up by holding the button down on it a moment first, so that
dragging across the map goes on moving the view. A thing somebody carries, or that is kept
somewhere, is dragged out of the panel it is listed in. What is under the pointer lights up
and says what letting go there would do.

Nothing here decides anything: the world is asked what would come of it, and told what was
let go where, by stable IDs.
"""

import math
from dataclasses import dataclass
from typing import TYPE_CHECKING

import pygame

from graphics.body_renderer import FRAME_ORIGIN, FRAME_SIZE
from graphics.building_renderer import building_area
from graphics.font import LINE_HEIGHT
from graphics.palette import PALETTE
from scenes.body_stage import FEET_ABOVE_EDGE
from settings import TILE_SIZE
from simulation.ai.placing import CHILD, CHOOSE, GROUND, OBJECT, RESIDENT, ROOM, SITE, WITH
from simulation.commands import (
    HandChildCommand,
    HandItemCommand,
    HoldResidentCommand,
    MoveObjectCommand,
    PutDownCommand,
    ReleaseResidentCommand,
)
from simulation.items.handing import TO_CONTAINER, TO_RESIDENT
from world.map import Tile

if TYPE_CHECKING:
    from scenes.global_view import GlobalView

# What can be in the hand: somebody, a child in its blanket, a thing that stands on the map,
# or a thing that is carried or kept.
SOMEBODY, BUNDLE, THING, ITEM = "resident", "child", "thing", "item"
# Seconds the button is held down on a thing that stands on the map before it comes up.
LIFT_SECONDS = 0.35
# How far under the pointer the feet of whoever is held hang, in map pixels: they are held by
# the scruff of the neck.
HELD_BELOW = 16.0
# The clip of a body that hangs from a hand: its legs behind it at 0, straight down half-way
# through, and in front of it at 1.
DANGLE_CLIP = "dangle"
# How fast across the map, in map pixels a second, the hand has to go for the legs of whoever
# hangs from it to trail as far as they go; how quickly they come to trail, in shares of the
# way left a second; and how far and how fast they kick with the hand still.
SWING_SPEED = 110.0
SWING_RATE = 9.0
KICK = 0.16
KICK_RATE = 1.3
# Canvas pixels from the edge of the map at which carrying something moves the view, and how
# fast, in canvas pixels a second.
EDGE = 12
EDGE_SPEED = 150.0
HINT_OFFSET = (10, 12)
BACK_ON_MAP = "Suéltalo en el mapa"
BACK = "Vuelve a donde estaba"
CHILD_NEEDS_ARMS = "A un bebé se le deja en brazos de alguien"
ITEM_NEEDS_PLACE = "Suéltalo sobre alguien, o sobre algo donde se guarden cosas"
THING_MOVES = "Se pondrá aquí"
LIFTED = "Lo llevas en la mano: suéltalo donde quieras"


@dataclass(frozen=True)
class Held:
    """What is in the hand, by its stable ID."""

    kind: str
    held_id: str


@dataclass(frozen=True)
class Target:
    """What is under the pointer while something is in the hand, and what letting go there would do."""

    ok: bool
    text: str
    on_kind: str = GROUND
    on_id: str | None = None
    tile: Tile | None = None
    # What lights up, on the canvas.
    box: pygame.Rect | None = None
    # The tile somebody would come down on, where it is bare ground they are over.
    lands: Tile | None = None


class DragController:
    def __init__(self, view: "GlobalView") -> None:
        self.view = view
        # What the button went down on that could be picked up, and for how many seconds it
        # has been down there without the mouse going anywhere.
        self.pressed: Held | None = None
        self.pressed_for = 0.0
        self.held: Held | None = None
        # How far through its clip the body of whoever is held is, and how far their legs trail.
        self.swing = 0.5
        self._lean = 0.0
        self._last: tuple[float, float] | None = None
        self._clock = 0.0
        # Where on a thing that stands on the map it was taken, in tiles from its corner.
        self._grip: Tile = (0, 0)
        self.target: Target | None = None

    @property
    def active(self) -> bool:
        return self.held is not None

    def carries(self, kind: str, held_id: str) -> bool:
        return self.held is not None and self.held.kind == kind and self.held.held_id == held_id

    # ----- picking up -----

    def what_at(self, position: tuple[int, int]) -> Held | None:
        """What at a canvas position could be picked up, if anything."""
        view = self.view
        if view.inside is not None or view.hud.wheel.open:
            return None
        if not view._on_map(position):
            intent = view.hud.click(position)
            item_id = view.hud.item_at(position) if isinstance(intent, tuple) and intent[0] == "edit_item" else None
            return Held(ITEM, item_id) if item_id is not None else None
        bundle = [child_id for child_id, box in view.bundle_boxes.items() if box.collidepoint(position)]
        if bundle:
            return Held(BUNDLE, bundle[-1])
        picked = [resident_id for resident_id, box in view.hitboxes.items() if box.collidepoint(position)]
        if picked:
            # Whoever has come to trade or knocks at the gate is nobody to carry about.
            return Held(SOMEBODY, picked[-1]) if picked[-1] in view.world.residents else None
        things = [object_id for object_id, box in view.object_boxes.items() if box.collidepoint(position)]
        return Held(THING, things[-1]) if things else None

    def press(self, position: tuple[int, int]) -> bool:
        """The button has gone down. Says whether it is on something that could be picked up."""
        self.pressed, self.pressed_for = self.what_at(position), 0.0
        return self.pressed is not None

    def moved(self) -> bool:
        """The mouse has gone further than a click with the button down: whatever it went
        down on comes up with it, if it can be picked up that way. Says whether something is
        in the hand now. A thing that stands on the map is not: it has to be held first."""
        if self.held is not None:
            return True
        pressed, self.pressed = self.pressed, None
        if pressed is None or pressed.kind == THING:
            return False
        return self._lift(pressed)

    def _lift(self, what: Held) -> bool:
        view, world = self.view, self.view.world
        if what.kind == SOMEBODY:
            error = world.placing.obstacle(world, what.held_id)
            result = world.apply_command(HoldResidentCommand(what.held_id)) if error is None else None
            if result is None or not result.ok:
                view._sound("refuse")
                view.hud.notify(error or result.message)
                return False
            # Whoever is carried is who is looked at, and the view stays where it is put.
            view.hud.select_resident(what.held_id)
            view._selection_seen, view.following = what.held_id, None
        elif what.kind == BUNDLE and what.held_id not in world.bundles:
            return False
        elif what.kind == THING:
            placed = world.interactables.get(what.held_id)
            if placed is None or view.pointer is None:
                return False
            tile = view.tile_under(view.pointer)
            self._grip = (tile[0] - placed.x, tile[1] - placed.y)
            view.hud.notify(LIFTED)
        self.held, self.pressed = what, None
        self.swing, self._lean, self._last = 0.5, 0.0, None
        view._sound("select")
        return True

    # ----- while it is in the hand -----

    def update(self, dt: float) -> None:
        view, world = self.view, self.view.world
        self._clock += dt
        if self.held is None:
            if self.pressed is not None and self.pressed.kind == THING and not view._dragging and view._press is not None:
                self.pressed_for += dt
                if self.pressed_for >= LIFT_SECONDS:
                    if self._lift(self.pressed):
                        # In the hand without having gone anywhere: letting go is no click.
                        view._dragging = True
            self.target = None
            return
        held = self.held
        if held.kind == SOMEBODY:
            if world.placing.obstacle(world, held.held_id) is not None:
                self.cancel()
                return
            if not world.affect.is_held(world, held.held_id):
                # They go on hanging there for as long as they are carried.
                world.apply_command(HoldResidentCommand(held.held_id))
        elif held.kind == BUNDLE and held.held_id not in world.bundles:
            self.cancel()
            return
        elif held.kind == THING and held.held_id not in world.interactables:
            self.cancel()
            return
        elif held.kind == ITEM and world.items.find_item(world, held.held_id) is None:
            self.cancel()
            return
        self._move_view(dt)
        self._swing(dt)
        self.target = self._target()

    def _move_view(self, dt: float) -> None:
        """Near an edge of the map, carrying something across it moves the view that way."""
        view = self.view
        pointer, area = view.pointer, view.viewport
        if pointer is None or self.held is None or self.held.kind == ITEM or not area.collidepoint(pointer):
            return
        across = (pointer[0] > area.right - EDGE) - (pointer[0] < area.left + EDGE)
        down = (pointer[1] > area.bottom - EDGE) - (pointer[1] < area.top + EDGE)
        if across or down:
            view.scroll(across * EDGE_SPEED * dt, down * EDGE_SPEED * dt)

    def _swing(self, dt: float) -> None:
        """Have the legs of whoever hangs from the hand trail behind as it goes, and kick a
        little when it is still."""
        point = self.map_point()
        if point is None:
            return
        speed = 0.0
        if self._last is not None and dt > 0:
            speed = (point[0] - self._last[0]) / dt
        self._last = point
        aim = max(-1.0, min(1.0, speed / SWING_SPEED))
        self._lean += (aim - self._lean) * min(1.0, SWING_RATE * dt)
        kick = KICK * math.sin(self._clock * KICK_RATE * math.tau) * (1.0 - abs(self._lean))
        self.swing = max(0.0, min(1.0, 0.5 - 0.5 * (self._lean + kick)))

    def map_point(self) -> tuple[float, float] | None:
        """Where on the map the pointer is, in map pixels. None while it is off it."""
        view = self.view
        if view.pointer is None or not view.viewport.collidepoint(view.pointer):
            return None
        return view._map_point(view.pointer)

    def standing(self, grown: float = 1.0) -> tuple[float, float] | None:
        """Where whoever hangs from the hand counts as standing, in tiles, as a body is placed
        by the tile it is on: under the pointer by as much as they hang."""
        point = self.map_point()
        if point is None:
            return None
        left = (TILE_SIZE - FRAME_SIZE[0]) // 2 + FRAME_ORIGIN[0]
        top = TILE_SIZE - FEET_ABOVE_EDGE - FRAME_SIZE[1] + FRAME_ORIGIN[1]
        return ((point[0] - left) / TILE_SIZE, (point[1] + HELD_BELOW * grown - top) / TILE_SIZE)

    # ----- what is under it -----

    def _target(self) -> Target | None:
        view, held = self.view, self.held
        pointer = view.pointer
        if held is None or pointer is None:
            return None
        if held.kind == ITEM:
            return self._item_target(pointer)
        if not view.viewport.collidepoint(pointer) or view.hud.covers(pointer):
            return Target(False, BACK_ON_MAP)
        if held.kind == BUNDLE:
            return self._bundle_target(pointer)
        if held.kind == THING:
            return self._thing_target(pointer)
        return self._resident_target(pointer)

    def _under(self, boxes: dict[str, pygame.Rect], pointer: tuple[int, int], but: str | None = None) -> str | None:
        """Whatever was drawn last, and so is in front, of what a canvas position is on."""
        found = [each for each, box in boxes.items() if each != but and box.collidepoint(pointer)]
        return found[-1] if found else None

    def feet(self, pointer: tuple[int, int]) -> tuple[int, int]:
        """Where on the canvas the feet of whoever hangs from the pointer are."""
        return (pointer[0], pointer[1] + round(HELD_BELOW * self.view.tile_px / TILE_SIZE))

    def _on(self, point: tuple[int, int], resident_id: str) -> tuple[str, str, pygame.Rect] | None:
        """Who or what a canvas position is on that somebody could be put down on."""
        view, world = self.view, self.view.world
        other = self._under(view.hitboxes, point, but=resident_id)
        if other is not None and other in world.residents:
            return (RESIDENT, other, view.hitboxes[other])
        child = self._under(view.bundle_boxes, point)
        if child is not None and world.bundles[child].carried_by is None:
            return (CHILD, child, view.bundle_boxes[child])
        thing = self._under(view.object_boxes, point)
        if thing is not None:
            return (OBJECT, thing, view.object_boxes[thing])
        tile = view.tile_under(point)
        room_id = next((each for each in view._closed if tile in view.roof_tiles[each]), None)
        if room_id is not None:
            # What is under a roof that is on cannot be pointed at: it is the building.
            return (ROOM, room_id, view._canvas_rect(building_area(world.rooms[room_id])))
        site = self._under(view.site_boxes, point)
        return (SITE, site, view.site_boxes[site]) if site is not None else None

    def _resident_target(self, pointer: tuple[int, int]) -> Target:
        """What whoever hangs from the pointer would be put down on: what the hand is over,
        or else what their feet are over, or else the ground under their feet."""
        view, world = self.view, self.view.world
        resident_id = self.held.held_id
        feet = self.feet(pointer)
        on = self._on(pointer, resident_id) or self._on(feet, resident_id)
        if on is not None:
            tile = view.tile_under(pointer)
            seen = world.foresee_put_down(resident_id, tile, on[0], on[1])
            return Target(seen.ok, seen.text, on[0], on[1], tile, on[2])
        # The tile whose foot is nearest to their feet: they come down where they hang.
        tile = view.tile_under((feet[0], feet[1] - view.tile_px // 2))
        seen = world.foresee_put_down(resident_id, tile)
        return Target(seen.ok, seen.text, GROUND, None, tile, None, seen.tile)

    def _bundle_target(self, pointer: tuple[int, int]) -> Target:
        view, world = self.view, self.view.world
        bundle = world.bundles[self.held.held_id]
        other = self._under(view.hitboxes, pointer)
        resident = world.residents.get(other or "")
        if resident is None:
            return Target(False, CHILD_NEEDS_ARMS)
        error = world.children.cannot_mind(world, resident)
        text = error or f"{resident.name} cogerá en brazos a {bundle.name}"
        return Target(error is None, text, RESIDENT, resident.resident_id, None, view.hitboxes[other])

    def _thing_target(self, pointer: tuple[int, int]) -> Target:
        view, world = self.view, self.view.world
        placed = world.interactables[self.held.held_id]
        definition = world.definition_of(placed)
        under = view.tile_under(pointer)
        tile = (under[0] - self._grip[0], under[1] - self._grip[1])
        area = pygame.Rect(tile[0] * TILE_SIZE, tile[1] * TILE_SIZE, definition.width * TILE_SIZE, definition.height * TILE_SIZE)
        box = view._canvas_rect(area)
        if tile == (placed.x, placed.y):
            return Target(False, BACK, OBJECT, placed.object_id, tile, box)
        error = world.urbanism.move_object_error(world, placed.object_id, tile)
        text = error or THING_MOVES
        return Target(error is None, text, OBJECT, placed.object_id, tile, box)

    def _item_target(self, pointer: tuple[int, int]) -> Target:
        view, world = self.view, self.view.world
        item_id = self.held.held_id
        to_kind, to_id, box = None, None, None
        listed = next((each for each in view.hud.listed() if each[0].collidepoint(pointer)), None)
        if listed is not None:
            to_kind, to_id, box = TO_RESIDENT, listed[1], listed[0]
        elif view.inside is None and view.viewport.collidepoint(pointer) and not view.hud.covers(pointer):
            other = self._under(view.hitboxes, pointer)
            kept = self._under(view.container_hitboxes, pointer)
            if other is not None and other in world.residents:
                to_kind, to_id, box = TO_RESIDENT, other, view.hitboxes[other]
            elif kept is not None and kept in world.containers:
                to_kind, to_id, box = TO_CONTAINER, kept, view.container_hitboxes[kept]
        if to_kind is None or to_id is None:
            return Target(False, ITEM_NEEDS_PLACE)
        error = world.handing.error(world, item_id, to_kind, to_id)
        return Target(error is None, world.foresee_hand_item(item_id, to_kind, to_id), to_kind, to_id, None, box)

    # ----- letting go -----

    def cancel(self) -> None:
        """Let go of whatever is in the hand with nothing done: it is back where it was."""
        held, self.held, self.pressed, self.target = self.held, None, None, None
        if held is not None and held.kind == SOMEBODY:
            self.view.world.apply_command(ReleaseResidentCommand(held.held_id))

    def let_go(self) -> None:
        """The button has come up: whatever is in the hand is put down on what is under it."""
        view, world = self.view, self.view.world
        held, target = self.held, self._target()
        if held is None:
            return
        if target is None or not target.ok:
            self.cancel()
            view._sound("refuse")
            view.hud.notify(target.text if target is not None and target.text else BACK)
            return
        self.held, self.pressed, self.target = None, None, None
        if held.kind == SOMEBODY:
            result = world.apply_command(PutDownCommand(held.held_id, target.tile, target.on_kind, target.on_id))
            if not result.ok:
                world.apply_command(ReleaseResidentCommand(held.held_id))
            elif result.does == WITH and result.detail is not None:
                view.ask_with(held.held_id, result.detail)
            elif result.does == CHOOSE and result.detail is not None:
                view.ask_which(held.held_id, result.detail)
        elif held.kind == BUNDLE:
            result = world.apply_command(HandChildCommand(held.held_id, target.on_id or ""))
        elif held.kind == THING:
            result = world.apply_command(MoveObjectCommand(held.held_id, target.tile))
        else:
            # With Shift held, only one of them is moved.
            one = bool(pygame.key.get_mods() & pygame.KMOD_SHIFT)
            result = world.apply_command(HandItemCommand(held.held_id, target.on_id or "", target.on_kind, 1 if one else None))
        view.hud.notify(result.message)
        view._sound("order" if result.ok else "refuse")

    # ----- showing it -----

    def draw_on_map(self) -> None:
        """Light up what is under the pointer, within the part of the canvas that shows the map."""
        view, target = self.view, self.target
        if self.held is not None and target is not None and target.lands is not None:
            self._draw_landing(target.lands, target.ok)
        if self.held is None or target is None or target.box is None or not view.viewport.colliderect(target.box):
            return
        # A line round it and no more: what is in the hand is not to be painted over.
        color = PALETTE["lamp" if target.ok else "ember"]
        box = target.box.inflate(2, 2)
        pygame.draw.rect(view.canvas, PALETTE["ink"], box.inflate(2, 2), 1)
        pygame.draw.rect(view.canvas, color, box, 1)
        if self.held.kind == THING:
            self._draw_thing(target)

    def _draw_landing(self, tile: Tile, ok: bool) -> None:
        """Where on the ground whoever hangs from the pointer would come down: their shadow, ringed."""
        view = self.view
        box = view.tile_box(tile)
        ring = pygame.Rect(0, 0, max(6, box.width * 3 // 4), max(4, box.height * 3 // 8))
        ring.midbottom = (box.centerx, box.bottom - max(1, box.height // 10))
        shadow = pygame.Surface(ring.size, pygame.SRCALPHA)
        pygame.draw.ellipse(shadow, (*PALETTE["ink"], 96), shadow.get_rect())
        view.canvas.blit(shadow, ring)
        pygame.draw.ellipse(view.canvas, PALETTE["lamp" if ok else "ember"], ring, 1)

    def _draw_thing(self, target: Target) -> None:
        """A thing in the hand is seen where it would stand, faintly."""
        view, world = self.view, self.view.world
        placed = world.interactables.get(self.held.held_id)
        if placed is None or target.box is None:
            return
        definition = world.definition_of(placed)
        sheet = view.object_sprites.sheet(definition)
        width = min(definition.width * TILE_SIZE, sheet.get_width())
        image = sheet.subsurface((0, 0, width, sheet.get_height()))
        zoom = view.tile_px / TILE_SIZE
        ghost = pygame.transform.scale(image, (max(1, round(image.get_width() * zoom)), max(1, round(image.get_height() * zoom))))
        ghost.set_alpha(170)
        view.canvas.blit(ghost, (target.box.left, target.box.bottom - ghost.get_height()))

    def draw_over(self) -> None:
        """What goes over everything else: a thing dragged out of a panel, and what letting go would do."""
        view, target = self.view, self.target
        pointer = view.pointer
        if self.held is None or pointer is None:
            return
        if self.held.kind == ITEM:
            item = view.world.items.find_item(view.world, self.held.held_id)
            if item is not None:
                if target is not None and target.box is not None and not view.viewport.colliderect(target.box):
                    pygame.draw.rect(view.canvas, PALETTE["lamp" if target.ok else "ember"], target.box, 1)
                # Its small picture, on the canvas itself: it goes over the map and over the panels alike.
                icon = view.icons.icon(item.definition_id)
                view.canvas.blit(icon, icon.get_rect(center=pointer))
        if target is None or not target.text:
            return
        font, canvas = view.font, view.canvas
        text = font.truncate(target.text, canvas.get_width() - 8)
        width = font.width(text)
        x = pointer[0] + HINT_OFFSET[0]
        if x + width > canvas.get_width() - 4:
            # No room for it to the right of the pointer: it goes to its left.
            x = pointer[0] - HINT_OFFSET[0] - width
        x = max(4, x)
        y = max(4, min(canvas.get_height() - 4 - LINE_HEIGHT, pointer[1] + HINT_OFFSET[1]))
        for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1), (1, 1), (-1, 1), (1, -1)):
            font.draw(canvas, text, (x + dx, y + dy), PALETTE["ink"])
        font.draw(canvas, text, (x, y), PALETTE["glow" if target.ok else "ember"])
