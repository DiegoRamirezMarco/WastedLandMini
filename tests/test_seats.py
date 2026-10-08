"""Something to sit on: whoever is at a thing done sitting down takes a free seat beside it, and is seen on it."""

import os
import tempfile
import unittest
from pathlib import Path

import pygame

from graphics.poses import builtin_poses, poses_from_data
from settings import TILE_SIZE
from simulation.ai.navigation import adjacent_spots, seat_at
from simulation.residents.activity import Activity
from simulation.residents.manner import SIT
from simulation.world import SimulationWorld
from skeleton.plan import builtin_plan
from world.custom_content import _definition_data
from world.interactable import Interactable, interactable_definition_from_data

STOOL = {"name": "taburete", "article": "un", "blocks": False, "seat": True}


class SeatDataTests(unittest.TestCase):
    def test_a_seat_is_one_tile_that_can_be_stood_on_and_says_so_in_its_data(self) -> None:
        stool = interactable_definition_from_data("stool", STOOL)
        self.assertTrue(stool.seat)
        self.assertFalse(interactable_definition_from_data("crate", {"name": "caja", "article": "una"}).seat)
        for wrong in ({**STOOL, "blocks": True}, {**STOOL, "width": 2}, {**STOOL, "height": 2}):
            with self.assertRaises(ValueError, msg=wrong):
                interactable_definition_from_data("stool", wrong)
        # A pack's own object keeps it when it is written out and read again.
        written = _definition_data(stool)
        self.assertTrue(written["seat"])
        again = interactable_definition_from_data("stool", {key: value for key, value in written.items() if key != "id"})
        self.assertTrue(again.seat)

    def test_the_stools_the_game_comes_with_are_seats_and_nothing_else_is(self) -> None:
        world = SimulationWorld.demo_world()
        seats = {placed.kind for placed in world.interactables.values() if world.definition_of(placed).seat}
        self.assertEqual(seats, {"stool"})
        fire = world.interactables["campfire"]
        self.assertEqual(seat_at(world, (fire.x, fire.y - 1)).kind, "stool")
        self.assertIsNone(seat_at(world, (fire.x, fire.y)), "the fire is no seat")
        self.assertIsNone(seat_at(world, (fire.x + 3, fire.y + 3)))

    def test_on_a_seat_anybody_sits_the_same_way_and_at_its_height(self) -> None:
        poses, plan = builtin_poses(), builtin_plan()
        self.assertIn(poses.seat.clip, plan.clips)
        self.assertEqual(plan.frames(poses.seat.clip, "side"), 1)
        self.assertIsNone(poses_from_data({}).seat, "where nothing is said of it they sit as on the ground")
        standing, seated = plan.pose("doll_right"), plan.pose("doll_right", poses.seat.clip)
        down = seated["pelvis"][1] - standing["pelvis"][1]
        self.assertGreater(down, 0.5)
        self.assertLess(down, 3.0, "a seat is not the ground: the hips are only a little lower than they stand")
        self.assertGreater(seated["knee_right"][0], seated["hip_right"][0] + 2.0, "the thighs are out ahead")
        self.assertGreater(seated["foot_right"][1], seated["knee_right"][1] + 2.0, "and the shins hang down")
        self.assertLessEqual(max(y for _, y in seated.values()), 1e-6)
        ground = {manner.clip for manner in SimulationWorld.demo_world().registries.manners.of_kind("sit")}
        self.assertNotIn(poses.seat.clip, ground, "it is nobody's own way of sitting")


class TakingASeatTests(unittest.TestCase):
    """Runs the simulation alone."""

    def setUp(self) -> None:
        self.world = SimulationWorld.demo_world(seed=3)
        self.routine = self.world.activities.routine
        self.fire = self.world.interactables["campfire"]
        self.raul = self.world.residents["raul"]
        for resident in self.world.residents.values():
            resident.x, resident.y, resident.trail, resident.activity = 2, 2 + len(resident.resident_id), [], None

    def _only_stool(self, tile: tuple[int, int]) -> None:
        """Leave the fire one stool, on one side of it."""
        for object_id in [placed.object_id for placed in self.world.interactables.values() if placed.kind == "stool"]:
            del self.world.interactables[object_id]
        self.world.interactables["stool_test"] = Interactable("stool_test", "stool", *tile)

    def test_whoever_goes_to_sit_by_the_fire_takes_the_free_stool_though_the_ground_is_nearer(self) -> None:
        fire, raul = self.fire, self.raul
        self.assertIsNotNone(self.world.registries.manners.during(SIT, self.world.definition_of(fire).use.action))
        self._only_stool((fire.x + 1, fire.y))
        raul.x, raul.y = fire.x - 4, fire.y
        nearest = adjacent_spots(self.world, raul, fire)[0]
        self.assertEqual(nearest, (fire.x - 1, fire.y), "the near side of the fire is bare ground")
        going = self.routine._use(self.world, raul, fire)
        self.assertEqual(going.path[-1], (fire.x + 1, fire.y), "and he goes round to the stool")
        self.assertEqual(going.action, "relax")

    def test_a_stool_somebody_has_is_not_free_and_the_next_one_sits_on_the_ground(self) -> None:
        fire, raul = self.fire, self.raul
        self._only_stool((fire.x + 1, fire.y))
        ines = self.world.residents["ines"]
        ines.x, ines.y = fire.x + 1, fire.y
        ines.activity = Activity("relax", fire.object_id, minutes_left=40, using=True)
        raul.x, raul.y = fire.x - 4, fire.y
        going = self.routine._use(self.world, raul, fire)
        self.assertEqual(going.path[-1], (fire.x - 1, fire.y))

    def test_what_is_not_done_sitting_down_is_done_from_the_nearest_spot_stool_or_no_stool(self) -> None:
        bench = self.world.interactables["workbench"]
        use = self.world.definition_of(bench).use
        self.assertIsNone(self.world.registries.manners.during(SIT, use.action))
        raul = self.raul
        raul.x, raul.y = bench.x, bench.y + 4
        spots = adjacent_spots(self.world, raul, bench)
        if len(spots) < 2:
            self.skipTest("the bench has one side to stand at")
        without = self.routine._use(self.world, raul, bench).path[-1]
        other = next(spot for spot in spots if spot != without)
        self._only_stool(other)
        self.assertEqual(self.routine._use(self.world, raul, bench).path[-1], without, "the stool beside it changes nothing")

    def test_with_a_stool_on_every_side_of_the_fire_nothing_changes_of_where_they_go(self) -> None:
        fire, raul = self.fire, self.raul
        raul.x, raul.y = fire.x - 4, fire.y + 1
        spots = adjacent_spots(self.world, raul, fire)
        self.assertTrue(all(seat_at(self.world, spot) is not None for spot in spots))
        self.assertEqual(self.routine._use(self.world, raul, fire).path[-1], spots[0])


class SittingOnASeatTests(unittest.TestCase):
    """Runs the real game without a window, with folders of its own for drawings and content."""

    def setUp(self) -> None:
        for variable in ("SDL_VIDEODRIVER", "SDL_AUDIODRIVER"):
            self.addCleanup(self._restore_driver, variable, os.environ.get(variable))
            os.environ[variable] = "dummy"
        from game.game import Game

        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        (self.root / "illustrations").mkdir()
        (self.root / "custom").mkdir()
        self.game = Game(
            illustrations_dir=self.root / "illustrations",
            voices_dir=None,
            custom_content_dir=self.root / "custom",
            save_path=self.root / "save.json",
            start_in_menu=False,
        )
        self.addCleanup(pygame.quit)
        self.view, self.world = self.game.global_view, self.game.world
        self.fire = self.world.interactables["campfire"]
        for resident in self.world.residents.values():
            resident.x, resident.y, resident.trail, resident.activity = 2, 2, [], None
        self.view.centre_on((self.fire.x + 0.5, self.fire.y + 0.5))
        self.view.following = None

    @staticmethod
    def _restore_driver(variable: str, previous: str | None) -> None:
        if previous is None:
            os.environ.pop(variable, None)
        else:
            os.environ[variable] = previous

    def _at_the_fire(self, name: str, tile: tuple[int, int]):
        resident = self.world.residents[name]
        resident.x, resident.y, resident.facing = tile[0], tile[1], "right"
        resident.activity = Activity("relax", self.fire.object_id, minutes_left=40, using=True)
        return resident

    def test_whoever_has_a_seat_under_them_sits_on_it_and_whoever_has_none_sits_their_own_way(self) -> None:
        view, fire = self.view, self.fire
        on_stool = self._at_the_fire("raul", (fire.x - 1, fire.y))
        on_ground = self._at_the_fire("ines", (fire.x - 2, fire.y))
        seat = view.poses.seat
        self.assertEqual(view._seat_of(on_stool), (seat.clip, seat.rate))
        self.assertEqual(view._seat_under(on_stool).kind, "stool")
        own = self.world.manner_of(on_ground, "sit")
        self.assertEqual(view._seat_of(on_ground), (own.clip, own.rate))
        self.assertIsNone(view._seat_under(on_ground))
        view.render()
        self.game.present()
        self.assertEqual(view.bodies.characters["raul"].clip, seat.clip)
        self.assertEqual(view.bodies.characters["ines"].clip, own.clip)
        # On a seat they are a good deal higher than on the ground: their name is too.
        self.assertLess(view.hitboxes["raul"].top, view.hitboxes["ines"].top)

    def test_they_are_in_front_of_the_seat_they_are_on_and_only_while_they_sit(self) -> None:
        view, fire = self.view, self.fire
        raul = self._at_the_fire("raul", (fire.x - 1, fire.y))
        view.render()
        self.game.present()
        doll = view._doll_of("raul")
        depth = next(entry[0] for entry in view._doll_draws if entry[1] is doll)
        stool_foot = (raul.y + 1) * TILE_SIZE
        self.assertGreater(depth, stool_foot, "drawn after the stool, which stands on the same tile")
        # Standing on that tile with nothing to do they are where their feet are, as anybody is.
        raul.activity = None
        self.assertIsNone(view._seat_under(raul))
        view.render()
        self.game.present()
        standing = next(entry[0] for entry in view._doll_draws if entry[1] is doll)
        self.assertLess(standing, stool_foot)
        # Eating on a seat, they eat with their arms over the way anybody sits on one.
        raul.activity = Activity("eat", "pantry_1", minutes_left=10, using=True, item_id="canned_beans")
        clip, _, over = view._bearing(raul)
        self.assertEqual((clip, over), (view.poses.seat.clip, self.world.manner_of(raul, "eat").clip))


if __name__ == "__main__":
    unittest.main()
