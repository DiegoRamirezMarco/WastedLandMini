import json
import os
import tempfile
import unittest
from pathlib import Path

import pygame

from graphics.doll import DOLL_FACINGS, build_path, doll_path, load_template
from graphics.mannequin import figures, tones_of
from scenes.global_view import EAT_CLIP, MAP_TURN_STEP, TO_BEHIND, TO_FRONT, TO_SIDE, TURN_SPEED, GlobalView
from settings import SCREEN_HEIGHT, SCREEN_WIDTH

SKIN = (214, 170, 130)
LINE = (30, 22, 20)
EYE = (40, 200, 60, 255)


def wide(doll) -> int:
    return doll.parts["spine"].image.get_bounding_rect().width


def eyes(image: pygame.Surface) -> int:
    return pygame.mask.from_threshold(image, EYE, (30, 30, 30, 255)).count()


class TurningResidentsTests(unittest.TestCase):
    """Whoever is shown as a doll on the map comes round to the way they walk."""

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
        self.keep("raul")
        from game.game import Game

        self.game = Game(illustrations_dir=self.root, voices_dir=None, start_in_menu=False)
        self.view = self.game.global_view
        self.raul = self.game.world.residents["raul"]
        self.stand("right")
        self.view.centre_on((20, 14))

    @staticmethod
    def _restore(variable: str, previous: str | None) -> None:
        if previous is None:
            os.environ.pop(variable, None)
        else:
            os.environ[variable] = previous

    def keep(self, resident_id: str) -> None:
        """Keep somebody as they were drawn before there was any turning, an eye on their head."""
        base = load_template()
        plain = figures(base.built(base.starting()), tones_of(SKIN, LINE), 5)
        for canvas, drawing in plain.items():
            if canvas == "head":
                box = drawing.get_bounding_rect()
                pygame.draw.circle(drawing, EYE, (box.centerx + box.width // 5, box.centery), 5)
            path = self.root / doll_path(resident_id, canvas)
            path.parent.mkdir(parents=True, exist_ok=True)
            pygame.image.save(drawing, str(path))
        (self.root / build_path(resident_id)).write_text(json.dumps(base.starting().to_data()), encoding="utf-8")

    def stand(self, facing: str) -> None:
        raul = self.raul
        raul.x, raul.y, raul.trail, raul.activity, raul.facing = 20, 14, [], None, facing

    def frame(self, seconds: float = 1 / 60) -> None:
        self.view.update(seconds)
        self.view.render()
        self.game.present(self.window)

    def settle(self) -> None:
        """Long enough for anybody to have come round, and for each way they are turned on
        the way there to have been made."""
        for _ in range(40):
            self.frame()

    def yaw(self) -> float:
        return self.view._turns["raul"][0]

    def drawn(self):
        return next(entry for entry in self.view._doll_draws if entry[1] is self.view.doll_shown["raul"])

    def test_walking_across_they_are_their_drawing_seen_from_its_side(self) -> None:
        self.frame()
        doll = self.game.dolls.get("raul")
        self.assertEqual(self.yaw(), TO_SIDE)
        self.assertIs(self.view.doll_shown["raul"], doll)
        self.assertEqual(self.drawn()[2].facing, DOLL_FACINGS["right"])
        self.stand("left")
        self.settle()
        self.assertEqual(self.yaw(), -TO_SIDE)
        self.assertIs(self.view.doll_shown["raul"], doll)
        self.assertEqual(self.drawn()[2].facing, DOLL_FACINGS["left"])

    def test_facing_down_the_map_they_are_seen_from_the_front_and_up_it_from_behind(self) -> None:
        self.frame()
        doll = self.game.dolls.get("raul")
        self.stand("down")
        self.settle()
        self.assertEqual(self.yaw(), TO_FRONT)
        front = self.view.doll_shown["raul"]
        self.assertGreater(wide(front), wide(doll) * 1.3)
        self.assertGreater(eyes(front.parts["skull"].image), 30)
        # Their arms are to either side of them, and not one before the other.
        skeleton = self.drawn()[2]
        self.assertGreater(abs(skeleton.joints["shoulder_left"].x - skeleton.joints["shoulder_right"].x), 4.0)
        self.stand("up")
        self.settle()
        self.assertEqual(abs(self.yaw()), TO_BEHIND)
        behind = self.view.doll_shown["raul"]
        self.assertAlmostEqual(wide(behind), wide(front), delta=2)
        self.assertEqual(eyes(behind.parts["skull"].image), 0, "there is no face on the back of a head")

    def test_they_come_round_by_degrees_and_through_the_front_from_one_side_to_the_other(self) -> None:
        self.frame()
        self.stand("left")
        seen = []
        for _ in range(40):
            self.frame()
            seen.append(self.yaw())
        self.assertEqual(seen[-1], -TO_SIDE)
        self.assertTrue(all(abs(yaw) <= TO_SIDE for yaw in seen), "nobody turns their back to go from side to side")
        self.assertTrue(any(abs(yaw) < MAP_TURN_STEP for yaw in seen), "they go through the front")
        steps = [abs(later - earlier) for earlier, later in zip(seen, seen[1:])]
        self.assertLessEqual(max(steps), TURN_SPEED / 60 * max(1.0, float(self.game.world.clock.speed)) + 1e-6)
        self.assertGreater(len([step for step in steps if step > 0]), 5)

    def test_time_standing_still_nobody_turns(self) -> None:
        self.frame()
        self.game.world.clock.paused = True
        self.stand("down")
        self.settle()
        self.assertEqual(self.yaw(), TO_SIDE)
        self.game.world.clock.paused = False
        self.settle()
        self.assertEqual(self.yaw(), TO_FRONT)

    def test_at_something_they_are_at_it_from_their_side(self) -> None:
        self.stand("down")
        self.settle()
        self.assertEqual(self.yaw(), TO_FRONT)
        # Whatever they do that is not standing there, every clip of it is seen from the side.
        self.view._bearing = lambda resident: (EAT_CLIP, 1.0, None)
        self.settle()
        self.assertEqual(abs(self.yaw()), TO_SIDE)
        self.assertIs(self.view.doll_shown["raul"], self.game.dolls.get("raul"))

    def test_walking_aslant_they_are_seen_part_of_the_way_round(self) -> None:
        heading = GlobalView._heading
        self.assertEqual(heading("right", None), TO_SIDE)
        self.assertEqual(heading("left", "left"), -TO_SIDE)
        self.assertEqual(heading("down", None), TO_FRONT)
        self.assertEqual(heading("down", "right"), 45.0)
        self.assertEqual(heading("down", "left"), -45.0)
        self.assertEqual(heading("up", None), TO_BEHIND)
        self.assertEqual(heading("up", "right"), 135.0)
        self.assertEqual(heading("up", "left"), -135.0)

    def test_whoever_has_not_been_drawn_turns_as_well(self) -> None:
        marta = self.game.world.residents["marta"]
        marta.x, marta.y, marta.trail, marta.activity, marta.facing = 22, 14, [], None, "right"
        self.frame()
        self.assertIsNone(self.game.dolls.get("marta"))
        side = self.view.doll_shown["marta"]
        marta.facing = "down"
        self.settle()
        self.assertGreater(wide(self.view.doll_shown["marta"]), wide(side) * 1.3)


if __name__ == "__main__":
    unittest.main()
