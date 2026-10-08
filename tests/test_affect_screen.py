import os
import unittest

import pygame

from scenes.hud import scrap_intent
from simulation.commands import AffectCommand, SetFreeWillCommand
from simulation.residents.activity import HEED_ACTION
from simulation.residents.needs import Needs
from simulation.tastes.taste import Taste
from simulation.work.construction import AWAIT_ACTION
from simulation.work.salvage import SALVAGE_ACTION
from ui.affect_wheel import (
    AFFECT_INTENT,
    BACK_INTENT,
    CLOSE_INTENT,
    NEEDS,
    PASTIME,
    SOCIAL,
    TASKS,
    WILL_INTENT,
    WheelState,
    branch_intent,
    cancel_intent,
    order_intent,
    person_intent,
    target_intent,
    wheel_entries,
    wheel_place,
    wheel_view,
)
from ui.inventory_view import container_scrap_hitboxes
from ui.labels import describe_action
from ui.resident_panel import affect_hitbox

SCRAP_PILES = ("scrap_workshop", "scrap_yard")


class AffectScreenTests(unittest.TestCase):
    """The wheel about a resident, and breaking things up, through the real game without a window."""

    def setUp(self) -> None:
        for variable in ("SDL_VIDEODRIVER", "SDL_AUDIODRIVER"):
            self.addCleanup(self._restore_driver, variable, os.environ.get(variable))
            os.environ[variable] = "dummy"
        from game.game import Game

        self.game = Game(illustrations_dir=None, voices_dir=None, start_in_menu=False)
        self.addCleanup(pygame.quit)
        self.view = self.game.global_view
        self.hud = self.view.hud
        self.wheel = self.hud.wheel
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

    def _entries(self) -> dict:
        return {entry.intent: entry for entry in self.hud.wheel_entries()}

    def _frame(self) -> None:
        self.view.update(0.0)
        self.view.render()

    def _click(self, intent) -> None:
        self.view.click(self._entries()[intent].rect.center)
        self._frame()

    def _on_map(self, resident_id: str) -> tuple[int, int]:
        """Where a resident is on the screen, with the view on them."""
        self.view.centre_on_resident(resident_id)
        self.view.following = None
        self.view.render()
        return self.view.hitboxes[resident_id].center

    def _open(self, resident_id: str) -> None:
        """Select somebody on the map, and click them again."""
        self.hud.select_resident(None)
        for _ in range(2):
            self.view.click(self._on_map(resident_id))
            self._frame()

    def test_a_click_on_somebody_follows_them_and_a_second_opens_the_wheel_about_them(self) -> None:
        self.world.step(60)
        raul = self.world.residents["raul"]
        self.view.click(self._on_map("raul"))
        self._frame()
        self.assertEqual((self.hud.selected_id, self.view.following), ("raul", "raul"))
        self.assertFalse(self.wheel.open)
        self.assertNotEqual(raul.current_action, HEED_ACTION, "selecting him does not stop him")
        self.view.click(self.view.hitboxes["raul"].center)
        self._frame()
        self.assertTrue(self.wheel.open)
        self.assertEqual((self.wheel.about, raul.current_action), ("raul", HEED_ACTION))
        entries = self._entries()
        for branch in (SOCIAL, PASTIME, NEEDS, TASKS):
            self.assertIn(branch_intent(branch), entries)
        self.assertIn(WILL_INTENT, entries)
        self.assertIn(CLOSE_INTENT, entries)
        self.assertEqual(describe_action(self.world, raul), "se queda pensando...")
        # He goes on standing there for as long as the player is choosing.
        self.world.step(self.world.registries.affect.hold_minutes + 5)
        self.view.update(0.0)
        self.assertEqual(raul.current_action, HEED_ACTION)

    def test_the_wheel_is_a_ring_about_them_and_a_click_on_it_is_no_click_on_the_map(self) -> None:
        self.world.step(60)
        self._open("raul")
        about = self.view.hitboxes["raul"].center
        self.assertEqual(self.wheel.centre, about)
        entries = self.hud.wheel_entries()
        area = self.hud.wheel_area()
        x, y, radius = wheel_place(about, area, len(entries) - 1)
        for entry in entries:
            self.assertTrue(area.contains(entry.rect), entry.item.label)
            distance = ((entry.rect.centerx - x) ** 2 + (entry.rect.centery - y) ** 2) ** 0.5
            self.assertAlmostEqual(distance, radius, delta=1.5)
            self.assertTrue(self.hud.covers(entry.rect.center))
            self.assertFalse(self.view._on_map(entry.rect.center))
        self.assertEqual(entries[0].intent, CLOSE_INTENT, "the way out is at the foot of the ring")
        self.assertGreater(entries[0].rect.centery, max(entry.rect.centery for entry in entries[1:]))
        for one in entries:
            for other in entries:
                self.assertTrue(one is other or not one.rect.colliderect(other.rect), "no button is over another")
        # Near the edge of the map it is moved in, and kept whole.
        corner = wheel_entries(area.topleft, area, wheel_view(self.world, "raul", self.wheel))
        self.assertTrue(all(area.contains(entry.rect) for entry in corner))

    def test_what_is_chosen_is_done_and_the_wheel_shuts(self) -> None:
        self.world.step(60)
        self._open("ines")
        self._click(branch_intent(NEEDS))
        self.assertIn(order_intent("need:eat"), self._entries())
        self.assertIn(BACK_INTENT, self._entries())
        self._click(order_intent("need:eat"))
        self.assertFalse(self.wheel.open)
        self.assertIn("que coma algo", self.hud.notice)
        ines = self.world.residents["ines"]
        self.assertIsNotNone(ines.activity)
        self.assertEqual((ines.activity.action, ines.activity.ordered), ("eat", True))

    def test_what_is_done_with_somebody_asks_who_by_their_faces_and_then_what_by_what_is_felt(self) -> None:
        self.world.step(60)
        self.world.relationship("raul", "marta").resentment = 80
        self._open("raul")
        self._click(branch_intent(SOCIAL))
        faces = [entry for entry in self.hud.wheel_entries() if entry.intent != BACK_INTENT]
        there = self.world.affect_people("raul")
        self.assertEqual(len(faces), min(len(there), self.world.registries.affect.most_targets))
        self.assertTrue(all(entry.item.face in self.world.residents for entry in faces), "each is somebody's face")
        self.assertEqual(faces[0].item.face, self.world.affect_people("raul")[0][0], "the nearest first")
        self._click(person_intent("ines"))
        friendly = [entry.intent for entry in self.hud.wheel_entries() if entry.intent != BACK_INTENT]
        self.assertEqual(friendly, [target_intent("with:talk", "ines"), target_intent("leisure:cards", "ines")])
        self._click(BACK_INTENT)
        self.assertEqual((self.wheel.branch, self.wheel.person), (SOCIAL, None))
        self._click(person_intent("marta"))
        strike = target_intent("with:strike", "marta")
        self.assertIn(strike, self._entries(), "hating her as he does, he can be set on her")
        self.assertNotIn(target_intent("leisure:cards", "marta"), self._entries())
        self.assertEqual(self._entries()[strike].item.icon, "clash")
        self.assertIn("Marta", self._entries()[strike].item.hint)
        self._click(strike)
        self.assertFalse(self.wheel.open)
        raul = self.world.residents["raul"]
        self.assertEqual((raul.activity.partner_id, raul.activity.intent), ("marta", "fight"))

    def test_with_the_wheel_open_a_click_on_somebody_else_on_the_map_says_who(self) -> None:
        self.world.step(60)
        self._open("raul")
        self.view.click(self.view.hitboxes["ines"].center) if "ines" in self.view.hitboxes else self.skipTest("she is out of view")
        self._frame()
        self.assertEqual(self.hud.selected_id, "raul", "it is not her that is selected")
        self.assertTrue(self.wheel.open)
        self.assertEqual((self.wheel.branch, self.wheel.person), (SOCIAL, "ines"))
        self._click(target_intent("with:talk", "ines"))
        raul = self.world.residents["raul"]
        self.assertEqual((raul.activity.partner_id, raul.activity.intent), ("ines", "chat"))

    def test_a_pastime_with_somebody_goes_on_to_who_and_takes_a_click_on_the_map_too(self) -> None:
        self.world.step(60)
        self._open("raul")
        self._click(branch_intent(PASTIME))
        solo = [intent for intent in self._entries() if isinstance(intent, tuple) and intent[0] == "affect"]
        self.assertIn(order_intent("leisure:stroll"), solo)
        self._click(order_intent("leisure:cards"))
        self.assertTrue(self.wheel.open, "it is not said yet: there is who to choose")
        self.assertEqual(self.wheel.kind, "leisure:cards")
        self.assertTrue(all(entry.item.face for entry in self.hud.wheel_entries() if entry.intent != BACK_INTENT))
        if "ines" not in self.view.hitboxes:
            self.skipTest("she is out of view")
        self.view.click(self.view.hitboxes["ines"].center)
        self._frame()
        self.assertFalse(self.wheel.open)
        raul = self.world.residents["raul"]
        self.assertEqual((raul.activity.partner_id, raul.activity.intent), ("ines", "cards"))

    def test_what_they_are_known_to_like_is_marked(self) -> None:
        self.world.step(60)
        raul = self.world.residents["raul"]
        self.world.tastes.profile(self.world, raul).tags["music"] = Taste(leaning=90.0)
        self.world.apply_command(AffectCommand("raul", "leisure:hum"))
        self.world.step(3)
        self.world.apply_command(AffectCommand("raul", "task:stop"))
        self._open("raul")
        self._click(branch_intent(PASTIME))
        entries = self._entries()
        self.assertEqual(entries[order_intent("leisure:hum")].item.mark, "heart")
        self.assertIn("gusta", entries[order_intent("leisure:hum")].item.hint)
        self.assertIsNone(entries[order_intent("leisure:nap")].item.mark, "nothing is known of that yet")

    def test_a_click_on_nothing_or_on_them_again_or_the_other_button_takes_a_step_back_or_shuts_it(self) -> None:
        self.world.step(60)
        self._open("raul")
        raul = self.world.residents["raul"]
        self._click(branch_intent(NEEDS))
        self.view.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=3, pos=(0, 0)))
        self.assertTrue(self.wheel.open)
        self.assertIsNone(self.wheel.branch)
        self.view.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=3, pos=(0, 0)))
        self._frame()
        self.assertFalse(self.wheel.open)
        self.assertIsNone(raul.activity, "let go, he goes about his day")
        self._open("raul")
        self.assertTrue(self.wheel.open)
        self.view.click(self.view.hitboxes["raul"].center)
        self._frame()
        self.assertFalse(self.wheel.open, "a click on him again shuts it")
        self._open("raul")
        empty = next(
            (x, y)
            for x in range(self.view.viewport.left + 4, self.view.viewport.right, 9)
            for y in range(self.view.viewport.top + 4, self.view.viewport.bottom, 9)
            if self.view._on_map((x, y)) and not any(box.collidepoint(x, y) for box in self.view.hitboxes.values())
        )
        self.view.click(empty)
        self._frame()
        self.assertFalse(self.wheel.open)
        self.assertEqual(self.hud.selected_id, "raul", "and it was no click on the map behind")

    def test_let_go_or_left_for_somebody_else_they_go_about_their_day(self) -> None:
        self.world.step(60)
        self._open("raul")
        raul = self.world.residents["raul"]
        self._click(CLOSE_INTENT)
        self.assertFalse(self.wheel.open)
        self.assertIsNone(raul.activity)
        self._open("raul")
        self.assertEqual(raul.current_action, HEED_ACTION)
        self.hud.select_resident("ines")
        self.view.update(0.0)
        self.assertFalse(self.wheel.open)
        self.assertIsNone(raul.activity, "nobody is left standing there forgotten")
        self.assertEqual(self.hud.wheel_entries(), [])

    def test_the_way_in_the_panel_opens_the_same_wheel_and_shuts_it(self) -> None:
        self.hud.select_resident("raul")
        self.assertEqual(self.hud.click(affect_hitbox(self.hud.layout.panel).center), AFFECT_INTENT)
        self.hud.select_resident(None)
        self.assertNotEqual(self.hud.click(affect_hitbox(self.hud.layout.panel).center), AFFECT_INTENT)
        self.hud.select_resident("ines")
        self.view.render()
        self.view.click(affect_hitbox(self.hud.layout.panel).center)
        self._frame()
        self.assertTrue(self.wheel.open)
        self.view.click(affect_hitbox(self.hud.layout.panel).center)
        self._frame()
        self.assertFalse(self.wheel.open, "the same button lets them go")
        self.assertIsNone(self.world.residents["ines"].activity)

    def test_somebody_who_cannot_be_told_anything_is_said_why(self) -> None:
        from simulation.work.expedition import Expedition

        self.world.residents["sergio"].expedition = Expedition(returns_at=10**9, finds=0, danger=0.0)
        self.hud.select_resident("sergio")
        self.view.render()
        self.view.click(affect_hitbox(self.hud.layout.panel).center)
        self._frame()
        self.assertFalse(self.wheel.open)
        self.assertIn("fuera", self.hud.notice)

    def test_what_they_were_told_is_shown_by_their_panel_and_a_click_takes_it_back(self) -> None:
        self.world.step(60)
        self.hud.select_resident("raul")
        self.assertEqual(self.hud.queue_entries(), [])
        for kind, target in (("leisure:sit", None), ("with:talk", "marta"), ("need:eat", None)):
            self.assertTrue(self.world.apply_command(AffectCommand("raul", kind, target)).ok)
        self._frame()
        strip = self.hud.queue_entries()
        self.assertEqual([entry.intent for entry in strip], [cancel_intent(0), cancel_intent(1), cancel_intent(2)])
        self.assertEqual([entry.doing for entry in strip], [True, False, False])
        self.assertEqual([entry.icon for entry in strip], ["leisure", "talk", "food"])
        self.assertIn("Marta", strip[1].hint)
        area = self.hud.wheel_area()
        self.assertTrue(all(area.contains(entry.rect) and self.hud.covers(entry.rect.center) for entry in strip))
        self.view.click(strip[1].rect.center)
        self._frame()
        self.assertEqual([queued.order.kind for queued in self.world.orders_of("raul")], ["leisure:sit", "need:eat"])
        self.assertEqual(len(self.hud.queue_entries()), 2)
        self.assertEqual(describe_action(self.world, self.world.residents["raul"]), "mira pasar el día")

    def test_at_something_they_were_told_the_wheel_does_not_stop_them_and_what_is_said_waits(self) -> None:
        self.world.step(60)
        raul = self.world.residents["raul"]
        self.world.apply_command(AffectCommand("raul", "leisure:sit"))
        self.world.step(2)
        self._open("raul")
        self.assertTrue(self.wheel.open)
        self.assertEqual(raul.activity.action, "sit", "he goes on with what he was told")
        self._click(branch_intent(NEEDS))
        self._click(order_intent("need:eat"))
        self.assertEqual(raul.activity.action, "sit")
        self.assertEqual([queued.order.kind for queued in self.world.orders_of("raul")], ["leisure:sit", "need:eat"])
        self.assertIn("para después", self.hud.notice)

    def test_their_will_is_taken_and_given_back_from_the_wheel(self) -> None:
        self.world.step(60)
        raul = self.world.residents["raul"]
        self._open("raul")
        self.assertEqual(self._entries()[WILL_INTENT].item.icon, "unlock")
        self._click(WILL_INTENT)
        self.assertFalse(raul.free_will)
        self.assertTrue(self.wheel.open, "it is a switch: the wheel stays")
        self.assertEqual(self._entries()[WILL_INTENT].item.icon, "lock")
        self._click(CLOSE_INTENT)
        self.world.step(3)
        self._frame()
        self.assertEqual(describe_action(self.world, raul), "espera a que le digan qué hacer")
        strip = self.hud.queue_entries()
        self.assertEqual([entry.intent for entry in strip], [WILL_INTENT], "a lock by his panel says so")
        self.view.click(strip[0].rect.center)
        self._frame()
        self.assertTrue(raul.free_will)
        self.assertEqual(self.hud.queue_entries(), [])
        self.world.apply_command(SetFreeWillCommand("raul", False))
        self.assertEqual(wheel_view(self.world, "raul", WheelState(open=True, about="raul")).items[-1].icon, "lock")

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
        self.assertEqual((self.wheel.branch, self.wheel.kind), (TASKS, "task:salvage"))
        targets = [intent for intent in self._entries() if isinstance(intent, tuple) and intent[0] == "affect_target"]
        self.assertTrue(targets)
        self.assertEqual(self._entries()[targets[0]].item.icon, "scrap")
        self._click(targets[0])
        self.assertIn(targets[0][2], self.world.salvage)
        self.assertFalse(self.wheel.open)
        for _ in range(120):
            self.world.step(1)
            if paco.current_action == SALVAGE_ACTION:
                break
        self.assertEqual(paco.current_action, SALVAGE_ACTION)
        self.assertIn(site.site_id, self.world.sites)

    def test_whoever_passes_the_time_sitting_or_lying_is_seen_to(self) -> None:
        self.world.step(60)
        raul, marta = self.world.residents["raul"], self.world.residents["marta"]
        self.world.apply_command(AffectCommand("raul", "leisure:sit"))
        self.world.step(2)
        self.assertIsNotNone(self.view._seat_of(raul))
        self.assertFalse(self.view.sleeps_rough(raul))
        self.world.apply_command(AffectCommand("raul", "task:stop"))
        self.world.apply_command(AffectCommand("raul", "leisure:nap"))
        self.world.step(2)
        self.assertTrue(self.view.sleeps_rough(raul))
        self.assertIsNone(self.view._seat_of(raul))
        self.world.apply_command(AffectCommand("raul", "task:stop"))
        self.world.apply_command(AffectCommand("raul", "leisure:cards", "marta"))
        for _ in range(120):
            self.world.step(1)
            if raul.activity is not None and raul.activity.action == "cards":
                break
        self.assertEqual(raul.activity.action, "cards")
        self.assertIsNotNone(self.view._seat_of(raul), "two at cards sit down to it")
        self.assertIsNotNone(self.view._seat_of(marta))
        self.assertEqual(describe_action(self.world, raul), "echa unas cartas con Marta")
        self._frame()

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
