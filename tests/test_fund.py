import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from save.save_manager import SaveManager
from simulation.commands import (
    DealWithMerchantCommand,
    FoundResidentCommand,
    ProposeBarterCommand,
    ProposeCurrencyCommand,
    ProposeSaleCommand,
)
from simulation.economy.merchant import Merchant
from simulation.economy.pilfering import FUND_THEFT_ACTION, PILFER_ACTION
from simulation.economy.settings import economy_settings_from_data
from simulation.economy.terms import TradingState
from simulation.events.decision import decision_definition_from_data
from simulation.events.world_event import world_event_settings_from_data
from simulation.items.theft import FUND_VICTIM
from simulation.knowledge.fact import SOURCE_WITNESS
from simulation.knowledge.knowledge_system import learn
from simulation.registries import DATA_DIR, BuiltInRegistries
from simulation.residents.activity import Activity
from simulation.residents.needs import Needs
from simulation.residents.personality import Personality
from simulation.residents.resident import Resident
from simulation.rng import SimulationRNG
from simulation.tastes.taste import ITEM, Taste
from simulation.tutorial.tutorial import TutorialState
from simulation.work.work_system import WORK_ACTION
from simulation.world import SimulationWorld

ROOT = Path(__file__).resolve().parent.parent
MINUTES_PER_DAY = 24 * 60
COUNTER = "shop_counter"
# Somewhere out in the open, far from the dormitory and from the shop.
FAR_AWAY = (30, 15)
BESIDE_THE_COUNTER = (17, 4)


class _Certain(SimulationRNG):
    """A generator of world events for which whatever can happen does, at the first chance."""

    def random(self) -> float:
        return 0.0


def _content(world: SimulationWorld, *resident_ids: str) -> None:
    for resident_id in resident_ids or world.residents:
        world.residents[resident_id].needs = Needs(hunger=0, tiredness=0, social=0, stress=0)


def _settled(seed: int = 7) -> SimulationWorld:
    """The settlement that comes ready made, with everyone content and no grudges."""
    world = SimulationWorld.demo_world(seed=seed)
    world.relationships.clear()
    _content(world)
    return world


def _bartering(world: SimulationWorld) -> SimulationWorld:
    """The same settlement as it would be had it never taken up a currency."""
    world.trading = TradingState()
    for resident in world.residents.values():
        resident.credits = 0.0
    return world


def _few(world: SimulationWorld) -> SimulationWorld:
    """Leave only Marta, Raúl and Lucía, with no jobs, nothing put by in a crate and nothing to do."""
    for extra in [resident_id for resident_id in world.residents if resident_id not in ("marta", "raul", "lucia")]:
        del world.residents[extra]
    for resident in world.residents.values():
        resident.job_id = resident.post_id = None
    for container_id in ("cooking_pot", "crate_dorm", "crate_1"):
        world.containers[container_id].items.clear()
    return world


def _place(world: SimulationWorld, resident_id: str, tile: tuple[int, int]) -> Resident:
    resident = world.residents[resident_id]
    resident.x, resident.y = tile
    return resident


def _put_on_duty(world: SimulationWorld, resident_id: str, minutes: int = 600) -> Resident:
    """Stand a resident at their post, already at work."""
    resident = world.residents[resident_id]
    post = world.interactables[resident.post_id]
    passable = world.passable()
    resident.x, resident.y = next(
        (post.x + dx, post.y + dy)
        for dx, dy in ((0, 1), (0, -1), (-1, 0), (1, 0))
        if passable((post.x + dx, post.y + dy))
    )
    resident.activity = Activity(WORK_ACTION, resident.post_id, minutes_left=minutes, using=True)
    resident.current_action = WORK_ACTION
    return resident


def _asleep(world: SimulationWorld, resident_id: str, bed_id: str = "bed_1") -> Resident:
    """Put a resident to bed, tired enough to sleep through the next few hours."""
    resident = world.residents[resident_id]
    bed = world.interactables[bed_id]
    resident.x, resident.y = bed.x, bed.y
    resident.needs.tiredness = 90.0
    resident.activity = Activity("sleep", bed_id, minutes_left=600, using=True)
    resident.current_action = "sleep"
    return resident


def _types(world: SimulationWorld) -> list[str]:
    return [line.split(" | ")[1] for line in world.event_log]


def _use(world: SimulationWorld, kind: str):
    return world.registries.interactables.get(kind).use


def _go_and_use(world: SimulationWorld, resident: Resident, object_id: str, until: str, limit: int = 90) -> None:
    """Send a resident to use an object and let time pass until an event of a type is given."""
    resident.activity = world.activities.routine._use(world, resident, world.interactables[object_id])
    seen = _types(world).count(until)
    for _ in range(limit):
        world.step(1)
        if _types(world).count(until) > seen:
            return
    raise AssertionError(f"{resident.name} never got as far as {until}")


def _held(world: SimulationWorld) -> float:
    """All the coin there is in the settlement: in every pocket and in the fund."""
    return world.trading.fund + sum(resident.credits for resident in world.residents.values())


def _registries_with(file_name: str, old: str, new: str) -> BuiltInRegistries:
    """Registries loaded from a copy of the data folder with one piece of text replaced."""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "data"
        (root / "maps").mkdir(parents=True)
        for path in DATA_DIR.rglob("*.json"):
            text = path.read_text(encoding="utf-8")
            if path.name == file_name:
                assert old in text, old
                text = text.replace(old, new)
            (root / path.relative_to(DATA_DIR)).write_text(text, encoding="utf-8")
        return BuiltInRegistries.load(root)


def _caravan(world: SimulationWorld, goods: dict[str, int], purse: float = 30.0) -> Merchant:
    """Have a caravan standing by the gate with these things and this much coin."""
    world.merchant = Merchant("caravan", world.clock.total_minutes + 300, dict(goods), purse)
    return world.merchant


class FundTests(unittest.TestCase):
    def setUp(self) -> None:
        self.world = _settled()
        self.economy = self.world.registries.economy

    def test_a_settlement_that_is_already_running_has_a_fund_and_trades_with_its_credits(self) -> None:
        coin = self.world.fund.currency(self.world)
        self.assertEqual((coin.name, coin.singular), ("vales", "vale"))
        self.assertEqual((coin.amount(1), coin.amount(12.9)), ("1 vale", "12 vales"))
        self.assertEqual(self.world.trading.fund, self.economy.fund_per_resident * len(self.world.residents))

    def test_a_purchase_adds_to_the_fund_what_it_cost(self) -> None:
        marta = self.world.residents["marta"]
        self.world.relationship("marta", "raul").fear = 60
        marta.credits = 50.0
        before, held = self.world.trading.fund, _held(self.world)
        self.assertEqual(self.world.trade.buy(self.world, marta, COUNTER), "rusty_knife")
        self.assertEqual(marta.credits, 10.0)
        self.assertEqual(self.world.trading.fund - before, 40.0)
        self.assertEqual(_held(self.world), held, "what was paid is not gone: the settlement has it")

    def test_a_drink_and_a_repair_are_paid_into_the_fund_too(self) -> None:
        ines = self.world.residents["ines"]
        before = self.world.trading.fund
        for kind in ("bar", "workbench"):
            self.assertTrue(self.world.trade.charge(self.world, ines, _use(self.world, kind)))
        self.assertEqual(self.world.trading.fund - before, 6.0)
        ines.credits = 1.0
        self.assertFalse(self.world.trade.charge(self.world, ines, _use(self.world, "bar")))
        self.assertEqual((ines.credits, self.world.trading.fund - before), (1.0, 6.0), "nothing is taken from the broke")

    def test_wages_come_out_of_the_fund_and_stop_when_it_is_empty(self) -> None:
        tomas = _put_on_duty(self.world, "tomas")
        self.world.clock.hour = 9
        before, held = tomas.credits, _held(self.world)
        for _ in range(60):
            self.world.step(1)
            _content(self.world)
        self.assertAlmostEqual(tomas.credits - before, self.economy.wage_per_hour)
        self.assertAlmostEqual(_held(self.world), held)

        self.world.trading.fund = 0.25
        for resident in self.world.residents.values():
            resident.credits = 0.0
        for _ in range(90):
            self.world.step(1)
            _content(self.world)
            self.assertGreaterEqual(self.world.trading.fund, 0.0)
        self.assertEqual(self.world.trading.fund, 0.0)
        self.assertAlmostEqual(sum(resident.credits for resident in self.world.residents.values()), 0.25)
        self.assertEqual(_types(self.world).count("wages_unpaid"), 1, "said once a day")

    def test_a_week_with_a_currency_pays_wages_from_the_fund_and_takes_back_what_is_spent(self) -> None:
        world = SimulationWorld.demo_world(seed=3)
        started, pocket = _held(world), world.registries.economy.starting_credits
        lowest = world.trading.fund
        for _ in range(7 * MINUTES_PER_DAY):
            world.step(1)
            lowest = min(lowest, world.trading.fund)
        self.assertGreaterEqual(lowest, 0.0, "the fund never goes below nothing")
        types = _types(world)
        self.assertIn("item_bought", types)
        self.assertEqual(len(world.deaths), 0)
        joined = types.count("newcomer_joined")
        # No coin is made or lost: it goes round. Only whoever walks in brings some.
        self.assertAlmostEqual(_held(world), started + joined * pocket, places=6)
        self.assertLess(world.trading.fund, started, "wages were paid out of it")
        self.assertTrue(all(resident.credits != pocket for resident in world.residents.values()), "everyone earned")


class WorkingToolTests(unittest.TestCase):
    """Found by running ten weeks with a fund that can run dry: farmers made presents of the hoes
    they worked with and could not buy another, or could not pay to have theirs mended, and the
    garden fed nobody."""

    def setUp(self) -> None:
        self.world = _settled()
        self.raul, self.marta = self.world.residents["raul"], self.world.residents["marta"]
        self.hoe = self.raul.inventory.stack_of("hoe", "raul")

    def test_nobody_gives_or_swaps_away_the_tool_they_work_with(self) -> None:
        self.assertEqual(self.world.items.owned(self.world, self.raul), [self.hoe])
        self.assertEqual(self.world.items.spare(self.world, self.raul), [])
        self.world.stock(self.marta.inventory, "rusty_knife", 1, "marta")
        self.assertIsNone(self.world.items.propose_trade(self.world, self.raul, self.marta))
        self.assertIsNone(self.world.items.propose_trade(self.world, self.marta, self.raul))
        self.world.relationship("raul", "marta").affection = 90
        chat = self.world.registries.interactions["chat"]
        for _ in range(200):
            self.world.items.after_exchange(self.world, self.raul, self.marta, chat)
        self.assertIs(self.raul.inventory.find(self.hoe.instance_id), self.hoe)
        self.assertNotIn("gift_given", _types(self.world))

    def test_a_tool_they_have_besides_it_is_theirs_to_give(self) -> None:
        second = self.world.new_item("hoe", owner_id="raul")
        self.raul.inventory.add(second)
        self.assertEqual(self.world.items.spare(self.world, self.raul), [second])
        self.hoe.condition = 0.0
        self.assertEqual(self.world.items.spare(self.world, self.raul), [self.hoe], "the one that works is the one kept")
        self.raul.job_id = None
        self.assertEqual(self.world.items.spare(self.world, self.raul), [self.hoe, second], "with no job it is a thing like any")

    def test_the_tool_they_work_with_is_mended_even_when_they_cannot_pay_for_it(self) -> None:
        bench = _use(self.world, "workbench")
        self.hoe.condition = 20.0
        self.raul.credits = 0.0
        fund = self.world.trading.fund
        self.assertTrue(self.world.trade.can_afford(self.world, self.raul, bench))
        self.assertTrue(self.world.trade.charge(self.world, self.raul, bench))
        self.assertEqual((self.raul.credits, self.world.trading.fund), (0.0, fund))
        self.raul.credits = 10.0
        self.assertTrue(self.world.trade.charge(self.world, self.raul, bench))
        self.assertEqual((self.raul.credits, self.world.trading.fund), (6.0, fund + 4.0), "whoever can pay does")

        self.raul.credits = 0.0
        self.assertFalse(self.world.trade.can_afford(self.world, self.raul, _use(self.world, "bar")))
        radio = self.world.stock(self.marta.inventory, "old_radio", 1, "marta")
        radio.condition, self.marta.credits = 20.0, 0.0
        self.assertFalse(self.world.trade.can_afford(self.world, self.marta, bench), "a radio is not what she works with")
        self.raul.job_id = None
        self.assertFalse(self.world.trade.can_afford(self.world, self.raul, bench), "nor is a hoe, to someone with no garden")

    def test_a_farmer_with_an_empty_pocket_comes_back_from_the_workshop_with_a_mended_hoe(self) -> None:
        self.hoe.condition = 20.0
        self.world.clock.hour = 10
        _put_on_duty(self.world, "paco")
        self.raul.job_id, self.raul.credits = "farmer", 0.0
        self.raul.activity = self.world.activities.routine._use(self.world, self.raul, self.world.interactables["workbench"])
        for _ in range(150):
            self.world.step(1)
            _content(self.world)
            if self.hoe.condition >= 100.0:
                break
        self.assertEqual((self.hoe.condition, self.raul.credits), (100.0, 0.0))


class BarterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.world = _bartering(_settled())
        self.ines, self.nuria = self.world.residents["ines"], self.world.residents["nuria"]
        self.shop = self.world.containers[COUNTER]

    def test_a_new_settlement_starts_on_barter_with_no_coin_anywhere(self) -> None:
        world = SimulationWorld.new_settlement()
        self.assertIsNone(world.fund.currency(world))
        founder = world.residents[world.apply_command(FoundResidentCommand("Ada", 34, {}, []))]
        self.assertEqual((founder.credits, world.trading.fund, world.trading.currency), (0.0, 0.0, None))

    def test_whoever_holds_a_job_is_kept_and_earns_nothing(self) -> None:
        tomas = _put_on_duty(self.world, "tomas")
        self.world.clock.hour = 9
        for _ in range(60):
            self.world.step(1)
            _content(self.world)
        self.assertEqual((tomas.credits, self.world.trading.fund), (0.0, 0.0))
        for kind in ("bar", "workbench", "cooking_pot"):
            use = _use(self.world, kind)
            self.assertTrue(self.world.trade.can_afford(self.world, self.ines, use), kind)
            self.assertTrue(self.world.trade.charge(self.world, self.ines, use), kind)
        self.assertNotIn("keep_paid", _types(self.world))

    def test_whoever_holds_no_job_gives_a_thing_for_what_has_a_price_or_goes_without(self) -> None:
        self.ines.job_id = None
        self.ines.inventory.items.clear()
        bar = _use(self.world, "bar")
        self.assertFalse(self.world.trade.can_afford(self.world, self.ines, bar))
        self.assertFalse(self.world.trade.charge(self.world, self.ines, bar))
        self.world.stock(self.ines.inventory, "scrap", 1, "ines")
        radio = self.world.stock(self.ines.inventory, "old_radio", 1, "ines")
        before = self.shop.count("scrap")
        self.assertTrue(self.world.trade.can_afford(self.world, self.ines, bar))
        self.assertTrue(self.world.trade.charge(self.world, self.ines, bar))
        self.assertEqual(self.ines.inventory.items, [radio], "it is what is worth least to them that they part with")
        self.assertEqual(self.shop.count("scrap") - before, 1)
        self.assertIsNone(self.shop.stack_of("scrap", "ines"), "what was handed over is the settlement's now")
        self.assertEqual(_types(self.world).count("keep_paid"), 1)

    def test_whoever_holds_no_job_gives_a_thing_for_a_meal_and_is_fed_all_the_same_with_nothing(self) -> None:
        self.ines.job_id = None
        self.ines.inventory.items.clear()
        self.world.stock(self.ines.inventory, "scrap", 1, "ines")
        self.world.clock.hour = 13
        for expected in ("keep_paid", "keep_unpaid"):
            self.ines.needs.hunger = 80
            _go_and_use(self.world, self.ines, "cooking_pot", "meal_started")
            self.assertEqual(_types(self.world).count(expected), 1)
            self.assertEqual(self.ines.inventory.items, [])
            self.world.step(30)
        self.ines.needs.hunger = 80
        _go_and_use(self.world, self.ines, "cooking_pot", "meal_started")
        self.assertEqual(_types(self.world).count("keep_unpaid"), 1, "said once a day")
        self.assertTrue(self.world.trade.can_afford(self.world, self.ines, _use(self.world, "water_tank")))

    def test_a_settlement_in_its_opening_asks_nothing_of_anybody(self) -> None:
        world = SimulationWorld.new_settlement()
        founder = world.residents[world.apply_command(FoundResidentCommand("Ada", 34, {}, []))]
        pot = _use(world, "cooking_pot")
        self.assertTrue(world.tutorial.active)
        self.assertFalse(world.trade.owes_keep(world, founder, pot))
        world.tutorial = TutorialState()
        self.assertTrue(world.trade.owes_keep(world, founder, pot))

    def test_a_swap_at_the_counter_leaves_both_better_off_by_their_own_lights(self) -> None:
        self.ines.job_id = None
        self.ines.inventory.items.clear()
        hoe = self.world.stock(self.ines.inventory, "hoe", 1, "ines")
        _put_on_duty(self.world, "nuria")
        wanted = lambda: [item.definition_id for _, item, _ in self.world.trade.offers(self.world, self.ines, COUNTER)]
        self.assertNotIn("canned_beans", wanted(), "she is not hungry, and a tin is worth less to her than a hoe")
        self.ines.needs.hunger = 95
        self.assertEqual(wanted()[0], "canned_beans")
        value = self.world.items.personal_value
        resolve = self.world.registries.items.resolve
        beans, hoe_kind = resolve("canned_beans"), resolve("hoe")
        self.assertGreater(value(self.world, self.ines, beans), value(self.world, self.ines, hoe_kind))
        self.assertGreater(value(self.world, self.nuria, hoe_kind), value(self.world, self.nuria, beans))
        hoes = self.shop.count("hoe")
        self.assertEqual(self.world.trade.buy(self.world, self.ines, COUNTER), "canned_beans")
        self.assertIsNotNone(self.ines.inventory.stack_of("canned_beans", "ines"))
        self.assertIsNone(self.ines.inventory.find(hoe.instance_id))
        self.assertEqual((self.shop.count("hoe"), self.shop.count("canned_beans")), (hoes + 1, 9))
        self.assertIsNone(hoe.owner_id, "what she gave is the settlement's, to be had by the next")
        self.assertEqual(_types(self.world).count("item_swapped"), 1)
        self.assertEqual((self.ines.credits, self.world.trading.fund), (0.0, 0.0), "no coin anywhere")

    def test_a_swap_whoever_keeps_the_counter_would_lose_by_is_turned_down(self) -> None:
        self.ines.job_id = None
        self.ines.inventory.items.clear()
        self.world.stock(self.ines.inventory, "scrap", 1, "ines")
        _put_on_duty(self.world, "nuria")
        self.ines.needs.hunger = 95
        self.assertIsNotNone(self.world.trade.shop_score(self.world, self.ines, COUNTER), "she cannot know beforehand")
        self.assertIsNone(self.world.trade.buy(self.world, self.ines, COUNTER))
        self.assertEqual(self.ines.inventory.count("scrap"), 1)
        self.assertEqual(self.shop.count("canned_beans"), 10)
        self.assertTrue(any("Nuria no le cambia a Inés" in line for line in self.world.event_log))
        self.assertIsNone(self.world.trade.shop_score(self.world, self.ines, COUNTER), "she does not ask again today")
        self.world.clock.day += 1
        self.assertIsNotNone(self.world.trade.shop_score(self.world, self.ines, COUNTER))

    def test_nobody_gives_away_what_they_work_with_or_what_they_have_not_got(self) -> None:
        self.ines.needs.hunger = 95
        self.assertEqual(self.ines.job_id, "farmer")
        self.assertEqual(self.world.trade.offers(self.world, self.ines, COUNTER), [], "her hoe is for the garden")
        self.ines.inventory.items.clear()
        self.assertEqual(self.world.trade.offers(self.world, self.ines, COUNTER), [])

    def test_a_week_under_barter_feeds_everyone_and_the_shop_changes_hands_with_no_coin(self) -> None:
        world = _bartering(SimulationWorld.demo_world(seed=3))
        for resident_id in ("lucia", "paco", "vera", "sergio"):
            for item_id in ("hoe", "rusty_knife"):
                world.stock(world.residents[resident_id].inventory, item_id, 1, resident_id)
        for _ in range(7 * MINUTES_PER_DAY):
            world.step(1)
            for resident in world.residents.values():
                for need in ("hunger", "thirst", "tiredness"):
                    self.assertLess(getattr(resident.needs, need), 100.0, (resident.name, need, world.clock.label))
        types = _types(world)
        self.assertIn("item_swapped", types)
        self.assertNotIn("item_bought", types)
        self.assertNotIn("no_food", types)
        self.assertNotIn("wages_unpaid", types)
        self.assertEqual(len(world.deaths), 0)
        self.assertTrue(any("toma algo en la cantina" in line for line in world.event_log), "whoever works drinks")
        self.assertEqual(_held(world), 0.0, "no coin anywhere")


class TermsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.world = _bartering(_settled())
        self.economy = self.world.registries.economy

    def _all(self, **traits: float) -> None:
        for resident in self.world.residents.values():
            resident.personality = Personality(**traits)

    def test_the_residents_take_up_a_currency_the_player_made_and_go_back_to_barter(self) -> None:
        self._all(greed=90, empathy=10)
        result = self.world.apply_command(ProposeCurrencyCommand("  chapas  "))
        self.assertTrue(result.ok, result.message)
        coin = self.world.fund.currency(self.world)
        self.assertEqual((coin.name, coin.singular, coin.currency_id), ("chapas", "chapa", "currency_1"))
        people = len(self.world.residents)
        self.assertEqual(self.world.trading.fund, self.economy.fund_per_resident * people)
        self.assertEqual({r.credits for r in self.world.residents.values()}, {self.economy.starting_credits})
        self.assertIn("trade_terms_changed", [event.event_type for event in self.world.history])
        self.assertEqual(sum("está por comerciar con chapas" in line for line in self.world.event_log), people)

        tomas = _put_on_duty(self.world, "tomas")
        self.world.clock.hour = 9
        self.world.step(60)
        self.assertAlmostEqual(tomas.credits, self.economy.starting_credits + self.economy.wage_per_hour)
        self.assertIn("chapas", self.world.event_log[0] + "".join(self.world.event_log))

        self.assertFalse(self.world.apply_command(ProposeCurrencyCommand("perras")).ok, "there is one in use")
        again = self.world.apply_command(ProposeBarterCommand())
        self.assertFalse(again.ok)
        self.assertIn("hace poco", again.message)
        self.assertIsNotNone(self.world.fund.currency(self.world))

        self.world.step(self.economy.trade_ask_days * MINUTES_PER_DAY)
        self._all(greed=5, empathy=95)
        for resident in self.world.residents.values():
            resident.credits = 2.0
        fund = self.world.trading.fund
        self.assertTrue(self.world.apply_command(ProposeBarterCommand()).ok)
        self.assertIsNone(self.world.fund.currency(self.world))
        self.assertEqual(self.world.trading.currency.name, "chapas", "it is there if they take it up again")
        tomas = _put_on_duty(self.world, "tomas")
        self.world.clock.hour = 9
        self.world.step(60)
        self.assertEqual((tomas.credits, self.world.trading.fund), (2.0, fund), "what is held counts for nothing")

        self.world.step(self.economy.trade_ask_days * MINUTES_PER_DAY)
        self._all(greed=90, empathy=10)
        held = _held(self.world)
        self.assertTrue(self.world.apply_command(ProposeCurrencyCommand("chapas")).ok)
        self.assertEqual(self.world.fund.currency(self.world).currency_id, "currency_1")
        self.assertEqual(_held(self.world), held, "a currency puts coin in pockets only the first time")

    def test_it_is_the_residents_who_settle_it_and_advice_only_tips_it(self) -> None:
        self._all(greed=10, empathy=90)
        result = self.world.apply_command(ProposeCurrencyCommand("chapas"))
        self.assertFalse(result.ok)
        self.assertIn("sigue con el trueque", result.message)
        self.assertIsNone(self.world.trading.currency, "no currency is made that nobody wanted")
        self.assertEqual(_held(self.world), 0.0)
        self.assertIn("trade_terms_kept", _types(self.world))

        outcomes = {}
        for option in ("encourage", "neutral"):
            self.setUp()
            # With nothing of their own to swap, not much for it and not much against: what the
            # player says is what tips them.
            self._all(greed=40, empathy=60)
            for inventory in (*self.world.containers.values(), *(r.inventory for r in self.world.residents.values())):
                inventory.items[:] = [item for item in inventory.items if item.owner_id is None]
            outcomes[option] = self.world.apply_command(ProposeCurrencyCommand("chapas", option_id=option)).ok
        self.assertEqual(outcomes, {"encourage": True, "neutral": False})

    def test_whoever_is_outside_has_no_say_and_a_settlement_of_nobody_cannot_be_asked(self) -> None:
        self._all(greed=10, empathy=90)
        marta = self.world.residents["marta"]
        marta.personality = Personality(greed=95, empathy=5)
        for resident in self.world.residents.values():
            if resident is not marta:
                resident.expedition = object()
        self.assertTrue(self.world.apply_command(ProposeCurrencyCommand("chapas")).ok, "she is the only one in")
        empty = SimulationWorld.new_settlement()
        self.assertFalse(empty.apply_command(ProposeCurrencyCommand("chapas")).ok)
        self.assertFalse(empty.apply_command(ProposeCurrencyCommand("   ")).ok)
        self.assertFalse(empty.apply_command(ProposeBarterCommand()).ok, "it trades by barter already")

    def test_someone_with_savings_is_loath_to_go_back_to_barter(self) -> None:
        world = _settled()
        inputs = world.terms.decision_inputs
        ines = world.residents["ines"]
        ines.credits = 0.0
        self.assertEqual(inputs(world, ines)["savings"], 0.0)
        ines.credits = 300.0
        self.assertEqual(inputs(world, ines)["savings"], 1.0)
        self.assertGreater(inputs(world, world.residents["marta"])["goods"], inputs(world, world.residents["vera"])["goods"])
        for resident in world.residents.values():
            resident.personality = Personality()
            resident.credits = 300.0
        self.assertFalse(world.apply_command(ProposeBarterCommand()).ok)
        self.assertIsNotNone(world.fund.currency(world))


class MerchantTests(unittest.TestCase):
    def setUp(self) -> None:
        self.world = _settled()
        self.shop = self.world.containers[COUNTER]

    def test_a_caravan_stops_for_some_hours_and_leaves_nothing_for_nothing(self) -> None:
        world = self.world
        world.event_rng = _Certain(1)
        world.clock.day, world.clock.hour, world.clock.minute = 2, 4, 0
        world.happened = {other: 2 for other in world.registries.world_events.events if other != "caravan"}
        before = sum(item.quantity for item in self.shop.items)
        world.step(60)
        self.assertEqual([upcoming.event_id for upcoming in world.upcoming], ["caravan"], "it is on its way first")
        self.assertIsNone(world.merchant)
        world.step(5 * 60)
        merchant = world.merchant
        self.assertIsNotNone(merchant)
        self.assertTrue(8 <= sum(merchant.goods.values()) <= 14, merchant.goods)
        self.assertTrue(20 <= merchant.purse <= 60)
        self.assertEqual(sum(item.quantity for item in self.shop.items), before, "nothing is left at the shop")
        self.assertEqual(_types(world).count("merchant_arrived"), 1)
        self.assertTrue(any("Una caravana para junto a la puerta a comerciar:" in line for line in world.event_log))
        world.step(6 * 60)
        self.assertIsNone(world.merchant)
        self.assertEqual(_types(world).count("merchant_left"), 1)
        self.assertEqual(_types(world).count("merchant_arrived"), 1, "one at a time, and not again for days")

    def test_the_player_sells_what_is_nobodys_and_buys_out_of_the_fund(self) -> None:
        world = self.world
        merchant = _caravan(world, {"medicine": 2}, purse=30.0)
        self.assertEqual((world.merchants.asks(world, "medicine"), world.merchants.gives(world, "canned_beans")), (27, 6))
        beans, fund = world.fund.goods(world)["canned_beans"], world.trading.fund
        medicine = self.shop.count("medicine")
        result = world.apply_command(DealWithMerchantCommand(sell={"canned_beans": 2}, buy={"medicine": 1}))
        self.assertTrue(result.ok, result.message)
        self.assertEqual(world.fund.goods(world)["canned_beans"], beans - 2)
        self.assertEqual(self.shop.count("medicine"), medicine + 1)
        self.assertEqual((world.trading.fund, merchant.purse), (fund - 15, 45.0))
        self.assertEqual(merchant.goods, {"medicine": 1, "canned_beans": 2})
        self.assertEqual(_types(world).count("merchant_deal"), 1)
        self.assertIn("el fondo paga 15 vales", world.event_log[-1])

        self.assertTrue(world.apply_command(DealWithMerchantCommand(sell={"canned_beans": 5})).ok)
        self.assertEqual((world.trading.fund, merchant.purse), (fund + 15, 15.0), "what a merchant pays goes into the fund")

    def test_a_deal_that_cannot_be_met_changes_nothing(self) -> None:
        world = self.world
        merchant = _caravan(world, {"medicine": 2}, purse=30.0)
        saved = SaveManager().to_data(world)
        deal = lambda **what: world.apply_command(DealWithMerchantCommand(**what))
        self.assertIn("no lleva tanto encima", deal(sell={"canned_beans": 6}).message)
        self.assertIn("no lleva tanto", deal(buy={"medicine": 3}).message)
        self.assertIn("no lleva tanto", deal(buy={"hoe": 1}).message)
        self.assertIn("No hay tanto", deal(sell={"canned_beans": 900}).message)
        self.assertIn("nada que tratar", deal(sell={"canned_beans": 0}).message)
        world.trading.fund = 20.0
        self.assertIn("faltan 7 vales", deal(buy={"medicine": 1}).message)
        world.trading.fund = saved["trading"]["fund"]
        self.assertEqual(SaveManager().to_data(world), saved)
        self.assertEqual(merchant.goods, {"medicine": 2})
        world.merchant = None
        self.assertFalse(deal(buy={"medicine": 1}).ok)

    def test_what_is_somebodys_cannot_be_sold_over_their_head(self) -> None:
        world = self.world
        _caravan(world, {}, purse=60.0)
        self.assertEqual(world.fund.goods(world).get("old_radio"), 1, "the one on the shelf, not Marta's")
        self.assertTrue(world.apply_command(DealWithMerchantCommand(sell={"old_radio": 1})).ok)
        self.assertFalse(world.apply_command(DealWithMerchantCommand(sell={"old_radio": 1})).ok)
        self.assertEqual(world.containers["crate_dorm"].stack_of("old_radio", "marta").quantity, 1)

    def test_under_barter_a_deal_is_things_for_things(self) -> None:
        world = _bartering(self.world)
        merchant = _caravan(world, {"medicine": 2}, purse=30.0)
        short = world.apply_command(DealWithMerchantCommand(sell={"canned_beans": 4}, buy={"medicine": 1}))
        self.assertFalse(short.ok)
        self.assertIn("pide más a cambio", short.message)
        self.assertTrue(world.apply_command(DealWithMerchantCommand(sell={"canned_beans": 5}, buy={"medicine": 1})).ok)
        self.assertEqual(merchant.goods, {"medicine": 1, "canned_beans": 5})
        self.assertEqual((_held(world), merchant.purse), (0.0, 30.0), "no coin changes hands")

    def test_a_resident_sells_a_thing_of_their_own_only_if_it_is_worth_it_to_them(self) -> None:
        world = self.world
        marta = world.residents["marta"]
        radio = world.containers["crate_dorm"].stack_of("old_radio", "marta")
        merchant = _caravan(world, {}, purse=60.0)
        fund, credits = world.trading.fund, marta.credits
        self.assertEqual(world.merchants.gives(world, "old_radio"), 21)
        refused = world.apply_command(ProposeSaleCommand("marta", radio.instance_id))
        self.assertFalse(refused.ok)
        self.assertIn("Marta no quiere vender una radio vieja", refused.message)
        self.assertIsNotNone(world.containers["crate_dorm"].find(radio.instance_id))
        self.assertIn("hace poco", world.apply_command(ProposeSaleCommand("marta", radio.instance_id)).message)

        generous = _registries_with("world_events.json", '"buys_at": 0.6', '"buys_at": 1.5')
        world = _settled()
        world.registries = generous
        marta = world.residents["marta"]
        radio = world.containers["crate_dorm"].stack_of("old_radio", "marta")
        merchant = _caravan(world, {}, purse=60.0)
        sold = world.apply_command(ProposeSaleCommand("marta", radio.instance_id))
        self.assertTrue(sold.ok, sold.message)
        self.assertIsNone(world.containers["crate_dorm"].find(radio.instance_id))
        self.assertEqual((marta.credits, merchant.purse, world.trading.fund), (credits + 52, 8.0, fund), "it is hers")
        self.assertEqual(merchant.goods, {"old_radio": 1})
        self.assertIn("item_sold", _types(world))

    def test_only_what_is_theirs_and_only_while_they_are_in_can_be_put_to_them(self) -> None:
        world = self.world
        beans = self.shop.stack_of("canned_beans", None)
        sale = lambda *what: world.apply_command(ProposeSaleCommand(*what))
        radio = world.containers["crate_dorm"].stack_of("old_radio", "marta")
        self.assertFalse(sale("marta", radio.instance_id).ok, "nobody is here to buy")
        _caravan(world, {}, purse=60.0)
        self.assertIn("no es suyo", sale("marta", beans.instance_id).message)
        self.assertIn("no es suyo", sale("raul", radio.instance_id).message)
        self.assertFalse(sale("nobody", radio.instance_id).ok)
        world.residents["marta"].expedition = object()
        self.assertFalse(sale("marta", radio.instance_id).ok)

    def test_under_barter_what_a_thing_fetches_is_a_thing_and_is_theirs(self) -> None:
        world = _bartering(_settled())
        world.registries = _registries_with("world_events.json", '"buys_at": 0.6', '"buys_at": 1.5')
        marta = world.residents["marta"]
        radio = world.containers["crate_dorm"].stack_of("old_radio", "marta")
        merchant = _caravan(world, {"medicine": 3, "canned_beans": 1}, purse=0.0)
        sale = lambda *what: world.apply_command(ProposeSaleCommand("marta", *what))
        self.assertIn("qué se lleva a cambio", sale(radio.instance_id).message)
        marta.needs.hunger = 95
        self.assertFalse(sale(radio.instance_id, "canned_beans").ok, "a tin for a radio is no bargain, however hungry")
        self.assertIsNotNone(world.containers["crate_dorm"].find(radio.instance_id))

        baton = world.stock(marta.inventory, "baton", 1, "marta")
        self.assertIn("por tan poco", sale(baton.instance_id, "medicine").message, "the caravan would lose by it")
        # She cannot stand the thing, and she is hungry: by her lights a tin is worth more.
        world.tastes.profile(world, marta).of(ITEM)["baton"] = Taste(leaning=-100)
        world.crisis_cooldowns.clear()
        sold = sale(baton.instance_id, "canned_beans")
        self.assertTrue(sold.ok, sold.message)
        self.assertIsNone(marta.inventory.find(baton.instance_id))
        self.assertEqual(marta.inventory.stack_of("canned_beans", "marta").quantity, 1)
        self.assertEqual(merchant.goods, {"medicine": 3, "baton": 1})
        self.assertEqual((_held(world), merchant.purse), (0.0, 0.0), "no coin changes hands")


class PilferingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.world = _few(_settled())
        self.marta, self.raul, self.lucia = (self.world.residents[name] for name in ("marta", "raul", "lucia"))
        self.raul.personality = Personality(greed=95, empathy=5)
        _place(self.world, "lucia", FAR_AWAY)
        self.world.trading.fund = 0.0

    def _tempted(self, resident: Resident, action: str) -> list:
        return [c for c in self.world.items.candidates(self.world, resident) if c.name == action]

    def _let_raul(self, action: str, limit: int = 40) -> None:
        for _ in range(limit):
            self.world.step(1)
            _content(self.world, "raul", "lucia")
            if self.world.thefts:
                return
        raise AssertionError(f"Raúl never got round to it: {action}")

    def test_credit_is_taken_from_someone_asleep_by_whoever_is_given_to_it(self) -> None:
        _asleep(self.world, "marta")
        self.marta.credits, self.raul.credits = 15.0, 2.0
        _place(self.world, "raul", (6, 5))
        self.assertEqual([c.item_id for c in self._tempted(self.raul, PILFER_ACTION)], ["marta"])
        self.lucia.x, self.lucia.y = 6, 6
        self.assertEqual(self._tempted(self.lucia, PILFER_ACTION), [], "it is not in her")
        _place(self.world, "lucia", FAR_AWAY)
        self._let_raul(PILFER_ACTION)
        self.assertEqual((self.marta.credits, self.raul.credits), (0.0, 17.0))
        attempt = self.world.thefts[0]
        self.assertEqual((attempt.thief_id, attempt.victim_id, attempt.amount), ("raul", "marta", 15.0))
        self.assertEqual((attempt.item_instance_id, attempt.container_id), ("", "bed_1"))
        self.assertFalse(attempt.discovered)
        self.assertTrue(any("Raúl le roba 15 vales a Marta" in line for line in self.world.event_log))
        self.assertFalse(self.world.knowledge.knows("marta", attempt.fact_id))
        self.assertEqual(self._tempted(self.raul, PILFER_ACTION), [], "no second theft the same day")

    def test_nobody_takes_it_from_someone_awake_from_someone_with_nothing_or_with_someone_looking_on(self) -> None:
        _place(self.world, "raul", (6, 5))
        self.marta.credits = 15.0
        _place(self.world, "marta", (4, 5))
        self.assertEqual(self._tempted(self.raul, PILFER_ACTION), [], "she is awake")
        _asleep(self.world, "marta")
        self.assertEqual(len(self._tempted(self.raul, PILFER_ACTION)), 1)
        _place(self.world, "lucia", (6, 6))
        self.assertEqual(self._tempted(self.raul, PILFER_ACTION), [], "Lucía would see")
        _place(self.world, "lucia", FAR_AWAY)
        self.marta.credits = 0.5
        self.assertEqual(self._tempted(self.raul, PILFER_ACTION), [], "there is not a whole one to take")
        self.marta.credits = 15.0
        self.raul.credits = 60.0
        self.assertEqual(self._tempted(self.raul, PILFER_ACTION), [], "he has plenty put by: a little more does not tempt")
        self.raul.credits = 0.0
        self.world.trading.in_use = False
        self.assertEqual(self._tempted(self.raul, PILFER_ACTION), [], "under barter it is worth nothing")

    def test_whoever_sees_it_holds_it_against_the_thief_and_the_victim_misses_it_on_waking(self) -> None:
        _asleep(self.world, "marta")
        self.marta.credits = 15.0
        _place(self.world, "raul", (6, 5))
        self.world.step(1)
        self.assertEqual(self.raul.activity.action, PILFER_ACTION)
        _place(self.world, "lucia", (6, 6))
        self.lucia.activity = Activity("wander", minutes_left=60, using=True)
        self._let_raul(PILFER_ACTION)
        attempt = self.world.thefts[0]
        self.assertTrue(attempt.discovered)
        self.assertGreater(self.world.relationship("lucia", "raul").resentment, 0)
        self.assertEqual(self.world.relationship("marta", "raul").resentment, 0, "she slept through it")

        self.marta.activity = None
        _place(self.world, "marta", (3, 5))
        self.world.step(1)
        self.assertTrue(attempt.noticed)
        self.assertTrue(any("Marta echa en falta 15 vales" in line for line in self.world.event_log))
        learn(self.world, self.marta, self.world.knowledge.facts[attempt.fact_id], 1.0, SOURCE_WITNESS)
        self.assertGreater(self.world.relationship("marta", "raul").resentment, 15)

    def test_making_peace_brings_the_credit_back_as_far_as_it_is_still_there(self) -> None:
        _asleep(self.world, "marta")
        self.marta.credits, self.raul.credits = 15.0, 0.0
        _place(self.world, "raul", (6, 5))
        self._let_raul(PILFER_ACTION)
        self.raul.credits = 9.5
        heart_to_heart = self.world.registries.interactions["heart_to_heart"]
        self.world.items.after_exchange(self.world, self.raul, self.marta, heart_to_heart)
        self.assertEqual((self.marta.credits, self.raul.credits), (9.0, 0.5))
        self.assertTrue(self.world.thefts[0].returned)
        self.assertTrue(any("Raúl le devuelve 9 vales a Marta" in line for line in self.world.event_log))

    def test_the_fund_is_stolen_from_by_someone_given_to_stealing_and_left_alone_by_someone_who_is_not(self) -> None:
        self.world.trading.fund = 50.0
        self.world.clock.hour = 23
        _place(self.world, "marta", FAR_AWAY)
        _place(self.world, "raul", (17, 6))
        self.assertEqual([c.target_id for c in self._tempted(self.raul, FUND_THEFT_ACTION)], [COUNTER])
        _place(self.world, "lucia", (17, 6))
        self.assertEqual(self._tempted(self.lucia, FUND_THEFT_ACTION), [], "it is not in her")
        _place(self.world, "lucia", FAR_AWAY)
        self._let_raul(FUND_THEFT_ACTION)
        most = self.world.registries.economy.pilfer_max
        pocket = self.world.registries.economy.starting_credits
        self.assertEqual((self.world.trading.fund, self.raul.credits), (50.0 - most, pocket + most))
        attempt = self.world.thefts[0]
        self.assertEqual((attempt.victim_id, attempt.amount, attempt.container_id), (FUND_VICTIM, most, COUNTER))
        fact = self.world.knowledge.facts[attempt.fact_id]
        self.assertEqual(fact.subject_ids, ["raul"])
        learn(self.world, self.lucia, fact, 1.0, SOURCE_WITNESS)
        self.assertGreater(self.world.relationship("lucia", "raul").resentment, 0, "found out as any theft is")

    def test_nobody_takes_from_the_fund_while_the_counter_is_watched_or_the_fund_is_empty(self) -> None:
        self.world.trading.fund = 50.0
        _place(self.world, "marta", FAR_AWAY)
        _place(self.world, "raul", (17, 6))
        self.assertEqual(len(self._tempted(self.raul, FUND_THEFT_ACTION)), 1)
        _place(self.world, "lucia", BESIDE_THE_COUNTER)
        self.assertEqual(self._tempted(self.raul, FUND_THEFT_ACTION), [], "Lucía is at the counter")
        _place(self.world, "lucia", FAR_AWAY)
        self.world.trading.fund = 0.9
        self.assertEqual(self._tempted(self.raul, FUND_THEFT_ACTION), [])

    def test_whoever_keeps_the_counter_sees_that_the_fund_is_short(self) -> None:
        self.world.trading.fund = 50.0
        _place(self.world, "marta", FAR_AWAY)
        _place(self.world, "raul", (17, 6))
        self._let_raul(FUND_THEFT_ACTION)
        attempt = self.world.thefts[0]
        _place(self.world, "raul", FAR_AWAY)
        _place(self.world, "marta", BESIDE_THE_COUNTER)
        self.marta.activity = None
        self.world.step(1)
        self.assertFalse(attempt.noticed, "it is not hers to keep count of")
        self.lucia.job_id = "shopkeeper"
        _place(self.world, "lucia", BESIDE_THE_COUNTER)
        self.lucia.activity = None
        self.world.step(1)
        self.assertTrue(attempt.noticed)
        self.assertTrue(any("Lucía echa en falta 20 vales de lo que es de todos" in line for line in self.world.event_log))
        self.assertEqual(self.world.relationship("lucia", "raul").resentment, 0, "she does not know who")

    def test_under_barter_it_is_a_thing_off_the_shelf_that_is_taken(self) -> None:
        _bartering(self.world)
        _place(self.world, "marta", FAR_AWAY)
        _place(self.world, "raul", (17, 6))
        shelf = self.world.containers[COUNTER]
        before = sum(item.quantity for item in shelf.items)
        self._let_raul(FUND_THEFT_ACTION)
        attempt = self.world.thefts[0]
        taken = self.raul.inventory.find(attempt.item_instance_id)
        self.assertEqual((attempt.victim_id, attempt.amount, taken.owner_id), (FUND_VICTIM, 0.0, "raul"))
        self.assertEqual(sum(item.quantity for item in shelf.items), before - 1)
        self.assertEqual(taken.definition_id, "old_radio", "what is worth most to them")


class FundDataAndSaveTests(unittest.TestCase):
    def setUp(self) -> None:
        self.manager = SaveManager()

    def _reloaded(self, world: SimulationWorld) -> SimulationWorld:
        return self.manager.from_data(json.loads(json.dumps(self.manager.to_data(world))), world.registries)

    def test_a_save_from_before_loads_with_its_credits_as_its_currency(self) -> None:
        world = SimulationWorld.demo_world(seed=5)
        world.step(MINUTES_PER_DAY)
        data = self.manager.to_data(world)
        data["version"] = 25
        del data["trading"], data["merchant"]
        for attempt in data["thefts"]:
            del attempt["amount"]
        loaded = self.manager.from_data(json.loads(json.dumps(data)))
        coin = loaded.fund.currency(loaded)
        self.assertEqual((coin.name, coin.currency_id), ("vales", "credits"))
        self.assertEqual(
            [resident.credits for resident in loaded.residents.values()],
            [resident.credits for resident in world.residents.values()],
        )
        self.assertEqual(loaded.trading.fund, loaded.registries.economy.fund_per_resident * len(loaded.residents))
        self.assertIsNone(loaded.merchant)
        loaded.step(MINUTES_PER_DAY)

    def test_the_fund_the_currency_a_merchant_and_stolen_credit_survive_saving(self) -> None:
        world = _bartering(SimulationWorld.demo_world(seed=5))
        for resident in world.residents.values():
            resident.personality.greed = 90.0
        self.assertTrue(world.apply_command(ProposeCurrencyCommand("chapas")).ok)
        _caravan(world, {"medicine": 2, "hoe": 1}, purse=33.0)
        self.assertTrue(world.apply_command(DealWithMerchantCommand(buy={"medicine": 1})).ok)
        world.step(2 * MINUTES_PER_DAY)
        _caravan(world, {"medicine": 2, "hoe": 1}, purse=33.0)
        loaded = self._reloaded(world)
        self.assertEqual(self.manager.to_data(loaded), self.manager.to_data(world))
        self.assertEqual(loaded.trading, world.trading)
        self.assertEqual(loaded.merchant, world.merchant)
        self.assertEqual(loaded.fund.currency(loaded).amount(3), "3 chapas")
        world.step(MINUTES_PER_DAY)
        loaded.step(MINUTES_PER_DAY)
        self.assertEqual(self.manager.to_data(loaded), self.manager.to_data(world))
        self.assertIsNone(loaded.merchant, "they moved on")

    def test_a_theft_of_credit_is_saved_with_what_was_taken(self) -> None:
        world = _few(_settled())
        world.trading.fund = 0.0
        _asleep(world, "marta")
        world.residents["marta"].credits = 15.0
        raul = _place(world, "raul", (6, 5))
        raul.personality = Personality(greed=95, empathy=5)
        _place(world, "lucia", FAR_AWAY)
        for _ in range(40):
            world.step(1)
        loaded = self._reloaded(world)
        self.assertEqual([attempt.amount for attempt in loaded.thefts], [15.0])
        self.assertEqual(loaded.thefts, world.thefts)

    def test_what_a_save_says_of_trading_that_makes_no_sense_is_put_right(self) -> None:
        world = SimulationWorld.demo_world()
        _caravan(world, {"medicine": 2, "unobtainium": 4}, purse=10.0)
        data = self.manager.to_data(world)
        loaded = self.manager.from_data(json.loads(json.dumps(data)))
        self.assertEqual(loaded.merchant.goods, {"medicine": 2}, "what the game no longer has is not for sale")
        data["merchant"]["event_id"] = "dust_storm"
        data["trading"] = {"currency": None, "in_use": True, "fund": -40}
        loaded = self.manager.from_data(json.loads(json.dumps(data)))
        self.assertIsNone(loaded.merchant, "a storm sells nothing")
        self.assertIsNone(loaded.fund.currency(loaded), "no currency, no trading with one")
        self.assertEqual(loaded.trading.fund, 0.0)
        loaded.step(MINUTES_PER_DAY)

    def test_bad_economy_and_merchant_data_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "negative"):
            economy_settings_from_data({"fund_per_resident": -1})
        with self.assertRaisesRegex(ValueError, "list of item categories"):
            economy_settings_from_data({"kept_categories": "food"})
        with self.assertRaisesRegex(ValueError, "scales must be positive"):
            economy_settings_from_data({"savings_scale": 0})
        with self.assertRaisesRegex(ValueError, "need a name"):
            economy_settings_from_data({"credits_name": " "})
        merchant = {"kind": "merchant", "chance_per_day": 0.2, "minutes": [60, 120], "sells_at": 1.5, "buys_at": 0.6}
        world_event_settings_from_data({"events": {"pedlar": merchant}})
        with self.assertRaisesRegex(ValueError, "never buy for more"):
            world_event_settings_from_data({"events": {"pedlar": {**merchant, "buys_at": 2.0}}})
        with self.assertRaisesRegex(ValueError, "minutes to stop for"):
            world_event_settings_from_data({"events": {"pedlar": {**merchant, "minutes": [0, 0]}}})

    def test_an_outcome_can_say_it_goes_along_with_what_was_put(self) -> None:
        data = {
            "event_type": "x",
            "text": "x",
            "prompt": "x",
            "outcomes": {"yes": {"text": "x", "agrees": True, "score": {"bargain": 1, "savings": 1, "goods": 1}}, "no": {"text": "x"}},
            "options": [],
        }
        outcomes = decision_definition_from_data("x", data).outcomes
        self.assertEqual((outcomes["yes"].agrees, outcomes["no"].agrees), (True, False))

    def test_a_kind_of_event_that_leaves_things_for_nothing_still_can(self) -> None:
        registries = _registries_with("world_events.json", '"kind": "merchant"', '"kind": "stock"')
        world = SimulationWorld.demo_world(registries=registries)
        world.event_rng = _Certain(1)
        world.clock.day, world.clock.hour, world.clock.minute = 2, 4, 0
        world.happened = {other: 2 for other in registries.world_events.events if other != "caravan"}
        counter = world.containers[COUNTER]
        before = sum(item.quantity for item in counter.items)
        world.step(6 * 60)
        self.assertTrue(8 <= sum(item.quantity for item in counter.items) - before <= 14)
        self.assertEqual((_types(world).count("goods_left"), world.merchant), (1, None))

    def test_trading_needs_no_pygame(self) -> None:
        check = (
            "import sys; import simulation.world, save.save_manager; "
            "import simulation.economy.fund_system, simulation.economy.merchant, simulation.economy.pilfering, "
            "simulation.economy.terms, simulation.economy.terms_system, simulation.economy.trade_system; "
            "from simulation.world import SimulationWorld; SimulationWorld.demo_world().step(600); "
            "sys.exit(1 if 'pygame' in sys.modules else 0)"
        )
        done = subprocess.run([sys.executable, "-c", check], cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(done.returncode, 0, done.stderr)


if __name__ == "__main__":
    unittest.main()
