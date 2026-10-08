import math
import os
import unittest

import pygame

from graphics.bolts import BOLTS, BURSTS, CORE, HIGHEST, SEEN, STARTS, BoltArt, bolts
from graphics.cartoon import LINE


def _reach(bolt) -> float:
    """How far from the head the furthest corner of a bolt is."""
    return max(math.hypot(x, y) for x, y in bolt.points)


class BoltTests(unittest.TestCase):
    def test_the_same_moment_of_the_same_quarrel_is_always_the_same(self) -> None:
        for seconds in (0.0, 0.31, 7.77, 1234.5):
            self.assertEqual(bolts(seconds, 1.0, 5), bolts(seconds, 1.0, 5))
        moments = [step / 60 for step in range(240)]
        mine = [bool(bolts(seconds, 1.0, 5)) for seconds in moments]
        theirs = [bool(bolts(seconds, 1.0, 6)) for seconds in moments]
        self.assertNotEqual(mine, theirs, "no two heads let theirs fly in step")

    def test_they_fly_in_lots_with_nothing_in_the_air_between_one_and_the_next(self) -> None:
        counts = [len(bolts(step / 200, 1.0, 2)) for step in range(800)]
        self.assertEqual(set(counts), {0, BOLTS})
        self.assertAlmostEqual(sum(1 for count in counts if count) / len(counts), SEEN, delta=0.03)
        lots = sum(1 for before, after in zip(counts, counts[1:]) if not before and after)
        self.assertAlmostEqual(lots, 4 * BURSTS, delta=1)

    def test_a_bolt_flies_out_from_over_the_head_and_never_across_the_face(self) -> None:
        for seed in range(12):
            flown: list[list[float]] = []
            for step in range(400):
                flying = bolts(step / 400, 1.0, seed)
                if not flying:
                    if flown and len(flown[-1]):
                        flown.append([])
                    continue
                if not flown:
                    flown.append([])
                flown[-1].append(_reach(flying[0]))
                for bolt in flying:
                    self.assertEqual(len(bolt.points), 7, "a bolt as in a strip: a tail, a step, a point")
                    for x, y in bolt.points:
                        self.assertLess(y, 0.0, "over the head")
                        self.assertGreaterEqual(math.hypot(x, y), STARTS * 0.95, "and clear of it")
                        self.assertLessEqual(-y, HIGHEST + 1e-9, "no higher than a name is put out of the way of")
            for lot in filter(None, flown):
                self.assertEqual(lot, sorted(lot), "further and further out")

    def test_they_are_over_the_side_the_other_is_on_and_the_same_in_a_mirror(self) -> None:
        towards = 0.0
        for step in range(200):
            right, left = bolts(step / 50, 3.0, 9), bolts(step / 50, -0.5, 9)
            self.assertEqual(len(right), len(left))
            for one, other in zip(right, left):
                for (x, y), (mirrored, same) in zip(one.points, other.points):
                    self.assertAlmostEqual(x, -mirrored)
                    self.assertAlmostEqual(y, same)
            towards += sum(x for bolt in right for x, _ in bolt.points)
        self.assertGreater(towards, 0.0, "more of them on the side of whoever they are for")
        self.assertEqual(bolts(0.1, 0.0, 9), bolts(0.1, 1.0, 9), "with the other dead ahead they go as to the right")


class BoltArtTests(unittest.TestCase):
    def setUp(self) -> None:
        previous = os.environ.get("SDL_VIDEODRIVER")
        os.environ["SDL_VIDEODRIVER"] = "dummy"
        self.addCleanup(lambda: os.environ.pop("SDL_VIDEODRIVER", None) if previous is None else os.environ.update(SDL_VIDEODRIVER=previous))
        pygame.init()
        self.addCleanup(pygame.quit)

    def _lit(self, picture: pygame.Surface, color) -> list[tuple[int, int]]:
        return [
            (x, y) for x in range(picture.get_width()) for y in range(picture.get_height()) if picture.get_at((x, y))[:3] == tuple(color)[:3]
        ]

    def test_bolts_are_drawn_bright_with_a_dark_line_round_them_at_any_size(self) -> None:
        flying = next(found for found in (bolts(step / 50, 1.0, 4) for step in range(50)) if found)
        areas = []
        for detail in (1.0, 3.0, 6.0):
            picture = pygame.Surface((round(40 * detail), round(40 * detail)))
            picture.fill((90, 120, 90))
            head = (20 * detail, 30 * detail)
            BoltArt().draw(picture, flying, head, detail)
            bright, dark = self._lit(picture, CORE), self._lit(picture, LINE)
            self.assertTrue(bright, detail)
            self.assertTrue(dark, detail)
            self.assertTrue(all(y < head[1] for _, y in bright + dark), "all of it over the head")
            # Every bright pixel has the dark line, or more of the bolt, on every side of it.
            ground = picture.map_rgb((90, 120, 90))
            for x, y in bright:
                for beside in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
                    self.assertNotEqual(picture.get_at_mapped(beside), ground, (detail, x, y))
            areas.append(len(bright))
        self.assertLess(areas[0], areas[1])
        self.assertLess(areas[1], areas[2])

    def test_with_nothing_in_the_air_nothing_is_drawn(self) -> None:
        picture = pygame.Surface((40, 40))
        picture.fill((90, 120, 90))
        before = pygame.image.tobytes(picture, "RGB")
        BoltArt().draw(picture, [], (20.0, 30.0), 2.0)
        self.assertEqual(pygame.image.tobytes(picture, "RGB"), before)


if __name__ == "__main__":
    unittest.main()
