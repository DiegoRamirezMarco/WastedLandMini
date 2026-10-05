import contextlib
import wave
import io
import logging
import tempfile
import unittest
from pathlib import Path

import pygame

from graphics.assets import ASSETS_DIR, PLACEHOLDER_COLORS, AssetStore
from graphics.character_renderer import FACINGS, FRAME_SIZE, SHEET_SIZE, CharacterRenderer
from graphics.palette import PALETTE
from graphics.face_renderer import EXPRESSIONS, FACE_SIZE, MARKER_SIZE, FaceRenderer
from audio.audio_manager import load_sound_map
from graphics.font import CELL_SIZE, FONT_CHARS, FONT_SHEET, BitmapFont
from graphics.font import SHEET_SIZE as FONT_SHEET_SIZE
from graphics.icons import ICON_SIZE
from graphics.item_icons import ICON_SIZE as ITEM_ICON_SIZE
from graphics.item_icons import ItemIcons
from graphics.map_renderer import render_roofs, render_terrain, roof_names, tile_names
from graphics.tileset import (
    ROOF_CELLS,
    ROOF_SHEET,
    ROOF_SHEET_SIZE,
    SETTLEMENT_CELLS,
    SETTLEMENT_SHEET,
    SETTLEMENT_SHEET_SIZE,
    Tileset,
)
from settings import TILE_SIZE
from simulation.items.registry import ItemRegistry
from simulation.registries import DATA_DIR
from simulation.world import SimulationWorld
from tools.art.sounds import SOUNDS, duration_ms
from tools.make_art import build_all, main as make_art


def _pngs() -> list[Path]:
    return sorted(ASSETS_DIR.rglob("*.png"))


class ArtContractTests(unittest.TestCase):
    """Every PNG under assets/ follows docs/visual-style.md, generated or hand-made."""

    def test_pixels_use_the_palette_and_binary_alpha(self) -> None:
        allowed = set(PALETTE.values())
        for path in _pngs():
            surface = pygame.image.load(str(path))
            for y in range(surface.get_height()):
                for x in range(surface.get_width()):
                    red, green, blue, alpha = surface.get_at((x, y))
                    where = f"{path.relative_to(ASSETS_DIR)} at ({x}, {y})"
                    self.assertIn(alpha, (0, 255), f"Partial alpha in {where}")
                    if alpha:
                        self.assertIn((red, green, blue), allowed, f"Off-palette colour in {where}")

    def test_sizes_match_their_folder(self) -> None:
        for path in _pngs():
            relative = path.relative_to(ASSETS_DIR)
            size = pygame.image.load(str(path)).get_size()
            folder = relative.parts[:2] if relative.parts[0] == "sprites" else relative.parts[:1]
            if folder == ("sprites", "residents"):
                self.assertEqual(size, SHEET_SIZE, relative)
            elif folder == ("sprites", "items"):
                self.assertEqual(size, (TILE_SIZE, TILE_SIZE), relative)
            elif folder == ("faces",):
                self.assertEqual(size, FACE_SIZE, relative)
            elif folder in (("sprites", "tiles"), ("sprites", "objects")):
                self.assertEqual((size[0] % TILE_SIZE, size[1] % TILE_SIZE), (0, 0), relative)

    def test_file_names_are_lowercase_snake_case(self) -> None:
        for path in _pngs():
            stem = path.stem
            self.assertTrue(stem.isascii() and stem == stem.lower() and " " not in stem, path.name)


class ArtGeneratorTests(unittest.TestCase):
    def test_generator_never_overwrites_an_existing_png(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            edited = out / SETTLEMENT_SHEET
            edited.parent.mkdir(parents=True)
            edited.write_bytes(b"hand edited")
            with contextlib.redirect_stdout(io.StringIO()):
                make_art(["--out", str(out)])
            self.assertEqual(edited.read_bytes(), b"hand edited")
            self.assertTrue((out / "sprites/objects/bed.png").exists())

    def test_settlement_sheet_covers_every_named_tile(self) -> None:
        sheet = build_all()[SETTLEMENT_SHEET]
        self.assertEqual(sheet.get_size(), SETTLEMENT_SHEET_SIZE)
        tiles = Tileset(sheet, SETTLEMENT_CELLS)
        for name in SETTLEMENT_CELLS:
            self.assertEqual(tiles.tile(name).get_at((8, 8))[3], 255, name)

    def test_roof_sheet_covers_every_named_tile_in_blocks_that_survive_being_halved(self) -> None:
        sheet = build_all()[ROOF_SHEET]
        self.assertEqual(sheet.get_size(), ROOF_SHEET_SIZE)
        tiles = Tileset(sheet, ROOF_CELLS)
        for name in ROOF_CELLS:
            tile = tiles.tile(name)
            for y in range(0, TILE_SIZE, 2):
                for x in range(0, TILE_SIZE, 2):
                    block = {tuple(tile.get_at((x + dx, y + dy))) for dx in (0, 1) for dy in (0, 1)}
                    self.assertEqual(len(block), 1, (name, x, y))
                    self.assertEqual(block.pop()[3], 255, (name, x, y))

    def test_unknown_tile_name_gives_a_placeholder(self) -> None:
        tiles = Tileset(build_all()[SETTLEMENT_SHEET], SETTLEMENT_CELLS)
        self.assertIn(tuple(tiles.tile("lava").get_at((0, 0)))[:3], PLACEHOLDER_COLORS)


class SettlementArtCoverageTests(unittest.TestCase):
    """The built-in settlement is drawn entirely with real art, never placeholders."""

    def setUp(self) -> None:
        self.world = SimulationWorld.demo_world()

    def test_every_terrain_on_the_map_has_a_tile(self) -> None:
        tile_map = self.world.tile_map
        for y in range(tile_map.height):
            for x in range(tile_map.width):
                for name in tile_names(tile_map, x, y):
                    self.assertIn(name, SETTLEMENT_CELLS, (x, y))

    def test_fence_and_walls_show_their_face_where_they_end(self) -> None:
        tile_map = self.world.tile_map
        bottom = tile_map.height - 1
        self.assertEqual(tile_names(tile_map, 0, 0)[0], "dirt")
        self.assertIn(tile_names(tile_map, 0, 0)[-1], ("fence_face", "fence_face_rusty"))
        self.assertEqual(tile_names(tile_map, 0, 5)[-1], "fence_top")
        self.assertIn(tile_names(tile_map, 5, bottom)[-1], ("fence_face", "fence_face_rusty"))
        self.assertEqual(tile_names(tile_map, 2, 4), ["wall_top"])
        self.assertIn(tile_names(tile_map, 3, 2)[0], ("wall_face", "wall_face_window"))

    def test_roofs_cover_buildings_and_leave_their_front_wall_in_view(self) -> None:
        tile_map, rooms = self.world.tile_map, self.world.rooms
        roofs = roof_names(tile_map, rooms.values())
        self.assertLessEqual(set(roofs.values()), ROOF_CELLS.keys())
        for room in rooms.values():
            inside = [
                (x, y) for x in range(room.x, room.x + room.width) for y in range(room.y, room.y + room.height)
            ]
            if not room.roofed:
                self.assertFalse(roofs.keys() & set(inside), room.room_id)
                continue
            self.assertLessEqual(set(inside), roofs.keys(), room.room_id)
            # The walls behind and beside are under the roof; the one with the door is not.
            self.assertIn((room.x - 1, room.y - 1), roofs, room.room_id)
            self.assertIn((room.x + room.width, room.y), roofs, room.room_id)
            front = room.y + room.height
            self.assertEqual(roofs[(room.x, front - 1)], "roof_eave", room.room_id)
            for x in range(room.x - 1, room.x + room.width + 1):
                self.assertNotIn((x, front), roofs, room.room_id)
                self.assertIn(tile_map.terrain_at((x, front)), ("wall", "door"), room.room_id)

    def test_roofs_are_drawn_over_the_terrain_and_nowhere_else(self) -> None:
        tile_map = self.world.tile_map
        store = AssetStore(ASSETS_DIR)
        ground = Tileset(store.image(SETTLEMENT_SHEET, size=SETTLEMENT_SHEET_SIZE), SETTLEMENT_CELLS)
        tin = Tileset(store.image(ROOF_SHEET, size=ROOF_SHEET_SIZE), ROOF_CELLS)
        terrain = render_terrain(tile_map, ground)
        before = _pixels(terrain)
        roofs = roof_names(tile_map, self.world.rooms.values())
        roofed = render_roofs(terrain, roofs, tin)
        self.assertEqual(_pixels(terrain), before, "the terrain without roofs must be left as it was")
        for y in range(tile_map.height):
            for x in range(tile_map.width):
                corner = (x * TILE_SIZE, y * TILE_SIZE)
                source = tin.tile(roofs[(x, y)]) if (x, y) in roofs else terrain.subsurface((*corner, 1, 1))
                self.assertEqual(roofed.get_at(corner)[:3], source.get_at((0, 0))[:3], (x, y))

    def test_every_object_kind_and_resident_has_a_sprite(self) -> None:
        for kind in self.world.registries.interactables.kinds():
            definition = self.world.registries.interactables.get(kind)
            path = ASSETS_DIR / f"sprites/objects/{kind}.png"
            self.assertTrue(path.exists(), kind)
            width, height = pygame.image.load(str(path)).get_size()
            # Animated objects hold several frames side by side.
            self.assertEqual(width % (definition.width * TILE_SIZE), 0, kind)
            self.assertGreaterEqual(height, definition.height * TILE_SIZE, kind)
        for resident_id in self.world.residents:
            self.assertTrue((ASSETS_DIR / f"sprites/residents/{resident_id}.png").exists(), resident_id)


class CharacterRendererTests(unittest.TestCase):
    def test_every_facing_has_a_frame(self) -> None:
        renderer = CharacterRenderer(AssetStore(ASSETS_DIR))
        for facing in FACINGS:
            self.assertEqual(renderer.frame("marta", facing, step=1).get_size(), FRAME_SIZE)

    def test_left_frame_mirrors_right_frame(self) -> None:
        renderer = CharacterRenderer(AssetStore(ASSETS_DIR))
        left, right = renderer.frame("raul", "left"), renderer.frame("raul", "right")
        for x in range(FRAME_SIZE[0]):
            self.assertEqual(left.get_at((x, 8)), right.get_at((FRAME_SIZE[0] - 1 - x, 8)))

    def test_unknown_body_draws_a_placeholder_frame(self) -> None:
        logging.disable(logging.WARNING)
        self.addCleanup(logging.disable, logging.NOTSET)
        renderer = CharacterRenderer(AssetStore(ASSETS_DIR))
        frame = renderer.frame("nobody")
        self.assertEqual(frame.get_size(), FRAME_SIZE)
        self.assertIn(tuple(frame.get_at((0, 0)))[:3], PLACEHOLDER_COLORS)


def _pixels(surface: pygame.Surface) -> list[tuple[int, ...]]:
    return [
        tuple(surface.get_at((x, y)))
        for x in range(surface.get_width())
        for y in range(surface.get_height())
    ]


class BitmapFontTests(unittest.TestCase):
    def setUp(self) -> None:
        self.font = BitmapFont(AssetStore(ASSETS_DIR).image(FONT_SHEET, size=FONT_SHEET_SIZE))

    def test_every_character_has_its_own_glyph(self) -> None:
        missing = self.font.render("\u20ac", PALETTE["paper"])
        for char in FONT_CHARS.strip():
            glyph = self.font.render(char, PALETTE["paper"])
            same = glyph.get_size() == missing.get_size() and _pixels(glyph) == _pixels(missing)
            self.assertFalse(same, f"{char!r} draws as the missing glyph")

    def test_accented_letters_exist_and_differ_from_plain_ones(self) -> None:
        for plain, accented in zip("aeiounAEIOUN", "áéíóúñÁÉÍÓÚÑ"):
            self.assertIn(accented, FONT_CHARS)
            plain_glyph = self.font.render(plain, PALETTE["paper"])
            accented_glyph = self.font.render(accented, PALETTE["paper"])
            self.assertNotEqual(_pixels(plain_glyph), _pixels(accented_glyph), accented)

    def test_text_is_proportional_and_drawn_in_the_exact_colour(self) -> None:
        self.assertLess(self.font.width("ill"), self.font.width("MMM"))
        self.assertEqual(self.font.width(""), 0)
        surface = self.font.render("Día 1", PALETTE["lamp"])
        self.assertEqual(surface.get_size(), (self.font.width("Día 1"), CELL_SIZE[1]))
        self.assertEqual(set(_pixels(surface)), {(*PALETTE["lamp"], 255), (0, 0, 0, 0)})

    def test_scaled_text_is_a_whole_multiple(self) -> None:
        small = self.font.render("Hola", PALETTE["paper"])
        big = self.font.render("Hola", PALETTE["paper"], scale=2)
        self.assertEqual(big.get_size(), (small.get_width() * 2, small.get_height() * 2))

    def test_truncate_fits_the_width_and_leaves_short_text_alone(self) -> None:
        long = "Anoche hizo un frío de mil demonios en todo el asentamiento"
        cut = self.font.truncate(long, 120)
        self.assertLessEqual(self.font.width(cut), 120)
        self.assertTrue(cut.endswith("...") and long.startswith(cut[:-3]))
        self.assertEqual(self.font.truncate("Hola", 120), "Hola")

    def test_icons_have_the_contract_size(self) -> None:
        icons = sorted((ASSETS_DIR / "ui").glob("icon_*.png"))
        self.assertTrue(icons)
        for path in icons:
            self.assertEqual(pygame.image.load(str(path)).get_size(), ICON_SIZE, path.name)


class FaceRendererTests(unittest.TestCase):
    def setUp(self) -> None:
        logging.disable(logging.WARNING)
        self.addCleanup(logging.disable, logging.NOTSET)
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.custom_root = Path(self._tmp.name)
        self.faces = FaceRenderer(AssetStore(ASSETS_DIR), AssetStore(self.custom_root))

    def _custom(self, face_id: str, name: str, color: str) -> None:
        folder = self.custom_root / "faces" / face_id
        folder.mkdir(parents=True, exist_ok=True)
        surface = pygame.Surface(FACE_SIZE, pygame.SRCALPHA)
        surface.fill(PALETTE[color])
        pygame.image.save(surface, str(folder / name))

    def test_every_resident_has_a_face_for_every_expression_and_they_differ(self) -> None:
        for face_id in SimulationWorld.demo_world().residents:
            seen = set()
            for expression in EXPRESSIONS:
                face = self.faces.face(face_id, expression)
                self.assertEqual(face.get_size(), FACE_SIZE)
                self.assertFalse(any(tuple(p)[:3] in PLACEHOLDER_COLORS[:1] for p in _pixels(face)), face_id)
                seen.add(tuple(_pixels(face)))
            self.assertEqual(len(seen), len(EXPRESSIONS), face_id)

    def test_layer_files_exist_for_every_expression(self) -> None:
        for layer in ("eyes", "brows", "mouth"):
            for expression in EXPRESSIONS:
                self.assertTrue((ASSETS_DIR / "faces" / layer / f"{expression}.png").exists(), (layer, expression))

    def test_unknown_resident_and_unknown_expression_fall_back_safely(self) -> None:
        stranger = self.faces.face("nobody", "angry")
        self.assertEqual(stranger.get_size(), FACE_SIZE)
        self.assertIn(PLACEHOLDER_COLORS[0], {tuple(p)[:3] for p in _pixels(stranger)})
        self.assertIs(self.faces.face("marta", "smug"), self.faces.face("marta", "neutral"))

    def test_a_custom_face_replaces_the_layered_one_for_its_expression(self) -> None:
        self._custom("marta", "neutral.png", "teal")
        self._custom("marta", "angry.png", "blood")
        self.assertEqual(tuple(self.faces.face("marta", "angry").get_at((0, 0)))[:3], PALETTE["blood"])
        self.assertEqual(tuple(self.faces.face("marta", "neutral").get_at((0, 0)))[:3], PALETTE["teal"])
        self.assertEqual(tuple(self.faces.face("marta", "sad").get_at((0, 0)))[:3], PALETTE["teal"])
        self.assertNotEqual(tuple(self.faces.face("raul", "sad").get_at((32, 30)))[:3], PALETTE["teal"])

    def test_a_marker_is_the_face_made_small_in_the_same_colours(self) -> None:
        allowed = {(*color, 255) for color in PALETTE.values()} | {(0, 0, 0, 0)}
        seen = set()
        for face_id in SimulationWorld.demo_world().residents:
            marker = self.faces.marker(face_id)
            self.assertEqual(marker.get_size(), MARKER_SIZE)
            pixels = [pixel if pixel[3] else (0, 0, 0, 0) for pixel in _pixels(marker)]
            self.assertLessEqual(set(pixels), allowed, face_id)
            self.assertIn((*PALETTE["ink"], 255), pixels, face_id)
            seen.add(tuple(pixels))
        self.assertEqual(len(seen), len(SimulationWorld.demo_world().residents), "two residents look alike")
        self.assertIs(self.faces.marker("marta"), self.faces.marker("marta", "smug"))

    def test_markers_follow_custom_faces_and_fall_back_safely(self) -> None:
        self._custom("lucia", "portrait.png", "rose")
        self.assertEqual({tuple(p) for p in _pixels(self.faces.marker("lucia"))}, {(*PALETTE["rose"], 255)})
        stranger = self.faces.marker("nobody")
        self.assertEqual(stranger.get_size(), MARKER_SIZE)
        self.assertIn(PLACEHOLDER_COLORS[0], {tuple(p)[:3] for p in _pixels(stranger)})

    def test_a_single_custom_image_is_used_for_every_expression(self) -> None:
        self._custom("lucia", "portrait.png", "rose")
        for expression in EXPRESSIONS:
            self.assertEqual(tuple(self.faces.face("lucia", expression).get_at((5, 5)))[:3], PALETTE["rose"])

    def test_text_wraps_between_words_within_the_width(self) -> None:
        font = BitmapFont(AssetStore(ASSETS_DIR).image(FONT_SHEET, size=FONT_SHEET_SIZE))
        text = "Raúl va a buscar a Marta para decirle cuatro cosas (consejo: Dale, dale)"
        lines = font.wrap(text, 150)
        self.assertGreater(len(lines), 1)
        self.assertEqual(" ".join(lines), text)
        for line in lines:
            self.assertLessEqual(font.width(line), 150)
        self.assertEqual(font.wrap("", 150), [])


class ItemIconTests(unittest.TestCase):
    def setUp(self) -> None:
        logging.disable(logging.WARNING)
        self.addCleanup(logging.disable, logging.NOTSET)
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.custom_root = Path(self._tmp.name)
        self.icons = ItemIcons(AssetStore(ASSETS_DIR), AssetStore(self.custom_root))

    def _pack_icon(self, folder: str, item_id: str, size: tuple[int, int]) -> None:
        path = self.custom_root / folder / item_id
        path.mkdir(parents=True)
        surface = pygame.Surface(size, pygame.SRCALPHA)
        surface.fill(PALETTE["rose"])
        pygame.image.save(surface, str(path / "icon.png"))

    def test_every_built_in_item_has_an_icon(self) -> None:
        registry = ItemRegistry()
        registry.load_collection_json_file(DATA_DIR / "items.json")
        for item_id in registry.ids():
            icon = self.icons.icon(item_id)
            self.assertEqual(icon.get_size(), ITEM_ICON_SIZE)
            self.assertNotIn(PLACEHOLDER_COLORS[0], {tuple(p)[:3] for p in _pixels(icon)}, item_id)

    def test_the_bundled_example_packs_have_icons_that_follow_the_contract(self) -> None:
        bundled = ItemIcons(AssetStore(ASSETS_DIR), AssetStore(ASSETS_DIR.parent / "custom_content"))
        allowed = {(*color, 255) for color in PALETTE.values()} | {(0, 0, 0, 0)}
        for item_id in ("pizza_radioactiva", "peluche_maligno"):
            icon = bundled.icon(item_id)
            self.assertEqual(icon.get_size(), ITEM_ICON_SIZE)
            self.assertTrue({tuple(p) if p[3] else (0, 0, 0, 0) for p in _pixels(icon)} <= allowed, item_id)
            self.assertNotIn(PLACEHOLDER_COLORS[0], {tuple(p)[:3] for p in _pixels(icon)}, item_id)

    def test_a_pack_icon_of_any_size_is_brought_down_to_ours(self) -> None:
        self._pack_icon("foods", "broth", (128, 128))
        icon = self.icons.icon("broth")
        self.assertEqual(icon.get_size(), ITEM_ICON_SIZE)
        self.assertEqual(tuple(icon.get_at((8, 8)))[:3], PALETTE["rose"])

    def test_an_item_without_an_icon_gets_the_placeholder(self) -> None:
        self.assertIn(PLACEHOLDER_COLORS[0], {tuple(p)[:3] for p in _pixels(self.icons.icon("mystery"))})


class SoundTests(unittest.TestCase):
    def test_every_sound_is_a_short_valid_wav(self) -> None:
        for name, notes in SOUNDS.items():
            path = ASSETS_DIR / "sounds" / f"{name}.wav"
            self.assertTrue(path.exists(), name)
            with wave.open(str(path), "rb") as sound:
                self.assertEqual((sound.getnchannels(), sound.getsampwidth(), sound.getframerate()), (1, 2, 22050))
                milliseconds = sound.getnframes() * 1000 // sound.getframerate()
            self.assertLess(abs(milliseconds - duration_ms(notes)), 5, name)
            self.assertLess(milliseconds, 600, name)

    def test_every_event_sound_exists(self) -> None:
        mapping = load_sound_map(DATA_DIR / "audio.json")
        self.assertIn("crisis_opened", mapping)
        for event_type, sound in mapping.items():
            self.assertIn(sound, SOUNDS, event_type)

    def test_a_missing_or_broken_sound_map_means_silence_not_a_crash(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(load_sound_map(Path(tmp) / "nope.json"), {})
            broken = Path(tmp) / "audio.json"
            broken.write_text("{ not json", encoding="utf-8")
            self.assertEqual(load_sound_map(broken), {})


if __name__ == "__main__":
    unittest.main()
