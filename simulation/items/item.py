from dataclasses import dataclass, field


@dataclass(frozen=True)
class ItemDefinition:
    item_id: str
    name: str
    article: str
    category: str
    base_value: int = 0
    description: str = ""
    tags: tuple[str, ...] = ()
    effects: dict[str, float] = field(default_factory=dict)
    # Other numbers about the item, such as `damage` for a weapon.
    properties: dict[str, float] = field(default_factory=dict)


@dataclass
class ItemInstance:
    instance_id: str
    definition_id: str
    owner_id: str | None = None
    condition: float = 100.0
    quantity: int = 1
