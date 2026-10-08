"""What current is made of, as data (S55)."""

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class PowerSettings:
    # The item a generator burns.
    fuel: str = "fuel"
    # How long a unit of it lasts, in minutes of one unit of current being drawn: nine lamps
    # through a night of seven hours burn one. Nothing for fuel that is never used up.
    fuel_lasts: float = 3780.0


def power_settings_from_data(data: dict[str, Any]) -> PowerSettings:
    defaults = PowerSettings()
    settings = PowerSettings(
        fuel=str(data.get("fuel", defaults.fuel)), fuel_lasts=float(data.get("fuel_lasts", defaults.fuel_lasts))
    )
    if settings.fuel_lasts < 0:
        raise ValueError("A unit of fuel lasts no less than no time at all")
    return settings
