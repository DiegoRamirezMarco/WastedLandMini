import logging
import os
import tempfile
import unittest
from pathlib import Path

import pygame

from save.save_manager import SaveManager
from settings import SCALE
from simulation.commands import (
    AcknowledgeTutorialCommand,
    ChooseOptionCommand,
    FoundResidentCommand,
    MoveObjectCommand,
    PlaceBuildingCommand,
    PlaceObjectCommand,
    SuggestJobCommand,
)
from simulation.registries import builtin_registries
from simulation.tutorial.tutorial import tutorial_definition_from_data
from simulation.world import SimulationWorld

MINUTES_PER_DAY = 24 * 60
# A shack whose inside runs from (10, 10) to (13, 12), with its door at (12, 13).
SHACK_AT = (10, 10)
SECOND_SHACK_AT = (10, 20)


def settle(world: SimulationWorld, until: str | None = None) -> None:
    """Do what each step of the opening asks for, in order, stopping once `until` is the step in hand."""
    moves = {
        "founder": lambda: world.apply_command(FoundResidentCommand("Ada", 34, {"empathy": 70.0}, ["music_lover"])),
        "shack": lambda: world.apply_command(PlaceBuildingCommand("shack", SHACK_AT)),
        "bed": lambda: world.apply_command(PlaceObjectCommand("bed", (10, 10))),
        "crate": lambda: world.apply_command(PlaceObjectCommand("crate", (13, 10))),
        "pantry": lambda: world.apply_command(PlaceObjectCommand("pantry", (12, 10))),
        "water": lambda: world.apply_command(PlaceObjectCommand("water_tank", (18, 10))),
        "time": lambda: world.step(120),
        "garden": lambda: [world.apply_command(PlaceObjectCommand("crop_bed", (x, 16))) for x in (20, 22)],
        "job": lambda: world.apply_command(SuggestJobCommand(next(iter(world.residents)), "farmer")),
        "fire": lambda: world.apply_command(PlaceObjectCommand("campfire", (16, 16))),
        "second_bed": lambda: [
            world.apply_command(PlaceBuildingCommand("shack", SECOND_SHACK_AT)),
            world.apply_command(PlaceObjectCommand("bed", SECOND_SHACK_AT)),
        ],
        "stranger": lambda: world.apply_command(ChooseOptionCommand(next(iter(world.decisions)), "open")),
        "free": lambda: world.apply_command(AcknowledgeTutorialCommand()),
    }
    for _ in range(len(moves) + 1):
        step = world.tutorial.step_id
        if step is None or step == until:
            return
        moves[step]()


class NewSettlementTests(unittest.TestCase):
    def setUp(self) -> None:
        self.world = SimulationWorld.new_settlement(seed=7)

    def test_a_new_settlement_is_an_empty_plot_on_its_first_step(self) -> None:
        self.assertEqual(self.world.map_id, self.world.registries.tutorial.map_id)
        self.assertFalse(self.world.residents)
        self.assertFalse([room for room in self.world.rooms.values() if room.roofed])
        self.assertFalse(self.world.containers)
        self.assertEqual(self.world.tutorial.step_id, self.world.registries.tutorial.steps[0].step_id)
        self.assertEqual(self.world.guide.progress(self.world), (1, len(self.world.registries.tutorial.steps)))
        # Nothing goes wrong on a plot with nobody and nothing on it.
        self.world.step(MINUTES_PER_DAY)

    def test_the_settlement_that_comes_ready_made_has_no_opening(self) -> None:
        demo = SimulationWorld.demo_world()
        self.assertFalse(demo.tutorial.active)
        self.assertIsNone(demo.guide.current(demo))
        self.assertFalse(demo.apply_command(AcknowledgeTutorialCommand()))

    def test_the_first_resident_is_made_by_the_player_and_only_the_first(self) -> None:
        created = self.world.apply_command(
            FoundResidentCommand("  Ñoño   Pérez ", 5, {"empathy": 140.0, "no_such_thing": 3.0}, ["music_lover", "no_such"], "tomas")
        )
        self.assertEqual(created, "nono_perez")
        resident = self.world.residents[created]
        self.assertEqual(resident.name, "Ñoño Pérez")
        self.assertEqual(resident.age, 18)
        self.assertEqual(resident.personality.empathy, 100.0)
        self.assertEqual(resident.traits, ["music_lover"])
        self.assertEqual(resident.look, "tomas")
        self.assertIn(resident.tile, self.world.entry_tiles())
        self.assertEqual(self.world.events.drain()[0].event_type, "resident_founded")
        # After that people come by the gate, or not at all.
        self.assertIsNone(self.world.apply_command(FoundResidentCommand("Otra", 30)))
        self.assertEqual(list(self.world.residents), [created])

    def test_nobody_is_made_without_a_name_or_where_people_already_live(self) -> None:
        self.assertIsNone(self.world.apply_command(FoundResidentCommand("   ", 30)))
        self.assertFalse(self.world.residents)
        demo = SimulationWorld.demo_world()
        self.assertIsNone(demo.apply_command(FoundResidentCommand("Ada", 30)))

    def test_a_made_resident_never_takes_the_id_of_someone_who_may_still_walk_in(self) -> None:
        newcomer = self.world.registries.world_events.newcomers[0]
        created = self.world.apply_command(FoundResidentCommand(newcomer.name, 30))
        self.assertNotEqual(created, newcomer.newcomer_id)
        self.assertTrue(self.world.happenings.strangers_left(self.world))

    def test_steps_are_done_by_what_the_settlement_becomes_even_with_time_stopped(self) -> None:
        self.world.set_paused(True)
        settle(self.world, until="time")
        self.assertEqual(self.world.tutorial.done, ["founder", "shack", "bed", "crate", "pantry", "water"])
        done = [event for event in self.world.events.drain() if event.event_type == "tutorial_step_done"]
        self.assertEqual([event.data["step"] for event in done], self.world.tutorial.done)
        # Waiting is the one step that time has to pass for.
        self.world.step(500)
        self.assertEqual(self.world.tutorial.step_id, "time")
        self.world.set_paused(False)
        self.world.step(89)
        self.assertEqual(self.world.tutorial.step_id, "time")
        self.world.step(1)
        self.assertEqual(self.world.tutorial.step_id, "garden")

    def test_a_bed_out_of_doors_is_not_the_bed_under_a_roof_that_was_asked_for(self) -> None:
        settle(self.world, until="bed")
        self.assertTrue(self.world.apply_command(PlaceObjectCommand("bed", (30, 10))).ok)
        self.assertEqual(self.world.tutorial.step_id, "bed")
        self.assertTrue(self.world.apply_command(PlaceObjectCommand("bed", (10, 10))).ok)
        self.assertEqual(self.world.tutorial.step_id, "crate")

    def test_each_step_hands_over_what_the_settlement_starts_with(self) -> None:
        settle(self.world, until="time")
        founder = next(iter(self.world.residents.values()))
        self.assertEqual([(item.definition_id, item.owner_id) for item in founder.inventory.items], [("hoe", founder.resident_id)])
        stock = {
            self.world.interactables[object_id].kind: {item.definition_id: item.quantity for item in inventory.items}
            for object_id, inventory in self.world.containers.items()
        }
        self.assertEqual(stock, {"crate": {"scrap": 6}, "pantry": {"canned_beans": 30}, "water_tank": {"water": 120}})

    def test_the_stranger_of_the_opening_is_answered_by_whoever_is_there_and_decided_by_them(self) -> None:
        settle(self.world, until="stranger")
        founder = next(iter(self.world.residents.values()))
        self.assertIsNotNone(self.world.at_the_gate)
        decision = next(iter(self.world.decisions.values()))
        self.assertEqual((decision.kind, decision.resident_id), ("stranger", founder.resident_id))
        # Nobody is told what to do: left alone, they make up their own mind and the opening goes on.
        self.world.step(61)
        self.assertFalse([each for each in self.world.decisions.values() if each.kind == "stranger"])
        self.assertIsNone(self.world.at_the_gate)
        self.assertEqual(self.world.tutorial.step_id, "free")

    def test_no_stranger_comes_until_there_is_a_bed_for_them(self) -> None:
        settle(self.world, until="second_bed")
        self.world.step(30)
        self.assertIsNone(self.world.at_the_gate)
        self.assertFalse(self.world.decisions)

    def test_the_world_outside_keeps_away_until_the_opening_is_over(self) -> None:
        settle(self.world, until="free")
        self.world.step(MINUTES_PER_DAY * 20)
        kinds = {line.split(" | ")[1] for line in self.world.event_log}
        self.assertFalse(kinds & {"raid", "weather_changed", "food_spoiled", "stranger_unanswered", "caravan_passed"})
        self.assertFalse(self.world.upcoming)
        self.assertTrue(self.world.apply_command(AcknowledgeTutorialCommand()))
        self.assertFalse(self.world.tutorial.active)
        self.assertEqual(self.world.events.drain()[-1].event_type, "tutorial_finished")
        self.world.step(MINUTES_PER_DAY * 30)
        kinds = {line.split(" | ")[1] for line in self.world.event_log}
        self.assertTrue(kinds & {"raid", "weather_changed", "food_spoiled", "stranger_unanswered", "stranger_at_gate"})

    def test_a_settlement_with_no_generator_is_not_told_its_fuel_ran_out(self) -> None:
        settle(self.world)
        self.world.step(MINUTES_PER_DAY * 2)
        self.assertNotIn("power_failed", {line.split(" | ")[1] for line in self.world.event_log})

    def test_the_opening_is_saved_where_it_was(self) -> None:
        settle(self.world, until="stranger")
        manager = SaveManager()
        data = manager.to_data(self.world)
        loaded = manager.from_data(data, self.world.registries)
        self.assertEqual(loaded.tutorial, self.world.tutorial)
        self.assertEqual(manager.to_data(loaded), data)
        self.assertEqual(next(iter(loaded.residents.values())).look, next(iter(self.world.residents.values())).look)
        # And it goes on from there.
        settle(loaded)
        self.assertFalse(loaded.tutorial.active)

    def test_older_saves_and_steps_that_are_gone_are_past_the_opening(self) -> None:
        manager = SaveManager()
        data = manager.to_data(self.world)
        without = {key: value for key, value in data.items() if key != "tutorial"}
        self.assertFalse(manager.from_data(without, self.world.registries).tutorial.active)
        data["tutorial"]["step"] = "a_step_nobody_wrote"
        loaded = manager.from_data(data, self.world.registries)
        self.assertFalse(loaded.tutorial.active)
        loaded.step(10)

    def test_two_people_settled_as_the_opening_teaches_last_four_weeks(self) -> None:
        for seed in (7, 23):
            world = SimulationWorld.new_settlement(seed=seed)
            settle(world)
            self.assertEqual(len(world.residents), 2, seed)
            world.step(MINUTES_PER_DAY * 28)
            self.assertEqual(len(world.residents), 2, seed)
            self.assertFalse(world.deaths, seed)
            self.assertTrue(all(resident.health > 90 for resident in world.residents.values()), seed)

    def test_the_same_seed_settles_the_same_way(self) -> None:
        logs = []
        for _ in range(2):
            world = SimulationWorld.new_settlement(seed=11)
            settle(world)
            world.step(MINUTES_PER_DAY * 3)
            logs.append(world.event_log)
        self.assertEqual(logs[0], logs[1])


class TutorialDataTests(unittest.TestCase):
    def test_the_steps_the_game_comes_with_can_all_be_done_with_what_it_has(self) -> None:
        registries = builtin_registries()
        self.assertIn(registries.tutorial.map_id, registries.maps)
        self.assertGreater(len(registries.tutorial.steps), 5)
        layout = registries.maps[registries.tutorial.map_id]
        self.assertTrue(layout.arrivals)

    def test_steps_that_make_no_sense_are_refused(self) -> None:
        step = {"id": "a", "title": "t", "text": "x", "goal": {"type": "residents"}}
        tutorial_definition_from_data({"map": "m", "steps": [step]})
        for broken in (
            {**step, "goal": {"type": "no_such_goal"}},
            {**step, "goal": {"type": "object"}},
            {**step, "goal": {"type": "answered"}},
            {**step, "opening": "no_such_opening"},
            {**step, "gifts": [{"item": "hoe"}]},
            {**step, "gifts": [{"item": "hoe", "into": "crate", "to": "resident"}]},
            {**step, "gifts": [{"item": "hoe", "to": "somebody"}]},
        ):
            with self.assertRaises(ValueError, msg=broken):
                tutorial_definition_from_data({"map": "m", "steps": [broken]})
        with self.assertRaises(ValueError):
            tutorial_definition_from_data({"map": "m", "steps": [step, step]})


class WithinReachTests(unittest.TestCase):
    """Nothing can be put down that leaves a bed, a container, a post or a doorway out of reach."""

    def setUp(self) -> None:
        self.world = SimulationWorld.new_settlement(seed=7)
        settle(self.world, until="crate")

    def _refused(self, result) -> str:
        self.assertFalse(result.ok)
        return result.message

    def test_a_bed_cannot_be_walled_in_by_another(self) -> None:
        before = dict(self.world.interactables)
        self.assertIn("cama", self._refused(self.world.apply_command(PlaceObjectCommand("bed", (11, 10)))))
        self.assertEqual(self.world.interactables, before)
        # Away from its head there is room.
        self.assertTrue(self.world.apply_command(PlaceObjectCommand("bed", (13, 10))).ok)

    def test_nothing_goes_in_the_doorway_of_a_building_that_is_used(self) -> None:
        self._refused(self.world.apply_command(PlaceObjectCommand("crate", (12, 12))))
        # Something that can be walked over is another matter.
        self.assertTrue(self.world.apply_command(PlaceObjectCommand("stool", (12, 12))).ok)

    def test_a_building_cannot_be_put_up_against_another_s_door(self) -> None:
        self._refused(self.world.apply_command(PlaceBuildingCommand("shack", (10, 15))))
        self.assertTrue(self.world.apply_command(PlaceBuildingCommand("shack", (10, 16))).ok)

    def test_an_empty_building_keeps_its_way_in_too(self) -> None:
        empty = self.world.apply_command(PlaceBuildingCommand("shack", (30, 10)))
        self.assertTrue(empty.ok)
        self.assertIn("chabola", self._refused(self.world.apply_command(PlaceObjectCommand("crate", (32, 14)))))

    def test_a_building_whose_door_would_face_the_fence_is_refused(self) -> None:
        height = self.world.tile_map.height
        self._refused(self.world.apply_command(PlaceBuildingCommand("shack", (36, height - 5))))

    def test_moving_is_judged_the_same_way(self) -> None:
        crate = self.world.apply_command(PlaceObjectCommand("crate", (13, 12))).entity_id
        self.assertIsNotNone(self.world.urbanism.move_object_error(self.world, crate, (11, 10)))
        self.assertFalse(self.world.apply_command(MoveObjectCommand(crate, (11, 10))).ok)
        self.assertTrue(self.world.apply_command(MoveObjectCommand(crate, (13, 10))).ok)

    def test_what_is_already_out_of_reach_does_not_stop_everything_else(self) -> None:
        # A bed walled in behind the simulation's back, as an old save may have it.
        from world.interactable import Interactable

        self.world.interactables["stray"] = Interactable("stray", "crate", 11, 10)
        self.assertTrue(self.world.apply_command(PlaceObjectCommand("crate", (30, 10))).ok)


class MenuAndCreatorTests(unittest.TestCase):
    """Runs the real game shell without a window, through SDL's dummy drivers."""

    def setUp(self) -> None:
        for variable in ("SDL_VIDEODRIVER", "SDL_AUDIODRIVER"):
            self.addCleanup(self._restore_driver, variable, os.environ.get(variable))
            os.environ[variable] = "dummy"
        from game.game import Game

        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.save_path = Path(self._tmp.name) / "saves" / "quicksave.json"
        self.game = Game(illustrations_dir=None, voices_dir=None, save_path=self.save_path)
        self.addCleanup(pygame.quit)

    @staticmethod
    def _restore_driver(variable: str, previous: str | None) -> None:
        if previous is None:
            os.environ.pop(variable, None)
        else:
            os.environ[variable] = previous

    def _key(self, key: int, text: str = "") -> None:
        self.game.handle_event(pygame.event.Event(pygame.KEYDOWN, key=key, unicode=text, mod=0))
        self.game.sync_scenes()

    def _click(self, position: tuple[int, int]) -> None:
        window = (position[0] * SCALE + 1, position[1] * SCALE + 1)
        for kind in (pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP):
            self.game.handle_event(pygame.event.Event(kind, pos=window, button=1))
        self.game.sync_scenes()

    def _frame(self) -> None:
        self.game.active_scene.update(1 / 60)
        self.game.active_scene.render()
        self.game.present()

    def _type(self, text: str) -> None:
        for char in text:
            self._key(pygame.key.key_code(char.lower()) if char.isalpha() else pygame.K_SPACE, char)

    def _start_new_game(self, name: str = "Ada") -> str:
        self.game.main_menu.choose("new")
        self.game.sync_scenes()
        self._type(name)
        self._key(pygame.K_RETURN)
        return next(iter(self.game.world.residents))

    def test_the_game_opens_on_the_menu_with_nothing_to_go_on_with(self) -> None:
        self.assertEqual(self.game.scene_name, "menu")
        self.assertFalse(self.game.in_session)
        self._frame()
        entries = {entry.choice: entry for entry in self.game.main_menu.entries}
        self.assertFalse(entries["continue"].enabled)
        self.assertTrue(entries["new"].enabled)
        # What cannot be chosen is passed over, and time does not run behind the menu.
        self._key(pygame.K_UP)
        self._key(pygame.K_UP)
        self.assertTrue(self.game.main_menu.entries[self.game.main_menu.selected].enabled)
        minute = self.game.world.clock.total_minutes
        self.game.advance_simulation(5.0)
        self.assertEqual(self.game.world.clock.total_minutes, minute)
        self.game.main_menu.choose("continue")
        self.game.sync_scenes()
        self.assertEqual(self.game.scene_name, "menu")

    def test_keys_in_the_menu_are_choices_and_not_the_shortcuts_of_the_map(self) -> None:
        self._key(pygame.K_SPACE)
        self.assertFalse(self.game.world.clock.paused)
        self.assertEqual(self.game.scene_name, "creator")
        self._key(pygame.K_m, "m")
        self._key(pygame.K_TAB, "\t")
        self._key(pygame.K_1, "1")
        self.assertEqual(self.game.scene_name, "creator")
        self.assertEqual(self.game.creator.name, "m1")
        self.assertFalse(self.game.audio.muted)

    def test_a_new_game_makes_its_first_resident_and_leads_on_from_there(self) -> None:
        self.game.main_menu.choose("new")
        self.game.sync_scenes()
        self.assertEqual(self.game.scene_name, "creator")
        self.assertEqual(self.game.world.map_id, self.game.world.registries.tutorial.map_id)
        self._frame()
        # Nobody is made without a name.
        self._key(pygame.K_RETURN)
        self.assertEqual(self.game.scene_name, "creator")
        self.assertFalse(self.game.world.residents)
        self._type("Ada")
        self._key(pygame.K_BACKSPACE)
        self._type("a")
        creator = self.game.creator
        creator.set_age(creator.age + 5)
        creator.toggle_trait("music_lover")
        self._click(creator.look_buttons[1].rect.center)
        look = creator.look
        slider = creator.sliders["courage"]
        self._click((slider.rect.right, slider.rect.centery))
        self._frame()
        self._key(pygame.K_RETURN)

        self.assertEqual(self.game.scene_name, "global")
        resident = self.game.world.residents["ada"]
        self.assertEqual((resident.age, resident.traits, resident.look), (35, ["music_lover"], look))
        self.assertEqual(resident.personality.courage, 100.0)
        self.assertEqual(self.game.global_view.hud.selected_id, "ada")
        self.assertEqual(self.game.world.tutorial.step_id, "shack")
        # They are drawn with the look they were given, by face and body alike.
        self.assertEqual(self.game.faces.looks.of("ada"), look)
        self.assertEqual(self.game.global_view.bodies.renderer.looks.of("ada"), look)
        self._frame()
        self.assertIsNotNone(self.game.global_view.hud.tutorial_rect())

    def test_leaving_the_creator_empty_handed_leaves_a_way_back_to_it(self) -> None:
        self.game.main_menu.choose("new")
        self.game.sync_scenes()
        self._key(pygame.K_ESCAPE)
        self.assertEqual(self.game.scene_name, "global")
        self.assertFalse(self.game.world.residents)
        self._frame()
        hud = self.game.global_view.hud
        button = next(button for button in hud.buttons if button.intent == ("tutorial_creator",))
        self._click(button.rect.center)
        self.assertEqual(self.game.scene_name, "creator")

    def test_the_step_in_hand_is_on_show_and_moves_on_as_things_are_built(self) -> None:
        self._start_new_game()
        hud = self.game.global_view.hud
        self.assertEqual(hud.focus, "urbanism")
        self.assertTrue(hud.covers(hud.tutorial_rect().center))
        self._key(pygame.K_u, "u")
        self.assertEqual(self.game.scene_name, "urbanism")
        self._frame()
        self.game.world.apply_command(PlaceBuildingCommand("shack", SHACK_AT))
        self.assertEqual(self.game.world.tutorial.step_id, "bed")
        self._frame()
        # The editor says why something cannot go where it is held, and that it would wall a bed in.
        self.game.world.apply_command(PlaceObjectCommand("bed", (10, 10)))
        editor = self.game.urbanism_editor
        editor.category, editor.catalog_id = "furniture", "bed"
        held = editor._catalog_held()
        pointer = (11 + held.grip[0], 10 + held.grip[1])
        self.assertEqual(held.origin(pointer), (11, 10))
        self.assertIn("cama", editor._held_error(held, pointer) or "")

    def test_the_last_step_is_done_by_saying_it_has_been_read(self) -> None:
        self._start_new_game()
        settle(self.game.world, until="free")
        self._frame()
        hud = self.game.global_view.hud
        button = next(button for button in hud.buttons if button.intent == ("tutorial_acknowledge",))
        self._click(button.rect.center)
        self.assertFalse(self.game.world.tutorial.active)
        self._frame()
        self.assertIsNone(hud.tutorial_rect())

    def test_escape_goes_to_the_menu_and_the_settlement_waits_there(self) -> None:
        self._start_new_game()
        self._key(pygame.K_ESCAPE)
        self.assertEqual(self.game.scene_name, "menu")
        self.assertTrue(self.game.running)
        self._frame()
        self.assertTrue(self.game.main_menu.in_session)
        self._key(pygame.K_ESCAPE)
        self.assertEqual(self.game.scene_name, "global")
        self.assertIn("ada", self.game.world.residents)

    def test_a_game_being_played_is_only_thrown_away_when_asked_twice(self) -> None:
        self._start_new_game()
        self._key(pygame.K_ESCAPE)
        self.game.main_menu.choose("demo")
        self.game.sync_scenes()
        self.assertEqual(self.game.scene_name, "menu")
        self.assertIn("ada", self.game.world.residents)
        self.game.main_menu.choose("demo")
        self.game.sync_scenes()
        self.assertEqual(self.game.scene_name, "global")
        self.assertIn("marta", self.game.world.residents)
        self.assertFalse(self.game.world.tutorial.active)

    def test_continue_brings_back_the_saved_settlement_and_its_opening(self) -> None:
        self._start_new_game()
        self.game.world.apply_command(PlaceBuildingCommand("shack", SHACK_AT))
        self.assertTrue(self.game.save_game())
        self.assertIn("1 habitante", self.game.describe_save() or "")

        from game.game import Game

        again = Game(illustrations_dir=None, voices_dir=None, save_path=self.save_path)
        self.assertEqual(again.scene_name, "menu")
        self.assertTrue(again.main_menu.entries[0].enabled)
        again.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN, unicode="\r", mod=0))
        again.sync_scenes()
        self.assertEqual(again.scene_name, "global")
        self.assertTrue(again.in_session)
        self.assertEqual(list(again.world.residents), ["ada"])
        self.assertEqual(again.world.tutorial.step_id, "bed")

    def test_a_save_that_cannot_be_read_leaves_the_menu_saying_so(self) -> None:
        logging.disable(logging.WARNING)
        self.addCleanup(logging.disable, logging.NOTSET)
        self.save_path.parent.mkdir(parents=True)
        self.save_path.write_text('{"version": 9999}', encoding="utf-8")
        self.game.open_menu()
        self.assertTrue(self.game.main_menu.entries[0].enabled)
        self.game.main_menu.choose("continue")
        self.game.sync_scenes()
        self.assertEqual(self.game.scene_name, "menu")
        self.assertTrue(self.game.main_menu.notice)
        self.assertFalse(self.game.in_session)

    def test_quitting_is_done_from_the_menu(self) -> None:
        self.game.main_menu.choose("quit")
        self.game.sync_scenes()
        self.assertFalse(self.game.running)


if __name__ == "__main__":
    unittest.main()
