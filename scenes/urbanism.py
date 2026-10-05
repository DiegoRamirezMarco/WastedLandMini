"""Settlement layout editor. Input becomes simulation commands; pygame owns only the UI."""

from __future__ import annotations

from collections.abc import Hashable

import pygame

from graphics.assets import AssetStore
from graphics.font import LINE_HEIGHT, BitmapFont
from graphics.object_sprites import ObjectSprites
from graphics.palette import PALETTE
from graphics.screen_layers import ScreenLayers
from scenes.scene import canvas_position
from simulation.commands import (
    MoveBuildingCommand,
    MoveObjectCommand,
    PlaceBuildingCommand,
    PlaceObjectCommand,
    RemoveBuildingCommand,
    RemoveObjectCommand,
)
from simulation.world import SimulationWorld
from ui.button import Button
from ui.panel import draw_panel
from world.room import Room
from world.urbanism import UrbanismResult

PANEL_WIDTH = 218
MARGIN = 8
CATALOG_TOP = 58
CATALOG_BOTTOM = 326
ROW_HEIGHT = 14
CATEGORY_LABELS = {
    "buildings": "Edificios",
    "furniture": "Muebles",
    "decor": "Decorado",
}
TERRAIN_COLORS = {
    "dirt": "earth",
    "grass": "moss",
    "soil": "earth_dark",
    "floor_wood": "copper",
    "floor_concrete": "stone",
    "wall": "iron",
    "door": "sand",
    "fence": "rust",
    "gate": "ochre",
}

Selection = tuple[str, str]


class UrbanismEditor:
    def __init__(
        self,
        canvas: pygame.Surface,
        world: SimulationWorld,
        font: BitmapFont,
        assets: AssetStore,
        custom: AssetStore | None = None,
        layers: ScreenLayers | None = None,
    ) -> None:
        self.canvas = canvas
        self.world = world
        self.font = font
        self.layers = layers
        self.sprites = ObjectSprites(assets, custom)
        self.closed = False
        self.category = "buildings"
        self.catalog_id: str | None = next(iter(world.registries.buildings), None)
        self.tool = "place"
        self.selection: Selection | None = None
        self.confirm_delete = False
        self.message = "Elige algo del catálogo y colócalo en el mapa"
        self.pointer_tile: tuple[int, int] | None = None
        self.catalog_offset = 0
        self.requested_art_room: str | None = None
        self._layout()

    def _layout(self) -> None:
        width, height = self.canvas.get_size()
        available_width = width - PANEL_WIDTH - MARGIN * 2
        available_height = height - 74
        self.tile_px = max(
            4,
            min(
                available_width // max(1, self.world.tile_map.width),
                available_height // max(1, self.world.tile_map.height),
            ),
        )
        map_size = (
            self.world.tile_map.width * self.tile_px,
            self.world.tile_map.height * self.tile_px,
        )
        self.map_rect = pygame.Rect(
            PANEL_WIDTH + (width - PANEL_WIDTH - map_size[0]) // 2,
            48 + max(0, (available_height - map_size[1]) // 2),
            *map_size,
        )
        x = MARGIN
        self.category_buttons: list[Button] = []
        for category, label in CATEGORY_LABELS.items():
            button = Button.at(self.font, x, 31, label, ("category", category))
            self.category_buttons.append(button)
            x = button.rect.right + 3
        self.select_button = Button.at(self.font, PANEL_WIDTH + MARGIN, 8, "Seleccionar", ("tool", "select"))
        self.close_button = Button.at(self.font, self.canvas.get_width() - 54, 8, "Volver", ("close",))

    def open(self) -> None:
        self.closed = False
        self.requested_art_room = None

    def _catalog(self) -> list[tuple[str, str]]:
        if self.category == "buildings":
            return [
                (blueprint_id, definition.name)
                for blueprint_id, definition in self.world.registries.buildings.items()
            ]
        return [
            (kind, self.world.registries.interactables.get(kind).name)
            for kind in self.world.registries.interactables.kinds()
            if self.world.registries.interactables.get(kind).urbanism_category == self.category
        ]

    def _catalog_buttons(self) -> list[Button]:
        visible = (CATALOG_BOTTOM - CATALOG_TOP) // ROW_HEIGHT
        entries = self._catalog()[self.catalog_offset : self.catalog_offset + visible]
        return [
            Button(
                pygame.Rect(MARGIN, CATALOG_TOP + index * ROW_HEIGHT, PANEL_WIDTH - MARGIN * 2, ROW_HEIGHT - 1),
                self.font.truncate(name, PANEL_WIDTH - MARGIN * 4),
                ("catalog", entry_id),
            )
            for index, (entry_id, name) in enumerate(entries)
        ]

    def _action_buttons(self) -> list[Button]:
        if self.selection is None:
            return []
        buttons = [Button.at(self.font, MARGIN, 382, "Mover", ("move",))]
        x = buttons[-1].rect.right + 4
        label = "Confirmar" if self.confirm_delete else "Retirar"
        buttons.append(Button.at(self.font, x, 382, label, ("remove",)))
        if self.selection[0] == "building":
            x = buttons[-1].rect.right + 4
            buttons.append(Button.at(self.font, x, 382, "Arte", ("art",)))
        return buttons

    @property
    def buttons(self) -> list[Button]:
        return [
            *self.category_buttons,
            self.select_button,
            self.close_button,
            *self._catalog_buttons(),
            *self._action_buttons(),
        ]

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self.closed = True
        elif event.type == pygame.KEYDOWN and event.key == pygame.K_m and self.selection is not None:
            self.tool, self.confirm_delete = "move", False
            self.message = "Elige la nueva posición"
        elif event.type == pygame.KEYDOWN and event.key == pygame.K_DELETE and self.selection is not None:
            self._remove_selected()
        elif event.type == pygame.MOUSEWHEEL:
            position = canvas_position(pygame.mouse.get_pos())
            if position[0] < PANEL_WIDTH:
                maximum = max(0, len(self._catalog()) - (CATALOG_BOTTOM - CATALOG_TOP) // ROW_HEIGHT)
                self.catalog_offset = min(maximum, max(0, self.catalog_offset - event.y))
        elif event.type == pygame.MOUSEMOTION:
            self.pointer_tile = self._tile_at(canvas_position(event.pos))
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            position = canvas_position(event.pos)
            self.pointer_tile = self._tile_at(position)
            intent = next((button.intent for button in self.buttons if button.contains(position)), None)
            if intent is not None:
                self._apply_intent(intent)
            elif self.pointer_tile is not None:
                self._use_map(self.pointer_tile)

    def _apply_intent(self, intent: Hashable) -> None:
        if intent == ("close",):
            self.closed = True
            return
        if not isinstance(intent, tuple):
            return
        if intent[0] == "category":
            self.category = str(intent[1])
            self.catalog_offset = 0
            entries = self._catalog()
            self.catalog_id = entries[0][0] if entries else None
            self.tool, self.selection, self.confirm_delete = "place", None, False
            return
        if intent[0] == "catalog":
            self.catalog_id = str(intent[1])
            self.tool, self.selection, self.confirm_delete = "place", None, False
            return
        if intent == ("tool", "select"):
            self.tool, self.confirm_delete = "select", False
            self.message = "Selecciona un edificio u objeto del mapa"
        elif intent == ("move",):
            self.tool, self.confirm_delete = "move", False
            self.message = "Elige la nueva posición"
        elif intent == ("remove",):
            self._remove_selected()
        elif intent == ("art",) and self.selection is not None and self.selection[0] == "building":
            self.requested_art_room = self.selection[1]

    def _use_map(self, tile: tuple[int, int]) -> None:
        if self.tool == "select":
            self.selection = self._pick(tile)
            self.confirm_delete = False
            self.message = self._selection_name() if self.selection is not None else "No hay nada en esa casilla"
            return
        if self.tool == "move" and self.selection is not None:
            kind, entity_id = self.selection
            command = (
                MoveObjectCommand(entity_id, tile)
                if kind == "object"
                else MoveBuildingCommand(entity_id, tile)
            )
            self._accept(self.world.apply_command(command))
            if self.message.endswith("movido"):
                self.tool = "select"
            return
        if self.tool != "place" or self.catalog_id is None:
            return
        command = (
            PlaceBuildingCommand(self.catalog_id, tile)
            if self.category == "buildings"
            else PlaceObjectCommand(self.catalog_id, tile)
        )
        result = self.world.apply_command(command)
        self._accept(result)
        if result.ok and result.entity_id is not None:
            self.selection = (
                "building" if self.category == "buildings" else "object",
                result.entity_id,
            )

    def _remove_selected(self) -> None:
        if self.selection is None:
            return
        if not self.confirm_delete:
            self.confirm_delete = True
            self.message = "Pulsa Confirmar para retirar definitivamente"
            return
        kind, entity_id = self.selection
        command = RemoveObjectCommand(entity_id) if kind == "object" else RemoveBuildingCommand(entity_id)
        result = self.world.apply_command(command)
        self._accept(result)
        if result.ok:
            self.selection = None
            self.confirm_delete = False
            self.tool = "select"

    def _accept(self, result: object) -> None:
        if isinstance(result, UrbanismResult):
            self.message = result.message
            if result.ok:
                self.confirm_delete = False

    def _tile_at(self, position: tuple[int, int]) -> tuple[int, int] | None:
        if not self.map_rect.collidepoint(position):
            return None
        return (
            (position[0] - self.map_rect.x) // self.tile_px,
            (position[1] - self.map_rect.y) // self.tile_px,
        )

    def _pick(self, tile: tuple[int, int]) -> Selection | None:
        objects = [
            placed
            for placed in self.world.interactables.values()
            if tile in placed.footprint(self.world.definition_of(placed))
        ]
        if objects:
            return ("object", objects[-1].object_id)
        rooms = [room for room in self.world.rooms.values() if room.roofed and tile in self._room_tiles(room)]
        return ("building", rooms[-1].room_id) if rooms else None

    def _selection_name(self) -> str:
        if self.selection is None:
            return ""
        kind, entity_id = self.selection
        if kind == "building":
            room = self.world.rooms.get(entity_id)
            return room.name.capitalize() if room is not None else ""
        placed = self.world.interactables.get(entity_id)
        return self.world.definition_of(placed).name.capitalize() if placed is not None else ""

    @staticmethod
    def _room_tiles(room: Room) -> set[tuple[int, int]]:
        return {
            (x, y)
            for y in range(room.y - 1, room.y + room.height + 1)
            for x in range(room.x - 1, room.x + room.width + 1)
        }

    def update(self, dt: float) -> None:
        pass

    def render(self) -> None:
        if self.layers is not None:
            self.layers.clear()
        self.canvas.fill(PALETTE["ink"])
        draw_panel(self.canvas, pygame.Rect(0, 0, PANEL_WIDTH, self.canvas.get_height()), border="copper")
        self.font.draw(self.canvas, "URBANISMO", (MARGIN, 8), PALETTE["lamp"])
        self.font.draw(self.canvas, "Añadir y editar el asentamiento", (MARGIN, 19), PALETTE["bone"])
        for button in self.buttons:
            active = (
                (isinstance(button.intent, tuple) and button.intent[:1] == ("category",) and button.intent[1] == self.category)
                or (button.intent == ("tool", "select") and self.tool == "select")
                or (isinstance(button.intent, tuple) and button.intent[:1] == ("catalog",) and button.intent[1] == self.catalog_id)
            )
            button.draw(self.canvas, self.font, active=active)
        self._render_map()
        selected = self._selection_name()
        if selected:
            self.font.draw(self.canvas, f"Seleccionado: {selected}", (MARGIN, 346), PALETTE["paper"])
        hint = self.font.truncate(self.message, PANEL_WIDTH - MARGIN * 2)
        self.font.draw(self.canvas, hint, (MARGIN, 365), PALETTE["glow"])
        self.font.draw(
            self.canvas,
            "Esc: volver   M: mover   Supr: retirar",
            (PANEL_WIDTH + MARGIN, self.canvas.get_height() - LINE_HEIGHT - 4),
            PALETTE["dust"],
        )

    def _render_map(self) -> None:
        for y, row in enumerate(self.world.tile_map.tiles):
            for x, terrain in enumerate(row):
                color = PALETTE[TERRAIN_COLORS.get(terrain, "shadow")]
                pygame.draw.rect(self.canvas, color, self._tile_rect((x, y)))
        for room in self.world.rooms.values():
            if not room.roofed:
                continue
            rect = self._tiles_rect(room.x - 1, room.y - 1, room.width + 2, room.height + 2)
            pygame.draw.rect(self.canvas, PALETTE["rust_dark"], rect, max(1, self.tile_px // 3))
        for placed in self.world.interactables.values():
            definition = self.world.definition_of(placed)
            rect = self._tiles_rect(placed.x, placed.y, definition.width, definition.height)
            sheet = self.sprites.sheet(definition)
            frame_width = definition.width * 16
            image = sheet.subsurface((0, 0, min(frame_width, sheet.get_width()), sheet.get_height()))
            self.canvas.blit(pygame.transform.scale(image, rect.size), rect)
        for resident in self.world.residents.values():
            if not resident.away:
                pygame.draw.circle(self.canvas, PALETTE["glow"], self._tile_rect(resident.tile).center, max(2, self.tile_px // 3))
        if self.selection is not None:
            kind, entity_id = self.selection
            if kind == "object" and entity_id in self.world.interactables:
                placed = self.world.interactables[entity_id]
                definition = self.world.definition_of(placed)
                rect = self._tiles_rect(placed.x, placed.y, definition.width, definition.height)
                pygame.draw.rect(self.canvas, PALETTE["glow"], rect, 2)
            elif kind == "building" and entity_id in self.world.rooms:
                room = self.world.rooms[entity_id]
                pygame.draw.rect(
                    self.canvas,
                    PALETTE["glow"],
                    self._tiles_rect(room.x - 1, room.y - 1, room.width + 2, room.height + 2),
                    2,
                )
        if self.pointer_tile is not None:
            pygame.draw.rect(self.canvas, PALETTE["paper"], self._tile_rect(self.pointer_tile), 1)
        pygame.draw.rect(self.canvas, PALETTE["iron"], self.map_rect, 1)

    def _tile_rect(self, tile: tuple[int, int]) -> pygame.Rect:
        return pygame.Rect(
            self.map_rect.x + tile[0] * self.tile_px,
            self.map_rect.y + tile[1] * self.tile_px,
            self.tile_px,
            self.tile_px,
        )

    def _tiles_rect(self, x: int, y: int, width: int, height: int) -> pygame.Rect:
        return pygame.Rect(
            self.map_rect.x + x * self.tile_px,
            self.map_rect.y + y * self.tile_px,
            width * self.tile_px,
            height * self.tile_px,
        )
