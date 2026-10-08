import json
import os
import tempfile
import unittest
from pathlib import Path

import pygame

from graphics.palette import PALETTE
from save.save_manager import SaveManager
from scenes.hud import URBANISM_INTENT
from settings import SCALE
from simulation.commands import (
    MoveBuildingCommand,
    MoveObjectCommand,
    RemoveBuildingCommand,
    RemoveObjectCommand,
)
from simulation.registries import DATA_DIR, BuiltInRegistries
from simulation.world import SimulationWorld
from world.urbanism import CUT_OFF, UrbanismResult


def put(world: SimulationWorld, kind: str, tile: tuple[int, int]) -> UrbanismResult:
    """Stand an object where the rules of the layout let it stand, with no building of it."""
    return world.urbanism.place_object(world, kind, tile)


def put_up(world: SimulationWorld, blueprint_id: str, tile: tuple[int, int]) -> UrbanismResult:
    """Stand a building where the rules of the layout let it stand, with no building of it."""
    return world.urbanism.place_building(world, blueprint_id, tile)


class UrbanismDomainTests(unittest.TestCase):
    def setUp(self) -> None:
        self.world = SimulationWorld.demo_world()

    def _building_spot(self, blueprint_id: str, avoid: tuple[int, int] | None = None) -> tuple[int, int]:
        definition = self.world.registries.buildings[blueprint_id]
        for y in range(1, self.world.tile_map.height - definition.height):
            for x in range(1, self.world.tile_map.width - definition.width):
                tile = (x, y)
                if tile != avoid and self.world.urbanism.building_error(
                    self.world, definition.width, definition.height, tile
                ) is None:
                    return tile
        self.fail("the map should have a free construction site")

    def test_nothing_is_put_where_it_would_cut_ground_off_from_the_way_in(self) -> None:
        # The strip behind the houses is one tile wide. Something across it and something across
        # the gap that leads out of it would leave what lies between with no way out, and
        # whoever stepped onto it, as off the far side of a bed, shut in.
        self.assertTrue(put(self.world, "bed", (13, 1)).ok)
        self.assertEqual(self.world.urbanism.object_error(self.world, "bed", (23, 1)), CUT_OFF)
        self.assertEqual(put(self.world, "bed", (23, 1)).message, CUT_OFF)
        # What nobody can be shut in by is no matter, and neither is what leaves a way round.
        self.assertTrue(put(self.world, "stool", (23, 1)).ok)
        self.assertTrue(put(self.world, "crate", (30, 1)).ok)

    def test_objects_are_placed_moved_and_removed_through_commands(self) -> None:
        placed = put(self.world, "crate", (1, 1))
        self.assertTrue(placed.ok)
        self.assertIn(placed.entity_id, self.world.interactables)
        self.assertIn(placed.entity_id, self.world.containers)

        moved = self.world.apply_command(MoveObjectCommand(placed.entity_id, (2, 1)))
        self.assertTrue(moved.ok)
        self.assertEqual((self.world.interactables[placed.entity_id].x, self.world.interactables[placed.entity_id].y), (2, 1))

        removed = self.world.apply_command(RemoveObjectCommand(placed.entity_id))
        self.assertTrue(removed.ok)
        self.assertNotIn(placed.entity_id, self.world.interactables)
        self.assertNotIn(placed.entity_id, self.world.containers)

    def test_buildings_change_terrain_can_move_and_restore_the_ground(self) -> None:
        start = self._building_spot("shack")
        original = [list(row) for row in self.world.tile_map.tiles]
        placed = put_up(self.world, "shack", start)
        self.assertTrue(placed.ok)
        room = self.world.rooms[placed.entity_id]
        self.assertEqual(self.world.tile_map.terrain_at((room.x, room.y)), "floor_wood")
        self.assertEqual(self.world.tile_map.terrain_at((room.x - 1, room.y - 1)), "wall")

        destination = self._building_spot("shack", avoid=start)
        moved = self.world.apply_command(MoveBuildingCommand(room.room_id, destination))
        self.assertTrue(moved.ok)
        self.assertEqual((room.x, room.y), destination)
        self.assertEqual(self.world.tile_map.tiles[start[1]][start[0]], original[start[1]][start[0]])

        removed = self.world.apply_command(RemoveBuildingCommand(room.room_id))
        self.assertTrue(removed.ok)
        self.assertNotIn(room.room_id, self.world.rooms)

    def test_a_move_is_judged_without_touching_the_settlement(self) -> None:
        start = self._building_spot("shack")
        room_id = put_up(self.world, "shack", start).entity_id
        terrain = [list(row) for row in self.world.tile_map.tiles]
        underlays = {key: dict(value) for key, value in self.world.urbanism.underlays.items()}

        verdicts = {
            (x, y): self.world.urbanism.move_building_error(self.world, room_id, (x, y))
            for y in range(self.world.tile_map.height)
            for x in range(self.world.tile_map.width)
        }
        self.assertEqual(self.world.tile_map.tiles, terrain)
        self.assertEqual(self.world.urbanism.underlays, underlays)

        # One step aside overlaps its own walls, which must not count as an obstacle.
        self.assertIsNone(verdicts[start])
        beside = next(
            tile
            for tile, error in verdicts.items()
            if error is None and abs(tile[0] - start[0]) + abs(tile[1] - start[1]) == 1
        )
        refused = next(tile for tile, error in verdicts.items() if error is not None)
        rejected = self.world.apply_command(MoveBuildingCommand(room_id, refused))
        self.assertFalse(rejected.ok)
        self.assertEqual(rejected.message, verdicts[refused])
        self.assertEqual(self.world.tile_map.tiles, terrain)
        self.assertTrue(self.world.apply_command(MoveBuildingCommand(room_id, beside)).ok)

        crate = put(self.world, "crate", (1, 1)).entity_id
        self.assertIsNone(self.world.urbanism.move_object_error(self.world, crate, (2, 1)))
        self.assertEqual((self.world.interactables[crate].x, self.world.interactables[crate].y), (1, 1))

    def test_edited_layout_round_trips_in_the_save(self) -> None:
        building = put_up(self.world, "shack", self._building_spot("shack"))
        furniture = put(self.world, "stool", (1, 1))
        self.assertTrue(building.ok and furniture.ok)
        manager = SaveManager()
        loaded = manager.from_data(manager.to_data(self.world), self.world.registries)
        self.assertEqual(manager.to_data(loaded), manager.to_data(self.world))

    def test_custom_buildings_use_the_same_blueprint_registry(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            pack = root / "buildings" / "watch_tower"
            pack.mkdir(parents=True)
            (pack / "data.json").write_text(
                json.dumps(
                    {
                        "id": "watch_tower",
                        "name": "torre de vigilancia",
                        "width": 3,
                        "height": 3,
                        "floor": "floor_concrete",
                    }
                ),
                encoding="utf-8",
            )
            registries = BuiltInRegistries.load(DATA_DIR, root)
            self.assertEqual(registries.buildings["watch_tower"].width, 3)


class UrbanismShellTests(unittest.TestCase):
    def setUp(self) -> None:
        for variable in ("SDL_VIDEODRIVER", "SDL_AUDIODRIVER"):
            previous = os.environ.get(variable)
            self.addCleanup(self._restore, variable, previous)
            os.environ[variable] = "dummy"
        from game.game import Game

        self.game = Game(illustrations_dir=None, voices_dir=None, start_in_menu=False)
        self.addCleanup(pygame.quit)

    @staticmethod
    def _restore(variable: str, previous: str | None) -> None:
        if previous is None:
            os.environ.pop(variable, None)
        else:
            os.environ[variable] = previous

    def _editor(self):
        self.game.global_view._apply(URBANISM_INTENT)
        self.game.sync_scenes()
        return self.game.active_scene

    @staticmethod
    def _window(position: tuple[int, int]) -> tuple[int, int]:
        return (position[0] * SCALE, position[1] * SCALE)

    def _tile_position(self, editor, tile: tuple[int, int]) -> tuple[int, int]:
        return self._window(
            (
                editor.map_rect.x + tile[0] * editor.tile_px + editor.tile_px // 2,
                editor.map_rect.y + tile[1] * editor.tile_px + editor.tile_px // 2,
            )
        )

    def _drag(self, editor, start: tuple[int, int], end: tuple[int, int]) -> None:
        editor.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=start, button=1))
        editor.handle_event(pygame.event.Event(pygame.MOUSEMOTION, pos=end, rel=(0, 0), buttons=(1, 0, 0)))
        editor.render()
        editor.handle_event(pygame.event.Event(pygame.MOUSEBUTTONUP, pos=end, button=1))

    def _press(self, editor, intent: tuple) -> None:
        button = next(button for button in editor.buttons if button.intent == intent)
        position = self._window(button.rect.center)
        editor.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=position, button=1))
        editor.handle_event(pygame.event.Event(pygame.MOUSEBUTTONUP, pos=position, button=1))

    def _free_tiles(self, kind: str) -> list[tuple[int, int]]:
        world = self.game.world
        return [
            (x, y)
            for y in range(world.tile_map.height)
            for x in range(world.tile_map.width)
            if world.urbanism.object_error(world, kind, (x, y)) is None
        ]

    def test_dragging_out_of_the_catalogue_places_and_dragging_on_the_map_moves(self) -> None:
        editor = self._editor()
        world = self.game.world
        # Tyres are lying about for the taking: they are put down, with nothing to build.
        self._press(editor, ("category", "decor"))
        entry = next(button for button in editor.buttons if button.intent == ("catalog", "tyres"))
        first, second = self._free_tiles("tyres")[:2]
        before = set(world.interactables)

        self._drag(editor, self._window(entry.rect.center), self._tile_position(editor, first))
        (stool_id,) = set(world.interactables) - before
        stool = world.interactables[stool_id]
        self.assertEqual((stool.kind, stool.x, stool.y), ("tyres", *first))
        self.assertEqual(editor.selection, ("object", stool_id))
        self.assertIsNone(editor.proposal)

        self._drag(editor, self._tile_position(editor, first), self._tile_position(editor, second))
        self.assertEqual((stool.x, stool.y), second)
        self.assertEqual(set(world.interactables) - before, {stool_id})

    def test_what_takes_building_is_dropped_where_it_goes_and_then_put_to_somebody(self) -> None:
        editor = self._editor()
        world = self.game.world
        self._press(editor, ("category", "furniture"))
        entry = next(button for button in editor.buttons if button.intent == ("catalog", "stool"))
        spot = self._free_tiles("stool")[0]
        before = set(world.interactables)

        self._drag(editor, self._window(entry.rect.center), self._tile_position(editor, spot))
        self.assertEqual(set(world.interactables), before)
        self.assertEqual(world.sites, {})
        self.assertIsNotNone(editor.proposal)
        self.assertEqual(editor.proposal.tile, spot)
        # In place of the catalogue there is everybody who lives here, to choose from.
        asked = [button.intent[1] for button in editor.buttons if button.intent[0] == "propose"]
        self.assertEqual(asked, list(world.residents))
        self.assertFalse(any(button.intent[0] == "catalog" for button in editor.buttons))
        editor.render()

        # Somebody in no mood for it says no, and it can be put to somebody else.
        raul = world.residents["raul"]
        raul.mood, raul.needs.stress = 0.0, 100.0
        raul.personality.empathy, raul.personality.greed = 0.0, 100.0
        self._press(editor, ("propose", "raul"))
        self.assertEqual(world.sites, {})
        self.assertIsNotNone(editor.proposal)
        self.assertIn("Raúl", editor.message)

        self._press(editor, ("propose", "marta"))
        (site,) = world.sites.values()
        self.assertEqual((site.what, (site.x, site.y), site.in_charge), ("stool", spot, "marta"))
        self.assertIsNone(editor.proposal)
        self.assertEqual(editor.selection, ("site", site.site_id))
        self.assertEqual(set(world.interactables), before)
        editor.render()

        # A site is not moved. It is given up, when that is said twice.
        self._drag(editor, self._tile_position(editor, spot), self._tile_position(editor, self._free_tiles("stool")[5]))
        self.assertEqual((site.x, site.y), spot)
        self._press(editor, ("remove",))
        self.assertIn(site.site_id, world.sites)
        self._press(editor, ("remove",))
        self.assertEqual(world.sites, {})

    def test_what_was_dropped_to_be_built_can_be_let_go_with_nobody_asked(self) -> None:
        editor = self._editor()
        self._press(editor, ("category", "buildings"))
        entry = next(button for button in editor.buttons if button.intent == ("catalog", "shack"))
        world = self.game.world
        definition = world.registries.buildings["shack"]
        spot = next(
            (x, y)
            for y in range(2, world.tile_map.height - definition.height)
            for x in range(2, world.tile_map.width - definition.width)
            if world.urbanism.building_error(world, definition.width, definition.height, (x, y)) is None
        )
        # A building is held by its middle.
        held_at = (spot[0] + definition.width // 2, spot[1] + definition.height // 2)
        self._drag(editor, self._window(entry.rect.center), self._tile_position(editor, held_at))
        self.assertIsNotNone(editor.proposal)
        self.assertEqual(editor.proposal.tile, spot)
        editor.render()
        self._press(editor, ("drop_proposal",))
        self.assertIsNone(editor.proposal)
        self.assertEqual(world.sites, {})
        self.assertFalse(any(room.blueprint_id == "shack" for room in world.rooms.values()))

    def test_a_click_only_selects_and_a_drop_off_the_map_changes_nothing(self) -> None:
        editor = self._editor()
        world = self.game.world
        stool_id = put(world, "stool", self._free_tiles("stool")[0]).entity_id
        stool = world.interactables[stool_id]
        home = (stool.x, stool.y)
        layout = {key: (placed.x, placed.y) for key, placed in world.interactables.items()}
        rooms = set(world.rooms)

        self._drag(editor, self._tile_position(editor, home), self._tile_position(editor, home))
        self.assertEqual(editor.selection, ("object", stool_id))
        self._drag(editor, self._tile_position(editor, home), self._window(editor.close_button.rect.center))
        self.assertFalse(editor.closed)
        entry = next(button for button in editor.buttons if button.intent[0] == "catalog")
        self._drag(editor, self._window(entry.rect.center), self._window((4, 4)))

        self.assertEqual({key: (placed.x, placed.y) for key, placed in world.interactables.items()}, layout)
        self.assertEqual(set(world.rooms), rooms)

    def _tiles(self, editor) -> list:
        return [button for button in editor.buttons if button.intent[0] == "catalog"]

    def _point(self, editor, position: tuple[int, int]) -> None:
        editor.handle_event(
            pygame.event.Event(pygame.MOUSEMOTION, pos=self._window(position), rel=(0, 0), buttons=(0, 0, 0))
        )

    def test_the_catalogue_is_a_grid_of_pictures_with_every_tab_in_sight(self) -> None:
        from scenes.urbanism import CATALOG_BOTTOM, CATALOG_COLUMNS, CATALOG_TILE, CATALOG_TOP, PANEL_WIDTH

        editor = self._editor()
        kinds = self.game.world.registries.interactables
        for category in ("buildings", "furniture", "decor"):
            self._press(editor, ("category", category))
            tiles = self._tiles(editor)
            self.assertEqual(len(tiles), len(editor._catalog()), f"{category}: all of it fits without the wheel")
            self.assertEqual(editor._catalog_scroll(), 0)
            for tile in tiles:
                self.assertEqual(tile.rect.size, (CATALOG_TILE, CATALOG_TILE))
                self.assertTrue(pygame.Rect(0, CATALOG_TOP, PANEL_WIDTH, CATALOG_BOTTOM - CATALOG_TOP).contains(tile.rect))
            rows = [line for line in editor._catalog_lines() if not isinstance(line, str)]
            self.assertEqual(len({tile.rect.y for tile in tiles}), len(rows))
            self.assertTrue(all(len(row) <= CATALOG_COLUMNS for row in rows), "so many to a row")
            self.assertEqual(len({tile.rect.x for tile in tiles}), min(CATALOG_COLUMNS, max(len(row) for row in rows)))
            self.assertEqual(len({tuple(tile.rect) for tile in tiles}), len(tiles), "no two on the same place")
            editor.render()
        # Each is the picture of what it offers, fitted to its tile whatever its shape.
        self._press(editor, ("category", "furniture"))
        for entry in editor._catalog():
            picture = editor._catalog_picture(entry, 1)
            self.assertLessEqual(max(picture.get_size()), CATALOG_TILE, entry.entry_id)
            self.assertGreater(pygame.mask.from_surface(picture).count(), 20, entry.entry_id)
        self.assertGreater(kinds.get("bed").height, kinds.get("bed").width)
        bed = editor._catalog_picture(next(entry for entry in editor._catalog() if entry.entry_id == "bed"), 1)
        self.assertGreater(bed.get_height(), bed.get_width(), "nothing is squashed into a square")

    def test_resting_the_pointer_on_a_picture_names_it_and_says_what_it_takes(self) -> None:
        editor = self._editor()
        self._press(editor, ("category", "furniture"))
        self.assertIsNone(editor.pointed_entry())
        tiles = {button.intent[1]: button for button in self._tiles(editor)}
        self._point(editor, tiles["bed"].rect.center)
        entry = editor.pointed_entry()
        self.assertEqual((entry.entry_id, entry.name), ("bed", "cama"))
        self.assertIn("chatarra", editor.entry_note(entry))
        self.assertIn("min de obra", editor.entry_note(entry))
        editor.render()
        # It is said in a box beside the pointer, framed so that it stands out from what is under it.
        corner = (tiles["bed"].rect.centerx + 10, tiles["bed"].rect.centery + 12)
        self.assertEqual(self.game.canvas.get_at(corner)[:3], PALETTE["lamp"])
        self.assertEqual(self.game.canvas.get_at((corner[0] + 2, corner[1] + 2))[:3], PALETTE["ink"])
        # What is simply put down says so, and off the catalogue nothing is named.
        self._press(editor, ("category", "decor"))
        tiles = {button.intent[1]: button for button in self._tiles(editor)}
        self._point(editor, tiles["tyres"].rect.center)
        self.assertEqual(editor.entry_note(editor.pointed_entry()), "se pone sin obra")
        self._point(editor, editor.map_rect.center)
        self.assertIsNone(editor.pointed_entry())
        editor.render()

    def test_what_nobody_knows_how_to_make_comes_last_under_its_heading_and_is_not_handed_over(self) -> None:
        from scenes.urbanism import LOCKED_TITLE

        world = self.game.world
        world.studies.known.remove("still")
        editor = self._editor()
        self._press(editor, ("category", "furniture"))
        entries = editor._catalog()
        locked = [entry.entry_id for entry in entries if entry.lock is not None]
        self.assertIn("bar", locked)
        self.assertEqual([entry.entry_id for entry in entries][-len(locked):], locked, "they come after the rest")
        lines = editor._catalog_lines()
        heading = lines.index(LOCKED_TITLE)
        self.assertTrue(all(entry.lock is None for line in lines[:heading] for entry in line))
        self.assertTrue(all(entry.lock is not None for line in lines[heading + 1 :] for entry in line))
        cells, where = editor._catalog_cells()
        self.assertIsNotNone(where)
        tiles = {entry.entry_id: rect for entry, rect in cells}
        self.assertGreater(tiles["bar"].y, where, "under the heading")
        self.assertLess(tiles["bed"].y, where)
        # Its picture is dimmed, it says what has to be found out, and it does not come off the catalogue.
        bar = next(entry for entry in entries if entry.entry_id == "bar")
        plain = editor._catalog_picture(next(entry for entry in entries if entry.entry_id == "bed"), 1)
        self.assertIsNot(editor._catalog_picture(bar, 1), plain)
        self._point(editor, tiles["bar"].center)
        self.assertIn("Alambique", editor.entry_note(editor.pointed_entry()))
        editor.render()
        self._press(editor, ("catalog", "bar"))
        self.assertIsNone(editor.catalog_id)
        self.assertIn("Alambique", editor.message)
        # A tab with nothing locked in it has no heading.
        self._press(editor, ("category", "decor"))
        self.assertNotIn(LOCKED_TITLE, editor._catalog_lines())
        self.assertIsNone(editor._catalog_cells()[1])

    def test_a_catalogue_longer_than_its_room_rolls_with_the_wheel(self) -> None:
        import scenes.urbanism as urbanism

        editor = self._editor()
        self._press(editor, ("category", "furniture"))
        everything = len(editor._catalog())
        room = urbanism.CATALOG_BOTTOM
        self.addCleanup(setattr, urbanism, "CATALOG_BOTTOM", room)
        urbanism.CATALOG_BOTTOM = urbanism.CATALOG_TOP + urbanism.CATALOG_TILE * 2 + urbanism.CATALOG_GAP
        self.assertLess(len(self._tiles(editor)), everything)
        self.assertGreater(editor._catalog_scroll(), 0)
        first = self._tiles(editor)[0].intent
        seen = {tile.intent[1] for tile in self._tiles(editor)}
        for _ in range(editor._catalog_scroll() + 3):
            editor.catalog_offset = min(editor._catalog_scroll(), editor.catalog_offset + 1)
            seen |= {tile.intent[1] for tile in self._tiles(editor)}
        self.assertNotEqual(self._tiles(editor)[0].intent, first)
        self.assertEqual(len(seen), everything, "all of it can be reached")
        editor.render()

    def test_the_menu_opens_urbanism_while_time_stands_still_and_saving_is_in_the_menu_of_escape(self) -> None:
        view = self.game.global_view
        intents = [button.intent for button in view.hud.menu]
        self.assertIn(URBANISM_INTENT, intents)
        self.assertNotIn("Guardar", [button.label for button in view.hud.menu])

        # Saving is done from the menu Escape opens, and leaves the player there.
        saved: list[bool] = []
        self.game.save_game = lambda path=None: saved.append(True) or True
        self.game.open_menu()
        self.game.main_menu.choose("save")
        self.game.sync_scenes()
        self.assertEqual(saved, [True])
        self.assertEqual(self.game.scene_name, "menu")
        self.game.main_menu.choose("continue")
        self.game.sync_scenes()
        self.assertEqual(self.game.scene_name, "global")

        view._apply(URBANISM_INTENT)
        self.game.sync_scenes()
        self.assertEqual(self.game.scene_name, "urbanism")
        minute = self.game.world.clock.total_minutes
        self.game.advance_simulation(10.0)
        self.assertEqual(self.game.world.clock.total_minutes, minute)
        self.game.active_scene.render()

        self.game.active_scene.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE))
        self.game.sync_scenes()
        self.assertEqual(self.game.scene_name, "global")


if __name__ == "__main__":
    unittest.main()
