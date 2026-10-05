from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class EconomySettings:
    """The settlement's rules about work and what it buys."""

    # Credits earned per hour on duty, for a job that does not set its own wage.
    wage_per_hour: float = 2.0
    # What a resident has in their pocket when a settlement starts.
    starting_credits: float = 8.0
    # Price of a thing as a multiple of its base value, with the shelf full.
    price_factor: float = 1.0
    # How much dearer a thing gets as it runs out: this much extra, divided by the units left.
    scarcity_markup: float = 1.0
    # Hours a job goes without enough people before the settlement takes notice.
    vacancy_notice_hours: int = 24
    # Length of the week that days off are counted in.
    week_days: int = 7


def economy_settings_from_data(data: dict[str, Any]) -> EconomySettings:
    defaults = EconomySettings()
    settings = EconomySettings(
        wage_per_hour=float(data.get("wage_per_hour", defaults.wage_per_hour)),
        starting_credits=float(data.get("starting_credits", defaults.starting_credits)),
        price_factor=float(data.get("price_factor", defaults.price_factor)),
        scarcity_markup=float(data.get("scarcity_markup", defaults.scarcity_markup)),
        vacancy_notice_hours=int(data.get("vacancy_notice_hours", defaults.vacancy_notice_hours)),
        week_days=int(data.get("week_days", defaults.week_days)),
    )
    if min(settings.wage_per_hour, settings.starting_credits, settings.scarcity_markup) < 0:
        raise ValueError("Economy wages, starting credits and scarcity markup must not be negative")
    if settings.price_factor <= 0 or settings.vacancy_notice_hours < 1 or settings.week_days < 1:
        raise ValueError("Economy price factor, vacancy notice and week length must be positive")
    return settings
