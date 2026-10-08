# Save Format

Version saves from day one. The prototype starts with JSON behind `SaveManager`; SQLite can replace or complement it later without changing simulation entities.

Never save render-only state. Store stable IDs for residents, item definitions and item instances.

## Version 34 (current)

| Field | Content |
|---|---|
| `version` | `36` |
| `clock` | Day, hour, minute, tick size, paused, speed |
| `rng` | Seed and generator state, so randomness continues where it left off |
| `event_rng` | The same for the generator that world events are rolled with |
| `happened`, `weather` | Day each world event last happened; the weather now, as `event_id` and `until` |
| `upcoming` | World events on their way: `event_id`, `at`, and the `fact_id` of the word a radio gave of it |
| `at_the_gate`, `newcomers_seen` | ID of the newcomer waiting for an answer; IDs of all who have come before |
| `under_raid` | ID of the raid at the gate while whoever is on watch decides what to do |
| `trading` | How the settlement trades: `currency` (its `currency_id`, `name` and `singular`, or `null` if it never made one), `in_use` (false under barter), `fund` (the coin the settlement holds as a whole), `currency_count`, `asked_on` (the day the residents were last asked), `refusals` (swaps turned down per resident ID since they last made something of it), and `asked_about` with `answers` (what was last put to them, and whether each was for it, by resident ID; nothing in a save from before P25) |
| `merchant` | Whoever has stopped by to trade, or `null`: `event_id`, `leaves_at`, `goods` (units per item ID), `purse`, `fact_id` (the fact of their being there), and `tile` and `cart`: where they stand and where their cart is, by its left tile, each as `[x, y]` or `null` |
| `housing` | Whose each building is: `owners` (resident IDs per room ID; a room that is missing is the settlement's), `names` and `uses` given by the player per room ID, `began` (whether houses have been given out for the first time), `locked` (the room IDs whose door is locked), `lifted_on` (the day a house last told on the mood of whoever lives in it), and what has been put in each to be looked at: `ornaments` (per room ID, each with `ornament_id`, `kind`, `on` which is `floor` or `wall`, and `x` and `y` in cells of its inside from its back left corner), `floors`, `walls` and `ornament_count` |
| `debts` | What residents have lent one another and not had back: `debtor_id`, `creditor_id`, `amount`, `since` (the day) and `overdue` |
| `at_gate` | Units of what was bought for the settlement that wait at the gate to be carried in, per item ID |
| `government` | The government the settlement has: `kind`, `leader`, `council`, the seven `measures`, `chosen_on`, `term_began`, `choosing_until`, `proposed`, `election_at`, `vacant_since`, `heir`, `resigned`; `laws` (per law ID: `degree`, `params`, `since`, `by`, `pushed`, `imposed`); `protests` (per law ID: `days`, `last_day` and `who` was there); `meals` (per resident ID, `[day, times]` eaten out of the commons); `proposals` waiting, per ID, and those `decided`, oldest first (each with `kind`, `by`, `sponsor`, `law`, `degree`, `target`, `government`, `params`, `text`, `raised_at`, `decides_at`, `lobbied`, `pushed`, `status`, `decided_at`, `passed_degree`, `ballots`, `open_ballot` and `imposed`); `proposal_count`, `refused` (per matter, the day from which it may be put again) and `raised_on` (day per resident); `elections` (each with `day`, `at`, `seat`, `way`, `candidates`, the `tally` given out, `winner`, who each voter `backed`, `open_ballot`, `rigged_by` and `claimed_by`); `recall`, `rigged_by`, `rig_asked` and `backing` for the vote that has been called |
| `political_profiles` | Per resident ID, the seven leanings and `loyalty`, `trust`, `fear` and `resentment` |
| `player_standing` | Per resident ID, what the player is to them: `trust` and `resistance` |
| `leaving`, `exiled` | Per resident ID, the game minute by which somebody thrown out is gone; and everyone thrown out, oldest first: `resident_id`, `name`, `at` and `why`, and, since S28, `back_at` (the game minute at which they are heard of again, or `null`), `grudge`, `tries`, `person` (who they were, for them to be the same if they are let back in) and `returned`. In a save from before, whoever was thrown out is gone for good |
| `courts` | Trials and punishments (S28): `trials` (each with `trial_id`, `accused`, `accuser`, `offence`, `fact_id`, `opened_at`, `step`, `next_at`, `witnesses`, `ballots`, `verdict`, `punishment` and `closed_at`), `trial_count`, `sentences` being served (`resident_id`, `punishment`, `trial_id`, `until`, `place_id`, `unfed_on`), the `history` of punishments carried out (`resident_id`, `name`, `offence`, `punishment`, `at`, `trial_id`, `present`, `kin`, `friends`, `reactions`, `child`), the `ration` prisoners are given (`meals`, `drinks`, `food`, `drink`, or `null` for what the data says), who is `weighing` an accusation, and whoever exiled is `at_gate`. Missing in an older save, which has none of it |
| `map_id` | ID of the map in `data/maps/` |
| `terrain`, `rooms` | The live terrain grid and stable room records after changes made in Urbanismo |
| `urbanism` | Stable placement counters and the terrain kept below constructed buildings, so they can be moved or removed later |
| `interactables` | Placed objects: `id`, `kind`, tile `x` and `y` |
| `sites`, `site_count` | What is being built: `id`, `kind` (`object` or `building`), `what` (the object kind or blueprint ID), tile `x` and `y`, `in_charge` (the resident who agreed to it), `delivered` (units brought so far, per item definition), `progress` (minutes of work done) and `started_at`; and the counter behind site IDs |
| `salvage` | What somebody has been told to take apart: `object_id`, `resident_id` and `progress` (minutes of work done) |
| `residents` | `id`, `name`, tile `x` and `y`, `facing`, `needs`, `personality`, `attributes` (`strength`, `constitution`, `dexterity`, `mind` and `senses` from 1 to 10, or `null` for somebody not asked yet), `mood`, `current_action`, `activity`, `traits`, `inventory`, `job_id`, `post_id`, `work_progress`, `day_off`, `credits`, `age`, `couple_with`, `expedition`, `last_expedition_day`, `seeks_work`, `injuries`, `dosed_until` (game minute until which the last dose given them in care goes on working), `lost_limbs` (limb IDs), `manners` (per kind ID from `data/manners.json`, the ID of the manner chosen for them) |
| `containers` | Per container object ID, the items inside |
| `item_count` | Counter behind item IDs |
| `thefts`, `theft_cooldowns`, `notices` | Record of every theft, with the `amount` of credit taken when it was not an item and `@fund` for a `victim_id` when it was the settlement's; last theft per resident; once-a-day notices already given |
| `relationships` | One entry per direction: `source_id`, `target_id`, the five feelings, `last_argued`, `bond` (the degree of friendship last held) and `last_together` |
| `memories` | Per resident ID, a list of `text`, `importance`, `emotional_value`, `people`, `tags`, `timestamp`, `location_id` |
| `facts` | Recorded facts: `fact_id`, `event_type`, `text`, `subject_ids`, `importance`, `timestamp`, `location_id`, `expires_at` |
| `beliefs` | Per resident ID, the facts they know: `fact_id`, `credibility`, `source`, `learned_at`, `told_by` |
| `vacancies` | Per job ID, the game minute since which it has been short of people |
| `research` | What the settlement knows and is working out: `subject` (the subject in hand, or `null`), `known` (subject IDs from `data/research.json`, oldest first), `progress` (minutes done per subject not yet known) and `supplied` (subjects whose item has been handed over and used up) |
| `decisions` | Open decisions with their options, deadline, crisis and, for a job offer, `job_id`; for one about a thing, its `subject` and the `inputs` that weigh on it |
| `decision_count`, `crisis_cooldowns` | Counter for decision IDs; game minute of each resident's last crisis, and of the last time each vacant job was offered |
| `deaths` | Everyone who has died: `resident_id`, `name`, `timestamp`, `cause`, `killer_id`, `grave_id` |
| `history` | Every noteworthy event so far, in full, with its `data` |
| `event_log` | Text history of emitted events |
| `tastes` | Per resident ID, their tastes under `category`, `tag`, `item` and `people`: each a name with its `leaning` and what has been `learned` |
| `taste_seen_as` | The same way round as `taste_knowledge`: the reaction each taste looked like the last time it showed |
| `taste_knowledge` | Per onlooker (`@player`, or a resident ID), per resident, per taste (`tag:sweet`, `item:stew`, `category:food`): how much of it has been seen |
| `tutorial` | Where a new settlement is in its opening: `step` (a step ID from `data/tutorial.json`, or `null` once it is over or if it never had one), `since` (game minute the step began), `opened`, `acknowledged`, the `deeds` the player has done of what the step asks them to do themselves, and the IDs of the steps `done` |

A resident's `activity` is `null` or `action`, `target_id` (an object ID, or a site ID), `partner_id` (a resident
ID, when talking or walking over to talk), `intent` (the exchange they are set on having), the
remaining `path` as tiles, `minutes_left`, `using` and `held_up` (minutes running that somebody
in the way has kept them from a step along that path).

A resident's `expedition` is `null` or `returns_at`, `finds`, `danger`, `find_at` and `fetch`.

An item is saved as `id`, `definition_id`, `owner_id`, `condition`, `quantity` and `given_by` (the
resident who made a present of it, or `null`), inside whichever
inventory holds it. An activity's `item_id` names the item involved.

Definitions (terrain kinds, object kinds, building blueprints and items) are not saved; they are
looked up by ID when loading. The live terrain and rooms are saved because Urbanismo may change
them after the map definition was loaded.

## Loading older or damaged saves

- **Version 1** stored resident positions in pixels and had no map. Residents are placed on the
  map's spawn points and the default map is used.
- **Version 2** had no memories and no `partner_id`; both default to empty.
- **Version 3** had no facts, beliefs, decisions or history; all default to empty.
- A belief about a fact that is no longer in the save is dropped.
- A decision whose resident or kind no longer exists is dropped.
- **Version 34** added `housing`. In an older save everybody is given the house they were
  sleeping in, by how many beds each building has, unless the settlement is still in its
  opening. An owner who no longer lives here, and a building that is no longer there, are
  dropped.
- **Version 33** added `tile` and `cart` to `merchant`. Whoever was at the gate in an older
  save is found a place as they would be on coming. A place that is not two whole numbers
  is none.
- **Version 36** added `attributes` on a resident (S46). In an older save everybody has what
  the settlement's seed gives them, the first time it is asked. What is out of bounds is
  brought back in.
- **Version 35** added `imposed` on a law in force and on a proposal, and `protests` inside
  `government` (S45). In an older save every law was voted and nobody is out against any.
  Somebody who is no longer there is dropped from a protest, and so is a protest against a
  law that is no longer in force.
- **Version 32** added `salvage`, and `fetch` in a resident's `expedition` (the one item a trip
  is for, or `null`). In an older save nobody has been told to take anything apart. An entry
  for something that is no longer there, or for somebody who is, is dropped.
- **Version 31** added, inside `government`, `laws`, `meals`, `proposals`, `decided`,
  `proposal_count`, `refused`, `raised_on`, `elections`, `recall`, `rigged_by`, `rig_asked` and
  `backing`; and `player_standing`, `leaving` and `exiled`. In an older save there are no laws,
  nothing waits to be decided, no vote is on record, nobody has been thrown out, and the
  player is in the middle for trust with everybody. A law or a kind of proposal that is no
  longer defined is dropped, and so is somebody on their way out who is no longer there.
- **Version 30** added `charisma` and `leadership` among the sides of a personality; a resident's
  `roles`; `government` (its `kind`, `leader`, `council`, the seven `measures`, `chosen_on`,
  `term_began`, `choosing_until` and what was `proposed` while a kind is being chosen,
  `election_at`, `vacant_since`, `heir` and `resigned`); `political_profiles` (per resident ID:
  the seven leanings, and `loyalty`, `trust`, `fear` and `resentment`); and `government` on an
  event in `history` that is a political one. In an older save everyone is in the middle for
  both sides, nobody holds a role, and there is no government: one is chosen as the game goes on.
- **Version 29** added a resident's `born` (the day they were born, counted as the settlement's
  days are, less than 1 for before it began), `sex`, `gender`, `drawn_to`, `expecting_with` and
  `due_day`, and `libido` among the sides of their personality; `kinship` (per person ID, living,
  dead or never let in: `name`, `gender`, `parents`, `adoptive`, `siblings` and `spouse`);
  `bundles` (children under ten: who they are, where they are and how they fare); and
  `gate_party` (everyone waiting at the gate together). In an older save everyone has the date
  of birth that makes them the age they were, is who the game says or their ID makes them, is
  drawn to both, and is kin to nobody.
- **Version 28** added what each resident is `under` (what they have taken and are under or
  coming down from: `item_id`, `until`, `after_until`, `sign` and `unaware`), their `habits` (per
  item ID: `uses`, `last_taken`, `dependent`, `without`, `recovered`, `allowed_until` and
  `resisting_until`) and `tempted_by` (the item they stopped to think over). In an older save
  nobody is under anything or has a habit, and the bar, which holds what it serves from now on,
  starts with what the map puts in it. A habit of something no content defines any longer is kept.
- **Version 27** added a resident's `last_worked`, `unpaid_on` and `unpaid_days`, an item's
  `meant_for` (the resident it was bought as a present for, or `@fund` while it is the
  settlement's and on its way to the till), `debts`, `at_gate` and `refusals`. In an older save
  everybody has just worked, nobody owes anything and nothing waits. What is owed to or by
  somebody who is gone is dropped.
- **Version 26** added `trading`, `merchant` and a theft's `amount`. An older save trades with
  the credits it had, called as `data/economy.json` calls them, and its fund starts with what a
  currency just taken up would have put in it. A merchant whose event is gone, or is no longer
  one that trades, has moved on; what they carried that no content defines any longer is left out.
- **Version 25** added `research`. An older save knows every subject that opens up something
  it has standing, and whatever those take knowing, and is working nothing out. A subject that
  is no longer defined is forgotten.
- **Version 24** added `sites`. An older save has nothing being built, and what stands in it
  stands as it did. A site for an object kind or a blueprint that is no longer defined, or that
  no longer fits on the map, is dropped along with what had been brought to it.
- **Version 23** added `dosed_until` and medicine in the clinic's cabinet. An older save has nobody
  under a dose, and its cabinet starts with what the map puts in it; no other container is
  restocked. On the built-in map the south house's two beds and its crate are moved to where
  nobody is walled in by them, unless they no longer stand where the map first had them.
- **Version 22** added `held_up` to an activity. An older save has nobody held up. It may have
  two residents on one tile, as could happen before: nothing moves them, and they walk apart.
- **Version 21** added each resident's `manners`. Whoever has none chosen for a kind, as in any
  older save, goes by the one that is theirs by default: always the same for the same resident
  ID. A manner that is no longer defined, or is kept under a kind it is not of, is dropped.
- **Version 20** added tastes in `people` and `taste_seen_as`. An older save has no tastes in
  people yet, and what was known of the rest is shown as it stands until it shows again.
- **Version 19** added `tastes`, `taste_knowledge` and an item's `given_by`. An older save has no
  tastes but those its residents' traits give: the rest are made as things are met, as in a new
  settlement. Tastes for tags and items that no content defines any longer are kept as they are.
- **Version 18** added `tutorial`. An older save is past its opening, and so is one made on a step
  that is no longer defined. Drawings are not part of a save: they are kept as pictures, by ID.
- **Version 17** added the editable terrain, rooms and construction underlays. Older saves use the
  rooms and terrain from their registered map and can be edited normally after loading.
- **Version 16** added thirst, mood, the water tank's stock and generator fuel. Older saves load
  with thirst and mood defaults, and gain the new map stock if they were made before the map
  change.
- **Version 15** had no thirst, mood, water stock or generator fuel.
- **Version 14** had no lost limbs and no particulars on its events: everyone loads whole.
- A lost limb that is no longer defined, or listed twice, is dropped.
- **Version 13** had no raids, and has simply never had one. Raiders at the gate whom nobody is
  deciding about are dropped.
- **Version 12** had nothing on its way and no radio in the cantina. It gains the radio.
- An event on its way that is no longer defined is dropped. One whose word nobody has any more
  is kept, and is simply unheard again.
- **Version 11** had no world events. Nothing has happened to it yet, its events are rolled from
  the seed it was started with, and it gains the beds a newcomer needs.
- Weather of a kind that is no longer defined is dropped, and so is a stranger at the gate whom
  nobody is deciding about.
- **Version 10** had no trips outside. It gains the cart, a bed, and the scrap the piles now
  hold, as any save older than the last change to the map does, and nobody is out.
- A trip is only kept together with the activity of being out there, and that activity only with
  its trip.
- **Version 9** had no ages, couples or degrees of friendship. Everyone loads aged 30 and single.
- A couple is only kept if both are in the save and each names the other.
- **Version 8** is the same format. The number only marks a change to the built-in map, which
  gave the shop its shelves and the settlement its lamps and scrap. A save older than the last such change gains the objects the map has
  been given since, wherever it has nothing standing, and containers among them start with the
  map's stock. A save of the current version keeps exactly the objects it was made with.
- **Version 7** had no credits, days off, vacancies or shop. Residents load with the settlement's
  starting credits and no day off, and the map's new objects are added as above. The new posts
  stand empty, so they are offered to the residents there are.
- **Version 6** had no injuries or deaths; everyone loads unhurt.
- **Version 5** had no jobs and a smaller settlement. Its residents load without a job, and the
  map's current objects are used instead of the saved ones, so the new buildings are furnished.
- **Version 4** had no items and food never ran out. The map's starting stock is added.
- An item whose definition is gone, for instance from a removed content pack, is kept as an inert
  "unknown object": nobody eats, uses, gives or values it. If the pack comes back, so does the item.
- Items in a container that no longer exists go back to their owners; shared ones are lost.
- A saved conversation is dropped if the partner is missing or is not in the same conversation.
- A `map_id` that no longer exists falls back to the default map, with that map's own objects.
- Objects whose `kind` is no longer defined are dropped, and activities that targeted them end.
- A resident outside the map, or standing where the map now has a wall, is moved to a spawn point.
  A saved walk that would cross a wall is dropped.
- A decision about a job that is no longer defined is dropped, and so is its vacancy.
- Every field has a default, so a missing field never makes a save unloadable.
