from collections.abc import Callable

import pygame

from audio.voice_player import VoicePlayer

from graphics.face_renderer import FaceRenderer
from graphics.font import LINE_HEIGHT, BitmapFont
from graphics.palette import PALETTE
from graphics.screen_layers import ScreenLayers
from scenes.scene import canvas_position
from simulation.commands import ChooseOptionCommand
from simulation.events.decision import Decision
from simulation.world import SimulationWorld
from ui.button import Button
from ui.dock import dock_areas, draw_scene
from ui.labels import FEELING_LABELS
from ui.panel import draw_panel

OPTION_HEIGHT = 18
OPTION_GAP = 3
OPTION_KEYS = (pygame.K_1, pygame.K_2, pygame.K_3, pygame.K_4, pygame.K_5, pygame.K_6)
CONTINUE_KEYS = (pygame.K_SPACE, pygame.K_RETURN)
NOBODY_TITLE = "Nadie necesita consejo"
NOBODY_TEXT = "Cuando alguien esté al límite verás un ! sobre su cabeza. ESPACIO o TAB para volver."
CONTINUE_TEXT = "ESPACIO para continuar"
# Face each resident shows once they have made up their mind, by outcome ID.
OUTCOME_EXPRESSIONS = {
    "confront": "angry", "talk_it_out": "neutral", "cool_off": "sad", "fight": "angry", "walk_away": "sad",
    "take": "happy", "stay": "neutral", "confess": "happy", "keep_quiet": "sad", "break_up": "sad",
    "push_on": "happy", "turn_back": "sad", "let_in": "happy", "turn_away": "angry",
    "stand_ground": "angry", "give_way": "sad",
}
# Face a resident wears while they make up their mind, by kind of decision. Anger for any other.
DECISION_EXPRESSIONS = {"job_offer": "neutral", "confession": "neutral", "breakup": "sad", "risky_find": "neutral",
                        "stranger": "neutral"}


class InteractionView:
    """A resident asking for advice, in the dock under the map. Time stands still while it is open.

    The rest of the screen is whatever `backdrop` draws: the settlement, as it was left.
    """

    def __init__(
        self,
        canvas: pygame.Surface,
        world: SimulationWorld,
        font: BitmapFont,
        faces: FaceRenderer,
        dock: pygame.Rect | None = None,
        backdrop: Callable[[], None] | None = None,
        layers: ScreenLayers | None = None,
        voices: VoicePlayer | None = None,
    ) -> None:
        self.canvas = canvas
        self.layers = layers
        # What says the question out loud, if there are voices to say it with.
        self.voices = voices
        self.world = world
        self.font = font
        self.faces = faces
        self.dock = dock if dock is not None else canvas.get_rect()
        self.backdrop = backdrop
        self.decision: Decision | None = None
        # Narration shown once the resident has decided, until the player moves on.
        self.result: str | None = None
        self.expression = "angry"
        # Set when the player is finished here and the global view should come back.
        self.closed = False
        self.buttons: list[Button] = []

    def open(self, decision_id: str | None) -> None:
        """Show the given open decision, or say that there is none."""
        self.decision = self.world.decisions.get(decision_id) if decision_id else None
        self.result = None
        # Someone weighing a job or their own heart is not at the end of their tether, as in a crisis.
        self.expression = DECISION_EXPRESSIONS.get(self.decision.kind if self.decision else "", "angry")
        self.closed = False
        self.buttons = self._option_buttons()
        if self.decision is not None and self.voices is not None:
            # They ask it out loud, over whatever was being said.
            self.voices.say(self.decision.resident_id, self.decision.prompt, interrupt=True)

    def _option_buttons(self) -> list[Button]:
        """The advice on offer, one under another down the side of the dock."""
        if self.decision is None:
            return []
        side = dock_areas(self.dock).side
        buttons = []
        for index, option in enumerate(self.decision.options):
            label = self.font.truncate(f"[{index + 1}] {option.text}", side.width - 8)
            button = Button.at(self.font, side.x, side.y + index * (OPTION_HEIGHT + OPTION_GAP), label, option.option_id)
            button.rect.size = (side.width, OPTION_HEIGHT)
            buttons.append(button)
        return buttons

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.KEYDOWN:
            if self.result is not None or self.decision is None:
                if event.key in CONTINUE_KEYS:
                    self.closed = True
            elif event.key in OPTION_KEYS[: len(self.buttons)]:
                self.choose(self.buttons[OPTION_KEYS.index(event.key)].intent)
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            position = canvas_position(event.pos)
            if self.result is not None or self.decision is None:
                self.closed = True
                return
            for button in self.buttons:
                if button.contains(position):
                    self.choose(button.intent)
                    return

    def choose(self, option_id: str) -> None:
        """Send the player's advice and show what the resident does with it."""
        if self.decision is None or self.result is not None:
            return
        before = len(self.world.history)
        outcome = self.world.apply_command(ChooseOptionCommand(self.decision.decision_id, option_id))
        resolved = [e for e in self.world.history[before:] if e.event_type == "crisis_resolved"]
        self.result = resolved[-1].text if resolved else "Ya no hay nada que decidir."
        self.expression = OUTCOME_EXPRESSIONS.get(str(outcome), "neutral")

    def update(self, dt: float) -> None:
        pass

    def render(self) -> None:
        if self.backdrop is not None:
            self.backdrop()
        else:
            self.canvas.fill(PALETTE["ink"])
        dock, decision = self.dock, self.decision
        resident = self.world.residents.get(decision.resident_id) if decision is not None else None
        if decision is None or resident is None:
            draw_panel(self.canvas, dock, fill="shadow", border="lamp")
            self.font.draw(self.canvas, NOBODY_TITLE, (dock.x + 12, dock.y + 12), PALETTE["glow"], scale=2)
            y = dock.y + 12 + LINE_HEIGHT * 2 + 6
            for line in self.font.wrap(NOBODY_TEXT, dock.width - 24):
                self.font.draw(self.canvas, line, (dock.x + 12, y), PALETTE["dust"])
                y += LINE_HEIGHT
            return

        crisis = decision.crisis
        target = self.world.residents.get(crisis.target_id) if crisis and crisis.target_id else None
        across = (target.resident_id, "neutral", target.name) if target is not None else None
        text = decision.prompt if self.result is None else self.result
        areas = draw_scene(
            self.canvas,
            self.font,
            self.faces,
            dock,
            (resident.resident_id, self.expression, resident.name),
            across,
            text,
            narration=self.result is not None,
            layers=self.layers,
        )
        # A frame in the colour of an alert: this is waiting on the player.
        pygame.draw.rect(self.canvas, PALETTE["lamp"], dock, 1)
        self._render_under_speech(areas.speech, resident.resident_id, target)
        side = areas.side
        if self.result is not None:
            self.font.draw(self.canvas, CONTINUE_TEXT, side.topleft, PALETTE["lamp"])
            return
        for button in self.buttons:
            button.draw(self.canvas, self.font)
        y = (self.buttons[-1].rect.bottom if self.buttons else side.y) + 4
        notes = [
            (f"Pulsa 1-{len(self.buttons)} o haz clic. Tu consejo influye, pero quien decide es {resident.name}.", "dust"),
            (self._leaning_text(decision, resident.name, target.name if target else ""), "stone"),
            (f"{self.world.clock.label} · el tiempo está detenido", "stone"),
        ]
        for note, color in notes:
            for line in self.font.wrap(note, side.width):
                if y + LINE_HEIGHT > side.bottom + 2:
                    return
                self.font.draw(self.canvas, line, (side.x, y), PALETTE[color])
                y += LINE_HEIGHT

    def _render_under_speech(self, speech: pygame.Rect, resident_id: str, target) -> None:
        """What the resident feels about the other, in the strip left under what is said."""
        if target is None:
            return
        feelings = self.world.relationships.get((resident_id, target.resident_id))
        felt = "  ".join(
            f"{label} {round(getattr(feelings, feeling)) if feelings is not None else 0}"
            for feeling, label in FEELING_LABELS.items()
        )
        line = self.font.truncate(f"Por {target.name}: {felt}", speech.width)
        left = speech.centerx - self.font.width(line) // 2
        self.font.draw(self.canvas, line, (left, speech.bottom + 6), PALETTE["bone"])

    def _leaning_text(self, decision: Decision, name: str, target_name: str) -> str:
        """What the resident will probably do if the player says nothing."""
        definition = self.world.registries.decisions.get(decision.kind)
        intent = decision.crisis.intent if decision.crisis else ""
        if definition is None or intent not in definition.outcomes:
            return ""
        job = self.world.registries.jobs.get(decision.job_id or "")
        text = (
            definition.outcomes[intent]
            .text.replace("{name}", name)
            .replace("{target}", target_name)
            .replace("{job}", job.name if job is not None else "")
        )
        return f"Si nadie le dice nada: {text}."
