# Audio Rules
- Audio reacts to simulation events but does not drive gameplay state.
- A voice is a profile: a model and a figure for each control. Profiles are kept as small files under `voices/residents/`; generated audio is never part of a saved game.
- Voices must be optional: without Piper, a model, numpy or a mixer the game is silent and nothing else changes. Headless simulation never imports them.
- Piper is run as a program of its own, never imported: it is under the GPL.
- `voice_system.py` is plain data and needs only the standard library. Only `voice_effects.py` may need numpy, and only `voice_player.py` pygame.
