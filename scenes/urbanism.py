"""Settlement layout editor, worked by dragging: out of the catalogue to add, across the map to move.

What takes building is not put down: once it has been dropped where it is to go, the player
says who it is proposed to, and that resident agrees to it or does not.

Input becomes simulation commands; pygame owns only the UI.
"""

from __future__ import annotations

from collections.abc import Hashable
from dataclasses import dataclass

import pygame

from graphics.assets import AssetStore
from graphics import building_pictures
from graphics.building_renderer import BuildingRenderer
from graphics.font import LINE_HEIGHT, BitmapFont
from graphics.object_art import ObjectArtStore
from graphics.object_pictures import ObjectPictures
from graphics.object_sprites import ObjectSprites
from graphics.palette import PALETTE
from graphics.screen_layers import ScreenLayers
from graphics.ui_skin import WindowSkin
from scenes.scene import canvas_position
from simulation.commands import (
    CancelSiteCommand,
    MoveBuildingCommand,
    MoveObjectCommand,
    PlaceBuildingCommand,
    PlaceObjectCommand,
    ProposeBuildingCommand,
    ProposeObjectCommand,
    RemoveBuildingCommand,
    RemoveObjectCommand,
)
from simulation.world import SimulationWorld
from ui.button import Button
from ui.panel import draw_panel
from ui.tutorial_panel import BUILDING_ART_FOCUS, lit, owed_object, tutorial_heading
from world.build import BUILDING_SITE, OBJECT_SITE, BuildRule, BuildSite
from world.interactable import InteractableDefinition
from world.map import Tile
from world.room import Room
from world.urbanism import UrbanismResult

PANEL_WIDTH = 218
MARGIN = 8
CATALOG_TOP = 58
CATALOG_BOTTOM = 326
ROW_HEIGHT = 14
# The catalogue is a grid of pictures: so many to a row, each on a tile of this side, with
# this much between them and this much of the tile for the picture.
CATALOG_COLUMNS = 5
CATALOG_TILE = 38
CATALOG_GAP = 3
CATALOG_PICTURE = 32
# How large a cell is in the picture the game draws of a thing for the catalogue, before it is fitted to its tile.
CATALOG_DRAWN_CELL = 64
# What nobody knows how to make yet comes last, under a heading of its own.
LOCKED_TITLE = "Bloqueados"
LOCKED_HEADING = LINE_HEIGHT + 4
LOCK_SIZE = 13
# How much of its colour a picture keeps while what it shows cannot be made.
LOCKED_SHADE = (96, 100, 112, 255)
FREE_TO_PLACE = "se pone sin obra"
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

GHOST_ALPHA = 150
DEFAULT_MESSAGE = "Arrastra algo del catálogo al mapa"
WHO_MESSAGE = "¿A quién se lo propones?"
MORE_BELOW = "Rueda del ratón: hay más"
# Where the message goes, and how many lines of it there is room for above the buttons.
MESSAGE_TOP = 357
MESSAGE_LINES = 2
SITE = "site"

Selection = tuple[str, str]


@dataclass(frozen=True)
class CatalogEntry:
    """One thing the catalogue offers: a kind of building or of object."""

    entry_id: str
    name: str
    site_kind: str
    # Why it cannot be put up yet, for want of knowing how. None for what can be.
    lock: str | None = None


@dataclass(frozen=True)
class Held:
    """What the pointer carries: a catalogue entry not yet placed, or something lifted off the map."""

    kind: str
    width: int
    height: int
    # From the pointer's tile back to the tile the thing is placed by, so it does not jump when grabbed.
    grip: Tile
    catalog_id: str | None = None
    entity_id: str | None = None

    @property
    def margin(self) -> int:
        """Buildings are placed by their inside; their walls stand one tile out all round."""
        return 1 if self.kind == "building" else 0

    def origin(self, pointer: Tile) -> Tile:
        return (pointer[0] - self.grip[0], pointer[1] - self.grip[1])


@dataclass(frozen=True)
class Proposal:
    """Something that takes building, dropped where it is to go and waiting to be put to somebody."""

    held: Held
    tile: Tile

    @property
    def site_kind(self) -> str:
        return BUILDING_SITE if self.held.kind == "building" else OBJECT_SITE


class UrbanismEditor:
    def __init__(
        self,
        canvas: pygame.Surface,
        world: SimulationWorld,
        font: BitmapFont,
        assets: AssetStore,
        custom: AssetStore | None = None,
        layers: ScreenLayers | None = None,
        object_art: ObjectArtStore | None = None,
    ) -> None:
        self.canvas = canvas
        self.world = world
        self.font = font
        self.layers = layers
        self.sprites = ObjectSprites(assets, custom)
        # What somebody has drawn of each kind of object, if there is anywhere to keep drawings.
        self.object_art = object_art if object_art is not None and object_art.available else None
        self._drawn: dict[tuple[str, tuple[int, int]], pygame.Surface] = {}
        # Buildings as the catalogue shows them, and every picture of it once it has been fitted to its tile.
        self.buildings = BuildingRenderer(assets, custom)
        # A picture of the player's own takes the place of the padlock as of any other icon.
        self.skin = WindowSkin(canvas, layers, object_art.illustrations if object_art is not None else None)
        self._tiles: dict[tuple[str, str, int, bool], pygame.Surface] = {}
        # What the game draws of each kind of object, for the tiles of the catalogue (P41).
        self.pictures = ObjectPictures()
        self.time = 0.0
        self.closed = False
        self.category = "buildings"
        # The catalogue entry in hand. It stays there after a drop, so a click sets down another.
        self.catalog_id: str | None = None
        # What the pressed button is dragging, from the press until the release.
        self.drag: Held | None = None
        self.selection: Selection | None = None
        # What has been dropped on the map and takes building, until it is put to somebody or let go.
        self.proposal: Proposal | None = None
        self.confirm_delete = False
        self.message = DEFAULT_MESSAGE
        self.pointer: tuple[int, int] = (0, 0)
        self.pointer_tile: Tile | None = None
        self.catalog_offset = 0
        self.requested_art_room: str | None = None
        # Kind of object the player asked to draw. The game shell picks it up.
        self.requested_art_object: str | None = None
        # Why the thing in hand cannot go where it was last asked about. Time stands still here,
        # so the answer holds until something is placed, moved or removed.
        self._judged: tuple[tuple[Held, Tile], str | None] | None = None
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
        self.close_button = Button.at(self.font, self.canvas.get_width() - 54, 8, "Volver", ("close",))

    def open(self) -> None:
        self.closed = False
        self.requested_art_room = None
        self.requested_art_object = None
        self.drag = None
        self.proposal = None
        self._judged = None
        # Whatever was drawn while this was out of sight is read again.
        self._drawn = {}
        self._tiles = {}

    def _catalog(self) -> list[CatalogEntry]:
        """What the tab on show offers: what can be put up first, then what nobody knows how to make yet."""
        if self.category == "buildings":
            found = [
                (blueprint_id, definition.name, BUILDING_SITE)
                for blueprint_id, definition in self.world.registries.buildings.items()
            ]
        else:
            kinds = self.world.registries.interactables
            found = [
                (kind, kinds.get(kind).name, OBJECT_SITE)
                for kind in kinds.kinds()
                if kinds.get(kind).urbanism_category == self.category
            ]
        entries = [
            CatalogEntry(entry_id, name, site_kind, self.world.construction.not_known(self.world, site_kind, entry_id))
            for entry_id, name, site_kind in found
        ]
        # Sorting keeps each half in the order the data gives it.
        return sorted(entries, key=lambda entry: entry.lock is not None)

    def _catalog_lines(self) -> list[list[CatalogEntry] | str]:
        """The catalogue from the top down: rows of tiles, and the heading over what is locked."""
        entries = self._catalog()
        known = [entry for entry in entries if entry.lock is None]
        locked = [entry for entry in entries if entry.lock is not None]
        lines: list[list[CatalogEntry] | str] = [
            known[start : start + CATALOG_COLUMNS] for start in range(0, len(known), CATALOG_COLUMNS)
        ]
        if locked:
            lines.append(LOCKED_TITLE)
            lines += [locked[start : start + CATALOG_COLUMNS] for start in range(0, len(locked), CATALOG_COLUMNS)]
        return lines

    @staticmethod
    def _line_height(line: list[CatalogEntry] | str) -> int:
        return LOCKED_HEADING if isinstance(line, str) else CATALOG_TILE + CATALOG_GAP

    def _catalog_scroll(self) -> int:
        """How many lines the catalogue can be rolled down by before its last one is on show."""
        lines = self._catalog_lines()
        room, fitting = CATALOG_BOTTOM - CATALOG_TOP + CATALOG_GAP, 0
        for line in reversed(lines):
            room -= self._line_height(line)
            if room < 0:
                break
            fitting += 1
        return len(lines) - fitting

    def _catalog_cells(self) -> tuple[list[tuple[CatalogEntry, pygame.Rect]], int | None]:
        """Every tile on show with what it offers, and where the heading over the locked ones is, if it is on show."""
        cells: list[tuple[CatalogEntry, pygame.Rect]] = []
        heading: int | None = None
        y = CATALOG_TOP
        for line in self._catalog_lines()[self.catalog_offset :]:
            if isinstance(line, str):
                if y + LOCKED_HEADING > CATALOG_BOTTOM:
                    break
                heading = y
            else:
                if y + CATALOG_TILE > CATALOG_BOTTOM:
                    break
                for column, entry in enumerate(line):
                    left = MARGIN + column * (CATALOG_TILE + CATALOG_GAP)
                    cells.append((entry, pygame.Rect(left, y, CATALOG_TILE, CATALOG_TILE)))
            y += self._line_height(line)
        return cells, heading

    def _catalog_buttons(self) -> list[Button]:
        return [Button(rect, entry.name, ("catalog", entry.entry_id)) for entry, rect in self._catalog_cells()[0]]

    def pointed_entry(self) -> CatalogEntry | None:
        """What the tile under the pointer offers, while the catalogue is on show and nothing is in the air."""
        if self.proposal is not None or self.drag is not None:
            return None
        return next((entry for entry, rect in self._catalog_cells()[0] if rect.collidepoint(self.pointer)), None)

    def entry_note(self, entry: CatalogEntry) -> str:
        """What there is to say of a thing under its name: what stands in its way, or what it takes to put up."""
        if entry.lock is not None:
            return entry.lock
        building = self.world.construction
        if not building.needs_building(self.world, entry.site_kind, entry.entry_id):
            return FREE_TO_PLACE
        return self._rule_text(building.rule_for(self.world, entry.site_kind, entry.entry_id)) or FREE_TO_PLACE

    def _resident_buttons(self) -> list[Button]:
        """Whoever the thing waiting to be built can be put to, in place of the catalogue."""
        buttons = []
        for index, resident in enumerate(self.world.residents.values()):
            theirs = sum(1 for site in self.world.sites.values() if site.in_charge == resident.resident_id)
            label = resident.name if not theirs else f"{resident.name} ({theirs} en marcha)"
            if resident.away:
                label = f"{resident.name} (fuera)"
            buttons.append(
                Button(
                    pygame.Rect(MARGIN, CATALOG_TOP + index * ROW_HEIGHT, PANEL_WIDTH - MARGIN * 2, ROW_HEIGHT - 1),
                    self.font.truncate(label, PANEL_WIDTH - MARGIN * 4),
                    ("propose", resident.resident_id),
                )
            )
        return buttons

    def _action_buttons(self) -> list[Button]:
        if self.proposal is not None:
            return [Button.at(self.font, MARGIN, 382, "Dejarlo", ("drop_proposal",))]
        if self.selection is None:
            return []
        label = "Confirmar" if self.confirm_delete else ("Abandonar" if self.selection[0] == SITE else "Retirar")
        buttons = [Button.at(self.font, MARGIN, 382, label, ("remove",))]
        if self._can_draw(self.selection):
            x = buttons[-1].rect.right + 4
            buttons.append(Button.at(self.font, x, 382, "Arte", ("art",)))
        return buttons

    def _can_draw(self, selection: Selection) -> bool:
        """Whether what is selected has a drawing of its own to open."""
        if selection[0] == "building":
            return True
        return self.object_art is not None and selection[1] in self.world.interactables

    def _ask_for_art(self, selection: Selection) -> None:
        if not self._can_draw(selection):
            return
        if selection[0] == "building":
            self.requested_art_room = selection[1]
        else:
            self.requested_art_object = self.world.interactables[selection[1]].kind

    @property
    def buttons(self) -> list[Button]:
        if self.proposal is not None:
            return [self.close_button, *self._resident_buttons(), *self._action_buttons()]
        return [
            *self.category_buttons,
            self.close_button,
            *self._catalog_buttons(),
            *self._action_buttons(),
        ]

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            if self.drag is not None or self.proposal is not None:
                self._let_go()
            else:
                self.closed = True
        elif event.type == pygame.KEYDOWN and event.key == pygame.K_DELETE and self.selection is not None:
            self._remove_selected()
        elif event.type == pygame.MOUSEWHEEL:
            position = canvas_position(pygame.mouse.get_pos())
            if position[0] < PANEL_WIDTH:
                self.catalog_offset = min(self._catalog_scroll(), max(0, self.catalog_offset - event.y))
        elif event.type == pygame.MOUSEMOTION:
            self._point(canvas_position(event.pos))
            if self.drag is not None and self.pointer_tile is not None:
                self.message = self._held_error(self.drag, self.pointer_tile) or "Suelta para dejarlo aquí"
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            self._point(canvas_position(event.pos))
            intent = next((button.intent for button in self.buttons if button.contains(self.pointer)), None)
            if intent is not None:
                self._apply_intent(intent)
            elif self.pointer_tile is not None and self.proposal is None:
                self._press_map(self.pointer_tile)
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            self._point(canvas_position(event.pos))
            self._drop()
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 3:
            self._let_go()

    def _point(self, position: tuple[int, int]) -> None:
        self.pointer = position
        self.pointer_tile = self._tile_at(position)

    def _apply_intent(self, intent: Hashable) -> None:
        if intent == ("close",):
            self.closed = True
            return
        if not isinstance(intent, tuple):
            return
        if intent[0] == "category":
            self.category = str(intent[1])
            self.catalog_offset = 0
            self.catalog_id, self.selection, self.confirm_delete = None, None, False
            self.message = DEFAULT_MESSAGE
        elif intent[0] == "catalog":
            site_kind = BUILDING_SITE if self.category == "buildings" else OBJECT_SITE
            unknown = self.world.construction.not_known(self.world, site_kind, str(intent[1]))
            if unknown is not None:
                # It is not taken in hand: there is nothing to put down until somebody knows how.
                self.catalog_id, self.drag, self.message = None, None, unknown
                return
            self.catalog_id = str(intent[1])
            self.selection, self.confirm_delete = None, False
            self.drag = self._catalog_held()
            self.message = self._cost_of(self.drag) or "Suéltalo en el mapa; un clic coloca otro igual"
        elif intent[0] == "propose":
            self._propose_to(str(intent[1]))
        elif intent == ("drop_proposal",):
            self._let_go()
        elif intent == ("remove",):
            self._remove_selected()
        elif intent == ("art",) and self.selection is not None:
            self._ask_for_art(self.selection)

    def _press_map(self, tile: Tile) -> None:
        picked = self._pick(tile)
        if picked is not None:
            # Taking hold of something on the map puts down whatever came from the catalogue.
            self.selection, self.catalog_id, self.confirm_delete = picked, None, False
            self.drag = self._entity_held(picked, tile)
            self.message = self._selection_name()
            return
        held = self._catalog_held()
        if held is not None:
            self._place(held, tile)
        else:
            self.selection, self.confirm_delete = None, False
            self.message = DEFAULT_MESSAGE

    def _drop(self) -> None:
        held, self.drag = self.drag, None
        if held is None or self.pointer_tile is None:
            return
        if held.entity_id is None:
            self._place(held, self.pointer_tile)
            return
        target = held.origin(self.pointer_tile)
        if target == self._entity_origin((held.kind, held.entity_id)):
            # Pressed and released in place: a click, which only selects.
            self.message = self._selection_name()
            return
        command = (
            MoveObjectCommand(held.entity_id, target)
            if held.kind == "object"
            else MoveBuildingCommand(held.entity_id, target)
        )
        self._accept(self.world.apply_command(command))

    def _place(self, held: Held, tile: Tile) -> None:
        if held.catalog_id is None:
            return
        target = held.origin(tile)
        site_kind = BUILDING_SITE if held.kind == "building" else OBJECT_SITE
        building = self.world.construction
        if building.needs_building(self.world, site_kind, held.catalog_id):
            # It is not put down: it is settled where it goes, and then who is asked to see to it.
            error = building.site_error(self.world, site_kind, held.catalog_id, target)
            if error is not None:
                self._accept(UrbanismResult(False, error))
                return
            self.proposal = Proposal(held, target)
            self.selection, self.confirm_delete = None, False
            self.message = WHO_MESSAGE
            return
        command = (
            PlaceBuildingCommand(held.catalog_id, target)
            if held.kind == "building"
            else PlaceObjectCommand(held.catalog_id, target)
        )
        result = self.world.apply_command(command)
        self._accept(result)
        if result.ok and result.entity_id is not None:
            self.selection = (held.kind, result.entity_id)
            if self._step_wants_it_drawn(held.kind):
                # In the opening of a new settlement, what is put down is drawn there and then.
                self._ask_for_art(self.selection)

    def _step_wants_it_drawn(self, kind: str) -> bool:
        step = self.world.guide.current(self.world)
        if step is None:
            return False
        if kind == "building":
            return step.focus == BUILDING_ART_FOCUS
        return owed_object(self.world) is not None

    def _propose_to(self, resident_id: str) -> None:
        """Put what is waiting to be built to a resident. If they will not, somebody else can be asked."""
        proposal = self.proposal
        if proposal is None or proposal.held.catalog_id is None:
            return
        command = (
            ProposeBuildingCommand(proposal.held.catalog_id, proposal.tile, resident_id)
            if proposal.held.kind == "building"
            else ProposeObjectCommand(proposal.held.catalog_id, proposal.tile, resident_id)
        )
        result = self.world.apply_command(command)
        self._accept(result)
        if isinstance(result, UrbanismResult) and result.ok and result.entity_id is not None:
            self.proposal = None
            self.selection = (SITE, result.entity_id)

    def _cost_of(self, held: Held | None) -> str:
        """What the thing in hand takes to build, in a few words. Nothing for what is simply put down."""
        if held is None or held.catalog_id is None:
            return ""
        site_kind = BUILDING_SITE if held.kind == "building" else OBJECT_SITE
        building = self.world.construction
        if not building.needs_building(self.world, site_kind, held.catalog_id):
            return ""
        return f"Hay que construirlo: {self._rule_text(building.rule_for(self.world, site_kind, held.catalog_id))}"

    def _rule_text(self, rule: BuildRule | None) -> str:
        if rule is None:
            return ""
        parts = [f"{units} de {self._material(tag)}" for tag, units in rule.cost.items()]
        if rule.minutes:
            parts.append(f"{rule.minutes} min de obra")
        job = self.world.registries.jobs.get(rule.job or "")
        if job is not None:
            parts.append(f"puesto: {job.name}")
        return ", ".join(parts)

    def _material(self, tag: str) -> str:
        items = self.world.registries.items
        return next((items.get(item_id).name for item_id in items.ids() if tag in items.get(item_id).tags), tag)

    def _let_go(self) -> None:
        """Put down whatever is in hand without changing the settlement."""
        self.drag, self.catalog_id, self.confirm_delete = None, None, False
        self.proposal = None
        self.message = self._selection_name() or DEFAULT_MESSAGE

    def _catalog_held(self) -> Held | None:
        if self.catalog_id is None:
            return None
        if self.category == "buildings":
            blueprint = self.world.registries.buildings.get(self.catalog_id)
            if blueprint is None:
                return None
            size = (blueprint.width, blueprint.height)
        else:
            definition = self.world.registries.interactables.find(self.catalog_id)
            if definition is None:
                return None
            size = (definition.width, definition.height)
        kind = "building" if self.category == "buildings" else "object"
        # Held by its middle, where the hand expects it.
        return Held(kind, *size, (size[0] // 2, size[1] // 2), catalog_id=self.catalog_id)

    def _entity_held(self, selection: Selection, pointer: Tile) -> Held | None:
        origin = self._entity_origin(selection)
        if origin is None:
            return None
        kind, entity_id = selection
        if kind == "building":
            room = self.world.rooms[entity_id]
            size = (room.width, room.height)
        else:
            definition = self.world.definition_of(self.world.interactables[entity_id])
            size = (definition.width, definition.height)
        grip = (pointer[0] - origin[0], pointer[1] - origin[1])
        return Held(kind, *size, grip, entity_id=entity_id)

    def _entity_origin(self, selection: Selection) -> Tile | None:
        kind, entity_id = selection
        if kind == SITE:
            # What is being built stays where it was agreed: it is given up, not moved.
            return None
        entity = (self.world.rooms if kind == "building" else self.world.interactables).get(entity_id)
        return (entity.x, entity.y) if entity is not None else None

    def _held_error(self, held: Held, pointer: Tile) -> str | None:
        """Ask the simulation why the held thing cannot go under the pointer. None means it can."""
        if self._judged is None or self._judged[0] != (held, pointer):
            self._judged = ((held, pointer), self._judge(held, pointer))
        return self._judged[1]

    def _judge(self, held: Held, pointer: Tile) -> str | None:
        target = held.origin(pointer)
        urbanism = self.world.urbanism
        if held.entity_id is not None:
            check = urbanism.move_object_error if held.kind == "object" else urbanism.move_building_error
            return check(self.world, held.entity_id, target)
        if held.kind == "building":
            return urbanism.building_error(self.world, held.width, held.height, target)
        return urbanism.object_error(self.world, held.catalog_id or "", target)

    def _remove_selected(self) -> None:
        if self.selection is None:
            return
        if not self.confirm_delete:
            self.confirm_delete = True
            self.message = "Pulsa Confirmar para retirar definitivamente"
            return
        kind, entity_id = self.selection
        if kind == SITE:
            command = CancelSiteCommand(entity_id)
        else:
            command = RemoveObjectCommand(entity_id) if kind == "object" else RemoveBuildingCommand(entity_id)
        result = self.world.apply_command(command)
        self._accept(result)
        if result.ok:
            self.selection = None
            self.confirm_delete = False

    def _accept(self, result: object) -> None:
        self._judged = None
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
        site = next((site for site in self.world.sites.values() if tile in site.tiles), None)
        if site is not None:
            return (SITE, site.site_id)
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
        if kind == SITE:
            site = self.world.sites.get(entity_id)
            return self._site_name(site) if site is not None else ""
        if kind == "building":
            room = self.world.rooms.get(entity_id)
            return room.name.capitalize() if room is not None else ""
        placed = self.world.interactables.get(entity_id)
        return self.world.definition_of(placed).name.capitalize() if placed is not None else ""

    def _site_name(self, site: BuildSite) -> str:
        """What a site is for, how far along it is, who has it in hand and what it still waits for."""
        building = self.world.construction
        thing = building.thing(self.world, site.kind, site.what) or site.what
        done = round(building.fraction_done(self.world, site) * 100)
        text = f"Obra: {thing}, {done}%"
        in_charge = self.world.residents.get(site.in_charge or "")
        if in_charge is not None:
            text += f", de {in_charge.name}"
        lacking = building.lacking(self.world, site)
        if lacking:
            text += ". Falta " + ", ".join(f"{units} de {self._material(tag)}" for tag, units in lacking.items())
        return text

    @staticmethod
    def _room_tiles(room: Room) -> set[tuple[int, int]]:
        return {
            (x, y)
            for y in range(room.y - 1, room.y + room.height + 1)
            for x in range(room.x - 1, room.x + room.width + 1)
        }

    def update(self, dt: float) -> None:
        self.time += dt

    def render(self) -> None:
        if self.layers is not None:
            self.layers.clear()
        self.canvas.fill(PALETTE["ink"])
        draw_panel(self.canvas, pygame.Rect(0, 0, PANEL_WIDTH, self.canvas.get_height()), border="copper")
        self.font.draw(self.canvas, "URBANISMO", (MARGIN, 8), PALETTE["lamp"])
        self.font.draw(self.canvas, "Añadir y editar el asentamiento", (MARGIN, 19), PALETTE["bone"])
        if self.proposal is None:
            self._render_catalog()
        for button in self.buttons:
            if isinstance(button.intent, tuple) and button.intent[:1] == ("catalog",):
                # The catalogue is drawn as pictures, each on its tile.
                continue
            active = isinstance(button.intent, tuple) and button.intent[:1] == ("category",) and button.intent[1] == self.category
            button.draw(self.canvas, self.font, active=active)
            if button.intent == ("art",) and owed_object(self.world) is not None and lit(self.time):
                pygame.draw.rect(self.canvas, PALETTE["glow"], button.rect.inflate(4, 4), 1)
        self._render_step()
        self._render_map()
        self._render_held()
        width = PANEL_WIDTH - MARGIN * 2
        selected = self._selection_name()
        if self.proposal is not None:
            selected = self._proposal_name(self.proposal)
        elif selected and self.selection is not None and self.selection[0] != SITE:
            selected = f"Seleccionado: {selected}"
        # What is selected is said above the message, and gives way to the catalogue where they meet.
        lines = self.font.wrap(selected, width) if selected else []
        if self.proposal is None and self.catalog_offset < self._catalog_scroll() and len(lines) < 2:
            self.font.draw(self.canvas, MORE_BELOW, (MARGIN, CATALOG_BOTTOM + 1), PALETTE["dust"])
        top = MESSAGE_TOP - LINE_HEIGHT * len(lines)
        for index, line in enumerate(lines):
            self.font.draw(self.canvas, line, (MARGIN, top + index * LINE_HEIGHT), PALETTE["paper"])
        for index, line in enumerate(self.font.wrap(self.message, width)[:MESSAGE_LINES]):
            self.font.draw(self.canvas, line, (MARGIN, MESSAGE_TOP + index * LINE_HEIGHT), PALETTE["glow"])
        self.font.draw(
            self.canvas,
            "Arrastra para colocar o mover   Clic derecho: soltar   Supr: retirar o abandonar   Esc: volver",
            (PANEL_WIDTH + MARGIN, self.canvas.get_height() - LINE_HEIGHT - 4),
            PALETTE["dust"],
        )
        self._render_pointed()

    def _render_catalog(self) -> None:
        """The catalogue as a grid of pictures, with what cannot be made yet dimmed under its heading."""
        cells, heading = self._catalog_cells()
        if heading is not None:
            self.font.draw(self.canvas, LOCKED_TITLE, (MARGIN, heading + 1), PALETTE["stone"])
            left = MARGIN + self.font.width(LOCKED_TITLE) + 5
            pygame.draw.line(
                self.canvas, PALETTE["iron"], (left, heading + LINE_HEIGHT // 2 + 1), (PANEL_WIDTH - MARGIN, heading + LINE_HEIGHT // 2 + 1)
            )
        pointed = self.pointed_entry()
        scale = self.layers.scale if self.skin.usable and self.layers is not None else 1
        for entry, rect in cells:
            locked = entry.lock is not None
            border = "lamp" if entry.entry_id == self.catalog_id else ("bone" if entry is pointed else "iron")
            draw_panel(self.canvas, rect, fill="ink" if locked else "shadow", border=border)
            picture = self._catalog_picture(entry, scale)
            place = pygame.Rect(0, 0, picture.get_width() // scale, picture.get_height() // scale)
            place.center = rect.center
            if not self.skin.picture(self.canvas, picture, place):
                self.canvas.blit(picture, place)
            if locked:
                badge = pygame.Rect(rect.right - LOCK_SIZE - 2, rect.bottom - LOCK_SIZE - 2, LOCK_SIZE, LOCK_SIZE)
                lock = self.skin.icon("lock", LOCK_SIZE * scale)
                if not self.skin.picture(self.canvas, lock, badge):
                    self.canvas.blit(lock, badge)

    def _catalog_picture(self, entry: CatalogEntry, scale: int) -> pygame.Surface:
        """What a thing looks like, fitted to its tile: `scale` pixels of the picture to one of the canvas."""
        locked = entry.lock is not None
        key = (entry.site_kind, entry.entry_id, scale, locked)
        if key not in self._tiles:
            source, drawn = self._catalog_source(entry)
            width, height = source.get_size()
            fit = min(CATALOG_PICTURE / width, CATALOG_PICTURE / height)
            size = (max(1, round(width * fit)) * scale, max(1, round(height * fit)) * scale)
            # A drawing is brought to size smoothly. The game's own art keeps its pixels.
            resize = pygame.transform.smoothscale if drawn else pygame.transform.scale
            picture = resize(source.convert_alpha() if pygame.display.get_surface() else source, size)
            if locked:
                picture = picture.copy()
                picture.fill(LOCKED_SHADE, special_flags=pygame.BLEND_RGBA_MULT)
            self._tiles[key] = picture
        return self._tiles[key]

    def _catalog_source(self, entry: CatalogEntry) -> tuple[pygame.Surface, bool]:
        """The picture of a thing as it is kept, and whether somebody drew it."""
        if entry.site_kind == BUILDING_SITE:
            definition = self.world.registries.buildings[entry.entry_id]
            room = Room(
                f"catalog:{entry.entry_id}", definition.name, width=definition.width, height=definition.height,
                roofed=True, blueprint_id=entry.entry_id,
            )
            if self.skin.usable:
                # As the game draws it on the map, with a door in the middle of its front.
                return building_pictures.closed(room, CATALOG_DRAWN_CELL, (definition.width // 2 + 1,)), True
            return self.buildings.picture(room), False
        definition = self.world.registries.interactables.get(entry.entry_id)
        drawing = self.object_art.drawing(definition) if self.object_art is not None else None
        if drawing is not None:
            return drawing, True
        if self.skin.usable and self.pictures.has(definition.kind, definition.width, definition.height):
            return self.pictures.whole(definition.kind, CATALOG_DRAWN_CELL), True
        sheet = self.sprites.sheet(definition)
        frame_width = definition.width * 16
        return sheet.subsurface((0, 0, min(frame_width, sheet.get_width()), sheet.get_height())), False

    def _render_pointed(self) -> None:
        """Beside the pointer, the name of what it is on in the catalogue and what there is to say of it."""
        entry = self.pointed_entry()
        if entry is None:
            return
        name, note = entry.name.capitalize(), self.entry_note(entry)
        room = self.canvas.get_width() - MARGIN * 4
        notes = self.font.wrap(note, min(room, 220))
        width = max(self.font.width(line) for line in [name, *notes]) + 10
        height = LINE_HEIGHT * (1 + len(notes)) + 7
        box = pygame.Rect(self.pointer[0] + 10, self.pointer[1] + 12, width, height)
        box.clamp_ip(self.canvas.get_rect().inflate(-4, -4))
        draw_panel(self.canvas, box, fill="ink", border="lamp")
        self.font.draw(self.canvas, name, (box.x + 5, box.y + 3), PALETTE["paper"])
        for index, line in enumerate(notes):
            position = (box.x + 5, box.y + 3 + LINE_HEIGHT * (index + 1))
            self.font.draw(self.canvas, line, position, PALETTE["ember" if entry.lock is not None else "sand"])

    def _render_step(self) -> None:
        """Above the map, what the opening of a new settlement asks for next, while it is on a step."""
        step = self.world.guide.current(self.world)
        if step is None:
            return
        x, y = PANEL_WIDTH + MARGIN, 6
        width = self.close_button.rect.left - MARGIN - x
        self.font.draw(self.canvas, tutorial_heading(self.world, step), (x, y), PALETTE["lamp"])
        lines = [(line, "paper") for line in self.font.wrap(step.text, width)]
        if owed_object(self.world) is not None:
            lines = [("Ya está puesto. Selecciónalo y pulsa Arte para dibujarlo.", "glow")]
        for line, color in lines[: max(0, (self.map_rect.top - y) // LINE_HEIGHT - 1)]:
            y += LINE_HEIGHT
            self.font.draw(self.canvas, line, (x, y), PALETTE[color])

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
            self.canvas.blit(self._object_image(definition, rect.size), rect)
        for site in self.world.sites.values():
            self._render_site(site)
        for resident in self.world.residents.values():
            if not resident.away:
                pygame.draw.circle(self.canvas, PALETTE["glow"], self._tile_rect(resident.tile).center, max(2, self.tile_px // 3))
        if self.proposal is not None:
            held, tile = self.proposal.held, self.proposal.tile
            rect = self._tiles_rect(
                tile[0] - held.margin, tile[1] - held.margin, held.width + held.margin * 2, held.height + held.margin * 2
            )
            self._draw_ghost(held, rect, "ochre")
        if self.selection is not None:
            kind, entity_id = self.selection
            if kind == SITE and entity_id in self.world.sites:
                pygame.draw.rect(self.canvas, PALETTE["glow"], self._site_rect(self.world.sites[entity_id]), 2)
            elif kind == "object" and entity_id in self.world.interactables:
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

    def _proposal_name(self, proposal: Proposal) -> str:
        building = self.world.construction
        thing = building.thing(self.world, proposal.site_kind, proposal.held.catalog_id or "") or ""
        rule = building.rule_for(self.world, proposal.site_kind, proposal.held.catalog_id or "")
        return f"Obra: {thing}. {self._rule_text(rule).capitalize()}"

    def _site_rect(self, site: BuildSite) -> pygame.Rect:
        columns = [x for x, _ in site.tiles] or [site.x]
        rows = [y for _, y in site.tiles] or [site.y]
        return self._tiles_rect(
            min(columns), min(rows), max(columns) - min(columns) + 1, max(rows) - min(rows) + 1
        )

    def _render_site(self, site: BuildSite) -> None:
        """Ground marked out for something being built: its outline, filled as far as it is done."""
        rect = self._site_rect(site)
        done = self.world.construction.fraction_done(self.world, site)
        shade = pygame.Surface(rect.size, pygame.SRCALPHA)
        shade.fill((*PALETTE["ochre"], GHOST_ALPHA // 3))
        shade.fill((*PALETTE["lichen"], GHOST_ALPHA), (0, 0, round(rect.width * done), rect.height))
        self.canvas.blit(shade, rect)
        pygame.draw.rect(self.canvas, PALETTE["ochre"], rect, 1)

    def _render_held(self) -> None:
        """Show where the held thing would land, and whether the settlement has room for it there."""
        held = self.drag or self._catalog_held()
        if held is None or self.proposal is not None:
            return
        size = ((held.width + held.margin * 2) * self.tile_px, (held.height + held.margin * 2) * self.tile_px)
        if self.pointer_tile is None:
            if self.drag is not None:
                # On its way across the panel: it follows the hand until it reaches the map.
                rect = pygame.Rect((0, 0), size)
                rect.center = self.pointer
                self._draw_ghost(held, rect, "dust")
            return
        origin = held.origin(self.pointer_tile)
        rect = pygame.Rect(self._tile_rect((origin[0] - held.margin, origin[1] - held.margin)).topleft, size)
        fits = self._held_error(held, self.pointer_tile) is None
        self.canvas.set_clip(self.map_rect)
        self._draw_ghost(held, rect, "lichen" if fits else "ember")
        self.canvas.set_clip(None)

    def _draw_ghost(self, held: Held, rect: pygame.Rect, color: str) -> None:
        ghost = pygame.Surface(rect.size, pygame.SRCALPHA)
        ghost.fill((*PALETTE[color], GHOST_ALPHA // 2))
        definition = self._held_object_definition(held)
        if definition is not None:
            ghost.blit(self._object_image(definition, rect.size), (0, 0))
            ghost.set_alpha(GHOST_ALPHA)
        self.canvas.blit(ghost, rect)
        pygame.draw.rect(self.canvas, PALETTE[color], rect, 2 if held.kind == "building" else 1)

    def _held_object_definition(self, held: Held) -> InteractableDefinition | None:
        if held.kind != "object":
            return None
        if held.catalog_id is not None:
            return self.world.registries.interactables.find(held.catalog_id)
        placed = self.world.interactables.get(held.entity_id or "")
        return self.world.definition_of(placed) if placed is not None else None

    def _object_image(self, definition: InteractableDefinition, size: tuple[int, int]) -> pygame.Surface:
        drawing = self.object_art.drawing(definition) if self.object_art is not None else None
        if drawing is not None:
            key = (definition.kind, size)
            if key not in self._drawn:
                self._drawn[key] = pygame.transform.smoothscale(drawing, size)
            return self._drawn[key]
        sheet = self.sprites.sheet(definition)
        frame_width = definition.width * 16
        image = sheet.subsurface((0, 0, min(frame_width, sheet.get_width()), sheet.get_height()))
        return pygame.transform.scale(image, size)

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
