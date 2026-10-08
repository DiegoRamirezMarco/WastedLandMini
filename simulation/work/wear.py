"""Posts that wear and break down (S55).

A post wears as it is worked, the faster for being pushed, and when it is worn out it breaks
down: nobody can work at it or use it until it has been mended. A push that goes wrong can
break one outright (S52).

Mending is a site on the thing, laid by itself when it breaks: what it takes is carried to it
and worked on by whoever holds the job that mends, as anything is built (S16). How fast a
post wears and what mending takes are data.
"""

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from simulation.events.event import DomainEvent
from simulation.residents.resident import Resident
from world.build import REPAIR_SITE, BuildRule, BuildSite
from world.interactable import Interactable

if TYPE_CHECKING:
    from simulation.world import SimulationWorld

BROKE_EVENT = "post_broke"
MENDED_EVENT = "post_mended"
BROKE_IMPORTANCE = 45
MENDED_IMPORTANCE = 30
NOT_BROKEN = "Eso no está averiado"


@dataclass(frozen=True)
class WearSettings:
    # How much of its condition, of a hundred, a post loses in an hour of being worked, and by
    # how much that is multiplied while whoever works it is pushing.
    per_hour: float = 0.0
    pushed: float = 1.0
    # What mending one takes, by the tag of the items that will do, the minutes of work, and
    # the job whoever does it has to hold. None for anybody.
    cost: dict[str, int] = field(default_factory=dict)
    minutes: int = 0
    job: str | None = None

    @property
    def enabled(self) -> bool:
        return self.per_hour > 0


def wear_settings_from_data(data: dict[str, Any]) -> WearSettings:
    settings = WearSettings(
        per_hour=float(data.get("per_hour", 0.0)),
        pushed=float(data.get("pushed", 1.0)),
        cost={str(tag): int(units) for tag, units in data.get("cost", {}).items()},
        minutes=int(data.get("minutes", 0)),
        job=str(data["job"]) if data.get("job") else None,
    )
    if settings.per_hour < 0 or settings.pushed <= 0 or settings.minutes < 0:
        raise ValueError("A post wears by no less than nothing, the faster for a push, and is mended in no less than no time")
    if any(units < 0 for units in settings.cost.values()):
        raise ValueError("Mending takes no less than nothing")
    return settings


class WearSystem:
    def settings(self, world: "SimulationWorld") -> WearSettings:
        return world.registries.wear

    def wears(self, world: "SimulationWorld", placed: Interactable | None) -> bool:
        """Whether a thing is of a kind that wears: the post of some job."""
        return placed is not None and world.staffing.job_at(world, placed.object_id) is not None

    def broken(self, world: "SimulationWorld", object_id: str | None) -> bool:
        """Whether a thing has broken down, and so stands idle until it is mended."""
        placed = world.interactables.get(object_id or "")
        return placed is not None and placed.condition <= 0.0

    def worked(self, world: "SimulationWorld", resident: Resident, placed: Interactable) -> None:
        """A minute of work at a post takes its toll on it. Worn out, it breaks down."""
        settings = self.settings(world)
        if not settings.enabled or placed.condition <= 0.0:
            return
        toll = settings.per_hour / 60.0 * (settings.pushed if world.rush.pushed(world, resident) else 1.0)
        placed.condition = max(0.0, placed.condition - toll)
        if placed.condition <= 0.0:
            self.break_down(world, placed)

    def break_down(self, world: "SimulationWorld", placed: Interactable) -> None:
        """A post breaks down: it is said, and the ground is marked out for mending it."""
        placed.condition = 0.0
        definition = world.definition_of(placed)
        named = f"{definition.article} {definition.name}"
        world.emit_event(
            DomainEvent(
                BROKE_EVENT,
                BROKE_IMPORTANCE,
                f"Se avería {named}: hay que arreglarlo",
                data={"object_id": placed.object_id, "kind": placed.kind},
            ),
            at=(placed.x, placed.y),
        )
        if self.site_of(world, placed.object_id) is None and world.upgrades.site_of(world, placed.object_id) is None:
            world.construction.lay(world, REPAIR_SITE, placed.object_id, (placed.x, placed.y), self.mender(world))

    def tick(self, world: "SimulationWorld") -> None:
        """Once an hour: what is waiting to be mended with nobody to see to it is put in the
        hands of whoever mends, if there is anybody by now."""
        if world.clock.minute != 0 or not world.sites:
            return
        for site in world.sites.values():
            if site.kind == REPAIR_SITE and site.in_charge not in world.residents:
                site.in_charge = self.mender(world)

    def mender(self, world: "SimulationWorld") -> str | None:
        """Whoever mends what breaks down: the first who holds the job for it and is here and fit."""
        job_id = self.settings(world).job
        for resident in world.residents.values():
            if (job_id is None or resident.job_id == job_id) and not resident.away and world.health.is_fit_for_work(resident):
                return resident.resident_id
        return None

    # ----- the site it is mended at -----

    def site_of(self, world: "SimulationWorld", object_id: str) -> BuildSite | None:
        return next((site for site in world.sites.values() if site.kind == REPAIR_SITE and site.what == object_id), None)

    def obstacle(self, world: "SimulationWorld", object_id: str) -> str | None:
        """Why a thing cannot be set to be mended. None if it can."""
        if not self.broken(world, object_id):
            return NOT_BROKEN
        if self.site_of(world, object_id) is not None or world.upgrades.site_of(world, object_id) is not None:
            return "Ya hay una obra en ello"
        return None

    def rule(self, world: "SimulationWorld", object_id: str) -> BuildRule | None:
        if object_id not in world.interactables:
            return None
        settings = self.settings(world)
        return BuildRule(dict(settings.cost), settings.minutes, settings.job)

    def thing(self, world: "SimulationWorld", object_id: str) -> str | None:
        placed = world.interactables.get(object_id)
        if placed is None:
            return None
        definition = world.definition_of(placed)
        return f"arreglar {definition.article} {definition.name}"

    def finish(self, world: "SimulationWorld", site: BuildSite) -> str:
        """A thing has been mended: it is as good as new."""
        placed = world.interactables[site.what]
        placed.condition = 100.0
        definition = world.definition_of(placed)
        named = f"{definition.article} {definition.name}"
        world.emit_event(
            DomainEvent(
                MENDED_EVENT,
                MENDED_IMPORTANCE,
                f"{named[0].upper()}{named[1:]} vuelve a funcionar",
                data={"object_id": placed.object_id, "kind": placed.kind},
            ),
            at=(placed.x, placed.y),
        )
        return placed.object_id
