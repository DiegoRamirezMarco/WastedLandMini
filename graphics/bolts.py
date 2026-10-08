"""What flies from somebody who is having words with another: jagged bolts, as in a strip.

Nothing is kept from one frame to the next. Where a bolt is and which way it points follows
from whose it is and how long the scene has been going, so the same moment is always drawn
the same.
"""

import math
from dataclasses import dataclass

import pygame

from graphics.cartoon import LINE
from graphics.palette import PALETTE, Color

Point = tuple[float, float]

# How many times a second bolts are let fly, how many each time, and for how much of the time
# between one lot and the next they are seen.
BURSTS = 2.2
BOLTS = 3
SEEN = 0.7
# Pixels of the map's art: how far from the middle of the head the tail of a bolt starts, how
# far it gets, and how long the bolt is.
STARTS = 5.5
FLIES = (6.5, 8.5)
LONG = (5.0, 6.0)
# Which way they go, in a fan over the head: from well towards the other to a little away
# from them, so that no face is hidden and the bolts of two who quarrel are not in a heap.
RISES = (math.radians(42), math.radians(124))
# The outline of a bolt: how far along it each corner is, from its tail at 0 to its point at
# 1, and how far to one side of its way, in lengths of it. Broad at the tail, a step half-way.
SHAPE = ((0.0, -0.03), (0.56, -0.25), (0.56, -0.06), (1.0, -0.13), (0.4, 0.25), (0.4, 0.04), (0.0, 0.18))
# How far above the middle of the head a bolt ever gets: a name is written above that.
HIGHEST = max(math.hypot(FLIES[1] + along * LONG[1], aside * LONG[1]) for along, aside in SHAPE)
# How thick the dark line round it is.
EDGE = 0.4
CORE: Color = PALETTE["glow"]
# The pixels next to one, itself among them.
AROUND = tuple((aside, under) for aside in (-1, 0, 1) for under in (-1, 0, 1))


@dataclass(frozen=True)
class Bolt:
    # The corners of its outline in turn, from the middle of the head, in pixels of the map's art.
    points: tuple[Point, ...]


def _chance(seed: int) -> float:
    """A number from 0 to 1 that is always the same for the same seed, and nothing like its neighbours'."""
    seed &= 0xFFFFFFFF
    seed = (seed ^ 61) ^ (seed >> 16)
    seed = (seed * 9) & 0xFFFFFFFF
    seed ^= seed >> 4
    seed = (seed * 0x27D4EB2D) & 0xFFFFFFFF
    seed ^= seed >> 15
    return seed / 0xFFFFFFFF


def bolts(seconds: float, towards: float, seed: int = 0) -> list[Bolt]:
    """The bolts in the air at one moment of a quarrel, over the head of one of those having it.

    `towards` is which side the other is on, ahead of 0 to the right and behind it to the
    left, and `seed` tells one head from another, so that no two let theirs fly in step.
    """
    side = -1.0 if towards < 0 else 1.0
    turn = seconds * BURSTS + _chance(seed * 7919 + 13)
    burst, age = math.floor(turn), turn % 1.0
    if age >= SEEN:
        return []
    # Out fast, and slower as they go.
    out = 1.0 - (1.0 - age / SEEN) ** 2
    flying = []
    for index in range(BOLTS):
        key = seed * 131071 + burst * 8191 + index * 127
        # Each has a part of the fan to itself, so that no two lie on one another.
        share = (index + 0.2 + 0.6 * _chance(key)) / BOLTS
        rise = RISES[0] + (RISES[1] - RISES[0]) * share
        way = (math.cos(rise), -math.sin(rise))
        across = (-way[1], way[0])
        long = LONG[0] + (LONG[1] - LONG[0]) * _chance(key + 1)
        far = STARTS + (FLIES[0] + (FLIES[1] - FLIES[0]) * _chance(key + 2) - STARTS) * out
        # Its step is to one side or to the other.
        lean = long if _chance(key + 3) < 0.5 else -long
        flying.append(
            Bolt(
                tuple(
                    # Towards the left it is the same in a mirror.
                    (side * (way[0] * (far + along * long) + across[0] * aside * lean), way[1] * (far + along * long) + across[1] * aside * lean)
                    for along, aside in SHAPE
                )
            )
        )
    return flying


class BoltArt:
    """Draws bolts wherever they are wanted, at whatever size a pixel of the map's art is there."""

    def draw(self, target: pygame.Surface, flying: list[Bolt], at: Point, detail: float) -> None:
        """Draw bolts on a surface where a pixel of the map's art is `detail` of its own and
        the middle of the head they fly from is at `at`."""
        edge = max(1.0, EDGE * detail)
        # An odd number of pixels, so that the line is as thick to one side of the shape as to the other.
        stroke = 2 * round(edge) + 1
        shapes = [[(round(at[0] + x * detail), round(at[1] + y * detail)) for x, y in bolt.points] for bolt in flying]
        # The dark line of all of them first: where two cross they are one shape, as drawn.
        for shape in shapes:
            # A pixel of it on every side however small it is drawn, and the rest of its thickness over that.
            for aside, under in AROUND:
                pygame.draw.polygon(target, LINE, [(x + aside, y + under) for x, y in shape])
            pygame.draw.lines(target, LINE, True, shape, stroke)
            for corner in shape:
                pygame.draw.circle(target, LINE, corner, edge)
        for shape in shapes:
            pygame.draw.polygon(target, CORE, shape)
