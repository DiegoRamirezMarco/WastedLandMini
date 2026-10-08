import os
import tempfile
import unittest
from pathlib import Path

import pygame

from scenes.hud import MANNERS_INTENT
from settings import SCALE
from simulation.commands import SetMannerCommand
from simulation.residents.activity import Activity
from ui.resident_panel import TASTES_TAB, manners_hitbox


class _Shell(unittest.TestCase):
    """Runs the real game shell without a window, through SDL's dummy drivers."""

    # Whether there is a folder to keep drawings in, and so dolls on the window itself.
    DRAWABLE = False
    START_IN_MENU = False

    def setUp(self) -> None:
        for variable in ("SDL_VIDEODRIVER", "SDL_AUDIODRIVER"):
            self.addCleanup(self._restore_driver, variable, os.environ.get(variable))
            os.environ[variable] = "dummy"
        from game.game import Game

        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        illustrations = self.root / "illustrations"
        if self.DRAWABLE:
            illustrations.mkdir()
        self.game = Game(
            illustrations_dir=illustrations if self.DRAWABLE else None,
            voices_dir=None,
            custom_content_dir=self.root / "custom",
            save_path=self.root / "save.json",
            start_in_menu=self.START_IN_MENU,
        )
        self.addCleanup(pygame.quit)

    @staticmethod
    def _restore_driver(variable: str, previous: str | None) -> None:
        if previous is None:
            os.environ.pop(variable, None)
        else:
            os.environ[variable] = previous

    def _key(self, key: int, text: str = "") -> None:
        self.game.handle_event(pygame.event.Event(pygame.KEYDOWN, key=key, unicode=text, mod=0))
        self.game.sync_scenes()

    def _click(self, position: tuple[int, int]) -> None:
        window = (position[0] * SCALE + 1, position[1] * SCALE + 1)
        for kind in (pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP):
            self.game.handle_event(pygame.event.Event(kind, pos=window, button=1))
        self.game.sync_scenes()

    def _frame(self, seconds: float = 1 / 60) -> pygame.Surface:
        """Let the scene on show draw a frame, and return the window as it is left."""
        self.game.active_scene.update(seconds)
        with self.assertNoLogs("graphics.assets", level="WARNING"):
            self.game.active_scene.render()
        self.game.present()
        return self.game.screen

    def _pick(self, scene, manner_id: str) -> None:
        self._click(next(button for button in scene.picker.buttons if button.intent[2] == manner_id).rect.center)


class MannersOnTheMapTests(_Shell):
    def setUp(self) -> None:
        super().setUp()
        self.view, self.world = self.game.global_view, self.game.world
        self.world.clock.paused = True
        self.raul, self.tomas = self.world.residents["raul"], self.world.residents["tomas"]
        for index, resident in enumerate((self.raul, self.tomas)):
            resident.x, resident.y, resident.trail, resident.activity = 20 + index, 14, [], None
            resident.inventory.items.clear()
        self.view.centre_on((20.5, 13.5))
        self.view.following = None

    def _fight(self) -> None:
        self.raul.activity = Activity("fight", partner_id="tomas", using=True)
        self.tomas.activity = Activity("fight", partner_id="raul", using=True)

    def _clip_shown(self, resident_id: str = "raul") -> str:
        self.view.render()
        return self.view.bodies.characters[resident_id].clip

    def test_each_resident_walks_eats_and_fights_in_the_manner_that_is_theirs(self) -> None:
        self.raul.trail = [(self.raul.x - 1, self.raul.y), self.raul.tile]
        self.view.tick_progress = 0.5
        for manner in self.world.registries.manners.of_kind("walk"):
            self.world.apply_command(SetMannerCommand("raul", "walk", manner.manner_id))
            self.assertEqual(self._clip_shown(), manner.clip)
        self.raul.trail = []
        self.raul.activity = Activity("eat", "pantry_1", minutes_left=10, using=True, item_id="canned_beans")
        for manner in self.world.registries.manners.of_kind("eat"):
            self.world.apply_command(SetMannerCommand("raul", "eat", manner.manner_id))
            # They eat sitting down, their own way of each: the body sits, and the arms eat over it.
            seat = self.world.manner_of(self.raul, "sit")
            self.assertEqual(self._clip_shown(), seat.clip)
            self.assertEqual(self.view.bodies.characters["raul"].overlay, manner.clip)
            self.assertEqual(self.view._bearing(self.raul), (seat.clip, manner.rate, manner.clip))
            self.assertEqual([entry[0] for entry in self.view._held], ["canned_beans"], "the meal is in the hand")
        self._fight()
        for manner in self.world.registries.manners.of_kind("fight"):
            self.world.apply_command(SetMannerCommand("raul", "fight", manner.manner_id))
            self.assertEqual(self._clip_shown(), manner.clip)
        self.assertEqual(self.view._held, [], "bare hands hold nothing")

    def test_they_sit_their_own_way_by_the_fire_at_the_radio_eating_and_drinking(self) -> None:
        view, raul = self.view, self.raul
        # Seen from a side: from the front the game's own small bodies have no way of sitting.
        raul.trail, raul.facing = [], "right"
        view.render()
        standing = view.hitboxes["raul"].copy()
        self.assertIsNone(view._seat_of(raul), "with nothing to do they are on their feet")
        for manner in self.world.registries.manners.of_kind("sit"):
            self.world.apply_command(SetMannerCommand("raul", "sit", manner.manner_id))
            for action in ("relax", "listen", "drink"):
                raul.activity = Activity(action, minutes_left=30, using=True)
                self.assertEqual(view._seat_of(raul), (manner.clip, manner.rate))
                self.assertEqual(view._bearing(raul), (manner.clip, manner.rate, None))
                self.assertEqual(self._clip_shown(), manner.clip, action)
                body = view.bodies.characters["raul"]
                self.assertIsNone(body.overlay)
                self.assertFalse(body.idle, "sitting is something to be at: nobody fidgets out of it")
                # Their name comes down with their head, and so does what is picked.
                seated = view.hitboxes["raul"]
                self.assertGreater(seated.top, standing.top, (manner.manner_id, action))
                self.assertEqual(seated.bottom, standing.bottom)
        # On the way there they walk, and at work, or with somebody, they are on their feet.
        raul.activity = Activity("relax", path=[(raul.x + 1, raul.y)], minutes_left=3)
        self.assertIsNone(view._seat_of(raul), "not sitting yet")
        for activity in (Activity("work", using=True), Activity("sleep", using=True), Activity("chat", partner_id="tomas", using=True)):
            raul.activity = activity
            self.assertIsNone(view._seat_of(raul), activity.action)
        raul.activity = None
        view.render()
        self.assertEqual(view.hitboxes["raul"], standing)
        self.assertTrue(view.bodies.characters["raul"].clip == "idle")

    def test_a_walk_of_short_steps_takes_two_to_the_stride_and_ends_where_the_next_begins(self) -> None:
        self.raul.trail = [(self.raul.x - 2, self.raul.y), (self.raul.x - 1, self.raul.y), self.raul.tile]
        phases = {}
        for manner_id in ("walk_steady", "walk_shuffle"):
            self.world.apply_command(SetMannerCommand("raul", "walk", manner_id))
            seen = []
            for progress in (0.0, 0.25, 0.999):
                self.view.tick_progress = progress
                self.view.render()
                seen.append(self.view.bodies.characters["raul"].phase)
            phases[manner_id] = seen
        self.assertGreater(phases["walk_shuffle"][1], phases["walk_steady"][1])
        for seen in phases.values():
            # A minute's walk is a whole number of turns: nothing jumps as the next one starts.
            self.assertEqual(seen[0], 0.0)
            self.assertGreater(seen[2], 0.8)

    def test_whoever_fights_with_a_knife_does_it_their_way_with_a_knife_and_it_is_in_their_hand(self) -> None:
        self.world.apply_command(SetMannerCommand("raul", "fight", "fight_kicker"))
        self.world.apply_command(SetMannerCommand("raul", "knife", "knife_overhand"))
        self._fight()
        self.assertEqual(self._clip_shown(), "fight_kick")
        self.world.stock(self.raul.inventory, "rusty_knife", 1, "raul")
        self.assertEqual(self._clip_shown(), "knife_overhand")
        self.assertEqual([entry[0] for entry in self.view._held], ["rusty_knife"])
        # A blunt thing is swung the way fists are, and is seen too.
        self.raul.inventory.items.clear()
        self.world.stock(self.raul.inventory, "baton", 1, "raul")
        self.assertEqual(self._clip_shown(), "fight_kick")
        self.assertEqual([entry[0] for entry in self.view._held], ["baton"])
        # Once the fight is over it is put away.
        self.raul.activity = self.tomas.activity = None
        self.assertEqual(self._clip_shown(), "idle")
        self.assertEqual(self.view._held, [])

    def test_anything_tagged_as_a_firearm_is_fired_the_way_they_shoot(self) -> None:
        from dataclasses import replace

        knife = self.world.registries.items.get("rusty_knife")
        self.world.registries.items.register(replace(knife, item_id="pistol", name="pistola", tags=("weapon", "firearm")))
        self.world.stock(self.raul.inventory, "pistol", 1, "raul")
        self.world.apply_command(SetMannerCommand("raul", "shoot", "shoot_hip"))
        self._fight()
        self.assertEqual(self._clip_shown(), "shoot_hip")
        self.assertEqual([entry[0] for entry in self.view._held], ["pistol"])


class MannerEditorTests(_Shell):
    def _open(self, resident_id: str):
        self.game.global_view.hud.select_resident(resident_id)
        self._frame()
        self._click(manners_hitbox(self.game.global_view.hud.layout.panel).center)
        self.assertEqual(self.game.scene_name, "manners")
        return self.game.manner_editor

    def test_the_panel_opens_it_on_whoever_is_selected_and_time_stops(self) -> None:
        hud = self.game.global_view.hud
        self.assertNotIn(MANNERS_INTENT, [button.intent for button in hud.menu], "the menu has no room for it")
        editor = self._open("lucia")
        self.assertEqual(editor.resident_id, "lucia")
        minute = self.game.world.clock.total_minutes
        self.game.advance_simulation(5.0)
        self.assertEqual(self.game.world.clock.total_minutes, minute)
        self._frame()
        # Escape leaves the manners, not the game. F6 is the way in from the keyboard.
        self._key(pygame.K_ESCAPE)
        self.assertEqual(self.game.scene_name, "global")
        self.assertTrue(self.game.running)
        self._key(pygame.K_F6)
        self.assertEqual((self.game.scene_name, editor.resident_id), ("manners", "lucia"))
        self._key(pygame.K_ESCAPE)
        # On what they like, that corner is for something else.
        hud.panel_tab = TASTES_TAB
        self._click(manners_hitbox(hud.layout.panel).center)
        self.assertEqual(self.game.scene_name, "global")

    def test_what_is_picked_is_theirs_at_once_and_lit_and_nothing_lies_over_anything_else(self) -> None:
        editor = self._open("raul")
        world, raul = self.game.world, self.game.world.residents["raul"]
        boxes = [button.rect for button in editor.buttons]
        for index, box in enumerate(boxes):
            self.assertTrue(self.game.canvas.get_rect().contains(box), box)
            self.assertEqual(box.collidelist(boxes[index + 1 :]), -1, box)
        self.assertEqual(len(editor.picker.rows), 6)
        self.assertEqual([len(buttons) for _, _, buttons in editor.picker.rows], [3, 3, 3, 3, 3, 4])
        # Before anything is picked, what is lit is what is theirs by default.
        self.assertEqual(editor.chosen()["walk"], world.manner_of(raul, "walk").manner_id)
        for manner_id, manner in world.registries.manners.manners.items():
            self._pick(editor, manner_id)
            self.assertEqual(raul.manners[manner.kind], manner_id)
            self.assertEqual((editor.shown, editor.chosen()[manner.kind]), (manner.kind, manner_id))
            self._frame()
        # The arrows go round everybody, and what was given to one is not given to the next.
        self._key(pygame.K_RIGHT)
        self.assertEqual(editor.resident_id, "lucia")
        self.assertEqual(world.residents["lucia"].manners, {})
        self._key(pygame.K_LEFT)
        self.assertEqual(editor.resident_id, "raul")

    def test_what_is_seen_moving_is_the_manner_on_show_and_it_moves(self) -> None:
        editor = self._open("raul")
        from scenes.manner_editor import PREVIEW

        place = self.game.layers.on_screen(PREVIEW)

        def seen() -> bytes:
            return pygame.image.tobytes(self._frame(0.0).subsurface(place), "RGB")

        self._pick(editor, "walk_steady")
        steady = seen()
        self.assertEqual(seen(), steady, "with no time gone by it stands as it stood")
        self.assertNotEqual(pygame.image.tobytes(self._frame(0.2).subsurface(place), "RGB"), steady)
        editor.preview.time = 0.0
        self._pick(editor, "walk_swagger")
        self.assertNotEqual(seen(), steady)
        # Something in the hand where there is anything of the kind to put there: a knife, not yet a gun.
        knife = editor.preview.prop(self.game.world.registries.manners.manners["knife_slash"])
        self.assertEqual(knife, "rusty_knife")
        self.assertIsNone(editor.preview.prop(self.game.world.registries.manners.manners["shoot_hip"]))
        self.assertIsNone(editor.preview.prop(self.game.world.registries.manners.manners["walk_steady"]))

    def test_with_nobody_living_there_it_does_not_open(self) -> None:
        self.game.new_game(seed=7)
        self._key(pygame.K_ESCAPE)
        self.assertEqual(self.game.scene_name, "global")
        self._key(pygame.K_F6)
        self.assertEqual(self.game.scene_name, "global")


class DrawnMannerTests(_Shell):
    DRAWABLE = True

    def test_someone_who_has_been_drawn_is_seen_trying_their_manners_as_they_were_drawn(self) -> None:
        from scenes.manner_editor import PREVIEW

        self.game.global_view.hud.select_resident("raul")
        self._key(pygame.K_F6)
        editor = self.game.manner_editor
        place = self.game.layers.on_screen(PREVIEW)
        self._pick(editor, "fight_brawler")
        editor.preview.time = 0.3
        example = pygame.image.tobytes(self._frame(0.0).subsurface(place), "RGB")
        self.assertIs(editor.preview.doll_of("raul"), editor.preview.example())
        self.assertGreater(len(set(example[index : index + 3] for index in range(0, len(example), 3))), 4)
        self._key(pygame.K_ESCAPE)

        # Drawn, with a head of a colour nothing else is, it is that head that is seen.
        drawing = self.game.doll_editor
        drawing.open("raul")
        drawing.mannequin()
        drawing.drawings["head"].fill((255, 0, 255, 255))
        self.assertTrue(drawing.save())
        self._key(pygame.K_F6)
        self.assertIsNot(editor.preview.doll_of("raul"), editor.preview.example())
        editor.preview.time = 0.3
        window = self._frame(0.0).subsurface(place)
        self.assertNotEqual(pygame.image.tobytes(window, "RGB"), example)
        self.assertGreater(pygame.mask.from_threshold(window, (255, 0, 255, 255), (2, 2, 2, 255)).count(), 100)


class CreatorMannerTests(_Shell):
    START_IN_MENU = True

    def _type(self, text: str) -> None:
        for char in text:
            self._key(pygame.key.key_code(char.lower()), char)

    def test_the_first_resident_is_given_their_manners_where_they_are_made(self) -> None:
        self.game.main_menu.choose("new")
        self.game.sync_scenes()
        creator = self.game.creator
        self._type("Ada")
        self._frame()
        manners = self.game.world.registries.manners
        # Until one is picked, each kind stands at the first way there is of it.
        self.assertEqual(creator.manners, {kind: manners.of_kind(kind)[0].manner_id for kind in manners.kinds})
        self._click(creator.page_buttons[1].rect.center)
        self.assertEqual(creator.page, "manners")
        boxes = [button.rect for button in creator.buttons]
        for index, box in enumerate(boxes):
            self.assertTrue(self.game.canvas.get_rect().contains(box), box)
            self.assertEqual(box.collidelist(boxes[index + 1 :]), -1, box)
        self._frame()
        self._pick(creator, "walk_shuffle")
        self._pick(creator, "shoot_braced")
        self.assertEqual(creator.shown_kind, "shoot")
        self._frame(0.3)
        # The name is written on the other face: here the keys do not touch it.
        self._type("x")
        self.assertEqual(creator.name, "Ada")
        # Going back and forth loses nothing, and it can be made from either face.
        self._click(creator.page_buttons[0].rect.center)
        self._frame()
        self._type("m")
        self._click(creator.page_buttons[1].rect.center)
        self._key(pygame.K_RETURN)
        self.assertEqual(self.game.scene_name, "global")
        ada = self.game.world.residents["adam"]
        self.assertEqual(ada.manners["walk"], "walk_shuffle")
        self.assertEqual(ada.manners["shoot"], "shoot_braced")
        self.assertEqual(ada.manners["eat"], manners.of_kind("eat")[0].manner_id)
        self.assertEqual(self.game.world.manner_of(ada, "walk").clip, "walk_shuffle")

    def test_opened_again_it_starts_from_a_blank(self) -> None:
        self.game.main_menu.choose("new")
        self.game.sync_scenes()
        creator = self.game.creator
        self._click(creator.page_buttons[1].rect.center)
        self._pick(creator, "eat_wolf")
        self._key(pygame.K_ESCAPE)
        self.game.open_creator()
        self.assertEqual((creator.page, creator.manners["eat"]), ("person", "eat_calm"))


if __name__ == "__main__":
    unittest.main()
