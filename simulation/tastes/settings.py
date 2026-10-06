"""The rules tastes go by, read from `data/tastes.json`."""

from dataclasses import dataclass, field
from typing import Any

from simulation.residents.personality import Personality
from simulation.social.relationship import FEELINGS
from simulation.tastes.taste import CATEGORY, ITEM, PEOPLE, TAG

HATED, DISLIKED, NEUTRAL, LIKED, LOVED = "hated", "disliked", "neutral", "liked", "loved"
# From the worst to the best.
REACTIONS = (HATED, DISLIKED, NEUTRAL, LIKED, LOVED)
# What a reaction is to: a meal, a drink, a thing used, a thing handed over.
EATEN, DRUNK, USED, GIVEN = "eaten", "drunk", "used", "given"
UNKNOWN, SUSPECTED, KNOWN = "unknown", "suspected", "known"
# What may be passing between two people when a taste in people comes into it: any friendly
# exchange, a piece of gossip, or being told what to do.
EXCHANGE, RUMOR, ADVICE = "exchange", "rumor", "advice"
# Seeing someone with something on them that they have taken.
UNDER = "under"
OCCASIONS = (EXCHANGE, RUMOR, ADVICE, UNDER)


def side_of(reaction: str) -> int:
    """Which way a reaction goes: -1 against, 1 for, 0 neither."""
    if reaction in (HATED, DISLIKED):
        return -1
    return 1 if reaction in (LIKED, LOVED) else 0


@dataclass(frozen=True)
class PeopleTaste:
    """Something about another person, or about what passes between two, that a resident may like or not."""

    taste_id: str
    name: str
    # What the other has to be like: for each side of their personality, the least and the most.
    who: dict[str, tuple[float, float]] = field(default_factory=dict)
    # Jobs any one of which the other has to hold.
    jobs: tuple[str, ...] = ()
    # What has to be passing between them. With none given, any friendly exchange.
    when: tuple[str, ...] = ()
    # Signs of something taken, any one of which the other has to have on them.
    under: tuple[str, ...] = ()
    # The feeling for the other that it moves.
    feeling: str = "affection"


@dataclass(frozen=True)
class ReactionEffects:
    """What a reaction does to whoever has it, and to what they feel for whoever gave the thing."""

    mood: float = 0.0
    affection: float = 0.0
    trust: float = 0.0
    # How much it shows: what an onlooker learns of their tastes from seeing it.
    shows: float = 0.0


@dataclass(frozen=True)
class TasteSettings:
    # How much the taste for an item's category counts beside the taste for its tags.
    category_weight: float = 0.35
    # How much the strongest taste there can be for the item itself counts over its category and
    # tags. A milder one counts for less, and the rest is theirs.
    item_weight: float = 0.7
    # A leaning for a category is this much milder than one for a tag.
    category_scale: float = 0.5
    # How often someone has a taste for one item in particular, and how strong it is then.
    quirk_chance: float = 0.15
    quirk_range: tuple[float, float] = (60.0, 100.0)
    # From what liking each reaction begins. Between `disliked` and `liked` it is neutral.
    thresholds: dict[str, float] = field(
        default_factory=lambda: {HATED: -60.0, DISLIKED: -20.0, LIKED: 20.0, LOVED: 60.0}
    )
    # What the moment adds to a liking, at the most: a pressing need answered, good spirits, and
    # fondness for whoever handed the thing over.
    need_bonus: float = 15.0
    mood_bonus: float = 8.0
    fondness_bonus: float = 20.0
    effects: dict[str, ReactionEffects] = field(default_factory=dict)
    # Stress eased by a meal liked as much as can be, and added by one loathed as much.
    meal_stress: float = 6.0
    # How much a liking counts beside what a food does, when choosing what to eat.
    food_choice: float = 0.3
    # What a thing is worth to someone over its base value, as shares of it: for being liked as
    # much as can be, for answering a pressing need, for having come from someone dear, and for
    # being the only one there is.
    worth_taste: float = 0.6
    worth_need: float = 0.5
    worth_keepsake: float = 0.5
    worth_scarcity: float = 0.3
    # How much has to have been seen of a taste for it to be suspected, and to be known.
    suspected_at: float = 1.0
    known_at: float = 3.0
    # Seen in a reaction, a category shows this much of what the item itself does.
    category_share: float = 0.25
    # How often a friendly exchange has someone speak of a taste of theirs, and how much that shows.
    mention_chance: float = 0.1
    mention_shows: float = 1.5
    # A swap turned down over a taste, and a thing bought, show this much.
    refusal_shows: float = 1.0
    purchase_shows: float = 0.5
    # What a taste is called where it is spoken of, by kind and name. One with no name of its own
    # is called by its ID.
    names: dict[str, dict[str, str]] = field(default_factory=dict)
    # What is said of a reaction, by what it is to and which it is, with `{name}`, `{thing}` and `{giver}`.
    lines: dict[str, dict[str, str]] = field(default_factory=dict)
    # What there is to like or not about people, by ID.
    people: dict[str, PeopleTaste] = field(default_factory=dict)
    # How far the strongest taste in people moves a feeling each time it comes into it, how much
    # that shows, and how much more or less advice counts with whoever feels strongly about being given it.
    people_push: float = 2.0
    people_shows: float = 0.4
    advice_weight: float = 0.4
    # How far something lived through that mattered as much as anything can moves what is learned.
    learning: float = 60.0
    # How much the first time of a taste matters, and being handed a thing by someone.
    first_mark: float = 0.05
    keepsake_mark: float = 0.15
    # What having a thing again adds to or takes from the taste for each of its tags, and how far
    # that alone can take it. Tags named in `habits` go that many times as fast and as far.
    exposure: float = 0.4
    exposure_cap: float = 12.0
    habits: dict[str, float] = field(default_factory=dict)
    # The harm a meal that turns on someone does, and the harm that matters as much as anything can.
    # Its tags are blamed this much of what the thing itself is.
    sickness_harm: tuple[int, int] = (8, 30)
    sickness_full: float = 30.0
    sickness_tags: float = 0.5

    def effects_of(self, reaction: str) -> ReactionEffects:
        return self.effects.get(reaction, ReactionEffects())

    def name_of(self, kind: str, name: str) -> str | None:
        if kind == PEOPLE:
            return self.people[name].name if name in self.people else None
        return self.names.get(kind, {}).get(name)


def taste_settings_from_data(data: dict[str, Any]) -> TasteSettings:
    defaults = TasteSettings()
    weights = _object(data.get("weights"))
    leaning = _object(data.get("leaning"))
    moment = _object(data.get("moment"))
    worth = _object(data.get("worth"))
    found_out = _object(data.get("found_out"))
    quirk = leaning.get("quirk_range", defaults.quirk_range)
    learned = _object(data.get("learning"))
    with_people = _object(data.get("with_people"))
    harm = learned.get("sickness_harm", defaults.sickness_harm)
    thresholds = {**defaults.thresholds, **{str(k): float(v) for k, v in _object(data.get("thresholds")).items()}}
    settings = TasteSettings(
        category_weight=float(weights.get("category", defaults.category_weight)),
        item_weight=float(weights.get("item", defaults.item_weight)),
        category_scale=float(leaning.get("category_scale", defaults.category_scale)),
        quirk_chance=float(leaning.get("quirk_chance", defaults.quirk_chance)),
        quirk_range=(float(quirk[0]), float(quirk[1])),
        thresholds=thresholds,
        need_bonus=float(moment.get("need", defaults.need_bonus)),
        mood_bonus=float(moment.get("mood", defaults.mood_bonus)),
        fondness_bonus=float(moment.get("fondness", defaults.fondness_bonus)),
        effects={
            str(reaction): ReactionEffects(
                mood=float(values.get("mood", 0.0)),
                affection=float(values.get("affection", 0.0)),
                trust=float(values.get("trust", 0.0)),
                shows=float(values.get("shows", 0.0)),
            )
            for reaction, values in _object(data.get("effects")).items()
            if isinstance(values, dict)
        },
        meal_stress=float(data.get("meal_stress", defaults.meal_stress)),
        food_choice=float(data.get("food_choice", defaults.food_choice)),
        worth_taste=float(worth.get("taste", defaults.worth_taste)),
        worth_need=float(worth.get("need", defaults.worth_need)),
        worth_keepsake=float(worth.get("keepsake", defaults.worth_keepsake)),
        worth_scarcity=float(worth.get("scarcity", defaults.worth_scarcity)),
        suspected_at=float(found_out.get("suspected", defaults.suspected_at)),
        known_at=float(found_out.get("known", defaults.known_at)),
        category_share=float(found_out.get("category_share", defaults.category_share)),
        mention_chance=float(found_out.get("mention_chance", defaults.mention_chance)),
        mention_shows=float(found_out.get("mention", defaults.mention_shows)),
        refusal_shows=float(found_out.get("refusal", defaults.refusal_shows)),
        purchase_shows=float(found_out.get("purchase", defaults.purchase_shows)),
        names={
            str(kind): {str(name): str(label) for name, label in _object(labels).items()}
            for kind, labels in _object(data.get("names")).items()
        },
        lines={
            str(how): {str(reaction): str(line) for reaction, line in _object(lines).items()}
            for how, lines in _object(data.get("lines")).items()
        },
        people={
            str(taste_id): PeopleTaste(
                taste_id=str(taste_id),
                name=str(values.get("name", taste_id)),
                who={str(side): (float(span[0]), float(span[1])) for side, span in _object(values.get("who")).items()},
                jobs=tuple(str(job) for job in values.get("jobs", [])),
                when=tuple(str(occasion) for occasion in values.get("when", [])),
                under=tuple(str(sign) for sign in values.get("under", [])),
                feeling=str(values.get("feeling", "affection")),
            )
            for taste_id, values in _object(data.get("people")).items()
            if isinstance(values, dict)
        },
        people_push=float(with_people.get("push", defaults.people_push)),
        people_shows=float(with_people.get("shows", defaults.people_shows)),
        advice_weight=float(with_people.get("advice", defaults.advice_weight)),
        learning=float(learned.get("most", defaults.learning)),
        first_mark=float(learned.get("first_time", defaults.first_mark)),
        keepsake_mark=float(learned.get("present", defaults.keepsake_mark)),
        exposure=float(learned.get("exposure", defaults.exposure)),
        exposure_cap=float(learned.get("exposure_cap", defaults.exposure_cap)),
        habits={str(tag): float(times) for tag, times in _object(learned.get("habits")).items()},
        sickness_harm=(int(harm[0]), int(harm[1])),
        sickness_full=float(learned.get("sickness_full", defaults.sickness_full)),
        sickness_tags=float(learned.get("sickness_tags", defaults.sickness_tags)),
    )
    sides = set(vars(Personality()))
    for taste in settings.people.values():
        if taste.feeling not in FEELINGS:
            raise ValueError(f"Taste in people {taste.taste_id} moves an unknown feeling: {taste.feeling}")
        if set(taste.who) - sides:
            raise ValueError(f"Taste in people {taste.taste_id} asks for unknown sides of a personality: {sorted(set(taste.who) - sides)}")
        if set(taste.when) - set(OCCASIONS):
            raise ValueError(f"Taste in people {taste.taste_id} comes into unknown occasions: {sorted(set(taste.when) - set(OCCASIONS))}")
        if not (taste.who or taste.jobs or taste.when):
            raise ValueError(f"Taste in people {taste.taste_id} is for nobody and nothing in particular")
    if settings.sickness_harm[0] > settings.sickness_harm[1] or settings.sickness_harm[0] < 1 or settings.sickness_full <= 0:
        raise ValueError("The harm of a meal that turns on someone must be a range of at least 1, and what counts as full harm more than nothing")
    if min(settings.learning, settings.exposure, settings.exposure_cap, settings.first_mark, settings.keepsake_mark) < 0:
        raise ValueError("What moves a taste is given as amounts that are not negative")
    if any(times <= 0 for times in settings.habits.values()):
        raise ValueError("A habit is so many times as fast as anything else: more than nothing")
    unknown = (set(settings.effects) | set(_object(data.get("thresholds")))) - set(REACTIONS)
    if unknown:
        raise ValueError(f"Unknown reactions in the taste settings: {sorted(unknown)}")
    ordered = [settings.thresholds[HATED], settings.thresholds[DISLIKED], settings.thresholds[LIKED], settings.thresholds[LOVED]]
    if ordered != sorted(ordered) or not ordered[1] < 0 < ordered[2]:
        raise ValueError("Taste thresholds must rise from hated to loved, with neutral round nothing")
    if not 0.0 <= settings.item_weight <= 1.0 or not 0.0 <= settings.quirk_chance <= 1.0:
        raise ValueError("The weight of an item's own taste and the chance of a quirk are shares, from 0 to 1")
    if not 0 < settings.suspected_at <= settings.known_at:
        raise ValueError("A taste is suspected before it is known")
    if set(settings.names) - {CATEGORY, TAG, ITEM}:
        raise ValueError("Tastes are named by category and by tag, and those in people where they are defined")
    return settings


def _object(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}
