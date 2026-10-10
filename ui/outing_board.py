"""The board of trips (P70): how far whoever goes out is sent, and what is handed to them to
get there.

The country out there lies in a line. What is handed over fills the way like a bar: as far
as it reaches is as far as they go. It reads the simulation and changes nothing: what is
pressed is an intent for the scene.
"""

from dataclasses import dataclass, field

import pygame

from graphics.font import LINE_HEIGHT, BitmapFont
from graphics.palette import PALETTE
from graphics.ui_art import band_hue
from simulation.residents.resident import Resident
from simulation.world import SimulationWorld
from ui.button import HEIGHT as BUTTON_HEIGHT
from ui.button import Button
from ui.panel import draw_panel

PANEL_WIDTH = 380
PADDING = 5
ROW_HEIGHT = BUTTON_HEIGHT + 2
BAR_HEIGHT = 9
TRIPS_INTENT = ("trips",)
PLAN_INTENT = ("trip_plan",)
CANCEL_INTENT = ("trip_cancel",)
DRAW_INTENT = ("trip_draw",)
TITLE = "Viajes: hasta dónde va quien sale fuera"
NOBODY = "Nadie tiene un oficio de salir fuera."
AWAY = "{name} está fuera: se prepara cuando vuelva."
READY = "Listo: irá hasta {zone} la próxima vez que salga."
UNKNOWN = "???"
PLAN_LABEL, CANCEL_LABEL, DRAW_LABEL = "Preparar viaje", "Deshacer", "Nombre y dibujo"
NOTHING_TO_TAKE = "No hay comida ni agua que sea de todos."
FOOTER = "Si se da la vuelta antes de llegar, trae de vuelta lo que no gastó."


@dataclass
class OutingEntry:
    """What is being made ready on the board: for whom, how far, and what is handed over."""

    resident_id: str = ""
    zone_id: str = ""
    supplies: dict[str, int] = field(default_factory=dict)


def who_intent(step: int) -> tuple[str, int]:
    return ("trip_who", step)


def zone_intent(zone_id: str) -> tuple[str, str]:
    return ("trip_zone", zone_id)


def more_intent(item_id: str, step: int) -> tuple[str, str, int]:
    return ("trip_more", item_id, step)


def travellers(world: SimulationWorld) -> list[Resident]:
    """Whoever has a job done out there, in the order the settlement has them."""
    return [resident for resident in world.residents.values() if world.expeditions.goes_out(world, resident) is not None]


def traveller(world: SimulationWorld, entry: OutingEntry) -> Resident | None:
    """Whoever the board is on: the one it says if they still go out, or else the first who does."""
    going = travellers(world)
    return next((resident for resident in going if resident.resident_id == entry.resident_id), going[0] if going else None)


def provisions(world: SimulationWorld, entry: OutingEntry) -> list[tuple[str, int]]:
    """What there is to hand over, and how many of each there are: what is everybody's, with
    what was already handed over for a trip made ready."""
    there = dict(world.expeditions.on_hand(world))
    resident = traveller(world, entry)
    if resident is not None and resident.outing is not None:
        for item_id, units in resident.outing.supplies.items():
            there[item_id] = there.get(item_id, 0) + units
    return sorted(there.items(), key=lambda pair: world.registries.items.resolve(pair[0]).name)


def filled(world: SimulationWorld, entry: OutingEntry, zone_id: str) -> dict[str, int]:
    """What to hand over to get as far as a zone and no further, out of what there is: as
    much of one thing as of another, a unit at a time."""
    zone = world.registries.expeditions.zone(zone_id)
    needed = world.expeditions.needs(world, zone) if zone is not None else 0.0
    there = dict(provisions(world, entry))
    supplies: dict[str, int] = {}
    while world.expeditions.worth_of(world, supplies) < needed:
        # Only of what gets anybody any further: what is taken along to mend with is for the player to hand over.
        left = [
            item_id for item_id, units in there.items()
            if supplies.get(item_id, 0) < units and world.expeditions.worth(world, item_id) > 0
        ]
        if not left:
            break
        item_id = min(left, key=lambda each: (supplies.get(each, 0), -there[each], each))
        supplies[item_id] = supplies.get(item_id, 0) + 1
    return supplies


def trip_hours(world: SimulationWorld, resident: Resident, zone_id: str) -> float:
    """About how many hours a trip as far as a zone takes."""
    job = world.expeditions.goes_out(world, resident)
    zone = world.registries.expeditions.zone(zone_id)
    if job is None or zone is None:
        return 0.0
    line = world.registries.expeditions.line
    extra = sum(crossed.minutes for crossed in world.expeditions.route_to(world, zone) if not line or crossed is not line[0])
    return (sum(job.expedition.minutes) / 2 + extra) / 60.0


def _zones(world: SimulationWorld) -> list:
    return list(world.registries.expeditions.line)


def outing_board_height(world: SimulationWorld, entry: OutingEntry) -> int:
    rows = len(_zones(world)) + max(1, len(provisions(world, entry)))
    return PADDING * 2 + LINE_HEIGHT * 5 + BAR_HEIGHT + 14 + ROW_HEIGHT * (rows + 2)


def _tops(rect: pygame.Rect, world: SimulationWorld) -> tuple[int, int, int, int]:
    """Where the name of whoever goes, the list of zones, the bar and the provisions begin."""
    who = rect.y + PADDING + LINE_HEIGHT + 3
    zones = who + ROW_HEIGHT + LINE_HEIGHT + 2
    bar = zones + ROW_HEIGHT * len(_zones(world)) + 3
    return who, zones, bar, bar + BAR_HEIGHT + LINE_HEIGHT + 6


def outing_buttons(font: BitmapFont, rect: pygame.Rect, world: SimulationWorld, entry: OutingEntry) -> list[Button]:
    """Everything that can be pressed on the board as things stand."""
    resident = traveller(world, entry)
    if resident is None:
        return []
    who, zones_top, _, items_top = _tops(rect, world)
    buttons: list[Button] = []
    if len(travellers(world)) > 1:
        back = Button.at(font, rect.x + PADDING, who, "<", who_intent(-1))
        buttons += [back, Button.at(font, back.rect.right + 2, who, ">", who_intent(1))]
    if resident.away:
        return buttons
    reach = {zone.zone_id for zone in world.expeditions.reach(world, resident)}
    y = zones_top
    for zone in _zones(world):
        if zone.zone_id in reach:
            go = Button.at(font, 0, y, "Hasta aquí", zone_intent(zone.zone_id))
            go.rect.right = rect.right - PADDING
            buttons.append(go)
        y += ROW_HEIGHT
    y = items_top
    for item_id, _ in provisions(world, entry):
        more = Button.at(font, 0, y, "+", more_intent(item_id, 1))
        more.rect.right = rect.right - PADDING
        less = Button.at(font, 0, y, "-", more_intent(item_id, -1))
        less.rect.right = more.rect.left - 26
        buttons += [less, more]
        y += ROW_HEIGHT
    y = rect.bottom - PADDING - LINE_HEIGHT - ROW_HEIGHT - 1
    plan = Button.at(font, rect.x + PADDING, y, PLAN_LABEL, PLAN_INTENT)
    buttons.append(plan)
    last = plan
    if resident.outing is not None:
        last = Button.at(font, plan.rect.right + 3, y, CANCEL_LABEL, CANCEL_INTENT)
        buttons.append(last)
    if entry.zone_id:
        buttons.append(Button.at(font, last.rect.right + 3, y, DRAW_LABEL, DRAW_INTENT))
    return [button for button in buttons if button.rect.bottom <= rect.bottom]


def bar_marks(rect: pygame.Rect, world: SimulationWorld) -> tuple[pygame.Rect, list[int]]:
    """Where the bar of the way is on the board, and where along it each zone is reached."""
    _, _, top, _ = _tops(rect, world)
    bar = pygame.Rect(rect.x + PADDING, top, rect.width - PADDING * 2, BAR_HEIGHT)
    zones = _zones(world)
    most = max((world.expeditions.needs(world, zone) for zone in zones), default=0.0)
    marks = [
        bar.x + (round(world.expeditions.needs(world, zone) / most * (bar.width - 1)) if most > 0 else 0)
        for zone in zones
    ]
    return bar, marks


def draw_outing_board(
    target: pygame.Surface, font: BitmapFont, rect: pygame.Rect, world: SimulationWorld, entry: OutingEntry
) -> None:
    draw_panel(target, rect, band=PADDING + LINE_HEIGHT, band_color=band_hue("trips"))
    x, y = rect.x + PADDING, rect.y + PADDING
    width = rect.width - PADDING * 2
    font.draw(target, font.truncate(TITLE, width), (x, y), PALETTE["paper"])
    resident = traveller(world, entry)
    who, zones_top, _, items_top = _tops(rect, world)
    if resident is None:
        font.draw(target, NOBODY, (x, who + 2), PALETTE["stone"])
        return
    trips = world.expeditions
    buttons = outing_buttons(font, rect, world, entry)
    for button in buttons:
        button.draw(target, font, active=button.intent == zone_intent(entry.zone_id))
    job = trips.goes_out(world, resident)
    level = world.crafts.level(world, resident, job.job_id)
    left = x + (28 if len(travellers(world)) > 1 else 0)
    font.draw(target, f"{resident.name} · {job.name.lower()}, nivel {level}", (left, who + 2), PALETTE["glow"])
    y = who + ROW_HEIGHT
    if resident.away:
        font.draw(target, font.truncate(AWAY.format(name=resident.name), width), (x, y), PALETTE["dust"])
    elif resident.outing is not None:
        zone = world.registries.expeditions.zone(resident.outing.zone)
        name = trips.name_of(world, zone) if zone is not None else UNKNOWN
        font.draw(target, font.truncate(READY.format(zone=name), width), (x, y), PALETTE["lichen"])
    else:
        font.draw(target, "Sin viaje preparado: sale por su cuenta, a lo más cercano.", (x, y), PALETTE["dust"])
    # The line of zones, the nearest first: what each takes, and who lies in wait there.
    reach = {zone.zone_id for zone in trips.reach(world, resident)}
    worth = trips.worth_of(world, entry.supplies)
    y = zones_top
    for index, zone in enumerate(_zones(world)):
        known = trips.is_found(world, zone)
        within = zone.zone_id in reach
        gets = within and trips.needs(world, zone) <= worth
        name = trips.name_of(world, zone).capitalize() if known else UNKNOWN
        color = "glow" if zone.zone_id == entry.zone_id else "paper" if gets else "bone" if within else "stone"
        font.draw(target, f"{index + 1}. {font.truncate(name, 130)}", (x, y + 2), PALETTE[color])
        if known:
            low, high = zone.raiders
            said = f"pide {trips.needs(world, zone):g} · enemigos nv {low}" + (f"-{high}" if high > low else "")
            if not within:
                said += " · no sabe llegar"
            font.draw(target, said, (x + 150, y + 2), PALETTE["dust" if within else "stone"])
        y += ROW_HEIGHT
    # The way as a bar: what is handed over fills it, and each zone is a mark along it.
    bar, marks = bar_marks(rect, world)
    pygame.draw.rect(target, PALETTE["shadow"], bar)
    most = max((trips.needs(world, zone) for zone in _zones(world)), default=0.0)
    if most > 0 and worth > 0:
        pygame.draw.rect(target, PALETTE["lamp"], (bar.x, bar.y, round(min(1.0, worth / most) * bar.width), bar.height))
    pygame.draw.rect(target, PALETTE["iron"], bar, 1)
    for zone, mark in zip(_zones(world), marks):
        pygame.draw.rect(target, PALETTE["paper" if zone.zone_id in reach else "stone"], (mark, bar.y - 2, 1, bar.height + 4))
    gets_to = trips.gets_to(world, resident, entry.supplies)
    said = "Con eso no sale de lo más cercano"
    if gets_to is not None:
        hours = trip_hours(world, resident, gets_to.zone_id)
        said = f"Con esto llega hasta {trips.name_of(world, gets_to)} · unas {hours:.0f} h"
    font.draw(target, font.truncate(said, width), (x, bar.bottom + 3), PALETTE["paper"])
    y = items_top
    there = provisions(world, entry)
    if not there:
        font.draw(target, NOTHING_TO_TAKE, (x, y + 2), PALETTE["stone"])
    for item_id, units in there:
        definition = world.registries.items.resolve(item_id)
        taken = entry.supplies.get(item_id, 0)
        font.draw(target, font.truncate(f"{definition.name.capitalize()} (hay {units})", width - 80), (x, y + 2), PALETTE["bone"])
        count = str(taken)
        font.draw(target, count, (rect.right - PADDING - 24 - font.width(count) // 2, y + 2), PALETTE["glow" if taken else "stone"])
        y += ROW_HEIGHT
    font.draw(target, font.truncate(FOOTER, width), (x, rect.bottom - PADDING - LINE_HEIGHT + 1), PALETTE["dust"])
