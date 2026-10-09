"""Picked up and put down (P27): what comes of setting somebody down somewhere.

The player takes a resident up off the map and lets go of them over a thing, over somebody
else, over a site or over bare ground. They are there at once, and what they were let go over
is what they set about, as an order like any other (S37): a post is theirs, a bed is slept in,
a pot is eaten from. Where nothing can come of it they are put down beside it and go on with
their day. A child's bundle is taken up the same way, and put in the arms of somebody or laid
down.

What a drop would do is worked out here, so that it can be said before the button is let go,
and it is done here, by stable IDs, so that it runs with no screen.
"""

from dataclasses import dataclass
from typing import TYPE_CHECKING

from simulation.ai.activity_system import facing_towards
from simulation.ai.affect import LEISURE, SALVAGE, TAKE_CHARGE, TASK, TO_POST, USE
from simulation.ai.crowd import spots_taken
from simulation.events.event import DomainEvent
from simulation.family.children import BED_ACTION, Bundle
from simulation.residents.resident import Resident
from simulation.work.work_system import Expected
from world.interactable import Interactable
from world.map import Tile
from world.pathfinding import DIAGONALS, NEIGHBOURS, manhattan

if TYPE_CHECKING:
    from simulation.world import SimulationWorld

# What can come of putting a resident down: only being there, being with somebody, a post that
# becomes theirs, a post changed with whoever had it, a thing used, a seat sat on, a site taken
# charge of, something taken apart. And of a bundle: being handed to somebody, or laid down.
STAND, PERSON, POST, SWAP, USE_IT, SIT, SITE, TAKE_APART, HAND, LAY = (
    "stand", "person", "post", "swap", "use", "sit", "site", "salvage", "hand", "lay",
)
KINDS = (STAND, PERSON, POST, SWAP, USE_IT, SIT, SITE, TAKE_APART, HAND, LAY)
PLACED_IMPORTANCE = 10
NOWHERE = "Ahí no se puede dejar a nadie"
HERE = "Dejar aquí"
PLAIN_USE = "Usar"
WHICH_USE = "Dejar aquí, y elegir qué hace"


@dataclass(frozen=True)
class Placement:
    """One thing that would come of putting somebody down somewhere."""

    kind: str
    # Where they would be stood or laid. None for what cannot be done, and `text` says why.
    tile: Tile | None
    # What it says, in a few words, before it is done.
    text: str
    # What or whom it is about: an object, a resident or a site.
    target_id: str | None = None
    # For a post: the job it is of, what they would make of it, and whether they would set
    # about it there and then, which they do only with a shift ahead of them.
    job_id: str | None = None
    expected: Expected | None = None
    at_once: bool = False
    # For being put with somebody: whether there is anything the two could be told to do.
    # For being put by a thing with nothing it is mainly for: that it is asked what they do there.
    opens: bool = False

    @property
    def ok(self) -> bool:
        return self.tile is not None


@dataclass(frozen=True)
class PlaceResult:
    ok: bool
    message: str
    kind: str = ""
    tile: Tile | None = None
    # Who they were put with, where there is something the two could now be told to do.
    other_id: str | None = None
    # The thing they were put by, where there is nothing it is mainly for that they can do
    # and none of what else it offers was set about: it is for whoever put them there to
    # say which (P63).
    thing_id: str | None = None


class PlacingSystem:
    # ----- a resident -----

    def obstacle(self, world: "SimulationWorld", resident_id: str) -> str | None:
        """Why a resident cannot be taken up and put somewhere else right now. None if they can."""
        error = world.affect.obstacle(world, resident_id)
        if error is not None:
            return error
        if world.justice.confined(world, resident_id):
            return f"{world.residents[resident_id].name} cumple su condena: de ahí no se mueve"
        return None

    def options(
        self,
        world: "SimulationWorld",
        resident_id: str,
        *,
        object_id: str | None = None,
        other_id: str | None = None,
        site_id: str | None = None,
        tile: Tile | None = None,
    ) -> list[Placement]:
        """What could come of putting a resident down on a thing, on somebody, on a site or on
        a tile, the likeliest first: what is done with nothing else said. `tile` is where the
        hand is, and with nothing else named it is what lies on it that they are put down on.
        Empty for somebody who cannot be taken up at all."""
        if self.obstacle(world, resident_id) is not None:
            return []
        resident = world.residents[resident_id]
        ground = Ground(world, resident, tile or resident.tile)
        other = world.residents.get(other_id or "")
        placed = world.interactables.get(object_id or "")
        site = world.sites.get(site_id or "")
        if other is None and placed is None and site is None and tile is not None:
            other = next(
                (each for each in world.residents.values() if each is not resident and not each.away and each.tile == tile),
                None,
            )
            placed = self._object_on(world, tile) if other is None else None
            site = next((each for each in world.sites.values() if tile in each.tiles), None) if placed is None else None
        if other is not None and other is not resident:
            return [self._with(world, resident, other, ground)]
        if placed is not None:
            return self._at_object(world, resident, placed, ground)
        if site is not None:
            return self._at_site(world, resident, site, ground)
        if tile is None:
            return []
        return [Placement(STAND, tile if ground.fit(tile) else None, HERE if ground.fit(tile) else NOWHERE)]

    def put(
        self,
        world: "SimulationWorld",
        resident_id: str,
        *,
        object_id: str | None = None,
        other_id: str | None = None,
        site_id: str | None = None,
        tile: Tile | None = None,
        do: str | None = None,
    ) -> PlaceResult:
        """Put a resident down. They are there at once, whatever they were at, and set about
        what they were put down on: the first of what `options` gives, or the one of the kind
        `do` names. What they had been told to do before is still theirs to do afterwards."""
        error = self.obstacle(world, resident_id)
        if error is not None:
            return PlaceResult(False, error)
        found = self.options(world, resident_id, object_id=object_id, other_id=other_id, site_id=site_id, tile=tile)
        chosen = next((each for each in found if do is None or each.kind == do), None)
        if chosen is None or chosen.tile is None:
            return PlaceResult(False, chosen.text if chosen is not None else NOWHERE)
        resident = world.residents[resident_id]
        came_from = resident.tile
        world.affect.interrupted(world, resident)
        world.affect.leave_off(world, resident)
        resident.x, resident.y = chosen.tile
        resident.trail, resident.ahead = [chosen.tile], []
        towards = self._where(world, chosen)
        resident.facing = (facing_towards(resident.tile, towards) if towards is not None else None) or resident.facing
        world.emit_event(
            DomainEvent(
                "resident_placed",
                PLACED_IMPORTANCE,
                f"A {resident.name} se le coge y se le deja en otro sitio",
                [resident_id],
                data={"kind": chosen.kind, "target": chosen.target_id, "from": list(came_from), "to": list(chosen.tile)},
            ),
            at=resident.tile,
        )
        self._set_about(world, resident, chosen)
        opened = chosen.target_id if chosen.kind == PERSON and chosen.opens else None
        asked = chosen.target_id if chosen.kind == USE_IT and chosen.opens else None
        return PlaceResult(True, chosen.text, chosen.kind, chosen.tile, opened, asked)

    def _set_about(self, world: "SimulationWorld", resident: Resident, chosen: Placement) -> None:
        """Have a resident who has just been put down get on with what they were put down on.
        Where it turns out that they cannot, they are there and nothing else."""
        order = world.affect.order
        resident_id = resident.resident_id
        if chosen.kind in (POST, SWAP):
            holder = world.staffing.holder(world, chosen.target_id or "")
            if chosen.kind == SWAP and holder is not None:
                world.staffing.swap(world, resident, holder)
            elif holder is None:
                world.staffing.assign(world, resident, chosen.job_id or "", chosen.target_id)
            if resident.post_id == chosen.target_id:
                order(world, resident_id, f"{TASK}:{TO_POST}", None, now=True)
        elif chosen.kind == USE_IT and not chosen.opens:
            order(world, resident_id, f"{TASK}:{USE}", chosen.target_id, now=True)
        elif chosen.kind == SIT:
            pastime = self._sitting(world)
            if pastime is not None:
                order(world, resident_id, f"{LEISURE}:{pastime}", None, now=True)
        elif chosen.kind == SITE:
            order(world, resident_id, f"{TASK}:{TAKE_CHARGE}", chosen.target_id, now=True)
        elif chosen.kind == TAKE_APART:
            order(world, resident_id, f"{TASK}:{SALVAGE}", chosen.target_id, now=True)

    def _where(self, world: "SimulationWorld", chosen: Placement) -> Tile | None:
        """The tile of what a placement is about, for whoever is put down to turn towards."""
        target = chosen.target_id or ""
        if target in world.interactables:
            return (world.interactables[target].x, world.interactables[target].y)
        if target in world.residents:
            return world.residents[target].tile
        if target in world.sites:
            return (world.sites[target].x, world.sites[target].y)
        return None

    def _object_on(self, world: "SimulationWorld", tile: Tile) -> Interactable | None:
        """What stands on a tile, if anything does: what is in the way before what is not."""
        on = [
            placed
            for placed in world.interactables.values()
            if tile in placed.footprint(world.definition_of(placed))
        ]
        return min(on, key=lambda placed: (not world.definition_of(placed).blocks, placed.object_id), default=None)

    def _sitting(self, world: "SimulationWorld") -> str | None:
        """The pastime that is sitting down, if the data has one."""
        return next((each.pastime_id for each in world.registries.leisure.pastimes.values() if each.sits), None)

    def _with(self, world: "SimulationWorld", resident: Resident, other: Resident, ground: "Ground") -> Placement:
        if other.away:
            return Placement(PERSON, None, f"{other.name} está fuera del asentamiento", other.resident_id)
        spot = ground.beside([other.tile], corners=True)
        if spot is None:
            return Placement(PERSON, None, f"No hay sitio junto a {other.name}", other.resident_id)
        opens = world.is_aware(other) and bool(world.affect.with_whom(world, resident.resident_id, other.resident_id))
        text = f"Con {other.name}: elegir qué hacen" if opens else f"Dejar junto a {other.name}"
        return Placement(PERSON, spot, text, other.resident_id, opens=opens)

    def _at_object(
        self, world: "SimulationWorld", resident: Resident, placed: Interactable, ground: "Ground"
    ) -> list[Placement]:
        definition = world.definition_of(placed)
        footprint = placed.footprint(definition)
        object_id = placed.object_id
        named = f"{definition.article} {definition.name}"
        beside = ground.beside(footprint)
        found: list[Placement] = []
        job = world.staffing.job_at(world, object_id)
        if job is not None and beside is not None:
            holder = world.staffing.holder(world, object_id)
            fit = world.health.is_fit_for_work(resident)
            at_once = fit and world.work.shift_minutes_left(world, resident, job) > 0
            expected = world.work.expected(world, resident, job)
            if holder is resident:
                found.append(
                    Placement(POST, beside, f"A su puesto: {job.name}", object_id, job.job_id, expected, at_once)
                )
            elif holder is None:
                found.append(Placement(POST, beside, f"Puesto: {job.name}", object_id, job.job_id, expected, at_once))
            elif not holder.away:
                text = f"{job.name}: cambia el puesto con {holder.name}"
                found.append(Placement(SWAP, beside, text, object_id, job.job_id, expected, at_once))
        use = definition.use
        if use is not None and world.affect.can_use(world, resident, placed):
            spot = ground.onto(footprint, (placed.x, placed.y)) if use.position == "on" else beside
            if spot is not None:
                found.append(Placement(USE_IT, spot, use.label or PLAIN_USE, object_id))
        elif beside is not None and world.affect.things_to_do(world, resident, placed):
            # Nothing it is mainly for that they can do, and something else it offers (S60):
            # they are put by it, and it is asked which, as it is with a click on it (P63).
            found.append(Placement(USE_IT, beside, WHICH_USE, object_id, opens=True))
        if definition.seat and ground.fit((placed.x, placed.y)):
            pastime = world.registries.leisure.pastimes.get(self._sitting(world) or "")
            if pastime is not None:
                found.append(Placement(SIT, (placed.x, placed.y), pastime.name, object_id))
        if (
            beside is not None
            and object_id not in world.salvage
            and world.salvaging.rule_of(world, placed) is not None
            and world.health.is_fit_for_work(resident)
            and not (object_id in world.containers and world.containers[object_id].items)
        ):
            task = world.registries.affect.tasks.get(SALVAGE)
            if task is not None:
                found.append(Placement(TAKE_APART, beside, f"{task.name}: {named}", object_id))
        # And they can always be left there and nothing else, where there is anywhere to leave them.
        if not definition.blocks and ground.fit(ground.near) and ground.near in footprint:
            found.append(Placement(STAND, ground.near, HERE, object_id))
        elif beside is not None:
            found.append(Placement(STAND, beside, f"Dejar junto a {named}", object_id))
        return found or [Placement(STAND, None, f"No hay sitio junto a {named}", object_id)]

    def _at_site(self, world: "SimulationWorld", resident: Resident, site, ground: "Ground") -> list[Placement]:
        thing = world.construction.thing(world, site.kind, site.what) or site.what
        beside = ground.beside(site.tiles or [(site.x, site.y)])
        if beside is None:
            return [Placement(STAND, None, f"No hay sitio junto a la obra: {thing}", site.site_id)]
        found = []
        task = world.registries.affect.tasks.get(TAKE_CHARGE)
        if task is not None and site.in_charge != resident.resident_id:
            found.append(Placement(SITE, beside, f"{task.name}: {thing}", site.site_id))
        found.append(Placement(STAND, beside, f"Dejar junto a la obra: {thing}", site.site_id))
        return found

    # ----- a bundle -----

    def bundle_options(
        self,
        world: "SimulationWorld",
        child_id: str,
        *,
        other_id: str | None = None,
        object_id: str | None = None,
        tile: Tile | None = None,
    ) -> list[Placement]:
        """What could come of putting a child's bundle down on somebody, on a thing or on a
        tile. With only a tile, it is whoever stands on it that takes it, if anybody does."""
        bundle = world.bundles.get(child_id)
        if bundle is None:
            return []
        other = world.residents.get(other_id or "")
        placed = world.interactables.get(object_id or "")
        if other is None and placed is None and tile is not None:
            other = next((each for each in world.residents.values() if not each.away and each.tile == tile), None)
            placed = self._object_on(world, tile) if other is None else None
        if other is not None:
            return [self._to_arms(world, bundle, other)]
        ground = Ground(world, None, tile or bundle.tile)
        if placed is not None:
            definition = world.definition_of(placed)
            use = definition.use
            footprint = placed.footprint(definition)
            if use is not None and use.action == BED_ACTION and ground.reached(footprint):
                return [Placement(LAY, (placed.x, placed.y), "Acostar en la cama", placed.object_id)]
            if definition.blocks:
                spot = ground.near if ground.near in footprint else (placed.x, placed.y)
                ok = ground.reached(footprint)
                text = self._laid(world, spot) if ok else NOWHERE
                return [Placement(LAY, spot if ok else None, text, placed.object_id)]
        if tile is None:
            return []
        ok = tile in ground.reach
        return [Placement(LAY, tile if ok else None, self._laid(world, tile) if ok else NOWHERE)]

    def put_bundle(
        self,
        world: "SimulationWorld",
        child_id: str,
        *,
        other_id: str | None = None,
        object_id: str | None = None,
        tile: Tile | None = None,
    ) -> PlaceResult:
        """Put a child's bundle in the arms of somebody, who carries it from then on, or lay it
        down, where it stays."""
        bundle = world.bundles.get(child_id)
        if bundle is None:
            return PlaceResult(False, "Ya no hay a quién coger")
        found = self.bundle_options(world, child_id, other_id=other_id, object_id=object_id, tile=tile)
        chosen = found[0] if found else None
        if chosen is None or chosen.tile is None:
            return PlaceResult(False, chosen.text if chosen is not None else NOWHERE)
        if chosen.kind == HAND:
            world.children.hand_to(world, bundle, world.residents[chosen.target_id or ""])
        else:
            placed = world.interactables.get(chosen.target_id or "")
            use = world.definition_of(placed).use if placed is not None else None
            world.children.leave_at(world, bundle, chosen.tile, in_bed=use is not None and use.action == BED_ACTION)
        return PlaceResult(True, chosen.text, chosen.kind, chosen.tile)

    def _to_arms(self, world: "SimulationWorld", bundle: Bundle, other: Resident) -> Placement:
        able = (
            world.children.can_mind(world, other)
            and world.bonds.is_adult(world, other)
            and other.resident_id not in world.leaving
            and not world.justice.confined(world, other.resident_id)
        )
        if not able:
            return Placement(HAND, None, f"{other.name} no está para llevar a nadie", other.resident_id)
        return Placement(HAND, other.tile, f"Dejar a {bundle.name} con {other.name}", other.resident_id)

    def _laid(self, world: "SimulationWorld", tile: Tile) -> str:
        return "Dejar aquí, a cubierto" if world.under_roof(tile) else "Dejar aquí, en el suelo"


class Ground:
    """Where somebody could be put down, as things stand: what can be walked to, and what
    nobody else stands on or is making for."""

    def __init__(self, world: "SimulationWorld", resident: Resident | None, near: Tile) -> None:
        self.reach = world.urbanism.within_reach(world)
        self.taken = spots_taken(world, resident) if resident is not None else set()
        # Where the hand is: of two places that would do, the nearer to it.
        self.near = near

    def fit(self, tile: Tile) -> bool:
        return tile in self.reach and tile not in self.taken

    def reached(self, footprint: list[Tile]) -> bool:
        """Whether a thing can be got to: some tile beside it can be walked to."""
        return any((x + dx, y + dy) in self.reach for x, y in footprint for dx, dy in NEIGHBOURS)

    def onto(self, footprint: list[Tile], tile: Tile) -> Tile | None:
        """The tile of a thing that is lain on, if it can be got to and nobody is on it."""
        return tile if self.reached(footprint) and tile not in self.taken else None

    def beside(self, footprint: list[Tile], corners: bool = False) -> Tile | None:
        """The free tile next to a thing that is nearest to where the hand is. With `corners`,
        one that touches it only at a corner will do where no other does."""
        covered = set(footprint)
        for around in (NEIGHBOURS, DIAGONALS) if corners else (NEIGHBOURS,):
            spots = {
                (x + dx, y + dy)
                for x, y in footprint
                for dx, dy in around
                if (x + dx, y + dy) not in covered and self.fit((x + dx, y + dy))
            }
            if spots:
                return min(spots, key=lambda spot: (manhattan(self.near, spot), spot[1], spot[0]))
        return None
