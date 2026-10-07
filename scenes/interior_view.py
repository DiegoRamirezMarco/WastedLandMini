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
from graphics.palette import PALETTE, Color
from graphics.screen_layers import TRANSPARENT
from graphics.ui_art import darker, lighter, mix
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
# What each part takes, in widths of a cell: how deep a cell looks, seen from a little above;
# how tall the back wall is; how wide the walls at the sides are; and how tall what is left of
# the front wall is, with the way out in it.
DEPTH = 0.62
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
                draws.append(self._object(room, layout, placed))
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
        """Something that stands in the room: where its foot is, and how to draw it."""
        view = self.view
        definition = view.world.definition_of(placed)
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

        return (bottom - 0.5, draw)

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
        if doll is not None:
            facing = view._side_facing(resident.resident_id, view._lean(resident) or facing)
            plan = doll.plan if doll.plan is not None else view.bodies.plan
            key = (resident.resident_id, facing, id(plan))
            if key not in self._skeletons:
                self._skeletons[key] = Skeleton(plan, facing)
            skeleton = self._skeletons[key]
            skeleton.set_pose(plan.pose(facing, clip, turn % 1.0))
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

        else:
            frames = renderer.frames(clip, facing)
            picture, origin = renderer.frame(resident.resident_id, facing, clip, int(turn * frames) % frames)
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

        hitbox = pygame.Rect(self._to_canvas(box.topleft), (max(4, box.width // SCALE), max(4, box.height // SCALE)))

        def label() -> None:
            view.hitboxes[resident.resident_id] = hitbox
            view._draw_overhead(resident, hitbox.midtop, with_name=True)

        return (foot[1], draw, label)

    def _asleep(self, room: Room, layout: InteriorLayout, resident: Resident, lying_in: Interactable):
        """Somebody lying in something: their face on it, at its head."""
        view = self.view
        definition = view.world.definition_of(lying_in)
        column, row = self.place(room, lying_in.x, lying_in.y)
        centre = layout.spot(column + definition.width / 2, row + 0.55)
        face = view.faces.marker(resident.resident_id)
        side = max(8, round(layout.cell * 0.62))
        key = (id(face), side)
        if key not in self._pictures:
            self._pictures[key] = pygame.transform.scale(face, (side, side))
        shown = self._pictures[key]
        box = shown.get_rect(center=centre)
        hitbox = pygame.Rect(self._to_canvas(box.topleft), (max(4, side // SCALE), max(4, side // SCALE)))

        def draw(target: pygame.Surface, corner: tuple[int, int]) -> None:
            target.blit(shown, box.move(corner))

        def label() -> None:
            view.hitboxes[resident.resident_id] = hitbox
            view._draw_overhead(resident, hitbox.midtop, with_name=True, resting=True)

        # Over what they lie in, which is drawn by its foot.
        return (layout.spot(column, row + definition.height)[1], draw, label)

    def _shadow(self, target: pygame.Surface, corner: tuple[int, int], foot: tuple[int, int], layout: InteriorLayout) -> None:
        shade = pygame.Surface((round(layout.cell * 0.7), max(2, round(layout.depth * 0.36))), pygame.SRCALPHA)
        pygame.draw.ellipse(shade, (0, 0, 0, 85), shade.get_rect())
        target.blit(shade, shade.get_rect(center=(corner[0] + foot[0], corner[1] + foot[1])))
