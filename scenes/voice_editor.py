"""Where a resident is given a voice: who speaks, a ready-made kind of voice, and a slider for each thing about it."""

import pygame

from audio.voice_player import VoicePlayer
from audio.voice_system import VoiceProfile
from graphics.face_renderer import FaceRenderer
from graphics.font import LINE_HEIGHT, BitmapFont
from graphics.palette import PALETTE
from graphics.screen_layers import ScreenLayers
from scenes.scene import canvas_position
from simulation.world import SimulationWorld
from ui.button import Button
from ui.slider import Slider

LEFT = 8
WIDTH = 330
MODELS_Y = 62
PRESETS_Y = 96
SLIDERS_Y = 128
SLIDER_ROW = 30
SLIDER_HEIGHT = 8
FACE_AT = (430, 58)
FACE_SCALE = 2
NOTES = pygame.Rect(430, 204, 330, 200)
SAVED_TEXT = "Guardado: ya habla así"
NOT_SAVED_TEXT = "No se pudo guardar"
IDLE_TEXT = "El tiempo está detenido"
NO_VOICES_TEXT = "No hay voces que elegir"
NOTES_TEXT = (
    "Elige quién habla y un tipo de voz, y afínala con los controles. Al soltar un control se oye cómo queda.",
    "Tono la hace más aguda o más grave. Temblor es la voz de un viejo, aspereza la de un monstruo, metal la de una máquina, y enredo hace que no se entienda nada.",
    "La primera vez que una voz dice una frase tarda un momento. Espacio la repite, Esc vuelve sin guardar.",
)


class VoiceEditor:
    """Give a resident a voice. Time stands still while it is open."""

    def __init__(
        self,
        canvas: pygame.Surface,
        world: SimulationWorld,
        font: BitmapFont,
        faces: FaceRenderer,
        voices: VoicePlayer,
        layers: ScreenLayers | None = None,
    ) -> None:
        self.canvas = canvas
        self.world = world
        self.font = font
        self.faces = faces
        self.voices = voices
        self.layers = layers
        self.catalog = voices.catalog
        self.closed = False
        self.resident_id: str | None = None
        self.profile: VoiceProfile | None = None
        self.notice = ""
        # Which of the sample lines is said to try the voice.
        self.sample = 0
        # The control whose knob is held, if any.
        self._held: str | None = None

        self.model_buttons = self._rows(MODELS_Y, [(model.label, ("model", model_id)) for model_id, model in self.catalog.models.items()])
        self.preset_buttons = self._rows(PRESETS_Y, [(label, ("preset", name)) for name, (label, _) in self.catalog.presets.items()])
        self.sliders: dict[str, Slider] = {}
        y = max(SLIDERS_Y, (self.preset_buttons[-1].rect.bottom if self.preset_buttons else PRESETS_Y) + 14)
        for control_id, control in self.catalog.controls.items():
            self.sliders[control_id] = Slider(pygame.Rect(LEFT + 3, y + LINE_HEIGHT + 4, WIDTH - 6, SLIDER_HEIGHT), control.low, control.high)
            y += SLIDER_ROW
        self.sample_y = y + 6
        self.try_buttons = self._rows(self.sample_y, [("Probar", ("try",)), ("Otra frase", ("sample",))])
        self.top_buttons = self._rows(6, [("<", ("step", -1)), (">", ("step", 1)), ("Guardar", ("save",)), ("Volver", ("close",))], left=530)

    def _rows(self, y: int, entries: list[tuple[str, tuple]], left: int = LEFT) -> list[Button]:
        """Buttons one after another, going on to a new row where they would pass the edge of the column."""
        buttons, x = [], left
        for label, intent in entries:
            button = Button.at(self.font, x, y, label, intent)
            if left == LEFT and button.rect.right > LEFT + WIDTH:
                x, y = left, y + button.rect.height + 3
                button = Button.at(self.font, x, y, label, intent)
            buttons.append(button)
            x = button.rect.right + 3
        return buttons

    @property
    def buttons(self) -> list[Button]:
        return [*self.top_buttons, *self.model_buttons, *self.preset_buttons, *self.try_buttons]

    @property
    def line(self) -> str:
        """The line the voice is tried with."""
        samples = self.catalog.samples
        return samples[self.sample % len(samples)] if samples else ""

    def open(self, resident_id: str | None) -> None:
        """Start on a resident, from the voice they have."""
        residents = list(self.world.residents)
        self.resident_id = resident_id if resident_id in self.world.residents else (residents[0] if residents else None)
        self.profile = self.voices.store.get(self.resident_id) if self.resident_id is not None else None
        self.closed = self.resident_id is None or self.profile is None
        self.notice = ""
        self._held = None

    def set_value(self, control_id: str, value: float) -> None:
        """Set one control of the voice, to the nearest figure it can take."""
        control = self.catalog.controls.get(control_id)
        if control is not None and self.profile is not None:
            self.profile = self.profile.with_value(control_id, control.clamp(value))
            self.notice = ""

    def try_out(self) -> bool:
        """Say the sample line in the voice as it stands. Returns whether it is being said."""
        return self.profile is not None and self.voices.speak(self.profile, self.line, interrupt=True)

    def save(self) -> bool:
        if self.resident_id is None or self.profile is None:
            return False
        saved = self.voices.store.save(self.resident_id, self.profile)
        self.notice = SAVED_TEXT if saved else NOT_SAVED_TEXT
        return saved

    def step(self, by: int) -> None:
        """Go on to the next resident, or back to the one before."""
        residents = list(self.world.residents)
        if self.resident_id in residents:
            self.voices.stop()
            self.open(residents[(residents.index(self.resident_id) + by) % len(residents)])

    def _apply(self, intent: tuple) -> None:
        if intent[0] == "model" and self.profile is not None:
            self.profile = self.profile.with_model(intent[1])
            self.notice = ""
            self.try_out()
        elif intent[0] == "preset":
            self.profile = self.catalog.presets[intent[1]][1]
            self.notice = ""
            self.try_out()
        elif intent[0] == "try":
            self.try_out()
        elif intent[0] == "sample":
            self.sample += 1
            self.try_out()
        elif intent[0] == "step":
            self.step(intent[1])
        elif intent[0] == "save":
            self.save()
        elif intent[0] == "close":
            self.close()

    def close(self) -> None:
        self.voices.stop()
        self.closed = True

    def press(self, position: tuple[int, int]) -> None:
        """Handle the left button going down at a position on the game's canvas."""
        for control_id, slider in self.sliders.items():
            if slider.contains(position):
                self._held = control_id
                self.set_value(control_id, slider.value_at(position[0]))
                return
        for button in self.buttons:
            if button.contains(position):
                self._apply(button.intent)
                return

    def drag(self, position: tuple[int, int]) -> None:
        if self._held is not None:
            self.set_value(self._held, self.sliders[self._held].value_at(position[0]))

    def release(self) -> None:
        """Let go of a knob: the voice is heard as it has been left."""
        if self._held is not None:
            self._held = None
            self.try_out()

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            self.press(canvas_position(event.pos))
        elif event.type == pygame.MOUSEMOTION:
            self.drag(canvas_position(event.pos))
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            self.release()
        elif event.type == pygame.KEYDOWN and event.key == pygame.K_SPACE:
            self.try_out()
        elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self.close()

    def update(self, dt: float) -> None:
        self.voices.update()

    def render(self) -> None:
        if self.layers is not None:
            self.layers.clear()
        canvas, font = self.canvas, self.font
        canvas.fill(PALETTE["ink"])
        resident = self.world.residents.get(self.resident_id or "")
        font.draw(canvas, f"Voz de {resident.name}" if resident is not None else "Voz", (LEFT, 4), PALETTE["glow"], scale=2)
        profile = self.profile
        if profile is None:
            font.draw(canvas, NO_VOICES_TEXT, (LEFT, 30), PALETTE["stone"])
            return
        # What is in the way of hearing it comes first; then what was just done; then that time has stopped.
        waiting = self.voices.notice(profile, self.line)
        font.draw(canvas, waiting or self.notice or IDLE_TEXT, (LEFT, 30), PALETTE["lamp" if waiting or self.notice else "stone"])
        for button in self.top_buttons:
            button.draw(canvas, font)

        font.draw(canvas, "Quién habla", (LEFT, MODELS_Y - LINE_HEIGHT - 1), PALETTE["dust"])
        for button in self.model_buttons:
            button.draw(canvas, font, active=button.intent == ("model", profile.model))
        font.draw(canvas, "Tipo de voz", (LEFT, PRESETS_Y - LINE_HEIGHT - 1), PALETTE["dust"])
        like = self.catalog.preset_like(profile)
        for button in self.preset_buttons:
            button.draw(canvas, font, active=button.intent == ("preset", like))

        for control_id, slider in self.sliders.items():
            control = self.catalog.controls[control_id]
            value = profile.value(control_id, control.default)
            top = slider.rect.y - LINE_HEIGHT - 4
            font.draw(canvas, control.label, (LEFT, top), PALETTE["bone"])
            figure = control.describe(value)
            font.draw(canvas, figure, (LEFT + WIDTH - font.width(figure), top), PALETTE["lamp" if value != control.default else "stone"])
            slider.draw(canvas, value, resting=control.default, active=self._held == control_id)

        for button in self.try_buttons:
            button.draw(canvas, font)
        font.draw(canvas, font.truncate(f'"{self.line}"', WIDTH), (LEFT, self.try_buttons[0].rect.bottom + 5), PALETTE["paper"])

        if resident is not None:
            face = self.faces.face(resident.resident_id)
            size = (face.get_width() * FACE_SCALE, face.get_height() * FACE_SCALE)
            canvas.blit(pygame.transform.scale(face, size), FACE_AT)
            pygame.draw.rect(canvas, PALETTE["stone"], pygame.Rect(FACE_AT, size).inflate(2, 2), 1)
        y = NOTES.y
        for note in NOTES_TEXT:
            for line in font.wrap(note, NOTES.width):
                font.draw(canvas, line, (NOTES.x, y), PALETTE["bone"])
                y += LINE_HEIGHT
            y += 4
