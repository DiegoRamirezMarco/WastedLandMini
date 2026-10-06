"""Building: the player proposes, somebody agrees or does not, and what was agreed goes up as
there are hands free to carry what it takes to the site and to work on it."""

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from simulation.ai.crowd import spots_taken
from simulation.ai.navigation import path_beside
from simulation.ai.utility_ai import DISTANCE_COST, ScoredAction
from simulation.events.event import DomainEvent
from simulation.events.intervention_system import BUILD_PROPOSAL
from simulation.items.item import ItemInstance
from simulation.memory.memory import Memory
from simulation.residents.activity import Activity
from simulation.residents.resident import Resident
from simulation.work.research import BUILD_PACE, NOT_KNOWN
from simulation.work.work_system import HAUL_MINUTES, PRESSING_NEED
from world.build import BUILDING_SITE, OBJECT_SITE, SITE_KINDS, BuildRule, BuildSite
from world.map import Tile
from world.pathfinding import NEIGHBOURS, find_path, manhattan
from world.urbanism import UrbanismResult

if TYPE_CHECKING:
    from simulation.world import SimulationWorld

# Working on a site, and carrying to one what it takes or fetching that from where it lies.
BUILD_ACTION = "build"
CARRY_ACTION = "carry"
BUILD_ACTIONS = (BUILD_ACTION, CARRY_ACTION)
# The advice a piece of building is put to somebody with, unless another is given.
ADVICE = "encourage"
NEEDS_BUILDING = "Eso hay que construirlo: propónselo a alguien"
NOBODY_TO_ASK = "No hay a quién proponérselo"
UNAVAILABLE = {OBJECT_SITE: "Ese tipo de objeto no está disponible", BUILDING_SITE: "Ese edificio no está disponible"}
SITE_EVENT_IMPORTANCE = 20
CARRY_EVENT_IMPORTANCE = 5
WAITING_IMPORTANCE = 30
FINISHED_IMPORTANCE = 35
SITE_NOTICE = "site:"
FINISHED_EVENT = "site_finished"
# Nobody lends a hand on something that is in the charge of someone they resent this much.
SOUR_RESENTMENT = 30.0


@dataclass(frozen=True)
class ConstructionSettings:
    """How building is gone about, whatever is being built."""

    # Units somebody carries to a site in one trip.
    carry: int = 6
    # Minutes somebody works on a site before looking up to see what else there is to do.
    stint_minutes: int = 90
    # How much whoever agreed to a site wants to get on with it, and how much anybody else does.
    in_charge_score: float = 0.45
    helping_score: float = 0.25
    # What a minute of building does to whoever is doing it.
    per_minute: dict[str, float] = field(default_factory=dict)
    # Sites in somebody's charge at which they will hear of no more, and the minutes of work at
    # which a thing is as big a job as it ever weighs.
    burden_sites: int = 3
    long_minutes: int = 480
    # What seeing a thing finished does for the mood of whoever saw to it.
    finished_mood: float = 4.0
    # How many can work on one site at a time, by what it is a site for: there is only so much room.
    hands: dict[str, int] = field(default_factory=lambda: {OBJECT_SITE: 2, BUILDING_SITE: 4})


def construction_settings_from_data(data: dict[str, Any]) -> ConstructionSettings:
    score = data.get("score", {})
    settings = ConstructionSettings(
        carry=int(data.get("carry", 6)),
        stint_minutes=int(data.get("stint_minutes", 90)),
        in_charge_score=float(score.get("in_charge", 0.45)),
        helping_score=float(score.get("helping", 0.25)),
        per_minute={str(need): float(delta) for need, delta in data.get("per_minute", {}).items()},
        burden_sites=int(data.get("burden_sites", 3)),
        long_minutes=int(data.get("long_minutes", 480)),
        finished_mood=float(data.get("finished_mood", 4.0)),
        hands={
            kind: int(data.get("hands", {}).get(kind, default))
            for kind, default in ((OBJECT_SITE, 2), (BUILDING_SITE, 4))
        },
    )
    if any(hands < 1 for hands in settings.hands.values()):
        raise ValueError("Construction needs room for at least one pair of hands at a site")
    if settings.carry < 1 or settings.stint_minutes < 1 or settings.burden_sites < 1 or settings.long_minutes < 1:
        raise ValueError("Construction needs a load, a stint, a burden and a long job of at least 1")
    if settings.in_charge_score < 0 or settings.helping_score < 0:
        raise ValueError("Construction scores must not be negative")
    return settings


class ConstructionSystem:
    # ----- what a thing takes -----

    def rule_for(self, world: "SimulationWorld", kind: str, what: str) -> BuildRule | None:
        if kind == BUILDING_SITE:
            building = world.registries.buildings.get(what)
            return building.build if building is not None else None
        definition = world.registries.interactables.find(what)
        return definition.build if definition is not None else None

    def rule_of(self, world: "SimulationWorld", site: BuildSite) -> BuildRule:
        """What a site takes. One whose definition asks for nothing any more takes nothing."""
        return self.rule_for(world, site.kind, site.what) or BuildRule()

    def thing(self, world: "SimulationWorld", kind: str, what: str) -> str | None:
        """What is being built, as it is named in a sentence. None for something no longer defined."""
        if kind == BUILDING_SITE:
            building = world.registries.buildings.get(what)
            return building.name if building is not None else None
        definition = world.registries.interactables.find(what)
        return f"{definition.article} {definition.name}" if definition is not None else None

    def is_free(self, world: "SimulationWorld", rule: BuildRule | None) -> bool:
        """Whether a thing is simply put down: it takes nothing, or the settlement is still in its
        opening, when what is put down is what came in the pack."""
        return rule is None or rule.free or world.tutorial.active

    def needs_building(self, world: "SimulationWorld", kind: str, what: str) -> bool:
        """Whether putting this down has to be proposed to somebody."""
        return self.thing(world, kind, what) is not None and not self.is_free(world, self.rule_for(world, kind, what))

    # ----- what the player does -----

    def place(self, world: "SimulationWorld", kind: str, what: str, tile: Tile) -> UrbanismResult:
        """Put something down at once. Only what is free can be, and what is known how to make."""
        unknown = self.not_known(world, kind, what)
        if unknown is not None:
            return UrbanismResult(False, unknown)
        if self.needs_building(world, kind, what):
            return UrbanismResult(False, NEEDS_BUILDING)
        if kind == BUILDING_SITE:
            return world.urbanism.place_building(world, what, tile)
        return world.urbanism.place_object(world, what, tile)

    def not_known(self, world: "SimulationWorld", kind: str, what: str) -> str | None:
        """Why this cannot be put up anywhere yet, for want of knowing how. None if it is known."""
        subject = world.research.lock_on(world, kind, what)
        return NOT_KNOWN.format(subject=subject.name) if subject is not None else None

    def site_error(self, world: "SimulationWorld", kind: str, what: str, tile: Tile) -> str | None:
        """Why this cannot be built there. None means it can."""
        if self.thing(world, kind, what) is None:
            return UNAVAILABLE[kind]
        unknown = self.not_known(world, kind, what)
        if unknown is not None:
            return unknown
        if kind == BUILDING_SITE:
            building = world.registries.buildings[what]
            return world.urbanism.building_error(world, building.width, building.height, tile)
        return world.urbanism.object_error(world, what, tile)

    def obstacle(self, world: "SimulationWorld", resident_id: str, rule: BuildRule | None) -> str | None:
        """Why a piece of building cannot be put to a resident right now. None if it can."""
        resident = world.residents.get(resident_id)
        if resident is None or BUILD_PROPOSAL not in world.registries.decisions:
            return NOBODY_TO_ASK
        if resident.away:
            return f"{resident.name} está fuera del asentamiento"
        if not world.health.is_fit_for_work(resident):
            return f"{resident.name} no está para obras"
        job = world.registries.jobs.get(rule.job or "") if rule is not None else None
        if rule is not None and rule.job is not None and resident.job_id != rule.job:
            return f"Eso lo tiene que hacer quien lleve el puesto: {job.name if job is not None else rule.job}"
        asked = world.interventions.asking_obstacle(world, resident, BUILD_PROPOSAL)
        if asked == "deciding":
            return f"{resident.name} tiene otra cosa en la cabeza"
        if asked is not None:
            return f"{resident.name} ya ha dicho que no: vuelve a intentarlo más tarde"
        return None

    def propose(
        self, world: "SimulationWorld", kind: str, what: str, tile: Tile, resident_id: str, option_id: str = ADVICE
    ) -> UrbanismResult:
        """Put it to a resident that they put something up. They weigh it and answer on the spot.

        If they agree the ground is marked out, and the result names the site. What is free is
        simply put down, with nobody asked.
        """
        thing = self.thing(world, kind, what)
        if kind not in SITE_KINDS or thing is None:
            return UrbanismResult(False, UNAVAILABLE.get(kind, NOBODY_TO_ASK))
        rule = self.rule_for(world, kind, what)
        if self.is_free(world, rule):
            return self.place(world, kind, what, tile)
        error = self.site_error(world, kind, what, tile) or self.obstacle(world, resident_id, rule)
        if error is not None:
            return UrbanismResult(False, error)
        resident = world.residents[resident_id]
        inputs = self.decision_inputs(world, resident, rule)
        if not world.interventions.propose_build(world, resident, thing, inputs, option_id):
            return UrbanismResult(False, f"{resident.name} no quiere ponerse con esa obra")
        site = self.lay(world, kind, what, tile, resident_id)
        return UrbanismResult(True, f"{resident.name} se hace cargo de la obra", site.site_id)

    def cancel(self, world: "SimulationWorld", site_id: str) -> UrbanismResult:
        """Give a site up. What had been brought to it goes to the nearest container there is."""
        site = world.sites.get(site_id)
        if site is None:
            return UrbanismResult(False, "Esa obra ya no existe")
        thing = self.thing(world, site.kind, site.what) or site.what
        nearest = world.nearest_container((site.x, site.y))
        if nearest is not None:
            for item_id, units in site.delivered.items():
                world.stock(world.containers[nearest], item_id, units, None)
        self._clear(world, site)
        world.emit_event(
            DomainEvent(
                "site_cancelled", SITE_EVENT_IMPORTANCE, f"Se abandona la obra: {thing}", data={"site_id": site_id}
            ),
            at=(site.x, site.y),
        )
        return UrbanismResult(True, "Obra abandonada")

    def decision_inputs(self, world: "SimulationWorld", resident: Resident, rule: BuildRule) -> dict[str, float]:
        """What a resident weighs about taking a piece of building on, each from 0 to 1."""
        settings = world.registries.construction
        theirs = sum(1 for site in world.sites.values() if site.in_charge == resident.resident_id)
        short = any(self._lying_about(world, tag) < units for tag, units in rule.cost.items())
        return {
            "idle": 0.0 if resident.job_id in world.registries.jobs else 1.0,
            "burden": min(1.0, theirs / settings.burden_sites),
            "effort": min(1.0, rule.minutes / settings.long_minutes),
            "short": 1.0 if short else 0.0,
        }

    # ----- sites -----

    def lay(self, world: "SimulationWorld", kind: str, what: str, tile: Tile, in_charge: str | None) -> BuildSite:
        """Mark the ground out for something that has been agreed to."""
        world.site_count += 1
        while f"site_{world.site_count}" in world.interactables:
            world.site_count += 1
        site = BuildSite(
            f"site_{world.site_count}", kind, what, tile[0], tile[1], in_charge, started_at=world.clock.total_minutes
        )
        self.measure(world, site)
        world.sites[site.site_id] = site
        world.urbanism.invalidate_routes(world, set(site.tiles))
        world.emit_event(
            DomainEvent(
                "site_laid",
                SITE_EVENT_IMPORTANCE,
                f"Se marca el sitio de una obra: {self.thing(world, kind, what)}",
                [in_charge] if in_charge is not None else [],
                data={"site_id": site.site_id},
            ),
            at=tile,
        )
        return site

    def measure(self, world: "SimulationWorld", site: BuildSite) -> bool:
        """Work out the ground a site takes up. False if what it is a site for is no longer defined."""
        if site.kind not in SITE_KINDS or self.thing(world, site.kind, site.what) is None:
            return False
        site.tiles = world.urbanism.site_tiles(world, site.kind, site.what, (site.x, site.y))
        site.blocks = site.kind == BUILDING_SITE or world.registries.interactables.get(site.what).blocks
        return True

    def lacking(self, world: "SimulationWorld", site: BuildSite) -> dict[str, int]:
        """Units a site is still waiting for, by the tag of the items that will do."""
        cost = self.rule_of(world, site).cost
        brought: dict[str, int] = {}
        for item_id, units in site.delivered.items():
            tags = world.registries.items.resolve(item_id).tags
            tag = next((tag for tag in cost if tag in tags), None)
            if tag is not None:
                brought[tag] = brought.get(tag, 0) + units
        return {tag: units - brought.get(tag, 0) for tag, units in cost.items() if units > brought.get(tag, 0)}

    def awaits(self, world: "SimulationWorld", item: ItemInstance) -> bool:
        """Whether something carried is what some site is still waiting for."""
        if not world.sites or item.owner_id is not None:
            return False
        tags = world.registries.items.resolve(item.definition_id).tags
        return any(tag in tags for site in world.sites.values() for tag in self.lacking(world, site))

    def fraction_done(self, world: "SimulationWorld", site: BuildSite) -> float:
        """How far along a site is, from 0 to 1: what has been brought and the work done, as one."""
        rule = self.rule_of(world, site)
        owed = sum(rule.cost.values())
        total = owed + rule.minutes
        if total <= 0:
            return 1.0
        brought = owed - sum(self.lacking(world, site).values())
        return max(0.0, min(1.0, (brought + min(site.progress, rule.minutes)) / total))

    def tick(self, world: "SimulationWorld") -> None:
        """Stand what is finished and had to wait for the ground to clear, and once an hour give
        notice of the sites that nothing can be done about."""
        if not world.sites:
            return
        for site in list(world.sites.values()):
            if self._ready(world, site):
                self._finish(world, site, None)
        if world.clock.minute != 0:
            return
        for site in world.sites.values():
            waiting_for = self._held_up(world, site)
            key = f"{SITE_NOTICE}{site.site_id}"
            if waiting_for is None or world.notices.get(key) == world.clock.day:
                continue
            world.notices[key] = world.clock.day
            thing = self.thing(world, site.kind, site.what)
            world.emit_event(
                DomainEvent(
                    "site_waiting",
                    WAITING_IMPORTANCE,
                    f"Una obra espera {waiting_for}: {thing}",
                    data={"site_id": site.site_id},
                )
            )

    # ----- what a resident does about them -----

    def candidate(self, world: "SimulationWorld", resident: Resident, busy: bool) -> ScoredAction | None:
        """The next thing a resident would do for a site, if they have the time and the will.

        Building is for spare time: nobody with work of their own to do right now (`busy`), a
        need that presses or no light to see by gives it a thought.
        """
        if busy or (not world.sites and not resident.inventory.items):
            return None
        if world.sites and self._free_to_build(world, resident):
            best: ScoredAction | None = None
            for site in world.sites.values():
                step = self._step(world, resident, site)
                if step is None:
                    continue
                score = self._keenness(world, resident, site) - DISTANCE_COST * manhattan(
                    resident.tile, (site.x, site.y)
                )
                if score > 0 and (best is None or score > best.score):
                    best = ScoredAction(step[0], score, step[1])
            if best is not None:
                return best
        return self._put_back(world, resident)

    def plan(self, world: "SimulationWorld", resident: Resident, candidate: ScoredAction) -> Activity | None:
        """The walk to a site, or to the container a load is fetched from or left in."""
        site = world.sites.get(candidate.target_id or "")
        if site is not None:
            path = self.path_to(world, resident, site)
            if path is None:
                return None
            stint = world.registries.construction.stint_minutes
            return Activity(candidate.name, site.site_id, path, stint if candidate.name == BUILD_ACTION else HAUL_MINUTES)
        placed = world.interactables.get(candidate.target_id or "")
        path = path_beside(world, resident, placed) if placed is not None else None
        return Activity(CARRY_ACTION, placed.object_id, path, HAUL_MINUTES) if path is not None else None

    def path_to(
        self,
        world: "SimulationWorld",
        resident: Resident,
        site: BuildSite,
        passable: Callable[[Tile], bool] | None = None,
    ) -> list[Tile] | None:
        """A short walk to a tile beside a site, or None if there is no getting next to it."""
        passable = passable or world.passable()
        marked = set(site.tiles)
        spots = {
            (x + dx, y + dy)
            for x, y in site.tiles
            for dx, dy in NEIGHBOURS
            if (x + dx, y + dy) not in marked and passable((x + dx, y + dy))
        }
        for spot in sorted(
            spots - spots_taken(world, resident), key=lambda spot: (manhattan(resident.tile, spot), spot[1], spot[0])
        ):
            path = find_path(resident.tile, spot, passable)
            if path is not None:
                return path
        return None

    def build_tick(self, world: "SimulationWorld", resident: Resident, activity: Activity) -> None:
        """Spend one minute working on a site."""
        site = world.sites.get(activity.target_id or "")
        if site is None or not self._can_work_on(world, resident, site) or not self._free_to_build(world, resident):
            self._leave(resident)
            return
        rule = self.rule_of(world, site)
        if not activity.using:
            activity.using = True
            resident.current_action = BUILD_ACTION
            self._face(resident, site)
            room = world.room_at(resident.tile)
            world.emit_event(
                DomainEvent(
                    "build_started",
                    CARRY_EVENT_IMPORTANCE,
                    f"{resident.name} se pone con la obra: {self.thing(world, site.kind, site.what)}",
                    [resident.resident_id],
                    location_id=room.room_id if room is not None else None,
                    data={"site_id": site.site_id},
                )
            )
        resident.needs.apply(world.registries.construction.per_minute)
        # Putting something up is work for the settlement like any other.
        resident.last_worked = world.clock.total_minutes
        pace = world.health.work_pace(world, resident) * world.work.mood_pace(resident)
        site.progress += pace * world.research.factor(world, BUILD_PACE)
        activity.minutes_left -= 1
        if site.progress >= rule.minutes and self._finish(world, site, resident):
            return
        if activity.minutes_left <= 0 or self._called_to_work(world, resident):
            self._leave(resident)

    def carry_tick(self, world: "SimulationWorld", resident: Resident, activity: Activity) -> None:
        """Spend one minute at the site a load was brought to, or at the container it comes from or goes back to."""
        if not activity.using:
            done = self._exchange(world, resident, activity.target_id or "")
            if resident.activity is not activity:
                # That was the last of what the site was waiting for, and it took no more than that.
                return
            if done is None:
                self._leave(resident)
                return
            activity.using = True
            resident.current_action = CARRY_ACTION
            room = world.room_at(resident.tile)
            world.emit_event(
                DomainEvent(
                    "goods_hauled",
                    CARRY_EVENT_IMPORTANCE,
                    f"{resident.name} {done}",
                    [resident.resident_id],
                    location_id=room.room_id if room is not None else None,
                )
            )
        activity.minutes_left -= 1
        if activity.minutes_left <= 0:
            self._leave(resident)

    # ----- deciding what to do -----

    def _free_to_build(self, world: "SimulationWorld", resident: Resident) -> bool:
        return (
            not world.is_dark()
            and world.health.is_fit_for_work(resident)
            and not world.activities.urgent_needs(world, resident, PRESSING_NEED)
        )

    def _called_to_work(self, world: "SimulationWorld", resident: Resident) -> bool:
        """Whether their own shift has begun, which comes before anybody's building."""
        job = world.work.job_of(world, resident)
        return (
            job is not None
            and resident.post_id in world.interactables
            and world.work.shift_minutes_left(world, resident, job) > 0
        )

    def _keenness(self, world: "SimulationWorld", resident: Resident, site: BuildSite) -> float:
        """How much a resident wants to get on with a site: whoever agreed to it most, and the
        rest as far as they feel for others. Not at all for someone they have it in for."""
        settings = world.registries.construction
        if site.in_charge == resident.resident_id:
            return settings.in_charge_score
        feelings = world.relationships.get((resident.resident_id, site.in_charge or ""))
        if feelings is not None and feelings.resentment >= SOUR_RESENTMENT:
            return 0.0
        return settings.helping_score * (0.5 + resident.personality.empathy / 100.0)

    def _can_work_on(self, world: "SimulationWorld", resident: Resident, site: BuildSite) -> bool:
        """Whether a site is ready to be worked on, and by this resident, as things stand."""
        rule = self.rule_of(world, site)
        if self.lacking(world, site) or site.progress >= rule.minutes:
            return False
        if rule.job is not None and resident.job_id != rule.job:
            return False
        at_it = sum(
            1
            for other in world.residents.values()
            if other is not resident
            and other.activity is not None
            and other.activity.action == BUILD_ACTION
            and other.activity.target_id == site.site_id
        )
        if at_it >= world.registries.construction.hands.get(site.kind, 1):
            return False
        return not self._rained_off(world, site)

    def _rained_off(self, world: "SimulationWorld", site: BuildSite) -> bool:
        return world.happenings.is_stormy(world) and not world.under_roof((site.x, site.y))

    def _step(self, world: "SimulationWorld", resident: Resident, site: BuildSite) -> tuple[str, str] | None:
        """What a resident would do next for a site, and where: carry to it, fetch for it, or work on it."""
        if self._rained_off(world, site):
            return None
        lacking = self.lacking(world, site)
        if not lacking:
            return (BUILD_ACTION, site.site_id) if self._can_work_on(world, resident, site) else None
        if any(self._carried(world, resident, tag) > 0 for tag in lacking):
            return (CARRY_ACTION, site.site_id)
        wanted = [tag for tag in lacking if self._still_to_fetch(world, tag, resident) > 0]
        source = self._source(world, resident, wanted) if wanted else None
        return (CARRY_ACTION, source) if source is not None else None

    def _put_back(self, world: "SimulationWorld", resident: Resident) -> ScoredAction | None:
        """Taking back to where things are kept what was fetched for a site that wants it no longer."""
        job = world.work.job_of(world, resident)
        if job is not None and job.expedition is not None:
            # Whoever goes outside carries what they found, and puts it away as their job has it.
            return None
        tags = [tag for tag in self._material_tags(world) if self._carried(world, resident, tag) > 0]
        if not tags:
            return None
        target = self._source(world, resident, tags) or world.nearest_container(resident.tile)
        if target is None:
            return None
        return ScoredAction(CARRY_ACTION, world.registries.construction.helping_score, target)

    # ----- what there is to build with -----

    def _fits(self, world: "SimulationWorld", item: ItemInstance, tag: str) -> bool:
        """Whether an item is nobody's and of the kind a site takes."""
        return item.owner_id is None and tag in world.registries.items.resolve(item.definition_id).tags

    def _carried(self, world: "SimulationWorld", resident: Resident, tag: str) -> int:
        return sum(item.quantity for item in resident.inventory.items if self._fits(world, item, tag))

    def _material_tags(self, world: "SimulationWorld") -> set[str]:
        """Every tag of item that something or other is built with."""
        rules = [world.registries.interactables.get(kind).build for kind in world.registries.interactables.kinds()]
        rules += [building.build for building in world.registries.buildings.values()]
        return {tag for rule in rules if rule is not None for tag in rule.cost}

    def _stores(self, world: "SimulationWorld") -> list[str]:
        """Containers that things for building may be taken from. What is for sale is bought, not taken."""
        return [
            object_id
            for object_id in world.containers
            if (placed := world.interactables.get(object_id)) is not None
            and not ((use := world.definition_of(placed).use) is not None and use.sells)
        ]

    def _lying_about(self, world: "SimulationWorld", tag: str) -> int:
        """Units of something that are to be had, less what the sites there are already wait for."""
        stored = sum(
            item.quantity
            for object_id in self._stores(world)
            for item in world.containers[object_id].items
            if self._fits(world, item, tag)
        )
        spoken_for = sum(self.lacking(world, site).get(tag, 0) for site in world.sites.values())
        return max(0, stored - spoken_for)

    def _still_to_fetch(self, world: "SimulationWorld", tag: str, resident: Resident) -> int:
        """Units all the sites together wait for that nobody else is already bringing."""
        wanted = sum(self.lacking(world, site).get(tag, 0) for site in world.sites.values())
        coming = sum(
            self._carried(world, other, tag)
            for other in world.residents.values()
            if other is not resident and other.activity is not None and other.activity.action == CARRY_ACTION
        )
        return wanted - coming

    def _source(self, world: "SimulationWorld", resident: Resident, tags: list[str]) -> str | None:
        """The nearest container that holds any of what is wanted."""
        best: tuple[int, str] | None = None
        for object_id in self._stores(world):
            if not any(self._fits(world, item, tag) for item in world.containers[object_id].items for tag in tags):
                continue
            placed = world.interactables[object_id]
            key = (manhattan(resident.tile, (placed.x, placed.y)), object_id)
            if best is None or key < best:
                best = key
        return best[1] if best is not None else None

    def _exchange(self, world: "SimulationWorld", resident: Resident, target_id: str) -> str | None:
        """Hand over, pick up or put back at what a resident has walked to. Returns what they did, if anything."""
        site = world.sites.get(target_id)
        if site is not None:
            return self._deliver(world, resident, site)
        placed = world.interactables.get(target_id)
        container = world.containers.get(target_id)
        if placed is None or container is None:
            return None
        definition = world.definition_of(placed)
        where = f"{definition.article} {definition.name}"
        settings = world.registries.construction
        taken: dict[str, int] = {}
        for tag in self._material_tags(world):
            room = min(settings.carry - sum(taken.values()), self._still_to_fetch(world, tag, resident))
            room -= self._carried(world, resident, tag)
            for item in [item for item in container.items if self._fits(world, item, tag)]:
                if room <= 0:
                    break
                units = container.take_units(item.instance_id, room)
                world.stock(resident.inventory, item.definition_id, units, None)
                taken[item.definition_id] = taken.get(item.definition_id, 0) + units
                room -= units
        if taken:
            return f"coge {self._listed(world, taken)} de {where} para una obra"
        left: dict[str, int] = {}
        for tag in self._material_tags(world):
            if self._still_to_fetch(world, tag, resident) > 0:
                continue
            for item in [item for item in resident.inventory.items if self._fits(world, item, tag)]:
                resident.inventory.remove(item.instance_id)
                world.stock(container, item.definition_id, item.quantity, None)
                left[item.definition_id] = left.get(item.definition_id, 0) + item.quantity
        return f"deja {self._listed(world, left)} en {where}" if left else None

    def _deliver(self, world: "SimulationWorld", resident: Resident, site: BuildSite) -> str | None:
        given: dict[str, int] = {}
        for tag, wanted in self.lacking(world, site).items():
            for item in [item for item in resident.inventory.items if self._fits(world, item, tag)]:
                if wanted <= 0:
                    break
                units = resident.inventory.take_units(item.instance_id, wanted)
                site.delivered[item.definition_id] = site.delivered.get(item.definition_id, 0) + units
                given[item.definition_id] = given.get(item.definition_id, 0) + units
                wanted -= units
        if not given:
            return None
        thing = self.thing(world, site.kind, site.what)
        done = f"lleva {self._listed(world, given)} a la obra: {thing}"
        if self._ready(world, site):
            self._finish(world, site, resident)
        return done

    def _listed(self, world: "SimulationWorld", units: dict[str, int]) -> str:
        return ", ".join(f"{count} de {world.registries.items.resolve(item_id).name}" for item_id, count in units.items())

    # ----- finishing -----

    def _ready(self, world: "SimulationWorld", site: BuildSite) -> bool:
        """Whether everything a site takes has been brought and done."""
        return not self.lacking(world, site) and site.progress >= self.rule_of(world, site).minutes

    def _finish(self, world: "SimulationWorld", site: BuildSite, by: Resident | None) -> bool:
        """Stand what a site was for. False if it has to wait, for somebody being on ground it will shut off."""
        tile = (site.x, site.y)
        marked = set(site.tiles)
        if site.blocks and any(not other.away and other.tile in marked for other in world.residents.values()):
            return False
        thing = self.thing(world, site.kind, site.what)
        self._clear(world, site)
        if site.kind == BUILDING_SITE:
            entity_id = world.urbanism.raise_building(world, site.what, tile)
        else:
            entity_id = world.urbanism.raise_object(world, site.what, tile)
        pleased = {site.in_charge, by.resident_id if by is not None else None}
        for resident_id in sorted(person for person in pleased if person in world.residents):
            world.residents[resident_id].adjust_mood(world.registries.construction.finished_mood)
        if site.in_charge in world.residents:
            world.memories.remember(
                site.in_charge,
                Memory(
                    text=f"Saqué adelante una obra: {thing}.",
                    importance=float(FINISHED_IMPORTANCE),
                    emotional_value=0.4,
                    tags=["construction"],
                    timestamp=world.clock.total_minutes,
                ),
            )
        world.emit_event(
            DomainEvent(
                FINISHED_EVENT,
                FINISHED_IMPORTANCE,
                f"Obra terminada: {thing}",
                [by.resident_id] if by is not None else [],
                data={"site_id": site.site_id, "entity_id": entity_id, "kind": site.kind, "what": site.what},
            ),
            at=tile,
        )
        return True

    def _clear(self, world: "SimulationWorld", site: BuildSite) -> None:
        """Take a site off the map, and everybody off it."""
        world.sites.pop(site.site_id, None)
        world.notices.pop(f"{SITE_NOTICE}{site.site_id}", None)
        for resident in world.residents.values():
            if resident.activity is not None and resident.activity.target_id == site.site_id:
                self._leave(resident)

    def _held_up(self, world: "SimulationWorld", site: BuildSite) -> str | None:
        """What a site that nobody can get on with is waiting for, as the end of a sentence. None if nothing."""
        rule = self.rule_of(world, site)
        for tag in self.lacking(world, site):
            in_hand = sum(self._carried(world, resident, tag) for resident in world.residents.values())
            stored = sum(
                item.quantity
                for object_id in self._stores(world)
                for item in world.containers[object_id].items
                if self._fits(world, item, tag)
            )
            if in_hand + stored <= 0:
                return f"material ({self._material_name(world, tag)})"
        if rule.job is not None and not any(resident.job_id == rule.job for resident in world.residents.values()):
            job = world.registries.jobs.get(rule.job)
            return f"a quien lleve el puesto ({job.name if job is not None else rule.job})"
        return None

    def _material_name(self, world: "SimulationWorld", tag: str) -> str:
        items = world.registries.items
        return next((items.get(item_id).name for item_id in items.ids() if tag in items.get(item_id).tags), tag)

    def _leave(self, resident: Resident) -> None:
        resident.activity = None
        resident.current_action = "idle"

    def _face(self, resident: Resident, site: BuildSite) -> None:
        nearest = min(site.tiles, key=lambda tile: (manhattan(resident.tile, tile), tile), default=(site.x, site.y))
        dx, dy = nearest[0] - resident.x, nearest[1] - resident.y
        if dx or dy:
            resident.facing = ("right" if dx > 0 else "left") if abs(dx) >= abs(dy) else ("down" if dy > 0 else "up")
