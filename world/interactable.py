from dataclasses import dataclass, field
from typing import Any

from world.map import Tile

USE_POSITIONS = ("adjacent", "on")


@dataclass(frozen=True)
class UseDefinition:
    """What a resident gets from using an object, and how."""

    action: str
    text: str
    minutes: int
    per_minute: dict[str, float] = field(default_factory=dict)
    item_id: str | None = None
    # Category of item the use takes one unit of from this object's own contents.
    consumes: str | None = None
    position: str = "adjacent"
    capacity: int = 1
    preferred_hours: tuple[int, int] | None = None
    # Whether someone using this can be drawn into a conversation.
    interruptible: bool = False
    # Whether someone using this notices nothing around them, as when asleep.
    unaware: bool = False
    # Need that ends the use early once it reaches zero. Without one, every need it lowers must.
    until: str | None = None
    # Job that must have someone on duty for this to be used at all, such as a bar.
    staffed_by: str | None = None
    # Whether lying here mends injuries, and the job whose worker makes it mend them faster.
    heals: bool = False
    care_job: str | None = None


@dataclass(frozen=True)
class InteractableDefinition:
    kind: str
    name: str
    article: str
    width: int = 1
    height: int = 1
    blocks: bool = True
    # Whether items can be kept inside.
    container: bool = False
    use: UseDefinition | None = None


@dataclass
class Interactable:
    object_id: str
    kind: str
    x: int
    y: int

    def footprint(self, definition: InteractableDefinition) -> list[Tile]:
        return [
            (self.x + dx, self.y + dy)
            for dy in range(definition.height)
            for dx in range(definition.width)
        ]


def interactable_definition_from_data(kind: str, data: dict[str, Any]) -> InteractableDefinition:
    missing = {"name", "article"} - data.keys()
    if missing:
        raise ValueError(f"Missing fields in interactable {kind}: {sorted(missing)}")
    return InteractableDefinition(
        kind=kind,
        name=str(data["name"]),
        article=str(data["article"]),
        width=int(data.get("width", 1)),
        height=int(data.get("height", 1)),
        blocks=bool(data.get("blocks", True)),
        container=bool(data.get("container", False)),
        use=_use_from_data(kind, data["use"]) if "use" in data else None,
    )


def _use_from_data(kind: str, data: dict[str, Any]) -> UseDefinition:
    missing = {"action", "text", "minutes"} - data.keys()
    if missing:
        raise ValueError(f"Missing fields in use of interactable {kind}: {sorted(missing)}")
    position = str(data.get("position", "adjacent"))
    if position not in USE_POSITIONS:
        raise ValueError(f"Unknown use position for interactable {kind}: {position}")
    hours = data.get("preferred_hours")
    return UseDefinition(
        action=str(data["action"]),
        text=str(data["text"]),
        minutes=int(data["minutes"]),
        per_minute={str(need): float(delta) for need, delta in data.get("per_minute", {}).items()},
        item_id=str(data["item"]) if "item" in data else None,
        consumes=str(data["consumes"]) if "consumes" in data else None,
        position=position,
        capacity=int(data.get("capacity", 1)),
        preferred_hours=(int(hours[0]), int(hours[1])) if hours else None,
        interruptible=bool(data.get("interruptible", False)),
        unaware=bool(data.get("unaware", False)),
        until=str(data["until"]) if "until" in data else None,
        staffed_by=str(data["staffed_by"]) if "staffed_by" in data else None,
        heals=bool(data.get("heals", False)),
        care_job=str(data["care_job"]) if "care_job" in data else None,
    )
