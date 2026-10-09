"""Where armour is drawn and tried on (P66): a piece painted over the plain figure, on the doll's
own two papers, and seen at once on whoever it is tried on, moving.

It is the doll editor's paper and tools with other things beside them. Only the part of the paper
a piece is worn on can be painted, and the figure beside it is not the drawing cut up but a
resident with every piece on, each laid over their own body (`graphics/tailor.py`).

This is a first look. The pieces drawn here are nobody's: who wears what is not yet something the
settlement knows. A switch puts them on everybody on the map meanwhile, to see them there.
"""

import json
from collections.abc import Callable, Sequence
from pathlib import Path

import pygame

from graphics.body_renderer import BodyRenderer
from graphics.doll import Doll, DollStore, Garment, garment_file, garment_path, unsided
from graphics.doll_guide import GUIDE_JOINT, cuts, piece_zone, pieces, reference
from graphics.font import BitmapFont
from graphics.palette import PALETTE
from graphics.screen_layers import ScreenLayers
from graphics.stand_ins import stand_in
from scenes.doll_editor import BODY_AT, BRUSH_TOOL, ERASER_TOOL, FILL_TOOL, TOOL_LABELS, TOOLS_LEFT, DollEditor
from simulation.world import SimulationWorld
from skeleton.plan import SIDES, SkeletonPlan
from ui.button import Button

# Where the places there are to wear something are picked, over the paper of the body.
SLOTS_TOP = 26
MIRROR_LABEL = "Igual al otro lado"
MAP_LABELS = {False: "En el mapa: no", True: "En el mapa: sí"}
# How solid what is not to be painted is made under the paper's guide, and the other pieces on it.
VEIL = 110
OTHERS = 120
SAVED = "Guardado"
NOT_SAVED = "No se pudo guardar"
NOBODY = "el maniquí"
NOTES = (
    "Pinta la pieza sobre el maniquí, dentro de la zona clara: lo de fuera no se pinta.",
    "A la derecha se ve puesta. Con < y > cambia a quién: la misma pieza se ajusta a cada cuerpo.",
    "Es una prueba: con En el mapa las llevan todos para verlas allí, y no cambia nada del juego.",
)


class GarmentEditor(DollEditor):
    """Draw the pieces there are to wear, and try them on. Time stands still while it is open."""

    # The place the piece being drawn is worn in. None until the editor is made.
    slot: str | None = None

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
        on_tried: Callable[[Sequence[str]], None] | None = None,
    ) -> None:
        super().__init__(canvas, world, font, layers, root, dolls, plan, bodies)
        # Told what everybody on the map is to be seen in, whenever that changes.
        self.on_tried = on_tried
        self.on_map = False
        self.slots = list(self.base_template.wear)
        # Every piece as it stands, by its slot and canvas, and each laid over whoever it is tried on.
        self.pieces: dict[str, dict[str, pygame.Surface]] = {}
        self._laid: dict[str, dict[str, pygame.Surface]] = {}
        self._allowed: dict[tuple[str, str], pygame.mask.Mask] = {}
        self._wearer: Doll | None = None
        self._bodies: dict = {}
        # No way from here to here, and neither the measures nor a figure to start from: a piece
        # is drawn over the one there is.
        self.top_buttons = [button for button in self.top_buttons if button.intent != ("fitting",)]
        self.tool_buttons = self._row(
            self.tool_buttons[0].rect.y, [(TOOL_LABELS[tool], ("tool", tool)) for tool in (BRUSH_TOOL, ERASER_TOOL, FILL_TOOL)]
        )
        self.mannequin_button = Button.at(font, TOOLS_LEFT, self.mannequin_button.rect.y, MIRROR_LABEL, ("mirror",))
        self.measures_button = Button.at(font, TOOLS_LEFT, self.measures_button.rect.y, MAP_LABELS[False], ("on_map",))
        self.extra_buttons = self._row(SLOTS_TOP, [(slot.name, ("slot", slot.slot_id)) for slot in self.slots], left=BODY_AT[0])
        self.slot = self.slots[0].slot_id if self.slots else None

    # ----- what is being drawn, and on whom it is tried -----

    @property
    def worn(self) -> tuple[str, ...]:
        """What every piece drawn here is called where it is kept: the slot it is for."""
        return tuple(slot.slot_id for slot in self.slots)

    def open(self, resident_id: str | None) -> None:
        """Start from the pieces as they were kept, tried on a resident, or on the plain figure."""
        self.closed = self.slot is None
        self.requested_fitting = None
        self.notice = ""
        self._undo, self._stroke, self._draft, self._grab = [], None, None, None
        self.tool = BRUSH_TOOL if self.tool not in (BRUSH_TOOL, ERASER_TOOL, FILL_TOOL) else self.tool
        self.pieces = {slot.slot_id: self._kept(slot.slot_id) for slot in self.slots}
        self.resident_id = resident_id if resident_id in self.world.residents else next(iter(self.world.residents), None)
        self._try_on()
        if not self.closed:
            self.pick(self.slot)

    def _kept(self, slot_id: str) -> dict[str, pygame.Surface]:
        """The drawing of a piece on every canvas, as it was kept: clean paper where it was not."""
        papers = {name: pygame.Surface(size, pygame.SRCALPHA) for name, size in self.template.canvases.items()}
        garment = self.dolls.garment(slot_id)
        if garment is None:
            return papers
        drawings = garment.drawings
        if garment.build.to_data() != self.build.to_data():
            # Drawn over the figure as it used to stand: it is laid over the figure of today.
            figure = {name: reference(self.template, name) for name in self.template.canvases}
            drawings = self.dolls.tailor.fitted(garment, self.dolls.tailor.bodies(self.template, figure))
        for name, drawing in drawings.items():
            if drawing.get_size() == papers[name].get_size():
                papers[name].blit(drawing, (0, 0))
        return papers

    def pick(self, slot_id: str) -> None:
        """Take up the piece of another slot."""
        if slot_id not in self.pieces:
            return
        self.slot = slot_id
        self.drawings = self.pieces[slot_id]
        self._undo, self._stroke, self._draft = [], None, None
        self.guides = {name: self._named_guide(name) for name in self.areas}
        self._cut()

    def step(self, by: int) -> None:
        """Try the pieces on the next resident, or on the one before."""
        residents = list(self.world.residents)
        if self.resident_id in residents:
            self.resident_id = residents[(residents.index(self.resident_id) + by) % len(residents)]
            self._try_on()
            self._cut()

    def _try_on(self) -> None:
        """Take whoever the pieces are tried on, as they are drawn or as the plain figure they are
        shown as until somebody draws them, and have every piece laid over them anew."""
        wearer = None
        if self.resident_id is not None:
            body_id = self.resident_id
            wearer = self.dolls.get(body_id) or self.dolls.stand_in(
                body_id, lambda template: stand_in(template, self.bodies.skin(body_id))
            )
        self._wearer = wearer or self._example
        self._bodies = self.dolls.tailor.bodies(self._wearer.template, self._wearer.sheets)
        self._laid = {}

    # ----- where a piece may be painted -----

    def allowed(self, canvas: str) -> pygame.mask.Mask:
        """Where on a canvas the piece in hand may be painted: the parts its slot is worn on."""
        key = (self.slot or "", canvas)
        if key not in self._allowed:
            template = self.template
            bones = [bone for bone in template.worn_on(self.slot or "") if template.parts[bone].canvas == canvas]
            zone = pygame.Mask(template.canvases[canvas], fill=any(template.parts[bone].whole for bone in bones))
            for piece in pieces(template, canvas):
                mine = tuple(bone for bone in piece if bone in bones)
                if mine:
                    zone.draw(piece_zone(template, mine), (0, 0))
            self._allowed[key] = zone
        return self._allowed[key]

    def _keep_within(self, name: str) -> None:
        """Rub out whatever of the piece in hand is where it is not worn."""
        within = self.allowed(name).to_surface(setcolor=(255, 255, 255, 255), unsetcolor=(255, 255, 255, 0))
        self.drawings[name].blit(within, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)

    def _paint(self, name: str, start: tuple[int, int], end: tuple[int, int]) -> None:
        super()._paint(name, start, end)
        self._keep_within(name)

    def _named_guide(self, canvas: str) -> pygame.Surface:
        """What is under the paper: the plain figure, the other pieces over it, and everything
        but where this one is worn made dark."""
        if self.slot is None:
            return super()._named_guide(canvas)
        guide = pygame.Surface(self.template.canvases[canvas], pygame.SRCALPHA)
        guide.blit(reference(self.template, canvas), (0, 0))
        for slot_id, papers in self.pieces.items():
            if slot_id != self.slot:
                other = papers[canvas].copy()
                other.fill((255, 255, 255, OTHERS), special_flags=pygame.BLEND_RGBA_MULT)
                guide.blit(other, (0, 0))
        zone = self.allowed(canvas)
        guide.blit(zone.to_surface(setcolor=(0, 0, 0, 0), unsetcolor=(*PALETTE["ink"], VEIL)), (0, 0))
        for part in zone.connected_components():
            edge = part.outline()
            if len(edge) > 2:
                pygame.draw.lines(guide, (*GUIDE_JOINT, 255), True, edge)
        # Where it bends, as the body under it does.
        bones = tuple(bone for bone in self.template.worn_on(self.slot) if self.template.parts[bone].canvas == canvas)
        for start, end in cuts(self.template, canvas, bones) if bones else ():
            pygame.draw.line(guide, (*GUIDE_JOINT, 255), start, end)
        return guide

    # ----- seeing it on somebody -----

    def _garment(self, slot_id: str) -> Garment | None:
        """The piece of a slot as it stands on the paper. None while nothing of it is painted."""
        papers = self.pieces[slot_id]
        if not any(pygame.mask.from_surface(paper).count() for paper in papers.values()):
            return None
        return Garment(slot_id, slot_id, papers, self.build)

    def _cut(self) -> None:
        """Lay the piece in hand over whoever it is tried on, and cut them with every piece on."""
        if self.slot is None or self._wearer is None:
            return
        for name in self.drawings:
            self._keep_within(name)
        garment = self._garment(self.slot)
        self._laid[self.slot] = self.dolls.tailor.fitted(garment, self._bodies) if garment is not None else {}
        wearer = self._wearer
        sheets = {name: sheet.copy() for name, sheet in wearer.sheets.items()}
        for slot in self.slots:
            if slot.slot_id not in self._laid:
                other = self._garment(slot.slot_id)
                self._laid[slot.slot_id] = self.dolls.tailor.fitted(other, self._bodies) if other is not None else {}
            for name, laid in self._laid[slot.slot_id].items():
                sheets[name].blit(laid, (0, 0))
        self._preview = Doll(wearer.template, sheets, wearer.plan)
        self._showing_example = False
        # They stand and move by their own measures, not by those of the figure on the paper.
        self.doll_plan = wearer.plan or self.plan

    # ----- the buttons -----

    def mirror(self) -> None:
        """Have the far side of the body wear what was painted for the near one."""
        template = self.template
        remembered: set[str] = set()
        for bone in template.worn_on(self.slot or ""):
            other = unsided(bone) + SIDES[0]
            if not bone.endswith(SIDES[1]) or other not in template.parts:
                continue
            near, far = template.parts[bone], template.parts[other]
            if near.canvas != far.canvas:
                continue
            drawing = self.drawings[near.canvas]
            if near.canvas not in remembered:
                remembered.add(near.canvas)
                self._remember(near.canvas)
            painted = drawing.copy()
            own = piece_zone(template, (bone,)).to_surface(setcolor=(255, 255, 255, 255), unsetcolor=(255, 255, 255, 0))
            painted.blit(own, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
            # What the far side had goes, and the near side's is put where the far part is.
            piece_zone(template, (other,)).to_surface(drawing, setcolor=(0, 0, 0, 0), unsetcolor=None)
            by = (round(far.start[0] - near.start[0]), round(far.start[1] - near.start[1]))
            drawing.blit(painted, by)
        self._cut()

    def show_on_map(self, shown: bool) -> None:
        """Have everybody on the map seen in the pieces as they are kept, or in none."""
        if shown and not self.save():
            return
        self.on_map = shown
        self.measures_button.label = MAP_LABELS[shown]
        self.measures_button.rect.width = self.font.width(self.measures_button.label) + 8
        if self.on_tried is not None:
            self.on_tried(self.worn if shown else ())

    def _apply(self, intent: tuple) -> None:
        if intent[0] == "slot":
            self.pick(intent[1])
        elif intent[0] == "mirror":
            self.mirror()
        elif intent[0] == "on_map":
            self.show_on_map(not self.on_map)
        else:
            super()._apply(intent)

    def _active(self, button: Button) -> bool:
        return button.intent in (("tool", self.tool), ("slot", self.slot)) or (button.intent == ("on_map",) and self.on_map)

    def save(self) -> bool:
        """Keep every piece where the game looks for them: one that has nothing painted is not kept."""
        try:
            for slot in self.slots:
                garment = self._garment(slot.slot_id)
                kept = self.root / garment_file(slot.slot_id)
                canvases = {self.template.parts[bone].canvas for bone in self.template.worn_on(slot.slot_id)}
                for name in self.template.canvases:
                    path = self.root / garment_path(slot.slot_id, name)
                    if garment is not None and name in canvases:
                        path.parent.mkdir(parents=True, exist_ok=True)
                        pygame.image.save(garment.drawings[name], str(path))
                    else:
                        path.unlink(missing_ok=True)
                if garment is not None:
                    kept.write_text(json.dumps({"slot": slot.slot_id, "build": self.build.to_data()}, indent=2) + "\n", encoding="utf-8")
                else:
                    kept.unlink(missing_ok=True)
                self.dolls.forget_garment(slot.slot_id)
        except (OSError, pygame.error):
            self.notice = NOT_SAVED
            return False
        self.notice = SAVED
        return True

    # ----- what is written -----

    def _title(self) -> str:
        slot = self.base_template.slot(self.slot or "")
        return f"Probador: {slot.name}" if slot is not None else "Probador"

    def _caption(self) -> str:
        resident = self.world.residents.get(self.resident_id or "")
        return f"Puesto a {resident.name if resident is not None else NOBODY}"

    def _notes(self) -> tuple[str, ...]:
        return NOTES

    def _lesson(self):
        return None
