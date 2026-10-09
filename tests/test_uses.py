"""More than one thing to do with a thing (S60)."""

import json
import unittest
from dataclasses import replace

from save.save_manager import SaveManager
from simulation.ai.affect import split_use, use_target
from simulation.ai.routine_system import EXTRA_USE_APPEAL
from simulation.commands import AffectCommand
from simulation.items.item_system import USE_ITEM_APPEAL
from simulation.registries import DATA_DIR, InteractableRegistry, builtin_registries
from simulation.residents.activity import Activity
from simulation.residents.needs import Needs
from simulation.world import SimulationWorld
from ui.labels import describe_action
from world.custom_content import merged_interactable_data
from world.interactable import interactable_definition_from_data

MINUTES_PER_DAY = 24 * 60
USE = "task:use"


def _quiet(world: SimulationWorld, *resident_ids: str) -> None:
    """Have residents want for nothing and hold no job, so that they do what they are told and no more."""
    for resident_id in resident_ids or world.residents:
        resident = world.residents[resident_id]
        resident.needs = Needs(hunger=0, thirst=0, tiredness=0, social=0, stress=0)
        resident.job_id = resident.post_id = None
        resident.activity = None


def _one_use_each():
    """The game's own definitions with nothing to do with a thing but what it is for."""
    registries = builtin_registries()
    plain = InteractableRegistry()
    for kind in registries.interactables.kinds():
        plain.register(replace(registries.interactables.get(kind), more=()))
    return replace(registries, interactables=plain)


def _of_kind(world: SimulationWorld, kind: str):
    return [placed for placed in world.interactables.values() if placed.kind == kind]


def _run_until_using(world: SimulationWorld, resident, action: str, limit: int = 240) -> Activity:
    for _ in range(limit):
        world.step(1)
        resident.needs.hunger = resident.needs.thirst = 0.0
        activity = resident.activity
        if activity is not None and activity.action == action and activity.using:
            return activity
    raise AssertionError(f"{resident.name} never got to {action}: {resident.activity}")


class DataTests(unittest.TestCase):
    def test_a_thing_may_offer_more_than_what_it_is_for(self) -> None:
        kinds = builtin_registries().interactables
        bed = kinds.get("bed")
        self.assertEqual(bed.use.action, "sleep")
        self.assertEqual([use.action for use in bed.uses], ["sleep", "lie_down"])
        self.assertEqual([use.action for use in bed.more], ["lie_down"])
        self.assertIs(bed.use_named("lie_down"), bed.more[0])
        self.assertIsNone(bed.use_named("fly"))
        self.assertIs(bed.use_for("lie_down"), bed.more[0])
        self.assertIs(bed.use_for("fly"), bed.use, "what it is mainly for, for an action that is none of its own")
        self.assertIs(bed.use_for(None), bed.use)
        self.assertFalse(bed.more[0].unaware, "lying down is not being asleep")
        # Every extra use says what it is called, and a thing with none is as it was.
        with_more = [kinds.get(kind) for kind in kinds.kinds() if kinds.get(kind).more]
        self.assertGreaterEqual(len(with_more), 6)
        self.assertTrue(all(use.label for definition in with_more for use in definition.more))
        self.assertEqual(kinds.get("pantry").more, ())
        self.assertEqual(kinds.get("crate").uses, ())
        table = kinds.get("table")
        self.assertIsNone(table.use, "a table is for nothing in particular, as ever")
        self.assertEqual([use.action for use in table.uses], ["sit_table"], "and can be sat at")

    def test_nothing_that_was_added_is_rest(self) -> None:
        """Rest is what a bed is slept in for. Sitting and lying down a while once took sleep
        off whoever did them, and by night, too hungry to settle down to sleep, people sat
        up instead: in six weeks fifteen settlements of eighteen had starved."""
        kinds = builtin_registries().interactables
        for kind in kinds.kinds():
            definition = kinds.get(kind)
            for use in definition.more:
                self.assertGreaterEqual(use.per_minute.get("tiredness", 0.0), 0.0, (kind, use.action))
                self.assertFalse(use.unaware, (kind, use.action))

    def test_data_that_makes_no_sense_is_refused(self) -> None:
        use = {"action": "sit", "text": "se sienta", "minutes": 10, "label": "Sentarse"}
        good = {"name": "banco", "article": "un", "use": use, "uses": [{**use, "action": "lie", "label": "Tumbarse"}]}
        self.assertEqual(len(interactable_definition_from_data("bench", good).uses), 2)
        self.assertEqual(len(interactable_definition_from_data("bench", {**good, "use": None}).uses), 1)
        for bad in (
            {**good, "uses": [use]},
            {**good, "uses": [{**use, "action": "lie", "label": ""}]},
            {**good, "uses": [{"action": "lie", "label": "Tumbarse"}]},
        ):
            with self.assertRaises(ValueError, msg=str(bad)):
                interactable_definition_from_data("bench", bad)

    def test_a_pack_that_changes_a_thing_keeps_what_else_is_done_with_it(self) -> None:
        bed = builtin_registries().interactables.get("bed")
        merged = merged_interactable_data({"name": "catre"}, bed)
        again = interactable_definition_from_data("bed", merged)
        self.assertEqual([use.action for use in again.uses], ["sleep", "lie_down"])
        raw = json.loads((DATA_DIR / "interactables.json").read_text(encoding="utf-8"))
        self.assertEqual(raw["bed"]["uses"][0]["action"], "lie_down")

    def test_a_pack_that_changes_nothing_of_a_thing_leaves_all_of_it_as_it_was(self) -> None:
        """What a pack lays its changes over is the whole of the thing: nothing of it is lost."""
        kinds = builtin_registries().interactables
        for kind in kinds.kinds():
            base = kinds.get(kind)
            again = interactable_definition_from_data(kind, merged_interactable_data({}, base))
            self.assertEqual(again, base, kind)


class ToldTests(unittest.TestCase):
    def setUp(self) -> None:
        self.world = SimulationWorld.demo_world()
        _quiet(self.world)
        self.marta = self.world.residents["marta"]
        self.tank = _of_kind(self.world, "water_tank")[0]

    def test_one_of_the_things_there_are_to_do_with_it_is_told_by_name(self) -> None:
        world, marta, tank = self.world, self.marta, self.tank
        target = use_target(tank.object_id, "wash")
        self.assertEqual(split_use(target), (tank.object_id, "wash"))
        self.assertEqual(split_use(tank.object_id), (tank.object_id, None))
        result = world.apply_command(AffectCommand("marta", USE, target))
        self.assertTrue(result.ok, result.message)
        self.assertIn("(lavarse)", result.message)
        self.assertEqual((marta.activity.action, marta.activity.target_id), ("wash", tank.object_id))
        marta.needs.stress = 60.0
        activity = _run_until_using(world, marta, "wash")
        self.assertTrue(activity.ordered)
        self.assertEqual(describe_action(world, marta), "se lava en el depósito")
        before = marta.needs.stress
        held = sum(item.quantity for item in world.containers[tank.object_id].items)
        world.step(3)
        self.assertLess(marta.needs.stress, before, "it does what washing does")
        self.assertEqual(sum(item.quantity for item in world.containers[tank.object_id].items), held, "and drinks nothing")

    def test_told_plainly_it_is_what_the_thing_is_mainly_for(self) -> None:
        world, marta, tank = self.world, self.marta, self.tank
        marta.needs.thirst = 50.0
        result = world.apply_command(AffectCommand("marta", USE, tank.object_id))
        self.assertTrue(result.ok, result.message)
        self.assertEqual(marta.activity.action, "drink_water")
        self.assertNotIn("(", result.message)

    def test_what_a_thing_has_no_use_for_cannot_be_told(self) -> None:
        world, tank = self.world, self.tank
        for target in (use_target(tank.object_id, "fly"), use_target("nothing", "wash"), use_target(tank.object_id, "sleep")):
            self.assertFalse(world.apply_command(AffectCommand("marta", USE, target)).ok, target)

    def test_what_can_be_done_with_a_thing_is_listed_with_what_it_is_for_first(self) -> None:
        world, marta, tank = self.world, self.marta, self.tank
        marta.needs.thirst = 50.0
        found = world.affect.things_to_do(world, marta, tank)
        self.assertEqual([label for label, _kind, _target in found], ["Beber", "Lavarse"])
        self.assertEqual([target for _label, _kind, target in found], [tank.object_id, use_target(tank.object_id, "wash")])
        self.assertTrue(all(kind == USE for _label, kind, _target in found))
        for _label, kind, target in found:
            marta.activity, marta.orders = None, []
            self.assertTrue(world.apply_command(AffectCommand("marta", kind, target)).ok, target)
        crate = _of_kind(world, "crate")[0]
        self.assertEqual(world.affect.things_to_do(world, marta, crate), [])

    def test_a_thing_taken_up_for_one_thing_has_no_room_for_another(self) -> None:
        world, marta = self.world, self.marta
        bed = next(
            placed for placed in _of_kind(world, "bed") if world.affect.can_use(world, marta, placed, "use", "lie_down")
        )
        self.assertTrue(world.apply_command(AffectCommand("marta", USE, use_target(bed.object_id, "lie_down"))).ok)
        # It eases the nerves and no more: with none to ease she would be up again at once.
        marta.needs.stress = 60.0
        _run_until_using(world, marta, "lie_down")
        self.assertTrue(world.is_aware(marta), "lying down she sees what goes on")
        raul = world.residents["raul"]
        self.assertFalse(world.affect.can_use(world, raul, bed), "the bed is taken")
        self.assertFalse(world.affect.can_use(world, raul, bed, "use", "lie_down"))
        self.assertEqual(world.affect.things_to_do(world, raul, bed), [])

    def test_it_waits_its_turn_and_says_which_thing_and_what(self) -> None:
        world, marta, tank = self.world, self.marta, self.tank
        marta.needs.thirst, marta.needs.stress = 50.0, 60.0
        self.assertTrue(world.apply_command(AffectCommand("marta", USE, tank.object_id)).ok)
        self.assertTrue(world.apply_command(AffectCommand("marta", USE, use_target(tank.object_id, "wash"))).ok)
        queue = world.affect.queue(world, "marta")
        self.assertEqual(len(queue), 2)
        self.assertIn("(lavarse)", queue[-1].said)
        self.assertNotIn("(", queue[0].said)
        for _ in range(120):
            world.step(1)
            if marta.activity is not None and marta.activity.action == "wash":
                break
        self.assertEqual(marta.activity.action, "wash", "after drinking, she washes")


class OwnAccordTests(unittest.TestCase):
    def test_residents_weigh_everything_a_thing_offers(self) -> None:
        world = SimulationWorld.demo_world()
        marta = world.residents["marta"]
        marta.needs = Needs(hunger=0, thirst=0, tiredness=0, social=0, stress=80)
        tank = _of_kind(world, "water_tank")[0]
        routine = world.activities.routine
        kinds = world.definition_of(tank)
        drink, wash = kinds.use, kinds.use_named("wash")
        self.assertGreater(routine._score_use(world, marta, tank, wash), routine._score_use(world, marta, tank, drink))
        names = {(scored.name, scored.target_id) for scored in routine.candidates(world, marta)}
        self.assertIn(("wash", tank.object_id), names)
        marta.needs = Needs(hunger=0, thirst=70, tiredness=0, social=0, stress=0)
        self.assertGreater(routine._score_use(world, marta, tank, drink), routine._score_use(world, marta, tank, wash))
        # Left to herself on edge, with nothing else pressing, it is one of the ways of easing it she takes.
        marta.needs = Needs(hunger=0, thirst=0, tiredness=0, social=0, stress=90)
        marta.job_id = marta.post_id = None
        marta.activity = routine.plan(world, marta)
        eases = {use.action for kind in world.registries.interactables.kinds() for use in world.registries.interactables.get(kind).uses if use.per_minute.get("stress", 0) < 0}
        self.assertTrue(marta.activity.action in eases or marta.activity.partner_id is not None, marta.activity)

    def test_what_a_thing_offers_beside_appeals_a_little_less_than_what_a_thing_is_for(self) -> None:
        """And than a thing of their own that is to hand: a table to sit at does not come
        before the fire, nor before the toy somebody carries."""
        world = SimulationWorld.demo_world()
        marta = world.residents["marta"]
        marta.needs = Needs(hunger=0, thirst=0, tiredness=0, social=0, stress=90)
        routine = world.activities.routine
        table, fire = _of_kind(world, "table")[0], _of_kind(world, "campfire")[0]
        scored = {(each.name, each.target_id): each.score for each in routine.candidates(world, marta)}
        sitting = scored[("sit_table", table.object_id)]
        plain = routine._score_use(world, marta, table, world.definition_of(table).use_named("sit_table"))
        self.assertAlmostEqual(sitting, plain * EXTRA_USE_APPEAL)
        self.assertLess(EXTRA_USE_APPEAL, USE_ITEM_APPEAL)
        self.assertGreater(scored[(world.definition_of(fire).use.action, fire.object_id)], sitting)

    def test_weighing_what_else_a_thing_offers_throws_none_of_the_settlements_dice(self) -> None:
        """A settlement goes as it went until somebody takes one of them up: the grain of
        chance everything is weighed with is thrown as often as it was, and no oftener."""
        several, plain = SimulationWorld.demo_world(seed=7), SimulationWorld.demo_world(seed=7, registries=_one_use_each())
        for world in (several, plain):
            world.residents["marta"].needs = Needs(hunger=30, thirst=30, tiredness=30, social=30, stress=30)
        offered = several.activities.routine.candidates(several, several.residents["marta"])
        as_ever = plain.activities.routine.candidates(plain, plain.residents["marta"])
        self.assertGreater(len(offered), len(as_ever))
        self.assertEqual(several.rng.get_state(), plain.rng.get_state())
        names = {(each.name, each.target_id) for each in as_ever}
        self.assertEqual([each for each in offered if (each.name, each.target_id) in names], as_ever)

    def test_a_day_goes_as_it_did_while_nobody_takes_one_up(self) -> None:
        several, plain = SimulationWorld.demo_world(seed=7), SimulationWorld.demo_world(seed=7, registries=_one_use_each())
        extra = {use.action for kind in several.registries.interactables.kinds() for use in several.registries.interactables.get(kind).more}
        taken_up = False
        for _ in range(MINUTES_PER_DAY):
            several.step(1)
            plain.step(1)
            taken_up = taken_up or any(
                resident.activity is not None and resident.activity.action in extra for resident in several.residents.values()
            )
            if taken_up:
                break
            self.assertEqual(several.rng.get_state(), plain.rng.get_state(), several.clock.label)
        self.assertEqual(several.event_log[: len(plain.event_log) - 5], plain.event_log[: len(plain.event_log) - 5])

    def test_they_go_on_sleeping_and_working_as_they_did(self) -> None:
        """Ten days of a settlement that did not last six weeks when sitting was rest."""
        world = SimulationWorld.demo_world(seed=2)
        slept = worked = 0
        days = 10
        for _ in range(days * MINUTES_PER_DAY):
            world.step(1)
            for resident in world.residents.values():
                activity = resident.activity
                if activity is not None and activity.using:
                    slept += activity.action == "sleep"
                    worked += activity.action == "work"
        people = len(world.residents)
        self.assertEqual(world.deaths, [])
        self.assertGreater(slept / 60 / days / people, 5.5, "hours of sleep each, a day")
        self.assertGreater(worked / 60 / days / people, 3.0, "and of work")

class SaveTests(unittest.TestCase):
    def test_somebody_at_one_of_them_and_one_told_for_later_are_saved(self) -> None:
        manager = SaveManager()
        world = SimulationWorld.demo_world()
        _quiet(world)
        marta = world.residents["marta"]
        tank = _of_kind(world, "water_tank")[0]
        marta.needs.thirst = 50.0
        self.assertTrue(world.apply_command(AffectCommand("marta", USE, use_target(tank.object_id, "wash"))).ok)
        self.assertTrue(world.apply_command(AffectCommand("marta", USE, tank.object_id)).ok)
        marta.needs.stress = 60.0
        _run_until_using(world, marta, "wash")
        loaded = manager.from_data(json.loads(json.dumps(manager.to_data(world))))
        again = loaded.residents["marta"]
        self.assertEqual((again.activity.action, again.activity.target_id), ("wash", tank.object_id))
        self.assertEqual([order.target_id for order in again.orders], [tank.object_id])
        for each in (world, loaded):
            each.step(120)
        self.assertEqual(manager.to_data(loaded), manager.to_data(world))


if __name__ == "__main__":
    unittest.main()
