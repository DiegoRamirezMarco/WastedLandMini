"""One screen to make a doll on: its body, its head, its face and its hands, a tab for each,
with the doll moving beside whichever is up.

Nothing on it has to be read. Everything there is to press is a tile with a picture on it, in
the colour of the kind of thing it does, and says what it is when the mouse rests on it. What is
seldom wanted is behind a cog. The doll is shown large, and is turned by hand with a bar under
it, from one side round to the front and on to the other; four tiles say what it is at.

The work is done by the screens there were (`doll_page`, `face_page`, `hand_page`), each
of which is now a page of this one: it keeps what it knows how to do, and is told where to do
it. This lays them out, shows them, and passes on what is pressed.
"""

import math
import random
from collections.abc import Callable, Hashable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pygame

from graphics.doll import BODY_CANVAS, DOLL_FACINGS, HEAD_CANVAS, DollStore, draw_doll
from graphics.face import OPEN, SHUT, FaceLook, FaceStore
from graphics.figure import FRONT_DRAWN, SIDE_DRAWN
from graphics.font import LINE_HEIGHT, BitmapFont
from graphics.foot import FootStore, Made
from graphics.hand import HandStore
from graphics.hose import Allowance
from graphics.palette import PALETTE
from graphics.screen_layers import TRANSPARENT, ScreenLayers
from graphics.sides import DARKER, OWN
from graphics.studio_icons import studio_tile
from graphics.poses import builtin_poses
from graphics.turn import body_yaw, limbs_moved, turned_pose
from scenes.doll_page import BACK_PAPER, COLOR_DEED, BRUSH_TOOL, BRUSHES, ERASER_TOOL, FILL_TOOL, GUIDE_OVER, GUIDE_UNDER, MEASURE_TOOL, DollPaper
from scenes.face_page import FacePaper
from scenes.hand_page import FEET, HANDS, HandPaper
from scenes.scene import canvas_position
from simulation.residents.manner import OCCASIONS, TALK
from skeleton.character import Character
from skeleton.motion import Life
from skeleton.plan import FACINGS, SkeletonPlan
from skeleton.rig import Skeleton
from ui.paintbox import BOX_TOOL, LINE_TOOL, OVAL_TOOL, POLYGON_TOOL, SHAPE_LABELS, ColorField
from ui.panel import draw_panel
from ui.tutorial_panel import DOLL_FOCUS, draw_hint, draw_lesson, lesson_for

# The tabs, and the icon of each.
BODY_TAB, HEAD_TAB, FACE_TAB, HANDS_TAB = "body", "head", "face", "hands"
TABS = {BODY_TAB: "tab_body", HEAD_TAB: "tab_head", FACE_TAB: "tab_face", HANDS_TAB: "tab_hands"}
TAB_TIPS = {
    BODY_TAB: ("Cuerpo", "El tronco de frente; brazos y piernas de lado."),
    HEAD_TAB: ("Cabeza", "La cabeza sola, sin cara ni pelo."),
    FACE_TAB: ("Cara", "Ojos, boca, pelo... cada pieza aparte, y se colocan."),
    HANDS_TAB: ("Manos", "Dibujadas, o de bola y dedos."),
}

# Where everything is, on the game's own canvas.
LEFT = 8
COLUMN = 180
WORK = pygame.Rect(196, 62, 400, 386)
SHOW = pygame.Rect(604, 37, 192, 325)
TAB_SIZE, TABS_AT = 30, (196, 3)
TOOL_SIZE, SMALL, STEP = 26, 22, 30
STRIP_Y = 37
CHIP = pygame.Rect(LEFT, 40, 174, 9)
SWATCH, SWATCHES_PER_ROW, SWATCHES_Y = (29, 13), 6, 53
FIELD_SIZE = (174, 40)
TOOLS_Y = 210
SLIDER = pygame.Rect(SHOW.x + 22, SHOW.bottom + 12, SHOW.width - 44, 8)
CLIPS_Y = SHOW.bottom + 30
NOTICE_AT = (LEFT, 424)
# Window pixels to one of the skeleton's for the doll shown beside the work, how far above the
# foot of its room it stands, and how fast it goes through what it is at.
SHOW_DETAIL = 18.0
# Milliseconds of bending of limbs to a frame of the doll beside the work, as an allowance
# counts them: one limb. Shown that large a limb is bent finer and takes some ten thousandths
# of a second, and a doll that turns as it walks has a new shape for a limb or two every frame:
# three to a frame, it was shown thirty times a second and no more.
SHOW_BENDING = 8.0
SHOW_FOOT = 60
SHOW_RATE = 1.2
# What it can be shown at, by the icon of each, and what each is called.
CLIPS = {"stand": "idle", "walk": "walk", "punch": "fight", "talk": "talk_calm", "hammer": "hammer"}
CLIP_TIPS = {"stand": "Quieto", "walk": "Andar", "punch": "Pelear", "talk": "Hablar", "hammer": "Trabajar"}
# The clips among those that are somebody's own way of doing something, by what it is they do:
# the rest are called what the occasion is called.
OCCASION_OF = {"talk_calm": TALK}
# The clip that stands for work where nobody is anybody with a job of their own.
WORK_CLIP = "hammer"
# The picture of each view things are put in place in, from the front to the side.
VIEW_ICONS = ("view_front", "view_quarter", "view_side")
# Seconds it takes to turn from one side to the other and back when it turns by itself, and
# how long something said stays on the screen.
SPIN_SECONDS = 8.0
NOTICE_SECONDS = 4.0
# How long the mouse rests on something before it says what it is.
TIP_AFTER = 0.35
TIP_WIDTH = 150
BACK = (26, 23, 23)
PANEL = (38, 34, 34)
PANEL_EDGE = (74, 68, 64)
LIT = PALETTE["glow"]
SHAPE_ICONS = {LINE_TOOL: "line", BOX_TOOL: "box", OVAL_TOOL: "oval", POLYGON_TOOL: "polygon"}
FAR_ICONS = {OWN: "far_own", "same": "far_same", DARKER: "far_darker"}
FAR_HINTS = {
    OWN: "Brazo y pierna de detrás se dibujan aparte.",
    "same": "Brazo y pierna de detrás son copia de los de delante.",
    DARKER: "Copia de los de delante, un poco más oscura.",
}
GUIDE_HINTS = {GUIDE_UNDER: "El maniquí va debajo de tu dibujo.", GUIDE_OVER: "El maniquí va encima.", "off": "Sin maniquí."}


@dataclass
class IconButton:
    """Something to press: where it is, the picture on it, what pressing it means, and what it
    says of itself when the mouse rests on it."""

    rect: pygame.Rect
    icon: str
    intent: Hashable
    name: str
    hint: str = ""
    lit: bool = False
    off: bool = False

    def contains(self, position: tuple[int, int]) -> bool:
        return self.rect.collidepoint(position)


class _Page:
    """A screen that is a page of this one: it has nothing of its own to press but its paper."""

    @property
    def buttons(self) -> list:
        return []

    def hush(self) -> None:
        """Have it look for nothing of what this screen now shows in its place."""
        self.swatches, self.brush_buttons = [], []
        self.field = ColorField(pygame.Rect(-4000, -4000, 14, 2))


class BodyPage(_Page, DollPaper):
    pass


class FacePage(_Page, FacePaper):
    pass


class HandPage(_Page, HandPaper):
    # What the doll beside the work is at, for hands held as each thing done holds them.
    shown_clip = "idle"

    def _clip(self) -> str:
        return self.shown_clip


class Studio:
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
        foot_store: FootStore | None = None,
        world: Any = None,
        on_saved: Callable[[str], None] | None = None,
        on_deed: Callable[[str], None] | None = None,
        can_fit: bool = False,
    ) -> None:
        self.canvas, self.font, self.layers = canvas, font, layers
        # The settlement whose people are drawn here, where there is one: who they are, what
        # they are called, how each of them walks and fights, and what its opening is teaching.
        self.world = world
        self.on_deed = on_deed
        # Whether there is somewhere to try armour on whoever is being drawn, and who is to
        # be taken there, once the way has been pressed.
        self.can_fit = can_fit
        self.requested_fitting: str | None = None
        self.faces, self.hand_store, self.foot_store, self.plan = faces, hand_store, foot_store, plan
        shared = (canvas, font, layers, root, dolls, plan, faces, hand_store)
        self.body, self.face, self.hand = BodyPage(*shared), FacePage(*shared), HandPage(*shared)
        for page in (self.body, self.face, self.hand):
            page.foot_store = foot_store
            page.on_deed = on_deed
            page.hush()
        self.body.on_saved = on_saved
        if world is not None:
            self.body.who = self._who
        self.body.preview_rect, self.body.preview_foot, self.body.measure_detail = SHOW, SHOW_FOOT, SHOW_DETAIL
        self.running = True
        self.tab = BODY_TAB
        # What is in hand, for whichever page is up.
        self.tool, self.size, self.filled = BRUSH_TOOL, BRUSHES[1], False
        self.color = PALETTE["ink"]
        self._brush_color = self.color
        # On the tab of the face: whether pieces are being put in place, and not one of them drawn.
        self.arranging = True
        self.cog = False
        # The doll beside the work: how far round, what it is at, and whether it turns by itself.
        self.yaw, self.clip, self.spinning = 45.0, "walk", False
        # Whether the paper up on the tab of the body is that of its back, and how far round
        # the doll was before it was turned to be seen from behind for that.
        self.back_paper, self._yaw_before = False, 45.0
        self.time = 0.0
        self._poses = builtin_poses()
        # How the doll beside the work feels, and whether it is speaking: to see its face at it.
        self.mood = ""
        self.talking = False
        self._character = Character(plan)
        self._character.life, self._character.at_ease = Life(random.Random(0)), True
        self._seen_with: tuple | None = None
        self._hands_at = 0.0
        self._bending = Allowance(SHOW_BENDING, never_bare=True)
        self.pointer = (-1, -1)
        self._rested = 0.0
        self._picking = self._sliding = False
        self._said: tuple[str, float] = ("", 0.0)
        self._shown: list[IconButton] = []
        # What is behind the cog, while it is open.
        self._cogged: list[IconButton] = []

        colors = list(PALETTE.values())
        self.swatches = [
            (pygame.Rect(LEFT + (index % SWATCHES_PER_ROW) * SWATCH[0], SWATCHES_Y + (index // SWATCHES_PER_ROW) * SWATCH[1], *SWATCH), color)
            for index, color in enumerate(colors)
        ]
        self.field = ColorField(pygame.Rect(LEFT, self.swatches[-1][0].bottom + 4, *FIELD_SIZE))
        y = self.field.rect.bottom + 6
        self.brushes = [(pygame.Rect(LEFT + index * 44, y, 42, 18), size) for index, size in enumerate(BRUSHES)]
        self.body.open(None)
        self._enter(self.tab)

    # --- what whoever has this screen asks of it, as of the screen residents were drawn on ---

    def open(self, resident_id: str | None) -> None:
        """Begin on somebody, from what has been drawn of them so far: on their body."""
        self.running = True
        self.requested_fitting = None
        self.back_paper = False
        self.body.open(resident_id)
        self._enter(BODY_TAB)

    @property
    def closed(self) -> bool:
        return not self.running

    @closed.setter
    def closed(self, value: bool) -> None:
        self.running = not value

    @property
    def buttons(self) -> list[IconButton]:
        """Everything there is to press, as it stands now."""
        return self._buttons()

    @property
    def areas(self) -> dict[str, pygame.Rect]:
        """The papers that are up, by what each is of."""
        return self.page.areas

    @property
    def mannequin_button(self) -> IconButton:
        return next(button for button in self._buttons() if button.intent == ("mannequin",))

    @property
    def brush_buttons(self) -> list[tuple[pygame.Rect, int]]:
        """How thick the brush may be, each with where it is pressed."""
        return self.brushes

    def save(self) -> bool:
        return self.body.save()

    def __getattr__(self, name: str) -> Any:
        # Whatever else is asked of it is asked of the page a body is drawn on: its drawings,
        # its measures, its joints. Never of itself again, before it has such a page.
        if name in ("body", "face", "hand") or name.startswith("__"):
            raise AttributeError(name)
        return getattr(self.body, name)

    def _who(self) -> list[str]:
        """Whoever there is to draw: those who live there, those who keep a stall, and those just born."""
        world = self.world
        found = [*world.residents, *world.merchants.keepers(world), *world.bundles]
        return list(dict.fromkeys(found))

    def _name(self) -> str:
        """What whoever is being drawn is called."""
        who = self.body.resident_id or ""
        world = self.world
        if world is None:
            return who
        if who in world.bundles:
            # Somebody just born: what is drawn is who they will be once grown.
            return f"{world.bundles[who].name}, de mayor"
        resident = world.residents.get(who)
        return resident.name if resident is not None else world.merchants.keepers(world).get(who) or who

    def _own_clip(self, clip: str) -> str:
        """What the doll beside the work is at, in the manner of whoever is being drawn."""
        world = self.world
        resident = world.residents.get(self.body.resident_id or "") if world is not None else None
        occasion = OCCASION_OF.get(clip, clip)
        if resident is not None and clip == WORK_CLIP and resident.job_id in self._poses.jobs:
            # At work, it is the work they have: stirring a pot, keeping a watch.
            return self._poses.working(resident.job_id, False).clip
        if resident is None or occasion not in OCCASIONS:
            return clip
        kind = world.registries.manners.kind_for(occasion)
        manner = world.manner_of(resident, kind.kind_id) if kind is not None else None
        return manner.clip if manner is not None else clip

    def _did(self, deed: str) -> None:
        if self.on_deed is not None:
            self.on_deed(deed)

    def _lesson(self) -> Any:
        """The lesson of the opening of a new settlement that is taught here, while one is."""
        return lesson_for(self.world, focus=DOLL_FOCUS) if self.world is not None else None

    def _hint_rect(self, hint: str | None) -> pygame.Rect | None:
        """Where on the screen what a lesson is about is."""
        shown = {button.intent: button.rect for button in self._shown}

        def about(*intents: tuple) -> pygame.Rect | None:
            rects = [shown[intent] for intent in intents if intent in shown]
            return rects[0].unionall(rects[1:]) if rects else None

        if hint == "palette":
            return self.swatches[0][0].unionall([*(rect for rect, _ in self.swatches), self.field.rect])
        if hint == "canvas":
            return next(iter(self.page.areas.values()), None)
        if hint == "tools":
            return about(*(intent for intent in shown if intent[0] == "tool" and intent[1] != MEASURE_TOOL))
        if hint == "edit":
            return about(("undo",), ("clear",))
        if hint == "save":
            return about(("save",))
        return None

    # --- which page is up, and where it is laid out ---

    @property
    def page(self) -> DollPaper:
        return {FACE_TAB: self.face, HANDS_TAB: self.hand}.get(self.tab, self.body)

    @property
    def drawing(self) -> bool:
        """Whether there is a paper up to draw on."""
        return self.tab in (BODY_TAB, HEAD_TAB) or (self.tab == FACE_TAB and not self.arranging)

    def _enter(self, tab: str) -> None:
        """Put a tab up, over the doll as it now stands."""
        if self.tab == HANDS_TAB and tab != HANDS_TAB:
            self.color = self._brush_color
        if tab != self.tab and tab == HANDS_TAB:
            self._brush_color = self.color
        self.tab, self.cog = tab, False
        body = self.body
        if tab in (BODY_TAB, HEAD_TAB):
            name = BODY_CANVAS if tab == BODY_TAB else HEAD_CANVAS
            width, height = body.template.canvases[name]
            if tab == BODY_TAB and self.back_paper:
                # The paper of the back is as large as the body's, with only the trunk on it.
                name = BACK_PAPER
            zoom = max(1, min(WORK.width // width, WORK.height // height))
            area = pygame.Rect(0, 0, width * zoom, height * zoom)
            area.midtop = WORK.midtop
            if area.height > WORK.height:
                # A paper taller than the work has the room above it too, where on other tabs
                # there is a strip of things to press: it stands on the foot of the work.
                area.midbottom = WORK.midbottom
            body.areas, body.zooms = {name: area}, {name: zoom}
            if name == BACK_PAPER and self.tool == MEASURE_TOOL:
                self.tool = BRUSH_TOOL
            return
        body.areas = {}
        if self.tool == MEASURE_TOOL:
            self.tool = BRUSH_TOOL
        if tab == FACE_TAB:
            self.face.open_for(body.resident_id, body.drawings, body.build, body.depth)
            self.face.hush()
            self.face.paper_room = WORK
            self._lay_out_face()
        else:
            self.hand.open_for(body.resident_id, body.drawings, body.build, body.depth)
            self.hand.room = pygame.Rect(WORK.x, WORK.y, WORK.width, 320)
            self.hand.bar = pygame.Rect(WORK.x + 50, WORK.y + 344, WORK.width - 100, 10)
            self.color = self.hand.chosen_color()

    def _look(self) -> FaceLook:
        """What the face of the doll beside the work is doing: it blinks, it speaks and feels
        as its tiles say, and while an eye shut or a mouth open is being drawn it holds that."""
        rules = self.face.rules
        moves = rules.moves
        speaking = self.talking or OCCASION_OF.get(self.clip) == TALK
        lids, mouth = moves.lids_at(self.time, 0.37), moves.mouth_at(self.time, 0.0) if speaking else 0
        held = rules.kinds.get(self.face.kind) if self.tab == FACE_TAB and not self.arranging else None
        if held is not None and held.when == SHUT:
            lids = moves.steps(SHUT)
        elif held is not None and held.when == OPEN:
            mouth = moves.steps(OPEN)
        return FaceLook(lids, mouth, self.mood)

    def _lay_out_face(self) -> None:
        face = self.face
        if self.arranging:
            zoom = 2
            face.areas, face.zooms, face.stage_zoom = {}, {}, zoom
            face.stage = pygame.Rect(0, 0, face.head.get_width() * zoom, face.head.get_height() * zoom)
            face.stage.midtop = WORK.midtop
        else:
            face._show_paper(face.kind)
            face.stage = pygame.Rect(-4000, -4000, 2, 2)

    def say(self, text: str) -> None:
        self._said = (text, self.time + NOTICE_SECONDS)

    # --- what there is to press ---

    def _row(self, x: int, y: int, size: int, entries: list[tuple], step: int | None = None) -> list[IconButton]:
        """Tiles side by side: each an icon, what pressing it means, its name, and then whatever more is said of it."""
        step = step if step is not None else size + 4
        made = []
        for index, entry in enumerate(entries):
            icon, intent, name, *more = entry
            made.append(IconButton(pygame.Rect(x + index * step, y, size, size), icon, intent, name, *more))
        return made

    def _buttons(self) -> list[IconButton]:
        body, face, hand, tab = self.body, self.face, self.hand, self.tab
        can_draw = self.drawing
        steps = [("prev", ("step", -1), "Anterior"), ("next", ("step", 1), "Siguiente")]
        if self.world is None:
            # Where there is a settlement, whoever is drawn is somebody who is there already.
            steps.append(("new", ("new",), "Nuevo muñeco"))
        found = self._row(118 if self.world is None else 142, 6, SMALL, steps, 24)
        found += [
            IconButton(pygame.Rect(TABS_AT[0] + index * (TAB_SIZE + 4), TABS_AT[1], TAB_SIZE, TAB_SIZE), icon, ("tab", name), *TAB_TIPS[name], lit=name == tab)
            for index, (name, icon) in enumerate(TABS.items())
        ]
        found += self._row(SHOW.right - 56, 5, TOOL_SIZE, [
            ("save_all", ("save",), "Guardar", "Ctrl+S"), ("leave", ("close",), "Salir", "Sin guardar lo que falte."),
        ])
        tools = [
            ("brush", ("tool", BRUSH_TOOL), "Pincel"), ("eraser", ("tool", ERASER_TOOL), "Goma"), ("bucket", ("tool", FILL_TOOL), "Cubo", "Rellena una zona del mismo color."),
            *((SHAPE_ICONS[tool], ("tool", tool), label) for tool, label in SHAPE_LABELS.items() if tool != POLYGON_TOOL),
        ]
        for button in self._row(LEFT, TOOLS_Y, TOOL_SIZE, tools, STEP):
            button.lit, button.off = can_draw and button.intent == ("tool", self.tool), not can_draw
            found.append(button)
        second = self._row(LEFT, TOOLS_Y + STEP, TOOL_SIZE, [
            ("polygon", ("tool", POLYGON_TOOL), "Polígono", "Clic en cada esquina; clic derecho lo cierra."),
            ("filled", ("fill",), "Formas rellenas", "Rellenas o solo el borde."),
            ("undo", ("undo",), "Deshacer", "Ctrl+Z"),
            ("trash", ("clear",), "Borrar todo", "Limpia este papel. Se puede deshacer."),
        ], STEP)
        second[0].lit = can_draw and self.tool == POLYGON_TOOL
        second[1].lit = can_draw and self.filled
        for button in second:
            button.off = not can_draw
        found += second

        y = TOOLS_Y + STEP * 2 + 6
        if tab in (BODY_TAB, HEAD_TAB):
            own = [
                ("mannequin", ("mannequin",), "Maniquí", "Pone la figura lisa para dibujar encima."),
                ("measure", ("tool", MEASURE_TOOL), "Medidas", "Arrastra las articulaciones, y hombros, piernas y cabeza en el muñeco."),
            ]
            if tab == BODY_TAB:
                own.append((FAR_ICONS[body.far_side], ("far",), "Brazo y pierna de detrás", FAR_HINTS[body.far_side]))
                own.append(("back_paper", ("back_paper",), "Espalda", "Dibuja la espalda del tronco, vista desde atrás. Sin dibujar, es lisa."))
            row = self._row(LEFT, y, TOOL_SIZE, own, STEP)
            row[1].lit = self.tool == MEASURE_TOOL
            if tab == BODY_TAB:
                row[2].lit = body.far_side != OWN
                row[3].lit = self.back_paper
                # On the paper of the back there is only the trunk: nothing to measure, no limbs to copy.
                row[1].off = row[2].off = self.back_paper
                if self.can_fit:
                    found.append(IconButton(
                        pygame.Rect(LEFT + 4 * STEP, y, TOOL_SIZE, TOOL_SIZE), "fitting", ("fitting",), "Probador",
                        "Prueba piezas de armadura sobre este cuerpo.",
                    ))
            found += row
        elif tab == FACE_TAB:
            row = self._row(LEFT, y, TOOL_SIZE, [
                ("spark", ("mannequin",), "Cara de ejemplo", "Rellena las piezas que estén sin dibujar."),
                ("symmetry", ("symmetric",), "Simetría", "Al mover un ojo, el otro va a su sitio."),
            ], STEP)
            row[1].lit = face.symmetric
            found += row
        else:
            row = self._row(LEFT, y, TOOL_SIZE, [
                ("hand_made", ("made",), "Manos de bola y dedos", "En vez de las dibujadas: se abren y se cierran."),
                ("minus", ("size", -1), "Más pequeñas"), ("plus", ("size", 1), "Más grandes"),
                ("finger_less", ("fingers", -1), "Menos dedos"), ("finger_more", ("fingers", 1), "Más dedos"),
            ], STEP)
            row[0].lit = hand.hands.choice.made
            found += row
            if hand.feet is not None:
                feet = self._row(LEFT, y + STEP, TOOL_SIZE, [
                    ("foot_made", ("feet_made",), "Pies hechos", "En vez de los dibujados: una bota del color que se elija."),
                    ("minus", ("feet_size", -1), "Más pequeños"), ("plus", ("feet_size", 1), "Más grandes"),
                ], STEP)
                feet[0].lit = hand.feet.choice.made
                found += feet
            which = "los pies" if hand.making == FEET else "las manos"
            line = self._row(LEFT, y + STEP * 2, TOOL_SIZE, [
                ("line_color", ("line_color",), "Color del contorno", f"El color que se elija es el de la línea de {which}, y no el de dentro."),
                ("thinner", ("line", -1), "Contorno más fino", f"El de {which}. Del todo fino, no hay contorno."),
                ("thicker", ("line", 1), "Contorno más grueso", f"El de {which}."),
            ], STEP)
            line[0].lit = hand.of_line
            low, high = hand.chosen_made().rules.lines
            line[1].off, line[2].off = hand.chosen_made().bold <= low, hand.chosen_made().bold >= high
            found += line
        if tab != HANDS_TAB:
            found.append(IconButton(pygame.Rect(LEFT + 5 * STEP, y, TOOL_SIZE, TOOL_SIZE), "gear", ("cog",), "Más opciones", lit=self.cog))
            self._cogged = self._behind_the_cog(y + STEP + 6) if self.cog else []
            found += self._cogged

        if tab == FACE_TAB:
            kinds = [("place", ("place",), "Colocar", "Arrastra cada pieza a su sitio. Rueda: ancho. Clic derecho: ocultar.")]
            for kind in face.rules.kinds.values():
                said = "Se dibuja uno; el otro es su espejo." if kind.paired else ""
                if kind.stands_for:
                    # Another drawing of a piece: nobody has to make it.
                    said = f"Si no lo dibujas, el juego lo saca de: {face.rules.kinds[kind.stands_for].name}."
                kinds.append((kind.kind_id, ("kind", kind.kind_id), kind.name, said))
            moves = face.rules.moves
            feels = moves.mood_names.get(self.mood, "Normal")
            kinds += [
                ("mood", ("mood",), f"Ánimo: {feels}", "Cómo se siente el muñeco de al lado: su cara lo dice."),
                ("talk", ("talk",), "Hablar", "El muñeco de al lado mueve la boca, para ver cómo le queda."),
            ]
            strip = self._row(WORK.x, STRIP_Y, SMALL, kinds, 25)
            strip[0].lit = self.arranging
            for button in strip[1:]:
                button.lit = not self.arranging and button.intent == ("kind", face.kind)
                if button.intent == ("mood",):
                    button.lit = bool(self.mood)
                elif button.intent == ("talk",):
                    button.lit = self.talking
            found += strip
        elif tab == HANDS_TAB:
            poses = [(f"hand_{pose_id}", ("pose", pose_id), pose.name) for pose_id, pose in hand.rules.poses.items()]
            strip = self._row(WORK.x, STRIP_Y, SMALL, [
                *poses,
                ("by_gesture", ("pose", None), "Según el gesto", "Cada animación lleva su mano."),
                ("open_shut", ("cycle",), "Abrir y cerrar"),
            ], 25)
            for button in strip:
                button.lit = hand.cycling if button.intent == ("cycle",) else (not hand.cycling and hand.manual is None and button.intent == ("pose", hand.pose_id))
            more = self._row(strip[-1].rect.right + 12, STRIP_Y, SMALL, [
                ("holding", ("held",), "Con algo cogido"), ("thinner", ("thick", -1), "Más fino"), ("thicker", ("thick", 1), "Más grueso"),
            ], 25)
            more[0].lit = hand.holding
            more[1].off = more[2].off = not hand.holding
            # A hand at either end of the bar that opens and shuts them: open at one, a fist at the other.
            bar = hand.bar
            ends = [
                IconButton(pygame.Rect(bar.x - 26, bar.centery - 9, 18, 18), "hand_open", ("pose", "open"), "Abierta"),
                IconButton(pygame.Rect(bar.right + 8, bar.centery - 9, 18, 18), "hand_fist", ("pose", "fist"), "Cerrada"),
            ]
            found += strip + more + ends

        if self.placing:
            # Whatever is put in place is put in place in one view: a tile for each, and one
            # that puts back what was moved in the view in hand.
            rules, seen = self.faces.rules, self._view()
            entries = [
                (VIEW_ICONS[min(index, len(VIEW_ICONS) - 1)], ("view", view), rules.view_names[view], "Lo que coloques aquí vale para esta vista.")
                for index, view in enumerate(rules.views)
            ]
            if tab != FACE_TAB:
                entries.append(("reset", ("limbs_auto",), "Recolocar sola", "En esta vista, la extremidad elegida vuelve a su sitio. Sin elegir: todas."))
            clips = self._row(SHOW.x, CLIPS_Y, TOOL_SIZE, entries, STEP)
            for button in clips:
                button.lit = button.intent == ("view", seen)
        else:
            clips = self._row(SHOW.x, CLIPS_Y, TOOL_SIZE, [(icon, ("clip", icon), CLIP_TIPS[icon]) for icon in CLIPS], STEP)
            for button in clips:
                button.lit = button.intent == ("clip", self.clip_icon)
        spin = IconButton(pygame.Rect(SHOW.right - TOOL_SIZE, CLIPS_Y, TOOL_SIZE, TOOL_SIZE), "turn", ("spin",), "Girar solo", lit=self.spinning)
        return found + clips + [spin]

    def _behind_the_cog(self, y: int) -> list[IconButton]:
        """What is seldom wanted, for the tab that is up."""
        page = self.page
        entries = [("guide", ("guide",), "Maniquí de calco", GUIDE_HINTS.get(page.guide, ""))]
        if self.tab in (BODY_TAB, HEAD_TAB):
            entries += [
                ("thinner", ("depth", -1), "Tronco más plano", f"Fondo: {round(self.body.depth * 100)}% del ancho."),
                ("thicker", ("depth", 1), "Tronco más grueso", f"Fondo: {round(self.body.depth * 100)}% del ancho."),
                ("reset", ("measures",), "Medidas de partida", "Devuelve todas las medidas a como empiezan."),
            ]
            if self.tab == BODY_TAB:
                front = self.body.trunk_drawn == FRONT_DRAWN
                entries.append((
                    "tab_body", ("trunk",), "Tronco dibujado de frente",
                    "Encendido: gira envuelto. Apagado: está dibujado de lado, y gira por regla." if front
                    else "Apagado: está dibujado de lado, y gira por regla. Enciéndelo si ya lo has dibujado de frente.",
                ))
        else:
            entries.append(("reset", ("auto",), "Recolocar sola", "En esta vista, la pieza elegida vuelve a donde le toca. Sin elegir: todas."))
        row = self._row(LEFT + 4, y, TOOL_SIZE, entries, STEP)
        row[0].lit = page.guide != "off"
        for button in row:
            if button.intent == ("trunk",):
                button.lit = self.body.trunk_drawn == FRONT_DRAWN
        return row

    @property
    def clip_icon(self) -> str:
        return next(icon for icon, clip in CLIPS.items() if clip == self.clip)

    def _apply(self, intent: tuple) -> None:
        kind = intent[0]
        if kind == "tab":
            self._enter(intent[1])
        elif kind == "tool" and intent[1] == MEASURE_TOOL:
            self.tool = BRUSH_TOOL if self.tool == MEASURE_TOOL else MEASURE_TOOL
            if self.tool == MEASURE_TOOL:
                # Measured, it is seen from its side to begin with, as its papers are drawn.
                self.yaw, self.spinning = self.faces.rules.side, False
        elif kind == "view":
            self.yaw, self.spinning = self.faces.rules.views[intent[1]], False
        elif kind == "limbs_auto":
            self.body.limbs_by_rule()
        elif kind == "tool":
            self.tool = intent[1]
            self.page._draft = None
        elif kind == "fitting":
            self.requested_fitting = self.body.resident_id
        elif kind == "fill":
            self.filled = not self.filled
        elif kind == "measure":
            self.tool = BRUSH_TOOL if self.tool == MEASURE_TOOL else MEASURE_TOOL
        elif kind == "cog":
            self.cog = not self.cog
        elif kind == "trunk":
            body = self.body
            body.trunk_drawn = SIDE_DRAWN if body.trunk_drawn == FRONT_DRAWN else FRONT_DRAWN
            body._cut()
            self.say("Tronco de frente: gira envuelto" if body.trunk_drawn == FRONT_DRAWN else "Tronco de lado: gira por regla")
        elif kind == "back_paper":
            # The back is drawn with the doll beside it seen from behind, and left as it was after.
            self.back_paper = not self.back_paper
            if self.back_paper:
                self._yaw_before, self.yaw, self.spinning = self.yaw, self.faces.rules.side * 2.0, False
            else:
                self.yaw = self._yaw_before
            self._enter(BODY_TAB)
        elif kind == "clip":
            self.clip = CLIPS[intent[1]]
        elif kind == "spin":
            self.spinning = not self.spinning
        elif kind == "close":
            self.running = False
        elif kind == "save":
            self.say("Guardado" if self.body.save() else "No se pudo guardar")
        elif kind in ("step", "new"):
            self.body._apply(intent)
            self._enter(self.tab)
        elif kind == "place":
            self.arranging = True
            self._lay_out_face()
        elif kind == "kind":
            self.arranging = False
            self.face.kind = intent[1]
            self._lay_out_face()
        elif kind == "mood":
            # Each feeling in turn, and then none again.
            moods = ["", *self.face.rules.moves.moods]
            self.mood = moods[(moods.index(self.mood) + 1) % len(moods)] if self.mood in moods else ""
            self.say(f"Ánimo: {self.face.rules.moves.mood_names.get(self.mood, 'Normal')}")
        elif kind == "talk":
            self.talking = not self.talking
        else:
            # Everything else is the page's own to do, as it always did.
            if self.tab == HANDS_TAB and kind in ("made", "size", "fingers", "feet_made", "feet_size"):
                # Whatever is done to the hands or to the feet, the colour in hand is theirs from then on.
                self._making(FEET if kind.startswith("feet") else HANDS)
            self._hand_over()
            self.page._apply(intent)
            if kind == "line_color":
                # The colour in hand is now that of the line, or of what is inside it again.
                self.color = self.hand.chosen_color()
            if kind == "far":
                self.say(FAR_HINTS[self.body.far_side])
            elif kind == "depth":
                self.say(f"Fondo del tronco: {round(self.body.depth * 100)}%")

    def _making(self, which: str) -> None:
        """Have the colour in hand be that of the hands, or of the feet."""
        hand = self.hand
        hand.making = which if hand.feet is not None else HANDS
        self.color = hand.chosen_color()

    def _hand_over(self) -> None:
        """Have the page that is up hold what is in hand here."""
        page = self.page
        page.tool, page.size, page.filled, page.color = self.tool, self.size, self.filled, self.color
        if self.tab == FACE_TAB:
            self.face.view = self._view()
        elif self.tab == HANDS_TAB:
            self.hand.shown_clip = self.clip
            self.hand._take_color()

    @property
    def placing(self) -> bool:
        """Whether things are being put in place by hand, in one view or another: the limbs
        of the doll beside the work, or the pieces of a face."""
        measuring = self.tool == MEASURE_TOOL and self.tab in (BODY_TAB, HEAD_TAB)
        return measuring or (self.tab == FACE_TAB and self.arranging)

    def _view(self) -> str:
        """The view of a face that pieces are put in place in: the one nearest how far round the doll is."""
        views = self.faces.rules.views
        side = self.faces.rules.side
        # From behind nothing is put in place: the view is the one as far round from the front.
        seen = min(abs(self.yaw), 2.0 * side - abs(self.yaw))
        return min(views, key=lambda view: abs(views[view] - seen))

    # --- the mouse and the keys ---

    def press(self, position: tuple[int, int]) -> None:
        for button in self._buttons():
            if button.contains(position):
                if not button.off:
                    self._apply(button.intent)
                return
        for rect, color in self.swatches:
            if rect.collidepoint(position):
                self._take(color)
                return
        if self.field.contains(position):
            self._picking = True
            self._take(self.field.color_at(position))
            return
        for rect, size in self.brushes:
            if rect.collidepoint(position):
                self.size = size
                return
        if SLIDER.inflate(16, 18).collidepoint(position):
            self._sliding = True
            self._slide(position)
            return
        if self.tab == HANDS_TAB and self.hand.room.collidepoint(position):
            # A press on the hands or on the feet says which of them the colour is for.
            self._making(FEET if position[1] >= self.hand.feet_from() else HANDS)
            return
        self._hand_over()
        self.page.press(position)

    def _take(self, color: tuple[int, int, int]) -> None:
        self.color = color
        if self.tool == ERASER_TOOL:
            self.tool = BRUSH_TOOL
        self._hand_over()
        self._did(COLOR_DEED)

    def _slide(self, position: tuple[int, int]) -> None:
        """Turn the doll to where the mouse is along the bar: seen from behind at either end, the
        front in the middle, and each side half way between."""
        share = max(0.0, min(1.0, (position[0] - SLIDER.x) / SLIDER.width))
        side = self.faces.rules.side
        self.yaw, self.spinning = (share * 2.0 - 1.0) * side * 2.0, False

    def drag(self, position: tuple[int, int]) -> None:
        if self._sliding:
            self._slide(position)
        elif self._picking:
            self._take(self.field.color_at(position))
        else:
            self._hand_over()
            self.page.drag(position)

    def release(self) -> None:
        if self._sliding or self._picking:
            self._sliding = self._picking = False
            return
        self.page.release()

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.MOUSEMOTION:
            position = canvas_position(event.pos)
            if position != self.pointer:
                self.pointer, self._rested = position, 0.0
            if event.buttons[0]:
                self.drag(position)
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            self.pointer = canvas_position(event.pos)
            self.press(self.pointer)
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            self.release()
        elif event.type == pygame.KEYDOWN and event.key == pygame.K_s and event.mod & pygame.KMOD_CTRL:
            self._apply(("save",))
        elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE and self.page._draft is None:
            if self.cog:
                self.cog = False
            elif self.world is not None:
                # In the game Escape leaves a screen, as it does every other: without saving.
                self.running = False
        else:
            self._hand_over()
            self.page.handle_event(event)

    def update(self, dt: float) -> None:
        self.time += dt
        self._rested += dt
        # Measured, the doll stands in the view nearest how far round the bar has it.
        self.body.measure_view = self._view()
        for page in (self.body, self.face, self.hand):
            page.update(dt)
        self._character.update(dt)
        if self.spinning:
            # All the way round, and round again.
            around = self.faces.rules.side * 4.0
            self.yaw = (self.time / SPIN_SECONDS * around + around / 2.0) % around - around / 2.0

    # --- what is shown ---

    def render(self) -> None:
        self.layers.clear()
        canvas, font = self.canvas, self.font
        canvas.fill(TRANSPARENT)
        self._hand_over()
        self._shown = self._buttons()
        self.layers.under(self._show_chrome)
        name = font.truncate(self._name(), 60 if self.world is not None else 52)
        font.draw(canvas, name, (LEFT, 8), PALETTE["glow"], scale=2)

        pygame.draw.rect(canvas, self.color, CHIP, border_radius=3)
        pygame.draw.rect(canvas, PALETTE["bone"], CHIP, 1, border_radius=3)
        for rect, color in self.swatches:
            pygame.draw.rect(canvas, color, rect.inflate(-2, -2), border_radius=2)
            if tuple(color) == tuple(self.color):
                pygame.draw.rect(canvas, PALETTE["paper"], rect, 1, border_radius=2)
        self.field.draw(canvas)
        for rect, size in self.brushes:
            lit = size == self.size and self.drawing
            draw_panel(canvas, rect, fill="shadow", border="glow" if lit else "iron")
            pygame.draw.circle(canvas, PALETTE["bone"] if self.drawing else PALETTE["stone"], rect.center, max(1, size // 2))

        self._render_work()
        canvas.fill(TRANSPARENT, SHOW)
        self.layers.under(self._show_doll)
        if self.tool == MEASURE_TOOL and self.tab in (BODY_TAB, HEAD_TAB):
            self.body._render_handles()
        self._render_slider()
        if self.page.notice:
            # Whatever the page has to say is said here, and for a while: not for good.
            self.say(self.page.notice)
            self.page.notice = ""
        said = self._said[0] if self.time < self._said[1] else ""
        for index, line in enumerate(font.wrap(said, COLUMN)[:2]):
            font.draw(canvas, line, (NOTICE_AT[0], NOTICE_AT[1] + index * LINE_HEIGHT), PALETTE["lamp"])
        lesson = self._lesson()
        if lesson is not None and not self.cog:
            # While the opening of a new settlement teaches drawing, the lesson goes under the tools.
            top = TOOLS_Y + STEP * (5 if self.tab == HANDS_TAB else 3) + 12
            draw_lesson(canvas, font, pygame.Rect(LEFT, top, COLUMN - 4, NOTICE_AT[1] - 4 - top), self.world, lesson)
            draw_hint(canvas, self._hint_rect(lesson.hint), self.time)
        self._render_tip()

    def _render_work(self) -> None:
        canvas, tab = self.canvas, self.tab
        if tab == HANDS_TAB:
            self._render_hands()
            return
        page = self.page
        for name, area in page.areas.items():
            pygame.draw.rect(canvas, PALETTE["stone"], area.inflate(2, 2), 1)
            canvas.fill(TRANSPARENT, area)
            self.layers.under(page._show_drawing(name, area))
        if tab == FACE_TAB and self.arranging:
            face = self.face
            pygame.draw.rect(canvas, PALETTE["stone"], face.stage.inflate(2, 2), 1)
            canvas.fill(TRANSPARENT, face.stage)
            self.layers.under(face._show_stage)
            held = face._held[0] if face._held else None
            for piece, _, _, box in face._laid():
                if piece in (face.chosen, held):
                    said = face.face.said(piece, face.view)
                    pygame.draw.rect(canvas, PALETTE["glow" if said else "paper"], face.stage_frame(box), 1)
            self.font.draw(canvas, face.rules.view_names[face.view], (face.stage.x + 4, face.stage.y + 3), PALETTE["dust"])

    def _render_hands(self) -> None:
        canvas, hand = self.canvas, self.hand
        pygame.draw.rect(canvas, PALETTE["stone"], hand.room.inflate(2, 2), 1)
        canvas.fill(TRANSPARENT, hand.room)
        self.layers.under(hand._show_hands)
        if hand.feet is not None:
            # A frame round whichever the colour in hand is the colour of.
            room, split = hand.room, hand.feet_from()
            frame = pygame.Rect(room.x + 3, split + 2, room.width - 6, room.bottom - split - 5) if hand.making == FEET else pygame.Rect(room.x + 3, room.y + 3, room.width - 6, split - room.y - 5)
            pygame.draw.rect(canvas, PALETTE["glow"], frame, 1, border_radius=6)
        bar = hand.bar
        pygame.draw.rect(canvas, PALETTE["shadow"], bar, border_radius=4)
        pygame.draw.rect(canvas, PALETTE["iron"], bar, 1, border_radius=4)
        pose = hand.picked() or hand.rules.pose_for(self.clip)
        knob = pygame.Rect(0, 0, 9, bar.height + 8)
        knob.center = (bar.x + round(pose.curl * bar.width), bar.centery)
        pygame.draw.rect(canvas, PALETTE["lamp" if hand.manual is not None else "bone"], knob, border_radius=3)

    def _render_slider(self) -> None:
        """The bar the doll is turned with: a notch at each side, at three quarters either way, and at the front."""
        canvas = self.canvas
        pygame.draw.rect(canvas, PALETTE["shadow"], SLIDER, border_radius=4)
        pygame.draw.rect(canvas, PALETTE["iron"], SLIDER, 1, border_radius=4)
        around = self.faces.rules.side * 2.0
        turns = set(self.faces.rules.views.values())
        turns |= {around - turn for turn in turns}
        for yaw in sorted({sign * turn for turn in turns for sign in (-1, 1)}):
            x = SLIDER.x + round((yaw / around + 1.0) / 2.0 * SLIDER.width)
            pygame.draw.line(canvas, PALETTE["stone"], (x, SLIDER.bottom + 1), (x, SLIDER.bottom + 3))
        knob = pygame.Rect(0, 0, 9, SLIDER.height + 8)
        knob.center = (SLIDER.x + round((self.yaw / around + 1.0) / 2.0 * SLIDER.width), SLIDER.centery)
        pygame.draw.rect(canvas, PALETTE["glow" if self._sliding else "bone"], knob, border_radius=3)

    def _hovered(self) -> IconButton | None:
        return next((button for button in self._shown if button.contains(self.pointer)), None)

    def _render_tip(self) -> None:
        """What the thing under the mouse is, once the mouse has rested on it."""
        button = self._hovered()
        if button is None or self._rested < TIP_AFTER:
            return
        font, canvas = self.font, self.canvas
        lines = font.wrap(button.hint, TIP_WIDTH) if button.hint else []
        wide = max([font.width(button.name), *(font.width(line) for line in lines)]) + 10
        box = pygame.Rect(0, 0, wide, (1 + len(lines)) * LINE_HEIGHT + 7)
        box.midtop = (button.rect.centerx, button.rect.bottom + 4)
        if box.bottom > canvas.get_height() - 2:
            box.bottom = button.rect.top - 4
        box.clamp_ip(canvas.get_rect().inflate(-4, -4))
        pygame.draw.rect(canvas, PALETTE["ink"], box, border_radius=4)
        pygame.draw.rect(canvas, PALETTE["glow"], box, 1, border_radius=4)
        font.draw(canvas, button.name, (box.x + 5, box.y + 4), PALETTE["glow"])
        for index, line in enumerate(lines):
            font.draw(canvas, line, (box.x + 5, box.y + 4 + (index + 1) * LINE_HEIGHT), PALETTE["bone"])

    def _show_chrome(self, screen: pygame.Surface) -> None:
        """What is behind everything, and every tile, as fine as the window."""
        scale = self.layers.scale
        screen.fill(BACK)
        for room in (pygame.Rect(2, 34, COLUMN + 10, 414), SHOW.inflate(8, 8).union(pygame.Rect(SHOW.x - 4, CLIPS_Y - 4, SHOW.width + 8, TOOL_SIZE + 8))):
            place = self.layers.on_screen(room)
            pygame.draw.rect(screen, PANEL, place, border_radius=16)
            pygame.draw.rect(screen, PANEL_EDGE, place, 2, border_radius=16)
        if self.cog and self._cogged and self.tab != HANDS_TAB:
            behind = self._cogged
            place = self.layers.on_screen(behind[0].rect.unionall([button.rect for button in behind]).inflate(8, 8))
            pygame.draw.rect(screen, BACK, place, border_radius=14)
            pygame.draw.rect(screen, PANEL_EDGE, place, 2, border_radius=14)
        for button in self._shown:
            place = self.layers.on_screen(button.rect)
            screen.blit(studio_tile(button.icon, place.width, button.lit, button.off), place)
            if button.lit:
                pygame.draw.rect(screen, LIT, place.inflate(6, 6), 3, border_radius=round(place.width * 0.3))

    def _show_doll(self, screen: pygame.Surface) -> None:
        """The doll at what it has been told to be at, as far round as the bar has it."""
        place = self.layers.on_screen(SHOW)
        body = self.body
        if self.tool == MEASURE_TOOL and self.tab in (BODY_TAB, HEAD_TAB):
            # Measured, it stands as it was drawn, to be taken hold of: the page knows how.
            body._show_preview(screen)
            return
        pygame.draw.rect(screen, PALETTE["earth"], place, border_radius=14)
        rules = self.faces.rules
        face, hands = self.faces.get(body.resident_id), self.hand_store.get(body.resident_id)
        # Whatever it was shown as is no use once its face or its hands are not what they were.
        feet = self.foot_store.get(body.resident_id) if self.foot_store is not None and body.resident_id else None
        with_what = (body.resident_id, face.revision, hands.choice.made, feet is not None and feet.choice.made)
        if with_what != self._seen_with:
            self._seen_with = with_what
            body._turned = {}
            body._cut()
        step = rules.stepped(self.yaw, behind=True)
        head_yaw = rules.yaw_of(step)
        # The body goes as far round as the head, whatever it is at: what it does is seen
        # less across the screen the nearer the front it is (`graphics/turn.py`).
        round_by = body_yaw(rules.body, head_yaw, standing=True)
        doll = body._seen(head_yaw, round_by, self._look())
        if doll is None:
            return
        facing = DOLL_FACINGS["right" if self.yaw >= 0 else "left"]
        plan, character = body.doll_plan, self._character
        character.plan, character.lively = plan, True
        character.stand(0.0, 0.0, facing, self._own_clip(self.clip), self.time * SHOW_RATE)
        _, _, mirrored, swapped = FACINGS[facing]
        moved = limbs_moved(body.limb_keys, rules.views, round_by, rules.side) if body.limb_keys else None
        pose = turned_pose(rules.body, body._apart, character.local_pose(), round_by, rules.side, mirrored, swapped, moved)
        skeleton = Skeleton(plan, facing)
        skeleton.set_pose(pose)
        made = body.made_hands() if not body._showing_example else None
        if made is not None:
            seconds, self._hands_at = self.time - self._hands_at, self.time
            picked = self.hand.picked() if self.tab == HANDS_TAB else None
            made.settle(picked or made.rules.pose_for(self.clip), seconds)
            made.turned(round_by)
        made_feet = body.made_feet() if not body._showing_example else None
        if made_feet is not None:
            made_feet.turned(round_by, rules.side)
        made = Made(made, made_feet) if made is not None or made_feet is not None else None
        before = screen.get_clip()
        screen.set_clip(place)
        self._bending.new_frame()
        draw_doll(
            screen, doll, plan, skeleton, (place.centerx, place.bottom - SHOW_FOOT), SHOW_DETAIL, hands=made,
            allowance=self._bending,
        )
        screen.set_clip(before)
