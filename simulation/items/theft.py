from dataclasses import dataclass

STEAL_MINUTES = 2
# How much someone has to want a thing that is not theirs before they take it.
THEFT_THRESHOLD = 0.15
THEFT_COOLDOWN_MINUTES = 1440
THEFT_IMPORTANCE = 45
# What a theft is recorded against when it was the settlement as a whole that was stolen from.
# No resident can have it for an ID.
FUND_VICTIM = "@fund"


@dataclass
class TheftAttempt:
    """One thing taken from whoever it belonged to. The world's record, whether or not anyone knows.

    It is an item out of its owner's container, a sum of credit from someone who was not
    looking, or either of them out of what the settlement holds in common.
    """

    thief_id: str
    # The resident it was taken from, or `FUND_VICTIM`.
    victim_id: str
    # The item taken. Empty when it was credit.
    item_instance_id: str
    # True once anyone but the thief knows who did it.
    discovered: bool = False
    # Where it was taken: the container, the counter, or the bed of whoever was asleep.
    container_id: str = ""
    fact_id: str = ""
    # True once the victim, or whoever keeps the counter, has seen that it is gone.
    noticed: bool = False
    returned: bool = False
    # The credit taken. Nothing when it was an item.
    amount: float = 0.0
