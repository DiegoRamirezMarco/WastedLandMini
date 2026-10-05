from dataclasses import dataclass, field

# A thing in worse condition than this is worth taking to be repaired.
WORN_CONDITION = 50.0


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

    @property
    def broken(self) -> bool:
        """Worn right out. A broken thing does nothing until it is repaired."""
        return self.condition <= 0.0
