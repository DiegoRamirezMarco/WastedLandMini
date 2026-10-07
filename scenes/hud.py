"""Everything round the map: the bar on top, the menu on the left and the panel on the right, and what
opens over it: the panels of the menu, and the dock of whoever is talking."""

from collections.abc import Hashable, Iterable
from dataclasses import dataclass

import pygame

from graphics.assets import AssetStore
from graphics.face_renderer import FaceRenderer
from graphics.font import LINE_HEIGHT, BitmapFont
from graphics.icons import ICON_SIZE, icon_path
from graphics.illustrations import Illustrations
from graphics.item_icons import ICON_SIZE as ITEM_ICON_SIZE
from graphics.item_icons import ItemIcons
from graphics.palette import PALETTE
from graphics.screen_layers import ScreenLayers
from graphics.ui_art import band_hue
from graphics.ui_skin import WindowSkin
from settings import SPEEDS
from simulation.events.event import DomainEvent
from simulation.residents.resident import Resident
from simulation.world import SimulationWorld
from ui.button import Button
from ui.dock import draw_scene
from ui.event_log import EventFeed
from ui.affect_board import AFFECT_INTENT, affect_board_height, affect_rows, draw_affect_board
from ui.affect_board import PANEL_WIDTH as AFFECT_WIDTH
from ui.government_board import PANEL_WIDTH as GOVERNMENT_WIDTH
from ui.government_board import choose_buttons, draw_government_board, government_board_height
from ui.inventory_view import (
    container_item_hitboxes,
    container_panel_height,
    container_scrap_hitboxes,
    draw_container_panel,
)
from ui.job_board import PANEL_WIDTH as BOARD_WIDTH
from ui.job_board import draw_job_board, job_board_height, suggest_buttons
from ui.labels import (
    FEELING_LABELS,
    describe_action,
    describe_weather,
    expression_of,
    known_forecasts,
    settlement_counts,
    settlement_stock,
    spoken_line,
)
from ui.layout import Layout, layout_for
from ui.research_board import PANEL_WIDTH as RESEARCH_WIDTH
from ui.research_board import draw_research_board, research_board_height, study_buttons
from ui.panel import draw_panel, set_skin
from ui.resident_panel import (
    LIFE_TAB,
    TASTES_TAB,
    draw_resident_panel,
    draw_roster,
    inventory_hitboxes,
    relationship_hitboxes,
    debug_hitbox,
    affect_hitbox,
    manners_hitbox,
    roster_rows,
    tab_hitbox,
)
from ui.tutorial_panel import PANEL_WIDTH as TUTORIAL_WIDTH
from ui.tutorial_panel import draw_tutorial, tutorial_button, tutorial_height

MARGIN = 6
# What has been going on is read here and nowhere else, so it is given room for whole lines.
LOG_SIZE = (340, 232)
STORES_WIDTH = 184
OUTLOOK_WIDTH = 300
OUTLOOK_PADDING = 4
# Rows of the menu on the left: compact enough for the game and editor controls together. Each
# is the tile of its icon over a word, and the entries that are not of the settlement stand a
# little apart from the ones that are.
MENU_ROW = 30
MENU_TOP = 2
MENU_TILE = 18
MENU_GAP = 4
# How large the icons of the bar on top are shown.
TOP_ICON = 11
# The plate behind the entry of the menu that is open, and behind the one the pointer is on.
MENU_OPEN = ((58, 74, 90), PALETTE["lamp"])
MENU_POINTED = ((46, 59, 72), (96, 120, 132))

PAUSE_INTENT = ("pause",)
LOG_INTENT = ("log",)
JOBS_INTENT = ("jobs",)
STORES_INTENT = ("stores",)
RESEARCH_INTENT = ("research",)
GOVERNMENT_INTENT = ("government",)
ROSTER_INTENT = ("roster",)
MINIMAP_INTENT = ("minimap",)
SAVE_INTENT = ("save",)
URBANISM_INTENT = ("urbanism",)
DRAW_INTENT = ("draw",)
BUILD_INTENT = ("draw_building",)
VOICE_INTENT = ("voice",)
MANNERS_INTENT = ("manners",)
ZOOM_OUT_INTENT = ("zoom", -1)
ZOOM_IN_INTENT = ("zoom", 1)
NOTICE_SECONDS = 3.0
# How long what the opening points at stays lit, and then unlit, in seconds.
BLINK_SECONDS = 0.5
# What a step of the opening is about, when it is about one of the entries of the menu.
FOCUS_INTENTS = {
    "urbanism": URBANISM_INTENT, "jobs": JOBS_INTENT, "save": SAVE_INTENT, "research": RESEARCH_INTENT,
}
CLOCK_FOCUS = "clock"
STORES_TITLE = "Almacén: lo que es de todos"
STORES_EMPTY = "No queda nada"
STORES_BAND = MARGIN + LINE_HEIGHT - 1


def speed_intent(speed: int) -> tuple[str, int]:
    return ("speed", speed)


# Switches the lower part of a resident's panel between how they live and what they like.
PANEL_TAB_INTENT = "panel_tab"
# Shows the figures behind a resident's tastes, which the game otherwise keeps to itself. Not for play.
TASTE_DEBUG_INTENT = "taste_debug"


def select_intent(resident_id: str) -> tuple[str, str]:
    return ("select", resident_id)


def edit_item_intent(definition_id: str) -> tuple[str, str]:
    return ("edit_item", definition_id)


def scrap_intent(instance_id: str) -> tuple[str, str]:
    return ("scrap", instance_id)


@dataclass
class MenuButton:
    """An entry of the menu on the left: an icon over a word."""

    rect: pygame.Rect
    icon: str
    label: str
    intent: Hashable

    def contains(self, position: tuple[int, int]) -> bool:
        return self.rect.collidepoint(position)

    def draw(
        self, target: pygame.Surface, font: BitmapFont, skin: WindowSkin, active: bool = False, pointed: bool = False
    ) -> None:
        plate = self.rect.inflate(-4, 0)
        if active or pointed:
            fill, trim = MENU_OPEN if active else MENU_POINTED
            if not skin.plate(target, plate, fill, trim):
                pygame.draw.rect(target, PALETTE["shadow"], plate)
                pygame.draw.rect(target, PALETTE["lamp" if active else "iron"], plate, 1)
        place = pygame.Rect(self.rect.centerx - MENU_TILE // 2, self.rect.y + 2, MENU_TILE, MENU_TILE)
        scale = skin.layers.scale if skin.layers is not None else 1
        lit = active or pointed
        if not skin.picture(target, skin.tile(self.icon, MENU_TILE * scale, lit), place):
            # With no window to show it finer on, the same tile at the size of the canvas.
            target.blit(pygame.transform.smoothscale(skin.tile(self.icon, MENU_TILE * 4, lit), place.size), place)
        left = self.rect.centerx - font.width(self.label) // 2
        # The top of a line of text is room for accents: the word sits close under the tile.
        font.draw(target, self.label, (left, place.bottom - 2), PALETTE["paper" if lit else "bone"])


class Hud:
    def __init__(
        self,
        canvas: pygame.Surface,
        world: SimulationWorld,
        font: BitmapFont,
        icons: ItemIcons,
        faces: FaceRenderer,
        assets: AssetStore,
        illustrations: Illustrations | None = None,
        layers: ScreenLayers | None = None,
        drawable: bool = False,
        voiced: bool = False,
    ) -> None:
        self.canvas = canvas
        self.layers = layers
        self.world = world
        self.font = font
        self.icons = icons
        self.faces = faces
        self.assets = assets
        self.layout: Layout = layout_for(canvas.get_size())
        # Where there is a window under the canvas, everything is dressed at its resolution. The
        # bar, the menu, the panel and the dock, while it is open, are the plates of the frame.
        self.skin = WindowSkin(canvas, layers, illustrations)
        self.skin.parts = {tuple(part) for part in (self.layout.top, self.layout.sidebar, self.layout.panel, self.layout.dock)}
        set_skin(self.skin if self.skin.usable else None)
        # The log, the job board, the stores, what is studied and how the settlement is governed
        # share a corner of the map, so only one of them is open at a time.
        self.log_open = False
        self.jobs_open = False
        self.stores_open = False
        self.research_open = False
        self.government_open = False
        # The kind of government the player has pressed for once, and has to press for again.
        self.government_armed: str | None = None
        # What the player can tell whoever is selected, while they stand stopped to be told: the
        # kind of thing chosen so far, and the thing, on the way to who or what it is about.
        self.affect_open = False
        self.affect_group: str | None = None
        self.affect_kind: str | None = None
        # Where the pointer is, for what lights up under it.
        self.pointer: tuple[int, int] | None = None
        # At most one of these is set: the resident or the container whose panel is showing.
        self.selected_id: str | None = None
        self.selected_container: str | None = None
        # Which of its two faces a resident's panel is showing. It stays as it is from one resident to the next.
        self.panel_tab = LIFE_TAB
        # Whether the tastes are shown with the figures behind them, for looking under the bonnet.
        self.taste_debug = False
        # Who is speaking in the dock and what they say, as last drawn. None while nobody is.
        self.spoken: tuple[str, str] | None = None
        # Where the scene draws its minimap, so that clicks on it do not fall through to the map.
        self.minimap_rect: pygame.Rect | None = None
        self._notice = ""
        self._notice_left = 0.0
        # Real seconds, for the blink of whatever the opening points at.
        self._pulse = 0.0
        importance = world.registries.event_settings.get("importance", {})
        self.intervention_from = int(importance.get("noteworthy_max", 49)) + 1
        self.feed = EventFeed(
            noteworthy_from=int(importance.get("ambient_max", 29)) + 1,
            intervention_from=self.intervention_from,
        )

        top, sidebar = self.layout.top, self.layout.sidebar
        self.clock_left = sidebar.right + MARGIN
        self.pause_button = Button.at(font, self.clock_left + TOP_ICON + 40, 1, "II", PAUSE_INTENT)
        self.speed_buttons: list[Button] = []
        x = self.pause_button.rect.right + 4
        for speed in SPEEDS:
            button = Button.at(font, x, 1, f"x{speed}", speed_intent(speed))
            self.speed_buttons.append(button)
            x = button.rect.right + 2
        self.counts_left = x + 10
        self.zoom_buttons = [
            Button.at(font, 0, 1, "-", ZOOM_OUT_INTENT),
            Button.at(font, 0, 1, "+", ZOOM_IN_INTENT),
        ]
        right = top.right - MARGIN
        for button in reversed(self.zoom_buttons):
            button.rect.right = right
            right = button.rect.left - 2
        self.counts_right = right - 6

        entries = [
            ("people", "Residentes", ROSTER_INTENT),
            ("work", "Puestos", JOBS_INTENT),
            ("study", "Estudio", RESEARCH_INTENT),
            ("stores", "Almacén", STORES_INTENT),
            ("government", "Gobierno", GOVERNMENT_INTENT),
            ("events", "Eventos", LOG_INTENT),
            ("map", "Mapa", MINIMAP_INTENT),
            ("save", "Guardar", SAVE_INTENT),
            ("urbanism", "Urbanismo", URBANISM_INTENT),
        ]
        if drawable:
            # Where there is somewhere to keep drawings, residents can be drawn.
            entries.append(("draw", "Dibujar", DRAW_INTENT))
            entries.append(("buildings", "Edificios", BUILD_INTENT))
        if voiced:
            # And where there are voices to choose from, they can be given one.
            entries.append(("voice", "Voz", VOICE_INTENT))
        self.menu: list[MenuButton] = []
        # Where the line is drawn between what is of the settlement and what is of the game.
        self.menu_rule = 0
        y = sidebar.y + MENU_TOP
        for icon, label, intent in entries:
            if intent == SAVE_INTENT:
                self.menu_rule = y + MENU_GAP // 2
                y += MENU_GAP
            self.menu.append(MenuButton(pygame.Rect(sidebar.x, y, sidebar.width, MENU_ROW), icon, label, intent))
            y += MENU_ROW
        self.jobs_button = next(button for button in self.menu if button.intent == JOBS_INTENT)
        self.log_button = next(button for button in self.menu if button.intent == LOG_INTENT)
        self.research_button = next(button for button in self.menu if button.intent == RESEARCH_INTENT)

    @property
    def buttons(self) -> list[Button | MenuButton]:
        """Every button on show, the ones of an open panel included."""
        fixed = [self.pause_button, *self.speed_buttons, *self.zoom_buttons, *self.menu]
        guide = self.tutorial_rect()
        step_button = tutorial_button(self.font, guide, self.world) if guide is not None else None
        if step_button is not None:
            fixed.append(step_button)
        if self.research_open:
            return fixed + study_buttons(self.font, self.research_rect(), self.world)
        if self.government_open:
            return fixed + choose_buttons(self.font, self.government_rect(), self.world, self.government_armed)
        if self.affect_open and self.selected_id in self.world.residents:
            return fixed + affect_rows(
                self.affect_rect(), self.world, self.selected_id or "", self.affect_group, self.affect_kind
            )
        if not self.jobs_open:
            return fixed
        return fixed + suggest_buttons(self.font, self.jobs_rect(), self.world, self.selected_id)

    def _open_only(self, panel: str) -> None:
        """Open one of the panels that share a corner, or shut it if it is the one open, and shut the rest."""
        for name in ("log_open", "jobs_open", "stores_open", "research_open", "government_open", "affect_open"):
            setattr(self, name, name == panel and not getattr(self, name))
        self.affect_group = self.affect_kind = None
        self.government_armed = None

    def toggle_log(self) -> None:
        self._open_only("log_open")

    def toggle_jobs(self) -> None:
        self._open_only("jobs_open")

    def toggle_stores(self) -> None:
        self._open_only("stores_open")

    def toggle_research(self) -> None:
        self._open_only("research_open")

    def toggle_government(self) -> None:
        self._open_only("government_open")

    def open_affect(self, group: str | None = None, kind: str | None = None) -> None:
        """Show what whoever is selected can be told, in place of whatever else was open there."""
        self.affect_open = False
        self._open_only("affect_open")
        self.affect_group, self.affect_kind = group, kind

    def close_affect(self) -> None:
        self.affect_open, self.affect_group, self.affect_kind = False, None, None

    def on_events(self, events: Iterable[DomainEvent]) -> None:
        self.feed.add(events)

    def notify(self, text: str) -> None:
        """Show a short message from the game itself, such as a save confirmation."""
        self._notice = text
        self._notice_left = NOTICE_SECONDS

    @property
    def notice(self) -> str:
        """The message from the game on show right now, or nothing."""
        return self._notice if self._notice_left > 0 else ""

    def update(self, dt: float) -> None:
        self._notice_left = max(0.0, self._notice_left - dt)
        self._pulse = (self._pulse + dt) % (BLINK_SECONDS * 2)

    @property
    def lit(self) -> bool:
        """The half of a blink in which what the opening points at stands out."""
        return self._pulse < BLINK_SECONDS

    @property
    def focus(self) -> str | None:
        """What the step of the opening the settlement is on is about, if it is on one."""
        step = self.world.guide.current(self.world)
        return step.focus if step is not None else None

    def select_resident(self, resident_id: str | None) -> None:
        self.selected_id, self.selected_container = resident_id, None

    def select_container(self, container_id: str | None) -> None:
        self.selected_id, self.selected_container = None, container_id

    def toggle_panel_tab(self) -> None:
        self.panel_tab = LIFE_TAB if self.panel_tab == TASTES_TAB else TASTES_TAB

    def click(self, position: tuple[int, int]) -> Hashable | None:
        """Return the intent of the button, item or resident under `position`."""
        for button in self.buttons:
            if button.contains(position):
                return button.intent
        if self.selected_id in self.world.residents and affect_hitbox(self.layout.panel).collidepoint(position):
            return AFFECT_INTENT
        if self.selected_container in self.world.containers:
            marks = container_scrap_hitboxes(
                self.layout.panel.topleft, self.world, self.selected_container or "", self.layout.panel.width
            )
            for rect, instance_id in marks:
                if rect.collidepoint(position):
                    return scrap_intent(instance_id)
        if self.selected_id in self.world.residents and tab_hitbox(self.layout.panel).collidepoint(position):
            return PANEL_TAB_INTENT
        if (
            self.selected_id in self.world.residents
            and self.panel_tab == LIFE_TAB
            and manners_hitbox(self.layout.panel).collidepoint(position)
        ):
            return MANNERS_INTENT
        if (
            self.selected_id in self.world.residents
            and self.panel_tab == TASTES_TAB
            and debug_hitbox(self.layout.panel).collidepoint(position)
        ):
            return TASTE_DEBUG_INTENT
        for rect, definition_id in self._inventory_items():
            if rect.collidepoint(position):
                return edit_item_intent(definition_id)
        return next((select_intent(resident_id) for row, resident_id in self._listed() if row.collidepoint(position)), None)

    def _inventory_items(self) -> list[tuple[pygame.Rect, str]]:
        resident = self.world.residents.get(self.selected_id or "")
        if resident is not None:
            # Their things are not on show while the panel is on what they like.
            return inventory_hitboxes(self.layout.panel, self.world, resident) if self.panel_tab == LIFE_TAB else []
        if self.selected_container in self.world.containers:
            return container_item_hitboxes(
                self.layout.panel.topleft, self.world, self.selected_container or "", self.layout.panel.width
            )
        return []

    def _listed(self) -> list[tuple[pygame.Rect, str]]:
        """Residents named in the panel on the right, each of whom a click there selects."""
        resident = self.world.residents.get(self.selected_id or "")
        if resident is not None:
            return relationship_hitboxes(self.layout.panel, self.world, resident) if self.panel_tab == LIFE_TAB else []
        if self.selected_container in self.world.containers:
            return []
        return roster_rows(self.layout.panel, self.world)

    def covers(self, position: tuple[int, int]) -> bool:
        """True if `position` is not on the map, or something of the HUD is in front of the map there."""
        if not self.layout.map.collidepoint(position):
            return True
        panels = [self.minimap_rect, self.outlook_rect(), self.tutorial_rect(), self.dock_rect()]
        panels += [self.log_rect()] if self.log_open else []
        panels += [self.jobs_rect()] if self.jobs_open else []
        panels += [self.stores_rect()] if self.stores_open else []
        panels += [self.research_rect()] if self.research_open else []
        panels += [self.government_rect()] if self.government_open else []
        panels += [self.affect_rect()] if self.affect_open else []
        return any(rect is not None and rect.collidepoint(position) for rect in panels)

    def _float(self, width: int, height: int) -> pygame.Rect:
        """A panel that opens over the top right corner of the map, and stops short of the dock while that is open."""
        area, dock = self.layout.map, self.dock_rect()
        room = (dock.top if dock is not None else area.bottom) - area.y
        return pygame.Rect(area.right - MARGIN - width, area.y + MARGIN, width, min(height, room - MARGIN * 2))

    def log_rect(self) -> pygame.Rect:
        return self._float(*LOG_SIZE)

    def jobs_rect(self) -> pygame.Rect:
        return self._float(BOARD_WIDTH, job_board_height(self.world))

    def research_rect(self) -> pygame.Rect:
        return self._float(RESEARCH_WIDTH, research_board_height(self.world, self.font))

    def government_rect(self) -> pygame.Rect:
        return self._float(GOVERNMENT_WIDTH, government_board_height(self.font, self.world))

    def affect_rect(self) -> pygame.Rect:
        height = affect_board_height(self.world, self.selected_id or "", self.affect_group, self.affect_kind)
        return self._float(AFFECT_WIDTH, height)

    def stores_rect(self) -> pygame.Rect:
        rows = max(1, len(settlement_stock(self.world)))
        return self._float(STORES_WIDTH, MARGIN * 2 + LINE_HEIGHT + 4 + rows * (ITEM_ICON_SIZE[1] + 2))

    def outlook_rect(self) -> pygame.Rect | None:
        """Where the forecasts the settlement has heard are listed, when it has heard any."""
        lines = len(known_forecasts(self.world))
        if not lines:
            return None
        height = OUTLOOK_PADDING * 2 + LINE_HEIGHT * lines
        area = self.layout.map
        return pygame.Rect(area.x + MARGIN, area.y + MARGIN, OUTLOOK_WIDTH, height)

    def tutorial_rect(self) -> pygame.Rect | None:
        """Where the step of the opening is shown, while the settlement is on one: under the forecasts."""
        height = tutorial_height(self.font, self.world, TUTORIAL_WIDTH)
        if not height:
            return None
        area, outlook = self.layout.map, self.outlook_rect()
        top = outlook.bottom + MARGIN if outlook is not None else area.y + MARGIN
        return pygame.Rect(area.x + MARGIN, top, TUTORIAL_WIDTH, height)

    def card_rect(self) -> pygame.Rect | None:
        """Where the selected resident is shown in full, while one is selected."""
        return self.layout.panel if self.selected_id in self.world.residents else None

    def container_rect(self) -> pygame.Rect | None:
        """Where the contents of the selected container are listed, while one is selected."""
        inventory = self.world.containers.get(self.selected_container or "")
        if inventory is None:
            return None
        panel = self.layout.panel
        return pygame.Rect(panel.x, panel.y, panel.width, min(panel.height, container_panel_height(inventory)))

    def render(self) -> None:
        # Buttons light up under the pointer while it is this that is being drawn.
        self.skin.pointer = self.pointer
        self._render_top()
        self._render_menu()
        self._render_panel()
        self._render_dock()

        outlook = self.outlook_rect()
        if outlook is not None:
            draw_panel(self.canvas, outlook)
            for index, line in enumerate(known_forecasts(self.world)):
                text = self.font.truncate(line, outlook.width - OUTLOOK_PADDING * 2)
                position = (outlook.x + OUTLOOK_PADDING, outlook.y + OUTLOOK_PADDING + index * LINE_HEIGHT)
                self.font.draw(self.canvas, text, position, PALETTE["sand"])
        guide = self.tutorial_rect()
        if guide is not None:
            draw_tutorial(self.canvas, self.font, guide, self.world, self.lit)
        if self.log_open:
            self.feed.draw_panel(self.canvas, self.font, self.log_rect())
        if self.jobs_open:
            draw_job_board(self.canvas, self.font, self.jobs_rect(), self.world, self.selected_id)
        if self.stores_open:
            self._render_stores(self.stores_rect())
        if self.research_open:
            draw_research_board(self.canvas, self.font, self.research_rect(), self.world)
        if self.government_open:
            draw_government_board(
                self.canvas, self.font, self.government_rect(), self.world, self.government_armed, band_hue("government")
            )
        if self.affect_open and self.selected_id in self.world.residents:
            draw_affect_board(
                self.canvas, self.font, self.affect_rect(), self.world, self.selected_id or "",
                self.affect_group, self.affect_kind, self.pointer,
            )
        self.skin.pointer = None

    def _render_menu(self) -> None:
        sidebar = self.layout.sidebar
        draw_panel(self.canvas, sidebar, border="ink")
        if self.menu_rule:
            pygame.draw.line(self.canvas, PALETTE["iron"], (sidebar.x + 8, self.menu_rule), (sidebar.right - 9, self.menu_rule))
        focused = FOCUS_INTENTS.get(self.focus or "")
        for button in self.menu:
            pointed = self.pointer is not None and button.contains(self.pointer)
            button.draw(self.canvas, self.font, self.skin, self._menu_active(button.intent), pointed)
            if button.intent == focused and self.lit:
                pygame.draw.rect(self.canvas, PALETTE["glow"], button.rect, 2)

    def _top_icon(self, name: str, x: int) -> None:
        """One of the icons of the bar on top: as fine as the window shows it, or else the game's own small one."""
        place = pygame.Rect(x, 2, TOP_ICON, TOP_ICON)
        if self.skin.usable and self.skin.picture(self.canvas, self.skin.icon(name, TOP_ICON * self.layers.scale), place):
            return
        self.canvas.blit(self.assets.image(icon_path(name), size=ICON_SIZE), (x, 3))

    def _menu_active(self, intent: Hashable) -> bool:
        if intent == ROSTER_INTENT:
            return self.card_rect() is None and self.container_rect() is None
        if intent == MINIMAP_INTENT:
            return self.minimap_rect is not None
        open_panels = {
            JOBS_INTENT: self.jobs_open,
            STORES_INTENT: self.stores_open,
            LOG_INTENT: self.log_open,
            RESEARCH_INTENT: self.research_open,
            GOVERNMENT_INTENT: self.government_open,
        }
        return open_panels.get(intent, False)

    def _render_top(self) -> None:
        top, clock = self.layout.top, self.world.clock
        draw_panel(self.canvas, top, border="ink")
        plaque = pygame.Rect(top.x + 2, top.y + 2, self.layout.sidebar.width - 4, top.height - 4)
        draw_panel(self.canvas, plaque, fill="shadow", border="copper")
        day = f"Día {clock.day}"
        self.font.draw(self.canvas, day, (plaque.centerx - self.font.width(day) // 2, plaque.y + 5), PALETTE["lamp"])

        self._top_icon("moon" if self.world.is_dark() else "sun", self.clock_left)
        hour = f"{clock.hour:02d}:{clock.minute:02d}"
        self.font.draw(self.canvas, hour, (self.clock_left + TOP_ICON + 4, 2), PALETTE["paper"])
        self.pause_button.draw(self.canvas, self.font, active=clock.paused)
        for button, speed in zip(self.speed_buttons, SPEEDS):
            button.draw(self.canvas, self.font, active=clock.speed == speed and not clock.paused)
        for button in self.zoom_buttons:
            button.draw(self.canvas, self.font)
        if self.focus == CLOCK_FOCUS and self.lit:
            controls = self.pause_button.rect.unionall([button.rect for button in self.speed_buttons])
            pygame.draw.rect(self.canvas, PALETTE["glow"], controls.inflate(4, 2), 1)

        x = self.counts_left
        for icon, figure in settlement_counts(self.world):
            self._top_icon(icon, x)
            self.font.draw(self.canvas, figure, (x + TOP_ICON + 3, 2), PALETTE["bone"])
            x += TOP_ICON + 3 + self.font.width(figure) + 10
        weather = describe_weather(self.world)
        if weather is not None and x + self.font.width(weather) < self.counts_right:
            self.font.draw(self.canvas, weather, (self.counts_right - self.font.width(weather), 2), PALETTE["sand"])

        # Under all that, one line: a word from the game, whoever is waiting for advice, or the latest news.
        width = top.right - MARGIN - self.clock_left
        waiting = next(iter(self.world.decisions.values()), None)
        asker = self.world.residents.get(waiting.resident_id) if waiting is not None else None
        builder = next(
            (
                resident
                for resident in self.world.residents.values()
                if self.world.construction.waiting_for_material(self.world, resident) is not None
            ),
            None,
        )
        if self._notice_left > 0:
            self.font.draw(self.canvas, self.font.truncate(self._notice, width), (self.clock_left, 14), PALETTE["glow"])
        elif asker is None and builder is not None:
            # Somebody sits by a site with nothing to build with: they can be told what to take apart.
            hint = self.font.truncate(f"! {builder.name} pide material: selecciónale y pulsa Afectar", width)
            self.font.draw(self.canvas, hint, (self.clock_left, 14), PALETTE["lamp"])
        elif asker is not None:
            hint = self.font.truncate(f"! {asker.name} necesita consejo: TAB o clic", width)
            self.font.draw(self.canvas, hint, (self.clock_left, 14), PALETTE["lamp"])
        else:
            self.feed.draw_ticker(self.canvas, self.font, (self.clock_left, 14), width)

    def _render_panel(self) -> None:
        panel = self.layout.panel
        resident = self.world.residents.get(self.selected_id or "")
        if resident is not None:
            draw_resident_panel(
                self.canvas,
                self.font,
                self.icons,
                self.faces,
                self.assets,
                panel,
                self.world,
                resident,
                self.layers,
                self.panel_tab,
                self.taste_debug,
            )
        elif self.container_rect() is not None:
            draw_panel(self.canvas, panel)
            draw_container_panel(self.canvas, self.font, self.icons, panel.topleft, self.world, self.selected_container, panel.width)
        else:
            draw_roster(self.canvas, self.font, self.faces, panel, self.world)

    def _exchange(self) -> tuple[Resident, Resident] | None:
        """Whoever is selected and whoever they are in an exchange with, while they are in one."""
        resident = self.world.residents.get(self.selected_id or "")
        activity = resident.activity if resident is not None else None
        partner = self.world.residents.get(activity.partner_id or "") if activity is not None and activity.using else None
        if resident is None or partner is None or resident.away:
            return None
        return resident, partner

    def dock_rect(self) -> pygame.Rect | None:
        """Where the exchange of whoever is selected is shown, while they are in one. The rest of the
        time nothing is there but the map."""
        return self.layout.dock if self._exchange() is not None else None

    def _render_dock(self) -> None:
        """Over the foot of the map: the exchange the selected resident is in, while they are in one."""
        dock, exchange = self.layout.dock, self._exchange()
        if exchange is None:
            self.spoken = None
            return
        resident, partner = exchange
        # They take turns to speak, a few minutes each.
        turn = (self.world.clock.total_minutes // 4) % 2
        speaker = resident if turn == 0 else partner
        line = spoken_line(self.world, speaker)
        self.spoken = (speaker.resident_id, line) if line else None
        areas = draw_scene(
            self.canvas,
            self.font,
            self.faces,
            dock,
            (resident.resident_id, expression_of(self.world, resident), resident.name),
            (partner.resident_id, expression_of(self.world, partner), partner.name),
            line or "...",
            speaker=-1 if turn == 0 else 1,
            layers=self.layers,
        )
        x, y = areas.side.x, areas.side.y
        lines = [(f"{resident.name} {describe_action(self.world, resident)}", "paper")]
        for one, other in ((resident, partner), (partner, resident)):
            feelings = self.world.relationships.get((one.resident_id, other.resident_id))
            felt = ", ".join(
                f"{label} {round(getattr(feelings, feeling)) if feelings is not None else 0}"
                for feeling, label in FEELING_LABELS.items()
            )
            lines.append((f"{one.name} por {other.name}: {felt}", "bone"))
        for text, color in lines:
            for line in self.font.wrap(text, areas.side.width):
                self.font.draw(self.canvas, line, (x, y), PALETTE[color])
                y += LINE_HEIGHT
            y += 2

    def _render_stores(self, rect: pygame.Rect) -> None:
        draw_panel(self.canvas, rect, band=STORES_BAND, band_color=band_hue("stores"))
        x, y = rect.x + MARGIN, rect.y + MARGIN - 1
        self.font.draw(self.canvas, STORES_TITLE, (x, y), PALETTE["paper"])
        y += LINE_HEIGHT + 4
        stock = settlement_stock(self.world)
        if not stock:
            self.font.draw(self.canvas, STORES_EMPTY, (x, y + 3), PALETTE["stone"])
        for definition_id, quantity in stock:
            if y + ITEM_ICON_SIZE[1] > rect.bottom - 2:
                break
            self.canvas.blit(self.icons.icon(definition_id), (x, y))
            name = self.world.registries.items.resolve(definition_id).name
            text = self.font.truncate(f"{name} x{quantity}", rect.width - MARGIN * 2 - ITEM_ICON_SIZE[0] - 4)
            self.font.draw(self.canvas, text, (x + ITEM_ICON_SIZE[0] + 4, y + 3), PALETTE["bone"])
            y += ITEM_ICON_SIZE[1] + 2
