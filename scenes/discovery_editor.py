"""Where the player says what a resident has come to at their job is (P54): they draw it, name
it, and pick from what its kind lets be picked. What it is like otherwise is the game's to say.

It is the item editor's paper and tools with other things beside them: a name, and a drop-down
list for each thing there is to pick. Nothing is the thing's until it is saved here; left
without saving, it waits to be named another time.
"""

from pathlib import Path

import pygame

from graphics.font import FONT_CHARS, LINE_HEIGHT, BitmapFont
from graphics.item_icons import ItemIcons
from graphics.palette import PALETTE
from graphics.screen_layers import TRANSPARENT, ScreenLayers
from scenes.item_editor import ART_AREA, ART_SIZE, ERASER_TOOL, TOOLS_LEFT, ItemEditor
from simulation.commands import NameDiscoveryCommand
from simulation.work.craft import Discovery, KindDefinition, OptionDefinition
from simulation.world import SimulationWorld
from ui.panel import draw_panel

# The folder of `custom_content/` the pictures of what was come to are kept in, by item ID.
MADE_FOLDER = "made"
FIELDS_LEFT = 470
FIELD_WIDTH = 300
NAME_FIELD = pygame.Rect(FIELDS_LEFT, 84, FIELD_WIDTH, 16)
CHOICES_TOP = 130
# A choice takes a line for what it is called, its box, and two lines for what the pick does.
CHOICE_STEP = 16 + LINE_HEIGHT * 3 + 10
OPTION_ROW = LINE_HEIGHT + 3
SAVE_LABEL = "Guardar"
LATER_LABEL = "Luego"
NAME_LABEL = "Nombre"
NAMELESS = "Hace falta un nombre"
NOT_DRAWN = "Un sitio no se dibuja: basta con su nombre y lo que se trae de allí."
GAME_DECIDES = "Lo demás lo pone el juego: lo que alimenta, lo que vale y a qué sabe."
PLACE_DECIDES = "Lo demás lo pone el juego: cuánto se trae y lo que se arriesga."
WAITS = "Si lo dejas para luego, nadie lo hace hasta que le pongas nombre."
ICON_LABEL = "Dibújalo"


class DiscoveryEditor(ItemEditor):
    """Name and draw one thing somebody has come to. Simulation time stands still while it is open."""

    def __init__(
        self,
        canvas: pygame.Surface,
        world: SimulationWorld,
        font: BitmapFont,
        root: Path,
        icons: ItemIcons,
        layers: ScreenLayers,
    ) -> None:
        super().__init__(canvas, world, font, root, icons, layers)
        self.discovery_id: str | None = None
        self.name = ""
        # What has been picked for each choice, by choice ID, and the choice whose list is open.
        self.picked: dict[str, str] = {}
        self.open_choice: str | None = None
        # The ID of the item that was made of it, once it has been saved.
        self.made: str | None = None
        self.top_buttons = self._row(6, [(SAVE_LABEL, ("save",)), (LATER_LABEL, ("close",))], left=610)
        # None of the item editor's fields: what a thing is like is the game's to say.
        self.field_rects = {}
        self._blink = 0.0

    # ----- what is being named -----

    @property
    def discovery(self) -> Discovery | None:
        return self.world.discoveries.get(self.discovery_id or "")

    @property
    def kind(self) -> KindDefinition | None:
        discovery = self.discovery
        return self.world.registries.crafts.kinds.get(discovery.kind) if discovery is not None else None

    @property
    def drawn(self) -> bool:
        """Whether what is being named is a thing, and so has a picture."""
        kind = self.kind
        return kind is not None and kind.item is not None

    def options(self) -> dict[str, list[OptionDefinition]]:
        discovery = self.discovery
        return self.world.crafts.options(self.world, discovery) if discovery is not None else {}

    def open(self, discovery_id: str) -> None:
        """Start from a blank: no name, the first of everything there is to pick, and clean paper."""
        self.discovery_id = discovery_id
        self.item_id = None
        self.made = None
        self.closed = False
        self.notice = ""
        self.name = ""
        self.active_field = "name"
        self.open_choice = None
        self._undo = []
        self._stroke = None
        self.picture = pygame.Surface(ART_SIZE, pygame.SRCALPHA)
        self.picture.fill(TRANSPARENT)
        self.picked = {choice_id: options[0].option_id for choice_id, options in self.options().items() if options}
        discovery = self.discovery
        if discovery is None or discovery.named:
            # Nothing to name: somebody else did, or whoever came to it is gone.
            self.closed = True

    def set_name(self, name: str) -> None:
        length = self.world.registries.crafts.name_length
        self.name = "".join(char for char in name if char in FONT_CHARS)[:length]
        self.notice = ""

    def pick(self, choice_id: str, option_id: str) -> None:
        if any(option.option_id == option_id for option in self.options().get(choice_id, [])):
            self.picked[choice_id] = option_id
        self.open_choice = None

    def picked_option(self, choice_id: str) -> OptionDefinition | None:
        return next(
            (option for option in self.options().get(choice_id, []) if option.option_id == self.picked.get(choice_id)),
            None,
        )

    # ----- where things are -----

    def choice_boxes(self) -> dict[str, pygame.Rect]:
        """The box of each choice, which shows what is picked and opens its list."""
        kind = self.kind
        if kind is None:
            return {}
        return {
            choice_id: pygame.Rect(FIELDS_LEFT, CHOICES_TOP + index * CHOICE_STEP + LINE_HEIGHT + 1, FIELD_WIDTH, 16)
            for index, choice_id in enumerate(kind.choices)
        }

    def option_boxes(self) -> list[tuple[pygame.Rect, str]]:
        """The rows of the list that is open, under its box, and the option each is."""
        box = self.choice_boxes().get(self.open_choice or "")
        if box is None:
            return []
        options = self.options().get(self.open_choice or "", [])
        room = (self.canvas.get_height() - 8 - box.bottom) // OPTION_ROW
        return [
            (pygame.Rect(box.x, box.bottom + index * OPTION_ROW, box.width, OPTION_ROW), option.option_id)
            for index, option in enumerate(options[:room])
        ]

    # ----- saving -----

    def save(self) -> bool:
        """Say what it is, and keep its picture. Returns whether the settlement took it."""
        discovery = self.discovery
        if discovery is None:
            self.closed = True
            return False
        if not self.name.strip():
            self.notice = NAMELESS
            return False
        result = self.world.apply_command(NameDiscoveryCommand(discovery.discovery_id, self.name, dict(self.picked)))
        if not result.ok:
            self.notice = result.message
            return False
        self.made = discovery.item_id
        if discovery.item_id is not None:
            try:
                folder = self.root / MADE_FOLDER / discovery.item_id
                folder.mkdir(parents=True, exist_ok=True)
                pygame.image.save(self.picture, str(folder / "icon.png"))
            except (OSError, pygame.error) as error:
                # It is named all the same: only its picture is the game's plain one.
                self.notice = f"Tiene nombre, pero no se pudo guardar el dibujo: {error}"
            self.icons.forget(discovery.item_id)
        self.closed = True
        return True

    # ----- input -----

    def press(self, position: tuple[int, int]) -> None:
        for box, option_id in self.option_boxes():
            if box.collidepoint(position):
                self.pick(self.open_choice or "", option_id)
                return
        was_open, self.open_choice = self.open_choice, None
        for choice_id, box in self.choice_boxes().items():
            if box.collidepoint(position):
                self.open_choice = None if was_open == choice_id else choice_id
                self.active_field = None
                return
        if NAME_FIELD.collidepoint(position):
            self.active_field = "name"
            return
        if ART_AREA.collidepoint(position) and not self.drawn:
            return
        super().press(position)
        # Whatever was pressed, what is typed is still the name.
        self.active_field = "name"

    def _type(self, event: pygame.event.Event) -> None:
        if event.key == pygame.K_BACKSPACE:
            self.set_name(self.name[:-1])
        elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
            self.save()
        elif event.key not in (pygame.K_TAB, pygame.K_ESCAPE):
            self.set_name(self.name + getattr(event, "unicode", ""))

    def update(self, dt: float) -> None:
        self._blink = (self._blink + dt) % 1.0

    # ----- drawing it -----

    def render(self) -> None:
        self.layers.clear()
        font, canvas = self.font, self.canvas
        canvas.fill(PALETTE["ink"])
        discovery, kind = self.discovery, self.kind
        if discovery is None or kind is None:
            return
        job = self.world.registries.jobs.get(discovery.job_id)
        font.draw(canvas, kind.ask or f"¿Qué {kind.name} es?", (TOOLS_LEFT, 4), PALETTE["glow"], scale=2)
        where = f", nivel {discovery.level} de {job.name.lower()}" if job is not None else ""
        said = self.notice or f"{discovery.by_name}{where}. {WAITS}"
        font.draw(canvas, font.truncate(said, 590), (TOOLS_LEFT, 30), PALETTE["lamp" if self.notice else "stone"])
        for button in self.top_buttons:
            button.draw(canvas, font, active=button.intent == ("save",) and bool(self.name.strip()))

        if self.drawn:
            self._render_paper()
        else:
            for index, line in enumerate(font.wrap(NOT_DRAWN, ART_AREA.width)):
                font.draw(canvas, line, (ART_AREA.x, ART_AREA.y + index * LINE_HEIGHT), PALETTE["dust"])

        font.draw(canvas, NAME_LABEL, (NAME_FIELD.x, NAME_FIELD.y - LINE_HEIGHT - 1), PALETTE["sand"])
        draw_panel(canvas, NAME_FIELD, fill="shadow", border="lamp" if self.active_field == "name" else "iron")
        caret = "_" if self._blink < 0.5 and self.active_field == "name" else ""
        font.draw(canvas, self.name + caret, (NAME_FIELD.x + 4, NAME_FIELD.y + 3), PALETTE["paper"])

        boxes = self.choice_boxes()
        y = CHOICES_TOP
        for choice_id, choice in kind.choices.items():
            box = boxes[choice_id]
            option = self.picked_option(choice_id)
            font.draw(canvas, choice.name, (box.x, box.y - LINE_HEIGHT - 1), PALETTE["sand"])
            draw_panel(canvas, box, fill="shadow", border="lamp" if self.open_choice == choice_id else "iron")
            label = option.name if option is not None else "-"
            font.draw(canvas, font.truncate(label, box.width - 20), (box.x + 4, box.y + 3), PALETTE["paper"])
            font.draw(canvas, "v", (box.right - 10, box.y + 3), PALETTE["lamp"])
            if option is not None and self.open_choice is None:
                for index, line in enumerate(font.wrap(option.text, box.width)[:2]):
                    font.draw(canvas, line, (box.x, box.bottom + 2 + index * LINE_HEIGHT), PALETTE["dust"])
            y = box.bottom + LINE_HEIGHT * 2 + 10
        note = GAME_DECIDES if self.drawn else PLACE_DECIDES
        if self.open_choice is None:
            for index, line in enumerate(font.wrap(note, FIELD_WIDTH)):
                font.draw(canvas, line, (FIELDS_LEFT, y + 6 + index * LINE_HEIGHT), PALETTE["stone"])
        # The list that is open is drawn last, over whatever is under it.
        rows = self.option_boxes()
        if rows:
            whole = rows[0][0].unionall([row for row, _ in rows])
            draw_panel(canvas, whole.inflate(2, 2), fill="ink", border="lamp")
            options = {option.option_id: option for option in self.options().get(self.open_choice or "", [])}
            for row, option_id in rows:
                chosen = self.picked.get(self.open_choice or "") == option_id
                if chosen:
                    pygame.draw.rect(canvas, PALETTE["shadow"], row)
                text = font.truncate(options[option_id].name, row.width - 8)
                font.draw(canvas, text, (row.x + 4, row.y + 1), PALETTE["glow" if chosen else "bone"])

    def _render_paper(self) -> None:
        """The paper and the tools to draw on it with, as the item editor has them."""
        font, canvas = self.font, self.canvas
        font.draw(canvas, "Color", (TOOLS_LEFT, 58), PALETTE["dust"])
        for rect, color in self.swatches:
            pygame.draw.rect(canvas, color, rect.inflate(-2, -2))
            if color == self.color and self.tool != ERASER_TOOL:
                pygame.draw.rect(canvas, PALETTE["paper"], rect, 1)
        for rect, size in self.brush_buttons:
            draw_panel(canvas, rect, fill="shadow", border="lamp" if size == self.size else "iron")
            pygame.draw.circle(canvas, PALETTE["bone"], rect.center, max(1, size // 2))
        for button in self.tool_buttons:
            button.draw(canvas, font, active=button.intent == ("tool", self.tool))
        for button in self.edit_buttons:
            button.draw(canvas, font)
        pygame.draw.rect(canvas, PALETTE["bone"], ART_AREA)
        canvas.blit(pygame.transform.scale(self.picture, ART_AREA.size), ART_AREA)
        pygame.draw.rect(canvas, PALETTE["stone"], ART_AREA.inflate(2, 2), 1)
        font.draw(canvas, ICON_LABEL, (ART_AREA.x, ART_AREA.y - LINE_HEIGHT - 2), PALETTE["dust"])
