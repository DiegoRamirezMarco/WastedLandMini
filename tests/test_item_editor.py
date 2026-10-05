import json
import os
import tempfile
import unittest
from pathlib import Path

import pygame

from graphics.palette import PALETTE
from settings import SCALE
from ui.inventory_view import container_item_hitboxes
from ui.resident_panel import inventory_hitboxes


class ItemEditorTests(unittest.TestCase):
    def setUp(self) -> None:
        for variable in ("SDL_VIDEODRIVER", "SDL_AUDIODRIVER"):
            self.addCleanup(self._restore_driver, variable, os.environ.get(variable))
            os.environ[variable] = "dummy"
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        from game.game import Game

        self.root = Path(self.temporary.name)
        self.game = Game(illustrations_dir=None, voices_dir=None, custom_content_dir=self.root, start_in_menu=False)
        self.addCleanup(pygame.quit)

    @staticmethod
    def _restore_driver(variable: str, previous: str | None) -> None:
        if previous is None:
            os.environ.pop(variable, None)
        else:
            os.environ[variable] = previous

    @staticmethod
    def _window(position: tuple[int, int]) -> tuple[int, int]:
        return position[0] * SCALE + 1, position[1] * SCALE + 1

    def test_clicking_a_resident_inventory_item_opens_its_editor(self) -> None:
        view = self.game.global_view
        resident = self.game.world.residents["raul"]
        view.hud.select_resident(resident.resident_id)
        rect, definition_id = inventory_hitboxes(view.hud.layout.panel, self.game.world, resident)[0]

        view.click(rect.center)
        self.game.sync_scenes()

        self.assertEqual(self.game.scene_name, "item_editor")
        self.assertEqual(self.game.item_editor.item_id, definition_id)
        before = self.game.world.clock.total_minutes
        self.game.advance_simulation(30)
        self.assertEqual(self.game.world.clock.total_minutes, before)

    def test_clicking_an_item_inside_map_furniture_opens_its_editor(self) -> None:
        view = self.game.global_view
        view.hud.select_container("crate_dorm")
        rect, definition_id = container_item_hitboxes(
            view.hud.layout.panel.topleft, self.game.world, "crate_dorm", view.hud.layout.panel.width
        )[0]

        view.click(rect.center)
        self.game.sync_scenes()

        self.assertEqual(self.game.scene_name, "item_editor")
        self.assertEqual(self.game.item_editor.item_id, definition_id)

    def test_saving_changes_data_art_and_live_definition_but_not_instance_ids(self) -> None:
        editor = self.game.item_editor
        resident = self.game.world.residents["raul"]
        carried = resident.inventory.items[0]
        original_instance_id = carried.instance_id
        editor.open(carried.definition_id)
        editor.values.update(
            {
                "name": "azada de prueba",
                "article": "una",
                "category": "tool",
                "base_value": "37",
                "description": "Hecha dentro del juego.",
                "tags": "garden, heavy",
                "effects": "stress=-2",
                "properties": "wear=1.5, damage=4",
            }
        )
        editor.picture.fill((*PALETTE["ember"], 255))

        self.assertTrue(editor.save(), editor.notice)

        pack = self.root / "items" / "hoe"
        data = json.loads((pack / "data.json").read_text(encoding="utf-8"))
        self.assertEqual(data["name"], "azada de prueba")
        self.assertEqual(data["properties"], {"wear": 1.5, "damage": 4.0})
        self.assertTrue((pack / "icon.png").is_file())
        changed = self.game.world.registries.items.get("hoe")
        self.assertEqual((changed.name, changed.base_value), ("azada de prueba", 37))
        self.assertEqual((carried.instance_id, carried.definition_id), (original_instance_id, "hoe"))
        self.assertEqual(self.game.icons.icon("hoe").get_at((0, 0))[:3], PALETTE["ember"])

    def test_invalid_numeric_data_is_not_written(self) -> None:
        editor = self.game.item_editor
        editor.open("hoe")
        editor.values["effects"] = "hunger=mucho"

        self.assertFalse(editor.save())
        self.assertFalse((self.root / "items" / "hoe" / "data.json").exists())
        self.assertIn("No se pudo guardar", editor.notice)

    def test_keyboard_edits_the_selected_field_and_tab_moves_to_the_next(self) -> None:
        editor = self.game.item_editor
        editor.open("hoe")
        editor.active_field = "name"
        old = editor.values["name"]

        editor.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_x, unicode="x", mod=0))
        editor.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_TAB, unicode="\t", mod=0))

        self.assertEqual(editor.values["name"], old + "x")
        self.assertEqual(editor.active_field, "article")


if __name__ == "__main__":
    unittest.main()
