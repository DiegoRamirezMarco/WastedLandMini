import tempfile
import unittest
from pathlib import Path

from save.save_manager import SaveManager
from simulation.ai.placing import (
    BUILD,
    CHILD,
    CHOOSE,
    ENTER,
    OBJECT,
    PASTIME,
    POST,
    RESIDENT,
    ROOM,
    SITE,
    STAY,
    TAKE_APART,
    TAKE_UP,
    USE,
    WITH,
    WORK,
    placing_settings_from_data,
)
from simulation.commands import (
    AffectCommand,
    HandChildCommand,
    HandItemCommand,
    PlaceObjectCommand,
    ProposeObjectCommand,
    PutDownCommand,
)
from simulation.family.children import CARRIED
from simulation.items.handing import TO_CONTAINER, TO_RESIDENT, handing_settings_from_data
from simulation.residents.activity import HEED_ACTION, SERVE_ACTION, Activity, Order
from simulation.residents.needs import Needs
from simulation.work.expedition import Expedition
from simulation.work.salvage import SALVAGE_ACTION
from simulation.work.work_system import WORK_ACTION
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


def _at(world: SimulationWorld, object_id: str) -> tuple[int, int]:
    placed = world.interactables[object_id]
    return (placed.x, placed.y)


def _beside(one: tuple[int, int], other: tuple[int, int], within: int = 1) -> bool:
    return abs(one[0] - other[0]) + abs(one[1] - other[1]) <= within


def _out() -> Expedition:
    """A trip outside that is not over for as long as any test runs."""
    return Expedition(returns_at=10**9, finds=0, danger=0.0)


def _definitions(world: SimulationWorld) -> list:
    return [world.registries.items.get(item_id) for item_id in world.registries.items.ids()]


def _born(world: SimulationWorld, mother_id: str = "ines", father_id: str | None = "tomas"):
    mother = world.residents[mother_id]
    mother.expecting_with = father_id
    return world.children.give_birth(world, mother)


class PlacingDataTests(unittest.TestCase):
    def test_how_somebody_is_put_down_is_data(self) -> None:
        world = _settled()
        settings = world.registries.placing
        self.assertGreaterEqual(settings.reach, 1)
        self.assertIn(settings.otherwise, world.registries.leisure.pastimes)
        self.assertIn("{thing}", settings.use)
        self.assertTrue(all("{thing}" in said for said in settings.uses.values()))

    def test_bad_data_is_refused(self) -> None:
        with self.assertRaises(ValueError):
            placing_settings_from_data({"reach": 0})
        with self.assertRaises(ValueError):
            handing_settings_from_data({"stress": [9, 2]})
        with self.assertRaises(ValueError):
            handing_settings_from_data({"worth_most": 0})


class GroundTests(unittest.TestCase):
    """Put down on bare ground, somebody is simply there now (S51)."""

    def test_they_are_where_they_are_put_at_once(self) -> None:
        world = _settled()
        world.step(30)
        raul = world.residents["raul"]
        far = (50, 28)
        self.assertGreater(abs(raul.x - far[0]) + abs(raul.y - far[1]), 10)
        result = world.apply_command(PutDownCommand("raul", far))
        self.assertTrue(result.ok)
        self.assertEqual(result.does, STAY)
        self.assertEqual(raul.tile, far, "there, and not on the way there")
        self.assertIsNone(raul.activity)
        self.assertIn("resident_placed", _types(world))

    def test_put_down_where_nobody_can_stand_they_are_stood_beside_it(self) -> None:
        world = _settled()
        raul = world.residents["raul"]
        bar = _at(world, "bar")
        result = world.apply_command(PutDownCommand("raul", bar))
        self.assertTrue(result.ok)
        self.assertNotEqual(raul.tile, bar)
        self.assertTrue(world.passable()(raul.tile))
        self.assertTrue(_beside(raul.tile, bar, world.registries.placing.reach * 2))

    def test_nobody_is_stood_on_somebody_else(self) -> None:
        world = _settled()
        marta = world.residents["marta"]
        self.assertTrue(world.apply_command(PutDownCommand("raul", marta.tile)).ok)
        self.assertNotEqual(world.residents["raul"].tile, marta.tile)

    def test_off_the_map_there_is_nowhere_to_put_them(self) -> None:
        world = _settled()
        raul = world.residents["raul"]
        before = raul.tile
        result = world.apply_command(PutDownCommand("raul", (-40, -40)))
        self.assertFalse(result.ok)
        self.assertEqual(raul.tile, before)

    def test_what_they_were_told_before_is_taken_up_again_after(self) -> None:
        world = _settled()
        world.step(60)
        raul = world.residents["raul"]
        self.assertTrue(world.apply_command(AffectCommand("raul", "leisure:sit")).ok)
        self.assertTrue(world.apply_command(AffectCommand("raul", "need:eat")).ok)
        self.assertTrue(world.apply_command(PutDownCommand("raul", (50, 28))).ok)
        self.assertEqual(raul.orders, [Order("leisure:sit"), Order("need:eat")], "nothing they were told is lost")
        world.step(1)
        self.assertEqual(raul.doing, Order("leisure:sit"))

    def test_who_cannot_be_told_anything_cannot_be_picked_up(self) -> None:
        world = _settled()
        raul, tomas = world.residents["raul"], world.residents["tomas"]
        raul.expedition = _out()
        self.assertFalse(world.apply_command(PutDownCommand("raul", (20, 20))).ok)
        tomas.activity = Activity(SERVE_ACTION, None, [], 600, using=True)
        before = tomas.tile
        result = world.apply_command(PutDownCommand("tomas", (20, 20)))
        self.assertFalse(result.ok)
        self.assertIn("condena", result.message)
        self.assertEqual(tomas.tile, before)
        self.assertFalse(world.foresee_put_down("tomas", (20, 20)).ok)


class ObjectTests(unittest.TestCase):
    """What somebody is put down on is what they set about (S51)."""

    def test_on_a_bed_that_is_theirs_to_use_they_sleep_at_once(self) -> None:
        world = _settled()
        raul = world.residents["raul"]
        bed = next(
            object_id
            for object_id, placed in world.interactables.items()
            if placed.kind == "bed" and world.placing.choices(world, "raul", OBJECT, object_id)[0].open
        )
        seen = world.foresee_put_down("raul", _at(world, bed), OBJECT, bed)
        self.assertEqual((seen.ok, seen.does), (True, USE))
        self.assertIn("se acostará", seen.text)
        raul.needs.tiredness = 70
        result = world.apply_command(PutDownCommand("raul", _at(world, bed), OBJECT, bed))
        self.assertEqual(result.does, USE)
        self.assertEqual(raul.tile, _at(world, bed), "in it already")
        self.assertEqual((raul.activity.action, raul.activity.target_id), ("sleep", bed))
        self.assertTrue(raul.activity.ordered)
        self.assertEqual(raul.doing, Order("use:thing", bed))
        world.step(2)
        self.assertEqual(raul.current_action, "sleep")
        self.assertFalse(world.is_aware(raul))

    def test_a_bed_that_is_somebody_elses_only_puts_them_down(self) -> None:
        world = _settled()
        raul = world.residents["raul"]
        shut = next(
            (
                object_id
                for object_id, placed in world.interactables.items()
                if placed.kind == "bed" and not world.placing.choices(world, "raul", OBJECT, object_id)[0].open
            ),
            None,
        )
        if shut is None:
            self.skipTest("every bed is his to use in this settlement")
        seen = world.foresee_put_down("raul", _at(world, shut), OBJECT, shut)
        self.assertEqual((seen.ok, seen.does), (True, STAY))
        result = world.apply_command(PutDownCommand("raul", _at(world, shut), OBJECT, shut))
        self.assertEqual((result.ok, result.does), (True, STAY))
        self.assertTrue(_beside(raul.tile, _at(world, shut), 2))
        self.assertIsNone(raul.activity)

    def test_on_the_pantry_they_eat(self) -> None:
        world = _settled()
        raul = world.residents["raul"]
        raul.needs.hunger = 60
        result = world.apply_command(PutDownCommand("raul", _at(world, "pantry_1"), OBJECT, "pantry_1"))
        self.assertEqual(result.does, USE)
        self.assertTrue(_beside(raul.tile, _at(world, "pantry_1"), 2))
        world.step(2)
        self.assertEqual(raul.current_action, "eat")

    def test_on_their_own_post_in_hours_they_work(self) -> None:
        world = _settled()
        world.step(60)
        raul = world.residents["raul"]
        seen = world.foresee_put_down("raul", _at(world, raul.post_id), OBJECT, raul.post_id)
        self.assertEqual(seen.does, WORK)
        result = world.apply_command(PutDownCommand("raul", _at(world, raul.post_id), OBJECT, raul.post_id))
        self.assertEqual(result.does, WORK)
        self.assertEqual(raul.activity.action, WORK_ACTION)
        self.assertEqual(raul.activity.path, [], "at it, not on the way to it")
        self.assertTrue(_beside(raul.tile, _at(world, raul.post_id), 2))

    def test_on_their_own_post_out_of_hours_they_are_only_put_down(self) -> None:
        world = _settled()
        raul = world.residents["raul"]
        job = world.registries.jobs[raul.job_id]
        _run(world, 60 * 24, until=lambda: world.work.shift_minutes_left(world, raul, job) <= 0)
        self.assertLessEqual(world.work.shift_minutes_left(world, raul, job), 0)
        seen = world.foresee_put_down("raul", _at(world, raul.post_id), OBJECT, raul.post_id)
        self.assertEqual(seen.does, STAY)
        self.assertIn("hora", seen.text)

    def test_a_free_post_of_another_job_is_theirs_from_then_on(self) -> None:
        world = _settled()
        world.step(60)
        paco = world.residents["paco"]
        self.assertEqual(paco.job_id, "mechanic")
        free = next(
            object_id
            for object_id, placed in world.interactables.items()
            if placed.kind == "crop_bed" and all(each.post_id != object_id for each in world.residents.values())
        )
        seen = world.foresee_put_down("paco", _at(world, free), OBJECT, free)
        self.assertEqual(seen.does, POST)
        result = world.apply_command(PutDownCommand("paco", _at(world, free), OBJECT, free))
        self.assertEqual(result.does, POST)
        self.assertEqual((paco.job_id, paco.post_id), ("farmer", free), "that very bed, and not just any")
        self.assertIn("job_changed", _types(world))
        self.assertNotIn("post_lost", _types(world))

    def test_a_post_that_was_somebody_elses_is_taken_from_them(self) -> None:
        world = _settled()
        world.step(60)
        paco, raul = world.residents["paco"], world.residents["raul"]
        post = raul.post_id
        seen = world.foresee_put_down("paco", _at(world, post), OBJECT, post)
        self.assertEqual(seen.does, POST)
        self.assertIn("Raúl lo perderá", seen.text)
        result = world.apply_command(PutDownCommand("paco", _at(world, post), OBJECT, post))
        self.assertEqual(result.does, POST)
        self.assertEqual((paco.job_id, paco.post_id), ("farmer", post))
        self.assertEqual((raul.job_id, raul.post_id), (None, None))
        self.assertTrue(raul.seeks_work, "left without, he is somebody looking for a job")
        self.assertIn("post_lost", _types(world))

    def test_what_is_a_post_and_is_used_too_waits_to_be_told_which(self) -> None:
        world = _settled()
        world.step(60 * 11)
        raul, lucia = world.residents["raul"], world.residents["lucia"]
        raul.needs.thirst = 50
        tank = _at(world, "water_tank")
        seen = world.foresee_put_down("raul", tank, OBJECT, "water_tank")
        self.assertEqual(seen.does, CHOOSE)
        self.assertEqual({each.does for each in seen.choices}, {USE, POST})
        result = world.apply_command(PutDownCommand("raul", tank, OBJECT, "water_tank"))
        self.assertEqual(result.does, CHOOSE)
        self.assertEqual({each.does for each in result.choices}, {USE, POST})
        self.assertEqual(raul.activity.action, HEED_ACTION, "he stands there until told which")
        self.assertEqual(raul.job_id, "farmer", "nothing is his that was not said")
        told = world.apply_command(PutDownCommand("raul", raul.tile, OBJECT, "water_tank", does=USE))
        self.assertEqual(told.does, USE)
        self.assertEqual(raul.activity.target_id, "water_tank")
        self.assertEqual(raul.job_id, "farmer")
        self.assertEqual(lucia.job_id, "bartender")

    def test_what_can_be_taken_apart_they_take_apart(self) -> None:
        world = _settled()
        world.step(60)
        raul = world.residents["raul"]
        wreck = _at(world, "wreck_corner")
        seen = world.foresee_put_down("raul", wreck, OBJECT, "wreck_corner")
        self.assertEqual(seen.does, TAKE_APART)
        result = world.apply_command(PutDownCommand("raul", wreck, OBJECT, "wreck_corner"))
        self.assertEqual(result.does, TAKE_APART)
        self.assertEqual(world.salvage["wreck_corner"].resident_id, "raul")
        self.assertEqual((raul.activity.action, raul.activity.target_id), (SALVAGE_ACTION, "wreck_corner"))
        self.assertEqual(raul.doing, Order("task:salvage", "wreck_corner"))

    def test_by_a_thing_there_is_nothing_else_to_do_with_they_pass_the_time(self) -> None:
        world = _settled()
        raul = world.residents["raul"]
        seen = world.foresee_put_down("raul", _at(world, "lamp_shop"), OBJECT, "lamp_shop")
        self.assertEqual(seen.does, PASTIME)
        result = world.apply_command(PutDownCommand("raul", _at(world, "lamp_shop"), OBJECT, "lamp_shop"))
        self.assertEqual(result.does, PASTIME)
        self.assertEqual(raul.activity.action, world.registries.placing.otherwise)
        self.assertTrue(_beside(raul.tile, _at(world, "lamp_shop"), 2))

    def test_everything_on_the_map_comes_to_something(self) -> None:
        world = _settled()
        world.step(60)
        for object_id in world.interactables:
            found = world.placing.choices(world, "raul", OBJECT, object_id)
            self.assertTrue(found, f"nothing comes of being put down on {object_id}")


class SiteAndRoomTests(unittest.TestCase):
    def test_on_a_site_it_is_theirs_to_see_to(self) -> None:
        world = _settled()
        world.step(60)
        proposed = world.apply_command(ProposeObjectCommand("lamp", (20, 18), "marta"))
        if not proposed.ok or not world.sites:
            self.skipTest("nobody would put it up")
        site = next(iter(world.sites.values()))
        seen = world.foresee_put_down("raul", (site.x, site.y), SITE, site.site_id)
        self.assertEqual(seen.does, BUILD)
        result = world.apply_command(PutDownCommand("raul", (site.x, site.y), SITE, site.site_id))
        self.assertEqual(result.does, BUILD)
        self.assertEqual(site.in_charge, "raul")
        again = world.foresee_put_down("raul", (site.x, site.y), SITE, site.site_id)
        self.assertEqual(again.does, STAY)

    def test_on_a_building_they_are_inside_and_no_more(self) -> None:
        world = _settled()
        raul = world.residents["raul"]
        room = world.rooms["storehouse"]
        centre = (room.x + room.width // 2, room.y + room.height // 2)
        seen = world.foresee_put_down("raul", centre, ROOM, "storehouse")
        self.assertEqual(seen.does, ENTER)
        owners = list(world.housing.owners(world, "storehouse"))
        result = world.apply_command(PutDownCommand("raul", centre, ROOM, "storehouse"))
        self.assertEqual(result.does, ENTER)
        self.assertTrue(room.contains(raul.tile))
        self.assertEqual(world.housing.owners(world, "storehouse"), owners, "it is nobody's for his being in it")

    def test_a_locked_house_that_is_not_theirs_leaves_them_outside(self) -> None:
        world = _settled()
        raul = world.residents["raul"]
        room = world.rooms["south_house"]
        self.assertTrue(world.give_house("south_house", ["marta"]).ok)
        self.assertTrue(world.lock_house("south_house", True).ok)
        centre = (room.x + room.width // 2, room.y + room.height // 2)
        seen = world.foresee_put_down("raul", centre, ROOM, "south_house")
        self.assertEqual(seen.does, STAY)
        self.assertIn("llave", seen.text)
        result = world.apply_command(PutDownCommand("raul", centre, ROOM, "south_house"))
        self.assertTrue(result.ok)
        self.assertFalse(room.contains(raul.tile))
        own = world.apply_command(PutDownCommand("marta", centre, ROOM, "south_house"))
        self.assertEqual(own.does, ENTER)
        self.assertTrue(room.contains(world.residents["marta"].tile))


class WithSomebodyTests(unittest.TestCase):
    def test_beside_somebody_they_stand_until_told_what_the_two_do(self) -> None:
        world = _settled()
        world.step(60)
        raul, marta = world.residents["raul"], world.residents["marta"]
        seen = world.foresee_put_down("raul", marta.tile, RESIDENT, "marta")
        self.assertEqual(seen.does, WITH)
        result = world.apply_command(PutDownCommand("raul", marta.tile, RESIDENT, "marta"))
        self.assertEqual((result.does, result.detail), (WITH, "marta"))
        self.assertTrue(_beside(raul.tile, marta.tile))
        self.assertEqual(raul.activity.action, HEED_ACTION)
        told = world.apply_command(AffectCommand("raul", "with:talk", "marta"))
        self.assertTrue(told.ok)
        self.assertEqual(raul.activity.partner_id, "marta")

    def test_somebody_asleep_only_has_them_put_down_beside(self) -> None:
        world = _settled()
        raul, marta = world.residents["raul"], world.residents["marta"]
        bed = next(
            object_id
            for object_id, placed in world.interactables.items()
            if placed.kind == "bed" and world.placing.choices(world, "marta", OBJECT, object_id)[0].open
        )
        marta.needs.tiredness = 80
        world.apply_command(PutDownCommand("marta", _at(world, bed), OBJECT, bed))
        world.step(3)
        self.assertFalse(world.is_aware(marta))
        seen = world.foresee_put_down("raul", marta.tile, RESIDENT, "marta")
        self.assertEqual(seen.does, STAY)
        self.assertIn("duerme", seen.text)
        result = world.apply_command(PutDownCommand("raul", marta.tile, RESIDENT, "marta"))
        self.assertEqual(result.does, STAY)
        self.assertIsNone(raul.activity)

    def test_the_same_drops_on_the_same_seed_come_out_the_same(self) -> None:
        logs = []
        for _ in range(2):
            world = _settled(seed=11)
            world.step(90)
            world.apply_command(PutDownCommand("raul", _at(world, "pantry_1"), OBJECT, "pantry_1"))
            world.apply_command(PutDownCommand("paco", _at(world, "wreck_yard"), OBJECT, "wreck_yard"))
            world.apply_command(PutDownCommand("ines", (30, 14)))
            world.step(240)
            logs.append(list(world.event_log))
        self.assertEqual(logs[0], logs[1])


class ChildTests(unittest.TestCase):
    """A child still in its blanket is put in the arms of somebody (S51)."""

    def test_handed_to_somebody_they_see_to_it_whoever_they_are_to_it(self) -> None:
        world = _settled()
        bundle = _born(world)
        result = world.apply_command(HandChildCommand(bundle.child_id, "raul"))
        self.assertTrue(result.ok)
        self.assertEqual((bundle.minded_by, bundle.carried_by, bundle.place), ("raul", "raul", CARRIED))
        self.assertIn("child_handed", _types(world))
        _run(world, 120)
        self.assertEqual(bundle.carried_by, "raul")
        self.assertEqual(bundle.tile, world.residents["raul"].tile)
        self.assertNotIn("raul", world.family.kin.parents_of(world, bundle.child_id), "it makes him nothing to it")

    def test_with_them_gone_it_is_its_parents_again(self) -> None:
        world = _settled()
        bundle = _born(world)
        world.apply_command(HandChildCommand(bundle.child_id, "raul"))
        world.residents["raul"].expedition = _out()
        world.step(2)
        self.assertEqual(bundle.carried_by, "ines")

    def test_handed_back_to_a_parent_it_is_theirs_to_carry(self) -> None:
        world = _settled()
        bundle = _born(world)
        world.apply_command(HandChildCommand(bundle.child_id, "raul"))
        self.assertTrue(world.apply_command(HandChildCommand(bundle.child_id, "tomas")).ok)
        world.step(2)
        self.assertEqual(bundle.carried_by, "tomas")

    def test_nobody_in_no_state_to_is_handed_it(self) -> None:
        world = _settled()
        bundle = _born(world)
        world.residents["raul"].expedition = _out()
        self.assertFalse(world.apply_command(HandChildCommand(bundle.child_id, "raul")).ok)
        self.assertIsNone(bundle.minded_by)

    def test_put_down_on_a_child_lying_about_they_take_it_up(self) -> None:
        world = _settled()
        bundle = _born(world)
        for parent in ("ines", "tomas"):
            world.residents[parent].expedition = _out()
        world.step(2)
        self.assertIsNone(bundle.carried_by)
        seen = world.foresee_put_down("raul", bundle.tile, CHILD, bundle.child_id)
        self.assertEqual(seen.does, TAKE_UP)
        result = world.apply_command(PutDownCommand("raul", bundle.tile, CHILD, bundle.child_id))
        self.assertEqual(result.does, TAKE_UP)
        self.assertEqual(bundle.carried_by, "raul")

    def test_whose_arms_it_is_in_is_saved_and_a_save_from_before_has_nobodys(self) -> None:
        world = _settled()
        bundle = _born(world)
        world.apply_command(HandChildCommand(bundle.child_id, "raul"))
        manager = SaveManager()
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "save.json"
            manager.save(world, path)
            loaded = manager.load(path)
        self.assertEqual(loaded.bundles[bundle.child_id].minded_by, "raul")
        data = manager.to_data(world)
        for saved in data["bundles"]:
            del saved["minded_by"]
        self.assertIsNone(manager.from_data(data).bundles[bundle.child_id].minded_by)


class ItemTests(unittest.TestCase):
    """A thing is moved by the hand of the player, whatever anybody makes of it (S51)."""

    def setUp(self) -> None:
        self.world = _settled()
        self.raul, self.marta = self.world.residents["raul"], self.world.residents["marta"]
        definition = _definitions(self.world)[0]
        self.item_id = definition.item_id

    def _give(self, resident, quantity: int = 1, owner: str | None = "own"):
        item = self.world.new_item(self.item_id, quantity, resident.resident_id if owner == "own" else owner)
        resident.inventory.add(item)
        return item

    def test_what_is_nobodys_is_whoevers_hands_it_is_put_in(self) -> None:
        crate = self.world.containers["crate_1"]
        item = self.world.new_item(self.item_id, 3, None)
        crate.add(item)
        said = self.world.foresee_hand_item(item.instance_id, TO_RESIDENT, "raul")
        self.assertIn("Raúl", said)
        result = self.world.apply_command(HandItemCommand(item.instance_id, "raul"))
        self.assertTrue(result.ok)
        self.assertIsNone(result.upset)
        self.assertIsNone(crate.find(item.instance_id))
        held = self.raul.inventory.find(item.instance_id)
        self.assertEqual((held.owner_id, held.quantity), ("raul", 3))
        self.assertIn("item_handed", _types(self.world))

    def test_taken_from_somebody_for_another_it_changes_hands_and_sits_ill(self) -> None:
        item = self._give(self.raul)
        self.raul.x, self.raul.y = self.marta.x + 1, self.marta.y
        said = self.world.foresee_hand_item(item.instance_id, TO_RESIDENT, "marta")
        self.assertIn("le sentará mal", said)
        before = self.raul.needs.stress
        result = self.world.apply_command(HandItemCommand(item.instance_id, "marta"))
        self.assertTrue(result.ok)
        self.assertEqual(result.upset, "raul")
        self.assertEqual(self.marta.inventory.find(item.instance_id).owner_id, "marta")
        settings = self.world.registries.handing
        self.assertGreaterEqual(self.raul.needs.stress - before, settings.stress[0])
        resentment = self.world.relationship("raul", "marta").resentment
        self.assertGreaterEqual(resentment, settings.resentment[0])
        self.assertLessEqual(resentment, settings.resentment[1])
        self.assertEqual(self.world.relationship("marta", "raul").resentment, 0.0, "one way only")
        self.assertIn("item_taken", _types(self.world))
        self.assertTrue(any("Me quitaron" in memory.text for memory in self.world.memories.of("raul")))

    def test_the_more_it_was_worth_to_them_the_worse_they_take_it(self) -> None:
        taken = []
        definitions = sorted(_definitions(self.world), key=lambda each: each.base_value)
        for definition in (definitions[0], definitions[-1]):
            world = _settled()
            raul = world.residents["raul"]
            item = world.new_item(definition.item_id, 1, "raul")
            raul.inventory.add(item)
            world.apply_command(HandItemCommand(item.instance_id, "marta"))
            taken.append(world.relationship("raul", "marta").resentment)
        self.assertGreater(taken[1], taken[0])

    def test_what_they_do_not_see_go_they_know_nothing_of(self) -> None:
        crate = self.world.containers["crate_1"]
        item = self.world.new_item(self.item_id, 1, "raul")
        crate.add(item)
        self.raul.x, self.raul.y = 2, 33
        self.assertNotIn("raul", self._watching("crate_1"))
        result = self.world.apply_command(HandItemCommand(item.instance_id, "marta"))
        self.assertTrue(result.ok)
        self.assertIsNone(result.upset)
        self.assertEqual(self.world.relationships.get(("raul", "marta")), None)

    def _watching(self, container_id: str) -> list[str]:
        from simulation.knowledge.knowledge_system import witnesses_of

        placed = self.world.interactables[container_id]
        return witnesses_of(self.world, (placed.x, placed.y))

    def test_put_away_it_is_still_whose_it_was(self) -> None:
        item = self._give(self.raul)
        result = self.world.apply_command(HandItemCommand(item.instance_id, "crate_1", TO_CONTAINER))
        self.assertTrue(result.ok)
        self.assertIsNone(result.upset)
        kept = self.world.containers["crate_1"].find(item.instance_id)
        self.assertEqual(kept.owner_id, "raul")
        self.assertIsNone(self.raul.inventory.find(item.instance_id))

    def test_only_some_of_a_stack_can_be_moved(self) -> None:
        item = self._give(self.raul, quantity=5)
        result = self.world.apply_command(HandItemCommand(item.instance_id, "crate_1", TO_CONTAINER, units=2))
        self.assertTrue(result.ok)
        self.assertNotEqual(result.item_id, item.instance_id)
        self.assertEqual(self.raul.inventory.find(item.instance_id).quantity, 3)
        self.assertEqual(self.world.containers["crate_1"].find(result.item_id).quantity, 2)

    def test_what_cannot_be_done_is_refused_and_nothing_moves(self) -> None:
        item = self._give(self.raul)
        self.assertFalse(self.world.apply_command(HandItemCommand(item.instance_id, "raul")).ok, "he has it already")
        self.assertFalse(self.world.apply_command(HandItemCommand(item.instance_id, "nobody")).ok)
        self.assertFalse(self.world.apply_command(HandItemCommand(item.instance_id, "bar_nowhere", TO_CONTAINER)).ok)
        self.assertFalse(self.world.apply_command(HandItemCommand("item_none", "marta")).ok)
        self.marta.expedition = _out()
        self.assertFalse(self.world.apply_command(HandItemCommand(item.instance_id, "marta")).ok)
        self.assertIsNotNone(self.raul.inventory.find(item.instance_id))


class HeadlessTests(unittest.TestCase):
    def test_none_of_it_needs_pygame(self) -> None:
        import subprocess
        import sys

        root = Path(__file__).resolve().parent.parent
        code = (
            "import sys\n"
            "from simulation.commands import PutDownCommand, HandItemCommand, HandChildCommand\n"
            "from simulation.world import SimulationWorld\n"
            "world = SimulationWorld.demo_world()\n"
            "world.apply_command(PutDownCommand('raul', (30, 14)))\n"
            "world.step(30)\n"
            "assert 'pygame' not in sys.modules\n"
        )
        done = subprocess.run([sys.executable, "-c", code], cwd=root, capture_output=True, text=True)
        self.assertEqual(done.returncode, 0, done.stderr)

    def test_placing_a_free_thing_still_works_alongside(self) -> None:
        world = _settled()
        self.assertIsNotNone(world.apply_command(PlaceObjectCommand("stool", (30, 14))))


if __name__ == "__main__":
    unittest.main()
