from dataclasses import dataclass


@dataclass
class TheftAttempt:
    """One item taken from its owner's container. The world's record, whether or not anyone knows."""

    thief_id: str
    victim_id: str
    item_instance_id: str
    # True once anyone but the thief knows who did it.
    discovered: bool = False
    container_id: str = ""
    fact_id: str = ""
    # True once the victim has seen that the item is gone.
    noticed: bool = False
    returned: bool = False
