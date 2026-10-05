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

### P15 — Houses drawn by hand — planned
Every house and premises is to be drawable in the game as residents are: in parts, each over a
guide, and put together by the game.

- **The walls** of a building, as a part of their own
- **The inside**, empty: the floor and whatever belongs to the room itself, with nothing standing
  in it
- **The roof as seen from outside**, which is what shows until the building is looked into
- Each building its own drawing, kept as a resident's is, and optional in the same way: a
  building nobody has drawn looks as it does now
- An editor for them in the game, after the pattern of the one for residents

Not part of this: furniture and objects. They are to be drawn separately, later, and how is still
to be seen.

To be settled when it is built: the size of each canvas for buildings of different sizes, where
the door and the sign go on a drawing, and how the three parts are told apart on the guide.

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

## Later
- SQLite persistence
- Semantic/vector memory if the amount of narrative memory justifies it
