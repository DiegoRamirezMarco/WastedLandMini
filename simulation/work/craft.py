"""A trade and what it teaches (S47): levels of a job, as data, and the new things each brings.

Time at a job adds up, and at each level whoever does it comes to something new of the kind
their job gives: a crop, a dish, a drink, a tool, somewhere to go. The game works out what it
is like. The player says what it is called and picks from what the kind lets them pick, and
draws it: that is theirs alone. What is come to is the resident's, who can show it to others.

A kind has no code of its own: what the thing is, what there is to pick and what each pick
does are data, laid over one another to make an item like any a pack might bring.
"""

from dataclasses import dataclass, field
from typing import Any

# Where what there is to pick from comes from, when it is not written out: food that is not
# a dish yet, and the jobs that make something.
RAW_FOOD, MAKING_JOBS = "raw_food", "making_jobs"
SOURCES = (RAW_FOOD, MAKING_JOBS)
# The parts of an item a kind or a pick may give. A pair of numbers is anywhere between them.
ITEM_FIELDS = (
    "category", "tags", "value", "effects", "properties", "preference_tags", "flavours", "substance", "spoils",
)


@dataclass(frozen=True)
class OptionDefinition:
    """One thing the player may pick, and what picking it does."""

    option_id: str
    name: str
    text: str = ""
    # What it lays over the thing as the kind makes it: parts of an item.
    item: dict[str, Any] = field(default_factory=dict)
    # How the thing is made, where the pick says: minutes a time, units a time, and the days
    # from learning it until it first gives. None for what the kind says.
    every_minutes: int | None = None
    batch: int | None = None
    ripens_days: int = 0
    # For somewhere to go: the one thing brought back from there, and how many more or fewer.
    fetch: str | None = None
    finds: int = 0


@dataclass(frozen=True)
class ChoiceDefinition:
    choice_id: str
    # What it is called where it is picked: "Cómo se cultiva".
    name: str
    options: dict[str, OptionDefinition] = field(default_factory=dict)
    # Where the options come from as things stand, when they are not written out.
    source: str | None = None


@dataclass(frozen=True)
class KindDefinition:
    """A kind of thing a job may teach."""

    kind_id: str
    name: str
    # What the player is asked, and how it is said of whoever comes to one: "aprende a cultivar".
    ask: str = ""
    learned: str = "aprende a hacer"
    # The item it is, as the game makes it. None for what is not a thing, like somewhere to go.
    item: dict[str, Any] | None = None
    choices: dict[str, ChoiceDefinition] = field(default_factory=dict)
    # How a unit is made where no pick says: minutes a time and units a time.
    every_minutes: int = 30
    batch: int = 1
    # For a job that makes nothing otherwise: the kind of container what is made is kept in,
    # and how many of each the settlement keeps before no more are made.
    into: str | None = None
    max_stock: int = 3


@dataclass(frozen=True)
class CraftSettings:
    kinds: dict[str, KindDefinition] = field(default_factory=dict)
    # The kind each job teaches, by job ID. A job left out teaches nothing, and is still learned.
    jobs: dict[str, str] = field(default_factory=dict)
    # Minutes at a job from which each level is reached, the first from none.
    levels: tuple[int, ...] = (0,)
    # How much faster each level past the first makes the work.
    pace: float = 0.05
    # Minutes near somebody who knows a thing that it takes to learn it from them, and how near.
    teach_minutes: int = 900
    teach_reach: int = 6
    # The longest name a thing may be given.
    name_length: int = 20
    # How much better each level makes what is come to at it, past the first thing.
    better: float = 0.08
    # What a food that is come to may taste of.
    flavours: tuple[str, ...] = ()

    @property
    def top(self) -> int:
        return len(self.levels)


@dataclass
class Discovery:
    """Something a resident came to at their job. Until the player has named it, it waits."""

    discovery_id: str
    kind: str
    job_id: str
    # Who came to it, and their name, for when they are no longer here.
    by: str
    by_name: str = ""
    level: int = 2
    day: int = 0
    # What the player called it, and what they picked, by choice ID. Empty until they have.
    name: str = ""
    choices: dict[str, str] = field(default_factory=dict)
    # The item it is, once named, and its definition as a pack would give it. None for what
    # is not a thing.
    item_id: str | None = None
    item: dict[str, Any] = field(default_factory=dict)
    # For what was found and not come to at a job (S59): where it came from, how many of it
    # there are until it is named, and whose they are then. Nobody's is the settlement's.
    source: str = ""
    units: int = 0
    owner: str | None = None

    @property
    def named(self) -> bool:
        return bool(self.name)


@dataclass(frozen=True)
class Product:
    """Something a resident knows how to make at their job, and how."""

    discovery_id: str
    item_id: str
    every_minutes: int
    batch: int = 1
    # The one item it is made of, when it is made of one.
    needs: str | None = None
    # Whether it gives yet: a tree takes its time.
    ripe: bool = True


@dataclass(frozen=True)
class CraftResult:
    ok: bool
    message: str = ""
    # The ID of the discovery it is about, where there is one.
    detail: str = ""


def _option(option_id: str, data: Any, where: str) -> OptionDefinition:
    if not isinstance(data, dict) or "name" not in data:
        raise ValueError(f"{where} needs a name")
    item = data.get("item", {})
    if not isinstance(item, dict) or set(item) - set(ITEM_FIELDS):
        raise ValueError(f"{where} lays over an item what an item has not: one of {ITEM_FIELDS}")
    option = OptionDefinition(
        option_id=option_id,
        name=str(data["name"]),
        text=str(data.get("text", "")),
        item=dict(item),
        every_minutes=int(data["every_minutes"]) if "every_minutes" in data else None,
        batch=int(data["batch"]) if "batch" in data else None,
        ripens_days=int(data.get("ripens_days", 0)),
        fetch=str(data["fetch"]) if data.get("fetch") else None,
        finds=int(data.get("finds", 0)),
    )
    if (option.every_minutes is not None and option.every_minutes < 1) or (option.batch is not None and option.batch < 1):
        raise ValueError(f"{where} is made in a minute or more, a unit or more at a time")
    if option.ripens_days < 0:
        raise ValueError(f"{where} gives from the day it is learned, or later")
    return option


def kind_from_data(kind_id: str, data: Any) -> KindDefinition:
    if not isinstance(data, dict) or "name" not in data:
        raise ValueError(f"Kind {kind_id} of thing to learn needs a name")
    item = data.get("item")
    if item is not None and (not isinstance(item, dict) or "category" not in item or set(item) - set(ITEM_FIELDS)):
        raise ValueError(f"Kind {kind_id} makes an item with a category and nothing an item has not: {ITEM_FIELDS}")
    choices = {}
    for choice_id, values in data.get("choices", {}).items():
        if not isinstance(values, dict) or "name" not in values:
            raise ValueError(f"Choice {choice_id} of kind {kind_id} needs a name")
        source = str(values["source"]) if values.get("source") else None
        options = {
            str(option_id): _option(str(option_id), option, f"Option {option_id} of kind {kind_id}")
            for option_id, option in values.get("options", {}).items()
        }
        if source is not None and source not in SOURCES:
            raise ValueError(f"Choice {choice_id} of kind {kind_id} picks from what there is not: one of {SOURCES}")
        if (source is None) == (not options):
            raise ValueError(f"Choice {choice_id} of kind {kind_id} needs its options written out, or where they come from")
        choices[str(choice_id)] = ChoiceDefinition(str(choice_id), str(values["name"]), options, source)
    kind = KindDefinition(
        kind_id=kind_id,
        name=str(data["name"]),
        ask=str(data.get("ask", "")),
        learned=str(data.get("learned", "aprende a hacer")),
        item=dict(item) if item is not None else None,
        choices=choices,
        every_minutes=int(data.get("every_minutes", 30)),
        batch=int(data.get("batch", 1)),
        into=str(data["into"]) if data.get("into") else None,
        max_stock=int(data.get("max_stock", 3)),
    )
    if kind.every_minutes < 1 or kind.batch < 1 or kind.max_stock < 1:
        raise ValueError(f"Kind {kind_id} is made in a minute or more, a unit or more at a time, and one at least is kept")
    return kind


def craft_settings_from_data(data: dict[str, Any]) -> CraftSettings:
    defaults = CraftSettings()
    kinds = {str(kind_id): kind_from_data(str(kind_id), values) for kind_id, values in data.get("kinds", {}).items()}
    jobs = {str(job_id): str(kind_id) for job_id, kind_id in data.get("jobs", {}).items()}
    unknown = sorted(set(jobs.values()) - set(kinds))
    if unknown:
        raise ValueError(f"Jobs teach kinds of thing there are not: {unknown}")
    levels = tuple(int(minutes) for minutes in data.get("levels", defaults.levels))
    if not levels or levels[0] != 0 or any(later <= earlier for earlier, later in zip(levels, levels[1:])):
        raise ValueError("The levels of a trade start at no minutes, and each takes more than the one before")
    settings = CraftSettings(
        kinds=kinds,
        jobs=jobs,
        levels=levels,
        pace=float(data.get("pace", defaults.pace)),
        teach_minutes=int(data.get("teach_minutes", defaults.teach_minutes)),
        teach_reach=int(data.get("teach_reach", defaults.teach_reach)),
        name_length=int(data.get("name_length", defaults.name_length)),
        better=float(data.get("better", defaults.better)),
        flavours=tuple(str(tag) for tag in data.get("flavours", [])),
    )
    if settings.pace < 0 or settings.teach_minutes < 1 or settings.teach_reach < 0 or settings.name_length < 1:
        raise ValueError("A level makes work no slower, teaching takes a minute or more, and a name has a letter")
    return settings


def article_for(name: str) -> str:
    """The article a thing the player has named goes by, as near as its ending tells."""
    word = name.strip().lower().split(" ")[0] if name.strip() else ""
    if word.endswith("as"):
        return "unas"
    if word.endswith(("os", "es")):
        return "unos"
    return "una" if word.endswith("a") else "un"
