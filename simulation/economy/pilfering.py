"""Stealing what is not a thing in somebody's crate: credit, and what the settlement holds in common.

Credit is a figure and not coins in a pocket, but it is taken as a thing is: by whoever dares,
from someone who is not looking, seen or not by whoever is near. The fund is taken from where
its takings are kept, in coin, or under barter in what is on the shelf. It is the same leaning
that has someone steal from a neighbour, and it is found out the same way. Coin tempts whoever
is short of it, and whoever is that way inclined whatever they have.

Whoever the settlement no longer keeps, and cannot pay, takes what they eat and drink without
leave once they are hungry or thirsty enough.
"""

from typing import TYPE_CHECKING

from simulation.ai.navigation import path_beside
from simulation.ai.utility_ai import DISTANCE_COST, ScoredAction
from simulation.economy.fund_system import hand_over
from simulation.economy.ledger import STOLEN
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
from simulation.residents.needs import BODILY_NEEDS
from simulation.residents.resident import Resident
from world.pathfinding import manhattan

if TYPE_CHECKING:
    from simulation.world import SimulationWorld

# Taking credit from someone who is not looking.
PILFER_ACTION = "pilfer"
# Taking from what the settlement holds in common, where it is kept.
FUND_THEFT_ACTION = "steal_fund"
# Taking a meal or a drink out of the commons without leave.
STEAL_FOOD_ACTION = "steal_food"
PILFERING_ACTIONS = (PILFER_ACTION, FUND_THEFT_ACTION, STEAL_FOOD_ACTION)
# What a sum of credit is worth is weighed like a thing of that base value.
WORTH_SCALE = 50.0
# How hungry or thirsty somebody has to be to help themselves, and to do it in front of anybody.
HUNGRY_ENOUGH = 75.0
DESPERATE = 92.0
FOOD_THEFT_IMPORTANCE = 30
FOOD_THEFT_MINUTES = 5


def _sum_within_reach(world: "SimulationWorld", held: float) -> int:
    """The whole credits somebody would take at once out of what is held."""
    return int(min(held, world.registries.economy.pilfer_max))


def _want_of_coin(world: "SimulationWorld", thief: Resident) -> float:
    """How much more coin means to somebody, from 1 for whoever has none to 0 for whoever has
    plenty put by. To whoever is given to thieving by nature it is always worth having."""
    if world.items.thieving(world, thief) > 0:
        return 1.0
    return 1.0 - min(1.0, max(0.0, thief.credits) / world.registries.economy.savings_scale)


def _pick(world: "SimulationWorld", thief: Resident, container_id: str) -> ItemInstance | None:
    """The thing where the fund is kept, nobody's and in working order, that a thief would most like to have."""
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
    till_id = world.fund.till(world)
    placed = world.interactables.get(till_id or "")
    if till_id is None or placed is None:
        return scored
    if coin is not None:
        worth, item_id = _sum_within_reach(world, world.trading.fund) * _want_of_coin(world, thief), None
    else:
        item = _pick(world, thief, till_id)
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
    scored.append(ScoredAction(FUND_THEFT_ACTION, score, till_id, item_id=item_id))
    return scored


def hunger_candidates(world: "SimulationWorld", resident: Resident) -> list[ScoredAction]:
    """Meals and drinks somebody the settlement no longer keeps would take without leave.

    They have to be hungry or thirsty enough, and unable to pay. They wait for nobody to be
    looking unless they are past caring.
    """
    if world.trade.supplied(world, resident):
        return []
    scored: list[ScoredAction] = []
    for placed in world.interactables.values():
        use = world.definition_of(placed).use
        if use is None or use.consumes is None:
            continue
        food = world.items.best_food(world, resident, placed.object_id, use.consumes)
        if food is None or world.trade.can_afford(world, resident, use, placed.object_id):
            continue
        effects = world.items.use_effects(world, resident, world.registries.items.resolve(food.definition_id))
        level = max(
            (getattr(resident.needs, need) for need in BODILY_NEEDS if effects.get(need, 0.0) < 0), default=0.0
        )
        if level < HUNGRY_ENOUGH:
            continue
        if level < DESPERATE and witnesses_of(world, (placed.x, placed.y), exclude=[resident.resident_id]):
            continue
        score = 1.0 + level / 100.0 - DISTANCE_COST * manhattan(resident.tile, (placed.x, placed.y))
        scored.append(ScoredAction(STEAL_FOOD_ACTION, score, placed.object_id))
    return scored


def plan(world: "SimulationWorld", thief: Resident, candidate: ScoredAction) -> Activity | None:
    """The walk to whoever, or whatever, is to be taken from."""
    placed = world.interactables.get(candidate.target_id or "")
    path = path_beside(world, thief, placed) if placed is not None else None
    if path is None:
        return None
    minutes = FOOD_THEFT_MINUTES if candidate.name == STEAL_FOOD_ACTION else STEAL_MINUTES
    return Activity(candidate.name, candidate.target_id, path, minutes, item_id=candidate.item_id)


def begin(world: "SimulationWorld", thief: Resident, activity: Activity) -> bool:
    """Take what a resident walked over for. False if it is no longer there to be taken."""
    if activity.action == PILFER_ACTION:
        return _pilfer(world, thief, activity)
    if activity.action == STEAL_FOOD_ACTION:
        return _help_themselves(world, thief, activity)
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
    till_id = activity.target_id or ""
    container = world.containers.get(till_id)
    if container is None:
        return False
    coin = world.fund.currency(world)
    if coin is not None:
        amount = world.fund.pay_out(world, _sum_within_reach(world, world.trading.fund))
        if amount < 1:
            world.fund.pay_in(world, amount)
            return False
        thief.credits += amount
        attempt = TheftAttempt(thief.resident_id, FUND_VICTIM, "", container_id=till_id, amount=amount)
        taken = coin.amount(amount)
    else:
        item = container.find(activity.item_id or "")
        if item is None or item.owner_id is not None:
            return False
        definition = world.registries.items.resolve(item.definition_id)
        # It is theirs now, as far as they are concerned: nobody's would be put away as a find.
        mine = hand_over(world, container, item, thief.inventory, thief.resident_id, STOLEN)
        attempt = TheftAttempt(thief.resident_id, FUND_VICTIM, mine.instance_id, container_id=till_id)
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


def _help_themselves(world: "SimulationWorld", thief: Resident, activity: Activity) -> bool:
    """Eat or drink out of the commons without leave. It is seen or it is not, and nobody keeps
    count of a meal: there is no record of it but what whoever saw it knows."""
    placed = world.interactables.get(activity.target_id or "")
    use = world.definition_of(placed).use if placed is not None else None
    if use is None or use.consumes is None or world.trade.supplied(world, thief):
        return False
    taken = world.items.take_food(world, thief, placed.object_id, use.consumes)
    if taken is None:
        return False
    definition = world.registries.items.resolve(taken)
    world.items.take_in(world, thief, definition)
    thing = f"{definition.article} {definition.name}"
    room = world.room_at(thief.tile)
    world.emit_event(
        DomainEvent(
            "theft_committed",
            FOOD_THEFT_IMPORTANCE,
            f"{thief.name}, a quien ya no se mantiene, coge {thing} sin permiso",
            [thief.resident_id],
            location_id=room.room_id if room is not None else None,
            data={"victim_id": FUND_VICTIM, "item_id": definition.item_id},
        ),
        at=thief.tile,
        fact_text=f"{thief.name} cogió {thing} de lo que es de todos sin permiso",
        subjects=[thief.resident_id],
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
    """Whether it falls to a resident to see what the till has and has not got: it is their job
    to keep that counter. A fund kept in a box is everybody's to look into."""
    placed = world.interactables.get(container_id)
    if placed is None:
        return False
    use = world.definition_of(placed).use
    return use is None or use.staffed_by is None or use.staffed_by == resident.job_id
