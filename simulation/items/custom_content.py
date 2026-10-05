"""Loads item and food definitions from content packs. Everything in a pack is untrusted input."""

import json
import logging
import re
from numbers import Real
from pathlib import Path
from typing import Any

from simulation.items.registry import ItemRegistry

logger = logging.getLogger(__name__)

ID_PATTERN = re.compile(r"^[a-z0-9]+(_[a-z0-9]+)*$")
DATA_FILE = "data.json"
MAX_DATA_BYTES = 64 * 1024
# Folder of a pack type, and the category its items must have (None for any).
FOLDERS: dict[str, str | None] = {"items": None, "foods": "food"}


def validate_item_data(data: Any, folder_name: str, required_category: str | None) -> None:
    """Raise ValueError unless `data` is a well-formed item definition for that folder.

    Unknown extra fields are allowed, so packs made for a newer version still load.
    """
    if not isinstance(data, dict):
        raise ValueError("data.json must hold an object")
    for name in ("id", "name", "article", "category"):
        if not isinstance(data.get(name), str) or not data[name].strip():
            raise ValueError(f"'{name}' must be a non-empty string")
    if not ID_PATTERN.match(data["id"]):
        raise ValueError("'id' must be lowercase letters, digits and single underscores")
    if data["id"] != folder_name:
        raise ValueError(f"'id' must match its folder name '{folder_name}'")
    if required_category is not None and data["category"] != required_category:
        raise ValueError(f"'category' must be '{required_category}' in this folder")
    if not _is_number(data.get("base_value", 0)) or data.get("base_value", 0) < 0:
        raise ValueError("'base_value' must be a number that is not negative")
    if not isinstance(data.get("description", ""), str):
        raise ValueError("'description' must be a string")
    tags = data.get("tags", [])
    if not isinstance(tags, list) or not all(isinstance(tag, str) for tag in tags):
        raise ValueError("'tags' must be a list of strings")
    for field_name in ("effects", "properties"):
        numbers = data.get(field_name, {})
        if not isinstance(numbers, dict) or not all(
            isinstance(name, str) and _is_number(value) for name, value in numbers.items()
        ):
            raise ValueError(f"'{field_name}' must map names to numbers")


def _is_number(value: Any) -> bool:
    return isinstance(value, Real) and not isinstance(value, bool)


def load_custom_items(registry: ItemRegistry, root: Path) -> list[str]:
    """Register every valid item under `root`. Returns the IDs that loaded.

    A pack that is malformed, or that reuses an ID already taken, is skipped with a warning
    and never stops the game from starting.
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
                validate_item_data(data, pack.name, required_category)
                registry.load_mapping(data, str(path))
            except (OSError, ValueError) as error:
                logger.warning("Skipped custom content %s/%s: %s", folder, pack.name, error)
                continue
            loaded.append(str(data["id"]))
    return loaded
