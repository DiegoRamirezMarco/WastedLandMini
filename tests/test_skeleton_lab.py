import os
import unittest

import pygame

from settings import INTERNAL_HEIGHT, INTERNAL_WIDTH, SCALE
from tools.skeleton_lab import MORE, START_COUNT, Lab


def _key(key: int) -> pygame.event.Event:
    return pygame.event.Event(pygame.KEYDOWN, key=key)


class SkeletonLabTests(unittest.TestCase):
    """Runs the lab without a window, through SDL's dummy video driver."""

    def setUp(self) -> None:
        previous = os.environ.get("SDL_VIDEODRIVER")
        os.environ["SDL_VIDEODRIVER"] = "dummy"
        self.addCleanup(lambda: os.environ.pop("SDL_VIDEODRIVER") if previous is None else os.environ.update(SDL_VIDEODRIVER=previous))
        pygame.init()
        self.addCleanup(pygame.quit)
        pygame.display.set_mode((INTERNAL_WIDTH * SCALE, INTERNAL_HEIGHT * SCALE))
        self.lab = Lab(pygame.Surface((INTERNAL_WIDTH, INTERNAL_HEIGHT)))

    def _run(self, seconds: float) -> None:
        for _ in range(round(seconds * 60)):
            self.lab.update(1 / 60)
            self.lab.render()

    def _point_at(self, index: int) -> None:
        body = self.lab.actors[index].character
        position = (int(body.x) * SCALE, (int(body.y) - 10) * SCALE)
        self.lab.handle_event(pygame.event.Event(pygame.MOUSEMOTION, pos=position, rel=(0, 0), buttons=(0, 0, 0)))

    def test_bodies_that_are_left_alone_cost_no_physics(self) -> None:
        self.lab.handle_event(_key(pygame.K_n))
        for _ in range(len(self.lab.clips)):
            self.lab.handle_event(_key(pygame.K_c))
            self.lab.handle_event(_key(pygame.K_f))
            self._run(0.2)
        self.assertEqual(len(self.lab.actors), START_COUNT + MORE)
        self.assertEqual(self.lab.awake(), 0)
        self.assertTrue(all(actor.character.skeleton is None for actor in self.lab.actors))

    def test_a_click_strikes_only_the_body_under_the_mouse(self) -> None:
        self._point_at(2)
        body = self.lab.actors[2].character
        click = pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=(int(body.x) * SCALE, (int(body.y) - 10) * SCALE))
        self.lab.handle_event(click)
        self.assertEqual([actor.character.physical for actor in self.lab.actors].count(True), 1)
        self.assertTrue(body.physical)
        self._run(1.0)
        self.assertEqual(self.lab.awake(), 0)

    def test_parts_come_off_bodies_die_and_everything_comes_to_rest(self) -> None:
        self.lab.handle_event(_key(pygame.K_b))
        self._point_at(0)
        for key in (pygame.K_1, pygame.K_4, pygame.K_h):
            self.lab.handle_event(_key(key))
        self.assertEqual(self.lab.actors[0].character.lost, ["arm_left", "leg_right", "head"])
        self.assertEqual(len(self.lab.parts), 3)
        self.lab.handle_event(_key(pygame.K_1))
        self.assertEqual(len(self.lab.parts), 3, "an arm comes off once")
        # With the mouse on nobody, a key is for everybody.
        self.lab.handle_event(pygame.event.Event(pygame.MOUSEMOTION, pos=(2, 2), rel=(0, 0), buttons=(0, 0, 0)))
        self.lab.handle_event(_key(pygame.K_d))
        self.assertEqual(self.lab.awake(), START_COUNT + 3)
        self.lab.handle_event(_key(pygame.K_k))
        self._run(7.5)
        self.assertEqual(self.lab.awake(), 0)
        self.assertFalse(any(actor.character.alive for actor in self.lab.actors))
        for actor in self.lab.actors:
            self.assertTrue(self.lab.renderer.is_settled(actor.character.skeleton))
        self.lab.handle_event(_key(pygame.K_r))
        self.assertEqual((len(self.lab.actors), len(self.lab.parts)), (START_COUNT, 0))


if __name__ == "__main__":
    unittest.main()
