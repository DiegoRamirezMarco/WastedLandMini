# Wasteland Minis

A post-apocalyptic social simulation built with Python + Pygame. A handful of survivors live in an
open-air settlement of shacks and makeshift premises, each with a job to do: they grow the food,
carry it in, cook it, run the cantina, the shop and the workshop, and keep watch. The player
watches, advises and intervenes, but does not control them.

## Goals

- Top-down global view of the settlement for daily life and navigation.
- Residents with jobs, posts, shifts and days off; places that only work while someone staffs them.
- A working economy: what is made is carried to where it is used, tools wear out and are mended,
  work earns credits and credits buy things, and a post left empty is taken up by someone else.
- Consequences that last: injuries, a clinic, fights you can try to stop, a limb lost for good
  to a blade, and death.
- A world beyond the fence: someone goes out to scavenge, is gone for hours, and comes back with
  what stocks the shop and mends the tools, or comes back hurt.
- A world that does not leave it alone: strangers who ask to stay, caravans, dust storms to take
  shelter from, vermin in the pantry, and raiders by night for whoever is on watch to face. A radio gives word of some of it, to whoever listens and whoever they tell.
- Relationships that deepen: friendships, adults who fall for each other and say so or do not
  dare, couples, affairs kept secret until someone finds out, jealousy and breakups.
- Day and night over a place that looks salvaged: fires in barrels, lamps by the doors, wrecks
  and scrap. What happens in the dark, away from them, is seen by almost nobody.
- Close-up interaction view for important conversations and crises.
- Pixel art: bodies drawn over a skeleton, which reel from a blow, fall when they die and can
  lose a limb for good, with modular faces or optional custom PNG faces.
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
- `G`: go to whoever needs attention: someone waiting for advice, in the middle of something
  serious, or hurt. Press it again for the next one
- The screen is the map with a bar on top, a menu on the left, a panel on the right and a dock
  underneath. The menu opens the job board, the stores (what is everyone's, added up) and the
  log, puts the minimap away, and goes back to the list of residents
- The minimap in the corner shows everyone as a dot, blinking if they need attention. Click it
  to go there. `N` puts it away, or brings it back
- Whoever is outside the settlement waits as a face in the top left corner; click it to select
  them. What the residents have heard is coming is listed there too, with how many know
- With a resident selected, a heart marks their partner and a star those they hold as friends
- A building keeps its roof on until you rest the mouse on it or select someone or something
  inside. Whoever is under a roof shows as a face on it. `T` takes every roof off, or puts them
  back
- `Space`: pause / resume
- `1` `2` `3`: game speed x1, x4, x16
- `L`: open or close the event log
- `J`: open or close the job board: who holds each post and which stand empty. With a resident
  selected, `Proponer` beside a post puts it to them. They may say no, and cannot be pressed
  again for a while
- With nobody selected the panel on the right lists everybody: click a name to go to them. So
  does a click on anyone listed under a resident's relationships
- While whoever is selected is talking with someone, the dock under the map shows the two of them
- Click a resident to see their needs, their credits, what they carry, what they are doing and
  how they feel about the others. Click a pantry or a crate to see what is inside and whose it is, or the shop's
  counter to see what is on sale and at what price
- The pause, speed and zoom buttons at the top can also be clicked
- When a resident is at breaking point, is asked to take a post nobody is doing, or has a matter
  of the heart to settle, a `!` appears over them. Someone outside the settlement who comes on a
  risky find is not on the map: the line at the top says who is asking, and `Tab` opens it. Click them or press `Tab` to hear them out, then press `1`-`4` or click to give
  advice. Time stops while you decide; if you never answer, they make up their own mind after a
  while
- `Tab` again returns to the settlement
- `Dibujar` in the menu, or `F2`: draw the selected resident. Paint their body and their head
  over the guide, watch them move as you go, and save: from then on that is how they look, in the
  settlement and in their portrait. `Esc` goes back without saving
- `F5` saves the game to `saves/quicksave.json`; `F9` loads it
- `M`: sound and music on / off
- `Esc`: quit

## Art

`python -m tools.make_art` generates any missing starter image, sound or music track under `assets/`. It never
overwrites an existing file, so anything edited by hand is safe. The rules for sizes, palette and naming are in
`docs/visual-style.md`.

Residents' bodies are drawn over a skeleton. To try it away from the game, with blows, falls and
limbs coming off at a key press:

```bash
python -m tools.skeleton_lab
```

## Custom content

Illustrations made outside the game go in `illustrations/`: the ground of the map, buildings,
faces and the skin of the panels. They are shown at the full resolution of the window, in place of
the game's own pixel art. `illustrations/README.md` lists the files and how to frame them, and
`python -m tools.art.buildings` gives the proportions of each building.

See `docs/modding.md` and the examples in `custom_content/`.
