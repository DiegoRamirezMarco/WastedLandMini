"""Raiders come on out there (S70): who they are, what is done about them, the fight if it
comes to one, and what is left of whoever was in it.

Each zone a trip goes through may have somebody lying in wait, the likelier the further it
is. Whoever comes on them decides what to do, as with anything else worth a risk, and the
player may advise. If it comes to blows the fight waits a while for the player to watch it,
and to have a hand in it; nobody watching, it is fought out by itself. What is lost in it
stays lost: they go on with the health they have left, and only what they carry to mend
themselves gives any of it back.
"""

from typing import TYPE_CHECKING

from simulation.combat.encounter import (
    FIGHT,
    PAY,
    RUN,
    Aftermath,
    aftermath,
    decide_alone,
    hero,
    payable,
    price,
    raider,
    raiders,
)
from simulation.combat.model import MELEE, CombatData, Fighter, Weapon
from simulation.combat.rules import FLED, LOST, WON, Event, Fight
from simulation.economy.ledger import DOSED, FOUND, RAIDED
from simulation.events.event import DomainEvent
from simulation.items.item import ItemInstance
from simulation.residents.resident import Resident
from simulation.rng import SimulationRNG
from simulation.work.expedition import Expedition, Raid

if TYPE_CHECKING:
    from simulation.world import SimulationWorld

RAIDERS_MET = "raiders_met"
RAID_FOUGHT_EVENT = "raid_fight"
RAID_OVER_EVENT = "raid_over"
RAID_IMPORTANCE = 70.0
# What the player may do in a fight they are watching.
CRIT, TARGET, HEAL, SHOVE, FLEE, STANCE, HANDS_OFF = "crit", "target", "heal", "shove", "flee", "stance", "hands_off"


class RaidSystem:
    def __init__(self) -> None:
        # The fights being watched, by whose they are. Nothing of them is kept: one that is
        # not over when the game is left starts again when it is come back to.
        self.live: dict[str, Fight] = {}

    def data(self, world: "SimulationWorld") -> CombatData:
        return world.registries.combat

    # ----- on the way -----

    def ahead(self, world: "SimulationWorld", resident: Resident, trip: Expedition) -> list[int]:
        """The game minutes at which a trip that is setting out comes on raiders: for each zone
        it goes through, maybe once, somewhere along its stretch of the way out. Drawn apart
        from everything else, so that it moves nothing else on."""
        data = self.data(world)
        if not data.zones:
            return []
        zones = trip.route or ([trip.zone] if trip.zone is not None else [])
        ends = trip.stages if trip.route else [1.0]
        way = trip.out_minutes if trip.out_minutes > 0 else trip.turns_at - trip.left_at
        low, high = world.registries.expeditions.raid_stretch
        found, start = [], 0.0
        for zone_id, end in zip(zones, ends):
            dice = SimulationRNG.keyed(world.rng.seed, "raid_at", resident.resident_id, trip.left_at, zone_id)
            if dice.random() < data.zone(zone_id).chance:
                share = start + (end - start) * (low + (high - low) * dice.random())
                found.append(trip.left_at + max(1, round(way * share)))
            start = end
        return sorted(found)

    def meet(self, world: "SimulationWorld", resident: Resident, trip: Expedition) -> None:
        """They come on raiders where they are: who those are is settled, and what to do about
        them is theirs to decide, with the player to advise."""
        now = world.clock.total_minutes
        zone_id = trip.zone_at(now)
        dice = SimulationRNG.keyed(world.rng.seed, "raiders", resident.resident_id, now)
        band = raiders(self.data(world), zone_id or "", dice)
        trip.raid = Raid(zone_id or "", now, [[foe.kind, foe.level] for foe in band])
        if world.interventions.ask(world, resident, RAIDERS_MET) is None:
            # Nobody to ask and nothing to ask with: they do as they are.
            fight = self.fight(world, resident)
            carried = self.carried(trip)
            self.choose(world, resident, decide_alone(fight, resident.personality.courage / 100.0, carried, self.data(world)))

    def carried(self, trip: Expedition) -> int:
        """How much somebody out there has on them that could be handed over to be let by: what
        they have found so far, and what they were handed to get there."""
        return max(0, trip.finds) + sum(max(0, units) for units in trip.supplies.values())

    def choose(self, world: "SimulationWorld", resident: Resident, choice: str) -> None:
        """Carry out what somebody decided on coming on raiders: hand over what they ask, run
        for it, or fight. Whoever cannot pay runs, and whoever is caught fights."""
        trip = resident.expedition
        raid = trip.raid if trip is not None else None
        if raid is None or raid.due is not None:
            return
        data = self.data(world)
        fight = self.fight(world, resident)
        cost = price(data, fight.foes)
        if choice == PAY and payable(fight.foes) and self.carried(trip) >= cost:
            self._hand_over(world, resident, trip, cost)
            self._over(world, resident, trip, PAY, f"{resident.name} les da lo que piden y le dejan pasar", {"paid": cost})
            return
        if choice in (RUN, PAY):
            dice = SimulationRNG.keyed(world.rng.seed, "run", resident.resident_id, raid.met_at)
            if dice.random() < fight.flee_chance(before=True):
                self._head_home(world, trip)
                self._over(world, resident, trip, FLED, f"{resident.name} les da esquinazo y se vuelve")
                return
        # It comes to blows: for a while it waits for whoever wants to see it.
        raid.due = world.clock.total_minutes + world.registries.expeditions.raid_wait
        zone = world.registries.expeditions.zone(raid.zone)
        where = world.expeditions.name_of(world, zone) if zone is not None else "ahí fuera"
        world.emit_event(
            DomainEvent(
                RAID_FOUGHT_EVENT, RAID_IMPORTANCE, f"{resident.name} se lía a golpes con quien le cerraba el paso en {where}",
                [resident.resident_id], data={"resident_id": resident.resident_id, "zone": raid.zone, "foes": [list(foe) for foe in raid.foes]},
            ),
            at=resident.tile,
        )

    def tick(self, world: "SimulationWorld", resident: Resident, trip: Expedition) -> None:
        """A minute goes by with raiders in the way: a fight that nobody came to watch is
        fought out, and whoever is no longer being asked what to do does as they are."""
        raid = trip.raid
        if raid is None or resident.resident_id in self.live:
            return
        if raid.due is None:
            asked = world.interventions.pending_for(world, resident.resident_id)
            if asked is None or asked.kind != RAIDERS_MET:
                # The question was dropped, or lost with a save: nobody stands there for ever.
                fight = self.fight(world, resident)
                self.choose(world, resident, decide_alone(fight, resident.personality.courage / 100.0, self.carried(trip), self.data(world)))
            return
        if world.clock.total_minutes >= raid.due:
            fight = self.fight(world, resident)
            fight.resolve()
            self._settle(world, resident, fight)

    # ----- who is in it -----

    def weapons(self, world: "SimulationWorld", resident: Resident) -> tuple[ItemInstance | None, ItemInstance | None]:
        """What somebody fights with of what they carry: the best thing for the hand, and the
        best thing to fire, of those in a state to be used."""
        data = self.data(world)
        best: dict[bool, tuple[float, ItemInstance]] = {}
        for item in resident.inventory.items:
            weapon = data.weapons.get(item.definition_id)
            if weapon is None or item.broken:
                continue
            good = sum(weapon.damage) / 2 / max(0.1, weapon.seconds) * world.items.better(world, item)
            hand = weapon.kind == MELEE
            if hand not in best or good > best[hand][0]:
                best[hand] = (good, item)
        return (best[True][1] if True in best else None, best[False][1] if False in best else None)

    def kits(self, world: "SimulationWorld", resident: Resident) -> list[tuple[str, bool]]:
        """What somebody out there has to mend themselves with, a unit at a time: its item ID
        and whether it is of what they were handed for the trip, which is used first."""
        expeditions = world.expeditions
        trip = resident.expedition
        found = []
        for item_id, units in (trip.supplies.items() if trip is not None else ()):
            found += [(item_id, True)] * (max(0, units) if expeditions.is_kit(world, item_id) else 0)
        for item in resident.inventory.items:
            found += [(item.definition_id, False)] * (item.quantity if expeditions.is_kit(world, item.definition_id) else 0)
        return found

    def fighter(self, world: "SimulationWorld", resident: Resident) -> Fighter:
        """Somebody of the settlement as they go into a fight: what they are capable of, what
        they carry, how good they are at their trade, the health they have and what they are without."""
        data = self.data(world)
        attributes = {name: world.attributes.value(world, resident, name) for name in data.attributes}
        hand, fired = self.weapons(world, resident)
        job = world.work.job_of(world, resident)
        level = world.crafts.level(world, resident, job.job_id) if job is not None else 1
        first = hand if hand is not None else fired
        who = hero(
            data, resident.name, attributes, first.definition_id if first is not None else data.tuning.bare_hands,
            level=max(1, level), health=max(1.0, resident.health),
            gun_id=fired.definition_id if hand is not None and fired is not None else None,
        )
        # What they were already without they go in without, long since seen to.
        limbs = {part for limb in (*data.tuning.arms, *data.tuning.legs) for part in limb}
        who.lost = [part for part in resident.lost_limbs if part in limbs]
        who.staunched = True
        return who

    def band(self, world: "SimulationWorld", raid: Raid, rng: SimulationRNG) -> list[Fighter]:
        data = self.data(world)
        kinds = [(data.raiders.get(str(kind)), int(level)) for kind, level in raid.foes]
        return [raider(data, kind, max(1, level), rng) for kind, level in kinds if kind is not None]

    def fight(self, world: "SimulationWorld", resident: Resident) -> Fight:
        """The fight somebody out there has on their hands, as it starts: the same every time
        it is asked for, whoever asks."""
        raid = resident.expedition.raid
        rng = SimulationRNG.keyed(world.rng.seed, "raid", resident.resident_id, raid.met_at)
        foes = self.band(world, raid, rng)
        return Fight(self.data(world), self.fighter(world, resident), foes, rng, len(self.kits(world, resident)))

    # ----- watched -----

    def waiting(self, world: "SimulationWorld", resident_id: str) -> bool:
        """Whether somebody has a fight on their hands that has come to blows and is not over."""
        resident = world.residents.get(resident_id)
        trip = resident.expedition if resident is not None else None
        return trip is not None and trip.raid is not None and trip.raid.due is not None

    def open(self, world: "SimulationWorld", resident_id: str) -> Fight | None:
        """Start watching somebody's fight, to have a hand in it. None if they have none."""
        if resident_id in self.live:
            return self.live[resident_id]
        if not self.waiting(world, resident_id):
            return None
        self.live[resident_id] = self.fight(world, world.residents[resident_id])
        return self.live[resident_id]

    def step(self, world: "SimulationWorld", resident_id: str, seconds: float) -> list[Event]:
        """Let a fight that is being watched go on for so long. Says what happened in it; once
        it is over, what is left of it is the settlement's and the fight is nobody's."""
        fight = self.live.get(resident_id)
        resident = world.residents.get(resident_id)
        if fight is None or resident is None:
            self.live.pop(resident_id, None)
            return []
        told = fight.update(seconds)
        if fight.outcome is not None:
            del self.live[resident_id]
            self._settle(world, resident, fight)
        return told

    def act(self, world: "SimulationWorld", resident_id: str, act: str, value: float | str | None = None) -> bool:
        """The player has a hand in a fight they are watching. Says whether it came to anything."""
        fight = self.live.get(resident_id)
        if fight is None or fight.outcome is not None:
            return False
        if act == CRIT:
            return fight.land_crit(float(value or 0.0))
        if act == TARGET:
            return fight.choose(None if value is None else int(value))
        if act == HEAL:
            return fight.heal()
        if act == SHOVE:
            return fight.shove()
        if act == FLEE:
            return fight.flee()
        if act == STANCE:
            return fight.set_stance(str(value)) if value is not None else bool(fight.next_stance())
        if act == HANDS_OFF:
            fight.hands_off = bool(value)
            return True
        return False

    def leave(self, world: "SimulationWorld", resident_id: str) -> None:
        """Stop watching a fight: it is fought out by itself from where it stands."""
        fight = self.live.pop(resident_id, None)
        resident = world.residents.get(resident_id)
        if fight is None or resident is None:
            return
        if fight.outcome is None:
            fight.resolve()
        self._settle(world, resident, fight)

    # ----- what is left of it -----

    def _hand_over(self, world: "SimulationWorld", resident: Resident, trip: Expedition, cost: int) -> None:
        """Give up so many things: of what was found first, and then of what was handed over for the way."""
        from_finds = min(cost, max(0, trip.finds))
        trip.finds -= from_finds
        left = cost - from_finds
        for item_id in list(trip.supplies):
            gone = min(left, trip.supplies[item_id])
            trip.supplies[item_id] -= gone
            left -= gone
            if gone > 0:
                world.ledger.record(world, item_id, -gone, RAIDED, by=resident.resident_id)
        trip.supplies = {item_id: units for item_id, units in trip.supplies.items() if units > 0}

    def _head_home(self, world: "SimulationWorld", trip: Expedition) -> None:
        """Turn round where they stand: the way home is as long as the way there was, and
        there is nobody else to come on."""
        now = world.clock.total_minutes
        trip.returns_at = min(trip.returns_at, now + max(1, now - trip.left_at))
        trip.turns_at = min(trip.turns_at, now)
        trip.find_at = None
        trip.raids_at = []

    def _use_kits(self, world: "SimulationWorld", resident: Resident, trip: Expedition, used: int) -> None:
        for item_id, handed in self.kits(world, resident)[: max(0, used)]:
            if handed:
                trip.supplies[item_id] -= 1
            else:
                item = next(each for each in resident.inventory.items if each.definition_id == item_id)
                resident.inventory.take_units(item.instance_id, 1)
            world.ledger.record(world, item_id, -1, DOSED, by=resident.resident_id)
        trip.supplies = {item_id: units for item_id, units in trip.supplies.items() if units > 0}

    def _over(
        self, world: "SimulationWorld", resident: Resident, trip: Expedition, outcome: str, text: str, more: dict | None = None
    ) -> None:
        raid, trip.raid = trip.raid, None
        world.emit_event(
            DomainEvent(
                RAID_OVER_EVENT, RAID_IMPORTANCE, text, [resident.resident_id],
                data={"resident_id": resident.resident_id, "outcome": outcome, "zone": raid.zone if raid is not None else None, **(more or {})},
            ),
            at=resident.tile,
        )

    def _settle(self, world: "SimulationWorld", resident: Resident, fight: Fight) -> None:
        """Take back into the settlement what a fight that is over made of whoever was in it."""
        trip = resident.expedition
        if trip is None or trip.raid is None:
            return
        data, raid = self.data(world), trip.raid
        tuning = data.tuning
        rng = SimulationRNG.keyed(world.rng.seed, "raid_over", resident.resident_id, raid.met_at)
        after: Aftermath = aftermath(data, fight, rng)
        zone = world.registries.expeditions.zone(raid.zone)
        where = world.expeditions.name_of(world, zone) if zone is not None else "ahí fuera"
        self._use_kits(world, resident, trip, len(self.kits(world, resident)) - fight.medkits)
        hand, fired = self.weapons(world, resident)
        for used in (hand, fired):
            if used is not None:
                world.items.wear(world, resident, used)
        world.attributes.practise(world, resident, "strength", "fight")
        world.attributes.practise(world, resident, "dexterity", "fight")
        cause = f"toparse con saqueadores en {where}"
        more = {"seconds": round(fight.seconds, 1), "lost": list(after.lost), "foes": [list(foe) for foe in raid.foes]}
        if after.died:
            self._over(world, resident, trip, LOST, f"{resident.name} no vuelve de {where}: acabaron con él", {**more, "died": True})
            world.health.die(world, resident, cause)
            return
        # What it cost them is theirs to carry: what they had going in, less what they have coming out.
        cut = any(foe.weapon.severs > 0.0 for foe in fight.foes) or bool(after.lost)
        parts = [part for part in after.lost if part not in resident.lost_limbs and part not in tuning.deadly]
        world.health.fought(world, resident, max(0.0, resident.health - after.health), "cut" if cut else "bruise", cause, parts)
        if after.outcome == WON:
            brought = []
            for item_id, units in after.loot.items():
                definition = world.registries.items.find(item_id)
                if definition is None or units <= 0:
                    continue
                world.stock(resident.inventory, item_id, units, None)
                world.ledger.record(world, item_id, units, FOUND, by=resident.resident_id)
                brought.append(f"{definition.name} ({units})")
            job = world.work.job_of(world, resident)
            if job is not None:
                world.crafts.worked(world, resident, job, float(after.experience))
            took = f" y se lleva {', '.join(brought)}" if brought else ""
            self._over(world, resident, trip, WON, f"{resident.name} tumba a quien le cerraba el paso en {where}{took}", {**more, "loot": dict(after.loot)})
            return
        if after.outcome == FLED:
            self._head_home(world, trip)
            self._over(world, resident, trip, FLED, f"{resident.name} sale por piernas de {where} y se vuelve", more)
            return
        # Down among them: what they had on them is gone, and they crawl home.
        for item_id, units in trip.supplies.items():
            world.ledger.record(world, item_id, -units, RAIDED, by=resident.resident_id)
        trip.finds, trip.supplies = 0, {}
        self._head_home(world, trip)
        self._over(world, resident, trip, LOST, f"{resident.name} cae en {where}: le quitan lo que llevaba y vuelve a rastras", {**more, "robbed": True})


__all__ = ["FIGHT", "PAY", "RUN", "RAIDERS_MET", "RaidSystem", "Weapon"]
