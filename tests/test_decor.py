import json
import unittest
from pathlib import Path

from save.save_manager import SaveManager
from simulation.commands import DecorateCommand, SurfaceCommand, UndecorateCommand
from simulation.housing.decor import CELLS, DECORATED_EVENT, FLOOR, WALL, decor_settings_from_data
from simulation.world import SimulationWorld

ROOT = Path(__file__).resolve().parent.parent
HOUSE = "south_house"


def _world() -> SimulationWorld:
    return SimulationWorld.demo_world()


def _free_cell(world: SimulationWorld, room_id: str = HOUSE) -> tuple[int, int]:
    """A cell of the inside of a building that no furniture takes."""
    room = world.rooms[room_id]
    taken = world.decor.furniture_cells(world, room)
    columns, rows = world.decor.size(room)
    return next((x, y) for y in range(rows) for x in range(columns) if (x, y) not in taken)


class PlacingTests(unittest.TestCase):
    def test_the_inside_has_more_cells_than_the_building_has_tiles(self) -> None:
        world = _world()
        room = world.rooms[HOUSE]
        self.assertEqual(world.decor.size(room), (room.width * CELLS, room.height * CELLS))
        self.assertGreater(CELLS, 1)

    def test_an_ornament_goes_where_the_player_says_at_once_and_for_nothing(self) -> None:
        world = _world()
        scrap = dict(world.fund.goods(world))
        x, y = _free_cell(world)
        result = world.apply_command(DecorateCommand(HOUSE, "plant", x, y))
        self.assertTrue(result.ok, result.message)
        placed = world.decor.ornaments(world, HOUSE)
        self.assertEqual([(each.kind, each.on, each.x, each.y) for each in placed], [("plant", FLOOR, x, y)])
        self.assertEqual(world.fund.goods(world), scrap, "nothing was paid for it")
        self.assertEqual(world.sites, {}, "and nobody has to make it")
        self.assertIn(DECORATED_EVENT, " ".join(world.event_log))

    def test_each_has_an_id_of_its_own_that_is_never_given_twice(self) -> None:
        world = _world()
        x, y = _free_cell(world)
        world.apply_command(DecorateCommand(HOUSE, "plant", x, y))
        first = world.decor.ornaments(world, HOUSE)[0].ornament_id
        world.apply_command(UndecorateCommand(HOUSE, first))
        world.apply_command(DecorateCommand(HOUSE, "plant", x, y))
        self.assertNotEqual(world.decor.ornaments(world, HOUSE)[0].ornament_id, first)

    def test_it_has_to_fit_in_the_room(self) -> None:
        world = _world()
        columns, rows = world.decor.size(world.rooms[HOUSE])
        for x, y in ((-1, 0), (columns, 0), (0, rows), (columns - 1, rows - 1)):
            self.assertFalse(world.apply_command(DecorateCommand(HOUSE, "rug", x, y)).ok, (x, y))
        self.assertEqual(world.decor.ornaments(world, HOUSE), [])

    def test_nothing_stands_where_something_else_does(self) -> None:
        world = _world()
        x, y = _free_cell(world)
        self.assertTrue(world.apply_command(DecorateCommand(HOUSE, "plant", x, y)).ok)
        self.assertFalse(world.apply_command(DecorateCommand(HOUSE, "chair", x, y)).ok)

    def test_nothing_stands_where_there_is_furniture(self) -> None:
        world = _world()
        room = world.rooms[HOUSE]
        bed = next(placed for placed in world.interactables.values() if placed.kind == "bed" and room.contains((placed.x, placed.y)))
        cell = ((bed.x - room.x) * CELLS, (bed.y - room.y) * CELLS)
        self.assertIn(cell, world.decor.furniture_cells(world, room))
        self.assertFalse(world.apply_command(DecorateCommand(HOUSE, "plant", *cell)).ok)

    def test_what_lies_flat_goes_under_anything(self) -> None:
        world = _world()
        room = world.rooms[HOUSE]
        bed = next(placed for placed in world.interactables.values() if placed.kind == "bed" and room.contains((placed.x, placed.y)))
        cell = ((bed.x - room.x) * CELLS, (bed.y - room.y) * CELLS)
        self.assertTrue(world.apply_command(DecorateCommand(HOUSE, "mat", *cell)).ok, "under the bed")
        x, y = _free_cell(world)
        self.assertTrue(world.apply_command(DecorateCommand(HOUSE, "mat", x, y)).ok)
        self.assertTrue(world.apply_command(DecorateCommand(HOUSE, "plant", x, y)).ok, "and a plant on a mat")
        self.assertFalse(world.apply_command(DecorateCommand(HOUSE, "mat", x, y)).ok, "but not one mat on another")
        # What stands is found before what it stands on.
        self.assertEqual(world.decor.at(world, HOUSE, FLOOR, (x, y)).kind, "plant")

    def test_what_hangs_takes_a_stretch_of_the_wall_and_leaves_the_floor_alone(self) -> None:
        world = _world()
        columns, _ = world.decor.size(world.rooms[HOUSE])
        self.assertTrue(world.apply_command(DecorateCommand(HOUSE, "window", 2, 5)).ok)
        window = world.decor.ornaments(world, HOUSE)[0]
        self.assertEqual((window.on, window.x, window.y), (WALL, 2, 0), "how far up it hangs is its own business")
        self.assertFalse(world.apply_command(DecorateCommand(HOUSE, "picture", 3, 0)).ok, "the window is there")
        self.assertTrue(world.apply_command(DecorateCommand(HOUSE, "picture", 4, 0)).ok)
        self.assertFalse(world.apply_command(DecorateCommand(HOUSE, "window", columns - 1, 0)).ok, "it would stick out")
        self.assertTrue(world.apply_command(DecorateCommand(HOUSE, "mat", 2, 0)).ok, "the floor under it is free")
        self.assertEqual(world.decor.at(world, HOUSE, WALL, (3, 0)).kind, "window")

    def test_only_a_building_has_an_inside_to_dress_and_only_with_what_there_is(self) -> None:
        world = _world()
        self.assertFalse(world.apply_command(DecorateCommand("commons", "plant", 0, 0)).ok)
        self.assertFalse(world.apply_command(DecorateCommand("no_such_room", "plant", 0, 0)).ok)
        self.assertFalse(world.apply_command(DecorateCommand(HOUSE, "no_such_thing", 0, 0)).ok)

    def test_it_comes_away_as_it_went(self) -> None:
        world = _world()
        x, y = _free_cell(world)
        world.apply_command(DecorateCommand(HOUSE, "plant", x, y))
        ornament = world.decor.ornaments(world, HOUSE)[0]
        self.assertTrue(world.apply_command(UndecorateCommand(HOUSE, ornament.ornament_id)).ok)
        self.assertEqual(world.decor.ornaments(world, HOUSE), [])
        self.assertNotIn(HOUSE, world.homes.ornaments)
        self.assertFalse(world.apply_command(UndecorateCommand(HOUSE, ornament.ornament_id)).ok)

    def test_where_it_is_goes_by_the_building_and_not_by_the_map(self) -> None:
        world = _world()
        x, y = _free_cell(world)
        world.apply_command(DecorateCommand(HOUSE, "plant", x, y))
        room = world.rooms[HOUSE]
        room.x += 3
        room.y += 2
        ornament = world.decor.ornaments(world, HOUSE)[0]
        self.assertEqual((ornament.x, ornament.y), (x, y))


class SurfaceTests(unittest.TestCase):
    def test_the_floor_and_the_walls_are_what_the_player_says(self) -> None:
        world = _world()
        self.assertIsNone(world.decor.floor_of(world, HOUSE))
        self.assertTrue(world.apply_command(SurfaceCommand(HOUSE, floor="floor_tiles")).ok)
        self.assertTrue(world.apply_command(SurfaceCommand(HOUSE, wall="brick")).ok)
        self.assertEqual((world.decor.floor_of(world, HOUSE), world.decor.wall_of(world, HOUSE)), ("floor_tiles", "brick"))

    def test_nothing_said_of_one_puts_it_back_as_it_was(self) -> None:
        world = _world()
        world.apply_command(SurfaceCommand(HOUSE, floor="floor_tiles", wall="brick"))
        world.apply_command(SurfaceCommand(HOUSE, floor=""))
        self.assertEqual((world.decor.floor_of(world, HOUSE), world.decor.wall_of(world, HOUSE)), (None, "brick"))

    def test_only_of_what_there_is(self) -> None:
        world = _world()
        self.assertFalse(world.apply_command(SurfaceCommand(HOUSE, floor="floor_gold")).ok)
        self.assertFalse(world.apply_command(SurfaceCommand(HOUSE, wall="marble")).ok)
        self.assertFalse(world.apply_command(SurfaceCommand("commons", floor="floor_tiles")).ok)
        self.assertEqual((world.homes.floors, world.homes.walls), ({}, {}))


class WorthTests(unittest.TestCase):
    def test_what_is_put_in_a_house_makes_it_better_to_live_in(self) -> None:
        world = _world()
        room = world.rooms[HOUSE]
        before = world.housing.qualities(world, room)
        x, y = _free_cell(world)
        world.apply_command(DecorateCommand(HOUSE, "plant", x, y))
        world.apply_command(DecorateCommand(HOUSE, "window", 0, 0))
        after = world.housing.qualities(world, room)
        self.assertGreater(after["beauty"], before["beauty"])
        self.assertGreater(after["light"], before["light"])

    def test_so_does_what_its_floor_and_its_walls_are_made_of(self) -> None:
        world = _world()
        room = world.rooms[HOUSE]
        before = world.housing.qualities(world, room)["beauty"]
        world.apply_command(SurfaceCommand(HOUSE, wall="plaster"))
        self.assertGreater(world.housing.qualities(world, room)["beauty"], before)

    def test_every_ornament_there_is_adds_something(self) -> None:
        world = _world()
        furnishing = world.registries.housing.furnishing
        for kind in world.registries.decor.ornaments:
            self.assertIn(kind, furnishing, kind)


class SaveTests(unittest.TestCase):
    def test_how_a_building_is_dressed_survives_saving(self) -> None:
        world = _world()
        x, y = _free_cell(world)
        world.apply_command(DecorateCommand(HOUSE, "plant", x, y))
        world.apply_command(DecorateCommand(HOUSE, "clock", 1, 0))
        world.apply_command(SurfaceCommand(HOUSE, floor="floor_tiles", wall="plaster"))
        manager = SaveManager()
        loaded = manager.from_data(json.loads(json.dumps(manager.to_data(world))))
        self.assertEqual(loaded.decor.ornaments(loaded, HOUSE), world.decor.ornaments(world, HOUSE))
        self.assertEqual((loaded.decor.floor_of(loaded, HOUSE), loaded.decor.wall_of(loaded, HOUSE)), ("floor_tiles", "plaster"))
        # And the next to be put in is not given an ID that was already taken.
        loaded.apply_command(DecorateCommand(HOUSE, "picture", 4, 0))
        ids = [each.ornament_id for each in loaded.decor.ornaments(loaded, HOUSE)]
        self.assertEqual(len(ids), len(set(ids)))

    def test_an_ornament_of_a_kind_there_no_longer_is_is_not_shown_and_breaks_nothing(self) -> None:
        world = _world()
        manager = SaveManager()
        data = json.loads(json.dumps(manager.to_data(world)))
        data["housing"]["ornaments"] = {HOUSE: [{"ornament_id": "ornament_9", "kind": "gone_from_a_pack", "on": "floor", "x": 1, "y": 1}]}
        data["housing"]["floors"] = {HOUSE: "floor_gone"}
        loaded = manager.from_data(data)
        self.assertEqual(loaded.decor.ornaments(loaded, HOUSE), [])
        self.assertIsNone(loaded.decor.floor_of(loaded, HOUSE))
        loaded.housing.qualities(loaded, loaded.rooms[HOUSE])


class DataTests(unittest.TestCase):
    def test_what_there_is_to_dress_a_building_with_is_data(self) -> None:
        settings = decor_settings_from_data(json.loads((ROOT / "data" / "decor.json").read_text(encoding="utf-8")))
        self.assertTrue({each.on for each in settings.ornaments.values()} == {FLOOR, WALL})
        self.assertTrue(settings.floors and settings.walls)
        self.assertTrue(all(each.height == 1 for each in settings.ornaments.values() if each.on == WALL))
        self.assertTrue(any(each.flat for each in settings.ornaments.values()))

    def test_one_that_goes_nowhere_or_takes_no_room_is_refused(self) -> None:
        with self.assertRaises(ValueError):
            decor_settings_from_data({"ornaments": {"mobile": {"on": "ceiling"}}})
        with self.assertRaises(ValueError):
            decor_settings_from_data({"ornaments": {"speck": {"width": 0}}})

    def test_a_game_with_no_such_file_has_nothing_to_put_and_breaks_nothing(self) -> None:
        settings = decor_settings_from_data({})
        self.assertEqual((settings.ornaments, settings.floors, settings.walls), ({}, {}, {}))


if __name__ == "__main__":
    unittest.main()
