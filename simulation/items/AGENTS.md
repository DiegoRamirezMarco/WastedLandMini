# Item System Rules
- Never branch gameplay logic on item display names.
- Use categories, tags, properties and effects.
- `ItemDefinition` describes a type; `ItemInstance` describes one concrete object.
- Built-in and custom items must use the same registry and validation path.
- Ownership, location and condition belong to instances, not definitions.
