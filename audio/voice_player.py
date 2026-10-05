"""Says lines out loud in a resident's voice.

A line is spoken once by a model, kept, and then made into the voice of whoever says it each time
it is wanted, which is quick. Never required: without sound, without numpy, without Piper or
without a model, nothing is said and nothing else changes.
"""

import logging
import zlib
from collections import OrderedDict

import pygame

from audio.audio_manager import AudioManager
from audio.voice_synth import NO_ENGINE, NO_MODEL, READY, VoiceSynth
from audio.voice_system import VoiceCatalog, VoiceProfile, VoiceStore

try:
    from audio import voice_effects
except ImportError:  # numpy is not there: no voices.
    voice_effects = None

logger = logging.getLogger(__name__)

# Real milliseconds a line may take to be spoken for the first time and still be said when it is ready.
STILL_WANTED_MS = 8000
# How many lines are kept ready to be said again, in the voices they were last said in.
KEPT_SOUNDS = 48
VOLUME = 0.9
# What the editor says of a voice that cannot be heard yet.
NOTICES = {
    NO_ENGINE: "Falta Piper para oír frases nuevas: pip install piper-tts",
    NO_MODEL: "Falta el modelo de esta voz: python -m tools.make_voices",
}
NO_SOUND = "No hay sonido en este equipo"
MAKING = "Preparando la voz..."


def speakable(text: str) -> bool:
    """Whether there is anything in a line to say."""
    return any(char.isalnum() for char in text)


class VoicePlayer:
    def __init__(
        self,
        catalog: VoiceCatalog,
        store: VoiceStore,
        synth: VoiceSynth,
        audio: AudioManager | None = None,
    ) -> None:
        self.catalog = catalog
        self.store = store
        self.synth = synth
        self.audio = audio
        # The voice and the line last said out loud, and the ones waiting to be spoken for the first time.
        self.last: tuple[VoiceProfile, str] | None = None
        self._wanted: tuple[VoiceProfile, str, int] | None = None
        self._sounds: OrderedDict[tuple[VoiceProfile, str], pygame.mixer.Sound] = OrderedDict()
        self._channel: pygame.mixer.Channel | None = None

    @property
    def enabled(self) -> bool:
        """Whether there is anything to say lines with."""
        return voice_effects is not None and bool(self.catalog.models)

    @property
    def audible(self) -> bool:
        return self.enabled and pygame.mixer.get_init() is not None

    @property
    def busy(self) -> bool:
        return self._channel is not None and self._channel.get_busy()

    def say(self, resident_id: str, text: str, interrupt: bool = False) -> bool:
        """Have a resident say a line. Returns whether it is being said, now or as soon as it is ready."""
        profile = self.store.get(resident_id)
        return profile is not None and self.speak(profile, text, interrupt)

    def speak(self, profile: VoiceProfile, text: str, interrupt: bool = True) -> bool:
        """Say a line in a voice. Unless told to interrupt, it waits for nobody: a line that finds another being said is dropped."""
        model = self.catalog.models.get(profile.model)
        if not self.audible or model is None or not speakable(text):
            return False
        if self.busy and not interrupt:
            return False
        if self.synth.spoken(model, text) is None:
            # Not heard before: it is said as soon as the model has spoken it, if it is still wanted then.
            if not self.synth.request(model, text):
                return False
            self._wanted = (profile, text, pygame.time.get_ticks())
            if self.synth.spoken(model, text) is None:
                return True
        return self._play(profile, text)

    def update(self) -> None:
        """Say what was waiting for its model, once the model has spoken."""
        finished = self.synth.finished()
        wanted = self._wanted
        if wanted is None:
            return
        profile, text, asked_at = wanted
        model = self.catalog.models.get(profile.model)
        if pygame.time.get_ticks() - asked_at > STILL_WANTED_MS or model is None:
            self._wanted = None
        elif (model, text) in finished or self.synth.spoken(model, text) is not None:
            self._wanted = None
            self._play(profile, text)

    def stop(self) -> None:
        self._wanted = None
        if self._channel is not None:
            self._channel.stop()

    def notice(self, profile: VoiceProfile, text: str | None = None) -> str | None:
        """What stands between a voice and being heard, in words for the player. None if nothing does."""
        model = self.catalog.models.get(profile.model)
        if model is None or not self.enabled:
            return None
        if not self.audible:
            return NO_SOUND
        if text is not None and self.synth.spoken(model, text) is not None:
            return None
        if self.synth.state(model) != READY:
            return NOTICES[self.synth.state(model)]
        return MAKING if text is not None and self.synth.waiting(model, text) else None

    def _play(self, profile: VoiceProfile, text: str) -> bool:
        sound = self._sound(profile, text)
        if sound is None:
            return False
        if self._channel is not None:
            self._channel.stop()
        self.last = (profile, text)
        if self.audio is not None and self.audio.muted:
            return False
        self._channel = sound.play()
        return self._channel is not None

    def _sound(self, profile: VoiceProfile, text: str) -> pygame.mixer.Sound | None:
        key = (profile, text)
        if key in self._sounds:
            self._sounds.move_to_end(key)
            return self._sounds[key]
        model = self.catalog.models.get(profile.model)
        path = self.synth.spoken(model, text) if model is not None else None
        mixer = pygame.mixer.get_init()
        # Only plain 16-bit sound is made, which is what the game asks the mixer for.
        if path is None or mixer is None or mixer[1] != -16 or voice_effects is None:
            return None
        try:
            samples, rate = voice_effects.read_wav(path)
            # The same line is scrambled the same way every time it is said.
            voice = voice_effects.shaped(samples, rate, profile, seed=zlib.crc32(text.encode("utf-8")))
            sound = pygame.mixer.Sound(buffer=voice_effects.as_pcm(voice, rate, mixer[0], mixer[2]))
        except (OSError, ValueError, EOFError, pygame.error) as error:
            logger.warning("A line could not be said: %s", error)
            return None
        sound.set_volume(VOLUME)
        self._sounds[key] = sound
        while len(self._sounds) > KEPT_SOUNDS:
            self._sounds.popitem(last=False)
        return sound
