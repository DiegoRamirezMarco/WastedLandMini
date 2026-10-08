"""A building seen from inside: its back wall face on and its floor from a little above, as a grid.

What is shown is what the building holds on the map, spread over a floor with more cells than
the building has tiles, and whoever is inside is where the map has them (P39). On top of that
it is where a building is dressed (P40): the ornaments put in it, which go by its own cells
and not by the map, the floor and the walls chosen for it, and the board that says whose it
is. The room of its own that a building is to have inside comes after (S40).

It is a part of the global view and draws with what that has: the same bodies, dolls and
object art. Everything is laid out in pixels of the window, since that is what it is shown in.
"""

from __future__ import annotations

import math
import random
from collections.abc import Hashable
from dataclasses import dataclass
from typing import TYPE_CHECKING

import pygame

from graphics.body_renderer import FRAME_ORIGIN, FRAME_SIZE
from graphics.doll import DOLL_FACINGS, draw_doll
from graphics.font import LINE_HEIGHT
from graphics.object_pictures import DEPTH, ObjectPicture
from graphics.ornament_pictures import OrnamentPictures
from graphics.palette import PALETTE, Color
from graphics.screen_layers import TRANSPARENT
from graphics.shelf_display import displayed_goods
from graphics.ui_art import band_hue, darker, lighter, mix
from scenes.body_stage import (
    BUNDLE_BEHIND,
    BUNDLE_RAISED,
    BUNDLE_UP,
    BUNDLE_WIDTH,
    HEAD_BONE,
    HEAD_OF_HEIGHT,
    LYING_HEAD_OFFSET,
    LYING_HEAD_ROWS,
    LYING_NECK,
    ground_spot,
    grown_share,
)
from settings import SCALE, TILE_SIZE
from simulation.family.children import CARRIED as BUNDLE_CARRIED
from simulation.family.children import GROUND as BUNDLE_ON_GROUND
from simulation.family.children import Bundle
from simulation.housing.decor import CELLS, FLOOR
from simulation.housing.decor import WALL as ON_WALL
from simulation.residents.manner import WALK
from simulation.residents.resident import Resident
from simulation.work.construction import OBJECT_SITE
from skeleton.rig import Skeleton
from ui.button import Button
from ui.decor_board import AS_BUILT_ID, FURNITURE, ORNAMENTS, WALLS
from ui.decor_board import PICTURE as DECOR_PICTURE
from ui.decor_board import DecorEntry, decor_board_height, decor_buttons, decor_click, draw_decor_board
from ui.house_board import PANEL_WIDTH as HOUSE_WIDTH
from ui.house_board import draw_house_board, house_board_height, house_buttons
from world.interactable import Interactable
from world.map import Tile
from world.room import Room

if TYPE_CHECKING:
    from scenes.global_view import GlobalView

LEAVE_INTENT = ("leave_interior",)
LEAVE_LABEL = "Salir"
# Opens and shuts the board on the building: whose it is and what it is like.
HOUSE_INTENT = ("house_board",)
HOUSE_LABEL = "Casa"
MARGIN = 6
# Opens and shuts the mode in which the building is dressed.
DECOR_INTENT = ("decorate",)
DECOR_LABEL = "Decorar"
# The line round what is in hand, by whether it can go where it is held, and round what is being put up.
CAN_GO: Color = (126, 190, 110)
CANNOT_GO: Color = (214, 84, 74)
SITE_LINE: Color = (214, 170, 84)
DECOR_NOTE = "Clic: poner o quitar · Botón derecho: soltar lo que llevas"
# How many cells of the inside go to a tile of the building as it stands on the map, each way.
GROWTH = CELLS
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
FLOORS: dict[str, Color] = {
    "floor_wood": (170, 128, 92),
    "floor_concrete": (136, 134, 128),
    "floor_tiles": (190, 176, 152),
    "floor_earth": (132, 104, 78),
}
# What the walls can be made of: boards, as every building is put up, or what the player has said.
PLAIN_WALL = "boards"
WALLS_OF: dict[str, Color] = {
    PLAIN_WALL: BOARDS,
    "plaster": (206, 194, 172),
    "brick": (160, 94, 74),
    "sheet": (126, 136, 142),
}
PLAIN_FLOOR: Color = (150, 130, 104)
PLAIN_FLOOR_KIND = "floor_wood"
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


def surface_swatch(kind: str, on_wall: bool, size: int) -> pygame.Surface:
    """A square of a floor or of a wall, as a room made of it shows it: for a catalogue."""
    layout = layout_for(Room("swatch", "", width=1, height=2, roofed=True), pygame.Rect(0, 0, size * 4, size * 5))
    shell = draw_shell(layout, PLAIN_FLOOR_KIND if on_wall else kind, 5, kind if on_wall else PLAIN_WALL)
    part = (layout.wall if on_wall else layout.floor).move(-layout.whole.x, -layout.whole.y)
    side = min(part.width, part.height)
    piece = shell.subsurface(pygame.Rect(part.centerx - side // 2, part.centery - side // 2, side, side))
    return pygame.transform.smoothscale(piece, (size, size))


def draw_shell(layout: InteriorLayout, floor_kind: str, seed: int = 0, wall_kind: str = PLAIN_WALL) -> pygame.Surface:
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

    # The back wall: what it is made of, a beam along the top and a skirting along the foot.
    made_of = WALLS_OF.get(wall_kind, BOARDS)
    picture.fill(made_of, wall)
    picture.blit(_fade(wall.size, (0, 0, 0), 70, 0), wall)
    thin = max(1, cell // 40)
    if wall_kind == "brick":
        course = max(5, cell // 5)
        for index, y in enumerate(range(wall.top, wall.bottom, course)):
            pygame.draw.line(picture, darker(made_of, 0.32), (wall.left, y), (wall.right - 1, y), thin)
            for x in range(wall.left + (course if index % 2 else 0), wall.right, course * 2):
                pygame.draw.line(picture, darker(made_of, 0.32), (x, y), (x, min(wall.bottom, y + course)), thin)
    elif wall_kind == "plaster":
        # Smooth, with a damp patch here and there.
        picture.set_clip(wall)
        for _ in range(max(3, wall.width // max(1, cell))):
            patch = pygame.Surface((chance.randint(cell // 3, cell), chance.randint(cell // 6, cell // 3)), pygame.SRCALPHA)
            pygame.draw.ellipse(patch, (60, 40, 20, 16), patch.get_rect())
            picture.blit(patch, (chance.randrange(wall.left, wall.right), chance.randrange(wall.top, wall.bottom)))
        picture.set_clip(None)
    elif wall_kind == "sheet":
        rib = max(4, cell // 7)
        for index, x in enumerate(range(wall.left, wall.right, rib)):
            strip = pygame.Rect(x, wall.top, rib, wall.height).clip(wall)
            tint = pygame.Surface(strip.size, pygame.SRCALPHA)
            tint.fill((255, 255, 255, 26) if index % 2 else (0, 0, 0, 30))
            picture.blit(tint, strip)
    else:
        board = max(6, cell // 2)
        for x in range(wall.left, wall.right, board):
            shade = chance.randint(-9, 9)
            tint = pygame.Surface((board, wall.height), pygame.SRCALPHA)
            tint.fill((255, 255, 255, shade) if shade > 0 else (0, 0, 0, -shade))
            picture.blit(tint, (x, wall.top), wall.clip(pygame.Rect(x, wall.top, board, wall.height)).move(-x, -wall.top))
            pygame.draw.line(picture, darker(made_of, 0.32), (x, wall.top), (x, wall.bottom), thin)
    beam = max(4, round(cell * 0.2))
    picture.fill(BEAM, (wall.left, wall.top, wall.width, beam))
    picture.fill(lighter(BEAM, 0.14), (wall.left, wall.top + beam - max(1, beam // 5), wall.width, max(1, beam // 5)))
    skirting = max(4, round(cell * 0.16))
    picture.fill(darker(made_of, 0.38), (wall.left, wall.bottom - skirting, wall.width, skirting))
    picture.fill(lighter(made_of, 0.1), (wall.left, wall.bottom - skirting, wall.width, max(1, skirting // 5)))

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
    elif floor_kind == "floor_tiles":
        # Four tiles to a cell, one in two a little darker, with the joints between them.
        wide, deep = max(2, cell // 2), max(2, depth // 2)
        for row, y in enumerate(range(floor.top, floor.bottom, deep)):
            for column, x in enumerate(range(floor.left, floor.right, wide)):
                tile = pygame.Rect(x, y, wide, deep).clip(floor)
                picture.fill(darker(base, 0.1) if (row + column) % 2 else lighter(base, 0.06), tile)
                pygame.draw.rect(picture, darker(base, 0.24), tile, 1)
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
        picture.fill(darker(made_of, 0.45), strip)
        # Darker towards the outside of the room.
        outer, inner = (70, 0) if left < wall.left else (0, 70)
        picture.blit(_fade(strip.size, (0, 0, 0), outer, inner, across=True), strip)
    front = pygame.Rect(wall.left - side, floor.bottom, wall.width + side * 2, layout.front)
    picture.fill(darker(made_of, 0.62), front)
    picture.fill(darker(made_of, 0.5), (front.left, front.top, front.width, max(1, layout.front // 5)))
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
        self.leave_button = Button.at(view.font, corner[0] + MARGIN, corner[1] + MARGIN, LEAVE_LABEL, LEAVE_INTENT)
        self.house_button = Button.at(view.font, self.leave_button.rect.right + 3, corner[1] + MARGIN, HOUSE_LABEL, HOUSE_INTENT)
        # Whether the board on the building is open, and the name being written for it while one is.
        self.board_open = True
        self.naming: str | None = None
        self.decor_button = Button.at(view.font, self.house_button.rect.right + 3, corner[1] + MARGIN, DECOR_LABEL, DECOR_INTENT)
        # Whether the building is being dressed, the tab of the board on show, what of it is in
        # hand as its tab and its ID, and whether ornaments are being taken away instead.
        self.decorating = False
        self.decor_tab = ORNAMENTS
        self.decor_held: tuple[str, str] | None = None
        self.decor_removing = False
        self.ornaments = OrnamentPictures()
        self._shells: dict[tuple, pygame.Surface] = {}
        self._pictures: dict[tuple, pygame.Surface] = {}
        self._skeletons: dict[tuple, Skeleton] = {}

    def stage(self) -> pygame.Rect:
        """The part of the screen the room is laid out in, in pixels of the window, from its own corner."""
        viewport = self.view.viewport
        return pygame.Rect(0, 0, viewport.width * SCALE, viewport.height * SCALE)

    def board_rect(self) -> pygame.Rect | None:
        """Where the board on the building is, on the canvas, while it is open: down the right of the room."""
        if not self.board_open and not self.decorating:
            return None
        viewport = self.view.viewport
        height = decor_board_height() if self.decorating else house_board_height(self.view.world, self.naming is not None)
        return pygame.Rect(
            viewport.right - MARGIN - HOUSE_WIDTH, viewport.y + MARGIN, HOUSE_WIDTH, min(height, viewport.height - MARGIN * 2)
        )

    def buttons(self, room: Room) -> list[Button]:
        """Everything that can be pressed in here: the way out, the board, and what is on it."""
        board = self.board_rect()
        if board is None:
            on_board = []
        elif self.decorating:
            on_board = decor_buttons(self.view.font, board)
        else:
            on_board = house_buttons(self.view.font, board, self.view.world, room.room_id, self.naming is not None)
        return [self.leave_button, self.house_button, self.decor_button, *on_board]

    def click(self, room: Room, position: tuple[int, int]) -> Hashable | None:
        """What a press at a place on the canvas asks for, if it is on anything of this view's."""
        board = self.board_rect()
        if self.decorating and board is not None and board.collidepoint(position):
            return decor_click(self.view.font, board, self.view.world, self.decor_tab, position)
        return next((button.intent for button in self.buttons(room) if button.contains(position)), None)

    def covers(self, position: tuple[int, int]) -> bool:
        """Whether a place on the canvas is under the board, and so not in the room."""
        board = self.board_rect()
        return board is not None and board.collidepoint(position)

    def layout(self, room: Room) -> InteriorLayout:
        area = self.stage()
        if self.board_open or self.decorating:
            # The room is laid out in what the board leaves of the screen.
            area.width -= (HOUSE_WIDTH + MARGIN) * SCALE
        return layout_for(room, area, door_columns(self.view.world, room))

    # ----- dressing it -----

    def spot_under(self, room: Room, position: tuple[int, int] | None) -> tuple[str, tuple[int, int]] | None:
        """What of the room a place on the canvas is over: a cell of its floor, or a stretch of its back wall."""
        viewport = self.view.viewport
        if position is None or not viewport.collidepoint(position) or self.covers(position):
            return None
        layout = self.layout(room)
        x, y = (position[0] - viewport.x) * SCALE, (position[1] - viewport.y) * SCALE
        if layout.floor.collidepoint(x, y):
            return (FLOOR, ((x - layout.floor.x) // layout.cell, (y - layout.floor.y) // layout.depth))
        if layout.wall.collidepoint(x, y):
            return (ON_WALL, ((x - layout.wall.x) // layout.cell, 0))
        return None

    def held_place(self, room: Room, position: tuple[int, int] | None) -> tuple[int, int] | None:
        """Where the ornament in hand would go if it were put down at a place on the canvas: the
        cell its corner takes, with the pointer at its middle and all of it kept inside the room."""
        world = self.view.world
        held = self.decor_held
        definition = world.registries.decor.ornaments.get(held[1]) if held is not None and held[0] == ORNAMENTS else None
        spot = self.spot_under(room, position)
        if definition is None or spot is None or spot[0] != definition.on:
            return None
        columns, rows = world.decor.size(room)
        x = min(max(0, spot[1][0] - definition.width // 2), max(0, columns - definition.width))
        if definition.on == ON_WALL:
            return (x, 0)
        return (x, min(max(0, spot[1][1] - definition.height // 2), max(0, rows - definition.height)))

    def held_tile(self, room: Room, position: tuple[int, int] | None) -> Tile | None:
        """The tile of the map the piece of furniture in hand would be put up on."""
        spot = self.spot_under(room, position)
        if self.decor_held is None or self.decor_held[0] != FURNITURE or spot is None or spot[0] != FLOOR:
            return None
        return (room.x + spot[1][0] // GROWTH, room.y + spot[1][1] // GROWTH)

    def _ornament(self, layout: InteriorLayout, kind: str, definition, x: int, y: int, ghost: bool | None = None):
        """An ornament where it is, or as it would be if it were put there: `ghost` says whether it could."""
        cell = layout.cell
        if definition.on == ON_WALL:
            picture, top = self.ornaments.on_wall(kind, definition.width, cell)
            place = (layout.wall.x + x * cell, layout.wall.y + top)
            box = pygame.Rect(place, picture.get_size())
            depth = float(layout.wall.y)
        else:
            drawn = self.ornaments.on_floor(kind, (definition.width, definition.height), cell, layout.depth)
            picture = drawn.under
            left = layout.spot(x, y)[0]
            bottom = layout.spot(x, y + definition.height)[1]
            place = (left, bottom - picture.get_height())
            box = pygame.Rect(layout.spot(x, y), (definition.width * cell, definition.height * layout.depth))
            # What lies flat is under everything that stands on the floor.
            depth = layout.floor.y - 0.25 if definition.flat else bottom - 0.5
        if ghost is not None:
            picture = self._faint(picture)

        def draw(target: pygame.Surface, corner: tuple[int, int]) -> None:
            target.blit(picture, (corner[0] + place[0], corner[1] + place[1]))
            if ghost is not None:
                pygame.draw.rect(target, CAN_GO if ghost else CANNOT_GO, box.move(corner), max(2, cell // 22), border_radius=4)

        return (depth if ghost is None else float("inf"), draw)

    def _faint(self, picture: pygame.Surface) -> pygame.Surface:
        """A picture seen through, for what is not there yet."""
        key = ("faint", id(picture))
        if key not in self._pictures:
            faint = picture.copy()
            faint.fill((255, 255, 255, 150), special_flags=pygame.BLEND_RGBA_MULT)
            self._pictures[key] = faint
        return self._pictures[key]

    def _site(self, room: Room, layout: InteriorLayout, site):
        """Something being put up in the room: seen through where it will stand, with how far along it is."""
        world = self.view.world
        definition = world.registries.interactables.get(site.what) if site.kind == OBJECT_SITE else None
        column, row = self.place(room, site.x, site.y)
        wide, deep = (definition.width, definition.height) if definition is not None else (1, 1)
        box = pygame.Rect(layout.spot(column, row), (wide * layout.cell, deep * layout.depth))
        done = world.construction.fraction_done(world, site)
        own = self._own(layout, definition) if definition is not None else None
        faint = self._faint(own.under) if own is not None else None

        def draw(target: pygame.Surface, corner: tuple[int, int]) -> None:
            area = box.move(corner)
            if faint is not None:
                target.blit(faint, (area.x, area.bottom - faint.get_height()))
            pygame.draw.rect(target, SITE_LINE, area.inflate(-4, -4), max(2, layout.cell // 24), border_radius=4)
            bar = pygame.Rect(area.x + 6, area.bottom - 12, area.width - 12, 6)
            pygame.draw.rect(target, (30, 22, 20), bar, border_radius=3)
            pygame.draw.rect(target, CAN_GO, (bar.x, bar.y, round(bar.width * done), bar.height), border_radius=3)

        return (box.bottom - 0.6, draw)

    def _in_hand(self, room: Room, layout: InteriorLayout):
        """What is in hand, where the pointer has it over the room. None with nothing in hand, or off the room."""
        view, world = self.view, self.view.world
        if not self.decorating or self.decor_held is None:
            return None
        tab, entry_id = self.decor_held
        if tab == ORNAMENTS:
            place = self.held_place(room, view.pointer)
            definition = world.registries.decor.ornaments.get(entry_id)
            if place is None or definition is None:
                return None
            fits = world.decor.error(world, room.room_id, entry_id, *place) is None
            return self._ornament(layout, entry_id, definition, place[0], place[1], ghost=fits)
        tile = self.held_tile(room, view.pointer)
        if tile is None:
            return None
        definition = world.registries.interactables.get(entry_id)
        fits = world.construction.site_error(world, OBJECT_SITE, entry_id, tile) is None
        column, row = self.place(room, tile[0], tile[1])
        box = pygame.Rect(layout.spot(column, row), (definition.width * layout.cell, definition.height * layout.depth))
        own = self._own(layout, definition)
        faint = self._faint(own.under) if own is not None else None

        def draw(target: pygame.Surface, corner: tuple[int, int]) -> None:
            area = box.move(corner)
            if faint is not None:
                target.blit(faint, (area.x, area.bottom - faint.get_height()))
            pygame.draw.rect(target, CAN_GO if fits else CANNOT_GO, area, max(2, layout.cell // 22), border_radius=4)

        return (float("inf"), draw)

    def _to_remove(self, room: Room, layout: InteriorLayout):
        """A line round the ornament under the pointer, while they are being taken away."""
        world = self.view.world
        spot = self.spot_under(room, self.view.pointer)
        ornament = world.decor.at(world, room.room_id, *spot) if spot is not None and self.decor_removing else None
        if ornament is None:
            return None
        definition = world.registries.decor.ornaments[ornament.kind]
        if definition.on == ON_WALL:
            picture, top = self.ornaments.on_wall(ornament.kind, definition.width, layout.cell)
            box = pygame.Rect((layout.wall.x + ornament.x * layout.cell, layout.wall.y + top), picture.get_size())
        else:
            box = pygame.Rect(
                layout.spot(ornament.x, ornament.y), (definition.width * layout.cell, definition.height * layout.depth)
            )

        def draw(target: pygame.Surface, corner: tuple[int, int]) -> None:
            pygame.draw.rect(target, CANNOT_GO, box.move(corner), max(2, layout.cell // 20), border_radius=4)

        return (float("inf"), draw)

    def _decor_picture(self, entry: DecorEntry, scale: int) -> pygame.Surface | None:
        """What a thing on the board looks like, to fit its tile: `scale` pixels of it to one of the canvas."""
        key = ("decor", entry.tab, entry.entry_id, scale)
        if key in self._pictures:
            return self._pictures[key]
        view, world = self.view, self.view.world
        size = DECOR_PICTURE * scale
        if entry.tab == ORNAMENTS:
            definition = world.registries.decor.ornaments[entry.entry_id]
            picture = self.ornaments.whole(entry.entry_id, definition.on == ON_WALL, (definition.width, definition.height), size)
        elif entry.tab == FURNITURE:
            definition = world.registries.interactables.get(entry.entry_id)
            if view.object_pictures.has(definition.kind, definition.width, definition.height):
                picture = view.object_pictures.whole(definition.kind, max(8, size // max(definition.width, definition.height)))
            else:
                sheet = view.object_sprites.sheet(definition)
                picture = sheet.subsurface((0, 0, min(definition.width * TILE_SIZE, sheet.get_width()), sheet.get_height()))
            fit = min(size / picture.get_width(), size / picture.get_height())
            picture = pygame.transform.smoothscale(
                picture, (max(1, round(picture.get_width() * fit)), max(1, round(picture.get_height() * fit)))
            )
        elif entry.entry_id == AS_BUILT_ID:
            return None
        else:
            picture = surface_swatch(entry.entry_id, entry.tab == WALLS, size)
        self._pictures[key] = picture
        return picture

    def _show_entry(self, entry: DecorEntry, cell: pygame.Rect) -> None:
        """Put the picture of a thing on its tile of the board."""
        view = self.view
        skin = view.hud.skin
        scale = view.layers.scale if skin.usable and view.layers is not None else 1
        picture = self._decor_picture(entry, scale)
        if picture is None:
            # The floor or the walls as the building was put up.
            mark = "="
            view.font.draw(view.canvas, mark, (cell.centerx - view.font.width(mark) // 2, cell.centery - LINE_HEIGHT // 2), PALETTE["dust"])
            return
        place = pygame.Rect(0, 0, max(1, picture.get_width() // scale), max(1, picture.get_height() // scale))
        place.center = cell.center
        if not skin.picture(view.canvas, picture, place):
            view.canvas.blit(picture, place)

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
        labels = []
        for placed in world.interactables.values():
            if room.contains((placed.x, placed.y)):
                draws.extend(self._object(room, layout, placed))
                if placed.object_id in world.containers:
                    labels.append(self._kept_in(room, layout, placed))
        for resident in world.residents.values():
            if resident.away or not room.contains(resident.tile):
                continue
            depth, draw, label = self._resident(room, layout, resident)
            draws.append((depth, draw))
            labels.append(label)
        for bundle in world.bundles.values():
            if room.contains(bundle.tile):
                draws.append(self._bundle(room, layout, bundle))
        for site in world.sites.values():
            if room.contains((site.x, site.y)):
                draws.append(self._site(room, layout, site))
        known = world.registries.decor.ornaments
        for ornament in world.decor.ornaments(world, room.room_id):
            draws.append(self._ornament(layout, ornament.kind, known[ornament.kind], ornament.x, ornament.y))
        draws.extend(filter(None, (self._in_hand(room, layout), self._to_remove(room, layout))))
        draws.sort(key=lambda entry: entry[0])
        # What the player has said its floor and its walls are made of, or else what it was put up with.
        floor_kind = world.decor.floor_of(world, room.room_id) or world.tile_map.terrain_at((room.x, room.y))
        wall_kind = world.decor.wall_of(world, room.room_id) or PLAIN_WALL
        key = (room.room_id, layout.cell, layout.columns, layout.rows, floor_kind, wall_kind, layout.door)
        if key not in self._shells:
            self._shells[key] = draw_shell(layout, floor_kind, sum(map(ord, room.room_id)), wall_kind)
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
        self.house_button.draw(canvas, view.font, active=self.board_open and not self.decorating)
        self.decor_button.draw(canvas, view.font, active=self.decorating)
        board = self.board_rect()
        if board is not None and self.decorating:
            chosen = (world.homes.floors.get(room.room_id, AS_BUILT_ID), world.homes.walls.get(room.room_id, AS_BUILT_ID))
            draw_decor_board(
                canvas, view.font, board, world, self.decor_tab, self.decor_held, self.decor_removing,
                view.pointer, self._show_entry, chosen, band_hue("urbanism"),
            )
        elif board is not None:
            draw_house_board(canvas, view.font, board, world, room.room_id, self.naming, band_hue("buildings"))
        left = self.decor_button.rect.right + 6
        view.font.draw(canvas, f"{room.name.capitalize()}, por dentro", (left, self.leave_button.rect.y + 1), PALETTE["paper"])
        if self.decorating:
            view.font.draw(canvas, DECOR_NOTE, (viewport.x + 6, viewport.bottom - LINE_HEIGHT - 3), PALETTE["dust"])

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

    def _kept_in(self, room: Room, layout: InteriorLayout, placed: Interactable):
        """Where something that things are kept in is on the screen, to be picked there."""
        view = self.view
        definition = view.world.definition_of(placed)
        column, row = self.place(room, placed.x, placed.y)
        left, top = layout.spot(column, row)
        own = self._own(layout, definition)
        rise = own.rise if own is not None else 0
        box = pygame.Rect(left, top - rise, definition.width * layout.cell, definition.height * layout.depth + rise)
        hitbox = pygame.Rect(self._to_canvas(box.topleft), (max(4, box.width // SCALE), max(4, box.height // SCALE)))

        def label() -> None:
            view.container_hitboxes[placed.object_id] = hitbox
            if placed.object_id == view.hud.selected_container:
                pygame.draw.rect(view.canvas, PALETTE["glow"], hitbox, 1)

        return label

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

    def _bundle(self, room: Room, layout: InteriorLayout, bundle: Bundle):
        """A child in its blanket: on the back of whoever carries it, or where it was put down."""
        view = self.view
        detail = layout.cell / TILE_SIZE
        carrier = view.world.residents.get(bundle.carried_by or "") if bundle.place == BUNDLE_CARRIED else None
        if carrier is not None and room.contains(carrier.tile):
            x, y, facing, _ = view._walk_state(carrier)
            foot = layout.spot(*self.place(room, x + 0.5 + view.sway(carrier), y + 0.5))
            turned = view._doll_facing.get(carrier.resident_id, DOLL_FACINGS.get(facing, DOLL_FACINGS["right"]))
            back = BUNDLE_BEHIND if turned == DOLL_FACINGS["left"] or facing == "left" else -BUNDLE_BEHIND
            share = grown_share(view.world, carrier)
            middle, bottom, depth = foot[0] + back * share * detail, foot[1] - BUNDLE_UP * share * detail, foot[1] - 0.1
        else:
            foot = layout.spot(*self.place(room, bundle.x + 0.5, bundle.y + 0.5))
            raised = BUNDLE_RAISED * detail if bundle.place != BUNDLE_ON_GROUND else 0.0
            middle, bottom, depth = foot[0], foot[1] - raised, foot[1] + 0.7
        picture = view.bundle_shown(bundle, max(4, round(BUNDLE_WIDTH * detail)))
        corner_of = (round(middle - picture.get_width() / 2), round(bottom - picture.get_height()))

        def draw(target: pygame.Surface, corner: tuple[int, int]) -> None:
            target.blit(picture, (corner[0] + corner_of[0], corner[1] + corner_of[1]))

        return (depth, draw)

    def _resident(self, room: Room, layout: InteriorLayout, resident: Resident):
        """Somebody in the room: how far down the floor they are, how to draw them, and what goes over their head."""
        view = self.view
        x, y, facing, stride = view._walk_state(resident)
        lying_in = view._lying_in(resident)
        if lying_in is not None:
            return self._asleep(room, layout, resident, lying_in)
        # Whoever is under something reels here as they do on the map.
        column, row = self.place(room, x + 0.5 + view.sway(resident), y + 0.5)
        foot = layout.spot(column, row)
        detail = layout.cell / TILE_SIZE
        doll = view._doll_for(resident)
        # Somebody not yet grown has a smaller body under the head they were drawn with.
        grown = grown_share(view.world, resident)
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
            # The same body as on the map, moving as it does there: on its springs.
            character = view.bodies.character(resident)
            if character.plan is not plan and not character.physical:
                character.plan = plan
            character.lively = True
            character.at_ease = (
                stride is None
                and overlay is None
                and view._meal_in_hand(resident) is None
                and view._weapon_in_hand(resident) is None
            )
            character.stand(*ground_spot(x, y), facing, clip, turn % 1.0, overlay)
            pose = character.local_pose()
            skeleton.set_pose(pose)
            reach = doll.standing(plan)
            # A smaller body is brought down about the ground its soles are on.
            sole = (0.0, reach[3])
            held = self.in_hand(resident, facing, pose, turn, stride, grown, sole)
            high = reach[1] * (HEAD_OF_HEIGHT + (1.0 - HEAD_OF_HEIGHT) * grown)
            box = pygame.Rect(
                foot[0] + math.floor(reach[0] * detail),
                foot[1] + math.floor(high * detail),
                math.ceil((reach[2] - reach[0]) * detail),
                math.ceil((reach[3] - high) * detail),
            )

            def draw(target: pygame.Surface, corner: tuple[int, int]) -> None:
                self._shadow(target, corner, foot, layout)
                draw_doll(
                    target, doll, plan, skeleton, (corner[0] + foot[0], corner[1] + foot[1]), detail,
                    view.dolls.allowance, grown, sole,
                )
                self._show_held(target, held, (corner[0] + foot[0], corner[1] + foot[1]), detail)

        else:
            frames = renderer.frames(clip, facing)
            index = int(turn * frames) % frames
            picture, origin = renderer.frame(resident.resident_id, facing, clip, index, (), overlay)
            pose = view.bodies.plan.pose(facing, clip, index / frames, overlay)
            held = self.in_hand(resident, facing, pose, turn, stride, grown)
            # The game's own small body is brought down whole for whoever is not grown.
            detail *= grown
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
            detail /= grown

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

    def in_hand(
        self,
        resident: Resident,
        facing: str,
        pose: dict,
        turn: float,
        stride: float | None,
        grown: float = 1.0,
        sole: tuple[float, float] = (0.0, 0.0),
    ) -> list:
        """What somebody has in their hand, as the map would show it, from where their feet are:
        the meal they are at with the bites gone from it and the crumbs that fly, what they
        fight with, or what they carry for their job. Empty for empty hands. `grown` is how
        much of its size their body is shown at, about the ground at `sole`."""
        view = self.view
        kept, view._held = view._held, []
        meal = view._meal_in_hand(resident)
        weapon = view._weapon_in_hand(resident) if stride is None else None
        load = view._load_of(resident)
        about = (grown, sole)
        if meal is not None:
            view._hold(meal, facing, pose, 0.0, turn, view._bites_taken(resident), about)
        elif weapon is not None:
            view._hold(weapon, facing, pose, 0.0, about=about)
        elif load is not None:
            view._hold(load, facing, pose, 0.0, about=about)
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
        doll = view._doll_for(resident)
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
