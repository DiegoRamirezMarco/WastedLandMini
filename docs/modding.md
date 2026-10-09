# Modding / Custom Content

Each new or modified item or food lives in its own directory. The folder name and stable `id`
decide which item it is:

```text
custom_content/foods/my_food/
    data.json
    icon.png
```

Minimal `data.json`:

```json
{
  "id": "my_food",
  "name": "bocata nuclear",
  "article": "un",
  "category": "food"
}
```

Optional fields include `description`, `base_value`, `tags`, `preference_tags` and `effects`.
`effects` maps a need (`hunger`, `thirst`, `tiredness`, `social`, `stress`) to the change from
using or eating the item.

`properties` holds other numbers about the item: `wear` and `damage`, and `sickens`, the chance
from 0 to 1 that eating or drinking it makes someone ill. Whoever it does turns against it, and
against what it tastes of.

`tags` and `preference_tags` are two different things:

- `tags` are what the game works by: `food`, `weapon`, `radio`, `custom`. They never make anyone
  like or dislike the item.
- `preference_tags` are what there is to like or loathe about it: `sweet`, `salty`, `slimy`,
  `cute`. Residents have tastes for these, and react to the item by them.

There is no list of taste tags. Use the ones the game's own items have (see `data/items.json`
and the names in `data/tastes.json`) or make up your own: the first time a resident meets
`alien` or `crunchy` they come to like or loathe it, each in their own way, and it is kept in
the save. They are written in lower case with underscores (`very_spicy`, `old_world`); capitals,
spaces and hyphens are put right, duplicates are dropped, and anything else is refused.

```json
{
  "id": "sopa_algas",
  "name": "sopa de algas fosforescentes",
  "article": "una",
  "category": "food",
  "tags": ["food", "custom"],
  "preference_tags": ["salty", "seafood", "radioactive", "slimy"],
  "effects": {"hunger": -30}
}
```

Every built-in item can be modified in exactly the same place. For an existing ID, `data.json` is
a partial patch: omitted fields keep their built-in value. This changes only the name and value of
the canned beans, for example, while preserving their article, category, tags and effects:

```text
custom_content/items/canned_beans/
    data.json
    icon.png
```

```json
{
  "id": "canned_beans",
  "name": "lata misteriosa",
  "base_value": 14
}
```

`icon.png` replaces the built-in drawing when the IDs match. To replace only the drawing, keep a
minimal `data.json` containing just `{"id": "canned_beans"}`. The editable definition fields are
`name`, `article`, `category`, `description`, `base_value`, `tags`, `preference_tags`, `effects`
and `properties`.
Lists and mappings supplied by a patch replace that whole field; omitted fields are inherited.

The same files can be made from inside the game. Select a resident or a container placed on the
map, then click an object in the inventory panel. Its editor changes every field above and its
icon; `effects` and `properties` use comma-separated `name=number` pairs. Saving writes
`custom_content/items/<id>/data.json` and `icon.png` and refreshes every occurrence immediately.
The stable ID is deliberately read-only, so existing inventories and saved games keep referring
to the same object.

Packs are loaded at start-up through the same registry as built-in items. A pack is skipped, with
a warning in the log and without stopping the game, if:

- `data.json` is missing, is not valid JSON, is not an object or is larger than 64 KB;
- `id` is not lowercase letters, digits and single underscores, or differs from the folder name;
- `name`, `article` or `category` is missing or empty for a new item, or a food's effective
  `category` is not `food`;
- `base_value` is negative, `tags` is not a list of strings, or `effects` has non-numeric values;
- `preference_tags` is not a list of strings, or one of them cannot be written as lowercase
  letters, digits and single underscores;
- the same `id` has already been modified by an earlier pack. A built-in ID itself is allowed and
  means that the pack modifies it.

Fields the game does not know are ignored, so a pack made for a newer version still loads.
Removing a pack never breaks a save: its items stay as inert unknown objects, and the tastes
residents had for them and for their taste tags are kept, in case it comes back.

`icon.png` is 16×16 in lists and inventories; any other size is scaled down to it there. In a
resident's hand it is shown from the file as it is, so one drawn larger, as the in-game editor's
64×64 are, is seen in more detail there. A new item without an icon shows
the magenta checker placeholder; a modified built-in item without one keeps its original drawing.
Face PNGs must be 64×64. See `docs/visual-style.md` for the art rules and palette.

Use stable lowercase IDs with underscores. Display names may contain spaces and accents. Gameplay must use IDs/tags/categories, never the display name.

## Maps, terrain and objects

Maps and terrain live in `data/` for now. Furniture and other kinds of object placed by those maps
can be modified under `custom_content/objects/` with the same stable-ID patch model as items:

```text
custom_content/objects/bed/
    data.json
    sprite.png
```

A minimal patch can change only the displayed name:

```json
{
  "id": "bed",
  "name": "catre remendado"
}
```

Editable fields are `name`, `article`, `width`, `height`, `blocks`, `container`, `display_of`,
`light`, `category`, `seat`, `use`, `uses` and `build`. Whatever else a kind has, what it gives
taken apart, the current it draws, what it stores, is kept as it was. `category` is `furniture` or `decor` and decides where the kind
appears in the Urbanismo catalogue. A `use` object is itself patched field by field, so
`{"id":"bed", "use":{"minutes":480}}` keeps the sleeping action and changes only its duration.
Set `"use": null` to remove the use entirely. `uses` is a list of whatever else can be done
with the thing (S60), each written as a `use` with an `action` of its own and a `label`, which
is what it is called where it is offered: a pack that gives one replaces the whole list. Every placed object of that kind receives the
modified definition; object instances and saved games continue to store only their stable IDs.

`build` says what putting one up takes: `{"cost": {"scrap": 2}, "minutes": 60, "job": "mechanic"}`.
`cost` is units by the tag of the items that will do, `minutes` the work once they are there, and
`job` the job whoever does that work has to hold; all three are optional, and `build` is patched
field by field like `use`. A kind with no `build`, or with `"build": null`, is put down at once
and for nothing. A cost in a tag that no item carries, or a job that does not exist, is refused.
`data/construction.json` holds what is the same for everything: how much is carried in a trip,
how long somebody works before looking up, how many hands fit on a site, and how keen people are.

`sprite.png` replaces `assets/sprites/objects/<id>.png`. Each animation frame is `width × 16`
pixels wide, frames are laid side by side, and the picture must be at least `height × 16` pixels
high. It may be taller so that lamps, shelves and other upright objects rise above their footprint.
To replace only the drawing, use a minimal `data.json` containing the ID. Invalid or oversized
data is skipped without stopping the game, and missing custom art falls back to the built-in sprite.

A map (`data/maps/<id>.json`) is drawn with characters, one per tile:

```json
{
  "id": "my_camp",
  "legend": {".": "dirt", "#": "wall", "=": "floor_wood", "+": "door"},
  "rows": [
    "#####",
    "#===#",
    "##+##",
    "....."
  ],
  "rooms": [{"id": "hut", "name": "cabaña", "x": 1, "y": 1, "width": 3, "height": 1, "privacy": 0.5}],
  "objects": [{"id": "bed_1", "kind": "bed", "x": 1, "y": 1}],
  "spawns": [[2, 3]]
}
```

- Every row must have the same length, and every character must be in the legend.
- Legend values are terrain IDs from `data/terrain.json`; `kind` values are object kinds from
  `data/interactables.json` or `custom_content/objects/`. Unknown IDs are rejected when the game
  loads its data.
- Spawns must be on walkable terrain.
- A room with `"roofed": true` is a building: seen from afar it is drawn with its roof on. Its
  rectangle is the floor inside, with walls one tile thick around it and the door in the wall
  below. Leave it out for open places such as a yard or a garden.
- `stock` lists what containers hold at the start and `supplies` what arrives each day:
  `{"container": "pantry_1", "item": "canned_beans", "count": 8, "hour": 7}`. The container must be
  an object whose kind is marked `"container": true`. An item that is not defined is left out.
- Terrain is drawn with the tile of the same name in the tileset; a terrain without a tile shows
  the placeholder. An object kind uses `custom_content/objects/<kind>/sprite.png` when present,
  otherwise `assets/sprites/objects/<kind>.png`.
- `"light": 5` on an object kind makes it light that many tiles around it after dark. The built-in
  `lamp` kind needs generator fuel to shine; fires and other light kinds do not. A kind with no
  `use` is scenery; give it `"blocks": false` if it can be walked over.
- `"seat": true` makes a kind something to sit on, as the built-in `stool` is: it has to take up
  one tile and be walked over. Whoever goes to do something done sitting down (see Manners)
  takes a free seat that stands beside what they use, before the nearest bare ground, and is
  seen sitting on it for as long as they are at it. A seat is whoever's stands on its tile: two
  cannot, and nothing of it is kept in a save.
- A use with `"consumes": "water"` takes one shared item from the object's own container, just as
  food uses do. The built-in water tank is a container and consumes items in category `water`.

## Health and weapons

- `data/injuries.json` defines kinds of injury: `name`, `heal_per_day` and `treated_per_day`.
  With `severs_from` and `severs_chance`, a single injury of that kind at least that severe takes
  a limb off with that chance, from 0 to 1. With `from_need` and `worsens_per_day`, it is what
  comes of that need being left at its worst, and grows that fast while it is.
- `data/body.json` lists under `limbs` what can be lost: a `name` with its article, as it reads
  after a verb, and what is left of the pace of work and of walking without it (`work_pace`,
  `walk_pace`, above 0 and up to 1). A limb ID must be a part of the body in `data/skeleton.json`
  to be seen coming off. Without the file nobody loses anything.
- An item is a weapon if its `properties` give it a `damage` multiplier, e.g. `{"damage": 1.8}`.
  The tag `blade` makes the wounds it leaves cuts. `blade` and `firearm` also say in which of
  their manners whoever carries it fights (see Manners).
- An object's use heals with `"heals": true`; `"care_job"` names the job whose worker on duty
  makes it heal at the treated rate. With `"care_item"` (an item tag), `"care_from"` (a
  container kind) and `"dose_minutes"`, that care uses up one unit of such an item from such a
  container for every `dose_minutes` someone is under it, and without one it is only rest.
- An exchange in `data/social.json` is a fight if it has a `damage` range, e.g. `[8, 18]`.
- A map's `graves` lists the tiles where the dead are buried, in the order they are used.

## The opening of a new settlement

`data/tutorial.json` names the `map` a new settlement starts on and lists its `steps`, in order.
A step has an `id`, a `title`, a `text`, and a `goal`:

| `goal.type` | Done when | Other fields |
|---|---|---|
| `residents` | that many people live there | `count` |
| `building` | that many roofed buildings stand | `count`, `target` (a blueprint ID; any if left out) |
| `object` | that many objects of a kind stand | `target` (the kind), `count`, `indoors` |
| `job` | that many residents hold a job | `count`, `target` (a job ID; any if left out) |
| `elapsed` | that many game minutes have gone by since the step began | `minutes` |
| `answered` | whatever the step's `opening` set going has been settled | |
| `acknowledged` | the player presses the step's button | |
| `deed` | the player has done the thing named | `target` (the name) |

Any goal may also carry a `deed`, to be done besides: `{"type": "object", "target": "bed", "deed":
"draw:bed"}` is done once a bed stands and has been drawn. The names the game reports are `color`,
`stroke`, `fill` and `undo` from any drawing screen, `part` and `save_building` from the one for
buildings, `save_resident` from the one for residents, and `draw:<kind>` when an object's drawing
is saved.

Optional: `gifts`, each an `item` and a `count` with either `into` (a kind of container, where it
is left as nobody's) or `"to": "resident"` (given to whoever has been there longest, as their
own); `opening`, which is `stranger` to bring someone to the gate; `done`, the line logged when
the step is finished; `focus`, which names what the step is about so the screen can point at
it: `creator`, `doll`, `building_art`, `urbanism`, `jobs`, `research`, `save` or `clock`; and `hint`, what
inside a drawing screen it is about: `palette`, `canvas`, `tools`, `edit`, `parts` or `save`.

The map, the kinds, blueprints and jobs a goal names, and the containers gifts go into are
checked when the game starts. A gift of an item that is not defined is left out.

## Research

`data/research.json` lists what there is to work out, under `subjects`, by ID:

```json
"radio": {
  "name": "Radio",
  "text": "Hay que abrir una radio vieja para entender cómo se hace una que alcance lejos.",
  "minutes": 480,
  "requires": ["electricity"],
  "needs": {"item": "old_radio", "count": 1},
  "opens": {"objects": ["radio_set"]}
}
```

- `minutes` is time on shift at the post. `requires` names the subjects that come first; they
  may not lead back round to each other.
- `needs` is an item that is studied and used up, by item ID. Whoever holds the post fetches it.
- `opens` lists the object kinds and the building blueprints that cannot be put up until the
  subject is known. Whatever no subject opens can be put up from the start.
- `effects` are factors on figures of the simulation: `build_pace`, `expedition_danger`,
  `expedition_finds`, `dose_minutes`, and `pace:<job ID>` for what a job turns out. The factors
  of every subject known are multiplied together.
- A job with `"research": true` in `data/jobs.json` is one whose time at the post goes towards
  the subject in hand. Its `station` has to be a kind of container, to hold what is studied.

A subject that names an item, a kind, a blueprint, a job or an effect that does not exist is
refused when the game starts.

## Buildings

Urbanismo gets its built-in building blueprints from `data/urbanism.json`. A content pack can add
one with `custom_content/buildings/<id>/data.json`; it uses `id`, display `name`, interior `width`
and `height`, `floor`, and optional `privacy` and `build` (as for objects, above). Put its art in `sprite.png` in the same folder. If
art is absent, the game supplies a procedural wasteland building that can then be opened in the
building art editor.

Every roofed room of a map is drawn, while its roof is on, as one picture. To give a building a
look of your own, put a PNG named after the room's ID in `custom_content/buildings/`, for example
`custom_content/buildings/cantina.png`. It needs no particular size or palette: the game brings it
to the size of the building. Draw it as seen from the open ground in front, roof at the top and
the front wall along the bottom.

```bash
python -m tools.art.buildings
```

lists every building with the size its picture is shown at and where its door is, so that the door
of the picture can be put where residents walk in. A building's picture is as wide as the room
plus a wall on each side, and as tall as the room plus the walls behind and in front, plus one
tile of headroom, at 16 pixels a tile.

## Bodies

`data/skeleton.json` is the body every resident has. Distances are in art pixels from the spot
between the feet, with `y` growing downwards. Angles are in degrees.

- `joints`: each with a `mass` (the heavier, the less a blow moves it) and a `radius` (how far
  above the ground it comes to rest).
- `bones`: each a pair of joints, listed from `root` outwards, so that every bone starts at a
  joint that an earlier one already reached.
- `braces`: pairs of joints kept a fixed distance apart without a bone, which is what keeps the
  trunk in shape.
- `parts`: the bone each part hangs from. Cutting that bone loose takes it and everything beyond
  it off. A limb in `data/body.json` is seen coming off only if it is a part here.
- `limits`: how far a bone may turn against another (`ref`), from the `side` and from the
  `front`. From the side a positive angle is towards where the body faces. From the front it is
  away from the middle of the body for a bone with a side. `ref_reversed` measures against the
  other bone pointing the other way, as for a limb that hangs from the trunk.
- `follows`: a bone that turns with another whenever a clip turns that one and says nothing of
  its own, as a hand with its forearm. A bone that follows nothing keeps the way it points at
  rest, as a foot stays level.
- `views`: where each joint is at rest, seen from the `front` and from the right `side`. A third,
  `doll`, is the build of a body drawn by hand: it is `like` the side view, which is to say it is
  posed by that view's clips and held by its limits, but has its own places for the joints. That
  is where a paper doll's limbs are made longer or shorter, and its shoulders and hips set
  forwards or back.
- `orders`: for the `front`, `side` and `back`, the bones from the furthest to the nearest, and
  for the `doll` the parts of a drawing in the same way.
- `skins`: what is drawn over a bone, a `sprite` or a `strip` from the parts sheet. A sprite's
  `anchor` is the `start`, `middle` or `end` of its bone.
- `clips`: for each view, a list of keyframes that are run through in a loop. A keyframe gives
  bones an angle from rest, or `[angle, scale]` to make one look shorter as well, and may shift
  the whole body with `root`. A positive angle swings a hanging limb to the right of the screen.
  The game uses `idle`; walking, eating, fighting and having words use whichever clip the
  resident's manner names (see Manners below), and work whichever `data/poses.json` names
  for it (see Work, as it is shown, below). A clip that is missing stands still. `carry`,
  arms held out for a load, is there for whoever wants it: the game lays it over nobody now.
- Beside its views a clip may say how something with a handle is held while it goes on, with
  `grip`. `"hands": 2` has the handle run from the palm of the hand of the far side through
  that of the near one, which is the nearer to its far end: where the two hands go, the
  thing goes, so keep them well apart. `"hands": 1`, or none said, has it come out of the
  palm of the near hand, turned by `turn` degrees from the way that hand points. `at` is how
  far along its handle the thing is held, by the one hand or by the far one of two, from 0
  at the end it is held by to 1. Where the hands are is for `anchors` to say (`held_item` and
  `held_wrist` for the one that holds, `other_item` and `other_wrist`): no code names a joint.
- The small bodies the game shows without a window do not bend their legs to go down. A pose
  that would have any of one under the ground it stands on leaves it standing on it.
- A clip goes through its keys in a curve, as fast into each as out of it, and round from the
  last to the first. Its keys are spaced evenly unless every one of them says when it comes
  with `at`, from 0 up to but not 1, each later than the one before: that is how a blow is
  held back and then let go all at once. Beside its views a clip may say `"once": true`:
  it is then done from its first key to its last, setting off and ending at rest, and does
  not come round (its last `at`, if it gives any, may be 1).
- `motion` is how loosely a body shown as a doll follows its clips. Each bone is drawn towards
  where its clip has it by a spring: `speed` is how fast it gets there, `bounce` how much it
  goes past and comes back, from 0 to under 1, and `drag` how far it is left behind by the
  swing of the bone it hangs from. `spring` is for any bone, `root` for the body as a whole,
  and `springs` gives a bone one of its own: stiff for legs, loose for hands and heads.
  `jolt` is the speed a body is given when it takes up something else: `root` in pixels a
  second, and under `bones` a turn in degrees a second and a length in lengths a second.
- `life` is what a body shown as a doll does of itself. `breath` names a clip laid over
  whatever else it is doing, and its `rate` in turns a second; everybody is somewhere else
  in theirs. `stand` names the clip a body with nothing to do and nothing in hand stands in,
  in place of `idle`. `fidgets` lists clips done once, now and then, by such a body: between
  one and the next go by from the first to the second of `every` seconds, and each is gone
  through at `rate` turns a second. A fidget should be a clip marked `once` that starts and
  ends standing. `idle` itself stays one pose: dolls are measured by it.
- **Work, as it is shown** (`data/poses.json`). None of it changes what happens: it is how
  what the simulation says is going on looks. `work` is the clip of any work and how many
  turns of it a second (`clip`, `rate`). `jobs` gives a job a look of its own: its `clip`
  and `rate` are for bare hands, and under `tool` those of whoever has the tool of the job
  on them and not broken, which is then seen in their hands. `build` is the same for
  building, and may name a `prop`: something seen in the hand that is no item of anybody's,
  drawn by `graphics/item_pictures.py` under that name. `handles` says, for an item or a
  prop by its ID, where the handle is on its picture, `from` the end it is held by `to` its
  far end in hundredths of the picture's side, and how `long` that is in a hand, in the
  skeleton's own measure. A thing with a handle, held in a clip that has a `grip`, turns
  with the hands; any other is shown flat in the hand, as a meal is. A picture drawn anew
  in the item editor is turned by the same handle: draw it along the same line. `pocket` is
  the clip a doll goes through once, over whatever else it is doing, when its resident has
  more on them or less than a moment before, and its `rate`: the bones that clip moves do as
  it says meanwhile and the rest go on as they were, so move one arm and little else. Leave
  it out and nothing is made of what goes into a pocket. `seat` is the clip of whoever sits
  on a seat, which is one pose as any way of sitting is, with the hips at the height of
  it: on a seat nobody sits their own way of sitting on the ground. Leave it out and they
  do. `sleep_rough` is how a doll that
  sleeps on the ground is shown, and needs all three of its parts: `down`, a clip done once
  from standing to lying; `asleep`, the clip of lying there; and `up`, done once from lying
  to standing. The last key of `down` and the first of `up` should be the pose of `asleep`.
  A body is laid down by turning every one of its bones: a bone a key does not name stays
  as it stands. Leave `sleep_rough` out and whoever sleeps on the ground is a blanket with a
  head at one end, as the small bodies are.
- However a pose has a doll, none of it is under the ground: where a joint would be, the whole
  body is that much higher. Lay a body down by the build every doll starts from, and one
  with longer limbs still lies on the ground and not in it.
- `footing` keeps feet on the ground. A clip moves the whole body with `root`; in the `views`
  listed, a foot of one of the `legs` (a bone and the one that hangs from it) that the clip
  has on the ground stays where it stands, and the knee bends to let the body go. A leg too
  short to reach is drawn out up to `stretch` times its length, and past that it is the body
  that comes down: a `root` that lifts it higher than its legs go does not take it off its
  feet. A foot the clip holds `free` pixels or more above the ground goes with the body, so
  a clip that means to leave the ground, as a jump does, lifts its feet by turning its legs.
  One held less than `hold` above the ground is on it, and not a hair over it. `level` is how
  far off the ground a foot has its sole kept flat to it, whichever way the clip turns the
  foot: ahead for one that stands, behind for one that kneels. From there up it is more and
  more as the clip has it, and twice as high wholly, as in a kick. Leave `hold` and `level`
  out and feet turn as their clips say. Only the `doll` view is posed so: the small bodies
  of the game bob whole.
- `doll`: how a body is drawn by hand. `unit` is the pixels of a drawing to one of the skeleton's;
  `canvases` gives the size of the body's and the head's in those units; and each entry of `parts`
  is a bone with the canvas it is drawn on and the two points it runs `from` and `to`. `radius`
  is half the width of the slim figure the guide shows. `reach` is half the width of the zone
  the part may be drawn in and `ends` how far that zone goes beyond each joint; give them room,
  so that people can draw other builds than the figure's. `shape` says what the part is on the
  plain figure the guide shows and whoever nobody has drawn is shown as: `neck`, `chest`,
  `pelvis`, `upper_arm`, `forearm`, `hand`, `thigh`, `shin`, `foot` or `head`; anything else is
  a plain rounded strip. `whole` is for a part that is everything on its canvas. Every other
  part is cut round at the joints it shares, but for
  `free_start`, a part that does not turn about its first joint, and `free_end`, one left as
  drawn at its second though another starts there, as the trunk at the shoulders. In the game a
  bone that a part is drawn for is as long as the part is on its paper, whatever the `doll` view
  says: of that view the game keeps where the bones between are, the ones that join a limb to
  the trunk, and how high the feet stand. Every part must have its turn in the `doll` order, and
  what is a part's own, its zone as far as the joints it is cut at, may only be on another's
  where the two share a joint. On the guide a limb of `doll.hoses` is one piece, and so is
  whatever else is joined together: lay the paper out so that no piece is on another.
- `doll.hoses` lists the limbs of rubber: for each, its parts from the trunk outwards, such as
  an upper arm, its forearm and its hand. They are kept in one piece, where other parts are
  pinned at a joint. The parts of one must be drawn one after the other on the same canvas,
  each starting where the one before ends, and no part may be in two. It is shown where the
  first of its parts comes in the `doll` order. The last part of a limb of three or more is
  its end, a hand or a foot: it keeps its shape, turns about the joint it hangs from and may be
  drawn pointing any way, as a foot sticks out of a leg. The parts before it bend along their
  bones as one curve, and must be drawn in one line. `doll.hose` says how: `round` is how much
  of the limb each bend takes up, from 0, where a joint is a corner, to 2, where the limb is
  one curve from end to end; `volume` is how much wider a limb gets for being shorter than it
  is at rest, and thinner for being longer, from 0, not at all, to 1, enough to take up the
  same room; `tip` is how much of a hand's or a foot's own length the limb gives, back from
  the joint, to go into it without a cut, and at 0 limbs have no such ends and every part
  bends. Leave `hoses` out and every part is pinned as before. Bending needs numpy; without it
  the game shows the parts.
- A doll's own measures are kept in `illustrations/dolls/<id>/build.json`, written by the
  editor: `joints` says how far each joint of the guide was moved along its part, in the
  skeleton's own measure, by part and end (`shin.end` is the ankle, `upper_arm.start` the
  shoulder, and a limb's start moves all of it); `points` how far a joint that goes anywhere was
  moved (`skull.start`, where a head sits on its neck); and `attach` how far from where the
  `doll` view has them the bones that join a limb on end (`clavicle`, `pelvis`). Names carry no
  side: both arms are one. Measures a doll cannot have are ignored whole.
- `doll.former` says how the paper was laid out before, each time it was changed, the latest
  first: one entry, or a list of them. Each tells how it differed from the layout that came
  after it: the size its `canvases` had, where each part that has since been moved used to run
  `from`, and under `zones` the `reach` and the `ends` of each part whose zone was another.
  A drawing of the size of one of them is taken apart as it was cut then and each part put
  where it goes now, with nothing of it drawn again or resized. A paper is told by its size,
  so a new layout needs a size no layout before it had. It should move every part by a whole
  number of drawing pixels and leave each all that was its own, its zone as far as the joints
  it is cut at: what was drawn then would otherwise be put down between two pixels, or cut
  off. To lay the paper out anew, put what `canvases` and the parts say today at the head of
  `former` and then change them.
- `doll.build`, in `data/skeleton.json`, is the same three tables: the measures every doll
  starts from. Whoever has not been drawn yet is given them, and `Medidas de partida` goes back
  to them. The `from` and `to` of the parts stay as they are under them: a drawing kept without
  a `build.json` was made before there were measures, and is still cut where those say.
- `physics`: gravity in pixels per second squared, how much speed is kept each step (`damping`),
  lost along the ground (`friction`) and given back on landing (`bounce`), how hard limits push
  back, and when a body that lies still goes to sleep.

A resident's look is `assets/sprites/bodies/<resident_id>.png`, laid out as in
`docs/visual-style.md`. One that is missing is drawn in placeholder parts.

## Manners

`data/manners.json` says in what ways a resident can walk, eat, fight, have words with
somebody and sit. Each resident has one
of each kind: chosen by the player where the first resident is made or under `Maneras`, and
otherwise one that is always the same for the same resident ID. A manner changes how a thing
looks and nothing of what happens.

- `kinds`: each with a `name` and the `occasion` on which it shows: `walk`, `eat`, `fight`,
  `argue` or `sit`. `argue` is any exchange with another resident that is `hostile` and does
  no `damage` (`data/social.json`): while it lasts bolts fly over the heads of both, whatever
  their manner of it. Sitting is no doing of its own: a kind of it lists under `actions` what a resident has
  to be at for it to show, such as `relax`, `listen`, `eat` or `drink`, the actions of the
  objects used. While they eat sitting, the clip of their way of sitting is the body's and
  that of their way of eating is laid over it: the bones an eating clip moves do as it says.
  A kind for fighting may have a `weapon_tag`: whoever fights with an item tagged so does it in
  their manner of that kind, and with any other weapon, or none, in their manner of the kind
  that has no `weapon_tag`. The game's own are `blade` for `knife` and `firearm` for `shoot`.
  `prop_tag` is the tag of an item to put in the hand of the figure that tries a manner out; it
  is the `weapon_tag` unless given.
- `manners`: each with its `kind`, a `name`, a `description`, the `clip` of
  `data/skeleton.json` that shows it, and a `rate`: turns of the clip a second, or for walking,
  turns to a step with each foot, which must be a whole number. The first manner of a kind is
  the one the screen that makes the first resident starts on.
- A way of sitting is one key, a pose: what moves in it is the breath. Let the hips down with
  `root` and turn the legs, for the feet are not kept on the ground under a body that sits;
  none of it will be under the ground, whoever's body it is. Seen from the front the small
  bodies of the game have no way of sitting, and a `front` of `[{}]` leaves them standing.
- A new manner needs its clip in `data/skeleton.json`, for the `side` and for the `front`. The
  hand that holds things is the right one (the `held_item` anchor): a clip for a weapon moves
  that arm. An eating clip has the hand at the mouth a third of the way through, which is when
  the bite is taken and the crumbs fly.
- Nothing in the game is tagged `firearm` yet. Give an item that tag and a `damage` and it is
  fired the way its owner shoots.

## Attributes

`data/attributes.json` holds the six things a resident is capable of, and what each does.

- `attributes` gives each of the six a `name`, a `short` of three letters and a `text`. There
  are six and they are these: a pack cannot add a seventh.
- `lowest`, `highest` and `middle` are the scale. `spread` is how far from the middle what
  somebody is born with may fall, `inherit` the share of a child's that is the middle of its
  parents', and `founder_points` what the first resident has to share out among the six.
- `effects` says what a point either side of the middle changes: `work_pace`, `fight_strength`,
  `fight_dodge`, `toughness`, `healing`, `tiredness`, `study`, `learning`, `finds` and `danger`
  as a share, and `carry` and `sight` as so many units or tiles a point.
- `practice` says what raises one: a minute of `work`, a `fight`, being `hurt`, a day to `lead`,
  a minute to `train` at a thing for it.
- `training` says how far a thing to train at takes an attribute: `cap` for a common one,
  and `per_level` more for each rarity past it.
- A kind of object in `data/interactables.json` is a thing to train at when its `use` has
  `"trains"` with the ID of one of the six. Give it a `label`, which is what putting somebody
  down on it says, and a `per_minute` that tires. To have it made better, and so teach
  further, name the kind under `upgrade.kinds` in `data/rarities.json`. `"category":
  "training"` puts it under `Entreno` in the catalogue of `Urbanismo`, beside `furniture`
  and `decor`.
- `age` (`from`, `per_year`, `of`), `youth` (`grown_at`, `floor`, `of`) and `injury` (`of`,
  `share`) say what the years, growing up and being hurt take from, and how much.

## Trades

`data/crafts.json` holds the levels of a job and the kinds of thing a job teaches.

- `levels` are the minutes at a job from which each level is reached, the first from 0. `pace`
  is how much faster each level makes the work, `better` how much better each level makes
  what is come to at it, `teach_minutes` and `teach_reach` how long and how near somebody has
  to be to learn a thing from whoever knows it, and `name_length` the longest name.
- `jobs` says which kind each job teaches, by job ID. A job left out teaches nothing.
- `kinds` lists them by ID, each with a `name`, what the player is asked (`ask`), how it is
  said of whoever comes to one (`learned`), and:
  - `item`, the item it is as the game makes it: `category`, `tags`, `value`, `effects`,
    `properties`, `preference_tags`, a `substance`, and `flavours` (how many of the tastes in
    `flavours` it is given). A pair of numbers is anywhere between them. Left out, it is not
    a thing: somewhere to go.
  - `choices`, what the player picks, by ID. Each has a `name` and either its `options`
    written out or a `source` they come from as things stand: `raw_food` or `making_jobs`.
    An option has a `name`, a `text`, and what picking it does: an `item` laid over the kind's
    (lists grow, the rest is written over), `every_minutes`, `batch` and `ripens_days` for how
    it is made, and `fetch` and `finds` for what is brought from a place.
  - `every_minutes` and `batch` for how a unit is made where no option says, and, for a job
    that makes nothing of its own, `into` (the kind of container what is made is kept in) and
    `max_stock` (how many of each the settlement keeps before no more are made).
- A choice called `from` names what a thing is made of, which has to be in the hands of
  whoever makes it. One called `for` names the job a tool is for, and tags it `tool_<job>`.
- The picture the player draws of a thing is kept in `custom_content/made/<item ID>/icon.png`.
  That folder is no pack: nothing in it defines an item.
- What a made item is good for is its data: `speed` on a tool, `dose` and `mends_<injury>` on
  a medicine, `armour`, and `damage` and `raid` on a weapon.

## Finds

`data/finds.json` is what turns up that nobody knows, and where from. Without the file
nothing ever does.

- `kinds` lists the kinds of thing there are to find, each written as a kind of
  `data/crafts.json` with an `item` and no `choices`: the game settles all of it, and the
  player gives it a name and a drawing. `ask` is what the player is told it is, and `weight`
  how often it turns up beside the others. A kind here cannot be called as one there.
- `sources` are the ways a thing comes in: `expedition`, `caravan`, `salvage` and
  `newcomer` are the ones the game asks at. Each has a `chance` from 0 to 1, how many
  `units` come as a pair of numbers, what is said when it turns up (`found`) and what is
  said of the thing ever after (`told`), both with `{name}` for whoever found it, and
  `keeps` where it is theirs and not the settlement's.
- `most_waiting` is how many may wait to be named before no more turn up, and `nobody` who is
  said to have found what nobody in particular did.

How a thing put in somebody's hands by the player is said to be taken is `lines.handed` in
`data/tastes.json`, by reaction, with `{name}` and `{thing}`.

## Jobs

`data/jobs.json` defines the settlement's posts:

```json
"cook": {
  "name": "Cocina",
  "station": "cooking_pot",
  "shifts": [[11, 14], [18, 21]],
  "text": "se pone a cocinar",
  "interruptible": true,
  "produces": {"item": "stew", "every_minutes": 15, "into": "station", "max_stock": 8,
               "from": "pantry", "from_category": "food", "skip_tag": "cooked"}
}
```

- `station` is an object kind from `data/interactables.json`; a resident's post is one object of it.
- `shifts` are hour ranges and may run past midnight, e.g. `[22, 6]`.
- `produces` is optional. `into` is `station` (the post itself, which must be a container) or a
  container kind the worker carries the produce to. `from` and `from_category` name the raw
  material and the container kind the worker fetches it from, if the work needs any. `carry` is
  how many units go in one trip, either way (6 unless set).
- `"supplies": {"item": "fuel", "into": "generator", "low": 4, "carry": 6}` has the worker keep
  a kind of container stocked with an item from wherever else in the settlement it is lying.
  They go for it when `carry` units are waiting in one place, or at once for whatever there is
  when the receiving container holds fewer than `low`, and never while someone is being served
  at their post. `max_stock` stops it (99 unless set). `into` must be a container kind.
- `per_minute` changes the worker's needs while on duty, and `sight_bonus` extends how far they see.
- `stat` names the attribute the work goes by (`strength`, `constitution`, `dexterity`, `mind`,
  `senses` or `charisma`): whoever has more of it does the job faster, and doing it raises it.
  Left out, anybody does it as well as anybody else.
- `"tool": {"tag": "hoe", "speed": 1.5}` makes the work that much faster for a worker carrying a
  working item with that tag. At least one item must have the tag.
- `wage` is credits per hour on duty, in place of the settlement's `wage_per_hour`.
- `needed` is how many residents the job takes (1 unless set); with fewer it has a vacancy.
  `priority` says how much it is missed: a vacancy is offered to those in jobs of lower priority.
- An object's use can require a job to be on duty with `"staffed_by": "bartender"`.
- `"also_at": ["well"]` on a job names other kinds of object it is worked at, each a post of
  it as its `station` is. `"post_pace": 0.6` on a kind of object in
  `data/interactables.json` has a post of that kind worked at six tenths of the pace of any other.
- A use may have a `label`: what it is called for short where it is offered by name, as
  when somebody is carried over the object (`Dormir`, `Comer`). Left out, it is `Usar`.

Which resident has which job, and which day of the week they have off, is set where the
settlement is created, in `SimulationWorld.demo_world`.

A job that is never to be pushed says `"rush": false`.

## Pushing a post

`data/work.json` says what telling somebody to push their post does, under `rush`:

```json
{
  "rush": {
    "pace": 1.5,
    "per_minute": {"tiredness": 0.07, "stress": 0.06},
    "risk": 0.05,
    "check_minutes": 30,
    "tired_from": 50,
    "tired_risk": 2.0,
    "level_relief": 0.1,
    "trust": -6,
    "mood": -6,
    "memory": "Me pasó algo por apretar en el trabajo.",
    "mishaps": {
      "hurt": {"weight": 4, "text": "{name} se hace daño apretando en su puesto: {job}",
               "injuries": {"bruise": {"weight": 5, "harm": [6, 14]}}},
      "tool": {"weight": 3, "text": "A {name} se le parte {thing} de tanto apretar"},
      "spoil": {"weight": 3, "text": "...", "fraction": 0.25, "most": 6}
    }
  }
}
```

- `pace` is how many times as fast they work, and `per_minute` what each minute of it adds to
  their needs. With a `pace` of 1, or no file, nobody can be pushed.
- `risk` is the chance that a unit turned out pushed ends badly, for somebody rested, in the
  middle of what the job goes by and at its first level. `tired_risk` is how many times as
  likely it is for somebody worn right out, from `tired_from` of tiredness up, and
  `level_relief` the share of it each level past the first takes off. `check_minutes` is how
  many minutes of work that turns out no units count as one.
- `mishaps` are the ways it can end badly, picked by `weight` among those that can happen:
  `hurt` with the `injuries` there are to come by (kinds of `data/injuries.json`, each with a
  weight and the least and the most harm), `tool` and `spoil`, which loses that `fraction`
  of what they made and still have by them, and never more than `most` units. `text` is what
  is told of it, with `{name}`, `{job}` and, for a tool, `{thing}`.
- `trust` and `mood` are what it does to how far they trust the player and to their spirits,
  and `memory` what they remember of it.

## Expeditions

- A job is done outside with `"expedition": {"minutes": [240, 360], "finds": [3, 6], "danger": 0.12}`:
  how long a trip takes, how many things it brings back, and the chance of coming back hurt.
- `data/expeditions.json` says what is out there. `loot` lists items with a `weight`; the heavier,
  the oftener found. `deliveries` says where finds go, the first match winning:
  `{"tag": "water", "to": "water_tank"}`, `{"tag": "fuel", "to": "generator"}`,
  `{"tag": "medicine", "to": "medicine_cabinet"}`,
  `{"tag": "scrap", "to": "scrap_pile"}` for items with a tag, `{"to": "shop_counter"}` for the
  rest. A rule whose kind of container does not stand anywhere in the settlement is passed over
  for the next that fits, which is what the rules after the catch-all are for: food to a
  `pantry`, anything to a `crate`. A rule with `"needs"` only counts where the settlement has an
  object of that kind: `{"tag": "fuel", "to": "crate", "needs": "workbench"}` leaves fuel in store
  where there is a workshop whose mechanic carries it on, and nowhere else. `to` must be a container kind. `injury` and `injury_kind` are what a bad trip does.
  `find_chance`, `push_on_finds`, `push_on_danger`, `push_on_minutes` and `turn_back_minutes`
  shape the risky find.
- In `data/decisions.json` the game opens `risky_find` by ID, and an outcome's `"expedition"`
  (`push_on` or `turn_back`) is what it does to the trip.

## World events

`data/world_events.json` holds what can happen to the settlement from outside.

- `quiet_days` is how many days pass at the start before anything does.
- `newcomers` lists who may come to the gate: `id`, `name`, `age`, `personality` and `traits`.
  Each needs art under its `id`, like any resident: a body sheet and the two face layers.
- `events` maps an ID to an event. All have a `kind`, a `chance_per_day`, the `hours` it can
  happen in and its `cooldown_days`. By kind:
  - `stranger`: `asks` names the job whose worker on duty answers the gate.
  - `stock`: puts `count` things from `items` (each with a `weight`) into the first container of
    kind `container`, and says `text`.
  - `merchant`: someone called `name` stops for `minutes` with `count` things from `items` and a
    `purse` of coin, both ranges. They ask `sells_at` times a thing's base value for it and give
    `buys_at` times for one, which must not be more. What is bought from them is left in the first
    container of kind `container`, or else in the one nearest the way in. It says `text` when they
    come and `end_text` when they go. With `leaves_hour` they stay until that hour of the day
    they come on, whatever `minutes` says: it must not be before the `hours` they may come in
    are over. `keeper` says who it is, as an `id` of their own and a `name`: that is who is
    seen by the gate, and whose doll is drawn under `illustrations/dolls/<id>/`. `cart` is the
    kind of object, from `data/interactables.json`, that stands beside them while they are
    there. All three can be left out.
  - `weather`: lasts `minutes`, is called `name`, adds `stress_per_minute` to anyone not under a
    roof, and says `text` when it comes and `end_text` when it goes. A job marked
    `"outdoors": true` makes nothing while it lasts.
  - `spoil`: removes a `fraction` of each shared stack of `category` in containers of kind
    `container`.
  - `raid`: takes a `fraction` of each shared stack in the kinds of container listed in
    `containers`, unless the worker of the job in `asks` is on duty and stands their ground, which
    hurts them with a chance of `danger`.
- Any event can give warning with `"lead_hours": 6` and `"forecast": "una tormenta de polvo"`,
  the words a radio uses for it. It is then settled that many hours before the `hours` it keeps to,
  which must not reach back before midnight. A `weather` event's `danger` is added to the trip of
  anyone it catches outside.
- An object's use is listening to a radio with `"radio": true`, and an item tagged `radio` is one
  too when it is used. Radios only give warnings while the generator has fuel.
- A job with `"watch_for": "raid"` keeps watch for that kind of event: its worker hears the evening
  bulletin and, knowing one is coming, stays at the post until it has.
- In `data/events.json`, `perception` also takes `dark_hours` and `dark_sight_range`: when it is
  dark, and how far a thing is seen then if nothing lights it. Leave `dark_hours` out and it is
  never dark.
- The game also opens `raid` by ID, and an outcome's `"raid"` (`stand_ground` or `give_way`) is
  what is done about the raiders.
- In `data/decisions.json` the game opens `stranger` by ID. Its texts may use `{visitor}`, and an
  outcome's `"gate"` (`let_in` or `turn_away`) is what is done about them.
- A map's `arrivals` lists the tiles just inside the gate where someone let in first stands.

## Houses

`data/housing.json` holds how houses work. Everything in it can be left out.

- `welcome_affection` is how well somebody who owns a house has to think of another to have
  them in.
- `desperate` maps a need to the level at which somebody goes into a house that is not theirs
  for what would see to it.
- `trespass_importance` and `housed_importance` are how much going in unasked, and a house
  being given, matter as events.
- `furnishing` maps a kind of object from `data/interactables.json` to what it adds to the
  building it stands in: any of `comfort`, `warmth`, `light` and `beauty`, which may be less
  than nothing. A kind that is not listed adds nothing.
- `rest_per_comfort` is how much better somebody rests in a bed in their own house for each
  point of its comfort, and `mood_per_day` how much a house as good to look at as can be lifts
  whoever owns it each day. Neither may be less than nothing.
- `uses` maps an ID to the name of something a building can be said to be for.

## Ornaments, floors and walls

`data/decor.json` holds what a building can be dressed with from inside.

- `ornaments` maps a kind to its `name`, where it goes (`on`: `floor` or `wall`), and the
  cells of the inside it takes: `width` across and, on the floor, `height` towards the front.
  `flat` is for what lies on the floor, so that anything else can stand on it.
- `floors` and `walls` map an ID to the name of something a floor, or the walls, can be made
  of.
- What any of them adds to a building goes in `furnishing` in `data/housing.json`, under the
  same kind or ID.
- The game draws the kinds, floors and walls it comes with. One it has no picture of is shown
  as a plain box, or as bare boards.

## Families

- `data/family.json` holds `start_year`; `old_age` (`from`, `chance_per_year`, `doubles_every`);
  `sleeping_rough` (`per_minute`, `from` how tired, `minutes`); `casual` (`affection` and `desire`
  it takes for two who are no couple); `marriage` (`affection`, `trust`, `accept_affection`); `kin`
  (`affection` and `trust` to begin with, the `events` that tell on whoever sees them happen to
  one of their own, and how much `stress`); `parted_at_gate`; and `children`: the `chance` of
  one, `carried_weeks`, `fertile_until`, the `weeks` a child is a bundle for and the age it is
  `grown_at`, `names` by sex, `mix_spread` and `trait_chance`, how a `bundle` fares, and what is
  made of a child's lot by whoever sees it (`seen`). In `bundle`, `taken_up_below` is how well
  a child the player laid down has to be for whoever sees to it to leave it where it lies.
- `people` in the same file says who those the game has by name are: `sex` (`m` or `f`),
  `gender` (`m`, `f`, `nb` or `bi`, the same as `sex` if left out), `drawn_to` (`m`, `f` or
  `both`), and their `siblings` and `parents` by ID. `arrive_together` lists pairs of newcomers
  who come to the gate together.
- `libido` is a side of a personality like any other, from 0 to 100.
- `children.inbred.worse` in `data/family.json` lists the sides of a way of being of which a
  child of two who are kin by blood takes the worse of its parents', and which end of each is
  the worse one: `"high"` or `"low"`. A side left out is mixed as in any child.
- A job with `"per_residents": 4.5` takes one more worker for every so many people who live in
  the settlement, and never fewer than `needed`.
- The game opens `proposal`, `strangers` (two at the gate: an outcome's `"gate"` may also be
  `let_first` or `let_second`, and texts may use `{first}` and `{second}`) and `take_in` by ID.
  Their scores may weigh `kin` and `room`.

## Governments

`data/governments.json` holds every kind of government, and how politics goes.

- `governments` lists the kinds by ID, each with a `name`; a `leader_role` if somebody leads; a
  `council_role` and `council_seats` if there is a council; who `proposes`, who `approves` and
  who `votes` (`leader`, `council`, `everyone` or `nobody`); how votes are taken (`ballot`:
  `open` for a show of hands, `secret` for one in which only the count is known); the share it
  takes to approve (`approval`), the `leader_weight` and whether there is a `veto`; `term_days` (0 for no
  terms); `succession`, the ways the next leader comes to be in the order they are tried
  (`election`, `council`, `strongest`, `heir`, `following`); `abuse_tolerance` from 0 to 100;
  `dissent` from 0 to 1, how freely people take to the square against a law under it (1 by
  default, and 0 for one under which they do as they are told however much they hate it);
  the measures it `starts` with; and its `appeal`, how much each leaning of a resident counts
  for or against it. A kind with a leader needs a way of succession, and one without has none.
- `roles` gives each role a `name` and, by gender, other `names`.
- `founding_residents`, `choosing_hours`, `election_hours` and `proposal_weight` say when a
  government is chosen, how long that and a vote take, and how much the player's proposal adds.
- `profile` says where each leaning comes from (`leanings`: for each, how much every side of a
  personality moves it from the middle), how far a leaning of somebody's own may fall
  (`own_spread`), where trust starts, how fast fear and resentment fade, which leaning `sways`
  each thing held, and what goes into `obedience`.
- `loyalty` says where loyalty to a leader starts (`base`), how much what is felt for them
  (`from`) and their `charisma` add, what having `backed` them adds, and its daily `drift`.
- `ways` holds what counts in each way of coming to lead, and `seated` what coming to the seat
  by each does to the measures. `measures` holds how the measures move.
- `reactions` says, by the type of a fact, what learning that somebody who governs did it does:
  `holds` (to the fear, loyalty, trust and resentment of whoever learns it), `measures` (to the
  settlement if everybody learned it) and `victim` (how many times over for whoever it was
  done to).
- `leadership_pace`, `resign_stress` and `resign_support` say how much a leader tells on work,
  and when one thinks of stepping down.
- `ways.election` also says who stands: `stand_from` is how much somebody has to want a seat
  (left out, everybody stands), and `interest` and `liked` how much their interest in politics
  and what others feel for them count towards it, beside `charisma` and `leadership`.
- `elections` holds `rig_hours` (how long before a secret vote a leader about to lose it thinks
  of seeing to the count), `rig_corruption`, `claim_from` (how sore a loser has to be to say
  there was cheating), `lost_resentment` and `let_down_trust`.
- The game opens `rig_election` by ID. Its scores may weigh `losing` and `scruples`. The
  decisions at the gate may weigh `law`: 1 when a law says nobody comes in and whoever answers keeps it.

## Affecting a resident

`data/affect.json` holds what the player can tell a resident. Everything in it has a `label`,
which is what telling it says, and may have a `name`, which is what it is called for short in
the wheel, and an `icon`: one of the game's icons, or a file of that name in
`illustrations/ui/icons/`.

- `needs` lists what they can be told to see to, each with the `need` it lowers, or
  `"heals": true` for being mended. `"asleep": true` is for what is done lying down.
- `with` lists what they can go to somebody for: a `label` with `{target}` for who, the
  `interaction` from `data/social.json`, and `who` it can be with (`anybody`, `single` for
  somebody they are no couple with, `partner`).
  - `feels` is what they have to feel for the other for it to be on offer, and with none it
    always is: `{"affection": 40}` is forty or more of it, `{"affection": [-100, 15]}` is
    between those, several feelings in one have all to hold, and a list of them
    (`[{"resentment": 30}, {"affection": [-100, 15]}]`) is any one of them holding. The
    feelings are `affection`, `trust`, `attraction`, `fear` and `resentment`: what the one
    who is told feels, never the other.
  - `tone` is `friendly`, `romance` or `hostile`: the colour and icon it is shown with. What
    is `romance` is only between adults, towards somebody they could be drawn to.
- `leisure` lists what they can pass the time with somebody at, the same way as `with`.
- `incite` is the same again, for content from before: a `feeling` that has to be
  `strong_feeling` or more. The game's own no longer has any.
- `words` lists what is simply said to them: the `needs` it changes and what it does to
  their `mood`.
- `tasks` lists each thing they can be told to get on with, as a label or as an object with
  one: `to_post`, `push`, `take_charge`, `salvage`, `take_job`, `leave_job`, `treat`, `use`
  and `stop`. What each does is code; one left out is not on offer. `use` is using one
  thing in particular, with `{target}` where the thing goes: it is not in the wheel, and is
  what putting somebody down on a bed or a pot tells them. Left out, nobody put down on a
  thing uses it.
- `hold_minutes` is how long somebody who is stopped stands listening, and `most_targets` how
  many people or things are offered to choose among, the nearest first.
- `most_orders` is how many things can wait for a resident to get to them. `wait_minutes` is
  how often somebody who does nothing unasked looks again at whether there is anything they
  have to see to, and `desperate_need` how high a need of the body gets before they see to it
  unasked: over 100 they never do.

## Leisure

`data/leisure.json` holds what a resident does alone to pass the time.

- `alone` lists the pastimes, each with a `name`, a `label`, the `text` of the event with
  `{name}` for who, what is said of somebody `doing` it, how many `minutes` it takes at the
  least and at the most, and what it does to their needs `per_minute`.
  - `taste` is the taste it is liked or loathed by: a tag, as an item has
    (`data/tastes.json` gives it a name under `names.tag`). Without one it is the same to all.
  - `strolls`, `sits` or `lies` says how it is done: walking about, sitting down as they
    sit, or lying on the ground. Otherwise on their feet.
- `relief` is how much of the good a pastime does comes of it, by how it is taken (`hated`,
  `disliked`, `neutral`, `liked`, `loved`), and `taken` what is added to what is told of it.
- `accept_affection` is how fond of whoever asks somebody has to be to go on somewhere with
  them.

A pastime with somebody is an exchange in `data/social.json` with a `pastime`, offered from
`leisure` in `data/affect.json`. The two may not share a name.

Wanting to be entertained is a need, `boredom` (S62), beside `hunger`, `thirst`, `tiredness`,
`social` and `stress`. Whatever changes needs can name it: `per_minute` on a pastime, on a
`use` of an object, on an exchange and on a job, and the `effects` of an item. Below zero
passes the time and above it bores. Residents take up a pastime unasked once they are bored
enough, the sooner the more it takes off them and the better they like it, and weigh
whatever else lowers it with the rest of what they could do.

## Taking things apart

- An object in `data/interactables.json`, or in a pack, may have `"salvage": {"item": "scrap",
  "units": 8, "minutes": 180}`: what taking it apart gives, how much and how long it takes one
  pair of hands. Without it nobody can be told to.
- An item may have `"scrap": 2` among its `properties`: how many units of scrap one of it
  comes to when the player has it broken up. Without it, it cannot be.
- `data/construction.json` holds `score.task` (how much a site in somebody's charge comes
  first), `await_minutes`, `scrap_item` (what breaking things up gives) and `fetch` (`minutes`,
  `units` and `danger` of a trip outside for what a site waits for).
- The game opens `scrap_proposal` by ID. Its scores may weigh `bargain`: how little the thing
  is worth to its owner.

## Laws

`data/laws.json` holds every law there is to pass, and how laws are kept.

- `laws` lists them by ID, each with a `name`, a `text` (what it says, with `{item}` for what it
  names) and its `degrees` from mildest to harshest. A degree has a `name`, a `weight` (how
  much more or less it weighs with people than the law as written, 1 by default) and its
  `effects`:

| Effect | What it does |
|---|---|
| `curfew` | `[from, to]` hours in which nobody is out of doors |
| `closes` | Kinds of object nobody uses |
| `bans_tags` | Tags of item nobody takes |
| `bans_item` | Nobody takes the item the law names. The law needs `"param": "hated_food"` |
| `day_off` | A day of the week, from 0, on which nobody works |
| `leader_birthday` | Nobody works on the birthday of whoever leads |
| `shift_hours` | Hours the working day is longer by, or shorter if less than none: its last shift gives |
| `wage_factor`, `tax` | How many times the usual wage is paid, and the share of it the fund keeps |
| `meals` | How many times a day anybody eats out of what is common |
| `meal_price` | How many times the usual price a meal out of the commons costs |
| `common` | What is kept in a container is nobody's |
| `gate` | `closed`: nobody from outside is let in |
| `excused` | Who does not work and is kept all the same: `expecting` |
| `requires` | A `kind` of object everybody gathers at, at an `hour` |
| `quiet` | `[from, to]` hours in which nobody talks to anybody |
| `salute` | Whoever leads is greeted by whoever comes across them |
| `dark` | Kinds of object that give no light at night |

- `opinion` says what weighs for or against it with each resident, and `bias` what it starts
  from. A key is a leaning, a side of a personality, something held (`loyalty`, `trust`,
  `resentment`, `dread`), a stake (`works`, `idle`, `savings`, `poor`, `goods`, `drinks`,
  `uses`, `hungry`, `tired`, `stressed`, `guards`, `expecting`, `governs`, `leads`,
  `partnered`, `shortage` for how short the settlement is of food, `item` for how much they
  like the item it names, `appeal`), or `taste:` and a taste tag.
- `harsh` is what it adds to how authoritarian the settlement is, and `burden`, from 0 to 1,
  how hard it is to keep. `absurd` marks a nonsense, which costs legitimacy to pass; `whim`
  one that whoever leads may pass because they fancy it, by `whim_opinion`.
- `excludes` names laws it cannot stand beside. `needs_currency`, `needs_leader` and
  `needs_kind` say what there has to be for it to make sense.
- `motive` is what brings a resident to propose it, one of: `need_above` (`need`, `level`),
  `stock_below` (`category`, `per_resident`), `fund_below`, `fund_above` (coin per resident),
  `known_facts` (`types`, `days`, `count`, and `night` for what happened in the dark),
  `conviction` (how much they have to hold with it) and `stake` (a stake they must have).
- `keeping` says how laws are kept (`base`, `burden`, `regard`, `legitimacy`, `jitter`), `grind`
  what a day under one does, `breach` what being seen to break one does, `whim_from`,
  `whim_chance` and `absurd_legitimacy` how whims go, and `plenty_per_resident` how much food
  a head there has to be for nobody to think the settlement short of it.
- A new effect needs code that asks about it. A new law made of the effects there are needs none.

## Proposals

- `protest` in `data/laws.json` says how people take to the square against a law: the `kind`
  of object they gather at and the `reach` that counts as being there, its `hours`, how much
  somebody has to have against a law to go (`from`), how much a law counts that was `imposed`
  and one that was `voted`, the `tire_days` after which they give it up, what a day of it does
  to `unrest` and `legitimacy` where it is put up with, how authoritarian the settlement has
  to be for it to be leaned on instead (`harsh_from`) and what that leaves (`cowed_fear`,
  `cowed_resentment`, `harsh_authoritarianism`), and what giving in does (`given_in_trust`,
  `given_in_resentment`, `given_in_legitimacy`).

`data/proposals.json` holds what can be put to a settlement, and how deciding goes.

- `kinds` lists them by ID: `enact_law`, `repeal_law`, `call_election`, `change_government`,
  `expel`, `adopt_currency` and `return_to_barter`. Each has a `name`, a `text` (with
  `{described}`, `{law}`, `{text}`, `{degree}`, `{target}`, `{government}` and `{currency}`), an
  `opinion` and `bias` as a law has, `debate_hours` if it is talked over longer than usual,
  and a `motive` that brings a resident to raise it unasked. What a kind does when it passes
  is code: a new kind needs some.
- `decrees` lists the kinds that are the player's to run: put by the player they need nobody
  to make them theirs, are in force at once where one person decides, and are voted where a
  council or everybody does. `residents_raise` lists the kinds a resident may raise unasked.
  Left out, laws and how to trade are the player's and residents raise a vote on whoever
  leads and another kind of government. With `decrees` empty and every kind in
  `residents_raise`, everything goes through whoever may propose, as it did before.
- `debate_hours`, `leader_hours`, `pending_limit`, `again_days`, `undo_days`, `rest_days` and `sore_days`
  say how long a proposal waits, how many wait at once, and how soon the same thing, the same
  resident, or the same resident with the same thing comes back. `raise_from` and `repeal_from` are what somebody has to make of a matter to
  raise it, and `margin` how far from the middle a mind has to be to vote.
- `weights` holds how much each part of a mind on a proposal counts, `target` what is felt for
  whoever it is about, and `misdeeds` the facts that count against them.
- `influence` holds the player's word: `lobby`, `against`, `defiance`, `contrary`,
  `resistance_fade`, `outcome` and `backing`. `aftermath` holds what comes of a decision.
- A trait in `data/traits.json` may give `"politics": {"justice_sensitivity": -25}`: so much
  more or less of a leaning.
- `charisma` and `leadership` are sides of a personality like any other, from 0 to 100.
- The game opens `resign` by ID. Its scores may weigh `support`.

## Trials and punishments

`data/punishments.json` holds what somebody can be tried for and what they can be given.

- `offences` lists, by the type of the event, what can be brought to trial: a `name`, as it is
  said after "de" (`un robo`), and a `gravity` from 1 to 10. An event of that type has to leave
  a fact whose first subject is whoever did it, as a theft or a broken law does.
- `punishments` lists them by ID, each with a `name`, a `severity` from 1 to 10 and what is
  `said` of whoever is given it. `building` names the use a building has to have for it to be
  carried out, and `objects` the kinds of object any one of which has to stand in the
  settlement: without them nobody is sentenced to it. `public` has it seen by whoever is there,
  and `harsh` marks the ones that frighten. `amount`, `things`, `days`, `hours`, `harm` and
  `cause` say how much of it there is. What `fine`, `confiscation`, `community_service`,
  `public_stocks`, `prison`, `corporal_punishment`, `exile` and `execution` do is code: a
  punishment by another ID is a word, a record and how it is taken, and no more.
- `trial` holds `step_minutes`, the `sentence_hours` the player has to say what is given and
  what is given `unanswered`, `guilty_from`, and the `weights` of a verdict: `saw`, `told`,
  `testimony`, `resentment`, `affection`, `kin` and `accuser`.
- `accusing` holds the `hour` at which whoever knows of something thinks of accusing, how sure
  of it they have to be (`sure_from`), how old it may be (`within_days`), what it has to come to
  (`from`), and its `weights`: `gravity`, `resentment`, `affection` and `justice`.
- `prison` holds what a prisoner is given each day until the player says otherwise: `meals`,
  `drinks`, a `food` and a `drink` by item ID (empty for whatever there is most of), and the
  `most` of either.
- `reactions` holds how a punishment is taken: `friend_from`, `harsher_by`,
  `indifferent_below`, what `approval`, `anger`, `grief` and `fear` each do to whoever feels
  them (sides of a political profile, `stress` and `mood`) for each point of severity, what
  each does to the settlement's `measures`, what a `harsh` one adds, the `child_factor`, and
  the `heard_share` that reaches whoever was not there.
- `exile_return` holds after how many `days` somebody exiled is heard of again (a range), the
  `raid_chance` for one who left with all the grudge there is, and how many `tries` they give
  the gate.
- A building is a jail by its use: `uses` in `data/housing.json` has `jail`. `stocks`, `gallows`
  and `guillotine` are objects like any other in `data/interactables.json`.
- The game opens the decisions `accuse` and `exile_back` by ID. `exile_back` may weigh
  `affection`, `resentment` and `kin`.

## Substances

- An item is a substance with a `substance` entry:
  `{"route": "smoked", "minutes": 30, "dependence": 0.12, "sign": "smoke"}`. `route` is one of
  the ways of taking one in `data/substances.json`, and `minutes` how long it lasts. The rest
  are optional: `per_minute` (what it does to needs each minute meanwhile), `work_pace` (how
  fast it has them work, 1 for no difference), `unaware` (whether they notice nothing),
  `after` (`minutes` and `per_minute` of what comes once it wears off), `toll` (harm each time)
  and `harm` (harm when taken on top of itself), `dependence` (the chance of it the first time,
  from 0 to 1), `craving_minutes` (how long before whoever depends on it wants more) and `sign`
  (what it looks like on them). What it does on the spot is the item's `effects`, as for any item.
- A taste in people may be for whoever has a sign on them: in `data/tastes.json`,
  `{"name": "la gente que fuma", "under": ["smoke"], "when": ["under"]}`.
- `data/substances.json` holds how they work in general: the `routes` and how each is said,
  the `signs` and how each is said of someone seen with it, `fills_the_room` (the route whose
  sign reaches everyone under the same roof), `habit_growth` and `max_chance`,
  `passes_after_minutes` and `care_factor`, `withdrawal` (`per_minute` and `work_pace`),
  `craving_wish`, `impulse_from`, `hooks_from`, `relapse_minutes`, `allowed_minutes`,
  `resist_minutes`, `resist_stress` and `overdose_kind` (an injury from `data/injuries.json`).
- A use that `consumes` a category gives one unit of what the object holds, substance or not:
  it is how the bar serves a drink.
- A job's `produces` may list `"also": ["sedative", "powder"]`: other things made at the same
  post in turn with `item`, whichever there is least of. Only for what stays at the post.
- The game opens `substance_tempted` and `substance_habit` by ID. An outcome's `"substance"`
  (`take` or `resist`) is what is done about what they were about to take, and their texts may
  use `{thing}`.

## Resources

`data/resources.json` says what a settlement counts as what it lives on, and how its books are
kept:

```json
{
  "window_days": 3,
  "kept_days": 7,
  "low_days": 2,
  "resources": {
    "food": {"name": "Comida", "icon": "food", "category": "food"},
    "energy": {"name": "Combustible", "icon": "energy", "tag": "fuel"}
  },
  "reasons": {"made": "Hecho aquí", "eaten": "Comido"}
}
```

- A resource is every item of a `category`, every item with a `tag`, or both. An item of a pack
  counts as one by having that category or tag, with nothing else to do. `icon` is the name of
  the picture it goes by in the bar.
- `window_days` is how many of the last days the pace of things is worked out from, `kept_days`
  how many are kept, and `low_days` how few days a resource has to have left to be running low.
- `reasons` is what each reason a thing comes in or goes out is called where it is shown.
  `sourced` is what a reason is called where the job a thing came of is known, with
  `{source}` for the job's name: `"made": "{source}"` has what the garden made called `Huerto`.
- Nothing is a resource that is not named here: take one out and it is no longer counted, add
  one and it is.

### Current

- `"draws": 2` on a kind of object in `data/interactables.json` has it run on current: so
  much while it is switched on. Without it gives no light, tells nothing if it is a radio,
  and cannot be worked at if it is a post.
- `"gives": 16` makes a kind of object a generator: so much current while it holds fuel. It
  has to be a container.
- `data/power.json` names the item that is `fuel`, and `fuel_lasts`: the minutes of one unit
  of current that a unit of it is good for.

### What goes off

- `"spoils": 20` on an item, in `data/items.json` or in a pack, is how much of its freshness,
  of a hundred, one loses in a day: five days for that. Left out, the thing keeps. The item
  editor has a field for it. `"spoils"` in the `item` of a kind of `data/crafts.json` does
  the same for what residents come to make.
- `"chill": 0.25` on a kind of object in `data/interactables.json` has what is kept in it go
  off a quarter as fast while it has current, so it needs `"container": true` and wants
  `"draws"`. With `"store"` as well it is a store that takes only what goes off, ahead of the
  others.
- `data/spoilage.json` says what a unit that has gone off `becomes`; how far `apart` in
  freshness two lots may be and still be one stack; and under `compost` the `item` that is
  one, the kinds of object it is put `on`, the `units` a dressing takes, the `factor` the
  post is worked faster by and the `days` it lasts. With no such file nothing is left of what
  goes off and nothing takes compost.

### Stores, and where what they hold is taken from

Two keys of a kind of object in `data/interactables.json`, both of which need
`"container": true`:

```json
"warehouse": {"name": "almacén", "article": "un", "width": 4, "height": 3, "container": true,
              "store": {"food": 100, "water": 300}},
"pantry": {"container": true, "outlet": {"food": 4}}
```

- `store` makes a kind of object a store: how many units of each resource one of them
  holds. A resource it does not name is not kept in it.
- `outlet` makes a kind of object somewhere what a store holds is taken from and brought
  to: how many units of each kind of thing of a resource it keeps at hand. The rest goes to
  the store, and comes back as it is used. `0` is for what keeps none, as a crate. A
  resource it does not name stays in it as it always did.
- A kind is one or the other, and the resources are those of `data/resources.json`.
- A map with no store on it works as it did before there were stores.

## Posts that wear

`wear` in `data/work.json`:

```json
"wear": {"per_hour": 0.25, "pushed": 2.0, "cost": {"scrap": 2}, "minutes": 120, "job": "mechanic"}
```

- `per_hour` is how much of its hundred a post loses in an hour of being worked, and
  `pushed` what that is multiplied by while whoever works it is pushing. With `per_hour`
  at 0, or the block left out, nothing wears.
- `cost`, by the tag of the items that will do, and `minutes` are what mending one takes.
  `job` is who mends: left out, anybody does.
- `breakdown` among the `mishaps` of `rush` is a push ending with the post broken down.

## Rarities, and making things better

`data/rarities.json` says how rare a thing can be and what making it rarer takes:

```json
{
  "tiers": {
    "common": {"name": "Común", "color": [236, 229, 212], "better": 1.0},
    "uncommon": {"name": "Poco común", "color": [104, 152, 84], "better": 1.15, "study": "fine_work"},
    "mythic": {"name": "Mítico", "color": [238, 190, 70], "better": 2.0, "built": false}
  },
  "upgrade": {"cost": {"scrap": 3}, "minutes": 180, "kinds": ["generator"]}
}
```

- `tiers` are the rarities, the commonest first: a thing of level 1 has the first. Each has
  a `name`, the `color` it is known by, and by how much it is `better`, which may not be
  less than the one before.
- `study` is the subject of `data/research.json` that has to be known before a thing can be
  made that rare. `"built": false` is for a rarity that is never made, only found.
- `upgrade` is what making a thing one level better takes for the first level: `cost` by the
  tag of the items that will do, and `minutes` of work. The second takes twice that.
- `kinds` names kinds of object that can be made better besides those that always can: the
  post of any job, a store, and whatever is slept in.
- `found` says how rare what a trip brings back is: `weights` by rarity, and the
  `risk_factor` every weight but the first is multiplied by for whoever went on at
  something worth a risk. Left out, everything found is common.
- Nothing has to be said of an item for it to have a rarity: any may. What rarity does to
  one follows from what the item is already said to do: its `effects`, its `speed`, `wear`
  and `damage` among its `properties`, and its `base_value`.

## Wear, prices and the shop

- An item wears out if its `properties` give it `wear`, the condition it loses per use out of 100:
  `{"wear": 2}`. An item without it lasts for ever.
- An object's use costs credits with `"price": 2`.
- `"repairs": 2.0` makes a use mend a worn thing the resident brings, that much condition a
  minute. Give it a `staffed_by` so that someone has to be there to do it. With
  `"material": "scrap"` and `"material_from": "scrap_pile"` each repair uses up one item with that
  tag from a container of that kind.
- `"sells": true` makes a use the buying of something kept inside the object, which must be a
  container. Stock it from the map's `stock` like any other container.
- `"display_of": "shop_counter"` on an object kind makes it show what the containers of that kind
  in the same room hold, as the shop's shelves do. It changes nothing but how the object is drawn.
- `data/economy.json` holds the settlement's rules: `wage_per_hour`, `starting_credits`,
  `price_factor` (a price is the item's `base_value` times this), `scarcity_markup` (how much
  dearer a thing gets as it runs out), `vacancy_notice_hours` and `week_days`. Every field has a
  default, and so does the file.
- The same file holds how it trades. `starting_credits` is what each resident is handed when a
  currency is first taken up, and `fund_per_resident` what goes into the fund for each.
  `credits_name` and `credits_singular` name the currency of a settlement that comes ready made.
  `kept_categories` lists the categories of thing that, under barter, whoever holds no job hands
  something over for. `pilfer_max` is the most credit taken at once. `trade_ask_days` is how long
  the residents cannot be asked again how they would trade, and `savings_scale` and `goods_scale`
  are the credits and the worth of belongings at which either weighs all it can on their answer.
- More of how it trades, in the same file: `meal_price` (what a meal out of the commons costs
  with a currency), `idle_days` (days without working before the settlement stops keeping
  somebody), `gift_savings` (what somebody keeps by them before spending on anybody else),
  `loan_size`, `poor_below` and `loan_days`, `common_finds` (tags of what whoever goes outside
  never keeps for themselves), `unpaid_mood` and `unpaid_stress`, `grumble_swaps` and
  `grumble_unpaid_days` (how much of either before somebody raises trading another way) and
  `strongbox_kind` (the kind of container a fund is kept in where there is no counter).
- A trait in `data/traits.json` may give `"thieving": 0.5`, which is added to how given its
  owner is to taking what is not theirs and has coin tempt them whatever they have, and
  `"careless": true`, which has them part with the tool they work with.
- A trait may be marked `"flaw": true`: a child of two who are kin by blood takes every flaw
  its parents have, before any other trait of theirs.
- The game also opens `currency_raised` and `barter_raised` by ID, for a resident who has had
  enough of how things are traded. An outcome's `"raises"` (`currency` or `barter`) is what it
  puts to everyone.
- In `data/decisions.json` the game puts `currency_proposal`, `barter_proposal` and
  `sale_proposal` to residents by ID. An outcome with `"agrees": true` is going along with what
  was put. Their scores may weigh `savings`, `goods` and `bargain` (how good a sale is by the
  resident's own lights: a half for an even one).

## Traits and sounds

`data/traits.json` gives residents tastes: a trait lists `tags` and may set
`item_value_multiplier` (items with a matching tag are worth more to them) and
`food_reaction_bonus` (food with a matching tag also eases their stress).

`data/audio.json` says what sounds and when. Effects are files in `assets/sounds/`, named as in
that file. A file of the same name in `sounds/`, at the top of the project, is played in place
of the game's: see `sounds/README.md`. The game comes with no ambience and no music: each is
heard only from a file somebody has put there, ambience in `sounds/ambience/`.

- `events` says which sound each event type plays. Of what happens in the same moment, the most
  important is the one heard.
- `actions` says what is heard while somebody in view is in the middle of doing something:
  the name of what they do (`build`, `salvage`, `carry`, `repair`, `fight`, or any exchange or
  use), the `sound`, and how often it comes again (`every_ms`). Nothing that goes on for hours,
  such as sleeping, should have one.
- `interface` gives a sound to what the player does with their own hand: `click`, `open`,
  `close`, `select`, `order` and `refuse`.
- `ambience` says when each loop would be heard, once there is a file for it, and how loud at
  most (`volume`, from 0 to 1): `when`
  is `always`, `day`, `night`, `storm`, `talk` (people in view talking) or `near`, with the
  `kind` of object that has to be in view. `"powered": true` is for what only runs while the
  settlement has power. One taken out of here is never heard.
- `volumes` says how loud `effects`, `actions`, `interface` and `ambience` are, from 0 to 1.
- The game's own sounds are written by `tools/art/sounds.py`: an effect is a list of notes,
  each `(frequency, milliseconds, waveform)` and optionally the frequency it slides to and how
  loud it is, with a second voice under it in `UNDER`. `python -m tools.make_art` writes
  whatever is missing. It writes nothing that goes on and on.

Its `music` section says which track plays in each mood: `tracks` maps `day`, `night`, `storm`
and `tension` to WAV files in `assets/music/`, and `night_hours` says when night falls and ends.
A mood left out plays nothing, and the game comes with none: `tracks` is empty. Trouble (a fight,
or someone waiting for advice on something urgent) is heard over a storm, and a storm over the
hour. A track must be written to loop: it should end where it begins.

## Voices

`data/voices.json` is everything a voice can be made of. What residents say in the dock, and what
they ask the player, is said out loud by a model and then made into the voice of whoever says it.

- `models`: who can speak. Each names a Piper voice `file`, kept in `voices/models/`, and which
  of its `speaker`s. Any Piper voice will do; `voices/README.md` says how to get them.
- `controls`: what can be turned up or down, in the order the editor shows them, each with a
  `name`, a `min`, a `max`, a `default` at which it does nothing, and a `step`. The game knows
  what to do with `pitch` (semitones: the whole voice goes up or down, as a smaller or a larger
  throat would sound), `speed`, `tremble` (a voice that wavers), `growl` (hoarse, with a rattle
  under it), `robot` (a hum and a ring) and `garble` (cut up and shuffled, so that it is a voice
  saying nothing). Changing a range here changes how far the slider goes.
- `presets`: the kinds of voice the editor offers, each a `name`, a `model` and whatever controls
  it turns. `default` is the one given to a resident nobody has chosen a voice for.
- `residents`: the voice each resident starts with, by resident ID: a `preset`, and anything laid
  over it. Give a new resident a line here, or they will have the default.
- `samples`: the lines a voice is tried with in the editor.

A voice chosen in the editor is written to `voices/residents/<resident_id>.json`, which is all
there is to it: the model and a figure for each control. No sound is ever part of a saved game.

A line is spoken by its model once and kept in `voices/cache/`, named after its own words, so a
line that is reworded is simply spoken anew. `python -m tools.make_voices` has every line in
`data/dialogue.json` spoken beforehand.

## Social exchanges

`data/social.json` defines the exchanges two residents can have. The game picks `chat` or
`argument` by ID; everything about them is data:

```json
"chat": {
  "hostile": false,
  "minutes": [10, 30],
  "importance": 10,
  "per_minute": {"social": -1.0, "stress": -0.1},
  "relationship": {"affection": 1.0, "trust": 0.4, "resentment": -0.5},
  "text": "{a} y {b} charlan",
  "dialogue": "chat",
  "memory": "Charlé un rato con {other}.",
  "emotional_value": 0.3,
  "tags": ["chat"]
}
```

`subject` says that the exchange is about something (see `Talk`, below): whoever starts it
brings a subject up, and how the other takes it tells on what they feel for them. Such an
exchange quotes no line.

`dialogue` names a list of lines in `data/dialogue.json`; one is picked for the event text.
Lines can be written, changed and taken out freely: which one is said comes of a die of its
own, and no number of lines changes what happens in a settlement with the same seed.
`relationship` holds base changes that are scaled by both residents' personalities.

`doing` is what is said of somebody who is at it, with `{other}` for the other one: without it
they are said to talk, or to argue. `pastime` is the taste it is liked or loathed by, for
something done for the sake of it: how fond of the other each comes away goes by how they took
it. `then_use` is the use both go on to once it is over, each for themselves: `drink` sends
them to the bar. Whoever was asked goes only if they care for whoever asked.

An exchange is part of a romance with `"romance"`: `confession` (at its end the one told answers
from what they feel), `tryst` (two residents alone: it needs the other to want it and nobody
watching) or `breakup` (at its end the couple is over). In `relationship`, a positive `attraction`
is scaled by the spark between the two instead of by their personalities.

## Talk

`data/talk.json` is what talk is about and the words the player is asked for. Without the
file nothing is about anything, and a chat quotes a line as it used to.

```json
"lists": {
  "places": {
    "name": "Sitios",
    "ask": "¿Qué sitio hay ahí fuera que merezca la pena?",
    "words": [],
    "patterns": ["aquella vez en {word}", "cómo se llega a {word}"]
  }
},
"new_subjects": "subjects",
"phrases": {
  "greeting": {"name": "Saludo", "when": "begin", "ask": "¿Cómo saludo yo a la gente?"}
},
"items": {
  "food": ["el día que se comió {an_item} y se atragantó", "{item}"],
  "default": ["{item}", "lo que haría con {an_item}"]
},
"people": ["{pj}", "la última de {pj}"],
"heard": ["lo de que {fact}"]
```

- **`lists`** are the lists of words the settlement keeps. `ask` is what a resident says to
  ask for one more, `words` the ones it comes with (the built-in ones come with none: the
  words are the player's) and `patterns` how a word of it is talked of, with `{word}` for
  the word. `new_subjects` is the list a subject made up on the spot goes into.
- **`phrases`** are the phrases each resident has of their own. `when` is when one comes
  out: `begin` as a talk begins, `glad`, `low` or `angry` when that is how they are, and
  `any` otherwise.
- **`items`** is how a thing is talked of, by its category, with `default` for any other:
  `{item}` reads `el guiso caliente` and `{an_item}` reads `un guiso caliente`. **`people`**
  is how somebody is, with `{pj}`, and **`heard`** how something heard is, with `{fact}`.
  Every pattern is read after `sobre`, and is best written so that it reads with a word of
  any gender and number.
- **`taken`** is what a subject does to what whoever listens feels for whoever brought it
  up, by how they take it (`hated`, `disliked`, `neutral`, `liked`, `loved`); **`relish`**
  is how much of the good of the talk itself comes to them, by the same; and **`lines`** is
  how it is said, with `{listener}`, `{speaker}` and `{subject}`. A reaction with no line is
  not said.
- **`weights`**: `fond_from` is how much they have to like a thing or a word to bring it up,
  `talked_of_from` how much they have to feel for somebody, `sore_from` how far two have to
  stand on somebody for talk of them to be welcome or not, `news` the chance that news is
  the subject before half of how sociable they are is added, and `shunned` and `favoured`
  how much less and more they bring up what they have seen the other dislike and like.
- **`asks`**: the `hour` residents think of asking at, the `chance` each has, how many wait
  at `most`, after how many `lapse_hours` one is let go, how much they have to like somebody
  to wonder what to talk to them about (`subject_from`) or feel for them to want a name for
  them (`nickname_from`), and what they say to ask for those two.
- **`saying`**: for how many `greet_minutes` of a talk the greeting is seen, `every` how many
  minutes in company and `alone_every` how many alone a phrase may come out, for how many
  `minutes` it is seen and with what `chance`, and the mood (`glad_from`, `low_below`) and
  the stress (`angry_from`) that settle which.
- **`order`** is what a resident is told when they are told what to talk about with
  somebody, one of the orders of `data/affect.json`, and **`longest`** the most letters a
  word or a phrase has. `shows` is how much of a taste shows each time (see `Tastes`).

A word is a taste tag, `word_<list>.<word>`, with a leaning for each resident like any other
tag.

## Wishes

`data/wishes.json` is what residents come to want of their own accord (S61). Without the
file, or with `chance` at 0, nobody wants anything.

```json
{
  "chance": 0.04,
  "hours": [8, 22],
  "lasts_hours": 24,
  "met_mood": 10,
  "lapsed_mood": -6,
  "met_value": 0.5,
  "lapsed_value": -0.3,
  "liked_from": 20,
  "fond_from": 20,
  "pull": 0.3,
  "kinds": {
    "eat": {
      "text": "{name} tiene antojo de {what}",
      "weight": 3,
      "categories": ["food", "drink"],
      "met": "Tenía antojo de {what}, y me di el gusto.",
      "lapsed": "Me quedé con el antojo de {what}.",
      "got": "{name} se da el gusto de {what}",
      "lost": "A {name} se le pasa el antojo de {what}"
    }
  }
}
```

- **`chance`** is how likely a wish is to come to somebody who has none, each hour between
  the two `hours` of the day, and **`lasts_hours`** how long they have to see it met.
- **`met_mood`** and **`lapsed_mood`** are what one met and one let go do to their mood,
  and **`met_value`** and **`lapsed_value`** how the memory of each sits with them, from -1
  to 1.
- **`liked_from`** is how much a thing has to be to their taste to be wished for, and
  **`fond_from`** how much affection they need for somebody to wish to be with them.
- **`pull`** is how much is added to the score of whatever would meet it, when they choose
  what to do.
- **`kinds`** are the kinds of wish there are, of `eat`, `with`, `have` and `do`: leave one
  out and nobody wishes that way. Each has the `text` said of whoever has it, `got` and
  `lost` for when it is met and let go, all three with `{name}` and `{what}`, and what they
  remember of it, `met` and `lapsed`, with `{what}`. `weight` is how often it is that kind
  beside the others. `eat` and `have` need the `categories` of item wished for that way:
  give a pack's items one of them and they are wished for with no more said.

What there is to do, for `do`, is every pastime of `data/leisure.json` and everything in
the `uses` of the kinds of object that stand in the settlement, save what is for training.

## Friendship and romance

`data/relationships.json` holds the rules:

- `friendship` lists the degrees of friendship from the least to the closest, each with an `id`,
  a `name` and the `affection` and `trust` it takes. The last one is who secrets are told to.
- `adult_age` is the age from which a resident takes any part in romance. It cannot be under 18.
- `romance` sets the thresholds: `confess_attraction` and `confess_affection` to think of saying
  so, `accept_attraction` and `accept_affection` to say yes, `tryst_attraction`, `tryst_hours` and
  `tryst_cooldown_minutes` for time alone, `affair_attraction` and `affair_max_empathy` for going
  behind a partner's back, `taken_attraction_factor`, and `breakup_resentment`.

In `data/events.json`, a reaction can now also say:

- `"secret": 2`: how many of the fact's first subjects keep it to themselves (`true` is 1).
- `"blame_subjects": 2`: how many of the first subjects did it. The rest had it done to them, and
  onlookers do not blame them.
- `"rival"`: what someone it was done to feels about the other one, when the one who wronged them
  is their own partner.
- `"blame_target": "all"`: nobody takes a side, and everyone who did it is held to it in full.
  `kin_together` is the reaction to two close kin being together.

## Decisions

`data/decisions.json` defines the crisis in which a resident asks for advice: when it opens, how
long the player has, the outcomes the resident may choose and the advice the player may give.

- An outcome's `score` weighs inputs that each run from 0 to 1: `bias` (always 1), `anger`,
  `aggression`, `impulsiveness`, `empathy`, `courage`, `sociability`, `greed`, `stress`, `health`,
  `affection`, `resentment`, `fear` and `attraction` (the last four towards the other person),
  and for a decision about a job, `vacancy` (how long it has stood empty) and `idle` (1 for someone with no
  job).
- An option's `influence` adds to the score of the outcomes it names. It is advice, not a command.
- An outcome may name an `interaction` from `data/social.json` for the resident to go and have,
  change `needs` and `feelings`, and leave a `memory`. `"takes_job": true` makes it taking up the
  job the decision is about.
- The game opens `grievance`, `brawl`, `job_offer`, `confession`, `breakup`, `risky_find` and `stranger` by ID. Texts may use `{name}`, `{target}`
  and, in `job_offer`, `{job}`.

## Faces

Put PNGs for a resident in a folder named after their ID. They replace the built-in layered face:

```text
custom_content/faces/<resident_or_pack>/
    neutral.png
    happy.png
    angry.png
    sad.png
```

The expressions are `neutral`, `angry`, `sad` and `happy`. A missing expression uses `neutral.png`.
If the folder holds a single PNG, whatever its name, it is used for every expression.
