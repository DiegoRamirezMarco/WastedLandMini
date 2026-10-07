import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from save.save_manager import SaveManager
from simulation.commands import ChooseOptionCommand, SuggestJobCommand
from simulation.economy.settings import economy_settings_from_data
from simulation.economy.trade_system import MAX_WANT, MIN_WANT
from simulation.events.intervention_system import JOB_OFFER
from simulation.items.item_system import USE_ITEM_ACTION
from simulation.registries import DATA_DIR, BuiltInRegistries
from simulation.residents.activity import Activity
from simulation.residents.needs import Needs
from simulation.residents.personality import Personality
from simulation.residents.resident import Resident
from simulation.work.hauling import carried
from simulation.work.work_system import HAUL_ACTION, WORK_ACTION
from simulation.world import SimulationWorld
from world.pathfinding import manhattan

MINUTES_PER_DAY = 24 * 60
PANTRIES = ("pantry_1", "pantry_2")


def _settled(seed: int = 7) -> SimulationWorld:
    """The demo settlement with everyone content and no grudges, so only work drives the day."""
    world = SimulationWorld.demo_world(seed=seed)
    world.relationships.clear()
    _keep_content(world)
    return world


def _keep_content(world: SimulationWorld, *resident_ids: str) -> None:
    for resident_id in resident_ids or world.residents:
        world.residents[resident_id].needs = Needs(hunger=0, tiredness=0, social=0, stress=0)


def _set_time(world: SimulationWorld, hour: int, minute: int = 0) -> None:
    world.clock.hour, world.clock.minute = hour, minute


def _run(world: SimulationWorld, minutes: int, *content: str) -> None:
    """Let time pass with the named residents kept content, or everyone if none is named."""
    for _ in range(minutes):
        world.step(1)
        _keep_content(world, *content)


def _run_until_on_duty(world: SimulationWorld, resident_id: str, limit: int = 180) -> None:
    resident = world.residents[resident_id]
    for _ in range(limit):
        world.step(1)
        _keep_content(world)
        if world.work.on_duty(world, resident):
            return
    raise AssertionError(f"{resident_id} never reached their post")


def _put_on_duty(world: SimulationWorld, resident_id: str, minutes: int = 240) -> Resident:
    """Stand a resident at their post, already at work."""
    resident = world.residents[resident_id]
    post = world.interactables[resident.post_id]
    passable = world.passable()
    resident.x, resident.y = next(
        (post.x + dx, post.y + dy) for dx, dy in ((0, -1), (0, 1), (-1, 0), (1, 0)) if passable((post.x + dx, post.y + dy))
    )
    resident.activity = Activity(WORK_ACTION, resident.post_id, minutes_left=minutes, using=True)
    resident.current_action = WORK_ACTION
    return resident


def _types(world: SimulationWorld) -> list[str]:
    return [line.split(" | ")[1] for line in world.event_log]


def _others(world: SimulationWorld, resident_id: str) -> list[str]:
    return [other_id for other_id in world.residents if other_id != resident_id]


def _owned(world: SimulationWorld, resident_id: str, definition_id: str):
    return world.residents[resident_id].inventory.stack_of(definition_id, resident_id)


def _without_water_post(world: SimulationWorld) -> SimulationWorld:
    """Leave out the post that nobody holds when a settlement starts, for tests about one vacancy at a time."""
    jobs = {job_id: job for job_id, job in world.registries.jobs.items() if job_id != "water_carrier"}
    world.registries = replace(world.registries, jobs=jobs)
    world.vacancies.pop("water_carrier", None)
    return world


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


class CarryingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.world = _settled()
        self.raul, self.marta = self.world.residents["raul"], self.world.residents["marta"]

    def _hauling_at(self, container_id: str) -> list[str]:
        """Residents who are loading or unloading at a container this minute."""
        return [
            resident.resident_id
            for resident in self.world.residents.values()
            if resident.activity is not None
            and resident.activity.action == HAUL_ACTION
            and resident.activity.using
            and resident.activity.target_id == container_id
        ]

    def test_what_grows_is_in_the_farmers_hands_until_they_carry_it_to_a_pantry(self) -> None:
        _set_time(self.world, 8)
        before = {pantry: self.world.containers[pantry].count("vegetables") for pantry in PANTRIES}
        arrivals = 0
        seen_in_hand = 0
        for _ in range(5 * 60):
            self.world.step(1)
            _keep_content(self.world)
            seen_in_hand = max(seen_in_hand, carried(self.raul, "vegetables"))
            for pantry in PANTRIES:
                now = self.world.containers[pantry].count("vegetables")
                if now > before[pantry]:
                    arrivals += 1
                    hauliers = self._hauling_at(pantry)
                    self.assertTrue(hauliers, f"vegetables appeared in {pantry} at {self.world.clock.label}")
                    place = self.world.interactables[pantry]
                    for resident_id in hauliers:
                        self.assertEqual(manhattan(self.world.residents[resident_id].tile, (place.x, place.y)), 1)
                before[pantry] = now
        self.assertEqual(seen_in_hand, 6, "a farmer sets off once their hands are full")
        self.assertGreaterEqual(arrivals, 2)
        self.assertIn("goods_hauled", _types(self.world))

    def test_at_the_end_of_the_shift_a_farmer_hands_in_what_they_still_carry(self) -> None:
        _put_on_duty(self.world, "raul", minutes=1)
        self.world.stock(self.raul.inventory, "vegetables", 2, None)
        _set_time(self.world, 12, 59)
        _run(self.world, 60)
        self.assertEqual(carried(self.raul, "vegetables"), 0)
        self.assertEqual(sum(self.world.containers[pantry].count("vegetables") for pantry in PANTRIES), 2)

    def test_the_cook_walks_to_a_pantry_for_what_goes_in_the_pot(self) -> None:
        pot = self.world.containers["cooking_pot"]
        pot.items.clear()
        for farmer_id in ("raul", "ines"):
            self.world.residents[farmer_id].job_id = None
        _set_time(self.world, 11)
        raw = sum(item.quantity for pantry in PANTRIES for item in self.world.containers[pantry].items)
        fetched = False
        for _ in range(3 * 60):
            self.world.step(1)
            _keep_content(self.world)
            left = sum(item.quantity for pantry in PANTRIES for item in self.world.containers[pantry].items)
            if left < raw:
                fetched = True
                self.assertTrue(
                    any("marta" in self._hauling_at(pantry) for pantry in PANTRIES),
                    f"raw food left a pantry by itself at {self.world.clock.label}",
                )
            raw = left
        self.assertTrue(fetched)
        self.assertGreaterEqual(pot.count("stew"), 6)
        self.assertTrue(any("Marta coge" in line for line in self.world.event_log))

    def test_with_nothing_to_fetch_the_cook_stays_at_the_pot(self) -> None:
        self.world.containers["cooking_pot"].items.clear()
        for pantry in PANTRIES:
            self.world.containers[pantry].items.clear()
        for farmer_id in ("raul", "ines"):
            self.world.residents[farmer_id].job_id = None
        _set_time(self.world, 11)
        _run_until_on_duty(self.world, "marta")
        where = self.marta.tile
        _run(self.world, 90)
        self.assertTrue(self.world.work.on_duty(self.world, self.marta))
        self.assertEqual(self.marta.tile, where)
        self.assertEqual(sum("Marta se pone a cocinar" in line for line in self.world.event_log), 1)
        self.assertEqual(self.world.containers["cooking_pot"].count("stew"), 0)

    def test_someone_who_leaves_a_job_puts_down_what_they_were_carrying_for_it(self) -> None:
        self.world.stock(self.raul.inventory, "vegetables", 4, None)
        self.assertTrue(self.world.staffing.assign(self.world, self.raul, "bartender") is False)
        self.world.residents["lucia"].job_id = self.world.residents["lucia"].post_id = None
        self.assertTrue(self.world.staffing.assign(self.world, self.raul, "bartender"))
        self.assertEqual(carried(self.raul, "vegetables"), 0)
        self.assertEqual(sum(c.count("vegetables") for c in self.world.containers.values()), 4)
        self.assertIsNotNone(_owned(self.world, "raul", "hoe"), "what is theirs stays with them")


class WearAndRepairTests(unittest.TestCase):
    def setUp(self) -> None:
        self.world = _settled()
        self.raul, self.ines = self.world.residents["raul"], self.world.residents["ines"]
        self.hoe = _owned(self.world, "raul", "hoe")

    def test_a_hoe_makes_the_garden_yield_faster_and_wears_out_doing_it(self) -> None:
        self.ines.inventory.items.clear()
        for farmer_id in ("raul", "ines"):
            _put_on_duty(self.world, farmer_id)
        _set_time(self.world, 8)
        _run(self.world, 60)
        self.assertEqual(carried(self.raul, "vegetables"), 3)
        self.assertEqual(carried(self.ines, "vegetables"), 2)
        self.assertEqual(self.hoe.condition, 94.0)

    def test_a_thing_worn_right_out_breaks_and_is_no_use_until_repaired(self) -> None:
        job = self.world.work.job_of(self.world, self.raul)
        self.assertIs(self.world.work.tool_of(self.world, self.raul, job), self.hoe)
        for _ in range(60):
            self.world.items.wear(self.world, self.raul, self.hoe)
        self.assertEqual(self.hoe.condition, 0.0)
        self.assertTrue(self.hoe.broken)
        self.assertEqual(_types(self.world).count("item_broke"), 1)
        self.assertIsNone(self.world.work.tool_of(self.world, self.raul, job))

    def test_a_broken_weapon_is_bare_hands_and_a_fight_wears_a_good_one(self) -> None:
        tomas = self.world.residents["tomas"]
        baton = _owned(self.world, "tomas", "baton")
        self.assertGreater(self.world.health.weapon_of(self.world, tomas)[0], 1.0)
        self.world.health.fight_damage(self.world, self.raul, tomas, self.world.registries.interactions["fight"])
        self.assertEqual(baton.condition, 92.0)
        baton.condition = 0.0
        self.assertEqual(self.world.health.weapon_of(self.world, tomas), (1.0, ()))

    def test_something_too_worn_to_put_back_is_kept_to_be_seen_to_and_a_broken_one_is_left_alone(self) -> None:
        marta = self.world.residents["marta"]
        crate = self.world.containers["crate_dorm"]
        radio = crate.stack_of("old_radio", "marta")
        radio.condition = 52.0
        marta.needs.stress = 70
        place = self.world.interactables["crate_dorm"]
        marta.x, marta.y = place.x - 1, place.y
        marta.activity = Activity(USE_ITEM_ACTION, "crate_dorm", minutes_left=10, item_id=radio.instance_id)
        self.world.step(10)
        self.assertEqual(radio.condition, 47.0)
        self.assertIs(marta.inventory.find(radio.instance_id), radio)
        self.assertIsNone(crate.find(radio.instance_id))
        radio.condition = 0.0
        marta.needs.stress = 70
        uses = [c for c in self.world.items.candidates(self.world, marta) if c.name == USE_ITEM_ACTION]
        self.assertEqual(uses, [])

    def _repairs(self) -> list[str]:
        candidates = self.world.activities.routine.candidates(self.world, self.raul)
        return [candidate.name for candidate in candidates if candidate.name == "repair"]

    def test_a_worn_tool_is_taken_to_the_workshop_only_while_the_mechanic_is_there(self) -> None:
        self.raul.job_id = None
        self.hoe.condition = 20.0
        _set_time(self.world, 9)
        self.assertEqual(self._repairs(), [])
        _set_time(self.world, 10)
        _run_until_on_duty(self.world, "paco")
        self.assertEqual(self._repairs(), ["repair"])
        self.hoe.condition = 80.0
        self.assertEqual(self._repairs(), [], "a thing in good order needs no repair")
        self.hoe.condition = 20.0
        self.raul.credits = 1.0
        self.assertEqual(self._repairs(), [], "a repair has to be paid for")

    def test_the_mechanic_mends_it_for_a_price_and_stops_when_they_leave(self) -> None:
        self.raul.job_id = None
        self.hoe.condition = 20.0
        self.raul.credits = 10.0
        _set_time(self.world, 10)
        _run_until_on_duty(self.world, "paco")
        bench = self.world.interactables["workbench"]
        self.raul.activity = self.world.activities.routine._use(self.world, self.raul, bench)
        for _ in range(120):
            self.world.step(1)
            _keep_content(self.world)
            if self.hoe.condition >= 100.0:
                break
        self.assertEqual(self.hoe.condition, 100.0)
        self.assertEqual(self.raul.credits, 6.0)
        self.assertTrue(any("Raúl lleva una azada a arreglar" in line for line in self.world.event_log))
        self.world.step(2)
        self.assertNotEqual(self.raul.current_action, "repair")

        self.hoe.condition = 20.0
        self.raul.activity = self.world.activities.routine._use(self.world, self.raul, bench)
        _run(self.world, 5)
        self.assertEqual(self.raul.current_action, "repair")
        paco = self.world.residents["paco"]
        paco.activity, paco.job_id = None, None
        _run(self.world, 5)
        self.assertNotEqual(self.raul.current_action, "repair")
        self.assertLess(self.hoe.condition, 100.0)
        self.assertGreater(self.hoe.condition, 20.0)


class TradeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.world = _settled()
        # Inés has no food put by, unlike Raúl, so she is the one to send shopping.
        self.ines = self.world.residents["ines"]
        self.ines.job_id = None
        self.shop = self.world.containers["shop_counter"]
        self.items = self.world.registries.items

    def test_an_hour_on_duty_earns_the_settlements_wage(self) -> None:
        tomas = _put_on_duty(self.world, "tomas")
        _set_time(self.world, 9)
        before = tomas.credits
        _run(self.world, 60)
        self.assertAlmostEqual(tomas.credits - before, self.world.registries.economy.wage_per_hour)
        idle = self.world.residents["lucia"]
        self.assertEqual(idle.credits, self.world.registries.economy.starting_credits, "no work, no pay")

    def test_a_job_can_pay_its_own_wage(self) -> None:
        registries = _registries_with("jobs.json", '"sight_bonus": 8,', '"sight_bonus": 8, "wage": 6,')
        world = SimulationWorld.demo_world(registries=registries)
        _keep_content(world)
        tomas = _put_on_duty(world, "tomas")
        _set_time(world, 9)
        before = tomas.credits
        _run(world, 30)
        self.assertAlmostEqual(tomas.credits - before, 3.0)

    def test_the_fewer_there_are_left_the_dearer_they_get(self) -> None:
        beans = self.items.get("canned_beans")
        prices = [self.world.trade.price_of(self.world, beans, units) for units in (10, 5, 2, 1)]
        self.assertEqual(prices, [11, 12, 15, 20])

    def _shops(self) -> list[str]:
        candidates = self.world.activities.routine.candidates(self.world, self.ines)
        return [candidate.name for candidate in candidates if candidate.name == "shop"]

    def test_the_shop_sells_only_while_someone_is_behind_the_counter(self) -> None:
        self.ines.needs.hunger = 60
        self.ines.credits = 20.0
        _set_time(self.world, 9)
        self.assertEqual(self._shops(), [])
        _set_time(self.world, 12)
        _run_until_on_duty(self.world, "nuria")
        self.ines.needs.hunger = 60
        self.assertEqual(self._shops(), ["shop"])
        self.ines.credits = 5.0
        self.assertEqual(self._shops(), [], "nothing on the counter is that cheap")

    def test_what_is_bought_is_paid_for_and_becomes_the_buyers(self) -> None:
        self.ines.credits = 20.0
        _set_time(self.world, 12)
        _run_until_on_duty(self.world, "nuria")
        self.ines.needs.hunger = 60
        self.ines.activity = self.world.activities.routine._use(
            self.world, self.ines, self.world.interactables["shop_counter"]
        )
        self.assertEqual(self.ines.activity.action, "shop")
        for _ in range(60):
            self.world.step(1)
            _keep_content(self.world, *_others(self.world, "ines"))
            if "item_bought" in _types(self.world):
                break
        bought = _owned(self.world, "ines", "canned_beans")
        self.assertIsNotNone(bought)
        self.assertEqual(bought.quantity, 1)
        self.assertEqual(self.ines.credits, 9.0)
        self.assertEqual(self.shop.count("canned_beans"), 9)
        self.assertTrue(any("Inés compra unas judías en conserva por 11 vales" in line for line in self.world.event_log))

    def test_a_farmer_without_a_hoe_wants_one_above_all(self) -> None:
        hoe = self.items.get("hoe")
        ines, tomas = self.ines, self.world.residents["tomas"]
        ines.job_id = "farmer"
        self.assertEqual(self.world.trade.want(self.world, ines, hoe, 18), 0.0, "she has one already")
        ines.inventory.items.clear()
        ines.credits = 30.0
        self.assertEqual(self.world.trade.want(self.world, ines, hoe, 18), MAX_WANT)
        self.assertEqual(self.world.trade.want(self.world, tomas, hoe, 18), 0.0, "a guard has no use for it")
        choice = self.world.trade.best_buy(self.world, ines, "shop_counter")
        self.assertEqual(choice[0].definition_id, "hoe")

    def test_someone_afraid_of_another_buys_a_weapon_on_purpose(self) -> None:
        knife = self.items.get("rusty_knife")
        marta, tomas = self.world.residents["marta"], self.world.residents["tomas"]
        self.assertEqual(self.world.trade.want(self.world, marta, knife, 40), 0.0)
        self.world.relationship("marta", "raul").fear = 60
        self.assertGreaterEqual(self.world.trade.want(self.world, marta, knife, 40), MIN_WANT)
        self.world.relationship("tomas", "raul").fear = 60
        self.assertEqual(self.world.trade.want(self.world, tomas, knife, 40), 0.0, "he is armed already")
        marta.credits = 50.0
        self.assertEqual(self.world.trade.buy(self.world, marta, "shop_counter"), "rusty_knife")
        self.assertGreater(self.world.health.weapon_of(self.world, marta)[0], 1.0)
        self.assertEqual(marta.credits, 10.0)

    def test_nobody_buys_what_they_have_no_use_for_or_already_have_enough_of(self) -> None:
        beans, radio = self.items.get("canned_beans"), self.items.get("old_radio")
        marta = self.world.residents["marta"]
        marta.needs.stress = 80
        self.assertEqual(self.world.trade.want(self.world, marta, radio, 40), 0.0, "she has a radio")
        self.ines.needs.stress = 80
        self.assertGreater(self.world.trade.want(self.world, self.ines, radio, 40), MIN_WANT)
        self.ines.needs.hunger = 60
        self.assertGreater(self.world.trade.want(self.world, self.ines, beans, 11), MIN_WANT)
        self.assertLess(self.world.trade.want(self.world, self.ines, beans, 40), MIN_WANT, "not at any price")
        self.world.stock(self.ines.inventory, "canned_beans", 2, "ines")
        self.assertEqual(self.world.trade.want(self.world, self.ines, beans, 11), 0.0)

    def test_a_drink_costs_credits_and_the_broke_go_without(self) -> None:
        _set_time(self.world, 18)
        _run_until_on_duty(self.world, "lucia")
        self.ines.needs.stress = 80
        self.ines.credits = 1.0
        drinks = [c.name for c in self.world.activities.routine.candidates(self.world, self.ines) if c.name == "drink"]
        self.assertEqual(drinks, [])
        self.ines.credits = 5.0
        self.ines.activity = self.world.activities.routine._use(self.world, self.ines, self.world.interactables["bar"])
        for _ in range(60):
            self.world.step(1)
            if self.ines.current_action == "drink":
                break
        self.assertEqual(self.ines.current_action, "drink")
        self.assertEqual(self.ines.credits, 3.0)


class ChangingJobsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.world = _without_water_post(_settled())
        self.lucia = self.world.residents["lucia"]

    def _job_decisions(self) -> list:
        return [decision for decision in self.world.decisions.values() if decision.kind == JOB_OFFER]

    def _run_until_offer(self, limit: int = 3 * MINUTES_PER_DAY):
        for _ in range(limit):
            self.world.step(1)
            _keep_content(self.world)
            if self._job_decisions():
                return self._job_decisions()[0]
        raise AssertionError("nobody was asked to take the job")

    def test_taking_a_job_gives_a_free_post_and_says_so(self) -> None:
        self.assertFalse(self.world.staffing.assign(self.world, self.lucia, "guard"), "the only post is taken")
        self.assertFalse(self.world.staffing.assign(self.world, self.lucia, "astronaut"))
        self.assertTrue(self.world.staffing.assign(self.world, self.lucia, "farmer"))
        self.assertEqual((self.lucia.job_id, self.lucia.post_id), ("farmer", "crop_2"))
        self.assertTrue(any("Lucía cambia de puesto: de Cantina a Huerto" in line for line in self.world.event_log))
        self.assertIn("job_changed", [event.event_type for event in self.world.history])

    def test_a_job_nobody_does_is_noticed_only_after_a_while(self) -> None:
        self.world.health.die(self.world, self.world.residents["marta"], "una prueba")
        self.world.step(60)
        self.assertIn("cook", self.world.vacancies)
        self.world.step(22 * 60)
        self.assertNotIn("post_vacant", _types(self.world))
        self.assertEqual(self._job_decisions(), [])
        _run(self.world, 2 * 60)
        self.assertEqual(_types(self.world).count("post_vacant"), 1)
        _run(self.world, 3 * MINUTES_PER_DAY)
        self.assertEqual(
            sum("Nadie se ocupa de un puesto: Cocina" in line for line in self.world.event_log), 1, "said once"
        )

    def test_the_one_whose_job_matters_least_is_asked_first_and_never_a_peer(self) -> None:
        self.world.health.die(self.world, self.world.residents["marta"], "una prueba")
        asked = [resident.resident_id for resident in self.world.staffing.candidates(self.world, "cook")]
        self.assertEqual(asked, ["lucia", "paco", "nuria", "tomas", "sergio", "vera"])
        self.world.residents["vera"].job_id = None
        self.assertEqual(self.world.staffing.candidates(self.world, "cook")[0].resident_id, "vera", "the idle first")
        decision = self._run_until_offer()
        self.assertEqual((decision.resident_id, decision.job_id), ("vera", "cook"))
        self.assertIn("Cocina", decision.prompt)
        self.assertIn("job_offered", _types(self.world))

    def test_advice_tips_the_choice_but_the_resident_makes_it(self) -> None:
        outcomes = {}
        for option in ("encourage", "discourage", None):
            self.setUp()
            self.world.health.die(self.world, self.world.residents["marta"], "una prueba")
            decision = self._run_until_offer()
            self.assertEqual(decision.resident_id, "lucia")
            outcomes[option] = self.world.interventions.resolve(self.world, decision.decision_id, option)
            if outcomes[option] == "take":
                self.assertEqual((self.lucia.job_id, self.lucia.post_id), ("cook", "cooking_pot"))
            else:
                self.assertEqual(self.lucia.job_id, "bartender")
        self.assertEqual(outcomes, {"encourage": "take", "discourage": "stay", None: "stay"})

    def test_the_same_advice_does_not_move_everyone(self) -> None:
        self.lucia.personality = Personality(empathy=80, greed=20, courage=60, impulsiveness=30)
        paco = self.world.residents["paco"]
        paco.personality = Personality(empathy=10, greed=95, courage=10, impulsiveness=90)
        willing = self.world.apply_command(SuggestJobCommand("lucia", "farmer"))
        grasping = self.world.apply_command(SuggestJobCommand("paco", "farmer"))
        self.assertEqual((willing, grasping), ("take", "stay"))
        self.assertEqual((self.lucia.job_id, paco.job_id), ("farmer", "mechanic"))

    def test_the_player_can_suggest_a_job_but_only_one_with_a_free_post_and_not_over_and_over(self) -> None:
        self.assertIsNone(self.world.apply_command(SuggestJobCommand("lucia", "guard")), "no free post")
        self.assertIsNone(self.world.apply_command(SuggestJobCommand("lucia", "bartender")), "it is her job already")
        self.assertIsNone(self.world.apply_command(SuggestJobCommand("nobody", "farmer")))
        self.assertIsNone(self.world.apply_command(SuggestJobCommand("lucia", "astronaut")))
        self.assertEqual(self.world.decisions, {})
        self.assertEqual(self.world.apply_command(SuggestJobCommand("lucia", "farmer", "discourage")), "stay")
        self.assertEqual(self.lucia.job_id, "bartender")
        self.assertIsNone(self.world.apply_command(SuggestJobCommand("lucia", "farmer")), "asked a moment ago")
        self.world.step(13 * 60)
        self.assertEqual(self.world.apply_command(SuggestJobCommand("lucia", "farmer")), "take")
        self.assertEqual(self.lucia.job_id, "farmer")

    def test_what_stands_in_the_way_of_a_suggestion_can_be_asked(self) -> None:
        obstacle = self.world.interventions.suggestion_obstacle
        self.assertIsNone(obstacle(self.world, "lucia", "farmer"))
        self.assertEqual(obstacle(self.world, "lucia", "bartender"), "own_job")
        self.assertEqual(obstacle(self.world, "lucia", "guard"), "no_post")
        self.assertEqual(obstacle(self.world, "nobody", "farmer"), "unknown")
        self.assertEqual(obstacle(self.world, "lucia", "astronaut"), "unknown")
        self.world.apply_command(SuggestJobCommand("lucia", "farmer", "discourage"))
        self.assertEqual(obstacle(self.world, "lucia", "farmer"), "asked_recently")
        marta = self.world.residents["marta"]
        marta.job_id = marta.post_id = None
        self.world.vacancies["cook"] = self.world.clock.total_minutes - 30 * 60
        marta.activity = self.world.interventions.maybe_offer_job(self.world, marta)
        self.assertEqual(obstacle(self.world, "marta", "farmer"), "deciding")

    def test_a_suggestion_does_not_wake_or_interrupt_whoever_gets_it(self) -> None:
        self.lucia.activity = Activity("sleep", "bed_1", minutes_left=300, using=True)
        self.assertEqual(self.world.apply_command(SuggestJobCommand("lucia", "farmer")), "take")
        self.assertEqual(self.lucia.activity.action, "sleep")

    def test_a_post_left_by_the_dead_is_taken_up_and_the_settlement_eats_again(self) -> None:
        world = SimulationWorld.demo_world(seed=3)
        world.health.die(world, world.residents["marta"], "una prueba")
        for _ in range(5 * MINUTES_PER_DAY):
            world.step(1)
            for decision in list(world.decisions.values()):
                if decision.job_id is not None:
                    world.apply_command(ChooseOptionCommand(decision.decision_id, "encourage"))
        cooks = world.staffing.workers(world, "cook")
        self.assertEqual(len(cooks), 1)
        cooked_after = [line for line in world.event_log if f"{cooks[0].name} se pone a cocinar" in line]
        self.assertTrue(cooked_after)
        self.assertNotIn("cook", world.vacancies)


class DaysOffTests(unittest.TestCase):
    def setUp(self) -> None:
        self.world = _settled()
        self.lucia = self.world.residents["lucia"]

    def test_nobody_in_the_demo_has_the_first_day_off_and_the_farmers_never_rest_together(self) -> None:
        days = {resident_id: resident.day_off for resident_id, resident in self.world.residents.items()}
        self.assertNotIn(None, days.values())
        self.assertNotIn(0, days.values())
        self.assertNotEqual(days["raul"], days["ines"])

    def test_on_their_day_off_a_resident_does_not_go_to_work(self) -> None:
        _set_time(self.world, 19)
        self.assertIsNotNone(self.world.work.candidate(self.world, self.lucia))
        self.world.clock.day = 2
        self.assertTrue(self.world.work.is_day_off(self.world, self.lucia))
        self.assertIsNone(self.world.work.candidate(self.world, self.lucia))
        self.world.clock.day = 9
        self.assertTrue(self.world.work.is_day_off(self.world, self.lucia), "the same day every week")
        self.world.clock.day = 3
        self.assertIsNotNone(self.world.work.candidate(self.world, self.lucia))

    def test_the_bar_stays_shut_the_day_the_bartender_rests(self) -> None:
        self.world.clock.day = 2
        _set_time(self.world, 0)
        for _ in range(MINUTES_PER_DAY):
            self.world.step(1)
            for resident in self.world.residents.values():
                resident.needs = Needs(hunger=0, tiredness=0, social=0, stress=70)
            self.assertFalse(self.world.work.on_duty(self.world, self.lucia), self.world.clock.label)
        self.assertFalse(any("toma algo en la cantina" in line for line in self.world.event_log))
        self.assertNotIn("bartender", self.world.vacancies, "a day off is not a vacancy")


class EconomyDataAndSaveTests(unittest.TestCase):
    def setUp(self) -> None:
        self.manager = SaveManager()

    def test_bad_economy_data_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "negative"):
            economy_settings_from_data({"wage_per_hour": -1})
        with self.assertRaisesRegex(ValueError, "positive"):
            economy_settings_from_data({"week_days": 0})
        self.assertEqual(economy_settings_from_data({}).week_days, 7)

    def test_a_counter_that_sells_must_hold_things(self) -> None:
        with self.assertRaisesRegex(ValueError, "must be a container"):
            _registries_with(
                "interactables.json",
                '"container": true,\n    "use": {\n      "action": "shop"',
                '"use": {\n      "action": "shop"',
            )

    def test_a_display_must_stand_for_a_kind_of_container(self) -> None:
        with self.assertRaisesRegex(ValueError, "displays what is in guard_post"):
            _registries_with("interactables.json", '"display_of": "shop_counter"', '"display_of": "guard_post"')

    def test_a_save_older_than_the_last_change_to_the_map_gains_what_was_added(self) -> None:
        world = SimulationWorld.demo_world()
        data = self.manager.to_data(world)
        shelves = {"shop_shelf_1", "shop_shelf_2"}
        data["interactables"] = [placed for placed in data["interactables"] if placed["id"] not in shelves]
        current = self.manager.from_data(json.loads(json.dumps(data)))
        self.assertFalse(shelves & current.interactables.keys(), "a save keeps the objects it was made with")
        data["version"] = 8
        older = self.manager.from_data(json.loads(json.dumps(data)))
        self.assertTrue(shelves <= older.interactables.keys())
        self.assertEqual(older.containers["shop_counter"].count("canned_beans"), 10, "its stock is not doubled")
        self.assertEqual(older.residents["raul"].credits, world.residents["raul"].credits)

    def test_a_job_whose_tool_no_item_is_tagged_as_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "no item is tagged as: scythe"):
            _registries_with("jobs.json", '"tag": "hoe"', '"tag": "scythe"')

    def test_saving_in_the_middle_of_a_vacancy_continues_exactly_like_not_saving(self) -> None:
        original = _without_water_post(SimulationWorld.demo_world(seed=5))
        original.health.die(original, original.residents["marta"], "una prueba")
        while not any(decision.job_id for decision in original.decisions.values()):
            original.step(1)
        loaded = self.manager.from_data(json.loads(json.dumps(self.manager.to_data(original))), original.registries)
        self.assertEqual(self.manager.to_data(loaded), self.manager.to_data(original))
        self.assertEqual([d.job_id for d in loaded.decisions.values()], ["cook"])
        self.assertEqual(loaded.vacancies, original.vacancies)
        self.assertEqual(
            [(r.credits, r.day_off) for r in loaded.residents.values()],
            [(r.credits, r.day_off) for r in original.residents.values()],
        )
        original.step(3 * MINUTES_PER_DAY)
        loaded.step(3 * MINUTES_PER_DAY)
        self.assertEqual(self.manager.to_data(loaded), self.manager.to_data(original))

    def test_a_decision_about_a_job_that_no_longer_exists_is_dropped(self) -> None:
        world = _without_water_post(SimulationWorld.demo_world(seed=5))
        world.health.die(world, world.residents["marta"], "una prueba")
        while not any(decision.job_id for decision in world.decisions.values()):
            world.step(1)
        data = self.manager.to_data(world)
        without_cooks = _registries_with("jobs.json", '"cook": {', '"chef": {')
        loaded = self.manager.from_data(data, without_cooks)
        self.assertEqual(loaded.decisions, {})
        self.assertNotIn("cook", loaded.vacancies)
        loaded.step(MINUTES_PER_DAY)

    def test_a_save_from_before_the_economy_gains_the_shop_and_keeps_what_it_had(self) -> None:
        world = SimulationWorld.demo_world()
        world.health.die(world, world.residents["vera"], "una prueba")
        world.step(90)
        data = self.manager.to_data(world)
        data["version"] = 7
        del data["vacancies"]
        newer = {"shop_counter", "bed_7", "bed_8"}
        data["interactables"] = [placed for placed in data["interactables"] if placed["id"] not in newer]
        del data["containers"]["shop_counter"]
        data["residents"] = [r for r in data["residents"] if r["id"] not in ("paco", "nuria", "sergio")]
        for resident in data["residents"]:
            del resident["credits"], resident["day_off"]
        # Where someone stood before a shop was built there.
        data["residents"][0]["x"], data["residents"][0]["y"] = 14, 4
        data["residents"][0]["activity"] = None
        loaded = self.manager.from_data(json.loads(json.dumps(data)))

        self.assertIn("grave_vera", loaded.interactables, "what the save had is kept")
        self.assertTrue(newer <= loaded.interactables.keys())
        self.assertEqual(loaded.containers["shop_counter"].count("canned_beans"), 10)
        ids = [item.instance_id for inventory in loaded.containers.values() for item in inventory.items]
        ids += [item.instance_id for resident in loaded.residents.values() for item in resident.inventory.items]
        self.assertEqual(len(ids), len(set(ids)), "no two items share an ID")
        pocket = loaded.registries.economy.starting_credits
        self.assertEqual([(r.credits, r.day_off) for r in loaded.residents.values()], [(pocket, None)] * 5)
        first = next(iter(loaded.residents.values()))
        self.assertTrue(loaded.passable()(first.tile), "nobody is left standing inside a wall")
        loaded.step(2 * MINUTES_PER_DAY)
        self.assertIn("mechanic", loaded.vacancies, "the new posts stand empty until someone takes them")


class WorkingEconomyTests(unittest.TestCase):
    def test_a_week_in_which_things_are_carried_worn_mended_earned_and_spent(self) -> None:
        world = SimulationWorld.demo_world(seed=3)
        hoes = [_owned(world, farmer_id, "hoe") for farmer_id in ("raul", "ines")]
        worst = 100.0
        mended = 0
        last = [hoe.condition for hoe in hoes]
        for _ in range(7 * MINUTES_PER_DAY):
            world.step(1)
            for index, hoe in enumerate(hoes):
                worst = min(worst, hoe.condition)
                if hoe.condition >= 100.0 > last[index]:
                    mended += 1
                last[index] = hoe.condition
            for resident in world.residents.values():
                self.assertGreaterEqual(resident.credits, 0.0, resident.name)
                for need in ("hunger", "tiredness", "social", "stress"):
                    self.assertLess(getattr(resident.needs, need), 100.0, (resident.name, need, world.clock.label))
        types = _types(world)
        self.assertGreaterEqual(types.count("goods_hauled"), 30)
        self.assertLess(worst, 50.0, "a hoe wore down")
        self.assertGreaterEqual(mended, 2, "and came back from the workshop as good as new")
        self.assertIn("item_bought", types)
        self.assertTrue(any("toma algo en la cantina" in line for line in world.event_log))
        self.assertNotIn("no_food", types)
        pocket = world.registries.economy.starting_credits
        self.assertTrue(all(resident.credits != pocket for resident in world.residents.values()), "everyone earned")
        # Whether anybody came to stay that week goes by what the week brought. Nobody was lost in it.
        self.assertGreaterEqual(len(world.residents), 9)
        self.assertEqual(world.deaths, [])

    def test_the_same_seed_gives_the_same_week(self) -> None:
        logs = []
        for _ in range(2):
            world = SimulationWorld.demo_world(seed=11)
            world.step(3 * MINUTES_PER_DAY)
            logs.append((world.event_log, [resident.credits for resident in world.residents.values()]))
        self.assertEqual(logs[0], logs[1])


if __name__ == "__main__":
    unittest.main()
