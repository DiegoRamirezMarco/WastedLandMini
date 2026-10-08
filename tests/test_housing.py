import json
import unittest
from pathlib import Path

from save.save_manager import SaveManager
from simulation.commands import GiveHouseCommand, LockHouseCommand, NameBuildingCommand
from simulation.family.family_system import SLEEP_ROUGH_ACTION
from simulation.housing.housing import (
    HOUSED_EVENT,
    QUALITIES,
    TRESPASS_EVENT,
    Ornament,
    housing_settings_from_data,
)
from simulation.tutorial.tutorial import TutorialState
from simulation.work.hauling import containers_of_kind
from simulation.world import SimulationWorld
from world.interactable import Interactable

ROOT = Path(__file__).resolve().parent.parent
HOUSE = "south_house"
DORMITORY = "dormitory"
WORKSHOP = "workshop"


def _world(seed: int = 7) -> SimulationWorld:
    return SimulationWorld.demo_world(seed=seed)


def _thing(world: SimulationWorld, room_id: str, kind: str) -> Interactable:
    """Something of a kind that stands in a building."""
    room = world.rooms[room_id]
    return next(placed for placed in world.interactables.values() if placed.kind == kind and room.contains((placed.x, placed.y)))


def _bed(world: SimulationWorld, room_id: str) -> Interactable:
    return _thing(world, room_id, "bed")


def _put(world: SimulationWorld, room_id: str, kind: str, object_id: str = "put_in") -> Interactable:
    """Stand something in the first free corner of a building, without anybody having built it."""
    room = world.rooms[room_id]
    taken = {(placed.x, placed.y) for placed in world.interactables.values()}
    tile = next(
        (x, y)
        for y in range(room.y, room.y + room.height)
        for x in range(room.x, room.x + room.width)
        if (x, y) not in taken
    )
    placed = Interactable(object_id, kind, tile[0], tile[1])
    world.interactables[object_id] = placed
    return placed


def _events(world: SimulationWorld, kind: str) -> list:
    return [event for event in world.history if event.event_type == kind]


class WhoseTests(unittest.TestCase):
    def test_a_settlement_that_is_already_running_has_its_houses_given_out(self) -> None:
        world = _world()
        housing = world.housing
        housed = [owner for room_id in world.homes.owners for owner in housing.owners(world, room_id)]
        self.assertEqual(sorted(housed), sorted(world.residents), "everybody has a house, and only the one")
        for room_id in world.homes.owners:
            room = world.rooms[room_id]
            beds = sum(1 for placed in world.interactables.values() if placed.kind == "bed" and room.contains((placed.x, placed.y)))
            self.assertLessEqual(len(housing.owners(world, room_id)), beds, f"{room_id} has a bed for each of them")

    def test_a_building_that_is_nobodys_is_the_settlements(self) -> None:
        world = _world()
        self.assertEqual(world.housing.owners(world, WORKSHOP), [])
        self.assertEqual(world.housing.owners(world, "cantina"), [])
        marta = world.residents["marta"]
        self.assertTrue(world.housing.welcome(world, marta, world.rooms["cantina"]))

    def test_the_player_says_whose_a_building_is(self) -> None:
        world = _world()
        result = world.apply_command(GiveHouseCommand(WORKSHOP, ("marta", "raul")))
        self.assertTrue(result.ok)
        self.assertEqual(world.housing.owners(world, WORKSHOP), ["marta", "raul"])
        self.assertIn(WORKSHOP, world.housing.homes_of(world, "marta"))
        given = _events(world, HOUSED_EVENT)
        self.assertEqual(len(given), 1)
        self.assertEqual(given[0].data["owners"], ["marta", "raul"])

    def test_given_to_nobody_it_is_everybodys_again_and_its_door_is_open(self) -> None:
        world = _world()
        world.apply_command(LockHouseCommand(HOUSE, True))
        self.assertIn(HOUSE, world.homes.locked)
        world.apply_command(GiveHouseCommand(HOUSE, ()))
        self.assertEqual(world.housing.owners(world, HOUSE), [])
        self.assertNotIn(HOUSE, world.homes.locked)

    def test_it_cannot_be_given_to_somebody_who_does_not_live_here(self) -> None:
        world = _world()
        before = list(world.housing.owners(world, HOUSE))
        self.assertFalse(world.apply_command(GiveHouseCommand(HOUSE, ("nobody_at_all",))).ok)
        self.assertEqual(world.housing.owners(world, HOUSE), before)

    def test_only_a_building_with_a_roof_is_anybodys(self) -> None:
        world = _world()
        self.assertFalse(world.apply_command(GiveHouseCommand("commons", ("marta",))).ok)
        self.assertFalse(world.apply_command(GiveHouseCommand("no_such_room", ("marta",))).ok)

    def test_whoever_has_died_or_gone_no_longer_owns_anything(self) -> None:
        world = _world()
        world.apply_command(GiveHouseCommand(WORKSHOP, ("marta",)))
        del world.residents["marta"]
        self.assertEqual(world.housing.owners(world, WORKSHOP), [])


class LivingThereTests(unittest.TestCase):
    def test_a_bed_is_for_whoever_lives_in_the_house(self) -> None:
        world = _world()
        housing = world.housing
        owner = world.residents[housing.owners(world, HOUSE)[0]]
        other = world.residents[housing.owners(world, DORMITORY)[0]]
        bed = _bed(world, HOUSE)
        use = world.definition_of(bed).use
        self.assertTrue(housing.may_use(world, owner, bed, use))
        self.assertFalse(housing.may_use(world, other, bed, use))

    def test_a_bed_in_a_building_that_is_the_settlements_is_nobodys(self) -> None:
        world = _world()
        bed = _bed(world, WORKSHOP)
        use = world.definition_of(bed).use
        for resident in world.residents.values():
            self.assertFalse(world.housing.may_use(world, resident, bed, use))

    def test_whoever_is_with_one_of_them_lives_there_too(self) -> None:
        world = _world()
        housing = world.housing
        owner_id = housing.owners(world, HOUSE)[0]
        other = world.residents[housing.owners(world, DORMITORY)[0]]
        room = world.rooms[HOUSE]
        self.assertFalse(housing.lives_in(world, other, room))
        other.couple_with = owner_id
        self.assertTrue(housing.lives_in(world, other, room))
        bed = _bed(world, HOUSE)
        self.assertTrue(housing.may_use(world, other, bed, world.definition_of(bed).use))

    def test_a_child_lives_in_the_house_of_their_mother_or_father_and_brothers_and_sisters_do_not(self) -> None:
        world = _world()
        housing = world.housing
        room = world.rooms[HOUSE]
        owner_id = housing.owners(world, HOUSE)[0]
        child = world.residents["raul"]
        sibling = world.residents["lucia"]
        world.family.kin.record(world, sibling.resident_id, sibling.name).siblings.append(owner_id)
        self.assertFalse(housing.lives_in(world, sibling, room))
        world.family.kin.record(world, child.resident_id, child.name).parents.append(owner_id)
        self.assertTrue(housing.lives_in(world, child, room))

    def test_whoever_has_no_house_sleeps_in_the_open(self) -> None:
        world = _world()
        homeless = world.residents[world.housing.owners(world, HOUSE)[0]]
        owners = [owner for owner in world.housing.owners(world, HOUSE) if owner != homeless.resident_id]
        world.apply_command(GiveHouseCommand(HOUSE, tuple(owners)))
        homeless.needs.tiredness = 95.0
        homeless.needs.hunger = 0.0
        world.clock.hour = 23
        beds = {placed.object_id for placed in world.interactables.values() if placed.kind == "bed"}
        candidates = world.activities.routine.candidates(world, homeless)
        self.assertFalse([each for each in candidates if each.target_id in beds], "no bed is theirs to go to")
        self.assertIn(SLEEP_ROUGH_ACTION, [each.name for each in candidates])

    def test_whoever_has_a_house_goes_to_a_bed_in_it(self) -> None:
        world = _world()
        owner = world.residents[world.housing.owners(world, HOUSE)[0]]
        owner.needs.tiredness = 95.0
        owner.needs.hunger = 0.0
        world.clock.hour = 23
        room = world.rooms[HOUSE]
        candidates = world.activities.routine.candidates(world, owner)
        beds = [world.interactables[each.target_id] for each in candidates if each.target_id in world.interactables and world.interactables[each.target_id].kind == "bed"]
        self.assertTrue(beds)
        self.assertTrue(all(room.contains((bed.x, bed.y)) for bed in beds), "and to none in anybody else's")
        self.assertNotIn(SLEEP_ROUGH_ACTION, [each.name for each in candidates])

    def test_they_rest_the_better_in_a_bed_of_their_own_for_how_comfortable_the_house_is(self) -> None:
        world = _world()
        housing = world.housing
        owner = world.residents[housing.owners(world, HOUSE)[0]]
        other = world.residents[housing.owners(world, DORMITORY)[0]]
        bed = _bed(world, HOUSE)
        comfort = housing.qualities(world, world.rooms[HOUSE])["comfort"]
        self.assertGreater(comfort, 0)
        self.assertAlmostEqual(housing.rest_factor(world, owner, bed), 1.0 + world.registries.housing.rest_per_comfort * comfort)
        self.assertEqual(housing.rest_factor(world, other, bed), 1.0)


class VisitTests(unittest.TestCase):
    def _pair(self, world: SimulationWorld):
        housing = world.housing
        owner = world.residents[housing.owners(world, HOUSE)[0]]
        other = world.residents[housing.owners(world, DORMITORY)[0]]
        for owner_id in housing.owners(world, HOUSE):
            world.relationship(owner_id, other.resident_id).affection = 0.0
        return owner, other

    def test_whoever_they_think_well_of_may_come_in(self) -> None:
        world = _world()
        owner, other = self._pair(world)
        room = world.rooms[HOUSE]
        self.assertFalse(world.housing.welcome(world, other, room))
        world.relationship(owner.resident_id, other.resident_id).affection = world.registries.housing.welcome_affection
        self.assertTrue(world.housing.welcome(world, other, room))

    def test_it_is_what_the_owner_thinks_of_them_that_counts_and_not_the_other_way(self) -> None:
        world = _world()
        owner, other = self._pair(world)
        world.relationship(other.resident_id, owner.resident_id).affection = 100.0
        self.assertFalse(world.housing.welcome(world, other, world.rooms[HOUSE]))

    def test_with_the_door_locked_only_whoever_lives_there_goes_in(self) -> None:
        world = _world()
        owner, other = self._pair(world)
        room = world.rooms[HOUSE]
        world.relationship(owner.resident_id, other.resident_id).affection = 100.0
        self.assertTrue(world.apply_command(LockHouseCommand(HOUSE, True)).ok)
        self.assertTrue(world.housing.locked(world, room))
        self.assertFalse(world.housing.welcome(world, other, room))
        self.assertTrue(world.housing.welcome(world, owner, room))
        world.apply_command(LockHouseCommand(HOUSE, False))
        self.assertTrue(world.housing.welcome(world, other, room))

    def test_what_is_everybodys_cannot_be_locked(self) -> None:
        world = _world()
        self.assertFalse(world.apply_command(LockHouseCommand("cantina", True)).ok)
        self.assertEqual(world.homes.locked, [])

    def test_going_in_unasked_is_seen_and_held_against_them(self) -> None:
        world = _world()
        owner, other = self._pair(world)
        table = _put(world, HOUSE, "table")
        world.housing.used(world, other, table)
        seen = _events(world, TRESPASS_EVENT)
        self.assertEqual(len(seen), 1)
        self.assertEqual(seen[0].participants[0], other.resident_id)
        self.assertIn(owner.resident_id, seen[0].participants[1:])
        self.assertEqual(seen[0].data["room"], HOUSE)

    def test_nobody_trespasses_in_their_own_house_nor_where_they_are_welcome_nor_in_what_is_everybodys(self) -> None:
        world = _world()
        owner, other = self._pair(world)
        table = _put(world, HOUSE, "table")
        world.housing.used(world, owner, table)
        world.relationship(owner.resident_id, other.resident_id).affection = 100.0
        world.housing.used(world, other, table)
        world.housing.used(world, other, _thing(world, "cantina", "table"))
        self.assertEqual(_events(world, TRESPASS_EVENT), [])

    def test_whoever_is_not_welcome_does_not_go_in_for_what_is_there(self) -> None:
        world = _world()
        owner, other = self._pair(world)
        pantry = _put(world, HOUSE, "pantry")
        use = world.definition_of(pantry).use
        self.assertFalse(world.housing.may_use(world, other, pantry, use))
        self.assertTrue(world.housing.may_use(world, owner, pantry, use))

    def test_hunger_drives_somebody_into_a_house_that_is_not_theirs_unless_it_is_locked(self) -> None:
        world = _world()
        _, other = self._pair(world)
        pantry = _put(world, HOUSE, "pantry")
        use = world.definition_of(pantry).use
        other.needs.hunger = 40.0
        self.assertFalse(world.housing.pressed(world, other, pantry, use))
        other.needs.hunger = 95.0
        self.assertTrue(world.housing.pressed(world, other, pantry, use))
        world.apply_command(LockHouseCommand(HOUSE, True))
        self.assertFalse(world.housing.pressed(world, other, pantry, use))

    def test_nobody_is_driven_into_another_s_bed(self) -> None:
        world = _world()
        _, other = self._pair(world)
        other.needs.hunger = other.needs.thirst = 100.0
        bed = _bed(world, HOUSE)
        self.assertFalse(world.housing.pressed(world, other, bed, world.definition_of(bed).use))


class KeptTests(unittest.TestCase):
    def test_what_is_kept_in_a_house_is_for_whoever_lives_there_and_whoever_they_would_have_in(self) -> None:
        world = _world()
        housing = world.housing
        owner = world.residents[housing.owners(world, HOUSE)[0]]
        other = world.residents["raul"]
        for owner_id in housing.owners(world, HOUSE):
            world.relationship(owner_id, other.resident_id).affection = 0.0
        pantry = _put(world, HOUSE, "pantry")
        world.containers[pantry.object_id] = type(world.containers["pantry_1"])()
        world.stock(world.containers[pantry.object_id], "canned_beans", 4, None)
        owner.needs.hunger = other.needs.hunger = 70.0
        routine = world.activities.routine
        self.assertTrue(routine.relieves(world, owner, pantry, "hunger"))
        self.assertFalse(routine.relieves(world, other, pantry, "hunger"), "it is not his to go in for")
        self.assertNotIn(pantry.object_id, [each.target_id for each in routine.candidates(world, other)])
        world.relationship(owner.resident_id, other.resident_id).affection = 100.0
        self.assertTrue(routine.relieves(world, other, pantry, "hunger"))

    def test_what_is_the_settlement_s_stays_the_settlement_s_wherever_it_is_kept(self) -> None:
        world = _world()
        crate = _thing(world, HOUSE, "crate")
        before = world.fund.goods(world).get("scrap", 0)
        world.stock(world.containers[crate.object_id], "scrap", 5, None)
        self.assertEqual(world.fund.goods(world).get("scrap", 0), before + 5)
        self.assertIn(crate.object_id, [object_id for object_id, _ in containers_of_kind(world, "crate")])


class NameTests(unittest.TestCase):
    def test_a_building_is_given_a_name_and_said_what_it_is_for(self) -> None:
        world = _world()
        result = world.apply_command(NameBuildingCommand(HOUSE, "  La   casa de Marta ", "home"))
        self.assertTrue(result.ok)
        self.assertEqual(world.rooms[HOUSE].name, "La casa de Marta")
        self.assertEqual(world.housing.use_of(world, HOUSE), world.registries.housing.uses["home"])

    def test_it_has_to_be_called_something_and_be_for_something_there_is(self) -> None:
        world = _world()
        name = world.rooms[HOUSE].name
        self.assertFalse(world.apply_command(NameBuildingCommand(HOUSE, "   ")).ok)
        self.assertFalse(world.apply_command(NameBuildingCommand(HOUSE, None, "no_such_use")).ok)
        self.assertEqual(world.rooms[HOUSE].name, name)
        self.assertEqual(world.housing.use_of(world, HOUSE), "")

    def test_what_it_is_for_can_be_taken_back(self) -> None:
        world = _world()
        world.apply_command(NameBuildingCommand(HOUSE, None, "home"))
        world.apply_command(NameBuildingCommand(HOUSE, None, ""))
        self.assertEqual(world.housing.use_of(world, HOUSE), "")


class QualityTests(unittest.TestCase):
    def test_what_stands_in_a_building_makes_it_what_it_is(self) -> None:
        world = _world()
        room = world.rooms[HOUSE]
        before = world.housing.qualities(world, room)
        self.assertEqual(set(before), set(QUALITIES))
        _put(world, HOUSE, "lamp")
        after = world.housing.qualities(world, room)
        self.assertGreater(after["light"], before["light"])
        self.assertEqual(after["comfort"], before["comfort"])

    def test_a_second_of_the_same_adds_less_than_the_first(self) -> None:
        world = _world()
        room = world.rooms["cantina"]
        base = world.housing.qualities(world, room)["light"]
        _put(world, "cantina", "lamp", "first")
        one = world.housing.qualities(world, room)["light"]
        _put(world, "cantina", "lamp", "second")
        two = world.housing.qualities(world, room)["light"]
        self.assertAlmostEqual(two - one, (one - base) / 2)

    def test_what_is_put_in_it_to_be_looked_at_counts(self) -> None:
        world = _world()
        room = world.rooms[HOUSE]
        before = world.housing.qualities(world, room)["beauty"]
        world.homes.ornaments[HOUSE] = [Ornament("ornament_1", "picture", "wall", 2, 1)]
        self.assertGreater(world.housing.qualities(world, room)["beauty"], before)

    def test_nothing_goes_below_nothing_or_above_full(self) -> None:
        world = _world()
        room = world.rooms[HOUSE]
        world.homes.ornaments[HOUSE] = [Ornament(f"ornament_{n}", kind, "floor", n, 0) for n, kind in enumerate(world.registries.housing.furnishing)]
        for value in world.housing.qualities(world, room).values():
            self.assertTrue(0.0 <= value <= 100.0)

    def test_a_house_good_to_look_at_lifts_whoever_lives_in_it_once_a_day(self) -> None:
        world = _world()
        owner = world.residents[world.housing.owners(world, HOUSE)[0]]
        world.homes.ornaments[HOUSE] = [Ornament("ornament_1", "picture", "wall", 2, 1)]
        beauty = world.housing.qualities(world, world.rooms[HOUSE])["beauty"]
        self.assertGreater(beauty, 0)
        owner.mood = 0.0
        world.clock.hour, world.clock.minute = 0, 0
        world.homes.lifted_on = world.clock.day - 1
        world.housing.tick(world)
        lifted = owner.mood
        self.assertAlmostEqual(lifted, world.registries.housing.mood_per_day * beauty / 100.0)
        world.housing.tick(world)
        self.assertEqual(owner.mood, lifted, "and only the once")


class OpeningTests(unittest.TestCase):
    def test_nothing_is_anybodys_while_a_settlement_is_in_its_opening(self) -> None:
        world = _world()
        other = world.residents[world.housing.owners(world, DORMITORY)[0]]
        bed = _bed(world, HOUSE)
        world.tutorial = TutorialState(step_id="any")
        self.assertFalse(world.housing.applies(world))
        self.assertTrue(world.housing.may_use(world, other, bed, world.definition_of(bed).use))

    def test_houses_are_given_out_when_the_opening_is_over(self) -> None:
        world = _world()
        world.homes.owners.clear()
        world.homes.began = False
        world.tutorial = TutorialState(step_id="any")
        world.housing.tick(world)
        self.assertEqual(world.homes.owners, {})
        world.tutorial = TutorialState()
        world.housing.tick(world)
        self.assertTrue(world.homes.began)
        housed = {owner for owners in world.homes.owners.values() for owner in owners}
        self.assertEqual(housed, set(world.residents))

    def test_once_given_out_whoever_comes_later_has_to_be_given_one(self) -> None:
        world = _world()
        owners = world.housing.owners(world, HOUSE)
        world.apply_command(GiveHouseCommand(HOUSE, tuple(owners[1:])))
        world.housing.tick(world)
        self.assertNotIn(owners[0], world.housing.owners(world, HOUSE), "it is for the player to say")


class SaveTests(unittest.TestCase):
    def test_whose_everything_is_survives_saving(self) -> None:
        world = _world()
        world.apply_command(GiveHouseCommand(WORKSHOP, ("marta",)))
        world.apply_command(LockHouseCommand(WORKSHOP, True))
        world.apply_command(NameBuildingCommand(WORKSHOP, "El taller de Marta", "workshop"))
        world.homes.ornaments[WORKSHOP] = [Ornament("ornament_1", "picture", "wall", 3, 1)]
        world.homes.floors[WORKSHOP] = "floor_wood"
        world.homes.ornament_count = 1
        manager = SaveManager()
        data = json.loads(json.dumps(manager.to_data(world)))
        loaded = manager.from_data(data)
        self.assertEqual(loaded.homes.owners, world.homes.owners)
        self.assertEqual(loaded.homes.locked, [WORKSHOP])
        self.assertEqual(loaded.rooms[WORKSHOP].name, "El taller de Marta")
        self.assertEqual(loaded.housing.use_of(loaded, WORKSHOP), world.registries.housing.uses["workshop"])
        self.assertEqual(loaded.homes.ornaments, world.homes.ornaments)
        self.assertEqual(loaded.homes.floors, {WORKSHOP: "floor_wood"})
        self.assertEqual(loaded.homes.ornament_count, 1)
        self.assertTrue(loaded.homes.began)

    def test_a_save_from_before_houses_were_anybodys_gives_everybody_the_one_they_slept_in(self) -> None:
        world = _world()
        manager = SaveManager()
        data = json.loads(json.dumps(manager.to_data(world)))
        del data["housing"]
        data["version"] = 33
        loaded = manager.from_data(data)
        housed = sorted(owner for owners in loaded.homes.owners.values() for owner in owners)
        self.assertEqual(housed, sorted(loaded.residents))

    def test_whoever_no_longer_lives_here_is_dropped_from_a_save(self) -> None:
        world = _world()
        manager = SaveManager()
        data = json.loads(json.dumps(manager.to_data(world)))
        data["housing"]["owners"]["workshop"] = ["somebody_gone"]
        data["housing"]["owners"]["no_such_room"] = ["marta"]
        data["housing"]["locked"] = ["workshop"]
        loaded = manager.from_data(data)
        self.assertNotIn("workshop", loaded.homes.owners)
        self.assertNotIn("no_such_room", loaded.homes.owners)
        self.assertEqual(loaded.homes.locked, [])


class DataTests(unittest.TestCase):
    def test_what_each_thing_adds_is_to_a_quality_there_is(self) -> None:
        data = json.loads((ROOT / "data" / "housing.json").read_text(encoding="utf-8"))
        settings = housing_settings_from_data(data)
        self.assertTrue(settings.furnishing)
        self.assertTrue(settings.uses)
        with self.assertRaises(ValueError):
            housing_settings_from_data({"furnishing": {"bed": {"luck": 5}}})

    def test_a_game_with_no_such_file_still_has_houses(self) -> None:
        settings = housing_settings_from_data({})
        self.assertGreater(settings.welcome_affection, 0)


if __name__ == "__main__":
    unittest.main()
