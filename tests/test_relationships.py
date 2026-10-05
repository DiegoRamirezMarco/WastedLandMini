import unittest

from simulation.world import SimulationWorld


class RelationshipTests(unittest.TestCase):
    def test_relationships_are_directional(self) -> None:
        world = SimulationWorld.demo_world()
        world.relationship("marta", "raul").affection = 80
        world.relationship("raul", "marta").affection = 10
        self.assertEqual(world.relationship("marta", "raul").affection, 80)
        self.assertEqual(world.relationship("raul", "marta").affection, 10)


if __name__ == "__main__":
    unittest.main()
