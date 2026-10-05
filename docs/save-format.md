# Save Format

Version saves from day one. The prototype starts with JSON behind `SaveManager`; SQLite can replace or complement it later without changing simulation entities.

Never save render-only state. Store stable IDs for residents, item definitions and item instances.

## Version 7 (current)

| Field | Content |
|---|---|
| `version` | `7` |
| `clock` | Day, hour, minute, tick size, paused, speed |
| `rng` | Seed and generator state, so randomness continues where it left off |
| `map_id` | ID of the map in `data/maps/` |
| `interactables` | Placed objects: `id`, `kind`, tile `x` and `y` |
| `residents` | `id`, `name`, tile `x` and `y`, `facing`, `needs`, `personality`, `current_action`, `activity`, `traits`, `inventory`, `job_id`, `post_id`, `work_progress`, `injuries` |
| `containers` | Per container object ID, the items inside |
| `item_count` | Counter behind item IDs |
| `thefts`, `theft_cooldowns`, `notices` | Record of every theft; last theft per resident; once-a-day notices already given |
| `relationships` | One entry per direction: `source_id`, `target_id`, the five feelings and `last_argued` |
| `memories` | Per resident ID, a list of `text`, `importance`, `emotional_value`, `people`, `tags`, `timestamp`, `location_id` |
| `facts` | Recorded facts: `fact_id`, `event_type`, `text`, `subject_ids`, `importance`, `timestamp`, `location_id` |
| `beliefs` | Per resident ID, the facts they know: `fact_id`, `credibility`, `source`, `learned_at`, `told_by` |
| `decisions` | Open decisions with their options, deadline and crisis |
| `decision_count`, `crisis_cooldowns` | Counter for decision IDs; game minute of each resident's last crisis |
| `deaths` | Everyone who has died: `resident_id`, `name`, `timestamp`, `cause`, `killer_id`, `grave_id` |
| `history` | Every noteworthy event so far, in full |
| `event_log` | Text history of emitted events |

A resident's `activity` is `null` or `action`, `target_id` (an object ID), `partner_id` (a resident
ID, when talking or walking over to talk), `intent` (the exchange they are set on having), the
remaining `path` as tiles, `minutes_left` and `using`.

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
- A resident outside the map is moved to a spawn point.
- Every field has a default, so a missing field never makes a save unloadable.
