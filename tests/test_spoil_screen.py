"""What goes off, on screen (S65, P60): how far gone a thing is on its square, what is said of
the chest and of a bed that takes compost, and the field of the item editor for it."""

import json
import os
import tempfile
import unittest
from pathlib import Path

import pygame

from graphics.object_pictures import PAINTERS, footprint
from simulation.items.inventory import Inventory
from ui.inventory_view import draw_container_panel
from ui.labels import condition_of, days_left_label
from ui.object_marks import NO_CURRENT, marks_of
from ui.object_panel import compost_intent, speaks
from world.interactable import Interactable

CHEST = "chest"


class SpoilScreenTests(unittest.TestCase):
    def setUp(self) -> None:
        for variable in ("SDL_VIDEODRIVER", "SDL_AUDIODRIVER"):
            self.addCleanup(self._restore_driver, variable, os.environ.get(variable))
            os.environ[variable] = "dummy"
        keep = tempfile.TemporaryDirectory()
        self.addCleanup(keep.cleanup)
        from game.game import Game

        self.root = Path(keep.name)
        self.game = Game(illustrations_dir=None, voices_dir=None, custom_content_dir=self.root, start_in_menu=False)
        self.addCleanup(pygame.quit)
        self.view, self.world, self.hud = self.game.global_view, self.game.world, self.game.global_view.hud

    @staticmethod
    def _restore_driver(variable: str, previous: str | None) -> None:
        if previous is None:
            os.environ.pop(variable, None)
        else:
            os.environ[variable] = previous

    def _said(self) -> list[str]:
        view = self.hud.object_view()
        return [line.text for line, _ in view.lines] if view is not None else []

    def _press(self, intent) -> None:
        button = next(button for button in self.hud.buttons if button.intent == intent)
        self.view.click(button.rect.center)

    def _stand_chest(self) -> Inventory:
        self.world.interactables[CHEST] = Interactable(CHEST, "refrigerated_chest", 30, 20)
        self.world.containers[CHEST] = Inventory()
        return self.world.containers[CHEST]

    def test_the_bar_under_a_thing_that_goes_off_says_how_fresh_it_is(self) -> None:
        world = self.world
        crate = world.containers["crate_dorm"]
        crate.items.clear()
        greens = world.stock(crate, "vegetables", 3, "ines", freshness=35.0)
        tins = world.stock(crate, "canned_beans", 3, "ines")
        hoe = world.stock(crate, "hoe", 1, "ines")
        hoe.condition = 60.0
        self.assertEqual(condition_of(world, greens), 35.0)
        self.assertIsNone(condition_of(world, tins))
        self.assertEqual(condition_of(world, hoe), 60.0, "what wears is as it was")
        self.assertEqual(days_left_label(world, greens), "1 d")
        self.assertIsNone(days_left_label(world, tins))
        greens.freshness = 10.0
        self.assertEqual(days_left_label(world, greens), "<1 d")
        # And the list of what a place holds says how long each has, kept there.
        said: list[str] = []
        font = self.view.font
        draw, font.draw = font.draw, lambda target, text, *rest, **more: said.append(text)
        self.addCleanup(setattr, font, "draw", draw)
        draw_container_panel(pygame.Surface((220, 120)), font, self.view.icons, (0, 0), world, "crate_dorm", 220)
        self.assertTrue(any("x3 · <1 d" in text for text in said), said)
        self.assertFalse(any("judías" in text and "·" in text for text in said), said)

    def test_what_is_said_of_the_chest_is_whether_it_is_keeping_what_is_in_it(self) -> None:
        world = self.world
        chest = self._stand_chest()
        world.stock(chest, "vegetables", 10, None)
        self.assertTrue(speaks(world, world.interactables[CHEST]))
        self.hud.select_object(CHEST)
        said = self._said()
        self.assertEqual(said[0], "Arcón refrigerado")
        self.assertIn("Corriente: gasta 1. Encendido", said)
        self.assertIn("Enfría: lo que guarda dura 4 veces más", said)
        self.assertIn("Comida: 10 de 40", said)
        world.switch(CHEST, False)
        self.assertIn("No enfría: apagado", self._said())
        world.switch(CHEST, True)
        fuel = world.registries.power.fuel
        for inventory in world.containers.values():
            inventory.items[:] = [item for item in inventory.items if item.definition_id != fuel]
        self.assertIn("No enfría: sin corriente", self._said())
        self.assertEqual(marks_of(world)[CHEST], NO_CURRENT)
        self.view.render()
        self.assertEqual(footprint("refrigerated_chest"), (2, 1))
        self.assertIn("refrigerated_chest", PAINTERS)

    def test_compost_is_put_on_a_bed_from_what_is_said_of_it(self) -> None:
        world = self.world
        self.hud.select_object("crop_1")
        self.assertIn("Hace falta abono: 2, y hay 0", " ".join(self._said()))
        self.assertNotIn(compost_intent("crop_1"), [button.intent for button in self.hud.buttons])
        world.stock(world.containers["warehouse"], "compost", 3, None)
        self.assertIn("Abono: hay 3. Con 2, da más durante 3 días", " ".join(self._said()))
        self._press(compost_intent("crop_1"))
        self.assertIn("crop_1", world.dressed)
        self.assertEqual(world.spoilage.compost_held(world), 1)
        self.assertIn("abono", self.hud.notice)
        day = world.dressed["crop_1"] // (24 * 60) + 1
        self.assertIn(f"Abonado: da más hasta el día {day}", self._said())
        self.assertNotIn(compost_intent("crop_1"), [button.intent for button in self.hud.buttons])
        # A post that is no bed says nothing of compost.
        self.hud.select_object("workbench")
        self.assertFalse(any("bono" in text for text in self._said()))

    def test_the_item_editor_says_how_fast_a_thing_goes_off_and_takes_another_figure(self) -> None:
        editor = self.game.item_editor
        editor.open("stew")
        self.assertEqual(editor.values["spoils"], "34")
        self.assertTrue(all(rect.bottom < self.game.canvas.get_height() for rect in editor.field_rects.values()))
        editor.render()
        editor.values["spoils"] = "12,5"
        self.assertTrue(editor.save(), editor.notice)
        data = json.loads((self.root / "items" / "stew" / "data.json").read_text(encoding="utf-8"))
        self.assertEqual(data["spoils"], 12.5)
        self.assertEqual(self.world.registries.items.get("stew").spoils, 12.5)
        # A thing that kept can be made to go off, and one that went off to keep.
        editor.open("canned_beans")
        self.assertEqual(editor.values["spoils"], "0")
        editor.values["spoils"] = "50"
        self.assertTrue(editor.save(), editor.notice)
        self.assertTrue(self.world.spoilage.goes_off(self.world, "canned_beans"))
        editor.open("stew")
        editor.values["spoils"] = ""
        self.assertTrue(editor.save(), editor.notice)
        self.assertFalse(self.world.spoilage.goes_off(self.world, "stew"))
        for wrong in ("mucho", "-3", "140"):
            editor.values["spoils"] = wrong
            self.assertFalse(editor.save(), wrong)
            self.assertIn("No se pudo guardar", editor.notice)
        self.assertEqual(self.world.registries.items.get("stew").spoils, 0.0)


if __name__ == "__main__":
    unittest.main()
