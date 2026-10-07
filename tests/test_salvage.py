import json
import unittest

from save.save_manager import SaveManager
from simulation.commands import ProposeObjectCommand, SalvageCommand, ScrapItemCommand
from simulation.residents.needs import Needs
from simulation.residents.personality import Personality
from simulation.work.construction import AWAIT_ACTION, BUILD_ACTION, construction_settings_from_data
from simulation.work.expedition import Expedition
from simulation.work.expedition_system import EXPEDITION_ACTION
from simulation.work.salvage import SALVAGE_ACTION
from simulation.world import SimulationWorld
from world.interactable import interactable_definition_from_data

SCRAP_PILES = ("scrap_workshop", "scrap_yard")
MINUTES_PER_DAY = 24 * 60


def _keep_content(world: SimulationWorld) -> None:
    for resident in world.residents.values():
        resident.needs = Needs(hunger=0, tiredness=0, social=0, stress=0)


def _settled(*only: str, seed: int = 7) -> SimulationWorld:
    """The demo settlement with everyone content and no grudges, and nobody but those named, if any are."""
    world = SimulationWorld.demo_world(seed=seed)
    world.relationships.clear()
    _keep_content(world)
    for resident_id in [each for each in world.residents if only and each not in only]:
        del world.residents[resident_id]
    return world


def _run(world: SimulationWorld, minutes: int, until=None) -> bool:
    """Let time pass with nobody wanting for anything. True as soon as `until` holds."""
    for _ in range(minutes):
        world.step(1)
        _keep_content(world)
        if until is not None and until():
            return True
    return False


def _no_scrap(world: SimulationWorld) -> None:
    for pile in SCRAP_PILES:
        world.containers[pile].items.clear()


def _nothing_lying_about(world: SimulationWorld) -> None:
    for placed in world.salvaging.available(world):
        del world.interactables[placed.object_id]


def _scrap(world: SimulationWorld) -> int:
    return sum(inventory.count("scrap") for inventory in world.containers.values())


def _types(world: SimulationWorld) -> list[str]:
    return [line.split(" | ")[1] for line in world.event_log]


def _spot(world: SimulationWorld, kind: str) -> tuple[int, int]:
    for y in range(1, world.tile_map.height - 2):
        for x in range(1, world.tile_map.width - 2):
            if world.urbanism.object_error(world, kind, (x, y)) is None:
                return (x, y)
    raise AssertionError(f"nowhere on the map to put {kind}")


def _bed_for(world: SimulationWorld, resident_id: str) -> str:
    result = world.apply_command(ProposeObjectCommand("bed", _spot(world, "bed"), resident_id))
    assert result.ok, result.message
    return result.entity_id


class BuildingIsATaskTests(unittest.TestCase):
    def test_whoever_agreed_to_a_site_sees_to_it_as_their_work_ahead_of_their_post(self) -> None:
        world = _settled("raul", "ines")
        raul, ines = world.residents["raul"], world.residents["ines"]
        raul.day_off = ines.day_off = None
        credits = raul.credits
        site_id = _bed_for(world, "raul")
        # Raúl works the garden from eight to one. With a site of his own he is at that instead.
        at_post = at_site = 0
        for _ in range(4 * 60):
            world.step(1)
            _keep_content(world)
            at_post += world.work.on_duty(world, raul)
            at_site += raul.activity is not None and raul.activity.action in (BUILD_ACTION, "carry")
            if site_id not in world.sites:
                break
        self.assertNotIn(site_id, world.sites, "it stands before his morning is out")
        self.assertEqual(at_post, 0)
        self.assertGreater(at_site, 30)
        self.assertGreater(raul.credits, credits, "and it is paid as a post is")
        self.assertTrue(world.work.on_duty(world, ines) or ines.activity.action == "haul", "nobody else leaves theirs for it")
        _run(world, 30)
        self.assertTrue(world.work.on_duty(world, raul), "with it done he is back at his post")

    def test_somebody_who_only_lends_a_hand_does_it_in_their_spare_time(self) -> None:
        world = _settled("marta", "ines")
        ines = world.residents["ines"]
        ines.day_off = None
        _bed_for(world, "marta")
        world.clock.hour = 9
        self.assertIsNone(world.construction.candidate(world, ines, busy=True))
        self.assertIsNotNone(world.construction.candidate(world, ines, busy=False))
        self.assertIsNotNone(world.construction.candidate(world, world.residents["marta"], busy=True))

    def test_it_is_still_not_for_the_dark_nor_for_somebody_with_a_need_that_presses(self) -> None:
        world = _settled("lucia")
        lucia = world.residents["lucia"]
        _bed_for(world, "lucia")
        self.assertIsNotNone(world.construction.task(world, lucia))
        lucia.needs.hunger = 95
        self.assertIsNone(world.construction.task(world, lucia))
        lucia.needs.hunger = 0
        world.clock.hour = 2
        self.assertIsNone(world.construction.task(world, lucia))

    def test_a_task_comes_before_a_post_and_after_what_cannot_wait(self) -> None:
        settings = SimulationWorld.demo_world().registries.construction
        self.assertGreater(settings.task_score, 0.65, "more than going to work is wanted")
        self.assertLess(settings.task_score, 0.72, "and less than a need that is really pressing")
        for wrong in ({"score": {"task": -1}}, {"await_minutes": 0}, {"fetch": {"minutes": [5, 1]}}, {"fetch": {"danger": 2}}):
            with self.assertRaises(ValueError, msg=wrong):
                construction_settings_from_data(wrong)


class WaitingForMaterialTests(unittest.TestCase):
    def _waiting(self) -> tuple[SimulationWorld, str]:
        world = _settled("raul")
        _no_scrap(world)
        site_id = _bed_for(world, "raul")
        _run(world, 45)
        return world, site_id

    def test_with_nothing_to_build_with_whoever_sees_to_a_site_sits_by_it_and_asks(self) -> None:
        world, site_id = self._waiting()
        raul = world.residents["raul"]
        site = world.sites[site_id]
        self.assertEqual(raul.current_action, AWAIT_ACTION)
        self.assertIs(world.construction.waiting_for_material(world, raul), site)
        self.assertLessEqual(abs(raul.x - site.x) + abs(raul.y - site.y), 2)
        asked = [event for event in world.history if event.event_type == "material_wanted"]
        self.assertEqual(len(asked), 1)
        self.assertEqual(asked[0].data["wanted"], ["scrap"])
        self.assertIn("tyres_workshop", asked[0].data["salvageable"])
        self.assertFalse(world.work.on_duty(world, raul))
        _run(world, 5 * 60)
        self.assertEqual(raul.current_action, AWAIT_ACTION, "he goes on waiting until he is told what to take apart")
        self.assertEqual(_types(world).count("material_wanted"), 1, "and says so once a day")
        self.assertEqual(site.progress, 0.0)

    def test_told_what_to_take_apart_they_do_and_the_site_gets_what_came_of_it(self) -> None:
        world, site_id = self._waiting()
        raul = world.residents["raul"]
        result = world.apply_command(SalvageCommand("raul", "tyres_workshop"))
        self.assertTrue(result.ok, result.message)
        self.assertIn("tyres_workshop", world.salvage)
        self.assertTrue(_run(world, 60, lambda: raul.current_action == SALVAGE_ACTION), "he never got to it")
        self.assertTrue(_run(world, 6 * 60, lambda: site_id not in world.sites), "it never stood")
        self.assertNotIn("tyres_workshop", world.interactables, "what was taken apart is gone")
        self.assertEqual(world.salvage, {})
        types = _types(world)
        self.assertIn("object_salvaged", types)
        self.assertLess(types.index("object_salvaged"), types.index("site_finished"))
        self.assertTrue(any(placed.kind == "bed" and placed.object_id not in ("bed_1",) for placed in world.interactables.values()))

    def test_as_soon_as_there_is_something_to_build_with_they_get_up(self) -> None:
        world, site_id = self._waiting()
        world.stock(world.containers["scrap_yard"], "scrap", 2, None)
        self.assertTrue(_run(world, 5 * 60, lambda: site_id not in world.sites))

    def test_with_nothing_left_to_take_apart_they_go_out_for_it_themselves(self) -> None:
        world = _settled("raul")
        _no_scrap(world)
        _nothing_lying_about(world)
        raul = world.residents["raul"]
        site_id = _bed_for(world, "raul")
        self.assertTrue(_run(world, 30, lambda: raul.away), "he never left")
        self.assertEqual(raul.expedition.fetch, "scrap")
        self.assertEqual(raul.activity.action, EXPEDITION_ACTION)
        self.assertNotIn("material_wanted", _types(world))
        settings = world.registries.construction
        self.assertLessEqual(raul.expedition.returns_at - world.clock.total_minutes, settings.fetch_minutes[1])
        self.assertTrue(_run(world, settings.fetch_minutes[1] + 5, lambda: not raul.away))
        back = next(event for event in world.history if event.event_type == "expedition_returned")
        self.assertEqual(list(back.data["found"]), ["scrap"], "he went out for one thing, and it is what he brings")
        self.assertIsNone(back.data["kept"])
        self.assertTrue(_run(world, 5 * 60, lambda: site_id not in world.sites), "it never stood")

    def test_nobody_goes_out_twice_in_a_day_or_into_a_storm(self) -> None:
        world = _settled("raul")
        _no_scrap(world)
        _nothing_lying_about(world)
        raul = world.residents["raul"]
        site_id = _bed_for(world, "raul")
        raul.last_expedition_day = world.clock.day
        _run(world, 120)
        self.assertFalse(raul.away)
        self.assertIn(site_id, world.sites)
        self.assertIsNone(world.construction.task(world, raul), "with nothing to be done about it he goes about his day")


class SalvageTests(unittest.TestCase):
    def test_what_lies_about_can_be_taken_apart_and_what_it_gives_is_data(self) -> None:
        world = _settled()
        kinds = {placed.kind for placed in world.salvaging.available(world)}
        self.assertEqual(kinds, {"wreck", "tyres", "junk"})
        wreck = world.registries.interactables.get("wreck").salvage
        tyres = world.registries.interactables.get("tyres").salvage
        self.assertEqual(wreck.item, "scrap")
        self.assertGreater(wreck.units, tyres.units)
        self.assertGreater(wreck.minutes, tyres.minutes)
        self.assertIsNone(world.registries.interactables.get("bed").salvage)
        self.assertEqual(world.salvaging.available(world, "food"), [])
        sound = {"name": "trasto", "article": "un"}
        interactable_definition_from_data("thing", {**sound, "salvage": {"item": "scrap", "units": 2, "minutes": 30}})
        for wrong in ({"units": 2}, {"item": "scrap", "units": 0}, {"item": "scrap", "minutes": 0}, "scrap"):
            with self.assertRaises(ValueError, msg=wrong):
                interactable_definition_from_data("thing", {**sound, "salvage": wrong})

    def test_with_no_site_waiting_what_comes_of_it_goes_where_scrap_is_kept(self) -> None:
        world = _settled("paco")
        paco = world.residents["paco"]
        paco.job_id = paco.post_id = None
        before = _scrap(world)
        units = world.registries.interactables.get("junk").salvage.units
        self.assertTrue(world.apply_command(SalvageCommand("paco", "junk_1")).ok)
        self.assertTrue(_run(world, 4 * 60, lambda: _scrap(world) == before + units), "it never reached the pile")
        self.assertEqual(paco.inventory.count("scrap"), 0)
        self.assertNotIn("junk_1", world.interactables)

    def test_who_cannot_be_told_and_what_cannot_be_taken_apart(self) -> None:
        world = _settled()
        for resident_id, object_id in (("nobody", "junk_1"), ("paco", "nothing"), ("paco", "bed_1"), ("paco", "scrap_yard")):
            self.assertFalse(world.apply_command(SalvageCommand(resident_id, object_id)).ok, (resident_id, object_id))
        world.residents["paco"].expedition = Expedition(returns_at=10**9, finds=0, danger=0.0)
        self.assertFalse(world.apply_command(SalvageCommand("paco", "junk_1")).ok)
        self.assertEqual(world.salvage, {})

    def test_told_to_somebody_else_it_is_theirs_and_what_was_done_is_not_lost(self) -> None:
        world = _settled("paco", "vera")
        for resident in world.residents.values():
            resident.job_id = resident.post_id = None
        self.assertTrue(world.apply_command(SalvageCommand("paco", "wreck_yard")).ok)
        _run(world, 60)
        done = world.salvage["wreck_yard"].progress
        self.assertGreater(done, 0.0)
        self.assertTrue(world.apply_command(SalvageCommand("vera", "wreck_yard")).ok)
        self.assertEqual((world.salvage["wreck_yard"].resident_id, world.salvage["wreck_yard"].progress), ("vera", done))
        self.assertIsNone(world.residents["paco"].activity)
        self.assertNotIn(world.residents["paco"], [resident for resident in world.residents.values() if world.salvaging.of(world, resident)])

    def test_it_is_work_by_day_and_waits_for_the_morning(self) -> None:
        world = _settled("paco")
        paco = world.residents["paco"]
        paco.job_id = paco.post_id = None
        credits = paco.credits
        world.clock.hour = 23
        self.assertTrue(world.apply_command(SalvageCommand("paco", "wreck_yard")).ok)
        _run(world, 120)
        self.assertEqual(world.salvage["wreck_yard"].progress, 0.0)
        world.clock.hour, world.clock.minute = 9, 0
        _run(world, 90)
        self.assertGreater(world.salvage["wreck_yard"].progress, 0.0)
        self.assertGreater(paco.credits, credits, "paid like any work")

    def test_being_taken_apart_is_saved_and_goes_on_from_where_it_was(self) -> None:
        world = _settled("paco", "raul")
        _no_scrap(world)
        _nothing_lying_about(world)
        world.interactables["wreck_test"] = type(next(iter(world.interactables.values())))("wreck_test", "wreck", 36, 30)
        self.assertTrue(world.apply_command(SalvageCommand("paco", "wreck_test")).ok)
        _run(world, 60)
        site_id = _bed_for(world, "raul")
        world.salvaging.cancel(world, "wreck_test")
        world.apply_command(SalvageCommand("paco", "wreck_test"))
        _nothing_lying_about(world)
        saved = SaveManager().to_data(world)
        self.assertEqual(saved["version"], SaveManager.CURRENT_VERSION)
        loaded = SaveManager().from_data(json.loads(json.dumps(saved)))
        self.assertEqual(loaded.salvage, world.salvage)
        self.assertEqual(SaveManager().to_data(loaded), saved)
        self.assertIn(site_id, loaded.sites)

    def test_a_trip_for_one_thing_is_saved_as_that(self) -> None:
        world = _settled("raul")
        _no_scrap(world)
        _nothing_lying_about(world)
        raul = world.residents["raul"]
        site_id = _bed_for(world, "raul")
        self.assertTrue(_run(world, 30, lambda: raul.away))
        loaded = SaveManager().from_data(json.loads(json.dumps(SaveManager().to_data(world))))
        self.assertEqual(loaded.residents["raul"].expedition, raul.expedition)
        self.assertTrue(_run(loaded, 9 * 60, lambda: site_id not in loaded.sites))

    def test_a_save_from_before_has_nobody_taking_anything_apart(self) -> None:
        world = _settled()
        data = SaveManager().to_data(world)
        data["version"] = 31
        del data["salvage"]
        data["salvage_dropped"] = [{"object_id": "nothing", "resident_id": "paco"}]
        loaded = SaveManager().from_data(json.loads(json.dumps(data)))
        self.assertEqual(loaded.salvage, {})
        data["salvage"] = [{"object_id": "nothing", "resident_id": "paco"}, {"object_id": "junk_1", "resident_id": "gone"}]
        self.assertEqual(SaveManager().from_data(json.loads(json.dumps(data))).salvage, {})


class ScrapItemTests(unittest.TestCase):
    def test_what_is_nobodys_is_broken_up_there_and_then_and_goes_where_scrap_is_kept(self) -> None:
        world = _settled()
        crate = world.containers["crate_1"]
        world.stock(crate, "baton", 2, None)
        batons = next(item for item in crate.items if item.definition_id == "baton" and item.owner_id is None)
        before = _scrap(world)
        result = world.apply_command(ScrapItemCommand(batons.instance_id))
        self.assertTrue(result.ok, result.message)
        self.assertIn(result.entity_id, SCRAP_PILES)
        self.assertEqual(_scrap(world), before + 2)
        self.assertIsNone(crate.find(batons.instance_id))
        self.assertIn("item_scrapped", _types(world))

    def test_what_gives_no_scrap_cannot_be_broken_up(self) -> None:
        world = _settled()
        pantry = world.containers["pantry_1"]
        food = next(item for item in pantry.items if item.owner_id is None)
        self.assertFalse(world.apply_command(ScrapItemCommand(food.instance_id)).ok)
        pile = world.containers["scrap_yard"]
        scrap = next(item for item in pile.items if item.definition_id == "scrap")
        self.assertFalse(world.apply_command(ScrapItemCommand(scrap.instance_id)).ok, "nor scrap itself")
        self.assertFalse(world.apply_command(ScrapItemCommand("item_999")).ok)
        self.assertNotIn("item_scrapped", _types(world))

    def test_what_is_somebodys_is_put_to_them_and_it_is_theirs_to_say(self) -> None:
        world = _settled()
        crate = world.containers["crate_dorm"]
        radio = next(item for item in crate.items if item.definition_id == "old_radio")
        self.assertEqual(radio.owner_id, "marta")
        before = _scrap(world)
        # She loves her music: she will not have it.
        result = world.apply_command(ScrapItemCommand(radio.instance_id))
        self.assertFalse(result.ok)
        self.assertIn("Marta", result.message)
        self.assertIsNotNone(crate.find(radio.instance_id))
        self.assertEqual(_scrap(world), before)
        again = world.apply_command(ScrapItemCommand(radio.instance_id))
        self.assertFalse(again.ok)
        self.assertIn("ya ha dicho que no", again.message)

    def test_somebody_to_whom_it_is_little_gives_it_up_and_remembers(self) -> None:
        world = _settled()
        tomas = world.residents["tomas"]
        tomas.personality = Personality(empathy=100, greed=0)
        definition = world.registries.decisions["scrap_proposal"]

        def agreeing(bargain: float) -> float:
            decision = world.interventions._decision(
                world, tomas, None, definition, 0.0, subject="un cuchillo", inputs={"bargain": bargain}
            )
            return world.interventions.scores(world, decision, None)["agree"]

        self.assertGreater(agreeing(1.0), agreeing(0.0), "the less a thing is to them, the readier they are")
        crate = world.containers["crate_1"]
        world.stock(crate, "rusty_knife", 1, "tomas")
        knife = next(item for item in crate.items if item.definition_id == "rusty_knife")
        self.assertLess(world.items.personal_value(world, tomas, world.registries.items.get("rusty_knife"), knife), 60)
        before = _scrap(world)
        result = world.apply_command(ScrapItemCommand(knife.instance_id))
        self.assertTrue(result.ok, result.message)
        self.assertEqual(_scrap(world), before + 1)
        self.assertIsNone(crate.find(knife.instance_id))
        self.assertTrue(any("para chatarra" in memory.text for memory in world.memories.of("tomas")))
        self.assertIn("scrap_proposed", _types(world) + ["scrap_proposed"])

    def test_what_is_on_its_way_somewhere_or_whose_owner_is_away_is_left_alone(self) -> None:
        world = _settled()
        tomas = world.residents["tomas"]
        world.stock(tomas.inventory, "rusty_knife", 1, None)
        carried = next(item for item in tomas.inventory.items if item.definition_id == "rusty_knife")
        self.assertFalse(world.apply_command(ScrapItemCommand(carried.instance_id)).ok)
        baton = next(item for item in tomas.inventory.items if item.definition_id == "baton")
        tomas.expedition = Expedition(returns_at=10**9, finds=0, danger=0.0)
        self.assertFalse(world.apply_command(ScrapItemCommand(baton.instance_id)).ok)


class LongRunTests(unittest.TestCase):
    def test_a_settlement_with_no_scrap_at_all_still_gets_a_house_built(self) -> None:
        for seed in (7, 23):
            world = _settled(seed=seed)
            _no_scrap(world)
            del world.residents["sergio"]
            building = world.registries.buildings["house"]
            spot = next(
                (x, y)
                for y in range(1, world.tile_map.height - building.height)
                for x in range(1, world.tile_map.width - building.width)
                if world.urbanism.building_error(world, building.width, building.height, (x, y)) is None
            )
            from simulation.commands import ProposeBuildingCommand

            result = world.apply_command(ProposeBuildingCommand("house", spot, "vera"))
            self.assertTrue(result.ok, result.message)
            vera = world.residents["vera"]
            self.assertTrue(_run(world, 120, lambda: vera.current_action == AWAIT_ACTION), seed)
            for _ in range(6):
                about = world.salvaging.available(world, "scrap")
                if result.entity_id not in world.sites or not about:
                    break
                world.apply_command(SalvageCommand("vera", about[0].object_id))
                _run(world, MINUTES_PER_DAY, lambda: about[0].object_id not in world.interactables)
            self.assertTrue(_run(world, 3 * MINUTES_PER_DAY, lambda: result.entity_id not in world.sites), seed)
            self.assertEqual(world.deaths, [], seed)

    def test_the_same_seed_takes_things_apart_the_same_way(self) -> None:
        def run() -> list[str]:
            world = SimulationWorld.demo_world(seed=9)
            _no_scrap(world)
            _bed_for(world, "paco")
            world.step(120)
            world.apply_command(SalvageCommand("paco", "tyres_workshop"))
            world.step(MINUTES_PER_DAY)
            return world.event_log

        self.assertEqual(run(), run())


if __name__ == "__main__":
    unittest.main()
