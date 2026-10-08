"""How rare a thing is, on screen (P60): the border of its square, wherever things are shown."""

import os
import unittest

import pygame

from graphics.font import LINE_HEIGHT
from graphics.item_icons import ICON_SIZE
from ui.inventory_view import PADDING, ROW_HEIGHT, draw_container_panel, draw_item_row
from ui.labels import rarity_color, rarity_name


class RarityOnScreenTests(unittest.TestCase):
    def setUp(self) -> None:
        for variable in ("SDL_VIDEODRIVER", "SDL_AUDIODRIVER"):
            self.addCleanup(self._restore_driver, variable, os.environ.get(variable))
            os.environ[variable] = "dummy"
        from game.game import Game

        self.game = Game(illustrations_dir=None, voices_dir=None, start_in_menu=False)
        self.addCleanup(pygame.quit)
        self.view, self.world = self.game.global_view, self.game.world

    @staticmethod
    def _restore_driver(variable: str, previous: str | None) -> None:
        if previous is None:
            os.environ.pop(variable, None)
        else:
            os.environ[variable] = previous

    def test_each_rarity_has_the_colour_the_user_gave_it(self) -> None:
        names = [rarity_name(self.world, level) for level in range(1, 7)]
        self.assertEqual(names, ["Común", "Poco común", "Raro", "Épico", "Legendario", "Mítico"])
        white, green, blue, red, purple, yellow = (rarity_color(self.world, level) for level in range(1, 7))
        self.assertTrue(min(white) > 200, "white")
        self.assertTrue(green[1] > green[0] and green[1] > green[2], "green")
        self.assertTrue(blue[2] > blue[0] and blue[2] > blue[1], "blue")
        self.assertTrue(red[0] > red[1] + 80 and red[0] > red[2] + 80, "red")
        self.assertTrue(purple[0] > purple[1] and purple[2] > purple[1], "purple")
        self.assertTrue(yellow[0] > 200 and yellow[1] > 150 and yellow[2] < 120, "yellow")

    def test_in_what_a_container_holds_the_border_of_each_square_is_its_rarity(self) -> None:
        crate = self.world.containers["crate_dorm"]
        crate.items.clear()
        for level in (1, 3, 6):
            self.world.stock(crate, "hoe", 1, None, level)
        surface = pygame.Surface((220, 120))
        draw_container_panel(surface, self.view.font, self.view.icons, (0, 0), self.world, "crate_dorm")
        top = PADDING + LINE_HEIGHT + 2
        for row, level in enumerate((1, 3, 6)):
            corner = (PADDING - 1, top + row * ROW_HEIGHT - 1)
            self.assertEqual(tuple(surface.get_at(corner))[:3], rarity_color(self.world, level), level)
            far = (corner[0] + ICON_SIZE[0] + 1, corner[1] + ICON_SIZE[1] + 1)
            self.assertEqual(tuple(surface.get_at(far))[:3], rarity_color(self.world, level), level)

    def test_in_a_row_of_what_somebody_carries_too(self) -> None:
        ines = self.world.residents["ines"]
        ines.inventory.items.clear()
        self.world.stock(ines.inventory, "hoe", 1, "ines", 4)
        self.world.stock(ines.inventory, "canned_beans", 2, "ines")
        surface = pygame.Surface((200, 40))
        draw_item_row(surface, self.view.font, self.view.icons, (10, 10), self.world, ines.inventory, "ines", 180)
        self.assertEqual(tuple(surface.get_at((9, 9)))[:3], rarity_color(self.world, 4))
        colours = {tuple(surface.get_at((x, 9)))[:3] for x in range(9, 190)}
        self.assertIn(rarity_color(self.world, 1), colours, "what is common has its border too, in white")

    def test_and_in_the_squares_of_whoever_is_selected(self) -> None:
        ines = self.world.residents["ines"]
        ines.inventory.items.clear()
        self.world.stock(ines.inventory, "hoe", 1, "ines", 5)
        self.view.hud.select_resident("ines")
        self.view.update(0.0)
        self.view.render()
        purple = rarity_color(self.world, 5)
        panel = self.view.hud.layout.panel
        found = any(
            tuple(self.view.canvas.get_at((x, y)))[:3] == purple
            for x in range(panel.left, panel.right)
            for y in range(panel.top, panel.bottom)
        )
        self.assertTrue(found, "nothing in the panel has the border of what is legendary")


if __name__ == "__main__":
    unittest.main()
