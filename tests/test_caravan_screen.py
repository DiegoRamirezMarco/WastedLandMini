import os
import tempfile
import unittest
from pathlib import Path

import pygame

from ui.trade_board import BUY, CART_INTENT, DEAL_INTENT, DRAW_INTENT, SELL, balance, goods_rows, step_intent, title

CARAVAN = "caravan"


class CaravanScreenTests(unittest.TestCase):
    """Whoever comes to trade, seen by the gate and dealt with, through the real game shell without a window."""

    illustrated = False

    def setUp(self) -> None:
        for variable in ("SDL_VIDEODRIVER", "SDL_AUDIODRIVER"):
            self.addCleanup(self._restore_driver, variable, os.environ.get(variable))
            os.environ[variable] = "dummy"
        from game.game import Game

        folder = None
        if self.illustrated:
            keep = tempfile.TemporaryDirectory()
            self.addCleanup(keep.cleanup)
            folder = Path(keep.name) / "illustrations"
            folder.mkdir()
        self.game = Game(illustrations_dir=folder, voices_dir=None, start_in_menu=False)
        self.addCleanup(pygame.quit)
        self.view, self.hud, self.world = self.game.global_view, self.game.global_view.hud, self.game.world

    @staticmethod
    def _restore_driver(variable: str, previous: str | None) -> None:
        if previous is None:
            os.environ.pop(variable, None)
        else:
            os.environ[variable] = previous

    def _arrive(self) -> None:
        world = self.world
        world.clock.day, world.clock.hour, world.clock.minute = 2, 9, 0
        world.merchants.arrive(world, world.registries.world_events.events[CARAVAN])
        self.view.centre_on((world.merchant.tile[0] + 0.5, world.merchant.tile[1] - 3))
        self.view.render()

    def _button(self, intent):
        return next(button for button in self.hud.buttons if button.intent == intent)

    def test_with_nobody_at_the_gate_there_is_nobody_to_see_or_to_deal_with(self) -> None:
        self.view.render()
        self.assertIsNone(self.view.visitor())
        self.hud.open_trade()
        self.assertFalse(self.hud.trade_open)
        self.assertEqual(len(self.view._standing()), len(self.world.interactables))

    def test_whoever_comes_is_seen_by_the_gate_with_their_cart(self) -> None:
        self._arrive()
        visitor = self.view.visitor()
        definition = self.world.registries.world_events.events[CARAVAN]
        self.assertEqual((visitor.resident_id, visitor.name), (definition.keeper_id, definition.keeper_name))
        self.assertEqual(visitor.tile, self.world.merchant.tile)
        box = self.view.hitboxes[visitor.resident_id]
        self.assertTrue(self.view.viewport.contains(box))
        cart = self.view._standing()[-1]
        self.assertEqual((cart.kind, (cart.x, cart.y)), (definition.cart, self.world.merchant.cart))
        self.assertNotIn(cart.object_id, self.world.interactables, "it is no part of the settlement")
        # From afar they are a face like anybody, and still to be clicked on.
        self.view.set_zoom(0)
        self.view.render()
        self.assertIn(visitor.resident_id, self.view.hitboxes)

    def test_a_click_on_them_opens_the_deal_and_selects_nobody(self) -> None:
        self._arrive()
        visitor = self.view.visitor()
        self.view.click(self.view.hitboxes[visitor.resident_id].center)
        self.assertTrue(self.hud.trading)
        self.assertIsNone(self.hud.selected_id)
        self.view.render()
        board = self.hud.trade_rect()
        self.assertTrue(self.hud.covers(board.center))
        self.assertIn(visitor.name, title(self.world))
        self.assertIn("21:00", title(self.world))
        # One panel at a time in that corner.
        self.hud.toggle_jobs()
        self.assertFalse(self.hud.trade_open)

    def test_what_is_chosen_stays_within_what_there_is(self) -> None:
        self._arrive()
        self.hud.open_trade()
        brought, held = goods_rows(self.world, {}, {})
        thing, own = brought[0], held[0]
        self.assertEqual(balance(self.world, brought, held)[1], "dust", "nothing is chosen yet")
        self.view.click(self._button(step_intent(BUY, thing.item_id, -1)).rect.center)
        self.assertEqual(self.hud.trade_deal(), ({}, {}), "no fewer than none")
        for _ in range(thing.units + 3):
            self.view.click(self._button(step_intent(BUY, thing.item_id, 1)).rect.center)
        self.view.click(self._button(step_intent(SELL, own.item_id, 1)).rect.center)
        self.assertEqual(self.hud.trade_deal(), ({own.item_id: 1}, {thing.item_id: thing.units}), "no more than they bring")
        self.view.render()
        # Shutting the panel forgets it.
        self.hud.toggle_jobs()
        self.hud.toggle_jobs()
        self.hud.open_trade()
        self.assertEqual(self.hud.trade_deal(), ({}, {}))

    def test_closing_the_deal_is_done_out_of_the_fund_and_said(self) -> None:
        self._arrive()
        self.hud.open_trade()
        world = self.world
        thing = min(goods_rows(world, {}, {})[0], key=lambda row: row.price)
        fund, purse = world.trading.fund, world.merchant.purse
        self.view.click(self._button(step_intent(BUY, thing.item_id, 1)).rect.center)
        self.view.render()
        self.view.click(self._button(DEAL_INTENT).rect.center)
        self.assertEqual(world.trading.fund, fund - thing.price)
        self.assertEqual(world.merchant.purse, purse + thing.price)
        self.assertEqual(world.merchant.goods.get(thing.item_id, 0), thing.units - 1)
        self.assertIn("Trato con", self.hud.notice)
        self.assertEqual(self.hud.trade_deal(), ({}, {}), "what was chosen is done with")
        self.assertTrue(self.hud.trading, "and they are still there to deal with")

    def test_a_deal_that_cannot_be_done_says_why_and_keeps_what_was_chosen(self) -> None:
        self._arrive()
        self.hud.open_trade()
        world = self.world
        world.trading.fund = 0.0
        thing = goods_rows(world, {}, {})[0][0]
        self.view.click(self._button(step_intent(BUY, thing.item_id, 1)).rect.center)
        brought, held = goods_rows(world, self.hud.trade_buy, self.hud.trade_sell)
        self.assertEqual(balance(world, brought, held)[1], "ember")
        heard: list[str] = []
        self.view.sound = heard.append
        self.view.click(self._button(DEAL_INTENT).rect.center)
        self.assertIn("refuse", heard)
        self.assertIn("fondo", self.hud.notice)
        self.assertEqual(self.hud.trade_deal(), ({}, {thing.item_id: 1}))

    def test_when_they_go_the_panel_goes_with_them(self) -> None:
        self._arrive()
        self.hud.open_trade()
        self.world.merchant = None
        self.assertFalse(self.hud.trading)
        self.view.render()
        self.assertFalse(self.hud.trade_open)
        self.assertIsNone(self.view.visitor())

    def test_with_nowhere_to_keep_drawings_there_is_no_drawing_them(self) -> None:
        self._arrive()
        self.hud.open_trade()
        intents = [button.intent for button in self.hud.buttons]
        self.assertNotIn(DRAW_INTENT, intents)
        self.assertNotIn(CART_INTENT, intents)


class DrawnCaravanTests(CaravanScreenTests):
    """The same, with a folder for drawings: whoever comes can be drawn, and so can their cart."""

    illustrated = True

    def test_with_nowhere_to_keep_drawings_there_is_no_drawing_them(self) -> None:
        self._arrive()
        self.hud.open_trade()
        definition = self.world.registries.world_events.events[CARAVAN]
        self.view.click(self._button(DRAW_INTENT).rect.center)
        self.assertEqual(self.view.requested_editor, definition.keeper_id)
        self.game.doll_editor.open(definition.keeper_id)
        self.assertEqual(self.game.doll_editor.resident_id, definition.keeper_id, "they are drawn as a resident is")
        self.assertFalse(self.game.doll_editor.closed)
        self.game.doll_editor.render()
        self.view.requested_editor = None
        self.view.click(self._button(CART_INTENT).rect.center)
        self.assertEqual(self.view.requested_object_editor, definition.cart)
        self.game.object_editor.open(definition.cart)
        self.assertFalse(self.game.object_editor.closed)
        self.game.object_editor.render()


if __name__ == "__main__":
    unittest.main()
