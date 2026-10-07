import json
import os
import shutil
import tempfile
import unittest
import wave
from pathlib import Path

import pygame

from audio.ambience import actions_in_view, ambience_for, at_night, talking
from audio.audio_manager import (
    AMBIENCE_FOLDER,
    SOUNDS_DIR,
    AmbienceRule,
    AudioManager,
    SoundSettings,
    find_sound,
    load_sound_settings,
)
from audio.music import MusicSettings
from graphics.assets import ASSETS_DIR
from simulation.events.world_event import Weather
from simulation.registries import DATA_DIR
from simulation.residents.activity import Activity
from simulation.world import SimulationWorld
from tools.art.sounds import AMBIENCE, AMBIENCE_SECONDS, PITCHED, ROUGH, SOUNDS, UNDER, duration_ms, render, render_ambience

AUDIO = DATA_DIR / "audio.json"


class GeneratedSoundTests(unittest.TestCase):
    def test_there_are_far_more_sounds_than_the_eleven_the_game_began_with(self) -> None:
        self.assertGreater(len(SOUNDS), 55)
        for name in ("hammer", "clank", "coins", "knock", "gavel", "ballots", "decree", "banished", "held", "order"):
            self.assertIn(name, SOUNDS)

    def test_every_note_is_one_the_synth_can_play(self) -> None:
        for name, notes in {**SOUNDS, **{f"{name} (under)": notes for name, notes in UNDER.items()}}.items():
            for note in notes:
                self.assertIn(len(note), (3, 4, 5), name)
                self.assertIn(note[2], (*PITCHED, *ROUGH), name)
                self.assertGreater(note[1], 0, name)
        self.assertTrue(set(UNDER) <= set(SOUNDS))
        for name, under in UNDER.items():
            self.assertLessEqual(duration_ms(under), duration_ms(SOUNDS[name]) + 200, name)

    def test_the_same_notes_give_the_same_file_and_a_second_voice_changes_it(self) -> None:
        notes = SOUNDS["built"]
        self.assertEqual(render(notes, UNDER["built"]), render(notes, UNDER["built"]))
        self.assertNotEqual(render(notes, UNDER["built"]), render(notes))
        self.assertEqual(len(render(notes, UNDER["built"])), len(render(notes)), "it is no longer for it")

    def test_a_note_can_slide_and_be_louder_or_softer(self) -> None:
        plain = render([(440, 100, "sine")])
        self.assertNotEqual(render([(440, 100, "sine", 880)]), plain)
        self.assertNotEqual(render([(440, 100, "sine", 440, 0.3)]), plain)
        self.assertEqual(render([(440, 100, "sine", 440, 1.0)]), plain)
        for shape in ROUGH:
            self.assertNotEqual(render([(300, 80, shape)]), render([(300, 80, "sine")]), shape)

    def test_ambience_is_a_few_seconds_that_can_go_round_and_round(self) -> None:
        self.assertEqual(set(AMBIENCE), {"wind", "night", "storm", "fire", "generator", "voices"})
        for name in AMBIENCE:
            path = ASSETS_DIR / "sounds" / AMBIENCE_FOLDER / f"{name}.wav"
            self.assertTrue(path.exists(), name)
            with wave.open(str(path), "rb") as sound:
                self.assertEqual((sound.getnchannels(), sound.getsampwidth(), sound.getframerate()), (1, 2, 22050))
                self.assertEqual(sound.getnframes(), int(22050 * AMBIENCE_SECONDS), name)
                frames = sound.readframes(sound.getnframes())
            samples = [int.from_bytes(frames[index : index + 2], "little", signed=True) for index in range(0, len(frames), 2)]
            peak = max(abs(sample) for sample in samples)
            self.assertGreater(peak, 15000, f"{name} is loud enough to be turned down, not too quiet to be heard")
            self.assertLess(peak, 32767, name)

    def test_ambience_comes_out_the_same_every_time(self) -> None:
        self.assertEqual(render_ambience(AMBIENCE["night"], 0.5), render_ambience(AMBIENCE["night"], 0.5))


class SoundSettingsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.settings = load_sound_settings(AUDIO)

    def test_everything_that_sounds_has_a_sound_there_is(self) -> None:
        for name in self.settings.names():
            self.assertIn(name, SOUNDS, name)
        for name in self.settings.ambience:
            self.assertIn(name, AMBIENCE, name)
        self.assertGreater(len(self.settings.events), 130)

    def test_what_matters_most_is_not_left_silent(self) -> None:
        events = self.settings.events
        for event_type in (
            "death", "fight_started", "site_finished", "object_salvaged", "law_enacted", "vote_held",
            "election_held", "resident_expelled", "child_born", "couple_married", "raiders_at_gate",
            "stranger_at_gate", "order_given", "resident_held", "material_wanted", "power_failed",
        ):
            self.assertIn(event_type, events)
        self.assertNotEqual(events["death"], events["injured"])
        self.assertNotEqual(events["law_enacted"], events["law_broken"])
        self.assertEqual(events["crisis_opened"], "alert", "what there was is as it was")

    def test_the_players_hand_what_is_being_done_and_the_air_each_have_theirs(self) -> None:
        settings = self.settings
        self.assertEqual(set(settings.interface), {"click", "open", "close", "select", "refuse", "order"})
        self.assertIn("build", settings.actions)
        self.assertIn("salvage", settings.actions)
        self.assertGreater(settings.actions["sleep"].every_ms, settings.actions["build"].every_ms)
        self.assertEqual(settings.ambience["fire"], AmbienceRule("near", settings.ambience["fire"].volume, "campfire"))
        self.assertTrue(settings.ambience["generator"].powered)
        self.assertEqual({rule.when for rule in settings.ambience.values()}, {"day", "night", "storm", "near", "talk"})
        self.assertLess(settings.volumes["actions"], settings.volumes["effects"])

    def test_a_part_that_makes_no_sense_is_silent_and_the_rest_is_kept(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "audio.json"
            self.assertEqual(load_sound_settings(path), SoundSettings())
            path.write_text("{ not json", encoding="utf-8")
            self.assertEqual(load_sound_settings(path), SoundSettings())
            path.write_text(
                json.dumps(
                    {
                        "events": {"death": "toll"},
                        "interface": "loud",
                        "actions": {"build": {"every_ms": 100}, "salvage": {"sound": "clank", "every_ms": 1}},
                        "ambience": {"wind": {"when": "tuesdays"}, "night": {"when": "night", "volume": 7}, "fire": 3},
                        "volumes": {"effects": "max", "actions": 0.2},
                    }
                ),
                encoding="utf-8",
            )
            settings = load_sound_settings(path)
            self.assertEqual(settings.events, {"death": "toll"})
            self.assertEqual(settings.interface, {})
            self.assertEqual(list(settings.actions), ["salvage"])
            self.assertEqual(settings.actions["salvage"].every_ms, 50, "nothing sounds faster than can be told apart")
            self.assertEqual(settings.ambience, {"night": AmbienceRule("night", 1.0)})
            self.assertEqual((settings.volumes["effects"], settings.volumes["actions"]), (1.0, 0.2))

    def test_the_folder_for_the_players_own_sounds_says_what_each_is_called(self) -> None:
        readme = (SOUNDS_DIR / "README.md").read_text(encoding="utf-8")
        for name in self.settings.names():
            self.assertIn(f"`{name}`", readme, name)
        for name in self.settings.ambience:
            self.assertIn(f"`{AMBIENCE_FOLDER}/{name}`", readme, name)


class OwnSoundTests(unittest.TestCase):
    def test_a_sound_of_the_players_own_is_found_before_the_games(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            own, game = Path(folder) / "own", Path(folder) / "game"
            own.mkdir()
            game.mkdir()
            self.assertIsNone(find_sound("hammer", [own, game]))
            (game / "hammer.wav").write_bytes(render(SOUNDS["hammer"]))
            self.assertEqual(find_sound("hammer", [own, game]), game / "hammer.wav")
            (own / "hammer.ogg").write_bytes(b"not really")
            self.assertEqual(find_sound("hammer", [own, game]), own / "hammer.ogg")
            (own / "hammer.wav").write_bytes(render(SOUNDS["click"]))
            self.assertEqual(find_sound("hammer", [own, game]), own / "hammer.wav", "a wav before an ogg")


class AudioManagerTests(unittest.TestCase):
    """The real mixer, with no loudspeaker: SDL's dummy audio driver."""

    def setUp(self) -> None:
        self.addCleanup(self._restore, os.environ.get("SDL_AUDIODRIVER"))
        os.environ["SDL_AUDIODRIVER"] = "dummy"
        pygame.init()
        self.addCleanup(pygame.quit)
        self.folder = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.folder, True)
        self.settings = load_sound_settings(AUDIO)

    @staticmethod
    def _restore(previous: str | None) -> None:
        if previous is None:
            os.environ.pop("SDL_AUDIODRIVER", None)
        else:
            os.environ["SDL_AUDIODRIVER"] = previous

    def _audio(self, own: Path | None = None) -> AudioManager:
        return AudioManager(ASSETS_DIR / "sounds", self.settings, own_dir=own)

    def test_every_sound_the_game_asks_for_is_loaded(self) -> None:
        audio = self._audio()
        self.assertTrue(audio.available)
        self.assertEqual(set(audio._sounds), self.settings.names())
        self.assertEqual(set(audio._ambience), set(self.settings.ambience))
        self.assertEqual(audio.own, set())

    def test_the_players_own_sounds_are_played_in_place_of_the_games(self) -> None:
        (self.folder / AMBIENCE_FOLDER).mkdir()
        (self.folder / "hammer.wav").write_bytes(render(SOUNDS["click"]))
        (self.folder / AMBIENCE_FOLDER / "wind.wav").write_bytes(render_ambience(AMBIENCE["wind"], 0.25))
        (self.folder / "toll.wav").write_bytes(b"this is no sound at all")
        audio = self._audio(self.folder)
        self.assertEqual(audio.own, {"hammer", "wind"})
        self.assertLess(audio._sounds["hammer"].get_length(), 0.1, "it is the one that was dropped in")
        self.assertNotIn("toll", audio._sounds, "one that cannot be read is left out, and nothing breaks")
        self.assertIn("clank", audio._sounds)

    def test_an_old_map_of_events_alone_still_does(self) -> None:
        audio = AudioManager(ASSETS_DIR / "sounds", {"crisis_opened": "alert"})
        self.assertEqual(audio.event_sounds, {"crisis_opened": "alert"})
        self.assertEqual(audio.ambience_levels, {})
        self.assertIsNone(audio.interface("click"))
        audio.set_ambience({"wind": 1.0})
        audio.update(1.0)

    def test_the_players_own_clicks_sound_and_what_has_no_sound_does_not(self) -> None:
        audio = self._audio()
        self.assertEqual(audio.interface("click"), "ui_click")
        self.assertEqual(audio.interface("order"), "order")
        self.assertIsNone(audio.interface("somersault"))
        audio.toggle_mute()
        self.assertEqual(audio.interface("refuse"), "ui_refuse", "it says what it would have been, muted or not")

    def test_what_is_being_done_in_view_sounds_every_so_often_for_as_long_as_it_is(self) -> None:
        audio = self._audio()
        every = self.settings.actions["build"].every_ms / 1000.0
        self.assertEqual(audio.on_actions(["build", "build", "wander"], 0.016), ["hammer"])
        self.assertEqual(audio.on_actions(["build"], every / 2), [], "not again so soon")
        self.assertEqual(audio.on_actions(["build", "salvage"], every / 4), ["clank"], "something else is")
        self.assertEqual(audio.on_actions(["build"], every), ["hammer"])
        self.assertEqual(audio.on_actions([], 10.0), [])

    def test_ambience_comes_up_and_dies_away_and_is_silenced_with_the_rest(self) -> None:
        audio = self._audio()
        self.assertTrue(all(level == 0.0 for level in audio.ambience_levels.values()))
        audio.set_ambience({"night": 1.0})
        audio.update(0.1)
        rising = audio.ambience_levels["night"]
        self.assertGreater(rising, 0.0)
        self.assertLess(rising, self.settings.ambience["night"].volume, "it does not come on all at once")
        audio.update(5.0)
        self.assertEqual(audio.ambience_levels["night"], self.settings.ambience["night"].volume)
        self.assertEqual(audio.ambience_levels["wind"], 0.0)
        self.assertTrue(audio._ambience_channels["night"].get_busy())
        self.assertFalse(audio._ambience_channels["wind"].get_busy())
        audio.toggle_mute()
        self.assertEqual(audio._ambience_channels["night"].get_volume(), 0.0)
        audio.toggle_mute()
        audio.set_ambience({})
        audio.update(5.0)
        self.assertEqual(audio.ambience_levels["night"], 0.0)
        self.assertFalse(audio._ambience_channels["night"].get_busy())


class WhatIsHeardTests(unittest.TestCase):
    def setUp(self) -> None:
        self.world = SimulationWorld.demo_world()
        self.rules = load_sound_settings(AUDIO).ambience
        self.music = MusicSettings()

    def _heard(self, kinds=(), people=()) -> set[str]:
        return {name for name, level in ambience_for(self.world, self.rules, self.music, kinds, people).items() if level > 0}

    def test_the_hour_and_the_weather_say_what_the_air_sounds_like(self) -> None:
        self.world.clock.hour = 12
        self.assertEqual(self._heard(), {"wind"})
        self.world.clock.hour = 23
        self.assertTrue(at_night(self.world, self.music.night_hours))
        self.assertEqual(self._heard(), {"night"})
        self.world.weather = Weather("dust_storm", self.world.clock.total_minutes + 60)
        self.assertEqual(self._heard(), {"storm"}, "a storm drowns the rest out")

    def test_what_is_in_view_is_heard_and_what_is_not_is_not(self) -> None:
        self.world.clock.hour = 12
        self.assertEqual(self._heard(kinds={"campfire", "bed"}), {"wind", "fire"})
        self.assertTrue(self.world.has_power())
        self.assertIn("generator", self._heard(kinds={"generator"}))
        for inventory in self.world.containers.values():
            inventory.items[:] = [item for item in inventory.items if item.definition_id != "fuel"]
        self.assertFalse(self.world.has_power())
        self.assertNotIn("generator", self._heard(kinds={"generator"}), "with no fuel it does not run")

    def test_people_talking_in_view_are_heard(self) -> None:
        self.world.clock.hour = 12
        raul, ines = self.world.residents["raul"], self.world.residents["ines"]
        raul.activity = Activity("chat", minutes_left=20, using=True, partner_id="ines")
        ines.activity = Activity("chat", minutes_left=20, using=True, partner_id="raul")
        self.assertTrue(talking(self.world, ["raul"]))
        self.assertIn("voices", self._heard(people=["raul", "paco"]))
        self.assertNotIn("voices", self._heard(people=["paco"]), "out of view, they are not")

    def test_what_those_in_view_are_doing_is_what_sounds(self) -> None:
        raul, paco = self.world.residents["raul"], self.world.residents["paco"]
        raul.activity = Activity("build", "site_1", minutes_left=30, using=True)
        paco.activity = Activity("salvage", "junk_1", path=[(1, 1)], minutes_left=30)
        self.assertEqual(actions_in_view(self.world, ["raul", "paco", "nobody"]), ["build"], "on his way there, Paco is not at it yet")
        self.assertEqual(actions_in_view(self.world, ["paco"]), [])


class GameSoundTests(unittest.TestCase):
    def setUp(self) -> None:
        for variable in ("SDL_VIDEODRIVER", "SDL_AUDIODRIVER"):
            self.addCleanup(self._restore_driver, variable, os.environ.get(variable))
            os.environ[variable] = "dummy"
        from game.game import Game

        self.game = Game(illustrations_dir=None, voices_dir=None, start_in_menu=False, sounds_dir=None)
        self.addCleanup(pygame.quit)

    @staticmethod
    def _restore_driver(variable: str, previous: str | None) -> None:
        if previous is None:
            os.environ.pop(variable, None)
        else:
            os.environ[variable] = previous

    def test_what_is_heard_follows_the_settlement_frame_by_frame(self) -> None:
        game, world = self.game, self.game.world
        world.clock.hour = 12
        for _ in range(120):
            game.update_sound(1 / 30)
        levels = game.audio.ambience_levels
        self.assertGreater(levels["wind"], 0.0)
        self.assertEqual(levels["night"], 0.0)
        world.clock.hour = 23
        for _ in range(120):
            game.update_sound(1 / 30)
        self.assertEqual(levels["wind"], 0.0)
        self.assertGreater(levels["night"], 0.0)

    def test_the_view_says_what_is_in_it(self) -> None:
        view = self.game.global_view
        kinds, people = view.in_view()
        self.assertTrue(kinds)
        self.assertTrue(set(people) <= set(self.game.world.residents))
        everything = {placed.kind for placed in self.game.world.interactables.values()}
        self.assertTrue(kinds <= everything)
        self.assertLess(len(kinds), len(everything), "not the whole settlement at once")

    def test_a_click_on_the_screen_sounds(self) -> None:
        view = self.game.global_view
        self.assertEqual(view.sound, self.game.audio.interface, "the game gives the view its way to sound")
        heard: list[str] = []
        view.sound = heard.append
        view.click(view.hud.menu[0].rect.center)
        self.assertEqual(heard, ["click"])
        view.render()
        _resident_id, rect = next(iter(view.hitboxes.items()))
        view.click(rect.center)
        self.assertIn("select", heard)

    def test_the_game_looks_for_the_players_own_sounds_unless_told_not_to(self) -> None:
        from game.game import Game

        self.assertEqual(Game.__init__.__defaults__[-1], SOUNDS_DIR)
        self.assertEqual(self.game.audio.own, set(), "told there is no such folder, it plays its own")


if __name__ == "__main__":
    unittest.main()
