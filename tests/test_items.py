import tempfile
import unittest
from pathlib import Path

from simulation.items.registry import ItemRegistry


class ItemRegistryTests(unittest.TestCase):
    def test_custom_definition_loads(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "data.json"
            path.write_text('{"id":"x","name":"X","article":"un","category":"gift"}', encoding="utf-8")
            registry = ItemRegistry()
            item = registry.load_json_file(path)
            self.assertEqual(item.item_id, "x")


if __name__ == "__main__":
    unittest.main()
