from collections.abc import Callable, Hashable, Iterable

import pygame

from graphics.assets import AssetStore
from graphics.character_renderer import FRAME_SIZE, CharacterRenderer
from graphics.face_renderer import FaceRenderer
from graphics.font import CELL_SIZE, BitmapFont
from graphics.icons import ICON_SIZE, icon_path
from graphics.item_icons import ItemIcons
from graphics.map_renderer import render_roofs, render_terrain, roof_names
from graphics.palette import PALETTE
from graphics.tileset import (
    ROOF_CELLS,
    ROOF_SHEET,
    ROOF_SHEET_SIZE,
    SETTLEMENT_CELLS,
    SETTLEMENT_SHEET,
    SETTLEMENT_SHEET_SIZE,
    Tileset,
)
from scenes.hud import LOG_INTENT, PAUSE_INTENT, Hud
from scenes.scene import canvas_position
from settings import SCALE, TILE_SIZE
from simulation.commands import SetPausedCommand, SetSpeedCommand
from simulation.events.event import DomainEvent
from simulation.items.item_system import USE_ITEM_ACTION
from simulation.work.work_system import WORK_ACTION
from simulation.residents.resident import Resident
from simulation.world import SimulationWorld
from world.interactable import Interactable

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
        elif event.type == pygame.KEYDOWN and event.key == pygame.K_c:
            self.centre_on_resident(self.hud.selected_id)
        elif event.type == pygame.KEYDOWN and event.key in ZOOM_KEYS:
            self.set_zoom(self.zoom + ZOOM_KEYS[event.key])
        elif event.type == pygame.MOUSEWHEEL:
            # The wheel zooms towards whatever is under the mouse, one step per notch.
            steps = (event.y > 0) - (event.y < 0)
            self.set_zoom(self.zoom + steps, canvas_position(pygame.mouse.get_pos()))
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            self.click(canvas_position(event.pos))
        elif event.type == pygame.MOUSEMOTION and event.buttons[RIGHT_MOUSE_BUTTON]:
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

    def click(self, position: tuple[int, int]) -> None:
        """Handle a left click at a canvas position: a button, a resident, or empty ground."""
        intent = self.hud.click(position)
        if intent is not None:
            self._apply(intent)
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
            self.hud.log_open = not self.hud.log_open
        elif isinstance(intent, tuple) and intent[0] == "speed":
            self.world.apply_command(SetSpeedCommand(intent[1]))
        elif isinstance(intent, tuple) and intent[0] == "zoom":
            self.set_zoom(self.zoom + intent[1])

    def render(self) -> None:
        self.canvas.fill(PALETTE["ink"])
        region = self._visible_region()
        self._scene = self._buffer(region.size)
        self._scene_origin = region.topleft
        self._scene.blit(self.roofed_terrain if self.overview else self.terrain, (0, 0), region)

        # Objects and residents share one list so that whatever stands lower on screen is in front.
        draws: list[Draw] = []
        for placed in self.world.interactables.values():
            # From afar a roof hides what is under it.
            if not (self.overview and (placed.x, placed.y) in self.roofs):
                draws.append(self._object_draw(placed))
        for resident in self.world.residents.values():
            draws.append(self._marker_draw(resident) if self.overview else self._resident_draw(resident))
        self.hitboxes = {}
        self.container_hitboxes = {}
        self._overlays = []
        for _, _, draw in sorted(draws, key=lambda entry: entry[:2]):
            draw()

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
        frames = max(1, sheet.get_width() // width)
        frame = int(self.time * ANIMATION_FPS) % frames
        image = sheet.subsurface((frame * width, 0, min(width, sheet.get_width()), sheet.get_height()))
        bottom = (placed.y + definition.height) * TILE_SIZE
        area = pygame.Rect((placed.x * TILE_SIZE, bottom - image.get_height()), image.get_size())

        def draw() -> None:
            self._blit(image, area.topleft)
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

        def draw() -> None:
            self._blit(self.characters.frame(resident.resident_id, facing, step), body.topleft)
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
            return "argument" if interaction is not None and interaction.hostile else "chat"
        if resting:
            return "sleep"
        if resident.health < HURT_HEALTH:
            return "hurt"
        return "work" if activity is not None and activity.using and activity.action == WORK_ACTION else None

    def _name_left(self, resident: Resident, centre_x: int, width: int) -> int:
        """Left edge of a name label. Two residents talking side by side push theirs apart."""
        activity = resident.activity
        partner = self.world.residents.get(activity.partner_id) if activity and activity.partner_id else None
        if partner is None or not activity.using or partner.y != resident.y:
            return centre_x - width // 2
        half_tile = self.tile_px // 2
        return centre_x + half_tile - 3 - width if partner.x > resident.x else centre_x - half_tile + 3

    def _item_in_hand(self, resident: Resident) -> str | None:
        """Definition ID of what a resident is eating or using right now."""
        activity = resident.activity
        if activity is None or not activity.using or activity.item_id is None:
            return None
        if activity.action == USE_ITEM_ACTION:
            item = self.world.items.find_item(self.world, activity.item_id)
            return item.definition_id if item is not None else None
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
