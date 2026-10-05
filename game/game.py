import logging
from pathlib import Path

import pygame

from audio.audio_manager import AudioManager, load_sound_map
from audio.music import load_music_settings, track_for
from audio.voice_player import VoicePlayer
from audio.voice_synth import VoiceSynth
from audio.voice_system import CACHE_FOLDER, MODELS_FOLDER, VOICES_DIR, VoiceStore, load_voice_catalog
from graphics.assets import ASSETS_DIR, AssetStore
from graphics.doll import DollStore, load_template
from graphics.face_renderer import FaceRenderer
from graphics.font import FONT_SHEET, SHEET_SIZE, BitmapFont
from graphics.illustrations import ILLUSTRATIONS_DIR, Illustrations
from graphics.item_icons import ItemIcons
from graphics.screen_layers import ScreenLayers
from save.save_manager import SaveManager
from scenes.building_editor import BuildingEditor
from scenes.doll_editor import DollEditor
from scenes.global_view import GlobalView
from scenes.interaction_view import InteractionView
from scenes.item_editor import ItemEditor
from scenes.urbanism import UrbanismEditor
from scenes.voice_editor import VoiceEditor
from settings import (
    FPS,
    GAME_MINUTES_PER_REAL_SECOND,
    INTERNAL_HEIGHT,
    INTERNAL_WIDTH,
    SCALE,
    SCREEN_HEIGHT,
    SCREEN_WIDTH,
    SPEEDS,
)
from simulation.commands import AdvanceTimeCommand, SetPausedCommand, SetSpeedCommand
from simulation.registries import DATA_DIR, BuiltInRegistries
from simulation.world import SimulationWorld
from skeleton.plan import builtin_plan

SPEED_KEYS = dict(zip((pygame.K_1, pygame.K_2, pygame.K_3), SPEEDS))
CUSTOM_CONTENT_DIR = ASSETS_DIR.parent / "custom_content"
SAVE_PATH = ASSETS_DIR.parent / "saves" / "quicksave.json"

logger = logging.getLogger(__name__)
# Upper bound on catching up after a long frame, so a stall never snowballs.
MAX_MINUTES_PER_FRAME = 60
# Editors in which simulation time stands still and Escape goes back to the map.
EDITOR_SCENE, BUILDING_SCENE, ITEM_SCENE, VOICE_SCENE, URBANISM_SCENE = (
    "editor",
    "building_editor",
    "item_editor",
    "voice",
    "urbanism",
)


class Game:
    def __init__(
        self,
        illustrations_dir: Path | None = ILLUSTRATIONS_DIR,
        voices_dir: Path | None = VOICES_DIR,
        custom_content_dir: Path = CUSTOM_CONTENT_DIR,
    ) -> None:
        pygame.init()
        pygame.display.set_caption("Wasteland Minis")
        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        # Pictures made outside the game go straight on the window, under the canvas.
        self.illustrations = Illustrations(illustrations_dir)
        self.layers = ScreenLayers(SCALE)
        # Scenes draw on the low-resolution canvas; the window shows it scaled up. Where there are
        # illustrations to show through it, the canvas can be left clear.
        flags = pygame.SRCALPHA if self.illustrations.root is not None else 0
        self.canvas = pygame.Surface((INTERNAL_WIDTH, INTERNAL_HEIGHT), flags)
        self.clock = pygame.time.Clock()
        self.custom_content_dir = Path(custom_content_dir).resolve()
        # The editor replaces live definitions, so each running game owns its registries instead
        # of mutating the process-wide read-only built-ins shared by headless simulations.
        registries = BuiltInRegistries.load(DATA_DIR, self.custom_content_dir)
        self.world = SimulationWorld.demo_world(registries=registries)
        self.running = True
        self.scene_name = "global"
        # Game minutes that real time has earned but the simulation has not played yet.
        self.minutes_owed = 0.0
        self.assets = AssetStore(ASSETS_DIR)
        self.custom = AssetStore(self.custom_content_dir)
        self.font = BitmapFont(self.assets.image(FONT_SHEET, size=SHEET_SIZE))
        self.icons = ItemIcons(self.assets, self.custom)
        self.faces = FaceRenderer(self.assets, self.custom, self.illustrations)
        # Residents whose body has been drawn, cut into parts that move.
        self.dolls = DollStore(self.illustrations, load_template())
        self.music = load_music_settings(DATA_DIR / "audio.json")
        self.audio = AudioManager(
            ASSETS_DIR / "sounds",
            load_sound_map(DATA_DIR / "audio.json"),
            ASSETS_DIR / "music",
            self.music.tracks.values(),
        )
        # What residents say is said out loud, each in their own voice, if there is a folder for voices.
        self.voices: VoicePlayer | None = None
        if voices_dir is not None:
            catalog = load_voice_catalog()
            self.voices = VoicePlayer(
                catalog,
                VoiceStore(voices_dir, catalog),
                VoiceSynth(voices_dir / MODELS_FOLDER, voices_dir / CACHE_FOLDER),
                self.audio,
            )
        self.saves = SaveManager()
        self._build_scenes()

    def _build_scenes(self) -> None:
        """Create the scenes for the current world. Called again whenever the world is replaced."""
        self.scene_name = "global"
        self.minutes_owed = 0.0
        self.global_view = GlobalView(
            self.canvas, self.world, self.assets, self.font, self.icons, self.faces, self.custom,
            self.illustrations, self.layers, self.dolls, self.voices,
        )
        # Advice is asked for in the dock under the map, with the settlement left on show around it.
        self.interaction_view = InteractionView(
            self.canvas,
            self.world,
            self.font,
            self.faces,
            dock=self.global_view.hud.layout.dock,
            backdrop=self.global_view.render,
            layers=self.layers,
            voices=self.global_view.voices,
        )
        # Where residents are given a voice, if there are voices to give.
        self.voice_editor = (
            VoiceEditor(self.canvas, self.world, self.font, self.faces, self.voices, self.layers)
            if self.global_view.voices is not None
            else None
        )
        # Where residents are drawn, if there is a folder to keep the drawings in.
        self.doll_editor = (
            DollEditor(
                self.canvas,
                self.world,
                self.font,
                self.layers,
                self.illustrations.root,
                self.dolls,
                builtin_plan(),
                self.global_view.bodies.renderer,
                on_saved=self.faces.forget,
            )
            if self.illustrations.root is not None
            else None
        )
        # Buildings use the same illustrations folder, but keep four aligned drawings of their own.
        self.building_editor = (
            BuildingEditor(
                self.canvas,
                self.world,
                self.font,
                self.layers,
                self.illustrations.root,
                self.global_view.building_art,
            )
            if self.illustrations.root is not None
            else None
        )
        # Items can always be edited: their overrides live in custom_content, independently of
        # the optional high-resolution illustrations folder.
        self.item_editor = ItemEditor(
            self.canvas,
            self.world,
            self.font,
            self.custom_content_dir,
            self.icons,
            self.layers,
        )
        self.urbanism_editor = UrbanismEditor(
            self.canvas,
            self.world,
            self.font,
            self.assets,
            self.custom,
            self.layers,
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
            world = self.saves.load(path, self.world.registries)
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
        if self.scene_name == EDITOR_SCENE and self.doll_editor is not None:
            return self.doll_editor
        if self.scene_name == BUILDING_SCENE and self.building_editor is not None:
            return self.building_editor
        if self.scene_name == ITEM_SCENE:
            return self.item_editor
        if self.scene_name == URBANISM_SCENE:
            return self.urbanism_editor
        if self.scene_name == VOICE_SCENE and self.voice_editor is not None:
            return self.voice_editor
        return self.global_view if self.scene_name == "global" else self.interaction_view

    def handle_key(self, key: int) -> None:
        if key == pygame.K_ESCAPE and self.scene_name in (
            EDITOR_SCENE,
            BUILDING_SCENE,
            ITEM_SCENE,
            VOICE_SCENE,
            URBANISM_SCENE,
        ):
            # Out of the drawing or the voice, not out of the game. The editor closes itself on the same key.
            return
        if key == pygame.K_ESCAPE:
            self.running = False
        elif key == pygame.K_TAB:
            if self.scene_name == ITEM_SCENE:
                # The item editor uses Tab to move between text fields.
                return
            if self.scene_name == URBANISM_SCENE:
                self.urbanism_editor.closed = True
                return
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
        if self.scene_name == EDITOR_SCENE and (self.doll_editor is None or self.doll_editor.closed):
            self.scene_name = "global"
        elif self.scene_name == BUILDING_SCENE and (self.building_editor is None or self.building_editor.closed):
            self.scene_name = "global"
        elif self.scene_name == ITEM_SCENE and self.item_editor.closed:
            self.scene_name = "global"
        elif self.scene_name == URBANISM_SCENE and self.urbanism_editor.requested_art_room is not None:
            room_id = self.urbanism_editor.requested_art_room
            if self.building_editor is None:
                self.urbanism_editor.requested_art_room = None
                self.urbanism_editor.message = "No hay carpeta de ilustraciones disponible"
                return
            # Rebuild render caches first; the drawing editor must guide from the edited terrain.
            self._build_scenes()
            if room_id in self.world.rooms:
                self.building_editor.open(room_id)
                self.scene_name = BUILDING_SCENE
        elif self.scene_name == URBANISM_SCENE and self.urbanism_editor.closed:
            notice = self.urbanism_editor.message
            # Terrain and room render caches are rebuilt from the authoritative edited world.
            self._build_scenes()
            self.global_view.hud.notify(notice)
        elif self.scene_name == VOICE_SCENE and (self.voice_editor is None or self.voice_editor.closed):
            self.scene_name = "global"
        elif self.scene_name == "global" and self.global_view.requested_editor is not None and self.doll_editor is not None:
            self.doll_editor.open(self.global_view.requested_editor)
            self.scene_name = EDITOR_SCENE
        elif (
            self.scene_name == "global"
            and self.global_view.requested_building_editor is not None
            and self.building_editor is not None
        ):
            self.building_editor.open(self.global_view.requested_building_editor)
            self.scene_name = BUILDING_SCENE
        elif self.scene_name == "global" and self.global_view.requested_item_editor is not None:
            self.item_editor.open(self.global_view.requested_item_editor)
            self.scene_name = ITEM_SCENE
        elif self.scene_name == "global" and self.global_view.requested_save:
            self.save_game()
        elif self.scene_name == "global" and self.global_view.requested_urbanism:
            self.urbanism_editor.open()
            self.scene_name = URBANISM_SCENE
        elif self.scene_name == "global" and self.global_view.requested_voice is not None and self.voice_editor is not None:
            self.voice_editor.open(self.global_view.requested_voice)
            self.scene_name = VOICE_SCENE
        elif self.scene_name == "global" and self.global_view.requested_decision is not None:
            self.open_interaction(self.global_view.requested_decision)
        elif self.scene_name == "interaction" and self.interaction_view.closed:
            self.scene_name = "global"
        self.global_view.requested_decision = None
        self.global_view.requested_editor = None
        self.global_view.requested_building_editor = None
        self.global_view.requested_item_editor = None
        self.global_view.requested_save = False
        self.global_view.requested_urbanism = False
        self.global_view.requested_voice = None

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

    def present(self, screen: pygame.Surface | None = None) -> None:
        """Put the frame the active scene has just drawn on the window, or on another surface of its size."""
        self.layers.compose(screen if screen is not None else self.screen, self.canvas)

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
            if self.voices is not None:
                self.voices.update()
            self.active_scene.update(dt)
            self.active_scene.render()
            self.present()
            pygame.display.flip()

        pygame.quit()
