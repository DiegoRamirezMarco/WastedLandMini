import os
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame

from graphics import hose as rubber
from graphics.doll import DollPart
from graphics.volume import wrapped

SKIN = (214, 170, 130)


def part_solid(surface: pygame.Surface) -> int:
    """How many pixels of a picture are neither clear nor solid: those of a soft edge."""
    faint = pygame.mask.from_surface(surface, 8).count()
    solid = pygame.mask.from_surface(surface, 246).count()
    return faint - solid


@unittest.skipUnless(rubber.AVAILABLE, "no numpy")
class SmoothTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        pygame.init()
        pygame.display.set_mode((1, 1))

    def limb(self) -> pygame.Surface:
        image = pygame.Surface((40, 120), pygame.SRCALPHA)
        pygame.draw.line(image, SKIN, (20, 12), (20, 108), 18)
        pygame.draw.circle(image, SKIN, (20, 12), 9)
        pygame.draw.circle(image, SKIN, (20, 108), 9)
        return image

    def test_a_limb_looked_at_more_closely_has_a_softer_edge_and_is_no_other_size(self) -> None:
        strip = rubber.read_strip(self.limb(), [(20, 12), (20, 60), (20, 108)])
        points = [(0.0, 0.0), (26.0, 40.0), (4.0, 86.0)]
        rough, joint = rubber.bent(strip, points)
        smooth, at = rubber.bent(strip, points, closer=1.4)
        self.assertEqual(rough.get_size(), smooth.get_size())
        self.assertEqual(joint, at)
        # As much of it, to within its edge, and more of that edge neither there nor not.
        whole = pygame.mask.from_surface(rough, 127).count()
        self.assertAlmostEqual(pygame.mask.from_surface(smooth, 127).count(), whole, delta=whole * 0.04)
        self.assertGreater(part_solid(smooth), part_solid(rough) * 1.3)

    def test_a_picture_made_large_is_brought_down_with_its_joint(self) -> None:
        strip = rubber.read_strip(pygame.transform.scale_by(self.limb(), 2), [(40, 24), (40, 120), (40, 216)])
        large = rubber.bent(strip, [(0.0, 0.0), (52.0, 80.0), (8.0, 172.0)])
        image, joint = rubber.brought_down(large, 2)
        self.assertEqual(image.get_size(), (-(-large[0].get_width() // 2), -(-large[0].get_height() // 2)))
        self.assertEqual(joint, (large[1][0] / 2, large[1][1] / 2))
        # Its colour is its own to the edge: nothing clear has darkened it.
        box = image.get_bounding_rect(1)
        for x in range(box.left, box.right):
            for y in range(box.top, box.bottom):
                red, green, blue, alpha = image.get_at((x, y))
                if alpha > 20:
                    self.assertGreater(red + green + blue, sum(SKIN) - 30, (x, y, alpha))
        self.assertIs(rubber.brought_down(large, 1), large)

    def test_a_trunk_wrapped_round_has_an_edge_that_is_part_of_a_pixel(self) -> None:
        # A trunk that slants: wider at the top than at the foot.
        image = pygame.Surface((90, 120), pygame.SRCALPHA)
        pygame.draw.polygon(image, SKIN, [(8, 6), (82, 6), (62, 114), (28, 114)])
        part = DollPart(image, (45.0, 110.0), (45.0, 10.0))
        turned = wrapped(part, 45.0, 0.6).image
        self.assertGreater(part_solid(turned), 60)
        # It is as tall as it was, and narrower for being seen part of the way round.
        self.assertEqual(turned.get_height(), image.get_height())
        self.assertLess(turned.get_bounding_rect().width, image.get_bounding_rect().width)


if __name__ == "__main__":
    unittest.main()
