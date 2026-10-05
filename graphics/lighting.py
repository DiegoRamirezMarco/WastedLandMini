"""Day and night: how dark it is by the clock, and the light that fires and lamps give.

Light is the one thing the game does not draw in palette colours. After dark the finished picture of
the map is multiplied by a light map: a dim blue everywhere, and warm and bright around whatever
gives light. To keep it pixel art the light map is built in blocks, and both the hours of twilight
and the edge of a light move in steps instead of fading smoothly.
"""

import pygame

from graphics.palette import Color

# Hours between which the light comes up in the morning and goes down at night.
DAWN = (5.5, 7.5)
DUSK = (19.5, 21.5)
# Twilight passes through this many steps of darkness.
STEPS = 8
# What the dead of night multiplies every colour by, and what the middle of a light does.
NIGHT: Color = (92, 100, 150)
FIRELIGHT: Color = (255, 238, 206)
# Side in map pixels of the blocks a pool of light is made of.
BLOCK = 4
# How bright each ring of a pool of light is, from its edge inwards.
RINGS = (0.5, 0.7, 0.88, 1.0)


def daylight(hour: int, minute: int = 0) -> float:
    """How much daylight there is, from 1 in full day to 0 in the dead of night, in steps."""
    time = hour + minute / 60.0
    if DAWN[1] <= time <= DUSK[0]:
        level = 1.0
    elif time >= DUSK[1] or time <= DAWN[0]:
        level = 0.0
    elif time < DAWN[1]:
        level = (time - DAWN[0]) / (DAWN[1] - DAWN[0])
    else:
        level = (DUSK[1] - time) / (DUSK[1] - DUSK[0])
    return round(level * STEPS) / STEPS


def ambient(level: float) -> Color:
    """What a given amount of daylight multiplies the scene by: white by day, the night's blue after dark."""
    return tuple(round(dark + (255 - dark) * level) for dark in NIGHT)


class LightMap:
    """Builds the light map for the part of the map in view, and keeps the pools of light it has drawn."""

    def __init__(self) -> None:
        self._pools: dict[int, pygame.Surface] = {}
        self._surfaces: dict[tuple[int, int], pygame.Surface] = {}

    def pool(self, radius: int) -> pygame.Surface:
        """A round pool of light of this radius in map pixels, on black, brightest in the middle."""
        if radius not in self._pools:
            cells = max(1, radius // BLOCK)
            small = pygame.Surface((cells * 2, cells * 2))
            for index, strength in enumerate(RINGS):
                reach = round(cells * (1.0 - index / len(RINGS)))
                color = tuple(round(channel * strength) for channel in FIRELIGHT)
                pygame.draw.circle(small, color, (cells, cells), reach)
            self._pools[radius] = pygame.transform.scale(small, (cells * 2 * BLOCK, cells * 2 * BLOCK))
        return self._pools[radius]

    def render(
        self, size: tuple[int, int], level: float, lights: list[tuple[tuple[int, int], int]]
    ) -> pygame.Surface:
        """The light map for a view of `size`: `lights` are centres in its pixels, each with a radius."""
        if size not in self._surfaces:
            self._surfaces[size] = pygame.Surface(size)
        surface = self._surfaces[size]
        surface.fill(ambient(level))
        for (x, y), radius in lights:
            pool = self.pool(radius)
            # The brighter of the two wins, so a light only shows where it beats what daylight is left.
            surface.blit(
                pool, (x - pool.get_width() // 2, y - pool.get_height() // 2), special_flags=pygame.BLEND_RGB_MAX
            )
        return surface


def shade(scene: pygame.Surface, light_map: pygame.Surface) -> None:
    """Darken a picture of the map by its light map, in place."""
    scene.blit(light_map, (0, 0), special_flags=pygame.BLEND_RGB_MULT)
