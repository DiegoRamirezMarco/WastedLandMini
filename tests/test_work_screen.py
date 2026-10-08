"""Work on screen (P59): a ring over whoever is at a post, each unit seen to come out, whoever
is pushed, and a board that says what somebody would make of a post and puts them to it."""

import os
import tempfile
import unittest
from pathlib import Path

import pygame

from graphics import ui_art
from graphics.palette import PALETTE
from simulation.economy.ledger import MADE, SPOILED
from simulation.residents.needs import Needs
from ui.affect_wheel import icon_of
from ui.job_board import (
    LEAVE_POST_INTENT,
    PUSH_POST_INTENT,
    PUSH_KIND,
    PUSHED,
    board_buttons,
    describe_expected,
    post_rows,
    put_intent,
    suggest_intent,
)
from ui.work_marks import POP_SECONDS, RING, SMALL_RING


class _Shell(unittest.TestCase):
    """The game as it is played, with no window: the settlement that comes ready made, on the
    map, with no grudges and nobody wanting for anything."""

    illustrated = False

    def setUp(self) -> None:
        for variable in ("SDL_VIDEODRIVER", "SDL_AUDIODRIVER"):
            self.addCleanup(self._restore_driver, variable, os.environ.get(variable))
            os.environ[variable] = "dummy"
        from game.game import Game

        self.folder = None
        if self.illustrated:
            keep = tempfile.TemporaryDirectory()
            self.addCleanup(keep.cleanup)
            self.folder = Path(keep.name) / "illustrations"
            self.folder.mkdir()
        self.game = Game(illustrations_dir=self.folder, voices_dir=None, start_in_menu=False)
        self.addCleanup(pygame.quit)
        self.view, self.hud, self.world = self.game.global_view, self.game.global_view.hud, self.game.world
        self.world.relationships.clear()
        self._content()

    @staticmethod
    def _restore_driver(variable: str, previous: str | None) -> None:
        if previous is None:
            os.environ.pop(variable, None)
        else:
            os.environ[variable] = previous

    def _content(self) -> None:
        for resident in self.world.residents.values():
            resident.needs = Needs(hunger=0, thirst=0, tiredness=0, social=0, stress=0)

    def _run(self, minutes: int, until=None) -> bool:
        for _ in range(minutes):
            self.world.step(1)
            self._content()
            if until is not None and until():
                return True
        return False

    def _to_post(self, resident_id: str) -> None:
        resident = self.world.residents[resident_id]
        self.assertTrue(self._run(180, lambda: self.world.work.on_duty(self.world, resident)), f"{resident_id} never got there")

    def _frame(self) -> None:
        self.view.update(0.0)
        self.view.render()

    def _board(self, selected: str | None) -> dict:
        if selected is not None:
            self.hud.select_resident(selected)
        if not self.hud.jobs_open:
            self.hud.toggle_jobs()
        self._frame()
        return {button.intent: button for button in board_buttons(self.view.font, self.hud.jobs_rect(), self.world, selected)}


class WorkOnTheMapTests(_Shell):
    def test_a_ring_over_whoever_is_at_a_post_fills_as_the_next_unit_comes(self) -> None:
        self._frame()
        self.assertEqual(self.view.work_rings, {}, "nobody is at a post yet")
        self._to_post("raul")
        self.view.centre_on_resident("raul")
        self._frame()
        ring = self.view.work_rings["raul"]
        self.assertEqual(ring.size, (RING, RING))
        self.assertTrue(self.view.viewport.contains(ring))
        self.assertGreater(self.view.hitboxes["raul"].top, ring.top, "it is over them")
        bar = self.view.task_bars["raul"]
        self.assertLess(ring.right, bar.left, "beside how much of the shift has gone, which is still there")
        self.assertEqual(ring.bottom, bar.bottom)
        # Whoever is at a post that makes nothing by the unit has the shift over them, as before.
        self.world.clock.hour = 9
        self._to_post("tomas")
        self.view.centre_on_resident("tomas")
        self._frame()
        self.assertIn("tomas", self.view.task_bars)
        self.assertNotIn("tomas", self.view.work_rings)

    def test_from_afar_and_under_a_roof_it_is_over_their_face(self) -> None:
        self._to_post("raul")
        self.view.set_zoom(0)
        self.assertTrue(self.view.overview)
        with self.assertNoLogs("graphics.assets", level="WARNING"):
            self._frame()
        self.assertEqual(self.view.work_rings["raul"].size, (SMALL_RING, SMALL_RING), "smaller, as the bar is")

    def test_a_unit_that_comes_out_is_seen_for_a_moment(self) -> None:
        raul = self.world.residents["raul"]
        self.world.ledger.record(self.world, "vegetables", 1, MADE, "farmer", "raul", raul.post_id)
        self._frame()
        self.assertEqual(self.view.pops.pops, [], "what was written before anybody looked is not news")
        self._to_post("raul")
        self.view.centre_on_resident("raul")
        self.view.update(0.0)
        self.view.pops.pops.clear()
        self.world.ledger.record(self.world, "vegetables", 2, MADE, "farmer", "raul", raul.post_id)
        self.world.ledger.record(self.world, "vegetables", -3, SPOILED, by="raul", at=raul.post_id)
        self.world.ledger.record(self.world, "vegetables", -1, "eaten", by="raul")
        self.view.update(0.0)
        self.assertEqual([(pop.definition_id, pop.units, pop.by) for pop in self.view.pops.pops], [("vegetables", 2, "raul"), ("vegetables", -3, "raul")])
        with self.assertNoLogs("graphics.assets", level="WARNING"):
            self.view.render()
        self.view.update(POP_SECONDS / 2)
        self.assertEqual(len(self.view.pops.pops), 2)
        self.view.update(POP_SECONDS)
        self.assertEqual(self.view.pops.pops, [])

    def test_whoever_is_pushed_is_seen_to_be(self) -> None:
        self._to_post("raul")
        self.view.centre_on_resident("raul")
        self.hud.select_resident("raul")
        self.view._affect(PUSH_KIND, None)
        self.assertTrue(self.world.rush.pushed(self.world, self.world.residents["raul"]))
        with self.assertNoLogs("graphics.assets", level="WARNING"):
            self._frame()
        self.assertIn("raul", self.view.work_rings)
        # Their ring is another colour, with an ember in the middle of it.
        plain = ui_art.ring(44, 0.5, PALETTE["lichen"])
        hot = ui_art.ring(44, 0.5, PALETTE["ember"], True)
        self.assertNotEqual(tuple(plain.get_at((22, 22))), tuple(hot.get_at((22, 22))))
        self.assertEqual(tuple(ui_art.ring(44, 0.0, PALETTE["lichen"]).get_at((22, 4)))[:3], tuple(ui_art.ring(44, 0.0, PALETTE["ember"]).get_at((22, 4)))[:3], "an empty ring has no colour in it yet")
        self.assertNotEqual(tuple(ui_art.ring(44, 1.0, PALETTE["lichen"]).get_at((22, 4))), tuple(ui_art.ring(44, 0.0, PALETTE["lichen"]).get_at((22, 4))))

    def test_an_accident_is_marked_over_whoever_had_it(self) -> None:
        from simulation.events.event import DomainEvent

        self.view.on_events([DomainEvent("work_accident", 45, "A Raúl se le parte una azada de tanto apretar", ["raul"])])
        self.assertEqual(self.view.mark_over("raul"), "alert")


class WorkBoardTests(_Shell):
    def test_the_board_says_what_whoever_is_selected_would_make_of_each_post(self) -> None:
        rows = {row.job_id: row for row in post_rows(self.world, None)}
        self.assertEqual({row.would_make for row in rows.values()}, {""}, "with nobody picked there is nobody to say it of")
        raul, jobs = self.world.residents["raul"], self.world.registries.jobs
        rows = {row.job_id: row for row in post_rows(self.world, "raul")}
        farmer = self.world.work.expected(self.world, raul, jobs["farmer"])
        self.assertEqual(rows["farmer"].would_make, describe_expected(farmer))
        self.assertRegex(rows["farmer"].would_make, r"^x\d,\d · \d+/día$")
        self.assertRegex(rows["guard"].would_make, r"^x\d,\d$", "keeping watch turns out nothing by the unit")
        self.assertEqual(rows["farmer"].standing, 1, "he has a hoe")
        self.assertTrue(rows["farmer"].own)
        raul.mood = 5.0
        raul.inventory.items.clear()
        self.assertEqual({row.job_id: row for row in post_rows(self.world, "raul")}["cook"].standing, -1)

    def test_putting_somebody_to_a_post_from_the_board_is_an_order(self) -> None:
        lucia = self.world.residents["lucia"]
        buttons = self._board("lucia")
        # Two posts stand free: the water nobody draws yet, and the second plot of the garden.
        self.assertEqual(
            [intent for intent in buttons if intent[0] in ("put", "suggest")],
            [suggest_intent("water_carrier"), put_intent("water_carrier"), suggest_intent("farmer"), put_intent("farmer")],
        )
        self.view.click(buttons[put_intent("farmer")].rect.center)
        self.assertEqual((lucia.job_id, lucia.post_id), ("farmer", "crop_2"))
        self.assertIn("A Lucía se le dice", self.hud.notice)
        self.assertEqual(self.world.decisions, {}, "nobody was asked anything")
        self.assertEqual(self.hud.selected_id, "lucia", "a click on the board does not fall through to the map")

    def test_their_own_post_is_pushed_and_left_from_the_board(self) -> None:
        raul = self.world.residents["raul"]
        buttons = self._board("raul")
        self.assertIn(PUSH_POST_INTENT, buttons)
        self.assertIn(LEAVE_POST_INTENT, buttons)
        self.assertNotIn(put_intent("farmer"), buttons, "it is his already")
        self.view.click(buttons[PUSH_POST_INTENT].rect.center)
        self.assertTrue(self.world.rush.pushed(self.world, raul))
        buttons = self._board("raul")
        self.assertNotIn(PUSH_POST_INTENT, buttons, "he is at it")
        self.assertTrue({row.job_id: row for row in post_rows(self.world, "raul")}["farmer"].pushed)
        self.assertEqual(PUSHED, "va apretando")
        # Told to leave it while he is at that, it waits its turn like anything else he is told (S50).
        self.view.click(buttons[LEAVE_POST_INTENT].rect.center)
        self.assertEqual(raul.job_id, "farmer")
        self.assertIn("para después", self.hud.notice)

    def test_somebody_is_taken_off_their_post_from_the_board(self) -> None:
        raul = self.world.residents["raul"]
        buttons = self._board("raul")
        self.view.click(buttons[LEAVE_POST_INTENT].rect.center)
        self.assertIsNone(raul.job_id)
        self.assertNotIn(LEAVE_POST_INTENT, self._board("raul"))

    def test_off_their_shift_there_is_nothing_to_push(self) -> None:
        self.world.clock.hour = 21
        buttons = self._board("raul")
        self.assertNotIn(PUSH_POST_INTENT, buttons)
        self.assertIn(LEAVE_POST_INTENT, buttons)

    def test_every_button_of_the_board_is_on_it_and_none_is_over_another(self) -> None:
        for selected in ("lucia", "raul", None):
            with self.subTest(selected=selected):
                buttons = list(self._board(selected).values())
                board = self.hud.jobs_rect()
                self.assertTrue(all(board.contains(button.rect) for button in buttons))
                for index, one in enumerate(buttons):
                    self.assertFalse(any(one.rect.colliderect(other.rect) for other in buttons[index + 1 :]))
                with self.assertNoLogs("graphics.assets", level="WARNING"):
                    self._frame()

    def test_the_wheel_has_pushing_under_work_with_a_picture_of_its_own(self) -> None:
        option = next(each for each in self.world.affect_options("raul") if each.kind == PUSH_KIND)
        self.assertEqual((option.name, icon_of(option)), ("Apretar", "push"))
        self.assertIn("push", ui_art.HUES)


class WindowWorkTests(WorkOnTheMapTests):
    """The same with a window under the canvas, where the ring is drawn at its resolution."""

    illustrated = True


if __name__ == "__main__":
    unittest.main()
