"""Merchants: whoever stops by the gate for a few hours with things to sell and coin to buy with.

Dealing with them is the player's to do with their own hands, out of the common fund and into
it: it is the one thing in the settlement that is. What is a resident's own is theirs to sell or
not, so that can only be put to them.
"""

import math
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from simulation.economy.terms import TradeResult
from simulation.events.event import DomainEvent
from simulation.events.world_event import WorldEventDefinition
from simulation.items.inventory import Inventory
from simulation.items.item import ItemInstance
from simulation.items.registry import UNKNOWN_CATEGORY
from simulation.residents.resident import Resident
from simulation.work.hauling import containers_of_kind

if TYPE_CHECKING:
    from simulation.world import SimulationWorld

SALE_PROPOSAL = "sale_proposal"
ADVICE = "encourage"
ARRIVAL_IMPORTANCE = 45
LEFT_IMPORTANCE = 20
DEAL_IMPORTANCE = 30
SALE_IMPORTANCE = 25
NOBODY = "No hay nadie de fuera con quien tratar"
OBSTACLES = {"deciding": "tiene algo que decidir", "asked_recently": "se lo preguntaron hace poco"}


@dataclass
class Merchant:
    """Someone from outside who has stopped to trade, and what they have with them."""

    # The world event that brought them, which says what they ask and give for things.
    event_id: str
    # Game minute at which they move on.
    leaves_at: int
    # Units of each kind of thing they have to sell, by item ID.
    goods: dict[str, int] = field(default_factory=dict)
    # The coin they have to buy with.
    purse: float = 0.0


class MerchantSystem:
    def definition(self, world: "SimulationWorld") -> WorldEventDefinition | None:
        """The event behind whoever is here to trade. None with nobody here."""
        if world.merchant is None:
            return None
        return world.registries.world_events.events.get(world.merchant.event_id)

    def arrive(self, world: "SimulationWorld", definition: WorldEventDefinition) -> None:
        """Have a merchant stop by the gate with what they bring, drawn from their own list."""
        goods = world.happenings.draw_goods(world, definition)
        world.merchant = Merchant(
            definition.event_id,
            world.clock.total_minutes + world.event_rng.randint(*definition.minutes),
            goods,
            float(world.event_rng.randint(*definition.purse)),
        )
        brought = self._listed(world, goods) or "nada"
        world.emit_event(
            DomainEvent(
                "merchant_arrived",
                ARRIVAL_IMPORTANCE,
                f"{definition.text}: {brought}",
                data={"event_id": definition.event_id, "goods": dict(goods)},
            )
        )

    def tick(self, world: "SimulationWorld") -> None:
        """Have whoever stopped to trade move on once their time is up."""
        merchant = world.merchant
        if merchant is None or world.clock.total_minutes < merchant.leaves_at:
            return
        definition = self.definition(world)
        world.merchant = None
        if definition is not None and definition.end_text:
            world.emit_event(DomainEvent("merchant_left", LEFT_IMPORTANCE, definition.end_text))

    # ----- what things go for -----

    def asks(self, world: "SimulationWorld", item_id: str) -> int:
        """What whoever is here asks for one unit of a thing, in what things are worth."""
        definition = self.definition(world)
        item = world.registries.items.find(item_id)
        if definition is None or item is None:
            return 0
        return math.ceil(item.base_value * definition.sells_at)

    def gives(self, world: "SimulationWorld", item_id: str) -> int:
        """What whoever is here gives for one unit of a thing. Nothing for what they have no use for."""
        definition = self.definition(world)
        item = world.registries.items.find(item_id)
        if definition is None or item is None or item.category == UNKNOWN_CATEGORY:
            return 0
        return math.floor(item.base_value * definition.buys_at)

    # ----- the settlement's own dealings -----

    def deal(self, world: "SimulationWorld", sell: Mapping[str, int], buy: Mapping[str, int]) -> TradeResult:
        """Sell a merchant things that are nobody's and buy things from them, in one go.

        With a currency the difference is settled in it, out of the fund or into it. Under barter
        what is handed over has to be worth at least what is taken, and nothing comes back for
        the rest. Either all of it is done or none of it.
        """
        merchant, definition = world.merchant, self.definition(world)
        if merchant is None or definition is None:
            return TradeResult(False, NOBODY)
        sold = {str(item_id): int(units) for item_id, units in sell.items() if int(units) > 0}
        bought = {str(item_id): int(units) for item_id, units in buy.items() if int(units) > 0}
        if not sold and not bought:
            return TradeResult(False, "No hay nada que tratar")
        who = definition.name
        held = world.fund.goods(world)
        resolve = world.registries.items.resolve
        for item_id, units in sold.items():
            if held.get(item_id, 0) < units:
                return TradeResult(False, f"No hay tanto que no sea de nadie: {resolve(item_id).name}")
            if self.gives(world, item_id) <= 0:
                return TradeResult(False, f"{who.capitalize()} no da nada por eso: {resolve(item_id).name}")
        for item_id, units in bought.items():
            if merchant.goods.get(item_id, 0) < units:
                return TradeResult(False, f"{who.capitalize()} no lleva tanto: {resolve(item_id).name}")
        earned = sum(units * self.gives(world, item_id) for item_id, units in sold.items())
        owed = sum(units * self.asks(world, item_id) for item_id, units in bought.items())
        store = self._store(world, definition)
        if bought and store is None:
            return TradeResult(False, "No hay donde dejar lo que se compre")
        coin = world.fund.currency(world)
        settled = ""
        if coin is None:
            if earned < owed:
                return TradeResult(
                    False, f"{who.capitalize()} pide más a cambio: lo que se le da vale {earned} y lo que se pide, {owed}"
                )
        elif owed > earned:
            short = owed - earned - world.trading.fund
            if short > 0:
                return TradeResult(False, f"El fondo no alcanza: faltan {coin.amount(math.ceil(short))}")
            merchant.purse += world.fund.pay_out(world, owed - earned)
            settled = f"; el fondo paga {coin.amount(owed - earned)}"
        elif earned > owed:
            short = earned - owed - merchant.purse
            if short > 0:
                return TradeResult(False, f"{who.capitalize()} no lleva tanto encima: le faltan {coin.amount(math.ceil(short))}")
            merchant.purse -= earned - owed
            world.fund.pay_in(world, earned - owed)
            settled = f"; el fondo cobra {coin.amount(earned - owed)}"
        for item_id, units in sold.items():
            world.fund.take_goods(world, item_id, units)
            merchant.goods[item_id] = merchant.goods.get(item_id, 0) + units
        for item_id, units in bought.items():
            self._take(merchant, item_id, units)
            world.stock(store, item_id, units, None)
        parts = []
        if sold:
            parts.append(f"se le vende {self._listed(world, sold)}")
        if bought:
            parts.append(f"se le compra {self._listed(world, bought)}")
        text = f"Trato con {who}: {' y '.join(parts)}{settled}"
        world.emit_event(
            DomainEvent(
                "merchant_deal",
                DEAL_IMPORTANCE,
                text,
                data={"sold": sold, "bought": bought, "paid": owed - earned if coin is not None else 0},
            )
        )
        return TradeResult(True, text)

    # ----- what is somebody's own -----

    def propose_sale(
        self,
        world: "SimulationWorld",
        resident_id: str,
        item_id: str,
        for_item: str | None = None,
        option_id: str = ADVICE,
    ) -> TradeResult:
        """Put it to a resident that they sell a merchant a thing of their own. They weigh it and answer.

        What it fetches is theirs: coin, or under barter one of what the merchant brings, which
        is `for_item`. They go by what the thing is worth to them against what they would get.
        """
        merchant, definition = world.merchant, self.definition(world)
        if merchant is None or definition is None:
            return TradeResult(False, NOBODY)
        resident = world.residents.get(resident_id)
        if resident is None or resident.away:
            return TradeResult(False, "No está para preguntárselo")
        found = self._own(world, resident, item_id)
        if found is None:
            return TradeResult(False, "Eso no es suyo para venderlo")
        holder, item = found
        thing_definition = world.registries.items.resolve(item.definition_id)
        thing = f"{thing_definition.article} {thing_definition.name}"
        who = definition.name
        offered = self.gives(world, item.definition_id)
        if offered <= 0:
            return TradeResult(False, f"{who.capitalize()} no da nada por eso: {thing_definition.name}")
        coin = world.fund.currency(world)
        if coin is not None:
            if merchant.purse < offered:
                return TradeResult(False, f"{who.capitalize()} no lleva tanto encima")
            worth, price, for_item = float(offered), coin.amount(offered), None
        else:
            wanted = world.registries.items.find(for_item or "")
            if wanted is None or merchant.goods.get(wanted.item_id, 0) < 1:
                return TradeResult(False, f"Hay que decir qué se lleva a cambio, de lo que trae {who}")
            if offered < self.asks(world, wanted.item_id):
                return TradeResult(False, f"{who.capitalize()} no da eso por tan poco: {wanted.name}")
            worth, price, for_item = (
                world.items.personal_value(world, resident, wanted),
                f"{wanted.article} {wanted.name}",
                wanted.item_id,
            )
        obstacle = world.interventions.asking_obstacle(world, resident, SALE_PROPOSAL)
        if obstacle is not None:
            return TradeResult(False, f"{resident.name} {OBSTACLES.get(obstacle, 'no puede decidirlo ahora')}")
        own_worth = world.items.personal_value(world, resident, thing_definition, item)
        # An even deal by their own lights is half way: twice what it is worth to them, or more, is all the way.
        bargain = min(1.0, worth / (2.0 * own_worth)) if own_worth > 0 else 1.0
        outcome = world.interventions.put_to(
            world, resident, SALE_PROPOSAL, f"{thing} por {price}", {"bargain": bargain}, option_id
        )
        if outcome is None or not outcome.agrees:
            return TradeResult(False, f"{resident.name} no quiere vender {thing}")
        if item.quantity > 1:
            item.quantity -= 1
        else:
            holder.remove(item.instance_id)
        merchant.goods[item.definition_id] = merchant.goods.get(item.definition_id, 0) + 1
        if for_item is None:
            merchant.purse -= offered
            resident.credits += offered
        else:
            self._take(merchant, for_item, 1)
            world.stock(resident.inventory, for_item, 1, resident.resident_id)
        text = f"{resident.name} le vende {thing} a {who} por {price}"
        world.emit_event(
            DomainEvent(
                "item_sold",
                SALE_IMPORTANCE,
                text,
                [resident.resident_id],
                data={"item_id": item.definition_id, "for_item": for_item, "price": offered if for_item is None else 0},
            ),
            at=resident.tile,
        )
        return TradeResult(True, text)

    # ----- particulars -----

    def _own(self, world: "SimulationWorld", resident: Resident, instance_id: str) -> tuple[Inventory, ItemInstance] | None:
        """A thing of a resident's own in working order, on them or put away, and where it is."""
        for holder in (resident.inventory, *world.containers.values()):
            item = holder.find(instance_id)
            if item is not None and item.owner_id == resident.resident_id and not item.broken:
                return (holder, item)
        return None

    def _store(self, world: "SimulationWorld", definition: WorldEventDefinition) -> Inventory | None:
        """Where what is bought is left: the kind of container the event names, or else the one nearest the way in."""
        named = containers_of_kind(world, definition.container or "")
        if named:
            return named[0][1]
        nearest = world.nearest_container(world.happenings.arrival_tile(world))
        return world.containers.get(nearest or "")

    def _take(self, merchant: Merchant, item_id: str, units: int) -> None:
        merchant.goods[item_id] = merchant.goods.get(item_id, 0) - units
        if merchant.goods[item_id] <= 0:
            del merchant.goods[item_id]

    def _listed(self, world: "SimulationWorld", goods: Mapping[str, int]) -> str:
        return ", ".join(f"{world.registries.items.resolve(item_id).name} ({units})" for item_id, units in goods.items())
