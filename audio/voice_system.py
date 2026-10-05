from dataclasses import dataclass


@dataclass
class VoiceProfile:
    pitch: float = 1.0
    speed: float = 1.0
    formant: float = 1.0
    expression: float = 0.5
