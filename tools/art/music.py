"""Background music: short synthesised loops, written as 16-bit mono WAV files.

Each track is a few voices written as notes, tracker style. Every voice of a track lasts the same
number of beats, and every note fades out before the next, so a track can loop without a click.
"""

import functools
import io
import struct
import wave

from tools.art.sounds import _wave

# Music is slow and low, so half the rate of the sound effects is plenty and halves the files.
SAMPLE_RATE = 11025
SEMITONES = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}

# A note is a pitch such as "A3" or "F#2" and how many beats it lasts. "-" is a rest.
Note = tuple[str, float]
# A voice is a waveform, how loud it is from 0 to 1, and its notes.
Voice = tuple[str, float, list[Note]]
# A track is a tempo in beats per minute and its voices.
Track = tuple[int, list[Voice]]


def _repeat(notes: list[Note], times: int) -> list[Note]:
    return notes * times


TRACKS: dict[str, Track] = {
    # Daylight: an unhurried tune over a walking bass. Somebody whistling while they work.
    "day": (
        84,
        [
            (
                "triangle",
                0.30,
                [
                    ("A4", 1), ("C5", 1), ("E5", 2), ("D5", 1), ("C5", 1), ("A4", 2),
                    ("G4", 1), ("A4", 1), ("C5", 2), ("A4", 1), ("G4", 1), ("E4", 2),
                    ("A4", 1), ("C5", 1), ("E5", 2), ("G5", 1), ("E5", 1), ("D5", 2),
                    ("C5", 1), ("A4", 1), ("G4", 1), ("E4", 1), ("A4", 3), ("-", 1),
                ],
            ),
            (
                "square",
                0.10,
                _repeat([("A2", 2), ("E3", 2), ("F2", 2), ("C3", 2), ("G2", 2), ("D3", 2), ("A2", 2), ("E3", 2)], 2),
            ),
        ],
    ),
    # Night: long low notes with air between them. The fire, and not much else.
    "night": (
        56,
        [
            ("triangle", 0.26, [("E4", 3), ("-", 1), ("G4", 3), ("-", 1), ("A4", 2), ("G4", 2), ("E4", 3), ("-", 1)]),
            ("triangle", 0.18, [("A2", 4), ("E2", 4), ("F2", 4), ("E2", 4)]),
        ],
    ),
    # A storm: a low drone with a pulse on top of it that never settles.
    "storm": (
        72,
        [
            ("saw", 0.14, [("E2", 4), ("E2", 4), ("D2", 4), ("E2", 4)]),
            ("square", 0.08, _repeat([("B3", 0.5), ("-", 0.5), ("B3", 0.5), ("-", 0.5), ("A3", 0.5), ("-", 1.5)], 4)),
        ],
    ),
    # Something is about to go wrong: a tight figure that keeps coming round.
    "tension": (
        126,
        [
            ("square", 0.14, _repeat([("E3", 0.5), ("E3", 0.5), ("G3", 0.5), ("E3", 0.5), ("A3", 0.5), ("E3", 0.5), ("G3", 0.5), ("F#3", 0.5)], 4)),
            ("saw", 0.12, [("E2", 4), ("E2", 4), ("C2", 4), ("D2", 4)]),
        ],
    ),
}


def frequency(pitch: str) -> float:
    """Frequency in Hz of a pitch such as "A4" (440) or "F#2". A rest is 0."""
    if pitch == "-":
        return 0.0
    name, octave = pitch[:-1], int(pitch[-1])
    semitone = SEMITONES[name[0]] + (1 if name.endswith("#") else 0)
    return 440.0 * 2.0 ** ((semitone - 9) / 12.0 + (octave - 4))


def beats(track: Track) -> float:
    """How many beats a track lasts. Every voice must last the same."""
    lengths = {sum(length for _, length in notes) for _, _, notes in track[1]}
    if len(lengths) != 1:
        raise ValueError(f"The voices of a track last different numbers of beats: {sorted(lengths)}")
    return lengths.pop()


def duration_ms(track: Track) -> int:
    return round(beats(track) * 60000 / track[0])


def _voice(tempo: int, shape: str, volume: float, notes: list[Note]) -> list[float]:
    samples: list[float] = []
    for pitch, length in notes:
        count = round(SAMPLE_RATE * length * 60 / tempo)
        hertz = frequency(pitch)
        if hertz <= 0:
            samples.extend([0.0] * count)
            continue
        # A quick rise, then a slow fall to nothing by the end of the note.
        rise = max(1, SAMPLE_RATE // 100)
        for index in range(count):
            envelope = min(1.0, index / rise) * (1.0 - index / count) ** 1.5
            samples.append(volume * envelope * _wave(shape, (index * hertz / SAMPLE_RATE) % 1.0))
    return samples


@functools.cache
def render(name: str) -> bytes:
    """Return a track as the bytes of a WAV file. Rendered once: it is slow work."""
    tempo, voices = TRACKS[name]
    beats(TRACKS[name])
    mixed = [sum(values) for values in zip(*(_voice(tempo, *voice) for voice in voices))]
    samples = [int(32767 * max(-1.0, min(1.0, value))) for value in mixed]
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(SAMPLE_RATE)
        output.writeframes(struct.pack(f"<{len(samples)}h", *samples))
    return buffer.getvalue()


def build() -> dict[str, bytes]:
    return {f"music/{name}.wav": render(name) for name in TRACKS}
