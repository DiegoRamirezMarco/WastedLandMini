import json
import tempfile
import unittest
from collections import Counter
from pathlib import Path

from save.save_manager import SaveManager
from simulation.knowledge.knowledge_system import witnesses_of
from simulation.registries import DATA_DIR, BuiltInRegistries, builtin_registries
from simulation.residents.activity import Activity
from simulation.residents.needs import Needs
from simulation.social.social_system import PURSUIT_MINUTES, TALK_ACTION, SocialSystem
from simulation.work.hauling import carried
from simulation.work.job import job_definition_from_data
from simulation.work.work_system import WORK_ACTION, minutes_left_in_shift
from simulation.world import SimulationWorld
from world.pathfinding import find_path, manhattan
from world.settlement import layout_from_data

MINUTES_PER_DAY = 24 * 60


def _settled(seed: int = 7) -> SimulationWorld:
    """The demo settlement with everyone content and no grudges, so only work drives the day."""
    world = SimulationWorld.demo_world(seed=seed)
    world.relationships.clear()
    for resident in world.residents.values():
        resident.needs = Needs(hunger=0, tiredness=0, social=0, stress=0)
    return world


def _set_time(world: SimulationWorld, hour: int, minute: int = 0) -> None:
    world.clock.hour, world.clock.minute = hour, minute


def _keep_content(world: SimulationWorld, *resident_ids: str) -> None:
    for resident_id in resident_ids or world.residents:
        world.residents[resident_id].needs = Needs(hunger=0, tiredness=0, social=0, stress=0)


def _run_until_on_duty(world: SimulationWorld, resident_id: str, limit: int = 180) -> None:
    resident = world.residents[resident_id]
    for _ in range(limit):
        world.step(1)
        _keep_content(world)
        if world.work.on_duty(world, resident):
            return
    raise AssertionError(f"{resident_id} never reached their post")


def _count(world: SimulationWorld, item_id: str, *container_ids: str) -> int:
    return sum(world.containers[container_id].count(item_id) for container_id in container_ids)


def _types(world: SimulationWorld) -> list[str]:
    return [line.split(" | ")[1] for line in world.event_log]


def _registries_with(file_name: str, old: str, new: str) -> BuiltInRegistries:
    """Registries loaded from a copy of the data folder with one piece of text replaced."""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "data"
        (root / "maps").mkdir(parents=True)
        for path in DATA_DIR.rglob("*.json"):
            text = path.read_text(encoding="utf-8")
            if path.name == file_name:
                assert old in text, old
                text = text.replace(old, new)
            (root / path.relative_to(DATA_DIR)).write_text(text, encoding="utf-8")
        return BuiltInRegistries.load(root)


class ShiftTests(unittest.TestCase):
    def setUp(self) -> None:
        self.day = job_definition_from_data("d", {"name": "D", "station": "x", "shifts": [[8, 13], [15, 18]], "text": "t"})
        self.night = job_definition_from_data("n", {"name": "N", "station": "x", "shifts": [[22, 6]], "text": "t"})

    def test_minutes_left_inside_and_outside_a_shift(self) -> None:
        self.assertEqual(minutes_left_in_shift(self.day, 8, 0), 300)
        self.assertEqual(minutes_left_in_shift(self.day, 12, 59), 1)
        self.assertEqual(minutes_left_in_shift(self.day, 13, 0), 0)
        self.assertEqual(minutes_left_in_shift(self.day, 16, 30), 90)
        self.assertEqual(minutes_left_in_shift(self.day, 3, 0), 0)

    def test_a_shift_can_run_past_midnight(self) -> None:
        self.assertEqual(minutes_left_in_shift(self.night, 23, 0), 7 * 60)
        self.assertEqual(minutes_left_in_shift(self.night, 5, 30), 30)
        self.assertEqual(minutes_left_in_shift(self.night, 12, 0), 0)

    def test_a_job_needs_shifts_and_a_sensible_product(self) -> None:
        with self.assertRaisesRegex(ValueError, "shifts"):
            job_definition_from_data("x", {"name": "X", "station": "x", "shifts": [], "text": "t"})
        with self.assertRaisesRegex(ValueError, "every_minutes"):
            job_definition_from_data(
                "x", {"name": "X", "station": "x", "shifts": [[8, 9]], "text": "t", "produces": {"item": "stew"}}
            )


class GoingToWorkTests(unittest.TestCase):
    def setUp(self) -> None:
        self.world = _settled()
        self.raul = self.world.residents["raul"]
        self.plan = lambda: self.world.activities.routine.plan(self.world, self.raul)

    def test_everyone_in_the_demo_has_a_post_of_the_right_kind(self) -> None:
        for resident in self.world.residents.values():
            job = self.world.work.job_of(self.world, resident)
            self.assertIsNotNone(job, resident.name)
            self.assertEqual(self.world.interactables[resident.post_id].kind, job.station, resident.name)

    def test_during_their_shift_a_resident_heads_for_their_post(self) -> None:
        _set_time(self.world, 9)
        activity = self.plan()
        self.assertEqual((activity.action, activity.target_id), (WORK_ACTION, "crop_1"))

    def test_outside_their_shift_they_do_something_else(self) -> None:
        for hour in (7, 14, 20):
            _set_time(self.world, hour)
            self.assertNotEqual(self.plan().action, WORK_ACTION, hour)

    def test_a_pressing_bodily_need_comes_before_work_but_loneliness_does_not(self) -> None:
        _set_time(self.world, 9)
        self.raul.needs.hunger = 85
        self.assertEqual(self.plan().action, "eat")
        self.raul.needs = Needs(hunger=0, tiredness=0, social=99, stress=0)
        self.assertIsNotNone(self.world.work.candidate(self.world, self.raul))

    def test_someone_without_a_job_never_goes_to_work(self) -> None:
        self.raul.job_id = self.raul.post_id = None
        _set_time(self.world, 9)
        self.assertIsNone(self.world.work.candidate(self.world, self.raul))
        self.assertNotEqual(self.plan().action, WORK_ACTION)

    def test_they_stand_at_their_post_until_the_shift_ends(self) -> None:
        tomas = self.world.residents["tomas"]
        _set_time(self.world, 9)
        _run_until_on_duty(self.world, "tomas")
        post = self.world.interactables["guard_post"]
        self.assertEqual(manhattan(tomas.tile, (post.x, post.y)), 1)
        self.assertEqual(tomas.current_action, WORK_ACTION)
        self.assertEqual(sum("Tomás empieza su turno" in line for line in self.world.event_log), 1)
        where = tomas.tile
        while (self.world.clock.hour, self.world.clock.minute) != (12, 58):
            self.world.step(1)
            _keep_content(self.world)
            self.assertTrue(self.world.work.on_duty(self.world, tomas), self.world.clock.label)
            self.assertEqual(tomas.tile, where)
        self.world.step(2)
        self.assertFalse(self.world.work.on_duty(self.world, tomas))


class ProductionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.world = _settled()
        self.pantries = ("pantry_1", "pantry_2")

    def test_a_morning_in_the_garden_fills_the_pantries_with_vegetables(self) -> None:
        self.assertEqual(_count(self.world, "vegetables", *self.pantries), 0)
        _set_time(self.world, 8)
        for _ in range(5 * 60):
            self.world.step(1)
            _keep_content(self.world)
        grown = [self.world.containers[pantry].count("vegetables") for pantry in self.pantries]
        self.assertGreaterEqual(sum(grown), 16)
        self.assertLessEqual(abs(grown[0] - grown[1]), 6, "the harvest is shared between the pantries, a load at a time")

    def test_nothing_grows_while_nobody_tends_the_garden(self) -> None:
        for resident_id in ("raul", "ines"):
            self.world.residents[resident_id].job_id = None
        _set_time(self.world, 8)
        for _ in range(5 * 60):
            self.world.step(1)
            _keep_content(self.world)
        self.assertEqual(_count(self.world, "vegetables", *self.pantries), 0)

    def test_a_full_pantry_takes_no_more(self) -> None:
        self.world.residents["marta"].job_id = None
        for pantry in self.pantries:
            self.world.stock(self.world.containers[pantry], "vegetables", 40, None)
        _set_time(self.world, 8)
        for _ in range(5 * 60):
            self.world.step(1)
            _keep_content(self.world)
        self.assertEqual(_count(self.world, "vegetables", *self.pantries), 80)
        for farmer_id in ("raul", "ines"):
            # With nowhere to take it, a farmer stops once their hands are full.
            self.assertEqual(carried(self.world.residents[farmer_id], "vegetables"), 6)

    def test_the_cook_turns_raw_food_into_stew_one_for_one(self) -> None:
        pot = self.world.containers["cooking_pot"]
        pot.items.clear()
        for resident_id in ("raul", "ines"):
            self.world.residents[resident_id].job_id = None
        raw_before = sum(item.quantity for pantry in self.pantries for item in self.world.containers[pantry].items)
        _set_time(self.world, 11)
        for _ in range(3 * 60):
            self.world.step(1)
            _keep_content(self.world)
        cooked = pot.count("stew")
        self.assertGreaterEqual(cooked, 6)
        self.assertLessEqual(cooked, 10, "the pot only holds so much")
        raw_after = sum(item.quantity for pantry in self.pantries for item in self.world.containers[pantry].items)
        in_hand = sum(item.quantity for item in self.world.residents["marta"].inventory.items if item.owner_id is None)
        self.assertEqual(raw_before - raw_after, cooked + in_hand, "every unit taken was cooked or is still on her")

    def test_with_nothing_to_cook_the_pot_stays_empty_and_cooked_food_is_not_cooked_again(self) -> None:
        pot = self.world.containers["cooking_pot"]
        pot.items.clear()
        for resident_id in ("raul", "ines"):
            self.world.residents[resident_id].job_id = None
        for pantry in self.pantries:
            self.world.containers[pantry].items.clear()
        self.world.stock(self.world.containers["pantry_1"], "stew", 5, None)
        _set_time(self.world, 11)
        for _ in range(3 * 60):
            self.world.step(1)
            _keep_content(self.world)
        self.assertEqual(pot.count("stew"), 0)
        self.assertEqual(self.world.containers["pantry_1"].count("stew"), 5)


class StaffedPlacesTests(unittest.TestCase):
    def setUp(self) -> None:
        self.world = _settled()
        self.raul, self.lucia = self.world.residents["raul"], self.world.residents["lucia"]
        self.raul.job_id = None

    def _drinks(self) -> list[str]:
        candidates = self.world.activities.routine.candidates(self.world, self.raul)
        return [candidate.name for candidate in candidates if candidate.name == "drink"]

    def test_the_bar_serves_only_while_someone_is_behind_it(self) -> None:
        self.raul.needs.stress = 80
        _set_time(self.world, 15)
        self.assertEqual(self._drinks(), [])
        _set_time(self.world, 18)
        _run_until_on_duty(self.world, "lucia")
        self.assertTrue(self.world.work.is_staffed(self.world, "bartender"))
        self.raul.needs.stress = 80
        self.assertEqual(self._drinks(), ["drink"])

    def test_arriving_after_the_bar_has_closed_gets_nothing(self) -> None:
        _set_time(self.world, 18)
        _run_until_on_duty(self.world, "lucia")
        self.raul.needs.stress = 80
        self.raul.activity = self.world.activities.routine._use(self.world, self.raul, self.world.interactables["bar"])
        self.assertEqual(self.raul.activity.action, "drink")
        self.lucia.activity = None
        self.lucia.job_id = None
        for _ in range(60):
            self.world.step(1)
            if self.raul.activity is None or self.raul.activity.action != "drink":
                break
        self.assertFalse(any("Raúl toma algo" in line for line in self.world.event_log))

    def test_a_guard_on_duty_sees_further_than_anyone_else(self) -> None:
        tomas = self.world.residents["tomas"]
        post = self.world.interactables["guard_post"]
        far = (post.x + 12, post.y - 1)
        for resident in self.world.residents.values():
            if resident is not tomas:
                resident.x, resident.y = 3, 3
        tomas.x, tomas.y = post.x, post.y - 1
        self.assertEqual(witnesses_of(self.world, far), [])
        tomas.activity = Activity(WORK_ACTION, "guard_post", minutes_left=60, using=True)
        self.assertEqual(witnesses_of(self.world, far), ["tomas"])
        tomas.job_id = "farmer"
        self.assertEqual(witnesses_of(self.world, far), [], "the long sight goes with the job, not the spot")

    def test_a_worker_can_be_drawn_into_a_chat_and_then_goes_back_to_work(self) -> None:
        ines = self.world.residents["ines"]
        _set_time(self.world, 8)
        _run_until_on_duty(self.world, "ines")
        self.raul.needs.social = 90
        partners = [c.partner_id for c in SocialSystem().candidates(self.world, self.raul)]
        self.assertIn("ines", partners)
        self.raul.activity = SocialSystem().approach(self.world, self.raul, ines)
        talked = False
        for _ in range(120):
            self.world.step(1)
            talked = talked or ines.current_action in ("chat", "argument")
            if talked and ines.current_action == WORK_ACTION:
                break
        self.assertTrue(talked)
        self.assertEqual(ines.current_action, WORK_ACTION)


class BodyAndWorkTests(unittest.TestCase):
    """Regressions found while giving residents jobs."""

    def setUp(self) -> None:
        self.world = _settled()
        self.raul = self.world.residents["raul"]

    def test_a_starving_worker_leaves_to_eat_and_comes_back(self) -> None:
        _set_time(self.world, 8)
        _run_until_on_duty(self.world, "raul")
        self.raul.needs.hunger = 90
        self.world.step(1)
        self.assertFalse(self.world.work.on_duty(self.world, self.raul))
        ate = back = False
        for _ in range(200):
            self.world.step(1)
            ate = ate or self.raul.current_action == "eat"
            back = ate and self.world.work.on_duty(self.world, self.raul)
            if back:
                break
        self.assertTrue(ate and back)

    def test_loneliness_never_wakes_a_sleeper(self) -> None:
        tomas = self.world.residents["tomas"]
        _set_time(self.world, 23)
        tomas.needs = Needs(hunger=0, tiredness=70, social=99, stress=0)
        tomas.x, tomas.y = 5, 24
        tomas.activity = Activity("sleep", "bed_5", minutes_left=600, using=True)
        self.world.step(120)
        self.assertEqual((tomas.activity.action, tomas.activity.using), ("sleep", True))
        self.assertFalse(self.world.is_aware(tomas))

    def test_nobody_goes_to_bed_on_an_empty_stomach(self) -> None:
        _set_time(self.world, 23)
        self.raul.needs = Needs(hunger=75, tiredness=70, social=0, stress=0)
        self.assertEqual(self.world.activities.routine.plan(self.world, self.raul).action, "eat")
        self.raul.needs.hunger = 20
        self.assertEqual(self.world.activities.routine.plan(self.world, self.raul).action, "sleep")

    def test_asleep_hunger_grows_at_half_the_pace(self) -> None:
        awake, asleep = Needs(hunger=10, social=10), Needs(hunger=10, social=10)
        awake.step(100)
        asleep.step(100, resting=True)
        self.assertAlmostEqual(asleep.hunger - 10, (awake.hunger - 10) / 2)
        self.assertAlmostEqual(asleep.social - 10, (awake.social - 10) / 2)
        self.assertEqual(asleep.tiredness, awake.tiredness)

    def test_a_chase_is_given_up_even_if_the_other_never_stands_still(self) -> None:
        marta = self.world.residents["marta"]
        self.raul.job_id = None
        self.raul.activity = SocialSystem().pursue(self.world, self.raul, marta, "argument")
        spots = [(6, 9), (35, 12), (16, 30), (50, 12)]
        for minute in range(PURSUIT_MINUTES + 30):
            marta.x, marta.y = spots[(minute // 15) % len(spots)]
            marta.activity = Activity("wander", minutes_left=5, using=True)
            self.world.step(1)
            _keep_content(self.world)
            chasing = self.raul.activity is not None and self.raul.activity.intent == "argument"
            if not chasing and self.raul.current_action not in ("argument",):
                break
        self.assertLess(minute, PURSUIT_MINUTES + 5)
        self.assertFalse(self.raul.activity is not None and self.raul.activity.action == TALK_ACTION)

    def test_an_exhausted_resident_naps_by_day_and_a_merely_tired_one_does_not(self) -> None:
        _set_time(self.world, 14)
        self.raul.needs.tiredness = 95
        self.assertEqual(self.world.activities.routine.plan(self.world, self.raul).action, "sleep")
        self.raul.needs.tiredness = 60
        self.assertNotEqual(self.world.activities.routine.plan(self.world, self.raul).action, "sleep")


class SettlementLayoutTests(unittest.TestCase):
    def test_every_building_and_premises_can_be_walked_into(self) -> None:
        world = SimulationWorld.demo_world()
        passable = world.passable()
        start = world.registries.maps[world.map_id].spawns[0]
        self.assertGreaterEqual(len(world.rooms), 8)
        for room in world.rooms.values():
            inside = [
                (x, y)
                for x in range(room.x, room.x + room.width)
                for y in range(room.y, room.y + room.height)
                if passable((x, y))
            ]
            self.assertTrue(inside, room.room_id)
            self.assertIsNotNone(find_path(start, inside[0], passable), room.room_id)

    def test_the_buildings_have_a_roof_and_the_open_places_do_not(self) -> None:
        world = SimulationWorld.demo_world()
        roofed = {room.room_id for room in world.rooms.values() if room.roofed}
        self.assertEqual(roofed, {"dormitory", "storehouse", "cantina", "south_house", "workshop", "clinic", "shop"})
        for room_id in roofed:
            room = world.rooms[room_id]
            around = [
                (x, y)
                for x in range(room.x - 1, room.x + room.width + 1)
                for y in range(room.y - 1, room.y + room.height + 1)
                if not room.contains((x, y))
            ]
            for tile in around:
                self.assertIn(world.tile_map.terrain_at(tile), ("wall", "door"), (room_id, tile))

    def test_a_room_has_no_roof_unless_its_map_says_so(self) -> None:
        data = {
            "id": "camp",
            "legend": {".": "dirt"},
            "rows": ["...."],
            "rooms": [
                {"id": "yard", "x": 0, "y": 0, "width": 2, "height": 1},
                {"id": "hut", "x": 2, "y": 0, "width": 2, "height": 1, "roofed": True},
            ],
        }
        rooms = layout_from_data(data).rooms
        self.assertFalse(rooms["yard"].roofed)
        self.assertTrue(rooms["hut"].roofed)

    def test_there_is_a_bed_for_everyone_and_the_old_quarter_is_where_it_was(self) -> None:
        world = SimulationWorld.demo_world()
        beds = [placed for placed in world.interactables.values() if placed.kind == "bed"]
        self.assertGreaterEqual(len(beds), len(world.residents))
        self.assertEqual((world.interactables["campfire"].x, world.interactables["campfire"].y), (19, 11))
        self.assertEqual(world.room_at((6, 5)).room_id, "dormitory")
        self.assertEqual(world.room_at((46, 6)).room_id, "cantina")

    def test_the_settlement_is_larger_than_one_screen(self) -> None:
        tile_map = SimulationWorld.demo_world().tile_map
        self.assertGreater(tile_map.width, 40)
        self.assertGreater(tile_map.height, 21)


class WorkingWeekTests(unittest.TestCase):
    def test_a_week_of_work_feeds_the_settlement(self) -> None:
        world = SimulationWorld.demo_world(seed=3)
        hours = {resident_id: Counter() for resident_id in world.residents}
        for _ in range(7 * MINUTES_PER_DAY):
            world.step(1)
            for resident_id, resident in world.residents.items():
                # Whoever comes to stay in the middle of the week is not held to a week of it.
                if resident_id in hours:
                    hours[resident_id][resident.current_action] += 1
                for need in ("hunger", "tiredness", "social", "stress"):
                    self.assertLess(getattr(resident.needs, need), 100.0, (resident.name, need, world.clock.label))
        for resident_id, actions in hours.items():
            # The scavenger's work is done out there.
            worked = actions[WORK_ACTION] + actions["expedition"]
            self.assertGreater(worked / 7 / 60, 2.0, f"{resident_id} barely worked")
            self.assertGreater(actions["sleep"] / 7 / 60, 6.0, f"{resident_id} barely slept")
        self.assertNotIn("no_food", _types(world))
        self.assertTrue(any("guiso caliente" in line for line in world.event_log))
        self.assertTrue(any("toma algo en la cantina" in line for line in world.event_log))


class WorkDataAndSaveTests(unittest.TestCase):
    def test_a_job_at_an_unknown_kind_of_post_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "unknown object kind: throne"):
            _registries_with("jobs.json", '"station": "guard_post"', '"station": "throne"')

    def test_a_job_that_makes_something_undefined_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "unknown item: caviar"):
            _registries_with("jobs.json", '"item": "stew"', '"item": "caviar"')

    def test_an_object_cannot_give_less_than_no_light(self) -> None:
        with self.assertRaisesRegex(ValueError, "negative amount of light"):
            _registries_with("interactables.json", '"light": 6', '"light": -1')

    def test_a_place_staffed_by_an_unknown_job_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "unknown job: sommelier"):
            _registries_with("interactables.json", '"staffed_by": "bartender"', '"staffed_by": "sommelier"')

    def test_saving_mid_shift_continues_exactly_like_not_saving(self) -> None:
        manager = SaveManager()
        original = SimulationWorld.demo_world(seed=5)
        original.step(4 * 60 + 30)
        self.assertTrue(any(original.work.on_duty(original, r) for r in original.residents.values()))
        loaded = manager.from_data(json.loads(json.dumps(manager.to_data(original))))
        self.assertEqual(manager.to_data(loaded), manager.to_data(original))
        self.assertEqual(loaded.residents["marta"].job_id, "cook")
        original.step(2 * MINUTES_PER_DAY)
        loaded.step(2 * MINUTES_PER_DAY)
        self.assertEqual(manager.to_data(loaded), manager.to_data(original))

    def test_a_save_from_before_jobs_gets_the_new_buildings_and_jobless_residents(self) -> None:
        manager = SaveManager()
        world = SimulationWorld.demo_world()
        data = manager.to_data(world)
        data["version"] = 5
        old_objects = {"bed_1", "bed_2", "bed_3", "crate_dorm", "pantry_1", "pantry_2", "crate_1", "campfire", "table"}
        data["interactables"] = [placed for placed in data["interactables"] if placed["id"] in old_objects]
        data["residents"] = [r for r in data["residents"] if r["id"] in ("marta", "raul", "lucia")]
        for resident in data["residents"]:
            for key in ("job_id", "post_id", "work_progress"):
                del resident[key]
        loaded = manager.from_data(data)
        self.assertIn("cooking_pot", loaded.interactables)
        self.assertIn("cooking_pot", loaded.containers)
        self.assertEqual(loaded.containers["pantry_1"].count("canned_beans"), world.containers["pantry_1"].count("canned_beans"))
        self.assertEqual([r.job_id for r in loaded.residents.values()], [None, None, None])
        loaded.step(MINUTES_PER_DAY)

    def test_the_demo_registries_know_every_job(self) -> None:
        self.assertEqual(
            sorted(builtin_registries().jobs),
            [
                "bartender", "chemist", "cook", "farmer", "guard", "mechanic", "medic", "researcher", "scavenger",
                "shopkeeper", "water_carrier",
            ],
        )


if __name__ == "__main__":
    unittest.main()
