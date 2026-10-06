"""Loads item and food definitions from content packs. Everything in a pack is untrusted input."""

import json
import logging
import re
from numbers import Real
from pathlib import Path
from typing import Any

from simulation.substances.substance import substance_from_data
from simulation.items.item import ItemDefinition, taste_tags
from simulation.items.registry import ItemRegistry

logger = logging.getLogger(__name__)

ID_PATTERN = re.compile(r"^[a-z0-9]+(_[a-z0-9]+)*$")
DATA_FILE = "data.json"
MAX_DATA_BYTES = 64 * 1024
# Folder of a pack type, and the category its items must have (None for any).
FOLDERS: dict[str, str | None] = {"items": None, "foods": "food"}


def _definition_data(definition: ItemDefinition) -> dict[str, Any]:
    """Editable data of a definition, ready for a custom patch to be laid over it."""
    return {
        "id": definition.item_id,
        "name": definition.name,
        "article": definition.article,
        "category": definition.category,
        "base_value": definition.base_value,
        "description": definition.description,
        "tags": list(definition.tags),
        "effects": dict(definition.effects),
        "properties": dict(definition.properties),
        "preference_tags": list(definition.preference_tags),
    }


def merged_item_data(data: Any, base: ItemDefinition | None = None) -> dict[str, Any]:
    """Return a complete definition from new data or a partial patch of an existing item."""
    if not isinstance(data, dict):
        raise ValueError("data.json must hold an object")
    merged = _definition_data(base) if base is not None else {}
    merged.update(data)
    return merged


def validate_item_data(
    data: Any,
    folder_name: str,
    required_category: str | None,
    base: ItemDefinition | None = None,
) -> None:
    """Raise ValueError unless `data` is a well-formed item definition for that folder.

    Unknown extra fields are allowed, so packs made for a newer version still load.
    """
    merged = merged_item_data(data, base)
    # Even a patch names its stable ID explicitly. This catches a copied folder whose data still
    # points at another item instead of silently editing the wrong definition.
    if not isinstance(data.get("id"), str) or not data["id"].strip():
        raise ValueError("'id' must be a non-empty string")
    for name in ("id", "name", "article", "category"):
        if not isinstance(merged.get(name), str) or not merged[name].strip():
            raise ValueError(f"'{name}' must be a non-empty string")
    if not ID_PATTERN.match(merged["id"]):
        raise ValueError("'id' must be lowercase letters, digits and single underscores")
    if merged["id"] != folder_name:
        raise ValueError(f"'id' must match its folder name '{folder_name}'")
    if required_category is not None and merged["category"] != required_category:
        raise ValueError(f"'category' must be '{required_category}' in this folder")
    if not _is_number(merged.get("base_value", 0)) or merged.get("base_value", 0) < 0:
        raise ValueError("'base_value' must be a number that is not negative")
    if not isinstance(merged.get("description", ""), str):
        raise ValueError("'description' must be a string")
    tags = merged.get("tags", [])
    if not isinstance(tags, list) or not all(isinstance(tag, str) for tag in tags):
        raise ValueError("'tags' must be a list of strings")
    taste_tags(merged.get("preference_tags", []))
    for field_name in ("effects", "properties"):
        numbers = merged.get(field_name, {})
        if not isinstance(numbers, dict) or not all(
            isinstance(name, str) and _is_number(value) for name, value in numbers.items()
        ):
            raise ValueError(f"'{field_name}' must map names to numbers")
    if merged.get("substance") is not None:
        substance_from_data("the item", merged["substance"])


def _is_number(value: Any) -> bool:
    return isinstance(value, Real) and not isinstance(value, bool)


def load_custom_items(registry: ItemRegistry, root: Path) -> list[str]:
    """Register every valid item under `root`. Returns the IDs that loaded.

    A malformed pack, or a second pack for the same ID, is skipped with a warning and never
    stops the game from starting. A first pack may patch a built-in definition with the same ID.
    """
    loaded: list[str] = []
    for folder, required_category in FOLDERS.items():
        base = root / folder
        if not base.is_dir():
            continue
        for pack in sorted(child for child in base.iterdir() if child.is_dir()):
            path = pack / DATA_FILE
            try:
                if not path.is_file() or path.is_symlink():
                    raise ValueError(f"no {DATA_FILE}")
                if path.stat().st_size > MAX_DATA_BYTES:
                    raise ValueError(f"{DATA_FILE} is too large")
                data = json.loads(path.read_text(encoding="utf-8"))
                if pack.name in loaded:
                    raise ValueError(f"item id already modified by another pack: {pack.name}")
                base = registry.find(pack.name)
                validate_item_data(data, pack.name, required_category, base)
                complete = merged_item_data(data, base)
                registry.load_mapping(complete, str(path), replace_existing=base is not None)
            except (OSError, ValueError) as error:
                logger.warning("Skipped custom content %s/%s: %s", folder, pack.name, error)
                continue
            loaded.append(str(data["id"]))
    return loaded
