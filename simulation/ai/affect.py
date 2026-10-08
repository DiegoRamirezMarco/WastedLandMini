"""Affecting a resident: the one place where the player's word is an order.

Everywhere else residents decide for themselves and the player advises. Here the player stops
a resident, who stands and listens, and tells them what to do: see to a need, go to somebody,
pass the time, get on with something, or simply hear a few words. They do it, as far as it can
be done. What can be done with somebody is what they feel for them: there is always talk, and
past that only what there is between the two, from a joke to a kiss to coming to blows.

What is said one thing after another is done one thing after another (S50): the first at once,
the rest when their turn comes. And a resident can be told to do nothing of their own accord,
who then waits to be told.

What can be said is data. What is on offer at a given moment follows from how things stand.
"""

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from simulation.ai.utility_ai import ScoredAction
from simulation.events.event import DomainEvent
from simulation.residents.activity import HEED_ACTION, WAIT_ACTION, Activity, Order
from simulation.residents.needs import NEED_NAMES
from simulation.residents.resident import Resident
from simulation.social.relationship import FEELINGS, SIGNED_FEELINGS, Relationship
from simulation.tastes.taste import TAG, key_of
from simulation.work.salvage import SALVAGE_ACTION
from world.interactable import Interactable
from world.pathfinding import manhattan

if TYPE_CHECKING:
    from simulation.world import SimulationWorld

# The groups what can be said falls into.
NEED, WITH, INCITE, LEISURE, TASK, WORDS = "need", "with", "incite", "leisure", "task", "words"
GROUPS = (NEED, WITH, INCITE, LEISURE, TASK, WORDS)
# The groups of what is done with somebody else.
SHARED = (WITH, INCITE, LEISURE)
# What a resident can be told to get on with.
TO_POST, TAKE_CHARGE, SALVAGE, TAKE_JOB, LEAVE_JOB, TREAT, STOP = (
    "to_post", "take_charge", "salvage", "take_job", "leave_job", "treat", "stop",
)
TASKS = (TO_POST, TAKE_CHARGE, SALVAGE, TAKE_JOB, LEAVE_JOB, TREAT, STOP)
# Who an exchange can be had with: anybody, only somebody they are no couple with, or only their partner.
ANYBODY, SINGLE, PARTNER = "anybody", "single", "partner"
# What an exchange is, for whoever shows it: between friends, between two who are drawn to
# each other, between two who are at odds, or to pass the time.
FRIENDLY, ROMANCE, HOSTILE, PLAY = "friendly", "romance", "hostile", "play"
TONES = (FRIENDLY, ROMANCE, HOSTILE, PLAY)
HELD_IMPORTANCE = 10
ORDER_IMPORTANCE = 25
QUEUED_IMPORTANCE = 10
DROPPED_IMPORTANCE = 15
WILL_IMPORTANCE = 20
FOOD = "food"

# One way of feeling that will do: for each feeling it goes by, the least and the most of it.
Feels = dict[str, tuple[float, float]]


@dataclass(frozen=True)
class NeedOrder:
    label: str
    # The need it sees to, or whether it is being mended that is sought.
    need: str | None = None
    heals: bool = False
    # Whether it is done asleep, which only somewhere to sleep will do for.
    asleep: bool = False
    name: str = ""
    icon: str | None = None


@dataclass(frozen=True)
class ExchangeOrder:
    label: str
    interaction: str
    who: str = ANYBODY
    # The feeling that has to be strong for it to be something they can be set on to, if any.
    feeling: str | None = None
    # What they have to feel for the other for it to be on offer: any one of these will do,
    # and each is every feeling it names being within its bounds. Empty for what needs nothing felt.
    feels: tuple[Feels, ...] = ()
    name: str = ""
    tone: str = FRIENDLY
    icon: str | None = None


@dataclass(frozen=True)
class WordsOrder:
    label: str
    needs: dict[str, float] = field(default_factory=dict)
    mood: float = 0.0
    name: str = ""
    icon: str | None = None


@dataclass(frozen=True)
class TaskOrder:
    label: str
    name: str = ""
    icon: str | None = None


@dataclass(frozen=True)
class AffectSettings:
    # Minutes a resident who has been stopped stands and listens before going about their day.
    hold_minutes: int = 30
    # How strong a feeling for somebody has to be for a resident to be set on to act on it.
    strong_feeling: float = 50.0
    # How many things or people are offered to choose among at most, the nearest first.
    most_targets: int = 8
    # How many things a resident can have been told to do that they have not got to yet.
    most_orders: int = 6
    # Minutes at a time that somebody who does nothing unasked stands by, and how high a need
    # of the body has to get for them to see to it without being told.
    wait_minutes: int = 10
    desperate_need: float = 90.0
    needs: dict[str, NeedOrder] = field(default_factory=dict)
    exchanges: dict[str, ExchangeOrder] = field(default_factory=dict)
    incitements: dict[str, ExchangeOrder] = field(default_factory=dict)
    # Ways of passing the time with somebody. What is done alone is in `data/leisure.json`.
    pastimes: dict[str, ExchangeOrder] = field(default_factory=dict)
    words: dict[str, WordsOrder] = field(default_factory=dict)
    tasks: dict[str, TaskOrder] = field(default_factory=dict)

    def shared(self, group: str) -> dict[str, ExchangeOrder]:
        """What can be done with somebody, of one group of it."""
        return {WITH: self.exchanges, INCITE: self.incitements, LEISURE: self.pastimes}.get(group, {})


@dataclass(frozen=True)
class AffectOption:
    """One thing the player can tell a resident right now."""

    # What it is, as `group:name`: `need:eat`, `with:talk`, `task:salvage`.
    kind: str
    group: str
    # What it says, with `{target}` where whoever or whatever it is about goes.
    label: str
    # Who or what it can be about, as IDs with their names. Empty for what is about nothing.
    targets: tuple[tuple[str, str], ...] = ()
    # What it is called for short, where there is no room for what it says.
    name: str = ""
    # What it is between two people, where it is between two; and the icon it goes by, if it has its own.
    tone: str = ""
    icon: str | None = None
    # How they take it, as far as the player has found out: a reaction, or None for what has
    # not shown and for what is the same to everybody.
    liked: str | None = None

    def said(self, target_id: str | None = None) -> str:
        name = next((name for each, name in self.targets if each == target_id), "")
        return self.label.replace("{target}", name)


@dataclass(frozen=True)
class QueuedOrder:
    """Something a resident has been told to do, as it stands in what they have ahead of them."""

    order: Order
    said: str
    name: str
    group: str
    tone: str = ""
    icon: str | None = None
    # Whether it is what they are at right now.
    doing: bool = False


@dataclass(frozen=True)
class AffectResult:
    ok: bool
    message: str


def _feels(name: str, data: Any, where: str) -> tuple[Feels, ...]:
    """What has to be felt, out of the data: one way of feeling, or a list of ways any of which will do."""
    ways = data if isinstance(data, list) else [data]
    if not ways:
        raise ValueError(f"{where} {name} goes by what is felt, and says nothing of what")
    found = []
    for way in ways:
        if not isinstance(way, dict) or not way:
            raise ValueError(f"{where} {name} goes by what is felt, as feelings with their bounds")
        bounds: Feels = {}
        for feeling, value in way.items():
            if feeling not in FEELINGS:
                raise ValueError(f"{where} {name} goes by a feeling there is not: {feeling}")
            lowest = -100.0 if feeling in SIGNED_FEELINGS else 0.0
            least, most = (float(value[0]), float(value[1])) if isinstance(value, list) else (float(value), 100.0)
            if not lowest <= least <= most <= 100.0:
                raise ValueError(f"{where} {name} asks for {feeling} out of bounds")
            bounds[str(feeling)] = (least, most)
        found.append(bounds)
    return tuple(found)


def _exchange(name: str, data: Any, where: str, tone: str = FRIENDLY) -> ExchangeOrder:
    if not isinstance(data, dict) or "label" not in data or "interaction" not in data:
        raise ValueError(f"{where} {name} needs a label and an interaction")
    order = ExchangeOrder(
        label=str(data["label"]),
        interaction=str(data["interaction"]),
        who=str(data.get("who", ANYBODY)),
        feeling=str(data["feeling"]) if data.get("feeling") else None,
        feels=_feels(name, data["feels"], where) if "feels" in data else (),
        name=str(data.get("name", data["label"])),
        tone=str(data.get("tone", tone)),
        icon=str(data["icon"]) if data.get("icon") else None,
    )
    if order.who not in (ANYBODY, SINGLE, PARTNER):
        raise ValueError(f"{where} {name} is with somebody it cannot tell: {order.who}")
    if order.feeling is not None and order.feeling not in FEELINGS:
        raise ValueError(f"{where} {name} goes by a feeling there is not: {order.feeling}")
    if order.tone not in TONES:
        raise ValueError(f"{where} {name} is of a tone there is not: {order.tone}")
    return order


def affect_settings_from_data(data: dict[str, Any]) -> AffectSettings:
    defaults = AffectSettings()
    needs = {}
    for name, values in data.get("needs", {}).items():
        if not isinstance(values, dict) or "label" not in values:
            raise ValueError(f"Need {name} that a resident can be told to see to needs a label")
        order = NeedOrder(
            label=str(values["label"]),
            need=str(values["need"]) if values.get("need") else None,
            heals=bool(values.get("heals", False)),
            asleep=bool(values.get("asleep", False)),
            name=str(values.get("name", values["label"])),
            icon=str(values["icon"]) if values.get("icon") else None,
        )
        if (order.need is None) == (not order.heals) or (order.need is not None and order.need not in NEED_NAMES):
            raise ValueError(f"Need {name} must name a need there is, or be for being mended, and not both")
        needs[str(name)] = order
    incitements = {
        str(name): _exchange(str(name), values, "Incitement") for name, values in data.get("incite", {}).items()
    }
    if any(order.feeling is None and not order.feels for order in incitements.values()):
        raise ValueError("What a resident is set on to goes by a feeling of theirs")
    words = {}
    for name, values in data.get("words", {}).items():
        if not isinstance(values, dict) or "label" not in values:
            raise ValueError(f"Words {name} need a label")
        words[str(name)] = WordsOrder(
            label=str(values["label"]),
            needs={str(need): float(delta) for need, delta in values.get("needs", {}).items()},
            mood=float(values.get("mood", 0.0)),
            name=str(values.get("name", values["label"])),
            icon=str(values["icon"]) if values.get("icon") else None,
        )
        if any(need not in NEED_NAMES for need in words[str(name)].needs):
            raise ValueError(f"Words {name} change a need there is not")
    tasks = {}
    for name, values in data.get("tasks", {}).items():
        # A task is what telling it says, or that with what it is called for short and its icon.
        if isinstance(values, dict) and "label" not in values:
            raise ValueError(f"Task {name} needs a label")
        label = str(values["label"]) if isinstance(values, dict) else str(values)
        tasks[str(name)] = TaskOrder(
            label=label,
            name=str(values.get("name", label)) if isinstance(values, dict) else label,
            icon=str(values["icon"]) if isinstance(values, dict) and values.get("icon") else None,
        )
    if any(name not in TASKS for name in tasks):
        raise ValueError(f"A resident can only be told to get on with one of {TASKS}")
    settings = AffectSettings(
        hold_minutes=int(data.get("hold_minutes", defaults.hold_minutes)),
        strong_feeling=float(data.get("strong_feeling", defaults.strong_feeling)),
        most_targets=int(data.get("most_targets", defaults.most_targets)),
        most_orders=int(data.get("most_orders", defaults.most_orders)),
        wait_minutes=int(data.get("wait_minutes", defaults.wait_minutes)),
        desperate_need=float(data.get("desperate_need", defaults.desperate_need)),
        needs=needs,
        exchanges={str(name): _exchange(str(name), values, "Exchange") for name, values in data.get("with", {}).items()},
        incitements=incitements,
        pastimes={
            str(name): _exchange(str(name), values, "Pastime", PLAY) for name, values in data.get("leisure", {}).items()
        },
        words=words,
        tasks=tasks,
    )
    if settings.hold_minutes < 1 or settings.most_targets < 1:
        raise ValueError("A resident listens for a minute or more, and is offered at least one thing to choose")
    if settings.most_orders < 1 or settings.wait_minutes < 1:
        raise ValueError("A resident can be told at least one thing ahead, and waits a minute or more at a time")
    return settings


class AffectSystem:
    # ----- stopping somebody -----

    def obstacle(self, world: "SimulationWorld", resident_id: str) -> str | None:
        """Why a resident cannot be told anything right now. None if they can."""
        resident = world.residents.get(resident_id)
        if resident is None:
            return "No hay a quién decírselo"
        if resident.away:
            return f"{resident.name} está fuera del asentamiento"
        if resident_id in world.leaving:
            return f"A {resident.name} le han echado: ya no escucha a nadie"
        if world.interventions.pending_for(world, resident_id) is not None:
            return f"{resident.name} está dándole vueltas a algo: dile primero qué piensas de eso"
        return None

    def hold(self, world: "SimulationWorld", resident_id: str) -> AffectResult:
        """Stop a resident: they leave off what they were doing, whatever it was, and stand
        there listening for a while. With nothing said to them they go about their day, and
        take up again whatever they had been told to do."""
        error = self.obstacle(world, resident_id)
        if error is not None:
            return AffectResult(False, error)
        resident = world.residents[resident_id]
        self.interrupted(world, resident)
        self._leave_off(world, resident)
        resident.activity = Activity(HEED_ACTION, None, [], world.registries.affect.hold_minutes, using=True)
        resident.current_action = HEED_ACTION
        text = f"{resident.name} se queda pensando"
        world.emit_event(DomainEvent("resident_held", HELD_IMPORTANCE, text, [resident_id]))
        return AffectResult(True, text)

    def is_held(self, world: "SimulationWorld", resident_id: str) -> bool:
        resident = world.residents.get(resident_id)
        return resident is not None and resident.activity is not None and resident.activity.action == HEED_ACTION

    def release(self, world: "SimulationWorld", resident_id: str) -> bool:
        """Let a resident who was stopped go about their day. Returns whether they were stopped."""
        if not self.is_held(world, resident_id):
            return False
        resident = world.residents[resident_id]
        resident.activity = None
        resident.current_action = "idle"
        return True

    def _leave_off(self, world: "SimulationWorld", resident: Resident) -> None:
        """Have a resident drop what they are doing, and whoever they were doing it with."""
        activity = resident.activity
        if activity is not None and activity.partner_id is not None and activity.using:
            partner = world.residents.get(activity.partner_id)
            if partner is not None and partner.activity is not None and partner.activity.partner_id == resident.resident_id:
                partner.activity = None
                partner.current_action = "idle"
        resident.activity = None
        resident.current_action = "idle"
        resident.doing = None

    # ----- what there is to say -----

    def options(self, world: "SimulationWorld", resident_id: str) -> list[AffectOption]:
        """Everything a resident can be told right now, in the order the data gives it."""
        if self.obstacle(world, resident_id) is not None:
            return []
        resident = world.residents[resident_id]
        settings = world.registries.affect
        found: list[AffectOption] = []
        for name, order in settings.needs.items():
            if self._place_for(world, resident, order) is not None:
                found.append(AffectOption(f"{NEED}:{name}", NEED, order.label, name=order.name, icon=order.icon))
        for group in (WITH, INCITE):
            found += self._shared_options(world, resident, group)
        for pastime in world.registries.leisure.pastimes.values():
            found.append(
                AffectOption(
                    f"{LEISURE}:{pastime.pastime_id}", LEISURE, pastime.label, name=pastime.name, tone=PLAY,
                    icon=pastime.icon, liked=self._known_taste(world, resident, pastime.taste),
                )
            )
        found += self._shared_options(world, resident, LEISURE)
        for name, task in settings.tasks.items():
            targets = self._task_targets(world, resident, name)
            if targets is not None:
                found.append(AffectOption(f"{TASK}:{name}", TASK, task.label, targets, name=task.name, icon=task.icon))
        for name, words in settings.words.items():
            found.append(AffectOption(f"{WORDS}:{name}", WORDS, words.label, name=words.name, icon=words.icon))
        return found

    def people(self, world: "SimulationWorld", resident_id: str) -> tuple[tuple[str, str], ...]:
        """Everybody a resident could be told to do something with right now, the nearest first."""
        if self.obstacle(world, resident_id) is not None:
            return ()
        resident = world.residents[resident_id]
        settings = world.registries.affect
        orders = [order for group in SHARED for order in settings.shared(group).values()]
        near = sorted(
            (manhattan(resident.tile, other.tile), other.resident_id, other.name)
            for other in world.residents.values()
            if any(self._may_with(world, resident, order, other) for order in orders)
        )
        return tuple((each, name) for _distance, each, name in near)

    def with_whom(self, world: "SimulationWorld", resident_id: str, other_id: str) -> list[AffectOption]:
        """What a resident can be told to do with one person in particular, as things stand
        between the two: the talk there always is, and whatever else they feel enough for."""
        other = world.residents.get(other_id)
        if other is None or self.obstacle(world, resident_id) is not None:
            return []
        resident = world.residents[resident_id]
        settings = world.registries.affect
        return [
            self._shared_option(world, resident, group, name, order, ((other_id, other.name),))
            for group in SHARED
            for name, order in settings.shared(group).items()
            if self._may_with(world, resident, order, other)
        ]

    def _shared_options(self, world: "SimulationWorld", resident: Resident, group: str) -> list[AffectOption]:
        found = []
        for name, order in world.registries.affect.shared(group).items():
            targets = self._people_for(world, resident, order)
            if targets:
                found.append(self._shared_option(world, resident, group, name, order, targets))
        return found

    def _shared_option(
        self,
        world: "SimulationWorld",
        resident: Resident,
        group: str,
        name: str,
        order: ExchangeOrder,
        targets: tuple[tuple[str, str], ...],
    ) -> AffectOption:
        definition = world.registries.interactions.get(order.interaction)
        taste = definition.pastime if definition is not None else None
        return AffectOption(
            f"{group}:{name}", group, order.label, targets, name=order.name, tone=order.tone, icon=order.icon,
            liked=self._known_taste(world, resident, taste),
        )

    def _known_taste(self, world: "SimulationWorld", resident: Resident, tag: str | None) -> str | None:
        """How a resident takes something, as far as the player has found out. None if they have not."""
        if tag is None:
            return None
        key = key_of(TAG, tag)
        return next((leaning for found, _state, leaning in world.tastes.found_out(world, resident) if found == key), None)

    def _place_for(self, world: "SimulationWorld", resident: Resident, order: NeedOrder) -> Interactable | None:
        """The nearest thing that would see to what a resident is told to see to, with room at it."""
        routine = world.activities.routine
        best: tuple[int, str] | None = None
        for placed in world.interactables.values():
            use = world.definition_of(placed).use
            if use is None or world.users_of(placed.object_id) >= use.capacity:
                continue
            if order.heals:
                fits = use.heals
            elif order.asleep:
                fits = use.unaware and use.per_minute.get(order.need or "", 0.0) < 0
            else:
                fits = not use.unaware and routine.relieves(world, resident, placed, order.need or "")
            if not fits:
                continue
            key = (manhattan(resident.tile, (placed.x, placed.y)), placed.object_id)
            if best is None or key < best:
                best = key
        return world.interactables[best[1]] if best is not None else None

    def _may_with(self, world: "SimulationWorld", resident: Resident, order: ExchangeOrder, other: Resident) -> bool:
        """Whether a resident can be told to have an exchange with somebody: they are there,
        they are who it can be had with, and the resident feels for them what it takes."""
        settings = world.registries.affect
        definition = world.registries.interactions.get(order.interaction)
        if definition is None or other is resident or other.away or other.resident_id in world.leaving:
            return False
        together = resident.couple_with == other.resident_id
        if (order.who == PARTNER and not together) or (order.who == SINGLE and together):
            return False
        if definition.romance is not None or order.tone == ROMANCE:
            # Between adults, and only towards somebody they could be drawn to.
            if not world.bonds.is_adult(world, resident) or not world.bonds.is_adult(world, other):
                return False
            if order.tone == ROMANCE and not world.family.drawn(resident, other):
                return False
        feelings = world.relationships.get((resident.resident_id, other.resident_id))
        if order.feeling is not None:
            if feelings is None or getattr(feelings, order.feeling) < settings.strong_feeling:
                return False
        if order.feels:
            felt = feelings or Relationship(resident.resident_id, other.resident_id)
            if not any(
                all(least <= getattr(felt, feeling) <= most for feeling, (least, most) in way.items())
                for way in order.feels
            ):
                return False
        if definition.then_use is not None and world.leisure.place_for(world, resident, definition.then_use) is None:
            # It leads somewhere, and there is nowhere to go on to.
            return False
        return True

    def _people_for(self, world: "SimulationWorld", resident: Resident, order: ExchangeOrder) -> tuple[tuple[str, str], ...]:
        """Who an exchange can be had with, the nearest first and no more than are offered at once."""
        settings = world.registries.affect
        people = [
            (manhattan(resident.tile, other.tile), other.resident_id, other.name)
            for other in world.residents.values()
            if self._may_with(world, resident, order, other)
        ]
        return tuple((each, name) for _distance, each, name in sorted(people)[: settings.most_targets])

    def _task_targets(self, world: "SimulationWorld", resident: Resident, name: str) -> tuple[tuple[str, str], ...] | None:
        """Who or what a task can be about. Empty for one that is about nothing, and None for
        one that cannot be told them as things stand."""
        settings = world.registries.affect
        if name == STOP:
            return ()
        if name == TO_POST:
            job = world.work.job_of(world, resident)
            on = job is not None and resident.post_id in world.interactables
            return () if on and world.work.shift_minutes_left(world, resident, job) > 0 else None
        if name == LEAVE_JOB:
            return () if resident.job_id in world.registries.jobs else None
        if name == TAKE_CHARGE:
            sites = [
                (manhattan(resident.tile, (site.x, site.y)), site.site_id, world.construction.thing(world, site.kind, site.what) or site.what)
                for site in world.sites.values()
                if site.in_charge != resident.resident_id
            ]
            return tuple((each, said) for _distance, each, said in sorted(sites)[: settings.most_targets]) or None
        if name == SALVAGE:
            about = [
                (manhattan(resident.tile, (placed.x, placed.y)), placed.object_id, self._named(world, placed))
                for placed in world.salvaging.available(world)
            ]
            # There may be several of a kind about: how far each is tells them apart.
            return tuple(
                (each, f"{said}, a {distance} pasos") for distance, each, said in sorted(about)[: settings.most_targets]
            ) or None
        if name == TAKE_JOB:
            jobs = [
                (job_id, job.name)
                for job_id, job in world.registries.jobs.items()
                if job_id != resident.job_id and world.staffing.free_post(world, job) is not None
            ]
            return tuple(jobs) or None
        if name == TREAT:
            liked = world.tastes.favourites(world, resident).get("favorite_food")
            definition = world.registries.items.find(liked or "")
            if definition is None or self._holding(world, resident, definition.item_id) is None:
                return None
            return ((definition.item_id, f"{definition.article} {definition.name}"),)
        return None

    def _named(self, world: "SimulationWorld", placed: Interactable) -> str:
        definition = world.definition_of(placed)
        return f"{definition.article} {definition.name}"

    def _holding(self, world: "SimulationWorld", resident: Resident, item_id: str) -> Interactable | None:
        """The nearest place a resident can eat from that holds an item they may take."""
        best: tuple[int, str] | None = None
        for object_id, inventory in world.containers.items():
            placed = world.interactables.get(object_id)
            use = world.definition_of(placed).use if placed is not None else None
            if use is None or use.consumes != FOOD or world.users_of(object_id) >= use.capacity:
                continue
            if not any(
                item.definition_id == item_id and item.owner_id in (None, resident.resident_id) for item in inventory.items
            ):
                continue
            key = (manhattan(resident.tile, (placed.x, placed.y)), object_id)
            if best is None or key < best:
                best = key
        return world.interactables[best[1]] if best is not None else None

    # ----- saying it -----

    def order(self, world: "SimulationWorld", resident_id: str, kind: str, target_id: str | None = None) -> AffectResult:
        """Tell a resident to do something. They do it, as far as it can be done.

        `kind` is one of what `options` offers, and `target_id` who or what it is about, where
        it is about somebody or something. Told while they are at something else they were
        told, or have yet to get to, it waits its turn. A few words are said there and then.
        """
        error = self.obstacle(world, resident_id)
        if error is not None:
            return AffectResult(False, error)
        resident = world.residents[resident_id]
        error, said = self._check(world, resident, kind, target_id)
        if error is not None:
            return AffectResult(False, error)
        settings = world.registries.affect
        group, _, name = kind.partition(":")
        told = f"{said[0].lower()}{said[1:]}"
        at_once = group == WORDS or (group == TASK and name == STOP)
        if not at_once and (self.busy(world, resident_id) or resident.orders):
            if len(resident.orders) >= settings.most_orders:
                return AffectResult(False, f"{resident.name} ya tiene bastante por delante")
            resident.orders.append(Order(kind, target_id))
            text = f"A {resident.name} se le dice, para después: {told}"
            world.emit_event(
                DomainEvent(
                    "order_queued", QUEUED_IMPORTANCE, text, [resident_id], data={"kind": kind, "target": target_id}
                )
            )
            return AffectResult(True, text)
        failed = self._carry_out(world, resident, group, name, target_id)
        if failed is not None:
            return AffectResult(False, failed)
        if not at_once:
            self._taken_up(resident, Order(kind, target_id))
        text = f"A {resident.name} se le dice: {told}"
        world.emit_event(
            DomainEvent(
                "order_given",
                ORDER_IMPORTANCE,
                text,
                [resident_id],
                data={"kind": kind, "target": target_id},
            ),
            at=resident.tile,
        )
        return AffectResult(True, text)

    def _check(
        self, world: "SimulationWorld", resident: Resident, kind: str, target_id: str | None
    ) -> tuple[str | None, str]:
        """Whether something can be told a resident as things stand, as why not if it cannot,
        and what telling it says."""
        group, _, name = kind.partition(":")
        shared = world.registries.affect.shared(group).get(name)
        if shared is not None:
            # Who it is with need not be among the few that are offered: anybody it can be had with will do.
            other = world.residents.get(target_id or "")
            if other is None:
                return "Hay que decir con quién, o con qué", ""
            if not self._may_with(world, resident, shared, other):
                return "Eso no se le puede decir ahora", ""
            return None, shared.label.replace("{target}", other.name)
        option = next((each for each in self.options(world, resident.resident_id) if each.kind == kind), None)
        if option is None:
            return "Eso no se le puede decir ahora", ""
        if option.targets and target_id not in [each for each, _name in option.targets]:
            return "Hay que decir con quién, o con qué", ""
        return None, option.said(target_id)

    def _taken_up(self, resident: Resident, order: Order) -> None:
        """Mark what a resident has just set about as something they were told to do."""
        if resident.activity is not None:
            resident.activity.ordered = True
            resident.doing = order

    def _carry_out(
        self, world: "SimulationWorld", resident: Resident, group: str, name: str, target_id: str | None
    ) -> str | None:
        """Have a resident set about what they were told. Returns why they could not, if they could not."""
        settings = world.registries.affect
        routine = world.activities.routine
        nowhere = "No hay manera de llegar hasta allí"
        if group == WORDS:
            words = settings.words[name]
            resident.needs.apply(words.needs)
            resident.adjust_mood(words.mood)
            # A few words stop nobody for long: they go back to what they were at.
            self.release(world, resident.resident_id)
            return None
        if group == NEED:
            placed = self._place_for(world, resident, settings.needs[name])
            activity = routine.use(world, resident, placed) if placed is not None else None
            if activity is None:
                return nowhere
            self._leave_off(world, resident)
            resident.activity = activity
            resident.current_action = "walking"
            return None
        if group in SHARED and name in settings.shared(group):
            order = settings.shared(group)[name]
            other = world.residents.get(target_id or "")
            if other is None:
                return "Ya no está"
            self._leave_off(world, resident)
            resident.activity = routine.social.pursue(world, resident, other, order.interaction)
            resident.current_action = "walking"
            return None
        if group == LEISURE:
            activity = world.leisure.plan(world, resident, name)
            if activity is None:
                return "Eso no se le puede decir"
            self._leave_off(world, resident)
            resident.activity = activity
            resident.current_action = "walking" if activity.path else "idle"
            return None
        if name == STOP:
            self._leave_off(world, resident)
            resident.orders.clear()
            return None
        if name == TO_POST:
            activity = world.work.plan(world, resident)
            if activity is None:
                return nowhere
            self._leave_off(world, resident)
            resident.activity = activity
            resident.current_action = "walking"
            return None
        if name == LEAVE_JOB:
            self._leave_off(world, resident)
            resident.job_id, resident.post_id, resident.work_progress = None, None, 0
            return None
        if name == TAKE_JOB:
            self._leave_off(world, resident)
            return None if world.staffing.assign(world, resident, target_id or "") else "Ese puesto ya no está libre"
        if name == TAKE_CHARGE:
            site = world.sites.get(target_id or "")
            if site is None:
                return "Esa obra ya no está"
            site.in_charge = resident.resident_id
            self._leave_off(world, resident)
            self._set_to_task(world, resident)
            return None
        if name == SALVAGE:
            result = world.salvaging.order(world, resident.resident_id, target_id or "")
            if not result.ok:
                return result.message
            self._leave_off(world, resident)
            activity = world.salvaging.plan(world, resident, ScoredAction(SALVAGE_ACTION, 1.0, target_id))
            if activity is not None:
                resident.activity = activity
                resident.current_action = "walking"
            return None
        if name == TREAT:
            placed = self._holding(world, resident, target_id or "")
            activity = routine.use(world, resident, placed) if placed is not None else None
            if activity is None:
                return nowhere
            self._leave_off(world, resident)
            resident.activity = activity
            resident.current_action = "walking"
            return None
        return "Eso no se le puede decir"

    def _set_to_task(self, world: "SimulationWorld", resident: Resident) -> bool:
        """Have a resident get on with what has been put in their hands: something to take
        apart, a site in their charge. Says whether there was anything they could get on with."""
        task = world.construction.task(world, resident)
        activity = world.construction.plan(world, resident, task) if task is not None else None
        if activity is None:
            return False
        resident.activity = activity
        resident.current_action = "walking" if activity.path else resident.current_action
        return True

    # ----- one thing after another -----

    def busy(self, world: "SimulationWorld", resident_id: str) -> bool:
        """Whether a resident is at something they were told to do."""
        resident = world.residents.get(resident_id)
        return resident is not None and resident.activity is not None and resident.activity.ordered

    def interrupted(self, world: "SimulationWorld", resident: Resident) -> None:
        """Something is about to take a resident from what they were told to do: it goes back
        to the head of what they have ahead of them, to be taken up again."""
        if resident.activity is not None and resident.activity.ordered and resident.doing is not None:
            resident.orders.insert(0, resident.doing)
            resident.activity.ordered = False
        resident.doing = None

    def next(self, world: "SimulationWorld", resident: Resident) -> Activity | None:
        """What a resident with nothing in hand does next for having been told: the next thing
        they were told, if they were told any, and if they do nothing unasked, what that leaves
        them. None for somebody free to do as they like, with nothing they were told left.

        What can no longer be done when its turn comes is let go, and it is said.
        """
        resident.doing = None
        if resident.orders and self.obstacle(world, resident.resident_id) is not None:
            return None
        while resident.orders:
            order = resident.orders.pop(0)
            group, _, name = order.kind.partition(":")
            error, _said = self._check(world, resident, order.kind, order.target_id)
            error = error or self._carry_out(world, resident, group, name, order.target_id)
            if error is not None:
                what = self.described(world, order).name
                world.emit_event(
                    DomainEvent(
                        "order_dropped",
                        DROPPED_IMPORTANCE,
                        f"{resident.name} deja sin hacer lo que se le dijo ({what[0].lower()}{what[1:]}): {error}",
                        [resident.resident_id],
                        data={"kind": order.kind, "target": order.target_id},
                    )
                )
                continue
            self._taken_up(resident, order)
            if resident.activity is not None:
                return resident.activity
        return None if resident.free_will else self._unbidden(world, resident)

    def _unbidden(self, world: "SimulationWorld", resident: Resident) -> Activity:
        """What somebody who does nothing unasked does with nothing asked of them: what was put
        in their hands and is not done, what their body can wait for no longer, and otherwise
        nothing at all."""
        settings = world.registries.affect
        if self._set_to_task(world, resident):
            return resident.activity
        for need in world.activities.urgent_needs(world, resident, settings.desperate_need):
            order = next((each for each in settings.needs.values() if each.need == need), None)
            placed = self._place_for(world, resident, order) if order is not None else None
            activity = world.activities.routine.use(world, resident, placed) if placed is not None else None
            if activity is not None:
                resident.current_action = "walking"
                return activity
        resident.current_action = WAIT_ACTION
        return Activity(WAIT_ACTION, minutes_left=settings.wait_minutes, using=True)

    def wait_tick(self, world: "SimulationWorld", resident: Resident, activity: Activity) -> None:
        """Spend a minute standing by. Every so often they look again at whether there is
        anything they have to see to, and otherwise go on standing by."""
        activity.minutes_left -= 1
        if resident.free_will:
            resident.activity = None
            resident.current_action = "idle"
        elif activity.minutes_left <= 0:
            resident.activity = self.next(world, resident)

    def queue(self, world: "SimulationWorld", resident_id: str) -> list[QueuedOrder]:
        """What a resident has been told to do and has not done: what they are at, if they
        were told to, and after it what waits, the next first."""
        resident = world.residents.get(resident_id)
        if resident is None:
            return []
        ahead = [self.described(world, order) for order in resident.orders]
        if self.busy(world, resident_id) and resident.doing is not None:
            now = self.described(world, resident.doing)
            ahead.insert(0, QueuedOrder(now.order, now.said, now.name, now.group, now.tone, now.icon, doing=True))
        return ahead

    def described(self, world: "SimulationWorld", order: Order) -> QueuedOrder:
        """What an order says and goes by, whether or not it could be told right now."""
        settings = world.registries.affect
        group, _, name = order.kind.partition(":")
        label, short, tone, icon = order.kind, order.kind, "", None
        shared = settings.shared(group).get(name)
        pastime = world.registries.leisure.pastimes.get(name) if group == LEISURE else None
        if shared is not None:
            label, short, tone, icon = shared.label, shared.name, shared.tone, shared.icon
        elif pastime is not None:
            label, short, tone, icon = pastime.label, pastime.name, PLAY, pastime.icon
        elif group == NEED and name in settings.needs:
            label, short, icon = settings.needs[name].label, settings.needs[name].name, settings.needs[name].icon
        elif group == TASK and name in settings.tasks:
            label, short, icon = settings.tasks[name].label, settings.tasks[name].name, settings.tasks[name].icon
        elif group == WORDS and name in settings.words:
            label, short, icon = settings.words[name].label, settings.words[name].name, settings.words[name].icon
        said = label.replace("{target}", self._target_name(world, order.target_id))
        return QueuedOrder(order, said, short, group, tone, icon)

    def _target_name(self, world: "SimulationWorld", target_id: str | None) -> str:
        """What whoever or whatever an order is about is called. Nothing for what is gone."""
        if target_id is None:
            return ""
        if target_id in world.residents:
            return world.residents[target_id].name
        if target_id in world.sites:
            site = world.sites[target_id]
            return world.construction.thing(world, site.kind, site.what) or site.what
        if target_id in world.interactables:
            return self._named(world, world.interactables[target_id])
        if target_id in world.registries.jobs:
            return world.registries.jobs[target_id].name
        definition = world.registries.items.find(target_id)
        return f"{definition.article} {definition.name}" if definition is not None else ""

    def cancel(self, world: "SimulationWorld", resident_id: str, index: int) -> AffectResult:
        """Take back one of the things a resident has been told to do, counted as `queue` gives
        them. What they were at, they leave off."""
        resident = world.residents.get(resident_id)
        ahead = self.queue(world, resident_id)
        if resident is None or not 0 <= index < len(ahead):
            return AffectResult(False, "Eso ya no lo tiene por delante")
        taken = ahead[index]
        if taken.doing:
            self._leave_off(world, resident)
        else:
            del resident.orders[index - (1 if ahead[0].doing else 0)]
        text = f"A {resident.name} ya no se le pide: {taken.said[0].lower()}{taken.said[1:]}"
        world.emit_event(
            DomainEvent(
                "order_cancelled", QUEUED_IMPORTANCE, text, [resident_id],
                data={"kind": taken.order.kind, "target": taken.order.target_id},
            )
        )
        return AffectResult(True, text)

    # ----- doing nothing unasked -----

    def set_will(self, world: "SimulationWorld", resident_id: str, free: bool) -> AffectResult:
        """Say whether a resident does anything of their own accord. Told not to, they finish
        what they are at and from then on do what they are told and wait to be told the rest."""
        resident = world.residents.get(resident_id)
        if resident is None:
            return AffectResult(False, "No hay a quién decírselo")
        if resident.free_will == free:
            return AffectResult(True, f"{resident.name} sigue como estaba")
        resident.free_will = free
        text = (
            f"{resident.name} vuelve a hacer su vida"
            if free
            else f"{resident.name} hará solo lo que se le diga, y esperará a que se le diga"
        )
        world.emit_event(
            DomainEvent("will_changed", WILL_IMPORTANCE, text, [resident_id], data={"free": free})
        )
        return AffectResult(True, text)
