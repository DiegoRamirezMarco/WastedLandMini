"""What work is paid with, and what it buys: goods over a counter, a meal, a drink, a repair.

With a currency, wages come out of the common fund and what is paid goes back into it. Under
barter nothing is priced: a thing is had for another, each worth to each of the two what it is
worth to them. Either way the settlement keeps whoever works for it, and nobody else.
"""

import math
from typing import TYPE_CHECKING

from simulation.work.craft_system import tool_tag
from simulation.ai.utility_ai import need_urgency
from simulation.economy.fund_system import hand_over
from simulation.events.event import DomainEvent
from simulation.items.inventory import Inventory
from simulation.items.item import WORN_CONDITION, ItemDefinition, ItemInstance
from simulation.items.item_system import FOOD_CATEGORY, GIFT_AFFECTION, GIFT_MAX_GREED
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
# How much somebody with coin to spare wants to buy a present for someone they are fond of.
PRESENT_WANT = 0.3
# Units of food of their own a resident keeps before they stop buying more.
STASH_SIZE = 2
# Fear of someone from which a resident wants something to defend themselves with.
ARM_FEAR = 30.0
PURCHASE_IMPORTANCE = 15
MINUTES_PER_HOUR = 60.0
MINUTES_PER_DAY = 24 * 60
KEEP_IMPORTANCE = 10
SUPPLY_IMPORTANCE = 40
SUPPLY_NOTICE = "cut_off:"
TREAT_IMPORTANCE = 15
TREAT_FEELINGS = {"affection": 4.0, "trust": 2.0}
SWAP_REFUSED_IMPORTANCE = 20
SWAP_REFUSED_NOTICE = "swap_refused:"
UNPAID_WAGES_IMPORTANCE = 35
UNPAID_WAGES_NOTICE = "unpaid_wages"
# How much slower each day without a wage has someone work, and the slowest it gets them.
UNPAID_DRAG = 0.05
UNPAID_FLOOR = 0.8
# What is left over from counting a wage by the minute: too little to say it went unpaid.
SHORT_BY = 1e-9


class TradeSystem:
    # ----- earning -----

    def pay_wage(self, world: "SimulationWorld", resident: Resident, job: JobDefinition | None) -> None:
        """Count one minute of a resident's work, and pay them for it out of the common fund as far as it goes.

        Under barter there is no wage: whoever works is kept instead. Work that is no post, such
        as a site in somebody's charge, is paid the settlement's usual wage.
        """
        resident.last_worked = world.clock.total_minutes
        if world.fund.currency(world) is None:
            return
        wage = job.wage if job is not None and job.wage is not None else world.registries.economy.wage_per_hour
        # What the law has it come to: more or less by the hour, less what the fund keeps of it.
        due = world.politics.laws.wage(world, wage / MINUTES_PER_HOUR)
        paid = world.fund.pay_out(world, due)
        resident.credits += paid
        if paid + SHORT_BY >= due:
            return
        self._went_unpaid(world, resident)
        if world.notices.get(UNPAID_WAGES_NOTICE) != world.clock.day:
            world.notices[UNPAID_WAGES_NOTICE] = world.clock.day
            world.emit_event(
                DomainEvent(
                    "wages_unpaid", UNPAID_WAGES_IMPORTANCE, "No hay con qué pagar los sueldos: el fondo está vacío"
                )
            )

    def _went_unpaid(self, world: "SimulationWorld", resident: Resident) -> None:
        """Have a day without their wage tell on a worker, the first time in the day it is short."""
        today = world.clock.day
        if resident.unpaid_on == today:
            return
        economy = world.registries.economy
        resident.unpaid_days = resident.unpaid_days + 1 if resident.unpaid_on == today - 1 else 1
        resident.unpaid_on = today
        resident.adjust_mood(-economy.unpaid_mood)
        resident.needs.apply({"stress": economy.unpaid_stress})
        if resident.unpaid_days >= economy.grumble_unpaid_days:
            world.terms.maybe_raise(world, resident)

    def unpaid_days(self, world: "SimulationWorld", resident: Resident) -> int:
        """How many days running a resident has gone without their wage, as of today."""
        return resident.unpaid_days if resident.unpaid_on >= world.clock.day - 1 else 0

    def unpaid_pace(self, world: "SimulationWorld", resident: Resident) -> float:
        """How fast someone works for how long they have gone unpaid: nobody puts their back into it for nothing."""
        return max(UNPAID_FLOOR, 1.0 - UNPAID_DRAG * self.unpaid_days(world, resident))

    def pay(self, world: "SimulationWorld", resident: Resident, price: float) -> bool:
        """Take a price out of a resident's credits and into the fund. False, and nothing taken, if they are short."""
        if resident.credits < price:
            return False
        resident.credits -= price
        world.fund.pay_in(world, price)
        return True

    # ----- who the settlement keeps -----

    def supplied(self, world: "SimulationWorld", resident: Resident) -> bool:
        """Whether the settlement still keeps a resident: they have worked in the last few days,
        or could not have. A settlement still in its opening keeps everybody."""
        if world.tutorial.active or world.children.is_child(world, resident):
            # Nobody under age has to earn their keep.
            return True
        idle = world.clock.total_minutes - resident.last_worked
        return idle < world.registries.economy.idle_days * MINUTES_PER_DAY

    def watch_supply(self, world: "SimulationWorld", resident: Resident) -> None:
        """Say so when the settlement stops keeping somebody, and when it takes them back."""
        key = f"{SUPPLY_NOTICE}{resident.resident_id}"
        cut = not self.supplied(world, resident)
        if cut == (key in world.notices):
            return
        if cut:
            world.notices[key] = world.clock.day
            days = world.registries.economy.idle_days
            text = f"El asentamiento deja de mantener a {resident.name}: lleva {days} días sin trabajar"
        else:
            del world.notices[key]
            text = f"{resident.name} vuelve a trabajar, y el asentamiento a mantenerle"
        world.emit_event(
            DomainEvent(
                "supply_cut" if cut else "supply_restored", SUPPLY_IMPORTANCE, text, [resident.resident_id]
            ),
            at=resident.tile,
        )

    # ----- what a use costs -----

    def cost(self, world: "SimulationWorld", resident: Resident, use: UseDefinition) -> float:
        """What a use costs a resident in coin: its price, and for a meal out of the commons the
        price of one. Water is for nothing to whoever the settlement keeps."""
        economy = world.registries.economy
        price = float(use.price)
        meal = economy.meal_price * world.politics.laws.meal_price(world)
        if use.consumes in economy.kept_categories:
            price += meal
        elif use.consumes is not None and not self.supplied(world, resident):
            price += meal
        return price

    def owes_keep(self, world: "SimulationWorld", resident: Resident, use: UseDefinition) -> bool:
        """Under barter, whether a resident has to hand something over for a use.

        Whoever the settlement keeps eats, drinks and has things mended for nothing. Whoever it
        does not gives a thing for what has a price and for anything out of the commons.
        """
        if world.fund.currency(world) is not None or self.supplied(world, resident):
            return False
        return use.price > 0 or use.consumes is not None

    def on_the_house(self, world: "SimulationWorld", resident: Resident, use: UseDefinition) -> bool:
        """With a currency, whether somebody who cannot pay is served all the same: whoever the
        settlement keeps is fed, and the tool somebody works with is mended."""
        if self.mends_their_tool(world, resident, use):
            return True
        return use.price <= 0 and use.consumes is not None and self.supplied(world, resident)

    def can_afford(
        self, world: "SimulationWorld", resident: Resident, use: UseDefinition, object_id: str | None = None
    ) -> bool:
        """Whether a resident has what a use costs them, as the settlement trades right now."""
        if world.fund.currency(world) is not None:
            return (
                self.cost(world, resident, use) <= resident.credits
                or self.on_the_house(world, resident, use)
                or self.patron(world, resident, use, object_id) is not None
            )
        return not self.owes_keep(world, resident, use) or self.token(world, resident) is not None

    def mends_their_tool(self, world: "SimulationWorld", resident: Resident, use: UseDefinition) -> bool:
        """Whether a use is the mending of what a resident works with, which nobody goes without
        for want of coin: the settlement that cannot pay a wage does not lose a pair of hands to it."""
        job = world.work.job_of(world, resident)
        worn = self.worn_item(world, resident) if use.repairs > 0 and job is not None and job.tool is not None else None
        return worn is not None and job.tool.tag in world.registries.items.resolve(worn.definition_id).tags

    def patron(
        self, world: "SimulationWorld", resident: Resident, use: UseDefinition, object_id: str | None
    ) -> Resident | None:
        """Whoever would stand a resident a drink they cannot pay for: someone at the same bar
        who is fond of them and has coin to spare. The fondest, if there are several."""
        if object_id is None or use.price <= 0 or use.repairs > 0 or use.sells:
            return None
        needed = self.cost(world, resident, use) + world.registries.economy.gift_savings
        best: tuple[float, Resident] | None = None
        for other in world.residents.values():
            activity = other.activity
            if other is resident or activity is None or not activity.using:
                continue
            if activity.target_id != object_id or activity.action != use.action:
                continue
            if other.credits < needed or other.personality.greed > GIFT_MAX_GREED:
                continue
            feelings = world.relationships.get((other.resident_id, resident.resident_id))
            fondness = feelings.affection if feelings is not None else 0.0
            if fondness >= GIFT_AFFECTION and (best is None or fondness > best[0]):
                best = (fondness, other)
        return best[1] if best is not None else None

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

    def charge(
        self, world: "SimulationWorld", resident: Resident, use: UseDefinition, object_id: str | None = None
    ) -> bool:
        """Take what a use costs a resident. False, and nothing taken, if they have not got it."""
        if world.fund.currency(world) is not None:
            price = self.cost(world, resident, use)
            if self.pay(world, resident, price) or self.on_the_house(world, resident, use):
                return True
            patron = self.patron(world, resident, use, object_id)
            if patron is None or not self.pay(world, patron, price):
                return False
            self._stood(world, patron, resident)
            return True
        if not self.owes_keep(world, resident, use):
            return True
        given = self.token(world, resident)
        if given is None:
            return False
        definition = world.registries.items.resolve(given.definition_id)
        # Handed over where things are kept it stays there. Handed to whoever serves, they carry it.
        if not world.fund.take_in(
            world,
            resident.inventory,
            given,
            resident.tile,
            into=world.containers.get(object_id or ""),
            carrier=self.keeper(world, object_id or ""),
        ):
            return False
        world.emit_event(
            DomainEvent(
                "keep_paid",
                KEEP_IMPORTANCE,
                f"{resident.name}, a quien ya no se mantiene, entrega {definition.article} {definition.name} a cambio",
                [resident.resident_id],
                data={"item_id": definition.item_id},
            ),
            at=resident.tile,
        )
        return True

    def _stood(self, world: "SimulationWorld", patron: Resident, resident: Resident) -> None:
        """Somebody has paid for what another could not: it is said, and not forgotten."""
        feelings = world.relationship(resident.resident_id, patron.resident_id)
        for feeling, delta in TREAT_FEELINGS.items():
            feelings.adjust(feeling, delta)
        world.emit_event(
            DomainEvent(
                "drink_stood",
                TREAT_IMPORTANCE,
                f"{patron.name} invita a {resident.name}",
                [patron.resident_id, resident.resident_id],
            ),
            at=resident.tile,
        )

    # ----- buying over a counter -----

    def price_of(self, world: "SimulationWorld", definition: ItemDefinition, in_stock: int) -> int:
        """What one unit costs new. The fewer there are left, the dearer."""
        economy = world.registries.economy
        scarcity = 1.0 + economy.scarcity_markup / max(1, in_stock)
        return math.ceil(definition.base_value * economy.price_factor * scarcity)

    def price_for(self, world: "SimulationWorld", container: Inventory, item: ItemInstance) -> int:
        """What one unit of a thing on a counter costs: its price new, and less the more worn it is."""
        definition = world.registries.items.resolve(item.definition_id)
        new = self.price_of(world, definition, container.count(item.definition_id))
        return math.ceil(new * world.items.condition_share(world, item))

    def want(self, world: "SimulationWorld", resident: Resident, definition: ItemDefinition, price: float) -> float:
        """How much a resident wants to buy something at a price, from 0 to `MAX_WANT`. Under
        barter the price is what the thing they would give for it is worth to them.

        A tool for their own job when they have none comes first. A weapon is wanted out of fear.
        Anything else is weighed by what it would do for them now against what it costs.
        """
        if definition.category == UNKNOWN_CATEGORY or price <= 0:
            return 0.0
        if definition.substance is not None and world.substances.craves(world, resident, definition.item_id):
            # What they cannot do without, they want above anything, unless they have some by them.
            return 0.0 if self._owned_units(world, resident, definition.item_id) else MAX_WANT
        job = world.work.job_of(world, resident)
        if job is not None and job.tool is not None and job.tool.tag in definition.tags:
            return 0.0 if self._carries_tagged(world, resident, job.tool.tag) else MAX_WANT
        if job is not None and tool_tag(job.job_id) in definition.tags:
            return 0.0 if world.work.tool_of(world, resident, job) is not None else MAX_WANT
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
            price = self.price_for(world, container, item)
            if price > resident.credits:
                continue
            want = self.want(world, resident, definition, price)
            if want >= MIN_WANT and (best is None or want > best[2]):
                best = (item, price, want)
        return best

    def present(
        self, world: "SimulationWorld", resident: Resident, container_id: str
    ) -> tuple[ItemInstance, int, Resident] | None:
        """A present a resident with coin to spare would buy at a counter: the thing, its price
        and who it is for. It is for whoever they are fondest of, and it is what they believe
        that one would like, by what they have seen of their tastes. One present at a time."""
        container = world.containers.get(container_id)
        if container is None or resident.personality.greed > GIFT_MAX_GREED:
            return None
        if any(item.meant_for in world.residents for item in resident.inventory.items):
            return None
        fondest: tuple[float, Resident] | None = None
        for other in world.residents.values():
            feelings = world.relationships.get((resident.resident_id, other.resident_id))
            if other is resident or other.away or feelings is None or feelings.affection < GIFT_AFFECTION:
                continue
            if fondest is None or feelings.affection > fondest[0]:
                fondest = (feelings.affection, other)
        if fondest is None:
            return None
        spare = resident.credits - world.registries.economy.gift_savings
        best: tuple[float, ItemInstance, int] | None = None
        for item in container.items:
            if item.owner_id is not None or item.broken:
                continue
            definition = world.registries.items.resolve(item.definition_id)
            price = self.price_for(world, container, item)
            if definition.category == UNKNOWN_CATEGORY or price > spare:
                continue
            appeal = world.items.gift_appeal(world, resident, fondest[1], definition)
            if best is None or (appeal, item.instance_id) > (best[0], best[1].instance_id):
                best = (appeal, item, price)
        return (best[1], best[2], fondest[1]) if best is not None else None

    def shop_score(self, world: "SimulationWorld", resident: Resident, container_id: str) -> float | None:
        """How much a resident wants to go to a counter for something. None if nothing tempts them."""
        if world.fund.currency(world) is None:
            if world.notices.get(f"{SWAP_REFUSED_NOTICE}{resident.resident_id}") == world.clock.day:
                # They were turned down there today, and will not go and ask again.
                return None
            offers = self.offers(world, resident, container_id)
            return offers[0][0] * SHOP_APPEAL if offers else None
        choice = self.best_buy(world, resident, container_id)
        if choice is not None:
            return choice[2] * SHOP_APPEAL
        return PRESENT_WANT * SHOP_APPEAL if self.present(world, resident, container_id) is not None else None

    def buy(self, world: "SimulationWorld", resident: Resident, container_id: str) -> str | None:
        """Have a resident get the thing they want most from a counter: paid for with a currency,
        had for a thing of their own under barter. With nothing they want for themselves and coin
        to spare, it may be a present for somebody. Returns its definition ID, or None."""
        coin = world.fund.currency(world)
        if coin is None:
            return self.swap(world, resident, container_id)
        choice = self.best_buy(world, resident, container_id)
        gift = self.present(world, resident, container_id) if choice is None else None
        if choice is None and gift is None:
            return None
        item, price = (choice[0], choice[1]) if choice is not None else (gift[0], gift[1])
        if not self.pay(world, resident, price):
            return None
        container = world.containers[container_id]
        definition = world.registries.items.resolve(item.definition_id)
        text = f"{resident.name} compra {definition.article} {definition.name} por {coin.amount(price)}"
        if gift is None:
            hand_over(world, container, item, resident.inventory, resident.resident_id)
        else:
            # A present is kept apart from what is theirs to use, until it is given.
            kept = world.new_item(item.definition_id, 1, resident.resident_id)
            kept.condition, kept.meant_for = item.condition, gift[2].resident_id
            container.take_unit(item.instance_id)
            resident.inventory.add(kept)
            text = f"{text}, para {gift[2].name}"
        room = world.room_at(resident.tile)
        world.emit_event(
            DomainEvent(
                "item_bought",
                PURCHASE_IMPORTANCE,
                text,
                [resident.resident_id],
                location_id=room.room_id if room is not None else None,
                data={
                    "item_id": definition.item_id,
                    "price": price,
                    "for": gift[2].resident_id if gift is not None else None,
                },
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
            (self.worth(world, resident, item), item)
            for item in world.items.spare(world, resident)
            if not item.broken
        ]
        found: list[tuple[float, float, ItemInstance, ItemInstance]] = []
        for wanted in container.items:
            if wanted.owner_id is not None or wanted.broken:
                continue
            definition = resolve(wanted.definition_id)
            worth = self.worth(world, resident, wanted)
            for cost, given in mine:
                if given.definition_id == wanted.definition_id or worth <= cost:
                    continue
                want = self.want(world, resident, definition, max(cost, 1.0))
                if want >= MIN_WANT:
                    found.append((want, cost, wanted, given))
        found.sort(key=lambda offer: (-offer[0], offer[1], offer[2].instance_id, offer[3].instance_id))
        return [(want, wanted, given) for want, _, wanted, given in found]

    def worth(self, world: "SimulationWorld", resident: Resident, item: ItemInstance) -> float:
        """What one thing in particular is worth to somebody, as worn as it is."""
        definition = world.registries.items.resolve(item.definition_id)
        return world.items.personal_value(world, resident, definition, item) * world.items.condition_share(world, item)

    def keeper(self, world: "SimulationWorld", container_id: str) -> Resident | None:
        """Whoever is behind a counter, a bar or a bench right now, to serve at it."""
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
        if keeper is None:
            resolve = world.registries.items.resolve
            share = world.items.condition_share
            return resolve(given.definition_id).base_value * share(world, given) >= resolve(
                wanted.definition_id
            ).base_value * share(world, wanted)
        return self.worth(world, keeper, given) >= self.worth(world, keeper, wanted)

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
        refusals = world.trading.refusals
        refusals[resident.resident_id] = refusals.get(resident.resident_id, 0) + 1
        if refusals[resident.resident_id] >= world.registries.economy.grumble_swaps:
            world.terms.maybe_raise(world, resident)
        return None

    def _carries_tagged(self, world: "SimulationWorld", resident: Resident, tag: str) -> bool:
        return any(tag in world.registries.items.resolve(item.definition_id).tags for item in resident.inventory.items)

    def _owned_units(self, world: "SimulationWorld", resident: Resident, definition_id: str) -> int:
        """How many of something a resident already has for themselves, on them or put away."""
        inventories = [resident.inventory, *world.containers.values()]
        return sum(
            item.quantity
            for inventory in inventories
            for item in inventory.items
            if item.definition_id == definition_id
            and item.owner_id == resident.resident_id
            and item.meant_for is None
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
