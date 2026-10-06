"""In-game editor for a building's aligned inside, walls, roof and door drawings."""

from collections.abc import Callable
from pathlib import Path

import pygame

from graphics.building_art import (
    BUILDING_PARTS,
    DOOR_PART,
    INSIDE_PART,
    PART_LABELS,
    ROOF_PART,
    WALLS_PART,
    BuildingArtStore,
    building_canvas_size,
    building_part_path,
)
from graphics.font import LINE_HEIGHT, BitmapFont
from graphics.palette import PALETTE
from graphics.screen_layers import TRANSPARENT, ScreenLayers
from scenes.scene import canvas_position
from simulation.world import SimulationWorld
from ui.button import Button
from ui.paintbox import (
    FILLED_LABEL,
    HOLLOW_LABEL,
    POLYGON_NOTICE,
    POLYGON_TOOL,
    SHAPE_LABELS,
    ColorField,
    ShapeDraft,
    draw_chosen,
)
from ui.panel import draw_panel
from ui.tutorial_panel import (
    BUILDING_ART_FOCUS,
    BUILDING_DRAWN_DEED,
    COLOR_DEED,
    FILL_DEED,
    PART_DEED,
    STROKE_DEED,
    UNDO_DEED,
    draw_hint,
    draw_lesson,
    lesson_for,
)

DRAWING_AT = (196, 58)
PREVIEW = pygame.Rect(660, 64, 132, 116)
NOTES = pygame.Rect(660, 194, 132, 244)
TOOLS_LEFT = 8
SWATCH = (28, 16)
SWATCHES_PER_ROW = 6
BRUSHES = (2, 5, 10, 18)
BRUSH_TOOL, ERASER_TOOL, FILL_TOOL = "brush", "eraser", "fill"
TOOL_LABELS = {BRUSH_TOOL: "Pincel", ERASER_TOOL: "Goma", FILL_TOOL: "Cubo"}
GUIDE_UNDER, GUIDE_OVER, GUIDE_OFF = "under", "over", "off"
GUIDE_LABELS = {GUIDE_UNDER: "Calco: debajo", GUIDE_OVER: "Calco: encima", GUIDE_OFF: "Calco: quitado"}
GUIDE_ALPHA = {GUIDE_UNDER: 160, GUIDE_OVER: 90}
# What each stretch of a part is called on the guide.
ZONE_NAMES = {
    "floor": "suelo de dentro",
    "roof": "tejado",
    "door": "puerta",
    "back": "muro del fondo",
    "side": "lateral",
    "front": "fachada",
    "gap": "hueco",
}
UNDO_STEPS = 30
# Under the tools, the field any colour is picked from, and beside the word the one in hand.
FIELD_SIZE = (168, 44)
CHOSEN = pygame.Rect(40, 44, 22, 10)
PAPER = PALETTE["bone"]
SAVED_TEXT = "Guardado: el edificio ya usa estos dibujos"
NOTES_TEXT = (
    "Las cuatro piezas comparten marco: no cambies su sitio al pasar de una a otra.",
    "El interior queda bajo muebles y personas. Muros y puerta quedan delante. El tejado se quita al mirar dentro.",
    "El calco marca y nombra la zona de cada pieza, con la del juego debajo como ejemplo. Lo que quede sin pintar deja ver el terreno.",
    "Ctrl+Z deshace. Esc vuelve sin guardar.",
)


class BuildingEditor:
    """Draw roofed rooms. Simulation time stands still while it is open."""

    def __init__(
        self,
        canvas: pygame.Surface,
        world: SimulationWorld,
        font: BitmapFont,
        layers: ScreenLayers,
        root: Path,
        buildings: BuildingArtStore,
        on_saved: Callable[[str], None] | None = None,
        on_deed: Callable[[str], None] | None = None,
    ) -> None:
        self.canvas = canvas
        self.world = world
        self.font = font
        self.layers = layers
        self.root = root
        self.buildings = buildings
        self.on_saved = on_saved
        self.on_deed = on_deed
        self.time = 0.0
        self.closed = False
        self.room_id: str | None = None
        self.part = INSIDE_PART
        self.drawings: dict[str, pygame.Surface] = {}
        self.area = pygame.Rect(DRAWING_AT, (1, 1))
        self.guide_picture = pygame.Surface((1, 1), pygame.SRCALPHA)
        self.colors = list(PALETTE.values())
        self.color = PALETTE["ink"]
        self.size = BRUSHES[1]
        self.tool = BRUSH_TOOL
        self.guide = GUIDE_UNDER
        self.roof_on = True
        self.notice = ""
        self._undo: list[tuple[str, pygame.Surface]] = []
        self._stroke: tuple[int, int] | None = None
        # A shape being laid down, whether shapes are filled, and whether the mouse is held on the field of colour.
        self._draft: ShapeDraft | None = None
        self.filled = False
        self._picking = False

        self.swatches = [
            (
                pygame.Rect(
                    TOOLS_LEFT + (index % SWATCHES_PER_ROW) * SWATCH[0],
                    58 + (index // SWATCHES_PER_ROW) * SWATCH[1],
                    *SWATCH,
                ),
                color,
            )
            for index, color in enumerate(self.colors)
        ]
        y = self.swatches[-1][0].bottom + 8
        self.brush_buttons = [
            (pygame.Rect(TOOLS_LEFT + index * 42, y, 40, 26), size)
            for index, size in enumerate(BRUSHES)
        ]
        y += 32
        self.tool_buttons = self._row(y, [(TOOL_LABELS[tool], ("tool", tool)) for tool in TOOL_LABELS])
        y += 18
        self.edit_buttons = self._row(y, [("Deshacer", ("undo",)), ("Limpiar", ("clear",))])
        y += 18
        self.guide_button = Button.at(font, TOOLS_LEFT, y, GUIDE_LABELS[GUIDE_UNDER], ("guide",))
        self.guide_button.rect.width = 110
        y += 18
        self.starter_button = Button.at(font, TOOLS_LEFT, y, "Arte de partida", ("starter",))
        y += 18
        self.shape_buttons = self._row(y, [(label, ("tool", tool)) for tool, label in SHAPE_LABELS.items()])
        y += 18
        self.fill_button = Button.at(font, TOOLS_LEFT, y, HOLLOW_LABEL, ("fill",))
        y += 20
        self.field = ColorField(pygame.Rect(TOOLS_LEFT, y, *FIELD_SIZE))
        self.top_buttons = self._row(
            6,
            [("<", ("step", -1)), (">", ("step", 1)), ("Guardar", ("save",)), ("Volver", ("close",))],
            left=530,
        )
        self.part_buttons = self._row(
            36,
            [(PART_LABELS[part], ("part", part)) for part in BUILDING_PARTS],
            left=DRAWING_AT[0],
        )
        self.preview_button = Button.at(font, PREVIEW.x, PREVIEW.bottom + 2, "Vista: tejado", ("preview",))

    def _row(self, y: int, entries: list[tuple[str, tuple]], left: int = TOOLS_LEFT) -> list[Button]:
        buttons: list[Button] = []
        x = left
        for label, intent in entries:
            button = Button.at(self.font, x, y, label, intent)
            buttons.append(button)
            x = button.rect.right + 2
        return buttons

    @property
    def buttons(self) -> list[Button]:
        return [
            *self.top_buttons,
            *self.part_buttons,
            *self.tool_buttons,
            *self.shape_buttons,
            *self.edit_buttons,
            self.fill_button,
            self.guide_button,
            self.starter_button,
            self.preview_button,
        ]

    def _did(self, deed: str) -> None:
        """Say that the player has done something the opening of a new settlement may be waiting for."""
        if self.on_deed is not None:
            self.on_deed(deed)

    def _hint_rect(self, hint: str | None) -> pygame.Rect | None:
        """Where on the screen what a lesson is about is."""
        if hint == "palette":
            return self.swatches[0][0].unionall([rect for rect, _ in self.swatches])
        if hint == "canvas":
            return self.area
        if hint == "tools":
            return self.tool_buttons[0].rect.unionall([button.rect for button in self.tool_buttons])
        if hint == "edit":
            return self.edit_buttons[0].rect.unionall([button.rect for button in self.edit_buttons])
        if hint == "parts":
            return self.part_buttons[0].rect.unionall([button.rect for button in self.part_buttons])
        if hint == "save":
            return next(button.rect for button in self.top_buttons if button.intent == ("save",))
        return None

    def _rooms(self) -> list[str]:
        return [room_id for room_id, room in self.world.rooms.items() if room.roofed]

    def open(self, room_id: str | None) -> None:
        """Start drawing a roofed room, from its saved parts if it has any."""
        rooms = self._rooms()
        self.room_id = room_id if room_id in rooms else (rooms[0] if rooms else None)
        self.closed = self.room_id is None
        self.notice = ""
        self._undo = []
        self._stroke = None
        if self.room_id is None:
            return
        room = self.world.rooms[self.room_id]
        size = building_canvas_size(room)
        self.area = pygame.Rect(DRAWING_AT, size)
        kept = self.buildings.drawings(room)
        self.drawings = {}
        for part in BUILDING_PARTS:
            surface = pygame.Surface(size, pygame.SRCALPHA)
            if part in kept:
                surface.blit(kept[part], (0, 0))
            self.drawings[part] = surface
        self._set_part(self.part)

    def _set_part(self, part: str) -> None:
        if part not in BUILDING_PARTS or self.room_id is None:
            return
        self.part = part
        self.guide_picture = self._named_guide(part)
        self._stroke = None
        self._draft = None

    def _named_guide(self, part: str) -> pygame.Surface:
        """The guide of a part with each of its stretches named on it."""
        room = self.world.rooms[self.room_id]
        guide = self.buildings.guide(room, part)
        for name, rect in self.buildings.zones(room, part):
            label = self.font.render(ZONE_NAMES.get(name, name), PALETTE["ink"])
            spot = label.get_rect(topleft=(rect.x + 3, rect.y + 3))
            if rect.height > rect.width or label.get_width() + 6 > rect.width:
                # Taller than it is wide, or too narrow to be written across: up its side, half way along it.
                label = pygame.transform.rotate(label, 90)
                spot = label.get_rect(midleft=(rect.x + 3, rect.centery))
            spot = spot.clamp(guide.get_rect())
            backing = pygame.Surface(spot.inflate(2, 2).size, pygame.SRCALPHA)
            backing.fill((*PALETTE["paper"], 190))
            guide.blit(backing, spot.inflate(2, 2))
            guide.blit(label, spot)
        return guide

    def _remember(self) -> None:
        self._undo.append((self.part, self.drawings[self.part].copy()))
        del self._undo[:-UNDO_STEPS]

    def undo(self) -> None:
        if self._undo:
            part, surface = self._undo.pop()
            self.drawings[part] = surface
            self._set_part(part)
            self._did(UNDO_DEED)

    def clear(self) -> None:
        self._remember()
        self.drawings[self.part].fill(TRANSPARENT)

    def starter(self) -> None:
        if self.room_id is None:
            return
        self._remember()
        self.drawings[self.part] = self.buildings.starter(self.world.rooms[self.room_id], self.part)

    def save(self) -> bool:
        """Write all four aligned drawings. Returns whether it worked."""
        if self.room_id is None:
            return False
        try:
            for part, surface in self.drawings.items():
                path = self.root / building_part_path(self.room_id, part)
                path.parent.mkdir(parents=True, exist_ok=True)
                pygame.image.save(surface, str(path))
        except (OSError, pygame.error):
            self.notice = "No se pudo guardar"
            return False
        self.buildings.forget(self.room_id)
        if self.on_saved is not None:
            self.on_saved(self.room_id)
        self.notice = SAVED_TEXT
        self._did(BUILDING_DRAWN_DEED)
        return True

    def step(self, by: int) -> None:
        rooms = self._rooms()
        if self.room_id in rooms:
            self.open(rooms[(rooms.index(self.room_id) + by) % len(rooms)])

    def _pick(self, position: tuple[int, int]) -> None:
        """Take the colour under the mouse off the field: any colour, not only the ready ones."""
        self.color = self.field.color_at(position)
        if self.tool == ERASER_TOOL:
            self.tool = BRUSH_TOOL
        self._did(COLOR_DEED)

    def _shape_press(self, at: tuple[int, int]) -> None:
        """Begin a shape on the paper, or put down the next corner of the polygon being made."""
        draft = self._draft
        if draft is not None and draft.tool == POLYGON_TOOL:
            if draft.corner(at):
                self._lay_down()
            return
        self._draft = ShapeDraft(self.tool, "", at)
        if self.tool == POLYGON_TOOL:
            self.notice = POLYGON_NOTICE

    def _lay_down(self) -> None:
        """Put the shape in hand on the part being drawn for good. A polygon of fewer than three corners is nothing."""
        draft, self._draft = self._draft, None
        if draft is None or (draft.tool == POLYGON_TOOL and len(draft.fixed) < 3):
            return
        self._remember()
        draft.paint(self.drawings[self.part], self.color, self.size, self.filled)
        self.notice = ""
        self._did(STROKE_DEED)

    def _apply(self, intent: tuple) -> None:
        if intent[0] == "tool":
            self.tool = intent[1]
            # Whatever shape was half made with the other tool is let go of.
            self._draft = None
        elif intent[0] == "fill":
            self.filled = not self.filled
            self.fill_button.label = FILLED_LABEL if self.filled else HOLLOW_LABEL
            self.fill_button.rect.width = self.font.width(self.fill_button.label) + 8
        elif intent[0] == "undo":
            self.undo()
        elif intent[0] == "clear":
            self.clear()
        elif intent[0] == "guide":
            order = (GUIDE_UNDER, GUIDE_OVER, GUIDE_OFF)
            self.guide = order[(order.index(self.guide) + 1) % len(order)]
            self.guide_button.label = GUIDE_LABELS[self.guide]
        elif intent[0] == "starter":
            self.starter()
        elif intent[0] == "part":
            self._set_part(intent[1])
            self._did(PART_DEED)
        elif intent[0] == "preview":
            self.roof_on = not self.roof_on
            self.preview_button.label = "Vista: tejado" if self.roof_on else "Vista: interior"
        elif intent[0] == "step":
            self.step(intent[1])
        elif intent[0] == "save":
            self.save()
        elif intent[0] == "close":
            self.closed = True

    def _paint(self, start: tuple[int, int], end: tuple[int, int]) -> None:
        surface = self.drawings[self.part]
        color = TRANSPARENT if self.tool == ERASER_TOOL else (*self.color, 255)
        radius = max(1, self.size // 2)
        pygame.draw.line(surface, color, start, end, max(1, self.size))
        pygame.draw.circle(surface, color, start, radius)
        pygame.draw.circle(surface, color, end, radius)

    def _fill(self, at: tuple[int, int]) -> None:
        surface = self.drawings[self.part]
        alike = pygame.mask.from_threshold(surface, surface.get_at(at), (1, 1, 1, 1))
        alike.connected_component(at).to_surface(surface, setcolor=(*self.color, 255), unsetcolor=None)

    def press(self, position: tuple[int, int]) -> None:
        if self.area.collidepoint(position) and self.tool in SHAPE_LABELS:
            self._shape_press((position[0] - self.area.x, position[1] - self.area.y))
            return
        if self.field.contains(position):
            self._picking = True
            self._pick(position)
            return
        if self.area.collidepoint(position):
            at = (position[0] - self.area.x, position[1] - self.area.y)
            self._remember()
            if self.tool == FILL_TOOL:
                self._fill(at)
                self._did(FILL_DEED)
            else:
                self._paint(at, at)
                self._stroke = at
            return
        for button in self.buttons:
            if button.contains(position):
                self._apply(button.intent)
                return
        for rect, color in self.swatches:
            if rect.collidepoint(position):
                self.color = color
                if self.tool == ERASER_TOOL:
                    self.tool = BRUSH_TOOL
                self._did(COLOR_DEED)
                return
        for rect, size in self.brush_buttons:
            if rect.collidepoint(position):
                self.size = size
                return

    def drag(self, position: tuple[int, int]) -> None:
        if self._picking:
            self._pick(position)
            return
        if self._draft is not None:
            self._draft.move((position[0] - self.area.x, position[1] - self.area.y))
            return
        if self._stroke is None:
            return
        at = (position[0] - self.area.x, position[1] - self.area.y)
        self._paint(self._stroke, at)
        self._stroke = at

    def release(self) -> None:
        self._picking = False
        if self._draft is not None and self._draft.tool != POLYGON_TOOL:
            # Let go where it was pressed, it is no shape at all.
            if self._draft.drawn:
                self._lay_down()
            else:
                self._draft = None
        if self._stroke is not None:
            self._stroke = None
            self._did(STROKE_DEED)

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            self.press(canvas_position(event.pos))
        elif event.type == pygame.MOUSEMOTION:
            self.drag(canvas_position(event.pos))
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            self.release()
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 3 and self._draft is not None:
            self._lay_down()
        elif event.type == pygame.KEYDOWN and event.key in (pygame.K_RETURN, pygame.K_KP_ENTER) and self._draft is not None:
            self._lay_down()
        elif event.type == pygame.KEYDOWN and event.key == pygame.K_z and event.mod & pygame.KMOD_CTRL:
            self.undo()
        elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE and self._draft is not None:
            # Out of the shape, not out of the drawing.
            self._draft, self.notice = None, ""
        elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self.closed = True

    def update(self, dt: float) -> None:
        self.time += dt

    def render(self) -> None:
        self.layers.clear()
        self.canvas.fill(PALETTE["ink"])
        room = self.world.rooms.get(self.room_id or "")
        title = f"Dibujar {room.name}" if room is not None else "Dibujar edificio"
        self.font.draw(self.canvas, title, (TOOLS_LEFT, 4), PALETTE["glow"], scale=2)
        self.font.draw(
            self.canvas,
            self.notice or "El tiempo está detenido",
            (TOOLS_LEFT, 30),
            PALETTE["lamp" if self.notice else "stone"],
        )
        for button in self.top_buttons:
            button.draw(self.canvas, self.font)

        self.font.draw(self.canvas, "Color", (TOOLS_LEFT, 44), PALETTE["dust"])
        draw_chosen(self.canvas, CHOSEN, self.color)
        self.field.draw(self.canvas)
        for button in self.shape_buttons:
            button.draw(self.canvas, self.font, active=button.intent == ("tool", self.tool))
        self.fill_button.draw(self.canvas, self.font, active=self.filled)
        for rect, color in self.swatches:
            pygame.draw.rect(self.canvas, color, rect.inflate(-2, -2))
            if color == self.color and self.tool != ERASER_TOOL:
                pygame.draw.rect(self.canvas, PALETTE["paper"], rect, 1)
        for rect, size in self.brush_buttons:
            draw_panel(self.canvas, rect, fill="shadow", border="lamp" if size == self.size else "iron")
            pygame.draw.circle(self.canvas, PALETTE["bone"], rect.center, max(1, size // 2))
        for button in self.tool_buttons:
            button.draw(self.canvas, self.font, active=button.intent == ("tool", self.tool))
        for button in (*self.edit_buttons, self.guide_button, self.starter_button):
            button.draw(self.canvas, self.font)
        for button in self.part_buttons:
            button.draw(self.canvas, self.font, active=button.intent == ("part", self.part))

        pygame.draw.rect(self.canvas, PALETTE["stone"], self.area.inflate(2, 2), 1)
        self.canvas.fill(TRANSPARENT, self.area)
        self.layers.under(self._show_drawing)

        self.font.draw(self.canvas, "Edificio", (PREVIEW.x, PREVIEW.y - LINE_HEIGHT - 1), PALETTE["dust"])
        pygame.draw.rect(self.canvas, PALETTE["stone"], PREVIEW.inflate(2, 2), 1)
        self.canvas.fill(TRANSPARENT, PREVIEW)
        self.layers.under(self._show_preview)
        self.preview_button.draw(self.canvas, self.font)

        lesson = lesson_for(self.world, focus=BUILDING_ART_FOCUS)
        if lesson is not None:
            # While the opening of a new settlement teaches drawing, the lesson goes where the notes do.
            draw_lesson(self.canvas, self.font, NOTES, self.world, lesson)
            draw_hint(self.canvas, self._hint_rect(lesson.hint), self.time)
            return
        y = NOTES.y
        for note in NOTES_TEXT:
            for line in self.font.wrap(note, NOTES.width):
                self.font.draw(self.canvas, line, (NOTES.x, y), PALETTE["bone"])
                y += LINE_HEIGHT
            y += 4

    def _show_drawing(self, screen: pygame.Surface) -> None:
        place = self.layers.on_screen(self.area)
        screen.fill(PAPER, place)
        if self.guide == GUIDE_UNDER:
            self.guide_picture.set_alpha(GUIDE_ALPHA[GUIDE_UNDER])
            screen.blit(pygame.transform.scale(self.guide_picture, place.size), place)
        picture = self.drawings[self.part]
        if self._draft is not None:
            # The shape in hand is seen on the paper before it is on it.
            picture = self._draft.shown_on(picture, self.color, self.size, self.filled)
        screen.blit(pygame.transform.scale(picture, place.size), place)
        if self.guide == GUIDE_OVER:
            self.guide_picture.set_alpha(GUIDE_ALPHA[GUIDE_OVER])
            screen.blit(pygame.transform.scale(self.guide_picture, place.size), place)

    def _show_preview(self, screen: pygame.Surface) -> None:
        place = self.layers.on_screen(PREVIEW)
        screen.fill(PALETTE["earth"], place)
        order = (
            (INSIDE_PART, WALLS_PART, DOOR_PART, ROOF_PART)
            if self.roof_on
            else (INSIDE_PART, WALLS_PART, DOOR_PART)
        )
        source = pygame.Surface(self.area.size, pygame.SRCALPHA)
        for part in order:
            source.blit(self.drawings[part], (0, 0))
        scale = min(place.width / source.get_width(), place.height / source.get_height())
        size = (max(1, round(source.get_width() * scale)), max(1, round(source.get_height() * scale)))
        picture = pygame.transform.smoothscale(source, size)
        screen.blit(picture, picture.get_rect(center=place.center))
