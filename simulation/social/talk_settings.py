"""What talk is made of, as data (`data/talk.json`, S58): the lists of words the settlement
keeps, the phrases a resident has of their own, the patterns a subject is put into words by,
and what bringing a subject up does to how two people get on."""

from dataclasses import dataclass, field
from typing import Any

from simulation.social.relationship import FEELINGS
from simulation.tastes.settings import REACTIONS

DEFAULT_PATTERN = ("{word}",)
# When a phrase of somebody's own comes out.
BEGIN, ANY, GLAD, LOW, ANGRY = "begin", "any", "glad", "low", "angry"
WHENS = (BEGIN, ANY, GLAD, LOW, ANGRY)


@dataclass(frozen=True)
class WordList:
    """A list of words of the settlement's: what it is called, what a resident says to ask
    for one more, the words it comes with, and the patterns a word of it is talked of by."""

    list_id: str
    name: str
    ask: str = ""
    words: tuple[str, ...] = ()
    patterns: tuple[str, ...] = DEFAULT_PATTERN


@dataclass(frozen=True)
class PhraseKind:
    """One of the phrases a resident has of their own: how they greet, what they keep saying.
    `when` is when it comes out: as a talk begins, at any time, or glad, low or angry."""

    phrase_id: str
    name: str
    ask: str = ""
    when: str = ANY


@dataclass(frozen=True)
class TalkSettings:
    lists: dict[str, WordList] = field(default_factory=dict)
    phrases: dict[str, PhraseKind] = field(default_factory=dict)
    # How a thing is talked of, by its category, with `default` for any other; how somebody
    # is; and how something heard is. `{item}`, `{an_item}`, `{pj}` and `{fact}` are filled in.
    item_patterns: dict[str, tuple[str, ...]] = field(default_factory=dict)
    person_patterns: tuple[str, ...] = ("{pj}",)
    fact_patterns: tuple[str, ...] = ("{fact}",)
    # What a subject does to what whoever listens feels for whoever brought it up, by how
    # they take it: one of the five reactions of a taste.
    taken: dict[str, dict[str, float]] = field(default_factory=dict)
    # How much of the good of the talk itself comes to whoever listens, by the same, and how
    # it is said that they took it so: `{listener}`, `{speaker}` and `{subject}` are filled in.
    relish: dict[str, float] = field(default_factory=dict)
    lines: dict[str, str] = field(default_factory=dict)
    # How much of the listener's taste shows each time, as a taste shows (S19).
    shows: float = 0.5
    # How much somebody has to like a thing to bring it up of their own accord, how much they
    # have to feel for somebody to talk of them, and from how much resentment or affection
    # hearing of somebody is unwelcome or welcome.
    fond_from: float = 15.0
    # How much less somebody brings up what they have seen the other dislike, and how much
    # more what they have seen them like.
    shunned: float = 0.25
    favoured: float = 1.5
    talked_of_from: float = 20.0
    sore_from: float = 30.0
    # How likely somebody with news the other has not heard is to make it the subject, before
    # how sociable they are is added: what the chance of passing a rumour on has always been.
    news_chance: float = 0.3
    # What a resident is told when they are told what to talk about with somebody: one of the
    # orders of `data/affect.json`. With none they are told nothing, and it keeps.
    order: str = ""
    # When in the day residents think of asking the player for something, how likely each is
    # to, how many may be waiting at once, how long one waits, and how much they have to like
    # somebody to wonder what to talk to them about.
    ask_hour: int = 10
    ask_chance: float = 0.0
    most_asks: int = 3
    lapse_hours: int = 24
    subject_from: float = 20.0
    nickname_from: float = 40.0
    nickname_ask: str = "¿Cómo llamo a {other}?"
    subject_ask: str = "¿De qué hablo con {other}?"
    # The list a subject made up on the spot goes into.
    new_subjects: str = ""
    # For how many minutes of a talk each says how they greet; every how many minutes a
    # phrase of their own may come out, in company and alone, for how many it is seen and how
    # likely it is to; and the mood and the stress from which what they say glad, low and
    # angry does.
    greet_minutes: int = 3
    say_every: int = 6
    alone_every: int = 60
    say_minutes: int = 2
    say_chance: float = 0.3
    glad_from: float = 75.0
    low_below: float = 30.0
    angry_from: float = 70.0
    # The most letters a word or a phrase has.
    longest: int = 40

    @property
    def enabled(self) -> bool:
        return bool(self.lists) or bool(self.item_patterns)


def _patterns(data: Any, fallback: tuple[str, ...]) -> tuple[str, ...]:
    found = tuple(str(each) for each in data) if isinstance(data, list) else ()
    return found or fallback


def talk_settings_from_data(data: dict[str, Any]) -> TalkSettings:
    defaults = TalkSettings()
    lists = {}
    for list_id, values in data.get("lists", {}).items():
        if not isinstance(values, dict) or "name" not in values:
            raise ValueError(f"List of words {list_id} needs a name")
        lists[str(list_id)] = WordList(
            str(list_id),
            str(values["name"]),
            str(values.get("ask", "")),
            tuple(str(word) for word in values.get("words", [])),
            _patterns(values.get("patterns"), DEFAULT_PATTERN),
        )
    phrases = {}
    for phrase_id, values in data.get("phrases", {}).items():
        if not isinstance(values, dict) or "name" not in values:
            raise ValueError(f"Phrase {phrase_id} needs a name")
        when = str(values.get("when", ANY))
        if when not in WHENS:
            raise ValueError(f"Phrase {phrase_id} comes out one of {WHENS}: {when}")
        phrases[str(phrase_id)] = PhraseKind(str(phrase_id), str(values["name"]), str(values.get("ask", "")), when)
    taken = {}
    for reaction, changes in data.get("taken", {}).items():
        if reaction not in REACTIONS or set(changes) - set(FEELINGS):
            raise ValueError(f"A subject is taken one of {REACTIONS}, and moves feelings there are: {reaction}")
        taken[str(reaction)] = {str(feeling): float(delta) for feeling, delta in changes.items()}
    relish, lines = data.get("relish", {}), data.get("lines", {})
    if set(relish) - set(REACTIONS) or set(lines) - set(REACTIONS):
        raise ValueError(f"A subject is taken one of {REACTIONS}")
    asks, saying, weights = data.get("asks", {}), data.get("saying", {}), data.get("weights", {})
    settings = TalkSettings(
        lists=lists,
        phrases=phrases,
        item_patterns={
            str(category): _patterns(patterns, ("{item}",)) for category, patterns in data.get("items", {}).items()
        },
        person_patterns=_patterns(data.get("people"), defaults.person_patterns),
        fact_patterns=_patterns(data.get("heard"), defaults.fact_patterns),
        taken=taken,
        relish={str(reaction): max(0.0, float(share)) for reaction, share in relish.items()},
        lines={str(reaction): str(line) for reaction, line in lines.items()},
        shows=float(data.get("shows", defaults.shows)),
        fond_from=float(weights.get("fond_from", defaults.fond_from)),
        shunned=max(0.0, float(weights.get("shunned", defaults.shunned))),
        favoured=max(0.0, float(weights.get("favoured", defaults.favoured))),
        talked_of_from=float(weights.get("talked_of_from", defaults.talked_of_from)),
        sore_from=float(weights.get("sore_from", defaults.sore_from)),
        news_chance=float(weights.get("news", defaults.news_chance)),
        order=str(data.get("order", defaults.order)),
        ask_hour=int(asks.get("hour", defaults.ask_hour)),
        ask_chance=float(asks.get("chance", defaults.ask_chance)),
        most_asks=int(asks.get("most", defaults.most_asks)),
        lapse_hours=int(asks.get("lapse_hours", defaults.lapse_hours)),
        subject_from=float(asks.get("subject_from", defaults.subject_from)),
        nickname_from=float(asks.get("nickname_from", defaults.nickname_from)),
        nickname_ask=str(asks.get("nickname", defaults.nickname_ask)),
        subject_ask=str(asks.get("subject", defaults.subject_ask)),
        new_subjects=str(data.get("new_subjects", next(iter(lists), ""))),
        greet_minutes=int(saying.get("greet_minutes", defaults.greet_minutes)),
        say_every=int(saying.get("every", defaults.say_every)),
        alone_every=int(saying.get("alone_every", defaults.alone_every)),
        say_minutes=int(saying.get("minutes", defaults.say_minutes)),
        say_chance=float(saying.get("chance", defaults.say_chance)),
        glad_from=float(saying.get("glad_from", defaults.glad_from)),
        low_below=float(saying.get("low_below", defaults.low_below)),
        angry_from=float(saying.get("angry_from", defaults.angry_from)),
        longest=int(data.get("longest", defaults.longest)),
    )
    if settings.new_subjects and settings.new_subjects not in settings.lists:
        raise ValueError(f"New subjects go into a list there is not: {settings.new_subjects}")
    if not 0.0 <= settings.ask_chance <= 1.0 or not 0.0 <= settings.say_chance <= 1.0:
        raise ValueError("How likely somebody is to ask, or to say something, goes from 0 to 1")
    if (
        settings.most_asks < 0
        or settings.lapse_hours < 1
        or min(settings.say_every, settings.alone_every) < 1
        or settings.longest < 1
    ):
        raise ValueError("Asks wait an hour or more, phrases come a minute or more apart, and a word has a letter or more")
    return settings
