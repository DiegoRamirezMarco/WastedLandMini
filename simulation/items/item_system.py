"""What residents do with things: eat them, use them, give them, swap them and steal them."""

from typing import TYPE_CHECKING

from simulation.ai.navigation import path_beside
from simulation.ai.utility_ai import DISTANCE_COST, ScoredAction, need_urgency
from simulation.economy import pilfering
from simulation.economy.ledger import ARRIVED, DRUNK, EATEN
from simulation.economy.pilfering import PILFERING_ACTIONS
from simulation.events.event import DomainEvent
from simulation.events.world_event_system import RADIO_TAG
from simulation.items.inventory import Inventory
from simulation.items.item import WORN_CONDITION, ItemDefinition, ItemInstance
from simulation.items.registry import UNKNOWN_CATEGORY
from simulation.items.theft import (
    FUND_VICTIM,
    STEAL_MINUTES,
    THEFT_COOLDOWN_MINUTES,
    THEFT_IMPORTANCE,
    THEFT_THRESHOLD,
    TheftAttempt,
)
from simulation.items.trading import TradeOffer
from simulation.knowledge.fact import SOURCE_PARTICIPANT
from simulation.knowledge.knowledge_system import learn, witnesses_of
from simulation.memory.memory import Memory
from simulation.residents.activity import Activity
from simulation.residents.needs import NEED_NAMES
from simulation.residents.resident import Resident
from simulation.tastes.settings import DISLIKED, DRUNK, EATEN, GIVEN, USED
from world.pathfinding import manhattan

if TYPE_CHECKING:
    from simulation.social.interaction import InteractionDefinition
    from simulation.world import SimulationWorld

USE_ITEM_ACTION = "use_item"
STEAL_ACTION = "steal"
ITEM_ACTIONS = (USE_ITEM_ACTION, STEAL_ACTION, *PILFERING_ACTIONS)
FOOD_CATEGORY = "food"
WATER_CATEGORY = "water"

USE_ITEM_MINUTES = 10
USE_ITEM_APPEAL = 0.8
NOTICE_IMPORTANCE = 40
NOTICE_STRESS = 8.0
RETURN_IMPORTANCE = 25
GIFT_IMPORTANCE = 20
GIFT_AFFECTION = 35.0
GIFT_MAX_GREED = 60.0
GIFT_CHANCE = 0.25
TRADE_IMPORTANCE = 15
NO_FOOD_IMPORTANCE = 40
NO_FOOD_NOTICE = "no_food"
NO_WATER_NOTICE = "no_water"
BROKEN_IMPORTANCE = 30
# The chance, from 0 to 1, that eating or drinking a thing makes whoever does it ill, as a property of the item.
SICKENS = "sickens"
SICKNESS = "sickness"
# The least of what a thing is worth new that is left in it, however worn.
WORN_FLOOR = 0.25
# What a trait may say of whoever has it: how much more given they are to taking what is not
# theirs, and whether they are fool enough to part with what they work with.
THIEVING = "thieving"
CARELESS = "careless"


def _named(definition: ItemDefinition) -> str:
    return f"{definition.article} {definition.name}"


class ItemSystem:
    # ----- what things are worth to someone -----

    def personal_value(
        self,
        world: "SimulationWorld",
        resident: Resident,
        definition: ItemDefinition,
        item: ItemInstance | None = None,
    ) -> float:
        """What an item is worth to this resident: its base value as their tastes, their needs
        and its scarcity make it. With `item`, one in particular, which may be a keepsake."""
        return world.tastes.worth(world, resident, definition, item)

    def condition_share(self, world: "SimulationWorld", item: ItemInstance) -> float:
        """How much of what a thing is worth new is left in it, for how worn it is. All of it, for
        what does not wear."""
        if world.registries.items.resolve(item.definition_id).properties.get("wear", 0.0) <= 0:
            return 1.0
        return max(WORN_FLOOR, min(1.0, item.condition / 100.0))

    def thieving(self, world: "SimulationWorld", resident: Resident) -> float:
        """How much more given to taking what is not theirs a resident is, for the traits they have."""
        traits = (world.registries.traits.find(trait_id) or {} for trait_id in resident.traits)
        return sum(float(trait.get(THIEVING, 0.0)) for trait in traits)

    def careless(self, world: "SimulationWorld", resident: Resident) -> bool:
        """Whether a resident has it in them to part with the very thing they work with."""
        return any((world.registries.traits.find(trait_id) or {}).get(CARELESS) for trait_id in resident.traits)

    def use_effects(self, world: "SimulationWorld", resident: Resident, definition: ItemDefinition) -> dict[str, float]:
        """Need changes from using or eating the item, including the pleasure of a food to their
        taste and the displeasure of one that is not, by the tastes they have so far."""
        effects = dict(definition.effects)
        if definition.category == FOOD_CATEGORY:
            liked = world.tastes.liking(world, resident, definition)
            if liked:
                effects["stress"] = effects.get("stress", 0.0) - liked / 100.0 * world.registries.tastes.meal_stress
        return effects

    def better(self, world: "SimulationWorld", item: ItemInstance | None) -> float:
        """By how much a thing does what it does better than a common one, for how rare it is (S64)."""
        return world.upgrades.settings(world).of(item.level if item is not None else 1).better

    def take_in(
        self, world: "SimulationWorld", resident: Resident, definition: ItemDefinition, better: float = 1.0
    ) -> None:
        """Have a resident eat, drink or use an item: it is taken as their tastes have them, it
        does what it does to their needs, and what is eaten may turn on them. A rarer one
        does them that much more good, and no more harm."""
        # Tastes they did not have for it are made first, so that the pleasure of it is theirs.
        world.tastes.react(world, resident, definition, self.how_taken(definition))
        effects = self.use_effects(world, resident, definition)
        if better != 1.0:
            effects = {need: delta * better if delta < 0 else delta for need, delta in effects.items()}
        resident.needs.apply(effects)
        if definition.substance is not None:
            world.substances.taken(world, resident, definition)
            if resident.resident_id not in world.residents:
                return
        world.politics.laws.taken(world, resident, definition)
        chance = definition.properties.get(SICKENS, 0.0)
        if chance <= 0.0 or definition.category not in (FOOD_CATEGORY, WATER_CATEGORY):
            return
        if world.rng.random() >= chance:
            return
        harm = float(world.rng.randint(*world.registries.tastes.sickness_harm))
        if world.health.hurt(world, resident, harm, SICKNESS, f"comer {_named(definition)}"):
            world.tastes.sickened(world, resident, definition, harm)

    def how_taken(self, definition: ItemDefinition) -> str:
        """What is done with an item when it is put to use: eaten, drunk or used."""
        if definition.category == FOOD_CATEGORY:
            return EATEN
        return DRUNK if definition.category == WATER_CATEGORY else USED

    def definition_for(self, world: "SimulationWorld", item_id: str) -> ItemDefinition:
        """The definition behind an ID that names either a kind of item or one item in particular."""
        definition = world.registries.items.find(item_id)
        if definition is not None:
            return definition
        item = self.find_item(world, item_id)
        return world.registries.items.resolve(item.definition_id if item is not None else item_id)

    def wear(self, world: "SimulationWorld", holder: Resident, item: ItemInstance) -> None:
        """Take the toll of one use on an item. A thing worn right out breaks, and does nothing until repaired."""
        definition = world.registries.items.resolve(item.definition_id)
        # A rarer thing lasts that much longer.
        toll = definition.properties.get("wear", 0.0) / self.better(world, item)
        if toll <= 0 or item.broken:
            return
        item.condition = max(0.0, item.condition - toll)
        if item.broken:
            self._broke(world, holder, definition)

    def shatter(self, world: "SimulationWorld", holder: Resident, item: ItemInstance) -> None:
        """Break a thing outright, whatever was left in it. It does nothing until repaired."""
        if item.broken:
            return
        item.condition = 0.0
        self._broke(world, holder, world.registries.items.resolve(item.definition_id))

    def _broke(self, world: "SimulationWorld", holder: Resident, definition: ItemDefinition) -> None:
        world.emit_event(
            DomainEvent(
                "item_broke",
                BROKEN_IMPORTANCE,
                f"A {holder.name} se le rompe {_named(definition)}",
                [holder.resident_id],
            ),
            at=holder.tile,
        )

    def _relief(self, resident: Resident, effects: dict[str, float]) -> float:
        return sum(need_urgency(resident, need) for need, delta in effects.items() if delta < 0 and need in NEED_NAMES)

    # ----- eating from a shared container -----

    def best_food(
        self, world: "SimulationWorld", resident: Resident, container_id: str, category: str
    ) -> ItemInstance | None:
        """The food in a container this resident may take and would most like: shared or their own."""
        container = world.containers.get(container_id)
        if container is None:
            return None
        choices = [
            item
            for item in container.items
            if item.owner_id in (None, resident.resident_id)
            and world.registries.items.resolve(item.definition_id).category == category
            and world.politics.laws.may_have(world, resident, world.registries.items.resolve(item.definition_id))
        ]
        if not choices:
            return None
        resolve = world.registries.items.resolve
        taste = world.registries.tastes.food_choice
        # What answers their needs comes first. Among those, what does most, and what they like.
        return max(
            choices,
            key=lambda item: (
                self._relief(resident, self.use_effects(world, resident, resolve(item.definition_id)))
                * self.better(world, item),
                -sum(resolve(item.definition_id).effects.values())
                + world.tastes.liking(world, resident, resolve(item.definition_id)) * taste,
                item.instance_id,
            ),
        )

    def take_food(self, world: "SimulationWorld", resident: Resident, container_id: str, category: str) -> str | None:
        """Take one unit of the best food out of a container. Returns its definition ID."""
        taken = self.take_meal(world, resident, container_id, category)
        return taken[0] if taken is not None else None

    def take_meal(
        self, world: "SimulationWorld", resident: Resident, container_id: str, category: str
    ) -> tuple[str, int] | None:
        """Take one unit of the best food out of a container. Returns its definition ID and
        how rare it was, which is gone with the unit."""
        food = self.best_food(world, resident, container_id, category)
        if food is None:
            # A wasted walk to one empty pot is not news. Nothing to eat anywhere is.
            if not any(self.best_food(world, resident, other_id, category) for other_id in world.containers):
                if category == WATER_CATEGORY:
                    self._report_no_water(world, resident)
                elif category == FOOD_CATEGORY:
                    self._report_no_food(world, resident)
            return None
        world.containers[container_id].take_unit(food.instance_id)
        if food.owner_id is None:
            # What was everybody's is one the less for it.
            world.ledger.record(
                world, food.definition_id, -1, DRUNK if category == WATER_CATEGORY else EATEN, by=resident.resident_id
            )
        return (food.definition_id, food.level)

    def _report_no_food(self, world: "SimulationWorld", resident: Resident) -> None:
        """Say that someone found every shelf bare, at most once a day."""
        if world.notices.get(NO_FOOD_NOTICE) == world.clock.day:
            return
        world.notices[NO_FOOD_NOTICE] = world.clock.day
        world.emit_event(
            DomainEvent("no_food", NO_FOOD_IMPORTANCE, f"{resident.name} no encuentra nada que comer", [resident.resident_id]),
            at=resident.tile,
        )

    def report_nothing_for(self, world: "SimulationWorld", resident: Resident, need: str) -> None:
        """Give notice, once a day, that there is nothing left to answer a need with."""
        if need == "thirst":
            self._report_no_water(world, resident)
        elif need == "hunger":
            self._report_no_food(world, resident)

    def _report_no_water(self, world: "SimulationWorld", resident: Resident) -> None:
        if world.notices.get(NO_WATER_NOTICE) == world.clock.day:
            return
        world.notices[NO_WATER_NOTICE] = world.clock.day
        world.emit_event(
            DomainEvent("no_water", NO_FOOD_IMPORTANCE, f"{resident.name} no encuentra agua que beber", [resident.resident_id]),
            at=resident.tile,
        )

    # ----- choosing to use or steal something -----

    def candidates(self, world: "SimulationWorld", resident: Resident) -> list[ScoredAction]:
        return (
            self._use_candidates(world, resident)
            + pilfering.hunger_candidates(world, resident)
            + self._theft_candidates(world, resident)
        )

    def _use_candidates(self, world: "SimulationWorld", resident: Resident) -> list[ScoredAction]:
        """Own things worth using right now, wherever they are kept."""
        scored: list[ScoredAction] = []
        places: list[tuple[str | None, Inventory]] = [(None, resident.inventory), *world.containers.items()]
        for container_id, inventory in places:
            placed = world.interactables.get(container_id) if container_id else None
            distance = manhattan(resident.tile, (placed.x, placed.y)) if placed is not None else 0
            for item in inventory.items:
                if item.owner_id != resident.resident_id or item.broken or item.meant_for is not None:
                    # What is being kept for somebody is not theirs to use.
                    continue
                definition = world.registries.items.resolve(item.definition_id)
                if not world.politics.laws.may_have(world, resident, definition):
                    continue
                relief = self._relief(resident, self.use_effects(world, resident, definition))
                # What they depend on is wanted beside what it does for them, and what they
                # have made up their mind against is not wanted at all.
                wish = world.substances.wish(world, resident, definition)
                if wish is None or relief + wish <= 0:
                    continue
                score = (relief + wish) * USE_ITEM_APPEAL - DISTANCE_COST * distance
                scored.append(ScoredAction(USE_ITEM_ACTION, score, container_id, item_id=item.instance_id))
        return scored

    def temptation(
        self,
        world: "SimulationWorld",
        thief: Resident,
        owner: Resident,
        definition: ItemDefinition,
        item: ItemInstance | None = None,
    ) -> float:
        """How much a resident wants to take something of someone else's."""
        return self.personal_value(world, thief, definition, item) / 50.0 * self.leaning_to_steal(world, thief, owner)

    def leaning_to_steal(self, world: "SimulationWorld", thief: Resident, owner: Resident | None) -> float:
        """How given a resident is to taking what is not theirs, from 0 for not at all.

        Greed and a grudge against the owner push towards it; empathy holds back, and some are
        that way inclined whatever else they are. With no owner it is what the settlement holds
        in common, and there is nobody to bear the grudge.
        """
        feelings = world.relationships.get((thief.resident_id, owner.resident_id)) if owner is not None else None
        resentment = feelings.resentment if feelings is not None else 0.0
        drive = (thief.personality.greed - 50.0) / 50.0 + resentment / 100.0 - thief.personality.empathy / 200.0
        return max(0.0, drive + self.thieving(world, thief))

    def _theft_candidates(self, world: "SimulationWorld", resident: Resident) -> list[ScoredAction]:
        """Other people's things in containers nobody is watching, their credit, and what is everybody's."""
        last = world.theft_cooldowns.get(resident.resident_id)
        if last is not None and world.clock.total_minutes - last < THEFT_COOLDOWN_MINUTES:
            return []
        scored: list[ScoredAction] = pilfering.candidates(world, resident)
        for container_id, inventory in world.containers.items():
            placed = world.interactables.get(container_id)
            if placed is None:
                continue
            watched: bool | None = None
            for item in inventory.items:
                owner = world.residents.get(item.owner_id or "")
                if owner is None or owner is resident:
                    continue
                definition = world.registries.items.resolve(item.definition_id)
                temptation = self.temptation(world, resident, owner, definition, item)
                if temptation < THEFT_THRESHOLD:
                    continue
                if watched is None:
                    watched = bool(witnesses_of(world, (placed.x, placed.y), exclude=[resident.resident_id]))
                if watched:
                    break
                score = temptation - DISTANCE_COST * manhattan(resident.tile, (placed.x, placed.y))
                scored.append(ScoredAction(STEAL_ACTION, score, container_id, item_id=item.instance_id))
        return scored

    def plan(self, world: "SimulationWorld", resident: Resident, candidate: ScoredAction) -> Activity | None:
        if candidate.name in PILFERING_ACTIONS:
            return pilfering.plan(world, resident, candidate)
        minutes = STEAL_MINUTES if candidate.name == STEAL_ACTION else USE_ITEM_MINUTES
        if candidate.target_id is None:
            return Activity(candidate.name, minutes_left=minutes, item_id=candidate.item_id)
        placed = world.interactables.get(candidate.target_id)
        path = path_beside(world, resident, placed) if placed is not None else None
        if path is None:
            return None
        return Activity(candidate.name, candidate.target_id, path, minutes, item_id=candidate.item_id)

    # ----- doing it -----

    def tick(self, world: "SimulationWorld", resident: Resident, activity: Activity) -> None:
        """Spend one minute using or stealing an item, once the resident has reached it."""
        if not activity.using:
            if activity.action in PILFERING_ACTIONS:
                self._face(world, resident, activity)
                started = pilfering.begin(world, resident, activity)
            elif activity.action == STEAL_ACTION:
                started = self._begin_theft(world, resident, activity)
            else:
                started = self._begin_use(world, resident, activity)
            if not started:
                self._end(resident)
                return
            activity.using = True
            resident.current_action = activity.action
        activity.minutes_left -= 1
        if activity.minutes_left > 0:
            return
        if activity.action == USE_ITEM_ACTION:
            self._finish_use(world, resident, activity)
        self._end(resident)

    def _end(self, resident: Resident) -> None:
        resident.activity = None
        resident.current_action = "idle"

    def _where(self, world: "SimulationWorld", resident: Resident, activity: Activity) -> Inventory | None:
        """The inventory the activity's item should be in: a container, or the resident's own."""
        if activity.target_id is None:
            return resident.inventory
        return world.containers.get(activity.target_id)

    def _face(self, world: "SimulationWorld", resident: Resident, activity: Activity) -> None:
        placed = world.interactables.get(activity.target_id) if activity.target_id else None
        if placed is None:
            return
        dx, dy = placed.x - resident.x, placed.y - resident.y
        if dx or dy:
            resident.facing = ("right" if dx > 0 else "left") if abs(dx) > abs(dy) else ("down" if dy > 0 else "up")

    def _begin_use(self, world: "SimulationWorld", resident: Resident, activity: Activity) -> bool:
        inventory = self._where(world, resident, activity)
        item = inventory.find(activity.item_id or "") if inventory is not None else None
        if item is None or item.owner_id != resident.resident_id or item.broken:
            return False
        definition = world.registries.items.resolve(item.definition_id)
        if not world.substances.may_take(world, resident, definition):
            return False
        self._face(world, resident, activity)
        verb = "come" if definition.category == FOOD_CATEGORY else "pasa un rato con"
        if definition.substance is not None:
            verb = "echa mano de"
        room = world.room_at(resident.tile)
        world.emit_event(
            DomainEvent(
                "activity_started",
                5,
                f"{resident.name} {verb} {_named(definition)}",
                [resident.resident_id],
                location_id=room.room_id if room is not None else None,
            )
        )
        return True

    def _finish_use(self, world: "SimulationWorld", resident: Resident, activity: Activity) -> None:
        inventory = self._where(world, resident, activity)
        item = inventory.find(activity.item_id or "") if inventory is not None else None
        if item is None or inventory is None:
            return
        definition = world.registries.items.resolve(item.definition_id)
        if definition.category == FOOD_CATEGORY or definition.substance is not None:
            # What is eaten or taken is used up, and it is gone before it can do for them.
            better = self.better(world, item)
            inventory.take_unit(item.instance_id)
            self.take_in(world, resident, definition, better)
            return
        self.take_in(world, resident, definition, self.better(world, item))
        if RADIO_TAG in definition.tags:
            world.happenings.hear_radio(world, resident)
        self.wear(world, resident, item)
        if item.condition < WORN_CONDITION and inventory is not resident.inventory:
            # Too worn to put back: they keep it on them, to have it seen to.
            inventory.remove(item.instance_id)
            resident.inventory.add(item)

    def _begin_theft(self, world: "SimulationWorld", thief: Resident, activity: Activity) -> bool:
        container = world.containers.get(activity.target_id or "")
        item = container.find(activity.item_id or "") if container is not None else None
        victim = world.residents.get(item.owner_id or "") if item is not None else None
        if container is None or item is None or victim is None or victim is thief:
            return False
        self._face(world, thief, activity)
        container.remove(item.instance_id)
        thief.inventory.add(item)
        definition = world.registries.items.resolve(item.definition_id)
        attempt = TheftAttempt(
            thief.resident_id, victim.resident_id, item.instance_id, container_id=activity.target_id or ""
        )
        world.thefts.append(attempt)
        world.theft_cooldowns[thief.resident_id] = world.clock.total_minutes
        room = world.room_at(thief.tile)
        event = DomainEvent(
            "theft_committed",
            THEFT_IMPORTANCE,
            f"{thief.name} le roba {_named(definition)} a {victim.name}",
            [thief.resident_id],
            location_id=room.room_id if room is not None else None,
        )
        fact = world.emit_event(
            event,
            at=thief.tile,
            fact_text=f"{thief.name} le robó {_named(definition)} a {victim.name}",
            subjects=[thief.resident_id, victim.resident_id],
        )
        attempt.fact_id = fact.fact_id if fact is not None else ""
        attempt.discovered = bool(event.witnesses)
        return True

    def notice_missing(self, world: "SimulationWorld", resident: Resident) -> None:
        """A resident who can see where they kept something realises it is gone.

        So does whoever keeps the counter, of what the settlement had there.
        """
        for attempt in world.thefts:
            if attempt.noticed or attempt.returned:
                continue
            common = attempt.victim_id == FUND_VICTIM
            if attempt.victim_id != resident.resident_id and not (
                common and pilfering.keeps_counter(world, resident, attempt.container_id)
            ):
                continue
            placed = world.interactables.get(attempt.container_id)
            if placed is None or resident.resident_id not in witnesses_of(world, (placed.x, placed.y)):
                continue
            attempt.noticed = True
            item = self.find_item(world, attempt.item_instance_id)
            definition = world.registries.items.resolve(item.definition_id) if item is not None else None
            thing = _named(definition) if definition is not None else "algo"
            if attempt.amount > 0 and world.trading.currency is not None:
                thing = world.trading.currency.amount(attempt.amount)
            if common:
                thing = f"{thing} de lo que es de todos"
            if world.knowledge.knows(resident.resident_id, attempt.fact_id):
                continue
            resident.needs.apply({"stress": NOTICE_STRESS})
            world.memories.remember(
                resident.resident_id,
                Memory(f"Eché en falta {thing}.", NOTICE_IMPORTANCE, -0.5, tags=["theft"], timestamp=world.clock.total_minutes),
            )
            world.emit_event(
                DomainEvent("theft_noticed", NOTICE_IMPORTANCE, f"{resident.name} echa en falta {thing}", [resident.resident_id]),
                at=resident.tile,
            )

    def find_item(self, world: "SimulationWorld", instance_id: str) -> ItemInstance | None:
        inventories = [resident.inventory for resident in world.residents.values()] + list(world.containers.values())
        return next((item for inventory in inventories if (item := inventory.find(instance_id)) is not None), None)

    # ----- between two people at the end of a friendly exchange -----

    def after_exchange(
        self, world: "SimulationWorld", resident: Resident, partner: Resident, definition: "InteractionDefinition"
    ) -> None:
        """Things that change hands once two residents have talked: `resident`'s side of it."""
        if definition.returns_stolen:
            self._return_stolen(world, resident, partner)
        world.lending.after_exchange(world, resident, partner)
        if not self._maybe_gift(world, resident, partner):
            self._maybe_trade(world, resident, partner)

    def owned(self, world: "SimulationWorld", resident: Resident) -> list[ItemInstance]:
        """Things a resident carries that are theirs to give away."""
        return [
            item
            for item in resident.inventory.items
            if item.owner_id == resident.resident_id
            and world.registries.items.resolve(item.definition_id).category != UNKNOWN_CATEGORY
        ]

    def spare(self, world: "SimulationWorld", resident: Resident) -> list[ItemInstance]:
        """Things of their own that a resident carries and could part with.

        Nobody gives away what they work with: the tool of their job stays with them, unless
        they are fool enough. One they have besides it is theirs to give like anything else.
        What they are keeping for somebody is for that somebody.
        """
        owned = [item for item in self.owned(world, resident) if item.meant_for is None]
        job = world.work.job_of(world, resident)
        if job is None or job.tool is None or self.careless(world, resident):
            return owned
        resolve = world.registries.items.resolve
        kept = world.work.tool_of(world, resident, job) or next(
            (item for item in owned if job.tool.tag in resolve(item.definition_id).tags), None
        )
        return [item for item in owned if item is not kept or item.quantity > 1]

    def _return_stolen(self, world: "SimulationWorld", resident: Resident, partner: Resident) -> None:
        for attempt in world.thefts:
            if attempt.returned or attempt.thief_id != resident.resident_id or attempt.victim_id != partner.resident_id:
                continue
            if attempt.amount > 0:
                # Credit comes back as far as they still have it.
                back = min(attempt.amount, float(int(resident.credits)))
                coin = world.trading.currency
                if back < 1 or coin is None:
                    continue
                resident.credits -= back
                partner.credits += back
                thing = coin.amount(back)
            else:
                item = resident.inventory.remove(attempt.item_instance_id)
                if item is None:
                    continue
                partner.inventory.add(item)
                thing = _named(world.registries.items.resolve(item.definition_id))
            attempt.returned = True
            attempt.discovered = True
            fact = world.knowledge.facts.get(attempt.fact_id)
            if fact is not None:
                # Handing it back is the confession; they have just made their peace over it.
                learn(world, partner, fact, 1.0, SOURCE_PARTICIPANT)
            world.emit_event(
                DomainEvent(
                    "item_returned",
                    RETURN_IMPORTANCE,
                    f"{resident.name} le devuelve {thing} a {partner.name}",
                    [resident.resident_id, partner.resident_id],
                ),
                at=resident.tile,
            )

    def _maybe_gift(self, world: "SimulationWorld", giver: Resident, receiver: Resident) -> bool:
        # Something bought for them is handed over the first time the two of them talk.
        present = next(
            (
                item
                for item in giver.inventory.items
                if item.meant_for == receiver.resident_id and item.owner_id == giver.resident_id
            ),
            None,
        )
        gifts = self.spare(world, giver)
        feelings = world.relationship(giver.resident_id, receiver.resident_id)
        if present is None:
            if not gifts or feelings.affection < GIFT_AFFECTION or giver.personality.greed > GIFT_MAX_GREED:
                return False
            if world.rng.random() >= GIFT_CHANCE:
                return False
        resolve = world.registries.items.resolve
        item = present or max(
            gifts,
            key=lambda i: (self.gift_appeal(world, giver, receiver, resolve(i.definition_id)), i.instance_id),
        )
        definition = resolve(item.definition_id)
        if item.quantity > 1:
            item.quantity -= 1
            given = world.stock(receiver.inventory, item.definition_id, 1, receiver.resident_id, item.level)
        else:
            giver.inventory.remove(item.instance_id)
            item.owner_id, item.meant_for = receiver.resident_id, None
            receiver.inventory.add(item)
            given = item
        given.given_by = giver.resident_id
        now = world.clock.total_minutes
        thing = _named(definition)
        world.memories.remember(
            giver.resident_id,
            Memory(f"Le regalé {thing} a {receiver.name}.", GIFT_IMPORTANCE, 0.4, [receiver.resident_id], ["gift"], now),
        )
        world.memories.remember(
            receiver.resident_id,
            Memory(f"{giver.name} me regaló {thing}.", GIFT_IMPORTANCE, 0.6, [giver.resident_id], ["gift"], now),
        )
        world.emit_event(
            DomainEvent(
                "gift_given",
                GIFT_IMPORTANCE,
                f"{giver.name} le regala {thing} a {receiver.name}",
                [giver.resident_id, receiver.resident_id],
            ),
            at=giver.tile,
        )
        # How it is taken is what it does to what the receiver feels for the giver.
        world.tastes.react(world, receiver, definition, GIVEN, giver)
        return True

    def gift_appeal(
        self, world: "SimulationWorld", giver: Resident, receiver: Resident, definition: ItemDefinition
    ) -> float:
        """How good a present something looks to the giver: what it is worth, and what they
        have seen of the receiver's tastes. What they have not seen, they cannot choose by."""
        believed = world.tastes.believed_liking(world, giver, receiver, definition)
        return definition.base_value * (1.0 + believed / 100.0 * world.registries.tastes.worth_taste)

    def propose_trade(self, world: "SimulationWorld", proposer: Resident, receiver: Resident) -> TradeOffer | None:
        """The swap of one item each that the proposer gains most from and the receiver does not lose by."""
        resolve = world.registries.items.resolve
        best: tuple[float, str, str] | None = None
        for mine in self.spare(world, proposer):
            for theirs in self.spare(world, receiver):
                if mine.definition_id == theirs.definition_id:
                    continue
                mine_def, theirs_def = resolve(mine.definition_id), resolve(theirs.definition_id)
                gain = self.personal_value(world, proposer, theirs_def, theirs) - self.personal_value(
                    world, proposer, mine_def, mine
                )
                other_gain = self.personal_value(world, receiver, mine_def, mine) - self.personal_value(
                    world, receiver, theirs_def, theirs
                )
                if gain > 0 and other_gain >= 0 and (best is None or gain + other_gain > best[0]):
                    best = (gain + other_gain, mine.instance_id, theirs.instance_id)
        if best is None:
            return None
        return TradeOffer(proposer.resident_id, receiver.resident_id, [best[1]], [best[2]])

    def _maybe_trade(self, world: "SimulationWorld", proposer: Resident, receiver: Resident) -> bool:
        offer = self.propose_trade(world, proposer, receiver)
        if offer is None:
            self._turned_down(world, proposer, receiver)
            return False
        names = []
        for giver, taker, instance_ids in (
            (proposer, receiver, offer.offered_instance_ids),
            (receiver, proposer, offer.requested_instance_ids),
        ):
            for instance_id in instance_ids:
                item = giver.inventory.remove(instance_id)
                if item is None:
                    continue
                item.owner_id = taker.resident_id
                taker.inventory.add(item)
                names.append(_named(world.registries.items.resolve(item.definition_id)))
        world.emit_event(
            DomainEvent(
                "trade_made",
                TRADE_IMPORTANCE,
                f"{proposer.name} y {receiver.name} cambian {' por '.join(names)}",
                [proposer.resident_id, receiver.resident_id],
            ),
            at=proposer.tile,
        )
        return True

    def _turned_down(self, world: "SimulationWorld", proposer: Resident, receiver: Resident) -> None:
        """A swap the proposer wants, and that the receiver would not lose by were the thing
        offered not so little to their liking: it is said, once a day between the two."""
        notice = f"refused:{proposer.resident_id}:{receiver.resident_id}"
        if world.notices.get(notice) == world.clock.day:
            return
        resolve = world.registries.items.resolve
        dislike = world.registries.tastes.thresholds[DISLIKED]
        for mine in self.spare(world, proposer):
            mine_def = resolve(mine.definition_id)
            if world.tastes.liking(world, receiver, mine_def) > dislike:
                continue
            for theirs in self.spare(world, receiver):
                theirs_def = resolve(theirs.definition_id)
                if mine.definition_id == theirs.definition_id or mine_def.base_value < theirs_def.base_value:
                    continue
                wanted = self.personal_value(world, proposer, theirs_def, theirs) > self.personal_value(
                    world, proposer, mine_def, mine
                )
                if wanted:
                    world.notices[notice] = world.clock.day
                    world.tastes.refused(world, receiver, proposer, mine_def)
                    return

    # ----- the settlement's supplies -----

    def tick_world(self, world: "SimulationWorld") -> None:
        """Deliver the day's supplies at the hour the map says."""
        layout = world.registries.maps.get(world.map_id)
        if layout is None or world.clock.minute != 0:
            return
        for rule in layout.supplies:
            container = world.containers.get(rule.container)
            definition = world.registries.items.find(rule.item)
            if rule.hour != world.clock.hour or container is None or definition is None:
                continue
            world.stock(container, rule.item, rule.count, None)
            world.ledger.record(world, rule.item, rule.count, ARRIVED)
            world.emit_event(
                DomainEvent("supplies_arrived", 10, f"Llegan provisiones: {rule.count} de {definition.name}")
            )
