"""Picked up and put down, on screen (P27): somebody is taken up with the mouse, hangs from it
while time stands still, and is put down on what the hand is over."""

import math
import os
import tempfile
import unittest
from pathlib import Path

import pygame

from scenes.carrying import HINT, IN_HAND_DEPTH, OUT_OF_HOURS, Carry, caption, hung
from scenes.global_view import DRAG_START
from settings import SCALE, TILE_SIZE
from simulation.ai.affect import TASK, USE
from simulation.ai.placing import POST, STAND, USE_IT
from simulation.commands import PutDownCommand
from simulation.justice.justice_system import PRISON
from simulation.justice.records import Sentence
from simulation.residents.activity import Order
from simulation.residents.needs import Needs
from ui.affect_wheel import SOCIAL


class _Shell(unittest.TestCase):
    """The game as it is played, with no window: the settlement that comes ready made, on the
    map at nine in the morning, with no grudges and nobody wanting for anything."""

    illustrated = False

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
        self.world.relationships.clear()
        self.world.clock.hour, self.world.clock.minute = 9, 0
        self._content()
        self.world.step(30)
        self._content()
        self.ines = self.world.residents["ines"]

    @staticmethod
    def _restore_driver(variable: str, previous: str | None) -> None:
        if previous is None:
            os.environ.pop(variable, None)
        else:
            os.environ[variable] = previous

    def _content(self) -> None:
        for resident in self.world.residents.values():
            resident.needs = Needs(hunger=0, thirst=0, tiredness=0, social=0, stress=0)

    def _frame(self, seconds: float = 0.0) -> None:
        self.view.update(seconds)
        self.view.render()

    def _look_at(self, resident_id: str) -> tuple[int, int]:
        """Bring somebody to the middle of the view. Returns a place on the canvas that is on them."""
        self.view.centre_on_resident(resident_id)
        self._frame()
        return self.view.hitboxes[resident_id].center

    def _mouse(self, kind: int, at: tuple[int, int], **more) -> None:
        self.view.handle_event(pygame.event.Event(kind, pos=(at[0] * SCALE + 1, at[1] * SCALE + 1), **more))

    def _press(self, at: tuple[int, int]) -> None:
        self._mouse(pygame.MOUSEBUTTONDOWN, at, button=1)

    def _move(self, at: tuple[int, int], held: bool = True) -> None:
        self._mouse(pygame.MOUSEMOTION, at, rel=(0, 0), buttons=(1 if held else 0, 0, 0))
        self._frame()

    def _release(self, at: tuple[int, int]) -> None:
        self._mouse(pygame.MOUSEBUTTONUP, at, button=1)

    def _take_up(self, resident_id: str) -> tuple[int, int]:
        """Press on somebody and pull away far enough to have them in the hand."""
        at = self._look_at(resident_id)
        self._press(at)
        self._move((at[0] + DRAG_START + 2, at[1]))
        self.assertIsNotNone(self.view.carry, f"{resident_id} was not taken up")
        return at

    def _over_tile(self, tile: tuple[int, int]) -> tuple[int, int]:
        """The place on the canvas of the middle of a tile of the map."""
        return self.view._tile_pixel(tile[0] + 0.5, tile[1] + 0.5)

    def _over_thing(self, object_id: str) -> tuple[int, int]:
        placed = self.world.interactables[object_id]
        return self.view._canvas_rect(self.view._object_area(placed)).center

    def _bare_tile(self, near: tuple[int, int]) -> tuple[int, int]:
        """A tile in the open near another, in view, that somebody could be stood on."""
        for reach in range(2, 9):
            for dx in range(-reach, reach + 1):
                for dy in range(-reach, reach + 1):
                    tile = (near[0] + dx, near[1] + dy)
                    found = self.world.placements("ines", tile=tile)
                    on_thing = any(
                        tile in placed.footprint(self.world.definition_of(placed))
                        for placed in self.world.interactables.values()
                    )
                    plain = found and found[0].kind == STAND and found[0].tile == tile and not on_thing
                    if plain and self.world.room_at(tile) is None and self.view._on_map(self._over_tile(tile)):
                        return tile
        raise AssertionError("no bare ground in view")


class TakingUpTests(_Shell):
    def test_pulling_away_from_somebody_takes_them_up_and_time_stands_still(self) -> None:
        at = self._look_at("ines")
        camera = list(self.view.camera)
        self.assertFalse(self.world.clock.paused)
        self._press(at)
        self.assertIsNone(self.view.carry, "a press alone takes nobody up")
        self._move((at[0] + DRAG_START - 1, at[1]))
        self.assertIsNone(self.view.carry, "nor a hand that has barely moved")
        self._move((at[0] + DRAG_START + 2, at[1]))
        carry = self.view.carry
        self.assertEqual((carry.who, carry.bundle, carry.sticky), ("ines", False, False))
        self.assertTrue(self.world.clock.paused)
        self.assertEqual(self.view.camera, camera, "it is them that come along, not the map")
        self.assertNotIn("ines", self.view.hitboxes, "nobody is picked out from under the hand")

    def test_a_click_on_them_still_only_selects_them(self) -> None:
        at = self._look_at("ines")
        self._press(at)
        self._release(at)
        self.assertIsNone(self.view.carry)
        self.assertEqual(self.hud.selected_id, "ines")
        self.assertFalse(self.world.clock.paused)

    def test_pulling_on_bare_ground_still_moves_the_map(self) -> None:
        self._look_at("ines")
        at = self._over_tile(self._bare_tile(self.ines.tile))
        camera = list(self.view.camera)
        self._press(at)
        self._move((at[0] - 30, at[1]))
        self._release((at[0] - 30, at[1]))
        self.assertIsNone(self.view.carry)
        self.assertNotEqual(self.view.camera, camera)
        self.assertIsNone(self.hud.selected_id)

    def test_whoever_cannot_be_taken_up_says_why_and_stays(self) -> None:
        self.world.courts.sentences.append(Sentence("ines", PRISON, "t1", self.world.clock.total_minutes + 600))
        at = self._look_at("ines")
        camera = list(self.view.camera)
        self._press(at)
        self._move((at[0] + 20, at[1]))
        self.assertIsNone(self.view.carry)
        self.assertIn("condena", self.hud.notice)
        self.assertEqual(self.view.camera, camera, "nor is the map pulled along instead")
        self.assertFalse(self.world.clock.paused)

    def test_the_other_button_lets_go_of_them_where_they_were(self) -> None:
        at = self._take_up("ines")
        before = self.ines.tile
        self._move(self._over_tile(self._bare_tile(before)))
        self._mouse(pygame.MOUSEBUTTONDOWN, at, button=3)
        self.assertIsNone(self.view.carry)
        self.assertEqual(self.ines.tile, before)
        self.assertFalse(self.world.clock.paused, "time goes on as it did")
        self._frame()
        self.assertIn("ines", self.view.hitboxes)

    def test_escape_lets_go_of_them_and_does_not_leave_the_settlement(self) -> None:
        self._take_up("ines")
        before = self.ines.tile
        self.game.handle_key(pygame.K_ESCAPE)
        self.assertEqual(self.game.scene_name, "global", "the map sees to the keys while somebody is in the hand")
        self.view.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE, unicode="", mod=0))
        self.assertIsNone(self.view.carry)
        self.assertEqual(self.ines.tile, before)

    def test_time_that_stood_still_already_goes_on_standing_still_after(self) -> None:
        self.game.handle_key(pygame.K_SPACE)
        self.assertTrue(self.world.clock.paused)
        self._take_up("ines")
        at = self._over_tile(self._bare_tile(self.ines.tile))
        self._move(at)
        self._release(at)
        self.assertIsNone(self.view.carry)
        self.assertTrue(self.world.clock.paused)

    def test_nothing_else_is_opened_while_somebody_is_in_the_hand(self) -> None:
        self._take_up("ines")
        for key in (pygame.K_j, pygame.K_l, pygame.K_f, pygame.K_u):
            self.view.handle_event(pygame.event.Event(pygame.KEYDOWN, key=key, unicode="", mod=0))
        self.assertFalse(self.hud.jobs_open or self.hud.log_open)
        self.assertFalse(self.view.requested_urbanism)
        self.game.handle_key(pygame.K_SPACE)
        self.assertTrue(self.world.clock.paused, "nor is time set going")
        self.assertIsNotNone(self.view.carry)

    def test_the_view_does_not_run_after_whoever_it_was_following_once_they_are_in_the_hand(self) -> None:
        self.hud.select_resident("ines")
        self._frame()
        self.assertEqual(self.view.following, "ines")
        at = self._take_up("ines")
        self._move((at[0] + 80, at[1] - 40))
        camera = list(self.view.camera)
        for _ in range(5):
            self.view.update(0.1)
        self.assertEqual(self.view.camera, camera)

    def test_a_hand_at_the_edge_of_the_map_pulls_the_view_along(self) -> None:
        self._take_up("ines")
        edge = (self.view.viewport.right - 2, self.view.viewport.centery)
        self._move(edge)
        camera = self.view.camera[0]
        self.view.update(0.2)
        self.assertGreater(self.view.camera[0], camera)
        self.assertIsNotNone(self.view.carry)


class PuttingDownTests(_Shell):
    def test_let_go_over_bare_ground_they_are_there_and_time_goes_on(self) -> None:
        self._take_up("ines")
        tile = self._bare_tile(self.ines.tile)
        at = self._over_tile(tile)
        self._move(at)
        self.assertEqual((self.view.carry.target.tile, self.view.carry.chosen.kind), (tile, STAND))
        self._release(at)
        self.assertIsNone(self.view.carry)
        self.assertEqual(self.ines.tile, tile)
        self.assertFalse(self.world.clock.paused)
        self.assertEqual(self.hud.selected_id, "ines")
        self.assertIsNone(self.view.following, "the view does not run after them")
        self._frame()
        self.assertTrue(self.view.hitboxes["ines"].collidepoint(at[0], at[1] - 4), "they stand where they were let go")

    def test_over_a_free_post_it_says_what_they_would_make_of_it_and_it_is_theirs(self) -> None:
        paco = self.world.residents["paco"]
        self.world.apply_command(PutDownCommand("paco", other_id="ines"))
        self._take_up("paco")
        at = self._over_thing("crop_2")
        self._move(at)
        carry = self.view.carry
        self.assertEqual((carry.target.object_id, carry.chosen.kind), ("crop_2", POST))
        lines, ok = caption(carry)
        self.assertTrue(ok)
        self.assertIn("Puesto: Huerto", lines[0])
        self.assertRegex(lines[0], r"x\d,\d · \d+/día")
        self.assertNotIn(OUT_OF_HOURS, lines[0])
        self.assertTrue(lines[1].startswith("Tab: "), "and what else could come of it")
        self._release(at)
        self.assertEqual((paco.job_id, paco.post_id), ("farmer", "crop_2"))
        self.assertEqual(self.hud.selected_id, "paco")

    def test_out_of_hours_it_says_so(self) -> None:
        self.world.clock.hour = 22
        self.world.apply_command(PutDownCommand("paco", other_id="ines"))
        self._take_up("paco")
        self._move(self._over_thing("crop_2"))
        self.assertIn(OUT_OF_HOURS, caption(self.view.carry)[0][0])

    def test_tab_goes_on_to_what_else_could_come_of_letting_go(self) -> None:
        self.world.apply_command(PutDownCommand("ines", object_id="water_tank", do=STAND))
        self._take_up("ines")
        at = self._over_thing("water_tank")
        self._move(at)
        carry = self.view.carry
        self.assertEqual([each.kind for each in carry.found], [POST, USE_IT, STAND])
        self.view.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_TAB, unicode="", mod=0))
        self.assertEqual(carry.chosen.kind, USE_IT)
        self.assertEqual(caption(carry)[0][0], "Beber")
        self._move((at[0] + 1, at[1]))
        self.assertEqual(carry.chosen.kind, USE_IT, "it is still what was chosen while the hand is over the same thing")
        self._release((at[0] + 1, at[1]))
        self.assertEqual(self.ines.job_id, "farmer")
        self.assertEqual(self.ines.doing, Order(f"{TASK}:{USE}", "water_tank"))

    def test_over_somebody_it_is_asked_what_the_two_are_to_do(self) -> None:
        self.world.apply_command(PutDownCommand("raul", other_id="ines"))
        self._take_up("ines")
        self._frame()
        at = self.view.hitboxes["raul"].center
        self._move(at)
        self.assertEqual(self.view.carry.target.other_id, "raul")
        self.assertIn("Raúl", caption(self.view.carry)[0][0])
        self._release(at)
        wheel = self.hud.wheel
        self.assertTrue(wheel.open)
        self.assertEqual((wheel.about, wheel.branch, wheel.person), ("ines", SOCIAL, "raul"))
        self.assertTrue(self.world.affect.is_held(self.world, "ines"), "they stand listening, beside them")

    def test_where_they_cannot_be_put_they_are_back_where_they_were(self) -> None:
        self._take_up("ines")
        before = self.ines.tile
        # Somewhere out in the open that nobody can stand on: a stretch of the fence, say.
        terrain = self.world.registries.terrain
        roofed = set().union(*self.view.roof_tiles.values())
        covered = {
            tile
            for placed in self.world.interactables.values()
            for tile in placed.footprint(self.world.definition_of(placed))
        }
        shut = next(
            (x, y)
            for y, row in enumerate(self.world.tile_map.tiles)
            for x, terrain_id in enumerate(row)
            if not terrain[terrain_id].walkable
            and (x, y) not in roofed
            and (x, y) not in covered
            and self.world.room_at((x, y)) is None
            and 4 < x < self.world.tile_map.width - 4
        )
        self.view.centre_on((shut[0] + 0.5, shut[1] + 0.5))
        self._frame()
        at = self._over_tile(shut)
        self._move(at)
        carry = self.view.carry
        self.assertEqual(carry.target.tile, shut)
        self.assertFalse(carry.chosen.ok)
        self.assertFalse(caption(carry)[1])
        self._release(at)
        self.assertIsNone(self.view.carry)
        self.assertEqual(self.ines.tile, before)
        self.assertTrue(self.hud.notice)
        self.assertFalse(self.world.clock.paused)

    def test_with_nothing_under_the_hand_it_says_what_to_do(self) -> None:
        self._take_up("ines")
        self.hud.toggle_jobs()
        self._frame()
        over_board = self.hud.jobs_rect().center
        self._move(over_board)
        self.assertIsNone(self.view.carry.target)
        self.assertEqual(caption(self.view.carry), ([HINT], True))
        self._release(over_board)
        self.assertIsNone(self.view.carry, "let go of over a board, they are where they were")


class IntoABuildingTests(_Shell):
    def _roof(self) -> tuple[str, tuple[int, int]]:
        """A building with its roof on that is in view once Inés is, and a tile of its roof."""
        self.view.centre_on((6, 5))
        self._frame()
        room_id = "dormitory"
        self.assertIn(room_id, self.view._closed)
        tile = next(tile for tile in sorted(self.view.roof_tiles[room_id]) if self.view._on_map(self._over_tile(tile)))
        return room_id, tile

    def _carry_into(self) -> str:
        self.world.apply_command(PutDownCommand("ines", tile=(6, 12)))
        self.before = self.ines.tile
        self._take_up("ines")
        room_id, tile = self._roof()
        at = self._over_tile(tile)
        self._move(at)
        self.assertEqual(self.view.carry.target.room_id, room_id)
        self.assertIn("Entrar", caption(self.view.carry, "Entrar en X")[0][0])
        self._release(at)
        return room_id

    def _floor_place(self, room_id: str, wanted) -> tuple[int, int]:
        """A place on the canvas, inside, over a tile of the floor that `wanted` says will do."""
        room = self.world.rooms[room_id]
        viewport = self.view.viewport
        for y in range(viewport.top + 4, viewport.bottom - 4, 3):
            for x in range(viewport.left + 4, viewport.right - 4, 3):
                tile = self.view.interior.tile_under(room, (x, y))
                if tile is not None and not self.hud.covers((x, y)) and wanted(tile):
                    return (x, y)
        raise AssertionError("nowhere on the floor will do")

    def test_over_a_roof_the_building_is_gone_into_with_them_still_in_the_hand(self) -> None:
        room_id = self._carry_into()
        self.assertEqual(self.view.inside, room_id)
        carry = self.view.carry
        self.assertTrue(carry is not None and carry.sticky, "they are put down in there, with a click")
        self.assertEqual(self.ines.tile, self.before, "they are nowhere new until they are put down")
        self.assertTrue(self.world.clock.paused)
        self._frame()
        self.assertNotIn("ines", self.view.hitboxes)

    def test_a_click_in_there_puts_them_down_where_it_is(self) -> None:
        room_id = self._carry_into()
        room = self.world.rooms[room_id]

        def bare(tile) -> bool:
            found = self.world.placements("ines", tile=tile)
            return bool(found) and found[0].kind == STAND and found[0].tile == tile

        at = self._floor_place(room_id, bare)
        self._move(at, held=False)
        tile = self.view.carry.target.tile
        self._press(at)
        self.assertIsNone(self.view.carry)
        self.assertEqual(self.ines.tile, tile)
        self.assertTrue(room.contains(self.ines.tile))
        self.assertEqual(self.view.inside, room_id, "and the building is still being looked at")
        self.assertFalse(self.world.clock.paused)
        self._frame()
        self.assertIn("ines", self.view.hitboxes)

    def test_put_down_on_a_bed_in_there_they_sleep_in_it(self) -> None:
        room_id = self._carry_into()
        bed = self.world.interactables["bed_1"]
        self.ines.needs.tiredness = 60.0
        at = self._floor_place(room_id, lambda tile: tile == (bed.x, bed.y))
        self._move(at, held=False)
        self.assertEqual(self.view.carry.chosen.kind, USE_IT)
        self.assertEqual(caption(self.view.carry)[0][0], "Dormir")
        self._press(at)
        self.assertEqual(self.ines.doing, Order(f"{TASK}:{USE}", "bed_1"))
        self.assertEqual(self.ines.tile, (bed.x, bed.y))

    def test_the_other_button_in_there_lets_go_of_them_where_they_were(self) -> None:
        room_id = self._carry_into()
        self._mouse(pygame.MOUSEBUTTONDOWN, self.view.viewport.center, button=3)
        self.assertIsNone(self.view.carry)
        self.assertEqual((self.ines.tile, self.view.inside), (self.before, room_id))
        self.assertFalse(self.world.clock.paused)

    def test_going_back_out_with_them_in_the_hand_they_are_put_down_out_there(self) -> None:
        self._carry_into()
        self.view.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_i, unicode="i", mod=0))
        self.assertIsNone(self.view.inside)
        self.assertTrue(self.view.carry is not None and self.view.carry.sticky, "a click puts them down out here too")
        self._frame()
        tile = self._bare_tile((6, 12))
        at = self._over_tile(tile)
        self._move(at, held=False)
        self._press(at)
        self.assertIsNone(self.view.carry)
        self.assertEqual(self.ines.tile, tile)

    def test_somebody_in_there_is_taken_up_and_put_down_in_there_too(self) -> None:
        self.world.apply_command(PutDownCommand("ines", object_id="bed_1", do=STAND))
        self.assertTrue(self.view.enter("dormitory"))
        self._frame()
        at = self.view.hitboxes["ines"].center
        self._press(at)
        self.assertEqual(self.hud.selected_id, "ines", "a press in there is a click, as it was")
        self._move((at[0] + DRAG_START + 2, at[1]))
        carry = self.view.carry
        self.assertEqual((carry.who, carry.sticky), ("ines", False))
        bed = self.world.interactables["bed_7"]
        self.ines.needs.tiredness = 60.0
        over = self._floor_place("dormitory", lambda tile: tile == (bed.x, bed.y))
        self._move(over)
        self._release(over)
        self.assertIsNone(self.view.carry)
        self.assertEqual(self.ines.doing, Order(f"{TASK}:{USE}", "bed_7"))


class BundleTests(_Shell):
    def setUp(self) -> None:
        super().setUp()
        self.ines.expecting_with = "tomas"
        self.bundle = self.world.children.give_birth(self.world, self.ines)

    def test_a_child_is_taken_off_a_back_and_put_in_the_arms_of_somebody_else(self) -> None:
        self.world.apply_command(PutDownCommand("vera", other_id="ines"))
        self._look_at("ines")
        box = self.view.bundle_boxes[self.bundle.child_id]
        self._press(box.center)
        self._move((box.centerx, box.centery - DRAG_START - 2))
        carry = self.view.carry
        self.assertEqual((carry.who, carry.bundle), (self.bundle.child_id, True))
        self.assertTrue(self.world.clock.paused)
        self._frame()
        self.assertNotIn(self.bundle.child_id, self.view.bundle_boxes)
        at = self.view.hitboxes["vera"].center
        self._move(at)
        self.assertIn("Vera", caption(carry)[0][0])
        self._release(at)
        self.assertIsNone(self.view.carry)
        self.assertEqual((self.bundle.carried_by, self.bundle.keeper), ("vera", "vera"))
        self.assertFalse(self.world.clock.paused)

    def test_let_go_over_the_ground_it_is_laid_there(self) -> None:
        self._look_at("ines")
        box = self.view.bundle_boxes[self.bundle.child_id]
        self._press(box.center)
        self._move((box.centerx, box.centery - DRAG_START - 2))
        tile = self._bare_tile(self.ines.tile)
        at = self._over_tile(tile)
        self._move(at)
        self._release(at)
        self.assertEqual((self.bundle.tile, self.bundle.set_down, self.bundle.carried_by), (tile, True, None))
        self._frame()
        self.assertIn(self.bundle.child_id, self.view.bundle_boxes)


class HangingTests(unittest.TestCase):
    def test_a_hand_that_moves_throws_them_back_and_they_come_to_rest_under_it(self) -> None:
        carry = Carry("ines")
        carry.swing(100.0, 1 / 60)
        self.assertEqual(carry.angle, 0.0, "nothing to go by on the first look")
        x = 100.0
        for _ in range(12):
            x += 6.0
            carry.swing(x, 1 / 60)
        self.assertGreater(carry.angle, 0.15, "moving right, they trail to the left of the hand")
        furthest = abs(carry.angle)
        swung_back = False
        for _ in range(600):
            carry.swing(x, 1 / 60)
            swung_back = swung_back or carry.angle < -0.02
            furthest = max(furthest, abs(carry.angle))
        self.assertTrue(swung_back, "they swing past straight down before they settle")
        self.assertLess(abs(carry.angle), 0.01)
        self.assertLess(furthest, 1.4)

    def test_what_is_further_from_the_hand_swings_further(self) -> None:
        still = {"neck": (0.0, 0.0), "hip": (0.0, 10.0), "foot": (0.0, 20.0)}
        self.assertEqual(hung(still, (0.0, 0.0), 0.0), still)
        swung = hung(still, (0.0, 0.0), 0.5)
        self.assertEqual(swung["neck"], (0.0, 0.0))
        self.assertLess(swung["foot"][0], swung["hip"][0], "feet trail to the left of a hand moving right")
        self.assertLess(swung["hip"][0], 0.0)
        for name, (x, y) in swung.items():
            self.assertAlmostEqual(math.hypot(x, y), math.hypot(*still[name]), places=6, msg="nothing is stretched")
        hip, foot = math.atan2(-swung["hip"][0], swung["hip"][1]), math.atan2(-swung["foot"][0], swung["foot"][1])
        self.assertGreater(foot, hip)


class ShownTests(_Shell):
    illustrated = True

    def test_whoever_is_in_the_hand_is_drawn_under_it_in_front_of_everything(self) -> None:
        at = self._take_up("ines")
        self._move((at[0] + 30, at[1] - 10))
        self.view.render()
        held = [entry for entry in self.view._doll_draws if entry[0] == IN_HAND_DEPTH]
        self.assertEqual(len(held), 1)
        skeleton = held[0][2]
        top = min(joint.y for joint in skeleton.joints.values())
        middle = sum(joint.x for joint in skeleton.joints.values()) / len(skeleton.joints)
        pointer = self.view._map_point(self.view.pointer)
        self.assertLess(abs(top - pointer[1]), TILE_SIZE, "their head is at the hand")
        self.assertLess(abs(middle - pointer[0]), TILE_SIZE)

    def test_from_afar_their_face_goes_with_the_hand(self) -> None:
        at = self._take_up("ines")
        self.view.set_zoom(0)
        self._move((at[0] + 30, at[1] - 10))
        with self.assertNoLogs("graphics.assets", level="WARNING"):
            self.view.render()
        self.assertNotIn("ines", self.view.hitboxes)

    def test_inside_a_building_too(self) -> None:
        self._take_up("ines")
        self.assertTrue(self.view.enter("dormitory"))
        self.view.carry.sticky = True
        self._move(self.view.viewport.center, held=False)
        with self.assertNoLogs("graphics.assets", level="WARNING"):
            self.view.render()
        self.assertNotIn("ines", self.view.hitboxes)
        self.assertIsNotNone(self.view.carry.target)


if __name__ == "__main__":
    unittest.main()
