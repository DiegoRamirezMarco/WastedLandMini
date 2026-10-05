import unittest

from save.save_manager import SaveManager
from simulation.events.event import DomainEvent
from simulation.knowledge.fact import SOURCE_PARTICIPANT, SOURCE_TOLD, SOURCE_WITNESS, Fact
from simulation.knowledge.knowledge_system import MIN_CREDIBILITY, learn, share_rumor, witnesses_of
from simulation.residents.activity import Activity
from simulation.social.rumor import Rumor
from simulation.world import SimulationWorld
from world.visibility import line_of_sight, line_tiles, within_range

MINUTES_PER_DAY = 24 * 60
PLAZA = (20, 14)
INSIDE_STOREHOUSE = (31, 5)
INSIDE_DORMITORY = (6, 5)


def _feelings(world: SimulationWorld, source: str, target: str) -> tuple[float, ...]:
    rel = world.relationship(source, target)
    return (rel.affection, rel.trust, rel.fear, rel.resentment)


def _place(world: SimulationWorld, resident_id: str, tile: tuple[int, int]) -> None:
    world.residents[resident_id].x, world.residents[resident_id].y = tile


def _argue(world: SimulationWorld, a: str = "marta", b: str = "raul", importance: int = 50) -> Fact:
    """Stage an argument between two residents standing in the plaza."""
    _place(world, a, PLAZA)
    _place(world, b, (PLAZA[0] + 1, PLAZA[1]))
    names = world.residents[a].name, world.residents[b].name
    world.emit_event(
        DomainEvent("argument_started", importance, f"{names[0]} discute con {names[1]}", [a, b]),
        at=PLAZA,
        fact_text=f"{names[0]} discutió con {names[1]}",
    )
    return list(world.knowledge.facts.values())[-1]


def _tell(world: SimulationWorld, teller: str, listener: str) -> Rumor:
    """Have `teller` talk to `listener` until they pass something on."""
    for _ in range(200):
        rumor = share_rumor(world, world.residents[teller], world.residents[listener])
        if rumor is not None:
            return rumor
    raise AssertionError("nothing was told")


class VisibilityTests(unittest.TestCase):
    def test_line_runs_between_both_ends(self) -> None:
        tiles = line_tiles((0, 0), (4, 2))
        self.assertEqual((tiles[0], tiles[-1]), ((0, 0), (4, 2)))
        self.assertEqual(line_tiles((3, 3), (3, 3)), [(3, 3)])

    def test_something_opaque_in_between_blocks_sight_but_the_ends_do_not(self) -> None:
        wall = {(2, 0)}
        self.assertFalse(line_of_sight((0, 0), (4, 0), wall.__contains__))
        self.assertTrue(line_of_sight((0, 1), (4, 1), wall.__contains__))
        self.assertTrue(line_of_sight((2, 0), (4, 0), wall.__contains__))

    def test_range_counts_diagonals_as_one(self) -> None:
        self.assertTrue(within_range((0, 0), (8, 8), 8))
        self.assertFalse(within_range((0, 0), (9, 0), 8))


class WitnessTests(unittest.TestCase):
    def setUp(self) -> None:
        self.world = SimulationWorld.demo_world()
        for resident_id in self.world.residents:
            _place(self.world, resident_id, (1, 17))

    def test_someone_nearby_in_the_open_sees_it(self) -> None:
        _place(self.world, "lucia", (PLAZA[0] + 5, PLAZA[1] - 3))
        self.assertEqual(witnesses_of(self.world, PLAZA), ["lucia"])

    def test_someone_too_far_away_does_not(self) -> None:
        _place(self.world, "lucia", (PLAZA[0] + 12, PLAZA[1]))
        self.assertEqual(witnesses_of(self.world, PLAZA), [])

    def test_walls_hide_what_happens_inside_from_outside(self) -> None:
        _place(self.world, "lucia", (31, 9))
        self.assertEqual(witnesses_of(self.world, INSIDE_STOREHOUSE), [])
        _place(self.world, "lucia", (33, 6))
        self.assertEqual(witnesses_of(self.world, INSIDE_STOREHOUSE), ["lucia"])

    def test_sleepers_see_nothing_and_participants_are_not_witnesses(self) -> None:
        _place(self.world, "lucia", (PLAZA[0] + 2, PLAZA[1]))
        self.assertEqual(witnesses_of(self.world, PLAZA, exclude=["lucia"]), [])
        self.world.residents["lucia"].activity = Activity("sleep", "bed_1", minutes_left=300, using=True)
        self.assertEqual(witnesses_of(self.world, PLAZA), [])


class LocalKnowledgeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.world = SimulationWorld.demo_world()
        self.lucia = self.world.residents["lucia"]

    def test_an_absent_resident_does_not_react_until_told(self) -> None:
        _place(self.world, "lucia", INSIDE_STOREHOUSE)
        before = _feelings(self.world, "lucia", "raul"), _feelings(self.world, "lucia", "marta")
        stress_before = self.lucia.needs.stress
        fact = _argue(self.world)

        self.assertFalse(self.world.knowledge.knows("lucia", fact.fact_id))
        self.assertEqual((_feelings(self.world, "lucia", "raul"), _feelings(self.world, "lucia", "marta")), before)
        self.assertEqual(self.world.memories.of("lucia"), [])

        self.world.relationship("lucia", "marta").affection = 30
        calm = _feelings(self.world, "lucia", "raul")
        rumor = _tell(self.world, "marta", "lucia")

        belief = self.world.knowledge.belief("lucia", fact.fact_id)
        self.assertEqual((belief.source, belief.told_by), (SOURCE_TOLD, "marta"))
        self.assertEqual(belief.credibility, rumor.credibility)
        self.assertLess(belief.credibility, 1.0)
        self.assertGreater(self.world.relationship("lucia", "raul").resentment, calm[3])
        self.assertLess(self.world.relationship("lucia", "raul").trust, calm[1])
        self.assertGreater(self.lucia.needs.stress, stress_before)
        self.assertIn("Marta me contó", self.world.memories.of("lucia")[-1].text)

    def test_a_witness_reacts_at_once_and_more_strongly_than_someone_told(self) -> None:
        told_world = SimulationWorld.demo_world()
        _place(told_world, "lucia", INSIDE_STOREHOUSE)
        _argue(told_world)
        told_world.relationship("lucia", "marta").affection = 30
        _tell(told_world, "marta", "lucia")

        self.world.relationship("lucia", "marta").affection = 30
        _place(self.world, "lucia", (PLAZA[0] + 3, PLAZA[1] - 2))
        fact = _argue(self.world)
        belief = self.world.knowledge.belief("lucia", fact.fact_id)
        self.assertEqual((belief.source, belief.credibility), (SOURCE_WITNESS, 1.0))
        self.assertIn("Vi que", self.world.memories.of("lucia")[-1].text)
        self.assertGreater(
            self.world.relationship("lucia", "raul").resentment,
            told_world.relationship("lucia", "raul").resentment,
        )

    def test_participants_know_it_without_blaming_themselves(self) -> None:
        before = _feelings(self.world, "marta", "raul")
        fact = _argue(self.world)
        for resident_id in ("marta", "raul"):
            self.assertEqual(self.world.knowledge.belief(resident_id, fact.fact_id).source, SOURCE_PARTICIPANT)
        self.assertEqual(_feelings(self.world, "marta", "raul"), before)

    def test_an_onlooker_blames_the_one_they_like_less(self) -> None:
        _place(self.world, "lucia", (PLAZA[0] + 3, PLAZA[1]))
        self.world.relationship("lucia", "raul").affection = 40
        _argue(self.world)
        self.assertGreater(self.world.relationship("lucia", "marta").resentment, 0)
        self.assertEqual(self.world.relationship("lucia", "raul").resentment, 0)

    def test_an_onlooker_with_no_favourite_blames_both_a_little(self) -> None:
        _place(self.world, "lucia", (PLAZA[0] + 3, PLAZA[1]))
        _argue(self.world)
        both = self.world.relationship("lucia", "marta").resentment, self.world.relationship("lucia", "raul").resentment
        self.assertEqual(both[0], both[1])
        self.assertGreater(both[0], 0)

    def test_hearing_it_again_firms_the_belief_without_a_second_reaction(self) -> None:
        _place(self.world, "lucia", INSIDE_STOREHOUSE)
        fact = _argue(self.world)
        self.assertTrue(learn(self.world, self.lucia, fact, 0.4, SOURCE_TOLD, told_by="marta"))
        after_first = _feelings(self.world, "lucia", "raul")
        memories = len(self.world.memories.of("lucia"))
        self.assertFalse(learn(self.world, self.lucia, fact, 0.9, SOURCE_TOLD, told_by="raul"))
        self.assertEqual(self.world.knowledge.belief("lucia", fact.fact_id).credibility, 0.9)
        self.assertEqual(_feelings(self.world, "lucia", "raul"), after_first)
        self.assertEqual(len(self.world.memories.of("lucia")), memories)

    def test_a_barely_credible_rumor_is_not_believed(self) -> None:
        _place(self.world, "lucia", INSIDE_STOREHOUSE)
        fact = _argue(self.world)
        self.assertFalse(learn(self.world, self.lucia, fact, MIN_CREDIBILITY / 2, SOURCE_TOLD, told_by="marta"))
        self.assertFalse(self.world.knowledge.knows("lucia", fact.fact_id))

    def test_credibility_fades_along_the_chain_and_grows_with_trust(self) -> None:
        _place(self.world, "lucia", INSIDE_STOREHOUSE)
        _argue(self.world, "marta", "raul")
        first = _tell(self.world, "marta", "lucia")
        self.assertLess(first.credibility, 1.0)

        trusting = SimulationWorld.demo_world()
        _place(trusting, "lucia", INSIDE_STOREHOUSE)
        _argue(trusting, "marta", "raul")
        trusting.relationship("lucia", "marta").trust = 50
        self.assertGreater(_tell(trusting, "marta", "lucia").credibility, first.credibility)

        chain = SimulationWorld.demo_world()
        _place(chain, "raul", INSIDE_DORMITORY)
        _place(chain, "lucia", PLAZA)
        _place(chain, "marta", (PLAZA[0] + 1, PLAZA[1]))
        chain.emit_event(
            DomainEvent("argument_started", 50, "x", ["lucia", "marta"]), at=PLAZA, fact_text="Lucía discutió con Marta"
        )
        chain.residents["raul"].needs.stress = 0
        self.assertEqual(_tell(chain, "marta", "raul").credibility, first.credibility)
        self.assertIsNone(share_rumor(chain, chain.residents["marta"], chain.residents["raul"]))

    def test_nobody_is_told_about_their_own_argument(self) -> None:
        _place(self.world, "lucia", (PLAZA[0] + 3, PLAZA[1]))
        _argue(self.world)
        for _ in range(50):
            self.assertIsNone(share_rumor(self.world, self.lucia, self.world.residents["raul"]))


class KnowledgeInTheSettlementTests(unittest.TestCase):
    def test_news_travels_and_every_rumor_comes_from_someone_who_knew(self) -> None:
        world = SimulationWorld.demo_world(seed=99)
        world.step(10 * MINUTES_PER_DAY)
        told = [
            (resident_id, belief)
            for resident_id in world.residents
            for belief in world.knowledge.beliefs_of(resident_id)
            if belief.source == SOURCE_TOLD
        ]
        self.assertTrue(world.knowledge.facts)
        self.assertTrue(told)
        for resident_id, belief in told:
            teller = world.knowledge.belief(belief.told_by, belief.fact_id)
            self.assertIsNotNone(teller, "told by someone who did not know")
            self.assertLessEqual(teller.learned_at, belief.learned_at)
            self.assertLess(belief.credibility, teller.credibility)
            self.assertNotIn(resident_id, world.knowledge.facts[belief.fact_id].subject_ids)

    def test_knowledge_survives_saving_and_the_run_stays_identical(self) -> None:
        manager = SaveManager()
        original = SimulationWorld.demo_world(seed=99)
        original.step(3 * MINUTES_PER_DAY)
        self.assertTrue(original.knowledge.facts)
        loaded = manager.from_data(manager.to_data(original))
        self.assertEqual(manager.to_data(loaded), manager.to_data(original))
        original.step(3 * MINUTES_PER_DAY)
        loaded.step(3 * MINUTES_PER_DAY)
        self.assertEqual(manager.to_data(loaded), manager.to_data(original))

    def test_a_belief_about_a_missing_fact_is_dropped_on_load(self) -> None:
        manager = SaveManager()
        world = SimulationWorld.demo_world(seed=99)
        world.step(3 * MINUTES_PER_DAY)
        data = manager.to_data(world)
        data["facts"] = data["facts"][1:]
        loaded = manager.from_data(data)
        for resident_id in loaded.residents:
            for belief in loaded.knowledge.beliefs_of(resident_id):
                self.assertIn(belief.fact_id, loaded.knowledge.facts)
        loaded.step(MINUTES_PER_DAY)


if __name__ == "__main__":
    unittest.main()
