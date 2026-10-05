"""Short synthesised sound effects, written as 16-bit mono WAV files."""

import io
import math
import struct
import wave

SAMPLE_RATE = 22050
AMPLITUDE = 0.35

# Each sound is a list of notes: (frequency in Hz, milliseconds, waveform). Frequency 0 is silence.
Note = tuple[float, int, str]
SOUNDS: dict[str, list[Note]] = {
    "alert": [(660, 90, "square"), (0, 30, "square"), (880, 90, "square"), (0, 30, "square"), (1320, 160, "square")],
    "resolve": [(523, 80, "triangle"), (659, 80, "triangle"), (784, 140, "triangle")],
    "chat": [(880, 40, "triangle"), (1175, 60, "triangle")],
    "argument": [(196, 70, "saw"), (165, 70, "saw"), (147, 140, "saw")],
    "whisper": [(1568, 30, "triangle"), (0, 20, "triangle"), (1568, 30, "triangle")],
    "gift": [(784, 60, "triangle"), (988, 60, "triangle"), (1175, 60, "triangle"), (1568, 160, "triangle")],
    "theft": [(330, 60, "square"), (262, 60, "square"), (196, 60, "square"), (131, 180, "square")],
    "missing": [(440, 120, "triangle"), (0, 40, "triangle"), (370, 220, "triangle")],
    "supplies": [(392, 70, "square"), (523, 110, "square")],
    "click": [(1047, 25, "square")],
}


def _wave(shape: str, phase: float) -> float:
    """One cycle of a waveform, for a phase from 0 to 1, in the range -1 to 1."""
    if shape == "square":
        return 1.0 if phase < 0.5 else -1.0
    if shape == "saw":
        return 2.0 * phase - 1.0
    return 4.0 * abs(phase - 0.5) - 1.0


def _note(frequency: float, milliseconds: int, shape: str) -> list[int]:
    count = SAMPLE_RATE * milliseconds // 1000
    if frequency <= 0:
        return [0] * count
    samples = []
    for index in range(count):
        phase = (index * frequency / SAMPLE_RATE) % 1.0
        # Fade out over the note, with a short fade in, so notes do not click.
        envelope = min(1.0, index / 40.0) * (1.0 - index / count)
        samples.append(int(32767 * AMPLITUDE * envelope * _wave(shape, phase)))
    return samples


def render(notes: list[Note]) -> bytes:
    """Return the notes as the bytes of a WAV file."""
    samples = [sample for note in notes for sample in _note(*note)]
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(SAMPLE_RATE)
        output.writeframes(struct.pack(f"<{len(samples)}h", *samples))
    return buffer.getvalue()


def duration_ms(notes: list[Note]) -> int:
    return sum(milliseconds for _, milliseconds, _ in notes)


def build() -> dict[str, bytes]:
    return {f"sounds/{name}.wav": render(notes) for name, notes in SOUNDS.items()}
