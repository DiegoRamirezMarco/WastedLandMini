"""Where the player makes the settlement's first resident: a name, an age, who they are, a way of being and a way of moving.

The scene only gathers what was chosen. Whether anyone comes of it is the simulation's to say.
"""

import pygame

from graphics.font import FONT_CHARS, LINE_HEIGHT, BitmapFont
from graphics.palette import PALETTE
from graphics.screen_layers import ScreenLayers
from scenes.manner_preview import MannerPreview
from scenes.scene import canvas_position
from simulation.commands import FoundResidentCommand
from simulation.family.kin import BOTH, DRAWN_TO, GENDERS, SEXES
from simulation.residents.founding import AGE_RANGE, MAX_TRAITS, NAME_LENGTH, tidy_name
from simulation.residents.personality import Personality
from simulation.world import SimulationWorld
from ui.button import Button
from ui.manner_picker import MannerPicker
from ui.panel import draw_panel
from ui.slider import Slider

LEFT = 24
NAME_FIELD = pygame.Rect(LEFT, 70, 200, 16)
AGE_Y = 104
# Under the age, who they are: a row to each of the three things said of it.
IDENTITY_Y = 122
IDENTITY_ROW = 16
SLIDERS_Y = 190
SLIDER_ROW = 20
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
    "libido": ("Deseo", "busca con más ganas a quien le atrae"),
}
# What is said of who somebody is, and the words for each thing it can be.
SEX, GENDER, DRAWN = "sex", "gender", "drawn_to"
IDENTITY_LABELS = {SEX: "Cuerpo", GENDER: "Se siente", DRAWN: "Le atraen"}
IDENTITY_WORDS = {
    SEX: {"m": "De hombre", "f": "De mujer"},
    GENDER: {"m": "Hombre", "f": "Mujer", "nb": "No binario", "bi": "Bigénero"},
    DRAWN: {"m": "Hombres", "f": "Mujeres", BOTH: "Ambos"},
}
IDENTITY_CHOICES = {SEX: SEXES, GENDER: GENDERS, DRAWN: DRAWN_TO}
DEFAULT_SEX = "f"
# The three faces of the screen: who they are, what they are capable of, and how they go about
# what everybody does.
PERSON_PAGE, ABLE_PAGE, MANNERS_PAGE = "person", "able", "manners"
PAGE_LABELS = {PERSON_PAGE: "Quién es", MANNERS_PAGE: "Cómo se mueve", ABLE_PAGE: "Qué puede"}
ABLE_AT = (LEFT + 8, 96)
ABLE_ROW = 30
ABLE_HEADING = "Lo que puede: reparte los puntos"
ABLE_LEFT = "Puntos por repartir: {points}"
ABLE_NOTES = (
    "Del 1 al 10. En el 5 está cualquiera.",
    "Cada trabajo va por una de ellas, y hacerlo la sube poco a poco.",
    "Los que lleguen después traerán las suyas, y los hijos saldrán a sus padres.",
)
PAGES_AT = (470, 16)
PICKER_AT = (LEFT + 8, 84)
PICKER_WIDTH = 400
PREVIEW = pygame.Rect(470, 58, 300, 300)
MANNERS_HEADING = "Maneras: una de cada fila"
MANNERS_NOTES = (
    "No cambian lo que hace ni lo bien que lo hace: solo cómo se le ve hacerlo.",
    "La figura es la de ejemplo: en cuanto lo dibujes, será él quien se mueva así.",
    "Se pueden cambiar más adelante: Maneras en su ficha del mapa, o F6.",
)
NOTES_TEXT = (
    "Nada de esto le obliga: decide por su cuenta, y tú le aconsejas.",
    "En Cómo se mueve eliges su manera de andar, de comer y de pelear.",
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
        preview: MannerPreview | None = None,
    ) -> None:
        self.canvas = canvas
        self.world = world
        self.font = font
        self.layers = layers
        # What shows a manner being tried out, if there is anything to show it with.
        self.preview = preview
        self.page = PERSON_PAGE
        # The manner chosen for each kind, and the kind on show beside them.
        self.manners: dict[str, str] = {}
        self.shown_kind: str | None = None
        self.closed = True
        # ID of whoever was made, once someone has been.
        self.created: str | None = None
        self.name = ""
        self.age = DEFAULT_AGE
        self.personality: dict[str, float] = {}
        # Their sex, what they take themselves to be, and who they are drawn to, as IDs.
        self.identity: dict[str, str] = {SEX: DEFAULT_SEX, GENDER: DEFAULT_SEX, DRAWN: BOTH}
        self.traits: list[str] = []
        # Their strength, constitution, dexterity, mind, senses and charisma, in whole points.
        self.attributes: dict[str, int] = {}
        self.notice = ""
        self._held: str | None = None
        self._blink = 0.0
        self.able_buttons: list[Button] = []
        for row, name in enumerate(world.registries.attributes.attributes):
            y = ABLE_AT[1] + row * ABLE_ROW
            self.able_buttons.append(Button.at(font, ABLE_AT[0] + 96, y, "-", ("attribute", name, -1)))
            self.able_buttons.append(Button.at(font, ABLE_AT[0] + 140, y, "+", ("attribute", name, 1)))

        self.sliders: dict[str, Slider] = {}
        y = SLIDERS_Y
        for trait in PERSONALITY_LABELS:
            if trait in vars(Personality()):
                self.sliders[trait] = Slider(pygame.Rect(SLIDER_LEFT, y + 2, *SLIDER_SIZE), 0.0, 100.0)
                y += SLIDER_ROW
        self.traits_y = y + 8
        self.identity_buttons: list[Button] = []
        for row, what in enumerate(IDENTITY_LABELS):
            x = LEFT + 78
            for choice in IDENTITY_CHOICES[what]:
                button = Button.at(font, x, IDENTITY_Y + row * IDENTITY_ROW, IDENTITY_WORDS[what][choice], ("identity", what, choice))
                self.identity_buttons.append(button)
                x = button.rect.right + 3
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
        self.page_buttons: list[Button] = []
        x = PAGES_AT[0]
        for page, label in PAGE_LABELS.items():
            button = Button.at(font, x, PAGES_AT[1], label, ("page", page))
            self.page_buttons.append(button)
            x = button.rect.right + 3
        self.picker = MannerPicker(font, world.registries.manners, *PICKER_AT, PICKER_WIDTH)

    @property
    def buttons(self) -> list[Button]:
        """The buttons of the face on show, and the ones that are on both."""
        shared = [*self.page_buttons, self.create_button, self.close_button]
        if self.page == MANNERS_PAGE:
            return [*shared, *self.picker.buttons]
        if self.page == ABLE_PAGE:
            return [*shared, *self.able_buttons]
        return [*self.age_buttons, *self.identity_buttons, *self.trait_buttons, *shared]

    def open(self) -> None:
        """Start from a blank: nobody in particular, of middling everything."""
        self.closed = False
        self.created = None
        self.name, self.age, self.traits = "", DEFAULT_AGE, []
        self.personality = {trait: 50.0 for trait in self.sliders}
        self.identity = {SEX: DEFAULT_SEX, GENDER: DEFAULT_SEX, DRAWN: BOTH}
        settings = self.world.registries.attributes
        self.attributes = {name: round(settings.middle) for name in settings.attributes}
        self.notice = ""
        self._held = None
        self.page = PERSON_PAGE
        # Until another is picked, the first way there is of each kind.
        self.manners = {kind.kind_id: buttons[0].intent[2] for kind, _, buttons in self.picker.rows}
        self.shown_kind = self.picker.rows[0][0].kind_id if self.picker.rows else None

    def set_name(self, name: str) -> None:
        self.name = "".join(char for char in name if char in FONT_CHARS)[:NAME_LENGTH]
        self.notice = ""

    def set_age(self, age: int) -> None:
        self.age = min(max(age, AGE_RANGE[0]), AGE_RANGE[1])

    def set_identity(self, what: str, choice: str) -> None:
        """Say one thing of who they are. Until it is said otherwise, they take themselves to be what their body is."""
        if what not in IDENTITY_CHOICES or choice not in IDENTITY_CHOICES[what]:
            return
        follows = self.identity[GENDER] == self.identity[SEX]
        self.identity[what] = choice
        if what == SEX and follows:
            self.identity[GENDER] = choice

    def points_left(self) -> int:
        """How many points there still are to share out among what they are capable of."""
        return round(self.world.registries.attributes.founder_points) - sum(self.attributes.values())

    def set_attribute(self, name: str, value: int) -> None:
        """Have them be so much of one thing, as far as the scale and the points there are allow."""
        settings = self.world.registries.attributes
        if name not in self.attributes:
            return
        value = int(min(max(value, settings.lowest), settings.highest))
        self.attributes[name] = min(value, self.attributes[name] + max(0, self.points_left()))

    def toggle_trait(self, trait_id: str) -> None:
        if trait_id in self.traits:
            self.traits.remove(trait_id)
        elif len(self.traits) < MAX_TRAITS:
            self.traits.append(trait_id)

    def set_manner(self, kind_id: str, manner_id: str) -> None:
        """Choose a way of doing one kind of thing, and have it shown."""
        manner = self.world.registries.manners.manners.get(manner_id)
        if manner is not None and manner.kind == kind_id:
            self.manners[kind_id] = manner_id
            self.shown_kind = kind_id

    def create(self) -> str | None:
        """Ask the settlement to take in whoever has been described. Returns their ID if it did."""
        if not tidy_name(self.name):
            self.notice = NAMELESS
            return None
        created = self.world.apply_command(
            FoundResidentCommand(
                self.name, self.age, dict(self.personality), tuple(self.traits), dict(self.manners), dict(self.identity),
                {name: float(value) for name, value in self.attributes.items()} or None,
            )
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
        elif intent[0] == "identity":
            self.set_identity(intent[1], intent[2])
        elif intent[0] == "attribute":
            self.set_attribute(intent[1], self.attributes.get(intent[1], 0) + intent[2])
        elif intent[0] == "page":
            self.page, self._held = intent[1], None
        elif intent[0] == "manner":
            self.set_manner(intent[1], intent[2])
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
            elif self.page != PERSON_PAGE:
                # The name is written where it is seen.
                return
            elif event.key == pygame.K_BACKSPACE:
                self.set_name(self.name[:-1])
            else:
                self.set_name(self.name + getattr(event, "unicode", ""))
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            position = canvas_position(event.pos)
            for trait, slider in self.sliders.items() if self.page == PERSON_PAGE else ():
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
        if self.preview is not None:
            self.preview.update(dt)

    def render(self) -> None:
        if self.layers is not None:
            self.layers.clear()
        self.canvas.fill(PALETTE["ink"])
        font, canvas = self.font, self.canvas
        font.draw(canvas, TITLE, (LEFT, 14), PALETTE["lamp"], scale=2)
        font.draw(canvas, SUBTITLE, (LEFT, 14 + LINE_HEIGHT * 2 + 2), PALETTE["bone"])
        for button in self.page_buttons:
            button.draw(canvas, font, active=button.intent[1] == self.page)
        if self.page == MANNERS_PAGE:
            self._render_manners()
        elif self.page == ABLE_PAGE:
            self._render_able()
        else:
            self._render_person()
        self.create_button.draw(canvas, font, active=bool(tidy_name(self.name)))
        self.close_button.draw(canvas, font)
        if self.notice:
            font.draw(canvas, self.notice, (self.close_button.rect.right + 12, self.close_button.rect.y + 2), PALETTE["glow"])

    def _render_manners(self) -> None:
        """How they go about what everybody does: a row to each kind, and the one last picked seen moving."""
        font, canvas = self.font, self.canvas
        name = tidy_name(self.name) or NO_NAME_YET
        font.draw(canvas, f"{MANNERS_HEADING} ({name})", (LEFT, PICKER_AT[1] - LINE_HEIGHT - 6), PALETTE["sand"])
        self.picker.draw(canvas, self.manners, self.shown_kind)
        shown = self.manners.get(self.shown_kind or "")
        self.picker.describe(canvas, shown)
        y = self.picker.bottom + LINE_HEIGHT * 3 + 6
        for text in MANNERS_NOTES:
            for line in font.wrap(text, PICKER_WIDTH):
                font.draw(canvas, line, (LEFT, y), PALETTE["dust"])
                y += LINE_HEIGHT
            y += 3
        if self.preview is not None:
            self.preview.draw(PREVIEW, None, self.world.registries.manners.manners.get(shown or ""))

    def _render_able(self) -> None:
        """What they are capable of: a row to each of the six, and the points still to share out."""
        font, canvas = self.font, self.canvas
        settings = self.world.registries.attributes
        name = tidy_name(self.name) or NO_NAME_YET
        font.draw(canvas, f"{ABLE_HEADING} ({name})", (LEFT, ABLE_AT[1] - LINE_HEIGHT * 2 - 8), PALETTE["sand"])
        left = self.points_left()
        font.draw(
            canvas, ABLE_LEFT.format(points=left), (LEFT, ABLE_AT[1] - LINE_HEIGHT - 5), PALETTE["glow" if left else "dust"]
        )
        for row, (attribute_id, definition) in enumerate(settings.attributes.items()):
            y = ABLE_AT[1] + row * ABLE_ROW
            value = self.attributes.get(attribute_id, round(settings.middle))
            font.draw(canvas, definition.name, (ABLE_AT[0], y + 2), PALETTE["bone"])
            figure = str(value)
            colour = "lichen" if value > settings.middle else ("ember" if value < settings.middle else "paper")
            font.draw(canvas, figure, (ABLE_AT[0] + 124 - font.width(figure) // 2, y + 2), PALETTE[colour])
            font.draw(canvas, definition.text, (ABLE_AT[0] + 164, y + 2), PALETTE["dust"])
            track = pygame.Rect(ABLE_AT[0], y + LINE_HEIGHT + 5, 150, 4)
            pygame.draw.rect(canvas, PALETTE["shadow"], track)
            span = max(1.0, settings.highest - settings.lowest)
            filled = round(track.width * (value - settings.lowest) / span)
            pygame.draw.rect(canvas, PALETTE[colour if colour != "paper" else "lamp"], (track.x, track.y, filled, track.height))
        for button in self.able_buttons:
            button.draw(canvas, font)
        y = ABLE_AT[1] + len(settings.attributes) * ABLE_ROW + 8
        for text in ABLE_NOTES:
            for line in font.wrap(text, 560):
                font.draw(canvas, line, (LEFT, y), PALETTE["dust"])
                y += LINE_HEIGHT
            y += 2

    def _render_person(self) -> None:
        font, canvas = self.font, self.canvas
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

        for row, (what, label) in enumerate(IDENTITY_LABELS.items()):
            font.draw(canvas, label, (LEFT, IDENTITY_Y + row * IDENTITY_ROW + 2), PALETTE["sand"])
        for button in self.identity_buttons:
            button.draw(canvas, font, active=self.identity.get(button.intent[1]) == button.intent[2])

        font.draw(canvas, "Forma de ser", (LEFT, SLIDERS_Y - LINE_HEIGHT - 4), PALETTE["sand"])
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

    def _render_who(self) -> None:
        """Who they are so far, and what each side of their way of being means. Their looks come after."""
        font, canvas = self.font, self.canvas
        name = tidy_name(self.name)
        font.draw(canvas, name or NO_NAME_YET, (WHO_AT[0], WHO_AT[1]), PALETTE["paper" if name else "stone"], scale=2)
        who = f"{self.age} años · {IDENTITY_WORDS[GENDER][self.identity[GENDER]].lower()}"
        font.draw(canvas, who, (WHO_AT[0], WHO_AT[1] + LINE_HEIGHT * 2 + 4), PALETTE["bone"])
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
