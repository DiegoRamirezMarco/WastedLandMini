"""What is done to a spoken line to make it somebody's voice: higher or lower, faster or slower,
hoarse, trembling, metallic, or scrambled past understanding.

Everything here works on plain samples, from -1 to 1, and needs numpy and nothing else. Without
numpy the game has no voices, which it can do without.
"""

import random
import wave
from pathlib import Path

import numpy as np

from audio.voice_system import GARBLE, GROWL, PITCH, ROBOT, SPEED, TREMBLE, VoiceProfile

Samples = np.ndarray

# How long a piece of sound is laid over the next when a line is made longer or shorter, and how
# far either side of where it should be taken from a better fit is looked for, in seconds.
STRETCH_WINDOW = 0.04
STRETCH_SEARCH = 0.012
# A tremble: how often the voice wavers a second, twice over so that it never quite repeats, how
# far its pitch is pulled, in seconds of delay, and how much of its loudness comes and goes.
TREMBLE_RATES = (5.3, 7.9)
TREMBLE_DELAY = 0.0022
TREMBLE_DEPTH = 0.4
# A growl: how hard the voice is driven into distortion, and the rattle under it, in Hz.
GROWL_DRIVE = 9.0
GROWL_RATTLE = 38.0
# A robot: the hum the voice is multiplied by, and the pipe it seems to speak through, in Hz.
ROBOT_HUM = 55.0
ROBOT_PIPE = 190.0
ROBOT_RING = 0.72
# Scrambled speech: how long the pieces are that it is cut into, and the join between them, in seconds.
GARBLE_GRAIN = 0.11
GARBLE_JOIN = 0.008
# How loud the loudest moment of a line is left.
PEAK = 0.85


def read_wav(path: Path) -> tuple[Samples, int]:
    """A WAV file as samples from -1 to 1, one channel, and how many of them there are to a second."""
    with wave.open(str(path), "rb") as file:
        rate, channels, width = file.getframerate(), file.getnchannels(), file.getsampwidth()
        raw = file.readframes(file.getnframes())
    if width != 2:
        raise ValueError(f"{path} is not 16-bit sound")
    samples = np.frombuffer(raw, dtype="<i2").astype(np.float32) / 32768.0
    if channels > 1:
        samples = samples.reshape(-1, channels).mean(axis=1)
    return samples, rate


def resampled(samples: Samples, factor: float) -> Samples:
    """A sound played `factor` times as fast: that much shorter, and that much higher, voice and all."""
    if len(samples) < 2 or abs(factor - 1.0) < 1e-6:
        return samples
    count = max(2, int(round(len(samples) / factor)))
    return np.interp(np.linspace(0.0, len(samples) - 1.0, count), np.arange(len(samples)), samples).astype(np.float32)


def stretched(samples: Samples, factor: float, rate: int) -> Samples:
    """A sound made `factor` times as long without changing how high it is.

    Pieces of it are laid over each other, each taken from near where it should come from, at the
    spot that goes on best from the piece before, so that the voice does not ring or stutter.
    """
    window = int(rate * STRETCH_WINDOW) // 2 * 2
    if abs(factor - 1.0) < 0.01 or len(samples) < window * 2:
        return samples
    hop = window // 2
    search = int(rate * STRETCH_SEARCH)
    fade = np.hanning(window + 1)[:window].astype(np.float32)
    length = int(len(samples) * factor)
    padded = np.concatenate([samples, np.zeros(window + search * 2 + hop, dtype=np.float32)])
    out = np.zeros(length + window * 2, dtype=np.float32)
    last = 0
    out[:window] += padded[:window] * fade
    for index in range(1, max(1, length // hop)):
        ideal = int(index * hop / factor)
        # What would follow the last piece had nothing been moved: the new piece should look like it.
        follows = padded[last + hop : last + hop + window]
        low = max(0, ideal - search)
        high = min(len(samples) - 1, ideal + search)
        if high <= low or len(follows) < window:
            break
        fit = np.correlate(padded[low : high + window], follows, mode="valid")
        last = low + int(np.argmax(fit))
        out[index * hop : index * hop + window] += padded[last : last + window] * fade
    return out[:length]


def garbled(samples: Samples, amount: float, rate: int, seed: int) -> Samples:
    """Speech cut into short pieces, some played backwards and some out of turn: a voice, saying nothing."""
    grain = int(rate * GARBLE_GRAIN)
    if amount <= 0.0 or len(samples) < grain * 2:
        return samples
    chance = random.Random(seed)
    join = int(rate * GARBLE_JOIN)
    pieces = [samples[start : start + grain].copy() for start in range(0, len(samples), grain)]
    for index, piece in enumerate(pieces):
        if chance.random() < amount:
            pieces[index] = piece[::-1].copy()
    for index in range(0, len(pieces) - 2):
        # Never the last piece, which is where the voice dies away.
        if chance.random() < amount * 0.6:
            pieces[index], pieces[index + 1] = pieces[index + 1], pieces[index]
    ramp = np.linspace(0.0, 1.0, join, dtype=np.float32)
    for piece in pieces:
        if len(piece) > join * 2:
            piece[:join] *= ramp
            piece[-join:] *= ramp[::-1]
    return np.concatenate(pieces)


def trembling(samples: Samples, amount: float, rate: int) -> Samples:
    """A voice that wavers, in pitch and in strength, as an old one does."""
    if amount <= 0.0 or len(samples) < 2:
        return samples
    seconds = np.arange(len(samples), dtype=np.float32) / rate
    waver = sum(np.sin(2 * np.pi * each * seconds) for each in TREMBLE_RATES) / len(TREMBLE_RATES)
    delay = (1.0 + waver) * 0.5 * TREMBLE_DELAY * rate * amount
    at = np.clip(np.arange(len(samples)) - delay, 0, len(samples) - 1)
    wavering = np.interp(at, np.arange(len(samples)), samples)
    return (wavering * (1.0 - TREMBLE_DEPTH * amount * (1.0 + waver) * 0.5)).astype(np.float32)


def growling(samples: Samples, amount: float, rate: int) -> Samples:
    """A voice driven hoarse, with a rattle in the throat under it."""
    if amount <= 0.0:
        return samples
    drive = 1.0 + GROWL_DRIVE * amount
    loud = max(float(np.max(np.abs(samples))), 1e-6)
    rough = np.tanh(samples / loud * drive) / np.tanh(drive) * loud
    seconds = np.arange(len(samples), dtype=np.float32) / rate
    rattle = 0.5 + 0.5 * np.sign(np.sin(2 * np.pi * GROWL_RATTLE * seconds)) * np.abs(np.sin(2 * np.pi * GROWL_RATTLE * seconds)) ** 0.5
    return (rough * (1.0 - 0.55 * amount * rattle)).astype(np.float32)


def robotic(samples: Samples, amount: float, rate: int) -> Samples:
    """A voice out of a machine: multiplied by a hum, and ringing as if spoken down a pipe."""
    if amount <= 0.0:
        return samples
    seconds = np.arange(len(samples), dtype=np.float32) / rate
    hummed = samples * ((1.0 - amount) + amount * np.sin(2 * np.pi * ROBOT_HUM * seconds))
    # The pipe: each stretch of sound comes back, fainter, on top of the next one.
    delay = max(1, int(rate / ROBOT_PIPE))
    ring = ROBOT_RING * amount
    piped = hummed.astype(np.float32).copy()
    for start in range(delay, len(piped), delay):
        end = min(start + delay, len(piped))
        piped[start:end] += ring * piped[start - delay : start - delay + (end - start)]
    return piped


def shaped(samples: Samples, rate: int, profile: VoiceProfile, seed: int = 0) -> Samples:
    """A line as spoken by the model, made into the voice a profile describes."""
    pitch = 2.0 ** (profile.value(PITCH) / 12.0)
    speed = max(0.25, profile.value(SPEED, 1.0))
    voice = garbled(samples.astype(np.float32), profile.value(GARBLE), rate, seed)
    # Higher or lower by playing it faster or slower, then back to the length it should have.
    voice = stretched(resampled(voice, pitch), pitch / speed, rate)
    voice = trembling(voice, profile.value(TREMBLE), rate)
    voice = growling(voice, profile.value(GROWL), rate)
    voice = robotic(voice, profile.value(ROBOT), rate)
    loud = float(np.max(np.abs(voice))) if len(voice) else 0.0
    return (voice * (PEAK / loud)).astype(np.float32) if loud > 1e-6 else voice


def as_pcm(samples: Samples, rate: int, out_rate: int, channels: int) -> bytes:
    """Samples as 16-bit sound at the rate and number of channels something plays at."""
    if out_rate != rate:
        samples = resampled(samples, rate / out_rate)
    whole = (np.clip(samples, -1.0, 1.0) * 32767.0).astype("<i2")
    if channels > 1:
        whole = np.repeat(whole[:, None], channels, axis=1)
    return whole.tobytes()
