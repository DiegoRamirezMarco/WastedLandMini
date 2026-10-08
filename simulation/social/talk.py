"""What is talked of (S58).

A talk has a subject: a thing, somebody, a word of one of the settlement's lists, or
something heard. Whoever starts it brings up one they like out of what they know, or the one
the player told them to. How whoever listens takes it moves what they feel for whoever
brought it up: down for a subject they dislike, up for one they like or have nothing
against. Whether a subject is liked goes by the tastes there already are (S19): a word is a
taste like any other, with a leaning to it for each resident, found out as the rest are.

The words are the player's: lists the settlement keeps, each resident's own phrases, and what
one calls another. Residents ask for them, and wonder aloud what to talk to somebody about.
None of it draws from the settlement's dice.
"""

import unicodedata
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from simulation.events.event import DomainEvent
from simulation.items.item import ItemDefinition
from simulation.items.registry import UNKNOWN_CATEGORY
from simulation.knowledge.knowledge_system import pass_on, striking_news
from simulation.residents.resident import Resident
from simulation.rng import SimulationRNG
from simulation.social.talk_settings import ANGRY, ANY, BEGIN, GLAD, LOW, TalkSettings, WordList
from simulation.tastes.reaction import reaction_to
from simulation.tastes.settings import DISLIKED, HATED, LIKED, LOVED, NEUTRAL, side_of
from simulation.tastes.taste import ITEM as ITEM_TASTE
from simulation.tastes.taste import TAG, key_of

if TYPE_CHECKING:
    from simulation.world import SimulationWorld

# The kinds of thing a talk can be about, as the first part of a subject: `item:stew`.
ITEM, PERSON, WORD, FACT = "item", "person", "word", "fact"
# The kinds of thing a resident asks the player for.
ASK_WORD, ASK_PHRASE, ASK_NICKNAME, ASK_SUBJECT = "word", "phrase", "nickname", "subject"
ASK_KINDS = (ASK_WORD, ASK_PHRASE, ASK_NICKNAME, ASK_SUBJECT)
TAG_PREFIX = "word_"
TAKEN_EVENT = "subject_taken"
ASKED_EVENT = "word_asked"
GIVEN_EVENT = "word_given"
TAKEN_IMPORTANCE = 8
ASKED_IMPORTANCE = 30
GIVEN_IMPORTANCE = 12
MINUTES_PER_HOUR = 60
DEFINITE = {"un": "el", "una": "la", "unos": "los", "unas": "las"}


def subject_of(kind: str, name: str) -> str:
    return f"{kind}:{name}"


def parts_of(subject: str) -> tuple[str, str]:
    kind, _, name = subject.partition(":")
    return kind, name


def contracted(text: str) -> str:
    """A sentence put together from a pattern and a word, with `de el` and `a el` run together
    as they are said. A name that begins `El` is left as it was written."""
    return text.replace(" de el ", " del ").replace(" a el ", " al ")


def slug(text: str) -> str:
    """A word as it is told apart from any other: no accents, no capitals, nothing but
    letters and figures with a line between them."""
    plain = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii").lower()
    return "_".join("".join(letter if letter.isalnum() else " " for letter in plain).split())


@dataclass
class Word:
    """A word of one of the settlement's lists, as the player gave it."""

    word_id: str
    text: str
    # Who asked for it, if anybody did, and the day it was given.
    by: str | None = None
    day: int = 0


@dataclass
class Ask:
    """Something a resident is waiting for the player to give them: a word for a list, a
    phrase of their own, what to call somebody, or what to talk to somebody about."""

    ask_id: str
    resident_id: str
    kind: str
    # The list, the phrase or the other resident it is about.
    what: str
    since: int = 0


@dataclass
class VocabularyState:
    """The words the player has given the settlement. Plain state, saved by stable IDs."""

    # The words given for each list, beside the ones it comes with.
    lists: dict[str, list[Word]] = field(default_factory=dict)
    # Each resident's own phrases, by the kind of phrase, and what each calls the others.
    phrases: dict[str, dict[str, str]] = field(default_factory=dict)
    nicknames: dict[str, dict[str, str]] = field(default_factory=dict)
    asks: list[Ask] = field(default_factory=list)
    ask_count: int = 0
    # What the player told somebody to talk about, and with whom: taken up the next time
    # the two of them talk.
    told: dict[str, tuple[str, str]] = field(default_factory=dict)


@dataclass(frozen=True)
class TalkResult:
    ok: bool
    message: str


@dataclass(frozen=True)
class Shown:
    """What is seen over somebody who is talking: the picture of a thing, a face, or words."""

    item_id: str | None = None
    face_id: str | None = None
    text: str = ""


class TalkSystem:
    def settings(self, world: "SimulationWorld") -> TalkSettings:
        return world.registries.talk

    # ----- the words there are -----

    def words(self, world: "SimulationWorld", list_id: str) -> list[Word]:
        """Every word of a list: the ones it comes with, and then the ones the player gave."""
        definition = self.settings(world).lists.get(list_id)
        if definition is None:
            return []
        seeded = [Word(f"{list_id}.{slug(text)}", text) for text in definition.words if slug(text)]
        ids = {word.word_id for word in seeded}
        return seeded + [word for word in world.words.lists.get(list_id, []) if word.word_id not in ids]

    def all_words(self, world: "SimulationWorld") -> list[tuple[WordList, Word]]:
        return [
            (definition, word)
            for list_id, definition in self.settings(world).lists.items()
            for word in self.words(world, list_id)
        ]

    def find_word(self, world: "SimulationWorld", word_id: str) -> tuple[WordList, Word] | None:
        list_id = word_id.partition(".")[0]
        definition = self.settings(world).lists.get(list_id)
        word = next((each for each in self.words(world, list_id) if each.word_id == word_id), None)
        return (definition, word) if definition is not None and word is not None else None

    def tag_of(self, word_id: str) -> str:
        """The taste a word is: one of the tags a resident has a leaning for (S19)."""
        return TAG_PREFIX + word_id

    def text_of_tag(self, world: "SimulationWorld", tag: str) -> str | None:
        """The word a taste is for, as the player wrote it. None for a taste that is no word."""
        found = self.find_word(world, tag[len(TAG_PREFIX):]) if tag.startswith(TAG_PREFIX) else None
        return found[1].text if found is not None else None

    def _clean(self, world: "SimulationWorld", text: str) -> str | None:
        """A word or a phrase as it is kept, or None for one that cannot be."""
        tidy = " ".join(text.split())
        if not tidy or len(tidy) > self.settings(world).longest or not tidy.isprintable():
            return None
        return tidy

    def add_word(self, world: "SimulationWorld", list_id: str, text: str, by: str | None = None) -> TalkResult:
        """Put a word in one of the settlement's lists. One that is there already is not put twice."""
        definition = self.settings(world).lists.get(list_id)
        tidy = self._clean(world, text)
        if definition is None:
            return TalkResult(False, "No hay tal lista")
        if tidy is None or not slug(tidy):
            return TalkResult(False, f"Hace falta una palabra, de {self.settings(world).longest} letras como mucho")
        word_id = f"{list_id}.{slug(tidy)}"
        if any(word.word_id == word_id for word in self.words(world, list_id)):
            return TalkResult(False, f'"{tidy}" ya está en {definition.name}')
        world.words.lists.setdefault(list_id, []).append(Word(word_id, tidy, by, world.clock.day))
        text = f'"{tidy}" entra en {definition.name}'
        world.emit_event(
            DomainEvent(GIVEN_EVENT, GIVEN_IMPORTANCE, text, [by] if by in world.residents else [], data={"word": word_id})
        )
        return TalkResult(True, text)

    # ----- what each has of their own -----

    def phrase(self, world: "SimulationWorld", resident_id: str, phrase_id: str) -> str:
        return world.words.phrases.get(resident_id, {}).get(phrase_id, "")

    def set_phrase(self, world: "SimulationWorld", resident_id: str, phrase_id: str, text: str) -> TalkResult:
        """Give a resident one of their own phrases, or with nothing take it back."""
        resident, kind = world.residents.get(resident_id), self.settings(world).phrases.get(phrase_id)
        if resident is None or kind is None:
            return TalkResult(False, "No hay tal frase")
        if not text.strip():
            world.words.phrases.get(resident_id, {}).pop(phrase_id, None)
            return TalkResult(True, f"{resident.name} se queda sin {kind.name.lower()}")
        tidy = self._clean(world, text)
        if tidy is None:
            return TalkResult(False, f"Hace falta una frase, de {self.settings(world).longest} letras como mucho")
        world.words.phrases.setdefault(resident_id, {})[phrase_id] = tidy
        return TalkResult(True, f'{kind.name} de {resident.name}: "{tidy}"')

    def nickname(self, world: "SimulationWorld", resident_id: str, other_id: str) -> str:
        """What one resident calls another: what the player gave them for it, or their name."""
        other = world.residents.get(other_id)
        return world.words.nicknames.get(resident_id, {}).get(other_id) or (other.name if other is not None else other_id)

    def set_nickname(self, world: "SimulationWorld", resident_id: str, other_id: str, text: str) -> TalkResult:
        resident, other = world.residents.get(resident_id), world.residents.get(other_id)
        if resident is None or other is None or resident_id == other_id:
            return TalkResult(False, "No hay a quién llamar así")
        if not text.strip():
            world.words.nicknames.get(resident_id, {}).pop(other_id, None)
            return TalkResult(True, f"{resident.name} vuelve a llamar a {other.name} por su nombre")
        tidy = self._clean(world, text)
        if tidy is None:
            return TalkResult(False, f"Hace falta un nombre, de {self.settings(world).longest} letras como mucho")
        world.words.nicknames.setdefault(resident_id, {})[other_id] = tidy
        return TalkResult(True, f'{resident.name} llama a {other.name} "{tidy}"')

    # ----- what there is to talk of -----

    def known_items(self, world: "SimulationWorld", resident: Resident) -> list[ItemDefinition]:
        """The kinds of thing a resident knows of: what they carry, and what is kept in the
        settlement that is everybody's or their own. What is somebody else's they do not."""
        found: dict[str, ItemDefinition] = {}
        for inventory in (resident.inventory, *world.containers.values()):
            for item in inventory.items:
                if inventory is not resident.inventory and item.owner_id not in (None, resident.resident_id):
                    continue
                definition = world.registries.items.find(item.definition_id)
                if definition is not None and definition.category != UNKNOWN_CATEGORY:
                    found.setdefault(definition.item_id, definition)
        return [found[item_id] for item_id in sorted(found)]

    def known_people(self, world: "SimulationWorld", resident: Resident, but: tuple[str, ...] = ()) -> list[Resident]:
        return [
            other
            for other in world.residents.values()
            if other is not resident and other.resident_id not in but
        ]

    def vocabulary(self, world: "SimulationWorld", resident: Resident, listener_id: str = "") -> list[str]:
        """Every subject a resident could be told to talk about: the things they know of, the
        people there are, and the words of every list."""
        return [
            *(subject_of(ITEM, definition.item_id) for definition in self.known_items(world, resident)),
            *(subject_of(PERSON, other.resident_id) for other in self.known_people(world, resident, (listener_id,))),
            *(subject_of(WORD, word.word_id) for _list, word in self.all_words(world)),
        ]

    def valid(self, world: "SimulationWorld", subject: str) -> bool:
        kind, name = parts_of(subject)
        if kind == ITEM:
            return world.registries.items.find(name) is not None
        if kind == PERSON:
            return name in world.residents
        if kind == WORD:
            return self.find_word(world, name) is not None
        return kind == FACT and name in world.knowledge.facts

    def _brought_up(self, world: "SimulationWorld", speaker: Resident, listener: Resident) -> list[tuple[str, float]]:
        """What a resident might bring up with somebody of their own accord, each with how
        much they are given to: the things and the words they like, and the people they feel
        strongly about."""
        settings = self.settings(world)
        # What they have seen of the other's tastes tells: less of what they have seen them
        # dislike, more of what they have seen them like. What they have not seen, they do not know.
        seen = {key: side_of(taken) for key, _state, taken in world.tastes.found_out(world, listener, speaker.resident_id)}

        def minded(key: str, weight: float) -> float:
            side = seen.get(key, 0)
            return weight * (settings.shunned if side < 0 else settings.favoured if side > 0 else 1.0)

        found: list[tuple[str, float]] = []
        for definition in self.known_items(world, speaker):
            liked = world.tastes.fancy(world, speaker, definition)
            if liked >= settings.fond_from:
                found.append((subject_of(ITEM, definition.item_id), minded(key_of(ITEM_TASTE, definition.item_id), liked)))
        for other in self.known_people(world, speaker, (listener.resident_id,)):
            feelings = world.relationships.get((speaker.resident_id, other.resident_id))
            strongest = max(feelings.affection, feelings.resentment) if feelings is not None else 0.0
            if strongest >= settings.talked_of_from:
                found.append((subject_of(PERSON, other.resident_id), strongest))
        for _list, word in self.all_words(world):
            taste = world.tastes.taste(world, speaker, TAG, self.tag_of(word.word_id))
            if taste is not None and taste.value >= settings.fond_from:
                tag = key_of(TAG, self.tag_of(word.word_id))
                found.append((subject_of(WORD, word.word_id), minded(tag, taste.value)))
        return found

    def pick(self, world: "SimulationWorld", speaker: Resident, listener: Resident) -> tuple[str, str] | None:
        """The subject a talk is about and the words for it: what the player told whoever
        starts it to bring up with this person; or else, as often as news was ever passed
        on, the most striking thing they know that the other does not; or else something
        they like; or else, with nothing they care for, any word there is. None where there
        is nothing to talk of."""
        settings = self.settings(world)
        if not settings.enabled:
            return None
        dice = SimulationRNG.keyed(
            world.rng.seed, "subject", speaker.resident_id, listener.resident_id, world.clock.total_minutes
        )
        told = world.words.told.get(speaker.resident_id)
        if told is not None and told[0] == listener.resident_id:
            del world.words.told[speaker.resident_id]
            if self.valid(world, told[1]):
                return told[1], self.sentence(world, speaker, told[1], dice)
        news = striking_news(world, speaker, listener)
        if news is not None and dice.random() < settings.news_chance + speaker.personality.sociability / 200.0:
            subject = subject_of(FACT, news.fact_id)
            return subject, self.sentence(world, speaker, subject, dice)
        choices = self._brought_up(world, speaker, listener)
        if not choices:
            choices = [(subject_of(WORD, word.word_id), 1.0) for _list, word in self.all_words(world)]
        if not choices:
            return None
        mark = dice.random() * sum(weight for _subject, weight in choices)
        subject = choices[-1][0]
        for each, weight in choices:
            mark -= weight
            if mark < 0:
                subject = each
                break
        return subject, self.sentence(world, speaker, subject, dice)

    def label(self, world: "SimulationWorld", subject: str, speaker_id: str = "") -> str:
        """A subject in a few words: the thing, whoever it is, the word."""
        kind, name = parts_of(subject)
        if kind == ITEM:
            definition = world.registries.items.resolve(name)
            return f"{DEFINITE.get(definition.article, definition.article)} {definition.name}"
        if kind == PERSON:
            return self.nickname(world, speaker_id, name)
        if kind == WORD:
            found = self.find_word(world, name)
            return found[1].text if found is not None else name
        fact = world.knowledge.facts.get(name)
        return fact.text if fact is not None else name

    def named(self, world: "SimulationWorld", subject: str, speaker_id: str = "") -> str:
        """A subject as it is named in the middle of a sentence: a word is quoted."""
        label = self.label(world, subject, speaker_id)
        return f'"{label}"' if parts_of(subject)[0] == WORD else label

    def sentence(self, world: "SimulationWorld", speaker: Resident, subject: str, dice: SimulationRNG) -> str:
        """What is being talked of, put into words by one of the patterns there are for it."""
        settings = self.settings(world)
        kind, name = parts_of(subject)
        label = self.label(world, subject, speaker.resident_id)
        if kind == ITEM:
            definition = world.registries.items.resolve(name)
            patterns = settings.item_patterns.get(definition.category) or settings.item_patterns.get("default", ("{item}",))
            pattern = patterns[dice.randint(0, len(patterns) - 1)]
            return pattern.replace("{item}", label).replace("{an_item}", f"{definition.article} {definition.name}")
        if kind == PERSON:
            pattern = settings.person_patterns[dice.randint(0, len(settings.person_patterns) - 1)]
            return pattern.replace("{pj}", label)
        if kind == WORD:
            found = self.find_word(world, name)
            patterns = found[0].patterns if found is not None else ("{word}",)
            return contracted(patterns[dice.randint(0, len(patterns) - 1)].replace("{word}", label))
        pattern = settings.fact_patterns[dice.randint(0, len(settings.fact_patterns) - 1)]
        return pattern.replace("{fact}", label)

    # ----- how it is taken -----

    def _stance(self, world: "SimulationWorld", resident_id: str, other_id: str) -> float:
        """Where somebody stands on somebody else: for them, or against."""
        feelings = world.relationships.get((resident_id, other_id))
        return feelings.affection - feelings.resentment if feelings is not None else 0.0

    def reaction(
        self, world: "SimulationWorld", listener: Resident, subject: str, speaker: Resident | None = None
    ) -> str:
        """How somebody takes hearing of a subject: one of the five reactions of a taste. A
        thing and a word go by the taste they have for it. Somebody goes by whether the two
        of them stand the same way on them: to hear ill of whoever they cannot stand
        either is welcome, and to hear it of a friend is not. Where whoever speaks stands
        nowhere, it goes by where whoever listens does. Something heard is taken as it comes."""
        settings = world.registries.tastes
        kind, name = parts_of(subject)
        if kind == ITEM:
            definition = world.registries.items.find(name)
            if definition is None or definition.category == UNKNOWN_CATEGORY:
                return NEUTRAL
            return reaction_to(world.tastes.fancy(world, listener, definition), settings)
        if kind == WORD:
            return world.tastes.takes(world, listener, self.tag_of(name))
        if kind == PERSON and name != listener.resident_id:
            sore = self.settings(world).sore_from
            mine = self._stance(world, listener.resident_id, name)
            theirs = self._stance(world, speaker.resident_id, name) if speaker is not None else 0.0
            agreed = mine if theirs >= 0 else -mine
            if agreed <= -sore:
                return HATED if agreed <= -sore * 2 else DISLIKED
            if agreed >= sore:
                return LOVED if agreed >= sore * 2 else LIKED
        return NEUTRAL

    def taken(self, world: "SimulationWorld", listener: Resident, speaker: Resident, subject: str) -> str:
        """Somebody has heard a subject out: what they feel for whoever brought it up moves by
        how they took it, and something of their taste for it shows. Returns the reaction."""
        settings = self.settings(world)
        reaction = self.reaction(world, listener, subject, speaker)
        feelings = world.relationship(listener.resident_id, speaker.resident_id)
        for feeling, delta in settings.taken.get(reaction, {}).items():
            feelings.adjust(feeling, delta)
        onlookers = [speaker.resident_id]
        line = settings.lines.get(reaction)
        if line:
            text = (
                line.replace("{listener}", listener.name)
                .replace("{speaker}", speaker.name)
                .replace("{subject}", self.named(world, subject, speaker.resident_id))
            )
            event = DomainEvent(
                TAKEN_EVENT,
                TAKEN_IMPORTANCE,
                text,
                [listener.resident_id, speaker.resident_id],
                data={
                    "resident_id": listener.resident_id, "speaker_id": speaker.resident_id, "subject": subject,
                    "reaction": reaction,
                },
            )
            world.emit_event(event, at=listener.tile)
            onlookers.extend(event.witnesses)
        self._show(world, listener, subject, reaction, onlookers)
        return reaction

    def _show(self, world: "SimulationWorld", resident: Resident, subject: str, reaction: str, onlookers: list[str]) -> None:
        """Something of what a resident makes of a thing or a word shows, for its having been
        talked of: to the player, and to whoever was there."""
        kind, name = parts_of(subject)
        key = {ITEM: key_of(ITEM_TASTE, name), WORD: key_of(TAG, self.tag_of(name))}.get(kind)
        if key is not None:
            world.tastes.show(world, resident, key, self.settings(world).shows, onlookers, reaction)

    def brought_up(self, world: "SimulationWorld", speaker: Resident, listener: Resident, subject: str) -> None:
        """Somebody has brought a subject up: what they make of it themselves shows as well."""
        self._show(world, speaker, subject, self.reaction(world, speaker, subject), [listener.resident_id])

    def tell(self, world: "SimulationWorld", teller: Resident, listener: Resident, subject: str) -> bool:
        """What a talk was about was something heard: whoever listened has heard it too."""
        kind, name = parts_of(subject)
        belief = world.knowledge.belief(teller.resident_id, name) if kind == FACT else None
        if belief is None or world.knowledge.knows(listener.resident_id, name):
            return False
        pass_on(world, teller, listener, belief)
        return True

    # ----- what is seen and read of it -----

    def about(self, world: "SimulationWorld", resident: Resident) -> tuple[str, str] | None:
        """The subject somebody is talking of right now and the words for it, if they are."""
        activity = resident.activity
        if activity is None or not activity.using or activity.partner_id is None or not activity.about:
            return None
        return activity.about, activity.about_text

    def saying(self, world: "SimulationWorld", resident: Resident) -> str:
        """The phrase of their own a resident comes out with this minute, if any: how they
        greet as a talk begins, and now and then what they say angry, glad or low when that
        is how they are, or else what they keep saying. Oftener in company than alone, and
        nothing where the player gave none."""
        settings = self.settings(world)
        mine = world.words.phrases.get(resident.resident_id)
        if not mine or resident.away or not world.is_aware(resident):
            return ""

        def of(when: str) -> str:
            return next(
                (mine[kind.phrase_id] for kind in settings.phrases.values() if kind.when == when and mine.get(kind.phrase_id)),
                "",
            )

        now, activity = world.clock.total_minutes, resident.activity
        talking = activity is not None and activity.using and activity.partner_id is not None
        if talking and now - activity.began_at < settings.greet_minutes and of(BEGIN):
            return of(BEGIN)
        every = settings.say_every if talking else settings.alone_every
        if now % every >= settings.say_minutes:
            return ""
        if SimulationRNG.keyed(world.rng.seed, "say", resident.resident_id, now // every).random() >= settings.say_chance:
            return ""
        if resident.needs.stress >= settings.angry_from and of(ANGRY):
            return of(ANGRY)
        if resident.mood >= settings.glad_from and of(GLAD):
            return of(GLAD)
        if resident.mood < settings.low_below and of(LOW):
            return of(LOW)
        return of(ANY)

    def shown(self, world: "SimulationWorld", resident: Resident) -> Shown | None:
        """What is seen over somebody who is talking: a phrase of their own when one comes
        out, or else the thing, the face or the words of what the talk is about."""
        said = self.saying(world, resident)
        if said:
            return Shown(text=said)
        about = self.about(world, resident)
        if about is None:
            return None
        kind, name = parts_of(about[0])
        if kind == ITEM:
            return Shown(item_id=name)
        if kind == PERSON:
            return Shown(face_id=name)
        if kind == FACT:
            fact = world.knowledge.facts.get(name)
            who = next((each for each in (fact.subject_ids if fact is not None else []) if each in world.residents), None)
            return Shown(face_id=who) if who is not None else Shown(text=about[1])
        return Shown(text=about[1])

    # ----- what residents ask for -----

    def ask_of(self, world: "SimulationWorld", ask_id: str) -> Ask | None:
        return next((ask for ask in world.words.asks if ask.ask_id == ask_id), None)

    def question(self, world: "SimulationWorld", ask: Ask) -> str:
        """What a resident is asking, in their words."""
        settings = self.settings(world)
        if ask.kind == ASK_WORD:
            wanted = settings.lists.get(ask.what)
            return wanted.ask if wanted is not None and wanted.ask else "¿Me dices una palabra?"
        if ask.kind == ASK_PHRASE:
            wanted = settings.phrases.get(ask.what)
            return wanted.ask if wanted is not None and wanted.ask else "¿Qué digo?"
        other = world.residents.get(ask.what)
        pattern = settings.nickname_ask if ask.kind == ASK_NICKNAME else settings.subject_ask
        return pattern.replace("{other}", other.name if other is not None else "esa persona")

    def _raise(self, world: "SimulationWorld", resident: Resident, kind: str, what: str) -> Ask:
        state = world.words
        state.ask_count += 1
        ask = Ask(f"ask_{state.ask_count}", resident.resident_id, kind, what, world.clock.total_minutes)
        state.asks.append(ask)
        world.emit_event(
            DomainEvent(
                ASKED_EVENT,
                ASKED_IMPORTANCE,
                f'{resident.name} quiere preguntarte algo: "{self.question(world, ask)}"',
                [resident.resident_id],
                data={"ask_id": ask.ask_id, "resident_id": resident.resident_id, "kind": kind, "what": what},
            ),
            at=resident.tile,
        )
        return ask

    def _wants(self, world: "SimulationWorld", resident: Resident, dice: SimulationRNG) -> tuple[str, str] | None:
        """What a resident would ask for today, if they asked: a phrase they still lack, a
        word for a list, what to call somebody they feel strongly about, or what to talk
        about with somebody they like."""
        settings, state = self.settings(world), world.words
        mine = state.phrases.get(resident.resident_id, {})
        choices: list[tuple[str, str, float]] = []
        lacking = [phrase_id for phrase_id in settings.phrases if phrase_id not in mine]
        if lacking:
            choices.append((ASK_PHRASE, lacking[0], 3.0))
        if settings.lists:
            lists = sorted(settings.lists)
            choices.append((ASK_WORD, lists[dice.randint(0, len(lists) - 1)], 3.0))
        named = state.nicknames.get(resident.resident_id, {})
        for other in world.residents.values():
            feelings = world.relationships.get((resident.resident_id, other.resident_id))
            if other is resident or feelings is None or other.away:
                continue
            if max(feelings.affection, feelings.resentment) >= settings.nickname_from and other.resident_id not in named:
                choices.append((ASK_NICKNAME, other.resident_id, 1.0))
            if feelings.affection >= settings.subject_from:
                choices.append((ASK_SUBJECT, other.resident_id, 1.0))
        if not choices:
            return None
        mark = dice.random() * sum(weight for _kind, _what, weight in choices)
        for kind, what, weight in choices:
            mark -= weight
            if mark < 0:
                return kind, what
        return choices[-1][0], choices[-1][1]

    def tick(self, world: "SimulationWorld") -> None:
        """On the hour: what has waited too long is let go, and at their hour of the day
        residents think of asking for something."""
        settings = self.settings(world)
        if world.clock.minute != 0 or not settings.enabled:
            return
        state, now = world.words, world.clock.total_minutes
        lapse = settings.lapse_hours * MINUTES_PER_HOUR
        state.asks = [ask for ask in state.asks if now - ask.since < lapse and ask.resident_id in world.residents]
        if world.clock.hour != settings.ask_hour or world.tutorial.active:
            return
        for resident in list(world.residents.values()):
            if len(state.asks) >= settings.most_asks:
                break
            if resident.away or any(ask.resident_id == resident.resident_id for ask in state.asks):
                continue
            dice = SimulationRNG.keyed(world.rng.seed, "ask", resident.resident_id, world.clock.day)
            if dice.random() >= settings.ask_chance:
                continue
            wanted = self._wants(world, resident, dice)
            if wanted is not None:
                self._raise(world, resident, *wanted)

    def answer(
        self, world: "SimulationWorld", ask_id: str, text: str = "", subject: str | None = None, list_id: str | None = None
    ) -> TalkResult:
        """Give a resident what they asked for: the word, the phrase, the name, or what to
        talk about, which is a subject there is or a word made up on the spot."""
        ask = self.ask_of(world, ask_id)
        resident = world.residents.get(ask.resident_id) if ask is not None else None
        if ask is None or resident is None:
            return TalkResult(False, "Ya nadie pregunta eso")
        if ask.kind == ASK_WORD:
            result = self.add_word(world, ask.what, text, resident.resident_id)
        elif ask.kind == ASK_PHRASE:
            result = self.set_phrase(world, resident.resident_id, ask.what, text) if text.strip() else TalkResult(False, "Hace falta una frase")
        elif ask.kind == ASK_NICKNAME:
            result = self.set_nickname(world, resident.resident_id, ask.what, text) if text.strip() else TalkResult(False, "Hace falta un nombre")
        else:
            result = self.talk_about(world, resident.resident_id, ask.what, subject, text, list_id)
        if result.ok:
            world.words.asks = [each for each in world.words.asks if each.ask_id != ask_id]
        return result

    def dismiss(self, world: "SimulationWorld", ask_id: str) -> TalkResult:
        if self.ask_of(world, ask_id) is None:
            return TalkResult(False, "Ya nadie pregunta eso")
        world.words.asks = [each for each in world.words.asks if each.ask_id != ask_id]
        return TalkResult(True, "Otra vez será")

    def talk_about(
        self,
        world: "SimulationWorld",
        resident_id: str,
        other_id: str,
        subject: str | None = None,
        text: str = "",
        list_id: str | None = None,
    ) -> TalkResult:
        """Tell a resident what to talk about with somebody: a subject there is, or a word
        made up on the spot, which joins a list. They go and talk, when they can."""
        resident, other = world.residents.get(resident_id), world.residents.get(other_id)
        if resident is None or other is None or resident is other:
            return TalkResult(False, "No hay con quién hablar")
        if subject is None:
            wanted = list_id or self.settings(world).new_subjects
            tidy = self._clean(world, text)
            word_id = f"{wanted}.{slug(tidy)}" if tidy is not None else ""
            if tidy is None or (self.find_word(world, word_id) is None and not self.add_word(world, wanted, tidy, resident_id).ok):
                return TalkResult(False, "Hace falta un tema: uno de los que hay, o una palabra nueva")
            subject = subject_of(WORD, word_id)
        if not self.valid(world, subject):
            return TalkResult(False, "De eso no se puede hablar")
        world.words.told[resident_id] = (other_id, subject)
        said = self.named(world, subject, resident_id)
        # They go and have it out, as when they are told to talk to somebody (S50). Where
        # that cannot be told them now, it keeps for the next time the two of them talk.
        order = self.settings(world).order
        if order and world.affect.order(world, resident_id, order, other_id).ok:
            return TalkResult(True, f"{resident.name} va a hablar con {other.name} sobre {said}")
        return TalkResult(True, f"{resident.name} hablará sobre {said} la próxima vez que charle con {other.name}")
