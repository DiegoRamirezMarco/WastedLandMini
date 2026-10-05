from dataclasses import dataclass, field
from typing import Any

from simulation.work.expedition import ExpeditionRule, expedition_rule_from_data

# Where a job's product goes when it stays in the worker's own post.
INTO_STATION = "station"


@dataclass(frozen=True)
class ProduceRule:
    """What a worker turns out while at their post, and from what."""

    item: str
    every_minutes: int
    # `station` for the post itself, or the kind of container the worker carries it to.
    into: str = INTO_STATION
    # Nothing more is made while the receiving container already holds this many.
    max_stock: int = 99
    # Kind of container the worker fetches raw material from, one unit for each unit made, if any.
    source: str | None = None
    source_category: str | None = None
    # Items with this tag are not raw material: a cook does not cook what is already cooked.
    skip_tag: str | None = None
    # How many units a worker carries in one trip, to the receiving container or from the source.
    carry: int = 6


@dataclass(frozen=True)
class ToolRule:
    """A kind of tool that makes the work go faster, and wears out doing it."""

    tag: str
    speed: float = 1.5


@dataclass(frozen=True)
class JobDefinition:
    """A post in the settlement: where it is worked, when, and what working it does."""

    job_id: str
    name: str
    station: str
    shifts: tuple[tuple[int, int], ...]
    text: str
    # Whether someone can come and talk to the worker while they are at it.
    interruptible: bool = True
    per_minute: dict[str, float] = field(default_factory=dict)
    produces: ProduceRule | None = None
    # Extra tiles a worker on duty can see, for those whose job is to keep watch.
    sight_bonus: int = 0
    tool: ToolRule | None = None
    # Credits earned per hour on duty. None for the settlement's usual wage.
    wage: float | None = None
    # How much the settlement misses this job when nobody does it. Higher is filled first.
    priority: int = 1
    # How many residents it takes. With fewer, the job has a vacancy.
    needed: int = 1
    # For a job done outside the settlement: the worker leaves from the post instead of standing at it.
    expedition: ExpeditionRule | None = None
    # Whether the work is done in the open, where bad weather stops it.
    outdoors: bool = False
    # Kind of world event this job keeps watch for: a worker who knows one is on its way stays at
    # the post until it has come, whatever their shift.
    watch_for: str | None = None


def job_definition_from_data(job_id: str, data: dict[str, Any]) -> JobDefinition:
    missing = {"name", "station", "shifts", "text"} - data.keys()
    if missing:
        raise ValueError(f"Missing fields in job {job_id}: {sorted(missing)}")
    shifts = tuple((int(start), int(end)) for start, end in data["shifts"])
    if not shifts or any(not (0 <= hour <= 24) for shift in shifts for hour in shift):
        raise ValueError(f"Job {job_id} needs shifts with hours from 0 to 24")
    produces = None
    if "produces" in data:
        rule = data["produces"]
        if "item" not in rule or int(rule.get("every_minutes", 0)) < 1:
            raise ValueError(f"Job {job_id} produces needs an item and every_minutes of at least 1")
        produces = ProduceRule(
            item=str(rule["item"]),
            every_minutes=int(rule["every_minutes"]),
            into=str(rule.get("into", INTO_STATION)),
            max_stock=int(rule.get("max_stock", 99)),
            source=str(rule["from"]) if "from" in rule else None,
            source_category=str(rule["from_category"]) if "from_category" in rule else None,
            skip_tag=str(rule["skip_tag"]) if "skip_tag" in rule else None,
            carry=int(rule.get("carry", 6)),
        )
        if produces.carry < 1:
            raise ValueError(f"Job {job_id} must carry at least 1 unit per trip")
    tool = None
    if "tool" in data:
        tool = ToolRule(str(data["tool"]["tag"]), float(data["tool"].get("speed", 1.5)))
        if tool.speed < 1.0:
            raise ValueError(f"Job {job_id} has a tool that slows the work down")
    wage = float(data["wage"]) if "wage" in data else None
    if (wage is not None and wage < 0) or int(data.get("needed", 1)) < 0:
        raise ValueError(f"Job {job_id} needs a wage and a number of workers that are not negative")
    return JobDefinition(
        job_id=job_id,
        name=str(data["name"]),
        station=str(data["station"]),
        shifts=shifts,
        text=str(data["text"]),
        interruptible=bool(data.get("interruptible", True)),
        per_minute={str(need): float(delta) for need, delta in data.get("per_minute", {}).items()},
        produces=produces,
        sight_bonus=int(data.get("sight_bonus", 0)),
        tool=tool,
        wage=wage,
        priority=int(data.get("priority", 1)),
        needed=int(data.get("needed", 1)),
        expedition=expedition_rule_from_data(job_id, data["expedition"]) if "expedition" in data else None,
        outdoors=bool(data.get("outdoors", False)),
        watch_for=str(data["watch_for"]) if "watch_for" in data else None,
    )
