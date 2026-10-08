"""In-game editor for an item's data and inventory icon."""

import json
from pathlib import Path

import pygame

from graphics.font import LINE_HEIGHT, BitmapFont
from graphics.item_icons import ItemIcons
from graphics.palette import PALETTE
from graphics.screen_layers import TRANSPARENT, ScreenLayers
from simulation.items.item import taste_tags
from scenes.scene import canvas_position
from simulation.items.custom_content import merged_item_data, validate_item_data
from simulation.world import SimulationWorld
from ui.button import Button
from ui.panel import draw_panel

ART_SIZE = (64, 64)
ART_AREA = pygame.Rect(190, 68, 256, 256)
TOOLS_LEFT = 8
FIELDS_LEFT = 470
FIELD_WIDTH = 322
FIELD_HEIGHT = 16
FIELD_STEP = 36
SWATCH = (27, 16)
SWATCHES_PER_ROW = 6
BRUSHES = (1, 3, 6, 10)
BRUSH_TOOL, ERASER_TOOL, FILL_TOOL = "brush", "eraser", "fill"
TOOL_LABELS = {BRUSH_TOOL: "Pincel", ERASER_TOOL: "Goma", FILL_TOOL: "Cubo"}
UNDO_STEPS = 30
FIELDS = (
    ("name", "Nombre"),
    ("article", "Artículo"),
    ("category", "Categoría"),
    ("base_value", "Valor base"),
    ("description", "Descripción"),
    ("tags", "Etiquetas de reglas (separadas por comas)"),
    ("preference_tags", "Gustos: a qué sabe o qué tiene (por comas)"),
    ("effects", "Efectos (nombre=numero, ... )"),
    ("properties", "Propiedades (nombre=numero, ... )"),
    ("spoils", "Se pocha: cuánto pierde al día, de 100 (0 si no se pocha)"),
)


def _number_text(values: dict[str, float]) -> str:
    return ", ".join(f"{name}={value:g}" for name, value in values.items())


def _parse_numbers(text: str) -> dict[str, float]:
    result: dict[str, float] = {}
    for entry in (part.strip() for part in text.split(",")):
        if not entry:
            continue
        if "=" not in entry:
            raise ValueError(f"Falta '=' en {entry}")
        name, raw = (part.strip() for part in entry.split("=", 1))
        if not name:
            raise ValueError("Hay un nombre vacío")
        result[name] = float(raw)
    return result


class ItemEditor:
    """Edit one stable item definition. Simulation time stands still while it is open."""

    def __init__(
        self,
        canvas: pygame.Surface,
        world: SimulationWorld,
        font: BitmapFont,
        root: Path,
        icons: ItemIcons,
        layers: ScreenLayers,
    ) -> None:
        self.canvas = canvas
        self.world = world
        self.font = font
        self.root = root
        self.icons = icons
        self.layers = layers
        self.closed = False
        self.item_id: str | None = None
        self.picture = pygame.Surface(ART_SIZE, pygame.SRCALPHA)
        self.values: dict[str, str] = {}
        self.active_field: str | None = None
        self.notice = ""
        self.colors = list(PALETTE.values())
        self.color = PALETTE["ink"]
        self.size = BRUSHES[1]
        self.tool = BRUSH_TOOL
        self._undo: list[pygame.Surface] = []
        self._stroke: tuple[int, int] | None = None

        self.top_buttons = self._row(
            6,
            [("Guardar", ("save",)), ("Volver", ("close",))],
            left=610,
        )
        self.swatches = [
            (
                pygame.Rect(
                    TOOLS_LEFT + (index % SWATCHES_PER_ROW) * SWATCH[0],
                    72 + (index // SWATCHES_PER_ROW) * SWATCH[1],
                    *SWATCH,
                ),
                color,
            )
            for index, color in enumerate(self.colors)
        ]
        y = self.swatches[-1][0].bottom + 8
        self.brush_buttons = [
            (pygame.Rect(TOOLS_LEFT + index * 40, y, 38, 24), size)
            for index, size in enumerate(BRUSHES)
        ]
        y += 30
        self.tool_buttons = self._row(y, [(label, ("tool", tool)) for tool, label in TOOL_LABELS.items()])
        y += 18
        self.edit_buttons = self._row(y, [("Deshacer", ("undo",)), ("Limpiar", ("clear",))])
        self.field_rects = {
            name: pygame.Rect(FIELDS_LEFT, 65 + index * FIELD_STEP, FIELD_WIDTH, FIELD_HEIGHT)
            for index, (name, _) in enumerate(FIELDS)
        }

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
        return [*self.top_buttons, *self.tool_buttons, *self.edit_buttons]

    def open(self, item_id: str) -> None:
        """Start from the live definition and the picture of the item as it stands."""
        definition = self.world.registries.items.resolve(item_id)
        self.item_id = item_id
        self.closed = False
        self.notice = ""
        self.active_field = None
        self._undo = []
        self._stroke = None
        self.values = {
            "name": definition.name,
            "article": definition.article,
            "category": definition.category,
            "base_value": str(definition.base_value),
            "description": definition.description,
            "tags": ", ".join(definition.tags),
            "preference_tags": ", ".join(definition.preference_tags),
            "effects": _number_text(definition.effects),
            "properties": _number_text(definition.properties),
            "spoils": f"{definition.spoils:g}",
        }
        # As it was last drawn, not the small icon of it: what was drawn here is still here to go on with.
        drawn = self.icons.picture(item_id)
        fit = pygame.transform.smoothscale if drawn.get_width() > ART_SIZE[0] else pygame.transform.scale
        self.picture = (drawn.copy() if drawn.get_size() == ART_SIZE else fit(drawn, ART_SIZE)).convert_alpha()

    def _remember(self) -> None:
        self._undo.append(self.picture.copy())
        del self._undo[:-UNDO_STEPS]

    def undo(self) -> None:
        if self._undo:
            self.picture = self._undo.pop()

    def clear(self) -> None:
        self._remember()
        self.picture.fill(TRANSPARENT)

    def _data(self) -> dict:
        if self.item_id is None:
            raise ValueError("No hay objeto seleccionado")
        try:
            base_value = int(self.values["base_value"].strip())
        except ValueError as error:
            raise ValueError("El valor base debe ser un número entero") from error
        try:
            spoils = float(self.values["spoils"].strip().replace(",", ".") or 0)
        except ValueError as error:
            raise ValueError("Lo que se pocha al día debe ser un número") from error
        if not 0 <= spoils <= 100:
            raise ValueError("Lo que se pocha al día va de 0 a 100")
        return {
            "id": self.item_id,
            "name": self.values["name"].strip(),
            "article": self.values["article"].strip(),
            "category": self.values["category"].strip(),
            "base_value": base_value,
            "description": self.values["description"].strip(),
            "tags": [tag.strip() for tag in self.values["tags"].split(",") if tag.strip()],
            "effects": _parse_numbers(self.values["effects"]),
            "properties": _parse_numbers(self.values["properties"]),
            # How much of its freshness, of a hundred, it loses in a day (S65).
            "spoils": spoils,
            # Written as they are kept: lower case, underscores for spaces, each of them once.
            "preference_tags": list(
                taste_tags([tag for tag in self.values["preference_tags"].split(",") if tag.strip()])
            ),
        }

    def save(self) -> bool:
        """Persist the override and replace the live registry entry immediately."""
        if self.item_id is None:
            return False
        try:
            data = self._data()
            base = self.world.registries.items.find(self.item_id)
            validate_item_data(data, self.item_id, None, base)
            complete = merged_item_data(data, base)
            pack = self.root / "items" / self.item_id
            pack.mkdir(parents=True, exist_ok=True)
            (pack / "data.json").write_text(
                json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
            )
            pygame.image.save(self.picture, str(pack / "icon.png"))
            self.world.registries.items.load_mapping(
                complete, str(pack / "data.json"), replace_existing=base is not None
            )
        except (OSError, ValueError, pygame.error) as error:
            self.notice = f"No se pudo guardar: {error}"
            return False
        self.icons.forget(self.item_id)
        self.notice = "Guardado: inventarios y mapa ya usan los cambios"
        return True

    def _art_point(self, position: tuple[int, int]) -> tuple[int, int]:
        return (
            min(ART_SIZE[0] - 1, max(0, (position[0] - ART_AREA.x) * ART_SIZE[0] // ART_AREA.width)),
            min(ART_SIZE[1] - 1, max(0, (position[1] - ART_AREA.y) * ART_SIZE[1] // ART_AREA.height)),
        )

    def _paint(self, start: tuple[int, int], end: tuple[int, int]) -> None:
        color = TRANSPARENT if self.tool == ERASER_TOOL else (*self.color, 255)
        radius = max(1, self.size // 2)
        pygame.draw.line(self.picture, color, start, end, max(1, self.size))
        pygame.draw.circle(self.picture, color, start, radius)
        pygame.draw.circle(self.picture, color, end, radius)

    def _fill(self, at: tuple[int, int]) -> None:
        alike = pygame.mask.from_threshold(self.picture, self.picture.get_at(at), (1, 1, 1, 1))
        alike.connected_component(at).to_surface(
            self.picture, setcolor=(*self.color, 255), unsetcolor=None
        )

    def press(self, position: tuple[int, int]) -> None:
        self.active_field = None
        if ART_AREA.collidepoint(position):
            at = self._art_point(position)
            self._remember()
            if self.tool == FILL_TOOL:
                self._fill(at)
            else:
                self._paint(at, at)
                self._stroke = at
            return
        for name, rect in self.field_rects.items():
            if rect.collidepoint(position):
                self.active_field = name
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

    def _apply(self, intent: tuple) -> None:
        if intent[0] == "tool":
            self.tool = intent[1]
        elif intent[0] == "undo":
            self.undo()
        elif intent[0] == "clear":
            self.clear()
        elif intent[0] == "save":
            self.save()
        elif intent[0] == "close":
            self.closed = True

    def drag(self, position: tuple[int, int]) -> None:
        if self._stroke is None:
            return
        at = self._art_point(position)
        self._paint(self._stroke, at)
        self._stroke = at

    def _type(self, event: pygame.event.Event) -> None:
        if self.active_field is None:
            return
        if event.key == pygame.K_BACKSPACE:
            self.values[self.active_field] = self.values[self.active_field][:-1]
        elif event.key in (pygame.K_RETURN, pygame.K_TAB):
            names = [name for name, _ in FIELDS]
            self.active_field = names[(names.index(self.active_field) + 1) % len(names)]
        elif event.key != pygame.K_ESCAPE:
            text = getattr(event, "unicode", "")
            if text and text.isprintable():
                self.values[self.active_field] += text

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            self.press(canvas_position(event.pos))
        elif event.type == pygame.MOUSEMOTION and self._stroke is not None:
            self.drag(canvas_position(event.pos))
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            self._stroke = None
        elif event.type == pygame.KEYDOWN and event.key == pygame.K_z and event.mod & pygame.KMOD_CTRL:
            self.undo()
        elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self.closed = True
        elif event.type == pygame.KEYDOWN:
            self._type(event)

    def update(self, dt: float) -> None:
        pass

    def render(self) -> None:
        self.layers.clear()
        self.canvas.fill(PALETTE["ink"])
        definition = self.world.registries.items.resolve(self.item_id or "")
        self.font.draw(self.canvas, f"Modificar {definition.name}", (TOOLS_LEFT, 4), PALETTE["glow"], scale=2)
        self.font.draw(
            self.canvas,
            self.font.truncate(self.notice or "El ID es estable; se cambia el aspecto y lo que hace", 590),
            (TOOLS_LEFT, 30),
            PALETTE["lamp" if self.notice else "stone"],
        )
        self.font.draw(self.canvas, f"ID: {self.item_id or '-'}", (TOOLS_LEFT, 46), PALETTE["dust"])
        for button in self.top_buttons:
            button.draw(self.canvas, self.font)

        self.font.draw(self.canvas, "Color", (TOOLS_LEFT, 58), PALETTE["dust"])
        for rect, color in self.swatches:
            pygame.draw.rect(self.canvas, color, rect.inflate(-2, -2))
            if color == self.color and self.tool != ERASER_TOOL:
                pygame.draw.rect(self.canvas, PALETTE["paper"], rect, 1)
        for rect, size in self.brush_buttons:
            draw_panel(self.canvas, rect, fill="shadow", border="lamp" if size == self.size else "iron")
            pygame.draw.circle(self.canvas, PALETTE["bone"], rect.center, max(1, size // 2))
        for button in self.tool_buttons:
            button.draw(self.canvas, self.font, active=button.intent == ("tool", self.tool))
        for button in self.edit_buttons:
            button.draw(self.canvas, self.font)

        pygame.draw.rect(self.canvas, PALETTE["bone"], ART_AREA)
        self.canvas.blit(pygame.transform.scale(self.picture, ART_AREA.size), ART_AREA)
        pygame.draw.rect(self.canvas, PALETTE["stone"], ART_AREA.inflate(2, 2), 1)
        self.font.draw(self.canvas, "Icono", (ART_AREA.x, ART_AREA.y - LINE_HEIGHT - 2), PALETTE["dust"])

        for name, label in FIELDS:
            rect = self.field_rects[name]
            self.font.draw(self.canvas, label, (rect.x, rect.y - LINE_HEIGHT - 1), PALETTE["dust"])
            draw_panel(
                self.canvas,
                rect,
                fill="shadow",
                border="lamp" if name == self.active_field else "iron",
            )
            text = self.values.get(name, "")
            shown = self.font.truncate(text, rect.width - 8)
            self.font.draw(self.canvas, shown, (rect.x + 4, rect.y + 2), PALETTE["paper"])
            if name == self.active_field and self.font.width(shown) < rect.width - 10:
                x = rect.x + 4 + self.font.width(shown) + 1
                pygame.draw.line(self.canvas, PALETTE["glow"], (x, rect.y + 2), (x, rect.bottom - 3))
