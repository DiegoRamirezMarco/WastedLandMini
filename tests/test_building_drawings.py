import os
import tempfile
import unittest
from pathlib import Path

import pygame

from graphics.building_art import (
    BUILDING_DETAIL,
    BUILDING_PARTS,
    DOOR_PART,
    INSIDE_PART,
    ROOF_PART,
    WALLS_PART,
    building_canvas_size,
    building_part_path,
    door_columns,
)
from scenes.hud import BUILD_INTENT
from settings import SCALE, SCREEN_HEIGHT, SCREEN_WIDTH, TILE_SIZE

INSIDE = (42, 156, 92)
WALL = (54, 91, 181)
ROOF = (181, 65, 54)
DOOR = (220, 171, 61)


def _near(color: tuple[int, ...], wanted: tuple[int, int, int]) -> bool:
    return all(abs(channel - expected) <= 4 for channel, expected in zip(color[:3], wanted))


class BuildingDrawingTests(unittest.TestCase):
    def setUp(self) -> None:
        for variable in ("SDL_VIDEODRIVER", "SDL_AUDIODRIVER"):
            previous = os.environ.get(variable)
            self.addCleanup(self._restore, variable, previous)
            os.environ[variable] = "dummy"
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name) / "illustrations"
        self.root.mkdir()
        from game.game import Game

        self.game = Game(illustrations_dir=self.root, voices_dir=None)
        self.addCleanup(pygame.quit)
        self.window = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))

    @staticmethod
    def _restore(variable: str, previous: str | None) -> None:
        if previous is None:
            os.environ.pop(variable, None)
        else:
            os.environ[variable] = previous

    def _show(self) -> pygame.Surface:
        self.game.active_scene.render()
        self.game.present(self.window)
        return self.window

    def _on_window(self, tile: tuple[float, float]) -> tuple[int, int]:
        point = self.game.global_view._canvas_point(tile[0] * TILE_SIZE, tile[1] * TILE_SIZE)
        return (point[0] * SCALE, point[1] * SCALE)

    def test_f4_and_the_menu_open_a_building_editor_while_time_stands_still(self) -> None:
        view = self.game.global_view
        self.assertIn(BUILD_INTENT, [button.intent for button in view.hud.menu])
        view.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_F4))
        self.game.sync_scenes()
        editor = self.game.building_editor
        self.assertEqual(self.game.scene_name, "building_editor")
        self.assertTrue(self.game.world.rooms[editor.room_id].roofed)
        minute = self.game.world.clock.total_minutes
        self.game.advance_simulation(5.0)
        self.assertEqual(self.game.world.clock.total_minutes, minute)
        self._show()
        self.game.handle_key(pygame.K_ESCAPE)
        editor.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE, mod=0))
        self.game.sync_scenes()
        self.assertEqual(self.game.scene_name, "global")
        self.assertTrue(self.game.running)

    def test_each_part_has_an_aligned_guide_and_all_four_are_saved_at_the_display_detail(self) -> None:
        editor = self.game.building_editor
        editor.open("shop")
        room = self.game.world.rooms["shop"]
        self.assertEqual(editor.area.size, building_canvas_size(room))
        self.assertEqual(set(editor.drawings), set(BUILDING_PARTS))
        guides = {part: self.game.global_view.building_art.guide(room, part) for part in BUILDING_PARTS}
        self.assertTrue(all(guide.get_size() == editor.area.size for guide in guides.values()))
        self.assertTrue(all(pygame.mask.from_surface(guide).count() for guide in guides.values()))

        editor.color = ROOF
        editor._set_part(ROOF_PART)
        editor.press((editor.area.x + 20, editor.area.y + 20))
        editor.release()
        self.assertEqual(tuple(editor.drawings[ROOF_PART].get_at((20, 20)))[:3], ROOF)
        self.assertTrue(editor.save())
        for part in BUILDING_PARTS:
            saved = pygame.image.load(str(self.root / building_part_path("shop", part)))
            self.assertEqual(saved.get_size(), building_canvas_size(room))

    def test_the_game_assembles_the_parts_and_exchanges_the_roof_for_the_inside(self) -> None:
        editor = self.game.building_editor
        editor.open("shop")
        room = self.game.world.rooms["shop"]
        tile = TILE_SIZE * BUILDING_DETAIL
        width, height = editor.area.size
        facade_top = height - 2 * tile

        editor.drawings[INSIDE_PART].fill((0, 0, 0, 0))
        pygame.draw.rect(editor.drawings[INSIDE_PART], INSIDE, (tile, tile * 2, room.width * tile, room.height * tile))
        editor.drawings[WALLS_PART].fill((0, 0, 0, 0))
        pygame.draw.rect(editor.drawings[WALLS_PART], WALL, (0, facade_top, width, height - facade_top))
        editor.drawings[ROOF_PART].fill((0, 0, 0, 0))
        pygame.draw.rect(editor.drawings[ROOF_PART], ROOF, (0, 0, width, facade_top))
        editor.drawings[DOOR_PART].fill((0, 0, 0, 0))
        door_column = door_columns(self.game.world.tile_map, room)[0]
        pygame.draw.rect(editor.drawings[DOOR_PART], DOOR, (door_column * tile, facade_top, tile, height - facade_top))
        self.assertTrue(editor.save())
        editor.closed = True
        self.game.sync_scenes()

        view = self.game.global_view
        # A clear patch of floor, away from the shelves and counter in the top row.
        inside = (room.x + 1.5, room.y + 1.5)
        view.centre_on(inside)
        closed = self._show()
        self.assertTrue(_near(tuple(closed.get_at(self._on_window(inside))), ROOF))

        # With the roof off, the same point is the independently drawn empty interior.
        view.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_t))
        opened = self._show()
        self.assertTrue(_near(tuple(opened.get_at(self._on_window(inside))), INSIDE))
        door_tile = (room.x - 1 + door_column + 0.5, room.y + room.height + 0.5)
        self.assertTrue(_near(tuple(opened.get_at(self._on_window(door_tile))), DOOR))

    def test_a_building_can_be_drawn_without_a_drawn_map_and_others_keep_the_old_art(self) -> None:
        editor = self.game.building_editor
        editor.open("shop")
        editor._set_part(ROOF_PART)
        editor.drawings[ROOF_PART] = editor.buildings.starter(self.game.world.rooms["shop"], ROOF_PART)
        editor.drawings[ROOF_PART].fill(ROOF)
        editor.save()
        editor.closed = True
        self.game.sync_scenes()
        view = self.game.global_view
        shop = self.game.world.rooms["shop"]
        point = (shop.x + 1.5, shop.y + 0.5)
        view.centre_on(point)
        self.assertTrue(_near(tuple(self._show().get_at(self._on_window(point))), ROOF))
        self.assertIsNone(view.building_art.closed(self.game.world.rooms["dormitory"]))


if __name__ == "__main__":
    unittest.main()
