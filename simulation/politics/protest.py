"""Taking to the square against a law in force (S45).

Laws are the player's to run, and what residents make of one is their own. Whoever is against
a law enough leaves their post at the hour for it and stands in the square with the others
who are, each day it stays in force: the more so for a law put on them with nobody asked, the
less for one that was voted, and not at all under a government where people do as they are
told however much they hate it. The player may do away with the law, make it milder, or hold.
Where it is put up with, holding costs legitimacy and adds to unrest; where the settlement is
authoritarian enough it is leaned on instead, and leaves fear and a grudge. After some days
of it they give it up, and what they hold against the government stays.

Nothing here is a roll: who goes is worked out from what each makes of the law.
"""

from typing import TYPE_CHECKING

from simulation.ai.crowd import spots_taken
from simulation.ai.utility_ai import ScoredAction
from simulation.memory.memory import Memory
from simulation.politics.law import LawDefinition, ProtestSettings
from simulation.politics.political_event import PoliticalEvent
from simulation.politics.records import LawInForce, ProtestRecord
from simulation.residents.activity import (
    LEAVE_ACTION,
    PROTEST_ACTION,
    RETIRE_ACTION,
    SERVE_ACTION,
    SHELTER_ACTION,
    WANDER_ACTION,
    Activity,
)
from simulation.residents.resident import Resident
from simulation.work.work_system import WORK_ACTION
from world.map import Tile
from world.pathfinding import find_path, manhattan

if TYPE_CHECKING:
    from simulation.world import SimulationWorld

CALLED_IMPORTANCE = 45
HELD_IMPORTANCE = 55
WON_IMPORTANCE = 60
PROTEST_MEMORY = 45.0
# Being in the square comes before work and before anything that can wait.
PROTEST_SCORE = 0.9
# What somebody leaves off to go.
DROPPED_TO_PROTEST = (WANDER_ACTION, SHELTER_ACTION, RETIRE_ACTION, WORK_ACTION)
# Whoever is locked up or on their way out for good goes nowhere.
HELD_BACK = (SERVE_ACTION, LEAVE_ACTION)


class Protests:
    def settings(self, world: "SimulationWorld") -> ProtestSettings:
        return world.registries.laws.protest

    # ----- who is against what, and how much -----

    def grievance(self, world: "SimulationWorld", resident: Resident, held: LawInForce) -> float:
        """How much a resident has against a law in force, as it counts for going out against
        it: nothing if they are for it, more if it was put on them with nobody asked, less
        with each day they have already stood there for nothing, and by how freely people
        speak out under the government they have."""
        settings = self.settings(world)
        regard = world.politics.laws.regard(world, resident, held.law_id, held.degree, held.params)
        if regard >= 0.0:
            return 0.0
        definition = world.politics.leadership.definition(world)
        dissent = definition.dissent if definition is not None else 1.0
        record = world.government.protests.get(held.law_id)
        worn = max(0.0, 1.0 - (record.days if record is not None else 0) / settings.tire_days)
        return -regard * (settings.imposed if held.imposed else settings.voted) * dissent * worn

    def cause(self, world: "SimulationWorld", resident: Resident) -> LawInForce | None:
        """The law in force a resident would go out against today: the one they have most
        against, if it is enough. None for somebody who has nothing to go out for."""
        if not world.bonds.is_adult(world, resident) or resident.away:
            return None
        if resident.resident_id in world.leaving:
            return None
        if resident.activity is not None and resident.activity.action in HELD_BACK:
            return None
        start = self.settings(world).start
        worst: tuple[float, str, LawInForce] | None = None
        for held in world.government.laws.values():
            ranked = (self.grievance(world, resident, held), held.law_id, held)
            if ranked[0] >= start and (worst is None or (ranked[0], worst[1]) > (worst[0], ranked[1])):
                worst = ranked
        return worst[2] if worst is not None else None

    def out_today(self, world: "SimulationWorld", resident_id: str) -> str | None:
        """The law a resident is out against today, by its ID, if they are."""
        today = world.clock.day
        for record in world.government.protests.values():
            if record.last_day == today and resident_id in record.who:
                return record.law_id
        return None

    def protesting(self, world: "SimulationWorld", resident: Resident) -> str | None:
        """The law a resident is standing in the square against right now, by its ID."""
        activity = resident.activity
        if activity is None or activity.action != PROTEST_ACTION or activity.path:
            return None
        return activity.item_id

    # ----- where -----

    def square(self, world: "SimulationWorld", near: Tile) -> Tile:
        """Where people gather: the square nearest a tile, or where newcomers first stand in a
        settlement that has not marked one out."""
        kind = self.settings(world).kind
        squares = [placed for placed in world.interactables.values() if placed.kind == kind]
        if squares:
            nearest = min(squares, key=lambda placed: (manhattan(near, (placed.x, placed.y)), placed.object_id))
            return (nearest.x, nearest.y)
        layout = world.registries.maps.get(world.map_id)
        spawns = layout.spawns if layout is not None else []
        return spawns[0] if spawns else near

    # ----- what a resident does about it -----

    def candidate(self, world: "SimulationWorld", resident: Resident) -> ScoredAction | None:
        """Being in the square, for whoever is out today, during the hours for it."""
        start, end = self.settings(world).hours
        if not start <= world.clock.hour < end:
            return None
        law_id = self.out_today(world, resident.resident_id)
        if law_id is None or law_id not in world.government.laws:
            return None
        return ScoredAction(PROTEST_ACTION, PROTEST_SCORE, item_id=law_id)

    def plan(self, world: "SimulationWorld", resident: Resident, candidate: ScoredAction) -> Activity | None:
        """The walk to the square, and standing there until the hour is out."""
        settings = self.settings(world)
        minutes = 60 - world.clock.minute
        centre = self.square(world, resident.tile)
        if manhattan(resident.tile, centre) <= settings.reach:
            return Activity(PROTEST_ACTION, None, [], minutes, item_id=candidate.item_id)
        passable = world.passable()
        taken = spots_taken(world, resident)
        reach = settings.reach
        spots = sorted(
            (
                (centre[0] + dx, centre[1] + dy)
                for dx in range(-reach, reach + 1)
                for dy in range(-reach, reach + 1)
                if abs(dx) + abs(dy) <= reach
            ),
            key=lambda spot: (manhattan(resident.tile, spot), spot[1], spot[0]),
        )
        for spot in spots:
            if spot in taken or not passable(spot):
                continue
            path = find_path(resident.tile, spot, passable)
            if path is not None:
                return Activity(PROTEST_ACTION, None, path, minutes, item_id=candidate.item_id)
        return None

    # ----- time -----

    def tick(self, world: "SimulationWorld") -> None:
        """One minute: on the hour it begins whoever is against a law enough goes out, and as
        it ends what the day of it did is counted."""
        state = world.government
        if state.kind is None or (not state.laws and not state.protests):
            return
        start, end = self.settings(world).hours
        hour, minute = world.clock.hour, world.clock.minute
        if hour == start and minute == 0:
            self.call(world)
        elif hour == end - 1 and minute == 59:
            self.close(world)

    def call(self, world: "SimulationWorld") -> dict[str, list[str]]:
        """Have whoever is against a law enough go out against it today. Returns who, by law ID."""
        state = world.government
        today = world.clock.day
        out: dict[str, list[str]] = {}
        for resident in world.residents.values():
            held = self.cause(world, resident)
            if held is not None:
                out.setdefault(held.law_id, []).append(resident.resident_id)
        for law_id, who in out.items():
            record = state.protests.setdefault(law_id, ProtestRecord(law_id))
            record.last_day, record.who = today, who
            definition = world.politics.laws.definition(world, law_id)
            name = definition.name if definition is not None else law_id
            for resident_id in who:
                resident = world.residents[resident_id]
                activity = resident.activity
                if activity is not None and activity.action in DROPPED_TO_PROTEST:
                    resident.activity = None
                    resident.current_action = "idle"
            if record.days == 0:
                world.emit_event(
                    PoliticalEvent(
                        "protest_called",
                        CALLED_IMPORTANCE,
                        f"{self._names(world, who)} {_verb(who, 'sale', 'salen')} a la plaza contra la ley «{name}»",
                        list(who),
                        data={"law": law_id, "who": list(who)},
                        government=state.kind,
                    )
                )
        return out

    def close(self, world: "SimulationWorld") -> None:
        """The day's protest is over: what it did, by how many stood there and how the
        settlement is run."""
        state = world.government
        settings = self.settings(world)
        today = world.clock.day
        adults = max(1, len(world.politics.leadership.present(world)))
        harsh = state.measures["authoritarianism"] >= settings.harsh_from
        now = world.clock.total_minutes
        for record in list(state.protests.values()):
            if record.last_day != today or record.law_id not in state.laws:
                continue
            there = [
                resident
                for resident_id in record.who
                if (resident := world.residents.get(resident_id)) is not None
                and self.protesting(world, resident) == record.law_id
            ]
            record.who = [resident.resident_id for resident in there]
            if not there:
                continue
            record.days += 1
            definition = world.politics.laws.definition(world, record.law_id)
            name = definition.name if definition is not None else record.law_id
            share = len(there) / adults
            legitimacy = world.politics.legitimacy
            if harsh:
                for resident in there:
                    profile = legitimacy.profile(world, resident)
                    profile.adjust("fear", settings.cowed_fear)
                    profile.adjust("resentment", settings.cowed_resentment)
                legitimacy.shock(world, {"authoritarianism": settings.harsh_authoritarianism}, share)
                came_of_it = "se les hace volver al trabajo"
            else:
                legitimacy.shock(world, {"unrest": settings.unrest, "legitimacy": settings.legitimacy}, share)
                came_of_it = "nadie les estorba"
            for resident in there:
                world.memories.remember(
                    resident.resident_id,
                    Memory(
                        f"Me planté en la plaza contra la ley «{name}».",
                        PROTEST_MEMORY, -0.3 if harsh else 0.1,
                        [each.resident_id for each in there if each is not resident],
                        ["politics", "protest"], now,
                    ),
                )
            legitimacy.measure(world)
            who = [resident.resident_id for resident in there]
            world.emit_event(
                PoliticalEvent(
                    "protest_held",
                    HELD_IMPORTANCE,
                    f"{self._names(world, who)} {_verb(who, 'se planta', 'se plantan')} en la plaza contra la ley "
                    f"«{name}»: {came_of_it}",
                    who,
                    data={"law": record.law_id, "who": who, "days": record.days, "harsh": harsh},
                    government=state.kind,
                ),
                at=self.square(world, there[0].tile),
                fact_text=f"hubo protesta en la plaza contra la ley «{name}»",
                subjects=who[:1],
            )

    def answered(self, world: "SimulationWorld", law_id: str, definition: LawDefinition | None, gone: bool) -> None:
        """A law people were out against has been done away with, or made milder: whoever
        stood there takes it as having been heard."""
        state = world.government
        record = state.protests.pop(law_id, None) if gone else state.protests.get(law_id)
        if record is None or record.days == 0:
            return
        settings = self.settings(world)
        name = definition.name if definition is not None else law_id
        now = world.clock.total_minutes
        who = [resident_id for resident_id in record.who if resident_id in world.residents]
        for resident_id in who:
            resident = world.residents[resident_id]
            world.politics.influence.judged(world, resident, settings.given_in_trust)
            world.politics.legitimacy.profile(world, resident).adjust("resentment", settings.given_in_resentment)
            said = "Quitaron" if gone else "Rebajaron"
            world.memories.remember(
                resident_id,
                Memory(
                    f"{said} la ley «{name}» después de plantarnos en la plaza.",
                    PROTEST_MEMORY, 0.5, [each for each in who if each != resident_id],
                    ["politics", "protest", "player"], now,
                ),
            )
        if not gone:
            # Milder, it is another law to them: whoever still cannot abide it starts again.
            record.days, record.who = 0, []
        if who:
            world.politics.legitimacy.shock(world, {"legitimacy": settings.given_in_legitimacy})
            world.emit_event(
                PoliticalEvent(
                    "protest_won",
                    WON_IMPORTANCE,
                    f"La protesta contra la ley «{name}» consigue lo que pedía: "
                    f"{'deja de regir' if gone else 'se rebaja'}",
                    who,
                    data={"law": law_id, "who": who, "gone": gone},
                    government=state.kind,
                )
            )

    def _names(self, world: "SimulationWorld", resident_ids: list[str]) -> str:
        names = [world.residents[each].name for each in resident_ids if each in world.residents]
        if len(names) <= 1:
            return "".join(names) or "Nadie"
        return f"{', '.join(names[:-1])} y {names[-1]}"


def _verb(who: list[str], one: str, many: str) -> str:
    return one if len(who) == 1 else many
