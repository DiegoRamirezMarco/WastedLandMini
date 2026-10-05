import os
import tempfile
import unittest
from pathlib import Path

import pygame

from graphics.character_renderer import FRAME_SIZE
from graphics.face_renderer import MARKER_SIZE
from scenes.global_view import ZOOM_TILE_SIZES
from settings import GAME_MINUTES_PER_REAL_SECOND, SCALE, TILE_SIZE
from simulation.events.event import DomainEvent
from simulation.health.injury import Injury
from simulation.residents.activity import Activity
from ui.labels import describe_action, describe_injuries, describe_job, format_time


class GameShellTests(unittest.TestCase):
    """Runs the real game shell without a window, through SDL's dummy video driver."""

    def setUp(self) -> None:
        # Neither a window nor a loudspeaker: both SDL drivers are the dummy ones.
        for variable in ("SDL_VIDEODRIVER", "SDL_AUDIODRIVER"):
            self.addCleanup(self._restore_driver, variable, os.environ.get(variable))
            os.environ[variable] = "dummy"
        from game.game import Game

        self.game = Game()
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
        self.game.active_scene.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=window, button=1))

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
        self._click(view.hud.card_rect().center)
        self.assertEqual(view.hud.selected_id, "raul", "a click on the card fell through to the map")
        self._click((320, 300))
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
        view.render()
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
        view.render()
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


if __name__ == "__main__":
    unittest.main()
