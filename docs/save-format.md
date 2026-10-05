# Save Format

Version saves from day one. The prototype starts with JSON behind `SaveManager`; SQLite can replace or complement it later without changing simulation entities.

Never save render-only state. Store stable IDs for residents, item definitions and item instances.

## Version 13 (current)

| Field | Content |
|---|---|
| `version` | `13` |
| `clock` | Day, hour, minute, tick size, paused, speed |
| `rng` | Seed and generator state, so randomness continues where it left off |
| `event_rng` | The same for the generator that world events are rolled with |
| `happened`, `weather` | Day each world event last happened; the weather now, as `event_id` and `until` |
| `upcoming` | World events on their way: `event_id`, `at`, and the `fact_id` of the word a radio gave of it |
| `at_the_gate`, `newcomers_seen` | ID of the newcomer waiting for an answer; IDs of all who have come before |
| `map_id` | ID of the map in `data/maps/` |
| `interactables` | Placed objects: `id`, `kind`, tile `x` and `y` |
| `residents` | `id`, `name`, tile `x` and `y`, `facing`, `needs`, `personality`, `current_action`, `activity`, `traits`, `inventory`, `job_id`, `post_id`, `work_progress`, `day_off`, `credits`, `age`, `couple_with`, `expedition`, `last_expedition_day`, `seeks_work`, `injuries` |
| `containers` | Per container object ID, the items inside |
| `item_count` | Counter behind item IDs |
| `thefts`, `theft_cooldowns`, `notices` | Record of every theft; last theft per resident; once-a-day notices already given |
| `relationships` | One entry per direction: `source_id`, `target_id`, the five feelings, `last_argued`, `bond` (the degree of friendship last held) and `last_together` |
| `memories` | Per resident ID, a list of `text`, `importance`, `emotional_value`, `people`, `tags`, `timestamp`, `location_id` |
| `facts` | Recorded facts: `fact_id`, `event_type`, `text`, `subject_ids`, `importance`, `timestamp`, `location_id`, `expires_at` |
| `beliefs` | Per resident ID, the facts they know: `fact_id`, `credibility`, `source`, `learned_at`, `told_by` |
| `vacancies` | Per job ID, the game minute since which it has been short of people |
| `decisions` | Open decisions with their options, deadline, crisis and, for a job offer, `job_id` |
| `decision_count`, `crisis_cooldowns` | Counter for decision IDs; game minute of each resident's last crisis, and of the last time each vacant job was offered |
| `deaths` | Everyone who has died: `resident_id`, `name`, `timestamp`, `cause`, `killer_id`, `grave_id` |
| `history` | Every noteworthy event so far, in full |
| `event_log` | Text history of emitted events |

A resident's `activity` is `null` or `action`, `target_id` (an object ID), `partner_id` (a resident
ID, when talking or walking over to talk), `intent` (the exchange they are set on having), the
remaining `path` as tiles, `minutes_left` and `using`.

A resident's `expedition` is `null` or `returns_at`, `finds`, `danger` and `find_at`.

An item is saved as `id`, `definition_id`, `owner_id`, `condition` and `quantity`, inside whichever
inventory holds it. An activity's `item_id` names the item involved.

Definitions (terrain, object kinds, items, the map itself) are not saved; they are looked up by ID
when loading.

## Loading older or damaged saves

- **Version 1** stored resident positions in pixels and had no map. Residents are placed on the
  map's spawn points and the default map is used.
- **Version 2** had no memories and no `partner_id`; both default to empty.
- **Version 3** had no facts, beliefs, decisions or history; all default to empty.
- A belief about a fact that is no longer in the save is dropped.
- A decision whose resident or kind no longer exists is dropped.
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
