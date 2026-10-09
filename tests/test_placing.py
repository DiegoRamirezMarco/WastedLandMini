"""Picked up and put down (P27), with no screen: where somebody put down ends up, what they set
about for it, and a child's bundle that is handed to somebody or laid down."""

import subprocess
import sys
import unittest
from pathlib import Path

from save.save_manager import SaveManager
from simulation.ai.affect import TASK, USE
from simulation.ai.placing import HAND, LAY, PERSON, POST, SIT, SITE, STAND, SWAP, TAKE_APART, USE_IT, WHICH_USE
from simulation.commands import AffectCommand, ProposeObjectCommand, PutBundleCommand, PutDownCommand
from simulation.family.children import BED, CARRIED, GROUND, SURFACE, Bundle
from simulation.health.injury import Injury
from simulation.justice.justice_system import PRISON
from simulation.justice.records import Sentence
from simulation.residents.activity import Order
from simulation.residents.attributes import Attributes
from simulation.residents.needs import Needs
from simulation.work.expedition import Expedition
from simulation.work.salvage import SALVAGE_ACTION
from simulation.work.work_system import WORK_ACTION
from simulation.world import SimulationWorld
from world.pathfinding import manhattan

ROOT = Path(__file__).resolve().parent.parent
USE_KIND = f"{TASK}:{USE}"


def _keep_content(world: SimulationWorld) -> None:
    for resident in world.residents.values():
        resident.needs = Needs(hunger=0, thirst=0, tiredness=0, social=0, stress=0)


def _settled(seed: int = 7, hour: int = 9) -> SimulationWorld:
    """The settlement that comes ready made, at an hour when everybody works, with everyone
    content and nothing between any two of them."""
    world = SimulationWorld.demo_world(seed=seed)
    world.relationships.clear()
    world.clock.hour, world.clock.minute = hour, 0
    for resident in world.residents.values():
        resident.attributes = Attributes()
    _keep_content(world)
    return world


def _run(world: SimulationWorld, minutes: int, until=None) -> bool:
    for _ in range(minutes):
        world.step(1)
        _keep_content(world)
        if until is not None and until():
            return True
    return False


def _open_tile(world: SimulationWorld, near: tuple[int, int] = (22, 16)) -> tuple[int, int]:
    """A tile out in the open that nobody is on or making for, and nothing stands on."""
    reach = world.urbanism.within_reach(world)
    taken = {resident.destination for resident in world.residents.values()}
    covered = {
        tile for placed in world.interactables.values() for tile in placed.footprint(world.definition_of(placed))
    }
    free = [tile for tile in reach if tile not in taken and tile not in covered and world.room_at(tile) is None]
    return min(free, key=lambda tile: (manhattan(tile, near), tile))


def _events(world: SimulationWorld, event_type: str) -> list:
    return [event for event in world.history if event.event_type == event_type]


def _heard(world: SimulationWorld) -> list:
    """Every time somebody was put down, of what has been given out and nobody has taken yet."""
    return [event for event in world.events.drain() if event.event_type == "resident_placed"]


def _born(world: SimulationWorld, mother_id: str = "ines", father_id: str | None = "tomas") -> Bundle:
    mother = world.residents[mother_id]
    mother.expecting_with = father_id
    return world.children.give_birth(world, mother)


class GroundTests(unittest.TestCase):
    def setUp(self) -> None:
        self.world = _settled()
        self.ines = self.world.residents["ines"]

    def test_put_down_on_bare_ground_they_are_there_at_once(self) -> None:
        self.world.step(30)
        spot = _open_tile(self.world)
        self.assertGreater(manhattan(self.ines.tile, spot), 10, "it is a long way off")
        found = self.world.placements("ines", tile=spot)
        self.assertEqual([(each.kind, each.tile) for each in found], [(STAND, spot)])
        result = self.world.apply_command(PutDownCommand("ines", tile=spot))
        self.assertTrue(result.ok)
        self.assertEqual((result.kind, result.tile, self.ines.tile), (STAND, spot, spot))
        self.assertIsNone(self.ines.activity, "whatever they were at, they have left it")
        heard = _heard(self.world)
        self.assertEqual(len(heard), 1)
        self.assertEqual((heard[0].participants, heard[0].data["to"]), (["ines"], list(spot)))
        self.assertEqual(heard[0].data["kind"], STAND)
        self.assertEqual(_events(self.world, "resident_placed"), [], "too quiet a thing to be remembered")

    def test_they_go_on_with_their_day_from_where_they_were_left(self) -> None:
        self.world.step(30)
        spot = _open_tile(self.world)
        self.world.apply_command(PutDownCommand("ines", tile=spot))
        self.assertTrue(
            _run(self.world, 4 * 60, lambda: self.world.work.on_duty(self.world, self.ines)),
            "left in the open in the middle of a shift, they never went back to their post",
        )

    def test_what_they_had_been_told_is_still_theirs_to_do(self) -> None:
        self.world.step(30)
        self.assertTrue(self.world.apply_command(AffectCommand("ines", "leisure:sit")).ok)
        self.assertTrue(self.world.apply_command(AffectCommand("ines", "task:to_post")).ok)
        self.assertEqual((self.ines.doing, self.ines.orders), (Order("leisure:sit"), [Order("task:to_post")]))
        self.world.apply_command(PutDownCommand("ines", tile=_open_tile(self.world)))
        self.assertEqual(self.ines.orders, [Order("leisure:sit"), Order("task:to_post")])
        self.world.step(1)
        self.assertEqual(self.ines.doing, Order("leisure:sit"), "taken up again where they were left")

    def test_nobody_is_put_where_nobody_could_walk_to(self) -> None:
        before = self.ines.tile
        terrain = self.world.registries.terrain
        wall = next(
            (x, y)
            for y, row in enumerate(self.world.tile_map.tiles)
            for x, terrain_id in enumerate(row)
            if not terrain[terrain_id].walkable
        )
        for tile in (wall, (-3, 2), (self.world.tile_map.width + 4, 1)):
            with self.subTest(tile=tile):
                found = self.world.placements("ines", tile=tile)
                self.assertEqual([(each.kind, each.ok) for each in found], [(STAND, False)])
                self.assertFalse(self.world.apply_command(PutDownCommand("ines", tile=tile)).ok)
                self.assertEqual(self.ines.tile, before)
        self.assertEqual(_heard(self.world), [])

    def test_nobody_is_put_on_top_of_somebody_else(self) -> None:
        raul = self.world.residents["raul"]
        found = self.world.placements("ines", tile=raul.tile)
        self.assertEqual([(each.kind, each.target_id) for each in found], [(PERSON, "raul")])
        result = self.world.apply_command(PutDownCommand("ines", tile=raul.tile))
        self.assertTrue(result.ok)
        self.assertNotEqual(self.ines.tile, raul.tile)
        self.assertLessEqual(max(abs(self.ines.x - raul.x), abs(self.ines.y - raul.y)), 1, "beside them")

    def test_working_out_what_a_drop_would_do_changes_nothing(self) -> None:
        self.world.step(30)
        manager = SaveManager()
        before = manager.to_data(self.world)
        for object_id in self.world.interactables:
            self.world.placements("ines", object_id=object_id)
        self.world.placements("ines", other_id="raul")
        self.world.placements("ines", tile=_open_tile(self.world))
        self.assertEqual(manager.to_data(self.world), before, "nor a throw of the dice")

    def test_whoever_cannot_be_told_anything_cannot_be_taken_up(self) -> None:
        spot = _open_tile(self.world)
        self.ines.expedition = Expedition(self.world.clock.total_minutes + 600, 0, 0.0)
        self.assertEqual(self.world.placements("ines", tile=spot), [])
        result = self.world.apply_command(PutDownCommand("ines", tile=spot))
        self.assertFalse(result.ok)
        self.assertIn("fuera", result.message)
        self.assertFalse(self.world.apply_command(PutDownCommand("nadie", tile=spot)).ok)

    def test_whoever_serves_a_sentence_stays_where_they_serve_it(self) -> None:
        self.world.courts.sentences.append(Sentence("raul", PRISON, "t1", self.world.clock.total_minutes + 600))
        self.assertTrue(self.world.justice.confined(self.world, "raul"))
        before = self.world.residents["raul"].tile
        result = self.world.apply_command(PutDownCommand("raul", tile=_open_tile(self.world)))
        self.assertFalse(result.ok)
        self.assertIn("condena", result.message)
        self.assertEqual(self.world.residents["raul"].tile, before)

    def test_putting_somebody_down_needs_no_pygame(self) -> None:
        check = (
            "import sys; import simulation.ai.placing; from simulation.world import SimulationWorld; "
            "from simulation.commands import PutDownCommand; world = SimulationWorld.demo_world(); world.step(60); "
            "assert world.apply_command(PutDownCommand('ines', object_id='bed_1')).ok; world.step(60); "
            "sys.exit(1 if 'pygame' in sys.modules else 0)"
        )
        done = subprocess.run([sys.executable, "-c", check], cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(done.returncode, 0, done.stderr)


class PostTests(unittest.TestCase):
    def setUp(self) -> None:
        self.world = _settled()
        self.world.step(30)
        self.ines, self.paco = self.world.residents["ines"], self.world.residents["paco"]

    def test_put_down_on_a_free_post_it_is_theirs_and_they_set_to_it(self) -> None:
        found = self.world.placements("paco", object_id="crop_2")
        self.assertEqual([each.kind for each in found], [POST, STAND])
        self.assertEqual((found[0].job_id, found[0].at_once), ("farmer", True))
        self.assertEqual(found[0].expected, self.world.work.expected(self.world, self.paco, self.world.registries.jobs["farmer"]))
        result = self.world.apply_command(PutDownCommand("paco", object_id="crop_2"))
        self.assertTrue(result.ok)
        self.assertEqual((self.paco.job_id, self.paco.post_id), ("farmer", "crop_2"))
        self.assertEqual(self.paco.tile, found[0].tile)
        self.assertEqual((self.paco.activity.action, self.paco.activity.path), (WORK_ACTION, []), "there already")
        self.assertTrue(self.paco.activity.ordered)
        self.world.step(1)
        self.assertTrue(self.world.work.on_duty(self.world, self.paco))
        self.assertTrue(any("Paco cambia de puesto: de Taller a Huerto" in line for line in self.world.event_log))

    def test_out_of_hours_the_post_is_theirs_and_they_are_left_to_their_evening(self) -> None:
        world = _settled(hour=22)
        world.step(5)
        paco = world.residents["paco"]
        found = world.placements("paco", object_id="crop_2")
        self.assertEqual((found[0].kind, found[0].at_once), (POST, False))
        self.assertTrue(world.apply_command(PutDownCommand("paco", object_id="crop_2")).ok)
        self.assertEqual((paco.job_id, paco.post_id), ("farmer", "crop_2"))
        self.assertIsNone(paco.activity, "nobody is told to work out of hours")

    def test_put_down_on_their_own_post_they_go_back_to_it(self) -> None:
        self.world.apply_command(PutDownCommand("ines", tile=_open_tile(self.world)))
        found = self.world.placements("ines", object_id="crop_5")
        self.assertEqual((found[0].kind, found[0].text), (POST, "A su puesto: Huerto"))
        self.world.apply_command(PutDownCommand("ines", object_id="crop_5"))
        self.world.step(1)
        self.assertTrue(self.world.work.on_duty(self.world, self.ines))
        self.assertEqual(_events(self.world, "job_changed"), [], "it was theirs already")

    def test_another_post_of_the_job_they_have_is_only_another_post(self) -> None:
        self.world.apply_command(PutDownCommand("ines", object_id="crop_2"))
        self.assertEqual((self.ines.job_id, self.ines.post_id), ("farmer", "crop_2"))
        self.assertEqual(_events(self.world, "job_changed"), [])
        self.world.step(1)
        self.assertTrue(self.world.work.on_duty(self.world, self.ines))

    def test_put_down_on_a_post_somebody_has_the_two_change_posts(self) -> None:
        vera = self.world.residents["vera"]
        found = self.world.placements("ines", object_id="medicine_cabinet")
        self.assertEqual((found[0].kind, found[0].at_once), (SWAP, True))
        self.assertIn("Vera", found[0].text)
        self.assertTrue(self.world.apply_command(PutDownCommand("ines", object_id="medicine_cabinet")).ok)
        self.assertEqual((self.ines.job_id, self.ines.post_id), ("medic", "medicine_cabinet"))
        self.assertEqual((vera.job_id, vera.post_id), ("farmer", "crop_5"))
        self.assertEqual({event.participants[0] for event in _events(self.world, "job_changed")}, {"ines", "vera"})
        self.world.step(1)
        self.assertTrue(self.world.work.on_duty(self.world, self.ines))
        self.assertTrue(
            _run(self.world, 3 * 60, lambda: self.world.work.on_duty(self.world, vera)),
            "whoever was moved out never took up the post they were left",
        )
        self.assertEqual(vera.activity.target_id, "crop_5")

    def test_whoever_changes_with_somebody_who_had_no_post_is_left_with_none(self) -> None:
        self.ines.job_id = self.ines.post_id = None
        self.ines.activity = None
        self.world.apply_command(PutDownCommand("ines", object_id="workbench"))
        self.assertEqual((self.ines.job_id, self.ines.post_id), ("mechanic", "workbench"))
        self.assertEqual((self.paco.job_id, self.paco.post_id), (None, None))
        self.assertTrue(any("Paco deja su puesto: Taller" in line for line in self.world.event_log))

    def test_a_push_does_not_go_with_them_to_the_post_they_are_given(self) -> None:
        self.assertTrue(_run(self.world, 120, lambda: self.world.work.on_duty(self.world, self.ines)))
        self.assertTrue(self.world.apply_command(AffectCommand("ines", "task:push")).ok)
        self.assertTrue(self.world.rush.pushed(self.world, self.ines))
        self.world.apply_command(PutDownCommand("ines", object_id="workbench"))
        self.assertFalse(self.world.rush.pushed(self.world, self.ines))

    def test_the_post_of_somebody_who_is_out_is_not_changed_behind_their_back(self) -> None:
        self.paco.expedition = Expedition(self.world.clock.total_minutes + 600, 0, 0.0)
        found = self.world.placements("ines", object_id="workbench")
        self.assertNotIn(SWAP, [each.kind for each in found])
        self.world.apply_command(PutDownCommand("ines", object_id="workbench"))
        self.assertEqual((self.ines.job_id, self.paco.job_id), ("farmer", "mechanic"))

    def test_a_post_that_is_also_used_gives_the_post_first_and_the_use_if_asked(self) -> None:
        found = self.world.placements("ines", object_id="cooking_pot")
        self.assertEqual([each.kind for each in found], [SWAP, USE_IT, STAND])
        self.assertEqual(found[1].text, "Comer")
        self.assertTrue(self.world.apply_command(PutDownCommand("ines", object_id="cooking_pot", do=USE_IT)).ok)
        self.assertEqual(self.ines.job_id, "farmer", "they were only to eat")
        self.assertEqual(self.ines.doing, Order(USE_KIND, "cooking_pot"))
        self.world.step(1)
        self.assertEqual(self.ines.current_action, "eat")
        self.assertFalse(self.world.apply_command(PutDownCommand("ines", object_id="cooking_pot", do=SIT)).ok)


class ThingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.world = _settled()
        self.world.step(30)
        self.ines = self.world.residents["ines"]

    def test_put_down_on_a_bed_they_lie_down_and_sleep(self) -> None:
        self.ines.needs.tiredness = 60.0
        found = self.world.placements("ines", object_id="bed_1")
        self.assertEqual([(each.kind, each.text) for each in found], [(USE_IT, "Dormir"), (STAND, "Dejar junto a una cama")])
        bed = self.world.interactables["bed_1"]
        result = self.world.apply_command(PutDownCommand("ines", object_id="bed_1"))
        self.assertEqual((result.ok, result.kind, self.ines.tile), (True, USE_IT, (bed.x, bed.y)))
        self.world.step(1)
        self.ines.needs.tiredness = 60.0
        self.assertEqual(self.ines.current_action, "sleep")
        self.assertFalse(self.world.is_aware(self.ines))
        self.assertTrue(any("order_given | A Inés se le dice: que use una cama" in line for line in self.world.event_log))

    def test_a_bed_that_is_somebody_elses_only_has_them_left_beside_it(self) -> None:
        found = self.world.placements("ines", object_id="bed_4")
        self.assertEqual([each.kind for each in found], [STAND])
        result = self.world.apply_command(PutDownCommand("ines", object_id="bed_4"))
        self.assertTrue(result.ok)
        bed = self.world.interactables["bed_4"]
        self.assertEqual(manhattan(self.ines.tile, (bed.x, bed.y)), 1)
        self.assertIsNone(self.ines.doing)

    def test_what_they_are_put_down_on_is_done_before_what_waited(self) -> None:
        self.assertTrue(self.world.apply_command(AffectCommand("ines", "leisure:sit")).ok)
        self.assertTrue(self.world.apply_command(AffectCommand("ines", "task:to_post")).ok)
        self.ines.needs.tiredness = 60.0
        self.world.apply_command(PutDownCommand("ines", object_id="bed_1"))
        self.assertEqual(self.ines.doing, Order(USE_KIND, "bed_1"))
        self.assertEqual(self.ines.orders, [Order("leisure:sit"), Order("task:to_post")])
        said = [each.said for each in self.world.orders_of("ines")]
        self.assertEqual(said[0], "Que use una cama")

    def test_stopped_on_the_way_they_go_back_to_the_very_thing(self) -> None:
        self.ines.needs.tiredness = 60.0
        self.world.apply_command(PutDownCommand("ines", object_id="bed_7"))
        self.world.apply_command(PutDownCommand("ines", tile=_open_tile(self.world)))
        self.assertEqual(self.ines.orders, [Order(USE_KIND, "bed_7")])
        self.world.step(1)
        self.ines.needs.tiredness = 60.0
        self.assertEqual((self.ines.doing, self.ines.activity.target_id), (Order(USE_KIND, "bed_7"), "bed_7"))
        self.assertTrue(self.ines.activity.path, "it is a walk away now")

    def test_put_down_on_a_seat_they_sit(self) -> None:
        stool = self.world.interactables["stool_1"]
        found = self.world.placements("ines", object_id="stool_1")
        self.assertEqual((found[0].kind, found[0].tile), (SIT, (stool.x, stool.y)))
        self.world.apply_command(PutDownCommand("ines", object_id="stool_1"))
        self.assertEqual(self.ines.tile, (stool.x, stool.y))
        self.assertEqual((self.ines.activity.action, self.ines.doing), ("sit", Order("leisure:sit")))

    def test_put_down_on_what_is_lying_about_they_take_it_apart(self) -> None:
        found = self.world.placements("ines", object_id="junk_1")
        self.assertEqual(found[0].kind, TAKE_APART)
        self.world.apply_command(PutDownCommand("ines", object_id="junk_1"))
        self.assertEqual(self.world.salvage["junk_1"].resident_id, "ines")
        self.assertEqual((self.ines.activity.action, self.ines.activity.path), (SALVAGE_ACTION, []))
        self.assertTrue(_run(self.world, 6 * 60, lambda: "junk_1" not in self.world.interactables), "it is still there")

    def test_put_down_on_a_site_they_take_charge_of_it(self) -> None:
        spot = next(
            (x, y)
            for y in range(1, self.world.tile_map.height - 2)
            for x in range(1, self.world.tile_map.width - 2)
            if self.world.urbanism.object_error(self.world, "bed", (x, y)) is None
        )
        site_id = self.world.apply_command(ProposeObjectCommand("bed", spot, "marta")).entity_id
        found = self.world.placements("ines", site_id=site_id)
        self.assertEqual([each.kind for each in found], [SITE, STAND])
        self.assertEqual(self.world.placements("ines", tile=spot)[0].kind, SITE, "by the tile it lies on, too")
        self.assertTrue(self.world.apply_command(PutDownCommand("ines", site_id=site_id)).ok)
        self.assertEqual(self.world.sites[site_id].in_charge, "ines")
        site = self.world.sites[site_id]
        self.assertEqual(min(manhattan(self.ines.tile, tile) for tile in site.tiles), 1)
        self.assertEqual([each.kind for each in self.world.placements("ines", site_id=site_id)], [STAND])

    def test_a_thing_with_nothing_to_it_only_has_them_left_beside_it(self) -> None:
        # A barrel: a table is something to sit at since things offer more than one thing (S60).
        found = self.world.placements("ines", object_id="barrel_cantina")
        self.assertEqual([(each.kind, each.text) for each in found], [(STAND, "Dejar junto a un bidón")])
        self.world.apply_command(PutDownCommand("ines", object_id="barrel_cantina"))
        table = self.world.interactables["barrel_cantina"]
        footprint = table.footprint(self.world.definition_of(table))
        self.assertEqual(min(manhattan(self.ines.tile, tile) for tile in footprint), 1)

    def test_of_two_places_beside_a_thing_it_is_the_one_nearer_the_hand(self) -> None:
        table = self.world.interactables["table"]
        footprint = table.footprint(self.world.definition_of(table))
        left = min(x for x, _y in footprint)
        right = max(x for x, _y in footprint)
        west = self.world.placements("ines", object_id="table", tile=(left - 3, table.y))[0].tile
        east = self.world.placements("ines", object_id="table", tile=(right + 3, table.y))[0].tile
        self.assertLess(west[0], left)
        self.assertGreater(east[0], right)

    def test_put_down_on_somebody_they_are_beside_them_and_it_says_who(self) -> None:
        raul = self.world.residents["raul"]
        found = self.world.placements("ines", other_id="raul")
        self.assertEqual([(each.kind, each.opens) for each in found], [(PERSON, True)])
        result = self.world.apply_command(PutDownCommand("ines", other_id="raul"))
        self.assertEqual((result.ok, result.kind, result.other_id), (True, PERSON, "raul"))
        self.assertLessEqual(max(abs(self.ines.x - raul.x), abs(self.ines.y - raul.y)), 1)
        self.assertTrue(self.world.affect_with("ines", "raul"), "there is something the two can be told to do")

    def test_put_down_on_somebody_asleep_they_are_only_left_there(self) -> None:
        raul = self.world.residents["raul"]
        raul.needs.tiredness = 80.0
        self.world.apply_command(PutDownCommand("raul", object_id="bed_2"))
        self.world.step(1)
        raul.needs.tiredness = 80.0
        self.assertFalse(self.world.is_aware(raul))
        found = self.world.placements("ines", other_id="raul")
        self.assertEqual((found[0].kind, found[0].opens), (PERSON, False))
        result = self.world.apply_command(PutDownCommand("ines", other_id="raul"))
        self.assertEqual((result.ok, result.other_id), (True, None))


class SeveralUsesTests(unittest.TestCase):
    """A thing that offers more than one thing to do (S60), and somebody put down on it (P63)."""

    def setUp(self) -> None:
        self.world = _settled()
        self.world.step(30)
        self.ines = self.world.residents["ines"]
        self.ines.needs.tiredness = 60.0

    def test_put_down_on_a_bed_they_still_sleep_though_it_offers_more(self) -> None:
        """What a thing is mainly for is what being put down on it is for, as it was."""
        world, ines = self.world, self.ines
        bed = world.interactables["bed_1"]
        self.assertEqual(
            [label for label, _kind, _target in world.affect.things_to_do(world, ines, bed)], ["Dormir", "Echarse un rato"]
        )
        found = world.placements("ines", object_id="bed_1")
        self.assertEqual([(each.kind, each.text, each.opens) for each in found if each.kind == USE_IT], [(USE_IT, "Dormir", False)])
        result = world.apply_command(PutDownCommand("ines", object_id="bed_1"))
        self.assertEqual((result.ok, result.kind, result.thing_id), (True, USE_IT, None))
        self.assertEqual(ines.doing, Order(USE_KIND, "bed_1"))

    def test_a_table_which_is_for_nothing_in_particular_asks_what_they_do_there(self) -> None:
        world, ines = self.world, self.ines
        ines.needs.stress = 40.0
        table = next(placed for placed in world.interactables.values() if placed.kind == "table")
        self.assertIsNone(world.definition_of(table).use)
        found = world.placements("ines", object_id=table.object_id)
        asked = [each for each in found if each.kind == USE_IT]
        self.assertEqual([(each.opens, each.text) for each in asked], [(True, WHICH_USE)])
        result = world.placing.put(world, "ines", object_id=table.object_id, do=USE_IT)
        self.assertEqual((result.ok, result.thing_id), (True, table.object_id))
        self.assertNotEqual(ines.tile, (table.x, table.y), "beside it")
        self.assertLessEqual(manhattan(ines.tile, (table.x, table.y)), 2)
        self.assertIsNone(ines.doing, "nothing was set about: it is for the player to say what")
        # What is then said is an order like any other.
        _label, kind, target = world.affect.things_to_do(world, ines, table)[0]
        self.assertTrue(world.apply_command(AffectCommand("ines", kind, target)).ok)
        world.step(2)
        self.assertEqual(ines.activity.action, "sit_table")

    def test_a_thing_that_cannot_be_used_for_what_it_is_for_asks_for_what_else_it_offers(self) -> None:
        """A tank with no water in it is still somewhere to... no: washing wants water too.
        Where nothing at all can be done with a thing, they are only left beside it."""
        world, ines = self.world, self.ines
        tank = next(placed for placed in world.interactables.values() if placed.kind == "water_tank")
        world.containers[tank.object_id].items.clear()
        doable = world.affect.things_to_do(world, ines, tank)
        found = [each for each in world.placements("ines", object_id=tank.object_id) if each.kind == USE_IT]
        self.assertEqual(bool(found), bool(doable))
        self.assertTrue(all(each.opens for each in found), "what it is mainly for is not on offer")


class SavedTests(unittest.TestCase):
    def setUp(self) -> None:
        self.manager = SaveManager()

    def test_what_a_drop_set_them_about_is_saved_and_goes_on_the_same(self) -> None:
        world = _settled()
        world.step(30)
        world.residents["ines"].needs.tiredness = 60.0
        world.apply_command(PutDownCommand("ines", object_id="bed_1"))
        world.apply_command(PutDownCommand("paco", object_id="crop_2"))
        world.step(3)
        data = self.manager.to_data(world)
        loaded = self.manager.from_data(data)
        self.assertEqual(loaded.residents["ines"].doing, Order(USE_KIND, "bed_1"))
        self.assertEqual(loaded.residents["paco"].post_id, "crop_2")
        for each in (world, loaded):
            each.step(3 * 60)
        self.assertEqual(self.manager.to_data(loaded), self.manager.to_data(world))

    def test_a_bundle_handed_over_or_laid_down_is_saved(self) -> None:
        world = _settled()
        one, other = _born(world), _born(world, "marta", "raul")
        world.apply_command(PutBundleCommand(one.child_id, other_id="vera"))
        world.apply_command(PutBundleCommand(other.child_id, object_id="bed_3"))
        data = self.manager.to_data(world)
        loaded = self.manager.from_data(data)
        self.assertEqual((loaded.bundles[one.child_id].keeper, loaded.bundles[one.child_id].set_down), ("vera", False))
        self.assertEqual((loaded.bundles[other.child_id].keeper, loaded.bundles[other.child_id].set_down), (None, True))
        for each in (world, loaded):
            each.step(6 * 60)
        self.assertEqual(self.manager.to_data(loaded), self.manager.to_data(world))

    def test_in_a_save_from_before_a_bundle_is_nobodys_but_its_own_and_was_not_laid_down(self) -> None:
        world = _settled()
        bundle = _born(world)
        world.apply_command(PutBundleCommand(bundle.child_id, other_id="vera"))
        data = self.manager.to_data(world)
        for saved in data["bundles"]:
            del saved["keeper"]
            del saved["set_down"]
        data["version"] = 40
        loaded = self.manager.from_data(data)
        self.assertEqual((loaded.bundles[bundle.child_id].keeper, loaded.bundles[bundle.child_id].set_down), (None, False))
        loaded.step(5)
        self.assertEqual(loaded.bundles[bundle.child_id].carried_by, "ines", "its mother has it again")

    def test_a_keeper_who_is_no_longer_there_is_forgotten_on_loading(self) -> None:
        world = _settled()
        bundle = _born(world)
        world.apply_command(PutBundleCommand(bundle.child_id, other_id="vera"))
        data = self.manager.to_data(world)
        data["residents"] = [each for each in data["residents"] if each["id"] != "vera"]
        loaded = self.manager.from_data(data)
        self.assertIsNone(loaded.bundles[bundle.child_id].keeper)


class BundleTests(unittest.TestCase):
    def setUp(self) -> None:
        self.world = _settled()
        self.world.step(30)
        self.bundle = _born(self.world)
        self.child_id = self.bundle.child_id
        self.ines, self.vera = self.world.residents["ines"], self.world.residents["vera"]

    def test_handed_to_somebody_they_carry_it_from_then_on(self) -> None:
        found = self.world.bundle_placements(self.child_id, other_id="vera")
        self.assertEqual([(each.kind, each.ok) for each in found], [(HAND, True)])
        self.assertIn("Vera", found[0].text)
        result = self.world.apply_command(PutBundleCommand(self.child_id, other_id="vera"))
        self.assertEqual((result.ok, result.kind), (True, HAND))
        self.assertEqual((self.bundle.carried_by, self.bundle.place, self.bundle.tile), ("vera", CARRIED, self.vera.tile))
        for _ in range(90):
            self.world.step(1)
            _keep_content(self.world)
            if self.world.is_aware(self.vera):
                self.assertEqual((self.bundle.carried_by, self.bundle.tile), ("vera", self.vera.tile))
        self.assertEqual(self.bundle.health, 100.0)
        self.assertTrue(any("Vera se queda con" in line for line in self.world.event_log))

    def test_it_is_fed_by_whoever_has_it(self) -> None:
        self.world.apply_command(PutBundleCommand(self.child_id, other_id="vera"))
        self.bundle.hunger = 59.9
        self.world.step(1)
        self.assertEqual(self.bundle.hunger, 0.0)
        self.assertGreater(self.vera.needs.tiredness, self.ines.needs.tiredness)

    def test_when_whoever_has_it_cannot_its_own_see_to_it_again(self) -> None:
        self.world.apply_command(PutBundleCommand(self.child_id, other_id="vera"))
        self.vera.injuries.append(Injury("cut", 80.0))
        self.assertFalse(self.world.health.is_fit_for_work(self.vera))
        self.world.step(1)
        self.assertEqual(self.bundle.carried_by, "ines")
        self.vera.injuries.clear()
        self.world.step(1)
        self.assertEqual(self.bundle.carried_by, "vera", "and when they can again, they do")

    def test_handed_back_to_its_mother_it_is_hers(self) -> None:
        self.world.apply_command(PutBundleCommand(self.child_id, other_id="vera"))
        self.world.apply_command(PutBundleCommand(self.child_id, tile=self.ines.tile))
        self.assertEqual((self.bundle.keeper, self.bundle.carried_by), ("ines", "ines"))

    def test_nobody_who_is_in_no_state_to_is_handed_a_bundle(self) -> None:
        self.vera.injuries.append(Injury("cut", 80.0))
        found = self.world.bundle_placements(self.child_id, other_id="vera")
        self.assertEqual([(each.kind, each.ok) for each in found], [(HAND, False)])
        self.assertFalse(self.world.apply_command(PutBundleCommand(self.child_id, other_id="vera")).ok)
        self.assertEqual(self.bundle.carried_by, "ines")

    def test_laid_on_the_ground_it_stays_there_and_is_the_worse_for_it(self) -> None:
        spot = _open_tile(self.world)
        found = self.world.bundle_placements(self.child_id, tile=spot)
        self.assertEqual([(each.kind, each.tile) for each in found], [(LAY, spot)])
        result = self.world.apply_command(PutBundleCommand(self.child_id, tile=spot))
        self.assertEqual((result.ok, result.kind), (True, LAY))
        self.bundle.hunger = 59.9
        for _ in range(4 * 60):
            self.world.step(1)
            _keep_content(self.world)
            self.assertEqual((self.bundle.tile, self.bundle.place, self.bundle.carried_by), (spot, GROUND, None))
        self.assertLess(self.bundle.health, 100.0)
        self.assertLess(self.bundle.hunger, 60.0, "its own still feed it there")
        self.assertEqual(self.bundle.left, 0, "it is not as if nobody were seeing to it")
        self.assertTrue(any("se le deja en el suelo" in line for line in self.world.event_log))

    def test_before_it_comes_to_harm_whoever_sees_to_it_takes_it_up_again(self) -> None:
        spot = _open_tile(self.world)
        self.world.apply_command(PutBundleCommand(self.child_id, tile=spot))
        below = self.world.registries.family.children.taken_up_below
        self.bundle.health = below + 0.01
        self.world.step(1)
        self.assertEqual((self.bundle.set_down, self.bundle.tile), (True, spot))
        self.world.step(2)
        self.assertEqual((self.bundle.set_down, self.bundle.carried_by), (False, "ines"))
        self.assertTrue(any("Inés recoge a" in line for line in self.world.event_log))
        self.assertTrue(_run(self.world, 3 * 24 * 60, lambda: self.bundle.health >= 99.0), "and it mends")

    def test_laid_in_a_bed_it_comes_to_no_harm(self) -> None:
        bed = self.world.interactables["bed_3"]
        found = self.world.bundle_placements(self.child_id, object_id="bed_3")
        self.assertEqual([(each.kind, each.tile, each.text) for each in found], [(LAY, (bed.x, bed.y), "Acostar en la cama")])
        self.world.apply_command(PutBundleCommand(self.child_id, object_id="bed_3"))
        _run(self.world, 6 * 60)
        self.assertEqual((self.bundle.place, self.bundle.tile, self.bundle.health), (BED, (bed.x, bed.y), 100.0))

    def test_laid_under_a_roof_it_is_better_off_than_out_in_the_open(self) -> None:
        indoors = next(
            tile
            for tile in sorted(self.world.urbanism.within_reach(self.world))
            if self.world.under_roof(tile) and all(tile != each.tile for each in self.world.residents.values())
        )
        self.world.apply_command(PutBundleCommand(self.child_id, tile=indoors))
        self.assertEqual(self.bundle.place, SURFACE)
        self.assertIn("a cubierto", self.world.bundle_placements(self.child_id, tile=indoors)[0].text)

    def test_it_is_not_laid_where_nobody_could_get_to_it(self) -> None:
        found = self.world.bundle_placements(self.child_id, tile=(-2, -2))
        self.assertEqual([(each.kind, each.ok) for each in found], [(LAY, False)])
        self.assertFalse(self.world.apply_command(PutBundleCommand(self.child_id, tile=(-2, -2))).ok)
        self.assertEqual(self.bundle.carried_by, "ines")
        self.assertFalse(self.world.apply_command(PutBundleCommand("nadie", tile=(5, 5))).ok)


if __name__ == "__main__":
    unittest.main()
