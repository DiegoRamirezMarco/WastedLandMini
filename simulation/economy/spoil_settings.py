"""What going off comes to, as data (S65). Kept apart from the system that sees to it, so that
the registries can read it without the systems."""

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class SpoilSettings:
    # What a unit that has gone off becomes. None for nothing at all.
    becomes: str | None = None
    # By how much of their freshness, of a hundred, two lots of a thing may differ and still
    # be kept as one stack. Further apart they are two, and the older goes off first.
    apart: float = 20.0
    # Compost: the item that is one, the kinds of thing it is put on, how many units one
    # dressing takes, by how much the thing is worked faster while it lasts, and for how
    # many days it does.
    compost: str | None = None
    compost_on: tuple[str, ...] = ()
    compost_units: int = 1
    compost_factor: float = 1.0
    compost_days: int = 0

    @property
    def dresses(self) -> bool:
        return self.compost is not None and bool(self.compost_on) and self.compost_days > 0


def spoil_settings_from_data(data: dict[str, Any]) -> SpoilSettings:
    compost = data.get("compost", {})
    settings = SpoilSettings(
        becomes=str(data["becomes"]) if data.get("becomes") else None,
        apart=float(data.get("apart", 20.0)),
        compost=str(compost["item"]) if compost.get("item") else None,
        compost_on=tuple(str(kind) for kind in compost.get("on", [])),
        compost_units=int(compost.get("units", 1)),
        compost_factor=float(compost.get("factor", 1.0)),
        compost_days=int(compost.get("days", 0)),
    )
    if settings.apart < 0:
        raise ValueError("Two lots of a thing are kept apart by no less than no difference in freshness")
    if settings.compost_units < 1 or settings.compost_factor <= 0 or settings.compost_days < 0:
        raise ValueError(
            "A dressing of compost takes a unit or more, and makes a bed give more than nothing for no less than no days"
        )
    return settings
