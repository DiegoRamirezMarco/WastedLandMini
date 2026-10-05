import json
import tempfile
import unittest
from pathlib import Path

from save.save_manager import SaveManager
from simulation.commands import ChooseOptionCommand
from simulation.events.world_event import Upcoming, Weather
from simulation.events.world_event_system import RAID_DECISION
from simulation.knowledge.fact import SOURCE_TOLD
from simulation.knowledge.knowledge_system import learn, witnesses_of
from simulation.registries import DATA_DIR, BuiltInRegistries
from simulation.residents.activity import SHELTER_ACTION, Activity
from simulation.residents.needs import Needs
from simulation.rng import SimulationRNG
from simulation.social.social_system import SocialSystem
from simulation.work.work_system import WORK_ACTION
from simulation.world import SimulationWorld

MINUTES_PER_DAY = 24 * 60
# Open ground away from every fire and lamp, and tiles along the same row at growing distances.
HERE, NEAR, FAR, VERY_FAR = (20, 18), (23, 18), (26, 18), (30, 18)
INDOORS = (5, 5)


class _Fixed(SimulationRNG):
    """A generator of world events whose every roll comes up the same."""

    def __init__(self, value: float) -> None:
        super().__init__(1)
        self.value = value

    def random(self) -> float:
        return self.value


def _types(world: SimulationWorld) -> list[str]:
    return [line.split(" | ")[1] for line in world.event_log]


def _keep_content(world: SimulationWorld) -> None:
    for resident in world.residents.values():
        resident.needs = Needs(hunger=0, tiredness=0, social=0, stress=resident.needs.stress)


def _settled(seed: int = 7) -> SimulationWorld:
    world = SimulationWorld.demo_world(seed=seed)
    world.relationships.clear()
    for resident in world.residents.values():
        resident.needs = Needs(hunger=0, tiredness=0, social=0, stress=0)
    # Nothing from outside happens unless a test makes it.
    world.clock.day = 2
    world.happened = {event_id: 2 for event_id in world.registries.world_events.events}
    return world


def _run(world: SimulationWorld, minutes: int) -> None:
    for _ in range(minutes):
        world.step(1)
        _keep_content(world)


def _stand(world: SimulationWorld, resident_id: str, tile: tuple[int, int]):
    resident = world.residents[resident_id]
    resident.x, resident.y = tile
    resident.activity = Activity("wander", minutes_left=6000, using=True)
    return resident


def _on_duty(world: SimulationWorld, resident_id: str, minutes: int = 600, at: tuple[int, int] | None = None):
    resident = world.residents[resident_id]
    post = world.interactables[resident.post_id]
    resident.x, resident.y = at or (post.x, post.y - 1)
    resident.activity = Activity(WORK_ACTION, resident.post_id, minutes_left=minutes, using=True)
    resident.current_action = WORK_ACTION
    return resident


def _storm(world: SimulationWorld, minutes: int = 120) -> None:
    world.weather = Weather("dust_storm", world.clock.total_minutes + minutes)


def _raid_in(world: SimulationWorld, minutes: int) -> Upcoming:
    upcoming = Upcoming("raid", world.clock.total_minutes + minutes)
    world.upcoming.append(upcoming)
    return upcoming


def _stock(world: SimulationWorld) -> dict[str, int]:
    return {
        container_id: sum(item.quantity for item in inventory.items if item.owner_id is None)
        for container_id, inventory in world.containers.items()
    }


def _registries_with(file_name: str, old: str, new: str) -> BuiltInRegistries:
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


class DarknessTests(unittest.TestCase):
    def setUp(self) -> None:
        self.world = _settled()
        for resident_id in self.world.residents:
            _stand(self.world, resident_id, INDOORS)
        _stand(self.world, "raul", HERE)

    def test_night_falls_and_lifts_by_the_clock(self) -> None:
        dark = {}
        for hour in (12, 21, 22, 0, 4, 5):
            self.world.clock.hour = hour
            dark[hour] = self.world.is_dark()
        self.assertEqual(dark, {12: False, 21: False, 22: True, 0: True, 4: True, 5: False})

    def test_in_the_dark_only_what_is_close_is_seen(self) -> None:
        self.world.clock.hour = 12
        self.assertEqual(witnesses_of(self.world, FAR), ["raul"])
        self.world.clock.hour = 23
        self.assertEqual(witnesses_of(self.world, FAR), [])
        self.assertEqual(witnesses_of(self.world, NEAR), ["raul"])

    def test_a_fire_or_a_lamp_shows_what_is_by_it_from_as_far_as_by_day(self) -> None:
        self.world.clock.hour = 23
        by_the_fire, onlooker = (19, 13), (19, 20)
        _stand(self.world, "raul", onlooker)
        self.assertTrue(self.world.is_lit(by_the_fire))
        self.assertFalse(self.world.is_lit(FAR))
        self.assertEqual(witnesses_of(self.world, by_the_fire), ["raul"])
        del self.world.interactables["campfire"]
        self.assertFalse(self.world.is_lit(by_the_fire))
        self.assertEqual(witnesses_of(self.world, by_the_fire), [])

    def test_light_does_not_go_through_walls(self) -> None:
        self.assertTrue(self.world.is_lit((14, 25)), "by the workbench, inside the workshop")
        self.assertFalse(self.world.is_lit((14, 22)), "just outside its back wall")

    def test_whoever_keeps_watch_sees_further_in_the_dark_too(self) -> None:
        self.world.clock.hour = 23
        tomas = _on_duty(self.world, "tomas", at=HERE)
        self.assertEqual(witnesses_of(self.world, VERY_FAR), ["tomas"])
        tomas.activity = Activity("wander", minutes_left=600, using=True)
        self.assertEqual(witnesses_of(self.world, VERY_FAR), [])


class ShelterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.world = _settled()
        self.world.clock.hour = 9
        self.raul = self.world.residents["raul"]

    def _idle(self, resident_id: str, tile: tuple[int, int]):
        resident = self.world.residents[resident_id]
        resident.x, resident.y = tile
        resident.job_id = resident.post_id = None
        resident.activity = None
        return resident

    def test_caught_in_a_storm_with_nothing_pressing_a_resident_gets_under_a_roof(self) -> None:
        lucia = self._idle("lucia", HERE)
        self.assertNotEqual(self.world.activities.routine.plan(self.world, lucia).action, SHELTER_ACTION)
        _storm(self.world)
        lucia.activity = self.world.activities.routine.plan(self.world, lucia)
        self.assertEqual(lucia.activity.action, SHELTER_ACTION)
        self.assertTrue(self.world.under_roof(lucia.activity.path[-1]))
        for _ in range(60):
            self.world.step(1)
            if not lucia.activity.path:
                break
        self.world.step(1)
        self.assertTrue(self.world.under_roof(lucia.tile))
        self.assertEqual(lucia.current_action, SHELTER_ACTION)

    def test_shelter_spares_the_nerves_and_ends_with_the_storm(self) -> None:
        lucia = self._idle("lucia", HERE)
        outside = _stand(self.world, "paco", NEAR)
        _storm(self.world, 100)
        lucia.activity = self.world.activities.routine.plan(self.world, lucia)
        self.world.step(90)
        self.assertLess(lucia.needs.stress, outside.needs.stress)
        self.assertEqual(lucia.activity.action, SHELTER_ACTION)
        self.world.step(15)
        self.assertFalse(self.world.happenings.is_stormy(self.world))
        self.assertFalse(lucia.activity is not None and lucia.activity.action == SHELTER_ACTION)

    def test_a_real_need_still_comes_first(self) -> None:
        lucia = self._idle("lucia", HERE)
        _storm(self.world)
        lucia.needs.hunger = 92
        self.assertEqual(self.world.activities.routine.plan(self.world, lucia).action, "eat")

    def test_nobody_who_is_in_the_dry_strolls_out_into_it(self) -> None:
        lucia = self._idle("lucia", INDOORS)
        _storm(self.world)
        for _ in range(40):
            stroll = self.world.activities.routine.plan(self.world, lucia)
            self.assertNotEqual(stroll.action, SHELTER_ACTION)
            self.assertTrue(self.world.under_roof(stroll.path[-1] if stroll.path else lucia.tile))

    def test_work_in_the_open_stops_for_a_storm_and_starts_again_after(self) -> None:
        _on_duty(self.world, "raul", minutes=230)
        marta = _on_duty(self.world, "marta", minutes=230)
        _storm(self.world, 45)
        self.world.step(1)
        self.assertFalse(self.world.work.on_duty(self.world, self.raul))
        self.assertTrue(self.world.work.on_duty(self.world, marta), "the cook has a roof over her")
        self.assertIsNone(self.world.work.candidate(self.world, self.raul))
        _run(self.world, 35)
        self.assertTrue(self.world.under_roof(self.raul.tile))
        back = False
        for _ in range(90):
            self.world.step(1)
            _keep_content(self.world)
            back = back or self.world.work.on_duty(self.world, self.raul)
        self.assertTrue(back)

    def test_someone_waiting_out_the_weather_can_be_talked_to(self) -> None:
        lucia = self._idle("lucia", INDOORS)
        lucia.activity = Activity(SHELTER_ACTION, minutes_left=90, using=True)
        paco = self._idle("paco", (6, 5))
        paco.needs.social = 90
        self.assertIn("lucia", [c.partner_id for c in SocialSystem().candidates(self.world, paco)])


class RaidTests(unittest.TestCase):
    def setUp(self) -> None:
        self.world = _settled()
        self.world.clock.hour, self.world.clock.minute = 22, 58
        self.tomas = self.world.residents["tomas"]
        for resident_id in self.world.residents:
            _stand(self.world, resident_id, INDOORS)

    def _decision(self):
        return next((d for d in self.world.decisions.values() if d.kind == RAID_DECISION), None)

    def test_with_nobody_on_watch_raiders_take_a_share_of_what_is_everyones(self) -> None:
        before = _stock(self.world)
        private = self.world.containers["crate_1"].count("canned_beans")
        _raid_in(self.world, 1)
        self.world.step(1)
        after = _stock(self.world)
        self.assertIsNone(self._decision())
        self.assertEqual(before["pantry_1"] - after["pantry_1"], 6)
        self.assertEqual(before["shop_counter"] - after["shop_counter"], 2)
        self.assertEqual(before["scrap_yard"] - after["scrap_yard"], 1)
        self.assertEqual(before["cooking_pot"], after["cooking_pot"], "they do not stop to eat")
        self.assertEqual(self.world.containers["crate_1"].count("canned_beans"), private)
        self.assertEqual(_types(self.world).count("raid"), 1)
        self.assertIn("Unos merodeadores entran de noche: se llevan 12 cosas", self.world.event_log[-1])
        self.assertIsNone(self.world.under_raid)

    def test_a_guard_at_the_gate_gets_to_decide_and_the_player_to_advise(self) -> None:
        _on_duty(self.world, "tomas")
        before = _stock(self.world)
        _raid_in(self.world, 1)
        self.world.step(1)
        decision = self._decision()
        self.assertEqual(decision.resident_id, "tomas")
        self.assertIn("raiders_at_gate", _types(self.world))
        self.assertEqual(_stock(self.world), before, "nothing is taken while he makes up his mind")
        self.assertEqual([option.option_id for option in decision.options], ["fight", "neutral", "hide"])
        self.world.event_rng = _Fixed(0.99)
        self.assertEqual(self.world.apply_command(ChooseOptionCommand(decision.decision_id, "fight")), "stand_ground")
        self.assertEqual(_stock(self.world), before)
        self.assertIn("raid_repelled", _types(self.world))
        self.assertNotIn("raid", _types(self.world))
        self.assertEqual(self.tomas.health, 100.0)
        self.assertIsNone(self.world.under_raid)

    def test_giving_way_costs_the_settlement_and_the_guards_peace_of_mind(self) -> None:
        _on_duty(self.world, "tomas")
        self.tomas.personality.courage = self.tomas.personality.aggression = 5
        before = _stock(self.world)
        _raid_in(self.world, 1)
        self.world.step(1)
        self.assertEqual(self.world.apply_command(ChooseOptionCommand(self._decision().decision_id, "hide")), "give_way")
        self.assertLess(sum(_stock(self.world).values()), sum(before.values()))
        self.assertGreaterEqual(self.tomas.needs.stress, 15)
        self.assertIn("raid", _types(self.world))
        self.assertTrue(any("Dejé pasar" in memory.text for memory in self.world.memories.of("tomas")))

    def test_left_alone_the_brave_stand_and_the_timid_step_aside(self) -> None:
        _on_duty(self.world, "tomas")
        _raid_in(self.world, 1)
        self.world.step(1)
        self.assertEqual(self.world.interventions.resolve(self.world, self._decision().decision_id, None), "stand_ground")
        self.setUp()
        _on_duty(self.world, "tomas")
        self.tomas.personality.courage = self.tomas.personality.aggression = 5
        _raid_in(self.world, 1)
        self.world.step(1)
        self.assertEqual(self.world.interventions.resolve(self.world, self._decision().decision_id, None), "give_way")

    def test_standing_up_to_them_can_cost_a_wound_and_a_weapon_makes_it_less_likely(self) -> None:
        outcomes = {}
        for armed in (True, False):
            self.setUp()
            _on_duty(self.world, "tomas")
            if not armed:
                self.tomas.inventory.items.clear()
            _raid_in(self.world, 1)
            self.world.step(1)
            # A roll that an armed defender shrugs off and a bare-handed one does not.
            self.world.event_rng = _Fixed(0.3)
            self.world.apply_command(ChooseOptionCommand(self._decision().decision_id, "fight"))
            outcomes[armed] = self.tomas.health
        self.assertEqual(outcomes[True], 100.0)
        self.assertLess(outcomes[False], 100.0)
        self.assertTrue(any("plantar cara a unos merodeadores" in line for line in self.world.event_log))

    def test_whoever_hears_of_it_thinks_the_better_of_the_guard(self) -> None:
        _on_duty(self.world, "tomas")
        _raid_in(self.world, 1)
        self.world.step(1)
        self.world.event_rng = _Fixed(0.99)
        self.world.apply_command(ChooseOptionCommand(self._decision().decision_id, "fight"))
        fact = next(f for f in self.world.knowledge.facts.values() if f.event_type == "raid_repelled")
        lucia = self.world.residents["lucia"]
        self.assertFalse(self.world.knowledge.knows("lucia", fact.fact_id), "she was indoors")
        learn(self.world, lucia, fact, 1.0, SOURCE_TOLD, told_by="tomas")
        feelings = self.world.relationship("lucia", "tomas")
        self.assertGreater(feelings.trust, 5)
        self.assertGreater(feelings.affection, 3)

    def test_if_the_guard_is_gone_before_deciding_they_walk_in(self) -> None:
        _on_duty(self.world, "tomas")
        _raid_in(self.world, 1)
        self.world.step(1)
        self.assertIsNotNone(self.world.under_raid)
        self.world.health.die(self.world, self.tomas, "una prueba")
        self.world.step(1)
        self.assertIsNone(self.world.under_raid)
        self.assertIn("raid", _types(self.world))


class NightWatchTests(unittest.TestCase):
    def setUp(self) -> None:
        self.world = _settled()
        self.tomas = self.world.residents["tomas"]
        self.job = self.world.work.job_of(self.world, self.tomas)

    def _set_time(self, hour: int, minute: int = 0) -> None:
        self.world.clock.hour, self.world.clock.minute = hour, minute

    def test_the_guard_goes_to_hear_the_evening_bulletin_once(self) -> None:
        self._set_time(19, 30)
        self.assertEqual(self.world.work.candidate(self.world, self.tomas).name, WORK_ACTION)
        self._set_time(20, 5)
        candidate = self.world.work.candidate(self.world, self.tomas)
        self.assertEqual((candidate.name, candidate.target_id), ("listen", "radio_set"))
        self.world.happenings.hear_radio(self.world, self.tomas)
        self.assertEqual(self.world.work.candidate(self.world, self.tomas).name, WORK_ACTION)
        self._set_time(21, 30)
        self.assertIsNone(self.world.work.candidate(self.world, self.tomas), "with nothing announced, to bed")

    def test_a_morning_bulletin_does_not_count_for_the_evening(self) -> None:
        self._set_time(8)
        self.world.happenings.hear_radio(self.world, self.tomas)
        self._set_time(20, 5)
        self.assertEqual(self.world.work.candidate(self.world, self.tomas).name, "listen")

    def test_knowing_raiders_are_about_keeps_them_at_the_gate_past_their_shift(self) -> None:
        self._set_time(21, 30)
        raid = _raid_in(self.world, 90)
        self.assertEqual(self.world.work.shift_minutes_left(self.world, self.tomas, self.job), 0, "nobody has told him")
        self.world.happenings.hear_radio(self.world, self.tomas)
        self.assertIsNotNone(raid.fact_id)
        self.assertEqual(self.world.work.shift_minutes_left(self.world, self.tomas, self.job), 150)
        self.assertEqual(self.world.work.candidate(self.world, self.tomas).name, WORK_ACTION)
        for _ in range(60):
            self.world.step(1)
            _keep_content(self.world)
            if self.world.work.on_duty(self.world, self.tomas):
                break
        self.assertTrue(self.world.work.on_duty(self.world, self.tomas))
        self.assertEqual(_types(self.world).count("night_watch"), 1)
        self.assertTrue(any("Tomás se queda de guardia esta noche" in line for line in self.world.event_log))
        raul = self.world.residents["raul"]
        raul_job = self.world.work.job_of(self.world, raul)
        self.world.happenings.hear_radio(self.world, raul)
        self.assertEqual(self.world.work.shift_minutes_left(self.world, raul, raul_job), 0, "it is not a farmer's job")

    def test_from_the_bulletin_to_the_gate(self) -> None:
        self._set_time(19, 0)
        _on_duty(self.world, "tomas", minutes=120)
        _raid_in(self.world, 4 * 60)
        self.world.event_rng = _Fixed(0.99)
        for _ in range(5 * 60):
            self.world.step(1)
            _keep_content(self.world)
            for decision in list(self.world.decisions.values()):
                if decision.kind == RAID_DECISION:
                    self.world.apply_command(ChooseOptionCommand(decision.decision_id, "fight"))
        types = _types(self.world)
        order = [types.index(name) for name in ("radio_bulletin", "night_watch", "raiders_at_gate", "raid_repelled")]
        self.assertEqual(order, sorted(order))
        self.assertNotIn("raid", types, "nothing was carried off")

    def test_unwarned_the_gate_stands_empty_and_they_help_themselves(self) -> None:
        del self.world.interactables["radio_set"]
        self._set_time(19, 0)
        _on_duty(self.world, "tomas", minutes=120)
        _raid_in(self.world, 4 * 60)
        self.world.event_rng = _Fixed(0.99)
        _run(self.world, 5 * 60)
        types = _types(self.world)
        self.assertNotIn("night_watch", types)
        self.assertNotIn("raiders_at_gate", types)
        self.assertEqual(types.count("raid"), 1)


class DangerDataAndSaveTests(unittest.TestCase):
    def setUp(self) -> None:
        self.manager = SaveManager()

    def test_bad_definitions_are_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "never happens"):
            _registries_with("jobs.json", '"watch_for": "raid"', '"watch_for": "comet"')
        with self.assertRaisesRegex(ValueError, "not a container kind"):
            _registries_with("world_events.json", '"scrap_pile"\n      ]', '"guard_post"\n      ]')
        with self.assertRaisesRegex(ValueError, "Unknown raid choice"):
            _registries_with("decisions.json", '"raid": "give_way"', '"raid": "run"')

    def test_saving_with_raiders_at_the_gate_continues_exactly_like_not_saving(self) -> None:
        original = _settled(seed=5)
        original.clock.hour, original.clock.minute = 22, 58
        _on_duty(original, "tomas")
        _raid_in(original, 1)
        original.step(3)
        self.assertEqual(original.under_raid, "raid")
        loaded = self.manager.from_data(json.loads(json.dumps(self.manager.to_data(original))))
        self.assertEqual(self.manager.to_data(loaded), self.manager.to_data(original))
        self.assertEqual(loaded.under_raid, "raid")
        original.step(2 * MINUTES_PER_DAY)
        loaded.step(2 * MINUTES_PER_DAY)
        self.assertEqual(self.manager.to_data(loaded), self.manager.to_data(original))

    def test_raiders_nobody_is_facing_are_not_kept_and_an_older_save_has_none(self) -> None:
        world = _settled()
        world.under_raid = "raid"
        data = self.manager.to_data(world)
        self.assertIsNone(self.manager.from_data(json.loads(json.dumps(data))).under_raid)
        data["version"] = 13
        del data["under_raid"]
        loaded = self.manager.from_data(json.loads(json.dumps(data)))
        self.assertIsNone(loaded.under_raid)
        loaded.step(MINUTES_PER_DAY)


class DarkWeeksTests(unittest.TestCase):
    def test_four_weeks_of_storms_and_raiders_leave_the_settlement_standing(self) -> None:
        # A seed with which raiders come within the four weeks.
        world = SimulationWorld.demo_world(seed=5)
        sheltered = 0
        for _ in range(28 * MINUTES_PER_DAY):
            world.step(1)
            for resident in world.residents.values():
                sheltered += resident.current_action == SHELTER_ACTION
                for need in ("hunger", "tiredness", "social", "stress"):
                    self.assertLess(getattr(resident.needs, need), 100.0, (resident.name, need, world.clock.label))
        types = _types(world)
        self.assertGreater(sheltered, 60, "people got out of the storms")
        self.assertIn("raiders_at_gate", types)
        self.assertIn("night_watch", types)
        self.assertLess(types.index("night_watch"), types.index("raiders_at_gate"))
        self.assertEqual(world.deaths, [])
        self.assertNotIn("no_food", types)


if __name__ == "__main__":
    unittest.main()
