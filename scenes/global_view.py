import math
from collections.abc import Callable, Hashable, Iterable
from dataclasses import dataclass

import pygame

from graphics.assets import AssetStore
from graphics.body_renderer import FRAME_ORIGIN, FRAME_SIZE, BodyRenderer
from graphics import building_pictures, ground_pictures
from graphics.building_art import BuildingArtStore, door_columns
from graphics.bolts import HIGHEST, Bolt, BoltArt, bolts
from graphics.building_renderer import FACADE_ROWS, BuildingRenderer, building_area
from graphics.bundle import bundle_height, bundle_picture, ground_blanket
from graphics.crumbs import Crumb, CrumbArt, crumbs
from graphics.doll import DOLL_FACINGS, Doll, DollStore, draw_doll
from graphics.face_renderer import FaceRenderer
from graphics.font import CELL_SIZE, BitmapFont
from graphics.icons import ICON_SIZE, icon_path
from graphics.illustrations import Illustrations
from graphics.item_icons import ICON_SIZE as ITEM_ICON_SIZE
from graphics.item_icons import ItemIcons
from graphics.lighting import BLOCK, LightMap, daylight, shade
from graphics.object_sprites import ObjectSprites
from graphics.screen_layers import TRANSPARENT, ScreenLayers
from graphics.object_art import ObjectArtStore
from graphics.object_pictures import ObjectPicture, ObjectPictures
from graphics.shelf_display import GOODS_SIZE
from graphics.stand_ins import child_stand_in, stand_in
from graphics.map_renderer import GROUND_TILES, render_roofs, render_terrain, roof_names
from graphics.palette import PALETTE
from graphics.poses import Doing, builtin_poses
from graphics.shelf_display import SLOTS, displayed_goods
from graphics.tileset import (
    ROOF_CELLS,
    ROOF_SHEET,
    ROOF_SHEET_SIZE,
    SETTLEMENT_CELLS,
    SETTLEMENT_SHEET,
    SETTLEMENT_SHEET_SIZE,
    Tileset,
)
from scenes.body_stage import (
    BUNDLE_BEHIND,
    BUNDLE_RAISED,
    BUNDLE_UP,
    BUNDLE_WIDTH,
    HEAD_BONE,
    HEAD_OF_HEIGHT,
    LYING_HEAD_OFFSET,
    LYING_HEAD_ROWS,
    LYING_NECK,
    TILES_PER_STRIDE,
    BodyStage,
    Remains,
    ground_spot,
    grown_share,
    spot_tile,
)
from scenes.carrying import (
    EDGE,
    HANG,
    IN_HAND_DEPTH,
    INTO,
    Carry,
    Target,
    caption,
    draw_caption,
    draw_footing,
    draw_pick,
    hung,
)
from audio.voice_player import VoicePlayer
from scenes.hud import (
    AWAY_LABEL,
    BUILD_INTENT,
    FAMILY_INTENT,
    FUND_INTENT,
    DISCOVERY_INTENT,
    GIVE_OPEN_INTENT,
    GOVERNMENT_INTENT,
    VOICE_INTENT,
    DRAW_INTENT,
    JOBS_INTENT,
    RESEARCH_INTENT,
    MANNERS_INTENT,
    LOG_INTENT,
    MINIMAP_INTENT,
    PANEL_KIN_INTENT,
    PANEL_MOOD_INTENT,
    PANEL_TAB_INTENT,
    PAUSE_INTENT,
    ROSTER_INTENT,
    STORES_INTENT,
    TASTE_DEBUG_INTENT,
    URBANISM_INTENT,
    Hud,
)
from scenes.expedition_view import LEAVE_TRIP_INTENT, ExpeditionView
from scenes.interior_view import DECOR_INTENT, HOUSE_INTENT, LEAVE_INTENT, InteriorView
from ui.decor_board import DONE_INTENT as DECOR_DONE_INTENT
from ui.decor_board import FLOORS as DECOR_FLOORS
from ui.decor_board import FURNITURE as DECOR_FURNITURE
from ui.decor_board import ORNAMENTS as DECOR_ORNAMENTS
from ui.decor_board import REMOVE_INTENT as DECOR_REMOVE_INTENT
from ui.decor_board import WALLS as DECOR_WALLS
from ui.house_board import LOCK_INTENT as HOUSE_LOCK_INTENT
from ui.house_board import NAME_LENGTH
from ui.house_board import RENAME_INTENT as HOUSE_RENAME_INTENT
from ui.house_board import USE_INTENT as HOUSE_USE_INTENT
from ui.house_board import next_use
from scenes.scene import canvas_position
from settings import SCALE, TILE_SIZE
from simulation.commands import (
    AccuseCommand,
    AcknowledgeTutorialCommand,
    ChooseGovernmentCommand,
    AddWordCommand,
    AnswerAskCommand,
    CompostCommand,
    DismissAskCommand,
    GiveCommand,
    SetNicknameCommand,
    SetPhraseCommand,
    TalkAboutCommand,
    DealWithMerchantCommand,
    DecorateCommand,
    GiveHouseCommand,
    LockHouseCommand,
    NameBuildingCommand,
    ProposeBarterCommand,
    ProposeCommand,
    ProposeCurrencyCommand,
    ProposeObjectCommand,
    ProposeSaleCommand,
    ProposeUpgradeCommand,
    RenameCurrencyCommand,
    SurfaceCommand,
    UndecorateCommand,
    PutBundleCommand,
    PutDownCommand,
    SentenceCommand,
    SetPausedCommand,
    SetPrisonRationCommand,
    SetResearchCommand,
    SetSpeedCommand,
    AffectCommand,
    CancelOrderCommand,
    HoldResidentCommand,
    ReleaseResidentCommand,
    SetFreeWillCommand,
    ScrapItemCommand,
    SuggestJobCommand,
    SwitchCommand,
)
from simulation.ai.affect import SALVAGE, SHARED, TASK
from simulation.ai.placing import LAY, NOWHERE, STAND
from simulation.events.event import DomainEvent
from simulation.events.world_event_system import GATE_DECISIONS
from simulation.family.children import BED as BUNDLE_IN_BED
from simulation.family.children import CARRIED as BUNDLE_CARRIED
from simulation.family.children import SURFACE as BUNDLE_ON_SURFACE
from simulation.family.children import Bundle
from simulation.ai.navigation import seat_at
from simulation.family.family_system import SLEEP_ROUGH_ACTION
from simulation.items.item_system import USE_ITEM_ACTION
from simulation.residents.manner import ARGUE, EAT, FIGHT, SIT, WALK
from simulation.social.talk import ASK_SUBJECT
from simulation.social.talk import TAKEN_EVENT as SUBJECT_TAKEN_EVENT
from simulation.tastes.settings import DISLIKED, HATED, LIKED, LOVED
from simulation.tastes.taste_system import FOUND_OUT_EVENT, REACTION_EVENT
from simulation.work.construction import BUILD_ACTION, FINISHED_EVENT
from simulation.work.work_system import WORK_ACTION
from simulation.politics.proposal import ENACT_LAW, REPEAL_LAW
from simulation.work.craft_system import FOUND_EVENT
from simulation.residents.activity import PROTEST_ACTION
from simulation.residents.resident import Resident
from simulation.world import SimulationWorld
from skeleton.plan import IDLE_CLIP, builtin_plan
from skeleton.rig import Skeleton
from ui.affect_wheel import AFFECT_INTENT, BACK_INTENT, CLOSE_INTENT, SOCIAL, TASKS, WILL_INTENT
from ui.fund_board import BARTER_BACK, CURRENCY, RENAME, FundEntry
from ui.trade_board import CART_INTENT as TRADE_CART_INTENT
from ui.trade_board import DEAL_INTENT as TRADE_DEAL_INTENT
from ui.trade_board import DRAW_INTENT as TRADE_DRAW_INTENT
from ui.bubble import MARK_SIZE, MARK_TAIL, PLACARD_SIZE, PLACARD_STICK, draw_mark, draw_placard
from ui.law_board import named_items, picked_degree, picked_params
from ui.labels import away_residents, has_birthday, rarity_color, talk_line
from ui.object_marks import draw_gem, draw_object_mark, marks_of
from ui.object_panel import speaks
from ui.power_board import POWER_INTENT
from ui.talk_bubble import TAIL as BUBBLE_TAIL
from ui.talk_bubble import bubble_of, bubble_size, draw_talk_bubble, said_aloud, wish_shown
from ui.words_board import (
    ANSWER_FIELD,
    ASKED,
    ITEMS_TAB,
    LISTS,
    NICKNAME_FIELD,
    ONE,
    PHRASE_FIELD,
    PICK,
    SUBJECT_FIELD,
    WORD_FIELD,
    WORDS_BACK_INTENT,
    WORDS_GIVE_INTENT,
    WORDS_INTENT,
    WordsEntry,
    first_list,
    new_list,
    pages,
)
from ui.punish_board import DRINK as RATION_DRINK
from ui.punish_board import DRINKS as RATION_DRINKS
from ui.punish_board import FOOD as RATION_FOOD
from ui.punish_board import MEALS as RATION_MEALS
from ui.punish_board import next_ration_item
from ui.minimap import TILE_PIXELS, draw_minimap, minimap_base, minimap_size, tile_at
from ui.panel import draw_item, draw_panel
from ui.task_bar import draw_task_bar, task_bar_rect, task_progress
from ui.job_board import LEAVE_KIND, LEAVE_POST_INTENT, PUSH_KIND, PUSH_POST_INTENT, PUT_KIND
from ui.work_marks import RING, SMALL_RING, TRAINING_COLOR, WorkPops, draw_ring
from ui.tutorial_panel import (
    ACKNOWLEDGE_INTENT,
    BUILDING_ART_FOCUS,
    CREATOR_INTENT,
    DOLL_FOCUS,
    owed_object,
)
from ui.tutorial_panel import DRAW_INTENT as TUTORIAL_DRAW_INTENT
from world.build import BUILDING_SITE, BuildSite
from world.interactable import Interactable
from world.map import Tile
from world.room import Room

# How far across a step has to take someone, in tiles, for a doll to turn to that side.
LEAN = 0.05
# What a body does besides standing and walking, and how many times a second its clip goes round.
# Walking, eating, fighting and having words are done each resident's own way, and those go
# by their manner.
# Work is shown by what the work is (`graphics.poses`).
WALK_CLIP = "walk"
ARGUE_CLIP = "argue"
FIGHT_CLIP = "fight"
EAT_CLIP = "eat"
EAT_ACTION = "eat"
CLIP_RATES = {ARGUE_CLIP: 1.2, FIGHT_CLIP: 1.5, EAT_CLIP: 1.15}
# The clip and the rate of whoever has no manner to go by, as on a game with none defined.
PLAIN_CLIPS = {WALK: WALK_CLIP, EAT: EAT_CLIP, FIGHT: FIGHT_CLIP, ARGUE: ARGUE_CLIP}
# The semantic anchors live in the body plan; these only place the mouth a little below and in
# front of the head joint for each view.
MOUTH_OFFSETS = {
    "down": (0, 2), "up": (0, 1), "right": (2, 2), "left": (-2, 2),
    "doll_right": (2, 2), "doll_left": (-2, 2),
}
# How large a thing in someone's hand is along its longer side, in pixels of the map's art: more
# than a head, so that what was drawn on it can be made out.
HELD_SIZE = 11
# It is held by its back half: this far out in front of the hand, so that it is not over the face.
HELD_AHEAD = 2
# A meal is seen with a bite more gone from it at each of these shares of the way through.
BITES_AT = (0.2, 0.4, 0.6, 0.8)
# Frames per second of animated objects and bobbing icons.
ANIMATION_FPS = 5
ENTER_HINT = "clic: entrar"
# Something shown on the window: how far down the map its foot is, where it goes in map
# pixels (left, top, width, height), and its picture.
Standing = tuple[float, tuple[float, float, float, float], pygame.Surface]
NOBODY_TO_MAKE_IT = "Elige antes a quien deba hacerlo, o di de quién es la casa."
NEWCOMER_EVENT = "newcomer_joined"
NO_HOUSE_YET = "{name} no tiene casa y dormirá al raso: entra en un edificio y dásela en Casa"
NOWHERE_TO_ENTER = "No hay ningún edificio ahí en el que entrar"
BOBBING_ICONS = ("alert", "sleep", "push", "ask")
# What someone is doing is shown in a bubble over their head. These are not: they mark who it is.
BARE_ICONS = ("selected", "heart", "friend", "birthday", "push")
# Over whoever wants a word of the player, for as long as they wait for it (P62).
ASK_ICON = "ask"
# Over whoever wants something for themselves, for as long as they do (P63).
WISH_ICON = "wish"
# Over whoever is pushing their post, and over whoever it has just gone badly for.
PUSH_ICON = "push"
ACCIDENT_EVENT = "work_accident"
ACCIDENT_MARK = "alert"
BIRTHDAY_ICON = "birthday"
# Two who marry wear it over their heads for this many seconds.
WEDDING_EVENT = "couple_married"
WEDDING_MARK = "rings"
WEDDING_SECONDS = 10.0
# Somebody asleep on the ground, under a blanket: how wide and how tall the heap of them is in
# map pixels, and where their neck is on it, from its left end and from the ground.
ROUGH_SIZE = (20.0, 9.0)
ROUGH_NECK = (3.5, 3.0)
# How something was taken, and that something was learned of whoever took it, shown over their
# head for this many seconds each, one after the other.
TASTE_MARKS = {LOVED: "relish", LIKED: "relish", DISLIKED: "disgust", HATED: "disgust"}
FOUND_OUT_MARK = "insight"
MARK_SECONDS = 2.5
MARKS_WAITING = 3
# How something is seen to be taken, by the way it is taken, and by any other way.
TAKEN_EVENT = "substance_taken"
ROUTE_MARKS = {"swallowed": "swallow", "sniffed": "sniff", "injected": "inject", "smoked": "smoke"}
TAKEN_MARK = "swallow"
# How whoever is under something goes about, by what it looks like on them: how far to either
# side they sway, in tiles, and how many times a second. Any other sign sways as the last does.
SWAYS = {"drunk": (0.2, 0.9), "high": (0.07, 3.6)}
STEADY_SIGNS = ("smoke",)
OTHER_SWAY = (0.1, 1.6)
UNDER_ICON = "dizzy"
# The sign that has smoke hang round whoever wears it: how many puffs, how high they rise over
# their head in canvas pixels, how far to either side they drift, and how long each takes, in seconds.
SMOKE_SIGN = "smoke"
SMOKE_PUFFS = 4
SMOKE_RISE = 18
SMOKE_DRIFT = 5
SMOKE_SECONDS = 2.4
# Health below which a resident is shown as hurt.
HURT_HEALTH = 70.0
# Where a load is drawn on a body frame, by the way the resident faces: in their arms, or on their back.
SUGGESTION_REFUSED = "Ahora no se le puede proponer ese puesto"
HARSH_SENTENCE = "Un castigo así no tiene vuelta atrás ({name}): pulsa otra vez para darlo"
NOBODY_NEEDS_ATTENTION = "Nadie necesita atención ahora"
NOTHING_WITH = "Con {name} no hay nada que decirle ahora"
ROOFS_ON = "Tejados puestos: se quitan al mirar dentro"
ROOFS_OFF = "Tejados quitados"
MINIMAP_ON = "Minimapa a la vista"
MINIMAP_OFF = "Minimapa guardado"
# What was bought at the gate and waits there to be carried in: how many kinds of it are shown.
GATE_KINDS = 3
MINIMAP_MARGIN = 6
# What bad weather multiplies the picture of the map by, and how many streaks of dust blow across it.
STORM_TINT = (226, 198, 156)
STORM_STREAKS = 70
STORM_SPEED = 140
# Canvas pixels per real second that the view scrolls while a direction key is held.
SCROLL_SPEED = 260
SCROLL_KEYS = {
    (-1, 0): (pygame.K_LEFT, pygame.K_a),
    (1, 0): (pygame.K_RIGHT, pygame.K_d),
    (0, -1): (pygame.K_UP, pygame.K_w),
    (0, 1): (pygame.K_DOWN, pygame.K_s),
}
RIGHT_MOUSE_BUTTON = 2
# Canvas pixels the mouse must move with the left button held before it is pulling the map along
# and no longer clicking on it.
DRAG_START = 4
# How fast the view closes on whoever it follows: the share of the way left that it covers in a
# second, were it to keep its speed. Nearer than FOLLOW_SNAP map pixels, it is simply there.
FOLLOW_RATE = 8.0
FOLLOW_SNAP = 0.75
# Canvas pixels a tile takes at each zoom step, whole multiples of the art but for the first.
# The first is the overview: the settlement from afar, with the roofs on and a face for each resident.
ZOOM_TILE_SIZES = (TILE_SIZE // 2, TILE_SIZE, TILE_SIZE * 2, TILE_SIZE * 3)
DEFAULT_ZOOM = 1
# An illustrated ground is kept at this many of its pixels to a pixel of the map's own art, which
# is what the window shows at the default zoom.
GROUND_DETAIL = 2
ZOOM_KEYS = {
    pygame.K_PLUS: 1,
    pygame.K_KP_PLUS: 1,
    pygame.K_EQUALS: 1,
    pygame.K_MINUS: -1,
    pygame.K_KP_MINUS: -1,
}

Draw = tuple[float, int, Callable[[], None]]
# Something in someone's hand this frame: what, where in map pixels, whether they face left, how
# many bites are gone from it, and the crumbs flying from their mouth with where that is.
InHand = tuple[str, tuple[float, float], bool, int, list[Crumb], tuple[float, float]]


@dataclass(frozen=True)
class Gripped:
    """Something held by its handle this frame, as a tool is: what, the point of its handle that
    is in the hand, in map pixels, the way the handle runs from there and how far along it that
    point is, how much of its size it is shown at, and whether whoever holds it faces left."""

    item_id: str
    hand: tuple[float, float]
    way: tuple[float, float]
    at: float
    share: float
    left: bool


@dataclass(frozen=True)
class Sparks:
    """The bolts that fly this frame from somebody who is having words with another: the middle
    of the head they fly from, in map pixels, the bolts, and how much of its size their body is
    shown at."""

    at: tuple[float, float]
    bolts: tuple[Bolt, ...]
    share: float


Held = InHand | Gripped | Sparks
# A paper doll to put on the window this frame: how far down the map it stands, the doll, and either
# the skeleton it is laid over or, for someone lying under a blanket, where their neck is. Then
# how much of its drawn size the body is shown at, and the spot between its feet that it is
# brought down about.
DollDraw = tuple[float, Doll, Skeleton | None, tuple[float, float] | None, float, tuple[float, float]]
# The body every child nobody has drawn is shown with.
CHILD_BODY = "child"
BORN_EVENT = "child_born"
# Which way a doll faces until its resident has walked to one side or the other.
DOLL_FACING = DOLL_FACINGS["right"]


class GlobalView:
    def __init__(
        self,
        canvas: pygame.Surface,
        world: SimulationWorld,
        assets: AssetStore,
        font: BitmapFont,
        icons: ItemIcons,
        faces: FaceRenderer,
        custom: AssetStore | None = None,
        illustrations: Illustrations | None = None,
        layers: ScreenLayers | None = None,
        dolls: DollStore | None = None,
        voices: VoicePlayer | None = None,
    ) -> None:
        self.canvas = canvas
        # What says out loud the words in the bubble over whoever is selected, if there are
        # voices to say it with.
        self.voices = voices if voices is not None and voices.enabled else None
        self._spoken_seen: tuple[str, str] | None = None
        # Resident the player asked to give a voice to. The game shell picks it up.
        self.requested_voice: str | None = None
        # Resident whose manners the player asked to choose.
        self.requested_manners: str | None = None
        # Residents whose body has been drawn are shown as paper dolls, on the window itself.
        self.dolls = dolls if layers is not None else None
        self._doll_facing: dict[str, str] = {}
        self._doll_draws: list[DollDraw] = []
        self._held: list[Held] = []
        self._crumb_art = CrumbArt()
        self._bolt_art = BoltArt()
        self._posed: dict[tuple, Skeleton] = {}
        # The game's own small bodies brought down for whoever is not grown, and children in
        # their blankets, each kept at the size it was last shown.
        self._small_frames: dict[tuple, tuple[pygame.Surface, tuple[int, int]]] = {}
        self._bundle_pictures: dict[tuple, pygame.Surface] = {}
        # Resident the player asked to draw. The game shell picks it up.
        self.requested_editor: str | None = None
        # The pieces everybody is seen in while armour is being tried out (P66). Only how they
        # are shown: who wears what is not yet something the settlement knows.
        self.trying_on: tuple[str, ...] = ()
        # Building the player asked to draw. Kept separate from resident drawings.
        self.requested_building_editor: str | None = None
        # Item definition picked in a resident's or container's inventory.
        self.requested_item_editor: str | None = None
        # The discovery there is to name and draw, by its ID, when one has just been come to
        # or the notice of one is pressed.
        self.requested_discovery: str | None = None
        # Infrastructure requests are picked up by the game shell after event handling.
        self.requested_urbanism = False
        # The opening of a new settlement asks for the screen where its first resident is made.
        self.requested_creator = False
        # Kind of object the player asked to draw, and how good the ones to be drawn are:
        # past the first level, the drawing is of those made that good (P60).
        self.requested_object_editor: str | None = None
        self.requested_object_level = 1
        # Currency whose coin the player asked to draw, by its ID.
        self.requested_coin_editor: str | None = None
        # Whether the player asked for the families of the whole settlement.
        self.requested_family = False
        # Pictures made outside the game, and where they are put to go straight on the window.
        self.illustrations = illustrations if layers is not None else None
        self.layers = layers
        self.world = world
        self.assets = assets
        self.font = font
        self.icons = icons
        # How what residents do is shown: the clip of each kind of work, and the handles of what they hold.
        self.poses = builtin_poses()
        # How much lower than standing the top of a body is in a clip, by body plan, facing and clip.
        self._lower: dict[tuple[int, str, str], float] = {}
        self.object_sprites = ObjectSprites(assets, custom)
        # Furniture and objects somebody has drawn take the place of the game's own, kind by kind.
        self.object_art = ObjectArtStore(self.illustrations, self.object_sprites)
        # What the game draws for itself at the resolution of the window, wherever nobody has
        # drawn it (P41): every kind of object, the buildings, and the ground of the map.
        self.object_pictures = ObjectPictures()
        self._building_pictures: dict[tuple, pygame.Surface] = {}
        self._painted_ground: pygame.Surface | None = None
        # Whether the ground on show is the game's own picture of it, with the fence in it.
        self._ground_painted = False
        self.faces = faces
        # Everyone's body, and what a blow leaves lying about. Presentation only: nothing of it is saved.
        self.bodies = BodyStage(BodyRenderer(assets, builtin_plan(), faces.looks))
        drawable = self.dolls is not None and illustrations is not None and illustrations.root is not None
        self.hud = Hud(canvas, world, font, icons, faces, assets, illustrations, layers, drawable, self.voices is not None)
        # Real seconds of unpaused play, driving animations that have nothing to do with game state.
        self.time = 0.0
        # How far the current game minute has played out, from 0 to 1. Set by the game shell.
        self.tick_progress = 0.0
        # Residents taking part in an event important enough to call for the player's attention.
        self.alerts: set[str] = set()
        # Marks to show over heads for a moment: per resident, each with when it comes on and goes off.
        self._marks: dict[str, list[tuple[str, float, float]]] = {}
        # Where each resident was last drawn, for picking them with the mouse.
        self.hitboxes: dict[str, pygame.Rect] = {}
        # Where the face of each of those who are out was last drawn, in its corner of the map.
        self.away_boxes: dict[str, pygame.Rect] = {}
        # Where the bubble of what each is talking of was last drawn (P62).
        self.talk_bubbles: dict[str, pygame.Rect] = {}
        self.container_hitboxes: dict[str, pygame.Rect] = {}
        # Where each thing with something to say, or to hold, was last drawn, to be picked
        # there; why each thing that stands idle does; and where the mark of each was drawn.
        self.thing_hitboxes: dict[str, pygame.Rect] = {}
        # Where each thing there is something to do with was last drawn: a click there, with
        # somebody selected, asks what they are to do with it (P63).
        self.use_hitboxes: dict[str, pygame.Rect] = {}
        self.object_marks: dict[str, pygame.Rect] = {}
        self._idle: dict[str, str] = {}
        # Decision the player asked to open by clicking a resident. The game shell picks it up.
        self.requested_decision: str | None = None
        self._read_layout()
        # On the map itself a building with its roof on is one picture, standing on the terrain.
        self.buildings = BuildingRenderer(assets, custom)
        self.building_art = BuildingArtStore(self.illustrations, self.buildings, world.tile_map)
        # Whether buildings have their roof on from close. Off, every one of them stands open.
        self.roofs_on = True
        # Canvas position of the mouse, as far as the scene has been told.
        self.pointer: tuple[int, int] | None = None
        # What has just come out of a post, while it is seen to, and where the ring of each
        # post somebody is at was last drawn, by who is at it.
        self.pops = WorkPops()
        self.work_rings: dict[str, pygame.Rect] = {}
        # And the ring of whoever is training, which fills as the next point comes (P61).
        self.train_rings: dict[str, pygame.Rect] = {}
        # Tiles under a roof that is on this frame: what stands there is not drawn.
        self._hidden: set[Tile] = set()
        # Buildings that stand closed this frame, by room ID.
        self._closed: set[str] = set()
        self.lights = LightMap()
        width, height = minimap_size((world.tile_map.width, world.tile_map.height))
        # The part of the canvas that shows the map, and the map pixel at its top-left corner.
        self.viewport = self.hud.layout.map.copy()
        # The minimap keeps to the bottom left of the map, out of the way of what opens on the right,
        # and goes up over the dock while that is open.
        self._minimap_rect = pygame.Rect(
            self.viewport.left + MINIMAP_MARGIN, self.viewport.bottom - MINIMAP_MARGIN - height, width, height
        )
        self.hud.minimap_rect = self._minimap_rect
        self.camera = [0.0, 0.0]
        # Whoever the view keeps in its middle as they move: the resident last selected, until the
        # player moves the view by hand. `_selection_seen` is what tells a new selection from an old one.
        self.following: str | None = None
        self._selection_seen: str | None = None
        # Where the bar that says how far along a resident is with their task was last drawn,
        # by resident ID.
        self.task_bars: dict[str, pygame.Rect] = {}
        # Where the placard of each resident out in the square was drawn this frame, by resident ID.
        self.placards: dict[str, pygame.Rect] = {}
        # What sounds the player's own clicks, if anything does: given the name of what was done.
        self.sound: Callable[[str], object] | None = None
        # Whoever the player has stopped to tell something, while they are choosing what. Nobody
        # while the wheel is open about somebody who goes on with what they were told.
        self._affected: str | None = None
        # The building being looked at from inside, by room ID, and what draws it. None out on the map.
        self.inside: str | None = None
        self.interior = InteriorView(self)
        # Whoever is being watched out of the settlement, by their ID, and what draws them
        # walking there. Nobody out on the map (P68).
        self.outside: str | None = None
        self.expedition = ExpeditionView(self)
        # Where the sign of each building that can be gone into was last drawn, by room ID.
        self.sign_boxes: dict[str, pygame.Rect] = {}
        # Whether the minimap was on show when a building was gone into, to put it back on coming out.
        self._minimap_kept = False
        # Whoever has come to trade, as a body to draw. They are no resident: the settlement keeps
        # no more of them than where they stand.
        self._visitor_body: Resident | None = None
        # Whoever stands at the gate asking to be let in, as bodies to draw, by their ID. They
        # are no residents yet, and may never be.
        self._gate_bodies: dict[str, Resident] = {}
        # Where on the canvas the left button went down on the map and where the mouse last was
        # with it held, and whether it has moved far enough since to be dragging.
        self._press: tuple[int, int] | None = None
        self._drag_last: tuple[int, int] | None = None
        self._dragging = False
        # Whoever that press landed on, to be taken up if the mouse moves off with the button
        # held: whether it is a child in its blanket, and their ID. And whoever is in the
        # player's hand, while somebody is (P27).
        self._press_on: tuple[bool, str] | None = None
        self.carry: Carry | None = None
        # Where each child in its blanket was last drawn, for taking it up with the mouse.
        self.bundle_boxes: dict[str, pygame.Rect] = {}
        # Index into ZOOM_TILE_SIZES.
        self.zoom = DEFAULT_ZOOM
        # What is being drawn this frame: the visible part of the map at the size of its art, where
        # that part starts on the map, and what goes on top of it once it is on the canvas.
        self._scene = self.terrain
        self._scene_origin = (0, 0)
        self._overlays: list[Callable[[], None]] = []
        self._buffers: dict[tuple[tuple[int, int], bool], pygame.Surface] = {}
        commons = world.rooms.get("commons")
        entry = next(iter(world.entry_tiles()), None)
        if commons is not None:
            self.centre_on((commons.x + commons.width / 2, commons.y + commons.height / 2))
        elif entry is not None:
            # A map with no plaza is first seen from where people come in.
            self.centre_on((entry[0] + 0.5, entry[1] + 0.5))

    @property
    def typing(self) -> bool:
        """Whether what is typed is being written down somewhere, and so is no shortcut."""
        return (self.inside is not None and self.interior.naming is not None) or self.hud.typing

    def handle_event(self, event: pygame.event.Event) -> None:
        if self.hud.writing_words and event.type == pygame.KEYDOWN:
            self._words_key(event)
            return
        if self.hud.typing and event.type == pygame.KEYDOWN:
            self._fund_key(event)
            return
        if self.typing and event.type == pygame.KEYDOWN:
            self._name_key(event)
            return
        if self.carry is not None and self._carry_event(event):
            return
        if self.outside is not None and self._outside_event(event):
            return
        if event.type == pygame.KEYDOWN and event.key == pygame.K_i:
            self.toggle_inside()
            return
        if self.inside is not None and self._inside_event(event):
            return
        if event.type == pygame.KEYDOWN and event.key == pygame.K_l:
            self._apply(LOG_INTENT)
        elif event.type == pygame.KEYDOWN and event.key == pygame.K_j:
            self._apply(JOBS_INTENT)
        elif event.type == pygame.KEYDOWN and event.key == pygame.K_e:
            self._apply(RESEARCH_INTENT)
        elif event.type == pygame.KEYDOWN and event.key == pygame.K_p:
            self._apply(GOVERNMENT_INTENT)
        elif event.type == pygame.KEYDOWN and event.key == pygame.K_f:
            self._apply(FUND_INTENT)
        elif event.type == pygame.KEYDOWN and event.key == pygame.K_k:
            self._apply(POWER_INTENT)
        elif event.type == pygame.KEYDOWN and event.key == pygame.K_h:
            self._apply(WORDS_INTENT)
        elif event.type == pygame.KEYDOWN and event.key == pygame.K_c:
            self.centre_on_resident(self.hud.selected_id)
            self.following = self.hud.selected_id
        elif event.type == pygame.KEYDOWN and event.key == pygame.K_g:
            self.jump_to_attention()
        elif event.type == pygame.KEYDOWN and event.key == pygame.K_t:
            self.roofs_on = not self.roofs_on
            self.hud.notify(ROOFS_ON if self.roofs_on else ROOFS_OFF)
        elif event.type == pygame.KEYDOWN and event.key == pygame.K_n:
            self._apply(MINIMAP_INTENT)
        elif event.type == pygame.KEYDOWN and event.key == pygame.K_u:
            self._apply(URBANISM_INTENT)
        elif event.type == pygame.KEYDOWN and event.key == pygame.K_F2:
            self._apply(DRAW_INTENT)
        elif event.type == pygame.KEYDOWN and event.key == pygame.K_F4:
            self._apply(BUILD_INTENT)
        elif event.type == pygame.KEYDOWN and event.key == pygame.K_F3:
            self._apply(VOICE_INTENT)
        elif event.type == pygame.KEYDOWN and event.key == pygame.K_F6:
            self._apply(MANNERS_INTENT)
        elif event.type == pygame.KEYDOWN and event.key == pygame.K_F7:
            self._apply(FAMILY_INTENT)
        elif event.type == pygame.KEYDOWN and event.key in ZOOM_KEYS:
            self.set_zoom(self.zoom + ZOOM_KEYS[event.key])
        elif event.type == pygame.MOUSEWHEEL:
            # The wheel zooms towards whatever is under the mouse, one step per notch.
            steps = (event.y > 0) - (event.y < 0)
            self.set_zoom(self.zoom + steps, canvas_position(pygame.mouse.get_pos()))
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 3 and self.hud.wheel.open:
            # The other button goes a step back in the wheel, and out of it from its first step.
            self._sound("click")
            self._affect_back(close=False)
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            self.pointer = canvas_position(event.pos)
            if self._on_map(self.pointer):
                # On the map a press may be the start of a drag. It is a click once the button
                # comes up without the mouse having gone anywhere.
                self._press, self._drag_last, self._dragging = self.pointer, self.pointer, False
                self._press_on = self._grab_at(self.pointer)
            else:
                self.click(self.pointer)
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            press, dragged = self._press, self._dragging
            self._press, self._drag_last, self._dragging, self._press_on = None, None, False, None
            if press is not None and not dragged:
                self.click(press)
        elif event.type == pygame.MOUSEMOTION:
            self.pointer = canvas_position(event.pos)
            if self._press is not None and self._drag_last is not None:
                if not self._dragging:
                    self._dragging = max(abs(self.pointer[axis] - self._press[axis]) for axis in (0, 1)) >= DRAG_START
                    if self._dragging and self._press_on is not None:
                        # Pulled away from somebody, it is them that come along and not the map.
                        self._take_up(*self._press_on)
                        return
                if self._dragging:
                    # Dragging pulls the map along with the mouse, from where it was pressed.
                    self.pan(self._drag_last[0] - self.pointer[0], self._drag_last[1] - self.pointer[1])
                    self._drag_last = self.pointer
            elif event.buttons[RIGHT_MOUSE_BUTTON]:
                # So does the right button, which clicks on nothing.
                self.pan(-event.rel[0] / SCALE, -event.rel[1] / SCALE)

    # ----- inside a building -----

    def enterable(self, room_id: str | None) -> bool:
        """Whether a room is a building that can be gone into: one with a roof over it."""
        room = self.world.rooms.get(room_id or "")
        return room is not None and room.roofed

    def enter(self, room_id: str) -> bool:
        """Look at a building from inside, in place of the map. Says whether there was such a building."""
        if not self.enterable(room_id):
            return False
        self.come_back()
        if self.inside is None:
            self._minimap_kept = self.hud.minimap_rect is not None
        self.inside = room_id
        # There is no map to find one's way on in there.
        self.hud.minimap_rect = None
        self._press, self._drag_last, self._dragging, self._press_on = None, None, False, None
        return True

    def leave(self) -> None:
        """Go back out to the map."""
        if self.inside is None:
            return
        self.inside = None
        self.interior.naming = None
        self.interior.decorating, self.interior.decor_held, self.interior.decor_removing = False, None, False
        self.hud.minimap_rect = self._minimap_rect if self._minimap_kept else None

    def toggle_inside(self) -> None:
        """Go into the building under the pointer, or the one whoever is selected is in. From inside, come out."""
        if self.inside is not None:
            self.leave()
            return
        tiles: list[Tile] = []
        if self.pointer is not None and self.viewport.collidepoint(self.pointer) and not self.hud.covers(self.pointer):
            x, y = self._map_point(self.pointer)
            tiles.append((int(x // TILE_SIZE), int(y // TILE_SIZE)))
        selected = self.world.residents.get(self.hud.selected_id or "")
        if selected is not None and not selected.away:
            tiles.append(selected.tile)
        for tile in tiles:
            room_id = next((room_id for room_id in self.roof_tiles if self._is_at(room_id, tile)), None)
            if room_id is not None and self.enter(room_id):
                self._sound("open")
                return
        self.hud.notify(NOWHERE_TO_ENTER)

    # ----- beyond the fence -----

    def watch(self, resident_id: str | None) -> bool:
        """Look at somebody who is out of the settlement, walking, in place of the map. Says
        whether there was such a one."""
        resident = self.world.residents.get(resident_id or "")
        if resident is None or not resident.away:
            return False
        self.leave()
        if self.hud.wheel.open:
            self._close_wheel()
        if self.outside is None:
            self._minimap_kept = self.hud.minimap_rect is not None
        self.outside = resident.resident_id
        # There is no map to find the way on out there.
        self.hud.minimap_rect = None
        self._press, self._drag_last, self._dragging, self._press_on = None, None, False, None
        return True

    def come_back(self) -> None:
        """Go back to the map from watching somebody who is out."""
        if self.outside is None:
            return
        self.outside = None
        self.hud.minimap_rect = self._minimap_rect if self._minimap_kept else None

    def _outside_event(self, event: pygame.event.Event) -> bool:
        """Take what the mouse does while somebody is watched out of the settlement. Says whether it did."""
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            self.pointer = canvas_position(event.pos)
            self.click(self.pointer)
            return True
        if event.type == pygame.MOUSEMOTION:
            self.pointer = canvas_position(event.pos)
            return True
        # There is no map out there to drag about, to see from nearer or to go into a building of.
        return event.type in (pygame.MOUSEBUTTONUP, pygame.MOUSEBUTTONDOWN, pygame.MOUSEWHEEL) or (
            event.type == pygame.KEYDOWN and (event.key in ZOOM_KEYS or event.key == pygame.K_i)
        )

    def _click_outside(self, position: tuple[int, int]) -> None:
        """A press while somebody is watched out of the settlement: the way back, somebody
        else who is out, or whoever is walking there."""
        if self.expedition.click(position) == LEAVE_TRIP_INTENT:
            self._sound("click")
            self.come_back()
            return
        if self.hud.covers(position):
            return
        boxes = (*self.hitboxes.items(), *self.away_boxes.items())
        picked = [rid for rid, rect in boxes if rect.collidepoint(position)]
        if not picked:
            return
        self._sound("select")
        self.hud.select_resident(picked[-1])
        # Another face of those who are out is another trip to look at.
        self.watch(picked[-1])
        decision = self._decision_of(picked[-1])
        if decision is not None:
            # Stopped at something they have come on: what to do about it is asked there and then.
            self.requested_decision = decision

    def _render_outside(self, resident: Resident) -> None:
        """The frame while somebody is watched out of the settlement: them walking where the
        map was, and everything round it."""
        self.hitboxes = {}
        self.container_hitboxes = {}
        self.thing_hitboxes = {}
        self.use_hitboxes = {}
        self.object_marks = {}
        self._idle = {}
        self.task_bars = {}
        self.work_rings = {}
        self.train_rings = {}
        self.placards = {}
        self.talk_bubbles = {}
        self.hud.spoken = None
        self.sign_boxes = {}
        self.bundle_boxes = {}
        self.expedition.render(resident)
        self.hud.render()
        self._draw_away()

    def _inside_event(self, event: pygame.event.Event) -> bool:
        """Take what the mouse does while a building is being looked at from inside. Says whether it did."""
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            self.pointer = canvas_position(event.pos)
            # Whoever the press is on comes along if the mouse is pulled away with it held.
            pressed_on = self._grab_at(self.pointer)
            self.click(self.pointer)
            if self.inside is not None:
                self._press, self._press_on = self.pointer, pressed_on
            return True
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 3 and self.hud.wheel.open:
            self._sound("click")
            self._affect_back(close=False)
            return True
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 3:
            # The other button puts down whatever is in hand.
            self.interior.decor_held, self.interior.decor_removing = None, False
            return True
        if event.type == pygame.MOUSEMOTION:
            self.pointer = canvas_position(event.pos)
            if self._press is not None and self._press_on is not None and event.buttons[0]:
                if max(abs(self.pointer[axis] - self._press[axis]) for axis in (0, 1)) >= DRAG_START:
                    self._take_up(*self._press_on)
            return True
        if event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            self._press, self._press_on = None, None
        # There is no map in there to drag about or to see from nearer.
        return event.type in (pygame.MOUSEBUTTONUP, pygame.MOUSEBUTTONDOWN, pygame.MOUSEWHEEL) or (
            event.type == pygame.KEYDOWN and event.key in ZOOM_KEYS
        )

    def _click_inside(self, position: tuple[int, int]) -> None:
        room = self.world.rooms.get(self.inside or "")
        intent = self.interior.click(room, position) if room is not None else None
        if intent == LEAVE_INTENT:
            self._sound("click")
            self.leave()
        elif intent is not None:
            self._sound("click")
            self._house(room, intent)
        elif self.interior.covers(position):
            # A press on the board that is on nothing of it is no press on the room behind.
            return
        elif self.interior.decorating and room is not None:
            # While the building is being dressed, a press on the room is to put down or to take away.
            if not self.hud.covers(position):
                self._decorate_at(room, position)
        elif not self.hud.covers(position) and self.viewport.collidepoint(position):
            picked = [rid for rid, rect in self.hitboxes.items() if rect.collidepoint(position)]
            kept = [object_id for object_id, rect in self.thing_hitboxes.items() if rect.collidepoint(position)]
            if self.hud.wheel.open:
                self._click_past_wheel(picked[-1] if picked else None)
                return
            if picked and self._asks_for_wheel(picked[-1]):
                self._toggle_affect()
                return
            if picked:
                self._sound("select")
                self.hud.select_resident(picked[-1])
                self._hear(picked[-1])
            elif any(rect.collidepoint(position) for rect in self.use_hitboxes.values()) and self._ring_of(
                [object_id for object_id, rect in self.use_hitboxes.items() if rect.collidepoint(position)][-1]
            ):
                # With somebody selected, a thing they could do something with asks what (P63).
                return
            else:
                # What things are kept in is looked into from in here, as it was under the roof,
                # and so is anything else with something to say of itself.
                self.hud.select_object(kept[-1] if kept else None)
            decision = self._decision_of(self.hud.selected_id)
            if decision is not None:
                self.requested_decision = decision

    def _house(self, room: Room, intent: Hashable) -> None:
        """Do what was pressed on the board of the building being looked at from inside."""
        interior, world, room_id = self.interior, self.world, room.room_id
        result = None
        if intent == HOUSE_INTENT:
            # Out of dressing it, the board comes back; otherwise it opens and shuts.
            interior.board_open = True if interior.decorating else not interior.board_open
            interior.naming = None
            interior.decorating, interior.decor_held, interior.decor_removing = False, None, False
        elif intent in (DECOR_INTENT, DECOR_DONE_INTENT):
            interior.decorating = intent == DECOR_INTENT and not interior.decorating
            interior.naming, interior.decor_held, interior.decor_removing = None, None, False
        elif intent == DECOR_REMOVE_INTENT:
            interior.decor_removing, interior.decor_held = not interior.decor_removing, None
        elif isinstance(intent, tuple) and intent[0] == "decor_tab":
            interior.decor_tab, interior.decor_held, interior.decor_removing = intent[1], None, False
        elif isinstance(intent, tuple) and intent[0] == "decor_pick" and intent[1] == DECOR_FLOORS:
            result = world.apply_command(SurfaceCommand(room_id, floor=intent[2]))
        elif isinstance(intent, tuple) and intent[0] == "decor_pick" and intent[1] == DECOR_WALLS:
            result = world.apply_command(SurfaceCommand(room_id, wall=intent[2]))
        elif isinstance(intent, tuple) and intent[0] == "decor_pick":
            # Pressed again, what was in hand is put down.
            held = (intent[1], intent[2])
            interior.decor_held, interior.decor_removing = (None if interior.decor_held == held else held), False
        elif intent == HOUSE_RENAME_INTENT:
            # Pressed again, the name is left as it was.
            interior.naming = None if interior.naming is not None else ""
        elif intent == HOUSE_USE_INTENT:
            result = world.apply_command(NameBuildingCommand(room_id, None, next_use(world, room_id)))
        elif intent == HOUSE_LOCK_INTENT:
            result = world.apply_command(LockHouseCommand(room_id, room_id not in world.homes.locked))
        elif isinstance(intent, tuple) and intent[0] == "house_owner":
            owners = world.housing.owners(world, room_id)
            chosen = [each for each in owners if each != intent[1]] if intent[1] in owners else [*owners, intent[1]]
            result = world.apply_command(GiveHouseCommand(room_id, tuple(chosen)))
        if result is not None:
            self.hud.notify(result.message)
            if not result.ok:
                self._sound("refuse")

    def _decorate_at(self, room: Room, position: tuple[int, int]) -> None:
        """Put what is in hand down where the room was pressed, or take away the ornament that is there."""
        interior, world = self.interior, self.world
        result = None
        if interior.decor_removing:
            spot = interior.spot_under(room, position)
            ornament = world.decor.at(world, room.room_id, *spot) if spot is not None else None
            if ornament is not None:
                result = world.apply_command(UndecorateCommand(room.room_id, ornament.ornament_id))
        elif interior.decor_held is not None and interior.decor_held[0] == DECOR_ORNAMENTS:
            place = interior.held_place(room, position)
            if place is not None:
                result = world.apply_command(DecorateCommand(room.room_id, interior.decor_held[1], place[0], place[1]))
        elif interior.decor_held is not None and interior.decor_held[0] == DECOR_FURNITURE:
            tile = interior.held_tile(room, position)
            if tile is not None:
                self._order_furniture(room, interior.decor_held[1], tile)
        if result is not None:
            self.hud.notify(result.message)
            self._sound("click" if result.ok else "refuse")

    def _order_furniture(self, room: Room, kind: str, tile: Tile) -> None:
        """Put it to somebody that they make a piece of furniture in a building: whoever is
        selected, or else whoever lives there, one after another until one of them will."""
        world = self.world
        selected = self.hud.selected_id
        asked = [selected] if selected in world.residents else world.housing.owners(world, room.room_id)
        if not asked:
            self.hud.notify(NOBODY_TO_MAKE_IT)
            self._sound("refuse")
            return
        for resident_id in asked:
            result = world.apply_command(ProposeObjectCommand(kind, tile, resident_id))
            if result.ok:
                break
        self.hud.notify(result.message)
        self._sound("click" if result.ok else "refuse")

    def _name_key(self, event: pygame.event.Event) -> None:
        """A key while a name is being written for the building: it goes into the name, ends it or drops it."""
        interior = self.interior
        written = interior.naming or ""
        if event.key == pygame.K_ESCAPE:
            interior.naming = None
        elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
            interior.naming = None
            if written.strip() and self.inside is not None:
                result = self.world.apply_command(NameBuildingCommand(self.inside, written))
                self.hud.notify(result.message)
        elif event.key == pygame.K_BACKSPACE:
            interior.naming = written[:-1]
        else:
            letter = getattr(event, "unicode", "")
            if letter and letter.isprintable() and len(written) < NAME_LENGTH:
                interior.naming = written + letter

    def _render_inside(self, room: Room) -> None:
        """The frame while a building is looked at from inside: the room where the map was, and everything round it."""
        self.hitboxes = {}
        self.container_hitboxes = {}
        self.thing_hitboxes = {}
        self.use_hitboxes = {}
        self.object_marks = {}
        self._idle = marks_of(self.world)
        self.task_bars = {}
        self.train_rings = {}
        self.placards = {}
        self.talk_bubbles = {}
        self.hud.spoken = None
        self.sign_boxes = {}
        self.bundle_boxes = {}
        self.interior.render(room)
        self._seat_wheel()
        self.hud.render()
        self._draw_carry()

    def update(self, dt: float) -> None:
        if not self.world.clock.paused:
            self.time += dt
            self.bodies.update(dt, self.world)
        self.expedition.update(dt, self.world.residents.get(self.outside or ""))
        self.hud.update(dt)
        self.hud.pointer = self.pointer
        self.pops.take(self.world, self.time)
        self._keep_listening()
        self._carry_on(dt)
        pressed = pygame.key.get_pressed()
        for (dx, dy), keys in SCROLL_KEYS.items():
            if any(pressed[key] for key in keys):
                self.pan(dx * SCROLL_SPEED * dt, dy * SCROLL_SPEED * dt)
        self._follow(dt)
        self._voice_what_is_said()

    def _voice_what_is_said(self) -> None:
        """Have whoever is selected say out loud the words of the bubble over them, as it comes
        up. A line that finds another being said goes unsaid."""
        spoken = self.hud.spoken
        if spoken != self._spoken_seen:
            self._spoken_seen = spoken
            if spoken is not None and self.voices is not None:
                self.voices.say(*spoken)

    def _follow(self, dt: float) -> None:
        """Keep whoever is selected in the middle of the view, catching up with them smoothly."""
        selected = self.hud.selected_id
        if selected != self._selection_seen:
            # Somebody else was just selected: the view goes with them from now on.
            self._selection_seen = self.following = selected
        resident = self.world.residents.get(self.following or "")
        if resident is None or resident.away:
            return
        x, y, _, _ = self._walk_state(resident)
        target = ((x + 0.5) * TILE_SIZE, (y + 0.5) * TILE_SIZE)
        for axis in (0, 1):
            wanted = target[axis] - self.viewport.size[axis] / 2 * TILE_SIZE / self.tile_px
            gap = wanted - self.camera[axis]
            share = 1.0 if abs(gap) <= FOLLOW_SNAP else min(1.0, FOLLOW_RATE * dt)
            self.camera[axis] += gap * share
        self.scroll(0, 0)

    def _on_map(self, position: tuple[int, int]) -> bool:
        """Whether a canvas position is on the map itself, with nothing of the HUD over it."""
        return self.viewport.collidepoint(position) and not self.hud.covers(position) and self.hud.click(position) is None

    def pan(self, dx: float, dy: float) -> None:
        """Move the view by hand, by a distance in canvas pixels. It lets go of whoever it was following."""
        self.following = None
        self.scroll(dx, dy)

    @property
    def tile_px(self) -> int:
        """Canvas pixels a tile takes at the current zoom."""
        return ZOOM_TILE_SIZES[self.zoom]

    @property
    def overview(self) -> bool:
        """True when the map is seen from as far as it goes."""
        return self.zoom == 0

    def scroll(self, dx: float, dy: float) -> None:
        """Move the view over the map by a distance in canvas pixels, stopping at its edges."""
        for axis, distance in enumerate((dx, dy)):
            in_view = self.viewport.size[axis] * TILE_SIZE / self.tile_px
            limit = max(0.0, self.terrain.get_size()[axis] - in_view)
            moved = self.camera[axis] + distance * TILE_SIZE / self.tile_px
            self.camera[axis] = min(max(moved, 0.0), limit)

    def centre_on(self, tile: tuple[float, float]) -> None:
        """Put a map tile in the middle of the view, as far as the map's edges allow."""
        self._show_at((tile[0] * TILE_SIZE, tile[1] * TILE_SIZE), self.viewport.center)

    def centre_on_resident(self, resident_id: str | None) -> None:
        resident = self.world.residents.get(resident_id or "")
        if resident is not None:
            self.centre_on((resident.x + 0.5, resident.y + 0.5))

    def set_zoom(self, zoom: int, anchor: tuple[int, int] | None = None) -> None:
        """Change the zoom step. The part of the map at `anchor`, a canvas position, stays under it.

        Without an anchor on the map, the middle of the view is what stays in place.
        """
        if anchor is None or not self.viewport.collidepoint(anchor):
            anchor = self.viewport.center
        held = self._map_point(anchor)
        self.zoom = min(max(zoom, 0), len(ZOOM_TILE_SIZES) - 1)
        self._show_at(held, anchor)

    def _show_at(self, map_point: tuple[float, float], position: tuple[int, int]) -> None:
        """Move the view so a map pixel falls on a canvas position, as far as the map's edges allow."""
        for axis in (0, 1):
            offset = position[axis] - self.viewport.topleft[axis]
            self.camera[axis] = map_point[axis] - offset * TILE_SIZE / self.tile_px
        self.scroll(0, 0)

    def _read_layout(self) -> None:
        """Make the pictures that depend on where the walls and roofs are. Again whenever a building goes up."""
        tile_map, rooms = self.world.tile_map, self.world.rooms
        tileset = Tileset(self.assets.image(SETTLEMENT_SHEET, size=SETTLEMENT_SHEET_SIZE), SETTLEMENT_CELLS)
        self.terrain = render_terrain(tile_map, tileset)
        # What stands on the ground, without the ground: it goes over an illustrated one.
        self.raised_terrain = render_terrain(tile_map, tileset, without=GROUND_TILES)
        # The tiles that roofs cover, and the same terrain with those roofs on, which is what the minimap shows.
        self.roofs = roof_names(tile_map, rooms.values())
        roof_tiles = Tileset(self.assets.image(ROOF_SHEET, size=ROOF_SHEET_SIZE), ROOF_CELLS)
        self.roofed_terrain = render_roofs(self.terrain, self.roofs, roof_tiles)
        self.roof_tiles: dict[str, set[Tile]] = {
            room.room_id: set(roof_names(tile_map, [room])) for room in rooms.values() if room.roofed
        }
        self._minimap = minimap_base(self.roofed_terrain, (tile_map.width, tile_map.height))
        # Whatever the game had drawn of the ground and the buildings is of the map as it was.
        self._painted_ground = None
        self._building_pictures = {}

    def on_events(self, events: Iterable[DomainEvent]) -> None:
        """React to what the simulation just emitted."""
        events = list(events)
        if any(event.event_type == FINISHED_EVENT and event.data.get("kind") == BUILDING_SITE for event in events):
            # A building has gone up while the map was on show: its walls and its roof are new.
            self._read_layout()
        self.hud.on_events(events)
        self.bodies.on_events(self.world, events)
        for event in events:
            if event.importance >= self.hud.intervention_from:
                self.alerts.update(event.participants)
            if event.event_type == REACTION_EVENT:
                self._mark(str(event.data.get("resident_id")), TASTE_MARKS.get(str(event.data.get("reaction"))))
            elif event.event_type == FOUND_OUT_EVENT:
                self._mark(str(event.data.get("resident_id")), FOUND_OUT_MARK)
            elif event.event_type == SUBJECT_TAKEN_EVENT:
                # How what was talked of went down is seen over whoever listened, as a meal is.
                self._mark(str(event.data.get("resident_id")), TASTE_MARKS.get(str(event.data.get("reaction"))))
            elif event.event_type == BORN_EVENT and self.hud.drawable and self.dolls is not None:
                # Somebody has been born: the next thing is to draw them, as the adult they will be.
                child_id = str(event.data.get("child_id") or "")
                if child_id in self.world.bundles and self.dolls.get(child_id) is None:
                    self.requested_editor = child_id
            elif event.event_type == FOUND_EVENT:
                # Somebody has come to something new at their job: the next thing is to say what it is.
                found = str(event.data.get("discovery") or "")
                if found in self.world.discoveries and not self.world.discoveries[found].named:
                    self.requested_discovery = found
            elif event.event_type == ACCIDENT_EVENT and event.participants:
                self._mark(event.participants[0], ACCIDENT_MARK)
            elif event.event_type == WEDDING_EVENT:
                for resident_id in event.participants:
                    self._mark(resident_id, WEDDING_MARK, WEDDING_SECONDS)
            elif event.event_type == TAKEN_EVENT and event.participants:
                # How it was taken is seen over their head: swallowed, sniffed, injected or smoked.
                self._mark(event.participants[0], ROUTE_MARKS.get(str(event.data.get("route")), TAKEN_MARK))
            elif event.event_type == NEWCOMER_EVENT and event.participants and self.world.housing.applies(self.world):
                # Whoever comes to stay has no house until they are given one (S41).
                newcomer = self.world.residents.get(event.participants[0])
                if newcomer is not None:
                    self.hud.notify(NO_HOUSE_YET.format(name=newcomer.name))
        # Someone asking for advice may be off screen: bring them into view, unless the view is
        # with somebody the player chose to follow. The notice at the top says who is waiting.
        for decision in self.world.decisions.values():
            if self.following is None and any(decision.resident_id in event.participants for event in events):
                self.centre_on_resident(decision.resident_id)
                break

    def _mark(self, resident_id: str, icon: str | None, seconds: float = MARK_SECONDS) -> None:
        """Have a mark shown over a resident for a moment, after any that is waiting to be."""
        if icon is None:
            return
        waiting = [mark for mark in self._marks.get(resident_id, []) if mark[2] > self.time]
        if len(waiting) >= MARKS_WAITING or any(mark[0] == icon for mark in waiting):
            return
        start = max([self.time, *(mark[2] for mark in waiting)])
        self._marks[resident_id] = [*waiting, (icon, start, start + seconds)]

    def mark_over(self, resident_id: str) -> str | None:
        """The mark showing over a resident right now, if any."""
        return next(
            (icon for icon, start, end in self._marks.get(resident_id, []) if start <= self.time < end), None
        )

    def needing_attention(self) -> list[str]:
        """Residents the player should look at, the most pressing first.

        Whoever waits for advice, then whoever is in the middle of something serious, then the hurt.
        """
        waiting = [decision.resident_id for decision in self.world.decisions.values()]
        involved = [resident_id for resident_id in self.world.residents if resident_id in self.alerts]
        hurt = [
            resident_id for resident_id, resident in self.world.residents.items() if resident.health < HURT_HEALTH
        ]
        return [resident_id for resident_id in dict.fromkeys([*waiting, *involved, *hurt]) if resident_id in self.world.residents]

    def jump_to_attention(self) -> str | None:
        """Select and show the next resident who needs attention, going round them one by one."""
        waiting = self.needing_attention()
        if not waiting:
            self.hud.notify(NOBODY_NEEDS_ATTENTION)
            return None
        current = self.hud.selected_id
        chosen = waiting[(waiting.index(current) + 1) % len(waiting)] if current in waiting else waiting[0]
        self.hud.select_resident(chosen)
        self.centre_on_resident(chosen)
        return chosen

    def looked_into(self) -> set[str]:
        """Roofed rooms that stand open this frame.

        From the map a building is always shut (S40): what is in it is seen by going in, and
        who is in it by their faces on its roof. Only the key that takes every roof off opens
        them, and then all at once.
        """
        if self.overview or self.roofs_on:
            return set()
        return set(self.roof_tiles)

    def _is_at(self, room_id: str, tile: Tile) -> bool:
        """Whether a tile is under a building's roof or in the wall in front of it, door included."""
        room = self.world.rooms[room_id]
        in_front = tile[1] == room.y + room.height and room.x - 1 <= tile[0] <= room.x + room.width
        return tile in self.roof_tiles[room_id] or in_front

    def _seat_minimap(self) -> None:
        """Keep the minimap at the foot of the map."""
        self._minimap_rect.bottom = self.viewport.bottom - MINIMAP_MARGIN

    def click(self, position: tuple[int, int]) -> None:
        """Handle a left click at a canvas position: a button, the minimap, a resident, or empty ground."""
        self._seat_minimap()
        intent = self.hud.click(position)
        minimap = self.hud.minimap_rect
        if intent is not None:
            self._sound("click")
            self._apply(intent)
        elif self.outside is not None:
            self._click_outside(position)
        elif self.inside is not None:
            self._click_inside(position)
        elif minimap is not None and minimap.collidepoint(position):
            self.following = None
            self.centre_on(tile_at(minimap, position))
        elif not self.hud.covers(position) and self.viewport.collidepoint(position):
            # The resident drawn last is in front, so it is the one picked.
            picked = [rid for rid, rect in self.hitboxes.items() if rect.collidepoint(position)]
            if self.hud.wheel.open:
                # With the wheel open, a click on somebody else says who, and on anything else shuts it.
                self._click_past_wheel(picked[-1] if picked else None)
                return
            visitor = self.visitor()
            sign = next((room_id for room_id, box in self.sign_boxes.items() if box.collidepoint(position)), None)
            if sign is not None and self.enter(sign):
                # A click on the sign of a building is to go into it.
                self._sound("open")
                return
            if picked and visitor is not None and picked[-1] == visitor.resident_id:
                # Whoever has come to trade is nobody to select: a click on them is to deal with them.
                self._sound("open")
                self.hud.open_trade()
            elif picked and picked[-1] in self._gate_bodies:
                # Nor is whoever knocks at the gate: a click on them is to hear whoever answers it.
                self._sound("open")
                self.requested_decision = self.gate_decision()
                return
            elif picked and self.watch(picked[-1]):
                # A face of those who are out: a click on it is to see them walking there.
                self._sound("open")
                self.hud.select_resident(picked[-1])
            elif picked and self._asks_for_wheel(picked[-1]):
                # A second click on whoever is selected opens the wheel about them.
                self._toggle_affect()
                return
            elif picked:
                self._sound("select")
                self.hud.select_resident(picked[-1])
                self._hear(picked[-1])
            else:
                # With somebody selected, a thing they could do something with asks what (P63).
                usable = [object_id for object_id, rect in self.use_hitboxes.items() if rect.collidepoint(position)]
                if usable and self._ring_of(usable[-1]):
                    return
                # A thing with something to say of itself, or to hold: the one drawn last is in front.
                things = [object_id for object_id, rect in self.thing_hitboxes.items() if rect.collidepoint(position)]
                self.hud.select_object(things[-1] if things else None)
            decision = self._decision_of(self.hud.selected_id)
            if decision is not None:
                self.requested_decision = decision

    def _hear(self, resident_id: str) -> None:
        """Somebody has just been picked: if they want a word of the player it is heard out,
        and if they are talking of something, what it is is said (P62)."""
        resident = self.world.residents.get(resident_id)
        ask = next((each for each in self.world.words.asks if each.resident_id == resident_id), None)
        if ask is not None:
            self._words(("words_ask", ask.ask_id))
            return
        said = talk_line(self.world, resident) if resident is not None else None
        if said is not None:
            self.hud.notify(said)

    def _decision_of(self, resident_id: str | None) -> str | None:
        """ID of the open decision waiting on this resident, if any."""
        return next(
            (d.decision_id for d in self.world.decisions.values() if d.resident_id == resident_id), None
        )

    def _apply(self, intent: Hashable) -> None:
        if intent == PAUSE_INTENT:
            self.world.apply_command(SetPausedCommand(not self.world.clock.paused))
        elif intent == LOG_INTENT:
            self.hud.toggle_log()
        elif intent == JOBS_INTENT:
            self.hud.toggle_jobs()
        elif intent == STORES_INTENT:
            self.hud.toggle_stores()
        elif intent == RESEARCH_INTENT:
            self.hud.toggle_research()
        elif intent == GOVERNMENT_INTENT:
            self.hud.toggle_government()
        elif intent == FUND_INTENT:
            self.hud.toggle_fund()
        elif intent == POWER_INTENT:
            self.hud.toggle_power()
        elif intent == WORDS_INTENT:
            self.hud.toggle_words()
        elif intent in (WORDS_GIVE_INTENT, WORDS_BACK_INTENT) or (isinstance(intent, tuple) and str(intent[0]).startswith("words_")):
            self._words(intent)
        elif isinstance(intent, tuple) and intent[0] == "resource":
            self._open_resource(intent[1])
        elif isinstance(intent, tuple) and intent[0] == "switch":
            # What runs on current is the player's to switch on and off (S55).
            self._say(self.world.apply_command(SwitchCommand(intent[1], intent[2])))
        elif isinstance(intent, tuple) and intent[0] == "upgrade":
            # Making a thing better is put to whoever keeps it, who says yes or no.
            self._say(self.world.apply_command(ProposeUpgradeCommand(intent[1])))
        elif isinstance(intent, tuple) and intent[0] == "compost":
            # Compost goes on a bed at the player's word, from wherever it is kept (S65).
            self._say(self.world.apply_command(CompostCommand(intent[1])))
        elif isinstance(intent, tuple) and intent[0] == "redraw":
            placed = self.world.interactables.get(intent[1])
            if placed is not None and self.object_art.available:
                self.requested_object_editor, self.requested_object_level = placed.kind, placed.level
        elif isinstance(intent, tuple) and intent[0] == "redraw_ask":
            asked, self.hud.redraw = self.hud.redraw, None
            if intent[1] and asked is not None and self.object_art.available:
                self.requested_object_editor, self.requested_object_level = asked.kind, asked.level
        elif isinstance(intent, tuple) and intent[0] == "fund":
            self._fund(intent[1:])
        elif isinstance(intent, tuple) and intent[0] == "trade_sale":
            self._propose_sale(intent[1], intent[2])
        elif isinstance(intent, tuple) and intent[0] == "choose_government":
            self._choose_government(intent[1])
        elif intent == GIVE_OPEN_INTENT:
            # What there is to give is what the Almacén lists (P65).
            if not self.hud.stores_open:
                self.hud.toggle_stores()
        elif isinstance(intent, tuple) and intent[0] == "give":
            if self.hud.selected_id in self.world.residents:
                self._said(self.world.apply_command(GiveCommand(self.hud.selected_id, intent[1])))
        elif intent == DISCOVERY_INTENT:
            waiting = self.world.crafts.waiting(self.world)
            self.requested_discovery = waiting[0].discovery_id if waiting else None
        elif isinstance(intent, tuple) and intent[0] == "government_tab":
            self.hud.government_tab, self.hud.government_armed, self.hud.sentence_armed = intent[1], None, None
        elif isinstance(intent, tuple) and intent[0] == "sentence":
            self._sentence(intent[1], intent[2])
        elif isinstance(intent, tuple) and intent[0] == "accuse":
            # The player accuses of what is known of somebody, as anybody who knows it may (S28).
            self._say(self.world.apply_command(AccuseCommand(intent[1], intent[2])))
        elif isinstance(intent, tuple) and intent[0] in ("ration", "ration_item"):
            self._ration(intent)
        elif isinstance(intent, tuple) and intent[0] in ("law_degree", "law_item", "law_enact", "law_repeal"):
            self._law(intent)
        elif isinstance(intent, tuple) and intent[0] == "trade_step":
            self.hud.trade_step(intent[1], intent[2], intent[3])
        elif intent == TRADE_DEAL_INTENT:
            self._close_deal()
        elif intent == TRADE_DRAW_INTENT and self.dolls is not None:
            definition = self.world.merchants.definition(self.world)
            self.requested_editor = definition.keeper_id if definition is not None and definition.keeper_id else None
        elif intent == TRADE_CART_INTENT and self.illustrations is not None and self.illustrations.root is not None:
            definition = self.world.merchants.definition(self.world)
            self.requested_object_editor = definition.cart if definition is not None else None
        elif intent == URBANISM_INTENT:
            self.requested_urbanism = True
        elif intent == CREATOR_INTENT:
            self.requested_creator = True
        elif intent == TUTORIAL_DRAW_INTENT:
            self._draw_for_the_step()
        elif intent == ACKNOWLEDGE_INTENT:
            self.world.apply_command(AcknowledgeTutorialCommand())
        elif intent == DRAW_INTENT and self.dolls is not None:
            # Whoever is selected, or else the first resident there is.
            self.requested_editor = self.hud.selected_id or next(iter(self.world.residents), None)
        elif intent == BUILD_INTENT and self.illustrations is not None and self.illustrations.root is not None:
            self.requested_building_editor = self._building_to_draw()
        elif intent == VOICE_INTENT and self.voices is not None:
            self.requested_voice = self.hud.selected_id or next(iter(self.world.residents), None)
        elif intent == MANNERS_INTENT:
            self.requested_manners = self.hud.selected_id or next(iter(self.world.residents), None)
        elif intent == PANEL_TAB_INTENT:
            self.hud.toggle_panel_tab()
        elif intent == PANEL_KIN_INTENT:
            self.hud.toggle_panel_kin()
        elif intent == PANEL_MOOD_INTENT:
            self._sound("click")
            self.hud.toggle_panel_mood()
        elif intent == FAMILY_INTENT:
            self.requested_family = True
        elif intent == AFFECT_INTENT:
            self._toggle_affect()
        elif intent in (CLOSE_INTENT, BACK_INTENT):
            self._affect_back(intent == CLOSE_INTENT)
        elif intent == WILL_INTENT:
            self._toggle_will()
        elif isinstance(intent, tuple) and intent[0] == "affect_branch":
            wheel = self.hud.wheel
            wheel.branch, wheel.kind, wheel.person = intent[1], None, None
        elif isinstance(intent, tuple) and intent[0] == "affect_person":
            self._affect_person(intent[1])
        elif isinstance(intent, tuple) and intent[0] == "order_cancel":
            self._cancel_order(intent[1])
        elif isinstance(intent, tuple) and intent[0] == "affect":
            self._affect(intent[1], None)
        elif isinstance(intent, tuple) and intent[0] == "thing_panel":
            # From the ring of a thing to what there is to say of it.
            self._close_wheel()
            self.hud.select_object(intent[1])
        elif isinstance(intent, tuple) and intent[0] == "affect_target":
            self._affect(intent[1], intent[2])
        elif isinstance(intent, tuple) and intent[0] == "scrap":
            # What is nobody's is broken up there and then. What is somebody's is theirs to say.
            self.hud.notify(self.world.apply_command(ScrapItemCommand(intent[1])).message)
        elif intent == TASTE_DEBUG_INTENT:
            self.hud.taste_debug = not self.hud.taste_debug
        elif intent == ROSTER_INTENT:
            # Nobody in particular: the panel goes back to listing everybody.
            self.hud.select_resident(None)
        elif intent == MINIMAP_INTENT:
            self.hud.minimap_rect = None if self.hud.minimap_rect is not None else self._minimap_rect
            self.hud.notify(MINIMAP_ON if self.hud.minimap_rect is not None else MINIMAP_OFF)
        elif isinstance(intent, tuple) and intent[0] == "select":
            self.hud.select_resident(intent[1])
            self.centre_on_resident(intent[1])
            decision = self._decision_of(intent[1])
            if decision is not None:
                self.requested_decision = decision
        elif isinstance(intent, tuple) and intent[0] == "edit_item":
            self.requested_item_editor = intent[1]
        elif isinstance(intent, tuple) and intent[0] == "suggest":
            self._suggest_job(intent[1])
        elif isinstance(intent, tuple) and intent[0] == "put":
            # Putting somebody to a post from the board is an order, as it is from the wheel.
            self._affect(PUT_KIND, intent[1])
        elif intent == PUSH_POST_INTENT:
            self._affect(PUSH_KIND, None)
        elif intent == LEAVE_POST_INTENT:
            self._affect(LEAVE_KIND, None)
        elif isinstance(intent, tuple) and intent[0] == "study":
            # What is studied is the player's to say. Whoever holds the post gets on with it.
            self.hud.notify(self.world.apply_command(SetResearchCommand(intent[1])).message)
        elif isinstance(intent, tuple) and intent[0] == "speed":
            self.world.apply_command(SetSpeedCommand(intent[1]))
        elif isinstance(intent, tuple) and intent[0] == "zoom":
            self.set_zoom(self.zoom + intent[1])

    def _draw_for_the_step(self) -> None:
        """Ask for the drawing the step of the opening in hand wants: of someone, of a building or of an object."""
        step = self.world.guide.current(self.world)
        if step is None:
            return
        if step.focus == DOLL_FOCUS:
            self.requested_editor = self.hud.selected_id or next(iter(self.world.residents), None)
        elif step.focus == BUILDING_ART_FOCUS:
            self.requested_building_editor = self._building_to_draw()
        else:
            self.requested_object_editor = owed_object(self.world)

    def _building_to_draw(self) -> str | None:
        """The roofed building currently in context, or the first one on the map."""
        candidates: list[tuple[int, int]] = []
        selected = self.world.residents.get(self.hud.selected_id or "")
        if selected is not None and not selected.away:
            candidates.append(selected.tile)
        if self.pointer is not None and self.viewport.collidepoint(self.pointer):
            x, y = self._map_point(self.pointer)
            candidates.append((int(x // TILE_SIZE), int(y // TILE_SIZE)))
        roofed = [room for room in self.world.rooms.values() if room.roofed]
        for tile in candidates:
            for room in roofed:
                if self._is_at(room.room_id, tile):
                    return room.room_id
        return roofed[0].room_id if roofed else None

    def in_view(self) -> tuple[set[str], list[str]]:
        """What can be seen of the settlement right now: the kinds of object, and who is there.
        For whoever sounds it: nothing here is drawn."""
        if self.outside is not None:
            # Out there with somebody, nothing of the settlement is in sight.
            return set(), []
        region = self._visible_region()

        def seen(x: int, y: int) -> bool:
            return region.collidepoint(x * TILE_SIZE + TILE_SIZE // 2, y * TILE_SIZE + TILE_SIZE // 2)

        kinds = {placed.kind for placed in self.world.interactables.values() if seen(placed.x, placed.y)}
        people = [
            resident_id
            for resident_id, resident in self.world.residents.items()
            if not resident.away and seen(resident.x, resident.y)
        ]
        return kinds, people

    def _sound(self, what: str) -> None:
        """Sound something the player did with their own hand, if there is anything to sound it with."""
        if self.sound is not None:
            self.sound(what)

    def _asks_for_wheel(self, resident_id: str) -> bool:
        """Whether a click on a resident on the map is the second one on them, which opens the
        wheel: they are who is selected, and have nothing waiting on the player to be heard first."""
        return resident_id == self.hud.selected_id and self._decision_of(resident_id) is None

    def _seat_wheel(self) -> None:
        """Tell the wheel where whoever is selected stands on the screen, to be laid out about them."""
        box = self.hitboxes.get(self.hud.selected_id or "")
        if self.hud.wheel.thing is not None:
            # The ring of a thing is laid out about the thing.
            box = self.use_hitboxes.get(self.hud.wheel.thing) or box
        self.hud.wheel.centre = box.center if box is not None else self.viewport.center

    def _toggle_affect(self) -> None:
        """Open the wheel about whoever is selected, or shut it and let them go. It stops them
        to be told something, unless they are at something they were told: then they go on
        with it, and what is said waits its turn."""
        resident_id = self.hud.selected_id
        if resident_id is None:
            return
        if self.hud.wheel.open:
            self._close_wheel()
            return
        waiting = self.world.construction.waiting_for_material(self.world, self.world.residents[resident_id])
        error = self.world.affect.obstacle(self.world, resident_id)
        held = error is None and not self.world.affect.busy(self.world, resident_id)
        if held:
            result = self.world.apply_command(HoldResidentCommand(resident_id))
            error = None if result.ok else result.message
        if error is not None:
            self._sound("refuse")
            self.hud.notify(error)
            return
        self._sound("open")
        self._affected = resident_id if held else None
        salvage = f"{TASK}:{SALVAGE}"
        if waiting is not None and any(option.kind == salvage for option in self.world.affect_options(resident_id)):
            # Somebody waiting for material is asked first what they may take apart for it.
            self.hud.wheel.show(resident_id, TASKS, salvage)
        else:
            self.hud.wheel.show(resident_id)

    def _ring_of(self, object_id: str) -> bool:
        """With somebody selected, open the ring of what they can do with a thing (P63). They
        are stopped to be told, as the wheel stops them. False where there is nobody to do
        anything, or nothing they could be told: the thing then shows what there is to say
        of it, as ever."""
        resident_id = self.hud.selected_id
        resident = self.world.residents.get(resident_id or "")
        placed = self.world.interactables.get(object_id)
        if resident is None or placed is None or self.world.affect.obstacle(self.world, resident.resident_id) is not None:
            return False
        if not self.world.affect.things_to_do(self.world, resident, placed):
            return False
        if self.hud.wheel.open:
            self._close_wheel()
        held = not self.world.affect.busy(self.world, resident.resident_id)
        if held and not self.world.apply_command(HoldResidentCommand(resident.resident_id)).ok:
            return False
        self._sound("open")
        self._affected = resident.resident_id if held else None
        self.hud.wheel.show(resident.resident_id, thing=object_id)
        return True

    def _close_wheel(self) -> None:
        """Shut the wheel. Whoever was stopped for it goes about their day, or on to what they were told."""
        if self._affected is not None:
            self.world.apply_command(ReleaseResidentCommand(self._affected))
        self._affected = None
        self.hud.wheel.shut()

    def _affect_back(self, close: bool) -> None:
        """Go a step back in what is being said, or with nothing chosen yet let them go."""
        if close or not self.hud.wheel.back():
            self._close_wheel()

    def _affect_person(self, other_id: str) -> None:
        """Turn the wheel to what whoever is selected can be told to do with one person."""
        resident_id = self.hud.selected_id
        other = self.world.residents.get(other_id)
        if resident_id is None or other is None:
            return
        if not self.world.affect_with(resident_id, other_id):
            self._sound("refuse")
            self.hud.notify(NOTHING_WITH.format(name=other.name))
            return
        wheel = self.hud.wheel
        wheel.branch, wheel.kind, wheel.person = SOCIAL, None, other_id

    def _click_past_wheel(self, other_id: str | None) -> None:
        """A click on the map while the wheel is open: on somebody else, it says who what is
        being chosen is with; on whoever it is about, or on nobody, it shuts it."""
        self._sound("click")
        wheel = self.hud.wheel
        if other_id is None or other_id == self.hud.selected_id or other_id not in self.world.residents:
            self._close_wheel()
        elif wheel.kind is not None and wheel.kind.partition(":")[0] in SHARED:
            self._affect(wheel.kind, other_id)
        elif wheel.kind is None:
            self._affect_person(other_id)

    def _affect(self, kind: str, target_id: str | None) -> None:
        """Tell whoever is selected what was chosen, or go on to who or what it is about."""
        resident_id = self.hud.selected_id
        if resident_id is None:
            return
        option = next((each for each in self.world.affect_options(resident_id) if each.kind == kind), None)
        if option is not None and option.targets and target_id is None:
            self.hud.wheel.kind = kind
            return
        result = self.world.apply_command(AffectCommand(resident_id, kind, target_id))
        self.hud.notify(result.message)
        self._sound("order" if result.ok else "refuse")
        if result.ok:
            self._close_wheel()

    # ----- picked up and put down (P27) -----

    def _in_hand(self, resident: Resident) -> bool:
        """Whether a resident is the one the player is carrying about."""
        carry = self.carry
        return carry is not None and not carry.bundle and carry.who == resident.resident_id and self.pointer is not None

    def _bundle_in_hand(self, bundle: Bundle) -> bool:
        carry = self.carry
        return carry is not None and carry.bundle and carry.who == bundle.child_id

    def _hand_tile(self) -> tuple[float, float]:
        """Where, in tiles, whoever hangs from the pointer counts as standing: their feet a
        little under it."""
        x, y = self._map_point(self.pointer or self.viewport.center)
        return spot_tile(x, y + HANG)

    def _hang(self, skeleton: Skeleton, pivot: tuple[float, float]) -> None:
        """Swing a skeleton that has just been posed about the point it is held by."""
        if self.carry is None or not self.carry.angle:
            return
        joints = skeleton.joints
        swung = hung({name: (joint.x, joint.y) for name, joint in joints.items()}, pivot, self.carry.angle)
        for name, (x, y) in swung.items():
            joints[name].x = joints[name].px = x
            joints[name].y = joints[name].py = y

    def _grab_at(self, position: tuple[int, int]) -> tuple[bool, str] | None:
        """Whoever a press at a place on the canvas would take hold of: a child in its
        blanket before whoever has it on their back, and of two residents the one in front.
        Nobody while something is being said to somebody."""
        if self.hud.wheel.open or self.hud.covers(position) or self.interior_covers(position):
            return None
        child = [child_id for child_id, box in self.bundle_boxes.items() if box.collidepoint(position)]
        if child and child[-1] in self.world.bundles:
            return (True, child[-1])
        people = [
            resident_id
            for resident_id, box in self.hitboxes.items()
            if box.collidepoint(position) and resident_id in self.world.residents
        ]
        return (False, people[-1]) if people else None

    def interior_covers(self, position: tuple[int, int]) -> bool:
        """Whether a place on the canvas is under the board of the building being looked at from inside."""
        return self.inside is not None and self.interior.covers(position)

    def _take_up(self, bundle: bool, who: str) -> None:
        """Take somebody up off the map into the hand. Time stands still while they are in it."""
        self._press, self._drag_last, self._dragging, self._press_on = None, None, False, None
        error = None if bundle else self.world.placing.obstacle(self.world, who)
        if bundle and who not in self.world.bundles:
            return
        if error is not None:
            self._sound("refuse")
            self.hud.notify(error)
            return
        if self.hud.wheel.open:
            self._close_wheel()
        self.carry = Carry(who, bundle, paused=self.world.clock.paused)
        # The view stays where it is: it would run after its own hand otherwise.
        self.following = None
        self.world.apply_command(SetPausedCommand(True))
        self._sound("select")
        self._look_under_hand()

    def _end_carry(self) -> None:
        """The hand is empty again, and time goes on as it did before."""
        carry, self.carry = self.carry, None
        if carry is not None:
            self.world.apply_command(SetPausedCommand(carry.paused))

    def _let_go_of(self) -> None:
        """Let go of whoever is in the hand without putting them anywhere: they are where they were."""
        if self.carry is not None:
            self._sound("close")
            self._end_carry()

    def _carry_event(self, event: pygame.event.Event) -> bool:
        """Take what the mouse and the keys do while somebody is in the hand. Says whether it did."""
        carry = self.carry
        if event.type == pygame.MOUSEMOTION:
            self.pointer = canvas_position(event.pos)
            return True
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                self._let_go_of()
            elif event.key == pygame.K_TAB:
                # On to whatever else could come of letting go here.
                self._look_under_hand()
                carry.turn()
                self._sound("click")
            elif event.key == pygame.K_i and self.inside is not None:
                # Back out with them: out there, too, a click puts them down.
                self.leave()
                carry.sticky = True
            # The map can still be seen from nearer or further. Nothing else is opened meanwhile.
            return event.key not in ZOOM_KEYS or self.inside is not None
        if event.type == pygame.MOUSEWHEEL:
            return self.inside is not None
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 3:
            self._let_go_of()
            return True
        released = event.type == pygame.MOUSEBUTTONUP and event.button == 1 and not carry.sticky
        clicked = event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 and carry.sticky
        if released or clicked:
            self.pointer = canvas_position(event.pos)
            self._put_down()
        return event.type in (pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP)

    def _carry_on(self, dt: float) -> None:
        """A moment of having somebody in the hand: they swing from it, the view goes along
        when the hand is at its edge, and what is under it is looked at again."""
        carry = self.carry
        if carry is None:
            return
        if carry.who not in (self.world.bundles if carry.bundle else self.world.residents):
            self._end_carry()
            return
        if not self.world.clock.paused:
            self.world.apply_command(SetPausedCommand(True))
        if self.pointer is None:
            return
        carry.swing(float(self.pointer[0]), dt)
        if self.inside is None:
            for axis in (0, 1):
                low, high = self.viewport.topleft[axis], self.viewport.bottomright[axis] - 1
                pull = (self.pointer[axis] >= high - EDGE) - (self.pointer[axis] <= low + EDGE)
                if pull:
                    self.pan(*(pull * SCROLL_SPEED * dt if each == axis else 0.0 for each in (0, 1)))
        self._look_under_hand()

    def _under_hand(self) -> Target | None:
        """What the hand is over, as it was last drawn: somebody, a building with its roof
        on, a thing, a site, or only the ground. None over nothing somebody could be put on."""
        carry, position = self.carry, self.pointer
        if carry is None or position is None or not self.viewport.collidepoint(position):
            return None
        if self.hud.covers(position) or self.interior_covers(position):
            return None
        people = [
            resident_id
            for resident_id, box in self.hitboxes.items()
            if box.collidepoint(position) and resident_id in self.world.residents and resident_id != carry.who
        ]
        if people:
            return Target(other_id=people[-1], box=self.hitboxes[people[-1]])
        if self.inside is not None:
            room = self.world.rooms.get(self.inside)
            kept = [object_id for object_id, box in self.container_hitboxes.items() if box.collidepoint(position)]
            tile = self.interior.tile_under(room, position) if room is not None else None
            if kept:
                return Target(object_id=kept[-1], tile=tile, box=self.container_hitboxes[kept[-1]])
            return Target(tile=tile, box=self._tile_box(tile)) if tile is not None else None
        x, y = self._map_point(position)
        tile = (int(x // TILE_SIZE), int(y // TILE_SIZE))
        room_id = next((each for each, box in self.sign_boxes.items() if box.collidepoint(position)), None)
        room_id = room_id or next((each for each in self._closed if tile in self.roof_tiles[each]), None)
        if room_id is not None and self.enterable(room_id):
            return Target(room_id=room_id, tile=tile, box=self._canvas_rect(building_area(self.world.rooms[room_id])))
        things = []
        for placed in self.world.interactables.values():
            definition = self.world.definition_of(placed)
            if (placed.x, placed.y) in self._hidden:
                continue
            if not (definition.blocks or definition.seat or definition.salvage is not None):
                # What is only walked over, as the plaza is, is the ground it lies on.
                continue
            box = self._canvas_rect(self._object_area(placed))
            if box.collidepoint(position):
                things.append((box.bottom, placed.object_id, box))
        if things:
            _bottom, object_id, box = max(things, key=lambda each: each[:2])
            return Target(object_id=object_id, tile=tile, box=box)
        site = next((each for each in self.world.sites.values() if tile in each.tiles), None)
        box = self._canvas_rect(pygame.Rect(tile[0] * TILE_SIZE, tile[1] * TILE_SIZE, TILE_SIZE, TILE_SIZE))
        if site is not None:
            return Target(site_id=site.site_id, tile=tile, box=box)
        return Target(tile=tile, box=box)

    def _look_under_hand(self) -> None:
        """Work out again what the hand is over and what could come of letting go there."""
        carry = self.carry
        if carry is None:
            return
        target = self._under_hand()
        if target is None or target.room_id is not None:
            carry.over(target, [])
            return
        if carry.target is not None and carry.target.key == target.key and carry.found:
            # Nothing moves while somebody is in the hand: it is as it was a moment ago.
            carry.over(target, carry.found)
            return
        if carry.bundle:
            found = self.world.bundle_placements(carry.who, target.other_id, target.object_id, target.tile)
        else:
            found = self.world.placements(carry.who, target.object_id, target.other_id, target.site_id, target.tile)
        carry.over(target, found)

    def _put_down(self) -> None:
        """Let go of whoever is in the hand over what it is over. Over a building with its
        roof on, it is gone into with them still in the hand, to be put down in there. Where
        they cannot be put they are back where they were."""
        carry = self.carry
        if carry is None:
            return
        self._look_under_hand()
        target, chosen = carry.target, carry.chosen
        if target is not None and target.room_id is not None and self.inside is None and self.enter(target.room_id):
            carry.sticky = True
            carry.over(None, [])
            self._sound("open")
            return
        if target is None or chosen is None or not chosen.ok:
            self._sound("refuse")
            if target is not None:
                self.hud.notify(chosen.text if chosen is not None else NOWHERE)
            if not carry.sticky or target is None:
                self._end_carry()
            return
        if carry.bundle:
            command = PutBundleCommand(carry.who, target.other_id, target.object_id, target.tile)
        else:
            command = PutDownCommand(
                carry.who, target.object_id, target.other_id, target.site_id, target.tile, chosen.kind
            )
        self._end_carry()
        result = self.world.apply_command(command)
        if not result.ok:
            self._sound("refuse")
            self.hud.notify(result.message)
            return
        self._sound("click" if result.kind in (STAND, LAY) else "order")
        if carry.bundle:
            return
        # Whoever was put down is who is looked at now, without the view running after them.
        self.hud.select_resident(carry.who)
        self._selection_seen, self.following = carry.who, None
        if result.other_id is not None:
            # Put down by somebody, it is asked at once what the two are to do.
            self._toggle_affect()
            if self.hud.wheel.open:
                self._affect_person(result.other_id)
        elif result.thing_id is not None:
            # Put down by a thing that is for nothing in particular, it is asked what they do there (P63).
            self._ring_of(result.thing_id)

    def _draw_carry(self) -> None:
        """What is said by the hand while somebody is in it: what it is over, picked out,
        where they would be stood, and what would come of letting go."""
        carry, pointer = self.carry, self.pointer
        if carry is None or pointer is None:
            return
        target, chosen = carry.target, carry.chosen
        into = None
        if target is not None and target.room_id is not None:
            room = self.world.rooms[target.room_id]
            into = INTO.format(name=room.name.capitalize(), who=self._name_in_hand())
        lines, ok = caption(carry, into)
        self.canvas.set_clip(self.viewport)
        if target is not None and target.box is not None:
            # A thing, somebody or a building is picked out. Bare ground only where it will not do.
            named = target.object_id or target.other_id or target.site_id or target.room_id
            if named or not ok:
                draw_pick(self.canvas, target.box, ok)
        stood = self._tile_box(chosen.tile) if chosen is not None and chosen.tile is not None else None
        if stood is not None:
            draw_footing(self.canvas, stood)
        self.canvas.set_clip(None)
        draw_caption(self.canvas, self.font, lines, ok, pointer, self.canvas.get_rect())

    def _tile_box(self, tile: Tile) -> pygame.Rect | None:
        """Where a tile of the map is on the canvas, out on the map or in the building being looked at."""
        if self.inside is None:
            return self._canvas_rect(pygame.Rect(tile[0] * TILE_SIZE, tile[1] * TILE_SIZE, TILE_SIZE, TILE_SIZE))
        room = self.world.rooms.get(self.inside)
        return self.interior.tile_box(room, tile) if room is not None else None

    def _name_in_hand(self) -> str:
        carry = self.carry
        if carry is None:
            return ""
        held = (self.world.bundles if carry.bundle else self.world.residents).get(carry.who)
        return held.name if held is not None else ""

    def _toggle_will(self) -> None:
        """Have whoever is selected do nothing of their own accord, or give them their will back."""
        resident = self.world.residents.get(self.hud.selected_id or "")
        if resident is None:
            return
        result = self.world.apply_command(SetFreeWillCommand(resident.resident_id, not resident.free_will))
        self.hud.notify(result.message)
        self._sound("order" if result.ok else "refuse")

    def _cancel_order(self, index: int) -> None:
        """Take back one of the things whoever is selected has been told to do."""
        resident_id = self.hud.selected_id
        if resident_id is None:
            return
        result = self.world.apply_command(CancelOrderCommand(resident_id, index))
        self.hud.notify(result.message)
        self._sound("click" if result.ok else "refuse")

    def _keep_listening(self) -> None:
        """While the player is choosing what to say, whoever was stopped goes on standing there.
        With somebody else selected, or them gone or no longer to be told anything, the wheel
        shuts and they are let go."""
        wheel = self.hud.wheel
        if not wheel.open:
            if self._affected is not None:
                self.world.apply_command(ReleaseResidentCommand(self._affected))
                self._affected = None
            return
        resident_id = self.hud.selected_id
        if resident_id != wheel.about or self.world.affect.obstacle(self.world, resident_id or "") is not None:
            self._close_wheel()
        elif self._affected is not None and not self.world.affect.is_held(self.world, resident_id):
            if not self.world.apply_command(HoldResidentCommand(resident_id)).ok:
                self._close_wheel()

    def _law(self, intent: tuple) -> None:
        """Something pressed beside a law on the government's panel: how far it would go, what
        it would name, putting it or doing away with it. How it comes in is the government's."""
        hud = self.hud
        law = self.world.registries.laws.laws.get(intent[1])
        if law is None:
            return
        if intent[0] == "law_degree":
            degree = picked_degree(self.world, law, hud.law_degrees) + int(intent[2])
            hud.law_degrees[law.law_id] = max(0, min(degree, len(law.degrees) - 1))
            return
        if intent[0] == "law_item":
            options = named_items(self.world)
            now = picked_params(self.world, law, hud.law_items).get("item", "")
            if options:
                hud.law_items[law.law_id] = options[(options.index(now) + 1) % len(options) if now in options else 0]
            return
        if intent[0] == "law_enact":
            command = ProposeCommand(
                ENACT_LAW, law=law.law_id, degree=picked_degree(self.world, law, hud.law_degrees),
                params=picked_params(self.world, law, hud.law_items),
            )
        else:
            command = ProposeCommand(REPEAL_LAW, law=law.law_id)
        result = self.world.apply_command(command)
        hud.notify(result.message)
        if result.ok:
            hud.law_degrees.pop(law.law_id, None)
        else:
            self._sound("refuse")

    def _sentence(self, trial_id: str, punishment_id: str) -> None:
        """Say what somebody found guilty is given (S28). A harsh one is pressed for twice:
        there is no taking it back."""
        hud = self.hud
        definition = self.world.registries.justice.punishments.get(punishment_id)
        if definition is not None and definition.harsh and hud.sentence_armed != (trial_id, punishment_id):
            hud.sentence_armed = (trial_id, punishment_id)
            hud.notify(HARSH_SENTENCE.format(name=definition.name))
            return
        hud.sentence_armed = None
        self._say(self.world.apply_command(SentenceCommand(trial_id, punishment_id)))

    def _ration(self, intent: tuple) -> None:
        """Change what prisoners are given each day: one more or fewer of a thing, or another
        thing of that kind."""
        ration = self.world.justice.ration(self.world)
        meals, drinks, food, drink = ration.meals, ration.drinks, ration.food, ration.drink
        if intent[0] == "ration":
            meals += int(intent[2]) if intent[1] == RATION_MEALS else 0
            drinks += int(intent[2]) if intent[1] == RATION_DRINKS else 0
        elif intent[1] == RATION_FOOD:
            food = next_ration_item(self.world, RATION_FOOD)
        else:
            drink = next_ration_item(self.world, RATION_DRINK)
        self._say(self.world.apply_command(SetPrisonRationCommand(meals, drinks, food, drink)))

    def _choose_government(self, government_id: str) -> None:
        """Give the settlement a kind of government. It is asked for twice: once to say which, and once to mean it."""
        if self.hud.government_armed != government_id:
            self.hud.government_armed = government_id
            return
        self.hud.government_armed = None
        result = self.world.apply_command(ChooseGovernmentCommand(government_id))
        self.hud.notify(result.message)
        if not result.ok:
            self._sound("refuse")

    def _fund(self, what: tuple) -> None:
        """Something pressed on the board of the fund: a thing set about, the advice it is put
        with, or the way out of it. What comes of it is the residents' to say."""
        hud, entry = self.hud, self.hud.fund_entry
        made = self.world.trading.currency
        action = what[0]
        if action == "propose":
            hud.fund_entry = FundEntry(CURRENCY)
        elif action == "barter":
            hud.fund_entry = FundEntry(BARTER_BACK)
        elif action == "rename" and made is not None:
            hud.fund_entry = FundEntry(RENAME, made.name, made.singular)
        elif action == "cancel":
            hud.fund_entry = None
        elif action == "field" and entry is not None:
            entry.field = what[1]
        elif action == "draw" and made is not None and hud.drawable:
            self.requested_coin_editor = made.currency_id
        elif action == "name_it" and entry is not None:
            self._settle_fund(RenameCurrencyCommand(entry.name, entry.singular or None), entry)
        elif action == "advise" and entry is not None:
            if entry.mode == BARTER_BACK:
                self._settle_fund(ProposeBarterCommand(what[1]), entry)
            else:
                self._settle_fund(ProposeCurrencyCommand(entry.name, entry.singular or None, what[1]), entry)

    def _settle_fund(self, command, entry: FundEntry) -> None:
        """Send what was set about on the board of the fund, and say what came of it."""
        if entry.written and not entry.name.strip():
            # With no name there is nothing to put to anybody: the board stays as it is.
            self.hud.notify(self.world.apply_command(command).message)
            self._sound("refuse")
            return
        result = self.world.apply_command(command)
        self.hud.fund_entry = None
        self.hud.notify(result.message)
        self._sound("click" if result.ok else "refuse")

    def _words(self, intent: tuple) -> None:
        """Something pressed on the board of words, or that opens it on something."""
        hud, world, entry = self.hud, self.world, self.hud.words_entry
        what = intent[0]
        if what == "words_ask":
            ask = world.talk.ask_of(world, intent[1])
            if ask is None:
                return
            if ask.kind == ASK_SUBJECT:
                # What to talk about is picked out of all there is, or made up.
                hud.show_words(WordsEntry(PICK, ITEMS_TAB, ask.resident_id, ask.what, ask.ask_id))
            else:
                hud.show_words(WordsEntry(ASKED, ask_id=ask.ask_id, field=ANSWER_FIELD))
        elif what == "words_dismiss":
            self._said(world.apply_command(DismissAskCommand(intent[1])))
            hud.show_words(WordsEntry())
        elif what == "words_one":
            hud.show_words(WordsEntry(ONE, resident_id=intent[1]))
        elif what == "words_pick":
            hud.show_words(WordsEntry(PICK, ITEMS_TAB, intent[1]))
        elif what == "words_with":
            hud.show_words(WordsEntry(PICK, ITEMS_TAB, entry.resident_id, intent[1]))
        elif what == "words_tab":
            entry.tab, entry.page = intent[1], 0
            entry.write("")
        elif what == "words_page":
            entry.page = max(0, min(pages(world, entry) - 1, entry.page + intent[1]))
        elif what == "words_field":
            written = ""
            if intent[1].startswith(PHRASE_FIELD):
                written = world.talk.phrase(world, entry.resident_id, intent[1][len(PHRASE_FIELD):])
            elif intent[1].startswith(NICKNAME_FIELD):
                written = world.words.nicknames.get(entry.resident_id, {}).get(intent[1][len(NICKNAME_FIELD):], "")
            entry.write(intent[1], written)
        elif what == "words_subject":
            self._talk_about(intent[1], "")
        elif intent == WORDS_GIVE_INTENT:
            self._give_words()
        elif intent == WORDS_BACK_INTENT:
            hud.show_words(WordsEntry())

    def _said(self, result) -> bool:
        """Say what came of something done with words, and sound it. Returns whether it was done."""
        self.hud.notify(result.message)
        self._sound("click" if result.ok else "refuse")
        return bool(result.ok)

    def _talk_about(self, subject: str | None, text: str) -> None:
        """Tell whoever the board is about what to talk of with the other: a subject there
        is, or a word made up on the spot. Asked for, it is the answer to what was asked."""
        world, entry = self.world, self.hud.words_entry
        wanted = new_list(world, entry) if subject is None else None
        if entry.ask_id:
            command = AnswerAskCommand(entry.ask_id, text, subject, wanted)
        else:
            command = TalkAboutCommand(entry.resident_id, entry.other_id, subject, text, wanted)
        if self._said(world.apply_command(command)):
            self.hud.toggle_words()

    def _give_words(self) -> None:
        """Give what has been written on the board of words to whoever, or whatever, it is for."""
        world, entry = self.world, self.hud.words_entry
        name, text = entry.field, entry.text
        if name == WORD_FIELD:
            tab = entry.tab if entry.tab in world.registries.talk.lists else first_list(world)
            if self._said(world.apply_command(AddWordCommand(tab, text))):
                entry.write(WORD_FIELD)
        elif name == ANSWER_FIELD:
            if self._said(world.apply_command(AnswerAskCommand(entry.ask_id, text))):
                self.hud.show_words(WordsEntry())
        elif name == SUBJECT_FIELD:
            self._talk_about(None, text)
        elif name.startswith(PHRASE_FIELD):
            if self._said(world.apply_command(SetPhraseCommand(entry.resident_id, name[len(PHRASE_FIELD):], text))):
                entry.write("")
        elif name.startswith(NICKNAME_FIELD):
            if self._said(world.apply_command(SetNicknameCommand(entry.resident_id, name[len(NICKNAME_FIELD):], text))):
                entry.write("")

    def _words_key(self, event: pygame.event.Event) -> None:
        """A key while something is being written on the board of words: it goes into it,
        gives it or drops it."""
        entry = self.hud.words_entry
        if event.key == pygame.K_ESCAPE:
            if entry.mode == ASKED:
                # What was asked is left waiting, and the board goes back to its lists.
                self.hud.show_words(WordsEntry(LISTS))
            else:
                entry.write("")
        elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
            self._give_words()
        elif event.key == pygame.K_BACKSPACE:
            entry.erase()
        else:
            entry.type(getattr(event, "unicode", ""), self.world.registries.talk.longest)

    def _fund_key(self, event: pygame.event.Event) -> None:
        """A key while a currency is being named: it goes into the name, moves on, ends it or drops it."""
        entry = self.hud.fund_entry
        if entry is None:
            return
        if event.key == pygame.K_ESCAPE:
            self.hud.fund_entry = None
        elif event.key == pygame.K_TAB:
            entry.next_field()
        elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
            if entry.mode == RENAME:
                self._fund(("name_it",))
            else:
                # A currency is put to them with an advice, and that is said with the mouse.
                entry.next_field()
        elif event.key == pygame.K_BACKSPACE:
            entry.erase()
        else:
            entry.type(getattr(event, "unicode", ""))

    def _propose_sale(self, resident_id: str, instance_id: str) -> None:
        """Put it to a resident that they sell a thing of their own to whoever is at the gate.
        Under barter what they get for it is the first thing of the merchant's put in the deal."""
        wanted = next((item_id for item_id, units in self.hud.trade_deal()[1].items() if units > 0), None)
        result = self.world.apply_command(ProposeSaleCommand(resident_id, instance_id, wanted))
        self.hud.notify(result.message)
        self._sound("click" if result.ok else "refuse")

    def _close_deal(self) -> None:
        """Do the deal chosen with whoever is at the gate, out of the fund and into it, and say what came of it."""
        sell, buy = self.hud.trade_deal()
        result = self.world.apply_command(DealWithMerchantCommand(sell=sell, buy=buy))
        self.hud.notify(result.message)
        if result.ok:
            self.hud.trade_buy, self.hud.trade_sell = {}, {}
        # A deal that is done is heard as what happened is; one that is not, as a refusal.
        if not result.ok:
            self._sound("refuse")

    def _suggest_job(self, job_id: str) -> None:
        """Put a job to the selected resident and say what came of it. The choice is theirs."""
        resident = self.world.residents.get(self.hud.selected_id or "")
        if resident is None:
            return
        before = len(self.world.history)
        outcome = self.world.apply_command(SuggestJobCommand(resident.resident_id, job_id))
        answers = [event for event in self.world.history[before:] if event.event_type == "crisis_resolved"]
        if outcome is None or not answers:
            self.hud.notify(SUGGESTION_REFUSED)
        else:
            # The event also says what advice it came with, which here is always the same.
            self.hud.notify(answers[-1].text.partition(" (")[0])

    def render(self) -> None:
        if self.layers is not None:
            self.layers.clear()
        self.canvas.fill(PALETTE["ink"])
        if self.outside is not None:
            watched = self.world.residents.get(self.outside)
            if watched is not None and watched.away:
                self._render_outside(watched)
                return
            # They are back in, or no more: the map is where to look, and where they now are.
            back = self.outside
            self.come_back()
            if watched is not None and self.hud.selected_id == back:
                self.centre_on_resident(back)
                self.following = back
        if self.inside is not None:
            room = self.world.rooms.get(self.inside)
            if room is not None and room.roofed:
                self._render_inside(room)
                return
            # It is no longer there to be inside of.
            self.leave()
        self._seat_minimap()
        region = self._visible_region()
        ground = self._ground()
        # Decide the state of buildings before making the scene: a freehand building needs an
        # alpha-capable buffer even when nobody has drawn the ground below it.
        open_rooms = self.looked_into()
        self._closed = set(self.roof_tiles) - open_rooms
        # A roof hides what is under it.
        self._hidden = set().union(*(self.roof_tiles[room_id] for room_id in self._closed))
        # What goes on the window itself, at its resolution: floors, which lie under everything,
        # and whatever stands on the ground, each with how far down the map its foot is, so
        # that whoever and whatever is nearer is drawn in front.
        floors: list[tuple[pygame.Rect, pygame.Surface]] = []
        standing: list[Standing] = self._object_pictures(region)
        # Objects, residents and buildings share one list so that whatever stands lower on screen is in front.
        draws: list[Draw] = []
        self._bundle_names: list[tuple[pygame.Surface, tuple[int, int]]] = []
        self._rough: list[Standing] = []
        for room_id in self._closed:
            room = self.world.rooms[room_id]
            area = building_area(room)
            if not area.colliderect(region):
                continue
            picture = self._building_picture(room, "closed")
            if picture is not None:
                standing.append((float(area.bottom), tuple(area), picture))
            else:
                draws.append(self._building_draw(room))
        for room_id in open_rooms:
            room = self.world.rooms[room_id]
            area = building_area(room)
            if not area.colliderect(region):
                continue
            background = self._building_picture(room, "background")
            foreground = self._building_picture(room, "foreground")
            if background is not None:
                floors.append((area, background))
            if foreground is not None:
                # The wall in front, and its door, hide the feet of whoever is inside by it.
                standing.append((area.bottom + 0.75, tuple(area), foreground))
        self._scene = self._buffer(region.size, clear=ground is not None or bool(floors) or bool(standing))
        self._scene_origin = region.topleft
        if ground is None:
            self._scene.blit(self.terrain, (0, 0), region)
        else:
            self._scene.fill(TRANSPARENT)
            if not self._ground_painted:
                # The game's own picture of the ground has the fence in it. Any other has not.
                self._scene.blit(self.raised_terrain, (0, 0), region)
        for area, picture in floors:
            # Remove only where a drawing has paint. Clear corners continue to show the ground.
            self._erase_for_picture(area, picture)
        for placed in self._standing():
            if (placed.x, placed.y) not in self._hidden:
                draws.append(self._object_draw(placed))
        for site in self.world.sites.values():
            if (site.x, site.y) not in self._hidden:
                draws.append(self._site_draw(site))
        for resident in self.world.residents.values():
            if resident.away:
                # Whoever is outside the settlement is nowhere on its map.
                continue
            # Someone under a roof is still found: their face is shown on it, as from afar.
            # Whoever is in the player's hand is wherever the hand is, roof or no roof.
            unseen = self.overview or (resident.tile in self._hidden and not self._in_hand(resident))
            draws.append(self._marker_draw(resident) if unseen else self._resident_draw(resident))
        visitor = self.visitor()
        if visitor is not None:
            draws.append(self._marker_draw(visitor) if self.overview else self._resident_draw(visitor))
        for stranger in self.strangers():
            # Whoever knocks is seen at the gate, and two who came together are seen together.
            draws.append(self._marker_draw(stranger) if self.overview else self._resident_draw(stranger))
        self.bundle_boxes = {}
        for bundle in self.world.bundles.values():
            # A child still carried is a head and a blanket, on a back or where it was put down.
            if (not self.overview and bundle.tile not in self._hidden) or self._bundle_in_hand(bundle):
                self._show_bundle(bundle, standing, draws)
        for remains in self.bodies.remains:
            # The dead are not picked out from afar, and a roof hides them like anything else.
            if not self.overview and remains.tile not in self._hidden:
                draws.append(self._remains_draw(remains))
        self.hitboxes = {}
        self.container_hitboxes = {}
        self.thing_hitboxes = {}
        self.use_hitboxes = {}
        self.object_marks = {}
        self._idle = marks_of(self.world)
        self.task_bars = {}
        self.work_rings = {}
        self.train_rings = {}
        self.placards = {}
        self.talk_bubbles = {}
        self.hud.spoken = None
        self._overlays = []
        self._doll_draws = []
        self._held = []
        self._rough = []
        for _, _, draw in sorted(draws, key=lambda entry: entry[:2]):
            draw()
        # The blanket of whoever sleeps on the ground goes on the window with everything else that stands there.
        standing.extend(self._rough)
        for name, place in self._bundle_names:
            self._overlays.append(lambda name=name, place=place: self.canvas.blit(name, place))
        stormy = self._storm(region)
        light = self._light(region)

        # Nothing of the map is drawn outside its part of the canvas.
        self.canvas.set_clip(self.viewport)
        size = (self._scaled(region.width), self._scaled(region.height))
        if ground is not None or self._doll_draws or floors or standing:
            self._show_illustrated(region, size, ground, floors, standing, stormy, light)
        else:
            if stormy:
                self._scene.fill(STORM_TINT, special_flags=pygame.BLEND_RGB_MULT)
            if light is not None:
                shade(self._scene, light)
            scene = self._scene
            if size != region.size:
                scene = pygame.transform.scale(scene, size, self._buffer(size))
            self.canvas.blit(scene, self._canvas_point(*region.topleft))
            # With nothing on the window itself, what is held goes on the canvas, as large as a canvas pixel lets it.
            corner = self._canvas_point(*region.topleft)
            zoom = self.tile_px / TILE_SIZE
            self._draw_held(self.canvas, (corner[0] - region.x * zoom, corner[1] - region.y * zoom), zoom)
        # Names, icons and faces go straight on the canvas, so they keep their size at any zoom.
        self._draw_zone_names()
        self._draw_at_gate()
        for overlay in self._overlays:
            overlay()
        self._draw_work()
        self.canvas.set_clip(None)

        self._seat_wheel()
        self.hud.render()
        self._draw_minimap(region)
        self._draw_away()
        self._draw_carry()

    def _say(self, result) -> None:
        """Say what came of something the player did, and sound it if it came to nothing."""
        if not result.ok:
            self._sound("refuse")
        self.hud.notify(result.message)

    def _open_resource(self, resource_id: str) -> None:
        """A press on a figure of the bar: what the generator burns opens the board of
        current, and anything else what the settlement holds."""
        fuel = self.world.registries.items.find(self.world.registries.power.fuel)
        burnt = self.world.ledger.resources_of(self.world, fuel) if fuel is not None else ()
        if resource_id in burnt:
            self.hud.toggle_power()
        else:
            self.hud.toggle_stores()

    def mark_thing(self, placed: Interactable, box: pygame.Rect) -> None:
        """What is seen of a thing over its picture (P60): that it is the one selected, a
        stone in the colour of its rarity when it is better than common, and that it
        stands idle and why. Drawn straight on the canvas, where it was last drawn."""
        mark = self._idle.get(placed.object_id)
        selected = placed.object_id == self.hud.selected_object
        if selected:
            pygame.draw.rect(self.canvas, PALETTE["glow"], box, 1)
        if placed.level > 1 and not self.overview:
            draw_gem(self.canvas, box, rarity_color(self.world, placed.level))
        if mark is not None:
            self.object_marks[placed.object_id] = draw_object_mark(self.canvas, box, mark)

    def _draw_work(self) -> None:
        """Each unit that has just come out of a post, for a moment, beside the ring of whoever
        made it, or over them if they have since left it."""
        for pop in self.pops.pops:
            ring = self.work_rings.get(pop.by or "")
            maker = self.hitboxes.get(pop.by or "")
            if ring is not None:
                # To the side the ring is on, clear of their name.
                spot = (ring.left - 11, ring.bottom)
            elif maker is not None:
                spot = (maker.centerx, maker.top)
            else:
                continue
            if self.viewport.collidepoint(spot):
                self.pops.draw(self.canvas, self.font, pop, spot, self.time, self.icons.small(pop.definition_id))

    def _draw_zone_names(self) -> None:
        """A sign over each named place, on the wall at its back, so that the map can be read."""
        self.sign_boxes = {}
        for room in self.world.rooms.values():
            name = room.name.upper()
            width = self.font.width(name) + 6
            height = CELL_SIZE[1] + 2
            if room.room_id in self._closed:
                # On a building that stands closed, the sign sits on the eave, over its front.
                row = room.y + room.height + 1 - FACADE_ROWS
                centre_x, top = self._canvas_point((room.x + room.width / 2) * TILE_SIZE, row * TILE_SIZE)
                top -= height + 1
            else:
                centre_x, top = self._canvas_point((room.x + room.width / 2) * TILE_SIZE, (room.y - 1) * TILE_SIZE)
            sign = pygame.Rect(centre_x - width // 2, top + 1, width, height)
            if not self.viewport.colliderect(sign):
                continue
            pointed = False
            if room.roofed and not self.overview:
                # The sign of a building is the way into it: it lights up under the pointer.
                self.sign_boxes[room.room_id] = sign
                pointed = self.pointer is not None and sign.collidepoint(self.pointer) and not self.hud.covers(self.pointer)
            draw_panel(self.canvas, sign, fill="shadow" if pointed else "ink", border="lamp" if pointed else "copper")
            self.font.draw(self.canvas, name, (sign.x + 3, sign.y + 1), PALETTE["glow" if pointed else "sand"])
            if pointed:
                hint = self.font.render(ENTER_HINT, PALETTE["glow"])
                self.canvas.blit(hint, (sign.centerx - hint.get_width() // 2, sign.bottom + 1))

    def _draw_at_gate(self) -> None:
        """What was bought from whoever came to trade waits by the gate until somebody carries it
        in: a thing of each kind, and how many there are in all."""
        waiting = self.world.at_gate
        if not waiting or self.overview:
            return
        gate = next(iter(self.world.entry_tiles()), None)
        if gate is None or gate in self._hidden:
            return
        x, y = gate
        left, top = self._canvas_point((x + 0.5) * TILE_SIZE, (y + 1) * TILE_SIZE)
        kinds = sorted(waiting)[:GATE_KINDS]
        left -= len(kinds) * (ITEM_ICON_SIZE[0] - 3) // 2
        for index, item_id in enumerate(kinds):
            place = pygame.Rect(left + index * (ITEM_ICON_SIZE[0] - 3), top - ITEM_ICON_SIZE[1], *ITEM_ICON_SIZE)
            draw_item(self.canvas, self.icons, item_id, place)
        count = self.font.render(f"x{sum(waiting.values())}", PALETTE["paper"])
        self.canvas.blit(count, (left + len(kinds) * (ITEM_ICON_SIZE[0] - 3) + 4, top - CELL_SIZE[1]))

    def _draw_away(self) -> None:
        """Whoever is outside the settlement is nowhere on the map: their faces go in a corner, to be picked there."""
        away = away_residents(self.world)
        self.away_boxes = {}
        if not away:
            return
        panel = self.hud.away_rect()
        if panel is None:
            return
        label_width = self.font.width(AWAY_LABEL)
        draw_panel(self.canvas, panel)
        self.font.draw(self.canvas, AWAY_LABEL, (panel.x + 4, panel.y + 4), PALETTE["dust"])
        x = panel.x + 4 + label_width + 4
        for resident in away:
            marker = self.faces.marker(resident.resident_id)
            spot = marker.get_rect(topleft=(x, panel.y + 2))
            self.canvas.blit(marker, spot)
            self.away_boxes[resident.resident_id] = spot
            # Whoever is being watched out there is picked where they walk.
            self.hitboxes.setdefault(resident.resident_id, spot)
            if resident.resident_id == self.hud.selected_id:
                pygame.draw.rect(self.canvas, PALETTE["glow"], spot, 1)
            x += marker.get_width() + 2

    def _ground(self) -> pygame.Surface | None:
        """The ground of this map as someone has drawn it, at the detail the window shows. None if nobody has."""
        self._ground_painted = False
        if self.illustrations is None:
            return None
        width, height = self.terrain.get_size()
        own = self.illustrations.fitted(f"map/{self.world.map_id}.png", (width * GROUND_DETAIL, height * GROUND_DETAIL))
        if own is not None or not self.windowed:
            return own
        # Nobody has: the game draws it, fence and all, the first time it is asked for.
        if self._painted_ground is None:
            seed = sum(map(ord, self.world.map_id))
            self._painted_ground = ground_pictures.ground(self.world.tile_map, TILE_SIZE * GROUND_DETAIL, seed)
        self._ground_painted = True
        return self._painted_ground

    @property
    def windowed(self) -> bool:
        """Whether there is a window under the canvas, to draw on at its resolution."""
        return self.layers is not None and bool(self.canvas.get_flags() & pygame.SRCALPHA)

    @property
    def _cell(self) -> int:
        """Pixels of the window a tile of the map takes at the zoom it is seen at."""
        return self.tile_px * (self.layers.scale if self.layers is not None else 1)

    def _building_picture(self, room: Room, part: str) -> pygame.Surface | None:
        """A building with its roof on, or with it off its floor or the wall in front of it: as
        somebody drew it, or else as the game does. None where there is no window to show either on."""
        if part == "closed":
            own = self.building_art.closed(room)
        else:
            own = self.building_art.opened(room, foreground=part == "foreground")
        if own is not None or not self.windowed:
            return own
        if self.building_art.has_parts(room):
            # Somebody has drawn some of it: what they left out stays out.
            return None
        doors = door_columns(self.world.tile_map, room)
        key = (room.room_id, part, self._cell, room.width, room.height, doors)
        if key not in self._building_pictures:
            if part == "closed":
                made = building_pictures.closed(room, self._cell, doors)
            else:
                floor = self.world.tile_map.terrain_at((room.x, room.y))
                made = building_pictures.opened(room, self._cell, doors, floor, part == "foreground")
            self._building_pictures[key] = made
        return self._building_pictures[key]

    def _game_picture(self, definition, placed: Interactable | None = None) -> ObjectPicture | None:
        """The game's own picture of a kind of object, where it is that and not somebody's
        drawing that is shown. With `placed`, as that very one looks: a bed by what grows in it."""
        level = placed.level if placed is not None else 1
        if not self.windowed or self.object_art.drawing(definition, level) is not None:
            return None
        if not self.object_pictures.has(definition.kind, definition.width, definition.height):
            return None
        frame = int(self.time * ANIMATION_FPS) % self.object_pictures.frames(definition.kind)
        way = self.world.crafts.grown_at(self.world, placed.object_id) if placed is not None else None
        return self.object_pictures.at(self.object_pictures.grown(definition.kind, way), self._cell, frame)

    def _show_illustrated(
        self,
        region: pygame.Rect,
        size: tuple[int, int],
        ground: pygame.Surface | None,
        floors: list[tuple[pygame.Rect, pygame.Surface]],
        standing: list[Standing],
        stormy: bool,
        light: pygame.Surface | None,
    ) -> None:
        """Have the map drawn on the window itself: the illustrated ground if there is one, everything
        that stands on it, and then the paper dolls, at the full resolution of the window.

        The canvas is left clear over the map, so that only names, bubbles and signs are drawn there.
        """
        layers, scene = self.layers, self._scene
        plan = self.bodies.plan
        # With many bodies in sight, only so many limbs are bent to a new shape in one frame.
        allowance = self.dolls.allowance if self.dolls is not None else None
        # Whoever and whatever stands lower on the map is in front: pictures and dolls in one order.
        ordered: list[tuple[float, int, object]] = [(entry[0], 0, entry) for entry in standing]
        ordered += [(float(entry[0]), 1, entry) for entry in self._doll_draws]
        ordered.sort(key=lambda entry: entry[:2])
        corner = self._canvas_point(*region.topleft)
        place = layers.on_screen(pygame.Rect(corner, size))
        clip = layers.on_screen(self.viewport)
        # Window pixels to a pixel of the map's art.
        detail = place.width / region.width
        source = pygame.Rect(
            region.x * GROUND_DETAIL, region.y * GROUND_DETAIL, region.width * GROUND_DETAIL, region.height * GROUND_DETAIL
        )

        def draw(screen: pygame.Surface) -> None:
            before = screen.get_clip()
            screen.set_clip(clip)
            if ground is not None:
                piece = ground.subsurface(source)
                screen.blit(piece if piece.get_size() == place.size else pygame.transform.smoothscale(piece, place.size), place)
            origin = (place.x - region.x * detail, place.y - region.y * detail)

            def show(area: tuple[float, float, float, float], picture: pygame.Surface) -> None:
                spot = pygame.Rect(
                    round(origin[0] + area[0] * detail),
                    round(origin[1] + area[1] * detail),
                    round(area[2] * detail),
                    round(area[3] * detail),
                )
                # What the game draws is made at the size it is shown. A drawing may not be.
                near = abs(picture.get_width() - spot.width) <= 1 and abs(picture.get_height() - spot.height) <= 1
                screen.blit(picture if near else pygame.transform.smoothscale(picture, spot.size), spot)

            for area, picture in floors:
                show(tuple(area), picture)
            # The pixel art keeps its hard edges however large it is shown.
            screen.blit(scene if scene.get_size() == place.size else pygame.transform.scale(scene, place.size), place)
            for _, kind, entry in ordered:
                if kind == 0:
                    show(entry[1], entry[2])
                    continue
                _, doll, skeleton, neck, grown, foot = entry
                if skeleton is not None:
                    draw_doll(screen, doll, plan, skeleton, origin, detail, allowance, grown, foot)
                    continue
                # Lying under a blanket: only the head, upright on the pillow.
                head = doll.placed(HEAD_BONE, False, detail, math.pi)
                if head is not None:
                    image, joint = head
                    screen.blit(image, (round(origin[0] + neck[0] * detail - joint[0]), round(origin[1] + neck[1] * detail - joint[1])))
            # What they hold is in front of them, and under the dark like everything else.
            self._draw_held(screen, origin, detail)
            if stormy:
                screen.fill(STORM_TINT, place, special_flags=pygame.BLEND_RGB_MULT)
            if light is not None:
                screen.blit(pygame.transform.scale(light, place.size), place, special_flags=pygame.BLEND_RGB_MULT)
            screen.set_clip(before)

        layers.under(draw)
        self.canvas.fill(TRANSPARENT, self.viewport)

    def _erase_for_picture(self, area: pygame.Rect, picture: pygame.Surface) -> None:
        """Make the scene clear under the painted pixels of a window-resolution picture."""
        local = area.move(-self._scene_origin[0], -self._scene_origin[1])
        clipped = local.clip(self._scene.get_rect())
        if clipped.width <= 0 or clipped.height <= 0:
            return
        # Work at map-art resolution. A hard alpha edge is deliberate: the high-resolution source
        # itself is what supplies the smooth edge on the window.
        small = pygame.transform.scale(picture, area.size)
        source = pygame.Rect(clipped.x - local.x, clipped.y - local.y, clipped.width, clipped.height)
        mask = pygame.mask.from_surface(small.subsurface(source))
        eraser = mask.to_surface(setcolor=(0, 0, 0, 255), unsetcolor=(0, 0, 0, 0))
        self._scene.blit(eraser, clipped, special_flags=pygame.BLEND_RGBA_SUB)

    def _storm(self, region: pygame.Rect) -> bool:
        """Under bad weather, blow streaks of dust across the scene. Returns whether there is a storm to tint it."""
        if not self.world.happenings.is_stormy(self.world):
            return False
        drift = int(self.time * STORM_SPEED)
        for index in range(STORM_STREAKS):
            # Each streak keeps its own height and length, and they all move with the wind.
            x = (index * 97 + drift * (1 + index % 3)) % (region.width + 16) - 16
            y = (index * 53 + index * index * 7) % max(1, region.height)
            pygame.draw.line(self._scene, PALETTE["sand"], (x, y), (x + 4 + index % 5, y))
        return True

    def _light(self, region: pygame.Rect) -> pygame.Surface | None:
        """What darkens the scene by the hour, with a pool of light round every fire and lamp in sight. None by day."""
        level = daylight(self.world.clock.hour, self.world.clock.minute)
        if level >= 1.0:
            return None
        flicker = int(self.time * ANIMATION_FPS) % 2
        lights = []
        for placed in self.world.interactables.values():
            definition = self.world.definition_of(placed)
            # A lamp with the power out is as dark on screen as it is for whoever stands by it.
            reach = self.world.light_of(placed)
            if reach <= 0 or (placed.x, placed.y) in self._hidden:
                continue
            centre = (
                round((placed.x + definition.width / 2) * TILE_SIZE) - region.x,
                round((placed.y + definition.height / 2) * TILE_SIZE) - region.y,
            )
            # A flame wavers; a lamp burns steady.
            wavers = self.object_sprites.frames(definition) > 1
            lights.append((centre, reach * TILE_SIZE - (BLOCK * flicker if wavers else 0)))
        return self.lights.render(region.size, level, lights)

    def _draw_minimap(self, region: pygame.Rect) -> None:
        rect = self.hud.minimap_rect
        if rect is None:
            return
        attention = set(self.needing_attention())
        blink = int(self.time * ANIMATION_FPS) % 2 == 0
        dots = {}
        for resident_id, resident in self.world.residents.items():
            if resident.away:
                continue
            color = "paper"
            if resident_id in attention:
                color = "ember" if blink else "glow"
            elif resident_id == self.hud.selected_id:
                color = "lamp"
            dots[(resident.x, resident.y)] = color
        merchant = self.world.merchant
        if merchant is not None and merchant.tile is not None:
            # Whoever has come to trade is found on it too, in a colour of their own.
            dots[merchant.tile] = "copper"
        for stranger in self._gate_bodies.values():
            dots[(stranger.x, stranger.y)] = "glow"
        view = pygame.Rect(
            region.x * TILE_PIXELS // TILE_SIZE,
            region.y * TILE_PIXELS // TILE_SIZE,
            region.width * TILE_PIXELS // TILE_SIZE,
            region.height * TILE_PIXELS // TILE_SIZE,
        )
        draw_minimap(self.canvas, rect, self._minimap, view, dots)

    def _buffer(self, size: tuple[int, int], clear: bool = False) -> pygame.Surface:
        """A surface of this size to draw a frame on, kept from one frame to the next.

        A `clear` one can be left empty where nothing is drawn, to go over something else.
        """
        key = (size, clear)
        if key not in self._buffers:
            self._buffers[key] = pygame.Surface(size, pygame.SRCALPHA) if clear else pygame.Surface(size)
        return self._buffers[key]

    def _scaled(self, pixels: int) -> int:
        """Canvas pixels that a distance in map pixels takes at the current zoom."""
        return pixels * self.tile_px // TILE_SIZE

    def _visible_region(self) -> pygame.Rect:
        """The part of the map in view, in map pixels."""
        # The view moves by whole canvas pixels, which from afar are several map pixels each.
        step = max(1, TILE_SIZE // self.tile_px)
        left, top = (int(position) // step * step for position in self.camera)
        width, height = (-(-side * TILE_SIZE // self.tile_px) for side in self.viewport.size)
        return pygame.Rect(left, top, width, height).clip(self.terrain.get_rect())

    def _canvas_point(self, map_x: float, map_y: float) -> tuple[int, int]:
        """Canvas pixel where a map pixel is drawn, on screen or off it."""
        region = self._visible_region()
        point = []
        for axis, position in enumerate((map_x, map_y)):
            # A map smaller than the view sits in the middle of it.
            spare = max(0, self.viewport.size[axis] - self._scaled(self.terrain.get_size()[axis]))
            shown_at = self._scaled(round(position) - region.topleft[axis])
            point.append(self.viewport.topleft[axis] + spare // 2 + shown_at)
        return (point[0], point[1])

    def _canvas_rect(self, area: pygame.Rect) -> pygame.Rect:
        """Where a rectangle given in map pixels is drawn on the canvas."""
        left, top = self._canvas_point(*area.topleft)
        right, bottom = self._canvas_point(*area.bottomright)
        return pygame.Rect(left, top, right - left, bottom - top)

    def _map_point(self, position: tuple[int, int]) -> tuple[float, float]:
        """Map pixel that is drawn at a canvas position."""
        region = self._visible_region()
        corner = self._canvas_point(*region.topleft)
        x, y = (
            region.topleft[axis] + (position[axis] - corner[axis]) * TILE_SIZE / self.tile_px
            for axis in (0, 1)
        )
        return (x, y)

    def _tile_pixel(self, x: float, y: float) -> tuple[int, int]:
        return self._canvas_point(x * TILE_SIZE, y * TILE_SIZE)

    def _blit(self, image: pygame.Surface, map_position: tuple[int, int]) -> None:
        """Draw an image on the scene, at a position in map pixels."""
        self._scene.blit(
            image, (map_position[0] - self._scene_origin[0], map_position[1] - self._scene_origin[1])
        )

    def _object_area(self, placed: Interactable) -> pygame.Rect:
        """Where an object is drawn, in map pixels: on its tiles, and as far above them as it rises."""
        width, height = self.object_art.frame_size(self.world.definition_of(placed))
        bottom = (placed.y + self.world.definition_of(placed).height) * TILE_SIZE
        return pygame.Rect(placed.x * TILE_SIZE, bottom - height, width, height)

    def _object_pictures(self, region: pygame.Rect) -> list[Standing]:
        """The objects in view that are shown on the window: as somebody drew them, or as the game
        does. Each part comes with how far down the map its foot is, where it goes in map
        pixels, and its picture at the size the window shows it."""
        if self.layers is None or not (self.object_art.available or self.windowed):
            return []
        shown: list[Standing] = []
        scale = self.layers.scale
        for placed in self._standing():
            if (placed.x, placed.y) in self._hidden:
                continue
            definition = self.world.definition_of(placed)
            goods = displayed_goods(self.world, placed) if definition.display_of is not None else []
            foot = float((placed.y + definition.height) * TILE_SIZE)
            game = self._game_picture(definition, placed)
            if game is not None:
                # A map pixel is this many of the picture's.
                detail = self._cell / TILE_SIZE
                width, height = game.under.get_width() / detail, game.under.get_height() / detail
                area = (float(placed.x * TILE_SIZE), foot - height, width, height)
                if not pygame.Rect(area).inflate(2, 2).colliderect(region):
                    continue
                shown.append((foot - 0.5, area, game.under))
                if game.over is not None:
                    # Whoever lies in it is drawn by its foot, between the two.
                    shown.append((foot + 0.5, area, game.over))
                side = game.slot_size / detail
                for item_id, (x, y) in zip(goods, game.slots):
                    spot = (area[0] + x / detail, area[1] + y / detail, side, side)
                    shown.append((foot - 0.4, spot, self.icons.shown(item_id, game.slot_size)))
                continue
            area = self._object_area(placed)
            if not area.colliderect(region):
                continue
            size = (self._scaled(area.width) * scale, self._scaled(area.height) * scale)
            picture = self.object_art.shown(definition, size, placed.level)
            if picture is None:
                continue
            shown.append((foot - 0.5, tuple(area), picture))
            side = self._scaled(GOODS_SIZE[0]) * scale
            for item_id, (x, y) in zip(goods, SLOTS):
                spot = (float(area.left + x), float(area.top + y), float(GOODS_SIZE[0]), float(GOODS_SIZE[1]))
                shown.append((foot - 0.4, spot, self.icons.shown(item_id, side)))
        return shown

    def visitor(self) -> Resident | None:
        """Whoever has stopped by the gate to trade, as somebody to draw and to click on. None with nobody there."""
        merchant, definition = self.world.merchant, self.world.merchants.definition(self.world)
        if merchant is None or merchant.tile is None or definition is None:
            return None
        visitor_id = definition.keeper_id or definition.event_id
        if self._visitor_body is None or self._visitor_body.resident_id != visitor_id:
            self._visitor_body = Resident(visitor_id, definition.keeper_name, x=merchant.tile[0], y=merchant.tile[1])
        body = self._visitor_body
        body.x, body.y = merchant.tile
        # They face their cart, which is where what they sell is.
        body.facing = "left" if merchant.cart is not None and merchant.cart[0] < merchant.tile[0] else "right"
        return body

    def strangers(self) -> list[Resident]:
        """Whoever stands at the gate waiting for an answer, as somebody to draw and to click on:
        side by side by the way in, if they came together. Empty with nobody there."""
        waiting = self.world.happenings.visitors(self.world)
        gate = next(iter(self.world.entry_tiles()), None)
        if not waiting or gate is None:
            self._gate_bodies = {}
            return []
        bodies = {}
        for index, newcomer in enumerate(waiting):
            body = self._gate_bodies.get(newcomer.newcomer_id)
            if body is None:
                body = Resident(newcomer.newcomer_id, newcomer.name, age=newcomer.age)
            body.x, body.y = gate[0] + index, gate[1]
            bodies[newcomer.newcomer_id] = body
        self._gate_bodies = bodies
        return list(bodies.values())

    def gate_decision(self) -> str | None:
        """ID of the decision of whoever is answering the gate, while somebody waits there."""
        return next(
            (decision.decision_id for decision in self.world.decisions.values() if decision.kind in GATE_DECISIONS), None
        )

    def _standing(self) -> list[Interactable]:
        """Everything that stands on the map: what has been placed, and the cart of whoever has come to trade."""
        placed = list(self.world.interactables.values())
        merchant, definition = self.world.merchant, self.world.merchants.definition(self.world)
        if merchant is None or merchant.cart is None or definition is None:
            return placed
        if self.world.registries.interactables.find(definition.cart or "") is None:
            return placed
        return placed + [Interactable(f"visitor:{definition.event_id}", definition.cart, *merchant.cart)]

    def _object_draw(self, placed: Interactable) -> Draw:
        definition = self.world.definition_of(placed)
        sheet = self.object_sprites.sheet(definition)
        # A picture of it on the window, somebody's or the game's, goes there by itself with
        # whatever it shows off: here there is only where it is, to be picked by.
        drawn = self.layers is not None and (
            self.object_art.drawing(definition, placed.level) is not None or self._game_picture(definition) is not None
        )
        # Whether a press on it shows what there is to say of it: the cart of whoever has
        # come to trade is no thing of the settlement's.
        kept = placed.object_id in self.world.containers
        told = kept or (placed.object_id in self.world.interactables and speaks(self.world, placed))
        # A sheet wider than the object holds animation frames side by side.
        width = definition.width * TILE_SIZE
        frame = int(self.time * ANIMATION_FPS) % self.object_sprites.frames(definition)
        image = sheet.subsurface((frame * width, 0, min(width, sheet.get_width()), sheet.get_height()))
        bottom = (placed.y + definition.height) * TILE_SIZE
        area = pygame.Rect((placed.x * TILE_SIZE, bottom - image.get_height()), image.get_size())

        goods = displayed_goods(self.world, placed) if definition.display_of is not None else []

        def draw() -> None:
            if not drawn:
                self._blit(image, area.topleft)
                for definition_id, (dx, dy) in zip(goods, SLOTS):
                    self._blit(self.icons.small(definition_id), (area.left + dx, area.top + dy))
            box = self._canvas_rect(area)
            if kept:
                self.container_hitboxes[placed.object_id] = box
            if told:
                self.thing_hitboxes[placed.object_id] = box
            if definition.uses and placed.object_id in self.world.interactables:
                self.use_hitboxes[placed.object_id] = box
            if placed.object_id in self._idle or placed.level > 1 or placed.object_id == self.hud.selected_object:
                self._overlays.append(lambda: self.mark_thing(placed, box))

        return (bottom, 0, draw)

    def _site_draw(self, site: BuildSite) -> Draw:
        """Ground marked out for something that is being put up: a string round it between four
        stakes, and along its near side how far along it is."""
        columns = [x for x, _ in site.tiles] or [site.x]
        rows = [y for _, y in site.tiles] or [site.y]
        area = pygame.Rect(
            min(columns) * TILE_SIZE,
            min(rows) * TILE_SIZE,
            (max(columns) - min(columns) + 1) * TILE_SIZE,
            (max(rows) - min(rows) + 1) * TILE_SIZE,
        )
        done = self.world.construction.fraction_done(self.world, site)

        def draw() -> None:
            rect = area.move(-self._scene_origin[0], -self._scene_origin[1])
            pygame.draw.rect(self._scene, PALETTE["ochre"], rect.inflate(-2, -2), 1)
            for corner in (rect.topleft, (rect.right - 3, rect.top), (rect.left, rect.bottom - 3), (rect.right - 3, rect.bottom - 3)):
                pygame.draw.rect(self._scene, PALETTE["bone"], (*corner, 3, 3))
            bar = pygame.Rect(rect.left + 3, rect.bottom - 6, rect.width - 6, 2)
            pygame.draw.rect(self._scene, PALETTE["shadow"], bar)
            pygame.draw.rect(self._scene, PALETTE["lichen"], (bar.left, bar.top, round(bar.width * done), bar.height))

        # Flat on the ground: whatever stands on the same row is drawn over it.
        return (area.top, -1, draw)

    def under_sign(self, resident: Resident) -> str | None:
        """What a resident is under looks like on them right now, as their data names it. None
        for somebody who is under nothing."""
        now = self.world.clock.total_minutes
        return next((intake.sign for intake in resident.under if intake.until > now), None)

    def sway(self, resident: Resident) -> float:
        """How far to one side whoever is under something is from where they stand, in tiles:
        they reel as they go. Nothing for somebody steady on their feet."""
        sign = self.under_sign(resident)
        if sign is None or sign in STEADY_SIGNS:
            return 0.0
        reach, rate = SWAYS.get(sign, OTHER_SWAY)
        # Nobody reels in step with anybody else.
        offset = sum(map(ord, resident.resident_id)) % 7
        return reach * math.sin((self.time * rate + offset / 7.0) * math.tau)

    def _resident_draw(self, resident: Resident) -> Draw:
        # In the player's hand they are doing nothing of what they were at: they hang from it.
        carried = self._in_hand(resident)
        lying_in = None if carried else self._lying_in(resident)
        if lying_in is not None:
            return self._lying_draw(resident, lying_in)
        doll = self._doll_for(resident)
        asleep = not carried and self.sleeps_rough(resident)
        if asleep and (doll is None or self.poses.rough is None):
            # The small bodies of the game do not lie down: a blanket, and a head out at one end.
            return self._rough_draw(resident)
        x, y, facing, stride = self._walk_state(resident)
        x += 0.0 if carried else self.sway(resident)
        # Somebody not yet grown has a smaller body under the head they were drawn with.
        grown = grown_share(self.world, resident)
        if doll is not None:
            facing = self._side_facing(resident.resident_id, (None if carried else self._lean(resident)) or facing)
        top = round(y * TILE_SIZE)
        spot = ground_spot(x, y)
        # Where a body stands at rest, which is what is picked with the mouse whatever it is doing.
        body = pygame.Rect(spot[0] - FRAME_ORIGIN[0], spot[1] - FRAME_ORIGIN[1], *FRAME_SIZE)
        sole = (float(spot[0]), float(spot[1]))
        if grown < 1.0:
            body = pygame.Rect(
                spot[0] - round(FRAME_ORIGIN[0] * grown), spot[1] - round(FRAME_ORIGIN[1] * grown),
                max(1, round(FRAME_SIZE[0] * grown)), max(1, round(FRAME_SIZE[1] * grown)),
            )
        if doll is not None:
            # A doll is as tall and as wide as it was drawn: its name goes over its own head.
            left, high, right, low = doll.standing(doll.plan or self.bodies.plan)
            high *= HEAD_OF_HEIGHT + (1.0 - HEAD_OF_HEIGHT) * grown
            # A smaller body is brought down about the ground its soles are on, so that it stands on it.
            sole = (float(spot[0]), float(spot[1]) + low)
            body = pygame.Rect(
                spot[0] + math.floor(left), spot[1] + math.floor(high), math.ceil(right - left), math.ceil(low) - math.floor(high)
            )

        # What they carry is in their pockets: nothing is in their hands but what they are using.
        clip, rate, overlay = (*self._way_of(resident, WALK), None) if stride is not None else self._bearing(resident)
        if carried:
            clip, rate, overlay = IDLE_CLIP, 1.0, None
        elif stride is None and self._seat_of(resident) is not None:
            # Sitting, they are not as tall: their name comes down with their head.
            plan = doll.plan if doll is not None and doll.plan is not None else self.bodies.plan
            lower = min(body.height - 1, round(self._lower_in(plan, facing, clip) * grown))
            body = pygame.Rect(body.left, body.top + lower, body.width, body.height - lower)
        renderer = self.bodies.renderer
        frames = renderer.frames(clip, facing)
        turn = (stride if stride is not None else self.time) * rate
        index = int(turn * frames) % frames
        phase = turn % 1.0
        # A doll that sleeps on the ground lies down on it, curled up, and gets up from it.
        rough = self._rough_pose(resident, stride) if doll is not None else None
        if rough is not None:
            clip, phase = rough
        if asleep:
            # Lying there it is no taller than it lies: that is what is picked, and its name is not over it.
            body = pygame.Rect(
                round(spot[0] - ROUGH_SIZE[0] / 2), round(spot[1] - ROUGH_SIZE[1] - 6), round(ROUGH_SIZE[0]), round(ROUGH_SIZE[1] + 6)
            )
        character = self.bodies.character(resident)
        # A doll stands and moves by its own measures, so that it is as it was drawn. Physics is
        # left with whatever body it has in hand until it is done with it.
        own = doll.plan if doll is not None and doll.plan is not None else self.bodies.plan
        if character.plan is not own and not character.physical:
            character.plan = own
        # A doll moves on springs, with some weight to it. A body kept as pictures is posed exactly.
        character.lively = doll is not None
        # With nothing to do and nothing in hand it may fidget.
        character.at_ease = (
            not carried
            and stride is None
            and self._meal_in_hand(resident) is None
            and self._weapon_in_hand(resident) is None
        )
        if not carried:
            self._pocketing(resident, character)
        # A doll turns smoothly; the game's own bodies go from one kept picture to the next.
        character.stand(spot[0], spot[1], facing, clip, phase if doll is not None else index / frames, overlay)

        # Whoever sits on something is in front of it, though it stands on the tile they are on.
        on_seat = not carried and stride is None and self._seat_under(resident) is not None
        depth = max(float(spot[1]), (y + 1) * TILE_SIZE + 0.5) if on_seat else float(spot[1])
        if carried:
            # In front of everything that stands on the map.
            depth = IN_HAND_DEPTH

        def draw() -> None:
            if doll is not None:
                skeleton = character.skeleton if character.physical else self._posed_skeleton(resident.resident_id, character)
                if carried and not character.physical:
                    # Held by the scruff of the neck, they swing from it as the hand moves.
                    self._hang(skeleton, (float(spot[0]), float(spot[1]) - HANG))
                self._doll_draws.append((depth, doll, skeleton, None, grown, sole))
            elif character.physical:
                # Reeling from a blow or knocked down: drawn joint by joint, wherever physics has them.
                renderer.draw_limp(
                    self._scene, character.skeleton, resident.resident_id, (-self._scene_origin[0], -self._scene_origin[1])
                )
            else:
                picture, origin = renderer.frame(
                    resident.resident_id, facing, clip, index, tuple(character.lost), overlay
                )
                if grown < 1.0:
                    # The game's own small body is brought down whole, head and all.
                    picture, origin = self._small_frame(picture, origin, grown)
                self._blit(picture, (spot[0] - origin[0], spot[1] - origin[1]))
            if carried:
                # Nobody is picked out from under the hand that holds them, and they have
                # nothing in theirs and nothing over their head meanwhile.
                return
            hitbox = self._canvas_rect(body)
            self.hitboxes[resident.resident_id] = hitbox
            held = len(self._held)
            if not character.physical:
                self._hold_all(resident, facing, character.pose(), spot[1], turn, stride, (grown, sole), clip)
            # What is held up higher than their head, as a meal is by somebody sitting, is not
            # written over: their name goes above it.
            tops = [top for top in map(self._top_of, self._held[held:]) if top is not None]
            over = min([hitbox.top, *(self._canvas_point(*top)[1] for top in tops)])
            self._overlays.append(
                lambda: self._draw_overhead(resident, (hitbox.centerx, over), with_name=not asleep, resting=asleep)
            )

        return (IN_HAND_DEPTH if carried else top + TILE_SIZE, 1, draw)

    def _building_draw(self, room: Room) -> Draw:
        """A building with its roof on. Whatever stands behind it is hidden by as much as it rises."""
        area = building_area(room)
        picture = self.buildings.picture(room)

        def draw() -> None:
            self._blit(picture, area.topleft)

        return (area.bottom, 0, draw)

    def _doll_of(self, body_id: str, young: bool = False) -> Doll | None:
        """The paper doll of a body, if its body has been drawn and there is a window to show it on.
        `young` says they are a child, who has the one look children have until somebody draws them."""
        if self.dolls is None:
            return None
        doll = self.dolls.get(body_id)
        if doll is None and self.windowed and young:
            doll = self.dolls.stand_in(CHILD_BODY, child_stand_in)
        elif doll is None and self.windowed:
            # Nobody has drawn them: on the window they are a plain figure in their own colours.
            skin = self.bodies.renderer.skin(body_id)
            doll = self.dolls.stand_in(body_id, lambda template: stand_in(template, skin))
        return self.dolls.dressed(doll, self.trying_on, in_turn=True)

    def _doll_for(self, resident: Resident) -> Doll | None:
        """The paper doll a resident is shown as."""
        return self._doll_of(resident.resident_id, self.world.children.is_child(self.world, resident))

    def _small_frame(
        self, picture: pygame.Surface, origin: tuple[int, int], grown: float
    ) -> tuple[pygame.Surface, tuple[int, int]]:
        """One of the game's own small bodies at a share of its size, and where the spot between its feet is on it."""
        key = (id(picture), round(grown * 100))
        if key not in self._small_frames:
            size = (max(1, round(picture.get_width() * grown)), max(1, round(picture.get_height() * grown)))
            self._small_frames[key] = (pygame.transform.scale(picture, size), (round(origin[0] * grown), round(origin[1] * grown)))
        return self._small_frames[key]

    def _side_facing(self, resident_id: str, facing: str) -> str:
        """Which way a doll faces: it is drawn from the side, so walking up or down it keeps the side it last had."""
        if facing in DOLL_FACINGS:
            self._doll_facing[resident_id] = DOLL_FACINGS[facing]
        return self._doll_facing.get(resident_id, DOLL_FACING)

    def _posed_skeleton(self, resident_id: str, character) -> Skeleton:
        """A skeleton standing as a resident's body is right now, to lay their doll over."""
        plan = character.plan
        key = (resident_id, character.facing, tuple(character.lost), id(plan))
        if key not in self._posed:
            self._posed[key] = Skeleton(plan, character.facing, character.lost)
        skeleton = self._posed[key]
        skeleton.set_pose(character.local_pose(), character.x, character.y)
        return skeleton

    def bundle_spot(self, bundle: Bundle) -> tuple[float, float, float]:
        """Where a child in its blanket is shown: the middle of its foot in map pixels, and how
        far down the map it counts as standing, for what goes in front of what.

        Carried, it is on the back of whoever has it: a little behind them and well up from the
        ground. Put down, it is on its tile, off the ground where that is a bed or a table.
        """
        if self._bundle_in_hand(bundle) and self.pointer is not None:
            x, y = self._map_point(self.pointer)
            return (x, y + BUNDLE_WIDTH, IN_HAND_DEPTH)
        carrier = self.world.residents.get(bundle.carried_by or "") if bundle.place == BUNDLE_CARRIED else None
        if carrier is not None and not carrier.away:
            x, y, facing, _ = self._walk_state(carrier)
            foot = ground_spot(x + (0.0 if self._in_hand(carrier) else self.sway(carrier)), y)
            turned = self._doll_facing.get(carrier.resident_id, DOLL_FACINGS.get(facing, DOLL_FACING))
            back = BUNDLE_BEHIND if turned == DOLL_FACINGS["left"] or facing == "left" else -BUNDLE_BEHIND
            share = grown_share(self.world, carrier)
            # Just behind whoever carries it, so that they are in front of it.
            return (foot[0] + back * share, foot[1] - BUNDLE_UP * share, foot[1] - 0.1)
        raised = BUNDLE_RAISED if bundle.place in (BUNDLE_IN_BED, BUNDLE_ON_SURFACE) else 0.0
        bottom = (bundle.y + 1) * TILE_SIZE
        return ((bundle.x + 0.5) * TILE_SIZE, bottom - 2 - raised, bottom + 0.7)

    def bundle_shown(self, bundle: Bundle, side: int) -> pygame.Surface:
        """A child in its blanket, `side` pixels across, made once and kept: with their own head
        if somebody has drawn them as the adult they will be, or else the face the game has for them."""
        doll = self.dolls.get(bundle.child_id) if self.dolls is not None else None
        placed = doll.placed(HEAD_BONE, False, 8.0, math.pi) if doll is not None else None
        head = placed[0] if placed is not None else self.faces.face(bundle.child_id)
        # A head drawn anew is another picture, and so is the bundle made with it.
        key = (bundle.child_id, id(head), side)
        if key not in self._bundle_pictures:
            if len(self._bundle_pictures) > 64:
                self._bundle_pictures.clear()
            self._bundle_pictures[key] = bundle_picture(head.subsurface(head.get_bounding_rect()), side)
        return self._bundle_pictures[key]

    def _show_bundle(self, bundle: Bundle, standing: list[Standing], draws: list[Draw]) -> None:
        """Have a child in its blanket drawn: on the window where there is one, or else small on the map's own art."""
        x, bottom, depth = self.bundle_spot(bundle)
        height = BUNDLE_WIDTH * bundle_height(100) / 100
        area = (x - BUNDLE_WIDTH / 2, bottom - height, BUNDLE_WIDTH, height)
        if self.windowed:
            side = max(4, round(BUNDLE_WIDTH * self._cell / TILE_SIZE))
            standing.append((depth, area, self.bundle_shown(bundle, side)))
        else:
            small = self.bundle_shown(bundle, round(BUNDLE_WIDTH))
            draws.append((depth, 1, lambda: self._blit(small, (round(area[0]), round(area[1])))))
        place = self._canvas_rect(pygame.Rect(round(area[0]), round(area[1]), round(area[2]), round(area[3])))
        if self._bundle_in_hand(bundle):
            return
        self.bundle_boxes[bundle.child_id] = place.inflate(2, 2)
        if bundle.place != BUNDLE_CARRIED:
            # Put down, it has its name over it: there is nobody's back to look for it on.
            name = self.font.render(bundle.name, PALETTE["bone"])
            self._bundle_names.append((name, (place.centerx - name.get_width() // 2, place.top - CELL_SIZE[1])))

    def _remains_draw(self, remains: Remains) -> Draw:
        """A dead body or a part of one, in among the living by how far down the map it lies."""
        doll = self._doll_of(remains.body_id)

        def draw() -> None:
            if doll is not None:
                self._doll_draws.append((remains.skeleton.ground, doll, remains.skeleton, None, 1.0, (0.0, 0.0)))
                return
            self.bodies.draw_remains(self._scene, remains, self._scene_origin)

        return (remains.skeleton.ground, 1, draw)

    def _way_of(self, resident: Resident, occasion: str) -> tuple[str, float]:
        """The clip a resident walks, eats or fights with, and how fast it goes: their own manner of it.

        Fighting, it is the manner that goes with whatever weapon they carry.
        """
        tags = self.world.health.weapon_of(self.world, resident)[1] if occasion == FIGHT else ()
        kind = self.world.registries.manners.kind_for(occasion, tags)
        manner = self.world.manner_of(resident, kind.kind_id) if kind is not None else None
        if manner is None:
            clip = PLAIN_CLIPS[occasion]
            return (clip, CLIP_RATES.get(clip, 1.0))
        return (manner.clip, manner.rate)

    def _fighting(self, resident: Resident) -> bool:
        """Whether a resident is coming to blows with someone right now."""
        activity = resident.activity
        if activity is None or not activity.using or activity.partner_id is None:
            return False
        interaction = self.world.registries.interactions.get(activity.action)
        return interaction is not None and interaction.hostile and interaction.damage is not None

    def _arguing(self, resident: Resident) -> bool:
        """Whether a resident is having words with someone right now, and it has not come to blows."""
        activity = resident.activity
        if activity is None or not activity.using or activity.partner_id is None:
            return False
        interaction = self.world.registries.interactions.get(activity.action)
        return interaction is not None and interaction.hostile and interaction.damage is None

    def _clip_of(self, resident: Resident) -> tuple[str, float]:
        """What the body of someone who is not walking is doing, and how many times a second its clip goes round."""
        return self._bearing(resident)[:2]

    def _bearing(self, resident: Resident) -> tuple[str, float, str | None]:
        """How the body of someone who is not walking is: the clip it is in, how many times a
        second that goes round, and a second clip laid over the first, whose bones take the
        place of the first one's: whoever eats sitting down sits, and eats with their arms."""
        activity = resident.activity
        if activity is None or not activity.using:
            return (IDLE_CLIP, 0.0, None)
        if activity.partner_id is not None:
            if self._fighting(resident):
                return (*self._way_of(resident, FIGHT), None)
            if self._arguing(resident):
                return (*self._way_of(resident, ARGUE), None)
            # What two sit down to, they sit down to: cards, a story.
            together = self._seat_of(resident)
            return (*together, None) if together is not None else (IDLE_CLIP, 0.0, None)
        seat = self._seat_of(resident)
        if activity.action == EAT_ACTION:
            clip, rate = self._way_of(resident, EAT)
            # The meal goes at the pace of eating, on a body that sits still under it.
            return (seat[0], rate, clip) if seat is not None else (clip, rate, None)
        work = self._work_of(resident)
        if work is not None:
            return (work[0].clip, work[0].rate, None)
        return (*seat, None) if seat is not None else (IDLE_CLIP, 0.0, None)

    def _lower_in(self, plan, facing: str, clip: str) -> float:
        """How much lower than standing the top of a body is in a clip, as it begins it, in map pixels."""
        key = (id(plan), facing, clip)
        if key not in self._lower:
            standing = min(y for _, y in plan.pose(facing).values())
            self._lower[key] = max(0.0, min(y for _, y in plan.pose(facing, clip).values()) - standing)
        return self._lower[key]

    def _seat_of(self, resident: Resident) -> tuple[str, float] | None:
        """The clip a resident sits in, and how many turns of it a second, if what they are at
        is done sitting down: by a fire, at the radio, eating, drinking, or passing the time that
        way, alone or with somebody. On a seat it is the way anybody sits on one, and on the
        ground their own. None for whoever is on their feet."""
        activity = resident.activity
        if activity is None or not activity.using:
            return None
        kind = self.world.registries.manners.during(SIT, activity.action)
        if kind is None:
            return None
        on_seat = self.poses.seat
        if on_seat is not None and seat_at(self.world, resident.tile) is not None:
            return (on_seat.clip, on_seat.rate)
        manner = self.world.manner_of(resident, kind.kind_id)
        return (manner.clip, manner.rate) if manner is not None else None

    def _seat_under(self, resident: Resident) -> Interactable | None:
        """What a resident is sitting on, if they sit and it is not the ground: the seat that
        stands on the tile they are on."""
        return seat_at(self.world, resident.tile) if self._seat_of(resident) is not None else None

    def _work_of(self, resident: Resident) -> tuple[Doing, str | None] | None:
        """How the work a resident is at right now is shown, and what they are seen to do it with.

        At their post that is the tool of their job, if they carry one that is not broken:
        whoever has none works as the job is done with bare hands. Building, it is whatever
        builders are seen with, which is nobody's. None for somebody who is not at work.
        """
        activity = resident.activity
        if activity is None or not activity.using or activity.partner_id is not None:
            return None
        if activity.action == BUILD_ACTION:
            return (self.poses.build, self.poses.build.prop)
        if self.world.attributes.training(self.world, resident) is not None:
            # At a thing to train at they are seen hard at it, as at any work with bare hands (P61).
            return (self.poses.work, None)
        if activity.action != WORK_ACTION:
            return None
        job = self.world.work.job_of(self.world, resident)
        job_id = job.job_id if job is not None else None
        tool = self.world.work.tool_of(self.world, resident, job) if job is not None else None
        doing = self.poses.working(job_id, tool is not None)
        with_tool = tool is not None and doing is not self.poses.working(job_id, False)
        return (doing, tool.definition_id if with_tool else doing.prop)

    def _tool_in_hand(self, resident: Resident) -> str | None:
        """ID of what a resident at work is seen to work with: an item of theirs, or something
        that is only there for the look of it. None for bare hands."""
        work = self._work_of(resident)
        return work[1] if work is not None else None

    def _meal_in_hand(self, resident: Resident) -> str | None:
        """Definition ID of the food in a resident's hand during an active meal."""
        activity = resident.activity
        if activity is None or activity.action != EAT_ACTION:
            return None
        return self._item_in_hand(resident)

    def _weapon_in_hand(self, resident: Resident) -> str | None:
        """Definition ID of what a resident fights with, while they are fighting. None for bare hands."""
        if not self._fighting(resident):
            return None
        weapon = self.world.health.weapon_item(self.world, resident)
        return weapon.definition_id if weapon is not None else None

    def _bites_taken(self, resident: Resident) -> int:
        """How many bites are gone from what a resident is eating, by how far through the meal they are."""
        activity = resident.activity
        placed = self.world.interactables.get(activity.target_id or "") if activity is not None else None
        use = self.world.definition_of(placed).use if placed is not None else None
        if activity is None or use is None or use.minutes <= 0:
            return 0
        done = 1.0 - max(0.0, min(1.0, activity.minutes_left / use.minutes))
        return sum(1 for share in BITES_AT if done >= share)

    def _hold(
        self,
        item_id: str,
        facing: str,
        pose: dict[str, tuple[float, float]],
        ground: float,
        turn: float | None = None,
        bites: int = 0,
        about: tuple[float, tuple[float, float]] | None = None,
        clip: str | None = None,
    ) -> None:
        """Have something shown in the hand of a resident whose feet are `ground` down the map.
        With `turn`, how many turns of the eating clip have gone, it is a meal and crumbs fly from each bite.
        `about` is how much of its size their body is shown at and the spot between their feet,
        for somebody not yet grown: their hand is where their smaller arm has it. `clip` is what
        their body is doing: in one that holds things by the handle, a thing that has one is
        held by it, and turns with the hands."""
        plan = self.bodies.plan
        left = facing.endswith("left")
        gripped = plan.handle(clip, facing, pose) if clip is not None and item_id in self.poses.handles else None
        if gripped is not None:
            point, way, at = gripped
            share, (foot_x, foot_y) = about if about is not None else (1.0, (0.0, 0.0))
            if share < 1.0:
                point = (foot_x + (point[0] - foot_x) * share, foot_y + (point[1] - foot_y) * share)
            self._held.append(Gripped(item_id, point, way, at, share, left))
            return
        hand = plan.anchor("held_item", facing, pose)
        mouth = plan.anchor("mouth", facing, pose)
        if hand is None or mouth is None:
            return
        if about is not None and about[0] < 1.0:
            share, (foot_x, foot_y) = about
            hand = (foot_x + (hand[0] - foot_x) * share, foot_y + (hand[1] - foot_y) * share)
            mouth = (foot_x + (mouth[0] - foot_x) * share, foot_y + (mouth[1] - foot_y) * share)
        offset = MOUTH_OFFSETS.get(facing, (0, 2))
        mouth = (mouth[0] + offset[0], mouth[1] + offset[1])
        forward = -1 if left else (1 if facing.endswith("right") else 0)
        flying = crumbs(turn, forward, ground - mouth[1]) if turn is not None else []
        self._held.append((item_id, (hand[0] + forward * HELD_AHEAD, hand[1]), left, bites, flying, mouth))

    def _hold_all(
        self,
        resident: Resident,
        facing: str,
        pose: dict[str, tuple[float, float]],
        ground: float,
        turn: float,
        stride: float | None,
        about: tuple[float, tuple[float, float]],
        clip: str,
    ) -> None:
        """Have whatever a resident has in hand shown: the meal they are at, with the bites gone
        from it, what they fight with, or the tool of the work they are at. Nothing for empty
        hands, and what they merely carry is not in them. `stride` is None for somebody standing still."""
        if self._arguing(resident):
            self._spark(resident, facing, pose, about)
        meal = self._meal_in_hand(resident)
        weapon = self._weapon_in_hand(resident) if stride is None else None
        tool = self._tool_in_hand(resident) if stride is None else None
        if meal is not None:
            self._hold(meal, facing, pose, ground, turn, self._bites_taken(resident), about)
        elif weapon is not None:
            self._hold(weapon, facing, pose, ground, about=about)
        elif tool is not None:
            self._hold(tool, facing, pose, ground, about=about, clip=clip)

    def _spark(
        self, resident: Resident, facing: str, pose: dict[str, tuple[float, float]], about: tuple[float, tuple[float, float]]
    ) -> None:
        """Have bolts fly from the head of a resident who is having words with somebody, at them."""
        head = self.bodies.plan.anchor("mouth", facing, pose)
        if head is None:
            return
        share, (foot_x, foot_y) = about
        if share < 1.0:
            head = (foot_x + (head[0] - foot_x) * share, foot_y + (head[1] - foot_y) * share)
        other = self.world.residents.get(resident.activity.partner_id or "") if resident.activity is not None else None
        towards = float(other.x - resident.x) if other is not None else 0.0
        if towards == 0.0:
            # One above the other on the map: at whichever side they are turned to.
            towards = -1.0 if facing.endswith("left") else 1.0
        seed = sum(map(ord, resident.resident_id))
        self._held.append(Sparks(head, tuple(bolts(self.time, towards, seed)), share))

    def _top_of(self, held: Held) -> tuple[float, float] | None:
        """The top, in map pixels, of something shown with a resident that their name is to be
        written above: the meal in their hand, or as high as their bolts ever fly. None for
        what is held by its handle, which their name is written over as it was."""
        if isinstance(held, Sparks):
            return (held.at[0], held.at[1] - HIGHEST * held.share)
        if isinstance(held, Gripped):
            return None
        return (held[1][0], held[1][1] - HELD_SIZE / 2)

    def _pocketing(self, resident: Resident, character) -> None:
        """Have a body put a hand to its pocket when its resident has taken something up or
        handed it over since they were last looked at."""
        pocket = self.poses.pocket
        if self.bodies.took_or_gave(resident) and pocket is not None:
            character.gesture(pocket.clip, pocket.rate)

    def _draw_held(self, target: pygame.Surface, origin: tuple[float, float], detail: float) -> None:
        """Draw what residents hold, and the crumbs of their meals, on a surface where a map pixel
        is `detail` of its own and the map's corner is at `origin`."""
        size = max(3, round(HELD_SIZE * detail))
        for held in self._held:
            if isinstance(held, Sparks):
                head = (origin[0] + held.at[0] * detail, origin[1] + held.at[1] * detail)
                self._bolt_art.draw(target, list(held.bolts), head, detail * held.share)
                continue
            if isinstance(held, Gripped):
                handle = self.poses.handles[held.item_id]
                long = handle.long * held.share * detail
                picture, point = self.icons.gripped(held.item_id, handle.start, handle.end, long, held.way, held.at, held.left)
                at = (origin[0] + held.hand[0] * detail - point[0], origin[1] + held.hand[1] * detail - point[1])
                target.blit(picture, (round(at[0]), round(at[1])))
                continue
            item_id, hand, left, bites, flying, mouth = held
            picture = self.icons.held(item_id, size, bites, left)
            centre = (round(origin[0] + hand[0] * detail), round(origin[1] + hand[1] * detail))
            target.blit(picture, picture.get_rect(center=centre))
            at = (origin[0] + mouth[0] * detail, origin[1] + mouth[1] * detail)
            self._crumb_art.draw(target, flying, self.icons.crumb_colors(item_id), at, detail)

    def _draw_smoke(self, resident: Resident, top_centre: tuple[int, int]) -> None:
        """Smoke hanging round whoever smokes: puffs that rise from their head, swell and thin out."""
        x, y = top_centre
        offset = sum(map(ord, resident.resident_id)) % 5
        for puff in range(SMOKE_PUFFS):
            age = (self.time / SMOKE_SECONDS + (puff + offset / 5.0) / SMOKE_PUFFS) % 1.0
            drift = math.sin((age + puff * 0.37) * math.tau) * SMOKE_DRIFT
            centre = (round(x + drift + (puff - (SMOKE_PUFFS - 1) / 2) * 2), round(y + 4 - age * SMOKE_RISE))
            radius = 1.5 + 3.0 * math.sin(age * math.pi)
            pygame.draw.circle(self.canvas, PALETTE["stone"], centre, radius + 1)
            pygame.draw.circle(self.canvas, PALETTE["bone" if age < 0.55 else "dust"], centre, radius)

    def _marker_draw(self, resident: Resident) -> Draw:
        """From afar a resident is only their face, over the tile they are on, roof or no roof."""
        carried = self._in_hand(resident)
        lying_in = None if carried else self._lying_in(resident)
        if lying_in is not None:
            x, y = float(lying_in.x), float(lying_in.y)
        else:
            x, y, _, _ = self._walk_state(resident)
        face = self.faces.marker(resident.resident_id)
        hitbox = face.get_rect(center=self._canvas_point((x + 0.5) * TILE_SIZE, (y + 0.5) * TILE_SIZE))
        if carried and self.pointer is not None:
            # Their face goes with the hand, and nobody is picked out from under it.
            hitbox = face.get_rect(midtop=self.pointer)
            return (IN_HAND_DEPTH, 1, lambda: self._overlays.append(lambda: self.canvas.blit(face, hitbox)))

        def overlay() -> None:
            self.canvas.blit(face, hitbox)
            # Over a face on a roof, what they are doing in there: talking, eating, asleep, at work.
            self._draw_overhead(resident, hitbox.midtop, with_name=False, resting=lying_in is not None, unseen=True)

        def draw() -> None:
            self.hitboxes[resident.resident_id] = hitbox
            self._overlays.append(overlay)

        return ((y + 1) * TILE_SIZE, 1, draw)

    def _walk_state(self, resident: Resident) -> tuple[float, float, str, float | None]:
        """Position in tiles, facing and how far into a stride, part-way through the current minute.

        The stride goes from 0 to 1 over a step with each foot. It is None for someone standing still.
        """
        if self._in_hand(resident):
            # Wherever the hand has them, hanging from it: they walk nowhere meanwhile.
            return (*self._hand_tile(), resident.facing, None)
        trail = resident.trail
        if len(trail) < 2:
            return (resident.x, resident.y, resident.facing, None)
        distance = min(self.tick_progress, 1.0) * (len(trail) - 1)
        index = min(int(distance), len(trail) - 2)
        fraction = distance - index
        (from_x, from_y), (to_x, to_y) = trail[index], trail[index + 1]
        # They walk at any angle, and are seen from whichever of the four sides is nearest to it.
        if abs(to_x - from_x) >= abs(to_y - from_y):
            facing = "right" if to_x > from_x else "left"
        else:
            facing = "down" if to_y > from_y else "up"
        stride = distance / TILES_PER_STRIDE % 1.0
        return (from_x + (to_x - from_x) * fraction, from_y + (to_y - from_y) * fraction, facing, stride)

    def _lean(self, resident: Resident) -> str | None:
        """The side someone walking is going towards, however slightly. None if they stand or go straight up or down."""
        trail = resident.trail
        if len(trail) < 2:
            return None
        index = min(int(min(self.tick_progress, 1.0) * (len(trail) - 1)), len(trail) - 2)
        across = trail[index + 1][0] - trail[index][0]
        if abs(across) < LEAN:
            return None
        return "right" if across > 0 else "left"

    def _lying_in(self, resident: Resident) -> Interactable | None:
        """The object a resident is lying in, if they are using one from on top of it."""
        activity = resident.activity
        if activity is None or not activity.using or activity.target_id is None:
            return None
        placed = self.world.interactables.get(activity.target_id)
        if placed is None:
            return None
        # By the use they are at: a thing may offer several, and not all of them from on top of it (S60).
        use = self.world.definition_of(placed).use_for(activity.action)
        return placed if use is not None and use.position == "on" else None

    def _lying_draw(self, resident: Resident, placed: Interactable) -> Draw:
        definition = self.world.definition_of(placed)
        bed = pygame.Rect(
            placed.x * TILE_SIZE, placed.y * TILE_SIZE, TILE_SIZE, definition.height * TILE_SIZE
        )
        face = self.bodies.renderer.head(resident.resident_id)
        head = face.subsurface((0, 0, face.get_width(), LYING_HEAD_ROWS))

        doll = self._doll_for(resident)
        neck = (bed.left + LYING_NECK[0], bed.top + LYING_NECK[1])
        game = self._game_picture(definition, placed)
        if game is not None and game.neck is not None:
            # The game's own picture of a bed says where a head goes on it.
            detail = self._cell / TILE_SIZE
            neck = (bed.left + game.neck[0] / detail, bed.bottom - (game.under.get_height() - game.neck[1]) / detail)

        def draw() -> None:
            if doll is not None:
                self._doll_draws.append((bed.bottom, doll, None, neck, 1.0, (0.0, 0.0)))
            else:
                self._blit(head, (bed.left + LYING_HEAD_OFFSET[0], bed.top + LYING_HEAD_OFFSET[1]))
            hitbox = self._canvas_rect(bed)
            self.hitboxes[resident.resident_id] = hitbox
            self._overlays.append(
                lambda: self._draw_overhead(resident, hitbox.midtop, with_name=False, resting=True)
            )

        return (bed.bottom, 1, draw)

    def sleeps_rough(self, resident: Resident) -> bool:
        """Whether a resident is lying on the ground: asleep there for want of a bed, or dozing where they were."""
        activity = resident.activity
        if activity is None or not activity.using:
            return False
        pastime = self.world.leisure.pastime_of(self.world, activity)
        return activity.action == SLEEP_ROUGH_ACTION or (pastime is not None and pastime.lies)

    def _rough_pose(self, resident: Resident, stride: float | None) -> tuple[str, float] | None:
        """The clip somebody who sleeps on the ground is at, and how far through it: lying down
        on it, lying there, or getting up again when they wake. None for anybody else, and for
        whoever walks off as they wake: they are simply up. Only what is seen to begin is
        shown beginning: somebody found asleep is found lying."""
        rough = self.poses.rough
        if rough is None:
            return None
        lying, seconds = self.bodies.rest(resident.resident_id, self.sleeps_rough(resident))
        if lying:
            done = seconds * rough.down.rate
            if done < 1.0:
                return (rough.down.clip, done)
            return (rough.asleep.clip, min(seconds, 1e6) * rough.asleep.rate % 1.0)
        done = seconds * rough.up.rate
        return (rough.up.clip, done) if done < 1.0 and stride is None else None

    def rough_blanket(self, width: int, height: int) -> pygame.Surface:
        """The blanket over whoever sleeps on the ground, at a size, made once and kept."""
        key = ("rough", width, height)
        if key not in self._bundle_pictures:
            self._bundle_pictures[key] = ground_blanket(width, height)
        return self._bundle_pictures[key]

    def _rough_draw(self, resident: Resident) -> Draw:
        """Somebody asleep on the ground: a blanket with them under it, and their head out at one end."""
        bottom = (resident.y + 1) * TILE_SIZE - 1
        left = (resident.x + 0.5) * TILE_SIZE - ROUGH_SIZE[0] / 2
        area = (left, bottom - ROUGH_SIZE[1], *ROUGH_SIZE)
        neck = (left + ROUGH_NECK[0], bottom - ROUGH_NECK[1])
        doll = self._doll_for(resident)
        face = self.bodies.renderer.head(resident.resident_id)
        head = face.subsurface((0, 0, face.get_width(), LYING_HEAD_ROWS))
        box = pygame.Rect(round(area[0]), round(area[1] - 6), round(area[2]), round(area[3] + 6))

        def draw() -> None:
            if doll is not None:
                detail = self._cell / TILE_SIZE
                blanket = self.rough_blanket(max(4, round(ROUGH_SIZE[0] * detail)), max(2, round(ROUGH_SIZE[1] * detail)))
                self._rough.append((float(bottom) - 0.2, area, blanket))
                self._doll_draws.append((float(bottom), doll, None, neck, 1.0, (0.0, 0.0)))
            else:
                self._blit(self.rough_blanket(round(ROUGH_SIZE[0]), round(ROUGH_SIZE[1])), (round(area[0]), round(area[1])))
                self._blit(head, (round(neck[0]) - head.get_width() // 2, round(neck[1]) - head.get_height()))
            hitbox = self._canvas_rect(box)
            self.hitboxes[resident.resident_id] = hitbox
            self._overlays.append(lambda: self._draw_overhead(resident, hitbox.midtop, with_name=False, resting=True))

        return (bottom, 1, draw)

    def _status_icon(self, resident: Resident, resting: bool, unseen: bool = False) -> str | None:
        """Icon for what a resident is doing, most urgent first. For somebody `unseen`, who is
        only a face on a roof, it also says what would otherwise be seen of them: that they eat."""
        if self._decision_of(resident.resident_id) is not None:
            return "alert"
        activity = resident.activity
        in_exchange = activity is not None and activity.using and activity.partner_id is not None
        if resident.resident_id in self.alerts:
            if in_exchange:
                return "alert"
            self.alerts.discard(resident.resident_id)
        if in_exchange:
            interaction = self.world.registries.interactions.get(activity.action)
            if interaction is not None and interaction.romance == "tryst":
                return "heart"
            return "argument" if interaction is not None and interaction.hostile else "chat"
        if resting:
            return "sleep"
        if unseen and activity is not None and activity.using and activity.action == EAT_ACTION:
            return "eat"
        if resident.health < HURT_HEALTH:
            return "hurt"
        at_work = activity is not None and activity.using and activity.action in (WORK_ACTION, BUILD_ACTION)
        if at_work:
            return "work"
        # Whoever is under something wears it, with nothing more pressing to show.
        return UNDER_ICON if self.under_sign(resident) not in (None, *STEADY_SIGNS) else None

    def _bond_icon(self, resident: Resident) -> str | None:
        """What a resident is to whoever is selected: their partner, someone they hold as a friend, or neither."""
        selected = self.world.residents.get(self.hud.selected_id or "")
        if selected is None:
            return None
        if selected.couple_with == resident.resident_id:
            return "heart"
        feelings = self.world.relationships.get((selected.resident_id, resident.resident_id))
        return "friend" if feelings is not None and self.world.bonds.tier(self.world, feelings) is not None else None

    def _name_left(self, resident: Resident, centre_x: int, width: int) -> int:
        """Left edge of a name label. Two residents talking side by side push theirs apart."""
        activity = resident.activity
        partner = self.world.residents.get(activity.partner_id) if activity and activity.partner_id else None
        if partner is None or not activity.using or partner.y != resident.y:
            return centre_x - width // 2
        half_tile = self.tile_px // 2
        return centre_x + half_tile - 3 - width if partner.x > resident.x else centre_x - half_tile + 3

    def _load_of(self, resident: Resident) -> str | None:
        """Definition ID of what a resident is carrying for their job: goods that are nobody's yet."""
        return next((item.definition_id for item in resident.inventory.items if item.owner_id is None), None)

    def _item_in_hand(self, resident: Resident) -> str | None:
        """Definition ID of what a resident is eating or using right now."""
        activity = resident.activity
        if activity is None or not activity.using or activity.item_id is None:
            return None
        item = self.world.items.find_item(self.world, activity.item_id)
        if item is not None:
            # One thing in particular: what they are using, or having repaired.
            return item.definition_id
        if activity.action == USE_ITEM_ACTION:
            return None
        return activity.item_id if activity.target_id is not None and activity.partner_id is None else None

    def protesting(self, resident: Resident) -> bool:
        """Whether a resident is standing in the square against a law right now."""
        activity = resident.activity
        return activity is not None and activity.action == PROTEST_ACTION and not activity.path

    def _draw_overhead(
        self, resident: Resident, top_centre: tuple[int, int], with_name: bool, resting: bool = False, unseen: bool = False
    ) -> None:
        """Stack how far along they are with a task, their name, a status icon and the
        selection arrow above a resident."""
        x, y = top_centre
        if not unseen and self.under_sign(resident) == SMOKE_SIGN:
            self._draw_smoke(resident, top_centre)
        done = task_progress(self.world, resident)
        here = resident.resident_id in self.world.residents
        coming = self.world.work.progress(self.world, resident) if here else None
        top = y
        if done is not None:
            bar = task_bar_rect((x, y), small=self.overview)
            draw_task_bar(self.canvas, bar, done)
            self.task_bars[resident.resident_id] = bar
            top = bar.top - 1
        if coming is not None:
            # At a post that makes something: beside how much of the shift has gone, a ring
            # that fills as the next unit comes.
            side = SMALL_RING if self.overview else RING
            beside = task_bar_rect((x, y), small=self.overview)
            # Its foot level with the bar's, and a little room between the two.
            centre = (beside.left - (side + 1) // 2 - 2, beside.bottom - (side + 1) // 2)
            pushed = self.world.rush.pushed(self.world, resident)
            ring = draw_ring(self.canvas, self.hud.skin, centre, coming, pushed, side)
            self.work_rings[resident.resident_id] = ring
            top = min(top, ring.top - 1)
        training = self.world.attributes.training(self.world, resident) if here and coming is None else None
        if training is not None:
            # At a thing to train at: a ring of its own colour, for the next point of it.
            side = SMALL_RING if self.overview else RING
            beside = task_bar_rect((x, y), small=self.overview)
            centre = (beside.left - (side + 1) // 2 - 2, beside.bottom - (side + 1) // 2)
            ring = draw_ring(self.canvas, self.hud.skin, centre, training[1], False, side, TRAINING_COLOR)
            self.train_rings[resident.resident_id] = ring
            top = min(top, ring.top - 1)
        y = top
        if with_name:
            y -= CELL_SIZE[1]
            name = self.font.render(resident.name, PALETTE["paper"])
            self.canvas.blit(name, (self._name_left(resident, x, name.get_width()), y))
        here_now = resident.resident_id in self.world.residents
        # What they are talking of, or a phrase of their own: seen from near, and not through a roof.
        shown = bubble_of(self.world, resident) if here_now and not unseen and not self.overview else None
        status = self._status_icon(resident, resting, unseen)
        if shown is not None and status == "chat":
            # The bubble says it better.
            status = None
        icons = [status, self.mark_over(resident.resident_id)]
        if here_now and resident.resident_id in self.world.wishes_of and resident.resident_id != self.hud.selected_id:
            # They want something: what, is seen by selecting them.
            icons.append(WISH_ICON)
        if here_now and any(ask.resident_id == resident.resident_id for ask in self.world.words.asks):
            # They want a word of the player, and wait for it.
            icons.append(ASK_ICON)
        if resident.resident_id in self.world.residents and has_birthday(self.world, resident):
            # A year more today: it is worn all day.
            icons.append(BIRTHDAY_ICON)
        if resident.resident_id in self.world.residents and self.world.rush.pushed(self.world, resident):
            # Pushing their post: it is over their head for as long as it lasts.
            icons.append(PUSH_ICON)
        if resident.resident_id == self.hud.selected_id:
            icons.append("selected")
        else:
            icons.append(self._bond_icon(resident))
        # From afar there is only room for what calls for attention.
        # Meals are visible in the hand itself; the overhead item remains for other item uses.
        in_hand = None if self.overview or self._meal_in_hand(resident) is not None else self._item_in_hand(resident)
        if in_hand is not None:
            y -= ITEM_ICON_SIZE[1] + 1
            draw_item(self.canvas, self.icons, in_hand, pygame.Rect(x - ITEM_ICON_SIZE[0] // 2, y, *ITEM_ICON_SIZE))
        bob = int(self.time * ANIMATION_FPS) % 2
        if self.protesting(resident):
            # Out in the square against a law: a placard held up, and shaken.
            y -= PLACARD_SIZE[1] + PLACARD_STICK + 1
            self.placards[resident.resident_id] = draw_placard(self.canvas, (x, y - bob), tilt=bob)
        for icon in icons:
            if icon is None:
                continue
            image = self.assets.image(icon_path(icon), size=ICON_SIZE)
            lift = bob if icon in BOBBING_ICONS else 0
            if icon in BARE_ICONS:
                y -= ICON_SIZE[1] + 1
                self.canvas.blit(image, (x - ICON_SIZE[0] // 2, y - lift))
            else:
                # What they are doing, in a bubble that points at them.
                y -= MARK_SIZE[1] + MARK_TAIL + 1
                draw_mark(self.canvas, image, (x, y - lift))
        wish = self.world.wishes_of.get(resident.resident_id) if here_now and not unseen and not self.overview else None
        if shown is None and wish is not None and resident.resident_id == self.hud.selected_id:
            # What whoever is selected wants, while they are saying nothing: the thing, the face or the words.
            shown = wish_shown(self.world, wish)
        if shown is not None:
            y -= bubble_size(self.font, shown)[1] + BUBBLE_TAIL + 1
            self.talk_bubbles[resident.resident_id] = draw_talk_bubble(
                self.canvas, self.font, self.icons, self.hud.faces, shown, (x, y), self.viewport
            )
            if resident.resident_id == self.hud.selected_id and said_aloud(shown):
                self.hud.spoken = (resident.resident_id, said_aloud(shown))
