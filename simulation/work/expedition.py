"""Going out beyond the fence: the rules of it, and the state of someone who is out there."""

from dataclasses import dataclass
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
class ExpeditionSettings:
    """What there is out there, and what becomes of it once it is brought in."""

    loot: tuple[LootEntry, ...] = ()
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


def expedition_rule_from_data(job_id: str, data: dict[str, Any]) -> ExpeditionRule:
    shortest, longest = (int(value) for value in data.get("minutes", (240, 360)))
    fewest, most = (int(value) for value in data.get("finds", (3, 6)))
    danger = float(data.get("danger", 0.0))
    if not (1 <= shortest <= longest and 0 <= fewest <= most and 0.0 <= danger <= 1.0):
        raise ValueError(f"Job {job_id} has an expedition with impossible minutes, finds or danger")
    return ExpeditionRule((shortest, longest), (fewest, most), danger)


def expedition_settings_from_data(data: dict[str, Any]) -> ExpeditionSettings:
    defaults = ExpeditionSettings()
    loot = tuple(LootEntry(str(entry["item"]), float(entry.get("weight", 1.0))) for entry in data.get("loot", []))
    if any(entry.weight <= 0 for entry in loot):
        raise ValueError("Expedition loot weights must be positive")
    low, high = (int(value) for value in data.get("injury", defaults.injury))
    if not 0 <= low <= high:
        raise ValueError("Expedition injury must be a range that is not negative")
    return ExpeditionSettings(
        loot=loot,
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
