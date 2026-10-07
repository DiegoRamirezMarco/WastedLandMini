import os
import tempfile
import unittest
from pathlib import Path

import pygame

from scenes.interior_view import DEPTH, GROWTH, WALL, door_columns, draw_shell, layout_for
from settings import SCALE
from simulation.residents.activity import Activity
from simulation.world import SimulationWorld
from world.room import Room

AREA = pygame.Rect(0, 0, 1092, 848)


class InteriorLayoutTests(unittest.TestCase):
    """Where the parts of a room seen from inside fall. Nothing here needs a window."""

    def test_the_inside_is_twice_as_wide_and_twice_as_deep_as_the_building_on_the_map(self) -> None:
        layout = layout_for(Room("house", "casa", width=4, height=3, roofed=True), AREA)
        self.assertEqual((layout.columns, layout.rows), (4 * GROWTH, 3 * GROWTH))
        self.assertEqual(layout.floor.size, (layout.columns * layout.cell, layout.rows * layout.depth))
        self.assertEqual(layout.wall.width, layout.floor.width)

    def test_the_wall_is_face_on_over_a_floor_seen_from_a_little_above(self) -> None:
        layout = layout_for(Room("house", "casa", width=4, height=3, roofed=True), AREA)
        self.assertEqual(layout.wall.bottom, layout.floor.top, "the floor starts at the foot of the back wall")
        self.assertLess(layout.depth, layout.cell, "a cell looks less deep than it is wide")
        self.assertGreater(layout.depth, layout.cell // 2, "but only a little: it is no view from the side")
        self.assertAlmostEqual(layout.depth / layout.cell, DEPTH, delta=0.02)
        self.assertAlmostEqual(layout.wall.height / layout.cell, WALL, delta=0.02)

    def test_a_room_of_any_shape_fits_where_it_is_shown_and_fills_it_one_way(self) -> None:
        for width, height in ((4, 3), (7, 4), (12, 6), (2, 9)):
            layout = layout_for(Room("room", "sala", width=width, height=height, roofed=True), AREA)
            whole = layout.whole
            self.assertTrue(AREA.contains(whole), (width, height))
            self.assertTrue(whole.width > AREA.width * 0.8 or whole.height > AREA.height * 0.8, (width, height))
            self.assertLess(abs(whole.centerx - AREA.centerx), layout.cell)

    def test_places_on_the_floor_go_from_its_back_left_corner_in_cells(self) -> None:
        layout = layout_for(Room("house", "casa", width=4, height=3, roofed=True), AREA)
        self.assertEqual(layout.spot(0, 0), layout.floor.topleft)
        self.assertEqual(layout.spot(layout.columns, layout.rows), layout.floor.bottomright)
        self.assertEqual(layout.spot(1, 0)[0] - layout.spot(0, 0)[0], layout.cell)
        self.assertEqual(layout.spot(0, 1)[1] - layout.spot(0, 0)[1], layout.depth)

    def test_the_way_out_is_where_the_door_is_on_the_map(self) -> None:
        world = SimulationWorld.demo_world()
        for room in world.rooms.values():
            if not room.roofed:
                continue
            found = door_columns(world, room)
            if found is None:
                continue
            first, count = found
            self.assertEqual(count % GROWTH, 0)
            self.assertTrue(0 <= first and first + count <= room.width * GROWTH, room.room_id)
            self.assertEqual(world.tile_map.terrain_at((room.x + first // GROWTH, room.y + room.height)), "door")
        house = world.rooms["south_house"]
        self.assertIsNotNone(door_columns(world, house))
        # With none in its front wall, the way out is put in the middle.
        nowhere = Room("nowhere", "ninguna", x=1, y=1, width=4, height=2, roofed=True)
        self.assertIsNone(door_columns(world, nowhere))
        self.assertEqual(layout_for(nowhere, AREA).door, (3, GROWTH))

    def test_the_empty_room_is_drawn_whole_with_wall_floor_and_grid(self) -> None:
        layout = layout_for(Room("house", "casa", width=4, height=3, roofed=True), AREA)
        shell = draw_shell(layout, "floor_wood", 3)
        self.assertEqual(shell.get_size(), layout.whole.size)
        corner = layout.whole.topleft

        def at(x: int, y: int) -> tuple[int, int, int]:
            return tuple(shell.get_at((x - corner[0], y - corner[1])))[:3]

        wall = at(layout.wall.centerx + 3, layout.wall.centery)
        inside_a_cell = at(layout.floor.x + layout.cell * 3 + layout.cell // 2, layout.floor.y + layout.depth * 3 + layout.depth // 2)
        on_a_line = at(layout.floor.x + layout.cell * 3, layout.floor.y + layout.depth * 3 + layout.depth // 2)
        self.assertNotEqual(wall, inside_a_cell)
        self.assertLess(sum(on_a_line), sum(inside_a_cell) - 30, "every cell has a line round it")
        again = draw_shell(layout, "floor_wood", 3)
        spots = [(x, y) for x in range(5, shell.get_width(), 97) for y in range(5, shell.get_height(), 53)]
        self.assertEqual([again.get_at(spot) for spot in spots], [shell.get_at(spot) for spot in spots], "the same every time")
        self.assertNotEqual(
            draw_shell(layout, "floor_concrete", 3).get_at((shell.get_width() // 2, shell.get_height() - layout.front - 5)),
            shell.get_at((shell.get_width() // 2, shell.get_height() - layout.front - 5)),
            "the floor is what the building's floor is",
        )


class InsideABuildingTests(unittest.TestCase):
    """Going into a building from the map, through the real game shell without a window."""

    illustrated = False

    def setUp(self) -> None:
        for variable in ("SDL_VIDEODRIVER", "SDL_AUDIODRIVER"):
            self.addCleanup(self._restore_driver, variable, os.environ.get(variable))
            os.environ[variable] = "dummy"
        from game.game import Game

        folder = None
        if self.illustrated:
            keep = tempfile.TemporaryDirectory()
            self.addCleanup(keep.cleanup)
            folder = Path(keep.name) / "illustrations"
            folder.mkdir()
        self.game = Game(illustrations_dir=folder, voices_dir=None, start_in_menu=False)
        self.addCleanup(pygame.quit)
        self.view, self.hud, self.world = self.game.global_view, self.game.global_view.hud, self.game.world

    @staticmethod
    def _restore_driver(variable: str, previous: str | None) -> None:
        if previous is None:
            os.environ.pop(variable, None)
        else:
            os.environ[variable] = previous

    def _see(self, room_id: str) -> pygame.Rect:
        """Bring a building into view and draw it. Returns where its sign is."""
        room = self.world.rooms[room_id]
        self.view.centre_on((room.x + room.width / 2, room.y + room.height / 2))
        self.view.render()
        return self.view.sign_boxes[room_id]

    def _move(self, position: tuple[int, int]) -> None:
        self.view.handle_event(
            pygame.event.Event(
                pygame.MOUSEMOTION, pos=(position[0] * SCALE + 1, position[1] * SCALE + 1), rel=(0, 0), buttons=(0, 0, 0)
            )
        )
        self.view.update(0.0)

    def _indoors(self, resident_id: str, room_id: str, offset: tuple[int, int] = (1, 1)) -> None:
        room, resident = self.world.rooms[room_id], self.world.residents[resident_id]
        resident.x, resident.y = room.x + offset[0], room.y + offset[1]
        resident.trail = []
        resident.activity = Activity("wander", minutes_left=600, using=True)

    def test_only_what_has_a_roof_has_a_sign_to_go_in_by(self) -> None:
        self._see("south_house")
        roofed = {room_id for room_id, room in self.world.rooms.items() if room.roofed}
        self.assertTrue(set(self.view.sign_boxes) <= roofed)
        self.assertIn("south_house", self.view.sign_boxes)
        self.assertFalse(self.view.enter("commons"), "open ground is not gone into")
        self.assertFalse(self.view.enter("nowhere"))
        self.assertIsNone(self.view.inside)

    def test_resting_on_the_sign_of_a_closed_building_leaves_its_roof_on_and_a_click_goes_in(self) -> None:
        sign = self._see("south_house")
        self._move(sign.center)
        self.view.render()
        self.assertNotIn("south_house", self.view.looked_into(), "the sign stays where the pointer found it")
        self.assertEqual(self.view.sign_boxes["south_house"], sign)
        # Anywhere else on the building, the roof still comes off.
        room = self.world.rooms["south_house"]
        x, y = self.view._tile_pixel(room.x + room.width / 2, room.y + room.height / 2)
        self._move((x, y))
        self.assertIn("south_house", self.view.looked_into())
        self._move(sign.center)
        self.view.render()
        self._move(sign.center)
        self.view.render()
        self.view.click(sign.center)
        self.assertEqual(self.view.inside, "south_house")

    def test_inside_there_is_the_room_and_whoever_is_in_it_and_no_map(self) -> None:
        self._indoors("ines", "south_house")
        self._indoors("paco", "cantina")
        self.hud.minimap_rect = self.view._minimap_rect
        self.assertTrue(self.view.enter("south_house"))
        self.view.render()
        self.assertEqual(set(self.view.hitboxes), {"ines"}, "only whoever is in there is seen")
        self.assertEqual(self.view.sign_boxes, {})
        self.assertIsNone(self.hud.minimap_rect)
        self.assertTrue(self.view.viewport.contains(self.view.hitboxes["ines"]))
        # Where somebody is in there goes by where the map has them.
        before = self.view.hitboxes["ines"].center
        self.world.residents["ines"].x += 2
        self.view.render()
        self.assertGreater(self.view.hitboxes["ines"].centerx, before[0])
        self.world.residents["ines"].y += 1
        self.view.render()
        self.assertGreater(self.view.hitboxes["ines"].centery, before[1], "further down the floor is nearer")

    def test_whoever_is_in_there_is_picked_as_on_the_map_and_time_goes_on(self) -> None:
        self._indoors("ines", "south_house")
        self.view.enter("south_house")
        self.view.render()
        self.view.click(self.view.hitboxes["ines"].center)
        self.assertEqual(self.hud.selected_id, "ines")
        self.view.click((self.view.viewport.centerx, self.view.viewport.bottom - 30))
        self.assertIsNone(self.hud.selected_id)
        minute = self.world.clock.total_minutes
        self.game.advance_simulation(5.0)
        self.assertGreater(self.world.clock.total_minutes, minute, "it is still the same settlement, going on")
        self.view.render()

    def test_somebody_asleep_in_there_is_seen_in_their_bed(self) -> None:
        room = self.world.rooms["south_house"]
        bed = next(
            placed
            for placed in self.world.interactables.values()
            if placed.kind == "bed" and room.contains((placed.x, placed.y))
        )
        ines = self.world.residents["ines"]
        ines.x, ines.y, ines.trail = bed.x, bed.y, []
        ines.activity = Activity("sleep", target_id=bed.object_id, minutes_left=300, using=True)
        self.view.enter("south_house")
        self.view.render()
        self.assertIn("ines", self.view.hitboxes)

    def test_the_way_out_and_the_key_bring_the_map_back_as_it_was(self) -> None:
        self.hud.minimap_rect = self.view._minimap_rect
        self.view.enter("south_house")
        self.view.render()
        self.view.click(self.view.interior.leave_button.rect.center)
        self.assertIsNone(self.view.inside)
        self.assertIs(self.hud.minimap_rect, self.view._minimap_rect, "the minimap is where it was")
        self.view.render()
        self.assertIn("south_house", self.view.sign_boxes)
        # The key goes into the building whoever is selected is in, and comes out of it.
        self._indoors("ines", "south_house")
        self.hud.select_resident("ines")
        key = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_i, mod=0, unicode="i")
        self.view.handle_event(key)
        self.assertEqual(self.view.inside, "south_house")
        self.view.handle_event(key)
        self.assertIsNone(self.view.inside)
        self.hud.select_resident(None)
        self.view.pointer = None
        self.view.handle_event(key)
        self.assertIsNone(self.view.inside)
        self.assertIn("edificio", self.hud.notice)

    def test_in_there_the_wheel_and_a_drag_move_nothing(self) -> None:
        zoom, camera = self.view.zoom, tuple(self.view._visible_region())
        self.view.enter("south_house")
        self.view.handle_event(pygame.event.Event(pygame.MOUSEWHEEL, y=1, x=0))
        centre = self.view.viewport.center
        down = (centre[0] * SCALE, centre[1] * SCALE)
        self.view.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=down, button=1))
        self.view.handle_event(
            pygame.event.Event(pygame.MOUSEMOTION, pos=(down[0] + 120, down[1] + 80), rel=(120, 80), buttons=(1, 0, 0))
        )
        self.view.handle_event(pygame.event.Event(pygame.MOUSEBUTTONUP, pos=(down[0] + 120, down[1] + 80), button=1))
        self.view.leave()
        self.assertEqual((self.view.zoom, tuple(self.view._visible_region())), (zoom, camera))

    def test_a_building_that_is_no_longer_there_is_come_out_of(self) -> None:
        self.view.enter("south_house")
        del self.world.rooms["south_house"]
        self.view.roof_tiles.pop("south_house", None)
        self.view.render()
        self.assertIsNone(self.view.inside)

    def test_every_building_there_is_can_be_seen_from_inside(self) -> None:
        for room_id, room in self.world.rooms.items():
            if room.roofed:
                self.assertTrue(self.view.enter(room_id), room_id)
                self.view.render()
                self.game.present(pygame.Surface(self.game.screen.get_size()))
        self.view.leave()


class InsideOnTheWindowTests(InsideABuildingTests):
    """The same with a window under the canvas: the room is drawn on it, at its resolution."""

    illustrated = True

    def test_inside_there_is_the_room_and_whoever_is_in_it_and_no_map(self) -> None:
        super().test_inside_there_is_the_room_and_whoever_is_in_it_and_no_map()
        centre = self.view.viewport.center
        self.assertEqual(self.game.canvas.get_at(centre)[3], 0, "the canvas is left clear over the room")
        window = pygame.Surface(self.game.screen.get_size())
        self.game.present(window)
        layout = self.view.interior.layout(self.world.rooms["south_house"])
        corner = (self.view.viewport.x * SCALE, self.view.viewport.y * SCALE)
        wall = tuple(window.get_at((corner[0] + layout.wall.centerx + 3, corner[1] + layout.wall.y + layout.wall.height // 3)))[:3]
        outside = tuple(window.get_at((corner[0] + 6, corner[1] + self.view.viewport.height * SCALE // 2)))[:3]
        self.assertNotEqual(wall, outside)
        self.assertGreater(wall[0], wall[2], "boards, warm against the dark round the room")


if __name__ == "__main__":
    unittest.main()
