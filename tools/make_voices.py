"""Get the voices ready: fetch the models that are missing and have them speak every line the game has.

    python -m tools.make_voices            fetch what is missing, then speak every written line with every model
    python -m tools.make_voices --models   only fetch the models

The game does this by itself, a line at a time, the first time each line is said. This does it all
at once, so that nobody waits. It needs Piper: pip install piper-tts
"""

import argparse
import json
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path

from audio.voice_synth import MODEL_SUFFIX, READY, VoiceSynth, engine_installed
from audio.voice_system import CACHE_FOLDER, MODELS_FOLDER, VOICES_DIR, VoiceCatalog, load_voice_catalog
from simulation.registries import DATA_DIR

DOWNLOADER = "piper.download_voices"


def written_lines(catalog: VoiceCatalog, data_dir: Path = DATA_DIR) -> list[str]:
    """Every line that is written out whole: what residents say to each other, and what a voice is tried with.

    What they ask the player names somebody, so it is only known, and spoken, when it is asked.
    """
    dialogue = json.loads((data_dir / "dialogue.json").read_text(encoding="utf-8"))
    lines = [str(line) for kind in dialogue.values() for line in kind]
    return list(dict.fromkeys([*lines, *catalog.samples]))


def fetch_models(catalog: VoiceCatalog, models_dir: Path) -> list[str]:
    """Download the model files that are not there. Returns the names of those it fetched."""
    missing = sorted({model.file for model in catalog.models.values() if not (models_dir / f"{model.file}{MODEL_SUFFIX}").is_file()})
    if missing:
        models_dir.mkdir(parents=True, exist_ok=True)
        subprocess.run([sys.executable, "-m", DOWNLOADER, "--download-dir", str(models_dir), *missing], check=True)
    return missing


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Fetch the voice models and have them speak the game's lines.")
    parser.add_argument("--models", action="store_true", help="only fetch the models")
    parser.add_argument("--voices", type=Path, default=VOICES_DIR, help="the folder the voices are kept in")
    args = parser.parse_args(argv)
    if not engine_installed():
        raise SystemExit("Piper is not installed: pip install piper-tts")
    catalog = load_voice_catalog()
    for name in fetch_models(catalog, args.voices / MODELS_FOLDER):
        print(f"fetched {name}")
    if args.models:
        return
    synth = VoiceSynth(args.voices / MODELS_FOLDER, args.voices / CACHE_FOLDER, threaded=False)
    lines = written_lines(catalog)
    for model in catalog.models.values():
        if synth.state(model) != READY:
            print(f"skipped {model.label}: its model is missing")
            continue
        spoken = 0
        for line in lines:
            if synth.spoken(model, line) is None:
                synth.request(model, line)
                spoken += synth.spoken(model, line) is not None
        print(f"{model.label}: {spoken} new lines, {len(lines)} in all")


if __name__ == "__main__":
    main()
