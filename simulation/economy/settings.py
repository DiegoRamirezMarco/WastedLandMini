from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class EconomySettings:
    """The settlement's rules about work and what it buys."""

    # Credits earned per hour on duty, for a job that does not set its own wage.
    wage_per_hour: float = 2.0
    # What each resident is handed when a settlement first takes up a currency, and what
    # whoever joins one that trades with it arrives with.
    starting_credits: float = 8.0
    # What goes into the common fund for each resident when a currency is first taken up.
    fund_per_resident: float = 30.0
    # What the currency of a settlement that was already running is called, and one of it.
    credits_name: str = "vales"
    credits_singular: str = "vale"
    # Price of a thing as a multiple of its base value, with the shelf full.
    price_factor: float = 1.0
    # How much dearer a thing gets as it runs out: this much extra, divided by the units left.
    scarcity_markup: float = 1.0
    # Hours a job goes without enough people before the settlement takes notice.
    vacancy_notice_hours: int = 24
    # Length of the week that days off are counted in.
    week_days: int = 7
    # Under barter, the categories of thing whoever holds no job hands something over to be given.
    kept_categories: tuple[str, ...] = ("food",)
    # The most credit anybody takes at once from someone else, or from the fund.
    pilfer_max: float = 20.0
    # Days that pass before the residents can be asked again how they would trade.
    trade_ask_days: int = 3
    # Credits put by, and worth in things owned, from which either weighs all it can on how
    # someone would rather trade.
    savings_scale: float = 30.0
    goods_scale: float = 60.0


def economy_settings_from_data(data: dict[str, Any]) -> EconomySettings:
    defaults = EconomySettings()
    kept = data.get("kept_categories", defaults.kept_categories)
    if isinstance(kept, str) or not all(isinstance(category, str) for category in kept):
        raise ValueError("Economy kept categories must be a list of item categories")
    settings = EconomySettings(
        wage_per_hour=float(data.get("wage_per_hour", defaults.wage_per_hour)),
        starting_credits=float(data.get("starting_credits", defaults.starting_credits)),
        fund_per_resident=float(data.get("fund_per_resident", defaults.fund_per_resident)),
        credits_name=str(data.get("credits_name", defaults.credits_name)).strip(),
        credits_singular=str(data.get("credits_singular", defaults.credits_singular)).strip(),
        price_factor=float(data.get("price_factor", defaults.price_factor)),
        scarcity_markup=float(data.get("scarcity_markup", defaults.scarcity_markup)),
        vacancy_notice_hours=int(data.get("vacancy_notice_hours", defaults.vacancy_notice_hours)),
        week_days=int(data.get("week_days", defaults.week_days)),
        kept_categories=tuple(kept),
        pilfer_max=float(data.get("pilfer_max", defaults.pilfer_max)),
        trade_ask_days=int(data.get("trade_ask_days", defaults.trade_ask_days)),
        savings_scale=float(data.get("savings_scale", defaults.savings_scale)),
        goods_scale=float(data.get("goods_scale", defaults.goods_scale)),
    )
    amounts = (
        settings.wage_per_hour,
        settings.starting_credits,
        settings.scarcity_markup,
        settings.fund_per_resident,
        settings.pilfer_max,
    )
    if min(amounts) < 0:
        raise ValueError(
            "Economy wages, starting credits, scarcity markup, fund and pilfering must not be negative"
        )
    if settings.price_factor <= 0 or settings.vacancy_notice_hours < 1 or settings.week_days < 1:
        raise ValueError("Economy price factor, vacancy notice and week length must be positive")
    if settings.trade_ask_days < 0 or min(settings.savings_scale, settings.goods_scale) <= 0:
        raise ValueError("Economy days between askings must not be negative, and its scales must be positive")
    if not settings.credits_name or not settings.credits_singular:
        raise ValueError("Economy credits need a name, and a name for one of them")
    return settings
