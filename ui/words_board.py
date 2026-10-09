"""The board of words (P62): what residents ask the player for, the lists of the settlement,
each resident's own phrases and what they call the others, and what somebody is told to talk
about.

It reads the simulation and changes nothing: what is pressed in it is an intent for the
scene, and what is typed is kept in a `WordsEntry` until it is given.
"""

from collections.abc import Hashable
from dataclasses import dataclass, field

import pygame

from graphics.face_renderer import MARKER_SIZE, FaceRenderer
from graphics.font import FONT_CHARS, LINE_HEIGHT, BitmapFont
from graphics.item_icons import ICON_SIZE, ItemIcons
from graphics.palette import PALETTE
from graphics.ui_art import band_hue
from simulation.social.talk import ASK_WORD, ITEM, PERSON, WORD, Ask, subject_of
from simulation.world import SimulationWorld
from ui.button import HEIGHT as BUTTON_HEIGHT
from ui.button import Button
from ui.panel import draw_item, draw_panel

WORDS_WIDTH = 380
PADDING = 5
GAP = 3
ROW = BUTTON_HEIGHT + 2
PICTURE_ROW = max(MARKER_SIZE[1], ICON_SIZE[1]) + 2
WORDS_INTENT = ("words",)
# What the board is showing: the lists of the settlement and who is asking, one resident's own
# words, something asked for that is being answered, or a subject being picked for somebody.
LISTS, ONE, ASKED, PICK = "lists", "one", "asked", "pick"
# What a subject is picked from beside the lists: the things they know of, and the people.
ITEMS_TAB, PEOPLE_TAB = "@items", "@people"
# What is being written: a word for the list on show, the answer to what was asked, a subject
# made up on the spot, or one of a resident's own, which names the phrase or the other resident.
WORD_FIELD, ANSWER_FIELD, SUBJECT_FIELD = "word", "answer", "subject"
PHRASE_FIELD, NICKNAME_FIELD = "phrase:", "nickname:"
# How many of the others are listed at a time with what one calls them, how many things or
# people to pick from, and how many words.
MOST_NAMES = 6
MOST_PICTURES = 10
MOST_WORDS = 18
PICTURE_COLUMNS = 2
LISTS_TITLE = "Palabras del asentamiento"
ONE_TITLE = "Palabras de {name}"
ASKED_TITLE = "{name} pregunta"
PICK_TITLE = "¿De qué habla {name} con {other}?"
WITH_TITLE = "¿Con quién habla {name}?"
ASKING = "Te preguntan"
EACH = "Las de cada uno"
ANSWER_LABEL, LATER_LABEL = "Responder", "Ahora no"
GIVE_LABEL, ADD_LABEL, NEW_LABEL = "Dar", "Añadir", "Crear"
CHANGE_LABEL, BACK_LABEL = "Cambiar", "Volver"
TALK_LABEL = "Que hable de algo"
OTHER_LABEL = "Con otro"
EMPTY_LIST = "Todavía no hay ninguna."
ADD_TO = "Añadir a {name}:"
NEW_SUBJECT = "Tema nuevo, para {name}:"
FOR_LIST = "Para la lista {name}. Ya hay: {words}"
NO_WORDS_YET = "ninguna"
NAMES_TITLE = "Cómo llama a los demás"
BY_NAME = "por su nombre"
NO_PHRASE = "—"
ITEMS_LABEL, PEOPLE_LABEL = "Cosas", "Gente"
NOTHING_KNOWN = "No hay nada de eso de lo que hablar."
WRITE_HERE = "pulsa aquí y escribe"
CARET = "_"


def tab_intent(tab: str) -> tuple[str, str]:
    return ("words_tab", tab)


def write_intent(name: str) -> tuple[str, str]:
    return ("words_field", name)


def ask_intent(ask_id: str) -> tuple[str, str]:
    return ("words_ask", ask_id)


def dismiss_intent(ask_id: str) -> tuple[str, str]:
    return ("words_dismiss", ask_id)


def one_intent(resident_id: str) -> tuple[str, str]:
    return ("words_one", resident_id)


def pick_intent(resident_id: str) -> tuple[str, str]:
    return ("words_pick", resident_id)


def with_intent(other_id: str) -> tuple[str, str]:
    return ("words_with", other_id)


def subject_intent(subject: str) -> tuple[str, str]:
    return ("words_subject", subject)


def page_intent(step: int) -> tuple[str, int]:
    return ("words_page", step)


WORDS_GIVE_INTENT = ("words_give",)
WORDS_BACK_INTENT = ("words_back",)


@dataclass
class WordsEntry:
    """What the player is at on the board of words: what it shows, and what is being written."""

    mode: str = LISTS
    # The list on show, or what a subject is being picked from.
    tab: str = ""
    resident_id: str = ""
    other_id: str = ""
    ask_id: str = ""
    # What is being written, if anything is, and what has been written of it.
    field: str = ""
    text: str = ""
    page: int = 0

    @property
    def written(self) -> bool:
        """Whether anything is being written, and so keys are letters and not shortcuts."""
        return bool(self.field)

    def write(self, name: str, text: str = "") -> None:
        self.field, self.text = name, text

    def type(self, letter: str, longest: int) -> None:
        if letter and letter in FONT_CHARS and len(self.text) < longest:
            self.text += letter

    def erase(self) -> None:
        self.text = self.text[:-1]


@dataclass(frozen=True)
class Part:
    """One thing shown on the board that is not a button: a line, a face, the picture of a
    thing, or the box something is written in."""

    rect: pygame.Rect
    text: str = ""
    color: str = "bone"
    face_id: str | None = None
    item_id: str | None = None
    # The field it is the box of, for a box: pressing it is to write there.
    box: str | None = None


@dataclass
class WordsView:
    """The board as it stands: how tall it is, its heading, and everything on it."""

    height: int
    title: str
    parts: list[Part] = field(default_factory=list)
    buttons: list[Button] = field(default_factory=list)
    # The buttons that stand for what is on show, which are lit.
    lit: set[Hashable] = field(default_factory=set)


def asked(world: SimulationWorld, entry: WordsEntry) -> Ask | None:
    """What is being answered, while whoever asked is still waiting for it."""
    return world.talk.ask_of(world, entry.ask_id) if entry.ask_id else None


def pick_tabs(world: SimulationWorld) -> list[tuple[str, str]]:
    """What a subject can be picked from, each with what it is called."""
    lists = [(list_id, each.name) for list_id, each in world.registries.talk.lists.items()]
    return [(ITEMS_TAB, ITEMS_LABEL), (PEOPLE_TAB, PEOPLE_LABEL), *lists]


def first_list(world: SimulationWorld) -> str:
    return next(iter(world.registries.talk.lists), "")


def new_list(world: SimulationWorld, entry: WordsEntry) -> str:
    """The list a subject made up on the spot goes into: the one on show, or the one new subjects have."""
    talk = world.registries.talk
    return entry.tab if entry.tab in talk.lists else talk.new_subjects


def subjects_of(world: SimulationWorld, entry: WordsEntry) -> list[tuple[str, str, str | None, str | None]]:
    """What there is to pick on the tab on show: the subject, what it is called, and the item
    or the face it is shown with."""
    resident = world.residents.get(entry.resident_id)
    if resident is None:
        return []
    if entry.tab == ITEMS_TAB:
        return [
            (subject_of(ITEM, each.item_id), each.name.capitalize(), each.item_id, None)
            for each in world.talk.known_items(world, resident)
        ]
    if entry.tab == PEOPLE_TAB:
        return [
            (subject_of(PERSON, each.resident_id), each.name, None, each.resident_id)
            for each in world.talk.known_people(world, resident, (entry.other_id,))
        ]
    return [(subject_of(WORD, each.word_id), each.text, None, None) for each in world.talk.words(world, entry.tab)]


def pages(world: SimulationWorld, entry: WordsEntry) -> int:
    """How many pages what is on show takes."""
    if entry.mode == ONE:
        count, most = max(0, len(world.residents) - 1), MOST_NAMES
    elif entry.mode == PICK:
        count, most = len(subjects_of(world, entry)), MOST_PICTURES if entry.tab in (ITEMS_TAB, PEOPLE_TAB) else MOST_WORDS
    else:
        count, most = len(world.talk.words(world, entry.tab)), MOST_WORDS * 2
    return max(1, -(-count // most))


def words_view(font: BitmapFont, corner: tuple[int, int], world: SimulationWorld, entry: WordsEntry) -> WordsView:
    """Lay the board out from its top left corner, as it stands."""
    left, y = corner[0] + PADDING, corner[1] + PADDING + LINE_HEIGHT + 4
    right = corner[0] + WORDS_WIDTH - PADDING
    width = right - left
    talk = world.registries.talk
    view = WordsView(0, LISTS_TITLE)

    def say(text: str, color: str = "bone", indent: int = 0, room: int | None = None, lines: int = 3) -> None:
        nonlocal y
        for line in font.wrap(text, (room or width) - indent)[:lines]:
            view.parts.append(Part(pygame.Rect(left + indent, y, (room or width) - indent, LINE_HEIGHT), line, color))
            y += LINE_HEIGHT
        y += 1

    def flow(labelled: list[tuple[str, Hashable]], most_rows: int = 3) -> None:
        """Buttons one after another, on as many rows as they take."""
        nonlocal y
        x, rows = left, 1
        for label, intent in labelled:
            button = Button.at(font, x, y, label, intent)
            if button.rect.right > right and x > left:
                rows += 1
                if rows > most_rows:
                    break
                x, y = left, y + ROW
                button = Button.at(font, x, y, label, intent)
            view.buttons.append(button)
            x = button.rect.right + GAP
        if labelled:
            y += ROW + 1

    def at_right(labelled: list[tuple[str, Hashable]], top: int) -> int:
        """Buttons against the right edge of a row. Returns where the leftmost of them begins."""
        x = right
        for label, intent in reversed(labelled):
            button = Button.at(font, 0, top, label, intent)
            button.rect.right = x
            view.buttons.append(button)
            x = button.rect.left - GAP
        return x

    def box(name: str, label: str, give: str, more: list[tuple[str, Hashable]] | None = None) -> None:
        """What is being written, or where to press to write it, and the way to give it."""
        nonlocal y
        if label:
            say(label, "stone")
        writing = entry.field == name
        ends = at_right([*([(give, WORDS_GIVE_INTENT)] if writing else []), *(more or [])], y)
        shown = entry.text if writing else WRITE_HERE
        rect = pygame.Rect(left, y, ends - GAP - left, BUTTON_HEIGHT)
        view.parts.append(Part(rect, shown, "paper" if writing else "stone", box=name))
        y += ROW + 2

    def paging() -> None:
        nonlocal y
        count = pages(world, entry)
        if count > 1:
            at_right([("<", page_intent(-1)), (f"{entry.page + 1}/{count}", page_intent(0)), (">", page_intent(1))], y)
            y += ROW

    if entry.mode == ASKED and (ask := asked(world, entry)) is not None and ask.resident_id in world.residents:
        resident = world.residents[ask.resident_id]
        view.title = ASKED_TITLE.format(name=resident.name)
        view.parts.append(Part(pygame.Rect(left, y, *MARKER_SIZE), face_id=resident.resident_id))
        top = y
        said = world.talk.question(world, ask)
        for line in font.wrap(said, width - MARKER_SIZE[0] - 4)[:3]:
            view.parts.append(Part(pygame.Rect(left + MARKER_SIZE[0] + 4, y, width, LINE_HEIGHT), line, "paper"))
            y += LINE_HEIGHT
        y = max(y, top + MARKER_SIZE[1]) + 3
        if ask.kind == ASK_WORD and ask.what in talk.lists:
            words = ", ".join(word.text for word in world.talk.words(world, ask.what)) or NO_WORDS_YET
            say(FOR_LIST.format(name=talk.lists[ask.what].name, words=words), "stone", lines=2)
        box(ANSWER_FIELD, "", GIVE_LABEL)
        flow([(LATER_LABEL, dismiss_intent(ask.ask_id)), (BACK_LABEL, WORDS_BACK_INTENT)])
    elif entry.mode == PICK and entry.resident_id in world.residents:
        resident = world.residents[entry.resident_id]
        other = world.residents.get(entry.other_id)
        ask = asked(world, entry)
        if other is None:
            view.title = WITH_TITLE.format(name=resident.name)
            flow(
                [(each.name, with_intent(each.resident_id)) for each in world.residents.values() if each is not resident],
                most_rows=4,
            )
            flow([(BACK_LABEL, WORDS_BACK_INTENT)])
        else:
            view.title = PICK_TITLE.format(name=resident.name, other=other.name)
            flow([(label, tab_intent(tab)) for tab, label in pick_tabs(world)])
            view.lit.add(tab_intent(entry.tab))
            found = subjects_of(world, entry)
            pictured = entry.tab in (ITEMS_TAB, PEOPLE_TAB)
            most = MOST_PICTURES if pictured else MOST_WORDS
            shown = found[entry.page * most:(entry.page + 1) * most]
            if not found:
                say(NOTHING_KNOWN if pictured else EMPTY_LIST, "stone")
            elif pictured:
                column = width // PICTURE_COLUMNS
                for index, (subject, name, item_id, face_id) in enumerate(shown):
                    x = left + (index % PICTURE_COLUMNS) * column
                    top = y + (index // PICTURE_COLUMNS) * PICTURE_ROW
                    view.parts.append(Part(pygame.Rect(x, top, *MARKER_SIZE), item_id=item_id, face_id=face_id))
                    label = font.truncate(name, column - MARKER_SIZE[0] - 14)
                    view.buttons.append(Button.at(font, x + MARKER_SIZE[0] + 3, top + 1, label, subject_intent(subject)))
                y += -(-len(shown) // PICTURE_COLUMNS) * PICTURE_ROW + 2
            else:
                flow([(name, subject_intent(subject)) for subject, name, _item, _face in shown], most_rows=4)
            paging()
            wanted = talk.lists.get(new_list(world, entry))
            if wanted is not None:
                more = [] if ask is not None else [(OTHER_LABEL, with_intent(""))]
                box(SUBJECT_FIELD, NEW_SUBJECT.format(name=wanted.name), NEW_LABEL, more)
            flow(
                [*([(LATER_LABEL, dismiss_intent(ask.ask_id))] if ask is not None else []), (BACK_LABEL, WORDS_BACK_INTENT)]
            )
    elif entry.mode == ONE and entry.resident_id in world.residents:
        resident = world.residents[entry.resident_id]
        view.title = ONE_TITLE.format(name=resident.name)
        for phrase_id, kind in talk.phrases.items():
            name = PHRASE_FIELD + phrase_id
            if entry.field == name:
                box(name, kind.name, GIVE_LABEL)
                continue
            ends = at_right([(CHANGE_LABEL, write_intent(name))], y)
            mine = world.talk.phrase(world, resident.resident_id, phrase_id) or NO_PHRASE
            text = font.truncate(f"{kind.name}: {mine}", ends - GAP - left)
            view.parts.append(Part(pygame.Rect(left, y + 1, ends - left, LINE_HEIGHT), text, "bone"))
            y += ROW
        y += 2
        say(NAMES_TITLE, "stone")
        others = [each for each in world.residents.values() if each is not resident]
        for other in others[entry.page * MOST_NAMES:(entry.page + 1) * MOST_NAMES]:
            name = NICKNAME_FIELD + other.resident_id
            view.parts.append(Part(pygame.Rect(left, y, *MARKER_SIZE), face_id=other.resident_id))
            if entry.field == name:
                y += MARKER_SIZE[1] + 1
                box(name, "", GIVE_LABEL)
                continue
            ends = at_right([(CHANGE_LABEL, write_intent(name))], y + 1)
            called = world.words.nicknames.get(resident.resident_id, {}).get(other.resident_id) or BY_NAME
            text = font.truncate(f"{other.name}: {called}", ends - GAP - left - MARKER_SIZE[0] - 4)
            view.parts.append(Part(pygame.Rect(left + MARKER_SIZE[0] + 4, y + 2, ends - left, LINE_HEIGHT), text, "bone"))
            y += PICTURE_ROW
        paging()
        y += 2
        flow([(TALK_LABEL, pick_intent(resident.resident_id)), (BACK_LABEL, WORDS_BACK_INTENT)])
    else:
        waiting = [ask for ask in world.words.asks if ask.resident_id in world.residents]
        if waiting:
            say(ASKING, "lamp")
            for ask in waiting:
                resident = world.residents[ask.resident_id]
                ends = at_right([(ANSWER_LABEL, ask_intent(ask.ask_id)), (LATER_LABEL, dismiss_intent(ask.ask_id))], y + 1)
                view.parts.append(Part(pygame.Rect(left, y, *MARKER_SIZE), face_id=resident.resident_id))
                room = ends - GAP - left - MARKER_SIZE[0] - 4
                text = font.truncate(f"{resident.name}: {world.talk.question(world, ask)}", room)
                view.parts.append(Part(pygame.Rect(left + MARKER_SIZE[0] + 4, y + 2, room, LINE_HEIGHT), text, "paper"))
                y += PICTURE_ROW
            y += 2
        say(EACH, "stone")
        flow([(each.name, one_intent(each.resident_id)) for each in world.residents.values()])
        tab = entry.tab if entry.tab in talk.lists else first_list(world)
        flow([(each.name, tab_intent(list_id)) for list_id, each in talk.lists.items()])
        view.lit.add(tab_intent(tab))
        words = world.talk.words(world, tab)
        most = MOST_WORDS * 2
        shown = words[entry.page * most:(entry.page + 1) * most]
        say(", ".join(word.text for word in shown) if words else EMPTY_LIST, "paper" if words else "stone", lines=5)
        paging()
        if tab in talk.lists:
            box(WORD_FIELD, ADD_TO.format(name=talk.lists[tab].name), ADD_LABEL)
    view.height = y + PADDING - corner[1]
    return view


def words_board_height(font: BitmapFont, world: SimulationWorld, entry: WordsEntry) -> int:
    return words_view(font, (0, 0), world, entry).height


def words_buttons(font: BitmapFont, rect: pygame.Rect, world: SimulationWorld, entry: WordsEntry) -> list[Button]:
    """The buttons of the board that are within it."""
    view = words_view(font, rect.topleft, world, entry)
    return [button for button in view.buttons if button.rect.bottom <= rect.bottom]


def words_field_rects(font: BitmapFont, rect: pygame.Rect, world: SimulationWorld, entry: WordsEntry) -> dict[str, pygame.Rect]:
    """Where each thing that can be written is, to be pressed there."""
    view = words_view(font, rect.topleft, world, entry)
    return {part.box: part.rect for part in view.parts if part.box is not None and part.rect.bottom <= rect.bottom}


def draw_words_board(
    target: pygame.Surface,
    font: BitmapFont,
    icons: ItemIcons,
    faces: FaceRenderer,
    rect: pygame.Rect,
    world: SimulationWorld,
    entry: WordsEntry,
    lit: bool = True,
) -> None:
    """Draw the board. `lit` is whether what blinks is lit right now: the mark where the next
    letter goes."""
    view = words_view(font, rect.topleft, world, entry)
    draw_panel(target, rect, band=PADDING + LINE_HEIGHT, band_color=band_hue("talk"))
    font.draw(target, font.truncate(view.title, rect.width - PADDING * 2), (rect.x + PADDING, rect.y + PADDING), PALETTE["paper"])
    for part in view.parts:
        if part.rect.bottom > rect.bottom:
            continue
        if part.box is not None:
            writing = entry.field == part.box
            draw_panel(target, part.rect, fill="shadow", border="lamp" if writing else "iron")
            text = part.text + (CARET if writing and lit else "")
            room = part.rect.width - 8
            # What does not fit is cut from the front: the end of it is what is being written.
            while writing and text and font.width(text) > room:
                text = text[1:]
            font.draw(target, font.truncate(text, room) if not writing else text, (part.rect.x + 4, part.rect.y + 1), PALETTE[part.color])
        elif part.face_id is not None:
            target.blit(faces.marker(part.face_id), part.rect.topleft)
        elif part.item_id is not None:
            draw_item(target, icons, part.item_id, pygame.Rect(part.rect.topleft, ICON_SIZE))
        else:
            font.draw(target, part.text, part.rect.topleft, PALETTE[part.color])
    for button in view.buttons:
        if button.rect.bottom <= rect.bottom:
            button.draw(target, font, active=button.intent in view.lit)
