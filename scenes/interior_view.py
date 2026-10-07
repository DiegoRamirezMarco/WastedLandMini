"""A building seen from inside: its back wall face on and its floor from a little above, as a grid.

This is a first try of the look (P39). What is shown is what the building holds on the map,
spread over a floor twice as wide and twice as deep: nothing can be put down here yet, and
whoever is inside is where the map has them. The room of its own that a building is to have
inside, and furnishing it, come after (S40 and on).

It is a part of the global view and draws with what that has: the same bodies, dolls and
object art. Everything is laid out in pixels of the window, since that is what it is shown in.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass
from typing import TYPE_CHECKING

import pygame

from graphics.body_renderer import FRAME_ORIGIN, FRAME_SIZE
from graphics.doll import draw_doll
from graphics.font import LINE_HEIGHT
from graphics.object_pictures import DEPTH, ObjectPicture
from graphics.palette import PALETTE, Color
from graphics.screen_layers import TRANSPARENT
from graphics.shelf_display import displayed_goods
from graphics.ui_art import darker, lighter, mix
from scenes.body_stage import HEAD_BONE, LYING_HEAD_OFFSET, LYING_HEAD_ROWS, LYING_NECK
from settings import SCALE, TILE_SIZE
from simulation.residents.manner import WALK
from simulation.residents.resident import Resident
from skeleton.rig import Skeleton
from ui.button import Button
from world.interactable import Interactable
from world.room import Room

if TYPE_CHECKING:
    from scenes.global_view import GlobalView

LEAVE_INTENT = ("leave_interior",)
LEAVE_LABEL = "Salir"
TRIAL_NOTE = "Prueba de la vista: lo que hay dentro es lo que tiene en el mapa."
# How many cells of the inside go to a tile of the building as it stands on the map, each way.
GROWTH = 2
# What each part takes, in widths of a cell: how tall the back wall is; how wide the walls at
# the sides are; and how tall what is left of the front wall is, with the way out in it. How
# deep a cell looks is `DEPTH`, which the pictures of what stands in it are drawn to.
WALL = 2.3
SIDE = 0.3
FRONT = 0.28
# The share of the part of the screen it has that the room takes.
FILL = 0.94
DOOR_TERRAIN = "door"
ANIMATION_FPS = 5
BACKDROP: Color = (17, 20, 26)
BOARDS: Color = (150, 112, 84)
BEAM: Color = (74, 54, 44)
FLOORS: dict[str, Color] = {"floor_wood": (170, 128, 92), "floor_concrete": (136, 134, 128)}
PLAIN_FLOOR: Color = (150, 130, 104)
MAT: Color = (150, 58, 48)


@dataclass(frozen=True)
class InteriorLayout:
    """Where the parts of a room fall, in pixels of the stage it is drawn on."""

    columns: int
    rows: int
    # The width of a cell of the floor, and how deep it looks.
    cell: int
    depth: int
    wall: pygame.Rect
    floor: pygame.Rect
    side: int
    front: int
    # The first column the way out takes, and how many.
    door: tuple[int, int]

    @property
    def whole(self) -> pygame.Rect:
        """Everything of the room: walls, floor and what is left of the front."""
        return pygame.Rect(
            self.wall.x - self.side, self.wall.y, self.wall.width + self.side * 2, self.wall.height + self.floor.height + self.front
        )

    def spot(self, column: float, row: float) -> tuple[int, int]:
        """Where on the stage a place on the floor is, given in cells from its back left corner."""
        return (round(self.floor.x + column * self.cell), round(self.floor.y + row * self.depth))


def layout_for(room: Room, area: pygame.Rect, door: tuple[int, int] | None = None) -> InteriorLayout:
    """Lay the inside of a building out to fill an area, keeping its proportions."""
    columns, rows = room.width * GROWTH, room.height * GROWTH
    cell = max(4, int(min(area.width * FILL / (columns + SIDE * 2), area.height * FILL / (WALL + rows * DEPTH + FRONT))))
    depth, side, front = max(2, round(cell * DEPTH)), round(cell * SIDE), round(cell * FRONT)
    wall_height = round(cell * WALL)
    left = area.centerx - columns * cell // 2
    top = area.centery - (wall_height + rows * depth + front) // 2
    wall = pygame.Rect(left, top, columns * cell, wall_height)
    floor = pygame.Rect(left, wall.bottom, columns * cell, rows * depth)
    return InteriorLayout(columns, rows, cell, depth, wall, floor, side, front, door or ((columns - GROWTH) // 2, GROWTH))


def door_columns(world, room: Room) -> tuple[int, int] | None:
    """The columns of the inside that the door in the front wall takes. None if it has none there."""
    row = room.y + room.height
    tile_map = world.tile_map
    if not 0 <= row < tile_map.height:
        return None
    doors = [x for x in range(room.x, room.x + room.width) if tile_map.terrain_at((x, row)) == DOOR_TERRAIN]
    return ((doors[0] - room.x) * GROWTH, len(doors) * GROWTH) if doors else None


def _fade(size: tuple[int, int], color: Color, start: int, end: int, across: bool = False) -> pygame.Surface:
    """A veil of one colour that goes from one strength to another, down it or across it."""
    width, height = max(1, size[0]), max(1, size[1])
    length = width if across else height
    line = pygame.Surface((length, 1) if across else (1, length), pygame.SRCALPHA)
    for step in range(length):
        alpha = round(start + (end - start) * step / max(1, length - 1))
        line.set_at((step, 0) if across else (0, step), (*color, alpha))
    return pygame.transform.scale(line, (width, height))


def draw_shell(layout: InteriorLayout, floor_kind: str, seed: int = 0) -> pygame.Surface:
    """The empty room: back wall, side walls, floor with its grid, and the front with the way out.

    The picture is the size of `layout.whole`.
    """
    whole = layout.whole
    cell, depth, side = layout.cell, layout.depth, layout.side
    picture = pygame.Surface(whole.size, pygame.SRCALPHA)
    wall = layout.wall.move(-whole.x, -whole.y)
    floor = layout.floor.move(-whole.x, -whole.y)
    # Not the simulation's randomness: the same boards every time, and nothing rides on them.
    chance = random.Random(seed)

    # The back wall: boards standing side by side, a beam along the top and a skirting along the foot.
    picture.fill(BOARDS, wall)
    picture.blit(_fade(wall.size, (0, 0, 0), 70, 0), wall)
    board = max(6, cell // 2)
    for x in range(wall.left, wall.right, board):
        shade = chance.randint(-9, 9)
        tint = pygame.Surface((board, wall.height), pygame.SRCALPHA)
        tint.fill((255, 255, 255, shade) if shade > 0 else (0, 0, 0, -shade))
        picture.blit(tint, (x, wall.top), wall.clip(pygame.Rect(x, wall.top, board, wall.height)).move(-x, -wall.top))
        pygame.draw.line(picture, darker(BOARDS, 0.32), (x, wall.top), (x, wall.bottom), max(1, cell // 40))
    beam = max(4, round(cell * 0.2))
    picture.fill(BEAM, (wall.left, wall.top, wall.width, beam))
    picture.fill(lighter(BEAM, 0.14), (wall.left, wall.top + beam - max(1, beam // 5), wall.width, max(1, beam // 5)))
    skirting = max(4, round(cell * 0.16))
    picture.fill(darker(BOARDS, 0.38), (wall.left, wall.bottom - skirting, wall.width, skirting))
    picture.fill(lighter(BOARDS, 0.1), (wall.left, wall.bottom - skirting, wall.width, max(1, skirting // 5)))

    # The floor: boards running across, or a poured one, with a line round every cell.
    base = FLOORS.get(floor_kind, PLAIN_FLOOR)
    picture.fill(base, floor)
    if floor_kind == "floor_wood":
        plank = max(4, depth // 2)
        for index, y in enumerate(range(floor.top, floor.bottom, plank)):
            start = floor.left - (cell * 2 if index % 2 else cell)
            for x in range(start, floor.right, cell * 2):
                piece = pygame.Rect(x, y, cell * 2, plank).clip(floor)
                if piece.width > 0:
                    picture.fill(mix(base, (0, 0, 0) if chance.random() < 0.5 else (255, 240, 210), chance.random() * 0.08), piece)
                    pygame.draw.line(picture, darker(base, 0.13), piece.topleft, (piece.left, piece.bottom - 1), max(1, cell // 60))
            # The boards are only what the floor is made of: it is the grid over them that is to be read.
            pygame.draw.line(picture, darker(base, 0.12), (floor.left, y), (floor.right - 1, y), max(1, cell // 60))
    else:
        for _ in range(floor.width * floor.height // 220):
            x, y = chance.randrange(floor.left, floor.right), chance.randrange(floor.top, floor.bottom)
            picture.set_at((x, y), mix(base, (0, 0, 0) if chance.random() < 0.5 else (255, 255, 255), 0.16))
    grid = pygame.Surface(floor.size, pygame.SRCALPHA)
    for column in range(layout.columns):
        for row in range(layout.rows):
            if (column + row) % 2:
                grid.fill((0, 0, 0, 14), (column * cell, row * depth, cell, depth))
    line = max(2, cell // 28)
    for column in range(layout.columns + 1):
        pygame.draw.line(grid, (30, 20, 14, 135), (column * cell, 0), (column * cell, floor.height), line)
    for row in range(layout.rows + 1):
        pygame.draw.line(grid, (30, 20, 14, 135), (0, row * depth), (floor.width, row * depth), line)
    picture.blit(grid, floor)
    # The walls throw a little shade on the floor at their feet.
    picture.blit(_fade((floor.width, max(2, depth // 2)), (0, 0, 0), 90, 0), floor)
    reach = max(2, cell // 2)
    picture.blit(_fade((reach, floor.height), (0, 0, 0), 70, 0, across=True), floor)
    picture.blit(_fade((reach, floor.height), (0, 0, 0), 0, 70, across=True), (floor.right - reach, floor.top))

    # The walls at the sides, seen edge on, and what is left of the front one, with the way out in it.
    for left in (wall.left - side, wall.right):
        strip = pygame.Rect(left, wall.top, side, wall.height + floor.height)
        picture.fill(darker(BOARDS, 0.45), strip)
        # Darker towards the outside of the room.
        outer, inner = (70, 0) if left < wall.left else (0, 70)
        picture.blit(_fade(strip.size, (0, 0, 0), outer, inner, across=True), strip)
    front = pygame.Rect(wall.left - side, floor.bottom, wall.width + side * 2, layout.front)
    picture.fill(darker(BOARDS, 0.62), front)
    picture.fill(darker(BOARDS, 0.5), (front.left, front.top, front.width, max(1, layout.front // 5)))
    first, count = layout.door
    way_out = pygame.Rect(floor.left + first * cell, floor.bottom, count * cell, layout.front)
    picture.fill(darker(base, 0.34), way_out)
    mat = pygame.Rect(0, 0, round(count * cell * 0.7), round(depth * 0.56))
    mat.midbottom = (way_out.centerx, floor.bottom - max(2, depth // 7))
    pygame.draw.rect(picture, darker(MAT, 0.35), mat.inflate(4, 4), border_radius=max(2, depth // 8))
    pygame.draw.rect(picture, MAT, mat, border_radius=max(2, depth // 8))
    pygame.draw.rect(picture, lighter(MAT, 0.25), mat.inflate(-mat.width // 5, -mat.height // 3), max(1, cell // 30), border_radius=2)
    return picture


class InteriorView:
    """Draws the building the global view is inside of, in its part of the screen."""

    def __init__(self, view: "GlobalView") -> None:
        self.view = view
        corner = view.viewport.topleft
        self.leave_button = Button.at(view.font, corner[0] + 6, corner[1] + 6, LEAVE_LABEL, LEAVE_INTENT)
        self._shells: dict[tuple, pygame.Surface] = {}
        self._pictures: dict[tuple, pygame.Surface] = {}
        self._skeletons: dict[tuple, Skeleton] = {}

    def stage(self) -> pygame.Rect:
        """The part of the screen the room is laid out in, in pixels of the window, from its own corner."""
        viewport = self.view.viewport
        return pygame.Rect(0, 0, viewport.width * SCALE, viewport.height * SCALE)

    def layout(self, room: Room) -> InteriorLayout:
        return layout_for(room, self.stage(), door_columns(self.view.world, room))

    def place(self, room: Room, x: float, y: float) -> tuple[float, float]:
        """Where on the floor of the inside a place of the map falls, in cells."""
        return ((x - room.x) * GROWTH, (y - room.y) * GROWTH)

    def _to_canvas(self, point: tuple[float, float]) -> tuple[int, int]:
        viewport = self.view.viewport
        return (viewport.x + round(point[0] / SCALE), viewport.y + round(point[1] / SCALE))

    def render(self, room: Room) -> None:
        """Draw the inside of a building, whoever is in it, and the way back out."""
        view = self.view
        canvas, viewport, world = view.canvas, view.viewport, view.world
        layout = self.layout(room)
        draws: list[tuple[float, object]] = []
        for placed in world.interactables.values():
            if room.contains((placed.x, placed.y)):
                draws.extend(self._object(room, layout, placed))
        labels = []
        for resident in world.residents.values():
            if resident.away or not room.contains(resident.tile):
                continue
            depth, draw, label = self._resident(room, layout, resident)
            draws.append((depth, draw))
            labels.append(label)
        draws.sort(key=lambda entry: entry[0])
        floor_kind = world.tile_map.terrain_at((room.x, room.y))
        key = (room.room_id, layout.cell, layout.columns, layout.rows, floor_kind, layout.door)
        if key not in self._shells:
            self._shells[key] = draw_shell(layout, floor_kind, sum(map(ord, room.room_id)))
        shell = self._shells[key]

        def paint(target: pygame.Surface, corner: tuple[int, int]) -> None:
            area = pygame.Rect(corner, self.stage().size)
            before = target.get_clip()
            target.set_clip(area)
            target.fill(BACKDROP, area)
            target.blit(shell, (corner[0] + layout.whole.x, corner[1] + layout.whole.y))
            for _, draw in draws:
                draw(target, corner)
            target.set_clip(before)

        layers = view.layers
        if layers is not None and canvas.get_flags() & pygame.SRCALPHA:
            corner = layers.on_screen(viewport).topleft
            layers.under(lambda screen: paint(screen, corner))
            canvas.fill(TRANSPARENT, viewport)
        else:
            # With no window under the canvas, the same picture brought down to it.
            stage = pygame.Surface(self.stage().size)
            paint(stage, (0, 0))
            canvas.blit(pygame.transform.smoothscale(stage, viewport.size), viewport)
        canvas.set_clip(viewport)
        for label in labels:
            label()
        canvas.set_clip(None)
        self.leave_button.draw(canvas, view.font)
        left = self.leave_button.rect.right + 6
        view.font.draw(canvas, f"{room.name.capitalize()}, por dentro", (left, self.leave_button.rect.y + 1), PALETTE["paper"])
        view.font.draw(canvas, TRIAL_NOTE, (viewport.x + 6, viewport.bottom - LINE_HEIGHT - 3), PALETTE["dust"])

    # ----- what stands in it -----

    def _object(self, room: Room, layout: InteriorLayout, placed: Interactable):
        """Something that stands in the room: each part of it, by how far down the floor it is drawn at."""
        view = self.view
        definition = view.world.definition_of(placed)
        own = self._own(layout, definition)
        if own is not None:
            return self._own_object(room, layout, placed, own)
        # A kind the game has no picture of, such as a pack brings: its art as it is.
        sheet = view.object_sprites.sheet(definition)
        frame_width = definition.width * TILE_SIZE
        frames = view.object_sprites.frames(definition)
        frame = int(view.time * ANIMATION_FPS) % frames
        tiles_tall = sheet.get_height() / TILE_SIZE
        upright = tiles_tall > definition.height
        column, row = self.place(room, placed.x, placed.y)
        width = definition.width * layout.cell
        # What stands up is as tall as it is drawn. What lies flat is seen as the floor is: from a little above.
        height = round(tiles_tall * layout.cell) if upright else definition.height * layout.depth
        left, bottom = layout.spot(column, row + definition.height)
        drawing = view.object_art.shown(definition, (width, height)) if view.layers is not None else None
        key = (definition.kind, width, height, frame, drawing is not None)
        if key not in self._pictures:
            if drawing is not None:
                self._pictures[key] = drawing
            else:
                piece = sheet.subsurface((frame * frame_width, 0, min(frame_width, sheet.get_width()), sheet.get_height()))
                # The game's own art keeps its hard edges however large it is shown.
                self._pictures[key] = pygame.transform.scale(piece, (width, height))
        picture = self._pictures[key]

        def draw(target: pygame.Surface, corner: tuple[int, int]) -> None:
            if upright:
                shade = pygame.Surface((width, max(2, layout.depth // 2)), pygame.SRCALPHA)
                pygame.draw.ellipse(shade, (0, 0, 0, 80), shade.get_rect())
                target.blit(shade, (corner[0] + left, corner[1] + bottom - shade.get_height() * 2 // 3))
            target.blit(picture, (corner[0] + left, corner[1] + bottom - height))

        return [(bottom - 0.5, draw)]

    def _own(self, layout: InteriorLayout, definition) -> ObjectPicture | None:
        """The game's picture of a kind of thing, which is what is shown of it in here. None if it has none.

        A drawing of the player's is made for the map, from above, and is not shown in here.
        """
        view = self.view
        if not view.object_pictures.has(definition.kind, definition.width, definition.height):
            return None
        frame = int(view.time * ANIMATION_FPS) % view.object_pictures.frames(definition.kind)
        return view.object_pictures.picture(definition.kind, layout.cell, layout.depth, frame)

    def _own_object(self, room: Room, layout: InteriorLayout, placed: Interactable, picture: ObjectPicture):
        """Something the game has drawn: what of it is under whoever is in it, what is over them, and what it shows off."""
        view = self.view
        definition = view.world.definition_of(placed)
        column, row = self.place(room, placed.x, placed.y)
        left = layout.spot(column, row)[0]
        bottom = layout.spot(column, row + definition.height)[1]
        corner_of = (left, bottom - picture.under.get_height())
        goods = displayed_goods(view.world, placed) if definition.display_of is not None else []
        shown = [
            (view.icons.shown(item_id, picture.slot_size), (corner_of[0] + x, corner_of[1] + y))
            for item_id, (x, y) in zip(goods, picture.slots)
        ]

        def under(target: pygame.Surface, corner: tuple[int, int]) -> None:
            target.blit(picture.under, (corner[0] + corner_of[0], corner[1] + corner_of[1]))
            for item, spot in shown:
                target.blit(item, (corner[0] + spot[0], corner[1] + spot[1]))

        def over(target: pygame.Surface, corner: tuple[int, int]) -> None:
            target.blit(picture.over, (corner[0] + corner_of[0], corner[1] + corner_of[1]))

        # Whoever lies in it is drawn by its foot, between the two.
        return [(bottom - 0.5, under)] + ([(bottom + 0.5, over)] if picture.over is not None else [])

    def _resident(self, room: Room, layout: InteriorLayout, resident: Resident):
        """Somebody in the room: how far down the floor they are, how to draw them, and what goes over their head."""
        view = self.view
        x, y, facing, stride = view._walk_state(resident)
        column, row = self.place(room, x + 0.5, y + 0.5)
        foot = layout.spot(column, row)
        detail = layout.cell / TILE_SIZE
        lying_in = view._lying_in(resident)
        if lying_in is not None:
            return self._asleep(room, layout, resident, lying_in)
        doll = view._doll_of(resident.resident_id)
        clip, rate = view._way_of(resident, WALK) if stride is not None else view._clip_of(resident)
        turn = (stride if stride is not None else view.time) * rate
        renderer = view.bodies.renderer
        # Whoever carries something for their job holds their arms out for it, as on the map.
        overlay = self._carrying() if view._load_of(resident) is not None else None
        if doll is not None:
            facing = view._side_facing(resident.resident_id, view._lean(resident) or facing)
            plan = doll.plan if doll.plan is not None else view.bodies.plan
            key = (resident.resident_id, facing, id(plan))
            if key not in self._skeletons:
                self._skeletons[key] = Skeleton(plan, facing)
            skeleton = self._skeletons[key]
            pose = plan.pose(facing, clip, turn % 1.0, overlay)
            skeleton.set_pose(pose)
            held = self.in_hand(resident, facing, pose, turn, stride)
            reach = doll.standing(plan)
            box = pygame.Rect(
                foot[0] + math.floor(reach[0] * detail),
                foot[1] + math.floor(reach[1] * detail),
                math.ceil((reach[2] - reach[0]) * detail),
                math.ceil((reach[3] - reach[1]) * detail),
            )

            def draw(target: pygame.Surface, corner: tuple[int, int]) -> None:
                self._shadow(target, corner, foot, layout)
                draw_doll(target, doll, plan, skeleton, (corner[0] + foot[0], corner[1] + foot[1]), detail)
                self._show_held(target, held, (corner[0] + foot[0], corner[1] + foot[1]), detail)

        else:
            frames = renderer.frames(clip, facing)
            index = int(turn * frames) % frames
            picture, origin = renderer.frame(resident.resident_id, facing, clip, index, (), overlay)
            held = self.in_hand(resident, facing, view.bodies.plan.pose(facing, clip, index / frames, overlay), turn, stride)
            size = (round(picture.get_width() * detail), round(picture.get_height() * detail))
            key = (id(picture), size)
            if key not in self._pictures:
                self._pictures[key] = pygame.transform.scale(picture, size)
            shown = self._pictures[key]
            corner_of = (foot[0] - round(origin[0] * detail), foot[1] - round(origin[1] * detail))
            box = pygame.Rect(
                foot[0] - round(FRAME_ORIGIN[0] * detail),
                foot[1] - round(FRAME_ORIGIN[1] * detail),
                round(FRAME_SIZE[0] * detail),
                round(FRAME_SIZE[1] * detail),
            )

            def draw(target: pygame.Surface, corner: tuple[int, int]) -> None:
                self._shadow(target, corner, foot, layout)
                target.blit(shown, (corner[0] + corner_of[0], corner[1] + corner_of[1]))
                self._show_held(target, held, (corner[0] + foot[0], corner[1] + foot[1]), detail)

        hitbox = pygame.Rect(self._to_canvas(box.topleft), (max(4, box.width // SCALE), max(4, box.height // SCALE)))

        def label() -> None:
            view.hitboxes[resident.resident_id] = hitbox
            view._draw_overhead(resident, hitbox.midtop, with_name=True)

        return (foot[1], draw, label)

    @staticmethod
    def _carrying() -> str:
        from scenes.global_view import CARRY_CLIP

        return CARRY_CLIP

    def in_hand(self, resident: Resident, facing: str, pose: dict, turn: float, stride: float | None) -> list:
        """What somebody has in their hand, as the map would show it, from where their feet are:
        the meal they are at with the bites gone from it and the crumbs that fly, what they
        fight with, or what they carry for their job. Empty for empty hands."""
        view = self.view
        kept, view._held = view._held, []
        meal = view._meal_in_hand(resident)
        weapon = view._weapon_in_hand(resident) if stride is None else None
        load = view._load_of(resident)
        if meal is not None:
            view._hold(meal, facing, pose, 0.0, turn, view._bites_taken(resident))
        elif weapon is not None:
            view._hold(weapon, facing, pose, 0.0)
        elif load is not None:
            view._hold(load, facing, pose, 0.0)
        held, view._held = view._held, kept
        return held

    def _show_held(self, target: pygame.Surface, held: list, feet: tuple[int, int], detail: float) -> None:
        """Draw what somebody holds, with them standing at `feet`, as the map draws it."""
        if not held:
            return
        view = self.view
        kept, view._held = view._held, held
        view._draw_held(target, feet, detail)
        view._held = kept

    def _asleep(self, room: Room, layout: InteriorLayout, resident: Resident, lying_in: Interactable):
        """Somebody lying in something, as the map shows them: their own head on the pillow, the rest under the blanket."""
        view = self.view
        definition = view.world.definition_of(lying_in)
        column, row = self.place(room, lying_in.x, lying_in.y)
        left, top = layout.spot(column, row)
        # What they lie in is seen as the floor is, so a place on it is less far down than across.
        across, down = layout.cell / TILE_SIZE, layout.depth / TILE_SIZE
        bed = pygame.Rect(left, top, definition.width * layout.cell, definition.height * layout.depth)
        doll = view._doll_of(resident.resident_id)
        head = doll.placed(HEAD_BONE, False, across, math.pi) if doll is not None else None
        own = self._own(layout, definition)
        if head is not None:
            # A doll's head, upright, by where its neck is on the pillow.
            shown, joint = head
            neck = (left + LYING_NECK[0] * across, top + LYING_NECK[1] * down)
            if own is not None and own.neck is not None:
                # The game's own picture of a bed says where a head goes on it.
                neck = (left + own.neck[0], bed.bottom - own.under.get_height() + own.neck[1])
            place = (round(neck[0] - joint[0]), round(neck[1] - joint[1]))
        else:
            # The head of the game's own body, down to the eyes.
            whole = view.bodies.renderer.head(resident.resident_id)
            piece = whole.subsurface((0, 0, whole.get_width(), LYING_HEAD_ROWS))
            size = (round(piece.get_width() * across), round(piece.get_height() * across))
            key = ("head", resident.resident_id, size)
            if key not in self._pictures:
                self._pictures[key] = pygame.transform.scale(piece, size)
            shown = self._pictures[key]
            place = (round(left + LYING_HEAD_OFFSET[0] * across), round(top + LYING_HEAD_OFFSET[1] * down))
        # They are picked by the whole of what they lie in, headboard and all, and named over it.
        if own is not None:
            bed = pygame.Rect(bed.x, bed.bottom - own.under.get_height(), bed.width, own.under.get_height())
        hitbox = pygame.Rect(self._to_canvas(bed.topleft), (max(4, bed.width // SCALE), max(4, bed.height // SCALE)))

        def draw(target: pygame.Surface, corner: tuple[int, int]) -> None:
            target.blit(shown, (corner[0] + place[0], corner[1] + place[1]))

        def label() -> None:
            view.hitboxes[resident.resident_id] = hitbox
            view._draw_overhead(resident, hitbox.midtop, with_name=True, resting=True)

        # Over what they lie in, which is drawn by its foot.
        return (layout.spot(column, row + definition.height)[1], draw, label)

    def _shadow(self, target: pygame.Surface, corner: tuple[int, int], foot: tuple[int, int], layout: InteriorLayout) -> None:
        shade = pygame.Surface((round(layout.cell * 0.7), max(2, round(layout.depth * 0.36))), pygame.SRCALPHA)
        pygame.draw.ellipse(shade, (0, 0, 0, 85), shade.get_rect())
        target.blit(shade, shade.get_rect(center=(corner[0] + foot[0], corner[1] + foot[1])))
