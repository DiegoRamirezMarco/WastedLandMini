"""Trials and punishments, on the government's panel beside its laws (P64).

What somebody found guilty is given is the player's to say, always (S28), and so is what
prisoners are given to eat and drink; and the player may accuse of what is known of somebody,
as residents do. Until this there was a command for each and no screen.

It reads the simulation and changes nothing: what is pressed in it is an intent for the scene.
"""

from dataclasses import dataclass, field

import pygame

from graphics.font import LINE_HEIGHT, BitmapFont
from graphics.palette import PALETTE
from simulation.items.item_system import FOOD_CATEGORY, WATER_CATEGORY
from simulation.justice.justice_system import PRISON
from simulation.justice.records import ACCUSATION, DEFENCE, EVIDENCE, VERDICT, WITNESSES, Trial
from simulation.knowledge.fact import Fact
from simulation.residents.resident import Resident
from simulation.world import SimulationWorld
from ui.button import HEIGHT as BUTTON_HEIGHT
from ui.button import Button

PADDING = 6
ROW_HEIGHT = BUTTON_HEIGHT + 2
# How many things somebody could be accused of are listed, and how many punishments already given.
MOST_ACCUSED = 5
MOST_REMEMBERED = 3
MINUTES_PER_DAY = 24 * 60
MEALS, DRINKS = "meals", "drinks"
FOOD, DRINK = "food", "drink"
GIVE_LABEL = "Dar"
CONFIRM_LABEL = "Confirmar"
ACCUSE_LABEL = "Acusar"
NO_TRIAL = "No hay ningún juicio en marcha."
TRIAL = "Juicio a {name} por {offence}"
STEP = "Van por {step}. Sigue en {minutes} min"
STEP_WORDS = {
    ACCUSATION: "la acusación",
    EVIDENCE: "lo que se sabe de ello",
    WITNESSES: "quién lo vio",
    DEFENCE: "lo que dice quien se defiende",
    VERDICT: "el veredicto",
}
GUILTY = "Culpable. Qué se le da lo dices tú: quedan {hours} h, y si no, {fallback}."
GRAVITY = "Lo que hizo pesa {gravity} de 10: lo que pese mucho más se toma mal."
WEIGHS = "pesa {severity}"
IN_PUBLIC = "a la vista"
HARSH = "duro"
KNOWN_TITLE = "De quién se sabe algo"
NOTHING_KNOWN = "No se sabe de nadie nada por lo que juzgarle."
ONE_AT_A_TIME = "Con un juicio en marcha no se acusa a nadie más."
KNOWN = "{name}: {offence}, día {day}"
SERVING_TITLE = "Cumpliendo castigo"
SERVING = "{name}: {punishment}, hasta el día {day} a las {hour:02d}:{minute:02d}"
RATION_TITLE = "A los presos, al día"
RATION_WORDS = {MEALS: "De comer", DRINKS: "De beber"}
WHATEVER = "lo que más haya"
GIVEN_TITLE = "Lo último que se ha dado"
GIVEN = "{name}: {punishment}, por {offence} (día {day})"


def sentence_intent(trial_id: str, punishment_id: str) -> tuple[str, str, str]:
    return ("sentence", trial_id, punishment_id)


def accuse_intent(accused_id: str, fact_id: str) -> tuple[str, str, str]:
    return ("accuse", accused_id, fact_id)


def ration_intent(what: str, step: int) -> tuple[str, str, int]:
    return ("ration", what, step)


def ration_item_intent(what: str) -> tuple[str, str]:
    return ("ration_item", what)


@dataclass
class PunishView:
    """The tab laid out: each line with its colour and how far down it is, and what can be pressed."""

    lines: list[tuple[str, str, int, int]] = field(default_factory=list)
    buttons: list[Button] = field(default_factory=list)
    bottom: int = 0


def awaiting(world: SimulationWorld) -> Trial | None:
    """The trial that waits for the player to say what somebody found guilty is given, if one does."""
    trial = world.justice.open_trial(world)
    return trial if trial is not None and trial.awaiting_sentence and trial.accused in world.residents else None


def accusable(world: SimulationWorld) -> list[tuple[Resident, Fact]]:
    """What is known of whom that nobody has been tried for, the latest first: only what
    somebody here other than whoever did it saw or was told of."""
    justice, offences = world.justice, world.registries.justice.offences
    found = []
    for fact in world.knowledge.facts.values():
        if fact.event_type not in offences or not fact.subject_ids:
            continue
        accused = world.residents.get(fact.subject_ids[0])
        if accused is None or accused.resident_id in world.leaving or justice.tried(world, fact.fact_id):
            continue
        if any(knower.resident_id != accused.resident_id for knower in justice.knowers(world, fact.fact_id)):
            found.append((accused, fact))
    found.sort(key=lambda entry: (-entry[1].timestamp, entry[1].fact_id))
    return found[:MOST_ACCUSED]


def ration_items(world: SimulationWorld, what: str) -> list[str]:
    """What a prisoner can be given of a kind, by item ID: nothing in particular, which is
    whatever there is most of, and then each thing of that kind there is."""
    category = FOOD_CATEGORY if what == FOOD else WATER_CATEGORY
    items = world.registries.items
    return ["", *(item_id for item_id in items.ids() if items.get(item_id).category == category)]


def next_ration_item(world: SimulationWorld, what: str) -> str:
    """The thing after the one prisoners are given of a kind, round and round."""
    ration = world.justice.ration(world)
    options = ration_items(world, what)
    held = ration.food if what == FOOD else ration.drink
    return options[(options.index(held) + 1) % len(options)] if held in options else ""


def _day(minute: int) -> int:
    return minute // MINUTES_PER_DAY + 1


def punish_view(
    font: BitmapFont, rect: pygame.Rect, top: int, world: SimulationWorld, armed: tuple[str, str] | None = None
) -> PunishView:
    """Everything the tab says and offers, from `top` down the panel."""
    view = PunishView()
    left, right = rect.x + PADDING, rect.right - PADDING
    width = right - left
    y = top
    settings = world.registries.justice
    names = settings.punishments

    def say(text: str, color: str = "bone", indent: int = 0, room: int | None = None) -> None:
        nonlocal y
        for line in font.wrap(text, (room if room is not None else width) - indent):
            view.lines.append((line, color, left + indent, y))
            y += LINE_HEIGHT

    def row(text: str, color: str, label: str, intent) -> None:
        """A line with a button at its end."""
        nonlocal y
        button = Button.at(font, 0, y, label, intent)
        button.rect.right = right
        view.buttons.append(button)
        view.lines.append((font.truncate(text, button.rect.left - 4 - left), color, left, y + 1))
        y += ROW_HEIGHT

    # ----- the trial in hand -----
    trial = world.justice.open_trial(world)
    accused = world.residents.get(trial.accused) if trial is not None else None
    now = world.clock.total_minutes
    if trial is None or accused is None:
        say(NO_TRIAL, "dust")
    else:
        offence = settings.offences.get(trial.offence)
        say(TRIAL.format(name=accused.name, offence=offence.name if offence is not None else trial.offence), "lamp")
        if not trial.awaiting_sentence:
            step = STEP_WORDS.get(trial.step, trial.step)
            say(STEP.format(step=step, minutes=max(1, trial.next_at - now)), "sand")
        else:
            fallback = names.get(settings.unanswered)
            hours = max(1, -(-(trial.next_at - now) // 60))
            say(GUILTY.format(hours=hours, fallback=fallback.name if fallback is not None else settings.unanswered), "glow")
            if offence is not None:
                say(GRAVITY.format(gravity=offence.gravity), "sand")
            y += 2
            for punishment_id, definition in sorted(names.items(), key=lambda entry: (entry[1].severity, entry[0])):
                notes = [WEIGHS.format(severity=definition.severity)]
                notes += [IN_PUBLIC] if definition.public else []
                notes += [HARSH] if definition.harsh else []
                there = world.justice.place_for(world, definition)[0]
                if not there:
                    text = f"{definition.name.capitalize()}: {world.justice.missing_for(world, definition)}"
                    view.lines.append((font.truncate(text, width), "iron", left, y + 1))
                    y += ROW_HEIGHT
                    continue
                label = CONFIRM_LABEL if armed == (trial.trial_id, punishment_id) else GIVE_LABEL
                text = f"{definition.name.capitalize()} ({', '.join(notes)})"
                row(text, "ember" if definition.harsh else "bone", label, sentence_intent(trial.trial_id, punishment_id))
    y += 4

    # ----- what somebody could be accused of -----
    known = accusable(world)
    say(KNOWN_TITLE, "paper")
    if not known:
        say(NOTHING_KNOWN, "dust")
    elif trial is not None:
        say(ONE_AT_A_TIME, "dust")
    for resident, fact in known:
        offence = settings.offences[fact.event_type]
        text = KNOWN.format(name=resident.name, offence=offence.name, day=_day(fact.timestamp))
        if trial is None:
            row(text, "bone", ACCUSE_LABEL, accuse_intent(resident.resident_id, fact.fact_id))
        else:
            say(text, "stone")
    y += 4

    # ----- who is serving what -----
    serving = [each for each in world.courts.sentences if each.resident_id in world.residents]
    if serving:
        say(SERVING_TITLE, "paper")
        for sentence in serving:
            definition = names.get(sentence.punishment)
            say(
                SERVING.format(
                    name=world.residents[sentence.resident_id].name,
                    punishment=definition.name if definition is not None else sentence.punishment,
                    day=_day(sentence.until),
                    hour=sentence.until % MINUTES_PER_DAY // 60,
                    minute=sentence.until % 60,
                ),
                "sand",
            )
        y += 4

    # ----- what prisoners are given -----
    if PRISON in names:
        say(RATION_TITLE, "paper")
        ration = world.justice.ration(world)
        for what, count, kind, item_id in (
            (MEALS, ration.meals, FOOD, ration.food),
            (DRINKS, ration.drinks, DRINK, ration.drink),
        ):
            label = RATION_WORDS[what]
            view.lines.append((label, "bone", left, y + 1))
            x = left + 60
            less = Button.at(font, x, y, "<", ration_intent(what, -1))
            figure = str(count)
            view.lines.append((figure, "glow", less.rect.right + 6, y + 1))
            more = Button.at(font, less.rect.right + 12 + font.width("0"), y, ">", ration_intent(what, 1))
            item = world.registries.items.find(item_id) if item_id else None
            change = Button.at(font, 0, y, ">", ration_item_intent(kind))
            change.rect.right = right
            name = item.name if item is not None else WHATEVER
            room = change.rect.left - 4 - (more.rect.right + 10)
            view.lines.append((font.truncate(f"de {name}", room), "sand", more.rect.right + 10, y + 1))
            view.buttons += [less, more, change]
            y += ROW_HEIGHT
        y += 4

    # ----- what has been given -----
    given = world.courts.history[-MOST_REMEMBERED:]
    if given:
        say(GIVEN_TITLE, "paper")
        for record in reversed(given):
            definition, offence = names.get(record.punishment), settings.offences.get(record.offence)
            say(
                GIVEN.format(
                    name=record.name,
                    punishment=definition.name if definition is not None else record.punishment,
                    offence=offence.name if offence is not None else record.offence,
                    day=_day(record.at),
                ),
                "stone",
            )
    view.bottom = y + PADDING
    return view


def punish_height(font: BitmapFont, world: SimulationWorld, width: int) -> int:
    """How tall the tab is, for a panel so wide."""
    return punish_view(font, pygame.Rect(0, 0, width, 0), 0, world).bottom


def punish_buttons(
    font: BitmapFont, rect: pygame.Rect, top: int, world: SimulationWorld, armed: tuple[str, str] | None = None
) -> list[Button]:
    return [button for button in punish_view(font, rect, top, world, armed).buttons if button.rect.bottom <= rect.bottom]


def draw_punishments(
    target: pygame.Surface,
    font: BitmapFont,
    rect: pygame.Rect,
    top: int,
    world: SimulationWorld,
    armed: tuple[str, str] | None = None,
) -> None:
    view = punish_view(font, rect, top, world, armed)
    for text, color, x, y in view.lines:
        if y + LINE_HEIGHT <= rect.bottom:
            font.draw(target, text, (x, y), PALETTE[color])
    for button in view.buttons:
        if button.rect.bottom <= rect.bottom:
            button.draw(target, font, active=button.label == CONFIRM_LABEL)
