"""Laws as data, and the laws a settlement has in force as state.

A law is never only words. Each degree of one names effects that the rest of the simulation
asks about: whether a thing may be used, what a shift lasts, what a wage comes to. No law has
code of its own.
"""

from dataclasses import dataclass, field
from typing import Any

from simulation.politics import opinion

# What a degree of a law may do. Hours are given as `[from, to]` and may wrap past midnight.
#   curfew: hours in which nobody is out of doors.
#   closes: kinds of object nobody uses.
#   bans_tags: tags of item nobody takes. bans_item: nobody takes the item the law names.
#   day_off: a day of the week, from 0, on which nobody works. leader_birthday: nor on that day.
#   shift_hours: hours the working day is longer by, or shorter if less than none.
#   wage_factor: how many times the usual wage is paid. tax: the share of it the fund keeps.
#   meals: how many times a day anybody eats out of what is common.
#   meal_price: how many times the usual price a meal out of the commons costs.
#   common: what is kept in a container is nobody's.
#   gate: `closed` for nobody from outside being let in.
#   excused: who does not work and is kept all the same: `expecting`.
#   requires: a `kind` of object everybody gathers at, at an `hour`.
#   quiet: hours in which nobody talks to anybody.
#   salute: whoever leads is greeted by whoever comes across them.
#   dark: kinds of object that give no light at night.
EFFECTS = (
    "curfew", "closes", "bans_tags", "bans_item", "day_off", "leader_birthday", "shift_hours",
    "wage_factor", "tax", "meals", "meal_price", "common", "gate", "excused", "requires", "quiet",
    "salute", "dark",
)
# What may bring a resident to propose a law: something of their own they have had enough of
# (`need_above`), how little or how much there is of something (`stock_below`, `fund_below`,
# `fund_above`), things they know to have happened (`known_facts`), holding strongly that it
# should be so (`conviction`), or having a stake in it (`stake`).
MOTIVES = ("need_above", "stock_below", "fund_below", "fund_above", "known_facts", "conviction", "stake")
EXCUSES = ("expecting",)
# What a law may ask of whoever proposes it: the food they like least.
PARAMS = ("hated_food",)
GATE_CLOSED = "closed"


@dataclass(frozen=True)
class LawDegree:
    """How far a law goes: what it is called at that, what it does, and how much more or less
    it weighs with people than the law as written."""

    name: str
    effects: dict[str, Any] = field(default_factory=dict)
    weight: float = 1.0


@dataclass(frozen=True)
class LawDefinition:
    law_id: str
    name: str
    # What it says, as it would be cried out: `de noche cada uno en su casa`.
    text: str
    # From the mildest to the harshest. A law is always in force at one of them.
    degrees: tuple[LawDegree, ...]
    # What weighs for or against it with each resident, and what it starts from.
    opinion: dict[str, float] = field(default_factory=dict)
    bias: float = 0.0
    # What it adds to how authoritarian the settlement is, at a degree of weight 1.
    harsh: float = 0.0
    # How hard it is to keep, from 0 to 1.
    burden: float = 0.0
    # Whether it is a nonsense, which costs whoever passes it, and whether it may come of the
    # whim of whoever leads, with what makes them want it.
    absurd: bool = False
    whim: bool = False
    whim_opinion: dict[str, float] = field(default_factory=dict)
    # Laws it cannot stand beside: passing it does away with them.
    excludes: tuple[str, ...] = ()
    # What brings a resident to propose it. None for one nobody thinks of unasked.
    motive: dict[str, Any] | None = None
    # What whoever proposes it has to name: one of PARAMS.
    param: str | None = None
    # What there has to be for it to make sense: a currency, somebody who leads, a kind of object.
    needs_currency: bool = False
    needs_leader: bool = False
    needs_kind: str | None = None


@dataclass(frozen=True)
class ProtestSettings:
    """Taking to the square against a law in force (S45)."""

    # The kind of object people gather at, how near it counts as being there, and the hours.
    kind: str = "plaza"
    reach: int = 3
    hours: tuple[int, int] = (12, 15)
    # How much somebody has to be against a law to go, how much a law counts that was put on
    # them with nobody asked and one that was voted, and the days after which they give it up.
    start: float = 0.3
    imposed: float = 1.0
    voted: float = 0.5
    tire_days: int = 6
    # What a day of it does where it is put up with, for everybody out: to unrest and to
    # legitimacy. How authoritarian the settlement has to be for it to be leaned on instead,
    # and what that leaves in whoever was there and adds to how authoritarian it is.
    unrest: float = 12.0
    legitimacy: float = -6.0
    harsh_from: float = 60.0
    cowed_fear: float = 6.0
    cowed_resentment: float = 4.0
    harsh_authoritarianism: float = 4.0
    # What the law being done away with, or made milder, does: to the trust in the player of
    # whoever was out against it, to what they hold against the government, and to legitimacy.
    given_in_trust: float = 8.0
    given_in_resentment: float = -6.0
    given_in_legitimacy: float = 2.0


@dataclass(frozen=True)
class LawSettings:
    laws: dict[str, LawDefinition] = field(default_factory=dict)
    protest: ProtestSettings = field(default_factory=ProtestSettings)
    # Keeping a law: how far somebody has to do as the government says to keep one that is no
    # trouble, what a burdensome one adds to that, how much what they make of it counts, how
    # much of the government's legitimacy goes into keeping what it passes, and how far the
    # bar moves from one day to the next for the same person.
    keep_base: float = 20.0
    keep_burden: float = 30.0
    keep_regard: float = 30.0
    keep_legitimacy: float = 0.2
    keep_jitter: float = 10.0
    # What a day under a law somebody is against adds to what they hold against the government,
    # what a day under one they are for adds to their trust in it, and what either does to
    # their trust in the player if the player was behind it.
    grind_resentment: float = 0.6
    grind_trust: float = 0.3
    grind_player: float = 0.4
    # Being seen to break a law: how much it matters, what it does to what somebody who keeps
    # that law feels for whoever broke it, and to what somebody who does not keep it either does.
    breach_importance: int = 35
    breach_trust: float = -4.0
    breach_resentment: float = 3.0
    breach_fellow: float = 2.0
    # How near a thing counts as being at it, and how near whoever leads as coming across them.
    attend_reach: int = 4
    salute_reach: int = 2
    # Hunger from which nobody keeps a law that stands between them and food, and the units of
    # food for each resident with which nobody thinks the settlement short of it.
    desperate_hunger: float = 85.0
    plenty_per_resident: float = 6.0
    # How authoritarian a settlement has to be for whoever leads to pass a whim, the chance of
    # one a day in the most authoritarian of them, and what passing a nonsense does to legitimacy.
    whim_from: float = 50.0
    whim_chance: float = 0.25
    absurd_legitimacy: float = -4.0


def _hours(value: Any, where: str) -> tuple[int, int]:
    if not isinstance(value, (list, tuple)) or len(value) != 2 or not all(0 <= int(hour) <= 23 for hour in value):
        raise ValueError(f"{where} must be two hours from 0 to 23")
    return int(value[0]), int(value[1])


def _kinds(value: Any, where: str) -> tuple[str, ...]:
    if not isinstance(value, (list, tuple)) or not value or not all(isinstance(kind, str) for kind in value):
        raise ValueError(f"{where} must be a list of IDs")
    return tuple(value)


def _effects(data: Any, where: str) -> dict[str, Any]:
    if not isinstance(data, dict) or not data:
        raise ValueError(f"{where} must do something")
    unknown = sorted(set(data) - set(EFFECTS))
    if unknown:
        raise ValueError(f"{where} has effects nothing asks about: {unknown}")
    effects: dict[str, Any] = {}
    for effect, value in data.items():
        if effect in ("curfew", "quiet"):
            effects[effect] = _hours(value, f"The {effect} of {where}")
        elif effect in ("closes", "bans_tags", "dark"):
            effects[effect] = _kinds(value, f"What {where} {effect}")
        elif effect == "excused":
            effects[effect] = _kinds(value, f"Who {where} excuses")
            if any(excuse not in EXCUSES for excuse in effects[effect]):
                raise ValueError(f"{where} excuses somebody it cannot tell: one of {EXCUSES}")
        elif effect in ("bans_item", "leader_birthday", "common", "salute"):
            effects[effect] = bool(value)
        elif effect in ("day_off", "meals"):
            effects[effect] = int(value)
            if effects[effect] < 0:
                raise ValueError(f"{where} has a {effect} of less than none")
        elif effect in ("shift_hours", "wage_factor", "tax", "meal_price"):
            effects[effect] = float(value)
            if effect != "shift_hours" and effects[effect] < 0 or effect == "tax" and effects[effect] >= 1:
                raise ValueError(f"{where} has a {effect} that makes no sense")
        elif effect == "gate":
            if value != GATE_CLOSED:
                raise ValueError(f"{where} can only have the gate {GATE_CLOSED}")
            effects[effect] = GATE_CLOSED
        elif effect == "requires":
            if not isinstance(value, dict) or "kind" not in value or "hour" not in value:
                raise ValueError(f"{where} requires a kind of object and an hour")
            effects[effect] = {"kind": str(value["kind"]), "hour": int(value["hour"])}
            if not 0 <= effects[effect]["hour"] <= 23:
                raise ValueError(f"{where} gathers everybody at an hour there is not")
    return effects


def _weights(data: Any, where: str) -> dict[str, float]:
    if not isinstance(data, dict):
        raise ValueError(f"{where} must be an object of numbers")
    weights = {str(key): float(value) for key, value in data.items()}
    opinion.check(weights, where)
    return weights


def law_definition_from_data(law_id: str, data: Any) -> LawDefinition:
    if not isinstance(data, dict) or not {"name", "text", "degrees"} <= data.keys():
        raise ValueError(f"Law {law_id} needs a name, a text and its degrees")
    degrees = tuple(
        LawDegree(
            name=str(degree.get("name", "")),
            effects=_effects(degree.get("effects"), f"law {law_id}"),
            weight=float(degree.get("weight", 1.0)),
        )
        for degree in data["degrees"]
        if isinstance(degree, dict)
    )
    if not degrees or len(degrees) != len(data["degrees"]) or any(degree.weight <= 0 for degree in degrees):
        raise ValueError(f"Law {law_id} needs at least one degree, each with a weight above nothing")
    motive = data.get("motive")
    if motive is not None and (not isinstance(motive, dict) or len(motive) != 1 or next(iter(motive)) not in MOTIVES):
        raise ValueError(f"Law {law_id} has a motive that is not one of {MOTIVES}")
    param = str(data["param"]) if data.get("param") else None
    if param is not None and param not in PARAMS:
        raise ValueError(f"Law {law_id} asks for something nobody can name: one of {PARAMS}")
    names_item = any(degree.effects.get("bans_item") for degree in degrees)
    if names_item != (param is not None):
        raise ValueError(f"Law {law_id} has to ask for an item if it bans one, and for nothing if not")
    definition = LawDefinition(
        law_id=law_id,
        name=str(data["name"]),
        text=str(data["text"]),
        degrees=degrees,
        opinion=_weights(data.get("opinion", {}), f"The opinion of law {law_id}"),
        bias=float(data.get("bias", 0.0)),
        harsh=float(data.get("harsh", 0.0)),
        burden=float(data.get("burden", 0.0)),
        absurd=bool(data.get("absurd", False)),
        whim=bool(data.get("whim", False)),
        whim_opinion=_weights(data.get("whim_opinion", {}), f"The whim behind law {law_id}"),
        excludes=tuple(str(other) for other in data.get("excludes", [])),
        motive=dict(motive) if motive is not None else None,
        param=param,
        needs_currency=bool(data.get("needs_currency", False)),
        needs_leader=bool(data.get("needs_leader", False)),
        needs_kind=str(data["needs_kind"]) if data.get("needs_kind") else None,
    )
    if not 0.0 <= definition.burden <= 1.0:
        raise ValueError(f"Law {law_id} has a burden outside 0 to 1")
    return definition


def protest_settings_from_data(data: Any) -> ProtestSettings:
    defaults = ProtestSettings()
    if not isinstance(data, dict):
        return defaults
    numbers = {
        name: type(getattr(defaults, name))(data[name])
        for name in vars(defaults)
        if name in data and name not in ("kind", "hours", "start")
    }
    settings = ProtestSettings(
        kind=str(data.get("kind", defaults.kind)),
        hours=_hours(data["hours"], "The hours of a protest") if "hours" in data else defaults.hours,
        start=float(data.get("from", defaults.start)),
        **numbers,
    )
    if settings.reach < 0 or settings.tire_days < 1 or settings.start <= 0 or settings.hours[0] >= settings.hours[1]:
        raise ValueError("A protest is within a reach of no less than nothing, for a day at least, in hours of one day")
    return settings


def law_settings_from_data(data: dict[str, Any]) -> LawSettings:
    defaults = LawSettings()
    keeping = data.get("keeping", {})
    grind = data.get("grind", {})
    breach = data.get("breach", {})
    laws = {
        str(law_id): law_definition_from_data(str(law_id), values) for law_id, values in data.get("laws", {}).items()
    }
    for law_id, law in laws.items():
        unknown = [other for other in law.excludes if other not in laws]
        if unknown:
            raise ValueError(f"Law {law_id} cannot stand beside laws there are not: {unknown}")
    settings = LawSettings(
        laws=laws,
        protest=protest_settings_from_data(data.get("protest")),
        keep_base=float(keeping.get("base", defaults.keep_base)),
        keep_burden=float(keeping.get("burden", defaults.keep_burden)),
        keep_regard=float(keeping.get("regard", defaults.keep_regard)),
        keep_legitimacy=float(keeping.get("legitimacy", defaults.keep_legitimacy)),
        keep_jitter=float(keeping.get("jitter", defaults.keep_jitter)),
        grind_resentment=float(grind.get("resentment", defaults.grind_resentment)),
        grind_trust=float(grind.get("trust", defaults.grind_trust)),
        grind_player=float(grind.get("player_trust", defaults.grind_player)),
        breach_importance=int(breach.get("importance", defaults.breach_importance)),
        breach_trust=float(breach.get("trust", defaults.breach_trust)),
        breach_resentment=float(breach.get("resentment", defaults.breach_resentment)),
        breach_fellow=float(breach.get("fellow", defaults.breach_fellow)),
        attend_reach=int(data.get("attend_reach", defaults.attend_reach)),
        salute_reach=int(data.get("salute_reach", defaults.salute_reach)),
        desperate_hunger=float(data.get("desperate_hunger", defaults.desperate_hunger)),
        plenty_per_resident=float(data.get("plenty_per_resident", defaults.plenty_per_resident)),
        whim_from=float(data.get("whim_from", defaults.whim_from)),
        whim_chance=float(data.get("whim_chance", defaults.whim_chance)),
        absurd_legitimacy=float(data.get("absurd_legitimacy", defaults.absurd_legitimacy)),
    )
    if settings.attend_reach < 0 or settings.salute_reach < 0 or not 0.0 <= settings.whim_chance <= 1.0:
        raise ValueError("Laws are kept within a reach of no less than nothing, and whims come by a chance from 0 to 1")
    return settings
