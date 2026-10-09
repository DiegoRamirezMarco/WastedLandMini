"""Training on screen (P61): told from the wheel or by putting somebody down on the thing,
what is said of a thing to train at, and the ring over whoever is at one."""

import os
import unittest

import pygame

from graphics.assets import ASSETS_DIR
from graphics.icons import icon_path
from graphics.object_pictures import PAINTERS
from graphics.palette import PALETTE
from graphics.ui_art import GLYPHS, HUES
from simulation.ai.placing import WHICH_USE
from simulation.residents.attributes import Attributes
from simulation.residents.needs import Needs
from ui.affect_wheel import TASKS
from ui.decor_board import FURNITURE
from ui.decor_board import entries as decor_entries
from ui.work_marks import TRAINING_COLOR
from world.interactable import Interactable

GYM = "gym"
ORDER = "task:train"
KINDS = ("weights", "chess_table", "target", "skipping_rope", "dummy", "training_log")


class TrainingScreenTests(unittest.TestCase):
    def setUp(self) -> None:
        for variable in ("SDL_VIDEODRIVER", "SDL_AUDIODRIVER"):
            self.addCleanup(self._restore_driver, variable, os.environ.get(variable))
            os.environ[variable] = "dummy"
        from game.game import Game

        self.game = Game(illustrations_dir=None, voices_dir=None, start_in_menu=False)
        self.addCleanup(pygame.quit)
        self.view, self.world, self.hud = self.game.global_view, self.game.world, self.game.global_view.hud
        self.world.relationships.clear()
        self.world.clock.hour = 9
        for resident in self.world.residents.values():
            resident.attributes = Attributes()
            resident.needs = Needs(hunger=0, thirst=0, tiredness=0, social=0, stress=0)

    @staticmethod
    def _restore_driver(variable: str, previous: str | None) -> None:
        if previous is None:
            os.environ.pop(variable, None)
        else:
            os.environ[variable] = previous

    def _stand(self, kind: str, level: int = 1) -> Interactable:
        junk = next(placed for placed in self.world.interactables.values() if placed.kind == "junk")
        del self.world.interactables[junk.object_id]
        self.world.interactables[GYM] = Interactable(GYM, kind, junk.x, junk.y, level)
        return self.world.interactables[GYM]

    def _frame(self) -> None:
        self.view.update(0.0)
        self.view.render()

    def _press(self, intent) -> None:
        entry = next(entry for entry in self.hud.wheel_entries() if entry.intent == intent)
        self.view.click(entry.rect.center)

    def _until_training(self, resident_id: str) -> None:
        for _ in range(180):
            if self.world.attributes.training(self.world, self.world.residents[resident_id]) is not None:
                return
            self.world.step(1)
        self.fail("never got to it")

    def test_each_thing_to_train_at_has_its_picture_and_training_its_icon(self) -> None:
        for kind in KINDS:
            self.assertIn(kind, PAINTERS)
            self.assertTrue((ASSETS_DIR / "sprites" / "objects" / f"{kind}.png").is_file(), kind)
        self.assertIn("train", GLYPHS)
        self.assertIn("train", HUES)
        self.assertTrue((ASSETS_DIR / icon_path("train")).is_file())
        self.assertEqual(self.world.registries.affect.tasks["train"].icon, "train")

    def test_they_have_a_tab_of_their_own_in_the_catalogue_and_are_no_furniture(self) -> None:
        from scenes.urbanism import PANEL_WIDTH

        editor = self.game.urbanism_editor
        editor.open()
        tab = next(button for button in editor.category_buttons if button.intent == ("category", "training"))
        self.assertEqual(tab.label, "Entreno")
        self.assertLessEqual(max(button.rect.right for button in editor.category_buttons), PANEL_WIDTH)
        editor.category = "training"
        self.assertEqual([entry.entry_id for entry in editor._catalog()], list(KINDS))
        self.assertEqual(editor._catalog_scroll(), 0, "all of it is in sight")
        editor.render()
        editor.category = "furniture"
        self.assertFalse(set(KINDS) & {entry.entry_id for entry in editor._catalog()})
        self.assertEqual(editor._catalog_scroll(), 0, "and so is the furniture, as before")
        self.assertFalse(set(KINDS) & {entry.entry_id for entry in decor_entries(self.world, FURNITURE)})

    def test_what_is_said_of_a_thing_to_train_at_is_what_for_and_how_far(self) -> None:
        placed = self._stand("weights")
        self.hud.select_object(GYM)
        said = [line.text for line, _ in self.hud.object_view().lines]
        self.assertEqual(said[0], "Pesas")
        self.assertIn("Para entrenar fuerza: hasta 6", said)
        self.assertIn("Mejor, llegaría a 7", said)
        placed.level = 5
        said = [line.text for line, _ in self.hud.object_view().lines]
        self.assertIn("Para entrenar fuerza: hasta 10", said)
        self.assertFalse(any(text.startswith("Mejor, llegaría") for text in said))
        self._frame()

    def test_it_is_told_from_the_wheel_and_whoever_trains_has_a_ring_of_their_own(self) -> None:
        self._stand("target")
        self.hud.select_resident("ines")
        self._frame()
        self.view._toggle_affect()
        self.assertTrue(self.hud.wheel.open)
        self._press(("affect_branch", TASKS))
        self._press(("affect", ORDER))
        self._frame()
        self._press(("affect_target", ORDER, GYM))
        self.assertFalse(self.hud.wheel.open)
        self.assertIn("entrene", self.hud.notice)
        self._until_training("ines")
        self.world.step(30)
        self.view.set_zoom(2)
        self.view.centre_on_resident("ines")
        self._frame()
        self.assertIn("ines", self.view.train_rings)
        self.assertNotIn("ines", self.view.work_rings)
        # And they are seen hard at it, as at any work done with bare hands.
        self.assertEqual(self.view._work_of(self.world.residents["ines"]), (self.view.poses.work, None))
        ring = self.view.train_rings["ines"]
        colours = {
            tuple(self.view.canvas.get_at((x, y)))[:3]
            for x in range(ring.left, ring.right)
            for y in range(ring.top, ring.bottom)
        }
        self.assertFalse(PALETTE["ember"] in colours, "it is no ring of a post being pushed")
        self.assertEqual(TRAINING_COLOR, "teal")
        # Whoever is at their post has the ring of the post, and no other.
        self.assertFalse(set(self.view.train_rings) & set(self.view.work_rings))

    def test_putting_somebody_down_on_it_says_what_will_come_of_it(self) -> None:
        self._stand("skipping_rope")
        offered = self.world.placements("ines", object_id=GYM)
        self.assertEqual((offered[0].kind, offered[0].text), ("use", "Entrenar"))
        # For whoever it has nothing left to teach there is no training to be put down to. It is
        # still something to skip with for the sake of it (S60), and it is asked what they do there (P63).
        self.world.residents["ines"].attributes.dexterity = 6.0
        used = [each for each in self.world.placements("ines", object_id=GYM) if each.kind == "use"]
        self.assertEqual([(each.opens, each.text) for each in used], [(True, WHICH_USE)])
        self.assertNotIn("Entrenar", [each.text for each in used])


if __name__ == "__main__":
    unittest.main()
