import json
import unittest

from save.save_manager import SaveManager
from simulation.events.world_event import Upcoming, Weather, world_event_settings_from_data
from simulation.items.item_system import USE_ITEM_ACTION
from simulation.knowledge.knowledge_system import share_rumor
from simulation.residents.activity import Activity
from simulation.residents.needs import Needs
from simulation.rng import SimulationRNG
from simulation.world import SimulationWorld

MINUTES_PER_DAY = 24 * 60
# Beside the settlement's radio, a little way off inside the cantina, and well outside it.
BY_THE_RADIO, ACROSS_THE_ROOM, OUTSIDE = (51, 8), (49, 8), (20, 18)


class _Certain(SimulationRNG):
    """A generator of world events for which whatever can happen does, at the first chance."""

    def random(self) -> float:
        return 0.0


def _types(world: SimulationWorld) -> list[str]:
    return [line.split(" | ")[1] for line in world.event_log]


def _keep_content(world: SimulationWorld) -> None:
    for resident in world.residents.values():
        resident.needs = Needs(hunger=0, tiredness=0, social=0, stress=0)


def _settled(seed: int = 7) -> SimulationWorld:
    world = SimulationWorld.demo_world(seed=seed)
    world.relationships.clear()
    _keep_content(world)
    return world


def _run(world: SimulationWorld, minutes: int) -> None:
    for _ in range(minutes):
        world.step(1)
        _keep_content(world)


def _stand(world: SimulationWorld, resident_id: str, tile: tuple[int, int]):
    resident = world.residents[resident_id]
    resident.x, resident.y = tile
    resident.job_id = resident.post_id = None
    resident.activity = Activity("wander", minutes_left=6000, using=True)
    return resident


def _storm_on_its_way(world: SimulationWorld, hours: int = 5) -> Upcoming:
    """Have a dust storm due in so many hours, with nobody any the wiser."""
    world.clock.day = max(world.clock.day, 2)
    world.happened = {event_id: world.clock.day for event_id in world.registries.world_events.events}
    upcoming = Upcoming("dust_storm", world.clock.total_minutes + hours * 60)
    world.upcoming.append(upcoming)
    return upcoming


def _listen(world: SimulationWorld, resident_id: str):
    """Sit a resident down at the settlement's radio and let them hear it out."""
    resident = _stand(world, resident_id, BY_THE_RADIO)
    # Someone with nothing on their mind does not sit by a radio for long.
    resident.needs.stress = 30
    resident.activity = world.activities.routine._use(world, resident, world.interactables["radio_set"])
    world.step(1)
    return resident


class OnItsWayTests(unittest.TestCase):
    def test_what_gives_warning_is_settled_hours_before_it_comes(self) -> None:
        world = _settled()
        world.event_rng = _Certain(1)
        world.clock.day, world.clock.hour = 2, 2
        world.happened = {event_id: 2 for event_id in world.registries.world_events.events if event_id != "dust_storm"}
        world.step(60)
        self.assertEqual(world.upcoming, [], "a storm for ten is not settled before four")
        world.step(60)
        self.assertEqual([(u.event_id, u.at - world.clock.total_minutes) for u in world.upcoming], [("dust_storm", 360)])
        self.assertIsNone(world.weather)
        self.assertEqual(world.happened["dust_storm"], 2)
        world.step(60)
        self.assertEqual(len(world.upcoming), 1, "one of a kind at a time")
        world.event_rng = SimulationRNG(1)
        world.step(5 * 60)
        self.assertTrue(world.happenings.is_stormy(world))
        self.assertEqual(world.upcoming, [])

    def test_what_gives_no_warning_just_happens(self) -> None:
        world = _settled()
        world.event_rng = _Certain(1)
        world.clock.day, world.clock.hour = 2, 1
        world.happened = {event_id: 2 for event_id in world.registries.world_events.events if event_id != "vermin"}
        world.step(60)
        self.assertEqual(world.upcoming, [])
        self.assertIn("food_spoiled", _types(world))

    def test_what_was_coming_comes_to_nothing_if_it_no_longer_can(self) -> None:
        world = _settled()
        _storm_on_its_way(world, hours=1)
        # A storm is already blowing when the next one is due.
        world.weather = Weather("dust_storm", world.clock.total_minutes + 180)
        world.step(61)
        self.assertEqual(world.upcoming, [])
        self.assertNotIn("weather_changed", _types(world), "no second storm was announced")

    def test_an_event_cannot_be_on_its_way_since_before_the_day_began(self) -> None:
        with self.assertRaisesRegex(ValueError, "before the day began"):
            world_event_settings_from_data(
                {"events": {"x": {"kind": "weather", "hours": [3, 9], "lead_hours": 5}}}
            )


class HearingOfItTests(unittest.TestCase):
    def setUp(self) -> None:
        self.world = _settled()
        self.upcoming = _storm_on_its_way(self.world)
        for resident_id in self.world.residents:
            _stand(self.world, resident_id, OUTSIDE)

    def _knows(self, resident_id: str) -> bool:
        fact_id = self.upcoming.fact_id
        return fact_id is not None and self.world.knowledge.knows(resident_id, fact_id)

    def test_nobody_knows_what_is_coming_just_because_it_is(self) -> None:
        self.world.step(30)
        self.assertIsNone(self.upcoming.fact_id)
        self.assertEqual(self.world.knowledge.facts, {})
        sergio = self.world.residents["sergio"]
        self.assertIsNone(self.world.happenings.expected(self.world, sergio, "weather", within=600))

    def test_whoever_listens_to_the_radio_hears_it_and_so_do_those_around(self) -> None:
        _stand(self.world, "raul", ACROSS_THE_ROOM)
        lucia = _listen(self.world, "lucia")
        self.assertEqual(lucia.current_action, "listen")
        self.assertEqual(_types(self.world).count("radio_bulletin"), 1)
        hour = self.upcoming.at // 60 % 24
        self.assertIn(f"Lucía oye en la radio que anuncian una tormenta de polvo para las {hour}", self.world.event_log[-2])
        self.assertTrue(self._knows("lucia"))
        self.assertTrue(self._knows("raul"), "he was in the room")
        self.assertFalse(self._knows("marta"), "she was not")
        self.assertIsNotNone(self.world.happenings.expected(self.world, lucia, "weather", within=600))
        self.assertIsNone(self.world.happenings.expected(self.world, lucia, "weather", within=60), "not that soon")
        self.assertIsNone(self.world.happenings.expected(self.world, lucia, "stock", within=600))

    def test_a_bulletin_is_news_once_and_later_listeners_hear_the_same(self) -> None:
        _listen(self.world, "lucia")
        fact_id = self.upcoming.fact_id
        _stand(self.world, "lucia", OUTSIDE)
        _listen(self.world, "marta")
        self.assertEqual(self.upcoming.fact_id, fact_id)
        self.assertTrue(self._knows("marta"))
        self.assertEqual(_types(self.world).count("radio_bulletin"), 1)
        self.assertEqual(len(self.world.knowledge.facts), 1)

    def test_a_radio_of_ones_own_gives_the_same_word(self) -> None:
        marta = self.world.residents["marta"]
        crate = self.world.interactables["crate_dorm"]
        radio = self.world.containers["crate_dorm"].stack_of("old_radio", "marta")
        marta.x, marta.y = crate.x - 1, crate.y
        marta.needs.stress = 60
        marta.activity = Activity(USE_ITEM_ACTION, "crate_dorm", minutes_left=10, item_id=radio.instance_id)
        self.world.step(10)
        self.assertTrue(self._knows("marta"))
        self.assertIn("radio_bulletin", _types(self.world))

    def test_with_nothing_on_its_way_the_radio_is_only_company(self) -> None:
        self.world.upcoming.clear()
        lucia = _listen(self.world, "lucia")
        lucia.needs.stress = 50
        self.world.step(10)
        self.assertLess(lucia.needs.stress, 50)
        self.assertNotIn("radio_bulletin", _types(self.world))

    def test_word_of_it_is_passed_on_until_its_hour_has_come(self) -> None:
        lucia = _listen(self.world, "lucia")
        marta = self.world.residents["marta"]
        lucia.personality.sociability = 100
        told = any(share_rumor(self.world, lucia, marta) is not None for _ in range(60))
        self.assertTrue(told)
        self.assertTrue(self._knows("marta"))
        self.assertTrue(any("Lucía le cuenta a Marta que en la radio anuncian" in line for line in self.world.event_log))

        self.world.clock.advance_minutes(6 * 60)
        raul = self.world.residents["raul"]
        for _ in range(60):
            self.assertIsNone(share_rumor(self.world, lucia, raul), "old news is no news")
        self.assertFalse(self._knows("raul"))


class HeedingItTests(unittest.TestCase):
    def setUp(self) -> None:
        self.world = _settled()
        self.sergio = self.world.residents["sergio"]

    def _morning(self, minutes: int = 150) -> None:
        self.world.clock.hour, self.world.clock.minute = 8, 0
        _run(self.world, minutes)

    def test_before_leaving_the_scavenger_hears_what_the_radio_has_to_say(self) -> None:
        self.world.clock.hour = 8
        candidate = self.world.work.candidate(self.world, self.sergio)
        self.assertEqual((candidate.name, candidate.target_id), ("listen", "radio_set"))
        self._morning()
        self.assertTrue(self.sergio.away, "with nothing announced, out he goes")
        log = self.world.event_log
        listened = next(i for i, line in enumerate(log) if "Sergio escucha la radio" in line)
        left = next(i for i, line in enumerate(log) if "expedition_left" in line)
        self.assertLess(listened, left)
        self.assertEqual(sum("Sergio escucha la radio" in line for line in log), 1, "once a day is enough")

    def test_warned_of_a_storm_they_stay_in_and_say_so_once(self) -> None:
        _storm_on_its_way(self.world, hours=5)
        self._morning(240)
        self.assertFalse(self.sergio.away)
        self.assertNotIn("expedition_left", _types(self.world))
        self.assertEqual(_types(self.world).count("stayed_in"), 1)
        self.assertTrue(any("Sergio no sale hoy: la radio anuncia mal tiempo" in line for line in self.world.event_log))

    def test_a_storm_too_far_off_to_catch_them_keeps_nobody_in(self) -> None:
        _storm_on_its_way(self.world, hours=20)
        self._morning()
        self.assertTrue(self.sergio.away)

    def test_they_go_by_what_they_have_heard_and_unwarned_the_storm_catches_them_out(self) -> None:
        del self.world.interactables["radio_set"]
        _storm_on_its_way(self.world, hours=3)
        self._morning(120)
        self.assertTrue(self.sergio.away, "nobody told him")
        danger = self.sergio.expedition.danger
        self.sergio.expedition.returns_at = self.world.clock.total_minutes + 300
        self.sergio.expedition.find_at = None
        _run(self.world, 70)
        self.assertTrue(self.world.happenings.is_stormy(self.world))
        self.assertAlmostEqual(self.sergio.expedition.danger, danger + 0.4)
        self.assertEqual(_types(self.world).count("caught_out"), 1)
        self.assertTrue(any("A Sergio le pilla fuera: tormenta de polvo" in line for line in self.world.event_log))

    def test_told_by_someone_else_is_as_good_as_having_heard_it(self) -> None:
        del self.world.interactables["radio_set"]
        upcoming = _storm_on_its_way(self.world, hours=5)
        self.world.interactables["radio_set"] = self.world.registries.maps[self.world.map_id].interactables["radio_set"]
        lucia = _listen(self.world, "lucia")
        del self.world.interactables["radio_set"]
        lucia.personality.sociability = 100
        self.assertTrue(any(share_rumor(self.world, lucia, self.sergio) is not None for _ in range(60)))
        self.assertTrue(self.world.knowledge.knows("sergio", upcoming.fact_id))
        self._morning(120)
        self.assertFalse(self.sergio.away)
        self.assertEqual(_types(self.world).count("stayed_in"), 1)


class RadioSaveTests(unittest.TestCase):
    def setUp(self) -> None:
        self.manager = SaveManager()

    def test_saving_with_something_on_its_way_continues_exactly_like_not_saving(self) -> None:
        original = _settled(seed=5)
        upcoming = _storm_on_its_way(original, hours=4)
        _listen(original, "lucia")
        loaded = self.manager.from_data(json.loads(json.dumps(self.manager.to_data(original))))
        self.assertEqual(self.manager.to_data(loaded), self.manager.to_data(original))
        self.assertEqual(loaded.upcoming, [upcoming])
        self.assertEqual(loaded.knowledge.facts[upcoming.fact_id].expires_at, upcoming.at)
        original.step(2 * MINUTES_PER_DAY)
        loaded.step(2 * MINUTES_PER_DAY)
        self.assertEqual(self.manager.to_data(loaded), self.manager.to_data(original))
        self.assertIn("weather_changed", _types(loaded))

    def test_an_older_save_has_nothing_on_its_way_and_gains_the_radio(self) -> None:
        world = SimulationWorld.demo_world(seed=9)
        data = self.manager.to_data(world)
        data["version"] = 12
        del data["upcoming"]
        data["interactables"] = [placed for placed in data["interactables"] if placed["id"] != "radio_set"]
        loaded = self.manager.from_data(json.loads(json.dumps(data)))
        self.assertEqual(loaded.upcoming, [])
        self.assertIn("radio_set", loaded.interactables)
        loaded.step(2 * MINUTES_PER_DAY)

    def test_word_that_nobody_remembers_and_events_nobody_knows_are_dropped(self) -> None:
        world = _settled()
        _storm_on_its_way(world)
        world.upcoming.append(Upcoming("blizzard", world.clock.total_minutes + 60))
        world.upcoming[0].fact_id = "fact_404"
        loaded = self.manager.from_data(json.loads(json.dumps(self.manager.to_data(world))))
        self.assertEqual([(u.event_id, u.fact_id) for u in loaded.upcoming], [("dust_storm", None)])


if __name__ == "__main__":
    unittest.main()
