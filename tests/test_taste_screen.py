"""What the player is shown of what residents like: in their panel, over their heads, in the log and in the item editor."""

import json
import os
import tempfile
import unittest
from pathlib import Path

import pygame

from graphics.palette import PALETTE
from scenes.global_view import FOUND_OUT_MARK, MARK_SECONDS
from scenes.hud import PANEL_TAB_INTENT, TASTE_DEBUG_INTENT
from simulation.items.item import ItemDefinition
from simulation.tastes.settings import EATEN, GIVEN, LOVED
from simulation.tastes.taste import CATEGORY, ITEM, TAG, Taste
from simulation.tastes.taste_system import FOUND_OUT_EVENT, REACTION_EVENT
from ui.labels import MORE_TO_FIND_OUT, NOTHING_FOUND_OUT, TASTE_WORDS, UNKNOWN_TASTE, taste_debug_rows, taste_rows
from ui.resident_panel import LIFE_TAB, TASTES_TAB, debug_hitbox, inventory_hitboxes, relationship_hitboxes, tab_hitbox


class TasteScreenTests(unittest.TestCase):
    """Runs the real game without a window, with folders of its own for drawings and content."""

    def setUp(self) -> None:
        for variable in ("SDL_VIDEODRIVER", "SDL_AUDIODRIVER"):
            self.addCleanup(self._restore_driver, variable, os.environ.get(variable))
            os.environ[variable] = "dummy"
        from game.game import Game

        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        (self.root / "illustrations").mkdir()
        (self.root / "custom").mkdir()
        self.game = Game(
            illustrations_dir=self.root / "illustrations",
            voices_dir=None,
            custom_content_dir=self.root / "custom",
            save_path=self.root / "save.json",
            start_in_menu=False,
        )
        self.addCleanup(pygame.quit)
        self.view, self.world, self.hud = self.game.global_view, self.game.world, self.game.global_view.hud
        self.world.clock.paused = True
        self.tastes = self.world.tastes
        self.raul, self.lucia = self.world.residents["raul"], self.world.residents["lucia"]
        self.cake = ItemDefinition("cake", "tarta", "una", "food", preference_tags=("sweet",))
        self.world.registries.items.register(self.cake)
        for resident in (self.raul, self.lucia):
            # Nothing but the sweetness of it to go by.
            profile = self.tastes.profile(self.world, resident)
            profile.categories["food"] = profile.items["cake"] = Taste()
        self.tastes.profile(self.world, self.raul).tags["sweet"] = Taste(leaning=-80)

    @staticmethod
    def _restore_driver(variable: str, previous: str | None) -> None:
        if previous is None:
            os.environ.pop(variable, None)
        else:
            os.environ[variable] = previous

    def _eat(self, resident, times: int = 1) -> None:
        for _ in range(times):
            self.tastes.react(self.world, resident, self.cake, EATEN)
        self.view.on_events(self.world.events.drain())

    # ----- the panel -----

    def test_what_is_not_found_out_is_three_question_marks(self) -> None:
        tomas = self.world.residents["tomas"]
        self.assertEqual(taste_rows(self.world, tomas), [(UNKNOWN_TASTE, NOTHING_FOUND_OUT, None)])
        # Raúl loathes sweet things, and nothing has shown it.
        self.assertEqual(taste_rows(self.world, self.raul), [(UNKNOWN_TASTE, NOTHING_FOUND_OUT, None)])
        # A trait is there to be seen, and with it the taste it gives.
        self.assertEqual(
            taste_rows(self.world, self.lucia),
            [("Lo dulce", "Le encanta", LOVED), (UNKNOWN_TASTE, MORE_TO_FIND_OUT, None)],
        )

    def test_a_taste_is_first_said_to_seem_so_and_then_said_outright(self) -> None:
        self._eat(self.raul)
        rows = taste_rows(self.world, self.raul)
        self.assertEqual({(label, words) for label, words, _ in rows[:2]}, {("La tarta", "Parece no gustarle"), ("Lo dulce", "Parece no gustarle")})
        self.assertEqual(rows[-1][:2], (UNKNOWN_TASTE, MORE_TO_FIND_OUT))
        self._eat(self.raul, 2)
        rows = taste_rows(self.world, self.raul)
        self.assertEqual({(label, words) for label, words, _ in rows[:2]}, {("La tarta", "Lo detesta"), ("Lo dulce", "Lo detesta")})

    def test_what_is_surest_comes_first_and_nowhere_is_there_a_figure(self) -> None:
        self._eat(self.raul, 3)
        profile = self.tastes.profile(self.world, self.raul)
        profile.tags["hot"] = profile.tags["homemade"] = Taste(leaning=45)
        profile.items["stew"] = Taste()
        for _ in range(2):
            self.tastes.react(self.world, self.raul, self.world.registries.items.get("stew"), EATEN)
        rows = taste_rows(self.world, self.raul)
        words = [said for _, said, _ in rows]
        outright, seeming = set(TASTE_WORDS["known"].values()), set(TASTE_WORDS["suspected"].values())
        known_until = max(index for index, said in enumerate(words) if said in outright)
        seems_from = min(index for index, said in enumerate(words) if said in seeming)
        self.assertLess(known_until, seems_from)
        for row in rows:
            self.assertFalse(any(character.isdigit() for part in row if part for character in part), row)
        for words_of in TASTE_WORDS.values():
            for said in words_of.values():
                self.assertFalse(any(character.isdigit() for character in said))

    def test_the_panel_is_switched_to_what_they_like_and_back_with_a_click(self) -> None:
        self.hud.select_resident("lucia")
        self.assertEqual(self.hud.panel_tab, LIFE_TAB)
        self.view.render()
        living = pygame.image.tobytes(self.game.canvas.subsurface(self.hud.layout.panel), "RGB")
        tab = tab_hitbox(self.hud.layout.panel)
        self.assertTrue(self.hud.layout.panel.contains(tab))
        self.assertEqual(self.hud.click(tab.center), PANEL_TAB_INTENT)

        self.view.click(tab.center)

        self.assertEqual(self.hud.panel_tab, TASTES_TAB)
        self.assertEqual(self.hud.selected_id, "lucia")
        self.view.render()
        liking = pygame.image.tobytes(self.game.canvas.subsurface(self.hud.layout.panel), "RGB")
        self.assertNotEqual(liking, living)
        # It stays on what they like from one resident to the next, and goes back with another click.
        self.hud.select_resident("raul")
        self.assertEqual(self.hud.panel_tab, TASTES_TAB)
        self.view.render()
        self.view.click(tab.center)
        self.assertEqual(self.hud.panel_tab, LIFE_TAB)
        self.hud.select_resident(None)
        self.assertNotEqual(self.hud.click(tab.center), PANEL_TAB_INTENT, "with nobody picked there is nothing to switch")

    def test_while_it_is_on_what_they_like_nothing_under_it_is_picked_by_mistake(self) -> None:
        self.world.relationship("lucia", "raul").affection = 40
        self.world.stock(self.lucia.inventory, "canned_beans", 1, "lucia")
        self.hud.select_resident("lucia")
        panel = self.hud.layout.panel
        people = relationship_hitboxes(panel, self.world, self.lucia)
        things = inventory_hitboxes(panel, self.world, self.lucia)
        self.assertTrue(people and things)
        self.assertEqual(self.hud.click(people[0][0].center), ("select", "raul"))
        self.hud.toggle_panel_tab()
        self.assertIsNone(self.hud.click(people[0][0].center))
        self.assertIsNone(self.hud.click(things[0][0].center))

    def test_a_long_list_of_tastes_stays_inside_the_panel(self) -> None:
        profile = self.tastes.profile(self.world, self.raul)
        for number in range(60):
            profile.tags[f"taste_{number}"] = Taste(leaning=90)
            self.world.taste_knowledge.observe("@player", "raul", f"tag:taste_{number}", 5.0, self.world.registries.tastes)
        self.assertGreater(len(taste_rows(self.world, self.raul)), 60)
        self.hud.select_resident("raul")
        self.hud.toggle_panel_tab()
        self.view.render()
        panel = self.hud.layout.panel
        below = pygame.Rect(panel.x, panel.bottom - 3, panel.width, 2)
        colours = {tuple(self.game.canvas.get_at((x, y)))[:3] for x in range(below.left + 3, below.right - 3) for y in range(below.top, below.bottom)}
        self.assertNotIn(PALETTE["bone"], colours)
        self.assertNotIn(PALETTE["lichen"], colours)

    # ----- looking under the bonnet -----

    def test_a_switch_on_the_tastes_shows_the_figures_the_game_keeps_to_itself(self) -> None:
        self.hud.select_resident("raul")
        switch = debug_hitbox(self.hud.layout.panel)
        # On how they live that corner is the way to their manners: the switch is not there yet.
        self.assertNotEqual(self.hud.click(switch.center), TASTE_DEBUG_INTENT, "it is not there until the panel is on what they like")
        self.hud.toggle_panel_tab()
        self.assertFalse(self.hud.taste_debug)
        self.view.render()
        plain = pygame.image.tobytes(self.game.canvas.subsurface(self.hud.layout.panel), "RGB")
        self.assertEqual(self.hud.click(switch.center), TASTE_DEBUG_INTENT)

        self.view.click(switch.center)

        self.assertTrue(self.hud.taste_debug)
        self.assertEqual(self.hud.panel_tab, TASTES_TAB)
        self.view.render()
        self.assertNotEqual(pygame.image.tobytes(self.game.canvas.subsurface(self.hud.layout.panel), "RGB"), plain)
        self.view.click(switch.center)
        self.assertFalse(self.hud.taste_debug)
        # What the player is told in play has no more in it for the switch having been used.
        self.assertEqual(taste_rows(self.world, self.raul), [(UNKNOWN_TASTE, NOTHING_FOUND_OUT, None)])

    def test_the_figures_are_every_taste_they_have_whether_it_has_shown_or_not(self) -> None:
        self.tastes.learn(self.world, self.raul, TAG, "sweet", 1.0, 0.25)
        rows = {label: rest for label, *rest in taste_debug_rows(self.world, self.raul)}
        self.assertEqual(rows["Lo dulce"], [-80, 15, -65, "hated", "-"])
        self.assertEqual(rows["La comida"], [0, 0, 0, "neutral", "-"])
        self._eat(self.raul, 3)
        rows = {label: rest for label, *rest in taste_debug_rows(self.world, self.raul)}
        self.assertEqual(rows["Lo dulce"][3:], ["hated", "!"])
        self.assertEqual(rows["La tarta"][4], "!")
        # A thing they have been seen to take and have no feeling for of its own: how they like it as a whole.
        self.tastes.profile(self.world, self.raul).items.pop("cake")
        rows = {label: rest for label, *rest in taste_debug_rows(self.world, self.raul)}
        self.assertEqual(rows["La tarta"][:2], [None, None])
        self.assertLess(rows["La tarta"][2], -60)
        self.assertEqual(taste_debug_rows(self.world, self.world.residents["tomas"]), [])
        self.hud.select_resident("tomas")
        self.hud.toggle_panel_tab()
        self.hud.taste_debug = True
        self.view.render()

    # ----- over their heads and in the log -----

    def test_how_a_meal_is_taken_is_seen_over_the_head_of_whoever_takes_it(self) -> None:
        self.assertIsNone(self.view.mark_over("lucia"))
        self._eat(self.lucia)
        self._eat(self.raul)
        self.assertEqual(self.view.mark_over("lucia"), "relish")
        self.assertEqual(self.view.mark_over("raul"), "disgust")
        self.assertIsNone(self.view.mark_over("tomas"))
        self.view.render()
        # Then, for as long again, that something has been learned of them; and then nothing.
        self.view.time += MARK_SECONDS + 0.1
        self.assertEqual(self.view.mark_over("raul"), FOUND_OUT_MARK)
        self.view.time += MARK_SECONDS
        self.assertIsNone(self.view.mark_over("raul"))
        self.view.render()

    def test_marks_do_not_pile_up_however_fast_time_goes(self) -> None:
        for _ in range(20):
            self._eat(self.raul)
        self.view.time += MARK_SECONDS * 3 + 0.1
        self.assertIsNone(self.view.mark_over("raul"))

    def test_a_present_taken_well_shows_over_whoever_was_given_it(self) -> None:
        self.tastes.react(self.world, self.lucia, self.cake, GIVEN, self.raul)
        self.view.on_events(self.world.events.drain())
        self.assertEqual(self.view.mark_over("lucia"), "relish")
        self.assertIsNone(self.view.mark_over("raul"))

    def test_what_is_found_out_stands_out_in_the_log_and_is_told_in_words(self) -> None:
        self._eat(self.raul)
        feed = self.hud.feed
        found = [event for event in feed.recent(10) if event.event_type == FOUND_OUT_EVENT]
        taken = [event for event in feed.recent(10) if event.event_type == REACTION_EVENT]
        self.assertTrue(found and taken)
        self.assertEqual(feed.color(found[0]), PALETTE["teal"])
        self.assertNotEqual(feed.color(taken[0]), PALETTE["teal"])
        self.assertIn("Raúl parece evitar", found[0].text)
        self.assertIn("Raúl come una tarta con asco", taken[0].text)

    def test_the_whole_thing_is_seen_on_the_map_and_then_in_the_panel(self) -> None:
        self.hud.select_resident("lucia")
        self.hud.toggle_panel_tab()
        self.assertNotIn(("La tarta", "Le encanta", LOVED), taste_rows(self.world, self.lucia))
        self._eat(self.lucia, 3)
        self.assertEqual(self.view.mark_over("lucia"), "relish")
        self.assertIn(("La tarta", "Le encanta", LOVED), taste_rows(self.world, self.lucia))
        self.view.render()
        self.game.present()

    # ----- the item editor -----

    def test_the_item_editor_has_a_field_for_what_there_is_to_like_about_a_thing(self) -> None:
        editor = self.game.item_editor
        editor.open("stew")
        self.assertEqual(editor.values["tags"], "food, cooked, meal")
        self.assertEqual(editor.values["preference_tags"], "hot, homemade")
        self.assertIn("preference_tags", editor.field_rects)
        self.assertTrue(all(rect.bottom < self.game.canvas.get_height() for rect in editor.field_rects.values()))
        editor.values["preference_tags"] = "Hot, very spicy,  hot , old-world,"

        self.assertTrue(editor.save(), editor.notice)

        data = json.loads((self.root / "custom" / "items" / "stew" / "data.json").read_text(encoding="utf-8"))
        self.assertEqual(data["preference_tags"], ["hot", "very_spicy", "old_world"])
        self.assertEqual(data["tags"], ["food", "cooked", "meal"])
        self.assertEqual(self.world.registries.items.get("stew").preference_tags, ("hot", "very_spicy", "old_world"))
        editor.open("stew")
        self.assertEqual(editor.values["preference_tags"], "hot, very_spicy, old_world")
        editor.render()
        # And whoever eats it next has a taste for what it now is.
        self.tastes.react(self.world, self.raul, self.world.registries.items.get("stew"), EATEN)
        self.assertIn("very_spicy", self.tastes.profile(self.world, self.raul).tags)

    def test_a_taste_that_cannot_be_one_is_not_saved_and_the_editor_says_so(self) -> None:
        editor = self.game.item_editor
        editor.open("stew")
        editor.values["preference_tags"] = "hot, ¿qué?"
        self.assertFalse(editor.save())
        self.assertIn("No se pudo guardar", editor.notice)
        self.assertFalse((self.root / "custom" / "items" / "stew" / "data.json").exists())
        self.assertEqual(self.world.registries.items.get("stew").preference_tags, ("hot", "homemade"))
        # With none at all it is simply a thing nobody makes anything of.
        editor.values["preference_tags"] = " "
        self.assertTrue(editor.save(), editor.notice)
        self.assertEqual(self.world.registries.items.get("stew").preference_tags, ())


if __name__ == "__main__":
    unittest.main()
