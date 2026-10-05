from dataclasses import dataclass, field

from world.map import Tile

MOVE_TILES_PER_MINUTE = 2
# Strolling to a random spot and standing there: what residents do when nothing presses.
WANDER_ACTION = "wander"


@dataclass
class Activity:
    """What a resident is doing: walking `path`, then spending `minutes_left` at the end of it.

    `target_id` names the object being used, `partner_id` the resident being talked to.
    `intent` is the exchange a resident has made up their mind to have with that partner.
    `item_id` is the item involved: the kind of food while eating from a container, otherwise
    the one item instance being used or taken.
    """

    action: str
    target_id: str | None = None
    path: list[Tile] = field(default_factory=list)
    minutes_left: int = 0
    using: bool = False
    partner_id: str | None = None
    intent: str | None = None
    item_id: str | None = None
