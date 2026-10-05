# Voices

What residents say in the dock is said out loud, each in their own voice. This folder is where
that is kept. All of it is optional: with nothing here the game is silent, as it was.

| Folder | What is in it | Kept in the repository |
| --- | --- | --- |
| `models/` | The voice models that speak: an `.onnx` file and its `.onnx.json` each | No, they are 60 to 80 MB each |
| `cache/` | Every line a model has spoken, as a WAV, so that it is spoken once | No, it is made again when needed |
| `residents/` | The voice chosen for a resident, as `<resident_id>.json` | Yes |

## Getting them

Voices are spoken by [Piper](https://github.com/OHF-Voice/piper1-gpl), which the game runs as a
program of its own. It is not part of the game and is under the GPL.

```bash
pip install piper-tts
python -m tools.make_voices
```

The second line fetches the models named in `data/voices.json` and has them speak every line
written in `data/dialogue.json`. The game does the same by itself for any line it has not heard,
the first time it is said, which takes a second or two.

The models the game comes set up for:

| Model | Speakers | Its recordings are under |
| --- | --- | --- |
| `es_ES-sharvard-medium` | a man and a woman | CC BY 3.0 (Sharvard corpus, University of Edinburgh) |
| `es_ES-davefx-medium` | a man | CC0 |

Any other Piper voice works: put its two files in `models/` and name it under `models` in
`data/voices.json`.

## A resident's voice

`Voz` in the menu, or `F3`, opens the editor on whoever is selected. A voice is a model that
speaks and a figure for each control, and that is all a file in `residents/` holds:

```json
{"model": "mujer", "pitch": 1.5, "speed": 1.05, "tremble": 0.0, "growl": 0.0, "robot": 0.0, "garble": 0.0}
```

A resident without a file has the voice `data/voices.json` gives them under `residents`, or else
its `default`.
