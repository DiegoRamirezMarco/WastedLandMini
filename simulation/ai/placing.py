"""Picked up and put down: where the player lets go of a resident is what they set about (S51).

It is the order of affecting a resident (S37) given another way: by where they are put, and
not by what is said to them. They are there at once, and what they are put down on says what
they do: at a place of work they work, or it is their post from then on; what is used, they
use; what can be taken apart, they take apart; a site is theirs to see to; a building, they
are inside; beside somebody, it is for the player to say what the two do. Where what they are
put on can mean more than one thing, they stand there until told which.

Nothing here knows of a screen: who, where, and on what or on whom, by stable IDs.
"""

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Callable

from simulation.ai.affect import LEISURE, SALVAGE, TAKE_CHARGE, TASK, TO_POST, USE_THING
from simulation.ai.crowd import spots_taken
from simulation.events.event import DomainEvent
from simulation.residents.activity import SERVE_ACTION
from simulation.residents.resident import Resident
from simulation.work.job import JobDefinition
from world.interactable import Interactable, UseDefinition
from world.map import Tile
from world.pathfinding import NEIGHBOURS, manhattan
from world.room import Room

if TYPE_CHECKING:
    from simulation.world import SimulationWorld

# What somebody can be put down on.
GROUND, OBJECT, RESIDENT, SITE, ROOM, CHILD = "ground", "object", "resident", "site", "room", "child"
ON_KINDS = (GROUND, OBJECT, RESIDENT, SITE, ROOM, CHILD)
# What comes of it: being there and no more, using the thing, working at their post, taking a
# post, taking the thing apart, seeing to a site, being inside, something with somebody that
# is still to be said, passing the time beside it, taking a child up, or one of several
# things that is still to be said.
STAY, USE, WORK, POST, TAKE_APART, BUILD, ENTER, WITH, PASTIME, TAKE_UP, CHOOSE = (
    "stay", "use", "work", "post", "salvage", "build", "enter", "with", "pastime", "take_up", "choose",
)
PLACED_EVENT = "resident_placed"
POST_LOST_EVENT = "post_lost"
PLACED_IMPORTANCE = 15
POST_LOST_IMPORTANCE = 40

NAMES = {USE: "Usar", WORK: "Trabajar", POST: "Darle el puesto", TAKE_APART: "Desguazar", PASTIME: "Quedarse un rato"}
NO_ROOM = "No hay sitio donde dejarle ahí"
SERVING = "{name} cumple condena: de ahí no se le mueve"
OFF_HOURS = "No es su hora de trabajar"
NOBODY_SERVING = "No hay nadie atendiendo"
NOT_THEIRS = "No es para {name}"
CANNOT_PAY = "No le llega para pagarlo"
NOTHING_LEFT = "No queda nada"
FULL = "Ya no cabe nadie más"
IN_CHARGE = "Ya se encarga de esa obra"
NOT_FIT = "{name} no está para eso"
TO_EMPTY = "Hay que vaciarlo antes"
ASLEEP = "{name} duerme"
GONE = "Ya no está"
NOTHING_WITH = "Con {name} no tiene nada que hacer ahora"
LOCKED = "{room} está cerrada con llave"


@dataclass(frozen=True)
class PlacingSettings:
    # How many tiles from where somebody is let go a free one is looked for to stand them on.
    reach: int = 4
    # The pastime somebody is left at beside a thing there is nothing else to do with.
    otherwise: str = "sit"
    # What is said of using a thing before it is done, by the action of its use, with
    # `{thing}` where it is named; and what is said of any other.
    uses: dict[str, str] = field(default_factory=dict)
    use: str = "usará {thing}"


def placing_settings_from_data(data: dict[str, Any]) -> PlacingSettings:
    defaults = PlacingSettings()
    settings = PlacingSettings(
        reach=int(data.get("reach", defaults.reach)),
        otherwise=str(data.get("otherwise", defaults.otherwise)),
        uses={str(action): str(said) for action, said in data.get("uses", {}).items()},
        use=str(data.get("use", defaults.use)),
    )
    if settings.reach < 1:
        raise ValueError("Somebody is put down within a tile or more of where they are let go")
    return settings


@dataclass(frozen=True)
class Placing:
    """One thing that would come of putting somebody down somewhere."""

    does: str
    # What it is called where there are several to choose among, and what is said of it
    # before it is done.
    name: str
    text: str
    # Why it cannot be done as things stand. Empty for what can.
    reason: str = ""

    @property
    def open(self) -> bool:
        return not self.reason


@dataclass(frozen=True)
class Foreseen:
    """What letting go of somebody over something would do, before it is done."""

    # Whether they can be put down there at all.
    ok: bool
    # What comes of it: one of the things above, `choose` where there are several, `stay`
    # where there is nothing but being there.
    does: str
    text: str
    # Where they would stand.
    tile: Tile | None = None
    # What there is to choose among, where there is more than one thing.
    choices: tuple[Placing, ...] = ()


@dataclass(frozen=True)
class PlacingResult:
    ok: bool
    message: str
    does: str = STAY
    # Who or what it was on, where the player has still to say what comes of it.
    detail: str | None = None
    choices: tuple[Placing, ...] = ()


class PlacingSystem:
    # ----- whether somebody can be picked up -----

    def obstacle(self, world: "SimulationWorld", resident_id: str) -> str | None:
        """Why a resident cannot be picked up and put down right now. None if they can."""
        error = world.affect.obstacle(world, resident_id)
        if error is not None:
            return error
        resident = world.residents[resident_id]
        if resident.activity is not None and resident.activity.action == SERVE_ACTION:
            return SERVING.format(name=resident.name)
        return None

    # ----- what would come of it -----

    def foresee(
        self, world: "SimulationWorld", resident_id: str, tile: Tile, on_kind: str = GROUND, on_id: str | None = None
    ) -> Foreseen:
        """What putting a resident down there would do, with nothing done."""
        error = self.obstacle(world, resident_id)
        if error is not None:
            return Foreseen(False, STAY, error)
        resident = world.residents[resident_id]
        spot = self._spot(world, resident, tile, on_kind, on_id)
        if spot is None:
            return Foreseen(False, STAY, NO_ROOM)
        found = self.choices(world, resident_id, on_kind, on_id)
        open_ones = tuple(each for each in found if each.open)
        if len(open_ones) > 1:
            return Foreseen(True, CHOOSE, f"{resident.name}, {self._named(world, on_kind, on_id)}: elige qué", spot, open_ones)
        if open_ones:
            return Foreseen(True, open_ones[0].does, f"{resident.name} {open_ones[0].text}", spot, open_ones)
        why = next((each.reason for each in found if each.reason), "")
        text = f"{resident.name} se quedará aquí"
        return Foreseen(True, STAY, f"{text} ({why[0].lower()}{why[1:]})" if why else text, spot)

    def choices(self, world: "SimulationWorld", resident_id: str, on_kind: str, on_id: str | None) -> list[Placing]:
        """Everything that being put down on something could come to for a resident, what
        cannot be done as things stand too, with why not. Empty for bare ground."""
        resident = world.residents.get(resident_id)
        if resident is None:
            return []
        if on_kind == OBJECT and on_id in world.interactables:
            return self._on_object(world, resident, world.interactables[on_id])
        if on_kind == RESIDENT:
            return [self._with(world, resident, on_id)]
        if on_kind == SITE:
            return [self._on_site(world, resident, on_id)]
        if on_kind == ROOM and on_id in world.rooms:
            return [self._into(world, resident, world.rooms[on_id])]
        if on_kind == CHILD:
            return [self._child(world, resident, on_id)]
        return []

    def _named(self, world: "SimulationWorld", on_kind: str, on_id: str | None) -> str:
        placed = world.interactables.get(on_id or "") if on_kind == OBJECT else None
        return world.definition_of(placed).name.lower() if placed is not None else ""

    def _thing(self, world: "SimulationWorld", placed: Interactable) -> str:
        definition = world.definition_of(placed)
        return f"{definition.article} {definition.name.lower()}"

    def _job_at(self, world: "SimulationWorld", placed: Interactable) -> JobDefinition | None:
        """The job that is worked at a thing, if it is the station of one."""
        return next((job for job in world.registries.jobs.values() if job.station == placed.kind), None)

    def _holder(self, world: "SimulationWorld", object_id: str) -> Resident | None:
        return next((each for each in world.residents.values() if each.post_id == object_id), None)

    def _on_object(self, world: "SimulationWorld", resident: Resident, placed: Interactable) -> list[Placing]:
        settings = world.registries.placing
        definition = world.definition_of(placed)
        thing = self._thing(world, placed)
        found: list[Placing] = []
        job = self._job_at(world, placed)
        if job is not None and resident.post_id == placed.object_id:
            on = world.work.shift_minutes_left(world, resident, job) > 0
            found.append(Placing(WORK, NAMES[WORK], "se pondrá a trabajar", "" if on else OFF_HOURS))
        elif job is not None:
            holder = self._holder(world, placed.object_id)
            text = f"se quedará con el puesto: {job.name.lower()}"
            if holder is not None:
                text += f", y {holder.name} lo perderá"
            found.append(Placing(POST, NAMES[POST], text))
        if definition.use is not None:
            said = settings.uses.get(definition.use.action, settings.use).replace("{thing}", thing)
            found.append(Placing(USE, NAMES[USE], said, self._closed(world, resident, placed, definition.use)))
        if world.salvaging.rule_of(world, placed) is not None:
            found.append(Placing(TAKE_APART, NAMES[TAKE_APART], f"desguazará {thing}", self._not_apart(world, resident, placed)))
        if not found:
            pastime = world.registries.leisure.pastimes.get(settings.otherwise)
            if pastime is not None:
                found.append(Placing(PASTIME, NAMES[PASTIME], f"se quedará un rato junto a {thing}"))
        return found

    def _closed(self, world: "SimulationWorld", resident: Resident, placed: Interactable, use: UseDefinition) -> str:
        """Why a resident cannot use a thing as things stand. Empty if they can."""
        if not world.work.open_to(world, resident, use):
            return NOBODY_SERVING
        housing = world.housing
        if not housing.may_use(world, resident, placed, use) and not housing.pressed(world, resident, placed, use):
            return NOT_THEIRS.format(name=resident.name)
        if not world.trade.can_afford(world, resident, use, placed.object_id):
            return CANNOT_PAY
        if use.consumes is not None and world.items.best_food(world, resident, placed.object_id, use.consumes) is None:
            return NOTHING_LEFT
        if world.users_of(placed.object_id) >= use.capacity:
            return FULL
        return ""

    def _not_apart(self, world: "SimulationWorld", resident: Resident, placed: Interactable) -> str:
        if not world.health.is_fit_for_work(resident):
            return NOT_FIT.format(name=resident.name)
        kept = world.containers.get(placed.object_id)
        if kept is not None and kept.items:
            return TO_EMPTY
        return ""

    def _with(self, world: "SimulationWorld", resident: Resident, other_id: str | None) -> Placing:
        other = world.residents.get(other_id or "")
        if other is None or other is resident or other.away:
            return Placing(WITH, "", "", GONE)
        text = f"con {other.name}: elige qué"
        if not world.is_aware(other):
            return Placing(WITH, "", text, ASLEEP.format(name=other.name))
        if not world.affect.with_whom(world, resident.resident_id, other.resident_id):
            return Placing(WITH, "", text, NOTHING_WITH.format(name=other.name))
        return Placing(WITH, "", text)

    def _on_site(self, world: "SimulationWorld", resident: Resident, site_id: str | None) -> Placing:
        site = world.sites.get(site_id or "")
        if site is None:
            return Placing(BUILD, "", "", GONE)
        what = world.construction.thing(world, site.kind, site.what) or site.what
        text = f"se hará cargo de la obra: {what.lower()}"
        return Placing(BUILD, "", text, IN_CHARGE if site.in_charge == resident.resident_id else "")

    def _into(self, world: "SimulationWorld", resident: Resident, room: Room) -> Placing:
        text = f"entrará en {room.name}"
        if not room.roofed or world.housing.lives_in(world, resident, room) or not world.housing.locked(world, room):
            return Placing(ENTER, "", text)
        return Placing(ENTER, "", text, LOCKED.format(room=room.name))

    def _child(self, world: "SimulationWorld", resident: Resident, child_id: str | None) -> Placing:
        bundle = world.bundles.get(child_id or "")
        if bundle is None:
            return Placing(TAKE_UP, "", "", GONE)
        error = world.children.cannot_mind(world, resident)
        return Placing(TAKE_UP, "", f"cogerá en brazos a {bundle.name}", error or "")

    # ----- where they would stand -----

    def _free(self, world: "SimulationWorld", resident: Resident) -> Callable[[Tile], bool]:
        """Whether a tile is somewhere a resident could be stood: ground to walk on, with nobody on it."""
        passable = world.passable()
        taken = spots_taken(world, resident)
        return lambda tile: passable(tile) and tile not in taken

    def _near(
        self, world: "SimulationWorld", resident: Resident, tile: Tile, allowed: Callable[[Tile], bool] | None = None
    ) -> Tile | None:
        """The free tile nearest to one, no further off than somebody is put down from where
        they are let go, and among those `allowed`, if only some are."""
        reach = world.registries.placing.reach
        free = self._free(world, resident)
        around = sorted(
            ((tile[0] + dx, tile[1] + dy) for dx in range(-reach, reach + 1) for dy in range(-reach, reach + 1)),
            key=lambda each: (manhattan(tile, each), each[1], each[0]),
        )
        return next((each for each in around if free(each) and (allowed is None or allowed(each))), None)

    def _beside(self, world: "SimulationWorld", resident: Resident, tiles: list[Tile], tile: Tile) -> Tile | None:
        """The free tile next to a thing that is nearest to where somebody is let go over it."""
        free = self._free(world, resident)
        footprint = set(tiles)
        spots = {
            (x + dx, y + dy) for x, y in footprint for dx, dy in NEIGHBOURS if (x + dx, y + dy) not in footprint
        }
        near = sorted((each for each in spots if free(each)), key=lambda each: (manhattan(tile, each), each[1], each[0]))
        return near[0] if near else None

    def _spot(self, world: "SimulationWorld", resident: Resident, tile: Tile, on_kind: str, on_id: str | None) -> Tile | None:
        """Where a resident let go of over something would stand. None if there is nowhere."""
        stood_on: list[Tile] | None = None
        if on_kind == OBJECT and on_id in world.interactables:
            placed = world.interactables[on_id]
            stood_on = placed.footprint(world.definition_of(placed))
        elif on_kind == RESIDENT and on_id in world.residents and on_id != resident.resident_id:
            stood_on = [world.residents[on_id].tile]
        elif on_kind == SITE and on_id in world.sites:
            site = world.sites[on_id]
            stood_on = list(site.tiles) or [(site.x, site.y)]
        if stood_on is not None:
            return self._beside(world, resident, stood_on, tile) or self._near(world, resident, tile)
        if on_kind == ROOM and on_id in world.rooms:
            room = world.rooms[on_id]
            if self._into(world, resident, room).open:
                return self._near(world, resident, tile, room.contains) or self._near(world, resident, tile)
            # Shut out, they are left at the nearest ground that is not under its roof.
            return self._near(world, resident, tile, lambda each: not room.contains(each))
        if on_kind == CHILD and on_id in world.bundles:
            return self._near(world, resident, world.bundles[on_id].tile)
        return self._near(world, resident, tile)

    # ----- putting them down -----

    def put_down(
        self,
        world: "SimulationWorld",
        resident_id: str,
        tile: Tile,
        on_kind: str = GROUND,
        on_id: str | None = None,
        does: str | None = None,
    ) -> PlacingResult:
        """Put a resident down. They are there at once, and set about what they were put on.

        `does` says which, of what `choices` gives, where it could be more than one thing.
        Left out there, they stand where they were put until it is said, and the result's
        `choices` are what there is to say. With nowhere to stand them, nothing is done.
        """
        error = self.obstacle(world, resident_id)
        if error is not None:
            return PlacingResult(False, error)
        resident = world.residents[resident_id]
        spot = self._spot(world, resident, tile, on_kind, on_id)
        if spot is None:
            return PlacingResult(False, NO_ROOM)
        found = self.choices(world, resident_id, on_kind, on_id)
        open_ones = tuple(each for each in found if each.open)
        chosen = next((each for each in open_ones if each.does == does), None)
        if chosen is None and does is None and len(open_ones) == 1:
            chosen = open_ones[0]
        self._move(world, resident, spot)
        self._announce(world, resident, on_kind, on_id, chosen.does if chosen is not None else STAY)
        if chosen is None and does is None and len(open_ones) > 1:
            # It could be more than one thing: they stand there until told which.
            world.affect.hold(world, resident_id)
            return PlacingResult(True, f"{resident.name}: ¿qué hace aquí?", CHOOSE, on_id, open_ones)
        if chosen is None:
            why = next((each.reason for each in found if each.reason), "")
            said = f"{resident.name} se queda aquí"
            return PlacingResult(True, f"{said}: {why[0].lower()}{why[1:]}" if why else said)
        return self._carry_out(world, resident, chosen, on_id)

    def _move(self, world: "SimulationWorld", resident: Resident, spot: Tile) -> None:
        """Have a resident be somewhere at once, with whatever they were at left off. What
        they were at for having been told goes back to wait its turn."""
        world.affect.interrupted(world, resident)
        world.affect.leave_off(world, resident)
        resident.x, resident.y = spot
        resident.trail, resident.ahead = [], []

    def _announce(self, world: "SimulationWorld", resident: Resident, on_kind: str, on_id: str | None, does: str) -> None:
        world.emit_event(
            DomainEvent(
                PLACED_EVENT,
                PLACED_IMPORTANCE,
                f"A {resident.name} se le deja en otro sitio",
                [resident.resident_id],
                data={"tile": list(resident.tile), "on": on_kind, "target": on_id, "does": does},
            ),
            at=resident.tile,
        )

    def _arrive(self, resident: Resident) -> None:
        """Have a resident be where they were walking to, to get on with it there and then."""
        activity = resident.activity
        if activity is not None and activity.path and activity.partner_id is None:
            resident.x, resident.y = activity.path[-1]
            activity.path = []
            resident.trail, resident.ahead = [], []

    def _told(
        self, world: "SimulationWorld", resident: Resident, placing: Placing, kind: str, target_id: str | None
    ) -> PlacingResult:
        result = world.affect.do_now(world, resident.resident_id, kind, target_id)
        if not result.ok:
            return PlacingResult(True, f"{resident.name} se queda aquí: {result.message[0].lower()}{result.message[1:]}")
        self._arrive(resident)
        return PlacingResult(True, f"{resident.name} {placing.text}", placing.does, target_id)

    def _carry_out(self, world: "SimulationWorld", resident: Resident, placing: Placing, on_id: str | None) -> PlacingResult:
        does = placing.does
        if does == USE:
            return self._told(world, resident, placing, USE_THING, on_id)
        if does == WORK:
            return self._told(world, resident, placing, f"{TASK}:{TO_POST}", None)
        if does == TAKE_APART:
            return self._told(world, resident, placing, f"{TASK}:{SALVAGE}", on_id)
        if does == BUILD:
            return self._told(world, resident, placing, f"{TASK}:{TAKE_CHARGE}", on_id)
        if does == PASTIME:
            return self._told(world, resident, placing, f"{LEISURE}:{world.registries.placing.otherwise}", None)
        if does == POST:
            return self._take_post(world, resident, world.interactables[on_id or ""])
        if does == WITH:
            # What the two do is still to be said: they stand by the other until it is.
            world.affect.hold(world, resident.resident_id)
            other = world.residents[on_id or ""]
            return PlacingResult(True, f"{resident.name}, con {other.name}: ¿qué?", WITH, on_id)
        if does == TAKE_UP:
            handed = world.children.hand(world, on_id or "", resident.resident_id)
            return PlacingResult(True, handed.message, TAKE_UP if handed.ok else STAY, on_id)
        return PlacingResult(True, f"{resident.name} {placing.text}", does, on_id)

    def _take_post(self, world: "SimulationWorld", resident: Resident, placed: Interactable) -> PlacingResult:
        """Have a post be a resident's from now on, whoever's it was: that one is left without."""
        job = self._job_at(world, placed)
        if job is None:
            return PlacingResult(True, f"{resident.name} se queda aquí")
        holder = self._holder(world, placed.object_id)
        said = f"{resident.name} se queda con el puesto: {job.name.lower()}"
        if holder is not None and holder is not resident:
            world.staffing.dismiss(world, holder)
            said += f". {holder.name} lo pierde"
            world.emit_event(
                DomainEvent(
                    POST_LOST_EVENT,
                    POST_LOST_IMPORTANCE,
                    f"{holder.name} se queda sin su puesto: ahora es de {resident.name}",
                    [holder.resident_id, resident.resident_id],
                    data={"job": job.job_id, "post": placed.object_id, "to": resident.resident_id},
                ),
                at=holder.tile,
            )
        if not world.staffing.assign(world, resident, job.job_id, placed.object_id):
            return PlacingResult(True, f"{resident.name} se queda aquí: ese puesto no se le puede dar")
        if world.work.shift_minutes_left(world, resident, job) > 0:
            if world.affect.do_now(world, resident.resident_id, f"{TASK}:{TO_POST}").ok:
                self._arrive(resident)
        return PlacingResult(True, said, POST, placed.object_id)
