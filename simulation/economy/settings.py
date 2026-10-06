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
    # With a currency, what a meal out of the commons costs.
    meal_price: float = 1.0
    # Days somebody can go without working before the settlement stops keeping them.
    idle_days: int = 3
    # What somebody keeps by them before they spend on anybody else: a present, a drink, a loan.
    gift_savings: float = 15.0
    # What is lent at once, below how much somebody is short enough to be lent it, and the days
    # after which a loan not paid back tells on the two of them.
    loan_size: float = 10.0
    poor_below: float = 3.0
    loan_days: int = 7
    # Tags of what is found outside that is everybody's whatever happens: whoever goes out
    # under barter keeps one thing of each trip for themselves, and never one of these.
    common_finds: tuple[str, ...] = ("water", "fuel", "medicine", "scrap")
    # What a day without their wage does to a worker's mood and nerves.
    unpaid_mood: float = 4.0
    unpaid_stress: float = 5.0
    # Swaps turned down, and days running without a wage, after which somebody raises trading
    # another way.
    grumble_swaps: int = 3
    grumble_unpaid_days: int = 3
    # The kind of container a settlement with no counter keeps its fund in.
    strongbox_kind: str = "crate"


def economy_settings_from_data(data: dict[str, Any]) -> EconomySettings:
    defaults = EconomySettings()
    kept = data.get("kept_categories", defaults.kept_categories)
    if isinstance(kept, str) or not all(isinstance(category, str) for category in kept):
        raise ValueError("Economy kept categories must be a list of item categories")
    common = data.get("common_finds", defaults.common_finds)
    if isinstance(common, str) or not all(isinstance(tag, str) for tag in common):
        raise ValueError("Economy common finds must be a list of item tags")
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
        meal_price=float(data.get("meal_price", defaults.meal_price)),
        idle_days=int(data.get("idle_days", defaults.idle_days)),
        gift_savings=float(data.get("gift_savings", defaults.gift_savings)),
        loan_size=float(data.get("loan_size", defaults.loan_size)),
        poor_below=float(data.get("poor_below", defaults.poor_below)),
        loan_days=int(data.get("loan_days", defaults.loan_days)),
        common_finds=tuple(common),
        unpaid_mood=float(data.get("unpaid_mood", defaults.unpaid_mood)),
        unpaid_stress=float(data.get("unpaid_stress", defaults.unpaid_stress)),
        grumble_swaps=int(data.get("grumble_swaps", defaults.grumble_swaps)),
        grumble_unpaid_days=int(data.get("grumble_unpaid_days", defaults.grumble_unpaid_days)),
        strongbox_kind=str(data.get("strongbox_kind", defaults.strongbox_kind)),
    )
    amounts = (
        settings.wage_per_hour,
        settings.starting_credits,
        settings.scarcity_markup,
        settings.fund_per_resident,
        settings.pilfer_max,
        settings.meal_price,
        settings.gift_savings,
        settings.loan_size,
        settings.poor_below,
    )
    if min(amounts) < 0:
        raise ValueError(
            "Economy wages, prices, starting credits, scarcity markup, fund, loans and pilfering must not be negative"
        )
    if settings.price_factor <= 0 or settings.vacancy_notice_hours < 1 or settings.week_days < 1:
        raise ValueError("Economy price factor, vacancy notice and week length must be positive")
    if settings.trade_ask_days < 0 or min(settings.savings_scale, settings.goods_scale) <= 0:
        raise ValueError("Economy days between askings must not be negative, and its scales must be positive")
    if min(settings.idle_days, settings.loan_days, settings.grumble_swaps, settings.grumble_unpaid_days) < 1:
        raise ValueError("Economy days and counts before something is done about it must be one or more")
    if not settings.credits_name or not settings.credits_singular:
        raise ValueError("Economy credits need a name, and a name for one of them")
    return settings
