import os
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

import pygame

from audio.music import MOODS, MusicSettings
from graphics.body_renderer import FRAME_SIZE, BodyRenderer
from graphics.face_renderer import MARKER_SIZE
from graphics.lighting import NIGHT, STEPS, ambient, daylight
from graphics.shelf_display import displayed_goods
from scenes.body_stage import REMAINS_MINUTES
from scenes.hud import STORES_INTENT
from scenes.global_view import (
    MINIMAP_OFF,
    MINIMAP_ON,
    NOBODY_NEEDS_ATTENTION,
    ROOFS_OFF,
    SUGGESTION_REFUSED,
    ZOOM_TILE_SIZES,
)
from settings import GAME_MINUTES_PER_REAL_SECOND, SCALE, TILE_SIZE
from simulation.events.event import DomainEvent
from simulation.events.world_event import Upcoming, Weather
from simulation.health.injury import Injury
from simulation.residents.activity import Activity
from simulation.work.expedition import Expedition
from skeleton.character import Mode
from ui.inventory_view import condition_color
from ui.resident_panel import relationship_hitboxes, roster_rows
from ui.job_board import post_rows, suggest_buttons, suggest_intent
from ui.labels import (
    expression_of,
    relationship_rows,
    settlement_counts,
    settlement_stock,
    spoken_line,
    trait_names,
    affordable_goods,
    away_residents,
    condition_of,
    describe_action,
    describe_bond,
    describe_credits,
    describe_injuries,
    describe_job,
    describe_obstacle,
    describe_weather,
    format_time,
    has_shop,
    known_forecasts,
    price_at,
    price_label,
    selling_use,
    shop_goods,
)


class GameShellTests(unittest.TestCase):
    """Runs the real game shell without a window, through SDL's dummy video driver."""

    def setUp(self) -> None:
        # Neither a window nor a loudspeaker: both SDL drivers are the dummy ones.
        for variable in ("SDL_VIDEODRIVER", "SDL_AUDIODRIVER"):
            self.addCleanup(self._restore_driver, variable, os.environ.get(variable))
            os.environ[variable] = "dummy"
        from game.game import Game

        # Whatever pictures have been dropped into `illustrations/` are left out: these tests are about the game's own art.
        self.game = Game(illustrations_dir=None, voices_dir=None, start_in_menu=False)
        self.addCleanup(pygame.quit)

    @staticmethod
    def _restore_driver(variable: str, previous: str | None) -> None:
        if previous is None:
            os.environ.pop(variable, None)
        else:
            os.environ[variable] = previous

    def _minutes(self) -> int:
        clock = self.game.world.clock
        return (clock.day - 1) * 24 * 60 + clock.hour * 60 + clock.minute

    def test_the_game_fills_the_desktop_but_keeps_its_logical_resolution(self) -> None:
        from settings import SCREEN_HEIGHT, SCREEN_WIDTH

        self.assertEqual(self.game.screen.get_size(), (SCREEN_WIDTH, SCREEN_HEIGHT))
        self.assertEqual(pygame.display.get_window_size(), pygame.display.get_desktop_sizes()[0])

    def _look_into(self, room_id: str) -> None:
        """See into a building from the map, and draw the result.

        From the map a building is always shut (S40): the one way to see into it there is to
        have every roof off. The mouse is rested on it too, as somebody looking at it would.
        """
        view = self.game.global_view
        view.roofs_on = False
        room = self.game.world.rooms[room_id]
        x, y = view._tile_pixel(room.x + room.width / 2, room.y + 0.5)
        moved = pygame.event.Event(
            pygame.MOUSEMOTION, pos=(x * SCALE + 1, y * SCALE + 1), rel=(0, 0), buttons=(0, 0, 0)
        )
        view.handle_event(moved)
        view.render()

    def _play(self, seconds: float) -> None:
        for _ in range(round(seconds * 60)):
            self.game.advance_simulation(1 / 60)
            self.game.active_scene.render()

    def test_real_time_drives_game_time(self) -> None:
        start = self._minutes()
        self._play(10)
        self.assertAlmostEqual(self._minutes() - start, 10 * GAME_MINUTES_PER_REAL_SECOND, delta=1)

    def _make_everyone_get_along(self) -> None:
        """Remove the opening feud, so nothing important happens and the speed stays where it is put."""
        self.game.world.relationships.clear()
        self.game.world.residents["raul"].needs.stress = 0

    def test_speed_keys_scale_time_and_space_pauses(self) -> None:
        self._make_everyone_get_along()
        # The first minute of a settlement calls for attention by itself: it sets about choosing a government.
        self._play(1)
        self.game.handle_key(pygame.K_3)
        start = self._minutes()
        self._play(5)
        self.assertAlmostEqual(self._minutes() - start, 5 * GAME_MINUTES_PER_REAL_SECOND * 16, delta=16)

        self.game.handle_key(pygame.K_SPACE)
        paused_at = self._minutes()
        self._play(5)
        self.assertEqual(self._minutes(), paused_at)

        self.game.handle_key(pygame.K_SPACE)
        self._play(1)
        self.assertGreater(self._minutes(), paused_at)

    def test_time_stops_in_the_interaction_view(self) -> None:
        self.game.handle_key(pygame.K_TAB)
        self.assertEqual(self.game.scene_name, "interaction")
        start = self._minutes()
        self._play(5)
        self.assertEqual(self._minutes(), start)

    def test_a_full_day_renders_without_placeholders_being_needed(self) -> None:
        with self.assertNoLogs("graphics.assets", level="WARNING"):
            while self.game.world.clock.day < 2:
                # Crises slow the game down; speed it back up and let them resolve alone.
                self.game.handle_key(pygame.K_3)
                self._play(0.5)
            for scene in (self.game.global_view, self.game.interaction_view):
                scene.render()
        self.assertGreaterEqual(self.game.world.clock.day, 2)
        self.assertEqual(self.game.world.events.pending, [])


    # --- HUD ---

    def _click(self, canvas_position: tuple[int, int]) -> None:
        window = (canvas_position[0] * SCALE + 1, canvas_position[1] * SCALE + 1)
        scene = self.game.active_scene
        scene.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=window, button=1))
        # On the map a click is the button going down and coming up in the same place.
        scene.handle_event(pygame.event.Event(pygame.MOUSEBUTTONUP, pos=window, button=1))

    def test_buttons_pause_and_change_speed(self) -> None:
        hud = self.game.global_view.hud
        self._click(hud.speed_buttons[2].rect.center)
        self.assertEqual(self.game.world.clock.speed, 16)
        self._click(hud.pause_button.rect.center)
        self.assertTrue(self.game.world.clock.paused)
        self._click(hud.pause_button.rect.center)
        self.assertFalse(self.game.world.clock.paused)

    def test_clicking_a_resident_selects_them_and_empty_ground_deselects(self) -> None:
        view = self.game.global_view
        view.render()
        self._click(view.hitboxes["raul"].center)
        self.assertEqual(view.hud.selected_id, "raul")
        self.assertIsNotNone(view.hud.card_rect())
        view.render()
        card = view.hud.card_rect()
        self.assertEqual(card, view.hud.layout.panel)
        self._click((card.x + 20, card.y + 20))
        self.assertEqual(view.hud.selected_id, "raul", "a click on the card fell through to the map")
        self._click(view.viewport.center)
        self.assertIsNone(view.hud.selected_id)

    def test_log_opens_by_button_and_key_and_lists_events(self) -> None:
        view = self.game.global_view
        self._click(view.hud.log_button.rect.center)
        self.assertTrue(view.hud.log_open)
        view.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_l))
        self.assertFalse(view.hud.log_open)
        self.assertIsNone(view.hud.feed.latest())
        self.game.handle_key(pygame.K_3)
        self._play(8)
        latest = view.hud.feed.latest()
        self.assertIsNotNone(latest)
        self.assertGreater(latest.timestamp, 0)
        view.hud.log_open = True
        view.render()

    def test_important_events_mark_their_participants_until_the_exchange_ends(self) -> None:
        view, world = self.game.global_view, self.game.world
        marta, raul = world.residents["marta"], world.residents["raul"]
        marta.activity = Activity("argument", minutes_left=5, using=True, partner_id="raul")
        raul.activity = Activity("argument", minutes_left=5, using=True, partner_id="marta")
        self.assertEqual(view._status_icon(marta, resting=False), "argument")

        ambient = DomainEvent("argument_started", view.hud.intervention_from - 1, "x", ["marta", "raul"])
        view.on_events([ambient])
        self.assertEqual(view._status_icon(marta, resting=False), "argument")

        serious = DomainEvent("argument_started", view.hud.intervention_from, "x", ["marta", "raul"])
        view.on_events([serious])
        self.assertEqual(view._status_icon(marta, resting=False), "alert")
        self.assertIsNone(view._status_icon(world.residents["lucia"], resting=False))
        view.render()

        marta.activity = None
        self.assertIsNone(view._status_icon(marta, resting=False))
        self.assertNotIn("marta", view.alerts)

    def test_action_descriptions(self) -> None:
        world = self.game.world
        marta = world.residents["marta"]
        self.assertEqual(describe_action(world, marta), "sin hacer nada")
        marta.activity = Activity("talk", path=[(7, 9)], partner_id="raul")
        self.assertEqual(describe_action(world, marta), "va a hablar con Raúl")
        marta.activity = Activity("argument", minutes_left=5, using=True, partner_id="raul")
        self.assertEqual(describe_action(world, marta), "discute con Raúl")
        marta.activity = Activity("chat", minutes_left=5, using=True, partner_id="lucia")
        self.assertEqual(describe_action(world, marta), "charla con Lucía")
        marta.activity = Activity("eat", "pantry_1", path=[(7, 9)], minutes_left=20)
        self.assertEqual(describe_action(world, marta), "va hacia una despensa")
        marta.activity = Activity("eat", "pantry_1", minutes_left=20, using=True, item_id="canned_beans")
        self.assertEqual(describe_action(world, marta), "come unas judías en conserva")
        radio = world.containers["crate_dorm"].items[0]
        marta.activity = Activity("use_item", "crate_dorm", minutes_left=10, using=True, item_id=radio.instance_id)
        self.assertEqual(describe_action(world, marta), "pasa un rato con una radio vieja")
        marta.activity = Activity("steal", "crate_1", path=[(7, 9)], minutes_left=2, item_id="item_x")
        self.assertEqual(describe_action(world, marta), "trama algo")
        self.assertEqual(format_time(8 * 60 + 5), "08:05")
        self.assertEqual(format_time(24 * 60 + 61, with_day=True), "D2 01:01")


    # --- Interventions ---

    def _key(self, key: int) -> None:
        self.game.handle_key(key)
        self.game.active_scene.handle_event(pygame.event.Event(pygame.KEYDOWN, key=key))
        self.game.sync_scenes()

    def _open_raul_crisis(self) -> None:
        self._play(1.5)
        self.assertEqual([d.resident_id for d in self.game.world.decisions.values()], ["raul"])

    def test_a_crisis_drops_the_game_back_to_normal_speed(self) -> None:
        self.game.handle_key(pygame.K_3)
        self.assertEqual(self.game.world.clock.speed, 16)
        self._play(1)
        self.assertTrue(self.game.world.decisions)
        self.assertEqual(self.game.world.clock.speed, 1)

    def test_whoever_wants_advice_is_marked_and_clicking_them_opens_the_close_up(self) -> None:
        self._open_raul_crisis()
        view = self.game.global_view
        raul = self.game.world.residents["raul"]
        self.assertEqual(view._status_icon(raul, resting=False), "alert")
        self.assertIsNone(view._status_icon(self.game.world.residents["lucia"], resting=False))
        self._click(view.hitboxes["raul"].center)
        self.game.sync_scenes()
        self.assertEqual(self.game.scene_name, "interaction")
        self.assertEqual(self.game.interaction_view.decision.resident_id, "raul")
        self.game.active_scene.render()

    def test_advice_by_key_shows_what_the_resident_does_and_returns_to_the_settlement(self) -> None:
        self._open_raul_crisis()
        self._key(pygame.K_TAB)
        interaction = self.game.interaction_view
        self.assertEqual(self.game.scene_name, "interaction")
        self.assertEqual(len(interaction.buttons), 4)
        frozen = self._minutes()
        self._play(2)
        self.assertEqual(self._minutes(), frozen)

        self._key(pygame.K_4)
        self.assertEqual(self.game.world.decisions, {})
        self.assertIn("Dale, dale", interaction.result)
        self.assertEqual(interaction.expression, "angry")
        self.assertEqual(self.game.world.residents["raul"].activity.intent, "argument")
        self.game.active_scene.render()
        self._key(pygame.K_4)
        self.assertEqual(self.game.scene_name, "interaction", "a second option key must not do anything")

        self._key(pygame.K_SPACE)
        self.assertEqual(self.game.scene_name, "global")
        self.assertFalse(self.game.world.clock.paused, "SPACE closed the scene; it must not also pause")
        self._play(1)
        texts = [event.text for event in self.game.global_view.hud.feed.recent(5)]
        self.assertTrue(any("Dale, dale" in text for text in texts))

    def test_advice_by_click_works_too(self) -> None:
        self._open_raul_crisis()
        self._key(pygame.K_TAB)
        interaction = self.game.interaction_view
        self._click(interaction.buttons[0].rect.center)
        self.assertEqual(self.game.world.decisions, {})
        self.assertIn("Relájate", interaction.result)
        self._click((10, 10))
        self.game.sync_scenes()
        self.assertEqual(self.game.scene_name, "global")

    def test_the_close_up_with_nobody_waiting_says_so_and_closes(self) -> None:
        self._make_everyone_get_along()
        self._key(pygame.K_TAB)
        self.assertEqual(self.game.scene_name, "interaction")
        self.assertIsNone(self.game.interaction_view.decision)
        self.game.active_scene.render()
        self._key(pygame.K_TAB)
        self.assertEqual(self.game.scene_name, "global")


    # --- Objects, sound and saving ---

    def test_clicking_a_container_lists_what_is_inside_and_a_resident_replaces_it(self) -> None:
        view = self.game.global_view
        self._look_into("storehouse")
        self._click(view.container_hitboxes["pantry_1"].center)
        self.assertEqual((view.hud.selected_container, view.hud.selected_id), ("pantry_1", None))
        self.assertIsNotNone(view.hud.container_rect())
        view.render()
        self._click(view.hud.container_rect().center)
        self.assertEqual(view.hud.selected_container, "pantry_1", "a click on the panel fell through to the map")
        self._click(view.hitboxes["lucia"].center)
        self.assertEqual((view.hud.selected_container, view.hud.selected_id), (None, "lucia"))
        view.render()
        self._click((320, 300))
        self.assertEqual((view.hud.selected_container, view.hud.selected_id), (None, None))

    def test_the_campfire_flickers_while_time_runs_and_holds_still_when_paused(self) -> None:
        view = self.game.global_view
        campfire = self.game.world.interactables["campfire"]
        left, top = view._tile_pixel(campfire.x, campfire.y)
        area = pygame.Rect(left, top, 16, 16)

        def flames() -> bytes:
            view.render()
            return pygame.image.tobytes(view.canvas.subsurface(area), "RGB")

        seen = set()
        for _ in range(30):
            view.update(1 / 20)
            seen.add(flames())
        self.assertGreaterEqual(len(seen), 2)

        self.game.handle_key(pygame.K_SPACE)
        still = flames()
        for _ in range(30):
            view.update(1 / 20)
            self.assertEqual(flames(), still)

    def test_sound_follows_the_most_important_event_and_can_be_muted(self) -> None:
        audio = self.game.audio
        self.assertTrue(audio.available)
        quiet = DomainEvent("chat_started", 10, "x")
        loud = DomainEvent("crisis_opened", 55, "x")
        unknown = DomainEvent("something_new", 99, "x")
        self.assertEqual(audio.sound_for([quiet, loud, unknown]), "alert")
        self.assertIsNone(audio.sound_for([unknown]))
        self.assertTrue(audio.play("alert"))
        self.assertFalse(audio.play("alert"), "two sounds in the same instant")
        self.assertFalse(audio.play("no_such_sound"))

        self.game.handle_key(pygame.K_m)
        self.assertTrue(audio.muted)
        self.assertEqual(audio.on_events([loud]), "alert")
        self.game.handle_key(pygame.K_m)
        self.assertFalse(audio.muted)

    def test_the_music_follows_the_settlement_and_is_silenced_with_the_rest(self) -> None:
        self._make_everyone_get_along()
        audio, world = self.game.audio, self.game.world
        self.assertIsNone(audio.track)
        self.game.update_music()
        self.assertIsNone(audio.track, "the game comes with no music")
        # Given a track for each mood, it follows what is going on.
        self.game.music = MusicSettings(tracks={mood: mood for mood in MOODS})
        self.game.update_music()
        self.assertEqual(audio.track, "day")
        self.assertFalse(audio.set_music("day"), "the same track is not started again")
        world.clock.hour = 23
        self.game.update_music()
        self.assertEqual(audio.track, "night")
        world.weather = Weather("dust_storm", world.clock.total_minutes + 60)
        self.game.update_music()
        self.assertEqual(audio.track, "storm")
        self.game.handle_key(pygame.K_m)
        self.assertTrue(audio.muted)
        world.weather = None
        self.game.update_music()
        self.assertEqual(audio.track, "night", "muted, it still knows what it would be playing")
        self.game.handle_key(pygame.K_m)
        self.assertTrue(audio.set_music(None))
        self.assertIsNone(audio.track)
        self.assertTrue(audio.set_music("no_such_track"), "a track there is no file for is only silence")
        self.game.update_music()

    def test_saving_and_loading_bring_back_the_same_settlement(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "saves" / "quick.json"
            self.assertFalse(self.game.load_game(path))
            self._play(3)
            saved_at = self._minutes()
            radio_holder = self.game.world.containers["crate_dorm"].count("old_radio")
            self.assertTrue(self.game.save_game(path))
            self.assertTrue(path.is_file())

            self.game.handle_key(pygame.K_3)
            self._play(4)
            self.assertGreater(self._minutes(), saved_at)
            old_world = self.game.world
            self.assertTrue(self.game.load_game(path))
            self.assertIsNot(self.game.world, old_world)
            self.assertEqual(self._minutes(), saved_at)
            self.assertEqual(self.game.world.containers["crate_dorm"].count("old_radio"), radio_holder)
            self.assertIs(self.game.global_view.world, self.game.world)
            self.assertIs(self.game.interaction_view.world, self.game.world)
            self._play(2)
            self.assertGreater(self._minutes(), saved_at)

            path.write_text("{ broken", encoding="utf-8")
            world = self.game.world
            with self.assertLogs("game.game", level="WARNING"):
                self.assertFalse(self.game.load_game(path))
            self.assertIs(self.game.world, world, "a broken save must leave the current game alone")
            self.game.active_scene.render()

    def test_someone_eating_shows_what_they_eat(self) -> None:
        view, world = self.game.global_view, self.game.world
        marta = world.residents["marta"]
        self.assertIsNone(view._item_in_hand(marta))
        marta.activity = Activity("eat", "pantry_1", minutes_left=20, using=True, item_id="canned_beans")
        self.assertEqual(view._item_in_hand(marta), "canned_beans")
        lucia = world.residents["lucia"]
        toy = lucia.inventory.items[0]
        lucia.activity = Activity("use_item", minutes_left=10, using=True, item_id=toy.instance_id)
        self.assertEqual(view._item_in_hand(lucia), "peluche_maligno")
        view.hud.select_resident("lucia")
        with self.assertNoLogs("graphics.assets", level="WARNING"):
            view.render()


    # --- A settlement bigger than the screen ---

    def test_the_view_scrolls_over_the_map_and_stops_at_its_edges(self) -> None:
        view = self.game.global_view
        self.assertGreater(view.terrain.get_width(), view.viewport.width)
        self.assertGreater(view.terrain.get_height(), view.viewport.height)
        view.scroll(-10_000, -10_000)
        self.assertEqual(view.camera, [0.0, 0.0])
        view.scroll(10_000, 10_000)
        self.assertEqual(view.camera[0], view.terrain.get_width() - view.viewport.width)
        self.assertEqual(view.camera[1], view.terrain.get_height() - view.viewport.height)
        view.render()

    def test_centring_puts_a_tile_in_the_middle_of_the_view(self) -> None:
        view = self.game.global_view
        view.centre_on((30, 18))
        left, top = view._tile_pixel(30, 18)
        self.assertLess(abs(left - view.viewport.centerx), 2)
        self.assertLess(abs(top - view.viewport.centery), 2)

    def test_residents_are_picked_where_they_are_drawn_after_scrolling(self) -> None:
        view = self.game.global_view
        tomas = self.game.world.residents["tomas"]
        view.render()
        self.assertFalse(view.viewport.contains(view.hitboxes["tomas"]), "Tomás starts outside the first view")
        self._click(view.hitboxes["tomas"].center)
        self.assertIsNone(view.hud.selected_id, "nothing outside the view can be clicked")

        view.centre_on_resident("tomas")
        view.render()
        self.assertTrue(view.viewport.contains(view.hitboxes["tomas"]))
        self._click(view.hitboxes["tomas"].center)
        self.assertEqual(view.hud.selected_id, "tomas")
        self.assertEqual((tomas.x, tomas.y), self.game.world.registries.maps["settlement"].spawns[3])

    def test_dragging_with_the_right_button_moves_the_map(self) -> None:
        view = self.game.global_view
        view.scroll(-10_000, -10_000)
        drag = pygame.event.Event(pygame.MOUSEMOTION, pos=(400, 300), rel=(-80, -40), buttons=(0, 0, 1))
        view.handle_event(drag)
        self.assertEqual(view.camera, [80 / SCALE, 40 / SCALE])
        hover = pygame.event.Event(pygame.MOUSEMOTION, pos=(400, 300), rel=(-80, -40), buttons=(0, 0, 0))
        view.handle_event(hover)
        self.assertEqual(view.camera, [80 / SCALE, 40 / SCALE])

    def _drag(self, start: tuple[int, int], end: tuple[int, int], steps: int = 4) -> None:
        """Press the left button at a canvas position, move the mouse to another, and let go."""
        view = self.game.global_view
        window = lambda position: (position[0] * SCALE, position[1] * SCALE)
        view.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=window(start), button=1))
        last = start
        for step in range(1, steps + 1):
            at = (start[0] + (end[0] - start[0]) * step // steps, start[1] + (end[1] - start[1]) * step // steps)
            rel = ((at[0] - last[0]) * SCALE, (at[1] - last[1]) * SCALE)
            view.handle_event(pygame.event.Event(pygame.MOUSEMOTION, pos=window(at), rel=rel, buttons=(1, 0, 0)))
            last = at
        view.handle_event(pygame.event.Event(pygame.MOUSEBUTTONUP, pos=window(end), button=1))

    def test_dragging_with_the_left_button_moves_the_map_and_clicks_on_nothing(self) -> None:
        view = self.game.global_view
        view.centre_on_resident("raul")
        view.render()
        on_raul = view.hitboxes["raul"].center
        before = list(view.camera)
        # Pressed on a resident and pulled away: the map comes along, and nobody is selected.
        self._drag(on_raul, (on_raul[0] - 60, on_raul[1] - 30))
        self.assertEqual(view.camera, [before[0] + 60, before[1] + 30])
        self.assertIsNone(view.hud.selected_id)
        # The mouse may go on over the menu: the map still follows it until the button comes up.
        self._drag(on_raul, (view.viewport.left - 30, on_raul[1]))
        self.assertEqual(view.camera[0], before[0] + 60 + (on_raul[0] - view.viewport.left + 30))
        # With the button up again, moving the mouse moves nothing.
        still = list(view.camera)
        view.handle_event(pygame.event.Event(pygame.MOUSEMOTION, pos=(400, 300), rel=(-80, -40), buttons=(0, 0, 0)))
        self.assertEqual(view.camera, still)
        # A hand that shakes a little is still clicking.
        view.centre_on_resident("raul")
        view.render()
        still = list(view.camera)
        on_raul = view.hitboxes["raul"].center
        self._drag(on_raul, (on_raul[0] + 2, on_raul[1] + 1), steps=1)
        self.assertEqual(view.camera, still)
        self.assertEqual(view.hud.selected_id, "raul")
        # Zoomed in, the map still keeps under the mouse: it moves half as many of its own pixels.
        view.hud.select_resident(None)
        view.set_zoom(2)
        zoomed = list(view.camera)
        self._drag((300, 200), (340, 200))
        self.assertEqual(view.camera, [zoomed[0] - 20, zoomed[1]])

    def test_a_press_on_a_button_or_the_minimap_acts_at_once_and_drags_nothing(self) -> None:
        view, hud = self.game.global_view, self.game.global_view.hud
        view.render()
        minimap = hud.minimap_rect
        view.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=(minimap.right * SCALE - 4, minimap.bottom * SCALE - 4), button=1))
        moved = list(view.camera)
        self.assertNotEqual(moved, [0.0, 0.0])
        view.handle_event(pygame.event.Event(pygame.MOUSEMOTION, pos=(600, 300), rel=(200, 0), buttons=(1, 0, 0)))
        self.assertEqual(view.camera, moved)

    def test_the_view_follows_whoever_is_selected_until_it_is_moved_by_hand(self) -> None:
        view, world = self.game.global_view, self.game.world
        world.clock.paused = True
        tomas = world.residents["tomas"]
        # In the middle of the map, where the view can have him in its middle.
        tomas.x, tomas.y, tomas.trail, tomas.activity = 30, 18, [], None

        def off_centre() -> float:
            view.render()
            box = view.hitboxes["tomas"]
            return max(abs(box.centerx - view.viewport.centerx), abs(box.bottom - view.tile_px // 2 - view.viewport.centery))

        view.centre_on_resident("tomas")
        view.scroll(40, 24)
        self.assertGreater(off_centre(), 20)
        view.update(0.05)
        self.assertIsNone(view.following, "with nobody selected the view stays where it is put")
        self.assertGreater(off_centre(), 20)
        # Selected with a click, he is brought to the middle, smoothly and not in one jump.
        self._click(view.hitboxes["tomas"].center)
        view.update(0.02)
        self.assertEqual(view.following, "tomas")
        self.assertGreater(off_centre(), 4)
        for _ in range(60):
            view.update(0.02)
        self.assertLess(off_centre(), 3)
        # He walks off, and the view goes with him, part-way through a step as well.
        tomas.trail = [(tomas.x, tomas.y), (tomas.x + 1, tomas.y), (tomas.x + 2, tomas.y), (tomas.x + 3, tomas.y)]
        tomas.x += 3
        before = view.camera[0]
        view.tick_progress = 0.5
        view.update(0.02)
        for _ in range(60):
            view.update(0.02)
        self.assertAlmostEqual(view.camera[0], before + 1.5 * TILE_SIZE, delta=1.0)
        view.tick_progress = 1.0
        for _ in range(60):
            view.update(0.02)
        self.assertAlmostEqual(view.camera[0], before + 3 * TILE_SIZE, delta=1.0)
        self.assertLess(off_centre(), 3)
        # Zooming keeps him in the middle.
        view.set_zoom(2, (view.viewport.left + 10, view.viewport.top + 10))
        for _ in range(60):
            view.update(0.02)
        self.assertLess(off_centre(), 7)
        view.set_zoom(1)
        # Moved by hand, the view lets go of him, though he is still selected.
        view.handle_event(pygame.event.Event(pygame.MOUSEMOTION, pos=(400, 300), rel=(-80, -40), buttons=(0, 0, 1)))
        self.assertIsNone(view.following)
        for _ in range(30):
            view.update(0.02)
        self.assertEqual(view.hud.selected_id, "tomas")
        self.assertGreater(off_centre(), 20)
        # Dragging with the left button lets go as well, and C takes him up again.
        view.following = "tomas"
        self._drag((300, 200), (330, 200))
        self.assertIsNone(view.following)
        view.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_c))
        self.assertEqual(view.following, "tomas")
        self.assertLess(off_centre(), 3)
        # Someone else selected from the list is the one followed from then on.
        view.hud.select_resident("raul")
        view.update(0.02)
        self.assertEqual(view.following, "raul")
        # Someone away on an expedition is nowhere to follow: the view stays put.
        tomas.expedition = Expedition(returns_at=world.clock.total_minutes + 60, finds=0, danger=0.0)
        self.assertTrue(tomas.away)
        view.hud.select_resident("tomas")
        resting = None
        for _ in range(10):
            view.update(0.02)
            resting, moved = list(view.camera), resting
        self.assertEqual(resting, moved)

    def test_whoever_asks_for_advice_does_not_take_the_view_off_someone_being_followed(self) -> None:
        view = self.game.global_view
        view.hud.select_resident("tomas")
        view.centre_on_resident("tomas")
        view.update(0.02)
        self.assertEqual(view.following, "tomas")
        there = list(view.camera)
        self._open_raul_crisis()
        self.assertEqual(view.camera, there)

    def test_someone_asking_for_advice_is_brought_into_view(self) -> None:
        view = self.game.global_view
        view.scroll(10_000, 10_000)
        self._open_raul_crisis()
        view.render()
        self.assertTrue(view.viewport.contains(view.hitboxes["raul"]))

    def test_workers_on_duty_are_marked_and_the_card_names_their_job(self) -> None:
        view, world = self.game.global_view, self.game.world
        marta = world.residents["marta"]
        self.assertEqual(describe_job(world, marta), "Trabajo: Cocina (11-14, 18-21)")
        marta.activity = Activity("work", "cooking_pot", path=[(7, 9)])
        self.assertEqual(describe_action(world, marta), "va a trabajar: cocina")
        self.assertIsNone(view._status_icon(marta, resting=False))
        marta.activity = Activity("work", "cooking_pot", minutes_left=60, using=True)
        self.assertEqual(describe_action(world, marta), "trabajando: cocina")
        self.assertEqual(view._status_icon(marta, resting=False), "work")
        marta.job_id = None
        self.assertEqual(describe_job(world, marta), "Sin trabajo")
        view.hud.select_resident("marta")
        view.centre_on_resident("marta")
        with self.assertNoLogs("graphics.assets", level="WARNING"):
            view.render()


    # --- Zoom ---

    def _wheel(self, notches: int) -> None:
        self.game.active_scene.handle_event(pygame.event.Event(pygame.MOUSEWHEEL, x=0, y=notches))

    def _press(self, key: int) -> None:
        self.game.active_scene.handle_event(pygame.event.Event(pygame.KEYDOWN, key=key))

    def test_the_wheel_the_keys_and_the_buttons_zoom_and_stop_at_both_ends(self) -> None:
        view = self.game.global_view
        self.assertEqual(view.tile_px, TILE_SIZE)
        self._wheel(1)
        self.assertEqual(view.tile_px, TILE_SIZE * 2)
        for _ in range(10):
            self._wheel(1)
        self.assertEqual(view.tile_px, ZOOM_TILE_SIZES[-1])
        self._wheel(-1)
        self.assertEqual(view.tile_px, ZOOM_TILE_SIZES[-2])

        self._press(pygame.K_PLUS)
        self.assertEqual(view.tile_px, ZOOM_TILE_SIZES[-1])
        for _ in range(10):
            self._press(pygame.K_MINUS)
        self.assertEqual(view.tile_px, ZOOM_TILE_SIZES[0])
        self.assertTrue(view.overview)

        zoom_out, zoom_in = view.hud.zoom_buttons
        self._click(zoom_in.rect.center)
        self.assertEqual(view.tile_px, ZOOM_TILE_SIZES[1])
        self._click(zoom_out.rect.center)
        self._click(zoom_out.rect.center)
        self.assertTrue(view.overview)

    def test_zooming_keeps_the_place_under_the_mouse_where_it_is(self) -> None:
        view = self.game.global_view
        view.centre_on((30, 18))
        view.set_zoom(view.zoom + 1)
        left, top = view._tile_pixel(30, 18)
        self.assertLess(abs(left - view.viewport.centerx), 2)
        self.assertLess(abs(top - view.viewport.centery), 2)
        self.assertEqual(view._tile_pixel(31, 18)[0] - left, TILE_SIZE * 2)

        anchor = view._tile_pixel(33, 16)
        self.assertTrue(view.viewport.collidepoint(anchor))
        for zoom in (3, 2, 1, 2):
            view.set_zoom(zoom, anchor)
            left, top = view._tile_pixel(33, 16)
            self.assertLess(abs(left - anchor[0]), ZOOM_TILE_SIZES[zoom] // TILE_SIZE + 1, zoom)
            self.assertLess(abs(top - anchor[1]), ZOOM_TILE_SIZES[zoom] // TILE_SIZE + 1, zoom)

    def test_the_view_still_stops_at_the_edges_of_the_map_when_zoomed_in(self) -> None:
        view, tile_map = self.game.global_view, self.game.world.tile_map
        for zoom in range(1, len(ZOOM_TILE_SIZES)):
            view.set_zoom(zoom)
            view.scroll(-10_000, -10_000)
            self.assertEqual(view._tile_pixel(0, 0), view.viewport.topleft, zoom)
            view.scroll(10_000, 10_000)
            right, bottom = view._tile_pixel(tile_map.width, tile_map.height)
            # No more than one map pixel of the last tile is left off the canvas.
            self.assertIn(right - view.viewport.right, range(view.tile_px // TILE_SIZE + 1), zoom)
            self.assertIn(bottom - view.viewport.bottom, range(view.tile_px // TILE_SIZE + 1), zoom)

    def test_residents_are_drawn_and_picked_at_every_zoom(self) -> None:
        view = self.game.global_view
        for zoom, tile_px in enumerate(ZOOM_TILE_SIZES):
            view.set_zoom(zoom)
            view.centre_on_resident("raul")
            view.hud.select_resident(None)
            with self.assertNoLogs("graphics.assets", level="WARNING"):
                view.render()
            hitbox = view.hitboxes["raul"]
            self.assertTrue(view.viewport.contains(hitbox), zoom)
            if not view.overview:
                scale = tile_px // TILE_SIZE
                self.assertEqual(hitbox.size, (FRAME_SIZE[0] * scale, FRAME_SIZE[1] * scale))
            self._click(hitbox.center)
            self.assertEqual(view.hud.selected_id, "raul", zoom)

    def test_from_afar_the_whole_settlement_shows_with_roofs_on_and_a_face_per_resident(self) -> None:
        view, world = self.game.global_view, self.game.world
        self._look_into("dormitory")
        self.assertIn("crate_dorm", view.container_hitboxes)
        # Someone indoors is found from afar all the same.
        marta = world.residents["marta"]
        marta.x, marta.y = world.rooms["dormitory"].x, world.rooms["dormitory"].y + 1
        marta.trail = []

        view.set_zoom(0)
        with self.assertNoLogs("graphics.assets", level="WARNING"):
            view.render()
        settlement = pygame.Rect(view._tile_pixel(0, 0), (0, 0))
        settlement.union_ip(pygame.Rect(view._tile_pixel(world.tile_map.width, world.tile_map.height), (0, 0)))
        self.assertTrue(view.viewport.contains(settlement))
        self.assertEqual(settlement.center, view.viewport.center)
        for resident_id in world.residents:
            self.assertEqual(view.hitboxes[resident_id].size, MARKER_SIZE, resident_id)
        self.assertIn((marta.x, marta.y), view.roofs)
        self.assertTrue(view.hitboxes["marta"].collidepoint(view._tile_pixel(marta.x + 0.5, marta.y + 0.5)))
        self._click(view.hitboxes["marta"].center)
        self.assertEqual(view.hud.selected_id, "marta")
        # What a roof hides cannot be clicked through it.
        self.assertNotIn("crate_dorm", view.container_hitboxes)

        # Pointing at a place and zooming in goes there.
        target = view.hitboxes["marta"].center
        view.set_zoom(1, target)
        view.render()
        self.assertTrue(view.viewport.contains(view.hitboxes["marta"]))
        self.assertIn("crate_dorm", view.container_hitboxes)


    # --- Health, fights and death on screen ---

    def test_the_injured_are_marked_and_their_card_says_what_ails_them(self) -> None:
        view, world = self.game.global_view, self.game.world
        ines = world.residents["ines"]
        self.assertIsNone(view._status_icon(ines, resting=False))
        self.assertEqual(describe_injuries(world, ines), "Sin heridas")
        ines.injuries = [Injury("bruise", 10), Injury("cut", 30)]
        self.assertEqual(view._status_icon(ines, resting=False), "hurt")
        self.assertEqual(describe_injuries(world, ines), "Heridas: un corte, moratones")
        view.hud.select_resident("ines")
        view.centre_on_resident("ines")
        with self.assertNoLogs("graphics.assets", level="WARNING"):
            view.render()

    def test_a_fight_about_to_start_is_put_to_the_player_like_any_crisis(self) -> None:
        self._make_everyone_get_along()
        world = self.game.world
        raul, marta = world.residents["raul"], world.residents["marta"]
        world.relationship("raul", "marta").resentment = 90
        world.relationship("marta", "raul").resentment = 90
        for _ in range(200):
            activity = world.interventions.maybe_brawl(world, raul, marta)
            if activity is not None:
                raul.activity = activity
                break
        self.assertEqual([d.kind for d in world.decisions.values()], ["brawl"])
        self.assertEqual(self.game.global_view._status_icon(raul, resting=False), "alert")

        self._key(pygame.K_TAB)
        interaction = self.game.interaction_view
        self.assertEqual(self.game.scene_name, "interaction")
        self.assertEqual(len(interaction.buttons), 4)
        self.game.active_scene.render()
        self._key(pygame.K_1)
        self.assertEqual(world.decisions, {})
        self.assertIn("se da la vuelta", interaction.result)
        self.assertEqual(interaction.expression, "sad")
        self.game.active_scene.render()

    # --- Work, credits and changing jobs ---

    def test_errands_repairs_credits_and_days_off_are_put_into_words(self) -> None:
        view, world = self.game.global_view, self.game.world
        raul, lucia = world.residents["raul"], world.residents["lucia"]
        self.assertEqual(describe_credits(world, lucia), "6 vales")
        lucia.credits = 1.9
        self.assertEqual(describe_credits(world, lucia), "1 vale")
        lucia.activity = Activity("haul", "pantry_1", path=[(7, 9)], minutes_left=2)
        self.assertEqual(describe_action(world, lucia), "acarrea para su puesto")
        lucia.activity = Activity("haul", "pantry_1", minutes_left=2, using=True)
        self.assertEqual(describe_action(world, lucia), "carga y descarga")
        hoe = raul.inventory.stack_of("hoe", "raul")
        raul.activity = Activity("repair", "workbench", minutes_left=30, using=True, item_id=hoe.instance_id)
        self.assertEqual(describe_action(world, raul), "lleva una azada a arreglar")
        self.assertEqual(view._item_in_hand(raul), "hoe")
        raul.activity = Activity("shop", "shop_counter", minutes_left=5, using=True, item_id="canned_beans")
        self.assertEqual(describe_action(world, raul), "compra unas judías en conserva en la tienda")
        world.clock.day = 2
        self.assertEqual(describe_job(world, lucia), "Trabajo: Cantina (hoy libra)")
        for resident_id in ("raul", "lucia"):
            view.hud.select_resident(resident_id)
            view.centre_on_resident(resident_id)
            with self.assertNoLogs("graphics.assets", level="WARNING"):
                view.render()

    def test_a_vacant_post_is_put_to_the_player_like_any_other_decision(self) -> None:
        self._make_everyone_get_along()
        world = self.game.world
        marta = world.residents["marta"]
        marta.job_id = marta.post_id = None
        world.vacancies["cook"] = world.clock.total_minutes - 30 * 60
        marta.activity = world.interventions.maybe_offer_job(world, marta)
        self.assertEqual([d.job_id for d in world.decisions.values()], ["cook"])
        self.assertEqual(self.game.global_view._status_icon(marta, resting=False), "alert")
        self._key(pygame.K_TAB)
        interaction = self.game.interaction_view
        self.assertEqual(self.game.scene_name, "interaction")
        self.assertEqual(interaction.expression, "neutral")
        self.assertEqual([button.intent for button in interaction.buttons], ["encourage", "neutral", "discourage"])
        self.assertIn("Cocina", interaction.decision.prompt)
        self.assertIn("Cocina", interaction._leaning_text(interaction.decision, "Marta", ""))
        self.game.active_scene.render()
        self._key(pygame.K_1)
        self.assertEqual(world.decisions, {})
        self.assertIn("Hazlo, hace falta", interaction.result)
        self.assertEqual(interaction.expression, "happy")
        self.assertEqual((marta.job_id, marta.post_id), ("cook", "cooking_pot"))
        self.game.active_scene.render()

    # --- The economy on screen ---

    def test_the_job_board_lists_every_post_and_says_which_stand_empty(self) -> None:
        self._make_everyone_get_along()
        view, world = self.game.global_view, self.game.world
        hud = view.hud
        self._click(hud.jobs_button.rect.center)
        self.assertTrue(hud.jobs_open)
        self._click(hud.log_button.rect.center)
        self.assertEqual((hud.jobs_open, hud.log_open), (False, True), "the two share a corner of the screen")
        view.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_j))
        self.assertEqual((hud.jobs_open, hud.log_open), (True, False))

        rows = {row.job_id: row for row in post_rows(world, None)}
        self.assertEqual(
            list(rows),
            ["water_carrier", "farmer", "cook", "medic", "guard", "scavenger", "mechanic", "shopkeeper", "bartender"],
            "most missed first",
        )
        self.assertEqual((rows["farmer"].title, rows["farmer"].holders), ("Huerto (8-13, 15-18)", "Raúl, Inés"))
        # Every post is held but the water, which nobody draws when a settlement starts.
        self.assertEqual([job_id for job_id, row in rows.items() if row.vacant], ["water_carrier"])
        self.assertFalse(any(row.can_suggest for row in rows.values()), "with nobody selected there is nobody to ask")

        world.health.die(world, world.residents["marta"], "una prueba")
        world.step(3 * 60)
        rows = {row.job_id: row for row in post_rows(world, "lucia")}
        self.assertTrue(rows["cook"].vacant)
        self.assertEqual(rows["cook"].holders, "nadie · vacante hace 2 h")
        can = {job_id for job_id, row in rows.items() if row.can_suggest}
        self.assertEqual(can, {"water_carrier", "farmer", "cook"}, "only where a post is free, and never her own")
        world.clock.day = 2
        self.assertEqual(post_rows(world, None)[-1].holders, "Lucía (libra)")
        hud.select_resident("lucia")
        with self.assertNoLogs("graphics.assets", level="WARNING"):
            view.render()

    def test_proposing_a_post_from_the_board_asks_the_resident_and_shows_their_answer(self) -> None:
        self._make_everyone_get_along()
        view, world = self.game.global_view, self.game.world
        hud, lucia = view.hud, world.residents["lucia"]
        hud.toggle_jobs()
        self.assertEqual(suggest_buttons(view.font, hud.jobs_rect(), world, hud.selected_id), [])
        hud.select_resident("lucia")
        view.render()
        buttons = {button.intent: button for button in suggest_buttons(view.font, hud.jobs_rect(), world, "lucia")}
        # Two posts stand free: the water nobody draws yet, and the second plot of the garden.
        self.assertEqual(list(buttons), [suggest_intent("water_carrier"), suggest_intent("farmer")])
        self._click(buttons[suggest_intent("farmer")].rect.center)
        self.assertEqual((lucia.job_id, lucia.post_id), ("farmer", "crop_2"))
        self.assertEqual(hud.notice, "Lucía decide hacerse cargo del puesto: Huerto")
        self.assertEqual(hud.selected_id, "lucia", "a click on the board fell through to the map")

        # The bar she left has a free post now, but she has only just been asked, and the board says so.
        view.render()
        self.assertEqual(suggest_buttons(view.font, hud.jobs_rect(), world, "lucia"), [])
        rows = {row.job_id: row for row in post_rows(world, "lucia")}
        self.assertEqual(rows["bartender"].obstacle, "se lo preguntaron hace poco")
        self.assertEqual(rows["farmer"].obstacle, "ya es su puesto")
        self.assertEqual(rows["guard"].obstacle, "sin puesto libre")
        self.assertEqual({row.obstacle for row in post_rows(world, None)}, {""}, "with nobody picked, no reasons")
        self.assertFalse(hud.jobs_rect().colliderect(hud.minimap_rect), "the board leaves the minimap in view")
        view._suggest_job("bartender")
        self.assertEqual(lucia.job_id, "farmer")
        self.assertEqual(hud.notice, SUGGESTION_REFUSED)
        self._play(1)
        texts = [event.text for event in hud.feed.recent(10)]
        self.assertTrue(any("Lucía cambia de puesto: de Cantina a Huerto" in text for text in texts))

    def test_the_counter_shows_prices_and_the_card_what_a_resident_can_afford(self) -> None:
        view, world = self.game.global_view, self.game.world
        lucia = world.residents["lucia"]
        self.assertTrue(has_shop(world))
        self.assertIsNone(selling_use(world, "pantry_1"))
        self.assertIsNotNone(selling_use(world, "shop_counter"))
        counter = world.containers["shop_counter"]
        beans = counter.stack_of("canned_beans", None)
        self.assertEqual(price_at(world, "shop_counter", beans), 11)
        self.assertEqual(shop_goods(world)[:2], [("canned_beans", 11), ("hoe", 18)])
        self.assertEqual(affordable_goods(world, lucia), [], "six credits buy nothing there")
        lucia.credits = 20.0
        self.assertEqual(affordable_goods(world, lucia), ["canned_beans", "hoe"])
        beans.quantity = 1
        self.assertEqual(price_at(world, "shop_counter", beans), 20, "the last tin is dear")
        self.assertEqual(affordable_goods(world, lucia), ["hoe", "canned_beans"])
        self.assertEqual(price_label(world, "shop_counter", beans), "20 vales")
        self.assertEqual(describe_credits(world, lucia), "20 vales")
        world.trading.in_use = False
        self.assertIsNone(price_label(world, "shop_counter", beans), "under barter nothing has a price")
        self.assertEqual(describe_credits(world, lucia), "Trueque: sin moneda")
        lucia.inventory.items.clear()
        self.assertEqual(affordable_goods(world, lucia), [], "with nothing of her own there is nothing to be had")
        world.stock(lucia.inventory, "hoe", 1, "lucia")
        lucia.needs.hunger = 95
        self.assertIn("canned_beans", affordable_goods(world, lucia))
        for shown in (("shop_counter", None), (None, "lucia")):
            view.hud.selected_container, view.hud.selected_id = shown
            self.game.active_scene.render()
        del world.containers["shop_counter"]
        self.assertFalse(has_shop(world))
        world.containers["shop_counter"] = counter
        for select, target in ((view.hud.select_container, "shop_counter"), (view.hud.select_resident, "lucia")):
            select(target)
            with self.assertNoLogs("graphics.assets", level="WARNING"):
                view.render()

    def test_things_that_wear_out_show_the_state_they_are_in(self) -> None:
        view, world = self.game.global_view, self.game.world
        raul, lucia = world.residents["raul"], world.residents["lucia"]
        hoe = raul.inventory.stack_of("hoe", "raul")
        self.assertEqual(condition_of(world, hoe), 100.0)
        self.assertIsNone(condition_of(world, lucia.inventory.items[0]), "a toy never wears out")
        self.assertEqual([condition_color(value) for value in (80.0, 30.0, 5.0)], ["lichen", "lamp", "ember"])
        view.hud.select_resident("raul")
        view.render()
        card = view.hud.card_rect()
        sound = pygame.image.tobytes(self.game.canvas.subsurface(card), "RGB")
        hoe.condition = 10.0
        view.render()
        self.assertNotEqual(pygame.image.tobytes(self.game.canvas.subsurface(card), "RGB"), sound)
        hoe.condition = -3.0
        self.assertEqual(condition_of(world, hoe), 0.0)

    def test_a_load_is_seen_in_the_hands_that_carry_it(self) -> None:
        view, world = self.game.global_view, self.game.world
        raul = world.residents["raul"]
        self.assertIsNone(view._load_of(raul), "his own hoe is not a load")
        view.centre_on_resident("raul")
        view.render()
        body = view.hitboxes["raul"].copy()
        empty_handed = pygame.image.tobytes(self.game.canvas.subsurface(body), "RGB")
        world.stock(raul.inventory, "vegetables", 4, None)
        self.assertEqual(view._load_of(raul), "vegetables")
        with self.assertNoLogs("graphics.assets", level="WARNING"):
            view.render()
        self.assertNotEqual(pygame.image.tobytes(self.game.canvas.subsurface(body), "RGB"), empty_handed)

    def test_the_shop_shelves_show_the_stock_and_empty_as_it_sells(self) -> None:
        view, world = self.game.global_view, self.game.world
        shelves = [world.interactables["shop_shelf_1"], world.interactables["shop_shelf_2"]]
        first, second = (displayed_goods(world, shelf) for shelf in shelves)
        self.assertEqual(first[:5], ["canned_beans", "pizza_radioactiva", "hoe", "rusty_knife", "old_radio"])
        self.assertEqual((len(first), len(second)), (6, 6))
        self.assertEqual(displayed_goods(world, world.interactables["pantry_1"]), [], "a pantry is not a display")

        view.centre_on((18, 4))
        self._look_into("shop")
        area = view._canvas_rect(pygame.Rect(15 * TILE_SIZE, 2 * TILE_SIZE, 2 * TILE_SIZE, 2 * TILE_SIZE))
        stocked = pygame.image.tobytes(self.game.canvas.subsurface(area), "RGB")
        counter = world.containers["shop_counter"]
        counter.items[:] = [counter.stack_of("canned_beans", None)]
        counter.items[0].quantity = 2
        self.assertEqual([displayed_goods(world, shelf) for shelf in shelves], [["canned_beans"] * 2, []])
        counter.items.clear()
        with self.assertNoLogs("graphics.assets", level="WARNING"):
            view.render()
        self.assertNotEqual(pygame.image.tobytes(self.game.canvas.subsurface(area), "RGB"), stocked)

    # --- Friends and couples on screen ---

    def test_a_matter_of_the_heart_is_put_to_the_player_and_the_card_says_who_is_who(self) -> None:
        self._make_everyone_get_along()
        view, world = self.game.global_view, self.game.world
        tomas, ines, vera = (world.residents[name] for name in ("tomas", "ines", "vera"))
        self.assertEqual(describe_bond(world, tomas, ines), "")
        world.relationship("tomas", "vera").affection = 70
        world.relationship("tomas", "vera").trust = 40
        self.assertEqual(describe_bond(world, tomas, vera), " (amistad íntima)")
        self.assertEqual(describe_bond(world, vera, tomas), "", "it runs one way")

        feelings = world.relationship("tomas", "ines")
        feelings.attraction, feelings.affection = 50, 40
        tomas.activity = world.interventions.maybe_romance(world, tomas)
        self.assertEqual([d.kind for d in world.decisions.values()], ["confession"])
        self._key(pygame.K_TAB)
        interaction = self.game.interaction_view
        self.assertEqual(self.game.scene_name, "interaction")
        self.assertEqual(interaction.expression, "neutral")
        self.assertEqual(len(interaction.buttons), 3)
        self.game.active_scene.render()
        self._key(pygame.K_1)
        self.assertIn("Díselo", interaction.result)
        self.assertEqual(interaction.expression, "happy")
        self.assertEqual(tomas.activity.intent, "confession")
        self._key(pygame.K_SPACE)

        tomas.couple_with, ines.couple_with = "ines", "tomas"
        self.assertEqual(describe_bond(world, tomas, ines), " (pareja)")
        tomas.activity = Activity("tryst", minutes_left=30, using=True, partner_id="ines")
        self.assertEqual(describe_action(world, tomas), "a solas con Inés")
        view.hud.select_resident("tomas")
        view.centre_on_resident("tomas")
        with self.assertNoLogs("graphics.assets", level="WARNING"):
            view.render()

    # --- Beyond the fence ---

    def test_whoever_is_outside_is_not_on_the_map_and_their_find_is_put_to_the_player(self) -> None:
        self._make_everyone_get_along()
        view, world = self.game.global_view, self.game.world
        sergio = world.residents["sergio"]
        view.centre_on_resident("sergio")
        view.render()
        self.assertIn("sergio", view.hitboxes)
        while not sergio.away:
            world.step(1)
        on_the_map = view.hitboxes["sergio"].copy()
        view.centre_on_resident("sergio")
        with self.assertNoLogs("graphics.assets", level="WARNING"):
            view.render()
        # He is not on the map any more: his face waits in a corner, where he can still be picked.
        corner = view.hitboxes["sergio"]
        self.assertEqual(corner.size, MARKER_SIZE)
        self.assertNotEqual(corner.center, on_the_map.center)
        self.assertLess(corner.right, 120)
        self.assertEqual([resident.resident_id for resident in away_residents(world)], ["sergio"])
        self.assertEqual(describe_action(world, sergio), "fuera del asentamiento")
        self._click(corner.center)
        self.assertEqual(view.hud.selected_id, "sergio")
        view.render()
        self.assertIsNotNone(view.hud.card_rect(), "his card can still be read")

        sergio.expedition.find_at = world.clock.total_minutes + 1
        sergio.expedition.returns_at = world.clock.total_minutes + 200
        world.step(2)
        self.assertEqual(view.needing_attention(), ["sergio"])
        self._key(pygame.K_TAB)
        interaction = self.game.interaction_view
        self.assertEqual(self.game.scene_name, "interaction")
        self.assertEqual(interaction.decision.kind, "risky_find")
        self.game.active_scene.render()
        self._key(pygame.K_3)
        self.assertIn("Vuélvete, no compensa", interaction.result)
        self.assertEqual(interaction.expression, "sad")
        self.assertTrue(sergio.away)

    # --- What comes from outside ---

    def test_a_storm_is_seen_and_named_and_a_newcomer_is_drawn_like_anyone(self) -> None:
        self._make_everyone_get_along()
        view, world = self.game.global_view, self.game.world
        self.assertIsNone(describe_weather(world))
        view.centre_on((15, 14))
        view.render()
        ground = view._tile_pixel(10.5, 18.5)
        clear = tuple(self.game.canvas.get_at(ground))[:3]
        world.weather = Weather("dust_storm", world.clock.total_minutes + 120)
        self.assertEqual(describe_weather(world), "Tormenta de polvo")
        with self.assertNoLogs("graphics.assets", level="WARNING"):
            view.render()
        self.assertNotEqual(tuple(self.game.canvas.get_at(ground))[:3], clear)
        world.weather = None

        tomas = world.residents["tomas"]
        tomas.activity = Activity("work", "guard_post", minutes_left=300, using=True)
        world.at_the_gate = "olga"
        world.interventions.ask(world, tomas, "stranger")
        self._key(pygame.K_TAB)
        interaction = self.game.interaction_view
        self.assertEqual(interaction.decision.kind, "stranger")
        self.assertIn("Olga", interaction.decision.prompt)
        self.game.active_scene.render()
        self._key(pygame.K_1)
        self.assertIn("Tomás abre la puerta a Olga", interaction.result)
        self.assertEqual(interaction.expression, "happy")
        self._key(pygame.K_SPACE)
        self.assertIn("olga", world.residents)
        view.hud.select_resident("olga")
        view.centre_on_resident("olga")
        with self.assertNoLogs("graphics.assets", level="WARNING"):
            view.render()
        self.assertIn("olga", view.hitboxes)
        self.assertEqual(describe_job(world, world.residents["olga"]), "Sin trabajo")

    def test_raiders_are_put_to_the_player_and_shelter_is_put_into_words(self) -> None:
        self._make_everyone_get_along()
        view, world = self.game.global_view, self.game.world
        lucia, tomas = world.residents["lucia"], world.residents["tomas"]
        lucia.activity = Activity("shelter", path=[(7, 9)], minutes_left=90)
        self.assertEqual(describe_action(world, lucia), "corre a resguardarse")
        lucia.activity = Activity("shelter", minutes_left=90, using=True)
        self.assertEqual(describe_action(world, lucia), "se resguarda del mal tiempo")

        world.clock.day, world.clock.hour, world.clock.minute = 2, 22, 58
        world.happened = {event_id: 2 for event_id in world.registries.world_events.events}
        tomas.activity = Activity("work", "guard_post", minutes_left=300, using=True)
        world.upcoming.append(Upcoming("raid", world.clock.total_minutes + 1))
        world.step(1)
        self.assertEqual([decision.kind for decision in world.decisions.values()], ["raid"])
        self.game.music = MusicSettings(tracks={mood: mood for mood in MOODS})
        self.game.update_music()
        self.assertEqual(self.game.audio.track, "tension")
        self._key(pygame.K_TAB)
        interaction = self.game.interaction_view
        self.assertEqual(interaction.decision.resident_id, "tomas")
        self.game.active_scene.render()
        self._key(pygame.K_3)
        self.assertIn("Apártate, no merece la pena", interaction.result)
        self.assertIn(interaction.expression, ("angry", "sad"))
        self._key(pygame.K_SPACE)
        view.centre_on_resident("tomas")
        with self.assertNoLogs("graphics.assets", level="WARNING"):
            view.render()

    # --- At a glance ---

    def test_what_the_settlement_has_heard_is_coming_is_on_screen_and_what_it_has_not_is_not(self) -> None:
        self._make_everyone_get_along()
        view, world = self.game.global_view, self.game.world
        storm = Upcoming("dust_storm", world.clock.total_minutes + 5 * 60)
        world.upcoming.append(storm)
        self.assertEqual(known_forecasts(world), [], "it is coming, but nobody knows")
        self.assertIsNone(view.hud.outlook_rect())
        # Each hears it alone behind walls, so that nobody else is in earshot.
        lucia, marta = world.residents["lucia"], world.residents["marta"]
        lucia.x, lucia.y = 5, 5
        marta.x, marta.y = 16, 4
        world.happenings.hear_radio(world, lucia)
        self.assertEqual(known_forecasts(world), ["A las 13: una tormenta de polvo (lo sabe 1)"])
        world.happenings.hear_radio(world, marta)
        self.assertEqual(known_forecasts(world), ["A las 13: una tormenta de polvo (lo saben 2)"])
        panel = view.hud.outlook_rect()
        self.assertTrue(view.hud.covers(panel.center))
        before = pygame.image.tobytes(self.game.canvas.subsurface(panel), "RGB")
        with self.assertNoLogs("graphics.assets", level="WARNING"):
            view.render()
        self.assertNotEqual(pygame.image.tobytes(self.game.canvas.subsurface(panel), "RGB"), before)
        world.upcoming.clear()
        self.assertEqual(known_forecasts(world), [])
        self.assertIsNone(view.hud.outlook_rect())

    def test_partner_and_friends_of_whoever_is_selected_are_marked(self) -> None:
        self._make_everyone_get_along()
        view, world = self.game.global_view, self.game.world
        tomas, ines, vera, raul = (world.residents[name] for name in ("tomas", "ines", "vera", "raul"))
        self.assertIsNone(view._bond_icon(ines), "with nobody selected there is nothing to mark")
        view.hud.select_resident("tomas")
        self.assertIsNone(view._bond_icon(ines))
        tomas.couple_with, ines.couple_with = "ines", "tomas"
        self.assertEqual(view._bond_icon(ines), "heart")
        world.relationship("tomas", "vera").affection = 40
        world.relationship("tomas", "vera").trust = 20
        self.assertEqual(view._bond_icon(vera), "friend")
        self.assertIsNone(view._bond_icon(raul))
        view.hud.select_resident("vera")
        self.assertIsNone(view._bond_icon(tomas), "what she feels for him is another matter")
        ines.activity = Activity("tryst", minutes_left=30, using=True, partner_id="tomas")
        self.assertEqual(view._status_icon(ines, resting=False), "heart")
        view.hud.select_resident("tomas")
        view.centre_on_resident("tomas")
        with self.assertNoLogs("graphics.assets", level="WARNING"):
            view.render()

    def test_the_sky_by_the_clock_and_a_minimap_that_can_be_put_away(self) -> None:
        self._make_everyone_get_along()
        view, world = self.game.global_view, self.game.world
        sky = pygame.Rect(6 + view.font.width(world.clock.label) + 4, 5, 8, 8)
        view.render()
        by_day = pygame.image.tobytes(self.game.canvas.subsurface(sky), "RGB")
        world.clock.hour = 23
        with self.assertNoLogs("graphics.assets", level="WARNING"):
            view.render()
        sky = pygame.Rect(6 + view.font.width(world.clock.label) + 4, 5, 8, 8)
        self.assertNotEqual(pygame.image.tobytes(self.game.canvas.subsurface(sky), "RGB"), by_day)

        minimap = view.hud.minimap_rect
        put_away = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_n)
        view.handle_event(put_away)
        self.assertIsNone(view.hud.minimap_rect)
        self.assertEqual(view.hud.notice, MINIMAP_OFF)
        self.assertFalse(view.hud.covers(minimap.center))
        view.render()
        view.handle_event(put_away)
        self.assertEqual(view.hud.minimap_rect, minimap)
        self.assertEqual(view.hud.notice, MINIMAP_ON)

    def test_every_reason_not_to_ask_has_words(self) -> None:
        self.assertEqual(describe_obstacle(None), "")
        for code in ("own_job", "no_post", "deciding", "asked_recently", "unknown"):
            self.assertTrue(describe_obstacle(code), code)

    # --- Atmosphere ---

    def _brightness(self, tile: tuple[float, float]) -> int:
        return sum(self.game.canvas.get_at(self.game.global_view._tile_pixel(*tile))[:3])

    def test_the_light_goes_by_the_clock_in_steps(self) -> None:
        self.assertEqual([daylight(hour) for hour in (12, 8, 19, 0, 3, 22)], [1.0, 1.0, 1.0, 0.0, 0.0, 0.0])
        self.assertEqual((daylight(6, 30), daylight(20, 30)), (0.5, 0.5))
        levels = [daylight(hour, minute) for hour in range(24) for minute in range(0, 60, 5)]
        self.assertEqual({level * STEPS % 1 for level in levels}, {0.0}, "twilight moves in whole steps")
        dusk = [daylight(19, minute) for minute in range(30, 60)] + [daylight(20, m) for m in range(60)]
        self.assertEqual(dusk, sorted(dusk, reverse=True))
        self.assertEqual((ambient(1.0), ambient(0.0)), ((255, 255, 255), NIGHT))

    def test_night_darkens_the_settlement_except_around_fires_and_lamps(self) -> None:
        view, world = self.game.global_view, self.game.world
        far, by_the_fire, by_a_lamp = (10.5, 18.5), (19.5, 13.5), (9.5, 9.5)
        view.centre_on((15, 14))
        world.clock.hour = 12
        view.render()
        noon = {tile: self._brightness(tile) for tile in (far, by_the_fire, by_a_lamp)}
        world.clock.hour = 0
        with self.assertNoLogs("graphics.assets", level="WARNING"):
            view.render()
        night = {tile: self._brightness(tile) for tile in (far, by_the_fire, by_a_lamp)}
        self.assertLess(night[far], noon[far] * 0.6)
        for lit in (by_the_fire, by_a_lamp):
            self.assertGreater(night[lit] / noon[lit], 0.7, lit)
            self.assertLessEqual(night[lit], noon[lit], "light never makes a thing brighter than by day")
        # Names and icons are not part of the scene, so the night does not dim them.
        world.clock.hour = 20
        world.clock.minute = 30
        view.render()
        self.assertLess(night[far], self._brightness(far))
        self.assertLess(self._brightness(far), noon[far])

    def test_a_building_keeps_its_roof_until_someone_looks_inside(self) -> None:
        view, world = self.game.global_view, self.game.world
        marta = world.residents["marta"]
        marta.x, marta.y = world.rooms["dormitory"].x + 1, world.rooms["dormitory"].y + 2
        marta.trail = []
        view.centre_on((12, 8))
        view.render()
        self.assertEqual(view.looked_into(), set())
        self.assertNotIn("crate_dorm", view.container_hitboxes)
        self.assertEqual(view.hitboxes["marta"].size, MARKER_SIZE, "under a roof she is a face on it")

        # Resting the mouse on it does not open it, and nor does selecting whoever is inside:
        # from the map a building is always shut, and is seen into by going in.
        room = world.rooms["dormitory"]
        x, y = view._tile_pixel(room.x + room.width / 2, room.y + 0.5)
        view.handle_event(
            pygame.event.Event(pygame.MOUSEMOTION, pos=(x * SCALE + 1, y * SCALE + 1), rel=(0, 0), buttons=(0, 0, 0))
        )
        view.render()
        self.assertEqual(view.looked_into(), set())
        view.hud.select_resident("marta")
        view.render()
        self.assertEqual(view.looked_into(), set())
        self.assertEqual(view.hitboxes["marta"].size, MARKER_SIZE)
        self.assertNotIn("crate_dorm", view.container_hitboxes)
        view.hud.select_resident(None)

        view.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_t))
        self.assertEqual(view.hud.notice, ROOFS_OFF)
        self.assertEqual(view.looked_into(), set(view.roof_tiles))
        with self.assertNoLogs("graphics.assets", level="WARNING"):
            view.render()
        self.assertIn("pantry_1", view.container_hitboxes)
        self.assertIn("crate_dorm", view.container_hitboxes)
        self.assertEqual(view.hitboxes["marta"].size, FRAME_SIZE, "with the roofs off she is seen whole")
        view.set_zoom(0)
        self.assertEqual(view.looked_into(), set(), "from afar every roof is on")

    def test_the_minimap_shows_the_settlement_and_a_click_on_it_goes_there(self) -> None:
        view, world = self.game.global_view, self.game.world
        minimap = view.hud.minimap_rect
        self.assertTrue(view.viewport.contains(minimap), "it sits in a corner of the map")
        self.assertLess(minimap.right, view.viewport.centerx, "out of the way of what opens on the right")
        self.assertTrue(view.hud.covers(minimap.center))
        view.hud.select_resident("raul")
        view.centre_on((5, 5))
        with self.assertNoLogs("graphics.assets", level="WARNING"):
            view.render()
        self._click(minimap.center)
        self.assertEqual(view.hud.selected_id, "raul", "a click on the minimap fell through to the map")
        x, y = view._map_point(view.viewport.center)
        self.assertAlmostEqual(x / TILE_SIZE, world.tile_map.width / 2, delta=1)
        self.assertAlmostEqual(y / TILE_SIZE, world.tile_map.height / 2, delta=1)
        # A corner of it is a corner of the map, as far as the view can go.
        self._click((minimap.left + 2, minimap.top + 2))
        self.assertEqual(view._map_point(view.viewport.topleft), (0.0, 0.0))

    def test_one_key_goes_round_whoever_needs_attention(self) -> None:
        self._make_everyone_get_along()
        view, world = self.game.global_view, self.game.world
        go = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_g)
        self.assertEqual(view.needing_attention(), [])
        view.handle_event(go)
        self.assertEqual(view.hud.notice, NOBODY_NEEDS_ATTENTION)
        self.assertIsNone(view.hud.selected_id)

        ines, marta = world.residents["ines"], world.residents["marta"]
        ines.injuries = [Injury("cut", 40)]
        marta.job_id = marta.post_id = None
        world.vacancies["cook"] = world.clock.total_minutes - 30 * 60
        marta.activity = world.interventions.maybe_offer_job(world, marta)
        self.assertEqual(view.needing_attention(), ["marta", "ines"], "whoever waits for advice comes first")
        chosen = []
        for _ in range(3):
            view.handle_event(go)
            view.render()
            chosen.append(view.hud.selected_id)
            self.assertTrue(view.viewport.contains(view.hitboxes[view.hud.selected_id]))
        self.assertEqual(chosen, ["marta", "ines", "marta"])

    def test_a_death_leaves_a_grave_on_the_map_and_a_line_in_the_log(self) -> None:
        self._make_everyone_get_along()
        view, world = self.game.global_view, self.game.world
        raul, lucia = world.residents["raul"], world.residents["lucia"]
        lucia.injuries = [Injury("cut", 99)]
        world.health.fight_damage(world, lucia, raul, world.registries.interactions["fight"])
        self.assertNotIn("lucia", world.residents)
        view.hud.select_resident("lucia")
        self._play(1)
        grave = world.interactables[world.deaths[0].grave_id]
        view.centre_on((grave.x, grave.y))
        with self.assertNoLogs("graphics.assets", level="WARNING"):
            view.render()
        self.assertIsNone(view.hud.card_rect(), "there is no card for someone who is gone")
        texts = [event.text for event in view.hud.feed.recent(10)]
        self.assertTrue(any("Lucía ha muerto" in text for text in texts))
        self.assertEqual(self.game.world.clock.speed, 1)

    # --- The frame round the map ---

    def test_the_screen_is_a_map_with_a_bar_a_menu_and_a_panel_round_it(self) -> None:
        view = self.game.global_view
        layout = view.hud.layout
        canvas = self.game.canvas.get_rect()
        parts = [layout.top, layout.sidebar, layout.map, layout.panel]
        self.assertEqual(sum(part.width * part.height for part in parts), canvas.width * canvas.height)
        for index, part in enumerate(parts):
            self.assertTrue(canvas.contains(part))
            self.assertFalse(any(part.colliderect(other) for other in parts[index + 1 :]))
        self.assertEqual(view.viewport, layout.map)
        self.assertGreater(layout.map.width, layout.panel.width * 2)
        self.assertEqual(layout.map.bottom, canvas.bottom, "the map goes down to the foot of the screen")
        # Only the map is map: everything round it is in front of it.
        self.assertFalse(view.hud.covers(layout.map.center))
        for part in (layout.top, layout.sidebar, layout.panel):
            self.assertTrue(view.hud.covers(part.center))
        # The dock is no part of it: it opens over the foot of the menu and the map, clear of the menu's rows.
        self.assertTrue(layout.sidebar.union(layout.map).contains(layout.dock))
        self.assertEqual(layout.dock.bottom, canvas.bottom)
        self.assertLessEqual(max(button.rect.bottom for button in view.hud.menu), layout.dock.top)

    def test_with_nobody_selected_the_panel_lists_everybody_to_be_picked(self) -> None:
        view, world = self.game.global_view, self.game.world
        view.render()
        self.assertIsNone(view.hud.card_rect())
        rows = roster_rows(view.hud.layout.panel, world)
        self.assertEqual([resident_id for _, resident_id in rows], list(world.residents))
        row, resident_id = rows[3]
        self._click(row.center)
        self.assertEqual(view.hud.selected_id, resident_id)
        view.render()
        self.assertTrue(view.viewport.contains(view.hitboxes[resident_id]), "the view goes to whoever is picked")
        # The first entry of the menu goes back to the list.
        self._click(view.hud.menu[0].rect.center)
        self.assertIsNone(view.hud.selected_id)

    def test_the_panel_shows_who_matters_to_a_resident_and_a_click_goes_to_them(self) -> None:
        view, world = self.game.global_view, self.game.world
        raul = world.residents["raul"]
        view.hud.select_resident("raul")
        rows = relationship_rows(world, raul, 5)
        self.assertEqual(rows[0][0].resident_id, "marta", "whoever he feels most about comes first")
        self.assertEqual((rows[0][1], rows[0][2], rows[0][3]), (-35, "Se llevan mal", "argument"))
        raul.couple_with, world.residents["ines"].couple_with = "ines", "raul"
        self.assertEqual(relationship_rows(world, raul, 5)[0][2], "Pareja")
        self.assertEqual(trait_names(world, world.residents["marta"]), ["Le pierde la música"])
        with self.assertNoLogs("graphics.assets", level="WARNING"):
            view.render()
        row, other_id = relationship_hitboxes(view.hud.layout.panel, world, raul)[0]
        self.assertEqual(other_id, "ines")
        self._click(row.center)
        self.assertEqual(view.hud.selected_id, "ines")

    def test_the_bar_counts_what_the_settlement_has(self) -> None:
        world = self.game.world
        counts = dict(settlement_counts(world))
        self.assertEqual(counts["people"], f"{len(world.residents)}/11")
        self.assertEqual(counts["medicine"], str(world.containers["medicine_cabinet"].count("medicine")))
        food = int(counts["food"])
        self.assertGreater(food, 0)
        pantry = world.containers["pantry_1"]
        world.stock(pantry, "canned_beans", 5, None)
        world.stock(pantry, "canned_beans", 3, "raul")
        self.assertEqual(int(dict(settlement_counts(world))["food"]), food + 5, "what is somebody's own is not counted")
        stock = dict(settlement_stock(world))
        everyones = sum(
            item.quantity
            for inventory in world.containers.values()
            for item in inventory.items
            if item.definition_id == "canned_beans" and item.owner_id is None
        )
        self.assertEqual(stock["canned_beans"], everyones)

    def test_the_stores_open_from_the_menu_and_share_their_corner_with_the_board_and_the_log(self) -> None:
        view = self.game.global_view
        hud = view.hud
        stores = next(button for button in hud.menu if button.intent == STORES_INTENT)
        self._click(stores.rect.center)
        self.assertTrue(hud.stores_open)
        with self.assertNoLogs("graphics.assets", level="WARNING"):
            view.render()
        self.assertTrue(hud.covers(hud.stores_rect().center))
        self.assertTrue(view.viewport.contains(hud.stores_rect()))
        self._click(hud.jobs_button.rect.center)
        self.assertEqual((hud.stores_open, hud.jobs_open, hud.log_open), (False, True, False))
        self._click(hud.log_button.rect.center)
        self.assertEqual((hud.stores_open, hud.jobs_open, hud.log_open), (False, False, True))
        self.assertTrue(view.viewport.contains(hud.log_rect()))
        self.assertTrue(view.viewport.contains(hud.jobs_rect()))

    def test_nothing_is_kept_open_at_the_foot_of_the_map_and_what_has_gone_on_opens_from_the_menu(self) -> None:
        view, world = self.game.global_view, self.game.world
        hud, dock = view.hud, view.hud.layout.dock
        foot = (view.viewport.right - 20, dock.centery)
        self.game.handle_key(pygame.K_3)
        self._play(8)
        self.assertIsNotNone(hud.feed.latest(), "things have gone on")
        view.render()
        # With things going on and nobody talking, there is only map down there.
        self.assertIsNone(hud.dock_rect())
        self.assertIsNone(hud.spoken)
        self.assertFalse(hud.covers(foot))
        self.assertTrue(view._on_map(foot))
        self.assertGreater(hud.minimap_rect.bottom, dock.top, "and the minimap sits at the foot of it")
        self.assertTrue(view.viewport.contains(hud.minimap_rect))
        # What has gone on is read by asking for it, and put away the same way.
        closed = pygame.image.tobytes(self.game.canvas.subsurface(hud.log_rect()), "RGB")
        self._click(hud.log_button.rect.center)
        self.assertTrue(hud.log_open)
        view.render()
        self.assertNotEqual(pygame.image.tobytes(self.game.canvas.subsurface(hud.log_rect()), "RGB"), closed)
        self.assertTrue(hud.covers(hud.log_rect().center))
        self.assertFalse(hud.covers(foot), "it is not down there that it opens")
        self._click(hud.log_button.rect.center)
        self.assertFalse(hud.log_open)
        # Somebody selected who is talking to somebody opens the dock, and the minimap makes way.
        self._stand_together("raul", "tomas")
        raul, tomas = world.residents["raul"], world.residents["tomas"]
        hud.select_resident("raul")
        raul.activity = Activity("chat", partner_id="tomas", using=True)
        tomas.activity = Activity("chat", partner_id="raul", using=True)
        view.render()
        self.assertEqual(hud.dock_rect(), dock)
        self.assertTrue(hud.covers(foot))
        self.assertFalse(view._on_map(foot))
        self.assertLessEqual(hud.minimap_rect.bottom, dock.top)
        # A panel of the menu opened meanwhile stops short of it.
        hud.toggle_jobs()
        self.assertLessEqual(hud.jobs_rect().bottom, dock.top)
        hud.toggle_jobs()
        # A click on the dock is not a click on the map under it: whoever is selected stays selected.
        self._click(foot)
        self.assertEqual(hud.selected_id, "raul")
        # When they stop talking it goes, and the map and the minimap are back.
        raul.activity = tomas.activity = None
        view.render()
        self.assertIsNone(hud.dock_rect())
        self.assertGreater(hud.minimap_rect.bottom, dock.top)

    def test_the_dock_shows_the_exchange_of_whoever_is_selected(self) -> None:
        view, world = self.game.global_view, self.game.world
        self._stand_together("raul", "tomas")
        raul, tomas = world.residents["raul"], world.residents["tomas"]
        dock = view.hud.layout.dock
        view.hud.select_resident("raul")
        view.render()
        self.assertIsNone(view.hud.dock_rect(), "talking to nobody, there is nothing to show")
        quiet = pygame.image.tobytes(self.game.canvas.subsurface(dock), "RGB")
        raul.activity = Activity("chat", partner_id="tomas", using=True)
        tomas.activity = Activity("chat", partner_id="raul", using=True)
        self.assertEqual(view.hud.dock_rect(), dock)
        self.assertIn(spoken_line(world, raul), world.registries.dialogue["chat"])
        self.assertEqual(expression_of(world, raul), "happy")
        with self.assertNoLogs("graphics.assets", level="WARNING"):
            view.render()
        self.assertNotEqual(pygame.image.tobytes(self.game.canvas.subsurface(dock), "RGB"), quiet)
        raul.activity = Activity("argument", partner_id="tomas", using=True)
        self.assertEqual(expression_of(world, raul), "angry")
        raul.activity = None
        self.assertIsNone(spoken_line(world, raul))
        self.assertEqual(expression_of(world, raul), "neutral")
        raul.injuries = [Injury("cut", 40)]
        self.assertEqual(expression_of(world, raul), "sad")

    def test_advice_is_asked_for_in_the_dock_with_the_settlement_still_on_show(self) -> None:
        view, world = self.game.global_view, self.game.world
        self._play(8)
        decision = next(iter(world.decisions.values()))
        view.render()
        above = pygame.image.tobytes(self.game.canvas.subsurface(view.hud.layout.top), "RGB")
        self.game.open_interaction(decision.decision_id)
        self.assertEqual(view.hud.selected_id, decision.resident_id, "whoever asks is the one on the panel")
        scene = self.game.interaction_view
        with self.assertNoLogs("graphics.assets", level="WARNING"):
            self.game.active_scene.render()
        self.assertEqual(pygame.image.tobytes(self.game.canvas.subsurface(view.hud.layout.top), "RGB"), above)
        self.assertEqual(len(scene.buttons), len(decision.options))
        dock = view.hud.layout.dock
        for button in scene.buttons:
            self.assertTrue(dock.contains(button.rect))
        self._click(scene.buttons[0].rect.center)
        self.assertIsNotNone(scene.result)
        self.game.active_scene.render()

    def test_every_place_has_its_name_on_the_map_and_doing_something_shows_in_a_bubble(self) -> None:
        view, world = self.game.global_view, self.game.world
        self._stand_together("raul")
        view.set_zoom(0)
        view.render()
        plain = pygame.image.tobytes(self.game.canvas.subsurface(view.viewport), "RGB")
        names = {room.name for room in world.rooms.values()}
        self.assertGreater(len(names), 5)
        for room in world.rooms.values():
            room.name = ""
        view.render()
        self.assertNotEqual(pygame.image.tobytes(self.game.canvas.subsurface(view.viewport), "RGB"), plain)
        view.set_zoom(1)
        view.centre_on((20, 14))
        view.render()
        idle = pygame.image.tobytes(self.game.canvas.subsurface(view.viewport), "RGB")
        world.residents["raul"].activity = Activity("work", using=True)
        self.assertEqual(view._status_icon(world.residents["raul"], resting=False), "work")
        view.render()
        self.assertNotEqual(pygame.image.tobytes(self.game.canvas.subsurface(view.viewport), "RGB"), idle)

    def test_a_building_stands_whole_until_it_is_looked_into_and_hides_what_is_behind_it(self) -> None:
        view, world = self.game.global_view, self.game.world
        shop = world.rooms["shop"]
        view.centre_on((shop.x + shop.width / 2, shop.y + shop.height / 2))
        view.render()
        self.assertIn("shop", view._closed)
        # The row over the wall with the door is inside the shop, and shows as its front while it is closed.
        front = view._canvas_rect(pygame.Rect(shop.x * TILE_SIZE, (shop.y + shop.height - 1) * TILE_SIZE, shop.width * TILE_SIZE, TILE_SIZE))
        closed = pygame.image.tobytes(self.game.canvas.subsurface(front), "RGB")
        behind = (shop.x + 1, shop.y - 2)
        raul = world.residents["raul"]
        raul.x, raul.y, raul.trail, raul.activity = behind[0], behind[1], [], None
        view.render()
        hitbox = view.hitboxes["raul"].copy()
        hidden = pygame.image.tobytes(self.game.canvas.subsurface(hitbox), "RGB")
        view.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_t))
        view.render()
        self.assertNotIn("shop", view._closed)
        self.assertNotEqual(pygame.image.tobytes(self.game.canvas.subsurface(front), "RGB"), closed)
        self.assertNotEqual(
            pygame.image.tobytes(self.game.canvas.subsurface(hitbox), "RGB"), hidden, "the roof no longer hides his legs"
        )

    # --- Bodies with bones ---

    def _stand_together(self, *names: str) -> None:
        """Put residents side by side on open ground with nothing to do, and draw them."""
        view, world = self.game.global_view, self.game.world
        for index, name in enumerate(names):
            resident = world.residents[name]
            resident.x, resident.y, resident.trail, resident.activity = 20 + index, 14, [], None
        view.centre_on((20, 14))
        view.render()

    def _frames(self, seconds: float) -> None:
        """Let real time pass for the scene alone, a frame at a time, drawing each one."""
        view = self.game.global_view
        for _ in range(round(seconds * 60)):
            view.update(1 / 60)
            with self.assertNoLogs("graphics.assets", level="WARNING"):
                view.render()

    def test_everyday_life_runs_no_physics_at_all(self) -> None:
        view = self.game.global_view
        self._play(90)
        view.update(0.1)
        view.render()
        self.assertGreaterEqual(len(view.bodies.characters), 1)
        self.assertTrue(all(character.skeleton is None for character in view.bodies.characters.values()))
        self.assertEqual(view.bodies.awake(), 0)
        self.assertEqual(view.bodies.remains, [])

    def test_a_body_does_what_its_resident_is_doing(self) -> None:
        view, world = self.game.global_view, self.game.world
        self._stand_together("raul", "tomas")
        raul = world.residents["raul"]

        def clip() -> str:
            return view._clip_of(raul)[0]

        self.assertEqual(clip(), "idle")
        raul.activity = Activity("eat", "pantry_1", minutes_left=10, using=True, item_id="canned_beans")
        # Eating, fighting and walking are done their own way: the clip is the one of their manner.
        self.assertEqual(clip(), world.manner_of(raul, "eat").clip)
        raul.activity = Activity("work", using=True)
        self.assertEqual(clip(), "work")
        raul.activity = Activity("fight", partner_id="tomas", using=True)
        self.assertEqual(clip(), world.manner_of(raul, "fight").clip)
        raul.activity = Activity("argument", partner_id="tomas", using=True)
        self.assertEqual(clip(), "argue")
        raul.activity = Activity("chat", partner_id="tomas", using=True)
        self.assertEqual(clip(), "idle")
        raul.activity = None
        raul.trail = [(raul.x - 1, raul.y), raul.tile]
        view.tick_progress = 0.5
        view.render()
        self.assertEqual(view.bodies.characters["raul"].clip, world.manner_of(raul, "walk").clip)
        self.assertEqual(view.bodies.characters["raul"].facing, "right")
        self.assertEqual(view.bodies.characters["tomas"].clip, "idle")

    def test_a_walk_at_a_slant_is_drawn_along_its_line_and_seen_from_the_nearest_side(self) -> None:
        view, world = self.game.global_view, self.game.world
        self._stand_together("raul")
        raul = world.residents["raul"]
        view.tick_progress = 0.75
        # Mostly across and a little down; mostly up and a little back; and neither more than the other.
        for step, facing in (((1.0, 0.25), "right"), ((-0.25, -1.0), "up"), ((-1.0, 1.0), "left")):
            raul.trail = [(raul.x - 2 * step[0], raul.y - 2 * step[1]), (raul.x - step[0], raul.y - step[1]), raul.tile]
            x, y, seen, stride = view._walk_state(raul)
            self.assertAlmostEqual(x, raul.x - step[0] / 2)
            self.assertAlmostEqual(y, raul.y - step[1] / 2)
            self.assertEqual(seen, facing)
            self.assertAlmostEqual(stride, 0.75)
            view.render()
            self.assertEqual(view.bodies.characters["raul"].facing, facing)
            # Their feet are where the line is, between the middles of two tiles.
            feet = view.hitboxes["raul"].midbottom
            raul.trail = []
            view.render()
            there = view.hitboxes["raul"].midbottom
            self.assertAlmostEqual((feet[0] - there[0]) / view.tile_px, -step[0] / 2, delta=0.1)
            self.assertAlmostEqual((feet[1] - there[1]) / view.tile_px, -step[1] / 2, delta=0.1)

    def test_a_blow_staggers_whoever_takes_it_and_a_hard_one_knocks_them_down(self) -> None:
        view, world = self.game.global_view, self.game.world
        self._stand_together("raul", "tomas", "lucia")
        raul, tomas, lucia = (world.residents[name] for name in ("raul", "tomas", "lucia"))
        world.health.hurt(world, tomas, 8, "bruise", "una prueba", raul)
        world.health.hurt(world, lucia, 22, "fracture", "una prueba", tomas)
        view.on_events(world.events.drain())
        bodies = view.bodies.characters
        self.assertFalse(bodies["raul"].physical)
        self.assertIs(bodies["tomas"].mode, Mode.STAGGER)
        self.assertIs(bodies["lucia"].mode, Mode.RAGDOLL)
        self.assertEqual(view.bodies.awake(), 2)
        hitbox = view.hitboxes["lucia"].copy()
        self._frames(1.0)
        # Struck from the left, she goes down to the right. She can still be picked where she stands.
        down = bodies["lucia"].skeleton
        self.assertGreater(down.joints["head"].y, bodies["lucia"].pose()["head"][1] + 8)
        self.assertGreater(down.joints["head"].x, bodies["lucia"].x)
        self.assertEqual(view.hitboxes["lucia"], hitbox)
        self.assertFalse(bodies["tomas"].physical, "he has steadied himself")
        self._frames(3.0)
        self.assertFalse(bodies["lucia"].physical, "she is back on her feet")
        self.assertEqual(view.bodies.awake(), 0)

    def test_nothing_moves_while_the_game_is_paused(self) -> None:
        view, world = self.game.global_view, self.game.world
        self._stand_together("raul", "tomas")
        world.health.hurt(world, world.residents["tomas"], 22, "fracture", "una prueba", world.residents["raul"])
        view.on_events(world.events.drain())
        self._frames(0.1)
        world.set_paused(True)
        head = view.bodies.characters["tomas"].skeleton.joints["head"]
        before = (head.x, head.y)
        self._frames(0.5)
        self.assertEqual((head.x, head.y), before)

    def test_a_lost_limb_flies_off_lies_there_and_stays_off_the_body(self) -> None:
        view, world = self.game.global_view, self.game.world
        self._stand_together("raul", "tomas")
        raul, tomas = world.residents["raul"], world.residents["tomas"]
        sure = replace(world.registries.injuries["cut"], severs_chance=1.0)
        world.registries = replace(world.registries, injuries={**world.registries.injuries, "cut": sure})
        world.health.hurt(world, tomas, 30, "cut", "una pelea", raul)
        limb = tomas.lost_limbs[0]
        view.on_events(world.events.drain())
        body = view.bodies.characters["tomas"]
        self.assertEqual(body.lost, [limb])
        self.assertEqual(len(view.bodies.remains), 1)
        part = view.bodies.remains[0]
        self.assertEqual(part.body_id, "tomas")
        self.assertFalse(set(part.skeleton.bones) & set(body.skeleton.bones))
        self.assertIn("tomas", view.alerts, "it calls for the attention of the player")
        self._frames(7.0)
        self.assertTrue(part.skeleton.asleep)
        self.assertTrue(view.bodies.renderer.is_settled(part.skeleton), "lying still, it is drawn from one picture")
        self.assertEqual(view.bodies.awake(), 0)
        self.assertIn(f"sin {world.registries.limbs[limb].name}", describe_injuries(world, tomas))
        # He goes on without it, and what is left of it is cleared away in time.
        self._play(REMAINS_MINUTES + 1)
        view.update(1 / 60)
        view.render()
        self.assertEqual(view.bodies.remains, [])
        self.assertEqual(view.bodies.characters["tomas"].lost, [limb])

    def test_the_dead_fall_where_they_stood_and_are_taken_away_later(self) -> None:
        view, world = self.game.global_view, self.game.world
        self._stand_together("raul", "lucia")
        raul, lucia = world.residents["raul"], world.residents["lucia"]
        standing = view.bodies.characters["lucia"]
        lucia.injuries = [Injury("cut", 99)]
        world.health.fight_damage(world, lucia, raul, world.registries.interactions["fight"])
        view.on_events(world.events.drain())
        self.assertNotIn("lucia", view.bodies.characters)
        self.assertEqual([remains.body_id for remains in view.bodies.remains], ["lucia"])
        body = view.bodies.remains[0]
        self.assertIs(body.skeleton, standing.skeleton, "the very body that stood there")
        self.assertEqual(body.tile, (21, 14))
        self._frames(7.0)
        self.assertTrue(body.skeleton.asleep)
        left, top, right, bottom = body.skeleton.bounds()
        self.assertGreater(right - left, bottom - top, "she lies on the ground")
        self.assertNotIn("lucia", view.hitboxes)
        self._play(REMAINS_MINUTES + 1)
        view.update(1 / 60)
        self.assertEqual(view.bodies.remains, [])

    def test_someone_who_dies_unseen_or_beyond_the_fence_is_handled_all_the_same(self) -> None:
        view, world = self.game.global_view, self.game.world
        # Nobody has been drawn yet: there is no body on the stage to take over.
        self.assertEqual(view.bodies.characters, {})
        marta = world.residents["marta"]
        tile = marta.tile
        world.health.die(world, marta, "una prueba")
        sergio = world.residents["sergio"]
        sergio.expedition = Expedition(returns_at=world.clock.total_minutes + 60, finds=0, danger=0.0)
        world.health.die(world, sergio, "una prueba")
        view.on_events(world.events.drain())
        self.assertEqual([remains.body_id for remains in view.bodies.remains], ["marta"])
        self.assertEqual(view.bodies.remains[0].tile[1], tile[1])
        view.centre_on(tile)
        self._frames(0.5)
        view.set_zoom(0)
        view.render()

    def test_a_loaded_game_shows_who_was_already_maimed(self) -> None:
        self.game.world.residents["raul"].lost_limbs = ["arm_left", "leg_right"]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "save.json"
            self.assertTrue(self.game.save_game(path))
            self.assertTrue(self.game.load_game(path))
        view = self.game.global_view
        self._stand_together("raul")
        self.assertEqual(view.bodies.characters["raul"].lost, ["arm_left", "leg_right"])
        self.assertEqual(view.bodies.remains, [], "nothing came off just now")
        view.render()
        whole = BodyRenderer(self.game.assets, view.bodies.plan).frame("raul", "down", "idle")[0]
        maimed = view.bodies.renderer.frame("raul", "down", "idle", 0, ("arm_left", "leg_right"))[0]
        self.assertLess(pygame.mask.from_surface(maimed).count(), pygame.mask.from_surface(whole).count())


if __name__ == "__main__":
    unittest.main()
