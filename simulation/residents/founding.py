"""How a settlement gets its first resident: made by the player, where every other one walks in."""

import re
import unicodedata
from collections.abc import Mapping, Sequence
from typing import TYPE_CHECKING

from simulation.events.event import DomainEvent
from simulation.residents.personality import Personality
from simulation.residents.resident import Resident

if TYPE_CHECKING:
    from simulation.world import SimulationWorld

NAME_LENGTH = 16
# Residents are adults: nothing in the settlement is written for anyone younger.
AGE_RANGE = (18, 80)
MAX_TRAITS = 2
FOUNDED_EVENT = "resident_founded"
FOUNDED_IMPORTANCE = 45
FALLBACK_ID = "resident"


def tidy_name(name: str) -> str:
    """A name as the settlement keeps it: no stray spaces, and short enough to show."""
    return " ".join(name.split())[:NAME_LENGTH].strip()


def resident_id_for(world: "SimulationWorld", name: str) -> str:
    """A stable ID made from a name: plain lower-case letters, numbered where it is taken.

    Whoever might still walk in from outside keeps their own, and so do the dead.
    """
    plain = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-z0-9]+", "_", plain.lower()).strip("_") or FALLBACK_ID
    taken = {
        *world.residents,
        *(death.resident_id for death in world.deaths),
        *(newcomer.newcomer_id for newcomer in world.registries.world_events.newcomers),
    }
    candidate, number = slug, 2
    while candidate in taken:
        candidate, number = f"{slug}_{number}", number + 1
    return candidate


def found_resident(
    world: "SimulationWorld",
    name: str,
    age: int,
    personality: Mapping[str, float],
    traits: Sequence[str],
    manners: Mapping[str, str] | None = None,
) -> Resident | None:
    """Put the player's first resident just inside the gate.

    Only a settlement nobody has ever lived in takes one: after that, people come by the gate
    and are let in or not by whoever lives there. Returns None if it was refused.
    """
    name = tidy_name(name)
    if not name or world.residents or world.deaths:
        return None
    known = vars(Personality())
    youngest, oldest = AGE_RANGE
    x, y = world.happenings.arrival_tile(world)
    resident = Resident(
        resident_id_for(world, name),
        name,
        x=x,
        y=y,
        personality=Personality(
            **{trait: min(100.0, max(0.0, float(value))) for trait, value in personality.items() if trait in known}
        ),
        # Traits the game does not define are dropped, like any other content that has gone.
        traits=[trait for trait in dict.fromkeys(traits) if world.registries.traits.find(trait) is not None][
            :MAX_TRAITS
        ],
        # A manner the game does not define is dropped the same way: they go by their own.
        manners=world.registries.manners.tidy(manners or {}),
        age=min(max(int(age), youngest), oldest),
        credits=world.registries.economy.starting_credits,
    )
    world.residents[resident.resident_id] = resident
    room = world.room_at(resident.tile)
    world.emit_event(
        DomainEvent(
            FOUNDED_EVENT,
            FOUNDED_IMPORTANCE,
            f"{name} cruza la puerta y se queda: aquí empieza un asentamiento",
            [resident.resident_id],
            location_id=room.room_id if room is not None else None,
        ),
        at=resident.tile,
    )
    return resident
