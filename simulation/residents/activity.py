from dataclasses import dataclass, field

from world.map import Tile

MOVE_TILES_PER_MINUTE = 2
# Strolling to a random spot and standing there: what residents do when nothing presses.
WANDER_ACTION = "wander"
# Waiting under a roof for bad weather to pass.
SHELTER_ACTION = "shelter"
# Getting indoors because a law says so, being where a law says everybody is to be, and
# walking out of the settlement for good.
RETIRE_ACTION = "retire"
ATTEND_ACTION = "attend"
LEAVE_ACTION = "leave"
# Standing where they were stopped, listening for what the player has to say.
HEED_ACTION = "heed"
# Being where a sentence is served: locked up, or in the stocks.
SERVE_ACTION = "serve_sentence"
# What a resident who knows of something makes up their mind about: whether to accuse. And
# what whoever is at the gate decides when somebody who was exiled asks to come back.
ACCUSE_DECISION = "accuse"
EXILE_BACK_DECISION = "exile_back"


@dataclass
class Activity:
    """What a resident is doing: walking `path`, then spending `minutes_left` at the end of it.

    `target_id` names the object being used, `partner_id` the resident being talked to.
    `intent` is the exchange a resident has made up their mind to have with that partner.
    `item_id` is the item involved: the kind of food while eating from a container, otherwise
    the one item instance being used or taken. `held_up` is how many minutes running they have
    not got a step further along `path`, for somebody being in the way.
    """

    action: str
    target_id: str | None = None
    path: list[Tile] = field(default_factory=list)
    minutes_left: int = 0
    using: bool = False
    partner_id: str | None = None
    intent: str | None = None
    item_id: str | None = None
    held_up: int = 0
