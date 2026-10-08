"""Panel on what the settlement holds as a whole and how it trades: by barter or with a currency,
what is in the fund, what each resident said the last time they were asked, and the ways to put
a currency to them, to name it and to go back to barter."""

from collections.abc import Callable
from dataclasses import dataclass

import pygame

from graphics.face_renderer import MARKER_SIZE, FaceRenderer
from graphics.font import FONT_CHARS, LINE_HEIGHT, BitmapFont
from graphics.palette import PALETTE, Color
from simulation.economy.terms import NAME_LENGTH
from simulation.economy.terms_system import BARTER_PROPOSAL, CURRENCY_PROPOSAL, OBSTACLES
from simulation.world import SimulationWorld
from ui.button import HEIGHT as BUTTON_HEIGHT
from ui.button import Button
from ui.panel import draw_panel

PANEL_WIDTH = 330
PADDING = 6
BAND = LINE_HEIGHT + PADDING + 1
# How large the coin is shown beside how the settlement trades.
COIN = 22
ANSWER_ROW = MARKER_SIZE[1] + 2
ANSWER_COLUMNS = 2
FIELD_HEIGHT = LINE_HEIGHT + 4
FIELD_LABEL = 44
TITLE = "Fondo"
BARTER = "Se comercia por trueque: una cosa por otra"
WITH_COIN = "Se comercia con {name}"
IN_FUND = "En el fondo: {amount}"
NO_COIN = "Sin moneda, el fondo es lo que hay en los almacenes"
KEPT_ASIDE = "Guardado de cuando hubo moneda: {amount}"
GOODS = "De todos, en cosas: {units} de {kinds} clases"
NO_GOODS = "De todos, en cosas: nada"
ASKED = "Se les preguntó por {thing}: {yes} a favor, {no} en contra"
NEVER_ASKED = "Aún no se les ha preguntado con qué comerciar."
FOR, AGAINST = "a favor", "en contra"
GOVERNED = "Hay gobierno: se decide como cualquier propuesta, y aquí solo se presenta."
ANSWERS_TO_ALL = "Lo deciden ellos: más a favor que en contra, y queda hecho."
PROPOSE_LABEL = "Proponer moneda"
BARTER_LABEL = "Volver al trueque"
RENAME_LABEL = "Cambiar nombre"
DRAW_LABEL = "Dibujar moneda"
CANCEL_LABEL = "Dejarlo"
NAME_IT_LABEL = "Llamarla así"
NAME_FIELD, SINGULAR_FIELD = "name", "singular"
FIELD_LABELS = {NAME_FIELD: "Muchas", SINGULAR_FIELD: "Una"}
FIELD_HINTS = {NAME_FIELD: "vales", SINGULAR_FIELD: "vale"}
ENTRY_HINT = "Escribe cómo se llama. TAB cambia de casilla. Luego di con qué consejo se lo propones."
RENAME_HINT = "Escribe cómo se llama desde ahora. TAB cambia de casilla, Enter lo deja puesto."
BARTER_HINT = "Di con qué consejo se lo propones."
# What the player is in the middle of on the board.
CURRENCY, BARTER_BACK, RENAME = "currency", "barter", "rename"


def fund_intent(*what: str) -> tuple[str, ...]:
    return ("fund", *what)


PROPOSE_INTENT = fund_intent("propose")
BARTER_INTENT = fund_intent("barter")
RENAME_INTENT = fund_intent("rename")
DRAW_INTENT = fund_intent("draw")
CANCEL_INTENT = fund_intent("cancel")
NAME_IT_INTENT = fund_intent("name_it")


def advise_intent(option_id: str) -> tuple[str, ...]:
    return fund_intent("advise", option_id)


def field_intent(field: str) -> tuple[str, ...]:
    return fund_intent("field", field)


@dataclass
class FundEntry:
    """What the player is setting about on the board: a currency to put to the residents, going
    back to barter, or another name for the currency there is."""

    mode: str
    name: str = ""
    singular: str = ""
    # Which of the two names is being written.
    field: str = NAME_FIELD

    @property
    def written(self) -> bool:
        """Whether anything is being written, and so keys are letters and not shortcuts."""
        return self.mode in (CURRENCY, RENAME)

    def type(self, letter: str) -> None:
        text = getattr(self, self.field)
        if letter and letter in FONT_CHARS and len(text) < NAME_LENGTH:
            setattr(self, self.field, text + letter)

    def erase(self) -> None:
        setattr(self, self.field, getattr(self, self.field)[:-1])

    def next_field(self) -> None:
        self.field = SINGULAR_FIELD if self.field == NAME_FIELD else NAME_FIELD


def status_lines(world: SimulationWorld) -> list[tuple[str, str]]:
    """How the settlement trades and what it holds as a whole, as lines and the colour of each."""
    trading = world.trading
    coin = world.fund.currency(world)
    if coin is not None:
        lines = [(WITH_COIN.format(name=coin.name), "paper"), (IN_FUND.format(amount=coin.amount(trading.fund)), "lamp")]
    else:
        lines = [(BARTER, "paper"), (NO_COIN, "dust")]
        if trading.currency is not None and trading.fund >= 1:
            lines.append((KEPT_ASIDE.format(amount=trading.currency.amount(trading.fund)), "stone"))
    goods = world.fund.goods(world)
    held = GOODS.format(units=sum(goods.values()), kinds=len(goods)) if goods else NO_GOODS
    return [*lines, (held, "bone")]


def answer_rows(world: SimulationWorld) -> list[tuple[str, str, bool]]:
    """What each resident said the last time they were all asked how to trade: their ID, their
    name and whether they were for it. Whoever has gone since is not listed."""
    return [
        (resident_id, world.residents[resident_id].name, said)
        for resident_id, said in world.trading.answers.items()
        if resident_id in world.residents
    ]


def asked_line(world: SimulationWorld) -> str:
    rows = answer_rows(world)
    if not rows or not world.trading.asked_about:
        return NEVER_ASKED
    yes = sum(said for _, _, said in rows)
    return ASKED.format(thing=world.trading.asked_about, yes=yes, no=len(rows) - yes)


def advices(world: SimulationWorld, mode: str) -> list[tuple[str, str]]:
    """The advice a proposal can be put with, as the ID and the words of each, from the data of
    the decision each resident makes about it."""
    definition = world.registries.decisions.get(BARTER_PROPOSAL if mode == BARTER_BACK else CURRENCY_PROPOSAL)
    return [(option.option_id, option.text) for option in definition.options] if definition is not None else []


def hint(world: SimulationWorld, entry: FundEntry | None) -> tuple[str, str]:
    """What there is to say under the board, and the colour to say it in."""
    if entry is not None:
        return {CURRENCY: ENTRY_HINT, RENAME: RENAME_HINT}.get(entry.mode, BARTER_HINT), "glow"
    if world.government.kind is not None:
        return GOVERNED, "dust"
    obstacle = world.terms.obstacle(world)
    return (OBSTACLES[obstacle], "ember") if obstacle is not None else (ANSWERS_TO_ALL, "dust")


@dataclass(frozen=True)
class Parts:
    """Where each part of the board starts, from the top of it down."""

    status: int
    asked: int
    answers: int
    entry: int
    buttons: int
    hint: int
    bottom: int


def _parts(font: BitmapFont, world: SimulationWorld, entry: FundEntry | None) -> Parts:
    width = PANEL_WIDTH - PADDING * 2
    status = BAND + 3
    lines = sum(len(font.wrap(text, width - COIN - 6)) for text, _ in status_lines(world))
    asked = status + max(COIN, lines * LINE_HEIGHT) + 4
    answers = asked + len(font.wrap(asked_line(world), width)) * LINE_HEIGHT + 2
    rows = -(-len(answer_rows(world)) // ANSWER_COLUMNS)
    at = answers + rows * ANSWER_ROW + (4 if rows else 0)
    fields = 2 * (FIELD_HEIGHT + 2) + 2 if entry is not None and entry.written else 0
    buttons = at + fields
    said, _ = hint(world, entry)
    below = buttons + BUTTON_HEIGHT + 4
    return Parts(status, asked, answers, at, buttons, below, below + len(font.wrap(said, width)) * LINE_HEIGHT + PADDING)


def fund_board_height(font: BitmapFont, world: SimulationWorld, entry: FundEntry | None = None) -> int:
    return _parts(font, world, entry).bottom


def field_rects(font: BitmapFont, rect: pygame.Rect, world: SimulationWorld, entry: FundEntry | None) -> dict[str, pygame.Rect]:
    """Where each of the two names of a currency is written, while one is being."""
    if entry is None or not entry.written:
        return {}
    top = rect.y + _parts(font, world, entry).entry
    left = rect.x + PADDING + FIELD_LABEL
    width = NAME_LENGTH * 6 + 12
    return {
        field: pygame.Rect(left, top + index * (FIELD_HEIGHT + 2), width, FIELD_HEIGHT)
        for index, field in enumerate((NAME_FIELD, SINGULAR_FIELD))
    }


def fund_buttons(
    font: BitmapFont, rect: pygame.Rect, world: SimulationWorld, entry: FundEntry | None = None, drawable: bool = False
) -> list[Button]:
    """What can be done from the board as things stand: put a currency to them or go back to
    barter, give the currency a name or a drawing, and, in the middle of any of it, the advice
    to put it with or the way out of it."""
    y = rect.y + _parts(font, world, entry).buttons
    labels: list[tuple[str, tuple[str, ...]]]
    if entry is not None and entry.mode == RENAME:
        labels = [(NAME_IT_LABEL, NAME_IT_INTENT), (CANCEL_LABEL, CANCEL_INTENT)]
    elif entry is not None:
        labels = [(text, advise_intent(option_id)) for option_id, text in advices(world, entry.mode)]
        labels.append((CANCEL_LABEL, CANCEL_INTENT))
    elif world.fund.currency(world) is None:
        labels = [(PROPOSE_LABEL, PROPOSE_INTENT)]
    else:
        labels = [(BARTER_LABEL, BARTER_INTENT), (RENAME_LABEL, RENAME_INTENT)]
        if drawable:
            labels.append((DRAW_LABEL, DRAW_INTENT))
    buttons: list[Button] = []
    x = rect.x + PADDING
    for label, intent in labels:
        button = Button.at(font, x, y, label, intent)
        buttons.append(button)
        x = button.rect.right + 4
    return [button for button in buttons if button.rect.bottom <= rect.bottom - 2]


def draw_fund_board(
    target: pygame.Surface,
    font: BitmapFont,
    faces: FaceRenderer,
    rect: pygame.Rect,
    world: SimulationWorld,
    entry: FundEntry | None = None,
    drawable: bool = False,
    band_color: Color | None = None,
    show_coin: Callable[[pygame.Rect], None] | None = None,
    caret: bool = True,
) -> None:
    """Draw the board. `show_coin` puts the coin, as it is drawn, in the square it is given."""
    draw_panel(target, rect, band=BAND, band_color=band_color)
    x, width = rect.x + PADDING, rect.width - PADDING * 2
    font.draw(target, TITLE, (x, rect.y + PADDING - 1), PALETTE["paper"])
    parts = _parts(font, world, entry)
    floor = rect.bottom - 2

    y = rect.y + parts.status
    left = x
    if world.trading.currency is not None and show_coin is not None:
        show_coin(pygame.Rect(x, y, COIN, COIN))
        left = x + COIN + 6
    for text, color in status_lines(world):
        for line in font.wrap(text, rect.right - PADDING - left):
            font.draw(target, line, (left, y), PALETTE[color])
            y += LINE_HEIGHT

    y = rect.y + parts.asked
    for line in font.wrap(asked_line(world), width):
        font.draw(target, line, (x, y), PALETTE["sand"])
        y += LINE_HEIGHT
    column = width // ANSWER_COLUMNS
    for index, (resident_id, name, said) in enumerate(answer_rows(world)):
        spot = (x + (index % ANSWER_COLUMNS) * column, rect.y + parts.answers + (index // ANSWER_COLUMNS) * ANSWER_ROW)
        if spot[1] + ANSWER_ROW > floor:
            break
        target.blit(faces.marker(resident_id), spot)
        at = spot[0] + MARKER_SIZE[0] + 4
        font.draw(target, name, (at, spot[1] + 2), PALETTE["bone"])
        word = FOR if said else AGAINST
        font.draw(target, word, (at + font.width(name) + 5, spot[1] + 2), PALETTE["lichen" if said else "ember"])

    for field, box in field_rects(font, rect, world, entry).items():
        active = entry is not None and entry.field == field
        font.draw(target, FIELD_LABELS[field], (x, box.y + 2), PALETTE["sand"])
        draw_panel(target, box, fill="shadow", border="lamp" if active else "iron")
        text = getattr(entry, field)
        if text or active:
            shown = text + ("_" if active and caret and len(text) < NAME_LENGTH else "")
            font.draw(target, shown, (box.x + 4, box.y + 2), PALETTE["paper"])
        else:
            font.draw(target, FIELD_HINTS[field], (box.x + 4, box.y + 2), PALETTE["iron"])

    for button in fund_buttons(font, rect, world, entry, drawable):
        button.draw(target, font)
    said, color = hint(world, entry)
    y = rect.y + parts.hint
    for line in font.wrap(said, width):
        if y + LINE_HEIGHT > floor + 2:
            break
        font.draw(target, line, (x, y), PALETTE[color])
        y += LINE_HEIGHT
