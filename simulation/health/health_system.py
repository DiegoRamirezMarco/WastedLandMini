"""Injuries, healing, and what happens when someone dies."""

from typing import TYPE_CHECKING

from simulation.events.event import DomainEvent
from simulation.health.injury import Death, Injury, InjuryDefinition, LimbDefinition
from simulation.items.item import ItemInstance
from simulation.residents.activity import MOVE_TILES_PER_MINUTE
from simulation.residents.resident import Resident
from simulation.social.interaction import InteractionDefinition
from world.interactable import Interactable, UseDefinition

if TYPE_CHECKING:
    from simulation.world import SimulationWorld

MINUTES_PER_DAY = 24 * 60
# Below this, a resident is in no state to work.
UNFIT_HEALTH = 40.0
# Below this, a resident looks for somewhere to be looked after.
SEEK_CARE_HEALTH = 85.0
# At or above this, someone resting to recover gets up.
RECOVERED_HEALTH = 95.0
CARE_APPEAL = 1.5
# Healing while lying down without a medic, as a multiple of healing on one's feet.
BED_REST_BONUS = 2.0
# A single blow at least this hard breaks something.
FRACTURE_DAMAGE = 28.0
INJURY_IMPORTANCE = 45
LIMB_LOSS_IMPORTANCE = 85
# A need counts as left at its worst from here, and falling ill of it is worth a look from the player.
WORST_NEED = 99.5
PRIVATION_IMPORTANCE = 60
DEATH_IMPORTANCE = 95
GRAVE_KIND = "grave"
DEFAULT_INJURY = "bruise"


class HealthSystem:
    def is_fit_for_work(self, resident: Resident) -> bool:
        return resident.health >= UNFIT_HEALTH

    def work_pace(self, world: "SimulationWorld", resident: Resident) -> float:
        """How fast a resident gets on with their work, from 0 to 1, for the limbs they are short of."""
        pace = 1.0
        for limb_id in resident.lost_limbs:
            limb = world.registries.limbs.get(limb_id)
            pace *= limb.work_pace if limb is not None else 1.0
        return pace

    def walk_tiles(self, world: "SimulationWorld", resident: Resident) -> int:
        """Tiles a resident covers in a minute. Short of a leg they still get there, slowly."""
        pace = 1.0
        for limb_id in resident.lost_limbs:
            limb = world.registries.limbs.get(limb_id)
            pace *= limb.walk_pace if limb is not None else 1.0
        return max(1, round(MOVE_TILES_PER_MINUTE * pace))

    def care_use(self, world: "SimulationWorld", resident: Resident) -> UseDefinition | None:
        """The healing use a resident is lying in right now, if any."""
        activity = resident.activity
        if activity is None or not activity.using or activity.target_id is None:
            return None
        placed = world.interactables.get(activity.target_id)
        use = world.definition_of(placed).use if placed is not None else None
        return use if use is not None and use.heals else None

    def care_score(self, resident: Resident) -> float:
        """How much a resident wants to lie down and be looked after."""
        if resident.health >= SEEK_CARE_HEALTH:
            return 0.0
        return (100.0 - resident.health) / 100.0 * CARE_APPEAL

    def tick(self, world: "SimulationWorld", resident: Resident) -> None:
        """Let a resident's injuries mend for one minute, or grow if they come of going without.

        Whoever is left with nothing to drink or eat sickens of it, and in the end dies.
        """
        wasting = self._go_without(world, resident)
        if resident.resident_id not in world.residents or not resident.injuries:
            return
        care = self.care_use(world, resident)
        treated = care is not None and (care.care_job is None or world.work.is_staffed(world, care.care_job))
        resting = care is not None or not world.is_aware(resident)
        for injury in resident.injuries:
            if injury.kind in wasting:
                # Nothing mends while what brought it on goes on.
                continue
            definition = world.registries.injuries.get(injury.kind)
            if definition is None:
                # An injury of a kind that is no longer defined simply fades.
                rate = 10.0
            elif treated:
                rate = definition.treated_per_day
            else:
                rate = definition.heal_per_day * (BED_REST_BONUS if resting else 1.0)
            injury.severity -= rate / MINUTES_PER_DAY
        resident.injuries = [injury for injury in resident.injuries if injury.severity > 0]

    def _go_without(self, world: "SimulationWorld", resident: Resident) -> set[str]:
        """Worsen what a resident suffers from a need left at its worst. Returns the kinds that grew."""
        wasting: set[str] = set()
        for kind, definition in world.registries.injuries.items():
            if definition.from_need is None or getattr(resident.needs, definition.from_need, 0.0) < WORST_NEED:
                continue
            wasting.add(kind)
            injury = next((injury for injury in resident.injuries if injury.kind == kind), None)
            if injury is None:
                injury = Injury(kind, 0.0)
                resident.injuries.append(injury)
                room = world.room_at(resident.tile)
                world.emit_event(
                    DomainEvent(
                        "privation",
                        PRIVATION_IMPORTANCE,
                        f"{resident.name} empieza a sufrir {definition.name}",
                        [resident.resident_id],
                        location_id=room.room_id if room is not None else None,
                        data={"kind": kind, "need": definition.from_need},
                    ),
                    at=None if resident.away else resident.tile,
                )
            injury.severity += definition.worsens_per_day / MINUTES_PER_DAY
            if resident.health <= 0:
                self.die(world, resident, f"sufrir {definition.name}")
                break
        return wasting

    def weapon_item(self, world: "SimulationWorld", resident: Resident) -> ItemInstance | None:
        """The best weapon a resident carries that is in a state to be used, if they have one."""
        best: tuple[float, ItemInstance] | None = None
        for item in resident.inventory.items:
            damage = world.registries.items.resolve(item.definition_id).properties.get("damage", 0.0)
            if not item.broken and damage > (best[0] if best is not None else 1.0):
                best = (damage, item)
        return best[1] if best is not None else None

    def weapon_of(self, world: "SimulationWorld", resident: Resident) -> tuple[float, tuple[str, ...]]:
        """Damage multiplier and tags of the best weapon a resident carries. Bare hands are 1."""
        weapon = self.weapon_item(world, resident)
        if weapon is None:
            return (1.0, ())
        definition = world.registries.items.resolve(weapon.definition_id)
        return (definition.properties.get("damage", 1.0), definition.tags)

    def fight_damage(
        self, world: "SimulationWorld", victim: Resident, attacker: Resident, definition: InteractionDefinition
    ) -> bool:
        """Hurt `victim` with what `attacker` dealt them in a fight. Returns False if it killed them."""
        if definition.damage is None:
            return True
        low, high = definition.damage
        strength = (0.6 + attacker.personality.aggression / 125.0) * max(0.5, attacker.health / 100.0)
        multiplier, tags = self.weapon_of(world, attacker)
        weapon = self.weapon_item(world, attacker)
        if weapon is not None:
            world.items.wear(world, attacker, weapon)
        amount = world.rng.randint(low, high) * strength * multiplier
        kind = "cut" if "blade" in tags else ("fracture" if amount >= FRACTURE_DAMAGE else DEFAULT_INJURY)
        return self.hurt(world, victim, amount, kind, f"una pelea con {attacker.name}", attacker)

    def hurt(
        self,
        world: "SimulationWorld",
        resident: Resident,
        amount: float,
        kind: str,
        cause: str,
        by: Resident | None = None,
    ) -> bool:
        """Give a resident an injury. Returns False if they died of it."""
        if kind not in world.registries.injuries:
            kind = DEFAULT_INJURY
        resident.injuries.append(Injury(kind, amount))
        if resident.health <= 0:
            self.die(world, resident, cause, by)
            return False
        definition = world.registries.injuries.get(kind)
        room = world.room_at(resident.tile)
        details = {"amount": amount, "kind": kind, "by": by.resident_id if by is not None else None}
        limb = self._lose_limb(world, resident, amount, definition)
        if limb is not None:
            world.emit_event(
                DomainEvent(
                    "limb_lost",
                    LIMB_LOSS_IMPORTANCE,
                    f"{resident.name} pierde {limb.name} en {cause}",
                    [resident.resident_id],
                    location_id=room.room_id if room is not None else None,
                    data={**details, "limb": limb.limb_id},
                ),
                at=resident.tile,
                fact_text=f"{resident.name} perdió {limb.name} en {cause}",
            )
            return True
        world.emit_event(
            DomainEvent(
                "injured",
                INJURY_IMPORTANCE,
                f"{resident.name} sale con {definition.name if definition else 'heridas'} de {cause}",
                [resident.resident_id],
                location_id=room.room_id if room is not None else None,
                data=details,
            ),
            at=resident.tile,
        )
        return True

    def _lose_limb(
        self, world: "SimulationWorld", resident: Resident, amount: float, definition: InjuryDefinition | None
    ) -> LimbDefinition | None:
        """Take a limb off a resident if the injury they just got was of a kind and a severity to do it."""
        if definition is None or definition.severs_from is None or amount < definition.severs_from:
            return None
        left = [limb for limb_id, limb in world.registries.limbs.items() if limb_id not in resident.lost_limbs]
        if not left or world.rng.random() >= definition.severs_chance:
            return None
        limb = world.rng.choice(left)
        resident.lost_limbs.append(limb.limb_id)
        return limb

    def die(self, world: "SimulationWorld", resident: Resident, cause: str, killer: Resident | None = None) -> None:
        """Remove a resident from the living and deal with everything they leave behind."""
        dead_id, tile, away = resident.resident_id, resident.tile, resident.away
        room = world.room_at(tile)
        del world.residents[dead_id]
        resident.activity = None

        for other in world.residents.values():
            if other.activity is not None and other.activity.partner_id == dead_id:
                other.activity = None
                other.current_action = "idle"
            if other.couple_with == dead_id:
                other.couple_with = None
        for decision in list(world.decisions.values()):
            if decision.resident_id == dead_id or (decision.crisis and decision.crisis.target_id == dead_id):
                del world.decisions[decision.decision_id]
        # What they owned now belongs to everyone; what they carried is put away nearby.
        for inventory in [*world.containers.values(), *(other.inventory for other in world.residents.values())]:
            for item in inventory.items:
                if item.owner_id == dead_id:
                    item.owner_id = None
        nearest = world.nearest_container(tile)
        for item in resident.inventory.items:
            item.owner_id = None if item.owner_id == dead_id else item.owner_id
            if nearest is not None:
                world.containers[nearest].add(item)
        resident.inventory.items.clear()

        grave_id = self._dig_grave(world, dead_id)
        world.deaths.append(
            Death(dead_id, resident.name, world.clock.total_minutes, cause, killer.resident_id if killer else None, grave_id)
        )
        event = DomainEvent(
            "death",
            DEATH_IMPORTANCE,
            f"{resident.name} ha muerto tras {cause}",
            [killer.resident_id] if killer is not None else [],
            location_id=room.room_id if room is not None else None,
            # Where the body falls, unless they died out of sight beyond the fence.
            data={
                "resident_id": dead_id,
                "tile": None if away else list(tile),
                "by": killer.resident_id if killer is not None else None,
                "lost_limbs": list(resident.lost_limbs),
            },
        )
        subjects = [killer.resident_id, dead_id] if killer is not None else [dead_id]
        world.emit_event(event, at=tile, fact_text=f"{resident.name} murió tras {cause}", subjects=subjects)

    def _dig_grave(self, world: "SimulationWorld", dead_id: str) -> str | None:
        """Put a grave on the first free plot of the map's graveyard, if it has one."""
        layout = world.registries.maps.get(world.map_id)
        if layout is None or world.registries.interactables.find(GRAVE_KIND) is None:
            return None
        used = {(placed.x, placed.y) for placed in world.interactables.values()}
        for plot in layout.graves:
            if plot not in used:
                grave_id = f"grave_{dead_id}"
                world.interactables[grave_id] = Interactable(grave_id, GRAVE_KIND, plot[0], plot[1])
                return grave_id
        return None
