"""Loads data patches for furniture and other object kinds placed on maps."""

import json
import logging
import re
from numbers import Real
from pathlib import Path
from typing import Any, Protocol

from world.interactable import InteractableDefinition, UseDefinition, interactable_definition_from_data
from world.urbanism import BuildingDefinition, building_definition_from_data

logger = logging.getLogger(__name__)

ID_PATTERN = re.compile(r"^[a-z0-9]+(_[a-z0-9]+)*$")
OBJECTS_FOLDER = "objects"
BUILDINGS_FOLDER = "buildings"
DATA_FILE = "data.json"
MAX_DATA_BYTES = 64 * 1024


class InteractableRegistryLike(Protocol):
    def find(self, kind: str) -> InteractableDefinition | None: ...

    def register(self, definition: InteractableDefinition) -> None: ...

    def replace(self, definition: InteractableDefinition) -> None: ...


def _use_data(use: UseDefinition) -> dict[str, Any]:
    return {
        "action": use.action,
        "text": use.text,
        "minutes": use.minutes,
        "per_minute": dict(use.per_minute),
        "item": use.item_id,
        "consumes": use.consumes,
        "position": use.position,
        "capacity": use.capacity,
        "preferred_hours": list(use.preferred_hours) if use.preferred_hours is not None else None,
        "interruptible": use.interruptible,
        "unaware": use.unaware,
        "until": use.until,
        "staffed_by": use.staffed_by,
        "heals": use.heals,
        "care_job": use.care_job,
        "price": use.price,
        "sells": use.sells,
        "repairs": use.repairs,
        "material": use.material,
        "material_from": use.material_from,
        "radio": use.radio,
    }


def _definition_data(definition: InteractableDefinition) -> dict[str, Any]:
    return {
        "id": definition.kind,
        "name": definition.name,
        "article": definition.article,
        "width": definition.width,
        "height": definition.height,
        "blocks": definition.blocks,
        "container": definition.container,
        "use": _use_data(definition.use) if definition.use is not None else None,
        "display_of": definition.display_of,
        "light": definition.light,
        "category": definition.urbanism_category,
    }


def merged_interactable_data(
    data: Any,
    base: InteractableDefinition | None = None,
) -> dict[str, Any]:
    """Complete object data, recursively patching an existing use when there is one."""
    if not isinstance(data, dict):
        raise ValueError("data.json must hold an object")
    merged = (
        _definition_data(base)
        if base is not None
        else {
            "width": 1,
            "height": 1,
            "blocks": True,
            "container": False,
            "use": None,
            "display_of": None,
            "light": 0,
            "category": "furniture",
        }
    )
    patch = dict(data)
    if isinstance(merged.get("use"), dict) and isinstance(patch.get("use"), dict):
        patch["use"] = {**merged["use"], **patch["use"]}
    merged.update(patch)
    return merged


def _is_number(value: Any) -> bool:
    return isinstance(value, Real) and not isinstance(value, bool)


def _positive_int(
    data: dict[str, Any],
    name: str,
    minimum: int = 1,
    default: int | None = None,
) -> None:
    value = data.get(name, default)
    if not isinstance(value, int) or isinstance(value, bool) or value < minimum:
        raise ValueError(f"'{name}' must be an integer of at least {minimum}")


def validate_interactable_data(
    data: Any,
    folder_name: str,
    base: InteractableDefinition | None = None,
) -> None:
    """Validate a new object definition or a partial patch of an existing kind."""
    merged = merged_interactable_data(data, base)
    if not isinstance(data.get("id"), str) or not data["id"].strip():
        raise ValueError("'id' must be a non-empty string")
    if not ID_PATTERN.match(data["id"]):
        raise ValueError("'id' must be lowercase letters, digits and single underscores")
    if data["id"] != folder_name:
        raise ValueError(f"'id' must match its folder name '{folder_name}'")
    for name in ("name", "article"):
        if not isinstance(merged.get(name), str) or not merged[name].strip():
            raise ValueError(f"'{name}' must be a non-empty string")
    _positive_int(merged, "width")
    _positive_int(merged, "height")
    for name in ("blocks", "container"):
        if not isinstance(merged.get(name), bool):
            raise ValueError(f"'{name}' must be true or false")
    light = merged.get("light")
    if not isinstance(light, int) or isinstance(light, bool) or light < 0:
        raise ValueError("'light' must be a non-negative integer")
    if merged.get("display_of") is not None and not isinstance(merged["display_of"], str):
        raise ValueError("'display_of' must be a string or null")
    if merged.get("category") not in ("furniture", "decor"):
        raise ValueError("'category' must be 'furniture' or 'decor'")

    use = merged.get("use")
    if use is None:
        return
    if not isinstance(use, dict):
        raise ValueError("'use' must be an object or null")
    for name in ("action", "text"):
        if not isinstance(use.get(name), str) or not use[name].strip():
            raise ValueError(f"use '{name}' must be a non-empty string")
    _positive_int(use, "minutes")
    _positive_int(use, "capacity", default=1)
    per_minute = use.get("per_minute", {})
    if not isinstance(per_minute, dict) or not all(
        isinstance(name, str) and _is_number(value) for name, value in per_minute.items()
    ):
        raise ValueError("use 'per_minute' must map names to numbers")
    for name in ("item", "consumes", "until", "staffed_by", "care_job", "material", "material_from"):
        if use.get(name) is not None and not isinstance(use[name], str):
            raise ValueError(f"use '{name}' must be a string or null")
    for name in ("interruptible", "unaware", "heals", "sells", "radio"):
        if not isinstance(use.get(name, False), bool):
            raise ValueError(f"use '{name}' must be true or false")
    hours = use.get("preferred_hours")
    if hours is not None and (
        not isinstance(hours, (list, tuple))
        or len(hours) != 2
        or any(not isinstance(hour, int) or isinstance(hour, bool) for hour in hours)
    ):
        raise ValueError("use 'preferred_hours' must be two integer hours or null")
    if not isinstance(use.get("price", 0), int) or isinstance(use.get("price", 0), bool) or use.get("price", 0) < 0:
        raise ValueError("use 'price' must be a non-negative integer")
    if not _is_number(use.get("repairs", 0)) or use.get("repairs", 0) < 0:
        raise ValueError("use 'repairs' must be a non-negative number")

    # The domain constructor performs the remaining coupled checks, such as a seller being a container.
    interactable_definition_from_data(folder_name, {key: value for key, value in merged.items() if key != "id"})


def load_custom_interactables(registry: InteractableRegistryLike, root: Path) -> list[str]:
    """Register valid object packs and patch built-in kinds with matching stable IDs."""
    base = root / OBJECTS_FOLDER
    if not base.is_dir():
        return []
    loaded: list[str] = []
    for pack in sorted(child for child in base.iterdir() if child.is_dir()):
        path = pack / DATA_FILE
        try:
            if not path.is_file() or path.is_symlink():
                raise ValueError(f"no {DATA_FILE}")
            if path.stat().st_size > MAX_DATA_BYTES:
                raise ValueError(f"{DATA_FILE} is too large")
            data = json.loads(path.read_text(encoding="utf-8"))
            current = registry.find(pack.name)
            validate_interactable_data(data, pack.name, current)
            complete = merged_interactable_data(data, current)
            definition = interactable_definition_from_data(
                pack.name,
                {key: value for key, value in complete.items() if key != "id"},
            )
            if current is None:
                registry.register(definition)
            else:
                registry.replace(definition)
        except (OSError, ValueError) as error:
            logger.warning("Skipped custom content objects/%s: %s", pack.name, error)
            continue
        loaded.append(pack.name)
    return loaded


def load_custom_buildings(
    definitions: dict[str, BuildingDefinition], root: Path
) -> list[str]:
    """Load building definitions from the same packs that may contain their custom artwork."""
    base = root / BUILDINGS_FOLDER
    if not base.is_dir():
        return []
    loaded: list[str] = []
    for pack in sorted(child for child in base.iterdir() if child.is_dir()):
        path = pack / DATA_FILE
        try:
            if not path.is_file() or path.is_symlink():
                # Artwork-only folders remain valid and simply add no catalogue definition.
                continue
            if path.stat().st_size > MAX_DATA_BYTES:
                raise ValueError(f"{DATA_FILE} is too large")
            data = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                raise ValueError("data.json must hold an object")
            definition_id = str(data.get("id", pack.name))
            if definition_id != pack.name or not ID_PATTERN.match(definition_id):
                raise ValueError("'id' must match its lowercase folder name")
            definition = building_definition_from_data(definition_id, data)
            definitions[definition_id] = definition
        except (OSError, ValueError) as error:
            logger.warning("Skipped custom content buildings/%s: %s", pack.name, error)
            continue
        loaded.append(pack.name)
    return loaded
