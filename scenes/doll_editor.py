"""Where a resident's body and head are drawn: two canvases over a guide, and the result moving beside them."""

from collections.abc import Callable
from pathlib import Path

import pygame

from graphics.body_renderer import BodyRenderer
from graphics.doll import BODY_CANVAS, DOLL_FACINGS, HEAD_CANVAS, Doll, DollStore, doll_path, draw_doll
from graphics.font import LINE_HEIGHT, BitmapFont
from graphics.palette import PALETTE
from graphics.screen_layers import TRANSPARENT, ScreenLayers
from scenes.scene import canvas_position
from simulation.world import SimulationWorld
from skeleton.plan import SkeletonPlan
from skeleton.rig import Skeleton
from ui.button import Button
from ui.panel import draw_panel

BODY_AT = (196, 58)
HEAD_AT = (530, 58)
PREVIEW = pygame.Rect(530, 272, 192, 170)
NOTES = pygame.Rect(8, 272, 180, 174)
TOOLS_LEFT = 8
SWATCH = (28, 16)
SWATCHES_PER_ROW = 6
BRUSHES = (2, 5, 10, 18)
BRUSH_TOOL, ERASER_TOOL, FILL_TOOL = "brush", "eraser", "fill"
TOOL_LABELS = {BRUSH_TOOL: "Pincel", ERASER_TOOL: "Goma", FILL_TOOL: "Cubo"}
# Where the guide is shown: under the drawing, over it, or not at all.
GUIDE_UNDER, GUIDE_OVER, GUIDE_OFF = "under", "over", "off"
GUIDE_LABELS = {GUIDE_UNDER: "Calco: debajo", GUIDE_OVER: "Calco: encima", GUIDE_OFF: "Calco: quitado"}
GUIDE_ALPHA = {GUIDE_UNDER: 120, GUIDE_OVER: 70}
UNDO_STEPS = 30
PAPER = PALETTE["bone"]
# Window pixels to one of the skeleton's in the preview, and how fast it goes through its clips.
PREVIEW_DETAIL = 9.0
PREVIEW_RATE = 1.2
PREVIEW_CLIPS = ("walk", "idle", "work", "fight")
PREVIEW_SECONDS = 4.0
SAVED_TEXT = "Guardado: ya anda así por el asentamiento"
NOTES_TEXT = (
    "Cada marco es una pieza: lo que pintes dentro se mueve con ella.",
    "La figura fina es solo un ejemplo. Hazlo más gordo o con la forma que quieras, hasta el marco.",
    "Naranja: lado de delante. Azul: el de detrás. Puntos rojos: articulaciones. El cuello va aparte, sobre los hombros.",
    "Mira a la derecha. Ctrl+Z deshace, Esc vuelve sin guardar.",
)


class DollEditor:
    """Draw a resident. Time stands still while it is open.

    The canvases are as large on the window as two of its pixels to one of the drawing's, which is
    one pixel of the game's own canvas: nothing has to be scaled by a fraction.
    """

    def __init__(
        self,
        canvas: pygame.Surface,
        world: SimulationWorld,
        font: BitmapFont,
        layers: ScreenLayers,
        root: Path,
        dolls: DollStore,
        plan: SkeletonPlan,
        bodies: BodyRenderer,
        on_saved: Callable[[str], None] | None = None,
    ) -> None:
        self.canvas = canvas
        self.world = world
        self.font = font
        self.layers = layers
        self.root = root
        self.dolls = dolls
        self.plan = plan
        self.bodies = bodies
        self.on_saved = on_saved
        self.template = dolls.template
        self.closed = False
        self.resident_id: str | None = None
        self.drawings: dict[str, pygame.Surface] = {}
        self.areas = {
            BODY_CANVAS: pygame.Rect(BODY_AT, self.template.canvases[BODY_CANVAS]),
            HEAD_CANVAS: pygame.Rect(HEAD_AT, self.template.canvases[HEAD_CANVAS]),
        }
        self.guides = {name: self.template.guide(name) for name in self.areas}
        self.colors = list(PALETTE.values())
        self.color = PALETTE["ink"]
        self.size = BRUSHES[1]
        self.tool = BRUSH_TOOL
        self.guide = GUIDE_UNDER
        self.notice = ""
        self.time = 0.0
        self._undo: list[tuple[str, pygame.Surface]] = []
        # The canvas being drawn on and where the stroke last was, while the button is held.
        self._stroke: tuple[str, tuple[int, int]] | None = None
        self._preview: Doll | None = None

        self.swatches = [
            (pygame.Rect(TOOLS_LEFT + (index % SWATCHES_PER_ROW) * SWATCH[0], 58 + (index // SWATCHES_PER_ROW) * SWATCH[1], *SWATCH), color)
            for index, color in enumerate(self.colors)
        ]
        y = self.swatches[-1][0].bottom + 8
        self.brush_buttons = [(pygame.Rect(TOOLS_LEFT + index * 42, y, 40, 26), size) for index, size in enumerate(BRUSHES)]
        y += 32
        self.tool_buttons = self._row(y, [(TOOL_LABELS[tool], ("tool", tool)) for tool in TOOL_LABELS])
        y += 18
        self.edit_buttons = self._row(y, [("Deshacer", ("undo",)), ("Limpiar", ("clear",))])
        y += 18
        self.guide_button = Button.at(font, TOOLS_LEFT, y, GUIDE_LABELS[GUIDE_UNDER], ("guide",))
        self.guide_button.rect.width = 110
        y += 18
        self.mannequin_button = Button.at(font, TOOLS_LEFT, y, "Maniquí de partida", ("mannequin",))
        self.top_buttons = self._row(6, [("<", ("step", -1)), (">", ("step", 1)), ("Guardar", ("save",)), ("Volver", ("close",))], left=530)

    def _row(self, y: int, entries: list[tuple[str, tuple]], left: int = TOOLS_LEFT) -> list[Button]:
        buttons, x = [], left
        for label, intent in entries:
            button = Button.at(self.font, x, y, label, intent)
            buttons.append(button)
            x = button.rect.right + 3
        return buttons

    @property
    def buttons(self) -> list[Button]:
        return [*self.top_buttons, *self.tool_buttons, *self.edit_buttons, self.guide_button, self.mannequin_button]

    def open(self, resident_id: str | None) -> None:
        """Start drawing a resident, from what has been drawn of them so far."""
        residents = list(self.world.residents)
        self.resident_id = resident_id if resident_id in self.world.residents else (residents[0] if residents else None)
        self.closed = self.resident_id is None
        self.notice = ""
        self._undo = []
        self._stroke = None
        kept = self.dolls.drawings(self.resident_id) if self.resident_id is not None else {}
        self.drawings = {}
        for name, size in self.template.canvases.items():
            surface = pygame.Surface(size, pygame.SRCALPHA)
            if name in kept:
                picture = kept[name]
                surface.blit(picture if picture.get_size() == size else pygame.transform.smoothscale(picture, size), (0, 0))
            self.drawings[name] = surface
        self._cut()

    def _cut(self) -> None:
        """Cut the drawings as they stand into a doll, to be seen moving in the preview."""
        self._preview = Doll(self.template, self.drawings)

    def _remember(self, name: str) -> None:
        self._undo.append((name, self.drawings[name].copy()))
        del self._undo[:-UNDO_STEPS]

    def undo(self) -> None:
        if self._undo:
            name, surface = self._undo.pop()
            self.drawings[name] = surface
            self._cut()

    def clear(self) -> None:
        for name in self.drawings:
            self._remember(name)
            self.drawings[name].fill(TRANSPARENT)
        self._cut()

    def mannequin(self) -> None:
        """Fill every zone with a plain figure in the colours the resident has worn until now."""
        skin = self.bodies.skin(self.resident_id)

        def strip(cell: str, end: int) -> tuple[int, int, int]:
            return skin.strips[("side", cell)].colors[end]

        def middle(cell: str) -> tuple[int, int, int]:
            sprite = skin.sprites[("side", cell, False)]
            return tuple(sprite.image.get_at(sprite.anchor))[:3]

        colors = {"spine": middle("torso"), "skull": middle("head"), "neck": middle("head"), "hips": strip("thigh", 0)}
        for side in ("_left", "_right"):
            colors[f"upper_arm{side}"] = strip("upper_arm", 0)
            colors[f"forearm{side}"] = strip("forearm", -1)
            colors[f"hand{side}"] = strip("forearm", -1)
            colors[f"thigh{side}"] = strip("thigh", 0)
            colors[f"shin{side}"] = strip("thigh", 0)
            colors[f"foot{side}"] = strip("shin", -1)
        for name, figure in self.template.mannequin(colors).items():
            self._remember(name)
            self.drawings[name] = figure
        self._cut()

    def save(self) -> bool:
        """Write both drawings where the game looks for them. Returns whether it worked."""
        if self.resident_id is None:
            return False
        try:
            for name, surface in self.drawings.items():
                path = self.root / doll_path(self.resident_id, name)
                path.parent.mkdir(parents=True, exist_ok=True)
                pygame.image.save(surface, str(path))
        except (OSError, pygame.error):
            self.notice = "No se pudo guardar"
            return False
        self.dolls.forget(self.resident_id)
        if self.on_saved is not None:
            self.on_saved(self.resident_id)
        self.notice = SAVED_TEXT
        return True

    def step(self, by: int) -> None:
        """Go on to the next resident, or back to the one before."""
        residents = list(self.world.residents)
        if self.resident_id in residents:
            self.open(residents[(residents.index(self.resident_id) + by) % len(residents)])

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
        elif intent[0] == "mannequin":
            self.mannequin()
        elif intent[0] == "step":
            self.step(intent[1])
        elif intent[0] == "save":
            self.save()
        elif intent[0] == "close":
            self.closed = True

    def _canvas_under(self, position: tuple[int, int]) -> tuple[str, tuple[int, int]] | None:
        """The drawing a position is on, and the pixel of it."""
        for name, area in self.areas.items():
            if area.collidepoint(position):
                return (name, (position[0] - area.x, position[1] - area.y))
        return None

    def _paint(self, name: str, start: tuple[int, int], end: tuple[int, int]) -> None:
        surface = self.drawings[name]
        color = TRANSPARENT if self.tool == ERASER_TOOL else (*self.color, 255)
        radius = max(1, self.size // 2)
        pygame.draw.line(surface, color, start, end, max(1, self.size))
        pygame.draw.circle(surface, color, start, radius)
        pygame.draw.circle(surface, color, end, radius)

    def _fill(self, name: str, at: tuple[int, int]) -> None:
        """Pour the colour into everything of the same colour that touches a pixel."""
        surface = self.drawings[name]
        alike = pygame.mask.from_threshold(surface, surface.get_at(at), (1, 1, 1, 1))
        alike.connected_component(at).to_surface(surface, setcolor=(*self.color, 255), unsetcolor=None)

    def press(self, position: tuple[int, int]) -> None:
        """Handle the left button going down at a position on the game's canvas."""
        on = self._canvas_under(position)
        if on is not None:
            name, at = on
            self._remember(name)
            if self.tool == FILL_TOOL:
                self._fill(name, at)
                self._cut()
            else:
                self._paint(name, at, at)
                self._stroke = on
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
                return
        for rect, size in self.brush_buttons:
            if rect.collidepoint(position):
                self.size = size
                return

    def drag(self, position: tuple[int, int]) -> None:
        """Go on with a stroke, on the drawing it began on, even past its edge."""
        if self._stroke is None:
            return
        name, last = self._stroke
        area = self.areas[name]
        at = (position[0] - area.x, position[1] - area.y)
        self._paint(name, last, at)
        self._stroke = (name, at)

    def release(self) -> None:
        if self._stroke is not None:
            self._stroke = None
            self._cut()

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

    def render(self) -> None:
        self.layers.clear()
        canvas, font = self.canvas, self.font
        canvas.fill(PALETTE["ink"])
        resident = self.world.residents.get(self.resident_id or "")
        title = f"Dibujar a {resident.name}" if resident is not None else "Dibujar"
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
            pygame.draw.circle(canvas, PALETTE["bone"], rect.center, max(1, size // 2))
        for button in self.tool_buttons:
            button.draw(canvas, font, active=button.intent == ("tool", self.tool))
        for button in (*self.edit_buttons, self.guide_button, self.mannequin_button):
            button.draw(canvas, font)

        for name, area in self.areas.items():
            label = "Cuerpo" if name == BODY_CANVAS else "Cabeza"
            font.draw(canvas, label, (area.x, area.y - LINE_HEIGHT - 1), PALETTE["dust"])
            pygame.draw.rect(canvas, PALETTE["stone"], area.inflate(2, 2), 1)
            canvas.fill(TRANSPARENT, area)
            self.layers.under(self._show_drawing(name, area))
        font.draw(canvas, "Así se mueve", (PREVIEW.x, PREVIEW.y - LINE_HEIGHT - 1), PALETTE["dust"])
        pygame.draw.rect(canvas, PALETTE["stone"], PREVIEW.inflate(2, 2), 1)
        canvas.fill(TRANSPARENT, PREVIEW)
        self.layers.under(self._show_preview)

        y = NOTES.y
        for note in NOTES_TEXT:
            for line in font.wrap(note, NOTES.width):
                font.draw(canvas, line, (NOTES.x, y), PALETTE["bone"])
                y += LINE_HEIGHT
            y += 3

    def _show_drawing(self, name: str, area: pygame.Rect) -> Callable[[pygame.Surface], None]:
        place = self.layers.on_screen(area)

        def draw(screen: pygame.Surface) -> None:
            screen.fill(PAPER, place)
            guide = self.guides[name]
            if self.guide == GUIDE_UNDER:
                guide.set_alpha(GUIDE_ALPHA[GUIDE_UNDER])
                screen.blit(pygame.transform.scale(guide, place.size), place)
            screen.blit(pygame.transform.scale(self.drawings[name], place.size), place)
            if self.guide == GUIDE_OVER:
                guide.set_alpha(GUIDE_ALPHA[GUIDE_OVER])
                screen.blit(pygame.transform.scale(guide, place.size), place)

        return draw

    def _show_preview(self, screen: pygame.Surface) -> None:
        """The doll going through its clips, facing one way and then the other."""
        place = self.layers.on_screen(PREVIEW)
        screen.fill(PALETTE["earth"], place)
        if self._preview is None:
            return
        turn = int(self.time / PREVIEW_SECONDS)
        clip = PREVIEW_CLIPS[turn % len(PREVIEW_CLIPS)]
        facing = DOLL_FACINGS["right" if (turn // len(PREVIEW_CLIPS)) % 2 == 0 else "left"]
        skeleton = Skeleton(self.plan, facing)
        skeleton.set_pose(self.plan.pose(facing, clip, self.time * PREVIEW_RATE))
        before = screen.get_clip()
        screen.set_clip(place)
        draw_doll(screen, self._preview, self.plan, skeleton, (place.centerx, place.bottom - 40), PREVIEW_DETAIL)
        screen.set_clip(before)
