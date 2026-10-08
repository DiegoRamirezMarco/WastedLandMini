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
3. `ActivitySystem` walks the resident along the path (2 tiles per minute, each to any of the
   eight around; see "Getting there" below), then applies the use
   until its minutes run out or the needs it lowers reach zero. A use with `until` ends when
   that one need reaches zero: sleep eases stress too, but only tiredness decides when to wake.
   Any other bodily need reaching 85 cuts a long restful use short: hunger or thirst wakes a sleeper.

Starting a use emits an `activity_started` event with low importance. Eating emits the more
specific `meal_started` event so presentation can animate and sound the meal without owning it.

## Getting there

- A walk is a list of tiles, each beside the last, sideways or diagonally (`world/pathfinding.py`).
  Where a resident is, at the end of every minute, is one tile.
- The way is the straight line to where they are going, at whatever angle, if nothing is on it.
  Otherwise it is a way round, pulled straight between the corners it has to turn. A line is
  walked by the tiles nearest to it, none further than half a tile from it.
- A diagonal step needs both tiles it passes between to be free: nobody cuts the corner of a
  wall, and where two things touch at a corner there is no way through.
- Standing next to something, to use it or to talk, is beside it and never at its corner.
- `Resident.trail` is where they walked in the last minute: for each tile, the point of the line
  that is on it. It is there for whoever draws them, and it is not saved. The one thing that
  goes by it is who may step where during the minute it was walked in.

### In each other's way

- Nobody steps onto a tile that somebody else is on or has walked over this minute, or
  diagonally between two people (`simulation/ai/crowd.py`). Whoever is out of the settlement,
  or lying on a bed, is in nobody's way.
- Nobody plans to end up on a tile that somebody stands on or is heading for.
- A walk is planned as if nobody else were about. With somebody in the way of the next step:
  1. if they are passing, wait a minute for them to be gone;
  2. otherwise look for a way round, counting as obstacles everybody who stands still and
     whoever is walking within two tiles. If somebody has stopped on the very tile being made
     for, another place beside the same thing or person does as well;
  3. with no way round, whoever is in the way steps aside if they are only strolling or
     sheltering, to the nearest free tile off the walker's path;
  4. failing that, after two minutes held up the walk is given up for a short stroll a few
     tiles off, and whatever they wanted is thought of again afterwards.
- `Activity.held_up` counts the minutes running without a step along the path. It is saved.

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
  what is bought from a caravan, and what is handed over at the counter under barter, nothing
  reaches the shop any other way. A settlement with no shop or scrap pile yet puts food in a
  pantry and everything else in a crate.
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
  warning without power. Fuel brought in from outside is left in a crate, and it is the mechanic
  who carries it on to the generator: a load at a time, or at once when the generator is
  running low. With nobody at the workshop the fuel waits and the lamps go out. A settlement
  with no workbench has nobody to wait for, and there the fuel goes straight in.
- **Medicine.** The clinic's care uses it up. Whoever lies in a clinic bed with the medic on
  duty is given a unit from the cabinet, which goes on working in them for half a day; with
  none left they mend as anyone lying down does, and the settlement is told once a day
  (`no_medicine`). None is spent on what comes of going without water or food. It comes from
  outside: what a trip brings back goes to the cabinet, and what is bought from a caravan and
  left at the shop is fetched from there by the medic.
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
- **A caravan** comes in the morning and stays by the gate until night falls, with things drawn
  from its own list and some coin, and leaves nothing for nothing. Whoever brings it is
  somebody with a name, always the same, and no resident. They stand beside the way in, in
  the open, with their cart at their side; nobody plans to stop where they are, and whoever
  goes to deal with them stands next to them. Dealing with it is the player's to do: see
  *The fund, barter and currency*.
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

## Families

- **The date.** A settlement begins on the first of January of 2226 and its days are counted
  from there: twelve months, 365 days, no leap years. Everyone has a date of birth, their age
  follows from it, and a birthday comes round by itself. From eighty on, each day carries a
  small chance of dying of old age, which doubles every five years.
- **Who somebody is.** A sex, `m` or `f`; a gender, which is how they are spoken of and nothing
  else; and the sex of those they are drawn to, or both. Nobody courts, becomes a couple with or
  goes off alone with someone they are not drawn to, or anyone under age.
- **Kin together.** Being close kin keeps no two apart. Whoever sees them become a couple,
  marry or be alone together, or is told of it, thinks the worse of both. A child of two who
  are kin by blood takes the worse of its parents in every side of its way of being, and the
  flaws of both.
- **Libido** is one more side of a way of being. What it weighs at a given time falls with
  nerves, low spirits, tiredness and a hurt body. Two who get on very well and both want it
  enough go off alone together without being a couple.
- **Marrying.** A couple that is doing well thinks of it, the player may advise, one asks and
  the other answers.
- **Kin** are kept by ID for the living, the dead and those who never came in: parents by
  birth and by having been taken in, a spouse, and brothers and sisters. What is felt for close
  kin starts from being kin, and seeing one of their own hurt tells on whoever sees it.
- **At the gate.** Some come two together. Whoever answers decides for each, there has to be a
  bed for each one let in, and whoever is let in while the other is not does not forget it.
- **A child** may come when a man and a woman by sex go off alone together or marry. It is
  carried nine weeks and born a bundle: on the back of whichever parent is seeing to it, beside
  them when they sleep, fed by them at a cost in rest. Put down anywhere but a bed it fares
  worse the longer it is left. With no parent to see to it, someone is asked to take it in, with
  the player given a say, and if nobody does it dies. Twelve weeks on it is ten, and a resident
  like any other but for romance: whoever sees a child at work, hurt or taking something is the
  worse for it.
- **No bed.** Whoever is tired enough with no bed to go to lies down where they are, and
  rests the worse for it.
- **More mouths, more hands.** A job may take one more worker for every so many residents: the
  garden does, so that a settlement that grows goes on feeding itself.

## Politics

- **The player is nobody in the settlement.** They put things to people and advise, and never
  govern. Whoever leads is a resident like any other, with a role.
- **No government until there are three.** When a third resident lives there the adults take
  twelve hours to settle on a kind, each by what they hold, and the player may put one kind to
  them all, once. The ready-made settlement does it on its first day.
- **The kind of government is the player's to say** (`ChooseGovernmentCommand`), while they
  are settling on one or in place of the one they have. Nobody is asked, and what each would
  have had still counts: how many of them wanted it is how legitimate it starts, whoever
  wanted another trusts it less, and a change in the middle of a game unseats whoever governed
  and costs stability. A settlement of fewer than three is refused. What the residents vote
  and what comes of unrest can change it again.
- **A kind of government** says whether somebody leads, whether there is a council, and how the
  next leader comes to be: voted for by everyone or by the council, whoever is strongest,
  whoever the last one would have had, or whoever has the most behind them. Where there are
  terms, whoever leads has to win again.
- **Losing a leader ends nothing.** Dead, gone, voted out or resigned, the government's own
  ways name the next one, or the seat stands empty until they do.
- **What each resident holds** is kept apart from them: seven leanings that come of their way
  of being, their traits and something of their own, and what they feel about whoever leads
  (loyalty, which is to the person) and about the government (trust, fear and resentment).
- **It moves with what they learn.** Somebody who governs and is seen, or said, to have started
  a fight, stolen or killed is feared more and trusted less by whoever learns of it, each in
  their own way. Nobody thinks any different because the world knows.
- **Seven measures of the settlement**, from 0 to 100: legitimacy, public support, fear, unrest,
  stability, authoritarianism and corruption. A place can be afraid, obedient and full of
  resentment at once.
- **Charisma and leadership** are two more sides of a way of being: how readily others are won
  over by somebody, and how well others do under them.

### Affecting a resident

- **The one place where the player gives orders.** A resident who is stopped leaves off what
  they were doing and stands listening for a while. Told to see to a need, go to somebody, get
  on with something or simply hear a few words, they do it, as far as it can be done.
- **With somebody, only what they feel for them is on offer.** There is always talk. Past
  it, each thing has what it takes: a joke, a hug, a kiss, an insult, coming to blows. What one
  feels the other need not, and it is the one who is told whose feelings count.
- **Leisure**: a stroll, a sit, a doze or a tune alone; cards, stories, a dance or a drink
  with somebody. Each goes by a taste of theirs, which shows when they are at it: what they
  like does them more good.
- **One thing after another.** What is said while they are at something they were told
  waits its turn, and is done when the one before is over. What can no longer be done by then
  is let go. Any of it can be taken back.
- **Nothing unasked.** A resident can be told to do nothing of their own accord: they do what
  they are told, see to what was put in their hands, and otherwise stand by. A body that can
  wait no longer is seen to all the same.
- **It costs nothing**, and what is on offer follows from how things stand.

### Tasks, and taking things apart

- **A site in somebody's charge is their work**, ahead of their own post: by day they carry to
  it and work on it until it stands, and are paid as for a post. Others lend a hand in spare time.
- **A seat is taken if one is free.** Whoever goes to do something done sitting down, which
  is whatever a kind of manner of sitting lists, uses the thing from a tile with a seat on it
  if one beside it is free, and from the nearest free tile otherwise. Nothing else changes:
  not what they get of it, nor how long it takes.
- **With nothing to build with they sit by it and ask**, while there is something about that
  could be taken apart. The player tells them what: it is an order, and their task until done.
  What comes of it goes to the site, or to where such things are kept.
- **With nothing left to take apart they go out for it**, a short trip for that one thing.
- **The player breaks up an item for scrap**: what is nobody's at once, what is somebody's only
  if they agree.

### Proposals and votes

- **The player proposes and the settlement decides.** A proposal is a law, doing away with one,
  a vote for who leads, another kind of government, throwing somebody out, or another way of
  trading. Somebody who may propose under the government in force has to make it theirs:
  whoever of them is most for it, if any is. Otherwise it goes no further.
- **It is talked over, and then decided** by whoever the government says approves: whoever
  leads, the council, or every adult who is there. With nobody in the seat it names, the say
  falls to the council, and failing that to everybody. Nothing of it is done unless it passes.
- **Each of them votes by their own mind**: yes, no, or neither if it is too near the middle
  for somebody of their interest in politics. Their mind is made of what they hold and stand
  to gain or lose, what they feel for whoever it is about and know them to have done, what
  they feel for whoever put it, how far they trust the player if the player did, loyalty to
  whoever leads and what they hold against the government, fear where hands are shown, what
  they remember of politics, and what the player said to them. A ballot keeps the three that
  weighed most. Nothing is rolled.
- **A law that does not carry as put is tried milder**, a degree at a time, and passes at the
  first that carries. Where whoever leads may refuse what others approved and is against it,
  it is refused. What was turned down is left alone for a week, and a law just passed or
  done away with for two days.
- **A show of hands or a secret vote**, by the government. After a show of hands everybody
  knows who voted how, and whoever was voted against remembers who did it. After a secret
  vote only how many is known.
- **Residents propose things of their own**, once a day at most, where the government lets them:
  a law they hold with and have a reason for, doing away with one they cannot abide, a vote
  on a leader nobody is behind, another kind of government, or throwing out somebody they
  resent and know to have done wrong. Nobody proposes that for what they never came to know.
- **The player may speak to those who decide**, once each for each proposal, for it or against.
  It weighs by how much they lean on the player. They may go along, come half way, take no
  notice, or do the opposite.
- **What the player is to each resident** is a layer of its own: trust, which moves only with
  how what the player was behind turned out for them, and resistance, which comes of being
  pushed against their own mind and wears off. Both tell on any advice the player gives them.
- **Whoever is thrown out** walks to the gate and is gone for good: their post, their bed and
  what they kept are let go of as on a death, with no grave, and what they carried goes with
  them. They are still in the memories of those they left.

### Elections

- **Not everybody stands**: those who want the seat enough do, by their interest in politics,
  charisma, leadership and how they are thought of, and whoever leads already. Whoever puts
  themselves forward votes for themselves.
- **A result is kept**, and remembered: who each backed and how it went, whoever backed a loser
  trusts the government a little less, and a loser holds it against whoever won.
- **A count can be seen to.** A leader who stands to lose a vote cast in secret makes up their
  mind about it some hours before, with the player given a say. If they do, enough votes
  change hands in the count for them to win. Whoever sees them at it knows, and nobody else.
- **A sore loser says there was cheating**, whether there was or not, and whoever hears it makes
  of it what they make of them and of the government.
- **The player may speak for a candidate** to each resident once before a vote.

### Laws

- **A law is never only words.** Each is data: what it does at each degree, from mild to harsh,
  what weighs for or against it with each resident, and what brings somebody to propose it.
- **Keeping one is each resident's own affair**: how far they do as the government says, how
  legitimate the government is and what they make of the law, against how hard it is to keep.
  Whoever keeps it lives by it; whoever does not goes on as before.
- **Being seen to break one** is all that comes of it until there are trials: it is known,
  talked about, and held against them by whoever keeps that law. Two who break it together
  think none the worse of each other. Nothing comes of what nobody saw.
- **Want undoes what plenty passed.** How short the settlement is of food weighs on what
  anybody makes of a law that has people work less: a day of rest or short hours passed with
  the larder full is done away with when it runs low, and long hours and rationing find takers.
- **A day under a law** somebody is against is held against the government, and one they are
  for adds to their trust in it. A harsh law makes the place more authoritarian, and a
  nonsense costs legitimacy.
- **Whims.** Whoever leads an authoritarian enough settlement passes what takes their fancy:
  bans the food they cannot stand, has everybody greet them.

## Trials and punishment

- `world.justice` (`JusticeSystem`) tries people and punishes them; `world.courts`
  (`JusticeState`) is what is kept: trials, sentences being served, the history of punishments
  and what prisoners are given. All of it is data in `data/punishments.json`.
- **Somebody is tried for what is known of them.** `known_offences` is what a resident did
  that left a fact, that somebody else who is here knows by having seen it or been told, and
  that nobody was tried for. What only the world knows cannot be brought, and nobody is tried
  twice for one thing. There is one trial at a time.
- **Who accuses**: a resident, at one hour of the day, who knows of it surely enough and
  wants it answered for, by how grave it is, what they feel for whoever did it and how much
  justice matters to them. Nobody accuses their partner or their kin. It is theirs to decide
  and the player's to advise on (`accuse`). And the player, with `AccuseCommand`.
- **Six steps**, `step_minutes` apart: accusation, evidence (how many know of it), witnesses
  (who saw it, as against having heard it told), defence, verdict and punishment. Each is a
  domain event.
- **Who judges** is whoever decides anything under the government in force, and every adult
  where there is none. The accused never does. Each holds them guilty or not on what they
  believe they know (`belief_in_guilt`): what they saw counts whole and what they were told
  for less; having neither, they go by the witness they trust most; and what they feel for the
  accused and for whoever accuses weighs on it. More guilty than not is guilty. Found
  innocent, the accused holds it against whoever accused them.
- **The punishment is the player's to say** (`SentenceCommand`), out of `available`: nobody is
  sentenced to prison without a building whose use is `jail`, to the stocks without stocks, or
  to death without a gallows or a guillotine. Said nothing in `sentence_hours`, it is the
  least there is.
- **What each does**: a warning is a word. A fine goes into the fund, in coin as far as they
  have it, or under barter in things of theirs worth as much. Confiscation takes what is worth
  most of what they carry. Work for everybody weighs on them for its days. The stocks and
  prison keep them where they are served (`SERVE_ACTION`): they go nowhere and do nothing else,
  and at night they sleep where they are. Corporal punishment is an injury. Exile is
  `ExileSystem.banish`. Execution is a death.
- **A prisoner is given what the player says** (`SetPrisonRationCommand`): so many meals and so
  many drinks a day, of an item named or of whatever there is most of, out of what is nobody's.
  Given nothing, they go hungry like anybody who does not eat.
- **A punishment is a political event.** Whoever is there, or for one not done in public
  whoever is in the settlement, takes it one of five ways: with approval, fear, anger, grief
  or indifference, by whether the condemned is one of their own, whether they hold them
  guilty, and how far it goes beyond what was done. Each moves their political profile, their
  nerves and their mood, leaves a memory worded their own way, and adds to what the
  settlement's measures are moved by. A child's counts `child_factor` times, and nobody
  approves of a harsh one. It is all on record (`PunishmentRecord`).
- **Somebody exiled is heard of again**, `exile_return.days` later. Who they were is kept on
  their `Exile` record. One who left with a grudge may come with raiders, by `raid_chance`
  times that grudge. Otherwise they come to the gate, and whoever is there decides
  (`exile_back`), with the player's advice: let in, they are the same person with the same
  ID, kin and all. Turned away, or finding nobody for `tries` days, they are gone.

## Substances

- **Taking one.** A substance is an item: owned and used like any other, or had over a bar that
  holds it. It does what it does on the spot, and then it is on whoever took it for as long as
  it lasts: needs minute by minute, how fast they work, and for some whether they notice
  anything. When it wears off there is what comes after, for a while longer.
- **Being seen.** Whoever sees it taken knows it of them, and it weighs on what they feel for
  them by their own taste for people who drink, smoke or get high: some mind, some like it,
  some neither. Smoke reaches everyone under the same roof, seen or not, and nobody outside.
- **Too much.** Taken on top of itself it is an intoxication, an injury like any other, and
  enough of it kills. Only the rash take more of what they are already under.
- **Dependence** comes by chance each time, from the settlement's own randomness, likelier the
  more often it has been taken. Whoever depends on something wants it once enough time has
  gone by: they take it if they have it, want it above anything at a counter, and until they
  get it are on edge and slower at work. With enough time without, it passes; lying in the
  clinic under a medic, three times as fast, and somebody going without with nothing to take
  goes there of their own accord.
- **The player's say.** Starting on something that hooks, going back to it after days without,
  and now and then a habit, are decisions: they stop, the player may advise against it, and
  they make up their mind. A no lasts some hours; a yes, long enough to go and do it.
- **Where they come from.** Whoever keeps the bar makes what it serves, from water. The rest
  are made at a laboratory, which has to be worked out and built, and sold over its counter.

## Wear, repairs and credits

- **Wear.** An item with a `wear` property loses that much condition each time it is used: a tool
  for each unit it helps make, a weapon for each fight, a radio each time it is listened to. At 0
  it is broken and does nothing: no faster work, no harder blow, no comfort. Something too worn to
  put back is kept on its owner, to have it seen to.
- **Repairs.** A use with `repairs` mends a worn thing its owner brings, so much condition a
  minute, while the job it is `staffed_by` has someone on duty. It stops if they leave.
- **Credits.** With a currency, every minute on duty, or loading and unloading for the job,
  earns a resident a share of the hourly wage (`data/economy.json`, or the job's own `wage`),
  out of the common fund and as far as the fund goes. A use with a `price` takes that many
  credits when it starts, into the fund, and is not even considered by someone who cannot pay.
  A drink at the bar and a repair at the workbench both cost. The one thing nobody goes without
  for want of coin is the mending of the tool they work with.
- **Nobody gives away what they work with.** The tool of a resident's job is never made a
  present of, swapped or handed over. One they have besides it is theirs to give.
- **The shop.** A use with `sells` is buying one unit of something kept in that object, while its
  keeper is on duty. A thing costs its base value times the settlement's price factor, and more
  the fewer are left. What a resident wants to buy:
  - a tool for their own job when they carry none, above anything else;
  - a weapon, if they are afraid enough of someone and carry none;
  - otherwise whatever would do them most good right now for its price, unless they already own
    one, or two units if it is food.
  What is bought becomes the buyer's and goes with them. What was paid goes into the fund.

## The fund, barter and currency

- **The common fund** is what the settlement holds as a whole, apart from what anybody owns. In
  coin it is a figure. In things it is whatever lies in a container and is nobody's: the shop's
  shelves, the pantries, the scrap. It never goes below nothing.
- **A settlement trades by barter or with a currency.** A new one starts on barter. One that
  comes ready made, and a save from before, trade with the credits they always had.
- **It is the residents who settle it.** The player makes a currency by naming it and puts it to
  them, or puts it to them to go back to barter, with advice. Everyone who is in answers for
  themselves: greed and savings lean towards coin, things of their own and empathy towards
  barter. More for it than against, and it is done. They cannot be asked again for some days.
  The first currency a settlement takes up puts something in every pocket and in the fund. Going
  back to barter leaves what is held as it is, counting for nothing, and there if a currency is
  taken up again.
- **The settlement keeps whoever works for it, and nobody else.** Whoever has not worked for
  three days, post or no post, is no longer kept: it is said when it stops and when it starts
  again. Being in no state to work does not count against anybody, someone new has those days
  to find something to do, and a settlement still in its opening keeps everybody.
- **With a currency** wages come out of the fund and what is paid goes back into it: at a
  counter, at the bar, at the workbench, and one for every meal out of the commons. No coin is
  made or lost: it goes round. Whoever the settlement keeps is fed even with an empty pocket,
  and drinks water for nothing. Whoever it does not keep pays for both or goes without. With
  the fund empty wages go unpaid, which is said once a day and tells on whoever went without:
  mood, nerves, and slower work for each day running.
- **Under barter nothing is priced.** Whoever the settlement keeps eats, drinks at the bar and
  has things mended for nothing, and takes nothing home but one thing of each trip outside,
  for whoever makes it. Whoever it does not keep hands over the thing of theirs worth least to
  them for a meal, a drink of water, a drink at the bar or a repair, and with nothing to give
  goes without.
- **Hungry or thirsty enough, whoever is not kept and cannot pay helps themselves.** They wait
  until nobody is looking, unless they are past caring. Whoever sees it knows it of them.
- **Coin put by is spent.** Whoever keeps a counter can buy at it out of hours. Someone with
  enough to spare buys a present for whoever they are fondest of and gives it the next time
  they talk, stands a friend a drink they cannot pay for, and lends to a friend who is short.
  A loan is paid back when the borrower next has it, and tells on the two of them if it is not.
- **Residents raise it themselves.** Turned down at the counter often enough, somebody thinks
  of proposing a currency; unpaid for days, of going back to barter. The player advises, they
  decide, and if they go ahead everybody is asked with no advice.
- **What becomes the settlement's is carried to where it is kept**, by whoever was serving or
  whoever keeps the shop. A settlement with no counter keeps its fund in a crate.
- **A swap at the counter.** Under barter a resident goes to the counter for a thing they would
  give something of theirs for and come out better by their own lights. They cannot know
  beforehand what whoever keeps the counter will say: the keeper takes the swap only if they do
  not lose by it as they see it. What was given goes on the shelf as the settlement's. Turned
  down, they do not ask again that day.
- **Merchants.** While a caravan is at the gate the player sells it what is nobody's and buys
  from it, in one deal: it gives less for a thing than it asks for one, and less again for a
  worn one. Residents who know it is there go of their own accord, once, over what is theirs. With a currency the
  difference comes out of the fund or goes into it, as far as the fund and the caravan's purse
  go. Under barter what is handed over has to be worth what is taken. What is bought waits at the
  gate for whoever keeps the shop to carry in.
- **What is somebody's is theirs to sell.** The player can put it to a resident that they sell
  a merchant a thing of their own. They weigh what it is worth to them against what it fetches,
  and what it fetches is theirs: coin, or under barter a thing of the merchant's.
- **Credit can be stolen.** It is a figure and not coins in a pocket, but it is taken as a thing
  is: from someone asleep, with nobody looking on, by someone the same leaning would have steal a
  thing, and only by someone short of coin themselves or that way inclined by a trait. Whoever sees it knows, and holds it
  against the thief; the victim misses it on waking without knowing who.
- **So can the fund**, at the counter, when nobody is looking: coin, or under barter a thing off
  the shelf. Whoever keeps the counter sees that it is short.

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
  what they have **learned** since. The taste is the two together.
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
  never a number in it. The one place the figures are shown is the `Debug` switch on a resident's
  tastes, which is there for trying things out and not for play.
- A taste for something no content brings any longer stays in the save and does nothing.
- **What is lived moves what is learned**, by how good or bad it was and how much it mattered
  (`TasteSystem.learn`): a meal like any other hardly counts, and nearly dying of one counts for
  a great deal. Having a thing again adds a little to the taste for each of its tags, the way
  the reaction went, less each time and only so far; tags named as `habits` go faster and
  farther. The first time of a taste leaves a small mark of its own. A present leaves something
  of what is felt for the giver on the thing given.
- **A meal may turn on whoever eats it**: an item with a `sickens` property does, with that
  chance. They are hurt (`sickness`), turn against the thing and, less, against each thing it
  tasted of, and keep a memory of it. Nothing reads the memory back: what moved the taste has
  moved it once.
- **Nobody knows a taste has moved until they see it.** What an onlooker has of a taste is how
  it looked the last time it showed. Seeing it go the other way puts them back to suspecting
  it, the new way, however sure they were.
- **Tastes in people** are tastes like the others, of the kind `people`, defined as data: what
  the other has to be like (`who`, by their personality), what post they have to hold (`jobs`),
  or what has to be passing between the two (`when`: a piece of gossip, being given advice), and
  which feeling it moves. At the end of a friendly exchange, and when told a rumour, each one
  that comes into it moves what the resident feels for the other, one way only, and shows a
  little. A leaning for one is made the first time it comes into it.
- **Being told what to do** counts for more or less by that taste: it scales how much the
  player's advice weighs when a resident decides.

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

## Building

- What an object kind or a blueprint takes to put up is its `build`: a `cost` in units of
  items by tag, `minutes` of work, and a `job` that has to do it. With none it is put down at
  once, as everything is while a new settlement is in its opening.
- **Proposals.** `ProposeObjectCommand` and `ProposeBuildingCommand` put a thing and a place to
  a resident on the player's word. The place is judged as Urbanismo judges it. They answer at
  once, by the `build_proposal` decision: agreeing grows likelier with good spirits, empathy
  and nothing else to do, and less likely with stress, with each site already in their charge,
  with a long job and with nothing in store to build it with. Whoever refuses is not asked
  again until the decision's cooldown has passed; whoever agrees can be asked again at once.
  Nobody is asked who is away, unfit for work, in the middle of a decision, or who does not
  hold the job the thing asks for.
- **A site** is ground marked out, with whoever agreed in charge of it. Nothing else can be
  put there, and where what is coming blocks, the ground is shut off meanwhile.
  `CancelSiteCommand` gives it up and leaves what was brought in the nearest container.
- **Who works on it.** It is one more thing a resident may choose to do, when they have no work
  of their own to go to, no pressing need, and light to see by, and when the site is not out in
  a storm. Whoever is in charge wants to most. Anybody else may lend a hand, the more so the
  more they feel for others, and not at all for somebody they resent.
- **What they do.** While a site lacks something, they fetch it from the nearest container
  that holds any as nobody's, a load at a time, and carry it over. Things for sale are not
  taken, and nobody fetches what somebody else is already bringing. Once everything is there
  they work on it: each minute of each pair of hands counts, slower for a missing limb or low
  spirits, with only so many at a site at a time. A stint ends for a need, for nightfall, for
  their own shift or after `stint_minutes`.
- **When it is done** the thing stands where it was marked out, `site_finished` is emitted,
  and whoever saw to it is the better for it. If somebody is standing on ground it would shut
  off, it waits for them to move.
- Once an hour, a site that nothing can be done about gives notice, once a day: nothing to
  build it with anywhere, or nobody holding the job it asks for.
- What somebody is left holding when a site no longer wants it is taken back to where such
  things are kept. Whoever goes outside does not put away as a find what a site is waiting for.

## Research

- `data/research.json` lists the subjects. A settlement knows some, has one in hand or none,
  and keeps the minutes done on each of the rest.
- `SetResearchCommand` says which is in hand. It is the player's to say and nobody is asked: it
  is refused only for a subject that is known already, that does not exist, or that waits for
  another. Choosing another keeps what was done on the first.
- A job marked `research` is the post where it is done. Each minute a worker is on duty there
  adds to the subject in hand, slower for a missing limb or low spirits. Two desks with two
  workers go twice as fast.
- A subject that `needs` an item is not worked on until every unit of it is at the post. The
  worker fetches it as any worker fetches what their post is kept supplied with: from the
  container that holds most of it as nobody's, the shop included. Once it is all there it is
  used up, and is not asked for again if the subject is left and taken up later.
- When the minutes are done the subject is known, `research_finished` is emitted and nothing
  is in hand. What it `opens` can be proposed from then on; before, `PlaceObjectCommand`,
  `ProposeObjectCommand` and their like for buildings refuse it, the opening included.
- What it makes go better is asked for where the figure is used: `world.research.factor` is
  the product of that effect over every subject known, and 1 when none touches it.
- `demo_world`, and a save from before, start knowing every subject that opens up something
  they have standing, and whatever those require.
- Once an hour, while somebody holds the post, notice is given once a day if nothing has been
  chosen and something could be, or if the item the subject studies is nowhere to be had.

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

## Houses

- `world.homes` (`HousingState`) says whose each building with a roof is; `world.housing`
  (`HousingSystem`) is what follows from it. A building nobody owns is the settlement's.
- Who *lives* in a building is whoever owns it, whoever is with one of them, and their
  children. Who is *welcome* in it is whoever lives there and whoever one of its owners holds
  in enough affection (`welcome_affection`): the owner's feeling, not the visitor's. With its
  door locked only whoever lives there is.
- `may_use` is asked of every use the routine weighs: a bed under a roof is for whoever lives
  in that building, and so nobody's where nobody owns it; anything else in a house is for
  whoever is welcome. Whoever works at a thing always gets to it. Whoever has no bed to go to
  sleeps in the open, as they did when there was none free.
- `pressed` lets somebody in unasked for what would see to a need that has got past
  `desperate`, never for a bed and never through a locked door. `used` then emits `trespass`,
  seen by whoever is there and held against them by whoever lives there.
- A house changes who may go in for a thing, not whose the thing is: what is the settlement's
  stays on its books wherever it is kept.
- `qualities` adds up what `furnishing` says each kind of thing in a building is worth to its
  comfort, warmth, light and beauty, each kept from 0 to 100, a second of the same kind adding
  half as much. `rest_factor` makes a bed in one's own house rest the better for its comfort,
  and at midnight beauty lifts the mood of whoever owns the house, by `mood_per_day` at most.
- None of it applies while a new settlement is in its opening. When that ends, and in the
  ready-made settlement from the start, `settle` gives everybody without a house one of the
  buildings with beds to spare. After that it is the player who says.

## Dressing a building

- `world.decor` (`DecorSystem`) puts ornaments in buildings and takes them out. What there is
  to put is `registries.decor`; what has been put is in `world.homes`, with whose the
  building is.
- An ornament is where it is in cells of the inside of its building, from its back left
  corner: `CELLS` of them to a tile, each way. A piece of furniture on a tile takes the cell
  that tile starts at, and as many more across and down as it has tiles.
- One that stands takes cells no furniture and no other standing ornament has. One that lies
  flat is only in the way of another that does. One that hangs takes a stretch of the back
  wall, and only another that hangs is in its way.
- Nothing about an ornament touches the map: it blocks nobody, nobody uses it, and it is not
  an interactable. What it does is add to `HousingSystem.qualities`.

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
  now: an object that is used, holds things or is a post, the inside of a building, a site, or
  any ground at all. Reach is walked out from the map's `arrivals` and `spawns`. A bed is
  reached from beside its head.

## Determinism

All randomness comes from `SimulationRNG`, and its state is saved. What has to come out the same
whenever it is asked, such as a leaning for a taste, comes from `SimulationRNG.keyed`: a
generator of its own for that one question, which moves no other on. The same seed gives the same
event log, and a world saved mid-activity continues exactly as if it had never been saved. Both are
covered by tests. Player advice is part of the input: the same advice at the same minute gives
the same history.

Words are not part of the input. The line somebody says when an exchange begins comes from a
keyed generator, and the settlement's own is moved on as it was when lines came of it
(`LINE_DICE` in `simulation/social/social_system.py`), whatever lines there are: writing a line
in `data/dialogue.json`, or taking one out, changes how something is put and nothing that
happens.
