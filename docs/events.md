# Event Design

Suggested importance bands:

- 0-29: ambient, auto-resolve
- 30-49: noteworthy
- 50-69: intervention candidate
- 70-89: major
- 90-100: critical crisis

Event types emitted so far:

| Type | When | Importance |
|---|---|---|
| `activity_started` | A resident starts using an object | 5 |
| `work_started` | A resident takes up their post | 5 |
| `chat_started` | Two residents start a friendly chat | 10 |
| `argument_started` | Two residents start an argument | 35, plus up to 30 with the resentment between them, plus 15 if one went looking for the other |
| `heart_to_heart_started` | A resident talks things out after a crisis | 30 |
| `rumor_told` | A resident tells another about a fact | 15 |
| `supplies_arrived` | The day's supplies reach a container | 10 |
| `no_food` | Someone finds nothing to eat (once a day) | 40 |
| `gift_given`, `trade_made` | Something changes hands after a friendly exchange | 20, 15 |
| `theft_committed` | A resident takes someone else's thing | 45 |
| `theft_noticed` | An owner sees that something of theirs is gone | 40 |
| `item_returned` | A stolen thing is handed back | 25 |
| `crisis_opened` | A resident boils over and waits for advice | 50 to 69, by anger |
| `fight_brewing` | A resident squares up to another and waits for advice | 60 to 69 |
| `fight_started` | Two residents come to blows | 60, plus up to 20 with resentment, plus 15 |
| `injured` | A resident comes out of something hurt | 45 |
| `death` | A resident dies | 95 |
| `crisis_resolved` | The resident decides what to do | Same as the crisis |

Every event carries its participants, its witnesses, the room it happened in (if any) and a
`timestamp` in game minutes. The HUD colours events by band and marks with `!` anyone waiting for advice and the
participants of an ongoing event of importance 50 or more. An event that important also drops
the game back to normal speed.

Events describe what is happening. Decisions describe how the player can influence it. Advice should usually modify the resident's decision inputs rather than directly commanding the outcome.
