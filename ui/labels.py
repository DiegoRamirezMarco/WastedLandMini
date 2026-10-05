"""Display text for simulation state. Nothing here feeds back into gameplay."""

from simulation.items.item_system import FOOD_CATEGORY, STEAL_ACTION, USE_ITEM_ACTION
from simulation.residents.resident import Resident
from simulation.work.work_system import WORK_ACTION
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
    shifts = ", ".join(f"{start}-{end}" for start, end in job.shifts)
    return f"Trabajo: {job.name} ({shifts})"


def describe_injuries(world: SimulationWorld, resident: Resident) -> str:
    """What ails a resident, worst first, such as `Heridas: un corte, moratones`."""
    names: list[str] = []
    for injury in sorted(resident.injuries, key=lambda injury: -injury.severity):
        definition = world.registries.injuries.get(injury.kind)
        name = definition.name if definition is not None else "heridas"
        if name not in names:
            names.append(name)
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
        verb = "discute" if interaction is not None and interaction.hostile else "charla"
        return f"{verb} con {partner.name}"
    if activity.action == WORK_ACTION:
        job = world.work.job_of(world, resident)
        post = job.name.lower() if job is not None else "su puesto"
        return f"trabajando: {post}" if activity.using else f"va a trabajar: {post}"
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
        item = world.registries.items.resolve(item_id)
        text = text.replace("{item}", f"{item.article} {item.name}")
    return text
