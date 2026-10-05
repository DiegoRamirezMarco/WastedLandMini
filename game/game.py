import logging
from pathlib import Path

import pygame

from audio.audio_manager import AudioManager, load_sound_map
from audio.music import load_music_settings, track_for
from graphics.assets import ASSETS_DIR, AssetStore
from graphics.face_renderer import FaceRenderer
from graphics.font import FONT_SHEET, SHEET_SIZE, BitmapFont
from graphics.item_icons import ItemIcons
from save.save_manager import SaveManager
from scenes.global_view import GlobalView
from scenes.interaction_view import InteractionView
from settings import (
    FPS,
    GAME_MINUTES_PER_REAL_SECOND,
    INTERNAL_HEIGHT,
    INTERNAL_WIDTH,
    SCREEN_HEIGHT,
    SCREEN_WIDTH,
    SPEEDS,
)
from simulation.commands import AdvanceTimeCommand, SetPausedCommand, SetSpeedCommand
from simulation.registries import DATA_DIR
from simulation.world import SimulationWorld

SPEED_KEYS = dict(zip((pygame.K_1, pygame.K_2, pygame.K_3), SPEEDS))
CUSTOM_CONTENT_DIR = ASSETS_DIR.parent / "custom_content"
SAVE_PATH = ASSETS_DIR.parent / "saves" / "quicksave.json"

logger = logging.getLogger(__name__)
# Upper bound on catching up after a long frame, so a stall never snowballs.
MAX_MINUTES_PER_FRAME = 60


class Game:
    def __init__(self) -> None:
        pygame.init()
        pygame.display.set_caption("Wasteland Minis")
        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        # Scenes draw on the low-resolution canvas; the window only shows it scaled up.
        self.canvas = pygame.Surface((INTERNAL_WIDTH, INTERNAL_HEIGHT))
        self.clock = pygame.time.Clock()
        self.world = SimulationWorld.demo_world()
        self.running = True
        self.scene_name = "global"
        # Game minutes that real time has earned but the simulation has not played yet.
        self.minutes_owed = 0.0
        self.assets = AssetStore(ASSETS_DIR)
        self.custom = AssetStore(CUSTOM_CONTENT_DIR)
        self.font = BitmapFont(self.assets.image(FONT_SHEET, size=SHEET_SIZE))
        self.icons = ItemIcons(self.assets, self.custom)
        self.faces = FaceRenderer(self.assets, self.custom)
        self.music = load_music_settings(DATA_DIR / "audio.json")
        self.audio = AudioManager(
            ASSETS_DIR / "sounds",
            load_sound_map(DATA_DIR / "audio.json"),
            ASSETS_DIR / "music",
            self.music.tracks.values(),
        )
        self.saves = SaveManager()
        self._build_scenes()

    def _build_scenes(self) -> None:
        """Create the scenes for the current world. Called again whenever the world is replaced."""
        self.scene_name = "global"
        self.minutes_owed = 0.0
        self.global_view = GlobalView(
            self.canvas, self.world, self.assets, self.font, self.icons, self.faces, self.custom
        )
        # Advice is asked for in the dock under the map, with the settlement left on show around it.
        self.interaction_view = InteractionView(
            self.canvas,
            self.world,
            self.font,
            self.faces,
            dock=self.global_view.hud.layout.dock,
            backdrop=self.global_view.render,
        )

    def save_game(self, path: Path = SAVE_PATH) -> bool:
        """Write the settlement to disk. Returns whether it worked."""
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            self.saves.save(self.world, path)
        except OSError as error:
            logger.warning("Could not save to %s: %s", path, error)
            self.global_view.hud.notify("No se pudo guardar")
            return False
        self.global_view.hud.notify("Partida guardada")
        return True

    def load_game(self, path: Path = SAVE_PATH) -> bool:
        """Replace the settlement with the saved one. Returns whether it worked."""
        if not path.is_file():
            self.global_view.hud.notify("No hay partida guardada")
            return False
        try:
            world = self.saves.load(path)
        except (OSError, ValueError, KeyError, TypeError) as error:
            logger.warning("Could not load %s: %s", path, error)
            self.global_view.hud.notify("No se pudo cargar la partida")
            return False
        self.world = world
        self._build_scenes()
        self.global_view.hud.notify("Partida cargada")
        return True

    @property
    def active_scene(self):
        return self.global_view if self.scene_name == "global" else self.interaction_view

    def handle_key(self, key: int) -> None:
        if key == pygame.K_ESCAPE:
            self.running = False
        elif key == pygame.K_TAB:
            if self.scene_name == "global":
                self.open_interaction(next(iter(self.world.decisions), None))
            else:
                self.scene_name = "global"
        elif self.scene_name != "global":
            return
        elif key == pygame.K_SPACE:
            self.world.apply_command(SetPausedCommand(not self.world.clock.paused))
        elif key == pygame.K_F5:
            self.save_game()
        elif key == pygame.K_F9:
            self.load_game()
        elif key == pygame.K_m:
            muted = self.audio.toggle_mute()
            self.global_view.hud.notify("Sonido desactivado" if muted else "Sonido activado")
        elif key in SPEED_KEYS:
            self.world.apply_command(SetSpeedCommand(SPEED_KEYS[key]))

    def open_interaction(self, decision_id: str | None) -> None:
        """Show the close-up scene for an open decision. Time stops until it is closed."""
        self.interaction_view.open(decision_id)
        asking = self.world.decisions.get(decision_id or "")
        if asking is not None:
            # Whoever asks is the one to look at: their panel says what they are going through.
            self.global_view.hud.select_resident(asking.resident_id)
        self.scene_name = "interaction"

    def sync_scenes(self) -> None:
        """Follow requests from the scenes to switch between them."""
        if self.scene_name == "global" and self.global_view.requested_decision is not None:
            self.open_interaction(self.global_view.requested_decision)
        elif self.scene_name == "interaction" and self.interaction_view.closed:
            self.scene_name = "global"
        self.global_view.requested_decision = None

    def update_music(self) -> None:
        """Have the music follow the mood of the settlement."""
        self.audio.set_music(track_for(self.world, self.music))
        self.audio.keep_music_going()

    def advance_simulation(self, dt: float) -> None:
        """Play the game minutes that `dt` real seconds are worth. Time stops outside the global view."""
        if self.scene_name != "global" or self.world.clock.paused:
            return
        self.minutes_owed += dt * GAME_MINUTES_PER_REAL_SECOND * self.world.clock.speed
        minutes = min(int(self.minutes_owed), MAX_MINUTES_PER_FRAME)
        self.minutes_owed -= int(self.minutes_owed)
        if minutes:
            self.world.apply_command(AdvanceTimeCommand(minutes=minutes))
            events = self.world.events.drain()
            self.global_view.on_events(events)
            self.audio.on_events(events)
            # Something that calls for the player's attention: drop back to normal speed.
            threshold = self.global_view.hud.intervention_from
            if self.world.clock.speed != SPEEDS[0] and any(e.importance >= threshold for e in events):
                self.world.apply_command(SetSpeedCommand(SPEEDS[0]))
        self.global_view.tick_progress = self.minutes_owed

    def run(self) -> None:
        while self.running:
            dt = self.clock.tick(FPS) / 1000.0
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                elif event.type == pygame.KEYDOWN:
                    self.handle_key(event.key)
                self.active_scene.handle_event(event)
            self.sync_scenes()

            self.advance_simulation(dt)
            self.update_music()
            self.active_scene.update(dt)
            self.active_scene.render()
            pygame.transform.scale(self.canvas, self.screen.get_size(), self.screen)
            pygame.display.flip()

        pygame.quit()
