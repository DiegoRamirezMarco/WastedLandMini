import json
import tempfile
import unittest
from pathlib import Path

from save.save_manager import SaveManager
from simulation.commands import (
    CancelSiteCommand,
    MoveObjectCommand,
    PlaceBuildingCommand,
    PlaceObjectCommand,
    ProposeBuildingCommand,
    ProposeObjectCommand,
)
from simulation.registries import DATA_DIR, BuiltInRegistries
from simulation.residents.needs import Needs
from simulation.residents.personality import Personality
from simulation.work.construction import BUILD_ACTION, NEEDS_BUILDING
from simulation.world import SimulationWorld
from world.build import BUILDING_SITE, OBJECT_SITE, BuildRule, build_rule_from_data
from world.urbanism import SITE_IN_THE_WAY

MINUTES_PER_DAY = 24 * 60
SCRAP_PILES = ("scrap_workshop", "scrap_yard")


def _settled(seed: int = 7) -> SimulationWorld:
    """The demo settlement with everyone content and no grudges, so only work and building drive the day."""
    world = SimulationWorld.demo_world(seed=seed)
    world.relationships.clear()
    _keep_content(world)
    return world


def _keep_content(world: SimulationWorld) -> None:
    for resident in world.residents.values():
        resident.needs = Needs(hunger=0, tiredness=0, social=0, stress=0)


def _only(world: SimulationWorld, *resident_ids: str) -> None:
    for resident_id in [each for each in world.residents if each not in resident_ids]:
        del world.residents[resident_id]


def _set_time(world: SimulationWorld, hour: int, minute: int = 0) -> None:
    world.clock.hour, world.clock.minute = hour, minute


def _run(world: SimulationWorld, minutes: int, until=None) -> bool:
    """Let time pass with nobody wanting for anything. True as soon as `until` holds."""
    for _ in range(minutes):
        world.step(1)
        _keep_content(world)
        if until is not None and until():
            return True
    return False


def _scrap(world: SimulationWorld) -> int:
    return sum(world.containers[pile].count("scrap") for pile in SCRAP_PILES)


def _in_hand(world: SimulationWorld) -> int:
    return sum(resident.inventory.count("scrap") for resident in world.residents.values())


def _types(world: SimulationWorld) -> list[str]:
    return [line.split(" | ")[1] for line in world.event_log]


def _object_spot(world: SimulationWorld, kind: str) -> tuple[int, int]:
    for y in range(1, world.tile_map.height - 2):
        for x in range(1, world.tile_map.width - 2):
            if world.urbanism.object_error(world, kind, (x, y)) is None:
                return (x, y)
    raise AssertionError(f"nowhere on the map to put {kind}")


def _building_spot(world: SimulationWorld, blueprint_id: str) -> tuple[int, int]:
    definition = world.registries.buildings[blueprint_id]
    for y in range(1, world.tile_map.height - definition.height):
        for x in range(1, world.tile_map.width - definition.width):
            if world.urbanism.building_error(world, definition.width, definition.height, (x, y)) is None:
                return (x, y)
    raise AssertionError(f"nowhere on the map to put {blueprint_id}")


def _unwilling(world: SimulationWorld, resident_id: str) -> None:
    """Someone in no mood to do anything for anybody."""
    resident = world.residents[resident_id]
    resident.personality = Personality(empathy=0, greed=100, aggression=100, impulsiveness=100)
    resident.mood = 0.0
    resident.needs.stress = 100.0


def _registries_with(file_name: str, change) -> BuiltInRegistries:
    """Registries loaded from a copy of the data folder with one file's contents changed."""
    with tempfile.TemporaryDirectory() as folder:
        root = Path(folder)
        for path in DATA_DIR.rglob("*.json"):
            target = root / path.relative_to(DATA_DIR)
            target.parent.mkdir(parents=True, exist_ok=True)
            data = json.loads(path.read_text(encoding="utf-8"))
            if path.name == file_name:
                change(data)
            target.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        return BuiltInRegistries.load(root)


class WhatIsBuiltTests(unittest.TestCase):
    def setUp(self) -> None:
        self.world = _settled()

    def test_what_takes_building_is_not_put_down_at_once_and_what_takes_nothing_is(self) -> None:
        refused = self.world.apply_command(PlaceObjectCommand("bed", _object_spot(self.world, "bed")))
        self.assertFalse(refused.ok)
        self.assertEqual(refused.message, NEEDS_BUILDING)
        self.assertFalse(self.world.apply_command(PlaceBuildingCommand("shack", _building_spot(self.world, "shack"))).ok)
        self.assertEqual(self.world.sites, {})

        junk = self.world.apply_command(PlaceObjectCommand("junk", _object_spot(self.world, "junk")))
        self.assertTrue(junk.ok)
        self.assertIn(junk.entity_id, self.world.interactables)

    def test_proposing_what_takes_nothing_puts_it_down_with_nobody_asked(self) -> None:
        placed = self.world.apply_command(ProposeObjectCommand("junk", _object_spot(self.world, "junk"), "nobody"))
        self.assertTrue(placed.ok)
        self.assertIn(placed.entity_id, self.world.interactables)
        self.assertNotIn("crisis_resolved", _types(self.world))

    def test_a_settlement_in_its_opening_puts_down_for_nothing_and_builds_once_it_is_over(self) -> None:
        world = SimulationWorld.new_settlement()
        self.assertTrue(world.tutorial.active)
        self.assertTrue(world.apply_command(PlaceBuildingCommand("shack", _building_spot(world, "shack"))).ok)
        self.assertTrue(world.apply_command(PlaceObjectCommand("bed", _object_spot(world, "bed"))).ok)
        self.assertEqual(world.sites, {})

        world.tutorial.step_id = None
        self.assertFalse(world.apply_command(PlaceObjectCommand("bed", _object_spot(world, "bed"))).ok)

    def test_what_a_thing_takes_is_data_and_bad_data_is_refused(self) -> None:
        bed = self.world.registries.interactables.get("bed").build
        self.assertEqual(bed, BuildRule(cost={"scrap": 2}, minutes=60))
        self.assertEqual(self.world.registries.interactables.get("generator").build.job, "mechanic")
        self.assertIsNone(self.world.registries.interactables.get("junk").build)
        self.assertIsNone(build_rule_from_data("x", None))
        self.assertTrue(BuildRule().free)
        for bad in ({"cost": {"scrap": 0}}, {"cost": {"scrap": 1.5}}, {"minutes": -1}, {"job": 3}, []):
            with self.assertRaises(ValueError):
                build_rule_from_data("x", bad)

    def test_a_thing_built_by_an_unknown_job_or_with_what_no_item_is_makes_no_registry(self) -> None:
        def unknown_job(data: dict) -> None:
            data["bed"]["build"]["job"] = "wizard"

        def unknown_material(data: dict) -> None:
            data["shack"]["build"]["cost"] = {"unobtainium": 2}

        with self.assertRaises(ValueError):
            _registries_with("interactables.json", unknown_job)
        with self.assertRaises(ValueError):
            _registries_with("urbanism.json", unknown_material)


class ProposalTests(unittest.TestCase):
    def setUp(self) -> None:
        self.world = _settled()
        self.spot = _object_spot(self.world, "bed")

    def test_someone_who_agrees_has_the_ground_marked_out_in_their_charge(self) -> None:
        result = self.world.apply_command(ProposeObjectCommand("bed", self.spot, "marta"))
        self.assertTrue(result.ok)
        site = self.world.sites[result.entity_id]
        self.assertEqual((site.kind, site.what, site.in_charge), (OBJECT_SITE, "bed", "marta"))
        self.assertEqual(set(site.tiles), {self.spot, (self.spot[0], self.spot[1] + 1)})
        self.assertNotIn(result.entity_id, self.world.interactables)
        self.assertIn("site_laid", _types(self.world))
        # They said so, and what they were told is on record with it.
        self.assertIn("Marta se hace cargo de una obra: una cama (consejo: Hace falta)", self.world.event_log[-2])

    def test_someone_who_refuses_leaves_nothing_marked_out_and_is_not_asked_again_for_a_while(self) -> None:
        _unwilling(self.world, "raul")
        refused = self.world.apply_command(ProposeObjectCommand("bed", self.spot, "raul"))
        self.assertFalse(refused.ok)
        self.assertIn("Raúl", refused.message)
        self.assertEqual(self.world.sites, {})
        self.assertEqual(_scrap(self.world), 8)

        again = self.world.apply_command(ProposeObjectCommand("bed", self.spot, "raul"))
        self.assertFalse(again.ok)
        self.assertIn("más tarde", again.message)
        # It is Raúl who has said no. Anybody else can still be asked.
        self.assertTrue(self.world.apply_command(ProposeObjectCommand("bed", self.spot, "marta")).ok)

        cooldown = self.world.registries.decisions["build_proposal"].cooldown_minutes
        self.world.clock.advance_minutes(cooldown)
        self.world.residents["raul"].mood = 100.0
        self.world.residents["raul"].needs.stress = 0.0
        self.world.residents["raul"].personality = Personality(empathy=100)
        self.assertTrue(self.world.apply_command(ProposeObjectCommand("stool", _object_spot(self.world, "stool"), "raul")).ok)

    def test_whoever_says_yes_can_be_asked_again_at_once_until_they_have_enough_on_their_hands(self) -> None:
        answers = []
        for _ in range(6):
            answers.append(
                self.world.apply_command(ProposeObjectCommand("stool", _object_spot(self.world, "stool"), "marta")).ok
            )
        self.assertTrue(answers[0] and answers[1], "the first things asked of someone willing are taken on")
        self.assertIn(False, answers, "nobody takes on one thing after another without end")
        self.assertEqual(len(self.world.sites), answers.index(False))

    def test_advice_counts_and_does_not_settle_it(self) -> None:
        # Left to herself Nuria, who looks to her own, would rather not. Told it is needed, she does it.
        nuria = self.world.residents["nuria"]
        nuria.personality = Personality(empathy=40, greed=70)
        left_alone = self.world.apply_command(ProposeObjectCommand("bed", self.spot, "nuria", "neutral"))
        self.assertFalse(left_alone.ok)
        self.world.crisis_cooldowns.clear()
        self.assertTrue(self.world.apply_command(ProposeObjectCommand("bed", self.spot, "nuria", "encourage")).ok)

    def test_nobody_is_asked_who_is_away_hurt_or_making_up_their_mind_or_about_what_cannot_stand_there(self) -> None:
        taken = (self.world.interactables["bar"].x, self.world.interactables["bar"].y)
        self.assertFalse(self.world.apply_command(ProposeObjectCommand("bed", taken, "marta")).ok)
        self.assertFalse(self.world.apply_command(ProposeObjectCommand("bed", self.spot, "nobody")).ok)
        self.assertFalse(self.world.apply_command(ProposeObjectCommand("unknown_thing", self.spot, "marta")).ok)
        self.assertFalse(self.world.apply_command(ProposeBuildingCommand("unknown_thing", self.spot, "marta")).ok)

        self.world.health.hurt(self.world, self.world.residents["marta"], 70, "bruise", "una caída")
        self.assertIn("no está para obras", self.world.apply_command(ProposeObjectCommand("bed", self.spot, "marta")).message)
        self.world.residents["sergio"].expedition = object()
        self.assertIn("fuera", self.world.apply_command(ProposeObjectCommand("bed", self.spot, "sergio")).message)
        self.world.residents["sergio"].expedition = None
        self.world.residents["raul"].needs.stress = 60
        self.world.relationship("raul", "marta").resentment = 80
        self.world.step(1)
        self.assertIsNotNone(self.world.interventions.pending_for(self.world, "raul"))
        self.assertIn("cabeza", self.world.apply_command(ProposeObjectCommand("bed", self.spot, "raul")).message)
        self.assertEqual(self.world.sites, {})

    def test_what_asks_for_a_job_is_only_put_to_whoever_holds_it(self) -> None:
        spot = _object_spot(self.world, "generator")
        refused = self.world.apply_command(ProposeObjectCommand("generator", spot, "marta"))
        self.assertFalse(refused.ok)
        self.assertIn("Taller", refused.message)
        self.assertTrue(self.world.apply_command(ProposeObjectCommand("generator", spot, "paco")).ok)

    def test_a_site_keeps_its_ground_and_shuts_it_off_if_what_goes_there_will(self) -> None:
        site_id = self.world.apply_command(ProposeObjectCommand("bed", self.spot, "marta")).entity_id
        self.assertEqual(self.world.urbanism.object_error(self.world, "junk", self.spot), SITE_IN_THE_WAY)
        self.assertFalse(self.world.apply_command(ProposeObjectCommand("crate", self.spot, "vera")).ok)
        crate = next(object_id for object_id, placed in self.world.interactables.items() if placed.kind == "crate")
        self.world.containers[crate].items.clear()
        self.assertEqual(self.world.apply_command(MoveObjectCommand(crate, self.spot)).message, SITE_IN_THE_WAY)
        self.assertFalse(self.world.passable()(self.spot))

        self.assertTrue(self.world.apply_command(CancelSiteCommand(site_id)).ok)
        self.assertTrue(self.world.passable()(self.spot))
        self.assertIsNone(self.world.urbanism.object_error(self.world, "junk", self.spot))

        # Something that will not be in anybody's way is not in it while it is being made either.
        stool_at = _object_spot(self.world, "stool")
        self.assertTrue(self.world.apply_command(ProposeObjectCommand("stool", stool_at, "marta")).ok)
        self.assertTrue(self.world.passable()(stool_at))


class BuildingTests(unittest.TestCase):
    def test_what_was_agreed_is_carried_to_and_worked_on_until_it_stands(self) -> None:
        world = _settled()
        spot = _object_spot(world, "bed")
        beds = sum(1 for placed in world.interactables.values() if placed.kind == "bed")
        site_id = world.apply_command(ProposeObjectCommand("bed", spot, "marta")).entity_id

        self.assertTrue(_run(world, 2 * MINUTES_PER_DAY, lambda: site_id not in world.sites), "the bed never stood")
        built = [placed for placed in world.interactables.values() if placed.kind == "bed" and (placed.x, placed.y) == spot]
        self.assertEqual(len(built), 1)
        self.assertEqual(sum(1 for placed in world.interactables.values() if placed.kind == "bed"), beds + 1)
        self.assertIn("site_finished", _types(world))
        self.assertIn("build_started", _types(world))
        # What it took came out of the piles, and nobody is left holding any.
        _run(world, 120)
        self.assertEqual(_scrap(world) + _in_hand(world), 8 - 2)
        self.assertEqual(_in_hand(world), 0)
        self.assertTrue(any("Saqué adelante una obra" in memory.text for memory in world.memories.of("marta")))

    def test_a_building_goes_up_the_same_way_and_can_be_walked_into(self) -> None:
        for seed in (7, 11, 23):
            with self.subTest(seed=seed):
                world = _settled(seed)
                world.stock(world.containers["scrap_yard"], "scrap", 4, None)
                spot = _building_spot(world, "shack")
                result = world.apply_command(ProposeBuildingCommand("shack", spot, "vera"))
                self.assertTrue(result.ok)
                self.assertEqual(world.sites[result.entity_id].kind, BUILDING_SITE)
                self.assertFalse(world.passable()(spot))
                self.assertEqual(world.tile_map.terrain_at(spot), "dirt")

                done = _run(world, 2 * MINUTES_PER_DAY, lambda: result.entity_id not in world.sites)
                self.assertTrue(done, "the shack never stood")
                room = next(room for room in world.rooms.values() if room.blueprint_id == "shack")
                self.assertEqual((room.x, room.y), spot)
                self.assertEqual(world.tile_map.terrain_at(spot), "floor_wood")
                self.assertTrue(world.passable()(spot))
                self.assertEqual(_scrap(world) + _in_hand(world), 12 - 6)

    def test_whoever_agreed_builds_in_place_of_their_shift_and_a_helper_never_does(self) -> None:
        world = _settled()
        _only(world, "raul", "ines")
        site_id = world.apply_command(ProposeObjectCommand("bed", _object_spot(world, "bed"), "raul")).entity_id
        raul, ines = world.residents["raul"], world.residents["ines"]
        raul.day_off = ines.day_off = None
        # Raúl works the garden from eight to one. With a bed in his charge he is at that
        # instead, and it stands long before midday. Inés, who has none, keeps to the garden.
        self.assertTrue(_run(world, 4 * 60, lambda: site_id not in world.sites), "it was not built in the morning")
        self.assertFalse(any("| work_started | Raúl" in line for line in world.event_log))
        self.assertTrue(any("| work_started | Inés" in line for line in world.event_log))
        self.assertFalse(any("| build_started | Inés" in line for line in world.event_log))

    def test_nobody_builds_in_the_dark_or_with_a_need_that_presses(self) -> None:
        world = _settled()
        _only(world, "lucia", "paco")
        site_id = world.apply_command(ProposeObjectCommand("stool", _object_spot(world, "stool"), "lucia")).entity_id
        lucia, paco = world.residents["lucia"], world.residents["paco"]
        self.assertIsNotNone(world.construction.candidate(world, lucia, busy=False))
        self.assertIsNotNone(world.construction.candidate(world, lucia, busy=True), "it is her work now")
        self.assertIsNotNone(world.construction.candidate(world, paco, busy=False))
        self.assertIsNone(world.construction.candidate(world, paco, busy=True), "and for him something for spare time")
        lucia.needs.hunger = 90
        self.assertIsNone(world.construction.candidate(world, lucia, busy=False))
        lucia.needs.hunger = 0
        _set_time(world, 2)
        self.assertTrue(world.is_dark())
        self.assertIsNone(world.construction.candidate(world, lucia, busy=False))
        self.assertIn(site_id, world.sites)

    def test_others_lend_a_hand_unless_they_have_it_in_for_whoever_is_in_charge(self) -> None:
        world = _settled()
        world.apply_command(ProposeObjectCommand("bed", _object_spot(world, "bed"), "marta"))
        _set_time(world, 14)
        vera, raul = world.residents["vera"], world.residents["raul"]
        self.assertIsNotNone(world.construction.candidate(world, vera, busy=False))
        mine = world.construction.candidate(world, world.residents["marta"], busy=False)
        self.assertGreater(mine.score, world.construction.candidate(world, vera, busy=False).score)
        world.relationship("raul", "marta").resentment = 50
        self.assertIsNone(world.construction.candidate(world, raul, busy=False))

    def test_only_so_many_work_on_one_thing_at_a_time(self) -> None:
        world = _settled()
        world.stock(world.containers["scrap_yard"], "scrap", 4, None)
        site_id = world.apply_command(ProposeBuildingCommand("house", _building_spot(world, "house"), "vera")).entity_id
        most = 0
        for _ in range(MINUTES_PER_DAY):
            world.step(1)
            _keep_content(world)
            if site_id not in world.sites:
                break
            most = max(
                most,
                sum(
                    1
                    for resident in world.residents.values()
                    if resident.activity is not None
                    and resident.activity.action == BUILD_ACTION
                    and resident.activity.using
                ),
            )
        self.assertGreater(most, 1)
        self.assertLessEqual(most, world.registries.construction.hands[BUILDING_SITE])

    def test_what_asks_for_a_job_is_carried_to_by_anyone_and_worked_on_only_by_whoever_holds_it(self) -> None:
        world = _settled()
        world.stock(world.containers["scrap_yard"], "scrap", 4, None)
        site_id = world.apply_command(ProposeObjectCommand("generator", _object_spot(world, "generator"), "paco")).entity_id
        self.assertTrue(_run(world, 3 * MINUTES_PER_DAY, lambda: site_id not in world.sites), "it never stood")
        builders = {line.split(" | ")[2].split(" se pone")[0] for line in world.event_log if "| build_started |" in line}
        self.assertEqual(builders, {"Paco"})

    def test_what_costs_nothing_but_work_needs_nothing_carried(self) -> None:
        world = _settled()
        before = _scrap(world)
        spot = _object_spot(world, "crop_bed")
        site_id = world.apply_command(ProposeObjectCommand("crop_bed", spot, "ines")).entity_id
        self.assertTrue(_run(world, MINUTES_PER_DAY, lambda: site_id not in world.sites))
        self.assertEqual(_scrap(world) + _in_hand(world), before)
        self.assertNotIn("para una obra", "\n".join(world.event_log))

    def test_with_nothing_to_build_it_with_a_site_waits_and_says_so_once_a_day(self) -> None:
        world = _settled()
        for pile in SCRAP_PILES:
            world.containers[pile].items.clear()
        # With nobody going out for more, either.
        del world.residents["sergio"]
        site = world.construction.lay(world, OBJECT_SITE, "bed", _object_spot(world, "bed"), "marta")
        _run(world, 2 * MINUTES_PER_DAY)
        self.assertIn(site.site_id, world.sites)
        self.assertEqual(site.progress, 0.0)
        self.assertEqual(_types(world).count("site_waiting"), world.clock.day)
        self.assertTrue(any("chatarra" in line for line in world.event_log if "site_waiting" in line))

        # As soon as there is something to build it with, somebody does.
        world.stock(world.containers["scrap_yard"], "scrap", 2, None)
        self.assertTrue(_run(world, MINUTES_PER_DAY, lambda: site.site_id not in world.sites))

    def test_a_site_given_up_has_what_was_brought_to_it_put_away(self) -> None:
        world = _settled()
        site_id = world.apply_command(ProposeBuildingCommand("shack", _building_spot(world, "shack"), "vera")).entity_id
        site = world.sites[site_id]
        self.assertTrue(_run(world, MINUTES_PER_DAY, lambda: sum(site.delivered.values()) >= 4))
        everywhere = lambda: sum(inventory.count("scrap") for inventory in world.containers.values())  # noqa: E731

        self.assertTrue(world.apply_command(CancelSiteCommand(site_id)).ok)
        self.assertEqual(world.sites, {})
        self.assertFalse(world.apply_command(CancelSiteCommand(site_id)).ok)
        self.assertFalse(any(room.blueprint_id == "shack" for room in world.rooms.values()))
        # Whoever was on their way with more takes it back to where things are kept.
        _run(world, 180)
        self.assertEqual(_in_hand(world), 0)
        self.assertEqual(everywhere(), 8)
        self.assertFalse(any(r.activity is not None and r.activity.target_id == site_id for r in world.residents.values()))


class SavedSiteTests(unittest.TestCase):
    def test_a_site_half_built_is_saved_and_goes_on_from_where_it_was(self) -> None:
        world = _settled()
        world.stock(world.containers["scrap_yard"], "scrap", 4, None)
        site_id = world.apply_command(ProposeBuildingCommand("house", _building_spot(world, "house"), "vera")).entity_id
        site = world.sites[site_id]
        self.assertTrue(_run(world, MINUTES_PER_DAY, lambda: site.progress > 30))

        manager = SaveManager()
        data = json.loads(json.dumps(manager.to_data(world)))
        loaded = manager.from_data(data)
        again = loaded.sites[site_id]
        self.assertEqual(
            (again.kind, again.what, again.x, again.y, again.in_charge, again.delivered, again.progress),
            (site.kind, site.what, site.x, site.y, site.in_charge, site.delivered, site.progress),
        )
        self.assertEqual(set(again.tiles), set(site.tiles))
        self.assertTrue(again.blocks)
        self.assertEqual(loaded.site_count, world.site_count)
        self.assertEqual(manager.to_data(loaded)["sites"], data["sites"])
        # Whoever was at it when it was saved is still at it.
        at_it = [r.resident_id for r in world.residents.values() if r.activity and r.activity.target_id == site_id]
        self.assertTrue(at_it)
        for resident_id in at_it:
            self.assertEqual(loaded.residents[resident_id].activity.target_id, site_id)

        self.assertTrue(_run(loaded, 2 * MINUTES_PER_DAY, lambda: site_id not in loaded.sites))
        self.assertTrue(any(room.blueprint_id == "house" for room in loaded.rooms.values()))

    def test_a_save_from_before_has_nothing_being_built_and_one_for_something_gone_drops_it(self) -> None:
        manager = SaveManager()
        world = _settled()
        world.apply_command(ProposeObjectCommand("bed", _object_spot(world, "bed"), "marta"))
        data = json.loads(json.dumps(manager.to_data(world)))

        older = dict(data, version=23)
        del older["sites"], older["site_count"]
        self.assertEqual(manager.from_data(older).sites, {})

        data["sites"][0]["what"] = "something_gone"
        data["sites"].append("nonsense")
        self.assertEqual(manager.from_data(data).sites, {})


class LongRunTests(unittest.TestCase):
    def test_four_weeks_of_building_leave_everything_standing_and_everyone_alive(self) -> None:
        for seed in (7, 11, 23):
            with self.subTest(seed=seed):
                world = SimulationWorld.demo_world(seed=seed)
                people = len(world.residents)
                agreed = 0
                for week in range(4):
                    for kind in ("bed", "stool", "lamp"):
                        for resident_id in list(world.residents):
                            spot = _object_spot(world, kind)
                            if world.apply_command(ProposeObjectCommand(kind, spot, resident_id)).ok:
                                agreed += 1
                                break
                    world.step(7 * MINUTES_PER_DAY)
                self.assertGreaterEqual(agreed, 4, "hardly anybody would build anything")
                self.assertEqual(world.deaths, [])
                self.assertGreaterEqual(len(world.residents), people)
                finished = _types(world).count("site_finished")
                self.assertEqual(finished + len(world.sites), agreed)
                self.assertGreaterEqual(finished, 3, "what was agreed was hardly ever built")

    def test_the_same_seed_builds_the_same_way(self) -> None:
        def run() -> list[str]:
            world = SimulationWorld.demo_world(seed=5)
            world.apply_command(ProposeObjectCommand("bed", _object_spot(world, "bed"), "marta"))
            world.apply_command(ProposeBuildingCommand("shack", _building_spot(world, "shack"), "vera"))
            world.step(3 * MINUTES_PER_DAY)
            return world.event_log

        self.assertEqual(run(), run())


if __name__ == "__main__":
    unittest.main()
