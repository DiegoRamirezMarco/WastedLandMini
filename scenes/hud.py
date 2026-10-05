"""Everything round the map: the bar on top, the menu on the left, the panel on the right and the dock below."""

from collections.abc import Hashable, Iterable
from dataclasses import dataclass

import pygame

from graphics.assets import AssetStore
from graphics.face_renderer import FaceRenderer
from graphics.font import LINE_HEIGHT, BitmapFont
from graphics.icons import ICON_SIZE, icon_path
from graphics.illustrations import Illustrations, nine_slice
from graphics.item_icons import ICON_SIZE as ITEM_ICON_SIZE
from graphics.item_icons import ItemIcons
from graphics.palette import PALETTE
from graphics.screen_layers import TRANSPARENT, ScreenLayers
from settings import SPEEDS
from simulation.events.event import DomainEvent
from simulation.world import SimulationWorld
from ui.button import Button
from ui.dock import draw_scene
from ui.event_log import EventFeed
from ui.inventory_view import container_panel_height, draw_container_panel
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
from ui.panel import draw_panel, set_skin
from ui.resident_panel import draw_resident_panel, draw_roster, relationship_hitboxes, roster_rows

MARGIN = 6
LOG_SIZE = (250, 168)
STORES_WIDTH = 184
OUTLOOK_WIDTH = 300
OUTLOOK_PADDING = 4
# Rows of the menu on the left: an icon at twice its size with a word under it.
MENU_ROW = 34
MENU_ICON_SCALE = 2

PAUSE_INTENT = ("pause",)
LOG_INTENT = ("log",)
JOBS_INTENT = ("jobs",)
STORES_INTENT = ("stores",)
ROSTER_INTENT = ("roster",)
MINIMAP_INTENT = ("minimap",)
ZOOM_OUT_INTENT = ("zoom", -1)
ZOOM_IN_INTENT = ("zoom", 1)
NOTICE_SECONDS = 3.0
STORES_TITLE = "Almacén: lo que es de todos"
STORES_EMPTY = "No queda nada"
DOCK_TITLE = "Lo último"
# The picture that the large parts of the screen wear, if there is one, and how wide its border is drawn.
SKIN_PATH = "ui/panel.png"
SKIN_BORDER_PIXELS = 20


def speed_intent(speed: int) -> tuple[str, int]:
    return ("speed", speed)


def select_intent(resident_id: str) -> tuple[str, str]:
    return ("select", resident_id)


@dataclass
class MenuButton:
    """An entry of the menu on the left: an icon over a word."""

    rect: pygame.Rect
    icon: str
    label: str
    intent: Hashable

    def contains(self, position: tuple[int, int]) -> bool:
        return self.rect.collidepoint(position)

    def draw(self, target: pygame.Surface, font: BitmapFont, assets: AssetStore, active: bool = False) -> None:
        if active:
            pygame.draw.rect(target, PALETTE["shadow"], self.rect)
            pygame.draw.rect(target, PALETTE["lamp"], self.rect, 1)
        size = (ICON_SIZE[0] * MENU_ICON_SCALE, ICON_SIZE[1] * MENU_ICON_SCALE)
        icon = pygame.transform.scale(assets.image(icon_path(self.icon), size=ICON_SIZE), size)
        target.blit(icon, (self.rect.centerx - size[0] // 2, self.rect.y + 3))
        left = self.rect.centerx - font.width(self.label) // 2
        font.draw(target, self.label, (left, self.rect.y + 5 + size[1]), PALETTE["paper" if active else "bone"])


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
    ) -> None:
        self.canvas = canvas
        self.layers = layers
        self.world = world
        self.font = font
        self.icons = icons
        self.faces = faces
        self.assets = assets
        self.layout: Layout = layout_for(canvas.get_size())
        # The bar, the menu, the panel and the dock wear the skin, if the game has been given one.
        self._skin_source = illustrations.find(SKIN_PATH) if illustrations is not None and layers is not None else None
        self._skinned = {tuple(part) for part in (self.layout.top, self.layout.sidebar, self.layout.panel, self.layout.dock)}
        self._skins: dict[tuple[int, int, int, int], pygame.Surface] = {}
        set_skin(self._dress if self._skin_source is not None else None)
        # The log, the job board and the stores share a corner of the map, so only one is open at a time.
        self.log_open = False
        self.jobs_open = False
        self.stores_open = False
        # At most one of these is set: the resident or the container whose panel is showing.
        self.selected_id: str | None = None
        self.selected_container: str | None = None
        # Where the scene draws its minimap, so that clicks on it do not fall through to the map.
        self.minimap_rect: pygame.Rect | None = None
        self._notice = ""
        self._notice_left = 0.0
        importance = world.registries.event_settings.get("importance", {})
        self.intervention_from = int(importance.get("noteworthy_max", 49)) + 1
        self.feed = EventFeed(
            noteworthy_from=int(importance.get("ambient_max", 29)) + 1,
            intervention_from=self.intervention_from,
        )

        top, sidebar = self.layout.top, self.layout.sidebar
        self.clock_left = sidebar.right + MARGIN
        self.pause_button = Button.at(font, self.clock_left + ICON_SIZE[0] + 40, 1, "II", PAUSE_INTENT)
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

        entries = (
            ("people", "Residentes", ROSTER_INTENT),
            ("work", "Puestos", JOBS_INTENT),
            ("scrap", "Almacén", STORES_INTENT),
            ("log", "Eventos", LOG_INTENT),
            ("map", "Mapa", MINIMAP_INTENT),
        )
        self.menu = [
            MenuButton(pygame.Rect(sidebar.x, sidebar.y + index * MENU_ROW, sidebar.width, MENU_ROW), icon, label, intent)
            for index, (icon, label, intent) in enumerate(entries)
        ]
        self.jobs_button = self.menu[1]
        self.log_button = self.menu[3]

    def _dress(self, target: pygame.Surface, rect: pygame.Rect) -> bool:
        """Put the skin under one of the large parts of the screen, and clear the canvas there to show it."""
        key = tuple(rect)
        if target is not self.canvas or key not in self._skinned:
            return False
        if key not in self._skins:
            size = self.layers.on_screen(rect).size
            self._skins[key] = nine_slice(self._skin_source, size, SKIN_BORDER_PIXELS)
        target.fill(TRANSPARENT, rect)
        self.layers.picture_under(self._skins[key], rect)
        return True

    @property
    def buttons(self) -> list[Button | MenuButton]:
        """Every button on show, the ones of an open panel included."""
        fixed = [self.pause_button, *self.speed_buttons, *self.zoom_buttons, *self.menu]
        if not self.jobs_open:
            return fixed
        return fixed + suggest_buttons(self.font, self.jobs_rect(), self.world, self.selected_id)

    def toggle_log(self) -> None:
        self.log_open, self.jobs_open, self.stores_open = not self.log_open, False, False

    def toggle_jobs(self) -> None:
        self.jobs_open, self.log_open, self.stores_open = not self.jobs_open, False, False

    def toggle_stores(self) -> None:
        self.stores_open, self.log_open, self.jobs_open = not self.stores_open, False, False

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

    def select_resident(self, resident_id: str | None) -> None:
        self.selected_id, self.selected_container = resident_id, None

    def select_container(self, container_id: str | None) -> None:
        self.selected_id, self.selected_container = None, container_id

    def click(self, position: tuple[int, int]) -> Hashable | None:
        """Return the intent of whatever is under `position`: a button, or a resident listed in the panel."""
        for button in self.buttons:
            if button.contains(position):
                return button.intent
        return next((select_intent(resident_id) for row, resident_id in self._listed() if row.collidepoint(position)), None)

    def _listed(self) -> list[tuple[pygame.Rect, str]]:
        """Residents named in the panel on the right, each of whom a click there selects."""
        resident = self.world.residents.get(self.selected_id or "")
        if resident is not None:
            return relationship_hitboxes(self.layout.panel, self.world, resident)
        if self.selected_container in self.world.containers:
            return []
        return roster_rows(self.layout.panel, self.world)

    def covers(self, position: tuple[int, int]) -> bool:
        """True if `position` is not on the map, or something of the HUD is in front of the map there."""
        if not self.layout.map.collidepoint(position):
            return True
        panels = [self.minimap_rect, self.outlook_rect()]
        panels += [self.log_rect()] if self.log_open else []
        panels += [self.jobs_rect()] if self.jobs_open else []
        panels += [self.stores_rect()] if self.stores_open else []
        return any(rect is not None and rect.collidepoint(position) for rect in panels)

    def _float(self, width: int, height: int) -> pygame.Rect:
        """A panel that opens over the top right corner of the map."""
        area = self.layout.map
        return pygame.Rect(area.right - MARGIN - width, area.y + MARGIN, width, min(height, area.height - MARGIN * 2))

    def log_rect(self) -> pygame.Rect:
        return self._float(*LOG_SIZE)

    def jobs_rect(self) -> pygame.Rect:
        return self._float(BOARD_WIDTH, job_board_height(self.world))

    def stores_rect(self) -> pygame.Rect:
        rows = max(1, len(settlement_stock(self.world)))
        return self._float(STORES_WIDTH, MARGIN * 2 + LINE_HEIGHT + 2 + rows * (ITEM_ICON_SIZE[1] + 2))

    def outlook_rect(self) -> pygame.Rect | None:
        """Where the forecasts the settlement has heard are listed, when it has heard any."""
        lines = len(known_forecasts(self.world))
        if not lines:
            return None
        height = OUTLOOK_PADDING * 2 + LINE_HEIGHT * lines
        area = self.layout.map
        return pygame.Rect(area.x + MARGIN, area.y + MARGIN, OUTLOOK_WIDTH, height)

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
        self._render_top()
        draw_panel(self.canvas, self.layout.sidebar, border="ink")
        for button in self.menu:
            button.draw(self.canvas, self.font, self.assets, active=self._menu_active(button.intent))
        self._render_panel()
        self._render_dock()

        outlook = self.outlook_rect()
        if outlook is not None:
            draw_panel(self.canvas, outlook)
            for index, line in enumerate(known_forecasts(self.world)):
                text = self.font.truncate(line, outlook.width - OUTLOOK_PADDING * 2)
                position = (outlook.x + OUTLOOK_PADDING, outlook.y + OUTLOOK_PADDING + index * LINE_HEIGHT)
                self.font.draw(self.canvas, text, position, PALETTE["sand"])
        if self.log_open:
            self.feed.draw_panel(self.canvas, self.font, self.log_rect())
        if self.jobs_open:
            draw_job_board(self.canvas, self.font, self.jobs_rect(), self.world, self.selected_id)
        if self.stores_open:
            self._render_stores(self.stores_rect())

    def _menu_active(self, intent: Hashable) -> bool:
        if intent == ROSTER_INTENT:
            return self.card_rect() is None and self.container_rect() is None
        if intent == MINIMAP_INTENT:
            return self.minimap_rect is not None
        return {JOBS_INTENT: self.jobs_open, STORES_INTENT: self.stores_open, LOG_INTENT: self.log_open}.get(intent, False)

    def _render_top(self) -> None:
        top, clock = self.layout.top, self.world.clock
        draw_panel(self.canvas, top, border="ink")
        plaque = pygame.Rect(top.x + 2, top.y + 2, self.layout.sidebar.width - 4, top.height - 4)
        draw_panel(self.canvas, plaque, fill="shadow", border="copper")
        day = f"Día {clock.day}"
        self.font.draw(self.canvas, day, (plaque.centerx - self.font.width(day) // 2, plaque.y + 5), PALETTE["lamp"])

        sky = self.assets.image(icon_path("moon" if self.world.is_dark() else "sun"), size=ICON_SIZE)
        self.canvas.blit(sky, (self.clock_left, 3))
        hour = f"{clock.hour:02d}:{clock.minute:02d}"
        self.font.draw(self.canvas, hour, (self.clock_left + ICON_SIZE[0] + 4, 2), PALETTE["paper"])
        self.pause_button.draw(self.canvas, self.font, active=clock.paused)
        for button, speed in zip(self.speed_buttons, SPEEDS):
            button.draw(self.canvas, self.font, active=clock.speed == speed and not clock.paused)
        for button in self.zoom_buttons:
            button.draw(self.canvas, self.font)

        x = self.counts_left
        for icon, figure in settlement_counts(self.world):
            self.canvas.blit(self.assets.image(icon_path(icon), size=ICON_SIZE), (x, 3))
            self.font.draw(self.canvas, figure, (x + ICON_SIZE[0] + 3, 2), PALETTE["bone"])
            x += ICON_SIZE[0] + 3 + self.font.width(figure) + 12
        weather = describe_weather(self.world)
        if weather is not None and x + self.font.width(weather) < self.counts_right:
            self.font.draw(self.canvas, weather, (self.counts_right - self.font.width(weather), 2), PALETTE["sand"])

        # Under all that, one line: a word from the game, whoever is waiting for advice, or the latest news.
        width = top.right - MARGIN - self.clock_left
        waiting = next(iter(self.world.decisions.values()), None)
        asker = self.world.residents.get(waiting.resident_id) if waiting is not None else None
        if self._notice_left > 0:
            self.font.draw(self.canvas, self.font.truncate(self._notice, width), (self.clock_left, 14), PALETTE["glow"])
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
                self.canvas, self.font, self.icons, self.faces, self.assets, panel, self.world, resident, self.layers
            )
        elif self.container_rect() is not None:
            draw_panel(self.canvas, panel)
            draw_container_panel(self.canvas, self.font, self.icons, panel.topleft, self.world, self.selected_container, panel.width)
        else:
            draw_roster(self.canvas, self.font, self.faces, panel, self.world)

    def _render_dock(self) -> None:
        """Under the map: the exchange the selected resident is in, or else what has been going on."""
        dock = self.layout.dock
        resident = self.world.residents.get(self.selected_id or "")
        activity = resident.activity if resident is not None else None
        partner = self.world.residents.get(activity.partner_id or "") if activity is not None and activity.using else None
        if resident is None or partner is None or resident.away:
            self.feed.draw_panel(self.canvas, self.font, dock, title=DOCK_TITLE)
            return
        # They take turns to speak, a few minutes each.
        turn = (self.world.clock.total_minutes // 4) % 2
        speaker = resident if turn == 0 else partner
        areas = draw_scene(
            self.canvas,
            self.font,
            self.faces,
            dock,
            (resident.resident_id, expression_of(self.world, resident), resident.name),
            (partner.resident_id, expression_of(self.world, partner), partner.name),
            spoken_line(self.world, speaker) or "...",
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
        draw_panel(self.canvas, rect)
        x, y = rect.x + MARGIN, rect.y + MARGIN
        self.font.draw(self.canvas, STORES_TITLE, (x, y), PALETTE["paper"])
        y += LINE_HEIGHT + 2
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
