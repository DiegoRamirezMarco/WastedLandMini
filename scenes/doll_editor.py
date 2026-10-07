"""Where a resident's body and head are drawn: two canvases over a guide, and the result moving beside them."""

import json
import math
from collections.abc import Callable
from pathlib import Path

import pygame

from graphics.body_renderer import BodyRenderer
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
from graphics.doll_guide import label_spots, reference
from graphics.font import LINE_HEIGHT, BitmapFont
from graphics.palette import PALETTE
from graphics.screen_layers import TRANSPARENT, ScreenLayers
from scenes.scene import canvas_position
from simulation.residents.manner import OCCASIONS
from simulation.world import SimulationWorld
from skeleton.character import Character
from skeleton.plan import SkeletonPlan
from skeleton.rig import Skeleton
from ui.button import Button
from ui.paintbox import (
    FILLED_LABEL,
    HOLLOW_LABEL,
    POLYGON_NOTICE,
    POLYGON_TOOL,
    SHAPE_LABELS,
    ColorField,
    ShapeDraft,
    draw_chosen,
)
from ui.panel import draw_panel
from ui.tutorial_panel import (
    COLOR_DEED,
    DOLL_FOCUS,
    FILL_DEED,
    MEASURE_DEED,
    RESIDENT_DRAWN_DEED,
    STROKE_DEED,
    UNDO_DEED,
    draw_hint,
    draw_lesson,
    lesson_for,
)

BODY_AT = (196, 58)
HEAD_AT = (604, 58)
PREVIEW = pygame.Rect(604, 272, 192, 170)
NOTES = pygame.Rect(8, 308, 180, 138)
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
MEASURE_PREVIEW = "Arrastra hombros, piernas y cabeza"
MEASURE_NOTES = (
    "Arrastra los puntos del papel: la pieza se alarga o se acorta, y lo que cuelga de ella la sigue.",
    "En la figura de la derecha se mueven hombros, piernas y cabeza hasta donde encajen.",
    "Lo ya pintado no se mueve con los puntos: mejor ajustar las medidas antes de dibujar.",
)
# Where the guide is shown: under the drawing, over it, or not at all.
GUIDE_UNDER, GUIDE_OVER, GUIDE_OFF = "under", "over", "off"
GUIDE_LABELS = {GUIDE_UNDER: "Calco: debajo", GUIDE_OVER: "Calco: encima", GUIDE_OFF: "Calco: quitado"}
GUIDE_ALPHA = {GUIDE_UNDER: 170, GUIDE_OVER: 90}
# What each part is called on the guide, by the bone it goes with whichever side it is on, and
# what the two sides of the body are called.
PART_NAMES = {
    "neck": "cuello", "spine": "tronco", "hips": "cadera", "upper_arm": "brazo", "forearm": "antebrazo",
    "hand": "mano", "thigh": "muslo", "shin": "pierna", "foot": "pie",
}
SIDE_NAMES = {"_left": "DETRÁS", "_right": "DELANTE"}
# Parts whose name does not go up their left edge: one is too thin for it, the other lies flat.
NAMES_BESIDE = ("neck",)
NAMES_BELOW = ("foot",)
# The first and last part of a limb, over and under which the side it is on is written.
LIMB_TOPS = ("upper_arm",)
LIMB_BOTTOMS = ("foot",)
FACING_NOTE = "mira a la derecha >>"
NECK_NOTE = "aquí gira sobre el cuello"
EXAMPLE_PREVIEW = "Así se mueve el ejemplo"
OWN_PREVIEW = "Así se mueve"
UNDO_STEPS = 30
PAPER = PALETTE["bone"]
# Window pixels to one of the skeleton's in the preview, and how fast it goes through its clips.
PREVIEW_DETAIL = 9.0
# How far above the bottom of the preview, in window pixels, the ground it stands on is.
PREVIEW_FOOT = 40
# While it is being measured the figure stands still, and is shown larger to be taken hold of.
MEASURE_DETAIL = 12.0
PREVIEW_RATE = 1.2
# What the preview goes through. Walking and fighting are shown the way of whoever is being drawn.
PREVIEW_CLIPS = ("walk", "idle", "work", "fight")
PREVIEW_SECONDS = 4.0
SAVED_TEXT = "Guardado: ya anda así por el asentamiento"
NOTES_TEXT = (
    "Cada zona es una pieza: lo que pintes dentro se mueve con ella. Las rayas rojas son los cortes, por donde se dobla.",
    "El muñeco de debajo es un ejemplo para fijarte o calcar. Naranja: delante. Azul: detrás.",
    "Las formas se sueltan de un tirón; el polígono, esquina a esquina. Ctrl+Z deshace, Esc vuelve sin guardar.",
)


class DollEditor:
    """Draw a resident. Time stands still while it is open.

    The canvases are as large on the window as two of its pixels to one of the drawing's, which is
    one pixel of the game's own canvas: nothing has to be scaled by a fraction.
    """

    def __init__(
        self,
        canvas: pygame.Surface,
        world: SimulationWorld,
        font: BitmapFont,
        layers: ScreenLayers,
        root: Path,
        dolls: DollStore,
        plan: SkeletonPlan,
        bodies: BodyRenderer,
        on_saved: Callable[[str], None] | None = None,
        on_deed: Callable[[str], None] | None = None,
    ) -> None:
        self.canvas = canvas
        self.world = world
        self.font = font
        self.layers = layers
        self.root = root
        self.on_deed = on_deed
        self.dolls = dolls
        self.plan = plan
        self.bodies = bodies
        self.on_saved = on_saved
        # The template every doll starts from, and this one's own: its measures, the template with
        # its joints where they put them, and the body plan that stands as they say.
        self.base_template = dolls.template
        self.build = self.base_template.starting()
        self.template = self.base_template.built(self.build)
        self.doll_plan = doll_plan(plan, self.template, self.build)
        # What of the measures the mouse has hold of, and how they stood when it took hold.
        self._grab: tuple | None = None
        self.closed = False
        self.resident_id: str | None = None
        self.drawings: dict[str, pygame.Surface] = {}
        self.areas = {
            BODY_CANVAS: pygame.Rect(BODY_AT, self.template.canvases[BODY_CANVAS]),
            HEAD_CANVAS: pygame.Rect(HEAD_AT, self.template.canvases[HEAD_CANVAS]),
        }
        self.guides = {name: self._named_guide(name) for name in self.areas}
        # The figure of the guide, cut as a drawing would be: what moves in the preview until something is drawn.
        self._example = Doll(self.template, {name: reference(self.template, name) for name in self.areas}, self.doll_plan)
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
        # The body the doll is shown moving on beside the paper: on springs, as on the map.
        self._body = Character(plan)
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
            self.guide_button, self.mannequin_button, self.measures_button,
        ]

    def open(self, resident_id: str | None) -> None:
        """Start drawing a resident, from what has been drawn of them so far."""
        residents = list(self.world.residents)
        # Whoever comes to trade is drawn as a resident is, though they are none.
        known = resident_id in self.world.residents or resident_id in self.world.merchants.keepers(self.world)
        self.resident_id = resident_id if known else (residents[0] if residents else None)
        self.closed = self.resident_id is None
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
        self._grab = None
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
        self.guides = {name: self._named_guide(name) for name in self.areas}
        if settled:
            self._example = Doll(
                self.template, {name: reference(self.template, name) for name in self.areas}, self.doll_plan
            )
            self._cut()
        return True

    def joint_handles(self, canvas: str) -> list[JointHandle]:
        """The joints of one canvas that can be taken hold of, where the doll's measures have them."""
        return [handle for handle in self.base_template.handles(self.template) if handle.canvas == canvas]

    @property
    def _per_unit(self) -> float:
        """Canvas pixels to one of the skeleton's in the preview, as it is shown while measuring."""
        return MEASURE_DETAIL / self.layers.scale

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
            return (PREVIEW.centerx + (x + 0.5) * per_unit, PREVIEW.bottom - PREVIEW_FOOT / self.layers.scale + (y + 0.5) * per_unit)

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
            return True
        if PREVIEW.collidepoint(position):
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

    def _did(self, deed: str) -> None:
        """Say that the player has done something the opening of a new settlement may be waiting for."""
        if self.on_deed is not None:
            self.on_deed(deed)

    def _hint_rect(self, hint: str | None) -> pygame.Rect | None:
        """Where on the screen what a lesson is about is."""
        if hint == "palette":
            return self.swatches[0][0].unionall([*(rect for rect, _ in self.swatches), self.field.rect])
        if hint == "canvas":
            return self.areas[BODY_CANVAS]
        if hint == "tools":
            return self.tool_buttons[0].rect.unionall([button.rect for button in (*self.tool_buttons, *self.shape_buttons)])
        if hint == "edit":
            return self.edit_buttons[0].rect.unionall([button.rect for button in self.edit_buttons])
        if hint == "save":
            return next(button.rect for button in self.top_buttons if button.intent == ("save",))
        return None

    def _named_guide(self, canvas: str) -> pygame.Surface:
        """The guide of a canvas with every part named on it, and the side of the body each limb is on."""
        guide = self.template.guide(canvas)
        width, height = guide.get_size()
        ink = PALETTE["ink"]

        written: list[pygame.Rect] = []

        def write(text: str, position: tuple[int, int], upright: bool = False, yielding: bool = False) -> bool:
            """Write a name on the guide. One that is `yielding` is left out where another already is."""
            label = self.font.render(text, ink)
            if upright:
                label = pygame.transform.rotate(label, 90)
            spot = label.get_rect(topleft=position).clamp(guide.get_rect())
            if yielding and spot.inflate(4, 2).collidelist(written) >= 0:
                return False
            written.append(spot)
            backing = pygame.Surface(spot.inflate(2, 2).size, pygame.SRCALPHA)
            backing.fill((*PALETTE["paper"], 170))
            guide.blit(backing, spot.inflate(2, 2))
            guide.blit(label, spot)
            return True

        for bone, spot in label_spots(self.template, canvas).items():
            side = next((suffix for suffix in SIDE_NAMES if bone.endswith(suffix)), "")
            part = bone.removesuffix(side)
            name = PART_NAMES.get(part, part)
            if part in NAMES_BESIDE:
                write(name, (spot.right + 4, spot.top + 8))
            elif part in NAMES_BELOW:
                write(name, (spot.left + 4, spot.bottom - LINE_HEIGHT))
            elif spot.height >= self.font.width(name) + 2:
                # Up its left edge, where the figure leaves room. A part made too short for its name goes without.
                write(name, (spot.left + 3, spot.centery - self.font.width(name) // 2), upright=True)
            if side and part in LIMB_TOPS:
                # Over the round end the game gives a limb where nothing else begins.
                top = spot.top - round(self.template.parts[bone].radius) - LINE_HEIGHT - 10
                write(SIDE_NAMES[side], (spot.centerx - self.font.width(SIDE_NAMES[side]) // 2, top))
            if side and part in LIMB_BOTTOMS:
                write(SIDE_NAMES[side], (spot.centerx - self.font.width(SIDE_NAMES[side]) // 2, spot.bottom + 3))
        whole = [spec for spec in self.template.parts.values() if spec.canvas == canvas and spec.whole]
        for spec in whole:
            x = round(spec.start[0]) - self.font.width(NECK_NOTE) // 2
            write(NECK_NOTE, (x, round(spec.start[1]) + 7))
        # Which way it faces goes at the foot of the paper, or at its head where the foot is taken.
        middle = (width - self.font.width(FACING_NOTE)) // 2
        for y in (4, height - LINE_HEIGHT - 2) if whole else (height - LINE_HEIGHT - 2, 4):
            if write(FACING_NOTE, (middle, y), yielding=True):
                break
        return guide

    def _cut(self) -> None:
        """Cut the drawings as they stand into a doll, to be seen moving in the preview.

        With nothing drawn yet it is the figure of the guide that moves, to show what the parts add up to.
        """
        self._showing_example = not any(pygame.mask.from_surface(drawing).count() for drawing in self.drawings.values())
        if self._showing_example:
            self._preview = self._example
            return
        self._preview = Doll(self.template, self.drawings, self.doll_plan)

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
        for name in self.drawings:
            self._remember(name)
            self.drawings[name].fill(TRANSPARENT)
        self._cut()

    def mannequin(self) -> None:
        """Fill every zone with a plain figure in the colours the resident has worn until now."""
        skin = self.bodies.skin(self.resident_id)

        def strip(cell: str, end: int) -> tuple[int, int, int]:
            return skin.strips[("side", cell)].colors[end]

        def middle(cell: str) -> tuple[int, int, int]:
            sprite = skin.sprites[("side", cell, False)]
            return tuple(sprite.image.get_at(sprite.anchor))[:3]

        colors = {"spine": middle("torso"), "skull": middle("head"), "neck": middle("head"), "hips": strip("thigh", 0)}
        for side in ("_left", "_right"):
            colors[f"upper_arm{side}"] = strip("upper_arm", 0)
            colors[f"forearm{side}"] = strip("forearm", -1)
            colors[f"hand{side}"] = strip("forearm", -1)
            colors[f"thigh{side}"] = strip("thigh", 0)
            colors[f"shin{side}"] = strip("thigh", 0)
            colors[f"foot{side}"] = strip("shin", -1)
        for name, figure in self.template.mannequin(colors).items():
            self._remember(name)
            self.drawings[name] = figure
        self._cut()

    def save(self) -> bool:
        """Write both drawings where the game looks for them. Returns whether it worked."""
        if self.resident_id is None:
            return False
        try:
            for name, surface in self.drawings.items():
                path = self.root / doll_path(self.resident_id, name)
                path.parent.mkdir(parents=True, exist_ok=True)
                pygame.image.save(surface, str(path))
            # Their measures go with their drawings: one is cut by the other.
            measures = self.root / build_path(self.resident_id)
            measures.write_text(json.dumps(self.build.to_data(), indent=2) + "\n", encoding="utf-8")
        except (OSError, pygame.error):
            self.notice = "No se pudo guardar"
            return False
        self.dolls.forget(self.resident_id)
        if self.on_saved is not None:
            self.on_saved(self.resident_id)
        self.notice = SAVED_TEXT
        self._did(RESIDENT_DRAWN_DEED)
        return True

    def step(self, by: int) -> None:
        """Go on to the next resident, or back to the one before."""
        residents = list(self.world.residents)
        if self.resident_id in residents:
            self.open(residents[(residents.index(self.resident_id) + by) % len(residents)])

    def _pick(self, position: tuple[int, int]) -> None:
        """Take the colour under the mouse off the field: any colour, not only the ready ones."""
        self.color = self.field.color_at(position)
        if self.tool == ERASER_TOOL:
            self.tool = BRUSH_TOOL
        self._did(COLOR_DEED)

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
        elif intent[0] == "save":
            self.save()
        elif intent[0] == "close":
            self.closed = True

    def _canvas_under(self, position: tuple[int, int]) -> tuple[str, tuple[int, int]] | None:
        """The drawing a position is on, and the pixel of it."""
        for name, area in self.areas.items():
            if area.collidepoint(position):
                return (name, (position[0] - area.x, position[1] - area.y))
        return None

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
                self._did(COLOR_DEED)
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
            area = self.areas[self._draft.where]
            self._draft.move((position[0] - area.x, position[1] - area.y))
            return
        if self._stroke is None:
            return
        name, last = self._stroke
        area = self.areas[name]
        at = (position[0] - area.x, position[1] - area.y)
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

    def render(self) -> None:
        self.layers.clear()
        canvas, font = self.canvas, self.font
        canvas.fill(PALETTE["ink"])
        resident = self.world.residents.get(self.resident_id or "")
        name = resident.name if resident is not None else self.world.merchants.keepers(self.world).get(self.resident_id or "")
        title = f"Dibujar a {name}" if name else "Dibujar"
        font.draw(canvas, title, (TOOLS_LEFT, 4), PALETTE["glow"], scale=2)
        font.draw(canvas, self.notice or "El tiempo está detenido", (TOOLS_LEFT, 30), PALETTE["lamp" if self.notice else "stone"])
        for button in self.top_buttons:
            button.draw(canvas, font)

        font.draw(canvas, "Color", (TOOLS_LEFT, 44), PALETTE["dust"])
        draw_chosen(canvas, CHOSEN, self.color)
        for rect, color in self.swatches:
            pygame.draw.rect(canvas, color, rect.inflate(-2, -2))
            if color == self.color and self.tool != ERASER_TOOL:
                pygame.draw.rect(canvas, PALETTE["paper"], rect, 1)
        self.field.draw(canvas)
        for rect, size in self.brush_buttons:
            draw_panel(canvas, rect, fill="shadow", border="lamp" if size == self.size else "iron")
            pygame.draw.circle(canvas, PALETTE["bone"], rect.center, max(1, size // 2))
        for button in (*self.tool_buttons, *self.shape_buttons):
            button.draw(canvas, font, active=button.intent == ("tool", self.tool))
        self.fill_button.draw(canvas, font, active=self.filled)
        for button in (*self.edit_buttons, self.guide_button, self.mannequin_button, self.measures_button):
            button.draw(canvas, font)

        for name, area in self.areas.items():
            label = "Cuerpo" if name == BODY_CANVAS else "Cabeza"
            font.draw(canvas, label, (area.x, area.y - LINE_HEIGHT - 1), PALETTE["dust"])
            pygame.draw.rect(canvas, PALETTE["stone"], area.inflate(2, 2), 1)
            canvas.fill(TRANSPARENT, area)
            self.layers.under(self._show_drawing(name, area))
        measuring = self.tool == MEASURE_TOOL
        caption = MEASURE_PREVIEW if measuring else (EXAMPLE_PREVIEW if self._showing_example else OWN_PREVIEW)
        font.draw(canvas, caption, (PREVIEW.x, PREVIEW.y - LINE_HEIGHT - 1), PALETTE["glow" if measuring else "dust"])
        pygame.draw.rect(canvas, PALETTE["stone"], PREVIEW.inflate(2, 2), 1)
        canvas.fill(TRANSPARENT, PREVIEW)
        self.layers.under(self._show_preview)

        if measuring:
            self._render_handles()
        lesson = lesson_for(self.world, focus=DOLL_FOCUS)
        if lesson is not None:
            # While the opening of a new settlement teaches drawing, the lesson goes where the notes do.
            draw_lesson(canvas, font, NOTES, self.world, lesson)
            draw_hint(canvas, self._hint_rect(lesson.hint), self.time)
            return
        y = NOTES.y
        for note in MEASURE_NOTES if measuring else NOTES_TEXT:
            for line in font.wrap(note, NOTES.width):
                if y + LINE_HEIGHT > NOTES.bottom:
                    break
                font.draw(canvas, line, (NOTES.x, y), PALETTE["bone"])
                y += LINE_HEIGHT
            y += 3

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
            for handle in self.joint_handles(name):
                mark((area.x + handle.point[0], area.y + handle.point[1]), handle.key == held)
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
            screen.blit(pygame.transform.scale(picture, place.size), place)
            if self.guide == GUIDE_OVER:
                guide.set_alpha(GUIDE_ALPHA[GUIDE_OVER])
                screen.blit(pygame.transform.scale(guide, place.size), place)

        return draw

    def _own_clip(self, name: str) -> str:
        """The clip for one turn of the preview: their own manner of it, where it is something done in a manner."""
        resident = self.world.residents.get(self.resident_id or "")
        kind = self.world.registries.manners.kind_for(name) if name in OCCASIONS else None
        manner = self.world.manner_of(resident, kind.kind_id) if resident is not None and kind is not None else None
        return manner.clip if manner is not None else name

    def _show_preview(self, screen: pygame.Surface) -> None:
        """The doll going through its clips, facing one way and then the other."""
        place = self.layers.on_screen(PREVIEW)
        screen.fill(PALETTE["earth"], place)
        if self._preview is None:
            return
        turn = int(self.time / PREVIEW_SECONDS)
        clip = self._own_clip(PREVIEW_CLIPS[turn % len(PREVIEW_CLIPS)])
        facing = DOLL_FACINGS["right" if (turn // len(PREVIEW_CLIPS)) % 2 == 0 else "left"]
        phase, detail = self.time * PREVIEW_RATE, PREVIEW_DETAIL
        if self.tool == MEASURE_TOOL:
            # While it is being measured it stands still, facing right, so that it can be taken hold of.
            clip, facing, phase, detail = PREVIEW_CLIPS[1], DOLL_FACINGS["right"], 0.0, MEASURE_DETAIL
        plan = self.doll_plan
        skeleton = Skeleton(plan, facing)
        body = self._body
        # While it is being measured it is posed exactly, so that its joints are where they are taken hold of.
        body.plan, body.lively = plan, self.tool != MEASURE_TOOL
        body.stand(0.0, 0.0, facing, clip, phase)
        skeleton.set_pose(body.local_pose())
        before = screen.get_clip()
        screen.set_clip(place)
        draw_doll(screen, self._preview, plan, skeleton, (place.centerx, place.bottom - PREVIEW_FOOT), detail)
        screen.set_clip(before)
