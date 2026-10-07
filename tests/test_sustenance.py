import json
import unittest
from dataclasses import replace

from save.save_manager import SaveManager
from simulation.events.world_event import Upcoming
from simulation.health.injury import Injury
from simulation.residents.activity import Activity
from simulation.residents.needs import Needs
from simulation.residents.resident import Resident
from simulation.social.social_system import argument_chance
from simulation.work import hauling
from simulation.work.work_system import HAUL_ACTION, WORK_ACTION
from simulation.world import POWER_ITEM, SimulationWorld


def _settled(seed: int = 7) -> SimulationWorld:
    world = SimulationWorld.demo_world(seed=seed)
    world.relationships.clear()
    for resident in world.residents.values():
        resident.needs = Needs(hunger=0, thirst=0, tiredness=0, social=0, stress=0)
    return world


def _on_duty(world: SimulationWorld, resident_id: str, minutes: int = 120):
    resident = world.residents[resident_id]
    post = world.interactables[resident.post_id]
    resident.x, resident.y = post.x, post.y - 1
    resident.activity = Activity(WORK_ACTION, resident.post_id, minutes_left=minutes, using=True)
    resident.current_action = WORK_ACTION
    return resident


class WaterTests(unittest.TestCase):
    def test_thirst_grows_and_water_from_the_tank_slakes_it(self) -> None:
        world = _settled()
        raul = world.residents["raul"]
        tank = world.containers["water_tank"]
        before = tank.count("water")
        raul.needs.thirst = 90
        raul.x, raul.y = 53, 15

        activity = world.activities.routine.plan(world, raul)
        self.assertEqual((activity.action, activity.target_id), ("drink_water", "water_tank"))
        raul.activity = activity
        for _ in range(30):
            world.step(1)
            if raul.activity is None:
                break

        self.assertLess(raul.needs.thirst, 50)
        self.assertEqual(tank.count("water"), before - 1)

    def test_no_water_is_reported_separately_from_no_food(self) -> None:
        world = _settled()
        for object_id, inventory in world.containers.items():
            if world.interactables[object_id].kind == "water_tank":
                inventory.items.clear()
        raul = world.residents["raul"]
        self.assertIsNone(world.items.take_food(world, raul, "water_tank", "water"))
        event_types = [line.split(" | ")[1] for line in world.event_log]
        self.assertIn("no_water", event_types)
        self.assertNotIn("no_food", event_types)


class WaterPostTests(unittest.TestCase):
    def test_drawing_water_is_a_post_that_fills_the_tank_while_someone_works_it(self) -> None:
        world = _settled()
        job = world.registries.jobs["water_carrier"]
        self.assertEqual((job.station, job.produces.item, job.produces.into), ("water_tank", "water", "station"))
        self.assertTrue(world.staffing.is_short(world, job), "nobody draws water when a settlement starts")
        lucia = world.residents["lucia"]
        self.assertTrue(world.staffing.assign(world, lucia, "water_carrier"))
        self.assertEqual(lucia.post_id, "water_tank")
        tank = world.containers["water_tank"]
        before = tank.count("water")
        world.clock.hour = 7
        for _ in range(6 * 60):
            world.step(1)
            lucia.needs = Needs(hunger=0, thirst=0, tiredness=0, social=0, stress=0)
        self.assertGreaterEqual(tank.count("water") - before, 8, "a morning at the tank is water for a day")

    def test_the_post_is_offered_round_and_whoever_matters_least_elsewhere_is_asked(self) -> None:
        world = _settled()
        asked = [resident.resident_id for resident in world.staffing.candidates(world, "water_carrier")]
        self.assertEqual(asked[0], "lucia", "the bar can wait; water cannot")
        self.assertNotIn("water_carrier", [resident.job_id for resident in world.residents.values()])

    def test_six_weeks_on_the_settlement_still_has_water_and_light(self) -> None:
        world = SimulationWorld.demo_world(seed=3)
        tank = world.containers["water_tank"]
        start = tank.count("water")
        worst = 0.0
        for _ in range(42 * 24 * 60):
            world.step(1)
            worst = max(worst, max(resident.needs.thirst for resident in world.residents.values() if not resident.away))
        self.assertIn("water_carrier", [resident.job_id for resident in world.residents.values()])
        self.assertGreaterEqual(tank.count("water"), start // 2)
        self.assertLess(worst, 85.0, "nobody went thirsty")
        self.assertTrue(world.has_power())
        self.assertEqual(world.deaths, [])
        kinds = [line.split(" | ")[1] for line in world.event_log]
        self.assertNotIn("no_water", kinds)
        self.assertNotIn("privation", kinds)


class ShortageTests(unittest.TestCase):
    def _dry(self) -> SimulationWorld:
        world = _settled()
        world.containers["water_tank"].items.clear()
        # Nobody draws any more either: the post is left out.
        jobs = {job_id: job for job_id, job in world.registries.jobs.items() if job_id != "water_carrier"}
        world.registries = replace(world.registries, jobs=jobs)
        return world

    def test_a_thirst_nothing_can_slake_keeps_nobody_from_bed_or_post(self) -> None:
        world = self._dry()
        raul = world.residents["raul"]
        raul.needs.thirst = 95
        self.assertFalse(world.activities.routine.can_relieve(world, raul, "thirst"))
        self.assertEqual(world.activities.urgent_needs(world, raul), [])
        self.assertEqual(world.activities.unanswerable(world, raul), ["thirst"])
        world.clock.hour = 9
        self.assertIsNotNone(world.work.candidate(world, raul), "he still goes to work")
        # With water to be had, the same thirst comes first.
        world.stock(world.containers["water_tank"], "water", 3, None)
        self.assertTrue(world.activities.routine.can_relieve(world, raul, "thirst"))
        self.assertEqual(world.activities.urgent_needs(world, raul), ["thirst"])
        self.assertIsNone(world.work.candidate(world, raul))

    def test_what_they_carry_counts_as_something_to_be_done_about_it(self) -> None:
        world = self._dry()
        raul = world.residents["raul"]
        raul.needs.thirst = 95
        world.stock(raul.inventory, "water", 1, "raul")
        self.assertTrue(world.activities.routine.can_relieve(world, raul, "thirst"))

    def test_a_dry_settlement_is_told_once_a_day_and_keeps_working_and_sleeping(self) -> None:
        world = self._dry()
        for resident in world.residents.values():
            resident.needs.thirst = 90
        worked = slept = 0
        first_day = world.clock.day
        for _ in range(2 * 24 * 60):
            world.step(1)
            for resident in world.residents.values():
                resident.needs.thirst = max(resident.needs.thirst, 90)
                worked += resident.current_action == "work"
                slept += resident.current_action == "sleep"
        kinds = [line.split(" | ")[1] for line in world.event_log]
        self.assertEqual(kinds.count("no_water"), world.clock.day - first_day + 1, "said once each day")
        self.assertGreater(worked, 9 * 4 * 60, "the posts are still worked")
        self.assertGreater(slept, 9 * 8 * 60, "and the nights still slept")

    def test_thirst_left_at_its_worst_sickens_and_in_the_end_kills(self) -> None:
        world = self._dry()
        raul = world.residents["raul"]
        raul.needs.thirst = 100
        world.step(60)
        self.assertEqual([injury.kind for injury in raul.injuries], ["dehydration"])
        started = [event for event in world.history if event.event_type == "privation"]
        self.assertEqual(len(started), 1)
        self.assertEqual(started[0].participants, ["raul"])
        self.assertEqual(started[0].data, {"kind": "dehydration", "need": "thirst"})
        self.assertIn("Raúl empieza a sufrir deshidratación", started[0].text)
        self.assertAlmostEqual(raul.health, 100 - 30 / 24, delta=0.1)
        # A drink in time, and it mends.
        raul.needs.thirst = 0
        hurt = raul.health
        world.step(6 * 60)
        self.assertGreater(world.residents["raul"].health, hurt)
        # Left to it, it is the end of him, some days later.
        days = 0
        while "raul" in world.residents and days < 10:
            for _ in range(24 * 60):
                world.step(1)
                if "raul" in world.residents:
                    raul.needs.thirst = 100
            days += 1
        self.assertNotIn("raul", world.residents)
        self.assertIn(days, (3, 4))
        self.assertEqual(world.deaths[-1].cause, "sufrir deshidratación")
        # Falling ill of it was news each time it began, not every minute it went on.
        began = [event for event in world.history if event.event_type == "privation" and event.data["kind"] == "dehydration"]
        self.assertEqual(sum(event.participants == ["raul"] for event in began), 2)

    def test_hunger_does_the_same_more_slowly_and_ordinary_hunger_does_nothing(self) -> None:
        world = _settled()
        raul, ines = world.residents["raul"], world.residents["ines"]
        raul.needs.hunger, ines.needs.hunger = 100, 95
        world.step(1)
        self.assertEqual([injury.kind for injury in raul.injuries], ["starvation"])
        self.assertEqual(ines.injuries, [])
        definitions = world.registries.injuries
        self.assertLess(definitions["starvation"].worsens_per_day, definitions["dehydration"].worsens_per_day)
        self.assertEqual((definitions["dehydration"].from_need, definitions["starvation"].from_need), ("thirst", "hunger"))


class PowerTests(unittest.TestCase):
    def test_powered_lamps_and_radio_depend_on_generator_fuel(self) -> None:
        world = _settled()
        world.clock.hour = 23
        self.assertTrue(world.has_power())
        self.assertTrue(world.is_lit((26, 34)), "the gate lamp has power")

        world.containers["generator"].items.clear()
        self.assertFalse(world.has_power())
        self.assertFalse(world.is_lit((26, 34)), "a lamp without the generator is dark")
        self.assertTrue(world.is_lit((19, 13)), "firelight still works")

        upcoming = Upcoming("raid", world.clock.total_minutes + 60)
        world.upcoming.append(upcoming)
        world.happenings.hear_radio(world, world.residents["tomas"])
        self.assertIsNone(upcoming.fact_id)
        world.stock(world.containers["generator"], POWER_ITEM, 1, None)
        world.happenings.hear_radio(world, world.residents["tomas"])
        self.assertIsNotNone(upcoming.fact_id)

    def test_a_lamp_with_the_power_out_lights_nothing_and_a_fire_still_does(self) -> None:
        world = _settled()
        lamp = next(placed for placed in world.interactables.values() if placed.kind == "lamp")
        fire = next(placed for placed in world.interactables.values() if placed.kind == "campfire")
        self.assertGreater(world.light_of(lamp), 0)
        world.containers["generator"].items.clear()
        self.assertEqual(world.light_of(lamp), 0)
        self.assertGreater(world.light_of(fire), 0)

    def test_the_generator_burns_one_fuel_when_night_starts(self) -> None:
        world = _settled()
        world.clock.hour, world.clock.minute = 21, 59
        before = world.power_units()
        world.step(1)
        self.assertEqual(world.power_units(), before - 1)


def _content(world: SimulationWorld) -> None:
    for resident in world.residents.values():
        resident.needs = Needs(hunger=0, thirst=0, tiredness=0, social=0, stress=0)


def _types(world: SimulationWorld) -> list[str]:
    return [line.split(" | ")[1] for line in world.event_log]


def _fuel_in_store(world: SimulationWorld) -> int:
    return sum(
        inventory.count(POWER_ITEM)
        for object_id, inventory in world.containers.items()
        if world.interactables[object_id].kind != "generator"
    )


class GeneratorSupplyTests(unittest.TestCase):
    def test_fuel_from_outside_is_left_in_store_where_someone_is_there_to_carry_it_on(self) -> None:
        world = _settled()
        sergio = world.residents["sergio"]
        world.stock(sergio.inventory, POWER_ITEM, 2, None)
        self.assertEqual(world.interactables[world.expeditions.errand(world, sergio)].kind, "crate")
        # A settlement with no workshop has nobody to carry it on: it goes straight in.
        del world.interactables["workbench"]
        self.assertEqual(world.interactables[world.expeditions.errand(world, sergio)].kind, "generator")

    def test_the_mechanic_carries_a_load_of_fuel_from_the_store_to_the_generator(self) -> None:
        world = _settled()
        paco = world.residents["paco"]
        self.assertEqual(world.registries.jobs["mechanic"].supplies.into, "generator")
        world.stock(world.containers["crate_workshop"], POWER_ITEM, 6, None)
        before = world.power_units()
        world.clock.hour = 10
        for _ in range(180):
            world.step(1)
            _content(world)
            # Nothing reaches the generator except out of his hands.
            self.assertEqual(world.power_units() + _fuel_in_store(world) + hauling.carried(paco, POWER_ITEM), before + 6)
            if world.power_units() == before + 6:
                break
        self.assertEqual(world.power_units(), before + 6)
        hauls = [line for line in world.event_log if "goods_hauled" in line and "Paco" in line]
        self.assertIn("Paco coge 6 de combustible de una caja", hauls[0])
        self.assertIn("Paco lleva 6 de combustible a un generador", hauls[1])

    def test_he_waits_for_a_full_load_unless_the_generator_is_running_low(self) -> None:
        world = _settled()
        paco = world.residents["paco"]
        rule = world.registries.jobs["mechanic"].supplies
        world.stock(world.containers["crate_workshop"], POWER_ITEM, 2, None)
        self.assertIsNone(hauling.supply_errand(world, paco, rule, 120), "two units can wait")
        generator = world.containers["generator"]
        generator.take_units(generator.stack_of(POWER_ITEM, None).instance_id, generator.count(POWER_ITEM) - 3)
        self.assertEqual(hauling.supply_errand(world, paco, rule, 120), "crate_workshop")
        self.assertIsNone(hauling.supply_errand(world, paco, rule, 10), "not with the shift all but over")
        # What is already in his hands is taken where it goes, shift or no shift.
        world.stock(paco.inventory, POWER_ITEM, 1, None)
        self.assertEqual(hauling.supply_errand(world, paco, rule, 0), "generator")

    def test_he_does_not_leave_the_bench_while_someone_is_being_served(self) -> None:
        world = _settled()
        world.clock.hour = 10
        paco = _on_duty(world, "paco")
        world.stock(world.containers["crate_workshop"], POWER_ITEM, 6, None)
        customer = world.residents["nuria"]
        customer.activity = Activity("repair", "workbench", minutes_left=30, using=True)
        world.work.tick(world, paco, paco.activity)
        self.assertIsNotNone(paco.activity, "the repair comes first")
        customer.activity = None
        world.work.tick(world, paco, paco.activity)
        self.assertIsNone(paco.activity)
        self.assertEqual(world.work.candidate(world, paco).name, HAUL_ACTION)

    def test_with_nobody_at_the_workshop_the_fuel_waits_and_the_lamps_go_out(self) -> None:
        world = _settled()
        world.residents["paco"].job_id = world.residents["paco"].post_id = None
        world.containers["generator"].items.clear()
        world.stock(world.containers["crate_workshop"], POWER_ITEM, 10, None)
        for _ in range(24 * 60):
            world.step(1)
            _content(world)
        self.assertFalse(world.has_power())
        self.assertEqual(world.containers["crate_workshop"].count(POWER_ITEM), 10)
        self.assertIn("power_failed", _types(world))


class MedicineTests(unittest.TestCase):
    def _patient(self, world: SimulationWorld, medic_on_duty: bool = True) -> Resident:
        raul, vera = world.residents["raul"], world.residents["vera"]
        raul.injuries = [Injury("cut", 40)]
        raul.job_id = None
        raul.x, raul.y = 27, 22
        raul.activity = Activity("rest", "clinic_bed_1", minutes_left=10_000, using=True)
        if medic_on_duty:
            vera.activity = Activity(WORK_ACTION, "medicine_cabinet", minutes_left=10_000, using=True)
        else:
            vera.job_id = None
        return raul

    def _health_after(self, hours: int, medicine: int, medic_on_duty: bool = True) -> tuple[float, SimulationWorld]:
        world = _settled()
        cabinet = world.containers["medicine_cabinet"]
        cabinet.items.clear()
        if medicine:
            world.stock(cabinet, "medicine", medicine, None)
        raul = self._patient(world, medic_on_duty)
        for _ in range(hours * 60):
            world.step(1)
            _content(world)
        return raul.health, world

    def test_the_clinic_starts_with_medicine_in_its_cabinet(self) -> None:
        world = _settled()
        self.assertEqual(world.containers["medicine_cabinet"].count("medicine"), 6)
        use = world.registries.interactables.get("clinic_bed").use
        self.assertEqual((use.care_item, use.care_from, use.dose_minutes), ("medicine", "medicine_cabinet", 720))

    def test_care_uses_up_a_dose_and_another_once_the_first_has_worn_off(self) -> None:
        world = _settled()
        raul = self._patient(world)
        cabinet = world.containers["medicine_cabinet"]
        world.step(1)
        self.assertEqual(cabinet.count("medicine"), 5)
        self.assertEqual(raul.dosed_until, world.clock.total_minutes + 720)
        self.assertEqual(_types(world).count("dose_given"), 1)
        for _ in range(11 * 60):
            world.step(1)
            _content(world)
        self.assertEqual(cabinet.count("medicine"), 5, "one dose lasts half a day")
        for _ in range(2 * 60):
            world.step(1)
            _content(world)
        self.assertEqual(cabinet.count("medicine"), 4)
        self.assertEqual(_types(world).count("dose_given"), 2)

    def test_with_no_medicine_the_medic_can_only_let_them_rest(self) -> None:
        with_medicine, _ = self._health_after(8, medicine=3)
        without, dry = self._health_after(8, medicine=0)
        resting, _ = self._health_after(8, medicine=0, medic_on_duty=False)
        self.assertGreater(with_medicine, without + 3)
        self.assertAlmostEqual(without, resting, places=6)
        self.assertEqual(_types(dry).count("no_medicine"), 1, "said once a day")
        self.assertTrue(any("No queda con qué curar a Raúl" in line for line in dry.event_log))

    def test_nobody_is_given_any_while_the_medic_is_away(self) -> None:
        _, world = self._health_after(4, medicine=3, medic_on_duty=False)
        self.assertEqual(world.containers["medicine_cabinet"].count("medicine"), 3)
        self.assertNotIn("dose_given", _types(world))
        self.assertNotIn("no_medicine", _types(world))

    def test_medicine_is_not_spent_on_what_only_water_would_cure(self) -> None:
        world = _settled()
        raul = self._patient(world)
        raul.injuries = []
        for _ in range(120):
            raul.needs.thirst = 100
            world.health.tick(world, raul)
        self.assertEqual([injury.kind for injury in raul.injuries], ["dehydration"])
        self.assertEqual(world.containers["medicine_cabinet"].count("medicine"), 6)

    def test_what_is_found_outside_goes_to_the_cabinet_and_what_a_caravan_leaves_is_fetched(self) -> None:
        world = _settled()
        sergio = world.residents["sergio"]
        world.stock(sergio.inventory, "medicine", 1, None)
        self.assertEqual(world.expeditions.errand(world, sergio), "medicine_cabinet")
        sergio.inventory.items.clear()
        self.assertIn("medicine", [item for item, _ in world.registries.world_events.events["caravan"].items])
        cabinet = world.containers["medicine_cabinet"]
        cabinet.items.clear()
        world.stock(world.containers["shop_counter"], "medicine", 3, None)
        world.clock.hour = 9
        for _ in range(180):
            world.step(1)
            _content(world)
            if cabinet.count("medicine") == 3:
                break
        self.assertEqual(cabinet.count("medicine"), 3)
        self.assertEqual(world.containers["shop_counter"].count("medicine"), 0)
        self.assertTrue(any("Vera lleva 3 de medicinas a un botiquín" in line for line in world.event_log))

    def test_ten_weeks_on_nobody_has_gone_without_medicine_or_light(self) -> None:
        for seed in (3, 11):
            world = SimulationWorld.demo_world(seed=seed)
            for _ in range(70 * 24 * 60):
                world.step(1)
            kinds = _types(world)
            self.assertNotIn("no_medicine", kinds, seed)
            self.assertNotIn("power_failed", kinds, seed)
            self.assertEqual(world.deaths, [], seed)


class BarTests(unittest.TestCase):
    def test_the_bar_left_for_the_water_stays_shut_until_someone_new_looks_for_work(self) -> None:
        world = _settled()
        self.assertTrue(world.staffing.assign(world, world.residents["lucia"], "water_carrier"))
        bar = world.registries.jobs["bartender"]
        self.assertTrue(world.staffing.is_short(world, bar))
        self.assertEqual(world.staffing.candidates(world, "bartender"), [], "nobody leaves a post that matters more")
        newcomer = Resident("nuevo", "Nuevo", seeks_work=True)
        world.residents[newcomer.resident_id] = newcomer
        self.assertEqual(world.staffing.opening_for(world, newcomer), "farmer", "a tenth mouth wants more hands in the garden")
        self.assertTrue(world.staffing.assign(world, newcomer, "farmer"))
        another = Resident("otra", "Otra", seeks_work=True)
        world.residents[another.resident_id] = another
        self.assertEqual(world.staffing.opening_for(world, another), "bartender")


class MoodTests(unittest.TestCase):
    def test_low_mood_makes_arguments_likelier(self) -> None:
        world = _settled()
        a, b = world.residents["marta"], world.residents["lucia"]
        a.mood = b.mood = 50
        ordinary = argument_chance(world, a, b)
        a.mood = b.mood = 5
        self.assertGreater(argument_chance(world, a, b), ordinary)

    def test_low_mood_slows_productive_work(self) -> None:
        high = _settled()
        low = _settled()
        for world, mood in ((high, 50), (low, 20)):
            world.clock.hour = 8
            farmer = _on_duty(world, "raul", minutes=60)
            farmer.mood = mood
            farmer.inventory.items = [item for item in farmer.inventory.items if item.owner_id is not None]
            for _ in range(17):
                world.step(1)
                farmer.needs = Needs(hunger=0, thirst=0, tiredness=0, social=0, stress=0)
        self.assertGreater(high.residents["raul"].inventory.count("vegetables"), 0)
        self.assertEqual(low.residents["raul"].inventory.count("vegetables"), 0)


class SustenanceSaveTests(unittest.TestCase):
    def test_thirst_mood_water_and_power_round_trip_and_old_saves_get_defaults(self) -> None:
        manager = SaveManager()
        world = _settled()
        world.residents["marta"].needs.thirst = 44
        world.residents["marta"].mood = 23
        loaded = manager.from_data(json.loads(json.dumps(manager.to_data(world))))
        self.assertEqual(manager.to_data(loaded), manager.to_data(world))

        data = manager.to_data(world)
        data["version"] = 15
        data["interactables"] = [placed for placed in data["interactables"] if placed["id"] not in ("water_tank", "generator")]
        data["containers"].pop("water_tank")
        data["containers"].pop("generator")
        for resident in data["residents"]:
            resident["needs"].pop("thirst", None)
            resident.pop("mood", None)
        older = manager.from_data(json.loads(json.dumps(data)))
        self.assertIn("water_tank", older.containers)
        self.assertIn("generator", older.containers)
        self.assertGreater(older.containers["water_tank"].count("water"), 0)
        self.assertGreater(older.power_units(), 0)
        self.assertTrue(all(resident.needs.thirst == 12.0 and resident.mood == 50.0 for resident in older.residents.values()))

    def test_a_dose_round_trips_and_a_save_from_before_medicine_finds_its_cabinet_stocked(self) -> None:
        manager = SaveManager()
        world = _settled()
        world.residents["raul"].dosed_until = 4321
        cabinet = world.containers["medicine_cabinet"]
        cabinet.take_units(cabinet.stack_of("medicine", None).instance_id, 4)
        loaded = manager.from_data(json.loads(json.dumps(manager.to_data(world))))
        self.assertEqual(manager.to_data(loaded), manager.to_data(world))
        self.assertEqual(loaded.residents["raul"].dosed_until, 4321)
        self.assertEqual(loaded.containers["medicine_cabinet"].count("medicine"), 2, "an emptied cabinet is not refilled")

        data = manager.to_data(world)
        data["version"] = 22
        data["containers"].pop("medicine_cabinet")
        for resident in data["residents"]:
            resident.pop("dosed_until")
        older = manager.from_data(json.loads(json.dumps(data)))
        self.assertEqual(older.containers["medicine_cabinet"].count("medicine"), 6)
        self.assertTrue(all(resident.dosed_until == 0 for resident in older.residents.values()))
        self.assertEqual(older.power_units(), world.power_units(), "and nothing else is restocked")

    def test_a_save_from_before_has_the_south_house_put_right_unless_it_was_rearranged(self) -> None:
        manager = SaveManager()
        world = _settled()
        was = {"crate_south": (8, 24), "bed_6": (7, 24), "bed_10": (7, 26)}
        now = {object_id: (world.interactables[object_id].x, world.interactables[object_id].y) for object_id in was}
        self.assertEqual(now, {"crate_south": (7, 27), "bed_6": (8, 24), "bed_10": (8, 26)})

        def saved(version: int, places: dict[str, tuple[int, int]]) -> SimulationWorld:
            data = manager.to_data(world)
            data["version"] = version
            for placed in data["interactables"]:
                if placed["id"] in places:
                    placed["x"], placed["y"] = places[placed["id"]]
            return manager.from_data(json.loads(json.dumps(data)))

        def places(loaded: SimulationWorld) -> dict[str, tuple[int, int]]:
            return {object_id: (loaded.interactables[object_id].x, loaded.interactables[object_id].y) for object_id in was}

        self.assertEqual(places(saved(22, was)), now)
        # Whatever the player moved since is left where they put it.
        self.assertEqual(places(saved(22, {**was, "bed_6": (5, 26)}))["bed_6"], (5, 26))
        # A save made since is taken as it stands.
        self.assertEqual(places(saved(23, was)), was)


if __name__ == "__main__":
    unittest.main()
