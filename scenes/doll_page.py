"""Where a resident's body and head are drawn: two canvases over a guide, and the result moving beside them."""

import json
import math
import random
from collections.abc import Callable
from pathlib import Path

import pygame

from graphics.cartoon import LINE
from graphics.doll import (
    BODY_CANVAS,
    DOLL_FACINGS,
    HEAD_CANVAS,
    Doll,
    DollBuild,
    DollStore,
    JointHandle,
    build_path,
    doll_path,
    doll_plan,
    draw_doll,
    unsided,
)
from graphics.doll_guide import NOTE_INK, build_guide, label_spots, name_ink, piece_spots, piece_zone, piece_zones, reference
from graphics.face import FaceStore, faced
from graphics.figure import FRONT_DRAWN, SIDE_DRAWN, TRUNK_KEY
from graphics.face_examples import plain_head
from graphics.foot import Feet, FootStore, Made
from graphics.joined import colour_at, half_width_at
from graphics.hand import Hands, HandStore
from graphics.font import LINE_HEIGHT, BitmapFont
from graphics.mannequin import figures, tones_of
from graphics.palette import PALETTE
from graphics.screen_layers import TRANSPARENT, ScreenLayers
from graphics.sides import DARKER, OWN, SHADE, WAYS, far_darker, limbs, match_far_side
from graphics.turn import body_yaw, limbs_apart, turned_pose
from graphics.volume import back_of, fronted, turned_body
from scenes.scene import canvas_position
from skeleton.character import Character
from skeleton.motion import Life
from skeleton.plan import FACINGS, SkeletonPlan
from skeleton.rig import Skeleton
from ui.button import Button
from ui.paintbox import FILLED_LABEL, HOLLOW_LABEL, POLYGON_NOTICE, POLYGON_TOOL, SHAPE_LABELS, ColorField, ShapeDraft

BODY_AT = (196, 58)
HEAD_AT = (604, 58)
PREVIEW = pygame.Rect(604, 272, 192, 170)
TOOLS_LEFT = 8
SWATCH = (28, 12)
SWATCHES_PER_ROW = 6
# Under the ready colours, the field any other is picked from, and beside the word the one in hand.
FIELD_SIZE = (168, 44)
CHOSEN = pygame.Rect(40, 44, 22, 10)
BRUSHES = (2, 5, 10, 18)
BRUSH_TOOL, ERASER_TOOL, FILL_TOOL = "brush", "eraser", "fill"
# Not a way of painting: with it in hand the joints of the guide are what the mouse takes hold of.
MEASURE_TOOL = "measure"
TOOL_LABELS = {BRUSH_TOOL: "Pincel", ERASER_TOOL: "Goma", FILL_TOOL: "Cubo", MEASURE_TOOL: "Medidas"}
# Canvas pixels within which a joint is taken hold of, and how large it is drawn while it can be.
GRIP = 8
HANDLE_RADIUS = 4
# What the places where a limb is joined on are called beside the figure, by the bone that joins it.
ATTACH_NAMES = {"clavicle": "hombros", "pelvis": "piernas"}
HEAD_NAME = "cabeza"
# Where the guide is shown: under the drawing, over it, or not at all.
GUIDE_UNDER, GUIDE_OVER, GUIDE_OFF = "under", "over", "off"
GUIDE_LABELS = {GUIDE_UNDER: "Calco: debajo", GUIDE_OVER: "Calco: encima", GUIDE_OFF: "Calco: quitado"}
GUIDE_ALPHA = {GUIDE_UNDER: 170, GUIDE_OVER: 90}
# What each part is called on the guide, by the bone it goes with whichever side it is on, and
# what the two sides of the body are called.
PART_NAMES = {
    "neck": "cuello", "spine": "tronco", "hips": "cintura", "briefs": "calzón", "upper_arm": "brazo", "forearm": "antebrazo",
    "hand": "mano", "thigh": "muslo", "shin": "pierna", "foot": "pie",
}
SIDE_NAMES = {"_left": "DETRÁS", "_right": "DELANTE"}
# What the limbs of the near side are called on the guide when those of the far side are taken
# from them, and so are not on the paper.
BOTH_SIDES = "LOS DOS"
# The paper the back of a trunk is drawn on, by whoever would rather it were not plain: as
# large as the paper of the body, with only the trunk on it. And what is written at its head.
BACK_PAPER = "back"
BACK_NOTE = "la espalda, vista desde atrás"
SIDE_NOTICE = "Tronco de lado: gira por regla. Dibújalo de frente (Maniquí)"
COLOR_DEED, STROKE_DEED, FILL_DEED, UNDO_DEED = "color", "stroke", "fill", "undo"
MEASURE_DEED, RESIDENT_DRAWN_DEED = "measure", "save_resident"
# A name goes up the left edge of its part, beside the figure, if the zone leaves it this much room there.
NAME_MARGIN = 4
FACING_NOTE = "mira a la derecha >>"
NECK_NOTE = "aquí gira sobre el cuello"
UNDO_STEPS = 30
PAPER = PALETTE["bone"]
# Window pixels to one of the skeleton's in the preview, and how fast it goes through its clips.
PREVIEW_DETAIL = 9.0
# How far above the bottom of the preview, in window pixels, the ground it stands on is.
PREVIEW_FOOT = 40
PREVIEW_RATE = 1.2
# What the preview goes through. Walking and fighting are shown the way of whoever is being drawn.
PREVIEW_CLIPS = ("walk", "idle", "work", "fight")
PREVIEW_SECONDS = 4.0
SAVED_TEXT = "Guardado"
# What the button for the far side's limbs says, by how they are come by, and what is said when it is pressed.
FAR_LABELS = {OWN: "Detrás: se dibuja aparte", "same": "Detrás: igual que delante", DARKER: "Detrás: igual, más oscuro"}
FAR_NOTICES = {
    OWN: "Brazo y pierna de DETRÁS se dibujan aparte otra vez",
    "same": "Brazo y pierna de DETRÁS se copian de los de DELANTE. Ctrl+Z lo deshace",
    DARKER: "Brazo y pierna de DETRÁS se copian de los de DELANTE, más oscuros. Ctrl+Z lo deshace",
}
# Under what name it is kept with a doll's measures.
FAR_KEY = "far_side"
# And under what name how deep its trunk is, from chest to back, and how much a press changes it.
DEPTH_KEY = "depth"
DEPTH_STEP = 0.05
# The ways the doll beside the paper is shown, one after another, and what each is called.
PREVIEW_VIEWS = ("side", "quarter", "front")
# What the first doll of a folder with none is called.
FIRST_DOLL = "prueba"
FACE_LABEL = "Cara"
# The colour of the plain figure a drawing can be started from, and its line as a share of the unit.
MANNEQUIN_COLOR = (214, 170, 130)
MANNEQUIN_EDGE = 0.34
# How far round the head of the doll shown beside the paper is turned: its side, as the body is drawn.
PREVIEW_YAW = 90.0
NOTES_TEXT = (
    "Cada zona de color es una pieza: lo que pintes dentro se mueve con ella. Se dobla por las líneas de puntos.",
    "El tronco y la cadera se dibujan de frente: el juego los gira. Brazos y piernas, de lado.",
    "El maniquí de debajo es para calcar. Naranja: delante. Azul: detrás. Ctrl+Z deshace.",
)

# How far round the end of a limb its colour is looked for, in pixels of the drawing, for a
# hand or a foot that is made to be given.
MATCH_REACH = 7

class DollPaper:
    """Draw a doll: its body, and its head with nothing on it. What goes on the head is
    drawn and put in place on another screen (`scenes/face_page.py`).

    The canvases are as large on the window as two of its pixels to one of the drawing's, which is
    one pixel of the game's own canvas: nothing has to be scaled by a fraction.
    """

    def __init__(
        self,
        canvas: pygame.Surface,
        font: BitmapFont,
        layers: ScreenLayers,
        root: Path,
        dolls: DollStore,
        plan: SkeletonPlan,
        faces: FaceStore | None = None,
        hand_store: HandStore | None = None,
        on_saved: Callable[[str], None] | None = None,
    ) -> None:
        self.canvas = canvas
        self.font = font
        self.layers = layers
        self.root = root
        self.dolls = dolls
        self.plan = plan
        # What each doll has on its head, where there is somewhere to keep it.
        self.faces = faces
        # What has been said of each doll's hands: the ones drawn on it, or ones that are made.
        self.hand_store = hand_store
        # And of its feet: whoever has such a store gives it once this is made.
        self.foot_store: FootStore | None = None
        self.on_saved = on_saved
        # Who there is to draw, where it is not whoever has a doll kept, and who is told of
        # what is done here that the opening of a new settlement may be waiting for.
        self.who: Callable[[], list[str]] | None = None
        self.on_deed: Callable[[str], None] | None = None
        # How the trunk on the paper was drawn. One drawn before trunks were drawn from the
        # front was drawn from its side, and is made to turn by rule until it is drawn anew.
        self.trunk_drawn = FRONT_DRAWN
        self._fronted: Doll | None = None
        # When the doll beside the paper was last shown, for hands that take time to open and shut.
        self._hands_at = 0.0
        # How many times as large as it is drawn each paper is shown, for those that are not shown as they are.
        self.zooms: dict[str, int] = {}
        # Where the doll is shown moving, how far above the foot of that it stands, and how large
        # it is while it is measured: for whoever lays this screen out otherwise.
        self.preview_rect = pygame.Rect(604, 272, 192, 170)
        self.preview_foot = 40
        self.measure_detail = 12.0
        # How many times the doll has been cut again: whoever shows it elsewhere goes by this.
        self.changes = 0
        # The template every doll starts from, and this one's own: its measures, the template with
        # its joints where they put them, and the body plan that stands as they say.
        self.base_template = dolls.template
        self.build = self.base_template.starting()
        self.template = self.base_template.built(self.build)
        self.doll_plan = doll_plan(plan, self.template, self.build)
        # What of the measures the mouse has hold of, and how they stood when it took hold.
        self._grab: tuple | None = None
        self._grab_zoom = 1
        self.closed = False
        self.resident_id: str | None = None
        self.drawings: dict[str, pygame.Surface] = {}
        self.areas = {
            BODY_CANVAS: pygame.Rect(BODY_AT, self.template.canvases[BODY_CANVAS]),
            HEAD_CANVAS: pygame.Rect(HEAD_AT, self.template.canvases[HEAD_CANVAS]),
        }
        # How the far side comes by its limbs: said here so that the first guide can be made.
        self.far_side = OWN
        self.guides: dict[str, pygame.Surface] = {}
        self._undrawn: dict[str, pygame.Surface | None] = {}
        self._lay_guides()
        # The figure of the guide, cut as a drawing would be: what moves in the preview until something is drawn.
        self._example = Doll(self.template, {name: self._reference(name) for name in self.template.canvases}, self.doll_plan)
        self._showing_example = True
        self.colors = list(PALETTE.values())
        self.color = PALETTE["ink"]
        self.size = BRUSHES[1]
        self.tool = BRUSH_TOOL
        self.guide = GUIDE_UNDER
        self.notice = ""
        self.time = 0.0
        self._undo: list[tuple[str, pygame.Surface]] = []
        # The canvas being drawn on and where the stroke last was, while the button is held.
        self._stroke: tuple[str, tuple[int, int]] | None = None
        self._preview: Doll | None = None
        # That doll with its head turned each way it has been shown, by how far round.
        self._turned: dict[float, Doll] = {}
        # The body the doll is shown moving on beside the paper: on springs, as on the map.
        self._body = Character(plan)
        self._body.life, self._body.at_ease = Life(random.Random(0)), True
        # A shape being laid down, whether shapes are filled, and whether the mouse is held on the field of colour.
        self._draft: ShapeDraft | None = None
        self.filled = False
        self._picking = False

        self.swatches = [
            (pygame.Rect(TOOLS_LEFT + (index % SWATCHES_PER_ROW) * SWATCH[0], 58 + (index // SWATCHES_PER_ROW) * SWATCH[1], *SWATCH), color)
            for index, color in enumerate(self.colors)
        ]
        y = self.swatches[-1][0].bottom + 4
        self.field = ColorField(pygame.Rect(TOOLS_LEFT, y, *FIELD_SIZE))
        y = self.field.rect.bottom + 6
        self.brush_buttons = [(pygame.Rect(TOOLS_LEFT + index * 42, y, 40, 22), size) for index, size in enumerate(BRUSHES)]
        y += 26
        self.tool_buttons = self._row(y, [(TOOL_LABELS[tool], ("tool", tool)) for tool in TOOL_LABELS])
        y += 16
        self.shape_buttons = self._row(y, [(label, ("tool", tool)) for tool, label in SHAPE_LABELS.items()])
        y += 16
        self.edit_buttons = self._row(y, [("Deshacer", ("undo",)), ("Limpiar", ("clear",))])
        self.fill_button = Button.at(font, self.edit_buttons[-1].rect.right + 3, y, HOLLOW_LABEL, ("fill",))
        y += 16
        self.guide_button = Button.at(font, TOOLS_LEFT, y, GUIDE_LABELS[GUIDE_UNDER], ("guide",))
        self.guide_button.rect.width = 110
        y += 16
        self.mannequin_button = Button.at(font, TOOLS_LEFT, y, "Maniquí de partida", ("mannequin",))
        y += 16
        self.measures_button = Button.at(font, TOOLS_LEFT, y, "Medidas de partida", ("measures",))
        self.top_buttons = self._row(6, [("<", ("step", -1)), (">", ("step", 1)), ("Guardar", ("save",)), ("Volver", ("close",))], left=HEAD_AT[0])
        if faces is not None:
            # The way to where a face is drawn and put on the head, before the rest of that row.
            face = Button.at(font, 0, 6, FACE_LABEL, ("face",))
            face.rect.right = HEAD_AT[0] - 8
            new = Button.at(font, 0, 6, "Nuevo", ("new",))
            new.rect.right = face.rect.left - 3
            self.top_buttons += [face, new]
        if hand_store is not None:
            # And the way to where its hands are chosen.
            hands = Button.at(font, 0, 6, "Manos", ("hands",))
            hands.rect.right = min(button.rect.left for button in self.top_buttons) - 3
            self.top_buttons.append(hands)
        self.requested_hands: str | None = None
        # Whoever a face is to be given, once the way there has been pressed.
        self.requested_face: str | None = None
        # How the far side comes by its limbs: drawn by hand, or taken from the near side's.
        self.far_side = OWN
        self.far_button = Button.at(font, 0, 43, max(FAR_LABELS.values(), key=font.width), ("far",))
        self.far_button.rect.right = HEAD_AT[0] - 8
        self.far_button.label = FAR_LABELS[OWN]
        # How deep the trunk of whoever is being drawn is, from chest to back, against how wide.
        self.depth = faces.rules.body.depth if faces is not None else 1.0
        deeper = Button.at(font, 0, 43, "Fondo +", ("depth", 1))
        deeper.rect.right = self.far_button.rect.left - 6
        flatter = Button.at(font, 0, 43, "Fondo -", ("depth", -1))
        flatter.rect.right = deeper.rect.left - 3
        self.depth_buttons = [flatter, deeper] if faces is not None else []
        # How far to its side each limb of the doll beside the paper is, seen from the front.
        self._apart: dict[str, float] = {}
        # Whatever else a screen made of this one has to press. This one has those buttons.
        self.extra_buttons: list[Button] = [self.far_button, *self.depth_buttons]

    def _row(self, y: int, entries: list[tuple[str, tuple]], left: int = TOOLS_LEFT) -> list[Button]:
        buttons, x = [], left
        for label, intent in entries:
            button = Button.at(self.font, x, y, label, intent)
            buttons.append(button)
            x = button.rect.right + 3
        return buttons

    @property
    def buttons(self) -> list[Button]:
        return [
            *self.top_buttons, *self.tool_buttons, *self.shape_buttons, *self.edit_buttons, self.fill_button,
            self.guide_button, self.mannequin_button, self.measures_button, *self.extra_buttons,
        ]

    def open(self, resident_id: str | None) -> None:
        """Start drawing a resident, from what has been drawn of them so far."""
        self.resident_id = resident_id if resident_id is not None else self.roster()[0]
        self.closed = False
        self.requested_face = None
        self.requested_hands = None
        self.notice = ""
        self._undo = []
        self._stroke = None
        kept = self.dolls.drawings(self.resident_id) if self.resident_id is not None else {}
        self.drawings = {}
        for name, size in self.template.canvases.items():
            surface = pygame.Surface(size, pygame.SRCALPHA)
            if name in kept:
                picture = kept[name]
                surface.blit(picture if picture.get_size() == size else pygame.transform.smoothscale(picture, size), (0, 0))
            self.drawings[name] = surface
        # And the back of its trunk, if one was ever drawn.
        back = pygame.Surface(self.template.canvases[BODY_CANVAS], pygame.SRCALPHA)
        path = self.root / doll_path(self.resident_id, BACK_PAPER) if self.resident_id is not None else None
        if path is not None and path.is_file():
            try:
                picture = pygame.image.load(str(path)).convert_alpha()
                # Drawn on the paper as it was laid out before, it is put where its parts go now.
                picture = self.base_template.adopted(BODY_CANVAS, picture, self.dolls.build(self.resident_id))
                back.blit(picture if picture.get_size() == back.get_size() else pygame.transform.smoothscale(picture, back.get_size()), (0, 0))
            except pygame.error:
                pass
        self.drawings[BACK_PAPER] = back
        # A body kept with no word of how its trunk was drawn was drawn before there was any.
        said = self.dolls.extras(self.resident_id).get(TRUNK_KEY) if self.resident_id is not None else None
        self.trunk_drawn = FRONT_DRAWN if said == FRONT_DRAWN or BODY_CANVAS not in kept else SIDE_DRAWN
        if self.trunk_drawn == SIDE_DRAWN:
            self.notice = SIDE_NOTICE
        self._grab = None
        self.far_side = self._kept_far_side()
        self.far_button.label = FAR_LABELS[self.far_side]
        self.depth = self._kept_depth()
        start = self.base_template.starting()
        self.set_build(self.dolls.build(self.resident_id) if self.resident_id is not None else start)

    def set_build(self, build: DollBuild, settled: bool = True) -> bool:
        """Give the doll other measures, if it can have them. Returns whether it could.

        The guide, the figure under it and the body plan all follow. While a joint is still being
        dragged the drawing is not cut again, which is the slow part: `settled` says it has been let go.
        """
        if not self.base_template.takes(build):
            return False
        self.build = build
        self.template = self.base_template.built(build)
        self.doll_plan = doll_plan(self.plan, self.template, build)
        self._lay_guides()
        if settled:
            self._example = Doll(self.template, {name: self._reference(name) for name in self.template.canvases}, self.doll_plan)
            self._cut()
        return True

    def _kept_far_side(self) -> str:
        """How the far side of whoever is being drawn comes by its limbs, as it was kept with their measures."""
        path = self.root / build_path(self.resident_id) if self.resident_id is not None else None
        if path is None or not path.is_file():
            return OWN
        try:
            kept = json.loads(path.read_text(encoding="utf-8")).get(FAR_KEY)
        except (OSError, ValueError, AttributeError):
            return OWN
        return kept if kept in WAYS else OWN

    def _kept_depth(self) -> float:
        """How deep the trunk of whoever is being drawn is, as it was kept with their measures."""
        if self.faces is None:
            return 1.0
        turn = self.faces.rules.body
        path = self.root / build_path(self.resident_id) if self.resident_id is not None else None
        try:
            kept = json.loads(path.read_text(encoding="utf-8")).get(DEPTH_KEY) if path is not None and path.is_file() else None
        except (OSError, ValueError, AttributeError):
            kept = None
        if not isinstance(kept, (int, float)):
            return turn.depth
        return max(turn.depths[0], min(turn.depths[1], float(kept)))

    def _match_sides(self) -> None:
        """Have the limbs of the far side be those drawn for the near side, where that is how they are come by."""
        if self.far_side == OWN or BODY_CANVAS not in self.drawings:
            return
        # Where a body is turned every way, the far side is put in the shade when it is shown
        # (`_seen`), by as much as the body is seen from its side: the drawing has both alike.
        baked = SHADE if self.far_side == DARKER and self.faces is None else 0.0
        match_far_side(self.template, BODY_CANVAS, self.drawings[BODY_CANVAS], baked)

    def roster(self) -> list[str]:
        """Whoever there is to draw: every doll kept, and whoever is being drawn now. Never nobody."""
        folder = self.root / "dolls"
        if self.who is not None:
            return self.who() or [FIRST_DOLL]
        kept = sorted(each.name for each in folder.iterdir() if each.is_dir()) if folder.is_dir() else []
        if self.resident_id is not None and self.resident_id not in kept:
            kept.append(self.resident_id)
        return kept or [FIRST_DOLL]

    def new(self) -> None:
        """Begin somebody nobody has drawn, under a name nobody has."""
        taken = set(self.roster())
        self.open(next(name for name in (f"{FIRST_DOLL}_{number}" for number in range(1, 1000)) if name not in taken))

    def joint_handles(self, canvas: str) -> list[JointHandle]:
        """The joints of one canvas that can be taken hold of, where the doll's measures have them."""
        return [handle for handle in self.base_template.handles(self.template) if handle.canvas == canvas]

    @property
    def _per_unit(self) -> float:
        """Canvas pixels to one of the skeleton's in the preview, as it is shown while measuring."""
        return self.measure_detail / self.layers.scale

    def figure_handles(self) -> list[tuple[str, str, tuple[float, float]]]:
        """Where on the figure a limb or the head can be taken hold of to be joined on elsewhere.

        Each is a kind, `attach` for the bone that joins a limb to the trunk or `point` for a head
        on its neck, what the measures call it, and where it is on the game's canvas.
        """
        pose = self.doll_plan.pose(DOLL_FACINGS["right"])
        per_unit = self._per_unit

        def spot(joints: list[str]) -> tuple[float, float]:
            x = sum(pose[joint][0] for joint in joints) / len(joints)
            y = sum(pose[joint][1] for joint in joints) / len(joints)
            return (self.preview_rect.centerx + (x + 0.5) * per_unit, self.preview_rect.bottom - self.preview_foot / self.layers.scale + (y + 0.5) * per_unit)

        found: dict[tuple[str, str], list[str]] = {}
        for bone in self.plan.bones.values():
            spec = self.base_template.parts.get(bone.name)
            if spec is None:
                # A bone nobody draws: it is what holds a limb to the trunk, one each side.
                found.setdefault(("attach", unsided(bone.name)), []).append(bone.end)
            elif spec.whole:
                found.setdefault(("point", f"{unsided(bone.name)}.start"), []).append(bone.end)
        return [(kind, name, spot(joints)) for (kind, name), joints in found.items()]

    def _take_hold(self, position: tuple[int, int]) -> bool:
        """Take hold of the joint or the limb under the mouse, if there is one near enough."""
        on = self._canvas_under(position)
        if on is not None:
            name, at = on
            near = [handle for handle in self.joint_handles(name) if math.dist(handle.point, at) <= GRIP]
            if not near:
                return False
            handle = min(near, key=lambda each: math.dist(each.point, at))
            before = self.build.points.get(handle.key, (0.0, 0.0)) if handle.axis is None else self.build.joints.get(handle.key, 0.0)
            self._grab = ("joint", handle.key, handle.axis, before, position)
            # A paper shown larger is measured in its own pixels, however far the mouse goes.
            self._grab_zoom = self.zooms.get(name, 1)
            return True
        if self.preview_rect.collidepoint(position):
            near = [entry for entry in self.figure_handles() if math.dist(entry[2], position) <= GRIP + 2]
            if not near:
                return False
            kind, name, _ = min(near, key=lambda entry: math.dist(entry[2], position))
            before = (self.build.attach if kind == "attach" else self.build.points).get(name, (0.0, 0.0))
            self._grab = (kind, name, None, before, position)
            return True
        return False

    def _pull(self, position: tuple[int, int]) -> None:
        """Move whatever is held to where the mouse now is, as far as the doll can have it there."""
        kind, name, axis, before, pressed = self._grab
        dx, dy = position[0] - pressed[0], position[1] - pressed[1]
        if kind == "joint":
            dx, dy = dx / self._grab_zoom, dy / self._grab_zoom
        build = self.build.copy()
        if kind == "joint" and axis is not None:
            build.joints[name] = round(before + (dx * axis[0] + dy * axis[1]) / self.template.unit, 2)
        elif kind == "joint":
            build.points[name] = (round(before[0] + dx / self.template.unit, 2), round(before[1] + dy / self.template.unit, 2))
        elif kind == "attach":
            build.attach[name] = (round(before[0] + dx / self._per_unit, 2), round(before[1] + dy / self._per_unit, 2))
        else:
            # A head moved on the figure is its neck moved the other way on the head's own paper.
            build.points[name] = (round(before[0] - dx / self._per_unit, 2), round(before[1] - dy / self._per_unit, 2))
        self.set_build(build, settled=False)

    def _named_guide(self, paper: str) -> pygame.Surface:
        """The guide of a paper with every part named on it, and the side of the body each limb is on.

        Names are written in the colour of their piece, straight on the guide.
        """
        canvas = BODY_CANVAS if paper == BACK_PAPER else paper
        zones = piece_zones(self.template, canvas)
        figure = self._reference(canvas)
        copied = self._copied(paper)
        if copied is not None:
            # Whatever is not drawn is not on the guide: no zone for it, no figure in it, no name.
            gone = pygame.mask.from_surface(copied)
            zones = {piece: zone for piece, zone in zones.items() if zone.overlap_area(gone, (0, 0)) * 2 < zone.count()}
            figure = figure.copy()
            figure.blit(copied, (0, 0), special_flags=pygame.BLEND_RGBA_SUB)
        guide = build_guide(self.template, canvas, zones, figure)
        if copied is not None:
            # Nor the rings at its joints, which are those of the paper whatever its zones.
            guide.blit(copied, (0, 0), special_flags=pygame.BLEND_RGBA_SUB)
        width, height = guide.get_size()
        font = self.font
        written: list[pygame.Rect] = []

        def write(
            text: str, position: tuple[int, int], ink: tuple[int, int, int], upright: bool = False, yielding: bool = False
        ) -> bool:
            """Write a name on the guide. One that is `yielding` is left out where another already is."""
            label = font.render(text, ink)
            if upright:
                label = pygame.transform.rotate(label, 90)
            spot = label.get_rect(topleft=position).clamp(guide.get_rect())
            if yielding and spot.inflate(4, 2).collidelist(written) >= 0:
                return False
            written.append(spot)
            guide.blit(label, spot)
            return True

        spots = label_spots(self.template, canvas)
        boxes = piece_spots(self.template, canvas, zones)
        for piece, box in boxes.items():
            ink = name_ink(piece[0])
            for bone in piece:
                spot, spec = spots[bone], self.template.parts[bone]
                name = PART_NAMES.get(unsided(bone), unsided(bone))
                if abs(spec.end[0] - spec.start[0]) > abs(spec.end[1] - spec.start[1]):
                    # A part that lies flat, as a foot does, is named along the foot of its zone.
                    write(name, (spot.left + 4, spot.bottom - LINE_HEIGHT), ink)
                elif spec.reach - spec.radius < LINE_HEIGHT + NAME_MARGIN:
                    # Too thin a zone to be named in beside the figure, as a neck's: the name goes beside it.
                    write(name, (spot.right + 4, spot.centery - LINE_HEIGHT // 2), ink)
                elif spot.height >= font.width(name) + 2:
                    # Up its left edge, where the figure leaves room.
                    write(name, (spot.left + 3, spot.centery - font.width(name) // 2), ink, upright=True)
                elif spot.height >= LINE_HEIGHT + 2:
                    # Too short for its name upright, as a waist is: along its left edge, if nothing is there.
                    write(name, (spot.left + 3, spot.centery - LINE_HEIGHT // 2), ink, yielding=True)
            side = next((suffix for suffix in SIDE_NAMES if piece[0].endswith(suffix)), "")
            if not side:
                continue
            # Which side of the body a limb is on goes over it, or, where another piece is in the
            # way, beside its far end and away from the middle of the paper.
            title = BOTH_SIDES if copied is not None and paper != BACK_PAPER else SIDE_NAMES[side]
            wide = font.width(title)
            over = pygame.Rect(box.centerx - wide // 2, box.top - LINE_HEIGHT - 2, wide, LINE_HEIGHT)
            if over.top >= 0 and over.collidelist([other for each, other in boxes.items() if each != piece]) < 0:
                write(title, over.topleft, ink)
            elif box.centerx < width / 2:
                write(title, (box.left - wide - 5, box.bottom - LINE_HEIGHT - 2), ink)
            else:
                write(title, (box.right + 5, box.bottom - LINE_HEIGHT - 2), ink)
        for spec in self.template.parts.values():
            if spec.canvas == canvas and spec.whole:
                write(NECK_NOTE, (round(spec.start[0]) - font.width(NECK_NOTE) // 2, round(spec.start[1]) + 7), NOTE_INK)
        # Which way it faces goes at the head of the paper, or else at its foot or in a corner:
        # wherever no piece and no name is in the way.
        wide = font.width(FACING_NOTE)
        left, middle, right = 4, (width - wide) // 2, width - wide - 4
        top, bottom = 4, height - LINE_HEIGHT - 2
        taken = list(boxes.values())
        # A head that a face is put on by hand has no side to it, and is told to face nowhere.
        sided = canvas != HEAD_CANVAS or self.faces is None
        note = BACK_NOTE if paper == BACK_PAPER else FACING_NOTE
        wide = font.width(note)
        middle, right = (width - wide) // 2, width - wide - 4
        for place in ((middle, top), (middle, bottom), (left, top), (right, top), (left, bottom), (right, bottom)):
            if not sided:
                break
            if pygame.Rect(place, (wide, LINE_HEIGHT)).collidelist(taken) < 0 and write(note, place, NOTE_INK, yielding=True):
                break
        return guide

    def _copied(self, canvas: str) -> pygame.Surface | None:
        """The part of a paper that is not drawn on, solid where it is: the zones of the limbs
        of the far side, where those are taken from the near side. None for a paper that is
        all drawn on.

        The limbs are still in the drawing there, as they are kept and cut. They are only not
        shown on the paper: whatever is painted over them is gone at the next stroke, and a
        zone to draw in that takes no drawing is a puzzle.
        """
        if canvas == BACK_PAPER:
            # On the paper of the back there is the trunk, and nothing else is drawn.
            turn = self.faces.rules.body.trunk if self.faces is not None else ()
            zone = pygame.Mask(self.template.canvases[BODY_CANVAS], fill=True)
            for piece, its in piece_zones(self.template, BODY_CANVAS).items():
                if all(bone in turn for bone in piece):
                    zone.erase(its, (0, 0))
            return zone.to_surface(setcolor=(255, 255, 255, 255), unsetcolor=(0, 0, 0, 0))
        if self.far_side == OWN or canvas != BODY_CANVAS:
            return None
        zone = pygame.Mask(self.template.canvases[canvas])
        for _, far in limbs(self.template, canvas):
            zone.draw(piece_zone(self.template, far), (0, 0))
        return zone.to_surface(setcolor=(255, 255, 255, 255), unsetcolor=(0, 0, 0, 0)) if zone.count() else None

    def _lay_guides(self) -> None:
        """Make the guide of every paper again, and what of each is not drawn on."""
        papers = (*self.template.canvases, BACK_PAPER)
        self.guides = {name: self._named_guide(name) for name in papers}
        self._undrawn = {name: self._copied(name) for name in papers}

    def back_drawn(self) -> pygame.Surface | None:
        """The back of the trunk as somebody has drawn it, or None if nobody has: then it is plain."""
        back = self.drawings.get(BACK_PAPER)
        return back if back is not None and pygame.mask.from_surface(back).count() else None

    def _reference(self, canvas: str) -> pygame.Surface:
        """The figure of the guide on one paper: with its trunk seen from the front, where that
        is how a trunk is to be drawn."""
        figure = reference(self.template, canvas)
        if self.faces is None or canvas != BODY_CANVAS:
            return figure
        turn = self.faces.rules.body
        return fronted(self.template, figure, turn.trunk, turn.depth)

    def _seen(self, yaw: float, round_by: float | None = None) -> Doll | None:
        """The doll beside the paper with its head `yaw` degrees round and its body `round_by`:
        as it was drawn, with no word of how far round its body is. The figure of the guide has no face."""
        doll = self._preview
        if doll is None or self.faces is None:
            return doll
        rules = self.faces.rules
        # One drawn from its side is its drawing as it is, seen from its side: and from
        # anywhere else its trunk is made into one seen from the front, by rule.
        by_rule = self.trunk_drawn == SIDE_DRAWN and not self._showing_example
        as_drawn = by_rule and (round_by is None or abs(round_by - rules.side) < 1e-6)
        if by_rule and not as_drawn:
            if self._fronted is None:
                sheets = dict(doll.sheets)
                sheets[BODY_CANVAS] = fronted(self.template, sheets[BODY_CANVAS], rules.body.trunk, self.depth)
                self._fronted = Doll(self.template, sheets, self.doll_plan, doll.without)
                self._apart = limbs_apart(rules.body, self._fronted)
            doll = self._fronted
        key = (yaw, round_by)
        if key not in self._turned:
            shown = doll
            if not self._showing_example and HEAD_CANVAS in self.drawings:
                face = self.faces.get(self.resident_id) if self.resident_id is not None else None
                shown = faced(shown, face, self.to_show()[HEAD_CANVAS], yaw)
            if round_by is not None and not as_drawn:
                shown = turned_body(shown, rules.body, round_by, self.depth, rules.side, None if by_rule else self.back_drawn())
            if self.far_side == DARKER and not self._showing_example:
                seen_from_side = 1.0 if round_by is None else abs(math.sin(math.radians(round_by * 90.0 / self.faces.rules.side)))
                shown = far_darker(shown, SHADE * round(seen_from_side * 4) / 4)
            self._turned[key] = shown
        return self._turned[key]

    def _cut(self) -> None:
        """Cut the drawings as they stand into a doll, to be seen moving in the preview.

        With nothing drawn yet it is the figure of the guide that moves, to show what the parts add up to.
        """
        self.changes += 1
        self._match_sides()
        # A back by itself is no doll: it is its body or its head being drawn that makes one.
        self._showing_example = not any(
            pygame.mask.from_surface(self.drawings[name]).count() for name in self.template.canvases if name in self.drawings
        )
        self._turned = {}
        self._fronted = None
        if self._showing_example:
            self._preview = self._example
        else:
            # Whatever its head has been given goes on it when it is shown, turned as it is shown (`_seen`).
            self._preview = Doll(self.template, self.to_show(), self.doll_plan, self.left_out())
            self.match_made(self._preview)
        self._apart = limbs_apart(self.faces.rules.body, self._preview) if self.faces is not None else {}

    def to_show(self) -> dict[str, pygame.Surface]:
        """The drawings the doll is cut from to be shown moving: a paper nobody has drawn on yet
        is the plain figure meanwhile, so that a body is never shown without its head."""
        papers = {name: self.drawings[name] for name in self.template.canvases if name in self.drawings}
        blank = [name for name, drawing in papers.items() if not pygame.mask.from_surface(drawing).count()]
        if not blank or len(blank) == len(papers):
            return papers
        plain = self.plain_figures()
        return {name: plain[name] if name in blank else drawing for name, drawing in papers.items()}

    def left_out(self) -> tuple[str, ...]:
        """The parts the doll is cut without: its hands and its feet, where those are made and not drawn."""
        made = self.made()
        return made.bones if made is not None else ()

    def match_made(self, doll: Doll) -> None:
        """Tell the hands and the feet of whoever is being drawn about the limb each is joined
        to: what colour it is where it ends, which is theirs until one is picked for them, and
        how wide it is there, which is how wide they begin. And the feet, how far above the
        ground the ankle of this body is when it stands."""
        if self.resident_id is None:
            return
        for store in (self.hand_store, self.foot_store):
            if store is None:
                continue
            made = store.get(self.resident_id)
            part = doll.parts.get(made.rules.matches)
            made.natural = colour_at(part.image, part.end, MATCH_REACH) if part is not None else None
            wide = half_width_at(part.image, part.start, part.end) / doll.unit if part is not None else 0.0
            made.joins = wide if wide > 0 else None
        if self.foot_store is not None:
            feet = self.foot_store.get(self.resident_id)
            rest = self.doll_plan.pose(DOLL_FACINGS["right"])
            ankle = rest.get(feet.rules.matches_joint)
            feet.stands = -ankle[1] if ankle is not None and ankle[1] < 0 else None

    def made_feet(self) -> Feet | None:
        """The feet of whoever is being drawn, if they are made and not the ones drawn on them."""
        if self.foot_store is None or self.resident_id is None:
            return None
        feet = self.foot_store.get(self.resident_id)
        return feet if feet.choice.made else None

    def made(self) -> Made | None:
        """Whatever of whoever is being drawn is made and not drawn, to be laid on the doll."""
        kinds = [kind for kind in (self.made_hands(), self.made_feet()) if kind is not None]
        return Made(*kinds) if kinds else None

    def made_hands(self) -> Hands | None:
        """The hands of whoever is being drawn, if they are made and not the ones drawn on them."""
        if self.hand_store is None or self.resident_id is None:
            return None
        hands = self.hand_store.get(self.resident_id)
        return hands if hands.choice.made else None

    def _remember(self, name: str) -> None:
        self._undo.append((name, self.drawings[name].copy()))
        del self._undo[:-UNDO_STEPS]

    def undo(self) -> None:
        if self._undo:
            name, surface = self._undo.pop()
            self.drawings[name] = surface
            self._cut()
            self._did(UNDO_DEED)

    def clear(self) -> None:
        # Only the papers that are up: whoever shows one at a time wipes one at a time.
        for name in self.drawings:
            if name in self.areas:
                self._remember(name)
                self.drawings[name].fill(TRANSPARENT)
                if name == BODY_CANVAS:
                    # Whatever is drawn on it next is drawn over the guide, which is seen from the front.
                    self.trunk_drawn = FRONT_DRAWN
        self._cut()

    def mannequin(self) -> None:
        """Fill every zone with the plain figure they have been shown as until now, to draw over or change."""
        for name, figure in self.plain_figures().items():
            if name in self.areas:
                self._remember(name)
                self.drawings[name] = figure
                if name == BODY_CANVAS:
                    # The plain figure has its trunk seen from the front: so has this body now.
                    self.trunk_drawn = FRONT_DRAWN
        if BACK_PAPER in self.areas and self._preview is not None and self.faces is not None:
            # On the paper of the back it is the back as it is when nobody draws it.
            plain = back_of(self._preview, self.faces.rules.body)
            if plain is not None:
                self._remember(BACK_PAPER)
                self.drawings[BACK_PAPER] = plain[1]
        self._cut()

    def plain_figures(self) -> dict[str, pygame.Surface]:
        """The plain figure on each paper, as the doll's measures have it. Where faces are put on
        by hand its head is an egg with no side to it, for a face that turns."""
        line = max(2, round(self.template.unit * MANNEQUIN_EDGE))
        plain = figures(self.template, tones_of(MANNEQUIN_COLOR, LINE), line)
        if self.faces is not None:
            plain[HEAD_CANVAS] = plain_head(self.template, MANNEQUIN_COLOR, line)
            # And its trunk is seen from the front, as a trunk is to be drawn.
            turn = self.faces.rules.body
            plain[BODY_CANVAS] = fronted(self.template, plain[BODY_CANVAS], turn.trunk, turn.depth)
        return plain

    def save(self) -> bool:
        """Write both drawings where the game looks for them. Returns whether it worked."""
        if self.resident_id is None:
            return False
        try:
            # What is kept is what is shown beside the paper: a paper nobody has drawn on yet,
            # while another has been, is the plain figure. Nobody walks the map with no head.
            shown = {**self.drawings, **self.to_show()}
            for name, surface in shown.items():
                path = self.root / doll_path(self.resident_id, name)
                path.parent.mkdir(parents=True, exist_ok=True)
                pygame.image.save(surface, str(path))
            # Their measures go with their drawings: one is cut by the other.
            measures = self.root / build_path(self.resident_id)
            kept = {**self.build.to_data(), FAR_KEY: self.far_side, DEPTH_KEY: round(self.depth, 3), TRUNK_KEY: self.trunk_drawn}
            measures.write_text(json.dumps(kept, indent=2) + "\n", encoding="utf-8")
        except (OSError, pygame.error):
            self.notice = "No se pudo guardar"
            return False
        # Whatever of theirs nobody has looked at yet is kept as it stands: read, it can be.
        for store in (self.faces, self.hand_store, self.foot_store):
            if store is not None:
                store.get(self.resident_id)
        if self.faces is not None and not self.faces.save(self.resident_id):
            self.notice = "No se pudo guardar la cara"
            return False
        if self.hand_store is not None and not self.hand_store.save(self.resident_id):
            self.notice = "No se pudieron guardar las manos"
            return False
        if self.foot_store is not None and not self.foot_store.save(self.resident_id):
            self.notice = "No se pudieron guardar los pies"
            return False
        self.dolls.forget(self.resident_id)
        if self.on_saved is not None:
            self.on_saved(self.resident_id)
        self.notice = SAVED_TEXT
        self._did(RESIDENT_DRAWN_DEED)
        return True

    def step(self, by: int) -> None:
        """Go on to the next resident, or back to the one before."""
        residents = self.roster()
        if self.resident_id in residents:
            self.open(residents[(residents.index(self.resident_id) + by) % len(residents)])

    def _pick(self, position: tuple[int, int]) -> None:
        """Take the colour under the mouse off the field: any colour, not only the ready ones."""
        self.color = self.field.color_at(position)
        if self.tool == ERASER_TOOL:
            self.tool = BRUSH_TOOL

    def _shape_press(self, name: str, at: tuple[int, int]) -> None:
        """Begin a shape on a drawing, or put down the next corner of the polygon being made there."""
        draft = self._draft
        if draft is not None and draft.tool == POLYGON_TOOL and draft.where == name:
            if draft.corner(at):
                self._lay_down()
            return
        self._draft = ShapeDraft(self.tool, name, at)
        if self.tool == POLYGON_TOOL:
            self.notice = POLYGON_NOTICE

    def _lay_down(self) -> None:
        """Put the shape in hand on its drawing for good. A polygon of fewer than three corners is nothing."""
        draft, self._draft = self._draft, None
        if draft is None or (draft.tool == POLYGON_TOOL and len(draft.fixed) < 3):
            return
        self._remember(draft.where)
        draft.paint(self.drawings[draft.where], self.color, self.size, self.filled)
        self.notice = ""
        self._cut()
        self._did(STROKE_DEED)

    def _apply(self, intent: tuple) -> None:
        if intent[0] == "tool":
            self.tool = intent[1]
            # Whatever shape was half made with the other tool is let go of.
            self._draft = None
        elif intent[0] == "fill":
            self.filled = not self.filled
            self.fill_button.label = FILLED_LABEL if self.filled else HOLLOW_LABEL
            self.fill_button.rect.width = self.font.width(self.fill_button.label) + 8
        elif intent[0] == "undo":
            self.undo()
        elif intent[0] == "clear":
            self.clear()
        elif intent[0] == "guide":
            order = (GUIDE_UNDER, GUIDE_OVER, GUIDE_OFF)
            self.guide = order[(order.index(self.guide) + 1) % len(order)]
            self.guide_button.label = GUIDE_LABELS[self.guide]
        elif intent[0] == "mannequin":
            self.mannequin()
        elif intent[0] == "measures":
            # Back to what every doll starts from.
            self.set_build(self.base_template.starting())
        elif intent[0] == "step":
            self.step(intent[1])
        elif intent[0] == "face":
            self.requested_face = self.resident_id
        elif intent[0] == "new":
            self.new()
        elif intent[0] == "hands":
            self.requested_hands = self.resident_id
        elif intent[0] == "depth" and self.faces is not None:
            low, high = self.faces.rules.body.depths
            self.depth = round(max(low, min(high, self.depth + DEPTH_STEP * intent[1])), 3)
            self.notice = f"Fondo del tronco: {round(self.depth * 100)}% de su ancho"
            self._turned = {}
        elif intent[0] == "far":
            self.far_side = WAYS[(WAYS.index(self.far_side) + 1) % len(WAYS)]
            self.far_button.label = FAR_LABELS[self.far_side]
            self.notice = FAR_NOTICES[self.far_side]
            self._lay_guides()
            if self.far_side != OWN and BODY_CANVAS in self.drawings:
                # What was drawn for the far side is about to go: it can be had back.
                self._remember(BODY_CANVAS)
                self._cut()
        elif intent[0] == "save":
            self.save()
        elif intent[0] == "close":
            self.closed = True

    def _canvas_under(self, position: tuple[int, int]) -> tuple[str, tuple[int, int]] | None:
        """The drawing a position is on, and the pixel of it."""
        for name, area in self.areas.items():
            if area.collidepoint(position):
                return (name, self._on_paper(name, position))
        return None

    def _on_paper(self, name: str, position: tuple[int, int]) -> tuple[int, int]:
        """The pixel of a drawing a position on the screen is over, or would be if its paper went on that far."""
        area, zoom = self.areas[name], self.zooms.get(name, 1)
        return ((position[0] - area.x) // zoom, (position[1] - area.y) // zoom)

    def _paint(self, name: str, start: tuple[int, int], end: tuple[int, int]) -> None:
        surface = self.drawings[name]
        color = TRANSPARENT if self.tool == ERASER_TOOL else (*self.color, 255)
        radius = max(1, self.size // 2)
        pygame.draw.line(surface, color, start, end, max(1, self.size))
        pygame.draw.circle(surface, color, start, radius)
        pygame.draw.circle(surface, color, end, radius)

    def _fill(self, name: str, at: tuple[int, int]) -> None:
        """Pour the colour into everything of the same colour that touches a pixel."""
        surface = self.drawings[name]
        alike = pygame.mask.from_threshold(surface, surface.get_at(at), (1, 1, 1, 1))
        alike.connected_component(at).to_surface(surface, setcolor=(*self.color, 255), unsetcolor=None)

    def press(self, position: tuple[int, int]) -> None:
        """Handle the left button going down at a position on the game's canvas."""
        if self.tool == MEASURE_TOOL and self._take_hold(position):
            return
        on = self._canvas_under(position)
        if on is not None and self.tool == MEASURE_TOOL:
            # With the measures in hand nothing is painted: a slip of the mouse spoils no drawing.
            return
        if on is not None and self.tool in SHAPE_LABELS:
            self._shape_press(*on)
            return
        if self.field.contains(position):
            self._picking = True
            self._pick(position)
            return
        if on is not None:
            name, at = on
            self._remember(name)
            if self.tool == FILL_TOOL:
                self._fill(name, at)
                self._cut()
                self._did(FILL_DEED)
            else:
                self._paint(name, at, at)
                self._stroke = on
            return
        for button in self.buttons:
            if button.contains(position):
                self._apply(button.intent)
                return
        for rect, color in self.swatches:
            if rect.collidepoint(position):
                self.color = color
                if self.tool == ERASER_TOOL:
                    self.tool = BRUSH_TOOL
                return
        for rect, size in self.brush_buttons:
            if rect.collidepoint(position):
                self.size = size
                return

    def drag(self, position: tuple[int, int]) -> None:
        """Go on with a stroke, on the drawing it began on, even past its edge."""
        if self._grab is not None:
            self._pull(position)
            return
        if self._picking:
            self._pick(position)
            return
        if self._draft is not None:
            self._draft.move(self._on_paper(self._draft.where, position))
            return
        if self._stroke is None:
            return
        name, last = self._stroke
        at = self._on_paper(name, position)
        self._paint(name, last, at)
        self._stroke = (name, at)

    def release(self) -> None:
        if self._grab is not None:
            self._grab = None
            # Let go: now the drawing is cut again by the measures it was left with.
            self.set_build(self.build)
            self._did(MEASURE_DEED)
        self._picking = False
        if self._draft is not None and self._draft.tool != POLYGON_TOOL:
            # Let go where it was pressed, it is no shape at all.
            if self._draft.drawn:
                self._lay_down()
            else:
                self._draft = None
        if self._stroke is not None:
            self._stroke = None
            self._cut()
            self._did(STROKE_DEED)

    def _did(self, deed: str) -> None:
        """Say that something has been done here that the opening of a new settlement may be waiting for."""
        if self.on_deed is not None:
            self.on_deed(deed)

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            self.press(canvas_position(event.pos))
        elif event.type == pygame.MOUSEMOTION:
            self.drag(canvas_position(event.pos))
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            self.release()
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 3 and self._draft is not None:
            self._lay_down()
        elif event.type == pygame.KEYDOWN and event.key in (pygame.K_RETURN, pygame.K_KP_ENTER) and self._draft is not None:
            self._lay_down()
        elif event.type == pygame.KEYDOWN and event.key == pygame.K_z and event.mod & pygame.KMOD_CTRL:
            self.undo()
        elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE and self._draft is not None:
            # Out of the shape, not out of the drawing.
            self._draft, self.notice = None, ""
        elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self.closed = True

    def update(self, dt: float) -> None:
        self.time += dt
        self._body.update(dt)


    def _pass(self) -> int:
        """How many times the doll beside the paper has been through all its clips."""
        return int(self.time / PREVIEW_SECONDS) // len(PREVIEW_CLIPS)

    def _view(self) -> str:
        """Which way the doll beside the paper is shown just now: from its side, three quarters
        on and from the front, each for two passes, one facing either way."""
        return PREVIEW_VIEWS[(self._pass() // 2) % len(PREVIEW_VIEWS)]


    def _render_handles(self) -> None:
        """Mark what the mouse can take hold of: the joints on both papers, and on the figure where
        the limbs and the head are joined on."""
        held = self._grab[1] if self._grab is not None else None

        def mark(spot: tuple[float, float], lit: bool, radius: int = HANDLE_RADIUS) -> None:
            centre = (round(spot[0]), round(spot[1]))
            pygame.draw.circle(self.canvas, PALETTE["ink"], centre, radius + 2)
            pygame.draw.circle(self.canvas, PALETTE["glow" if lit else "paper"], centre, radius + 1)
            pygame.draw.circle(self.canvas, PALETTE["ember"], centre, radius - 1)

        for name, area in self.areas.items():
            zoom = self.zooms.get(name, 1)
            for handle in self.joint_handles(name):
                mark((area.x + handle.point[0] * zoom, area.y + handle.point[1] * zoom), handle.key == held)
        for kind, name, spot in self.figure_handles():
            mark(spot, name == held, HANDLE_RADIUS - 1)
            label = HEAD_NAME if kind == "point" else ATTACH_NAMES.get(name, name)
            self.font.draw(self.canvas, label, (round(spot[0]) + HANDLE_RADIUS + 5, round(spot[1]) - 5), PALETTE["paper"])

    def _show_drawing(self, name: str, area: pygame.Rect) -> Callable[[pygame.Surface], None]:
        place = self.layers.on_screen(area)

        def draw(screen: pygame.Surface) -> None:
            screen.fill(PAPER, place)
            guide = self.guides[name]
            if self.guide == GUIDE_UNDER:
                guide.set_alpha(GUIDE_ALPHA[GUIDE_UNDER])
                screen.blit(pygame.transform.scale(guide, place.size), place)
            picture = self.drawings[name]
            if self._draft is not None and self._draft.where == name:
                # The shape in hand is seen on the paper before it is on it.
                picture = self._draft.shown_on(picture, self.color, self.size, self.filled)
            undrawn = self._undrawn.get(name)
            if undrawn is not None and undrawn.get_size() == picture.get_size():
                # What is taken from the other side is not shown where it cannot be drawn.
                picture = picture.copy()
                picture.blit(undrawn, (0, 0), special_flags=pygame.BLEND_RGBA_SUB)
            screen.blit(pygame.transform.scale(picture, place.size), place)
            if self.guide == GUIDE_OVER:
                guide.set_alpha(GUIDE_ALPHA[GUIDE_OVER])
                screen.blit(pygame.transform.scale(guide, place.size), place)

        return draw

    def _own_clip(self, name: str) -> str:
        """The clip for one turn of the preview."""
        return name

    def _show_preview(self, screen: pygame.Surface) -> None:
        """The doll going through its clips, facing one way and then the other."""
        place = self.layers.on_screen(self.preview_rect)
        screen.fill(PALETTE["earth"], place)
        if self._preview is None:
            return
        turn = int(self.time / PREVIEW_SECONDS)
        clip = self._own_clip(PREVIEW_CLIPS[turn % len(PREVIEW_CLIPS)])
        facing = DOLL_FACINGS["right" if self._pass() % 2 == 0 else "left"]
        phase, detail = self.time * PREVIEW_RATE, PREVIEW_DETAIL
        measuring = self.tool == MEASURE_TOOL
        if measuring:
            # While it is being measured it stands still, facing right, so that it can be taken hold of.
            clip, facing, phase, detail = PREVIEW_CLIPS[1], DOLL_FACINGS["right"], 0.0, self.measure_detail
        plan = self.doll_plan
        skeleton = Skeleton(plan, facing)
        body = self._body
        # While it is being measured it is posed exactly, so that its joints are where they are taken hold of.
        body.plan, body.lively = plan, not measuring
        yaw, round_by = PREVIEW_YAW, None
        if self.faces is not None and not measuring:
            # From its side, three quarters on and from the front by turns. Measured, it is as it was drawn.
            rules, view = self.faces.rules, self._view()
            yaw = {"side": rules.side, "quarter": rules.body.nearest, "front": 0.0}[view]
            round_by = body_yaw(rules.body, yaw, standing=True)
            if round_by < rules.body.nearest:
                # Nearer the front than its clips can bear, it only stands.
                clip = PREVIEW_CLIPS[1]
        # It is told what it is at once, and asked where it is once: it is on springs, and told
        # two things in a frame it is thrown from one to the other.
        body.stand(0.0, 0.0, facing, clip, phase)
        pose = body.local_pose()
        if round_by is not None:
            _, _, mirrored, swapped = FACINGS[facing]
            pose = turned_pose(self.faces.rules.body, self._apart, pose, round_by, self.faces.rules.side, mirrored, swapped)
        skeleton.set_pose(pose)
        doll = self._seen(yaw, round_by)
        # The figure of the guide has the hands it was drawn with; a doll may have ones that are made.
        hands = None if self._showing_example else self.made_hands()
        if hands is not None:
            seconds, self._hands_at = self.time - self._hands_at, self.time
            hands.settle(hands.rules.pose_for(clip), seconds)
        made = None if self._showing_example else self.made()
        feet = None if self._showing_example else self.made_feet()
        if feet is not None:
            feet.turned(round_by, self.faces.rules.side if self.faces is not None else 90.0)
        before = screen.get_clip()
        screen.set_clip(place)
        draw_doll(screen, doll, plan, skeleton, (place.centerx, place.bottom - self.preview_foot), detail, hands=made)
        screen.set_clip(before)
