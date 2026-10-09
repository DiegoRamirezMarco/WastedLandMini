import os
import tempfile
import unittest
from pathlib import Path

import pygame

from graphics.backdrop import PLAIN_ART, BackdropStore, backdrops_from_data, builtin_backdrops, draw_strips
from graphics.backdrop_pictures import PICTURES, painted
from scenes.expedition_view import AHEAD, LEAVE_TRIP_INTENT, NOWHERE
from settings import SCALE
from simulation.commands import SetPausedCommand, SetSpeedCommand
from simulation.events.world_event import Weather
from simulation.work.expedition import Expedition
from simulation.world import SimulationWorld
from ui.labels import TRIP_HOME, describe_span, trip_ends, trip_lines
from ui.trip_bar import face_spot, trip_bar_height, way_ends

STAGE = (1092, 848)


def _send_out(world: SimulationWorld, resident_id: str = "sergio"):
    out = world.residents[resident_id]
    for _ in range(240):
        if out.away:
            return out
        world.step(1)
    raise AssertionError("the scavenger never set out")


def _brightness(surface: pygame.Surface, area: pygame.Rect) -> float:
    return sum(pygame.transform.average_color(surface, area)[:3]) / 3


class BackdropTests(unittest.TestCase):
    """The country that goes by behind whoever is out. No window is needed to draw it."""

    def setUp(self) -> None:
        pygame.init()
        self.addCleanup(pygame.quit)
        self.plan = builtin_backdrops()
        self.store = BackdropStore(None)

    def test_a_backdrop_is_layers_that_go_by_each_at_its_own_pace(self) -> None:
        plan = self.plan
        self.assertEqual([layer.layer_id for layer in plan.layers], ["sky", "far", "middle", "ground", "front"])
        paces = [layer.pace for layer in plan.layers]
        self.assertEqual(paces, sorted(paces), "the nearer a layer, the faster it goes by")
        self.assertEqual(plan.layer("sky").pace, 0.0, "the sky stands still")
        self.assertEqual(plan.layer("ground").pace, 1.0, "the ground goes by as fast as they walk")
        self.assertEqual([layer.layer_id for layer in plan.layers if layer.front], ["front"])
        self.assertTrue(all(layer.name and layer.note for layer in plan.layers), "each says what goes in it")
        self.assertEqual(plan.art_of("ruins"), "ruins")
        self.assertEqual(plan.art_of("somewhere_a_pack_added"), PLAIN_ART)

    def test_what_makes_no_sense_as_a_backdrop_is_rejected(self) -> None:
        good = {"layers": [{"id": "sky"}]}
        self.assertEqual(backdrops_from_data(good).layers[0].name, "sky")
        with self.assertRaisesRegex(ValueError, "at least one layer"):
            backdrops_from_data({})
        with self.assertRaisesRegex(ValueError, "same ID"):
            backdrops_from_data({"layers": [{"id": "sky"}, {"id": "sky"}]})
        with self.assertRaisesRegex(ValueError, "backwards"):
            backdrops_from_data({"layers": [{"id": "sky", "pace": -1}]})
        with self.assertRaisesRegex(ValueError, "ground to stand on"):
            backdrops_from_data({**good, "ground": 0.2, "figure": 0.5})
        with self.assertRaisesRegex(ValueError, "too small"):
            backdrops_from_data({**good, "paper": [4, 4]})

    def test_the_game_draws_every_layer_of_the_ruins_and_leaves_the_sky_alone_solid(self) -> None:
        self.assertEqual(set(PICTURES["ruins"]), {layer.layer_id for layer in self.plan.layers})
        for layer in self.plan.layers:
            picture = painted("ruins", layer.layer_id, self.plan.paper, self.plan)
            self.assertEqual(picture.get_size(), self.plan.paper)
            drawn = pygame.mask.from_surface(picture, 254).count()
            whole = picture.get_width() * picture.get_height()
            if layer.layer_id == "sky":
                self.assertEqual(drawn, whole, "nothing shows through the sky")
            else:
                self.assertTrue(0 < drawn < whole, f"{layer.layer_id} lets what is behind it show")
        # Whatever it has no picture of is left clear, and a zone it has no art for is bare country.
        self.assertIsNone(painted("ruins", "no_such_layer", (40, 31), self.plan).get_bounding_rect().width or None)
        bare = painted("no_such_art", "ground", self.plan.paper, self.plan)
        self.assertGreater(pygame.mask.from_surface(bare).count(), 0)
        again = painted("ruins", "middle", self.plan.paper, self.plan)
        first = painted("ruins", "middle", self.plan.paper, self.plan)
        self.assertEqual(pygame.image.tobytes(again, "RGBA"), pygame.image.tobytes(first, "RGBA"), "the same ruins every time")

    def test_the_ground_is_under_the_feet_and_what_passes_in_front_is_no_higher_than_the_shins(self) -> None:
        plan = self.plan
        wide, tall = plan.paper
        feet = round(plan.ground * tall)
        ground = painted("ruins", "ground", plan.paper, plan)
        for x in range(0, wide, 7):
            self.assertEqual(ground.get_at((x, feet))[3], 255, "there is ground wherever a foot comes down")
            self.assertEqual(ground.get_at((x, tall - 1))[3], 255)
        self.assertEqual(ground.get_bounding_rect().bottom, tall)
        front = painted("ruins", "front", plan.paper, plan)
        knees = feet - round(plan.figure * tall * 0.3)
        self.assertGreaterEqual(front.get_bounding_rect().top, knees)

    def test_layers_fill_the_place_however_far_the_ground_has_gone_by_and_come_round_again(self) -> None:
        strips = self.store.strips("ruins", STAGE[1])
        self.assertEqual([strip.layer.layer_id for strip in strips], [layer.layer_id for layer in self.plan.layers])
        wide = self.store.size_for(STAGE[1])[0]
        self.assertTrue(all(strip.picture.get_width() == wide for strip in strips))
        self.assertIs(self.store.strips("ruins", STAGE[1]), strips, "drawn once and kept")
        area = pygame.Rect(40, 30, *STAGE)

        def shown(travelled: float) -> pygame.Surface:
            picture = pygame.Surface((STAGE[0] + 80, STAGE[1] + 60), pygame.SRCALPHA)
            draw_strips(picture, strips, area, travelled, front=False)
            draw_strips(picture, strips, area, travelled, front=True)
            return picture

        for travelled in (0.0, 333.3, -4100.0, 98765.0):
            picture = shown(travelled)
            self.assertEqual(pygame.mask.from_surface(picture, 254).count(), STAGE[0] * STAGE[1], travelled)
            self.assertEqual(picture.get_bounding_rect(), area, "and nothing of it outside its place")
        ground = next(strip for strip in strips if strip.layer.layer_id == "ground")
        row = ground.top + ground.picture.get_height() // 2

        def road(travelled: float) -> list:
            picture = pygame.Surface((STAGE[0] + 80, STAGE[1] + 60), pygame.SRCALPHA)
            draw_strips(picture, [ground], area, travelled, front=False)
            return [tuple(picture.get_at((x, area.y + row))) for x in range(area.x, area.right, 5)]

        self.assertEqual(road(0.0), road(float(wide)), "a whole width on, the ground is where it was")
        self.assertNotEqual(road(0.0), road(120.0))

    def test_what_is_far_goes_by_slower_than_what_is_near(self) -> None:
        strips = self.store.strips("ruins", STAGE[1])
        wide = self.store.size_for(STAGE[1])[0]
        area = pygame.Rect(0, 0, *STAGE)

        def column(layer_id: str, travelled: float) -> bytes:
            strip = next(strip for strip in strips if strip.layer.layer_id == layer_id)
            picture = pygame.Surface(STAGE, pygame.SRCALPHA)
            draw_strips(picture, [strip], area, travelled, front=strip.layer.front)
            return pygame.image.tobytes(picture.subsurface((0, strip.top, 8, strip.picture.get_height())), "RGBA")

        self.assertEqual(column("sky", 0.0), column("sky", 5000.0))
        middle = self.plan.layer("middle")
        # The ground has to go by four times over for what is behind to come round once.
        self.assertEqual(column("middle", 0.0), column("middle", wide / middle.pace))
        self.assertNotEqual(column("middle", 0.0), column("middle", float(wide)))


class TripWordsTests(unittest.TestCase):
    """What is said of somebody who is out, and where their face goes along the way."""

    def test_a_span_is_said_as_somebody_would(self) -> None:
        self.assertEqual(describe_span(130), "2 h 10 min")
        self.assertEqual(describe_span(120), "2 h")
        self.assertEqual(describe_span(40), "40 min")
        self.assertEqual(describe_span(-5), "0 min")

    def test_it_says_which_way_they_go_and_when_they_are_due(self) -> None:
        world = SimulationWorld.demo_world(seed=7)
        sergio = _send_out(world)
        trip, now = sergio.expedition, world.clock.total_minutes
        self.assertEqual(trip_ends(world, sergio), (TRIP_HOME, "Las ruinas"))
        going, due = trip_lines(world, sergio)
        self.assertEqual(going, "Sergio se aleja por las ruinas")
        self.assertEqual(due, f"Llega en {describe_span(trip.returns_at - now)}")
        trip.turns_at = now
        self.assertEqual(trip_lines(world, sergio)[0], "Sergio vuelve al asentamiento")
        trip.returns_at = now
        self.assertEqual(trip_lines(world, sergio)[1], "Está al llegar")
        self.assertEqual(trip_lines(world, world.residents["marta"]), ("", ""))

    def test_the_face_goes_along_the_way_as_far_as_they_are(self) -> None:
        pygame.init()
        self.addCleanup(pygame.quit)
        rect, face = pygame.Rect(100, 20, 236, 60), pygame.Surface((16, 16))
        left, right = way_ends(rect, 16)
        self.assertTrue(rect.left < left < right < rect.right)
        spots = [face_spot(rect, face, share) for share in (0.0, 0.25, 0.5, 1.0, 7.0)]
        self.assertEqual([spot.centerx for spot in spots[:1] + spots[3:]], [left, right, right])
        self.assertTrue(spots[0].centerx < spots[1].centerx < spots[2].centerx < spots[3].centerx)
        self.assertTrue(all(rect.contains(spot) for spot in spots))


class _Shell(unittest.TestCase):
    """The real game shell without a window, on the settlement that comes ready made."""

    illustrated = True

    def setUp(self) -> None:
        for variable in ("SDL_VIDEODRIVER", "SDL_AUDIODRIVER"):
            self.addCleanup(self._restore_driver, variable, os.environ.get(variable))
            os.environ[variable] = "dummy"
        from game.game import Game

        self.folder = None
        if self.illustrated:
            keep = tempfile.TemporaryDirectory()
            self.addCleanup(keep.cleanup)
            self.folder = Path(keep.name) / "illustrations"
            self.folder.mkdir()
        self.game = Game(illustrations_dir=self.folder, voices_dir=None, start_in_menu=False)
        self.addCleanup(pygame.quit)
        self.view, self.hud, self.world = self.game.global_view, self.game.global_view.hud, self.game.world
        self.trips = self.view.expedition
        self.sergio = _send_out(self.world)
        self.world.events.drain()

    @staticmethod
    def _restore_driver(variable: str, previous: str | None) -> None:
        if previous is None:
            os.environ.pop(variable, None)
        else:
            os.environ[variable] = previous

    def _watch(self) -> None:
        """Press the face of whoever is out, in the corner of the map."""
        self.view.render()
        self.assertIn("sergio", self.view.away_boxes)
        self.view.click(self.view.away_boxes["sergio"].center)

    def _frames(self, count: int = 30) -> None:
        for _ in range(count):
            self.view.update(1 / 60)
        self.view.render()

    def _shown(self) -> pygame.Surface:
        """The frame as the window would have it."""
        self.view.render()
        screen = pygame.Surface((self.view.canvas.get_width() * SCALE, self.view.canvas.get_height() * SCALE))
        self.game.present(screen)
        return screen

    def _stage(self) -> pygame.Rect:
        return self.view.layers.on_screen(self.view.viewport)


class TripScreenTests(_Shell):
    def test_a_click_on_the_face_of_whoever_is_out_shows_them_walking_where_the_map_was(self) -> None:
        self.view.render()
        self.assertIsNone(self.view.outside)
        self.assertIsNotNone(self.hud.minimap_rect)
        self._watch()
        self.assertEqual(self.trips.click(self.trips.leave_button.rect.center), LEAVE_TRIP_INTENT)
        self.assertIsNone(self.trips.click(self.view.viewport.center))
        self.assertEqual((self.view.outside, self.hud.selected_id), ("sergio", "sergio"))
        self.assertIsNone(self.hud.minimap_rect, "there is no map out there to find the way on")
        self.view.render()
        self.assertTrue(self.view.layers.active, "it goes on the window itself, under the canvas")
        box = self.view.hitboxes["sergio"]
        self.assertTrue(self.view.viewport.contains(box))
        self.assertGreater(box.height, 60, "from far nearer than on the map")
        self.assertEqual(self.view.in_view(), (set(), []), "nothing of the settlement is in sight, or heard")
        # The way back to the map.
        self.view.click(self.trips.leave_button.rect.center)
        self.assertIsNone(self.view.outside)
        self.assertIsNotNone(self.hud.minimap_rect)
        self.view.render()
        self.assertNotEqual(self.view.in_view(), (set(), []))

    def test_with_two_out_they_are_seen_one_at_a_time_and_the_faces_say_which(self) -> None:
        now = self.world.clock.total_minutes
        marta = self.world.residents["marta"]
        marta.expedition = Expedition(returns_at=now + 200, finds=1, danger=0.0, left_at=now - 200, turns_at=now - 10)
        self._watch()
        self.view.render()
        self.assertEqual(set(self.view.away_boxes), {"sergio", "marta"})
        self.assertGreater(self.view.hitboxes["sergio"].height, 60, "whoever is watched is picked where they walk")
        self.assertEqual(self.view.hitboxes["marta"], self.view.away_boxes["marta"])
        self.assertFalse(self.trips.heading_back(self.sergio))
        # The other face is the other trip, without going back to the map for it.
        self.view.click(self.view.away_boxes["marta"].center)
        self.assertEqual((self.view.outside, self.hud.selected_id), ("marta", "marta"))
        self._frames(2)
        self.assertGreater(self.view.hitboxes["marta"].height, 60)
        self.assertTrue(self.trips.heading_back(marta))
        self.assertAlmostEqual(self.trips.lead, 1.0 - AHEAD, places=2, msg="found facing home, and not brought across")
        self.assertEqual(trip_lines(self.world, marta)[0], "Marta vuelve al asentamiento")
        self.view.click(self.view.away_boxes["sergio"].center)
        self.assertEqual(self.view.outside, "sergio")

    def test_only_whoever_is_out_can_be_watched(self) -> None:
        self.assertFalse(self.view.watch("marta"))
        self.assertFalse(self.view.watch(None))
        self.assertIsNone(self.view.outside)
        self.assertTrue(self.view.watch("sergio"))

    def test_the_country_goes_by_behind_them_and_they_stay_where_they_are(self) -> None:
        self._watch()
        self._frames(1)
        before, where = self._shown(), self.view.hitboxes["sergio"].copy()
        strides, travelled = self.trips.strides, self.trips.travelled
        self._frames(45)
        self.assertGreater(self.trips.strides, strides)
        self.assertGreater(self.trips.travelled, travelled, "on the way out the ground goes by one way")
        self.assertLess(abs(self.view.hitboxes["sergio"].centerx - where.centerx), 3, "they walk on the spot")
        after = self._shown()
        ground = pygame.Rect(self._stage().x, self._stage().bottom - 40, self._stage().width, 30)
        self.assertNotEqual(
            pygame.image.tobytes(before.subsurface(ground), "RGB"), pygame.image.tobytes(after.subsurface(ground), "RGB")
        )
        # Faster with the game, and not sixteen times as fast with it at sixteen.
        self.world.apply_command(SetSpeedCommand(16))
        strides = self.trips.strides
        self._frames(45)
        hurried = self.trips.strides - strides
        self.world.apply_command(SetSpeedCommand(1))
        strides = self.trips.strides
        self._frames(45)
        plain = self.trips.strides - strides
        self.assertTrue(plain < hurried < plain * 3, (plain, hurried))

    def test_they_face_away_on_the_way_out_and_home_on_the_way_back(self) -> None:
        self._watch()
        self._frames(20)
        self.assertFalse(self.trips.heading_back(self.sergio))
        self.assertAlmostEqual(self.trips.lead, AHEAD, places=2)
        out = self.trips.travelled
        self.sergio.expedition.turns_at = self.world.clock.total_minutes
        self.assertTrue(self.trips.heading_back(self.sergio))
        strides = self.trips.strides
        self._frames(240)
        self.assertLess(self.trips.travelled, out, "and the ground goes by the other way")
        self.assertGreater(self.trips.strides, strides, "walking forwards all the same")
        self.assertAlmostEqual(self.trips.lead, 1.0 - AHEAD, places=1)
        self.assertGreater(self.trips.lead, 0.5, "with more of the place ahead of them than behind")

    def test_with_time_stopped_they_stop_mid_stride(self) -> None:
        self._watch()
        self._frames(10)
        self.world.apply_command(SetPausedCommand(True))
        strides, travelled = self.trips.strides, self.trips.travelled
        self._frames(30)
        self.assertEqual((self.trips.strides, self.trips.travelled), (strides, travelled))

    def test_they_stand_still_at_what_they_come_on_and_a_click_on_them_asks_what_to_do(self) -> None:
        self._watch()
        self.sergio.expedition.find_at = self.world.clock.total_minutes + 1
        self.world.step(2)
        decision = next(d for d in self.world.decisions.values() if d.resident_id == "sergio")
        self.assertTrue(self.trips.stopped(self.sergio))
        strides, travelled = self.trips.strides, self.trips.travelled
        self._frames(30)
        self.assertEqual((self.trips.strides, self.trips.travelled), (strides, travelled))
        self.assertEqual(trip_lines(self.world, self.sergio)[0], "Sergio ha dado con algo y no se decide")
        self.assertEqual(self.view._status_icon(self.sergio, False), "alert")
        self.view.requested_decision = None
        self.view.click(self.view.hitboxes["sergio"].center)
        self.assertEqual(self.view.requested_decision, decision.decision_id)
        self.assertEqual(self.view.outside, "sergio", "and they are still who is looked at")
        # Told what to do, they walk on.
        self.world.interventions.resolve(self.world, decision.decision_id, None)
        self._frames(10)
        self.assertGreater(self.trips.strides, strides)

    def test_once_they_are_back_in_the_map_is_shown_again_where_they_are(self) -> None:
        self._watch()
        self._frames(5)
        trip = self.sergio.expedition
        trip.find_at, trip.finds, trip.returns_at = None, 0, self.world.clock.total_minutes
        self.world.step(1)
        self.assertFalse(self.sergio.away)
        self.view.render()
        self.assertIsNone(self.view.outside)
        self.assertEqual(self.view.following, "sergio")
        self.assertIsNotNone(self.hud.minimap_rect)
        self.assertIn("sergio", self.view.hitboxes)

    def test_nothing_moves_the_map_from_out_there(self) -> None:
        self._watch()
        zoom, camera = self.view.zoom, list(self.view.camera)
        centre = self.view.viewport.center
        window = (centre[0] * SCALE, centre[1] * SCALE)
        self.view.handle_event(pygame.event.Event(pygame.MOUSEWHEEL, y=1, x=0))
        self.view.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=window))
        self.view.handle_event(
            pygame.event.Event(pygame.MOUSEMOTION, pos=(window[0] + 80, window[1] + 60), rel=(80, 60), buttons=(1, 0, 0))
        )
        self.view.handle_event(pygame.event.Event(pygame.MOUSEBUTTONUP, button=1, pos=(window[0] + 80, window[1] + 60)))
        self.view.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_i, mod=0, unicode="i"))
        self.assertEqual((self.view.zoom, list(self.view.camera)), (zoom, camera))
        self.assertIsNone(self.view.inside)
        self.assertIsNone(self.view.carry)
        self.assertEqual(self.view.outside, "sergio")

    def test_going_into_a_building_is_coming_back_from_out_there(self) -> None:
        self._watch()
        room_id = next(room_id for room_id in self.world.rooms if self.view.enterable(room_id))
        self.assertTrue(self.view.enter(room_id))
        self.assertEqual((self.view.outside, self.view.inside), (None, room_id))
        self.assertTrue(self.view.watch("sergio"))
        self.assertEqual((self.view.outside, self.view.inside), ("sergio", None))
        self.view.come_back()
        self.assertIsNotNone(self.hud.minimap_rect)

    def test_it_is_dark_after_dark_and_dusty_in_a_storm(self) -> None:
        self._watch()
        self.world.apply_command(SetPausedCommand(True))
        self.world.clock.hour, self.world.clock.minute = 12, 0
        sky = pygame.Rect(self._stage().x + 20, self._stage().y + 300, 200, 80)
        day = self._shown()
        self.world.clock.hour = 23
        night = self._shown()
        self.assertLess(_brightness(night, sky), _brightness(day, sky) * 0.6)
        self.world.clock.hour = 12
        self.world.weather = Weather("dust_storm", self.world.clock.total_minutes + 120)
        self.assertTrue(self.world.happenings.is_stormy(self.world))
        dusty = self._shown()
        self.assertLess(pygame.transform.average_color(dusty, sky)[2], pygame.transform.average_color(day, sky)[2])

    def test_the_way_of_the_trip_is_shown_in_the_sky_and_not_over_them(self) -> None:
        self._watch()
        self.view.render()
        bar = self.trips.bar_rect(self.sergio)
        self.assertTrue(self.view.viewport.contains(bar))
        self.assertFalse(bar.colliderect(self.view.hitboxes["sergio"]))
        self.assertLess(bar.bottom, self.view.viewport.centery)
        face = self.view.faces.marker("sergio")
        self.assertEqual(bar.height, trip_bar_height(self.view.font, bar.width, face.get_height(), trip_lines(self.world, self.sergio)))

    def test_a_trip_through_no_country_the_data_names_is_through_bare_country(self) -> None:
        self.sergio.expedition.zone = None
        self.world.registries.expeditions = type(self.world.registries.expeditions)(
            loot=self.world.registries.expeditions.loot, deliveries=self.world.registries.expeditions.deliveries
        )
        self.assertEqual(self.trips.zone_id(self.sergio), NOWHERE)
        self._watch()
        self._frames(3)
        self.assertEqual(self.view.outside, "sergio")
        self.assertEqual(trip_ends(self.world, self.sergio), (TRIP_HOME, "Fuera"))


class TripScreenWithNoWindowTests(_Shell):
    """With no window under the canvas there are no dolls: the game's own small body walks there."""

    illustrated = False

    def test_they_are_seen_all_the_same_on_the_canvas_itself(self) -> None:
        self._watch()
        self._frames(20)
        self.assertEqual(self.view.outside, "sergio")
        viewport = self.view.viewport
        self.assertGreater(len({tuple(self.view.canvas.get_at((x, viewport.centery + 60))) for x in range(viewport.x, viewport.right, 9)}), 3)
        box = self.view.hitboxes["sergio"]
        self.assertTrue(viewport.contains(box))
        before = self.trips.strides
        self._frames(20)
        self.assertGreater(self.trips.strides, before)


if __name__ == "__main__":
    unittest.main()
