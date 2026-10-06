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
  hours with eight to fourteen things and some coin, asks half as much again as a thing is
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

Still open here:
- With nobody to sell to a caravan the fund runs dry in about a month: more is paid out in
  wages than comes back at the counter, and what is saved never comes back. From then on wages
  are paid as far as the day's takings go, to whoever is at work when they come in. Taxes are
  S28
- Whoever keeps the shop can never buy at it, so what they earn piles up: after ten weeks the
  shopkeeper holds two thirds of the coin there is
- Under barter nobody comes by anything of their own but by a present, a swap or a theft, so
  the shop moves little: whoever is kept takes nothing home
- Nobody minds going unpaid, and nobody minds someone who holds no job being fed for nothing
- What is handed over at the bar or the workbench under barter is on the shop's shelf at once,
  with nobody carrying it there, and so is what is bought from a caravan (S8)
- A caravan is not seen at the gate, and nobody goes to meet it. Residents do not deal with it
  unless the player puts it to them
- Nobody proposes a currency, or going back to barter, unasked
- A settlement with no shop has nowhere for its fund to be stolen from
- A thing sold to a caravan is sold as new, however worn
- Residents still never sell for coin: under a currency the counter only sells (S8)

### S24 — Substances (needs S20) — planned
- **A substance is a consumable like any other, as data**: an item with a `substance` property
  that says how it is taken, what it does and how likely it is to bring dependence. A pack
  brings one with no code of its own
- **Four ways of taking one**: swallowed, sniffed, injected or smoked
- **Three kinds of effect, each as data**: the good it does while it lasts; the harm of its own,
  then or afterwards; and what others make of it
- **Being seen is part of it.** Someone drunk or high is seen by whoever is near, as anything is
  (S3), and smoke reaches everyone in the room. Each takes it their own way, by their tastes in
  people (S20): some cannot stand a drunk, some mind the smoke, some mind neither. It moves what
  they feel for whoever it was, and what they know of them is passed on like any other fact
- **Dependence comes by chance**, each time one is taken, and the likelier the more of a habit
  it is. Whoever depends on something goes looking for it, and is the worse for going without:
  in mood, in nerves and at work. With long enough without, it passes
- Being under something, and depending on it, are states of a resident's own, and are saved
- What the bar serves is the first of them
- Taking one, being seen at it and coming to depend on it are each a domain event

Done when: the same drink leaves one resident dependent and another not, and the same way when
the same seed is run again; someone dependent is seen to go after it and to work worse without
it; two residents who watch the same drunk feel differently about them afterwards; smoke
indoors is minded by those in the room and by nobody outside it; and ten weeks pass with three
seeds without the whole settlement ending up dependent.

Tests it is not done without: each of the three kinds of effect; dependence by chance and from
the project RNG; going without; a pack's substance working with no code; a witness who minds
and one who does not; and a save from before, in which nobody is under anything.

Still to settle:
- Which substances the game comes with besides drink, and where they come from: made in the
  settlement, brought back from outside, left by caravans
- Whether too much of one can kill, and whether the medic treats dependence
- Whether the player is given a say when someone is about to take to something

### S25 — Families (needs S9) — planned
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
- Romance and sex stay between adults, as they are (S9), and are never between close kin
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
no romance or sex with anyone under age, whatever their libido, or between close kin; libido
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

Still to settle:
- What date a settlement begins on
- How fast the chance of dying of old age grows after eighty
- What somebody in a save from before has for sex and gender
- Whether libido is fixed like the rest of a way of being, or rises and falls
- What a child takes from their parents: way of being, traits, tastes, looks
- Whether those who come to the gate come with kin, and whether anyone there already is kin to
  anyone

### P25 — Coin, smoke and kin on screen (needs S23 to S25) — planned
- The currency named and drawn in the game, and seen wherever something is paid
- The fund in the bar, beside what the settlement has in food and scrap
- Putting a currency, or going back to barter, to the residents, and how each of them answered
- A caravan seen at the gate, and dealing with it: what it brings and asks, what the settlement
  has that is nobody's, and putting a sale to a resident. Until then S23 can only be played by
  commands
- A substance seen to be taken, each of the four ways, and seen on whoever is under it: how
  they walk, the smoke round them
- A resident's family in their panel, and the tree of it on a screen of its own
- **A child is drawn when they are born, as the adult they will be**: the same screen, the same
  paper and the same measures as anyone (P17, P19)
- **Until they are ten, what is seen of a child is their head and a blanket**: on the back of
  whoever carries them, and in the bed, on the table or on the ground where they are put down
- **From ten until they are grown the body is shown smaller and the head is not**: the one
  drawing does for every age, and the body comes up to its drawn size as they grow
- **A child nobody has drawn has a look the game comes with for children**, one for all of them
- Sex, gender, who they are drawn to and the slider for libido where the first resident is made
- The date by the clock, and a birthday seen when it comes round

Still to settle:
- How small the body of a ten-year-old is, and whether it grows year by year or in a few steps

### S26 — Who is in charge (needs S20) — planned
Politics comes in four milestones, S26 to S29, and a screen, P26. It has a module of its own,
`simulation/politics/`: `government.py`, `leadership.py`, `voting.py`, `law.py`, `punishment.py`,
`legitimacy.py`, `unrest.py`, `faction.py` and `political_event.py`.

What holds for all four:
- The player is not the mayor and is nobody in the settlement. They propose, advise and
  influence, and never govern
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

Still to settle:
- Which kind the ready-made settlement starts under, or whether it chooses on its first day
- Whether loyalty is to the person or to the place they hold, and so what is left of it for
  the next leader
- Where a resident's political profile starts from: their personality and traits, and whether a
  leaning of their own on top, made from the seed as tastes are (S19)

### S27 — Proposals and votes (needs S26) — planned
- **The player proposes and the settlement decides.** A proposal goes into the process of the
  government in force, to the leader, the council or a vote as its kind says, and comes out
  accepted, changed or rejected. Only then does anything follow. Nothing the player proposes is
  simply done, unless the government in force allows it
- **What can be proposed**, as data: rationing food, changing a law, punishing a resident (S28),
  calling an election, throwing somebody out, declaring property common, changing how the
  settlement trades (S23). Building something, such as an infirmary, is proposed this way once
  there is building (S16), and not before
- **A vote is yes, no or an abstention, and is worked out for each voter**: what they think of
  the proposal and of the people in it, what they hold, their fear, their trust in the
  government, what they stand to gain or lose, and what they remember. Somebody may vote down
  what would do them good because they hate the leader, because it helps an enemy, because it
  goes against what they hold, or for fear of what follows
- **The player may work on residents before a vote**, and cannot cast it for them
- **The player's influence is a layer of its own**: for each resident, trust in the player,
  resistance to the player, and how much they lean on the player's advice. A proposal weighs
  differently with each of them, and a resident may take the advice, change it, ignore it or do
  the opposite. It builds on advice (S4) and on the taste for being told what to do (S20)
- **Elections**, under the governments that have them. Who stands goes by reputation,
  relationships, leadership, charisma, how many are behind them, and factions (S29). A result
  leaves memories and consequences: a loser who resents it, a winner with legitimacy, talk of
  fraud, followers let down
- **What politics does is remembered**: "El alcalde encarceló a mi hermano", "Marta votó contra
  mi expulsión", "El jugador impulsó una elección", "El consejo ignoró la escasez". Such
  memories weigh on later votes, on relationships and on support
- Proposals still pending, the history of elections and political memories are saved

Done when: the same proposal is voted for by one resident and against by another, each for
reasons that can be read back from who they are; a proposal the player makes is turned down, and
nothing of it happens; an election is held, its winner leads, and the result is still there after
saving and loading; and those who took part remember it.

Tests it is not done without: a vote that follows the voter's own opinion; a proposal of the
player's rejected; an election whose result is kept; and political memories.

### S28 — Laws and punishment (needs S27, and S23 to S25) — planned
- **Laws as data** (`data/laws.json`): `rationing`, `private_property`, `communal_property`,
  `weapon_restrictions`, `drug_rules`, `curfew`, `theft_penalties`, `election_rules`. A law
  changes what residents do and what follows from what they do. It is never only words.
  `drug_rules` says which substances (S24) may be had and taken, and where. `pregnancy_work`
  says whether whoever is carrying a child keeps their post (S25)
- **A scale of punishments, as data** (`data/punishments.json`): `warning`, `fine`,
  `confiscation`, `community_service`, `prison`, `public_stocks`, `exile`, `corporal_punishment`
  and `execution`
- **A punishment needs its place.** A jail is a building, and the stocks, a gallows and a
  guillotine are things put down in Urbanismo, each drawn as everything put down is (P15, P17).
  Without a jail nobody is locked up, without stocks nobody is put in them, and without a
  gallows or a guillotine nobody is put to death
- **A fine goes into the common fund** (S23), in coin or, under barter, in things
- **Exile is walking out for good**: whoever is exiled goes to the gate and through it, and does
  not come back. What depended on them is let go of as on a death (S7), with no grave
- **A punishment moves fear, legitimacy, unrest, support, resentment and relationships, by how
  things stand.** Putting to death a killer whom most hate may raise support. Putting to death
  someone held to be innocent sinks legitimacy and sends unrest up
- **The harsh ones are political events of the first order**, and as with anything that cannot be
  undone, the player is given a say before they are carried out
- **Nothing gory is shown.** What happened is recorded with its consequences, with no detailed
  animation of it
- **A trial in six steps**: accusation, evidence, witnesses, defence, verdict, punishment. It
  goes by memory, knowledge, witnesses, rumours and relationships, and never by what the world
  knows: each resident judges, votes and reacts on what they believe they know
- **A punishment in public is a political event that records** who was condemned, for what, to
  what, who was there, which of them were kin (S25) or friends, how each took it and what
  memories it left
- **Each takes it their own way**: approval, fear, anger, grief or indifference. There is never
  one consequence dealt out the same to everybody
- **A child can be tried and punished like anyone** (S25), and it costs a government far more:
  in legitimacy, in support and in unrest, by each of those who see it or come to hear of it.
  So does a law or a post that puts children to work
- Laws in force and the history of punishments are saved

Done when: a law in force changes what residents are seen to do over a week; a theft that was
witnessed goes to trial and one that nobody saw cannot; nobody is sentenced to what the
settlement has no place for; someone exiled is gone from the map, the posts and the beds, and
is still in the memories of those they left; the same punishment raises legitimacy when those
watching hold the condemned guilty and sinks it when they hold them innocent; and after a harsh
one the kin of the condemned and those who wanted it remember it differently.

Tests it is not done without: legitimacy after a just punishment, and its fall after an unjust
one; a fine reaching the fund; exile removing a resident without breaking what depended on
them; and no prison without a jail.

Still to settle:
- What a day locked up is, and how a sentence is counted
- Whether someone exiled is ever heard of or met again, outside or at the gate (S10, S11)

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
- A government entry in the menu: its kind, who leads, who sits on the council, the laws in force
- The choosing of a government, when the third resident comes, as something seen and advised on
- The jail, the stocks, the gallows and the guillotine, in Urbanismo and in their editors
- Where a proposal is made, and where it is seen to go: who has it, how each vote went, what
  came of it
- An election, a trial and a public punishment seen as they happen, with nothing gory
- Trouble on the map: who has stopped work, who is out protesting

Still to settle:
- How much of the settlement's measures the player is shown, and whether as figures or as the
  mood of the place. What each resident holds is found out, as their tastes are, and not read
  off a panel

## Later
- SQLite persistence
- Semantic/vector memory if the amount of narrative memory justifies it
