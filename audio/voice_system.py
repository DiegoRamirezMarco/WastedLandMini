"""Who sounds like what: the voices there are to choose from, and the one each resident has.

A voice is a profile: a model that speaks, and a figure for each control that is then applied to
what it said. Profiles are what is kept. The sound itself is made again whenever it is needed, and
is never part of a saved game. Nothing here makes a sound, or needs anything but the standard
library.
"""

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from simulation.registries import DATA_DIR

logger = logging.getLogger(__name__)

VOICES_PATH = DATA_DIR / "voices.json"
# Where the models, the lines they have spoken and the voices given to residents are kept.
VOICES_DIR = DATA_DIR.parent / "voices"
MODELS_FOLDER = "models"
CACHE_FOLDER = "cache"
RESIDENTS_FOLDER = "residents"

# The controls the game knows what to do with. Their names, ranges and order are data.
PITCH = "pitch"
SPEED = "speed"
TREMBLE = "tremble"
GROWL = "growl"
ROBOT = "robot"
GARBLE = "garble"
# What each control is at when it does nothing, for a profile that does not mention it.
NEUTRAL = {PITCH: 0.0, SPEED: 1.0, TREMBLE: 0.0, GROWL: 0.0, ROBOT: 0.0, GARBLE: 0.0}


@dataclass(frozen=True)
class VoiceModel:
    """Something that speaks: a model file, and which of its speakers."""

    model_id: str
    label: str
    file: str
    speaker: int = 0


@dataclass(frozen=True)
class VoiceControl:
    """Something about a voice that can be turned up or down, and how far."""

    control_id: str
    label: str
    low: float
    high: float
    default: float
    step: float = 0.05
    # What is written after the figure, and how many decimals of it.
    unit: str = ""
    decimals: int = 2

    def clamp(self, value: float) -> float:
        """The nearest figure the control can be set to."""
        value = min(max(value, self.low), self.high)
        if self.step <= 0:
            return value
        return round(min(self.low + round((value - self.low) / self.step) * self.step, self.high), 4)

    def describe(self, value: float) -> str:
        return f"{value:+.{self.decimals}f}{self.unit}" if self.low < 0 else f"{value:.{self.decimals}f}{self.unit}"


@dataclass(frozen=True)
class VoiceProfile:
    """One voice: the model that speaks and what each control is set to."""

    model: str
    # Control and figure, in the order of the controls' names, so that two equal voices are equal.
    values: tuple[tuple[str, float], ...] = ()

    def value(self, control_id: str, default: float | None = None) -> float:
        for name, value in self.values:
            if name == control_id:
                return value
        return NEUTRAL.get(control_id, 0.0) if default is None else default

    def with_value(self, control_id: str, value: float) -> "VoiceProfile":
        kept = {name: figure for name, figure in self.values}
        kept[control_id] = value
        return VoiceProfile(self.model, tuple(sorted(kept.items())))

    def with_model(self, model: str) -> "VoiceProfile":
        return VoiceProfile(model, self.values)

    def to_data(self) -> dict[str, Any]:
        return {"model": self.model, **dict(self.values)}


@dataclass(frozen=True)
class VoiceCatalog:
    """Everything a voice can be made of, and the voices that come ready made."""

    models: dict[str, VoiceModel]
    controls: dict[str, VoiceControl]
    # Ready-made voices by name: what they are called, and the profile.
    presets: dict[str, tuple[str, VoiceProfile]]
    # The voice a resident starts with, by resident ID, until somebody gives them another.
    cast: dict[str, VoiceProfile]
    default: VoiceProfile | None
    # Lines to hear a voice with while it is being made.
    samples: tuple[str, ...] = ()

    def profile_from(self, data: Any, base: VoiceProfile | None = None) -> VoiceProfile | None:
        """A profile out of what a file says, kept within what the controls allow. None if it names no model there is.

        `preset` starts from a ready-made voice; whatever else is given is laid over it.
        """
        if not isinstance(data, dict):
            return None
        preset = self.presets.get(str(data.get("preset", "")))
        start = preset[1] if preset is not None else base
        model = str(data.get("model", start.model if start is not None else ""))
        if model not in self.models:
            return None
        values = {}
        for control_id, control in self.controls.items():
            given = data.get(control_id, start.value(control_id, control.default) if start is not None else control.default)
            values[control_id] = control.clamp(float(given)) if isinstance(given, (int, float)) else control.default
        return VoiceProfile(model, tuple(sorted(values.items())))

    def voice_of(self, resident_id: str) -> VoiceProfile | None:
        """The voice a resident has before anybody has chosen one for them."""
        return self.cast.get(resident_id, self.default)

    def preset_like(self, profile: VoiceProfile) -> str | None:
        """Which ready-made voice a profile is, if it is exactly one of them."""
        return next((name for name, (_, preset) in self.presets.items() if preset == profile), None)


EMPTY_CATALOG = VoiceCatalog({}, {}, {}, {}, None)


def catalog_from_data(data: dict[str, Any]) -> VoiceCatalog:
    models = {
        str(model_id): VoiceModel(str(model_id), str(values.get("name", model_id)), str(values["file"]), int(values.get("speaker", 0)))
        for model_id, values in data.get("models", {}).items()
    }
    controls = {
        str(control_id): VoiceControl(
            str(control_id),
            str(values.get("name", control_id)),
            float(values["min"]),
            float(values["max"]),
            float(values.get("default", NEUTRAL.get(str(control_id), 0.0))),
            float(values.get("step", 0.05)),
            str(values.get("unit", "")),
            int(values.get("decimals", 2)),
        )
        for control_id, values in data.get("controls", {}).items()
    }
    bare = VoiceCatalog(models, controls, {}, {}, None)
    presets = {}
    for name, values in data.get("presets", {}).items():
        profile = bare.profile_from(values)
        if profile is None:
            raise ValueError(f"Voice preset {name} speaks with unknown model: {values.get('model')}")
        presets[str(name)] = (str(values.get("name", name)), profile)
    known = VoiceCatalog(models, controls, presets, {}, None)
    cast = {}
    for resident_id, values in data.get("residents", {}).items():
        profile = known.profile_from(values)
        if profile is None:
            raise ValueError(f"The voice of {resident_id} is not one there is: {values}")
        cast[str(resident_id)] = profile
    default = presets.get(str(data.get("default", "")))
    if default is None and presets:
        default = next(iter(presets.values()))
    samples = tuple(str(line) for line in data.get("samples", ()))
    return VoiceCatalog(models, controls, presets, cast, default[1] if default is not None else None, samples)


def load_voice_catalog(path: Path = VOICES_PATH) -> VoiceCatalog:
    """Read the voices there are. A missing or broken file means there are none, and the game is silent."""
    try:
        return catalog_from_data(json.loads(path.read_text(encoding="utf-8")))
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as error:
        logger.warning("No voices: %s", error)
        return EMPTY_CATALOG


class VoiceStore:
    """The voice each resident has: the one chosen for them and kept on disk, or else the one they start with."""

    def __init__(self, root: Path | None, catalog: VoiceCatalog) -> None:
        self.root = root
        self.catalog = catalog
        self._kept: dict[str, VoiceProfile | None] = {}

    def path_of(self, resident_id: str) -> Path | None:
        return self.root / RESIDENTS_FOLDER / f"{resident_id}.json" if self.root is not None else None

    def get(self, resident_id: str) -> VoiceProfile | None:
        """A resident's voice. None only if there are no voices at all."""
        if resident_id not in self._kept:
            self._kept[resident_id] = self._read(resident_id)
        return self._kept[resident_id] or self.catalog.voice_of(resident_id)

    def chosen(self, resident_id: str) -> bool:
        """Whether somebody has chosen this resident's voice, and it is not just the one they start with."""
        self.get(resident_id)
        return self._kept.get(resident_id) is not None

    def _read(self, resident_id: str) -> VoiceProfile | None:
        path = self.path_of(resident_id)
        if path is None or not path.is_file():
            return None
        try:
            return self.catalog.profile_from(json.loads(path.read_text(encoding="utf-8")))
        except (OSError, ValueError, TypeError) as error:
            logger.warning("The voice kept for %s could not be read: %s", resident_id, error)
            return None

    def save(self, resident_id: str, profile: VoiceProfile) -> bool:
        """Keep a voice for a resident. Returns whether it could be written."""
        path = self.path_of(resident_id)
        if path is None:
            return False
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(profile.to_data(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        except OSError as error:
            logger.warning("The voice of %s could not be kept: %s", resident_id, error)
            return False
        self._kept[resident_id] = profile
        return True
