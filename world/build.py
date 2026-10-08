"""What it takes to put something up, and the ground marked out for it while it is not there yet."""

from dataclasses import dataclass, field
from typing import Any

from world.map import Tile

# What a site is for: a piece of furniture or other object, a whole building, or making
# better something that already stands (S54) or mending one that has broken down (S55),
# which is then the ID of that thing.
OBJECT_SITE = "object"
BUILDING_SITE = "building"
UPGRADE_SITE = "upgrade"
REPAIR_SITE = "repair"
SITE_KINDS = (OBJECT_SITE, BUILDING_SITE, UPGRADE_SITE, REPAIR_SITE)
# The kinds of site that are on something that stands, and not for something to come.
ON_WHAT_STANDS = (UPGRADE_SITE, REPAIR_SITE)


@dataclass(frozen=True)
class BuildRule:
    """What putting something up takes: what has to be brought, how much work, and whose."""

    # Units that have to be carried to the site, by the tag of the items that will do.
    cost: dict[str, int] = field(default_factory=dict)
    # Minutes of work once everything is there.
    minutes: int = 0
    # Job whoever does the work has to hold. None for anybody.
    job: str | None = None

    @property
    def free(self) -> bool:
        """Whether it takes nothing at all, and so is simply put down."""
        return not self.cost and self.minutes <= 0


def build_rule_from_data(where: str, data: Any) -> BuildRule | None:
    """The rule in a definition's `build` entry. None for a definition that has no such entry."""
    if data is None:
        return None
    if not isinstance(data, dict):
        raise ValueError(f"'build' of {where} must be an object")
    cost = data.get("cost", {})
    if not isinstance(cost, dict) or not all(
        isinstance(tag, str) and isinstance(units, int) and not isinstance(units, bool) and units > 0
        for tag, units in cost.items()
    ):
        raise ValueError(f"'build' of {where} must cost whole units of one or more tags of item")
    minutes = data.get("minutes", 0)
    if not isinstance(minutes, int) or isinstance(minutes, bool) or minutes < 0:
        raise ValueError(f"'build' of {where} must take a whole number of minutes, none or more")
    job = data.get("job")
    if job is not None and not isinstance(job, str):
        raise ValueError(f"'build' of {where} must name the job that does it as a string, or none")
    return BuildRule(cost={str(tag): int(units) for tag, units in cost.items()}, minutes=int(minutes), job=job)


def build_rule_data(rule: BuildRule | None) -> dict[str, Any] | None:
    """A rule as it is written in data, for whoever writes definitions back out."""
    if rule is None:
        return None
    return {"cost": dict(rule.cost), "minutes": rule.minutes, "job": rule.job}


@dataclass
class BuildSite:
    """Ground marked out for something somebody has agreed to put up, and how far along it is."""

    site_id: str
    # One of SITE_KINDS, and the object kind or blueprint it is a site for.
    kind: str
    what: str
    x: int
    y: int
    # Whoever said they would see to it. Others may lend a hand.
    in_charge: str | None = None
    # Units brought so far, by item definition.
    delivered: dict[str, int] = field(default_factory=dict)
    # Minutes of work done so far, counting each pair of hands.
    progress: float = 0.0
    # Game minute at which it was agreed.
    started_at: int = 0
    # Every tile it will stand on, and whether those can be walked meanwhile. Worked out from the
    # definition whenever a site is laid or loaded, and not saved.
    tiles: list[Tile] = field(default_factory=list, compare=False)
    blocks: bool = True
