import tempfile
import unittest
from pathlib import Path

from audio.music import DAY, MOODS, NIGHT, STORM, TENSION, MusicSettings, load_music_settings, mood_of, track_for
from graphics.assets import ASSETS_DIR
from simulation.events.crisis import Crisis
from simulation.events.decision import Decision
from simulation.events.world_event import Weather
from simulation.registries import DATA_DIR
from simulation.residents.activity import Activity
from simulation.world import SimulationWorld


# The moods are told apart whether or not anything plays for them: a track for each, as a game with music would have.
EVERY_MOOD = MusicSettings(tracks={mood: mood for mood in MOODS})


class MusicSettingsTests(unittest.TestCase):
    def test_the_game_comes_with_no_music_and_every_mood_is_silence(self) -> None:
        settings = load_music_settings(DATA_DIR / "audio.json")
        self.assertEqual(settings.tracks, {})
        self.assertEqual(list((ASSETS_DIR / "music").glob("*.wav")), [])
        world = SimulationWorld.demo_world()
        for hour in (9, 23):
            world.clock.hour = hour
            self.assertIsNone(track_for(world, settings))

    def test_a_missing_or_broken_file_means_no_music_not_a_crash(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(load_music_settings(Path(tmp) / "nope.json"), MusicSettings())
            broken = Path(tmp) / "audio.json"
            broken.write_text('{"music": {"tracks": 7, "night_hours": "late"}}', encoding="utf-8")
            self.assertEqual(load_music_settings(broken), MusicSettings())


class MoodTests(unittest.TestCase):
    def setUp(self) -> None:
        self.world = SimulationWorld.demo_world()
        self.settings = EVERY_MOOD

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
