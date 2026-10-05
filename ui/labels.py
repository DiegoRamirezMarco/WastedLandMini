"""Display text for simulation state. Nothing here feeds back into gameplay."""

from simulation.items.item import ItemInstance
from simulation.items.item_system import FOOD_CATEGORY, STEAL_ACTION, USE_ITEM_ACTION
from simulation.residents.activity import SHELTER_ACTION
from simulation.residents.resident import Resident
from simulation.work.expedition_system import EXPEDITION_ACTION
from simulation.work.job import JobDefinition
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
