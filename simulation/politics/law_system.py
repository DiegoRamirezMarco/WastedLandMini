"""The laws in force: what each asks, who keeps it, and what comes of being seen not to.

Keeping a law is each resident's own affair: how far they do as the government says, and
what they make of the law. Whoever keeps one lives by it, and whoever does not goes on as
before. Until there are trials nothing comes of breaking one but being seen to, which is
known, talked about and held against whoever did.
"""

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any

from simulation.ai.crowd import spots_taken
from simulation.ai.utility_ai import ScoredAction
from simulation.events.event import DomainEvent
from simulation.knowledge.knowledge_system import witnesses_of
from simulation.politics import opinion
from simulation.politics.law import GATE_CLOSED, LawDefinition, LawDegree, LawSettings
from simulation.politics.political_event import PoliticalEvent
from simulation.politics.records import LawInForce
from simulation.residents.activity import (
    ATTEND_ACTION,
    LEAVE_ACTION,
    RETIRE_ACTION,
    SHELTER_ACTION,
    WANDER_ACTION,
    Activity,
)
from simulation.residents.needs import BODILY_NEEDS, URGENT_NEED
from simulation.residents.resident import Resident
from simulation.rng import SimulationRNG
from simulation.work.work_system import WORK_ACTION, WORK_ACTIONS
from world.interactable import Interactable, UseDefinition
from world.pathfinding import find_path, manhattan

if TYPE_CHECKING:
    from simulation.items.item import ItemDefinition
    from simulation.world import SimulationWorld

ENACTED_IMPORTANCE = 60
REPEALED_IMPORTANCE = 50
SALUTE_IMPORTANCE = 8
# Being where a law says everybody is to be comes before work and before anything that can wait.
ATTEND_SCORE = 0.9
# What a use of the very thing everybody is gathered at gains while they are.
ATTEND_PULL = 1.0
# Minutes apart at which it is looked into who is out of doors, and who is talking.
PATROL_MINUTES = 15
QUIET_PATROL_MINUTES = 10
# Whoever is out of doors on work, or on their way out for good, is not out against a curfew.
ABROAD_BY_RIGHT = (*WORK_ACTIONS, LEAVE_ACTION)
# What somebody leaves off to be where a law they keep says everybody is to be.
DROPPED_TO_ATTEND = (WANDER_ACTION, SHELTER_ACTION, RETIRE_ACTION, WORK_ACTION)
# How loyal whoever leads is to themselves, for keeping the laws they live under.
OWN_LOYALTY = 50.0


def in_hours(hour: int, window: tuple[int, int]) -> bool:
    """Whether an hour is inside a window, which may wrap past midnight."""
    start, end = window
    return start <= hour < end if start <= end else hour >= start or hour < end


class Laws:
    def settings(self, world: "SimulationWorld") -> LawSettings:
        return world.registries.laws

    def definition(self, world: "SimulationWorld", law_id: str) -> LawDefinition | None:
        return world.registries.laws.laws.get(law_id)

    def degree(self, definition: LawDefinition, degree: int) -> LawDegree:
        return definition.degrees[max(0, min(degree, len(definition.degrees) - 1))]

    def active(self, world: "SimulationWorld", effect: str) -> list[tuple[LawInForce, LawDefinition, Any]]:
        """Every law in force that does a thing, with what it does of it at the degree it is at."""
        held_laws = world.government.laws
        if not held_laws:
            return []
        found = []
        for held in held_laws.values():
            definition = self.definition(world, held.law_id)
            if definition is None:
                continue
            effects = self.degree(definition, held.degree).effects
            if effect in effects:
                found.append((held, definition, effects[effect]))
        return found

    # ----- putting one into words -----

    def said(self, world: "SimulationWorld", definition: LawDefinition, params: Mapping[str, str] | None = None) -> str:
        """What a law says, with whatever it names put in."""
        item = world.registries.items.find((params or {}).get("item", ""))
        return definition.text.replace("{item}", item.name if item is not None else "eso")

    def describe(
        self, world: "SimulationWorld", law_id: str, degree: int = 0, params: Mapping[str, str] | None = None
    ) -> str:
        definition = self.definition(world, law_id)
        if definition is None:
            return law_id
        text = f"{definition.name}: {self.said(world, definition, params)}"
        return f"{text} ({self.degree(definition, degree).name})" if len(definition.degrees) > 1 else text

    # ----- what each resident makes of one, and whether they keep it -----

    def regard(
        self,
        world: "SimulationWorld",
        resident: Resident,
        law_id: str,
        degree: int = 0,
        params: Mapping[str, str] | None = None,
    ) -> float:
        """What a resident makes of a law at a degree: above nothing for it, below against."""
        definition = self.definition(world, law_id)
        if definition is None:
            return 0.0
        weight = self.degree(definition, degree).weight
        return opinion.weigh(world, resident, definition.opinion, params, weight) + definition.bias

    def keeps(self, world: "SimulationWorld", resident: Resident, law_id: str) -> bool:
        """Whether a resident keeps a law that is in force, today.

        It goes by how far they do as the government says, by how legitimate the government
        is and by what they make of the law, against how hard the law is to keep. Where the
        bar stands moves a little from one day to the next, always the same for the same
        resident, law and day.
        """
        state = world.government
        held = state.laws.get(law_id)
        definition = self.definition(world, law_id)
        if held is None or definition is None:
            return True
        settings = self.settings(world)
        will = world.politics.legitimacy.obedience(world, resident)
        if state.leader == resident.resident_id:
            # Nobody is loyal to themselves as others are to them: whoever leads keeps the law
            # as somebody half way there would.
            will += world.registries.politics.obedience.get("loyalty", 0.0) * OWN_LOYALTY
        will += settings.keep_legitimacy * state.measures["legitimacy"]
        will += settings.keep_regard * self.regard(world, resident, law_id, held.degree, held.params)
        own = SimulationRNG.keyed(world.rng.seed, "law", law_id, resident.resident_id, world.clock.day)
        bar = settings.keep_base + settings.keep_burden * definition.burden
        return will >= bar + (own.random() - own.random()) * settings.keep_jitter

    def _desperate(self, world: "SimulationWorld", resident: Resident) -> bool:
        return resident.needs.hunger >= self.settings(world).desperate_hunger

    # ----- what whoever keeps a law does differently -----

    def indoors(self, world: "SimulationWorld", resident: Resident) -> bool:
        """Whether a resident is keeping a curfew right now."""
        hour = world.clock.hour
        return any(
            in_hours(hour, hours) and self.keeps(world, resident, held.law_id)
            for held, _definition, hours in self.active(world, "curfew")
        )

    def hushed(self, world: "SimulationWorld", resident: Resident) -> bool:
        """Whether a resident is keeping hours in which nobody talks."""
        hour = world.clock.hour
        return any(
            in_hours(hour, hours) and self.keeps(world, resident, held.law_id)
            for held, _definition, hours in self.active(world, "quiet")
        )

    def meals_today(self, world: "SimulationWorld", resident: Resident) -> int:
        day, times = world.government.meals.get(resident.resident_id, [0, 0])
        return times if day == world.clock.day else 0

    def bars(
        self, world: "SimulationWorld", resident: Resident, placed: Interactable, use: UseDefinition, indoors: bool
    ) -> bool:
        """Whether a law the resident keeps stands between them and a use, as things are."""
        if not world.government.laws:
            return False
        for held, _definition, kinds in self.active(world, "closes"):
            if placed.kind in kinds and self.keeps(world, resident, held.law_id):
                return True
        if use.consumes in world.registries.economy.kept_categories and not self._desperate(world, resident):
            eaten = self.meals_today(world, resident)
            for held, _definition, limit in self.active(world, "meals"):
                if eaten >= limit and self.keeps(world, resident, held.law_id):
                    return True
        if indoors and not use.unaware and not self.under_same_roof(world, resident, (placed.x, placed.y)):
            # Across open ground only to get to bed, or for what cannot wait.
            return all(getattr(resident.needs, need) < URGENT_NEED for need in BODILY_NEEDS)
        return False

    def under_same_roof(self, world: "SimulationWorld", resident: Resident, tile: tuple[int, int]) -> bool:
        """Whether a tile is under the roof a resident is under: somewhere they can get to
        without setting foot out of doors."""
        room = world.room_at(resident.tile)
        return room is not None and room.roofed and room.contains(tile)

    def banned(self, world: "SimulationWorld", definition: "ItemDefinition") -> list[tuple[LawInForce, LawDefinition]]:
        """The laws in force that say nobody is to take an item."""
        if not world.government.laws:
            return []
        found = [
            (held, law)
            for held, law, tags in self.active(world, "bans_tags")
            if any(tag in definition.tags for tag in tags)
        ]
        found += [
            (held, law)
            for held, law, names in self.active(world, "bans_item")
            if names and held.params.get("item") == definition.item_id
        ]
        return found

    def may_have(self, world: "SimulationWorld", resident: Resident, definition: "ItemDefinition") -> bool:
        """Whether a resident would take an item, for all the law says: no, if a law they keep
        is against it and they are not starving."""
        banned = self.banned(world, definition)
        if not banned or self._desperate(world, resident):
            return True
        return not any(self.keeps(world, resident, held.law_id) for held, _law in banned)

    def pull(self, world: "SimulationWorld", resident: Resident, placed: Interactable) -> float:
        """What a use gains for being of the very thing a law the resident keeps gathers everybody at, at that hour."""
        hour = world.clock.hour
        for held, _definition, need in self.active(world, "requires"):
            if need["kind"] == placed.kind and need["hour"] == hour and self.keeps(world, resident, held.law_id):
                return ATTEND_PULL
        return 0.0

    def attendance(self, world: "SimulationWorld", resident: Resident) -> ScoredAction | None:
        """Being where a law the resident keeps says everybody is to be at this hour."""
        hour = world.clock.hour
        for held, _definition, need in self.active(world, "requires"):
            if need["hour"] != hour or not self.keeps(world, resident, held.law_id):
                continue
            things = [placed for placed in world.interactables.values() if placed.kind == need["kind"]]
            if things:
                nearest = min(things, key=lambda placed: (manhattan(resident.tile, (placed.x, placed.y)), placed.object_id))
                return ScoredAction(ATTEND_ACTION, ATTEND_SCORE, nearest.object_id)
        return None

    def plan_attend(self, world: "SimulationWorld", resident: Resident, candidate: ScoredAction) -> Activity | None:
        """The walk to where everybody is to be, and standing there until the hour is out."""
        placed = world.interactables.get(candidate.target_id or "")
        if placed is None:
            return None
        minutes = 60 - world.clock.minute
        reach = self.settings(world).attend_reach
        centre = (placed.x, placed.y)
        if manhattan(resident.tile, centre) <= reach:
            return Activity(ATTEND_ACTION, None, [], minutes)
        # Anywhere near enough that nobody else is standing on or heading for will do.
        passable = world.passable()
        taken = spots_taken(world, resident)
        spots = sorted(
            (
                (placed.x + dx, placed.y + dy)
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
                return Activity(ATTEND_ACTION, None, path, minutes)
        return None

    # ----- what a law changes for everybody -----

    def day_off(self, world: "SimulationWorld", resident: Resident) -> bool:
        """Whether a law has nobody working today."""
        if not world.government.laws:
            return False
        weekday = (world.clock.day - 1) % world.registries.economy.week_days
        if any(day == weekday for _held, _definition, day in self.active(world, "day_off")):
            return True
        leader = world.politics.leader(world)
        if leader is None or not any(on for _held, _definition, on in self.active(world, "leader_birthday")):
            return False
        today, born = world.family.today(world), world.family.birth_date(world, leader)
        return (today.month, today.day) == (born.month, born.day)

    def shift_minutes(self, world: "SimulationWorld") -> int:
        """How many minutes longer every shift is by law, or shorter if less than none."""
        return round(sum(hours for _held, _definition, hours in self.active(world, "shift_hours")) * 60)

    def wage(self, world: "SimulationWorld", due: float) -> float:
        """What a wage comes to once the law has had its say: how much is paid, less what the fund keeps."""
        for _held, _definition, factor in self.active(world, "wage_factor"):
            due *= factor
        for _held, _definition, share in self.active(world, "tax"):
            due *= 1.0 - share
        return due

    def meal_price(self, world: "SimulationWorld") -> float:
        """How many times the usual price a meal out of the commons costs."""
        factor = 1.0
        for _held, _definition, each in self.active(world, "meal_price"):
            factor *= each
        return factor

    def excused(self, world: "SimulationWorld", resident: Resident) -> bool:
        """Whether a law has a resident not working, and kept all the same."""
        for _held, _definition, who in self.active(world, "excused"):
            if "expecting" in who and resident.expecting_with is not None:
                return True
        return False

    def gate_shut(self, world: "SimulationWorld", keeper: Resident) -> float:
        """How much the law weighs on whoever answers the gate: 1 if it says nobody comes in and they keep it."""
        shut = any(
            how == GATE_CLOSED and self.keeps(world, keeper, held.law_id)
            for held, _definition, how in self.active(world, "gate")
        )
        return 1.0 if shut else 0.0

    def dark(self, world: "SimulationWorld", placed: Interactable) -> bool:
        """Whether a law has an object give no light right now."""
        return world.is_dark() and any(placed.kind in kinds for _held, _definition, kinds in self.active(world, "dark"))

    # ----- being seen to break one -----

    def used(self, world: "SimulationWorld", resident: Resident, placed: Interactable, use: UseDefinition) -> None:
        """A resident has begun a use: a meal out of the commons is counted, and a use the law is against is seen."""
        state = world.government
        common_meal = use.consumes in world.registries.economy.kept_categories
        if common_meal and (state.laws or resident.resident_id in state.meals):
            state.meals[resident.resident_id] = [world.clock.day, self.meals_today(world, resident) + 1]
        if not state.laws:
            return
        for held, definition, kinds in self.active(world, "closes"):
            if placed.kind in kinds:
                self.breach(world, resident, held, definition)
        if common_meal:
            for held, definition, limit in self.active(world, "meals"):
                if self.meals_today(world, resident) > limit:
                    self.breach(world, resident, held, definition)

    def taken(self, world: "SimulationWorld", resident: Resident, definition: "ItemDefinition") -> None:
        """A resident has eaten, drunk or used an item: one the law is against is seen."""
        for held, law in self.banned(world, definition):
            self.breach(world, resident, held, law)

    def gate_opened(self, world: "SimulationWorld", keeper: Resident) -> None:
        """Whoever answered the gate has let somebody in: seen, if the law said nobody comes in."""
        for held, definition, how in self.active(world, "gate"):
            if how == GATE_CLOSED:
                self.breach(world, keeper, held, definition)

    def breach(
        self,
        world: "SimulationWorld",
        resident: Resident,
        held: LawInForce,
        definition: LawDefinition,
        seen_by: list[str] | None = None,
    ) -> bool:
        """Have a resident be seen to break a law, at most once a day for each law.

        Nothing comes of it unless somebody sees: whoever is there to, or `seen_by` when it is
        the not being somewhere that gives them away. Returns whether it was seen.
        """
        key = f"law:{held.law_id}:{resident.resident_id}"
        if world.notices.get(key) == world.clock.day:
            return False
        watchers = seen_by if seen_by is not None else witnesses_of(world, resident.tile, exclude=[resident.resident_id])
        if not watchers:
            return False
        world.notices[key] = world.clock.day
        settings = self.settings(world)
        event = PoliticalEvent(
            "law_broken",
            settings.breach_importance,
            f"{resident.name} se salta la ley: {definition.name}",
            [resident.resident_id],
            data={"law": held.law_id, "resident_id": resident.resident_id},
            government=world.government.kind,
        )
        fact_text = f"{resident.name} se saltó la ley ({definition.name})"
        if seen_by is not None:
            event.witnesses = list(seen_by)
            world.emit_event(event, fact_text=fact_text)
        else:
            world.emit_event(event, at=resident.tile, fact_text=fact_text)
        for witness_id in event.witnesses:
            witness = world.residents.get(witness_id)
            if witness is None:
                continue
            feelings = world.relationship(witness_id, resident.resident_id)
            if self.keeps(world, witness, held.law_id):
                # Whoever keeps it thinks the less of whoever does not.
                feelings.adjust("trust", settings.breach_trust)
                feelings.adjust("resentment", settings.breach_resentment)
            else:
                feelings.adjust("affection", settings.breach_fellow)
        return True

    # ----- passing one, and doing away with one -----

    def obstacle(self, world: "SimulationWorld", law_id: str) -> str | None:
        """Why a law could not be had as things are, in words. None if it could."""
        definition = self.definition(world, law_id)
        if definition is None:
            return "No hay tal ley"
        if definition.needs_currency and world.fund.currency(world) is None:
            return "Esa ley no tiene sentido sin moneda"
        if definition.needs_leader and world.politics.leader(world) is None:
            return "Esa ley no tiene sentido sin nadie que mande"
        kind = definition.needs_kind
        if kind is not None and not any(placed.kind == kind for placed in world.interactables.values()):
            return "Esa ley no tiene sentido aquí: falta de qué habla"
        return None

    def enact(
        self,
        world: "SimulationWorld",
        law_id: str,
        degree: int = 0,
        params: Mapping[str, str] | None = None,
        by: str | None = None,
        pushed: bool = False,
    ) -> bool:
        """Put a law in force at a degree, in place of the same law at another and of any it
        cannot stand beside. Returns whether there was such a law."""
        definition = self.definition(world, law_id)
        if definition is None:
            return False
        state = world.government
        for other in definition.excludes:
            if other in state.laws:
                self.repeal(world, other)
        before = state.laws.get(law_id)
        degree = max(0, min(degree, len(definition.degrees) - 1))
        weight = self.degree(definition, degree).weight
        was = self.degree(definition, before.degree).weight if before is not None else 0.0
        state.laws[law_id] = LawInForce(law_id, degree, dict(params or {}), world.clock.day, by, pushed)
        changes = {"authoritarianism": definition.harsh * (weight - was)}
        government = world.politics.leadership.definition(world)
        if definition.absurd and before is None:
            tolerance = government.abuse_tolerance if government is not None else 0.0
            changes["legitimacy"] = self.settings(world).absurd_legitimacy * (1.0 - tolerance / 100.0)
        world.politics.legitimacy.shock(world, changes)
        if "common" in self.degree(definition, degree).effects:
            self._make_common(world)
        world.emit_event(
            PoliticalEvent(
                "law_enacted",
                ENACTED_IMPORTANCE,
                f"Desde hoy es ley: {self.describe(world, law_id, degree, params)}",
                data={"law": law_id, "degree": degree, "params": dict(params or {}), "by": by},
                government=state.kind,
            )
        )
        return True

    def repeal(self, world: "SimulationWorld", law_id: str) -> bool:
        """Do away with a law in force. Returns whether it was."""
        state = world.government
        held = state.laws.pop(law_id, None)
        definition = self.definition(world, law_id)
        if held is None:
            return False
        name = definition.name if definition is not None else law_id
        if definition is not None:
            weight = self.degree(definition, held.degree).weight
            world.politics.legitimacy.shock(world, {"authoritarianism": -definition.harsh * weight})
        world.emit_event(
            PoliticalEvent(
                "law_repealed",
                REPEALED_IMPORTANCE,
                f"Deja de ser ley: {name}",
                data={"law": law_id},
                government=state.kind,
            )
        )
        return True

    def _make_common(self, world: "SimulationWorld") -> None:
        """Have whatever is kept in a container be nobody's. What somebody carries is still theirs."""
        for inventory in world.containers.values():
            for item in inventory.items:
                if item.owner_id is not None and item.meant_for is None:
                    item.owner_id = None

    # ----- time -----

    def tick(self, world: "SimulationWorld") -> None:
        """One minute under the laws there are: who greets whoever leads, who is out of doors
        or talking when they should not be, and who is missing from where everybody is to be."""
        if not world.government.laws:
            return
        self._salutes(world)
        minute = world.clock.minute
        if minute == 0:
            self._summon(world)
        if minute % PATROL_MINUTES == 0:
            self._patrol(world)
        if minute % QUIET_PATROL_MINUTES == 5:
            self._hush(world)
        if minute == 59:
            self._roll_call(world)

    def tick_day(self, world: "SimulationWorld") -> None:
        """A day under the laws there are tells on what each resident holds: one they are
        against is held against the government, one they are for adds to their trust in it,
        and either way it is held to the player's account if the player was behind it."""
        state = world.government
        if not state.laws:
            return
        settings = self.settings(world)
        if self.active(world, "common"):
            self._make_common(world)
        for resident in list(world.residents.values()):
            if not world.bonds.is_adult(world, resident):
                continue
            profile = world.politics.legitimacy.profile(world, resident)
            for held in state.laws.values():
                regard = self.regard(world, resident, held.law_id, held.degree, held.params)
                if regard < 0:
                    profile.adjust("resentment", -regard * settings.grind_resentment)
                profile.adjust("trust", regard * settings.grind_trust)
                if held.pushed:
                    world.politics.influence.judged(world, resident, regard * settings.grind_player)

    def _summon(self, world: "SimulationWorld") -> None:
        """On the hour a law gathers everybody at, whoever keeps it leaves off what can be
        left off: a stroll, their post. Nobody is got out of bed or away from their plate.
        And on the hour a curfew begins, whoever keeps it and is strolling in the open stops."""
        hour = world.clock.hour
        for held, _definition, hours in self.active(world, "curfew"):
            if hours[0] != hour:
                continue
            for resident in world.residents.values():
                activity = resident.activity
                strolling = activity is not None and activity.action == WANDER_ACTION
                if strolling and not resident.away and not world.under_roof(resident.destination):
                    if self.keeps(world, resident, held.law_id):
                        resident.activity = None
                        resident.current_action = "idle"
        for held, _definition, need in self.active(world, "requires"):
            if need["hour"] != hour:
                continue
            for resident in world.residents.values():
                activity = resident.activity
                if activity is None or activity.action not in DROPPED_TO_ATTEND or resident.away:
                    continue
                if self.keeps(world, resident, held.law_id):
                    resident.activity = None
                    resident.current_action = "idle"

    def _salutes(self, world: "SimulationWorld") -> None:
        laws = self.active(world, "salute")
        leader = world.politics.leader(world)
        if not laws or leader is None or leader.away or not world.is_aware(leader):
            return
        held, definition, _on = laws[0]
        reach = self.settings(world).salute_reach
        for resident in list(world.residents.values()):
            if resident is leader or resident.away or not world.is_aware(resident):
                continue
            if manhattan(resident.tile, leader.tile) > reach:
                continue
            key = f"salute:{resident.resident_id}"
            if world.notices.get(key) == world.clock.day:
                continue
            world.notices[key] = world.clock.day
            if self.keeps(world, resident, held.law_id):
                world.emit_event(
                    DomainEvent(
                        "saluted",
                        SALUTE_IMPORTANCE,
                        f"{resident.name} saluda a {leader.name}, como manda la ley",
                        [resident.resident_id, leader.resident_id],
                    )
                )
            else:
                self.breach(world, resident, held, definition, seen_by=[leader.resident_id])

    def _patrol(self, world: "SimulationWorld") -> None:
        hour = world.clock.hour
        for held, definition, hours in self.active(world, "curfew"):
            if not in_hours(hour, hours):
                continue
            for resident in list(world.residents.values()):
                if resident.away or not world.is_aware(resident) or world.under_roof(resident.tile):
                    continue
                activity = resident.activity
                if activity is not None and activity.action in ABROAD_BY_RIGHT:
                    continue
                if not self.keeps(world, resident, held.law_id):
                    self.breach(world, resident, held, definition)

    def _hush(self, world: "SimulationWorld") -> None:
        hour = world.clock.hour
        for held, definition, hours in self.active(world, "quiet"):
            if not in_hours(hour, hours):
                continue
            for resident in list(world.residents.values()):
                activity = resident.activity
                talking = activity is not None and activity.using and activity.partner_id is not None
                if talking and not resident.away and not self.keeps(world, resident, held.law_id):
                    self.breach(world, resident, held, definition)

    def _roll_call(self, world: "SimulationWorld") -> None:
        hour = world.clock.hour
        reach = self.settings(world).attend_reach
        for held, definition, need in self.active(world, "requires"):
            if need["hour"] != hour:
                continue
            things = [placed for placed in world.interactables.values() if placed.kind == need["kind"]]
            if not things:
                continue
            here: list[Resident] = []
            missing: list[Resident] = []
            for resident in world.residents.values():
                if resident.away or not world.is_aware(resident):
                    continue
                near = any(manhattan(resident.tile, (placed.x, placed.y)) <= reach for placed in things)
                (here if near else missing).append(resident)
            if not here:
                continue
            seen_by = [resident.resident_id for resident in here]
            for resident in missing:
                if world.bonds.is_adult(world, resident):
                    self.breach(world, resident, held, definition, seen_by=seen_by)
