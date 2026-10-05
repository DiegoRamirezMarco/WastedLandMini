# Simulation Notes

The simulation runs without Pygame. Important state changes emit domain events. Residents do not gain omniscient knowledge.

## Time

- `SimulationWorld.step(minutes)` advances the world one game minute at a time. Every minute is one tick.
- The game shell turns real time into game minutes (`GAME_MINUTES_PER_REAL_SECOND` in `settings.py`,
  multiplied by the clock speed) and sends them through `AdvanceTimeCommand`.
- Scenes change the simulation only through commands in `simulation/commands.py`.

## The settlement

- A map is a grid of terrain IDs plus rooms, placed objects and spawn points (`data/maps/*.json`).
- `data/terrain.json` says which terrain can be walked on and which blocks sight.
- The settlement is outdoors: open ground, a fence around it, and shacks whose walls enclose a
  floor and are entered through a door. Rooms name those interiors and the open areas; a room
  that is a building is marked `roofed`.
- `data/interactables.json` defines object kinds: size in tiles, whether they block movement, and
  optionally a `use`.
- A `use` gives an action name, a duration, need changes per minute, and optionally an item whose
  effects apply when the use ends. `position` is `adjacent` (stand next to it) or `on` (a bed).
  `capacity` is how many residents can use it at once.

## What a resident does each minute

1. Needs rise (`simulation/residents/needs.py`). Asleep, hunger and loneliness grow at half pace.
2. With no activity, `RoutineSystem` scores every free usable object and picks the best reachable one:
   - each need the use would lower counts as `(need / 100)²`, weighted by personality;
   - a use with `preferred_hours` counts double inside that window and a fifth outside it,
     though the penalty fades as the need grows desperate, so the exhausted nap by day;
   - food is judged by how much it relieves, so a cooked meal is worth a longer walk than a tin;
   - bed loses its appeal with hunger: nobody settles down to sleep on an empty stomach;
   - distance costs a little, and a small random amount from the project RNG breaks ties;
   - wandering has a low constant score, so it wins when nothing is pressing.
3. `ActivitySystem` walks the resident along the path (2 tiles per minute), then applies the use
   until its minutes run out or the needs it lowers reach zero. A use with `until` ends when
   that one need reaches zero: sleep eases stress too, but only tiredness decides when to wake.
   Any other need reaching 85 cuts a long restful use short: hunger wakes a sleeper.

Starting a use emits an `activity_started` event with low importance.

## Social life

- Talking is one more thing a resident can choose. They walk to someone who is standing still and
  not busy (wandering, or using something marked `interruptible`, such as the campfire) and stand
  beside them. Sleepers and people eating are never interrupted.
- The wish to talk grows with the social need and with how much the resident likes the other
  person. Resentment puts off the meek and draws the aggressive towards a confrontation.
- On arrival the exchange becomes a chat or an argument. Arguments are likelier with shared
  resentment, hot tempers, and when either one is very hungry, tired or stressed.
- `data/social.json` defines each kind of exchange: length, importance, need changes per minute,
  base relationship changes, event text, dialogue lines and the memory it leaves.
- When it ends, each resident applies **their own** side: their feelings about the other change
  according to both personalities, and they keep their own memory of it. So A -> B and B -> A
  drift apart, and nobody remembers an exchange they were not part of.
- Affection and trust grow more slowly the higher they already are.
- After an argument, neither seeks the other out for six game hours unless a crisis drives them.
  Without this a feud feeds itself until it swamps everything else.

Starting an exchange emits `chat_started` or `argument_started` with both participants and the
room. An argument's importance rises with the resentment between the two.

## Work

- `data/jobs.json` defines each job: the kind of object that is its post, its shifts, the phrase
  for starting it, need changes while working, and optionally what it produces.
- A resident has at most one job and one post, a particular object of that kind. During a shift,
  going to work is one more thing they can choose. It beats idling and mild wants, and gives way to
  a pressing bodily need: nobody starts a shift starving.
- At the post they work until the shift ends. Hunger or exhaustion at 85 sends them off to see to
  it, and they come back if the shift is still on. Loneliness never does.
- **Production.** Every so many minutes of work makes one unit of an item, into the post itself or
  into the emptiest container of a given kind, up to a stock limit. A rule can require one unit of
  raw material from another kind of container: the cook turns raw food from the pantries into stew
  in the pot. With no raw material, or a full pot, nothing is made.
- **Staffed places.** A use with `staffed_by` exists only while someone with that job is on duty.
  The bar serves nobody when the bartender is away, and turns away whoever arrives too late.
- **Watch.** A job's `sight_bonus` lets its worker see further while on duty, so the guard witnesses
  what others would miss.
- Workers can be approached for a chat if their job is `interruptible`, and go back to work after.
- Nothing arrives from outside: the settlement eats what its farmers grow and its cook prepares.

## Health, fights and death

- A resident's health is 100 minus the severity of their injuries. `data/injuries.json` defines
  each kind and how fast it mends: on their feet, lying down (twice as fast), or in a clinic bed
  while the medic is on duty (fastest).
- The hurt look for a clinic bed, the more so the worse they are, and get up once recovered or
  when hunger or exhaustion insists. Below 40 health nobody works.
- **A fight never starts outright.** After an argument a resident may square up to the other; how
  likely depends on bad blood, temper and rashness against fear and empathy. That opens a short
  decision, like any crisis, and the player can step in. Only if the resident then chooses to
  fight do they go after the other.
- A fight is an exchange with a `damage` range. Each side is hurt by what the other deals: more
  from the aggressive and the healthy, and multiplied by the best weapon they carry (an item's
  `damage` property). A blade cuts, a heavy blow breaks something, the rest are bruises.
- **Death.** At 0 health a resident dies. They are removed from the living and recorded in
  `world.deaths`; a grave appears on the map's next free plot; what they owned becomes everyone's
  and what they carried is put in the nearest container; decisions and activities that involved
  them end; their post stands empty. The death is a fact: those who see it or hear of it turn on
  the killer and grieve in proportion to how fond they were of the dead.

## Things

- An item is an instance of a definition, with a stable ID, a quantity and an owner (a resident, or
  nobody for shared things). It is always in exactly one inventory: a resident's or a container's.
- Containers are objects marked `container` (pantries and crates). A map lists what they hold when
  a settlement starts (`stock`) and what arrives each day (`supplies`).
- **Food is real.** A use with `consumes` takes one unit of that category out of the object's own
  contents when the resident arrives, shared or their own, the one they would enjoy most. With
  nothing to take, the pantry is not worth the walk; finding bare shelves is reported once a day.
- **Belongings.** A resident uses their own things, carried or kept in a container, when the
  item's effects would help: food is eaten and used up, anything else is kept.
- **Worth** is personal: base value times the multiplier of any trait whose tags fit the item.
- **Gifts and swaps** happen at the end of a friendly exchange. Someone fond enough and not too
  grasping may give away something they carry; otherwise two residents swap one item each if one
  gains by it and the other does not lose.
- **Theft.** A resident tempted enough takes someone else's thing from a container that nobody
  can see at that moment. Temptation grows with the item's worth to them, their greed and their
  resentment of the owner, and shrinks with empathy. The item changes hands but not owner.
  The theft is a fact about thief and victim; the thief knows it and never volunteers it.
- **Finding out.** Whoever sees it learns it. The owner reacts only on learning who did it, by
  seeing it or being told. An owner who merely sees the empty spot knows something is missing,
  and is upset, but not who to blame.
- Talking things out after a crisis gives stolen things back.

## Who knows what

- An event can be recorded as a **fact**. The world keeps every fact; a resident only has a
  **belief** about the ones they learned, with a credibility and how they learned it.
- **Participants** know it. **Witnesses** are residents who are awake (not using something marked
  `unaware`, such as a bed), within `sight_range` tiles and with nothing opaque in between. Walls
  and doors are opaque (`data/terrain.json`), so what happens inside a shack stays inside.
- At the end of a friendly exchange a resident may pass on the most striking fact they know that
  the other does not. That is a **rumor**: the listener's credibility is the teller's, reduced, and
  higher the more the listener trusts the teller. A rumor too weak to believe is ignored.
- Learning a fact is what makes a resident react (`reactions` in `data/events.json`). Someone who
  learns of an argument blames whichever of the two they like less, or both a little, in
  proportion to credibility. Nobody reacts to something they have not learned, and hearing it
  again does not make them react twice.

## Crises and advice

- A resident who resents someone enough, and is stressed or hot-tempered enough, reaches a
  **crisis** instead of planning their next activity. They stop to stew and a **decision** opens.
- A decision has a window in game minutes. Within it the player may pick one piece of advice
  through `ChooseOptionCommand`. When the window closes the resident decides alone.
- `data/decisions.json` lists the possible **outcomes** and how each is scored from the resident's
  anger, personality, stress and feelings. Advice adds to or subtracts from those scores, scaled
  down by impulsiveness. The resident does whichever outcome scores highest: advice never picks
  the outcome directly.
- An outcome can change needs and feelings, leave a memory, and send the resident after the other
  person for a particular exchange. Someone who has made up their mind follows the other around
  and interrupts whatever they are doing, sleep included.
- Nobody enters a crisis while very hungry or tired: the body comes first.
- A resident can have one crisis per cooldown period. Being drawn into an exchange while stewing
  cancels the pending decision.
- Every event above the ambient band is appended to `world.history`, which is saved.

## Determinism

All randomness comes from `SimulationRNG`, and its state is saved. The same seed gives the same
event log, and a world saved mid-activity continues exactly as if it had never been saved. Both are
covered by tests. Player advice is part of the input: the same advice at the same minute gives
the same history.
