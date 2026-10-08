import json
import logging
import random
from pathlib import Path

import pygame

from audio.ambience import actions_in_view, ambience_for
from audio.audio_manager import SOUNDS_DIR, AudioManager, load_sound_settings
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
from graphics.looks import Looks
from graphics.screen_layers import ScreenLayers
from save.save_manager import SaveManager
from scenes.building_editor import BuildingEditor
from scenes.doll_editor import DollEditor
from scenes.global_view import GlobalView
from scenes.interaction_view import InteractionView
from scenes.item_editor import ItemEditor
from scenes.object_editor import ObjectEditor
from scenes.main_menu import CONTINUE, DEMO, NEW_GAME, QUIT, MainMenu
from scenes.manner_editor import MannerEditor
from scenes.manner_preview import MannerPreview
from scenes.resident_creator import ResidentCreator
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
from simulation.commands import AdvanceTimeCommand, ReportDeedCommand, SetPausedCommand, SetSpeedCommand
from simulation.registries import DATA_DIR, BuiltInRegistries
from simulation.world import SimulationWorld
from skeleton.plan import builtin_plan
from ui.tutorial_panel import BUILDING_ART_FOCUS, DOLL_FOCUS

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
OBJECT_SCENE = "object_editor"
MANNER_SCENE = "manners"
NO_DRAWINGS = "No hay carpeta de ilustraciones disponible"
# Screens that read the keyboard themselves: the way in, and where the first resident is made.
MENU_SCENE, CREATOR_SCENE = "menu", "creator"
LOAD_FAILED = "No se pudo cargar la partida guardada"


class Game:
    def __init__(
        self,
        illustrations_dir: Path | None = ILLUSTRATIONS_DIR,
        voices_dir: Path | None = VOICES_DIR,
        custom_content_dir: Path = CUSTOM_CONTENT_DIR,
        start_in_menu: bool = True,
        save_path: Path = SAVE_PATH,
        sounds_dir: Path | None = SOUNDS_DIR,
    ) -> None:
        pygame.init()
        pygame.display.set_caption("Wasteland Minis")
        # Keep the game's fixed logical surface, while SDL fits the physical window to the
        # desktop. Pygame maps input back to these logical coordinates, so scenes, illustrations
        # and the drawing editors stay aligned at every monitor resolution.
        self.screen = pygame.display.set_mode(
            (SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SCALED | pygame.FULLSCREEN
        )
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
        # With a window under the canvas, the game's own items are shown as it draws them for it.
        self.icons.painted = bool(flags)
        # Until somebody draws them, whoever has no art of their own borrows one of the game's looks.
        self.faces = FaceRenderer(self.assets, self.custom, self.illustrations, Looks(self.assets))
        # Residents whose body has been drawn, cut into parts that move.
        self.dolls = DollStore(self.illustrations, load_template(), builtin_plan())
        self.music = load_music_settings(DATA_DIR / "audio.json")
        # A sound of the player's own, in the folder for them, is played in place of the game's.
        self.audio = AudioManager(
            ASSETS_DIR / "sounds",
            load_sound_settings(DATA_DIR / "audio.json"),
            ASSETS_DIR / "music",
            self.music.tracks.values(),
            own_dir=sounds_dir,
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
        self.save_path = Path(save_path)
        # Whether a settlement is being played. Until one is chosen in the menu, the one above is only a stand-in.
        self.in_session = not start_in_menu
        self.main_menu = MainMenu(self.canvas, self.font, self.layers)
        self._build_scenes()
        if start_in_menu:
            self.open_menu()

    def _build_scenes(self) -> None:
        """Create the scenes for the current world. Called again whenever the world is replaced."""
        self.scene_name = "global"
        self.minutes_owed = 0.0
        # Whether the drawing on show was opened from the layout editor, to go back there from it.
        self._art_from_urbanism = False
        self.global_view = GlobalView(
            self.canvas, self.world, self.assets, self.font, self.icons, self.faces, self.custom,
            self.illustrations, self.layers, self.dolls, self.voices,
        )
        self.global_view.sound = self.audio.interface
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
                on_deed=self._report_deed,
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
                on_deed=self._report_deed,
            )
            if self.illustrations.root is not None
            else None
        )
        # Furniture and loose objects are drawn a kind at a time, and kept in the same folder.
        self.object_editor = (
            ObjectEditor(
                self.canvas,
                self.world,
                self.font,
                self.layers,
                self.illustrations.root,
                self.global_view.object_art,
                on_deed=self._report_deed,
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
            self.global_view.object_art,
        )
        # Whoever tries a manner out is seen doing it: in the screen that makes the first resident,
        # and in the one where anybody's manners are changed.
        preview = MannerPreview(self.canvas, self.layers, builtin_plan(), self.dolls, self.world.registries, self.icons)
        self.creator = ResidentCreator(self.canvas, self.world, self.font, self.layers, preview)
        self.manner_editor = MannerEditor(self.canvas, self.world, self.font, preview, self.layers)

    def _report_deed(self, deed: str) -> None:
        """Tell the simulation of something the player has done in an editor, which only the opening cares about."""
        self.world.apply_command(ReportDeedCommand(deed))

    def _skip_what_cannot_be_drawn(self) -> None:
        """With nowhere to keep drawings there are no editors, and the steps that teach drawing are passed over."""
        for _ in self.world.registries.tutorial.steps:
            step = self.world.guide.current(self.world)
            deed = step.goal.needed_deed if step is not None else None
            if deed is None or deed in self.world.tutorial.deeds:
                return
            if step.focus == DOLL_FOCUS:
                editor = self.doll_editor
            elif step.focus == BUILDING_ART_FOCUS:
                editor = self.building_editor
            else:
                editor = self.object_editor
            if editor is not None:
                return
            self._report_deed(deed)

    def _leave_art(self) -> None:
        """Go back from a drawing to where it was opened from."""
        if self._art_from_urbanism:
            self._art_from_urbanism = False
            self.urbanism_editor.open()
            self.scene_name = URBANISM_SCENE
        else:
            self.scene_name = "global"

    def describe_save(self) -> str | None:
        """A few words about the saved settlement, for the menu. None if there is none to go on with."""
        try:
            data = json.loads(self.save_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        if not isinstance(data, dict):
            return None
        clock, residents = data.get("clock"), data.get("residents")
        day = clock.get("day", 1) if isinstance(clock, dict) else 1
        count = len(residents) if isinstance(residents, list) else 0
        return f"Partida guardada: día {day}, {count} {'habitante' if count == 1 else 'habitantes'}"

    def open_menu(self, notice: str = "") -> None:
        """Show the way in. The settlement being played, if there is one, waits where it is."""
        self.main_menu.open(self.in_session, self.describe_save(), notice)
        self.scene_name = MENU_SCENE

    def continue_game(self) -> bool:
        """Go back to the settlement being played, or else to the saved one. Returns whether there was one."""
        if self.in_session:
            self.scene_name = "global"
            return True
        if self.load_game():
            self.in_session = True
            return True
        self.open_menu(LOAD_FAILED)
        return False

    def new_game(self, seed: int | None = None) -> None:
        """Start on an empty plot, with the opening that leads through settling it, and make its first resident."""
        if seed is None:
            # Which settlement this is going to be is the one thing left to chance outside the simulation.
            seed = random.SystemRandom().randrange(1, 2**31)
        self.world = SimulationWorld.new_settlement(seed, self.world.registries)
        self._build_scenes()
        self.in_session = True
        self.open_creator()

    def demo_game(self) -> None:
        """Start on the settlement that comes ready made, with everyone already at their post."""
        self.world = SimulationWorld.demo_world(registries=self.world.registries)
        self._build_scenes()
        self.in_session = True

    def open_creator(self) -> None:
        self.creator.open()
        self.scene_name = CREATOR_SCENE

    def save_game(self, path: Path | None = None) -> bool:
        """Write the settlement to disk. Returns whether it worked."""
        path = path if path is not None else self.save_path
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            self.saves.save(self.world, path)
        except OSError as error:
            logger.warning("Could not save to %s: %s", path, error)
            self.global_view.hud.notify("No se pudo guardar")
            return False
        self.global_view.hud.notify("Partida guardada")
        return True

    def load_game(self, path: Path | None = None) -> bool:
        """Replace the settlement with the saved one. Returns whether it worked."""
        path = path if path is not None else self.save_path
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
        if self.scene_name == MENU_SCENE:
            return self.main_menu
        if self.scene_name == CREATOR_SCENE:
            return self.creator
        if self.scene_name == EDITOR_SCENE and self.doll_editor is not None:
            return self.doll_editor
        if self.scene_name == BUILDING_SCENE and self.building_editor is not None:
            return self.building_editor
        if self.scene_name == OBJECT_SCENE and self.object_editor is not None:
            return self.object_editor
        if self.scene_name == ITEM_SCENE:
            return self.item_editor
        if self.scene_name == URBANISM_SCENE:
            return self.urbanism_editor
        if self.scene_name == VOICE_SCENE and self.voice_editor is not None:
            return self.voice_editor
        if self.scene_name == MANNER_SCENE:
            return self.manner_editor
        return self.global_view if self.scene_name == "global" else self.interaction_view

    def handle_key(self, key: int) -> None:
        if self.scene_name in (MENU_SCENE, CREATOR_SCENE):
            # There the keys are a choice or a name, not shortcuts.
            return
        if self.scene_name == "global" and self.global_view.typing:
            # Nor while a building is being given its name.
            return
        if key == pygame.K_ESCAPE and self.scene_name in (
            EDITOR_SCENE,
            BUILDING_SCENE,
            OBJECT_SCENE,
            ITEM_SCENE,
            VOICE_SCENE,
            MANNER_SCENE,
            URBANISM_SCENE,
        ):
            # Out of the drawing or the voice, not out of the game. The editor closes itself on the same key.
            return
        if key == pygame.K_ESCAPE:
            # Out of the settlement, not out of the game: the menu is where that is done.
            self.open_menu()
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

    def _follow_menu(self) -> None:
        choice, self.main_menu.requested = self.main_menu.requested, None
        if choice == CONTINUE:
            self.continue_game()
        elif choice == NEW_GAME:
            self.new_game()
        elif choice == DEMO:
            self.demo_game()
        elif choice == QUIT:
            self.running = False

    def sync_scenes(self) -> None:
        """Follow requests from the scenes to switch between them."""
        if self.scene_name == MENU_SCENE:
            self._follow_menu()
            return
        self._skip_what_cannot_be_drawn()
        if self.scene_name == CREATOR_SCENE:
            if self.creator.closed:
                self.scene_name = "global"
                created = self.creator.created
                step = self.world.guide.current(self.world)
                if created is not None:
                    # Whoever has just been made is who there is to look at.
                    self.global_view.hud.select_resident(created)
                    self.global_view.centre_on_resident(created)
                if created is not None and self.doll_editor is not None and step is not None and step.focus == DOLL_FOCUS:
                    # And nobody comes ready drawn: the next thing is to draw them.
                    self.doll_editor.open(created)
                    self.scene_name = EDITOR_SCENE
            return
        if self.scene_name == EDITOR_SCENE and (self.doll_editor is None or self.doll_editor.closed):
            self.scene_name = "global"
        elif self.scene_name == BUILDING_SCENE and (self.building_editor is None or self.building_editor.closed):
            self._leave_art()
        elif self.scene_name == OBJECT_SCENE and (self.object_editor is None or self.object_editor.closed):
            self._leave_art()
        elif self.scene_name == URBANISM_SCENE and self.urbanism_editor.requested_art_object is not None:
            kind = self.urbanism_editor.requested_art_object
            self.urbanism_editor.requested_art_object = None
            if self.object_editor is None:
                self.urbanism_editor.message = NO_DRAWINGS
                return
            self.object_editor.open(kind)
            if not self.object_editor.closed:
                self._art_from_urbanism = True
                self.scene_name = OBJECT_SCENE
        elif self.scene_name == ITEM_SCENE and self.item_editor.closed:
            self.scene_name = "global"
        elif self.scene_name == URBANISM_SCENE and self.urbanism_editor.requested_art_room is not None:
            room_id = self.urbanism_editor.requested_art_room
            if self.building_editor is None:
                self.urbanism_editor.requested_art_room = None
                self.urbanism_editor.message = NO_DRAWINGS
                return
            # Rebuild render caches first; the drawing editor must guide from the edited terrain.
            self._build_scenes()
            if room_id in self.world.rooms:
                self.building_editor.open(room_id)
                self._art_from_urbanism = True
                self.scene_name = BUILDING_SCENE
        elif self.scene_name == URBANISM_SCENE and self.urbanism_editor.closed:
            notice = self.urbanism_editor.message
            # Terrain and room render caches are rebuilt from the authoritative edited world.
            self._build_scenes()
            self.global_view.hud.notify(notice)
        elif self.scene_name == VOICE_SCENE and (self.voice_editor is None or self.voice_editor.closed):
            self.scene_name = "global"
        elif self.scene_name == MANNER_SCENE and self.manner_editor.closed:
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
        elif self.scene_name == "global" and self.global_view.requested_creator:
            self.open_creator()
        elif (
            self.scene_name == "global"
            and self.global_view.requested_object_editor is not None
            and self.object_editor is not None
        ):
            self.object_editor.open(self.global_view.requested_object_editor)
            if not self.object_editor.closed:
                self.scene_name = OBJECT_SCENE
        elif self.scene_name == "global" and self.global_view.requested_voice is not None and self.voice_editor is not None:
            self.voice_editor.open(self.global_view.requested_voice)
            self.scene_name = VOICE_SCENE
        elif self.scene_name == "global" and self.global_view.requested_manners is not None:
            self.manner_editor.open(self.global_view.requested_manners)
            if not self.manner_editor.closed:
                self.scene_name = MANNER_SCENE
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
        self.global_view.requested_creator = False
        self.global_view.requested_object_editor = None
        self.global_view.requested_voice = None
        self.global_view.requested_manners = None

    def update_music(self) -> None:
        """Have the music follow the mood of the settlement."""
        self.audio.set_music(track_for(self.world, self.music))
        self.audio.keep_music_going()

    def update_sound(self, dt: float) -> None:
        """Have what is heard follow the settlement: the hour and the weather, what is in view,
        and what those in view are doing. Outside the settlement there is nothing to hear."""
        on_the_map = self.scene_name == "global" and self.in_session
        kinds, people = self.global_view.in_view() if on_the_map else (set(), [])
        heard = ambience_for(self.world, self.audio.settings.ambience, self.music, kinds, people) if on_the_map else {}
        self.audio.set_ambience(heard)
        if on_the_map and not self.world.clock.paused:
            self.audio.on_actions(actions_in_view(self.world, people), dt)
        self.audio.update(dt)

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
        self.dolls.new_frame()

    def handle_event(self, event: pygame.event.Event) -> None:
        """Give one input event to the shell, and then to the scene on show."""
        if event.type == pygame.QUIT:
            self.running = False
            return
        if event.type == pygame.KEYDOWN:
            before = self.scene_name
            self.handle_key(event.key)
            if self.scene_name == MENU_SCENE and before != MENU_SCENE:
                # The key that brought the menu up is not also a choice made in it.
                return
        self.active_scene.handle_event(event)

    def run(self) -> None:
        while self.running:
            dt = self.clock.tick(FPS) / 1000.0
            for event in pygame.event.get():
                self.handle_event(event)
            self.sync_scenes()

            self.advance_simulation(dt)
            self.update_music()
            self.update_sound(dt)
            if self.voices is not None:
                self.voices.update()
            self.active_scene.update(dt)
            self.active_scene.render()
            self.present()
            pygame.display.flip()

        pygame.quit()
