# Audio Rules
- Audio reacts to simulation events but does not drive gameplay state.
- Voice profiles store pitch/speed/formant/expression metadata, not generated audio blobs in save state.
- TTS/modulation must be optional so headless simulation remains functional.
