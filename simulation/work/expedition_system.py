"""Scavenging outside: setting out, what happens out there, and bringing the finds home."""

from collections.abc import Mapping
from typing import TYPE_CHECKING

from simulation.residents.attributes import SENSES
from simulation.ai.crowd import free_tile
from simulation.economy.ledger import FOUND, PACKED, UNPACKED
from simulation.events.event import DomainEvent
from simulation.rng import SimulationRNG
from simulation.events.world_event import WEATHER
from simulation.items.item import ItemInstance
from simulation.residents.activity import Activity
from simulation.residents.resident import Resident
from simulation.work.expedition import PUSH_ON, RAID_CHOICES, TURN_BACK, Expedition, Outing, TripResult, Zone, ZoneFound
from simulation.work.hauling import containers_of_kind
from simulation.work.job import JobDefinition
from simulation.work.research import EXPEDITION_DANGER, EXPEDITION_FINDS
from world.interactable import Interactable
from world.pathfinding import manhattan

if TYPE_CHECKING:
    from simulation.world import SimulationWorld

EXPEDITION_ACTION = "expedition"
RISKY_FIND = "risky_find"
LEFT_IMPORTANCE = 15
RETURN_IMPORTANCE = 30
# Nobody sets out with less of their shift than this ahead of them.
MIN_SHIFT_LEFT = 60
INJURY_CAUSE = "una salida fuera del asentamiento"
STAYED_IN_IMPORTANCE = 20
STAYED_IN_NOTICE = "stayed_in:"
ZONE_FOUND_EVENT = "zone_found"
ZONE_FOUND_IMPORTANCE = 60
ZONE_NAMED_EVENT = "zone_named"
ZONE_NAMED_IMPORTANCE = 30
TRIP_PLANNED_EVENT = "trip_planned"
TRIP_PLANNED_IMPORTANCE = 15
# How much of the way out what is come on may be at, for a trip that goes past the first zone:
# anywhere from here to the far end.
EARLIEST_FIND = 0.4
# The longest name a zone may be given.
ZONE_NAME_LENGTH = 24


class ExpeditionSystem:
    def can_set_out(self, world: "SimulationWorld", resident: Resident, job: JobDefinition, shift_left: int) -> bool:
        """Whether a worker at their post should leave on a trip now: one a day, and empty-handed."""
        return (
            job.expedition is not None
            and resident.expedition is None
            and resident.last_expedition_day != world.clock.day
            and shift_left >= MIN_SHIFT_LEFT
            and bool(world.registries.expeditions.loot)
            and not (job.outdoors and world.happenings.is_stormy(world))
            and not self._finds_on(world, resident)
        )

    def stays_in(self, world: "SimulationWorld", resident: Resident, job: JobDefinition) -> bool:
        """Whether a worker about to leave thinks better of it: they know bad weather would catch them out.

        It goes by what they have heard, not by what is coming. Said once a day.
        """
        rule = job.expedition
        if rule is None or not job.outdoors:
            return False
        if world.happenings.expected(world, resident, WEATHER, within=rule.minutes[1]) is None:
            return False
        key = f"{STAYED_IN_NOTICE}{resident.resident_id}"
        if world.notices.get(key) != world.clock.day:
            world.notices[key] = world.clock.day
            world.emit_event(
                DomainEvent(
                    "stayed_in",
                    STAYED_IN_IMPORTANCE,
                    f"{resident.name} no sale hoy: la radio anuncia mal tiempo",
                    [resident.resident_id],
                ),
                at=resident.tile,
            )
        return True

    def zone_of(self, world: "SimulationWorld", trip: Expedition) -> Zone | None:
        """The zone a trip is bound for: the one it set out for if there still is such a one,
        or else the first there is. None where the data names none."""
        zones = world.registries.expeditions.zones
        return next((zone for zone in zones if zone.zone_id == trip.zone), zones[0] if zones else None)

    def zone_now(self, world: "SimulationWorld", trip: Expedition) -> Zone | None:
        """The zone whoever is on a trip is in right now, of those it goes through."""
        settings = world.registries.expeditions
        return settings.zone(trip.zone_at(world.clock.total_minutes)) or self.zone_of(world, trip)

    # ----- the country there is, and how far each can go (S68) -----

    def name_of(self, world: "SimulationWorld", zone: Zone) -> str:
        """What a zone is called: what the player has called it, or else what the game does."""
        found = world.zones.get(zone.zone_id)
        return found.name if found is not None and found.name else zone.name

    def is_found(self, world: "SimulationWorld", zone: Zone) -> bool:
        """Whether the settlement knows of a zone: the first of the line is at its gate."""
        line = world.registries.expeditions.line
        return zone.zone_id in world.zones or bool(line and line[0].zone_id == zone.zone_id)

    def found(self, world: "SimulationWorld") -> list[Zone]:
        """The zones the settlement knows of, the nearest first and those off the line last."""
        return [zone for zone in world.registries.expeditions.zones if self.is_found(world, zone)]

    def goes_out(self, world: "SimulationWorld", resident: Resident) -> JobDefinition | None:
        """The job of somebody whose job is done out there, or None."""
        job = world.work.job_of(world, resident)
        return job if job is not None and job.expedition is not None else None

    def reach(self, world: "SimulationWorld", resident: Resident) -> list[Zone]:
        """Where somebody can be sent: as many zones of the line as the level they have at a
        job done out there, of those that have been found, and wherever a map has opened."""
        job = self.goes_out(world, resident)
        if job is None:
            return []
        settings = world.registries.expeditions
        level = max(1, world.crafts.level(world, resident, job.job_id))
        line = [zone for zone in settings.line[:level] if self.is_found(world, zone)]
        return [*line, *(zone for zone in settings.zones if zone.apart and self.is_found(world, zone))]

    def route_to(self, world: "SimulationWorld", zone: Zone) -> list[Zone]:
        """Every zone gone through to get to one, itself last: all of the line before it, and
        nothing for one that is off the line."""
        if zone.apart:
            return [zone]
        line = world.registries.expeditions.line
        return list(line[: line.index(zone) + 1]) if zone in line else [zone]

    def needs(self, world: "SimulationWorld", zone: Zone) -> float:
        """How much has to be taken along to get to a zone, in what provisions are worth."""
        return sum(crossed.supplies for crossed in self.route_to(world, zone))

    def worth(self, world: "SimulationWorld", item_id: str) -> float:
        """How far a unit of a thing goes as provisions. Nothing for what is none."""
        definition = world.registries.items.find(item_id)
        if definition is None:
            return 0.0
        for provision in world.registries.expeditions.provisions:
            if provision.category == definition.category or (provision.tag is not None and provision.tag in definition.tags):
                return provision.worth
        return 0.0

    def is_kit(self, world: "SimulationWorld", item_id: str) -> bool:
        """Whether a thing is taken along to mend oneself with out there (S70)."""
        definition = world.registries.items.find(item_id)
        return definition is not None and definition.category in world.registries.expeditions.kits

    def worth_of(self, world: "SimulationWorld", supplies: Mapping[str, int]) -> float:
        return sum(self.worth(world, item_id) * max(0, units) for item_id, units in supplies.items())

    def on_hand(self, world: "SimulationWorld") -> dict[str, int]:
        """What there is to hand over for a trip: units of each thing that is everybody's,
        kept somewhere, and worth anything on the way or to mend oneself with out there."""
        return {
            item_id: units
            for item_id, units in world.giving.givable(world).items()
            if self.worth(world, item_id) > 0 or self.is_kit(world, item_id)
        }

    def gets_to(self, world: "SimulationWorld", resident: Resident, supplies: Mapping[str, int]) -> Zone | None:
        """The furthest zone of the line that somebody can go to with what is handed to them:
        as far as they know the way, and no further than the provisions last."""
        worth = self.worth_of(world, supplies)
        within = [zone for zone in self.reach(world, resident) if not zone.apart and self.needs(world, zone) <= worth]
        return within[-1] if within else None

    def obstacle(
        self,
        world: "SimulationWorld",
        resident_id: str,
        zone_id: str,
        supplies: Mapping[str, int],
        held: Mapping[str, int] | None = None,
    ) -> str | None:
        """Why a trip cannot be made ready for somebody as things stand, or None if it can.
        `held` is what was already handed to them for one, which counts as there to hand over."""
        resident = world.residents.get(resident_id)
        if resident is None:
            return "No hay a quién mandar"
        if self.goes_out(world, resident) is None:
            return f"{resident.name} no tiene un oficio de salir fuera"
        if resident.away:
            return f"{resident.name} ya está fuera"
        zone = world.registries.expeditions.zone(zone_id)
        if zone is None or zone not in self.reach(world, resident):
            return f"{resident.name} no sabe llegar hasta allí"
        there = self.on_hand(world)
        for item_id, units in (held or {}).items():
            there[item_id] = there.get(item_id, 0) + units
        if any(units < 0 or units > there.get(item_id, 0) for item_id, units in supplies.items()):
            return "No hay tanto de eso que sea de todos"
        if self.worth_of(world, supplies) < self.needs(world, zone):
            return f"Con eso no llega hasta {self.name_of(world, zone)}"
        return None

    def plan(self, world: "SimulationWorld", resident_id: str, zone_id: str, supplies: Mapping[str, int]) -> TripResult:
        """Make a trip ready for somebody: how far, and what is handed to them to get there,
        which leaves the stores at once. They go on it the next time they set out. A trip
        made ready before is undone first, and what was handed over for it put back."""
        supplies = {str(item_id): int(units) for item_id, units in supplies.items() if int(units) > 0}
        resident = world.residents.get(resident_id)
        held = dict(resident.outing.supplies) if resident is not None and resident.outing is not None else {}
        error = self.obstacle(world, resident_id, zone_id, supplies, held)
        if error is not None:
            return TripResult(False, error)
        zone = world.registries.expeditions.zone(zone_id)
        # Only what is more than they already held leaves the stores, and what is less is theirs to carry back.
        self._take(world, {item_id: units - held.get(item_id, 0) for item_id, units in supplies.items()})
        self._put_back(world, resident, {item_id: units - supplies.get(item_id, 0) for item_id, units in held.items()})
        resident.outing = Outing(zone.zone_id, supplies)
        name = self.name_of(world, zone)
        world.emit_event(
            DomainEvent(
                TRIP_PLANNED_EVENT,
                TRIP_PLANNED_IMPORTANCE,
                f"{resident.name} tiene listo un viaje hasta {name}",
                [resident.resident_id],
                data={"resident_id": resident.resident_id, "zone": zone.zone_id, "supplies": dict(supplies)},
            ),
            at=resident.tile,
        )
        return TripResult(True, f"{resident.name} irá hasta {name} la próxima vez que salga")

    def cancel(self, world: "SimulationWorld", resident_id: str) -> TripResult:
        """Undo the trip made ready for somebody: what was handed over goes back where it is kept."""
        resident = world.residents.get(resident_id)
        if resident is None or resident.outing is None:
            return TripResult(False, "No hay ningún viaje preparado")
        self._put_back(world, resident, resident.outing.supplies)
        resident.outing = None
        return TripResult(True, f"{resident.name} saldrá como cualquier día")

    def _take(self, world: "SimulationWorld", supplies: Mapping[str, int]) -> None:
        """Take units of things that are everybody's out of wherever they are kept."""
        for item_id, units in supplies.items():
            if units <= 0:
                continue
            left = units
            for inventory in world.containers.values():
                for item in list(inventory.items):
                    if left > 0 and item.definition_id == item_id and item.owner_id is None:
                        left -= inventory.take_units(item.instance_id, min(left, item.quantity))
            world.ledger.record(world, item_id, -(units - left), PACKED)

    def _put_back(self, world: "SimulationWorld", resident: Resident, supplies: Mapping[str, int]) -> None:
        """Give back provisions that are not gone out with: they are in the hands of whoever
        they were for, and nobody's, to be carried where such things are kept as finds are."""
        for item_id, units in supplies.items():
            if units > 0 and world.registries.items.find(item_id) is not None:
                world.stock(resident.inventory, item_id, units, None)
                world.ledger.record(world, item_id, units, UNPACKED, by=resident.resident_id)

    def levelled(self, world: "SimulationWorld", resident: Resident, job: JobDefinition, level: int) -> None:
        """Somebody has come to a level of a job done out there: with it they come on the
        next zone of the line, if nobody had yet. It is the settlement's to name and to draw."""
        line = world.registries.expeditions.line
        if job.expedition is None or not 1 < level <= len(line):
            return
        zone = line[level - 1]
        if zone.zone_id in world.zones:
            return
        world.zones[zone.zone_id] = ZoneFound(by=resident.resident_id, day=world.clock.day)
        world.emit_event(
            DomainEvent(
                ZONE_FOUND_EVENT,
                ZONE_FOUND_IMPORTANCE,
                f"¡{resident.name} ha encontrado una nueva zona! Más allá de lo conocido está {zone.name}",
                [resident.resident_id],
                data={"resident_id": resident.resident_id, "zone": zone.zone_id, "level": level},
            ),
            at=None if resident.away else resident.tile,
        )

    def rename(self, world: "SimulationWorld", zone_id: str, name: str) -> TripResult:
        """Say what a zone the settlement knows of is called. With no name, what the game calls it."""
        zone = world.registries.expeditions.zone(zone_id)
        if zone is None or not self.is_found(world, zone):
            return TripResult(False, "No hay tal zona que nombrar")
        name = " ".join(str(name).split())[:ZONE_NAME_LENGTH].strip()
        found = world.zones.setdefault(zone.zone_id, ZoneFound())
        if found.name == name:
            return TripResult(True, f"Se llama {self.name_of(world, zone)}")
        found.name = name
        world.emit_event(
            DomainEvent(
                ZONE_NAMED_EVENT,
                ZONE_NAMED_IMPORTANCE,
                f"Lo que hay ahí fuera tiene nombre: {self.name_of(world, zone)}",
                [],
                data={"zone": zone.zone_id, "name": name},
            )
        )
        return TripResult(True, f"Se llama {self.name_of(world, zone)}")

    def set_out(self, world: "SimulationWorld", resident: Resident, job: JobDefinition) -> None:
        """Send a resident out. From here on they are away: nobody sees them and they see nobody."""
        rule, settings = job.expedition, world.registries.expeditions
        now = world.clock.total_minutes
        minutes = world.rng.randint(*rule.minutes)
        # Where the player has made a trip ready for them to, and through what. Left to
        # themselves they keep to the first zone there is.
        outing, resident.outing = resident.outing, None
        aim = settings.zone(outing.zone) if outing is not None else None
        if aim is not None and aim not in self.reach(world, resident):
            aim = None
        route = self.route_to(world, aim) if aim is not None else list(settings.line[:1])
        # What a trip to the first zone takes, and on top of it what every zone past that adds.
        near = minutes
        minutes += sum(zone.minutes for zone in (route[1:] if len(route) > 1 else route) if zone is not settings.line[0])
        # What has been worked out about going outside brings more back, and brings it back safer.
        finds = round(
            world.rng.randint(*rule.finds)
            * world.research.factor(world, EXPEDITION_FINDS)
            * world.attributes.factor(world, resident, SENSES, "finds")
            * world.crafts.pace(world, resident, job)
        )
        wary = max(0.0, 2.0 - world.attributes.factor(world, resident, SENSES, "danger"))
        comes_on_something = world.rng.random() < settings.find_chance
        resident.expedition = Expedition(
            returns_at=now + minutes,
            finds=finds,
            danger=min(1.0, (rule.danger + sum(zone.danger for zone in route)) * world.research.factor(world, EXPEDITION_DANGER) * wary),
            find_at=now + minutes // 2 if comes_on_something else None,
            left_at=now,
            # Half the trip is the way out, and what there is to come on is at the far end of it.
            turns_at=now + minutes // 2,
            out_minutes=minutes // 2,
            supplies=dict(outing.supplies) if outing is not None and aim is not None else {},
        )
        trip = resident.expedition
        if outing is not None and aim is None:
            # Made ready for somewhere they can no longer get to: what was handed over is theirs to carry back.
            self._put_back(world, resident, outing.supplies)
        zone = route[-1] if route else None
        trip.zone = zone.zone_id if zone is not None else None
        trip.finds += zone.more if zone is not None else 0
        if len(route) > 1:
            trip.route = [crossed.zone_id for crossed in route]
            # Each zone takes of the way what it takes of the time: the first, what a trip to it does.
            lengths = [near, *(crossed.minutes for crossed in route[1:])]
            gone = 0.0
            for length in lengths:
                gone += length / max(1, minutes)
                trip.stages.append(min(1.0, gone))
            trip.stages[-1] = 1.0
            if comes_on_something:
                # Far from home what is come on may be anywhere along the way, and turning
                # back from it is not getting there. Drawn apart from everything else.
                dice = SimulationRNG.keyed(world.rng.seed, "find_at", resident.resident_id, now)
                share = EARLIEST_FIND + (1.0 - EARLIEST_FIND) * dice.random()
                trip.find_at = now + max(1, round(trip.out_minutes * share))
        # Whoever knows of a place out there goes to it in its turn, for what is brought from it.
        bound = world.crafts.destination(world, resident)
        said = job.text if aim is None else f"sale del asentamiento hacia {self.name_of(world, aim)}"
        if bound is not None and world.registries.items.find(bound[1].fetch or "") is not None:
            place, brings = bound
            resident.expedition.fetch = brings.fetch
            resident.expedition.place = place.discovery_id
            resident.expedition.finds = max(1, resident.expedition.finds + brings.finds)
            said = f"sale del asentamiento hacia {place.name}"
        # Who lies in wait along the way, zone by zone (S70).
        trip.raids_at = world.raids.ahead(world, resident, trip)
        resident.last_expedition_day = world.clock.day
        resident.activity = Activity(EXPEDITION_ACTION, resident.post_id, minutes_left=minutes, using=True)
        resident.current_action = EXPEDITION_ACTION
        world.emit_event(
            DomainEvent(
                "expedition_left", LEFT_IMPORTANCE, f"{resident.name} {said}", [resident.resident_id],
                data={
                    **({"place": bound[0].discovery_id} if bound is not None else {}),
                    **({"zone": zone.zone_id} if zone is not None else {}),
                },
            ),
            at=resident.tile,
        )

    def tick(self, world: "SimulationWorld", resident: Resident, activity: Activity) -> None:
        """Spend one minute out there."""
        trip = resident.expedition
        job = world.work.job_of(world, resident)
        if trip is None:
            resident.activity = None
            resident.current_action = "idle"
            return
        if job is not None:
            world.trade.pay_wage(world, resident, job)
            world.crafts.worked(world, resident, job)
        now = world.clock.total_minutes
        if trip.raid is not None:
            # Raiders in the way: nobody gets any further until that is over.
            trip.wait()
            activity.minutes_left = max(1, trip.returns_at - now)
            world.raids.tick(world, resident, trip)
            return
        activity.minutes_left = max(1, trip.returns_at - now)
        if trip.raids_at and now >= trip.turns_at:
            # Whoever has turned for home meets nobody they did not meet on the way out.
            trip.raids_at = []
        if trip.raids_at and now >= trip.raids_at[0] and world.interventions.pending_for(world, resident.resident_id) is None:
            trip.raids_at.pop(0)
            world.raids.meet(world, resident, trip)
            return
        if trip.find_at is not None and now >= trip.find_at:
            trip.find_at = None
            # Whether to risk it is theirs to decide, and the player's to advise on.
            world.interventions.ask(world, resident, RISKY_FIND)
        if now >= trip.returns_at and world.interventions.pending_for(world, resident.resident_id) is None:
            self._come_back(world, resident, trip)

    def choose(self, world: "SimulationWorld", resident: Resident, choice: str) -> None:
        """Carry out what a resident decided about a risky find, or about raiders in their way."""
        trip, settings = resident.expedition, world.registries.expeditions
        if trip is None:
            return
        if choice in RAID_CHOICES:
            world.raids.choose(world, resident, choice)
            return
        if choice == PUSH_ON:
            trip.finds += settings.push_on_finds
            trip.risked = True
            trip.danger = min(1.0, trip.danger + settings.push_on_danger)
            trip.returns_at += settings.push_on_minutes
            # Further in for half of what it adds, and the other half is that much more way back.
            now = world.clock.total_minutes
            trip.turns_at = min(trip.returns_at, max(trip.turns_at, now + settings.push_on_minutes // 2))
        elif choice == TURN_BACK:
            trip.finds = trip.finds // 2
            now = world.clock.total_minutes
            # From past the first zone the way home is as long as the way there was.
            back = max(settings.turn_back_minutes, now - trip.left_at) if trip.route else settings.turn_back_minutes
            trip.returns_at = min(trip.returns_at, now + back)
            # They turn round where they stand.
            trip.turns_at = min(trip.turns_at, now)

    def _come_back(self, world: "SimulationWorld", resident: Resident, trip: Expedition) -> None:
        settings = world.registries.expeditions
        resident.expedition = None
        resident.activity = None
        resident.current_action = "idle"
        # Somebody may be standing where they set out from.
        resident.x, resident.y = free_tile(world, resident.tile, resident)
        # What there is where they got to: the zone they set out for, or the one they turned round in.
        far = settings.zone(trip.furthest())
        table = far.loot if far is not None and far.loot else settings.loot
        loot = [entry for entry in table if world.registries.items.find(entry.item) is not None]
        rare, likelier = (far.rare, far.finds) if far is not None else (1.0, 1.0)
        found: dict[str, int] = {}
        if trip.fetch is not None and world.registries.items.find(trip.fetch) is not None:
            # They went out for one thing, and it is what they bring.
            found, loot = ({trip.fetch: trip.finds} if trip.finds > 0 else {}), []
        for _ in range(trip.finds if loot else 0):
            # A weighted draw: the heavier a thing is in the table, the oftener it turns up.
            mark = world.rng.random() * sum(entry.weight for entry in loot)
            for entry in loot:
                mark -= entry.weight
                if mark < 0:
                    break
            found[entry.item] = found.get(entry.item, 0) + 1
        haul = ", ".join(f"{world.registries.items.resolve(item_id).name} ({units})" for item_id, units in found.items())
        kept = self._keeps(world, resident, found) if trip.fetch is None else None
        # How rare each thing is is drawn apart from everything else, so that it changes
        # nothing of what is found or of what happens after (S64).
        dice = SimulationRNG.keyed(world.rng.seed, "found", resident.resident_id, world.clock.total_minutes)
        if kept is not None:
            found[kept] -= 1
            world.stock(resident.inventory, kept, 1, resident.resident_id, world.upgrades.found_level(world, dice, trip.risked, rare))
        for item_id, units in found.items():
            for _ in range(max(0, units)):
                world.stock(resident.inventory, item_id, 1, None, world.upgrades.found_level(world, dice, trip.risked, rare))
            if units > 0:
                world.ledger.record(world, item_id, units, FOUND, by=resident.resident_id)
        # Whoever turned round before getting there brings back what they did not use of
        # what was handed to them: of each thing, as much as there was of the way left to go.
        unused = 1.0 - trip.got_to()
        for item_id, units in trip.supplies.items():
            # What was taken along to mend oneself with comes back whole, what there is left of it.
            left = units if self.is_kit(world, item_id) else int(units * unused)
            if left > 0 and world.registries.items.find(item_id) is not None:
                world.stock(resident.inventory, item_id, left, None)
                world.ledger.record(world, item_id, left, UNPACKED, by=resident.resident_id)
        # Now and then there is something among it that nobody knows (S59), the oftener the further.
        world.finds.maybe(world, "expedition", resident, likelier=likelier)
        said = f"{resident.name} vuelve de fuera con {haul}" if haul else f"{resident.name} vuelve de fuera de vacío"
        if kept is not None:
            mine = world.registries.items.resolve(kept)
            said = f"{said}, y se queda {mine.article} {mine.name}"
        world.emit_event(
            DomainEvent(
                "expedition_returned",
                RETURN_IMPORTANCE,
                said,
                [resident.resident_id],
                data={"found": dict(found), "kept": kept},
            ),
            at=resident.tile,
        )
        if world.rng.random() < trip.danger:
            world.health.hurt(world, resident, world.rng.randint(*settings.injury), settings.injury_kind, INJURY_CAUSE)

    def _keeps(self, world: "SimulationWorld", resident: Resident, found: dict[str, int]) -> str | None:
        """The one thing of a trip that whoever made it keeps for themselves, under barter: there
        is no wage, and it is how anybody comes by something of their own. It is the thing worth
        most to them, and never what the settlement runs on."""
        if world.fund.currency(world) is not None:
            return None
        common = set(world.registries.economy.common_finds)
        resolve = world.registries.items.resolve
        choices = [item_id for item_id in found if not common & set(resolve(item_id).tags)]
        return max(
            choices,
            key=lambda item_id: (world.items.personal_value(world, resident, resolve(item_id)), item_id),
            default=None,
        )

    # ----- bringing the finds where they go -----

    def _finds_on(self, world: "SimulationWorld", resident: Resident) -> list[ItemInstance]:
        """What a resident carries that is nobody's yet. Not what a site is waiting for: that goes there."""
        return [
            item
            for item in resident.inventory.items
            if item.owner_id is None and not world.construction.awaits(world, item)
        ]

    def _goes_to(self, world: "SimulationWorld", item: ItemInstance) -> str | None:
        """The kind of container a find is taken to: the first it belongs in that the settlement has.

        A settlement with no shop or scrap pile yet still has somewhere to put what is brought
        back, so that nobody is left holding it and unable to set out again.
        """
        tags = world.registries.items.resolve(item.definition_id).tags
        kinds = {placed.kind for placed in world.interactables.values()}
        fitting = [
            rule.to
            for rule in world.registries.expeditions.deliveries
            if (rule.tag is None or rule.tag in tags) and (rule.needs is None or rule.needs in kinds)
        ]
        return next((kind for kind in fitting if containers_of_kind(world, kind)), fitting[0] if fitting else None)

    def errand(self, world: "SimulationWorld", resident: Resident) -> str | None:
        """The container to walk to with what was brought back: the nearest that takes the first find."""
        for item in self._finds_on(world, resident):
            kind = self._goes_to(world, item)
            places = [world.interactables[object_id] for object_id, _ in containers_of_kind(world, kind or "")]
            if places:
                return min(places, key=lambda p: (manhattan(resident.tile, (p.x, p.y)), p.object_id)).object_id
        return None

    def unload(self, world: "SimulationWorld", resident: Resident, placed: Interactable) -> str | None:
        """Leave in a container everything carried that belongs there. Returns what was done, or None."""
        container = world.containers.get(placed.object_id)
        if container is None:
            return None
        # What is left is told by the kind of thing, however many rarities of it there were (S64).
        units: dict[str, int] = {}
        for item in self._finds_on(world, resident):
            if self._goes_to(world, item) != placed.kind:
                continue
            resident.inventory.remove(item.instance_id)
            world.stock(container, item.definition_id, item.quantity, None, item.level, item.freshness)
            units[item.definition_id] = units.get(item.definition_id, 0) + item.quantity
        if not units:
            return None
        left = [f"{world.registries.items.resolve(item_id).name} ({count})" for item_id, count in units.items()]
        definition = world.definition_of(placed)
        return f"deja {', '.join(left)} en {definition.article} {definition.name}"
