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
`light`, `category`, `use` and `build`. `category` is `furniture` or `decor` and decides where the kind
appears in the Urbanismo catalogue. A `use` object is itself patched field by field, so
`{"id":"bed", "use":{"minutes":480}}` keeps the sleeping action and changes only its duration.
Set `"use": null` to remove the use entirely. Every placed object of that kind receives the
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
  The game uses `idle`, `work`, `argue` and, over any of them, `carry`; walking, eating and
  fighting use whichever clip the resident's manner names (see Manners below). A clip that is
  missing stands still.
- `doll`: how a body is drawn by hand. `unit` is the pixels of a drawing to one of the skeleton's;
  `canvases` gives the size of the body's and the head's in those units; and each entry of `parts`
  is a bone with the canvas it is drawn on and the two points it runs `from` and `to`. `radius`
  is half the width of the slim example the guide shows. `reach` is half the width of the zone
  the part may be drawn in and `ends` how far that zone goes beyond each joint; give them room,
  so that people can draw other builds than the example. `wears` says what the part is on the
  figure the guide shows, so that it is drawn as one: `skin`, `sleeve`, `hand`, `shirt`, `waist`,
  `leg`, `shin`, `shoe` or `head`; anything else is a plain rounded strip. `whole` is for a part
  that is everything on its canvas. Every other part is cut round at the joints it shares, but for
  `free_start`, a part that does not turn about its first joint, and `free_end`, one left as
  drawn at its second though another starts there, as the trunk at the shoulders. In the game a
  bone that a part is drawn for is as long as the part is on its paper, whatever the `doll` view
  says: of that view the game keeps where the bones between are, the ones that join a limb to
  the trunk, and how high the feet stand. Every part must have its turn in the `doll` order, and
  zones may only overlap where two parts share a joint.
- A doll's own measures are kept in `illustrations/dolls/<id>/build.json`, written by the
  editor: `joints` says how far each joint of the guide was moved along its part, in the
  skeleton's own measure, by part and end (`shin.end` is the ankle, `upper_arm.start` the
  shoulder, and a limb's start moves all of it); `points` how far a joint that goes anywhere was
  moved (`skull.start`, where a head sits on its neck); and `attach` how far from where the
  `doll` view has them the bones that join a limb on end (`clavicle`, `pelvis`). Names carry no
  side: both arms are one. Measures a doll cannot have are ignored whole.
- `doll.former` says how the paper was laid out before it was last changed: the size its
  `canvases` had, and where each part that has since been moved used to run `from`. A drawing of
  that size is taken apart as it was cut then and each part put where it goes now. Change the
  layout again and the layout before this one can no longer be read: redraw or re-save first.
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

`data/manners.json` says in what ways a resident can walk, eat and fight. Each resident has one
of each kind: chosen by the player where the first resident is made or under `Maneras`, and
otherwise one that is always the same for the same resident ID. A manner changes how a thing
looks and nothing of what happens.

- `kinds`: each with a `name` and the `occasion` on which it shows: `walk`, `eat` or `fight`.
  A kind for fighting may have a `weapon_tag`: whoever fights with an item tagged so does it in
  their manner of that kind, and with any other weapon, or none, in their manner of the kind
  that has no `weapon_tag`. The game's own are `blade` for `knife` and `firearm` for `shoot`.
  `prop_tag` is the tag of an item to put in the hand of the figure that tries a manner out; it
  is the `weapon_tag` unless given.
- `manners`: each with its `kind`, a `name`, a `description`, the `clip` of
  `data/skeleton.json` that shows it, and a `rate`: turns of the clip a second, or for walking,
  turns to a step with each foot, which must be a whole number. The first manner of a kind is
  the one the screen that makes the first resident starts on.
- A new manner needs its clip in `data/skeleton.json`, for the `side` and for the `front`. The
  hand that holds things is the right one (the `held_item` anchor): a clip for a weapon moves
  that arm. An eating clip has the hand at the mouth a third of the way through, which is when
  the bite is taken and the crumbs fly.
- Nothing in the game is tagged `firearm` yet. Give an item that tag and a `damage` and it is
  fired the way its owner shoots.

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
- `"tool": {"tag": "hoe", "speed": 1.5}` makes the work that much faster for a worker carrying a
  working item with that tag. At least one item must have the tag.
- `wage` is credits per hour on duty, in place of the settlement's `wage_per_hour`.
- `needed` is how many residents the job takes (1 unless set); with fewer it has a vacancy.
  `priority` says how much it is missed: a vacancy is offered to those in jobs of lower priority.
- An object's use can require a job to be on duty with `"staffed_by": "bartender"`.

Which resident has which job, and which day of the week they have off, is set where the
settlement is created, in `SimulationWorld.demo_world`.

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
    come and `end_text` when they go.
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

## Families

- `data/family.json` holds `start_year`; `old_age` (`from`, `chance_per_year`, `doubles_every`);
  `sleeping_rough` (`per_minute`, `from` how tired, `minutes`); `casual` (`affection` and `desire`
  it takes for two who are no couple); `marriage` (`affection`, `trust`, `accept_affection`); `kin`
  (`affection` and `trust` to begin with, the `events` that tell on whoever sees them happen to
  one of their own, and how much `stress`); `parted_at_gate`; and `children`: the `chance` of
  one, `carried_weeks`, `fertile_until`, the `weeks` a child is a bundle for and the age it is
  `grown_at`, `names` by sex, `mix_spread` and `trait_chance`, how a `bundle` fares, and what is
  made of a child's lot by whoever sees it (`seen`).
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
  who `votes` (`leader`, `council`, `everyone` or `nobody`); the share it takes to approve
  (`approval`), the `leader_weight` and whether there is a `veto`; `term_days` (0 for no
  terms); `succession`, the ways the next leader comes to be in the order they are tried
  (`election`, `council`, `strongest`, `heir`, `following`); `abuse_tolerance` from 0 to 100;
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
- A trait in `data/traits.json` may give `"politics": {"justice_sensitivity": -25}`: so much
  more or less of a leaning.
- `charisma` and `leadership` are sides of a personality like any other, from 0 to 100.
- The game opens `resign` by ID. Its scores may weigh `support`.

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

`data/audio.json` says which sound each event type plays. Sounds are WAV files in
`assets/sounds/`, named as in that file.

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

`dialogue` names a list of lines in `data/dialogue.json`; one is picked for the event text.
`relationship` holds base changes that are scaled by both residents' personalities.

An exchange is part of a romance with `"romance"`: `confession` (at its end the one told answers
from what they feel), `tryst` (two residents alone: it needs the other to want it and nobody
watching) or `breakup` (at its end the couple is over). In `relationship`, a positive `attraction`
is scaled by the spark between the two instead of by their personalities.

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
