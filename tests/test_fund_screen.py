import os
import tempfile
import unittest
from pathlib import Path

import pygame

from graphics.coin_art import COIN_PAPER, coin_path
from save.save_manager import SaveManager
from scenes.hud import FUND_INTENT, JOBS_INTENT
from simulation.economy.terms import TradingState
from simulation.world import SimulationWorld
from ui.fund_board import (
    BARTER_INTENT,
    CANCEL_INTENT,
    DRAW_INTENT,
    NAME_IT_INTENT,
    PROPOSE_INTENT,
    RENAME_INTENT,
    SINGULAR_FIELD,
    advise_intent,
    answer_rows,
    asked_line,
    field_rects,
    status_lines,
)
from ui.labels import COIN_ICON, settlement_counts
from ui.trade_board import MAX_OWN, own_rows, sale_buttons, sale_intent

CARAVAN = "caravan"
ENCOURAGE = "encourage"


class _Shell(unittest.TestCase):
    """The real game shell without a window, on the settlement that comes ready made."""

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

    @staticmethod
    def _restore_driver(variable: str, previous: str | None) -> None:
        if previous is None:
            os.environ.pop(variable, None)
        else:
            os.environ[variable] = previous

    def _button(self, intent):
        return next(button for button in self.hud.buttons if button.intent == intent)

    def _press(self, intent) -> None:
        self.view.render()
        self.view.click(self._button(intent).rect.center)

    def _type(self, text: str) -> None:
        for letter in text:
            self.view.handle_event(pygame.event.Event(pygame.KEYDOWN, key=ord(letter), mod=0, unicode=letter))

    def _key(self, key: int) -> None:
        self.view.handle_event(pygame.event.Event(pygame.KEYDOWN, key=key, mod=0, unicode=""))

    def _barter(self) -> None:
        """Have the settlement be as it would had it never taken up a currency."""
        self.world.trading = TradingState()
        for resident in self.world.residents.values():
            resident.credits = 0.0


class FundScreenTests(_Shell):
    """The entry of the menu for what the settlement holds as a whole and how it trades."""

    def _entry(self) -> pygame.Rect:
        return next(button for button in self.hud.menu if button.intent == FUND_INTENT).rect

    def test_the_menu_opens_it_over_the_map_and_shuts_it_again(self) -> None:
        self.assertFalse(self.hud.fund_open)
        self.view.click(self._entry().center)
        self.assertTrue(self.hud.fund_open)
        self.view.render()
        board = self.hud.fund_rect()
        self.assertTrue(self.hud.layout.map.contains(board))
        self.assertTrue(self.hud.covers(board.center), "a click on it does not fall through to the map")
        self.view.click(next(button for button in self.hud.menu if button.intent == JOBS_INTENT).rect.center)
        self.assertFalse(self.hud.fund_open, "one panel at a time in that corner")
        self.view.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_f, mod=0, unicode="f"))
        self.assertTrue(self.hud.fund_open)

    def test_every_entry_of_the_menu_has_room_on_the_screen(self) -> None:
        self.assertLessEqual(max(button.rect.bottom for button in self.hud.menu), self.hud.layout.sidebar.bottom)

    def test_it_says_how_they_trade_and_what_is_in_the_fund(self) -> None:
        said = [text for text, _ in status_lines(self.world)]
        self.assertIn("Se comercia con vales", said)
        self.assertIn(f"En el fondo: {int(self.world.trading.fund)} vales", said)
        self.assertEqual(dict(settlement_counts(self.world))[COIN_ICON], str(int(self.world.trading.fund)))
        self._barter()
        said = [text for text, _ in status_lines(self.world)]
        self.assertTrue(said[0].startswith("Se comercia por trueque"))
        self.assertNotIn(COIN_ICON, dict(settlement_counts(self.world)), "under barter there is no coin to count")
        self.hud.toggle_fund()
        self.view.render()

    def test_a_currency_is_named_and_put_to_them_and_each_answer_is_shown(self) -> None:
        self._barter()
        self.hud.toggle_fund()
        self.assertEqual(asked_line(self.world), "Aún no se les ha preguntado con qué comerciar.")
        self._press(PROPOSE_INTENT)
        self.assertTrue(self.view.typing, "what is typed is the name, and no shortcut")
        self._type("chapas")
        self._key(pygame.K_TAB)
        self._type("chapa")
        self.assertEqual((self.hud.fund_entry.name, self.hud.fund_entry.singular), ("chapas", "chapa"))
        self.assertFalse(self.world.clock.paused)
        self._press(advise_intent(ENCOURAGE))
        self.assertIsNone(self.hud.fund_entry)
        rows = answer_rows(self.world)
        self.assertEqual(len(rows), len(self.world.residents), "everybody who is in answered")
        yes = sum(said for _, _, said in rows)
        self.assertIn(f"{yes} a favor, {len(rows) - yes} en contra", asked_line(self.world))
        self.assertIn("chapas", asked_line(self.world))
        self.assertEqual(self.world.fund.currency(self.world) is not None, yes > len(rows) - yes)
        self.assertIn("chapas", self.hud.notice)
        self.view.render()

    def test_a_currency_with_no_name_is_put_to_nobody(self) -> None:
        self._barter()
        self.hud.toggle_fund()
        self._press(PROPOSE_INTENT)
        heard: list[str] = []
        self.view.sound = heard.append
        self._press(advise_intent(ENCOURAGE))
        self.assertIn("refuse", heard)
        self.assertIsNotNone(self.hud.fund_entry, "the board waits for a name")
        self.assertEqual(self.world.trading.answers, {})
        self._press(CANCEL_INTENT)
        self.assertIsNone(self.hud.fund_entry)
        self.assertFalse(self.view.typing)

    def test_a_click_on_a_field_writes_there_and_escape_drops_it(self) -> None:
        self._barter()
        self.hud.toggle_fund()
        self._press(PROPOSE_INTENT)
        self.view.render()
        fields = field_rects(self.view.font, self.hud.fund_rect(), self.world, self.hud.fund_entry)
        self.view.click(fields[SINGULAR_FIELD].center)
        self._type("bono")
        self.assertEqual((self.hud.fund_entry.name, self.hud.fund_entry.singular), ("", "bono"))
        self._key(pygame.K_BACKSPACE)
        self.assertEqual(self.hud.fund_entry.singular, "bon")
        self._key(pygame.K_ESCAPE)
        self.assertIsNone(self.hud.fund_entry)

    def test_going_back_to_barter_is_put_to_them_with_an_advice(self) -> None:
        self.hud.toggle_fund()
        self._press(BARTER_INTENT)
        self.assertFalse(self.view.typing, "there is nothing to write")
        self._press(advise_intent(ENCOURAGE))
        self.assertEqual(self.world.trading.asked_about, "volver al trueque")
        self.assertEqual(len(answer_rows(self.world)), len(self.world.residents))
        # They were asked just now: it says so, and asking again is refused.
        self._press(BARTER_INTENT)
        self._press(advise_intent(ENCOURAGE))
        self.assertIn("hace poco", self.hud.notice)

    def test_the_currency_there_is_can_be_given_another_name(self) -> None:
        self.hud.toggle_fund()
        self._press(RENAME_INTENT)
        self.assertEqual(self.hud.fund_entry.name, "vales")
        for _ in "vales":
            self._key(pygame.K_BACKSPACE)
        self._type("tapones")
        self._press(NAME_IT_INTENT)
        coin = self.world.fund.currency(self.world)
        self.assertEqual((coin.name, coin.singular), ("tapones", "vale"))
        self.assertIn("Se comercia con tapones", [text for text, _ in status_lines(self.world)])

    def test_with_nowhere_to_keep_drawings_the_coin_is_the_games_own(self) -> None:
        self.hud.toggle_fund()
        self.view.render()
        self.assertNotIn(DRAW_INTENT, [button.intent for button in self.hud.buttons])
        self.assertIsNone(self.game.coin_editor)


class CoinDrawingTests(_Shell):
    """The settlement's coin, drawn by the player."""

    illustrated = True

    def test_the_coin_is_drawn_and_kept_by_its_currency_and_shown_from_then_on(self) -> None:
        coin = self.world.trading.currency
        before = self.hud.coins.shown(coin.currency_id, 22).copy()
        self.hud.toggle_fund()
        self._press(DRAW_INTENT)
        self.game.sync_scenes()
        self.assertEqual(self.game.scene_name, "coin_editor")
        editor = self.game.coin_editor
        self.assertEqual(editor.drawing.get_size(), COIN_PAPER)
        editor.render()
        editor.color = (200, 30, 30)
        editor.press((editor.area.centerx, editor.area.centery))
        editor.release()
        self.assertTrue(editor.save())
        self.assertTrue((self.folder / coin_path(coin.currency_id)).is_file())
        after = self.hud.coins.shown(coin.currency_id, 22)
        self.assertNotEqual(pygame.image.tobytes(after, "RGBA"), pygame.image.tobytes(before, "RGBA"))
        editor.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE, mod=0, unicode=""))
        self.game.sync_scenes()
        self.assertEqual(self.game.scene_name, "global")
        self.view.render()

    def test_there_is_no_coin_to_draw_without_a_currency(self) -> None:
        self.world.trading = TradingState()
        self.game.coin_editor.open("credits")
        self.assertTrue(self.game.coin_editor.closed)


class OwnSaleScreenTests(_Shell):
    """Putting it to a resident, from the deal with whoever is at the gate, that they sell a thing of their own."""

    def _arrive(self) -> None:
        world = self.world
        world.clock.day, world.clock.hour, world.clock.minute = 2, 9, 0
        world.merchants.arrive(world, world.registries.world_events.events[CARAVAN])
        self.view.centre_on((world.merchant.tile[0] + 0.5, world.merchant.tile[1] - 3))
        self.hud.open_trade()
        self.view.render()

    def test_what_is_somebodys_own_is_listed_with_what_it_fetches(self) -> None:
        self.assertEqual(own_rows(self.world), [], "with nobody at the gate there is nobody to sell to")
        self._arrive()
        rows = own_rows(self.world)
        self.assertTrue(rows)
        for row in rows:
            owner = self.world.residents[row.resident_id]
            self.assertGreater(row.fetches, 0)
            self.assertEqual(self.world.merchants._own(self.world, owner, row.instance_id)[1].owner_id, row.resident_id)
        self.assertEqual(rows, sorted(rows, key=lambda row: -row.fetches), "what fetches most comes first")
        self.assertEqual(len(sale_buttons(self.view.font, self.hud.trade_rect(), self.world)), min(len(rows), MAX_OWN))
        self.assertTrue(self.hud.layout.map.contains(self.hud.trade_rect()))

    def test_it_is_put_to_its_owner_who_answers_and_it_is_said(self) -> None:
        self._arrive()
        row = own_rows(self.world)[0]
        owner = self.world.residents[row.resident_id]
        credits, purse = owner.credits, self.world.merchant.purse
        self.view.click(self._button(sale_intent(row.resident_id, row.instance_id)).rect.center)
        self.assertTrue(self.hud.notice)
        sold = owner.credits > credits
        self.assertEqual(self.world.merchant.purse, purse - row.fetches if sold else purse)
        self.assertEqual(owner.credits, credits + row.fetches if sold else credits, "what it fetches is theirs")
        self.view.render()

    def test_what_was_bought_waits_at_the_gate_to_be_seen(self) -> None:
        self._arrive()
        self.world.at_gate["canned_beans"] = 3
        self.view.render()
        self.world.at_gate.clear()
        self.view.render()


class AnswersKeptTests(unittest.TestCase):
    """What each resident said about how to trade is the settlement's to remember (no pygame)."""

    def test_what_each_said_is_kept_and_saved_and_missing_from_an_older_save(self) -> None:
        world = SimulationWorld.demo_world(seed=7)
        world.trading = TradingState()
        result = world.terms.propose_currency(world, "chapas")
        answers = dict(world.trading.answers)
        self.assertEqual(set(answers), set(world.residents))
        self.assertEqual(result.ok, sum(answers.values()) > len(answers) / 2)
        manager = SaveManager()
        data = manager.to_data(world)
        loaded = manager.from_data(data, world.registries)
        self.assertEqual(loaded.trading.answers, answers)
        self.assertEqual(loaded.trading.asked_about, "comerciar con chapas")
        del data["trading"]["answers"], data["trading"]["asked_about"]
        older = manager.from_data(data, world.registries)
        self.assertEqual((older.trading.answers, older.trading.asked_about), ({}, ""))


if __name__ == "__main__":
    unittest.main()
