import os
import unittest

import pygame

from scenes.hud import GOVERNMENT_INTENT, JOBS_INTENT
from ui.government_board import (
    CHOOSE_LABEL,
    CONFIRM_LABEL,
    choose_intent,
    describe_kind,
    law_lines,
    status_lines,
)


class GovernmentScreenTests(unittest.TestCase):
    """The entry of the menu for how the settlement is governed, through the real game shell without a window."""

    def setUp(self) -> None:
        for variable in ("SDL_VIDEODRIVER", "SDL_AUDIODRIVER"):
            self.addCleanup(self._restore_driver, variable, os.environ.get(variable))
            os.environ[variable] = "dummy"
        from game.game import Game

        self.game = Game(illustrations_dir=None, voices_dir=None, start_in_menu=False)
        self.addCleanup(pygame.quit)
        self.view, self.hud, self.world = self.game.global_view, self.game.global_view.hud, self.game.world

    @staticmethod
    def _restore_driver(variable: str, previous: str | None) -> None:
        if previous is None:
            os.environ.pop(variable, None)
        else:
            os.environ[variable] = previous

    def _entry(self) -> pygame.Rect:
        return next(button for button in self.hud.menu if button.intent == GOVERNMENT_INTENT).rect

    def _choose(self, government_id: str):
        return next(button for button in self.hud.buttons if button.intent == choose_intent(government_id))

    def test_the_menu_opens_it_over_the_map_and_shuts_it_again(self) -> None:
        self.assertFalse(self.hud.government_open)
        self.view.click(self._entry().center)
        self.assertTrue(self.hud.government_open)
        self.view.render()
        board = self.hud.government_rect()
        self.assertTrue(self.hud.layout.map.contains(board))
        self.assertTrue(self.hud.covers(board.center), "a click on it does not fall through to the map")
        self.view.click(next(button for button in self.hud.menu if button.intent == JOBS_INTENT).rect.center)
        self.assertFalse(self.hud.government_open, "one panel at a time in that corner")
        self.view.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_p, mod=0, unicode="p"))
        self.assertTrue(self.hud.government_open)
        self.view.click(self._entry().center)
        self.assertFalse(self.hud.government_open)

    def test_there_is_nothing_to_choose_until_they_have_to_govern_themselves(self) -> None:
        self.world.government.choosing_until = None
        self.hud.toggle_government()
        self.view.render()
        self.assertEqual([button for button in self.hud.buttons if button.label == CHOOSE_LABEL], [])
        self.assertIn("pocos", status_lines(self.world)[0][0])

    def test_a_kind_is_chosen_with_two_presses_and_the_settlement_has_it(self) -> None:
        self.world.step(1)
        self.assertIsNotNone(self.world.government.choosing_until)
        self.hud.toggle_government()
        self.view.render()
        kinds = list(self.world.registries.politics.governments)
        self.assertEqual(len([button for button in self.hud.buttons if button.label == CHOOSE_LABEL]), len(kinds))
        self.view.click(self._choose("commune").rect.center)
        self.assertIsNone(self.world.government.kind, "once is only saying which")
        self.assertEqual(self._choose("commune").label, CONFIRM_LABEL)
        # Pressing for another instead is saying which again.
        self.view.click(self._choose("council").rect.center)
        self.assertIsNone(self.world.government.kind)
        self.assertEqual(self._choose("commune").label, CHOOSE_LABEL)
        self.view.click(self._choose("council").rect.center)
        self.assertEqual(self.world.government.kind, "council")
        self.assertIn("Consejo", self.hud.notice)
        self.view.render()
        # What they have is not offered again, and the rest still are.
        offered = {button.intent for button in self.hud.buttons if button.label == CHOOSE_LABEL}
        self.assertEqual(offered, {choose_intent(kind) for kind in kinds if kind != "council"})
        self.view.click(self._choose("strong_mayor").rect.center)
        self.view.click(self._choose("strong_mayor").rect.center)
        self.assertEqual(self.world.government.kind, "strong_mayor")

    def test_shutting_the_panel_forgets_a_first_press(self) -> None:
        self.world.step(1)
        self.hud.toggle_government()
        self.view.click(self._choose("commune").rect.center)
        self.assertEqual(self.hud.government_armed, "commune")
        self.hud.toggle_government()
        self.hud.toggle_government()
        self.assertIsNone(self.hud.government_armed)

    def test_it_says_who_holds_the_seats_and_what_laws_there_are(self) -> None:
        world = self.world
        world.politics.leadership.establish(world, "strong_mayor")
        leader = world.residents[world.government.leader]
        said = " ".join(text for text, _ in status_lines(world))
        self.assertIn("Alcaldía", said)
        self.assertIn(leader.name, said)
        self.assertEqual(law_lines(self.view.font, world, 300), ["Ninguna ley en vigor."])
        law_id = next(iter(world.registries.laws.laws))
        self.assertTrue(world.politics.laws.enact(world, law_id))
        self.assertIn(world.registries.laws.laws[law_id].name, " ".join(law_lines(self.view.font, world, 300)))
        world.politics.leadership.change_kind(world, "council")
        self.assertIn("Consejo:", " ".join(text for text, _ in status_lines(world)))
        self.hud.toggle_government()
        self.view.render()

    def test_every_kind_is_put_into_words_from_its_data(self) -> None:
        governments = self.world.registries.politics.governments
        lines = {government_id: describe_kind(self.world, definition) for government_id, definition in governments.items()}
        self.assertTrue(all(lines.values()))
        self.assertEqual(len(set(lines.values())), len(lines), "no two kinds read the same")
        self.assertIn("consejo de 3", lines["council"])
        self.assertIn("75%", lines["commune"])


if __name__ == "__main__":
    unittest.main()
