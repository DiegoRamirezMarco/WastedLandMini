import unittest
from collections import Counter

from save.save_manager import SaveManager
from simulation.ai.crowd import Crowd, free_tile, spots_taken
from simulation.ai.navigation import adjacent_spots
from simulation.events.world_event import Weather
from simulation.residents.activity import SHELTER_ACTION, WANDER_ACTION, Activity
from simulation.residents.needs import Needs
from simulation.residents.resident import Resident
from simulation.work.expedition import Expedition
from simulation.world import SimulationWorld
from ui.labels import describe_action
from world.pathfinding import find_path, line, reach, tile_of

MINUTES_PER_DAY = 24 * 60
# A doorway of the demo settlement: a wall to either side of it, the house above and the yard below.
DOOR = (18, 6)


def _world(*names: str) -> SimulationWorld:
    """The demo settlement with only the named residents in it: everybody else is out beyond the fence."""
    world = SimulationWorld.demo_world(seed=3)
    for resident in world.residents.values():
        resident.needs = Needs(hunger=0, tiredness=0, social=0, stress=0)
        if resident.resident_id not in names:
            resident.expedition = Expedition(returns_at=10**9, finds=0, danger=0.0)
    return world


def _stroll(world: SimulationWorld, name: str, start: tuple[int, int], goal: tuple[int, int], stay: int = 60) -> Resident:
    """Put a resident somewhere with a walk ahead of them, planned as if nobody else were about."""
    resident = world.residents[name]
    resident.x, resident.y, resident.trail = start[0], start[1], []
    resident.activity = Activity(WANDER_ACTION, path=find_path(start, goal, world.passable()), minutes_left=stay)
    return resident


class _Watched(unittest.TestCase):
    def assertApart(self, world: SimulationWorld, residents: list[Resident] | None = None) -> None:
        """Nobody is on a tile with anybody else, and nobody has walked this minute where another was."""
        passable = world.passable()
        present = [
            resident
            for resident in (residents or world.residents.values())
            if not resident.away and passable(resident.tile)
        ]
        standing = Counter(resident.tile for resident in present)
        self.assertEqual([tile for tile, count in standing.items() if count > 1], [], "two on one tile")
        walked = [(resident, {tile_of(point) for point in resident.trail}) for resident in present]
        for index, (one, tiles) in enumerate(walked):
            for other, theirs in walked[index + 1 :]:
                self.assertFalse(tiles & theirs, f"{one.name} and {other.name} went through each other")

    def _minute(self, world: SimulationWorld, *residents: Resident) -> None:
        """Let a minute pass for some residents alone, in the order given."""
        world.activities.begin_minute(world)
        for resident in residents:
            world.activities.tick(world, resident)
        self.assertApart(world, list(residents))


class NobodyWalksThroughAnybodyTests(_Watched):
    def test_days_of_settlement_life_pass_with_nobody_on_anybody_elses_tile(self) -> None:
        for seed in (3, 42):
            world = SimulationWorld.demo_world(seed=seed)
            held_up = 0
            for _ in range(2 * MINUTES_PER_DAY):
                world.step(1)
                self.assertApart(world)
                held_up += sum(
                    1 for resident in world.residents.values() if resident.activity is not None and resident.activity.held_up
                )
            self.assertGreater(held_up, 0, "somebody was in somebody's way at some point")
            # Nobody is left standing in front of somebody for good.
            self.assertLess(held_up, 200)

    def test_two_who_meet_head_on_go_round_each_other(self) -> None:
        world = _world("marta", "raul")
        marta = _stroll(world, "marta", (20, 18), (27, 18))
        raul = _stroll(world, "raul", (25, 18), (18, 18))
        seen = []
        for _ in range(12):
            self._minute(world, marta, raul)
            seen.extend(tile_of(point) for point in (*marta.trail, *raul.trail))
        self.assertEqual((marta.tile, raul.tile), ((27, 18), (18, 18)), "both got where they were going")
        self.assertTrue(any(y != 18 for _, y in seen), "one of them stepped out of the row")

    def test_whoever_stands_in_the_way_is_walked_round(self) -> None:
        world = _world("marta", "raul")
        raul = world.residents["raul"]
        raul.x, raul.y, raul.trail = 23, 18, []
        raul.activity = Activity(WANDER_ACTION, minutes_left=60, using=True)
        marta = _stroll(world, "marta", (20, 18), (27, 18))
        self.assertIn(raul.tile, marta.activity.path)
        minutes = 0
        while marta.tile != (27, 18):
            self._minute(world, marta, raul)
            minutes += 1
            self.assertLess(minutes, 10)
        self.assertEqual(raul.tile, (23, 18), "he was not moved")
        self.assertEqual(marta.activity.held_up, 0)

    def test_nobody_squeezes_between_two_people_who_stand_corner_to_corner(self) -> None:
        world = _world("marta", "raul", "lucia")
        raul, lucia = world.residents["raul"], world.residents["lucia"]
        raul.x, raul.y, raul.trail, raul.activity = 21, 18, [], None
        lucia.x, lucia.y, lucia.trail, lucia.activity = 20, 19, [], None
        marta = world.residents["marta"]
        marta.x, marta.y, marta.trail = 20, 18, []
        crowd = Crowd(world, marta)
        self.assertFalse(crowd.free((20, 18), (21, 19)))
        self.assertTrue(crowd.free((20, 18), (19, 19)), "past one of them there is room")
        self.assertFalse(crowd.free((20, 18), (21, 18)))
        self.assertTrue(crowd.free((20, 18), (20, 17)))

    def test_somebody_behind_another_follows_and_does_not_overtake_through_them(self) -> None:
        world = _world("marta", "raul")
        raul = _stroll(world, "raul", (21, 18), (30, 18))
        marta = _stroll(world, "marta", (20, 18), (29, 18))
        for _ in range(8):
            # She is seen to first, with him still in front of her.
            self._minute(world, marta, raul)
            self.assertLess(marta.x, raul.x)
        self.assertEqual((marta.tile, raul.tile), ((29, 18), (30, 18)))

    def test_in_a_doorway_one_of_two_who_meet_gives_way(self) -> None:
        for first in ("marta", "raul"):
            world = _world("marta", "raul")
            self.assertFalse(world.passable()((DOOR[0] - 1, DOOR[1])) or world.passable()((DOOR[0] + 1, DOOR[1])))
            marta = _stroll(world, "marta", (DOOR[0], DOOR[1] + 1), (DOOR[0], DOOR[1] - 2), stay=600)
            raul = _stroll(world, "raul", (DOOR[0], DOOR[1] - 1), (DOOR[0], DOOR[1] + 3), stay=600)
            order = (marta, raul) if first == "marta" else (raul, marta)
            met = False
            for _ in range(8):
                self._minute(world, *order)
                met = met or bool(marta.activity.held_up or raul.activity.held_up)
            self.assertTrue(met, "they did stand in each other's way")
            # Whoever gave way went off for a stroll; the other is through the door and where they were going.
            through = [
                resident.name
                for resident, goal in ((marta, (DOOR[0], DOOR[1] - 2)), (raul, (DOOR[0], DOOR[1] + 3)))
                if resident.tile == goal
            ]
            self.assertTrue(through, f"with {first} seen to first, nobody got through")
            self.assertNotIn(DOOR, (marta.tile, raul.tile), "and nobody is left standing in the doorway")

    def test_with_somebody_stopped_where_they_were_going_they_stand_somewhere_else_beside_it(self) -> None:
        world = _world("marta", "raul")
        pantry = world.interactables["pantry_1"]
        marta, raul = world.residents["marta"], world.residents["raul"]
        marta.x, marta.y, marta.trail = 20, 18, []
        raul.x, raul.y, raul.trail, raul.activity = 21, 18, [], None
        spots = adjacent_spots(world, marta, pantry)
        self.assertGreater(len(spots), 1)
        path = find_path(marta.tile, spots[0], world.passable())
        marta.activity = Activity("eat", pantry.object_id, path, 20)
        # He comes to a stop on the very tile she was making for, and stays.
        raul.x, raul.y = spots[0]
        raul.activity = Activity(WANDER_ACTION, minutes_left=600, using=True)
        self.assertNotIn(spots[0], adjacent_spots(world, marta, pantry), "it is not a place to plan for any more")
        minutes = 0
        while marta.activity is not None and marta.activity.path:
            self._minute(world, marta, raul)
            minutes += 1
            self.assertLess(minutes, 60)
        self.assertIn(marta.tile, spots[1:], "she is beside the pantry all the same")
        self.assertEqual(raul.tile, spots[0])

    def test_whoever_stands_idle_in_a_doorway_steps_aside_for_whoever_wants_through(self) -> None:
        for action in (WANDER_ACTION, SHELTER_ACTION):
            world = _world("marta", "raul")
            raul = world.residents["raul"]
            # Just inside the door, where the first one in out of the rain stops.
            raul.x, raul.y, raul.trail = DOOR[0], DOOR[1] - 1, []
            raul.activity = Activity(action, minutes_left=600, using=True)
            if action == SHELTER_ACTION:
                world.weather = Weather("dust_storm", world.clock.total_minutes + 600)
            marta = _stroll(world, "marta", (DOOR[0], DOOR[1] + 3), (DOOR[0] - 1, DOOR[1] - 2), stay=600)
            minutes = 0
            while marta.tile != (DOOR[0] - 1, DOOR[1] - 2):
                self._minute(world, marta, raul)
                self.assertEqual(marta.activity.action, WANDER_ACTION)
                self.assertEqual(marta.destination, (DOOR[0] - 1, DOOR[1] - 2), "she never gave it up")
                minutes += 1
                self.assertLess(minutes, 10)
            self._minute(world, marta, raul)
            self.assertNotEqual(raul.tile, (DOOR[0], DOOR[1] - 1), "he moved out of her way")
            self.assertEqual((raul.activity.action, raul.activity.minutes_left > 500), (action, True), "and went on as he was")
            self.assertTrue(raul.activity.using)
            self.assertTrue(world.under_roof(raul.tile), "inside still")
            self.assertEqual(describe_action(world, marta), "sin hacer nada")

    def test_what_they_are_doing_says_when_they_are_waiting_to_get_by(self) -> None:
        world = _world("marta")
        marta = _stroll(world, "marta", (20, 18), (27, 18))
        self.assertEqual(describe_action(world, marta), "pasea")
        marta.activity.held_up = 1
        self.assertEqual(describe_action(world, marta), "espera a que le dejen pasar")

    def test_whoever_cannot_get_through_gives_up_and_stands_aside(self) -> None:
        world = _world("marta", "raul")
        raul = world.residents["raul"]
        # He has stopped in the doorway, with something to do there for a long while.
        raul.x, raul.y, raul.trail = DOOR[0], DOOR[1], []
        raul.activity = Activity("work", minutes_left=600, using=True)
        marta = _stroll(world, "marta", (DOOR[0], DOOR[1] + 3), (DOOR[0], DOOR[1] - 2), stay=600)
        waited = 0
        for _ in range(10):
            world.activities.begin_minute(world)
            world.activities.tick(world, marta)
            self.assertNotEqual(marta.tile, DOOR)
            waited = max(waited, marta.activity.held_up if marta.activity is not None else 0)
            if marta.activity is None or marta.destination != (DOOR[0], DOOR[1] - 2):
                break
        self.assertGreaterEqual(waited, 2, "she waited for him first")
        self.assertNotEqual(marta.destination, (DOOR[0], DOOR[1] - 2), "and then gave it up")
        self.assertEqual(marta.activity.action, WANDER_ACTION)
        self.assertGreater(len(marta.activity.path) + abs(marta.y - DOOR[1] - 1), 0)


class PlacesToStandTests(_Watched):
    def test_no_place_is_planned_for_that_somebody_stands_on_or_is_heading_to(self) -> None:
        world = _world("marta", "raul", "lucia")
        marta, raul, lucia = (world.residents[name] for name in ("marta", "raul", "lucia"))
        marta.x, marta.y, marta.activity = 20, 18, None
        raul.x, raul.y, raul.activity = 24, 18, None
        _stroll(world, "lucia", (30, 18), (25, 18))
        self.assertEqual(spots_taken(world, marta), {(24, 18), (25, 18)})
        self.assertEqual(spots_taken(world), {(20, 18), (24, 18), (25, 18)}, "whoever is out of the settlement takes none")
        approach = world.activities.social.approach(world, marta, raul)
        self.assertEqual(approach.path[-1], (23, 18))
        # With somebody on every side of him there is nowhere to stand to talk to him.
        for name, tile in (("ines", (23, 18)), ("vera", (24, 17)), ("paco", (24, 19))):
            other = world.residents[name]
            other.expedition, other.x, other.y, other.activity = None, tile[0], tile[1], None
        self.assertIsNone(world.activities.social.approach(world, marta, raul))
        # A stroll is not to where somebody is either.
        for _ in range(200):
            self.assertNotIn(world.activities.routine._wander(world, marta).path[-1:], ([(24, 18)], [(25, 18)]))

    def test_whoever_comes_onto_the_map_is_put_where_nobody_stands(self) -> None:
        world = _world("marta", "raul")
        marta, raul = world.residents["marta"], world.residents["raul"]
        first = world.happenings.arrival_tile(world)
        marta.x, marta.y, marta.activity = first[0], first[1], None
        second = world.happenings.arrival_tile(world)
        self.assertNotEqual(second, first)
        raul.x, raul.y, raul.activity = second[0], second[1], None
        third = world.happenings.arrival_tile(world)
        self.assertNotIn(third, (first, second))
        self.assertTrue(world.passable()(third))
        self.assertEqual(free_tile(world, (20, 18)), (20, 18))
        near = free_tile(world, first)
        self.assertNotIn(near, (first, second))
        self.assertLessEqual(max(abs(near[0] - first[0]), abs(near[1] - first[1])), 2)
        self.assertEqual(free_tile(world, first, marta), first, "her own tile is free to her")

    def test_how_long_they_have_been_held_up_is_saved(self) -> None:
        world = _world("marta", "raul")
        marta = _stroll(world, "marta", (20, 18), (27, 18))
        marta.activity.held_up = 2
        manager = SaveManager()
        data = manager.to_data(world)
        self.assertEqual(manager.from_data(data).residents["marta"].activity.held_up, 2)
        next(entry for entry in data["residents"] if entry["id"] == "marta")["activity"].pop("held_up")
        self.assertEqual(manager.from_data(data).residents["marta"].activity.held_up, 0, "an older save has none")


class ReachTests(unittest.TestCase):
    def test_what_is_within_reach_is_what_can_be_walked_to_nearest_first(self) -> None:
        rows = [
            ".....",
            "..#..",
            ".....",
        ]
        passable = lambda tile: 0 <= tile[1] < 3 and 0 <= tile[0] < 5 and rows[tile[1]][tile[0]] == "."  # noqa: E731
        near = reach((1, 1), 1, passable)
        self.assertEqual(set(near), {(1, 0), (0, 0), (0, 1), (0, 2), (1, 2)}, "not past the corner of what is in the way")
        further = reach((1, 1), 4, passable)
        self.assertNotIn((1, 1), further)
        self.assertNotIn((2, 1), further)
        self.assertEqual(further[(3, 1)], 4, "round the corner, not across it")
        self.assertEqual(list(further.values()), sorted(further.values()))
        self.assertEqual(len(reach((2, 1), 1, passable)), 8, "from where nobody can stand, to every side of it")
        self.assertEqual(line((0, 0), (2, 0)), [(1, 0), (2, 0)])
