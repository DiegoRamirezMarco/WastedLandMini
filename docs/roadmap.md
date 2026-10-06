# Roadmap

Work is split into two tracks that only meet at named points:

- **S — Simulation.** Headless, deterministic, verified by tests and a text event log.
- **P — Presentation.** Pygame scenes, UI and pixel art. Reads simulation state, never owns it.

A simulation milestone is finished without any art. A presentation milestone only starts once the
simulation milestone it depends on is finished. Every milestone has a "done when" check.

Standing rule for every milestone: new state is added to the save format with a backwards-compatible
default, and new behaviour gets a deterministic test.

## Simulation track

### S0 — Foundations — done
- Simulation clock owned by the simulation (game time), fixed tick, pause and speed
- Explicit command path from scenes into the simulation
- Built-in data (`data/*.json`) loaded through registries
- Headless runner that simulates N days and prints the event log
- Versioned save and load round trip

Done when: the same seed produces the same log twice, and a saved world reloads to an equal state.

### S1 — Alive in the settlement — done
- Tile map, rooms and interactables (bed, pantry, campfire)
- Grid pathfinding and movement
- Needs satisfied by using interactables and items
- Utility AI choosing between scored candidate actions

Done when: 3 residents run 7 days headless and no need stays pinned at its maximum.

### S2 — Social loop — done
- Conversations and arguments as actions between residents who are near each other
- Directional relationship changes
- Memories created from what a resident took part in
- Domain events with participants, location and importance

Done when: a week of simulation leaves relationships measurably different from the starting state,
and A -> B has diverged from B -> A for at least one pair.

### S3 — Local knowledge — done
- Witnesses derived from presence and line of sight
- Per-resident knowledge of events
- Rumors with credibility, passed on in conversation

Done when: a resident who was absent does not react to an event until someone tells them.

### S4 — Intervention — done
- Importance bands select intervention candidates
- Decisions generated from events, with options as influence modifiers
- Advice changes utility scores, not outcomes
- Resolution, consequences and settlement history

Done when: one argument runs end to end, and the same advice produces different outcomes for
residents with different personalities.

### S5 — Things matter — done
- Item instances, ownership and containers
- Gifts, trade and theft
- Custom content validation, placeholders for missing content

Done when: a discovered theft changes the victim's relationship with the thief, and a save that
references removed custom content still loads.

### S6 — Work — done
- Jobs as data: a post, shifts, and what working it does
- Residents go to their post for their shift and stay there, unless their body needs something
- Posts that only function while staffed: the cantina serves when someone is behind the bar
- Production: the garden grows the food, the kitchen cooks it
- A guard on duty sees further

Done when: a week passes in which everyone works their shifts, the settlement is fed only by what
its residents grow and cook, and the bar is used only while it is staffed.

### S7 — Consequences — done
- Health and injuries that mend with time, rest and care
- A clinic and a medic's post
- Fights, always preceded by a decision the player can step into
- Weapons as items
- Death, graves and the record of the dead

Done when: a fight never starts without a chance to intervene, the injured recover faster under
the medic's care, and a death removes a resident and everything that depended on them without
breaking the settlement.

### S8 — A working economy — done
- Carrying: produce is hauled from where it is made to where it is used, instead of appearing there
- A workshop job: repairs, and items that wear out
- Trade at a post: a shopkeeper, prices, things bought with work
- Residents can change jobs; the player can suggest who does what
- Days off, and what happens when a post is left empty too long

Done when: a week passes in which nothing reaches a pantry or the pot except in someone's hands,
a tool wears down and comes back from the workshop mended, things are bought with credits earned
on shift, and a post left empty by a death is taken up by someone else.

This also closed what S7 left open: a frightened resident buys a weapon on purpose, and a vacant
post is offered round until someone takes it.

Still open here:
- Residents buy but never sell, and credits spent are simply gone: there is no settlement fund.

S10 closed the rest: trips outside restock the shop, and a repair now uses up a piece of scrap.

### S9 — Deep relationships — done
- Friendship tiers
- Adult romance
- Consensual adult sexual relationships as narrative events
- Breakups
- Jealousy and secrets

Done when: two residents become a couple only after one dares to say so and the other feels the
same; a couple goes off alone and nobody else knows unless they come across them; whoever learns
that their partner was with another turns on both; and a couple that has soured can end, with
the player given a say before each confession and each breakup.

Still open here:
- Who is drawn to whom is fixed per pair, with no notion of what kind of person anyone is drawn to.
- A couple changes nothing about where the two sleep or how they spend the day.
- Jealousy only comes from learning of an affair, never from mere suspicion.
- On the map a couple shows only while one of the two is selected or they are alone together (P9).

### S10 — Beyond the fence — done
- Scavenging as a job: a cart by the gate, one trip a day, hours outside
- Whoever is out there is out of sight and out of reach, and sees nothing of the settlement
- What comes back: finds drawn from a table, carried in by hand to the shop and the scrap piles
- Danger: a trip can end in an injury
- A risky find the player can advise on: go for more, or turn back
- Repairs use up scrap

Done when: a week passes in which the scavenger goes out most days and comes back, more reaches
the shop than it started with, repairs are made with scrap that was brought in, and a find that
looks dangerous is never gone for without the player having had a say.

Still open here:
- Only one resident goes out, alone, and always to the same nowhere: there are no places out there.
- A trip is not seen: the scavenger simply stops being on the map until they are back.

### S11 — What comes from outside — done
- World events as data, rolled hourly with a random generator of their own
- Strangers at the gate: the guard answers, the player advises, and whoever is let in stays
- Newcomers who look for work without being asked
- Caravans that leave goods at the shop
- Dust storms: no work out of doors, no trips, and frayed nerves for whoever is out in one
- Vermin in the pantries

Done when: three weeks pass with the gate opened to whoever asks, in which strangers join and find
themselves work, caravans and storms come and go, nobody is ever let in without a bed for them, and
the settlement still feeds everyone.

Still open here:
- A stranger is a name at the gate until let in. Nobody sees them wait, and nobody else has a say.
- Nobody ever leaves the settlement for good.

S13 closed the rest: residents take shelter from a storm, and raiders come by night.

### S12 — Word from outside — done
- World events that give warning: settled hours before they come
- A radio in the cantina, and radios of one's own: whoever listens hears what is on its way
- Word of it as a fact like any other: heard by those in the room, passed on, and stale once its hour comes
- The scavenger hears the bulletin before leaving, and stays in if a storm would catch them out
- A storm that catches someone outside makes their trip more dangerous

Done when: nobody knows a storm is coming unless they heard it on a radio or were told, the
scavenger who knows stays in and the one who does not is caught out, and word of something that
has already happened is no longer passed on.

Still open here:
- Only the scavenger and the guard do anything about a forecast. Nobody brings anything in ahead
  of a storm or goes to meet a caravan.
- The radio is never wrong, and says nothing but what is on its way: no voices, no music, no
  other settlements.
- The player sees a forecast only once a resident has heard it. From then on it stays on screen
  (P9), with how many know.

### S13 — Dark and danger — done
- Darkness that limits what is seen: at night only what is close, or lit by a fire or a lamp
- Shelter: nobody stays out in a storm who can get under a roof, and work in the open stops
- Raiders by night, who take what they can unless someone stands in their way
- A night watch: a guard who has heard raiders are about stays at the gate past their shift

Done when: by night a thing is witnessed only from close by or in the light; a storm empties the
open ground and the garden; raiders who find nobody at the gate carry off a share of what is
everyone's; and a guard who heard of them on the radio is there when they come, with the player
given a say in whether to stand or step aside.

Still open here:
- Raiders only take things. They never hurt anyone but the guard, and never come twice in a night.
- Only the guard keeps watch. Nobody else can be roused to help, and nobody takes a turn.
- The dark hides what happens but changes nothing else: nobody is afraid of it or stays in.
- Nobody lights or puts out a lamp: they burn all night by themselves.

### S14 — Bodies that break — done
- Limbs as data: which ones a resident can lose for good, and what going without each one costs
- A cut bad enough may take one off, by luck. It is an event of its own, and a fact that those
  who saw it know and pass on
- Short of an arm the same work takes longer; short of a leg the same walk does
- Events carry the particulars of a blow: who dealt it, how hard, and where a body fell

Done when: a blade in a fight or at the gate can cost a limb and a lesser blow never does, the
limb stays lost through saving and loading while the wound itself mends, a maimed resident still
works their shifts and looks after themselves, and the same seed maims the same people.

Still open here:
- Nobody is afraid of whoever maimed them, and nobody looks after the maimed any differently.
- There is no crutch or false limb to buy or make: what is lost stays lost, and so does its cost.
- Only cuts take limbs. A fall, a machine or a trip outside never does more than its injury.

## Presentation track

### P0 — Style contract (no dependency) — done
- Internal resolution and integer scaling
- Tile size, sprite sizes and sheet layout
- Shared palette
- Asset naming and folder layout
- Asset loader with a placeholder for anything missing

Done when: the rules are written in `docs/visual-style.md` and a missing PNG renders a placeholder
instead of crashing.

### P1 — The settlement (needs S1) — done
- Ground, floor, wall, fence and furniture tiles
- Resident body sprites with idle and walk
- Global view drawn from the real map and resident positions

### P2 — HUD (needs S2) — done
- Bitmap font
- Clock and speed controls
- Resident card showing needs and current action
- `!` marker driven by real events
- Event log panel

### P3 — Faces and interaction (needs S4) — done
- Modular faces: base, eyes, brows, mouth and hair, combined into expressions
- Optional custom PNG faces with a single-image fallback
- Interaction view with dialogue box and selectable options

### P4 — Objects and feedback (needs S5) — done
- Item and food icons
- Small presentation-only animations
- Sound effects reacting to domain events

### P5 — A real settlement — done
- A map larger than the screen, with a scrolling view
- Shacks and premises that are walked into: cantina, storehouse, workshop, two houses, garden, gate
- Art for the new places, posts and residents
- A view that zooms: three steps up close, and an overview with the roofs on and a face per resident

### P6 — Atmosphere — done
- Day and night: light changes, and fires and lamps matter
- Roofs that hide a building until someone looks inside
- A minimap, and jumping to whoever needs attention
- More wear and scrap: the place should look salvaged

Nothing is left open here: S13 made darkness limit what residents see, and P9 let the minimap be
put away.

### P7 — The economy on screen (needs S8) — done
- A job board: who holds which post, which are vacant, and suggesting who should do what
- Prices at the counter, and what each resident can afford
- The condition of things, on the card and in containers
- Loads shown in a resident's hands while they carry them
- Shelves and stock that make the shop look like one

Still open here: a suggestion from the board always comes with the same encouragement, though the
simulation would take any of the three advices. (P9 made the board say why someone cannot be asked.)

### P8 — Music — done
- Synthesised loops written by the art tool, like the sound effects
- A track for the day, the night, a storm and trouble, chosen from what is going on
- One track fading into the next, under the sound effects, and silenced with them

Taken out since: once listened to, the synthesised loops were a torment, and the game now comes
with no music at all. What chooses a track for the mood and fades one into the next is still
there, waiting for music worth playing: a WAV in `assets/music/` and its name in `data/audio.json`.

### P9 — At a glance (needs S9 to S13) — done
- What the settlement knows is coming, on screen: each forecast and how many have heard it
- Who is outside the settlement, where they can be seen and picked
- Partner and friends of whoever is selected marked on the map, and a couple alone marked as such
- The job board says why someone cannot be asked just now
- Sun or moon by the clock, and a minimap that can be put away

Still open here:
- A trip outside is still not seen: only the face of whoever is on it, waiting in a corner.
- A stranger at the gate and raiders are words and a decision. Nobody is drawn at the gate.
- A couple shows only while one of the two is selected, or while they are alone together.

### P10 — Bodies with bones (needs S14) — done
- A skeleton for every resident: sixteen joints, bones between them, parts drawn over the bones
- New proportions, with arms and legs to speak of, in the same 16×24 space
- Poses as data: standing, walking, working, arguing, fighting, carrying
- Blows that stagger, hard ones that knock down, and the dead falling where they stood
- Limbs that are cut loose from the skeleton and fly off as bodies of their own
- No physics for anyone who is merely going about their day, and sleep for whatever lies still
- A room to try it in: `python -m tools.skeleton_lab`

Done when: a hundred residents walking about cost no physics at all; a blow, a lost limb and a
death each show on the bodies they happen to; whatever falls comes to rest and stops being worked
out; and a resident who has lost a limb is drawn without it after saving and loading.

Still open here:
- Bodies only collide with the ground. A falling body passes through walls, furniture and others.
- A body lies in the plane of the screen: it falls to one side, never towards the viewer or away.
- A one-legged resident walks as before, on the leg that is left, with no crutch and no limp.
- Nothing is worn or held: a weapon is still an icon over the head, and clothes are the look.
- Nobody carries the dead to their grave. The body lies a while and is gone.
- The interaction view still shows faces only.

### P11 — The frame of the picture — done
The first step towards `docs/concept/visual-target.png`, the look the game is meant to have.

- A larger canvas, 800×450, cut into a bar, a menu, the map, a panel and a dock
- The bar: day, hour, speed, and what the settlement has in people, beds, food and scrap
- The menu: residents, posts, stores, events and the minimap
- The panel: a resident in full, with a face, bars, traits, who matters to them and what they
  carry; or everybody at a glance, to be picked there
- The dock: advice is asked for under the map, with two large faces and a speech bubble, and the
  settlement left on show. With nobody asking, it shows the exchange the selected resident is in
- On the map: a sign with the name of every place, and a bubble for what each resident is doing

Still open here:
- The bar counts only what exists: there is no water, energy or medicine to count yet (S15).
- The menu has no construction or research, because there is none (S16, S17), and no radio screen.
- Traits are two. The panel has room for more than the settlement has.
- The speech in the dock is drawn from a handful of lines per kind of exchange.

### P12 — Buildings that stand up — done
- A roofed building is one picture, with a front two tiles high, a cloth over its door and its
  name on a sign over the eave
- It rises above the wall at its back, and hides by that much whatever stands behind it
- Looked into, the picture is not drawn and the inside shows, as before
- Any building's picture can be replaced from `custom_content/buildings/`, at any size and in any
  colours, without touching the game's own art

Still open here:
- The pictures are put together from the same tiles as before. They stand up, but they are plain.
- There is no horizon, no watchtower, no strings of lights, and dusk is as blue as the night.
- Places without a roof, such as the garden and the gate, are still only ground with a sign.
- Bodies are the size they were.

### P13 — Illustrations — under way
After P11 and P12 the look was still home-made, and it was settled that art drawn from code would
not do: the pictures are to be illustrations made outside the game, with an image generator.

Done:
- The window is put together from illustrations first and the canvas over them, so that a picture
  is shown at its full resolution and never doubled
- An illustrated ground for the whole map, with what stands on it drawn over; night and storms
  darken it too
- Illustrated buildings, faces at any size, and a skin for the large parts of the screen
- All of it optional, file by file: `illustrations/README.md` says what goes where
- **Paper dolls**: a resident's body and head drawn once over a guide, cut apart at the joints
  and moved by the skeleton, as smooth pictures on the window. One drawing from the side does
  for every pose and both ways of facing. Hands, feet and hips are parts of their own, and the
  doll has its own build: longer limbs, the near arm set back and the near leg over the hips
- **An editor in the game** to draw them: two canvases over the guide, brushes, a rubber, a
  bucket, undo, a mannequin to start from, and the doll moving beside the drawing

Still open here:
- A doll is always seen from the side, and is drawn over everything else on the map: someone
  standing behind a table is in front of it
- The editor's brush has hard edges and the palette's colours only. There is no picking a colour
  off the drawing, no zoom, and no layers
- What a doll carries or wears is not shown on it
- The pictures themselves. The first six, for one whole screen, are being made
- Text is still the pixel font, and bars, buttons and icons are still pixel art
- Furniture, objects and residents are still pixel art, standing on an illustrated ground
- A drawn building hides nobody: it goes under everything that stands on the map
- Places without a roof have no picture of their own, and an open building shows its pixel floor

### P14 — Voices — done
- What is said in the dock is said out loud: whoever starts a line in an exchange says it, and
  whoever asks for advice asks it, over anything else
- Lines are spoken by Piper, a neural voice that runs on the machine. Twelve voices to choose
  from: two men and a woman from Spain, a woman from Argentina, a man and a woman from Mexico,
  and a man and a woman each from Germany, France and America, who read Spanish by the rules of
  their own language and so with its accent. A line is spoken once and kept; the game asks for
  the ones it has not heard, on the side, and a tool speaks them all beforehand
- A voice is a model and six controls applied to what it said: tone, speed, tremble, roughness,
  metal and scramble. Nine kinds come ready made: young man and woman, old man and woman, boy,
  girl, monster, robot and one that cannot be understood
- **An editor in the game** (`Voz`, or `F3`): who speaks, the kind of voice, a slider for each
  control, and the voice heard as soon as a slider is let go
- Everyone in the settlement starts with a voice of their own, and a chosen one is kept in
  `voices/residents/`
- All of it optional: without Piper, a model, numpy or a sound card, the game is silent

Still open here:
- Nobody has listened to it with a critical ear: the effects were checked by measuring them,
  not by hearing them
- Tone moves the whole voice, pitch and throat together. There is no changing one without the other
- Only the selected resident's exchange is heard. Nothing is heard of who is far or near, and
  nobody mutters to themselves
- A line is said in the same way whatever the mood of whoever says it
- At x4 and x16 lines change faster than they can be said, and most go unsaid

### P15 — Houses drawn by hand — done
Every house and premises is to be drawable in the game as residents are: in parts, each over a
guide, and put together by the game.

- **The walls** of a building, as a part of their own
- **The inside**, empty: the floor and whatever belongs to the room itself, with nothing standing
  in it
- **The roof as seen from outside**, which is what shows until the building is looked into
- **The door**, a part of its own, so that it can be drawn apart from the wall it is in
- Each building its own drawing, kept as a resident's is, and optional in the same way: a
  building nobody has drawn looks as it does now
- An editor for them in the game, after the pattern of the one for residents

Not part of the building drawing itself: furniture and objects remain separate layers. Their
definitions and sprites can now be overridden under `custom_content/objects/`, while inventory
items open their own data-and-icon editor when clicked.

Settled in the editor:
- The four parts share a canvas at two pixels for every pixel of the map art. Its size follows the
  room, so it is also the exact resolution shown in the window at the default zoom
- The door's frame comes from the door tile authored in the map. The name sign remains game text,
  positioned by the room rather than baked into any drawing
- The door is a separate foreground part but does not animate open. The roof is the part exchanged:
  with it off, the empty inside lies below furniture and residents and the walls and door lie above
- Tabs and a distinct guide show one part at a time. All four keep the same origin, and the preview
  switches between the assembled outside and inside
- Old one-piece building illustrations remain valid. New drawings also work when the map ground
  itself has not been illustrated, and every undrawn building keeps the old pixel art

### S15 — What the settlement lives on — done

- **Water is a thirst of each resident's own**, a need like hunger: whoever is thirsty goes and
  drinks, from water that someone's work brings in
- **Energy is light and word from outside**: a generator that someone has to feed. Without it
  the lamps give no light at night, and the radio gives no warning
- **Mood is a state of its own**, apart from stress: it rises and falls slowly with what a
  resident lives through, and with it low they work worse and argue more

Done when: thirst is saved and drives residents to drink from stocked water, expeditions can bring
water and generator fuel back through the same hauling rules as other finds, lamps and radio
warnings depend on fuel, and low mood makes work slower and arguments likelier without breaking a
four-week headless run.

Added once it had been run for longer than that:
- **Drawing water is a post.** Left to what trips outside bring, the tank ran dry in five weeks.
  Now someone works it, as someone works the garden; the post stands empty when a settlement
  starts, and is offered round like any other
- **Going without sickens, and in the end kills.** A thirst or a hunger that nothing in the
  settlement can answer no longer keeps anyone from their bed or their post, which had brought
  everything to a stop. Left at its worst it wears their health down instead, and notice is given
- Trips outside bring more fuel and less water, the garden yields a quarter more, and nobody who
  gets out of bed in the south house is walled in by the other beds

Done when: ten weeks pass, with three different seeds, in which someone takes up the water, the
tank and the generator never run out, the pantries never empty and nobody dies; and a settlement
with no water at all goes on working and sleeping, is told so every day, and loses people to it
only after days.

Still open here:
- Whoever takes up the water leaves the bar, and nobody takes the bar after them.
- Nobody feeds the generator as a job: it lives on what trips outside happen to bring.
- A save from before keeps the south house as it was, with the beds that wall people in.

Still to settle:
- Medicine: used up by the clinic's care, and brought in from outside
- Materials: the scrap there already is, later spent on building
- A limit to how many can live here, set by the beds there are
- How dangerous it is outside, as something the settlement knows or does not

### S16 — Building — planned
- Things to build, as data: what they cost, how long they take, who builds them
- Sites: materials carried to them, work done at them, and the thing standing at the end
- The player proposes what to build and where. The residents do it, or do not

### S17 — Research — planned
- Things to work out, as data: what each needs and what it opens up
- A post where it is done, and time on shift that goes towards it

Each of S15, S16 and S17 is followed by its screen: the counters in the bar, and the construction
and research entries of the menu.

### S18 — A beginning — done
- **A new settlement is an empty plot** (`data/maps/homestead.json`): a fence, a gate, some scrap
  lying about, and nobody
- **The first resident is made by the player**: a name, an age, a way of being and up to two
  traits. Only a settlement nobody has ever lived in takes one. Everyone after comes by the gate
- **An opening made of steps, as data** (`data/tutorial.json`): what to do, what counts as done,
  and what the settlement is handed for it. A hoe, scrap, thirty tins and half a tank of water are
  where a settlement's stores come from
- A step is done by what the settlement has become, however it got there, and with time stopped
  too: a building or an object standing, someone in a job, time gone by, an answer given
- **A step may also wait for something the player does with their own hands**, which the
  simulation cannot see and knows only by name: a colour chosen, a stroke, a drawing saved. That
  is how the opening teaches drawing without the simulation knowing what a drawing is
- **The world outside keeps away** until the opening is over: no strangers, caravans, storms,
  vermin or raiders
- **One stranger is brought on purpose**, for whoever is there to answer, guard or not. It is the
  step that teaches advice: the player says what they think and the resident decides
- **Nothing can be put down that leaves something out of reach.** Urbanismo refuses whatever
  would wall in a bed, a container or a post, block a doorway, or put up a building whose door
  nobody could get to. What was already out of reach stops nothing else
- A settlement with no generator is no longer told every night that its fuel ran out

Done when: the opening can be gone through from an empty plot to the last step by commands
alone; each step hands over what it says; no stranger comes without a bed, and nothing else comes
from outside until the end; the opening is saved where it was and goes on from there; the two
people it leaves, one in the garden and one at the water, are both alive and well four weeks on
(ten were run, with three seeds); and the same seed settles the same way twice.

Added once it had been played:
- **A settlement too small to keep its gate still hears a knock.** With nobody whose job it is,
  whoever is in and awake answers a stranger, where before the stranger found the gate shut and
  nobody could ever join a settlement of two. With a guard it is still the guard, on their shift
- **What is brought back from outside goes where the settlement has room for it.** Finds went
  only to the shop, the scrap piles and the generator, and whoever had none of those was left
  holding them and never set out again. Now food goes to a pantry and the rest to a crate when
  the place a find belongs is not there
- The opening says both things before it ends: that people keep coming while there is a bed,
  and that a cart and the scavenging post send someone out

Done when: ten weeks on from the opening, with three seeds, a settlement given beds to spare
and no guard has taken in everyone there is to come and lost nobody; with a cart, one of them
takes it up unasked and goes out most days; and with no bed to spare nobody comes at all.

Still open here:
- Four people may ever come to the gate, the four the game has by name. After them nobody does
- Nobody is sent anywhere: a post is proposed and whoever holds it goes out when their shift says
- A founder who turns the stranger away is alone, and alone they do not last: after a couple of
  days they leave the garden for the water, which matters more to the settlement on paper, and
  starve about three weeks in with the tank full. Whoever has the last hands on what feeds
  everyone should not be talked out of it by an empty post
- Someone who cannot get to a bed still goes round in circles by the fire instead of doing
  anything else. Urbanismo no longer lets it happen, but an old save may have it
- With everyone dead the settlement simply stands empty: there is no ending, and nothing to do
  but go back to the menu
- Everything put down in Urbanismo is free and stands at once (S16)
- There is one save, and a new settlement saved with `F5` takes its place

### S19 — Tastes of their own — done
Until now what a resident liked was what their traits said, and so the same for everyone who
had the trait: a trait whose tags matched an item's raised what it was worth to them and the
pleasure of eating it.
- **A profile of tastes for each resident**, kept apart from `Resident`: how much they like or
  loathe a category, a taste tag, and one item in particular, from -100 to 100. It starts with
  what their traits give them and fills as they meet things. It is saved, and a save from
  before loads with profiles that are empty and fill the same way
- **A taste has two parts, kept apart**: the leaning they came with, and what they have learned
  since. Only the leaning is made here; what is learned stays at nothing until S20 moves it.
  Both are in the save from the first day, so that S20 changes no save
- **A leaning is made the first time it is needed**, and kept. Asked for a taste they do not
  have, the profile makes one from the settlement's seed, the resident and the tag: the same
  three always give the same leaning, two residents may well get opposite ones, and nothing is
  drawn from the stream the rest of the simulation draws from, so that meeting a new taste
  changes nothing else that happens
- **Taste tags are apart from the tags the game works by.** An item's `preference_tags`
  (`sweet`, `slimy`, `fermented`) are what tastes go by. Its `tags` (`food`, `weapon`, `custom`)
  are for rules, searching and sorting, and never make a taste. The game's own items are given
  their taste tags in their data, and whatever among their `tags` was only ever a taste goes
  there
- **There is no list of taste tags.** Whatever an item carries is one: a pack that brings
  `alien` or `crunchy` needs no code, and residents come to like or loathe it as they meet it.
  They are checked like the rest of an item's data, the game's own and a pack's alike: text, not
  empty, lower case with underscores, put in that form where they can be and each counted once
- **Tastes go by stable IDs, categories and taste tags**, never by names. A taste for a kind of
  thing the game does not have yet does nothing until something carries it
- **A reaction in five steps**: hated, disliked, neutral, liked, loved. It is worked out from
  the item itself, its category and its taste tags, and then from the state the resident is in,
  who it came from, and what the thing means to them. The item itself counts for more than its
  tags, the more so the stronger the feeling for it, without silencing them: someone who loathes
  `slimy` may love one slimy thing. About one item in seven is such a thing to any one resident
- **A reaction does something**: to mood and stress, to the affection and trust felt for whoever
  gave it, and to whether it is asked for again, traded away or stolen
- **What a thing is worth to someone** is its base value with their tastes, their needs, what it
  means to them and how scarce it is, in place of the traits' multiplier. Trade, gifts, theft and
  what is chosen to eat all go by it
- **A favourite and a loathed food, and a favourite and a loathed thing**, read off the profile
- **What the player has found out is kept apart from the taste itself**, for each resident and
  each taste: unknown, suspected, known. That a taste has been made does not make it known. It
  moves on what is seen to happen and never on the numbers: a meal eaten with relish, a gift
  taken badly, a thing asked for by name, a trade turned down over it, something said about it
  unprompted, each by how much it shows. A reaction shows only the tastes that pulled the way it
  went: one that was outweighed, or that hunger got the better of, stays out of sight. The taste
  a trait gives is known from the start, as the trait is
- **A taste nothing carries any longer stays in the save.** With the pack that brought `alien`
  taken out, the tastes for it load as they were, do nothing, and are there if it comes back
- A resident chooses a gift by what they know of the other, not by what the world knows
- A reaction, and a taste found out, are each a domain event
- The profile, the working out of a reaction, what the player has found out and the ties to
  items are separate small classes. None of it needs a language model

Done when: with one seed two residents take the same meal differently, and it shows in their mood
and in how they feel about whoever handed it over; an item added by a pack with a taste tag the
game has never had is reacted to by everyone who eats it, differently, and the same way when the
same seed is run again; a favourite is worth more to its owner than its base value and is the
last thing they trade; over a four-week headless run at least one taste of every resident goes
from unknown to known through what happened; a save from before loads; and a save made with a
pack loads without it.

Tests it is not done without: a liking by taste tag and a loathing; a taste made on meeting a new
tag; the same resident and tag always giving the same leaning, and two residents different ones;
a pack's taste tag working with no code of its own; a tag the game works by making no taste; one
item liked over taste tags that are loathed; finding out step by step, and what the player knows
kept apart from what is so; what a thing is worth to someone; tastes made on the way kept by
saving and loading; a save with tastes for a pack that is gone; and the module imported without
pygame.

Still open here:
- A taste is made by eating, using or being handed a thing. Buying it, carrying it or stealing it
  makes none, and nobody has a taste for what they have never had
- The player sees everything that is taken well or badly, wherever it happens and in the dark
- What a resident has seen of another's tastes is used for choosing a present and for nothing
  else: not for what to offer in a swap, and not for what to cook
- Nobody passes on what they know of someone's tastes
- A taste tag a pack brings is spoken of by its ID, with spaces for its underscores: a pack has
  nowhere to give it a name
- Tastes for kinds of thing the game does not have, such as music beyond the one radio, reading,
  clothes or animals, have nothing to show themselves on
- A meal is taken the same way every time: nobody tires of the stew they have had all week
- An item edited in the game before this, and that the game does not have of its own, has no
  taste tags until they are given to it in the item editor (P22)

### S20 — Tastes in people, and tastes that change (needs S19) — done
- **Hidden tastes in people**, as data like the others: for those sure of themselves, for the
  aggressive, for the generous, for the lively, for whoever keeps the watch, for gossip, and for
  being told what to do. Each says what the other has to be like, what post they have to hold or
  what has to be passing between the two, and which feeling it moves. They weigh on what is felt
  for someone at the end of a friendly exchange and on being told a rumour, one way only as
  every relationship is
- **Being told what to do** counts for more or less with a resident by that taste: the player's
  advice weighs up to two fifths more or less
- They are found out as tastes for things are, from what passes between people
- **What is lived moves what has been learned, and never the leaning**: a taste is the two
  together. It moves by how much the thing mattered, so that one meal like any other hardly
  counts and nearly dying of one counts for a great deal. A good meal with `spicy` in it adds to
  the liking for it; being taken ill by `seafood` takes from it; so do who a thing came from,
  coming to depend on what is consumed, having a thing often and what it is tied to
- **The first time of a taste leaves a small mark of its own**: the leaning is made, the meal is
  taken as the two say, and a little is learned from how it went
- **A meal may turn on whoever eats it**: an item with a `sickens` property does, with that
  chance. The bundled pizza has one. They are hurt, turn against the thing and, less, against
  what it tasted of, by how bad it was
- **What moved a taste is remembered** ("Enfermé después de comer una pizza radiactiva"), and
  the memory does not move it a second time: nothing reads it back
- **Nobody knows a taste has moved until they see it**: what the player has of it is how it
  looked the last time it showed. Seen to go the other way, it is back to being suspected, the
  new way, and found out again from there. The same goes for each resident who was there

Done when: two residents take the same person, the same piece of gossip and the same piece of
advice differently, and the relationship shows it; someone taken ill by a meal likes its taste
tags less afterwards, has a memory that says why, and stops choosing what carries them; and ten
weeks pass with three seeds without anyone's tastes all running to one end of the scale.

Tests it is not done without: something good adding to what is learned and something bad taking
from it, each by how much it mattered; the leaning left as it was; and a taste moved once by an
event and its memory together, not twice.

Still open here:
- Nothing in the game is funny: being drawn to the funny is being drawn to the lively
- Whoever is in charge is whoever keeps the watch. There is nobody else to distrust
- A taste in people moves what is felt for someone and nothing else: not who is sought out to
  talk to, nor who is believed
- Tastes in people are not learned: nothing lived through moves them yet
- Nobody tires of what they have every day: having a thing again only ever takes a taste the
  way it was already going
- Coming to depend on something is having a taste for it grow faster and farther. Nobody goes
  looking for it, and nobody misses it
- A grief, a fight or a death moves no taste: only a meal that turns on someone does
- Being told what to do is being given advice by the player. No resident orders another about
- Of the game's own foods none can make anyone ill

### S21 — Walking at any angle — done
Everybody walked like a rook: along the rows and the columns of the map, turning square corners
on open ground. Asked for by hand: that they go in every direction.
- **A way is straight wherever nothing is in it.** `find_path` first tries the line from where
  someone stands to where they are going, at whatever angle that is, and only looks for a way
  round when something is on it. That way round is then pulled straight between its corners
- **A step is to any of the eight tiles around**, and a walk is still a list of tiles, each
  beside the last: where a resident is, what they are next to and what is saved are tiles as
  before. Nobody cuts the corner of a wall or squeezes between two things that touch at one
- **The trail says where the line runs.** For each tile stepped on, `Resident.trail` gives the
  point of the line that is on it, up to half a tile off its middle. It is for whoever draws
  them, it is not saved, and nothing that happens goes by it. Stopped short part-way along a
  line, they take the next minute to step onto the middle of their tile
- Standing next to something to use it, or to someone to talk to them, is still beside it and
  not at its corner

Done when: across open ground a resident's whole walk lies on one line that is neither along the
map nor square to it, and two days of the settlement pass with nobody cutting a corner.

Still open here:
- **A step at a slant covers more ground in the same minute**: going diagonally they are up to
  four tenths faster than going along a row
- How far something is, when it is weighed against how much it is wanted, is still counted in
  rows and columns
- The way round something is a good one, not always the shortest there is
- Nobody steps aside for anybody: two residents can still walk through one another

### P16 — The way in (needs S18) — done
- **A main menu**: go on with the settlement being played or the saved one, start a new one,
  open the settlement that comes ready made, or leave. `Esc` on the map goes there, and no longer
  out of the game. A settlement being played is only thrown away when asked twice
- **Where the first resident is made**: a name, an age, a slider for each side of their way of
  being with what it does, and traits. There is no look to choose: they are drawn (P17)
- **Nobody is a placeholder**: until somebody draws them, whoever has no art under their own ID
  borrows one of the game's looks, always the same for the same ID
- **The step in hand, on show**: in a panel over the map and above the map in Urbanismo, with
  the entry of the menu or the controls it is about blinking, and a button where only a button
  will do

Still open here:
- The menu is words on black: no picture, no music
- The opening says where to click and locks nothing
- It is read, not heard: nobody says the steps out loud

### P17 — Everything is drawn (needs S18) — done
In a new settlement nothing comes ready made: whoever is made is drawn, and so is whatever is
put down. The opening teaches how.

- **Whoever is made is drawn next.** The screen where the first resident is made leads straight
  to the one where they are drawn, body and head
- **Drawing is taught a thing at a time**, each lesson done by doing it: choosing a colour,
  painting a stroke, pouring the bucket, undoing, and then drawing them whole and saving. The
  lesson stands where the editor's notes do, and what it is about blinks
- **A building put down in the opening opens its drawing**: one lesson for its four parts, one
  to draw them and save
- **Furniture and loose objects can be drawn** (`scenes/object_editor.py`): one picture a kind,
  which every object of that kind wears, kept in `illustrations/objects/<kind>.png`. Four pixels
  to one of the map's art, over a guide of the tiles it stands on and the room it has above
  them, with the game's own art to start from and the picture as it will look on the map beside
- **Drawn furniture is shown at the resolution of the window**, under the pixel art of the map
  and over the floor of a drawn building, and in the layout editor too
- In the opening, each first bed, crate, pantry, water tank, crop bed and fire is drawn as it is
  put down. Afterwards anything is drawn by selecting it in Urbanismo and pressing `Arte`
- Out of a drawing opened from Urbanismo is back to Urbanismo, to go on putting things down
- With no folder for drawings there are no editors, and the steps that teach drawing are passed over

Still open here:
- A drawn object is one still picture: a fire that somebody has drawn no longer flickers
- Drawn furniture lies under everything else on the map: someone in the game's own pixel art
  standing behind a tall drawn thing is seen in front of it
- Drawings go by name, not by settlement: a new settlement finds `shack_1`, the bed and anyone
  of the same name already drawn, as the last one left them
- The lessons do not check what was drawn, only that the tool was used: a scribble passes
- What is carried, worn or grown is still the game's own art, and so is the ground
- Nobody is taught to give a resident a voice

### P18 — Paper that can be read (needs P17) — done
Tried by hand, the paper of the editors could not be made out: frames one over another and
patches of colour with no shape to them. What is traced over now says what it is.

- **Each part of a body has a zone of its own**, where the old frames ran over one another: a
  limb is three zones in a row, tinted by the side of the body it is on, every other one a
  little darker
- **The cuts are drawn**: a dashed line across the limb at every joint a drawing is cut at,
  which is also where it bends
- **Every part is named on the paper**, and each limb says whether it is the one in front or
  the one behind, and the figure which way it faces
- **A figure to go by, not patches of colour**: under the zones stands someone drawn with a
  dark line round them, in a shirt, trousers and shoes, with hands and a face. It is put
  together from what each part is said to wear in the template (`wears`), and cut straight at
  the cuts, with the round end the game gives a limb where nothing else begins
- **Until something is drawn, it is that figure that walks in the preview**, to show what the
  parts add up to
- **A building's guide names its stretches** (back wall, sides, front, the gap for the door,
  floor, roof, door) and shows the game's own art of the part under them. For the inside,
  which the game has no picture of, a floor of boards
- **An object's guide shows the game's own picture of it under its zones**, and what the two
  colours mean is said beside the paper

Still open here:
- The figure is put together from shapes by code. It reads as a person, and it is no
  illustration: a better one would be drawn by hand and kept as a picture
- There is one figure, of one build, in one set of clothes. Nothing shows a stout body, a
  skirt, long hair or a hat, which the zones leave room for
- The parts of a limb still lie in a row touching each other, so that a limb can be drawn in
  one go. Nothing shows them pulled apart
- While one part of a building is drawn the other three are not seen under it, only in the
  small picture beside
- The example of an object is the game's own pixel art, enlarged

### P19 — A body of one's own (needs P18) — done
A doll was laid over one body made for all of them, and drawn out to fit it: a trunk came out
longer than it was drawn. Now the paper is the measure.

- **Every part is as long on the doll as on its paper.** Each doll stands on a body plan of its
  own, made from its drawing: nothing is drawn out between its joints any more
- **The joints of the guide can be dragged** (`Medidas`): a part is made longer or shorter and
  whatever hangs from it follows, as long as it was. Where a limb starts moves all of it, to
  make room on the paper. Someone short in the leg is made by shortening the legs there
- **Limbs and head are joined on where they are put**: on the figure beside the paper the
  shoulders, the legs and the head are dragged to their place, and the head's neck can be moved
  on its own paper too
- Both sides of a body share their measures, and they are kept beside the drawings
- **The measures a doll starts from are data** (`doll.build`), and are the ones the player set
  for Raúl: a longer trunk and longer limbs than the guide first had. Someone not drawn yet
  begins with them, and `Medidas de partida` goes back to them. Whoever was drawn before there
  were measures is left exactly as drawn
- A joint goes no further than the doll can have it: no part shorter than a sliver, none off
  its paper, none over a part it does not meet
- The guide, the figure under it and the walking figure all follow as a joint is dragged, and
  with the measures in hand nothing is painted
- The opening has a lesson for it, done by dragging a joint
- On the map a resident with a doll is posed, struck and knocked down on their own body

Still open here:
- What is already painted does not move with the joints: measures are best set before drawing
- Dragging a joint is not undone with `Ctrl+Z`; `Medidas de partida` puts them all back
- Both sides are always alike: nobody has one arm longer than the other
- There is no making a part wider on the guide, only longer. Wider is simply drawn wider
- The whole doll cannot be made larger or smaller at a stroke
- The game's own pixel bodies, for whoever has not been drawn, are all of one build

### P20 — Room to draw, and more to draw with (needs P19) — done
- **A wider paper for the body**, 384 across where it was 320: the arms, the trunk and the legs
  each stand in columns of their own, and an arm can be made a good deal longer without running
  into a leg. The head and the moving figure went to the right edge of the screen to make room
- **Drawings made on the narrower paper are still read**: taken apart as they were cut and each
  part put where it goes now, with nothing redrawn or resized. Their files are left as they are
  until they are saved again
- **Shapes laid down in one go**, in all three drawing screens: a straight line, a box, an oval
  and a polygon, hollow or filled, seen on the paper while they are made. A polygon is clicked
  out corner by corner and closed with a right click, `Enter` or a click on its first corner
- **Any colour**: under the ready ones, a field to pick from, round the colours from left to
  right, lighter above and darker below, full in its upper half and muted in its lower, with the
  greys beside it. The colour in hand is shown by the word
- `Esc` lets go of a shape half made before it leaves the drawing

Still open here:
- A colour is picked by eye: there is no taking one off the drawing, and no typing one in
- A colour picked off the field is not kept anywhere: the next one is picked again
- There is no zoom, no layers, no moving or resizing what has been drawn
- Shapes have hard edges, like the brush
- The trunk still stands over the legs on the paper: a very long trunk and very long legs meet
- The paper cannot be laid out a third way without losing the way to read the first

### P21 — What is in the hand (needs P20) — done
Tried by hand, a meal drawn at 64×64 in the item editor was eight pixels across in the hand,
whatever had been drawn on it, and the crumbs of a bite were four squares of fixed colours.
- **What is held is the picture as it was drawn**, not its 16×16 icon: without the empty paper
  round it, 11 map pixels along its longer side, on the window at the window's own resolution
- **A drawn resident carries their load in their hands** the same way
- **A meal is seen going**: a bite out of its outline, on the side of the mouth, at each fifth of
  the way through
- **Crumbs of the food's own colours**: chips of several shapes and sizes that are tossed up,
  turn, fall to the feet, hop and fade, the same way at the same moment every time
- **An item opened again in its editor is as finely drawn as it was saved**: it was being opened
  from its 16×16 icon, and saving it again lost what had been drawn

Still open here:
- Everything eaten is bitten and sheds crumbs alike: a tin loses pieces as a slice does
- What is held does not turn with the hand, and the hand is behind it, not round it
- Lists and inventories still show the 16×16 icon, twice as large in a resident's panel
- The game's own pixel bodies, on the canvas, hold it at the canvas's resolution

### P22 — What they like, as far as it is known (needs S19) — done
- **A resident's tastes in their panel, as the player knows them.** The panel has two faces,
  switched with a button on the first heading under the bars: how they live, as before, and
  `Gustos`. There, one taste to a line, the surest first: "Parece gustarle", "Parece darle igual"
  or "Parece no gustarle" for what is suspected; "Le encanta", "Le gusta", "Le da igual", "No le
  gusta" or "Lo detesta" for what is known; and `???` for what has not shown, which stands alone
  while nothing has. Never a number, and nothing that has not been found out
- **A reaction is seen where it happens**: a heart or a cross in a bubble over the head of
  whoever eats, uses or is handed something, and a line in the log
- **Notice when something is found out**: an eye over their head after the reaction, and the
  line of it in the log in a colour of its own
- **The item editor has a field for taste tags**, beside the one for the tags the game works by.
  They are written as they are kept, and one that cannot be a taste tag is not saved.
  `docs/modding.md` says which is which

Done when: a new settlement shows `???` for everyone; a meal a resident loves is seen to be loved
on the map, and their panel says so afterwards; and nowhere on the screen is there a figure for
a taste.

Still open here:
- The face of whoever eats does not change with how they take it
- The dock under the map shows a reaction only as one more line of what has been going on
- Nothing tells what a resident's favourite is: only each taste by itself
- The list is not sorted by what it is a taste for, and a long one is cut short with a count
- Tastes in people are in the list with the rest. A taste in doubt again is told as one newly
  suspected: nothing says that it was thought otherwise before
- The game's own icons for these are a heart and a cross: nobody has drawn them
- **For the time being there is a `Debug` switch on `Gustos`**, beside the way back. It shows
  every taste a resident has, found out or not, with the figures behind it: the leaning, what
  was learned, the two together, and how sure the player is (`-`, `?`, `!`). It is for looking
  under the bonnet while the tastes are being tried out, and it is to go or be hidden before
  anyone plays for real: with it on, nothing is left to find out

### P23 — A way of their own (needs P21) — done
Everybody walked, ate and fought through the same clip. Asked for by hand: that the way of doing
each be chosen where a resident is made and where they are changed, three ways of each to begin
with, so that everybody has more of a character.
- **Five kinds of manner, three of each**, as data in `data/manners.json`: walking (firm,
  shuffling, swaggering), eating (calm, wolfing it down, fussy), fighting bare-handed (boxer,
  brawler, kicker), shooting (side on, two-handed, from the hip) and using a knife (lunge,
  slashes, overhand). Twelve new clips in `data/skeleton.json`, from the side and from the front
- **Each resident has one of each.** It is kept with them and saved. Whoever was never given one,
  the people who walk in through the gate and everybody in an older save included, has one that
  is always the same for them, so nobody moves like everybody else
- **Chosen where the first resident is made**: the screen has a second face, `Cómo se mueve`,
  with a row to each kind and the figure of the guide trying out the one last picked
- **Changed under `Maneras`**, in a resident's panel or with `F6`: the same rows, with their own
  doll moving if they have been drawn. What is picked is theirs at once
- **The weapon says which manner a fight is fought in**: something tagged `blade` the knife one,
  something tagged `firearm` the shooting one, anything else the bare-handed one. **It is seen
  in the hand** while the fight lasts
- A manner changes what is seen and nothing of what happens: two settlements that differ only
  in their manners play out the same

Done when: two residents side by side are seen to walk differently; a new game's first resident
walks the way that was picked for them before they were drawn; and a fight with a knife in the
pocket is fought with the knife out.

Still open here:
- **There is no gun in the game yet.** The shooting manners are chosen and seen tried out, empty
  handed, and are used by anything tagged `firearm`; nothing is
- Whoever walks in is not asked: their manners are the ones their ID gives them
- A manner does not follow from what someone is like: a coward may swagger
- What is in the hand does not turn with it, so a knife points the same way all through a slash
- Seen from the front or from behind, on the game's own pixel bodies, the three ways of a kind
  are hard to tell apart: they were made to be read on a doll, from the side
- Carrying, working and arguing are still done one way by everybody
- The opening names `Cómo se mueve` but does not wait for it: it can be passed by without a look

### P24 — Seen to walk at any angle (needs S21) — done
- **A figure follows the line it walks**, between the middles of the tiles and not from one to
  the next, so a walk at a slant is not seen as a staircase
- **The game's own bodies are seen from the nearest of their four sides**: from the side when
  they go more across than up or down, and when they go as much of one as of the other
- **A doll turns to the side it is going towards**, however little that is, and keeps it only
  when it goes straight up or down the map

Done when: a resident sent across open ground at a slant is seen to go straight there.

Still open here:
- There is no drawing of a body seen from a corner: at a slant it is the side or the front
- The stride is as long as the step, so going diagonally the feet cover more than they seem to

## Later
- SQLite persistence
- Semantic/vector memory if the amount of narrative memory justifies it
