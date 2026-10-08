import os
import tempfile
import unittest
from pathlib import Path

import pygame

from scenes.global_view import NOBODY_TO_MAKE_IT
from scenes.interior_view import DECOR_INTENT, DEPTH, GROWTH, HOUSE_INTENT, WALL, door_columns, draw_shell, layout_for
from settings import SCALE
from simulation.residents.activity import Activity
from simulation.commands import DecorateCommand
from simulation.events.event import DomainEvent
from simulation.work.construction import OBJECT_SITE
from simulation.world import SimulationWorld
from ui.decor_board import DONE_INTENT, FLOORS, FURNITURE, ORNAMENTS, REMOVE_INTENT, TABS, WALLS, entries, entry_cells, pick_intent, tab_intent
from ui.house_board import LOCK_INTENT, RENAME_INTENT, USE_INTENT, owner_intent
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


class InsideArtTests(unittest.TestCase):
    """What is drawn of a thing for the view from inside."""

    def setUp(self) -> None:
        previous = os.environ.get("SDL_VIDEODRIVER")
        os.environ["SDL_VIDEODRIVER"] = "dummy"
        self.addCleanup(InsideABuildingTests._restore_driver, "SDL_VIDEODRIVER", previous)
        pygame.init()
        pygame.display.set_mode((16, 16))
        self.addCleanup(pygame.quit)

    def test_a_bed_is_seen_from_its_front_with_its_head_to_the_back_wall(self) -> None:
        from graphics.object_pictures import PAINTERS, bed

        self.assertIs(PAINTERS["bed"], bed)
        for cell in (140, 70, 40):
            depth = round(cell * DEPTH)
            picture = bed(cell, depth)
            self.assertEqual(picture.under.get_size(), (cell, picture.rise + depth * 2), "one cell across and two deep")
            self.assertEqual(picture.over.get_size(), picture.under.get_size())
            self.assertGreater(picture.rise, cell // 4, "the headboard stands up above the floor it takes")
            middle = cell // 2
            # Above the floor it takes up there is the headboard, and nothing of the blanket.
            self.assertGreater(picture.under.get_at((middle, picture.rise // 2)).a, 240)
            self.assertEqual(picture.over.get_at((middle, picture.rise // 2)).a, 0)
            # Over the pillow nothing covers a head; further down the blanket does, in another colour.
            pillow = (middle, picture.rise + round(cell * 0.2))
            self.assertEqual(picture.over.get_at(pillow).a, 0)
            self.assertGreater(min(picture.under.get_at(pillow)[:3]), 200, "the pillow is pale")
            blanket = picture.over.get_at((middle - cell // 5, picture.rise + depth))
            self.assertGreater(blanket.a, 240)
            self.assertGreater(blanket.b, blanket.r + 30, "and the blanket blue")
            # At its foot, the board that faces whoever looks in.
            board = picture.over.get_at((middle, picture.under.get_height() - round(cell * 0.14)))
            self.assertGreater(board.r, board.b + 30)


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
        # Nor does resting anywhere else on it: from the map a building is always shut.
        room = self.world.rooms["south_house"]
        x, y = self.view._tile_pixel(room.x + room.width / 2, room.y + 0.5)
        self._move((x, y))
        self.assertEqual(self.view.looked_into(), set())
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
        # They are picked by the bed they lie in, which is seen as the floor is: less deep than wide.
        layout = self.view.interior.layout(room)
        box = self.view.hitboxes["ines"]
        picture = self.view.interior._own(layout, self.world.definition_of(bed))
        self.assertEqual(box.size, (layout.cell // SCALE, (layout.depth * 2 + picture.rise) // SCALE))
        self.assertGreater(picture.rise, 0, "the bed is drawn for this view: its headboard stands up at the back")
        # It is their own head that shows on the pillow, as on the map, and not a mark for them.
        shown = [picture for key, picture in self.view.interior._pictures.items() if key[:2] == ("head", "ines")]
        if self.view.windowed:
            # On the window she is the figure the game draws of her, and it is that figure's head.
            self.assertEqual(shown, [])
            self.assertIsNotNone(self.view._doll_of("ines"))
            return
        head = self.view.bodies.renderer.head("ines")
        self.assertEqual(len(shown), 1)
        self.assertEqual(shown[0].get_width(), round(head.get_width() * layout.cell / 16))
        self.assertLess(shown[0].get_height(), shown[0].get_width(), "down to the eyes: the rest is under the blanket")

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

    def test_whoever_lies_in_a_bed_is_drawn_between_the_mattress_and_the_blanket(self) -> None:
        room = self.world.rooms["south_house"]
        bed = next(
            placed for placed in self.world.interactables.values() if placed.kind == "bed" and room.contains((placed.x, placed.y))
        )
        layout = self.view.interior.layout(room)
        parts = self.view.interior._object(room, layout, bed)
        self.assertEqual(len(parts), 2, "what is under them, and what is over them")
        ines = self.world.residents["ines"]
        ines.x, ines.y, ines.trail = bed.x, bed.y, []
        ines.activity = Activity("sleep", target_id=bed.object_id, minutes_left=300, using=True)
        sleeper = self.view.interior._resident(room, layout, ines)[0]
        self.assertLess(parts[0][0], sleeper)
        self.assertLess(sleeper, parts[1][0])
        # What has no picture of its own for this view is drawn in one piece, as it was.
        crate = next(placed for placed in self.world.interactables.values() if placed.kind == "crate" and room.contains((placed.x, placed.y)))
        self.assertEqual(len(self.view.interior._object(room, layout, crate)), 1)

    def test_whoever_eats_in_there_is_seen_with_their_meal_in_their_hand(self) -> None:
        self._indoors("ines", "south_house")
        ines = self.world.residents["ines"]
        room = self.world.rooms["south_house"]
        layout = self.view.interior.layout(room)
        plan = self.view.bodies.plan
        self.assertEqual(self.view.interior.in_hand(ines, "right", plan.pose("right", "idle", 0.0), 0.0, None), [])
        self.world.stock(ines.inventory, "canned_beans", 1, "ines")
        item = ines.inventory.items[-1]
        ines.activity = Activity("eat", minutes_left=20, using=True, item_id=item.instance_id)
        ines.current_action = "eat"
        self.view.time = 3.6
        self.assertEqual(self.view._meal_in_hand(ines), "canned_beans")
        held = self.view.interior.in_hand(ines, "right", plan.pose("right", "idle", 0.0), 3.6, None)
        self.assertEqual([entry[0] for entry in held], ["canned_beans"])
        self.assertEqual(self.view._held, [], "what is held on the map is left as it was")
        hand, mouth = held[0][1], held[0][5]
        self.assertLess(hand[1], 0, "up off the floor, in their hand: it goes by where their feet are")
        self.assertLess(mouth[1], hand[1] + 12)
        # It is drawn with them, and so is whatever they carry for their job.
        self.view.enter("south_house")
        self.view.render()
        self.assertIn("ines", self.view.hitboxes)
        ines.activity = Activity("wander", minutes_left=600, using=True)
        self.world.stock(ines.inventory, "scrap", 2, None)
        carried = self.view.interior.in_hand(ines, "right", plan.pose("right", "idle", 0.0), 0.0, None)
        self.assertEqual([entry[0] for entry in carried], ["scrap"])
        self.view.render()
        self.assertTrue(layout.cell > 0)

    def test_over_a_face_on_a_roof_is_what_they_are_doing_in_there(self) -> None:
        view, world = self.view, self.world
        self._indoors("ines", "south_house")
        self._indoors("paco", "south_house", (3, 1))
        ines, paco = world.residents["ines"], world.residents["paco"]
        self._see("south_house")
        self.assertEqual(view.looked_into(), set(), "the roof is on")
        self.assertIn("ines", view.hitboxes)
        self.assertIsNone(view._status_icon(ines, False, unseen=True), "doing nothing in particular")
        world.stock(ines.inventory, "canned_beans", 1, "ines")
        ines.activity = Activity("eat", minutes_left=20, using=True, item_id=ines.inventory.items[-1].instance_id)
        self.assertEqual(view._status_icon(ines, False, unseen=True), "eat")
        self.assertIsNone(view._status_icon(ines, False), "seen whole, the meal is in her hand and says it")
        ines.activity = Activity("chat", partner_id="paco", minutes_left=10, using=True)
        paco.activity = Activity("chat", partner_id="ines", minutes_left=10, using=True)
        self.assertEqual(view._status_icon(ines, False, unseen=True), "chat")
        self.assertEqual(view._status_icon(paco, True, unseen=True), "chat")
        paco.activity = None
        self.assertEqual(view._status_icon(paco, True, unseen=True), "sleep")
        view.render()

    def test_what_things_are_kept_in_is_picked_from_inside(self) -> None:
        room = self.world.rooms["south_house"]
        crate = next(
            placed
            for placed in self.world.interactables.values()
            if placed.object_id in self.world.containers and room.contains((placed.x, placed.y))
        )
        self.view.enter("south_house")
        self.view.render()
        self.assertIn(crate.object_id, self.view.container_hitboxes)
        self.view.click(self.view.container_hitboxes[crate.object_id].center)
        self.assertEqual((self.hud.selected_container, self.hud.selected_id), (crate.object_id, None))
        self.assertIsNotNone(self.hud.container_rect())
        self.view.render()
        # A click on somebody in there picks them in its place, and one on nothing puts it away.
        self._indoors("ines", "south_house", (3, 2))
        self.view.render()
        self.view.click(self.view.hitboxes["ines"].center)
        self.assertEqual((self.hud.selected_container, self.hud.selected_id), (None, "ines"))
        self.view.click((self.view.viewport.centerx, self.view.viewport.bottom - 30))
        self.assertEqual((self.hud.selected_container, self.hud.selected_id), (None, None))

    def _press(self, intent) -> None:
        """Press what there is for something on the board of the building being looked at."""
        room = self.world.rooms[self.view.inside]
        self.view.render()
        interior = self.view.interior
        places = [(button.intent, button.rect) for button in interior.buttons(room)]
        if interior.decorating:
            # The tiles of what there is to put in it are pressed as buttons are.
            tiles = entry_cells(interior.board_rect(), self.world, interior.decor_tab)
            places += [(pick_intent(entry.tab, entry.entry_id), cell) for entry, cell in tiles]
        self.view.click(next(rect for found, rect in places if found == intent).center)

    def test_the_board_of_a_building_says_whose_it_is_and_a_press_on_a_name_changes_it(self) -> None:
        self.view.enter("workshop")
        owners = lambda: self.world.housing.owners(self.world, "workshop")
        self.assertEqual(owners(), [])
        self._press(owner_intent("marta"))
        self.assertEqual(owners(), ["marta"])
        self._press(owner_intent("raul"))
        self.assertEqual(owners(), ["marta", "raul"])
        self._press(owner_intent("marta"))
        self.assertEqual(owners(), ["raul"])
        self.assertEqual(self.view.inside, "workshop", "and none of it is a press on the room behind")

    def test_the_door_is_locked_from_the_board_once_the_building_is_somebodys(self) -> None:
        self.view.enter("workshop")
        room = self.world.rooms["workshop"]
        self.view.render()
        self.assertNotIn(LOCK_INTENT, [button.intent for button in self.view.interior.buttons(room)])
        self._press(owner_intent("marta"))
        self._press(LOCK_INTENT)
        self.assertTrue(self.world.housing.locked(self.world, room))
        self._press(LOCK_INTENT)
        self.assertFalse(self.world.housing.locked(self.world, room))

    def test_what_a_building_is_for_goes_round_from_the_board(self) -> None:
        self.view.enter("workshop")
        uses = list(self.world.registries.housing.uses)
        for use in uses:
            self._press(USE_INTENT)
            self.assertEqual(self.world.homes.uses["workshop"], use)
        self._press(USE_INTENT)
        self.assertNotIn("workshop", self.world.homes.uses, "after the last, nothing is said of it again")

    def _type(self, key: int, letter: str = "") -> None:
        self.view.handle_event(pygame.event.Event(pygame.KEYDOWN, key=key, unicode=letter))

    def test_a_name_is_written_for_a_building_and_no_key_is_a_shortcut_meanwhile(self) -> None:
        self.view.enter("workshop")
        room = self.world.rooms["workshop"]
        before = room.name
        self.assertFalse(self.view.typing)
        self._press(RENAME_INTENT)
        self.assertTrue(self.view.typing)
        paused = self.world.clock.paused
        for letter in "Mi  taller!":
            self._type(ord(letter.lower()), letter)
            self.game.handle_key(ord(letter.lower()))
        self._type(pygame.K_BACKSPACE)
        self.assertEqual(self.view.inside, "workshop", "the i in it is no way out")
        self.assertEqual(self.world.clock.paused, paused, "nor the space a pause")
        self.view.render()
        self.assertEqual(room.name, before, "nothing is its name until it is said to be")
        self._type(pygame.K_RETURN)
        self.assertEqual(room.name, "Mi taller")
        self.assertFalse(self.view.typing)
        # Left half way, the name stays as it was, and the game is not left with it.
        self._press(RENAME_INTENT)
        self._type(pygame.K_x, "x")
        self._type(pygame.K_ESCAPE)
        self.game.handle_key(pygame.K_i)
        self.assertEqual((room.name, self.view.typing, self.view.inside), ("Mi taller", False, "workshop"))

    def test_the_player_is_told_when_somebody_comes_to_stay_with_no_house(self) -> None:
        event = DomainEvent("newcomer_joined", 45, "Marta entra en el asentamiento para quedarse", ["marta"])
        self.view.on_events([event])
        self.assertIn("Marta", self.hud.notice)
        self.assertIn("al raso", self.hud.notice)

    def test_the_room_is_laid_out_in_what_the_board_leaves_of_the_screen(self) -> None:
        self.view.enter("south_house")
        room = self.world.rooms["south_house"]
        self.view.render()
        interior, viewport = self.view.interior, self.view.viewport
        board = interior.board_rect()
        beside = interior.layout(room)
        self.assertLessEqual(viewport.x + beside.whole.right // SCALE, board.left)
        self.assertTrue(interior.covers(board.center))
        self._press(HOUSE_INTENT)
        self.assertIsNone(interior.board_rect())
        self.assertFalse(interior.covers(board.center))
        self.assertGreaterEqual(interior.layout(room).whole.width, beside.whole.width)
        self.view.render()
        self._press(HOUSE_INTENT)
        self.assertIsNotNone(interior.board_rect())

    def _cell(self, room_id: str, column: float, row: float) -> tuple[int, int]:
        """Where on the canvas the middle of a cell of the floor of a building is."""
        x, y = self.view.interior.layout(self.world.rooms[room_id]).spot(column + 0.5, row + 0.5)
        return (self.view.viewport.x + x // SCALE, self.view.viewport.y + y // SCALE)

    def _on_wall(self, room_id: str, column: float) -> tuple[int, int]:
        layout = self.view.interior.layout(self.world.rooms[room_id])
        x, y = layout.wall.x + round((column + 0.5) * layout.cell), layout.wall.centery
        return (self.view.viewport.x + x // SCALE, self.view.viewport.y + y // SCALE)

    def _free_cell(self, room_id: str) -> tuple[int, int]:
        room = self.world.rooms[room_id]
        taken = self.world.decor.furniture_cells(self.world, room)
        columns, rows = self.world.decor.size(room)
        return next((x, y) for y in range(1, rows) for x in range(1, columns) if (x, y) not in taken)

    def _free_tile(self, room_id: str, kind: str) -> tuple[int, int]:
        """A tile of a building where a kind of furniture could be put up."""
        room = self.world.rooms[room_id]
        return next(
            (x, y)
            for y in range(room.y, room.y + room.height)
            for x in range(room.x, room.x + room.width)
            if self.world.construction.site_error(self.world, OBJECT_SITE, kind, (x, y)) is None
        )

    def test_an_ornament_in_hand_goes_where_the_room_is_pressed_and_comes_away_the_same(self) -> None:
        self.view.enter("south_house")
        decor = self.world.decor
        self._press(DECOR_INTENT)
        self.assertTrue(self.view.interior.decorating)
        self._press(pick_intent(ORNAMENTS, "plant"))
        cell = self._free_cell("south_house")
        self._move(self._cell("south_house", *cell))
        self.view.render()
        self.view.click(self._cell("south_house", *cell))
        self.assertEqual([(each.kind, each.x, each.y) for each in decor.ornaments(self.world, "south_house")], [("plant", *cell)])
        self.assertIsNone(self.hud.selected_id, "and nobody is picked by it")
        # It stays in hand for the next, which does not go where the first is.
        self.view.click(self._cell("south_house", *cell))
        self.assertEqual(len(decor.ornaments(self.world, "south_house")), 1)
        self._press(REMOVE_INTENT)
        self._move(self._cell("south_house", *cell))
        self.view.render()
        self.view.click(self._cell("south_house", *cell))
        self.assertEqual(decor.ornaments(self.world, "south_house"), [])

    def test_what_hangs_goes_on_the_back_wall(self) -> None:
        self.view.enter("south_house")
        self._press(DECOR_INTENT)
        self._press(pick_intent(ORNAMENTS, "window"))
        self.view.click(self._cell("south_house", 4, 2))
        self.assertEqual(self.world.decor.ornaments(self.world, "south_house"), [], "not on the floor")
        self._move(self._on_wall("south_house", 4))
        self.view.render()
        self.view.click(self._on_wall("south_house", 4))
        hung = self.world.decor.ornaments(self.world, "south_house")
        self.assertEqual([(each.kind, each.on) for each in hung], [("window", "wall")])
        self.assertLessEqual(hung[0].x, 4)
        self.assertGreater(hung[0].x + 2, 4, "with the pointer at its middle")
        self.view.render()

    def test_the_floor_and_the_walls_are_chosen_from_the_board(self) -> None:
        self.view.enter("south_house")
        self._press(DECOR_INTENT)
        self._press(tab_intent(WALLS))
        self.assertEqual(self.view.interior.decor_tab, WALLS)
        self._press(pick_intent(WALLS, "brick"))
        self._press(tab_intent(FLOORS))
        self._press(pick_intent(FLOORS, "floor_tiles"))
        self.assertEqual((self.world.homes.walls, self.world.homes.floors), ({"south_house": "brick"}, {"south_house": "floor_tiles"}))
        self.assertIsNone(self.view.interior.decor_held, "they are not things to carry about")
        self.view.render()
        self._press(pick_intent(FLOORS, ""))
        self.assertEqual(self.world.homes.floors, {})

    def test_a_piece_of_furniture_is_put_to_whoever_lives_there_and_not_put_down(self) -> None:
        self.view.enter("south_house")
        room = self.world.rooms["south_house"]
        self._press(DECOR_INTENT)
        self._press(tab_intent(FURNITURE))
        self._press(pick_intent(FURNITURE, "stool"))
        tile = self._free_tile("south_house", "stool")
        before = len(self.world.interactables)
        place = self._cell("south_house", (tile[0] - room.x) * GROWTH, (tile[1] - room.y) * GROWTH)
        self._move(place)
        self.view.render()
        self.view.click(place)
        self.assertEqual(len(self.world.interactables), before, "nothing stands there until it is made")
        self.assertTrue(self.hud.notice)
        sites = [site for site in self.world.sites.values() if (site.x, site.y) == tile]
        if sites:
            # Whoever agreed to it lives there, and what they are putting up is seen where it will stand.
            self.assertIn(sites[0].in_charge, self.world.housing.owners(self.world, "south_house"))
            self.view.render()

    def test_in_a_building_that_is_nobodys_somebody_has_to_be_chosen_to_make_it(self) -> None:
        self.view.enter("workshop")
        room = self.world.rooms["workshop"]
        self._press(DECOR_INTENT)
        self._press(tab_intent(FURNITURE))
        self._press(pick_intent(FURNITURE, "stool"))
        tile = self._free_tile("workshop", "stool")
        self.view.click(self._cell("workshop", (tile[0] - room.x) * GROWTH, (tile[1] - room.y) * GROWTH))
        self.assertEqual(self.world.sites, {})
        self.assertEqual(self.hud.notice, NOBODY_TO_MAKE_IT)

    def test_the_other_button_and_the_way_out_put_down_what_is_in_hand(self) -> None:
        self.view.enter("south_house")
        interior = self.view.interior
        self._press(DECOR_INTENT)
        self._press(pick_intent(ORNAMENTS, "rug"))
        self.assertEqual(interior.decor_held, (ORNAMENTS, "rug"))
        self.view.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=(400, 400), button=3))
        self.assertIsNone(interior.decor_held)
        self._press(pick_intent(ORNAMENTS, "rug"))
        self._press(pick_intent(ORNAMENTS, "rug"))
        self.assertIsNone(interior.decor_held, "pressed again, it is put down")
        self._press(pick_intent(ORNAMENTS, "rug"))
        self._press(DONE_INTENT)
        self.assertEqual((interior.decorating, interior.decor_held), (False, None))
        self._press(DECOR_INTENT)
        self.view.leave()
        self.assertFalse(interior.decorating)

    def test_every_tab_of_the_board_is_drawn_with_something_in_hand_over_the_room(self) -> None:
        self.view.enter("south_house")
        self.world.apply_command(DecorateCommand("south_house", "rug", 4, 3))
        self.world.apply_command(DecorateCommand("south_house", "clock", 2, 0))
        self._press(DECOR_INTENT)
        board = self.view.interior.board_rect()
        for tab, _ in TABS:
            self._press(tab_intent(tab))
            last = entries(self.world, tab)[-1]
            self._press(pick_intent(tab, last.entry_id))
            for place in (self._cell("south_house", 4, 3), self._on_wall("south_house", 2), (board.x + 30, board.y + 60)):
                self._move(place)
                self.view.render()
                self.game.present(pygame.Surface(self.game.screen.get_size()))
        self._press(REMOVE_INTENT)
        for place in (self._cell("south_house", 4, 3), self._on_wall("south_house", 2)):
            self._move(place)
            self.view.render()

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
