"""Wishes (S61): small things a resident comes to want, one at a time.

Something to eat or drink, a while with somebody, a thing of their own, something to do. They
see to it themselves when the chance comes, a little the readier for wanting it, or the player
helps: gives them the thing, tells them to go and talk. A wish that is met lifts their spirits
and is remembered. One that is let go unmet is remembered too, the other way.

What they come to want is out of what they know of and like, by a die of their own: wishing
throws none of the settlement's dice.
"""

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from simulation.events.event import DomainEvent
from simulation.items.item import ItemDefinition
from simulation.memory.memory import Memory
from simulation.residents.resident import Resident
from simulation.rng import SimulationRNG

if TYPE_CHECKING:
    from simulation.ai.utility_ai import ScoredAction
    from simulation.world import SimulationWorld

# The kinds of thing a resident may wish for.
EAT, WITH, HAVE, DO = "eat", "with", "have", "do"
KINDS = (EAT, WITH, HAVE, DO)
WISH_EVENT = "wish_made"
MET_EVENT = "wish_met"
LAPSED_EVENT = "wish_lapsed"
WISH_IMPORTANCE = 14
MET_IMPORTANCE = 20
LAPSED_IMPORTANCE = 16
WISH_MEMORY = 30.0
MINUTES_PER_HOUR = 60


@dataclass
class Wish:
    """Something a resident wants right now."""

    resident_id: str
    kind: str
    # What it is for: an item, somebody, or something to do, by ID.
    what: str
    since: int = 0
    until: int = 0


@dataclass(frozen=True)
class WishKind:
    """One kind of thing to wish for: how it is said, and how much it weighs beside the rest."""

    kind_id: str
    # What is said of somebody who has it, with `{name}` and `{what}`.
    text: str
    weight: float = 1.0
    # What they remember of it met and let go, with `{what}`.
    met: str = "Tuve {what}."
    lapsed: str = "Me quedé sin {what}."
    # What is said of them when it is met and when it is let go, with `{name}` and `{what}`.
    got: str = "{name} ya tiene lo que quería: {what}"
    lost: str = "A {name} se le pasan las ganas de {what}"
    # For a thing to eat or to have: the categories of item that are wished for so.
    categories: tuple[str, ...] = ()


@dataclass(frozen=True)
class WishSettings:
    kinds: dict[str, WishKind] = field(default_factory=dict)
    # The hours of the day in which one may come, how likely each of them, and how long it lasts.
    hours: tuple[int, int] = (8, 22)
    chance: float = 0.0
    lasts_hours: int = 24
    # What one met and one let go do to their spirits, and how they sit in what is remembered.
    met_mood: float = 10.0
    lapsed_mood: float = -6.0
    met_value: float = 0.5
    lapsed_value: float = -0.3
    # How much a thing has to be liked to be wished for, and somebody to be wished to be with.
    liked_from: float = 20.0
    fond_from: float = 20.0
    # How much the readier they are to do what would meet it.
    pull: float = 0.3

    @property
    def enabled(self) -> bool:
        return bool(self.kinds) and self.chance > 0


def wish_settings_from_data(data: dict[str, Any]) -> WishSettings:
    defaults = WishSettings()
    kinds = {}
    for kind_id, values in data.get("kinds", {}).items():
        if kind_id not in KINDS or not isinstance(values, dict) or "text" not in values:
            raise ValueError(f"A wish is one of {KINDS} and says how it is told: {kind_id}")
        kinds[str(kind_id)] = WishKind(
            str(kind_id),
            str(values["text"]),
            float(values.get("weight", 1.0)),
            str(values.get("met", WishKind.met)),
            str(values.get("lapsed", WishKind.lapsed)),
            str(values.get("got", WishKind.got)),
            str(values.get("lost", WishKind.lost)),
            tuple(str(category) for category in values.get("categories", ())),
        )
        if kind_id in (EAT, HAVE) and not kinds[kind_id].categories:
            raise ValueError(f"A wish for a thing says which categories of thing: {kind_id}")
    start, end = (int(hour) for hour in data.get("hours", defaults.hours))
    settings = WishSettings(
        kinds=kinds,
        hours=(start, end),
        chance=float(data.get("chance", defaults.chance)),
        lasts_hours=int(data.get("lasts_hours", defaults.lasts_hours)),
        met_mood=float(data.get("met_mood", defaults.met_mood)),
        lapsed_mood=float(data.get("lapsed_mood", defaults.lapsed_mood)),
        met_value=float(data.get("met_value", defaults.met_value)),
        lapsed_value=float(data.get("lapsed_value", defaults.lapsed_value)),
        liked_from=float(data.get("liked_from", defaults.liked_from)),
        fond_from=float(data.get("fond_from", defaults.fond_from)),
        pull=float(data.get("pull", defaults.pull)),
    )
    if not 0.0 <= settings.chance <= 1.0 or settings.lasts_hours < 1 or not 0 <= start < end <= 24:
        raise ValueError("A wish comes an hour in so many, in hours of the day, and lasts an hour or more")
    if any(kind.weight <= 0 for kind in kinds.values()):
        raise ValueError("A kind of wish comes sometimes")
    return settings


class WishSystem:
    def settings(self, world: "SimulationWorld") -> WishSettings:
        return world.registries.wishes

    def of(self, world: "SimulationWorld", resident_id: str) -> Wish | None:
        return world.wishes_of.get(resident_id)

    # ----- what it is for, in words -----

    def what(self, world: "SimulationWorld", wish: Wish) -> str:
        """What a wish is for, as it is named in the middle of a sentence."""
        if wish.kind in (EAT, HAVE):
            definition = world.registries.items.resolve(wish.what)
            return f"{definition.article} {definition.name}"
        if wish.kind == WITH:
            other = world.residents.get(wish.what)
            return other.name if other is not None else "alguien"
        return self._doing(world, wish.what) or wish.what

    def said(self, world: "SimulationWorld", wish: Wish) -> str:
        """A wish as it is told of whoever has it."""
        kind = self.settings(world).kinds.get(wish.kind)
        resident = world.residents.get(wish.resident_id)
        text = kind.text if kind is not None else "{name} quiere {what}"
        return text.replace("{name}", resident.name if resident is not None else "").replace("{what}", self.what(world, wish))

    def _doing(self, world: "SimulationWorld", action: str) -> str | None:
        """What something to do is called, lower case: a pastime, or one of the things done with a thing."""
        pastime = world.registries.leisure.pastimes.get(action)
        if pastime is not None:
            return pastime.name.lower()
        for kind in world.registries.interactables.kinds():
            use = world.registries.interactables.get(kind).use_named(action)
            if use is not None and use.label:
                return use.label.lower()
        return None

    # ----- coming to want something -----

    def _liked_items(self, world: "SimulationWorld", resident: Resident, kind: str) -> list[ItemDefinition]:
        """The things a resident knows of and likes that are wished for this way. Not what a
        law they keep forbids them, nor what they have made up their mind against."""
        settings = self.settings(world)
        categories = settings.kinds[kind].categories
        return [
            definition
            for definition in world.talk.known_items(world, resident)
            if definition.category in categories
            and world.tastes.fancy(world, resident, definition) >= settings.liked_from
            and world.politics.laws.may_have(world, resident, definition)
            and world.substances.wish(world, resident, definition) is not None
        ]

    def _things_to_do(self, world: "SimulationWorld", resident: Resident) -> list[str]:
        """What there is to do for the sake of it: the pastimes, and whatever else is done
        with the things that stand in the settlement and are theirs to use."""
        found = list(world.registries.leisure.pastimes)
        for placed in world.interactables.values():
            for use in world.definition_of(placed).more:
                if use.trains is None and use.action not in found and world.housing.may_use(world, resident, placed, use):
                    found.append(use.action)
        return found

    def options(self, world: "SimulationWorld", resident: Resident) -> list[tuple[str, str]]:
        """Everything a resident could come to wish for as things stand, as a kind and what for."""
        settings = self.settings(world)
        found: list[tuple[str, str]] = []
        if EAT in settings.kinds:
            found += [(EAT, definition.item_id) for definition in self._liked_items(world, resident, EAT)]
        if HAVE in settings.kinds:
            mine = {item.definition_id for item in resident.inventory.items if item.owner_id == resident.resident_id}
            found += [
                (HAVE, definition.item_id)
                for definition in self._liked_items(world, resident, HAVE)
                if definition.item_id not in mine
            ]
        if WITH in settings.kinds:
            for other in world.residents.values():
                feelings = world.relationships.get((resident.resident_id, other.resident_id))
                if other is not resident and not other.away and feelings is not None and feelings.affection >= settings.fond_from:
                    found.append((WITH, other.resident_id))
        if DO in settings.kinds:
            found += [(DO, action) for action in self._things_to_do(world, resident)]
        return found

    def make(self, world: "SimulationWorld", resident: Resident, kind: str, what: str) -> Wish:
        """Have a resident want something, in place of whatever they wanted."""
        now = world.clock.total_minutes
        wish = Wish(resident.resident_id, kind, what, now, now + self.settings(world).lasts_hours * MINUTES_PER_HOUR)
        world.wishes_of[resident.resident_id] = wish
        world.emit_event(
            DomainEvent(
                WISH_EVENT,
                WISH_IMPORTANCE,
                self.said(world, wish),
                [resident.resident_id],
                data={"resident_id": resident.resident_id, "kind": kind, "what": what},
            ),
            at=resident.tile if not resident.away else None,
        )
        return wish

    def _come_to(self, world: "SimulationWorld", resident: Resident) -> None:
        """On the hour: maybe have a resident with nothing on their mind come to want something."""
        settings = self.settings(world)
        dice = SimulationRNG.keyed(world.rng.seed, "wish", resident.resident_id, world.clock.total_minutes)
        if dice.random() >= settings.chance:
            return
        by_kind: dict[str, list[str]] = {}
        for kind, what in self.options(world, resident):
            by_kind.setdefault(kind, []).append(what)
        if not by_kind:
            return
        mark = dice.random() * sum(settings.kinds[kind].weight for kind in by_kind)
        chosen = next(iter(by_kind))
        for kind in by_kind:
            mark -= settings.kinds[kind].weight
            if mark < 0:
                chosen = kind
                break
        wanted = by_kind[chosen]
        self.make(world, resident, chosen, wanted[dice.randint(0, len(wanted) - 1)])

    # ----- whether it is met -----

    def met(self, world: "SimulationWorld", resident: Resident, wish: Wish) -> bool:
        """Whether what a resident is at, or has, is what they wanted."""
        activity = resident.activity
        if wish.kind == HAVE:
            return any(
                item.definition_id == wish.what and item.owner_id == resident.resident_id for item in resident.inventory.items
            )
        if activity is None or not activity.using:
            return False
        if wish.kind == WITH:
            interaction = world.registries.interactions.get(activity.action)
            return activity.partner_id == wish.what and interaction is not None and not interaction.hostile
        if wish.kind == DO:
            return activity.action == wish.what
        if activity.item_id is None:
            return False
        item = world.items.find_item(world, activity.item_id)
        return (item.definition_id if item is not None else activity.item_id) == wish.what

    def handed(self, world: "SimulationWorld", resident: Resident, definition_id: str) -> bool:
        """A thing put in a resident's hands that is the thing they wanted, to eat or to have,
        is their wish met there and then."""
        wish = world.wishes_of.get(resident.resident_id)
        if wish is None or wish.kind not in (EAT, HAVE) or wish.what != definition_id:
            return False
        self._end(world, resident, wish, met=True)
        return True

    def fancied(self, world: "SimulationWorld", resident: Resident) -> str | None:
        """What a resident wants to eat or drink right now, if anything: where there is some
        of it among what they may take, that is what they take."""
        wish = world.wishes_of.get(resident.resident_id)
        return wish.what if wish is not None and wish.kind == EAT else None

    def _end(self, world: "SimulationWorld", resident: Resident, wish: Wish, met: bool) -> None:
        settings = self.settings(world)
        kind = settings.kinds.get(wish.kind)
        what = self.what(world, wish)
        del world.wishes_of[resident.resident_id]
        resident.adjust_mood(settings.met_mood if met else settings.lapsed_mood)
        remembered = (kind.met if met else kind.lapsed) if kind is not None else (WishKind.met if met else WishKind.lapsed)
        world.memories.remember(
            resident.resident_id,
            Memory(
                remembered.replace("{what}", what),
                WISH_MEMORY,
                settings.met_value if met else settings.lapsed_value,
                [wish.what] if wish.kind == WITH else [],
                ["wish"],
                world.clock.total_minutes,
            ),
        )
        told = (kind.got if met else kind.lost) if kind is not None else (WishKind.got if met else WishKind.lost)
        text = told.replace("{name}", resident.name).replace("{what}", what)
        world.emit_event(
            DomainEvent(
                MET_EVENT if met else LAPSED_EVENT,
                MET_IMPORTANCE if met else LAPSED_IMPORTANCE,
                text,
                [resident.resident_id],
                data={"resident_id": resident.resident_id, "kind": wish.kind, "what": wish.what},
            ),
            at=resident.tile if not resident.away else None,
        )

    def tick(self, world: "SimulationWorld") -> None:
        """Each minute: what is wanted and is had is met, and what has waited too long is let
        go. On the hour, by day, whoever wants nothing may come to want something."""
        settings = self.settings(world)
        if not settings.enabled:
            return
        now = world.clock.total_minutes
        for resident_id, wish in list(world.wishes_of.items()):
            resident = world.residents.get(resident_id)
            if resident is None:
                del world.wishes_of[resident_id]
            elif self.met(world, resident, wish):
                self._end(world, resident, wish, met=True)
            elif now >= wish.until or (wish.kind == WITH and wish.what not in world.residents):
                self._end(world, resident, wish, met=False)
        if world.clock.minute != 0 or not settings.hours[0] <= world.clock.hour < settings.hours[1] or world.tutorial.active:
            return
        for resident in list(world.residents.values()):
            if resident.resident_id not in world.wishes_of and not resident.away:
                self._come_to(world, resident)

    # ----- seeing to it themselves -----

    def pull(self, world: "SimulationWorld", resident: Resident, candidate: "ScoredAction") -> float:
        """How much the readier a resident is to do something for its being what they want:
        to talk to whoever it is, to do the thing, to eat where there is some of it."""
        wish = world.wishes_of.get(resident.resident_id)
        if wish is None:
            return 0.0
        settings = self.settings(world)
        if wish.kind == WITH:
            return settings.pull if candidate.partner_id == wish.what else 0.0
        if wish.kind == DO:
            return settings.pull if candidate.name == wish.what else 0.0
        if wish.kind == EAT and candidate.target_id in world.containers:
            # Going to eat or drink where there is some of it, and not there for anything else.
            placed = world.interactables.get(candidate.target_id)
            use = world.definition_of(placed).use_named(candidate.name) if placed is not None else None
            wanted = world.registries.items.find(wish.what)
            if use is None or wanted is None or use.consumes != wanted.category:
                return 0.0
            held = world.containers[candidate.target_id].items
            there = any(item.definition_id == wish.what and item.owner_id in (None, resident.resident_id) for item in held)
            return settings.pull if there else 0.0
        return 0.0
