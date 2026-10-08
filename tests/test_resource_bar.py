"""The bar on top (P58): what there is of each thing, which way it is going, how long it will
last, and how spirits stand."""

import os
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

import pygame

from scenes.hud import TOP_ICON
from simulation.economy.ledger import LedgerState, resource_settings_from_data
from ui.labels import lowest_spirits, settlement_mood
from ui.resource_bar import (
    COIN,
    MOOD,
    NOT_KNOWN,
    PEOPLE,
    RESOURCE,
    TENTATIVE,
    resource_chips,
    resource_words,
    tip_lines,
)

FOOD = {"made:farmer": 42.0, "used:cook": -15.0, "made:cook": 15.0, "eaten": -21.0, "found": 1.7}
WATER = {"made:water_carrier": 2.0, "drunk": -9.0}


class _Shell(unittest.TestCase):
    """The game as it is played, with no window: the settlement that comes ready made, on the map."""

    illustrated = False

    def setUp(self) -> None:
        for variable in ("SDL_VIDEODRIVER", "SDL_AUDIODRIVER"):
            self.addCleanup(self._restore_driver, variable, os.environ.get(variable))
            os.environ[variable] = "dummy"
        from game.game import Game

        self.folder = None
        if self.illustrated:
            keep = tempfile.TemporaryDirectory()
            self.addCleanup(keep.cleanup)
            self.folder = Path(keep.name) / "illustrations"
            self.folder.mkdir()
        self.game = Game(illustrations_dir=self.folder, voices_dir=None, start_in_menu=False)
        self.addCleanup(pygame.quit)
        self.view, self.hud, self.world = self.game.global_view, self.game.global_view.hud, self.game.world

    @staticmethod
    def _restore_driver(variable: str, previous: str | None) -> None:
        if previous is None:
            os.environ.pop(variable, None)
        else:
            os.environ[variable] = previous

    def _written(self, **flows: dict[str, float]) -> None:
        """Have the books say that this is what came in and went out on each of the last two days."""
        self.world.accounts = LedgerState(day=3, days={1: dict(flows), 2: dict(flows)})

    def _chip(self, icon: str):
        self.view.render()
        return next(chip for chip in self.hud.chips if chip.icon == icon)

    def _point(self, position: tuple[int, int]) -> None:
        """Rest the pointer somewhere on the canvas, and draw the frame that follows."""
        self.view.pointer = position
        self.view.update(0.0)
        self.view.render()

    def _leave_water(self, units: int) -> None:
        tank = self.world.containers["water_tank"]
        stack = tank.stack_of("water", None)
        tank.take_units(stack.instance_id, stack.quantity - units)


class ResourceBarTests(_Shell):
    def test_there_is_a_figure_for_people_each_resource_coin_and_spirits(self) -> None:
        self.view.render()
        chips = self.hud.chips
        self.assertEqual(
            [(chip.kind, chip.icon) for chip in chips],
            [
                (PEOPLE, "people"), (RESOURCE, "food"), (RESOURCE, "water"), (RESOURCE, "energy"),
                (RESOURCE, "medicine"), (RESOURCE, "scrap"), (COIN, "coin"), (MOOD, "mood"),
            ],
        )
        self.assertEqual(self._chip("food").figure, str(self.world.ledger.stock(self.world)["food"]))
        self.assertEqual(self._chip("people").figure, f"{len(self.world.residents)}/11")
        # In a row along the bar, none over another, and clear of the buttons at its end.
        self.assertGreaterEqual(chips[0].rect.left, self.hud.counts_left)
        self.assertLessEqual(chips[-1].rect.right, self.hud.counts_right)
        self.assertTrue(all(self.hud.layout.top.contains(chip.rect) for chip in chips))
        for one, other in zip(chips, chips[1:]):
            self.assertLess(one.rect.right, other.rect.left)

    def test_with_too_little_written_a_resource_says_only_what_there_is(self) -> None:
        food = self._chip("food")
        self.assertEqual((food.way, food.pace, food.days), (0, "", ""))
        self.assertEqual([text for text, _ in tip_lines(self.world, food)], [f"Comida: {food.figure}", NOT_KNOWN])

    def test_it_says_which_way_each_is_going_and_by_how_much_a_day(self) -> None:
        self._written(food=FOOD, water=WATER)
        food, water, scrap = self._chip("food"), self._chip("water"), self._chip("scrap")
        self.assertEqual((food.way, food.pace, food.days), (1, "23", ""))
        self.assertEqual((water.way, water.pace), (-1, "7"))
        self.assertEqual((scrap.way, scrap.pace, scrap.days), (0, "", ""), "nothing written of it: it stays as it is")
        # How long it will last is said of what is going down, unless that is a long way off.
        self.assertGreater(water.line.days_left, 30)
        self.assertEqual(water.days, "")
        self._leave_water(70)
        self.assertEqual(self._chip("water").days, "10d")
        self.assertFalse(self._chip("water").line.low)

    def test_what_is_running_low_says_so_whatever_room_there_is(self) -> None:
        self._written(food=FOOD, water=WATER, medicine={"dosed": -0.5})
        self._leave_water(9)
        water = self._chip("water")
        self.assertTrue(water.line.low)
        self.assertEqual((water.way, water.pace, water.days), (-1, "7", "1d"))
        self._leave_water(3)
        self.assertEqual(self._chip("water").days, "<1d")
        # With less room, how long it will last is said only of what is running low.
        left = self.hud.counts_left
        roomy = resource_chips(self.hud.font, self.world, left, self.hud.counts_right, 2, TOP_ICON)
        tight = resource_chips(self.hud.font, self.world, left, roomy[-1].rect.right - 1, 2, TOP_ICON)
        by_icon = {chip.icon: chip for chip in tight}
        medicine = self.world.ledger.stock(self.world)["medicine"]
        self.assertEqual(next(chip for chip in roomy if chip.icon == "medicine").days, f"{medicine * 2}d")
        self.assertEqual((by_icon["medicine"].days, by_icon["water"].days, by_icon["food"].pace), ("", "<1d", "23"))
        # And with less still, only what there is of each.
        bare = resource_chips(self.hud.font, self.world, left, tight[-1].rect.right - 1, 2, TOP_ICON)
        self.assertTrue(all((chip.way, chip.pace, chip.days) == (0, "", "") for chip in bare))
        self.assertEqual([chip.figure for chip in bare], [chip.figure for chip in roomy])

    def test_resting_the_pointer_on_one_says_who_makes_it_and_what_uses_it_up(self) -> None:
        self._written(food=FOOD, water=WATER)
        self.assertIsNone(self.hud.resource_tip())
        food = self._chip("food")
        self._point(food.rect.center)
        rect, lines = self.hud.resource_tip()
        said = [text for text, _ in lines]
        self.assertEqual(said[0], f"Comida: {food.figure}")
        self.assertEqual(
            said[1:],
            ["+42 Huerto", "+15 Cocina", "+1,7 Traído de fuera", "-21 Comido", "-15 Cocina: lo que gasta", "Al día: +23"],
        )
        self.assertTrue(self.hud.layout.map.contains(rect), "it is under the bar, whole on the map")
        self.assertTrue(all(self.hud.font.width(text) <= rect.width for text in said))
        # What is going down says how long it will last, and what is running low says it in red.
        self._leave_water(9)
        lines = tip_lines(self.world, self._chip("water"))
        self.assertEqual(lines[-1], ("A este paso queda para un día", "ember"))
        self._point(self.hud.layout.map.center)
        self.assertIsNone(self.hud.resource_tip())

    def test_a_reading_from_the_first_hours_is_said_to_be_one(self) -> None:
        self.world.step(8 * 60)
        food = self._chip("food")
        self.assertTrue(food.line.known and food.line.tentative)
        self.assertEqual(tip_lines(self.world, food)[-1][0], TENTATIVE)
        self.assertEqual(resource_words(food.line)[1], str(round(abs(food.line.net))) if abs(food.line.net) >= 0.5 else "")

    def test_spirits_are_the_mean_of_everybodys_and_whoever_is_lowest_is_named(self) -> None:
        residents = list(self.world.residents.values())
        for resident in residents:
            resident.mood = 80.0
        self.world.residents["raul"].mood = 20.0
        mean = (80.0 * (len(residents) - 1) + 20.0) / len(residents)
        self.assertAlmostEqual(settlement_mood(self.world), mean)
        self.assertEqual(lowest_spirits(self.world).resident_id, "raul")
        mood = self._chip("mood")
        self.assertAlmostEqual(mood.share, mean / 100.0)
        self.assertEqual(
            [text for text, _ in tip_lines(self.world, mood)],
            [f"Ánimo del asentamiento: {round(mean)} de 100", "Quien peor está: Raúl, 20"],
        )

    def test_a_resource_with_a_picture_the_game_has_not_goes_by_a_plain_one(self) -> None:
        resources = {
            "food": {"name": "Comida", "icon": "food", "category": "food"},
            "drink": {"name": "Bebida", "icon": "tankard", "category": "drink"},
        }
        self.world.registries = replace(self.world.registries, resources=resource_settings_from_data({"resources": resources}))
        with self.assertNoLogs("graphics.assets", level="WARNING"):
            self.view.render()
        self.assertEqual([chip.icon for chip in self.hud.chips if chip.kind == RESOURCE], ["food", "tankard"])
        liquor = sum(
            item.quantity
            for inventory in self.world.containers.values()
            for item in inventory.items
            if item.owner_id is None and self.world.registries.items.resolve(item.definition_id).category == "drink"
        )
        self.assertEqual(self._chip("tankard").figure, str(liquor))

    def test_the_bar_is_drawn_with_nothing_missing(self) -> None:
        self._written(food=FOOD, water=WATER)
        self._leave_water(9)
        self.view.pointer = self._chip("water").rect.center
        with self.assertNoLogs("graphics.assets", level="WARNING"):
            for _ in range(3):
                self.view.update(0.3)
                self.view.render()


class WindowBarTests(ResourceBarTests):
    """The same with a window under the canvas, where the bar is dressed at its resolution."""

    illustrated = True

    def test_the_window_dresses_it(self) -> None:
        self.assertTrue(self.hud.skin.usable)


if __name__ == "__main__":
    unittest.main()
