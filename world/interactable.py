from dataclasses import dataclass, field
from typing import Any

from world.build import BuildRule, build_rule_from_data
from world.map import Tile

USE_POSITIONS = ("adjacent", "on")
URBANISM_CATEGORIES = ("furniture", "decor")


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
    # Tag of the item that care uses up, the kind of container it is taken from, and how many minutes
    # one unit goes on working in whoever was given it. With none left, lying here is only rest.
    care_item: str | None = None
    care_from: str | None = None
    dose_minutes: int = 0
    # Credits it costs to use.
    price: int = 0
    # Whether the use is buying one of the things kept inside, at that thing's price.
    sells: bool = False
    # Condition restored per minute to a worn thing the resident brings. 0 for a use that mends nothing.
    repairs: float = 0.0
    # Tag of the item a repair uses one unit of, and the kind of container it is taken from. None for
    # repairs that need nothing but work.
    material: str | None = None
    material_from: str | None = None
    # Whether this is listening to a radio, which gives word of what is on its way from outside.
    radio: bool = False
    # What it is called for short, where using this is offered by name. Empty for none of its own.
    label: str = ""


@dataclass(frozen=True)
class SalvageRule:
    """What taking an object apart gives, and how long it takes one pair of hands."""

    item: str
    units: int
    minutes: int


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
    # Kind of container whose contents this object shows off, as a shop's shelves show its stock.
    display_of: str | None = None
    # How many tiles around it this object lights after dark. 0 for something that gives no light.
    light: int = 0
    # Where this kind appears in the urbanism catalogue. This is presentation metadata stored
    # with the domain definition so built-in and custom objects follow the same rules.
    urbanism_category: str = "furniture"
    # What putting one up takes. None for something that is simply put down.
    build: BuildRule | None = None
    # What taking one apart gives. None for something nobody takes apart.
    salvage: SalvageRule | None = None
    # Whether it is something to sit on: whoever is at something done sitting down, on the
    # tile it stands on, sits on it and not on the ground.
    seat: bool = False
    # How fast a post of this kind is worked, against any other of the same job: a well is
    # slower than a tank with its pump (S55).
    post_pace: float = 1.0
    # For a store (S53): how many units of each resource it holds. None for what is no store.
    store: dict[str, int] | None = None
    # For a place what a store holds is taken from and brought to: how many units of each
    # kind of thing of a resource it keeps at hand. The rest is the store's. None for what
    # has nothing to do with a store.
    outlet: dict[str, int] | None = None


@dataclass
class Interactable:
    object_id: str
    kind: str
    x: int
    y: int
    # How good it is, from 1: the place of its rarity among those there are (S54).
    level: int = 1

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
    definition = InteractableDefinition(
        kind=kind,
        name=str(data["name"]),
        article=str(data["article"]),
        width=int(data.get("width", 1)),
        height=int(data.get("height", 1)),
        blocks=bool(data.get("blocks", True)),
        container=bool(data.get("container", False)),
        use=_use_from_data(kind, data["use"]) if data.get("use") is not None else None,
        display_of=str(data["display_of"]) if data.get("display_of") is not None else None,
        light=int(data.get("light", 0)),
        urbanism_category=str(data.get("category", "furniture")),
        build=build_rule_from_data(f"interactable {kind}", data.get("build")),
        salvage=_salvage_from_data(kind, data.get("salvage")),
        seat=bool(data.get("seat", False)),
        post_pace=float(data.get("post_pace", 1.0)),
        store=_units_from_data(kind, "store", data.get("store")),
        outlet=_units_from_data(kind, "outlet", data.get("outlet")),
    )
    if (definition.store is not None or definition.outlet is not None) and not definition.container:
        raise ValueError(f"Interactable {kind} holds what a store keeps, so it must be a container")
    if definition.store is not None and (not definition.store or definition.outlet is not None):
        raise ValueError(f"Interactable {kind} is a store: it holds something, and is taken from through others")
    if definition.seat and (definition.blocks or definition.width * definition.height != 1):
        raise ValueError(f"Interactable {kind} is a seat, so it takes up one tile and can be stood on")
    if definition.post_pace <= 0:
        raise ValueError(f"Interactable {kind} is worked at a pace above nothing")
    if definition.light < 0:
        raise ValueError(f"Interactable {kind} gives a negative amount of light")
    if definition.urbanism_category not in URBANISM_CATEGORIES:
        raise ValueError(
            f"Unknown urbanism category for interactable {kind}: {definition.urbanism_category}"
        )
    if definition.use is not None and definition.use.sells and not definition.container:
        raise ValueError(f"Interactable {kind} sells things, so it must be a container")
    return definition


def _units_from_data(kind: str, what: str, data: Any) -> dict[str, int] | None:
    """So many units of each resource, as a store holds or a place keeps at hand."""
    if data is None:
        return None
    if not isinstance(data, dict):
        raise ValueError(f"'{what}' of interactable {kind} must give units by resource")
    units = {str(resource_id): int(count) for resource_id, count in data.items()}
    if any(count < 0 for count in units.values()):
        raise ValueError(f"'{what}' of interactable {kind} gives a negative number of units")
    return units


def _salvage_from_data(kind: str, data: Any) -> SalvageRule | None:
    if data is None:
        return None
    if not isinstance(data, dict) or "item" not in data:
        raise ValueError(f"'salvage' of interactable {kind} must say what item it gives")
    rule = SalvageRule(str(data["item"]), int(data.get("units", 1)), int(data.get("minutes", 60)))
    if rule.units < 1 or rule.minutes < 1:
        raise ValueError(f"'salvage' of interactable {kind} must give a unit or more and take a minute or more")
    return rule


def _use_from_data(kind: str, data: dict[str, Any]) -> UseDefinition:
    missing = {"action", "text", "minutes"} - data.keys()
    if missing:
        raise ValueError(f"Missing fields in use of interactable {kind}: {sorted(missing)}")
    position = str(data.get("position", "adjacent"))
    if position not in USE_POSITIONS:
        raise ValueError(f"Unknown use position for interactable {kind}: {position}")
    hours = data.get("preferred_hours")
    price, repairs = int(data.get("price", 0)), float(data.get("repairs", 0.0))
    if price < 0 or repairs < 0:
        raise ValueError(f"Use of interactable {kind} has a negative price or repair rate")
    if data.get("care_item") is not None and int(data.get("dose_minutes", 0)) < 1:
        raise ValueError(f"Use of interactable {kind} gives care with an item, so a dose must last a minute or more")
    return UseDefinition(
        action=str(data["action"]),
        text=str(data["text"]),
        minutes=int(data["minutes"]),
        per_minute={str(need): float(delta) for need, delta in data.get("per_minute", {}).items()},
        item_id=str(data["item"]) if data.get("item") is not None else None,
        consumes=str(data["consumes"]) if data.get("consumes") is not None else None,
        position=position,
        capacity=int(data.get("capacity", 1)),
        preferred_hours=(int(hours[0]), int(hours[1])) if hours else None,
        interruptible=bool(data.get("interruptible", False)),
        unaware=bool(data.get("unaware", False)),
        until=str(data["until"]) if data.get("until") is not None else None,
        staffed_by=str(data["staffed_by"]) if data.get("staffed_by") is not None else None,
        heals=bool(data.get("heals", False)),
        care_job=str(data["care_job"]) if data.get("care_job") is not None else None,
        care_item=str(data["care_item"]) if data.get("care_item") is not None else None,
        care_from=str(data["care_from"]) if data.get("care_from") is not None else None,
        dose_minutes=int(data.get("dose_minutes", 0)),
        price=price,
        sells=bool(data.get("sells", False)),
        repairs=repairs,
        material=str(data["material"]) if data.get("material") is not None else None,
        material_from=str(data["material_from"]) if data.get("material_from") is not None else None,
        radio=bool(data.get("radio", False)),
        label=str(data.get("label", "")),
    )
