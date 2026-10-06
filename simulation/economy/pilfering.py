"""Stealing what is not a thing in somebody's crate: credit, and what the settlement holds in common.

Credit is a figure and not coins in a pocket, but it is taken as a thing is: by whoever dares,
from someone who is not looking, seen or not by whoever is near. The fund is taken from at the
counter where its takings are kept, in coin, or under barter in what is on the shelf. It is the
same leaning that has someone steal from a neighbour, and it is found out the same way. Coin
tempts whoever is short of it: nobody with plenty put by takes a little more.
"""

from typing import TYPE_CHECKING

from simulation.ai.navigation import path_beside
from simulation.ai.utility_ai import DISTANCE_COST, ScoredAction
from simulation.economy.fund_system import hand_over
from simulation.events.event import DomainEvent
from simulation.items.item import ItemInstance
from simulation.items.theft import (
    FUND_VICTIM,
    STEAL_MINUTES,
    THEFT_IMPORTANCE,
    THEFT_THRESHOLD,
    TheftAttempt,
)
from simulation.knowledge.knowledge_system import witnesses_of
from simulation.residents.activity import Activity
from simulation.residents.resident import Resident
from world.pathfinding import manhattan

if TYPE_CHECKING:
    from simulation.world import SimulationWorld

# Taking credit from someone who is not looking.
PILFER_ACTION = "pilfer"
# Taking from what the settlement holds in common, at the counter.
FUND_THEFT_ACTION = "steal_fund"
PILFERING_ACTIONS = (PILFER_ACTION, FUND_THEFT_ACTION)
# What a sum of credit is worth is weighed like a thing of that base value.
WORTH_SCALE = 50.0


def _sum_within_reach(world: "SimulationWorld", held: float) -> int:
    """The whole credits somebody would take at once out of what is held."""
    return int(min(held, world.registries.economy.pilfer_max))


def _want_of_coin(world: "SimulationWorld", thief: Resident) -> float:
    """How much more coin means to somebody, from 1 for whoever has none to 0 for whoever has plenty put by."""
    return 1.0 - min(1.0, max(0.0, thief.credits) / world.registries.economy.savings_scale)


def _pick(world: "SimulationWorld", thief: Resident, container_id: str) -> ItemInstance | None:
    """The thing on a counter, nobody's and in working order, that a thief would most like to have."""
    resolve = world.registries.items.resolve
    choices = [item for item in world.containers[container_id].items if item.owner_id is None and not item.broken]
    return max(
        choices,
        key=lambda item: (world.items.personal_value(world, thief, resolve(item.definition_id), item), item.instance_id),
        default=None,
    )


def candidates(world: "SimulationWorld", thief: Resident) -> list[ScoredAction]:
    """Credit and common goods a resident is tempted to take, where nobody would see them do it."""
    scored: list[ScoredAction] = []
    coin = world.fund.currency(world)
    if coin is not None:
        for victim in world.residents.values():
            bed = world.interactables.get(victim.activity.target_id or "") if victim.activity is not None else None
            if victim is thief or victim.away or world.is_aware(victim) or bed is None:
                continue
            amount = _sum_within_reach(world, victim.credits)
            worth = amount * _want_of_coin(world, thief)
            temptation = worth / WORTH_SCALE * world.items.leaning_to_steal(world, thief, victim)
            if amount < 1 or temptation < THEFT_THRESHOLD:
                continue
            if witnesses_of(world, victim.tile, exclude=[thief.resident_id]):
                continue
            score = temptation - DISTANCE_COST * manhattan(thief.tile, victim.tile)
            scored.append(ScoredAction(PILFER_ACTION, score, bed.object_id, item_id=victim.resident_id))
    counter_id = world.fund.counter(world)
    placed = world.interactables.get(counter_id or "")
    if counter_id is None or placed is None:
        return scored
    if coin is not None:
        worth, item_id = _sum_within_reach(world, world.trading.fund) * _want_of_coin(world, thief), None
    else:
        item = _pick(world, thief, counter_id)
        if item is None:
            return scored
        definition = world.registries.items.resolve(item.definition_id)
        worth, item_id = world.items.personal_value(world, thief, definition, item), item.instance_id
    temptation = worth / WORTH_SCALE * world.items.leaning_to_steal(world, thief, None)
    if worth < 1 or temptation < THEFT_THRESHOLD:
        return scored
    if witnesses_of(world, (placed.x, placed.y), exclude=[thief.resident_id]):
        return scored
    score = temptation - DISTANCE_COST * manhattan(thief.tile, (placed.x, placed.y))
    scored.append(ScoredAction(FUND_THEFT_ACTION, score, counter_id, item_id=item_id))
    return scored


def plan(world: "SimulationWorld", thief: Resident, candidate: ScoredAction) -> Activity | None:
    """The walk to whoever, or whatever, is to be taken from."""
    placed = world.interactables.get(candidate.target_id or "")
    path = path_beside(world, thief, placed) if placed is not None else None
    if path is None:
        return None
    return Activity(candidate.name, candidate.target_id, path, STEAL_MINUTES, item_id=candidate.item_id)


def begin(world: "SimulationWorld", thief: Resident, activity: Activity) -> bool:
    """Take what a resident walked over for. False if it is no longer there to be taken."""
    if activity.action == PILFER_ACTION:
        return _pilfer(world, thief, activity)
    return _raid_fund(world, thief, activity)


def _pilfer(world: "SimulationWorld", thief: Resident, activity: Activity) -> bool:
    coin = world.fund.currency(world)
    victim = world.residents.get(activity.item_id or "")
    if coin is None or victim is None or victim is thief or victim.away or world.is_aware(victim):
        return False
    amount = _sum_within_reach(world, victim.credits)
    if amount < 1:
        return False
    victim.credits -= amount
    thief.credits += amount
    sum_taken = coin.amount(amount)
    _record(
        world,
        thief,
        TheftAttempt(thief.resident_id, victim.resident_id, "", container_id=activity.target_id or "", amount=amount),
        f"{thief.name} le roba {sum_taken} a {victim.name}",
        f"{thief.name} le robó {sum_taken} a {victim.name}",
        [thief.resident_id, victim.resident_id],
    )
    return True


def _raid_fund(world: "SimulationWorld", thief: Resident, activity: Activity) -> bool:
    counter_id = activity.target_id or ""
    container = world.containers.get(counter_id)
    if container is None:
        return False
    coin = world.fund.currency(world)
    if coin is not None:
        amount = world.fund.pay_out(world, _sum_within_reach(world, world.trading.fund))
        if amount < 1:
            world.fund.pay_in(world, amount)
            return False
        thief.credits += amount
        attempt = TheftAttempt(thief.resident_id, FUND_VICTIM, "", container_id=counter_id, amount=amount)
        taken = coin.amount(amount)
    else:
        item = container.find(activity.item_id or "")
        if item is None or item.owner_id is not None:
            return False
        definition = world.registries.items.resolve(item.definition_id)
        # It is theirs now, as far as they are concerned: nobody's would be put away as a find.
        mine = hand_over(world, container, item, thief.inventory, thief.resident_id)
        attempt = TheftAttempt(thief.resident_id, FUND_VICTIM, mine.instance_id, container_id=counter_id)
        taken = f"{definition.article} {definition.name}"
    _record(
        world,
        thief,
        attempt,
        f"{thief.name} se lleva {taken} de lo que es de todos",
        f"{thief.name} se llevó {taken} de lo que es de todos",
        [thief.resident_id],
    )
    return True


def _record(
    world: "SimulationWorld", thief: Resident, attempt: TheftAttempt, text: str, fact_text: str, subjects: list[str]
) -> None:
    """Put a theft on record and let whoever saw it know who did it."""
    world.thefts.append(attempt)
    world.theft_cooldowns[thief.resident_id] = world.clock.total_minutes
    room = world.room_at(thief.tile)
    event = DomainEvent(
        "theft_committed",
        THEFT_IMPORTANCE,
        text,
        [thief.resident_id],
        location_id=room.room_id if room is not None else None,
        data={"victim_id": attempt.victim_id, "amount": attempt.amount},
    )
    fact = world.emit_event(event, at=thief.tile, fact_text=fact_text, subjects=subjects)
    attempt.fact_id = fact.fact_id if fact is not None else ""
    attempt.discovered = bool(event.witnesses)


def keeps_counter(world: "SimulationWorld", resident: Resident, container_id: str) -> bool:
    """Whether it falls to a resident to see what a counter has and has not got: it is their job to keep it."""
    placed = world.interactables.get(container_id)
    use = world.definition_of(placed).use if placed is not None else None
    return use is not None and (use.staffed_by is None or use.staffed_by == resident.job_id)
