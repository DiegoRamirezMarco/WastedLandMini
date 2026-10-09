"""Everything round the map: the bar on top, the menu on the left and the panel on the right, and what
opens over it: the panels of the menu, and the notices of what waits for the player."""

from collections.abc import Hashable, Iterable
from dataclasses import dataclass

import pygame

from graphics.assets import AssetStore
from graphics.coin_art import CoinArt
from graphics.face_renderer import FaceRenderer
from graphics.font import LINE_HEIGHT, BitmapFont
from graphics.icons import ICON_SIZE, icon_path
from graphics.illustrations import Illustrations
from graphics.item_icons import ICON_SIZE as ITEM_ICON_SIZE
from graphics.item_icons import ItemIcons
from graphics.palette import PALETTE
from graphics.screen_layers import ScreenLayers
from graphics.ui_art import GLYPHS, band_hue
from graphics.ui_skin import WindowSkin
from settings import SPEEDS
from simulation.events.event import DomainEvent
from simulation.work.upgrades import UPGRADED_EVENT
from simulation.world import SimulationWorld
from ui.button import HEIGHT as BUTTON_HEIGHT
from ui.button import Button
from ui.event_log import EventFeed
from ui.affect_wheel import (
    AFFECT_INTENT,
    QueueEntry,
    WheelEntry,
    WheelState,
    WheelView,
    draw_queue,
    draw_wheel,
    queue_entries,
    wheel_entries,
    wheel_view,
)
from ui.fund_board import PANEL_WIDTH as FUND_WIDTH
from ui.fund_board import FundEntry, draw_fund_board, field_intent, field_rects, fund_board_height, fund_buttons
from ui.government_board import PANEL_WIDTH as GOVERNMENT_WIDTH
from ui.government_board import draw_government_board, government_board_height, government_buttons
from ui.law_board import KINDS_TAB, PUNISH_TAB
from ui.punish_board import awaiting
from ui.inventory_view import (
    container_item_hitboxes,
    container_panel_height,
    container_scrap_hitboxes,
    draw_container_panel,
)
from ui.job_board import PANEL_WIDTH as BOARD_WIDTH
from ui.job_board import board_buttons, draw_job_board, job_board_height
from ui.labels import (
    COIN_ICON,
    away_residents,
    describe_date,
    describe_weather,
    known_forecasts,
    rarity_name,
    settlement_stock,
)
from ui.layout import Layout, layout_for
from ui.object_panel import STORE_HEADING, ObjectView, draw_object_view, object_view
from ui.power_board import PANEL_WIDTH as POWER_WIDTH
from ui.power_board import POWER_INTENT, draw_power_board, power_board_height, power_buttons
from ui.research_board import PANEL_WIDTH as RESEARCH_WIDTH
from ui.research_board import draw_research_board, research_board_height, study_buttons
from ui.panel import draw_item, draw_panel, set_skin
from ui.resource_bar import Chip, draw_chips, draw_tip, resource_chips, tip_lines, tip_rect
from ui.resident_panel import (
    KIN_TAB,
    LIFE_TAB,
    TASTES_TAB,
    kin_hitbox,
    kin_hitboxes,
    roster_tree_hitbox,
    roster_words_hitbox,
    words_hitbox,
    give_hitbox,
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
from ui.trade_board import PANEL_WIDTH as TRADE_WIDTH
from ui.trade_board import BUY, chosen, draw_trade_board, goods_rows, trade_board_height, trade_buttons
from ui.tutorial_panel import PANEL_WIDTH as TUTORIAL_WIDTH
from ui.words_board import (
    ASKED,
    ONE,
    WORDS_INTENT,
    WORDS_WIDTH,
    WordsEntry,
    ask_intent,
    draw_words_board,
    words_board_height,
    words_buttons,
    words_field_rects,
    write_intent,
)
from ui.tutorial_panel import draw_tutorial, tutorial_button, tutorial_height

MARGIN = 6
# What has been going on is read here and nowhere else, so it is given room for whole lines.
LOG_SIZE = (340, 232)
STORES_WIDTH = 214
OUTLOOK_WIDTH = 300
OUTLOOK_PADDING = 4
# Rows of the menu on the left: compact enough for the game and editor controls together. Each
# is the tile of its icon over a word, and the entries that are not of the settlement stand a
# little apart from the ones that are.
MENU_ROW = 28
MENU_TOP = 2
MENU_TILE = 18
MENU_GAP = 4
# How large the icons of the bar on top are shown.
TOP_ICON = 11
# The icon a figure of the bar goes by when the game has no picture by the name it was given.
PLAIN_ICON = "scrap"
# The longest a date is in the plaque at the head of the bar, which is made wide enough for it.
WIDEST_DATE = "28 sep 2226"
# The plate behind the entry of the menu that is open, and behind the one the pointer is on.
MENU_OPEN = ((58, 74, 90), PALETTE["lamp"])
MENU_POINTED = ((46, 59, 72), (96, 120, 132))

PAUSE_INTENT = ("pause",)
LOG_INTENT = ("log",)
JOBS_INTENT = ("jobs",)
STORES_INTENT = ("stores",)
RESEARCH_INTENT = ("research",)
GOVERNMENT_INTENT = ("government",)
DISCOVERY_INTENT = ("discovery",)
# What is pressed to hear out a resident who wants a word of the player (P62).
ASK_NOTICE = "{name} te pregunta algo"
DISCOVERY_ONE = "{name} sabe algo nuevo: ponle nombre"
DISCOVERY_MANY = "{count} cosas nuevas por nombrar"
DISCOVERY_FOUND = "Hay algo que nadie conoce: ponle nombre"
FUND_INTENT = ("fund_board",)
ROSTER_INTENT = ("roster",)
MINIMAP_INTENT = ("minimap",)
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
    "urbanism": URBANISM_INTENT, "jobs": JOBS_INTENT, "research": RESEARCH_INTENT,
}
CLOCK_FOCUS = "clock"
STORES_TITLE = "Almacén: lo que es de todos"
SENTENCE_HINT = "! {name}, culpable: di qué se le da en Gobierno, Castigos"
AWAY_LABEL = "Fuera"
STORES_EMPTY = "No queda nada"
# What is everybody's can be put in the hands of whoever is selected, a unit at a time (P65).
GIVE_LABEL = "Dar"
GIVE_TO = "Lo que pulses se le da a {name}."
GIVE_NOBODY = "Elige a alguien y podrás darle de esto."
GIVE_OPEN_INTENT = ("give_open",)
STORES_BAND = MARGIN + LINE_HEIGHT - 1


def speed_intent(speed: int) -> tuple[str, int]:
    return ("speed", speed)


# Switches the lower part of a resident's panel between how they live and what they like.
PANEL_TAB_INTENT = "panel_tab"
# Turns a resident's panel to who they are and whose, and back.
PANEL_KIN_INTENT = "panel_kin"
# Asks for the families of the whole settlement, on a screen of their own.
FAMILY_INTENT = ("family",)
# What the player answers when asked whether to draw anew what has just been made better.
REDRAW_YES_INTENT = ("redraw_ask", True)
REDRAW_NO_INTENT = ("redraw_ask", False)
REDRAW_ASK = "{name}, ahora {rarity}: ¿lo dibujas como se ve?"
REDRAW_YES, REDRAW_NO = "Dibujar", "Ahora no"
# Shows the figures behind a resident's tastes, which the game otherwise keeps to itself. Not for play.
TASTE_DEBUG_INTENT = "taste_debug"


def resource_intent(resource_id: str) -> tuple[str, str]:
    """A press on one of the figures of the bar on top."""
    return ("resource", resource_id)


def select_intent(resident_id: str) -> tuple[str, str]:
    return ("select", resident_id)


def edit_item_intent(definition_id: str) -> tuple[str, str]:
    return ("edit_item", definition_id)


def scrap_intent(instance_id: str) -> tuple[str, str]:
    return ("scrap", instance_id)


def give_intent(definition_id: str) -> tuple[str, str]:
    return ("give", definition_id)


@dataclass(frozen=True)
class RedrawAsk:
    """Something that has just been made better, which the player may draw as it looks now."""

    kind: str
    level: int
    text: str


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
        place = pygame.Rect(self.rect.centerx - MENU_TILE // 2, self.rect.y + 1, MENU_TILE, MENU_TILE)
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
        self.fund_open = False
        self.power_open = False
        # The board of words (P62), and what the player is at on it: what it shows, and what
        # is being written there.
        self.words_open = False
        self.words_entry = WordsEntry()
        # What the player is in the middle of on the board of the fund: a currency being named
        # to put to everyone, going back to barter, or another name for the one there is.
        self.fund_entry: FundEntry | None = None
        # The settlement's coin, as somebody drew it or as the game does.
        self.coins = CoinArt(illustrations)
        # Dealing with whoever has stopped by the gate: what of theirs is being bought and what
        # of the settlement's sold, as units by item ID, until the deal is closed.
        self.trade_open = False
        self.trade_buy: dict[str, int] = {}
        self.trade_sell: dict[str, int] = {}
        # Whether there is somewhere to keep drawings, and so whoever comes can be drawn.
        self.drawable = drawable
        # The kind of government the player has pressed for once, and has to press for again.
        self.government_armed: str | None = None
        # The tab of the government's panel that is open, and what has been picked of each law
        # there before it is put: how far it goes, and what it names.
        self.government_tab = KINDS_TAB
        self.law_degrees: dict[str, int] = {}
        self.law_items: dict[str, str] = {}
        # The harsh punishment that has been pressed for once, as a trial and a punishment,
        # and has to be pressed for again (P64).
        self.sentence_armed: tuple[str, str] | None = None
        # The wheel of what the player can tell whoever is selected, while it is open about
        # them: what has been chosen in it so far, and where on the map they stand.
        self.wheel = WheelState()
        # Where the pointer is, for what lights up under it.
        self.pointer: tuple[int, int] | None = None
        # The figures of the bar on top, as last laid out: what there is of each thing, and how it stands.
        self.chips: list[Chip] = []
        # At most one of these is set: the resident or the thing whose panel is showing.
        self.selected_id: str | None = None
        self.selected_object: str | None = None
        # What has just been made better and can be drawn anew, until the player says whether to.
        self.redraw: RedrawAsk | None = None
        # Which of its two faces a resident's panel is showing. It stays as it is from one resident to the next.
        self.panel_tab = LIFE_TAB
        # Whether the tastes are shown with the figures behind them, for looking under the bonnet.
        self.taste_debug = False
        # Whoever is selected and the words in the bubble over them, as the scene last drew
        # it, to be said out loud. None while there are none.
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
        # At the head of the bar, a plaque with the day the settlement is on and its date.
        width = max(sidebar.width - 4, font.width(WIDEST_DATE) + 8)
        self.plaque = pygame.Rect(top.x + 2, top.y + 2, width, top.height - 4)
        self.clock_left = max(sidebar.right, self.plaque.right) + MARGIN
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
            ("energy", "Corriente", POWER_INTENT),
            ("government", "Gobierno", GOVERNMENT_INTENT),
            ("fund", "Fondo", FUND_INTENT),
            ("events", "Eventos", LOG_INTENT),
            ("map", "Mapa", MINIMAP_INTENT),
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
            if intent == URBANISM_INTENT:
                self.menu_rule = y + MENU_GAP // 2
                y += MENU_GAP
            self.menu.append(MenuButton(pygame.Rect(sidebar.x, y, sidebar.width, MENU_ROW), icon, label, intent))
            y += MENU_ROW
        self.jobs_button = next(button for button in self.menu if button.intent == JOBS_INTENT)
        self.log_button = next(button for button in self.menu if button.intent == LOG_INTENT)
        self.research_button = next(button for button in self.menu if button.intent == RESEARCH_INTENT)

    @property
    def buttons(self) -> list[Button | MenuButton | WheelEntry | QueueEntry]:
        """Every button on show, the ones of an open panel included."""
        # The wheel is over everything else, and so is pressed before anything under it.
        fixed = [
            *self.wheel_entries(), *self.queue_entries(),
            self.pause_button, *self.speed_buttons, *self.zoom_buttons, *self.menu,
            *self.object_buttons(), *self.redraw_buttons(),
        ]
        guide = self.tutorial_rect()
        step_button = tutorial_button(self.font, guide, self.world) if guide is not None else None
        if step_button is not None:
            fixed.append(step_button)
        waiting = self.discovery_button()
        if waiting is not None:
            fixed.append(waiting)
        fixed += self.ask_buttons()
        if self.words_open:
            return fixed + words_buttons(self.font, self.words_rect(), self.world, self.words_entry)
        if self.power_open:
            return fixed + power_buttons(self.font, self.power_rect(), self.world)
        if self.research_open:
            return fixed + study_buttons(self.font, self.research_rect(), self.world)
        if self.government_open:
            return fixed + government_buttons(
                self.font, self.government_rect(), self.world, self.government_armed, self.government_tab,
                self.law_degrees, self.law_items, self.sentence_armed,
            )
        if self.fund_open:
            return fixed + fund_buttons(self.font, self.fund_rect(), self.world, self.fund_entry, self.drawable)
        if self.trading:
            return fixed + trade_buttons(
                self.font, self.trade_rect(), self.world, self.trade_buy, self.trade_sell, self.drawable
            )
        if self.stores_open:
            return fixed + self.give_buttons()
        if not self.jobs_open:
            return fixed
        return fixed + board_buttons(self.font, self.jobs_rect(), self.world, self.selected_id)

    def _open_only(self, panel: str) -> None:
        """Open one of the panels that share a corner, or shut it if it is the one open, and shut the rest."""
        for name in (
            "log_open", "jobs_open", "stores_open", "research_open", "government_open", "fund_open", "trade_open",
            "power_open", "words_open",
        ):
            setattr(self, name, name == panel and not getattr(self, name))
        self.fund_entry = None
        self.words_entry = WordsEntry()
        self.government_armed = None
        self.sentence_armed = None
        self.trade_buy, self.trade_sell = {}, {}

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

    def toggle_fund(self) -> None:
        self._open_only("fund_open")

    def open_punishments(self) -> None:
        """Show the government's panel on what is done with whoever is tried (P64)."""
        if not self.government_open:
            self._open_only("government_open")
        self.government_tab = PUNISH_TAB

    def toggle_power(self) -> None:
        self._open_only("power_open")

    def toggle_words(self) -> None:
        """Open the board of words, or shut it: on whoever is selected, if anybody is, and
        otherwise on the words of the settlement."""
        self._open_only("words_open")
        if self.words_open and self.selected_id in self.world.residents:
            self.words_entry = WordsEntry(ONE, resident_id=self.selected_id or "")

    def _tidy_words(self) -> None:
        """Take the board of words back to its lists where what it was showing is no more:
        whoever asked has been let go, or whoever it was about has gone."""
        entry, world = self.words_entry, self.world
        gone = entry.ask_id and world.talk.ask_of(world, entry.ask_id) is None
        gone = gone or (entry.mode == ASKED and not entry.ask_id)
        gone = gone or (entry.resident_id and entry.resident_id not in world.residents)
        gone = gone or (entry.other_id and entry.other_id not in world.residents)
        if gone:
            self.words_entry = WordsEntry()

    def show_words(self, entry: WordsEntry) -> None:
        """Have the board of words show something in particular, opening it if it is shut."""
        if not self.words_open:
            self._open_only("words_open")
        self.words_entry = entry

    @property
    def typing(self) -> bool:
        """Whether what is typed is being written on one of the boards, and so is no shortcut."""
        return (self.fund_open and self.fund_entry is not None and self.fund_entry.written) or self.writing_words

    @property
    def writing_words(self) -> bool:
        """Whether a word, a phrase or a name is being written on the board of words."""
        return self.words_open and self.words_entry.written

    @property
    def trading(self) -> bool:
        """Whether the deal with whoever is at the gate is on show: it is open, and they are still there."""
        return self.trade_open and self.world.merchant is not None

    def open_trade(self) -> None:
        """Show the dealing with whoever has stopped by the gate, in place of whatever else was open there."""
        if self.world.merchant is not None and not self.trade_open:
            self._open_only("trade_open")

    def trade_step(self, side: str, item_id: str, by: int) -> None:
        """Put one more of a thing in the deal, or take one out, within what there is of it."""
        brought, held = goods_rows(self.world, self.trade_buy, self.trade_sell)
        row = next((row for row in (brought if side == BUY else held) if row.item_id == item_id), None)
        if row is None:
            return
        wanted = self.trade_buy if side == BUY else self.trade_sell
        wanted[item_id] = max(0, min(row.units, row.chosen + by))

    def trade_deal(self) -> tuple[dict[str, int], dict[str, int]]:
        """What the deal chosen so far sells and what it buys, as units by item ID."""
        brought, held = goods_rows(self.world, self.trade_buy, self.trade_sell)
        return chosen(held), chosen(brought)

    def wheel_area(self) -> pygame.Rect:
        """The part of the map the wheel is kept within: all of it."""
        return pygame.Rect(self.layout.map)

    def wheel_shown(self) -> WheelView | None:
        """What the wheel shows right now, while it is open about somebody who is there."""
        if not self.wheel.open or self.wheel.about != self.selected_id or self.selected_id not in self.world.residents:
            return None
        return wheel_view(self.world, self.selected_id or "", self.wheel)

    def wheel_entries(self) -> list[WheelEntry]:
        """The buttons of the wheel, where they are, while it is open."""
        view = self.wheel_shown()
        return wheel_entries(self.wheel.centre, self.wheel_area(), view) if view is not None else []

    def queue_entries(self) -> list[QueueEntry]:
        """What whoever is selected has been told to do and has not done, each to be taken back with a press."""
        return queue_entries(self.wheel_area(), self.world, self.selected_id)

    def on_events(self, events: Iterable[DomainEvent]) -> None:
        events = list(events)
        self.feed.add(events)
        for event in events:
            if event.event_type == UPGRADED_EVENT and self.drawable:
                self._ask_to_redraw(event)

    def _ask_to_redraw(self, event: DomainEvent) -> None:
        """A thing has been made better: ask whether it is to be drawn as it looks now."""
        definition = self.world.registries.interactables.find(str(event.data.get("kind", "")))
        if definition is None:
            return
        level = int(event.data.get("level", 1))
        text = REDRAW_ASK.format(name=definition.name.capitalize(), rarity=rarity_name(self.world, level).lower())
        self.redraw = RedrawAsk(definition.kind, level, text)

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

    @property
    def selected_container(self) -> str | None:
        """The thing whose panel is showing, if it is one that things are kept in."""
        return self.selected_object if self.selected_object in self.world.containers else None

    @selected_container.setter
    def selected_container(self, container_id: str | None) -> None:
        self.selected_object = container_id

    def select_resident(self, resident_id: str | None) -> None:
        self.selected_id, self.selected_object = resident_id, None

    def select_object(self, object_id: str | None) -> None:
        """Show what there is to say of a thing that stands, and what it holds."""
        self.selected_id, self.selected_object = None, object_id

    def select_container(self, container_id: str | None) -> None:
        self.select_object(container_id)

    def object_view(self) -> ObjectView | None:
        """What is said of the thing that is selected, laid out at the head of the panel.
        None with none selected, or one with nothing to say but what it holds."""
        if self.selected_object is None:
            return None
        panel = self.layout.panel
        return object_view(self.font, self.world, self.selected_object, panel.topleft, panel.width, self.drawable)

    def object_buttons(self) -> list[Button]:
        view = self.object_view()
        return view.buttons if view is not None else []

    def _container_corner(self) -> tuple[int, int]:
        """Where what the selected thing holds is listed: under what is said of it."""
        view, panel = self.object_view(), self.layout.panel
        return (panel.x, view.rect.bottom if view is not None else panel.y)

    def thing_rect(self) -> pygame.Rect | None:
        """Where the selected thing is shown, while one with anything to show is selected."""
        if self.object_view() is None and self.container_rect() is None:
            return None
        return self.layout.panel

    def toggle_panel_tab(self) -> None:
        """From how they live to what they like, and from any other face back to how they live."""
        self.panel_tab = TASTES_TAB if self.panel_tab == LIFE_TAB else LIFE_TAB

    def toggle_panel_kin(self) -> None:
        self.panel_tab = LIFE_TAB if self.panel_tab == KIN_TAB else KIN_TAB

    def click(self, position: tuple[int, int]) -> Hashable | None:
        """Return the intent of the button, item or resident under `position`."""
        for button in self.buttons:
            if button.contains(position):
                return button.intent
        chip = next((chip for chip in self.chips if chip.contains(position)), None)
        if chip is not None and chip.line is not None:
            # A figure of the bar opens what there is to see of that resource.
            return resource_intent(chip.line.resource_id)
        if self.fund_open:
            fields = field_rects(self.font, self.fund_rect(), self.world, self.fund_entry)
            for field, box in fields.items():
                if box.collidepoint(position):
                    return field_intent(field)
        if self.words_open:
            fields = words_field_rects(self.font, self.words_rect(), self.world, self.words_entry)
            for name, box in fields.items():
                if box.collidepoint(position):
                    return write_intent(name)
        if self.selected_id in self.world.residents and affect_hitbox(self.layout.panel).collidepoint(position):
            return AFFECT_INTENT
        if self.selected_id in self.world.residents and kin_hitbox(self.layout.panel).collidepoint(position):
            return PANEL_KIN_INTENT
        if self.card_rect() is None and self.thing_rect() is None:
            if roster_tree_hitbox(self.layout.panel).collidepoint(position):
                return FAMILY_INTENT
            if roster_words_hitbox(self.layout.panel).collidepoint(position):
                return WORDS_INTENT
        if self.selected_container in self.world.containers:
            marks = container_scrap_hitboxes(
                self._container_corner(), self.world, self.selected_container or "", self.layout.panel.width
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
            and self.panel_tab == LIFE_TAB
            and words_hitbox(self.layout.panel, self.world, self.world.residents[self.selected_id]).collidepoint(position)
        ):
            return WORDS_INTENT
        if (
            self.selected_id in self.world.residents
            and self.panel_tab == TASTES_TAB
            and debug_hitbox(self.layout.panel).collidepoint(position)
        ):
            return TASTE_DEBUG_INTENT
        if (
            self.selected_id in self.world.residents
            and self.panel_tab == LIFE_TAB
            and give_hitbox(self.layout.panel, self.world, self.world.residents[self.selected_id]).collidepoint(position)
        ):
            return GIVE_OPEN_INTENT
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
                self._container_corner(), self.world, self.selected_container or "", self.layout.panel.width
            )
        return []

    def _listed(self) -> list[tuple[pygame.Rect, str]]:
        """Residents named in the panel on the right, each of whom a click there selects."""
        resident = self.world.residents.get(self.selected_id or "")
        if resident is not None and self.panel_tab == KIN_TAB:
            return kin_hitboxes(self.layout.panel, self.world, resident)
        if resident is not None:
            return relationship_hitboxes(self.layout.panel, self.world, resident) if self.panel_tab == LIFE_TAB else []
        if self.thing_rect() is not None:
            return []
        return roster_rows(self.layout.panel, self.world)

    def covers(self, position: tuple[int, int]) -> bool:
        """True if `position` is not on the map, or something of the HUD is in front of the map there."""
        if not self.layout.map.collidepoint(position):
            return True
        panels = [self.minimap_rect, self.outlook_rect(), self.tutorial_rect(), self.redraw_rect()]
        waiting = self.discovery_button()
        panels += [waiting.rect] if waiting is not None else []
        panels += [button.rect for button in self.ask_buttons()]
        panels += [self.words_rect()] if self.words_open else []
        panels += [self.log_rect()] if self.log_open else []
        panels += [self.jobs_rect()] if self.jobs_open else []
        panels += [self.stores_rect()] if self.stores_open else []
        panels += [self.research_rect()] if self.research_open else []
        panels += [self.government_rect()] if self.government_open else []
        panels += [self.fund_rect()] if self.fund_open else []
        panels += [self.power_rect()] if self.power_open else []
        panels += [self.trade_rect()] if self.trading else []
        if any(rect is not None and rect.collidepoint(position) for rect in panels):
            return True
        return any(entry.contains(position) for entry in [*self.wheel_entries(), *self.queue_entries()])

    def _float(self, width: int, height: int) -> pygame.Rect:
        """A panel that opens over the top right corner of the map, no taller than the map is."""
        area = self.layout.map
        return pygame.Rect(area.right - MARGIN - width, area.y + MARGIN, width, min(height, area.height - MARGIN * 2))

    def log_rect(self) -> pygame.Rect:
        return self._float(*LOG_SIZE)

    def jobs_rect(self) -> pygame.Rect:
        return self._float(BOARD_WIDTH, job_board_height(self.world))

    def research_rect(self) -> pygame.Rect:
        return self._float(RESEARCH_WIDTH, research_board_height(self.world, self.font))

    def government_rect(self) -> pygame.Rect:
        return self._float(GOVERNMENT_WIDTH, government_board_height(self.font, self.world, self.government_tab))

    def fund_rect(self) -> pygame.Rect:
        return self._float(FUND_WIDTH, fund_board_height(self.font, self.world, self.fund_entry))

    def power_rect(self) -> pygame.Rect:
        return self._float(POWER_WIDTH, power_board_height(self.world))

    def words_rect(self) -> pygame.Rect:
        return self._float(WORDS_WIDTH, words_board_height(self.font, self.world, self.words_entry))

    def trade_rect(self) -> pygame.Rect:
        return self._float(TRADE_WIDTH, trade_board_height(self.world))

    def stores_rect(self) -> pygame.Rect:
        rows = max(1, len(settlement_stock(self.world)))
        return self._float(STORES_WIDTH, MARGIN * 2 + LINE_HEIGHT * 2 + 6 + rows * (ITEM_ICON_SIZE[1] + 2))

    def _stores_rows(self) -> list[tuple[str, int, pygame.Rect]]:
        """What the Almacén lists that fits in it: the item, how many, and where its row is."""
        rect = self.stores_rect()
        y = rect.y + MARGIN - 1 + LINE_HEIGHT * 2 + 6
        rows = []
        for definition_id, quantity in settlement_stock(self.world):
            row = pygame.Rect(rect.x + MARGIN, y, rect.width - MARGIN * 2, ITEM_ICON_SIZE[1])
            if row.bottom > rect.bottom - 2:
                break
            rows.append((definition_id, quantity, row))
            y += ITEM_ICON_SIZE[1] + 2
        return rows

    def give_buttons(self) -> list[Button]:
        """What is pressed to put a unit of a thing in the hands of whoever is selected: at
        the end of its row in the Almacén, while somebody is."""
        if self.selected_id not in self.world.residents:
            return []
        buttons = []
        for definition_id, _quantity, row in self._stores_rows():
            button = Button.at(self.font, 0, row.y + 1, GIVE_LABEL, give_intent(definition_id))
            button.rect.right = row.right
            buttons.append(button)
        return buttons

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

    def discovery_button(self) -> Button | None:
        """The notice that somebody has come to something that waits to be named, while any
        does: under whatever else is in that corner of the map, to be pressed."""
        waiting = self.world.crafts.waiting(self.world)
        if not waiting:
            return None
        label = (
            (DISCOVERY_FOUND if waiting[0].source else DISCOVERY_ONE.format(name=waiting[0].by_name))
            if len(waiting) == 1
            else DISCOVERY_MANY.format(count=len(waiting))
        )
        area = self.layout.map
        above = self.tutorial_rect() or self.outlook_rect()
        top = above.bottom + MARGIN if above is not None else area.y + MARGIN
        return Button.at(self.font, area.x + MARGIN, top, label, DISCOVERY_INTENT)

    def ask_buttons(self) -> list[Button]:
        """The notices that somebody wants a word of the player, one for each who does (P62):
        under whatever else is in that corner of the map, to be pressed."""
        waiting = [ask for ask in self.world.words.asks if ask.resident_id in self.world.residents]
        if not waiting:
            return []
        area = self.layout.map
        found = self.discovery_button()
        corner = [
            self.outlook_rect(), self.tutorial_rect(), self.away_rect(), self.redraw_rect(),
            found.rect if found is not None else None,
        ]
        top = max((rect.bottom for rect in corner if rect is not None), default=area.y) + MARGIN
        buttons = []
        for ask in waiting:
            label = ASK_NOTICE.format(name=self.world.residents[ask.resident_id].name)
            buttons.append(Button.at(self.font, area.x + MARGIN, top, label, ask_intent(ask.ask_id)))
            top += BUTTON_HEIGHT + 2
        return buttons

    def away_rect(self) -> pygame.Rect | None:
        """Where the faces of whoever is outside the settlement go, while anybody is: in
        the corner of the map, under the forecasts."""
        away = away_residents(self.world)
        if not away:
            return None
        area, outlook = self.layout.map, self.outlook_rect()
        top = (outlook.bottom if outlook is not None else area.top) + MARGIN
        face = self.faces.marker(away[0].resident_id)
        width = self.font.width(AWAY_LABEL) + 8 + (face.get_width() + 2) * len(away)
        return pygame.Rect(area.left + MARGIN, top, width + 4, face.get_height() + 4)

    def redraw_buttons(self) -> list[Button]:
        """What is pressed to draw anew what has just been made better, or to leave it as
        it is, while the player is being asked: under whatever else is in that corner."""
        if self.redraw is None:
            return []
        area = self.layout.map
        waiting = self.discovery_button()
        corner = [self.outlook_rect(), self.tutorial_rect(), self.away_rect(), waiting.rect if waiting is not None else None]
        foot = max((rect.bottom for rect in corner if rect is not None), default=area.y)
        top = foot + MARGIN + OUTLOOK_PADDING + LINE_HEIGHT + 1
        yes = Button.at(self.font, area.x + MARGIN + OUTLOOK_PADDING, top, REDRAW_YES, REDRAW_YES_INTENT)
        return [yes, Button.at(self.font, yes.rect.right + 2, top, REDRAW_NO, REDRAW_NO_INTENT)]

    def redraw_rect(self) -> pygame.Rect | None:
        """Where the player is asked whether to draw anew what has just been made better."""
        buttons = self.redraw_buttons()
        if self.redraw is None or not buttons:
            return None
        left = self.layout.map.x + MARGIN
        width = max(self.font.width(self.redraw.text), buttons[-1].rect.right - buttons[0].rect.left) + OUTLOOK_PADDING * 2
        top = buttons[0].rect.y - LINE_HEIGHT - 1 - OUTLOOK_PADDING
        return pygame.Rect(left, top, width, buttons[0].rect.bottom + OUTLOOK_PADDING - top)

    def card_rect(self) -> pygame.Rect | None:
        """Where the selected resident is shown in full, while one is selected."""
        return self.layout.panel if self.selected_id in self.world.residents else None

    def container_rect(self) -> pygame.Rect | None:
        """Where the contents of the selected container are listed, while one is selected."""
        inventory = self.world.containers.get(self.selected_container or "")
        if inventory is None:
            return None
        panel, corner = self.layout.panel, self._container_corner()
        return pygame.Rect(corner, (panel.width, min(panel.bottom - corner[1], container_panel_height(inventory))))

    def render(self) -> None:
        # Buttons light up under the pointer while it is this that is being drawn.
        self.skin.pointer = self.pointer
        self._render_top()
        self._render_menu()
        self._render_panel()

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
        waiting = self.discovery_button()
        if waiting is not None:
            # It asks to be seen: lit, and unlit, as what the opening points at is.
            waiting.draw(self.canvas, self.font, active=self.lit)
        for button in self.ask_buttons():
            # So does whoever wants a word, until they are given one or told not now.
            button.draw(self.canvas, self.font, active=self.lit)
        asked = self.redraw_rect()
        if asked is not None and self.redraw is not None:
            draw_panel(self.canvas, asked, fill="shadow", border="copper")
            self.font.draw(self.canvas, self.redraw.text, (asked.x + OUTLOOK_PADDING, asked.y + OUTLOOK_PADDING), PALETTE["paper"])
            for button in self.redraw_buttons():
                button.draw(self.canvas, self.font)
        if self.log_open:
            self.feed.draw_panel(self.canvas, self.font, self.log_rect())
        if self.jobs_open:
            draw_job_board(self.canvas, self.font, self.jobs_rect(), self.world, self.selected_id)
        if self.stores_open:
            self._render_stores(self.stores_rect())
        if self.research_open:
            draw_research_board(self.canvas, self.font, self.research_rect(), self.world)
        if self.power_open:
            draw_power_board(self.canvas, self.font, self.power_rect(), self.world)
        if self.words_open:
            self._tidy_words()
            draw_words_board(
                self.canvas, self.font, self.icons, self.faces, self.words_rect(), self.world, self.words_entry, self.lit
            )
        if self.government_open:
            draw_government_board(
                self.canvas, self.font, self.government_rect(), self.world, self.government_armed, band_hue("government"),
                self.government_tab, self.law_degrees, self.law_items, self.sentence_armed,
            )
        if self.fund_open:
            draw_fund_board(
                self.canvas, self.font, self.faces, self.fund_rect(), self.world, self.fund_entry, self.drawable,
                band_hue("fund"), self.show_coin, self.lit,
            )
        if self.trade_open and self.world.merchant is None:
            # They have packed up and gone, and the deal with them.
            self.trade_open, self.trade_buy, self.trade_sell = False, {}, {}
        if self.trading:
            draw_trade_board(
                self.canvas, self.font, self.icons, self.trade_rect(), self.world, self.trade_buy, self.trade_sell,
                self.drawable, band_hue("stores"), self.faces,
            )
        draw_queue(self.canvas, self.font, self.skin, self.queue_entries(), self.pointer)
        tip = self.resource_tip()
        if tip is not None:
            draw_tip(self.canvas, self.font, *tip)
        view = self.wheel_shown()
        if view is not None:
            entries = wheel_entries(self.wheel.centre, self.wheel_area(), view)
            draw_wheel(self.canvas, self.font, self.skin, self.faces, self.world, view, entries, self.pointer)
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
            waits = button.intent == GOVERNMENT_INTENT and not self.government_open and awaiting(self.world) is not None
            if (button.intent == focused or waits) and self.lit:
                # What the opening points at, and the way to somebody waiting to be sentenced.
                pygame.draw.rect(self.canvas, PALETTE["glow"], button.rect, 2)

    def _top_icon(self, name: str, x: int) -> None:
        """One of the icons of the bar on top: as fine as the window shows it, or else the game's own small one."""
        place = pygame.Rect(x, 2, TOP_ICON, TOP_ICON)
        if name not in GLYPHS and name != COIN_ICON and not self.skin.has_own(name):
            # A resource of a pack may name a picture the game has not: it goes by a plain one.
            name = PLAIN_ICON
        if name == COIN_ICON:
            # The fund is counted under the settlement's own coin, as it was drawn.
            self.show_coin(place)
            return
        if self.skin.usable and self.skin.picture(self.canvas, self.skin.icon(name, TOP_ICON * self.layers.scale), place):
            return
        self.canvas.blit(self.assets.image(icon_path(name), size=ICON_SIZE), (x, 3))

    def show_coin(self, place: pygame.Rect) -> None:
        """Put the coin of the currency the settlement has made in a square of the canvas: as
        fine as the window shows it, or else the game's own small one in the middle of it."""
        made = self.world.trading.currency
        if self.skin.usable:
            picture = self.coins.shown(made.currency_id if made is not None else None, place.width * self.layers.scale)
            if self.skin.picture(self.canvas, picture, place):
                return
        small = self.assets.image(icon_path(COIN_ICON), size=ICON_SIZE)
        self.canvas.blit(small, small.get_rect(center=place.center))

    def resource_tip(self) -> tuple[pygame.Rect, list[tuple[str, str]]] | None:
        """What is said of the figure of the bar the pointer rests on, and where: for a resource,
        who makes it and what uses it up. None while it rests on none."""
        if self.pointer is None:
            return None
        chip = next((chip for chip in self.chips if chip.contains(self.pointer)), None)
        if chip is None:
            return None
        lines = tip_lines(self.world, chip)
        return tip_rect(self.font, chip, lines, self.layout.map), lines

    def _menu_active(self, intent: Hashable) -> bool:
        if intent == ROSTER_INTENT:
            return self.card_rect() is None and self.thing_rect() is None
        if intent == MINIMAP_INTENT:
            return self.minimap_rect is not None
        open_panels = {
            JOBS_INTENT: self.jobs_open,
            STORES_INTENT: self.stores_open,
            LOG_INTENT: self.log_open,
            RESEARCH_INTENT: self.research_open,
            GOVERNMENT_INTENT: self.government_open,
            FUND_INTENT: self.fund_open,
            POWER_INTENT: self.power_open,
        }
        return open_panels.get(intent, False)

    def _render_top(self) -> None:
        top, clock = self.layout.top, self.world.clock
        draw_panel(self.canvas, top, border="ink")
        plaque = self.plaque
        draw_panel(self.canvas, plaque, fill="shadow", border="copper")
        day, date = f"Día {clock.day}", describe_date(self.world)
        self.font.draw(self.canvas, day, (plaque.centerx - self.font.width(day) // 2, plaque.y), PALETTE["lamp"])
        self.font.draw(self.canvas, date, (plaque.centerx - self.font.width(date) // 2, plaque.y + 10), PALETTE["bone"])

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

        self.chips = resource_chips(self.font, self.world, self.counts_left, self.counts_right, 2, TOP_ICON)
        draw_chips(self.canvas, self.font, self.chips, self._top_icon, TOP_ICON, self.lit)
        x = self.chips[-1].rect.right + 10 if self.chips else self.counts_left
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
        guilty = awaiting(self.world)
        if self._notice_left > 0:
            self.font.draw(self.canvas, self.font.truncate(self._notice, width), (self.clock_left, 14), PALETTE["glow"])
        elif asker is None and guilty is not None:
            # Somebody found guilty waits for the player to say what they are given (S28).
            name = self.world.residents[guilty.accused].name
            hint = self.font.truncate(SENTENCE_HINT.format(name=name), width)
            self.font.draw(self.canvas, hint, (self.clock_left, 14), PALETTE["lamp"])
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
                self.show_coin,
            )
        elif self.thing_rect() is not None:
            draw_panel(self.canvas, panel)
            view = self.object_view()
            if view is not None:
                draw_object_view(self.canvas, self.font, view)
            if self.container_rect() is not None:
                # Under what is said of it, what it holds.
                draw_container_panel(
                    self.canvas, self.font, self.icons, self._container_corner(), self.world,
                    self.selected_container, panel.width, STORE_HEADING if view is not None else None,
                )
        else:
            draw_roster(self.canvas, self.font, self.faces, panel, self.world)

    def _render_stores(self, rect: pygame.Rect) -> None:
        draw_panel(self.canvas, rect, band=STORES_BAND, band_color=band_hue("stores"))
        x, y = rect.x + MARGIN, rect.y + MARGIN - 1
        self.font.draw(self.canvas, STORES_TITLE, (x, y), PALETTE["paper"])
        y += LINE_HEIGHT + 4
        selected = self.world.residents.get(self.selected_id or "")
        hint = GIVE_TO.format(name=selected.name) if selected is not None else GIVE_NOBODY
        self.font.draw(self.canvas, self.font.truncate(hint, rect.width - MARGIN * 2), (x, y), PALETTE["stone"])
        y += LINE_HEIGHT + 2
        rows = self._stores_rows()
        if not rows:
            self.font.draw(self.canvas, STORES_EMPTY, (x, y + 3), PALETTE["stone"])
        buttons = self.give_buttons()
        room = rect.width - MARGIN * 2 - ITEM_ICON_SIZE[0] - 4 - (buttons[0].rect.width + 4 if buttons else 0)
        for definition_id, quantity, row in rows:
            draw_item(self.canvas, self.icons, definition_id, pygame.Rect(row.topleft, ITEM_ICON_SIZE))
            name = self.world.registries.items.resolve(definition_id).name
            text = self.font.truncate(f"{name} x{quantity}", room)
            self.font.draw(self.canvas, text, (row.x + ITEM_ICON_SIZE[0] + 4, row.y + 3), PALETTE["bone"])
        for button in buttons:
            button.draw(self.canvas, self.font)
