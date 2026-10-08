"""What each is capable of, and the level they have at their job, as the window shows them (P52)."""

import os
import unittest

import pygame

from simulation.residents.attributes import ATTRIBUTES, CHARISMA, MIND, STRENGTH
from ui.labels import describe_holders, describe_job
from ui.resident_panel import attribute_cells, relationship_hitboxes, tab_hitbox


class _Shell(unittest.TestCase):
    """The real game shell without a window."""

    in_menu = False

    def setUp(self) -> None:
        for variable in ("SDL_VIDEODRIVER", "SDL_AUDIODRIVER"):
            self.addCleanup(self._restore_driver, variable, os.environ.get(variable))
            os.environ[variable] = "dummy"
        from game.game import Game

        self.game = Game(illustrations_dir=None, voices_dir=None, start_in_menu=self.in_menu)
        self.addCleanup(pygame.quit)

    @staticmethod
    def _restore_driver(variable: str, previous: str | None) -> None:
        if previous is None:
            os.environ.pop(variable, None)
        else:
            os.environ[variable] = previous


class PanelTests(_Shell):
    def setUp(self) -> None:
        super().setUp()
        self.view, self.hud, self.world = self.game.global_view, self.game.global_view.hud, self.game.world

    def test_the_six_are_in_a_row_under_the_bars(self) -> None:
        self.hud.select_resident("raul")
        self.view.render()
        panel = self.hud.layout.panel
        cells = attribute_cells(panel, self.world)
        self.assertEqual([name for _, name in cells], list(ATTRIBUTES))
        self.assertEqual(len({cell.y for cell, _ in cells}), 1)
        boxes = [cell for cell, _ in cells]
        for index, cell in enumerate(boxes):
            self.assertTrue(panel.contains(cell), cell)
            self.assertEqual(cell.collidelist(boxes[index + 1 :]), -1)
        widest = max(self.view.font.width(f"{each.short}10") for each in self.world.registries.attributes.attributes.values())
        self.assertLessEqual(widest, boxes[0].width, "three letters and two figures fit in each")

    def test_what_comes_under_them_starts_under_them(self) -> None:
        self.hud.select_resident("raul")
        panel = self.hud.layout.panel
        cells = attribute_cells(panel, self.world)
        raul = self.world.residents["raul"]
        self.assertGreaterEqual(tab_hitbox(panel).top, cells[0][0].bottom - 1)
        rows = relationship_hitboxes(panel, self.world, raul)
        self.assertTrue(rows)
        self.assertGreater(rows[0][0].top, cells[0][0].bottom)
        # A click on somebody listed there still picks them.
        self.view.render()
        self.view.click(rows[0][0].center)
        self.assertEqual(self.hud.selected_id, rows[0][1])

    def test_a_job_is_said_with_the_level_whoever_does_it_has(self) -> None:
        world = self.world
        raul = world.residents["raul"]
        self.assertNotIn("nivel", describe_job(world, raul), "at the first there is nothing to say")
        self.assertIn("Raúl,", describe_holders(world, "farmer") + ",")
        raul.trade["farmer"] = float(world.registries.crafts.levels[2])
        self.assertIn("Huerto, nivel 3", describe_job(world, raul))
        self.assertIn("Raúl nv3", describe_holders(world, "farmer"))
        self.hud.select_resident("raul")
        self.hud.toggle_jobs()
        self.view.render()


class CreatorTests(_Shell):
    in_menu = True

    def setUp(self) -> None:
        super().setUp()
        self.game.main_menu.choose("new")
        self.game.sync_scenes()
        self.creator = self.game.creator

    def _press(self, intent) -> None:
        button = next(button for button in self.creator.buttons if button.intent == intent)
        self.creator._apply(button.intent)

    def test_there_is_a_face_for_what_they_are_capable_of(self) -> None:
        creator = self.creator
        self.assertEqual([button.intent[1] for button in creator.page_buttons], ["person", "manners", "able"])
        creator._apply(("page", "able"))
        self.assertEqual(set(creator.attributes), set(ATTRIBUTES))
        self.assertTrue(all(value == 5 for value in creator.attributes.values()))
        self.assertEqual(creator.points_left(), 3)
        boxes = [button.rect for button in creator.buttons]
        for index, box in enumerate(boxes):
            self.assertTrue(self.game.canvas.get_rect().contains(box), box)
            self.assertEqual(box.collidelist(boxes[index + 1 :]), -1, box)
        self.game.active_scene.render()

    def test_points_are_shared_out_and_there_are_only_so_many(self) -> None:
        creator = self.creator
        creator._apply(("page", "able"))
        for _ in range(5):
            self._press(("attribute", STRENGTH, 1))
        self.assertEqual((creator.attributes[STRENGTH], creator.points_left()), (8, 0), "there were three to give")
        self._press(("attribute", MIND, -1))
        self._press(("attribute", MIND, -1))
        self.assertEqual(creator.points_left(), 2, "what is taken from one is there to give to another")
        self._press(("attribute", STRENGTH, 1))
        self._press(("attribute", STRENGTH, 1))
        self._press(("attribute", STRENGTH, 1))
        self.assertEqual((creator.attributes[STRENGTH], creator.points_left()), (10, 0))
        for _ in range(12):
            self._press(("attribute", MIND, -1))
        self.assertEqual(creator.attributes[MIND], 1, "nothing goes under the lowest")
        for _ in range(12):
            self._press(("attribute", STRENGTH, 1))
        self.assertEqual(creator.attributes[STRENGTH], 10, "nor over the highest")

    def test_whoever_is_made_is_as_they_were_made(self) -> None:
        creator = self.creator
        creator.set_name("Ada")
        creator._apply(("page", "able"))
        self._press(("attribute", MIND, -1))
        self._press(("attribute", STRENGTH, 1))
        self._press(("attribute", CHARISMA, 1))
        self._press(("attribute", CHARISMA, 1))
        resident_id = creator.create()
        self.assertIsNotNone(resident_id)
        world = self.game.world
        ada = world.residents[resident_id]
        levels = world.attributes.levels(world, ada)
        self.assertEqual((levels[STRENGTH], levels[MIND], levels[CHARISMA]), (6, 4, 7))
        self.assertAlmostEqual(ada.personality.charisma, (7 - 1) / 9 * 100, places=1)

    def test_opened_again_it_starts_from_the_middle(self) -> None:
        creator = self.creator
        creator._apply(("page", "able"))
        self._press(("attribute", STRENGTH, 1))
        creator.open()
        self.assertEqual(creator.attributes[STRENGTH], 5)
        self.assertEqual(creator.page, "person")


if __name__ == "__main__":
    unittest.main()
