"""A thing handed over, and one found, on screen (P65), through the real game shell without
a window."""

import os
import tempfile
import unittest
from pathlib import Path

import pygame

from scenes.discovery_editor import FOUND_DECIDES, MADE_FOLDER, SETTLED_TITLE
from scenes.hud import DISCOVERY_FOUND, DISCOVERY_INTENT, GIVE_NOBODY, GIVE_OPEN_INTENT, GIVE_TO, give_intent
from scenes.item_editor import ART_AREA
from simulation.residents.needs import Needs
from simulation.tastes.taste import Taste
from ui.labels import settlement_stock
from ui.resident_panel import give_hitbox, words_hitbox


class GiveScreenTests(unittest.TestCase):
    def setUp(self) -> None:
        for variable in ("SDL_VIDEODRIVER", "SDL_AUDIODRIVER"):
            self.addCleanup(self._restore_driver, variable, os.environ.get(variable))
            os.environ[variable] = "dummy"
        from game.game import Game

        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.custom = Path(self._tmp.name)
        self.game = Game(illustrations_dir=None, voices_dir=None, start_in_menu=False, custom_content_dir=self.custom)
        self.addCleanup(pygame.quit)
        self.view, self.hud, self.world = self.game.global_view, self.game.global_view.hud, self.game.world
        self.editor = self.game.discovery_editor
        for resident in self.world.residents.values():
            resident.needs = Needs(hunger=0, thirst=0, tiredness=0, social=0, stress=0)

    @staticmethod
    def _restore_driver(variable: str, previous: str | None) -> None:
        if previous is None:
            os.environ.pop(variable, None)
        else:
            os.environ[variable] = previous

    def _button(self, intent):
        return next((button for button in self.hud.buttons if button.intent == intent), None)

    def _frame(self) -> None:
        self.game.sync_scenes()
        self.game.active_scene.update(0.1)
        self.game.active_scene.render()

    def _type(self, text: str) -> None:
        for char in text:
            self.game.handle_event(pygame.event.Event(pygame.KEYDOWN, key=ord(char), mod=0, unicode=char))

    def _held(self, item_id: str) -> int:
        return dict(settlement_stock(self.world)).get(item_id, 0)

    # ----- handed over -----

    def test_the_almacen_gives_to_whoever_is_selected_a_unit_at_a_time(self) -> None:
        world, hud = self.world, self.hud
        hud.select_resident(None)
        hud.toggle_stores()
        self.view.render()
        self.assertEqual(hud.give_buttons(), [], "with nobody selected there is nobody to give to")
        hud.select_resident("marta")
        self.view.render()
        listed = [item_id for item_id, _units in settlement_stock(world)]
        given = [button.intent[1] for button in hud.give_buttons()]
        self.assertEqual(given, listed[: len(given)])
        self.assertTrue(given)
        rect = hud.stores_rect()
        self.assertTrue(all(rect.contains(button.rect) for button in hud.give_buttons()))
        before = self._held("stew")
        marta = world.residents["marta"]
        button = self._button(give_intent("stew"))
        self.assertIsNotNone(button)
        self.view.click(button.rect.center)
        self.assertEqual(self._held("stew"), before - 1)
        self.assertEqual([item.owner_id for item in marta.inventory.items if item.definition_id == "stew"], ["marta"])
        self.assertEqual(hud.notice, "Marta tiene ahora un guiso caliente")
        self.assertTrue(hud.stores_open, "and another can be given at once")
        self.assertEqual(hud.selected_id, "marta", "a press on it is no click on the map")

    def test_it_says_who_it_gives_to_and_when_to_nobody(self) -> None:
        hud = self.hud
        hud.toggle_stores()
        for selected, hint in (("marta", GIVE_TO.format(name="Marta")), (None, GIVE_NOBODY)):
            hud.select_resident(selected)
            self.view.render()
            self.assertLessEqual(self.view.font.width(hint), hud.stores_rect().width - 12, "it fits on its line")
        hud.select_resident("marta")
        self.view.render()
        with_buttons = pygame.image.tobytes(self.game.canvas.subsurface(hud.stores_rect()), "RGB")
        hud.select_resident(None)
        self.view.render()
        self.assertNotEqual(pygame.image.tobytes(self.game.canvas.subsurface(hud.stores_rect()), "RGB"), with_buttons)

    def test_how_it_was_taken_is_seen_over_them(self) -> None:
        world, hud = self.world, self.hud
        marta, stew = world.residents["marta"], world.registries.items.resolve("stew")
        profile = world.tastes.profile(world, marta)
        profile.categories[stew.category] = Taste(leaning=0)
        profile.items[stew.item_id] = Taste(leaning=0)
        for tag in stew.preference_tags:
            profile.tags[tag] = Taste(leaning=-95)
        hud.select_resident("marta")
        hud.toggle_stores()
        self.view.render()
        self.view.click(self._button(give_intent("stew")).rect.center)
        self.view.on_events(world.events.drain())
        self.assertEqual(self.view.mark_over("marta"), "disgust")

    def test_what_is_all_gone_cannot_be_pressed_for(self) -> None:
        world, hud = self.world, self.hud
        hud.select_resident("marta")
        hud.toggle_stores()
        while self._held("stew"):
            self.view.render()
            self.view.click(self._button(give_intent("stew")).rect.center)
        self.view.render()
        self.assertIsNone(self._button(give_intent("stew")))
        self.view._apply(give_intent("stew"))
        self.assertIn("nada", hud.notice)
        mine = sum(item.quantity for item in world.residents["marta"].inventory.items if item.definition_id == "stew")
        self.assertGreater(mine, 0, "what she was given she still has")

    def test_a_residents_panel_leads_to_it(self) -> None:
        hud, panel = self.hud, self.hud.layout.panel
        hud.select_resident("marta")
        self.view.render()
        marta = self.world.residents["marta"]
        give, words = give_hitbox(panel, self.world, marta), words_hitbox(panel, self.world, marta)
        self.assertTrue(panel.contains(give))
        self.assertFalse(give.colliderect(words))
        self.assertEqual(hud.click(give.center), GIVE_OPEN_INTENT)
        self.view.click(give.center)
        self.assertTrue(hud.stores_open)
        self.assertEqual(hud.selected_id, "marta")
        self.view.click(give.center)
        self.assertTrue(hud.stores_open, "pressed again it stays open: it is shut from the menu")

    # ----- found -----

    def _found(self, source: str = "expedition", who: str | None = "sergio", kind: str = "found_food"):
        world = self.world
        found = world.finds.find(world, source, world.residents.get(who or ""), by_name="la caravana", kind_id=kind)
        self.view.on_events(world.events.drain())
        return found

    def test_something_nobody_knows_opens_the_screen_to_name_and_draw_it(self) -> None:
        found = self._found()
        self.assertEqual(self.view.requested_discovery, found.discovery_id)
        self._frame()
        self.assertEqual(self.game.scene_name, "discovery")
        editor = self.editor
        self.assertEqual(editor.kind.kind_id, "found_food")
        self.assertTrue(editor.drawn)
        self.assertEqual(editor.options(), {}, "there is nothing to pick")
        settled = editor.settled()
        preview = self.world.crafts.preview(self.world, found)
        self.assertIn(f"Hambre: {preview['effects']['hunger']:+g}", settled)
        self.assertIn(f"Vale {preview['base_value']}", settled)
        self.assertTrue(any("guste de" in line for line in settled))
        before = self.world.clock.total_minutes
        self.game.advance_simulation(5.0)
        self.assertEqual(self.world.clock.total_minutes, before, "time stands still")

    def test_named_and_drawn_it_is_a_thing_with_its_picture_and_waits_at_the_gate(self) -> None:
        found = self._found()
        units = found.units
        self._frame()
        editor = self.editor
        self._type("galletas")
        editor.color = (200, 40, 40)
        editor.press((ART_AREA.x + 40, ART_AREA.centery))
        editor.drag((ART_AREA.right - 40, ART_AREA.centery))
        self.game.handle_event(pygame.event.Event(pygame.MOUSEBUTTONUP, button=1, pos=(0, 0)))
        self._frame()
        save = next(button for button in editor.top_buttons if button.intent == ("save",))
        editor.press(save.rect.center)
        self.assertTrue(editor.closed)
        self.assertEqual(found.name, "galletas")
        self.assertTrue((self.custom / MADE_FOLDER / found.item_id / "icon.png").is_file())
        shown = self.game.icons.picture(found.item_id)
        self.assertEqual(tuple(shown.get_at((shown.get_width() // 2, shown.get_height() // 2)))[:3], (200, 40, 40))
        self.assertEqual(self.world.at_gate, {found.item_id: units})
        self._frame()
        self.assertEqual(self.game.scene_name, "global")
        self.assertIsNone(self.hud.discovery_button())

    def test_what_the_screen_says_of_a_find_is_its_own(self) -> None:
        self._found("caravan", None, "found_toy")
        self._frame()
        editor = self.editor
        canvas = self.game.canvas
        shown = pygame.image.tobytes(canvas, "RGB")
        self.assertTrue(editor.settled())
        self.assertIn("Social", " ".join(editor.settled()))
        # The lines of what the game settled are on it: without them it would look another way.
        editor.settled = lambda: []
        editor.render()
        self.assertNotEqual(pygame.image.tobytes(canvas, "RGB"), shown)
        self.assertTrue(SETTLED_TITLE and FOUND_DECIDES)

    def test_left_for_later_it_waits_under_a_notice_of_its_own(self) -> None:
        found = self._found()
        self._frame()
        self.game.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE, mod=0, unicode=""))
        self._frame()
        self.assertEqual(self.game.scene_name, "global")
        self.assertFalse(found.named)
        waiting = self.hud.discovery_button()
        self.assertIsNotNone(waiting)
        self.assertEqual(waiting.label, DISCOVERY_FOUND)
        self.assertEqual(waiting.intent, DISCOVERY_INTENT)
        self.view.click(waiting.rect.center)
        self._frame()
        self.assertEqual(self.game.scene_name, "discovery")
        self.assertEqual(self.editor.discovery_id, found.discovery_id)

    def test_what_a_job_teaches_is_named_as_it_ever_was(self) -> None:
        world = self.world
        raul = world.residents["raul"]
        job = world.registries.jobs[raul.job_id]
        marks = world.registries.crafts.levels
        level = world.crafts.level(world, raul, job.job_id)
        world.crafts.worked(world, raul, job, (marks[level] - raul.trade.get(job.job_id, 0.0)) * 2)
        self.view.on_events(world.events.drain())
        self._frame()
        self.assertEqual(self.game.scene_name, "discovery")
        self.assertEqual(self.editor.kind.kind_id, world.registries.crafts.jobs[job.job_id])
        self.assertTrue(self.editor.options(), "there is something to pick")
        self.game.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE, mod=0, unicode=""))
        self._frame()
        self.assertIn("Raúl", self.hud.discovery_button().label)


if __name__ == "__main__":
    unittest.main()
