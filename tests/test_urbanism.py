import json
import os
import tempfile
import unittest
from pathlib import Path

import pygame

from save.save_manager import SaveManager
from scenes.hud import SAVE_INTENT, URBANISM_INTENT
from settings import SCALE
from simulation.commands import (
    MoveBuildingCommand,
    MoveObjectCommand,
    PlaceBuildingCommand,
    PlaceObjectCommand,
    RemoveBuildingCommand,
    RemoveObjectCommand,
)
from simulation.registries import DATA_DIR, BuiltInRegistries
from simulation.world import SimulationWorld


class UrbanismDomainTests(unittest.TestCase):
    def setUp(self) -> None:
        self.world = SimulationWorld.demo_world()

    def _building_spot(self, blueprint_id: str, avoid: tuple[int, int] | None = None) -> tuple[int, int]:
        definition = self.world.registries.buildings[blueprint_id]
        for y in range(1, self.world.tile_map.height - definition.height):
            for x in range(1, self.world.tile_map.width - definition.width):
                tile = (x, y)
                if tile != avoid and self.world.urbanism.building_error(
                    self.world, definition.width, definition.height, tile
                ) is None:
                    return tile
        self.fail("the map should have a free construction site")

    def test_objects_are_placed_moved_and_removed_through_commands(self) -> None:
        placed = self.world.apply_command(PlaceObjectCommand("crate", (1, 1)))
        self.assertTrue(placed.ok)
        self.assertIn(placed.entity_id, self.world.interactables)
        self.assertIn(placed.entity_id, self.world.containers)

        moved = self.world.apply_command(MoveObjectCommand(placed.entity_id, (2, 1)))
        self.assertTrue(moved.ok)
        self.assertEqual((self.world.interactables[placed.entity_id].x, self.world.interactables[placed.entity_id].y), (2, 1))

        removed = self.world.apply_command(RemoveObjectCommand(placed.entity_id))
        self.assertTrue(removed.ok)
        self.assertNotIn(placed.entity_id, self.world.interactables)
        self.assertNotIn(placed.entity_id, self.world.containers)

    def test_buildings_change_terrain_can_move_and_restore_the_ground(self) -> None:
        start = self._building_spot("shack")
        original = [list(row) for row in self.world.tile_map.tiles]
        placed = self.world.apply_command(PlaceBuildingCommand("shack", start))
        self.assertTrue(placed.ok)
        room = self.world.rooms[placed.entity_id]
        self.assertEqual(self.world.tile_map.terrain_at((room.x, room.y)), "floor_wood")
        self.assertEqual(self.world.tile_map.terrain_at((room.x - 1, room.y - 1)), "wall")

        destination = self._building_spot("shack", avoid=start)
        moved = self.world.apply_command(MoveBuildingCommand(room.room_id, destination))
        self.assertTrue(moved.ok)
        self.assertEqual((room.x, room.y), destination)
        self.assertEqual(self.world.tile_map.tiles[start[1]][start[0]], original[start[1]][start[0]])

        removed = self.world.apply_command(RemoveBuildingCommand(room.room_id))
        self.assertTrue(removed.ok)
        self.assertNotIn(room.room_id, self.world.rooms)

    def test_a_move_is_judged_without_touching_the_settlement(self) -> None:
        start = self._building_spot("shack")
        room_id = self.world.apply_command(PlaceBuildingCommand("shack", start)).entity_id
        terrain = [list(row) for row in self.world.tile_map.tiles]
        underlays = {key: dict(value) for key, value in self.world.urbanism.underlays.items()}

        verdicts = {
            (x, y): self.world.urbanism.move_building_error(self.world, room_id, (x, y))
            for y in range(self.world.tile_map.height)
            for x in range(self.world.tile_map.width)
        }
        self.assertEqual(self.world.tile_map.tiles, terrain)
        self.assertEqual(self.world.urbanism.underlays, underlays)

        # One step aside overlaps its own walls, which must not count as an obstacle.
        self.assertIsNone(verdicts[start])
        beside = next(
            tile
            for tile, error in verdicts.items()
            if error is None and abs(tile[0] - start[0]) + abs(tile[1] - start[1]) == 1
        )
        refused = next(tile for tile, error in verdicts.items() if error is not None)
        rejected = self.world.apply_command(MoveBuildingCommand(room_id, refused))
        self.assertFalse(rejected.ok)
        self.assertEqual(rejected.message, verdicts[refused])
        self.assertEqual(self.world.tile_map.tiles, terrain)
        self.assertTrue(self.world.apply_command(MoveBuildingCommand(room_id, beside)).ok)

        crate = self.world.apply_command(PlaceObjectCommand("crate", (1, 1))).entity_id
        self.assertIsNone(self.world.urbanism.move_object_error(self.world, crate, (2, 1)))
        self.assertEqual((self.world.interactables[crate].x, self.world.interactables[crate].y), (1, 1))

    def test_edited_layout_round_trips_in_the_save(self) -> None:
        building = self.world.apply_command(PlaceBuildingCommand("shack", self._building_spot("shack")))
        furniture = self.world.apply_command(PlaceObjectCommand("stool", (1, 1)))
        self.assertTrue(building.ok and furniture.ok)
        manager = SaveManager()
        loaded = manager.from_data(manager.to_data(self.world), self.world.registries)
        self.assertEqual(manager.to_data(loaded), manager.to_data(self.world))

    def test_custom_buildings_use_the_same_blueprint_registry(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            pack = root / "buildings" / "watch_tower"
            pack.mkdir(parents=True)
            (pack / "data.json").write_text(
                json.dumps(
                    {
                        "id": "watch_tower",
                        "name": "torre de vigilancia",
                        "width": 3,
                        "height": 3,
                        "floor": "floor_concrete",
                    }
                ),
                encoding="utf-8",
            )
            registries = BuiltInRegistries.load(DATA_DIR, root)
            self.assertEqual(registries.buildings["watch_tower"].width, 3)


class UrbanismShellTests(unittest.TestCase):
    def setUp(self) -> None:
        for variable in ("SDL_VIDEODRIVER", "SDL_AUDIODRIVER"):
            previous = os.environ.get(variable)
            self.addCleanup(self._restore, variable, previous)
            os.environ[variable] = "dummy"
        from game.game import Game

        self.game = Game(illustrations_dir=None, voices_dir=None)
        self.addCleanup(pygame.quit)

    @staticmethod
    def _restore(variable: str, previous: str | None) -> None:
        if previous is None:
            os.environ.pop(variable, None)
        else:
            os.environ[variable] = previous

    def _editor(self):
        self.game.global_view._apply(URBANISM_INTENT)
        self.game.sync_scenes()
        return self.game.active_scene

    @staticmethod
    def _window(position: tuple[int, int]) -> tuple[int, int]:
        return (position[0] * SCALE, position[1] * SCALE)

    def _tile_position(self, editor, tile: tuple[int, int]) -> tuple[int, int]:
        return self._window(
            (
                editor.map_rect.x + tile[0] * editor.tile_px + editor.tile_px // 2,
                editor.map_rect.y + tile[1] * editor.tile_px + editor.tile_px // 2,
            )
        )

    def _drag(self, editor, start: tuple[int, int], end: tuple[int, int]) -> None:
        editor.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=start, button=1))
        editor.handle_event(pygame.event.Event(pygame.MOUSEMOTION, pos=end, rel=(0, 0), buttons=(1, 0, 0)))
        editor.render()
        editor.handle_event(pygame.event.Event(pygame.MOUSEBUTTONUP, pos=end, button=1))

    def _free_tiles(self, kind: str) -> list[tuple[int, int]]:
        world = self.game.world
        return [
            (x, y)
            for y in range(world.tile_map.height)
            for x in range(world.tile_map.width)
            if world.urbanism.object_error(world, kind, (x, y)) is None
        ]

    def test_dragging_out_of_the_catalogue_places_and_dragging_on_the_map_moves(self) -> None:
        editor = self._editor()
        world = self.game.world
        furniture = next(button for button in editor.buttons if button.intent == ("category", "furniture"))
        editor.handle_event(
            pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=self._window(furniture.rect.center), button=1)
        )
        editor.handle_event(
            pygame.event.Event(pygame.MOUSEBUTTONUP, pos=self._window(furniture.rect.center), button=1)
        )
        entry = next(button for button in editor.buttons if button.intent == ("catalog", "stool"))
        first, second = self._free_tiles("stool")[:2]
        before = set(world.interactables)

        self._drag(editor, self._window(entry.rect.center), self._tile_position(editor, first))
        (stool_id,) = set(world.interactables) - before
        stool = world.interactables[stool_id]
        self.assertEqual((stool.kind, stool.x, stool.y), ("stool", *first))
        self.assertEqual(editor.selection, ("object", stool_id))

        self._drag(editor, self._tile_position(editor, first), self._tile_position(editor, second))
        self.assertEqual((stool.x, stool.y), second)
        self.assertEqual(set(world.interactables) - before, {stool_id})

    def test_a_click_only_selects_and_a_drop_off_the_map_changes_nothing(self) -> None:
        editor = self._editor()
        world = self.game.world
        stool_id = world.apply_command(PlaceObjectCommand("stool", self._free_tiles("stool")[0])).entity_id
        stool = world.interactables[stool_id]
        home = (stool.x, stool.y)
        layout = {key: (placed.x, placed.y) for key, placed in world.interactables.items()}
        rooms = set(world.rooms)

        self._drag(editor, self._tile_position(editor, home), self._tile_position(editor, home))
        self.assertEqual(editor.selection, ("object", stool_id))
        self._drag(editor, self._tile_position(editor, home), self._window(editor.close_button.rect.center))
        self.assertFalse(editor.closed)
        entry = next(button for button in editor.buttons if button.intent[0] == "catalog")
        self._drag(editor, self._window(entry.rect.center), self._window((4, 4)))

        self.assertEqual({key: (placed.x, placed.y) for key, placed in world.interactables.items()}, layout)
        self.assertEqual(set(world.rooms), rooms)

    def test_visible_buttons_save_and_open_urbanism_while_time_stands_still(self) -> None:
        view = self.game.global_view
        intents = [button.intent for button in view.hud.menu]
        self.assertIn(SAVE_INTENT, intents)
        self.assertIn(URBANISM_INTENT, intents)

        saved: list[bool] = []
        self.game.save_game = lambda path=None: saved.append(True) or True
        view._apply(SAVE_INTENT)
        self.game.sync_scenes()
        self.assertEqual(saved, [True])

        view._apply(URBANISM_INTENT)
        self.game.sync_scenes()
        self.assertEqual(self.game.scene_name, "urbanism")
        minute = self.game.world.clock.total_minutes
        self.game.advance_simulation(10.0)
        self.assertEqual(self.game.world.clock.total_minutes, minute)
        self.game.active_scene.render()

        self.game.active_scene.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE))
        self.game.sync_scenes()
        self.assertEqual(self.game.scene_name, "global")


if __name__ == "__main__":
    unittest.main()
