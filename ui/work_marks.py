"""Work as it is seen on the map (P59): a ring over a post that fills as the next unit comes,
and each unit seen to come out of it.

It reads the simulation and the settlement's books, and changes nothing.
"""

from dataclasses import dataclass

import pygame

from graphics.font import BitmapFont
from graphics.palette import PALETTE
from graphics.ui_skin import WindowSkin
from simulation.economy.ledger import MADE, SPOILED
from simulation.world import SimulationWorld

# The side of a ring, on the canvas, from near and from afar, and how many steps it fills
# in: one picture is kept for each.
RING = 11
SMALL_RING = 7
RING_STEPS = 24
PLAIN_COLOR, PUSHED_COLOR = "lichen", "ember"
# How long a unit that came out is seen over its post, in real seconds, how far it rises, and
# how many are shown at once however fast time goes.
POP_SECONDS = 1.6
POP_RISE = 12
MOST_POPS = 24
ICON = 8


def draw_ring(
    target: pygame.Surface,
    skin: WindowSkin,
    centre: tuple[int, int],
    share: float,
    pushed: bool = False,
    side: int = RING,
) -> pygame.Rect:
    """A ring about a point of the canvas, with that share of it filled: as fine as the window
    shows it, or else at the size of the canvas. Whoever is being pushed has it in red."""
    rect = pygame.Rect(0, 0, side, side)
    rect.center = centre
    filled = round(max(0.0, min(1.0, share)) * RING_STEPS) / RING_STEPS
    color = PALETTE[PUSHED_COLOR if pushed else PLAIN_COLOR]
    scale = skin.layers.scale if skin.layers is not None else 1
    if not (skin.usable and skin.picture(target, skin.ring(rect.width * scale, filled, color, pushed), rect)):
        target.blit(pygame.transform.smoothscale(skin.ring(rect.width * 4, filled, color, pushed), rect.size), rect)
    return rect


@dataclass
class Pop:
    """Something that has just come out of a post, or been lost at one, while it is on show."""

    definition_id: str
    units: int
    # The post it came out of, and who made it.
    at: str | None
    by: str | None
    born: float


class WorkPops:
    """What has come out of posts lately, as the settlement's books wrote it down."""

    def __init__(self) -> None:
        self.pops: list[Pop] = []
        # How many entries of the books had been written when they were last looked at.
        self._seen: int | None = None

    def take(self, world: SimulationWorld, now: float) -> None:
        """Pick up what has been made, or lost, at a post since the books were last looked at.
        `now` is the scene's own time, in real seconds."""
        written = world.ledger.written
        if self._seen is None or written < self._seen:
            # The first look, or another settlement: what was written before is not news.
            self._seen = written
        fresh = list(world.ledger.recent)[len(world.ledger.recent) - min(written - self._seen, len(world.ledger.recent)) :]
        self._seen = written
        for entry in fresh:
            reason = entry.why.partition(":")[0]
            if entry.at is not None and reason in (MADE, SPOILED) and round(entry.units):
                self.pops.append(Pop(entry.definition_id, round(entry.units), entry.at, entry.by, now))
        self.pops = [pop for pop in self.pops if 0.0 <= now - pop.born < POP_SECONDS][-MOST_POPS:]

    def draw(self, target: pygame.Surface, font: BitmapFont, pop: Pop, spot: tuple[int, int], now: float, icon: pygame.Surface) -> None:
        """One of them, over the point of the canvas its post is seen at: its picture and how
        many, rising and fading as it goes."""
        age = max(0.0, min(1.0, (now - pop.born) / POP_SECONDS))
        text = f"+{pop.units}" if pop.units > 0 else str(pop.units)
        words = font.render(text, PALETTE["glow" if pop.units > 0 else "ember"])
        width = ICON + 1 + words.get_width()
        left, top = spot[0] - width // 2, spot[1] - ICON - round(POP_RISE * age)
        alpha = 255 if age < 0.6 else round(255 * (1.0 - age) / 0.4)
        for picture, place in ((icon, (left, top)), (words, (left + ICON + 1, top - 1))):
            shown = picture.copy()
            shown.set_alpha(alpha)
            target.blit(shown, place)
