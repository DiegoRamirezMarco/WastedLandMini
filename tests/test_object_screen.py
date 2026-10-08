"""What stands, on screen (P60): what is said of a thing when it is picked, the board of
current, what is seen over a thing that stands idle, how full the store is in the bar, and a
drawing of its own for what has been made better."""

import os
import tempfile
import unittest
from pathlib import Path

import pygame

from graphics.object_art import object_art_path
from graphics.palette import PALETTE
from scenes.hud import REDRAW_NO_INTENT, REDRAW_YES_INTENT
from simulation.residents.needs import Needs
from ui.labels import rarity_color
from ui.object_marks import BROKEN, NO_CURRENT, OFF, marks_of
from ui.object_panel import STORE_HEADING, redraw_intent, speaks, upgrade_intent
from ui.power_board import POWER_INTENT, SWITCHED_OFF, power_rows, switch_intent
from ui.resource_bar import room_gauge, room_share
from world.build import UPGRADE_SITE


def _dummy(case: unittest.TestCase) -> None:
    for variable in ("SDL_VIDEODRIVER", "SDL_AUDIODRIVER"):
        previous = os.environ.get(variable)
        case.addCleanup(_restore, variable, previous)
        os.environ[variable] = "dummy"


def _restore(variable: str, previous: str | None) -> None:
    if previous is None:
        os.environ.pop(variable, None)
    else:
        os.environ[variable] = previous


class ObjectScreenTests(unittest.TestCase):
    def setUp(self) -> None:
        _dummy(self)
        from game.game import Game

        self.game = Game(illustrations_dir=None, voices_dir=None, start_in_menu=False)
        self.addCleanup(pygame.quit)
        self.view, self.world, self.hud = self.game.global_view, self.game.world, self.game.global_view.hud
        self.world.relationships.clear()
        for resident in self.world.residents.values():
            resident.needs = Needs(hunger=0, thirst=0, tiredness=0, social=0, stress=0)

    def _show(self, object_id: str) -> pygame.Rect | None:
        """Look at a thing from near, with every roof off, and say where it is pressed."""
        placed = self.world.interactables[object_id]
        self.view.roofs_on = False
        self.view.set_zoom(2)
        self.view.centre_on((placed.x + 0.5, placed.y + 0.5))
        self.view.update(0.0)
        self.view.render()
        return self.view.thing_hitboxes.get(object_id)

    def _said(self) -> list[str]:
        view = self.hud.object_view()
        return [line.text for line, _ in view.lines] if view is not None else []

    def _press(self, intent) -> None:
        button = next(button for button in self.hud.buttons if button.intent == intent)
        self.view.click(button.rect.center)

    def _empty_of_fuel(self) -> None:
        fuel = self.world.registries.power.fuel
        for inventory in self.world.containers.values():
            inventory.items[:] = [item for item in inventory.items if item.definition_id != fuel]

    def test_a_press_on_a_thing_with_something_to_say_shows_it_in_the_panel(self) -> None:
        box = self._show("water_tank")
        self.assertFalse(any(rect.collidepoint(box.center) for rect in self.view.hitboxes.values()))
        self.view.click(box.center)
        self.assertEqual((self.hud.selected_object, self.hud.selected_id), ("water_tank", None))
        said = self._said()
        self.assertEqual(said[:2], ["Depósito de agua", "Calidad: común"])
        self.assertIn("Puesto de Agua: libre", said)
        self.assertIn("Estado", said)
        self.assertIn("Corriente: gasta 1. Encendido", said)
        # What it holds is listed under what is said of it, and is still pressed there.
        shown, kept = self.hud.object_view(), self.hud.container_rect()
        self.assertEqual(kept.top, shown.rect.bottom)
        self.assertTrue(self.hud.layout.panel.contains(kept))
        self.view.render()
        self.assertTrue(self.hud.covers(kept.center))
        # A press on bare ground lets go of it.
        self.view.click((box.right + 30, box.bottom + 30))
        self.assertIsNone(self.hud.selected_object)

    def test_who_holds_a_post_is_said_and_how_worn_it_is(self) -> None:
        self.hud.select_object("workbench")
        self.world.interactables["workbench"].condition = 40.0
        self.assertIn("Puesto de Taller: Paco", self._said())
        state = next(line for line, _ in self.hud.object_view().lines if line.text == "Estado")
        self.assertAlmostEqual(state.share, 0.4)
        self.world.wear.break_down(self.world, self.world.interactables["workbench"])
        said = self._said()
        self.assertIn("Averiado: no se puede usar", said)
        self.assertTrue(any(text.startswith("Lo arregla Paco") for text in said), said)
        self.assertIn("Antes hay que arreglarlo", said)

    def test_what_has_nothing_to_say_of_itself_is_shown_as_it_always_was(self) -> None:
        crate, stool = self.world.interactables["crate_dorm"], next(
            placed for placed in self.world.interactables.values() if placed.kind == "stool"
        )
        self.assertFalse(speaks(self.world, crate) or speaks(self.world, stool))
        self.hud.select_object("crate_dorm")
        self.assertIsNone(self.hud.object_view())
        self.assertEqual(self.hud.container_rect().topleft, self.hud.layout.panel.topleft)
        self.assertIsNone(self._show(stool.object_id), "there is nothing to press on a stool for")
        self.assertIn("crate_dorm", self.view.container_hitboxes)

    def test_a_store_says_how_full_it_is_of_each_thing(self) -> None:
        self.world.step(3)
        self.hud.select_object("warehouse")
        said = self._said()
        held, room = self.world.stores.held(self.world), self.world.stores.capacity(self.world)
        self.assertGreater(held["food"], 0)
        self.assertIn(f"Comida: {held['food']} de {room['food']}", said)
        self.assertIn(f"Agua: {held['water']} de {room['water']}", said)
        measures = [line for line, _ in self.hud.object_view().lines if line.share is not None]
        self.assertEqual(len(measures), len(room))
        self.view.render()
        self.assertEqual(self.hud.container_rect().top, self.hud.object_view().rect.bottom)
        self.assertEqual(STORE_HEADING, "Lo que guarda")

    def test_making_it_better_is_put_to_whoever_keeps_it_from_its_panel(self) -> None:
        self.hud.select_object("crop_1")
        said = self._said()
        self.assertTrue(any(text.startswith("Antes hay que estudiarlo") for text in said), said)
        self.assertNotIn(upgrade_intent("crop_1"), [button.intent for button in self.hud.buttons])
        self.world.studies.known.append("fine_work")
        said = " ".join(self._said())
        self.assertIn("Mejorar a poco común: 3 de chatarra, 3 h de obra", said)
        self.assertIn("Se le propone a Raúl", said)
        self._press(upgrade_intent("crop_1"))
        site = self.world.upgrades.site_of(self.world, "crop_1")
        self.assertIsNotNone(site, self.hud.notice)
        self.assertEqual((site.kind, site.in_charge), (UPGRADE_SITE, "raul"))
        self.assertIn("Raúl", self.hud.notice)
        self.assertTrue(any(text.startswith("Mejora en obra, de Raúl") for text in self._said()))
        self.assertNotIn(upgrade_intent("crop_1"), [button.intent for button in self.hud.buttons], "one at a time")

    def test_a_thing_is_switched_from_its_panel_and_from_the_board_of_current(self) -> None:
        lamp = self.world.interactables["lamp_shop"]
        self.hud.select_object("lamp_shop")
        self._press(switch_intent("lamp_shop", False))
        self.assertFalse(lamp.on)
        self.assertIn("Corriente: gasta 1. Apagado", self._said())
        # The key and the button of anything that runs on current open the board.
        self.view.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_k))
        self.assertTrue(self.hud.power_open)
        self._press(POWER_INTENT)
        self.assertFalse(self.hud.power_open)
        self._press(POWER_INTENT)
        rows = power_rows(self.world)
        drawing = [object_id for object_id, placed in self.world.interactables.items() if self.world.definition_of(placed).draws]
        self.assertEqual([row.object_id for row in rows], drawing)
        self.assertEqual(next(row for row in rows if row.object_id == "lamp_shop").state, SWITCHED_OFF)
        self.assertIn("junto a", next(row for row in rows if row.object_id == "lamp_shop").name)
        self.view.render()
        self.assertTrue(self.hud.covers(self.hud.power_rect().center))
        self.assertTrue(self.view.viewport.contains(self.hud.power_rect()))
        self._press(switch_intent("lamp_shop", True))
        self.assertTrue(lamp.on)
        self._press(switch_intent("workbench", False))
        self.assertFalse(self.world.interactables["workbench"].on)

    def test_the_figure_of_fuel_in_the_bar_opens_the_board_and_any_other_what_is_held(self) -> None:
        self.view.render()
        chips = {chip.line.resource_id: chip for chip in self.hud.chips if chip.line is not None}
        self.view.click(chips["energy"].rect.center)
        self.assertEqual((self.hud.power_open, self.hud.stores_open), (True, False))
        self.view.click(chips["food"].rect.center)
        self.assertEqual((self.hud.power_open, self.hud.stores_open), (False, True))

    def test_what_stands_idle_has_a_mark_over_it_that_says_why(self) -> None:
        world = self.world
        self.assertEqual(marks_of(world), {})
        world.switch("lamp_shop", False)
        world.wear.break_down(world, world.interactables["cooking_pot"])
        self.assertEqual(marks_of(world), {"lamp_shop": OFF, "cooking_pot": BROKEN})
        box = self._show("lamp_shop")
        mark = self.view.object_marks["lamp_shop"]
        self.assertLessEqual(mark.bottom, box.top)
        self.assertEqual(mark.centerx, box.centerx)
        self.assertNotIn("lamp_dormitory", self.view.object_marks)
        # With no fuel, everything that is on stands idle for want of current.
        self._empty_of_fuel()
        marks = marks_of(world)
        self.assertEqual(marks["lamp_dormitory"], NO_CURRENT)
        self.assertEqual(marks["workbench"], NO_CURRENT)
        self.assertEqual(marks["lamp_shop"], OFF, "what is off is off, current or no current")
        self.assertNotIn("well", marks)
        self.hud.select_object("workbench")
        self.assertIn("Corriente: gasta 2. Sin corriente", self._said())

    def test_a_thing_better_than_common_wears_a_stone_of_the_colour_of_its_rarity(self) -> None:
        blue = rarity_color(self.world, 3)

        def stones() -> int:
            box = self._show("crop_3")
            return sum(
                tuple(self.view.canvas.get_at((x, y)))[:3] == blue
                for x in range(box.left, box.right)
                for y in range(box.top, box.bottom)
            )

        self.assertEqual(stones(), 0)
        self.world.interactables["crop_3"].level = 3
        self.assertGreater(stones(), 0)
        self.hud.select_object("crop_3")
        self.assertEqual(self._said()[1], "Calidad: raro")
        self.assertEqual(self.hud.object_view().lines[0][0].color, blue)

    def test_the_bar_shows_how_full_the_store_is_of_each_thing(self) -> None:
        self.world.step(3)
        self.view.render()
        chip = next(chip for chip in self.hud.chips if chip.line is not None and chip.line.resource_id == "scrap")
        share = room_share(chip.line)
        self.assertEqual(share, chip.line.stored / chip.line.capacity)
        self.assertTrue(0.0 < share < 1.0)
        gauge = room_gauge(chip)
        self.assertEqual(tuple(self.view.canvas.get_at(gauge.topleft))[:3], PALETTE["lichen"])
        self.assertEqual(tuple(self.view.canvas.get_at((gauge.right - 1, gauge.y)))[:3], PALETTE["shadow"])
        store = self.world.containers["warehouse"]
        self.world.stock(store, "scrap", chip.line.capacity, None)
        self.view.render()
        chip = next(chip for chip in self.hud.chips if chip.line is not None and chip.line.resource_id == "scrap")
        self.assertTrue(chip.line.full)
        self.assertEqual(tuple(self.view.canvas.get_at((gauge.right - 1, gauge.y)))[:3], PALETTE["ember"])
        people = next(chip for chip in self.hud.chips if chip.line is None)
        self.assertIsNone(room_share(people.line))

    def test_from_inside_a_building_a_thing_is_picked_as_from_outside(self) -> None:
        bench = self.world.interactables["workbench"]
        room = self.world.room_at((bench.x, bench.y))
        self.assertTrue(self.view.enter(room.room_id))
        self.view.update(0.0)
        self.view.render()
        self.assertIn("workbench", self.view.thing_hitboxes)
        self.assertNotIn("workbench", self.view.container_hitboxes)
        box = self.view.thing_hitboxes["workbench"]
        people = [rect for rect in self.view.hitboxes.values() if rect.collidepoint(box.center)]
        if not people:
            self.view.click(box.center)
            self.assertEqual(self.hud.selected_object, "workbench")
        self.world.wear.break_down(self.world, bench)
        self.view.render()
        self.assertIn("workbench", self.view.object_marks)

    def test_with_nowhere_to_keep_drawings_nothing_asks_to_be_drawn(self) -> None:
        bed = self.world.interactables["bed_1"]
        site = self.world.construction.lay(self.world, UPGRADE_SITE, "bed_1", (bed.x, bed.y), "marta")
        self.world.upgrades.finish(self.world, site)
        self.view.on_events(self.world.events.drain())
        self.assertIsNone(self.hud.redraw)
        self.hud.select_object("bed_1")
        self.assertNotIn(redraw_intent("bed_1"), [button.intent for button in self.hud.buttons])


class RedrawTests(unittest.TestCase):
    def setUp(self) -> None:
        _dummy(self)
        from game.game import OBJECT_SCENE, Game

        keep = tempfile.TemporaryDirectory()
        self.addCleanup(keep.cleanup)
        self.root = Path(keep.name) / "illustrations"
        self.root.mkdir()
        self.object_scene = OBJECT_SCENE
        self.game = Game(illustrations_dir=self.root, voices_dir=None, start_in_menu=False)
        self.addCleanup(pygame.quit)
        self.view, self.world, self.hud = self.game.global_view, self.game.world, self.game.global_view.hud

    def _better(self, object_id: str) -> None:
        placed = self.world.interactables[object_id]
        site = self.world.construction.lay(self.world, UPGRADE_SITE, object_id, (placed.x, placed.y), "marta")
        self.world.upgrades.finish(self.world, site)
        self.view.on_events(self.world.events.drain())

    def _press(self, intent) -> None:
        button = next(button for button in self.hud.buttons if button.intent == intent)
        self.view.click(button.rect.center)

    def test_a_thing_made_better_asks_whether_it_is_to_be_drawn_as_it_looks_now(self) -> None:
        self.assertIsNone(self.hud.redraw)
        self._better("bed_1")
        asked = self.hud.redraw
        self.assertEqual((asked.kind, asked.level), ("bed", 2))
        self.assertIn("poco común", asked.text)
        self.view.render()
        box = self.hud.redraw_rect()
        self.assertTrue(self.view.viewport.contains(box))
        self.assertTrue(self.hud.covers(box.center))
        # It can be left for now, and nothing opens.
        self._press(REDRAW_NO_INTENT)
        self.assertIsNone(self.hud.redraw)
        self.assertIsNone(self.view.requested_object_editor)
        self._better("bed_1")
        self._press(REDRAW_YES_INTENT)
        self.assertEqual((self.view.requested_object_editor, self.view.requested_object_level), ("bed", 3))
        self.game.sync_scenes()
        self.assertEqual(self.game.scene_name, self.object_scene)
        self.assertEqual((self.game.object_editor.kind, self.game.object_editor.level), ("bed", 3))
        self.assertEqual(self.view.requested_object_level, 1)

    def test_the_drawing_is_only_of_those_that_good_or_better(self) -> None:
        store, bed = self.view.object_art, self.world.registries.interactables.get("bed")
        self.assertEqual(object_art_path("bed"), "objects/bed.png")
        self.assertEqual(object_art_path("bed", 3), "objects/bed@3.png")
        self.world.interactables["bed_1"].level = 3
        self.hud.select_object("bed_1")
        self._press(redraw_intent("bed_1"))
        self.game.sync_scenes()
        editor = self.game.object_editor
        self.assertEqual((editor.kind, editor.level), ("bed", 3))
        self.assertIn("raro", editor._title())
        editor.drawing.fill((200, 40, 40, 255))
        self.assertTrue(editor.save())
        self.assertTrue((self.root / "objects" / "bed@3.png").is_file())
        self.assertFalse((self.root / "objects" / "bed.png").exists())
        self.assertIsNone(store.drawing(bed), "a common bed is still the game's")
        self.assertIsNone(store.drawing(bed, 2))
        self.assertIsNotNone(store.drawing(bed, 3))
        self.assertIs(store.drawing(bed, 5), store.drawing(bed, 3), "until a better one has its own")
        # On the map, the bed that is that good is the drawn one, and the one beside it is not.
        better, plain = self.world.interactables["bed_1"], self.world.interactables["bed_2"]
        self.assertIsNone(self.view._game_picture(bed, better))
        self.assertIsNotNone(self.view._game_picture(bed, plain))


if __name__ == "__main__":
    unittest.main()
