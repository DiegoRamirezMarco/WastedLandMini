import struct
import tempfile
import unittest
import wave
from pathlib import Path

from audio.music import DAY, MOODS, NIGHT, STORM, TENSION, MusicSettings, load_music_settings, mood_of, track_for
from graphics.assets import ASSETS_DIR
from simulation.events.crisis import Crisis
from simulation.events.decision import Decision
from simulation.events.world_event import Weather
from simulation.registries import DATA_DIR
from simulation.residents.activity import Activity
from simulation.world import SimulationWorld
from tools.art.music import SAMPLE_RATE, TRACKS, beats, duration_ms, frequency, render


def _samples(name: str) -> tuple[list[int], int]:
    with wave.open(str(ASSETS_DIR / "music" / f"{name}.wav"), "rb") as track:
        frames = track.readframes(track.getnframes())
        return list(struct.unpack(f"<{len(frames) // 2}h", frames)), track.getframerate()


class MusicFilesTests(unittest.TestCase):
    def test_every_track_is_a_valid_wav_of_the_length_it_was_written_at(self) -> None:
        for name, track in TRACKS.items():
            path = ASSETS_DIR / "music" / f"{name}.wav"
            self.assertTrue(path.exists(), name)
            with wave.open(str(path), "rb") as sound:
                self.assertEqual((sound.getnchannels(), sound.getsampwidth(), sound.getframerate()), (1, 2, SAMPLE_RATE))
                milliseconds = sound.getnframes() * 1000 // sound.getframerate()
            self.assertLess(abs(milliseconds - duration_ms(track)), 20, name)
            self.assertGreater(milliseconds, 5000, name)

    def test_a_track_can_go_round_without_a_click_and_never_distorts(self) -> None:
        for name in TRACKS:
            samples, _ = _samples(name)
            peak = max(abs(sample) for sample in samples)
            self.assertGreater(peak, 2000, f"{name} is all but silent")
            self.assertLess(peak, 32000, f"{name} clips")
            # It ends, and begins, close to silence: the seam of the loop.
            self.assertLess(max(abs(sample) for sample in samples[-40:]), 600, name)
            self.assertLess(abs(samples[0]), 600, name)

    def test_the_generator_makes_exactly_the_files_that_are_there(self) -> None:
        for name in TRACKS:
            self.assertEqual(render(name), (ASSETS_DIR / "music" / f"{name}.wav").read_bytes(), name)

    def test_pitches_and_beats(self) -> None:
        self.assertAlmostEqual(frequency("A4"), 440.0)
        self.assertAlmostEqual(frequency("A3"), 220.0)
        self.assertAlmostEqual(frequency("C4"), 261.63, places=1)
        self.assertGreater(frequency("F#3"), frequency("F3"))
        self.assertEqual(frequency("-"), 0.0)
        self.assertEqual(beats(TRACKS["day"]), 32)
        with self.assertRaisesRegex(ValueError, "different numbers of beats"):
            beats((90, [("square", 0.1, [("A3", 4)]), ("square", 0.1, [("A2", 3)])]))

    def test_every_mood_has_a_track_that_exists(self) -> None:
        settings = load_music_settings(DATA_DIR / "audio.json")
        self.assertEqual(set(settings.tracks), set(MOODS))
        for mood, track in settings.tracks.items():
            self.assertIn(track, TRACKS, mood)

    def test_a_missing_or_broken_file_means_no_music_not_a_crash(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(load_music_settings(Path(tmp) / "nope.json"), MusicSettings())
            broken = Path(tmp) / "audio.json"
            broken.write_text('{"music": {"tracks": 7, "night_hours": "late"}}', encoding="utf-8")
            self.assertEqual(load_music_settings(broken), MusicSettings())


class MoodTests(unittest.TestCase):
    def setUp(self) -> None:
        self.world = SimulationWorld.demo_world()
        self.settings = load_music_settings(DATA_DIR / "audio.json")

    def test_the_music_goes_by_the_hour(self) -> None:
        moods = {}
        for hour in (8, 14, 20, 21, 23, 3, 5, 6):
            self.world.clock.hour = hour
            moods[hour] = mood_of(self.world, self.settings)
        self.assertEqual(
            moods, {8: DAY, 14: DAY, 20: DAY, 21: NIGHT, 23: NIGHT, 3: NIGHT, 5: NIGHT, 6: DAY}
        )

    def test_a_storm_is_heard_over_the_hour_and_trouble_over_both(self) -> None:
        self.world.clock.hour = 23
        self.world.weather = Weather("dust_storm", self.world.clock.total_minutes + 120)
        self.assertEqual(mood_of(self.world, self.settings), STORM)
        raul = self.world.residents["raul"]
        raul.activity = Activity("fight", minutes_left=5, using=True, partner_id="marta")
        self.assertEqual(mood_of(self.world, self.settings), TENSION)
        raul.activity = Activity("chat", minutes_left=5, using=True, partner_id="marta")
        self.assertEqual(mood_of(self.world, self.settings), STORM)
        self.assertEqual(track_for(self.world, self.settings), "storm")

    def test_only_a_decision_that_is_urgent_changes_the_music(self) -> None:
        def waiting(urgency: int) -> None:
            self.world.decisions = {
                "d": Decision("d", "raul", "", [], "crisis_opened", crisis=Crisis("raul", "marta", 0.0, urgency, ""))
            }

        waiting(50)
        self.assertEqual(mood_of(self.world, self.settings), DAY)
        waiting(62)
        self.assertEqual(mood_of(self.world, self.settings), TENSION)

    def test_a_mood_with_no_track_is_silence(self) -> None:
        self.assertIsNone(track_for(self.world, MusicSettings(tracks={"night": "night"})))


if __name__ == "__main__":
    unittest.main()
