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
| `es_ES-sharvard-medium` | a man and a woman, from Spain | CC BY 3.0 (Sharvard corpus, University of Edinburgh) |
| `es_ES-davefx-medium` | a man, from Spain | CC0 |
| `es_AR-daniela-high` | a woman, from Argentina | CC BY-SA 4.0 (OpenSLR 61) |
| `es_MX-ald-medium` | a man, from Mexico | Unlicense |
| `es_MX-claude-high` | a woman, from Mexico | Apache 2.0 |
| `de_DE-thorsten-medium` | a German man | CC0 |
| `de_DE-kerstin-low` | a German woman | CC0 |
| `fr_FR-upmc-medium` | a French woman and a French man | CC BY-SA 4.0 (UPMC, MaryTTS) |
| `en_US-joe-medium` | an American man | CC0 |
| `en_US-kristin-medium` | an American woman | public domain (LibriVox) |

They come to about 680 MB. The German, French and American ones read Spanish by the rules of
their own language, which is what gives them their accent: they are voices for people from far
away, not for being understood word for word. Some Piper voices are for non-commercial use only,
such as `en_US-ryan` and `en_US-hfc_male`; none of these is.

Any other Piper voice works: put its two files in `models/` and name it under `models` in
`data/voices.json`. To do with fewer, take the ones you do not want out of that list before
running the tool: a voice whose model is not there is simply not heard.

## A resident's voice

`Voz` in the menu, or `F3`, opens the editor on whoever is selected. A voice is a model that
speaks and a figure for each control, and that is all a file in `residents/` holds:

```json
{"model": "mujer", "pitch": 1.5, "speed": 1.05, "tremble": 0.0, "growl": 0.0, "robot": 0.0, "garble": 0.0}
```

A resident without a file has the voice `data/voices.json` gives them under `residents`, or else
its `default`.
