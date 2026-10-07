"""Affecting a resident: the one place where the player's word is an order.

Everywhere else residents decide for themselves and the player advises. Here the player stops
a resident, who stands and listens, and tells them what to do: see to a need, go to somebody,
get on with something, or simply hear a few words. They do it, as far as it can be done. What
they feel strongly for somebody is something they can be set on to act on.

What can be said is data. What is on offer at a given moment follows from how things stand.
"""

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from simulation.events.event import DomainEvent
from simulation.residents.activity import HEED_ACTION, Activity
from simulation.residents.needs import NEED_NAMES
from simulation.residents.resident import Resident
from simulation.social.relationship import FEELINGS
from world.interactable import Interactable
from world.pathfinding import manhattan

if TYPE_CHECKING:
    from simulation.world import SimulationWorld

# The groups what can be said falls into.
NEED, WITH, INCITE, TASK, WORDS = "need", "with", "incite", "task", "words"
GROUPS = (NEED, WITH, INCITE, TASK, WORDS)
# What a resident can be told to get on with.
TO_POST, TAKE_CHARGE, SALVAGE, TAKE_JOB, LEAVE_JOB, TREAT, STOP = (
    "to_post", "take_charge", "salvage", "take_job", "leave_job", "treat", "stop",
)
TASKS = (TO_POST, TAKE_CHARGE, SALVAGE, TAKE_JOB, LEAVE_JOB, TREAT, STOP)
# Who an exchange can be had with: anybody, only somebody they are no couple with, or only their partner.
ANYBODY, SINGLE, PARTNER = "anybody", "single", "partner"
HELD_IMPORTANCE = 10
ORDER_IMPORTANCE = 25
FOOD = "food"


@dataclass(frozen=True)
class NeedOrder:
    label: str
    # The need it sees to, or whether it is being mended that is sought.
    need: str | None = None
    heals: bool = False
    # Whether it is done asleep, which only somewhere to sleep will do for.
    asleep: bool = False


@dataclass(frozen=True)
class ExchangeOrder:
    label: str
    interaction: str
    who: str = ANYBODY
    # The feeling that has to be strong for it to be something they can be set on to, if any.
    feeling: str | None = None


@dataclass(frozen=True)
class WordsOrder:
    label: str
    needs: dict[str, float] = field(default_factory=dict)
    mood: float = 0.0


@dataclass(frozen=True)
class AffectSettings:
    # Minutes a resident who has been stopped stands and listens before going about their day.
    hold_minutes: int = 30
    # How strong a feeling for somebody has to be for a resident to be set on to act on it.
    strong_feeling: float = 50.0
    # How many things or people are offered to choose among at most, the nearest first.
    most_targets: int = 8
    needs: dict[str, NeedOrder] = field(default_factory=dict)
    exchanges: dict[str, ExchangeOrder] = field(default_factory=dict)
    incitements: dict[str, ExchangeOrder] = field(default_factory=dict)
    words: dict[str, WordsOrder] = field(default_factory=dict)
    tasks: dict[str, str] = field(default_factory=dict)


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

    def said(self, target_id: str | None = None) -> str:
        name = next((name for each, name in self.targets if each == target_id), "")
        return self.label.replace("{target}", name)


@dataclass(frozen=True)
class AffectResult:
    ok: bool
    message: str


def _exchange(name: str, data: Any, where: str) -> ExchangeOrder:
    if not isinstance(data, dict) or "label" not in data or "interaction" not in data:
        raise ValueError(f"{where} {name} needs a label and an interaction")
    order = ExchangeOrder(
        label=str(data["label"]),
        interaction=str(data["interaction"]),
        who=str(data.get("who", ANYBODY)),
        feeling=str(data["feeling"]) if data.get("feeling") else None,
    )
    if order.who not in (ANYBODY, SINGLE, PARTNER):
        raise ValueError(f"{where} {name} is with somebody it cannot tell: {order.who}")
    if order.feeling is not None and order.feeling not in FEELINGS:
        raise ValueError(f"{where} {name} goes by a feeling there is not: {order.feeling}")
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
        )
        if (order.need is None) == (not order.heals) or (order.need is not None and order.need not in NEED_NAMES):
            raise ValueError(f"Need {name} must name a need there is, or be for being mended, and not both")
        needs[str(name)] = order
    incitements = {
        str(name): _exchange(str(name), values, "Incitement") for name, values in data.get("incite", {}).items()
    }
    if any(order.feeling is None for order in incitements.values()):
        raise ValueError("What a resident is set on to goes by a feeling of theirs")
    words = {}
    for name, values in data.get("words", {}).items():
        if not isinstance(values, dict) or "label" not in values:
            raise ValueError(f"Words {name} need a label")
        words[str(name)] = WordsOrder(
            label=str(values["label"]),
            needs={str(need): float(delta) for need, delta in values.get("needs", {}).items()},
            mood=float(values.get("mood", 0.0)),
        )
        if any(need not in NEED_NAMES for need in words[str(name)].needs):
            raise ValueError(f"Words {name} change a need there is not")
    tasks = {str(name): str(label) for name, label in data.get("tasks", {}).items()}
    if any(name not in TASKS for name in tasks):
        raise ValueError(f"A resident can only be told to get on with one of {TASKS}")
    settings = AffectSettings(
        hold_minutes=int(data.get("hold_minutes", defaults.hold_minutes)),
        strong_feeling=float(data.get("strong_feeling", defaults.strong_feeling)),
        most_targets=int(data.get("most_targets", defaults.most_targets)),
        needs=needs,
        exchanges={str(name): _exchange(str(name), values, "Exchange") for name, values in data.get("with", {}).items()},
        incitements=incitements,
        words=words,
        tasks=tasks,
    )
    if settings.hold_minutes < 1 or settings.most_targets < 1:
        raise ValueError("A resident listens for a minute or more, and is offered at least one thing to choose")
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
        there listening for a while. With nothing said to them they go about their day."""
        error = self.obstacle(world, resident_id)
        if error is not None:
            return AffectResult(False, error)
        resident = world.residents[resident_id]
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
                found.append(AffectOption(f"{NEED}:{name}", NEED, order.label))
        for group, orders in ((WITH, settings.exchanges), (INCITE, settings.incitements)):
            for name, order in orders.items():
                targets = self._people_for(world, resident, order)
                if targets:
                    found.append(AffectOption(f"{group}:{name}", group, order.label, targets))
        for name, label in settings.tasks.items():
            targets = self._task_targets(world, resident, name)
            if targets is not None:
                found.append(AffectOption(f"{TASK}:{name}", TASK, label, targets))
        for name, words in settings.words.items():
            found.append(AffectOption(f"{WORDS}:{name}", WORDS, words.label))
        return found

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

    def _people_for(self, world: "SimulationWorld", resident: Resident, order: ExchangeOrder) -> tuple[tuple[str, str], ...]:
        settings = world.registries.affect
        definition = world.registries.interactions.get(order.interaction)
        if definition is None:
            return ()
        romance = definition.romance is not None
        if romance and not world.bonds.is_adult(world, resident):
            return ()
        people = []
        for other in world.residents.values():
            if other is resident or other.away or other.resident_id in world.leaving:
                continue
            together = resident.couple_with == other.resident_id
            if (order.who == PARTNER and not together) or (order.who == SINGLE and together):
                continue
            if romance and not world.bonds.is_adult(world, other):
                continue
            if order.feeling is not None:
                feelings = world.relationships.get((resident.resident_id, other.resident_id))
                if feelings is None or getattr(feelings, order.feeling) < settings.strong_feeling:
                    continue
            people.append((manhattan(resident.tile, other.tile), other.resident_id, other.name))
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
        it is about somebody or something.
        """
        error = self.obstacle(world, resident_id)
        if error is not None:
            return AffectResult(False, error)
        option = next((each for each in self.options(world, resident_id) if each.kind == kind), None)
        if option is None:
            return AffectResult(False, "Eso no se le puede decir ahora")
        if option.targets and target_id not in [each for each, _name in option.targets]:
            return AffectResult(False, "Hay que decir con quién, o con qué")
        resident = world.residents[resident_id]
        group, _, name = kind.partition(":")
        said = option.said(target_id)
        failed = self._carry_out(world, resident, group, name, target_id)
        if failed is not None:
            return AffectResult(False, failed)
        text = f"A {resident.name} se le dice: {said[0].lower()}{said[1:]}"
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
        if group in (WITH, INCITE):
            order = (settings.exchanges if group == WITH else settings.incitements)[name]
            other = world.residents.get(target_id or "")
            if other is None:
                return "Ya no está"
            self._leave_off(world, resident)
            resident.activity = routine.social.pursue(world, resident, other, order.interaction)
            resident.current_action = "walking"
            return None
        if name == STOP:
            self._leave_off(world, resident)
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
            return None
        if name == SALVAGE:
            result = world.salvaging.order(world, resident.resident_id, target_id or "")
            if not result.ok:
                return result.message
            self._leave_off(world, resident)
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
