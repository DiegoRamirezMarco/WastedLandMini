import unittest

from simulation.residents.needs import Needs


class NeedsTests(unittest.TestCase):
    def test_hunger_increases_with_time(self) -> None:
        needs = Needs(hunger=10)
        needs.step(60)
        self.assertGreater(needs.hunger, 10)


if __name__ == "__main__":
    unittest.main()
