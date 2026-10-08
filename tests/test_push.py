"""Work that is seen, pushed and given out (S52): how far along a post is, what somebody would
make of one, putting them to it, and a shift worked harder at the player's word."""

import json
import subprocess
import sys
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from save.save_manager import SaveManager
from simulation.ai.affect import PUSH, TASK
from simulation.commands import AffectCommand, SetResearchCommand
from simulation.economy.ledger import MADE, SPOILED
from simulation.health.injury import Injury
from simulation.registries import DATA_DIR, BuiltInRegistries, builtin_registries
from simulation.residents.attributes import Attributes
from simulation.residents.needs import Needs
from simulation.work.rush import (
    ACCIDENT_EVENT,
    HURT,
    LEAST_HEALTH,
    PUSH_EVENT,
    SPOIL,
    TOOL,
    RushSettings,
    rush_settings_from_data,
)
from simulation.work.work_system import WORK_ACTION
from simulation.world import SimulationWorld
from tests.worlds import no_store

ROOT = Path(__file__).resolve().parent.parent
MINUTES_PER_DAY = 24 * 60
PUSH_KIND = f"{TASK}:{PUSH}"
RUSH = json.loads((ROOT / "data" / "work.json").read_text(encoding="utf-8"))["rush"]


def _keep_content(world: SimulationWorld, *spared: str) -> None:
    """Nobody wants for anything. Whoever is `spared` still tires and frays as they would."""
    for resident_id, resident in world.residents.items():
        if resident_id in spared:
            resident.needs.hunger = resident.needs.thirst = resident.needs.social = 0.0
        else:
            resident.needs = Needs(hunger=0, thirst=0, tiredness=0, social=0, stress=0)


def _settled(seed: int = 7, hour: int = 8) -> SimulationWorld:
    """The settlement that comes ready made, with everyone content, no grudges, and in the middle
    of every attribute: what is looked at here is told apart from all that."""
    world = SimulationWorld.demo_world(seed=seed)
    no_store(world)
    world.relationships.clear()
    world.clock.hour, world.clock.minute = hour, 0
    for resident in world.residents.values():
        resident.attributes = Attributes()
    _keep_content(world)
    return world


def _only(world: SimulationWorld, *resident_ids: str) -> None:
    for resident_id in [each for each in world.residents if each not in resident_ids]:
        del world.residents[resident_id]


def _run(world: SimulationWorld, minutes: int, until=None, spared: tuple[str, ...] = ()) -> bool:
    for _ in range(minutes):
        world.step(1)
        _keep_content(world, *spared)
        if until is not None and until():
            return True
    return False


def _to_post(world: SimulationWorld, resident_id: str) -> None:
    resident = world.residents[resident_id]
    if not _run(world, 180, lambda: world.work.on_duty(world, resident)):
        raise AssertionError(f"{resident_id} never reached their post")


def _push(world: SimulationWorld, resident_id: str):
    return world.apply_command(AffectCommand(resident_id, PUSH_KIND, None))


def _push_when_free(world: SimulationWorld, resident_id: str, limit: int = 240) -> None:
    """Tell somebody to push their post as soon as they can be told: in the settlement as it
    comes, they may have something on their mind first."""
    for _ in range(limit):
        if _push(world, resident_id).ok:
            return
        world.step(1)
    raise AssertionError(f"{resident_id} could never be told to push")


def _risking(world: SimulationWorld, *mishaps: str, risk: float = 1.0) -> None:
    """Have a push end badly as often as `risk` says, and only in these ways."""
    rush = world.registries.rush
    kept = {name: rush.mishaps[name] for name in mishaps or rush.mishaps}
    world.registries = replace(world.registries, rush=replace(rush, risk=risk, mishaps=kept))


def _types(world: SimulationWorld) -> list[str]:
    return [line.split(" | ")[1] for line in world.event_log]


def _made(world: SimulationWorld, resource: str, job_id: str) -> float:
    return world.accounts.today.get(resource, {}).get(f"{MADE}:{job_id}", 0.0)


class RushDataTests(unittest.TestCase):
    def test_what_a_push_does_and_risks_is_data(self) -> None:
        rush = builtin_registries().rush
        self.assertTrue(rush.enabled)
        self.assertEqual((rush.pace, rush.risk), (1.5, 0.05))
        self.assertEqual(sorted(rush.mishaps), sorted((HURT, TOOL, SPOIL)))
        self.assertTrue(all(kind in builtin_registries().injuries for kind in rush.mishaps[HURT].injuries))
        self.assertFalse(RushSettings().enabled, "with no data for it nobody can be pushed")

    def test_data_that_makes_no_sense_is_refused(self) -> None:
        def changed(**changes) -> dict:
            return {**RUSH, **changes}

        for bad in (
            changed(pace=0.8),
            changed(risk=1.5),
            changed(check_minutes=0),
            changed(tired_risk=0.5),
            changed(level_relief=2),
            changed(per_minute={"boredom": 1}),
            changed(mishaps={"plague": {"weight": 1}}),
            changed(mishaps={"hurt": {"weight": 1}}),
            changed(mishaps={"spoil": {"weight": 0, "fraction": 0.2}}),
            changed(mishaps={"spoil": {"weight": 1, "fraction": 1.5}}),
            changed(mishaps={"hurt": {"weight": 1, "injuries": {"cut": {"harm": [9, 3]}}}}),
        ):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                rush_settings_from_data(bad)

    def test_a_push_that_hurts_in_a_way_there_is_not_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            for path in DATA_DIR.rglob("*.json"):
                target = root / path.relative_to(DATA_DIR)
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
            data = json.loads((root / "work.json").read_text(encoding="utf-8"))
            data["rush"]["mishaps"]["hurt"]["injuries"] = {"frostbite": {"harm": [5, 9]}}
            (root / "work.json").write_text(json.dumps(data), encoding="utf-8")
            with self.assertRaises(ValueError):
                BuiltInRegistries.load(root)

    def test_pushing_needs_no_pygame(self) -> None:
        check = (
            "import sys; import simulation.work.rush; from simulation.world import SimulationWorld; "
            "from simulation.commands import AffectCommand; world = SimulationWorld.demo_world(); world.step(120); "
            "world.apply_command(AffectCommand('raul', 'task:push', None)); world.step(120); "
            "sys.exit(1 if 'pygame' in sys.modules else 0)"
        )
        done = subprocess.run([sys.executable, "-c", check], cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(done.returncode, 0, done.stderr)


class SeenTests(unittest.TestCase):
    def test_how_far_along_the_next_unit_is_can_be_asked_of_whoever_is_at_a_post(self) -> None:
        world = _settled()
        raul = world.residents["raul"]
        self.assertIsNone(world.work.progress(world, raul), "on the way there, there is nothing to be far along with")
        _to_post(world, "raul")
        seen = []
        for _ in range(40):
            world.step(1)
            _keep_content(world)
            if world.work.on_duty(world, raul):
                seen.append(world.work.progress(world, raul))
        self.assertTrue(all(0.0 <= each <= 1.0 for each in seen))
        self.assertTrue(any(later < earlier for earlier, later in zip(seen, seen[1:])), "a unit came out and it began again")
        self.assertTrue(any(later > earlier for earlier, later in zip(seen, seen[1:])))
        self.assertTrue(_run(world, 6 * 60, lambda: not world.work.on_duty(world, raul)))
        self.assertIsNone(world.work.progress(world, raul), "the shift is over")

    def test_whoever_studies_is_as_far_along_as_what_is_being_worked_out(self) -> None:
        world = _settled(hour=9)
        spot = next(
            (x, y)
            for y in range(1, world.tile_map.height - 2)
            for x in range(1, world.tile_map.width - 2)
            if world.urbanism.object_error(world, "study_desk", (x, y)) is None
        )
        world.urbanism.place_object(world, "study_desk", spot)
        world.staffing.assign(world, world.residents["lucia"], "water_carrier")
        self.assertTrue(world.staffing.assign(world, world.residents["nuria"], "researcher"))
        world.apply_command(SetResearchCommand("pump"))
        _to_post(world, "nuria")
        _run(world, 60)
        nuria = world.residents["nuria"]
        subject = world.registries.research.subjects["pump"]
        self.assertGreater(world.studies.progress["pump"], 0)
        self.assertAlmostEqual(world.work.progress(world, nuria), world.studies.progress["pump"] / subject.minutes)

    def test_what_somebody_would_make_of_a_post_goes_by_what_they_are_today(self) -> None:
        world = _settled()
        jobs = world.registries.jobs
        strong, plain, weak = world.residents["tomas"], world.residents["marta"], world.residents["vera"]
        strong.attributes.strength, weak.attributes.strength = 10.0, 1.0
        made = {each.resident_id: world.work.expected(world, each, jobs["farmer"]) for each in (strong, plain, weak)}
        self.assertEqual(made["marta"].pace, 1.0, "in the middle of everything, with nothing in hand: a plain pair of hands")
        self.assertGreater(made["tomas"].pace, made["marta"].pace)
        self.assertGreater(made["marta"].pace, made["vera"].pace)
        self.assertGreater(made["tomas"].per_day, made["vera"].per_day)
        # It is asked of anybody, whether or not the post is theirs, and tells what they carry and know.
        raul = world.residents["raul"]
        self.assertEqual(world.work.expected(world, raul, jobs["farmer"]).pace, 1.5, "he has a hoe")
        raul.trade["farmer"] = float(world.registries.crafts.levels[2])
        self.assertAlmostEqual(world.work.expected(world, raul, jobs["farmer"]).pace, 1.5 * (1 + 2 * world.registries.crafts.pace))
        # Hurt or in low spirits, less; and a post that makes nothing by the unit has none a day.
        plain.mood = 10.0
        self.assertLess(world.work.expected(world, plain, jobs["farmer"]).pace, 1.0)
        self.assertIsNone(world.work.expected(world, strong, jobs["guard"]).per_day)
        # What is worked out goes by the head.
        strong.attributes.mind = 10.0
        self.assertGreater(
            world.work.expected(world, strong, jobs["researcher"]).pace, world.work.expected(world, weak, jobs["researcher"]).pace
        )

    def test_it_is_how_fast_the_work_goes(self) -> None:
        world = _settled()
        _only(world, "raul")
        raul, job = world.residents["raul"], world.registries.jobs["farmer"]
        _to_post(world, "raul")
        _run(world, 3)
        # Asked the minute after, it is what the minute before went by.
        expected = world.work.expected(world, raul, job)
        self.assertEqual(world.work.pace(world, raul, job, world.work.tool_of(world, raul, job)), expected.pace)
        self.assertEqual(raul.work_needed, -(-job.produces.every_minutes // expected.pace))
        self.assertEqual(expected.per_day, 8 * 60 / raul.work_needed)


class PushOrderTests(unittest.TestCase):
    def test_it_is_for_whoever_has_a_shift_ahead_at_a_post_that_makes_something(self) -> None:
        world = _settled(hour=9)
        offered = lambda name: PUSH_KIND in [option.kind for option in world.affect_options(name)]
        self.assertTrue(offered("raul"), "the garden makes food")
        self.assertFalse(offered("tomas"), "there is nothing to push about keeping watch")
        self.assertFalse(offered("sergio"), "nor about what is done outside")
        self.assertFalse(offered("marta"), "the kitchen opens at eleven")
        world.clock.hour = 12
        self.assertTrue(offered("marta"))
        world.clock.hour = 20
        self.assertFalse(offered("raul"), "the garden is done for the day")
        world.clock.hour = 9
        world.residents["raul"].injuries.append(Injury("fracture", 80.0))
        self.assertFalse(offered("raul"), "in no state to work")
        self.assertFalse(_push(world, "tomas").ok)
        self.assertEqual(world.residents["tomas"].pushing_until, 0)

    def test_a_job_can_say_it_is_not_pushed(self) -> None:
        world = _settled(hour=9)
        jobs = dict(world.registries.jobs)
        jobs["farmer"] = replace(jobs["farmer"], rush=False)
        world.registries = replace(world.registries, jobs=jobs)
        self.assertNotIn(PUSH_KIND, [option.kind for option in world.affect_options("raul")])
        self.assertFalse(_push(world, "raul").ok)
        self.assertIn("nada que apretar", world.rush.obstacle(world, world.residents["raul"]))

    def test_told_to_they_go_to_their_post_and_push_it_until_the_shift_is_over(self) -> None:
        world = _settled()
        _risking(world, risk=0.0)
        raul = world.residents["raul"]
        self.assertFalse(world.work.on_duty(world, raul))
        result = _push(world, "raul")
        self.assertTrue(result.ok, result.message)
        self.assertEqual(raul.pushing_until, 13 * 60, "what is left of the morning in the garden")
        self.assertTrue(world.rush.pushed(world, raul))
        self.assertEqual(_types(world).count(PUSH_EVENT), 1)
        self.assertEqual([queued.order.kind for queued in world.orders_of("raul")], [PUSH_KIND], "it is what he is at")
        _to_post(world, "raul")
        self.assertFalse(_push(world, "raul").ok, "he is at it already")
        self.assertTrue(_run(world, 6 * 60, lambda: not world.rush.pushed(world, raul)))
        self.assertEqual((world.clock.hour, world.clock.minute), (13, 0))
        self.assertEqual(world.rush.pace(world, raul), 1.0)

    def test_already_at_their_post_they_go_on_with_it_harder(self) -> None:
        world = _settled()
        _to_post(world, "raul")
        raul = world.residents["raul"]
        at = raul.activity
        self.assertTrue(_push(world, "raul").ok)
        self.assertIs(raul.activity, at)
        self.assertEqual(raul.activity.action, WORK_ACTION)
        self.assertTrue(raul.activity.ordered)
        self.assertEqual(world.rush.pace(world, raul), world.registries.rush.pace)

    def test_what_they_would_make_of_another_post_is_none_the_more_for_pushing_theirs(self) -> None:
        world = _settled()
        raul, jobs = world.residents["raul"], world.registries.jobs
        before = {job_id: world.work.expected(world, raul, jobs[job_id]).pace for job_id in ("farmer", "cook", "researcher")}
        self.assertTrue(_push(world, "raul").ok)
        pushed = {job_id: world.work.expected(world, raul, jobs[job_id]).pace for job_id in before}
        self.assertEqual(pushed["farmer"], before["farmer"] * world.registries.rush.pace)
        self.assertEqual((pushed["cook"], pushed["researcher"]), (before["cook"], before["researcher"]))

    def test_pushed_more_is_made_in_the_same_shift_and_it_takes_more_out_of_them(self) -> None:
        came = {}
        for pushed in (False, True):
            world = _settled()
            _risking(world, risk=0.0)
            _only(world, "raul")
            raul = world.residents["raul"]
            if pushed:
                self.assertTrue(_push(world, "raul").ok)
            _run(world, 5 * 60, spared=("raul",))
            came[pushed] = (_made(world, "food", "farmer"), raul.needs.tiredness, raul.needs.stress)
        (plain_made, plain_tired, plain_frayed), (made, tired, frayed) = came[False], came[True]
        self.assertGreater(plain_made, 8)
        self.assertGreaterEqual(made, plain_made * 1.3)
        self.assertGreater(tired - plain_tired, 10, "about twice as tired as the morning leaves anybody")
        self.assertGreater(frayed, plain_frayed + 5)

    def test_leaving_the_post_or_taking_another_ends_it(self) -> None:
        for kind, target in ((f"{TASK}:leave_job", None), (f"{TASK}:take_job", "water_carrier")):
            with self.subTest(kind=kind):
                world = _settled()
                _push(world, "raul")
                raul = world.residents["raul"]
                self.assertTrue(world.rush.pushed(world, raul))
                # Said after it, it waits its turn. Said in its place, it is done.
                world.apply_command(AffectCommand("raul", f"{TASK}:stop", None))
                self.assertTrue(world.apply_command(AffectCommand("raul", kind, target)).ok)
                self.assertEqual(raul.pushing_until, 0)


class MishapTests(unittest.TestCase):
    def _pushed_at_post(self, *mishaps: str, resident_id: str = "raul", hour: int = 8) -> SimulationWorld:
        world = _settled(hour=hour)
        _to_post(world, resident_id)
        _risking(world, *mishaps)
        self.assertTrue(_push(world, resident_id).ok)
        return world

    def _accidents(self, world: SimulationWorld) -> list:
        return [event for event in world.events.drain() if event.event_type == ACCIDENT_EVENT]

    def test_whoever_works_may_be_hurt_and_trusts_the_player_the_less_for_it(self) -> None:
        world = self._pushed_at_post(HURT)
        raul = world.residents["raul"]
        world.events.drain()
        self.assertTrue(_run(world, 60, lambda: bool(raul.injuries)))
        accident = self._accidents(world)
        self.assertEqual([event.data["mishap"] for event in accident], [HURT])
        self.assertIn("Raúl se hace daño apretando en su puesto: Huerto", accident[0].text)
        self.assertIn(raul.injuries[0].kind, world.registries.rush.mishaps[HURT].injuries)
        self.assertLess(raul.health, 100)
        self.assertFalse(world.rush.pushed(world, raul), "it ends the push")
        self.assertEqual(world.politics.influence.standing(world, raul).trust, 50.0 + world.registries.rush.trust)
        self.assertTrue(any("accident" in memory.tags for memory in world.memories.of("raul")))
        _run(world, 120)
        self.assertEqual(_types(world).count(ACCIDENT_EVENT), 1, "once: they are no longer pushed")

    def test_nobody_dies_of_having_been_pushed(self) -> None:
        for seed in (7, 11, 23, 31):
            with self.subTest(seed=seed):
                world = _settled(seed=seed)
                _to_post(world, "raul")
                _risking(world, HURT)
                raul = world.residents["raul"]
                raul.injuries.append(Injury("bruise", 100.0 - LEAST_HEALTH - 3.0))
                raul.pushing_until = world.clock.total_minutes + 120
                world.rush.after_unit(world, raul, world.registries.jobs["farmer"], world.interactables[raul.post_id])
                self.assertIn("raul", world.residents)
                self.assertGreaterEqual(raul.health, LEAST_HEALTH - 1e-6)
                self.assertEqual(world.deaths, [])

    def test_their_tool_may_break(self) -> None:
        world = self._pushed_at_post(TOOL)
        raul = world.residents["raul"]
        hoe = world.work.tool_of(world, raul, world.registries.jobs["farmer"])
        self.assertIsNotNone(hoe)
        world.events.drain()
        self.assertTrue(_run(world, 60, lambda: hoe.broken))
        accident = self._accidents(world)
        self.assertEqual([event.data["mishap"] for event in accident], [TOOL])
        self.assertIn("se le parte una azada", accident[0].text)
        self.assertIn("item_broke", _types(world))
        self.assertFalse(world.rush.pushed(world, raul))
        self.assertEqual(raul.injuries, [])

    def test_with_no_tool_in_hand_there_is_none_to_break(self) -> None:
        world = _settled()
        raul = world.residents["raul"]
        for item in list(raul.inventory.items):
            raul.inventory.remove(item.instance_id)
        _to_post(world, "raul")
        _risking(world, TOOL)
        self.assertTrue(_push(world, "raul").ok)
        _run(world, 90)
        self.assertNotIn(ACCIDENT_EVENT, _types(world))
        self.assertTrue(world.rush.pushed(world, raul), "nothing went wrong, and he goes on")

    def test_what_they_were_making_may_be_lost_and_some_of_what_the_post_held(self) -> None:
        world = _settled(hour=7)
        self.assertTrue(world.staffing.assign(world, world.residents["lucia"], "water_carrier"))
        _to_post(world, "lucia")
        _risking(world, SPOIL)
        lucia, tank = world.residents["lucia"], world.containers["water_tank"]
        self.assertTrue(_push(world, "lucia").ok)
        before = tank.count("water")
        spoil = world.registries.rush.mishaps[SPOIL]
        self.assertGreater(before * spoil.fraction, spoil.most, "a share of it would be more than can be lost at once")
        world.events.drain()
        self.assertTrue(_run(world, 90, lambda: ACCIDENT_EVENT in _types(world)))
        accident = self._accidents(world)
        self.assertEqual((accident[0].data["mishap"], accident[0].data["units"]), (SPOIL, spoil.most))
        self.assertEqual(tank.count("water"), before + 1 - spoil.most)
        self.assertEqual(lucia.work_progress, 0)
        self.assertFalse(world.rush.pushed(world, lucia))
        # It is in the books as lost, and they still come to what there is.
        written = world.accounts.today["water"]
        self.assertEqual((written[f"{MADE}:water_carrier"], written[SPOILED]), (1.0, -float(spoil.most)))
        opening = world.accounts.held[world.accounts.day - 1]["water"]
        self.assertEqual(world.ledger.stock(world)["water"] - opening, sum(written.values()))

    def test_what_is_in_their_hands_is_lost_where_the_post_holds_nothing(self) -> None:
        world = self._pushed_at_post(SPOIL)
        raul = world.residents["raul"]
        world.events.drain()
        self.assertTrue(_run(world, 60, lambda: ACCIDENT_EVENT in _types(world)))
        self.assertEqual(self._accidents(world)[0].data["units"], 1)
        self.assertEqual(raul.inventory.count("vegetables"), 0, "the one he had just grown")

    def test_the_more_tired_the_likelier_and_the_better_at_it_the_less(self) -> None:
        world = _settled()
        raul, job = world.residents["raul"], world.registries.jobs["farmer"]
        rush = world.registries.rush
        self.assertAlmostEqual(world.rush.risk(world, raul, job), rush.risk)
        raul.needs.tiredness = 100.0
        self.assertAlmostEqual(world.rush.risk(world, raul, job), rush.risk * rush.tired_risk)
        raul.needs.tiredness = rush.tired_from
        self.assertAlmostEqual(world.rush.risk(world, raul, job), rush.risk)
        raul.attributes.strength = 10.0
        sure = world.rush.risk(world, raul, job)
        raul.attributes.strength = 1.0
        clumsy = world.rush.risk(world, raul, job)
        self.assertLess(sure, rush.risk)
        self.assertGreater(clumsy, rush.risk)
        raul.attributes.strength = 5.0
        raul.trade["farmer"] = float(world.registries.crafts.levels[-1])
        top = world.registries.crafts.top
        self.assertAlmostEqual(world.rush.risk(world, raul, job), rush.risk * (1 - rush.level_relief * (top - 1)))
        # And so it comes out, over many units turned out.
        accidents = {}
        for strength in (1.0, 10.0):
            trial = _settled(seed=5)
            _risking(trial, HURT, risk=0.3)
            worker = trial.residents["raul"]
            worker.attributes.strength = strength
            count = 0
            for _ in range(400):
                worker.pushing_until = trial.clock.total_minutes + 60
                worker.injuries.clear()
                trial.rush.after_unit(trial, worker, job, trial.interactables[worker.post_id])
                count += bool(worker.injuries)
            accidents[strength] = count
        self.assertGreater(accidents[1.0], accidents[10.0] * 1.5)


class PushDeterminismTests(unittest.TestCase):
    def test_with_nobody_pushed_a_settlement_goes_exactly_as_it_would_without_any_of_it(self) -> None:
        registries = builtin_registries()
        with_it = SimulationWorld.demo_world(seed=11)
        without = SimulationWorld.demo_world(seed=11, registries=replace(registries, rush=RushSettings()))
        for world in (with_it, without):
            world.step(3 * MINUTES_PER_DAY)
        self.assertEqual(with_it.rng.get_state(), without.rng.get_state())
        self.assertEqual(with_it.event_log, without.event_log)
        self.assertNotIn(PUSH_KIND, [option.kind for option in without.affect_options("raul")])

    def test_the_same_push_on_the_same_seed_comes_out_the_same(self) -> None:
        logs = []
        for _ in range(2):
            world = SimulationWorld.demo_world(seed=23)
            _risking(world, risk=0.5)
            world.step(90)
            _push_when_free(world, "ines")
            world.step(MINUTES_PER_DAY)
            logs.append((world.event_log, world.rng.get_state()))
        self.assertEqual(logs[0], logs[1])
        self.assertIn(PUSH_EVENT, [line.split(" | ")[1] for line in logs[0][0]])


class PushSaveTests(unittest.TestCase):
    def setUp(self) -> None:
        self.manager = SaveManager()

    def test_a_pushed_shift_is_saved_and_goes_on_the_same(self) -> None:
        world = SimulationWorld.demo_world(seed=7)
        world.step(60)
        _push_when_free(world, "ines")
        world.step(30)
        data = self.manager.to_data(world)
        ines = next(each for each in data["residents"] if each["id"] == "ines")
        self.assertEqual(ines["pushing_until"], 13 * 60)
        loaded = self.manager.from_data(data)
        self.assertTrue(loaded.rush.pushed(loaded, loaded.residents["ines"]))
        for each in (world, loaded):
            each.step(6 * 60)
        self.assertEqual(self.manager.to_data(loaded), self.manager.to_data(world))

    def test_in_a_save_from_before_nobody_is_pushed(self) -> None:
        world = SimulationWorld.demo_world(seed=7)
        world.step(60)
        _push_when_free(world, "ines")
        data = self.manager.to_data(world)
        for resident in data["residents"]:
            del resident["pushing_until"]
        data["version"] = 39
        loaded = self.manager.from_data(data)
        self.assertEqual(loaded.residents["ines"].pushing_until, 0)
        self.assertFalse(loaded.rush.pushed(loaded, loaded.residents["ines"]))
        loaded.step(MINUTES_PER_DAY)


if __name__ == "__main__":
    unittest.main()
