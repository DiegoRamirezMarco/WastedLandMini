"""Somebody in the player's hand (P27): who is being carried about, how they hang from the
pointer, and what is said of where they would be put down.

It is all for show. What a drop does is the simulation's to say and to do (`simulation.ai.placing`).
"""

import math
from dataclasses import dataclass, field

import pygame

from graphics.font import LINE_HEIGHT, BitmapFont
from graphics.palette import PALETTE
from simulation.ai.placing import POST, SWAP, Placement
from ui.job_board import describe_expected
from ui.panel import draw_panel
from world.map import Tile

Point = tuple[float, float]

# How far under the pointer, in map pixels, the feet of somebody carried hang: they are held by
# the scruff of the neck.
HANG = 19.0
# The swing of whoever hangs from the pointer: how hard they are pulled back under it, how fast
# the swing dies down, how far a canvas pixel a second of the hand throws them, and the furthest
# they are thrown, in radians.
SWING_PULL = 70.0
SWING_DAMPING = 5.0
SWING_THROW = 0.006
SWING_MOST = 1.0
# What hangs furthest from the hand swings further than what is near it, as a rag does.
SWING_TRAIL = 0.6
# Canvas pixels from the edge of the map within which a hand that is carrying pulls the view along.
EDGE = 5
CAPTION_PADDING = 3
# How far down whoever is in the hand counts as standing: in front of everything else.
IN_HAND_DEPTH = 1e9
OUT_OF_HOURS = "fuera de turno"
NEXT_KEY = "Tab"
NO_PLACE = "Aquí no"
HINT = "Suelta donde quieras · Esc: dejarlo como estaba"
INTO = "Entrar en {name} con {who}"


@dataclass(frozen=True)
class Target:
    """What the hand is over: a thing, somebody, a site, a building to go into, or only a tile.
    `box` is where it is on the canvas, to be picked out."""

    object_id: str | None = None
    other_id: str | None = None
    site_id: str | None = None
    room_id: str | None = None
    tile: Tile | None = None
    box: pygame.Rect | None = None

    @property
    def key(self) -> tuple:
        return (self.object_id, self.other_id, self.site_id, self.room_id, self.tile)


@dataclass
class Carry:
    """Whoever is in the player's hand, until they are put down or let go of."""

    # A resident, or a child who is still a bundle, by ID.
    who: str
    bundle: bool = False
    # Whether the game stood still already when they were taken up: it goes back to that.
    paused: bool = False
    # Whether they are carried with no button held, and a click puts them down. So it is once
    # a building has been gone into with them.
    sticky: bool = False
    # What the hand is over, what could come of letting go there, and which of it is chosen.
    target: Target | None = None
    found: list[Placement] = field(default_factory=list)
    choice: int = 0
    # How far from straight down they hang, in radians, and how fast that is changing.
    angle: float = 0.0
    speed: float = 0.0
    _last_x: float | None = None

    @property
    def chosen(self) -> Placement | None:
        return self.found[self.choice % len(self.found)] if self.found else None

    def over(self, target: Target | None, found: list[Placement]) -> None:
        """Say what the hand is over now. With something else under it, the choice starts again."""
        if target is None or self.target is None or target.key != self.target.key:
            self.choice = 0
        self.target, self.found = target, found

    def turn(self) -> None:
        """Go on to the next thing that could come of letting go here."""
        if len(self.found) > 1:
            self.choice = (self.choice + 1) % len(self.found)

    def swing(self, pointer_x: float, seconds: float) -> None:
        """Let real time pass for whoever hangs: thrown back by how fast the hand moves, and
        drawn under it again."""
        if self._last_x is None or seconds <= 0.0:
            self._last_x = pointer_x
            return
        thrown = max(-SWING_MOST, min(SWING_MOST, (pointer_x - self._last_x) / seconds * SWING_THROW))
        self._last_x = pointer_x
        # In small steps, so that a long frame does not send them flying.
        left = min(seconds, 0.1)
        while left > 0.0:
            step = min(left, 1 / 120)
            self.speed += ((thrown - self.angle) * SWING_PULL - self.speed * SWING_DAMPING) * step
            self.angle += self.speed * step
            left -= step
        self.angle = max(-SWING_MOST * 1.3, min(SWING_MOST * 1.3, self.angle))


def hung(points: dict[str, Point], pivot: Point, angle: float) -> dict[str, Point]:
    """Where the joints of a body are when it hangs from `pivot` and has swung `angle` from
    straight down. What is further from the hand trails behind what is nearer."""
    if not points:
        return {}
    furthest = max(math.hypot(x - pivot[0], y - pivot[1]) for x, y in points.values()) or 1.0
    swung = {}
    for name, (x, y) in points.items():
        dx, dy = x - pivot[0], y - pivot[1]
        turn = angle * (1.0 + SWING_TRAIL * math.hypot(dx, dy) / furthest)
        cos, sin = math.cos(turn), math.sin(turn)
        swung[name] = (pivot[0] + dx * cos - dy * sin, pivot[1] + dx * sin + dy * cos)
    return swung


def caption(carry: Carry, into: str | None = None) -> tuple[list[str], bool]:
    """What is said by the hand: what would come of letting go here, and under it what else
    could. And whether it can be done at all."""
    if into is not None:
        return [into], True
    chosen = carry.chosen
    if chosen is None:
        return [HINT if carry.target is None else NO_PLACE], carry.target is None
    text = chosen.text
    if chosen.kind in (POST, SWAP) and chosen.ok:
        if chosen.expected is not None:
            text = f"{text} · {describe_expected(chosen.expected)}"
        if not chosen.at_once:
            text = f"{text} ({OUT_OF_HOURS})"
    lines = [text]
    if len(carry.found) > 1:
        other = carry.found[(carry.choice + 1) % len(carry.found)]
        lines.append(f"{NEXT_KEY}: {other.text}")
    return lines, chosen.ok


def caption_rect(font: BitmapFont, lines: list[str], pointer: tuple[int, int], bounds: pygame.Rect) -> pygame.Rect:
    """Where the caption goes: over the hand and to its right, clear of whoever hangs
    under it, and kept on the screen."""
    width = max(font.width(line) for line in lines) + CAPTION_PADDING * 2
    height = LINE_HEIGHT * len(lines) + CAPTION_PADDING * 2
    rect = pygame.Rect(pointer[0] + 10, pointer[1] - height - 4, width, height)
    return rect.clamp(bounds) if bounds.width >= rect.width and bounds.height >= rect.height else rect


def draw_caption(
    target: pygame.Surface, font: BitmapFont, lines: list[str], ok: bool, pointer: tuple[int, int], bounds: pygame.Rect
) -> pygame.Rect:
    rect = caption_rect(font, lines, pointer, bounds)
    draw_panel(target, rect)
    y = rect.y + CAPTION_PADDING
    for index, line in enumerate(lines):
        color = PALETTE["dust"] if index else PALETTE["paper" if ok else "ember"]
        font.draw(target, line, (rect.x + CAPTION_PADDING, y), color)
        y += LINE_HEIGHT
    return rect


def draw_footing(target: pygame.Surface, box: pygame.Rect) -> None:
    """Mark the ground somebody would be stood on, given where its tile is on the canvas."""
    ring = pygame.Rect(0, 0, max(5, box.width * 2 // 3), max(3, box.height // 3))
    ring.midbottom = (box.centerx, box.bottom - max(1, box.height // 8))
    pygame.draw.ellipse(target, PALETTE["lichen"], ring, 1)


def draw_pick(target: pygame.Surface, box: pygame.Rect, ok: bool) -> None:
    """Pick out what the hand is over."""
    color = PALETTE["lichen" if ok else "ember"]
    pygame.draw.rect(target, color, box.inflate(2, 2), 1, border_radius=2)
