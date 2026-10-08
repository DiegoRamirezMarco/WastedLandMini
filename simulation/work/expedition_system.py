"""Scavenging outside: setting out, what happens out there, and bringing the finds home."""

from typing import TYPE_CHECKING

from simulation.residents.attributes import SENSES
from simulation.ai.crowd import free_tile
from simulation.events.event import DomainEvent
from simulation.events.world_event import WEATHER
from simulation.items.item import ItemInstance
from simulation.residents.activity import Activity
from simulation.residents.resident import Resident
from simulation.work.expedition import PUSH_ON, TURN_BACK, Expedition
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

    def set_out(self, world: "SimulationWorld", resident: Resident, job: JobDefinition) -> None:
        """Send a resident out. From here on they are away: nobody sees them and they see nobody."""
        rule, settings = job.expedition, world.registries.expeditions
        now = world.clock.total_minutes
        minutes = world.rng.randint(*rule.minutes)
        # What has been worked out about going outside brings more back, and brings it back safer.
        finds = round(
            world.rng.randint(*rule.finds)
            * world.research.factor(world, EXPEDITION_FINDS)
            * world.attributes.factor(world, resident, SENSES, "finds")
        )
        wary = max(0.0, 2.0 - world.attributes.factor(world, resident, SENSES, "danger"))
        comes_on_something = world.rng.random() < settings.find_chance
        resident.expedition = Expedition(
            returns_at=now + minutes,
            finds=finds,
            danger=rule.danger * world.research.factor(world, EXPEDITION_DANGER) * wary,
            find_at=now + minutes // 2 if comes_on_something else None,
        )
        resident.last_expedition_day = world.clock.day
        resident.activity = Activity(EXPEDITION_ACTION, resident.post_id, minutes_left=minutes, using=True)
        resident.current_action = EXPEDITION_ACTION
        world.emit_event(
            DomainEvent("expedition_left", LEFT_IMPORTANCE, f"{resident.name} {job.text}", [resident.resident_id]),
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
        now = world.clock.total_minutes
        activity.minutes_left = max(1, trip.returns_at - now)
        if trip.find_at is not None and now >= trip.find_at:
            trip.find_at = None
            # Whether to risk it is theirs to decide, and the player's to advise on.
            world.interventions.ask(world, resident, RISKY_FIND)
        if now >= trip.returns_at and world.interventions.pending_for(world, resident.resident_id) is None:
            self._come_back(world, resident, trip)

    def choose(self, world: "SimulationWorld", resident: Resident, choice: str) -> None:
        """Carry out what a resident decided about a risky find."""
        trip, settings = resident.expedition, world.registries.expeditions
        if trip is None:
            return
        if choice == PUSH_ON:
            trip.finds += settings.push_on_finds
            trip.danger = min(1.0, trip.danger + settings.push_on_danger)
            trip.returns_at += settings.push_on_minutes
        elif choice == TURN_BACK:
            trip.finds = trip.finds // 2
            trip.returns_at = min(trip.returns_at, world.clock.total_minutes + settings.turn_back_minutes)

    def _come_back(self, world: "SimulationWorld", resident: Resident, trip: Expedition) -> None:
        settings = world.registries.expeditions
        resident.expedition = None
        resident.activity = None
        resident.current_action = "idle"
        # Somebody may be standing where they set out from.
        resident.x, resident.y = free_tile(world, resident.tile, resident)
        loot = [entry for entry in settings.loot if world.registries.items.find(entry.item) is not None]
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
        if kept is not None:
            found[kept] -= 1
            world.stock(resident.inventory, kept, 1, resident.resident_id)
        for item_id, units in found.items():
            if units > 0:
                world.stock(resident.inventory, item_id, units, None)
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
        left = []
        for item in self._finds_on(world, resident):
            if self._goes_to(world, item) != placed.kind:
                continue
            resident.inventory.remove(item.instance_id)
            world.stock(container, item.definition_id, item.quantity, None)
            left.append(f"{world.registries.items.resolve(item.definition_id).name} ({item.quantity})")
        if not left:
            return None
        definition = world.definition_of(placed)
        return f"deja {', '.join(left)} en {definition.article} {definition.name}"
