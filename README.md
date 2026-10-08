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
- Politics: no government until there are three; six kinds of government as data, chosen by
  the residents with the player's one proposal; leaders who are residents with a role, and who
  are followed when they die, resign or lose a vote; what each resident holds about it; and
  seven measures of the settlement. The player proposes and the settlement decides: laws,
  elections, another government, throwing somebody out. Each resident votes by their own
  mind, keeps a law or does not, and proposes things of their own.
- Families: a calendar, birthdays and old age; sex, gender and who each is drawn to; couples
  that marry; children carried, born, seen to and grown; kin by blood and by adoption; and
  families that come to the gate together.
- Substances: drink, smoke, pills, powder and the needle, each with the good it does, the harm
  of its own and what others make of it; dependence that comes by chance, is the worse for
  going without and passes; and a say for the player when someone starts or goes back.
- A common fund, and a say in what things are paid with: a settlement starts on barter, takes
  up a currency the player names if its residents will have it, pays its wages out of the fund
  and takes back at the counter what it paid. Caravans stop to trade, and credit can be stolen.
- Consequences that last: injuries, a clinic, fights you can try to stop, a limb lost for good
  to a blade, and death.
- Things to work out: somebody at a study desk spends their shift on what the player has
  chosen, which opens up the workshop, the generator, the clinic and the rest, or makes the
  garden, the water, building and trips outside go better.
- Building that is proposed and not ordered: somebody agrees to put a thing up, or does not,
  and it goes up in spare time out of scrap carried to the site.
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

The game opens on a menu. `Partida nueva` starts on an empty plot and leads through settling it,
step by step. Nothing there comes ready made: the first resident is named and then drawn, with
the game teaching how, and so are the shack, the bed, the crate and the rest as they are put
down. Then come food, water, a garden, a job, a fire, and the first stranger at the gate.
`Asentamiento de ejemplo` opens a settlement that is already running, with nine residents.
`Continuar` goes on with whatever was last saved.

Run the tests:

```bash
python -m unittest discover -s tests
```

Voices are optional. To hear the residents speak, each in a voice of their own:

```bash
pip install -r requirements-voices.txt
python -m tools.make_voices
```

The second line fetches ten voice models, about 680 MB, and has them speak every written line:
it takes a quarter of an hour. `voices/README.md` says what goes where, and how to do with fewer.

Run the simulation without a window and print what happened:

```bash
python -m simulation.headless --days 7 --seed 7
```

## Controls

- Arrow keys or `WASD`, or drag the map with either mouse button: move the view over the settlement
- Selecting a resident makes the view follow them wherever they go, until you move it yourself
- Mouse wheel, `+` / `-`, or the `-` `+` buttons at the top: zoom. Zoomed all the way out the
  whole settlement fits on screen, buildings have their roof on and residents are shown as faces
- `C`: centre the view on the selected resident, and follow them again
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
- A building is always shut from the map. Whoever is in it shows as a face on its roof, with
  what they are doing over it: talking, eating, asleep, at work. To see more, go in. `T` takes
  every roof off, or puts them back
- Inside a building, `Casa` opens the board on it: press a name to say the building is theirs,
  or no longer is. A bed under a roof is for whoever lives there, and whoever has no house
  sleeps in the open. `Echar llave` shuts everybody else out, `Nombre` gives it a name and
  `Uso` says what it is for. The four bars are what it is like to live in
- `Decorar`, inside a building, opens a catalogue of pictures. An `Adorno` goes down where you
  press, on the floor or on the back wall, at once and for nothing; a `Mueble` is put to
  whoever is selected, or whoever lives there, to make; `Suelo` and `Pared` change what the
  room is made of. `Quitar` takes an ornament away, and the right button puts down what is
  in hand
- Click the sign of a building, or press `I` with the pointer on it, to go inside: the room is
  seen with its back wall face on and its floor from a little above, as a grid, with whoever
  is in it. `Salir` or `I` goes back out. It is a first try of the look: nothing can be
  placed in there yet
- Everything the game shows of the settlement it draws itself, in thick lines and flat colour:
  the ground, the buildings, the furniture, what is carried, and whoever nobody has drawn.
  Whatever you draw in the editors takes its place on the map
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
- `Voz` in the menu, or `F3`: give the selected resident a voice. Choose who speaks and a kind
  of voice (young, old, child, monster, robot, or past understanding), then move the sliders:
  tone, speed, tremble, roughness, metal and scramble. Letting go of a slider says a line in
  the voice as it stands. `Guardar` keeps it; `Esc` goes back without
- `Maneras` in a resident's panel, or `F6`: choose how they walk, eat, fight, shoot and use a
  knife, three ways of each, with the one picked seen moving beside them. It changes how they
  look doing it and nothing else, and is theirs as soon as it is picked. `Esc` goes back
- `Dibujar` in the menu, or `F2`: draw the selected resident. Paint their body and their head
  over the guide, watch them move as you go, and save: from then on that is how they look, in the
  settlement and in their portrait. `Esc` goes back without saving
- In every drawing screen: a brush, a rubber and a bucket; a straight line, a box, an oval and a
  polygon, hollow or filled, laid down in one go (a polygon corner by corner, closed with a right
  click, `Enter` or a click on its first corner); the ready colours, and under them a field to
  pick any other from. `Ctrl+Z` undoes, and `Esc` lets go of a shape half made
- `Edificios` in the menu, or `F4`: draw a roofed place in four aligned parts: its empty
  interior, walls, roof and door. The preview exchanges the roof for the inside; `Guardar` writes
  the four PNGs under `illustrations/buildings/`. `Esc` goes back without saving
- `Urbanismo` in the menu, or `U`: add buildings, furniture and scenery by dragging them out of
  the catalogue onto the map, and move anything already placed by dragging it. The catalogue
  is a grid of pictures: rest the pointer on one for its name and what it takes, and what
  nobody knows how to make yet is last, dimmed, under `Bloqueados`. The outline under
  the pointer is green where it fits and red where it does not; a click on the map sets down
  another of the last thing taken, and a right click puts it away. Click something placed to
  remove it after confirmation, or press `Arte` to draw it: a building in its four parts, a piece
  of furniture once for all of its kind. Time stops while the
  editor is open and the changed layout is part of the save
- Once the opening of a new settlement is over, most of what is in the catalogue has to be
  built: drop it where it is to go, and the residents are listed for you to choose who to
  propose it to. They may say no, and somebody else can be asked. Whoever agrees builds it in
  their spare time, with scrap carried to the site, and others lend a hand. A site shows how
  far along it is; click it to see what it waits for, or to give it up
- `Estudio` in the menu, or `E`: what the settlement knows, what it is working out and what
  is left. `Estudiar` beside a subject takes it in hand, and `Dejar` puts it down; somebody
  has to hold the post of `Estudio`, at a study desk, for anything to come of it
- When a caravan comes, the caravaneer stands by the gate with his cart from morning until
  night. Click him to deal: `+` and `-` beside what he brings and what the settlement has
  that is nobody's, and `Cerrar trato` to buy and sell out of the fund in one go. `Dibujarle`
  and `Dibujar carro` there open their drawings
- `Gobierno` in the menu, or `P`: how the settlement is governed, who holds its seats, how
  things stand as seven bars, and the laws in force. `Elegir` beside a kind, and then
  `Confirmar`, gives the settlement that kind of government: it starts as legitimate as the
  number of residents who wanted it, and changing it later shakes the place
- `Guardar` in the menu, or `F5`, saves the game to `saves/quicksave.json`; `F9` loads it
- `M`: sound on / off, voices and all
- `Esc`: back to the menu, where the settlement waits; `Salir` there leaves the game

## Art

`python -m tools.make_art` generates any missing starter image or sound under `assets/`. It never
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
Every built-in item can be overridden there too: its icon, displayed name, article, category,
description, value, tags, effects and gameplay properties all remain keyed by the same stable ID.
Select a resident or a piece of storage furniture and click an item in its inventory to edit all
of those fields and draw its icon without leaving the game. Saving creates the same mod files.
Furniture and map objects follow the same rule under `custom_content/objects/<kind>/`: their
sprite, name, footprint, blocking, storage, light and complete use behaviour can all be patched.
