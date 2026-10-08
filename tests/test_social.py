import re
import unittest
from dataclasses import replace

from save.save_manager import SaveManager
from simulation.registries import builtin_registries
from simulation.residents.activity import Activity
from simulation.residents.needs import NEED_NAMES, Needs
from simulation.residents.personality import Personality
from simulation.residents.resident import Resident
from simulation.social.relationship import Relationship
from simulation.social.social_system import (
    ARGUMENT_COOLDOWN_MINUTES,
    ARGUMENT_ID,
    CHAT_ID,
    TALK_ACTION,
    SocialSystem,
    argument_chance,
    feeling_changes,
)
from simulation.world import SimulationWorld
from world.pathfinding import manhattan

MINUTES_PER_DAY = 24 * 60
SOCIAL_ACTIONS = (CHAT_ID, ARGUMENT_ID)


def _snapshot(world: SimulationWorld) -> dict[tuple[str, str], tuple[float, ...]]:
    return {
        key: (rel.affection, rel.trust, rel.attraction, rel.fear, rel.resentment)
        for key, rel in world.relationships.items()
    }


def _happened(world: SimulationWorld) -> list[str]:
    """What the log tells of, with the line somebody said taken out of it."""
    return [re.sub(r' — [^:"]+: "[^"]*"$', "", line) for line in world.event_log]


def _talking(resident: Resident) -> bool:
    return resident.activity is not None and resident.activity.using and resident.activity.partner_id is not None


def _run_until_talking(world: SimulationWorld, limit: int = 3 * MINUTES_PER_DAY) -> list[Resident]:
    for _ in range(limit):
        world.step(1)
        pair = [resident for resident in world.residents.values() if _talking(resident)]
        if pair:
            return pair
    raise AssertionError("nobody talked")


class RelationshipTests(unittest.TestCase):
    def test_feelings_are_clamped_to_their_range(self) -> None:
        feelings = Relationship("a", "b")
        feelings.adjust("resentment", -5)
        feelings.adjust("fear", 500)
        feelings.adjust("affection", -500)
        self.assertEqual((feelings.resentment, feelings.fear, feelings.affection), (0.0, 100.0, -100.0))
        with self.assertRaises(ValueError):
            feelings.adjust("name", 1)


class OutcomeTests(unittest.TestCase):
    def setUp(self) -> None:
        interactions = builtin_registries().interactions
        self.chat, self.argument = interactions[CHAT_ID], interactions[ARGUMENT_ID]
        self.kind = Resident("kind", "Kind", personality=Personality(empathy=90, aggression=10))
        self.harsh = Resident("harsh", "Harsh", personality=Personality(empathy=10, aggression=90))

    def test_a_chat_warms_and_an_argument_sours(self) -> None:
        chat = feeling_changes(self.chat, self.kind, self.harsh, Relationship("kind", "harsh"))
        self.assertGreater(chat["affection"], 0)
        self.assertLess(chat["resentment"], 0)
        argument = feeling_changes(self.argument, self.kind, self.harsh, Relationship("kind", "harsh"))
        self.assertGreater(argument["resentment"], 0)
        self.assertLess(argument["affection"], 0)

    def test_the_two_sides_of_one_exchange_differ(self) -> None:
        hurt = feeling_changes(self.argument, self.kind, self.harsh, Relationship("kind", "harsh"))
        shrug = feeling_changes(self.argument, self.harsh, self.kind, Relationship("harsh", "kind"))
        self.assertGreater(hurt["fear"], shrug["fear"])
        self.assertNotEqual(hurt["resentment"], shrug["resentment"])

    def test_affection_grows_more_slowly_when_already_high(self) -> None:
        fresh = feeling_changes(self.chat, self.kind, self.harsh, Relationship("kind", "harsh"))
        close = feeling_changes(
            self.chat, self.kind, self.harsh, Relationship("kind", "harsh", affection=80)
        )
        self.assertLess(close["affection"], fresh["affection"])

    def test_resentment_strain_and_temper_make_arguments_likelier(self) -> None:
        world = SimulationWorld.demo_world()
        marta, lucia = world.residents["marta"], world.residents["lucia"]
        calm = argument_chance(world, marta, lucia)
        world.relationship("marta", "lucia").resentment = 60
        resentful = argument_chance(world, marta, lucia)
        self.assertGreater(resentful, calm)
        lucia.needs.hunger = 95
        self.assertGreater(argument_chance(world, marta, lucia), resentful)
        world.relationship("marta", "lucia").affection = 80
        world.relationship("lucia", "marta").affection = 80
        self.assertLess(argument_chance(world, marta, lucia), argument_chance(world, lucia, world.residents["raul"]) + 1)
        self.assertLessEqual(argument_chance(world, marta, lucia), 0.9)


class MeetingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.world = SimulationWorld.demo_world()
        self.social = SocialSystem()
        self.marta = self.world.residents["marta"]
        self.raul = self.world.residents["raul"]
        self.lucia = self.world.residents["lucia"]
        for resident in self.world.residents.values():
            resident.needs = Needs(hunger=0, tiredness=0, social=0, stress=0)

    def _stand(self, resident: Resident, minutes: int = 30) -> None:
        resident.activity = Activity("wander", minutes_left=minutes, using=True)

    def test_a_lonely_resident_wants_to_talk_to_someone_standing_around(self) -> None:
        self.marta.needs.social = 80
        self._stand(self.raul)
        partners = [candidate.partner_id for candidate in self.social.candidates(self.world, self.marta)]
        self.assertEqual(partners, ["raul"])

    def test_sleeping_walking_and_busy_residents_are_left_alone(self) -> None:
        self.marta.needs.social = 80
        self.raul.activity = Activity("sleep", "bed_1", minutes_left=300, using=True)
        self.lucia.activity = Activity("wander", path=[(31, 9), (32, 9)], minutes_left=30)
        self.assertEqual(self.social.candidates(self.world, self.marta), [])
        self._stand(self.lucia)
        self.raul.activity = Activity(TALK_ACTION, path=[(29, 9)], partner_id="lucia")
        self.assertEqual(self.social.candidates(self.world, self.marta), [])

    def test_someone_about_to_leave_is_not_worth_walking_to(self) -> None:
        self.marta.needs.social = 80
        self._stand(self.raul, minutes=1)
        self.assertEqual(self.social.candidates(self.world, self.marta), [])

    def test_resentment_puts_off_the_meek_and_draws_the_aggressive(self) -> None:
        self.marta.needs.social = 60
        self._stand(self.raul)
        neutral = self.social.candidates(self.world, self.marta)[0].score
        self.world.relationship("marta", "raul").resentment = 80
        self.marta.personality.aggression = 0
        self.assertLess(self.social.candidates(self.world, self.marta)[0].score, neutral)
        self.marta.needs.social = 0
        self.marta.personality.aggression = 100
        self.assertGreater(self.social.candidates(self.world, self.marta)[0].score, 0.1)

    def test_after_an_argument_they_keep_their_distance_for_a_while(self) -> None:
        self.marta.needs.social = 90
        self._stand(self.lucia)
        self.assertTrue(self.social.candidates(self.world, self.marta))
        feelings = self.world.relationship("marta", "lucia")
        feelings.last_argued = self.world.clock.total_minutes
        self.assertEqual(self.social.candidates(self.world, self.marta), [])
        self.world.clock.advance_minutes(ARGUMENT_COOLDOWN_MINUTES)
        self.assertTrue(self.social.candidates(self.world, self.marta))

    def test_talk_starts_only_next_to_the_partner_and_engages_both(self) -> None:
        self.marta.needs.social = 90
        self._stand(self.lucia, minutes=60)
        self.raul.activity = Activity("sleep", "bed_1", minutes_left=300, using=True)
        self.world.step(1)
        self.assertEqual(self.marta.activity.action, TALK_ACTION)
        for _ in range(60):
            if _talking(self.marta):
                break
            self.assertNotIn(self.lucia.current_action, SOCIAL_ACTIONS)
            self.world.step(1)
        self.assertTrue(_talking(self.marta) and _talking(self.lucia))
        self.assertEqual(manhattan(self.marta.tile, self.lucia.tile), 1)
        self.assertEqual(self.marta.activity.partner_id, "lucia")
        self.assertEqual(self.lucia.activity.partner_id, "marta")
        self.assertIn(self.marta.current_action, SOCIAL_ACTIONS)

    def test_arriving_to_find_the_partner_gone_ends_quietly(self) -> None:
        self.marta.activity = Activity(TALK_ACTION, partner_id="raul")
        events_before = len(self.world.event_log)
        self.world.activities.social.tick(self.world, self.marta, self.marta.activity)
        self.assertIsNone(self.marta.activity)
        self.assertEqual(len(self.world.event_log), events_before)


class SocialLifeTests(unittest.TestCase):
    def test_a_week_changes_relationships_and_directions_diverge(self) -> None:
        world = SimulationWorld.demo_world(seed=7)
        before = _snapshot(world)
        world.step(7 * MINUTES_PER_DAY)
        after = _snapshot(world)
        for key, start in before.items():
            self.assertNotEqual(after[key], start, key)
        diverged = [
            (a, b)
            for (a, b) in after
            if abs(world.relationship(a, b).affection - world.relationship(b, a).affection) > 1.0
        ]
        self.assertTrue(diverged)

    def test_both_sides_of_a_conversation_stay_in_step_and_end_together(self) -> None:
        world = SimulationWorld.demo_world(seed=5)
        for _ in range(4 * MINUTES_PER_DAY):
            world.step(1)
            for resident in world.residents.values():
                if not _talking(resident):
                    continue
                partner = world.residents[resident.activity.partner_id]
                self.assertTrue(_talking(partner), resident.name)
                self.assertEqual(partner.activity.partner_id, resident.resident_id)
                self.assertEqual(partner.activity.minutes_left, resident.activity.minutes_left)
                self.assertEqual(manhattan(resident.tile, partner.tile), 1)

    def test_sleepers_are_only_woken_by_someone_who_came_looking_for_them(self) -> None:
        world = SimulationWorld.demo_world(seed=9)
        asleep: set[str] = set()
        seekers: set[str] = set()
        for _ in range(4 * MINUTES_PER_DAY):
            world.step(1)
            for resident in world.residents.values():
                if resident.resident_id in asleep and resident.current_action in SOCIAL_ACTIONS:
                    self.assertIn(resident.activity.partner_id, seekers, resident.name)
            asleep = {r.resident_id for r in world.residents.values() if r.current_action == "sleep"}
            seekers = {
                r.resident_id for r in world.residents.values() if r.activity and r.activity.intent is not None
            }

    def test_no_need_reaches_its_maximum_with_social_life_on(self) -> None:
        for seed in (7, 99):
            world = SimulationWorld.demo_world(seed=seed)
            for _ in range(7 * MINUTES_PER_DAY):
                world.step(1)
                for resident in world.residents.values():
                    for need in NEED_NAMES:
                        self.assertLess(getattr(resident.needs, need), 100.0, (seed, resident.name, need))

    def test_only_the_two_who_talked_remember_it(self) -> None:
        world = SimulationWorld.demo_world(seed=7)
        pair = _run_until_talking(world)
        names = {resident.resident_id for resident in pair}
        outsider = next(r for r in world.residents.values() if r.resident_id not in names)
        while any(_talking(resident) for resident in pair):
            world.step(1)
        for resident in pair:
            memory = world.memories.of(resident.resident_id)[-1]
            other = (names - {resident.resident_id}).pop()
            self.assertEqual(memory.people, [other])
            self.assertIn(world.residents[other].name, memory.text)
            self.assertEqual(memory.timestamp, world.clock.total_minutes)
        # The third may have watched, and remembers that, but has no memory of taking part.
        for memory in world.memories.of(outsider.resident_id):
            self.assertFalse({"chat", "argument", "reconcile"} & set(memory.tags), memory.text)

    def test_a_conversation_emits_an_event_naming_both_participants(self) -> None:
        world = SimulationWorld.demo_world(seed=7)
        world.events.drain()
        pair = _run_until_talking(world)
        event = next(e for e in world.events.drain() if e.event_type.endswith("_started") and len(e.participants) == 2)
        self.assertEqual(set(event.participants), {resident.resident_id for resident in pair})
        self.assertIn(event.event_type, ("chat_started", "argument_started"))
        self.assertTrue(all(world.residents[p].name in event.text for p in event.participants))

    def test_arguments_happen_and_matter_more_than_chats(self) -> None:
        world = SimulationWorld.demo_world(seed=7)
        world.step(7 * MINUTES_PER_DAY)
        events = world.events.drain()
        chats = [event for event in events if event.event_type == "chat_started"]
        arguments = [event for event in events if event.event_type == "argument_started"]
        self.assertTrue(chats and arguments)
        self.assertGreater(len(chats), len(arguments))
        self.assertGreater(min(e.importance for e in arguments), max(e.importance for e in chats))


class SpokenLineTests(unittest.TestCase):
    """Which line is said is a matter of words. Writing one changes nothing that happens.

    A talk is about something and quotes nobody (S58): the lines left are those of a quarrel."""

    def _world(self, angry: list[str]) -> SimulationWorld:
        registries = builtin_registries()
        return SimulationWorld.demo_world(seed=7, registries=replace(registries, dialogue={**registries.dialogue, "angry": angry}))

    def test_writing_another_line_changes_nothing_that_happens(self) -> None:
        written = list(builtin_registries().dialogue["angry"])
        worlds = [self._world(written), self._world(["Otra más.", "Y otra."]), self._world([])]
        for world in worlds:
            world.step(2 * MINUTES_PER_DAY)
        plain, wordy, silent = worlds
        self.assertTrue(any('"Otra más."' in line or '"Y otra."' in line for line in wordy.event_log))
        for other in (wordy, silent):
            self.assertEqual(_happened(other), _happened(plain))
            self.assertEqual(other.rng.get_state(), plain.rng.get_state())

    def test_the_line_said_is_one_of_those_written_and_the_same_for_the_same_seed(self) -> None:
        written = list(builtin_registries().dialogue["angry"])
        first, second = self._world(written), self._world(written)
        for world in (first, second):
            world.step(2 * MINUTES_PER_DAY)
        said = [line for line in first.event_log if "| argument_started |" in line]
        self.assertTrue(said)
        self.assertTrue(all(any(f'"{each}"' in line for each in written) for line in said))
        self.assertTrue(all(" — " not in line for line in first.event_log if "| chat_started |" in line))
        self.assertEqual(first.event_log, second.event_log)


class SocialSaveTests(unittest.TestCase):
    def setUp(self) -> None:
        self.manager = SaveManager()

    def test_saving_mid_conversation_continues_exactly_like_not_saving(self) -> None:
        original = SimulationWorld.demo_world(seed=7)
        _run_until_talking(original)
        loaded = self.manager.from_data(self.manager.to_data(original))
        self.assertEqual(self.manager.to_data(loaded), self.manager.to_data(original))
        self.assertTrue(any(_talking(resident) for resident in loaded.residents.values()))
        original.step(2 * MINUTES_PER_DAY)
        loaded.step(2 * MINUTES_PER_DAY)
        self.assertEqual(self.manager.to_data(loaded), self.manager.to_data(original))
        self.assertTrue(loaded.memories.resident_ids())

    def test_version_2_save_without_memories_or_partners_loads(self) -> None:
        world = SimulationWorld.demo_world(seed=7)
        world.step(300)
        data = self.manager.to_data(world)
        data["version"] = 2
        del data["memories"]
        for resident in data["residents"]:
            if resident["activity"] is not None:
                del resident["activity"]["partner_id"]
        loaded = self.manager.from_data(data)
        self.assertEqual(loaded.memories.resident_ids(), [])
        loaded.step(MINUTES_PER_DAY)

    def test_a_one_sided_saved_conversation_is_dropped(self) -> None:
        world = SimulationWorld.demo_world(seed=7)
        pair = _run_until_talking(world)
        data = self.manager.to_data(world)
        for resident in data["residents"]:
            if resident["id"] == pair[1].resident_id:
                resident["activity"] = None
        loaded = self.manager.from_data(data)
        self.assertIsNone(loaded.residents[pair[0].resident_id].activity)
        loaded.step(MINUTES_PER_DAY)


if __name__ == "__main__":
    unittest.main()
