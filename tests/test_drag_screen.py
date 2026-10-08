import os
import unittest

import pygame

from scenes.dragging import BUNDLE, DANGLE_CLIP, ITEM, LIFT_SECONDS, SOMEBODY, THING, Held
from scenes.global_view import DRAG_START
from settings import SCALE, TILE_SIZE
from simulation.ai.placing import OBJECT, POST, USE
from simulation.commands import ProposeObjectCommand
from simulation.family.children import CARRIED
from simulation.residents.activity import HEED_ACTION
from simulation.residents.needs import Needs
from simulation.work.expedition import Expedition
from skeleton.plan import builtin_plan
from ui.affect_wheel import SOCIAL, put_down_intent, target_intent


class DragScreenTests(unittest.TestCase):
    """Picking up and putting down with the mouse (P27), through the real game without a window."""

    def setUp(self) -> None:
        for variable in ("SDL_VIDEODRIVER", "SDL_AUDIODRIVER"):
            self.addCleanup(self._restore_driver, variable, os.environ.get(variable))
            os.environ[variable] = "dummy"
        from game.game import Game

        self.game = Game(illustrations_dir=None, voices_dir=None, start_in_menu=False)
        self.addCleanup(pygame.quit)
        self.view = self.game.global_view
        self.hud = self.view.hud
        self.drag = self.view.drag
        self.world = self.game.world
        self.world.relationships.clear()
        for resident in self.world.residents.values():
            resident.needs = Needs(hunger=0, tiredness=0, social=0, stress=0)
        self.world.decisions.clear()
        self._frame()

    @staticmethod
    def _restore_driver(variable: str, previous: str | None) -> None:
        if previous is None:
            os.environ.pop(variable, None)
        else:
            os.environ[variable] = previous

    def _frame(self, seconds: float = 0.0) -> None:
        self.view.update(seconds)
        self.view.render()

    def _event(self, kind: int, position: tuple[int, int], **more) -> None:
        window = (position[0] * SCALE, position[1] * SCALE)
        self.view.handle_event(pygame.event.Event(kind, pos=window, **more))

    def _press(self, position: tuple[int, int]) -> None:
        self._event(pygame.MOUSEBUTTONDOWN, position, button=1)

    def _move(self, position: tuple[int, int]) -> None:
        self._event(pygame.MOUSEMOTION, position, rel=(1, 1), buttons=(1, 0, 0))
        self._frame()

    def _release(self, position: tuple[int, int]) -> None:
        self._event(pygame.MOUSEBUTTONUP, position, button=1)
        self._frame()

    def _show(self, tile: tuple[float, float]) -> None:
        self.view.centre_on(tile)
        self._frame()

    def _pick_up(self, resident_id: str) -> tuple[int, int]:
        """Take a resident off the map with the mouse. Returns where the pointer is left."""
        resident = self.world.residents[resident_id]
        self._show((resident.x + 0.5, resident.y + 0.5))
        start = self.view.hitboxes[resident_id].center
        self._press(start)
        held = (start[0] + DRAG_START + 3, start[1])
        self._move(held)
        return held

    def _free_ground(self) -> tuple[int, int]:
        """A canvas position on the map with nothing but ground under whoever hangs from it."""
        view = self.view
        centre = view.viewport.center
        for dy in range(-80, 81, 16):
            for dx in range(-120, 121, 16):
                point = (centre[0] + dx, centre[1] + dy)
                if not view._on_map(point):
                    continue
                self._move(point)
                target = self.drag.target
                if target is not None and target.ok and target.lands is not None:
                    return point
        self.fail("no bare ground in view")

    # ----- picking up -----

    def test_dragging_somebody_picks_them_up_and_leaves_the_view_where_it_was(self) -> None:
        raul = self.world.residents["raul"]
        self._show((raul.x + 0.5, raul.y + 0.5))
        camera = list(self.view.camera)
        start = self.view.hitboxes["raul"].center
        self._press(start)
        self.assertFalse(self.drag.active, "a press is not yet a pick-up")
        self._move((start[0] + DRAG_START + 3, start[1]))
        self.assertEqual(self.drag.held, Held(SOMEBODY, "raul"))
        self.assertEqual(self.view.camera, camera, "the map does not go with the mouse")
        self.assertEqual(raul.activity.action, HEED_ACTION, "he leaves off what he was at")
        self.assertEqual(self.hud.selected_id, "raul")

    def test_dragging_bare_ground_still_moves_the_view(self) -> None:
        raul = self.world.residents["raul"]
        self._show((raul.x + 0.5, raul.y + 0.5))
        view = self.view
        empty = next(
            (x, y)
            for y in range(view.viewport.top + 40, view.viewport.bottom - 40, 8)
            for x in range(view.viewport.left + 40, view.viewport.right - 40, 8)
            if view._on_map((x, y)) and self.drag.what_at((x, y)) is None
        )
        camera = list(view.camera)
        self._press(empty)
        self._move((empty[0] - 20, empty[1] - 12))
        self.assertFalse(self.drag.active)
        self.assertNotEqual(view.camera, camera)
        self._release((empty[0] - 20, empty[1] - 12))

    def test_a_click_on_somebody_is_still_a_click(self) -> None:
        raul = self.world.residents["raul"]
        self._show((raul.x + 0.5, raul.y + 0.5))
        start = self.view.hitboxes["raul"].center
        self._press(start)
        self._release(start)
        self.assertFalse(self.drag.active)
        self.assertEqual(self.hud.selected_id, "raul")
        self.assertNotEqual(raul.activity.action if raul.activity else "", HEED_ACTION)

    def test_whoever_hangs_from_the_pointer_is_drawn_there_and_is_nobody_to_point_at(self) -> None:
        raul = self.world.residents["raul"]
        where = self._pick_up("raul")
        far = (where[0] + 90, where[1] - 40)
        self._move(far)
        self.assertNotIn("raul", self.view.hitboxes)
        x, y, _, stride = self.view._walk_state(raul)
        self.assertIsNone(stride)
        point = self.view._map_point(far)
        self.assertLess(abs((x + 0.5) * TILE_SIZE - point[0]), TILE_SIZE)
        self.assertGreater((y + 1) * TILE_SIZE, point[1], "he hangs under it")
        self.assertEqual((raul.x, raul.y), raul.tile, "in the settlement he has not moved yet")

    def test_the_body_that_hangs_has_a_clip_of_its_own_from_both_sides(self) -> None:
        plan = builtin_plan()
        self.assertIn(DANGLE_CLIP, plan.clips)
        self.assertIn(DANGLE_CLIP, plan.once)
        for view in ("front", "side"):
            self.assertGreaterEqual(plan.frames(DANGLE_CLIP, view), 3)
        standing = plan.pose("right")
        for phase in (0.0, 0.5, 1.0):
            hanging = plan.pose("right", DANGLE_CLIP, phase)
            self.assertLess(max(y for _, y in hanging.values()), max(y for _, y in standing.values()), "off the ground")
        behind, ahead = plan.pose("right", DANGLE_CLIP, 0.0), plan.pose("right", DANGLE_CLIP, 1.0)
        self.assertLess(behind["foot_left"][0], ahead["foot_left"][0] - 4, "the legs swing plainly")

    def test_the_legs_trail_behind_the_hand_as_it_goes(self) -> None:
        where = self._pick_up("raul")
        for step in range(1, 12):
            self._event(pygame.MOUSEMOTION, (where[0] + step * 8, where[1]), rel=(8, 0), buttons=(1, 0, 0))
            self._frame(1 / 30)
        self.assertLess(self.drag.swing, 0.35)
        for _ in range(60):
            self._frame(1 / 30)
        self.assertLess(abs(self.drag.swing - 0.5), 0.2, "still, they hang straight again, kicking a little")

    def test_somebody_who_cannot_be_told_anything_stays_on_the_ground(self) -> None:
        raul = self.world.residents["raul"]
        self._show((raul.x + 0.5, raul.y + 0.5))
        start = self.view.hitboxes["raul"].center
        self.world.leaving["raul"] = self.world.clock.total_minutes
        self._press(start)
        self._move((start[0] + DRAG_START + 3, start[1]))
        self.assertFalse(self.drag.active)
        self.assertTrue(self.hud.notice)

    # ----- putting down -----

    def test_let_go_over_bare_ground_they_are_there(self) -> None:
        raul = self.world.residents["raul"]
        self._pick_up("raul")
        point = self._free_ground()
        target = self.drag.target
        self.assertIn("se quedará aquí", target.text)
        self._release(point)
        self.assertFalse(self.drag.active)
        self.assertEqual(raul.tile, target.lands)
        self.assertIn("raul", self.view.hitboxes, "back on the map to be pointed at")
        self.assertFalse(self.world.affect.is_held(self.world, "raul"))

    def test_the_other_button_or_escape_lets_go_with_nothing_done(self) -> None:
        raul = self.world.residents["raul"]
        for cancel in ("button", "key"):
            before = raul.tile
            where = self._pick_up("raul")
            self._move((where[0] + 60, where[1] + 30))
            if cancel == "button":
                self._event(pygame.MOUSEBUTTONDOWN, (where[0] + 60, where[1] + 30), button=3)
            else:
                self.view.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE, unicode=""))
            self._frame()
            self.assertFalse(self.drag.active)
            self.assertEqual(raul.tile, before)
            self.assertFalse(self.world.affect.is_held(self.world, "raul"))
            self._release((where[0] + 60, where[1] + 30))
            self.assertEqual(raul.tile, before, "the button coming up afterwards is nothing")

    def test_escape_with_somebody_in_the_hand_does_not_leave_the_settlement(self) -> None:
        self._pick_up("raul")
        self.game.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE, unicode=""))
        self.assertEqual(self.game.scene_name, "global")
        self.assertFalse(self.drag.active)

    def test_leaving_the_settlement_for_another_screen_lets_go_of_them(self) -> None:
        raul = self.world.residents["raul"]
        before = raul.tile
        self._pick_up("raul")
        self.game.open_menu()
        self.game.sync_scenes()
        self.assertFalse(self.drag.active)
        self.assertEqual(raul.tile, before)
        self.assertFalse(self.world.affect.is_held(self.world, "raul"))

    def test_let_go_off_the_map_they_are_back_where_they_were(self) -> None:
        raul = self.world.residents["raul"]
        before = raul.tile
        self._pick_up("raul")
        panel = self.hud.layout.panel.center
        self._move(panel)
        self.assertFalse(self.drag.target.ok)
        self._release(panel)
        self.assertEqual(raul.tile, before)
        self.assertFalse(self.world.affect.is_held(self.world, "raul"))

    def test_over_a_thing_it_lights_up_and_says_what_would_come_of_it(self) -> None:
        raul = self.world.residents["raul"]
        raul.needs.hunger = 60
        self._pick_up("raul")
        pantry = self.world.interactables["pantry_1"]
        self.view.roofs_on = False
        self._show((pantry.x + 0.5, pantry.y + 1.5))
        point = self.view.object_boxes["pantry_1"].center
        self._move(point)
        target = self.drag.target
        self.assertEqual((target.on_kind, target.on_id), (OBJECT, "pantry_1"))
        self.assertEqual(target.box, self.view.object_boxes["pantry_1"])
        self.assertIn("comerá", target.text)
        self._release(point)
        self.assertEqual(raul.activity.target_id, "pantry_1")
        self.assertLessEqual(abs(raul.x - pantry.x) + abs(raul.y - pantry.y), 2)
        # It is among what he has been told, to be taken back like anything else.
        told = self.hud.queue_entries()
        self.assertEqual([(entry.icon, entry.doing) for entry in told], [("food", True)])
        self.view.click(told[0].rect.center)
        self._frame()
        self.assertIsNone(raul.activity)

    def test_over_a_building_with_its_roof_on_it_is_the_building(self) -> None:
        raul = self.world.residents["raul"]
        self._pick_up("raul")
        room = self.world.rooms["storehouse"]
        middle = (room.x + room.width / 2, room.y + room.height / 2)
        self._show(middle)
        point = self.view._canvas_point(middle[0] * TILE_SIZE, middle[1] * TILE_SIZE)
        self._move(point)
        target = self.drag.target
        self.assertEqual(target.on_id, "storehouse")
        self.assertIn("entrará", target.text)
        self._release(point)
        self.assertTrue(room.contains(raul.tile))

    def test_let_go_on_somebody_the_wheel_opens_on_what_the_two_can_do(self) -> None:
        raul, marta = self.world.residents["raul"], self.world.residents["marta"]
        marta.x, marta.y = raul.x + 3, raul.y
        self._pick_up("raul")
        self._frame()
        point = self.view.hitboxes["marta"].center
        self._move(point)
        self.assertEqual(self.drag.target.on_id, "marta")
        self._release(point)
        wheel = self.hud.wheel
        self.assertTrue(wheel.open)
        self.assertEqual((wheel.about, wheel.branch, wheel.person), ("raul", SOCIAL, "marta"))
        self.assertLessEqual(abs(raul.x - marta.x) + abs(raul.y - marta.y), 1, "he is beside her already")
        self.assertEqual(raul.activity.action, HEED_ACTION)
        entries = {entry.intent: entry for entry in self.hud.wheel_entries()}
        talk = target_intent("with:talk", "marta")
        self.assertIn(talk, entries)
        self.view.click(entries[talk].rect.center)
        self._frame()
        self.assertFalse(wheel.open)
        self.assertEqual(raul.activity.partner_id, "marta")

    def test_on_a_thing_that_is_a_post_and_is_used_the_wheel_asks_which(self) -> None:
        self.world.step(60 * 3)
        raul = self.world.residents["raul"]
        raul.needs = Needs(hunger=0, tiredness=0, social=0, stress=0, thirst=50)
        self._pick_up("raul")
        tank = self.world.interactables["water_tank"]
        self._show((tank.x + 1.0, tank.y + 1.0))
        point = self.view.object_boxes["water_tank"].center
        self._move(point)
        self.assertIn("elige", self.drag.target.text)
        self._release(point)
        wheel = self.hud.wheel
        self.assertTrue(wheel.open)
        self.assertEqual((wheel.about, wheel.thing), ("raul", "water_tank"))
        entries = {entry.intent: entry for entry in self.hud.wheel_entries()}
        self.assertIn(put_down_intent(USE), entries)
        self.assertIn(put_down_intent(POST), entries)
        self.assertEqual(raul.job_id, "farmer", "nothing is his that has not been said")
        self.view.click(entries[put_down_intent(USE)].rect.center)
        self._frame()
        self.assertFalse(wheel.open)
        self.assertEqual(raul.activity.target_id, "water_tank")
        self.assertEqual(raul.job_id, "farmer")

    def test_shutting_the_wheel_leaves_them_where_they_were_put(self) -> None:
        raul = self.world.residents["raul"]
        self._pick_up("raul")
        tank = self.world.interactables["water_tank"]
        self._show((tank.x + 1.0, tank.y + 1.0))
        point = self.view.object_boxes["water_tank"].center
        self._move(point)
        self._release(point)
        if not self.hud.wheel.open:
            self.skipTest("it came to one thing only")
        self._event(pygame.MOUSEBUTTONDOWN, point, button=3)
        self._frame()
        self.assertFalse(self.hud.wheel.open)
        self.assertFalse(self.world.affect.is_held(self.world, "raul"))
        self.assertLessEqual(abs(raul.x - tank.x) + abs(raul.y - tank.y), 4)

    # ----- things that stand on the map -----

    def test_a_thing_comes_up_only_after_the_button_is_held_on_it(self) -> None:
        stool = self.world.interactables["stool_5"]
        before = (stool.x, stool.y)
        self._show((stool.x + 0.5, stool.y + 0.5))
        start = self.view.object_boxes["stool_5"].center
        camera = list(self.view.camera)
        self._press(start)
        self._move((start[0] + 30, start[1] + 6))
        self.assertFalse(self.drag.active, "dragged at once, it is the map that moves")
        self.assertNotEqual(self.view.camera, camera)
        self._release((start[0] + 30, start[1] + 6))
        self.assertEqual((stool.x, stool.y), before)

        self._show((stool.x + 0.5, stool.y + 0.5))
        start = self.view.object_boxes["stool_5"].center
        self._press(start)
        self._frame(LIFT_SECONDS / 2)
        self.assertFalse(self.drag.active)
        self._frame(LIFT_SECONDS)
        self.assertEqual(self.drag.held, Held(THING, "stool_5"))

    def test_a_thing_is_put_down_where_there_is_room_for_it_and_nowhere_else(self) -> None:
        stool = self.world.interactables["stool_5"]
        self._show((stool.x + 0.5, stool.y + 0.5))
        start = self.view.object_boxes["stool_5"].center
        self._press(start)
        self._frame(LIFT_SECONDS + 0.05)
        self.assertTrue(self.drag.active)
        # Onto the table beside it: there is no room there.
        table = self.view.object_boxes["table"].center
        self._move(table)
        self.assertFalse(self.drag.target.ok)
        before = (stool.x, stool.y)
        self._release(table)
        self.assertEqual((stool.x, stool.y), before)

        self._show((stool.x + 0.5, stool.y + 0.5))
        start = self.view.object_boxes["stool_5"].center
        self._press(start)
        self._frame(LIFT_SECONDS + 0.05)
        free = None
        for dy in (48, 64, 80, -48):
            for dx in (0, 16, -16, 32, -32):
                self._move((start[0] + dx, start[1] + dy))
                if self.drag.target is not None and self.drag.target.ok:
                    free = (start[0] + dx, start[1] + dy)
                    break
            if free is not None:
                break
        self.assertIsNotNone(free, "no room for a stool anywhere near")
        tile = self.drag.target.tile
        self._release(free)
        self.assertEqual((stool.x, stool.y), tile)
        self.assertFalse(self.drag.active)

    # ----- a child in its blanket -----

    def test_a_child_is_dragged_into_the_arms_of_somebody(self) -> None:
        ines, raul = self.world.residents["ines"], self.world.residents["raul"]
        ines.expecting_with = "tomas"
        bundle = self.world.children.give_birth(self.world, ines)
        for parent in ("ines", "tomas"):
            self.world.residents[parent].expedition = Expedition(returns_at=10**9, finds=0, danger=0.0)
        self.world.step(2)
        self.assertIsNone(bundle.carried_by)
        raul.x, raul.y = bundle.x + 3, bundle.y
        # It may have been put down under a roof: with the roofs off it is there to be seen.
        self.view.roofs_on = False
        self._show((bundle.x + 0.5, bundle.y + 0.5))
        start = self.view.bundle_boxes[bundle.child_id].center
        self._press(start)
        self._move((start[0] + DRAG_START + 3, start[1]))
        self.assertEqual(self.drag.held, Held(BUNDLE, bundle.child_id))
        self.assertNotIn(bundle.child_id, self.view.bundle_boxes)
        ground = (start[0] + 20, start[1] + 60)
        self._move(ground)
        if self.view.hitboxes["raul"].collidepoint(ground):
            ground = (start[0] - 30, start[1] + 60)
            self._move(ground)
        self.assertFalse(self.drag.target.ok, "a child is not left lying about")
        point = self.view.hitboxes["raul"].center
        self._move(point)
        self.assertTrue(self.drag.target.ok)
        self._release(point)
        self.assertEqual((bundle.minded_by, bundle.carried_by, bundle.place), ("raul", "raul", CARRIED))

    # ----- things carried and kept -----

    def _with_item(self, resident_id: str):
        resident = self.world.residents[resident_id]
        resident.inventory.items.clear()
        item = self.world.new_item(self.world.registries.items.ids()[0], 2, resident_id)
        resident.inventory.add(item)
        return item

    def test_a_thing_is_dragged_out_of_the_panel_into_the_hands_of_somebody(self) -> None:
        raul, marta = self.world.residents["raul"], self.world.residents["marta"]
        item = self._with_item("raul")
        marta.x, marta.y = raul.x + 2, raul.y
        self.hud.select_resident("raul")
        self._show((raul.x + 0.5, raul.y + 0.5))
        cell = self.hud._inventory_items()[0][0].center
        self.assertEqual(self.hud.item_at(cell), item.instance_id)
        self._press(cell)
        self.assertIsNone(self.view.requested_item_editor, "a press is not yet a click")
        self._move((cell[0] - 20, cell[1]))
        self.assertEqual(self.drag.held, Held(ITEM, item.instance_id))
        self.assertFalse(self.drag.target.ok, "over nothing it can be left on")
        point = self.view.hitboxes["marta"].center
        self._move(point)
        self.assertTrue(self.drag.target.ok)
        self.assertIn("Marta", self.drag.target.text)
        self._release(point)
        self.assertFalse(self.drag.active)
        self.assertIsNone(raul.inventory.find(item.instance_id))
        self.assertEqual(marta.inventory.find(item.instance_id).owner_id, "marta")
        self.assertGreater(self.world.relationship("raul", "marta").resentment, 0.0)

    def test_a_thing_is_dragged_onto_a_name_in_the_panel(self) -> None:
        raul = self.world.residents["raul"]
        item = self._with_item("raul")
        self.world.relationship("raul", "marta").affection = 20
        self.hud.select_resident("raul")
        self._show((raul.x + 0.5, raul.y + 0.5))
        row = next(box for box, resident_id in self.hud.listed() if resident_id == "marta")
        cell = self.hud._inventory_items()[0][0].center
        self._press(cell)
        self._move((cell[0] - 12, cell[1] - 12))
        self._move(row.center)
        self.assertTrue(self.drag.target.ok)
        self._release(row.center)
        self.assertIsNotNone(self.world.residents["marta"].inventory.find(item.instance_id))

    def test_a_click_on_a_thing_in_the_panel_is_still_a_click(self) -> None:
        raul = self.world.residents["raul"]
        item = self._with_item("raul")
        self.hud.select_resident("raul")
        self._show((raul.x + 0.5, raul.y + 0.5))
        cell = self.hud._inventory_items()[0][0].center
        self._press(cell)
        self._release(cell)
        self.assertEqual(self.view.requested_item_editor, item.definition_id)
        self.assertIsNotNone(raul.inventory.find(item.instance_id))

    def test_let_go_over_nothing_a_thing_is_back_where_it_was(self) -> None:
        raul = self.world.residents["raul"]
        item = self._with_item("raul")
        self.hud.select_resident("raul")
        self._show((raul.x + 0.5, raul.y + 0.5))
        cell = self.hud._inventory_items()[0][0].center
        self._press(cell)
        self._move((cell[0] - 20, cell[1]))
        self._release((cell[0] - 20, cell[1]))
        self.assertIsNotNone(raul.inventory.find(item.instance_id))
        self.assertFalse(self.drag.active)

    # ----- the wheel and the inside -----

    def test_nothing_is_picked_up_with_the_wheel_open_or_from_inside(self) -> None:
        raul = self.world.residents["raul"]
        self._show((raul.x + 0.5, raul.y + 0.5))
        self.hud.select_resident("raul")
        self.view._toggle_affect()
        self._frame()
        self.assertTrue(self.hud.wheel.open)
        self.assertIsNone(self.drag.what_at(self.view.hitboxes["raul"].center))
        self.view._close_wheel()
        self.assertTrue(self.view.enter("storehouse"))
        self._frame()
        self.assertIsNone(self.drag.what_at(self.view.viewport.center))

    def test_going_inside_lets_go_of_whoever_is_in_the_hand(self) -> None:
        raul = self.world.residents["raul"]
        before = raul.tile
        self._pick_up("raul")
        self.assertTrue(self.view.enter("storehouse"))
        self.assertFalse(self.drag.active)
        self.assertEqual(raul.tile, before)
        self.assertFalse(self.world.affect.is_held(self.world, "raul"))

    def test_a_site_takes_whoever_is_put_down_on_it(self) -> None:
        self.world.step(60)
        proposed = self.world.apply_command(ProposeObjectCommand("lamp", (20, 18), "marta"))
        if not proposed.ok or not self.world.sites:
            self.skipTest("nobody would put it up")
        site = next(iter(self.world.sites.values()))
        self.world.decisions.clear()
        self._pick_up("raul")
        self._show((site.x + 0.5, site.y + 0.5))
        point = self.view.site_boxes[site.site_id].center
        self._move(point)
        self.assertEqual(self.drag.target.on_id, site.site_id)
        self._release(point)
        self.assertEqual(site.in_charge, "raul")


if __name__ == "__main__":
    unittest.main()
