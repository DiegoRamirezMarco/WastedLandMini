import json
import unittest

from save.save_manager import SaveManager
from simulation.commands import FoundResidentCommand, SetMannerCommand
from simulation.registries import builtin_registries
from simulation.residents.manner import EAT, FIGHT, SIT, WALK, manner_settings_from_data
from simulation.world import SimulationWorld
from skeleton.plan import VIEWS, builtin_plan

KINDS = ("walk", "eat", "fight", "shoot", "knife", "sit")
# How many ways there are of each: three of everything, and four of sitting.
WAYS = {"sit": 4}


class MannerDataTests(unittest.TestCase):
    def setUp(self) -> None:
        self.manners = builtin_registries().manners

    def test_there_are_three_ways_of_walking_eating_fighting_shooting_and_using_a_knife_and_four_of_sitting(self) -> None:
        self.assertEqual(tuple(self.manners.kinds), KINDS)
        for kind_id in KINDS:
            choices = self.manners.of_kind(kind_id)
            self.assertEqual(len(choices), WAYS.get(kind_id, 3), kind_id)
            self.assertEqual(len({manner.name for manner in choices}), len(choices), "each is called something else")
            self.assertTrue(all(manner.description for manner in choices))

    def test_every_manner_has_a_clip_of_its_own_that_moves_from_the_side_and_from_the_front(self) -> None:
        plan = builtin_plan()
        clips = [manner.clip for manner in self.manners.manners.values()]
        self.assertEqual(len(set(clips)), len(clips), "no two manners look the same")
        for manner in self.manners.manners.values():
            self.assertIn(manner.clip, plan.clips, manner.manner_id)
            if self.manners.kinds[manner.kind].occasion == SIT:
                continue
            for view in VIEWS:
                self.assertGreater(plan.frames(manner.clip, view), 1, (manner.manner_id, view))

    def test_a_way_of_sitting_is_a_way_of_being_still_low_on_the_ground(self) -> None:
        plan = builtin_plan()
        standing = plan.pose("doll_right")
        tall = -min(y for _, y in standing.values())
        seen = []
        for manner in self.manners.of_kind("sit"):
            self.assertEqual(plan.frames(manner.clip, "side"), 1, "whoever sits, sits still: it is their breath that moves")
            self.assertNotIn(manner.clip, plan.once)
            pose = plan.pose("doll_right", manner.clip)
            self.assertLess(-min(y for _, y in pose.values()), tall * 0.8, f"{manner.manner_id} is lower than standing")
            self.assertGreater(pose["pelvis"][1], standing["pelvis"][1] + tall * 0.2, "the hips are down")
            self.assertLessEqual(max(y for _, y in pose.values()), 1e-6, "and none of it is under the ground")
            self.assertLess(pose["head"][1], pose["pelvis"][1], "the head is still up")
            seen.append(tuple(round(value, 1) for joint in ("head", "knee_right", "hand_right") for value in pose[joint]))
        self.assertEqual(len(set(seen)), len(seen), "no two are the same to look at")

    def test_sitting_shows_while_they_are_at_something_done_sitting_down(self) -> None:
        self.assertEqual(self.manners.kind_for(SIT).kind_id, "sit")
        for action in ("relax", "listen", "eat", "drink"):
            self.assertEqual(self.manners.during(SIT, action).kind_id, "sit", action)
        for action in ("work", "sleep", "build", "wander", "chat"):
            self.assertIsNone(self.manners.during(SIT, action), action)
        self.assertIsNone(self.manners.during(EAT, "eat"), "eating is a doing of its own: it shows whenever they eat")
        made = manner_settings_from_data({"kinds": {"perch": {"occasion": "sit", "actions": ["fish"]}}})
        self.assertEqual(made.during(SIT, "fish").kind_id, "perch")
        self.assertEqual(made.kinds["perch"].actions, ("fish",))
        self.assertEqual(manner_settings_from_data({"kinds": {"walk": {"occasion": "walk"}}}).kinds["walk"].actions, ())

    def test_the_weapon_in_hand_says_which_kind_of_manner_a_fight_calls_for(self) -> None:
        self.assertEqual(self.manners.kind_for(WALK).kind_id, "walk")
        self.assertEqual(self.manners.kind_for(EAT).kind_id, "eat")
        self.assertEqual(self.manners.kind_for(FIGHT).kind_id, "fight")
        self.assertEqual(self.manners.kind_for(FIGHT, ("weapon", "blunt")).kind_id, "fight")
        self.assertEqual(self.manners.kind_for(FIGHT, ("weapon", "blade")).kind_id, "knife")
        self.assertEqual(self.manners.kind_for(FIGHT, ("weapon", "firearm")).kind_id, "shoot")

    def test_data_that_cannot_be_shown_is_refused(self) -> None:
        kinds = {"walk": {"name": "Andar", "occasion": "walk"}}
        with self.assertRaises(ValueError):
            manner_settings_from_data({"kinds": {"swim": {"occasion": "swim"}}})
        with self.assertRaises(ValueError):
            manner_settings_from_data({"kinds": kinds, "manners": {"dive": {"kind": "swim"}}})
        # A walk that does not end where the next stride begins would jump at every minute.
        with self.assertRaises(ValueError):
            manner_settings_from_data({"kinds": kinds, "manners": {"limp": {"kind": "walk", "rate": 1.5}}})
        self.assertEqual(manner_settings_from_data({}).kind_for(WALK), None)


class ResidentMannerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.world = SimulationWorld.demo_world(seed=7)
        self.manners = self.world.registries.manners
        self.manager = SaveManager()

    def test_whoever_was_given_none_has_manners_of_their_own_and_they_are_not_everybodys(self) -> None:
        again = SimulationWorld.demo_world(seed=99)
        for kind_id in KINDS:
            found = {
                resident_id: self.world.manner_of(resident, kind_id).manner_id
                for resident_id, resident in self.world.residents.items()
            }
            self.assertGreater(len(set(found.values())), 1, f"everybody would {kind_id} alike")
            # Whatever the settlement and whenever it is asked, the same resident does it the same way.
            for resident_id, manner_id in found.items():
                self.assertEqual(again.manner_of(again.residents[resident_id], kind_id).manner_id, manner_id)
        self.assertTrue(all(resident.manners == {} for resident in self.world.residents.values()))

    def test_the_player_gives_a_resident_a_manner_and_only_one_of_the_right_kind(self) -> None:
        raul = self.world.residents["raul"]
        other = next(m for m in self.manners.of_kind("walk") if m != self.world.manner_of(raul, "walk"))
        self.assertTrue(self.world.apply_command(SetMannerCommand("raul", "walk", other.manner_id)))
        self.assertEqual(self.world.manner_of(raul, "walk"), other)
        self.assertEqual(raul.manners, {"walk": other.manner_id})
        # Not a manner, not of that kind, or not anybody: nothing changes.
        self.assertFalse(self.world.apply_command(SetMannerCommand("raul", "walk", "moonwalk")))
        self.assertFalse(self.world.apply_command(SetMannerCommand("raul", "eat", other.manner_id)))
        self.assertFalse(self.world.apply_command(SetMannerCommand("nobody", "walk", other.manner_id)))
        self.assertEqual(raul.manners, {"walk": other.manner_id})

    def test_the_first_resident_is_made_with_the_manners_chosen_for_them(self) -> None:
        world = SimulationWorld.new_settlement(seed=7)
        chosen = {"walk": "walk_swagger", "knife": "knife_overhand", "eat": "walk_shuffle", "swim": "crawl"}
        created = world.apply_command(FoundResidentCommand("Ada", 34, {}, (), chosen))
        ada = world.residents[created]
        self.assertEqual(ada.manners, {"walk": "walk_swagger", "knife": "knife_overhand"})
        self.assertEqual(world.manner_of(ada, "walk").clip, "walk_swagger")
        # What was left out, or could not be kept, is theirs by default like anybody's.
        self.assertEqual(world.manner_of(ada, "eat"), self.manners.default(created, "eat"))
        # And somebody made with none at all is still somebody.
        plain = SimulationWorld.new_settlement(seed=7)
        self.assertIsNotNone(plain.apply_command(FoundResidentCommand("Ada", 34)))
        self.assertEqual(plain.residents["ada"].manners, {})

    def test_manners_survive_saving(self) -> None:
        self.world.apply_command(SetMannerCommand("raul", "fight", "fight_kicker"))
        self.world.apply_command(SetMannerCommand("marta", "shoot", "shoot_hip"))
        data = json.loads(json.dumps(self.manager.to_data(self.world)))
        self.assertEqual(data["version"], SaveManager.CURRENT_VERSION)
        loaded = self.manager.from_data(data)
        self.assertEqual(loaded.residents["raul"].manners, {"fight": "fight_kicker"})
        self.assertEqual(loaded.residents["marta"].manners, {"shoot": "shoot_hip"})
        self.assertEqual(self.manager.to_data(loaded), self.manager.to_data(self.world))

    def test_an_older_save_loads_with_everyone_moving_their_own_way(self) -> None:
        data = self.manager.to_data(self.world)
        data["version"] = 20
        for resident in data["residents"]:
            del resident["manners"]
        loaded = self.manager.from_data(json.loads(json.dumps(data)))
        for resident_id, resident in loaded.residents.items():
            self.assertEqual(resident.manners, {})
            self.assertEqual(loaded.manner_of(resident, "walk"), self.manners.default(resident_id, "walk"))

    def test_a_manner_that_is_no_longer_defined_is_forgotten_and_does_not_break_the_save(self) -> None:
        data = self.manager.to_data(self.world)
        data["residents"][0]["manners"] = {"walk": "moonwalk", "eat": "eat_wolf", "fight": "eat_wolf", "swim": 3}
        data["residents"][1]["manners"] = ["walk_swagger"]
        loaded = self.manager.from_data(json.loads(json.dumps(data)))
        first, second = list(loaded.residents.values())[:2]
        self.assertEqual(first.manners, {"eat": "eat_wolf"})
        self.assertEqual(second.manners, {})

    def test_a_manner_changes_how_it_looks_and_nothing_of_what_happens(self) -> None:
        other = SimulationWorld.demo_world(seed=7)
        for resident_id in other.residents:
            for kind_id in KINDS:
                other.apply_command(SetMannerCommand(resident_id, kind_id, self.manners.of_kind(kind_id)[-1].manner_id))
        self.world.step(6 * 60)
        other.step(6 * 60)

        def bare(world: SimulationWorld) -> dict:
            data = self.manager.to_data(world)
            for resident in data["residents"]:
                del resident["manners"]
            return data

        self.assertEqual(bare(other), bare(self.world))


if __name__ == "__main__":
    unittest.main()
