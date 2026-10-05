"""Makes a skeleton fall, swing and come to rest. Used only for bodies that are not being posed.

Position-based: each joint is moved by the speed it had and by gravity, then bones, limits and the
ground put right what that broke, a few times over. Nothing here is gameplay: it runs on real time.
"""

import math

from skeleton.plan import PhysicsSettings, Point
from skeleton.rig import Skeleton

_TURN = math.tau
_HALF_TURN = math.pi
# How near the ground a joint counts as lying on it, in pixels.
_TOUCHING = 0.05


def step(
    skeleton: Skeleton,
    settings: PhysicsSettings,
    targets: dict[str, Point] | None = None,
    pull: float = 0.0,
) -> None:
    """Move a skeleton forward by one step of `settings.step` seconds.

    With `targets`, each joint is drawn towards where a pose would have it, by `pull` from 0 to 1,
    and gravity lets go of it by as much: a body that is being held up, more or less firmly.
    """
    dt = settings.step
    joints = list(skeleton.joints.values())
    damping = settings.damping
    fall = settings.gravity * dt * dt * (1.0 - pull)
    ground = skeleton.ground
    keep = 1.0 - settings.friction
    bounce = settings.bounce
    fastest = 0.0
    for joint in joints:
        vx = (joint.x - joint.px) * damping
        vy = (joint.y - joint.py) * damping
        speed = vx * vx + vy * vy
        if speed > fastest:
            fastest = speed
        joint.px = joint.x
        joint.py = joint.y
        joint.x += vx
        joint.y += vy + fall
        floor = ground - joint.radius
        if joint.y > floor:
            # Landed: it loses its way along the ground and springs back a little.
            fell = joint.y - joint.py
            joint.y = floor
            joint.py = floor + fell * bounce
            joint.px = joint.x - (joint.x - joint.px) * keep

    if targets is not None and pull > 0.0:
        for joint in joints:
            target = targets.get(joint.name)
            if target is not None:
                joint.x += (target[0] - joint.x) * pull
                joint.y += (target[1] - joint.y) * pull

    held = [*skeleton.bones.values(), *skeleton.braces]
    limits = skeleton.limits
    spacers = skeleton.spacers
    stiffness = settings.limit_stiffness
    for _ in range(settings.iterations):
        for bone in held:
            a, b = bone.a, bone.b
            dx = b.x - a.x
            dy = b.y - a.y
            distance = math.sqrt(dx * dx + dy * dy)
            weight = a.inv_mass + b.inv_mass
            if distance < 1e-6 or weight <= 0.0:
                continue
            slack = (distance - bone.length) / distance / weight
            a.x += dx * slack * a.inv_mass
            a.y += dy * slack * a.inv_mass
            b.x -= dx * slack * b.inv_mass
            b.y -= dy * slack * b.inv_mass
        for spacer in spacers:
            a, b = spacer.a, spacer.b
            dx = b.x - a.x
            dy = b.y - a.y
            distance = math.sqrt(dx * dx + dy * dy)
            weight = a.inv_mass + b.inv_mass
            if distance >= spacer.length or distance < 1e-6 or weight <= 0.0:
                continue
            slack = (distance - spacer.length) / distance / weight
            a.x += dx * slack * a.inv_mass
            a.y += dy * slack * a.inv_mass
            b.x -= dx * slack * b.inv_mass
            b.y -= dy * slack * b.inv_mass
        for limit in limits:
            bone, ref = limit.bone, limit.ref
            a, b = bone.a, bone.b
            dx = b.x - a.x
            dy = b.y - a.y
            rx = ref.b.x - ref.a.x
            ry = ref.b.y - ref.a.y
            if (dx == 0.0 and dy == 0.0) or (rx == 0.0 and ry == 0.0):
                continue
            if limit.ref_reversed:
                rx, ry = -rx, -ry
            turned = (math.atan2(dx, dy) - math.atan2(rx, ry) + _HALF_TURN) % _TURN - _HALF_TURN
            if turned < limit.low:
                back = (limit.low - turned) * stiffness
            elif turned > limit.high:
                back = (limit.high - turned) * stiffness
            else:
                continue
            # The ground has the last word: an end that lies on it stays, and the other one turns.
            # With both ends down the bone is lying flat and there is nothing left to put right.
            sine, cosine = math.sin(back), math.cos(back)
            if b.y < ground - b.radius - _TOUCHING:
                b.x = a.x + dx * cosine + dy * sine
                b.y = a.y - dx * sine + dy * cosine
            elif a.y < ground - a.radius - _TOUCHING:
                a.x = b.x - dx * cosine - dy * sine
                a.y = b.y + dx * sine - dy * cosine
        for joint in joints:
            floor = ground - joint.radius
            if joint.y > floor:
                joint.y = floor

    if targets is not None:
        skeleton.still_for = skeleton.limp_for = 0.0
        return
    skeleton.limp_for += dt
    skeleton.still_for = skeleton.still_for + dt if fastest < (settings.sleep_speed * dt) ** 2 else 0.0
    # It sleeps once it lies still, or once it has had time enough to: a twitch must not keep it up.
    if skeleton.still_for >= settings.sleep_after or skeleton.limp_for >= settings.rest_after:
        skeleton.asleep = True
        for joint in joints:
            joint.px = joint.x
            joint.py = joint.y


def advance(
    skeleton: Skeleton,
    seconds: float,
    targets: dict[str, Point] | None = None,
    pull: float = 0.0,
) -> int:
    """Give a skeleton `seconds` of real time, in whole steps. Returns how many it took.

    A skeleton that is asleep takes none. Time that does not fill a step is kept for the next call,
    and a long stall is not caught up with.
    """
    if skeleton.asleep:
        skeleton.lag = 0.0
        return 0
    settings = skeleton.plan.physics
    skeleton.lag = min(skeleton.lag + seconds, settings.step * settings.max_steps)
    taken = 0
    while skeleton.lag >= settings.step and not skeleton.asleep:
        step(skeleton, settings, targets, pull)
        skeleton.lag -= settings.step
        taken += 1
    return taken
