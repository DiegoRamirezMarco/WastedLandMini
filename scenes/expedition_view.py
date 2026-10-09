"""Somebody out of the settlement, seen from the side as they go: they walk on the spot and the
country goes by behind them (P68).

Whoever is out is nowhere on the map. Here they are seen walking for as long as the trip
lasts: away from the settlement for the way out and towards it for the way home, standing
still while they wait to be told whether to go for something they have come on. What goes by
behind them is the backdrop of the country the trip goes through (`graphics.backdrop`), dark
after dark and blown with dust in a storm, as the map is.

It is a part of the global view and draws with what that has: the same bodies and dolls.
Everything is laid out in pixels of the window, since that is what it is shown in. Nothing
here is the simulation's: how far along the trip is and which way they are headed is read
from it, and how far the ground has gone by is only how it looks.
"""

from __future__ import annotations

import math
from collections.abc import Hashable
from typing import TYPE_CHECKING

import pygame

from graphics.backdrop import BackdropStore, draw_strips
from graphics.body_renderer import FRAME_ORIGIN, FRAME_SIZE
from graphics.doll import DOLL_FACINGS, draw_doll
from graphics.lighting import ambient, daylight
from graphics.palette import PALETTE, Color
from graphics.screen_layers import TRANSPARENT
from scenes.body_stage import HEAD_OF_HEIGHT, TILES_PER_STRIDE, grown_share
from settings import SCALE, TILE_SIZE
from simulation.residents.manner import IDLE_CLIP, WALK
from simulation.residents.resident import Resident
from ui.button import Button
from ui.labels import trip_ends, trip_lines
from ui.trip_bar import draw_trip_bar, trip_bar_height

if TYPE_CHECKING:
    from scenes.global_view import GlobalView

LEAVE_TRIP_INTENT = ("leave_trip",)
LEAVE_LABEL = "Volver"
# Opens the screen where the country they go through is drawn (P69).
DRAW_BACKDROP_INTENT = ("draw_backdrop",)
DRAW_LABEL = "Dibujar fondo"
MARGIN = 6
# The country of a trip that goes through none the data names.
NOWHERE = "nowhere"
# How tall a body is taken to be, in its skeleton's own measure: what the backdrop's share of
# its height for somebody standing is filled by.
BODY_TALL = 31.0
# Strides a second at the game's first speed, and how much faster for each doubling of it:
# quicker when time flies, and never so quick that legs cannot be seen.
STRIDES = 0.95
HURRY = 0.3
# How far across the place whoever walks is: with more of it ahead of them than behind, and
# how much of the way from one side to the other they are brought in a second on turning.
AHEAD = 0.42
TURNING = 1.6
# The most of a second taken at a time: a frame that took long does not throw them forward.
LONGEST_FRAME = 0.1
BACKDROP: Color = (17, 20, 26)
SHADE = (0, 0, 0, 70)
# Dust in a storm: how many streaks, how fast they go in pixels of the window a second, and
# what the whole of it is tinted.
STREAKS = 34
STREAK_SPEED = 520.0
STORM_TINT: Color = (226, 198, 156)
BAR_WIDTH = 236


class ExpeditionView:
    """Draws whoever the global view is watching out of the settlement, in its part of the screen."""

    def __init__(self, view: "GlobalView") -> None:
        self.view = view
        corner = view.viewport.topright
        self.leave_button = Button.at(view.font, 0, corner[1] + MARGIN, LEAVE_LABEL, LEAVE_TRIP_INTENT)
        self.leave_button.rect.right = corner[0] - MARGIN
        self.draw_button = Button.at(view.font, 0, corner[1] + MARGIN, DRAW_LABEL, DRAW_BACKDROP_INTENT)
        self.draw_button.rect.right = self.leave_button.rect.left - 3
        self.backdrops = BackdropStore(view.illustrations)
        # How far the ground has gone by under them, in the measure of their own body: on as
        # they go out and back as they come home. And how many strides they have taken.
        self.travelled = 0.0
        self.strides = 0.0
        # How far across the place they stand, as a share of it.
        self.lead = AHEAD
        self._watched: str | None = None
        self._pictures: dict[tuple, pygame.Surface] = {}

    def stage(self) -> pygame.Rect:
        """The part of the screen the trip is shown in, in pixels of the window, from its own corner."""
        viewport = self.view.viewport
        return pygame.Rect(0, 0, viewport.width * SCALE, viewport.height * SCALE)

    def buttons(self) -> list[Button]:
        """The way back to the map, and to where what goes by is drawn if there is anywhere to keep drawings."""
        return [self.leave_button, *([self.draw_button] if self.backdrops.available else [])]

    def click(self, position: tuple[int, int]) -> Hashable | None:
        """What a press at a place on the canvas asks for, if it is on anything of this view's."""
        return next((button.intent for button in self.buttons() if button.contains(position)), None)

    def zone_id(self, resident: Resident) -> str:
        """The zone whoever is out is in right now, by ID: each of those on their way, in its turn."""
        trip = resident.expedition
        zone = self.view.world.expeditions.zone_now(self.view.world, trip) if trip is not None else None
        return zone.zone_id if zone is not None else NOWHERE

    def stopped(self, resident: Resident) -> bool:
        """Whether they stand where they are, waiting to be told what to do about what they have come on."""
        return self.view._decision_of(resident.resident_id) is not None

    def heading_back(self, resident: Resident) -> bool:
        trip = resident.expedition
        return trip is not None and trip.heading_back(self.view.world.clock.total_minutes)

    def detail(self) -> float:
        """How many pixels of the window go to one of a body's own."""
        return self.backdrops.plan.figure * self.stage().height / BODY_TALL

    def update(self, seconds: float, resident: Resident | None) -> None:
        """Let real time pass for whoever is watched: they walk on, unless time stands still or they do."""
        clock = self.view.world.clock
        if resident is None or not resident.away:
            return
        if resident.resident_id != self._watched:
            # Somebody else: they are found where they belong, and not brought across to it.
            self._watched = resident.resident_id
            self.lead = 1.0 - AHEAD if self.heading_back(resident) else AHEAD
        seconds = min(seconds, LONGEST_FRAME)
        back = self.heading_back(resident)
        wanted = 1.0 - AHEAD if back else AHEAD
        self.lead += (wanted - self.lead) * min(1.0, TURNING * seconds)
        if clock.paused or self.stopped(resident):
            return
        taken = seconds * STRIDES * (1.0 + HURRY * math.log2(max(1, clock.speed)))
        self.strides += taken
        self.travelled += (-taken if back else taken) * TILES_PER_STRIDE * TILE_SIZE

    def _to_canvas(self, point: tuple[float, float]) -> tuple[int, int]:
        viewport = self.view.viewport
        return (viewport.x + round(point[0] / SCALE), viewport.y + round(point[1] / SCALE))

    def feet(self) -> tuple[int, int]:
        """Where on the stage the spot between their feet is."""
        stage = self.stage()
        return (round(stage.width * self.lead), round(stage.height * self.backdrops.plan.ground))

    def bar_rect(self, resident: Resident) -> pygame.Rect:
        """Where the way of the trip is shown, on the canvas: up in the sky, under the way back
        to the map, where it is over nothing of whoever walks or of the ground they are on."""
        view = self.view
        viewport = view.viewport
        width = min(BAR_WIDTH, viewport.width - MARGIN * 2)
        face = view.faces.marker(resident.resident_id)
        height = trip_bar_height(view.font, width, face.get_height(), trip_lines(view.world, resident))
        return pygame.Rect(viewport.right - MARGIN - width, self.leave_button.rect.bottom + 3, width, height)

    def _body(self, resident: Resident, feet: tuple[int, int], detail: float):
        """Somebody walking, or standing if they have stopped: how to draw them with their feet
        at a place on the stage, and the part of the stage they take."""
        view = self.view
        stopped = self.stopped(resident)
        side = "left" if self.heading_back(resident) else "right"
        clip, rate = (IDLE_CLIP, 0.0) if stopped else view._way_of(resident, WALK)
        turn = (view.time if stopped else self.strides) * rate
        grown = grown_share(view.world, resident)
        doll = view._doll_for(resident)
        if doll is not None:
            facing = DOLL_FACINGS[side]
            plan = doll.plan if doll.plan is not None else view.bodies.plan
            # The same body as on the map, moving as it does there: on its springs.
            character = view.bodies.character(resident)
            if character.plan is not plan and not character.physical:
                character.plan = plan
            character.lively = True
            # Stopped, they have nothing to do but wait, and may fidget.
            character.at_ease = stopped
            character.stand(0.0, 0.0, facing, clip, turn % 1.0)
            skeleton = view._posed_skeleton(resident.resident_id, character)
            reach = doll.standing(plan)
            sole = (0.0, reach[3])
            # Their soles are on the ground, wherever under them the spot between their feet is.
            origin = (feet[0], feet[1] - round(reach[3] * detail))
            high = reach[1] * (HEAD_OF_HEIGHT + (1.0 - HEAD_OF_HEIGHT) * grown)
            box = pygame.Rect(
                origin[0] + math.floor(reach[0] * detail),
                origin[1] + math.floor(high * detail),
                math.ceil((reach[2] - reach[0]) * detail),
                math.ceil((reach[3] - high) * detail),
            )

            def draw(target: pygame.Surface, corner: tuple[int, int]) -> None:
                draw_doll(
                    target, doll, plan, skeleton, (corner[0] + origin[0], corner[1] + origin[1]), detail,
                    view.dolls.allowance, grown, sole,
                )

            return draw, box
        # With no window to show a doll on, the game's own small body, as large as it has to be.
        renderer = view.bodies.renderer
        frames = renderer.frames(clip, side)
        index = int(turn * frames) % frames
        picture, origin = renderer.frame(resident.resident_id, side, clip, index, tuple(resident.lost_limbs))
        detail *= grown
        size = (max(1, round(picture.get_width() * detail)), max(1, round(picture.get_height() * detail)))
        key = (id(picture), size)
        if key not in self._pictures:
            if len(self._pictures) > 64:
                self._pictures.clear()
            self._pictures[key] = pygame.transform.scale(picture, size)
        shown = self._pictures[key]
        corner_of = (feet[0] - round(origin[0] * detail), feet[1] - round(origin[1] * detail))
        box = pygame.Rect(
            feet[0] - round(FRAME_ORIGIN[0] * detail),
            feet[1] - round(FRAME_ORIGIN[1] * detail),
            round(FRAME_SIZE[0] * detail),
            round(FRAME_SIZE[1] * detail),
        )

        def draw(target: pygame.Surface, corner: tuple[int, int]) -> None:
            target.blit(shown, (corner[0] + corner_of[0], corner[1] + corner_of[1]))

        return draw, box

    def _weather(self, target: pygame.Surface, area: pygame.Rect) -> None:
        """Dust across it all in a storm, and the dark of the hour over everything."""
        view = self.view
        world = view.world
        if world.happenings.is_stormy(world):
            drift = view.time * STREAK_SPEED
            for index in range(STREAKS):
                # Each streak keeps its own height and length, and they all go with the wind.
                x = (index * 197 + drift * (1.0 + index % 3 * 0.4)) % (area.width + 120) - 120
                y = (index * 113 + index * index * 17) % max(1, area.height)
                long = 30 + index % 5 * 22
                pygame.draw.line(target, PALETTE["sand"], (area.x + x, area.y + y), (area.x + x + long, area.y + y), 2 + index % 2)
            target.fill(STORM_TINT, area, special_flags=pygame.BLEND_RGB_MULT)
        level = daylight(world.clock.hour, world.clock.minute)
        if level < 1.0:
            target.fill(ambient(level), area, special_flags=pygame.BLEND_RGB_MULT)

    def render(self, resident: Resident) -> None:
        """Draw the trip of somebody who is out, the way of it, and the way back to the map."""
        view = self.view
        canvas, viewport, world = view.canvas, view.viewport, view.world
        stage = self.stage()
        detail = self.detail()
        strips = self.backdrops.strips(self.zone_id(resident), stage.height)
        feet = self.feet()
        figure, box = self._body(resident, feet, detail)
        gone_by = self.travelled * detail
        shade_size = (max(8, round(box.width * 0.9)), max(4, round(detail * 2.2)))

        def paint(target: pygame.Surface, corner: tuple[int, int]) -> None:
            area = pygame.Rect(corner, stage.size)
            before = target.get_clip()
            target.set_clip(area)
            target.fill(BACKDROP, area)
            draw_strips(target, strips, area, gone_by, front=False)
            shade = pygame.Surface(shade_size, pygame.SRCALPHA)
            pygame.draw.ellipse(shade, SHADE, shade.get_rect())
            target.blit(shade, shade.get_rect(center=(corner[0] + feet[0], corner[1] + feet[1])))
            figure(target, corner)
            draw_strips(target, strips, area, gone_by, front=True)
            self._weather(target, area)
            target.set_clip(before)

        layers = view.layers
        if layers is not None and canvas.get_flags() & pygame.SRCALPHA:
            corner = layers.on_screen(viewport).topleft
            layers.under(lambda screen: paint(screen, corner))
            canvas.fill(TRANSPARENT, viewport)
        else:
            # With no window under the canvas, the same picture brought down to it.
            picture = pygame.Surface(stage.size)
            paint(picture, (0, 0))
            canvas.blit(pygame.transform.smoothscale(picture, viewport.size), viewport)

        hitbox = pygame.Rect(self._to_canvas(box.topleft), (max(4, box.width // SCALE), max(4, box.height // SCALE)))
        view.hitboxes[resident.resident_id] = hitbox
        canvas.set_clip(viewport)
        view._draw_overhead(resident, (hitbox.centerx, hitbox.top), with_name=True)
        canvas.set_clip(None)
        for button in self.buttons():
            button.draw(canvas, view.font)
        trip = resident.expedition
        now = world.clock.total_minutes
        draw_trip_bar(
            canvas,
            view.font,
            self.bar_rect(resident),
            view.faces.marker(resident.resident_id),
            trip.distance(now) if trip is not None else 0.0,
            self.heading_back(resident),
            self.stopped(resident),
            trip_ends(world, resident),
            trip_lines(world, resident),
            # Where one zone gives way to the next, along the way.
            tuple(trip.stages[:-1]) if trip is not None else (),
        )
