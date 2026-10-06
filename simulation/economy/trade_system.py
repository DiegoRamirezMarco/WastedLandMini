"""What work is paid with, and what it buys: goods over a counter, a drink, a repair.

With a currency, wages come out of the common fund and what is paid at a counter goes back
into it. Under barter nothing is priced: whoever holds a job is kept, and a thing is had for
another, each worth to each of the two what it is worth to them.
"""

import math
from typing import TYPE_CHECKING

from simulation.ai.utility_ai import need_urgency
from simulation.economy.fund_system import hand_over
from simulation.events.event import DomainEvent
from simulation.items.inventory import Inventory
from simulation.items.item import WORN_CONDITION, ItemDefinition, ItemInstance
from simulation.items.item_system import FOOD_CATEGORY
from simulation.items.registry import UNKNOWN_CATEGORY
from simulation.residents.activity import Activity
from simulation.residents.needs import NEED_NAMES
from simulation.residents.resident import Resident
from simulation.work.job import JobDefinition
from world.interactable import UseDefinition

if TYPE_CHECKING:
    from simulation.world import SimulationWorld

REPAIR_APPEAL = 0.5
SHOP_APPEAL = 0.5
# How much a resident wants something they have no pressing use for, before its price is weighed.
BASE_DESIRE = 0.3
# Below this a thing is not worth the walk to the counter.
MIN_WANT = 0.25
MAX_WANT = 1.25
# Units of food of their own a resident keeps before they stop buying more.
STASH_SIZE = 2
# Fear of someone from which a resident wants something to defend themselves with.
ARM_FEAR = 30.0
PURCHASE_IMPORTANCE = 15
MINUTES_PER_HOUR = 60.0
KEEP_IMPORTANCE = 10
UNPAID_KEEP_IMPORTANCE = 20
UNPAID_KEEP_NOTICE = "unpaid_keep:"
SWAP_REFUSED_IMPORTANCE = 20
SWAP_REFUSED_NOTICE = "swap_refused:"
UNPAID_WAGES_IMPORTANCE = 35
UNPAID_WAGES_NOTICE = "unpaid_wages"
# What is left over from counting a wage by the minute: too little to say it went unpaid.
SHORT_BY = 1e-9


class TradeSystem:
    # ----- earning -----

    def pay_wage(self, world: "SimulationWorld", resident: Resident, job: JobDefinition) -> None:
        """Pay a resident one minute's wage out of the common fund, as far as the fund goes.

        Under barter there is no wage: whoever holds a job is kept instead.
        """
        if world.fund.currency(world) is None:
            return
        wage = job.wage if job.wage is not None else world.registries.economy.wage_per_hour
        due = wage / MINUTES_PER_HOUR
        paid = world.fund.pay_out(world, due)
        resident.credits += paid
        if paid + SHORT_BY < due and world.notices.get(UNPAID_WAGES_NOTICE) != world.clock.day:
            world.notices[UNPAID_WAGES_NOTICE] = world.clock.day
            world.emit_event(
                DomainEvent(
                    "wages_unpaid", UNPAID_WAGES_IMPORTANCE, "No hay con qué pagar los sueldos: el fondo está vacío"
                )
            )

    def pay(self, world: "SimulationWorld", resident: Resident, price: float) -> bool:
        """Take a price out of a resident's credits and into the fund. False, and nothing taken, if they are short."""
        if resident.credits < price:
            return False
        resident.credits -= price
        world.fund.pay_in(world, price)
        return True

    # ----- what a use costs -----

    def owes_keep(self, world: "SimulationWorld", resident: Resident, use: UseDefinition) -> bool:
        """Whether a use is one this resident has to hand something over for, under barter.

        Whoever holds a job eats and drinks for nothing. Whoever does not gives a thing for what
        has a price and for what is kept for those who work. A settlement still in its opening
        asks nothing of anybody.
        """
        if world.fund.currency(world) is not None or world.tutorial.active:
            return False
        if resident.job_id in world.registries.jobs:
            return False
        return use.price > 0 or use.consumes in world.registries.economy.kept_categories

    def can_afford(self, world: "SimulationWorld", resident: Resident, use: UseDefinition) -> bool:
        """Whether a resident has what a use costs them, as the settlement trades right now."""
        if world.fund.currency(world) is not None:
            return use.price <= resident.credits or self.mends_their_tool(world, resident, use)
        if use.price <= 0 or not self.owes_keep(world, resident, use):
            # Nobody is left to go hungry for having nothing to give.
            return True
        return self.token(world, resident) is not None

    def mends_their_tool(self, world: "SimulationWorld", resident: Resident, use: UseDefinition) -> bool:
        """Whether a use is the mending of what a resident works with, which nobody goes without
        for want of coin: the settlement that cannot pay a wage does not lose a pair of hands to it."""
        job = world.work.job_of(world, resident)
        worn = self.worn_item(world, resident) if use.repairs > 0 and job is not None and job.tool is not None else None
        return worn is not None and job.tool.tag in world.registries.items.resolve(worn.definition_id).tags

    def token(self, world: "SimulationWorld", resident: Resident) -> ItemInstance | None:
        """The thing of their own that a resident would part with soonest: the one worth least to them."""
        resolve = world.registries.items.resolve
        return min(
            world.items.spare(world, resident),
            key=lambda item: (
                world.items.personal_value(world, resident, resolve(item.definition_id), item),
                item.instance_id,
            ),
            default=None,
        )

    def charge(self, world: "SimulationWorld", resident: Resident, use: UseDefinition) -> bool:
        """Take what a use costs a resident. False, and nothing taken, if they have not got it."""
        if world.fund.currency(world) is not None:
            # Short of the price, the tool they work with is mended all the same.
            return self.pay(world, resident, use.price) or self.mends_their_tool(world, resident, use)
        if not self.owes_keep(world, resident, use):
            return True
        given = self.token(world, resident)
        if given is None or not world.fund.take_in(world, resident.inventory, given, resident.tile):
            if use.price > 0:
                return False
            self._say_unpaid(world, resident)
            return True
        definition = world.registries.items.resolve(given.definition_id)
        world.emit_event(
            DomainEvent(
                "keep_paid",
                KEEP_IMPORTANCE,
                f"{resident.name}, que no tiene puesto, entrega {definition.article} {definition.name} a cambio",
                [resident.resident_id],
                data={"item_id": definition.item_id},
            ),
            at=resident.tile,
        )
        return True

    def _say_unpaid(self, world: "SimulationWorld", resident: Resident) -> None:
        """Say, once a day, that someone who holds no job was fed with nothing to give for it."""
        key = f"{UNPAID_KEEP_NOTICE}{resident.resident_id}"
        if world.notices.get(key) == world.clock.day:
            return
        world.notices[key] = world.clock.day
        world.emit_event(
            DomainEvent(
                "keep_unpaid",
                UNPAID_KEEP_IMPORTANCE,
                f"{resident.name} no tiene puesto ni nada que dar por lo que come",
                [resident.resident_id],
            ),
            at=resident.tile,
        )

    # ----- buying over a counter -----

    def price_of(self, world: "SimulationWorld", definition: ItemDefinition, in_stock: int) -> int:
        """What one unit costs. The fewer there are left, the dearer."""
        economy = world.registries.economy
        scarcity = 1.0 + economy.scarcity_markup / max(1, in_stock)
        return math.ceil(definition.base_value * economy.price_factor * scarcity)

    def want(self, world: "SimulationWorld", resident: Resident, definition: ItemDefinition, price: float) -> float:
        """How much a resident wants to buy something at a price, from 0 to `MAX_WANT`. Under
        barter the price is what the thing they would give for it is worth to them.

        A tool for their own job when they have none comes first. A weapon is wanted out of fear.
        Anything else is weighed by what it would do for them now against what it costs.
        """
        if definition.category == UNKNOWN_CATEGORY or price <= 0:
            return 0.0
        job = world.work.job_of(world, resident)
        if job is not None and job.tool is not None and job.tool.tag in definition.tags:
            return 0.0 if self._carries_tagged(world, resident, job.tool.tag) else MAX_WANT
        if definition.properties.get("damage", 0.0) > 1.0:
            if world.health.weapon_of(world, resident)[0] > 1.0:
                return 0.0
            fear = max(
                (
                    feelings.fear
                    for (source_id, target_id), feelings in world.relationships.items()
                    if source_id == resident.resident_id and target_id in world.residents
                ),
                default=0.0,
            )
            return min(MAX_WANT, fear / 100.0 * 1.5) if fear >= ARM_FEAR else 0.0
        relief = sum(
            need_urgency(resident, need)
            for need, delta in world.items.use_effects(world, resident, definition).items()
            if delta < 0 and need in NEED_NAMES
        )
        owned = self._owned_units(world, resident, definition.item_id)
        if relief <= 0 and not definition.effects:
            return 0.0
        if owned >= (STASH_SIZE if definition.category == FOOD_CATEGORY else 1):
            return 0.0
        bargain = world.items.personal_value(world, resident, definition) / price
        return min(MAX_WANT, bargain * (BASE_DESIRE + relief))

    def best_buy(
        self, world: "SimulationWorld", resident: Resident, container_id: str
    ) -> tuple[ItemInstance, int, float] | None:
        """What a resident would buy from a counter right now: the item, its price and how much they want it."""
        container = world.containers.get(container_id)
        if container is None:
            return None
        best: tuple[ItemInstance, int, float] | None = None
        for item in container.items:
            if item.owner_id is not None or item.broken:
                continue
            definition = world.registries.items.resolve(item.definition_id)
            price = self.price_of(world, definition, container.count(item.definition_id))
            if price > resident.credits:
                continue
            want = self.want(world, resident, definition, price)
            if want >= MIN_WANT and (best is None or want > best[2]):
                best = (item, price, want)
        return best

    def shop_score(self, world: "SimulationWorld", resident: Resident, container_id: str) -> float | None:
        """How much a resident wants to go to a counter for something. None if nothing tempts them."""
        if world.fund.currency(world) is None:
            if world.notices.get(f"{SWAP_REFUSED_NOTICE}{resident.resident_id}") == world.clock.day:
                # They were turned down there today, and will not go and ask again.
                return None
            offers = self.offers(world, resident, container_id)
            return offers[0][0] * SHOP_APPEAL if offers else None
        choice = self.best_buy(world, resident, container_id)
        return choice[2] * SHOP_APPEAL if choice is not None else None

    def buy(self, world: "SimulationWorld", resident: Resident, container_id: str) -> str | None:
        """Have a resident get the thing they want most from a counter: paid for with a currency,
        had for a thing of their own under barter. Returns its definition ID, or None."""
        coin = world.fund.currency(world)
        if coin is None:
            return self.swap(world, resident, container_id)
        choice = self.best_buy(world, resident, container_id)
        if choice is None:
            return None
        item, price, _ = choice
        if not self.pay(world, resident, price):
            return None
        hand_over(world, world.containers[container_id], item, resident.inventory, resident.resident_id)
        definition = world.registries.items.resolve(item.definition_id)
        room = world.room_at(resident.tile)
        world.emit_event(
            DomainEvent(
                "item_bought",
                PURCHASE_IMPORTANCE,
                f"{resident.name} compra {definition.article} {definition.name} por {coin.amount(price)}",
                [resident.resident_id],
                location_id=room.room_id if room is not None else None,
                data={"item_id": definition.item_id, "price": price},
            ),
            at=resident.tile,
        )
        world.tastes.bought(world, resident, definition)
        return item.definition_id

    # ----- a thing for a thing -----

    def offers(
        self, world: "SimulationWorld", resident: Resident, container_id: str
    ) -> list[tuple[float, ItemInstance, ItemInstance]]:
        """The swaps a resident would propose at a counter, keenest first: how much they want
        it, the thing on the counter, and the thing of theirs they would give for it.

        Each is one they would come out of better by their own lights. Whether whoever keeps the
        counter will have it is another matter, and not theirs to know beforehand.
        """
        container = world.containers.get(container_id)
        if container is None:
            return []
        resolve = world.registries.items.resolve
        mine = [
            (world.items.personal_value(world, resident, resolve(item.definition_id), item), item)
            for item in world.items.spare(world, resident)
            if not item.broken
        ]
        found: list[tuple[float, float, ItemInstance, ItemInstance]] = []
        for wanted in container.items:
            if wanted.owner_id is not None or wanted.broken:
                continue
            definition = resolve(wanted.definition_id)
            worth = world.items.personal_value(world, resident, definition, wanted)
            for cost, given in mine:
                if given.definition_id == wanted.definition_id or worth <= cost:
                    continue
                want = self.want(world, resident, definition, max(cost, 1.0))
                if want >= MIN_WANT:
                    found.append((want, cost, wanted, given))
        found.sort(key=lambda offer: (-offer[0], offer[1], offer[2].instance_id, offer[3].instance_id))
        return [(want, wanted, given) for want, _, wanted, given in found]

    def keeper(self, world: "SimulationWorld", container_id: str) -> Resident | None:
        """Whoever is behind a counter right now, to say yes or no to a swap."""
        placed = world.interactables.get(container_id)
        use = world.definition_of(placed).use if placed is not None else None
        if use is None or use.staffed_by is None:
            return None
        on_duty = [
            resident
            for resident in world.residents.values()
            if resident.job_id == use.staffed_by and world.work.on_duty(world, resident)
        ]
        at_it = next((resident for resident in on_duty if resident.post_id == container_id), None)
        return at_it or (on_duty[0] if on_duty else None)

    def takes(
        self, world: "SimulationWorld", keeper: Resident | None, wanted: ItemInstance, given: ItemInstance
    ) -> bool:
        """Whether whoever keeps a counter will let one thing go for another: they must not lose
        by it as they see it. A counter nobody keeps goes by what things are worth to anybody."""
        resolve = world.registries.items.resolve
        wanted_definition, given_definition = resolve(wanted.definition_id), resolve(given.definition_id)
        if keeper is None:
            return given_definition.base_value >= wanted_definition.base_value
        return world.items.personal_value(world, keeper, given_definition, given) >= world.items.personal_value(
            world, keeper, wanted_definition, wanted
        )

    def swap(self, world: "SimulationWorld", resident: Resident, container_id: str) -> str | None:
        """Have a resident ask at a counter for what they want, offering things of their own for it.

        The first offer whoever keeps the counter will have is made good, and what was given goes
        on the shelf as the settlement's. Returns the definition ID of what they got, or None if
        every offer was turned down, which is said and keeps them from asking again that day.
        """
        offers = self.offers(world, resident, container_id)
        if not offers:
            return None
        container = world.containers[container_id]
        keeper = self.keeper(world, container_id)
        if keeper is resident:
            keeper = None
        resolve = world.registries.items.resolve
        room = world.room_at(resident.tile)
        location_id = room.room_id if room is not None else None
        people = [resident.resident_id, *([keeper.resident_id] if keeper is not None else [])]
        for _, wanted, given in offers:
            if not self.takes(world, keeper, wanted, given):
                continue
            wanted_definition, given_definition = resolve(wanted.definition_id), resolve(given.definition_id)
            hand_over(world, resident.inventory, given, container, None)
            hand_over(world, container, wanted, resident.inventory, resident.resident_id)
            world.emit_event(
                DomainEvent(
                    "item_swapped",
                    PURCHASE_IMPORTANCE,
                    f"{resident.name} cambia {given_definition.article} {given_definition.name} por "
                    f"{wanted_definition.article} {wanted_definition.name} en el mostrador",
                    people,
                    location_id=location_id,
                    data={"item_id": wanted_definition.item_id, "given_id": given_definition.item_id},
                ),
                at=resident.tile,
            )
            world.tastes.bought(world, resident, wanted_definition)
            return wanted_definition.item_id
        _, wanted, given = offers[0]
        wanted_definition, given_definition = resolve(wanted.definition_id), resolve(given.definition_id)
        world.notices[f"{SWAP_REFUSED_NOTICE}{resident.resident_id}"] = world.clock.day
        behind = keeper.name if keeper is not None else "Nadie"
        world.emit_event(
            DomainEvent(
                "swap_refused",
                SWAP_REFUSED_IMPORTANCE,
                f"{behind} no le cambia a {resident.name} {wanted_definition.article} {wanted_definition.name} "
                f"por {given_definition.article} {given_definition.name}",
                people,
                location_id=location_id,
                data={"item_id": wanted_definition.item_id, "given_id": given_definition.item_id},
            ),
            at=resident.tile,
        )
        return None

    def _carries_tagged(self, world: "SimulationWorld", resident: Resident, tag: str) -> bool:
        return any(tag in world.registries.items.resolve(item.definition_id).tags for item in resident.inventory.items)

    def _owned_units(self, world: "SimulationWorld", resident: Resident, definition_id: str) -> int:
        """How many of something a resident already has, on them or put away."""
        inventories = [resident.inventory, *world.containers.values()]
        return sum(
            item.quantity
            for inventory in inventories
            for item in inventory.items
            if item.definition_id == definition_id and item.owner_id == resident.resident_id
        )

    # ----- repairs -----

    def worn_item(self, world: "SimulationWorld", resident: Resident) -> ItemInstance | None:
        """The most worn thing of their own a resident has on them that is worth repairing."""
        worn = [
            item
            for item in resident.inventory.items
            if item.owner_id == resident.resident_id
            and item.condition < WORN_CONDITION
            and world.registries.items.resolve(item.definition_id).properties.get("wear", 0.0) > 0
        ]
        return min(worn, key=lambda item: (item.condition, item.instance_id), default=None)

    def repair_score(self, world: "SimulationWorld", resident: Resident, use: UseDefinition) -> float | None:
        """How much a resident wants something of theirs repaired. None if nothing needs it, or if
        there is nothing to repair it with."""
        item = self.worn_item(world, resident)
        if item is None or (use.material is not None and self.repair_material(world, use) is None):
            return None
        return REPAIR_APPEAL * (1.0 - max(0.0, item.condition) / 100.0)

    def repair_material(self, world: "SimulationWorld", use: UseDefinition) -> tuple[Inventory, ItemInstance] | None:
        """A unit of what a repair is made with, and where it is, if the settlement has any."""
        for object_id, inventory in world.containers.items():
            placed = world.interactables.get(object_id)
            if placed is None or placed.kind != use.material_from:
                continue
            for item in inventory.items:
                if item.owner_id is None and use.material in world.registries.items.resolve(item.definition_id).tags:
                    return (inventory, item)
        return None

    def take_repair_material(self, world: "SimulationWorld", use: UseDefinition) -> bool:
        """Use up what one repair takes. True if the repair needs nothing, or there was some."""
        if use.material is None:
            return True
        material = self.repair_material(world, use)
        if material is None:
            return False
        material[0].take_unit(material[1].instance_id)
        return True

    def repair_minute(self, world: "SimulationWorld", activity: Activity, use: UseDefinition) -> bool:
        """Mend the thing being repaired for one minute. True once there is no more to be done.

        The work is the repairer's, so it stops when they leave their post.
        """
        item = world.items.find_item(world, activity.item_id or "")
        if item is None or (use.staffed_by is not None and not world.work.is_staffed(world, use.staffed_by)):
            return True
        item.condition = min(100.0, max(0.0, item.condition) + use.repairs)
        return item.condition >= 100.0
