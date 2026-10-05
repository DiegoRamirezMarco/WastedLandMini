# Wasteland Minis

A post-apocalyptic social simulation built with Python + Pygame. A handful of survivors live in an
open-air settlement of shacks and makeshift premises, each with a job to do: they grow the food,
cook it, run the cantina and keep watch. The player watches, advises and intervenes, but does not
control them.

## Goals

- Top-down global view of the settlement for daily life and navigation.
- Residents with jobs, posts and shifts; places that only work while someone staffs them.
- Consequences that last: injuries, a clinic, fights you can try to stop, and death.
- Close-up interaction view for important conversations and crises.
- Pixel art: simple bodies with modular faces or optional custom PNG faces.
- Autonomous residents with needs, personalities, memories and directional relationships.
- Player influence rather than direct control.
- Data-driven items, food, maps and moddable custom content.

Progress and next steps are in `docs/roadmap.md`.

## Quick start

```bash
python -m venv .venv
# Windows
.venv\\Scripts\\activate
# Linux/macOS
source .venv/bin/activate

pip install -r requirements.txt
python main.py
```

Run the tests:

```bash
python -m unittest discover -s tests
```

Run the simulation without a window and print what happened:

```bash
python -m simulation.headless --days 7 --seed 7
```

## Controls

- Arrow keys or `WASD`, or drag with the right mouse button: move the view over the settlement
- Mouse wheel, `+` / `-`, or the `-` `+` buttons at the top: zoom. Zoomed all the way out the
  whole settlement fits on screen, buildings have their roof on and residents are shown as faces
- `C`: centre the view on the selected resident
- `Space`: pause / resume
- `1` `2` `3`: game speed x1, x4, x16
- `L`: open or close the event log
- Click a resident to see their needs, what they carry, what they are doing and how they feel
  about the others. Click a pantry or a crate to see what is inside and whose it is
- The pause, speed, zoom and log buttons at the top can also be clicked
- When a resident is at breaking point a `!` appears over them. Click them or press `Tab` to hear
  them out, then press `1`-`4` or click to give advice. Time stops while you decide; if you never
  answer, they make up their own mind after a while
- `Tab` again returns to the settlement
- `F5` saves the game to `saves/quicksave.json`; `F9` loads it
- `M`: sound on / off
- `Esc`: quit

## Art

`python -m tools.make_art` generates any missing starter image or sound under `assets/`. It never
overwrites an existing file, so anything edited by hand is safe. The rules for sizes, palette and naming are in
`docs/visual-style.md`.

## Custom content

See `docs/modding.md` and the examples in `custom_content/`.
