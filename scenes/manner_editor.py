"""Where a resident is given their manners: how they walk, eat and fight, with each one seen as it is picked."""

import pygame

from graphics.font import LINE_HEIGHT, BitmapFont
from graphics.palette import PALETTE
from graphics.screen_layers import ScreenLayers
from scenes.manner_preview import MannerPreview
from scenes.scene import canvas_position
from simulation.commands import SetMannerCommand
from simulation.world import SimulationWorld
from ui.button import Button
from ui.manner_picker import MannerPicker

LEFT = 16
PICKER_TOP = 64
PICKER_WIDTH = 400
PREVIEW = pygame.Rect(470, 58, 300, 300)
NOTES_Y = 250
IDLE_TEXT = "El tiempo está detenido"
NOBODY_TEXT = "No hay nadie a quien dar maneras"
PREVIEW_CAPTION = "Así lo hace"
NOTES_TEXT = (
    "Elige una manera de cada fila: se ve a la derecha, y queda puesta en cuanto la eliges.",
    "No cambia lo que hace ni lo bien que lo hace: solo cómo se le ve hacerlo.",
    "Disparar y Cuchillo se ven cuando pelea llevando un arma de esa clase.",
    "Las flechas pasan al siguiente habitante. Esc vuelve al mapa.",
)


class MannerEditor:
    """Choose how a resident does what everybody does. Time stands still while it is open."""

    def __init__(
        self,
        canvas: pygame.Surface,
        world: SimulationWorld,
        font: BitmapFont,
        preview: MannerPreview,
        layers: ScreenLayers | None = None,
    ) -> None:
        self.canvas = canvas
        self.world = world
        self.font = font
        self.preview = preview
        self.layers = layers
        self.closed = False
        self.resident_id: str | None = None
        # The kind of manner on show beside the rows: the one last picked.
        self.shown: str | None = None
        self.picker = MannerPicker(font, world.registries.manners, LEFT, PICKER_TOP, PICKER_WIDTH)
        self.top_buttons: list[Button] = []
        x = PREVIEW.x
        for label, intent in (("<", ("step", -1)), (">", ("step", 1)), ("Volver", ("close",))):
            button = Button.at(font, x, 6, label, intent)
            self.top_buttons.append(button)
            x = button.rect.right + 3

    @property
    def buttons(self) -> list[Button]:
        return [*self.top_buttons, *self.picker.buttons]

    def open(self, resident_id: str | None) -> None:
        """Start on a resident, with the first kind of manner on show."""
        residents = list(self.world.residents)
        self.resident_id = resident_id if resident_id in self.world.residents else (residents[0] if residents else None)
        self.closed = self.resident_id is None
        if self.shown is None and self.picker.rows:
            self.shown = self.picker.rows[0][0].kind_id

    def chosen(self) -> dict[str, str]:
        """The manner the resident has for each kind, their own by default included."""
        resident = self.world.residents.get(self.resident_id or "")
        if resident is None:
            return {}
        found = {kind.kind_id: self.world.manner_of(resident, kind.kind_id) for kind, _, _ in self.picker.rows}
        return {kind_id: manner.manner_id for kind_id, manner in found.items() if manner is not None}

    def pick(self, kind_id: str, manner_id: str) -> bool:
        """Give the resident a manner, and show it. Returns whether they took it."""
        if self.resident_id is None:
            return False
        self.shown = kind_id
        return bool(self.world.apply_command(SetMannerCommand(self.resident_id, kind_id, manner_id)))

    def step(self, by: int) -> None:
        """Go on to the next resident, or back to the one before."""
        residents = list(self.world.residents)
        if self.resident_id in residents:
            self.open(residents[(residents.index(self.resident_id) + by) % len(residents)])

    def press(self, position: tuple[int, int]) -> None:
        """Handle the left button going down at a position on the game's canvas."""
        picked = self.picker.picked(position)
        if picked is not None:
            self.pick(*picked)
            return
        intent = next((button.intent for button in self.top_buttons if button.contains(position)), None)
        if intent is None:
            return
        if intent[0] == "step":
            self.step(intent[1])
        elif intent[0] == "close":
            self.closed = True

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            self.press(canvas_position(event.pos))
        elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self.closed = True
        elif event.type == pygame.KEYDOWN and event.key in (pygame.K_LEFT, pygame.K_RIGHT):
            self.step(-1 if event.key == pygame.K_LEFT else 1)

    def update(self, dt: float) -> None:
        self.preview.update(dt)

    def render(self) -> None:
        if self.layers is not None:
            self.layers.clear()
        canvas, font = self.canvas, self.font
        canvas.fill(PALETTE["ink"])
        resident = self.world.residents.get(self.resident_id or "")
        font.draw(canvas, f"Maneras de {resident.name}" if resident is not None else "Maneras", (LEFT, 4), PALETTE["glow"], scale=2)
        font.draw(canvas, IDLE_TEXT if resident is not None else NOBODY_TEXT, (LEFT, 30), PALETTE["stone"])
        for button in self.top_buttons:
            button.draw(canvas, font)
        if resident is None:
            return
        chosen = self.chosen()
        self.picker.draw(canvas, chosen, self.shown)
        self.picker.describe(canvas, chosen.get(self.shown or ""))
        y = max(NOTES_Y, self.picker.bottom + LINE_HEIGHT * 3)
        for note in NOTES_TEXT:
            for line in font.wrap(note, PICKER_WIDTH):
                font.draw(canvas, line, (LEFT, y), PALETTE["dust"])
                y += LINE_HEIGHT
            y += 4
        font.draw(canvas, PREVIEW_CAPTION, (PREVIEW.x, PREVIEW.y - LINE_HEIGHT - 1), PALETTE["dust"])
        manner = self.world.registries.manners.manners.get(chosen.get(self.shown or "", ""))
        self.preview.draw(PREVIEW, resident.resident_id, manner)
