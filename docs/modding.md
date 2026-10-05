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
- `"light": 5` on an object kind makes it light that many tiles around it after dark. A kind with
  no `use` is scenery; give it `"blocks": false` if it can be walked over.

## Health and weapons

- `data/injuries.json` defines kinds of injury: `name`, `heal_per_day` and `treated_per_day`.
  With `severs_from` and `severs_chance`, a single injury of that kind at least that severe takes
  a limb off with that chance, from 0 to 1.
- `data/body.json` lists under `limbs` what can be lost: a `name` with its article, as it reads
  after a verb, and what is left of the pace of work and of walking without it (`work_pace`,
  `walk_pace`, above 0 and up to 1). A limb ID must be a part of the body in `data/skeleton.json`
  to be seen coming off. Without the file nobody loses anything.
- An item is a weapon if its `properties` give it a `damage` multiplier, e.g. `{"damage": 1.8}`.
  The tag `blade` makes the wounds it leaves cuts.
- An object's use heals with `"heals": true`; `"care_job"` names the job whose worker on duty
  makes it heal at the treated rate.
- An exchange in `data/social.json` is a fight if it has a `damage` range, e.g. `[8, 18]`.
- A map's `graves` lists the tiles where the dead are buried, in the order they are used.

## Buildings

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
- `views`: where each joint is at rest, seen from the `front` and from the right `side`.
- `orders`: for the `front`, `side` and `back`, the bones from the furthest to the nearest.
- `skins`: what is drawn over a bone, a `sprite` or a `strip` from the parts sheet. A sprite's
  `anchor` is the `start`, `middle` or `end` of its bone.
- `clips`: for each view, a list of keyframes that are run through in a loop. A keyframe gives
  bones an angle from rest, or `[angle, scale]` to make one look shorter as well, and may shift
  the whole body with `root`. A positive angle swings a hanging limb to the right of the screen.
  The game uses `idle`, `walk`, `work`, `argue`, `fight` and, over any of them, `carry`. A clip
  that is missing stands still.
- `physics`: gravity in pixels per second squared, how much speed is kept each step (`damping`),
  lost along the ground (`friction`) and given back on landing (`bounce`), how hard limits push
  back, and when a body that lies still goes to sleep.

A resident's look is `assets/sprites/bodies/<resident_id>.png`, laid out as in
`docs/visual-style.md`. One that is missing is drawn in placeholder parts.

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
  `{"tag": "scrap", "to": "scrap_pile"}` for items with a tag, `{"to": "shop_counter"}` for the
  rest. `to` must be a container kind. `injury` and `injury_kind` are what a bad trip does.
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
  too when it is used.
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

## Traits and sounds

`data/traits.json` gives residents tastes: a trait lists `tags` and may set
`item_value_multiplier` (items with a matching tag are worth more to them) and
`food_reaction_bonus` (food with a matching tag also eases their stress).

`data/audio.json` says which sound each event type plays. Sounds are WAV files in
`assets/sounds/`, named as in that file.

Its `music` section says which track plays in each mood: `tracks` maps `day`, `night`, `storm`
and `tension` to WAV files in `assets/music/`, and `night_hours` says when night falls and ends.
A mood left out plays nothing. Trouble (a fight, or someone waiting for advice on something
urgent) is heard over a storm, and a storm over the hour. A track must be written to loop: it
should end where it begins. The built-in ones are written out by `python -m tools.make_art` from
the notes in `tools/art/music.py`.

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
