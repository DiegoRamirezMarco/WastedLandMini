import os
import unittest

import pygame

from scenes.hud import scrap_intent
from simulation.ai.affect import INCITE, NEED, TASK
from simulation.residents.activity import HEED_ACTION
from simulation.residents.needs import Needs
from simulation.work.construction import AWAIT_ACTION
from simulation.work.salvage import SALVAGE_ACTION
from ui.affect_board import AFFECT_INTENT, BACK_INTENT, CLOSE_INTENT, affect_rows, group_intent, order_intent, target_intent
from ui.inventory_view import container_scrap_hitboxes
from ui.resident_panel import affect_hitbox

SCRAP_PILES = ("scrap_workshop", "scrap_yard")


class AffectScreenTests(unittest.TestCase):
    """The way to affect a resident, and to break things up, through the real game without a window."""

    def setUp(self) -> None:
        for variable in ("SDL_VIDEODRIVER", "SDL_AUDIODRIVER"):
            self.addCleanup(self._restore_driver, variable, os.environ.get(variable))
            os.environ[variable] = "dummy"
        from game.game import Game

        self.game = Game(illustrations_dir=None, voices_dir=None, start_in_menu=False)
        self.addCleanup(pygame.quit)
        self.view = self.game.global_view
        self.hud = self.view.hud
        self.world = self.game.world
        self.world.relationships.clear()
        for resident in self.world.residents.values():
            resident.needs = Needs(hunger=0, tiredness=0, social=0, stress=0)

    @staticmethod
    def _restore_driver(variable: str, previous: str | None) -> None:
        if previous is None:
            os.environ.pop(variable, None)
        else:
            os.environ[variable] = previous

    def _rows(self) -> dict:
        rows = affect_rows(self.hud.affect_rect(), self.world, self.hud.selected_id, self.hud.affect_group, self.hud.affect_kind)
        return {row.intent: row for row in rows}

    def _click(self, intent) -> None:
        row = self._rows()[intent]
        self.view.click(row.rect.center)
        self.view.update(0.0)
        self.view.render()

    def _open(self, resident_id: str) -> None:
        self.hud.select_resident(resident_id)
        self.view.render()
        self.view.click(affect_hitbox(self.hud.layout.panel).center)
        self.view.update(0.0)
        self.view.render()

    def test_the_panel_of_whoever_is_selected_has_a_way_to_affect_them(self) -> None:
        self.hud.select_resident("raul")
        self.assertEqual(self.hud.click(affect_hitbox(self.hud.layout.panel).center), AFFECT_INTENT)
        self.hud.select_resident(None)
        self.assertNotEqual(self.hud.click(affect_hitbox(self.hud.layout.panel).center), AFFECT_INTENT)

    def test_affecting_somebody_stops_them_and_shows_what_can_be_said(self) -> None:
        self.world.step(60)
        self._open("raul")
        raul = self.world.residents["raul"]
        self.assertTrue(self.hud.affect_open)
        self.assertEqual(raul.current_action, HEED_ACTION)
        self.assertIn(group_intent(NEED), self._rows())
        self.assertIn(CLOSE_INTENT, self._rows())
        self.assertNotIn(group_intent(INCITE), self._rows(), "he feels nothing strongly for anybody")
        self.assertTrue(self.hud.covers(self.hud.affect_rect().center), "a click on it does not fall through to the map")
        # He goes on standing there for as long as the player is choosing.
        self.world.step(self.world.registries.affect.hold_minutes + 5)
        self.view.update(0.0)
        self.assertEqual(raul.current_action, HEED_ACTION)

    def test_what_is_chosen_is_done_and_the_panel_shuts(self) -> None:
        self.world.step(60)
        self._open("ines")
        self._click(group_intent(NEED))
        self.assertIn(order_intent("need:eat"), self._rows())
        self.assertIn(BACK_INTENT, self._rows())
        self._click(order_intent("need:eat"))
        self.assertFalse(self.hud.affect_open)
        self.assertIn("que coma algo", self.hud.notice)
        ines = self.world.residents["ines"]
        self.assertIsNotNone(ines.activity)
        self.assertEqual(ines.activity.action, "eat")

    def test_what_is_about_somebody_goes_on_to_ask_who(self) -> None:
        self.world.step(60)
        self.world.relationship("raul", "marta").resentment = 80
        self._open("raul")
        self._click(group_intent(INCITE))
        self._click(order_intent("incite:strike"))
        self.assertTrue(self.hud.affect_open, "it is not said yet: there is who to choose")
        self.assertEqual(self.hud.affect_kind, "incite:strike")
        self.assertEqual(list(self._rows()), [target_intent("incite:strike", "marta"), BACK_INTENT])
        self.assertIn("Marta", self._rows()[target_intent("incite:strike", "marta")].text)
        self._click(BACK_INTENT)
        self.assertEqual((self.hud.affect_group, self.hud.affect_kind), (INCITE, None))
        self._click(order_intent("incite:strike"))
        self._click(target_intent("incite:strike", "marta"))
        self.assertFalse(self.hud.affect_open)
        raul = self.world.residents["raul"]
        self.assertEqual((raul.activity.partner_id, raul.activity.intent), ("marta", "fight"))

    def test_let_go_or_left_for_somebody_else_they_go_about_their_day(self) -> None:
        self.world.step(60)
        self._open("raul")
        raul = self.world.residents["raul"]
        self._click(CLOSE_INTENT)
        self.assertFalse(self.hud.affect_open)
        self.assertIsNone(raul.activity)
        self._open("raul")
        self.assertEqual(raul.current_action, HEED_ACTION)
        self.hud.select_resident("ines")
        self.view.update(0.0)
        self.assertFalse(self.hud.affect_open)
        self.assertIsNone(raul.activity, "nobody is left standing there forgotten")
        self._open("ines")
        self.view.click(affect_hitbox(self.hud.layout.panel).center)
        self.view.update(0.0)
        self.assertFalse(self.hud.affect_open, "the same button lets them go")
        self.assertIsNone(self.world.residents["ines"].activity)

    def test_somebody_who_cannot_be_told_anything_is_said_why(self) -> None:
        from simulation.work.expedition import Expedition

        self.world.residents["sergio"].expedition = Expedition(returns_at=10**9, finds=0, danger=0.0)
        self._open("sergio")
        self.assertFalse(self.hud.affect_open)
        self.assertIn("fuera", self.hud.notice)

    def test_a_builder_waiting_for_material_is_pointed_out_and_asked_what_to_take_apart(self) -> None:
        for pile in SCRAP_PILES:
            self.world.containers[pile].items.clear()
        site = self.world.construction.lay(self.world, "object", "bed", (1, 1), "paco")
        paco = self.world.residents["paco"]
        for _ in range(90):
            self.world.step(1)
            if paco.current_action == AWAIT_ACTION:
                break
        self.assertEqual(paco.current_action, AWAIT_ACTION)
        self.view.render()
        self._open("paco")
        self.assertEqual((self.hud.affect_group, self.hud.affect_kind), (TASK, "task:salvage"))
        targets = [intent for intent in self._rows() if isinstance(intent, tuple) and intent[0] == "affect_target"]
        self.assertTrue(targets)
        self._click(targets[0])
        self.assertIn(targets[0][2], self.world.salvage)
        self.assertFalse(self.hud.affect_open)
        for _ in range(120):
            self.world.step(1)
            if paco.current_action == SALVAGE_ACTION:
                break
        self.assertEqual(paco.current_action, SALVAGE_ACTION)
        self.assertIn(site.site_id, self.world.sites)

    def test_what_is_kept_in_a_container_can_be_broken_up_from_its_panel(self) -> None:
        crate = self.world.containers["crate_1"]
        self.world.stock(crate, "baton", 1, None)
        self.hud.select_container("crate_1")
        self.view.render()
        panel = self.hud.layout.panel
        marks = container_scrap_hitboxes(panel.topleft, self.world, "crate_1", panel.width)
        scrappable = {item.instance_id for item in crate.items if self.world.salvaging.scrap_units(self.world, item) > 0}
        self.assertEqual({instance_id for _rect, instance_id in marks}, scrappable)
        self.assertLess(len(marks), len(crate.items), "what gives no scrap has no mark")
        rect, instance_id = next(mark for mark in marks if crate.find(mark[1]).owner_id is None)
        self.assertEqual(self.hud.click(rect.center), scrap_intent(instance_id))
        before = sum(self.world.containers[pile].count("scrap") for pile in SCRAP_PILES)
        self.view.click(rect.center)
        self.assertIsNone(crate.find(instance_id))
        self.assertEqual(sum(self.world.containers[pile].count("scrap") for pile in SCRAP_PILES), before + 1)
        self.assertIn("desguaza", self.hud.notice)
        self.view.render()

    def test_nothing_on_a_counter_is_broken_up(self) -> None:
        counter = next(
            object_id
            for object_id, placed in self.world.interactables.items()
            if (use := self.world.definition_of(placed).use) is not None and use.sells
        )
        panel = self.hud.layout.panel
        self.assertEqual(container_scrap_hitboxes(panel.topleft, self.world, counter, panel.width), [])


if __name__ == "__main__":
    unittest.main()
