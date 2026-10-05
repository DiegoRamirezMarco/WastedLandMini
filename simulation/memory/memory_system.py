from simulation.memory.memory import Memory


class MemorySystem:
    """Memories are kept per resident: nobody remembers what they did not take part in."""

    def __init__(self) -> None:
        self._memories: dict[str, list[Memory]] = {}

    def remember(self, resident_id: str, memory: Memory) -> None:
        self._memories.setdefault(resident_id, []).append(memory)

    def recent(self, resident_id: str, limit: int = 10) -> list[Memory]:
        return self._memories.get(resident_id, [])[-limit:]

    def of(self, resident_id: str) -> list[Memory]:
        return list(self._memories.get(resident_id, []))

    def resident_ids(self) -> list[str]:
        return list(self._memories)
