"""Going out beyond the fence: the rules of it, and the state of someone who is out there."""

from dataclasses import dataclass, field
from typing import Any

# What a resident who has come on something risky out there can do about it.
PUSH_ON = "push_on"
TURN_BACK = "turn_back"
EXPEDITION_CHOICES = (PUSH_ON, TURN_BACK)


@dataclass(frozen=True)
class ExpeditionRule:
    """A job done outside the settlement: how long a trip takes, what it finds and what it risks."""

    # Shortest and longest trip, in game minutes.
    minutes: tuple[int, int]
    # Fewest and most things brought back.
    finds: tuple[int, int]
    # Chance of coming back hurt, from 0 to 1.
    danger: float = 0.0


@dataclass(frozen=True)
class LootEntry:
    item: str
    weight: float


@dataclass(frozen=True)
class Delivery:
    """Where a kind of find is taken on coming back: a kind of container, for things with a tag or for anything."""

    to: str
    tag: str | None = None
    # Kind of object the settlement has to have for a find to be taken there: fuel is left in
    # store only where there is a post whose worker carries it on to the generator.
    needs: str | None = None


@dataclass(frozen=True)
class Zone:
    """A stretch of country out there (S68). Those of the line lie one past the other: to get
    to one, every one before it is gone through. How it looks is not the simulation's business."""

    zone_id: str
    # What it is called until the player says otherwise.
    name: str
    # Minutes it adds to a trip that goes through it, there and back.
    minutes: int = 0
    # How much there is to take along to get through it, in what provisions are worth.
    supplies: float = 0.0
    # What going through it adds to the chance of coming back hurt.
    danger: float = 0.0
    # How many more things a trip that gets there brings, how many times as likely each is
    # to be rarer than common, and how many times as likely something nobody knows is among it.
    more: int = 0
    rare: float = 1.0
    finds: float = 1.0
    # The lowest and the highest level of whoever lies in wait there.
    raiders: tuple[int, int] = (1, 1)
    # What there is there. With nothing of its own, what there is anywhere.
    loot: tuple[LootEntry, ...] = ()
    # Whether it is off the line: reached by a map and by nothing else, with nothing gone through first.
    apart: bool = False


@dataclass(frozen=True)
class Provision:
    """Something that can be taken along to go further: things with a tag or of a category,
    and how far a unit of it goes."""

    worth: float = 1.0
    tag: str | None = None
    category: str | None = None


@dataclass
class ZoneFound:
    """A zone the settlement has come to know of: what the player calls it, who found it and when."""

    name: str = ""
    by: str = ""
    day: int = 0


@dataclass
class Outing:
    """A trip the player has made ready for somebody, to be gone on the next time they set
    out: how far, and what was handed to them to get there, in units by item ID."""

    zone: str
    supplies: dict[str, int] = field(default_factory=dict)


@dataclass(frozen=True)
class TripResult:
    ok: bool
    message: str = ""


@dataclass(frozen=True)
class ExpeditionSettings:
    """What there is out there, and what becomes of it once it is brought in."""

    loot: tuple[LootEntry, ...] = ()
    # The country there is out there, by ID. The first is where a trip goes that has nowhere
    # else to.
    zones: tuple[Zone, ...] = ()
    # What can be taken along to go further than that, the first that fits a thing saying its worth.
    provisions: tuple[Provision, ...] = ()

    @property
    def line(self) -> tuple[Zone, ...]:
        """The zones that lie one past the other, the nearest first."""
        return tuple(zone for zone in self.zones if not zone.apart)

    def zone(self, zone_id: str | None) -> Zone | None:
        return next((zone for zone in self.zones if zone.zone_id == zone_id), None)
    # The first that fits a find says where it goes.
    deliveries: tuple[Delivery, ...] = ()
    # Harm done by a trip that goes badly, and the kind of injury it leaves.
    injury: tuple[int, int] = (8, 20)
    injury_kind: str = "cut"
    # Chance that a trip comes on something worth a risk, which the player may advise on.
    find_chance: float = 0.35
    # What going for it adds: finds, danger, and minutes out.
    push_on_finds: int = 4
    push_on_danger: float = 0.35
    push_on_minutes: int = 60
    # How long it takes to get back in after turning round.
    turn_back_minutes: int = 30


@dataclass
class Expedition:
    """One trip outside, as it stands. It belongs to the resident who is out."""

    # Game minute at which they come back in.
    returns_at: int
    # How many things they will have found by then.
    finds: int
    danger: float
    # Game minute at which they come on something worth a risk, if they are going to.
    find_at: int | None = None
    # The one item they went out for, when it is not whatever turns up: all they find is that.
    fetch: str | None = None
    # Whether they went on at something worth a risk: what they bring is the likelier to be rare (S64).
    risked: bool = False
    # Game minute at which they set out, and at which they turn for home (S67). A trip from
    # before these were kept has been on its way back since for ever.
    left_at: int = 0
    turns_at: int = 0
    # The country it goes through, by ID, and the place out there it is bound for, as the ID
    # of what was come to: neither for a trip from before they were kept, or that has none.
    zone: str | None = None
    place: str | None = None
    # The zones it goes through, the furthest last, and how far along the way each of them
    # ends, from 0 to 1 (S68). Empty for a trip that keeps to the first there is.
    route: list[str] = field(default_factory=list)
    stages: list[float] = field(default_factory=list)
    # Minutes the way out was to take as it was planned: turning round sooner is not getting
    # all the way. None of it for a trip from before it was kept.
    out_minutes: int = 0
    # What was handed to them to get there, in units by item ID.
    supplies: dict[str, int] = field(default_factory=dict)

    def heading_back(self, now: int) -> bool:
        """Whether they are on their way home by a game minute."""
        return now >= self.turns_at

    def got_to(self) -> float:
        """How much of the way they set out to go they have gone, or will have by the time
        they turn: all of it, unless they turn round sooner than was planned."""
        planned = self.out_minutes if self.out_minutes > 0 else self.turns_at - self.left_at
        return min(1.0, max(0.0, (self.turns_at - self.left_at) / planned)) if planned > 0 else 1.0

    def distance(self, now: int) -> float:
        """How far from the settlement they are at a game minute: from 0 at the fence to 1 at
        the furthest they set out to go, out and then back."""
        if now < self.turns_at:
            way = self.out_minutes if self.out_minutes > 0 else self.turns_at - self.left_at
            return min(1.0, max(0.0, (now - self.left_at) / way)) if way > 0 else 1.0
        way = self.returns_at - self.turns_at
        return self.got_to() * min(1.0, max(0.0, (self.returns_at - now) / way)) if way > 0 else 0.0

    def stage_at(self, share: float) -> int:
        """Which of the zones of its route somebody that far along the way is in, the first being 0."""
        for index, end in enumerate(self.stages):
            if share <= end:
                return index
        return max(0, len(self.route) - 1)

    def zone_at(self, now: int) -> str | None:
        """The zone they are in at a game minute, by ID: the one it is bound for, for a trip with no route."""
        return self.route[self.stage_at(self.distance(now))] if self.route else self.zone

    def furthest(self) -> str | None:
        """The furthest zone they get to, by ID: short of where they set out for if they turn sooner."""
        return self.route[self.stage_at(self.got_to())] if self.route else self.zone


def expedition_rule_from_data(job_id: str, data: dict[str, Any]) -> ExpeditionRule:
    shortest, longest = (int(value) for value in data.get("minutes", (240, 360)))
    fewest, most = (int(value) for value in data.get("finds", (3, 6)))
    danger = float(data.get("danger", 0.0))
    if not (1 <= shortest <= longest and 0 <= fewest <= most and 0.0 <= danger <= 1.0):
        raise ValueError(f"Job {job_id} has an expedition with impossible minutes, finds or danger")
    return ExpeditionRule((shortest, longest), (fewest, most), danger)


def _zone(zone_id: str, data: Any) -> Zone:
    data = data if isinstance(data, dict) else {}
    low, high = (int(value) for value in data.get("raiders", (1, 1)))
    zone = Zone(
        zone_id=zone_id,
        name=str(data.get("name", zone_id)),
        minutes=int(data.get("minutes", 0)),
        supplies=float(data.get("supplies", 0.0)),
        danger=float(data.get("danger", 0.0)),
        more=int(data.get("more", 0)),
        rare=float(data.get("rare", 1.0)),
        finds=float(data.get("finds", 1.0)),
        raiders=(low, high),
        loot=tuple(LootEntry(str(entry["item"]), float(entry.get("weight", 1.0))) for entry in data.get("loot", [])),
        apart=bool(data.get("apart", False)),
    )
    if zone.minutes < 0 or zone.supplies < 0 or zone.danger < 0 or zone.rare < 0 or zone.finds < 0:
        raise ValueError(f"Zone {zone_id} takes time and provisions to cross, and makes nothing less likely than never")
    if not 1 <= low <= high:
        raise ValueError(f"Zone {zone_id} has raiders of a level from one up, the lowest first")
    if any(entry.weight <= 0 for entry in zone.loot):
        raise ValueError(f"Zone {zone_id} has loot with a weight that is not positive")
    return zone


def expedition_settings_from_data(data: dict[str, Any]) -> ExpeditionSettings:
    defaults = ExpeditionSettings()
    loot = tuple(LootEntry(str(entry["item"]), float(entry.get("weight", 1.0))) for entry in data.get("loot", []))
    if any(entry.weight <= 0 for entry in loot):
        raise ValueError("Expedition loot weights must be positive")
    low, high = (int(value) for value in data.get("injury", defaults.injury))
    if not 0 <= low <= high:
        raise ValueError("Expedition injury must be a range that is not negative")
    zones = tuple(_zone(str(zone_id), entry) for zone_id, entry in dict(data.get("zones", {})).items())
    provisions = tuple(
        Provision(
            float(entry.get("worth", 1.0)),
            str(entry["tag"]) if "tag" in entry else None,
            str(entry["category"]) if "category" in entry else None,
        )
        for entry in data.get("provisions", [])
    )
    if any(entry.worth <= 0 or (entry.tag is None) == (entry.category is None) for entry in provisions):
        raise ValueError("A provision is worth something, and is things with a tag or of a category: one of the two")
    return ExpeditionSettings(
        loot=loot,
        zones=zones,
        provisions=provisions,
        deliveries=tuple(
            Delivery(
                str(entry["to"]),
                str(entry["tag"]) if "tag" in entry else None,
                str(entry["needs"]) if "needs" in entry else None,
            )
            for entry in data.get("deliveries", [])
        ),
        injury=(low, high),
        injury_kind=str(data.get("injury_kind", defaults.injury_kind)),
        find_chance=float(data.get("find_chance", defaults.find_chance)),
        push_on_finds=int(data.get("push_on_finds", defaults.push_on_finds)),
        push_on_danger=float(data.get("push_on_danger", defaults.push_on_danger)),
        push_on_minutes=int(data.get("push_on_minutes", defaults.push_on_minutes)),
        turn_back_minutes=int(data.get("turn_back_minutes", defaults.turn_back_minutes)),
    )
