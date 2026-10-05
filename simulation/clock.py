from dataclasses import dataclass


@dataclass
class SimulationClock:
    day: int = 1
    hour: int = 8
    minute: int = 0
    fixed_tick_minutes: int = 1
    paused: bool = False
    speed: int = 1

    def advance_minutes(self, minutes: int) -> None:
        if minutes < 0:
            raise ValueError("minutes must be non-negative")
        total = self.hour * 60 + self.minute + minutes
        self.day += total // (24 * 60)
        total %= 24 * 60
        self.hour, self.minute = divmod(total, 60)

    def advance_ticks(self, ticks: int = 1) -> int:
        if ticks < 0:
            raise ValueError("ticks must be non-negative")
        minutes = self.fixed_tick_minutes * ticks
        self.advance_minutes(minutes)
        return minutes

    @property
    def total_minutes(self) -> int:
        """Game minutes since day 1, 00:00."""
        return (self.day - 1) * 24 * 60 + self.hour * 60 + self.minute

    @property
    def label(self) -> str:
        return f"Día {self.day} · {self.hour:02d}:{self.minute:02d}"
