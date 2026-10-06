"""Where a kind of furniture or loose object is drawn: one picture that every one of its kind wears."""

from collections.abc import Callable
from pathlib import Path

import pygame

from graphics.font import LINE_HEIGHT, BitmapFont
from graphics.object_art import ABOVE_FILL, GROUND_FILL, ObjectArtStore, object_art_path
from graphics.palette import PALETTE
from graphics.screen_layers import TRANSPARENT, ScreenLayers
from scenes.scene import canvas_position
from simulation.world import SimulationWorld
from ui.button import Button
from ui.panel import draw_panel
from ui.tutorial_panel import (
    COLOR_DEED,
    FILL_DEED,
    STROKE_DEED,
    UNDO_DEED,
    draw_hint,
    draw_lesson,
    lesson_for,
    object_drawn_deed,
)

DRAWING_AT = (196, 58)
# The most room the drawing is given on the canvas, and how large one of its pixels may be shown.
DRAWING_ROOM = (400, 380)
MAX_ZOOM = 4
PREVIEW = pygame.Rect(620, 64, 172, 128)
NOTES = pygame.Rect(620, 220, 172, 220)
TOOLS_LEFT = 8
SWATCH = (28, 16)
SWATCHES_PER_ROW = 6
BRUSHES = (2, 4, 8, 14)
BRUSH_TOOL, ERASER_TOOL, FILL_TOOL = "brush", "eraser", "fill"
TOOL_LABELS = {BRUSH_TOOL: "Pincel", ERASER_TOOL: "Goma", FILL_TOOL: "Cubo"}
GUIDE_UNDER, GUIDE_OVER, GUIDE_OFF = "under", "over", "off"
GUIDE_LABELS = {GUIDE_UNDER: "Calco: debajo", GUIDE_OVER: "Calco: encima", GUIDE_OFF: "Calco: quitado"}
GUIDE_ALPHA = {GUIDE_UNDER: 160, GUIDE_OVER: 90}
# What the colours of the guide mean, said beside the paper: a drawing this small has no room for words.
LEGEND = (
    (GROUND_FILL, "Suelo que ocupa, casilla a casilla"),
    (ABOVE_FILL, "Lo que se alza por encima"),
    (None, "Debajo, el del juego como ejemplo"),
)
LEGEND_WIDTH = 150
UNDO_STEPS = 30
PAPER = PALETTE["bone"]
SAVED_TEXT = "Guardado: así se ven ya todos los de su clase"
NOTES_TEXT = (
    "Se ve desde arriba y un poco de frente, como todo en el mapa.",
    "La zona naranja es el suelo que ocupa, casilla a casilla. La azul es lo que se alza por encima y tapa lo de detrás.",
    "Debajo se ve el del juego, de ejemplo: fíjate en su tamaño y desde dónde se mira. Lo que quede sin pintar deja ver el suelo.",
    "Arte de partida lo pone sobre el papel. Ctrl+Z deshace, Esc vuelve sin guardar.",
)


class ObjectEditor:
    """Draw a kind of object. Simulation time stands still while it is open."""

    def __init__(
        self,
        canvas: pygame.Surface,
        world: SimulationWorld,
        font: BitmapFont,
        layers: ScreenLayers,
        root: Path,
        objects: ObjectArtStore,
        on_saved: Callable[[str], None] | None = None,
        on_deed: Callable[[str], None] | None = None,
    ) -> None:
        self.canvas = canvas
        self.world = world
        self.font = font
        self.layers = layers
        self.root = root
        self.objects = objects
        self.on_saved = on_saved
        self.on_deed = on_deed
        self.closed = True
        self.kind: str | None = None
        self.drawing = pygame.Surface((1, 1), pygame.SRCALPHA)
        self.guide_picture = pygame.Surface((1, 1), pygame.SRCALPHA)
        self.area = pygame.Rect(DRAWING_AT, (1, 1))
        # Canvas pixels to one of the drawing's.
        self.zoom = 1
        self.colors = list(PALETTE.values())
        self.color = PALETTE["ink"]
        self.size = BRUSHES[1]
        self.tool = BRUSH_TOOL
        self.guide = GUIDE_UNDER
        self.notice = ""
        self.time = 0.0
        self._undo: list[pygame.Surface] = []
        self._stroke: tuple[int, int] | None = None

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
            (pygame.Rect(TOOLS_LEFT + index * 42, y, 40, 26), size) for index, size in enumerate(BRUSHES)
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
        self.top_buttons = self._row(6, [("Guardar", ("save",)), ("Volver", ("close",))], left=620)

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
        return [*self.top_buttons, *self.tool_buttons, *self.edit_buttons, self.guide_button, self.starter_button]

    def open(self, kind: str | None) -> None:
        """Start drawing a kind of object, from what has been drawn of it so far."""
        definition = self.world.registries.interactables.find(kind or "")
        self.kind = kind if definition is not None else None
        self.closed = definition is None
        self.notice = ""
        self._undo = []
        self._stroke = None
        if definition is None:
            return
        size = self.objects.canvas_size(definition)
        self.zoom = max(1, min(MAX_ZOOM, DRAWING_ROOM[0] // size[0], DRAWING_ROOM[1] // size[1]))
        self.area = pygame.Rect(DRAWING_AT, (size[0] * self.zoom, size[1] * self.zoom))
        self.drawing = pygame.Surface(size, pygame.SRCALPHA)
        kept = self.objects.drawing(definition)
        if kept is not None:
            self.drawing.blit(kept, (0, 0))
        self.guide_picture = self.objects.guide(definition)

    def _did(self, deed: str) -> None:
        if self.on_deed is not None:
            self.on_deed(deed)

    def _remember(self) -> None:
        self._undo.append(self.drawing.copy())
        del self._undo[:-UNDO_STEPS]

    def undo(self) -> None:
        if self._undo:
            self.drawing = self._undo.pop()
            self._did(UNDO_DEED)

    def clear(self) -> None:
        self._remember()
        self.drawing.fill(TRANSPARENT)

    def starter(self) -> None:
        """Put the game's own picture of the kind on the paper, to be drawn over."""
        definition = self.world.registries.interactables.find(self.kind or "")
        if definition is not None:
            self._remember()
            self.drawing = self.objects.starter(definition)

    def save(self) -> bool:
        """Write the drawing where the game looks for it. Returns whether it worked."""
        if self.kind is None:
            return False
        try:
            path = self.root / object_art_path(self.kind)
            path.parent.mkdir(parents=True, exist_ok=True)
            pygame.image.save(self.drawing, str(path))
        except (OSError, pygame.error):
            self.notice = "No se pudo guardar"
            return False
        self.objects.forget(self.kind)
        if self.on_saved is not None:
            self.on_saved(self.kind)
        self.notice = SAVED_TEXT
        self._did(object_drawn_deed(self.kind))
        return True

    def _apply(self, intent: tuple) -> None:
        if intent[0] == "tool":
            self.tool = intent[1]
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
        elif intent[0] == "save":
            self.save()
        elif intent[0] == "close":
            self.closed = True

    def _point(self, position: tuple[int, int]) -> tuple[int, int]:
        """The pixel of the drawing under a position on the game's canvas."""
        return ((position[0] - self.area.x) // self.zoom, (position[1] - self.area.y) // self.zoom)

    def _paint(self, start: tuple[int, int], end: tuple[int, int]) -> None:
        color = TRANSPARENT if self.tool == ERASER_TOOL else (*self.color, 255)
        radius = max(1, self.size // 2)
        pygame.draw.line(self.drawing, color, start, end, max(1, self.size))
        pygame.draw.circle(self.drawing, color, start, radius)
        pygame.draw.circle(self.drawing, color, end, radius)

    def _fill(self, at: tuple[int, int]) -> None:
        alike = pygame.mask.from_threshold(self.drawing, self.drawing.get_at(at), (1, 1, 1, 1))
        alike.connected_component(at).to_surface(self.drawing, setcolor=(*self.color, 255), unsetcolor=None)

    def press(self, position: tuple[int, int]) -> None:
        if self.area.collidepoint(position):
            at = self._point(position)
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
        if self._stroke is None:
            return
        at = self._point(position)
        self._paint(self._stroke, at)
        self._stroke = at

    def release(self) -> None:
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
        elif event.type == pygame.KEYDOWN and event.key == pygame.K_z and event.mod & pygame.KMOD_CTRL:
            self.undo()
        elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self.closed = True

    def update(self, dt: float) -> None:
        self.time += dt

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
        if hint == "save":
            return self.top_buttons[0].rect
        return None

    def render(self) -> None:
        self.layers.clear()
        canvas, font = self.canvas, self.font
        canvas.fill(PALETTE["ink"])
        definition = self.world.registries.interactables.find(self.kind or "")
        title = f"Dibujar {definition.name}" if definition is not None else "Dibujar objeto"
        font.draw(canvas, title, (TOOLS_LEFT, 4), PALETTE["glow"], scale=2)
        font.draw(canvas, self.notice or "El tiempo está detenido", (TOOLS_LEFT, 30), PALETTE["lamp" if self.notice else "stone"])
        for button in self.top_buttons:
            button.draw(canvas, font)

        font.draw(canvas, "Color", (TOOLS_LEFT, 44), PALETTE["dust"])
        for rect, color in self.swatches:
            pygame.draw.rect(canvas, color, rect.inflate(-2, -2))
            if color == self.color and self.tool != ERASER_TOOL:
                pygame.draw.rect(canvas, PALETTE["paper"], rect, 1)
        for rect, size in self.brush_buttons:
            draw_panel(canvas, rect, fill="shadow", border="lamp" if size == self.size else "iron")
            pygame.draw.circle(canvas, PALETTE["bone"], rect.center, max(1, size * self.zoom // 2))
        for button in self.tool_buttons:
            button.draw(canvas, font, active=button.intent == ("tool", self.tool))
        for button in (*self.edit_buttons, self.guide_button, self.starter_button):
            button.draw(canvas, font)

        font.draw(canvas, "Papel", (self.area.x, self.area.y - LINE_HEIGHT - 1), PALETTE["dust"])
        pygame.draw.rect(canvas, PALETTE["stone"], self.area.inflate(2, 2), 1)
        canvas.fill(TRANSPARENT, self.area)
        self.layers.under(self._show_drawing)

        self._render_legend()
        font.draw(canvas, "Así se ve en el mapa", (PREVIEW.x, PREVIEW.y - LINE_HEIGHT - 1), PALETTE["dust"])
        pygame.draw.rect(canvas, PALETTE["stone"], PREVIEW.inflate(2, 2), 1)
        canvas.fill(TRANSPARENT, PREVIEW)
        self.layers.under(self._show_preview)

        lesson = lesson_for(self.world, deed=object_drawn_deed(self.kind or ""))
        if lesson is not None:
            draw_lesson(canvas, font, NOTES, self.world, lesson)
            draw_hint(canvas, self._hint_rect(lesson.hint), self.time)
            return
        y = NOTES.y
        for note in NOTES_TEXT:
            for line in font.wrap(note, NOTES.width):
                font.draw(canvas, line, (NOTES.x, y), PALETTE["bone"])
                y += LINE_HEIGHT
            y += 4

    def _render_legend(self) -> None:
        """Say what the guide shows: beside the paper where there is room, or else under it."""
        beside = self.area.right + 12 + LEGEND_WIDTH <= PREVIEW.x
        x, y = (self.area.right + 12, self.area.y) if beside else (self.area.x, self.area.bottom + 6)
        for fill, text in LEGEND:
            if fill is not None:
                swatch = pygame.Rect(x, y + 1, 9, 9)
                pygame.draw.rect(self.canvas, PAPER, swatch)
                tint = pygame.Surface(swatch.size, pygame.SRCALPHA)
                tint.fill((*fill[:3], 200))
                self.canvas.blit(tint, swatch)
                pygame.draw.rect(self.canvas, PALETTE["stone"], swatch, 1)
            for line in self.font.wrap(text, LEGEND_WIDTH - 14):
                self.font.draw(self.canvas, line, (x + 14, y), PALETTE["bone"])
                y += LINE_HEIGHT
            y += 3

    def _show_drawing(self, screen: pygame.Surface) -> None:
        place = self.layers.on_screen(self.area)
        screen.fill(PAPER, place)
        if self.guide == GUIDE_UNDER:
            self.guide_picture.set_alpha(GUIDE_ALPHA[GUIDE_UNDER])
            screen.blit(pygame.transform.scale(self.guide_picture, place.size), place)
        screen.blit(pygame.transform.scale(self.drawing, place.size), place)
        if self.guide == GUIDE_OVER:
            self.guide_picture.set_alpha(GUIDE_ALPHA[GUIDE_OVER])
            screen.blit(pygame.transform.scale(self.guide_picture, place.size), place)

    def _show_preview(self, screen: pygame.Surface) -> None:
        """The object on bare ground, at the size the window shows it at the default zoom, and at twice that."""
        place = self.layers.on_screen(PREVIEW)
        screen.fill(PALETTE["earth"], place)
        width, height = self.drawing.get_size()
        before = screen.get_clip()
        screen.set_clip(place)
        x = place.x + 16
        for share in (2, 1):
            size = (max(1, width // share), max(1, height // share))
            picture = pygame.transform.smoothscale(self.drawing, size)
            screen.blit(picture, (x, place.bottom - 16 - size[1]))
            x += size[0] + 24
        screen.set_clip(before)
