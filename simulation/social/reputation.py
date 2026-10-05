from dataclasses import dataclass


@dataclass
class Reputation:
    respected: float = 0.0
    feared: float = 0.0
    trusted: float = 0.0
