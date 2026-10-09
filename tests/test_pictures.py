import os
import tempfile
import unittest
from pathlib import Path

import pygame

from graphics import building_pictures, ground_pictures, item_pictures
from graphics.object_pictures import DEPTH, FRAMES, PAINTERS, ObjectPictures, footprint
from settings import SCALE, TILE_SIZE
from simulation.residents.activity import Activity
from simulation.world import SimulationWorld
from world.room import Room


def _dummy(case: unittest.TestCase) -> None:
    for variable in ("SDL_VIDEODRIVER", "SDL_AUDIODRIVER"):
        previous = os.environ.get(variable)
        case.addCleanup(lambda name=variable, was=previous: os.environ.pop(name, None) if was is None else os.environ.update({name: was}))
        os.environ[variable] = "dummy"


class GamePictureTests(unittest.TestCase):
    """What the game draws for itself by code (P41): furniture, items, buildings and the ground."""

    def setUp(self) -> None:
        _dummy(self)
        pygame.init()
        pygame.display.set_mode((16, 16))
        self.addCleanup(pygame.quit)
        self.world = SimulationWorld.demo_world()

    def test_every_kind_of_object_there_is_has_a_picture_for_the_ground_it_takes(self) -> None:
        kinds = self.world.registries.interactables
        pictures = ObjectPictures()
        for kind in kinds.kinds():
            definition = kinds.get(kind)
            self.assertIn(kind, PAINTERS)
            self.assertEqual(footprint(kind), (definition.width, definition.height), kind)
            self.assertTrue(pictures.has(kind, definition.width, definition.height))
        self.assertFalse(pictures.has("bed", 3, 3), "a kind a pack has made another size of keeps the art it had")
        self.assertFalse(pictures.has("throne", 1, 1))

    def test_a_picture_is_as_wide_as_its_cells_and_stands_up_from_their_near_edge(self) -> None:
        pictures = ObjectPictures()
        for cell in (32, 64, 118):
            depth = round(cell * DEPTH)
            for kind in PAINTERS:
                wide, deep = footprint(kind)
                picture = pictures.at(kind, cell)
                self.assertEqual(picture.under.get_width(), wide * cell, kind)
                self.assertEqual(picture.under.get_height(), picture.rise + deep * depth, kind)
                self.assertGreater(pygame.mask.from_surface(picture.under).count(), cell * cell // 12, kind)
                if picture.over is not None:
                    self.assertEqual(picture.over.get_size(), picture.under.get_size(), kind)
        self.assertIs(pictures.at("crate", 64), pictures.at("crate", 64), "made once and kept")
        self.assertEqual(pictures.whole("bed", 64).get_size(), pictures.at("bed", 64).under.get_size())

    def test_what_burns_goes_through_its_turns_and_the_rest_stands_still(self) -> None:
        pictures = ObjectPictures()
        for kind in PAINTERS:
            turns = [pygame.image.tobytes(pictures.at(kind, 48, frame).under, "RGBA") for frame in range(3)]
            if kind in FRAMES:
                self.assertGreater(len(set(turns)), 1, kind)
            else:
                self.assertEqual(len(set(turns)), 1, kind)
        self.assertEqual(pictures.frames("campfire"), 3)
        self.assertEqual(pictures.frames("table"), 1)

    def test_a_bed_says_where_a_head_goes_and_a_shelf_where_its_goods_do(self) -> None:
        pictures = ObjectPictures()
        for kind in ("bed", "clinic_bed"):
            picture = pictures.at(kind, 100)
            self.assertIsNotNone(picture.over, "its blanket goes over whoever lies in it")
            neck = picture.neck
            self.assertAlmostEqual(neck[0], 50, delta=1)
            self.assertGreater(neck[1], picture.rise, "on the mattress, below the headboard")
            self.assertEqual(picture.over.get_at((50, round(neck[1]) - 12)).a, 0, "and nothing covers the face")
        shelf = pictures.at("shelf", 100)
        self.assertEqual(len(shelf.slots), 6)
        self.assertGreater(shelf.slot_size, 20)
        for x, y in shelf.slots:
            self.assertTrue(0 <= x and x + shelf.slot_size <= 200 and 0 <= y and y + shelf.slot_size <= shelf.under.get_height())
        self.assertIsNone(pictures.at("table", 100).neck)
        self.assertEqual(pictures.at("table", 100).slots, ())

    def test_every_item_the_game_comes_with_has_a_picture(self) -> None:
        import json

        own = json.loads((Path(__file__).resolve().parent.parent / "data" / "items.json").read_text(encoding="utf-8"))
        # What a pack brings comes with its own picture: these are the ones in the game's own data.
        for entry in own:
            self.assertTrue(item_pictures.painted(entry["id"]), entry["id"])
        for item_id in item_pictures.PAINTERS:
            for size in (32, 96):
                picture = item_pictures.picture(item_id, size)
                self.assertEqual(picture.get_size(), (size, size))
                self.assertGreater(pygame.mask.from_surface(picture).count(), size * size // 10, item_id)
        self.assertFalse(item_pictures.painted("throne"))

    def test_a_building_is_a_roof_over_a_front_with_a_door_where_its_door_is(self) -> None:
        room = Room("hall", "sala", width=5, height=3, roofed=True)
        cell = 40
        closed = building_pictures.closed(room, cell, (3,))
        self.assertEqual(closed.get_size(), ((room.width + 2) * cell, (room.height + 3) * cell))
        roof = closed.get_at((cell * 3, cell * 2))
        front = closed.get_at((cell + 8, closed.get_height() - cell))
        door = closed.get_at((cell * 3 + cell // 2, closed.get_height() - cell // 2))
        self.assertNotEqual(tuple(roof)[:3], tuple(front)[:3])
        self.assertNotEqual(tuple(door)[:3], tuple(front)[:3], "the door is no part of the boards")
        elsewhere = building_pictures.closed(room, cell, (1,))
        self.assertNotEqual(tuple(elsewhere.get_at((cell * 3 + cell // 2, closed.get_height() - cell // 2)))[:3], tuple(door)[:3])
        self.assertEqual(pygame.image.tobytes(closed, "RGBA"), pygame.image.tobytes(building_pictures.closed(room, cell, (3,)), "RGBA"))
        other = building_pictures.closed(Room("barn", "granero", width=5, height=3, roofed=True), cell, (3,))
        self.assertNotEqual(pygame.image.tobytes(closed, "RGBA"), pygame.image.tobytes(other, "RGBA"), "no two look quite alike")

    def test_a_building_with_its_roof_off_is_its_floor_and_walls_with_the_front_one_cut_low(self) -> None:
        room = Room("hall", "sala", width=5, height=3, roofed=True)
        cell = 40
        back = building_pictures.opened(room, cell, (3,), "floor_wood", False)
        front = building_pictures.opened(room, cell, (3,), "floor_wood", True)
        self.assertEqual(back.get_size(), front.get_size())
        middle = (back.get_width() // 2, cell * 3 + cell // 2)
        self.assertGreater(back.get_at(middle).a, 240, "the floor")
        self.assertEqual(front.get_at(middle).a, 0, "which the wall in front does not cover")
        foot = front.get_height() - cell // 3
        self.assertGreater(front.get_at((cell + cell // 2, foot)).a, 200, "the wall in front, at the foot of it all")
        self.assertEqual(front.get_at((cell + cell // 2, front.get_height() - cell + 4)).a, 0, "cut low, to see over")
        concrete = building_pictures.opened(room, cell, (3,), "floor_concrete", False)
        self.assertNotEqual(tuple(concrete.get_at(middle))[:3], tuple(back.get_at(middle))[:3])

    def test_the_ground_is_one_picture_of_the_whole_map_with_each_kind_of_it_in_its_place(self) -> None:
        tile_map = self.world.tile_map
        cell = 16
        ground = ground_pictures.ground(tile_map, cell, 5)
        self.assertEqual(ground.get_size(), (tile_map.width * cell, tile_map.height * cell))
        self.assertEqual(ground.get_at((5, 5)).a, 255)

        def middle_of(terrain: str) -> tuple[int, int, int]:
            x, y = next(
                (x, y)
                for y in range(1, tile_map.height - 1)
                for x in range(1, tile_map.width - 1)
                if all(tile_map.terrain_at((x + dx, y + dy)) == terrain for dx in (-1, 0, 1) for dy in (-1, 0, 1))
            )
            return tuple(ground.get_at((x * cell + cell // 2, y * cell + cell // 2)))[:3]

        soil, floor = middle_of("soil"), middle_of("floor_wood")
        self.assertNotEqual(soil, floor)
        self.assertLess(sum(floor), 240, "what is under a roof is dark: a building's own picture goes over it")
        fence = tuple(ground.get_at((tile_map.width * cell // 4, (tile_map.height - 1) * cell + cell // 2)))[:3]
        self.assertNotEqual(fence, soil)
        self.assertEqual(
            pygame.image.tobytes(ground, "RGBA"), pygame.image.tobytes(ground_pictures.ground(tile_map, cell, 5), "RGBA"), "the same every time"
        )


class PicturesOnTheMapTests(unittest.TestCase):
    """The map as the game draws it on the window, through the real game shell without a window."""

    def setUp(self) -> None:
        _dummy(self)
        from game.game import Game

        keep = tempfile.TemporaryDirectory()
        self.addCleanup(keep.cleanup)
        self.root = Path(keep.name) / "illustrations"
        self.root.mkdir()
        self.game = Game(illustrations_dir=self.root, voices_dir=None, start_in_menu=False)
        self.addCleanup(pygame.quit)
        self.view, self.world = self.game.global_view, self.game.world

    def _window(self) -> pygame.Surface:
        self.view.render()
        window = pygame.Surface(self.game.screen.get_size())
        self.game.present(window)
        return window

    def test_with_no_window_under_the_canvas_everything_is_the_art_there_was(self) -> None:
        from game.game import Game

        plain = Game(illustrations_dir=None, voices_dir=None, start_in_menu=False)
        view = plain.global_view
        self.assertFalse(view.windowed)
        view.render()
        self.assertIsNone(view._ground())
        self.assertIsNone(view._doll_of("paco"))
        self.assertIsNone(view._game_picture(plain.world.registries.interactables.get("table")))
        self.assertIsNone(view._building_picture(plain.world.rooms["shop"], "closed"))
        self.assertFalse(plain.icons.painted)
        self.assertEqual(plain.icons.picture("scrap").get_size(), (16, 16))

    def test_the_ground_buildings_and_objects_are_the_games_own_pictures(self) -> None:
        view, world = self.view, self.world
        self.assertTrue(view.windowed)
        self._window()
        self.assertTrue(view._ground_painted)
        tile_map = world.tile_map
        self.assertEqual(view._ground().get_size(), (tile_map.width * TILE_SIZE * 2, tile_map.height * TILE_SIZE * 2))
        shop = world.rooms["shop"]
        for part in ("closed", "background", "foreground"):
            picture = view._building_picture(shop, part)
            self.assertEqual(picture.get_size(), ((shop.width + 2) * view._cell, (shop.height + 3) * view._cell), part)
            self.assertIs(view._building_picture(shop, part), picture, "made once for the size it is seen at")
        table = world.registries.interactables.get("table")
        self.assertEqual(view._game_picture(table).under.get_width(), 2 * view._cell)
        self.assertTrue(self.game.icons.painted)
        self.assertGreater(self.game.icons.picture("scrap").get_width(), 16)

    def test_a_picture_of_the_players_own_is_shown_on_the_map_in_place_of_the_games(self) -> None:
        view, world = self.view, self.world
        bed = world.registries.interactables.get("bed")
        self.assertIsNotNone(view._game_picture(bed))
        own = pygame.Surface((64, 128), pygame.SRCALPHA)
        own.fill((10, 200, 30, 255))
        (self.root / "objects").mkdir()
        pygame.image.save(own, str(self.root / "objects" / "bed.png"))
        view.object_art.forget("bed")
        self.assertIsNone(view._game_picture(bed), "theirs is what the map shows")
        placed = next(each for each in world.interactables.values() if each.kind == "bed")
        view.roofs_on = False
        view.centre_on((placed.x, placed.y))
        shown = [entry for entry in view._object_pictures(view._visible_region()) if entry[1][0] == placed.x * TILE_SIZE]
        self.assertTrue(any(tuple(picture.get_at((4, 4)))[:3] == (10, 200, 30) for _, _, picture in shown))
        # Inside the building it is the game's, which is drawn for that view.
        room = world.room_at((placed.x, placed.y))
        layout = view.interior.layout(room)
        self.assertEqual(len(view.interior._object(room, layout, placed)), 2)
        # And a building somebody has drawn a part of is left to them.
        (self.root / "buildings" / "shop").mkdir(parents=True)
        shop = world.rooms["shop"]
        from graphics.building_art import building_canvas_size

        roof = pygame.Surface(building_canvas_size(shop), pygame.SRCALPHA)
        roof.fill((200, 10, 30, 255))
        pygame.image.save(roof, str(self.root / "buildings" / "shop" / "roof.png"))
        view.building_art._closed.clear()
        view.building_art._open.clear()
        self.assertEqual(tuple(view._building_picture(shop, "closed").get_at((8, 8)))[:3], (200, 10, 30))
        self.assertIsNone(view._building_picture(shop, "foreground"), "what they left out stays out")

    def test_whoever_stands_nearer_is_drawn_over_what_is_behind_them(self) -> None:
        view, world = self.view, self.world
        table = next(each for each in world.interactables.values() if each.kind == "table")
        paco = world.residents["paco"]
        view.centre_on((table.x, table.y))
        for row, in_front in ((table.y + 1, True), (table.y - 1, False)):
            paco.x, paco.y, paco.trail, paco.activity = table.x, row, [], Activity("wander", minutes_left=600, using=True)
            self._window()
            foot = (table.y + 1) * TILE_SIZE
            mine = next(entry[0] for entry in view._doll_draws if entry[1] is view.doll_shown["paco"])
            self.assertEqual(mine > foot - 0.5, in_front, "by how far down the map their feet are")

    def test_the_map_is_drawn_again_when_a_building_goes_up(self) -> None:
        view = self.view
        self._window()
        ground, shop = view._ground(), view._building_picture(self.world.rooms["shop"], "closed")
        self.assertIs(view._ground(), ground)
        view._read_layout()
        self.assertIsNot(view._ground(), ground)
        self.assertIsNot(view._building_picture(self.world.rooms["shop"], "closed"), shop)

    def test_every_zoom_and_the_night_are_drawn(self) -> None:
        view = self.view
        for zoom in range(4):
            view.set_zoom(zoom)
            window = self._window()
            centre = view.viewport.center
            self.assertNotEqual(tuple(window.get_at((centre[0] * SCALE, centre[1] * SCALE)))[:3], (0, 0, 0))
        self.world.clock.hour = 2
        self._window()
        view.roofs_on = False
        self._window()


if __name__ == "__main__":
    unittest.main()
