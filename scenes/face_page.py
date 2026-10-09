"""Where a face is made: each piece drawn on a paper of its own, and put on the head by hand.

It is a page of the one screen (`scenes/studio.py`), which shows it and says where its paper
and its head go: it was a screen of its own once, and no longer shows itself. It is the page a
doll is drawn on, with other papers: that of one kind of piece at a time, and a head shown
large with everything on it, where a piece is taken hold of and put where it goes in a view.

Nothing is put anywhere but from the front until somebody does it: turned, a piece is where it
works out to be (`graphics/face.py`), and that is what dragging it puts right.
"""

from dataclasses import replace
from pathlib import Path

import pygame

from graphics.doll import BODY_CANVAS, HEAD_CANVAS, Doll, DollBuild, DollStore, doll_plan
from graphics.face import FRONT, NARROWEST, WIDEST, Face, FaceStore, Key, head_of
from graphics.face_examples import example, skin_of
from graphics.font import BitmapFont
from graphics.hand import HandStore
from graphics.palette import PALETTE
from graphics.screen_layers import TRANSPARENT, ScreenLayers
from graphics.turn import limbs_apart
from scenes.doll_page import BACK_PAPER  # noqa: I001
from scenes.doll_page import BRUSH_TOOL, ERASER_TOOL, FILL_TOOL, HEAD_AT, TOOL_LABELS, TOOLS_LEFT, DollPaper
from scenes.scene import canvas_position
from skeleton.plan import SkeletonPlan
from ui.button import Button

# The room there is for the paper of a piece, between the tools and the head.
PAPER_ROOM = pygame.Rect(196, 60, 400, 386)
TABS_Y = 44
VIEWS_Y = 42
# Canvas pixels round the painted part of a piece within which it is taken hold of.
REACH = 3
# How much of its width a turn of the wheel gives a piece or takes from it.
WIDER = 0.05
GUIDE_INK = (120, 110, 100, 255)
SAVED_TEXT = "Cara guardada"
SYMMETRIC_LABELS = {True: "Simetría: sí", False: "Simetría: no"}
SWEEP_LABELS = {True: "Girando", False: "Girar"}
BODY_LABELS = {True: "Cuerpo: gira", False: "Cuerpo: de lado"}
NOTES_TEXT = (
    "Cada pieza se dibuja en su papel y se arrastra a su sitio en la cabeza de la derecha.",
    "En 3/4 y perfil ya está donde le toca: arrástrala para corregirlo. Auto lo deshace.",
    "Rueda: ancho. Clic derecho: se ve o no. B: delante o detrás.",
)


class FacePaper(DollPaper):
    """Draw the pieces of a face and put them on a head. It is opened for a doll as it stands in
    the screen it is drawn on, saved or not, and what it makes is kept apart from that."""

    def __init__(
        self,
        canvas: pygame.Surface,
        font: BitmapFont,
        layers: ScreenLayers,
        root: Path,
        dolls: DollStore,
        plan: SkeletonPlan,
        faces: FaceStore,
        hand_store: HandStore | None = None,
    ) -> None:
        super().__init__(canvas, font, layers, root, dolls, plan, faces, hand_store)
        self.rules = faces.rules
        self.kind = next(iter(self.rules.kinds))
        self.view = FRONT
        self.symmetric = True
        self.sweeping = False
        # The body comes round with the head, as far as a body can.
        self.body_turns = True
        self.face = Face(self.rules)
        self.head = pygame.Surface(self.template.canvases[HEAD_CANVAS], pygame.SRCALPHA)
        self.stage = pygame.Rect(HEAD_AT, self.head.get_size())
        # How many times as large as the head's paper the head is shown where pieces are put in
        # place, and the room there is for the paper of a piece: for whoever lays this out otherwise.
        self.stage_zoom = 1
        self.paper_room = PAPER_ROOM
        # The doll without its head, and with each head it has been given: by how far round that is.
        self._bare: Doll | None = None
        self._heads: dict[int, Doll] = {}
        # And each of those with its body turned too: by how far round the head is, and the body.
        self._bodies: dict[tuple[int, float], Doll] = {}
        # The piece the mouse has hold of on the head and how far from its middle, and the one last taken hold of.
        self._held: tuple[str, tuple[float, float]] | None = None
        self.chosen: str | None = None

        # The tools of the screen it is made of, without what is not for a face.
        row = self.tool_buttons[0].rect.y
        self.tool_buttons = self._row(row, [(TOOL_LABELS[tool], ("tool", tool)) for tool in (BRUSH_TOOL, ERASER_TOOL, FILL_TOOL)])
        self.mannequin_button.label = "Cara de ejemplo"
        self.mannequin_button.rect.width = font.width(self.mannequin_button.label) + 8
        y = self.measures_button.rect.y
        self.measures_button = self._toggle(y, SYMMETRIC_LABELS, ("symmetric",))
        self.sweep_button = self._toggle(y + 16, SWEEP_LABELS, ("sweep",))
        self.body_button = self._toggle(y + 32, BODY_LABELS, ("body",))
        self.notes_room = pygame.Rect(TOOLS_LEFT, y + 52, 180, canvas.get_height() - y - 56)
        self.top_buttons = self._row(6, [("Guardar", ("save",)), ("Volver", ("close",))], left=HEAD_AT[0])
        self.tab_buttons = self._row(TABS_Y, [(kind.name, ("kind", kind.kind_id)) for kind in self.rules.kinds.values()], left=PAPER_ROOM.x)
        self.view_buttons = self._row(VIEWS_Y, [(self.rules.view_names[view], ("view", view)) for view in self.rules.views], left=HEAD_AT[0])
        self.view_buttons.append(Button.at(font, self.view_buttons[-1].rect.right + 9, VIEWS_Y, "Auto", ("auto",)))
        self.extra_buttons = [*self.tab_buttons, *self.view_buttons, self.sweep_button, self.body_button]

    def _toggle(self, y: int, labels: dict[bool, str], intent: tuple) -> Button:
        """A button that says one of two things, as wide as the longer of them."""
        button = Button.at(self.font, TOOLS_LEFT, y, labels[False], intent)
        button.rect.width = max(self.font.width(label) for label in labels.values()) + 8
        return button

    def open_for(self, body_id: str, drawings: dict[str, pygame.Surface], build: DollBuild, depth: float | None = None) -> None:
        """Begin on somebody's face, over their head and their body as those stand now. A head
        or a body nobody has drawn yet is the plain figure meanwhile."""
        self.resident_id = body_id
        self.closed = False
        self.notice = ""
        self._undo, self._stroke, self._draft, self._held, self.chosen = [], None, None, None, None
        self.build = build
        self.depth = depth if depth is not None else self.rules.body.depth
        self.template = self.base_template.built(build)
        self.doll_plan = doll_plan(self.plan, self.template, build)
        plain = self.plain_figures()
        shown = {
            name: drawings[name] if name in drawings and pygame.mask.from_surface(drawings[name]).count() else plain[name]
            for name in (BODY_CANVAS, HEAD_CANVAS)
        }
        self.head = shown[HEAD_CANVAS]
        # With its head as it is drawn, which is what it has until something is put on it.
        self._bare = Doll(self.template, shown, self.doll_plan, self.left_out())
        self._apart = limbs_apart(self.rules.body, self._bare)
        self.face = self.faces.get(body_id)
        # The papers that are drawn on are the face's own: what is painted here is painted on it.
        self.drawings = self.face.drawings
        self.guides = {kind_id: self._piece_guide(kind_id) for kind_id in self.rules.kinds}
        self._show_paper(self.kind)
        self._cut()

    def _show_paper(self, kind_id: str) -> None:
        """Have the paper of one kind of piece be the one that is drawn on."""
        kind = self.rules.kinds[kind_id]
        self.kind = kind_id
        self._draft = None
        size = (kind.paper[0] * kind.zoom, kind.paper[1] * kind.zoom)
        area = pygame.Rect((0, 0), size)
        area.midtop = (self.paper_room.centerx, self.paper_room.y)
        self.areas = {kind_id: area}
        self.zooms = {kind_id: kind.zoom}

    def _piece_guide(self, kind_id: str) -> pygame.Surface:
        """What is shown under the paper of a kind of piece: the head itself for what is laid
        over the whole of it, and for the rest the middle of the paper, which is what is put in place."""
        kind = self.rules.kinds[kind_id]
        guide = pygame.Surface(kind.paper, pygame.SRCALPHA)
        if kind.over_head:
            # The head where it is under this paper: their tops together, one in the middle of the other.
            guide.blit(self.head, ((kind.paper[0] - self.head.get_width()) // 2, 0))
            return guide
        width, height = kind.paper
        for x in range(0, width, 4):
            guide.set_at((x, height // 2), GUIDE_INK)
        for y in range(0, height, 4):
            guide.set_at((width // 2, y), GUIDE_INK)
        return guide

    def _named_guide(self, canvas: str) -> pygame.Surface:
        # The papers of the screen this is made of are named as they were; a face's are not its.
        return super()._named_guide(canvas) if canvas in (BODY_CANVAS, HEAD_CANVAS, BACK_PAPER) else self._piece_guide(canvas)

    def _cut(self) -> None:
        """Have the head made again from the drawings as they stand, wherever it is shown."""
        self.face.touch()
        self._heads.clear()
        self._bodies.clear()

    @property
    def yaw(self) -> float:
        """How far round the head is in the view that pieces are being put in place in."""
        return self.rules.views[self.view]


    def clear(self) -> None:
        """Wipe the paper in hand, and no other."""
        self._remember(self.kind)
        self.drawings[self.kind].fill(TRANSPARENT)
        self._cut()

    def mannequin(self) -> None:
        """Fill every paper nobody has drawn on with a plain piece, to try putting them in place."""
        head = head_of(self.head)
        skin = skin_of(self.head, head)
        for kind in self.rules.kinds.values():
            if self.face.painted(kind.kind_id).width:
                continue
            picture = example(kind.kind_id, kind.paper, skin, self.face.on_paper(kind.kind_id, head, self.head.get_size()))
            if picture is not None:
                self._remember(kind.kind_id)
                self.drawings[kind.kind_id] = picture
        self._cut()

    def save(self) -> bool:
        if self.resident_id is None or not self.faces.save(self.resident_id):
            self.notice = "No se pudo guardar"
            return False
        self.notice = SAVED_TEXT
        return True

    def _apply(self, intent: tuple) -> None:
        if intent[0] == "kind":
            self._show_paper(intent[1])
        elif intent[0] == "view":
            self.view = intent[1]
        elif intent[0] == "auto":
            # Whatever has been put by hand in this view goes back to where it works out to be.
            self.face.forget_keys(self.view, self.chosen)
            self._cut()
        elif intent[0] == "symmetric":
            self.symmetric = not self.symmetric
        elif intent[0] == "sweep":
            self.sweeping = not self.sweeping
        elif intent[0] == "body":
            self.body_turns = not self.body_turns
        else:
            super()._apply(intent)
        self.measures_button.label = SYMMETRIC_LABELS[self.symmetric]
        self.sweep_button.label = SWEEP_LABELS[self.sweeping]
        self.body_button.label = BODY_LABELS[self.body_turns]


    # --- the head, and what is put on it by hand ---

    def _laid(self) -> list[tuple[str, Key, pygame.Surface, pygame.Rect]]:
        return self.face.laid(self.head, self.yaw)

    def _on_stage(self, position: tuple[int, int]) -> tuple[float, float]:
        """Where on the head's paper a place on the screen is, over the head where pieces are put in place."""
        return ((position[0] - self.stage.x) / self.stage_zoom, (position[1] - self.stage.y) / self.stage_zoom)

    def piece_at(self, position: tuple[int, int]) -> str | None:
        """The piece on the head under a place on the screen: the topmost there, seen or not."""
        at = self._on_stage(position)
        near = pygame.Rect(round(at[0]) - REACH, round(at[1]) - REACH, REACH * 2 + 1, REACH * 2 + 1)
        for piece, key, picture, box in reversed(self._laid()):
            if not box.colliderect(near):
                continue
            # By what is painted, and not by its paper: hair goes round a face without being over it.
            corner = (round(key.x - picture.get_width() / 2), round(key.y - picture.get_height() / 2))
            under = near.move(-corner[0], -corner[1]).clip(picture.get_rect())
            if under.width and pygame.mask.from_surface(picture.subsurface(under)).count():
                return piece
        return None

    def _key(self, piece: str) -> Key:
        return self.face.key(piece, self.view, head_of(self.head), self.head.get_size())

    def _put(self, piece: str, key: Key) -> None:
        """Say where a piece goes in the view in hand. From the front, with the two sides alike,
        the other of a pair goes to the same place on its own side."""
        self.face.set_key(piece, self.view, key)
        kind = self.rules.kind_of(piece)
        if self.view == FRONT and self.symmetric and kind.paired:
            near, far = kind.instances
            other = far if piece == near else near
            middle = head_of(self.head).x
            self.face.set_key(other, FRONT, replace(self._key(other), x=2 * middle - key.x, y=key.y, wide=key.wide))
        self._heads.clear()

    def press(self, position: tuple[int, int]) -> None:
        if self.stage.collidepoint(position):
            piece = self.piece_at(position)
            self.chosen = piece
            if piece is not None:
                key = self._key(piece)
                at = self._on_stage(position)
                self._held = (piece, (at[0] - key.x, at[1] - key.y))
            return
        super().press(position)

    def drag(self, position: tuple[int, int]) -> None:
        if self._held is None:
            super().drag(position)
            return
        piece, (dx, dy) = self._held
        width, height = self.head.get_size()
        at = self._on_stage(position)
        x = min(float(width), max(0.0, at[0] - dx))
        y = min(float(height), max(0.0, at[1] - dy))
        self._put(piece, replace(self._key(piece), x=x, y=y))

    def release(self) -> None:
        self._held = None
        super().release()

    def widen(self, piece: str, by: float) -> None:
        key = self._key(piece)
        self._put(piece, replace(key, wide=min(WIDEST, max(NARROWEST, round(key.wide + by, 3)))))

    def toggle_shown(self, piece: str) -> None:
        key = self._key(piece)
        self._put(piece, replace(key, shown=not key.shown))

    def toggle_behind(self, piece: str) -> None:
        key = self._key(piece)
        self._put(piece, replace(key, behind=not key.behind))

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.MOUSEWHEEL:
            piece = self.piece_at(canvas_position(pygame.mouse.get_pos()))
            if piece is not None:
                self.chosen = piece
                self.widen(piece, WIDER * event.y)
            return
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 3 and self.stage.collidepoint(canvas_position(event.pos)):
            piece = self.piece_at(canvas_position(event.pos))
            if piece is not None:
                self.chosen = piece
                self.toggle_shown(piece)
            return
        if event.type == pygame.KEYDOWN and event.key == pygame.K_b and self.chosen is not None:
            self.toggle_behind(self.chosen)
            return
        super().handle_event(event)

    # --- what is shown ---


    def stage_frame(self, box: pygame.Rect) -> pygame.Rect:
        """Where on the screen a part of the head's paper is, with room round it, over the head
        where pieces are put in place."""
        zoom = self.stage_zoom
        frame = pygame.Rect(self.stage.x + box.x * zoom, self.stage.y + box.y * zoom, box.width * zoom, box.height * zoom)
        return frame.inflate(REACH * 2, REACH * 2).clip(self.stage)

    def _show_stage(self, screen: pygame.Surface) -> None:
        """The head with its face on, in the view in hand: what is not seen there is shown faintly."""
        place = self.layers.on_screen(self.stage)
        screen.fill(PALETTE["earth"], place)
        whole = self.face.composed(self.head, self.yaw, ghosts=True)
        screen.blit(pygame.transform.scale(whole, place.size), place)


