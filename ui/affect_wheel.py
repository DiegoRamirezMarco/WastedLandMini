"""The wheel of what the player can tell a resident: round buttons in a ring about them.

It opens on the kinds of thing there are to say. Each opens on what there is of it, and what
is done with somebody opens on who: their faces, the nearest first. What can be done with one
person is what is felt for them. Beside it, a strip of what they have already been told and
have not done, each of which a click takes back.

Nothing here decides anything: what is on offer is asked of the world, and a press says what
was pressed.
"""

import math
from collections.abc import Hashable
from dataclasses import dataclass

import pygame

from graphics import ui_art
from graphics.face_renderer import FaceRenderer
from graphics.font import LINE_HEIGHT, BitmapFont
from graphics.palette import PALETTE
from graphics.ui_skin import WindowSkin
from simulation.ai.affect import (
    FRIENDLY,
    HOSTILE,
    INCITE,
    LEISURE,
    NEED,
    PLAY,
    ROMANCE,
    SALVAGE,
    TAKE_CHARGE,
    TAKE_JOB,
    TASK,
    TREAT,
    WITH,
    WORDS,
    AffectOption,
    split_use,
)
from simulation.residents.resident import Resident
from simulation.tastes.settings import DISLIKED, HATED, LIKED, LOVED
from simulation.world import SimulationWorld
from ui.labels import expression_of

# The side of a round button, on the canvas, and of the smaller ones of what waits to be done.
BUTTON = 24
QUEUE_BUTTON = 18
GAP = 14
SMALLEST_RADIUS = 42
MARGIN = 4
# Room kept at each side of the ring for what its buttons are called.
LABEL_ROOM = 84
# How many of what is done with one person, or of anything else, fit in the ring at once.
MOST_ENTRIES = 14

# The kinds of thing there are to say, as the wheel opens on them.
SOCIAL, PASTIME, NEEDS, TASKS, WORDS_BRANCH = "social", "leisure", "need", "task", "words"
BRANCHES = (SOCIAL, PASTIME, NEEDS, TASKS, WORDS_BRANCH)
BRANCH_GROUPS = {PASTIME: (LEISURE,), NEEDS: (NEED,), TASKS: (TASK,), WORDS_BRANCH: (WORDS,)}
BRANCH_NAMES = {SOCIAL: "Social", PASTIME: "Ocio", NEEDS: "Necesidades", TASKS: "Trabajo", WORDS_BRANCH: "Unas palabras"}
BRANCH_ICONS = {SOCIAL: "people", PASTIME: "leisure", NEEDS: "food", TASKS: "work", WORDS_BRANCH: "voice"}
BRANCH_HINTS = {
    SOCIAL: "Que vaya con alguien: según lo que sienta por cada cual",
    PASTIME: "Que pase el rato, a solas o con alguien",
    NEEDS: "Que atienda una necesidad",
    TASKS: "Que se ponga a algo",
    WORDS_BRANCH: "Decirle unas palabras",
}
TONE_ICONS = {FRIENDLY: "talk", ROMANCE: "heart", HOSTILE: "clash", PLAY: "leisure"}
GROUP_ICONS = {NEED: "food", WITH: "talk", INCITE: "clash", LEISURE: "leisure", TASK: "work", WORDS: "voice"}
# What a thing that a task is about goes by, where it is not somebody.
TARGET_ICONS = {TAKE_CHARGE: "buildings", SALVAGE: "scrap", TAKE_JOB: "work", TREAT: "food"}
# The mark on something they are known to like, or not to.
MARKS = {LOVED: "heart", LIKED: "heart", DISLIKED: "close", HATED: "close"}
MARK_WORDS = {LOVED: "le encanta", LIKED: "le gusta", DISLIKED: "no le gusta", HATED: "lo aborrece"}

WILL_FREE = "Hace su vida"
WILL_HELD = "Solo órdenes"
WILL_FREE_HINT = "Hace su vida por su cuenta. Pulsa para que haga solo lo que se le diga"
WILL_HELD_HINT = "No hace nada por su cuenta: espera órdenes. Pulsa para devolverle su vida"
BACK_LABEL = "Volver"
# The ring of a thing (P63).
LOOK_LABEL = "Ver"
LOOK_HINT = "Lo que hay que decir de {thing}"
THING_HINT = "Lo que puede hacer con esto"
NOTHING_TO_DO = "Ahora no puede hacer nada con esto"
# What only somebody can be told, for a trait of theirs (S63): the mark at its corner, and what is said of it.
OWN_MARK = "trait"
OWN_HINT = "{said} (solo por ser {trait})"
CLOSE_LABEL = "Nada"
ROOT_HINT = "Lo que le digas, lo hará"
WHO_HINT = "¿Con quién? Elige una cara, o a alguien en el mapa"
NOTHING_TO_SAY = "No está para que se le diga nada"
QUEUE_HINT = "{said} (clic: quitárselo)"
QUEUE_NOW = "Ahora: "

# Opens the wheel about whoever is selected, or shuts it and lets them go.
AFFECT_INTENT = ("affect_open",)
BACK_INTENT = ("affect_back",)
CLOSE_INTENT = ("affect_close",)
WILL_INTENT = ("affect_will",)


def branch_intent(branch: str) -> tuple[str, str]:
    return ("affect_branch", branch)


def person_intent(resident_id: str) -> tuple[str, str]:
    return ("affect_person", resident_id)


def order_intent(kind: str) -> tuple[str, str]:
    return ("affect", kind)


def target_intent(kind: str, target_id: str) -> tuple[str, str, str]:
    return ("affect_target", kind, target_id)


def cancel_intent(index: int) -> tuple[str, int]:
    return ("order_cancel", index)


@dataclass
class WheelState:
    """Where the player is in the wheel: whether it is open, and what has been chosen so far
    on the way to something to say."""

    open: bool = False
    # Who it is open about.
    about: str | None = None
    # The kind of thing chosen, then the thing, when it is about somebody or something; or,
    # under what is done with somebody, who.
    branch: str | None = None
    kind: str | None = None
    person: str | None = None
    # The thing it is open over, where it is the ring of what they can do with a thing (P63).
    thing: str | None = None
    # Where on the canvas whoever, or whatever, it is about stands: the ring is laid out about there.
    centre: tuple[int, int] = (0, 0)

    def show(self, about: str, branch: str | None = None, kind: str | None = None, thing: str | None = None) -> None:
        self.open, self.about, self.branch, self.kind, self.person, self.thing = True, about, branch, kind, None, thing

    def shut(self) -> None:
        self.open, self.about, self.branch, self.kind, self.person, self.thing = False, None, None, None, None, None

    def back(self) -> bool:
        """Go a step back in what is being chosen. False if there was nothing chosen to go back from."""
        if self.kind is not None:
            self.kind = None
        elif self.person is not None:
            self.person = None
        elif self.branch is not None:
            self.branch = None
        else:
            return False
        return True


@dataclass(frozen=True)
class WheelItem:
    """One thing to press, before it has a place in the ring."""

    intent: Hashable
    # What it is called, and what is said of it while the pointer is on it.
    label: str
    hint: str
    icon: str = "talk"
    # Whose face it wears in place of an icon, if it is somebody.
    face: str | None = None
    # The small icon at its corner, for something known of how they take it.
    mark: str | None = None


@dataclass(frozen=True)
class WheelEntry:
    """A round button of the ring, where it is on the canvas."""

    item: WheelItem
    rect: pygame.Rect
    # Which side of it what it is called goes: `above`, `below`, `left` or `right`.
    anchor: str

    @property
    def intent(self) -> Hashable:
        return self.item.intent

    def contains(self, position: tuple[int, int]) -> bool:
        dx, dy = position[0] - self.rect.centerx, position[1] - self.rect.centery
        return dx * dx + dy * dy <= (self.rect.width / 2) ** 2


@dataclass(frozen=True)
class WheelView:
    """What the wheel shows as it stands: its heading, what there is to press, the way back
    or out, and what is said while the pointer is on nothing."""

    title: str
    items: list[WheelItem]
    back: WheelItem
    hint: str


def icon_of(option: AffectOption) -> str:
    """The icon something that can be said goes by: its own, or that of what it is."""
    if option.icon in ui_art.GLYPHS:
        return option.icon
    return TONE_ICONS.get(option.tone) or GROUP_ICONS.get(option.group, "talk")


def _hint(option: AffectOption, said: str, world: SimulationWorld | None = None) -> str:
    if option.trait is not None and world is not None:
        # What only they can be told, for being how they are (S63).
        trait = world.registries.traits.find(option.trait) or {}
        return OWN_HINT.format(said=said, trait=str(trait.get("name", option.trait)))
    return f"{said} ({MARK_WORDS[option.liked]})" if option.liked in MARK_WORDS else said


def _option_item(option: AffectOption, intent: Hashable, said: str, world: SimulationWorld | None = None) -> WheelItem:
    mark = OWN_MARK if option.trait is not None else MARKS.get(option.liked or "")
    return WheelItem(intent, option.name or option.label, _hint(option, said, world), icon_of(option), mark=mark)


def thing_intent(object_id: str) -> tuple[str, str]:
    """To see what there is to say of a thing, from the ring of what can be done with it."""
    return ("thing_panel", object_id)


def use_icon(world: SimulationWorld, object_id: str, action: str | None) -> str:
    """The icon one of the things to do with a thing goes by: what it does for whoever does it."""
    placed = world.interactables.get(object_id)
    use = world.definition_of(placed).use_for(action) if placed is not None else None
    if use is None:
        return "work"
    if use.trains is not None:
        return "train"
    if use.heals:
        return "medicine"
    if use.consumes is not None:
        return "food" if use.consumes == "food" else "water"
    if use.unaware:
        return "moon"
    return "leisure"


def _thing_view(world: SimulationWorld, resident: Resident, state: WheelState) -> WheelView | None:
    """The ring of a thing (P63): what whoever is selected can do with it as things stand,
    what it is mainly for first, and the way to what is said of the thing."""
    placed = world.interactables.get(state.thing or "")
    if placed is None:
        return None
    definition = world.definition_of(placed)
    named = f"{definition.article} {definition.name}"
    items = []
    for label, kind, target in world.affect.things_to_do(world, resident, placed):
        object_id, action = split_use(target)
        items.append(WheelItem(target_intent(kind, target), label, f"{label}: {named}", use_icon(world, object_id, action)))
    items.append(WheelItem(thing_intent(placed.object_id), LOOK_LABEL, LOOK_HINT.format(thing=named), "study"))
    close = WheelItem(CLOSE_INTENT, CLOSE_LABEL, "Nada, que siga", "close")
    hint = THING_HINT if len(items) > 1 else NOTHING_TO_DO
    return WheelView(f"{resident.name}: {definition.name}", items[:MOST_ENTRIES], close, hint)


def wheel_view(world: SimulationWorld, resident_id: str, state: WheelState) -> WheelView:
    """What the wheel about a resident shows, by what has been chosen in it so far."""
    resident = world.residents.get(resident_id)
    name = resident.name if resident is not None else ""
    of_thing = _thing_view(world, resident, state) if resident is not None and state.thing is not None else None
    if of_thing is not None:
        return of_thing
    options = world.affect_options(resident_id)
    back = WheelItem(BACK_INTENT, BACK_LABEL, BACK_LABEL, "back")
    chosen = next((option for option in options if option.kind == state.kind), None)
    if chosen is not None and chosen.targets:
        task = chosen.kind.partition(":")[2]
        items = [
            WheelItem(
                target_intent(chosen.kind, target_id),
                target,
                chosen.said(target_id),
                TARGET_ICONS.get(task, icon_of(chosen)),
                face=target_id if target_id in world.residents else None,
            )
            for target_id, target in chosen.targets
        ]
        people = all(item.face is not None for item in items)
        return WheelView(f"{name}: {chosen.name.lower()}", items, back, WHO_HINT if people else chosen.label.replace("{target}", "..."))
    if state.branch == SOCIAL and state.person in world.residents:
        other = world.residents[state.person]
        items = [
            _option_item(option, target_intent(option.kind, other.resident_id), option.said(other.resident_id), world)
            for option in world.affect_with(resident_id, other.resident_id)
        ]
        return WheelView(f"{name} con {other.name}", items[:MOST_ENTRIES], back, "Según lo que siente por " + other.name)
    if state.branch == SOCIAL:
        most = world.registries.affect.most_targets
        items = [
            WheelItem(person_intent(other_id), other, f"Con {other}...", "people", face=other_id)
            for other_id, other in world.affect_people(resident_id)[:most]
        ]
        return WheelView(f"{name}: social", items, back, WHO_HINT)
    if state.branch in BRANCH_GROUPS:
        groups = BRANCH_GROUPS[state.branch]
        items = [
            _option_item(option, order_intent(option.kind), option.label.replace("{target}", "..."))
            for option in options
            if option.group in groups
        ]
        return WheelView(f"{name}: {BRANCH_NAMES[state.branch].lower()}", items[:MOST_ENTRIES], back, BRANCH_HINTS[state.branch])
    close = WheelItem(CLOSE_INTENT, CLOSE_LABEL, "Nada, que siga", "close")
    items = []
    for branch in BRANCHES:
        there = bool(world.affect_people(resident_id)) if branch == SOCIAL else any(
            option.group in BRANCH_GROUPS[branch] for option in options
        )
        if there:
            items.append(WheelItem(branch_intent(branch), BRANCH_NAMES[branch], BRANCH_HINTS[branch], BRANCH_ICONS[branch]))
    if resident is not None:
        free = resident.free_will
        items.append(
            WheelItem(WILL_INTENT, WILL_FREE if free else WILL_HELD, WILL_FREE_HINT if free else WILL_HELD_HINT, "unlock" if free else "lock")
        )
    # Their name is over their head already: the wheel has no heading until something is chosen in it.
    return WheelView("", items, close, ROOT_HINT if options else NOTHING_TO_SAY)


def _radius(count: int) -> int:
    return max(SMALLEST_RADIUS, round((count + 1) * (BUTTON + GAP) / (2 * math.pi)))


def wheel_place(centre: tuple[int, int], bounds: pygame.Rect, count: int) -> tuple[int, int, int]:
    """Where the middle of a ring of that many buttons goes, and how wide it is: about a
    point, and moved no further from it than keeps all of it within some bounds."""
    radius = _radius(count)
    reach_x = radius + BUTTON // 2 + LABEL_ROOM
    reach_y = radius + BUTTON // 2 + LINE_HEIGHT * 2 + 6
    x, y = centre
    x = bounds.centerx if bounds.width < reach_x * 2 else max(bounds.left + reach_x, min(bounds.right - reach_x, x))
    y = bounds.centery if bounds.height < reach_y * 2 else max(bounds.top + reach_y, min(bounds.bottom - reach_y, y))
    return x, y, radius


def wheel_entries(centre: tuple[int, int], bounds: pygame.Rect, view: WheelView) -> list[WheelEntry]:
    """The buttons of the wheel where they are drawn: what there is to press in a ring from
    the top round, and the way back or out at the foot of it."""
    x, y, radius = wheel_place(centre, bounds, len(view.items))
    slots = len(view.items) + 1
    entries = []
    for index, item in enumerate([view.back, *view.items]):
        # The foot of the ring is the way back; the rest go round from there, the same on both sides.
        angle = math.radians(90 + 360 * index / slots)
        across, down = math.cos(angle), math.sin(angle)
        rect = pygame.Rect(0, 0, BUTTON, BUTTON)
        rect.center = (round(x + radius * across), round(y + radius * down))
        # What each is called goes outwards: to its side, or over or under the one in the very middle.
        anchor = "right" if across > 0.05 else "left" if across < -0.05 else "above" if down < 0 else "below"
        entries.append(WheelEntry(item, rect, anchor))
    return entries


def _write(target: pygame.Surface, font: BitmapFont, text: str, position: tuple[int, int], color: str) -> None:
    """Words over the map: with a dark line round them, to be read on whatever is under them."""
    x, y = position
    for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1), (1, 1), (-1, 1), (1, -1)):
        font.draw(target, text, (x + dx, y + dy), PALETTE["ink"])
    font.draw(target, text, position, PALETTE[color])


def _show(target: pygame.Surface, skin: WindowSkin, picture_at, rect: pygame.Rect) -> None:
    """A round button in its place: as fine as the window shows it, or else at the size of the canvas."""
    scale = skin.layers.scale if skin.layers is not None else 1
    if not (skin.usable and skin.picture(target, picture_at(rect.width * scale), rect)):
        target.blit(pygame.transform.smoothscale(picture_at(rect.width * 4), rect.size), rect)


def _button(
    target: pygame.Surface,
    skin: WindowSkin,
    faces: FaceRenderer,
    world: SimulationWorld,
    item: WheelItem,
    rect: pygame.Rect,
    lit: bool,
) -> None:
    resident = world.residents.get(item.face or "")
    if resident is not None:
        expression = expression_of(world, resident)
        face = faces.face(resident.resident_id, expression)
        _show(target, skin, lambda size: skin.face_disc((resident.resident_id, expression), face, size, lit), rect)
    else:
        _show(target, skin, lambda size: skin.disc(item.icon, size, lit, item.mark), rect)


def draw_wheel(
    target: pygame.Surface,
    font: BitmapFont,
    skin: WindowSkin,
    faces: FaceRenderer,
    world: SimulationWorld,
    view: WheelView,
    entries: list[WheelEntry],
    pointer: tuple[int, int] | None = None,
) -> None:
    if not entries:
        return
    under = next((entry for entry in entries if pointer is not None and entry.contains(pointer)), None)
    for entry in entries:
        _button(target, skin, faces, world, entry.item, entry.rect, entry is under)
    # What they are called goes on after all of them, so that no button is put over a word.
    for entry in entries:
        text = font.truncate(entry.item.label, LABEL_ROOM - 4)
        width = font.width(text)
        rect = entry.rect
        if entry.anchor == "right":
            place = (rect.right + 3, rect.centery - LINE_HEIGHT // 2)
        elif entry.anchor == "left":
            place = (rect.left - 3 - width, rect.centery - LINE_HEIGHT // 2)
        elif entry.anchor == "above":
            place = (rect.centerx - width // 2, rect.top - LINE_HEIGHT - 1)
        else:
            place = (rect.centerx - width // 2, rect.bottom + 1)
        way_out = entry.item.intent in (BACK_INTENT, CLOSE_INTENT)
        _write(target, font, text, place, "glow" if entry is under else "dust" if way_out else "paper")
    top = min(entry.rect.top for entry in entries)
    bottom = max(entry.rect.bottom for entry in entries)
    middle = entries[0].rect.centerx
    clip = target.get_width() - MARGIN * 2
    if view.title:
        title = font.truncate(view.title, clip)
        _write(target, font, title, (middle - font.width(title) // 2, top - LINE_HEIGHT * 2 - 3), "glow")
    said = font.truncate(under.item.hint if under is not None else view.hint, clip)
    left = max(MARGIN, min(target.get_width() - MARGIN - font.width(said), middle - font.width(said) // 2))
    _write(target, font, said, (left, bottom + LINE_HEIGHT + 3), "paper" if under is not None else "dust")


# ----- what they have been told and have not done -----


@dataclass(frozen=True)
class QueueEntry:
    """One of the things a resident has ahead of them, as a small round button to take it back with."""

    rect: pygame.Rect
    intent: Hashable
    icon: str
    hint: str
    doing: bool = False

    def contains(self, position: tuple[int, int]) -> bool:
        return self.rect.collidepoint(position)


def queue_entries(area: pygame.Rect, world: SimulationWorld, resident_id: str | None) -> list[QueueEntry]:
    """What whoever is selected has been told to do, in a row at the foot of the map by their
    panel: what they are at first. Before it, a lock while they do nothing of their own accord."""
    resident = world.residents.get(resident_id or "")
    if resident is None:
        return []
    ahead = world.orders_of(resident.resident_id)
    found: list[tuple[Hashable, str, str, bool]] = []
    if not resident.free_will:
        found.append((WILL_INTENT, "lock", WILL_HELD_HINT, False))
    for index, queued in enumerate(ahead):
        icon = queued.icon if queued.icon in ui_art.GLYPHS else TONE_ICONS.get(queued.tone) or GROUP_ICONS.get(queued.group, "talk")
        said = (QUEUE_NOW if queued.doing else "") + queued.said
        found.append((cancel_intent(index), icon, QUEUE_HINT.format(said=said), queued.doing))
    step = QUEUE_BUTTON + 3
    left = area.right - MARGIN - step * len(found) + 3
    top = area.bottom - MARGIN - QUEUE_BUTTON
    return [
        QueueEntry(pygame.Rect(left + index * step, top, QUEUE_BUTTON, QUEUE_BUTTON), intent, icon, hint, doing)
        for index, (intent, icon, hint, doing) in enumerate(found)
    ]


def draw_queue(
    target: pygame.Surface,
    font: BitmapFont,
    skin: WindowSkin,
    entries: list[QueueEntry],
    pointer: tuple[int, int] | None = None,
) -> None:
    under = next((entry for entry in entries if pointer is not None and entry.contains(pointer)), None)
    for entry in entries:
        lit = entry is under or entry.doing
        _show(target, skin, lambda size, entry=entry, lit=lit: skin.disc(entry.icon, size, lit), entry.rect)
    if under is not None:
        text = font.truncate(under.hint, target.get_width() // 2)
        left = min(under.rect.centerx - font.width(text) // 2, entries[-1].rect.right - font.width(text))
        _write(target, font, text, (left, under.rect.top - LINE_HEIGHT - 2), "paper")
