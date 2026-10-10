import os
import unittest

import pygame

from scenes.expedition_view import FIGHT_INTENT
from scenes.fight_arena import AIMING, CHOOSING, FIGHTING, KO_SECONDS, OVER, POUND_CLIP, FightArena
from scenes.fight_look import Look
from settings import SCALE
from simulation.combat.raid_system import RAID_OVER_EVENT
from simulation.combat.rules import BOTH, GUN, HAND, HIT, SEVERED, Event
from simulation.work.expedition import FIGHT, Raid
from simulation.world import SimulationWorld


def _send_out(world: SimulationWorld, resident_id: str = "sergio"):
    out = world.residents[resident_id]
    for _ in range(240):
        if out.away:
            return out
        world.step(1)
    raise AssertionError("the scavenger never set out")


def _types(world: SimulationWorld, since: int = 0) -> list[str]:
    return [line.split(" | ")[1] for line in world.event_log[since:]]


class _Shell(unittest.TestCase):
    """The real game shell without a window, with the scavenger out and raiders in their way."""

    foes = [["thug", 1]]
    carries: tuple[str, ...] = ()

    def setUp(self) -> None:
        for variable in ("SDL_VIDEODRIVER", "SDL_AUDIODRIVER"):
            self.addCleanup(self._restore_driver, variable, os.environ.get(variable))
            os.environ[variable] = "dummy"
        from game.game import Game

        self.game = Game(illustrations_dir=None, voices_dir=None, start_in_menu=False)
        self.addCleanup(pygame.quit)
        self.view, self.world = self.game.global_view, self.game.world
        self.trips = self.view.expedition
        self.sergio = _send_out(self.world)
        self.sergio.expedition.raids_at = []
        for item_id in self.carries:
            self.world.stock(self.sergio.inventory, item_id, 1, "sergio")
        self.world.events.drain()

    @staticmethod
    def _restore_driver(variable: str, previous: str | None) -> None:
        if previous is None:
            os.environ.pop(variable, None)
        else:
            os.environ[variable] = previous

    def _blows(self) -> None:
        """Raiders are in their way, and it has come to blows."""
        trip = self.sergio.expedition
        trip.raid = Raid("forest", self.world.clock.total_minutes, [list(foe) for foe in self.foes])
        self.world.raids.choose(self.world, self.sergio, FIGHT)
        self.assertTrue(self.world.raids.waiting(self.world, "sergio"))

    def _watch(self) -> None:
        self.view.render()
        self.view.click(self.view.away_boxes["sergio"].center)
        self.assertEqual(self.view.outside, "sergio")

    def _frames(self, count: int = 30, seconds: float = 1 / 60) -> None:
        for _ in range(count):
            self.view.update(seconds)
        self.view.render()

    def _to_canvas(self, point: tuple[float, float]) -> tuple[int, int]:
        viewport = self.view.viewport
        return (viewport.x + round(point[0] / SCALE), viewport.y + round(point[1] / SCALE))


class FightScreenTests(_Shell):
    def test_nobody_watching_there_is_no_fight_on_screen_and_the_walk_goes_on_as_ever(self) -> None:
        self._watch()
        self._frames()
        self.assertIsNone(self.trips.arena)
        self.assertFalse(self.trips.stopped(self.sergio))
        self.assertFalse(self.trips.key(pygame.K_SPACE))

    def test_they_stand_where_they_are_with_raiders_in_their_way(self) -> None:
        self._watch()
        self.sergio.expedition.raid = Raid("forest", self.world.clock.total_minutes, [["thug", 1]])
        self.assertTrue(self.trips.stopped(self.sergio))
        gone = self.trips.travelled
        self._frames()
        self.assertEqual(self.trips.travelled, gone)
        self.assertIsNone(self.trips.arena, "it has not come to blows yet")

    def test_come_to_blows_the_fight_takes_the_place_of_the_walk_and_the_settlement_waits(self) -> None:
        self._blows()
        self._watch()
        self._frames(2)
        arena = self.trips.arena
        self.assertIsInstance(arena, FightArena)
        self.assertEqual(arena.state, FIGHTING, "with one thing to fight with, nothing is asked")
        self.assertIn("sergio", self.world.raids.live)
        self.assertEqual(arena.screen.get_size(), self.trips.stage().size)
        self.view.render()
        self.assertLess(self.view.hitboxes["sergio"].height, 30, "the walker is not there to press: only their face in the corner")
        now = self.world.clock.total_minutes
        for _ in range(120):
            self.game.advance_simulation(1 / 30)
            self.view.update(1 / 30)
        self.assertEqual(self.world.clock.total_minutes, now, "a fight being played has its own time")
        self.assertGreater(arena.fight.seconds, 3.0)
        self.view.render()

    def test_it_is_played_to_its_end_and_then_they_walk_on_or_do_not(self) -> None:
        self.world.attributes.give(self.world, self.sergio, {"strength": 9, "constitution": 9})
        self._blows()
        self._watch()
        since = len(self.world.event_log)
        self._frames(2)
        arena = self.trips.arena
        for _ in range(60 * 90):
            self.view.update(1 / 30)
            if self.trips.arena is None:
                break
            if arena.state == OVER and arena.ko_at is not None and arena.time - arena.ko_at < KO_SECONDS * 0.5:
                self.view.render()
        self.assertIsNone(self.trips.arena, "over, it is gone from the screen")
        self.assertIsNotNone(arena.fight.outcome)
        self.assertIn(RAID_OVER_EVENT, _types(self.world, since))
        self.assertEqual(self.world.raids.live, {})
        self.view.update(1 / 30)
        self.view.render()
        now = self.world.clock.total_minutes
        self.game.advance_simulation(2.0)
        self.assertGreater(self.world.clock.total_minutes, now, "and the settlement's time goes on")

    def test_going_back_to_the_map_leaves_it_to_be_fought_out(self) -> None:
        self._blows()
        self._watch()
        self._frames(20)
        arena = self.trips.arena
        self.assertIsNone(arena.fight.outcome)
        self.view.click(self.trips.leave_button.rect.center)
        self.assertIsNone(self.view.outside)
        self.assertIsNone(self.trips.arena)
        self.assertIsNotNone(arena.fight.outcome)
        self.assertEqual(self.world.raids.live, {})

    def test_the_keys_of_the_fight_are_the_fights_and_do_not_stop_the_settlement(self) -> None:
        self._blows()
        self._watch()
        self._frames(2)
        arena = self.trips.arena
        self.assertFalse(self.world.clock.paused)
        arena.fight.crit = 1.0
        self.game.handle_key(pygame.K_SPACE)
        self.assertFalse(self.world.clock.paused, "the space bar starts the mark going, and pauses nothing")
        self.assertEqual(arena.state, AIMING)
        self.game.handle_key(pygame.K_SPACE)
        self.assertEqual(arena.state, FIGHTING)
        self.game.handle_key(pygame.K_a)
        self.assertTrue(arena.fight.hands_off)
        self.assertFalse(self.trips.key(pygame.K_F5), "what is not the fight's is whoever's it was")

    def test_a_press_on_a_raider_says_who_is_hit_and_one_on_its_buttons_presses_them(self) -> None:
        self.foes = [["thug", 1], ["thug", 1]]
        self._blows()
        self._watch()
        self._frames(2)
        arena = self.trips.arena
        fight = arena.fight
        self.assertEqual(len(fight.foes), 2)
        self.assertEqual(self.trips.click(self._to_canvas(arena.box(2).center)), FIGHT_INTENT)
        self.assertEqual(fight.chosen, 1)
        self.view.click(self._to_canvas(arena.box(1).center))
        self.assertEqual(fight.chosen, 0)
        self.assertEqual(self.view.outside, "sergio", "a press on the fight goes nowhere else")
        self.assertTrue({"stance", "shove", "heal", "flee"} <= set(arena.buttons))
        self.assertTrue(all(arena.screen.get_rect().contains(rect) for rect in arena.buttons.values()))
        self.view.click(self._to_canvas(arena.buttons["flee"].center))
        self.assertTrue(arena.fight.outcome is not None or arena.failed_at > 0.0 or arena.fight.hero.wait > 0.0)


class ChoosingTests(_Shell):
    carries = ("baton", "pipe_pistol")

    def test_with_more_than_one_thing_to_fight_with_it_is_asked_which_before_a_blow(self) -> None:
        self._blows()
        self._watch()
        self._frames(2)
        arena = self.trips.arena
        self.assertEqual(arena.state, CHOOSING)
        self.assertTrue({HAND, GUN, BOTH, "fight"} <= set(arena.buttons))
        self._frames(30)
        self.assertEqual(arena.fight.seconds, 0.0, "nothing happens until it is said")
        self.view.click(self._to_canvas(arena.buttons[GUN].center))
        self.assertEqual(arena.fight.stance, GUN)
        self.game.handle_key(pygame.K_TAB)
        self.assertEqual(arena.fight.stance, BOTH)
        self.view.click(self._to_canvas(arena.buttons[HAND].center))
        self.view.render()
        self.view.click(self._to_canvas(arena.buttons["fight"].center))
        self.assertEqual((arena.state, arena.fight.stance), (FIGHTING, HAND))
        self._frames(30)
        self.assertGreater(arena.fight.seconds, 0.0)
        self.assertEqual(arena._rounds(), "6 balas")


class ArenaTests(unittest.TestCase):
    """What is seen of a fight, without the shell round it."""

    def setUp(self) -> None:
        os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
        pygame.init()
        self.addCleanup(pygame.quit)
        pygame.display.set_mode((64, 64))
        from graphics.backdrop import BackdropStore
        from graphics.font import BitmapFont
        from tools.art.font import build as build_font

        self.world = SimulationWorld.demo_world(seed=7)
        self.sergio = self.world.residents["sergio"]
        self.world.expeditions.set_out(self.world, self.sergio, self.world.registries.jobs["scavenger"])
        self.sergio.expedition.raid = Raid("forest", self.world.clock.total_minutes, [["cutter", 2]])
        self.world.raids.choose(self.world, self.sergio, FIGHT)
        sheet = next(iter(build_font().values()))
        self.font = BitmapFont(sheet)
        self.look = Look(None, BackdropStore(None))
        self.arena = FightArena(self.world, self.look, self.font, (1092, 848), "sergio", "forest")

    def test_nothing_is_written_over_it_but_numbers(self) -> None:
        arena = self.arena
        for event in (
            Event(HIT, 0, 1, 7.0, weapon="baton"),
            Event(HIT, 1, 0, 21.0, 3.0, "¡Brutal!", "rusty_knife"),
        ):
            arena._show(event)
        self.assertEqual([word.text for word in arena.words], ["-7", "-21"])
        self.assertTrue(arena.slowing, "a telling blow is seen slowly")
        self.assertFalse(arena.cinema)
        arena.fight.hero.lost.append("hand_left")
        arena._show(Event(SEVERED, 1, 0, said="hand_left"))
        self.assertTrue(arena.cinema, "and a part coming off from nearer, with the bars")
        self.assertEqual(len(arena.bodies[0].stumps()), 1)
        for _ in range(20):
            arena.update(1 / 60)
        self.assertTrue(arena.drops, "blood comes out of where it was")
        picture = arena.draw()
        self.assertEqual(picture.get_size(), (1092, 848))
        self.assertEqual(len(arena.words), 2)

    def test_they_get_down_on_whoever_is_on_the_ground_with_the_games_own_clip(self) -> None:
        arena = self.arena
        self.assertTrue(self.look.has_clip(POUND_CLIP))
        fight = arena.fight
        for fighter in fight.fighters:
            fighter.health = fighter.max_health = 9999.0
        fight.foes[0].at = fight.hero.at + self.world.registries.combat.tuning.reach
        fight.hero.attributes["strength"], fight.foes[0].attributes["strength"] = 10.0, 1.0
        fight._floor(0, 1, 9.0, "fists")
        knelt = 0
        for _ in range(180):
            arena.update(1 / 60)
            if 0 in fight.pins:
                knelt += 1
                self.assertEqual(arena.bodies[0].character.clip, POUND_CLIP)
        self.assertGreater(knelt, 30)
        arena.draw()

    def test_whoever_was_already_without_a_part_stands_there_without_it(self) -> None:
        self.world.raids.leave(self.world, "sergio")
        if "sergio" not in self.world.residents or self.sergio.expedition is None:
            self.skipTest("this one did not come through the first")
        self.sergio.lost_limbs[:] = ["hand_right"]
        self.sergio.expedition.raid = Raid("forest", self.world.clock.total_minutes + 1, [["thug", 1]])
        self.world.raids.choose(self.world, self.sergio, FIGHT)
        if not self.world.raids.waiting(self.world, "sergio"):
            self.skipTest("they got away")
        arena = FightArena(self.world, self.look, self.font, (1092, 848), "sergio", "forest")
        self.assertEqual(arena.fight.hero.lost, ["hand_right"])
        self.assertFalse(arena.bodies[0].character.has("hand_right"))
        self.assertEqual(arena.bodies[0].pieces, [], "it is not lying about: it was lost long since")
        for _ in range(30):
            arena.update(1 / 60)
        self.assertEqual(arena.drops, [], "nor does it bleed")
        arena.draw()


if __name__ == "__main__":
    unittest.main()
