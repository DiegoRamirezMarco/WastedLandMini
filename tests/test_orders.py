import tempfile
import unittest
from pathlib import Path

from save.save_manager import SaveManager
from simulation.ai.leisure import leisure_settings_from_data
from simulation.commands import AffectCommand, CancelOrderCommand, HoldResidentCommand, ReleaseResidentCommand, SetFreeWillCommand
from simulation.residents.activity import HEED_ACTION, WAIT_ACTION, Activity, Order
from simulation.residents.needs import Needs
from simulation.tastes.taste import TAG, Taste
from simulation.work.salvage import SALVAGE_ACTION
from simulation.world import SimulationWorld


def _keep_content(world: SimulationWorld) -> None:
    for resident in world.residents.values():
        resident.needs = Needs(hunger=0, tiredness=0, social=0, stress=0)


def _settled(seed: int = 7) -> SimulationWorld:
    """The ready-made settlement with nothing felt by anyone for anyone, and nobody in need."""
    world = SimulationWorld.demo_world(seed=seed)
    world.relationships.clear()
    _keep_content(world)
    return world


def _run(world: SimulationWorld, minutes: int, until=None) -> bool:
    for _ in range(minutes):
        world.step(1)
        _keep_content(world)
        if until is not None and until():
            return True
    return False


def _types(world: SimulationWorld) -> list[str]:
    return [line.split(" | ")[1] for line in world.event_log]


def _ahead(world: SimulationWorld, resident_id: str) -> list[str]:
    return [queued.order.kind for queued in world.orders_of(resident_id)]


class QueueTests(unittest.TestCase):
    """What is said one thing after another is done one thing after another (S50)."""

    def test_the_first_thing_said_is_done_at_once_and_the_rest_wait_their_turn(self) -> None:
        world = _settled()
        world.step(60)
        raul = world.residents["raul"]
        self.assertEqual(world.orders_of("raul"), [])
        self.assertTrue(world.apply_command(AffectCommand("raul", "leisure:hum")).ok)
        self.assertTrue(raul.activity.ordered)
        self.assertEqual(raul.activity.action, "hum")
        self.assertTrue(world.apply_command(AffectCommand("raul", "with:talk", "marta")).ok)
        self.assertTrue(world.apply_command(AffectCommand("raul", "need:eat")).ok)
        self.assertEqual(raul.activity.action, "hum", "what came after did not take him from it")
        ahead = world.orders_of("raul")
        self.assertEqual([queued.order.kind for queued in ahead], ["leisure:hum", "with:talk", "need:eat"])
        self.assertEqual([queued.doing for queued in ahead], [True, False, False])
        self.assertEqual(ahead[1].said, "Que charle con Marta")
        self.assertEqual(_types(world).count("order_given"), 1)
        self.assertEqual(_types(world).count("order_queued"), 2)
        seen: list[str] = []

        def watch() -> bool:
            action = raul.activity.action if raul.activity is not None and raul.activity.ordered else None
            if action is not None and action != "talk" and (not seen or seen[-1] != action):
                seen.append(action)
            return not world.orders_of("raul")

        self.assertTrue(_run(world, 240, watch), "he never got through it")
        self.assertEqual(seen, ["hum", "chat", "eat"])
        _run(world, 30)
        self.assertFalse(raul.activity is not None and raul.activity.ordered, "with nothing left he goes about his day")
        self.assertIsNone(raul.doing)

    def test_no_more_can_be_put_ahead_of_them_than_the_data_says(self) -> None:
        world = _settled()
        most = world.registries.affect.most_orders
        self.assertTrue(world.apply_command(AffectCommand("raul", "leisure:sit")).ok)
        for _ in range(most):
            self.assertTrue(world.apply_command(AffectCommand("raul", "leisure:hum")).ok)
        result = world.apply_command(AffectCommand("raul", "leisure:hum"))
        self.assertFalse(result.ok)
        self.assertEqual(len(world.residents["raul"].orders), most)

    def test_one_thing_can_be_taken_back_and_the_rest_stand(self) -> None:
        world = _settled()
        raul = world.residents["raul"]
        for kind in ("leisure:sit", "leisure:hum", "leisure:nap"):
            world.apply_command(AffectCommand("raul", kind))
        self.assertTrue(world.apply_command(CancelOrderCommand("raul", 1)).ok)
        self.assertEqual(_ahead(world, "raul"), ["leisure:sit", "leisure:nap"])
        self.assertEqual(raul.activity.action, "sit")
        # Taking back what he is at, he leaves it off and goes on to the next.
        self.assertTrue(world.apply_command(CancelOrderCommand("raul", 0)).ok)
        self.assertIsNone(raul.activity)
        self.assertEqual(_ahead(world, "raul"), ["leisure:nap"])
        world.step(1)
        self.assertEqual((raul.activity.action, raul.activity.ordered), ("nap", True))
        self.assertFalse(world.apply_command(CancelOrderCommand("raul", 4)).ok)
        self.assertFalse(world.apply_command(CancelOrderCommand("nobody", 0)).ok)
        self.assertEqual(_types(world).count("order_cancelled"), 2)

    def test_told_to_drop_everything_they_drop_what_waits_as_well(self) -> None:
        world = _settled()
        raul = world.residents["raul"]
        for kind in ("leisure:sit", "leisure:hum", "leisure:nap"):
            world.apply_command(AffectCommand("raul", kind))
        self.assertTrue(world.apply_command(AffectCommand("raul", "task:stop")).ok)
        self.assertEqual((raul.activity, raul.orders, raul.doing), (None, [], None))

    def test_a_few_words_are_said_there_and_then_and_take_them_from_nothing(self) -> None:
        world = _settled()
        raul = world.residents["raul"]
        world.apply_command(AffectCommand("raul", "leisure:sit"))
        raul.mood = 40.0
        self.assertTrue(world.apply_command(AffectCommand("raul", "words:cheer")).ok)
        self.assertGreater(raul.mood, 40.0)
        self.assertEqual(_ahead(world, "raul"), ["leisure:sit"])
        self.assertEqual(raul.activity.action, "sit")

    def test_what_can_no_longer_be_done_when_its_turn_comes_is_let_go_and_said(self) -> None:
        world = _settled()
        raul = world.residents["raul"]
        world.relationship("raul", "marta").resentment = 80
        world.apply_command(AffectCommand("raul", "leisure:hum"))
        self.assertTrue(world.apply_command(AffectCommand("raul", "with:strike", "marta")).ok)
        self.assertTrue(world.apply_command(AffectCommand("raul", "leisure:nap")).ok)
        # By the time he gets to it, he has nothing against her.
        world.relationship("raul", "marta").resentment = 0
        self.assertTrue(_run(world, 120, lambda: raul.activity is not None and raul.activity.action == "nap"))
        self.assertIn("order_dropped", _types(world))
        self.assertNotIn("fight_started", _types(world))

    def test_stopped_or_taken_from_it_they_take_up_again_what_they_were_told(self) -> None:
        world = _settled()
        raul = world.residents["raul"]
        world.apply_command(AffectCommand("raul", "leisure:sit"))
        world.apply_command(AffectCommand("raul", "leisure:hum"))
        self.assertTrue(world.apply_command(HoldResidentCommand("raul")).ok)
        self.assertEqual(raul.activity.action, HEED_ACTION)
        self.assertEqual([order.kind for order in raul.orders], ["leisure:sit", "leisure:hum"])
        # Told something while he stands there, it goes after what he already had.
        self.assertTrue(world.apply_command(AffectCommand("raul", "leisure:nap")).ok)
        self.assertEqual(raul.activity.action, HEED_ACTION)
        self.assertTrue(world.apply_command(ReleaseResidentCommand("raul")))
        world.step(1)
        self.assertEqual((raul.activity.action, raul.activity.ordered), ("sit", True))
        self.assertEqual(_ahead(world, "raul"), ["leisure:sit", "leisure:hum", "leisure:nap"])
        # Somebody who comes to have words with him takes him from it, and he goes back to it after.
        marta = world.residents["marta"]
        marta.x, marta.y = raul.x + 1, raul.y
        marta.activity = Activity("talk", minutes_left=60, partner_id="raul", intent="chat")
        world.step(1)
        self.assertEqual(raul.activity.action, "chat")
        self.assertFalse(raul.activity.ordered)
        self.assertEqual(raul.orders[0], Order("leisure:sit"))
        self.assertTrue(_run(world, 60, lambda: raul.activity is not None and raul.activity.action == "sit"))

    def test_what_is_put_in_their_hands_is_theirs_at_once(self) -> None:
        world = _settled()
        world.step(60)
        paco = world.residents["paco"]
        self.assertTrue(world.apply_command(AffectCommand("paco", "task:salvage", "tyres_workshop")).ok)
        self.assertEqual((paco.activity.action, paco.activity.ordered), (SALVAGE_ACTION, True))
        self.assertEqual(_ahead(world, "paco"), ["task:salvage"])
        self.assertEqual(world.orders_of("paco")[0].said, "Que desguace una pila de neumáticos")

    def test_what_they_were_told_is_saved_with_them(self) -> None:
        world = _settled()
        world.step(60)
        for kind, target in (("leisure:sit", None), ("with:talk", "marta"), ("need:eat", None)):
            world.apply_command(AffectCommand("raul", kind, target))
        world.apply_command(SetFreeWillCommand("ines", False))
        manager = SaveManager()
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "save.json"
            manager.save(world, path)
            loaded = manager.load(path)
        raul = loaded.residents["raul"]
        self.assertEqual(raul.doing, Order("leisure:sit"))
        self.assertEqual(raul.orders, [Order("with:talk", "marta"), Order("need:eat")])
        self.assertTrue(raul.activity.ordered)
        self.assertFalse(loaded.residents["ines"].free_will)
        self.assertTrue(loaded.residents["marta"].free_will)
        self.assertEqual(_ahead(loaded, "raul"), ["leisure:sit", "with:talk", "need:eat"])
        for one in (world, loaded):
            one.step(300)
        self.assertEqual(world.event_log, loaded.event_log, "it goes on the same from where it was saved")

    def test_a_save_from_before_has_nobody_told_anything(self) -> None:
        world = _settled()
        manager = SaveManager()
        data = manager.to_data(world)
        for resident in data["residents"]:
            for field in ("doing", "orders", "free_will"):
                del resident[field]
            if resident["activity"] is not None:
                del resident["activity"]["ordered"]
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "save.json"
            manager.save(world, path)
            import json

            path.write_text(json.dumps(data), encoding="utf-8")
            loaded = manager.load(path)
        for resident in loaded.residents.values():
            self.assertEqual((resident.doing, resident.orders, resident.free_will), (None, [], True))


class FreeWillTests(unittest.TestCase):
    """A resident can be told to do nothing of their own accord (S50)."""

    def test_told_to_do_nothing_unasked_they_finish_what_they_are_at_and_then_wait(self) -> None:
        world = _settled()
        world.step(60)
        raul = world.residents["raul"]
        self.assertTrue(world.work.on_duty(world, raul))
        result = world.apply_command(SetFreeWillCommand("raul", False))
        self.assertTrue(result.ok, result.message)
        self.assertIn("will_changed", _types(world))
        self.assertTrue(world.work.on_duty(world, raul), "what he was at, he goes on with")
        raul.activity = None
        _run(world, 5)
        self.assertEqual(raul.current_action, WAIT_ACTION)
        tile = raul.tile
        _run(world, 6 * 60)
        self.assertEqual((raul.tile, raul.current_action), (tile, WAIT_ACTION), "he did nothing of his own all morning")
        self.assertFalse(world.interventions.pending_for(world, "raul"), "nor made up his mind about anything")

    def test_they_do_what_they_are_told_and_wait_again(self) -> None:
        world = _settled()
        world.step(60)
        raul = world.residents["raul"]
        world.apply_command(SetFreeWillCommand("raul", False))
        raul.activity = None
        world.step(1)
        self.assertTrue(world.apply_command(AffectCommand("raul", "leisure:hum")).ok)
        self.assertEqual(raul.activity.action, "hum")
        self.assertTrue(_run(world, 60, lambda: raul.current_action == WAIT_ACTION), "he never went back to waiting")

    def test_given_their_will_back_they_go_about_their_day(self) -> None:
        world = _settled()
        world.step(60)
        raul = world.residents["raul"]
        world.apply_command(SetFreeWillCommand("raul", False))
        raul.activity = None
        _run(world, 30)
        self.assertEqual(raul.current_action, WAIT_ACTION)
        self.assertTrue(world.apply_command(SetFreeWillCommand("raul", True)).ok)
        self.assertTrue(_run(world, 60, lambda: world.work.on_duty(world, raul)), "he never went back to his post")
        self.assertFalse(world.apply_command(SetFreeWillCommand("nobody", False)).ok)

    def test_a_body_that_can_wait_no_longer_is_seen_to_unasked(self) -> None:
        world = SimulationWorld.demo_world(seed=7)
        world.relationships.clear()
        world.step(60)
        raul = world.residents["raul"]
        world.apply_command(SetFreeWillCommand("raul", False))
        raul.activity = None
        desperate = world.registries.affect.desperate_need
        raul.needs = Needs(hunger=desperate - 25, thirst=0, tiredness=0, social=0, stress=0)
        world.step(15)
        self.assertEqual(raul.current_action, WAIT_ACTION, "hungry as he is, he waits to be told")
        raul.needs.hunger = desperate + 2
        ate = False
        for _ in range(90):
            world.step(1)
            raul.needs.thirst = raul.needs.tiredness = 0
            ate = ate or raul.current_action == "eat"
        self.assertTrue(ate, "he never saw to it")

    def test_what_was_put_in_their_hands_is_still_theirs_to_do(self) -> None:
        world = _settled()
        world.step(60)
        paco = world.residents["paco"]
        world.apply_command(SetFreeWillCommand("paco", False))
        world.apply_command(AffectCommand("paco", "task:salvage", "tyres_workshop"))
        # Taken from it part-way, he goes back to it with nobody telling him again.
        self.assertTrue(_run(world, 60, lambda: paco.current_action == SALVAGE_ACTION))
        paco.activity = None
        self.assertTrue(_run(world, 60, lambda: paco.current_action == SALVAGE_ACTION), "he left it half done")
        self.assertTrue(_run(world, 12 * 60, lambda: "tyres_workshop" not in world.interactables), "it was never taken apart")
        self.assertTrue(_run(world, 30, lambda: paco.current_action == WAIT_ACTION))

    def test_others_can_still_come_and_talk_to_whoever_waits(self) -> None:
        world = _settled()
        raul, marta = world.residents["raul"], world.residents["marta"]
        world.apply_command(SetFreeWillCommand("raul", False))
        raul.activity = None
        world.step(1)
        self.assertEqual(raul.current_action, WAIT_ACTION)
        self.assertTrue(world.activities.social._can_be_approached(world, raul, marta))


class LeisureTests(unittest.TestCase):
    """Passing the time, alone and with somebody, each by how they like it (S49)."""

    def test_leisure_is_data_and_what_makes_no_sense_is_refused(self) -> None:
        world = _settled()
        settings = world.registries.leisure
        self.assertEqual(list(settings.pastimes), ["stroll", "sit", "nap", "hum"])
        self.assertTrue(all(pastime.taste for pastime in settings.pastimes.values()))
        good = {"name": "Mirar", "label": "Que mire", "text": "{name} mira", "doing": "mira", "minutes": [5, 10]}
        leisure_settings_from_data({"alone": {"watch": good}})
        for wrong in (
            {"alone": {"watch": {key: value for key, value in good.items() if key != "doing"}}},
            {"alone": {"watch": {**good, "minutes": [10, 5]}}},
            {"alone": {"watch": {**good, "per_minute": {"luck": -1}}}},
            {"alone": {"watch": {**good, "sits": True, "lies": True}}},
            {"relief": {"thrilled": 2.0}},
            {"relief": {"liked": -1.0}},
        ):
            with self.assertRaises(ValueError, msg=wrong):
                leisure_settings_from_data(wrong)

    def test_a_pastime_takes_the_edge_off_and_is_done_where_they_stand(self) -> None:
        world = SimulationWorld.demo_world(seed=7)
        world.relationships.clear()
        world.step(60)
        raul = world.residents["raul"]
        raul.needs = Needs(hunger=0, thirst=0, tiredness=0, social=0, stress=60)
        tile = raul.tile
        self.assertTrue(world.apply_command(AffectCommand("raul", "leisure:sit")).ok)
        world.step(15)
        self.assertEqual((raul.tile, raul.current_action), (tile, "sit"))
        self.assertLess(raul.needs.stress, 60.0)
        self.assertIn("leisure_started", _types(world))
        self.assertIsNotNone(world.leisure.pastime_of(world, raul.activity))
        self.assertTrue(world.leisure.pastime_of(world, raul.activity).sits)

    def test_a_stroll_is_walked(self) -> None:
        world = _settled()
        world.step(60)
        raul = world.residents["raul"]
        self.assertTrue(world.apply_command(AffectCommand("raul", "leisure:stroll")).ok)
        tiles = set()
        for _ in range(15):
            world.step(1)
            _keep_content(world)
            tiles.add(raul.tile)
            self.assertEqual(raul.activity.action, "stroll")
        self.assertGreater(len(tiles), 5, "he hardly moved")

    def test_what_they_like_does_them_more_good_and_shows(self) -> None:
        def relief(leaning: float) -> tuple[float, SimulationWorld]:
            world = SimulationWorld.demo_world(seed=7)
            world.relationships.clear()
            world.step(60)
            raul = world.residents["raul"]
            world.tastes.profile(world, raul).tags["music"] = Taste(leaning=leaning)
            raul.needs = Needs(hunger=0, thirst=0, tiredness=0, social=0, stress=60)
            world.apply_command(AffectCommand("raul", "leisure:hum"))
            before = raul.needs.stress
            world.step(8)
            return before - raul.needs.stress, world

        loved, world = relief(90.0)
        hated, other = relief(-90.0)
        plain, _ = relief(0.0)
        self.assertGreater(loved, plain)
        self.assertGreater(plain, hated)
        # Having seen him at it, the player knows which way it goes with him, if not yet how far.
        option = next(each for each in world.affect_options("raul") if each.kind == "leisure:hum")
        self.assertIn(option.liked, ("liked", "loved"))
        loathed = next(each for each in other.affect_options("raul") if each.kind == "leisure:hum")
        self.assertIn(loathed.liked, ("disliked", "hated"))
        fresh = _settled()
        unseen = next(each for each in fresh.affect_options("raul") if each.kind == "leisure:hum")
        self.assertIsNone(unseen.liked, "nothing is known of what has never shown")
        self.assertTrue(any("| leisure_started |" in line and "disfruta" in line for line in world.event_log))

    def test_passing_the_time_with_somebody_goes_by_how_each_takes_it(self) -> None:
        def fondness(leaning: float) -> float:
            world = _settled()
            world.step(60)
            raul, marta = world.residents["raul"], world.residents["marta"]
            world.tastes.profile(world, raul).tags["cards"] = Taste(leaning=leaning)
            world.tastes.profile(world, marta).tags["cards"] = Taste(leaning=0.0)
            self.assertTrue(world.apply_command(AffectCommand("raul", "leisure:cards", "marta")).ok)
            self.assertTrue(_run(world, 120, lambda: "cards_started" in _types(world)), "they never sat down to it")
            self.assertTrue(_run(world, 120, lambda: raul.activity is None or raul.activity.action != "cards"))
            return world.relationship("raul", "marta").affection

        self.assertGreater(fondness(90.0), fondness(-90.0))

    def _bar_open(self) -> SimulationWorld:
        """The settlement in the evening, with somebody behind the bar and Raúl fond of Marta."""
        world = _settled()
        world.relationship("raul", "marta").affection = 30
        for name in ("raul", "marta"):
            world.residents[name].credits = 50.0
        self.assertNotIn("leisure:invite_drink", [option.kind for option in world.affect_with("raul", "marta")],
                         "with nobody behind the bar there is nowhere to go on to")
        world.clock.hour, world.clock.minute = 18, 0
        on_offer = lambda: "leisure:invite_drink" in [option.kind for option in world.affect_with("raul", "marta")]
        self.assertTrue(_run(world, 180, on_offer), "the bar never opened")
        return world

    def test_asked_for_a_drink_they_go_on_to_where_there_is_one_if_they_care_to(self) -> None:
        world = self._bar_open()
        raul, marta = world.residents["raul"], world.residents["marta"]
        self.assertTrue(world.apply_command(AffectCommand("raul", "leisure:invite_drink", "marta")).ok)
        self.assertTrue(_run(world, 120, lambda: "invite_drink_started" in _types(world)))
        went = {"raul": False, "marta": False}

        def watch() -> bool:
            for name, resident in (("raul", raul), ("marta", marta)):
                went[name] = went[name] or (resident.activity is not None and resident.activity.action == "drink")
            return all(went.values())

        self.assertTrue(_run(world, 30, watch), f"they did not both go on for it: {went}")

    def test_whoever_does_not_care_for_them_does_not_go(self) -> None:
        world = self._bar_open()
        raul, marta = world.residents["raul"], world.residents["marta"]
        world.relationship("marta", "raul").affection = -40
        world.apply_command(AffectCommand("raul", "leisure:invite_drink", "marta"))
        self.assertTrue(_run(world, 150, lambda: "leisure_declined" in _types(world)), "she never said no")
        self.assertFalse(marta.activity is not None and marta.activity.action == "drink")

    def test_a_taste_for_a_pastime_is_a_taste_like_any_other(self) -> None:
        world = _settled()
        raul = world.residents["raul"]
        taken = world.tastes.takes(world, raul, "strolling")
        self.assertIn(taken, ("hated", "disliked", "neutral", "liked", "loved"))
        self.assertIsNotNone(world.tastes.profile(world, raul).find(TAG, "strolling"))
        self.assertEqual(world.tastes.takes(world, raul, "strolling"), taken, "it is the same every time")
        self.assertEqual(world.tastes.label(world, "tag:strolling"), "los paseos")


if __name__ == "__main__":
    unittest.main()
