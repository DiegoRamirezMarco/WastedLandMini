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
- Residents buy but never sell for coin. S23 gave the settlement a fund that what is spent goes
  into, and under barter has them hand a thing over at the counter.

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
- Who is drawn to whom is fixed per pair, with no notion of what kind of person anyone is drawn
  to (S25).
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
- A trip is as dangerous one day as another, short of a storm, and there is nothing for the
  settlement to know or not know about it. S15 left it for when there are places out there.

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
- Nobody ever leaves the settlement for good (S28).

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
- The bar counts what exists. S15 has since given it water, fuel and medicine to count.
- The menu has no construction or research, because there is none (S16, S17), and no radio screen.
- Traits are two. The panel has room for more than the settlement has.
- The speech in the dock is drawn from a handful of lines per kind of exchange. Wanted, by
  hand: lines for sleepwalking, before and after a meal, being hurt, losing a limb, falling in
  love, being sleepy, being sad, somebody new arriving, greeting, getting angry, and so on.

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
- What a doll carries is not shown on it. What it wears is being tried out (P66)
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

Closed since, along with what had been left to settle:
- **The mechanic feeds the generator.** Fuel brought in from outside is left in a crate, and it
  is whoever holds the workshop that carries it on: a load at a time, or at once when the
  generator is running low, and never while someone is at the bench having a thing mended.
  With nobody at the workshop the fuel waits and the lamps go out. Where there is no workbench
  at all there is nobody to wait for, and fuel goes straight in as before
- **Medicine**, an item like any other. The clinic's care uses up a unit for every half day
  someone is under it, out of the cabinet, which is a container now and starts with six. With
  none left the medic can only let them rest, and notice is given once a day. None is spent on
  what comes of thirst or hunger. Trips outside bring a little back, to the cabinet; a caravan
  may leave some at the shop, and the medic fetches it from there
- **A job may keep something supplied**, as data (`supplies`): it is how the mechanic and the
  medic do both of the above, and a pack can give the same errand to any post
- **The bar is left shut, and is meant to be**: there are nine people for eleven places, and
  the bar is the one that matters least. The first to come in at the gate looking for work
  takes it
- **A save from before has the south house put right** when it is loaded: its two beds and its
  crate go where the map has them now, unless they have been moved since
- **Materials** are the scrap there already is. Spending them is building (S16)
- **How many can live here** is the beds there are, and has been since S11: nobody comes to
  the gate without one to spare
- **How dangerous it is outside** stays as it is, the same every trip, until there are places
  out there to be more dangerous or less (S10)
- On screen, medicine is counted in the bar beside water and fuel

Done when: ten weeks pass, with two seeds, in which the lamps never go out with fuel lying in
store, nobody lies in the clinic with no medicine to be had and nobody dies; a patient with
medicine mends faster than one without, who mends as fast as one with no medic; and a save
from before loads with its cabinet stocked, nothing else restocked and nobody walled in.

Still open here:
- A generator wants a workshop with someone in it. A settlement that has a workbench and
  nobody to work it has its fuel in a crate and its lamps out
- As much medicine comes in as is used, or more: in ten quiet weeks, five to eleven doses. It
  runs short only where people are hurt often
- Nobody is sent for medicine or fuel when it runs out: it is whatever a trip happens to bring

### S16 — Building — done
Asked first, and answered: everything put down from Urbanismo takes building, as its data says;
whoever has a spare moment does the work; a thing is proposed to somebody, who answers; and a
new settlement puts down for nothing until its opening is over.

- **What a thing takes is data** (`build`, in `data/interactables.json` and `data/urbanism.json`,
  and in a pack's `data.json`): units of what it is made with, by the tag of the item, minutes
  of work, and the job that has to do it, if any. A thing with no such entry is put down at
  once as before: the wrecks, tyres and junk that are lying about
- **The player proposes it to somebody**, where it is to go. They weigh it and answer on the
  spot, as with a post: their mood and their nerves, how much they already have on their hands,
  how big a job it is and whether there is anything to build it with. Advice counts and does
  not settle it. Whoever says no is not asked again for three hours; whoever says yes can be
  asked again at once, and sooner or later has enough
- **A site is ground marked out**: nothing else goes there, and if what is coming will be in
  the way, nobody walks there meanwhile. It can be given up, and what had been brought to it is
  put away
- **It is built in spare time**: by whoever agreed, first of all, and by anybody else with a
  moment and a mind to help, which is nobody who has it in for them. Never on a shift, in the
  dark, with a need that presses or out in a storm. What it takes is carried from wherever it
  is kept, a load at a time, and then it is worked on, by no more hands than there is room for.
  What asks for a job is carried to by anyone and worked on only by whoever holds it
- **A site that cannot be got on with says so once a day**: there is nothing to build it with,
  or nobody holds the job it asks for
- **The opening puts down for nothing**, and says before it ends that from there on things are
  built
- **Nothing can be put down that cuts ground off from the way in.** Found while this was run: a
  bed across the one-tile strip behind the houses let somebody step off its far side into a
  corner with no way out, where they died of thirst. And what is fetched for a site is not a
  find for whoever goes outside to put away again
- On screen: in Urbanismo a thing that takes building is dropped where it goes and then put to
  one of the residents, who are listed in place of the catalogue. Sites are marked out on both
  maps with how far along they are, and in Urbanismo they can be selected and given up. A
  building that goes up while the map is on show stands there at once

Done when: in the settlement that comes ready made, with three seeds, a shack proposed to
somebody who agrees stands within two days, built out of shift with scrap carried from where it
was kept; somebody in no mood for it refuses and nothing is marked out; a site with nothing to
build it with waits and says so once a day; four weeks of building one thing and another leave
nobody dead; a new settlement puts down for nothing until its opening is over; and a save with
a house half built goes on from where it was.

Still open here:
- Moving and pulling down are still done at once and for nothing, and what is pulled down
  gives nothing back
- Nobody builds anything unasked: every site is the player's proposal
- Nobody is sent for scrap when a site waits for it: it is whatever a trip happens to bring
  (S36 has whoever sees to it go)
- A site has no picture of its own, only its outline, and whoever works on it does as at a post
- What each thing takes is a first guess, and tools do not come into it
- Everybody knows of every site there is, without having seen it or been told

### S17 — Research — done
Asked first, and answered: what is worked out opens up things to build and makes other things
go better; the player says what is studied, with nobody asked; it is done at a post of its
own; and a subject takes time, other subjects before it, and now and then a thing to study.

- **Subjects are data** (`data/research.json`): the minutes each takes, the subjects that have
  to be known first, the item it studies and uses up, the kinds of object and the blueprints
  that nobody can put up until it is known, and what goes better for knowing it
- **Twelve to begin with.** Six open up what a new settlement cannot make: the workshop, the
  generator and its lamps, the radio, the clinic, the shop and the cantina. Six make things go
  better: the garden, the water, building, and trips outside, which come back safer and with
  more, and medicine, which lasts longer
- **What is studied is the player's to say**, and theirs alone: it is the one thing in the
  settlement nobody is asked about. What was done on a subject left for another is kept
- **A post of its own**: a study desk and the job that goes with it, with a shift like any
  other. Time at the desk goes towards whatever is in hand. It matters as much as the shop or
  the workshop, so whoever holds it is called away to the water or the watch before they are
- **A thing to study is fetched** by whoever holds the post, from wherever one lies that is
  nobody's, the shop included, and is used up. Until it is at the desk nothing is done, and
  notice is given once a day; so it is when somebody is at the desk and nothing has been chosen
- **A settlement that is already running knows how to make what it has standing**, and so does
  a save from before. A new one knows nothing, and can put up only what takes no knowing,
  during its opening as after it
- **The opening says so** before it ends, in a step of its own, and leaves an old radio in
  the crate: asked for by hand, since the radio matters and one turns up seldom outside
- On screen: `Estudio` in the menu, or `E`, lists what is in hand, what can be chosen and what
  waits for something else, each with what it is for, and names what is known. Urbanismo lists
  what nobody knows how to make yet, marked as such, and says what it waits for

Done when: in the settlement that comes ready made, with somebody at a desk, a subject chosen
is known within three days and what it makes go better goes better; one that studies a thing
has it fetched and used up, and without it waits and says so; a new settlement cannot put up a
generator until electricity is known; three weeks of study, with three seeds, work three
things out and leave nobody dead; and a save keeps what is known and what is half worked out.

Still open here:
- Nobody is sent for the thing a subject studies: it is whatever a trip happens to bring. A
  settlement that has lost the old radio it began with may wait long for another
- Whoever studies is no better or worse at it than anybody else, and nothing of what they are
  like comes into it
- Subjects are the game's alone: a content pack cannot add one yet
- No building waits to be worked out, only furniture
- What each subject takes and gives is a first guess

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
  anything else. Urbanismo no longer lets it happen, but an old save may have it (S25)
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
- Whoever is in charge is whoever keeps the watch. There is nobody else to distrust (S26)
- A taste in people moves what is felt for someone and nothing else: not who is sought out to
  talk to, nor who is believed
- Tastes in people are not learned: nothing lived through moves them yet
- Nobody tires of what they have every day: having a thing again only ever takes a taste the
  way it was already going
- Coming to depend on something is having a taste for it grow faster and farther. Nobody goes
  looking for it, and nobody misses it (S24)
- A grief, a fight or a death moves no taste: only a meal that turns on someone does
- Being told what to do is being given advice by the player. No resident orders another
  about (S26)
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
  them and it is not saved. Stopped short part-way along a line, they take the next minute to
  step onto the middle of their tile
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

### S22 — In each other's way (needs S21) — done
People walked through one another, and stood two to a tile. Asked for by hand: that they must
not.
- **Nobody steps onto a tile somebody else is on**, nor one that somebody has walked over
  this same minute, nor diagonally between two people. So no two are ever on one tile, and no
  two cross through each other, on the map or in what is drawn of the minute
- **Nobody plans to end up where somebody stands or is heading.** Beside a thing or a person,
  out for a stroll or in out of the rain, a place that is taken is no place: with every side
  of somebody taken, there is no going over to talk to them
- **Met on the way, they sort it out**: they wait a minute for whoever is passing in front,
  and walk round whoever is standing or coming straight at them. If somebody has stopped
  where they were going, they go to another place beside the same thing or person
- **Whoever has nothing to keep them where they stand steps aside** when there is no way round
  them: somebody strolling or waiting out the weather moves to the nearest place out of the
  way, and goes on as they were. Somebody at work, at table, in bed or in talk does not move
- **With no way through at all they give it up** after two minutes, walk a little way off, and
  think again in a while. That is what gets two people past each other in a doorway
- Whoever comes onto the map, through the gate or back from beyond the fence, is put where
  nobody stands
- How long somebody has been held up is on their activity and in the save (version 22). Their
  panel says `espera a que le dejen pasar` while they are

Done when: days of the settlement pass with no two residents on one tile and no two crossing
in a minute; two who meet in a doorway both get where they were going; and the first one in
out of a storm does not keep everybody else out in it.

Still open here:
- Two lines that cross between tiles can still bring two walking figures very close for a
  moment: it is tiles that are kept apart, and a figure may be half a tile off the middle of its own
- Somebody at work or at table in a narrow place keeps everybody else out for as long as they
  are at it. Nobody asks them to move, and nobody thinks of another way in beforehand: they
  walk up, wait, and give up
- Giving way is not a matter of who anybody is: a brute and a coward stand aside alike, and
  nobody takes it badly
- In an older save two people may be on one tile. Nothing moves them: they walk apart

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
- **A drawn resident carries their load in their hands** the same way (until P48: it is in
  their pockets now)
- **A meal is seen going**: a bite out of its outline, on the side of the mouth, at each fifth of
  the way through
- **Crumbs of the food's own colours**: chips of several shapes and sizes that are tossed up,
  turn, fall to the feet, hop and fade, the same way at the same moment every time
- **An item opened again in its editor is as finely drawn as it was saved**: it was being opened
  from its 16×16 icon, and saving it again lost what had been drawn

Still open here:
- Everything eaten is bitten and sheds crumbs alike: a tin loses pieces as a slice does
- What is held does not turn with the hand, and the hand is behind it, not round it (a tool
  at work does since P47; a meal and a weapon still do not)
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

### S23 — A common fund, and what things are paid with (needs S8) — done
Asked for by hand, to come before politics along with S24 and S25: a fine has to go somewhere,
a law on drink needs drink, and "my brother" needs brothers.

Asked first, and answered: a caravan stops for some hours and gives nothing away; what is a
resident's own can be sold to it if they agree, and what it fetches is theirs; under barter the
fund is the things that are nobody's, in the shop and the stores, and what a trip brings back
goes into it as things; and under barter whoever works is kept, and takes nothing home.

- **A common fund**: what the settlement holds as a whole, apart from what anybody owns. In coin
  it is a figure, and it never goes below nothing. In things it is whatever lies in a container
  and is nobody's
- **The settlement settles how it trades**: by barter, a thing for a thing, or with a currency.
  It is the residents who settle it. The player puts it to them with advice, everyone who is in
  answers for themselves, and more for it than against carries it: greed and savings lean
  towards coin, things of their own and empathy towards barter. They cannot be asked again for
  three days. Once there is a government it is decided as any proposal is (S27)
- **A new settlement starts on barter.** The one that comes ready made trades with its credits
- **A currency is made by the player**: it is given a name, and what one of it is called. The
  first one a settlement takes up puts six in every pocket and thirty in the fund for each
  resident. Going back to barter leaves what is held as it is, counting for nothing, and there
  if a currency is taken up again. Drawing it is P25
- **With a currency, wages come out of the fund and what is paid at a counter goes back into
  it**: a purchase, a drink, a repair. No coin is made or lost. With the fund empty wages go
  unpaid, and it is said once a day
- **Under barter nothing is priced in coin, and whoever holds a job is kept**: they eat, drink
  at the bar and have things mended for nothing. Whoever holds none hands over the thing of
  theirs worth least to them for a meal, a drink or a repair. With nothing to give they are fed
  all the same, which is said once a day, and go without the rest. A settlement still in its
  opening asks nothing of anybody
- **A swap at the counter**: a resident offers a thing of theirs for one on the shelf that is
  worth more to them, not knowing what they will be told. Whoever keeps the counter takes it
  only if they do not lose by it as they see it (S19). What was given goes on the shelf as the
  settlement's. Turned down, they do not ask again that day
- **A caravan is a merchant** (`merchant`, a kind of world event): it stops for four to six
  hours (the whole day, since S39) with eight to fourteen things and some coin, asks half as much again as a thing is
  worth and gives six tenths for one. A pack can still have things left for nothing (`stock`)
- **Buying from merchants and selling to them is the player's to do**, out of the fund and
  into it, in one deal: only what is nobody's is sold this way. Under barter what is handed
  over has to be worth what is taken. What is bought is left at the shop
- **What is a resident's own is put to them**, and they answer by what it is worth to them
  against what it fetches. Advice counts for little. What it fetches is theirs: coin, or under
  barter a thing of the merchant's
- **Nobody else spends from the fund while there is no government**, but for wages
- **A currency is credit, and credit can be stolen.** It is taken from someone asleep, with
  nobody looking on, by whoever the same leaning would have steal a thing (S5), and only by
  someone short of coin themselves. Whoever sees it knows and holds it against the thief; the
  victim misses it on waking; making peace brings back what is left of it
- **The fund can be stolen from as well**, at the counter: coin, or under barter a thing off
  the shelf. Whoever keeps the counter sees that it is short
- A save from before loads as a settlement whose currency is the credits it had (save version 26)
- Each of these is a domain event, and each thing the player does is a command:
  `ProposeCurrencyCommand`, `ProposeBarterCommand`, `DealWithMerchantCommand` and
  `ProposeSaleCommand`. None has a screen until P25

Done when: a week passes under barter in which everyone is fed and the shop changes hands with
no coin anywhere; a settlement that takes up a currency pays its wages from the fund and takes
back at the counter what it paid; the fund never goes below nothing; and a save from before
loads with its credits.

Found by running ten weeks with a fund that can run dry, and put right:
- **Nobody gives away what they work with.** Farmers made presents of their hoes and bought
  others with wages that never ran out. With a fund that does, they were left without, the
  garden gave a third less and in some settlements everybody starved. The tool of a
  resident's job is no longer given, swapped or handed over; one they have besides it is
- **The tool somebody works with is mended even when they cannot pay for it**: whoever can
  pay does
- **Coin tempts whoever is short of it.** Taken by anyone given to it, credit went missing as
  often as every other day, and whoever had most took as readily as anyone
- With these, sixteen seeds run for ten weeks keep as much food by them as before the fund, but
  for one, where raiders got in three times and it was down to its last few meals at the end.
  The rest never had fewer than twenty-seven by them, against seventeen before

Closed since, with what the player said of it and what was asked:
the settlement keeps whoever works and nobody else; credit is stolen by whoever is short of it
or is that way inclined; only a fool parts with what they work with; food is paid for; whoever
has coin put by spends it at their own counter, on presents, on a friend's drink and on loans;
whoever goes outside under barter keeps a thing of each trip; going unpaid tells on mood and
on work; residents deal with a caravan over what is theirs; a worn thing is worth less;
residents raise a currency themselves; what becomes the settlement's is carried by hand; and a
settlement with no shop keeps its fund in a box.

- **The settlement keeps whoever works for it.** Three days without working, post or no post,
  and it stops: it is said, and said again when they go back to work. Whoever is in no state to
  work is not held to have stopped, someone new has those three days, and a settlement in its
  opening keeps everybody. Putting something up counts as work
- **Whoever is not kept pays for what comes out of the commons**, water included: coin, or
  under barter the thing of theirs worth least to them. With nothing to pay with they go
  without. Nobody is fed for nothing any longer
- **Hungry or thirsty enough, they take it without leave.** They wait for nobody to be looking
  unless they are past caring. Whoever sees it knows and holds it against them
- **With a currency a meal out of the commons costs one**, and it goes into the fund. Whoever
  the settlement keeps is fed even with an empty pocket; a drink at the bar is another matter
- **Traits that say who steals and who is a fool**, as data (`thieving`, `careless`): `Mano
  larga`, `Mala entraña` and `Picardía` make somebody more given to taking what is not theirs,
  things and coin alike, whatever they have put by. `Pocas luces` is who parts with the tool
  they work with. All four can be chosen for a first resident. Sergio has `Picardía`, Paco
  `Pocas luces`, and of those who may come to the gate Hugo has `Mano larga` and Carmen `Mala
  entraña`
- **Whoever keeps a counter can serve themselves at it out of hours**, paying like anybody
- **A present is bought**: someone with more than fifteen to spare, and nothing they want for
  themselves, buys what they believe whoever they are fondest of would like, keeps it apart,
  and hands it over the first time the two of them talk
- **A friend at the bar stands a drink** to whoever cannot pay for it, if they are fond enough
  of them and have coin to spare. It is not forgotten
- **A friend lends**: whoever is down to less than three is lent ten by someone fond of them
  who trusts them and has it to spare, at the end of a chat. It is a fact between the two. It
  is paid back the next time they talk with it in hand, and after a week unpaid it tells on
  what the lender thinks of them
- **Under barter whoever goes outside keeps one thing of each trip**: the one worth most to
  them, and never water, fuel, medicine or scrap
- **A day without their wage tells on a worker**: mood, nerves, and a twentieth slower at
  their work for each day running, down to four fifths
- **Residents go to a caravan of their own accord** over what is theirs, if they know it is
  there: they saw it come, heard it forecast or were told. With a currency they buy what they
  want at what is asked, or sell what fetches more than it is worth to them; under barter they
  swap. Once for each caravan
- **A worn thing is worth less**: to a caravan, on the counter and in a swap, down to a quarter
- **A resident raises it themselves**: three swaps turned down and they think of proposing a
  currency; three days without a wage, of going back to barter. Whether they do is theirs to
  decide and the player's to advise on. If they do, everybody answers with no advice. A
  currency taken up this way goes by `vales` until the player names it (`RenameCurrencyCommand`)
- **What becomes the settlement's is carried to where it is kept.** What is handed over at the
  bar or the workbench is taken by whoever serves and carried to the till after. What is
  bought from a caravan waits at the gate for whoever keeps the shop to bring in, six at a
  time. Handed over at a pantry or a pot, it stays there
- **A settlement with no counter keeps its fund in a crate**, which is where it is stolen
  from, and everybody's to look into
- Save version 27

Done when: sixteen seeds run for ten weeks end with a fund of 229 to 297, from 270, with every
wage paid, nobody holding more than twenty-six, nobody dead and never fewer than eleven meals
by them; whoever stops working is cut off after three days and helps themselves when hungry
enough; and a save from before loads with everybody having just worked.

Still open here:
- Everybody lives hand to mouth: a day's wage is seven and three meals take three of it, so few
  ever have the fifteen to spare that a present, a drink for a friend or a loan asks for. In
  ten weeks there is a loan or two and no present. What a wage and a meal ought to be is a guess
- The fund sits where it started: nothing the settlement does of its own accord spends it but
  wages. It is the player's to spend at a caravan, and that has no screen until P25
- Nobody minds someone who is not kept beyond what they see them take
- What waits at the gate is neither seen nor stolen. The caravan is seen since P37
- With nobody whose job it is to keep the till, what is bought from a caravan is at the shop at
  once
- Residents do not sell at the counter for coin: only to a caravan
- A thing sold to a caravan as nobody's by its kind is taken from wherever it lies, with nobody
  carrying it out
- A resident who takes up a currency unasked cannot name it: it is `vales` until the player does

### S24 — Substances (needs S20) — done
Asked first, and answered: the game comes with one for each way of taking them besides drink;
all of them can be made in the settlement, the drink at the bar and the rest at a post of its
own that has to be worked out and built; too much harms and can kill, and the clinic sees
somebody through dependence; and the player has a say when someone starts, when they go back
to it, and now and then in between.

- **A substance is a consumable like any other, as data**: an item with a `substance` entry
  that says how it is taken, how long it lasts, what it does meanwhile and afterwards, what it
  harms, how likely it is to bring dependence and what it looks like on whoever took it. A pack
  brings one with no code of its own
- **Four ways of taking one**: swallowed, sniffed, injected or smoked
- **Five to begin with**: `aguardiente` and `calmantes`, swallowed; `cigarro liado`, smoked;
  `polvo blanco`, sniffed; and `jeringa`, injected
- **Three kinds of effect, each as data**: the good it does on the spot and minute by minute
  while it lasts, with how fast it has them work; the harm of its own, which is what comes
  after it wears off, what it takes out of them each time and what too much does; and what
  others make of it
- **Being seen is part of it.** Whoever sees it taken knows it of them, as a fact to pass on,
  and takes it their own way by a taste in people (S20) for whoever drinks, smokes or gets
  high. Smoke reaches everyone under the same roof and nobody outside it, and bothers nobody
  in the open
- **Dependence comes by chance**, each time one is taken, from the settlement's own
  randomness, and the likelier the more of a habit it is. Whoever depends on something wants
  it once it is long enough since the last, takes it if they have it, buys it above anything,
  and is the worse for going without: nerves, and a fifth slower at work. Five days' worth of
  going without and it passes
- **The clinic sees somebody through it**: with nothing to take, whoever is going without
  lies down there while a medic is at it, and it passes three times as fast. Whoever lies in
  care is not held to have stopped working (S23): found when a medic who had come to depend on
  drink lay in her own clinic for three days, was no longer kept, and went hungry there
- **Too much harms, and can kill**: taking something on top of itself is an intoxication, an
  injury like any other, and a needle costs something every time. Nobody but the rash takes
  more of what they are already under
- **Someone under a needle notices nothing** while it lasts
- **The player's say**: the first time with something that hooks easily, going back to it
  after two days without, and at most every three days when it is a habit, they stop to think
  and the player may talk them out of it. Talked out of it, they leave it for six hours. A
  drink like any other asks nobody
- **What the bar serves is the first of them**: it holds what it serves, a drink is one unit
  of it, and whoever keeps the bar makes it, out of water
- **The rest are made at a laboratory**, a post of its own that has to be worked out first
  (`Química`, after the bar and the clinic) and built. Whoever holds it makes the four in turn,
  whichever there is least of, and sells them over its own counter
- **A job may make several things at its post** (`also`), as data
- Being under something, and depending on it, are states of a resident's own, and are saved
  (save version 28). In a save from before nobody is under anything
- Taking one, being seen at it, coming to depend on it and getting over it are each a domain
  event

Done when: the same drink leaves one resident dependent and another not, and the same way when
the same seed is run again; someone dependent is seen to go after it and to work worse without
it; two residents who watch the same drunk feel differently about them afterwards; smoke
indoors is minded by those in the room and by nobody outside it; and ten weeks pass with three
seeds without the whole settlement ending up dependent.

Still open here:
- The settlement that comes ready made has no laboratory and has not worked one out, so only
  drink is ever seen there unless the player has one studied and built
- The laboratory makes its four out of nothing, and the bar its drink out of water alone
- Whoever is under something is seen when they take it, and not for as long as it is on them
- Nobody is refused a drink for having had enough, and whoever keeps the bar thinks nothing
  of serving someone who depends on it
- Nobody tires of somebody's habit, hides their own or tries to talk a friend out of one: it
  is only the player who does
- Getting over it leaves nothing behind but that it is asked about if they go back
- Somebody about to take too much is not stopped for the player to have a say: only the
  starting, the going back and the habit are
- What each substance does is a first guess
- Seen while this was run: a guard who stays up for raiders can be drawn off the watch by their
  partner, and the raiders walk in (S13)

### S25 — Families (needs S9) — done
Asked first, and answered: a settlement begins on the first of January of 2226; the chance of
dying of old age is five in a hundred a year at eighty and doubles every five years; in a save
from before, those the game has by name are who its data says and anybody else is who their ID
makes them, to be changed later; libido is fixed and the moment counts; a child takes its way
of being, mixed, and its traits from its parents, and not their tastes; and there are kin from
the start, families come to the gate together, and one of them may be let in without the other,
which is not forgotten.

- **A couple may marry.** Like a confession and a breakup, it is something the player is given a
  say in beforehand
- **Libido, one more side to a way of being**, from 0 to 100 like the others, with a slider
  where the first resident is made (P16) and in the middle for everyone in a save from before.
  It counts for nothing in anyone who is not an adult
- **Two adults need not be a couple to go off alone together**: two who get on very well and
  both have a high libido may. It is the same narrative event it is for a couple (S9), known to
  nobody who does not come across them, and whoever has a partner and is found out is turned on
  as before
- **Residents have a sex and a gender, and the two are kept apart**: the sex of their body, `m`
  or `f`, and what they take themselves to be, `m`, `f`, `nb` or `bi`. Both are IDs, given
  where a resident is made and in the data of whoever comes to the gate. Gender says how they
  are spoken of, and nothing of what their body can do
- **Everyone is drawn to `m`, to `f` or to both**, and that too is theirs and is saved. It goes
  by the other's sex, not by their gender. Nobody courts, becomes a couple with or goes off
  alone with someone they are not drawn to, however well the two get on. It is what S9 lacked: who is drawn to whom was fixed for each pair, with
  no notion of what kind of person anyone is drawn to. In a save from before everyone is drawn
  to both, so that nothing that was going on stops
- **A child may come of it.** When two adults marry or go off alone together, couple or not,
  and one is `m` by sex and the other `f`, there is a chance of a child, drawn from the project
  RNG. It is whoever is `f` that carries it
- **A child is carried for nine weeks.** Whether whoever carries one goes on working is for the
  law to say (S28). Where there is no law on it, they work as before
- **A child is a resident**, born in the settlement, with parents and a date of birth
- **A calendar: days, weeks, months and years**, counted by the simulation's clock from the day
  a settlement begins. It is the ordinary one: twelve months, each with the days it has always
  had, 365 to the year and no leap years. Nothing new is saved for it: the date follows from
  the day
- **Everyone has a date of birth, and their age is worked out from it.** A birthday comes round
  by itself, and is a domain event. A save from before gives each resident the date that makes
  them the age they were
- **People grow old and die of it**, and go to a grave as any of the dead do (S7), with all
  that a death sets going. Nobody dies of it before eighty. From eighty on it is a matter of
  chance, drawn from the project RNG, and the likelier the older they are
- **Whoever has no bed curls up on the ground.** A child of ten is like anybody: they sleep in
  a bed if there is one for them and on the ground if there is not, and rest the worse for it.
  The same goes for a grown resident left without one
- **A child's time is counted in weeks, and runs fast**: twelve weeks after being born they are
  ten years old. How fast is data. From ten on they grow older as everybody does
- **Until they are ten a child is a bundle**: a head and a blanket, carried on someone's back.
  They go nowhere by themselves and do nothing
- **A bundle has needs of its own, and someone has to see to them.** Whoever looks after it
  carries it, feeds it and puts it down when they must: in a bed, or on a table, some other
  surface or the ground. Anywhere but a bed it is the worse for it, the more so the longer it
  is left
- **A bundle nobody looks after dies.** Its parents look after it first. With them dead, gone
  or not seeing to it, someone else may take it in, by who they are and what they felt for the
  parents, and the player is given a say before it is too late
- **Whoever takes a child in is its parent from then on**: adoption is kin like any other, kept
  beside the parents it was born to, and both are in the tree
- **From ten, a child is kept out of nothing but romance and sex.** They can be given a post,
  get into a fight, take a substance (S24), be tried and be punished (S28). None of it is taken
  as it would be with a grown man or woman: whoever sees a child at work, hurt, drunk or
  punished is the worse for it in mood, far more than for the same thing done by or to an
  adult, and with mood low a settlement argues and comes to blows that much sooner (S15). Once
  there is a government it is held against it as well (S28, S29)
- **Kin are kept by stable IDs**: who someone's parents, children, brothers and sisters and
  spouse are. The rest of a family is worked out from those, and so is the family tree, the
  dead included (S7)
- **Kin matter.** What is felt for a child, a parent, a brother or a sister starts from being
  kin, in each direction by itself as always, and what is done to one of them is taken as done
  to one's own
- Romance and sex stay between adults, as they are (S9)
- **Being kin keeps nobody apart** (said once it was built, in place of "never between close
  kin"): whoever comes to know of two close kin being together thinks the worse of both, and a
  child of two who are kin by blood takes the worse of its parents in every side of its way of
  being, and the flaws of both
- A save from before loads with nobody kin to anybody

Done when: over a long headless run a couple marries and has a child; two who are no couple,
get on very well and both have a high libido go off alone together, and two with a low one do
not, nor two of whom one is not drawn to the other; a child is born nine weeks after it was
conceived, to the two whose child it is; a second child is brother or sister to the first; for
twelve weeks a child is carried about, put down and seen to, and does nothing else, and at the
end of them is ten years old, walks, and can be given a post; a year after that they are
eleven, on their birthday; a bundle left on the ground is worse off than one in a bed; a bundle
whose parents die is taken in by someone and lives, or by nobody and dies, and never without
the player having had a say; nobody under eighty dies of old age, and someone old enough does
and is buried; someone with no bed sleeps on the ground and wakes less rested; a settlement that
puts a child to work is lower in mood and quicker to quarrel than the same settlement, with the
same seed, that does not; the tree of a family is the same after saving and loading, with a
dead grandparent still in it; and someone whose brother is hurt takes it worse than someone to
whom he is nobody.

Tests it is not done without: a child's parents, and brothers and sisters worked out from them;
no romance or sex with anyone under age, whatever their libido; close kin not kept apart,
ill seen by whoever knows of it, and their child the worse for it; libido
deciding who goes off with whom; being drawn to someone, or not, deciding it first; sex
deciding who can have a child, and gender deciding nothing of it; nine weeks from conception to
birth; the date worked out from the day, through months and years; a child's age week by week
up to ten, and year by year after; a bundle that is carried and never walks; a bundle faring
worse out of a bed; a bundle with nobody dying, and one taken in living; adoption in the tree
beside birth; a birthday as an event; no death of old age before eighty, and one after;
sleeping on the ground for want of a bed; a child at work seen and taken worse
than an adult at the same post; the same seed giving the same births; kin, sex, gender, who
they are drawn to and dates of birth kept by saving and loading; and a save from before, with
everyone the age they were and drawn to both.

As it was built, where the lines above leave it open:
- **Libido is theirs and the moment counts**: what it weighs at any time falls with nerves, low
  spirits, tiredness and a hurt body. Two who are no couple go off alone together when each gets
  on very well with the other and wants it enough there and then
- **A couple that is doing well thinks of marrying**, one of them asks, and the other answers
  by what they feel. Marrying is kin, and ends if the couple does
- **A child comes of it six times in a hundred**, to nobody of fifty or more, and one at a time
- **A child is named from a list**, is `m` or `f` by chance and takes itself for the same, and
  who it is drawn to is by chance too. Each side of its way of being falls within fifteen of the
  middle of its parents', and each trait of theirs is taken half the time, two at most
- **A bundle is on the back of whoever sees to it while they are awake, and beside them when
  they sleep**: the first of its parents who is here and in a state to. Feeding it costs them
  rest and nerves, and nothing else. With neither parent there it is put down: in a bed that is
  free, on something under a roof, or on the ground. Left twelve hours, or with no parent
  living, someone is asked to take it in, the likeliest first, one at a time. It does not die
  while somebody is making up their mind
- **Nobody under age has to earn their keep** (S23), whether they are given a post or not
- **Being kin** is forty of affection and thirty of trust to begin with, each way. Whoever sees
  one of their own hurt, in a fight or robbing is the worse for it in nerves. Whoever sees a
  child at work, hurt, in a fight or taking something is the worse for it in mood and nerves
- **Those the game has by name have a sex and who they are drawn to as data**
  (`data/family.json`), and so do their kin: Marta and Vera are sisters, Paco and Bruno
  brothers, and Hugo and Carmen brother and sister, who come to the gate together
- **Two at the gate are put to whoever answers it together**: both, either of them, or neither,
  and a bed for each one let in. Having kin inside weighs on the answer. Whoever is let in
  while the other is not remembers it, and holds it against whoever decided
- **Whoever sleeps on the ground** rests a little over half as fast as in a bed, and wakes on edge
- Who somebody is can be said where a first resident is made and with `SetIdentityCommand`.
  Save version 29

Changed once it was built, as the rule above says:
- **Two close kin** court, become a couple, marry and go off alone together like any two. It
  is one fact about the two of them (`kin_together`), which they keep to themselves, which
  whoever sees them become a couple, marry or be alone together learns, and which is passed on
  like any other. Whoever learns it thinks the worse of both alike, without taking a side:
  less affection and trust, more resentment, and nerves. Having been taken in by the same
  people counts as being kin for this
- **A child of two who are kin by blood** takes the higher of its parents' aggression,
  impulsiveness and greed and the lower of their empathy, sociability and courage, outright,
  and every trait of theirs that is marked a flaw, before any other and as far as there is
  room. Libido has no worse end and is mixed as in anyone. Having been taken in does not
  count for this
- Still open: nobody knows whose a child is, so nobody thinks the worse of a child for it,
  nor of its parents for having it; the two feel nothing about it themselves; and there is
  nothing to stop it, by law or otherwise (S28)

Found by running half a year, and put right:
- **The garden takes more hands as more people live here** (`per_residents`, on a job): with
  two in it whatever came, a tenth mouth emptied the pantries in forty days and everybody
  starved. Now a third is wanted from ten, and somebody is asked as for any post left empty.
  With it, three seeds run for half a year lose nobody, and in each a couple marries, has two
  children, and the first of them is ten and walking by the end

Still open here:
- A couple with a child on the way or on their back lives as before: nothing changes in where
  they sleep or how they spend the day, and whoever carries one works as before (S28)
- Whoever sees to a bundle picks it up wherever it is, without walking to it, and is the same
  parent as long as they are fit: the other only steps in when they cannot
- A bundle eats nothing out of the pantry. From ten a child eats like anybody
- A child of ten is a small adult in all but romance: nothing teaches them, and no post is
  kept from them
- What is done to one of their own tells on whoever sees it, and that is all: they do not
  turn on whoever did it more than anybody would
- A couple, once it starts, has a child every ten weeks or so, and nothing but age stops it
- Nobody knows somebody is expecting, the two of them included: it is not a fact anyone holds
- Whoever is turned away at the gate while their brother or sister is let in is gone for good
- The water does not take more hands as the garden does: with one tank there is one post
- All of it was put on screen in P25: who somebody is, the date, the tree and a bundle on a back

### P25 — Coin, smoke and kin on screen (needs S23 to S25) — done
Asked first, and answered:

- **From ten to eighteen the body grows a little at each birthday**: six tenths of what was
  drawn at ten, and a twentieth more every year, to all of it at eighteen. The head is as drawn
- **The fund has an entry of its own in the menu**, `Fondo`, with its board, and what it holds
  in coin is in the bar on top beside the food and the scrap
- **The family tree is of the whole settlement together**, on one screen. Not the
  recommendation, which was the tree of whoever is selected, opened from their panel
- **When a child is born the screen for drawing them opens**, with time stopped. `Esc` leaves
  it for later, and meanwhile they have the look the game comes with for children

Coin and fund:
- **`Fondo` in the menu, or `F`**: how the settlement trades, what the fund holds, what there is
  in things that is nobody's, and what each resident said the last time they were all asked,
  face by face. The settlement keeps what each said (`asked_about` and `answers`, saved)
- **A currency is named there**: its two names are written on the board, `TAB` changes field,
  and it is put to the residents with one of the advices the decision has in its data.
  `Volver al trueque` is put to them the same way. With a government either is a proposal
- **`Cambiar nombre`** gives the currency there is another name
- **The coin is drawn by the player**, in a screen of its own (`Dibujar moneda`), on a paper of
  96 by 96 over the game's coin. It is kept by the ID of its currency, as a save is
  (`illustrations/coins/`), so that a currency made after another is drawn anew
- **The coin is seen wherever something is counted in it**: in the bar on top beside what the
  fund holds, in the board, and in a resident's panel before what they have
- **A thing of a resident's own is put to them from the deal with whoever is at the gate**:
  what they own that would fetch something is listed under the deal, what fetches most first,
  with `Proponérselo`. Under barter what they get is the first thing of the merchant's that
  has been put in the deal
- **What was bought waits by the gate where it can be seen**, a thing of each kind and how many
  in all, until somebody carries it in. Whoever has come to trade is on the minimap

Substances:
- **How something is taken is seen as it is taken**: a mark over their head for each of the four
  ways, a bottle, a line, a syringe or a cigarette. A way a pack brings has the first of them
- **Whoever is under something reels**: they sway from side to side of where they stand, wide
  and slow with drink and short and quick with the rest, on the map and inside a building, with
  a spiral over their head while there is nothing more pressing to show
- **Smoke hangs round whoever smokes**, puffs that rise from their head, and they walk straight
- **`Quién es` in a resident's panel says what they take**: what they are under, what comes
  after it, what they cannot do without and whether they are going without it, and what they
  left behind. Never how much, or how often

Kin:
- **`Quién es`, a third face of a resident's panel**: their age and when their birthday falls,
  what they are and who they are drawn to, a child on the way or on their back, and their kin
  by what each is to them, the dead and the absent included. A click on one who lives here
  selects them
- **`Familias`, at the head of the list of residents or with `F7`**: the families of the whole
  settlement on a screen of their own, time stopped. Each family is a block, a generation to a
  row, parents over their children and partners side by side, with a line of its own colour for
  the married, a couple, children, those taken in, and brothers and sisters. Whoever is kin to
  nobody here comes after them. The dead and whoever never came are there, darkened. It opens
  about whoever is selected, is dragged or moved with the arrows, and a click on somebody who
  lives here goes back to the map with them selected
- **A child under ten is a head and a blanket**: just behind whoever carries them and well up
  their back, and where they were put down with their name over them, off the ground on a bed
  or a table. The head is their own once they are drawn, and until then the face the game has
  for them. The same inside a building
- **From ten to eighteen the body is smaller and the head is not**: brought down about the
  ground they stand on, with what they hold where their smaller arm has it
- **A child nobody has drawn has one look**, the same figure for all of them in one colour
- **When a child is born the doll editor opens on them**, titled as the adult they will be,
  where there is somewhere to keep drawings. `Esc` leaves it for later
- **Who the first resident is is said where they are made**: the sex of their body, what they
  take themselves to be, who they are drawn to, and a slider for their libido. What they take
  themselves to be follows their body until it is said otherwise
- **The date is in the plaque at the head of the bar**, under the day, and the plaque is as wide
  as the longest date. **A birthday is worn all day**, a cake over their head
- **Whoever knocks at the gate stands there**, two side by side if they came together, and is
  on the minimap. A click on them opens the answer of whoever is at the gate. In it both are
  seen, the second in a corner of the first, and it is said that they came together
- **Whoever sleeps on the ground is seen lying under a blanket**, their head out at one end
- **Two who marry wear two rings over their heads** for a while

Decided without asking:
- The family tree is asked for from the head of the list of residents and with `F7`, and has
  no entry of its own in the menu: with `Fondo` there is room for one more entry of the
  settlement clear of the dock and no more, and the rows are already two pixels shorter for it
- Who somebody is drawn to is said outright in their panel. It is not found out, as tastes are
- A child on the way is said in the panel of whoever carries it, as the log says it. Nothing
  of it is seen on their body
- A sale is put to its owner with the advice that encourages it. Three things of the
  residents' own are listed at once, and the rest are counted
- The one look of children is a yellow figure. With no window under the canvas, the game's own
  small body is brought down whole, head and all
- Whoever is under something that has them notice nothing reels like anybody: they are not
  seen sitting or lying

Still open here:
- A child still carried cannot be selected: what is known of them is in the panel of whoever
  is kin to them, and on the tree
- The tree lays each family out by itself. Two families joined by a marriage are one block,
  and with many of them the lines cross
- Nothing is seen of a habit beyond the moment: whoever is going without looks like anybody
- A wedding is two rings over two heads. Nobody gathers for it
- The coin is not shown beside each price at a counter, nor in the deal with a caravan: there
  the sums are in words

### S26 — Who is in charge (needs S20) — done
Asked first, and answered: the ready-made settlement has no government and chooses one on its
first day; loyalty is to the person, and what passes from one leader to the next is trust in
the government; a resident's politics come of their way of being, their traits and a leaning of
their own made from the seed; and the player puts one kind of government to everyone, once,
which weighs with each as advice does.

Politics comes in four milestones, S26 to S29, and a screen, P26. It has a module of its own,
`simulation/politics/`: `government.py`, `leadership.py`, `voting.py`, `law.py`, `punishment.py`,
`legitimacy.py`, `unrest.py`, `faction.py` and `political_event.py`.

What holds for all four:
- The player is not the mayor and is nobody in the settlement. They propose, advise and
  influence, and never govern. Set aside in one thing since (S38): the kind of government
  is the player's to say
- Whoever leads is a resident like any other, with a role. There is never a mayor apart from
  `Resident`
- Fear, support, legitimacy and loyalty are four things, and none stands in for another
- Nobody knows a thing because the world does: residents vote and react on what they saw, were
  told or believe
- What politics does to people it does to each of them in their own way, by who they are, what
  they remember, who was involved and how things stand
- A government can fall, change or split the settlement, and the game goes on
- A harsh punishment always leaves memories, reactions and political risk behind it
- No vote and no outcome is a roll alone, and nothing political is decided in a scene or the UI
- Politics is built on relationships, rumours, memory and events, and replaces none of them
- All of it runs headless, without pygame

This one:
- **Governments as data** (`data/governments.json`), one definition for all of them and no class
  for each: `strong_mayor`, `council`, `direct_democracy`, `military_leadership`, `commune` and
  `personalist_rule` to begin with. Each says who may propose, who approves, who votes, how much
  the leader's word weighs, whether there is a veto, how long a term lasts where there are
  terms, how the next leader comes to be, and how much abuse of power is put up with
- **The settlement's government is state**: its kind, who leads, who sits on the council, its
  rules for elections and for votes, and the laws in force. The kind can change in the middle
  of a game
- **There is no government until there are three.** One or two people simply get along. When a
  third is living there the settlement chooses its kind of government: the residents choose,
  each by what they hold, with the player given a say. Dropping back under three undoes nothing
- **Two more sides to a way of being: charisma and leadership.** Charisma is how readily others
  are won over by someone; leadership is how well others do under them. Both are data like the
  other six, have a slider where the first resident is made (P16), and are in the middle for
  everyone in a save from before
- **A leader is a resident with a role**: `Resident.roles`, IDs that are saved, such as `mayor`.
  They fall ill, fall in love, steal, take to drink or worse (S24), lose an election, are
  locked up, resign, die, are killed or are thrown out, as anybody might
- **Losing a leader ends nothing.** Dead, gone or removed, the government's own way of
  succession names the next one, or the place stands empty until it does
- **Seven measures of the settlement, from 0 to 100**: legitimacy, public support, fear, unrest,
  political stability, authoritarianism and corruption. Each moves by itself: a settlement may
  be afraid and obedient, with little legitimacy and a great deal of resentment
- **A political profile for each resident**, kept apart from `Resident` as their tastes are:
  authoritarian tolerance, justice sensitivity, collectivism, individualism, revengefulness,
  fearfulness, political interest, loyalty to the leader and trust in the government. The
  player is not necessarily shown any of it
- **Obeying and resenting are kept apart**: someone may do as the government says and hate it
- **A political event is a domain event of a kind of its own** (`PoliticalEvent`), with who took
  part, who saw it and how much it matters, so that history, sound and the screen can follow
- Kind of government, leader, council and measures are saved, by stable IDs

Done when: a settlement of two has no government, and chooses one when a third comes to live
there; a settlement runs four weeks headless under each kind of government; a leader who
resigns is followed by another by the rules of the government in force; a mayor who dies leaves
a settlement that goes on, with or without a successor; and a settlement can be brought to high
fear with low loyalty to its leader.

Tests it is not done without: no government with two and one chosen with three; a change of
leader; the mayor's death without the game ending; fear apart from loyalty; a save from before
loading with charisma and leadership in the middle; and the module imported without pygame.

As it was built, where the lines above leave it open:
- **Of the module, S26 has** `government.py` (kinds as data, and the settlement's government as
  state), `profile.py`, `leadership.py` (choosing a kind, seats, succession), `legitimacy.py`
  (what each resident holds, and the measures), `political_event.py` and `politics_system.py`.
  The rest come with S27 to S29
- **Choosing takes twelve hours** from the minute a third resident lives there. Each adult who
  is in the settlement says which kind they would have, by how much each kind appeals to what
  they hold, and the one most of them want is the government. Its seats are filled there and
  then. How many wanted it is how legitimate it starts, and whoever did trusts it the more
- **The player's one proposal** (`ProposeGovernmentCommand`) adds to that kind's appeal with
  each resident by how they take advice. It can be made only while they are choosing
- **Five ways of coming to lead**, tried in the order a government lists them: a vote of
  everyone, a vote of the council, whoever is strongest, whoever the last leader would have had,
  and whoever has the most behind them. A vote goes by what each voter feels for whoever
  stands, by the candidate's charisma and leadership, and for whoever leads already by the
  loyalty they have earned or lost. Somebody votes for themselves only if politics matter
  enough to them
- **A vote for a seat left empty takes a day to hold**, and the seat stands empty meanwhile.
  The other ways name somebody at once, if there is anybody. Whoever stepped down is not the
  one to follow themselves. A seat nobody can be found for is tried again each day, and costs
  legitimacy while it stands empty
- **A term is eight weeks** where there are terms: whoever leads has to win again, and the
  council is seated anew
- **A leader thinks of resigning** when worn down or with nobody behind them, and the player
  may advise (`resign`)
- **A leader has in mind who would follow them** where the government goes by that: their
  partner, the grown kin they care for most, or whoever they think most of, if it is enough
- **What those who govern are seen, or said, to have done** tells on what each resident who
  learns of it holds: fear, loyalty, trust and resentment, each more or less by their leanings,
  by whether it was done to them, and by what they feel for whoever it was done to. Through
  them it tells on legitimacy, corruption and authoritarianism, and a government that is
  expected to abuse loses less legitimacy by it
- **Public support and fear are what the residents hold, on average.** Unrest and stability
  come to where the rest puts them a day at a time. Legitimacy, authoritarianism and corruption
  move only by what happens
- **Obeying** is worked out from loyalty, fear, trust and tolerance of a firm hand, and says
  nothing of resentment, which is kept by itself. Nothing asks for it until there are laws (S28)
- **Leadership tells on work**: under a leader at either end of it people work up to six in a
  hundred faster or slower, the more so the more loyal they are
- **Charisma and leadership** are in the data of the nine of the ready-made settlement
- Save version 30

Still open here:
- Who may propose, who approves, who votes, the leader's weight and the veto are in each
  government's data and nothing acts on them until there is something to propose (S27)
- Nothing a leader does as a leader exists yet: they lead in name, in what is thought of them
  and in how people work. What they decide comes with S27 and S28
- Nobody remembers how they voted, and nobody resents having lost: political memories are S27
- Abuse of power is only what anybody might do, done by somebody who governs. What only a
  government can do, such as punishing, is S28
- A leader who is away on a trip cannot stand in a vote held meanwhile, and loses the seat
- Unrest is a figure and nothing comes of it (S29)
- How much each kind appeals, and every weight in a vote, are first guesses. With the nine of
  the ready-made settlement, forty seeds chose a commune sixteen times, an assembly twelve, a
  council four, a ruler four, a mayor three and a commander once
- None of it is on screen: P26. Until then a government is proposed by command. Since
  S38 and P34 the player chooses the kind, from `Gobierno` in the menu

### S27 — Proposals, votes and laws (needs S26) — done
Asked first, in two batches, and answered: residents propose things of their own too, those the
government lets, when they have a reason; what can be proposed is all that was offered (an
election and another government, throwing somebody out, how the settlement trades, rationing
and common property) and, in the user's words, laws that change what people do: curfews, days
off, working hours, wages, rationing, punishments, taxes, "una buena lista de leyes tanto serias
como absurdas"; whether hands are shown or the vote is secret depends on the government; the
player may speak to whoever they like before a vote, once each, and whoever is pushed against
their own mind resists the more for it; trust in the player moves only with how what they were
behind turned out for each resident; a count can really be seen to; until there are trials each
resident keeps a law by how far they obey, and whoever is seen breaking one is marked; and
absurd laws are a list in the data and also whims of whoever leads.

So laws came here from S28, which keeps trials, punishments and their places.

- **The player proposes and the settlement decides.** A proposal goes into the process of the
  government in force, to the leader, the council or a vote as its kind says, and comes out
  accepted, changed or rejected. Only then does anything follow. Nothing the player proposes is
  simply done
- **What can be proposed**, as data (`data/proposals.json`): a law, doing away with one, a vote
  for who leads, another kind of government, throwing somebody out, a currency, going back to
  barter
- **A vote is yes, no or an abstention, and is worked out for each voter**: what they think of
  the proposal and of the people in it, what they hold, their fear, their trust in the
  government, what they stand to gain or lose, and what they remember. Somebody may vote down
  what would do them good because they hate the leader, or for fear of what follows
- **The player may work on residents before a vote**, and cannot cast it for them
- **The player's influence is a layer of its own**: for each resident, trust in the player and
  resistance to the player, and from them how much they lean on the player's advice. A resident
  may take the advice, change it, ignore it or do the opposite. It builds on advice (S4) and on
  the taste for being told what to do (S20)
- **Residents propose things of their own**, where the government lets them
- **Elections**, under the governments that have them. Who stands goes by interest, charisma,
  leadership and how they are thought of. A result leaves memories and consequences: a loser
  who resents it, a winner with legitimacy, talk of fraud, followers let down
- **A count can be seen to**, by a leader about to lose a secret vote, with the player given a say
- **Laws as data** (`data/laws.json`): each says what it does at each degree, what weighs for or
  against it with each resident and what brings somebody to propose it. A law changes what
  residents do and what follows from what they do. It is never only words
- **Each resident keeps a law or does not**, and whoever is seen breaking one is known to have
- **Absurd laws**, from the list and from the whims of whoever leads
- **What politics does is remembered**, and weighs on later votes, on relationships and on support
- Laws in force, proposals pending and decided, the history of elections, what the player is to
  each resident and whoever was thrown out are saved

Done when: the same proposal is voted for by one resident and against by another, each for
reasons that can be read back from who they are; a proposal the player makes is turned down, and
nothing of it happens; an election is held, its winner leads, and the result is still there after
saving and loading; those who took part remember it; and a law in force changes what residents
are seen to do over a week.

Tests it is not done without: a vote that follows the voter's own opinion; a proposal of the
player's rejected; an election whose result is kept; and political memories. They are in
`tests/test_proposals.py` and `tests/test_laws.py`.

As it was built, where the lines above leave it open:
- **Of the module, S27 has** `records.py` (what is kept), `opinion.py` (what a resident makes
  of a matter), `proposal.py` and `voting.py`, `law.py` and `law_system.py`, `election.py`,
  `influence.py` and `exile.py`
- **Somebody has to make the player's proposal theirs**: whoever may propose under the
  government and is most for it, counting what they make of the player. If none of them is
  for it, it goes no further, and is left alone for a week like anything turned down
- **A proposal waits twelve hours** to be decided, six when one person decides alone, and a
  day when it is to throw somebody out, whoever decides it: there is that long to speak to
  them. Three wait at once at most
- **Who decides is who the government says approves.** With nobody in the seat it names, the
  say falls to the council, and failing that to everybody. Whoever is away has no say. `votes`
  in a government's data is not acted on yet
- **It carries with the share the government asks for**, of those who said yes or no, and more
  for than against. Whoever leads refuses what others approved if they have a veto and are
  against it, which costs legitimacy
- **Changed means milder.** A law that does not carry as put is tried a degree at a time and
  passes at the first that carries. Nothing else is changed: it passes or it does not
- **A mind on a proposal has ten parts**, and a ballot keeps the three that weighed most:
  `conviction` (what they hold and stand to gain or lose), `target` and `evidence` (what they
  feel for whoever it is about, and know them to have done), `proposer`, `player`, `loyalty`
  and `grudge` (for or against where whoever leads stands), `fear`, `memory` and `lobby`.
  Somebody votes one way or the other only if their mind is far enough from the middle for
  their interest in politics. Nothing is rolled
- **Fear bends a show of hands only.** A mayor and a council vote in secret. An assembly, a
  commune, a command and a caudillaje show hands
- **After a show of hands** whoever was voted out, and those close to them, know who did it
  and hold it against them. After a secret vote, and in what the game tells of a vote for a
  seat, only how many is known
- **Residents raise one thing a day at most**, whoever of those who may wants something most,
  and nobody twice in five days: a law they hold with and have the reason for that its data
  gives, the end of one they cannot abide, a vote on a leader they neither follow nor trust,
  another government, or throwing out somebody they resent a great deal and know to have done
  wrong three times in a fortnight. Once was too little: the ready-made settlement threw Raúl
  out in its second week every time
- **What was turned down is left alone for a week**, and a law just passed is not put to be
  done away with for two days, nor one just done away with put again. Whoever had something
  of theirs turned down remembers it, and leaves that very thing be for four weeks
- **Nobody thinks unasked of resting whoever is expecting**: it is there for the player to put.
  Raised by residents it took a farmer off the land for months, and the settlement went
  hungry or, with her post covered, dark: whoever a law rests does not count among those who
  hold a job, so that somebody else is asked to see to it, and that somebody left the workshop
- **Speaking to somebody before a vote** adds up to 0.4 to their mind, by how much they lean on
  the player. Past sixty of resistance they do the opposite
- **Trust in the player** moves by up to twelve when something they put, or spoke up for, passes,
  by what each resident makes of it, and a little each day a law of theirs stays in force.
  Nothing that is turned down moves it. It also tells on any advice the player gives (S4)
- **Whoever is thrown out has four hours to be gone**, walks to the gate, and takes what they
  carry of their own. What they kept is nobody's. A leader thrown out is followed as one who dies
- **How the settlement trades** is a proposal where there is a government, and whoever governs
  decides it. With no government everybody still answers for themselves (S23). A resident who
  has had enough of how things are traded and may not propose has nobody to put it to, and
  holds that against the government
- **Whoever wants a seat enough stands**, and whoever leads does. With fewer than two, the two
  who mind least. Whoever puts themselves forward votes for themselves, which is not how S26
  had it: there everybody stood, and nobody voted for themselves unless politics was a great
  deal to them
- **A count is seen to only where votes are secret**: nobody miscounts a show of hands. Whoever
  leads and stands to lose makes up their mind six hours before, or half the wait if that is
  less. Enough votes change hands for them to win, and none is made up. Only whoever sees
  them at it knows
- **A loser says there was cheating** by how vengeful and how distrustful they are, more so
  after a near result or with the votes taken from them. Nothing follows but what is made of it
- **Twenty-two laws**, of the eighteen things a law can do. Fourteen serious: curfew, a day of
  rest, long or short hours, low or high wages, taxes, rationing, common property, a dry law,
  substances banned, the gate closed, meals for nothing, and rest for whoever is expecting.
  Eight absurd: silence at siesta, the hour of the radio, greeting whoever leads, a food
  nobody is to eat, the round at the bar, a holiday on the leader's birthday, nobody at the
  fire, and lamps out at night
- **Two of the laws put to the user came out otherwise.** Silence at the table is silence from
  two to four, because nobody could be spoken to while eating as it was. And nobody sitting
  down is nobody at the fire, because a stool is not something anybody uses
- **Keeping a law** goes by how far a resident does as the government says (S26), a fifth of
  the government's legitimacy, and thirty times what they make of the law, against a bar that
  a burdensome law raises and that moves a little from day to day. Legitimacy was not in what
  was asked: without it hardly anybody kept a law under a government with no leader, where
  there is no loyalty to count. Whoever leads counts as half loyal to themselves
- **A curfew** keeps whoever keeps it under the roof they are under, across open ground only
  to bed or for what cannot wait. Whoever is out and not at work is seen by whoever is about,
  looked into every quarter of an hour
- **Rationing** counts meals out of the commons. Nobody keeps it starving
- **How short the settlement is of food weighs on its laws**: with less than six units a head
  in the commons, a day of rest and short hours lose their appeal and long hours and rationing
  gain it, so that what was passed in plenty is done away with in want. Without it the small
  settlement of the opening voted itself a day of rest and short hours and starved to the last
  of them. Long or short hours are the end of the working day, not of every shift, and
  nobody bans the only thing there is to eat
- **Where a law gathers everybody**, whoever keeps it leaves their stroll or their post on the
  hour and stands within four tiles. At the end of it whoever is awake and not there is seen
  not to be, by those who are
- **Hours, wages, taxes, days off, common property and lamps** are the same for everybody:
  there is no breaking them
- **Whims** come to whoever leads a settlement half authoritarian or more, up to one chance in
  four a day for each law they fancy
- **Being seen to break a law** costs trust with whoever keeps it, and a leader seen to loses
  legitimacy by it. Two who break one together think the better of each other
- Save version 31

Still open here:
- None of it is on screen: P26. Until then all of it is done by command
- Nothing comes of breaking a law but being seen to, and nobody enforces one: S28
- Laws put to the user and not built: couples that marry or part, weapons for the guard alone,
  and children put to work or kept from it. The last two were S28's already
- Punishing a resident is not a proposal yet (S28), and nothing is built by proposing it: a
  building is still put to one resident (S16)
- Residents do not work on each other before a vote, and nobody campaigns: it waits for
  conversations (S34, S35). Factions weigh on nothing (S29)
- Everybody is taken to know what the law is. Only who broke it is known locally. And
  whoever proposes rationing or a tax is taken to know how much is in the larder and the fund
- Whoever keeps a curfew gets under the nearest roof, which may not be where they sleep: nobody
  has a home, only a bed
- Somebody who says there was cheating is believed or not, and nothing follows: no recount, no
  second vote
- A vote for a seat on the council leaves no memories, and nobody says it was rigged
- The player cannot take a proposal back
- Whoever is thrown out is never heard of again. Whether they are is S28's to settle
- Every weight is a first guess. Under a mayor nobody doubts, almost everybody keeps every law,
  and under an assembly about half do
- A settlement has no slack: two on the land feed nine, and five days with one of them off it
  empty the larder. Any law that takes hands from work is a risk for it, and what holds that
  off is only that want weighs on votes. In the ready-made settlement, where Raúl starts
  fights from the first day, a council or a leader may still throw him out within two weeks
- With a law resting whoever is expecting, the post left is covered by taking somebody from a
  post that matters less, and nobody goes back when she does

### S28 — Trials and punishment (needs S27, and S23 to S25) — done
Asked first, and answered:

- **Prison is whole days locked up**, and in the user's words "se configura cuanto y que come
  y bebe": the player says how much a prisoner is given each day, and of what
- **Somebody exiled may be heard of again, both ways that were offered**: at the gate, asking
  to come back, and with raiders for one who left with a grudge
- **Residents accuse of their own accord, and the player may too**
- **What somebody found guilty is given is the player's to say, always.** Not the
  recommendation, which was that whoever decides in the government chose it and the player
  was asked before the harsh ones

What follows from the last: a punishment is not a proposal, as this milestone was written to
have it. Whether somebody is guilty is decided as the government decides anything; what they
are given is not decided by the settlement at all.

Built:
- **Somebody is tried for what is known of them, and never for what only the world knows**: a
  thing they did that left a fact, that somebody else who is here saw or was told of, and that
  nobody was tried for. One trial at a time, and nobody twice for one thing
- **What can be tried is data** (`offences` in `data/punishments.json`): a theft, a fight, a
  law broken, a vote rigged, a death. Each has a gravity from 1 to 10
- **Whoever knows of something may accuse**, once a day: by how grave it is, what they feel
  for whoever did it and how much justice matters to them, and never their partner or their
  kin. It is theirs to decide, with the player's advice. The player accuses with a command
- **A trial in six steps**, an hour apart: accusation, evidence, witnesses, defence, verdict,
  punishment. Who saw it is told from who only heard it
- **Each of those who judge holds the accused guilty or not on what they believe they know**:
  what they saw, what they were told, the word of the witness they trust most, and what they
  feel for the accused and for whoever accuses. Those who judge are whoever decides anything
  under the government in force, or every adult where there is none
- **A scale of nine punishments, as data**, each with a severity from 1 to 10: `warning`,
  `fine`, `confiscation`, `community_service`, `public_stocks`, `prison`, `corporal_punishment`,
  `exile` and `execution`
- **A punishment needs its place**: prison a building whose use is `jail`, the stocks a
  `stocks`, and death a `gallows` or a `guillotine`. The three are objects to put down and the
  jail a use to give a building, and nobody is sentenced to what there is none of
- **A fine goes into the common fund**, in coin as far as they have it, or under barter in
  things of theirs worth as much. Confiscation takes what is worth most of what they carry
- **Whoever is locked up or in the stocks goes there and stays**, doing nothing else, for
  their days or their hours, and sleeps where they are
- **A prisoner is given what the player says**: so many meals and drinks a day, of an item
  named or of whatever there is most of, out of what is nobody's. Given nothing they starve
- **Exile is walking out for good** (S27), and then being heard of again in five to twelve
  days: with raiders, the likelier the more they held against the government as they left, or
  at the gate, where whoever is there decides with the player's advice. Let back in they are
  who they were, kin and all. Turned away, or finding nobody three days running, they are gone
- **A punishment is a political event that records** who was condemned, for what, to what, who
  was there, which of them were kin or friends, and how each took it
- **Each takes it their own way**: approval, fear, anger, grief or indifference, by whether
  the condemned is one of their own, whether they hold them guilty, and how far the
  punishment goes beyond what was done. Each moves what they hold of the government, leaves
  a memory in their own words, and moves legitimacy and unrest by how many took it how
- **A child can be tried and punished like anyone**, and it counts three times over with
  whoever takes it ill. Nobody approves of a harsh one
- **Nothing gory is shown**: what is kept is what happened and what came of it
- Trials, sentences, the history of punishments and what prisoners are given are saved, with
  nothing of it in an older save. Each thing the player does is a command: `AccuseCommand`,
  `SentenceCommand` and `SetPrisonRationCommand`. None had a screen until P64

Decided without asking:
- With no word from the player in a day, somebody found guilty is given a warning
- A prisoner is given three meals and two drinks a day until it is said otherwise: fewer
  meals than that and they go hungry, as anybody would
- Found innocent, the accused holds it against whoever accused them, and nothing else
  comes of it
- Whoever is not there for a punishment that is not done in public takes it half as hard
- Somebody exiled comes to the gate once. A second exile of the same person is another going
- Work for everybody is their days as they were, weighing on their nerves: they are not
  set to anything in particular
- The jail and the three objects have the game's plain sprites, and no picture of their own
  on the window: that is P26

Still open here:
- **The laws that need a court are not written.** They are S43, after this one
- Nobody defends anybody: the defence is a step with nothing said in it that changes a mind
- A prisoner cannot be let out early, nor a sentence changed once given
- Whoever is locked up keeps their post and their house, and is paid nothing for not working
- Nobody breaks out, and nobody helps anybody to
- A prisoner who starves is a death like any other: nobody is held to answer for it
- What somebody exiled does out there is not played: they are a date and a grudge
- A fight in which somebody died is tried as a death only if somebody saw who struck

### S43 — The laws that need a court (needs S28) — planned
Left out of S28, which had the trial and the punishments to build, and re-cut here.

- `weapon_restrictions`: who may carry what, and being seen with it is breaking it
- `election_rules`: who may stand and who may vote
- Children put to work, or kept from it, by law
- Couples that marry or part by law
- `theft_penalties` as it was written no longer has a place: a law cannot say what a thief is
  given, since that is the player's to say (S28). To be asked: whether a law may narrow what
  the player can choose from

### S29 — Unrest and factions (needs S28) — planned
- **Trouble of eight kinds, as data**: `protest`, `refusal_to_work`, `sabotage`, `riot`, `coup`,
  `forced_election`, `settlement_split` and `revolt`
- **A crisis comes of three things together**: unrest over its mark, legitimacy under its own,
  and more means to resist than fear can hold down
- **What is done to children brings it on sooner** (S25, S28): unrest rises faster for a child
  worked, hurt or punished than for anything of the kind done to an adult
- **A crisis is not the end of the game.** A rebellion may change the leader, change the
  government, split the people, throw the leader out, bring on an election or leave a rival
  faction behind
- **Factions come about by themselves**, and there need not be any: from strong ties, from what
  people hold, from being against the leader, from a common interest, from an old quarrel.
  Such as `supporters_of_marta`, `anti_mayor_bloc`, `military_group`, `communalists`
- **A faction is laid over relationships and takes the place of none**
- Factions weigh on who stands in an election and on how its members vote (S27)
- Factions are saved

Done when: unrest kept high brings a protest; with legitimacy low and little fear to hold it
down, a rebellion changes the leader or the kind of government, and the settlement goes on for
weeks afterwards; a faction forms in one run among people who were already close or of a mind,
and in another run none forms at all.

Tests it is not done without: a protest from high unrest; and a rebellion that changes the
government.

Still to settle:
- What a split settlement is: whether those who leave are gone for good, or are a place outside
  that can be heard of and met again (S10, S11)
- What somebody's means to resist are counted from: how many they are, weapons, who keeps
  the watch

### P26 — Politics on screen (needs S26 to S29) — planned
The entry in the menu, the kind, the seats, the measures and the laws in force are built: P34.

- A government entry in the menu: its kind, who leads, who sits on the council, the laws in force
- The choosing of a government, when the third resident comes, as something seen and advised on
- Charisma and leadership where the first resident is made, beside the other sides (P16)
- Who holds which role seen on the map and in their panel, and a seat that stands empty
- The jail, the stocks, the gallows and the guillotine, in Urbanismo and in their editors
- Where a proposal is made, and where it is seen to go: who has it, how each vote went, what
  came of it. Until then proposals, speaking to whoever decides and backing a candidate are
  commands (S27)
- The laws there are to propose and the ones in force, at what degree, and who is seen to break one
- Somebody thrown out seen to walk to the gate and through it
- A leader making up their mind about the count of a vote, and what is advised
- An election, a trial and a public punishment seen as they happen, with nothing gory
- Accusing somebody of what is known of them, saying what somebody found guilty is given out
  of what there is a place for, and what prisoners are given to eat and drink: done as P64,
  a tab of the government's panel
- Somebody exiled seen at the gate when they come back, as a stranger is (P25)
- Trouble on the map: who has stopped work, who is out protesting

Still to settle:
- How much of the settlement's measures the player is shown, and whether as figures or as the
  mood of the place. What each resident holds is found out, as their tastes are, and not read
  off a panel
- Whether the player is shown how a vote is going to go before it is held, and what each
  resident makes of the player, or has to find both out

### P27 — Picked up and put down (needs P10) — done
The user's idea: residents can be dragged and dropped, and where one is dropped is what they do.
It is built with the layer of resources, after P59, as the user said on 2026-10-08: dropping
somebody on a post is one of the two ways of putting them to it (S52).

Asked first, in two batches, and answered on 2026-10-08:
- **They are where they are let go, at once.** They do not walk there
- **Let go over somebody, the wheel opens on what the two can do** (`Social`, with who it is
  with already said), with them stood beside the other
- **Let go over a post somebody has, the two change posts**: each has the job and the post the
  other had, and whoever changes with somebody who had none is left with none
- **Let go over a building with its roof on, it is gone into with them still in the hand**, to
  be put down in there with a click. Not the recommendation, which was to leave them at its door
- **Time stands still while somebody is in the hand**, and goes on as it did when they are let go
- **Being carried is nothing to them**: it tells on no nerves and on nothing they make of the player
- **A child who is still a bundle is taken up the same way**: let go over somebody, they carry it
  from then on; anywhere else, it is laid down and stays
- **Let go over bare ground they are there and go on with their day**, and take up again what
  they had been told to do

What there is:
- **A press on somebody on the map, pulled away with the button held, takes them up.** They hang
  from the pointer by the scruff of the neck and swing as it moves, further at the feet than at
  the head, in front of everything. From afar it is their face that goes with the hand. A press
  that goes nowhere is still a click, and a pull on bare ground still moves the map
- **What the hand is over is picked out, and a caption says what would come of letting go**:
  the post and what they would make of it, as the board says it (P59), and `fuera de turno`
  where they would not set to it there and then; who they would change posts with; `Dormir`,
  `Comer`, `Beber`; `Con Raúl: elegir qué hacen`; `Dejar aquí`. A ring on the ground says where
  they would be stood. Where they cannot be put it says why, in red
- **`Tab` goes on to whatever else could come of it**, where more than one thing could: a pot
  is the cook's post and is eaten from. A post is a post first, and after that what it is used
  for, and after that only being left beside it
- **What they are put down on is what they set about, as an order** (S37), done before
  whatever they had waiting: a free post is theirs, and they work at it if they have a shift
  ahead; a bed, a pot, a tank, the bar, the radio is used, that very one; a seat is sat on;
  what is lying about is taken apart; a site is in their charge. Where nothing can come of it
  they are left beside it: a bed that is somebody else's, a pot with nothing in it
- **A hand at the edge of the map pulls the view along**, the keys that move it still do, and
  the wheel still brings it nearer or further. Nothing else is opened meanwhile
- **The other button, or `Esc`, lets go of them where they were.** So does letting go over a
  panel. Whoever cannot be told anything cannot be taken up, nor whoever serves a sentence
  where they are kept, and it says why
- **Inside a building it is the same**: whoever is in there is taken up by pulling away from
  them and put down on the floor, on a bed, on somebody. `I`, with somebody in the hand, goes
  back out with them
- **A child in its blanket is taken up off a back or from where it lies.** In the arms of
  somebody grown who is in a state to, it is theirs to carry and to feed, before its own, for
  as long as they can. Laid down, it stays: in a bed it comes to no harm, and anywhere else it
  is the worse for it as it always was, still fed by whoever sees to it. Before it is half
  gone they take it up again, and it is said
- The simulation gets it as two commands, `PutDownCommand` and `PutBundleCommand`, by stable
  IDs, and says what a drop would do without doing it (`SimulationWorld.placements`): it runs
  and is tested with no screen

Decided without asking:
- **Dropping on a post gives it, for good**, as `Poner` on the board does. It was the reading
  the user was given before the batch and did not correct
- **Nobody is told to work out of hours** (S37): a post given at night is theirs, and they are
  left to their evening
- **The post of somebody who is out of the settlement is not changed behind their back**:
  whoever is dropped on it is left beside it
- **Nobody is put where they could not have walked to, nor on a tile somebody else stands on
  or is making for.** Dropped on a thing, they stand on the free tile beside it that is nearest
  the hand
- **Somebody asleep, dropped on, only has the other left beside them**: no wheel opens
- **Taking apart is what a drop on a wreck, tyres or junk does**, as its first thing. It is
  said before the button is let go, and it can be taken back like any order
- **A bundle handed to somebody stays theirs** until it is handed to somebody else, as long as
  they can see to it. Only somebody grown, fit, sober and free is handed one
- **A bundle laid down is taken up again at half its health** (`taken_up_below` in
  `data/family.json`), so that nobody loses a child to having put it down and forgotten it.
  With nobody to see to it, it is as it was: someone is asked to take it in (S25)
- **What a use is called for short is data**: `label` on a `use` in `data/interactables.json`
- **Using one thing in particular is an order of its own** (`task:use`, with the thing as what
  it is about), so that it is saved, shown in what they have ahead of them, and gone back to
  if they are stopped on the way. It is not in the wheel: S60 is where a thing gets its ring
- The save went to version 41: `keeper` and `set_down` on a bundle

Still open here:
- **The hand hangs them, and no more.** They do not struggle, and a doll hangs in the clip it
  stands in, swung about the hand: there is no clip of its own for being carried
- **A thing under a roof that is on cannot be dropped on from the map**: the building is gone
  into first. With roofs off (`T`) it can
- **Inside, what is dropped on is the tile of the floor under the hand**, and whoever stands
  there. The upper part of something tall counts as the floor behind it
- **Nothing is dragged but people**: not things from one store to another, nor a tool into a
  hand. Giving somebody something by hand is S59
- Whether somebody should mind being carried about after all, once it has been played with.
  What the player is to a resident is already there (S27), one number away
- **There is another of these, on the branch `feature/DragDrop`**, built the same day in
  another session and not known of here until this one was done: it was asked for by the
  user as a branch, is pushed, and is not merged. It was built to other answers on two
  points: on a post somebody has, whoever was there is put out, where here the two change
  posts; and time goes on while somebody is carried, where here it stops. It also picks up
  things on the map and things in an inventory, which this does not, and does nothing
  inside a building, which this does. What it calls S51 is its own simulation, not the
  books of S51 here. **Which of the two stays is for the user to say**, and neither is to
  be merged into the other before they do

### S30 — What a thing is for, and what is in it (needs S19 and S20) — planned
Content comes in four milestones, S30 to S33, and a screen, P28. They are the user's brief: keep
`ItemDefinition` from becoming everything, and tell apart physical things, cultural content,
activities and living beings.

What holds for all four:
- Built-in and custom content go through the same models and registries
- Nothing behaves by its display name: stable IDs, categories, tags and properties only
- A pack adds items, media and activities without touching code, and can never run code of its
  own: data says what can be done with a thing, and the game's code does it
- An animal is never an item. A song or a written work need not be a physical thing. A physical
  copy may point at cultural content
- What a thing is worth is different for each resident, and any thing can come to mean something
- Tastes come in through tags and `preference_tags`, which a pack may add to (S19, S20). No
  inner figure is shown to the player
- Bad content gives a warning and a fallback, and never stops the game. A save that names
  something a removed pack defined still loads, with a placeholder or the unknown ID kept
- Classes stay small: neither `ItemDefinition` nor `Resident` grows into a god object
- All of it runs headless, without pygame

What there is already to build on: items with a `category`, `tags`, `preference_tags` and
`properties`, and copies with an owner, a condition and who gave them (S6, S23); tastes for
tags, categories, single items and people, which change with what happens (S19, S20); packs
under `custom_content/` for items and foods; and a radio that can be listened to (S17).

This one:
- **A thing says what can be done with it, by ID**: `"uses": ["play_music"]`. Each use is a
  handler registered in code: `play_music`, `read`, `play_game`, `listen`, `watch`, `repair`,
  `pet` to begin with. A use nobody has registered is a warning, and the thing is still a thing
- **Cultural content has a definition of its own** (`MediaDefinition`), apart from any object:
  an `id`, a `media_type` (`music`, `written_work`, `radio_program` to begin with), a `title`,
  `tags` and `preference_tags`
- **A physical thing may hold content or give access to it**: `"contains_media": "song_blue_dust"`
  on a cassette, a written work on a book. Many copies may hold the same content, a copy can be
  stolen, and the song is still one song
- **A book is a copy and what is written in it.** Two residents may each have their own copy of
  the same work. Reading may entertain, ease nerves, move mood, teach a skill, give knowledge,
  leave a memory or something to talk about, and which of these goes by the content's tags
  (`medicine`, `technical`, `romantic`, `fiction`, `survival`, `history`) and never by its title
- **Music is heard by whoever is there to hear it**, by the usual rules of place, distance and
  presence, and never by the whole settlement. A radio, an instrument or a cassette may start
  it. Each hearer's reaction is worked out from the piece's `preference_tags` and their own
  tastes, and may move mood and nerves, show a taste, leave a memory and something to talk
  about. Those who hear it together have shared something, and it may tell on what they feel
  for each other
- Packs add content under `custom_content/media/<type>/<id>/data.json`, checked as items are:
  IDs, text, tags, `preference_tags`, references to media that exist, and safe paths
- Events of low importance for everyday leisure: `media_consumed`, `music_heard`, `book_read`.
  Nothing that would only be noise is emitted
- What a copy holds is saved by ID

Done when: a song exists with no object for it, and a cassette that holds it can be played to
whoever is in the room and to nobody else; two copies of a manual are read by two residents and
teach each of them the same; one resident is the better for a piece another cannot stand; and
a pack adds a song and the cassette for it with no change of code.

Tests it is not done without: a physical thing and cultural content kept apart; two physical
copies pointing at the same book; a cassette pointing at a song; a custom `MediaDefinition`
loading with no change of code; tastes telling on the reaction to music and to a book; a save
whose pack is gone, with media it named, still loading; and the simulation importing no pygame.

Still to settle, to be asked before it is built:
- Items of a kind are kept in stacks (`quantity`). A copy with content of its own, or a
  history (S32), cannot be one of a stack: which things stop stacking, and when
- Whether what a book teaches is a skill, which nothing has yet, something worked out as at the
  study desk (S17), or both
- Whether content is known to a resident once they have read or heard it, and what a second
  reading does
- Where the songs and the works the game comes with are from: written for it, or only named
- Whether `watch` has anything to be watched yet, or waits for a thing that shows pictures

### S31 — Things to do together (needs S30) — planned
- **An activity is data** (`ActivityDefinition`): an `id`, the tags an item has to have
  (`required_item_tags`), the kind of object it takes (`required_object_kind`),
  `min_participants` and `max_participants`, a `duration`, `tags`, `preference_tags`, and
  whether it is `social` and `competitive`. `reading`, `play_cards`, `chess`, `music_session`,
  `dancing` and `storytelling` to begin with
- **No action is written for one leisure object** where an activity definition will do
- **Residents choose it for themselves** (Utility AI), by how much they want entertaining and
  company, their mood, their way of being, their tastes, what there is to do it with, and what
  they feel for whoever else would be in it
- **Something done together leaves something behind**: what those in it feel for each other,
  memories, things to talk about, a winner and a loser where there is one, and a small quarrel
  now and then
- An activity and what is used for it go through the same tastes as everything else
- Packs add activities under `custom_content/activities/<id>/data.json`
- Events: `activity_started`, `activity_finished`, `game_won`, `game_lost`, of low importance
- Only what matters is remembered: "Raúl siempre me gana a las cartas", and not every hand played

Done when: two residents with a pack of cards sit down to a game of their own accord, one wins,
and both remember it differently; somebody who cannot stand games is not found at the table;
and a pack adds an activity that is played with no change of code.

Tests it is not done without: an activity that requires an object; the Utility AI choosing a
leisure activity; and tastes telling on the reaction to an activity.

Still to settle:
- Whether wanting to be entertained is a need of its own or comes out of mood and nerves (S15)
- What decides who wins: chance through the settlement's own randomness, something about the
  two of them, or a skill
- Whether the player can suggest an activity to somebody, as they can a job (S4)
- Whether leisure has its hours, or is whatever is done with time left over

### S32 — What a thing means to somebody (needs S30) — planned
- **Any copy of a thing can come to mean something.** There is no category for it
- **A copy has a history**: entries with the kind of event, who was in it, when and how much it
  mattered (`ItemHistoryEntry`). A present from somebody dear, a thing left by the dead, a thing
  used at a moment that mattered, a thing that belonged to somebody who died, a thing tied to
  what two people are to each other, a thing brought back from a trip that counted
- **What it means is kept for each resident** (`sentimental_value_by_resident`), and nobody
  else comes into it by being handed the thing
- **A copy may be given a name of its own** (`custom_name`)
- **What a thing is worth to somebody is worked out when it is asked for**, from what it is
  worth to anybody, how much they need it, how much they like it, how scarce it is and what it
  means to them. No single figure is kept where it can be worked out again
- **Some residents come to collect a kind of thing**: books, records, things of the old world,
  toys, weapons, art, relics that still work. A common thing may be worth a great deal to one
  of them
- All of it tells on buying, selling, swapping, giving, stealing and keeping (S6, S23)
- Events: `item_history_changed`, `sentimental_attachment_changed`
- Memories where it matters: "Marta me regaló esta guitarra", "Escuchábamos esta canción cuando
  murió Tomás", "Encontré este libro durante la gran tormenta"
- A copy's history, what it means to whom, and who collects what are saved

Done when: a guitar given by a friend is worth more to its owner than the same guitar is to
anybody, and is not sold at the price that would buy another; whoever it is stolen by feels
nothing for it; and a collector pays over the odds for a thing nobody else wants.

Tests it is not done without: a thing given as a present coming to mean something; a thing
that means something being worth more to its owner; another resident not coming into that
meaning with the thing; and collecting changing what a thing is worth to somebody.

Still to settle:
- Whether a taste for collecting is a taste like any other (S19), a trait, or something that
  grows from what somebody has happened to keep
- What losing a thing that meant something does: stolen, broken, sold in need, or given away
- Whether a thing's meaning passes to the kin of whoever died owning it (S25)
- How long a history is kept, and what is dropped from it first

### S33 — Animals (needs S14, S15 and S19) — planned
- **An animal is a living being of its own kind** (`Animal`), never an item. What it shares
  with a resident it shares by composition, or through a common base, whichever sits better
  with what there is: an ID, a `species`, a name, an age, health, hunger, nerves, a plain mood,
  a way of being, a place, what it is doing, and who it is tied to
- **It need not have what a resident has.** No tastes, no politics, no jobs, no knowledge of
  facts
- **What there is between a resident and an animal runs each way by itself**: affection and
  attachment from the resident, trust, fear and affection from the animal. Marta may dote on a
  dog that trusts her and is afraid of Raúl
- **A small part of the Utility AI**: it moves about, sleeps, eats, looks for attention, runs
  from what frightens it, falls ill, is looked after and takes to people
- **Nobody owns an animal outright.** It has those who look after it (`caretaker_ids`) and those
  it is bonded to, and may live with several, change hands, belong to the whole settlement or
  to nobody
- Events and memories: `animal_adopted`, `animal_fed`, `animal_missing`, `animal_injured`,
  `animal_died`, `animal_bond_changed`. Feeding is of low importance, and is not always said
- **The death of an animal tells hard on whoever was bonded to it**
- Species are data, as everything else is
- Animals, what they are like, how they fare and who they are tied to are saved, by stable IDs

Done when: a dog walks into the settlement and is taken in by somebody; it eats, sleeps and
follows whoever feeds it; it keeps away from whoever struck it; and when it dies whoever loved
it is the worse for it for days, and somebody who never cared is not.

Tests it is not done without: an animal not being an item; an animal moving and having its
basic needs; what a resident feels for an animal and what it feels for them kept apart; the
death of a pet telling on the residents bonded to it; and animals and their bonds surviving a
save.

Still to settle:
- Which species to begin with, and whether any of them work: a dog on watch, a cat at the
  pantry's mice, hens that lay
- Where animals come from: with a newcomer, in off the wasteland, from a caravan (S23), born here
- What they eat, and whether it comes out of the pantries the residents eat from
- Whether an animal can be eaten when there is nothing else, and what that does to whoever
  loved it
- Whether a child's first bond is with an animal (S25)

### P28 — Leisure, keepsakes and animals on screen (needs S30 to S33) — planned
- A book read, a cassette played, an instrument in the hands, a hand of cards at a table
- What is playing heard where it is playing, and from as far as it carries (P8)
- A thing's history and what it means, in its entry, as far as the player has seen it happen
- Animals on the map, and what they are to whom in a resident's panel
- New things, new media and new activities made in the game's own editors, as items are (P17)

Still to settle:
- Whether an animal is drawn by the player, as a resident is (P17, P19), or comes drawn
- How a song a pack adds is heard: a recording the pack brings, or only its name and its mood

### S34 — What is said (needs S2, S3 and S20) — planned
Conversation comes in two milestones, S34 and S35, and a screen, P29. They are the user's brief:
talk is a real part of the simulation, and tells on relationships, knowledge, rumours, feelings
and decisions. No dialogue is written out by a language model yet.

What holds for all of it:
- **The simulation decides what a conversation means, and the presentation how it is put.**
  Text is never the truth of the game: no words, generated or not, change the world
- A conversation holds meaning: a topic, an intent, a tone, facts, keywords, who is in it, its
  turns and what came of it. The screen holds the wording
- **Nobody is all-knowing.** A resident speaks only of facts they know, rumours they have heard,
  and what the game expressly lets them work out. Nothing is taken from what the world knows
- A rumour and a fact stay two things: what is told keeps who told it and how far it is believed
- Topics are never chosen by chance alone. The settlement's own randomness breaks ties and
  gives a little variety, and the same seed gives the same talk
- Small talk fills neither memory nor the event log
- What talk does to people comes of the simulation, each way by itself as always
- The player influences and never controls: where talk leads to something irreversible, the
  usual chance to advise is kept (S4)
- Whatever writes dialogue one day only puts into words what has already been settled
- All of it runs headless, without pygame

What there is already to build on, and is not to be made twice: exchanges as data (`chat`,
`argument`, `heart_to_heart`, `fight` and those of romance, S2 and S9); facts and beliefs with
their source and credibility, and rumours passed on in a chat (S3); the decision before a fight
(`fight_brewing`, S4); tastes that show when something is mentioned (S20); and what each
resident holds about the government (S26).

This one:
- **A conversation is a thing of its own** (`Conversation`): an ID, who is in it and who began
  it, a topic, an intent, a tone, where and when, how much it matters, the facts it is about,
  its keywords, its turns, a status (`active`, `finished`, `interrupted`) and an outcome. It
  keeps no narrative text as its truth. It grows out of the exchanges there are, in
  `simulation/social/`: `conversation.py`, `conversation_turn.py`, `topics.py`, `intents.py`,
  `topic_selection.py`, `conversation_resolution.py`, or whatever names sit better with what
  is there
- **Topics have stable IDs and are data**, so that a pack can add one: `daily_life`, `food`,
  `food_shortage`, `water`, `work`, `weather`, `merchant`, `theft`, `fight`, `injury`, `death`,
  `romance`, `breakup`, `friendship`, `rumor`, `politics`, `government`, `election`,
  `punishment`, `expedition`, `newcomer`, `pet`, `music`, `book`, `hobby` to begin with
- **What somebody is after is kept apart from what it is about** (`intent`): `chat`, `gossip`,
  `inform`, `ask`, `ask_help`, `complain`, `convince`, `debate`, `accuse`, `defend`,
  `apologize`, `comfort`, `thank`, `negotiate`, `flirt`, `confess`, `threaten`, `warn`. Two may
  talk of the same theft wanting different things of it
- **How it goes is a tone**, which may change as it goes: `neutral`, `friendly`, `excited`,
  `nervous`, `sad`, `angry`, `hostile`, `secretive`, `romantic`, `awkward`
- **A turn is a thing said, with no sentence to it** (`ConversationTurn`): who speaks and to
  whom, the speech act, who and which facts it is about, how strongly it is felt, a stance and
  when. Three to eight turns as a rule, set by kind and by how things stand. How long it takes
  in game time is worked out apart
- **What can be said is what is known.** Marta, who knows food is missing and not who took it,
  can speak of the theft, the food and the pantry, and not of Raúl. If she has heard it said
  that it was Raúl she can pass that on, as hearsay and no surer than she holds it
- **Telling passes knowledge on**: whoever is told has it from then on, with who told them, how
  far it is to be believed, and whether it was seen or only heard. They may believe it, doubt
  it or make something else of it. A rumour is never made true by being repeated
- **A topic is chosen by a score**: how recent it is, how much it stirs them, how much it
  interests them, how much it has to do with whoever listens and with what they need just now,
  what the two are to each other, what it is worth as gossip and how much it matters to the
  settlement, less for having been gone over lately
- **What matters gets talked about because people know of it**: a killing, a caravan, a theft,
  an election, a death, a newcomer, a storm, a wedding, a birth, a raid. There is no switch for
  "everybody is talking about it": each speaks of it only if it has reached them
- **Who has talked of what with whom lately is kept, lightly** (`ConversationHistory`), so that
  the same thing is not gone over again and again
- **Who to talk to is chosen too**: by who is near, how sociable they are, friendship,
  affection, trust, attraction, resentment, fear, how much they want company, what they have
  in common, and what there is to say to them. Not always whoever is liked best
- **Talk may tell on** affection, trust, resentment, attraction, fear, mood, nerves, what is
  known, rumours, memories, friendship and what there is between two. Much of it changes
  nothing but the want of company
- **Keywords are made from what is really known of the topic**: the topic's own words, who is
  in it, where, what things are called, the facts that matter. They are for showing, and
  nothing in the game depends on them
- **A snapshot for whoever shows it** (`PresentationSnapshot`): topic, tone, keywords,
  importance and who is in it
- **A way to put a turn into words, apart from what it means** (`DialogueRenderer`): it is
  given the turn, the conversation, what is publicly known of who speaks and the facts they
  know, and gives back text. It can make no fact, change no feeling, settle no outcome, add no
  knowledge and touch no memory. The first one gives keywords and murmur. No language model is
  wired in
- **Only talk that matters makes itself known**: small talk is of low importance, a rumour of
  weight or a serious quarrel more, a threat or a grave accusation the most
- **A memory only where it counts**: strong feeling, high importance, a relationship that
  changes for good, a secret out, a confession, a threat, a humiliation, a making-up. Never one
  for each turn
- Events with who took part, who saw it and where, as events have: `conversation_started`,
  `conversation_finished`, `conversation_interrupted`, `topic_shared`, `rumor_shared`. None for
  a turn of no account
- What is kept of a conversation that matters, and who has talked of what lately, is saved

Done when: two residents talk about a theft, one to gossip and one to accuse; a resident who
does not know who did it cannot name them, and one who has heard it said passes it on as
hearsay; yesterday's killing is what people who know of it talk about and last week's weather
is not; the same two do not go over the same thing all day; and all of it can be followed with
not one sentence written.

Tests it is not done without: a conversation between two residents; a resident not speaking of
a fact they do not know; a rumour being passed on; a rumour not becoming true by itself; a
recent topic coming first; the same topic not being gone over constantly; what two are to each
other telling on who is talked to; friendly talk improving a relationship; keywords coming of
known facts; a conversation working with no full text; conversations that matter surviving a
save, if any need to; the simulation importing no pygame; the same seed giving the same
result; and the renderer changing nothing in the game.

Still to settle, to be asked before it is built:
- Whether `chat`, `argument` and `heart_to_heart` as they are become kinds of conversation, or
  stay and conversation is laid over them
- What a resident may work out for themselves, beyond what they saw and were told: nothing yet,
  or a few plain inferences such as "it went missing while only he was there"
- Whether a listener's doubt goes by who tells it alone, as now, or also by what they already
  believe and by what they would rather were true
- How much of a finished conversation is kept, and for how long
- Whether a pack's topic can bring its own way of scoring, or only its words and its weights

### S35 — Where talk leads (needs S34, S26 and S31) — planned
- **Three or more can be in it.** Each has a stance, a response of their own and how willing
  they are to speak: on how the place should be run, Marta wants a vote, Raúl a strong hand, and
  Inés food and quiet before either
- **Talk can turn**: friendly, then a disagreement, an argument, an insult, a fight brewing. Most
  disagreements go no further. It goes by aggression, impulsiveness, nerves, resentment, what
  the two are to each other, how touchy the topic is, the tone and what has been said so far
- **A fight never starts out of a conversation directly**: talk that comes to `fight_brewing`
  goes through the decision there is, with the player given a say (S4)
- **Talk can mend as well**: an apology taken, a making-up (`conversation_reconciled`)
- **Flirting and saying what one feels are intents**, and go into the romance there is (S9).
  Talk does not make two people a couple: what settles that already settles it
- **Talk about politics** changes what somebody holds, passes arguments and political rumours
  on, and raises or lowers support (S26). No sentence changes a vote: talk moves what a vote is
  later worked out from (S27)
- **What people do gives them something to say**: a song somebody loved, a book just finished,
  a new animal in the settlement, a hand of cards that ended in jokes or in a quarrel (S30 to S33)
- **A conversation can be cut short**, by work, by hunger that will not wait, by a fight, an
  emergency, the two being parted, a death or something grave happening, and is left with an
  outcome that makes sense of it
- Events: `argument_escalated`, `conversation_reconciled`

Done when: three residents talk over how the place is run and one of them comes away thinking
differently, with nobody's vote having been touched; a quarrel over missing food comes to a
fight brewing and the player is asked before a blow lands; somebody who has just finished a
book brings it up; and a conversation broken off by a raid is on record as interrupted.

Tests it is not done without: a conversation of a group; an argument raising resentment; a
grave argument coming to `fight_brewing`; `fight_brewing` keeping the chance to intervene; a
political topic telling on what somebody holds; and something cultural giving a topic.

Still to settle:
- Whether a third can walk up and join two who are talking, and whether anybody can listen in
  without being in it (S3)
- Whether somebody can be talked round to a thing they will then do, such as leaving a partner
  or standing for a seat, and how that sits with the player's own say
- Whether a threat is only talk, or something the one threatened acts on
- Which topics are touchy, and whether that is the same for everybody

### P29 — Talk overheard (needs S34) — planned
- **What is seen of a conversation goes by how close the view is**: a bubble from afar, a word
  or two from nearer, and close by the murmur of it: "pss... comida... robo... Raúl..."
- **Its tone is seen in how it is written**: loud and broken where it is hostile ("¡COMIDA!...
  ¡RAÚL!..."), trailing where it is sad ("...Tomás... hospital...")
- Icons for topics and for what somebody is after, single words, murmur and short summaries
- **How near the player looks changes nothing of what residents know**: the player watches, and
  is nobody standing there
- Only talk that matters is brought to the player's notice
- A place for the `DialogueRenderer` to be changed for another, with the game none the wiser

Still to settle:
- Whether voices (P14) murmur along with it, by tone
- Whether the player may hear everything said in the settlement, or only what is near where
  they are looking
- Whether a language model is ever wired in, and if so where it runs

### S36 — Building is a task, and scrap from what lies about (needs S16) — done
The user's correction: "la construcción debe ser una tarea y no algo de ratos libres", and with
it a way never to be left stuck for want of scrap. Asked first, and answered: whoever agrees to
a site sees to it as their work, in place of their post, until it stands; a builder with
nothing to build with sits down and asks for it, and clicked on can be told what they may take
apart; what lies about is used up, and with none left the builder goes out for scrap
themselves; and of items, what is common is broken up at once and what is somebody's is put to
them, and they decide.

- **A site in somebody's charge is their work.** By day, fit and with no need that presses,
  they are at it ahead of their own post: they carry to it and work on it until it stands, and
  are paid for it as for a post. Their post waits. Whoever only lends a hand still does it in
  spare time, and goes back to their shift when it begins
- **With nothing to build with they sit by the site and ask** (`material_wanted`, once a day),
  for as long as there is something about that could be taken apart for it
- **What lies about can be taken apart**: a rusted car, a heap of tyres, a pile of junk. What
  each gives and how long it takes is data (`salvage`, in `data/interactables.json`). The
  player tells a resident which (`SalvageCommand`): it is an order, and their task until it is
  done. The thing is gone, and what came of it goes to the site they see to, if it waits for
  it, and otherwise to where such things are kept
- **With nothing left to take apart they go out for it themselves**: a short trip, once a day
  and not into a storm, that brings back that one thing and nothing else
- **The player breaks up an item for scrap** (`ScrapItemCommand`): what is nobody's and kept
  in a container, there and then; what is somebody's is put to them, who agree the readier
  the less it is worth to them, and remember having given it. What an item comes to is data
  (`scrap`, among its `properties`)
- What somebody has been told to take apart, and the one thing a trip is for, are saved

Done when: somebody with a post and a site in their charge builds in place of their shift, and
it stands before the shift is out; a builder with no scrap sits by the site until told what to
take apart, takes it apart, and builds; with nothing left to take apart they go out, come back
with scrap and build; a settlement with no scrap at all still gets a house built; and something
half taken apart is saved and goes on from where it was.

As it was built, where the lines above leave it open:
- **A task counts for 0.7**, over a post's 0.6 and under a need that really presses. Nothing is
  built or taken apart in the dark
- **Told to somebody else, a thing is theirs to take apart**, and what was done on it is kept
- **A wreck gives eight of scrap in three hours**, tyres three in one, junk two in forty minutes
- **A trip for scrap takes an hour and a half to two and a half**, brings three to six, and is
  a twentieth as likely to go badly as a real one. They leave from where they stand
- **Of the items the game comes with**, a radio gives two of scrap and a baton, a knife and a
  hoe one each. Nothing else gives any
- **Whoever is told to take something apart is not asked**: it is one of the orders the player
  gives (S37). Being asked for a thing of their own is not one
- Save version 32

Still open here:
- On screen only what a resident is doing is said: telling them what to take apart, and
  breaking up an item, come with P30
- Whoever has a site in their charge leaves their post to nobody: a cook who builds does not cook
- Things the settlement built and pulls down still give nothing back
- Nobody takes anything apart unasked, however long a site waits
- A site that asks for a job is still worked on only by whoever holds it

### S37 — Affecting a resident (needs S4 and S36) — done
The user's idea: "cuando seleccionas a un personaje deberíamos incluir una opción de afectar,
ahí se queda pensando... y nos da opciones para interactuar con él: así podemos afectar en todo
momento a los pj". Asked first, and answered: what can be said is seeing to a need, going to
somebody, getting on with something and a few words, and besides, in the user's words, "si
tiene mucho odio a alguien o a algo incitarle, si tiene afecto también"; what is said is an
order; and an order costs nothing.

- **The one place where the player's word is an order.** Everywhere else residents decide and
  the player advises. Here the player stops a resident, who leaves off what they were doing
  and stands listening, and tells them what to do. They do it, as far as it can be done
- **What can be said is data** (`data/affect.json`), in five groups: a need to see to (eat,
  drink, lie down, take a rest, be mended), somebody to go to and what for (talk, talk things
  over, face them, tell them what they feel, ask them to marry, leave them), something to get
  on with (their post, a site to take charge of, something to take apart, a post to take or
  to leave, a treat, dropping what they are at), and a few words that calm, cheer or scold
- **A resident can be set on to act on what they feel strongly**: to go for somebody they
  resent or have it out with them, to make a move on somebody they are drawn to or slip away
  with them, to seek out somebody they are fond of. Only what they feel that strongly is on offer
- **What is on offer follows from how things stand**: nobody is sent to a post out of hours,
  to a site there is not, or to somebody who is away
- **An order costs nothing.** Nobody thinks the more or the less of the player for it

Done when: a resident who is stopped leaves off what they were doing and stands there until
told something or let go; told to eat, sleep, go to somebody or take something apart, they do,
whatever they are like; set on somebody they hate, it comes to blows with nobody asked; what
they do not feel strongly they cannot be set on to; and the same orders on the same seed come
out the same.

As it was built, where the lines above leave it open:
- **Stopped, a resident listens for half an hour** and then goes about their day. Whoever they
  were talking to is left free. Somebody asleep can be woken for it. Somebody away, thrown
  out or with a decision of their own open cannot be told anything: that decision comes first
- **Strongly is fifty or more** of resentment, attraction or affection
- **Going to somebody is setting out to have that exchange with them**, as when a resident
  makes up their own mind to: the other may be busy, and what is asked of them is still
  theirs to answer. A fight that is ordered starts with no decision opened for anybody
- **A post or a site put in their hands is theirs at once**: they are not asked, as they are
  when it is proposed to them (S6, S16)
- **Of what is felt for a thing**, only a treat is there: going to eat what they like best, if
  there is any. Nothing is done about a thing they loathe
- **A few words** take fifteen from their nerves, or add ten to their spirits, or the other way
  about, and stop them no longer
- Nothing new is saved: somebody stopped is doing that, as anything else they do

Still open here:
- The user chose orders over advice and no cost over a cost, which is not how the rest of the
  game goes (S4, S27). If it turns out to make advising pointless, what an order costs is one
  number away: what the player is to a resident is already there (S27)
- Dragging a resident and dropping them on something (P27) is the same order given another
  way. It is built
- A resident cannot be told to do anything about a thing they loathe, to give somebody
  something, or to work out of hours

### P30 — Affecting, and breaking things up, on screen (needs S36 and S37) — done
The list that opened over the map is gone: P57 put a wheel about the resident in its place.
- **A way to affect whoever is selected**, in their panel beside their face. It stops them,
  and what they are about reads `se queda pensando...`
- **What can be said opens over the map**, a step at a time: the kind of thing, the thing, and
  who or what it is about, with a way back at each. What is chosen is said at once and the
  panel shuts. While the player is choosing, they go on standing there. Left for somebody
  else, or the panel shut, they go about their day
- **A builder who sits waiting for material is pointed out** in the line under the clock, and
  affected goes straight to what there is to take apart, the nearest first with how far it is
- **An item is broken up from the panel of the container it is in**: a mark at the end of its
  row, for whatever gives scrap. What is somebody's is put to them, and the answer is said.
  Nothing on a shop's counter has the mark
- What a resident is doing is said for what it is: waiting for material, taking something
  apart, standing stopped

Still open here:
- What somebody carries is not broken up from their panel, only what is kept in a container
- Nothing on the map shows which rusted car or heap of junk a line of the panel is, beyond how
  far it is
- The panel has no keys: it is all clicks

### P31 — Sound (no dependency) — done
The user's words: "tenemos que añadir efectos de sonido: el juego se siente pobre en cuanto
sonido y efectos". Asked first, and answered: synthesised, with room for the user's own.

- **Sixty effects where there were eleven**, still written by the art tool and still made of
  nothing recorded: notes that can slide and be louder or softer, rough sound of three colours
  for blows, scrapes and hiss, and a second voice under the ones that want body
- **Nearly everything that happens has a sound**: 145 kinds of event, where 50 had one. A
  death is not an injury, a law passed is not a law broken, and a vote, a wedding, a birth, a
  knock at the gate, somebody thrown out and an order given each have their own
- **What is being done in view is heard for as long as it is**: hammering on a site, metal
  taken apart, loads carried, something mended, blows. Each comes again every so often, and
  more quietly than what happens
- **The player's own hand sounds**: a click, somebody selected, the panel for affecting
  opening, an order given, something refused
- **A place for ambience under it all**, and none that comes with the game: wind by day, the
  night, a storm that drowns both, a fire or a generator while it is in view, and a murmur
  while people in view talk. Each is heard only from a file put in `sounds/ambience/`, comes
  up and dies away, and is silenced with the rest
- **Room for the user's own**: a file in `sounds/` with the name of one of the game's is played
  in its place, `.wav` or `.ogg`. `sounds/README.md` names every one and says when it is heard
- What sounds and when, and how loud each kind is, is data (`data/audio.json`)

Done when: every effect the data asks for is a file there is; a sound of the player's own is
played in place of the game's, and one that cannot be read breaks nothing; what would be heard
of the air follows the hour, the weather and what is in view; hammering is heard while somebody
in view builds and stops when they do; and the folder for the player's own sounds says what
each is called.

Taken out since: the game came with six synthesised loops of ambience, and with snoring for
as long as anybody in view slept. Once listened to, there was "un zumbido constante super
desagradable", and all of it went the way the synthesised music had (P8). The lesson is the
same twice over: nothing synthesised here that goes on and on.

Still open here:
- **The effects were written and checked by their numbers**, not by ear: no file is silent
  and none breaks up. Whether each sounds like what it is meant to is for an ear to say, and
  one that grates is silenced by taking its line out of `data/audio.json`, or replaced by a
  file in `sounds/`
- There is no ambience until somebody makes some
- What happens out of view sounds as loud as what happens in it
- The editors, Urbanismo and the menu are still silent
- Steps, doors and the day's small noises have no sound
- Music is still waiting for music worth playing (P8)

### P32 — How far along (needs S36) — done
The user's words: "pon una barra de tiempo encima de los pj cuando están en una tarea".

- **A small bar over the head of whoever is at a task**, under their name, that fills as they
  get on with it. From afar it is smaller
- **A site and something being taken apart say how far along they are themselves**: the bar
  over whoever works on them is the site's own, or the thing's
- **A shift at a post is as far along as the hours of it that have gone by**, so that leaving
  the post on an errand and coming back does not start it again, and a longer day by law is a
  longer bar
- **The use of a thing is as far along as the time it takes**: a meal, a drink, something mended
- **Nobody at no task has one**: on their way somewhere, strolling, talking, asleep, stopped to
  be told something, or sitting waiting for material

Decided without asking: a task is a shift, a site, taking something apart or using a thing.
Sleeping and talking are not, so that the night is not a row of bars.

Still open here:
- The bar is one colour whatever the task, and says nothing of how long is left in hours
- Whoever is out of the settlement has none, nor does anybody in the roster on the right

### P33 — Nothing kept open under the map (no dependency) — done
The user's words: "la parte de abajo donde se ve el historial, lo vamos a quitar, cuando demos a
eventos se abre, no lo quiero todo el rato abierto".

- **The map goes down to the foot of the screen**, and so does the menu. The strip that listed
  the latest events under it all the time is gone
- **What has been going on is read from `Eventos`**, in the panel that already opened from
  there, now wide and tall enough for whole lines
- **The dock is still where people talk**, but only while they do: it opens over the foot of
  the map when whoever is selected is in an exchange, or when somebody asks for advice, and
  goes when they are done. The minimap moves up out of its way, and a panel of the menu stops
  short of it

Decided without asking: the history opens in the corner panel `Eventos` already had, not in
the strip at the foot, which is left to conversations.

Still open here:
- The dock coming and going as a selected resident starts and ends a chat moves the minimap
  each time
- The lower entries of the menu are under the dock while it is open. The names are no longer
  cut by the row under them: P35

### S38 — The player says how they are governed (needs S26) — done
The user's words: "en el menu lateral izquierdo, añadiremos el apartado gobierno, ahi se puede
elegir". Asked first, and answered: choosing is the player's, whenever they like, and it is done,
not put to anybody. It starts with the legitimacy of how many wanted it, and changing it in the
middle of a game costs stability. This is the second place where the player's word is an order
and not advice, after affecting a resident (S37), and it sets aside what S26 began with, that
the player never governs: who leads, what is decided and what is voted are still the residents'.

- **`ChooseGovernmentCommand`** gives the settlement a kind of government: while it is choosing
  one, in place of what the residents would have settled on, or in place of the kind it has
- **Nobody is asked, and what each would have had still counts**: every adult who is there has a
  kind they would have, by what they hold (S26). How many of them it is, is how legitimate the
  government starts; whoever wanted it trusts it the more, and whoever wanted another, the less
- **A change in the middle of a game is the change there already was** (S27): whoever held a
  seat holds it no longer, the seats of the new kind are filled by its own ways, stability
  drops, and corruption and unrest are carried over
- **It cannot be done before there is anything to govern**: a settlement of fewer than three is
  not choosing, and is refused. Nor is the kind it already has given to it again
- **The residents can still undo it**: what they propose and vote (S27), and what comes of
  unrest (S29), change the kind as before
- The one proposal of S26 (`ProposeGovernmentCommand`) is still there, as a command
- `government_chosen` and `government_changed` say in `data` whether it was `imposed`
- Nothing new is saved

Decided without asking:
- There is no wait between one change and the next. Each costs stability, which is what holds
  it back
- A kind chosen while the residents are still talking it over ends the talking: they do not
  choose over it twelve hours later
- What the player proposed earlier, if they did, still weighs in what each would have had

Still open here:
- Nobody remembers that it was put on them rather than chosen: it tells on trust and
  legitimacy, and on nothing they say or hold against the player (S27's trust in the player)
- A kind nobody wanted starts at the floor of legitimacy and nothing else comes of it until
  unrest does (S29)

### P34 — How they are governed, on screen (needs S38) — done
Asked first, and answered: the seven measures are shown as bars in colour, with no figure.

- **`Gobierno` in the menu, or `P`**, opens a panel over the corner of the map, as the others do
- **How things stand**: the kind and the day it began, whoever leads by the name of their role,
  who sits on the council and how many seats stand empty, a vote that has been called and in
  how many hours; or that they are too few, or that they are talking it over and for how long
- **Seven bars**, one for each measure of the settlement, each in a colour of its own. What a
  resident holds is still not read off any panel
- **The laws in force**, by name
- **Every kind there is**, with a line on how it works made from its data: who decides, how
  the next to lead comes to it, how votes are taken and how long a term is. `Elegir` beside
  each, and `En vigor` beside the one they have
- **Choosing takes two presses**: the first says which and the button reads `Confirmar`; the
  second means it. Pressing for another, or shutting the panel, forgets the first

Decided without asking: the two presses, since one click would change a government; and `P`
for the key, `G` being taken.

Still open here, which is the rest of P26:
- Proposals, votes, elections, laws to propose, and whoever breaks one are still commands
- Who holds which role is not seen on the map or in their panel

### P35 — An interface drawn fine (no dependency) — done
The user's words: "dale una mejora visual a las interfaces son suuuuuuper cutres, dale un poco
mas de alegria no 3 x 3 pixeles cuadrados cutres". Asked first, and answered: drawn by code at
the resolution of the window, each icon one a picture of the user's can take the place of; and
the letters are changed afterwards, as a milestone of their own (P36).

- **Panels, buttons, bars and icons are drawn at the resolution of the window**, smooth and in
  colour, under the canvas, where the canvas is left clear for them (P13). `graphics/ui_art.py`
  draws them and `graphics/ui_skin.py` puts them there
- **Nothing that draws a panel had to change**: `draw_panel`, a button and a bar are offered to
  the skin first, and are flat as before where there is no window under the canvas, on any
  surface that is not the canvas, and where they are too small for a frame
- **The bar, the menu, the panel and the dock are plates** with a line of brass round them and
  rivets in their corners. A picture at `illustrations/ui/panel.png` still takes their place
- **What the menu opens has a band of its entry's colour** over its title, and a soft shadow
- **Every entry of the menu has an icon of its own on a tile of its own colour**, 36 pixels of
  the window where there were 8 doubled. Three pairs of entries no longer share one. The entry
  that is open stands on a lit plate, and so does the one under the pointer
- **The rows of the menu are spaced** so that no word is cut by the row under it, and the
  entries of the game (save, urbanism, the editors) stand a little apart from the settlement's
- **The icons of the bar on top** are drawn the same way, at 22 pixels
- **Buttons are raised and light up under the pointer**; the one that is on is lit
- **A picture at `illustrations/ui/icons/<name>.png` takes the place of an icon**, at any size

Decided without asking:
- The colours: dark blue plates with brass, and a hue for each entry of the menu
- Signs over buildings and the small frames are dressed too, down to 20 by 12 on the canvas
- The game's 8 by 8 icons stay for what is drawn over residents, and for a game with no
  window under its canvas

Still open here:
- The letters are still the pixel font doubled: P36
- What is over a resident on the map (bubbles, marks, the bar of a task) is still pixel art
- The editors and Urbanismo get the new panels and buttons, and their own tools, swatches and
  catalogue are as they were
- Under the dock, the lower entries of the menu are still covered while it is open

### S39 — A caravan stays the day (needs S23) — done
The user's words: "La caravana debe verse y estar todo el dia, debe ser un caravanero al lado de
la puerta". Asked first, and answered: it comes as often as it did, and when it does it is there
the whole day; whoever comes is always the same, somebody with a name.

- **A caravan comes in the morning and packs up as night falls**: between eight and ten, until
  nine at night, where it used to stop for four to six hours at any time of day. It still comes
  one day in several, and a radio still gives word of it five hours before
- **`leaves_hour`**, in a merchant's data, is the hour of the day they go at. One that names
  none stops for `minutes`, as before
- **Whoever comes is somebody**: `keeper`, in the data, with an ID of their own and a name. The
  caravan the game comes with is Zacarías's. They are no resident: nobody feels anything for
  them, and they hold nothing against anybody
- **They have a place**: beside the way in rather than in front of it, in the open, on nothing
  that stands there, with their cart at their side. It goes by the map, not by chance. With no
  room for the cart, or no cart in their data, they stand alone
- **The cart is a kind of object** (`cart`, in the data: `caravan_cart`), two tiles wide. It is
  not placed in the settlement: it is theirs, and goes when they do
- **Nobody plans to stop where they or their cart are**, and whoever goes to deal with them
  stands next to them, not on the way in
- Where they stand is saved. Save version 33

Decided without asking:
- The hours: in between eight and ten, out at nine at night
- They and their cart are not in anybody's way: people walk past them, and through them if the
  way is narrow, as nothing but residents are in each other's way yet (S22)
- The name. It is data: `data/world_events.json`

Still open here:
- Nobody has anything to do with them but buying and selling: no talk, no liking or disliking,
  and they are neither robbed nor hurt in a raid
- How much water is left after six weeks goes by the seed far more than by anything else: of
  220, from 36 to 219 with the caravan's hours as they were, and from 56 to 221 as they are, in
  the same four seeds. The test of it now runs on one where it is kept up, having been on one
  where it was by luck. Whether a settlement can keep itself in water is not settled (S15)
- A caravan that is there all day is visited by more residents than one of a few hours was.
  What that does to pockets over weeks has not been measured

### P37 — The caravaneer at the gate, and dealing with him (needs S39) — done
Asked first, and answered: a click on him opens the deal; he is a figure of the game's that the
player can draw over, and so is his cart.

- **Whoever has come to trade is seen where they stand**, with their name over their head, as a
  resident is: the game's own figure, or their paper doll once somebody has drawn it. From afar
  they are a face. Their cart stands beside them
- **A click on them opens the deal**, over the corner of the map, and selects nobody
- **What they bring and what the settlement has that is nobody's**, side by side: each thing
  with how many there are and what one goes for, and `-` and `+` to put it in the deal. Only
  what they would give something for is listed
- **How the deal comes out is said before it is closed**: what the fund pays or takes, or under
  barter what is given against what is asked, and in red when it cannot be done
- **`Cerrar trato`** does it in one go (`DealWithMerchantCommand`, S23), and says what came of
  it or why not. What was chosen is kept when it could not be done
- **`Dibujarle` and `Dibujar carro`**, where there is somewhere to keep drawings: the doll
  editor on the caravaneer, as on a resident, and the object editor on his cart
- When they go, the panel goes with them
- The cart can also be put in the settlement as scenery, from `Decorado` in Urbanismo

Decided without asking:
- One unit at a time. There is no way yet to take ten or all of a thing in one press
- Nothing says on the bar that a caravan is there: the news of its coming does, and the name
  over his head

What was still open here was built with P25: putting it to a resident that they sell a thing of
their own, what waits at the gate to be carried in, and where he is on the minimap.

### P38 — A catalogue of pictures (needs P35) — done
The user's words: "en urbanismo el menu es bastante poco familiar, es mejor que en el menu se
vea un grid con los dibujos si pasas por encima se ve el nombre y en bloqueados los no
aprendidos". Asked first, and answered: what nobody knows how to make yet stays in its own tab,
last and dimmed, under a heading; and resting the pointer on a picture gives its name and,
under it, what it takes.

- **The catalogue of Urbanismo is a grid of pictures**, five to a row, where it was a list of
  names. Every tab fits without the wheel, which still rolls one that does not
- **Each tile shows the thing itself**, fitted to it whatever its shape: a drawing of the
  player's where there is one, at the resolution of the window, and the game's own art where
  there is not. A building is shown with its roof on
- **Resting the pointer on one names it** in a box beside the pointer, with a line under the
  name: what it costs and how long it takes to put up, or that it is simply put down
- **What nobody knows how to make yet comes last**, under `Bloqueados`, dimmed and with a
  padlock. The line under its name says what has to be found out first, and a click on it
  still says so and hands nothing over
- The tile of what is in hand is framed in `lamp`, and the one under the pointer in `bone`

Decided without asking: five to a row, so that the twenty-two kinds of furniture are all in
sight at once, over fewer and larger.

Still open here:
- The three kinds of building look much alike in the catalogue: they are the game's own
  starter picture at three widths. A building's four drawings belong to one that stands, not
  to its kind
- Whoever a thing waiting to be built is put to is still a list of names

### P39 — A look inside, as a try (needs P15) — done, to be looked at
The user's words: "las casas molaria que en vez de ver el tejado y que se abra poder entrar en el
interior, y poder decorarla mas detalladamente, y las casas que puedan tener propiedades, el
interior no se si lo haria vista frontal con un toque cenital 2d ligero cenital probamos? pero
cuadricula en el suelo".

Asked first, and answered, for all of what follows (P39, S40 to S42 and P40):
- **The inside is a place of its own, larger than the building is from outside**, and the door
  is the way between the two. Not the recommendation, which was the same tiles seen from inside
- **A house has every property that was offered**: owners, and who lives in it; qualities that
  come of how it is furnished; a lock, and who may come in; and a name and a use of its own
- **Decorating in more detail is every way that was offered**: things on the wall, more kinds of
  furniture and ornament, a finer grid inside, and a floor and walls to choose
- **The view first, and then stop for it to be seen**

This one is only the view, to see whether the angle is right before anything is built on it:
- **A click on the sign of a building goes into it**, and so does `I` with the pointer on it or
  with somebody selected who is in it. The sign lights up under the pointer and says so, and
  resting on it does not take the roof off, so that it stays where it is to be clicked
- **The room takes the place of the map**, with everything round it as it was: time goes on,
  and the menu, the bar and the panel work as they do
- **The back wall is seen face on and the floor from a little above**: a cell of the floor is
  about six tenths as deep as it is wide. Every cell has a line round it
- **What stands up is as tall as it is drawn, and what lies flat is seen as the floor is**
- **Whoever is in the building is seen in the room**, as their doll or the game's own body, to
  be selected with a click. Whoever lies in a bed is seen as on the map: their own head on the
  pillow, a doll's as it was drawn, and the rest of them under the blanket. The first try had
  the small face that marks them from afar, blown up, and the user's word for it was that the
  people looked bad
- **`Salir`, or `I`, goes back out** to the map as it was left
- **`scenes/interior_view.py`** lays the room out and draws it, at the resolution of the window

What it is not yet, and says so on the screen:
- The inside is what the building holds on the map, spread over a floor twice as wide and twice
  as deep. It is no place of its own yet: where somebody is in there goes by where the map has
  them, so they cross the room twice as fast as they walk
- Nothing can be put down, moved or drawn in there
- The roof still comes off under the pointer out on the map
- The furniture is the art there was, which is drawn from above, and looks flat on the floor.
  What is drawn from the side is right already. **The bed is drawn for this view**, as a try
  the user asked for ("prueba hacer la cama con la nueva perspectiva y te digo si me gusta"):
  its headboard face on against the back wall, the top of its mattress from a little above,
  and the board at its foot in front, in thick dark lines and flat colour as the dolls are
  (`graphics/interior_art.py`). Whoever sleeps in it lies between the mattress and the
  blanket. It is the game's own picture and takes the place, in there, of whatever the player
  drew of a bed for the map
- The back wall is bare, and the room is as bright by night as by day

Decided without asking:
- The sign of a building as the way in, and `I` as the key
- Twice the size each way, which is also what a finer grid of four cells to a tile would give
- Every building with a roof can be gone into, not only the houses

### S40 — A place of its own inside (needs P39) — under way
The view of P39 was seen and liked ("me gusta"), and so was the art (P41). Then: "pasamos a la
decoracion y propiedad". Asked first, in two batches, and answered, for S40 to S42 and P40:

- **How much larger the inside is goes by the kind of building**, in its data. Not the
  recommendation, which was twice each way for all of them
- **What is inside is placed and moved from inside**, in a mode of the view for it. Urbanismo is
  for what is out of doors
- **Furniture is built and ornaments are not**: a bed, a table or a shelf is put to a resident
  and made of scrap, as it is outside; a picture, a rug, a plant or a curtain, and the floor and
  the walls, are put there at once and for nothing
- **From the map a building is always shut**, with the faces of whoever is in it, and, in the
  user's words, "se ve si estan hablando comiendo durmiendo etc mediante a los iconos que le
  salen arriba": over each face, what they are doing
- **The player says whose a house is**, from inside it
- **Whoever has no house sleeps in the open.** Not the recommendation, which was a bed in a
  house that is everybody's
- **A lock and visits, all four that were offered**: only those who live there and whoever they
  would have in go into a house that is somebody's; going in unasked is ill seen; a door can be
  locked, with a lock that is built; and what is kept inside is theirs
- **Any building can be somebody's**, and in the user's words one that is nobody's is "del
  estado, pueblo o lo que sea": the settlement's

What follows from those, said to the user before it was built:
- In the ready-made settlement, and in a save from before, everybody starts as one of the owners
  of the house they were sleeping in, so that nobody is put out by the rule
- While a new settlement is in its opening nothing is anybody's, and when it ends whoever
  founded it has the shack they made

This one:
- **Every building with a roof has an inside that is a place of its own**, larger than the
  ground it stands on by what its kind says, with its own floor and its own grid
- **The door is the way between the two**: whoever goes through it out on the map is inside, and
  whoever goes through it inside is out on the map
- **Residents find their way across both**: to a bed, a pot or a post that is inside from
  anywhere outside, and back
- **What is inside is inside**: what was in a building on the map moves to its inside, and the
  ground it stood on is the building, shut
- **Nobody outside sees what happens inside, or the other way round**: what is known of it is
  what was seen there, or told (S3)
- Who is where, and what is where, is saved. A save from before has every building's things and
  people moved inside it

### S41 — Whose house it is, and what it is like — done
Built before S40, and said so to the user: the inside as a place of its own is a deep change
(the map, the ways across it and every save), and whose a house is does not wait on it.

- **Owners** (`simulation/housing/housing.py`, `GiveHouseCommand`): any building with a roof is
  given to one or more residents by the player. One with no owners is the settlement's. Whoever
  has died or gone owns nothing
- **Who lives in a house** is whoever it belongs to, whoever is with one of them, and their
  children. A grown brother or sister does not for being one
- **A bed under a roof is for whoever lives in that building**, and so nobody's in a building
  that is the settlement's. Whoever has no house sleeps in the open (S25), as the user asked
- **Only those who live there and whoever they would have in go in** for what is there: whoever
  one of the owners thinks well enough of, which is theirs to think and not the visitor's.
  Whoever works at a thing gets to it all the same. Anybody goes into what is the settlement's
- **Hunger or thirst bad enough drives somebody in unasked**, for what would see to it, and
  **that is seen**: `trespass`, which whoever lives there holds against them and which is
  talked of (S5, S9)
- **A door is locked from the board of the building** (`LockHouseCommand`). Locked, nobody but
  whoever lives there goes in, however well they are thought of and however hungry
- **What is kept inside is for them**: a pantry, a pot or anything else in a house is used by
  whoever lives there and whoever they would have in, and by nobody else without trespassing
- **Qualities that come of how it is furnished**: comfort, warmth, light and how good it is to
  look at, each from 0 to 100, from what stands in it. A second of the same thing adds half of
  what the first did. Whoever lives there rests the better in their own bed for its comfort,
  and once a day has their mood lifted by how good it is to look at (S20)
- **A name and a use of its own** (`NameBuildingCommand`), which is what its sign says
- **All of it data** (`data/housing.json`): how well somebody has to be thought of, how bad a
  need has to be, what each kind of thing adds to each quality, and the uses there are
- **Saved** (version 34). In a save from before, and in the ready-made settlement, everybody
  has the house they were sleeping in. In a new settlement nothing is anybody's while its
  opening lasts, and houses are given out for the first time when it ends
- **From inside** (`ui/house_board.py`): a board down the right of the room with its name and
  use, its beds and who lives there, the four qualities as bars, the door, and everybody in the
  settlement to press: lit, the building is theirs. Whoever has no house is marked. `Casa`
  opens and shuts it

Decided without asking:
- **The lock is a switch of the house and not a thing that is built.** What was answered was
  "se puede cerrar con llave"; a lock taking a tile of floor in a shack of six was worse than
  what it bought. It costs nothing
- **Brothers and sisters do not live in one another's houses** for being kin; partners and
  children do
- **Whoever comes to the settlement later has no house** until the player gives them one: it
  was "la asigno yo". The player is told when they come in, and they are marked on the board
- **A bed in a building that is the settlement's is nobody's**, the clinic's sick beds apart,
  which are no beds to sleep the night in
- **A house changes who may go in for a thing, not whose the thing is.** What is the
  settlement's stays on its books wherever it is kept, is counted in `Almacén`, is traded and
  is fetched by whoever works with it. It was first built the other way, with what was in a
  house off the settlement's books, and taken back: when the opening of a new settlement ends
  the founder's shack is theirs and its crate is the only store there is, so the settlement
  was left with nothing to its name and nowhere to put what a trip brought back
- The thefts of S9 go on as they were
- **Sleeping in the open rests somebody better than it did** (`sleeping_rough` in
  `data/family.json`: 0.17 a minute, from 0.12; a bed is 0.21). It was made for the odd night
  with no bed free, and is now where whoever has no house sleeps every night. Measured over
  eighteen seeds of ten weeks with nobody giving houses out: as it was, whoever had no house
  slept six hours in ten and worked half of what the rest did, and four settlements starved
  where one did before; as it is now, one does, as before

Left for later:
- Keys given to somebody who does not live there
- A household's own stock: whoever lives in a house putting by in it what is theirs, off the
  settlement's books

### S42 — More to furnish with — done
Built before S40, like S41: where an ornament is goes by the building and not by the map, so
that it stays where it was put when the inside becomes a place of its own.

- **Ornaments** (`simulation/housing/decor.py`, `data/decor.json`): things put in a building only
  to be looked at. Nobody uses one and nobody walks into one. They go where the player says at
  once and for nothing (`DecorateCommand`), and come away the same (`UndecorateCommand`)
- **On the floor**: a rug and a mat, which lie flat and go under anything, furniture included; a
  plant, a chair, a bedside table and a standing lamp, which take a cell that no furniture and
  no other of them has
- **On the back wall**: a picture, a window, a curtain, a shelf, a lamp and a clock, each taking
  a stretch of it. The wall is its own place: what hangs is in the way of nothing on the floor
- **The grid inside is the finer one**: four cells of the inside to a tile of the building, as
  the view of P39 already drew it. Furniture stands on whole tiles and an ornament on any cell
- **A floor and walls to choose** (`SurfaceCommand`): boards, concrete, tiles or trodden earth
  underfoot; boards, plaster, brick or sheet metal round it. Nothing said puts it back as it was
  put up
- **All of it tells on what the building is like** (S41): each kind, and each floor and wall,
  adds to its comfort, warmth, light and beauty what `furnishing` in `data/housing.json` says
- **Saved** with whose the building is (version 34). An ornament of a kind that is no longer
  there, as when a pack is taken out, is kept and not shown

Decided without asking:
- **Ornaments cost nothing and need nobody**, floor and walls included: it was "muebles se
  construyen, adornos no"
- **A chair is an ornament**: nobody sits on it. The stool is still the thing to sit on
- **Nothing stops somebody walking where an ornament stands.** They are drawn in front of it or
  behind it by how far down the floor they are

Left for later:
- Moving an ornament without taking it away and putting it down again
- How far up the wall a thing hangs: each kind has its own height

### P40 — Furnishing from inside — done
- **`Decorar`, inside a building** (`ui/decor_board.py`): the board down the right of the room
  becomes a catalogue of pictures in four tabs, with the name of whatever the pointer is on and
  what it adds
- **`Adorno`**: press one and it is in hand; it follows the pointer over the floor or the back
  wall, seen through, with a green line round it where it can go and a red one where it cannot.
  A press puts it down, and it stays in hand for the next. The other button puts it away
- **`Mueble`**: every kind of furniture the settlement knows how to make, with what it takes. A
  press on the floor puts it to somebody to make, as in Urbanismo: whoever is selected, or else
  whoever lives there, one after another until one of them will. What is being put up is seen
  through where it will stand, with how far along it is
- **`Suelo` and `Pared`**: a press changes it at once; the first tile puts it back as it was
- **`Quitar`**: a press on an ornament takes it away. Furniture is still taken away in Urbanismo
- **Each kind is drawn by the game** (`graphics/ornament_pictures.py`), in the hand of P41, and
  so are the floors and the walls (`draw_shell`)
- Whose house it is, said from inside, what it is like, and its lock: built with S41
- From the map, over each face on a roof, what they are doing: built with S40's first step
- While a building is being dressed a press on the room picks nobody

Left for later:
- A way for the player to draw each kind of thing for the view from inside themselves
- Ornaments are not seen from the map, even with every roof off

### P41 — Everything in one hand (needs P39) — done
The user liked the bed drawn for the view from inside, and said: "cambia todos los items a este
estilo, y el esterior igual para que acompañe la perspectiva nueva".

Asked first, and answered: "items" is every kind of furniture and object, and the icons of what
is carried and kept as well; outside, all four things that were offered change: the objects on
the map, the buildings, the ground and the fence, and whoever has no doll; on the map a drawing
of the player's own still shows in place of the game's; and all of it in one go.

- **One hand for everything the game draws for itself** (`graphics/cartoon.py`): thick dark
  lines and flat colour, drawn by code at whatever size it is shown, as the bed was
- **Every kind of object, twenty-nine of them** (`graphics/object_pictures.py`): from its
  front and a little from above. One picture does for the map and for the inside of a
  building. What burns flickers
- **The buildings** (`graphics/building_pictures.py`): a roof of ridged metal, patched and
  rusting, over a front of boards with a door, an awning over it and windows; with the roof
  off, the floor, the back wall face on, the sides from above and the wall in front cut low.
  No two are quite alike: the colours and the dents go by which building it is
- **The ground of the whole map, and the fence round it** (`graphics/ground_pictures.py`):
  earth, grass in patches that run together, tilled soil in furrows, the fence in sheets of
  metal between posts, and the way in
- **Whoever nobody has drawn is a doll all the same** (`graphics/stand_ins.py`): the figure
  every doll starts from, stouter, in the colours their body wears, with a large head, hair, an
  eye and a mouth. They walk, sleep, fall and are carried as any doll
- **The items the game comes with, sixteen of them** (`graphics/item_pictures.py`): in a hand,
  on a shelf, over a head, and in every panel that lists them
- **Whatever stands nearer is drawn in front**: objects, buildings and people are put on the
  window in one order, by how far down the map their foot is. Somebody behind a shelf is
  behind it, which was not so before for anything drawn on the window (P13)
- **A drawing of the player's own shows on the map in place of the game's**: an object, a
  building, the ground, a resident, an item. Inside a building it is the game's picture of a
  thing that shows, since a drawing made for the map is seen from above. A building somebody
  has drawn a part of is left to them: what they left out stays out
- **The catalogue of Urbanismo** shows the new pictures too
- **With no window under the canvas** (a game with no folder for drawings, and every test of
  the simulation) everything is the pixel art it was

Decided without asking:
- On the map a thing is drawn as deep as it is inside: six tenths of a tile. It stands at the
  near edge of the ground it takes up, so a bed two tiles long leaves a little floor behind its
  headboard
- The ground keeps its square tiles. Only what stands on it is seen from the front
- A sleeper is put in the game's bed by where that picture says a head goes
- Items in panels are shown at the resolution of the window, the player's own included

Still open here:
- The faces in the panels, in the dock and on a roof are still the pixel faces, for whoever
  nobody has drawn
- What is over a head on the map (bubbles, marks, the bar of a task) and the minimap are
  still pixel art
- The fence is part of the ground: whoever stands behind it is drawn over it
- A kind of object a pack makes in another size than the game's keeps its pixel art
- Furniture and buildings as the game draws them have no editor of their own for the view from
  inside: a drawing of the player's is for the map
- A frame of the map takes about 8 ms to draw on the user's machine at every zoom, against
  about 3 with the canvas alone: within a sixtieth of a second, with little to spare on a
  machine half as fast. It has not been tried on one

### P42 — Limbs of rubber (needs P41) — done
The user said: "Vamos a intentar trabajar en como mejorar la experiencia visual de los pj skeleto
movimiento etc, evitar que las articulaciones parezcan unidas con chinchetas, movimiento mas
organico y natural".

Asked first, and answered, for all of what follows (P42 to P44):
- **How a joint bends: "Goma".** The whole limb curves, with no elbow or knee marked. Chosen
  over a skin that folds at the joint, which was what was recommended, and over parts with
  the join better hidden
- **What the movement is like: "Muy cartoon".** Squash and stretch, marked anticipation, wide
  bounces. Chosen over natural with some bounce, which was recommended, and over sober
- **Standing still: "Además, gestos sueltos".** They breathe and shift their weight, and now
  and then look about, scratch or stretch
- **Turning round: "Espejo al instante"**, as it is. Not narrowing to an edge and opening the
  other way, which was recommended
- **On a branch of its own**: "Crea una rama distinta, feature/SkeletonCartoon y aplicalo ahi".
  None of it is on `main` until it is asked for

Built:
- **An arm and a leg are each one piece that bends** (`graphics/hose.py`). The upper arm and
  the forearm, and the thigh and the shin, are kept together as they were drawn, and laid
  along their bones as one curve. The line down the middle rounds the joint off, and the
  drawing follows it: drawn out on the outside of the bend, gathered on the inside, its outline
  unbroken. Both ends are where the skeleton has them
- **Nothing is drawn again.** A limb drawn in one line, as all of them were, bends as it is
- **Which parts make a limb is data** (`doll.hoses` in `data/skeleton.json`), and so is how
  much of the limb a bend takes up and how much wider it gets for being shorter (`doll.hose`)
- Hands and feet are still parts of their own at the end of a limb, and the trunk, the hips
  and the neck are parts as they were
- A limb that has lost a part, as when a forearm is cut off, is shown in the parts it has
  left. So is every limb where numpy is not installed: the game runs without it
- **Bent limbs are kept**, each shape once and each way it is turned once, up to 56 MB of them
  for all the dolls together. Only about four milliseconds of bending are done in a frame: a
  limb that would go over that keeps, for that frame, the nearest shape it has had
- **The figure of whoever nobody has drawn was put right**, having been looked at closely for
  the first time:
  - It was drawn over the bare guide and then cut by the measures every doll starts from, so
    its trunk came out short, its legs hung loose under it and its hands were slivers. It is
    drawn by those measures now
  - The line goes round a whole limb, and not across it at the elbow and the knee
  - A hand ends round where it was cut off flat, and so does the bottom of the trunk
  - A shoe is whole and under the ankle. It was drawn half above it, where the foot is cut,
    and that half was lost. The guide shows the same shoe
  - Two specks beside the hips are gone: the top of each leg, which the zone of the hips
    reached. What two parts that do not meet both reach goes with the one further out

Decided without asking:
- numpy, which only the voices needed, is now in `requirements.txt`. It stays optional
- The curve is the kind that cuts the corner: bent double, a limb is a loop shorter than its
  bones, and its elbow is not where the skeleton has it. Only its ends are
- A limb is bent in steps of five degrees and drawn out in steps of four hundredths, and
  turned as a whole in finer steps, so that its far end is within a pixel of the hand or the
  foot that hangs from it

What it costs, on the user's machine, for twelve dolls all moving: about 1 ms a frame at the
size the map opens at and 2.4 ms at the nearest, against 0.8 and 1 in parts. In the first
second after they all take up something new at once, 4 to 8 ms a frame, and no frame over 12.

Still open here:
- The wrist and the ankle are still pins, and so are the shoulder and the hip, under the trunk
- Each part and each limb is put on a whole pixel by itself: where a hand hangs from an arm
  the two can be a pixel apart
- A drawing whose limb is not drawn in one line would have to be laid out again to bend
- The cost has not been measured in the game itself, with the map under it, nor on a slower
  machine

### P43 — Movement with weight and bounce (needs P42) — done
Answered with P42: "Muy cartoon".

- **Clips go from key to key in a curve**, as fast into each key as out of it, where they went
  in straight lines and turned a corner at every one. The game's own small bodies are posed by
  the same clips, and so move a little more smoothly too
- **A key can say when it comes** (`at`), so that a blow is held back and then let go all at
  once, and a clip can be one that is done once and does not come round (`once`)
- **Springs** (`skeleton/motion.py`): every bone of a doll is drawn towards where its clip has
  it, and gets there a little late and goes a little past. Legs keep up, so that a foot lands
  where it should; arms trail; a head nods on after the body has stopped. How loose each bone
  is, is data (`motion` in `data/skeleton.json`)
- **Going from one thing to another is not a jump.** The body swings into what it takes up,
  and is given a small drop and a bounce as it does (`motion.jolt`)
- **Feet stay on the ground** (`footing`). A clip moves the whole body; a foot it has on the
  ground stays where it stands, and the knee bends, or the leg is drawn out, to let the body
  sink, rise and lunge over it. So does the bounce of the springs: it is the body that
  bounces, on its legs
- **A trunk or a head squashed by its clip is wider, and thinner when drawn out**, as a limb of
  rubber already was (`doll.hose.volume`)
- **One body for every screen.** The map, the inside of a building, the editor and the pick of
  a manner all show a doll through the same lively body, where each posed it by itself. It
  is moved when it is looked at, by the time gone by since: one that is not in sight costs
  nothing, and one that comes back into sight is simply where its clips have it
- **Turning round is still at once**, as was asked: springs work on the body facing one way,
  and the mirror comes last
- **Written again from the side**: walking in eight keys (a foot lands, takes the weight, the
  other leg passes, the first pushes off), plain, shuffling and swaggering; working, with
  something raised, held and brought down; arguing; fighting, with a fist drawn back before
  it is thrown; eating, with the head coming down to the hand. The three walks are one walk
  with other measures. What the game reads from them is as it was: a foot lands at 0 and at
  a half, and the bite is at a half

Decided without asking:
- Springs run as fast as the game is going, so that they keep up with walking at four and
  sixteen times the speed
- The body in the editor is posed exactly while it is being measured, so that its joints are
  where they are taken hold of
- The clips with a weapon, and carrying, are as they were. They already moved the trunk and the
  head, and the springs do the rest
- From the front, which only the game's own small bodies are seen from, no clip was touched

What it costs, on the user's machine: posing twelve dolls on springs, 0.9 ms a frame. Drawing
them, 1.2 ms at the size the map opens at and about 4 at the nearest, with every one of them
taking up something new every three seconds. The game itself, with nine residents and seven in
sight, shows a frame in 9 to 10 ms without a window, at the first zoom and at the nearest.

Still open here:
- Feet slide: one turn of the walk takes a body two tiles, which is four times as far as its
  legs reach. It was so before, and the bounce makes it no worse
- A limp body, struck or knocked down, has no springs: physics has it, as before
- The clips with a weapon have no anticipation of their own yet
- It has not been seen on a real window by the user: all of it was checked on pictures made
  without one

### P44 — Life at rest (needs P43) — done
Answered with P42: "Además, gestos sueltos".

- **Everybody breathes**, over whatever else they are doing, each to a beat of their own: the
  chest swells and lifts, the shoulders with it
- **Standing with nothing to do, the weight goes over one foot and then the other**, hips first
- **Every four to eleven seconds, something small**, done once: a long look down and then up,
  a scratch at the back of the head, a crouch and a stretch on tiptoe with both arms up, a
  shrug. Only for whoever has nothing to do and nothing in hand: carrying, eating, armed or
  walking, nobody fidgets, and given something to do they leave off at once
- **When is left to chance, and the chance is each body's own** (`Life` in
  `skeleton/motion.py`), seeded by the stage and by who they are: never the simulation's, and
  none of it saved
- Which clips these are, and how often, is data (`life` in `data/skeleton.json`). `idle`
  stays one pose, since dolls are measured by it
- The doll in the editor breathes and fidgets too, where it stood still between its clips

**Made a good deal stronger, all of P42 to P44.** Shown the first version, the user said: "no
veo ningun cambio de movilidad en los movimientos ni nada de eso, ni en zoom ni en f2 seguro se
ha implementado?". It had been. The same seconds of the game were taken with the old code and
with the new, and the two could hardly be told apart: a bounce of one pixel of the skeleton is
two of the window where the map opens, the trunk was squashed by a twentieth, and the resident
followed walks dragging their feet. "Muy cartoon" had been answered, and it was not.
- Walking, the body drops and is thrown up at every step, the trunk squashed by a sixth and
  drawn out by as much, the arms swung twice as far. Dragging the feet is low and bent double,
  with the arms hanging in front
- A limb of rubber is one curve from end to end (`doll.hose.round` 2, from 1.4), and wider by
  more when it is short (`volume` 0.7, from 0.5)
- Springs are looser: the body bounces on its legs, and hands and heads are left well behind.
  The jolt of taking up something else is three times what it was
- Working, arguing, fighting and eating go further: up on tiptoe before the blow, a fist drawn
  out by a third
- At rest, breathing and the shift of weight are plain to see, and a fidget comes every four to
  eleven seconds, where it came every seven to nineteen
- The game's own small bodies lean as they walk now, since they go by the same clips, and that
  showed that facing left they were not quite the mirror of facing right: a part mirrored and
  then turned came out a pixel different from one turned and then mirrored. They are the very
  mirror now

Seen then, the user said "guay", and to bring it into `main`.

What it costs now, on the user's machine: the game with nine residents and seven in sight shows
a frame in about 10.6 ms without a window, from about 9 before any of P42 to P44.

Still open here:
- A fidget is the same for everybody: it does not go by mood, by trait or by what they are
- Nobody fidgets inside a bed, at a post or while talking
- The measures of the three walks were written by a script that is not kept: they are plain
  numbers in `data/skeleton.json` now, and changing a walk means changing eight keys

### P45 — Hands and feet that do not come apart (needs P44) — done
The user, with a picture of Olga holding a knife: "las manos y los pies se rompen bastante no se
si siguen el mismo metodo o no pero como ves en la imagen se rompen". They did not follow it:
the rubber went from the shoulder to the wrist and from the hip to the ankle, and a hand and a
foot were still parts pinned on the end. With the springs of P43 they turned by themselves,
and the straight cut each has at its joint showed: a block at the wrist, a step of trouser
over the shoe.

- **A hand and a foot are the end of their limb** (`doll.hoses` lists three parts to a limb
  now). The limb is cut out of the drawing in one piece, hand or foot and all
- **They keep their shape.** Laid along a curve as the rest of the limb is, a shoe came out of
  shape: its heel stayed behind and its sole twisted. That was tried and thrown out. A hand
  or a foot turns whole about the joint it hangs from, whichever way it was drawn pointing,
  as a foot sticks out of a leg
- **The joint gives.** Over a narrow band, most of it on the limb, everything turns a little
  further the nearer it is to the hand: the limb goes into it with no cut and nothing sticks
  out. How wide that band is, is data (`doll.hose.tip`)
- **What is drawn at a joint stays at it.** The round of a bend that takes more of one part
  than of the other was centred half-way along itself, and not on the joint: a leg, whose
  shin is longer than its thigh, had its knee a little off
- An arm with no hand drawn is still a limb, as far as it was drawn
- **A limb is kept as two pictures**: the part that bends, and the hand or foot with the band
  that gives. A hand turns all the time on its spring; kept as one picture the whole limb
  was bent again each time, and showing twelve dolls went from 1 ms to 7

What it costs now, on the user's machine: the game with nine residents and seven in sight
shows a frame in 9 to 10 ms without a window, as before. Twelve dolls on springs, every one
taking up something new every three seconds, are drawn in 2.6 ms at the size the map opens at
(1.2 before their hands and feet were theirs) and about 9 at the nearest, where there are more
pictures than are kept.

Still open here:
- The shoulder and the hip are still pins, under the trunk
- A limb cut off the body, a forearm with its hand, is shown in its parts as it falls
- At the nearest zoom with many dolls in sight, more turned pictures are wanted than are kept

### P46 — The paper laid out anew, a quiet guide and a plain figure (needs P45) — done
The user, with P45: "el esquema donde se dibujan los pj habria que darle un labado de cara
tambien para que se ajuste todo mejor y el diseño de ejemplo sea algo mejor". Asked before
designing:
- **The paper: laid out anew** ("Papel nuevo"). Parts may be moved and their zones resized,
  and what is already drawn has to be carried over. Keeping every part where it was had been
  recommended
- **The example: a neutral mannequin** ("Maniquí neutro"). A plain artist's figure with no
  clothes and no face, so as not to steer what is drawn. Whoever nobody has drawn is shown as
  one, in a colour. An ordinary person better drawn had been recommended
- **What fitted worst: the look of it all** ("Aspecto general"): colours, weight of lines,
  names, how well it reads

What was done:
- **The paper** is a unit wider, 400×384. Arms hang from the height of the trunk's shoulders
  and not from above them. A hand has twice the room past its fingertips, a foot more under
  its sole and ahead of its toe, arms are a little wider and the trunk a good deal. Legs are
  as far apart as they were: a foot can still be made twice as long before it reaches the other
- **What was drawn is carried over**, never edited: a drawing of the size the paper had is
  taken apart as it was cut then and laid out as today's each time it is read, and saved on
  the new paper only when it is next saved from the editor. The five dolls drawn on the paper
  of P20 are shown exactly as they were, pixel for pixel, standing, walking and fighting. The
  three from the paper before that one look the same, to within the edge of a part
- **More than one paper of before** (`doll.former` is a list, the latest first). Each is told
  by its size and says how it differed from the one after it, zones and all. Two of one size
  are refused
- **A piece taken to its new place keeps unseen the colours it had beside it.** A part made
  smaller or turned takes a little of what lies past its edge: with nothing there the edge
  went dark, and with what another piece had left there it took that colour
- **The guide is quiet.** A limb is one zone from where it is joined on to its fingers or its
  toes, as it moves since P45, and the trunk one with the hips and the neck; each is lightly
  tinted with one thin line round it. Dots where it bends and a small ring at each joint take
  the place of the red dashes and the dark dots. Names are in the colour of their piece,
  with no patch behind them, and the side of the body a leg is on moves out of the way of
  the trunk
- **One plain figure** (`graphics/mannequin.py`) in place of three: the clothed one under the
  guide, the strips the editor gave to start from, and the figure with hair and a face that
  whoever nobody had drawn was shown as. It is pale under the guide and of one colour, that
  of what they wear on their trunk, on the map. What each part of it is comes from the data
  (`shape`, which was `wears`)

Still open here:
- A drawing made on the first paper, the narrowest, has its near leg put down four tenths of
  a pixel off, as it has been since P20: that paper and the next were not a whole pixel apart
  there
- What had been painted outside every zone, which was never shown, is no longer on the paper
  once a drawing is laid out anew
- Nothing of this has been seen on a real window by whoever made it

### P47 — Work that looks like the work, with its tool in the hands (needs P45) — done
The user: "Vamos a meter animaciones nuevas, como la de trabajar, cuando se trabaja en el
huerto se coje la azada por el mango y se hace la animacion de levantar azada, clavar azada,
acurrucarse en el suelo tambien la hacemos, cuando cargan con algo pero no lo estan usando
que se lo guarden en el bolsillo; trabajar en la contrccion de algo lo mismo; diferentes
animaciones a elegir en maneras para sentarse". That is four things, P47 to P50, and a fifth
that came of the answers. Asked before designing all of them:
- **Tools: the hoe is the real one and the hammer is for show** (recommended). The hoe is an
  item already, which wears and makes the garden yield more: only whoever has one digs with
  it, and whoever has none works with their hands. There is no hammer in the game: whoever
  builds is seen with one that is nobody's
- **Curling up on the ground: when sleeping rough** (recommended), with lying down and
  getting up (P49)
- **The pocket**: "por ejemplo cuando cultivan van todos con la zanahoria en las manos,
  segun van cogiendo cosas que vaya a su inventario, no necesariamente se tiene que ver si
  no lo estan usando". What is carried and not being used is not in the hands (P48)
- **Sitting, each their own way: by the fire and at the radio, eating, drinking, and on a
  stool if there is one** (all four; only the first had been recommended). The first three are
  P50. Stools need the simulation to say who has which seat, and are left for a milestone of
  their own

What was done here:
- **Work is shown by what it is** (`data/poses.json`): by job, a clip for bare hands and
  another for whoever has the tool of the job on them, sound. Any job with no look of its
  own is the plain work of before
- **Digging with a hoe**: taken by the handle in both hands, dragged back, raised over the
  head, held an instant and brought down fast into the ground ahead, the knees giving
- **Working the ground with bare hands**, for whoever has no hoe or a broken one: down on
  the haunches, one hand at the ground and then the other
- **Hammering**, for whoever builds: one hand holds the work and the other comes down on it
  twice
- **A tool is held by its handle and turns with the hands.** A clip says how (`grip`): in
  both hands the handle runs from one palm through the other, in one it comes out of the fist
  at an angle. Where the handle is on a picture, and how long the thing is, is data
  (`handles`). The hoe in the hands is the item's own picture, the player's drawing of it if
  there is one. The hammer is a picture and no item
- **The small bodies of the game no longer sink.** Shown without a window they do not bend
  their legs, and a pose that takes the body down had their feet under the ground: plain
  work already did by a pixel. They are left standing on it
- The clips are written from where the hands are to be, and the arms worked out from that:
  two hands on one handle cannot be placed by turning four bones by eye

Still open here:
- A picture of the hoe drawn anew is turned by the handle the game's own has: the item
  editor does not show where to draw it, and nobody can say where theirs is
- A weapon and a meal are still shown flat in the hand, in front of it
- Whatever is held is drawn over every body, the one who holds it and anybody nearer
- The other posts (kitchen, bar, clinic, workshop, desk) are still plain work
- Taking a thing apart is not shown as work at all, as before
- Nothing of this has been seen on a real window by whoever made it

### P48 — What is carried is in the pockets (needs P47) — done
Asked with P47. The user: "por ejemplo cuando cultivan van todos con la zanahoria en las
manos, segun van cogiendo cosas que vaya a su inventario, no necesariamente se tiene que ver
si no lo estan usando".
- **Nothing is in the hands but what is being used**: a meal, a weapon in a fight, the tool
  of the work in hand. The goods somebody carries for their job were shown in their hands,
  with their arms held out for them all the way there: they are in their pockets, and are
  not seen
- **Whoever carries walks as anybody does**, and with nothing else to do may fidget as
  anybody does
- **A hand goes to the pocket** when something is taken up or handed over: a doll looks down
  and puts its near hand to its hip, once, over whatever else it is doing. It is a gesture,
  which is new: a clip gone through once over another, moving only the bones it names. The
  body it is laid over goes on walking, or working
- The small bodies the game shows without a window had the load as an icon beside them. It
  is gone too

Still open here:
- Nothing tells from afar who is carrying goods any more: it is on their card
- The same gesture does for taking out and for putting away, and for one thing as for six
- A tool is not seen taken out when work begins nor put away when it ends: it is in the
  hands, and then it is not
- The clip of arms held out for a load (`carry`) is left in the data, and nothing uses it

### P49 — Curled up on the ground to sleep (needs P48) — done
Asked with P47: whoever sleeps on the ground, for want of a bed, curls up on it, and is seen
to lie down and to get up. They were a blanket with a head out at one end.
- **Lying down**: a doll squats, puts its hands to the ground ahead, lets itself down and
  draws its knees up under it
- **Curled up**: knees under the body, shins along the ground, the trunk laid over the
  thighs and the head by the hands. It breathes there, as it does whatever it is at. There
  is no blanket: it is the whole of them that is seen
- **Getting up**: it pushes itself up, squats and stands
- **Only what is seen to begin is shown beginning.** Somebody the view comes upon asleep is
  found lying, and somebody who walks off the moment they wake is simply up: the walk is
  not kept waiting. How long anybody has been seen to lie, or to be up, is the stage's to
  keep, in real time and as fast as the game goes
- **What is picked, and where the sign of sleep goes, is as low as they lie**
- Inside a building it is the same
- **None of a doll is ever under the ground.** A body is laid down by turning every bone of
  it, by the build every doll starts from; one with longer limbs had its knees or its hands
  in the earth. Wherever a pose would have a joint under the ground, the whole body is that
  much higher
- Tried first and thrown out: the figure turned right over with its back up and its limbs
  under it, as one lying on their side is seen from above. On a map seen from the front it
  stood on its hands and knees with its feet in the air

Still open here:
- It is a crouch laid down and not a body on its side: a figure drawn from the side has no
  front to show
- Children under ten are still bundles, and whoever lies in a bed is still a head on a pillow
- The small bodies shown without a window still have their blanket
- Nothing of this has been seen on a real window by whoever made it

### P50 — Sitting down, each their own way (needs P49) — done
Asked with P47: where they sit, of four that could be marked, the user marked all four. By
the fire and at the radio, eating, and drinking are here. On a stool if there is one is a
milestone of its own (S44): where they go to sit is for the simulation to say.
- **Sitting is a manner** (`data/manners.json`), kept with the resident and chosen in
  `Maneras` like their walk: a sixth row, `Sentarse`, with four to pick from. With their legs
  crossed and their hands on their knees; with their knees drawn up to their chest; leaning
  back on their hands with their legs out; squatting on their heels. Whoever was given none
  has one of their own, as with the others
- **It shows while they are at something done sitting down.** A kind of manner may say what a
  resident has to be at for it to show (`actions`): resting by the fire, listening to the
  radio, eating, drinking at the bar. On the way there they walk, and at work or with
  somebody they are on their feet
- **Eating, they sit and eat.** The body sits their way of sitting and the arms and the head
  eat their way of eating, laid over it: twelve ways of having a meal out of four and three
- **They sit still.** A way of sitting is one pose, and what moves is their breath. Nobody
  fidgets out of it
- **Their name comes down with their head**, by as much as their head is lower, and so does
  what is picked. A meal held higher than the head of somebody sitting is not written over:
  the name goes above it
- No save changes hands: a manner of sitting is kept as the others are, and an older save
  loads with everybody sitting their own way

Still open here:
- They sit on the spot they stand on, facing whichever way they last walked: not the fire,
  nor each other. A stool under them is S44
- Whoever sits is seen to drop into it and to rise out of it by their springs alone: there is
  no sitting down as there is a lying down
- Drinking, they sit with their hands empty: there is no clip of drinking
- Seen from the front the small bodies shown without a window do not sit at all
- Nothing of this has been seen on a real window by whoever made it

### S44 — A seat of one's own (needs P50) — done
Asked with P47, and marked: whoever is at something done sitting down sits on a stool if
there is one free beside it, and on the ground if not.
- **A stool is a seat** (`"seat": true` in `data/interactables.json`): a kind of object says
  whether it is something to sit on. It was furniture that stood there
- **Whoever goes to rest, eat or drink takes a free seat beside what they use**, before the
  nearest bare ground. Round the fire of a settlement just begun there is a stool on every
  side, so nothing changes of where anybody goes there: it tells where the player has put
  a stool on one side of something and not on the others
- **A seat is whoever's stands on its tile.** Two cannot stand on one tile (S22), so two
  cannot have one seat, and there is nothing to keep in a save or to go wrong on loading
  one. It had been thought the activity would have to carry it
- **On a stool anybody sits the same way**: hips at the height of it, thighs out ahead, shins
  down to the ground, hands on their knees. Their own way of sitting is for the ground
- **They are drawn in front of the stool they are on**, which stands on the same tile and
  was drawn over the legs of whoever stood there
- What is done sitting down is said once, by the kind of manner of sitting (`actions`), for
  the simulation and for the map alike

Still open here:
- Only a stool beside the thing used is taken: the two by the bar of the starting settlement
  stand a tile away from it, and nobody sits on them
- They face whichever way they last walked, not the fire nor the table
- A table is nothing to eat at: a stool by one is a stool by nothing
- Whoever stands idle on a stool's tile stands, and the stool is still drawn over their feet
- Nothing of this has been seen on a real window by whoever made it

### S45 — The player governs (needs S27, S28 and S38) — done
The user's words: "Todo el tema de leyes castigos, moneda y tal aun que exista un cabecilla
«representante mini» lo gestiona el jugador, asi damos un apartado mas jugable al jugador".
Asked first, and answered:

- **What is left to the residents depends on the government**, in the user's words: "si es
  democracia todos tienen su voto, si es caudillaje acatan aun que lo odien, se pueden
  manifestar contra leyes si no estan bien metidas". Not one of the three that were offered
- **Whether somebody is guilty is still theirs to say**, and what they are given the player's
  (S28, as it was)
- **A protest is leaving the post and standing there**, a few hours each day the law stays in
  force, and in the user's words "podemos crear una plaza central donde puedan protestar con
  pancartas". The banners are P51's

This is the third place where what the player says is done and not advised, after affecting a
resident (S37) and the kind of government (S38), and it sets aside what S27 began with, that
the player proposes and the settlement decides: for laws and for what the settlement trades
with, the player now governs. Who leads, how each votes and what they make of it stay theirs.

Built:
- **Laws, doing away with one, a currency and going back to barter are the player's to run**
  (`decrees` in `data/proposals.json`). Put by the player they need nobody to make them
  theirs, and whoever leads refuses nothing of them
- **How one comes into force is the government's.** Where whoever leads decides alone (a
  mayor, a commander, a ruler) it is in force there and then, with nobody asked. Where a
  council or everybody decides, they vote on it as on anything: it waits to be talked over,
  the player may speak to whoever votes, and it is done only if it carries, milder if that is
  what carries. With the seat empty it falls to a vote
- **Residents no longer put laws to each other**, nor the end of one, nor how to trade, and
  whoever leads has no whims: what they still raise unasked is a vote on whoever leads and
  another kind of government (`residents_raise`). Whoever has had enough of how things are
  traded has nobody to put it to, and holds that against the government
- **A law remembers how it came in**: put on them with nobody asked, or voted
- **Whoever is against a law enough goes out against it** (`simulation/politics/protest.py`).
  At noon they leave a stroll or their post and stand in the square until three, each day it
  stays in force. How much they have against it is what they make of the law: all of that
  for one put on them, half for one that was voted, and by how freely people speak out under
  the government they have (`dissent`, from 1 under an assembly or a commune to nothing under
  a ruler, where they do as they are told however much they hate it)
- **The square is a thing to put down** (`plaza`): free, in Urbanismo, and there is one in the
  settlement that comes ready made. With none they gather where newcomers first stand
- **Holding has a cost.** Where it is put up with, each day of it takes legitimacy and adds
  to unrest, by how many stood there. Where the settlement is authoritarian enough they are
  leaned on instead: it leaves fear and a grudge in whoever was there, and adds to how
  authoritarian the place is
- **Doing away with the law, or making it milder, is taken as having been heard**: whoever
  stood there trusts the player more and holds less against the government, and legitimacy
  gains a little. Milder, it is another law to them, and whoever still cannot abide it
  starts again
- **They give it up after six days for nothing**, and what they hold against it stays
- Nobody goes who is a child, away, locked up or on their way out. Nothing of it is a roll
- `protest_called`, `protest_held` and `protest_won` are political events, and a protest is
  a fact that is seen and told
- Saved: whether each law was put on them, and who is out against which. Save version 35

Decided without asking:
- A mayor counts as one person deciding, like a commander or a ruler: under all three a law
  of the player's is in force at once. What tells them apart is how freely people speak out
- The player may undo or change at once what they decreed at once: there is no wait where
  nobody is asked. What was voted down is left alone for a week, as before
- Throwing somebody out, a vote on whoever leads and another government are still put as
  they were (S27): they are not laws, punishments or the currency
- A protest is from twelve to three, which costs whoever goes an hour or two of their shift
- With no word from anybody a protest wears itself out: nobody is punished for it, and
  nothing worse comes of it. Trouble that grows is still S29

Still open here:
- It is on screen since P51: the laws on the government's panel, and placards in the square
- Whoever leads is a representative in name: what they think of a law of the player's tells
  on their own vote where there is one, and on nothing else
- Nobody campaigns against a law before it is voted, and a council that votes a law in
  against most of the settlement answers to nobody for it
- The laws that need a court (S43) are still to be written, and are the player's too

### S46 — What each is capable of (needs S26) — done
The user's words: "vamos a agregarle estadisticas a los PJ: FUERZA CONSTITUCION DESTREZA MENTE
SENTIDOS CARISMA. Estos podran influir en trabajos combate liderazgo vida etc". Asked first, and
answered with the recommendation: from 1 to 10, the first resident's shared out by the player,
everybody else's from the seed and their parents, and growing with use.

- **Six attributes, as data** (`data/attributes.json`): strength, constitution, dexterity,
  mind, senses and charisma, each with a name, three letters and a line on what it is for
- **Five are kept with the resident, and charisma is not a sixth number.** It is the side of
  their way of being that already went by that name (S26), read from 1 to 10: there is one
  charisma, and what politics made of it is what it was
- **Whoever comes has what the seed gives them**, always the same for the same settlement
  and person, made the first time it is asked for. The nine who come ready made are as the
  game says: Tomás strong, Vera with a good head, Paco with a poor one
- **A child takes after whichever parents live here**: six parts in ten the middle of
  theirs, the rest their own
- **The first resident is as the player made them** (`FoundResidentCommand.attributes`): what
  is left out is in the middle, and all six come to no more than there are points for, 33.
  What is over is taken from each by how far above the lowest it is
- **What each is good for is data** (`effects`), so much for each point either side of five:
  - *Work*: every job goes by one of them (`stat` in `data/jobs.json`), and whoever has more
    of it does the job four parts in a hundred faster a point. The garden and the water go
    by strength, the kitchen and the workshop by dexterity, the cantina and the shop by
    charisma, the watch and the handcart by senses, and the clinic, the desk and the
    laboratory by mind
  - *Strength*: what is dealt in a fight, and a unit more in a trip for every two points
  - *Dexterity*: what is taken in a fight
  - *Constitution*: how bad any injury comes out, how fast it mends, and how much work tires
  - *Mind*: how fast things are worked out at the desk
  - *Senses*: how far somebody sees, and what a trip outside brings back and risks
  - *Charisma*: what it already did for loyalty and for votes (S26, S27)
- **Use raises it**, more slowly the higher it is and never past ten: a minute at the post
  for what the job goes by, a fight for the strength of whoever struck and the dexterity of
  whoever was struck, an injury come through for constitution, a day of leading for
  charisma. A point takes about three weeks of work from the middle
- **Age and injuries take from what somebody can do today, not from what they have**: past
  fifty the body gives a little each year, the head does not; a child has not all their
  strength until sixteen; and whoever is hurt has less strength and dexterity until they mend
- `attribute_grew` says when somebody comes to a whole point more
- Saved with each resident. Save version 36

Decided without asking:
- Leadership stays the side of a way of being that it was (S26): how well others do under
  somebody is not one of the six
- An attribute is shown in whole points and kept in tenths and less, so that growing is slow
- Somebody exiled who comes back is as capable as they left

Still open here:
- It is on screen since P52
- Children under ten have none until they walk (S25): what they will have is settled then
- Nobody is turned down for a job, or put to one, for what they are capable of: staffing
  (S8) does not look at it
- A raid is answered as it was (S11): strength does not come into it
- What each point does is a first guess

### S47 — A trade, and what it teaches (needs S46 and S17) — done
The user's words: "Los trabajos ahora tendran experiencia, cada nivel de experiencia de un pj le
enseña a hacer cosas nuevas, ejemplo, el granjero sube a nivel 2 ahora sabe cultivar (se generan
datos de un nuevo alimento) dibujalo y ponle nombre a lo nuevo que sabe cultivar, asi el jugador
si quiere que el nuevo cultivable sea un tomate lo es y si quiere un limon pues limon, nosotros
solo elegimos x cosas depende del trabajo, en el caso del granjero el dibujo el nombre y un
desplegable de como se cultiva, tierra, matojo, arbol etc". Asked first, in two batches, and
answered:

- **What somebody learns is theirs, and they can show it to others**: if they die or go
  without showing anybody, it is lost
- **Every job that was put to the user teaches something**, and in their words "cuando
  implementemos mas trabajos veremos que crean": the garden, the kitchen, the cantina, the
  laboratory, the clinic, the workshop, the watch and the handcart
- **Five levels, and something new at each**: not the recommendation, which was something new
  at two of them. Four things for each resident and job, and the work better at every level
- **How a crop is grown changes how long it takes, how much it gives and how it looks**

Built:
- **Time at a job adds up** (`Resident.trade`, minutes by job): a minute at the post, or out
  there for whoever works out there. A good head learns sooner (S46)
- **Five levels** (`data/crafts.json`), the first from nothing and the rest at 3000, 9000,
  20000 and 36000 minutes: about a week of work for the second and three months for the fifth
- **Each level makes the work go faster**, five parts in a hundred: what a post makes, what
  the desk works out, what a trip brings back, and how far whoever keeps watch sees
- **Each level brings something new**, of the kind the job teaches. The game works out what
  it is like, always the same for the same settlement and thing, and better the higher the
  level it was come to at. Until the player has named it, it waits, and nobody makes it
- **What the player says of it is its name and what its kind lets be picked**
  (`NameDiscoveryCommand`), and nothing else. Drawing it is the window's business:

  | Job | What is come to | What is picked |
  |---|---|---|
  | Garden | A crop: food | How it grows: in the ground, on a bush, on a vine, on a tree |
  | Kitchen | A dish: a meal | What it is made of, out of the raw food there is, crops included |
  | Cantina | A drink | How it is made: distilled, fermented, or an infusion with no drink in it |
  | Laboratory | A substance | What it does (calms, lifts, puts out) and how it is taken |
  | Clinic | A remedy | What it cures: wounds, what was eaten or taken, hunger and thirst |
  | Workshop | A tool | The job it is for, out of those that make something |
  | Watch | A weapon | Its type: for close quarters, to keep them at a distance, or to stop blows |
  | Handcart | Somewhere to go | What is brought from there: food, scrap, fuel or medicine |

- **A kind has no code of its own.** What the thing is, what there is to pick and what each
  pick does are data, laid over one another into an item like any a pack brings. The item is
  that settlement's alone, kept in its save, and the game's own definitions are not touched
- **A crop grown in the ground** gives one every 18 minutes; **on a bush** two every 30; **on
  a vine** three every 36, from four days after it is learned; **on a tree** four every 30,
  from two weeks after, with no replanting. Whoever is shown a tree waits for their own
- **What somebody has come to is made in turn with what the job gives anybody**: whichever
  there is least of. A dish needs what it is made of in the cook's hands, who fetches it when
  the pot has less of that dish than of the usual
- **A pantry holds as much of the garden as it did, of more kinds**: what a job makes and
  what anybody has come to at it share the room there is where it is kept
- **A post that makes nothing of its own** (the clinic, the workshop, the watch) makes what
  its worker has come to, slowly, while the settlement keeps too few: remedies into the
  medicine cabinet, tools and weapons onto the shop's counter
- **A tool made for a job** makes that job go faster for whoever carries it, as a hoe does
  for the garden, and whoever holds that job wants one. **A remedy** is a dose in the clinic
  that lasts longer and mends what it is for faster. **What is worn to stop blows** takes
  some of every blow and wears out. **What keeps them at a distance** makes standing up to
  raiders safer
- **Whoever knows of a place outside goes there in its turn**, for the one thing brought from
  it, and a day in between for wherever their feet take them
- **Whoever holds the job learns it from whoever knows it** by being within six tiles of
  them long enough: fifteen hours, less for a good head. It is the learner's from that day
- **What only one knew is lost with them**, dead or gone: the thing is what it was, what
  there is of it is still there, and nobody makes more. What they had come to and nobody had
  named is forgotten
- `trade_level`, `discovery_made`, `discovery_named`, `trade_taught`, `trade_lost` and
  `thing_made` say each of those. A thing named is a fact that is seen and told
- Saved: the time each has at each job, what each knows and is learning, what has been come
  to, and what somebody was last dosed with. Save version 37

Decided without asking:
- What a drink is made of was put to the user as what is picked. The bar draws only water,
  so what is picked is how it is made. A dish is made of what was said
- A place is not drawn: it has a name and what is brought from it
- What a new food tastes of is the game's to say, out of six tastes: the player is not asked
- A level is never lost, and time at a job that somebody leaves is kept for if they go back
- Somebody shown a thing remembers who showed them, and trusts them a little more for it
- Whoever is within reach teaches, at work or not: there is nobody who sets out to teach
- With no word from the player a discovery waits for ever: nothing names it for them

Still open here:
- It is on screen since P54: the screen on which a thing is drawn and named
- Tools, weapons and remedies are made of nothing, and only the time they take holds them back
- The shop, the water and the desk teach nothing: only the work is better at each level
- A crop is grown in the bed its farmer has: no bed is given over to it. How it grows is
  seen there since P55
- Nobody is put to a job, or kept at one, for the level they have at it (S8)
- A new thing has no part in what residents like until they have tried it (S19)
- What each level takes and gives is a first guess

### P51 — Laws to put, and placards in the square (needs S45) — done
- **The government's panel has three tabs**: how they are governed, as it was (P34); the
  laws; and the odd laws. Fourteen and eight, each on a line of its own, and all of them fit
- **How a law comes in here is said at the top**: at once where one person decides, or by a
  vote, with the hours it is talked over. Under it, what waits to be voted and in how long,
  and who is out in the square against what, how many and for how many days
- **Each law says how far it goes**, with an arrow either side for one that goes further or
  less far, and what it names for one that names a food. What is picked is kept on the panel
  until it is put
- **`Decretar` puts it in force** where one person decides, and reads `A votar` where it is
  voted. A law in force reads `Quitar`, and `Cambiar` beside it once another degree is
  picked. What comes of it is said in the notice, and a refusal sounds as one
- **Whoever stands in the square against a law holds up a placard**, a board on a stick with
  a thing crossed out, shaken as they stand. The list of residents says they are out
  protesting
- **The square is in the plaza**, by the fire, in the settlement that comes ready made, and
  is in Urbanismo to be put down anywhere

Decided without asking: the laws go on the government's panel as tabs, and not in an entry
of the menu of their own, which has no room for another.

Still open here:
- What a law does at each degree is its name and nothing more: nobody is told what each
  resident makes of it before it is put
- The votes of a law that is voted are not shown, nor who can be spoken to: `LobbyCommand`
  is still a command (P26)
- The currency is still put from `Fondo`, as it was, and comes in as a law does (S45)
- The square has the game's plain sprite on the canvas, and its picture on the window

### P52 — What each is capable of, on screen (needs S46 and S47) — done
- **A resident's panel has two rows more under their bars**: what they work at, the level
  they have at it and a bar to the next; and their six attributes, three letters and a
  figure each, green above the middle and red below it. What somebody can do today is what
  is shown: hurt or old, the figure is lower
- **`Puestos` says the level of whoever holds a post** past the first: `Raúl nv3`
- **Where the first resident is made there is a third face, `Qué puede`**: a row to each of
  the six, with what it is for, a figure and a bar, and a button either side. Everybody
  starts in the middle with three points to share out; what is taken from one is there to
  give to another, and nothing goes under 1 or over 10

Still open here:
- What an attribute does is said in a line where the first resident is made, and nowhere
  on the map: nothing says how much faster somebody works for it
- Nothing is shown when somebody comes to a point more, or to a level, but the line in the
  log of events
- The attributes of whoever is at the gate are not shown before they are let in

### P53 — Soles flat on the ground (needs P43) — done
The user: "la planta de los pies se mueve, deberia estar siempre horizontal al suelo y pegada
al suelo a menos que salten o similar". Walking, a shoe turned on its ankle to forty-five
degrees and its toe went under the ground: the stride rolled the foot from heel to toe (P43),
the foot had a spring of its own, and since P45 it turns whole about the ankle.
- **A sole on the ground, or near it, is level with it**, whichever way its clip and its
  spring would turn it. It lies the way it points: ahead for a foot that stands, behind for
  one that kneels, as when curled up on the ground
- **A foot that is down is down.** A leg that had not quite settled on its springs left its
  foot a hair above the ground. Within a little of the ground (`footing.hold`) a foot is on it
- **A body does not bounce off its feet.** The stride threw the body higher than its legs
  reach, drawn out and all, and both feet left the ground at every step: more with the
  longer legs most dolls are drawn with. The body is brought down until the foot it stands
  on is on the ground. A clip that means to leave the ground has to lift its feet, by
  turning its legs
- **Only a foot held well up is turned as its leg is**: a kick. How high that is, is data
  (`footing.level`): from there to twice as high a foot comes level little by little
- The small bodies shown without a window are left as they were

Still open here:
- Feet still slide along the ground when walking: a stride covers two tiles, and legs this
  short cover less than half of that. Not sliding would mean twice the steps, or half the
  speed
- The step is low and flat now: nothing rolls from heel to toe
- Nothing of this has been seen on a real window by whoever made it

### P54 — Drawn and named (needs S47) — done
The user's words: "dibujalo y ponle nombre a lo nuevo que sabe cultivar, asi el jugador si
quiere que el nuevo cultivable sea un tomate lo es y si quiere un limon pues limon".

- **Coming to something opens the screen for it**, as a birth opens the one to draw whoever
  was born (P25), and time stands still meanwhile. It asks what the kind asks: "¿Qué ha
  aprendido a cultivar?", and says who it was and at what level of what job
- **The paper and the tools are the item editor's**, and beside them there is only what the
  player says: a name, and a drop-down list for each thing its kind lets be picked, with a
  line under it on what the pick does. A list opens under its box and shuts on a pick.
  What the thing is like otherwise is the game's, and the screen says so
- **`Guardar`, or Enter, names it**: the settlement has the thing from then on, and its
  picture is kept in `custom_content/made/`, by the ID of the item. It needs a name, and one
  nothing else has: what is wrong is said, and the screen stays open
- **`Luego`, or Escape, leaves it waiting.** While anything waits there is a notice in the
  corner of the map, lit and unlit, that says who knows something new, or how many things
  wait. Pressing it opens the oldest
- **A place is named and not drawn**: there is no paper for it
- **What was drawn is what is seen** wherever the thing is: in a hand, in an inventory, in
  the pantry
- The folder of pictures is no pack: what a thing is belongs to the save of the settlement
  that came to it, and a new settlement does not have it

Decided without asking:
- The picture of a thing is kept apart from its definition: the drawing in the folder of
  drawings, which is the playthrough's (never committed), and what it is in the save
- A thing that is saved with nothing drawn has the game's plain picture

Still open here:
- What was named cannot be named again, nor drawn again, from this screen: the item editor
  redraws it, by its ID
- How a crop grows shows in the bed it grows in since P55. What the player drew of it does not
- What a pick does is said in a line, and no figure is shown before it is saved
- Two settlements kept on one machine share the folder of pictures, as they share the
  drawings of their residents

### P55 — A bed looks like what grows in it (needs S47 and P41) — done
Answered with S47: how a crop is grown changes how long it takes, how much it gives and how
it looks.

- **A bed is drawn by how the crop its farmer learned last is grown**: three round bushes
  heavy with fruit, two stakes with string and something climbing them, or a tree taller
  than whoever tends it. Grown in the ground, it is the bed as it always was
- **The simulation says which** (`CraftSystem.grown_at`), and the window has a picture for
  each (`crop_bed_bush`, `crop_bed_vine`, `crop_bed_tree`): a way of growing with no picture
  of its own is the bed as it was
- The bed of whoever grows nothing but what anybody grows, and one nobody tends, is as it was

Still open here:
- It is seen on the window, in the game's own hand. The small sprite of the canvas, and a
  bed the player has drawn (P17), are as they were
- A tree stands in its bed from the day it is learned: it does not grow before it gives
- One bed shows one way of growing, the last learned, whatever else its farmer grows there

### P56 — Words had each their own way, with bolts over their heads (needs P50) — done
The user: "la animacion de discutir debe ser tambien 3 animaciones elegibles en maneras, y
cuando discuten salen rayos". Until now everybody who had words with somebody did it the one
way, and nothing but a red bubble over their heads said they were at it.
- **Having words is a kind of manner**: `Discutir`, under `Maneras` and where the first
  resident is made, with three ways to pick from like the rest. `Encarado` is how everybody
  did it: at the other all the time, leaning in with a hand in their face. `Pataleta`: fists
  behind them, the body thrown at the other from the waist, and a foot brought down hard,
  twice. `Aspavientos`: both arms thrown up over their head, down against their thighs,
  held out, and up again
- Whoever was never given one has one of the three for good, by who they are, as with the
  other kinds: a settlement no longer argues all alike
- **Bolts fly while they have words**, as in a strip: jagged, bright, with the dark line of
  everything else round them. Three at a time and a couple of lots a second, from over the
  head of each of the two, in a fan that leans towards the other: out fast, then slower, and
  gone before the next lot. No two heads let theirs fly in step
- **They are over heads and never across a face**, and a name is written above where they
  fly for as long as the quarrel lasts, instead of among them
- On the map, inside buildings and where a manner is tried out, which shows the body a
  little smaller to leave them room. The small bodies shown without a window have them too
- Once it comes to blows they fight their own way, as before, and there are no bolts
- Nothing of a bolt is kept: which there are and where follows from whose head it is and
  the scene's own time. It is presentation: real time, none of the simulation's randomness,
  nothing saved

Decided without asking:
- A way of pointing a finger at the other was made first and thrown out. With arms as short
  as these it could not be told from the first way, side by side. The tantrum took its place
- The bolts go up from each head and not from one face to the other: one tile apart, bolts
  between the two hid both faces, the arms and the names
- How many bolts, how often and of what shape is in `graphics/bolts.py`, not in data

Still open here:
- A quarrel makes no sound of its own
- Seen from the front, the small bodies shown without a window tell the three ways apart
  by little: their keys from the front are few
- Two who quarrel one above the other on the map both look where they last walked, and
  their bolts lean that way
- Nothing of this has been seen on a real window by whoever made it

### S48 — With somebody, only what is felt for them (needs S37) — done
The user, on 2026-10-08: "Afectar lo vamos a cambiar, cuando cliquemos a un pj lo seguimos, si
le clicamos de nuevo se abrirá el menú afectar, este será similar al de los sims, circula
alrededor del personaje, tendremos varias opciones, desde hablar, a ocio etc, también se
desplegará el cómo se hace esa opción; si es con personas habrá más opciones según el afecto y
dependiendo de ese cambiarán, desde charlar a romance o a darse de hostias. Esto nos dará
mayor control sobre los pj y lo llevaremos un poco más al ámbito sims fallout shelter."

Asked first, and answered, for all of what follows (S48 to S50 and P57):
- **Who something is done with** is chosen by their faces in the wheel, and by a click on
  them on the map as well
- **What they do not feel is not there.** Shown greyed out with what is missing had been
  recommended, and was not taken: "Solo sale lo que siente"
- **Leisure** is what is done alone with nothing, what is done with somebody, and each by how
  they like it. Choosing which fire, bar or radio to go to was offered and left out
- **Orders pile up, and a resident can be told to do nothing of their own**: "Cola y además
  libre albedrío", over a queue alone, which had been recommended

- **What can be done with somebody is what is felt for them**, one way: what Raúl can be
  told to do with Marta is what Raúl feels for Marta, whatever she feels. There is always
  talk. Past it, each thing has what it takes written beside it in `data/affect.json`, as
  the least and the most of each feeling, with more than one way of feeling that will do
  where there is more than one
- **Thirteen things between two**: talk; a joke, talking things over and a hug as fondness
  grows; flirting, saying what they feel and slipping away as attraction does; a kiss, asking
  to marry and leaving, with a partner; standing up to them, insults and going for them as
  resentment does
- **Each is friendly, romantic or hostile**, which is how it is shown and nothing else
- **Romance is between adults, towards somebody they could be drawn to**, as everything of
  the kind already was
- **Five exchanges that were not there**: a joke, a hug, flirting, a kiss and an insult, each
  with what it does to both. An insult may come to blows as an argument may
- **Anybody it can be had with can be named**, not only the few nearest that are offered
- What had been "setting somebody on" (S37) is the same thing now: being set on somebody
  they hate is what there is to do with somebody they hate that much

Done when: with nothing felt there is talk and no more; each thing appears at what it takes
and not a point before; what one feels the other need not; a partner's are with a partner
only; nothing of romance is offered with a minor; and what is not on offer cannot be ordered.

Decided without asking:
- What each thing takes: a joke at 10 of affection, talking things over at 20 of it or 15 of
  resentment, a hug at 40; flirting at 20 of attraction, slipping away at 40, saying what they
  feel at 45 with 35 of affection, as a resident does of their own accord; asking to marry at
  50 of affection; leaving at 30 of resentment or no more than 15 of affection; standing up to
  somebody at 15 of resentment, insults at 30, blows at 50
- Whoever is asked is not: as with every order that sends one resident to another, what is
  asked of them is theirs to answer where it already was (a confession, a proposal, going off
  alone), and anything else simply happens to them
- `incite` is still read from the data, for content that has it. The game's own has none

Still open here:
- The player is not shown what is missing for something to appear, which is as it was asked
- Fear and trust open nothing yet

### S49 — Leisure (needs S48 and S22) — done
- **Four ways of passing the time alone, with nothing** (`data/leisure.json`): a stroll, a
  sit, a doze and a tune. Each is done where they stand, or from there, and takes a little off
  their nerves a minute at a time
- **Four with somebody**: cards, stories, a dance, and asking them for a drink. They are
  exchanges between two (`data/social.json`) and go by what is felt like the rest: cards with
  anybody they do not resent, stories with a little fondness, a dance with more or with
  attraction
- **Asking for a drink leads somewhere**: once it is said, each goes to the bar for
  themselves, and pays, and drinks as anybody does there. Whoever was asked goes only if they
  care for whoever asked. With nobody behind the bar it is not on offer
- **Each by how they like it**: a pastime goes by a taste (S19 to S22) like any other, that
  they come with and that shows. What they like does them more good, and what they loathe
  hardly any: from a fifth to nearly twice. With somebody, it is how much fonder of the
  other each comes away
- **The player learns it by seeing them at it**, as with what they eat, and from then on it is
  marked where it is offered. Whoever is with them learns it too

Done when: a pastime lowers what it says it lowers; one they love does more than one they
loathe; having seen it, the option says so; a stroll is walked; two sit down to cards and
come away fonder by how each took it; and asked for a drink, both go on to the bar unless the
one asked does not care for the other.

Decided without asking:
- How long each lasts and what it gives, in the data: a stroll of twenty to forty minutes,
  a tune of ten to twenty
- A doze is on the ground where they are, awake enough to be spoken to

Still open here:
- **Nobody does any of it unless told.** Residents with time on their hands still stroll
  about as they did: giving them leisure of their own changes how every day of the settlement
  goes, and wants weighing over many seeds first
- A taste for a pastime does not grow with doing it
- Whoever is asked to cards, a story or a dance is not asked: they sit down to it
- A dance has no movement of its own, and a tune no sound

### S50 — One thing after another, and nothing unasked (needs S37) — done
- **What is said while they are at something they were told waits its turn.** The first
  thing is done at once, as it was. The rest are done in the order they were said, each when
  the one before is over, up to six ahead
- **What can no longer be done when its turn comes is let go**, and it is said: somebody who
  has stopped hating whoever they were to go for does not go
- **Any of them can be taken back**: what they are at, which they leave off, or one that waits
- **Told to drop everything**, they drop what waits as well
- **A few words are said there and then**, whatever they are at, and take them from nothing
- **Taken from what they were told** by being stopped, or by somebody coming to have words
  with them, they take it up again after
- **A resident can be told to do nothing of their own accord.** They finish what they are
  at. From then on they do what they are told, and with nothing told they stand by: no work,
  no talk, no making up their mind about anything
- **What was put in their hands is still theirs to do**: something to take apart, a site in
  their charge
- **A body that can wait no longer is seen to unasked**: at ninety of hunger, thirst or
  tiredness they eat, drink or lie down, will or no will
- Others may still come and talk to whoever stands by
- **It is saved**: what they are at for having been told, what waits, and whether they do
  anything unasked. A save from before has nobody told anything

This is the fourth place where the player's word is done and not weighed, after S37, S38 and
S45, and the one that goes furthest: a resident with nothing of their own left to do is the
player's to run.

Done when: three things said are done in the order said; one taken back is not done and the
rest are; a resident who does nothing unasked stands where they are for a morning; told
something, they do it and stand by again; left hungry they eat at ninety and not before; a
save and a load go on the same; and the same orders on the same seed come out the same.

Decided without asking:
- **Opening the wheel does not stop somebody who is at something they were told.** It stops
  whoever is at something of their own, as before
- **The safety of a body that can wait no longer.** In the game this is taken after, somebody
  left alone dies of it. Here nobody dies of the player having looked away: the number is
  `desperate_need` in `data/affect.json`, and at 101 there is no such safety
- Telling somebody to do nothing unasked does not take them from what they are at

Still open here:
- Nothing is done about a whole settlement told to do nothing: every one of them stands by
- Whoever stands by with a decision of theirs open still has it: it was opened before
- What waits cannot be moved up or down, only taken back

### P57 — The wheel (needs S48 to S50, P35) — done
- **A click on somebody follows them, and a second opens the wheel about them**: round
  buttons in a ring, with them in the middle. It takes the place of the list that opened in
  the corner (P30). The way in from their panel opens the same wheel
- **It opens on the kinds of thing there are to say**: `Social`, `Ocio`, `Necesidades`,
  `Trabajo`, `Unas palabras`, and the switch for doing nothing unasked
- **Each opens on what there is of it**, and what is about somebody or something opens on
  who or what. `Social` is the other way about: first who, as their faces in the ring, the
  nearest first, and then what there is to do with them
- **A click on somebody on the map says who**, at any step, with the wheel still about
  whoever it was opened for
- **The way back is at the foot of the ring**, and out of it from its first step. The other
  button of the mouse does the same; a click on nothing, or on them again, shuts it
- **What it is, at a glance**: blue for what is friendly, pink for romance, red for what is
  hostile, purple for passing the time, each with its icon; a small heart or cross on a
  pastime they are known to like or not to
- **What each is called is beside it**, outwards, and what telling it says is under the ring
  while the pointer is on it
- **Kept whole on the screen**: near an edge of the map the ring is moved in
- **What they have been told is by their panel**, at the foot of the map: a small button for
  each, what they are at first and lit, and what it is when pointed at. A click takes it
  back. A lock before them while they do nothing unasked, which a click undoes
- **What they are at is said for what it is**: a stroll, a doze, cards with somebody,
  standing by to be told
- **Sitting and lying**: whoever sits to watch the day, to cards or to a story sits as they
  sit; whoever dozes lies on the ground as whoever has no bed does
- Drawn by the game at the resolution of the window, as the rest of the interface (P35),
  eight new icons among them, each to be replaced by a file in `illustrations/ui/icons/`

Decided without asking:
- The names: `Social` and not `Hablar`, since it is where blows are too
- The wheel shuts once something is said. To say another thing it is opened again, which
  does not stop them now
- Their name is not written over the wheel at its first step: it is over their head already
- No more than fourteen things in a ring

Still open here:
- The wheel has no keys
- What two are doing at cards, at a story or at a dance looks like sitting or standing and no more
- Somebody dozing is under the same blanket as whoever sleeps rough
- The faces offered are the eight nearest: anybody further is to be clicked on the map
- Nothing of this has been seen on a real window by whoever made it: the frames it was
  judged by were drawn without one

### S51 — What comes in and what goes out (needs S15) — done
The user, on 2026-10-08: "intentemos plantear como darle ese toque tomodatchi life (los dialogos
modulares con variables puestas por el jugador y los objetos)-> sims (todo el tema de
interacciones) -> fallout shelter (gestion de recursos hipervitaminado)". It comes in three
layers, each laid over what there is: what the settlement lives on (S51 to S57, S64, S65, P58 to P61
and P27), words and things (S58, S59, P62 and P65), and what is done with things and with each other
(S60 to S63 and P63).

Asked first, in two batches, and answered, for the three of them:
- **Resources first.** Not the recommendation, which was the order they were named in
- **The whole layer of resources in one go**, a milestone after another, with what is still to
  settle in each asked before it. Not the recommendation, which was to stop after the first
  four for them to be looked at
- **Every part of it that was offered**: a bar that says how things stand; work that is seen;
  stores, better posts and current; errands and training
- **Somebody is put to a post from the board, as an order, and by being dropped on it** (P27).
  Sharing everybody out among the posts at a press, and a mark on whoever would do better
  somewhere else, were offered and left out
- **A post is pushed for what is left of a shift**, as an order like any other, over a gamble
  settled there and then. **It can go wrong in all four ways that were offered**: whoever
  works is hurt, the tool breaks, the post breaks down, and what was being made is lost
- **For words** (S58): each resident's own phrases, lists of the settlement's, and what one
  calls another. In the user's words: "Los propios pj y los nombres de los items entran dentro
  de la composicion de las frases modulares". Writing whole lines inside the game was offered
  and left out
- **For what is done** (S60 to S63): things with more than one use, wishes and what weighs on
  somebody, and leisure of their own accord. In the user's words: "La parte agresiva, pegar,
  robar, acciones especiales que vayan con los rasgos". The other one answering was offered and
  left out

Read without asking: after resources come words, and then what is done, as they were named.

Where the layer of resources stands, on 2026-10-08: all of it is built but errands and the
box (S56), which the user left out for now when they were asked about, and what P61 was to
show of them. Words and things, and what is done with things and with each other, are
planned and not begun.

What holds for the layer of resources:
- Nothing is collected by the player. Whoever makes a thing carries it, as now (S8)
- What is the settlement's is what is nobody's: in a store, in the hands of whoever is
  carrying it, and at the gate
- Whatever changes how a settlement fares is run with the rule and without it, over some
  eighteen seeds of ten weeks, before it is taken as good

This one:
- **The resources a settlement counts are data** (`data/resources.json`): food, water, fuel,
  medicine and scrap, each by the category or the tag of the items that count as it. A pack
  adds another with an entry, and no code names any of them
- **What the settlement has of each** is what is nobody's: in a store, in the hands of whoever
  is carrying it, and at the gate waiting to be carried in. What is somebody's own is not
- **What comes in and what goes out is written down as it happens** (`LedgerSystem.record`, in
  `simulation/economy/ledger.py`), by resource and by why, where it happens: made at a post,
  with the job that made it; brought from outside; taken apart; bought from a caravan or sold
  to one; come as supplies; eaten and drunk; used to make something else; burnt in the
  generator; given in care; carried to a site, or given back from one; studied; used in a
  mending; sold over the counter; given to a prisoner; spoiled; taken by raiders; stolen;
  handed in to the settlement, or taken from it
- **Carrying is not written.** A thing that goes from a store into somebody's hands and on to
  another store is the settlement's all the way
- **At midnight what there is is counted**, and whatever the entries of the day do not come to
  is entered as unexplained. The count is the truth, and the entries explain it
- **How things stand** (`LedgerSystem.report`): for each resource, what there is; what comes
  in and what goes out in a day, by why, over the last three days closed; how many days it
  will last where more goes out than comes in; and whether that is fewer than two. Before a
  day has closed it is told from the hours there are, once there are six, and said to be so
- **What is running low is said once a day** (`resource_low`)
- **It decides nothing.** No dice are thrown and nobody does anything for what is written: a
  settlement goes with its books exactly as it would without them
- Saved (version 39): what was written today and on the last seven days, and what was counted
  at the end of each. A save from before has nothing written, and opens its books the minute
  it goes on

Done when: six weeks of the settlement that comes ready made, with six seeds, leave nothing
unaccounted for on any day; three seeds of ten days come out as they did before there were
books, event for event and die for die; what the garden makes is in and a meal is out; carrying
a thing about changes nothing; a deal with a caravan, a bed put up and a subject that uses up
what it studies are written as they happen; what nothing wrote down is entered as such; and a
save from before loads with nothing written.

Decided without asking:
- **Cooking is written as food into the pot and as much out of it.** The kitchen neither adds
  to what there is nor takes from it, and is seen to do both
- **What a site takes has left the stores once it is carried there**, and is back if the site
  is given up
- **Drink, tools and coin are not counted.** Nothing is a resource that the data does not name,
  and what the fund holds in coin is a figure of its own (S23)
- A week is kept, and three days tell the pace. The numbers are in the data

Still open here:
- It is on screen with P58
- Nobody in the settlement knows what the books say: they are for the player (S3)
- Three tests were failing before any of this, on the settlement as it was committed, and
  still are: four weeks of storms and raiders (`test_dark_and_danger`), three nights of curfew
  (`test_laws`) and ten weeks of medicine and light (`test_sustenance`)

### P58 — A bar that says how long it will last (needs S51) — done
- **Each resource in the bar says what there is, and which way it is going**
  (`ui/resource_bar.py`): a small arrow, up in green or down in red, and how much a day. With
  nothing to tell either way there is no arrow. What there is counts what is on its way in
  somebody's hands and at the gate, as the books do (S51)
- **How many days it will last**, where it is going down and that is under a month: `12d`,
  and `<1d` under one
- **Red, and blinking, where it will not last two days**
- **Resting the pointer on one says who makes it and what uses it up**, a day: the garden,
  the kitchen and what was brought from outside, what was eaten, what the kitchen took,
  what was sold; what that comes to; and how long what there is will last at that pace
- **A reading taken before a whole day is written is said more quietly**, and said to be
  rough where it is pointed at
- **How the settlement's spirits stand**, at the end of the bar: a face and a measure of the
  mean of everybody's who is there. Pointed at, it says the figure and names whoever is
  lowest. It is shown and does nothing
- **With less room, less is said**: first how long things will last, save of what is running
  low, and then which way they are going. What there is is always said
- **The resources shown are those the data names**, in its order, each by the icon it says. A
  picture the game has not goes by a plain one
- A face for spirits among the game's icons, drawn at the resolution of the window and small
  for where there is none, to be replaced by `illustrations/ui/icons/mood.png`

Decided without asking:
- The arrows are a few dots of the canvas, as the letters are, and not pictures of the window:
  they go with the letters when those are made fine (P36)
- The same job making a thing and using it up is said twice: `Cocina`, and `Cocina: lo que
  gasta`. How each reason is called where a job is known is data (`sourced`)
- What is said of a figure goes under the bar, over the map, and over whatever panel is open
  in that corner

Still open here:
- There is no room in the bar for how much there is room for: what the pointer says of a
  figure has it since S53, and the bar itself comes with P60
- What draws water is called `Agua`, as the job is, under what is said of water
- Nothing of this has been seen on a real window by whoever made it: the frames it was judged
  by were drawn without one

### S52 — Work that is seen, pushed and given out (needs S51, S46 and S50) — done
- **How fast somebody works is worked out in one place** (`WorkSystem.pace`), from what it
  already went by: the tool, health, spirits, pay, what they have taken, the laws, the
  attribute the job goes by, what has been worked out and the level they have at it
- **How far along the next unit is** can be asked of anybody at a post
  (`WorkSystem.progress`), and of whoever studies, how far along what is being worked out is
- **What somebody would make of a post can be asked before they have it**
  (`WorkSystem.expected`): how many times as fast as a plain pair of hands, and how many
  units a day where the job makes any. It tells what they carry and what they know
- **Putting somebody to a post is an order** (S37, S50): the one there already was,
  `task:take_job`. Proposing it is still there for whoever would rather ask
- **A post is pushed for what is left of the shift** (`task:push`, in
  `simulation/work/rush.py`): told to, they go to it if they are not there and work half as
  fast again. It is an order like any other, waits its turn and can be taken back. It is
  for whoever has a shift ahead of them at a post that makes something, works something
  out, or where they make what they have come to: not for keeping watch, nor for what is
  done outside
- **It takes more out of them**: as tired again as the day leaves anybody, and their nerves
  with it, every minute of it
- **Every unit turned out pushed may end badly**: one in twenty for somebody rested, in the
  middle of what the job goes by and new to it. Up to twice that the more tired they are
  past half way; less the more they have of what the job goes by; and a tenth less for
  every level they have at it. Work that turns out no units is looked at every half hour
- **What ends badly**, whichever of them can: they are hurt, with bruises, a cut or now and
  then a fracture, and never so that they die of it; the tool in their hands breaks; or what
  they had made and still had by them is lost, a quarter of it and no more than six units,
  out of their hands, their post and where it is kept, and is in the books as lost (S51)
- **It ends the push, and they trust the player the less for it** (S27), are the lower in
  spirits and remember it. Leaving the post or being put to another ends it too
- **What a push does and risks is data** (`data/work.json`), with what is told of each thing
  that goes wrong, and a job says it is not pushed with `"rush": false`
- `work_pushed` and `work_accident` say each
- Saved (version 40): until when each resident is pushing. In a save from before nobody is

Done when: pushed, the garden makes a third more in the same morning and whoever is at it
ends it more tired and more frayed; each thing that can go wrong does, with the risk forced;
nobody dies of it; whoever is better at it has fewer accidents; a push ends with the shift;
the books still come to what there is after something is lost; and with nobody pushed three
seeds of ten days come out as they did before any of this, event for event and die for die.

Decided without asking:
- **Being pushed tires by a figure of its own**, the same whatever the job, and not by twice
  what the job does: most jobs tire nobody past what a day does
- **Nobody dies of having been pushed.** It was asked for that they be hurt, not killed
- **What is lost is what they made and still have by them**, and at a tank never more than
  six units: a quarter of the water was a day and a half of it
- **Whatever goes wrong ends the push.** A second accident in the same shift would be the
  player's to ask for again
- Whoever is pushed still sees to hunger, thirst and sleep when they can wait no longer, as
  anybody at a post does, and is still pushed when they come back
- Trust in the player moves only when it goes wrong: a push that ends well is a shift

Still open here:
- The post breaking down is the fourth thing that can go wrong: it came with S55
- Nobody thinks anything of being pushed until it goes wrong: what they make of being told
  what to do (S20) does not come into it
- Whoever studies loses none of what was worked out: there is nothing of theirs to spoil
- The figures are a first guess

### P59 — Rings over posts, and a board that puts people to them (needs S52) — done
- **A ring over whoever is at a post that makes something** fills as the next unit comes
  (`ui/work_marks.py`), and for whoever studies, as what is being worked out does. It is
  beside the bar that says how much of the shift has gone (P32), which is as it was
- **Over their face where a roof is over them, and from afar**, smaller, as the bar is
- **A unit made is seen to come out**: its picture and `+1` beside the ring, rising and
  gone in a moment. What is lost at a post is seen the same way, in red. They come of the
  settlement's books (S51), and say nothing in the log
- **Whoever is pushed is seen to be**: a flame over their head for as long as it lasts, and
  their ring in red with an ember in the middle of it. When it goes wrong, a mark over them
  and a crash
- **The board says what whoever is selected would make of each post** (`ui/job_board.py`),
  at the end of its line: `x1,6 · 30/día`, in green where that is more than a plain pair of
  hands would and in red where it is less
- **`Poner` beside `Proponer`** on a post that stands free: the first is an order, and they
  have it at once; the second asks, as it did. On the post that is theirs, `Apretar` while
  they have a shift ahead, `va apretando` once they are, and `Quitar`
- **The wheel has `Apretar` under `Trabajo`**, with a flame of its own, and what they were
  told is by their panel with the rest
- Drawn by the game at the resolution of the window, and small where there is none, with
  `illustrations/ui/icons/push.png` to take the place of the flame

Decided without asking:
- **The ring is over whoever works, and not over the thing they work at.** Over a bed of the
  garden it fell on the head of whoever stood by it, and was thrown out
- **The bar of the shift stays**, since it was asked for by name (P32)
- **What they would make of another post takes no account of their pushing their own**
- **Told to leave a post they are pushing, it waits its turn** as anything they are told does
  (S50): `Dejarlo todo` first, for it to be done there and then
- A post that is somebody's cannot be given to another from the board: they are taken off
  it first

Still open here:
- Units that come out faster than they can be seen are over one another, with time at its
  fastest
- Nothing of this has been seen on a real window by whoever made it: the frames it was judged
  by were drawn without one

### S53 — Room for things (needs S51) — done
Asked on 2026-10-08 together with S54, in two batches, and answered. Three of the four answers
about this were in the user's own words, and none was one of the options:
- **The store is one thing of its own.** "Deberiamos crear un item unico que sea Almacen y ahi
  se meta todo recurso comun asi se diferencia cajas de Almacen". An `Almacén` is big, "tipo
  edificio", and everything the settlement lives on is kept in it. A crate is something else
- **What is kept there is taken through what there was.** "El almacen es el sitio donde se
  «guardan» pero se pueden coger los items a traves de deposito de agua despensa botiquin etc".
  The pantry, the tank and the cabinet are where it is taken from and brought to, not where it is
- **Full, they stop and say so, and another is what is wanted.** "Se deberia crear otro almacen
  (los almacenes son Grandes tipo edificio) si no paran e indican que no hay espacio"

What there is:
- **An `Almacén` is a thing of its own kind**, four tiles by three, a shed of sheet metal with
  wide doors, built as anything is (S16). It holds so much of each resource, as data: 100 of
  food, 300 of water, 30 of fuel, 15 of medicine, 40 of scrap. There may be more than one, and
  what they hold is added up
- **What stands free at a pantry, the tank, the cabinet, a heap of scrap or the generator goes
  to the store**, but for a little of each kind of thing kept at hand, and comes back as it is
  taken. Nobody carries it between the two: it is as the user said, kept in one place and taken
  through the others. So everything that was done at those places is done there still
- **A crate keeps none of it.** Whatever of what the settlement lives on is left in one goes to
  the store. A crate is for everything else: tools, what is somebody's, what is found
- **What is cooked stays in the pot, what is poured at the bar, what is on sale at the shop**:
  the store is for what is kept, not for what is served
- **With the store full of something, whoever makes it stops**, as they did when their own
  place was full, and it is said once a day: `No cabe más comida en el almacén: hace falta otro`
- **Another store makes room.** What they hold is one figure for the settlement
- **The cook fetches what goes in the pot from the store itself**, a load at a time. The medic
  and the mechanic no longer carry medicine and fuel about: the cabinet and the generator are
  kept up from the store
- **What vermin spoil and raiders take, they take from the store too**, of what was theirs to
  get at before: the food of the pantries and the scrap of the heaps, never the water
- **A settlement with no `Almacén` goes on as it did**: a new settlement has none until it
  builds one. Three seeds of ten days with the store taken out come out as they did before
  any of this
- **A save of the ready-made settlement from before gains its store** on being loaded, where
  the map has it, if that ground is still bare. Nothing else the map has is put back. The
  save went to version 42 to mark it
- **The settlement that comes ready made has one**, by the building its food is taken from
- The books say how much room there is, how much of each thing is in the store, and whether it
  is full (S51). Resting the pointer on a figure of the bar says so (P58). The bar itself is P60

Decided without asking:
- **The store is a thing, not a building**: it is not gone into, and has no room of its own.
  It is as large as a small building, which is what the user asked of it
- **The building the ready-made settlement had under the name of `Almacén` is called
  `Despensa` now**, which is what stands in it. There were two things of one name otherwise
- **A little of each kind of thing is kept at hand, not a little in all**, so that whoever eats
  at a pantry still has the choice of everything there is
- **Room is by resource, not by unit of anything**: a store with no room for water has room
  for food. Water is counted in hundreds and medicine in units
- **What is brought from outside is let in with the store full.** It stays where it was left,
  past what that place keeps at hand
- **How much a store holds is a first guess.** With it the ready-made settlement holds about a
  quarter more food than it did. Over eighteen seeds of ten weeks, against the same with the
  store taken out: as many alive (10.3 and 10.3), food 109 against 86, water 176 against 185,
  nobody without food in any, and four dead of thirst in one seed where there were none

Still open here:
- **That one seed.** With a bartender at the bar and eleven mouths, one water carrier does not
  keep up: the tank runs dry in ten weeks with the store and without, and with it four died
  before the ten weeks were out. It is how the settlement was before this, and wants seeing to
  where posts are made better (S54): a second carrier needs a second tank
- **Nobody asks for another store to be built.** It is said that one is wanted, and it is the
  player who has it built. The user's "se debería crear otro almacén" may ask for more
- **What comes from outside is not held at the gate** when there is no room, as the plan had it
- The store has no sign over it and says nothing of how full it is where it stands: P60

### S54 — Better things (needs S53 and S36) — done
Asked with S53. Three of the four answers were in the user's own words:
- **All four that were offered can be made better**: posts, stores, beds and the generator
- **Five levels, and a sixth that cannot be built.** "5, el 6 se consigue mediante las
  expediciones o mediante otros metodos mas adelante"
- **A level is a rarity, with its colour.** "En el inventario cambia el borde del grid de rareza
  comun pococomun raro epico legendario mitico (blanco verde azul rojo morado amarillo) si es una
  construccion como cama y demas te dice si quieres redibujarlo"
- **It takes a site and having been studied**: "Obra y estudio". Not the recommendation, which
  was a site alone

What there is:
- **The six rarities are data** (`data/rarities.json`): `Común`, `Poco común`, `Raro`, `Épico`,
  `Legendario` and `Mítico`, each with the colour the user gave it and by how much whatever has
  it does what it does better: 1, 1.15, 1.3, 1.5, 1.75 and 2
- **Whatever stands has a level**, from 1, which is its place among them. Everything starts
  common
- **A post is worked that much faster**, by whoever holds it. **A store holds that much more.**
  **A bed rests that much better**, over what the house it stands in already gives. **A
  generator gets that many more nights out of its fuel**
- **Making a thing better is a site on it** (S16, S36): put to somebody, who may say no; what
  it takes carried to it and worked on; and it is one level better when it is done. The first
  takes 3 of scrap and three hours, the second twice that, and so on
- **Each rarity has to have been studied first** (S17): `Buen oficio`, `Oficio fino`,
  `Maestría` and `Obra maestra`, each after the one before
- **A thing is not used while it is being made better**: nobody works at the post, sleeps in
  the bed or eats from it. A store goes on holding what it holds
- **Mythic is never made here**: at legendary a thing says that better is only found (S64)
- The save went to version 43: `level` on whatever stands. In a save from before everything
  is common

Decided without asking:
- **Which things have levels follows from what they are**: whatever is the post of a job, a
  store, or slept in. The generator is named in the data, where more can be
- **A pantry has none.** It was among the stores the user was offered, before the store became
  a thing of its own: it is where the store is taken from, and holds nothing of its own to
  hold more of
- **How much better each rarity is, and what it takes, are first guesses**
- **Whoever is asked may say no**, as with anything built. It is not an order
- **One thing is made better at a time, a level at a time**

Still open here:
- **There is no way of asking for it on screen yet**, nor of seeing how rare a thing is: P60
- **Nothing asks whether to draw it again** when it is done, which the user asked for: P60
- **A generator that gives more current** is what a better one should come to, once things run
  on current (S55). Until then it burns less
- Whether what a better post makes is better too is S64

### S64 — Rarer things (needs S54 and S47) — done
What the user's answers to S54 added, cut off as a milestone of its own. Asked what things that
are carried have a rarity, and where it comes from, they ticked every option and wrote "Todos".
Asked again on 2026-10-08, after S54, what it does and how it comes:
- **It does everything that was offered**: food and drink fill more, tools are faster and last
  longer, weapons hit harder, and it is worth more in trade. And in their own words: "Tambien es
  mas caro de vender y de comprar"
- **A tool or a weapon is made rarer by being mended at a better workshop**: a level each time,
  up to the workshop's own, with a unit of scrap more. Making the workshop better is what opens it
- **What comes from outside is seldom rare, and oftener for a risk taken**: nearly all of it
  common, and when whoever is out goes on at something worth a risk (S12) the odds are better.
  Mythic hardly ever

What there is:
- **A thing that is carried has a level**, which is its rarity (S54), and things of one kind
  and two rarities are two stacks. It keeps it wherever it goes: carried to a pantry, put away
  in the store, brought back out, handed over, bought, given
- **What a post makes is as rare as the post.** A bed of the garden that has been made rare
  grows rare vegetables
- **What is eaten or drunk does that much more good**, and no more harm. Of two things that
  would do, the rarer is what is reached for
- **A rarer tool is that much faster and wears that much less. A rarer weapon hits that much
  harder**
- **It is dearer by as much**, on a counter and in what anybody takes it to be worth
- **Mended at a workshop that has been made better, a thing comes away a rarity rarer**, no
  rarer than the workshop, for a unit more of what mending takes. It is said
- **What is found outside is drawn by weight**, as data: 86 in a hundred common, 10 uncommon,
  3 rare, and the rest between epic, legendary and mythic, which is three in ten thousand.
  Whoever went on at something worth a risk has three times the odds of anything but common
- How rare a find is is drawn with dice of its own: the settlement's are not moved by it, and
  the same things are found. What happens after may not be the same, for what a rarer thing
  does. Three seeds of ten days no longer come out as they did before this layer
- The save went to version 44: `level` on every item, and whether a trip took a risk

Decided without asking:
- **What rarity is better by is the one figure of S54**: a rare thing is 1.3 times as good at
  whatever it does, a mythic one twice
- **A mend raises one level and takes one unit more.** With none to be had the thing is mended
  and no more
- **What is used to build with loses its rarity in the building.** So does what is sold to the
  caravan
- **How much of a thing there is counts every rarity of it together**, in the bar and the books

Still open here:
- **What the caravan brings is always common.** The user asked for what comes from outside to
  be rare at times, "rebusca y caravana": what is bought at the gate is counted and not kept
  thing by thing, and wants that first
- **A thing that is rarer is not shown to be**: the border of its square is P60
- **Nobody prefers a rarer tool** when there are two to hand, and nobody is told a thing is rare

### S55 — Current, and things that break down (needs S54 and S15) — done
Built in three parts, each its own commit: the well, current, and wear and mending.
Asked on 2026-10-08, with S64 and after it, in two batches, and answered:
- **With no current, what runs on it stops.** Not the recommendation, which was that it only
  lose what current gave it over working without
- **The workshop, the laboratory and the water tank run on current**, besides the lamps and
  the radio. Of the tank, in the user's words: "El deposito / bomba va con electricidad, para
  la version de sin electricidad crearemos el pozo". So there is a **well**, a new thing, where
  water is drawn with no current
- **The player switches each thing on and off.** Each draws what it draws, and when more is
  asked for than there is, what was switched on last goes off
- **The generator burns by what is switched on**: the more that runs, the more fuel a day
- **Things wear with use and break by accident**, as recommended, and more, in the user's
  words: "objetos desgaste y accidentes (que en el inventario se vea la barra de salud) algunas
  comida y algunos consumibles que se vaya pochando que tenga un valor de pocharse a x
  velocidad dia". How worn a thing is shows in the inventory (P60), and what goes off is S65

What it comes to:
- **What a thing draws and what a generator gives are data**, and whether a thing is switched on
  is saved
- **A well** is the post of drawing water by hand: slower, and needing nothing
- **A post wears as it is worked**, breaks down when it is worn out or when a push goes wrong
  (S52), and stands idle until the mechanic has mended it with scrap
- A better generator gives more current (S54)

The well, done:
- **A job may have more than one kind of post** (`also_at` in `data/jobs.json`), each as
  good a post for it as the first, and **a kind of post says how fast it is worked** against
  any other (`post_pace` in `data/interactables.json`)
- **A well is a post of drawing water**, worked at six tenths of the pace of the tank. What
  is drawn is in it, a little kept at hand and the rest in the store (S53), and it is drunk
  from as the tank is. It takes 2 of scrap and two hours, and can be made better (S54)
- **Two can draw water now**, one at the tank and one at the well, which one tank never allowed
- **The opening of a new settlement asks for a well** where it asked for a tank
- **The settlement that comes ready made has one**, by its tank, and a save of it from before
  gains it (save version 45)

Current, done:
- **What a kind of thing draws and what a generator gives are data**: a lamp and the radio
  draw 1, the tank 1, the workshop and the laboratory 2, and a generator gives 16 while it
  has fuel, the more for having been made better (S54), which is what a better generator
  comes to now in place of burning less
- **Whatever runs on current is switched on or off**, by a command, and is on to begin with.
  Off, it draws nothing and stands idle
- **With no current a thing stops**: a lamp gives no light, the radio tells nobody anything,
  and nobody works at the workshop, the laboratory or the tank. What water there is in a
  tank is still drunk
- **Whoever draws water goes to the well when the tank stops**, if one stands free, and the
  post there is theirs from then on
- **When more is asked for than there is, what was switched on last goes off**, and then what
  was before it, until there is enough. It is said
- **Fuel is burnt by what is running and for how long**: a lamp for the night it is about to
  light, a post while somebody is at it, the radio while it is listened to. Nine lamps burn
  a unit a night, as the generator always did, and three burn a third of one
- **With no generator nothing that draws runs.** In a save from before, a tank in a
  settlement with no generator is a well from then on, which is the same post worked by hand
- The save went to version 46: whether each thing is switched on and when it last was, and
  the part of a unit of fuel burnt since the last whole one
- Over eighteen seeds of ten weeks, against the same before current: as many alive (10.4)
  and nobody dead in either, water 161 against 169, and fuel 15 against 34 from the 20 it
  begins with. It ran out for a night in one seed. With the tank drawing 2 it was 9, and
  ran out in three

Decided without asking, of current:
- **A workshop with no generator does nothing**, which follows from the two answers the user
  gave. The workshop is studied before electricity is: a settlement that builds one first
  has nobody mending until it has a generator
- **The tank draws less than the workshop**, for the fuel to last
- **Everything is on to begin with**, and what is built is on when it stands
- **The glow of the workshop goes with its current**, as the light of a lamp does

Still open here, of current:
- **There is no switch on screen**, nor any mark on what has stopped: P60
- **The mechanic of a workshop that has stopped is left with nothing to do**, and says nothing

Wear and mending, done:
- **A post has a condition, of a hundred**, and loses a quarter of one for every hour it is
  worked, twice that while whoever works it is pushing. Only posts wear: not a bed, nor a store
- **Worn out, it breaks down**: it is said, nobody works at it or uses it, and it cannot be made
  better until it is mended
- **Mending is a site on it, laid by itself when it breaks**, in the charge of whoever holds
  the workshop: 2 of scrap carried to it and two hours of work, as anything is built (S16)
- **Only the mechanic mends.** With none it waits, and it is theirs within the hour when
  somebody takes the workshop
- **A push that goes wrong may break the post outright**, the fourth way of the four the user
  chose (S52)
- The save went to version 47: `condition` on whatever stands
- Over eighteen seeds of ten weeks, against the same before it: as many alive and nobody dead,
  two posts broken down in a run and two mended, and 4 of scrap the less for it

Decided without asking, of wear:
- **How fast a post wears and what mending takes are first guesses**: a post worked every day
  breaks down about once in two months
- **A mechanic mends without current**: it is the workshop that needs it, not the hands
- **Nothing is looked over before it breaks.** The user chose wear and accidents, not rounds

Still open here, of wear:
- **How worn a post is is not shown**, nor that it has broken down but in the log: P60, with
  the bar on each thing in the inventory that the user asked for
- **A broken workshop is mended like any other post**, by the mechanic whose post it is

### S65 — What goes off (needs S51, S55 and S64) — done
From the answer of the user about how things break (S55): "algunas comida y algunos consumibles
que se vaya pochando que tenga un valor de pocharse a x velocidad dia".

Asked on 2026-10-08, when S55 was reported, and answered:
- **Food goes off more slowly in a new thing that runs on current**: "la comida se pocha mas
  lento en un nuevo objeto que va con electricidad y es arcon refrigerado". Not one of the
  options, which were about the store
- **What has gone off becomes compost**, which the garden uses to give more
- **What is fresh goes off, and what the player makes goes off if they say so**: vegetables
  and stew in a few days; tins, water and scrap not at all; medicine in weeks. Where an item
  is made in the game, whether it goes off and in how many days is chosen there

What it comes to:
- **How fast a kind of thing goes off, by the day, is data on it**, and most have none
- **A refrigerated chest** is a new kind of thing that holds food, runs on current (S55) and,
  while it has some, keeps what is in it much longer
- **What has gone off is compost**: it is in the books as spoiled (S51), and compost is a
  thing of its own that whoever works the garden uses up to grow more
- How far gone a thing is shows where things are shown (P60), as how worn one is does

Asked again on 2026-10-08, with everything else that was still open in the layer:
- **Food goes to the chest by itself, ahead of the store**: the chest is a store of food, what
  is fresh goes to it first while there is room and it has current, and the rest to the
  `Almacén`. With no current it goes off there as anywhere
- **Compost is put on a bed by the player**: "Lo echas tú". It is kept in the store until it
  is sent to a bed of the garden, which then gives more for some days. Not the
  recommendation, which was that whoever works the garden take it unasked

What there is:
- **`spoils` on a kind of item** is how much of its freshness, of a hundred, one loses in a
  day: vegetables 20, which is five days; stew 34, a little under three; medicine 1, which is
  fourteen weeks. Tins, water, fuel, scrap, drink and tools have none and keep. What residents
  come to make (S47) goes off as its kind does: a crop, a dish and a remedy
- **Every stack has its own freshness**, and loses it on the hour wherever it is: in a place
  things are kept in or on somebody. With none left the stack has gone off: it is written
  down as spoiled (S51) if it was the settlement's, it is said once for all that went that
  hour (`went_off`), and each unit of it is one of compost
- **Two lots of a thing that are not about as fresh are two stacks**, so that it is the
  older that goes off, and not all of it at once. Put together when they are within twenty
  points, they are as fresh as the two together. The older lot is eaten first, and comes
  out of the store first. Moving a thing leaves it as fresh as it was
- **The refrigerated chest** is built from `Urbanismo` for six of scrap and four hours of
  work, takes two tiles, holds forty of food and draws one of current for as long as it is
  on. What is in it goes off four times more slowly. What goes off is put in it ahead of the
  `Almacén`, and on the hour whatever of it is in the `Almacén` is moved to it while there
  is room. With no current, switched off or broken down it takes nothing in and keeps
  nothing: what is in it goes off as anywhere. What keeps is never put in it
- **Compost** is kept in the `Almacén`. `Abonar`, in what is said of a bed of the garden
  (P60), puts two units on it at once, from wherever they are kept: the bed is worked 1.4
  times as fast for three days. One dressing at a time, and nobody puts it on unasked
- **On screen**: the bar under the square of a thing that goes off is how fresh it is, as
  it is how worn for a tool; the list of what a place holds says how many days each lot has
  left, kept there; the chest says whether it is keeping what is in it; and the item editor
  has a field for how much a thing loses in a day, from 0 for what keeps

Decided without asking:
- **The figures**: 20, 34 and 1 a day, a chest that holds forty and keeps four times as
  long for one of current, two of compost for 1.4 times the work over three days. All of it
  is data: `spoils` on an item, `chill` on a kind of thing, and `data/spoilage.json`
- **Medicine goes off too**, in weeks, as the option that was chosen said, but in many of
  them: fourteen. At five weeks and at seven the settlement that comes ready made was left
  with half and with two thirds of its medicine after ten, and in one run of the two that
  `tests/test_sustenance.py` holds to it somebody went without. There is little of it and
  it comes slowly, so it is the last thing that should be lost to keeping it
- **Freshness changes nothing but when a thing goes**: half gone, it feeds as much and is
  worth as much. It is fresh, or it is compost
- **What is somebody's own goes off as well**, and is no loss in the books, which are of
  what is the settlement's. What goes off on somebody is left as compost in the nearest
  place things are kept in
- **Nothing goes off outside**: what whoever is away carries is as it was when they come
  back, and so is what waits at the gate to be carried in
- **The chest needs no study, and anybody builds it**. The settlement that comes ready made
  has none: it is what there is to do about food going off
- **The chest runs all day**, lamps only by night and a post only while somebody is at it:
  it is about four tenths of a unit of fuel a day
- **Its room is room for food in the bar**, with that of the `Almacén`
- **Compost is no resource**: it has no figure in the bar and the store holds any amount
- **The pantries still keep a little of each thing at hand**, out of the chest as out of
  the store: that little goes off at the pace of anywhere

How it was measured: eighteen seeds of ten weeks each, with things going off and without. Nobody dies either way. Food at the end is 94 units on average against 112, and the least there was at any midnight 59 against 65: some thirty units of food a week become compost, three hundred in ten weeks, which is far more than the beds can take. In two of the eighteen the pantries were bare for some days of the last weeks, four in one and two in the other, where without the rule none was. The one of the two that was followed day by day came to it after a fortnight of storms, rats in the pantry and a raid, with the garden worked as ever and nothing gone off in those weeks; and with the figures tried before these it was none of eighteen, and one. So eighteen runs do not say whether things going off makes such a stretch likelier, and it is written here as not known. Medicine at the end is 12 against 10: none of it can go off in ten weeks. One run went two days without medicine, with none of it gone off. A week of the settlement takes a twelfth longer to work out.

Still open here:
- Nothing is said before a thing goes off: there is its bar, and the days it has left
- With the `Almacén` full and room in the chest, the bar does not say that there is no room
  for what keeps
- Compost is good for nothing but the beds, and nothing limits how much of it there is
- A worker who carried two lots of what they make, one older than the other, counted only
  the first of them and so never thought their hands full: found while this was measured,
  and mended. Things of two rarities (S64) had the same flaw
- Nothing on the map says a bed has compost on it: it is said when the bed is pressed
- A thing a resident learned to make before this was built keeps: only what is come to
  from now on goes off as its kind does. The item editor changes either
- The screen where a discovery is named and drawn has no field for it: it is the item
  editor that has

### P60 — Stores, rarity and current on screen (needs S53 to S55, S64 and S65) — done
Done so far, the first of its parts:
- **The border of the square of a thing is the colour of its rarity**, in what a resident
  carries, in a row of what somebody has on them and in what a container holds: white for
  what is common, then green, blue, red, purple and yellow, as the user gave them
- **How worn a thing is was there already**, as a bar under whatever wears (S13): it is what
  the user asked for by `la barra de salud`, and is left as it was

Answered on 2026-10-08:
- **Things are switched on and off from the thing itself and from a board**: a click on the
  thing opens what there is to say of it, with its switch, and a board called `Corriente`
  lists everything that draws, what each draws and what the generator gives, with a switch
  to each
- **Of the two ways of picking somebody up, the one on `main` stays as it is** (P27). The
  branch `feature/DragDrop` is left unmerged

Done after that, the rest of it. How far gone what goes off is came with S65:
- **A press on a thing that stands shows what there is to say of it**, in the panel on the
  right: its name in the colour of its rarity, whose post it is, how worn, whether it has
  current and how much it draws, and for a store how full it is of each thing, as a measure
  beside each. What it holds is listed under that, as it was. A post, a bed, a store, the
  generator and whatever runs on current can be pressed; a stool or a table cannot, and a
  crate or a pantry is shown as it always was. It works from inside a building too
- **`Mejorar` is in that panel**, with the rarity it would come to and what it takes, or why
  it cannot be done yet: a subject to study, a breakdown to mend, a work already in hand
- **Making a thing better is put to whoever holds it**, as the user answered on 2026-10-08,
  and not to whoever is selected, which was the recommendation. The panel says who that is
  before it is pressed, and they may still say no
- **A switch on each thing that runs on current, and a board of them all**, as the user
  answered: `Apagar` and `Encender` in the panel of the thing, and `Corriente`, which lists
  what the generator gives, what is asked of it, the fuel left and every thing that draws,
  with where it stands, what it draws, how it stands and its switch
- **What stands idle is marked where it stands**: a red `!` over what has broken down, a
  grey bolt over what is switched off, and a bolt struck through over what is on with no
  current for it. What is better than common has a small stone at its foot in the colour
  of its rarity, and whatever is selected a line round it
- **When a thing has been made better it asks whether to draw it again**, as the user
  said: `Dibujar` opens the screen where objects are drawn, and `Ahora no` leaves it. The
  drawing is of every thing of that kind that good or better, and a common one stays as
  it was. `Dibujar` is in the panel of the thing too, at any time
- **How full the store is, in the bar**: a line under the figure of each resource, green,
  yellow from four fifths and red when there is no room left. A press on a figure opens
  what is behind it: the board of current for fuel, and what the settlement holds for the
  rest

Decided without asking:
- **`Corriente` has no entry in the menu**: the menu ends where the dock opens, and has no
  room for one more. It opens with `K`, from the figure of fuel in the bar, and from the
  panel of anything that runs on current or gives it
- **Who holds a thing**, where the answer left it open. A post: whoever has it, or else
  anybody of the job it is a post of. What stands in somebody's house, a bed above all:
  whose house it is, since a bed is nobody's in particular and a house is. Anything else,
  the store and the generator among it: whoever mends what breaks down. Whoever is away is
  not asked, and with none of them here it is said that there is nobody to put it to
- **The drawing of what has been made better is kept apart from the common one**, as
  `objects/<kind>@<level>.png` beside `objects/<kind>.png`, and is what every one of that
  kind as good or better is shown as until a better one still has its own. A drawing of each
  thing by itself would have been another way to read `redibujarlo`: it was not taken,
  because drawings are by kind everywhere else
- **The question stays until it is answered**, and is asked only where there is somewhere
  to keep drawings. A second thing made better meanwhile takes its place
- **The room there is, as a line and not as a figure**: there is no room in the bar for
  a second number beside each. The figures are said by resting the pointer on one, as since
  S53, and in the panel of the store
- **Where a thing in the open is**, in the board of current, is said by the building it
  stands beside, within six tiles: there are nine lamps and seven of them stand outside

Still open here:
- What stands under a roof shows its mark only from inside the building, or with the roofs
  off (`T`)
- A row of the board of current does not take the map to the thing it is about
- Nothing says what a mark over a thing means when the pointer rests on it: it is said in
  the panel of the thing
- The notice of a discovery still goes over the faces of whoever is away, in the same corner
  of the map; the question about drawing anew goes under them

### S56 — Errands, and the box (needs S51 and S39) — planned, left out for now
Asked on 2026-10-08, and the user answered every question about it the same way: "Dejamos
fuera los pedidos de momento". It is not built with the rest of the layer, and nothing of it
is settled.

- **An errand is a thing to be brought about, as data**, measured against how the settlement
  stands and against what was written down of what comes in and goes out
- **One that is done is paid with a box**, which waits at the gate to be carried in, as what
  is bought does (S23)

Still to settle, to be asked before it is built:
- Who sets them: the caravaneer, the settlement itself, or both
- How many at once, and whether one lapses
- What a box holds

### S57 — Training (needs S46) — done
- **Things to train at**, each for one attribute, as data: time at one raises it as using it
  does, and sooner
- A resident is told to, from the wheel

Asked on 2026-10-08, and answered:
- **Six things, one for each of the six**, three of the four that were offered and three in
  the words of the user: weights for strength, a chess table for mind, a target for senses,
  "destreza una comba, carisma un maniqui con cara pintada. Constitucion se hace dandole
  cabezazos a un tronco de entrenamiento jaja"
- **Nobody trains unasked**: "Solo tú". Not the recommendation, which had them go of their
  own accord in spare time as well
- **A thing trains as far as it is good**: a common one up to 6, and one more for each rarity
  past it, so that making the thing better (S54) is what lets somebody go on
- **It costs time and tiredness**: an hour of it tires and makes hungry and thirsty as work
  does, a point takes weeks, and whoever trains is not at their post

What there is:
- **Six kinds of thing to build**, from `Urbanismo` under `Entreno`, each for three of scrap
  and two hours of work: `pesas` for strength, `mesa de ajedrez` for mind, `diana` for
  senses, `comba` for dexterity, `maniquí` for charisma and `tronco de entrenamiento` for
  constitution. The settlement that comes ready made has none
- **Training is a use of the thing** that practises an attribute: `trains` on the use of a
  kind of object, as data. A minute of it raises the attribute as a minute at a post does,
  two and a half times as fast, and more slowly the higher it is
- **Only the player has anybody train**: with `Entrenar`, among the tasks of the wheel, which
  lists the things there are that still have something to teach whoever is asked, the
  nearest first; or by putting them down on the thing (P27). Nobody goes to one unasked
- **A thing teaches as far as it is good**: a common one up to 6, and one point more for
  each rarity past it, up to 10. Whoever has that much already cannot be told to train
  there, and it is said why. All six can be made better (S54)
- **A session is two hours**, and ends sooner if the thing has no more to teach them or a
  need of the body can wait no longer. It tires as work does, a little more for the
  weights, the rope, the target and the log than for the chess table and the dummy. One at
  a time at each thing

Decided without asking:
- **How fast**: 0.0003 of a point a minute in the middle of the scale, which is a point in
  about a month of one session a day, and in a week of doing nothing else. Work gives
  0.00012. It is data: `practice.train` in `data/attributes.json`
- **It makes nobody hungrier or thirstier than the day does**, which is what work does too:
  a post tires and nothing else
- **Charisma is trained like the rest**, though it is kept with how somebody is and not
  with their other five: the dummy raises that
- **What they can bring to bear today is not what is capped**: age and injuries take from
  that, and the cap is on what they have
- **Nothing is said when a session ends**, only when it comes to a whole point more
  (`attribute_grew`, as with anything that raises one)
- **A child trains like anybody**, if told to
- **They have a tab of their own in `Urbanismo`**, `Entreno`: among the furniture they were
  one more than its catalogue shows without the wheel, and more than the list of furniture
  inside a building has room for. The tests of both said so. They are a category of
  their own in the data, `"category": "training"`

Still open here:
- No thing has a movement of its own: whoever trains at any of the six is seen as at any
  work done with bare hands
- There is no way to have somebody train every day without telling them each time
- Nothing warns that training somebody leaves their post empty
- A thing to train at is put from `Urbanismo`: from inside a building only furniture is offered

### P61 — Training on screen (needs S57) — done
Errands and the box were to be shown here too. They went with S56, which the user left out
for now on 2026-10-08.
- **`Entrenar` in the wheel**, among the tasks, with an icon of its own: it opens on the
  things there are to train at, each named with what it is for
- **Putting somebody down on one** (P27) says `Entrenar` under the hand before they are let go
- **Whoever trains has a ring over them** that fills as the next point comes, in a colour
  of its own, where whoever is at a post has the ring of the post (P59), and is seen hard
  at it, as at any work done with bare hands
- **What is said of the thing** when it is pressed (P60): what it is for, how far it takes
  it, and how far it would if it were made better
- Each of the six is drawn by the game, like everything else, and can be drawn by the player

Still open here:
- The names in the wheel are cut short where there are many: how far each thing is does not fit
- Nowhere lists who has trained what, or how far each could still go

### P64 — Current in the menu, saving behind Escape, and punishments beside the laws (needs S28, P34 and P60) — done
Asked for by the user on 2026-10-09, with the layer of resources just built: "agrega corriente
al menu , y guardar lo metes en el menu de escape. ya que estas añade tambien castigos en
leyes".

What there is:
- **`Corriente` is an entry of the menu**, between `Almacén` and `Gobierno`. `K` and the
  figure of fuel in the bar still open the board (P60)
- **`Guardar` left that menu for the one `Esc` opens**, where it is the second entry while a
  settlement is being played: it saves, says so, and leaves the player in the menu. `F5`
  saves without leaving the map, as before. The last step of the opening says where it is
  now, and no longer points at the entry there was
- **`Castigos` is a fourth tab of the government's panel**, beside `Leyes` and `Leyes raras`.
  It is the screen that accusing, sentencing and what prisoners are given had been waiting
  for since S28, where each was a command and nothing else:
  - the trial in hand, who is tried for what and the step it has reached
  - **when somebody has been found guilty, every punishment there is**, with how much it
    weighs beside how much what they did weighs, whether it is done in sight of everybody
    and whether it is one of the harsh ones. `Dar` beside each that the settlement has a
    place for, and what is missing beside each it has not: stocks, a jail, a gallows
  - **what is known of whom** that nobody has been tried for, with `Acusar` beside each,
    while no trial is going on
  - who is serving what, and until when
  - **what prisoners are given each day**: how many meals and drinks, one more or fewer at
    a press, and of what, or of whatever there is most of
  - the last three punishments given
- **The game says when somebody waits to be sentenced**: in the line under the bar, and by
  the entry of `Gobierno` lighting up while its panel is shut. There is a day to say it in,
  as there was (S28)

Read without asking:
- **`castigos en leyes` is the screen for punishing, put where the laws are**, since there
  was none. It is not a punishment written into each law: what somebody is given is the
  player's to say each time (S28), and whether a law may narrow that is still S43's to ask

Decided without asking:
- **A harsh punishment is pressed for twice**: a beating, exile, death. There is no taking
  one back
- **What can be brought is what somebody here other than whoever did it knows of**, as the
  command already had it: the five latest, by name, with what it was and the day
- **Saving from the menu leaves the player in the menu**, with `Guardar` still in hand
- **The line in the menu of the map** is now drawn over `Urbanismo` and the drawing of
  things, which are of the game more than of the settlement

Still open here:
- The rest of P26: a trial and a punishment are not seen as they happen, only told
- What is known of whom is read off a panel by the player, who finds out a resident's
  tastes little by little and not this
- A sentence cannot be changed once given, nor a prisoner let out early (S28)
- The last step of the opening points at nothing on the screen now: it only says where saving is

### S58 — Lines with holes in them (needs S2, S19 and S47) — done
The second layer: words and things. It is the first way of putting talk into words (S34): a
line, not a murmur.

Already done, ahead of it: which line is said no longer moves the settlement's dice.

- **A line may have holes in it**, in `data/dialogue.json`, which still takes plain lines as it
  did. What a hole is filled with is data
- **A hole is filled with somebody or with the name of a thing**: whoever is listening, a
  partner, a friend, somebody they cannot stand; what they carry, what they like and what
  they loathe, what somebody came to at their job and the player named (S47). Only ever out
  of what whoever speaks knows
- **Words of the player's**, kept with the settlement: each resident's own phrases (how they
  greet, what they keep saying, what they say glad, low and angry), lists of the settlement's
  that fill holes for everybody, and what one calls another, each way by itself
- No words change what happens: so it was written, and the answers below undo it

Asked on 2026-10-09, in three batches with S59 and the layer after it, and answered. Two of
the answers changed what this milestone is: talk is no longer lines said in turn, and what
is talked of tells on how two people get on.
- **The residents ask the player for words**, with a notice that is opened whenever the
  player likes; they can be changed from the resident's panel as well
- **There is no dock any more, and nobody talks line by line.** In the user's words, which
  were none of the options: "El dock lo suprimimos, para las conversaciones, ahora saldran
  hablando y al pinchar sobre los que conversan pondra estan hablando sobre el dia que se
  comio [variable] y se atraganto etc. no van a conversar de manera real como antes,
  mientras les saldran bocadillos con iconos de lo que estan hablando ya sea pizza martillo
  la cara de un pj si es un tema en concreto sin ser un item saldra la frase variable en
  los bocadillos"
- **The lists to begin with are the four that were offered**, insults and compliments, food
  and cravings, places and dangers, subjects and gossip, and with them "Pj, items que
  conozcan": the residents themselves and the things they know of
- **What two people talk of need not be anything that passes between them, and it tells on
  how they get on.** In the user's words: "no tiene por que ser de algo que pase entre ellos
  pero si pueden hablar de rumores, items temas y todo eso, si pjA dice bla bla Zanahoria...
  osea hablan de zanahoria porque a pj A le gusta pero a pj B no le gusta bajara la relacion
  si es neutra o buena subira, asi con el tiempo se les podran pensar (!) de que puedo hablar
  con X y tu entre todo el vocabulario creado le puedes decir habla sobre esto o creas un
  nuevo tema, un poco como tomodatchi life 2". This undoes `No words change what happens`,
  which was written above before it was asked
- **Whether somebody likes a subject goes by the tastes there already are** (S19), and is
  listed with them: "ya tiene mecanica eso. en la lista de gustos de personaje salen de ahi,
  los temas tambien aplican ahi toda variable aplica en esa lista que ya tenemos"
- **Each resident's own phrases show as bubbles of text**: how they greet as a talk begins,
  what they keep saying now and then, and what they say glad, low and angry when they are

What it comes to:
- **A talk has a subject**: a thing, somebody, a word of one of the settlement's lists, or
  something heard. Whoever starts it picks one they like out of what they know
- **How whoever listens takes it moves what they feel for whoever speaks**: down for a
  subject they dislike, up for one they like or have nothing against
- **Over their heads there is a bubble**: the picture of the thing, the face of whoever it
  is about, or the words where it is neither. Pressing on either of them says what they
  are talking about, in a sentence put together from a pattern with holes
- **A resident comes to wonder what to talk about with somebody**, with a mark over them,
  and the player picks a subject out of everything there is, or makes a new one
- **Every word the player gives is a subject like any other**, with a taste to it for each
  resident, found out as their other tastes are

What there is, of which nothing is on screen until P62:
- **A talk is about something.** `chat` and `stories` carry `"subject": true` in
  `data/social.json`, and whoever walks over brings a subject up: a thing (`item:stew`),
  somebody (`person:ines`), a word of one of the lists (`word:insults.zopenco`) or something
  heard (`fact:fact_12`). Both have it for as long as the talk lasts. The log says what
  about, `Inés y Raúl charlan sobre lo que quedará en pie del Viejo Madrid`, and quotes nobody
- **What they bring up**, in this order: what the player told them to talk to this person
  about; or news the other has not heard, as often as a rumour was passed on before; or
  something they like out of what they know, the likelier the more they like it: the things
  they carry and those kept in the settlement that are everybody's or their own, the people
  they feel strongly about, for or against, never the one in front of them, and the words
  of the lists; or, caring for none of it, any word there is; or nothing, and then it is a
  talk as talks were
- **They learn what not to bring up.** What they have seen the other dislike weighs a
  quarter of what it would, and what they have seen them like half as much again. What
  they have not seen, they do not know
- **Whoever listens takes it one of the five ways a taste is taken**, and it tells on what
  they feel for whoever brought it up: a subject they hate takes 3 of affection, adds 2 of
  resentment and leaves them none of the good of the talk; one they dislike 1.5 and 0.5, and
  none of the good either; one they have nothing against leaves the talk what a talk has
  always been; one they like adds 2 and a third more of the good; one they love 4, half a
  point of trust and six tenths more. Whoever brought it up feels as after any talk
- **A thing is taken by the taste they would have for it** and a word by a taste of its own.
  **Somebody is taken by whether the two stand the same way on them**: to hear ill of
  whoever they cannot stand either is welcome, and to hear it of a friend is not. Something
  heard is taken as it comes, and is told by being the subject
- **A word is a taste like any other**: a taste tag, `word_insults.zopenco`, with a leaning
  for each resident, made the first time it comes up. Both what the listener makes of the
  subject and what whoever brought it up does show a little each time, to the player and to
  the other of the two, so it is found out and listed with the rest, called as it was
  written, between quotes
- **Eight lists of the settlement's**, as data in `data/talk.json`: `Insultos`, `Piropos`,
  `Comidas`, `Antojos`, `Sitios`, `Peligros`, `Temas` and `Cotilleos`, each with what a
  resident says to ask for a word and the patterns a word of it is talked of by. They come
  empty. A word is up to 48 letters and is not put twice in a list, however it is written
- **Five phrases of their own for each resident**: how they greet, what they keep saying, and
  what they say glad, low and angry. What comes out over them is worked out for the screen:
  the greeting as a talk begins, the rest now and then, oftener in company than alone
- **What one calls another**, each way by itself, said where that one is the subject
- **Residents ask.** At ten each day each has a chance in seven or so of asking for
  something: a word for a list, a phrase they still lack, what to call somebody they feel
  strongly about, or what to talk about with somebody they like. Up to three wait at once,
  one each, and one that has waited a day is let go with nothing lost. Nobody asks while the
  opening lasts
- **Told what to talk about**, asked or unasked, a resident goes and talks to them, as when
  told to (S50), and brings it up; where they cannot be told now it keeps for the next time
  the two talk. It is any subject there is, or a word made up on the spot, which joins a list
- **Six commands**: `AddWordCommand`, `SetPhraseCommand`, `SetNicknameCommand`,
  `AnswerAskCommand`, `DismissAskCommand` and `TalkAboutCommand`. Three events:
  `subject_taken`, `word_asked` and `word_given`
- **None of it throws the settlement's dice**: what is brought up, how it is put and who asks
  come of dice of their own
- **Saved**, version 49: the words, the phrases, the names, what waits and what was told, and
  on a talk under way what it is about
- **Measured** over eighteen seeds of six weeks, with it and without: nobody dies either way, and what residents feel for each other ends where it did: 10.9 of affection against 10.5, 11.8 of resentment against 11.9, 7.9 pairs fond of each other against 6.9, 123 arguments against 121. A little more news goes round, 565 tellings against 521, and more of what people like is found out, 357 times against 275. No word had been given in either

Decided without asking:
- **The lists come empty**: the words are the player's, as was answered. A list can come with
  words of its own, `words` in the data, for whoever mods one
- **Eight lists out of the four pairs that were answered**, each pair split in two, since an
  insult is not talked of as a compliment is, nor a place as a danger
- **Only a chat and stories are about something.** A joke, a hug, an argument and the rest
  are what they were, and a quarrel still quotes a line in the log
- **The lines of `chat` in `data/dialogue.json` are said no more** where talk is about
  something. The file is as it was: with no `data/talk.json` they are said as before
- **News is the subject as often as it was told before**, three times in ten and more for the
  sociable, and whoever brings a subject up tells nothing else at the end of it. Whoever
  listened still may, as ever
- **Somebody is taken by agreement**, and not by what the listener feels for them alone: two
  who cannot stand a third are the closer for saying so
- **They learn what not to bring up** from what they have seen, which was not asked for: it
  is what lets two people get on better with time without the player
- **What a resident knows of** is what they carry and what is kept that is everybody's or
  theirs. What is somebody else's in a chest they do not talk of
- **Guessing what they make of a thing makes no taste**: having it is still their first time
- **How often they ask**, how long an ask waits, and that one let go costs nothing
- **A phrase of their own comes out when they are alone too**, once an hour at most
- **The names are used for the subject only**: the log still calls everybody by their name
- **The numbers**, all of them in `data/talk.json`
- **Three tests of a long run look at another seed.** Two looked for somebody having a drink
  at the bar in the week of seed 3, and one for a fight that sends somebody to the clinic in
  the fortnight of seed 42, and with talk about something neither happens in those. It is
  the seed and not the rule: over eighteen seeds one week has no drink at the bar with it and
  one without, and of twelve fortnights with every fight egged on one has nobody at the
  clinic with it and none without, with 4.1 fights against 5.3. They look at seeds 18 and 9

Still open here:
- A word cannot be taken out of a list or put right once it is given
- An argument is about nothing
- Nothing keeps the same two from the same subject twice running, but what they have seen
  of how it was taken
- A word has no gender or number: the patterns are written to read with any
- Nobody makes up a word, a phrase or a name by themselves

### S59 — Handed over, and found (needs S58 and S19) — done
- **A thing is put into a resident's hands by the player**, and how they take it is seen and
  said (S19)
- **What is found outside may be something nobody knows**, which the player draws, names and
  says what it is, as with what is come to at a job (S47, P54)
- What a thing is for, and what is in it, is S30

Asked on 2026-10-09, and answered:
- **What is given comes out of the `Almacén` and the crates**: something that is everybody's
  is taken and put in their hands, and it is theirs from then on
- **A thing nobody knows may come from anywhere a thing comes from**: "de cualquier sitio,
  cuando se crea un nuevo item ya sea de salidas de caravana o todos los sitios posibles".
  The options were a trip outside, the caravan, the workshop and whoever arrives
- **The player draws it and names it, and no more**: what it is and what it does is the
  game's to settle when it is found. Not the recommendation, which had the player say what
  kind of thing it is as well

What there is, of which giving is on no screen until P65:
- **A thing is put in a resident's hands** with `GiveCommand`: one unit of something that is
  everybody's, out of wherever it is kept, the stores, a crate or the shop's counter, at once
  and with nobody carrying it. It is theirs from then on, as rare and as fresh as it was
- **They take it as their tastes have them** (S19), one of the five ways: it moves their
  mood, it is said, `Marta se alegra de tener un guiso caliente`, something of their taste
  for it shows, and they remember it, well or badly. Taken as it comes, nothing is said
- **It is in the settlement's books**, as given
- **Something nobody knows turns up now and then**, four ways: with whoever comes back from
  outside, 15 times in a hundred and one to three of it; left as a sample by whoever comes to
  trade, 30 in a hundred and one or two; inside something taken apart, 8 in a hundred; and
  in the pockets of whoever comes to stay, 35 in a hundred, which is theirs
- **The game settles what it is**, out of five kinds: something to eat, something to drink, a
  knick-knack, a toy and a remedy. What it does, what it is worth and what it tastes of
  come of a die of its own, the same for the same settlement and find, and can be had
  before it is named (`CraftSystem.preview`). The kinds are data, `data/finds.json`, each
  written as a kind a job teaches (S47) with nothing to pick
- **It waits to be named** as what is come to at a job does, by the same command and with
  the same event, `discovery_made`. Up to two wait, and while they do no more turn up
- **Named, it is an item like any other.** What there was of it waits at the gate and is
  carried in as what is bought is; what a newcomer brought goes into their hands. Nobody
  makes it. If whoever found it has gone, what was for everybody still waits, and what was
  their own went with them
- **Two events**, `thing_given` and `find_brought`, and `source` on `discovery_made` and
  `discovery_named`. Saved, version 50: where a discovery came from, how many of it wait
  and whose they are
- **None of it throws the settlement's dice**, and with nobody to name them finds change
  nothing that happens: the same seed gives the same days with them and without

Decided without asking:
- **One unit at a time**, and out of anything that is everybody's wherever it is kept, the
  shop's counter too. What is somebody's own in a chest is not the player's to give
- **Giving moves nothing of what they make of the player**: the answer was that how it is
  taken is seen and said, and it is. They are the gladder or the sorrier for it, and no more
- **They remember it always**, the better or the worse by how they took it
- **The four ways a thing comes in**, and how often by each. The answer was "de cualquier
  sitio": these are the ways things come in from outside. What a job makes is come to at
  the job, as it was (S47)
- **What a caravan brings that nobody knows is left as a sample**, and costs nothing
- **Five kinds, and none is a tool of a job or anything that gets hold of somebody**: a tool
  is for a job, which is picked, and a vice needs working out that a name does not give
- **There is none of it until it has a name**, so that nothing goes round without one
- **No more than two wait at once**
- **How good it is does not go by how much was risked for it** (S64)

Still open here:
- A thing cannot be taken back out of somebody's hands
- Nobody gives the player's present away, or minds its being given to somebody else
- What is found is never a tool, a vice or somewhere to go
- A find nobody names waits for ever

### P62 — Words on screen (needs S58) — done
What S58 brought, on screen. What S59 brings is P65.

What there is:
- **No dock for whoever talks.** The strip that opened over the foot of the map with two
  large faces and a line said in turn is gone, as was answered. It still opens for somebody
  asking for advice. The map goes down to the foot of the screen at all times
- **A bubble over whoever speaks**, of the two of a talk that is about something: the
  picture of the thing, the face of whoever it is about, or the words where it is neither,
  up to three lines of them. They take turns, four minutes each, whoever brought it up
  first. Inside a building as on the map; not from as far as the map is seen, nor through
  a roof
- **A phrase of their own is a bubble of words**: the greeting as a talk begins, the rest
  now and then, alone as well
- **How it was taken is seen over whoever listened**, with the mark a meal is taken with:
  relish or disgust
- **Pressing on whoever talks says what about**, under the bar, `Marta y Raúl están hablando
  sobre lo que daría ahora por un guiso caliente`, and it is at the foot of their panel for
  as long as they talk
- **Whoever is selected says the words of their bubble out loud**, where there are voices
- **Whoever wants a word of the player has a mark over them**, an exclamation in red, and a
  notice in the corner of the map, `Tomás te pregunta algo`. Pressing either hears them out
- **The board of words**, from `Palabras` at the foot of the roster, from `Palabras` over
  what a resident carries, or with `H`:
  - *of the settlement*: who is asking, with `Responder` and `Ahora no`; the eight lists,
    the words of the one on show, and a box to write another in
  - *of one resident*: their five phrases and what they call each of the others, each with
    `Cambiar`, and `Que hable de algo`
  - *an ask being answered*: what they ask, the box to write in, `Dar` and `Ahora no`
  - *a subject being picked*, for somebody who asked what to talk about or for anybody
    unasked: with whom, then `Cosas`, `Gente` and the eight lists to pick from, the things
    with their pictures and the people with their faces, and a box for a subject made up
    on the spot, which joins the list on show
- **Writing**: a press on a box, the letters, `Intro` to give it and `Esc` to drop it. While
  something is being written keys are letters and no shortcuts
- **A sound** when somebody asks

Decided without asking:
- **There is no entry of the menu for words**: the menu has no room for one more above where
  advice is asked for. The roster, a resident's panel and a key open the board
- **The mark over whoever asks is a red exclamation in a bubble**, since the answer was
  written `(!)`: the yellow one is somebody asking for advice
- **Only whoever's turn it is has the bubble**, so that two side by side do not show the
  same thing twice
- **What the two feel for each other, which the dock listed, is read in their panels**
- **The lines the dock said out loud are not said**: a voice says the words of a bubble,
  and a picture says nothing
- **A word is quoted with plain quotes**: the game's letters have no others
- **Answering what to talk about puts the board away**; anything else leaves it open
- **A click on whoever asks hears them out**, before it selects them for anything else

Still open here:
- A word cannot be taken out of a list or put right from the board
- The bubbles are the game's own drawing: there is no illustrated one
- Nothing shows that a subject was the player's and not theirs
- The notice of who asks does not say what, until it is pressed

### P65 — A thing handed over, and one found, on screen (needs S59) — done
What there is:
- **The `Almacén` gives.** With somebody selected, each thing it lists has `Dar` at the end of
  its row: a press puts one in their hands, and it says under the bar that they have it. It
  stays open, to give another. With nobody selected it says to choose somebody
- **`Dar` over what a resident carries** opens the `Almacén` for them
- **How they took it is seen over them**, as a meal is: relish or disgust
- **What nobody knows is named and drawn where what a job teaches is** (P54): the screen
  opens when it turns up, with time stopped. It says what the thing is, in its kind's
  words, where it came from and how many there are, and lists what the game has settled:
  what it does to each need, whose taste it is to and what it is worth. There is nothing to
  pick. Left for later, it waits under a notice of its own, `Hay algo que nadie conoce:
  ponle nombre`

Decided without asking:
- **Giving is done from the `Almacén`**, which lists just what there is to give: what is
  everybody's, wherever it is kept. The answer named the crates too, and what is in them is
  listed there with the rest
- **A press gives one**, and nothing is asked before it
- **The game says what it has settled before the thing is named**, so that it can be drawn
  and called for what it is

Still open here:
- A thing cannot be dragged onto somebody to give it them (P27)
- What a crate holds cannot be given from the crate's own panel
- The `Almacén` does not say what whoever is selected makes of each thing, where it is known

### S60 — More than one thing to do with a thing (needs P27) — done
The third layer: what is done with things and with each other.

- **A piece of furniture offers several things to do**, as data, where it offered one
- **A click on a thing opens a ring of what whoever is selected can do with it**, and dropping
  somebody on it (P27) goes by the same

Asked on 2026-10-09, since a click on a thing has shown what there is to say of it since P60,
and answered:
- **With somebody selected, a click on a thing opens the ring of what they can do with it**,
  with a way from it to what is said of the thing. With nobody selected it shows that, as now

What there is, of which the ring is P63:
- **A kind of object has what it is mainly for and whatever else can be done with it**, as
  data: `use`, as ever, and `uses`, a list of more, each a use like the first with an action
  of its own, what it is called, what is said of whoever is at it, how long it takes and what
  it does a minute
- **Ten more things to do with what there was**: lie down a while on a bed, sing by the
  fire, dance to the radio, wash at the tank or at the well, play a game at the chess
  table, skip for the sake of it, let off steam at the dummy and throw some darts at the
  target. And a table, which had nothing to it, is something to sit at
- **Residents weigh every one of them** when they choose what to do, each for what it is
  worth to them then: whoever is on edge and not thirsty washes sooner than drinks. What a
  thing offers beside what it is for is weighed without the grain of chance the rest is
  weighed with, so the settlement's dice are thrown as often as they were and no oftener:
  a settlement goes as it went, minute for minute, until somebody takes one of them up.
  And it appeals a little less than what a thing is for, three quarters as much, and than
  a thing of their own that is to hand: a table to sit at does not come before the fire,
  nor before the toy somebody carries
- **One in particular is told** with the order to use a thing, which names the thing and
  the use, `water_tank|wash`. Told plainly, it is what the thing is mainly for.
  `AffectSystem.things_to_do` lists what somebody can be told to do with a thing as things
  stand, what it is mainly for first
- **Everything about whoever is at a thing goes by the use they are at**: what is said of
  them, what it does to them and for how long, and whether they notice what goes on.
  Somebody lying down on a bed sees what happens in the room; somebody asleep in it does not
- **There is room at a thing for so many, whatever each is doing with it**: a bed with
  somebody lying on it is taken
- **A bed is whose it is whatever is done in it**: nobody lies down on somebody else's
- **Measured** over eighteen seeds of six weeks, with them and with each thing left its one
  use, in the same tree: nobody dies either way, with about as much food at the end (95
  against 102, less apart than one seed is from the next), the same spirits (56.8 against
  57.4) and as much said between them (533 chats against 531). It was not so at first:
  sitting at a table
  and lying down a while took sleep off whoever did them, and by night, too hungry to
  settle down to sleep, people sat up instead, night after night. In fifteen settlements of
  eighteen everybody had died within six weeks. Rest is a bed's, slept in: the two ease the
  nerves now and no more, and a test holds that nothing added to a thing is rest. Left to
  themselves residents take the ten up for less than an hour a day among them all, mostly a
  song by the fire of an evening: they ease nerves that are seldom on edge, and that waits
  for wanting to be entertained to be a need (S62)

Decided without asking:
- **Which ten**, and what each does: all of them ease the nerves, some tire, the fire and a
  song keep company
- **Residents do them unasked**, as they do anything else that is there to be used. The
  things to train at are still only for whoever is told (S57): what was added to them is the
  pastime, not the training
- **A table is still for nothing in particular**: sitting at it is one more thing to do with
  it, and it has no use that is its own
- **Six tests that held a seed to something were going to fail** when each thing a resident
  weighed threw a die more, for every day of every seed going another way. Weighing them
  without the dice was the answer to that, and not six new seeds
- **What a thing offers beside appeals three quarters as much as what a thing is for.**
  Weighed the same, whoever was on edge sat at a table before taking out the toy they
  carry, which is worth four fifths to them: things of their own would have gone unused
- **Being told to eat, drink, sleep or unwind still goes to what a thing is mainly for**
- **S30 is not built**, and this does not wait for it: what there is to do is still
  furniture's, as data, and not a handler that an item names
- **Nothing is saved that was not**: a use is told apart by its action, which was saved

Still open here:
- The ring of what can be done with a thing was P63. Dropping somebody on it still goes
  by what it is mainly for, as answered for P27, and asks only where there is no such thing
- None of the ten has a movement of its own: whoever dances stands
- None is for two at once: chess is played alone
- Nobody tires of doing the same thing

### S61 — Wishes, and what weighs on somebody (needs S60) — done
- **A resident comes to want small things**, which they see to themselves or are helped to
- **What has lifted their spirits and what has brought them down**, as a list, on their panel

Asked on 2026-10-09, and answered:
- **All four kinds of wish that were offered**: to eat or drink something, to be with
  somebody, to have a thing, and to do something. `Other` was ticked as well, with nothing
  written beside it
- **A wish that is met lifts their spirits and is remembered**, and one that lapses unmet is
  remembered too, the other way. Not the recommendation, which had it count for more when
  it was the player who met it

What there is, of which what is seen of it is P63:
- **A resident wants one thing at a time**, kept by resident in `world.wishes_of` and saved:
  what kind of wish it is, what it is for, since when and until when. The rules are
  `data/wishes.json`
- **Four kinds, as data**: something to eat or drink, a while with somebody, a thing to have,
  and something to do. Each says how it is told, how it is told met and let go, what is
  remembered of it either way and how much it weighs beside the rest. The two that are for
  a thing say which categories of thing: food and drink to eat, and to have, what is kept
  and used, which is a tool, a radio, or a trinket somebody found (S59)
- **What they come to want is out of what they know of and like**: a thing they carry or
  that is kept in the settlement as everybody's or their own, and that they would take to
  (`TasteSystem.fancy`, which makes no taste of its own); somebody they are fond of; any
  pastime (S49), and anything else there is to do with the things that stand there and
  are theirs to use (S60). Nobody wishes for a thing to have that they have, for what a
  law they keep forbids them, or for what they have made up their mind against
- **One may come on the hour, by day**, to whoever is in the settlement and wants nothing:
  about one every other day each, and it lasts a day. None comes during the tutorial
- **It is met** by eating or drinking the thing, or by being handed it (S59); by a friendly
  exchange with whoever it was, and not by a quarrel; by having one of the thing that is
  theirs, however they came by it; by doing what it was
- **They see to it themselves when the chance comes**: they are a little the readier to
  talk to whoever it is, to do the thing, and to go and eat or drink where there is some of
  it, hungry or not, and whoever eats or drinks from where there is some takes that and
  nothing else. It can wait, though: nothing pulls while a law they keep has them indoors,
  or in a storm
- **The player helps** with what there was: hands the thing over from the `Almacén`, tells
  them to go and talk to somebody, to pass the time, or to use a thing
- **Met, it lifts their spirits and is remembered as something good. Let go unmet, it
  brings them down and is remembered the other way**, by less. Whoever they wanted to be
  with leaving the settlement, or dying, lets it go there and then
- **Wishing throws none of the settlement's dice**: whether one comes and which is by a die
  of its own, keyed by who and when. What changes in a settlement is what follows from
  what they then do
- Domain events `wish_made`, `wish_met` and `wish_lapsed`
- **Measured** over eighteen seeds of six weeks, with wishes and without, in the same
  tree: nobody dies either way, with as much food at the end (105 against 95), the same
  spirits (56.8 either way) and as much said between them (535 chats against 533). A
  settlement of ten comes to want some four things a day among them all, and with nobody
  to help, a little over half are met (90 of 175 in six weeks): what there is to eat, a
  while with somebody, a song by the fire. What is wished for to have waits for the player

Decided without asking:
- **`Other`, ticked with nothing written beside it, is taken as no fifth kind.** Say what
  it was and it goes in as one
- **One wish at a time**, and none comes to whoever has one
- **How often and for how long**: one hour in twenty-five of the day's fourteen, a day to
  see to it
- **How much**: ten of spirits for one met and six off for one let go, and each is
  remembered for a little less than a present that was loved and one that was hated are
- **What is wished for to have is what is kept**: nobody wishes they had scrap, fuel,
  medicine or water, though they may like them, nor a vice, which whoever depends on it
  craves in a way of its own (S24)
- **Handed the very thing they wanted to eat, the wish is met there and then**, without
  waiting for them to eat it
- **Nobody goes and takes from a store a thing they want to have.** That one is for the
  player to give, which is what giving by hand was for, or for them to come by some other way
- **It makes no difference who or what met it**, as answered: a wish somebody else happened
  to meet counts as much
- **A thing wished for to have is met by any one of it that is theirs**, however rare
- **One test that held a seed to something moved to another**: three nights under a curfew
  see it broken by nobody but the two who owe the government nothing at seed 7 without
  wishes and not with them. Somebody else is caught out late in eleven seeds of eighteen
  without wishes and in twelve with them, so it is the seed's luck and not the rule. The
  settled world the tests of work count units in has nobody wishing: somebody who fancies
  a stew has one

Still open here:
- What somebody wants, over their head and on their panel, was P63, with the list of what
  has lifted their spirits and what has brought them down
- Nobody says what they want, to the player or to each other: it could be something to
  talk about (S58)
- Nobody goes and gets a thing they want to have, or buys it
- What somebody is like does not tell in what they wish for, beyond their tastes
- Nobody wishes for something to do with somebody: a game of chess is played alone (S60)

### S62 — Leisure of their own accord (needs S49 and S60) — done
- **Wanting to be entertained is a need of its own**, which tedium and work raise and pastimes
  and things lower. With time on their hands residents pass it unasked (S49 left it open)
- Run with it and without it over many seeds before it is taken as good

What there is:
- **A sixth need, `boredom`**, with a bar of its own on a resident's panel, `Tedio`. It is a
  need like the rest: whatever changes needs, by the minute or at a stroke, can name it, as
  data
- **It sets in with time awake**, some sixty of the hundred in a day, and not asleep nor
  away from the settlement. **Work adds a little** at every job
- **What passes it, as data**: every pastime (S49); a fire to sit by, a radio to listen to,
  and everything a thing offers beside what it is for (S60); a friendly exchange, a game of
  cards and a dance most of all; and a thing found that is for passing the time with (S59),
  which whoever carries one takes out. Not a quarrel, and not a drink at the bar
- **Residents weigh it with their other needs** when they choose what to do, at under half
  of what a need of the body weighs: bored to tears, and as fond of a pastime as anybody
  can be, is still less than work is worth, and a test holds that nobody leaves their post
  for it
- **With time on their hands and bored enough, they take up a pastime unasked**: from 45 of
  tedium each of the four is weighed for the tedium and the nerves it would take off them,
  a quarter more or less by how they like that sort of thing. Not in a storm, nor while a
  law they keep has them indoors or quiet
- **A pastime somebody wishes for (S61) is weighed bored or not**, so that wish is seen to
  as the others are
- **Whoever is bored is the readier to seek company**: some of what they want entertaining
  goes to going over to talk to somebody, which passes the time as a pastime does
- **Time of their own ends when their shift begins**: a pastime nobody told them to, and
  what a thing offers beside what it is for, are left when work calls, and what somebody
  wishes for (S61) does not pull at them while it does. What they were told to do, they
  see through
- **Nothing that is not a bed is rest** (S60): the rest there is in a doze, or in sitting
  down, is not counted when a pastime is weighed. Nobody naps in place of a night's sleep
- **Weighing a pastime throws none of the settlement's dice and makes no taste**: how they
  would take to it is read off the taste they have, or the leaning they would come to it
  with (`TasteSystem.inclination`)
- **It weighs on their spirits a little**: six of mood at its worst
- **Saved with the other needs.** In a save from before everybody is as bored as somebody
  new is, which is hardly
- **Measured** over eighteen seeds of six weeks, with it and without, in the same tree:
  nobody dies either way, with as much food at the end (108 either way) and the same
  spirits (56.4 against 57.1). A settlement of ten spends some five hours a day among them
  all at pastimes and at what things offer for the sake of it, where it spent one, and
  their nerves are the better for it (2.5 of stress against 4.8). Some of it comes out of
  talk: 493 chats against 531, and as many quarrels (127). Left alone they now meet two
  wishes in three themselves, where they met half
- **Four weeks of storms and raiders, seed by seed**: with it nobody's need of the body, of
  company or of quiet reaches the top in any of eighteen seeds, where without it somebody's
  did in three. Raiders find the guard at the gate in sixteen of them, and in the other
  two it is his night off

Decided without asking:
- **It does not wait for S31**, which is not built: what there is to do is still pastimes,
  things and exchanges, as data, and wanting to be entertained is what has them chosen
- **How fast, how much it weighs and from where**: a first guess, measured as above, in
  `simulation/residents/needs.py`, `simulation/ai/utility_ai.py` and
  `simulation/ai/routine_system.py`, and what each thing takes off it in the data
- **Drink is no answer to tedium.** Nobody takes to the bar for want of something to do:
  asking somebody for a drink passes the time, for the company
- **Company passes it by half of what was first written**: at the full figure a couple of
  chats a day left nobody ever bored, and no pastime was taken up
- **How much of it goes to seeking company**: three tenths. With none, time of their own
  came out of talk, a sixth fewer chats, and what they feel for each other grew a fifth the
  slower. With half, there was as much talk as ever and a fifth more quarrels, since going
  over to somebody is how a quarrel starts as well. At three tenths there are as many
  quarrels as there were and a little less talk
- **Time of their own ends with their shift** because the first measure of it showed the
  guard not at the gate when raiders came, in three seeds of eighteen where it had been
  none: he was still at a pastime begun before his watch. Whoever is at the fire or the
  radio when their shift begins stays as late as they always did: those are what the
  things are for, and were not touched
- **Two tests held by something else than what they say, and say it now**: the range a
  trip's finds fall in is the job's by who goes and what is known, and not the job's
  alone, which held at one seed; and a need there is not, in the test of pushing, is no
  longer `boredom`. No seed was moved
- **Nobody trains unasked, still** (S57). What was added to the things to train at is taken
  up unasked now, and the test that nobody went near them holds instead that nobody
  trains there
- **No order of its own.** Being told to pass the time one way, or to use a thing, was
  there already (S49, S60)
- **`Tedio`**, for the bar

Still open here:
- Nobody tires of the same pastime, or of the same thing
- Nothing is done together of their own accord but what is an exchange between two: that
  is S31
- Nothing shows over somebody who is bored
- Children are as bored as anybody

### S63 — Blows, theft, and what goes with what somebody is like (needs S48 and S60) — done
The user's words: "La parte agresiva, pegar, robar, acciones especiales que vayan con los
rasgos".

- **Things only somebody with a given trait can be told to do**, as data, beside what goes by
  what is felt (S48)
- **Stealing can be told**, as coming to blows can

Asked on 2026-10-09, and answered:
- **The four traits that were offered, and twenty more**: a bully who cows people, a charmer
  who gets round them, a gossip who worms things out of them and a clown who makes everybody
  laugh, and in the user's words "mete esos y unos 20 mas, 10 buenos y 10 malos mas". Which
  twenty was left to whoever builds it: they are listed here when they are built, to be put right
- **Stealing when told is from anybody, of what they carry, and from the `Almacén` and the
  shop as well.** Not the recommendation, which stopped at what somebody carries

What there is, of which what is seen of it is P63:
- **An order can be for whoever has a trait**, as data: `trait` on what can be done with
  somebody (`data/affect.json`). Nobody else is offered it or can be told it, and whoever
  has the trait needs to feel nothing in particular for it
- **Twenty-four traits, each with something only they can be told to do with somebody**:
  the four that were asked for, ten good ones and ten that are flaws, listed below. Each
  is an exchange between two (`data/social.json`) like any other
- **An exchange can be something done to somebody**, as data, beside what both come to
  feel: what whoever it was done to comes to feel for whoever did it, and the other way;
  what it does to the spirits and the needs of each; what each remembers of it, which is
  their side of it; and what is said of each while it goes on. Whoever went over to do it
  is the one doing it
- **Fourteen things an exchange can do besides**, each named in the data (`deeds`) and
  done by the game: have the news and a taste out of somebody, see to what ails them,
  teach them their job, ease what they hold against somebody or their fear of them, set
  them against somebody, give them a thing or have one off them, mend what they carry,
  have them give back what they stole, talk them out of their credit, hurt them, and
  have them leave what they were about
- **Stealing can be told** (`task:steal`): from the stores, from where the fund is kept,
  and from whoever carries something. From somebody it is the thing of theirs they carry
  that the thief would most like to have, or failing that the credit within reach, taken
  standing beside them: they see it. From the stores it is a thing that is nobody's, taken
  from the store or, where it holds nothing, from wherever its things are kept at hand;
  from the shop it is the fund's coin, or a thing where there is no coin
- **It is theft like any other**: it is on record, whoever sees it knows, and what follows
  from a theft follows (S5, S7, S28)
- **Who can be told to steal, and from whom, goes by what they have it in them to do**
  (`ItemSystem.leaning_to_steal`, which was there): greed and a grudge against whoever it
  is push towards it, feeling for others holds back, and some are that way whatever else
  they are. Whoever is past caring for hunger, thirst or sleep can be told to take from
  the stores
- **Whoever is talked into leaving what they were about is not called back by their
  shift**, which a pastime of their own is (S62): that is what it is for
- **The settlement that comes ready made has them**: each of the nine has one or two, and
  so do the four who come to the gate
- Domain event `deed_done`. Each exchange has its own `<exchange>_started`, as ever

The traits, and what each opens, to be put right:

| Trait | In the game | Only they can be told to | What it does |
|---|---|---|---|
| `bully`, a flaw | Matón | Intimidar | The other is left afraid of them, sore at them and shaken. It can come to blows |
| `charmer` | Labia | Camelar | The other warms to them: fonder, more trusting, more drawn |
| `gossip` | Chismoso | Sonsacar | They have out of the other the most striking thing they know, and one of their tastes |
| `clown` | Payaso | Hacer reír | The other's spirits lift and their nerves ease |
| `caring` | Buenas manos | Cuidar | The worst of what ails the other is a little better |
| `teacher` | Maestro | Enseñar | The other is an hour the better at their job |
| `peacemaker` | Mano izquierda | Poner paz | The other holds less against whoever they resent most |
| `listener` | Buen oyente | Escuchar | A good deal off the other's nerves and their want of company |
| `generous` | Generoso | Convidar | They give the other a thing of their own that they carry |
| `rousing` | Animoso | Arengar | The other's spirits lift, and they are less tired |
| `brave` | Valiente | Dar valor | The other is less afraid of whoever frightens them most |
| `upright` | Honrado | Hacer devolver | The other gives back what they stole |
| `handy` | Manitas | Arreglarle algo | The most worn thing the other carries is mended some |
| `affectionate` | Cariñoso | Mimar | Company and comfort for the other, who is the fonder for it |
| `swindler`, a flaw | Timador | Timar | They talk the other out of a little credit, and it is known |
| `schemer`, a flaw | Liante | Malmeter | The other is set against whoever they themselves resent most |
| `envious`, a flaw | Envidioso | Hacer de menos | The other is brought down, and sore at them. It can come to blows |
| `brute`, a flaw | Bruto | Zarandear | The other is hurt a little, afraid and sore. It can come to blows |
| `idler`, a flaw | Vago | Escaquearse | The other leaves what they were about and sits down to nothing |
| `grouch`, a flaw | Cascarrabias | Echar la bronca | The other is told off: a little afraid, a little sore. It can come to blows |
| `scrounger`, a flaw | Gorrón | Gorronear | They have something to eat or drink off the other |
| `tempter`, a flaw | Mala influencia | Liar para beber | Both go for a drink, whether the other cares to or not |
| `spiteful`, a flaw | Rencoroso | Remover lo pasado | Old things raked up: each is the sorer at the other. It can come to blows |
| `cold`, a flaw | Seco | Cortar en seco | The other is put off: less drawn to them, less fond |

Who has which: Marta `caring`, Raúl `bully` and `grouch`, Lucía `generous`, Tomás `brave` and
`cold`, Inés `gossip` and `handy`, Vera `listener` and `peacemaker`, Paco `clown`, Nuria
`charmer` and `scrounger`, Sergio `idler`; of those who come to the gate, Olga `teacher` and
`affectionate`, Hugo `swindler`, Carmen `brute`, Bruno `upright` and `rousing`. Nobody
begins with `schemer`, `envious`, `tempter` or `spiteful`: they are there for whoever the
player makes.

Decided without asking:
- **Which twenty**, their names, what each opens and what it does: the table above
- **The ten bad ones, and the bully, are flaws**, as the traits that were there say of
  themselves: a child of two who are kin takes the flaws of both
- **Nobody does any of it unasked.** The answer was what somebody can be told
- **Not anybody can be told to steal**, though anybody can be stolen from: what is told
  goes by what they are like and what they feel, as coming to blows does (S48). Somebody
  greedy, or with a grudge, or with a trait for it. Not somebody who feels for others
  and has nothing against anybody
- **From the stores it is always a thing, and from the shop the coin where there is one**
- **Which thing is not chosen**: the one they would most like to have
- **Taken off somebody standing beside them, it is seen**: there is no doing it unseen
- **A store that holds nothing is still the stores**: what the settlement holds is kept at
  hand in the pantries, the tank and the heaps, and it is taken from there
- **Coming to blows was already told by what is felt** (S48), and stays so. Of the traits,
  the brute lays hands on somebody, which hurts a little and no more
- **How much each does** is a first guess, in the data
- **Nobody has more than two traits**, as before: the creator lists all thirty, across the
  width of the screen
- **What an exchange does besides is the game's to do**, a small function to each, and the
  data's to name: a pack can give an exchange any of the fourteen, and cannot write a new one

Still open here:
- What only somebody can be told, marked as theirs in the wheel, was P63
- Nobody does what goes with their trait of their own accord
- A trait does not tell in what somebody wishes for (S61) nor in how they pass the time (S62)
- What each trait opens is not said where a resident is made
- The traits that were there, the thieving ones and the two for tastes, open nothing

### P63 — What is done, on screen (needs S60 to S63) — done
- The ring of a thing, wishes over heads, what weighs on somebody in their panel, and what
  only they can do in the wheel

What there is:
- **With somebody selected, a click on a thing opens the ring of what they can do with
  it** (S60), laid out about the thing: what it is mainly for first, then whatever else it
  offers, each with an icon of what it does for whoever does it, and `Ver`, the way to
  what there is to say of the thing. They are stopped to be told, as the wheel stops
  them, and what is picked is an order like any other. With nobody selected, or with
  nothing they could do with it, the click shows what there is to say of it, as it did
- **Everything there is something to do with can be clicked**, and not only what has
  something to say of itself: a bed, a table, the fire
- **Put down on a thing (P27), somebody still does what it is mainly for**, as was
  answered then. By a thing with nothing it is mainly for that they can do, a table, or
  the rope for somebody it has nothing left to teach, they are left beside it, nothing
  is set about, and its ring opens
- **Whoever wants something (S61) has a small bubble with something on their mind over
  their head.** Selected, and saying nothing, it is what they want that is over them: the
  picture of the thing, the face of whoever they want to be with, or what they feel like
  doing, in words
- **What they want is said in their panel**, under what they carry, before anything else
- **The name of the bar of their mood is a way in**: `Ánimo` turns the panel to what they
  want, what weighs on them right now, each need with the points of mood it takes and
  the heaviest first, and what they carry with them of what has happened, the latest
  first: in green with a `+` what lifted their spirits, and with a `-` what brought them
  down. `Volver`, or `Ánimo` again, turns it back
- **What weighs on their mood is what their mood goes by**: the panel and the simulation
  read it off the same place (`mood_strains`)
- **What only somebody can be told, for a trait of theirs (S63), wears a star at its
  corner in the wheel**, and says whose it is where the pointer rests on it: `solo por
  ser Matón`
- **Stealing has an icon of its own**, a mask (S63)

Decided without asking:
- **What lifts and what weighs is behind the bar of their mood and not under what they
  carry**: there is room there for a line or two, and the list wants the length of the
  panel
- **What weighs on them now is told beside what they remember**: a list of what has
  happened does not say why somebody is low who is only hungry
- **A need is worth a line from two points of mood**
- **Whoever is selected shows what they want and the others a mark**: nine bubbles with
  a picture in each would hide the map
- **A wish gives way to talk**: while they talk of something, that is what is over them
- **Being put down on a thing asks nothing where the thing is for something**, though
  S60 had it that it would go by the ring. Put down on their bed somebody sleeps, as
  was answered for P27, and what else a bed offers is a click away. Asking every time
  was built first: six modules of tests put somebody on a bed, the tank or a thing to
  train at to have them use it, which said how much is done that way, and it was undone
- **A click on a pantry or the tank with somebody selected opens the ring** and not what
  it holds, which is one press further, at `Ver`
- **The icon of each thing to do** goes by what it does: food, water, a moon for sleep,
  a cross for care, the weights for training, and a die for whatever is done for the
  sake of it

Still open here:
- Nothing shows over somebody who is bored
- What each trait opens is not said where a resident is made
- What has lifted their spirits goes back as far as they remember, and no further

### P66 — Armour cut to any body: a first look — done
Asked for on 2026-10-08, in plan mode: "investiga como podemos crear armaduras que se podamos
dibujar igual que todo pero se ajusten a los diferentes cuerpos por muy locos que sea, torso
hombreras casco pantalones etc". One batch of four:
- **Drawn over the plain figure**, on the doll's own two papers, with somewhere beside it to
  try it on. The recommendation
- **Everything bends** with the limb of rubber it is on. A helmet and a chest plate do not,
  as a head and a trunk do not. The recommendation
- **Besides a helmet, a torso, pauldrons and trousers: a cape or a pack, and a mask or
  goggles.** Boots, and bracers and gloves, were left unticked
- **A first look, and stop there** to be judged before who wears what is touched. The
  recommendation

What there is:
- **A piece is kept by where on the body it is and not where on the paper**
  (`graphics/tailor.py`): how far along its part, from one joint to the next, and how far
  from the skin. Laid over somebody it is as long as their part and as wide as they are
  drawn, behind and in front each by itself, so that a belly swells a plate in front only
- **Past the skin it is about as thick as it was drawn**: thinner on a thin body and thicker
  on a stout one, by the root of how many times as wide, and less where their body leaves it
  no room in the zone of the part
- **A head has no joints to go by**: a piece on it goes by the way from the middle of what
  is drawn, and by how far out that reaches each way, hair and all
- **Where a part ends in a round, the round stays one**; two parts that meet at a joint are
  measured as one there; and where nothing of a part is drawn nothing is worn on it
- **What comes of it is a drawing like any other**, laid over the body's own in memory and cut
  with it into one doll: it bends, turns, is mirrored and grows as the body does, and costs
  nothing more to show. Nobody's kept drawing is touched
- **Five places to wear something, as data** (`doll.wear` in `data/skeleton.json`): mask,
  helmet, torso, trousers and pauldrons, each with the parts it is drawn on
- **`Probador`, in `Dibujar`** (`scenes/garment_editor.py`): the doll editor's paper and
  tools, with only where the piece in hand is worn left light and nothing painted outside
  it. The other pieces show faintly under it. Beside the paper a resident wears every piece,
  moving; `<` and `>` try them on the next one. `Igual al otro lado` has the far side wear
  what was painted for the near one
- **`En el mapa`** keeps the pieces and has everybody on the map seen in them, one more cut
  in each frame. It is how they are shown and nothing else: no rule of the game, nothing
  saved with the settlement
- Pieces are kept in `illustrations/garments/<slot>/`, which belongs to a game being played

Decided without asking:
- **Hands and feet go bare**, as boots and gloves were left out. A slot is a line of data
- **A piece drawn for one side is copied to the other with a button**, and not by itself
- **The skin is taken a little wide**: as far out as the body goes anywhere within six
  pixels, so that a piece goes straight over a dent and over the round end of a part
- **Thickness follows width by its root**, between none of it and all of it. With none, a
  body drawn as a stick was lost in its trousers
- **Without numpy nobody is seen to wear anything**
- **The cape is not in this first look**: it wants a paper of its own and to be shown behind
  the body (P67)

Still open here:
- **Nobody has tried it with a mouse**: it was driven by scripted presses and looked at in
  pictures of the game, on the dolls kept in the folder and on bodies made up to be odd
- **A mask lands by the way from the middle of the head**: on a head with a snout the
  goggles sit on the snout. A point for the face in `Medidas`, as the neck has, would say
  where, if it is wanted
- **A helmet covers all the hair there is**, and is large on a head with a lot of it
- **On a body drawn right up to the edge of its zones a piece has no room past the skin**
  and loses the line round it
- **Inside a building nobody is seen in them**, nor in the family tree
- Cutting somebody with five pieces on takes about a fifth of a second, once

### S66 — Worn, piece by piece (needs P66) — planned
- **A thing that is worn says where** (a slot of `doll.wear`), one to a slot, and what is
  made at the watch as `Defensa` is one of them
- What is worn is the simulation's to say, and the map shows it in place of the switch (P66)

Still to settle, to be asked before it is built:
- Who decides what is worn: they themselves, the player from the wheel, or both
- How what each piece stops adds up, and which wears with a blow
- Whether a mask and a cape stop anything or are only looks
- Whether it comes off to sleep

### P67 — The whole wardrobe (needs P66 and S66) — planned
- **A cape or a pack**: a third paper, with the trunk of the figure to go by. All of it is one
  part hung from the spine, as a head is from the neck, shown behind the body and fitted to
  the back
- **What the watch comes to is drawn in `Probador`** when it is named, with a list to pick
  which piece it is. Its picture in a square comes of the drawing
- Pieces inside buildings, on the family tree and where manners are tried

### P36 — Letters as fine as the rest (needs P35) — planned
Answered with P35: all the text of the game goes to a smooth letter at the resolution of the
window, as a milestone of its own, because it touches every screen.

- One letter for the whole game, drawn at the resolution of the window
- Every measure of text the screens lay themselves out by goes on working: width, wrapping and
  cutting short
- The pixel font stays for a game with no window under its canvas

Still to settle, to be asked before it is built:
- Which letter: one that comes with the game as a file, so that it looks the same on any machine
- Whether sizes change with it, now that small text would be readable

## Later
- SQLite persistence
- Semantic/vector memory if the amount of narrative memory justifies it
