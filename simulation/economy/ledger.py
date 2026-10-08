"""The settlement's books (S51): what comes in, what goes out, and how long what there is will last.

Each thing that comes into what the settlement holds in common, or leaves it, is written down
as it happens, by the resource it counts as and by why. Once a day what there is is counted.
The count is the truth and what was written explains it: what it does not explain is entered
as such, so that the books always come to what there is.

Nothing here decides anything. No dice are thrown, and nobody does anything for what is
written: it is for whoever looks at the settlement to see how it stands.
"""

from collections import deque
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from simulation.events.event import DomainEvent
from simulation.items.item import ItemDefinition

if TYPE_CHECKING:
    from simulation.world import SimulationWorld

# Why a thing came in or went out. What each is called is in the data.
MADE, FOUND, SALVAGED, BOUGHT, ARRIVED, RETURNED, HANDED = (
    "made", "found", "salvaged", "bought", "arrived", "returned", "handed",
)
EATEN, DRUNK, USED, BURNT, DOSED, BUILT, STUDIED, MENDED, SOLD, RATIONED, SPOILED, RAIDED, STOLEN, TAKEN = (
    "eaten", "drunk", "used", "burnt", "dosed", "built", "studied", "mended", "sold", "rationed", "spoiled",
    "raided", "stolen", "taken",
)
# What the count at the end of a day found that nothing written down accounts for.
OTHER = "other"

LOW_EVENT = "resource_low"
LOW_IMPORTANCE = 35
LOW_NOTICE = "low:"
MINUTES_PER_DAY = 24 * 60
# Before a whole day has been written down, how much of one has to have gone by for its pace to be told.
FIRST_READING_MINUTES = 6 * 60
# How many of the last things written down are kept for whoever shows them.
RECENT = 48


@dataclass(frozen=True)
class ResourceDefinition:
    """Something a settlement lives on, and which items count as it."""

    resource_id: str
    name: str
    icon: str
    # Every item of this category counts as it, and every item with this tag.
    category: str | None = None
    tag: str | None = None

    def counts(self, definition: ItemDefinition) -> bool:
        if self.category is not None and definition.category == self.category:
            return True
        return self.tag is not None and self.tag in definition.tags


@dataclass(frozen=True)
class ResourceSettings:
    resources: dict[str, ResourceDefinition] = field(default_factory=dict)
    # How many days back the pace of things is worked out from, and how many are kept.
    window_days: int = 3
    kept_days: int = 7
    # With fewer days left than this, a resource is running low.
    low_days: float = 2.0
    # What each reason is called where it is shown, and what it is called where what a thing
    # came of is known, with `{source}` where the name of that goes: the job that made it.
    reasons: dict[str, str] = field(default_factory=dict)
    sourced: dict[str, str] = field(default_factory=dict)


@dataclass
class LedgerState:
    """What has been written down. Saved with the settlement."""

    # The day being written down, and the game minute the books were opened at. No day until they are.
    day: int = 0
    opened_at: int = 0
    # What has come in, above nothing, and gone out, below it, today: by resource and by why.
    today: dict[str, dict[str, float]] = field(default_factory=dict)
    # The same for the days before, by day, for as many as are kept.
    days: dict[int, dict[str, dict[str, float]]] = field(default_factory=dict)
    # What the settlement held of each resource when each of those days ended.
    held: dict[int, dict[str, int]] = field(default_factory=dict)


@dataclass(frozen=True)
class LedgerEntry:
    """One thing written down, for whoever shows it as it happens."""

    minute: int
    definition_id: str
    units: float
    # Why, as it is filed: the reason, and after a colon what it came of, where that is known.
    why: str
    resources: tuple[str, ...] = ()
    # Who did it, and at which object, where there was somebody and somewhere.
    by: str | None = None
    at: str | None = None


@dataclass(frozen=True)
class ResourceLine:
    """How one resource stands."""

    resource_id: str
    name: str
    icon: str
    stock: int
    # Whether there is enough written down to tell its pace, and whether that is less than a whole day.
    known: bool = False
    tentative: bool = False
    # Units a day that come in and that go out, as things have been going.
    coming: float = 0.0
    going: float = 0.0
    # Days what there is will last as things go. None where no more goes out than comes in.
    days_left: float | None = None
    low: bool = False
    # What makes that up, by why: units a day, what comes in first and the most first.
    by_reason: tuple[tuple[str, float], ...] = ()

    @property
    def net(self) -> float:
        return self.coming - self.going


def resource_settings_from_data(data: dict[str, Any]) -> ResourceSettings:
    defaults = ResourceSettings()
    resources = {}
    for resource_id, values in data.get("resources", {}).items():
        if not isinstance(values, dict) or "name" not in values:
            raise ValueError(f"Resource {resource_id} needs a name")
        resource = ResourceDefinition(
            resource_id=str(resource_id),
            name=str(values["name"]),
            icon=str(values.get("icon", resource_id)),
            category=str(values["category"]) if values.get("category") else None,
            tag=str(values["tag"]) if values.get("tag") else None,
        )
        if resource.category is None and resource.tag is None:
            raise ValueError(f"Resource {resource_id} must say what counts as it: a category or a tag")
        resources[resource.resource_id] = resource
    settings = ResourceSettings(
        resources=resources,
        window_days=int(data.get("window_days", defaults.window_days)),
        kept_days=int(data.get("kept_days", defaults.kept_days)),
        low_days=float(data.get("low_days", defaults.low_days)),
        reasons={str(reason): str(name) for reason, name in data.get("reasons", {}).items()},
        sourced={str(reason): str(name) for reason, name in data.get("sourced", {}).items()},
    )
    if settings.window_days < 1 or settings.kept_days < settings.window_days or settings.low_days < 0:
        raise ValueError("The pace of things goes by a day or more, no more than are kept, and low is not below none")
    return settings


class LedgerSystem:
    def __init__(self) -> None:
        # The last things written down, the newest last. They are for showing, and are not saved.
        self.recent: deque[LedgerEntry] = deque(maxlen=RECENT)

    def settings(self, world: "SimulationWorld") -> ResourceSettings:
        return world.registries.resources

    # ----- what there is -----

    def resources_of(self, world: "SimulationWorld", definition: ItemDefinition) -> tuple[str, ...]:
        """The resources an item counts as. Most count as none."""
        return tuple(
            resource_id for resource_id, resource in self.settings(world).resources.items() if resource.counts(definition)
        )

    def stock(self, world: "SimulationWorld") -> dict[str, int]:
        """What the settlement holds of each resource: what is nobody's, wherever it is kept, in
        the hands of whoever is carrying it, and waiting at the gate to be carried in."""
        held = {resource_id: 0 for resource_id in self.settings(world).resources}
        if not held:
            return held
        resolve = world.registries.items.resolve
        inventories = [*world.containers.values(), *(resident.inventory for resident in world.residents.values())]
        for inventory in inventories:
            for item in inventory.items:
                if item.owner_id is not None:
                    continue
                for resource_id in self.resources_of(world, resolve(item.definition_id)):
                    held[resource_id] += item.quantity
        for definition_id, units in world.at_gate.items():
            for resource_id in self.resources_of(world, resolve(definition_id)):
                held[resource_id] += units
        return held

    # ----- writing it down -----

    def record(
        self,
        world: "SimulationWorld",
        definition_id: str,
        units: float,
        reason: str,
        source: str | None = None,
        by: str | None = None,
        at: str | None = None,
    ) -> None:
        """Write down that units of a thing have come into what is the settlement's, or, below
        nothing, left it. It is written once it has happened. `source` is what it came of, where
        that says more than the reason: the job that made it. A thing that counts as no
        resource is not written down."""
        if not units:
            return
        counted = self.resources_of(world, world.registries.items.resolve(definition_id))
        if not counted:
            return
        state = world.accounts
        if state.day == 0:
            # The books are opened by this very entry: what there was before it is what there is without it.
            self._open(world)
            before = state.held[state.day - 1]
            for resource_id in counted:
                before[resource_id] = before.get(resource_id, 0) - round(units)
        why = reason if source is None else f"{reason}:{source}"
        for resource_id in counted:
            flows = state.today.setdefault(resource_id, {})
            flows[why] = flows.get(why, 0.0) + units
        self.recent.append(LedgerEntry(world.clock.total_minutes, definition_id, units, why, counted, by, at))

    def tick(self, world: "SimulationWorld") -> None:
        """Open the books the first time, close the day when another begins, and once an hour
        give notice, once a day for each, of what is running low."""
        if not self.settings(world).resources:
            return
        state = world.accounts
        if state.day == 0:
            self._open(world)
        elif world.clock.day != state.day:
            self._close(world)
        if world.clock.minute == 0:
            self._warn(world)

    def _open(self, world: "SimulationWorld") -> None:
        state = world.accounts
        state.day = world.clock.day
        state.opened_at = world.clock.total_minutes
        state.held[state.day - 1] = self.stock(world)

    def _close(self, world: "SimulationWorld") -> None:
        """Count what there is at the end of a day, and enter what nothing written down accounts for."""
        settings, state = self.settings(world), world.accounts
        closing = state.day
        held = self.stock(world)
        before = state.held.get(closing - 1, {})
        for resource_id in settings.resources:
            if resource_id not in before:
                # Counted for the first time: there is nothing to set it against yet.
                continue
            flows = state.today.get(resource_id, {})
            unexplained = held[resource_id] - before[resource_id] - sum(flows.values())
            if abs(unexplained) > 1e-6:
                state.today.setdefault(resource_id, {})[OTHER] = flows.get(OTHER, 0.0) + unexplained
        state.days[closing] = state.today
        state.held[closing] = held
        state.today = {}
        state.day = world.clock.day
        oldest = closing - settings.kept_days
        state.days = {day: flows for day, flows in state.days.items() if day > oldest}
        # The count of the last day closed is what the next is set against.
        state.held = {day: count for day, count in state.held.items() if day > oldest}

    # ----- how things stand -----

    def _pace(self, world: "SimulationWorld", resource_id: str) -> tuple[dict[str, float], bool] | None:
        """What has come in and gone out of a resource in a day, by why, as things have been
        going, and whether that is told from less than a whole day. None with too little to go by."""
        settings, state = self.settings(world), world.accounts
        closed = sorted(state.days)[-settings.window_days :]
        if closed:
            totals: dict[str, float] = {}
            for day in closed:
                for why, units in state.days[day].get(resource_id, {}).items():
                    totals[why] = totals.get(why, 0.0) + units
            return ({why: units / len(closed) for why, units in totals.items()}, False)
        elapsed = world.clock.total_minutes - state.opened_at
        if state.day == 0 or elapsed < FIRST_READING_MINUTES:
            return None
        share = MINUTES_PER_DAY / elapsed
        return ({why: units * share for why, units in state.today.get(resource_id, {}).items()}, True)

    def report(self, world: "SimulationWorld") -> list[ResourceLine]:
        """How each resource stands, in the order the data gives them."""
        settings = self.settings(world)
        held = self.stock(world)
        lines = []
        for resource_id, resource in settings.resources.items():
            stock = held.get(resource_id, 0)
            pace = self._pace(world, resource_id)
            if pace is None:
                lines.append(ResourceLine(resource_id, resource.name, resource.icon, stock))
                continue
            flows, tentative = pace
            coming = sum(units for units in flows.values() if units > 0)
            going = -sum(units for units in flows.values() if units < 0)
            days_left = stock / (going - coming) if going - coming > 1e-9 else None
            low = (days_left is not None and days_left < settings.low_days) or (stock <= 0 and going > 0)
            ordered = sorted(flows.items(), key=lambda entry: (entry[1] < 0, -abs(entry[1]), entry[0]))
            lines.append(
                ResourceLine(
                    resource_id, resource.name, resource.icon, stock, True, tentative, coming, going, days_left, low,
                    tuple((why, units) for why, units in ordered if abs(units) > 1e-9),
                )
            )
        return lines

    def line(self, world: "SimulationWorld", resource_id: str) -> ResourceLine | None:
        return next((line for line in self.report(world) if line.resource_id == resource_id), None)

    def reason_name(self, world: "SimulationWorld", why: str) -> str:
        """What a reason is called where it is shown: by the job a thing came of where there
        was one and the data has a way of saying so, and otherwise what the data calls it."""
        settings = self.settings(world)
        reason, _, source = why.partition(":")
        job = world.registries.jobs.get(source)
        if job is not None and reason in settings.sourced:
            return settings.sourced[reason].replace("{source}", job.name)
        return settings.reasons.get(reason, reason)

    def _warn(self, world: "SimulationWorld") -> None:
        for line in self.report(world):
            notice = f"{LOW_NOTICE}{line.resource_id}"
            if not line.low or world.notices.get(notice) == world.clock.day:
                continue
            world.notices[notice] = world.clock.day
            name = line.name.lower()
            days = round(line.days_left or 0)
            if line.stock <= 0:
                text = f"No queda nada de {name}"
            elif line.days_left is not None and line.days_left < 1:
                text = f"Queda {name} para menos de un día"
            else:
                text = f"Queda {name} para un día" if days <= 1 else f"Queda {name} para {days} días"
            world.emit_event(
                DomainEvent(
                    LOW_EVENT,
                    LOW_IMPORTANCE,
                    text,
                    data={"resource": line.resource_id, "stock": line.stock, "days_left": line.days_left},
                )
            )
