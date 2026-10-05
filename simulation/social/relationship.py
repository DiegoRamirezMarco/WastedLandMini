from dataclasses import dataclass

FEELINGS = ("affection", "trust", "attraction", "fear", "resentment")
# Feelings that can be negative. The rest run from 0 to 100.
SIGNED_FEELINGS = ("affection", "trust")


@dataclass
class Relationship:
    """What `source_id` feels about `target_id`. The reverse direction is a separate object."""

    source_id: str
    target_id: str
    affection: float = 0.0
    trust: float = 0.0
    attraction: float = 0.0
    fear: float = 0.0
    resentment: float = 0.0
    # Game minute of the last argument with this person, as the source remembers it.
    last_argued: int | None = None

    def adjust(self, feeling: str, delta: float) -> None:
        if feeling not in FEELINGS:
            raise ValueError(f"Unknown feeling: {feeling}")
        lowest = -100.0 if feeling in SIGNED_FEELINGS else 0.0
        setattr(self, feeling, max(lowest, min(100.0, getattr(self, feeling) + delta)))
