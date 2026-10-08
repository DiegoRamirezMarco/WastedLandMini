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
  `SentenceCommand` and `SetPrisonRationCommand`. None has a screen until P26

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
  of what there is a place for, and what prisoners are given to eat and drink. Until then
  the three are commands (S28)
- Somebody exiled seen at the gate when they come back, as a stranger is (P25)
- Trouble on the map: who has stopped work, who is out protesting

Still to settle:
- How much of the settlement's measures the player is shown, and whether as figures or as the
  mood of the place. What each resident holds is found out, as their tastes are, and not read
  off a panel
- Whether the player is shown how a vote is going to go before it is held, and what each
  resident makes of the player, or has to find both out

### P27 — Picked up and put down (needs P10) — planned
The user's idea: residents can be dragged and dropped, and where one is dropped is what they do.

- **A resident is picked up with the mouse on the map and carried with the pointer**, their
  body hanging from it as a paper doll's would (P10), and put down wherever the button is let go
- **What they are dropped on is what they set about**, as far as it can be done:
  - on a place of work, they work at it
  - on another resident, the two have something to do with each other
  - on a bed, they lie down and sleep
  - on whatever else is used, they use it: the pot or the pantry to eat, the tank to drink,
    the bar, the clinic's bed, a seat, the study desk, the radio
  - on bare ground, they are simply there now
- **What a drop would do is shown before the button is let go**: the thing under the pointer
  lights up and says what will come of it, or that nothing will
- The simulation gets it as a command like any other, by stable IDs, so that it runs headless
  and can be tested without a screen: who, and on what or on whom
- A drop that cannot be acted on puts them down and nothing else: a post that is not theirs to
  take, a bed that is somebody else's, somebody who is asleep or out of the settlement

Still to settle, to be asked before it is built:
- **Whether a drop is an order or a nudge.** Everywhere else residents decide for themselves and
  the player advises (S4). Either a drop is the one place where the player's hand settles it, or
  it puts the thing in front of them and they do it unless they have a strong reason not to
- What two residents do when one is dropped on the other: what they would have done anyway by
  what they feel for each other, or something the player picks as they let go
- Whether dropping somebody on a place of work gives them the post, or only has them lend a
  hand there this once
- Whether they are where they are dropped at once, or walk there from where they were
- Whether time stops while somebody is in the air
- What being carried about is to them: nothing, or something that tells on their nerves and on
  what they make of being told what to do (S20)
- Whether a child's bundle can be picked up and handed to somebody the same way (S25)

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
  way, and is not built
- A resident cannot be told to do anything about a thing they loathe, to give somebody
  something, or to work out of hours

### P30 — Affecting, and breaking things up, on screen (needs S36 and S37) — done
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
the fire and at the radio, eating, and drinking are here. On a stool if there is one is not:
which seat is whose is for the simulation to say, and is a milestone of its own (S44).
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
- They sit on the ground, on the spot they stand on, stool or no stool, and facing whichever
  way they last walked: not the fire, nor each other
- Whoever sits is seen to drop into it and to rise out of it by their springs alone: there is
  no sitting down as there is a lying down
- Drinking, they sit with their hands empty: there is no clip of drinking
- Seen from the front the small bodies shown without a window do not sit at all
- Nothing of this has been seen on a real window by whoever made it

### S44 — A seat of one's own (needs P50) — planned
Asked with P47, and marked: whoever is at something done sitting down sits on a stool if
there is one free beside it, and on the ground if not.
- A stool is nobody's to use today: it is furniture that stands there. Whoever goes to rest,
  eat or drink takes a free one within reach of what they are using, and has it until they
  are done; two cannot have the same
- Which seat is whose is the simulation's to say and to save, not the map's to guess: it
  goes with the activity
- On a stool they sit as on a chair, at its height, and not their own way of sitting on the
  ground: one clip more

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
