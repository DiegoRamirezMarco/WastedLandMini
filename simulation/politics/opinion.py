"""What a resident makes of a matter of politics, worked out from who they are.

A law, a proposal or a whim says in its data what weighs for or against it: a leaning, a side
of a way of being, something held about the government, or a stake the resident has in it.
Everything here is read off the resident. Nothing is rolled.
"""

from collections.abc import Mapping
from typing import TYPE_CHECKING

from simulation.politics.government import LEANINGS
from simulation.residents.personality import Personality
from simulation.residents.resident import Resident
from simulation.tastes.taste import TAG

if TYPE_CHECKING:
    from simulation.world import SimulationWorld

SIDES = tuple(vars(Personality()))
# What is held about whoever leads and about the government. `dread` is the fear of it.
HELD = ("loyalty", "trust", "resentment", "dread")
# What a resident may stand to gain or lose, each from 0 to 1 unless it says otherwise:
# having a job or none, what they have put by, being short, what they own in things, drinking
# and other habits, how hungry, tired and worn they are, keeping watch, carrying a child,
# holding a seat, leading, having a partner, how short the settlement is of food, how much
# they like the item a matter names (from -1 to 1) and how much more the kind of government it
# names appeals to them than the one there is.
STAKES = (
    "works", "idle", "savings", "poor", "goods", "drinks", "uses", "hungry", "tired", "stressed",
    "guards", "expecting", "governs", "leads", "partnered", "shortage", "item", "appeal",
)
# A key that starts with this is how much they like whatever carries a taste tag, from -1 to 1.
TASTE = "taste:"
DRINK_TAG = "alcohol"
VICE_TAG = "vice"
# Uses of something after which it is as much a habit as it gets, for what is made of a law about it.
HABIT_USES = 5.0


def known(key: str) -> bool:
    """Whether a key is something a matter's data may weigh."""
    return key in LEANINGS or key in SIDES or key in HELD or key in STAKES or key.startswith(TASTE)


def check(weights: Mapping[str, float], where: str) -> None:
    unknown = sorted(key for key in weights if not known(key))
    if unknown:
        raise ValueError(f"{where} weighs what no resident has: {unknown}")


def _habit(world: "SimulationWorld", resident: Resident, tag: str) -> float:
    most = 0.0
    for item_id, habit in resident.habits.items():
        definition = world.registries.items.find(item_id)
        if definition is None or tag not in definition.tags:
            continue
        most = max(most, 1.0 if habit.dependent else min(1.0, habit.uses / HABIT_USES))
    return most


def common_stock(world: "SimulationWorld", category: str, but: str | None = None) -> int:
    """Units of a category of thing that are nobody's, wherever they are kept. `but` leaves one kind of item out."""
    resolve = world.registries.items.resolve
    return sum(
        item.quantity
        for inventory in world.containers.values()
        for item in inventory.items
        if item.owner_id is None and item.definition_id != but and resolve(item.definition_id).category == category
    )


def shortage(world: "SimulationWorld") -> float:
    """How short the settlement is of what it eats out of the commons: 0 with plenty for
    everybody, 1 with nothing at all."""
    plenty = world.registries.laws.plenty_per_resident * max(1, len(world.residents))
    if plenty <= 0:
        return 0.0
    stock = sum(common_stock(world, category) for category in world.registries.economy.kept_categories)
    return max(0.0, 1.0 - stock / plenty)


def appeal_of(world: "SimulationWorld", resident: Resident, government_id: str | None) -> float:
    """How much a kind of government appeals to a resident, by what they hold and nothing else."""
    definition = world.registries.politics.governments.get(government_id or "")
    if definition is None:
        return 0.0
    profile = world.politics.legitimacy.profile(world, resident)
    return sum(weight * (getattr(profile, leaning) - 50.0) / 50.0 for leaning, weight in definition.appeal.items())


def value_of(world: "SimulationWorld", resident: Resident, key: str, params: Mapping[str, str] | None = None) -> float:
    """What one key comes to for a resident: from -1 to 1 for what has a middle, from 0 to 1 otherwise."""
    params = params or {}
    if key in LEANINGS:
        return (getattr(world.politics.legitimacy.profile(world, resident), key) - 50.0) / 50.0
    if key in SIDES:
        return (getattr(resident.personality, key) - 50.0) / 50.0
    if key in HELD:
        profile = world.politics.legitimacy.profile(world, resident)
        if key == "dread":
            return profile.fear / 100.0
        if key == "resentment":
            return profile.resentment / 100.0
        return (getattr(profile, key) - 50.0) / 50.0
    if key.startswith(TASTE):
        taste = world.tastes.profile(world, resident).find(TAG, key.removeprefix(TASTE))
        return taste.value / 100.0 if taste is not None else 0.0
    economy = world.registries.economy
    coin = world.fund.currency(world) is not None
    has_job = resident.job_id in world.registries.jobs
    if key == "works":
        return 1.0 if has_job else 0.0
    if key == "idle":
        return 0.0 if has_job else 1.0
    if key == "savings":
        return min(1.0, max(0.0, resident.credits) / economy.savings_scale) if coin and economy.savings_scale else 0.0
    if key == "poor":
        return 1.0 if coin and resident.credits < economy.poor_below else 0.0
    if key == "goods":
        return world.terms.decision_inputs(world, resident)["goods"]
    if key == "drinks":
        return _habit(world, resident, DRINK_TAG)
    if key == "uses":
        return _habit(world, resident, VICE_TAG)
    if key == "hungry":
        return resident.needs.hunger / 100.0
    if key == "tired":
        return resident.needs.tiredness / 100.0
    if key == "stressed":
        return resident.needs.stress / 100.0
    if key == "guards":
        job = world.registries.jobs.get(resident.job_id or "")
        return 1.0 if job is not None and job.watch_for is not None else 0.0
    if key == "expecting":
        return 1.0 if resident.expecting_with is not None else 0.0
    if key == "governs":
        return 1.0 if world.politics.leadership.holds_office(world, resident.resident_id) else 0.0
    if key == "leads":
        return 1.0 if world.government.leader == resident.resident_id else 0.0
    if key == "partnered":
        return 1.0 if resident.couple_with is not None else 0.0
    if key == "shortage":
        return shortage(world)
    if key == "item":
        definition = world.registries.items.find(params.get("item", ""))
        return max(-1.0, min(1.0, world.tastes.liking(world, resident, definition) / 100.0)) if definition else 0.0
    if key == "appeal":
        return appeal_of(world, resident, params.get("government")) - appeal_of(world, resident, world.government.kind)
    return 0.0


def weigh(
    world: "SimulationWorld",
    resident: Resident,
    weights: Mapping[str, float],
    params: Mapping[str, str] | None = None,
    weight: float = 1.0,
) -> float:
    """What a set of weights comes to for a resident.

    `weight` says how far the matter goes, 1 for as written: what counts against it counts that
    many times over, and what counts for it half way between as written and that.
    """
    total = 0.0
    for key, each in weights.items():
        part = each * value_of(world, resident, key, params)
        total += part * (weight if part < 0 else 0.5 + 0.5 * weight)
    return total
