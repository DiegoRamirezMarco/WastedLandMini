import os
import tempfile
import unittest
from pathlib import Path

import pygame

from scenes.backdrop_editor import FOUND_NOTICE
from simulation.commands import PlanTripCommand
from simulation.world import SimulationWorld
from ui.outing_board import (
    CANCEL_INTENT,
    DRAW_INTENT,
    PLAN_INTENT,
    TRIPS_INTENT,
    OutingEntry,
    bar_marks,
    filled,
    more_intent,
    outing_buttons,
    provisions,
    traveller,
    travellers,
    trip_hours,
    zone_intent,
)

LINE = ["forest", "ruins", "summit", "plant", "crater"]


def _level(world: SimulationWorld, resident_id: str, level: int) -> None:
    resident = world.residents[resident_id]
    job = world.registries.jobs[resident.job_id]
    marks = world.registries.crafts.levels
    while world.crafts.level(world, resident, job.job_id) < level:
        world.crafts.worked(world, resident, job, max(1.0, marks[level - 1] - resident.trade.get(job.job_id, 0.0)))


class OutingBoardTests(unittest.TestCase):
    """What the board of trips works out, with no window."""

    def setUp(self) -> None:
        self.world = SimulationWorld.demo_world(seed=7)
        _level(self.world, "sergio", 3)
        self.entry = OutingEntry("sergio")

    def test_it_is_on_whoever_goes_out(self) -> None:
        self.assertEqual([resident.resident_id for resident in travellers(self.world)], ["sergio"])
        self.assertEqual(traveller(self.world, OutingEntry("marta")).resident_id, "sergio", "nobody else is sent")
        self.assertEqual(traveller(self.world, OutingEntry()).resident_id, "sergio")

    def test_as_far_as_a_zone_takes_what_it_takes_and_no_more(self) -> None:
        world = self.world
        there = dict(provisions(world, self.entry))
        self.assertIn("water", there)
        self.assertEqual(filled(world, self.entry, "forest"), {})
        for zone_id, needed in (("ruins", 2), ("summit", 5)):
            supplies = filled(world, self.entry, zone_id)
            self.assertEqual(sum(supplies.values()), needed)
            self.assertGreater(len(supplies), 1, "a little of each, and not all of one")
            self.assertEqual(world.expeditions.gets_to(world, world.residents["sergio"], supplies).zone_id, zone_id)
        self.assertGreater(trip_hours(world, world.residents["sergio"], "summit"), trip_hours(world, world.residents["sergio"], "forest") + 5)

    def test_what_was_handed_over_for_a_trip_made_ready_is_there_to_change(self) -> None:
        world = self.world
        water = dict(provisions(world, self.entry))["water"]
        world.apply_command(PlanTripCommand("sergio", "ruins", {"water": 3}))
        self.assertEqual(dict(provisions(world, self.entry))["water"], water)


class _Shell(unittest.TestCase):
    """The real game shell without a window, on the settlement that comes ready made."""

    def setUp(self) -> None:
        for variable in ("SDL_VIDEODRIVER", "SDL_AUDIODRIVER"):
            self.addCleanup(self._restore_driver, variable, os.environ.get(variable))
            os.environ[variable] = "dummy"
        from game.game import Game

        keep = tempfile.TemporaryDirectory()
        self.addCleanup(keep.cleanup)
        self.folder = Path(keep.name) / "illustrations"
        self.folder.mkdir()
        self.game = Game(illustrations_dir=self.folder, voices_dir=None, start_in_menu=False)
        self.addCleanup(pygame.quit)
        self.view, self.hud, self.world = self.game.global_view, self.game.global_view.hud, self.game.world
        self.sergio = self.world.residents["sergio"]

    @staticmethod
    def _restore_driver(variable: str, previous: str | None) -> None:
        if previous is None:
            os.environ.pop(variable, None)
        else:
            os.environ[variable] = previous

    def _press(self, intent) -> None:
        self.view.render()
        button = next(button for button in self.hud.buttons if button.intent == intent)
        self.view.click(button.rect.center)


class OutingScreenTests(_Shell):
    def test_a_button_in_the_corner_of_the_map_opens_the_board_over_it(self) -> None:
        self.assertFalse(self.hud.trips_open)
        self.view.render()
        button = self.hud.trips_button()
        self.assertTrue(self.hud.layout.map.contains(button.rect))
        self.assertTrue(self.hud.covers(button.rect.center), "a click on it does not fall through to the map")
        self.assertNotIn(TRIPS_INTENT, [entry.intent for entry in self.hud.menu], "the menu has no row to spare")
        # It is under whoever is out, and under whatever else is in that corner.
        while not self.sergio.away:
            self.world.step(1)
        self.world.events.drain()
        self.view.render()
        self.assertGreaterEqual(self.hud.trips_button().rect.top, self.hud.away_rect().bottom)
        # Inside a building that corner is the building's: the way out is there.
        self.view.come_back()
        room_id = next(room_id for room_id in self.world.rooms if self.view.enterable(room_id))
        self.assertTrue(self.view.enter(room_id))
        self.assertIsNone(self.hud.trips_button())
        self.view.click(self.view.interior.leave_button.rect.center)
        self.assertIsNone(self.view.inside)
        self.assertIsNotNone(self.hud.trips_button())
        del self.world.residents["sergio"]
        self.assertIsNone(self.hud.trips_button(), "with nobody to send there is nothing to open")
        self.setUp()
        self._press(TRIPS_INTENT)
        self.assertTrue(self.hud.trips_open)
        self.view.render()
        board = self.hud.trips_rect()
        self.assertTrue(self.hud.layout.map.contains(board))
        self.assertTrue(self.hud.covers(board.center), "a click on it does not fall through to the map")
        self.assertEqual(self.hud.outing.resident_id, "sergio")
        buttons = outing_buttons(self.view.font, board, self.world, self.hud.outing)
        self.assertTrue(all(board.contains(button.rect) for button in buttons))
        rects = [button.rect for button in buttons]
        self.assertEqual([rect.collidelistall(rects) for rect in rects], [[index] for index in range(len(rects))])
        self._press(TRIPS_INTENT)
        self.assertFalse(self.hud.trips_open)

    def test_only_as_far_as_they_know_the_way_can_be_pressed(self) -> None:
        self._press(TRIPS_INTENT)
        board = self.hud.trips_rect()

        def zones() -> list[str]:
            return [
                button.intent[1]
                for button in outing_buttons(self.view.font, board, self.world, self.hud.outing)
                if button.intent[0] == "trip_zone"
            ]

        self.assertEqual(zones(), ["forest"])
        _level(self.world, "sergio", 3)
        self.assertEqual(zones(), LINE[:3])
        bar, marks = bar_marks(board, self.world)
        self.assertEqual(marks, sorted(marks))
        self.assertEqual((marks[0], marks[-1]), (bar.x, bar.right - 1))

    def test_a_zone_pressed_fills_the_way_that_far_and_a_unit_more_or_less_moves_it(self) -> None:
        _level(self.world, "sergio", 3)
        self.world.events.drain()
        self.view.requested_backdrop_editor = None
        self._press(TRIPS_INTENT)
        self._press(zone_intent("summit"))
        entry = self.hud.outing
        self.assertEqual((entry.zone_id, sum(entry.supplies.values())), ("summit", 5))
        self._press(more_intent("water", -1))
        self.assertEqual(self.hud.outing.zone_id, "ruins", "one short of the mountain is as far as the city")
        self._press(more_intent("water", 1))
        self.assertEqual(self.hud.outing.zone_id, "summit")
        for _ in range(400):
            self.view._apply(more_intent("water", 1))
        there = dict(provisions(self.world, self.hud.outing))
        self.assertEqual(self.hud.outing.supplies["water"], there["water"], "no more than there is")
        self.assertEqual(self.hud.outing.zone_id, "summit", "and no further than they know the way")
        for _ in range(400):
            self.view._apply(more_intent("water", -1))
        self.assertEqual(self.hud.outing.supplies["water"], 0)

    def test_made_ready_it_leaves_the_stores_and_can_be_undone(self) -> None:
        _level(self.world, "sergio", 2)
        self.world.events.drain()
        self.view.requested_backdrop_editor = None
        water = self.world.giving.givable(self.world)["water"]
        self._press(TRIPS_INTENT)
        self._press(zone_intent("ruins"))
        taking = dict(self.hud.outing.supplies)
        self._press(PLAN_INTENT)
        self.assertEqual((self.sergio.outing.zone, self.sergio.outing.supplies), ("ruins", taking))
        self.assertEqual(self.world.giving.givable(self.world)["water"], water - taking.get("water", 0))
        self.assertIn("las ruinas de ciudad", self.hud.notice)
        self.assertEqual(self.hud.outing.zone_id, "ruins", "the board says what is made ready")
        self._press(CANCEL_INTENT)
        self.assertIsNone(self.sergio.outing)
        self.assertEqual(self.hud.outing.supplies, {})

    def test_a_trip_that_cannot_be_says_why(self) -> None:
        _level(self.world, "sergio", 2)
        self.world.events.drain()
        self._press(TRIPS_INTENT)
        self.hud.outing.zone_id = "ruins"
        self.view._apply(PLAN_INTENT)
        self.assertIsNone(self.sergio.outing)
        self.assertIn("no llega", self.hud.notice)


class ZoneFoundTests(_Shell):
    def test_a_zone_found_opens_where_it_is_named_and_drawn(self) -> None:
        from game.game import BACKDROP_SCENE

        _level(self.world, "sergio", 2)
        self.view.on_events(self.world.events.drain())
        self.assertEqual(self.view.requested_backdrop_editor, ("ruins", "sergio"))
        self.game.sync_scenes()
        editor = self.game.backdrop_editor
        self.assertEqual((self.game.scene_name, editor.zone), (BACKDROP_SCENE, "ruins"))
        self.assertEqual(editor.notice, FOUND_NOTICE)
        self.assertEqual(editor.naming, "", "its name is the first thing asked")
        for letter in "Villaescombro":
            self.game.handle_event(pygame.event.Event(pygame.KEYDOWN, key=ord(letter.lower()), mod=0, unicode=letter))
        self.assertIn("Villaescombro", editor._title())
        self.game.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN, mod=0, unicode="\\r"))
        self.assertIsNone(editor.naming)
        self.assertEqual(self.world.zones["ruins"].name, "Villaescombro")
        self.assertEqual(editor._title(), "Dibujar el fondo: Villaescombro")
        editor.render()
        # Its paper starts from the city the game has, to be drawn over or left.
        self.assertEqual(editor.guide_picture.get_size(), editor.plan.paper)
        self.game.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE, mod=0, unicode=""))
        self.game.sync_scenes()
        self.assertEqual(self.game.scene_name, "global")
        self.assertIsNone(self.view.found_zone)

    def test_escape_while_naming_leaves_the_name_and_not_the_paper(self) -> None:
        _level(self.world, "sergio", 2)
        self.view.on_events(self.world.events.drain())
        self.game.sync_scenes()
        editor = self.game.backdrop_editor
        self.game.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_x, mod=0, unicode="x"))
        self.game.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE, mod=0, unicode=""))
        self.assertIsNone(editor.naming)
        self.assertFalse(editor.closed)
        self.assertEqual(self.world.zones["ruins"].name, "")
        editor._apply(("name",))
        self.assertEqual(editor.naming, "")

    def test_a_known_zone_is_named_and_drawn_from_the_board(self) -> None:
        _level(self.world, "sergio", 2)
        self.world.events.drain()
        self._press(TRIPS_INTENT)
        self._press(zone_intent("ruins"))
        self._press(DRAW_INTENT)
        self.assertEqual(self.view.requested_backdrop_editor, ("ruins", "sergio"))
        self.game.sync_scenes()
        self.assertEqual(self.game.backdrop_editor.zone, "ruins")
        self.assertIsNone(self.game.backdrop_editor.naming, "it is not asked again")

    def test_the_trip_is_seen_going_through_each_zone_in_its_turn(self) -> None:
        _level(self.world, "sergio", 3)
        self.world.events.drain()
        self.assertTrue(self.world.apply_command(PlanTripCommand("sergio", "summit", {"water": 5})).ok)
        self.world.expeditions.set_out(self.world, self.sergio, self.world.registries.jobs["scavenger"])
        trip = self.sergio.expedition
        trip.find_at = None
        self.assertTrue(self.view.watch("sergio"))
        trips = self.view.expedition
        seen = []
        for share in (0.05, 0.6, 0.99):
            self.world.clock.day, self.world.clock.hour, self.world.clock.minute = 1, 0, 0
            minute = trip.left_at + round(trip.out_minutes * share)
            self.world.clock.hour, self.world.clock.minute = divmod(minute, 60)
            self.assertEqual(self.world.clock.total_minutes, minute)
            self.view.render()
            seen.append(trips.zone_id(self.sergio))
        self.assertEqual(seen, ["forest", "ruins", "summit"])
        from ui.labels import trip_ends, trip_lines

        self.assertEqual(trip_ends(self.world, self.sergio)[1], "La cima de la montaña")
        self.assertEqual(trip_lines(self.world, self.sergio)[0], "Sergio se aleja por la cima de la montaña")


if __name__ == "__main__":
    unittest.main()
