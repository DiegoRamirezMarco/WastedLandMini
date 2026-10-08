"""The families of the whole settlement on one screen: who is whose, the dead and the absent included.

It reads who is kin to whom and shows it. A click on somebody who lives here picks them, for
whoever opened the screen to go back to the map with.
"""

import pygame

from graphics.face_renderer import FaceRenderer
from graphics.font import LINE_HEIGHT, BitmapFont
from graphics.palette import PALETTE
from graphics.screen_layers import ScreenLayers
from scenes.scene import canvas_position
from simulation.world import SimulationWorld
from ui.button import Button
from ui.dock import draw_face
from ui.family_tree import ADOPTIVE, CARRIED, COUPLE, DEAD, ELSEWHERE, HERE, PARENT, SIBLING, SPOUSE, Person, Tree, family_tree

TITLE = "FAMILIAS"
SUBTITLE = "Quién es de quién en el asentamiento. Clic en alguien que vive aquí para ir a su ficha."
NOBODY = "Todavía no vive nadie aquí."
ALONE = "Sin familia aquí"
CLOSE_LABEL = "Volver"
HINT = "Arrastra o usa las flechas para moverte. Esc vuelve al mapa."
# A column and a row of the tree on the canvas, and the face of whoever stands in one.
CELL = (58, 64)
FACE = 32
# The part of the canvas the tree is shown in.
STAGE = pygame.Rect(8, 44, 784, 372)
MARGIN = 10
SCROLL_STEP = 24
# What is said under somebody who does not live here, and how dark their face is shown.
STATE_WORDS = {DEAD: "murió", ELSEWHERE: "no vive aquí"}
CARRIED_WORD = "en brazos"
VEIL = (16, 14, 14, 150)
# The colour of each kind of tie, and what it is called in the legend under the tree.
TIE_COLORS = {PARENT: "sand", ADOPTIVE: "teal", SPOUSE: "lamp", COUPLE: "rose", SIBLING: "dust"}
LEGEND = (
    (SPOUSE, "casados"),
    (COUPLE, "pareja"),
    (PARENT, "hijos"),
    (ADOPTIVE, "acogidos"),
    (SIBLING, "hermanos"),
)


def describe(person: Person) -> str:
    """What is said under somebody's name: how old they are, or why they are not about."""
    if person.state == HERE:
        return f"{person.age} años" if person.age is not None else ""
    if person.state == CARRIED:
        return CARRIED_WORD
    return STATE_WORDS.get(person.state, "")


class FamilyView:
    """The settlement's families. Time stands still while it is open."""

    def __init__(
        self,
        canvas: pygame.Surface,
        world: SimulationWorld,
        font: BitmapFont,
        faces: FaceRenderer,
        layers: ScreenLayers | None = None,
    ) -> None:
        self.canvas = canvas
        self.world = world
        self.font = font
        self.faces = faces
        self.layers = layers
        self.closed = True
        # Whoever was clicked on, for the map to go back to. None if nobody was.
        self.picked: str | None = None
        # Whoever it was opened about, who stands out on it.
        self.focus: str | None = None
        self.tree: Tree = family_tree(world)
        # How far the tree has been moved under the stage, in canvas pixels.
        self.scroll = [0, 0]
        self.pointer: tuple[int, int] | None = None
        self._drag: tuple[int, int] | None = None
        self._moved = False
        self.close_button = Button.at(font, STAGE.right - font.width(CLOSE_LABEL) - 8, 10, CLOSE_LABEL, ("close",))

    def open(self, focus: str | None = None) -> None:
        """Lay the families out as they are now, with whoever it is about in view."""
        self.tree = family_tree(self.world)
        self.closed, self.picked = False, None
        self.focus = focus if focus in self.tree.places else None
        self.scroll = [0, 0]
        self._drag, self._moved = None, False
        if self.focus is not None:
            box = self._cell(self.focus)
            self.pan(box.centerx - STAGE.centerx, box.centery - STAGE.centery)

    # ----- where things are -----

    def content(self) -> tuple[int, int]:
        """How large the whole tree is, in canvas pixels."""
        return (round(self.tree.size[0] * CELL[0]), round(self.tree.size[1] * CELL[1]))

    def _origin(self) -> tuple[int, int]:
        """Where the top left corner of the tree falls on the canvas: a tree narrower than the
        stage sits in the middle of it."""
        width, _ = self.content()
        spare = max(0, STAGE.width - MARGIN * 2 - width) // 2
        return (STAGE.x + MARGIN + spare - self.scroll[0], STAGE.y + MARGIN - self.scroll[1])

    def _cell(self, person_id: str) -> pygame.Rect:
        column, row = self.tree.places[person_id]
        left, top = self._origin()
        return pygame.Rect(left + round(column * CELL[0]), top + round(row * CELL[1]), *CELL)

    def face_rect(self, person_id: str) -> pygame.Rect:
        """Where somebody's face is on the canvas, in view or out of it."""
        cell = self._cell(person_id)
        return pygame.Rect(cell.centerx - FACE // 2, cell.y, FACE, FACE)

    def pan(self, dx: int, dy: int) -> None:
        """Move the tree under the stage, as far as there is tree to see."""
        width, height = self.content()
        limits = (max(0, width + MARGIN * 2 - STAGE.width), max(0, height + MARGIN * 2 - STAGE.height))
        for axis, distance in enumerate((dx, dy)):
            self.scroll[axis] = min(max(self.scroll[axis] + distance, 0), limits[axis])

    def person_at(self, position: tuple[int, int]) -> str | None:
        """Whoever's face or name is under a place on the canvas."""
        if not STAGE.collidepoint(position):
            return None
        return next((person_id for person_id in self.tree.places if self._cell(person_id).collidepoint(position)), None)

    # ----- input -----

    def click(self, position: tuple[int, int]) -> None:
        if self.close_button.contains(position):
            self.closed = True
            return
        person_id = self.person_at(position)
        if person_id is not None and self.tree.people[person_id].state == HERE:
            # Whoever lives here is somebody to go and look at.
            self.picked, self.closed = person_id, True

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.KEYDOWN:
            steps = {pygame.K_LEFT: (-1, 0), pygame.K_RIGHT: (1, 0), pygame.K_UP: (0, -1), pygame.K_DOWN: (0, 1)}
            if event.key in (pygame.K_ESCAPE, pygame.K_F7):
                self.closed = True
            elif event.key in steps:
                self.pan(steps[event.key][0] * SCROLL_STEP, steps[event.key][1] * SCROLL_STEP)
        elif event.type == pygame.MOUSEWHEEL:
            self.pan(0, -event.y * SCROLL_STEP)
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            self._drag, self._moved = canvas_position(event.pos), False
        elif event.type == pygame.MOUSEMOTION:
            self.pointer = canvas_position(event.pos)
            if self._drag is not None:
                dx, dy = self._drag[0] - self.pointer[0], self._drag[1] - self.pointer[1]
                if self._moved or abs(dx) + abs(dy) >= 4:
                    self._moved = True
                    self.pan(dx, dy)
                    self._drag = self.pointer
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            pressed, self._drag = self._drag, None
            if pressed is not None and not self._moved:
                self.click(canvas_position(event.pos))

    def update(self, dt: float) -> None:
        pass

    # ----- drawing -----

    def render(self) -> None:
        if self.layers is not None:
            self.layers.clear()
        canvas, font = self.canvas, self.font
        canvas.fill(PALETTE["ink"])
        font.draw(canvas, TITLE, (STAGE.x, 8), PALETTE["lamp"], scale=2)
        font.draw(canvas, SUBTITLE, (STAGE.x, 8 + LINE_HEIGHT * 2), PALETTE["bone"])
        self.close_button.draw(canvas, font)
        pygame.draw.rect(canvas, PALETTE["iron"], STAGE.inflate(2, 2), 1)
        if not self.tree.places:
            font.draw(canvas, NOBODY, (STAGE.x + MARGIN, STAGE.y + MARGIN), PALETTE["stone"])
            return
        canvas.set_clip(STAGE)
        for tie in self.tree.ties:
            self._draw_tie(tie.kind, tie.one, tie.other)
        if self.tree.alone and len(self.tree.alone) < len(self.tree.places):
            first = self._cell(self.tree.alone[0])
            font.draw(canvas, ALONE, (first.x + 2, first.y - LINE_HEIGHT - 2), PALETTE["stone"])
        for person_id in self.tree.places:
            self._draw_person(self.tree.people[person_id])
        canvas.set_clip(None)
        self._draw_legend()

    def _draw_tie(self, kind: str, one: str, other: str) -> None:
        """A line between two people for what one is to the other."""
        canvas, color = self.canvas, PALETTE[TIE_COLORS[kind]]
        first, second = self.face_rect(one), self.face_rect(other)
        if kind in (PARENT, ADOPTIVE):
            # Down from the parent, across over the child's row, and down to the child.
            across = second.top - 6
            pygame.draw.lines(
                canvas, color, False, [first.midbottom, (first.centerx, across), (second.centerx, across), second.midtop]
            )
        elif kind == SIBLING:
            # A bracket over the two of them.
            over = min(first.top, second.top) - 4
            pygame.draw.lines(canvas, color, False, [first.midtop, (first.centerx, over), (second.centerx, over), second.midtop])
        else:
            pygame.draw.line(canvas, color, first.center, second.center)
            if kind == SPOUSE:
                # Two lines for two who are married.
                pygame.draw.line(canvas, color, (first.centerx, first.centery + 3), (second.centerx, second.centery + 3))

    def _draw_person(self, person: Person) -> None:
        canvas, font = self.canvas, self.font
        cell, face = self._cell(person.person_id), self.face_rect(person.person_id)
        if not cell.colliderect(STAGE):
            return
        if STAGE.contains(face):
            draw_face(canvas, self.faces, face, person.person_id, "neutral", self.layers)
        else:
            # Half out of the stage, it is the small face that is shown, cut where the stage ends.
            pygame.draw.rect(canvas, PALETTE["iron"], face)
            canvas.blit(pygame.transform.scale(self.faces.face(person.person_id), face.size), face)
        if person.state in (DEAD, ELSEWHERE):
            veil = pygame.Surface(face.size, pygame.SRCALPHA)
            veil.fill(VEIL)
            canvas.blit(veil, face)
        pointed = self.pointer is not None and cell.collidepoint(self.pointer) and person.state == HERE
        if person.person_id == self.focus or pointed:
            pygame.draw.rect(canvas, PALETTE["glow"], face.inflate(4, 4), 1)
        away = person.state in (DEAD, ELSEWHERE)
        lines = [(font.truncate(person.name, CELL[0] - 2), "stone" if away else "paper"), (describe(person), "stone" if away else "dust")]
        y = face.bottom + 2
        for text, color in lines:
            if not text:
                continue
            width = font.width(text)
            # On a plate of its own, so that no line of the tree runs through the words.
            plate = pygame.Rect(cell.centerx - width // 2 - 1, y, width + 2, LINE_HEIGHT - 1)
            canvas.fill(PALETTE["ink"], plate)
            font.draw(canvas, text, (plate.x + 1, y), PALETTE[color])
            y += LINE_HEIGHT - 1

    def _draw_legend(self) -> None:
        canvas, font = self.canvas, self.font
        x, y = STAGE.x, STAGE.bottom + 8
        for kind, word in LEGEND:
            color = PALETTE[TIE_COLORS[kind]]
            pygame.draw.line(canvas, color, (x, y + 5), (x + 14, y + 5))
            if kind == SPOUSE:
                pygame.draw.line(canvas, color, (x, y + 8), (x + 14, y + 8))
            font.draw(canvas, word, (x + 18, y), PALETTE["bone"])
            x += 18 + font.width(word) + 14
        font.draw(canvas, HINT, (STAGE.right - font.width(HINT), y), PALETTE["stone"])
