import os
import unittest

import pygame

from graphics.palette import PALETTE
from simulation.residents.activity import Activity
from simulation.residents.needs import Needs
from simulation.work.expedition import Expedition
from simulation.work.salvage import Salvage
from simulation.world import SimulationWorld
from ui.task_bar import BAR_SIZE, SMALL_BAR_SIZE, draw_task_bar, task_bar_rect, task_progress


def _settled() -> SimulationWorld:
    world = SimulationWorld.demo_world()
    world.relationships.clear()
    for resident in world.residents.values():
        resident.needs = Needs(hunger=0, tiredness=0, social=0, stress=0)
        resident.day_off = None
    return world


class TaskProgressTests(unittest.TestCase):
    def test_a_shift_is_as_far_along_as_the_hours_of_it_that_have_gone_by(self) -> None:
        world = _settled()
        raul = world.residents["raul"]
        # Raúl works the garden from eight to one, and from three to six.
        raul.activity = Activity("work", raul.post_id, minutes_left=300, using=True)
        for hour, minute, done in ((8, 0, 0.0), (10, 30, 0.5), (12, 45, 0.95), (15, 0, 0.0), (16, 30, 0.5)):
            world.clock.hour, world.clock.minute = hour, minute
            self.assertAlmostEqual(task_progress(world, raul), done, places=2, msg=(hour, minute))
        world.clock.hour, world.clock.minute = 14, 0
        self.assertIsNone(task_progress(world, raul), "between shifts there is nothing to be along with")

    def test_leaving_the_post_and_coming_back_does_not_start_it_again(self) -> None:
        world = _settled()
        raul = world.residents["raul"]
        world.clock.hour, world.clock.minute = 11, 0
        raul.activity = Activity("work", raul.post_id, minutes_left=120, using=True)
        before = task_progress(world, raul)
        raul.activity = Activity("work", raul.post_id, minutes_left=120, using=True)
        self.assertEqual(task_progress(world, raul), before)
        self.assertAlmostEqual(before, 0.6, places=2)

    def test_a_longer_day_by_law_is_a_longer_bar(self) -> None:
        world = _settled()
        world.politics.leadership.establish(world, "strong_mayor")
        raul = world.residents["raul"]
        raul.activity = Activity("work", raul.post_id, minutes_left=60, using=True)
        world.clock.hour, world.clock.minute = 16, 30
        usual = task_progress(world, raul)
        world.politics.laws.enact(world, "long_hours", 2)
        self.assertLess(task_progress(world, raul), usual)

    def test_the_use_of_a_thing_is_as_far_along_as_the_time_it_takes(self) -> None:
        world = _settled()
        ines = world.residents["ines"]
        pot = world.registries.interactables.get("cooking_pot").use
        ines.activity = Activity("eat", "cooking_pot", minutes_left=pot.minutes, using=True)
        self.assertEqual(task_progress(world, ines), 0.0)
        ines.activity.minutes_left = pot.minutes // 4
        self.assertAlmostEqual(task_progress(world, ines), 0.75, places=2)
        ines.activity.minutes_left = 0
        self.assertEqual(task_progress(world, ines), 1.0)

    def test_a_site_and_something_being_taken_apart_say_it_themselves(self) -> None:
        world = _settled()
        paco = world.residents["paco"]
        site = world.construction.lay(world, "object", "crop_bed", (22, 12), "paco")
        rule = world.construction.rule_of(world, site)
        paco.activity = Activity("build", site.site_id, minutes_left=90, using=True)
        self.assertEqual(task_progress(world, paco), 0.0)
        site.progress = rule.minutes / 2
        self.assertAlmostEqual(task_progress(world, paco), world.construction.fraction_done(world, site))
        self.assertGreater(task_progress(world, paco), 0.0)
        wreck = world.registries.interactables.get("wreck").salvage
        world.salvage["wreck_yard"] = Salvage("wreck_yard", "paco", wreck.minutes / 4)
        paco.activity = Activity("salvage", "wreck_yard", minutes_left=90, using=True)
        self.assertAlmostEqual(task_progress(world, paco), 0.25)
        world.salvage.clear()
        self.assertIsNone(task_progress(world, paco))

    def test_whoever_is_at_no_task_has_none(self) -> None:
        world = _settled()
        vera = world.residents["vera"]
        bed = next(object_id for object_id, placed in world.interactables.items() if placed.kind == "bed")
        world.clock.hour = 10
        for activity in (
            None,
            Activity("wander", minutes_left=20, using=True),
            Activity("chat", minutes_left=20, using=True, partner_id="paco"),
            Activity("sleep", bed, minutes_left=300, using=True),
            Activity("work", vera.post_id, path=[(1, 1)], minutes_left=0),
            Activity("eat", "cooking_pot", path=[(1, 1)], minutes_left=20),
            Activity("heed", minutes_left=20, using=True),
            Activity("await_material", "site_9", minutes_left=20, using=True),
        ):
            vera.activity = activity
            self.assertIsNone(task_progress(world, vera), activity)
        vera.activity = Activity("work", vera.post_id, minutes_left=60, using=True)
        self.assertIsNotNone(task_progress(world, vera))
        vera.expedition = Expedition(returns_at=10**9, finds=0, danger=0.0)
        self.assertIsNone(task_progress(world, vera), "nor whoever is out of the settlement")

    def test_it_changes_nothing(self) -> None:
        world = _settled()
        world.step(180)
        state = world.rng.get_state()
        log = len(world.event_log)
        for resident in world.residents.values():
            task_progress(world, resident)
        self.assertEqual((world.rng.get_state(), len(world.event_log)), (state, log))


class TaskBarTests(unittest.TestCase):
    def test_the_bar_fills_from_the_left_by_how_far_along_it_is(self) -> None:
        pygame.init()
        self.addCleanup(pygame.quit)
        canvas = pygame.Surface((40, 20))
        rect = task_bar_rect((20, 12))
        self.assertEqual(rect.size, BAR_SIZE)
        self.assertEqual((rect.centerx, rect.bottom), (20, 11), "centred, just over the point given")
        self.assertLess(task_bar_rect((20, 12), small=True).width, rect.width)
        self.assertEqual(task_bar_rect((20, 12), small=True).size, SMALL_BAR_SIZE)
        full, empty = tuple(PALETTE["lichen"]), tuple(PALETTE["shadow"])
        for fraction, filled in ((0.0, 0), (0.5, 8), (1.0, 16), (3.0, 16), (-1.0, 0)):
            canvas.fill((0, 0, 0))
            draw_task_bar(canvas, rect, fraction)
            row = [tuple(canvas.get_at((rect.x + x, rect.y)))[:3] for x in range(rect.width)]
            self.assertEqual(row, [full[:3]] * filled + [empty[:3]] * (rect.width - filled), fraction)


class TaskBarScreenTests(unittest.TestCase):
    def setUp(self) -> None:
        for variable in ("SDL_VIDEODRIVER", "SDL_AUDIODRIVER"):
            self.addCleanup(self._restore_driver, variable, os.environ.get(variable))
            os.environ[variable] = "dummy"
        from game.game import Game

        self.game = Game(illustrations_dir=None, voices_dir=None, start_in_menu=False, sounds_dir=None)
        self.addCleanup(pygame.quit)
        self.view, self.world = self.game.global_view, self.game.world
        for resident in self.world.residents.values():
            resident.day_off = None

    @staticmethod
    def _restore_driver(variable: str, previous: str | None) -> None:
        if previous is None:
            os.environ.pop(variable, None)
        else:
            os.environ[variable] = previous

    def _show(self, resident_id: str) -> None:
        self.view.following = None
        self.view.centre_on(self.world.residents[resident_id].tile)
        self.view.update(0.0)
        self.view.render()

    def test_whoever_is_at_a_task_in_view_has_a_bar_over_their_head(self) -> None:
        self.world.step(150)
        raul = self.world.residents["raul"]
        self.assertTrue(self.world.work.on_duty(self.world, raul))
        self._show("raul")
        bar = self.view.task_bars["raul"]
        self.assertTrue(self.view.viewport.contains(bar))
        body = self.view.hitboxes["raul"]
        self.assertLessEqual(bar.bottom, body.top + 4, "over the head, not across the body")
        self.assertLess(abs(bar.centerx - body.centerx), 4)
        done = task_progress(self.world, raul)
        filled = round(bar.width * done)
        self.assertGreater(filled, 0)
        self.assertEqual(tuple(self.view.canvas.get_at((bar.x, bar.y)))[:3], tuple(PALETTE["lichen"])[:3])
        if filled < bar.width:
            self.assertEqual(tuple(self.view.canvas.get_at((bar.right - 1, bar.y)))[:3], tuple(PALETTE["shadow"])[:3])

    def test_whoever_is_at_none_has_no_bar_and_one_that_was_there_goes(self) -> None:
        self.world.step(150)
        self._show("raul")
        self.assertIn("raul", self.view.task_bars)
        raul = self.world.residents["raul"]
        raul.activity = Activity("wander", minutes_left=30, using=True)
        self._show("raul")
        self.assertNotIn("raul", self.view.task_bars)
        for resident_id in self.view.task_bars:
            self.assertIsNotNone(task_progress(self.world, self.world.residents[resident_id]), resident_id)

    def test_from_afar_the_bar_is_smaller(self) -> None:
        self.world.step(150)
        self._show("raul")
        self.assertEqual(self.view.task_bars["raul"].size, BAR_SIZE)
        self.view.set_zoom(0)
        self.assertTrue(self.view.overview)
        self._show("raul")
        self.assertEqual(self.view.task_bars["raul"].size, SMALL_BAR_SIZE)


if __name__ == "__main__":
    unittest.main()
