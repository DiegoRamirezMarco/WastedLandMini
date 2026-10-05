import json
import os
import tempfile
import unittest
from pathlib import Path

import pygame

from save.save_manager import SaveManager
from scenes.hud import SAVE_INTENT, URBANISM_INTENT
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
