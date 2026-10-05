"""Display text for simulation state. Nothing here feeds back into gameplay."""

from simulation.items.item import ItemInstance
from simulation.items.item_system import FOOD_CATEGORY, STEAL_ACTION, USE_ITEM_ACTION
from simulation.residents.activity import SHELTER_ACTION
from simulation.residents.resident import Resident
from simulation.work.expedition_system import EXPEDITION_ACTION
from simulation.work.job import JobDefinition
from simulation.events.world_event_system import BED_USE_ACTION
from simulation.work.work_system import HAUL_ACTION, WORK_ACTION
from simulation.world import SimulationWorld

NEED_LABELS = {"hunger": "Hambre", "tiredness": "Sueño", "social": "Social", "stress": "Estrés"}
FEELING_LABELS = {"affection": "afecto", "resentment": "rencor"}
MINUTES_PER_DAY = 24 * 60


def format_time(timestamp: int, with_day: bool = False) -> str:
    """Format game minutes since day 1, 00:00."""
    day, minute = divmod(timestamp, MINUTES_PER_DAY)
    clock = f"{minute // 60:02d}:{minute % 60:02d}"
    return f"D{day + 1} {clock}" if with_day else clock


def describe_job(world: SimulationWorld, resident: Resident) -> str:
    """A resident's post and shifts, such as `Trabajo: Cocina (11-14, 18-21)`."""
    job = world.work.job_of(world, resident)
    if job is None:
        return "Sin trabajo"
    if world.work.is_day_off(world, resident):
        return f"Trabajo: {job.name} (hoy libra)"
    return f"Trabajo: {job.name} ({describe_shifts(job)})"


def describe_shifts(job: JobDefinition) -> str:
    """A job's hours, such as `11-14, 18-21`."""
    return ", ".join(f"{start}-{end}" for start, end in job.shifts)


def describe_holders(world: SimulationWorld, job_id: str) -> str:
    """Who does a job, such as `Raúl, Inés (libra)`, or `nadie`."""
    names = [
        f"{resident.name} (libra)" if world.work.is_day_off(world, resident) else resident.name
        for resident in world.staffing.workers(world, job_id)
    ]
    return ", ".join(names) if names else "nadie"


def describe_vacancy(world: SimulationWorld, job_id: str) -> str | None:
    """How long a job has been short of people, such as `vacante hace 30 h`. None if it is not."""
    job = world.registries.jobs.get(job_id)
    if job is None or not world.staffing.is_short(world, job):
        return None
    since = world.vacancies.get(job_id)
    hours = (world.clock.total_minutes - since) // 60 if since is not None else 0
    return f"vacante hace {hours} h" if hours >= 1 else "vacante"


def condition_of(world: SimulationWorld, item: ItemInstance) -> float | None:
    """The state of a thing that wears out, from 100 down to 0. None for things that never do."""
    wears = world.registries.items.resolve(item.definition_id).properties.get("wear", 0.0) > 0
    return max(0.0, item.condition) if wears else None


def selling_use(world: SimulationWorld, container_id: str):
    """The use of a container that is buying from it, if it is a shop counter."""
    placed = world.interactables.get(container_id)
    use = world.definition_of(placed).use if placed is not None else None
    return use if use is not None and use.sells else None


def price_at(world: SimulationWorld, container_id: str, item: ItemInstance) -> int:
    """What one unit of something on a counter costs right now."""
    definition = world.registries.items.resolve(item.definition_id)
    return world.trade.price_of(world, definition, world.containers[container_id].count(item.definition_id))


def shop_goods(world: SimulationWorld) -> list[tuple[str, int]]:
    """Everything on sale in the settlement as item definition ID and price, cheapest first."""
    goods: dict[str, int] = {}
    for container_id, inventory in world.containers.items():
        if selling_use(world, container_id) is None:
            continue
        for item in inventory.items:
            if item.owner_id is None and not item.broken:
                price = price_at(world, container_id, item)
                goods[item.definition_id] = min(price, goods.get(item.definition_id, price))
    return sorted(goods.items(), key=lambda entry: (entry[1], entry[0]))


def has_shop(world: SimulationWorld) -> bool:
    return any(selling_use(world, container_id) is not None for container_id in world.containers)


def affordable_goods(world: SimulationWorld, resident: Resident) -> list[str]:
    """Item definition IDs of what a resident has credits enough to buy, cheapest first."""
    return [definition_id for definition_id, price in shop_goods(world) if price <= resident.credits]


def describe_bond(world: SimulationWorld, resident: Resident, other: Resident) -> str:
    """What `other` is to `resident`, in a word after their name: their partner, a friend, or nothing."""
    if resident.couple_with == other.resident_id:
        return " (pareja)"
    feelings = world.relationships.get((resident.resident_id, other.resident_id))
    tier = world.bonds.tier(world, feelings) if feelings is not None else None
    return f" ({tier.name})" if tier is not None else ""


def describe_weather(world: SimulationWorld) -> str | None:
    """The weather the settlement is under, such as `Tormenta de polvo`. None when there is nothing to say."""
    weather = world.happenings.weather_now(world)
    return weather.name.capitalize() if weather is not None else None


OBSTACLE_LABELS = {
    "own_job": "ya es su puesto",
    "no_post": "sin puesto libre",
    "deciding": "tiene algo que decidir",
    "asked_recently": "se lo preguntaron hace poco",
}


def describe_obstacle(code: str | None) -> str:
    """Why a job cannot be put to someone right now, in a few words. Nothing if it can."""
    return OBSTACLE_LABELS.get(code or "", "no se le puede proponer" if code else "")


def known_forecasts(world: SimulationWorld) -> list[str]:
    """What is on its way that at least one resident knows of, soonest first, one line each.

    It shows what the settlement knows, not what is true: a storm nobody has heard of is not listed.
    """
    lines = []
    for upcoming in sorted(world.upcoming, key=lambda each: each.at):
        definition = world.registries.world_events.events.get(upcoming.event_id)
        if definition is None or upcoming.fact_id is None:
            continue
        knowers = sum(world.knowledge.knows(resident_id, upcoming.fact_id) for resident_id in world.residents)
        if knowers:
            heard = "lo sabe 1" if knowers == 1 else f"lo saben {knowers}"
            lines.append(f"A las {upcoming.at // 60 % 24}: {definition.forecast} ({heard})")
    return lines


def away_residents(world: SimulationWorld) -> list[Resident]:
    """Whoever is outside the settlement right now."""
    return [resident for resident in world.residents.values() if resident.away]


def describe_credits(resident: Resident) -> str:
    """What a resident has earned and not spent, in whole credits, such as `12 vales`."""
    whole = int(resident.credits)
    return "1 vale" if whole == 1 else f"{whole} vales"


def describe_injuries(world: SimulationWorld, resident: Resident) -> str:
    """What ails a resident, worst first, such as `Heridas: un corte, moratones`."""
    names: list[str] = []
    for injury in sorted(resident.injuries, key=lambda injury: -injury.severity):
        definition = world.registries.injuries.get(injury.kind)
        name = definition.name if definition is not None else "heridas"
        if name not in names:
            names.append(name)
    for limb_id in resident.lost_limbs:
        limb = world.registries.limbs.get(limb_id)
        if limb is not None:
            names.append(f"sin {limb.name}")
    return "Heridas: " + ", ".join(names) if names else "Sin heridas"


def describe_action(world: SimulationWorld, resident: Resident) -> str:
    """One short phrase for what a resident is doing right now."""
    activity = resident.activity
    if activity is None:
        return "sin hacer nada"
    partner = world.residents.get(activity.partner_id) if activity.partner_id else None
    if partner is not None:
        if not activity.using:
            return f"va a hablar con {partner.name}"
        interaction = world.registries.interactions.get(activity.action)
        if interaction is not None and interaction.romance == "tryst":
            return f"a solas con {partner.name}"
        verb = "discute" if interaction is not None and interaction.hostile else "charla"
        return f"{verb} con {partner.name}"
    if activity.action == WORK_ACTION:
        job = world.work.job_of(world, resident)
        post = job.name.lower() if job is not None else "su puesto"
        return f"trabajando: {post}" if activity.using else f"va a trabajar: {post}"
    if activity.action == EXPEDITION_ACTION:
        return "fuera del asentamiento"
    if activity.action == HAUL_ACTION:
        return "carga y descarga" if activity.using else "acarrea para su puesto"
    if activity.action == STEAL_ACTION:
        return "se lleva algo que no es suyo" if activity.using else "trama algo"
    if activity.action == USE_ITEM_ACTION:
        item = world.items.find_item(world, activity.item_id or "")
        if item is None:
            return "busca algo"
        definition = world.registries.items.resolve(item.definition_id)
        verb = "come" if definition.category == FOOD_CATEGORY else "pasa un rato con"
        return f"{verb} {definition.article} {definition.name}"
    placed = world.interactables.get(activity.target_id) if activity.target_id else None
    if activity.action == SHELTER_ACTION:
        return "se resguarda del mal tiempo" if not activity.path else "corre a resguardarse"
    if placed is None:
        if any(decision.resident_id == resident.resident_id for decision in world.decisions.values()):
            return "le da vueltas a algo"
        return "pasea" if activity.path else "sin hacer nada"
    definition = world.definition_of(placed)
    if not activity.using or definition.use is None:
        return f"va hacia {definition.article} {definition.name}"
    text = definition.use.text
    item_id = activity.item_id or definition.use.item_id
    if item_id is not None:
        item = world.items.definition_for(world, item_id)
        text = text.replace("{item}", f"{item.article} {item.name}")
    return text


# What one resident is to another when nothing closer can be said of it, by how they get on.
ON_BAD_TERMS = (-25, "Se llevan mal")
ON_GOOD_TERMS = (10, "Se llevan bien")
ACQUAINTANCE = "Conocido"
PARTNER = "Pareja"
# Stress from which a face looks angry, and health or need from which it looks down.
ANGRY_STRESS = 70.0
LOW_HEALTH = 70.0
PRESSING_NEED = 85.0
SCRAP_TAG = "scrap"


def trait_names(world: SimulationWorld, resident: Resident) -> list[str]:
    """The traits of a resident as they are shown. One without a name of its own shows its ID."""
    names = []
    for trait_id in resident.traits:
        definition = world.registries.traits.find(trait_id)
        names.append(str(definition.get("name", trait_id)) if definition is not None else trait_id)
    return names


def relationship_rows(world: SimulationWorld, resident: Resident, limit: int) -> list[tuple[Resident, int, str, str | None]]:
    """Who matters most to a resident: each with a score, a word for what they are, and an icon.

    The score is the affection they feel less the resentment. Their partner comes first, then
    whoever they feel most strongly about, for good or ill.
    """
    rows = []
    for other in world.residents.values():
        if other is resident:
            continue
        feelings = world.relationships.get((resident.resident_id, other.resident_id))
        score = round(feelings.affection - feelings.resentment) if feelings is not None else 0
        tier = world.bonds.tier(world, feelings) if feelings is not None else None
        if resident.couple_with == other.resident_id:
            label, icon = PARTNER, "heart"
        elif tier is not None:
            label, icon = tier.name.capitalize(), "friend"
        elif score <= ON_BAD_TERMS[0]:
            label, icon = ON_BAD_TERMS[1], "argument"
        elif score >= ON_GOOD_TERMS[0]:
            label, icon = ON_GOOD_TERMS[1], None
        else:
            label, icon = ACQUAINTANCE, None
        rows.append((other, score, label, icon))
    rows.sort(key=lambda row: (row[0].resident_id != resident.couple_with, -abs(row[1]), row[0].resident_id))
    return rows[:limit]


def expression_of(world: SimulationWorld, resident: Resident) -> str:
    """The face a resident wears as things stand with them."""
    activity = resident.activity
    if activity is not None and activity.using and activity.partner_id is not None:
        interaction = world.registries.interactions.get(activity.action)
        if interaction is not None:
            return "angry" if interaction.hostile else "happy"
    if resident.needs.stress >= ANGRY_STRESS:
        return "angry"
    needs = (resident.needs.hunger, resident.needs.tiredness, resident.needs.social)
    return "sad" if resident.health < LOW_HEALTH or max(needs) >= PRESSING_NEED else "neutral"


def spoken_line(world: SimulationWorld, resident: Resident) -> str | None:
    """Something a resident in an exchange might be saying right now, from the lines written for it."""
    activity = resident.activity
    if activity is None or not activity.using or activity.partner_id is None:
        return None
    interaction = world.registries.interactions.get(activity.action)
    lines = world.registries.dialogue.get(interaction.dialogue or "", []) if interaction is not None else []
    # A new line every few minutes, and the same one for as long as it is on show.
    return lines[(world.clock.total_minutes // 4) % len(lines)] if lines else None


def settlement_counts(world: SimulationWorld) -> list[tuple[str, str]]:
    """What the settlement has, as an icon and a figure each: people and beds, food, and scrap."""
    beds = sum(
        1
        for placed in world.interactables.values()
        if (use := world.definition_of(placed).use) is not None and use.action == BED_USE_ACTION
    )
    food = scrap = 0
    for definition_id, quantity in settlement_stock(world):
        definition = world.registries.items.resolve(definition_id)
        food += quantity if definition.category == FOOD_CATEGORY else 0
        scrap += quantity if SCRAP_TAG in definition.tags else 0
    return [("people", f"{len(world.residents)}/{beds}"), ("food", str(food)), ("scrap", str(scrap))]


def settlement_stock(world: SimulationWorld) -> list[tuple[str, int]]:
    """Everything in the settlement's containers that is nobody's own, as item ID and how many, by name."""
    totals: dict[str, int] = {}
    for inventory in world.containers.values():
        for item in inventory.items:
            if item.owner_id is None:
                totals[item.definition_id] = totals.get(item.definition_id, 0) + item.quantity
    return sorted(totals.items(), key=lambda entry: world.registries.items.resolve(entry[0]).name)
