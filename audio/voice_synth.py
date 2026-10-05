"""Has lines spoken by a voice model, once each, and keeps what was said.

The speaking is done by Piper, a program of its own that the game runs when it needs a line it
has not heard before. It takes a second or two, so it is done on the side and the line is kept as
a WAV file: after the first time, a line costs nothing. Without Piper, or without the model, there
is simply no voice.
"""

import hashlib
import importlib.util
import logging
import queue
import subprocess
import sys
import threading
from collections.abc import Callable
from pathlib import Path

from audio.voice_system import VoiceModel

logger = logging.getLogger(__name__)

ENGINE_MODULE = "piper"
MODEL_SUFFIX = ".onnx"
# Seconds a line may take to be spoken before it is given up on.
TIMEOUT = 90
# What is wrong when a model cannot speak.
READY, NO_ENGINE, NO_MODEL = "ready", "no_engine", "no_model"

# Speaks a line with a model file and one of its speakers into a WAV file. Returns whether it did.
Runner = Callable[[Path, int, str, Path], bool]


def engine_installed() -> bool:
    try:
        return importlib.util.find_spec(ENGINE_MODULE) is not None
    except (ImportError, ValueError):
        return False


def run_piper(model: Path, speaker: int, text: str, out: Path) -> bool:
    """Have Piper speak a line, as a program of its own."""
    command = [sys.executable, "-m", ENGINE_MODULE, "-m", str(model), "-s", str(speaker), "-f", str(out), "--", text]
    try:
        done = subprocess.run(
            command, capture_output=True, timeout=TIMEOUT, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)
        )
    except (OSError, subprocess.SubprocessError) as error:
        logger.warning("Piper could not be run: %s", error)
        return False
    if done.returncode != 0:
        logger.warning("Piper failed: %s", done.stderr.decode("utf-8", "replace")[-300:])
    return done.returncode == 0 and out.is_file()


class VoiceSynth:
    def __init__(
        self,
        models_dir: Path,
        cache_dir: Path,
        runner: Runner | None = None,
        threaded: bool = True,
    ) -> None:
        self.models_dir = models_dir
        self.cache_dir = cache_dir
        # Without a runner of its own it is Piper, if Piper is there.
        self._runner = runner if runner is not None else (run_piper if engine_installed() else None)
        self._threaded = threaded
        self._jobs: queue.Queue[tuple[VoiceModel, str]] = queue.Queue()
        self._asked: set[tuple[VoiceModel, str]] = set()
        self._done: list[tuple[VoiceModel, str]] = []
        self._lock = threading.Lock()
        self._worker: threading.Thread | None = None

    def model_path(self, model: VoiceModel) -> Path:
        return self.models_dir / f"{model.file}{MODEL_SUFFIX}"

    def state(self, model: VoiceModel) -> str:
        """Whether a model can speak new lines, or what it lacks."""
        if self._runner is None:
            return NO_ENGINE
        return READY if self.model_path(model).is_file() else NO_MODEL

    def path_for(self, model: VoiceModel, text: str) -> Path:
        """Where a line spoken by a model is kept. It is named after the line itself, so a changed line is a new one."""
        name = hashlib.sha1(text.encode("utf-8")).hexdigest()[:20]
        return self.cache_dir / f"{model.file}-{model.speaker}" / f"{name}.wav"

    def spoken(self, model: VoiceModel, text: str) -> Path | None:
        """The line as the model spoke it, if it already has."""
        path = self.path_for(model, text)
        return path if path.is_file() else None

    def waiting(self, model: VoiceModel, text: str) -> bool:
        with self._lock:
            return (model, text) in self._asked

    def request(self, model: VoiceModel, text: str) -> bool:
        """Have a line spoken, unless it has been or is about to be. Returns whether it will be there."""
        if self.spoken(model, text) is not None:
            return True
        if self.state(model) != READY:
            return False
        with self._lock:
            if (model, text) in self._asked:
                return True
            self._asked.add((model, text))
        if not self._threaded:
            self._speak(model, text)
            return True
        self._jobs.put((model, text))
        if self._worker is None or not self._worker.is_alive():
            self._worker = threading.Thread(target=self._work, name="voice-synth", daemon=True)
            self._worker.start()
        return True

    def finished(self) -> list[tuple[VoiceModel, str]]:
        """The lines spoken since this was last asked."""
        with self._lock:
            done, self._done = self._done, []
        return done

    def _work(self) -> None:
        while True:
            try:
                model, text = self._jobs.get(timeout=5.0)
            except queue.Empty:
                return
            self._speak(model, text)

    def _speak(self, model: VoiceModel, text: str) -> None:
        path = self.path_for(model, text)
        # Written under another name first: a file is never there half-made.
        part = path.with_suffix(".part")
        worked = False
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            worked = self._runner is not None and self._runner(self.model_path(model), model.speaker, text, part)
            if worked:
                part.replace(path)
        except OSError as error:
            logger.warning("A spoken line could not be kept: %s", error)
            worked = False
        finally:
            part.unlink(missing_ok=True)
        with self._lock:
            self._asked.discard((model, text))
            if worked:
                self._done.append((model, text))
