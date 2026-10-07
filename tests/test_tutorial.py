import logging
import math
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
    ReportDeedCommand,
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

    def drew(deed: str) -> None:
        """What the player draws is only a name to the simulation: say it was done."""
        world.apply_command(ReportDeedCommand(deed))

    def put(kind: str, *tiles: tuple[int, int]) -> None:
        for tile in tiles:
            world.apply_command(PlaceObjectCommand(kind, tile))
        drew(f"draw:{kind}")

    moves = {
        "founder": lambda: world.apply_command(FoundResidentCommand("Ada", 34, {"empathy": 70.0}, ["music_lover"])),
        "draw_color": lambda: drew("color"),
        "draw_stroke": lambda: drew("stroke"),
        "draw_fill": lambda: drew("fill"),
        "draw_undo": lambda: drew("undo"),
        "draw_measures": lambda: drew("measure"),
        "draw_resident": lambda: drew("save_resident"),
        "shack": lambda: world.apply_command(PlaceBuildingCommand("shack", SHACK_AT)),
        "draw_parts": lambda: drew("part"),
        "draw_building": lambda: drew("save_building"),
        "bed": lambda: put("bed", (10, 10)),
        "crate": lambda: put("crate", (13, 10)),
        "pantry": lambda: put("pantry", (12, 10)),
        "water": lambda: put("water_tank", (18, 10)),
        "time": lambda: world.step(120),
        "garden": lambda: put("crop_bed", (20, 16), (22, 16)),
        "job": lambda: world.apply_command(SuggestJobCommand(next(iter(world.residents)), "farmer")),
        "fire": lambda: put("campfire", (16, 16)),
        "second_bed": lambda: [
            world.apply_command(PlaceBuildingCommand("shack", SECOND_SHACK_AT)),
            world.apply_command(PlaceObjectCommand("bed", SECOND_SHACK_AT)),
        ],
        "stranger": lambda: world.apply_command(ChooseOptionCommand(next(iter(world.decisions)), "open")),
        "outside": lambda: world.apply_command(AcknowledgeTutorialCommand()),
        "building": lambda: world.apply_command(AcknowledgeTutorialCommand()),
        "study": lambda: world.apply_command(AcknowledgeTutorialCommand()),
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
            FoundResidentCommand("  Ñoño   Pérez ", 5, {"empathy": 140.0, "no_such_thing": 3.0}, ["music_lover", "no_such"])
        )
        self.assertEqual(created, "nono_perez")
        resident = self.world.residents[created]
        self.assertEqual(resident.name, "Ñoño Pérez")
        self.assertEqual(resident.age, 18)
        self.assertEqual(resident.personality.empathy, 100.0)
        self.assertEqual(resident.traits, ["music_lover"])
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
        steps = [step.step_id for step in self.world.registries.tutorial.steps]
        self.assertEqual(self.world.tutorial.done, steps[: steps.index("time")])
        self.assertTrue({"shack", "bed", "crate", "pantry", "water"} <= set(self.world.tutorial.done))
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
        self.assertIsNone(self.world.guide.owed(self.world))
        self.assertTrue(self.world.apply_command(PlaceObjectCommand("bed", (10, 10))).ok)
        # It stands, and now it wants drawing: here whatever is made is drawn.
        self.assertEqual(self.world.tutorial.step_id, "bed")
        self.assertEqual(self.world.guide.owed(self.world), "draw:bed")
        self.assertFalse(self.world.apply_command(ReportDeedCommand("draw:crate")))
        self.assertTrue(self.world.apply_command(ReportDeedCommand("draw:bed")))
        self.assertEqual(self.world.tutorial.step_id, "crate")

    def test_drawing_is_taught_a_thing_at_a_time_and_only_what_is_asked_counts(self) -> None:
        settle(self.world, until="draw_color")
        lessons = ["color", "stroke", "fill", "undo", "measure", "save_resident"]
        for index, deed in enumerate(lessons):
            self.assertEqual(self.world.guide.owed(self.world), deed)
            # Doing what a later lesson teaches is not doing this one.
            for other in lessons[index + 1 :]:
                self.assertFalse(self.world.apply_command(ReportDeedCommand(other)))
            self.assertEqual(self.world.guide.owed(self.world), deed)
            self.assertTrue(self.world.apply_command(ReportDeedCommand(deed)))
        self.assertEqual(self.world.tutorial.step_id, "shack")
        self.assertIsNone(self.world.guide.owed(self.world))
        # A building, like a person, is not done until it has been drawn.
        self.world.apply_command(PlaceBuildingCommand("shack", SHACK_AT))
        self.assertEqual(self.world.tutorial.step_id, "draw_parts")
        self.assertEqual(self.world.guide.current(self.world).focus, "building_art")

    def test_nothing_is_reported_to_a_settlement_that_is_past_its_opening(self) -> None:
        demo = SimulationWorld.demo_world()
        self.assertFalse(demo.apply_command(ReportDeedCommand("color")))
        self.assertIsNone(demo.guide.owed(demo))

    def test_each_step_hands_over_what_the_settlement_starts_with(self) -> None:
        settle(self.world, until="time")
        founder = next(iter(self.world.residents.values()))
        self.assertEqual([(item.definition_id, item.owner_id) for item in founder.inventory.items], [("hoe", founder.resident_id)])
        stock = {
            self.world.interactables[object_id].kind: {item.definition_id: item.quantity for item in inventory.items}
            for object_id, inventory in self.world.containers.items()
        }
        self.assertEqual(stock, {"crate": {"scrap": 6}, "pantry": {"canned_beans": 30}, "water_tank": {"water": 120}})

    def test_the_old_radio_that_the_radio_is_worked_out_from_comes_with_the_settlement(self) -> None:
        # It turns up seldom outside, and the radio is what gives word of what is coming.
        settle(self.world, until="study")
        radios = lambda: sum(inventory.count("old_radio") for inventory in self.world.containers.values())  # noqa: E731
        self.assertEqual(radios(), 0)
        settle(self.world)
        crate = next(
            inventory
            for object_id, inventory in self.world.containers.items()
            if self.world.interactables[object_id].kind == "crate"
        )
        # Nobody's, so that whoever studies can take it; and the one the subject asks for.
        self.assertEqual(crate.stack_of("old_radio", None).quantity, 1)
        radio = self.world.registries.research.subjects["radio"]
        self.assertEqual((radio.item, radio.count), ("old_radio", 1))

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
        self.assertEqual(self.world.tutorial.step_id, "outside")

    def test_no_stranger_comes_until_there_is_a_bed_for_them(self) -> None:
        settle(self.world, until="second_bed")
        self.world.step(30)
        self.assertIsNone(self.world.at_the_gate)
        self.assertFalse(self.world.decisions)

    def test_the_world_outside_keeps_away_until_the_opening_is_over(self) -> None:
        settle(self.world, until="free")
        self.world.step(MINUTES_PER_DAY * 20)
        kinds = {line.split(" | ")[1] for line in self.world.event_log}
        self.assertFalse(kinds & {"raid", "weather_changed", "food_spoiled", "stranger_unanswered", "merchant_arrived"})
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
        # And it goes on from there.
        settle(loaded)
        self.assertFalse(loaded.tutorial.active)

    def test_what_has_been_drawn_for_a_step_is_saved_with_it(self) -> None:
        settle(self.world, until="garden")
        self.world.apply_command(ReportDeedCommand("draw:crop_bed"))
        manager = SaveManager()
        loaded = manager.from_data(manager.to_data(self.world), self.world.registries)
        self.assertEqual(loaded.tutorial.deeds, ["draw:crop_bed"])
        for x in (20, 22):
            loaded.apply_command(PlaceObjectCommand("crop_bed", (x, 16)))
        self.assertEqual(loaded.tutorial.step_id, "job")

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


class AfterTheOpeningTests(unittest.TestCase):
    """What a small settlement can do once it is left to itself: take people in, and send someone out."""

    def setUp(self) -> None:
        self.world = SimulationWorld.new_settlement(seed=7)
        settle(self.world)
        self.assertFalse(self.world.tutorial.active)

    def _kinds(self) -> list[str]:
        return [line.split(" | ")[1] for line in self.world.event_log]

    def _room_for_more(self) -> None:
        # What is asked here is who comes and how they fare, so it stands without being built.
        urbanism = self.world.urbanism
        self.assertTrue(urbanism.place_building(self.world, "house", (20, 3)).ok)
        for x in (20, 22, 24):
            self.assertTrue(urbanism.place_object(self.world, "bed", (x, 3)).ok)
        for x in (24, 26):
            self.assertTrue(urbanism.place_object(self.world, "crop_bed", (x, 16)).ok)

    def test_with_no_bed_to_spare_nobody_comes_however_long_it_is(self) -> None:
        self.world.step(MINUTES_PER_DAY * 30)
        self.assertEqual(len(self.world.residents), 2)
        self.assertNotIn("stranger_at_gate", self._kinds()[self._kinds().index("tutorial_finished") :])

    def test_people_keep_coming_to_a_settlement_with_beds_and_no_guard_and_all_of_them_live(self) -> None:
        self._room_for_more()
        self.assertFalse([resident for resident in self.world.residents.values() if resident.job_id == "guard"])
        self.world.step(MINUTES_PER_DAY * 42)
        self.assertGreater(len(self.world.residents), 2, "whoever is in answers the gate")
        self.assertNotIn("stranger_unanswered", self._kinds())
        self.assertFalse(self.world.deaths)
        self.assertTrue(all(resident.health > 90 for resident in self.world.residents.values()))
        # Nobody was let in without a bed for them.
        beds = sum(1 for placed in self.world.interactables.values() if placed.kind == "bed")
        self.assertLessEqual(len(self.world.residents), beds)

    def test_whoever_takes_the_cart_goes_out_and_what_they_bring_ends_up_where_the_settlement_keeps_things(self) -> None:
        self._room_for_more()
        self.assertTrue(self.world.urbanism.place_object(self.world, "handcart", (28, 24)).ok)
        # No shop, no scrap pile, no generator: only a crate, a pantry and a tank.
        kinds = {placed.kind for placed in self.world.interactables.values()}
        self.assertFalse(kinds & {"shop_counter", "scrap_pile", "generator"})
        self.world.step(MINUTES_PER_DAY * 42)
        # With two there are no hands to spare for it. One of those who come takes it up unasked.
        # Whoever it was may have been thrown out since, for what they took that was not theirs
        # (S27), so it is asked of what happened and not of who is still there.
        took_it_up = [line for line in self.world.event_log if " | job_changed | " in line and "Rebusca" in line]
        self.assertEqual(len(took_it_up), 1)
        still_at_it = [resident for resident in self.world.residents.values() if resident.job_id == "scavenger"]
        self.assertEqual(len(still_at_it) + len(self.world.exiled), 1)
        self.assertGreaterEqual(self._kinds().count("expedition_left"), 10, "and goes out day after day, hands free")
        self.assertGreaterEqual(self._kinds().count("expedition_returned"), 10)
        self.assertFalse(self.world.deaths)
        stock: dict[str, int] = {}
        for object_id, inventory in self.world.containers.items():
            kind = self.world.interactables[object_id].kind
            for item in inventory.items:
                stock[kind] = stock.get(kind, 0) + item.quantity
        self.assertGreater(stock.get("crate", 0), 6, "what has no place of its own goes in a crate")


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
            {**step, "goal": {"type": "deed"}},
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
        slider = creator.sliders["courage"]
        self._click((slider.rect.right, slider.rect.centery))
        self._frame()
        self._key(pygame.K_RETURN)

        self.assertEqual(self.game.scene_name, "global")
        resident = self.game.world.residents["ada"]
        self.assertEqual((resident.age, resident.traits), (35, ["music_lover"]))
        self.assertEqual(resident.personality.courage, 100.0)
        self.assertEqual(self.game.global_view.hud.selected_id, "ada")
        # With nowhere to keep drawings there is no drawing them: those steps are passed over.
        self.assertIsNone(self.game.doll_editor)
        self.assertEqual(self.game.world.tutorial.step_id, "shack")
        # Until somebody draws them they borrow one of the game's looks, face and body alike.
        self.assertIn(self.game.faces.looks.of("ada"), self.game.faces.looks.known)
        self.assertEqual(self.game.global_view.bodies.renderer.looks.of("ada"), self.game.faces.looks.of("ada"))
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
        self.game.sync_scenes()
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
        self.assertEqual(again.world.tutorial.step_id, "draw_parts")
        again.sync_scenes()
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


class DrawingLessonsTests(unittest.TestCase):
    """With somewhere to keep drawings, a new settlement is drawn as it is made, and the opening teaches how."""

    def setUp(self) -> None:
        for variable in ("SDL_VIDEODRIVER", "SDL_AUDIODRIVER"):
            self.addCleanup(MenuAndCreatorTests._restore_driver, variable, os.environ.get(variable))
            os.environ[variable] = "dummy"
        from game.game import Game

        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        # Nothing drawn here touches what the player has drawn for real.
        self.drawings = self.root / "illustrations"
        self.drawings.mkdir()
        (self.root / "custom").mkdir()
        self.game = Game(
            illustrations_dir=self.drawings,
            voices_dir=None,
            custom_content_dir=self.root / "custom",
            save_path=self.root / "save.json",
        )
        self.addCleanup(pygame.quit)

    @property
    def step(self) -> str | None:
        return self.game.world.tutorial.step_id

    def _event(self, kind: int, **particulars) -> None:
        self.game.handle_event(pygame.event.Event(kind, **particulars))
        self.game.sync_scenes()

    def _key(self, key: int, text: str = "", mod: int = 0) -> None:
        self._event(pygame.KEYDOWN, key=key, unicode=text, mod=mod)

    def _press(self, position: tuple[int, int]) -> None:
        self._event(pygame.MOUSEBUTTONDOWN, pos=(position[0] * SCALE, position[1] * SCALE), button=1)

    def _move(self, position: tuple[int, int]) -> None:
        self._event(pygame.MOUSEMOTION, pos=(position[0] * SCALE, position[1] * SCALE), rel=(0, 0), buttons=(1, 0, 0))

    def _release(self, position: tuple[int, int]) -> None:
        self._event(pygame.MOUSEBUTTONUP, pos=(position[0] * SCALE, position[1] * SCALE), button=1)

    def _click(self, position: tuple[int, int]) -> None:
        self._press(position)
        self._release(position)

    def _stroke(self, start: tuple[int, int], end: tuple[int, int]) -> None:
        self._press(start)
        self._move(end)
        self._release(end)

    def _frame(self) -> None:
        self.game.active_scene.update(1 / 60)
        self.game.active_scene.render()
        self.game.present()

    def _make_someone(self, name: str = "Zoe") -> str:
        self.game.main_menu.choose("new")
        self.game.sync_scenes()
        for char in name:
            self._key(pygame.key.key_code(char.lower()), char)
        self._key(pygame.K_RETURN)
        return next(iter(self.game.world.residents))

    def _button(self, scene, intent: tuple) -> tuple[int, int]:
        return next(button for button in scene.buttons if button.intent == intent).rect.center

    def _draw_someone(self) -> None:
        """Go through the lessons of the first drawing, as the mouse would."""
        editor = self.game.doll_editor
        body = editor.areas["body"]
        self._click(editor.swatches[9][0].center)
        self._stroke((body.x + 100, body.y + 80), (body.x + 140, body.y + 120))
        self._click(self._button(editor, ("tool", "fill")))
        self._click((body.x + 10, body.y + 10))
        self._key(pygame.K_z, "z", pygame.KMOD_CTRL)
        self._measure(editor)
        self._click(self._button(editor, ("tool", "brush")))
        self._click(self._button(editor, ("mannequin",)))
        self._click(self._button(editor, ("save",)))

    def _measure(self, editor) -> None:
        """Take the measures in hand and make the legs a little shorter, by the ankle."""
        self._click(self._button(editor, ("tool", "measure")))
        body = editor.areas["body"]
        ankle = next(handle for handle in editor.joint_handles("body") if handle.key == "shin.end")
        start = (round(body.x + ankle.point[0]), round(body.y + ankle.point[1]))
        self._stroke(start, (start[0], start[1] - 16))

    def _put_down(self, category: str, catalog_id: str, tile: tuple[int, int]) -> None:
        """Drag something out of the catalogue of the layout editor and let go of it on a tile."""
        editor = self.game.urbanism_editor
        self._click(self._button(editor, ("category", category)))
        self._press(self._button(editor, ("catalog", catalog_id)))
        target = editor._tile_rect(tile).center
        self._move(target)
        self._release(target)

    def test_whoever_is_made_is_drawn_next_and_each_lesson_is_done_by_doing_it(self) -> None:
        resident_id = self._make_someone()
        self.assertEqual(self.game.scene_name, "editor")
        self.assertEqual(self.game.doll_editor.resident_id, resident_id)
        self.assertEqual(self.step, "draw_color")
        self._frame()
        editor = self.game.doll_editor
        body = editor.areas["body"]

        # Painting before a colour is chosen is not the lesson in hand.
        self._stroke((body.x + 60, body.y + 60), (body.x + 80, body.y + 90))
        self.assertEqual(self.step, "draw_color")
        self._click(editor.swatches[9][0].center)
        self.assertEqual(self.step, "draw_stroke")
        self._stroke((body.x + 100, body.y + 80), (body.x + 140, body.y + 120))
        self.assertEqual(self.step, "draw_fill")
        self._frame()
        # Choosing the bucket is not using it.
        self._click(self._button(editor, ("tool", "fill")))
        self.assertEqual(self.step, "draw_fill")
        self._click((body.x + 10, body.y + 10))
        self.assertEqual(self.step, "draw_undo")
        self._key(pygame.K_z, "z", pygame.KMOD_CTRL)
        self.assertEqual(self.step, "draw_measures")
        # Taking the tool is not using it; nor does it paint.
        self._click(self._button(editor, ("tool", "measure")))
        self.assertEqual(self.step, "draw_measures")
        painted = pygame.mask.from_surface(editor.drawings["body"]).count()
        self._stroke((body.x + 150, body.y + 200), (body.x + 170, body.y + 220))
        self.assertEqual(pygame.mask.from_surface(editor.drawings["body"]).count(), painted)
        self.assertEqual(self.step, "draw_measures")
        start = editor.base_template.starting()
        self.assertEqual(editor.build, start, "someone new has the measures every doll starts from")
        self._measure(editor)
        self.assertEqual(self.step, "draw_resident")
        shorter = {**start.joints, "shin.end": round(start.joints.get("shin.end", 0.0) - 1.0, 2)}
        self.assertEqual(editor.build.joints, shorter)
        self._click(self._button(editor, ("tool", "brush")))
        self._click(self._button(editor, ("mannequin",)))
        self._frame()
        self.assertEqual(self.step, "draw_resident")
        self._click(self._button(editor, ("save",)))
        self.assertEqual(self.step, "shack")
        for name in ("body.png", "head.png", "build.json"):
            self.assertTrue((self.drawings / "dolls" / resident_id / name).is_file())
        # Time has stood still all the while.
        self.assertEqual(self.game.world.clock.total_minutes, 8 * 60)
        self._key(pygame.K_ESCAPE)
        self.assertEqual(self.game.scene_name, "global")
        doll = self.game.dolls.get(resident_id)
        self.assertIsNotNone(doll)
        # On the map their legs are as short as they were made on the paper, and no shorter or longer.
        template = self.game.dolls.template
        begun = template.built(start)
        unit = template.unit
        shin = math.dist(begun.parts["shin_left"].start, begun.parts["shin_left"].end) / unit
        thigh = math.dist(begun.parts["thigh_left"].start, begun.parts["thigh_left"].end) / unit
        self.assertAlmostEqual(doll.plan.length("doll", "shin_left"), shin - 1.0, places=2)
        self.assertAlmostEqual(doll.plan.length("doll", "thigh_left"), thigh, places=2)
        self.assertAlmostEqual(doll.drawn["shin_left"], shin - 1.0, places=2)
        self._frame()
        self.assertIs(self.game.global_view.bodies.characters[resident_id].plan, doll.plan)

    def test_a_drawing_left_half_done_can_be_gone_back_to_from_the_map(self) -> None:
        self._make_someone()
        self._key(pygame.K_ESCAPE)
        self.assertEqual(self.game.scene_name, "global")
        self.assertEqual(self.step, "draw_color")
        self._frame()
        hud = self.game.global_view.hud
        button = next(button for button in hud.buttons if button.intent == ("tutorial_draw",))
        self._click(button.rect.center)
        self.assertEqual(self.game.scene_name, "editor")

    def test_a_building_put_down_is_drawn_there_and_then_in_four_parts(self) -> None:
        self._make_someone()
        self._draw_someone()
        self._key(pygame.K_ESCAPE)
        self._key(pygame.K_u, "u")
        self._put_down("buildings", "shack", (20, 12))
        self.assertEqual(self.game.scene_name, "building_editor")
        self.assertEqual(self.step, "draw_parts")
        self._frame()
        editor = self.game.building_editor
        room_id = editor.room_id
        self._click(editor.part_buttons[1].rect.center)
        self.assertEqual(self.step, "draw_building")
        for part in editor.part_buttons:
            self._click(part.rect.center)
            self._click(self._button(editor, ("starter",)))
        self._frame()
        self._click(self._button(editor, ("save",)))
        self.assertEqual(self.step, "bed")
        self.assertEqual(len(list((self.drawings / "buildings" / room_id).glob("*.png"))), 4)
        # Out of the drawing is back to where the building was put down, to go on from there.
        self._key(pygame.K_ESCAPE)
        self.assertEqual(self.game.scene_name, "urbanism")
        self._frame()

    def test_furniture_put_down_is_drawn_once_for_all_of_its_kind(self) -> None:
        self._make_someone()
        settle(self.game.world, until="bed")
        self._key(pygame.K_ESCAPE)
        self._key(pygame.K_u, "u")
        self.assertEqual(self.game.scene_name, "urbanism")
        self._put_down("furniture", "bed", (10, 11))
        self.assertEqual(self.game.scene_name, "object_editor")
        self.assertEqual(self.step, "bed")
        self._frame()
        editor = self.game.object_editor
        self.assertEqual(editor.kind, "bed")
        self.assertEqual(editor.drawing.get_size(), (64, 128))
        self._click(self._button(editor, ("starter",)))
        self._click(editor.swatches[26][0].center)
        corner = (editor.area.x + 4 * editor.zoom, editor.area.y + 4 * editor.zoom)
        self._stroke(corner, (corner[0] + 20, corner[1] + 10))
        self.assertEqual(tuple(editor.drawing.get_at((4, 4)))[:3], editor.color)
        self._key(pygame.K_z, "z", pygame.KMOD_CTRL)
        self.assertNotEqual(tuple(editor.drawing.get_at((4, 4)))[:3], editor.color)
        self._stroke(corner, (corner[0] + 20, corner[1] + 10))
        self._frame()
        self._click(self._button(editor, ("save",)))
        self.assertEqual(self.step, "crate")
        self.assertTrue((self.drawings / "objects" / "bed.png").is_file())
        self._key(pygame.K_ESCAPE)
        self.assertEqual(self.game.scene_name, "urbanism")
        self._frame()

        # A second bed needs no drawing: it is the same bed.
        self.game.world.apply_command(PlaceObjectCommand("bed", (13, 11)))
        self._key(pygame.K_ESCAPE)
        self.assertEqual(self.game.scene_name, "global")
        view = self.game.global_view
        view.roofs_on = False
        self._frame()
        beds = [area for area, _ in view._drawn_objects(view.terrain.get_rect())]
        self.assertEqual(len(beds), 2)
        self.assertEqual({area.size for area in beds}, {(16, 32)})
        # Whatever nobody has drawn keeps the art it came with.
        barrel = next(placed for placed in self.game.world.interactables.values() if placed.kind == "barrel")
        self.assertIsNone(view.object_art.drawing(self.game.world.definition_of(barrel)))

    def test_what_is_put_down_outside_the_opening_is_only_drawn_when_asked(self) -> None:
        self._make_someone()
        settle(self.game.world)
        self.assertFalse(self.game.world.tutorial.active)
        self._key(pygame.K_ESCAPE)
        self._key(pygame.K_u, "u")
        # Tyres take no building: they are put down, as everything was during the opening.
        self._put_down("decor", "tyres", (30, 12))
        self.assertEqual(self.game.scene_name, "urbanism")
        editor = self.game.urbanism_editor
        self.assertEqual(editor.selection[0], "object")
        self._click(self._button(editor, ("art",)))
        self.assertEqual(self.game.scene_name, "object_editor")
        self.assertEqual(self.game.object_editor.kind, "tyres")
        self._frame()


if __name__ == "__main__":
    unittest.main()
