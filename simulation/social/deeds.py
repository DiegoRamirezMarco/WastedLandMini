"""What an exchange does beyond what the two of them come to feel (S63).

Some things are done to somebody: cowing them, getting round them, worming something out of
them. Which exchange does what is data (`deeds` in `data/social.json`); how each is done is
here, one small function to a deed. Whoever went to do it is the doer, and the other is who
it was done to.

A deed may be done once the doer has had their say, or once the other has heard them out:
what changes what the other does next is theirs to do, when they are free to.
"""

from collections.abc import Callable
from typing import TYPE_CHECKING

from simulation.events.event import DomainEvent
from simulation.knowledge.knowledge_system import pass_on, striking_news
from simulation.residents.resident import Resident
from simulation.tastes.settings import KNOWN, UNKNOWN

if TYPE_CHECKING:
    from simulation.world import SimulationWorld

DEED_EVENT = "deed_done"
DEED_IMPORTANCE = 18
SWINDLE_IMPORTANCE = 40
# How much each deed does, where it is a matter of how much.
EASES = 12.0
STIRS = 10.0
MENDS = 40.0
TENDS = 6.0
TEACHES_MINUTES = 60.0
BRUISE = 6.0
SWINDLED = 5.0
IDLES = "sit"
EDIBLE = ("food", "drink")

Deed = Callable[["SimulationWorld", Resident, Resident], str | None]


def _said(world: "SimulationWorld", doer: Resident, other: Resident, text: str, importance: int = DEED_IMPORTANCE, fact: str | None = None) -> None:
    world.emit_event(
        DomainEvent(DEED_EVENT, importance, text, [doer.resident_id, other.resident_id]),
        at=doer.tile,
        fact_text=fact,
    )


def learn_news(world: "SimulationWorld", doer: Resident, other: Resident) -> str | None:
    """The doer has out of the other the most striking thing they know."""
    belief = striking_news(world, other, doer)
    if belief is None:
        return None
    pass_on(world, other, doer, belief)
    return None


def learn_taste(world: "SimulationWorld", doer: Resident, other: Resident) -> str | None:
    """Something the other likes or loathes comes out: to the doer, and to the player."""
    settings = world.registries.tastes
    profile = world.tastes.profile(world, other)
    hidden = [
        key
        for key in profile.keys()
        if world.taste_knowledge.state(doer.resident_id, other.resident_id, key, settings) != KNOWN
    ]
    if not hidden:
        return None
    # The strongest of what is not known yet, and before that what is not known at all.
    def weight(key: str) -> tuple[bool, float, str]:
        kind, _, name = key.partition(":")
        taste = profile.find(kind, name)
        unknown = world.taste_knowledge.state(doer.resident_id, other.resident_id, key, settings) == UNKNOWN
        return (unknown, abs(taste.value) if taste is not None else 0.0, key)

    key = max(hidden, key=weight)
    world.tastes.show(world, other, key, settings.known_at, [doer.resident_id])
    return None


def tend(world: "SimulationWorld", doer: Resident, other: Resident) -> str | None:
    """The worst of what ails the other is a little better for being seen to."""
    if not other.injuries:
        return None
    worst = max(other.injuries, key=lambda injury: injury.severity)
    worst.severity = max(0.0, worst.severity - TENDS)
    other.injuries = [injury for injury in other.injuries if injury.severity > 0]
    return f"{doer.name} le mira a {other.name} lo que tiene"


def teach(world: "SimulationWorld", doer: Resident, other: Resident) -> str | None:
    """The other is the better at their job for an hour of being shown."""
    job = world.registries.jobs.get(other.job_id or "")
    if job is None:
        return None
    world.crafts.worked(world, other, job, TEACHES_MINUTES)
    return f"{doer.name} le enseña a {other.name} cosas de su oficio"


def _strongest(world: "SimulationWorld", resident: Resident, feeling: str, but: Resident) -> tuple[str, float] | None:
    found = [
        (other_id, getattr(feelings, feeling))
        for (source_id, other_id), feelings in world.relationships.items()
        if source_id == resident.resident_id and other_id != but.resident_id and other_id in world.residents
    ]
    best = max(found, key=lambda each: (each[1], each[0]), default=None)
    return best if best is not None and best[1] > 0 else None


def calm(world: "SimulationWorld", doer: Resident, other: Resident) -> str | None:
    """The other thinks the better of whoever they cannot stand."""
    worst = _strongest(world, other, "resentment", doer)
    if worst is None:
        return None
    world.relationship(other.resident_id, worst[0]).adjust("resentment", -EASES)
    return f"{doer.name} pone paz entre {other.name} y {world.residents[worst[0]].name}"


def hearten(world: "SimulationWorld", doer: Resident, other: Resident) -> str | None:
    """The other is the less afraid of whoever frightens them."""
    worst = _strongest(world, other, "fear", doer)
    if worst is None:
        return None
    world.relationship(other.resident_id, worst[0]).adjust("fear", -EASES)
    return f"{doer.name} le quita a {other.name} el miedo a {world.residents[worst[0]].name}"


def stir(world: "SimulationWorld", doer: Resident, other: Resident) -> str | None:
    """The other is set against whoever the doer cannot stand."""
    worst = _strongest(world, doer, "resentment", other)
    if worst is None:
        return None
    world.relationship(other.resident_id, worst[0]).adjust("resentment", STIRS)
    return f"{doer.name} malmete a {other.name} contra {world.residents[worst[0]].name}"


def treat(world: "SimulationWorld", doer: Resident, other: Resident) -> str | None:
    """The doer gives the other something of their own that they carry: what the other would like best."""
    mine = world.items.owned(world, doer)
    if not mine:
        return None
    resolve = world.registries.items.resolve
    item = max(mine, key=lambda each: (world.tastes.fancy(world, other, resolve(each.definition_id)), each.instance_id))
    _hand(world, doer, other, item)
    item_definition = resolve(item.definition_id)
    return f"{doer.name} convida a {other.name}: {item_definition.article} {item_definition.name}"


def scrounge(world: "SimulationWorld", doer: Resident, other: Resident) -> str | None:
    """The doer has off the other something to eat or drink that they carry."""
    resolve = world.registries.items.resolve
    theirs = [item for item in world.items.owned(world, other) if resolve(item.definition_id).category in EDIBLE]
    if not theirs:
        return None
    item = max(theirs, key=lambda each: (world.tastes.fancy(world, doer, resolve(each.definition_id)), each.instance_id))
    _hand(world, other, doer, item)
    item_definition = resolve(item.definition_id)
    return f"{doer.name} le gorronea a {other.name} {item_definition.article} {item_definition.name}"


def _hand(world: "SimulationWorld", giver: Resident, receiver: Resident, item) -> None:
    """One unit of a thing goes from one pair of hands to another, and is the other's."""
    if item.quantity > 1:
        item.quantity -= 1
        world.stock(receiver.inventory, item.definition_id, 1, receiver.resident_id, item.level, item.freshness)
        return
    giver.inventory.remove(item.instance_id)
    item.owner_id, item.meant_for = receiver.resident_id, None
    receiver.inventory.add(item)


def mend(world: "SimulationWorld", doer: Resident, other: Resident) -> str | None:
    """The most worn thing the other carries is the better for being looked at."""
    worn = [item for item in world.items.owned(world, other) if item.condition < 100.0]
    if not worn:
        return None
    item = min(worn, key=lambda each: (each.condition, each.instance_id))
    item.condition = min(100.0, item.condition + MENDS)
    definition = world.registries.items.resolve(item.definition_id)
    return f"{doer.name} le arregla a {other.name} {definition.article} {definition.name}"


def give_back(world: "SimulationWorld", doer: Resident, other: Resident) -> str | None:
    """The other hands back what they have taken, to whoever is still there to have it."""
    returned = False
    for attempt in world.thefts:
        victim = world.residents.get(attempt.victim_id)
        if attempt.returned or attempt.thief_id != other.resident_id or victim is None:
            continue
        before = attempt.returned
        world.items._return_stolen(world, other, victim)
        returned = returned or attempt.returned != before
    return f"{doer.name} hace que {other.name} devuelva lo que no es suyo" if returned else None


def swindle(world: "SimulationWorld", doer: Resident, other: Resident) -> str | None:
    """The doer talks the other out of some of what they have."""
    taken = float(int(min(SWINDLED, other.credits)))
    if taken < 1:
        return None
    other.credits -= taken
    doer.credits += taken
    _said(
        world, doer, other, f"{doer.name} le saca {int(taken)} a {other.name} con un cuento", SWINDLE_IMPORTANCE,
        fact=f"{doer.name} timó a {other.name}",
    )
    return None


def bruise(world: "SimulationWorld", doer: Resident, other: Resident) -> str | None:
    """The other comes away the worse for it, and no more than that."""
    world.health.hurt(world, other, BRUISE, "bruise", f"un zarandeo de {doer.name}", by=doer)
    return None


def idle(world: "SimulationWorld", doer: Resident, other: Resident) -> str | None:
    """The other leaves what they were about and sits down to do nothing. It is theirs to
    do once they have heard the doer out."""
    activity = world.leisure.plan(world, other, IDLES)
    if activity is None:
        return None
    # Talked into it, their shift does not call them back: that is what it is for.
    activity.led = True
    other.activity = activity
    return f"{other.name} lo deja todo y se sienta, por {doer.name}"


# What each deed is called in the data, and whether it is the doer's to do, as they have had
# their say, or the other's, once they have heard them out.
DOERS: dict[str, Deed] = {
    "learn_news": learn_news,
    "learn_taste": learn_taste,
    "tend": tend,
    "teach": teach,
    "calm": calm,
    "hearten": hearten,
    "stir": stir,
    "treat": treat,
    "scrounge": scrounge,
    "mend": mend,
    "give_back": give_back,
    "swindle": swindle,
    "bruise": bruise,
}
OTHERS: dict[str, Deed] = {"idle": idle}
DEEDS = (*DOERS, *OTHERS)


class DeedSystem:
    def done(self, world: "SimulationWorld", doer: Resident, other: Resident, deeds: tuple[str, ...]) -> None:
        """The doer has had their say: what it does that is theirs to do is done."""
        self._run(world, doer, other, deeds, DOERS)

    def heard(self, world: "SimulationWorld", doer: Resident, other: Resident, deeds: tuple[str, ...]) -> None:
        """The other has heard the doer out: what it has them do is done."""
        self._run(world, doer, other, deeds, OTHERS)

    def _run(self, world: "SimulationWorld", doer: Resident, other: Resident, deeds: tuple[str, ...], known: dict[str, Deed]) -> None:
        if doer.resident_id not in world.residents or other.resident_id not in world.residents:
            return
        for name in deeds:
            deed = known.get(name)
            said = deed(world, doer, other) if deed is not None else None
            if said:
                _said(world, doer, other, said)
