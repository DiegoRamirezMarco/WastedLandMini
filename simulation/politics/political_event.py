from dataclasses import dataclass

from simulation.events.event import DomainEvent


@dataclass
class PoliticalEvent(DomainEvent):
    """Something that happens in how the settlement is run: a government chosen, a leader
    seated, lost or gone. It says who took part, who saw it and how much it matters as any
    event does, so that history, sound and the screen can follow it."""

    # The kind of government it happened under. None before there is one.
    government: str | None = None
