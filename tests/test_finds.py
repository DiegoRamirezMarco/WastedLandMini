"""Handed over, and found (S59): things nobody knows that turn up, and a thing put in a
resident's hands by the player."""

import json
import subprocess
import sys
import unittest
from dataclasses import replace
from pathlib import Path

from save.save_manager import SaveManager
from simulation.commands import GiveCommand, NameDiscoveryCommand
from simulation.economy.ledger import FOUND, GIVEN
from simulation.events.world_event import Newcomer
from simulation.items.giving import GIVEN_EVENT
from simulation.items.registry import ItemRegistry
from simulation.registries import DATA_DIR, builtin_registries
from simulation.tastes.settings import DISLIKED, HANDED, HATED, LIKED, LOVED, NEUTRAL
from simulation.tastes.taste import Taste
from simulation.work.finds import BROUGHT_EVENT, FOUND_EVENT, FindSource, find_settings_from_data
from simulation.world import SimulationWorld

ROOT = Path(__file__).resolve().parents[1]
MINUTES_PER_DAY = 24 * 60
STORE = "crate_dorm"


def _types(world: SimulationWorld) -> list[str]:
    return [line.split(" | ")[1] for line in world.event_log]


def _sources(world: SimulationWorld, **chances: float) -> None:
    """The same world with something found every time, or never, by where it comes from."""
    finds = world.registries.finds
    sources = {
        source_id: replace(source, chance=chances.get(source_id, 0.0)) for source_id, source in finds.sources.items()
    }
    world.registries = replace(world.registries, finds=replace(finds, sources=sources))


def _today(world: SimulationWorld, reason: str) -> dict[str, float]:
    """What the settlement's books have down for today under a reason, by resource."""
    return {
        resource: sum(units for why, units in entries.items() if why.split(":")[0] == reason)
        for resource, entries in world.accounts.today.items()
    }


class DataTests(unittest.TestCase):
    def test_what_there_is_to_find_and_where_is_data(self) -> None:
        finds = builtin_registries().finds
        self.assertTrue(finds.enabled)
        self.assertEqual(set(finds.sources), {"expedition", "caravan", "salvage", "newcomer"})
        self.assertGreaterEqual(len(finds.kinds), 4)
        self.assertEqual(set(finds.weights), set(finds.kinds))
        self.assertTrue(finds.sources["newcomer"].keeps)
        self.assertFalse(finds.sources["expedition"].keeps)
        self.assertTrue(all(0.0 < source.chance < 1.0 for source in finds.sources.values()))
        self.assertTrue(all(kind.ask and not kind.choices and kind.item for kind in finds.kinds.values()))

    def test_every_kind_makes_an_item_the_game_can_use(self) -> None:
        world = SimulationWorld.demo_world()
        sergio = world.residents["sergio"]
        for kind_id in world.registries.finds.kinds:
            found = world.finds.find(world, "expedition", sergio, kind_id=kind_id)
            preview = world.crafts.preview(world, found)
            self.assertEqual(preview["description"], "Lo trajo Sergio de fuera.")
            items = ItemRegistry()
            items.load_mapping({**preview, "name": "cosa", "article": "una"}, source="test")
            self.assertEqual(items.get(preview["id"]).category, preview["category"])

    def test_data_that_makes_no_sense_is_refused(self) -> None:
        kind = {"name": "algo", "item": {"category": "food"}}
        good = {"kinds": {"thing": kind}, "sources": {"outside": {"chance": 0.5, "units": [1, 2]}}}
        self.assertTrue(find_settings_from_data(good).enabled)
        for bad in (
            {"kinds": {"thing": {"name": "algo"}}},
            {"kinds": {"thing": {**kind, "choices": {"how": {"name": "Cómo", "source": "raw_food"}}}}},
            {"kinds": {"thing": {**kind, "weight": 0}}},
            {**good, "sources": {"outside": {"chance": 1.5}}},
            {**good, "sources": {"outside": {"chance": 0.5, "units": [0, 2]}}},
            {**good, "sources": {"outside": {"chance": 0.5, "units": [3, 2]}}},
            {**good, "sources": {"outside": "often"}},
            {**good, "most_waiting": -1},
        ):
            with self.assertRaises(ValueError, msg=str(bad)):
                find_settings_from_data(bad)
        registries = builtin_registries()
        clash = replace(registries, finds=replace(registries.finds, kinds={"dish": next(iter(registries.finds.kinds.values()))}))
        with self.assertRaisesRegex(ValueError, "dish"):
            clash.validate()

    def test_without_the_data_nothing_is_ever_found(self) -> None:
        world = SimulationWorld.demo_world()
        world.registries = replace(world.registries, finds=find_settings_from_data({}))
        self.assertIsNone(world.finds.maybe(world, "expedition", world.residents["sergio"]))
        self.assertIsNone(world.finds.find(world, "expedition", world.residents["sergio"]))

    def test_it_needs_no_pygame(self) -> None:
        code = (
            "import sys; from simulation.world import SimulationWorld; "
            "from simulation.commands import GiveCommand, NameDiscoveryCommand; world = SimulationWorld.demo_world(); "
            "found = world.finds.find(world, 'expedition', world.residents['sergio']); "
            "world.apply_command(NameDiscoveryCommand(found.discovery_id, 'cosa rara')); "
            "world.apply_command(GiveCommand('marta', 'stew')); world.step(60 * 24); "
            "print('pygame' in sys.modules)"
        )
        result = subprocess.run([sys.executable, "-c", code], cwd=ROOT, capture_output=True, text=True, check=True)
        self.assertEqual(result.stdout.strip().splitlines()[-1], "False")


class FindingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.world = SimulationWorld.demo_world()
        self.sergio = self.world.residents["sergio"]

    def test_now_and_then_something_nobody_knows_turns_up_and_waits_to_be_named(self) -> None:
        world = self.world
        _sources(world, expedition=1.0)
        found = world.finds.maybe(world, "expedition", self.sergio)
        self.assertIsNotNone(found)
        source = world.registries.finds.sources["expedition"]
        self.assertEqual((found.source, found.by, found.by_name, found.job_id, found.owner), ("expedition", "sergio", "Sergio", "", None))
        self.assertIn(found.kind, world.registries.finds.kinds)
        self.assertTrue(source.units[0] <= found.units <= source.units[1])
        self.assertFalse(found.named)
        self.assertEqual(world.crafts.waiting(world), [found])
        self.assertEqual(world.finds.waiting(world), [found])
        self.assertEqual(world.crafts.options(world, found), {}, "there is nothing to pick: the game has settled it")
        line = next(line for line in world.event_log if f"| {FOUND_EVENT} |" in line)
        self.assertIn("Sergio trae de fuera algo que nadie conoce", line)
        self.assertEqual(world.at_gate, {}, "there is none of it until it has a name")
        _sources(world)
        self.assertIsNone(world.finds.maybe(world, "expedition", self.sergio))
        self.assertIsNone(world.finds.maybe(world, "nowhere", self.sergio))

    def test_no_more_turn_up_while_enough_wait(self) -> None:
        world = self.world
        _sources(world, expedition=1.0)
        most = world.registries.finds.most_waiting
        for _ in range(most + 2):
            world.clock.advance_minutes(1)
            world.finds.maybe(world, "expedition", self.sergio)
        self.assertEqual(len(world.finds.waiting(world)), most)
        first = world.finds.waiting(world)[0]
        self.assertTrue(world.name_discovery(first.discovery_id, "cosa rara").ok)
        world.clock.advance_minutes(1)
        self.assertIsNotNone(world.finds.maybe(world, "expedition", self.sergio))

    def test_whether_and_what_come_of_a_die_of_their_own(self) -> None:
        world, other = self.world, SimulationWorld.demo_world()
        for each in (world, other):
            _sources(each, expedition=1.0)
        before = (world.rng.get_state(), world.event_rng.get_state())
        found = world.finds.maybe(world, "expedition", self.sergio)
        self.assertEqual((world.rng.get_state(), world.event_rng.get_state()), before)
        same = other.finds.maybe(other, "expedition", other.residents["sergio"])
        self.assertEqual((same.kind, same.units), (found.kind, found.units), "the same settlement, the same find")
        self.assertEqual(other.crafts.preview(other, same), world.crafts.preview(world, found))
        # Over many moments every kind turns up, the ones that weigh more oftener.
        _sources(world, expedition=1.0)
        world.registries = replace(world.registries, finds=replace(world.registries.finds, most_waiting=10**6))
        kinds = []
        for _ in range(400):
            world.clock.advance_minutes(1)
            kinds.append(world.finds.maybe(world, "expedition", self.sergio).kind)
        weights = world.registries.finds.weights
        self.assertEqual(set(kinds), set(weights))
        heaviest, lightest = max(weights, key=weights.get), min(weights, key=weights.get)
        self.assertGreater(kinds.count(heaviest), kinds.count(lightest))

    def test_named_it_is_an_item_like_any_other_and_what_there_was_of_it_waits_at_the_gate(self) -> None:
        world = self.world
        found = world.finds.find(world, "expedition", self.sergio, kind_id="found_food")
        units, preview = found.units, world.crafts.preview(world, found)
        result = world.apply_command(NameDiscoveryCommand(found.discovery_id, "galletas saladas"))
        self.assertTrue(result.ok, result.message)
        item = world.registries.items.get(found.item_id)
        self.assertEqual((item.name, item.category), ("galletas saladas", "food"))
        self.assertEqual(dict(item.effects), preview["effects"], "it is what the game had settled, whatever it is called")
        self.assertEqual(list(item.preference_tags), preview["preference_tags"])
        self.assertEqual(world.at_gate, {found.item_id: units})
        self.assertEqual(found.units, 0)
        self.assertEqual(_today(world, FOUND).get("food"), units, "and it is in the books as brought from outside")
        self.assertEqual(world.crafts.waiting(world), [])
        self.assertEqual(self.sergio.makes, {}, "nobody makes it")
        types = _types(world)
        self.assertIn("discovery_named", types)
        self.assertIn(BROUGHT_EVENT, types)
        self.assertFalse(world.name_discovery(found.discovery_id, "otra cosa").ok)
        # It is carried in by whoever keeps the till, and is the settlement's to use.
        world.step(MINUTES_PER_DAY)
        self.assertEqual(world.at_gate, {})
        held = sum(
            each.quantity for inventory in world.containers.values() for each in inventory.items if each.definition_id == found.item_id
        )
        carried = sum(
            each.quantity for resident in world.residents.values() for each in resident.inventory.items if each.definition_id == found.item_id
        )
        self.assertLessEqual(held + carried, units)

    def test_a_name_that_will_not_do_is_refused_as_for_anything_named(self) -> None:
        world = self.world
        found = world.finds.find(world, "expedition", self.sergio)
        for name in ("", "   ", "guiso caliente"):
            self.assertFalse(world.name_discovery(found.discovery_id, name).ok, name)
        self.assertFalse(found.named)
        self.assertEqual(world.at_gate, {})

    def test_what_a_newcomer_brings_is_theirs(self) -> None:
        world = self.world
        marta = world.residents["marta"]
        found = world.finds.find(world, "newcomer", marta, kind_id="found_trinket")
        self.assertEqual(found.owner, "marta")
        self.assertTrue(world.name_discovery(found.discovery_id, "medallón").ok)
        mine = [item for item in marta.inventory.items if item.definition_id == found.item_id]
        self.assertEqual([(item.owner_id, item.quantity) for item in mine], [("marta", 1)])
        self.assertEqual(world.at_gate, {})
        self.assertEqual(_today(world, FOUND), {}, "what is somebody's own is not in the settlement's books")

    def test_what_was_found_for_everybody_outlasts_whoever_found_it_and_their_own_goes_with_them(self) -> None:
        world = self.world
        for_all = world.finds.find(world, "expedition", self.sergio)
        world.clock.advance_minutes(1)
        own = world.finds.find(world, "newcomer", self.sergio)
        world.crafts.gone(world, self.sergio)
        del world.residents["sergio"]
        self.assertEqual(world.crafts.waiting(world), [for_all])
        self.assertNotIn(own.discovery_id, world.discoveries)
        self.assertTrue(world.name_discovery(for_all.discovery_id, "cosa rara").ok)
        self.assertEqual(sum(world.at_gate.values()), 1 if for_all.item_id is None else world.at_gate[for_all.item_id])
        # Somebody whose own it was, gone by the time it has a name: it is the settlement's.
        marta = world.residents["marta"]
        kept = world.finds.find(world, "newcomer", marta)
        del world.residents["marta"]
        self.assertTrue(world.name_discovery(kept.discovery_id, "amuleto").ok)
        self.assertIn(kept.item_id, world.at_gate)

    def test_what_a_caravan_leaves_was_found_by_nobody_here(self) -> None:
        world = self.world
        _sources(world, caravan=1.0)
        world.clock.day, world.clock.hour, world.clock.minute = 2, 9, 0
        world.merchants.arrive(world, world.registries.world_events.events["caravan"])
        (found,) = world.finds.waiting(world)
        self.assertEqual((found.source, found.by), ("caravan", ""))
        self.assertTrue(found.by_name)
        self.assertTrue(world.name_discovery(found.discovery_id, "especia rara").ok)
        self.assertIn(found.item_id, world.at_gate)
        self.assertEqual(world.registries.items.get(found.item_id).description, "Lo dejó de muestra quien vino a comerciar.")

    def test_whoever_comes_to_stay_may_bring_something(self) -> None:
        world = self.world
        _sources(world, newcomer=1.0)
        resident = world.happenings._settle_one(world, Newcomer("zoe", "Zoe"), True)
        (found,) = world.finds.waiting(world)
        self.assertEqual((found.source, found.by, found.owner), ("newcomer", resident.resident_id, resident.resident_id))
        self.assertEqual(resident.inventory.items, [], "not until it has a name")

    def test_a_trip_outside_may_bring_one_back(self) -> None:
        world = self.world
        _sources(world, expedition=1.0)
        for _ in range(2 * MINUTES_PER_DAY):
            world.step(1)
            if "expedition_returned" in _types(world):
                break
        self.assertIn("expedition_returned", _types(world))
        found = world.finds.waiting(world)
        self.assertTrue(found)
        self.assertEqual(found[0].source, "expedition")
        self.assertIn(found[0].by, world.residents)

    def test_with_nobody_to_name_them_finds_change_nothing_that_happens(self) -> None:
        plain, finding = SimulationWorld.demo_world(seed=5), SimulationWorld.demo_world(seed=5)
        _sources(plain)
        _sources(finding, expedition=1.0, caravan=1.0, salvage=1.0, newcomer=1.0)
        for world in (plain, finding):
            world.step(3 * MINUTES_PER_DAY)
        self.assertTrue(finding.finds.waiting(finding))
        self.assertEqual(plain.rng.get_state(), finding.rng.get_state())
        self.assertEqual(
            [line for line in finding.event_log if f"| {FOUND_EVENT} |" not in line], plain.event_log
        )


class GivingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.world = SimulationWorld.demo_world()
        self.marta = self.world.residents["marta"]
        self.stew = self.world.registries.items.resolve("stew")

    def _taste(self, liking: float) -> None:
        """Have Marta take stew a given way, whatever she came with."""
        profile = self.world.tastes.profile(self.world, self.marta)
        profile.categories[self.stew.category] = Taste(leaning=0)
        profile.items[self.stew.item_id] = Taste(leaning=0)
        for tag in self.stew.preference_tags:
            profile.tags[tag] = Taste(leaning=liking)
        self.marta.needs.hunger, self.marta.mood = 0.0, 50.0

    def _held(self, definition_id: str) -> int:
        return self.world.giving.givable(self.world).get(definition_id, 0)

    def test_a_thing_that_is_everybodys_is_put_in_their_hands_and_is_theirs(self) -> None:
        world = self.world
        before = self._held("stew")
        self.assertGreater(before, 0)
        result = world.apply_command(GiveCommand("marta", "stew"))
        self.assertTrue(result.ok, result.message)
        self.assertEqual(result.message, "Marta tiene ahora un guiso caliente")
        self.assertEqual(self._held("stew"), before - 1)
        mine = [item for item in self.marta.inventory.items if item.definition_id == "stew"]
        self.assertEqual([(item.owner_id, item.quantity) for item in mine], [("marta", 1)])
        self.assertEqual(_today(world, GIVEN).get("food"), -1, "it is in the books as given")
        line = next(line for line in world.event_log if f"| {GIVEN_EVENT} |" in line)
        self.assertIn("A Marta se le da un guiso caliente", line)

    def test_how_they_take_it_goes_by_their_tastes_and_is_seen_said_and_remembered(self) -> None:
        world = self.world
        world.stock(world.containers[STORE], "stew", 10, None)
        moods, values = {}, {}
        for reaction, liking in ((HATED, -95), (DISLIKED, -40), (NEUTRAL, 0), (LIKED, 40), (LOVED, 95)):
            self._taste(liking)
            said = len(world.event_log)
            result = world.give("marta", "stew")
            self.assertEqual(result.reaction, reaction)
            moods[reaction] = self.marta.mood - 50.0
            values[reaction] = world.memories.recent("marta", 1)[-1].emotional_value
            lines = [line for line in world.event_log[said:] if "| taste_reaction |" in line]
            if reaction == NEUTRAL:
                self.assertEqual(lines, [])
            else:
                self.assertEqual(len(lines), 1)
                self.assertIn(world.registries.tastes.lines[HANDED][reaction].format(name="Marta", thing="un guiso caliente"), lines[0])
            self.assertIn("guiso caliente", world.memories.recent("marta", 1)[-1].text)
        self.assertLess(moods[HATED], moods[DISLIKED])
        self.assertLess(moods[DISLIKED], 0.0)
        self.assertGreater(moods[LOVED], moods[LIKED])
        self.assertGreater(moods[LIKED], 0.0)
        self.assertEqual(sorted(values.values()), [values[each] for each in (HATED, DISLIKED, NEUTRAL, LIKED, LOVED)])
        self.assertLess(values[DISLIKED], 0.0)
        self.assertGreater(values[LIKED], 0.0)

    def test_it_shows_something_of_their_taste_to_the_player(self) -> None:
        world = self.world
        self._taste(95)
        known = {key for key, _state, _taken in world.tastes.found_out(world, self.marta)}
        for _ in range(3):
            self._taste(95)
            world.give("marta", "stew")
        found = {key for key, _state, _taken in world.tastes.found_out(world, self.marta)} - known
        self.assertTrue(found)
        self.assertTrue(found <= {"item:stew", "category:food", *(f"tag:{tag}" for tag in self.stew.preference_tags)}, found)

    def test_what_cannot_be_given_is_refused(self) -> None:
        world = self.world
        for arguments in (("nobody", "stew"), ("marta", "no_such_thing")):
            self.assertFalse(world.give(*arguments).ok, arguments)
        # What is somebody's own, wherever it is kept, is not everybody's to give.
        crate = world.containers[STORE]
        world.stock(crate, "baton", 1, "raul")
        self.assertEqual(self._held("baton"), 0)
        self.assertFalse(world.give("marta", "baton").ok)
        self.assertEqual(crate.stack_of("baton", "raul").quantity, 1)
        # Nor is anything to somebody who is not there.
        self.marta.away_until = world.clock.total_minutes + 600
        if self.marta.away:
            self.assertFalse(world.give("marta", "stew").ok)
        while self._held("stew"):
            self.assertTrue(world.give("raul", "stew").ok)
        self.assertFalse(world.give("raul", "stew").ok, "there is none left")

    def test_it_is_as_fresh_and_as_rare_in_their_hands_as_it_was(self) -> None:
        world = self.world
        for inventory in world.containers.values():
            inventory.items[:] = [item for item in inventory.items if item.definition_id != "stew"]
        world.stock(world.containers[STORE], "stew", 2, None, level=3, freshness=40.0)
        self.assertTrue(world.give("marta", "stew").ok)
        (mine,) = [item for item in self.marta.inventory.items if item.definition_id == "stew"]
        self.assertEqual((mine.level, mine.freshness, mine.owner_id), (3, 40.0, "marta"))

    def test_giving_throws_none_of_the_settlements_dice(self) -> None:
        world = self.world
        before = (world.rng.get_state(), world.event_rng.get_state())
        self.assertTrue(world.give("marta", "stew").ok)
        self.assertEqual((world.rng.get_state(), world.event_rng.get_state()), before)

    def test_what_was_found_can_be_given_once_it_is_carried_in(self) -> None:
        world = self.world
        found = world.finds.find(world, "expedition", world.residents["sergio"], kind_id="found_toy")
        self.assertTrue(world.name_discovery(found.discovery_id, "peonza").ok)
        self.assertFalse(world.give("marta", found.item_id).ok, "it is still at the gate")
        world.stock(world.containers[STORE], found.item_id, world.at_gate.pop(found.item_id), None)
        result = world.give("marta", found.item_id)
        self.assertTrue(result.ok, result.message)
        self.assertIn("peonza", result.message)


class SaveTests(unittest.TestCase):
    def test_what_waits_and_what_was_named_are_saved_and_go_on_the_same(self) -> None:
        manager = SaveManager()
        world = SimulationWorld.demo_world(seed=5)
        sergio = world.residents["sergio"]
        named = world.finds.find(world, "expedition", sergio, kind_id="found_drink")
        self.assertTrue(world.name_discovery(named.discovery_id, "refresco").ok)
        world.clock.advance_minutes(1)
        waiting = world.finds.find(world, "newcomer", world.residents["marta"])
        self.assertTrue(world.give("ines", "stew").ok)
        data = manager.to_data(world)
        self.assertEqual(data["version"], manager.CURRENT_VERSION)
        self.assertGreaterEqual(manager.CURRENT_VERSION, 50)
        loaded = manager.from_data(json.loads(json.dumps(data)))
        self.assertEqual(loaded.registries.items.get(named.item_id).name, "refresco")
        again = loaded.discoveries[waiting.discovery_id]
        self.assertEqual((again.source, again.units, again.owner, again.kind), ("newcomer", waiting.units, "marta", waiting.kind))
        self.assertEqual(loaded.at_gate, world.at_gate)
        self.assertEqual(loaded.crafts.preview(loaded, again), world.crafts.preview(world, waiting))
        for each in (world, loaded):
            self.assertTrue(each.name_discovery(waiting.discovery_id, "amuleto").ok)
            each.step(2 * MINUTES_PER_DAY)
        self.assertEqual(manager.to_data(loaded), manager.to_data(world))

    def test_a_save_from_before_has_no_finds_and_one_that_is_damaged_keeps_what_it_can(self) -> None:
        manager = SaveManager()
        world = SimulationWorld.demo_world()
        found = world.finds.find(world, "expedition", world.residents["sergio"])
        data = manager.to_data(world)
        old = json.loads(json.dumps(data))
        old["version"] = 49
        old["discoveries"] = []
        loaded = manager.from_data(old)
        self.assertEqual(loaded.finds.waiting(loaded), [])
        loaded.step(MINUTES_PER_DAY)
        broken = json.loads(json.dumps(data))
        broken["discoveries"][0]["units"] = "plenty"
        broken["discoveries"].append({"discovery_id": "discovery_9", "kind": "no_such_kind", "source": "expedition"})
        loaded = manager.from_data(broken)
        again = loaded.discoveries[found.discovery_id]
        self.assertEqual((again.source, again.units, again.owner), ("expedition", 0, None))
        self.assertNotIn("discovery_9", loaded.discoveries)
        self.assertTrue(loaded.name_discovery(found.discovery_id, "cosa rara").ok, "with none of it left, it still has a name")
        self.assertEqual(loaded.at_gate, {})


class TextTests(unittest.TestCase):
    def test_the_lines_for_a_thing_handed_over_name_no_giver(self) -> None:
        data = json.loads((DATA_DIR / "tastes.json").read_text(encoding="utf-8"))
        self.assertEqual(set(data["lines"]["handed"]), {HATED, DISLIKED, LIKED, LOVED})
        self.assertTrue(all("{giver}" not in line for line in data["lines"]["handed"].values()))
        resources = json.loads((DATA_DIR / "resources.json").read_text(encoding="utf-8"))
        self.assertIn(GIVEN, resources["reasons"])
        self.assertEqual(FindSource("x").units, (1, 1))


if __name__ == "__main__":
    unittest.main()
