"""Blows, theft, and what goes with what somebody is like (S63)."""

import json
import unittest

from save.save_manager import SaveManager
from simulation.commands import AffectCommand
from simulation.economy.pilfering import FUND_THEFT_ACTION, PICK_ACTION
from simulation.events.event import DomainEvent
from simulation.registries import DATA_DIR, builtin_registries
from simulation.residents.activity import Activity
from simulation.residents.needs import Needs
from simulation.social.deeds import DEEDS
from simulation.social.interaction import interaction_definition_from_data
from simulation.social.social_system import SocialSystem
from simulation.world import SimulationWorld

HERE, BESIDE = (20, 18), (21, 18)
# The trait each order is for, as the game comes: the four that were asked for, ten good and ten bad.
ASKED = ("bully", "charmer", "gossip", "clown")
GOOD = ("caring", "teacher", "peacemaker", "listener", "generous", "rousing", "brave", "upright", "handy", "affectionate")
BAD = ("swindler", "schemer", "envious", "brute", "idler", "grouch", "scrounger", "tempter", "spiteful", "cold")


def _types(world: SimulationWorld) -> list[str]:
    return [line.split(" | ")[1] for line in world.event_log]


def _stand(resident, tile) -> None:
    resident.x, resident.y = tile
    resident.needs = Needs(hunger=0, thirst=0, tiredness=0, social=0, stress=0)
    resident.job_id = resident.post_id = None
    resident.activity = Activity("wander", minutes_left=6000, using=True)


def _pair(world: SimulationWorld, a_id: str = "marta", b_id: str = "raul"):
    """Two residents side by side in the open, wanting for nothing, with nothing between them."""
    world.relationships.clear()
    for resident in world.residents.values():
        _stand(resident, (5, 5))
    a, b = world.residents[a_id], world.residents[b_id]
    _stand(a, HERE)
    _stand(b, BESIDE)
    return a, b


def _order_of(world: SimulationWorld, trait: str) -> tuple[str, str]:
    """The order a trait opens, and the exchange it is."""
    return next(
        (f"with:{name}", order.interaction)
        for name, order in world.registries.affect.exchanges.items()
        if order.trait == trait
    )


def _do(world: SimulationWorld, a, b, trait: str, limit: int = 240) -> None:
    """Have `a`, who is that way, be told what the trait opens with `b`, and see it through."""
    if trait not in a.traits:
        a.traits.append(trait)
    kind, interaction = _order_of(world, trait)
    result = world.apply_command(AffectCommand(a.resident_id, kind, b.resident_id))
    assert result.ok, result.message
    started = False
    for _ in range(limit):
        world.step(1)
        for resident in (a, b):
            resident.needs.hunger = resident.needs.thirst = 0.0
        busy = any(each.activity is not None and each.activity.action == interaction and each.activity.using for each in (a, b))
        started = started or busy
        if started and not busy:
            return
    raise AssertionError(f"{trait} never ran its course")


class DataTests(unittest.TestCase):
    def test_there_are_the_four_ten_good_and_ten_bad_each_with_something_only_they_can_be_told(self) -> None:
        registries = builtin_registries()
        for trait in (*ASKED, *GOOD, *BAD):
            definition = registries.traits.find(trait)
            self.assertIsNotNone(definition, trait)
            self.assertTrue(definition["name"], trait)
            orders = [order for order in registries.affect.exchanges.values() if order.trait == trait]
            self.assertEqual(len(orders), 1, trait)
            self.assertIn(orders[0].interaction, registries.interactions, trait)
            self.assertIn("{target}", orders[0].label)
        self.assertTrue(all(registries.traits.find(trait).get("flaw") for trait in BAD))
        self.assertFalse(any(registries.traits.find(trait).get("flaw") for trait in GOOD))
        names = [registries.traits.find(trait)["name"] for trait in (*ASKED, *GOOD, *BAD)]
        self.assertEqual(len(set(names)), 24)

    def test_nobody_comes_with_more_traits_than_anybody_can_have_and_all_of_them_are_there(self) -> None:
        from simulation.residents.founding import MAX_TRAITS

        registries = builtin_registries()
        world = SimulationWorld.demo_world()
        held = []
        for resident in world.residents.values():
            self.assertLessEqual(len(resident.traits), MAX_TRAITS, resident.name)
            for trait in resident.traits:
                self.assertIsNotNone(registries.traits.find(trait), (resident.name, trait))
            held += resident.traits
        raw = json.loads((DATA_DIR / "world_events.json").read_text(encoding="utf-8"))
        for newcomer in raw["newcomers"]:
            self.assertLessEqual(len(newcomer.get("traits", [])), MAX_TRAITS, newcomer["id"])
            for trait in newcomer.get("traits", []):
                self.assertIsNotNone(registries.traits.find(trait), (newcomer["id"], trait))
            held += newcomer.get("traits", [])
        new = set(ASKED) | set(GOOD) | set(BAD)
        self.assertGreaterEqual(len(new & set(held)), 18, "most of them are met in a settlement that comes ready made")

    def test_what_stealing_is_told_with_has_its_icon(self) -> None:
        from graphics.ui_art import GLYPHS, HUES

        affect = builtin_registries().affect
        for orders in (affect.tasks, affect.exchanges, affect.pastimes, affect.incitements, affect.needs):
            for name, order in orders.items():
                if order.icon is not None:
                    self.assertIn(order.icon, GLYPHS, name)
                    self.assertIn(order.icon, HUES, name)
        self.assertEqual(affect.tasks["steal"].icon, "steal")

    def test_every_deed_named_in_the_data_is_one_the_game_knows(self) -> None:
        named = {deed for interaction in builtin_registries().interactions.values() for deed in interaction.deeds}
        self.assertTrue(named)
        self.assertTrue(named <= set(DEEDS), named - set(DEEDS))
        raw = json.loads((DATA_DIR / "social.json").read_text(encoding="utf-8"))
        self.assertEqual(raw["cow"]["towards_doer"]["fear"], 12)

    def test_data_that_makes_no_sense_is_refused(self) -> None:
        good = {"minutes": [1, 2], "importance": 10, "text": "{a} y {b}", "memory": "Algo con {other}."}
        self.assertEqual(interaction_definition_from_data("x", good).deeds, ())
        for bad in ({**good, "towards_doer": {"hunger": 1}}, {**good, "other_needs": {"affection": 1}}):
            with self.assertRaises(ValueError, msg=str(bad)):
                interaction_definition_from_data("x", bad)
        registries = builtin_registries()
        from dataclasses import replace

        odd = replace(registries.interactions["cow"], deeds=("fly",))
        with self.assertRaisesRegex(ValueError, "fly"):
            replace(registries, interactions={**registries.interactions, "cow": odd}).validate()


class TraitTests(unittest.TestCase):
    def setUp(self) -> None:
        self.world = SimulationWorld.demo_world()
        self.marta, self.raul = _pair(self.world)

    def test_only_whoever_is_that_way_can_be_told(self) -> None:
        world, marta = self.world, self.marta
        marta.traits = []
        kind, _interaction = _order_of(world, "bully")
        self.assertFalse(world.apply_command(AffectCommand("marta", kind, "raul")).ok)
        self.assertNotIn(kind, [option.kind for option in world.affect.with_whom(world, "marta", "raul")])
        marta.traits = ["bully"]
        self.assertIn(kind, [option.kind for option in world.affect.with_whom(world, "marta", "raul")])
        self.assertTrue(world.apply_command(AffectCommand("marta", kind, "raul")).ok, "and nothing has to be felt for it")

    def test_cowing_somebody_leaves_them_afraid_and_is_one_sided(self) -> None:
        world, marta, raul = self.world, self.marta, self.raul
        raul.mood = marta.mood = 50.0
        _do(world, marta, raul, "bully")
        his, hers = world.relationship("raul", "marta"), world.relationship("marta", "raul")
        self.assertGreaterEqual(his.fear, 12)
        self.assertEqual(hers.fear, 0.0, "she is not the one who was cowed")
        self.assertGreater(raul.needs.stress, marta.needs.stress)
        mine = world.memories.recent("marta", 1)[-1]
        theirs = world.memories.recent("raul", 1)[-1]
        self.assertNotEqual(mine.text, theirs.text, "each remembers their side of it")
        self.assertLess(theirs.emotional_value, mine.emotional_value)
        self.assertIn("cow_started", _types(world))

    def test_making_somebody_laugh_lifts_them_and_they_like_whoever_did(self) -> None:
        world, marta, raul = self.world, self.marta, self.raul
        raul.mood, raul.needs.stress = 40.0, 60.0
        _do(world, marta, raul, "clown")
        self.assertGreater(raul.mood, 40.0)
        self.assertLess(raul.needs.stress, 60.0)
        self.assertGreater(world.relationship("raul", "marta").affection, world.relationship("marta", "raul").affection)

    def test_worming_something_out_has_the_news_and_a_taste_out_of_them(self) -> None:
        world, marta, raul = self.world, self.marta, self.raul
        fact = world.emit_event(DomainEvent("found", 40, "Raúl encuentra algo", ["raul"]), fact_text="Raúl encontró un tesoro")
        world.tastes.profile(world, raul).tags["sweet"] = __import__("simulation.tastes.taste", fromlist=["Taste"]).Taste(leaning=90)
        self.assertFalse(world.knowledge.knows("marta", fact.fact_id))
        _do(world, marta, raul, "gossip")
        self.assertTrue(world.knowledge.knows("marta", fact.fact_id))
        self.assertTrue(world.tastes.found_out(world, raul, "marta"), "and she knows something of what he likes")

    def test_a_scrounger_has_something_to_eat_off_them_and_a_generous_soul_gives(self) -> None:
        world, marta, raul = self.world, self.marta, self.raul
        world.stock(raul.inventory, "stew", 1, "raul")
        _do(world, marta, raul, "scrounger")
        self.assertEqual([item.owner_id for item in marta.inventory.items if item.definition_id == "stew"], ["marta"])
        self.assertFalse([item for item in raul.inventory.items if item.definition_id == "stew"])
        self.assertGreater(world.relationship("raul", "marta").resentment, 0)
        _do(world, marta, raul, "generous")
        self.assertEqual([item.owner_id for item in raul.inventory.items if item.definition_id == "stew"], ["raul"])

    def test_a_swindler_talks_them_out_of_what_they_have_and_it_is_a_thing_that_happened(self) -> None:
        world, marta, raul = self.world, self.marta, self.raul
        raul.credits, marta.credits = 20.0, 0.0
        _do(world, marta, raul, "swindler")
        self.assertGreater(marta.credits, 0.0)
        self.assertEqual(marta.credits + raul.credits, 20.0)
        self.assertTrue(any("timó" in fact.text for fact in world.knowledge.facts.values()))

    def test_a_brute_hurts_and_somebody_caring_mends(self) -> None:
        world, marta, raul = self.world, self.marta, self.raul
        _do(world, marta, raul, "brute")
        self.assertTrue(raul.injuries)
        hurt = sum(injury.severity for injury in raul.injuries)
        world.decisions.clear()
        _stand(marta, HERE)
        _stand(raul, BESIDE)
        _do(world, marta, raul, "caring")
        self.assertLess(sum(injury.severity for injury in raul.injuries), hurt)

    def test_an_idler_has_them_leave_what_they_were_about(self) -> None:
        world, marta, raul = self.world, self.marta, self.raul
        _do(world, marta, raul, "idler")
        self.assertIsNotNone(raul.activity)
        self.assertEqual(raul.activity.action, "sit", "he has sat down to do nothing")
        self.assertTrue(raul.activity.led)

    def test_talked_into_idling_their_shift_does_not_call_them_back(self) -> None:
        """Left to themselves a pastime ends when work calls (S62). Not this one."""
        world = SimulationWorld.demo_world()
        world.clock.hour = 11
        worker = next(resident for resident in world.residents.values() if world.work.candidate(world, resident) is not None)
        idler = next(resident for resident in world.residents.values() if resident is not worker)
        worker.needs = Needs(hunger=0, thirst=0, tiredness=0, social=0, stress=0)
        from simulation.social import deeds

        deeds.idle(world, idler, worker)
        self.assertEqual(worker.activity.action, "sit")
        for _ in range(5):
            world.step(1)
            worker.needs.hunger = worker.needs.thirst = 0.0
        self.assertEqual(worker.activity.action, "sit", "still at it, shift or no shift")
        saved = SaveManager().to_data(world)
        self.assertGreaterEqual(saved["version"], 52)
        loaded = SaveManager().from_data(json.loads(json.dumps(saved)))
        self.assertTrue(loaded.residents[worker.resident_id].activity.led)
        for resident in saved["residents"]:
            if resident.get("activity"):
                resident["activity"].pop("led", None)
        older = SaveManager().from_data(json.loads(json.dumps(saved)))
        self.assertFalse(older.residents[worker.resident_id].activity.led)

    def test_what_is_said_of_each_of_them_is_their_side_of_it(self) -> None:
        from ui.labels import describe_action

        world, marta, raul = self.world, self.marta, self.raul
        marta.traits.append("bully")
        kind, interaction = _order_of(world, "bully")
        self.assertTrue(world.apply_command(AffectCommand("marta", kind, "raul")).ok)
        for _ in range(60):
            world.step(1)
            if raul.activity is not None and raul.activity.action == interaction:
                break
        self.assertEqual(raul.activity.action, interaction)
        self.assertEqual(describe_action(world, marta), "intimida a Raúl")
        self.assertEqual(describe_action(world, raul), "se achanta ante Marta")
        for definition in world.registries.interactions.values():
            if definition.deeds or definition.towards_doer:
                self.assertTrue(definition.doing and definition.doing_other, definition.interaction_id)

    def test_a_schemer_sets_them_against_whoever_she_cannot_stand_and_a_peacemaker_undoes_it(self) -> None:
        world, marta, raul = self.world, self.marta, self.raul
        world.relationship("marta", "ines").resentment = 60
        _do(world, marta, raul, "schemer")
        stirred = world.relationship("raul", "ines").resentment
        self.assertGreater(stirred, 0)
        _stand(marta, HERE)
        _stand(raul, BESIDE)
        _do(world, marta, raul, "peacemaker")
        self.assertLess(world.relationship("raul", "ines").resentment, stirred)

    def test_somebody_led_astray_goes_for_a_drink_care_for_it_or_not(self) -> None:
        """Asked for a drink, somebody goes if they care for whoever asked (S49). Whoever is a
        bad influence will not hear of it."""
        world = SimulationWorld.demo_world()
        nuria, vera = world.residents["nuria"], world.residents["vera"]
        nuria.traits.append("tempter")
        for resident in (nuria, vera):
            resident.credits = 50.0
        world.relationship("vera", "nuria").affection = -40
        world.clock.hour, world.clock.minute = 18, 0

        def on_offer() -> bool:
            return "with:lead_astray" in [option.kind for option in world.affect_with("nuria", "vera")]

        for _ in range(180):
            if on_offer():
                break
            world.step(1)
        self.assertTrue(on_offer(), "the bar never opened")
        self.assertTrue(world.apply_command(AffectCommand("nuria", "with:lead_astray", "vera")).ok)
        went = {"nuria": False, "vera": False}
        for _ in range(180):
            world.step(1)
            for name, resident in (("nuria", nuria), ("vera", vera)):
                went[name] = went[name] or (resident.activity is not None and resident.activity.action == "drink")
            if all(went.values()):
                break
        self.assertIn("lead_astray_started", _types(world))
        self.assertTrue(all(went.values()), f"they did not both go on for it: {went}")
        self.assertNotIn("leisure_declined", _types(world))

    def test_every_one_of_them_runs_its_course(self) -> None:
        for trait in (*ASKED, *GOOD, *BAD):
            if trait == "tempter":
                # That one leads to the bar, which has to be open: it has a test of its own.
                continue
            world = SimulationWorld.demo_world()
            marta, raul = _pair(world)
            raul.credits = 10.0
            world.stock(raul.inventory, "stew", 1, "raul")
            world.stock(marta.inventory, "stew", 1, "marta")
            _do(world, marta, raul, trait)
            _kind, interaction = _order_of(world, trait)
            self.assertIn(f"{interaction}_started", _types(world), trait)
            self.assertTrue(world.memories.recent("raul", 1), trait)


class StealTests(unittest.TestCase):
    def setUp(self) -> None:
        self.world = SimulationWorld.demo_world()
        self.marta, self.raul = _pair(self.world)
        self.marta.traits = []

    def _targets(self) -> list[str]:
        option = next((each for each in self.world.affect.options(self.world, "marta") if each.kind == "task:steal"), None)
        return [target for target, _name in option.targets] if option is not None else []

    def test_stealing_is_told_of_whoever_they_resent_who_has_something_on_them(self) -> None:
        world, marta, raul = self.world, self.marta, self.raul
        world.stock(raul.inventory, "old_radio", 1, "raul")
        self.assertEqual(self._targets(), [], "she has nothing against him, and is not that way")
        world.relationship("marta", "raul").resentment = 20
        self.assertEqual(self._targets(), [], "nor is a little enough for somebody who feels for others as she does")
        world.relationship("marta", "raul").resentment = 60
        self.assertGreater(world.items.leaning_to_steal(world, marta, raul), 0)
        self.assertEqual(self._targets(), ["raul"])
        result = world.apply_command(AffectCommand("marta", "task:steal", "raul"))
        self.assertTrue(result.ok, result.message)
        self.assertEqual(marta.activity.action, PICK_ACTION)
        for _ in range(30):
            world.step(1)
            if "theft_committed" in _types(world):
                break
        self.assertIn("theft_committed", _types(world))
        taken = [item for item in marta.inventory.items if item.definition_id == "old_radio"]
        self.assertEqual([item.owner_id for item in taken], ["raul"], "it has changed hands, and is still his")
        attempt = world.thefts[-1]
        self.assertEqual((attempt.thief_id, attempt.victim_id), ("marta", "raul"))
        self.assertTrue(attempt.discovered, "he was standing right there")

    def test_whoever_is_given_to_it_can_be_told_of_anybody_and_of_what_is_everybodys(self) -> None:
        world, marta, raul = self.world, self.marta, self.raul
        marta.traits = ["kleptomaniac"]
        world.stock(raul.inventory, "old_radio", 1, "raul")
        targets = self._targets()
        self.assertIn("raul", targets)
        places = [target for target in targets if target in world.containers]
        self.assertTrue(places, "the stores and the shop")
        self.assertEqual(targets[: len(places)], places, "the places first")
        self.assertTrue(any(world.definition_of(world.interactables[each]).store is not None for each in places))
        store = next(each for each in places if world.definition_of(world.interactables[each]).store is not None)
        world.stock(world.containers[store], "canned_beans", 3, None)
        self._steal_from(store)
        self.assertEqual(marta.activity.target_id, store)
        self._until_taken()
        attempt = world.thefts[-1]
        self.assertEqual((attempt.thief_id, attempt.container_id), ("marta", store))
        self.assertEqual([item.instance_id for item in marta.inventory.items if item.owner_id == "marta"], [attempt.item_instance_id])

    def _steal_from(self, place: str) -> None:
        result = self.world.apply_command(AffectCommand("marta", "task:steal", place))
        self.assertTrue(result.ok, result.message)
        self.assertEqual(self.marta.activity.action, FUND_THEFT_ACTION)

    def _until_taken(self) -> None:
        for _ in range(240):
            self.world.step(1)
            self.marta.needs = Needs(hunger=0, thirst=0, tiredness=0, social=0, stress=0)
            if "theft_committed" in _types(self.world):
                break
        self.assertIn("theft_committed", _types(self.world))

    def test_from_a_store_with_nothing_in_it_it_is_taken_from_where_its_things_are_kept_at_hand(self) -> None:
        world, marta = self.world, self.marta
        marta.traits = ["kleptomaniac"]
        store = next(
            object_id for object_id, placed in world.interactables.items() if world.definition_of(placed).store is not None
        )
        world.containers[store].items.clear()
        at_hand = [
            object_id
            for object_id, placed in world.interactables.items()
            if object_id in world.containers and world.definition_of(placed).outlet is not None
        ]
        self.assertTrue(at_hand)
        self.assertTrue(
            any(item.owner_id is None for object_id in at_hand for item in world.containers[object_id].items),
            "the pantries and the tank are not empty",
        )
        self.assertIn(store, self._targets(), "the stores are the settlement's, wherever the things are")
        self._steal_from(store)
        self.assertIn(marta.activity.target_id, at_hand)
        self._until_taken()
        attempt = world.thefts[-1]
        self.assertEqual(attempt.thief_id, "marta")
        self.assertIn(attempt.container_id, at_hand)
        self.assertIn(attempt.item_instance_id, [item.instance_id for item in marta.inventory.items])
        for object_id in (store, *at_hand):
            world.containers[object_id].items.clear()
        self.assertNotIn(store, self._targets(), "with nothing anywhere there is nothing to tell them to take")

    def test_somebody_past_caring_for_hunger_can_be_told_to_take_from_the_stores(self) -> None:
        world, marta = self.world, self.marta
        self.assertFalse([target for target in self._targets() if target in world.containers])
        marta.needs.hunger = world.registries.affect.desperate_need
        self.assertTrue([target for target in self._targets() if target in world.containers])

    def test_what_cannot_be_stolen_from_is_refused(self) -> None:
        world = self.world
        for target in ("raul", "nobody", "nothing"):
            self.assertFalse(world.apply_command(AffectCommand("marta", "task:steal", target)).ok, target)


if __name__ == "__main__":
    unittest.main()
