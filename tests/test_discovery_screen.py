"""Where what a resident has come to at their job is drawn and named (P54), through the real
game shell without a window."""

import os
import tempfile
import unittest
from pathlib import Path

import pygame

from graphics.object_pictures import PAINTERS, ObjectPictures
from scenes.discovery_editor import MADE_FOLDER, NAMELESS
from scenes.hud import DISCOVERY_INTENT
from scenes.item_editor import ART_AREA
from simulation.registries import DATA_DIR, BuiltInRegistries


class DiscoveryScreenTests(unittest.TestCase):
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

    @staticmethod
    def _restore_driver(variable: str, previous: str | None) -> None:
        if previous is None:
            os.environ.pop(variable, None)
        else:
            os.environ[variable] = previous

    def _comes_to_something(self, resident_id: str) -> str:
        """Have a resident reach the next level of their job, and the game hear of it."""
        resident = self.world.residents[resident_id]
        job = self.world.registries.jobs[resident.job_id]
        marks = self.world.registries.crafts.levels
        level = self.world.crafts.level(self.world, resident, job.job_id)
        self.world.crafts.worked(self.world, resident, job, (marks[level] - resident.trade.get(job.job_id, 0.0)) * 2)
        self.view.on_events(self.world.events.drain())
        return self.world.crafts.waiting(self.world)[-1].discovery_id

    def _frame(self) -> None:
        self.game.sync_scenes()
        self.game.active_scene.update(0.1)
        self.game.active_scene.render()

    def _type(self, text: str) -> None:
        for char in text:
            self.game.handle_event(pygame.event.Event(pygame.KEYDOWN, key=ord(char), mod=0, unicode=char))

    def test_coming_to_something_opens_the_screen_and_time_stands_still(self) -> None:
        discovery_id = self._comes_to_something("raul")
        self.assertEqual(self.view.requested_discovery, discovery_id)
        self._frame()
        self.assertEqual(self.game.scene_name, "discovery")
        self.assertIs(self.game.active_scene, self.editor)
        self.assertEqual(self.editor.discovery_id, discovery_id)
        self.assertEqual(self.editor.picked, {"grows": "soil"}, "the first of what there is to pick")
        before = self.world.clock.total_minutes
        self.game.advance_simulation(5.0)
        self.assertEqual(self.world.clock.total_minutes, before)

    def test_it_is_drawn_named_and_picked_and_then_it_is_theirs(self) -> None:
        discovery_id = self._comes_to_something("raul")
        self._frame()
        editor = self.editor
        self._type("tomate")
        self.assertEqual(editor.name, "tomate")
        # A red stroke across the paper.
        editor.color = (200, 40, 40)
        editor.press((ART_AREA.x + 40, ART_AREA.centery))
        editor.drag((ART_AREA.right - 40, ART_AREA.centery))
        self.game.handle_event(pygame.event.Event(pygame.MOUSEBUTTONUP, button=1, pos=(0, 0)))
        # The list opens under its box, and a pick shuts it.
        editor.press(editor.choice_boxes()["grows"].center)
        self.assertEqual(editor.open_choice, "grows")
        rows = editor.option_boxes()
        self.assertEqual([option_id for _, option_id in rows], ["soil", "bush", "vine", "tree"])
        self._frame()
        editor.press(rows[1][0].center)
        self.assertEqual((editor.picked, editor.open_choice), ({"grows": "bush"}, None))
        self._frame()
        save = next(button for button in editor.top_buttons if button.intent == ("save",))
        editor.press(save.rect.center)
        self.assertTrue(editor.closed)
        discovery = self.world.discoveries[discovery_id]
        self.assertEqual((discovery.name, discovery.choices), ("tomate", {"grows": "bush"}))
        self.assertEqual(self.world.residents["raul"].makes, {discovery_id: self.world.clock.day})
        picture = self.custom / MADE_FOLDER / discovery.item_id / "icon.png"
        self.assertTrue(picture.is_file())
        shown = self.game.icons.picture(discovery.item_id)
        self.assertEqual(tuple(shown.get_at((shown.get_width() // 2, shown.get_height() // 2)))[:3], (200, 40, 40))
        self._frame()
        self.assertEqual(self.game.scene_name, "global")
        self.assertIn("tomate", self.hud.notice)
        self.assertIsNone(self.hud.discovery_button(), "nothing waits any more")

    def test_enter_saves_it_too(self) -> None:
        self._comes_to_something("raul")
        self._frame()
        self._type("ajos")
        self.game.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN, mod=0, unicode="\r"))
        self.assertTrue(self.editor.closed)
        self.assertEqual(self.editor.discovery.name, "ajos")

    def test_it_needs_a_name_and_one_that_is_not_taken(self) -> None:
        self._comes_to_something("raul")
        self._frame()
        editor = self.editor
        self.assertFalse(editor.save())
        self.assertEqual(editor.notice, NAMELESS)
        self.assertFalse(editor.closed)
        editor.set_name("Guiso caliente")
        self.assertFalse(editor.save())
        self.assertIn("Ya hay algo", editor.notice)
        self.assertFalse(editor.closed)
        self._frame()
        editor.set_name("x" * 80)
        self.assertEqual(len(editor.name), self.world.registries.crafts.name_length, "no longer than a name can be")

    def test_left_for_later_it_waits_under_a_notice_that_opens_it_again(self) -> None:
        discovery_id = self._comes_to_something("raul")
        self._frame()
        self._type("tom")
        self.game.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE, mod=0, unicode=""))
        self._frame()
        self.assertEqual(self.game.scene_name, "global")
        self.assertFalse(self.world.discoveries[discovery_id].named)
        waiting = self.hud.discovery_button()
        self.assertIsNotNone(waiting)
        self.assertIn("Raúl", waiting.label)
        self.assertTrue(self.hud.layout.map.contains(waiting.rect))
        self.assertTrue(self.hud.covers(waiting.rect.center), "a click on it does not fall through to the map")
        self.assertEqual(waiting.intent, DISCOVERY_INTENT)
        self.view.click(waiting.rect.center)
        self._frame()
        self.assertEqual(self.game.scene_name, "discovery")
        self.assertEqual(self.editor.name, "", "and it starts from a blank")

    def test_with_several_waiting_the_notice_counts_them_and_the_oldest_comes_first(self) -> None:
        first = self._comes_to_something("raul")
        self._frame()
        self.editor.closed = True
        self._frame()
        self._comes_to_something("marta")
        self._frame()
        self.editor.closed = True
        self._frame()
        waiting = self.hud.discovery_button()
        self.assertIn("2", waiting.label)
        self.view.click(waiting.rect.center)
        self._frame()
        self.assertEqual(self.editor.discovery_id, first)

    def test_what_a_dish_is_made_of_is_picked_from_the_food_there_is(self) -> None:
        self._comes_to_something("marta")
        self._frame()
        editor = self.editor
        editor.press(editor.choice_boxes()["from"].center)
        listed = [option_id for _, option_id in editor.option_boxes()]
        self.assertIn("vegetables", listed)
        self.assertNotIn("stew", listed)
        self._frame()
        editor.press(next(box for box, option_id in editor.option_boxes() if option_id == "vegetables").center)
        self._type("pisto")
        self.assertTrue(editor.save())
        self.assertEqual(editor.discovery.choices, {"from": "vegetables"})

    def test_a_place_is_named_and_not_drawn(self) -> None:
        discovery_id = self._comes_to_something("sergio")
        self._frame()
        editor = self.editor
        self.assertFalse(editor.drawn)
        blank = editor.picture.copy()
        editor.press(ART_AREA.center)
        self.assertEqual(pygame.image.tobytes(editor.picture, "RGBA"), pygame.image.tobytes(blank, "RGBA"))
        self._type("El Vertedero")
        self._frame()
        self.assertTrue(editor.save())
        self.assertIsNone(self.world.discoveries[discovery_id].item_id)
        self.assertFalse((self.custom / MADE_FOLDER).exists(), "there is nothing to keep a picture of")

    def test_what_has_a_name_already_is_not_opened(self) -> None:
        discovery_id = self._comes_to_something("raul")
        self.assertTrue(self.world.name_discovery(discovery_id, "tomate").ok)
        self._frame()
        self.assertEqual(self.game.scene_name, "global")

    def test_the_folder_of_pictures_is_no_pack(self) -> None:
        discovery_id = self._comes_to_something("raul")
        self._frame()
        self._type("tomate")
        self.assertTrue(self.editor.save())
        item_id = self.world.discoveries[discovery_id].item_id
        with self.assertNoLogs("simulation.items.custom_content", level="WARNING"):
            registries = BuiltInRegistries.load(DATA_DIR, custom_dir=self.custom)
        self.assertIsNone(registries.items.find(item_id), "what it is belongs to the settlement that came to it")


class BedsOnTheMapTests(unittest.TestCase):
    """A bed as the game draws it on the window, by how what grows in it is grown (P55)."""

    def setUp(self) -> None:
        for variable in ("SDL_VIDEODRIVER", "SDL_AUDIODRIVER"):
            self.addCleanup(DiscoveryScreenTests._restore_driver, variable, os.environ.get(variable))
            os.environ[variable] = "dummy"
        from game.game import Game

        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        root = Path(self._tmp.name)
        (root / "illustrations").mkdir()
        self.game = Game(
            illustrations_dir=root / "illustrations", voices_dir=None, start_in_menu=False,
            custom_content_dir=root / "custom",
        )
        self.addCleanup(pygame.quit)
        self.view, self.world = self.game.global_view, self.game.world

    def _learns(self, resident_id: str, name: str, way: str) -> None:
        world = self.world
        resident = world.residents[resident_id]
        job = world.registries.jobs[resident.job_id]
        level = world.crafts.level(world, resident, job.job_id)
        world.crafts.worked(world, resident, job, world.registries.crafts.levels[level] * 2)
        waiting = [each for each in world.crafts.waiting(world) if each.by == resident_id]
        self.assertTrue(world.name_discovery(waiting[0].discovery_id, name, {"grows": way}).ok)

    def test_each_way_of_growing_has_a_picture_of_its_own_and_the_ground_is_the_bed_as_it_was(self) -> None:
        pictures = ObjectPictures()
        self.assertEqual(pictures.grown("crop_bed", None), "crop_bed")
        self.assertEqual(pictures.grown("crop_bed", "soil"), "crop_bed")
        seen = {"crop_bed": pygame.image.tobytes(pictures.at("crop_bed", 64).under, "RGBA")}
        for way in ("bush", "vine", "tree"):
            kind = pictures.grown("crop_bed", way)
            self.assertEqual(kind, f"crop_bed_{way}")
            self.assertIn(kind, PAINTERS)
            seen[kind] = pygame.image.tobytes(pictures.at(kind, 64).under, "RGBA")
        self.assertEqual(len(set(seen.values())), 4, "no two look alike")
        self.assertGreater(pictures.at("crop_bed_tree", 64).rise, pictures.at("crop_bed_bush", 64).rise, "a tree stands taller")
        self.assertEqual(pictures.grown("crate", "tree"), "crate", "what grows nothing looks as it does")

    def test_the_bed_of_whoever_grows_a_tree_is_seen_with_a_tree_in_it(self) -> None:
        view, world = self.view, self.world
        self.assertTrue(view.windowed)
        raul, ines = world.residents["raul"], world.residents["ines"]
        bed = world.registries.interactables.get("crop_bed")
        mine, theirs = world.interactables[raul.post_id], world.interactables[ines.post_id]
        plain = view._game_picture(bed, mine)
        self.assertIs(plain, view._game_picture(bed), "until something is come to, a bed like any other")
        self._learns("raul", "limones", "tree")
        tree = view._game_picture(bed, mine)
        self.assertIs(tree, view.object_pictures.at("crop_bed_tree", view._cell))
        self.assertGreater(tree.under.get_height(), plain.under.get_height())
        self.assertIs(view._game_picture(bed, theirs), plain, "and the bed beside it is as it was")
        self.view.centre_on_resident("raul")
        self.view.render()


if __name__ == "__main__":
    unittest.main()
