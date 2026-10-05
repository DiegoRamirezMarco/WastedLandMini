import json
from pathlib import Path
from typing import Any

from simulation.items.item import ItemDefinition

# Category of the stand-in definition used for items whose real definition is gone.
UNKNOWN_CATEGORY = "unknown"


class ItemRegistry:
    def __init__(self) -> None:
        self._definitions: dict[str, ItemDefinition] = {}
        self._placeholders: dict[str, ItemDefinition] = {}

    def register(self, definition: ItemDefinition) -> None:
        if definition.item_id in self._definitions:
            raise ValueError(f"Duplicate item id: {definition.item_id}")
        self._definitions[definition.item_id] = definition

    def replace(self, definition: ItemDefinition) -> None:
        """Replace a known definition while preserving its stable ID in every live instance."""
        if definition.item_id not in self._definitions:
            raise KeyError(f"Unknown item id: {definition.item_id}")
        self._definitions[definition.item_id] = definition
        self._placeholders.pop(definition.item_id, None)

    def get(self, item_id: str) -> ItemDefinition:
        return self._definitions[item_id]

    def find(self, item_id: str) -> ItemDefinition | None:
        return self._definitions.get(item_id)

    def resolve(self, item_id: str) -> ItemDefinition:
        """Return the definition, or an inert placeholder if the item is no longer defined.

        Lets a save keep items from content that was removed: they do nothing until it comes back.
        """
        definition = self._definitions.get(item_id)
        if definition is not None:
            return definition
        if item_id not in self._placeholders:
            self._placeholders[item_id] = ItemDefinition(item_id, "objeto desconocido", "un", UNKNOWN_CATEGORY)
        return self._placeholders[item_id]

    def ids(self) -> list[str]:
        return list(self._definitions)

    def load_mapping(
        self,
        data: dict[str, Any],
        source: str = "<data>",
        replace_existing: bool = False,
    ) -> ItemDefinition:
        required = {"id", "name", "article", "category"}
        missing = required - data.keys()
        if missing:
            raise ValueError(f"Missing fields in {source}: {sorted(missing)}")
        definition = ItemDefinition(
            item_id=str(data["id"]),
            name=str(data["name"]),
            article=str(data["article"]),
            category=str(data["category"]),
            base_value=int(data.get("base_value", 0)),
            description=str(data.get("description", "")),
            tags=tuple(str(tag) for tag in data.get("tags", [])),
            effects={str(k): float(v) for k, v in data.get("effects", {}).items()},
            properties={str(k): float(v) for k, v in data.get("properties", {}).items()},
        )
        if replace_existing:
            self.replace(definition)
        else:
            self.register(definition)
        return definition

    def load_json_file(self, path: Path) -> ItemDefinition:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError(f"Expected object in {path}")
        return self.load_mapping(data, str(path))

    def load_collection_json_file(self, path: Path) -> list[ItemDefinition]:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, list):
            raise ValueError(f"Expected list in {path}")
        definitions = []
        for index, item_data in enumerate(data):
            if not isinstance(item_data, dict):
                raise ValueError(f"Expected object at {path}[{index}]")
            definitions.append(self.load_mapping(item_data, f"{path}[{index}]"))
        return definitions
