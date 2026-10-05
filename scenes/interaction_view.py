import pygame

from graphics.face_renderer import FACE_SIZE, FaceRenderer
from graphics.font import LINE_HEIGHT, BitmapFont
from graphics.palette import PALETTE
from scenes.scene import canvas_position
from simulation.commands import ChooseOptionCommand
from simulation.events.decision import Decision
from simulation.world import SimulationWorld
from ui.button import Button
from ui.dialogue_box import draw_dialogue_box
from ui.labels import FEELING_LABELS
from ui.panel import draw_panel

FACE_SCALE = 2
PORTRAIT = (FACE_SIZE[0] * FACE_SCALE, FACE_SIZE[1] * FACE_SCALE)
LEFT_PORTRAIT = (72, 62)
RIGHT_PORTRAIT = (440, 62)
BOX = pygame.Rect(72, 214, 496, 50)
OPTIONS_TOP = 276
OPTION_GAP = 8
OPTION_KEYS = (pygame.K_1, pygame.K_2, pygame.K_3, pygame.K_4, pygame.K_5, pygame.K_6)
CONTINUE_KEYS = (pygame.K_SPACE, pygame.K_RETURN)
# Face each resident shows once they have made up their mind, by outcome ID.
OUTCOME_EXPRESSIONS = {
    "confront": "angry", "talk_it_out": "neutral", "cool_off": "sad", "fight": "angry", "walk_away": "sad",
    "take": "happy", "stay": "neutral", "confess": "happy", "keep_quiet": "sad", "break_up": "sad",
    "push_on": "happy", "turn_back": "sad", "let_in": "happy", "turn_away": "angry",
}
# Face a resident wears while they make up their mind, by kind of decision. Anger for any other.
DECISION_EXPRESSIONS = {"job_offer": "neutral", "confession": "neutral", "breakup": "sad", "risky_find": "neutral",
                        "stranger": "neutral"}


class InteractionView:
    """Close-up of a resident asking for advice. Time stands still while it is open."""

    def __init__(
        self, canvas: pygame.Surface, world: SimulationWorld, font: BitmapFont, faces: FaceRenderer
    ) -> None:
        self.canvas = canvas
        self.world = world
        self.font = font
        self.faces = faces
        self.decision: Decision | None = None
        # Narration shown once the resident has decided, until the player moves on.
        self.result: str | None = None
        self.expression = "angry"
        # Set when the player is finished here and the global view should come back.
        self.closed = False
        self.buttons: list[Button] = []

    def open(self, decision_id: str | None) -> None:
        """Show the given open decision, or an empty scene if there is none."""
        self.decision = self.world.decisions.get(decision_id) if decision_id else None
        self.result = None
        # Someone weighing a job or their own heart is not at the end of their tether, as in a crisis.
        self.expression = DECISION_EXPRESSIONS.get(self.decision.kind if self.decision else "", "angry")
        self.closed = False
        self.buttons = self._option_buttons()

    def _option_buttons(self) -> list[Button]:
        if self.decision is None:
            return []
        count = len(self.decision.options)
        width = (BOX.width - OPTION_GAP * (count - 1)) // count
        buttons = []
        for index, option in enumerate(self.decision.options):
            label = self.font.truncate(f"[{index + 1}] {option.text}", width - 8)
            button = Button.at(self.font, BOX.x + index * (width + OPTION_GAP), OPTIONS_TOP, label, option.option_id)
            button.rect.width = width
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

    def _portrait(self, position: tuple[int, int], face_id: str, expression: str, name: str) -> None:
        frame = pygame.Rect(position[0] - 3, position[1] - 3, PORTRAIT[0] + 6, PORTRAIT[1] + 6)
        draw_panel(self.canvas, frame, fill="iron", border="stone")
        face = pygame.transform.scale(self.faces.face(face_id, expression), PORTRAIT)
        self.canvas.blit(face, position)
        self.font.draw(
            self.canvas, name, (frame.centerx - self.font.width(name) // 2, frame.bottom + 4), PALETTE["paper"]
        )

    def render(self) -> None:
        self.canvas.fill(PALETTE["ink"])
        decision = self.decision
        if decision is None:
            self.font.draw(self.canvas, "Nadie necesita consejo", (24, 16), PALETTE["glow"], scale=2)
            message = "Cuando alguien esté al límite verás un ! sobre su cabeza. ESPACIO o TAB para volver."
            self.font.draw(self.canvas, message, (24, 46), PALETTE["dust"])
            return

        resident = self.world.residents.get(decision.resident_id)
        crisis = decision.crisis
        target = self.world.residents.get(crisis.target_id) if crisis and crisis.target_id else None
        if resident is None:
            return
        self.font.draw(self.canvas, f"{resident.name} necesita consejo", (24, 12), PALETTE["glow"], scale=2)
        subtitle = f"{self.world.clock.label} · el tiempo está detenido"
        self.font.draw(self.canvas, subtitle, (24, 38), PALETTE["stone"])

        self._portrait(LEFT_PORTRAIT, resident.resident_id, self.expression, resident.name)
        if target is not None:
            self._portrait(RIGHT_PORTRAIT, target.resident_id, "neutral", target.name)
            self._render_feelings(resident.resident_id, target.resident_id, target.name)

        if self.result is None:
            draw_dialogue_box(self.canvas, self.font, BOX, f'"{decision.prompt}"', speaker=resident.name)
            for button in self.buttons:
                button.draw(self.canvas, self.font)
            hint = f"Pulsa 1-{len(self.buttons)} o haz clic. Tu consejo influye, pero quien decide es {resident.name}."
            self.font.draw(self.canvas, hint, (BOX.x, OPTIONS_TOP + 22), PALETTE["dust"])
            leaning = self._leaning_text(decision, resident.name, target.name if target else "")
            if leaning:
                self.font.draw(self.canvas, leaning, (BOX.x, OPTIONS_TOP + 22 + LINE_HEIGHT), PALETTE["stone"])
        else:
            draw_dialogue_box(self.canvas, self.font, BOX, self.result)
            self.font.draw(self.canvas, "ESPACIO para continuar", (BOX.x, OPTIONS_TOP + 4), PALETTE["lamp"])

    def _render_feelings(self, resident_id: str, target_id: str, target_name: str) -> None:
        """What the resident feels about the other, between the two portraits."""
        feelings = self.world.relationships.get((resident_id, target_id))
        left = LEFT_PORTRAIT[0] + PORTRAIT[0] + 3
        centre = (left + RIGHT_PORTRAIT[0] - 3) // 2
        lines = [f"Lo que siente por {target_name}"] + [
            f"{label} {round(getattr(feelings, feeling)) if feelings is not None else 0}"
            for feeling, label in FEELING_LABELS.items()
        ]
        y = LEFT_PORTRAIT[1] + 40
        for index, line in enumerate(lines):
            color = PALETTE["dust"] if index == 0 else PALETTE["bone"]
            self.font.draw(self.canvas, line, (centre - self.font.width(line) // 2, y), color)
            y += LINE_HEIGHT

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
