"""A small bar over a resident who is in the middle of a task: how far along they are with it."""

import pygame

from graphics.palette import PALETTE
from simulation.residents.resident import Resident
from simulation.work.construction import BUILD_ACTION
from simulation.work.salvage import SALVAGE_ACTION
from simulation.work.work_system import MINUTES_PER_DAY, WORK_ACTION
from simulation.world import SimulationWorld

BAR_SIZE = (16, 3)
# From afar there is less room over a head.
SMALL_BAR_SIZE = (9, 2)


def _shift_done(world: SimulationWorld, resident: Resident) -> float | None:
    """How much of the shift they are on has gone by. None off shift."""
    job = world.work.job_of(world, resident)
    if job is None:
        return None
    left = world.work.shift_minutes_left(world, resident, job)
    if left <= 0:
        return None
    now = world.clock.hour * 60 + world.clock.minute
    # The shift they are on is the one that began last.
    gone = min(((now - start * 60) % MINUTES_PER_DAY for start, _end in job.shifts), default=0)
    return gone / (gone + left)


def task_progress(world: SimulationWorld, resident: Resident) -> float | None:
    """How far along a resident is with their task, from 0 to 1. None while they are at none:
    on their way somewhere, strolling, talking, asleep, or doing nothing.

    A site and something being taken apart say how far along they are themselves. A shift at a
    post is as far along as the hours of it that have gone by, and the use of a thing as the
    time it takes. It reads the simulation and changes nothing.
    """
    activity = resident.activity
    if activity is None or not activity.using or resident.away:
        return None
    done: float | None = None
    if activity.action == BUILD_ACTION:
        site = world.sites.get(activity.target_id or "")
        done = world.construction.fraction_done(world, site) if site is not None else None
    elif activity.action == SALVAGE_ACTION:
        job = world.salvage.get(activity.target_id or "")
        placed = world.interactables.get(activity.target_id or "")
        rule = world.salvaging.rule_of(world, placed) if placed is not None else None
        done = job.progress / rule.minutes if job is not None and rule is not None else None
    elif activity.action == WORK_ACTION:
        done = _shift_done(world, resident)
    elif activity.partner_id is None and activity.target_id is not None:
        placed = world.interactables.get(activity.target_id)
        use = world.definition_of(placed).use if placed is not None else None
        # Nobody is timed in their sleep.
        if use is not None and not use.unaware and use.action == activity.action and use.minutes > 0:
            done = 1.0 - activity.minutes_left / use.minutes
    return max(0.0, min(1.0, done)) if done is not None else None


def task_bar_rect(top_centre: tuple[int, int], small: bool = False) -> pygame.Rect:
    """Where the bar goes: centred, just over the point given."""
    width, height = SMALL_BAR_SIZE if small else BAR_SIZE
    return pygame.Rect(top_centre[0] - width // 2, top_centre[1] - height - 1, width, height)


def draw_task_bar(target: pygame.Surface, rect: pygame.Rect, fraction: float) -> None:
    pygame.draw.rect(target, PALETTE["ink"], rect.inflate(2, 2))
    pygame.draw.rect(target, PALETTE["shadow"], rect)
    filled = round(rect.width * max(0.0, min(1.0, fraction)))
    if filled:
        pygame.draw.rect(target, PALETTE["lichen"], (rect.x, rect.y, filled, rect.height))
