from collections.abc import Callable, Hashable, Iterable

import pygame

from graphics.assets import AssetStore
from graphics.character_renderer import FRAME_SIZE, CharacterRenderer
from graphics.face_renderer import FaceRenderer
from graphics.font import CELL_SIZE, BitmapFont
from graphics.icons import ICON_SIZE, icon_path
from graphics.item_icons import ItemIcons
from graphics.lighting import BLOCK, LightMap, daylight, shade
from graphics.map_renderer import render_roofs, render_terrain, roof_names
from graphics.palette import PALETTE
from graphics.shelf_display import SLOTS, displayed_goods
from graphics.tileset import (
    CLOSE_ROOF_SHEET,
    ROOF_CELLS,
    ROOF_SHEET,
    ROOF_SHEET_SIZE,
    SETTLEMENT_CELLS,
    SETTLEMENT_SHEET,
    SETTLEMENT_SHEET_SIZE,
    Tileset,
)
from scenes.hud import JOBS_INTENT, LOG_INTENT, PAUSE_INTENT, Hud
from scenes.scene import canvas_position
from settings import SCALE, TILE_SIZE
from simulation.commands import SetPausedCommand, SetSpeedCommand, SuggestJobCommand
from simulation.events.event import DomainEvent
from simulation.items.item_system import USE_ITEM_ACTION
from simulation.work.work_system import WORK_ACTION
from simulation.residents.resident import Resident
from simulation.world import SimulationWorld
from ui.labels import away_residents
from ui.minimap import TILE_PIXELS, draw_minimap, minimap_base, minimap_size, tile_at
from ui.panel import draw_panel
from world.interactable import Interactable
from world.map import Tile

MAP_ORIGIN = (0, 32)
# Walk cycle over one tile: step A, idle, step B, idle.
WALK_CYCLE = (1, 0, 2, 0)
# Rows of a body frame left visible when a resident lies in a bed: hair and eyes above the blanket.
LYING_HEAD_ROWS = 10
# Frames per second of animated objects and bobbing icons.
ANIMATION_FPS = 5
BOBBING_ICONS = ("alert", "sleep")
# Health below which a resident is shown as hurt.
HURT_HEALTH = 70.0
# Where a load is drawn on a body frame, by the way the resident faces: in their arms, or on their back.
LOAD_OFFSETS = {"down": (4, 13), "up": (4, 12), "left": (0, 13), "right": (8, 13)}
SUGGESTION_REFUSED = "Ahora no se le puede proponer ese puesto"
NOBODY_NEEDS_ATTENTION = "Nadie necesita atención ahora"
ROOFS_ON = "Tejados puestos: se quitan al mirar dentro"
ROOFS_OFF = "Tejados quitados"
MINIMAP_ON = "Minimapa a la vista"
MINIMAP_OFF = "Minimapa guardado"
AWAY_LABEL = "Fuera"
MINIMAP_MARGIN = 6
# What bad weather multiplies the picture of the map by, and how many streaks of dust blow across it.
STORM_TINT = (226, 198, 156)
STORM_STREAKS = 70
STORM_SPEED = 140
# Canvas pixels per real second that the view scrolls while a direction key is held.
SCROLL_SPEED = 260
SCROLL_KEYS = {
    (-1, 0): (pygame.K_LEFT, pygame.K_a),
    (1, 0): (pygame.K_RIGHT, pygame.K_d),
    (0, -1): (pygame.K_UP, pygame.K_w),
    (0, 1): (pygame.K_DOWN, pygame.K_s),
}
RIGHT_MOUSE_BUTTON = 2
# Canvas pixels a tile takes at each zoom step, whole multiples of the art but for the first.
# The first is the overview: the settlement from afar, with the roofs on and a face for each resident.
ZOOM_TILE_SIZES = (TILE_SIZE // 2, TILE_SIZE, TILE_SIZE * 2, TILE_SIZE * 3)
DEFAULT_ZOOM = 1
ZOOM_KEYS = {
    pygame.K_PLUS: 1,
    pygame.K_KP_PLUS: 1,
    pygame.K_EQUALS: 1,
    pygame.K_MINUS: -1,
    pygame.K_KP_MINUS: -1,
}

Draw = tuple[float, int, Callable[[], None]]


class GlobalView:
    def __init__(
        self,
        canvas: pygame.Surface,
        world: SimulationWorld,
        assets: AssetStore,
        font: BitmapFont,
        icons: ItemIcons,
        faces: FaceRenderer,
    ) -> None:
        self.canvas = canvas
        self.world = world
        self.assets = assets
        self.font = font
        self.icons = icons
        self.faces = faces
        self.characters = CharacterRenderer(assets)
        self.hud = Hud(canvas, world, font, icons)
        # Real seconds of unpaused play, driving animations that have nothing to do with game state.
        self.time = 0.0
        # How far the current game minute has played out, from 0 to 1. Set by the game shell.
        self.tick_progress = 0.0
        # Residents taking part in an event important enough to call for the player's attention.
        self.alerts: set[str] = set()
        # Where each resident was last drawn, for picking them with the mouse.
        self.hitboxes: dict[str, pygame.Rect] = {}
        self.container_hitboxes: dict[str, pygame.Rect] = {}
        # Decision the player asked to open by clicking a resident. The game shell picks it up.
        self.requested_decision: str | None = None
        tileset = Tileset(self.assets.image(SETTLEMENT_SHEET, size=SETTLEMENT_SHEET_SIZE), SETTLEMENT_CELLS)
        self.terrain = render_terrain(world.tile_map, tileset)
        # The tiles that roofs cover, and the same terrain with those roofs on.
        self.roofs = roof_names(world.tile_map, world.rooms.values())
        roof_tiles = Tileset(self.assets.image(ROOF_SHEET, size=ROOF_SHEET_SIZE), ROOF_CELLS)
        self.roofed_terrain = render_roofs(self.terrain, self.roofs, roof_tiles)
        # The same from close, where a building keeps its roof until it is looked into.
        close_tiles = Tileset(self.assets.image(CLOSE_ROOF_SHEET, size=ROOF_SHEET_SIZE), ROOF_CELLS)
        self.close_roofed_terrain = render_roofs(self.terrain, self.roofs, close_tiles)
        self.roof_tiles: dict[str, set[Tile]] = {
            room.room_id: set(roof_names(world.tile_map, [room])) for room in world.rooms.values() if room.roofed
        }
        # Whether buildings have their roof on from close. Off, every one of them stands open.
        self.roofs_on = True
        # Canvas position of the mouse, as far as the scene has been told.
        self.pointer: tuple[int, int] | None = None
        # Tiles under a roof that is on this frame: what stands there is not drawn.
        self._hidden: set[Tile] = set()
        self.lights = LightMap()
        tiles = (world.tile_map.width, world.tile_map.height)
        self._minimap = minimap_base(self.roofed_terrain, tiles)
        width, height = minimap_size(tiles)
        self._minimap_rect = pygame.Rect(
            canvas.get_width() - MINIMAP_MARGIN - width, canvas.get_height() - MINIMAP_MARGIN - height, width, height
        )
        self.hud.minimap_rect = self._minimap_rect
        # The part of the canvas that shows the map, and the map pixel at its top-left corner.
        self.viewport = pygame.Rect(
            MAP_ORIGIN, (canvas.get_width() - MAP_ORIGIN[0], canvas.get_height() - MAP_ORIGIN[1])
        )
        self.camera = [0.0, 0.0]
        # Index into ZOOM_TILE_SIZES.
        self.zoom = DEFAULT_ZOOM
        # What is being drawn this frame: the visible part of the map at the size of its art, where
        # that part starts on the map, and what goes on top of it once it is on the canvas.
        self._scene = self.terrain
        self._scene_origin = (0, 0)
        self._overlays: list[Callable[[], None]] = []
        self._buffers: dict[tuple[int, int], pygame.Surface] = {}
        commons = world.rooms.get("commons")
        if commons is not None:
            self.centre_on((commons.x + commons.width / 2, commons.y + commons.height / 2))

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.KEYDOWN and event.key == pygame.K_l:
            self._apply(LOG_INTENT)
        elif event.type == pygame.KEYDOWN and event.key == pygame.K_j:
            self._apply(JOBS_INTENT)
        elif event.type == pygame.KEYDOWN and event.key == pygame.K_c:
            self.centre_on_resident(self.hud.selected_id)
        elif event.type == pygame.KEYDOWN and event.key == pygame.K_g:
            self.jump_to_attention()
        elif event.type == pygame.KEYDOWN and event.key == pygame.K_t:
            self.roofs_on = not self.roofs_on
            self.hud.notify(ROOFS_ON if self.roofs_on else ROOFS_OFF)
        elif event.type == pygame.KEYDOWN and event.key == pygame.K_n:
            self.hud.minimap_rect = None if self.hud.minimap_rect is not None else self._minimap_rect
            self.hud.notify(MINIMAP_ON if self.hud.minimap_rect is not None else MINIMAP_OFF)
        elif event.type == pygame.KEYDOWN and event.key in ZOOM_KEYS:
            self.set_zoom(self.zoom + ZOOM_KEYS[event.key])
        elif event.type == pygame.MOUSEWHEEL:
            # The wheel zooms towards whatever is under the mouse, one step per notch.
            steps = (event.y > 0) - (event.y < 0)
            self.set_zoom(self.zoom + steps, canvas_position(pygame.mouse.get_pos()))
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            self.pointer = canvas_position(event.pos)
            self.click(self.pointer)
        elif event.type == pygame.MOUSEMOTION:
            self.pointer = canvas_position(event.pos)
            if event.buttons[RIGHT_MOUSE_BUTTON]:
                # Dragging with the right button pulls the map along with the mouse.
                self.scroll(-event.rel[0] / SCALE, -event.rel[1] / SCALE)

    def update(self, dt: float) -> None:
        if not self.world.clock.paused:
            self.time += dt
        self.hud.update(dt)
        pressed = pygame.key.get_pressed()
        for (dx, dy), keys in SCROLL_KEYS.items():
            if any(pressed[key] for key in keys):
                self.scroll(dx * SCROLL_SPEED * dt, dy * SCROLL_SPEED * dt)

    @property
    def tile_px(self) -> int:
        """Canvas pixels a tile takes at the current zoom."""
        return ZOOM_TILE_SIZES[self.zoom]

    @property
    def overview(self) -> bool:
        """True when the map is seen from as far as it goes."""
        return self.zoom == 0

    def scroll(self, dx: float, dy: float) -> None:
        """Move the view over the map by a distance in canvas pixels, stopping at its edges."""
        for axis, distance in enumerate((dx, dy)):
            in_view = self.viewport.size[axis] * TILE_SIZE / self.tile_px
            limit = max(0.0, self.terrain.get_size()[axis] - in_view)
            moved = self.camera[axis] + distance * TILE_SIZE / self.tile_px
            self.camera[axis] = min(max(moved, 0.0), limit)

    def centre_on(self, tile: tuple[float, float]) -> None:
        """Put a map tile in the middle of the view, as far as the map's edges allow."""
        self._show_at((tile[0] * TILE_SIZE, tile[1] * TILE_SIZE), self.viewport.center)

    def centre_on_resident(self, resident_id: str | None) -> None:
        resident = self.world.residents.get(resident_id or "")
        if resident is not None:
            self.centre_on((resident.x + 0.5, resident.y + 0.5))

    def set_zoom(self, zoom: int, anchor: tuple[int, int] | None = None) -> None:
        """Change the zoom step. The part of the map at `anchor`, a canvas position, stays under it.

        Without an anchor on the map, the middle of the view is what stays in place.
        """
        if anchor is None or not self.viewport.collidepoint(anchor):
            anchor = self.viewport.center
        held = self._map_point(anchor)
        self.zoom = min(max(zoom, 0), len(ZOOM_TILE_SIZES) - 1)
        self._show_at(held, anchor)

    def _show_at(self, map_point: tuple[float, float], position: tuple[int, int]) -> None:
        """Move the view so a map pixel falls on a canvas position, as far as the map's edges allow."""
        for axis in (0, 1):
            offset = position[axis] - self.viewport.topleft[axis]
            self.camera[axis] = map_point[axis] - offset * TILE_SIZE / self.tile_px
        self.scroll(0, 0)

    def on_events(self, events: Iterable[DomainEvent]) -> None:
        """React to what the simulation just emitted."""
        events = list(events)
        self.hud.on_events(events)
        for event in events:
            if event.importance >= self.hud.intervention_from:
                self.alerts.update(event.participants)
        # Someone asking for advice may be off screen: bring them into view.
        for decision in self.world.decisions.values():
            if any(decision.resident_id in event.participants for event in events):
                self.centre_on_resident(decision.resident_id)
                break

    def needing_attention(self) -> list[str]:
        """Residents the player should look at, the most pressing first.

        Whoever waits for advice, then whoever is in the middle of something serious, then the hurt.
        """
        waiting = [decision.resident_id for decision in self.world.decisions.values()]
        involved = [resident_id for resident_id in self.world.residents if resident_id in self.alerts]
        hurt = [
            resident_id for resident_id, resident in self.world.residents.items() if resident.health < HURT_HEALTH
        ]
        return [resident_id for resident_id in dict.fromkeys([*waiting, *involved, *hurt]) if resident_id in self.world.residents]

    def jump_to_attention(self) -> str | None:
        """Select and show the next resident who needs attention, going round them one by one."""
        waiting = self.needing_attention()
        if not waiting:
            self.hud.notify(NOBODY_NEEDS_ATTENTION)
            return None
        current = self.hud.selected_id
        chosen = waiting[(waiting.index(current) + 1) % len(waiting)] if current in waiting else waiting[0]
        self.hud.select_resident(chosen)
        self.centre_on_resident(chosen)
        return chosen

    def looked_into(self) -> set[str]:
        """Roofed rooms that stand open this frame: under the pointer, or holding what is selected."""
        if self.overview:
            return set()
        if not self.roofs_on:
            return set(self.roof_tiles)
        looked_at: list[Tile] = []
        if self.pointer is not None and self.viewport.collidepoint(self.pointer) and not self.hud.covers(self.pointer):
            x, y = self._map_point(self.pointer)
            looked_at.append((int(x // TILE_SIZE), int(y // TILE_SIZE)))
        selected = self.world.residents.get(self.hud.selected_id or "")
        if selected is not None:
            looked_at.append(selected.tile)
        container = self.world.interactables.get(self.hud.selected_container or "")
        if container is not None:
            looked_at.append((container.x, container.y))
        return {
            room_id for room_id in self.roof_tiles if any(self._is_at(room_id, tile) for tile in looked_at)
        }

    def _is_at(self, room_id: str, tile: Tile) -> bool:
        """Whether a tile is under a building's roof or in the wall in front of it, door included."""
        room = self.world.rooms[room_id]
        in_front = tile[1] == room.y + room.height and room.x - 1 <= tile[0] <= room.x + room.width
        return tile in self.roof_tiles[room_id] or in_front

    def _roof_area(self, room_id: str) -> pygame.Rect:
        """The part of the map a building's roof covers, in map pixels."""
        room = self.world.rooms[room_id]
        return pygame.Rect(
            (room.x - 1) * TILE_SIZE, (room.y - 1) * TILE_SIZE, (room.width + 2) * TILE_SIZE, room.height * TILE_SIZE
        ).clip(self.terrain.get_rect())

    def click(self, position: tuple[int, int]) -> None:
        """Handle a left click at a canvas position: a button, the minimap, a resident, or empty ground."""
        intent = self.hud.click(position)
        minimap = self.hud.minimap_rect
        if intent is not None:
            self._apply(intent)
        elif minimap is not None and minimap.collidepoint(position):
            self.centre_on(tile_at(minimap, position))
        elif not self.hud.covers(position) and self.viewport.collidepoint(position):
            # The resident drawn last is in front, so it is the one picked.
            picked = [rid for rid, rect in self.hitboxes.items() if rect.collidepoint(position)]
            if picked:
                self.hud.select_resident(picked[-1])
            else:
                containers = [cid for cid, rect in self.container_hitboxes.items() if rect.collidepoint(position)]
                self.hud.select_container(containers[-1] if containers else None)
            decision = self._decision_of(self.hud.selected_id)
            if decision is not None:
                self.requested_decision = decision

    def _decision_of(self, resident_id: str | None) -> str | None:
        """ID of the open decision waiting on this resident, if any."""
        return next(
            (d.decision_id for d in self.world.decisions.values() if d.resident_id == resident_id), None
        )

    def _apply(self, intent: Hashable) -> None:
        if intent == PAUSE_INTENT:
            self.world.apply_command(SetPausedCommand(not self.world.clock.paused))
        elif intent == LOG_INTENT:
            self.hud.toggle_log()
        elif intent == JOBS_INTENT:
            self.hud.toggle_jobs()
        elif isinstance(intent, tuple) and intent[0] == "suggest":
            self._suggest_job(intent[1])
        elif isinstance(intent, tuple) and intent[0] == "speed":
            self.world.apply_command(SetSpeedCommand(intent[1]))
        elif isinstance(intent, tuple) and intent[0] == "zoom":
            self.set_zoom(self.zoom + intent[1])

    def _suggest_job(self, job_id: str) -> None:
        """Put a job to the selected resident and say what came of it. The choice is theirs."""
        resident = self.world.residents.get(self.hud.selected_id or "")
        if resident is None:
            return
        before = len(self.world.history)
        outcome = self.world.apply_command(SuggestJobCommand(resident.resident_id, job_id))
        answers = [event for event in self.world.history[before:] if event.event_type == "crisis_resolved"]
        if outcome is None or not answers:
            self.hud.notify(SUGGESTION_REFUSED)
        else:
            # The event also says what advice it came with, which here is always the same.
            self.hud.notify(answers[-1].text.partition(" (")[0])

    def render(self) -> None:
        self.canvas.fill(PALETTE["ink"])
        region = self._visible_region()
        self._scene = self._buffer(region.size)
        self._scene_origin = region.topleft
        self._scene.blit(self.roofed_terrain if self.overview else self.close_roofed_terrain, (0, 0), region)
        # A building that is looked into has its roof taken off: the bare terrain is put back there.
        open_rooms = self.looked_into()
        self._hidden = set()
        for room_id, covered in self.roof_tiles.items():
            if room_id not in open_rooms:
                self._hidden |= covered
                continue
            area = self._roof_area(room_id)
            self._scene.blit(self.terrain, (area.x - region.x, area.y - region.y), area)

        # Objects and residents share one list so that whatever stands lower on screen is in front.
        draws: list[Draw] = []
        for placed in self.world.interactables.values():
            # A roof hides what is under it.
            if (placed.x, placed.y) not in self._hidden:
                draws.append(self._object_draw(placed))
        for resident in self.world.residents.values():
            if resident.away:
                # Whoever is outside the settlement is nowhere on its map.
                continue
            # Someone under a roof is still found: their face is shown on it, as from afar.
            unseen = self.overview or resident.tile in self._hidden
            draws.append(self._marker_draw(resident) if unseen else self._resident_draw(resident))
        self.hitboxes = {}
        self.container_hitboxes = {}
        self._overlays = []
        for _, _, draw in sorted(draws, key=lambda entry: entry[:2]):
            draw()
        self._storm(region)
        self._shade(region)

        # Nothing of the map is drawn outside its part of the canvas.
        self.canvas.set_clip(self.viewport)
        size = (self._scaled(region.width), self._scaled(region.height))
        scene = self._scene
        if size != region.size:
            scene = pygame.transform.scale(scene, size, self._buffer(size))
        self.canvas.blit(scene, self._canvas_point(*region.topleft))
        # Names, icons and faces go straight on the canvas, so they keep their size at any zoom.
        for overlay in self._overlays:
            overlay()
        self.canvas.set_clip(None)

        self.hud.render()
        self._draw_minimap(region)
        self._draw_sky()
        self._draw_away()

    def _draw_sky(self) -> None:
        """A sun or a moon after the clock, for whether residents can see far or not."""
        icon = self.assets.image(icon_path("moon" if self.world.is_dark() else "sun"), size=ICON_SIZE)
        self.canvas.blit(icon, (MINIMAP_MARGIN + self.font.width(self.world.clock.label) + 4, 5))

    def _draw_away(self) -> None:
        """Whoever is outside the settlement is nowhere on the map: their faces go in a corner, to be picked there."""
        away = away_residents(self.world)
        if not away:
            return
        outlook = self.hud.outlook_rect()
        top = (outlook.bottom if outlook is not None else self.viewport.top) + MINIMAP_MARGIN
        label_width = self.font.width(AWAY_LABEL)
        face = self.faces.marker(away[0].resident_id)
        width = label_width + 8 + (face.get_width() + 2) * len(away)
        panel = pygame.Rect(MINIMAP_MARGIN, top, width + 4, face.get_height() + 4)
        draw_panel(self.canvas, panel)
        self.font.draw(self.canvas, AWAY_LABEL, (panel.x + 4, panel.y + 4), PALETTE["dust"])
        x = panel.x + 4 + label_width + 4
        for resident in away:
            marker = self.faces.marker(resident.resident_id)
            spot = marker.get_rect(topleft=(x, panel.y + 2))
            self.canvas.blit(marker, spot)
            self.hitboxes[resident.resident_id] = spot
            if resident.resident_id == self.hud.selected_id:
                pygame.draw.rect(self.canvas, PALETTE["glow"], spot, 1)
            x += marker.get_width() + 2

    def _storm(self, region: pygame.Rect) -> None:
        """Under bad weather, wash the scene in dust and blow streaks of it across."""
        if not self.world.happenings.is_stormy(self.world):
            return
        self._scene.fill(STORM_TINT, special_flags=pygame.BLEND_RGB_MULT)
        drift = int(self.time * STORM_SPEED)
        for index in range(STORM_STREAKS):
            # Each streak keeps its own height and length, and they all move with the wind.
            x = (index * 97 + drift * (1 + index % 3)) % (region.width + 16) - 16
            y = (index * 53 + index * index * 7) % max(1, region.height)
            pygame.draw.line(self._scene, PALETTE["sand"], (x, y), (x + 4 + index % 5, y))

    def _shade(self, region: pygame.Rect) -> None:
        """Darken the scene by the hour, leaving a pool of light round every fire and lamp in sight."""
        level = daylight(self.world.clock.hour, self.world.clock.minute)
        if level >= 1.0:
            return
        flicker = int(self.time * ANIMATION_FPS) % 2
        lights = []
        for placed in self.world.interactables.values():
            definition = self.world.definition_of(placed)
            if definition.light <= 0 or (placed.x, placed.y) in self._hidden:
                continue
            centre = (
                round((placed.x + definition.width / 2) * TILE_SIZE) - region.x,
                round((placed.y + definition.height / 2) * TILE_SIZE) - region.y,
            )
            # A flame wavers; a lamp burns steady.
            wavers = self._frames(placed.kind, definition.width) > 1
            lights.append((centre, definition.light * TILE_SIZE - (BLOCK * flicker if wavers else 0)))
        shade(self._scene, self.lights.render(region.size, level, lights))

    def _frames(self, kind: str, width_in_tiles: int) -> int:
        """How many animation frames an object's sheet holds, side by side."""
        sheet = self.assets.image(f"sprites/objects/{kind}.png")
        return max(1, sheet.get_width() // (width_in_tiles * TILE_SIZE))

    def _draw_minimap(self, region: pygame.Rect) -> None:
        rect = self.hud.minimap_rect
        if rect is None:
            return
        attention = set(self.needing_attention())
        blink = int(self.time * ANIMATION_FPS) % 2 == 0
        dots = {}
        for resident_id, resident in self.world.residents.items():
            if resident.away:
                continue
            color = "paper"
            if resident_id in attention:
                color = "ember" if blink else "glow"
            elif resident_id == self.hud.selected_id:
                color = "lamp"
            dots[(resident.x, resident.y)] = color
        view = pygame.Rect(
            region.x * TILE_PIXELS // TILE_SIZE,
            region.y * TILE_PIXELS // TILE_SIZE,
            region.width * TILE_PIXELS // TILE_SIZE,
            region.height * TILE_PIXELS // TILE_SIZE,
        )
        draw_minimap(self.canvas, rect, self._minimap, view, dots)

    def _buffer(self, size: tuple[int, int]) -> pygame.Surface:
        """A surface of this size to draw a frame on, kept from one frame to the next."""
        if size not in self._buffers:
            self._buffers[size] = pygame.Surface(size)
        return self._buffers[size]

    def _scaled(self, pixels: int) -> int:
        """Canvas pixels that a distance in map pixels takes at the current zoom."""
        return pixels * self.tile_px // TILE_SIZE

    def _visible_region(self) -> pygame.Rect:
        """The part of the map in view, in map pixels."""
        # The view moves by whole canvas pixels, which from afar are several map pixels each.
        step = max(1, TILE_SIZE // self.tile_px)
        left, top = (int(position) // step * step for position in self.camera)
        width, height = (-(-side * TILE_SIZE // self.tile_px) for side in self.viewport.size)
        return pygame.Rect(left, top, width, height).clip(self.terrain.get_rect())

    def _canvas_point(self, map_x: float, map_y: float) -> tuple[int, int]:
        """Canvas pixel where a map pixel is drawn, on screen or off it."""
        region = self._visible_region()
        point = []
        for axis, position in enumerate((map_x, map_y)):
            # A map smaller than the view sits in the middle of it.
            spare = max(0, self.viewport.size[axis] - self._scaled(self.terrain.get_size()[axis]))
            shown_at = self._scaled(round(position) - region.topleft[axis])
            point.append(self.viewport.topleft[axis] + spare // 2 + shown_at)
        return (point[0], point[1])

    def _canvas_rect(self, area: pygame.Rect) -> pygame.Rect:
        """Where a rectangle given in map pixels is drawn on the canvas."""
        left, top = self._canvas_point(*area.topleft)
        right, bottom = self._canvas_point(*area.bottomright)
        return pygame.Rect(left, top, right - left, bottom - top)

    def _map_point(self, position: tuple[int, int]) -> tuple[float, float]:
        """Map pixel that is drawn at a canvas position."""
        region = self._visible_region()
        corner = self._canvas_point(*region.topleft)
        x, y = (
            region.topleft[axis] + (position[axis] - corner[axis]) * TILE_SIZE / self.tile_px
            for axis in (0, 1)
        )
        return (x, y)

    def _tile_pixel(self, x: float, y: float) -> tuple[int, int]:
        return self._canvas_point(x * TILE_SIZE, y * TILE_SIZE)

    def _blit(self, image: pygame.Surface, map_position: tuple[int, int]) -> None:
        """Draw an image on the scene, at a position in map pixels."""
        self._scene.blit(
            image, (map_position[0] - self._scene_origin[0], map_position[1] - self._scene_origin[1])
        )

    def _object_draw(self, placed: Interactable) -> Draw:
        definition = self.world.definition_of(placed)
        sheet = self.assets.image(f"sprites/objects/{placed.kind}.png")
        # A sheet wider than the object holds animation frames side by side.
        width = definition.width * TILE_SIZE
        frame = int(self.time * ANIMATION_FPS) % self._frames(placed.kind, definition.width)
        image = sheet.subsurface((frame * width, 0, min(width, sheet.get_width()), sheet.get_height()))
        bottom = (placed.y + definition.height) * TILE_SIZE
        area = pygame.Rect((placed.x * TILE_SIZE, bottom - image.get_height()), image.get_size())

        goods = displayed_goods(self.world, placed) if definition.display_of is not None else []

        def draw() -> None:
            self._blit(image, area.topleft)
            for definition_id, (dx, dy) in zip(goods, SLOTS):
                self._blit(self.icons.small(definition_id), (area.left + dx, area.top + dy))
            if placed.object_id in self.world.containers:
                self.container_hitboxes[placed.object_id] = self._canvas_rect(area)

        return (bottom, 0, draw)

    def _resident_draw(self, resident: Resident) -> Draw:
        lying_in = self._lying_in(resident)
        if lying_in is not None:
            return self._lying_draw(resident, lying_in)
        x, y, facing, step = self._walk_state(resident)
        left, top = round(x * TILE_SIZE), round(y * TILE_SIZE)
        feet = (left + TILE_SIZE // 2, top + TILE_SIZE - 2)
        body = pygame.Rect(feet[0] - FRAME_SIZE[0] // 2, feet[1] - FRAME_SIZE[1], *FRAME_SIZE)

        load = self._load_of(resident)

        def draw() -> None:
            self._blit(self.characters.frame(resident.resident_id, facing, step), body.topleft)
            if load is not None:
                dx, dy = LOAD_OFFSETS[facing]
                self._blit(self.icons.small(load), (body.left + dx, body.top + dy))
            hitbox = self._canvas_rect(body)
            self.hitboxes[resident.resident_id] = hitbox
            self._overlays.append(lambda: self._draw_overhead(resident, hitbox.midtop, with_name=True))

        return (top + TILE_SIZE, 1, draw)

    def _marker_draw(self, resident: Resident) -> Draw:
        """From afar a resident is only their face, over the tile they are on, roof or no roof."""
        lying_in = self._lying_in(resident)
        if lying_in is not None:
            x, y = float(lying_in.x), float(lying_in.y)
        else:
            x, y, _, _ = self._walk_state(resident)
        face = self.faces.marker(resident.resident_id)
        hitbox = face.get_rect(center=self._canvas_point((x + 0.5) * TILE_SIZE, (y + 0.5) * TILE_SIZE))

        def overlay() -> None:
            self.canvas.blit(face, hitbox)
            self._draw_overhead(resident, hitbox.midtop, with_name=False, resting=lying_in is not None)

        def draw() -> None:
            self.hitboxes[resident.resident_id] = hitbox
            self._overlays.append(overlay)

        return ((y + 1) * TILE_SIZE, 1, draw)

    def _walk_state(self, resident: Resident) -> tuple[float, float, str, int]:
        """Position in tiles, facing and animation frame, part-way through the current minute."""
        trail = resident.trail
        if len(trail) < 2:
            return (resident.x, resident.y, resident.facing, 0)
        distance = min(self.tick_progress, 1.0) * (len(trail) - 1)
        index = min(int(distance), len(trail) - 2)
        fraction = distance - index
        (from_x, from_y), (to_x, to_y) = trail[index], trail[index + 1]
        if to_x != from_x:
            facing = "right" if to_x > from_x else "left"
        else:
            facing = "down" if to_y > from_y else "up"
        step = WALK_CYCLE[int(distance * 2) % len(WALK_CYCLE)]
        return (from_x + (to_x - from_x) * fraction, from_y + (to_y - from_y) * fraction, facing, step)

    def _lying_in(self, resident: Resident) -> Interactable | None:
        """The object a resident is lying in, if they are using one from on top of it."""
        activity = resident.activity
        if activity is None or not activity.using or activity.target_id is None:
            return None
        placed = self.world.interactables.get(activity.target_id)
        if placed is None:
            return None
        use = self.world.definition_of(placed).use
        return placed if use is not None and use.position == "on" else None

    def _lying_draw(self, resident: Resident, placed: Interactable) -> Draw:
        definition = self.world.definition_of(placed)
        bed = pygame.Rect(
            placed.x * TILE_SIZE, placed.y * TILE_SIZE, TILE_SIZE, definition.height * TILE_SIZE
        )
        frame = self.characters.frame(resident.resident_id, "down")
        head = frame.subsurface((0, 0, FRAME_SIZE[0], LYING_HEAD_ROWS))

        def draw() -> None:
            self._blit(head, (bed.left, bed.top + 1))
            hitbox = self._canvas_rect(bed)
            self.hitboxes[resident.resident_id] = hitbox
            self._overlays.append(
                lambda: self._draw_overhead(resident, hitbox.midtop, with_name=False, resting=True)
            )

        return (bed.bottom, 1, draw)

    def _status_icon(self, resident: Resident, resting: bool) -> str | None:
        """Icon for what a resident is doing, most urgent first."""
        if self._decision_of(resident.resident_id) is not None:
            return "alert"
        activity = resident.activity
        in_exchange = activity is not None and activity.using and activity.partner_id is not None
        if resident.resident_id in self.alerts:
            if in_exchange:
                return "alert"
            self.alerts.discard(resident.resident_id)
        if in_exchange:
            interaction = self.world.registries.interactions.get(activity.action)
            if interaction is not None and interaction.romance == "tryst":
                return "heart"
            return "argument" if interaction is not None and interaction.hostile else "chat"
        if resting:
            return "sleep"
        if resident.health < HURT_HEALTH:
            return "hurt"
        return "work" if activity is not None and activity.using and activity.action == WORK_ACTION else None

    def _bond_icon(self, resident: Resident) -> str | None:
        """What a resident is to whoever is selected: their partner, someone they hold as a friend, or neither."""
        selected = self.world.residents.get(self.hud.selected_id or "")
        if selected is None:
            return None
        if selected.couple_with == resident.resident_id:
            return "heart"
        feelings = self.world.relationships.get((selected.resident_id, resident.resident_id))
        return "friend" if feelings is not None and self.world.bonds.tier(self.world, feelings) is not None else None

    def _name_left(self, resident: Resident, centre_x: int, width: int) -> int:
        """Left edge of a name label. Two residents talking side by side push theirs apart."""
        activity = resident.activity
        partner = self.world.residents.get(activity.partner_id) if activity and activity.partner_id else None
        if partner is None or not activity.using or partner.y != resident.y:
            return centre_x - width // 2
        half_tile = self.tile_px // 2
        return centre_x + half_tile - 3 - width if partner.x > resident.x else centre_x - half_tile + 3

    def _load_of(self, resident: Resident) -> str | None:
        """Definition ID of what a resident is carrying for their job: goods that are nobody's yet."""
        return next((item.definition_id for item in resident.inventory.items if item.owner_id is None), None)

    def _item_in_hand(self, resident: Resident) -> str | None:
        """Definition ID of what a resident is eating or using right now."""
        activity = resident.activity
        if activity is None or not activity.using or activity.item_id is None:
            return None
        item = self.world.items.find_item(self.world, activity.item_id)
        if item is not None:
            # One thing in particular: what they are using, or having repaired.
            return item.definition_id
        if activity.action == USE_ITEM_ACTION:
            return None
        return activity.item_id if activity.target_id is not None and activity.partner_id is None else None

    def _draw_overhead(
        self, resident: Resident, top_centre: tuple[int, int], with_name: bool, resting: bool = False
    ) -> None:
        """Stack name, status icon and selection arrow above a resident."""
        x, y = top_centre
        if with_name:
            y -= CELL_SIZE[1]
            name = self.font.render(resident.name, PALETTE["paper"])
            self.canvas.blit(name, (self._name_left(resident, x, name.get_width()), y))
        icons = [self._status_icon(resident, resting)]
        if resident.resident_id == self.hud.selected_id:
            icons.append("selected")
        else:
            icons.append(self._bond_icon(resident))
        # From afar there is only room for what calls for attention.
        in_hand = None if self.overview else self._item_in_hand(resident)
        if in_hand is not None:
            image = self.icons.icon(in_hand)
            y -= image.get_height() + 1
            self.canvas.blit(image, (x - image.get_width() // 2, y))
        bob = int(self.time * ANIMATION_FPS) % 2
        for icon in icons:
            if icon is not None:
                y -= ICON_SIZE[1] + 1
                image = self.assets.image(icon_path(icon), size=ICON_SIZE)
                lift = bob if icon in BOBBING_ICONS else 0
                self.canvas.blit(image, (x - ICON_SIZE[0] // 2, y - lift))
