import math
from collections.abc import Callable, Hashable, Iterable

import pygame

from graphics.assets import AssetStore
from graphics.body_renderer import FRAME_ORIGIN, FRAME_SIZE, BodyRenderer
from graphics.building_art import BuildingArtStore
from graphics.building_renderer import FACADE_ROWS, BuildingRenderer, building_area
from graphics.doll import DOLL_FACINGS, Doll, DollStore, draw_doll
from graphics.face_renderer import FaceRenderer
from graphics.font import CELL_SIZE, BitmapFont
from graphics.icons import ICON_SIZE, icon_path
from graphics.illustrations import Illustrations
from graphics.item_icons import ItemIcons
from graphics.lighting import BLOCK, LightMap, daylight, shade
from graphics.object_sprites import ObjectSprites
from graphics.screen_layers import TRANSPARENT, ScreenLayers
from graphics.object_art import ObjectArtStore
from graphics.map_renderer import GROUND_TILES, render_roofs, render_terrain, roof_names
from graphics.palette import PALETTE
from graphics.shelf_display import SLOTS, displayed_goods
from graphics.tileset import (
    ROOF_CELLS,
    ROOF_SHEET,
    ROOF_SHEET_SIZE,
    SETTLEMENT_CELLS,
    SETTLEMENT_SHEET,
    SETTLEMENT_SHEET_SIZE,
    Tileset,
)
from scenes.body_stage import BodyStage, Remains, ground_spot
from audio.voice_player import VoicePlayer
from scenes.hud import (
    BUILD_INTENT,
    VOICE_INTENT,
    DRAW_INTENT,
    JOBS_INTENT,
    LOG_INTENT,
    MINIMAP_INTENT,
    PAUSE_INTENT,
    ROSTER_INTENT,
    SAVE_INTENT,
    STORES_INTENT,
    URBANISM_INTENT,
    Hud,
)
from scenes.scene import canvas_position
from settings import SCALE, TILE_SIZE
from simulation.commands import AcknowledgeTutorialCommand, SetPausedCommand, SetSpeedCommand, SuggestJobCommand
from simulation.events.event import DomainEvent
from simulation.items.item_system import USE_ITEM_ACTION
from simulation.work.work_system import WORK_ACTION
from simulation.residents.resident import Resident
from simulation.world import SimulationWorld
from skeleton.plan import IDLE_CLIP, builtin_plan
from skeleton.rig import Skeleton
from ui.bubble import MARK_SIZE, MARK_TAIL, draw_mark
from ui.labels import away_residents
from ui.minimap import TILE_PIXELS, draw_minimap, minimap_base, minimap_size, tile_at
from ui.panel import draw_panel
from ui.tutorial_panel import (
    ACKNOWLEDGE_INTENT,
    BUILDING_ART_FOCUS,
    CREATOR_INTENT,
    DOLL_FOCUS,
    owed_object,
)
from ui.tutorial_panel import DRAW_INTENT as TUTORIAL_DRAW_INTENT
from world.interactable import Interactable
from world.map import Tile
from world.room import Room

# Tiles walked in one turn of the walk clip: a step with each foot.
TILES_PER_STRIDE = 2
# What a body does besides standing and walking, and how many times a second its clip goes round.
WALK_CLIP = "walk"
WORK_CLIP = "work"
ARGUE_CLIP = "argue"
FIGHT_CLIP = "fight"
CARRY_CLIP = "carry"
EAT_CLIP = "eat"
CLIP_RATES = {WORK_CLIP: 1.0, ARGUE_CLIP: 1.2, FIGHT_CLIP: 1.5, EAT_CLIP: 1.15}
# The semantic anchors live in the body plan; these only place the mouth a little below and in
# front of the head joint for each view.
MOUTH_OFFSETS = {
    "down": (0, 2), "up": (0, 1), "right": (2, 2), "left": (-2, 2),
    "doll_right": (2, 2), "doll_left": (-2, 2),
}
# A portion of each eating cycle in which crumbs spring away from the bite.
BITE_START, BITE_END = 0.28, 0.62
CRUMB_OFFSETS = ((-3, -2), (2, -3), (4, 0), (-2, 2))
CRUMB_COLORS = ("sand", "glow", "lichen", "paper")
# Rows of a head left visible when a resident lies in a bed: hair and eyes above the blanket.
LYING_HEAD_ROWS = 10
# Where the corner of that head goes on the bed, so that it rests on the pillow.
LYING_HEAD_OFFSET = (1, -2)
# Frames per second of animated objects and bobbing icons.
ANIMATION_FPS = 5
BOBBING_ICONS = ("alert", "sleep")
# What someone is doing is shown in a bubble over their head. These are not: they mark who it is.
BARE_ICONS = ("selected", "heart", "friend")
# Health below which a resident is shown as hurt.
HURT_HEALTH = 70.0
# Where a load is drawn on a body frame, by the way the resident faces: in their arms, or on their back.
LOAD_OFFSETS = {"down": (4, 12), "up": (4, 10), "left": (0, 12), "right": (8, 12)}
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
# Canvas pixels the mouse must move with the left button held before it is pulling the map along
# and no longer clicking on it.
DRAG_START = 4
# How fast the view closes on whoever it follows: the share of the way left that it covers in a
# second, were it to keep its speed. Nearer than FOLLOW_SNAP map pixels, it is simply there.
FOLLOW_RATE = 8.0
FOLLOW_SNAP = 0.75
# Canvas pixels a tile takes at each zoom step, whole multiples of the art but for the first.
# The first is the overview: the settlement from afar, with the roofs on and a face for each resident.
ZOOM_TILE_SIZES = (TILE_SIZE // 2, TILE_SIZE, TILE_SIZE * 2, TILE_SIZE * 3)
DEFAULT_ZOOM = 1
# An illustrated ground is kept at this many of its pixels to a pixel of the map's own art, which
# is what the window shows at the default zoom.
GROUND_DETAIL = 2
ZOOM_KEYS = {
    pygame.K_PLUS: 1,
    pygame.K_KP_PLUS: 1,
    pygame.K_EQUALS: 1,
    pygame.K_MINUS: -1,
    pygame.K_KP_MINUS: -1,
}

Draw = tuple[float, int, Callable[[], None]]
# A paper doll to put on the window this frame: how far down the map it stands, the doll, and either
# the skeleton it is laid over or, for someone lying under a blanket, where their neck is.
DollDraw = tuple[float, Doll, Skeleton | None, tuple[float, float] | None]
# Which way a doll faces until its resident has walked to one side or the other.
DOLL_FACING = DOLL_FACINGS["right"]
HEAD_BONE = "skull"
# Where the neck of a doll lying in a bed is, from the bed's top left corner, in map pixels.
LYING_NECK = (7.5, 10.0)


class GlobalView:
    def __init__(
        self,
        canvas: pygame.Surface,
        world: SimulationWorld,
        assets: AssetStore,
        font: BitmapFont,
        icons: ItemIcons,
        faces: FaceRenderer,
        custom: AssetStore | None = None,
        illustrations: Illustrations | None = None,
        layers: ScreenLayers | None = None,
        dolls: DollStore | None = None,
        voices: VoicePlayer | None = None,
    ) -> None:
        self.canvas = canvas
        # What says out loud what is in the dock's bubble, if there are voices to say it with.
        self.voices = voices if voices is not None and voices.enabled else None
        self._spoken_seen: tuple[str, str] | None = None
        # Resident the player asked to give a voice to. The game shell picks it up.
        self.requested_voice: str | None = None
        # Residents whose body has been drawn are shown as paper dolls, on the window itself.
        self.dolls = dolls if layers is not None else None
        self._doll_facing: dict[str, str] = {}
        self._doll_draws: list[DollDraw] = []
        self._posed: dict[tuple, Skeleton] = {}
        # Resident the player asked to draw. The game shell picks it up.
        self.requested_editor: str | None = None
        # Building the player asked to draw. Kept separate from resident drawings.
        self.requested_building_editor: str | None = None
        # Item definition picked in a resident's or container's inventory.
        self.requested_item_editor: str | None = None
        # Infrastructure requests are picked up by the game shell after event handling.
        self.requested_save = False
        self.requested_urbanism = False
        # The opening of a new settlement asks for the screen where its first resident is made.
        self.requested_creator = False
        # Kind of object the player asked to draw.
        self.requested_object_editor: str | None = None
        # Pictures made outside the game, and where they are put to go straight on the window.
        self.illustrations = illustrations if layers is not None else None
        self.layers = layers
        self.world = world
        self.assets = assets
        self.font = font
        self.icons = icons
        self.object_sprites = ObjectSprites(assets, custom)
        # Furniture and objects somebody has drawn take the place of the game's own, kind by kind.
        self.object_art = ObjectArtStore(self.illustrations, self.object_sprites)
        self.faces = faces
        # Everyone's body, and what a blow leaves lying about. Presentation only: nothing of it is saved.
        self.bodies = BodyStage(BodyRenderer(assets, builtin_plan(), faces.looks))
        drawable = self.dolls is not None and illustrations is not None and illustrations.root is not None
        self.hud = Hud(canvas, world, font, icons, faces, assets, illustrations, layers, drawable, self.voices is not None)
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
        # What stands on the ground, without the ground: it goes over an illustrated one.
        self.raised_terrain = render_terrain(world.tile_map, tileset, without=GROUND_TILES)
        # The tiles that roofs cover, and the same terrain with those roofs on, which is what the minimap shows.
        self.roofs = roof_names(world.tile_map, world.rooms.values())
        roof_tiles = Tileset(self.assets.image(ROOF_SHEET, size=ROOF_SHEET_SIZE), ROOF_CELLS)
        self.roofed_terrain = render_roofs(self.terrain, self.roofs, roof_tiles)
        # On the map itself a building with its roof on is one picture, standing on the terrain.
        self.buildings = BuildingRenderer(assets, custom)
        self.building_art = BuildingArtStore(self.illustrations, self.buildings, world.tile_map)
        self.roof_tiles: dict[str, set[Tile]] = {
            room.room_id: set(roof_names(world.tile_map, [room])) for room in world.rooms.values() if room.roofed
        }
        # Whether buildings have their roof on from close. Off, every one of them stands open.
        self.roofs_on = True
        # Canvas position of the mouse, as far as the scene has been told.
        self.pointer: tuple[int, int] | None = None
        # Tiles under a roof that is on this frame: what stands there is not drawn.
        self._hidden: set[Tile] = set()
        # Buildings that stand closed this frame, by room ID.
        self._closed: set[str] = set()
        self.lights = LightMap()
        tiles = (world.tile_map.width, world.tile_map.height)
        self._minimap = minimap_base(self.roofed_terrain, tiles)
        width, height = minimap_size(tiles)
        # The part of the canvas that shows the map, and the map pixel at its top-left corner.
        self.viewport = self.hud.layout.map.copy()
        # The minimap keeps to the bottom left of the map, out of the way of what opens on the right.
        self._minimap_rect = pygame.Rect(
            self.viewport.left + MINIMAP_MARGIN, self.viewport.bottom - MINIMAP_MARGIN - height, width, height
        )
        self.hud.minimap_rect = self._minimap_rect
        self.camera = [0.0, 0.0]
        # Whoever the view keeps in its middle as they move: the resident last selected, until the
        # player moves the view by hand. `_selection_seen` is what tells a new selection from an old one.
        self.following: str | None = None
        self._selection_seen: str | None = None
        # Where on the canvas the left button went down on the map and where the mouse last was
        # with it held, and whether it has moved far enough since to be dragging.
        self._press: tuple[int, int] | None = None
        self._drag_last: tuple[int, int] | None = None
        self._dragging = False
        # Index into ZOOM_TILE_SIZES.
        self.zoom = DEFAULT_ZOOM
        # What is being drawn this frame: the visible part of the map at the size of its art, where
        # that part starts on the map, and what goes on top of it once it is on the canvas.
        self._scene = self.terrain
        self._scene_origin = (0, 0)
        self._overlays: list[Callable[[], None]] = []
        self._buffers: dict[tuple[tuple[int, int], bool], pygame.Surface] = {}
        commons = world.rooms.get("commons")
        entry = next(iter(world.entry_tiles()), None)
        if commons is not None:
            self.centre_on((commons.x + commons.width / 2, commons.y + commons.height / 2))
        elif entry is not None:
            # A map with no plaza is first seen from where people come in.
            self.centre_on((entry[0] + 0.5, entry[1] + 0.5))

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.KEYDOWN and event.key == pygame.K_l:
            self._apply(LOG_INTENT)
        elif event.type == pygame.KEYDOWN and event.key == pygame.K_j:
            self._apply(JOBS_INTENT)
        elif event.type == pygame.KEYDOWN and event.key == pygame.K_c:
            self.centre_on_resident(self.hud.selected_id)
            self.following = self.hud.selected_id
        elif event.type == pygame.KEYDOWN and event.key == pygame.K_g:
            self.jump_to_attention()
        elif event.type == pygame.KEYDOWN and event.key == pygame.K_t:
            self.roofs_on = not self.roofs_on
            self.hud.notify(ROOFS_ON if self.roofs_on else ROOFS_OFF)
        elif event.type == pygame.KEYDOWN and event.key == pygame.K_n:
            self._apply(MINIMAP_INTENT)
        elif event.type == pygame.KEYDOWN and event.key == pygame.K_u:
            self._apply(URBANISM_INTENT)
        elif event.type == pygame.KEYDOWN and event.key == pygame.K_F2:
            self._apply(DRAW_INTENT)
        elif event.type == pygame.KEYDOWN and event.key == pygame.K_F4:
            self._apply(BUILD_INTENT)
        elif event.type == pygame.KEYDOWN and event.key == pygame.K_F3:
            self._apply(VOICE_INTENT)
        elif event.type == pygame.KEYDOWN and event.key in ZOOM_KEYS:
            self.set_zoom(self.zoom + ZOOM_KEYS[event.key])
        elif event.type == pygame.MOUSEWHEEL:
            # The wheel zooms towards whatever is under the mouse, one step per notch.
            steps = (event.y > 0) - (event.y < 0)
            self.set_zoom(self.zoom + steps, canvas_position(pygame.mouse.get_pos()))
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            self.pointer = canvas_position(event.pos)
            if self._on_map(self.pointer):
                # On the map a press may be the start of a drag. It is a click once the button
                # comes up without the mouse having gone anywhere.
                self._press, self._drag_last, self._dragging = self.pointer, self.pointer, False
            else:
                self.click(self.pointer)
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            press, dragged = self._press, self._dragging
            self._press, self._drag_last, self._dragging = None, None, False
            if press is not None and not dragged:
                self.click(press)
        elif event.type == pygame.MOUSEMOTION:
            self.pointer = canvas_position(event.pos)
            if self._press is not None and self._drag_last is not None:
                if not self._dragging:
                    self._dragging = max(abs(self.pointer[axis] - self._press[axis]) for axis in (0, 1)) >= DRAG_START
                if self._dragging:
                    # Dragging pulls the map along with the mouse, from where it was pressed.
                    self.pan(self._drag_last[0] - self.pointer[0], self._drag_last[1] - self.pointer[1])
                    self._drag_last = self.pointer
            elif event.buttons[RIGHT_MOUSE_BUTTON]:
                # So does the right button, which clicks on nothing.
                self.pan(-event.rel[0] / SCALE, -event.rel[1] / SCALE)

    def update(self, dt: float) -> None:
        if not self.world.clock.paused:
            self.time += dt
            self.bodies.update(dt, self.world)
        self.hud.update(dt)
        pressed = pygame.key.get_pressed()
        for (dx, dy), keys in SCROLL_KEYS.items():
            if any(pressed[key] for key in keys):
                self.pan(dx * SCROLL_SPEED * dt, dy * SCROLL_SPEED * dt)
        self._follow(dt)
        self._voice_the_dock()

    def _voice_the_dock(self) -> None:
        """Have whoever starts a line in the dock say it out loud. A line that finds another being said goes unsaid."""
        spoken = self.hud.spoken
        if spoken != self._spoken_seen:
            self._spoken_seen = spoken
            if spoken is not None and self.voices is not None:
                self.voices.say(*spoken)

    def _follow(self, dt: float) -> None:
        """Keep whoever is selected in the middle of the view, catching up with them smoothly."""
        selected = self.hud.selected_id
        if selected != self._selection_seen:
            # Somebody else was just selected: the view goes with them from now on.
            self._selection_seen = self.following = selected
        resident = self.world.residents.get(self.following or "")
        if resident is None or resident.away:
            return
        x, y, _, _ = self._walk_state(resident)
        target = ((x + 0.5) * TILE_SIZE, (y + 0.5) * TILE_SIZE)
        for axis in (0, 1):
            wanted = target[axis] - self.viewport.size[axis] / 2 * TILE_SIZE / self.tile_px
            gap = wanted - self.camera[axis]
            share = 1.0 if abs(gap) <= FOLLOW_SNAP else min(1.0, FOLLOW_RATE * dt)
            self.camera[axis] += gap * share
        self.scroll(0, 0)

    def _on_map(self, position: tuple[int, int]) -> bool:
        """Whether a canvas position is on the map itself, with nothing of the HUD over it."""
        return self.viewport.collidepoint(position) and not self.hud.covers(position) and self.hud.click(position) is None

    def pan(self, dx: float, dy: float) -> None:
        """Move the view by hand, by a distance in canvas pixels. It lets go of whoever it was following."""
        self.following = None
        self.scroll(dx, dy)

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
        self.bodies.on_events(self.world, events)
        for event in events:
            if event.importance >= self.hud.intervention_from:
                self.alerts.update(event.participants)
        # Someone asking for advice may be off screen: bring them into view, unless the view is
        # with somebody the player chose to follow. The notice at the top says who is waiting.
        for decision in self.world.decisions.values():
            if self.following is None and any(decision.resident_id in event.participants for event in events):
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

    def click(self, position: tuple[int, int]) -> None:
        """Handle a left click at a canvas position: a button, the minimap, a resident, or empty ground."""
        intent = self.hud.click(position)
        minimap = self.hud.minimap_rect
        if intent is not None:
            self._apply(intent)
        elif minimap is not None and minimap.collidepoint(position):
            self.following = None
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
        elif intent == STORES_INTENT:
            self.hud.toggle_stores()
        elif intent == SAVE_INTENT:
            self.requested_save = True
        elif intent == URBANISM_INTENT:
            self.requested_urbanism = True
        elif intent == CREATOR_INTENT:
            self.requested_creator = True
        elif intent == TUTORIAL_DRAW_INTENT:
            self._draw_for_the_step()
        elif intent == ACKNOWLEDGE_INTENT:
            self.world.apply_command(AcknowledgeTutorialCommand())
        elif intent == DRAW_INTENT and self.dolls is not None:
            # Whoever is selected, or else the first resident there is.
            self.requested_editor = self.hud.selected_id or next(iter(self.world.residents), None)
        elif intent == BUILD_INTENT and self.illustrations is not None and self.illustrations.root is not None:
            self.requested_building_editor = self._building_to_draw()
        elif intent == VOICE_INTENT and self.voices is not None:
            self.requested_voice = self.hud.selected_id or next(iter(self.world.residents), None)
        elif intent == ROSTER_INTENT:
            # Nobody in particular: the panel goes back to listing everybody.
            self.hud.select_resident(None)
        elif intent == MINIMAP_INTENT:
            self.hud.minimap_rect = None if self.hud.minimap_rect is not None else self._minimap_rect
            self.hud.notify(MINIMAP_ON if self.hud.minimap_rect is not None else MINIMAP_OFF)
        elif isinstance(intent, tuple) and intent[0] == "select":
            self.hud.select_resident(intent[1])
            self.centre_on_resident(intent[1])
            decision = self._decision_of(intent[1])
            if decision is not None:
                self.requested_decision = decision
        elif isinstance(intent, tuple) and intent[0] == "edit_item":
            self.requested_item_editor = intent[1]
        elif isinstance(intent, tuple) and intent[0] == "suggest":
            self._suggest_job(intent[1])
        elif isinstance(intent, tuple) and intent[0] == "speed":
            self.world.apply_command(SetSpeedCommand(intent[1]))
        elif isinstance(intent, tuple) and intent[0] == "zoom":
            self.set_zoom(self.zoom + intent[1])

    def _draw_for_the_step(self) -> None:
        """Ask for the drawing the step of the opening in hand wants: of someone, of a building or of an object."""
        step = self.world.guide.current(self.world)
        if step is None:
            return
        if step.focus == DOLL_FOCUS:
            self.requested_editor = self.hud.selected_id or next(iter(self.world.residents), None)
        elif step.focus == BUILDING_ART_FOCUS:
            self.requested_building_editor = self._building_to_draw()
        else:
            self.requested_object_editor = owed_object(self.world)

    def _building_to_draw(self) -> str | None:
        """The roofed building currently in context, or the first one on the map."""
        candidates: list[tuple[int, int]] = []
        selected = self.world.residents.get(self.hud.selected_id or "")
        if selected is not None and not selected.away:
            candidates.append(selected.tile)
        if self.pointer is not None and self.viewport.collidepoint(self.pointer):
            x, y = self._map_point(self.pointer)
            candidates.append((int(x // TILE_SIZE), int(y // TILE_SIZE)))
        roofed = [room for room in self.world.rooms.values() if room.roofed]
        for tile in candidates:
            for room in roofed:
                if self._is_at(room.room_id, tile):
                    return room.room_id
        return roofed[0].room_id if roofed else None

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
        if self.layers is not None:
            self.layers.clear()
        self.canvas.fill(PALETTE["ink"])
        region = self._visible_region()
        ground = self._ground()
        # Decide the state of buildings before making the scene: a freehand building needs an
        # alpha-capable buffer even when nobody has drawn the ground below it.
        open_rooms = self.looked_into()
        self._closed = set(self.roof_tiles) - open_rooms
        # A roof hides what is under it.
        self._hidden = set().union(*(self.roof_tiles[room_id] for room_id in self._closed))
        drawn_objects = self._drawn_objects(region)
        closed_pictures = {
            room_id: self.building_art.closed(self.world.rooms[room_id]) for room_id in self._closed
        }
        open_backgrounds = {
            room_id: self.building_art.opened(self.world.rooms[room_id], foreground=False) for room_id in open_rooms
        }
        open_foregrounds = {
            room_id: self.building_art.opened(self.world.rooms[room_id], foreground=True) for room_id in open_rooms
        }
        has_building_pictures = any(
            (*closed_pictures.values(), *open_backgrounds.values(), *open_foregrounds.values())
        )
        self._scene = self._buffer(
            region.size, clear=ground is not None or has_building_pictures or bool(drawn_objects)
        )
        self._scene_origin = region.topleft
        if ground is None:
            self._scene.blit(self.terrain, (0, 0), region)
        else:
            self._scene.fill(TRANSPARENT)
            self._scene.blit(self.raised_terrain, (0, 0), region)
        # Freehand parts go straight on the window: backgrounds below the old map art, foregrounds
        # after residents, so the front wall and door can hide their feet.
        pictures: list[tuple[pygame.Rect, pygame.Surface]] = []
        foreground_pictures: list[tuple[pygame.Rect, pygame.Surface]] = []
        # Objects, residents and buildings share one list so that whatever stands lower on screen is in front.
        draws: list[Draw] = []
        for room_id in self._closed:
            room = self.world.rooms[room_id]
            if not building_area(room).colliderect(region):
                continue
            picture = closed_pictures[room_id]
            if picture is not None:
                pictures.append((building_area(room), picture))
            else:
                draws.append(self._building_draw(room))
        for room_id in open_rooms:
            room = self.world.rooms[room_id]
            area = building_area(room)
            if not area.colliderect(region):
                continue
            background = open_backgrounds[room_id]
            foreground = open_foregrounds[room_id]
            if background is not None:
                pictures.append((area, background))
            if foreground is not None:
                foreground_pictures.append((area, foreground))
        # Drawn furniture goes over the floor of a drawn building, whatever stands lower in front.
        pictures.extend(sorted(drawn_objects, key=lambda entry: entry[0].bottom))
        for area, picture in pictures:
            # Remove only where a drawing has paint. Clear corners continue to show the ground.
            self._erase_for_picture(area, picture)
        for placed in self.world.interactables.values():
            if (placed.x, placed.y) not in self._hidden:
                draws.append(self._object_draw(placed))
        for resident in self.world.residents.values():
            if resident.away:
                # Whoever is outside the settlement is nowhere on its map.
                continue
            # Someone under a roof is still found: their face is shown on it, as from afar.
            unseen = self.overview or resident.tile in self._hidden
            draws.append(self._marker_draw(resident) if unseen else self._resident_draw(resident))
        for remains in self.bodies.remains:
            # The dead are not picked out from afar, and a roof hides them like anything else.
            if not self.overview and remains.tile not in self._hidden:
                draws.append(self._remains_draw(remains))
        self.hitboxes = {}
        self.container_hitboxes = {}
        self._overlays = []
        self._doll_draws = []
        for _, _, draw in sorted(draws, key=lambda entry: entry[:2]):
            draw()
        stormy = self._storm(region)
        light = self._light(region)

        # Nothing of the map is drawn outside its part of the canvas.
        self.canvas.set_clip(self.viewport)
        size = (self._scaled(region.width), self._scaled(region.height))
        if ground is not None or self._doll_draws or pictures or foreground_pictures:
            self._show_illustrated(region, size, ground, pictures, foreground_pictures, stormy, light)
        else:
            if stormy:
                self._scene.fill(STORM_TINT, special_flags=pygame.BLEND_RGB_MULT)
            if light is not None:
                shade(self._scene, light)
            scene = self._scene
            if size != region.size:
                scene = pygame.transform.scale(scene, size, self._buffer(size))
            self.canvas.blit(scene, self._canvas_point(*region.topleft))
        # Names, icons and faces go straight on the canvas, so they keep their size at any zoom.
        self._draw_zone_names()
        for overlay in self._overlays:
            overlay()
        self.canvas.set_clip(None)

        self.hud.render()
        self._draw_minimap(region)
        self._draw_away()

    def _draw_zone_names(self) -> None:
        """A sign over each named place, on the wall at its back, so that the map can be read."""
        for room in self.world.rooms.values():
            name = room.name.upper()
            width = self.font.width(name) + 6
            height = CELL_SIZE[1] + 2
            if room.room_id in self._closed:
                # On a building that stands closed, the sign sits on the eave, over its front.
                row = room.y + room.height + 1 - FACADE_ROWS
                centre_x, top = self._canvas_point((room.x + room.width / 2) * TILE_SIZE, row * TILE_SIZE)
                top -= height + 1
            else:
                centre_x, top = self._canvas_point((room.x + room.width / 2) * TILE_SIZE, (room.y - 1) * TILE_SIZE)
            sign = pygame.Rect(centre_x - width // 2, top + 1, width, height)
            if not self.viewport.colliderect(sign):
                continue
            draw_panel(self.canvas, sign, fill="ink", border="copper")
            self.font.draw(self.canvas, name, (sign.x + 3, sign.y + 1), PALETTE["sand"])

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
        panel = pygame.Rect(self.viewport.left + MINIMAP_MARGIN, top, width + 4, face.get_height() + 4)
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

    def _ground(self) -> pygame.Surface | None:
        """The ground of this map as someone has drawn it, at the detail the window shows. None if nobody has."""
        if self.illustrations is None:
            return None
        width, height = self.terrain.get_size()
        return self.illustrations.fitted(f"map/{self.world.map_id}.png", (width * GROUND_DETAIL, height * GROUND_DETAIL))

    def _show_illustrated(
        self,
        region: pygame.Rect,
        size: tuple[int, int],
        ground: pygame.Surface | None,
        pictures: list[tuple[pygame.Rect, pygame.Surface]],
        foreground_pictures: list[tuple[pygame.Rect, pygame.Surface]],
        stormy: bool,
        light: pygame.Surface | None,
    ) -> None:
        """Have the map drawn on the window itself: the illustrated ground if there is one, everything
        that stands on it, and then the paper dolls, at the full resolution of the window.

        The canvas is left clear over the map, so that only names, bubbles and signs are drawn there.
        """
        layers, scene = self.layers, self._scene
        plan = self.bodies.plan
        # Whoever stands lower on the map is in front.
        dolls = sorted(self._doll_draws, key=lambda entry: entry[0])
        corner = self._canvas_point(*region.topleft)
        place = layers.on_screen(pygame.Rect(corner, size))
        clip = layers.on_screen(self.viewport)
        # Window pixels to a pixel of the map's art.
        detail = place.width / region.width
        source = pygame.Rect(
            region.x * GROUND_DETAIL, region.y * GROUND_DETAIL, region.width * GROUND_DETAIL, region.height * GROUND_DETAIL
        )

        def draw(screen: pygame.Surface) -> None:
            before = screen.get_clip()
            screen.set_clip(clip)
            if ground is not None:
                piece = ground.subsurface(source)
                screen.blit(piece if piece.get_size() == place.size else pygame.transform.smoothscale(piece, place.size), place)
            for area, picture in pictures:
                spot = pygame.Rect(
                    place.x + round((area.x - region.x) * detail),
                    place.y + round((area.y - region.y) * detail),
                    round(area.width * detail),
                    round(area.height * detail),
                )
                fitted = (
                    picture
                    if picture.get_size() == spot.size
                    else pygame.transform.smoothscale(picture, spot.size)
                )
                screen.blit(fitted, spot)
            # The pixel art keeps its hard edges however large it is shown.
            screen.blit(scene if scene.get_size() == place.size else pygame.transform.scale(scene, place.size), place)
            origin = (place.x - region.x * detail, place.y - region.y * detail)
            for _, doll, skeleton, neck in dolls:
                if skeleton is not None:
                    draw_doll(screen, doll, plan, skeleton, origin, detail)
                    continue
                # Lying under a blanket: only the head, upright on the pillow.
                head = doll.placed(HEAD_BONE, False, detail, math.pi)
                if head is not None:
                    image, joint = head
                    screen.blit(image, (round(origin[0] + neck[0] * detail - joint[0]), round(origin[1] + neck[1] * detail - joint[1])))
            for area, picture in foreground_pictures:
                spot = pygame.Rect(
                    place.x + round((area.x - region.x) * detail),
                    place.y + round((area.y - region.y) * detail),
                    round(area.width * detail),
                    round(area.height * detail),
                )
                fitted = (
                    picture
                    if picture.get_size() == spot.size
                    else pygame.transform.smoothscale(picture, spot.size)
                )
                screen.blit(fitted, spot)
            if stormy:
                screen.fill(STORM_TINT, place, special_flags=pygame.BLEND_RGB_MULT)
            if light is not None:
                screen.blit(pygame.transform.scale(light, place.size), place, special_flags=pygame.BLEND_RGB_MULT)
            screen.set_clip(before)

        layers.under(draw)
        self.canvas.fill(TRANSPARENT, self.viewport)

    def _erase_for_picture(self, area: pygame.Rect, picture: pygame.Surface) -> None:
        """Make the scene clear under the painted pixels of a window-resolution picture."""
        local = area.move(-self._scene_origin[0], -self._scene_origin[1])
        clipped = local.clip(self._scene.get_rect())
        if clipped.width <= 0 or clipped.height <= 0:
            return
        # Work at map-art resolution. A hard alpha edge is deliberate: the high-resolution source
        # itself is what supplies the smooth edge on the window.
        small = pygame.transform.scale(picture, area.size)
        source = pygame.Rect(clipped.x - local.x, clipped.y - local.y, clipped.width, clipped.height)
        mask = pygame.mask.from_surface(small.subsurface(source))
        eraser = mask.to_surface(setcolor=(0, 0, 0, 255), unsetcolor=(0, 0, 0, 0))
        self._scene.blit(eraser, clipped, special_flags=pygame.BLEND_RGBA_SUB)

    def _storm(self, region: pygame.Rect) -> bool:
        """Under bad weather, blow streaks of dust across the scene. Returns whether there is a storm to tint it."""
        if not self.world.happenings.is_stormy(self.world):
            return False
        drift = int(self.time * STORM_SPEED)
        for index in range(STORM_STREAKS):
            # Each streak keeps its own height and length, and they all move with the wind.
            x = (index * 97 + drift * (1 + index % 3)) % (region.width + 16) - 16
            y = (index * 53 + index * index * 7) % max(1, region.height)
            pygame.draw.line(self._scene, PALETTE["sand"], (x, y), (x + 4 + index % 5, y))
        return True

    def _light(self, region: pygame.Rect) -> pygame.Surface | None:
        """What darkens the scene by the hour, with a pool of light round every fire and lamp in sight. None by day."""
        level = daylight(self.world.clock.hour, self.world.clock.minute)
        if level >= 1.0:
            return None
        flicker = int(self.time * ANIMATION_FPS) % 2
        lights = []
        for placed in self.world.interactables.values():
            definition = self.world.definition_of(placed)
            # A lamp with the power out is as dark on screen as it is for whoever stands by it.
            reach = self.world.light_of(placed)
            if reach <= 0 or (placed.x, placed.y) in self._hidden:
                continue
            centre = (
                round((placed.x + definition.width / 2) * TILE_SIZE) - region.x,
                round((placed.y + definition.height / 2) * TILE_SIZE) - region.y,
            )
            # A flame wavers; a lamp burns steady.
            wavers = self.object_sprites.frames(definition) > 1
            lights.append((centre, reach * TILE_SIZE - (BLOCK * flicker if wavers else 0)))
        return self.lights.render(region.size, level, lights)

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

    def _buffer(self, size: tuple[int, int], clear: bool = False) -> pygame.Surface:
        """A surface of this size to draw a frame on, kept from one frame to the next.

        A `clear` one can be left empty where nothing is drawn, to go over something else.
        """
        key = (size, clear)
        if key not in self._buffers:
            self._buffers[key] = pygame.Surface(size, pygame.SRCALPHA) if clear else pygame.Surface(size)
        return self._buffers[key]

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

    def _object_area(self, placed: Interactable) -> pygame.Rect:
        """Where an object is drawn, in map pixels: on its tiles, and as far above them as it rises."""
        width, height = self.object_art.frame_size(self.world.definition_of(placed))
        bottom = (placed.y + self.world.definition_of(placed).height) * TILE_SIZE
        return pygame.Rect(placed.x * TILE_SIZE, bottom - height, width, height)

    def _drawn_objects(self, region: pygame.Rect) -> list[tuple[pygame.Rect, pygame.Surface]]:
        """The objects in view that somebody has drawn, each with its picture at the size the window shows it."""
        if not self.object_art.available or self.layers is None:
            return []
        drawn: list[tuple[pygame.Rect, pygame.Surface]] = []
        scale = self.layers.scale
        for placed in self.world.interactables.values():
            if (placed.x, placed.y) in self._hidden:
                continue
            area = self._object_area(placed)
            if not area.colliderect(region):
                continue
            size = (self._scaled(area.width) * scale, self._scaled(area.height) * scale)
            picture = self.object_art.shown(self.world.definition_of(placed), size)
            if picture is not None:
                drawn.append((area, picture))
        return drawn

    def _object_draw(self, placed: Interactable) -> Draw:
        definition = self.world.definition_of(placed)
        sheet = self.object_sprites.sheet(definition)
        # Somebody's drawing of it goes on the window by itself: here only what sits on it is drawn.
        drawn = self.layers is not None and self.object_art.drawing(definition) is not None
        # A sheet wider than the object holds animation frames side by side.
        width = definition.width * TILE_SIZE
        frame = int(self.time * ANIMATION_FPS) % self.object_sprites.frames(definition)
        image = sheet.subsurface((frame * width, 0, min(width, sheet.get_width()), sheet.get_height()))
        bottom = (placed.y + definition.height) * TILE_SIZE
        area = pygame.Rect((placed.x * TILE_SIZE, bottom - image.get_height()), image.get_size())

        goods = displayed_goods(self.world, placed) if definition.display_of is not None else []

        def draw() -> None:
            if not drawn:
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
        x, y, facing, stride = self._walk_state(resident)
        doll = self._doll_of(resident.resident_id)
        if doll is not None:
            facing = self._side_facing(resident.resident_id, facing)
        top = round(y * TILE_SIZE)
        spot = ground_spot(x, y)
        # Where a body stands at rest, which is what is picked with the mouse whatever it is doing.
        body = pygame.Rect(spot[0] - FRAME_ORIGIN[0], spot[1] - FRAME_ORIGIN[1], *FRAME_SIZE)
        if doll is not None:
            # A doll is as tall and as wide as it was drawn: its name goes over its own head.
            left, high, right, low = doll.standing(self.bodies.plan)
            body = pygame.Rect(
                spot[0] + math.floor(left), spot[1] + math.floor(high), math.ceil(right - left), math.ceil(low) - math.floor(high)
            )

        load = self._load_of(resident)
        overlay = CARRY_CLIP if load is not None else None
        clip = WALK_CLIP if stride is not None else self._clip_of(resident)
        renderer = self.bodies.renderer
        frames = renderer.frames(clip, facing)
        turn = stride if stride is not None else self.time * CLIP_RATES.get(clip, 0.0)
        index = int(turn * frames) % frames
        character = self.bodies.character(resident)
        # A doll turns smoothly; the game's own bodies go from one kept picture to the next.
        character.stand(spot[0], spot[1], facing, clip, turn % 1.0 if doll is not None else index / frames, overlay)

        def draw() -> None:
            if doll is not None:
                skeleton = character.skeleton if character.physical else self._posed_skeleton(resident.resident_id, character)
                self._doll_draws.append((spot[1], doll, skeleton, None))
            elif character.physical:
                # Reeling from a blow or knocked down: drawn joint by joint, wherever physics has them.
                renderer.draw_limp(
                    self._scene, character.skeleton, resident.resident_id, (-self._scene_origin[0], -self._scene_origin[1])
                )
            else:
                picture, origin = renderer.frame(
                    resident.resident_id, facing, clip, index, tuple(character.lost), overlay
                )
                self._blit(picture, (spot[0] - origin[0], spot[1] - origin[1]))
            if load is not None and doll is None:
                dx, dy = LOAD_OFFSETS[facing]
                self._blit(self.icons.small(load), (body.left + dx, body.top + dy))
            hitbox = self._canvas_rect(body)
            self.hitboxes[resident.resident_id] = hitbox
            meal = self._meal_in_hand(resident)
            if meal is not None and not character.physical:
                pose, phase = character.pose(), turn % 1.0
                self._overlays.append(
                    lambda: self._draw_meal(meal, facing, pose, phase)
                )
            self._overlays.append(lambda: self._draw_overhead(resident, hitbox.midtop, with_name=True))

        return (top + TILE_SIZE, 1, draw)

    def _building_draw(self, room: Room) -> Draw:
        """A building with its roof on. Whatever stands behind it is hidden by as much as it rises."""
        area = building_area(room)
        picture = self.buildings.picture(room)

        def draw() -> None:
            self._blit(picture, area.topleft)

        return (area.bottom, 0, draw)

    def _doll_of(self, body_id: str) -> Doll | None:
        """The paper doll of a body, if its body has been drawn and there is a window to show it on."""
        return self.dolls.get(body_id) if self.dolls is not None else None

    def _side_facing(self, resident_id: str, facing: str) -> str:
        """Which way a doll faces: it is drawn from the side, so walking up or down it keeps the side it last had."""
        if facing in DOLL_FACINGS:
            self._doll_facing[resident_id] = DOLL_FACINGS[facing]
        return self._doll_facing.get(resident_id, DOLL_FACING)

    def _posed_skeleton(self, resident_id: str, character) -> Skeleton:
        """A skeleton standing as a resident's clips have them right now, to lay their doll over."""
        key = (resident_id, character.facing, tuple(character.lost))
        if key not in self._posed:
            self._posed[key] = Skeleton(self.bodies.plan, character.facing, character.lost)
        skeleton = self._posed[key]
        pose = self.bodies.plan.pose(character.facing, character.clip, character.phase, character.overlay)
        skeleton.set_pose(pose, character.x, character.y)
        return skeleton

    def _remains_draw(self, remains: Remains) -> Draw:
        """A dead body or a part of one, in among the living by how far down the map it lies."""
        doll = self._doll_of(remains.body_id)

        def draw() -> None:
            if doll is not None:
                self._doll_draws.append((remains.skeleton.ground, doll, remains.skeleton, None))
                return
            self.bodies.draw_remains(self._scene, remains, self._scene_origin)

        return (remains.skeleton.ground, 1, draw)

    def _clip_of(self, resident: Resident) -> str:
        """What the body of someone standing still is doing."""
        activity = resident.activity
        if activity is None or not activity.using:
            return IDLE_CLIP
        if activity.partner_id is not None:
            interaction = self.world.registries.interactions.get(activity.action)
            if interaction is None or not interaction.hostile:
                return IDLE_CLIP
            return FIGHT_CLIP if interaction.damage is not None else ARGUE_CLIP
        if activity.action == EAT_CLIP:
            return EAT_CLIP
        return WORK_CLIP if activity.action == WORK_ACTION else IDLE_CLIP

    def _meal_in_hand(self, resident: Resident) -> str | None:
        """Definition ID of the food in a resident's hand during an active meal."""
        activity = resident.activity
        if activity is None or activity.action != EAT_CLIP:
            return None
        return self._item_in_hand(resident)

    def _draw_meal(self, item_id: str, facing: str, pose: dict[str, tuple[float, float]], phase: float) -> None:
        """Draw food at the body-plan hand anchor and crumbs at its mouth during a bite."""
        plan = self.bodies.plan
        hand = plan.anchor("held_item", facing, pose)
        mouth = plan.anchor("mouth", facing, pose)
        if hand is None or mouth is None:
            return
        mouth_offset = MOUTH_OFFSETS.get(facing, (0, 2))
        mouth = (mouth[0] + mouth_offset[0], mouth[1] + mouth_offset[1])
        hand_on_canvas = self._canvas_point(*hand)
        size = max(3, self._scaled(self.icons.small(item_id).get_width()))
        icon = self.icons.small(item_id)
        if icon.get_size() != (size, size):
            icon = pygame.transform.scale(icon, (size, size))
        self.canvas.blit(icon, icon.get_rect(center=hand_on_canvas))

        if not BITE_START <= phase <= BITE_END:
            return
        bite = (phase - BITE_START) / (BITE_END - BITE_START)
        spread = math.sin(math.pi * bite)
        fall = bite * 2.0
        mouth_on_canvas = self._canvas_point(*mouth)
        crumb_size = max(1, self.tile_px // TILE_SIZE)
        zoom = self.tile_px / TILE_SIZE
        for (dx, dy), color in zip(CRUMB_OFFSETS, CRUMB_COLORS):
            x = mouth_on_canvas[0] + round(dx * spread * zoom)
            y = mouth_on_canvas[1] + round((dy * spread + fall) * zoom)
            pygame.draw.rect(self.canvas, PALETTE[color], (x, y, crumb_size, crumb_size))

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

    def _walk_state(self, resident: Resident) -> tuple[float, float, str, float | None]:
        """Position in tiles, facing and how far into a stride, part-way through the current minute.

        The stride goes from 0 to 1 over a step with each foot. It is None for someone standing still.
        """
        trail = resident.trail
        if len(trail) < 2:
            return (resident.x, resident.y, resident.facing, None)
        distance = min(self.tick_progress, 1.0) * (len(trail) - 1)
        index = min(int(distance), len(trail) - 2)
        fraction = distance - index
        (from_x, from_y), (to_x, to_y) = trail[index], trail[index + 1]
        if to_x != from_x:
            facing = "right" if to_x > from_x else "left"
        else:
            facing = "down" if to_y > from_y else "up"
        stride = distance / TILES_PER_STRIDE % 1.0
        return (from_x + (to_x - from_x) * fraction, from_y + (to_y - from_y) * fraction, facing, stride)

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
        face = self.bodies.renderer.head(resident.resident_id)
        head = face.subsurface((0, 0, face.get_width(), LYING_HEAD_ROWS))

        doll = self._doll_of(resident.resident_id)

        def draw() -> None:
            if doll is not None:
                self._doll_draws.append((bed.bottom, doll, None, (bed.left + LYING_NECK[0], bed.top + LYING_NECK[1])))
            else:
                self._blit(head, (bed.left + LYING_HEAD_OFFSET[0], bed.top + LYING_HEAD_OFFSET[1]))
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
        # Meals are visible in the hand itself; the overhead item remains for other item uses.
        in_hand = None if self.overview or self._meal_in_hand(resident) is not None else self._item_in_hand(resident)
        if in_hand is not None:
            image = self.icons.icon(in_hand)
            y -= image.get_height() + 1
            self.canvas.blit(image, (x - image.get_width() // 2, y))
        bob = int(self.time * ANIMATION_FPS) % 2
        for icon in icons:
            if icon is None:
                continue
            image = self.assets.image(icon_path(icon), size=ICON_SIZE)
            lift = bob if icon in BOBBING_ICONS else 0
            if icon in BARE_ICONS:
                y -= ICON_SIZE[1] + 1
                self.canvas.blit(image, (x - ICON_SIZE[0] // 2, y - lift))
            else:
                # What they are doing, in a bubble that points at them.
                y -= MARK_SIZE[1] + MARK_TAIL + 1
                draw_mark(self.canvas, image, (x, y - lift))
