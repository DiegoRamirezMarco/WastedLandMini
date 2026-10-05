"""Where the player makes the settlement's first resident: a name, an age and a way of being.

The scene only gathers what was chosen. Whether anyone comes of it is the simulation's to say.
"""

import pygame

from graphics.font import FONT_CHARS, LINE_HEIGHT, BitmapFont
from graphics.palette import PALETTE
from graphics.screen_layers import ScreenLayers
from scenes.scene import canvas_position
from simulation.commands import FoundResidentCommand
from simulation.residents.founding import AGE_RANGE, MAX_TRAITS, NAME_LENGTH, tidy_name
from simulation.residents.personality import Personality
from simulation.world import SimulationWorld
from ui.button import Button
from ui.panel import draw_panel
from ui.slider import Slider

LEFT = 24
NAME_FIELD = pygame.Rect(LEFT, 70, 200, 16)
AGE_Y = 104
SLIDERS_Y = 150
SLIDER_ROW = 24
SLIDER_LEFT = LEFT + 78
SLIDER_SIZE = (200, 8)
WHO_AT = (470, 48)
NOTES = pygame.Rect(470, 150, 300, 250)
DEFAULT_AGE = 30
TITLE = "TU PRIMER HABITANTE"
SUBTITLE = "Quien levanta el asentamiento. Los demás llegarán por la puerta."
NAMELESS = "Hace falta un nombre"
REFUSED = "Aquí ya vive alguien: los demás llegan por la puerta"
NO_NAME_YET = "Sin nombre"
DRAWN_NEXT = "Aquí no se elige una cara ya hecha: en cuanto lo crees, lo dibujas tú, cuerpo y cabeza."
# What each side of a personality is called, and what it does to how they act.
PERSONALITY_LABELS = {
    "empathy": ("Empatía", "se pone en el lugar de los demás, y abre la puerta a quien llama"),
    "sociability": ("Sociable", "busca compañía y conversación"),
    "courage": ("Valor", "planta cara y se arriesga"),
    "aggression": ("Mal genio", "discute y pelea con más facilidad"),
    "impulsiveness": ("Impulso", "actúa antes de pensarlo"),
    "greed": ("Codicia", "mira por lo suyo antes que por lo de todos"),
}
NOTES_TEXT = (
    "Nada de esto le obliga: decide por su cuenta, y tú le aconsejas.",
    "Más adelante puedes volver a dibujarlo desde el mapa (Dibujar) y darle voz (Voz).",
    "Enter lo crea. Esc vuelve sin crear a nadie.",
)


class ResidentCreator:
    """Make the first resident. Time stands still while it is open."""

    def __init__(
        self,
        canvas: pygame.Surface,
        world: SimulationWorld,
        font: BitmapFont,
        layers: ScreenLayers | None = None,
    ) -> None:
        self.canvas = canvas
        self.world = world
        self.font = font
        self.layers = layers
        self.closed = True
        # ID of whoever was made, once someone has been.
        self.created: str | None = None
        self.name = ""
        self.age = DEFAULT_AGE
        self.personality: dict[str, float] = {}
        self.traits: list[str] = []
        self.notice = ""
        self._held: str | None = None
        self._blink = 0.0

        self.sliders: dict[str, Slider] = {}
        y = SLIDERS_Y
        for trait in PERSONALITY_LABELS:
            if trait in vars(Personality()):
                self.sliders[trait] = Slider(pygame.Rect(SLIDER_LEFT, y + 2, *SLIDER_SIZE), 0.0, 100.0)
                y += SLIDER_ROW
        self.traits_y = y + 12
        self.age_buttons = [
            Button.at(font, LEFT + 78, AGE_Y, "-", ("age", -1)),
            Button.at(font, LEFT + 122, AGE_Y, "+", ("age", 1)),
        ]
        self.trait_buttons: list[Button] = []
        x, row = LEFT, self.traits_y + LINE_HEIGHT + 3
        for trait_id in world.registries.traits.ids():
            label = str(world.registries.traits.get(trait_id).get("name", trait_id))
            button = Button.at(font, x, row, label, ("trait", trait_id))
            if button.rect.right > LEFT + 400:
                x, row = LEFT, row + button.rect.height + 3
                button = Button.at(font, x, row, label, ("trait", trait_id))
            self.trait_buttons.append(button)
            x = button.rect.right + 4
        bottom = canvas.get_height() - 30
        self.create_button = Button.at(font, LEFT, bottom, "Crear habitante", ("create",))
        self.close_button = Button.at(font, self.create_button.rect.right + 6, bottom, "Volver", ("close",))

    @property
    def buttons(self) -> list[Button]:
        return [*self.age_buttons, *self.trait_buttons, self.create_button, self.close_button]

    def open(self) -> None:
        """Start from a blank: nobody in particular, of middling everything."""
        self.closed = False
        self.created = None
        self.name, self.age, self.traits = "", DEFAULT_AGE, []
        self.personality = {trait: 50.0 for trait in self.sliders}
        self.notice = ""
        self._held = None

    def set_name(self, name: str) -> None:
        self.name = "".join(char for char in name if char in FONT_CHARS)[:NAME_LENGTH]
        self.notice = ""

    def set_age(self, age: int) -> None:
        self.age = min(max(age, AGE_RANGE[0]), AGE_RANGE[1])

    def toggle_trait(self, trait_id: str) -> None:
        if trait_id in self.traits:
            self.traits.remove(trait_id)
        elif len(self.traits) < MAX_TRAITS:
            self.traits.append(trait_id)

    def create(self) -> str | None:
        """Ask the settlement to take in whoever has been described. Returns their ID if it did."""
        if not tidy_name(self.name):
            self.notice = NAMELESS
            return None
        created = self.world.apply_command(
            FoundResidentCommand(self.name, self.age, dict(self.personality), tuple(self.traits))
        )
        if not isinstance(created, str):
            self.notice = REFUSED
            return None
        self.created, self.closed = created, True
        return created

    def _apply(self, intent: tuple) -> None:
        if intent[0] == "age":
            self.set_age(self.age + intent[1])
        elif intent[0] == "trait":
            self.toggle_trait(intent[1])
        elif intent[0] == "create":
            self.create()
        elif intent[0] == "close":
            self.closed = True

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                self.closed = True
            elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                self.create()
            elif event.key == pygame.K_BACKSPACE:
                self.set_name(self.name[:-1])
            else:
                self.set_name(self.name + getattr(event, "unicode", ""))
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            position = canvas_position(event.pos)
            for trait, slider in self.sliders.items():
                if slider.contains(position):
                    self._held = trait
                    self.personality[trait] = round(slider.value_at(position[0]))
                    return
            intent = next((button.intent for button in self.buttons if button.contains(position)), None)
            if isinstance(intent, tuple):
                self._apply(intent)
        elif event.type == pygame.MOUSEMOTION and self._held is not None:
            x = canvas_position(event.pos)[0]
            self.personality[self._held] = round(self.sliders[self._held].value_at(x))
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            self._held = None

    def update(self, dt: float) -> None:
        self._blink = (self._blink + dt) % 1.0

    def render(self) -> None:
        if self.layers is not None:
            self.layers.clear()
        self.canvas.fill(PALETTE["ink"])
        font, canvas = self.font, self.canvas
        font.draw(canvas, TITLE, (LEFT, 14), PALETTE["lamp"], scale=2)
        font.draw(canvas, SUBTITLE, (LEFT, 14 + LINE_HEIGHT * 2 + 2), PALETTE["bone"])

        font.draw(canvas, "Nombre", (LEFT, NAME_FIELD.y - LINE_HEIGHT - 1), PALETTE["sand"])
        draw_panel(canvas, NAME_FIELD, fill="shadow", border="lamp")
        caret = "_" if self._blink < 0.5 and len(self.name) < NAME_LENGTH else ""
        font.draw(canvas, self.name + caret, (NAME_FIELD.x + 4, NAME_FIELD.y + 3), PALETTE["paper"])

        font.draw(canvas, "Edad", (LEFT, AGE_Y + 2), PALETTE["sand"])
        for button in self.age_buttons:
            button.draw(canvas, font)
        years = f"{self.age}"
        middle = (self.age_buttons[0].rect.right + self.age_buttons[1].rect.left) // 2
        font.draw(canvas, years, (middle - font.width(years) // 2, AGE_Y + 2), PALETTE["paper"])

        font.draw(canvas, "Forma de ser", (LEFT, SLIDERS_Y - LINE_HEIGHT - 6), PALETTE["sand"])
        for trait, slider in self.sliders.items():
            value = self.personality.get(trait, 50.0)
            font.draw(canvas, PERSONALITY_LABELS[trait][0], (LEFT, slider.rect.y - 2), PALETTE["bone"])
            slider.draw(canvas, value, resting=50.0, active=self._held == trait)
            font.draw(canvas, f"{round(value)}", (slider.rect.right + 10, slider.rect.y - 2), PALETTE["paper"])

        if self.trait_buttons:
            font.draw(canvas, f"Rasgos (hasta {MAX_TRAITS})", (LEFT, self.traits_y), PALETTE["sand"])
            for button in self.trait_buttons:
                button.draw(canvas, font, active=button.intent[1] in self.traits)

        self._render_who()
        self.create_button.draw(canvas, font, active=bool(tidy_name(self.name)))
        self.close_button.draw(canvas, font)
        if self.notice:
            font.draw(canvas, self.notice, (self.close_button.rect.right + 12, self.close_button.rect.y + 2), PALETTE["glow"])

    def _render_who(self) -> None:
        """Who they are so far, and what each side of their way of being means. Their looks come after."""
        font, canvas = self.font, self.canvas
        name = tidy_name(self.name)
        font.draw(canvas, name or NO_NAME_YET, (WHO_AT[0], WHO_AT[1]), PALETTE["paper" if name else "stone"], scale=2)
        font.draw(canvas, f"{self.age} años", (WHO_AT[0], WHO_AT[1] + LINE_HEIGHT * 2 + 4), PALETTE["bone"])
        blank = pygame.Rect(WHO_AT[0], WHO_AT[1] + LINE_HEIGHT * 4, NOTES.width, LINE_HEIGHT * 3 + 8)
        draw_panel(canvas, blank, fill="shadow", border="lamp")
        for index, line in enumerate(font.wrap(DRAWN_NEXT, blank.width - 10)):
            font.draw(canvas, line, (blank.x + 5, blank.y + 5 + index * LINE_HEIGHT), PALETTE["lamp"])

        y = NOTES.y
        for trait in self.sliders:
            label, meaning = PERSONALITY_LABELS[trait]
            for index, line in enumerate(font.wrap(f"{label}: {meaning}.", NOTES.width)):
                font.draw(canvas, line, (NOTES.x, y), PALETTE["bone" if index == 0 else "dust"])
                y += LINE_HEIGHT
        y += 6
        for text in NOTES_TEXT:
            for line in font.wrap(text, NOTES.width):
                font.draw(canvas, line, (NOTES.x, y), PALETTE["dust"])
                y += LINE_HEIGHT
            y += 3
