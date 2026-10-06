"""Merchants: whoever stops by the gate for a few hours with things to sell and coin to buy with.

Dealing with them for the settlement is the player's to do with their own hands, out of the
common fund and into it: it is the one thing in the settlement that is. What is a resident's
own is theirs to deal with: they go to the gate of their own accord, if they know a merchant is
there, and the player can only put a sale to them.
"""

import math
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from simulation.ai.crowd import free_tile
from simulation.ai.utility_ai import DISTANCE_COST, ScoredAction
from simulation.economy.terms import TradeResult
from simulation.economy.trade_system import BASE_DESIRE, MAX_WANT, MIN_WANT, SHOP_APPEAL
from simulation.events.event import DomainEvent
from simulation.events.world_event import WorldEventDefinition
from simulation.items.inventory import Inventory
from simulation.items.item import ItemInstance
from simulation.items.registry import UNKNOWN_CATEGORY
from simulation.knowledge.fact import SOURCE_PARTICIPANT
from simulation.knowledge.knowledge_system import learn
from simulation.residents.activity import Activity
from simulation.residents.resident import Resident
from simulation.work.hauling import containers_of_kind
from world.pathfinding import find_path, manhattan

if TYPE_CHECKING:
    from simulation.world import SimulationWorld

SALE_PROPOSAL = "sale_proposal"
ADVICE = "encourage"
# Going to the gate to deal with whoever has stopped there, over what is one's own.
VISIT_ACTION = "visit_merchant"
VISIT_MINUTES = 5
VISITED_NOTICE = "merchant:"
ARRIVAL_IMPORTANCE = 45
LEFT_IMPORTANCE = 20
DEAL_IMPORTANCE = 30
SALE_IMPORTANCE = 25
OWN_DEAL_IMPORTANCE = 15
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
    # The fact of their being at the gate, which whoever saw them come knows and can pass on.
    fact_id: str | None = None


@dataclass(frozen=True)
class OwnDeal:
    """What a resident would do with a merchant over what is their own."""

    want: float
    # What they take from the merchant, by item ID, and the thing of theirs they hand over.
    takes: str | None = None
    gives: ItemInstance | None = None
    # The coin they pay. Less than nothing when it is they who are paid.
    coin: int = 0


class MerchantSystem:
    def definition(self, world: "SimulationWorld") -> WorldEventDefinition | None:
        """The event behind whoever is here to trade. None with nobody here."""
        if world.merchant is None:
            return None
        return world.registries.world_events.events.get(world.merchant.event_id)

    def arrive(self, world: "SimulationWorld", definition: WorldEventDefinition, heard: str | None = None) -> None:
        """Have a merchant stop by the gate with what they bring, drawn from their own list.

        Whoever sees them come knows they are there, and so does whoever had word of it, by the
        fact `heard`, from a radio. The rest have to be told.
        """
        goods = world.happenings.draw_goods(world, definition)
        leaves_at = world.clock.total_minutes + world.event_rng.randint(*definition.minutes)
        world.merchant = Merchant(
            definition.event_id, leaves_at, goods, float(world.event_rng.randint(*definition.purse))
        )
        brought = self._listed(world, goods) or "nada"
        fact = world.emit_event(
            DomainEvent(
                "merchant_arrived",
                ARRIVAL_IMPORTANCE,
                f"{definition.text}: {brought}",
                data={"event_id": definition.event_id, "goods": dict(goods)},
            ),
            at=world.happenings.arrival_tile(world),
            fact_text=f"hay {definition.name} en la puerta",
            expires_at=leaves_at,
        )
        if fact is None:
            return
        world.merchant.fact_id = fact.fact_id
        for resident in world.residents.values():
            if heard is not None and world.knowledge.knows(resident.resident_id, heard):
                learn(world, resident, fact, 1.0, SOURCE_PARTICIPANT)

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

    def gives(self, world: "SimulationWorld", item_id: str, item: ItemInstance | None = None) -> int:
        """What whoever is here gives for one unit of a thing: less for one in particular the more
        worn it is, and nothing for what they have no use for."""
        definition = self.definition(world)
        kind = world.registries.items.find(item_id)
        if definition is None or kind is None or kind.category == UNKNOWN_CATEGORY:
            return 0
        share = world.items.condition_share(world, item) if item is not None else 1.0
        return math.floor(kind.base_value * definition.buys_at * share)

    # ----- the settlement's own dealings -----

    def deal(self, world: "SimulationWorld", sell: Mapping[str, int], buy: Mapping[str, int]) -> TradeResult:
        """Sell a merchant things that are nobody's and buy things from them, in one go.

        With a currency the difference is settled in it, out of the fund or into it. Under barter
        what is handed over has to be worth at least what is taken, and nothing comes back for
        the rest. Either all of it is done or none of it. What is bought waits at the gate for
        whoever keeps the till to carry in, or goes straight where things are kept if nobody does.
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
        earned = sum(
            world.fund.worth_of_goods(world, item_id, units, self.gives(world, item_id))
            for item_id, units in sold.items()
        )
        owed = sum(units * self.asks(world, item_id) for item_id, units in bought.items())
        carried_in = world.fund.someone_fetches(world)
        store = self._store(world, definition)
        if bought and store is None and not carried_in:
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
            if carried_in:
                world.at_gate[item_id] = world.at_gate.get(item_id, 0) + units
            else:
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

    # ----- what is somebody's own, put to them -----

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
        offered = self.gives(world, item.definition_id, item)
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
        own_worth = world.trade.worth(world, resident, item)
        # An even deal by their own lights is half way: twice what it is worth to them, or more, is all the way.
        bargain = min(1.0, worth / (2.0 * own_worth)) if own_worth > 0 else 1.0
        outcome = world.interventions.put_to(
            world, resident, SALE_PROPOSAL, f"{thing} por {price}", {"bargain": bargain}, option_id
        )
        if outcome is None or not outcome.agrees:
            return TradeResult(False, f"{resident.name} no quiere vender {thing}")
        self._hand_to_merchant(merchant, holder, item)
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

    # ----- what is somebody's own, of their own accord -----

    def own_deal(self, world: "SimulationWorld", resident: Resident) -> OwnDeal | None:
        """The dealing a resident would most like to do with whoever is at the gate, over what is theirs.

        With a currency they buy a thing they want at what is asked for it, or sell one that
        fetches more than it is worth to them. Under barter they give a thing for one worth more
        to them, if the merchant does not lose by it.
        """
        merchant = world.merchant
        if merchant is None or self.definition(world) is None:
            return None
        resolve = world.registries.items.resolve
        spare = [item for item in world.items.spare(world, resident) if not item.broken]
        deals: list[tuple[float, str, OwnDeal]] = []
        if world.fund.currency(world) is not None:
            for item_id in merchant.goods:
                asked = self.asks(world, item_id)
                want = world.trade.want(world, resident, resolve(item_id), asked) if asked <= resident.credits else 0.0
                if want >= MIN_WANT:
                    deals.append((want, item_id, OwnDeal(want, takes=item_id, coin=asked)))
            for item in spare:
                offered, own = self.gives(world, item.definition_id, item), world.trade.worth(world, resident, item)
                if offered <= 0 or offered > merchant.purse or offered <= own:
                    continue
                want = min(MAX_WANT, offered / own * BASE_DESIRE) if own > 0 else MAX_WANT
                if want >= MIN_WANT:
                    deals.append((want, item.instance_id, OwnDeal(want, gives=item, coin=-offered)))
        else:
            for item in spare:
                offered, own = self.gives(world, item.definition_id, item), world.trade.worth(world, resident, item)
                for item_id in merchant.goods:
                    wanted = resolve(item_id)
                    if self.asks(world, item_id) > offered or item_id == item.definition_id:
                        continue
                    if world.items.personal_value(world, resident, wanted) <= own:
                        continue
                    want = world.trade.want(world, resident, wanted, max(own, 1.0))
                    if want >= MIN_WANT:
                        deals.append((want, f"{item_id}:{item.instance_id}", OwnDeal(want, takes=item_id, gives=item)))
        if not deals:
            return None
        return max(deals, key=lambda deal: (deal[0], deal[1]))[2]

    def candidate(self, world: "SimulationWorld", resident: Resident) -> ScoredAction | None:
        """Going to the gate to deal with a merchant, for a resident who knows one is there, has
        not been yet, and has something to do there."""
        merchant = world.merchant
        if merchant is None or merchant.fact_id is None:
            return None
        if world.notices.get(f"{VISITED_NOTICE}{resident.resident_id}") == merchant.leaves_at:
            return None
        if not world.knowledge.knows(resident.resident_id, merchant.fact_id):
            return None
        deal = self.own_deal(world, resident)
        if deal is None:
            return None
        gate = world.happenings.arrival_tile(world)
        return ScoredAction(VISIT_ACTION, deal.want * SHOP_APPEAL - DISTANCE_COST * manhattan(resident.tile, gate))

    def plan(self, world: "SimulationWorld", resident: Resident) -> Activity | None:
        """The walk to the gate, where whoever has stopped to trade is."""
        spot = free_tile(world, world.happenings.arrival_tile(world), resident)
        path = find_path(resident.tile, spot, world.passable())
        if path is None:
            return None
        return Activity(VISIT_ACTION, None, path, VISIT_MINUTES)

    def visit_tick(self, world: "SimulationWorld", resident: Resident, activity: Activity) -> None:
        """Spend one minute at the gate with a merchant: the dealing is done on getting there."""
        if not activity.using:
            merchant = world.merchant
            deal = self.own_deal(world, resident)
            if merchant is None or deal is None:
                resident.activity, resident.current_action = None, "idle"
                return
            # Once is enough for one caravan, whatever came of it.
            world.notices[f"{VISITED_NOTICE}{resident.resident_id}"] = merchant.leaves_at
            self._do_own(world, resident, merchant, deal)
            activity.using = True
            resident.current_action = VISIT_ACTION
        activity.minutes_left -= 1
        if activity.minutes_left <= 0:
            resident.activity, resident.current_action = None, "idle"

    def _do_own(self, world: "SimulationWorld", resident: Resident, merchant: Merchant, deal: OwnDeal) -> None:
        definition = self.definition(world)
        who = definition.name if definition is not None else "el mercader"
        coin = world.fund.currency(world)
        resolve = world.registries.items.resolve
        given = resolve(deal.gives.definition_id) if deal.gives is not None else None
        taken = resolve(deal.takes) if deal.takes is not None else None
        if deal.gives is not None:
            self._hand_to_merchant(merchant, resident.inventory, deal.gives)
        if deal.takes is not None:
            self._take(merchant, deal.takes, 1)
            world.stock(resident.inventory, deal.takes, 1, resident.resident_id)
        resident.credits -= deal.coin
        merchant.purse += deal.coin
        paid = coin.amount(abs(deal.coin)) if coin is not None else ""
        if given is not None and taken is not None:
            kind, text = "item_sold", f"{resident.name} le cambia {given.article} {given.name} a {who} por {taken.article} {taken.name}"
        elif taken is not None:
            kind, text = "item_bought", f"{resident.name} le compra {taken.article} {taken.name} a {who} por {paid}"
        else:
            kind, text = "item_sold", f"{resident.name} le vende {given.article} {given.name} a {who} por {paid}"
        world.emit_event(
            DomainEvent(
                kind,
                OWN_DEAL_IMPORTANCE,
                text,
                [resident.resident_id],
                data={
                    "item_id": (taken or given).item_id,
                    "for_item": taken.item_id if given is not None and taken is not None else None,
                    "price": abs(deal.coin),
                    "merchant": merchant.event_id,
                },
            ),
            at=resident.tile,
        )
        if taken is not None:
            world.tastes.bought(world, resident, taken)

    # ----- particulars -----

    def _own(self, world: "SimulationWorld", resident: Resident, instance_id: str) -> tuple[Inventory, ItemInstance] | None:
        """A thing of a resident's own in working order, on them or put away, and where it is."""
        for holder in (resident.inventory, *world.containers.values()):
            item = holder.find(instance_id)
            if item is not None and item.owner_id == resident.resident_id and not item.broken:
                return (holder, item)
        return None

    def _hand_to_merchant(self, merchant: Merchant, holder: Inventory, item: ItemInstance) -> None:
        """Have one unit of a thing leave whoever held it for the merchant's own goods."""
        if item.quantity > 1:
            item.quantity -= 1
        else:
            holder.remove(item.instance_id)
        merchant.goods[item.definition_id] = merchant.goods.get(item.definition_id, 0) + 1

    def _store(self, world: "SimulationWorld", definition: WorldEventDefinition) -> Inventory | None:
        """Where what is bought is left when nobody carries it in: the kind of container the
        event names, or else the one nearest the way in."""
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
