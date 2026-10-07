"""Synthesised sound, written as 16-bit mono WAV files: short effects, and ambience that goes
round and round.

An effect is a list of notes played one after another, with an optional second list mixed
under it. A note is `(frequency, milliseconds, waveform)`, and may go on with the frequency it
slides to and how loud it is: `(220, 120, "saw", 110, 0.6)`. Frequency 0 is silence.

Waveforms: `square`, `triangle`, `saw` and `sine` are pitched. `noise` is a dry crunch, `hiss`
is thin and bright, `thud` is dull and low: the three are rough and take their colour from the
frequency.

Nothing here is recorded and nothing is random: the same code gives the same files.
"""

import io
import math
import struct
import wave

SAMPLE_RATE = 22050
AMPLITUDE = 0.35

Note = tuple
PITCHED = ("square", "triangle", "saw", "sine")
ROUGH = ("noise", "hiss", "thud")

# What the game came with. Each is the notes of one voice.
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
    "eat": [(90, 65, "noise"), (0, 45, "noise"), (75, 75, "noise"), (0, 35, "noise"), (110, 80, "noise")],
    # ----- what is done with the hands -----
    "hammer": [(140, 45, "thud", 70, 1.6), (0, 20, "sine"), (900, 30, "hiss", 400, 0.5)],
    "saw_wood": [(260, 110, "noise", 320, 0.8), (0, 30, "sine"), (300, 110, "noise", 240, 0.8)],
    "clank": [(1400, 30, "square", 900, 0.7), (620, 90, "triangle", 560, 0.9), (0, 20, "sine"), (410, 120, "triangle", 380, 0.5)],
    "crash": [(180, 120, "thud", 60, 1.8), (700, 160, "noise", 200, 0.9), (300, 180, "triangle", 120, 0.4)],
    "site": [(120, 50, "thud", 80, 1.5), (0, 70, "sine"), (120, 50, "thud", 80, 1.5)],
    "built": [(392, 70, "triangle"), (523, 70, "triangle"), (659, 70, "triangle"), (784, 70, "triangle"), (1047, 200, "triangle")],
    "dig": [(160, 70, "thud", 90, 1.4), (500, 90, "noise", 250, 0.5)],
    "haul": [(110, 60, "thud", 80, 1.2), (0, 50, "sine"), (95, 80, "thud", 70, 1.0)],
    "pour": [(700, 220, "hiss", 1500, 0.5), (500, 120, "sine", 900, 0.3)],
    "gulp": [(240, 70, "sine", 140, 0.9), (0, 50, "sine"), (220, 80, "sine", 130, 0.9)],
    "mend": [(1200, 25, "square", 1000, 0.5), (0, 60, "sine"), (1200, 25, "square", 1000, 0.5), (0, 60, "sine"), (880, 90, "triangle")],
    "scrap": [(900, 40, "noise", 500, 0.8), (520, 70, "triangle", 470, 0.8), (0, 30, "sine"), (700, 50, "noise", 300, 0.6)],
    # ----- coin and goods -----
    "coins": [(2093, 30, "triangle"), (2637, 30, "triangle"), (0, 30, "sine"), (2349, 30, "triangle"), (3136, 80, "triangle")],
    "swap": [(587, 60, "triangle"), (784, 60, "triangle"), (0, 40, "sine"), (784, 60, "triangle"), (587, 80, "triangle")],
    "refuse": [(220, 90, "square", 200, 0.7), (0, 40, "sine"), (175, 160, "square", 150, 0.7)],
    "bell": [(1319, 220, "sine", 1319, 0.9), (1319, 200, "triangle", 1319, 0.3)],
    # ----- bodies -----
    "punch": [(200, 50, "thud", 60, 2.0), (800, 60, "noise", 300, 0.9), (0, 40, "sine"), (150, 70, "thud", 50, 1.6)],
    "hurt": [(520, 90, "saw", 300, 0.8), (260, 160, "saw", 180, 0.6)],
    "toll": [(196, 300, "sine", 196, 1.2), (98, 280, "triangle", 98, 0.6)],
    "cough": [(300, 60, "noise", 200, 1.0), (0, 50, "sine"), (260, 90, "noise", 150, 0.9)],
    "smoke": [(1800, 25, "square", 1600, 0.4), (0, 60, "sine"), (900, 260, "hiss", 400, 0.35)],
    "cradle": [(784, 110, "sine"), (659, 110, "sine"), (784, 110, "sine"), (1047, 220, "sine")],
    "wedding": [(1047, 90, "triangle"), (1319, 90, "triangle"), (1568, 90, "triangle"), (2093, 90, "triangle"), (1568, 200, "triangle")],
    "heartbreak": [(659, 140, "sine", 622), (523, 160, "sine", 494), (392, 260, "sine", 349)],
    "snore": [(110, 260, "saw", 80, 0.5), (0, 80, "sine"), (95, 160, "triangle", 120, 0.3)],
    # ----- from outside -----
    "knock": [(180, 40, "thud", 120, 1.6), (0, 70, "sine"), (180, 40, "thud", 120, 1.6), (0, 70, "sine"), (180, 40, "thud", 120, 1.6)],
    "welcome": [(523, 80, "triangle"), (659, 80, "triangle"), (784, 80, "triangle"), (659, 60, "triangle"), (1047, 180, "triangle")],
    "siren": [(440, 180, "saw", 880, 0.8), (880, 180, "saw", 440, 0.8), (440, 180, "saw", 880, 0.8)],
    "gust": [(300, 280, "hiss", 900, 0.7), (900, 280, "hiss", 250, 0.5)],
    "static": [(2000, 80, "hiss", 2600, 0.5), (1760, 40, "square", 1760, 0.3), (0, 30, "sine"), (1760, 40, "square", 1760, 0.3), (2200, 120, "hiss", 1800, 0.4)],
    "power_down": [(440, 120, "saw", 220, 0.8), (220, 160, "saw", 80, 0.7), (80, 220, "saw", 40, 0.5)],
    # ----- how the settlement is run -----
    "gavel": [(260, 45, "thud", 150, 1.8), (0, 90, "sine"), (260, 45, "thud", 150, 1.8)],
    "ballots": [(1200, 30, "noise", 900, 0.5), (0, 40, "sine"), (1300, 30, "noise", 900, 0.5), (0, 40, "sine"), (1100, 30, "noise", 900, 0.5), (0, 40, "sine"), (1400, 40, "noise", 800, 0.5)],
    "passed": [(392, 90, "square", 392, 0.7), (523, 90, "square", 523, 0.7), (784, 240, "square", 784, 0.7)],
    "turned_down": [(392, 110, "square", 392, 0.7), (311, 110, "square", 311, 0.7), (262, 260, "square", 262, 0.7)],
    "decree": [(196, 120, "saw", 196, 0.7), (196, 60, "saw", 196, 0.7), (294, 120, "saw", 294, 0.7), (392, 240, "saw", 392, 0.7)],
    "fanfare": [(523, 80, "square", 523, 0.7), (523, 60, "square", 523, 0.7), (659, 80, "square", 659, 0.7), (784, 80, "square", 784, 0.7), (1047, 260, "square", 1047, 0.7)],
    "breach": [(988, 50, "square", 988, 0.5), (0, 30, "sine"), (740, 120, "square", 700, 0.5)],
    "banished": [(330, 140, "saw", 262, 0.7), (262, 140, "saw", 196, 0.7), (150, 60, "thud", 60, 2.0), (0, 40, "sine"), (98, 180, "triangle", 98, 0.5)],
    "plot": [(147, 160, "triangle", 139, 0.8), (0, 60, "sine"), (139, 160, "triangle", 131, 0.8), (0, 60, "sine"), (104, 120, "saw", 98, 0.5)],
    "outcry": [(440, 80, "saw", 660, 0.8), (660, 80, "saw", 440, 0.8), (440, 80, "saw", 700, 0.8), (700, 200, "saw", 350, 0.7)],
    # ----- the player's own hand -----
    "held": [(660, 60, "sine", 880, 0.6), (0, 30, "sine"), (880, 110, "sine", 990, 0.5)],
    "order": [(880, 40, "square", 880, 0.5), (1175, 40, "square", 1175, 0.5), (1568, 110, "triangle", 1568, 0.7)],
    "ask": [(523, 90, "triangle", 523, 0.7), (0, 40, "sine"), (698, 180, "triangle", 740, 0.7)],
    "found_out": [(1319, 50, "sine"), (1760, 50, "sine"), (2093, 140, "sine")],
    "learned": [(659, 70, "triangle"), (880, 70, "triangle"), (1109, 70, "triangle"), (1319, 70, "triangle"), (1760, 220, "sine")],
    "ui_click": [(1319, 18, "square", 1319, 0.5)],
    "ui_open": [(660, 35, "triangle", 880, 0.6), (990, 55, "triangle", 1175, 0.6)],
    "ui_close": [(990, 35, "triangle", 880, 0.6), (740, 55, "triangle", 587, 0.6)],
    "ui_select": [(1047, 30, "triangle", 1047, 0.6), (1397, 50, "triangle", 1397, 0.6)],
    "ui_refuse": [(196, 70, "square", 185, 0.6), (0, 30, "sine"), (165, 110, "square", 147, 0.6)],
}

# A second voice under some of them, no longer than the first.
UNDER: dict[str, list[Note]] = {
    "built": [(196, 280, "sine", 196, 0.5), (262, 200, "sine", 262, 0.5)],
    "toll": [(392, 400, "sine", 392, 0.3)],
    "wedding": [(523, 360, "sine", 523, 0.4), (784, 200, "sine", 784, 0.4)],
    "fanfare": [(131, 300, "saw", 131, 0.5), (196, 260, "saw", 196, 0.5)],
    "decree": [(98, 540, "triangle", 98, 0.6)],
    "passed": [(196, 420, "triangle", 196, 0.5)],
    "banished": [(600, 280, "hiss", 200, 0.3)],
    "crash": [(1100, 200, "hiss", 300, 0.5)],
    "siren": [(110, 540, "saw", 110, 0.3)],
    "bell": [(2637, 300, "sine", 2637, 0.25)],
    "learned": [(330, 500, "sine", 330, 0.35)],
}

# Ambience that goes round and round, each a few seconds long: voices that last the whole of it.
# A voice is `(waveform, frequency, loudness, how often it swells a second, how far it swells)`,
# and for something that comes in pulses, how many a second and how long each lasts.
AMBIENCE_SECONDS = 4.0
# How loud the loudest moment of a piece of ambience is written, of all the way, and how many
# samples a pulse in one takes to come up.
AMBIENCE_PEAK = 0.7
PULSE_ATTACK = 40.0
AMBIENCE: dict[str, list[dict]] = {
    "wind": [
        {"shape": "thud", "frequency": 260, "volume": 0.55, "swell": 0.25, "depth": 0.6},
        {"shape": "hiss", "frequency": 700, "volume": 0.18, "swell": 0.5, "depth": 0.8},
    ],
    "night": [
        {"shape": "sine", "frequency": 4200, "volume": 0.16, "pulses": 9.0, "pulse_ms": 28, "swell": 0.5, "depth": 0.9},
        {"shape": "sine", "frequency": 3600, "volume": 0.10, "pulses": 6.5, "pulse_ms": 34, "swell": 0.25, "depth": 0.9},
        {"shape": "thud", "frequency": 180, "volume": 0.22, "swell": 0.25, "depth": 0.4},
    ],
    "storm": [
        {"shape": "thud", "frequency": 420, "volume": 0.9, "swell": 0.5, "depth": 0.7},
        {"shape": "hiss", "frequency": 1400, "volume": 0.45, "swell": 0.75, "depth": 0.8},
        {"shape": "noise", "frequency": 900, "volume": 0.25, "pulses": 14.0, "pulse_ms": 22, "swell": 0.25, "depth": 0.5},
    ],
    "fire": [
        {"shape": "thud", "frequency": 300, "volume": 0.35, "swell": 0.75, "depth": 0.5},
        {"shape": "noise", "frequency": 1600, "volume": 0.45, "pulses": 7.0, "pulse_ms": 14, "swell": 0.5, "depth": 0.9},
        {"shape": "noise", "frequency": 800, "volume": 0.3, "pulses": 2.75, "pulse_ms": 30, "swell": 0.25, "depth": 0.6},
    ],
    "generator": [
        {"shape": "saw", "frequency": 55, "volume": 0.45, "swell": 6.0, "depth": 0.25},
        {"shape": "square", "frequency": 110, "volume": 0.12, "swell": 3.0, "depth": 0.4},
        {"shape": "thud", "frequency": 200, "volume": 0.2, "pulses": 12.0, "pulse_ms": 30, "swell": 0.25, "depth": 0.2},
    ],
    "voices": [
        {"shape": "triangle", "frequency": 190, "volume": 0.2, "pulses": 3.25, "pulse_ms": 150, "swell": 0.5, "depth": 0.9},
        {"shape": "triangle", "frequency": 260, "volume": 0.16, "pulses": 2.5, "pulse_ms": 170, "swell": 0.75, "depth": 0.9},
        {"shape": "sine", "frequency": 330, "volume": 0.1, "pulses": 4.5, "pulse_ms": 110, "swell": 0.25, "depth": 0.9},
    ],
}


def _wave(shape: str, phase: float) -> float:
    """One cycle of a waveform, for a phase from 0 to 1, in the range -1 to 1."""
    if shape == "square":
        return 1.0 if phase < 0.5 else -1.0
    if shape == "saw":
        return 2.0 * phase - 1.0
    if shape == "sine":
        return math.sin(2.0 * math.pi * phase)
    return 4.0 * abs(phase - 0.5) - 1.0


def _rough(index: int) -> float:
    """A deterministic rough sample: a short dry crunch without adding a recorded asset."""
    return (((index * 1103515245 + 12345) >> 16) & 32767) / 16384.0 - 1.0


def _coloured(shape: str, frequency: float, count: int, offset: int = 0) -> list[float]:
    """Rough sound of a colour: as it comes for `noise`, with the low taken out for `hiss`, and
    with all but the low taken out for `thud`. The frequency says where the line is drawn."""
    raw = [_rough(offset + index) for index in range(count)]
    if shape == "noise":
        return raw
    # One pole: how much of each new sample is let through.
    share = min(1.0, 2.0 * math.pi * max(20.0, frequency) / SAMPLE_RATE)
    low, kept = 0.0, []
    for sample in raw:
        low += share * (sample - low)
        kept.append(low)
    if shape == "thud":
        return [min(1.0, max(-1.0, sample * 2.5)) for sample in kept]
    return [raw[index] - kept[index] for index in range(count)]


def _parts(note: Note) -> tuple[float, int, str, float, float]:
    frequency, milliseconds, shape = float(note[0]), int(note[1]), str(note[2])
    slides_to = float(note[3]) if len(note) > 3 else frequency
    volume = float(note[4]) if len(note) > 4 else 1.0
    return frequency, milliseconds, shape, slides_to, volume


def _note(note: Note) -> list[float]:
    frequency, milliseconds, shape, slides_to, volume = _parts(note)
    count = SAMPLE_RATE * milliseconds // 1000
    if frequency <= 0:
        return [0.0] * count
    rough = _coloured(shape, frequency, count) if shape in ROUGH and shape != "noise" else None
    samples, phase = [], 0.0
    for index in range(count):
        # Fade out over the note, with a short fade in, so notes do not click.
        envelope = min(1.0, index / 40.0) * (1.0 - index / count)
        if shape == "noise":
            sample = _rough(index)
        elif rough is not None:
            sample = rough[index]
        else:
            sample = _wave(shape, phase % 1.0)
        samples.append(volume * envelope * sample)
        at = frequency + (slides_to - frequency) * index / count
        phase += at / SAMPLE_RATE
    return samples


def _voice(notes: list[Note]) -> list[float]:
    return [sample for note in notes for sample in _note(note)]


def _wav(samples: list[float]) -> bytes:
    """Samples from -1 to 1 as the bytes of a WAV file, with whatever goes over the top held back."""
    packed = [max(-32767, min(32767, int(32767 * AMPLITUDE * sample))) for sample in samples]
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(SAMPLE_RATE)
        output.writeframes(struct.pack(f"<{len(packed)}h", *packed))
    return buffer.getvalue()


def render(notes: list[Note], under: list[Note] | None = None) -> bytes:
    """Return the notes as the bytes of a WAV file, with a second voice mixed under them if there is one."""
    samples = _voice(notes)
    for index, sample in enumerate(_voice(under or [])[: len(samples)]):
        samples[index] += sample
    return _wav(samples)


def duration_ms(notes: list[Note]) -> int:
    return sum(int(note[1]) for note in notes)


def render_ambience(voices: list[dict], seconds: float = AMBIENCE_SECONDS) -> bytes:
    """Return ambience as the bytes of a WAV file that can be played round and round.

    Everything in it comes round a whole number of times in its length, and what is rough is
    faded into its own beginning, so that where it joins cannot be heard.
    """
    count = int(SAMPLE_RATE * seconds)
    mixed = [0.0] * count
    for number, voice in enumerate(voices):
        shape, frequency = str(voice["shape"]), float(voice["frequency"])
        volume, depth = float(voice.get("volume", 1.0)), float(voice.get("depth", 0.0))
        # How many times it swells, and pulses, in the whole of it: whole numbers, to come round.
        swells = max(1, round(float(voice.get("swell", 0.25)) * seconds))
        pulses = round(float(voice.get("pulses", 0.0)) * seconds)
        pulse = int(SAMPLE_RATE * float(voice.get("pulse_ms", 0)) / 1000)
        if shape in ROUGH:
            extra = SAMPLE_RATE // 4
            rough = _coloured(shape, frequency, count + extra, offset=number * 7919)
            body = rough[:count]
            for index in range(extra):
                # The end is faded into what comes after it, which is laid over the beginning.
                share = index / extra
                body[index] = rough[count + index] * (1.0 - share) + body[index] * share
        else:
            cycles = max(1, round(frequency * seconds))
            body = [_wave(shape, (index * cycles / count) % 1.0) for index in range(count)]
        for index in range(count):
            level = 1.0 - depth * (0.5 + 0.5 * math.sin(2.0 * math.pi * swells * index / count + number))
            if pulses and pulse:
                within = (index * pulses) % count / pulses
                # Each pulse comes up in an instant, though not so fast as to click, and dies away.
                level *= min(1.0, within / PULSE_ATTACK) * max(0.0, 1.0 - within / pulse) if within < pulse else 0.0
            mixed[index] += volume * level * body[index]
    # Ambience is written as loud as it will go without breaking up: how loud it is heard is
    # for the game to say.
    peak = max((abs(sample) for sample in mixed), default=0.0)
    return _wav([sample * AMBIENCE_PEAK / (peak * AMPLITUDE) for sample in mixed] if peak > 0 else mixed)


def build() -> dict[str, bytes]:
    files = {f"sounds/{name}.wav": render(notes, UNDER.get(name)) for name, notes in SOUNDS.items()}
    files.update({f"sounds/ambience/{name}.wav": render_ambience(voices) for name, voices in AMBIENCE.items()})
    return files
