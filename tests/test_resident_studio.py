import json
import os
import tempfile
import unittest
from pathlib import Path

import pygame

from graphics.doll import BODY_CANVAS, HEAD_CANVAS, build_path, doll_path
from graphics.figure import FRONT_DRAWN, SIDE_DRAWN, TRUNK_KEY
from graphics.mannequin import figures, tones_of
from scenes.studio import BODY_TAB, HANDS_TAB, Studio
from settings import SCALE, SCREEN_HEIGHT, SCREEN_WIDTH

SKIN = (214, 170, 130)
LINE = (30, 22, 20)


def painted(surface: pygame.Surface) -> int:
    return pygame.mask.from_surface(surface).count()


class ResidentStudioTests(unittest.TestCase):
    """The one screen residents are drawn on, in the real game shell, without a window."""

    def setUp(self) -> None:
        for variable in ("SDL_VIDEODRIVER", "SDL_AUDIODRIVER"):
            self.addCleanup(self._restore, variable, os.environ.get(variable))
            os.environ[variable] = "dummy"
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name) / "illustrations"
        self.root.mkdir()
        self.addCleanup(pygame.quit)
        self.window = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))

    @staticmethod
    def _restore(variable: str, previous: str | None) -> None:
        if previous is None:
            os.environ.pop(variable, None)
        else:
            os.environ[variable] = previous

    def start(self):
        from game.game import Game

        self.game = Game(illustrations_dir=self.root, voices_dir=None, start_in_menu=False)
        return self.game

    def open(self, resident_id: str) -> Studio:
        game = self.game
        game.doll_editor.open(resident_id)
        game.scene_name = "editor"
        return game.doll_editor

    def frame(self) -> None:
        self.game.active_scene.update(1 / 60)
        self.game.active_scene.render()
        self.game.present(self.window)

    def click(self, position: tuple[int, int]) -> None:
        for kind in (pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP):
            self.game.active_scene.handle_event(pygame.event.Event(kind, pos=(position[0] * SCALE + 1, position[1] * SCALE + 1), button=1))

    def press(self, intent: tuple) -> None:
        self.click(next(button for button in self.game.doll_editor.buttons if button.intent == intent).rect.center)

    def key(self, key: int) -> None:
        self.game.active_scene.handle_event(pygame.event.Event(pygame.KEYDOWN, key=key, mod=0, unicode=""))

    def keep_drawn_before(self, resident_id: str) -> None:
        """Keep somebody as they were drawn before there was any turning: no word of their trunk."""
        from graphics.doll import load_template

        base = load_template()
        plain = figures(base.built(base.starting()), tones_of(SKIN, LINE), 5)
        for canvas, drawing in plain.items():
            path = self.root / doll_path(resident_id, canvas)
            path.parent.mkdir(parents=True, exist_ok=True)
            pygame.image.save(drawing, str(path))
        (self.root / build_path(resident_id)).write_text(json.dumps(base.starting().to_data()), encoding="utf-8")

    def test_it_is_the_screen_residents_are_drawn_on_and_knows_who_they_are(self) -> None:
        game = self.start()
        studio = self.open("raul")
        self.assertIsInstance(studio, Studio)
        self.assertEqual(studio.resident_id, "raul")
        self.assertEqual(studio._name(), game.world.residents["raul"].name)
        self.assertEqual(studio.tab, BODY_TAB)
        self.frame()
        # Whoever is drawn is somebody who is there: there is nobody new to begin, and the
        # next and the one before are the next and the one before of those who live there.
        self.assertFalse(any(button.intent == ("new",) for button in studio.buttons))
        residents = list(game.world.residents)
        self.press(("step", 1))
        roster = studio.roster()
        self.assertEqual(studio.resident_id, roster[(roster.index("raul") + 1) % len(roster)])
        self.press(("step", -1))
        self.assertEqual(studio.resident_id, "raul")
        self.assertEqual(studio.roster()[: len(residents)], residents)
        self.frame()

    def test_escape_leaves_it_as_it_leaves_every_other_screen_and_time_stands_still(self) -> None:
        game = self.start()
        studio = self.open("raul")
        minute = game.world.clock.total_minutes
        game.advance_simulation(5.0)
        self.assertEqual(game.world.clock.total_minutes, minute)
        # With what is behind the cog open, Escape shuts that first.
        self.press(("cog",))
        self.assertTrue(studio.cog)
        self.key(pygame.K_ESCAPE)
        self.assertFalse(studio.cog)
        self.assertFalse(studio.closed)
        self.key(pygame.K_ESCAPE)
        self.assertTrue(studio.closed)
        game.sync_scenes()
        self.assertEqual(game.scene_name, "global")
        self.assertTrue(game.running)

    def test_the_fitting_room_is_a_tile_away_and_comes_back_to_the_drawing(self) -> None:
        game = self.start()
        studio = self.open("raul")
        self.press(("mannequin",))
        drawn = painted(studio.drawings[BODY_CANVAS])
        self.press(("fitting",))
        self.assertEqual(studio.requested_fitting, "raul")
        game.sync_scenes()
        self.assertEqual(game.scene_name, "garment_editor")
        self.assertIsNone(studio.requested_fitting)
        game.garment_editor.closed = True
        game.sync_scenes()
        self.assertEqual(game.scene_name, "editor")
        self.assertEqual(painted(studio.drawings[BODY_CANVAS]), drawn, "the drawing is as it was left")

    def test_somebody_drawn_before_is_said_to_be_and_turns_by_rule_until_drawn_anew(self) -> None:
        self.keep_drawn_before("raul")
        game = self.start()
        self.assertEqual(game.figures.said("raul").drawn, SIDE_DRAWN)
        studio = self.open("raul")
        body = studio.body
        self.assertEqual(body.trunk_drawn, SIDE_DRAWN)
        self.assertIn("de lado", body.notice)
        self.frame()
        rules = game.figures.rules
        # Beside the paper they are their drawing from their side, and from the front their
        # trunk is made wider, as the settlement will show them.
        from_side = body._seen(rules.side, rules.side)
        self.assertIs(from_side.limbs["spine"].image if "spine" in from_side.limbs else from_side.parts["spine"].image, body._preview.parts["spine"].image)
        wide = lambda doll: doll.parts["spine"].image.get_bounding_rect().width
        self.assertGreater(wide(body._seen(0.0, 0.0)), wide(body._preview) * 1.3)
        # Kept as they are, they are still drawn from their side.
        self.press(("save",))
        kept = json.loads((self.root / build_path("raul")).read_text(encoding="utf-8"))
        self.assertEqual(kept[TRUNK_KEY], SIDE_DRAWN)
        self.assertEqual(game.figures.said("raul").drawn, SIDE_DRAWN)
        # The tile behind the cog says otherwise, and so does beginning from the plain figure.
        self.press(("cog",))
        self.assertFalse(next(button for button in studio.buttons if button.intent == ("trunk",)).lit)
        self.press(("trunk",))
        self.assertEqual(body.trunk_drawn, FRONT_DRAWN)
        self.press(("trunk",))
        self.press(("cog",))
        self.press(("mannequin",))
        self.assertEqual(body.trunk_drawn, FRONT_DRAWN)
        self.press(("save",))
        kept = json.loads((self.root / build_path("raul")).read_text(encoding="utf-8"))
        self.assertEqual(kept[TRUNK_KEY], FRONT_DRAWN)
        self.assertEqual(game.figures.said("raul").drawn, FRONT_DRAWN)
        self.frame()

    def test_somebody_kept_with_only_a_body_drawn_has_a_head_all_the_same(self) -> None:
        game = self.start()
        studio = self.open("raul")
        self.press(("mannequin",))
        self.assertEqual(painted(studio.drawings[HEAD_CANVAS]), 0)
        self.press(("save",))
        doll = game.dolls.get("raul")
        self.assertIn("skull", doll.parts)
        self.assertGreater(painted(pygame.image.load(str(self.root / doll_path("raul", HEAD_CANVAS)))), 1000)

    def test_hands_and_feet_made_here_are_the_ones_the_settlement_shows(self) -> None:
        game = self.start()
        studio = self.open("raul")
        self.press(("mannequin",))
        self.press(("tab", HANDS_TAB))
        self.press(("made",))
        self.press(("feet_made",))
        self.frame()
        self.press(("save",))
        for name in ("hands.json", "feet.json", "face.json"):
            self.assertTrue((self.root / "dolls" / "raul" / name).is_file(), name)
        doll = game.dolls.get("raul")
        shown = game.figures.shown("raul", doll)
        self.assertEqual(set(shown.made.bones), {"hand_left", "hand_right", "foot_left", "foot_right"})
        self.assertNotIn("hand_right", shown.doll.parts)
        # Read again by a game begun anew, they are as they were kept.
        self.game.running = False
        again = self.start()
        self.assertTrue(again.figures.hands.get("raul").choice.made)
        self.assertTrue(again.figures.feet.get("raul").choice.made)


if __name__ == "__main__":
    unittest.main()
