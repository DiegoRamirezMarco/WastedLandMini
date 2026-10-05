import json
import math
import os
import struct
import tempfile
import time
import unittest
import wave
from pathlib import Path
from unittest import mock

import numpy as np
import pygame

from audio import voice_effects, voice_synth
from audio.voice_player import MAKING, NOTICES, VoicePlayer, speakable
from audio.voice_synth import NO_ENGINE, NO_MODEL, READY, VoiceSynth
from audio.voice_system import (
    CACHE_FOLDER,
    GARBLE,
    GROWL,
    MODELS_FOLDER,
    PITCH,
    ROBOT,
    SPEED,
    TREMBLE,
    VoiceProfile,
    VoiceStore,
    catalog_from_data,
    load_voice_catalog,
)
from scenes.hud import VOICE_INTENT
from settings import SCALE
from simulation.residents.activity import Activity
from simulation.world import SimulationWorld
from tools.make_voices import written_lines

RATE = 22050


def _tone(frequency: float = 220.0, seconds: float = 1.0) -> np.ndarray:
    return (0.5 * np.sin(2 * np.pi * frequency * np.arange(int(RATE * seconds)) / RATE)).astype(np.float32)


def _strongest(samples: np.ndarray) -> float:
    """The frequency there is most of in a sound, in Hz."""
    spectrum = np.abs(np.fft.rfft(samples * np.hanning(len(samples))))
    return float(np.argmax(spectrum)) * RATE / len(samples)


def _share(samples: np.ndarray, low: float, high: float) -> float:
    """How much of the strength of a sound is between two frequencies, from 0 to 1."""
    spectrum = np.abs(np.fft.rfft(samples)) ** 2
    hertz = np.fft.rfftfreq(len(samples), 1 / RATE)
    return float(spectrum[(hertz >= low) & (hertz < high)].sum() / spectrum.sum())


def _write_wav(path: Path, frequency: float = 220.0, seconds: float = 0.4) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    count = int(RATE * seconds)
    frames = b"".join(struct.pack("<h", int(12000 * math.sin(2 * math.pi * frequency * n / RATE))) for n in range(count))
    with wave.open(str(path), "wb") as file:
        file.setnchannels(1)
        file.setsampwidth(2)
        file.setframerate(RATE)
        file.writeframes(frames)


def _fake_runner(spoken: list[tuple[str, int, str]]):
    """Something that speaks as Piper would, but at once and with a plain tone, noting what it was asked."""

    def run(model: Path, speaker: int, text: str, out: Path) -> bool:
        spoken.append((model.name, speaker, text))
        _write_wav(out, 180.0 + 40.0 * speaker)
        return True

    return run


class VoiceCatalogTests(unittest.TestCase):
    def setUp(self) -> None:
        self.catalog = load_voice_catalog()

    def test_the_game_comes_with_models_controls_and_the_kinds_of_voice_asked_for(self) -> None:
        self.assertGreaterEqual(len(self.catalog.models), 2)
        self.assertEqual(
            list(self.catalog.presets),
            ["chico", "chica", "viejo", "vieja", "nino", "nina", "monstruo", "robot", "ininteligible"],
        )
        self.assertEqual(set(self.catalog.controls), {PITCH, SPEED, TREMBLE, GROWL, ROBOT, GARBLE})
        for name, (label, profile) in self.catalog.presets.items():
            self.assertTrue(label)
            self.assertIn(profile.model, self.catalog.models, name)
            for control_id, control in self.catalog.controls.items():
                value = profile.value(control_id)
                self.assertTrue(control.low <= value <= control.high, (name, control_id, value))
        self.assertTrue(self.catalog.samples)
        # Each kind is what its name says, in the one thing that makes it so.
        value = lambda name, control_id: self.catalog.presets[name][1].value(control_id)
        self.assertGreater(value("viejo", TREMBLE), 0.4)
        self.assertGreater(value("vieja", TREMBLE), 0.4)
        self.assertGreater(value("nina", PITCH), value("nino", PITCH))
        self.assertGreater(value("nino", PITCH), 2)
        self.assertLess(value("monstruo", PITCH), -5)
        self.assertGreater(value("monstruo", GROWL), 0.5)
        self.assertGreater(value("robot", ROBOT), 0.5)
        self.assertEqual(value("ininteligible", GARBLE), 1.0)
        self.assertNotEqual(self.catalog.presets["chico"][1].model, self.catalog.presets["chica"][1].model)

    def test_there_are_voices_from_spain_and_from_far_away_each_a_speaker_of_its_own(self) -> None:
        models = self.catalog.models
        self.assertEqual(
            list(models),
            ["hombre", "mujer", "hombre_2", "argentina", "mexicano", "mexicana", "aleman", "alemana", "frances", "francesa", "americano", "americana"],
        )
        self.assertEqual(len({(model.file, model.speaker) for model in models.values()}), len(models))
        self.assertEqual(len({model.label for model in models.values()}), len(models))
        # A man and a woman from each country asked for, speaking with the voice of that country.
        for man, woman, language in (("aleman", "alemana", "de_DE"), ("frances", "francesa", "fr_FR"), ("americano", "americana", "en_US")):
            for model_id in (man, woman):
                self.assertTrue(models[model_id].file.startswith(language), model_id)
            self.assertNotEqual((models[man].file, models[man].speaker), (models[woman].file, models[woman].speaker))
        # Whoever is in the settlement from the start speaks Spanish as it is spoken somewhere.
        for resident_id, profile in self.catalog.cast.items():
            self.assertTrue(models[profile.model].file.startswith("es_"), resident_id)

    def test_everyone_who_starts_in_the_settlement_starts_with_a_voice_and_no_two_are_the_same(self) -> None:
        world = SimulationWorld.demo_world()
        self.assertEqual(set(self.catalog.cast), set(world.residents))
        self.assertEqual(len(set(self.catalog.cast.values())), len(self.catalog.cast))
        # Whoever turns up later has the default one.
        self.assertEqual(self.catalog.voice_of("somebody_new"), self.catalog.default)
        self.assertEqual(self.catalog.default, self.catalog.presets["chico"][1])

    def test_a_control_is_kept_within_its_range_and_on_its_steps(self) -> None:
        pitch = self.catalog.controls[PITCH]
        self.assertEqual(pitch.clamp(99), pitch.high)
        self.assertEqual(pitch.clamp(-99), pitch.low)
        self.assertEqual(pitch.clamp(3.3), 3.5)
        self.assertEqual(pitch.describe(3.5), "+3.5 st")
        self.assertEqual(self.catalog.controls[SPEED].describe(0.85), "0.85x")

    def test_a_profile_is_read_from_a_file_over_a_ready_made_voice_and_made_safe(self) -> None:
        old = self.catalog.presets["viejo"][1]
        profile = self.catalog.profile_from({"preset": "viejo", "pitch": 400, "speed": "fast", "nonsense": 3})
        self.assertEqual(profile.model, old.model)
        self.assertEqual(profile.value(PITCH), self.catalog.controls[PITCH].high)
        self.assertEqual(profile.value(SPEED), self.catalog.controls[SPEED].default)
        self.assertEqual(profile.value(TREMBLE), old.value(TREMBLE))
        self.assertNotIn("nonsense", dict(profile.values))
        self.assertIsNone(self.catalog.profile_from({"model": "nobody"}))
        self.assertIsNone(self.catalog.profile_from(["not", "a", "voice"]))
        self.assertEqual(self.catalog.preset_like(old), "viejo")
        self.assertIsNone(self.catalog.preset_like(old.with_value(PITCH, 1.0)))
        self.assertEqual(self.catalog.profile_from(old.to_data()), old)

    def test_a_missing_or_broken_file_means_no_voices_not_a_crash(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            broken = Path(folder) / "voices.json"
            broken.write_text("{not json", encoding="utf-8")
            with self.assertLogs("audio.voice_system", level="WARNING"):
                self.assertEqual(load_voice_catalog(broken).models, {})
            with self.assertLogs("audio.voice_system", level="WARNING"):
                self.assertIsNone(load_voice_catalog(Path(folder) / "nothing.json").default)
        with self.assertRaises(ValueError):
            catalog_from_data({"models": {}, "controls": {}, "presets": {"chico": {"model": "nobody"}}})


class VoiceStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.catalog = load_voice_catalog()
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)

    def test_a_chosen_voice_is_kept_on_disk_and_read_back(self) -> None:
        store = VoiceStore(self.root, self.catalog)
        self.assertEqual(store.get("raul"), self.catalog.cast["raul"])
        self.assertFalse(store.chosen("raul"))
        robot = self.catalog.presets["robot"][1].with_value(PITCH, -3.0)
        self.assertTrue(store.save("raul", robot))
        self.assertTrue(store.chosen("raul"))
        kept = json.loads(store.path_of("raul").read_text(encoding="utf-8"))
        self.assertEqual(kept["model"], robot.model)
        self.assertEqual(kept[PITCH], -3.0)
        self.assertEqual(VoiceStore(self.root, self.catalog).get("raul"), robot)
        self.assertEqual(store.get("marta"), self.catalog.cast["marta"], "nobody else has changed")

    def test_a_voice_file_that_cannot_be_read_leaves_the_voice_they_started_with(self) -> None:
        store = VoiceStore(self.root, self.catalog)
        store.path_of("raul").parent.mkdir(parents=True)
        store.path_of("raul").write_text("{", encoding="utf-8")
        with self.assertLogs("audio.voice_system", level="WARNING"):
            self.assertEqual(store.get("raul"), self.catalog.cast["raul"])
        store.path_of("marta").write_text('{"model": "a model there is not"}', encoding="utf-8")
        self.assertEqual(store.get("marta"), self.catalog.cast["marta"])

    def test_without_a_folder_nothing_is_kept(self) -> None:
        store = VoiceStore(None, self.catalog)
        self.assertEqual(store.get("raul"), self.catalog.cast["raul"])
        self.assertFalse(store.save("raul", self.catalog.default))


class VoiceEffectsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.plain = VoiceProfile("any")

    def _shaped(self, samples: np.ndarray, **values: float) -> np.ndarray:
        profile = self.plain
        for control_id, value in values.items():
            profile = profile.with_value(control_id, value)
        return voice_effects.shaped(samples, RATE, profile, seed=7)

    def test_a_voice_with_nothing_turned_is_the_line_as_it_was_spoken(self) -> None:
        tone = _tone()
        same = self._shaped(tone)
        self.assertEqual(len(same), len(tone))
        self.assertAlmostEqual(float(np.abs(same).max()), voice_effects.PEAK, 3)
        self.assertLess(float(np.abs(same / voice_effects.PEAK - tone / 0.5).max()), 1e-3)

    def test_tone_makes_it_higher_or_lower_and_no_longer_or_shorter(self) -> None:
        tone = _tone(220.0, 1.0)
        for semitones, expected in ((12, 440.0), (-12, 110.0), (7, 220.0 * 2 ** (7 / 12))):
            voice = self._shaped(tone, pitch=semitones)
            self.assertAlmostEqual(_strongest(voice), expected, delta=expected * 0.03, msg=semitones)
            self.assertAlmostEqual(len(voice) / RATE, 1.0, delta=0.05, msg=semitones)

    def test_speed_makes_it_longer_or_shorter_and_no_higher_or_lower(self) -> None:
        tone = _tone(220.0, 1.0)
        for speed in (0.5, 1.5, 1.8):
            voice = self._shaped(tone, speed=speed)
            self.assertAlmostEqual(len(voice) / RATE, 1.0 / speed, delta=0.05, msg=speed)
            self.assertAlmostEqual(_strongest(voice), 220.0, delta=6.0, msg=speed)
            # Stretched or squeezed, it is still one steady note: no gaps and no doubling.
            middle = voice[len(voice) // 4 : -len(voice) // 4]
            tenth = len(middle) // 10
            loudness = np.abs(middle[: tenth * 10]).reshape(10, tenth).max(axis=1)
            self.assertGreater(float(loudness.min()), 0.6 * float(loudness.max()), speed)

    def test_tremble_makes_the_voice_waver(self) -> None:
        tone = _tone(220.0, 1.5)
        steady, old = self._shaped(tone), self._shaped(tone, tremble=1.0)
        loudness = lambda voice: np.abs(voice[: len(voice) // 441 * 441]).reshape(-1, 441).max(axis=1)[5:-5]
        self.assertLess(float(np.ptp(loudness(steady))), 0.02)
        self.assertGreater(float(np.ptp(loudness(old))), 0.2)
        self.assertLess(_share(old, 215.0, 225.0), _share(steady, 215.0, 225.0), "its pitch wanders too")
        self.assertEqual(len(old), len(steady))

    def test_growl_makes_it_hoarse_and_robot_makes_it_ring(self) -> None:
        tone = _tone(220.0, 1.0)
        clean = self._shaped(tone)
        self.assertLess(_share(clean, 500.0, 11000.0), 0.001)
        self.assertGreater(_share(self._shaped(tone, growl=1.0), 500.0, 11000.0), 0.05)
        machine = self._shaped(tone, robot=1.0)
        # Multiplied by a hum, the note is gone from where it was and stands either side of it.
        self.assertLess(_share(machine, 215.0, 225.0), 0.1)
        either = _share(machine, 220.0 - voice_effects.ROBOT_HUM - 6, 220.0 - voice_effects.ROBOT_HUM + 6)
        either += _share(machine, 220.0 + voice_effects.ROBOT_HUM - 6, 220.0 + voice_effects.ROBOT_HUM + 6)
        self.assertGreater(either, 0.5)
        for voice in (machine, self._shaped(tone, growl=1.0)):
            self.assertEqual(len(voice), len(tone))
            self.assertLessEqual(float(np.abs(voice).max()), voice_effects.PEAK + 1e-4)

    def test_garble_leaves_a_voice_that_says_nothing_and_says_it_the_same_way_each_time(self) -> None:
        # A rising note stands for speech: played backwards, a piece of it is a falling one.
        seconds = np.arange(RATE) / RATE
        speech = (0.5 * np.sin(2 * np.pi * (200.0 + 300.0 * seconds) * seconds)).astype(np.float32)
        garbled = self._shaped(speech, garble=1.0)
        self.assertEqual(len(garbled), len(speech))
        self.assertGreater(float(np.abs(garbled / voice_effects.PEAK - speech / 0.5).mean()), 0.2)
        self.assertAlmostEqual(float(np.sqrt((garbled**2).mean())), float(np.sqrt((self._shaped(speech) ** 2).mean())), delta=0.1)
        self.assertTrue(np.array_equal(garbled, self._shaped(speech, garble=1.0)))
        other = voice_effects.shaped(speech, RATE, self.plain.with_value(GARBLE, 1.0), seed=8)
        self.assertFalse(np.array_equal(garbled, other), "another line is scrambled another way")

    def test_a_voice_is_given_to_the_mixer_at_its_own_rate_and_number_of_channels(self) -> None:
        tone = _tone(220.0, 0.5)
        self.assertEqual(len(voice_effects.as_pcm(tone, RATE, RATE, 1)), len(tone) * 2)
        stereo = voice_effects.as_pcm(tone, RATE, RATE * 2, 2)
        self.assertEqual(len(stereo), len(tone) * 2 * 2 * 2)
        left, right = np.frombuffer(stereo, dtype="<i2").reshape(-1, 2).T
        self.assertTrue(np.array_equal(left, right))
        # Twice as many samples to the second: measured as if at the old rate, the note is an octave down.
        self.assertAlmostEqual(_strongest(left.astype(np.float32)) * 2, 220.0, delta=4.0)

    def test_a_spoken_line_is_read_from_its_file(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            _write_wav(Path(folder) / "line.wav", 330.0, 0.5)
            samples, rate = voice_effects.read_wav(Path(folder) / "line.wav")
        self.assertEqual(rate, RATE)
        self.assertEqual(len(samples), RATE // 2)
        self.assertAlmostEqual(_strongest(samples), 330.0, delta=4.0)
        self.assertLessEqual(float(np.abs(samples).max()), 1.0)


class VoiceSynthTests(unittest.TestCase):
    def setUp(self) -> None:
        self.catalog = load_voice_catalog()
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        self.models = self.root / MODELS_FOLDER
        self.models.mkdir()
        self.man, self.woman = self.catalog.models["hombre"], self.catalog.models["mujer"]
        for model in self.catalog.models.values():
            (self.models / f"{model.file}.onnx").write_bytes(b"a model")
        self.asked: list[tuple[str, int, str]] = []

    def _synth(self, **more) -> VoiceSynth:
        return VoiceSynth(self.models, self.root / CACHE_FOLDER, **{"runner": _fake_runner(self.asked), "threaded": False, **more})

    def test_a_line_is_spoken_once_by_each_speaker_and_kept(self) -> None:
        synth = self._synth()
        self.assertIsNone(synth.spoken(self.man, "Hola."))
        self.assertTrue(synth.request(self.man, "Hola."))
        kept = synth.spoken(self.man, "Hola.")
        self.assertTrue(kept.is_file())
        self.assertEqual(synth.finished(), [(self.man, "Hola.")])
        self.assertEqual(synth.finished(), [])
        self.assertTrue(synth.request(self.man, "Hola."))
        self.assertEqual(self.asked, [(f"{self.man.file}.onnx", 0, "Hola.")], "the second time it is already there")
        # Another speaker of the same model, and another line, are other files.
        synth.request(self.woman, "Hola.")
        synth.request(self.man, "¿Qué tal el día?")
        self.assertEqual(len({synth.path_for(self.man, "Hola."), synth.path_for(self.woman, "Hola."), synth.path_for(self.man, "¿Qué tal el día?")}), 3)
        self.assertEqual(self.asked[1:], [(f"{self.woman.file}.onnx", 1, "Hola."), (f"{self.man.file}.onnx", 0, "¿Qué tal el día?")])
        self.assertEqual(list((self.root / CACHE_FOLDER).rglob("*.part")), [])
        # What was kept is there for the next game too.
        self.assertEqual(self._synth(runner=lambda *_: self.fail("spoken again")).spoken(self.man, "Hola."), kept)

    def test_without_the_model_or_without_piper_nothing_is_spoken(self) -> None:
        synth = self._synth()
        self.assertEqual(synth.state(self.man), READY)
        (self.models / f"{self.man.file}.onnx").unlink()
        self.assertEqual(synth.state(self.man), NO_MODEL)
        self.assertFalse(synth.request(self.man, "Hola."))
        self.assertEqual(self.asked, [])
        with mock.patch.object(voice_synth, "engine_installed", return_value=False):
            silent = VoiceSynth(self.models, self.root / CACHE_FOLDER)
        self.assertEqual(silent.state(self.catalog.models["hombre_2"]), NO_ENGINE)
        self.assertFalse(silent.request(self.catalog.models["hombre_2"], "Hola."))

    def test_a_line_that_could_not_be_spoken_leaves_nothing_behind(self) -> None:
        synth = self._synth(runner=lambda *_: False)
        self.assertTrue(synth.request(self.man, "Hola."))
        self.assertIsNone(synth.spoken(self.man, "Hola."))
        self.assertEqual(synth.finished(), [])
        self.assertFalse(synth.waiting(self.man, "Hola."))
        self.assertEqual([path for path in (self.root / CACHE_FOLDER).rglob("*") if path.is_file()], [])

    def test_speaking_is_done_on_the_side_so_the_game_does_not_wait(self) -> None:
        def slow(model: Path, speaker: int, text: str, out: Path) -> bool:
            time.sleep(0.05)
            return _fake_runner(self.asked)(model, speaker, text, out)

        synth = self._synth(runner=slow, threaded=True)
        started = time.perf_counter()
        self.assertTrue(synth.request(self.man, "Hola."))
        self.assertTrue(synth.request(self.man, "Hola."))
        self.assertLess(time.perf_counter() - started, 0.04)
        self.assertTrue(synth.waiting(self.man, "Hola."))
        done: list = []
        while not done and time.perf_counter() - started < 5.0:
            time.sleep(0.01)
            done = synth.finished()
        self.assertEqual(done, [(self.man, "Hola.")])
        self.assertEqual(len(self.asked), 1)
        self.assertIsNotNone(synth.spoken(self.man, "Hola."))

    def test_every_written_line_is_one_the_tool_has_spoken_beforehand(self) -> None:
        world = SimulationWorld.demo_world()
        lines = written_lines(self.catalog)
        for kind in world.registries.dialogue.values():
            for line in kind:
                self.assertIn(line, lines)
        for line in self.catalog.samples:
            self.assertIn(line, lines)
        self.assertEqual(len(lines), len(set(lines)))


class _SoundTestCase(unittest.TestCase):
    """Tests that need the mixer, on a machine that may have no sound card."""

    def setUp(self) -> None:
        for variable in ("SDL_VIDEODRIVER", "SDL_AUDIODRIVER"):
            self.addCleanup(self._restore, variable, os.environ.get(variable))
            os.environ[variable] = "dummy"
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name) / "voices"
        (self.root / MODELS_FOLDER).mkdir(parents=True)
        self.catalog = load_voice_catalog()
        for model in self.catalog.models.values():
            (self.root / MODELS_FOLDER / f"{model.file}.onnx").write_bytes(b"a model")
        self.asked: list[tuple[str, int, str]] = []

    @staticmethod
    def _restore(variable: str, previous: str | None) -> None:
        if previous is None:
            os.environ.pop(variable, None)
        else:
            os.environ[variable] = previous

    def _synth(self) -> VoiceSynth:
        return VoiceSynth(self.root / MODELS_FOLDER, self.root / CACHE_FOLDER, runner=_fake_runner(self.asked), threaded=False)


class VoicePlayerTests(_SoundTestCase):
    def setUp(self) -> None:
        super().setUp()
        pygame.mixer.init(frequency=RATE, size=-16, channels=1)
        self.addCleanup(pygame.mixer.quit)
        self.synth = self._synth()
        self.player = VoicePlayer(self.catalog, VoiceStore(self.root, self.catalog), self.synth)

    def test_a_resident_says_a_line_in_their_own_voice(self) -> None:
        self.assertTrue(self.player.enabled)
        self.assertTrue(self.player.say("raul", "Tengo hambre."))
        raul = self.catalog.cast["raul"]
        self.assertEqual(self.player.last, (raul, "Tengo hambre."))
        self.assertTrue(self.player.busy)
        self.assertEqual(self.asked, [(f"{self.catalog.models[raul.model].file}.onnx", self.catalog.models[raul.model].speaker, "Tengo hambre.")])
        # Marta says the same line with another speaker; said again, nothing is spoken anew.
        self.assertTrue(self.player.say("marta", "Tengo hambre.", interrupt=True))
        self.assertEqual(self.player.last[0], self.catalog.cast["marta"])
        self.player.say("marta", "Tengo hambre.", interrupt=True)
        self.assertEqual(len(self.asked), 2)

    def test_a_line_waits_for_nobody_unless_it_interrupts(self) -> None:
        self.assertTrue(self.player.say("raul", "Ya está bien."))
        self.assertFalse(self.player.say("marta", "A mí no me hables así."), "Raúl is still speaking")
        self.assertEqual(self.player.last[1], "Ya está bien.")
        self.assertTrue(self.player.say("marta", "A mí no me hables así.", interrupt=True))
        self.assertEqual(self.player.last[1], "A mí no me hables así.")
        self.player.stop()
        self.assertFalse(self.player.busy)

    def test_nothing_is_said_of_a_line_with_nothing_in_it_or_with_the_sound_off(self) -> None:
        self.assertFalse(speakable("..."))
        self.assertTrue(speakable("¿Eh?"))
        self.assertFalse(self.player.say("raul", "..."))
        self.assertFalse(self.player.say("nobody", "Hola.") and self.catalog.default is None)
        self.assertEqual(self.asked[:0], [])
        audio = mock.Mock(muted=True)
        quiet = VoicePlayer(self.catalog, VoiceStore(self.root, self.catalog), self.synth, audio)
        self.assertFalse(quiet.say("raul", "Tengo hambre."))
        self.assertFalse(quiet.busy)
        audio.muted = False
        self.assertTrue(quiet.say("raul", "Tengo hambre."))

    def test_a_line_never_heard_before_is_said_as_soon_as_it_has_been_spoken(self) -> None:
        held: list[tuple] = []

        def later(model: Path, speaker: int, text: str, out: Path) -> bool:
            held.append((model, speaker, text, out))
            return False

        synth = VoiceSynth(self.root / MODELS_FOLDER, self.root / CACHE_FOLDER, runner=later, threaded=False)
        player = VoicePlayer(self.catalog, VoiceStore(self.root, self.catalog), synth)
        profile = self.catalog.cast["raul"]
        model = self.catalog.models[profile.model]
        # Piper is slow this once: the line is wanted, and not yet there.
        with mock.patch.object(synth, "request", return_value=True), mock.patch.object(synth, "waiting", return_value=True):
            self.assertTrue(player.say("raul", "¿Queda algo de comer?"))
            self.assertIsNone(player.last)
            self.assertEqual(player.notice(profile, "¿Queda algo de comer?"), MAKING)
            player.update()
            self.assertIsNone(player.last)
        _write_wav(synth.path_for(model, "¿Queda algo de comer?"))
        player.update()
        self.assertEqual(player.last, (profile, "¿Queda algo de comer?"))
        self.assertIsNone(player.notice(profile, "¿Queda algo de comer?"))
        # One that takes too long is no longer wanted when it comes.
        with mock.patch.object(synth, "request", return_value=True):
            player.say("raul", "Echo de menos el café.", interrupt=True)
        with mock.patch.object(pygame.time, "get_ticks", return_value=pygame.time.get_ticks() + 60_000):
            player.update()
        _write_wav(synth.path_for(model, "Echo de menos el café."))
        player.update()
        self.assertEqual(player.last[1], "¿Queda algo de comer?")

    def test_the_player_is_told_what_is_missing(self) -> None:
        profile = self.catalog.cast["marta"]
        model = self.catalog.models[profile.model]
        self.assertIsNone(self.player.notice(profile, "Hola."))
        (self.root / MODELS_FOLDER / f"{model.file}.onnx").unlink()
        self.assertEqual(self.player.notice(profile, "Hola."), NOTICES[NO_MODEL])
        self.assertFalse(self.player.say("marta", "Hola."))
        # A line already spoken needs neither the model nor Piper.
        _write_wav(self.synth.path_for(model, "Hola."))
        self.assertIsNone(self.player.notice(profile, "Hola."))
        self.assertTrue(self.player.say("marta", "Hola."))


class VoiceEditorTests(_SoundTestCase):
    """The real game shell, without a window, with a folder of voices whose lines are plain tones."""

    def setUp(self) -> None:
        super().setUp()
        from game import game as shell

        synth = self._synth()
        with mock.patch.object(shell, "VoiceSynth", return_value=synth):
            self.game = shell.Game(illustrations_dir=None, voices_dir=self.root, start_in_menu=False)
        self.addCleanup(pygame.quit)
        self.voices = self.game.voices

    def _event(self, kind: int, position: tuple[int, int], **more) -> None:
        window = (position[0] * SCALE + 1, position[1] * SCALE + 1)
        self.game.active_scene.handle_event(pygame.event.Event(kind, pos=window, **more))

    def _click(self, position: tuple[int, int]) -> None:
        self._event(pygame.MOUSEBUTTONDOWN, position, button=1)
        self._event(pygame.MOUSEBUTTONUP, position, button=1)

    def _open(self, resident_id: str):
        view = self.game.global_view
        view.hud.select_resident(resident_id)
        self._click(next(button for button in view.hud.menu if button.intent == VOICE_INTENT).rect.center)
        self.game.sync_scenes()
        self.assertEqual(self.game.scene_name, "voice")
        return self.game.voice_editor

    def _button(self, editor, intent: tuple):
        return next(button for button in editor.buttons if button.intent == intent)

    def test_the_menu_opens_the_editor_on_whoever_is_selected_and_time_stops(self) -> None:
        editor = self._open("lucia")
        self.assertEqual(editor.resident_id, "lucia")
        self.assertEqual(editor.profile, self.catalog.cast["lucia"])
        minute = self.game.world.clock.total_minutes
        self.game.advance_simulation(5.0)
        self.assertEqual(self.game.world.clock.total_minutes, minute)
        with self.assertNoLogs("graphics.assets", level="WARNING"):
            editor.render()
        # Escape leaves the voice, not the game. F3 is the way in from the keyboard.
        self.game.handle_key(pygame.K_ESCAPE)
        editor.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE, mod=0))
        self.game.sync_scenes()
        self.assertEqual(self.game.scene_name, "global")
        self.assertTrue(self.game.running)
        self.game.global_view.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_F3, mod=0))
        self.game.sync_scenes()
        self.assertEqual(self.game.scene_name, "voice")

    def test_however_many_voices_there_are_nothing_in_the_editor_lies_over_anything_else(self) -> None:
        editor = self._open("raul")
        self.assertEqual(len(editor.model_buttons), len(self.catalog.models))
        boxes = [button.rect for button in editor.buttons] + [slider.rect.inflate(0, 10) for slider in editor.sliders.values()]
        for index, box in enumerate(boxes):
            self.assertTrue(self.game.canvas.get_rect().contains(box), box)
            self.assertEqual(box.collidelist(boxes[index + 1 :]), -1, box)
        lowest_button = max(button.rect.bottom for button in (*editor.model_buttons, *editor.preset_buttons))
        self.assertGreater(min(slider.rect.top for slider in editor.sliders.values()), lowest_button)
        self.assertGreater(editor.preset_buttons[0].rect.top, max(button.rect.bottom for button in editor.model_buttons))
        # Every voice there is can be chosen, and is heard.
        for model_id in self.catalog.models:
            self._click(self._button(editor, ("model", model_id)).rect.center)
            self.assertEqual(editor.profile.model, model_id)
            self.assertEqual(self.voices.last[0].model, model_id)

    def test_a_kind_of_voice_is_chosen_with_a_click_and_heard_at_once(self) -> None:
        editor = self._open("raul")
        for name, (_, preset) in self.catalog.presets.items():
            self._click(self._button(editor, ("preset", name)).rect.center)
            self.assertEqual(editor.profile, preset, name)
            self.assertEqual(self.voices.last, (preset, editor.line), name)
        # Who speaks is changed by itself, and the rest of the voice stays.
        monster = self.catalog.presets["monstruo"][1]
        self._click(self._button(editor, ("preset", "monstruo")).rect.center)
        self._click(self._button(editor, ("model", "mujer")).rect.center)
        self.assertEqual(editor.profile, monster.with_model("mujer"))
        self.assertEqual(self.voices.last[0].model, "mujer")
        # Another line to try it with.
        first = editor.line
        self._click(self._button(editor, ("sample",)).rect.center)
        self.assertNotEqual(editor.line, first)
        self.assertEqual(self.voices.last[1], editor.line)
        editor.render()

    def test_each_slider_is_dragged_and_the_voice_is_heard_when_it_is_let_go(self) -> None:
        editor = self._open("raul")
        self._click(self._button(editor, ("preset", "chico")).rect.center)
        self.assertEqual(set(editor.sliders), set(self.catalog.controls))
        for control_id, slider in editor.sliders.items():
            control = self.catalog.controls[control_id]
            heard = self.voices.last
            y = slider.rect.centery
            self._event(pygame.MOUSEBUTTONDOWN, (slider.rect.left + 20, y), button=1)
            self._event(pygame.MOUSEMOTION, (slider.rect.right + 50, y - 40), rel=(0, 0), buttons=(1, 0, 0))
            self.assertEqual(editor.profile.value(control_id), control.high, control_id)
            self.assertEqual(self.voices.last, heard, "not while it is being dragged")
            editor.render()
            self._event(pygame.MOUSEBUTTONUP, (slider.rect.right + 50, y - 40), button=1)
            self.assertEqual(self.voices.last, (editor.profile, editor.line), control_id)
            # Let go of, it stays where it was left whatever the mouse does.
            self._event(pygame.MOUSEMOTION, (slider.rect.left, y), rel=(0, 0), buttons=(0, 0, 0))
            self.assertEqual(editor.profile.value(control_id), control.high, control_id)
        # A press on the track puts the knob there, on a step of the control.
        pitch = editor.sliders[PITCH]
        self._click((pitch.rect.centerx + 13, pitch.rect.centery))
        value = editor.profile.value(PITCH)
        self.assertGreater(value, 0)
        self.assertEqual(value, self.catalog.controls[PITCH].clamp(value))
        self.assertIsNone(self.catalog.preset_like(editor.profile))

    def test_a_saved_voice_is_theirs_from_then_on_and_nobody_elses(self) -> None:
        editor = self._open("raul")
        self._click(self._button(editor, ("preset", "robot")).rect.center)
        robot = self.catalog.presets["robot"][1]
        self.assertEqual(self.voices.store.get("raul"), self.catalog.cast["raul"], "not until it is saved")
        self._click(self._button(editor, ("save",)).rect.center)
        self.assertIn("Guardado", editor.notice)
        self.assertEqual(self.voices.store.get("raul"), robot)
        self.assertEqual(VoiceStore(self.root, self.catalog).get("raul"), robot)
        # On to the next resident, who has the voice they started with; and back, to the robot.
        self._click(self._button(editor, ("step", 1)).rect.center)
        self.assertNotEqual(editor.resident_id, "raul")
        self.assertEqual(editor.profile, self.catalog.cast[editor.resident_id])
        self._click(self._button(editor, ("step", -1)).rect.center)
        self.assertEqual(editor.profile, robot)
        self._click(self._button(editor, ("close",)).rect.center)
        self.game.sync_scenes()
        self.assertEqual(self.game.scene_name, "global")
        # In the settlement, what he says in the dock is said in that voice.
        world, view = self.game.world, self.game.global_view
        raul, tomas = world.residents["raul"], world.residents["tomas"]
        tomas.x, tomas.y = raul.x + 1, raul.y
        raul.activity = Activity("chat", partner_id="tomas", using=True)
        tomas.activity = Activity("chat", partner_id="raul", using=True)
        view.hud.select_resident("raul")
        self.voices.stop()
        view.render()
        speaker, line = view.hud.spoken
        self.assertIn(line, world.registries.dialogue["chat"])
        view.update(0.02)
        self.assertEqual(self.voices.last, (self.voices.store.get(speaker), line))
        # The same line is not said again every frame, and a new one is when the other takes their turn.
        self.voices.stop()
        self.voices.last = None
        view.render()
        view.update(0.02)
        self.assertIsNone(self.voices.last)
        world.clock.minute += 4 if world.clock.minute < 56 else -4
        view.render()
        other, reply = view.hud.spoken
        self.assertNotEqual(other, speaker)
        view.update(0.02)
        self.assertEqual(self.voices.last, (self.voices.store.get(other), reply))
        # Nobody talking, nothing said.
        raul.activity = tomas.activity = None
        view.render()
        self.assertIsNone(view.hud.spoken)

    def test_whoever_asks_for_advice_asks_it_out_loud(self) -> None:
        world = self.game.world
        for _ in range(40):
            self.game.advance_simulation(0.05)
            if world.decisions:
                break
        decision = next(iter(world.decisions.values()))
        self.voices.say("marta", "Tengo hambre.")
        self.game.open_interaction(decision.decision_id)
        self.assertEqual(self.voices.last, (self.voices.store.get(decision.resident_id), decision.prompt))
        self.assertTrue(self.voices.busy)


class NoVoicesTests(_SoundTestCase):
    def test_without_a_folder_of_voices_the_game_is_as_it_was(self) -> None:
        from game.game import Game

        game = Game(illustrations_dir=None, voices_dir=None, start_in_menu=False)
        self.addCleanup(pygame.quit)
        self.assertIsNone(game.voices)
        self.assertIsNone(game.voice_editor)
        self.assertNotIn(VOICE_INTENT, [button.intent for button in game.global_view.hud.menu])
        game.global_view.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_F3, mod=0))
        game.sync_scenes()
        self.assertEqual(game.scene_name, "global")
        game.global_view.render()
        game.global_view.update(0.02)


if __name__ == "__main__":
    unittest.main()
