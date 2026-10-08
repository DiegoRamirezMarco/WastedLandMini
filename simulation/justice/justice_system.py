"""Trials and punishment.

Somebody is tried for what is known of them, never for what only the world knows: a thing
nobody saw or was told of cannot be brought. Whoever knows of it may accuse, and so may the
player. A trial goes through six steps, and those who decide in the government judge, each on
what they believe they know and on what they feel. What a guilty one is given is the player's
to say, out of what the settlement has a place for. A punishment is a political event: each of
those who see it or hear of it takes it their own way, and the settlement is moved by how.
"""

from dataclasses import dataclass
from typing import TYPE_CHECKING

from simulation.events.event import DomainEvent
from simulation.items.item_system import FOOD_CATEGORY, WATER_CATEGORY
from simulation.justice.records import (
    ACCUSATION,
    CLOSED,
    DEFENCE,
    EVIDENCE,
    GUILTY,
    INNOCENT,
    PUNISHMENT,
    STEPS,
    VERDICT,
    WITNESSES,
    PunishmentRecord,
    Ration,
    Sentence,
    Trial,
)
from simulation.justice.settings import (
    ANGER,
    APPROVAL,
    FEAR,
    GRIEF,
    INDIFFERENCE,
    JusticeSettings,
    PunishmentDefinition,
)
from simulation.knowledge.fact import SOURCE_TOLD, Fact
from simulation.knowledge.knowledge_system import witnesses_of
from simulation.memory.memory import Memory
from simulation.politics.political_event import PoliticalEvent
from simulation.politics.records import PLAYER
from simulation.residents.activity import ACCUSE_DECISION, EXILE_BACK_DECISION, SERVE_ACTION, Activity
from simulation.residents.personality import Personality
from simulation.residents.resident import Resident
from world.map import Tile
from world.pathfinding import find_path

if TYPE_CHECKING:
    from simulation.politics.records import Exile
    from simulation.world import SimulationWorld

# The punishments that have code of their own for what they do. Any other is a word and no more.
FINE, CONFISCATION, SERVICE, STOCKS, PRISON, CORPORAL, EXILE, EXECUTION = (
    "fine", "confiscation", "community_service", "public_stocks", "prison", "corporal_punishment", "exile",
    "execution",
)
MINUTES_PER_DAY = 24 * 60
OPENED_IMPORTANCE = 55
STEP_IMPORTANCE = 35
VERDICT_IMPORTANCE = 60
SERVED_IMPORTANCE = 40
UNFED_IMPORTANCE = 45
RETURN_IMPORTANCE = 65
CORPORAL_INJURY = "bruise"
# How much a memory of a punishment weighs for each point of its severity, and at the most.
MEMORY_PER_SEVERITY = 9.0
SERVE_MINUTES = 120
# How much better than somebody asleep in the open a prisoner rests at night.
NIGHT_REST = 1.6


@dataclass(frozen=True)
class JusticeResult:
    """Whether something the player set about came off, and what there is to say of it."""

    ok: bool
    message: str
    # The trial it was about, when it was about one.
    detail: str = ""


class JusticeSystem:
    def settings(self, world: "SimulationWorld") -> JusticeSettings:
        return world.registries.justice

    # ----- what can be brought -----

    def tried(self, world: "SimulationWorld", fact_id: str) -> bool:
        """Whether somebody has already been tried for a thing. Nobody is tried twice for one."""
        return any(trial.fact_id == fact_id for trial in world.courts.trials.values())

    def knowers(self, world: "SimulationWorld", fact_id: str) -> list[Resident]:
        """Whoever is here and knows of a thing, by having seen it or having been told."""
        return [
            resident
            for resident in world.residents.values()
            if not resident.away and world.knowledge.knows(resident.resident_id, fact_id)
        ]

    def known_offences(self, world: "SimulationWorld", accused_id: str) -> list[Fact]:
        """What somebody could be tried for: what they did that somebody here knows of, and
        for which nobody has been tried, the latest first. What nobody saw is not among it."""
        offences = self.settings(world).offences
        found = [
            fact
            for fact in world.knowledge.facts.values()
            if fact.event_type in offences
            and fact.subject_ids[:1] == [accused_id]
            and not self.tried(world, fact.fact_id)
            and any(knower.resident_id != accused_id for knower in self.knowers(world, fact.fact_id))
        ]
        return sorted(found, key=lambda fact: (-fact.timestamp, fact.fact_id))

    def open_trial(self, world: "SimulationWorld") -> Trial | None:
        """The trial going on, if one is: there is one at a time."""
        return next((trial for trial in world.courts.trials.values() if trial.open), None)

    def accuse(
        self, world: "SimulationWorld", accused_id: str, fact_id: str | None = None, by: str = PLAYER
    ) -> JusticeResult:
        """Have somebody tried for a thing known of them: the one named, or the latest there is.

        It is refused for what nobody here knows of, for what somebody was tried for already,
        and while another trial is going on.
        """
        accused = world.residents.get(accused_id)
        if accused is None or accused_id in world.leaving:
            return JusticeResult(False, "No hay a quién juzgar")
        if not self.settings(world).punishments:
            return JusticeResult(False, "Aquí no se juzga a nadie")
        known = self.known_offences(world, accused_id)
        fact = next((each for each in known if fact_id in (None, each.fact_id)), None)
        if fact is None:
            return JusticeResult(False, f"De {accused.name} no se sabe nada por lo que juzgarle")
        accuser = world.residents.get(by)
        if by != PLAYER and (accuser is None or not world.knowledge.knows(by, fact.fact_id)):
            return JusticeResult(False, "Nadie acusa de lo que no sabe")
        if self.open_trial(world) is not None:
            return JusticeResult(False, "Ya hay un juicio en marcha")
        state, settings = world.courts, self.settings(world)
        state.trial_count += 1
        now = world.clock.total_minutes
        trial = Trial(
            f"trial_{state.trial_count}", accused_id, by, fact.event_type, fact.fact_id, now, ACCUSATION,
            now + settings.step_minutes,
        )
        state.trials[trial.trial_id] = trial
        world.interventions.cancel_for(world, accused_id)
        who = accuser.name if accuser is not None else "Se"
        offence = settings.offences[fact.event_type].name
        text = f"{who} acusa a {accused.name} de {offence}" if accuser is not None else f"Se acusa a {accused.name} de {offence}"
        world.emit_event(
            PoliticalEvent(
                "trial_opened", OPENED_IMPORTANCE, text, [accused_id, *([by] if accuser is not None else [])],
                data={"trial_id": trial.trial_id, "accused": accused_id, "accuser": by, "offence": fact.event_type},
                government=world.government.kind,
            ),
            at=accused.tile,
            fact_text=f"a {accused.name} le juzgan por {offence}",
            subjects=[accused_id],
        )
        return JusticeResult(True, text, trial.trial_id)

    # ----- residents who accuse -----

    def _weigh_accusing(self, world: "SimulationWorld") -> None:
        """At one hour of the day, have whoever most wants to see something answered for think of accusing."""
        settings, state = self.settings(world), world.courts
        if state.weighing or self.open_trial(world) is not None or not settings.punishments:
            return
        since = world.clock.total_minutes - settings.accuse_within_days * MINUTES_PER_DAY
        best: tuple[float, str, str, str] | None = None
        for fact in world.knowledge.facts.values():
            if fact.event_type not in settings.offences or fact.timestamp < since or not fact.subject_ids:
                continue
            accused = world.residents.get(fact.subject_ids[0])
            if accused is None or accused.away or self.tried(world, fact.fact_id):
                continue
            for resident in world.politics.leadership.present(world):
                wish = self.wish_to_accuse(world, resident, accused, fact)
                if wish >= settings.accuse_from and (best is None or (wish, fact.fact_id) > best[:2]):
                    best = (wish, fact.fact_id, resident.resident_id, accused.resident_id)
        if best is None:
            return
        _, fact_id, resident_id, accused_id = best
        resident, accused = world.residents[resident_id], world.residents[accused_id]
        if ACCUSE_DECISION not in world.registries.decisions:
            self.accuse(world, accused_id, fact_id, resident_id)
        elif world.interventions.ask(world, resident, ACCUSE_DECISION, accused.name) is not None:
            state.weighing[resident_id] = (accused_id, fact_id)

    def wish_to_accuse(self, world: "SimulationWorld", resident: Resident, accused: Resident, fact: Fact) -> float:
        """How much a resident wants somebody tried for a thing: nothing unless they know of it
        surely enough, and then by how grave it is, what they feel for them and how much
        justice matters to them. Nobody accuses themselves, their partner or their kin."""
        settings = self.settings(world)
        belief = world.knowledge.belief(resident.resident_id, fact.fact_id)
        if resident is accused or belief is None or belief.credibility < settings.accuse_sure_from:
            return 0.0
        if resident.couple_with == accused.resident_id or world.family.kin.close(world, resident.resident_id, accused.resident_id):
            return 0.0
        if world.interventions.pending_for(world, resident.resident_id) is not None:
            return 0.0
        weights = settings.accuse_weights
        feelings = world.relationships.get((resident.resident_id, accused.resident_id))
        profile = world.politics.legitimacy.profile(world, resident)
        return (
            weights.get("gravity", 0.0) * settings.offences[fact.event_type].gravity
            + weights.get("resentment", 0.0) * (feelings.resentment if feelings is not None else 0.0) / 100.0
            + weights.get("affection", 0.0) * (feelings.affection if feelings is not None else 0.0) / 100.0
            + weights.get("justice", 0.0) * profile.justice_sensitivity / 100.0
        )

    def accusing_decided(self, world: "SimulationWorld", resident: Resident, accuses: bool) -> None:
        """Carry out what a resident decided about accusing somebody."""
        weighed = world.courts.weighing.pop(resident.resident_id, None)
        if weighed is not None and accuses:
            self.accuse(world, weighed[0], weighed[1], resident.resident_id)

    # ----- a trial, step by step -----

    def judges(self, world: "SimulationWorld", trial: Trial) -> list[Resident]:
        """Whoever judges: those who decide anything under the government in force, or everybody
        grown where there is none. The accused does not judge themselves."""
        deciding = world.politics.voting.deciders(world) or world.politics.leadership.present(world)
        judges = [resident for resident in deciding if resident.resident_id != trial.accused]
        # With nobody but the accused to decide, it falls to everybody else.
        return judges or [r for r in world.politics.leadership.present(world) if r.resident_id != trial.accused]

    def holds_guilty(self, world: "SimulationWorld", resident: Resident, trial: Trial) -> bool:
        """Whether a resident holds the accused guilty, on what they believe they know: what
        they saw or were told, what a witness they trust says, and what they feel for the
        accused and for whoever accuses. Never on what only the world knows."""
        return self.belief_in_guilt(world, resident, trial) >= self.settings(world).guilty_from

    def belief_in_guilt(self, world: "SimulationWorld", resident: Resident, trial: Trial) -> float:
        weights = self.settings(world).weights
        belief = world.knowledge.belief(resident.resident_id, trial.fact_id)
        if belief is not None:
            score = belief.credibility * weights.get("told" if belief.source == SOURCE_TOLD else "saw", 1.0)
        else:
            # Having seen nothing, they go by whoever says they did, as far as they trust them.
            trusted = 0.0
            for witness_id in trial.witnesses:
                feelings = world.relationships.get((resident.resident_id, witness_id))
                trusted = max(trusted, 0.5 + (feelings.trust if feelings is not None else 0.0) / 200.0)
            score = trusted * weights.get("testimony", 0.0)
        feelings = world.relationships.get((resident.resident_id, trial.accused))
        if feelings is not None:
            score += weights.get("resentment", 0.0) * feelings.resentment / 100.0
            score += weights.get("affection", 0.0) * feelings.affection / 100.0
        if resident.couple_with == trial.accused or world.family.kin.close(world, resident.resident_id, trial.accused):
            score += weights.get("kin", 0.0)
        toward = world.relationships.get((resident.resident_id, trial.accuser))
        if toward is not None:
            score += weights.get("accuser", 0.0) * toward.trust / 100.0
        return score

    def _advance(self, world: "SimulationWorld", trial: Trial) -> None:
        """Take a trial on to its next step, and say what came of the one it leaves."""
        settings = self.settings(world)
        accused = world.residents.get(trial.accused)
        if accused is None:
            # Dead or gone before it was over: there is nobody left to try.
            self._close(world, trial)
            return
        now = world.clock.total_minutes
        trial.step = STEPS[STEPS.index(trial.step) + 1]
        trial.next_at = now + settings.step_minutes
        knowers = [each for each in self.knowers(world, trial.fact_id) if each.resident_id != trial.accused]
        if trial.step == EVIDENCE:
            count = len(knowers)
            said = "nadie sabe nada de ello" if not count else f"lo {'sabe' if count == 1 else 'saben'} {count}"
            self._say(world, trial, f"Juicio a {accused.name}: se mira lo que hay, y {said}")
        elif trial.step == WITNESSES:
            saw = [
                each.resident_id
                for each in knowers
                if world.knowledge.belief(each.resident_id, trial.fact_id).source != SOURCE_TOLD
            ]
            trial.witnesses = saw
            names = ", ".join(world.residents[each].name for each in saw)
            said = f"dicen haberlo visto {names}" if saw else "nadie dice haberlo visto: solo se ha oído contar"
            self._say(world, trial, f"Juicio a {accused.name}: {said}")
        elif trial.step == DEFENCE:
            self._say(world, trial, f"Juicio a {accused.name}: {accused.name} dice lo que tiene que decir")
        elif trial.step == VERDICT:
            self._judge(world, trial, accused)
        elif trial.step == PUNISHMENT:
            if trial.verdict != GUILTY:
                self._close(world, trial)
                return
            # What they are given is the player's to say, and it waits for that.
            trial.next_at = now + settings.sentence_hours * 60

    def _judge(self, world: "SimulationWorld", trial: Trial, accused: Resident) -> None:
        judges = self.judges(world, trial)
        trial.ballots = {judge.resident_id: self.holds_guilty(world, judge, trial) for judge in judges}
        guilty = sum(trial.ballots.values())
        trial.verdict = GUILTY if guilty > len(trial.ballots) - guilty else INNOCENT
        word = "culpable" if trial.verdict == GUILTY else "inocente"
        offence = self.settings(world).offences[trial.offence].name
        world.emit_event(
            PoliticalEvent(
                "trial_verdict",
                VERDICT_IMPORTANCE,
                f"A {accused.name} le declaran {word} de {offence}: {guilty} de {len(trial.ballots)} le tienen por culpable",
                [trial.accused],
                data={"trial_id": trial.trial_id, "verdict": trial.verdict, "guilty": guilty, "judges": len(trial.ballots)},
                government=world.government.kind,
            ),
            at=accused.tile,
            fact_text=f"a {accused.name} le declararon {word} de {offence}",
            subjects=[trial.accused],
        )
        if trial.verdict == INNOCENT:
            accuser = world.residents.get(trial.accuser)
            if accuser is not None:
                # Whoever was accused for nothing does not forget who accused them.
                feelings = world.relationship(trial.accused, trial.accuser)
                feelings.adjust("resentment", 15.0)
                feelings.adjust("trust", -10.0)

    def _say(self, world: "SimulationWorld", trial: Trial, text: str) -> None:
        world.emit_event(
            PoliticalEvent(
                "trial_step", STEP_IMPORTANCE, text, [trial.accused],
                data={"trial_id": trial.trial_id, "step": trial.step}, government=world.government.kind,
            )
        )

    def _close(self, world: "SimulationWorld", trial: Trial) -> None:
        trial.step, trial.closed_at = CLOSED, world.clock.total_minutes

    # ----- what there is a place for -----

    def place_for(self, world: "SimulationWorld", definition: PunishmentDefinition) -> tuple[bool, str | None]:
        """Whether the settlement has what a punishment needs, and the ID of where it is served:
        the building with that use, or the object of one of those kinds."""
        if definition.building is not None:
            room_id = next(
                (
                    room_id
                    for room_id, use in world.homes.uses.items()
                    if use == definition.building and room_id in world.rooms and world.rooms[room_id].roofed
                ),
                None,
            )
            return (room_id is not None, room_id)
        if definition.objects:
            placed = next((each for each in world.interactables.values() if each.kind in definition.objects), None)
            return (placed is not None, placed.object_id if placed is not None else None)
        return (True, None)

    def available(self, world: "SimulationWorld") -> list[str]:
        """The punishments somebody can be given as things stand, the mildest first."""
        punishments = self.settings(world).punishments
        return [
            punishment_id
            for punishment_id, definition in sorted(punishments.items(), key=lambda entry: (entry[1].severity, entry[0]))
            if self.place_for(world, definition)[0]
        ]

    def missing_for(self, world: "SimulationWorld", definition: PunishmentDefinition) -> str:
        """What a punishment the settlement has no place for wants, in words."""
        if definition.building is not None:
            use = world.registries.housing.uses.get(definition.building, definition.building)
            return f"hace falta un edificio que sea {use}"
        names = []
        for kind in definition.objects:
            found = world.registries.interactables.find(kind)
            names.append(f"{found.article} {found.name}" if found is not None else kind)
        return f"hace falta {' o '.join(names)}"

    # ----- the punishment -----

    def sentence(self, world: "SimulationWorld", trial_id: str, punishment_id: str) -> JusticeResult:
        """Say what somebody found guilty is given, and have it carried out."""
        trial = world.courts.trials.get(trial_id)
        definition = self.settings(world).punishments.get(punishment_id)
        if trial is None or not trial.awaiting_sentence:
            return JusticeResult(False, "No hay nadie esperando condena")
        if definition is None:
            return JusticeResult(False, "No hay tal castigo")
        resident = world.residents.get(trial.accused)
        if resident is None:
            self._close(world, trial)
            return JusticeResult(False, "Ya no está para cumplirla")
        there, place_id = self.place_for(world, definition)
        if not there:
            return JusticeResult(False, f"No se le puede condenar a {definition.name}: {self.missing_for(world, definition)}")
        trial.punishment = punishment_id
        self._close(world, trial)
        name = resident.name
        record = self._record(world, trial, resident, definition)
        self._carry_out(world, trial, resident, definition, place_id)
        text = f"{name} {definition.said or 'recibe su castigo'}"
        event = PoliticalEvent(
            "punishment_carried",
            min(100, 40 + definition.severity * 6),
            text,
            [trial.accused],
            data={
                "trial_id": trial.trial_id, "resident_id": trial.accused, "punishment": punishment_id,
                "offence": trial.offence, "harsh": definition.harsh, "public": definition.public,
                "present": list(record.present), "reactions": dict(record.reactions),
            },
            government=world.government.kind,
        )
        # Whoever was there knows of it, and can tell whoever was not.
        event.witnesses = [each for each in record.present if each in world.residents]
        world.emit_event(event, fact_text=f"a {name} le condenaron a {definition.name}", subjects=[trial.accused])
        return JusticeResult(True, text, trial.trial_id)

    def _record(
        self, world: "SimulationWorld", trial: Trial, resident: Resident, definition: PunishmentDefinition
    ) -> PunishmentRecord:
        """Put a punishment on record, with who is there, who of them is the condemned's own,
        and how each takes it: their own way, and never the same for everybody."""
        settings = self.settings(world)
        condemned = resident.resident_id
        seen = set(witnesses_of(world, resident.tile, exclude=[condemned])) if definition.public else set()
        present = [
            other.resident_id
            for other in world.residents.values()
            if other is not resident and not other.away and (other.resident_id in seen or not definition.public)
        ]
        # Whoever is the condemned's own takes it as theirs wherever they were.
        own = [
            other.resident_id
            for other in world.residents.values()
            if other is not resident and not other.away and other.resident_id not in present
            and self._close_to(world, other, resident)
        ]
        child = world.children.is_child(world, resident)
        record = PunishmentRecord(
            condemned, resident.name, trial.offence, definition.punishment_id, world.clock.total_minutes,
            trial.trial_id, present=list(present), child=child,
        )
        gravity = settings.offences[trial.offence].gravity if trial.offence in settings.offences else 1
        shifts: dict[str, float] = {}
        for other_id in [*present, *own]:
            other = world.residents[other_id]
            kin = other.couple_with == condemned or world.family.kin.close(world, other_id, condemned)
            feelings = world.relationships.get((other_id, condemned))
            friend = not kin and feelings is not None and feelings.affection >= settings.friend_from
            if kin:
                record.kin.append(other_id)
            elif friend:
                record.friends.append(other_id)
            holds = trial.ballots.get(other_id)
            if holds is None:
                holds = self.holds_guilty(world, other, trial)
            reaction = self._reaction(settings, definition, gravity, kin or friend, holds, child)
            record.reactions[other_id] = reaction
            # Seen, it is felt in full. Heard of, by as much as reaches whoever was not there.
            share = 1.0 if (definition.public and other_id in seen) or kin or friend else settings.heard_share
            weight = definition.severity * share * (settings.child_factor if child and reaction != APPROVAL else 1.0)
            self._feel(world, other, resident, trial, definition, reaction, weight, kin)
            for measure, delta in settings.measures.get(reaction, {}).items():
                shifts[measure] = shifts.get(measure, 0.0) + delta * weight
        if definition.harsh:
            for measure, delta in settings.harsh.items():
                shifts[measure] = shifts.get(measure, 0.0) + delta
        count = max(1, len(record.reactions))
        # The settlement is moved by how those who know of it took it, as a share of them.
        world.politics.legitimacy.shock(world, {measure: delta / count * 4.0 for measure, delta in shifts.items()})
        world.courts.history.append(record)
        return record

    def _close_to(self, world: "SimulationWorld", other: Resident, resident: Resident) -> bool:
        if other.couple_with == resident.resident_id or world.family.kin.close(world, other.resident_id, resident.resident_id):
            return True
        feelings = world.relationships.get((other.resident_id, resident.resident_id))
        return feelings is not None and feelings.affection >= self.settings(world).friend_from

    @staticmethod
    def _reaction(
        settings: JusticeSettings, definition: PunishmentDefinition, gravity: int, own: bool, holds: bool, child: bool
    ) -> str:
        """How somebody takes a punishment: by whether the condemned is one of their own,
        whether they hold them guilty, and how far it goes beyond what was done."""
        beyond = definition.severity - gravity
        if own:
            return GRIEF if definition.harsh or beyond >= settings.harsher_by else ANGER
        if not holds:
            return ANGER if definition.severity >= settings.indifferent_below else INDIFFERENCE
        if child and definition.severity >= settings.harsher_by:
            # Nobody is glad of what is done to a child, whatever the child did.
            return FEAR
        if beyond >= settings.harsher_by:
            return FEAR
        return APPROVAL if definition.severity >= settings.indifferent_below else INDIFFERENCE

    def _feel(
        self,
        world: "SimulationWorld",
        other: Resident,
        condemned: Resident,
        trial: Trial,
        definition: PunishmentDefinition,
        reaction: str,
        weight: float,
        kin: bool,
    ) -> None:
        """Have somebody feel a punishment the way they take it, and remember it their own way."""
        settings = self.settings(world)
        profile = world.politics.legitimacy.profile(world, other)
        for name, delta in settings.felt.get(reaction, {}).items():
            if name == "stress":
                other.needs.apply({"stress": delta * weight / 2.0})
            elif name == "mood":
                other.adjust_mood(delta * weight / 2.0)
            else:
                profile.adjust(name, delta * weight)
        if definition.harsh:
            for name, delta in settings.felt.get(FEAR, {}).items():
                profile.adjust(name, delta * weight / 2.0)
        if reaction == INDIFFERENCE:
            return
        who = condemned.name
        if kin:
            who = f"{condemned.name}, {world.family.kin.word(world, other.resident_id, condemned.resident_id)} mía"
            who = who.replace("pareja mía", "mi pareja").replace("conocido mía", "de los míos")
        texts = {
            APPROVAL: (f"A {condemned.name} le condenaron a {definition.name}. Se hizo justicia.", 0.4),
            FEAR: (f"A {condemned.name} le condenaron a {definition.name}. Fue demasiado, y pudo ser cualquiera.", -0.5),
            ANGER: (f"A {who} le condenaron a {definition.name} sin que estuviera claro.", -0.7),
            GRIEF: (f"A {who} le condenaron a {definition.name}. No lo voy a olvidar.", -1.0),
        }
        text, mood = texts[reaction]
        world.memories.remember(
            other.resident_id,
            Memory(
                text, min(100.0, 20.0 + definition.severity * MEMORY_PER_SEVERITY), mood, [condemned.resident_id],
                ["punishment", reaction, definition.punishment_id], world.clock.total_minutes,
            ),
        )

    def _carry_out(
        self, world: "SimulationWorld", trial: Trial, resident: Resident, definition: PunishmentDefinition, place_id: str | None
    ) -> None:
        """Do to somebody what they were given."""
        now = world.clock.total_minutes
        kind = definition.punishment_id
        resident.needs.apply({"stress": float(definition.severity)})
        if kind == FINE:
            self._fine(world, resident, definition.amount)
        elif kind == CONFISCATION:
            self._confiscate(world, resident, definition.things)
        elif kind in (SERVICE, STOCKS, PRISON):
            minutes = definition.days * MINUTES_PER_DAY + definition.hours * 60
            world.courts.sentences.append(Sentence(resident.resident_id, kind, trial.trial_id, now + minutes, place_id))
            resident.activity = None
            resident.current_action = "idle"
        elif kind == CORPORAL:
            world.health.hurt(world, resident, definition.harm, CORPORAL_INJURY, f"el {definition.name}")
        elif kind == EXILE:
            offence = self.settings(world).offences.get(trial.offence)
            world.politics.exile.banish(world, resident, offence.name if offence is not None else "", trial.accuser)
        elif kind == EXECUTION:
            world.health.die(world, resident, definition.cause or definition.name)

    def _fine(self, world: "SimulationWorld", resident: Resident, amount: float) -> None:
        """Take a fine into the common fund: in coin, or under barter in things of theirs worth as much."""
        if world.fund.currency(world) is not None:
            paid = max(0.0, min(resident.credits, amount))
            resident.credits -= paid
            world.fund.pay_in(world, paid)
            return
        resolve = world.registries.items.resolve
        owed = amount
        for item in self._own_things(world, resident):
            if owed <= 0:
                break
            owed -= resolve(item.definition_id).base_value
            self._seize(world, resident, item)

    def _confiscate(self, world: "SimulationWorld", resident: Resident, things: int) -> None:
        """Take what is worth most of what somebody carries of their own, for the settlement."""
        for item in self._own_things(world, resident)[: max(0, things)]:
            self._seize(world, resident, item)

    def _own_things(self, world: "SimulationWorld", resident: Resident) -> list:
        resolve = world.registries.items.resolve
        own = [item for item in resident.inventory.items if item.owner_id == resident.resident_id]
        return sorted(own, key=lambda item: (-resolve(item.definition_id).base_value, item.instance_id))

    def _seize(self, world: "SimulationWorld", resident: Resident, item) -> None:
        store = world.fund.store_for(world, resident.tile)
        if store is not None:
            world.fund.take_in(world, resident.inventory, item, resident.tile, into=store)

    # ----- serving a sentence -----

    def sentence_of(self, world: "SimulationWorld", resident_id: str) -> Sentence | None:
        """What a resident is serving right now, if anything."""
        return next((each for each in world.courts.sentences if each.resident_id == resident_id), None)

    def confined(self, world: "SimulationWorld", resident_id: str) -> bool:
        """Whether a resident is locked up or in the stocks, and so goes nowhere and does nothing else."""
        sentence = self.sentence_of(world, resident_id)
        return sentence is not None and sentence.punishment in (PRISON, STOCKS)

    def ration(self, world: "SimulationWorld") -> Ration:
        """What prisoners are given each day: what the player said, or else what the data says."""
        settings = self.settings(world)
        return world.courts.ration or Ration(settings.meals, settings.drinks, settings.food, settings.drink)

    def set_ration(self, world: "SimulationWorld", meals: int, drinks: int, food: str = "", drink: str = "") -> JusticeResult:
        """Say how much a prisoner is given each day, and of what. An item left unsaid is
        whatever of the kind there is most of."""
        most = self.settings(world).most_rations
        for item_id, category in ((food, FOOD_CATEGORY), (drink, WATER_CATEGORY)):
            definition = world.registries.items.find(item_id) if item_id else None
            if item_id and (definition is None or definition.category != category):
                return JusticeResult(False, "Eso no es de comer ni de beber")
        if not (0 <= meals <= most and 0 <= drinks <= most):
            return JusticeResult(False, f"De nada a {most} al día, de cada cosa")
        world.courts.ration = Ration(int(meals), int(drinks), food, drink)
        parts = [f"{meals} de comer", f"{drinks} de beber"]
        return JusticeResult(True, f"A los presos, al día: {' y '.join(parts)}")

    def _serve(self, world: "SimulationWorld", sentence: Sentence) -> None:
        """One minute of a sentence: whoever serves it is kept where it is served, and fed if they are locked up."""
        resident = world.residents.get(sentence.resident_id)
        state = world.courts
        if resident is None:
            state.sentences.remove(sentence)
            return
        now = world.clock.total_minutes
        definition = self.settings(world).punishments.get(sentence.punishment)
        if now >= sentence.until or definition is None:
            state.sentences.remove(sentence)
            if resident.activity is not None and resident.activity.action == SERVE_ACTION:
                resident.activity = None
                resident.current_action = "idle"
            name = definition.name if definition is not None else "su condena"
            world.emit_event(
                DomainEvent(
                    "sentence_served", SERVED_IMPORTANCE, f"{resident.name} ha cumplido: {name}",
                    [resident.resident_id], data={"punishment": sentence.punishment},
                ),
                at=resident.tile,
            )
            return
        if sentence.punishment == SERVICE:
            # Working for everybody is their day as it was, and it weighs on them.
            if world.clock.hour == 0 and world.clock.minute == 0:
                resident.needs.apply({"stress": 6.0})
                resident.adjust_mood(-3.0)
            return
        if resident.away:
            return
        spot = self._spot(world, sentence)
        if spot is None:
            # Where it was served is gone: so is what was left of it.
            sentence.until = now
            return
        if resident.tile != spot:
            activity = resident.activity
            if activity is None or activity.action != SERVE_ACTION or not activity.path:
                path = find_path(resident.tile, spot, world.passable())
                if path:
                    resident.activity = Activity(SERVE_ACTION, None, path, SERVE_MINUTES)
                    resident.current_action = "walking"
                else:
                    resident.x, resident.y = spot
        else:
            resident.activity = Activity(SERVE_ACTION, None, [], SERVE_MINUTES, using=True)
            resident.current_action = SERVE_ACTION
            if world.is_dark():
                # By night they sleep where they are, as whoever has no bed does, and with
                # nothing else to do they sleep the night through.
                rough = world.registries.family.rough_per_minute
                resident.needs.apply({need: delta * (NIGHT_REST if delta < 0 else 1.0) for need, delta in rough.items()})
        if sentence.punishment == PRISON:
            self._feed(world, resident, sentence)

    def _spot(self, world: "SimulationWorld", sentence: Sentence) -> Tile | None:
        """The tile a sentence is served on: inside the building, or by the object."""
        room = world.rooms.get(sentence.place_id or "")
        passable = world.passable()
        if room is not None:
            tiles = [(x, y) for y in range(room.y, room.y + room.height) for x in range(room.x, room.x + room.width)]
            free = [tile for tile in tiles if passable(tile)]
            return free[len(free) // 2] if free else None
        placed = world.interactables.get(sentence.place_id or "")
        if placed is None:
            return None
        beside = [(placed.x, placed.y + 1), (placed.x + 1, placed.y), (placed.x - 1, placed.y), (placed.x, placed.y - 1)]
        return next((tile for tile in beside if passable(tile)), (placed.x, placed.y))

    def _feed(self, world: "SimulationWorld", resident: Resident, sentence: Sentence) -> None:
        """Give a prisoner what they are given, at even hours through the day, out of what is everybody's."""
        ration = self.ration(world)
        minute = world.clock.hour * 60 + world.clock.minute
        for times, item_id, category in (
            (ration.meals, ration.food, FOOD_CATEGORY), (ration.drinks, ration.drink, WATER_CATEGORY),
        ):
            if times <= 0 or minute % (MINUTES_PER_DAY // times) != (MINUTES_PER_DAY // times) // 2:
                continue
            given = item_id if item_id and world.fund.goods(world).get(item_id, 0) > 0 else self._plentiful(world, category)
            if given is None or world.fund.take_goods(world, given, 1)[0] < 1:
                if sentence.unfed_on != world.clock.day:
                    sentence.unfed_on = world.clock.day
                    word = "comer" if category == FOOD_CATEGORY else "beber"
                    world.emit_event(
                        DomainEvent(
                            "prisoner_unfed", UNFED_IMPORTANCE, f"No hay qué darle de {word} a {resident.name}, que está preso",
                            [resident.resident_id],
                        )
                    )
                continue
            resident.needs.apply(world.registries.items.resolve(given).effects)

    def _plentiful(self, world: "SimulationWorld", category: str) -> str | None:
        """The thing of a kind that is nobody's and that there is most of."""
        find = world.registries.items.find
        held = [
            (units, item_id)
            for item_id, units in world.fund.goods(world).items()
            if units > 0 and (definition := find(item_id)) is not None and definition.category == category
        ]
        return max(held)[1] if held else None

    # ----- whoever was exiled, heard of again -----

    def left(self, world: "SimulationWorld", resident: Resident, exile: "Exile") -> None:
        """Somebody thrown out is going through the gate: keep who they were, and say when
        they will be heard of again. The grudge they leave with is what they hold against the
        government."""
        settings = self.settings(world)
        if not settings.punishments:
            return
        first, last = settings.return_days
        exile.back_at = world.clock.total_minutes + world.rng.randint(first, last) * MINUTES_PER_DAY
        exile.grudge = world.politics.legitimacy.profile(world, resident).resentment / 100.0
        exile.person = {
            "age": resident.age, "born": resident.born, "sex": resident.sex, "gender": resident.gender,
            "drawn_to": resident.drawn_to, "traits": list(resident.traits), "manners": dict(resident.manners),
            "personality": dict(vars(resident.personality)),
        }

    def _returns(self, world: "SimulationWorld") -> None:
        """Once a day, have whoever was exiled and is due be heard of: at the gate asking to
        come back, or, for one who left with a grudge, with raiders."""
        state, settings = world.courts, self.settings(world)
        now = world.clock.total_minutes
        for exile in world.exiled:
            if exile.back_at is None or exile.back_at > now or exile.resident_id in world.residents:
                continue
            if state.at_gate is not None and state.at_gate != exile.resident_id:
                continue
            if exile.tries == 0 and world.rng.random() < settings.raid_chance * exile.grudge and self._raid(world, exile):
                exile.back_at = None
                continue
            exile.tries += 1
            keeper = world.happenings.anyone_home(world)
            known = EXILE_BACK_DECISION in world.registries.decisions
            if keeper is not None and known and not world.happenings.gate_is_busy(world):
                feelings = world.relationships.get((keeper.resident_id, exile.resident_id))
                inputs = {
                    "affection": (feelings.affection if feelings is not None else 0.0) / 100.0,
                    "resentment": (feelings.resentment if feelings is not None else 0.0) / 100.0,
                    "kin": 1.0 if world.family.kin.close(world, keeper.resident_id, exile.resident_id) else 0.0,
                }
                if world.interventions.ask(world, keeper, EXILE_BACK_DECISION, exile.name, inputs) is not None:
                    state.at_gate = exile.resident_id
                    exile.back_at = None
                    world.emit_event(
                        DomainEvent(
                            "exile_at_gate", RETURN_IMPORTANCE, f"{exile.name}, a quien echaron, llama a la puerta",
                            [keeper.resident_id], data={"resident_id": exile.resident_id},
                        ),
                        at=keeper.tile,
                    )
                    continue
            # Nobody came to the gate: they try again tomorrow, a few days running.
            exile.back_at = now + MINUTES_PER_DAY if exile.tries < settings.return_tries else None

    def _raid(self, world: "SimulationWorld", exile: "Exile") -> bool:
        """Have somebody exiled come back with raiders, if raiders are a thing that happens here."""
        from simulation.events.world_event import RAID

        definition = next((each for each in world.registries.world_events.events.values() if each.kind == RAID), None)
        if definition is None or world.under_raid is not None:
            return False
        world.emit_event(
            DomainEvent(
                "exile_raid", RETURN_IMPORTANCE + 10, f"{exile.name}, a quien echaron, vuelve de noche y no viene solo",
                data={"resident_id": exile.resident_id},
            ),
            fact_text=f"{exile.name} volvió con merodeadores",
            subjects=[exile.resident_id],
        )
        world.happenings._raid(world, definition)
        return True

    def gate_answered(self, world: "SimulationWorld", keeper: Resident, lets_in: bool) -> None:
        """Carry out what whoever was at the gate decided about somebody exiled who asked to come back."""
        state = world.courts
        exile = next((each for each in world.exiled if each.resident_id == state.at_gate), None)
        state.at_gate = None
        if exile is None:
            return
        if not lets_in or exile.resident_id in world.residents:
            world.emit_event(
                DomainEvent(
                    "exile_turned_away", RETURN_IMPORTANCE - 15, f"{exile.name} se queda fuera, y se va",
                    [keeper.resident_id], data={"resident_id": exile.resident_id},
                )
            )
            return
        person = exile.person
        known = vars(Personality())
        x, y = world.happenings.arrival_tile(world)
        resident = Resident(
            exile.resident_id,
            exile.name,
            x=x,
            y=y,
            personality=Personality(**{k: float(v) for k, v in person.get("personality", {}).items() if k in known}),
            traits=[trait for trait in person.get("traits", []) if world.registries.traits.find(trait) is not None],
            manners=world.registries.manners.tidy(person.get("manners", {})),
            age=int(person.get("age", 30)),
            born=person.get("born"),
            sex=str(person.get("sex", "")),
            gender=str(person.get("gender", "")),
            drawn_to=str(person.get("drawn_to", "both")),
            last_worked=world.clock.total_minutes,
        )
        world.residents[resident.resident_id] = resident
        world.family.welcome(world, resident)
        exile.returned = True
        world.emit_event(
            DomainEvent(
                "exile_readmitted", RETURN_IMPORTANCE, f"{keeper.name} abre a {exile.name}, que vuelve al asentamiento",
                [resident.resident_id, keeper.resident_id], data={"resident_id": exile.resident_id},
            ),
            at=resident.tile,
            fact_text=f"{exile.name} volvió al asentamiento",
            subjects=[resident.resident_id],
        )

    # ----- a minute going by -----

    def tick(self, world: "SimulationWorld") -> None:
        """One minute: the trial going on moves on when its time comes, sentences are served,
        and once a day whoever knows of something thinks of accusing and the exiled are heard of."""
        state, settings = world.courts, self.settings(world)
        now = world.clock.total_minutes
        trial = self.open_trial(world)
        if trial is not None and now >= trial.next_at:
            if trial.awaiting_sentence:
                # Nothing was said of what to give them: it is the least there is.
                self.sentence(world, trial.trial_id, settings.unanswered)
            else:
                self._advance(world, trial)
        for sentence in list(state.sentences):
            self._serve(world, sentence)
        for resident_id in [each for each in state.weighing if world.interventions.pending_for(world, each) is None]:
            # What they were thinking over was overtaken by something else, or they are gone.
            del state.weighing[resident_id]
        if state.at_gate is not None and not any(d.kind == EXILE_BACK_DECISION for d in world.decisions.values()):
            # Nobody answered: they go.
            state.at_gate = None
        if world.clock.minute != 0:
            return
        if world.clock.hour == settings.accuse_hour:
            self._weigh_accusing(world)
        if world.clock.hour == 0 and world.exiled:
            self._returns(world)
