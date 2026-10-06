"""What flies from a mouthful: where each crumb is, how it is turned and how faint, at any moment of a meal.

Nothing is kept from one frame to the next. A crumb's whole flight follows from which bite it is
and which crumb of it, so the same moment is always drawn the same way.
"""

import math
from dataclasses import dataclass

import pygame

# Where in a turn of the eating clip the teeth close: the hand has had the food at the mouth a moment.
BITE_AT = 0.36
# How long the crumbs of a bite are seen, in turns of the clip: they fly, land, hop, lie and fade.
# Less than a turn, so that they are gone before the next bite.
LIFE = 0.95
FADES_OVER = 0.2
CRUMBS = 12
# How late the last crumb leaves the mouth, in turns.
LATEST = 0.06
# Pixels of the map's art to a turn of the clip: how fast a crumb leaves sideways and upwards,
# and how hard it is pulled down.
SIDEWAYS = (2.0, 19.0)
UPWARDS = (0.0, 34.0)
PULL = 200.0
# How far in front of the mouth they start, and how far from one another.
STARTS = 1.0
APART = 1.2
# The ground is not a line: a crumb lands a little nearer or farther than the feet.
DEPTH = (-1.5, 1.5)
# How much of the speed it lands with a crumb hops back up with, and keeps sideways.
HOP = 0.25
# How large a crumb is across, in pixels of the map's art. Most are small.
ACROSS = (0.7, 2.0)
# Turns of its own a crumb makes in a turn of the clip, at the most, one way or the other.
SPIN = 2.5

# What a crumb looks like: corners round its middle, as shares of half its width.
SHAPES = (
    ((-1.0, -0.3), (-0.2, -1.0), (0.9, -0.5), (0.6, 0.8), (-0.6, 0.7)),
    ((-0.9, 0.6), (0.0, -1.0), (1.0, 0.7)),
    ((-1.0, -0.6), (0.8, -0.9), (1.0, 0.5), (-0.5, 0.9)),
    ((-0.7, -0.9), (0.9, -0.2), (0.3, 1.0), (-1.0, 0.3)),
)
# How many ways round a crumb's picture is kept.
TURNS = 16
# A crumb is drawn this many times too large and brought down, so that its edge is soft.
FINER = 4
# Under this many pixels across there is no shape to give it: it is a square.
SMALLEST_SHAPED = 4
# The side of a crumb away from the light is this much of its colour.
SHADED = 0.62


@dataclass(frozen=True)
class Crumb:
    # Where it is from the mouth, in pixels of the map's art.
    x: float
    y: float
    across: float
    # How far round it has turned, in radians.
    turned: float
    # How solid it still is, out of 255.
    alpha: int
    # Which of the food's colours it is and which shape, as numbers to count round them with.
    shade: int
    shape: int


def _chance(seed: int) -> float:
    """A number from 0 to 1 that is always the same for the same seed, and nothing like its neighbours'."""
    seed &= 0xFFFFFFFF
    seed = (seed ^ 61) ^ (seed >> 16)
    seed = (seed * 9) & 0xFFFFFFFF
    seed ^= seed >> 4
    seed = (seed * 0x27D4EB2D) & 0xFFFFFFFF
    seed ^= seed >> 15
    return seed / 0xFFFFFFFF


def _between(span: tuple[float, float], share: float) -> float:
    return span[0] + (span[1] - span[0]) * share


def crumbs(turn: float, forward: int, ground: float, count: int = CRUMBS) -> list[Crumb]:
    """The crumbs about at a moment of a meal, `turn` being how many turns of the eating clip have gone.

    `forward` is the way the eater faces: 1 for the right of the screen, -1 for the left, 0 for
    towards or away from the viewer, when crumbs go to both sides. `ground` is how far under the
    mouth the feet are: a crumb falls that far, hops once and lies there until it fades.
    """
    bite = math.floor(turn - BITE_AT)
    since = turn - BITE_AT - bite
    if since > LIFE:
        return []
    alpha = round(255 * min(1.0, (LIFE - since) / FADES_OVER))
    about = []
    for index in range(count):
        late, fast, high, big, spin, deep, off = (
            _chance(bite * 7919 + index * 104729 + draw * 31) for draw in range(7)
        )
        age = since - late * LATEST
        if age < 0.0:
            continue
        way = forward or (1 if index % 2 else -1)
        along, up = _between(SIDEWAYS, fast), _between(UPWARDS, high)
        floor = max(1.0, ground + _between(DEPTH, deep))
        lands = (up + math.sqrt(up * up + 2.0 * PULL * floor)) / PULL
        if age < lands:
            x, y, turning = along * age, -up * age + PULL * age * age / 2.0, age
        else:
            leaves = (PULL * lands - up) * HOP
            hopping = min(age - lands, 2.0 * leaves / PULL)
            x = along * (lands + HOP * hopping)
            y = floor - leaves * hopping + PULL * hopping * hopping / 2.0
            turning = lands + HOP * hopping
        about.append(
            Crumb(
                x=way * (STARTS + x) + (off - 0.5) * APART,
                y=y + (late - 0.5) * APART,
                across=_between(ACROSS, big * big),
                turned=math.tau * (spin * 2.0 - 1.0) * SPIN * turning + math.tau * off,
                alpha=alpha,
                shade=index,
                shape=index + bite,
            )
        )
    return about


class CrumbArt:
    """Draws crumbs: little chips of the food's own colours, lit from above, kept once made."""

    def __init__(self) -> None:
        self._pictures: dict[tuple[tuple[int, int, int], int, int, int], pygame.Surface] = {}

    def draw(
        self,
        target: pygame.Surface,
        flying: list[Crumb],
        colors: list[tuple[int, int, int]],
        mouth: tuple[float, float],
        detail: float,
    ) -> None:
        """Draw crumbs round a mouth at `mouth` on the surface, where a map pixel is `detail` of its own."""
        for crumb in flying:
            across = max(1, round(crumb.across * detail))
            step = round(crumb.turned / math.tau * TURNS) % TURNS
            picture = self._picture(colors[crumb.shade % len(colors)], crumb.shape % len(SHAPES), across, step)
            picture.set_alpha(crumb.alpha)
            centre = (round(mouth[0] + crumb.x * detail), round(mouth[1] + crumb.y * detail))
            target.blit(picture, picture.get_rect(center=centre))

    def _picture(self, color: tuple[int, int, int], shape: int, across: int, step: int) -> pygame.Surface:
        if across < SMALLEST_SHAPED:
            shape = step = 0
        key = (color, shape, across, step)
        if key not in self._pictures:
            self._pictures[key] = self._make(color, shape, across, step)
        return self._pictures[key]

    @staticmethod
    def _make(color: tuple[int, int, int], shape: int, across: int, step: int) -> pygame.Surface:
        if across < SMALLEST_SHAPED:
            picture = pygame.Surface((across, across), pygame.SRCALPHA)
            picture.fill(color)
            return picture
        fine = across * FINER
        half = fine / 2.0
        sine, cosine = math.sin(math.tau * step / TURNS), math.cos(math.tau * step / TURNS)
        corners = [
            (half + (x * cosine - y * sine) * (half - 1.0), half + (x * sine + y * cosine) * (half - 1.0))
            for x, y in SHAPES[shape]
        ]
        large = pygame.Surface((fine, fine), pygame.SRCALPHA)
        dark = tuple(round(channel * SHADED) for channel in color)
        pygame.draw.polygon(large, dark, corners)
        # The lit face is the same chip, smaller and nearer the light, which is up and to the left.
        lit = [(half * 0.8 + (x - half) * 0.72, half * 0.8 + (y - half) * 0.72) for x, y in corners]
        pygame.draw.polygon(large, color, lit)
        return pygame.transform.smoothscale(large, (across, across))
