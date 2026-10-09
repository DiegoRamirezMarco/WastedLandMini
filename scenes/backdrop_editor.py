"""Where the country a trip goes through is drawn: so many layers on one paper, that go by
each at its own pace behind whoever walks (P69).

It draws as an object is drawn, with the same tools, a layer at a time. The others are seen
faintly under and over the one in hand, and beside the paper the whole of it goes by as it
will out there, with whoever it was opened for walking in it.
"""

from collections.abc import Callable
from pathlib import Path

import pygame

from graphics.backdrop import BackdropStore, Strip, backdrop_path, draw_strips
from graphics.doll import DOLL_FACINGS, Doll, draw_doll
from graphics.font import LINE_HEIGHT, BitmapFont
from graphics.palette import PALETTE
from graphics.screen_layers import ScreenLayers
from scenes.body_stage import TILES_PER_STRIDE
from scenes.expedition_view import AHEAD, BODY_TALL, NOWHERE, STRIDES
from scenes.object_editor import (
    DRAWING_AT,
    GUIDE_ALPHA,
    GUIDE_OVER,
    GUIDE_UNDER,
    PAPER,
    PREVIEW,
    UNDO_STEPS,
    ObjectEditor,
)
from settings import TILE_SIZE
from simulation.world import SimulationWorld
from skeleton.character import Character
from skeleton.plan import SkeletonPlan
from skeleton.rig import Skeleton
from ui.button import Button
from ui.tutorial_panel import UNDO_DEED

# Somebody as they are shown walking: their doll, the plan it moves by, and the clip and pace
# of their own way of walking.
Walker = tuple[Doll, SkeletonPlan, str, float]

# Short, all of them: the row of layers begins where a long one would run to.
SAVED_TEXT = "Guardado: ya se ve fuera"
NOTHING_DRAWN = "Guardado: se ve el del juego"
ROLL_NOTICE = "Papel corrido"
PREVIEW_HEADING = "Así pasa mientras alguien anda"
OTHERS_ON, OTHERS_OFF = "Capas: todas", "Capas: solo esta"
# Where the row of layers is: over the paper, and under the name of what is being drawn.
LAYERS_TOP = 30
# How much of its width the paper is slid by at a press, to draw across where its ends meet.
ROLL = 0.25
# How strongly the layers that are not in hand are seen on the paper, behind it and in front.
BEHIND_ALPHA = 130
AHEAD_ALPHA = 80
# Where feet come down and how tall somebody is, on the guide.
FEET: tuple[int, int, int, int] = (*PALETTE["ember"], 255)
BODY: tuple[int, int, int, int] = (*PALETTE["ember"], 150)
LEGEND = (
    (PALETTE["ember"], "La línea es donde pisan, y el cuadro lo que ocupa alguien."),
    (None, "Los dos lados del papel se tocan: lo que sale por uno entra por el otro."),
    (None, "Debajo, la capa del juego como ejemplo. Las demás capas se ven tenues."),
)
NOTES_TEXT = (
    "Lo que quede sin pintar deja ver la capa de detrás. Una capa sin nada pintado es la del juego.",
    "Correr desliza el papel de lado, para pintar donde se juntan sus extremos.",
    "Arte de partida pone la capa del juego sobre el papel. Ctrl+Z deshace, Esc vuelve sin guardar.",
)


def rolled(picture: pygame.Surface, by: int) -> pygame.Surface:
    """A picture slid sideways by so many pixels, with what goes off one end come in at the other."""
    wide = picture.get_width()
    by %= wide
    slid = pygame.Surface(picture.get_size(), pygame.SRCALPHA)
    slid.blit(picture, (by, 0))
    slid.blit(picture, (by - wide, 0))
    return slid


class BackdropEditor(ObjectEditor):
    """Draw the layers of a zone. Simulation time stands still while it is open."""

    def __init__(
        self,
        canvas: pygame.Surface,
        world: SimulationWorld,
        font: BitmapFont,
        layers: ScreenLayers,
        root: Path,
        backdrops: BackdropStore,
        walker: Callable[[str | None], Walker | None] | None = None,
        on_saved: Callable[[str], None] | None = None,
    ) -> None:
        # What is drawn of each layer, by its ID. The one in hand is `drawing`.
        self.drawings: dict[str, pygame.Surface] = {}
        self.layer = backdrops.plan.layers[0].layer_id
        # It draws as an object is drawn, on a paper of its own and with nothing of the opening in it.
        super().__init__(canvas, world, font, layers, root, None, on_saved)  # type: ignore[arg-type]
        self.backdrops = backdrops
        self.plan = backdrops.plan
        self.walker = walker
        self.zone: str | None = None
        self.resident_id: str | None = None
        self.legend = LEGEND
        self.preview_heading = PREVIEW_HEADING
        self.notes = NOTES_TEXT
        # Whether the layers that are not in hand are seen on the paper.
        self.others_on = True
        self._undo: list[dict[str, pygame.Surface]] = []  # type: ignore[assignment]
        self.layer_buttons = self._row(
            LAYERS_TOP, [(layer.name, ("layer", layer.layer_id)) for layer in self.plan.layers], left=DRAWING_AT[0]
        )
        left = self.layer_buttons[-1].rect.right + 10
        self.roll_buttons = self._row(LAYERS_TOP, [("< Correr", ("roll", -1)), ("Correr >", ("roll", 1))], left=left)
        self.others_button = Button.at(font, PREVIEW.x, PREVIEW.bottom + 4, OTHERS_ON, ("others",))
        # The picture the game has of each layer, on the paper, for the ones with nothing drawn.
        self._own: dict[tuple[str, str], pygame.Surface] = {}
        self._body: Character | None = None
        self._skeletons: dict[tuple, Skeleton] = {}

    # ----- the layer in hand -----

    @property
    def drawing(self) -> pygame.Surface:
        return self.drawings[self.layer]

    @drawing.setter
    def drawing(self, picture: pygame.Surface) -> None:
        self.drawings[self.layer] = picture

    @property
    def buttons(self) -> list[Button]:
        return [*super().buttons, *self.layer_buttons, *self.roll_buttons, self.others_button]

    def open(self, zone_id: str | None, resident_id: str | None = None) -> None:  # type: ignore[override]
        """Start drawing a zone, from what has been drawn of it so far. `resident_id` is who
        is seen walking through it beside the paper."""
        known = {zone.zone_id for zone in self.world.registries.expeditions.zones} | {NOWHERE}
        self.zone = zone_id if zone_id in known else None
        self.kind = self.zone
        self.resident_id = resident_id
        self.closed = self.zone is None
        self.notice = ""
        self._undo = []
        self._stroke = None
        self._draft = None
        self._own = {}
        if self.zone is None:
            return
        self.zoom = 1
        self.area = pygame.Rect(DRAWING_AT, self.plan.paper)
        self.drawings = {}
        for layer in self.plan.layers:
            paper = pygame.Surface(self.plan.paper, pygame.SRCALPHA)
            kept = self.backdrops.drawing(self.zone, layer.layer_id)
            if kept is not None:
                paper.blit(kept, (0, 0))
            self.drawings[layer.layer_id] = paper
        self._set_layer(self.layer if self.plan.layer(self.layer) is not None else self.plan.layers[0].layer_id)

    def _set_layer(self, layer_id: str) -> None:
        if self.plan.layer(layer_id) is None or self.zone is None:
            return
        self.layer = layer_id
        self.guide_picture = self._guide(layer_id)
        self._stroke = None
        self._draft = None
        # What goes in the layer in hand is said first.
        layer = self.plan.layer(layer_id)
        self.notes = (f"{layer.name}. {layer.note}", *NOTES_TEXT) if layer.note else NOTES_TEXT

    def _guide(self, layer_id: str) -> pygame.Surface:
        """What is traced over: the game's own layer, where feet come down, and how tall somebody is."""
        wide, tall = self.plan.paper
        guide = self.backdrops.starter(self.zone or NOWHERE, layer_id)
        feet = round(self.plan.ground * tall)
        high = round(self.plan.figure * tall)
        pygame.draw.line(guide, FEET, (0, feet), (wide, feet), 1)
        body = pygame.Rect(0, feet - high, max(4, high // 3), high)
        body.centerx = round(wide * AHEAD)
        pygame.draw.rect(guide, BODY, body, 1)
        return guide

    # ----- changing what is drawn -----

    def _remember(self, every: bool = False) -> None:
        """Keep what is about to be changed: the layer in hand, or every one of them."""
        changed = self.drawings if every else {self.layer: self.drawing}
        self._undo.append({layer_id: picture.copy() for layer_id, picture in changed.items()})
        del self._undo[:-UNDO_STEPS]

    def undo(self) -> None:
        if not self._undo:
            return
        kept = self._undo.pop()
        self.drawings.update(kept)
        if len(kept) == 1:
            # Back on the layer the change was made to.
            self._set_layer(next(iter(kept)))
        self._did(UNDO_DEED)

    def starter(self) -> None:
        """Put the game's own picture of the layer in hand on the paper, to be drawn over."""
        if self.zone is not None:
            self._remember()
            self.drawing = self.backdrops.starter(self.zone, self.layer)

    def roll(self, way: int) -> None:
        """Slide the whole paper sideways, every layer with it: where its two ends meet comes
        into the middle, to be drawn across."""
        if self.zone is None:
            return
        self._remember(every=True)
        by = way * round(self.plan.paper[0] * ROLL)
        self.drawings = {layer_id: rolled(picture, by) for layer_id, picture in self.drawings.items()}
        self._stroke = None
        self._draft = None
        self.notice = ROLL_NOTICE

    def save(self) -> bool:
        """Write every layer that has anything on it where the game looks for it, and take
        away what was kept of one that has nothing: that one is the game's again."""
        if self.zone is None:
            return False
        painted = 0
        try:
            for layer_id, picture in self.drawings.items():
                path = self.root / backdrop_path(self.zone, layer_id)
                if picture.get_bounding_rect().width <= 0:
                    path.unlink(missing_ok=True)
                    continue
                path.parent.mkdir(parents=True, exist_ok=True)
                pygame.image.save(picture, str(path))
                painted += 1
        except (OSError, pygame.error):
            self.notice = "No se pudo guardar"
            return False
        self.backdrops.forget(self.zone)
        if self.on_saved is not None:
            self.on_saved(self.zone)
        self.notice = SAVED_TEXT if painted else NOTHING_DRAWN
        return True

    def _apply(self, intent: tuple) -> None:
        if intent[0] == "layer":
            self._set_layer(intent[1])
        elif intent[0] == "roll":
            self.roll(intent[1])
        elif intent[0] == "others":
            self.others_on = not self.others_on
            self.others_button.label = OTHERS_ON if self.others_on else OTHERS_OFF
            self.others_button.rect.width = self.font.width(self.others_button.label) + 8
        else:
            super()._apply(intent)

    # ----- showing it -----

    def _title(self) -> str:
        zone = next((zone for zone in self.world.registries.expeditions.zones if zone.zone_id == self.zone), None)
        return f"Dibujar el fondo: {zone.name}" if zone is not None else "Dibujar el fondo"

    def _lesson(self):
        return None

    def _shown(self, layer_id: str) -> pygame.Surface:
        """A layer as it will be seen out there: as it is drawn, or the game's own while nothing is."""
        picture = self.drawings[layer_id]
        if picture.get_bounding_rect().width > 0:
            return picture
        key = (self.zone or NOWHERE, layer_id)
        if key not in self._own:
            self._own[key] = self.backdrops.starter(*key)
        return self._own[key]

    def render(self) -> None:
        super().render()
        canvas, font = self.canvas, self.font
        for button in self.layer_buttons:
            button.draw(canvas, font, active=button.intent == ("layer", self.layer))
        for button in self.roll_buttons:
            button.draw(canvas, font)
        self.others_button.draw(canvas, font, active=self.others_on)

    def _render_legend(self) -> None:
        """What the guide shows, under the paper and as wide as it: there is no room beside it."""
        x, y = self.area.x, self.area.bottom + 6
        for fill, text in self.legend:
            if fill is not None:
                pygame.draw.rect(self.canvas, fill, (x, y + 1, 9, 9))
                pygame.draw.rect(self.canvas, PALETTE["stone"], (x, y + 1, 9, 9), 1)
            for line in self.font.wrap(text, self.area.width - 14):
                self.font.draw(self.canvas, line, (x + 14, y), PALETTE["bone"])
                y += LINE_HEIGHT
            y += 2

    def _show_drawing(self, screen: pygame.Surface) -> None:
        """The paper: the layers behind the one in hand faintly, it, and the ones in front fainter still."""
        if not self.others_on:
            super()._show_drawing(screen)
            return
        place = self.layers.on_screen(self.area)
        order = [layer.layer_id for layer in self.plan.layers]
        at = order.index(self.layer)
        under = pygame.Surface(self.plan.paper, pygame.SRCALPHA)
        for layer_id in order[:at]:
            under.blit(self._shown(layer_id), (0, 0))
        over = pygame.Surface(self.plan.paper, pygame.SRCALPHA)
        for layer_id in order[at + 1:]:
            over.blit(self._shown(layer_id), (0, 0))
        screen.fill(PAPER, place)
        for picture, alpha in ((under, BEHIND_ALPHA), (None, 255), (over, AHEAD_ALPHA)):
            if picture is None:
                self._show_layer(screen, place)
                continue
            faint = pygame.transform.scale(picture, place.size)
            faint.set_alpha(alpha)
            screen.blit(faint, place)

    def _show_layer(self, screen: pygame.Surface, place: pygame.Rect) -> None:
        """The layer in hand with its guide, as any drawing is shown, over what is already there."""
        if self.guide == GUIDE_UNDER:
            self.guide_picture.set_alpha(GUIDE_ALPHA[GUIDE_UNDER])
            screen.blit(pygame.transform.scale(self.guide_picture, place.size), place)
        picture = self.drawing
        if self._draft is not None:
            picture = self._draft.shown_on(picture, self.color, self.size, self.filled)
        screen.blit(pygame.transform.scale(picture, place.size), place)
        if self.guide == GUIDE_OVER:
            self.guide_picture.set_alpha(GUIDE_ALPHA[GUIDE_OVER])
            screen.blit(pygame.transform.scale(self.guide_picture, place.size), place)

    def _strips(self, height: int) -> list[Strip]:
        """Every layer as it stands on the papers, at the size that fills a height."""
        size = self.backdrops.size_for(height)
        strips = []
        for layer in self.plan.layers:
            strips.append(Strip(layer, pygame.transform.scale(self._shown(layer.layer_id), size), 0))
        return strips

    def _show_preview(self, screen: pygame.Surface) -> None:
        """The whole of it going by, as it will out there, with somebody walking in it."""
        place = self.layers.on_screen(PREVIEW)
        strips = self._strips(place.height)
        detail = self.plan.figure * place.height / BODY_TALL
        strides = self.time * STRIDES
        gone_by = strides * TILES_PER_STRIDE * TILE_SIZE * detail
        before = screen.get_clip()
        screen.set_clip(place)
        screen.fill(PALETTE["shadow"], place)
        draw_strips(screen, strips, place, gone_by, front=False)
        feet = (place.x + round(place.width * AHEAD), place.y + round(place.height * self.plan.ground))
        walker = self.walker(self.resident_id) if self.walker is not None else None
        if walker is not None:
            doll, plan, clip, rate = walker
            facing = DOLL_FACINGS["right"]
            if self._body is None or self._body.plan is not plan:
                self._body = Character(plan)
            self._body.stand(0.0, 0.0, facing, clip, strides * rate % 1.0)
            key = (id(plan), facing)
            if key not in self._skeletons:
                self._skeletons = {key: Skeleton(plan, facing)}
            skeleton = self._skeletons[key]
            skeleton.set_pose(self._body.local_pose())
            low = doll.standing(plan)[3]
            draw_doll(screen, doll, plan, skeleton, (feet[0], feet[1] - round(low * detail)), detail)
        else:
            # Nobody to show: as much room as somebody takes.
            high = round(self.plan.figure * place.height)
            body = pygame.Rect(0, feet[1] - high, max(4, high // 3), high)
            body.centerx = feet[0]
            pygame.draw.rect(screen, PALETTE["ember"], body, 2)
        draw_strips(screen, strips, place, gone_by, front=True)
        screen.set_clip(before)

    def _hint_rect(self, hint: str | None) -> pygame.Rect | None:
        if hint == "parts":
            return self.layer_buttons[0].rect.unionall([button.rect for button in self.layer_buttons])
        return super()._hint_rect(hint)

