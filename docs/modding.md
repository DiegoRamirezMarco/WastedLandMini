# Modding / Custom Content

Each custom item or food lives in its own directory:

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

Optional fields include `description`, `base_value`, `tags` and `effects`. `effects` maps a need
(`hunger`, `tiredness`, `social`, `stress`) to the change from using or eating the item.

Packs are loaded at start-up through the same registry as built-in items. A pack is skipped, with
a warning in the log and without stopping the game, if:

- `data.json` is missing, is not valid JSON, is not an object or is larger than 64 KB;
- `id` is not lowercase letters, digits and single underscores, or differs from the folder name;
- `name`, `article` or `category` is missing or empty, or a food's `category` is not `food`;
- `base_value` is negative, `tags` is not a list of strings, or `effects` has non-numeric values;
- the `id` is already taken by a built-in item or an earlier pack.

Fields the game does not know are ignored, so a pack made for a newer version still loads.
Removing a pack never breaks a save: its items stay as inert unknown objects.

`icon.png` is ideally 16×16; any other size is scaled down to it. A pack without an icon shows the
magenta checker placeholder. Face PNGs must be 64×64. See `docs/visual-style.md` for the art rules
and palette.

Use stable lowercase IDs with underscores. Display names may contain spaces and accents. Gameplay must use IDs/tags/categories, never the display name.

## Maps, terrain and objects

These live in `data/` for now; loading them from `custom_content/` comes later.

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
  `data/interactables.json`. Unknown IDs are rejected when the game loads its data.
- Spawns must be on walkable terrain.
- A room with `"roofed": true` is a building: seen from afar it is drawn with its roof on. Its
  rectangle is the floor inside, with walls one tile thick around it and the door in the wall
  below. Leave it out for open places such as a yard or a garden.
- `stock` lists what containers hold at the start and `supplies` what arrives each day:
  `{"container": "pantry_1", "item": "canned_beans", "count": 8, "hour": 7}`. The container must be
  an object whose kind is marked `"container": true`. An item that is not defined is left out.
- Terrain is drawn with the tile of the same name in the tileset; a terrain without a tile shows
  the placeholder. An object kind is drawn with `assets/sprites/objects/<kind>.png`.

## Health and weapons

- `data/injuries.json` defines kinds of injury: `name`, `heal_per_day` and `treated_per_day`.
- An item is a weapon if its `properties` give it a `damage` multiplier, e.g. `{"damage": 1.8}`.
  The tag `blade` makes the wounds it leaves cuts.
- An object's use heals with `"heals": true`; `"care_job"` names the job whose worker on duty
  makes it heal at the treated rate.
- An exchange in `data/social.json` is a fight if it has a `damage` range, e.g. `[8, 18]`.
- A map's `graves` lists the tiles where the dead are buried, in the order they are used.

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
  container kind. `from` and `from_category` name the raw material, if the work needs any.
- `per_minute` changes the worker's needs while on duty, and `sight_bonus` extends how far they see.
- An object's use can require a job to be on duty with `"staffed_by": "bartender"`.

Which resident has which job is set where the settlement is created, in
`SimulationWorld.demo_world`.

## Traits and sounds

`data/traits.json` gives residents tastes: a trait lists `tags` and may set
`item_value_multiplier` (items with a matching tag are worth more to them) and
`food_reaction_bonus` (food with a matching tag also eases their stress).

`data/audio.json` says which sound each event type plays. Sounds are WAV files in
`assets/sounds/`, named as in that file.

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

## Decisions

`data/decisions.json` defines the crisis in which a resident asks for advice: when it opens, how
long the player has, the outcomes the resident may choose and the advice the player may give.

- An outcome's `score` weighs inputs that each run from 0 to 1: `bias` (always 1), `anger`,
  `aggression`, `impulsiveness`, `empathy`, `courage`, `sociability`, `greed`, `stress`,
  `affection` and `resentment` (the last two towards the other person).
- An option's `influence` adds to the score of the outcomes it names. It is advice, not a command.
- An outcome may name an `interaction` from `data/social.json` for the resident to go and have,
  change `needs` and `feelings`, and leave a `memory`.

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
