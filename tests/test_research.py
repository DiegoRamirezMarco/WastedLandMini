import json
import os
import tempfile
import unittest
from pathlib import Path

from save.save_manager import SaveManager
from simulation.commands import (
    FoundResidentCommand,
    PlaceObjectCommand,
    ProposeObjectCommand,
    SetResearchCommand,
)
from simulation.registries import DATA_DIR, BuiltInRegistries
from simulation.residents.needs import Needs
from simulation.work.research import (
    BUILD_PACE,
    CLOSED,
    DOSE_MINUTES,
    EXPEDITION_DANGER,
    EXPEDITION_FINDS,
    IN_HAND,
    KNOWN,
    OPEN,
    research_settings_from_data,
)
from simulation.world import SimulationWorld
from world.build import OBJECT_SITE

MINUTES_PER_DAY = 24 * 60
STANDING = ["mechanics", "electricity", "radio", "first_aid", "trade", "still"]


def _keep_content(world: SimulationWorld) -> None:
    for resident in world.residents.values():
        resident.needs = Needs(hunger=0, tiredness=0, social=0, stress=0)


def _run(world: SimulationWorld, minutes: int, until=None) -> bool:
    """Let time pass with nobody wanting for anything. True as soon as `until` holds."""
    for _ in range(minutes):
        world.step(1)
        _keep_content(world)
        if until is not None and until():
            return True
    return False


def _types(world: SimulationWorld) -> list[str]:
    return [line.split(" | ")[1] for line in world.event_log]


def _spot(world: SimulationWorld, kind: str) -> tuple[int, int]:
    for y in range(8, world.tile_map.height - 2):
        for x in range(8, world.tile_map.width - 2):
            if world.urbanism.object_error(world, kind, (x, y)) is None:
                return (x, y)
    raise AssertionError(f"nowhere on the map to put {kind}")


def _studying(seed: int = 7, student: str = "nuria") -> tuple[SimulationWorld, str]:
    """The demo settlement with a desk to study at and somebody at it, and its water seen to.

    Returns the world and the ID of the desk. Nobody has a grudge, so only work drives the day.
    """
    world = SimulationWorld.demo_world(seed=seed)
    world.relationships.clear()
    _keep_content(world)
    # The water is the post everybody is asked to take up first: with it filled nobody is called away.
    world.staffing.assign(world, world.residents["lucia"], "water_carrier")
    desk = world.urbanism.place_object(world, "study_desk", _spot(world, "study_desk")).entity_id
    assert world.staffing.assign(world, world.residents[student], "researcher")
    return world, desk


def _registries_with(file_name: str, change) -> BuiltInRegistries:
    """Registries loaded from a copy of the data folder with one file's contents changed."""
    with tempfile.TemporaryDirectory() as folder:
        root = Path(folder)
        for path in DATA_DIR.rglob("*.json"):
            target = root / path.relative_to(DATA_DIR)
            target.parent.mkdir(parents=True, exist_ok=True)
            data = json.loads(path.read_text(encoding="utf-8"))
            if path.name == file_name:
                change(data)
            target.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        return BuiltInRegistries.load(root)


class SubjectDataTests(unittest.TestCase):
    def test_subjects_are_data_with_what_they_take_and_what_they_open(self) -> None:
        subjects = SimulationWorld.demo_world().registries.research.subjects
        radio = subjects["radio"]
        self.assertEqual((radio.requires, radio.item, radio.count), (("electricity",), "old_radio", 1))
        self.assertEqual(radio.objects, ("radio_set",))
        self.assertEqual(subjects["irrigation"].effects, {"pace:farmer": 1.25})
        self.assertGreater(subjects["electricity"].minutes, 0)

    def test_subjects_that_make_no_sense_are_refused(self) -> None:
        for bad in (
            {"a": {}},
            {"a": {"name": "A", "minutes": 0}},
            {"a": {"name": "A", "requires": ["nothing"]}},
            {"a": {"name": "A", "requires": ["b"]}, "b": {"name": "B", "requires": ["a"]}},
            {"a": {"name": "A", "needs": {"count": 2}}},
            {"a": {"name": "A", "needs": {"item": "scrap", "count": 0}}},
            {"a": {"name": "A", "effects": {"build_pace": 0}}},
        ):
            with self.assertRaises(ValueError, msg=bad):
                research_settings_from_data({"subjects": bad})

    def test_a_subject_about_what_is_not_defined_makes_no_registry(self) -> None:
        def unknown_item(data: dict) -> None:
            data["subjects"]["radio"]["needs"]["item"] = "crystal_ball"

        def unknown_object(data: dict) -> None:
            data["subjects"]["trade"]["opens"]["objects"] = ["stock_exchange"]

        def unknown_effect(data: dict) -> None:
            data["subjects"]["irrigation"]["effects"] = {"pace:wizard": 2.0}

        def desk_that_holds_nothing(data: dict) -> None:
            data["study_desk"]["container"] = False

        for file_name, change in (
            ("research.json", unknown_item),
            ("research.json", unknown_object),
            ("research.json", unknown_effect),
            ("interactables.json", desk_that_holds_nothing),
        ):
            with self.assertRaises(ValueError, msg=change.__name__):
                _registries_with(file_name, change)


class WhatIsKnownTests(unittest.TestCase):
    def test_a_settlement_that_is_running_knows_how_to_make_what_it_has(self) -> None:
        world = SimulationWorld.demo_world()
        self.assertEqual(world.studies.known, STANDING)
        self.assertIsNone(world.studies.subject_id)
        self.assertIsNone(world.construction.not_known(world, OBJECT_SITE, "generator"))
        status = {subject.subject_id: world.research.status(world, subject) for subject in world.research.subjects(world)}
        self.assertEqual({status[each] for each in STANDING}, {KNOWN})
        # What makes things go better is still to be worked out, and what follows from what it knows is open.
        self.assertEqual((status["irrigation"], status["pump"], status["dosage"]), (OPEN, OPEN, OPEN))

    def test_a_new_settlement_knows_nothing_and_can_put_up_only_what_takes_no_knowing(self) -> None:
        world = SimulationWorld.new_settlement()
        self.assertEqual(world.studies.known, [])
        self.assertTrue(world.tutorial.active)
        for kind in ("bed", "crate", "pantry", "water_tank", "crop_bed", "campfire", "handcart", "study_desk"):
            self.assertIsNone(world.construction.not_known(world, OBJECT_SITE, kind), kind)
        # Not even during the opening, when whatever is known is put down for nothing.
        refused = world.apply_command(PlaceObjectCommand("generator", _spot(world, "generator")))
        self.assertFalse(refused.ok)
        self.assertIn("Electricidad", refused.message)
        self.assertIn("Mecánica", world.apply_command(PlaceObjectCommand("workbench", _spot(world, "workbench"))).message)
        self.assertTrue(world.apply_command(PlaceObjectCommand("bed", _spot(world, "bed"))).ok)

        world.apply_command(FoundResidentCommand("Ada", 34, {}, []))
        world.tutorial.step_id = None
        asked = world.apply_command(ProposeObjectCommand("generator", _spot(world, "generator"), "ada"))
        self.assertFalse(asked.ok)
        self.assertIn("Electricidad", asked.message)
        self.assertEqual(world.sites, {})

    def test_what_is_to_be_worked_out_is_the_player_s_to_say_within_what_can_be(self) -> None:
        world = SimulationWorld.new_settlement()
        closed = world.apply_command(SetResearchCommand("electricity"))
        self.assertFalse(closed.ok)
        self.assertIn("Mecánica", closed.message)
        self.assertEqual(world.research.status(world, world.registries.research.subjects["electricity"]), CLOSED)
        self.assertFalse(world.apply_command(SetResearchCommand("alchemy")).ok)

        self.assertTrue(world.apply_command(SetResearchCommand("mechanics")).ok)
        self.assertEqual(world.studies.subject_id, "mechanics")
        self.assertEqual(world.research.status(world, world.registries.research.subjects["mechanics"]), IN_HAND)
        self.assertIn("research_chosen", _types(world))
        # Said again, it is said once.
        world.apply_command(SetResearchCommand("mechanics"))
        self.assertEqual(_types(world).count("research_chosen"), 1)

        self.assertTrue(world.apply_command(SetResearchCommand(None)).ok)
        self.assertIsNone(world.studies.subject_id)
        known = SimulationWorld.demo_world().apply_command(SetResearchCommand("radio"))
        self.assertFalse(known.ok)
        self.assertIn("ya se sabe", known.message)


class StudyTests(unittest.TestCase):
    def test_time_on_shift_at_the_desk_goes_towards_what_is_in_hand_until_it_is_known(self) -> None:
        world, _ = _studying()
        world.apply_command(SetResearchCommand("pump"))
        pump = world.registries.research.subjects["pump"]
        nuria = world.residents["nuria"]
        self.assertEqual(world.research.factor(world, "pace:water_carrier"), 1.0)

        # Her shift is from nine: before it nothing is done.
        _run(world, 50)
        self.assertEqual(world.studies.progress, {})
        _run(world, 180)
        self.assertTrue(world.work.on_duty(world, nuria))
        self.assertGreater(world.studies.progress["pump"], 120)
        self.assertLess(world.research.fraction_done(world, pump), 1.0)

        self.assertTrue(_run(world, 3 * MINUTES_PER_DAY, lambda: world.research.knows(world, "pump")), "never worked out")
        self.assertEqual(world.studies.known[-1], "pump")
        self.assertIsNone(world.studies.subject_id)
        self.assertNotIn("pump", world.studies.progress)
        self.assertEqual(world.research.status(world, pump), KNOWN)
        self.assertTrue(any("Nuria ha averiguado algo: Bomba de agua" in line for line in world.event_log))
        self.assertEqual(world.research.factor(world, "pace:water_carrier"), 1.5)

    def test_what_was_done_on_a_subject_left_for_another_is_kept(self) -> None:
        world, _ = _studying()
        world.apply_command(SetResearchCommand("pump"))
        _run(world, 240)
        done = world.studies.progress["pump"]
        self.assertGreater(done, 0)
        world.apply_command(SetResearchCommand("scaffolding"))
        _run(world, 60)
        self.assertEqual(world.studies.progress["pump"], done)
        self.assertGreater(world.studies.progress["scaffolding"], 0)

    def test_with_nothing_chosen_whoever_holds_the_post_waits_and_the_settlement_is_told_once_a_day(self) -> None:
        world, _ = _studying()
        _run(world, 2 * MINUTES_PER_DAY)
        self.assertEqual(world.studies.progress, {})
        waiting = [line for line in world.event_log if "| research_waiting |" in line]
        self.assertEqual(len(waiting), world.clock.day)
        self.assertIn("elegir", waiting[0])

    def test_nobody_is_told_to_choose_where_nobody_studies(self) -> None:
        world = SimulationWorld.demo_world()
        world.step(MINUTES_PER_DAY)
        self.assertNotIn("research_waiting", _types(world))

    def test_what_a_subject_studies_is_fetched_to_the_desk_and_used_up(self) -> None:
        world, desk = _studying()
        cabinet = world.containers["medicine_cabinet"]
        before = cabinet.count("medicine")
        self.assertGreaterEqual(before, 2)
        world.apply_command(SetResearchCommand("dosage"))

        self.assertTrue(_run(world, MINUTES_PER_DAY, lambda: "dosage" in world.studies.supplied), "never brought")
        self.assertEqual(cabinet.count("medicine"), before - 2)
        self.assertEqual(world.containers[desk].count("medicine"), 0)
        self.assertEqual(world.residents["nuria"].inventory.count("medicine"), 0)
        self.assertTrue(any("Nuria lleva 2 de medicinas a una mesa de estudio" in line for line in world.event_log))
        self.assertGreater(world.studies.progress.get("dosage", 0), 0)

    def test_without_it_nothing_is_done_and_what_is_somebody_s_own_is_left_alone(self) -> None:
        world, desk = _studying()
        world.studies.known.remove("radio")
        # Nobody goes out, so none is brought back, and the one the shop had has been sold.
        del world.residents["sergio"]
        for inventory in world.containers.values():
            for item in [item for item in inventory.items if item.definition_id == "old_radio" and item.owner_id is None]:
                inventory.remove(item.instance_id)
        # The only old radio there is belongs to Marta.
        self.assertEqual(world.containers["crate_dorm"].stack_of("old_radio", "marta").quantity, 1)
        self.assertTrue(world.apply_command(SetResearchCommand("radio")).ok)
        _run(world, 2 * MINUTES_PER_DAY)
        self.assertNotIn("radio", world.studies.progress)
        self.assertEqual(world.containers["crate_dorm"].stack_of("old_radio", "marta").quantity, 1)
        waiting = [line for line in world.event_log if "| research_waiting |" in line]
        self.assertEqual(len(waiting), world.clock.day)
        self.assertIn("radio vieja", waiting[0])

        # One that is nobody's turns up, as from a trip outside, and is taken to be studied.
        world.stock(world.containers["crate_1"], "old_radio", 1, None)
        self.assertTrue(_run(world, MINUTES_PER_DAY, lambda: world.studies.progress.get("radio", 0) > 0))
        self.assertIsNone(world.containers["crate_1"].stack_of("old_radio", None))
        self.assertEqual(world.containers[desk].count("old_radio"), 0)

    def test_what_is_studied_is_taken_from_wherever_it_lies_that_is_nobody_s_the_shop_included(self) -> None:
        world, _ = _studying()
        world.studies.known.remove("radio")
        counter = world.containers["shop_counter"]
        self.assertEqual(counter.count("old_radio"), 1)
        world.apply_command(SetResearchCommand("radio"))
        self.assertTrue(_run(world, MINUTES_PER_DAY, lambda: "radio" in world.studies.supplied))
        self.assertEqual(counter.count("old_radio"), 0)

    def test_working_a_thing_out_lets_it_be_built(self) -> None:
        world, _ = _studying()
        world.studies.known.clear()
        refused = world.apply_command(ProposeObjectCommand("workbench", _spot(world, "workbench"), "marta"))
        self.assertIn("Mecánica", refused.message)
        world.apply_command(SetResearchCommand("mechanics"))
        self.assertTrue(_run(world, 3 * MINUTES_PER_DAY, lambda: world.research.knows(world, "mechanics")))
        agreed = world.apply_command(ProposeObjectCommand("workbench", _spot(world, "workbench"), "marta"))
        self.assertTrue(agreed.ok, agreed.message)
        # And what waited for it can now be chosen.
        self.assertEqual(world.research.status(world, world.registries.research.subjects["electricity"]), OPEN)


class EffectTests(unittest.TestCase):
    def test_what_is_known_multiplies_and_what_is_not_does_nothing(self) -> None:
        world = SimulationWorld.demo_world()
        for effect in (BUILD_PACE, EXPEDITION_DANGER, EXPEDITION_FINDS, DOSE_MINUTES, "pace:farmer", "pace:cook"):
            self.assertEqual(world.research.factor(world, effect), 1.0, effect)
        world.studies.known += ["irrigation", "scaffolding", "safe_routes", "salvage", "dosage"]
        self.assertEqual(world.research.factor(world, "pace:farmer"), 1.25)
        self.assertEqual(world.research.factor(world, "pace:cook"), 1.0)
        self.assertEqual(world.research.factor(world, BUILD_PACE), 1.5)
        self.assertEqual(world.research.factor(world, EXPEDITION_DANGER), 0.6)
        self.assertEqual(world.research.factor(world, EXPEDITION_FINDS), 1.34)
        self.assertEqual(world.research.factor(world, DOSE_MINUTES), 1.5)

    def _garden_yield(self, known: bool) -> int:
        world = SimulationWorld.demo_world()
        world.relationships.clear()
        if known:
            world.studies.known.append("irrigation")
        for resident_id in [each for each in world.residents if each != "raul"]:
            del world.residents[resident_id]
        before = sum(inventory.count("vegetables") for inventory in world.containers.values())
        _run(world, 5 * 60)
        carried = world.residents["raul"].inventory.count("vegetables")
        return sum(inventory.count("vegetables") for inventory in world.containers.values()) + carried - before

    def test_knowing_about_watering_makes_the_garden_give_more(self) -> None:
        plain, watered = self._garden_yield(False), self._garden_yield(True)
        self.assertGreater(plain, 0)
        self.assertGreaterEqual(watered, plain * 1.15)

    def test_scaffolding_makes_a_site_go_up_faster(self) -> None:
        def progress(known: bool) -> float:
            world = SimulationWorld.demo_world()
            world.relationships.clear()
            if known:
                world.studies.known.append("scaffolding")
            for resident_id in [each for each in world.residents if each != "lucia"]:
                del world.residents[resident_id]
            site = world.construction.lay(world, OBJECT_SITE, "crop_bed", _spot(world, "crop_bed"), "lucia")
            _run(world, 30)
            return site.progress

        plain, propped = progress(False), progress(True)
        self.assertGreater(plain, 0)
        self.assertAlmostEqual(propped, plain * 1.5, delta=1.5)

    def test_trips_outside_are_safer_and_bring_more_back(self) -> None:
        def trip(known: list[str]):
            world = SimulationWorld.demo_world(seed=3)
            world.studies.known += known
            sergio = world.residents["sergio"]
            world.expeditions.set_out(world, sergio, world.registries.jobs["scavenger"])
            return sergio.expedition

        plain, wise = trip([]), trip(["safe_routes", "salvage"])
        self.assertAlmostEqual(wise.danger, plain.danger * 0.6)
        self.assertEqual(wise.finds, round(plain.finds * 1.34))
        # Knowing more changes nothing of when they come back, nor of what is rolled after.
        self.assertEqual(wise.returns_at, plain.returns_at)


class SavedResearchTests(unittest.TestCase):
    def test_what_is_known_and_what_is_in_hand_are_saved(self) -> None:
        world, _ = _studying()
        world.apply_command(SetResearchCommand("dosage"))
        self.assertTrue(_run(world, MINUTES_PER_DAY, lambda: world.studies.progress.get("dosage", 0) > 30))
        world.studies.progress["pump"] = 12.5
        manager = SaveManager()
        data = json.loads(json.dumps(manager.to_data(world)))
        loaded = manager.from_data(data)
        self.assertEqual(loaded.studies, world.studies)
        self.assertEqual(loaded.studies.supplied, ["dosage"])
        self.assertEqual(manager.to_data(loaded)["research"], data["research"])
        self.assertTrue(_run(loaded, 3 * MINUTES_PER_DAY, lambda: loaded.research.knows(loaded, "dosage")))

    def test_a_save_from_before_knows_what_it_has_standing_and_a_subject_that_is_gone_is_forgotten(self) -> None:
        manager = SaveManager()
        world, _ = _studying()
        world.apply_command(SetResearchCommand("pump"))
        data = json.loads(json.dumps(manager.to_data(world)))

        older = dict(data, version=24)
        del older["research"]
        before = manager.from_data(older)
        self.assertEqual(before.studies.known, STANDING)
        self.assertIsNone(before.studies.subject_id)

        data["research"] = {
            "subject": "alchemy",
            "known": ["mechanics", "alchemy", "mechanics"],
            "progress": {"alchemy": 5, "pump": 7, "mechanics": 3, "trade": "much"},
            "supplied": ["alchemy", "dosage"],
        }
        tidy = manager.from_data(data).studies
        self.assertEqual((tidy.subject_id, tidy.known, tidy.progress, tidy.supplied), (None, ["mechanics"], {"pump": 7.0}, ["dosage"]))


class LongRunTests(unittest.TestCase):
    def test_three_weeks_of_study_work_things_out_and_cost_nobody_their_life(self) -> None:
        for seed in (7, 11, 23):
            with self.subTest(seed=seed):
                world = SimulationWorld.demo_world(seed=seed)
                world.staffing.assign(world, world.residents["lucia"], "water_carrier")
                world.urbanism.place_object(world, "study_desk", _spot(world, "study_desk"))
                world.staffing.assign(world, world.residents["nuria"], "researcher")
                wanted = ["pump", "scaffolding", "irrigation", "safe_routes"]
                for _ in range(21):
                    if world.studies.subject_id is None:
                        left = [each for each in wanted if not world.research.knows(world, each)]
                        if left:
                            self.assertTrue(world.apply_command(SetResearchCommand(left[0])).ok)
                    world.step(MINUTES_PER_DAY)
                self.assertEqual(world.deaths, [])
                learnt = [each for each in wanted if world.research.knows(world, each)]
                self.assertGreaterEqual(len(learnt), 3, "three weeks of study worked hardly anything out")
                self.assertEqual(_types(world).count("research_finished"), len(learnt))

    def test_the_same_seed_studies_the_same_way(self) -> None:
        def run() -> list[str]:
            world, _ = _studying(seed=5)
            world.apply_command(SetResearchCommand("dosage"))
            world.step(3 * MINUTES_PER_DAY)
            return world.event_log

        self.assertEqual(run(), run())


class ResearchScreenTests(unittest.TestCase):
    def setUp(self) -> None:
        import pygame

        previous_video = os.environ.get("SDL_VIDEODRIVER")
        previous_audio = os.environ.get("SDL_AUDIODRIVER")
        os.environ["SDL_VIDEODRIVER"] = "dummy"
        os.environ["SDL_AUDIODRIVER"] = "dummy"
        self.addCleanup(self._restore, "SDL_VIDEODRIVER", previous_video)
        self.addCleanup(self._restore, "SDL_AUDIODRIVER", previous_audio)
        from game.game import Game

        self.pygame = pygame
        self.game = Game(illustrations_dir=None, voices_dir=None, start_in_menu=False)
        self.addCleanup(pygame.quit)

    @staticmethod
    def _restore(variable: str, previous: str | None) -> None:
        if previous is None:
            os.environ.pop(variable, None)
        else:
            os.environ[variable] = previous

    def _click(self, scene, position: tuple[int, int]) -> None:
        from settings import SCALE

        window = (position[0] * SCALE, position[1] * SCALE)
        scene.handle_event(self.pygame.event.Event(self.pygame.MOUSEBUTTONDOWN, pos=window, button=1))
        scene.handle_event(self.pygame.event.Event(self.pygame.MOUSEBUTTONUP, pos=window, button=1))

    def test_the_menu_opens_what_is_studied_and_a_click_says_what_comes_next(self) -> None:
        from scenes.hud import RESEARCH_INTENT
        from ui.research_board import known_lines, study_intent, subject_rows

        view, world = self.game.global_view, self.game.world
        hud = view.hud
        self.assertIn(RESEARCH_INTENT, [button.intent for button in hud.menu])
        self._click(view, hud.research_button.rect.center)
        self.assertTrue(hud.research_open)
        view.render()
        # What is still to be worked out has a row each. What is known is told in a line or two.
        rows = subject_rows(world)
        self.assertEqual({row.subject_id for row in rows}, set(world.registries.research.subjects) - set(STANDING))
        self.assertEqual({row.status for row in rows}, {OPEN})
        known = " ".join(known_lines(view.font, world, 290))
        self.assertTrue(all(world.registries.research.subjects[each].name in known for each in STANDING))

        button = next(button for button in hud.buttons if button.intent == study_intent("pump"))
        self._click(view, button.rect.center)
        self.assertEqual(world.studies.subject_id, "pump")
        view.render()
        self.assertEqual(subject_rows(world)[0].subject_id, "pump")
        # The one in hand can be put down again, and what is known has no button at all.
        self.assertFalse(any(button.intent == study_intent("radio") for button in hud.buttons))
        stop = next(button for button in hud.buttons if button.intent == study_intent(None))
        self._click(view, stop.rect.center)
        self.assertIsNone(world.studies.subject_id)

        # It shares its corner with the posts, and has a key of its own.
        self._click(view, hud.jobs_button.rect.center)
        self.assertEqual((hud.research_open, hud.jobs_open), (False, True))
        view.handle_event(self.pygame.event.Event(self.pygame.KEYDOWN, key=self.pygame.K_e, unicode="e", mod=0))
        self.assertEqual((hud.research_open, hud.jobs_open), (True, False))

    def test_the_catalogue_lists_what_nobody_knows_how_to_make_and_will_not_hand_it_over(self) -> None:
        from scenes.hud import URBANISM_INTENT
        from scenes.urbanism import NOT_KNOWN_MARK

        world = self.game.world
        world.studies.known.remove("still")
        self.game.global_view._apply(URBANISM_INTENT)
        self.game.sync_scenes()
        editor = self.game.active_scene
        furniture = next(button for button in editor.buttons if button.intent == ("category", "furniture"))
        self._click(editor, furniture.rect.center)
        labels = {button.intent[1]: button.label for button in editor.buttons if button.intent[0] == "catalog"}
        self.assertIn(NOT_KNOWN_MARK, labels["bar"])
        self.assertNotIn(NOT_KNOWN_MARK, labels["bed"])
        self.assertNotIn(NOT_KNOWN_MARK, labels["workbench"])

        bar = next(button for button in editor.buttons if button.intent == ("catalog", "bar"))
        self._click(editor, bar.rect.center)
        self.assertIsNone(editor.catalog_id)
        self.assertIsNone(editor.drag)
        self.assertIn("Alambique", editor.message)
        editor.render()


if __name__ == "__main__":
    unittest.main()
