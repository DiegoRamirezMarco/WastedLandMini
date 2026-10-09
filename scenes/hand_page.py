"""Where a doll's hands and feet are chosen: made, in a colour of one's picking, or the ones
drawn on it.

It is a page of the one screen (`scenes/studio.py`), which shows it and lays it out: it was a
screen of its own once, and no longer shows itself. Nothing is drawn here. The two sides of a
hand are shown large, held whichever way is picked: open, loose, shut on something, a fist,
anywhere between with the bar under them, or opening and shutting by themselves. Under them
are the two feet. What is picked of them is kept apart from the doll's drawings.
"""

import math
from pathlib import Path

import pygame

from graphics.doll import BODY_CANVAS, HEAD_CANVAS, Doll, DollBuild, DollStore, doll_plan
from graphics.face import FaceStore, faced
from graphics.font import BitmapFont
from graphics.foot import Feet, Made
from graphics.hand import LINE_STEP, HandPose, Hands, HandStore
from graphics.palette import PALETTE
from graphics.screen_layers import ScreenLayers
from graphics.volume import turned_body
from scenes.doll_page import HEAD_AT, PREVIEW_YAW, TOOLS_LEFT, DollPaper
from skeleton.plan import SkeletonPlan
from ui.button import Button

# Window pixels to one of the skeleton's for the hands shown large, and for the doll.
LARGE_DETAIL = 62.0
# How long the bone of a foot shown large is taken to be, in the skeleton's measure.
FOOT_LONG = 1.8
# What the doll goes through, and for how many seconds each.
CLIPS = ("walk", "idle", "fight", "hammer", "argue_arms")
CLIP_SECONDS = 3.5
# Seconds a hand takes to open and shut again when it does so by itself.
CYCLE_SECONDS = 2.4
# How much larger or smaller a press makes them, and how much thicker or thinner what is held.
SIZE_STEP = 0.1
THICK_STEP = 0.2
WOOD = (120, 86, 52)
LINE = (30, 22, 20)
SAVED_TEXT = "Manos guardadas"
# What the colour in hand is the colour of, and how far down the room the hands give way to the feet.
HANDS, FEET = "hands", "feet"
FEET_FROM = 0.58
HANDS_AT, FEET_AT = 0.2, 0.7
MADE_LABELS = {True: "Manos: de bola y dedos", False: "Manos: las dibujadas"}
CYCLE_LABELS = {True: "Abriendo y cerrando", False: "Abrir y cerrar"}
HELD_LABELS = {True: "Con algo cogido", False: "Sin nada cogido"}
BY_CLIP = "Según el gesto"
NOTES_TEXT = (
    "El color de la mano es el que se elija aquí arriba.",
    "La barra de abajo la abre y la cierra a mano. Con algo cogido, los dedos lo rodean sea fino o grueso.",
    "A la derecha, el muñeco con la mano que toca a cada gesto.",
)


class HandPaper(DollPaper):
    """Choose a doll's hands. It is opened for a doll as it stands on the screen it is drawn
    on, and keeps what is chosen apart from its drawings."""

    def __init__(
        self,
        canvas: pygame.Surface,
        font: BitmapFont,
        layers: ScreenLayers,
        root: Path,
        dolls: DollStore,
        plan: SkeletonPlan,
        faces: FaceStore,
        hand_store: HandStore,
    ) -> None:
        super().__init__(canvas, font, layers, root, dolls, plan, faces, hand_store)
        self.rules = hand_store.rules
        self.hands = Hands(self.rules)
        self._doll: Doll | None = None
        self._body_drawing: pygame.Surface | None = None
        self._head_drawing: pygame.Surface | None = None
        # Nothing is painted here: there is no paper, and no brush to pick.
        self.areas, self.drawings, self.brush_buttons = {}, {}, []
        # How the hands shown large are held: a way of the data's, or wherever the bar has them,
        # or neither, which is as each gesture has them. And whether they open and shut by themselves.
        self.pose_id: str | None = None
        self.manual: float | None = None
        self.cycling = False
        self.holding = False
        self.thick = 0.6
        self._on_bar = False
        self._shown_at = 0.0
        # Where the hands are shown large and the bar that opens and shuts them: for whoever lays this out otherwise.
        self.room = pygame.Rect(196, 58, 400, 330)
        self.bar = pygame.Rect(236, 406, 320, 10)
        # The feet of the same doll, shown under its hands, and which of the two the colour in
        # hand is the colour of.
        self.feet: Feet | None = None
        self.making = HANDS
        # Whether that colour is the colour of the line round them, and not of what is inside it.
        self.of_line = False

        y = self.field.rect.bottom + 8
        self.made_button = self._wide(y, MADE_LABELS, ("made",))
        self.size_buttons = self._row(y + 18, [("Más pequeñas", ("size", -1)), ("Más grandes", ("size", 1))])
        self.finger_buttons = self._row(y + 34, [("Menos dedos", ("fingers", -1)), ("Más dedos", ("fingers", 1))])
        self.pose_buttons = self._row(y + 54, [(pose.name, ("pose", pose_id)) for pose_id, pose in self.rules.poses.items()])
        self.auto_button = Button.at(font, TOOLS_LEFT, y + 70, BY_CLIP, ("pose", None))
        self.cycle_button = self._wide(y + 86, CYCLE_LABELS, ("cycle",))
        self.held_button = self._wide(y + 106, HELD_LABELS, ("held",))
        self.thick_buttons = self._row(y + 122, [("Más fino", ("thick", -1)), ("Más grueso", ("thick", 1))])
        self.notes_room = pygame.Rect(TOOLS_LEFT, y + 142, 180, canvas.get_height() - y - 146)
        self.top_buttons = self._row(6, [("Guardar", ("save",)), ("Volver", ("close",))], left=HEAD_AT[0])

    def _wide(self, y: int, labels: dict[bool, str], intent: tuple) -> Button:
        """A button that says one of two things, as wide as the longer of them."""
        button = Button.at(self.font, TOOLS_LEFT, y, labels[False], intent)
        button.rect.width = max(self.font.width(label) for label in labels.values()) + 8
        return button

    @property
    def buttons(self) -> list[Button]:
        return [
            *self.top_buttons, self.made_button, *self.size_buttons, *self.finger_buttons, *self.pose_buttons,
            self.auto_button, self.cycle_button, self.held_button, *self.thick_buttons,
        ]

    def open_for(self, body_id: str, drawings: dict[str, pygame.Surface], build: DollBuild, depth: float | None = None) -> None:
        """Begin on somebody's hands, over their body as it stands now. One nobody has drawn
        yet is the plain figure meanwhile."""
        self.resident_id = body_id
        self.closed = False
        self.notice = ""
        self.build = build
        if depth is not None:
            self.depth = depth
        self.template = self.base_template.built(build)
        self.doll_plan = doll_plan(self.plan, self.template, build)
        plain = self.plain_figures()
        shown = {
            name: drawings[name] if name in drawings and pygame.mask.from_surface(drawings[name]).count() else plain[name]
            for name in (BODY_CANVAS, HEAD_CANVAS)
        }
        self._body_drawing, self._head_drawing = shown[BODY_CANVAS], shown[HEAD_CANVAS]
        self.hands = self.hand_store.get(body_id)
        self.feet = self.foot_store.get(body_id) if self.foot_store is not None else None
        self.making, self.of_line = HANDS, False
        self.color = self.hands.color
        self._recut()

    def _recut(self) -> None:
        """Cut the doll again: with the hands it was drawn with, or without them for the ones made here."""
        body, head = self._body_drawing, self._head_drawing
        if body is None or head is None:
            return
        face = self.faces.get(self.resident_id) if self.faces is not None and self.resident_id else None
        doll = Doll(self.template, {BODY_CANVAS: body, HEAD_CANVAS: head}, self.doll_plan, Made(self.hands, self.feet).bones)
        self.match_made(doll)
        # From its side, as it is at what it does: its trunk, drawn from the front, gone round.
        rules = self.faces.rules
        self._doll = turned_body(faced(doll, face, head, PREVIEW_YAW), rules.body, rules.side, self.depth, rules.side)

    def save(self) -> bool:
        if self.resident_id is None or not self.hand_store.save(self.resident_id):
            self.notice = "No se pudo guardar"
            return False
        self.notice = SAVED_TEXT
        return True

    def _apply(self, intent: tuple) -> None:
        hands = self.hands
        if intent[0] == "made":
            hands.choose(made=not hands.choice.made)
            self._recut()
        elif intent[0] == "size":
            low, high = self.rules.sizes
            hands.choose(size=round(max(low, min(high, hands.size + SIZE_STEP * intent[1])), 2))
        elif intent[0] == "fingers":
            low, high = self.rules.finger_counts
            hands.choose(fingers=max(low, min(high, hands.fingers + intent[1])))
        elif intent[0] == "feet_made" and self.feet is not None:
            self.feet.choose(made=not self.feet.choice.made)
            self._recut()
        elif intent[0] == "feet_size" and self.feet is not None:
            low, high = self.feet.rules.sizes
            self.feet.choose(size=round(max(low, min(high, self.feet.size + SIZE_STEP * intent[1])), 2))
        elif intent[0] == "line_color":
            self.of_line = not self.of_line
        elif intent[0] == "line":
            mine = self.chosen_made()
            low, high = mine.rules.lines
            mine.choose(line=round(max(low, min(high, mine.bold + LINE_STEP * intent[1])), 2))
        elif intent[0] == "pose":
            self.pose_id, self.manual, self.cycling = intent[1], None, False
        elif intent[0] == "cycle":
            self.cycling = not self.cycling
        elif intent[0] == "held":
            self.holding = not self.holding
        elif intent[0] == "thick":
            low, high = self.rules.held_thick
            self.thick = round(max(low + THICK_STEP, min(high, self.thick + THICK_STEP * intent[1])), 2)
        else:
            super()._apply(intent)


    def _on_the_bar(self, position: tuple[int, int]) -> None:
        """Have the hands as far shut as the mouse is along the bar."""
        self.manual = max(0.0, min(1.0, (position[0] - self.bar.x) / self.bar.width))
        self.pose_id, self.cycling = None, False

    def press(self, position: tuple[int, int]) -> None:
        if self.bar.inflate(8, 14).collidepoint(position):
            self._on_bar = True
            self._on_the_bar(position)
            return
        super().press(position)
        self._take_color()

    def drag(self, position: tuple[int, int]) -> None:
        if self._on_bar:
            self._on_the_bar(position)
            return
        super().drag(position)
        self._take_color()

    def release(self) -> None:
        self._on_bar = False
        super().release()

    def _take_color(self) -> None:
        """The colour in hand is the colour of the hands, or of the feet if those are what is being made."""
        mine = self.chosen_made()
        if tuple(self.color) != tuple(self.chosen_color()):
            mine.choose(**{"line_color" if self.of_line else "color": tuple(self.color)})

    def chosen_color(self) -> tuple[int, int, int]:
        """The colour that the colour in hand is: of the hands or of the feet, of what is
        inside their line or of the line itself."""
        mine = self.chosen_made()
        return mine.ink if self.of_line else mine.color

    def chosen_made(self) -> Hands | Feet:
        """Whichever of the two the colour in hand is the colour of."""
        return self.feet if self.making == FEET and self.feet is not None else self.hands

    def feet_from(self) -> int:
        """How far down the room the hands give way to the feet."""
        return self.room.y + round(self.room.height * FEET_FROM)

    def picked(self) -> HandPose | None:
        """How the hands are held by whoever is at this screen. None for as each gesture has them."""
        if self.cycling:
            shut = 0.5 - 0.5 * math.cos(self.time / CYCLE_SECONDS * math.tau)
            return HandPose(shut, 1.0 - shut)
        if self.manual is not None:
            return HandPose(self.manual, 1.0 - self.manual)
        return self.rules.poses[self.pose_id] if self.pose_id is not None else None

    def _clip(self) -> str:
        return CLIPS[int(self.time / CLIP_SECONDS) % len(CLIPS)]

    # --- what is shown ---


    def _show_hands(self, screen: pygame.Surface) -> None:
        """The hand of the near side and the one of the far side, large, held as picked."""
        place = self.layers.on_screen(self.room)
        screen.fill(PALETTE["earth"], place)
        pose = self.picked() or self.rules.pose_for(self._clip())
        stick = (self.thick, WOOD) if self.holding else None
        if stick is not None:
            pose = self.rules.holding(self.thick)
        long = 1.6
        for name, across in (("hand_left", 0.73), ("hand_right", 0.3)):
            # Side by side they are the two sides of a hand: its back, as the near one is seen,
            # and its palm, as the far one is from its side.
            image, joint = self.hands.picture(name, 0.0, long, False, LARGE_DETAIL, pose, stick, other=True, back=name == "hand_right")
            wrist = (place.x + place.width * across, place.y + place.height * HANDS_AT)
            before = screen.get_clip()
            screen.set_clip(place)
            screen.blit(image, (round(wrist[0] - joint[0]), round(wrist[1] - joint[1])))
            screen.set_clip(before)
        if self.feet is None:
            return
        # Under them the two feet, flat on the ground and seen from their side.
        for name, across in (("foot_left", 0.66), ("foot_right", 0.23)):
            image, joint = self.feet.picture(name, math.pi / 2, FOOT_LONG, False, LARGE_DETAIL, 1.0)
            ankle = (place.x + place.width * across, place.y + place.height * FEET_AT)
            before = screen.get_clip()
            screen.set_clip(place)
            screen.blit(image, (round(ankle[0] - joint[0]), round(ankle[1] - joint[1])))
            screen.set_clip(before)

