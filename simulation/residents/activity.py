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
# Standing in the square against a law in force, with the others who are (S45).
PROTEST_ACTION = "protest"
# Standing where they were stopped, listening for what the player has to say.
HEED_ACTION = "heed"
# Standing by with nothing of their own to do, for having been told to do nothing unasked (S50).
WAIT_ACTION = "await_orders"
# Being where a sentence is served: locked up, or in the stocks.
SERVE_ACTION = "serve_sentence"
# What a resident who knows of something makes up their mind about: whether to accuse. And
# what whoever is at the gate decides when somebody who was exiled asks to come back.
ACCUSE_DECISION = "accuse"
EXILE_BACK_DECISION = "exile_back"


@dataclass(frozen=True)
class Order:
    """Something the player has told a resident to do, and who or what it is about (S50)."""

    kind: str
    target_id: str | None = None


@dataclass
class Activity:
    """What a resident is doing: walking `path`, then spending `minutes_left` at the end of it.

    `target_id` names the object being used, `partner_id` the resident being talked to.
    `intent` is the exchange a resident has made up their mind to have with that partner.
    `item_id` is the item involved: the kind of food while eating from a container, otherwise
    the one item instance being used or taken. `held_up` is how many minutes running they have
    not got a step further along `path`, for somebody being in the way. `ordered` says that it
    is what the player told them to do, and not something of their own. `about` is the
    subject of a talk (S58) and `about_text` the words for it, `brought` says that it was
    this one who brought it up, and `began_at` is the game minute the exchange began.
    """

    action: str
    target_id: str | None = None
    path: list[Tile] = field(default_factory=list)
    minutes_left: int = 0
    using: bool = False
    partner_id: str | None = None
    intent: str | None = None
    item_id: str | None = None
    # How rare the unit of food being eaten was: it is gone from the shelf by then (S64).
    item_level: int = 1
    held_up: int = 0
    ordered: bool = False
    about: str = ""
    about_text: str = ""
    brought: bool = False
    began_at: int = 0
