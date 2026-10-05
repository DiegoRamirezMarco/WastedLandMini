from dataclasses import dataclass, field
from typing import Any

# Where a job's product goes when it stays in the worker's own post.
INTO_STATION = "station"


@dataclass(frozen=True)
class ProduceRule:
    """What a worker turns out while at their post, and from what."""

    item: str
    every_minutes: int
    # `station` for the post itself, or the kind of container that receives it.
    into: str = INTO_STATION
    # Nothing more is made while the receiving container already holds this many.
    max_stock: int = 99
    # Kind of container to take one unit of raw material from for each unit made, if any.
    source: str | None = None
    source_category: str | None = None
    # Items with this tag are not raw material: a cook does not cook what is already cooked.
    skip_tag: str | None = None


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
        )
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
    )
