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

1. Needs rise (`simulation/residents/needs.py`). Asleep, hunger, thirst and loneliness grow at half pace.
   Mood drifts separately from stress: bad needs and wounds pull it down over time, good days let
   it recover.
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
   Any other bodily need reaching 85 cuts a long restful use short: hunger or thirst wakes a sleeper.

Starting a use emits an `activity_started` event with low importance. Eating emits the more
specific `meal_started` event so presentation can animate and sound the meal without owning it.

## Social life

- Talking is one more thing a resident can choose. They walk to someone who is standing still and
  not busy (wandering, or using something marked `interruptible`, such as the campfire) and stand
  beside them. Sleepers and people eating are never interrupted.
- The wish to talk grows with the social need and with how much the resident likes the other
  person. Resentment puts off the meek and draws the aggressive towards a confrontation.
- On arrival the exchange becomes a chat or an argument. Arguments are likelier with shared
  resentment, hot tempers, low mood, and when either one is very hungry, tired or stressed.
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
- **Production.** Every so many minutes of work makes one unit of an item, up to a stock limit.
  It stays in the post itself (the stew in the pot) or in the worker's hands (the vegetables).
- **Carrying.** Nothing appears where it is used. A worker whose hands are full walks to the
  emptiest container of the receiving kind that has room and leaves the load there; whatever they
  still carry when the shift ends is handed in then. A job that needs raw material sends its
  worker to fetch a load from the container with most of it: the cook walks to a pantry for what
  goes in the pot, and cooks from what they brought. With nothing to fetch, or a full pot, they
  stay at the post and nothing is made. What is being carried belongs to nobody and is nobody's
  to eat, give or steal; someone who changes jobs puts it down in the nearest container.
- **Tools.** A job can name a kind of tool by tag. A worker who has a working one on them works
  that much faster, and each unit made wears it.
- **Mood.** Low mood slows productive work. It is not a need to be filled directly, but a slow
  state that follows what a resident has been living through.
- **Staffed places.** A use with `staffed_by` exists only while someone with that job is on duty.
  The bar serves nobody when the bartender is away, and turns away whoever arrives too late.
- **Watch.** A job's `sight_bonus` lets its worker see further while on duty, so the guard witnesses
  what others would miss.
- Workers can be approached for a chat if their job is `interruptible`, and go back to work after.
- No food arrives from outside by itself: the settlement eats what its farmers grow and its cook
  prepares. What does come in is whatever a scavenger brings back (see Beyond the fence).
- **Days off.** A resident can have one day of the week on which they do not work. Their post
  simply stands empty that day: no stew if it is the cook, a shut bar if it is the bartender.

## Beyond the fence

- **The job.** A job with an `expedition` is done outside. Its post is only where the worker
  leaves from: on reaching it during the shift they set out, once a day, and are gone for hours.
  Nobody sets out with hunger or tiredness half way up: they see to it first.
- **Out there** a resident is away. They are not on the map, they witness nothing, and nobody can
  walk up to them, not even someone who has made up their mind to. They are paid as on any shift,
  and hunger grows at half pace: they eat as they go from what they took.
- **Coming back.** At the end of the trip they are at the cart again with what they found in
  their hands, so many things drawn from the table in `data/expeditions.json`, the commonest
  oftenest. Things from a pack that is not installed are never found. With the trip's `danger` as
  the chance, they come back hurt.
- **Putting it away.** What was found is carried to where it goes before anything else: the first
  rule in `deliveries` that fits, and whose kind of container the settlement has, says where.
  Scrap goes to a scrap pile; the rest goes on the shop's counter, where it is sold. Apart from
  a passing caravan, nothing reaches the shop any other way. A settlement with no shop or scrap
  pile yet puts food in a pantry and everything else in a crate.
- **A risky find.** Some trips come on something that promises more and looks dangerous. That is
  a decision, and the player may advise, but the resident is not stopped by it: they are still out
  there, and they do not come home until it is settled. Going for it means more finds, more danger
  and a later return; turning back means half the finds and an early one. The bold and the
  grasping go for it unless talked out of it.
- **Repairs take scrap.** A use that `repairs` can name a `material`: each repair uses up one
  such thing from a container of the kind given, and with none there is no repairing.

## What the settlement lives on

- **Water.** `thirst` is a bodily need like hunger. Residents drink from the water tank, consuming
  shared `water` items. Drawing it is a job, `water_carrier`, worked at the tank as the garden is
  worked at its plots; a morning's shift is about a day's water for everybody. The post stands
  empty when a settlement starts and is offered round like any vacancy. The scavenger may bring
  a little more back, hauled to the tank by the same delivery rules as every other find.
- **Going without.** A need of the body only comes before sleep and work if something can be
  done about it: something the resident carries, or somewhere open, within their means and not
  empty. With no water anywhere, thirst keeps nobody from their bed or their post, and the
  settlement is told once a day (`no_water`, `no_food`). An injury kind with `from_need` then
  sets in for whoever has that need at its worst: it grows for as long as the need stays there,
  mends once it is answered, and kills in the end. Thirst does it in a few days, hunger in a week.
- **Energy.** Generator fuel is kept in a generator container. When night begins, the generator
  burns one unit. Lamps of kind `lamp` only light the map while fuel remains, and radios give no
  warning without power.
- **Mood.** Mood is saved on each resident. Memories and decisions can nudge it, and the minute
  to minute state of the body pulls it slowly up or down. Low mood makes arguments more likely and
  productive work slower.

## What comes from outside

- **World events** are defined in `data/world_events.json`: how likely each is on a day it can
  happen, the hours it keeps to, and how long before it can come again. They are rolled once an
  hour with a random generator of their own, so whether one happens never changes what the
  residents would otherwise have done. Nothing happens on a settlement's first day.
- **Warning.** An event with `lead_hours` is settled that many hours before it comes, and is on
  its way in between. That it is coming is true of the world and known to nobody, until someone
  listens to a radio. If by its hour it can no longer happen, it comes to nothing.
- **The radio.** Listening to the settlement's radio, or to a working radio of one's own, gives
  word of whatever is on its way: what, and for what hour. The first to hear a bulletin makes it a
  fact. Those in sight hear it too, later listeners hear the same, and anyone who knows it may
  pass it on like any other news, but only until its hour has come: after that it is not news.
- **Heeding it.** Whoever is about to leave on a trip listens to the radio first, once a day.
  If they know of bad weather that would catch them out, by having heard it or been told, they
  stay in that day. They go by what they know: unwarned, they set out, and a storm that catches
  someone outside makes them that much likelier to come back hurt.
- **A stranger at the gate.** Someone from the list of newcomers asks to stay. They only come
  while there is a bed for them and while whoever keeps the gate is on duty. It is that resident's
  decision, and the player may advise: the kind open the gate, the gruff shut it. Let in, the
  stranger becomes a resident on the spot, hungry and tired and with nothing. Turned away, they
  never come back. If the settlement has no gatekeeper at all, as one of two or three has not,
  whoever has been there longest among those in and awake goes to the gate and decides. If
  nobody is in a state to, they knock, nobody answers, and they may try again another day.
- **Looking for work.** Someone newly arrived looks for a job without waiting to be asked: the
  one most missed that has a free post. It is put to them as any job offer is, and they take it
  unless they are talked out of it.
- **A caravan** leaves a few things on the shop's counter, drawn from its own list.
- **A storm** lasts some hours. While it does, work in the open stops and whoever does it leaves
  their post, nobody sets out on a trip, and anyone not under a roof grows more stressed by the
  minute. So people get out of it: taking shelter is one more thing a resident can choose, ahead
  of anything but work under a roof and a real need. They walk to the nearest free spot under a
  roof and wait there, free to talk, until it passes. Nobody who is in the dry strolls out.
- **Raiders** come by night, and give warning like a storm does. With nobody at the gate they
  walk in and take a share of everything that is everyone's in the kinds of container they go
  for; what belongs to someone is left. If whoever keeps the gate is at their post, it is theirs
  to decide and the player's to advise: stand their ground, and the raiders leave with nothing
  but may leave a wound, less likely on someone armed; or step aside, and they help themselves.
  Those who learn that someone drove raiders off think the better of them.
- **The night watch.** A job can keep watch for a kind of event. Its worker goes to hear the
  evening's bulletin, and if they know such an event is on its way they stay at their post until
  an hour after it is due, whatever their shift. It goes by what they know: unwarned, they go to
  bed, and the gate stands empty.
- **Vermin** get into the pantries by night and eat a share of the food that is everyone's.

## Wear, repairs and credits

- **Wear.** An item with a `wear` property loses that much condition each time it is used: a tool
  for each unit it helps make, a weapon for each fight, a radio each time it is listened to. At 0
  it is broken and does nothing: no faster work, no harder blow, no comfort. Something too worn to
  put back is kept on its owner, to have it seen to.
- **Repairs.** A use with `repairs` mends a worn thing its owner brings, so much condition a
  minute, while the job it is `staffed_by` has someone on duty. It stops if they leave.
- **Credits.** Every minute on duty, or loading and unloading for the job, earns a resident a
  share of the hourly wage (`data/economy.json`, or the job's own `wage`). A use with a `price`
  takes that many credits when it starts, and is not even considered by someone who cannot pay.
  A drink at the bar and a repair at the workbench both cost.
- **The shop.** A use with `sells` is buying one unit of something kept in that object, while its
  keeper is on duty. A thing costs its base value times the settlement's price factor, and more
  the fewer are left. What a resident wants to buy:
  - a tool for their own job when they carry none, above anything else;
  - a weapon, if they are afraid enough of someone and carry none;
  - otherwise whatever would do them most good right now for its price, unless they already own
    one, or two units if it is food.
  What is bought becomes the buyer's and goes with them.

## Who does what

- A job with fewer people than it `needed`, and a post standing free, has a **vacancy**. Days off
  do not count. After `vacancy_notice_hours` it is announced once, and from then on it is offered
  round.
- **Who is asked.** Those with no job first, then those whose own job has people to spare, then
  those whose job has a lower `priority`, least important first. Nobody is asked to leave a job
  that matters as much as the vacant one. One resident is asked at a time, a few hours apart.
- **The offer** is a decision like any crisis: the resident stops to think, the player may advise,
  and the outcome with the highest score wins. Taking the job grows more likely the longer it has
  been vacant, for those with nothing to do, and with empathy and courage; greed argues for
  staying put. So a cook who dies is replaced within a day or two, and the bar may then stand
  empty instead.
- **Suggestions.** `SuggestJobCommand` puts a job with a free post to a resident on the player's
  word. They weigh it at once with the advice it comes with, and may still say no. The same
  resident cannot be pressed again until the offer's cooldown has passed.
- Taking a job gives the first free post of its kind, and ends any shift or errand under way.

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
  from the aggressive and the healthy, and multiplied by the best working weapon they carry (an
  item's `damage` property). A blade cuts, a heavy blow breaks something, the rest are bruises.
- **Limbs.** `data/body.json` lists the limbs a resident can lose for good. A single injury of a
  kind that `severs_from` a given severity, such as a bad cut, takes one off with the chance its
  kind gives; which one is drawn from those they still have. The loss is the `limb_lost` event
  instead of `injured`, and a fact like any other: those who saw it know. The wound mends as it
  would have; the limb does not come back. `Resident.lost_limbs` holds the IDs. Each limb names
  what is left of the pace of its owner's work (`work_pace`) and of their walk (`walk_pace`): a
  one-armed farmer grows less in a shift, and a one-legged resident covers one tile a minute.
  A fight and a raid are both preceded by a decision, so the player always had a say before
  anyone could be maimed.
- **Death.** At 0 health a resident dies. They are removed from the living and recorded in
  `world.deaths`; a grave appears on the map's next free plot; what they owned becomes everyone's
  and what they carried is put in the nearest container; decisions and activities that involved
  them end; their post stands empty until someone takes it (see Who does what). The death is a fact: those who see it or hear of it turn on
  the killer and grieve in proportion to how fond they were of the dead.

## Things

- An item is an instance of a definition, with a stable ID, a quantity and an owner (a resident, or
  nobody for shared things). It is always in exactly one inventory: a resident's or a container's.
- Containers are objects marked `container` (pantries and crates). A map lists what they hold when
  a settlement starts (`stock`) and what arrives each day (`supplies`).
- **Food is real.** A use with `consumes` takes one unit of that category out of the object's own
  contents when the resident arrives, shared or their own, the one they would enjoy most. With
  nothing to take, the pantry is not worth the walk. Arriving to find it empty is a wasted trip;
  it is reported, once a day, only when there is nothing to eat anywhere else either.
- **Belongings.** A resident uses their own things, carried or kept in a container, when the
  item's effects would help: food is eaten and used up, anything else is kept.
- **Worth** is personal: base value, more or less by how much they like the thing, more if it
  answers a need that presses, if someone dear gave it to them, or if it is the only one there is
  (see Tastes). Trade, gifts, theft and buying all go by it.
- **Gifts and swaps** happen at the end of a friendly exchange. Someone fond enough and not too
  grasping may give away something they carry, the one that looks the best present by what they
  have seen of the other's tastes; otherwise two residents swap one item each if one gains by it
  and the other does not lose.
- **Theft.** A resident tempted enough takes someone else's thing from a container that nobody
  can see at that moment. Temptation grows with the item's worth to them, their greed and their
  resentment of the owner, and shrinks with empathy. The item changes hands but not owner.
  The theft is a fact about thief and victim; the thief knows it and keeps it to themselves,
  unless it is to confide in a close friend.
- **Finding out.** Whoever sees it learns it. The owner reacts only on learning who did it, by
  seeing it or being told. An owner who merely sees the empty spot knows something is missing,
  and is upset, but not who to blame.
- Talking things out after a crisis gives stolen things back.

## Tastes

- Every resident has a **profile of tastes** of their own, kept in `world.taste_profiles` and
  not on the resident: how much they like a category of item, a taste tag, or one item in
  particular, from -100 to 100. The rules are in `data/tastes.json`.
- A taste is two numbers kept apart: the **leaning** they came with, which never changes, and
  what they have **learned** since, which nothing moves yet. The taste is the two together.
- **Taste tags** are an item's `preference_tags`. They are not its `tags`, which are for rules and
  sorting and never make a taste. There is no list of them: whatever an item carries is one.
- A profile starts with what the resident's traits give (`tastes` in `data/traits.json`) and
  **fills as they meet things**. The first time they eat, use or are handed an item, a leaning
  is made for its category and for each taste tag they had none for, and kept. It comes from the
  settlement's seed, the resident's ID and the tag, so it is always the same for the same three,
  and making it draws nothing from the settlement's own randomness. Most are mild. About one
  item in seven is also something a resident loves or cannot stand for itself.
- **How much they like an item** is the mean of their tastes for its tags, plus a share of the
  one for its category. A taste for the item itself counts over those the stronger it is, without
  silencing them. Weighing things up uses the tastes there are and makes none.
- **A reaction** is one of hated, disliked, neutral, liked, loved. It is that liking as the
  moment colours it: a pressing need answered, their mood, and fondness for whoever handed it
  over. It moves their mood; a meal to their taste eases stress and one that is not adds to it;
  a present moves what they feel for the giver, down as well as up.
- **Choosing.** Among foods that answer their hunger they take what does most and what they like.
- **What is found out** is kept apart from the tastes, in `world.taste_knowledge`: how much has
  been *seen* of each taste of each resident, by the player and by each resident who was there.
  A taste is unknown, then suspected, then known. It moves on what happens: a reaction to a
  meal, a thing used or a present; something bought; a swap turned down over the thing offered;
  a taste spoken of in a friendly exchange. A reaction only shows the tastes that pulled the way
  it went: one that was outweighed, or that hunger got the better of, stays hidden. The taste a
  trait gives is known to the player from the start, as the trait is.
- `TasteSystem.found_out` is what a screen may show: each taste with how sure it is and which
  way it goes. Suspected, it says liked, disliked or neither; known, which of the five. There is
  never a number in it.
- A taste for something no content brings any longer stays in the save and does nothing.

## Friendship, romance and couples

Everything here is between adults, and nothing happens to anyone who does not want it.

- **Friendship** is a matter of degree and runs one way. What a resident feels for another
  amounts to a tier from `data/relationships.json` once affection and trust both reach it:
  friendship, then close friendship. Crossing into a tier, or falling out of it, is an event.
- **Attraction** is one more feeling, and it does not grow out of nothing. A friendly exchange
  raises it only where there is a spark, which is fixed by who the two are and is not the same
  in both directions, or where some attraction is felt already. Someone with a partner is slower
  to be drawn to anyone else. Arguments and fights lower it.
- **Saying so.** A single resident drawn enough to another who is also free, and fond enough of
  them, stops to wonder whether to tell them. That is a decision like any crisis, and the player
  may advise. Courage and rashness argue for speaking, and the timid keep quiet unless encouraged.
- **The answer** is the other's to give, from what they feel themselves. If they are drawn and fond
  enough in turn, the two are a couple from then on. If not, the one who spoke is hurt by it and
  cools towards them.
- **Time alone.** At night a couple may seek each other out to be alone. It only happens if the
  one sought wants it too, and only once nobody awake can see them: until then they wait. It is
  told as an event that the two went off alone, and no more. It eases stress and draws them closer.
  Two residents who are both free never do this: they say what they feel first.
- **Affairs.** Someone with a partner, drawn strongly enough to another and without the empathy
  to stop, may seek that other out instead, and so may someone drawn to a person who has a
  partner. If the other is willing it is an affair: the same event, but also a fact about the
  partner it is behind the back of.
- **Secrets.** Neither of the two tells anyone. A secret is only ever told to a close friend, and
  never to whoever it was kept from. The same goes for a thief's theft. But two people alone can
  be come across, and whoever sees them knows, and may talk.
- **Jealousy.** A resident who learns of an affair by seeing it or being told turns on their
  partner and, less, on the other one; an onlooker thinks worse of the two who did it and never
  of the one it was done to.
- **Breaking up.** A resident who resents their partner enough stops to wonder whether to go on.
  The player may advise leaving, talking or staying. Resentment argues for leaving; empathy and
  what fondness is left argue for talking it out. Leaving means going to tell the other, and only
  then is the couple over. The one left takes it harder.
- A death leaves a partner on their own.

## Who knows what

- An event can be recorded as a **fact**. The world keeps every fact; a resident only has a
  **belief** about the ones they learned, with a credibility and how they learned it.
- **Participants** know it. **Witnesses** are residents who are awake (not using something marked
  `unaware`, such as a bed), within `sight_range` tiles and with nothing opaque in between. Walls
  and doors are opaque (`data/terrain.json`), so what happens inside a shack stays inside.
- **In the dark**, during `dark_hours`, a thing is only witnessed from within `dark_sight_range`,
  unless it happens in the light: within reach of an object that gives `light`, with no wall in
  between. So by night what is done by a fire or under a lamp is seen as by day, and what is done
  away from them is seen by almost nobody. Whoever keeps watch still sees that much further.
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

## Starting a settlement

- `SimulationWorld.new_settlement` gives an empty plot, the map named in `data/tutorial.json`,
  with nobody on it. `demo_world` is the settlement that comes ready made, and has no opening.
- `FoundResidentCommand` makes the first resident, just inside the gate: a name, an age, a
  personality and up to two traits. It is refused once anyone lives or has died there. Their ID is made from their name, and never one that a newcomer or the dead have.
- The opening is a list of steps. A step has a goal: so many `residents`, a `building`, an
  `object` of a kind (under a roof, if `indoors`), someone with a `job`, minutes `elapsed`,
  something `answered`, or the step `acknowledged` with `AcknowledgeTutorialCommand`.
- A goal may also wait for a `deed`: something the player does that the simulation cannot see,
  such as drawing. Whoever shows the game says so with `ReportDeedCommand` and a name; it counts
  only if the step in hand asks for that name. The simulation never learns what a drawing is.
- Goals are checked every minute and after every command, so building with time stopped moves
  the opening on. Nothing is forced: a step is done by what the settlement has become.
- A finished step hands over its `gifts`, into the first container of a kind or to whoever has
  been there longest, and emits `tutorial_step_done`.
- While a settlement is on a step, nothing is rolled from outside. A step may open with a
  `stranger`: one comes to the gate for whoever is in and awake to answer, as soon as there is a
  bed to spare, and the step is done once they have been let in or sent away.
- Urbanismo refuses any change that would leave out of reach something that is within reach
  now: an object that is used, holds things or is a post, or the inside of a building. Reach is
  walked out from the map's `arrivals` and `spawns`. A bed is reached from beside its head.

## Determinism

All randomness comes from `SimulationRNG`, and its state is saved. What has to come out the same
whenever it is asked, such as a leaning for a taste, comes from `SimulationRNG.keyed`: a
generator of its own for that one question, which moves no other on. The same seed gives the same
event log, and a world saved mid-activity continues exactly as if it had never been saved. Both are
covered by tests. Player advice is part of the input: the same advice at the same minute gives
the same history.
