from simulation.events.event import DomainEvent


class EventManager:
    def __init__(self) -> None:
        self.pending: list[DomainEvent] = []

    def emit(self, event: DomainEvent) -> None:
        self.pending.append(event)

    def drain(self) -> list[DomainEvent]:
        events = list(self.pending)
        self.pending.clear()
        return events
