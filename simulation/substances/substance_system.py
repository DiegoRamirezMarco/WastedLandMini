"""What substances do to whoever takes them, and to what others make of it.

Taking one is seen by whoever is near, as anything is, and each takes it their own way by their
tastes in people. Dependence comes by chance, the likelier the more of a habit it is. Whoever
depends on something wants it, is the worse for going without, and with long enough without
gets over it. Starting on something that hooks, going back to it, and now and then a habit, are
the resident's to decide and the player's to advise on.
"""

from typing import TYPE_CHECKING

from simulation.events.event import DomainEvent
from simulation.items.item import ItemDefinition
from simulation.residents.resident import Resident
from simulation.substances.substance import RESIST, TAKE, Habit, Intake, SubstanceDefinition
from simulation.tastes.settings import UNDER
from world.interactable import UseDefinition

if TYPE_CHECKING:
    from simulation.world import SimulationWorld

# Starting on something that hooks, or going back to it: asked every time.
TEMPTED = "substance_tempted"
# Going for what they depend on: asked now and then.
HABIT = "substance_habit"
TAKEN_IMPORTANCE = 10
SEEN_IMPORTANCE = 15
DEPENDENCE_IMPORTANCE = 55
PASSED_IMPORTANCE = 45
# How much going without has somebody want a bed in the clinic: less than they want the thing itself.
CARE_WISH = 0.3


class SubstanceSystem:
    def of(self, world: "SimulationWorld", item_id: str) -> SubstanceDefinition | None:
        """What an item is as a substance. None for one that is not."""
        definition = world.registries.items.find(item_id)
        return definition.substance if definition is not None else None

    def is_under(self, world: "SimulationWorld", resident: Resident, item_id: str | None = None) -> bool:
        """Whether a resident is under something right now: that item, or anything at all."""
        now = world.clock.total_minutes
        return any(intake.until > now and item_id in (None, intake.item_id) for intake in resident.under)

    def out_of_it(self, world: "SimulationWorld", resident: Resident) -> bool:
        """Whether what a resident is under has them notice nothing around them."""
        now = world.clock.total_minutes
        return any(intake.unaware and intake.until > now for intake in resident.under)

    def craves(self, world: "SimulationWorld", resident: Resident, item_id: str) -> bool:
        """Whether a resident depends on something and it is long enough since they last had it."""
        habit = resident.habits.get(item_id)
        substance = self.of(world, item_id)
        if habit is None or substance is None or not habit.dependent:
            return False
        return world.clock.total_minutes - habit.last_taken >= substance.craving_minutes

    def in_withdrawal(self, world: "SimulationWorld", resident: Resident) -> bool:
        """Whether a resident is going without something they depend on."""
        return any(self.craves(world, resident, item_id) for item_id in resident.habits)

    def seen_through(self, world: "SimulationWorld", resident: Resident, use: UseDefinition) -> bool:
        """Whether lying somewhere would have a resident seen through going without: they are
        going without, and whoever cares for those who lie there is at it."""
        if not use.heals or not self.in_withdrawal(world, resident):
            return False
        return use.care_job is None or world.work.is_staffed(world, use.care_job)

    def care_wish(self, world: "SimulationWorld", resident: Resident, use: UseDefinition) -> float:
        """How much somebody going without wants to lie down under a medic and be seen through it."""
        return CARE_WISH if self.seen_through(world, resident, use) else 0.0

    def wish(self, world: "SimulationWorld", resident: Resident, definition: ItemDefinition) -> float | None:
        """How much more than for what it does to their needs a resident wants to take something.

        None when they will not have it at all right now: they have made up their mind not to,
        they are waiting to be advised, or they are under it already and not the sort to take more.
        """
        substance = definition.substance
        if substance is None:
            return 0.0
        settings = world.registries.substances
        now = world.clock.total_minutes
        habit = resident.habits.get(definition.item_id)
        if habit is not None and habit.resisting_until > now:
            return None
        if resident.tempted_by is not None:
            return None
        if self.is_under(world, resident, definition.item_id) and resident.personality.impulsiveness < settings.impulse_from:
            return None
        return settings.craving_wish if self.craves(world, resident, definition.item_id) else 0.0

    # ----- the player's say -----

    def may_take(self, world: "SimulationWorld", resident: Resident, definition: ItemDefinition) -> bool:
        """Whether a resident about to take something goes ahead.

        The first time with something that hooks, going back to it after days without, and now
        and then when it is a habit, they stop to think and the player may advise. Then it is
        False, and theirs to decide before they try again.
        """
        substance = definition.substance
        if substance is None:
            return True
        settings = world.registries.substances
        now = world.clock.total_minutes
        habit = resident.habits.get(definition.item_id) or Habit()
        if habit.resisting_until > now or resident.tempted_by is not None:
            return False
        if habit.allowed_until > now:
            return True
        first = habit.uses == 0 and substance.dependence >= settings.hooks_from
        relapse = (habit.dependent or habit.recovered) and now - habit.last_taken >= settings.relapse_minutes
        kind = TEMPTED if first or relapse else (HABIT if habit.dependent else None)
        if kind is None or kind not in world.registries.decisions:
            return True
        if world.interventions.asking_obstacle(world, resident, kind) is not None:
            # They have a decision open, or thought it over not long ago: it is their habit, and they go on.
            return kind == HABIT
        thing = f"{definition.article} {definition.name}"
        if world.interventions.ask(world, resident, kind, thing) is None:
            return True
        resident.tempted_by = definition.item_id
        return False

    def decided(self, world: "SimulationWorld", resident: Resident, choice: str) -> None:
        """Carry out what a resident decided about what they were about to take."""
        item_id, resident.tempted_by = resident.tempted_by, None
        if item_id is None:
            return
        settings = world.registries.substances
        habit = resident.habits.setdefault(item_id, Habit())
        now = world.clock.total_minutes
        if choice == TAKE:
            habit.allowed_until = now + settings.allowed_minutes
        elif choice == RESIST:
            habit.resisting_until = now + settings.resist_minutes
            resident.needs.apply({"stress": settings.resist_stress})

    # ----- taking it -----

    def taken(self, world: "SimulationWorld", resident: Resident, definition: ItemDefinition) -> None:
        """Have a resident have taken something: it is on them from now, it is seen, it may be
        too much, and it may bring dependence."""
        substance = definition.substance
        if substance is None:
            return
        settings = world.registries.substances
        now = world.clock.total_minutes
        thing = f"{definition.article} {definition.name}"
        on_top = self.is_under(world, resident, definition.item_id)
        resident.under = [intake for intake in resident.under if intake.item_id != definition.item_id]
        until = now + substance.minutes
        resident.under.append(
            Intake(definition.item_id, until, until + substance.after_minutes, substance.sign, substance.unaware)
        )
        habit = resident.habits.setdefault(definition.item_id, Habit())
        habit.uses += 1
        habit.last_taken, habit.without = now, 0.0
        room = world.room_at(resident.tile)
        location_id = room.room_id if room is not None else None
        said = settings.routes.get(substance.route, "toma")
        event = DomainEvent(
            "substance_taken",
            TAKEN_IMPORTANCE,
            f"{resident.name} {said} {thing}",
            [resident.resident_id],
            location_id=location_id,
            data={"item_id": definition.item_id, "route": substance.route},
        )
        seen = settings.signs.get(substance.sign)
        world.emit_event(
            event, at=resident.tile, fact_text=f"{resident.name} {seen}" if seen else None
        )
        self._seen(world, resident, definition, substance, event.witnesses)
        harm = substance.toll + (substance.harm if on_top else 0.0)
        if harm > 0 and not world.health.hurt(world, resident, harm, settings.overdose_kind, f"tomar {thing}"):
            # It killed them.
            return
        if resident.resident_id not in world.residents or habit.dependent or substance.dependence <= 0:
            return
        chance = min(settings.max_chance, substance.dependence * (1.0 + settings.habit_growth * (habit.uses - 1)))
        if world.rng.random() >= chance:
            return
        habit.dependent = True
        world.emit_event(
            DomainEvent(
                "dependence_began",
                DEPENDENCE_IMPORTANCE,
                f"{resident.name} ya no sabe pasar sin {thing}",
                [resident.resident_id],
                location_id=location_id,
                data={"item_id": definition.item_id},
            ),
            at=resident.tile,
        )

    def _seen(
        self,
        world: "SimulationWorld",
        resident: Resident,
        definition: ItemDefinition,
        substance: SubstanceDefinition,
        witnesses: list[str],
    ) -> None:
        """Have whoever it reaches take it their own way: those who saw it, or for what fills a
        room, everyone under that roof and nobody outside it."""
        reached = witnesses
        if substance.route == world.registries.substances.fills_the_room:
            room = world.room_at(resident.tile)
            reached = [
                other.resident_id
                for other in world.residents.values()
                if room is not None
                and room.roofed
                and other is not resident
                and not other.away
                and world.is_aware(other)
                and room.contains(other.tile)
            ]
        minded = [other_id for other_id in reached if other_id in world.residents]
        for other_id in minded:
            world.tastes.take_to(world, world.residents[other_id], resident, UNDER)
        if minded:
            world.emit_event(
                DomainEvent(
                    "substance_seen",
                    SEEN_IMPORTANCE,
                    f"A {resident.name} le ven: {world.registries.substances.signs.get(substance.sign, 'ha tomado algo')}",
                    [resident.resident_id, *minded],
                    data={"item_id": definition.item_id, "sign": substance.sign},
                )
            )

    # ----- living with it -----

    def tick(self, world: "SimulationWorld", resident: Resident) -> None:
        """One minute of what a resident is under, of what comes after it, and of going without
        what they depend on."""
        if resident.tempted_by is not None:
            waiting = world.interventions.pending_for(world, resident.resident_id)
            if waiting is None or waiting.kind not in (TEMPTED, HABIT):
                # What they were thinking over was overtaken by something else.
                resident.tempted_by = None
        if not resident.under and not resident.habits:
            return
        now = world.clock.total_minutes
        for intake in list(resident.under):
            substance = self.of(world, intake.item_id)
            if substance is None or now >= intake.after_until:
                resident.under.remove(intake)
            elif now < intake.until:
                resident.needs.apply(substance.per_minute)
            else:
                resident.needs.apply(substance.after_per_minute)
        settings = world.registries.substances
        for item_id, habit in resident.habits.items():
            if not habit.dependent or not self.craves(world, resident, item_id):
                continue
            resident.needs.apply(settings.withdrawal_per_minute)
            care = world.health.care_use(world, resident)
            tended = care is not None and self.seen_through(world, resident, care)
            habit.without += settings.care_factor if tended else 1.0
            if habit.without < settings.passes_after_minutes:
                continue
            habit.dependent, habit.recovered, habit.without = False, True, 0.0
            definition = world.registries.items.resolve(item_id)
            world.emit_event(
                DomainEvent(
                    "dependence_passed",
                    PASSED_IMPORTANCE,
                    f"{resident.name} ya puede pasar sin {definition.article} {definition.name}",
                    [resident.resident_id],
                    data={"item_id": item_id},
                ),
                at=resident.tile,
            )

    def work_pace(self, world: "SimulationWorld", resident: Resident) -> float:
        """How fast a resident works for what they are under, and for what they are going without."""
        if not resident.under and not resident.habits:
            return 1.0
        pace = 1.0
        now = world.clock.total_minutes
        for intake in resident.under:
            substance = self.of(world, intake.item_id)
            if substance is not None and now < intake.until:
                pace *= substance.work_pace
        if self.in_withdrawal(world, resident):
            pace *= world.registries.substances.withdrawal_pace
        return pace
