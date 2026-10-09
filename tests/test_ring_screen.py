"""What is done, on screen (P63): the ring of a thing, what somebody wants over their head and
in their panel, what weighs on them, and what only they can be told, through the real game
without a window."""

import os
import unittest
from unittest.mock import patch

import pygame

from graphics import ui_art
from graphics.icons import icon_path
from scenes.global_view import WISH_ICON
from scenes.hud import PANEL_MOOD_INTENT
from simulation.ai.activity_system import HEALTH, MOOD_WEIGHTS, mood_strains
from simulation.ai.affect import TASK, USE, use_target
from simulation.ai.placing import USE_IT
from simulation.memory.memory import Memory
from simulation.residents.needs import NEED_NAMES, Needs
from simulation.residents.wishes import DO, EAT, HAVE, WITH
from simulation.social.talk import Shown
from simulation.world import SimulationWorld
from ui.affect_wheel import (
    CLOSE_INTENT,
    LOOK_LABEL,
    OWN_MARK,
    SOCIAL,
    WheelState,
    branch_intent,
    person_intent,
    target_intent,
    thing_intent,
    use_icon,
    wheel_view,
)
from ui.labels import NEED_LABELS
from ui.resident_panel import HEALTH_STRAIN, LIFE_TAB, MOOD_TAB, STRAIN_FROM, mood_hitbox, mood_rows, tab_hitbox
from ui.talk_bubble import wish_shown

USE_KIND = f"{TASK}:{USE}"


class RingViewTests(unittest.TestCase):
    """What the ring of a thing shows, with no screen to it."""

    def setUp(self) -> None:
        self.world = SimulationWorld.demo_world()
        self.marta = self.world.residents["marta"]
        self.marta.needs = Needs(hunger=0, thirst=40, tiredness=0, social=0, stress=40)
        self.tank = next(placed for placed in self.world.interactables.values() if placed.kind == "water_tank")

    def test_the_ring_of_a_thing_is_what_they_can_do_with_it_and_a_way_to_what_is_said_of_it(self) -> None:
        world, tank = self.world, self.tank
        view = wheel_view(world, "marta", WheelState(open=True, about="marta", thing=tank.object_id))
        self.assertEqual([item.label for item in view.items], ["Beber", "Lavarse", LOOK_LABEL])
        self.assertEqual(
            [item.intent for item in view.items],
            [
                target_intent(USE_KIND, tank.object_id),
                target_intent(USE_KIND, use_target(tank.object_id, "wash")),
                thing_intent(tank.object_id),
            ],
        )
        self.assertEqual(view.back.intent, CLOSE_INTENT)
        self.assertIn("Marta", view.title)
        for item in view.items:
            self.assertIn(item.icon, ui_art.GLYPHS, item.label)

    def test_only_what_can_be_done_as_things_stand_is_in_it(self) -> None:
        world, tank = self.world, self.tank
        world.containers[tank.object_id].items.clear()
        view = wheel_view(world, "marta", WheelState(open=True, about="marta", thing=tank.object_id))
        labels = [item.label for item in view.items]
        self.assertNotIn("Beber", labels, "there is nothing in it to drink")
        self.assertEqual(labels[-1], LOOK_LABEL)

    def test_each_thing_to_do_goes_by_an_icon_of_what_it_does(self) -> None:
        world = self.world
        bed = next(placed for placed in world.interactables.values() if placed.kind == "bed")
        self.assertEqual(use_icon(world, bed.object_id, None), "moon")
        self.assertEqual(use_icon(world, bed.object_id, "lie_down"), "leisure")
        self.assertEqual(use_icon(world, self.tank.object_id, None), "water")
        self.assertEqual(use_icon(world, "pantry_1", None), "food")
        self.assertEqual(use_icon(world, "nothing", None), "work")

    def test_what_only_somebody_can_be_told_is_marked_as_theirs_and_says_why(self) -> None:
        world = self.world
        world.relationships.clear()
        state = WheelState(open=True, about="raul", branch=SOCIAL, person="marta")
        items = {item.label: item for item in wheel_view(world, "raul", state).items}
        self.assertEqual(items["Intimidar"].mark, OWN_MARK)
        self.assertIn("solo por ser Matón", items["Intimidar"].hint)
        self.assertEqual(items["Echar la bronca"].mark, OWN_MARK)
        self.assertIsNone(items["Charlar"].mark)
        self.assertNotIn("solo por ser", items["Charlar"].hint)
        self.assertIn(OWN_MARK, ui_art.GLYPHS)
        self.assertIn(OWN_MARK, ui_art.HUES)


class MoodRowsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.world = SimulationWorld.demo_world()
        self.marta = self.world.residents["marta"]
        self.marta.needs = Needs(hunger=0, thirst=0, tiredness=0, social=0, stress=0, boredom=0)

    def test_what_weighs_on_their_spirits_is_what_their_mood_goes_by(self) -> None:
        world, marta = self.world, self.marta
        self.assertEqual(set(mood_strains(marta)), {*NEED_NAMES, HEALTH})
        self.assertEqual(set(MOOD_WEIGHTS), set(NEED_NAMES))
        self.assertEqual(sum(mood_strains(marta).values()), 0.0)
        marta.needs.stress, marta.needs.hunger = 50.0, 25.0
        strains = mood_strains(marta)
        self.assertEqual((strains["stress"], strains["hunger"]), (50.0 * MOOD_WEIGHTS["stress"], 25.0 * MOOD_WEIGHTS["hunger"]))
        marta.mood = 60.0
        before = marta.mood
        world.activities._settle_mood(marta)
        self.assertLess(marta.mood, before, "and it is that that pulls their mood down")

    def test_the_heaviest_first_and_only_what_is_worth_telling(self) -> None:
        world, marta = self.world, self.marta
        wants, weighs, behind = mood_rows(world, marta)
        self.assertEqual((wants, weighs), ([], []))
        marta.needs.stress, marta.needs.hunger, marta.needs.thirst = 50.0, 25.0, 5.0
        _wants, weighs, _behind = mood_rows(world, marta)
        self.assertEqual(weighs, [(NEED_LABELS["stress"], 12), (NEED_LABELS["hunger"], 4)])
        self.assertLess(5.0 * MOOD_WEIGHTS["thirst"], STRAIN_FROM, "a little thirst is not worth a line")
        world.health.hurt(world, marta, 40.0, "cut", "una prueba")
        names = [name for name, _points in mood_rows(world, marta)[1]]
        self.assertIn(HEALTH_STRAIN, names)

    def test_what_they_want_and_what_they_carry_with_them(self) -> None:
        world, marta = self.world, self.marta
        world.wishes.make(world, marta, EAT, "stew")
        now = world.clock.total_minutes
        for text, value in (("Charlé con Vera.", 0.3), ("Vi llover.", 0.0), ("Me dije de todo con Raúl.", -0.5)):
            world.memories.remember("marta", Memory(text, 20.0, value, [], [], now))
        wants, _weighs, behind = mood_rows(world, marta)
        self.assertEqual(wants, ["Marta tiene antojo de un guiso caliente"])
        mine = [(text, lifted) for text, lifted in behind if text in ("Charlé con Vera.", "Vi llover.", "Me dije de todo con Raúl.")]
        self.assertEqual(mine, [("Me dije de todo con Raúl.", False), ("Charlé con Vera.", True)], "the latest first, and nothing that left no mark")


class WishShownTests(unittest.TestCase):
    def test_a_wish_is_seen_as_the_thing_the_face_or_the_words(self) -> None:
        world = SimulationWorld.demo_world()
        marta = world.residents["marta"]
        self.assertEqual(wish_shown(world, world.wishes.make(world, marta, EAT, "stew")), Shown(item_id="stew"))
        self.assertEqual(wish_shown(world, world.wishes.make(world, marta, HAVE, "old_radio")), Shown(item_id="old_radio"))
        self.assertEqual(wish_shown(world, world.wishes.make(world, marta, WITH, "vera")), Shown(face_id="vera"))
        self.assertEqual(wish_shown(world, world.wishes.make(world, marta, DO, "stroll")), Shown(text="pasear"))


class RingScreenTests(unittest.TestCase):
    """Through the real game without a window."""

    def setUp(self) -> None:
        for variable in ("SDL_VIDEODRIVER", "SDL_AUDIODRIVER"):
            self.addCleanup(self._restore_driver, variable, os.environ.get(variable))
            os.environ[variable] = "dummy"
        from game.game import Game

        self.game = Game(illustrations_dir=None, voices_dir=None, start_in_menu=False)
        self.addCleanup(pygame.quit)
        self.view = self.game.global_view
        self.hud = self.view.hud
        self.wheel = self.hud.wheel
        self.world = self.game.world
        self.world.relationships.clear()
        for resident in self.world.residents.values():
            resident.needs = Needs(hunger=0, thirst=40, tiredness=0, social=0, stress=40)
        self.tank = next(placed for placed in self.world.interactables.values() if placed.kind == "water_tank")

    @staticmethod
    def _restore_driver(variable: str, previous: str | None) -> None:
        if previous is None:
            os.environ.pop(variable, None)
        else:
            os.environ[variable] = previous

    def _frame(self) -> None:
        self.view.update(0.0)
        self.view.render()

    def _entries(self) -> dict:
        return {entry.intent: entry for entry in self.hud.wheel_entries()}

    def _beside(self, resident_id: str, placed) -> tuple[int, int]:
        """Stand somebody by a thing with the view on them, and say where the thing is on screen."""
        resident = self.world.residents[resident_id]
        resident.x, resident.y = placed.x + 1, placed.y + 2
        self.view.centre_on_resident(resident_id)
        self.view.following = None
        self._frame()
        return self.view.use_hitboxes[placed.object_id].center

    def test_everything_there_is_something_to_do_with_can_be_clicked(self) -> None:
        self._beside("marta", self.tank)
        usable = {
            object_id
            for object_id, placed in self.world.interactables.items()
            if self.world.definition_of(placed).uses
        }
        self.assertTrue(set(self.view.use_hitboxes) <= usable)
        self.assertIn(self.tank.object_id, self.view.use_hitboxes)

    def test_with_nobody_selected_a_click_on_a_thing_shows_what_there_is_to_say_of_it(self) -> None:
        where = self._beside("marta", self.tank)
        self.hud.select_resident(None)
        self.view.click(where)
        self._frame()
        self.assertFalse(self.wheel.open)
        self.assertEqual(self.hud.selected_object or self.hud.selected_container, self.tank.object_id)

    def test_with_somebody_selected_it_opens_the_ring_of_what_they_can_do_with_it(self) -> None:
        where = self._beside("marta", self.tank)
        self.hud.select_resident("marta")
        self.view.click(where)
        self._frame()
        self.assertTrue(self.wheel.open)
        self.assertEqual((self.wheel.about, self.wheel.thing), ("marta", self.tank.object_id))
        self.assertEqual(self.hud.selected_id, "marta", "she is still who is looked at")
        entries = self._entries()
        wash = target_intent(USE_KIND, use_target(self.tank.object_id, "wash"))
        self.assertIn(wash, entries)
        self.assertIn(thing_intent(self.tank.object_id), entries)
        # Picked, it is an order like any other, and the ring shuts.
        self.view.click(entries[wash].rect.center)
        self._frame()
        self.assertFalse(self.wheel.open)
        marta = self.world.residents["marta"]
        for _ in range(30):
            self.world.step(1)
            marta.needs = Needs(hunger=0, thirst=40, tiredness=0, social=0, stress=40)
            if marta.activity is not None and marta.activity.action == "wash":
                break
        self.assertEqual(marta.activity.action, "wash")
        self.assertTrue(marta.activity.ordered)

    def test_from_the_ring_there_is_a_way_to_what_is_said_of_the_thing(self) -> None:
        where = self._beside("marta", self.tank)
        self.hud.select_resident("marta")
        self.view.click(where)
        self._frame()
        self.view.click(self._entries()[thing_intent(self.tank.object_id)].rect.center)
        self._frame()
        self.assertFalse(self.wheel.open)
        self.assertEqual(self.hud.selected_object or self.hud.selected_container, self.tank.object_id)

    def test_nothing_they_could_do_with_it_and_the_click_is_what_it_always_was(self) -> None:
        where = self._beside("marta", self.tank)
        self.hud.select_resident("marta")
        with patch.object(type(self.world.affect), "things_to_do", lambda *_: []):
            self.view.click(where)
            self._frame()
        self.assertFalse(self.wheel.open)

    def test_put_down_by_a_thing_that_is_for_nothing_in_particular_it_is_asked_what(self) -> None:
        marta = self.world.residents["marta"]
        table = next(placed for placed in self.world.interactables.values() if placed.kind == "table")
        self._beside("marta", table)
        self.hud.select_resident(None)
        result = self.world.placing.put(self.world, "marta", object_id=table.object_id, do=USE_IT)
        self.assertEqual(result.thing_id, table.object_id)
        self.assertIsNone(marta.doing)
        self.hud.select_resident("marta")
        self._frame()
        self.assertTrue(self.view._ring_of(result.thing_id))
        self.assertEqual(self.wheel.thing, table.object_id)

    def test_put_down_on_a_thing_with_something_it_is_for_they_do_that_and_nothing_is_asked(self) -> None:
        marta = self.world.residents["marta"]
        self._beside("marta", self.tank)
        result = self.world.placing.put(self.world, "marta", object_id=self.tank.object_id, do=USE_IT)
        self.assertEqual((result.ok, result.thing_id), (True, None))
        self.assertIsNotNone(marta.doing)

    def test_whoever_wants_something_has_it_over_their_head(self) -> None:
        world = self.world
        marta = world.residents["marta"]
        self.assertTrue(self.view.assets.image(icon_path(WISH_ICON)).get_width() > 0)
        world.wishes.make(world, marta, EAT, "stew")
        self.hud.select_resident(None)
        self.view.centre_on_resident("marta")
        self.view.following = None
        self._frame()
        self.assertIn("marta", self.view.hitboxes)
        self.hud.select_resident("marta")
        with self.assertNoLogs("graphics.assets", level="WARNING"):
            self._frame()

    def test_the_name_of_their_mood_turns_the_panel_to_what_weighs_on_them(self) -> None:
        world = self.world
        marta = world.residents["marta"]
        world.wishes.make(world, marta, EAT, "stew")
        world.memories.remember("marta", Memory("Me dije de todo con Raúl.", 20.0, -0.5, [], [], world.clock.total_minutes))
        self.hud.select_resident("marta")
        self._frame()
        panel = self.hud.layout.panel
        self.assertEqual(self.hud.click(mood_hitbox(panel).center), PANEL_MOOD_INTENT)
        self.view.click(mood_hitbox(panel).center)
        self.assertEqual(self.hud.panel_tab, MOOD_TAB)
        with self.assertNoLogs("graphics.assets", level="WARNING"):
            self._frame()
        self.view.click(mood_hitbox(panel).center)
        self.assertEqual(self.hud.panel_tab, LIFE_TAB, "and back")
        self.view.click(mood_hitbox(panel).center)
        self.view.click(tab_hitbox(panel).center)
        self.assertEqual(self.hud.panel_tab, LIFE_TAB, "or by the way back that every face of it has")

    def test_what_only_they_can_be_told_is_marked_in_the_wheel(self) -> None:
        self.hud.select_resident("raul")
        self.view._toggle_affect()
        self._frame()
        self.view.click(self._entries()[branch_intent(SOCIAL)].rect.center)
        self._frame()
        self.view.click(self._entries()[person_intent("marta")].rect.center)
        self._frame()
        marks = {entry.item.label: entry.item.mark for entry in self.hud.wheel_entries()}
        self.assertEqual(marks["Intimidar"], OWN_MARK)
        self.assertIsNone(marks["Charlar"])


if __name__ == "__main__":
    unittest.main()
