"""Who is in charge: how a settlement comes to have a government, who holds its seats, and
who follows them.

Whoever leads is a resident like any other, with a role. They may die, resign or lose a
vote, and none of it ends anything: the government's own way of succession names the next
one, or the seat stands empty until it does.
"""

from collections import Counter
from typing import TYPE_CHECKING

from simulation.ai.decision_system import advice_influence
from simulation.memory.memory import Memory
from simulation.politics.election import RIG
from simulation.politics.government import (
    COUNCIL,
    ELECTION,
    FOLLOWING,
    HEIR,
    OPEN,
    STRONGEST,
    VOTED_WAYS,
    GovernmentDefinition,
    PoliticsResult,
)
from simulation.politics.political_event import PoliticalEvent
from simulation.politics.records import COUNCIL_SEAT, LEADER_SEAT
from simulation.residents.resident import Resident

if TYPE_CHECKING:
    from simulation.world import SimulationWorld

# What a leader worn down, or with nobody behind them, makes up their mind about.
RESIGN = "resign"
CHOOSING_IMPORTANCE = 65
PROPOSED_IMPORTANCE = 40
CHOSEN_IMPORTANCE = 75
SEATED_IMPORTANCE = 65
COUNCIL_IMPORTANCE = 55
LOST_IMPORTANCE = 75
RESIGNED_IMPORTANCE = 65
CALLED_IMPORTANCE = 50
HELD_IMPORTANCE = 60
EMPTY_IMPORTANCE = 60
CHANGED_IMPORTANCE = 75
OFFICE_MEMORY = 70.0
# What somebody who has put themselves forward adds to their own name, over anybody else's.
OWN_VOTE = 1000.0
# Minutes a choice or a vote is put off when there is nobody about to make it.
PUT_OFF_MINUTES = 60
# How a leader came to the seat, for whoever tells it.
HOW = {
    ELECTION: "por votación de todos",
    COUNCIL: "por decisión del consejo",
    STRONGEST: "porque nadie se le pone delante",
    HEIR: "porque así lo dejó dicho quien mandaba",
    FOLLOWING: "porque es a quien sigue la gente",
}


class Leadership:
    def definition(self, world: "SimulationWorld") -> GovernmentDefinition | None:
        """The kind of government the settlement has. None before it has one."""
        return world.registries.politics.governments.get(world.government.kind or "")

    def present(self, world: "SimulationWorld") -> list[Resident]:
        """The adults who are in the settlement to be asked, or to be chosen."""
        return [
            resident
            for resident in world.residents.values()
            if world.bonds.is_adult(world, resident) and not resident.away
        ]

    def role_name(self, world: "SimulationWorld", role_id: str, resident: Resident | None = None) -> str:
        role = world.registries.politics.roles.get(role_id)
        return role.called(resident.gender if resident is not None else "") if role is not None else role_id

    def holds_office(self, world: "SimulationWorld", resident_id: str) -> bool:
        """Whether somebody governs: they lead, or sit on the council."""
        state = world.government
        return resident_id == state.leader or resident_id in state.council

    # ----- time -----

    def tick(self, world: "SimulationWorld") -> None:
        """One minute: a settlement that has grown to it chooses a government, a seat whose
        holder is gone is seen to, and a vote that was called is held when its time comes."""
        settings = world.registries.politics
        state = world.government
        now = world.clock.total_minutes
        if state.kind is None:
            if not settings.governments:
                return
            if state.choosing_until is None:
                if len(world.residents) >= settings.founding_residents:
                    self.open_choosing(world)
            elif now >= state.choosing_until:
                self.settle_choosing(world)
            return
        definition = self.definition(world)
        if definition is None:
            return
        if state.leader is not None and state.leader not in world.residents:
            self._lost(world, definition, state.leader)
        if any(member not in world.residents for member in state.council):
            state.council = [member for member in state.council if member in world.residents]
            self.fill_seats(world, definition, at_once=False)
        if state.election_at is not None:
            if now >= state.election_at:
                self._hold(world, definition)
            elif not state.rig_asked and now >= state.election_at - self._rig_minutes(world):
                # Whoever leads has had time to see how the vote is going to go.
                state.rig_asked = True
                if self._term_over(world, definition) or state.recall:
                    world.politics.elections.consider_rigging(world, definition)
        elif self._term_over(world, definition):
            self._call(world, definition, "se ha cumplido el plazo")

    def tick_day(self, world: "SimulationWorld") -> None:
        """Once a day: a seat that could not be filled is tried again, whoever leads has
        somebody in mind to follow them, and may think of stepping down."""
        state = world.government
        definition = self.definition(world)
        if definition is None:
            return
        if state.election_at is None:
            self.fill_seats(world, definition, at_once=False, announce=False)
        leader = world.residents.get(state.leader or "")
        if leader is None:
            return
        if HEIR in definition.succession:
            state.heir = self._name_heir(world, leader)
        settings = world.registries.politics
        worn = leader.needs.stress >= settings.resign_stress
        alone = state.measures["public_support"] <= settings.resign_support
        if (worn or alone) and not leader.away and RESIGN in world.registries.decisions:
            if world.interventions.asking_obstacle(world, leader, RESIGN) is None:
                world.interventions.ask(
                    world, leader, RESIGN, inputs={"support": state.measures["public_support"] / 100.0}
                )

    # ----- choosing a government -----

    def open_choosing(self, world: "SimulationWorld") -> None:
        """The settlement has grown to where it wants a government: the residents take some
        hours to settle on a kind, and the player may put one to them meanwhile."""
        state = world.government
        hours = world.registries.politics.choosing_hours
        state.choosing_until, state.proposed = world.clock.total_minutes + hours * 60, None
        world.emit_event(
            PoliticalEvent(
                "government_choosing",
                CHOOSING_IMPORTANCE,
                "Ya son bastantes para tener que ponerse de acuerdo: el asentamiento va a decidir cómo gobernarse",
                [resident.resident_id for resident in self.present(world)],
                data={"until": state.choosing_until, "kinds": list(world.registries.politics.governments)},
            )
        )

    def propose(self, world: "SimulationWorld", government_id: str) -> PoliticsResult:
        """The player puts a kind of government to everyone, once. It weighs with each resident
        by how they take advice and by what they hold already, and decides nothing by itself."""
        state = world.government
        definition = world.registries.politics.governments.get(government_id)
        if definition is None:
            return PoliticsResult(False, "No hay tal manera de gobernarse")
        if state.kind is not None or state.choosing_until is None:
            return PoliticsResult(False, "El asentamiento no está eligiendo cómo gobernarse")
        if state.proposed is not None:
            return PoliticsResult(False, "Ya se les ha propuesto una manera de gobernarse")
        state.proposed = government_id
        text = f"Se propone a todos gobernarse así: {definition.name}"
        world.emit_event(
            PoliticalEvent("government_proposed", PROPOSED_IMPORTANCE, text, data={"government": government_id})
        )
        return PoliticsResult(True, text)

    def appeal(self, world: "SimulationWorld", resident: Resident) -> dict[str, float]:
        """What a resident makes of each kind of government, by what they hold. The kind the
        player put to everyone counts for more with whoever heeds advice."""
        settings = world.registries.politics
        profile = world.politics.legitimacy.profile(world, resident)
        proposed = world.government.proposed
        heed = advice_influence(resident, 1.0) * world.tastes.heed(world, resident) if proposed is not None else 0.0
        scores: dict[str, float] = {}
        for government_id, definition in settings.governments.items():
            score = sum(
                weight * (getattr(profile, leaning) - 50.0) / 50.0 for leaning, weight in definition.appeal.items()
            )
            if government_id == proposed:
                score += settings.proposal_weight * heed
            scores[government_id] = score
        return scores

    def settle_choosing(self, world: "SimulationWorld") -> str | None:
        """Each adult who is here says which kind they would have, and the one most of them
        want is the government. Returns its ID, or None if there was nobody to say."""
        state = world.government
        voters = self.present(world)
        if not voters:
            state.choosing_until = world.clock.total_minutes + PUT_OFF_MINUTES
            return None
        wanted: dict[str, str] = {}
        for voter in voters:
            scores = self.appeal(world, voter)
            # Between two they like the same, the one that comes first in the data.
            wanted[voter.resident_id] = max(scores, key=lambda government_id: scores[government_id])
        count = Counter(wanted.values())
        chosen = max(world.registries.politics.governments, key=lambda government_id: count[government_id])
        self.establish(world, chosen, wanted)
        return chosen

    def establish(self, world: "SimulationWorld", government_id: str, wanted: dict[str, str] | None = None) -> None:
        """Give the settlement this kind of government, and fill its seats at once.

        `wanted` is the kind each resident who was asked would have had: how many of them
        wanted this one is how legitimate it starts.
        """
        settings = world.registries.politics
        definition = settings.governments[government_id]
        state = world.government
        wanted = wanted or {}
        behind = sum(1 for kind in wanted.values() if kind == government_id)
        share = behind / len(wanted) if wanted else 1.0
        state.kind, state.choosing_until, state.chosen_on = government_id, None, world.clock.day
        state.leader, state.council, state.election_at, state.heir, state.resigned = None, [], None, None, None
        state.term_began = world.clock.day
        state.measures.update({"stability": 50.0, "corruption": 0.0, "unrest": 0.0, **definition.starts})
        state.measures["legitimacy"] = settings.legitimacy_floor + (100.0 - settings.legitimacy_floor) * share
        world.politics.legitimacy.founded(world, wanted, government_id)
        world.emit_event(
            PoliticalEvent(
                "government_chosen",
                CHOSEN_IMPORTANCE,
                f"El asentamiento se gobernará así: {definition.name} ({behind} de {len(wanted)} lo querían)",
                list(wanted),
                data={"government": government_id, "wanted": dict(Counter(wanted.values()))},
                government=government_id,
            )
        )
        self.fill_seats(world, definition, at_once=True)
        world.politics.legitimacy.measure(world)

    def change_kind(self, world: "SimulationWorld", government_id: str, wanted: dict[str, str] | None = None) -> bool:
        """Have a settlement that has a government take another kind, in the middle of a game.

        Whoever held a seat holds it no longer, and the seats of the new kind are filled by its
        own ways. Returns whether there was such a kind to change to.
        """
        settings = world.registries.politics
        state = world.government
        if government_id not in settings.governments or state.kind is None or state.kind == government_id:
            return False
        before = self.definition(world)
        kept = {measure: state.measures[measure] for measure in ("stability", "corruption", "unrest", "legitimacy")}
        self._unseat(world, state.leader, before.leader_role if before else None)
        for member in state.council:
            self._unseat(world, member, before.council_role if before else None)
        name = settings.governments[government_id].name
        world.emit_event(
            PoliticalEvent(
                "government_changed",
                CHANGED_IMPORTANCE,
                f"El asentamiento cambia su manera de gobernarse: {name}",
                data={"from": state.kind, "to": government_id},
                government=government_id,
            )
        )
        self.establish(world, government_id, wanted)
        # What the place has been through is not wiped by a new name for who runs it.
        state.measures.update({measure: kept[measure] for measure in ("corruption", "unrest")})
        if wanted is None:
            state.measures["legitimacy"] = kept["legitimacy"]
        state.measures["stability"] = max(0.0, kept["stability"] + 1.5 * settings.change_stability)
        return True

    # ----- seats -----

    def fill_seats(
        self, world: "SimulationWorld", definition: GovernmentDefinition, at_once: bool, announce: bool = True
    ) -> None:
        """See to every seat that stands empty, by the government's own ways.

        A way that takes a vote is held on the spot when a government is set up, and called
        for later otherwise. The ways are tried in the order the government gives them. With
        `announce`, a seat nobody can be found for is said to stand empty.
        """
        state = world.government
        if definition.council_seats > len(state.council):
            if at_once:
                self._seat_council(world, definition)
            elif state.election_at is None:
                self._call(world, definition, "hay sitio en el consejo")
        if definition.leader_role is None or state.leader is not None:
            return
        for way in definition.succession:
            if way in VOTED_WAYS and not at_once:
                if state.election_at is None:
                    self._call(world, definition, "el puesto está vacío")
                return
            chosen, backers = self._by_way(world, way)
            if chosen is not None:
                self._seat(world, definition, chosen, way, backers)
                return
        if state.vacant_since is None:
            state.vacant_since = world.clock.total_minutes
        if announce:
            world.emit_event(
                PoliticalEvent(
                    "leader_seat_empty",
                    EMPTY_IMPORTANCE,
                    "No hay quien ocupe el puesto de mando: se queda vacío",
                    government=state.kind,
                )
            )

    def standing(
        self, world: "SimulationWorld", exclude: tuple[str, ...] | list[str] = (), at_least: int = 2
    ) -> list[Resident]:
        """Whoever stands in a vote for a seat: those who put themselves forward."""
        return world.politics.elections.candidates(world, exclude, at_least)

    def _by_way(self, world: "SimulationWorld", way: str) -> tuple[Resident | None, set[str]]:
        """Whoever a way of succession names, and who was behind them. Nobody, if it names nobody."""
        state = world.government
        standing = [resident for resident in self.present(world) if resident.resident_id != state.resigned]
        if not standing:
            return None, set()
        if way == ELECTION:
            return self.elect(world, self.present(world), self.standing(world), way=ELECTION)
        if way == COUNCIL:
            sitting = [resident for resident in self.present(world) if resident.resident_id in state.council]
            return self.elect(world, sitting, self.standing(world), way=COUNCIL)
        if way == HEIR:
            heir = next((resident for resident in standing if resident.resident_id == state.heir), None)
            return heir, set()
        weights = world.registries.politics.ways.get(way, {})
        if way == STRONGEST:
            return max(standing, key=lambda resident: self._strength(world, resident, weights)), set()
        if way == FOLLOWING:
            return max(standing, key=lambda resident: self._following(world, resident, weights)), set()
        return None, set()

    def elect(
        self,
        world: "SimulationWorld",
        voters: list[Resident],
        standing: list[Resident],
        seat: str = LEADER_SEAT,
        way: str = ELECTION,
        record: bool = True,
    ) -> tuple[Resident | None, set[str]]:
        """Have each voter back whoever they would rather have, and return whoever most of
        them back, with the IDs of those who did. Nobody without voters or anyone standing.

        With `record` the result is given out and kept: where whoever leads has seen to the
        count, it is given out their way. Without it nothing is kept: it is only how a vote
        would go.
        """
        if not voters or not standing:
            return None, set()
        weights = world.registries.politics.ways.get(ELECTION, {})
        backed: dict[str, str] = {}
        for voter in voters:
            best = max(standing, key=lambda candidate: self.vote_score(world, voter, candidate, weights))
            backed[voter.resident_id] = best.resident_id
        count = Counter(backed.values())
        # Between two with as many behind them, whoever would lead better on the face of it.
        winner = max(standing, key=lambda candidate: (count[candidate.resident_id], self._merit(candidate, weights)))
        if record:
            winner = world.politics.elections.settle(world, seat, way, standing, backed, winner)
        return winner, {voter_id for voter_id, candidate_id in backed.items() if candidate_id == winner.resident_id}

    def vote_score(
        self, world: "SimulationWorld", voter: Resident, candidate: Resident, weights: dict[str, float] | None = None
    ) -> float:
        """How much a voter would have a candidate lead: what they feel for them, how readily
        the candidate wins people over and how well they lead, and for whoever leads already,
        the loyalty they have earned or lost. Someone votes for themselves only if politics
        matter enough to them. What the player said to them for a candidate counts for that one."""
        if weights is None:
            weights = world.registries.politics.ways.get(ELECTION, {})
        score = self._merit(candidate, weights)
        spoken_for = world.government.backing.get(voter.resident_id)
        if spoken_for is not None and spoken_for[0] == candidate.resident_id:
            score += float(spoken_for[1])
        if voter is candidate:
            mark = weights.get("stand_from")
            if mark is not None and world.politics.elections.will(world, voter) >= mark:
                # Whoever wants the seat enough to put themselves forward is for themselves.
                return score + OWN_VOTE
            interest = world.politics.legitimacy.profile(world, voter).political_interest
            return score + weights.get("self", 1.0) * (interest - weights.get("self_from", 70.0))
        feelings = world.relationships.get((voter.resident_id, candidate.resident_id))
        if feelings is not None:
            score += sum(
                weights.get(name, 0.0) * getattr(feelings, name) for name in ("affection", "trust", "resentment", "fear")
            )
        if candidate.resident_id == world.government.leader:
            loyalty = world.politics.legitimacy.profile(world, voter).loyalty
            # Loyalty earned beyond what anyone starts with counts for them, and loyalty lost against.
            score += weights.get("loyalty", 0.5) * (loyalty - world.registries.politics.loyalty_base)
        return score

    def _merit(self, candidate: Resident, weights: dict[str, float]) -> float:
        sides = candidate.personality
        return weights.get("charisma", 0.4) * sides.charisma + weights.get("leadership", 0.3) * sides.leadership

    def felt_for(self, world: "SimulationWorld", resident: Resident, feeling: str) -> float:
        """What the others who are here feel for a resident, on average."""
        others = [other for other in self.present(world) if other is not resident]
        felt = [world.relationships.get((other.resident_id, resident.resident_id)) for other in others]
        return sum(getattr(each, feeling) for each in felt if each is not None) / len(others) if others else 0.0

    def _strength(self, world: "SimulationWorld", resident: Resident, weights: dict[str, float]) -> float:
        sides = resident.personality
        return (
            weights.get("courage", 1.0) * sides.courage
            + weights.get("aggression", 0.5) * sides.aggression
            + weights.get("leadership", 0.5) * sides.leadership
            + weights.get("health", 0.3) * resident.health
            + weights.get("feared", 1.0) * self.felt_for(world, resident, "fear")
        )

    def _following(self, world: "SimulationWorld", resident: Resident, weights: dict[str, float]) -> float:
        sides = resident.personality
        liked = self.felt_for(world, resident, "affection") + self.felt_for(world, resident, "trust")
        return (
            weights.get("charisma", 1.0) * sides.charisma
            + weights.get("leadership", 0.3) * sides.leadership
            + weights.get("liked", 0.5) * (liked - self.felt_for(world, resident, "resentment"))
        )

    def _name_heir(self, world: "SimulationWorld", leader: Resident) -> str | None:
        """Whoever a leader would have follow them: their partner, the grown kin they care
        for most, or failing those whoever they think most of, if it is enough."""
        weights = world.registries.politics.ways.get(HEIR, {})

        def regard(other: Resident) -> float:
            feelings = world.relationships.get((leader.resident_id, other.resident_id))
            return feelings.affection + feelings.trust if feelings is not None else 0.0

        others = [
            other
            for other in world.residents.values()
            if other is not leader and world.bonds.is_adult(world, other)
        ]
        partner = next((other for other in others if other.resident_id == leader.couple_with), None)
        if partner is not None:
            return partner.resident_id
        kin = [other for other in others if world.family.kin.close(world, leader.resident_id, other.resident_id)]
        if kin:
            return max(kin, key=regard).resident_id
        best = max(others, key=regard, default=None)
        if best is not None and regard(best) >= weights.get("regard", 60.0):
            return best.resident_id
        return None

    def _seat(
        self, world: "SimulationWorld", definition: GovernmentDefinition, resident: Resident, way: str, backers: set[str]
    ) -> None:
        state = world.government
        role = definition.leader_role
        if role is not None and role not in resident.roles:
            resident.roles.append(role)
        state.leader, state.vacant_since, state.resigned = resident.resident_id, None, None
        state.term_began = world.clock.day
        world.politics.legitimacy.seated(world, resident, way, backers)
        called = self.role_name(world, role or "", resident)
        world.memories.remember(
            resident.resident_id,
            Memory(f"Me toca mandar: soy {called}.", OFFICE_MEMORY, 0.4, [], ["politics"], world.clock.total_minutes),
        )
        # Who was behind them is known after a show of hands, and not after a vote cast in secret.
        shown = sorted(backers) if definition.ballot == OPEN else []
        world.emit_event(
            PoliticalEvent(
                "leader_chosen",
                SEATED_IMPORTANCE,
                f"{resident.name} es {called}, {HOW.get(way, 'porque así ha salido')}",
                [resident.resident_id],
                data={"role": role, "way": way, "backers": shown},
                government=state.kind,
            ),
            at=resident.tile,
        )

    def _seat_council(self, world: "SimulationWorld", definition: GovernmentDefinition) -> None:
        """Fill the council's empty seats with whoever most of the residents back, one seat at a time."""
        state = world.government
        seated: list[str] = []
        while len(state.council) < definition.council_seats:
            left = definition.council_seats - len(state.council)
            standing = self.standing(world, exclude=state.council, at_least=left + 1)
            chosen, _backers = self.elect(world, self.present(world), standing, seat=COUNCIL_SEAT)
            if chosen is None:
                break
            state.council.append(chosen.resident_id)
            seated.append(chosen.resident_id)
            if definition.council_role is not None and definition.council_role not in chosen.roles:
                chosen.roles.append(definition.council_role)
        if seated:
            names = ", ".join(world.residents[each].name for each in seated)
            world.emit_event(
                PoliticalEvent(
                    "council_seated",
                    COUNCIL_IMPORTANCE,
                    f"Se sientan en el consejo: {names}",
                    seated,
                    data={"role": definition.council_role, "council": list(state.council)},
                    government=state.kind,
                )
            )

    def _unseat(self, world: "SimulationWorld", resident_id: str | None, role: str | None) -> None:
        resident = world.residents.get(resident_id or "")
        if resident is not None and role in resident.roles:
            resident.roles.remove(role)

    # ----- losing a leader -----

    def _lost(self, world: "SimulationWorld", definition: GovernmentDefinition, leader_id: str) -> None:
        """Whoever led is dead or gone. The seat is empty, and the government sees to it."""
        state = world.government
        death = next((each for each in reversed(world.deaths) if each.resident_id == leader_id), None)
        record = world.kinship.get(leader_id)
        name = death.name if death is not None else record.name if record is not None else leader_id
        called = self.role_name(world, definition.leader_role or "")
        state.leader, state.vacant_since = None, world.clock.total_minutes
        world.politics.legitimacy.shock(world, {"stability": world.registries.politics.lost_stability})
        world.emit_event(
            PoliticalEvent(
                "leader_lost",
                LOST_IMPORTANCE,
                f"{name}, {called}, ha muerto" if death is not None else f"{name}, {called}, ya no está",
                data={"resident_id": leader_id, "role": definition.leader_role, "died": death is not None},
                government=state.kind,
            )
        )
        self.fill_seats(world, definition, at_once=False)

    def resign(self, world: "SimulationWorld", resident: Resident) -> bool:
        """Have whoever leads, or sits on the council, step down. They stay in the settlement
        as anybody, and are not the one to follow themselves. Returns whether they held a seat."""
        state = world.government
        definition = self.definition(world)
        if definition is None or not self.holds_office(world, resident.resident_id):
            return False
        leading = state.leader == resident.resident_id
        role = definition.leader_role if leading else definition.council_role
        self._unseat(world, resident.resident_id, role)
        if leading:
            state.leader, state.vacant_since, state.resigned = None, world.clock.total_minutes, resident.resident_id
            world.politics.legitimacy.shock(world, {"stability": world.registries.politics.change_stability})
        else:
            state.council.remove(resident.resident_id)
        called = self.role_name(world, role or "", resident)
        world.memories.remember(
            resident.resident_id,
            Memory(f"Dejé de ser {called}.", OFFICE_MEMORY, -0.2, [], ["politics"], world.clock.total_minutes),
        )
        world.emit_event(
            PoliticalEvent(
                "leader_resigned" if leading else "council_seat_left",
                RESIGNED_IMPORTANCE,
                f"{resident.name} deja de ser {called}",
                [resident.resident_id],
                data={"role": role},
                government=state.kind,
            ),
            at=resident.tile,
        )
        self.fill_seats(world, definition, at_once=False)
        return True

    # ----- votes for a seat -----

    def _term_over(self, world: "SimulationWorld", definition: GovernmentDefinition) -> bool:
        state = world.government
        if definition.term_days <= 0 or world.clock.day - state.term_began < definition.term_days:
            return False
        voted_leader = state.leader is not None and any(way in VOTED_WAYS for way in definition.succession)
        return voted_leader or bool(state.council)

    def recall(self, world: "SimulationWorld") -> bool:
        """Call a vote that whoever leads has to win to go on leading, term or no term, and
        that seats the council anew. Returns whether one was called: not where one is already."""
        state = world.government
        definition = self.definition(world)
        if definition is None or state.election_at is not None:
            return False
        state.recall = True
        self._call(world, definition, "así se ha decidido")
        return True

    def _rig_minutes(self, world: "SimulationWorld") -> int:
        """How long before a vote whoever leads thinks of seeing to the count: never more than half the wait for it."""
        settings = world.registries.politics
        return min(settings.rig_hours * 60, settings.election_hours * 30)

    def _call(self, world: "SimulationWorld", definition: GovernmentDefinition, why: str) -> None:
        state = world.government
        state.rigged_by, state.rig_asked, state.backing = None, False, {}
        state.election_at = world.clock.total_minutes + world.registries.politics.election_hours * 60
        world.emit_event(
            PoliticalEvent(
                "election_called",
                CALLED_IMPORTANCE,
                f"Se llama a votar: {why}",
                data={"at": state.election_at},
                government=state.kind,
            )
        )

    def _hold(self, world: "SimulationWorld", definition: GovernmentDefinition) -> None:
        """The vote that was called is held: the council is seated again if its term is over,
        empty seats are filled, and whoever leads has to win to go on leading."""
        state = world.government
        if not self.present(world):
            state.election_at = world.clock.total_minutes + PUT_OFF_MINUTES
            return
        waiting = world.interventions.pending_for(world, state.leader or "")
        if waiting is not None and waiting.kind == RIG:
            # The hour has come: whoever was still making up their mind about the count does it now.
            world.interventions.resolve(world, waiting.decision_id, None)
        state.election_at = None
        over = self._term_over(world, definition) or state.recall
        state.recall = False
        if over and state.council:
            for member in state.council:
                self._unseat(world, member, definition.council_role)
            state.council = []
        if definition.council_seats > len(state.council):
            self._seat_council(world, definition)
        way = next((way for way in definition.succession if way in VOTED_WAYS), None)
        if definition.leader_role is None or way is None:
            state.term_began = world.clock.day
            return
        incumbent = world.residents.get(state.leader or "")
        if incumbent is not None and not over:
            return
        winner, backers = self._by_way(world, way)
        state.rigged_by, state.backing = None, {}
        if winner is None:
            # Nobody to vote, or nobody to vote for: the seat is tried again another day.
            return
        held = state.elections[-1] if state.elections else None
        if held is not None and (held.at != world.clock.total_minutes or held.winner != winner.resident_id):
            held = None
        incumbent_id = incumbent.resident_id if incumbent is not None else None
        if held is not None:
            world.politics.elections.took_part(world, held, incumbent_id)
        if winner is incumbent:
            state.term_began = world.clock.day
            world.politics.legitimacy.shock(world, world.registries.politics.seated.get(way, {}))
            text = f"{winner.name} sigue siendo {self.role_name(world, definition.leader_role, winner)} tras la votación"
        else:
            if incumbent is not None:
                self._unseat(world, incumbent.resident_id, definition.leader_role)
                world.politics.legitimacy.shock(world, {"stability": world.registries.politics.change_stability})
                world.memories.remember(
                    incumbent.resident_id,
                    Memory(
                        f"Perdí la votación: ahora manda {winner.name}.", OFFICE_MEMORY, -0.6,
                        [winner.resident_id], ["politics"], world.clock.total_minutes,
                    ),
                )
            state.leader = None
            self._seat(world, definition, winner, way, backers)
            text = f"{winner.name} gana la votación"
        # After a show of hands everybody knows who was behind whom. Otherwise only how many.
        shown = held is None or held.open_ballot
        world.emit_event(
            PoliticalEvent(
                "election_held",
                HELD_IMPORTANCE,
                text,
                [winner.resident_id],
                data={
                    "winner": winner.resident_id,
                    "backers": sorted(backers) if shown else [],
                    "kept": winner is incumbent,
                    "tally": dict(held.tally) if held is not None else {},
                    "open": shown,
                },
                government=state.kind,
            )
        )
        if held is not None:
            world.politics.elections.contested(world, held, incumbent_id)
