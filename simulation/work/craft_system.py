"""A trade as it is lived (S47): time at a job adds up to levels, each level brings something
new, and what somebody has come to is theirs to make and to show to others.

The game works out what a new thing is like, always the same for the same settlement and
thing. What it is called, and what is picked of it, is the player's to say: until they do it
waits, and nobody makes it. Whoever came to it knows how, and whoever holds the same job
learns it by being near them long enough. If the last who knew goes without showing anybody,
it is lost: the thing is still what it was, and nobody makes more.
"""

import math
from collections.abc import Mapping
from dataclasses import replace
from typing import TYPE_CHECKING, Any

from simulation.economy.ledger import MADE
from simulation.events.event import DomainEvent
from simulation.items.registry import ItemRegistry
from simulation.memory.memory import Memory
from simulation.residents.attributes import MIND
from simulation.residents.resident import Resident
from simulation.rng import SimulationRNG
from simulation.work.craft import (
    MAKING_JOBS,
    RAW_FOOD,
    CraftResult,
    CraftSettings,
    Discovery,
    KindDefinition,
    OptionDefinition,
    Product,
    article_for,
)
from simulation.work.job import JobDefinition
from world.interactable import Interactable
from world.pathfinding import manhattan

if TYPE_CHECKING:
    from simulation.world import SimulationWorld

LEVEL_EVENT = "trade_level"
LEVEL_IMPORTANCE = 40
FOUND_EVENT = "discovery_made"
FOUND_IMPORTANCE = 60
NAMED_EVENT = "discovery_named"
NAMED_IMPORTANCE = 55
TAUGHT_EVENT = "trade_taught"
TAUGHT_IMPORTANCE = 40
LOST_EVENT = "trade_lost"
LOST_IMPORTANCE = 50
MADE_EVENT = "thing_made"
MADE_IMPORTANCE = 10
LEARNED_MEMORY = 50.0
# Minutes apart at which it is looked into who is near enough somebody to be learning from them.
TEACH_EVERY = 10
# The tag a food has once it is a dish, and so is not what a dish is made of.
COOKED_TAG = "cooked"
FOOD_CATEGORY = "food"
# The choice of a dish that says what it is made of, and of a tool that says what job it is for.
FROM_CHOICE, FOR_CHOICE = "from", "for"
# The choice of a crop that says how it grows, which is what is seen of it where it grows.
GROWS_CHOICE = "grows"
TOOL_TAG = "tool_"


def tool_tag(job_id: str) -> str:
    """The tag of a tool that was made for a job."""
    return f"{TOOL_TAG}{job_id}"


class CraftSystem:
    def settings(self, world: "SimulationWorld") -> CraftSettings:
        return world.registries.crafts

    def kind_of(self, world: "SimulationWorld", job_id: str | None) -> KindDefinition | None:
        """The kind of thing a job teaches, if it teaches any."""
        settings = self.settings(world)
        return settings.kinds.get(settings.jobs.get(job_id or "", ""))

    # ----- levels -----

    def level(self, world: "SimulationWorld", resident: Resident, job_id: str | None) -> int:
        """A resident's level at a job, from 1: how many marks the time they have at it is past."""
        minutes = resident.trade.get(job_id or "", 0.0)
        return max(1, sum(1 for mark in self.settings(world).levels if minutes >= mark))

    def progress(self, world: "SimulationWorld", resident: Resident, job_id: str | None) -> float:
        """How far a resident is from their level at a job to the next, from 0 to 1. 1 at the top."""
        levels = self.settings(world).levels
        level = self.level(world, resident, job_id)
        if level >= len(levels):
            return 1.0
        minutes = resident.trade.get(job_id or "", 0.0)
        return max(0.0, min(1.0, (minutes - levels[level - 1]) / (levels[level] - levels[level - 1])))

    def pace(self, world: "SimulationWorld", resident: Resident, job: JobDefinition) -> float:
        """How much faster a resident does a job for the level they are at it."""
        return 1.0 + self.settings(world).pace * (self.level(world, resident, job.job_id) - 1)

    def worked(self, world: "SimulationWorld", resident: Resident, job: JobDefinition, minutes: float = 1.0) -> None:
        """Count time at a job towards a resident's level at it: a good head learns sooner.
        Each level reached is said, and brings something new if the job teaches anything."""
        settings = self.settings(world)
        if len(settings.levels) < 2:
            return
        before = self.level(world, resident, job.job_id)
        gained = minutes * world.attributes.factor(world, resident, MIND, "learning")
        resident.trade[job.job_id] = resident.trade.get(job.job_id, 0.0) + gained
        if before >= settings.top:
            return
        for level in range(before + 1, self.level(world, resident, job.job_id) + 1):
            self._levelled(world, resident, job, level)

    def _levelled(self, world: "SimulationWorld", resident: Resident, job: JobDefinition, level: int) -> None:
        world.emit_event(
            DomainEvent(
                LEVEL_EVENT,
                LEVEL_IMPORTANCE,
                f"{resident.name} llega al nivel {level} de {job.name.lower()}",
                [resident.resident_id],
                data={"resident_id": resident.resident_id, "job": job.job_id, "level": level},
            )
        )
        # A job done out there brings the next stretch of country with each level (S68).
        world.expeditions.levelled(world, resident, job, level)
        kind = self.kind_of(world, job.job_id)
        if kind is None:
            return
        world.discovery_count += 1
        discovery = Discovery(
            discovery_id=f"discovery_{world.discovery_count}",
            kind=kind.kind_id,
            job_id=job.job_id,
            by=resident.resident_id,
            by_name=resident.name,
            level=level,
            day=world.clock.day,
        )
        world.discoveries[discovery.discovery_id] = discovery
        world.emit_event(
            DomainEvent(
                FOUND_EVENT,
                FOUND_IMPORTANCE,
                f"{resident.name} {kind.learned} algo nuevo: falta decir qué es",
                [resident.resident_id],
                data={
                    "discovery": discovery.discovery_id, "resident_id": resident.resident_id, "job": job.job_id,
                    "kind": kind.kind_id, "level": level,
                },
            )
        )

    # ----- what waits to be named, and naming it -----

    def waiting(self, world: "SimulationWorld") -> list[Discovery]:
        """What the player has not named yet, oldest first: what residents who are still here
        have come to at their jobs, and what has been found (S59), whoever found it."""
        return [
            discovery
            for discovery in world.discoveries.values()
            if not discovery.named and (discovery.by in world.residents or discovery.source)
        ]

    def kind_for(self, world: "SimulationWorld", discovery: Discovery) -> KindDefinition | None:
        """The kind of thing a discovery is: one a job teaches, or, for what was found, one
        of those there are to find."""
        kinds = world.registries.finds.kinds if discovery.source else self.settings(world).kinds
        return kinds.get(discovery.kind)

    def preview(self, world: "SimulationWorld", discovery: Discovery) -> dict[str, Any] | None:
        """The item a discovery will be, as the game has settled it, before it has a name:
        with the first of whatever there is to pick. None for what is no thing."""
        kind = self.kind_for(world, discovery)
        if kind is None or kind.item is None:
            return None
        picked = {choice_id: options[0] for choice_id, options in self.options(world, discovery).items() if options}
        return self._item_data(world, discovery, kind, picked)

    def options(self, world: "SimulationWorld", discovery: Discovery) -> dict[str, list[OptionDefinition]]:
        """What there is to pick for a discovery, by choice ID, as things stand."""
        kind = self.kind_for(world, discovery)
        if kind is None:
            return {}
        found: dict[str, list[OptionDefinition]] = {}
        for choice_id, choice in kind.choices.items():
            if choice.source == RAW_FOOD:
                items = world.registries.items
                found[choice_id] = [
                    OptionDefinition(item_id, _capital(items.get(item_id).name))
                    for item_id in items.ids()
                    if items.get(item_id).category == FOOD_CATEGORY and COOKED_TAG not in items.get(item_id).tags
                ]
            elif choice.source == MAKING_JOBS:
                found[choice_id] = [
                    OptionDefinition(job_id, job.name)
                    for job_id, job in world.registries.jobs.items()
                    if job.produces is not None or job.research
                ]
            else:
                found[choice_id] = list(choice.options.values())
        return found

    def name(
        self, world: "SimulationWorld", discovery_id: str, name: str, choices: Mapping[str, str] | None = None
    ) -> CraftResult:
        """Say what a discovery is: what it is called, and what is picked of it. What is left
        unpicked is the first there is to pick. From then on whoever came to it makes it."""
        settings = self.settings(world)
        discovery = world.discoveries.get(discovery_id)
        if discovery is None:
            return CraftResult(False, "No hay tal cosa que nombrar")
        if discovery.named:
            return CraftResult(False, f"Eso ya se llama {discovery.name}", discovery_id)
        kind = self.kind_for(world, discovery)
        if kind is None:
            return CraftResult(False, "Ya no hay manera de hacer una cosa así", discovery_id)
        name = " ".join(str(name).split())[: settings.name_length].strip()
        if not name:
            return CraftResult(False, "Tiene que llamarse de alguna manera", discovery_id)
        taken = {other.name.lower() for other in world.discoveries.values() if other.named}
        taken.update(world.registries.items.get(item_id).name.lower() for item_id in world.registries.items.ids())
        if name.lower() in taken:
            return CraftResult(False, f"Ya hay algo que se llama {name}", discovery_id)
        picked: dict[str, OptionDefinition] = {}
        for choice_id, options in self.options(world, discovery).items():
            if not options:
                return CraftResult(False, f"No hay de qué elegir: {kind.choices[choice_id].name.lower()}", discovery_id)
            wanted = (choices or {}).get(choice_id)
            option = next((each for each in options if each.option_id == wanted), None)
            if wanted is not None and option is None:
                return CraftResult(False, f"No se puede elegir eso: {kind.choices[choice_id].name.lower()}", discovery_id)
            picked[choice_id] = option or options[0]
        discovery.name = name
        discovery.choices = {choice_id: option.option_id for choice_id, option in picked.items()}
        if kind.item is not None:
            try:
                discovery.item = self._item_data(world, discovery, kind, picked)
                self.register(world, discovery)
            except ValueError as error:
                discovery.name, discovery.choices, discovery.item = "", {}, {}
                return CraftResult(False, f"No sale nada que sirva: {error}", discovery_id)
            discovery.item_id = discovery.item["id"]
        if discovery.source:
            # It was found, and nobody makes it: what there is of it is brought in (S59).
            world.emit_event(
                DomainEvent(
                    NAMED_EVENT,
                    NAMED_IMPORTANCE,
                    f"Lo que nadie conocía ya tiene nombre: {name}",
                    [discovery.by] if discovery.by in world.residents else [],
                    data={
                        "discovery": discovery_id, "resident_id": discovery.by, "kind": kind.kind_id,
                        "item": discovery.item_id, "name": name, "source": discovery.source,
                    },
                )
            )
            world.finds.named(world, discovery)
            return CraftResult(True, f"Se llama {name}", discovery_id)
        maker = world.residents.get(discovery.by)
        if maker is not None:
            maker.makes[discovery_id] = world.clock.day
            text = f"{maker.name} {kind.learned} {name}"
            world.memories.remember(
                maker.resident_id,
                Memory(f"Di con algo mío en el trabajo: {name}.", LEARNED_MEMORY, 0.6, [], ["trade"], world.clock.total_minutes),
            )
            world.emit_event(
                DomainEvent(
                    NAMED_EVENT,
                    NAMED_IMPORTANCE,
                    text,
                    [maker.resident_id],
                    data={
                        "discovery": discovery_id, "resident_id": maker.resident_id, "kind": kind.kind_id,
                        "item": discovery.item_id, "name": name, "choices": dict(discovery.choices),
                    },
                ),
                at=maker.tile if not maker.away else None,
                fact_text=f"{maker.name} sabe hacer algo nuevo: {name}" if not maker.away else None,
            )
        return CraftResult(True, f"Se llama {name}", discovery_id)

    def _item_data(
        self, world: "SimulationWorld", discovery: Discovery, kind: KindDefinition, picked: Mapping[str, OptionDefinition]
    ) -> dict[str, Any]:
        """The definition of the item a discovery is, as a pack would give it: what the kind
        makes of it, with what was picked laid over, and better for the level it was come to at."""
        settings = self.settings(world)
        own = SimulationRNG.keyed(world.rng.seed, "discovery", discovery.discovery_id)
        spec: dict[str, Any] = {"tags": [], "effects": {}, "properties": {}, "preference_tags": []}
        for part in (kind.item or {}, *(option.item for option in picked.values())):
            _lay_over(spec, part)
        better = 1.0 + settings.better * max(0, discovery.level - 2)
        effects = {need: round(_settle(own, value) * better, 1) for need, value in spec["effects"].items()}
        properties = {name: _settle(own, value) for name, value in spec["properties"].items()}
        tastes = list(spec["preference_tags"])
        left = [tag for tag in settings.flavours if tag not in tastes]
        for _ in range(min(int(spec.get("flavours", 0)), len(left))):
            tastes.append(left.pop(own.randint(0, len(left) - 1)))
        tags = list(spec["tags"])
        made_of = world.registries.items.find(discovery.choices.get(FROM_CHOICE, ""))
        if made_of is not None:
            # A dish tastes of what it is made of.
            tastes += [tag for tag in made_of.preference_tags[:1] if tag not in tastes]
        if discovery.choices.get(FOR_CHOICE) in world.registries.jobs:
            tags.append(tool_tag(discovery.choices[FOR_CHOICE]))
        item_id = f"{kind.kind_id}_{discovery.discovery_id.rsplit('_', 1)[-1]}"
        while world.registries.items.find(item_id) is not None:
            item_id += "_x"
        data: dict[str, Any] = {
            "id": item_id,
            "name": discovery.name,
            "article": article_for(discovery.name),
            "category": str(spec["category"]),
            "base_value": max(0, round(_settle(own, spec.get("value", 0)) * better)),
            "description": (
                world.finds.told(world, discovery) if discovery.source else f"{_capital(kind.name)} de {discovery.by_name}."
            ),
            "tags": tags,
            "effects": effects,
            "properties": properties,
            "preference_tags": tastes,
            # What is fresh goes off as fast as its kind does (S65).
            "spoils": float(spec.get("spoils", 0.0)),
        }
        if spec.get("substance"):
            data["substance"] = spec["substance"]
        return data

    def register(self, world: "SimulationWorld", discovery: Discovery) -> None:
        """Have the settlement's items include the one a discovery is. The game's own
        definitions are shared between settlements, so this one gets a list of its own."""
        if not discovery.item or world.registries.items.find(str(discovery.item.get("id", ""))) is not None:
            return
        items = ItemRegistry()
        for item_id in world.registries.items.ids():
            items.register(world.registries.items.get(item_id))
        items.load_mapping(discovery.item, source=discovery.discovery_id)
        world.registries = _with_items(world.registries, items)

    def restore(self, world: "SimulationWorld") -> None:
        """Put back the items of everything that was named, as when a save is loaded."""
        for discovery in world.discoveries.values():
            if discovery.named and discovery.item:
                try:
                    self.register(world, discovery)
                except ValueError:
                    # What no longer makes an item is kept as a name, and nobody makes it.
                    discovery.item_id = None

    # ----- making what has been come to -----

    def known(self, world: "SimulationWorld", resident: Resident, job_id: str | None) -> list[Discovery]:
        """What a resident knows how to make, or where to go, of the kind a job teaches."""
        kind = self.kind_of(world, job_id)
        if kind is None or not resident.makes:
            return []
        return [
            discovery
            for discovery_id in resident.makes
            if (discovery := world.discoveries.get(discovery_id)) is not None
            and discovery.named
            and discovery.kind == kind.kind_id
        ]

    def products(self, world: "SimulationWorld", resident: Resident, job: JobDefinition) -> list[Product]:
        """The things a resident knows how to make at a job beyond what the job gives anybody."""
        kind = self.kind_of(world, job.job_id)
        if kind is None or not resident.makes:
            return []
        made = []
        for discovery in self.known(world, resident, job.job_id):
            if discovery.item_id is None or world.registries.items.find(discovery.item_id) is None:
                continue
            every, batch, ripens = kind.every_minutes, kind.batch, 0
            for choice_id, option_id in discovery.choices.items():
                choice = kind.choices.get(choice_id)
                option = choice.options.get(option_id) if choice is not None else None
                if option is not None:
                    every = option.every_minutes or every
                    batch = option.batch or batch
                    ripens = max(ripens, option.ripens_days)
            needs = discovery.choices.get(FROM_CHOICE) if FROM_CHOICE in kind.choices else None
            ripe = world.clock.day - resident.makes[discovery.discovery_id] >= ripens
            made.append(Product(discovery.discovery_id, discovery.item_id, every, batch, needs, ripe))
        return made

    def family(self, world: "SimulationWorld", job_id: str | None) -> tuple[str, ...]:
        """Every item anybody has come to of the kind a job teaches, whoever knows how to make it."""
        kind = self.kind_of(world, job_id)
        if kind is None or not world.discoveries:
            return ()
        return tuple(
            discovery.item_id
            for discovery in world.discoveries.values()
            if discovery.kind == kind.kind_id and discovery.item_id is not None
        )

    def grown_at(self, world: "SimulationWorld", post_id: str) -> str | None:
        """How what is grown at a post is grown, for it to be seen there: the way of the crop
        its worker learned last. None where nothing is grown but what anybody grows."""
        if not world.discoveries:
            return None
        last: tuple[tuple[int, int], str] | None = None
        for resident in world.residents.values():
            if resident.post_id != post_id or not resident.makes:
                continue
            for discovery in self.known(world, resident, resident.job_id):
                way = discovery.choices.get(GROWS_CHOICE)
                number = discovery.discovery_id.rsplit("_", 1)[-1]
                when = (resident.makes[discovery.discovery_id], int(number) if number.isdigit() else 0)
                if way is not None and (last is None or when > last[0]):
                    last = (when, way)
        return last[1] if last is not None else None

    def extra_items(self, world: "SimulationWorld", resident: Resident) -> tuple[str, ...]:
        """The items a resident's job has them make beyond the job's own, to be carried with them."""
        job = world.registries.jobs.get(resident.job_id or "")
        if job is None or not resident.makes:
            return ()
        return tuple(product.item_id for product in self.products(world, resident, job))

    def craft(self, world: "SimulationWorld", resident: Resident, job: JobDefinition, placed: Interactable) -> None:
        """One minute at a post that makes nothing of its own, towards the next of what its
        worker has come to: whichever the settlement has least of, while it has too few."""
        kind = self.kind_of(world, job.job_id)
        ready = [product for product in self.products(world, resident, job) if product.ripe]
        if kind is None or not ready:
            return
        product = min(ready, key=lambda each: (self._kept(world, each.item_id), each.item_id))
        if self._kept(world, product.item_id) >= kind.max_stock:
            return
        target = self._store(world, kind, placed)
        if target is None:
            return
        speed = world.health.work_pace(world, resident) * world.work.mood_pace(resident)
        speed *= world.attributes.work_pace(world, resident, job) * self.pace(world, resident, job)
        speed *= world.rush.pace(world, resident)
        needed = math.ceil(product.every_minutes / max(0.1, speed))
        resident.work_needed = needed
        resident.work_progress = min(resident.work_progress + 1, needed)
        if resident.work_progress < needed:
            return
        resident.work_progress = 0
        world.stock(world.containers[target], product.item_id, product.batch, None, placed.level)
        world.ledger.record(world, product.item_id, product.batch, MADE, job.job_id, resident.resident_id, placed.object_id)
        definition = world.registries.items.resolve(product.item_id)
        world.emit_event(
            DomainEvent(
                MADE_EVENT,
                MADE_IMPORTANCE,
                f"{resident.name} termina {definition.article} {definition.name}",
                [resident.resident_id],
                data={"item": product.item_id, "container": target},
            )
        )
        world.rush.after_unit(world, resident, job, placed)

    def _kept(self, world: "SimulationWorld", item_id: str) -> int:
        """Units of a thing lying in the settlement's containers."""
        return sum(inventory.count(item_id) for inventory in world.containers.values())

    def store(self, world: "SimulationWorld", kind: KindDefinition, placed: Interactable) -> str | None:
        """The container that what is made at a post is kept in. None if there is nowhere."""
        return self._store(world, kind, placed)

    def _store(self, world: "SimulationWorld", kind: KindDefinition, placed: Interactable) -> str | None:
        """Where what is made at a post is kept: the nearest container of the kind for it, the
        post itself if it holds things, or the nearest container of any kind."""
        of_kind = [
            world.interactables[object_id]
            for object_id in world.containers
            if object_id in world.interactables and world.interactables[object_id].kind == kind.into
        ]
        if of_kind:
            at = (placed.x, placed.y)
            return min(of_kind, key=lambda each: (manhattan(at, (each.x, each.y)), each.object_id)).object_id
        if placed.object_id in world.containers:
            return placed.object_id
        return world.nearest_container((placed.x, placed.y))

    def destination(self, world: "SimulationWorld", resident: Resident) -> tuple[Discovery, OptionDefinition] | None:
        """Where a resident who knows of places outside goes today, and what is brought from
        there: each in its turn, and a day in between for wherever their feet take them."""
        kind = self.kind_of(world, resident.job_id)
        places = [discovery for discovery in self.known(world, resident, resident.job_id) if discovery.item_id is None]
        if kind is None or not places:
            return None
        turn = world.clock.day % (len(places) + 1)
        if turn == 0:
            return None
        place = places[turn - 1]
        for choice_id, option_id in place.choices.items():
            choice = kind.choices.get(choice_id)
            option = choice.options.get(option_id) if choice is not None else None
            if option is not None and option.fetch is not None:
                return place, option
        return None

    # ----- showing it to others, and losing it -----

    def tick(self, world: "SimulationWorld") -> None:
        """Every so often, whoever holds a job and is near somebody who knows a thing of it
        that they do not is that much nearer knowing it too."""
        if world.clock.minute % TEACH_EVERY or not world.discoveries:
            return
        settings = self.settings(world)
        for learner in list(world.residents.values()):
            kind = self.kind_of(world, learner.job_id)
            if kind is None or learner.away or not world.is_aware(learner):
                continue
            for discovery in world.discoveries.values():
                if not discovery.named or discovery.kind != kind.kind_id or discovery.discovery_id in learner.makes:
                    continue
                teacher = self._teacher(world, learner, discovery)
                if teacher is None:
                    continue
                gained = TEACH_EVERY * world.attributes.factor(world, learner, MIND, "learning")
                learner.lessons[discovery.discovery_id] = learner.lessons.get(discovery.discovery_id, 0.0) + gained
                if learner.lessons[discovery.discovery_id] >= settings.teach_minutes:
                    self._learned(world, learner, teacher, discovery, kind)

    def _teacher(self, world: "SimulationWorld", learner: Resident, discovery: Discovery) -> Resident | None:
        reach = self.settings(world).teach_reach
        near = [
            resident
            for resident in world.residents.values()
            if resident is not learner
            and discovery.discovery_id in resident.makes
            and not resident.away
            and world.is_aware(resident)
            and manhattan(resident.tile, learner.tile) <= reach
        ]
        return min(near, key=lambda each: (manhattan(each.tile, learner.tile), each.resident_id)) if near else None

    def _learned(
        self, world: "SimulationWorld", learner: Resident, teacher: Resident, discovery: Discovery, kind: KindDefinition
    ) -> None:
        learner.makes[discovery.discovery_id] = world.clock.day
        learner.lessons.pop(discovery.discovery_id, None)
        now = world.clock.total_minutes
        world.memories.remember(
            learner.resident_id,
            Memory(f"{teacher.name} me enseñó lo suyo: {discovery.name}.", LEARNED_MEMORY, 0.4, [teacher.resident_id], ["trade"], now),
        )
        world.relationship(learner.resident_id, teacher.resident_id).adjust("trust", 4.0)
        text = f"{teacher.name} enseña a {learner.name} lo que sabe: {discovery.name}"
        world.emit_event(
            DomainEvent(
                TAUGHT_EVENT,
                TAUGHT_IMPORTANCE,
                text,
                [teacher.resident_id, learner.resident_id],
                data={"discovery": discovery.discovery_id, "teacher": teacher.resident_id, "learner": learner.resident_id},
            ),
            at=learner.tile,
        )

    def knowers(self, world: "SimulationWorld", discovery_id: str) -> list[Resident]:
        """Whoever in the settlement knows how to make a thing."""
        return [resident for resident in world.residents.values() if discovery_id in resident.makes]

    def gone(self, world: "SimulationWorld", resident: Resident) -> None:
        """Somebody has left the settlement for good: what only they knew is lost with them,
        and what they had come to and nobody had named is forgotten."""
        for discovery_id in list(resident.makes):
            discovery = world.discoveries.get(discovery_id)
            if discovery is None or not discovery.named or self.knowers(world, discovery_id):
                continue
            world.emit_event(
                DomainEvent(
                    LOST_EVENT,
                    LOST_IMPORTANCE,
                    f"Con {resident.name} se pierde lo que sabía: {discovery.name}",
                    data={"discovery": discovery_id, "resident_id": resident.resident_id, "item": discovery.item_id},
                )
            )
        forgotten = [
            each.discovery_id
            for each in world.discoveries.values()
            # What was found for everybody is still at the gate, whoever found it.
            if not each.named and each.by == resident.resident_id and (not each.source or each.owner == resident.resident_id)
        ]
        for discovery_id in forgotten:
            del world.discoveries[discovery_id]


def _capital(text: str) -> str:
    return text[:1].upper() + text[1:]


def _settle(own: SimulationRNG, value: Any) -> float:
    """A number, or one between the two of a pair: a whole one if both are."""
    if isinstance(value, (list, tuple)) and len(value) == 2:
        low, high = value
        if isinstance(low, int) and isinstance(high, int):
            return own.randint(min(low, high), max(low, high))
        return round(float(low) + own.random() * (float(high) - float(low)), 2)
    return value if isinstance(value, int) else float(value)


def _lay_over(spec: dict[str, Any], part: Mapping[str, Any]) -> None:
    """Lay parts of an item over what there is of it: lists grow, the rest is written over."""
    for name, value in part.items():
        if name in ("tags", "preference_tags"):
            spec[name] += [str(tag) for tag in value if tag not in spec[name]]
        elif name in ("effects", "properties"):
            spec[name].update(value)
        elif name == "substance":
            merged = dict(spec.get("substance", {}))
            for key, given in value.items():
                merged[key] = {**merged.get(key, {}), **given} if key == "per_minute" else given
            spec["substance"] = merged
        else:
            spec[name] = value


def _with_items(registries: Any, items: ItemRegistry) -> Any:
    return replace(registries, items=items)
