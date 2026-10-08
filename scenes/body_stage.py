"""The bodies on the map: a character for each resident, and whatever a blow leaves lying about.

Nothing here is gameplay. The simulation says who was hurt, who lost what and who died; this shows
it, in real time and with randomness of its own, and none of it is saved.
"""

import math
import random
from collections.abc import Iterable
from dataclasses import dataclass

import pygame

from graphics.body_renderer import FRAME_ORIGIN, FRAME_SIZE, BodyRenderer
from settings import TILE_SIZE
from simulation.events.event import DomainEvent
from simulation.residents.resident import Resident
from simulation.world import SimulationWorld
from skeleton import physics
from skeleton.character import Character
from skeleton.motion import Life
from skeleton.rig import Skeleton

# Game minutes that a body, or a part of one, lies where it fell before it is taken away.
REMAINS_MINUTES = 90
# Speed a blow gives the joint it lands on, in pixels per second: a little for any blow, more the harder it was.
BLOW_SPEED = 60.0
BLOW_SPEED_PER_DAMAGE = 5.0
# How much of that speed goes upwards.
BLOW_LIFT = 0.45
# An injury at least this bad knocks whoever takes it off their feet, for this many seconds.
KNOCKDOWN_DAMAGE = 20.0
KNOCKDOWN_SECONDS = 1.6
# How many of the highest joints a blow may land on.
STRUCK_JOINTS = 4
# Speed a part flies off with, as a multiple of the blow that took it.
SEVER_SPEED = 0.4
# How fast it tumbles at the most, in radians per second, one way or the other.
SEVER_SPIN = 9.0
# Rows of a tile left below the feet of whoever stands on it.
FEET_ABOVE_EDGE = 2
# Real seconds after which somebody nobody has looked at is taken as found: whatever they are
# at, they are not seen to begin it.
UNSEEN_SECONDS = 0.5


# Rows of a head left visible when a resident lies in a bed: hair and eyes above the blanket.
LYING_HEAD_ROWS = 10
# Where the corner of that head goes on the bed, so that it rests on the pillow.
LYING_HEAD_OFFSET = (1, -2)
# The part of a doll that is its head, and where the neck of one lying in a bed is, from the
# bed's top left corner, in map pixels.
HEAD_BONE = "skull"
LYING_NECK = (7.5, 10.0)


# How much of its drawn size the body of somebody just old enough to walk is shown at. It
# comes up to all of it, a little at each birthday, by the age at which they are grown.
SMALLEST_BODY = 0.6
# How much of a doll's height is its head, which stays as it was drawn while the body is small.
HEAD_OF_HEIGHT = 0.3
# A child under ten, in its blanket: how wide it is in map pixels, how far behind whoever carries
# it and how high on their back, and how far off the ground a bed or a table has it.
BUNDLE_WIDTH = 10.0
BUNDLE_BEHIND = 4.0
BUNDLE_UP = 9.0
BUNDLE_RAISED = 5.0


def grown_share(world: SimulationWorld, resident: Resident) -> float:
    """How much of its drawn size a resident's body is shown at: all of it once they are grown."""
    grown = world.bonds.settings(world).adult_age
    walking = world.children.settings(world).grown_at
    if resident.age >= grown or grown <= walking:
        return 1.0
    years = max(0, resident.age - walking)
    return min(1.0, SMALLEST_BODY + (1.0 - SMALLEST_BODY) * years / (grown - walking))


def ground_spot(x: float, y: float) -> tuple[int, int]:
    """The map pixel between the feet of someone standing on a tile, given in tiles."""
    return (
        round(x * TILE_SIZE) + (TILE_SIZE - FRAME_SIZE[0]) // 2 + FRAME_ORIGIN[0],
        round(y * TILE_SIZE) + TILE_SIZE - FEET_ABOVE_EDGE - FRAME_SIZE[1] + FRAME_ORIGIN[1],
    )


def spot_tile(x: float, y: float) -> tuple[float, float]:
    """Where, in tiles, somebody stands whose feet are at a map pixel: `ground_spot` the other way."""
    return (
        (x - (TILE_SIZE - FRAME_SIZE[0]) // 2 - FRAME_ORIGIN[0]) / TILE_SIZE,
        (y - TILE_SIZE + FEET_ABOVE_EDGE + FRAME_SIZE[1] - FRAME_ORIGIN[1]) / TILE_SIZE,
    )


@dataclass
class Remains:
    """A dead body or a part of one, falling or lying where it fell."""

    body_id: str
    skeleton: Skeleton
    # Game minute at which it is taken away.
    until: int

    @property
    def tile(self) -> tuple[int, int]:
        left, _, right, _ = self.skeleton.bounds()
        return (int((left + right) / 2) // TILE_SIZE, int(self.skeleton.ground) // TILE_SIZE)


class BodyStage:
    def __init__(self, renderer: BodyRenderer, seed: int = 0) -> None:
        self.renderer = renderer
        self.plan = renderer.plan
        self.characters: dict[str, Character] = {}
        self.remains: list[Remains] = []
        self._random = random.Random(seed)
        self._seed = seed
        rest = self.plan.rests["front"]
        self._struck = sorted(rest, key=lambda joint: rest[joint][1])[:STRUCK_JOINTS]
        # How many things each resident had on them when they were last looked at.
        self._carried: dict[str, int] = {}
        # Seconds gone by for the bodies, as fast as the game is going, and in real time.
        self.clock = 0.0
        self._real = 0.0
        # For each resident: whether they lay on the ground when last looked at, when by the
        # bodies' clock they were seen to lie down or to get up, and when in real time they
        # were last looked at.
        self._rest: dict[str, tuple[bool, float, float]] = {}

    def character(self, resident: Resident, losing: str | None = None) -> Character:
        """The body of a resident, made the first time it is asked for, short of what they have lost.

        `losing` names a limb that is about to be seen coming off, and so is still on the body.
        """
        gone = [limb for limb in resident.lost_limbs if limb != losing]
        character = self.characters.get(resident.resident_id)
        if character is None:
            character = Character(self.plan, gone)
            character.stand(*ground_spot(resident.x, resident.y), resident.facing)
            # A life of their own, with a chance of its own: nobody breathes or fidgets in step.
            character.life = Life(random.Random(f"{self._seed}:{resident.resident_id}"))
            self.characters[resident.resident_id] = character
        for limb in gone:
            # Lost without this stage being told, as in a game just loaded: it is simply not there.
            if limb in self.plan.parts and limb not in character.lost:
                character.lost.append(limb)
        return character

    def took_or_gave(self, resident: Resident) -> bool:
        """Whether a resident has more on them, or less, than when they were last looked at:
        something has gone into their pockets or come out of them. Never the first time."""
        carried = sum(item.quantity for item in resident.inventory.items)
        before = self._carried.get(resident.resident_id)
        self._carried[resident.resident_id] = carried
        return before is not None and before != carried

    def rest(self, resident_id: str, lying: bool) -> tuple[bool, float]:
        """Whether a resident lies on the ground, as whoever asks says, and for how many seconds
        they have been seen to: since they were seen to lie down, or to get up. Somebody found
        already lying, or already up, has been so for ever."""
        known = self._rest.get(resident_id)
        if known is None or self._real - known[2] > UNSEEN_SECONDS:
            since = -math.inf
        else:
            since = self.clock if known[0] != lying else known[1]
        self._rest[resident_id] = (lying, since, self._real)
        return (lying, self.clock - since)

    def on_events(self, world: SimulationWorld, events: Iterable[DomainEvent]) -> None:
        """Show on the bodies what the simulation just did to them."""
        for event in events:
            if event.event_type == "death":
                self._fall_dead(world, event)
            elif event.event_type in ("injured", "limb_lost") and event.participants:
                self._strike(world, event)

    def _blow(self, world: SimulationWorld, event: DomainEvent, at: tuple[float, float]) -> tuple[float, float]:
        """The speed a blow gives, away from whoever dealt it."""
        amount = float(event.data.get("amount") or 0.0)
        speed = BLOW_SPEED + amount * BLOW_SPEED_PER_DAMAGE
        striker = world.residents.get(event.data.get("by") or "")
        if striker is not None and striker.x != at[0]:
            side = 1.0 if at[0] > striker.x else -1.0
        else:
            side = self._random.choice((-1.0, 1.0))
        return (side * speed, -speed * BLOW_LIFT)

    def _strike(self, world: SimulationWorld, event: DomainEvent) -> None:
        resident = world.residents.get(event.participants[0])
        if resident is None or resident.away:
            return
        limb = event.data.get("limb")
        character = self.character(resident, losing=limb)
        vx, vy = self._blow(world, event, (resident.x, resident.y))
        if limb is not None:
            spin = self._random.uniform(SEVER_SPIN / 3, SEVER_SPIN) * self._random.choice((-1.0, 1.0))
            part = character.sever(str(limb), vx * SEVER_SPEED, vy * SEVER_SPEED * 2, spin)
            if part is not None:
                self._leave(world, resident.resident_id, part.skeleton)
            elif limb not in character.lost and limb in self.plan.parts:
                character.lost.append(str(limb))
        joint = self._random.choice(self._struck)
        if float(event.data.get("amount") or 0.0) >= KNOCKDOWN_DAMAGE:
            character.knock_down(vx, vy, joint, KNOCKDOWN_SECONDS)
        else:
            character.hit(vx, vy, joint)

    def _fall_dead(self, world: SimulationWorld, event: DomainEvent) -> None:
        dead_id = event.data.get("resident_id")
        if dead_id is None:
            return
        character = self.characters.pop(str(dead_id), None)
        tile = event.data.get("tile")
        if tile is None:
            # They died beyond the fence: there is no body to show.
            return
        if character is None:
            character = Character(self.plan, event.data.get("lost_limbs") or ())
            character.stand(*ground_spot(tile[0], tile[1]), "down")
        vx, vy = self._blow(world, event, (tile[0], tile[1]))
        self._leave(world, str(dead_id), character.kill(vx, vy, self._random.choice(self._struck)))

    def _leave(self, world: SimulationWorld, body_id: str, skeleton: Skeleton) -> None:
        self.remains.append(Remains(body_id, skeleton, world.clock.total_minutes + REMAINS_MINUTES))

    def update(self, seconds: float, world: SimulationWorld) -> None:
        """Let real time pass for whatever is being moved by physics. The rest costs nothing."""
        for resident_id in [resident_id for resident_id in self.characters if resident_id not in world.residents]:
            del self.characters[resident_id]
        pace = max(1.0, float(world.clock.speed))
        self.clock += seconds * pace
        self._real += seconds
        for character in self.characters.values():
            # A body on springs keeps up with its clips however fast the game is going.
            character.pace = pace
            character.update(seconds)
        now = world.clock.total_minutes
        self.remains = [remains for remains in self.remains if remains.until > now]
        for remains in self.remains:
            physics.advance(remains.skeleton, seconds)

    def awake(self) -> int:
        """How many bodies and parts physics is moving right now."""
        moving = sum(1 for character in self.characters.values() if not character.at_rest)
        return moving + sum(1 for remains in self.remains if not remains.skeleton.asleep)

    def draw_remains(self, target: pygame.Surface, remains: Remains, origin: tuple[int, int]) -> None:
        """Draw a body or a part that is nobody's any more. `origin` is the map pixel at the target's corner."""
        self.renderer.draw_limp(target, remains.skeleton, remains.body_id, (-origin[0], -origin[1]))
